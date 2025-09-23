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
        self._update_database_schema()
    
        logger.info("Vérification des tables de base terminée.")
        
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
            # Platforms table
            """CREATE TABLE IF NOT EXISTS platforms (
                id INTEGER PRIMARY KEY, 
                name TEXT UNIQUE, 
                profile_data TEXT, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, 
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Project profiles table  
            """CREATE TABLE IF NOT EXISTS project_profiles (
                id INTEGER PRIMARY KEY, 
                name TEXT UNIQUE, 
                profile_data TEXT, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, 
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Context typologies table (FIXED: removed strategy_id constraint)
            """CREATE TABLE IF NOT EXISTS context_typologies (
                id INTEGER PRIMARY KEY, 
                name TEXT UNIQUE, 
                description TEXT, 
                is_hierarchical BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Strategy items table
            """CREATE TABLE IF NOT EXISTS strategy_items (
                id INTEGER PRIMARY KEY, 
                typology_id INTEGER, 
                name TEXT, 
                type TEXT, 
                parent_id INTEGER, 
                description TEXT, 
                properties TEXT, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(typology_id) REFERENCES context_typologies(id) ON DELETE CASCADE
            )""",
            
            # Clusters table
            """CREATE TABLE IF NOT EXISTS clusters (
                id TEXT PRIMARY KEY, 
                name TEXT NOT NULL, 
                description TEXT, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Labels table
            """CREATE TABLE IF NOT EXISTS labels (
                id TEXT PRIMARY KEY, 
                name TEXT NOT NULL, 
                cluster_id TEXT, 
                parent_id TEXT, 
                level INTEGER, 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(cluster_id) REFERENCES clusters(id) ON DELETE CASCADE
            )""",
            
            # Generation history table
            """CREATE TABLE IF NOT EXISTS generation_history (
                id INTEGER PRIMARY KEY, 
                prompt_base TEXT, 
                context_ids TEXT, 
                batch_count INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, 
                status TEXT DEFAULT 'completed'
            )"""
        ]
        
        for query in queries:
            try:
                self.execute_query(query)
            except Exception as e:
                logger.error(f"Error creating table with query: {query}\nError: {e}")
        
        logger.info("Vérification des tables de base terminée.")

    def _update_database_schema(self):
        """Met à jour le schéma de la base de données si nécessaire"""
        try:
            # Vérifier si la colonne strategy_id existe encore
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(context_typologies)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'strategy_id' in columns:
                # Créer une table temporaire sans strategy_id
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS context_typologies_temp (
                        id INTEGER PRIMARY KEY, 
                        name TEXT UNIQUE, 
                        description TEXT, 
                        is_hierarchical BOOLEAN DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Copier les données
                cursor.execute("""
                    INSERT INTO context_typologies_temp (id, name, description, is_hierarchical, created_at)
                    SELECT id, name, description, is_hierarchical, created_at 
                    FROM context_typologies
                """)
                
                # Supprimer l'ancienne table et renommer la nouvelle
                cursor.execute("DROP TABLE context_typologies")
                cursor.execute("ALTER TABLE context_typologies_temp RENAME TO context_typologies")
                
                self.conn.commit()
                logger.info("Schéma de la base de données mis à jour")
                
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du schéma: {e}")
            self.conn.rollback()

    # === MÉTHODES POUR LES TYPOLOGIES ===
    def add_typology(self, name, description, is_hierarchical):
        try:
            # Vérifier d'abord si la typologie existe déjà
            existing = self.execute_query(
                "SELECT id FROM context_typologies WHERE name = ?", 
                (name,), 
                fetch='one'
            )
            
            if existing:
                raise ValueError(f"Une typologie nommée '{name}' existe déjà.")
                
            return self.execute_query(
                "INSERT INTO context_typologies (name, description, is_hierarchical) VALUES (?, ?, ?)", 
                (name, description, 1 if is_hierarchical else 0), 
                fetch='lastrowid'
            )
        except sqlite3.IntegrityError as e:
            # Capturer l'erreur d'intégrité SQLite
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Une typologie nommée '{name}' existe déjà.")
            raise DatabaseError(f"Erreur base de données: {e}")

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

    # === MÉTHODES POUR LA STRATÉGIE ===
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

    # === NOUVELLES MÉTHODES POUR L'HISTORIQUE DES GÉNÉRATIONS ===
    def get_generation_history(self):
        """Récupère l'historique des générations pour l'analyse des combinaisons"""
        try:
            return self.execute_query(
                "SELECT id, prompt_base, context_ids, batch_count, created_at, status FROM generation_history ORDER BY created_at DESC",
                fetch='all'
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique des générations: {e}")
            return []

    def add_generation_record(self, prompt_base, context_ids, batch_count=1, status="completed"):
        """Ajoute un enregistrement dans l'historique des générations"""
        try:
            created_at = datetime.now().isoformat()
            context_ids_json = json.dumps(context_ids) if isinstance(context_ids, (list, dict)) else str(context_ids)
            
            return self.execute_query(
                "INSERT INTO generation_history (prompt_base, context_ids, batch_count, created_at, status) VALUES (?, ?, ?, ?, ?)",
                (prompt_base, context_ids_json, batch_count, created_at, status),
                fetch='lastrowid'
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'un enregistrement de génération: {e}")
            return None

    # === MÉTHODES POUR LES PLATEFORMES ===
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

    # === MÉTHODES POUR LES DATASETS (si nécessaire) ===
    def get_datasets(self):
        """Récupère la liste des datasets (méthode de compatibilité)"""
        try:
            # Si vous avez une table datasets, adaptez cette requête
            return self.execute_query("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%dataset%'", fetch='all')
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des datasets: {e}")
            return []

    # === MÉTHODE DE COMPATIBILITÉ POUR L'ACCÈS AU CHEMIN ===
    def get_db_path(self):
        """Retourne le chemin de la base de données pour la compatibilité"""
        return self.db_path