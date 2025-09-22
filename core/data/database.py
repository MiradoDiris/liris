import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime
from utils.logger import logger
from utils.exceptions import DatabaseError

class Database:
    """
    Classe pour gérer les interactions avec la base de données SQLite.
    Utilise un context manager pour gérer les connexions et éviter les locks.
    """

    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "liris.db")
        else:
            self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        logger.info(f"Chemin de la base de données configuré: {self.db_path}")
        self._init_tables()
        
    @property
    def conn(self):
        """Propriété de compatibilité pour l'accès direct à la connexion"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"Erreur lors de la création de la connexion: {e}")
            raise DatabaseError(f"Impossible de créer la connexion: {e}")
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"Erreur de base de données (verrouillage probable): {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(f"La base de données est verrouillée: {e}")
        finally:
            if conn:
                conn.close()

    def execute_query(self, query, params=(), fetch=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch == 'one': return cursor.fetchone()
            if fetch == 'all': return cursor.fetchall()
            if fetch == 'lastrowid': return cursor.lastrowid
            return cursor.rowcount

    def _init_tables(self):
        queries = [
            "CREATE TABLE IF NOT EXISTS platforms (id INTEGER PRIMARY KEY, name TEXT UNIQUE, profile_data TEXT, created_at TEXT, updated_at TEXT)",
            "CREATE TABLE IF NOT EXISTS project_profiles (id INTEGER PRIMARY KEY, name TEXT UNIQUE, profile_data TEXT, created_at TEXT, updated_at TEXT)",
            "CREATE TABLE IF NOT EXISTS context_typologies (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT, is_hierarchical BOOLEAN)",
            "CREATE TABLE IF NOT EXISTS strategy_items (id INTEGER PRIMARY KEY, typology_id INTEGER, name TEXT, type TEXT, parent_id INTEGER, description TEXT, properties TEXT, FOREIGN KEY(typology_id) REFERENCES context_typologies(id))",
            "CREATE TABLE IF NOT EXISTS clusters (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, created_at TEXT)",
            "CREATE TABLE IF NOT EXISTS labels (id TEXT PRIMARY KEY, name TEXT NOT NULL, cluster_id TEXT, parent_id TEXT, level INTEGER, created_at TEXT)",
            "CREATE TABLE IF NOT EXISTS generation_history (id INTEGER PRIMARY KEY, prompt_base TEXT, context_ids TEXT, batch_count INTEGER, created_at TEXT, status TEXT)"
        ]
        for query in queries:
            self.execute_query(query)
        logger.info("Vérification des tables de base terminée.")

    def add_typology(self, name, description, is_hierarchical):
        try:
            return self.execute_query("INSERT INTO context_typologies (name, description, is_hierarchical) VALUES (?, ?, ?)", (name, description, is_hierarchical), fetch='lastrowid')
        except sqlite3.IntegrityError:
            raise ValueError(f"Une typologie nommée '{name}' existe déjà.")

    def get_typologies(self):
        return self.execute_query("SELECT id, name, is_hierarchical FROM context_typologies ORDER BY name", fetch='all')

    def get_typology_details(self, typology_id):
        return self.execute_query("SELECT name, description, is_hierarchical FROM context_typologies WHERE id = ?", (typology_id,), fetch='one')

    def update_typology(self, typology_id, name, description, is_hierarchical):
        try:
            self.execute_query("UPDATE context_typologies SET name = ?, description = ?, is_hierarchical = ? WHERE id = ?", (name, description, is_hierarchical, typology_id))
        except sqlite3.IntegrityError:
            raise ValueError(f"Une typologie nommée '{name}' existe déjà.")

    def delete_typology(self, typology_id):
        count_result = self.execute_query("SELECT COUNT(*) FROM strategy_items WHERE typology_id = ?", (typology_id,), fetch='one')
        if count_result and count_result[0] > 0:
            raise ValueError("Impossible de supprimer : cette typologie est utilisée par des éléments de stratégie.")
        self.execute_query("DELETE FROM context_typologies WHERE id = ?", (typology_id,))

    def get_all_platforms(self):
        """Récupère toutes les plateformes de la base de données."""
        try:
            platforms = self.execute_query("SELECT id, name, profile_data FROM platforms ORDER BY name", fetch='all')
            return {p['name']: {'id': p['id'], 'profile': json.loads(p['profile_data'])} for p in platforms}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de toutes les plateformes: {e}")
            return {}

    def get_platform(self, platform_name):
        """Récupère le profil d'une plateforme spécifique par son nom."""
        try:
            platform = self.execute_query("SELECT profile_data FROM platforms WHERE name = ?", (platform_name,), fetch='one')
            if platform:
                return json.loads(platform['profile_data'])
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la plateforme '{platform_name}': {e}")
            return None

    def clear_strategy_items(self, typology_id):
        self.execute_query("DELETE FROM strategy_items WHERE typology_id = ?", (typology_id,))

    def add_strategy_item(self, name, item_type, parent_id, description, properties, typology_id):
        return self.execute_query(
            "INSERT INTO strategy_items (name, type, parent_id, description, properties, typology_id) VALUES (?, ?, ?, ?, ?, ?)",
            (name, item_type, parent_id, description, properties, typology_id),
            fetch='lastrowid'
        )

    def get_strategy_items(self, typology_id):
        return self.execute_query("SELECT * FROM strategy_items WHERE typology_id = ? ORDER BY id", (typology_id,), fetch='all')

    def get_typology_names(self):
        return self.execute_query("SELECT name FROM context_typologies", fetch='all')
