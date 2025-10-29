
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import uuid
from venv import logger


class ProjectStorageManager:
    def __init__(self, parent_widget, db_path: str, dgraph_connector):
        """
        Args:
            parent_widget: Instance de ProjectConfigWidget
            db_path: Chemin vers la base SQLite
            dgraph_connector: Instance de LirisDgraphConnector
        """
        self.parent = parent_widget
        self.db_path = db_path
        self.dgraph_connector = dgraph_connector

    def _init_sqlite_db(self):
        """Initialise ou met à jour la base SQLite avec schéma aligné à Dgraph."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA max_page_count = 2147483646")  # ~140 TB
            cursor.execute("PRAGMA page_size = 65536")  # 64KB par page (max)
            cursor.execute("PRAGMA cache_size = -2000000")  # 2GB cache
            cursor.execute("PRAGMA temp_store = MEMORY")  # Temp en RAM
            cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
            cursor.execute("PRAGMA synchronous = NORMAL")  # Performance

            # === 1️⃣ Vérifier si la table relations existe déjà ===
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='relations';
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                cursor.execute("PRAGMA table_info(relations);")
                existing_cols = [row[1] for row in cursor.fetchall()]

                # Si l'ancienne structure est détectée (pas de colonne 'uid' ou noms différents)
                if 'uid' not in existing_cols or 'relationType' not in existing_cols:
                    logger.warning("Structure obsolète détectée pour la table 'relations'. Reconstruction en cours...")

                    # Sauvegarde des anciennes données minimales (si possible)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS relations_backup AS
                        SELECT * FROM relations;
                    """)

                    # Supprimer l'ancienne table
                    cursor.execute("DROP TABLE relations;")

            # === 2️⃣ Création / recréation des tables ===

            # Table des Workspaces
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT UNIQUE,
                    ownerId TEXT,
                    description TEXT,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table ClusterManagement
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cluster_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    workspace_uid TEXT NOT NULL,
                    lastUpdated TIMESTAMP,
                    version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_uid) REFERENCES workspaces(uid)
                )
            """)

            # Table Clusters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_management_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    userId TEXT,
                    nodeType TEXT DEFAULT 'cluster',
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    is_file_cluster BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_management_uid) REFERENCES cluster_management(uid)
                )
            """)

            # Table Labels
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_uid TEXT NOT NULL,
                    parent_uid TEXT,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    level INTEGER,
                    path TEXT,
                    parentId TEXT,
                    nodeType TEXT DEFAULT 'label',
                    category TEXT,
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_uid) REFERENCES clusters(uid),
                    FOREIGN KEY (parent_uid) REFERENCES labels(uid)
                )
            """)

            # 🧩 Table Relations corrigée (structure alignée)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT,
                    relationType TEXT NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)

            # Table Functions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    label_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (label_uid) REFERENCES labels(uid)
                )
            """)

            # Table Imports
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)

            # === 3️⃣ Création d’index ===
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_cm ON clusters(cluster_management_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_cluster ON labels(cluster_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_parent ON labels(parent_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_uid)")

            conn.commit()   
            conn.close()

            logger.info(f"Base de données SQLite initialisée et synchronisée : {self.db_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation ou mise à jour SQLite : {e}")

    def _create_workspace_in_sqlite(self, project_data):
        """CRUD Create: Crée un nouveau workspace en évitant les doublons via uid unique."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid
            
            # Vérifier si existe déjà (bien que uid unique)
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if cursor.fetchone():
                logger.warning(f"Workspace {project_uid} existe déjà.")
                conn.close()
                return False
            
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace créé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du workspace SQLite : {e}")
            return False
        
    def _read_workspace_from_sqlite(self, workspace_uid):
        """CRUD Read: Lit un workspace spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM workspaces WHERE uid = ?", (workspace_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du workspace SQLite : {e}")
            return None

    def _update_workspace_in_sqlite(self, project_data):
        """CRUD Update: Met à jour un workspace existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid')
            if not project_uid:
                logger.error("UID manquant pour update.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {project_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE workspaces SET
                name = ?, description = ?, files = ?, fileContents = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                project_data.get('name', ''),
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat(),
                project_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace mis à jour dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du workspace SQLite : {e}")
            return False
        
    def _delete_workspace_in_sqlite(self, workspace_uid):
        """CRUD Delete: Supprime un workspace et ses dépendances en cascade."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (workspace_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {workspace_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade (ordre inverse des FK)
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid IN (
                        SELECT uid FROM clusters 
                        WHERE cluster_management_uid IN (
                            SELECT uid FROM cluster_management 
                            WHERE workspace_uid = ?
                        )
                    )
                )
            """, (workspace_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))  # Remplacer ... par la sous-requête ci-dessus
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))
            
            # Labels
            cursor.execute("""
                DELETE FROM labels 
                WHERE cluster_uid IN (
                    SELECT uid FROM clusters 
                    WHERE cluster_management_uid IN (
                        SELECT uid FROM cluster_management 
                        WHERE workspace_uid = ?
                    )
                )
            """, (workspace_uid,))
            
            # Clusters
            cursor.execute("""
                DELETE FROM clusters 
                WHERE cluster_management_uid IN (
                    SELECT uid FROM cluster_management 
                    WHERE workspace_uid = ?
                )
            """, (workspace_uid,))
            
            # Cluster Management
            cursor.execute("""
                DELETE FROM cluster_management 
                WHERE workspace_uid = ?
            """, (workspace_uid,))
            
            # Workspace
            cursor.execute("DELETE FROM workspaces WHERE uid = ?", (workspace_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace supprimé de SQLite : {workspace_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du workspace SQLite : {e}")
            return False

    def _create_cluster_in_sqlite(self, cluster_data, workspace_uid):
        """CRUD Create: Crée un cluster en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
            cluster_data['uid'] = cluster_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} existe déjà.")
                conn.close()
                return False
            
            # Assurer cluster_management existe
            cm_uid = f"cm_{workspace_uid}"
            cursor.execute("""
                INSERT OR IGNORE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (cm_uid, workspace_uid, datetime.now().isoformat(), '1.0'))
            
            cursor.execute("""
                INSERT INTO clusters 
                (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                 description, codeContent, files, fileContents, is_file_cluster, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cluster_uid,
                cm_uid,
                cluster_data.get('name', ''),
                cluster_data.get('uid', str(uuid.uuid4())),
                'user1',
                'cluster',
                cluster_data.get('description', ''),
                '',
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster créé dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création cluster SQLite : {e}")
            return False

    def _update_cluster_in_sqlite(self, cluster_data):
        """CRUD Update: Met à jour un cluster existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid')
            if not cluster_uid:
                logger.error("UID manquant pour update cluster.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE clusters SET
                name = ?, description = ?, files = ?, fileContents = ?, is_file_cluster = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                cluster_data.get('name', ''),
                cluster_data.get('description', ''),
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                cluster_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster mis à jour dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour cluster SQLite : {e}")
            return False
        
    def _delete_cluster_in_sqlite(self, cluster_uid):
        """CRUD Delete: Supprime un cluster et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Labels
            cursor.execute("DELETE FROM labels WHERE cluster_uid = ?", (cluster_uid,))
            
            # Cluster
            cursor.execute("DELETE FROM clusters WHERE uid = ?", (cluster_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster supprimé de SQLite : {cluster_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression cluster SQLite : {e}")
            return False
        
    def _create_label_in_sqlite(self, label_data, cluster_uid, parent_uid=None, level=0):
        """CRUD Create: Crée un label en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid', str(uuid.uuid4()))
            label_data['uid'] = label_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if cursor.fetchone():
                logger.warning(f"Label {label_uid} existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label_uid,
                cluster_uid,
                parent_uid,
                label_data.get('label', ''),
                label_data.get('id', label_uid),
                level,
                '',  # path
                parent_uid,  # parentId
                'label',
                json.dumps(label_data.get('category', [])),
                label_data.get('description', ''),
                '',  # codeContent
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label créé dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création label SQLite : {e}")
            return False
        
    def _read_label_from_sqlite(self, label_uid):
        """CRUD Read: Lit un label spécifique et ses enfants récursivement."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM labels WHERE uid = ?", (label_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['category'] = json.loads(data['category'])
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            data['children'] = []
            data['parents'] = [data['parent_uid']] if data['parent_uid'] else []
            
            # Charger enfants récursivement
            cursor.execute("SELECT uid FROM labels WHERE parent_uid = ?", (label_uid,))
            for child_row in cursor.fetchall():
                child_data = self._read_label_from_sqlite(child_row['uid'])
                if child_data:
                    data['children'].append(child_data)
            
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture label SQLite : {e}")
            return None

    def _update_label_in_sqlite(self, label_data):
        """CRUD Update: Met à jour un label existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid')
            if not label_uid:
                logger.error("UID manquant pour update label.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour update.")
                conn.close()
                return False
            
            parent_uid = label_data.get('parents', [None])[0] if label_data.get('parents') else None
            
            cursor.execute("""
                UPDATE labels SET
                name = ?, description = ?, category = ?, files = ?, fileContents = ?, parent_uid = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                label_data.get('label', ''),
                label_data.get('description', ''),
                json.dumps(label_data.get('category', [])),
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                parent_uid,
                datetime.now().isoformat(),
                label_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label mis à jour dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour label SQLite : {e}")
            return False
        
    def _delete_label_in_sqlite(self, label_uid):
        """CRUD Delete: Supprime un label et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("DELETE FROM functions WHERE label_uid = ?", (label_uid,))
            
            # Imports
            cursor.execute("DELETE FROM imports WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Relations
            cursor.execute("DELETE FROM relations WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Enfants récursifs
            cursor.execute("""
                WITH RECURSIVE label_tree AS (
                    SELECT uid FROM labels WHERE uid = ?
                    UNION ALL
                    SELECT l.uid FROM labels l
                    JOIN label_tree lt ON l.parent_uid = lt.uid
                )
                DELETE FROM labels WHERE uid IN (SELECT uid FROM label_tree)
            """, (label_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Label supprimé de SQLite : {label_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression label SQLite : {e}")
            return False

    def _create_relation_in_sqlite(self, source_uid, target_uid, relation_type='relation'):
        """CRUD Create: Crée une relation en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            rel_uid = f"rel_{str(uuid.uuid4())}"
            
            # Vérifier doublon (même source, target, type)
            cursor.execute("""
                SELECT uid FROM relations 
                WHERE source_uid = ? AND target_uid = ? AND relationType = ?
            """, (source_uid, target_uid, relation_type))
            if cursor.fetchone():
                logger.warning(f"Relation {source_uid} -> {target_uid} ({relation_type}) existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO relations 
                (uid, name, relationType, source_uid, target_uid, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rel_uid,
                f"{relation_type}_relation",
                relation_type,
                source_uid,
                target_uid,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation créée dans SQLite : {source_uid} -> {target_uid} ({relation_type})")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création relation SQLite : {e}")
            return False
        
    def _read_relation_from_sqlite(self, rel_uid):
        """CRUD Read: Lit une relation spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM relations WHERE uid = ?", (rel_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture relation SQLite : {e}")
            return None

    def _update_relation_in_sqlite(self, rel_uid, new_target_uid=None, new_relation_type=None):
        """CRUD Update: Met à jour une relation existante."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if not rel_uid:
                logger.error("UID manquant pour update relation.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour update.")
                conn.close()
                return False
            
            updates = []
            params = []
            if new_target_uid is not None:
                updates.append("target_uid = ?")
                params.append(new_target_uid)
            if new_relation_type is not None:
                updates.append("relationType = ?")
                params.append(new_relation_type)
            updates.append("updatedAt = ?")  # Toujours updater la date
            params.append(datetime.now().isoformat())
            params.append(rel_uid)
            
            if updates:
                query = f"UPDATE relations SET {', '.join(updates)} WHERE uid = ?"
                cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            logger.info(f"Relation mise à jour dans SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour relation SQLite : {e}")
            return False
        
    def _delete_relation_in_sqlite(self, rel_uid):
        """CRUD Delete: Supprime une relation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour suppression.")
                conn.close()
                return False
            
            cursor.execute("DELETE FROM relations WHERE uid = ?", (rel_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation supprimée de SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression relation SQLite : {e}")
            return False
        
    def _save_project_to_sqlite(self, project_data):
        """Sauvegarde le projet complet dans SQLite avec schéma aligné à Dgraph (Upsert)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid  # Ensure uid is set
            
            # Upsert Workspace
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT OR REPLACE INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            # Upsert ClusterManagement
            cluster_management_uid = f"cm_{project_uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (
                cluster_management_uid,
                project_uid,
                datetime.now().isoformat(),
                '1.0'
            ))
            
            # Upsert clusters et labels
            for cluster_data in project_data.get('turing_ontology', {}).get('clusters_detailed', []):
                cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
                cluster_data['uid'] = cluster_uid
                
                cursor.execute("""
                    INSERT OR REPLACE INTO clusters 
                    (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                     description, codeContent, files, fileContents, is_file_cluster, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster_uid,
                    cluster_management_uid,
                    cluster_data.get('name', ''),
                    cluster_data.get('uid', str(uuid.uuid4())),
                    'user1',
                    'cluster',
                    cluster_data.get('description', ''),
                    '',
                    json.dumps(cluster_data.get('files', [])),
                    json.dumps(cluster_data.get('file_contents', {})),
                    1 if cluster_data.get('is_file_cluster') else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                # Upsert labels hiérarchiquement
                for root_label in cluster_data.get('root_labels', []):
                    self._save_label_recursive_sqlite(
                        cursor, root_label, cluster_uid, None, 0
                    )
            
            # Upsert relations
            for source_uid, relations in self.parent.pending_relations.items():
                for rel in relations:
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    relation_type = rel.get('relation_type', 'relation')
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{relation_type}_relation",
                        relation_type,
                        source_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Projet sauvegardé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde SQLite : {e}")
            return False

    def _delete_project_from_sqlite(self, workspace_uid):
        """Supprime un projet entier de SQLite (CRUD Delete pour projet)."""
        return self._delete_workspace_in_sqlite(workspace_uid)

    def _save_label_recursive_sqlite(self, cursor, label_data, cluster_uid, parent_uid, level):
        """Sauvegarde récursivement les labels dans SQLite (Upsert)."""
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid
        
        cursor.execute("""
            INSERT OR REPLACE INTO labels 
            (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
             nodeType, category, description, codeContent, files, fileContents, 
             createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label_uid,
            cluster_uid,
            parent_uid,
            label_data.get('label', ''),
            label_data.get('id', label_uid),
            level,
            '',  # path
            parent_uid,  # parentId
            'label',
            json.dumps(label_data.get('category', [])),
            label_data.get('description', ''),
            '',  # codeContent
            json.dumps(label_data.get('files', [])),
            json.dumps(label_data.get('file_contents', {})),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        # Traiter les enfants récursivement
        for child in label_data.get('children', []):
            self._save_label_recursive_sqlite(cursor, child, cluster_uid, label_uid, level + 1)

    def _load_projects_from_sqlite(self):
        """Charge les projets depuis SQLite au démarrage, en évitant les doublons avec Dgraph."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM workspaces")
            workspaces = cursor.fetchall()

            loaded_count = 0
            skipped_count = 0

            for ws_row in workspaces:
                workspace_uid = ws_row['uid']
                project_name = ws_row['name']

                # ✅ ÉVITER DOUBLON : skip si déjà chargé (de Dgraph)
                if project_name in self.parent.project_profiles:
                    logger.debug(f"   ⏭️ Projet déjà chargé (Dgraph), skip SQLite: {project_name}")
                    skipped_count += 1
                    continue
                
                # ✅ CHARGER VIA CRUD READ
                ws_data = self._read_workspace_from_sqlite(workspace_uid)
                if not ws_data:
                    continue
                
                project_data = {
                    'uid': ws_data['uid'],
                    'name': ws_data['name'],
                    'description': ws_data['description'],
                    'files': ws_data['files'],
                    'file_contents': ws_data['fileContents'],
                    'turing_ontology': {'clusters_detailed': []},
                    'pending_relations': {}
                }

                # Charger clusters via Read
                cursor.execute("""
                    SELECT c.* FROM clusters c 
                    JOIN cluster_management cm ON c.cluster_management_uid = cm.uid 
                    WHERE cm.workspace_uid = ?
                """, (workspace_uid,))

                for cluster_row in cursor.fetchall():
                    cluster_uid = cluster_row['uid']
                    cluster_data = self._read_cluster_from_sqlite(cluster_uid)
                    if not cluster_data:
                        continue
                    cluster_data['root_labels'] = []

                    # Charger labels racines
                    cursor.execute("""
                        SELECT * FROM labels 
                        WHERE cluster_uid = ? AND parent_uid IS NULL
                    """, (cluster_uid,))

                    for label_row in cursor.fetchall():
                        root_label = self._read_label_from_sqlite(label_row['uid'])
                        if root_label:
                            cluster_data['root_labels'].append(root_label)

                    project_data['turing_ontology']['clusters_detailed'].append(cluster_data)

                # Charger relations
                cursor.execute("""
                    SELECT * FROM relations WHERE source_uid IN (
                        SELECT uid FROM labels WHERE cluster_uid IN (
                            SELECT uid FROM clusters WHERE cluster_management_uid IN (
                                SELECT uid FROM cluster_management WHERE workspace_uid = ?
                            )
                        )
                    )
                """, (workspace_uid,))

                relations_by_source = {}
                for rel_row in cursor.fetchall():
                    source_uid = rel_row['source_uid']
                    if source_uid not in relations_by_source:
                        relations_by_source[source_uid] = []
                    relations_by_source[source_uid].append({
                        'target_uid': rel_row['target_uid'],
                        'relation_type': rel_row['relationType']
                    })

                project_data['pending_relations'] = relations_by_source

                # ✅ STOCKER
                self.parent.project_profiles[project_name] = project_data
                loaded_count += 1
                logger.debug(f"   ✅ Chargé depuis SQLite: {project_name}")

            conn.close()
            logger.info(f"✅ Chargé depuis SQLite: {loaded_count} projet(s) (ignoré {skipped_count} doublon(s))")

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement SQLite : {e}")
            import traceback
            traceback.print_exc()

    def _read_cluster_from_sqlite(self, cluster_uid):
        """CRUD Read: Lit un cluster spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM clusters WHERE uid = ?", (cluster_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None

            data = dict(row)
            data['files'] = json.loads(data['files'])
            data['file_contents'] = json.loads(data['fileContents'])
            data['root_labels'] = []  # Sera rempli par l'appelant

            conn.close()
            return data

        except Exception as e:
            logger.error(f"Erreur lecture cluster SQLite : {e}")
            return None
        
    def _load_label_from_sqlite(self, cursor, label_row):
        """Charge un label et ses enfants depuis SQLite."""
        label_uid = label_row['uid']
        label_data = {
            'uid': label_uid,
            'label': label_row['name'],
            'id': label_row['id_field'],
            'description': label_row['description'],
            'category': json.loads(label_row['category']),
            'files': json.loads(label_row['files']),
            'file_contents': json.loads(label_row['fileContents']),
            'parents': [label_row['parent_uid']] if label_row['parent_uid'] else [],
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': []
        }
        
        # Charger les enfants
        cursor.execute("""
            SELECT * FROM labels WHERE parent_uid = ?
        """, (label_uid,))
        
        for child_row in cursor.fetchall():
            child_label = self._load_label_from_sqlite(cursor, child_row)
            label_data['children'].append(child_label)
        
        return label_data
    
    def _save_project_to_sqlite_after_scan(self, project_data):
        """
        MODIFIÉ: Sauvegarde complète du projet avec les classes/fonctions/variables
        en tant que nœuds enfants dans SQLite (via CRUD).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid

            # 1. Upsert Workspace
            logger.info(f"  📁 Sauvegarde workspace: {project_data.get('name')}")
            cursor.execute("""
                INSERT OR REPLACE INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                project_data.get('name', str(uuid.uuid4())),
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))

            # 2. Upsert ClusterManagement
            cluster_management_uid = f"cm_{project_uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (
                cluster_management_uid,
                project_uid,
                datetime.now().isoformat(),
                '1.0'
            ))

            # 3. Upsert Clusters et Labels
            ontology = project_data.get('turing_ontology', {})
            clusters = ontology.get('clusters_detailed', [])

            for cluster_data in clusters:
                cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
                cluster_data['uid'] = cluster_uid

                logger.info(f"    📦 Sauvegarde cluster: {cluster_data.get('name')}")

                # Upsert cluster
                cursor.execute("""
                    INSERT OR REPLACE INTO clusters 
                    (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                     description, codeContent, files, fileContents, is_file_cluster, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster_uid,
                    cluster_management_uid,
                    cluster_data.get('name', ''),
                    cluster_data.get('uid', str(uuid.uuid4())),
                    'user1',
                    'cluster',
                    cluster_data.get('description', ''),
                    '',
                    json.dumps(cluster_data.get('files', [])),
                    json.dumps(cluster_data.get('file_contents', {})),
                    1 if cluster_data.get('is_file_cluster') else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Upsert labels et leurs enfants (classes/fonctions/variables)
                root_labels = cluster_data.get('root_labels', [])
                for root_label in root_labels:
                    self._save_label_and_children_recursive(
                        cursor, root_label, cluster_uid, None, 0
                    )

            # 4. Upsert Relations
            logger.info(f"  🔗 Sauvegarde relations")
            for source_uid, relations in self.pending_relations.items():
                for rel in relations:
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        source_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))

            conn.commit()
            conn.close()

            logger.info("✅ Sauvegarde SQLite complète")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde SQLite: {e}")
            return False
