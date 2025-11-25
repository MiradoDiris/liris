import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class DatasetDatabase:
    """
    Gestionnaire de base de données pour les projets de datasets.
    Gère la connexion SQLite et les opérations CRUD sur les projets avec structure hiérarchique complète.
    
    Structure hiérarchique supportée:
    Project → Typologies → Taxonomy Clusters → Root Labels → Parent Labels → Children (infini)
    """

    def __init__(self, db_path="data/liris.db"):
        self.db_path = os.path.join("data", db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.connection = None
        self._init_connection()
        self._create_tables()

    def _init_connection(self):
        """Initialise la connexion à la base de données SQLite"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            
            # Activer les clés étrangères
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # Test de structure
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT id FROM projects LIMIT 1")
                logger.info("Structure de table valide")
            except Exception as e:
                logger.warning(f"Table corrompue détectée : {str(e)}")
                logger.info("Suppression des tables corrompues...")
                cursor = self.connection.cursor()
                cursor.execute("DROP TABLE IF EXISTS child_labels")
                cursor.execute("DROP TABLE IF EXISTS parent_labels")
                cursor.execute("DROP TABLE IF EXISTS root_labels")
                cursor.execute("DROP TABLE IF EXISTS taxonomy_clusters")
                cursor.execute("DROP TABLE IF EXISTS typologies")
                cursor.execute("DROP TABLE IF EXISTS projects")
                cursor.execute("DROP TABLE IF EXISTS platforms")
                self.connection.commit()
                logger.info("Tables corrompues supprimées")

            logger.info(f"Base de données initialisée avec succès : {self.db_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données : {str(e)}")
            self.connection = None
            raise e

    def _create_tables(self):
        """Crée les tables nécessaires pour la structure hiérarchique complète"""
        try:
            cursor = self.connection.cursor()

            # Table principale des projets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table des typologies
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS typologies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, name)
                )
            ''')

            # Table des clusters de taxonomie
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS taxonomy_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typologie_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (typologie_id) REFERENCES typologies(id) ON DELETE CASCADE,
                    UNIQUE(typologie_id, name)
                )
            ''')

            # Table des root labels
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS root_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    taxonomy_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'default',
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (taxonomy_id) REFERENCES taxonomy_clusters(id) ON DELETE CASCADE,
                    UNIQUE(taxonomy_id, name)
                )
            ''')

            # Table des parent labels
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parent_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'default',
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (root_id) REFERENCES root_labels(id) ON DELETE CASCADE,
                    UNIQUE(root_id, name)
                )
            ''')

            # Table des child labels (hiérarchie infinie via parent_child_id)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS child_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_label_id INTEGER,
                    parent_child_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'default',
                    depth INTEGER DEFAULT 0,
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (parent_label_id) REFERENCES parent_labels(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_child_id) REFERENCES child_labels(id) ON DELETE CASCADE,
                    CHECK (
                        (parent_label_id IS NOT NULL AND parent_child_id IS NULL) OR
                        (parent_label_id IS NULL AND parent_child_id IS NOT NULL)
                    )
                )
            ''')

            # Table pour les plateformes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS platforms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    config TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    batch_number INTEGER NOT NULL,
                    total_batches INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, batch_number)
                )
            ''')
            
            # Index pour optimiser les requêtes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batches_project ON batches(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status)')

            # Index pour optimiser les requêtes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_typologies_project ON typologies(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_taxonomy_typologie ON taxonomy_clusters(typologie_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_root_taxonomy ON root_labels(taxonomy_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_parent_root ON parent_labels(root_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_child_parent_label ON child_labels(parent_label_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_child_parent_child ON child_labels(parent_child_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_child_depth ON child_labels(depth)')

            self.connection.commit()
            logger.info("Tables créées avec succès")

        except Exception as e:
            logger.error(f"Erreur lors de la création des tables : {str(e)}")
            raise e
        
    def save_batch(self, project_name, batch_number, total_batches, batch_data):
        """Sauvegarde un batch de données"""
        try:
            cursor = self.connection.cursor()

            # Récupérer l'ID du projet
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()

            if not project_row:
                logger.error(f"Projet '{project_name}' non trouvé")
                return False

            project_id = project_row['id']

            # Sérialiser les données du batch
            data_json = json.dumps(batch_data, ensure_ascii=False)

            # Insérer ou mettre à jour le batch
            cursor.execute("""
                INSERT INTO batches (project_id, batch_number, total_batches, data, status)
                VALUES (?, ?, ?, ?, 'pending')
                ON CONFLICT(project_id, batch_number) 
                DO UPDATE SET 
                    data = excluded.data,
                    total_batches = excluded.total_batches,
                    status = 'pending',
                    created_at = CURRENT_TIMESTAMP
            """, (project_id, batch_number, total_batches, data_json))

            self.connection.commit()
            logger.info(f"Batch {batch_number}/{total_batches} sauvegardé pour '{project_name}'")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du batch: {str(e)}")
            return False
        
    def get_batch(self, project_name, batch_number):
        """Récupère un batch spécifique"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.* FROM batches b
                JOIN projects p ON b.project_id = p.id
                WHERE p.name = ? AND b.batch_number = ?
            """, (project_name, batch_number))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'batch_number': row['batch_number'],
                'total_batches': row['total_batches'],
                'status': row['status'],
                'data': json.loads(row['data']),
                'created_at': row['created_at'],
                'processed_at': row['processed_at']
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du batch: {str(e)}")
            return None
        
    def get_all_batches(self, project_name):
        """Récupère tous les batches d'un projet"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.* FROM batches b
                JOIN projects p ON b.project_id = p.id
                WHERE p.name = ?
                ORDER BY b.batch_number
            """, (project_name,))

            batches = []
            for row in cursor.fetchall():
                batches.append({
                    'id': row['id'],
                    'batch_number': row['batch_number'],
                    'total_batches': row['total_batches'],
                    'status': row['status'],
                    'data': json.loads(row['data']),
                    'created_at': row['created_at'],
                    'processed_at': row['processed_at']
                })

            return batches

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des batches: {str(e)}")
            return []

    def update_batch_status(self, project_name, batch_number, status):
        """Met à jour le statut d'un batch"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE batches 
                SET status = ?,
                    processed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE processed_at END
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
                AND batch_number = ?
            """, (status, status, project_name, batch_number))

            self.connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {str(e)}")
            return False
        
    def delete_batch(self, project_name, batch_number):
        """Supprime un batch spécifique"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                DELETE FROM batches 
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
                AND batch_number = ?
            """, (project_name, batch_number))

            self.connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du batch: {str(e)}")
            return False
        
    def delete_all_batches(self, project_name):
        """Supprime tous les batches d'un projet"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                DELETE FROM batches 
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
            """, (project_name,))
            
            self.connection.commit()
            logger.info(f"Tous les batches de '{project_name}' supprimés")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des batches: {str(e)}")
            return False

    def get_dataset_projet(self, project_name):
        """Récupère un projet complet avec toute sa hiérarchie"""
        try:
            if not self.connection:
                logger.error("Aucune connexion à la base de données")
                return None

            cursor = self.connection.cursor()
            
            # Récupérer le projet
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()

            if not project_row:
                return None

            project_id = project_row['id']
            
            # Construire la structure complète
            project_data = {
                'nom': project_row['name'],
                'description': project_row['description'] or '',
                'typologies': self._load_typologies(project_id)
            }

            return project_data

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du projet '{project_name}': {str(e)}")
            return None

    def _load_typologies(self, project_id):
        """Charge toutes les typologies d'un projet avec leur hiérarchie complète"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM typologies 
            WHERE project_id = ? 
            ORDER BY position, id
        """, (project_id,))
        
        typologies = []
        for row in cursor.fetchall():
            typologie = {
                'name': row['name'],
                'description': row['description'] or '',
                'taxonomy_clusters': self._load_taxonomy_clusters(row['id'])
            }
            typologies.append(typologie)
        
        return typologies

    def _load_taxonomy_clusters(self, typologie_id):
        """Charge tous les clusters de taxonomie d'une typologie"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM taxonomy_clusters 
            WHERE typologie_id = ? 
            ORDER BY position, id
        """, (typologie_id,))
        
        clusters = []
        for row in cursor.fetchall():
            cluster = {
                'name': row['name'],
                'description': row['description'] or '',
                'root_labels': self._load_root_labels(row['id'])
            }
            clusters.append(cluster)
        
        return clusters

    def _load_root_labels(self, taxonomy_id):
        """Charge tous les root labels d'un cluster de taxonomie"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM root_labels 
            WHERE taxonomy_id = ? 
            ORDER BY position, id
        """, (taxonomy_id,))
        
        roots = []
        for row in cursor.fetchall():
            root = {
                'name': row['name'],
                'description': row['description'] or '',
                'category': row['category'] or 'default',
                'parent_labels': self._load_parent_labels(row['id'])
            }
            roots.append(root)
        
        return roots

    def _load_parent_labels(self, root_id):
        """Charge tous les parent labels d'un root"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM parent_labels 
            WHERE root_id = ? 
            ORDER BY position, id
        """, (root_id,))
        
        parents = []
        for row in cursor.fetchall():
            parent = {
                'name': row['name'],
                'description': row['description'] or '',
                'category': row['category'] or 'default',
                'children': self._load_children_recursive(parent_label_id=row['id'])
            }
            parents.append(parent)
        
        return parents

    def _load_children_recursive(self, parent_label_id=None, parent_child_id=None, depth=0):
        """Charge récursivement tous les enfants"""
        cursor = self.connection.cursor()
        
        if parent_label_id:
            cursor.execute("""
                SELECT * FROM child_labels 
                WHERE parent_label_id = ? AND parent_child_id IS NULL
                ORDER BY position, id
            """, (parent_label_id,))
        elif parent_child_id:
            cursor.execute("""
                SELECT * FROM child_labels 
                WHERE parent_child_id = ?
                ORDER BY position, id
            """, (parent_child_id,))
        else:
            return []
        
        children = []
        for row in cursor.fetchall():
            child = {
                'name': row['name'],
                'description': row['description'] or '',
                'category': row['category'] or 'default',
                'children': self._load_children_recursive(parent_child_id=row['id'], depth=depth+1)
            }
            children.append(child)
        
        return children

    def save_dataset_projet(self, project_name, project_data):
        """Sauvegarde un projet complet avec toute sa hiérarchie"""
        try:
            if not self.connection:
                logger.error("Aucune connexion à la base de données")
                return False

            cursor = self.connection.cursor()
            
            # Vérifier si le projet existe
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            existing = cursor.fetchone()

            if existing:
                project_id = existing['id']
                # Mettre à jour le projet
                cursor.execute("""
                    UPDATE projects
                    SET description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (project_data.get('description', ''), project_id))
                
                # Supprimer l'ancienne hiérarchie pour la recréer
                cursor.execute("DELETE FROM typologies WHERE project_id = ?", (project_id,))
            else:
                # Créer nouveau projet
                cursor.execute("""
                    INSERT INTO projects (name, description)
                    VALUES (?, ?)
                """, (project_name, project_data.get('description', '')))
                project_id = cursor.lastrowid

            # Sauvegarder la hiérarchie complète
            self._save_typologies(cursor, project_id, project_data.get('typologies', []))

            self.connection.commit()
            logger.info(f"Projet '{project_name}' sauvegardé avec succès")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du projet '{project_name}': {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False

    def _save_typologies(self, cursor, project_id, typologies):
        """Sauvegarde toutes les typologies"""
        for position, typologie in enumerate(typologies):
            cursor.execute("""
                INSERT INTO typologies (project_id, name, description, position)
                VALUES (?, ?, ?, ?)
            """, (project_id, typologie['name'], typologie.get('description', ''), position))
            typologie_id = cursor.lastrowid
            
            # Sauvegarder les clusters de taxonomie
            taxonomy_clusters = typologie.get('taxonomy_clusters', [])
            self._save_taxonomy_clusters(cursor, typologie_id, taxonomy_clusters)

    def _save_taxonomy_clusters(self, cursor, typologie_id, clusters):
        """Sauvegarde tous les clusters de taxonomie"""
        for position, cluster in enumerate(clusters):
            cursor.execute("""
                INSERT INTO taxonomy_clusters (typologie_id, name, description, position)
                VALUES (?, ?, ?, ?)
            """, (typologie_id, cluster['name'], cluster.get('description', ''), position))
            taxonomy_id = cursor.lastrowid
            
            # Sauvegarder les root labels
            root_labels = cluster.get('root_labels', [])
            self._save_root_labels(cursor, taxonomy_id, root_labels)

    def _save_root_labels(self, cursor, taxonomy_id, roots):
        """Sauvegarde tous les root labels"""
        for position, root in enumerate(roots):
            cursor.execute("""
                INSERT INTO root_labels (taxonomy_id, name, description, category, position)
                VALUES (?, ?, ?, ?, ?)
            """, (taxonomy_id, root['name'], root.get('description', ''), 
                  root.get('category', 'default'), position))
            root_id = cursor.lastrowid
            
            # Sauvegarder les parent labels
            parent_labels = root.get('parent_labels', [])
            self._save_parent_labels(cursor, root_id, parent_labels)

    def _save_parent_labels(self, cursor, root_id, parents):
        """Sauvegarde tous les parent labels"""
        for position, parent in enumerate(parents):
            cursor.execute("""
                INSERT INTO parent_labels (root_id, name, description, category, position)
                VALUES (?, ?, ?, ?, ?)
            """, (root_id, parent['name'], parent.get('description', ''), 
                  parent.get('category', 'default'), position))
            parent_id = cursor.lastrowid
            
            # Sauvegarder les enfants récursivement
            children = parent.get('children', [])
            self._save_children_recursive(cursor, children, parent_label_id=parent_id, depth=0)

    def _save_children_recursive(self, cursor, children, parent_label_id=None, 
                                  parent_child_id=None, depth=0):
        """Sauvegarde récursivement tous les enfants"""
        for position, child in enumerate(children):
            cursor.execute("""
                INSERT INTO child_labels 
                (parent_label_id, parent_child_id, name, description, category, depth, position)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (parent_label_id, parent_child_id, child['name'], 
                  child.get('description', ''), child.get('category', 'default'), 
                  depth, position))
            child_id = cursor.lastrowid
            
            # Sauvegarder les sous-enfants
            sub_children = child.get('children', [])
            if sub_children:
                self._save_children_recursive(cursor, sub_children, 
                                             parent_child_id=child_id, depth=depth+1)

    def delete_dataset_projet(self, project_name):
        """Supprime un projet et toute sa hiérarchie (CASCADE)"""
        try:
            if not self.connection:
                logger.error("Aucune connexion à la base de données")
                return False

            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM projects WHERE name = ?", (project_name,))
            self.connection.commit()

            if cursor.rowcount > 0:
                logger.info(f"Projet '{project_name}' supprimé avec succès")
                return True
            else:
                logger.warning(f"Aucun projet trouvé avec le nom '{project_name}'")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du projet '{project_name}': {str(e)}")
            return False

    def get_all_projects(self):
        """Récupère tous les projets (sans hiérarchie complète)"""
        try:
            if not self.connection:
                logger.error("Aucune connexion à la base de données")
                return []

            cursor = self.connection.cursor()
            cursor.execute("SELECT name, description FROM projects ORDER BY name")
            rows = cursor.fetchall()

            projects = []
            for row in rows:
                projects.append({
                    'name': row['name'],
                    'description': row['description'] or ''
                })

            return projects

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des projets: {str(e)}")
            return []

    def get_all_platforms(self):
        """Récupère toutes les plateformes"""
        try:
            if not self.connection:
                logger.error("Aucune connexion à la base de données")
                return []

            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM platforms ORDER BY name")
            rows = cursor.fetchall()

            platforms = [row['name'] for row in rows]
            return platforms

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des plateformes: {str(e)}")
            return []

    def test_connection(self):
        """Teste la connexion à la base de données"""
        try:
            if not self.connection:
                raise Exception("Aucune connexion à la base de données")

            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True

        except Exception as e:
            logger.error(f"Erreur lors du test de connexion: {str(e)}")
            raise e

    def force_recreate_database(self):
        """Force la recréation de la base de données"""
        try:
            if self.connection:
                self.connection.close()

            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info(f"Fichier de base de données supprimé: {self.db_path}")

            self._init_connection()
            self._create_tables()
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la base de données: {str(e)}")
            return False

    def close(self):
        """Ferme la connexion à la base de données"""
        if self.connection:
            self.connection.close()
            logger.info("Connexion à la base de données fermée")