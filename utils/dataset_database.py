import json
import logging
import os
import sqlite3
from datetime import datetime
import sys
import traceback

logger = logging.getLogger(__name__)


class DatasetDatabase:
    """
    Gestionnaire de base de données pour les projets de datasets.
    Gère la connexion SQLite et les opérations CRUD sur les projets avec structure hiérarchique complète.
    
    Structure hiérarchique supportée:
    Project → Typologies → Taxonomy Clusters → Root Labels → Parent Labels → Children (infini)
    """

    def __init__(self, db_path="data/liris.db"):
        """Initialise la base de données avec gestion robuste des chemins"""

        # ✅ CORRECTION 1: Utiliser un chemin utilisateur sûr
        self.db_path = self._get_safe_database_path(db_path)

        logger.info("=" * 80)
        logger.info("🗄️  INITIALISATION BASE DE DONNÉES")
        logger.info("=" * 80)
        logger.info(f"  Chemin: {self.db_path}")
        logger.info(f"  Existe: {os.path.exists(self.db_path)}")

        # ✅ CORRECTION 2: Vérifier les permissions AVANT de continuer
        if not self._check_write_permissions():
            raise PermissionError(
                f"Impossible d'écrire dans le dossier: {os.path.dirname(self.db_path)}\n"
                f"Vérifiez les permissions ou déplacez l'application ailleurs."
            )

        self.connection = None

        try:
            self._init_connection()
            self._validate_and_fix_schema()
            self._create_tables()
            logger.info("✅ Base de données initialisée")
        except Exception as e:
            logger.error(f"❌ Erreur critique lors de l'initialisation: {e}")
            logger.error(traceback.format_exc())
            raise

        logger.info("=" * 80)

    def _get_safe_database_path(self, db_path):
        """
        ✅ CORRECTION: Retourne un chemin sûr pour la base de données
        Utilise le dossier utilisateur si l'application est en lecture seule
        """
        if getattr(sys, 'frozen', False):
            # Application compilée
            exe_dir = os.path.dirname(sys.executable)
            
            # Tester si le dossier exe est accessible en écriture
            test_file = os.path.join(exe_dir, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                # Le dossier est accessible, utiliser exe_dir
                full_path = os.path.join(exe_dir, db_path)
            except (PermissionError, OSError):
                # Dossier en lecture seule, utiliser le dossier utilisateur
                app_data = os.path.join(
                    os.path.expanduser('~'),
                    '.liris'  # Dossier caché dans le home de l'utilisateur
                )
                full_path = os.path.join(app_data, db_path)
                logger.warning(f"⚠️ Dossier exe en lecture seule, utilisation de: {app_data}")
        else:
            # Mode développement
            current_file = os.path.abspath(__file__)
            utils_dir = os.path.dirname(current_file)
            base_path = os.path.dirname(utils_dir)
            full_path = os.path.join(base_path, db_path)

        # Créer le répertoire avec gestion d'erreur
        db_dir = os.path.dirname(full_path)
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"📁 Dossier créé/vérifié: {db_dir}")
        except Exception as e:
            logger.error(f"❌ Impossible de créer le dossier {db_dir}: {e}")
            raise

        return full_path
    
    def _check_write_permissions(self):
        """
        ✅ CORRECTION: Vérifie que le dossier est accessible en écriture
        """
        db_dir = os.path.dirname(self.db_path)
        
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"❌ Impossible de créer le dossier: {e}")
                return False

        # Test d'écriture
        test_file = os.path.join(db_dir, '.permission_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info("✅ Permissions d'écriture vérifiées")
            return True
        except Exception as e:
            logger.error(f"❌ Pas de permission d'écriture: {e}")
            return False

    def _validate_schema(self):
        """Valide que le schéma de la base est correct"""
        try:
            cursor = self.connection.cursor()

            # Vérifier la structure de root_labels
            cursor.execute("PRAGMA table_info(root_labels)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = {'id', 'taxonomy_id', 'name', 'description', 'category', 'position'}

            if not required_columns.issubset(columns):
                logger.warning(f"⚠️ Schéma invalide détecté pour root_labels")
                logger.warning(f"   Colonnes présentes: {columns}")
                logger.warning(f"   Colonnes requises: {required_columns}")
                logger.warning(f"   Colonnes manquantes: {required_columns - columns}")
                return False

            # Vérifier parent_labels
            cursor.execute("PRAGMA table_info(parent_labels)")
            columns = {row[1] for row in cursor.fetchall()}
            required_columns = {'id', 'root_id', 'name', 'description', 'category', 'position'}

            if not required_columns.issubset(columns):
                logger.warning(f"⚠️ Schéma invalide pour parent_labels")
                return False

            # Vérifier child_labels
            cursor.execute("PRAGMA table_info(child_labels)")
            columns = {row[1] for row in cursor.fetchall()}
            required_columns = {'id', 'parent_label_id', 'parent_child_id', 'name', 'description', 'category', 'depth', 'position'}

            if not required_columns.issubset(columns):
                logger.warning(f"⚠️ Schéma invalide pour child_labels")
                return False

            logger.info("✅ Schéma de base de données valide")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la validation du schéma: {e}")
            return False

    def _init_connection(self):
        """Initialise la connexion SQLite avec gestion d'erreur améliorée"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # ✅ CORRECTION: Vérifier que la connexion fonctionne
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            logger.info("✅ Connexion établie et testée")
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Erreur SQLite: {e}")
            logger.error(f"   Chemin DB: {self.db_path}")
            logger.error(f"   DB existe: {os.path.exists(self.db_path)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            raise

    def _validate_and_fix_schema(self):
        """
        ✅ CORRECTION: Validation plus tolérante avec backup avant suppression
        """
        try:
            cursor = self.connection.cursor()

            # Vérifier si des tables existent
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}

            if not existing_tables:
                logger.info("📄 Nouvelle base de données")
                return

            logger.info(f"📋 Tables existantes: {existing_tables}")

            # Vérifier root_labels si elle existe
            if 'root_labels' in existing_tables:
                cursor.execute("PRAGMA table_info(root_labels)")
                columns = {row[1] for row in cursor.fetchall()}

                logger.info(f"🔍 Colonnes de root_labels: {columns}")

                # Vérifier si taxonomy_id existe
                if 'taxonomy_id' not in columns:
                    logger.error("❌ CORRUPTION DÉTECTÉE: taxonomy_id manquant!")
                    
                    # ✅ CORRECTION: Créer un backup avant de supprimer
                    self._create_backup()
                    
                    logger.warning("🗑️  Suppression des tables corrompues...")
                    self._drop_all_tables()
                    return

            logger.info("✅ Schéma valide")

        except Exception as e:
            logger.error(f"❌ Erreur validation: {e}")
            logger.error(traceback.format_exc())
            # ✅ CORRECTION: Ne pas supprimer automatiquement en cas d'erreur inconnue
            logger.warning("⚠️  Validation échouée mais conservation de la base")

    def _create_backup(self):
        """
        ✅ NOUVELLE FONCTION: Crée un backup de la base avant suppression
        """
        if not os.path.exists(self.db_path):
            return
        
        backup_path = f"{self.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"💾 Backup créé: {backup_path}")
        except Exception as e:
            logger.warning(f"⚠️  Impossible de créer un backup: {e}")

    def _drop_all_tables(self):
        """Supprime toutes les tables"""
        try:
            cursor = self.connection.cursor()
            
            tables = [
                'child_labels',
                'parent_labels',
                'root_labels',
                'taxonomy_clusters',
                'typologies',
                'batches',
                'projects',
                'platforms'
            ]
            
            for table in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                except:
                    pass
                
            self.connection.commit()
            logger.info("✅ Toutes les tables supprimées")
            
        except Exception as e:
            logger.error(f"Erreur suppression: {e}")

    def _drop_all_tables(self):
        """Supprime toutes les tables avec logging détaillé"""
        try:
            cursor = self.connection.cursor()
            
            tables = [
                'child_labels',
                'parent_labels',
                'root_labels',
                'taxonomy_clusters',
                'typologies',
                'batches',
                'projects',
                'platforms'
            ]
            
            dropped_count = 0
            for table in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    dropped_count += 1
                    logger.info(f"  ✅ {table} supprimée")
                except Exception as e:
                    logger.warning(f"  ⚠️  {table}: {e}")
                
            self.connection.commit()
            logger.info(f"✅ {dropped_count} table(s) supprimée(s)")
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression: {e}")

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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dataset_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    project_name TEXT NOT NULL,
                    batch_number INTEGER,
                    batch_name TEXT,
                    batch_family TEXT,

                    -- Métadonnées de génération
                    num_batches_processed INTEGER DEFAULT 1,
                    total_samples INTEGER NOT NULL,
                    samples_per_batch INTEGER,
                    total_combinations INTEGER,

                    -- Configuration
                    output_format TEXT DEFAULT 'JSON',
                    master_typologie_name TEXT,

                    -- Prompts utilisés
                    global_context TEXT,
                    local_prompt TEXT,

                    -- Informations temporelles
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_seconds INTEGER,

                    -- Statut et résultats
                    status TEXT DEFAULT 'pending',
                    output_file_path TEXT,
                    error_message TEXT,

                    -- Métadonnées additionnelles (JSON)
                    metadata TEXT,

                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')
            
            # Index pour optimiser les requêtes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batches_project ON batches(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_generations_project ON dataset_generations(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_generations_status ON dataset_generations(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_generations_date ON dataset_generations(started_at)')

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
        
    def save_generation_start(self, generation_config):
        """
        ✅ CORRIGÉ: Enregistre le début d'une génération avec validation
        """
        try:
            cursor = self.connection.cursor()

            # ✅ Extraire et valider les données
            metadata = generation_config.get('metadata', {})
            prompts = generation_config.get('prompts', {})
            master = generation_config.get('master_typologie', {})

            # Récupérer l'ID du projet
            project_name = metadata.get('project_name')

            if not project_name:
                logger.error("❌ Nom de projet manquant dans la configuration")
                return None

            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            project_row = cursor.fetchone()

            if not project_row:
                logger.error(f"❌ Projet '{project_name}' non trouvé")
                return None

            project_id = project_row['id']

            # ✅ Sérialiser les métadonnées de manière sûre
            try:
                metadata_json = json.dumps(metadata, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"⚠️  Erreur sérialisation métadonnées: {e}, utilisation de {{}}")
                metadata_json = '{}'

            # Insérer la génération
            cursor.execute("""
                INSERT INTO dataset_generations (
                    project_id, project_name, batch_number, batch_name, batch_family,
                    num_batches_processed, total_samples, samples_per_batch, total_combinations,
                    output_format, master_typologie_name,
                    global_context, local_prompt,
                    status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                project_name,
                metadata.get('batch_number'),
                metadata.get('batch_name'),
                metadata.get('batch_family'),
                metadata.get('num_batches_to_process', 1),
                metadata.get('total_samples_all_batches', 0),
                metadata.get('total_samples_per_batch', 0),
                len(generation_config.get('combinations', [])),
                metadata.get('output_format', 'JSON'),
                master.get('name'),
                prompts.get('global_context'),
                prompts.get('local_prompt'),
                'running',
                metadata_json
            ))

            self.connection.commit()
            generation_id = cursor.lastrowid

            logger.info(f"✅ Génération #{generation_id} enregistrée pour '{project_name}'")
            logger.info(f"   • Batch: {metadata.get('batch_number')}")
            logger.info(f"   • Samples: {metadata.get('total_samples_all_batches', 0)}")
            logger.info(f"   • Combinaisons: {len(generation_config.get('combinations', []))}")

            return generation_id

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'enregistrement du démarrage: {str(e)}")
            logger.error(traceback.format_exc())
            return None
        
    def verify_database_integrity(self):
        """
        ✅ NOUVEAU: Vérifie l'intégrité de la base de données
        Retourne un rapport de diagnostic
        """
        report = {
            'status': 'ok',
            'issues': [],
            'statistics': {}
        }

        try:
            cursor = self.connection.cursor()

            # 1. Vérifier le nombre de générations
            cursor.execute("SELECT COUNT(*) as count FROM dataset_generations")
            total = cursor.fetchone()['count']
            report['statistics']['total_generations'] = total

            # 2. Vérifier les projets orphelins
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM dataset_generations 
                WHERE project_id NOT IN (SELECT id FROM projects)
            """)
            orphans = cursor.fetchone()['count']
            if orphans > 0:
                report['issues'].append(f"{orphans} génération(s) avec projet inexistant")
                report['status'] = 'warning'

            # 3. Vérifier les métadonnées invalides
            cursor.execute("SELECT id, metadata FROM dataset_generations")
            invalid_metadata = 0
            for row in cursor.fetchall():
                if row['metadata']:
                    try:
                        json.loads(row['metadata'])
                    except json.JSONDecodeError:
                        invalid_metadata += 1

            if invalid_metadata > 0:
                report['issues'].append(f"{invalid_metadata} métadonnées JSON invalides")
                report['status'] = 'warning'

            report['statistics']['invalid_metadata'] = invalid_metadata

            # 4. Statistiques par statut
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM dataset_generations 
                GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            report['statistics']['by_status'] = status_counts

            # 5. Vérifier les champs NULL importants
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM dataset_generations 
                WHERE project_name IS NULL OR project_name = ''
            """)
            null_projects = cursor.fetchone()['count']
            if null_projects > 0:
                report['issues'].append(f"{null_projects} génération(s) sans nom de projet")
                report['status'] = 'error'

            logger.info("\n" + "="*80)
            logger.info("🔍 DIAGNOSTIC BASE DE DONNÉES")
            logger.info("="*80)
            logger.info(f"Statut: {report['status'].upper()}")
            logger.info(f"\n📊 Statistiques:")
            logger.info(f"  • Total générations: {total}")
            logger.info(f"  • Métadonnées invalides: {invalid_metadata}")
            logger.info(f"  • Projets orphelins: {orphans}")
            logger.info(f"  • Projets NULL: {null_projects}")

            if status_counts:
                logger.info(f"\n📈 Par statut:")
                for status, count in status_counts.items():
                    logger.info(f"  • {status}: {count}")

            if report['issues']:
                logger.warning(f"\n⚠️  Problèmes détectés:")
                for issue in report['issues']:
                    logger.warning(f"  • {issue}")
            else:
                logger.info("\n✅ Aucun problème détecté")

            logger.info("="*80 + "\n")

            return report

        except Exception as e:
            logger.error(f"❌ Erreur diagnostic: {e}")
            logger.error(traceback.format_exc())
            report['status'] = 'error'
            report['issues'].append(f"Erreur diagnostic: {str(e)}")
            return report
        
    def fix_orphaned_generations(self, dry_run=True):
        """
        ✅ NOUVEAU: Corrige les générations orphelines
        Si dry_run=True, simule seulement les actions
        """
        try:
            cursor = self.connection.cursor()
            
            # Trouver les générations orphelines
            cursor.execute("""
                SELECT id, project_name
                FROM dataset_generations 
                WHERE project_id NOT IN (SELECT id FROM projects)
            """)
            
            orphans = cursor.fetchall()
            
            if not orphans:
                logger.info("✅ Aucune génération orpheline")
                return True
            
            logger.info(f"⚠️  {len(orphans)} génération(s) orpheline(s) trouvée(s)")
            
            for row in orphans:
                gen_id = row['id']
                project_name = row['project_name']
                
                if not project_name:
                    logger.warning(f"  • Génération #{gen_id}: nom de projet NULL, impossible à corriger")
                    continue
                
                # Vérifier si le projet existe
                cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
                project = cursor.fetchone()
                
                if project:
                    project_id = project['id']
                    logger.info(f"  • Génération #{gen_id}: lié au projet '{project_name}' (ID {project_id})")
                    
                    if not dry_run:
                        cursor.execute("""
                            UPDATE dataset_generations 
                            SET project_id = ?
                            WHERE id = ?
                        """, (project_id, gen_id))
                else:
                    logger.info(f"  • Génération #{gen_id}: projet '{project_name}' inexistant, création...")
                    
                    if not dry_run:
                        cursor.execute("""
                            INSERT INTO projects (name, description)
                            VALUES (?, ?)
                        """, (project_name, f"Projet recréé automatiquement"))
                        
                        project_id = cursor.lastrowid
                        
                        cursor.execute("""
                            UPDATE dataset_generations 
                            SET project_id = ?
                            WHERE id = ?
                        """, (project_id, gen_id))
            
            if not dry_run:
                self.connection.commit()
                logger.info(f"✅ {len(orphans)} génération(s) corrigée(s)")
            else:
                logger.info("ℹ️  Mode simulation (dry_run), aucune modification effectuée")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur correction: {e}")
            logger.error(traceback.format_exc())
            if not dry_run:
                self.connection.rollback()
            return False
            
    def update_generation_completion(self, generation_id, output_file_path=None, 
                                 duration_seconds=None, error_message=None):
        """
        Met à jour une génération terminée (succès ou échec)
        """
        try:
            cursor = self.connection.cursor()

            status = 'completed' if error_message is None else 'failed'

            cursor.execute("""
                UPDATE dataset_generations 
                SET status = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = ?,
                    output_file_path = ?,
                    error_message = ?
                WHERE id = ?
            """, (status, duration_seconds, output_file_path, error_message, generation_id))

            self.connection.commit()

            logger.info(f"✅ Génération #{generation_id} mise à jour: {status}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour: {str(e)}")
            return False
        
    def get_all_generations(self, project_name=None, limit=100):
        """
        ✅ CORRIGÉ: Récupère toutes les générations avec validation robuste
        """
        try:
            cursor = self.connection.cursor()

            if project_name:
                cursor.execute("""
                    SELECT * FROM dataset_generations
                    WHERE project_name = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (project_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM dataset_generations
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (limit,))

            generations = []
            for row in cursor.fetchall():
                try:
                    # ✅ VALIDATION: Vérifier les champs essentiels
                    if not row['id'] or not row['project_name']:
                        logger.warning(f"⚠️  Génération #{row.get('id', '?')} incomplète, ignorée")
                        continue
                    
                    # ✅ Parser les métadonnées de manière sécurisée
                    metadata_value = row['metadata']
                    metadata = {}

                    if metadata_value:
                        if isinstance(metadata_value, str):
                            try:
                                metadata = json.loads(metadata_value)
                            except json.JSONDecodeError as e:
                                logger.warning(f"⚠️  Métadonnées JSON invalides pour génération #{row['id']}: {e}")
                                metadata = {}
                        elif isinstance(metadata_value, dict):
                            metadata = metadata_value

                    # Construire l'objet génération
                    generation = {
                        'id': row['id'],
                        'project_name': row['project_name'],
                        'batch_number': row['batch_number'],
                        'batch_name': row['batch_name'],
                        'batch_family': row['batch_family'],
                        'num_batches_processed': row['num_batches_processed'],
                        'total_samples': row['total_samples'] or 0,
                        'samples_per_batch': row['samples_per_batch'],
                        'total_combinations': row['total_combinations'] or 0,
                        'output_format': row['output_format'] or 'JSON',
                        'master_typologie_name': row['master_typologie_name'],
                        'started_at': row['started_at'],
                        'completed_at': row['completed_at'],
                        'duration_seconds': row['duration_seconds'],
                        'status': row['status'] or 'unknown',
                        'output_file_path': row['output_file_path'],
                        'error_message': row['error_message'],
                        'metadata': metadata
                    }

                    generations.append(generation)

                except Exception as row_error:
                    logger.error(f"❌ Erreur traitement ligne DB génération #{row.get('id', '?')}: {row_error}")
                    continue

            logger.info(f"✅ {len(generations)} génération(s) récupérée(s) depuis la DB")
            return generations

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des générations: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        
    def get_generation_by_id(self, generation_id):
        """Récupère une génération spécifique par son ID"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM dataset_generations WHERE id = ?", (generation_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'id': row['id'],
                'project_name': row['project_name'],
                'batch_number': row['batch_number'],
                'batch_name': row['batch_name'],
                'batch_family': row['batch_family'],
                'num_batches_processed': row['num_batches_processed'],
                'total_samples': row['total_samples'],
                'samples_per_batch': row['samples_per_batch'],
                'total_combinations': row['total_combinations'],
                'output_format': row['output_format'],
                'master_typologie_name': row['master_typologie_name'],
                'global_context': row['global_context'],
                'local_prompt': row['local_prompt'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'duration_seconds': row['duration_seconds'],
                'status': row['status'],
                'output_file_path': row['output_file_path'],
                'error_message': row['error_message'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else {}
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération: {str(e)}")
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
        
    def update_generation_output_path(self, generation_id, output_file_path):
        """
        Met à jour uniquement le chemin du fichier de sortie
        Utilisé après l'export pour enregistrer où le fichier a été sauvegardé
        """
        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                UPDATE dataset_generations 
                SET output_file_path = ?
                WHERE id = ?
            """, (output_file_path, generation_id))

            self.connection.commit()

            logger.info(f"✅ Chemin d'export mis à jour pour génération #{generation_id}: {output_file_path}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du chemin: {str(e)}")
            return False

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
        """Supprime tous les batches d'un projet (définitif et irréversible)"""
        try:
            cursor = self.connection.cursor()
            # Compter d'abord pour logging
            cursor.execute("""
                SELECT COUNT(*) as count FROM batches 
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
            """, (project_name,))
            count = cursor.fetchone()['count']
            
            cursor.execute("""
                DELETE FROM batches 
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
            """, (project_name,))
            
            self.connection.commit()
            logger.info(f"{count} batches supprimés définitivement pour '{project_name}' (irréversible)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression définitive des batches: {str(e)}")
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
        """
        ✅ CORRECTION: Sauvegarde avec meilleure gestion d'erreur
        """
        try:
            if not self.connection:
                error_msg = "❌ DATABASE: Aucune connexion à la base de données"
                logger.error(error_msg)
                raise ConnectionError(error_msg)
    
            logger.info("╔" + "═" * 78 + "╗")
            logger.info("║ DATABASE: save_dataset_projet()                                             ║")
            logger.info("╠" + "═" * 78 + "╣")
            logger.info(f"║ Projet: {project_name:<66} ║")
            logger.info("╚" + "═" * 78 + "╝")
    
            cursor = self.connection.cursor()
            
            # Vérifier si le projet existe
            logger.info(f"🔍 DATABASE: Vérification de l'existence du projet '{project_name}'")
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            existing = cursor.fetchone()
    
            if existing:
                project_id = existing['id']
                logger.info(f"🔄 DATABASE: Projet existant trouvé (ID: {project_id})")
                
                cursor.execute("""
                    UPDATE projects
                    SET description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (project_data.get('description', ''), project_id))
                logger.info(f"✅ DATABASE: Projet mis à jour")
                
                logger.info(f"🗑️  DATABASE: Suppression de l'ancienne hiérarchie...")
                cursor.execute("DELETE FROM typologies WHERE project_id = ?", (project_id,))
                deleted_count = cursor.rowcount
                logger.info(f"✅ DATABASE: {deleted_count} typologie(s) supprimée(s) (CASCADE)")
            else:
                logger.info(f"🆕 DATABASE: Création d'un nouveau projet")
                cursor.execute("""
                    INSERT INTO projects (name, description)
                    VALUES (?, ?)
                """, (project_name, project_data.get('description', '')))
                project_id = cursor.lastrowid
                logger.info(f"✅ DATABASE: Nouveau projet créé (ID: {project_id})")
    
            # Sauvegarder la hiérarchie complète
            typologies = project_data.get('typologies', [])
            logger.info(f"\n📊 DATABASE: Sauvegarde de {len(typologies)} typologie(s)")
            
            self._save_typologies(cursor, project_id, typologies)
    
            # ✅ CORRECTION: Vérifier avant de commiter
            logger.info("\n🔍 DATABASE: Vérification pré-commit")
            cursor.execute("SELECT COUNT(*) as count FROM typologies WHERE project_id = ?", (project_id,))
            count_before_commit = cursor.fetchone()['count']
            logger.info(f"  Typologies à commiter: {count_before_commit}")
    
            self.connection.commit()
            logger.info("\n✅ DATABASE: Transaction COMMIT réussie")
            
            # Vérification post-sauvegarde
            logger.info("\n🔍 DATABASE: Vérification post-sauvegarde")
            self._verify_saved_data(cursor, project_id, project_name)
            
            logger.info("\n╔" + "═" * 78 + "╗")
            logger.info(f"║ ✅ SAUVEGARDE RÉUSSIE: {project_name:<58} ║")
            logger.info("╚" + "═" * 78 + "╝\n")
            
            return True
    
        except sqlite3.Error as e:
            error_msg = f"❌ Erreur SQLite: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            if self.connection:
                self.connection.rollback()
                logger.warning("⚠️  DATABASE: Transaction ROLLBACK effectué")
            
            # ✅ CORRECTION: Remonter l'exception pour que l'UI puisse l'afficher
            raise RuntimeError(f"Erreur de sauvegarde: {e}")
            
        except Exception as e:
            logger.error("\n╔" + "═" * 78 + "╗")
            logger.error(f"║ ❌ ERREUR DATABASE: {str(e):<61} ║")
            logger.error("╚" + "═" * 78 + "╝")
            logger.error(f"\n🔥 Exception complète:\n{traceback.format_exc()}")
            
            if self.connection:
                self.connection.rollback()
                logger.warning("⚠️  DATABASE: Transaction ROLLBACK effectué")
            
            raise
    
        except Exception as e:
            logger.error("\n╔" + "═" * 78 + "╗")
            logger.error(f"║ ❌ ERREUR DATABASE: {str(e):<61} ║")
            logger.error("╚" + "═" * 78 + "╝")
            logger.error(f"\n🔥 Exception complète:\n{traceback.format_exc()}")
            
            if self.connection:
                self.connection.rollback()
                logger.warning("⚠️  DATABASE: Transaction ROLLBACK effectué")
            return False

    def _save_typologies(self, cursor, project_id, typologies):
        """Sauvegarde toutes les typologies avec logs détaillés"""
        logger.info(f"\n  ┌─ Sauvegarde des typologies")

        for position, typologie in enumerate(typologies):
            typ_name = typologie['name']
            typ_desc = typologie.get('description', '')

            logger.info(f"  │")
            logger.info(f"  ├─ [{position+1}/{len(typologies)}] Typologie: '{typ_name}'")

            cursor.execute("""
                INSERT INTO typologies (project_id, name, description, position)
                VALUES (?, ?, ?, ?)
            """, (project_id, typ_name, typ_desc, position))
            typologie_id = cursor.lastrowid

            logger.info(f"  │    ✅ Inséré (ID: {typologie_id}, pos: {position})")

            # Sauvegarder les clusters de taxonomie
            taxonomy_clusters = typologie.get('taxonomy_clusters', [])
            logger.info(f"  │    📊 {len(taxonomy_clusters)} cluster(s) de taxonomie")

            self._save_taxonomy_clusters(cursor, typologie_id, taxonomy_clusters, position+1, len(typologies))

        logger.info(f"  └─ ✅ Toutes les typologies sauvegardées\n")

    def _save_taxonomy_clusters(self, cursor, typologie_id, clusters, typ_num, typ_total):
        """Sauvegarde tous les clusters de taxonomie avec logs détaillés"""
        for position, cluster in enumerate(clusters):
            cluster_name = cluster['name']
            cluster_desc = cluster.get('description', '')

            logger.info(f"  │    │")
            logger.info(f"  │    ├─ [{position+1}/{len(clusters)}] Cluster: '{cluster_name}'")

            cursor.execute("""
                INSERT INTO taxonomy_clusters (typologie_id, name, description, position)
                VALUES (?, ?, ?, ?)
            """, (typologie_id, cluster_name, cluster_desc, position))
            taxonomy_id = cursor.lastrowid

            logger.info(f"  │    │    ✅ Inséré (ID: {taxonomy_id}, pos: {position})")

            # Sauvegarder les root labels
            root_labels = cluster.get('root_labels', [])
            logger.info(f"  │    │    🏷️  {len(root_labels)} root label(s)")

            self._save_root_labels(cursor, taxonomy_id, root_labels)

    def _save_root_labels(self, cursor, taxonomy_id, roots):
        """Sauvegarde tous les root labels avec logs détaillés"""
        for position, root in enumerate(roots):
            root_name = root['name']
            root_desc = root.get('description', '')
            root_cat = root.get('category', 'default')

            logger.info(f"  │    │    │")
            logger.info(f"  │    │    ├─ [{position+1}/{len(roots)}] Root: '{root_name}' (cat: {root_cat})")

            cursor.execute("""
                INSERT INTO root_labels (taxonomy_id, name, description, category, position)
                VALUES (?, ?, ?, ?, ?)
            """, (taxonomy_id, root_name, root_desc, root_cat, position))
            root_id = cursor.lastrowid

            logger.info(f"  │    │    │    ✅ Inséré (ID: {root_id}, pos: {position})")

            # Sauvegarder les parent labels
            parent_labels = root.get('parent_labels', [])
            logger.info(f"  │    │    │    👨 {len(parent_labels)} parent label(s)")

            self._save_parent_labels(cursor, root_id, parent_labels)

    def _save_parent_labels(self, cursor, root_id, parents):
        """Sauvegarde tous les parent labels avec logs détaillés"""
        for position, parent in enumerate(parents):
            parent_name = parent['name']
            parent_desc = parent.get('description', '')
            parent_cat = parent.get('category', 'default')

            logger.info(f"  │    │    │    │")
            logger.info(f"  │    │    │    ├─ [{position+1}/{len(parents)}] Parent: '{parent_name}' (cat: {parent_cat})")

            cursor.execute("""
                INSERT INTO parent_labels (root_id, name, description, category, position)
                VALUES (?, ?, ?, ?, ?)
            """, (root_id, parent_name, parent_desc, parent_cat, position))
            parent_id = cursor.lastrowid

            logger.info(f"  │    │    │    │    ✅ Inséré (ID: {parent_id}, pos: {position})")

            # Sauvegarder les enfants récursivement
            children = parent.get('children', [])
            logger.info(f"  │    │    │    │    👶 {len(children)} enfant(s) direct(s)")

            self._save_children_recursive(cursor, children, parent_label_id=parent_id, depth=0)

    def _save_children_recursive(self, cursor, children, parent_label_id=None, 
                                  parent_child_id=None, depth=0):
        """Sauvegarde récursivement tous les enfants avec logs détaillés"""
        indent = "  │    │    │    │    │" + ("    │" * depth)

        for position, child in enumerate(children):
            child_name = child['name']
            child_desc = child.get('description', '')
            child_cat = child.get('category', 'default')

            logger.info(f"{indent}")
            logger.info(f"{indent}├─ [{position+1}/{len(children)}] Child (depth {depth}): '{child_name}'")

            cursor.execute("""
                INSERT INTO child_labels 
                (parent_label_id, parent_child_id, name, description, category, depth, position)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (parent_label_id, parent_child_id, child_name, child_desc, child_cat, depth, position))
            child_id = cursor.lastrowid

            logger.info(f"{indent}│    ✅ Inséré (ID: {child_id}, depth: {depth}, pos: {position})")

            # Sauvegarder les sous-enfants
            sub_children = child.get('children', [])
            if sub_children:
                logger.info(f"{indent}│    👶 {len(sub_children)} sous-enfant(s)")
                self._save_children_recursive(cursor, sub_children, 
                                             parent_child_id=child_id, depth=depth+1)
                
    def _verify_saved_data(self, cursor, project_id, project_name):
        """Vérifie que les données ont bien été sauvegardées"""
        logger.info("  ┌─ Vérification des données sauvegardées")

        # Compter les typologies
        cursor.execute("SELECT COUNT(*) as count FROM typologies WHERE project_id = ?", (project_id,))
        typ_count = cursor.fetchone()['count']
        logger.info(f"  │  ✅ {typ_count} typologie(s) dans la base")

        # Compter les clusters
        cursor.execute("""
            SELECT COUNT(*) as count FROM taxonomy_clusters 
            WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
        """, (project_id,))
        cluster_count = cursor.fetchone()['count']
        logger.info(f"  │  ✅ {cluster_count} cluster(s) de taxonomie dans la base")

        # Compter les roots
        cursor.execute("""
            SELECT COUNT(*) as count FROM root_labels 
            WHERE taxonomy_id IN (
                SELECT id FROM taxonomy_clusters 
                WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
            )
        """, (project_id,))
        root_count = cursor.fetchone()['count']
        logger.info(f"  │  ✅ {root_count} root label(s) dans la base")

        # Compter les parents
        cursor.execute("""
            SELECT COUNT(*) as count FROM parent_labels 
            WHERE root_id IN (
                SELECT id FROM root_labels 
                WHERE taxonomy_id IN (
                    SELECT id FROM taxonomy_clusters 
                    WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                )
            )
        """, (project_id,))
        parent_count = cursor.fetchone()['count']
        logger.info(f"  │  ✅ {parent_count} parent label(s) dans la base")

        # Compter les enfants
        cursor.execute("""
            SELECT COUNT(*) as count FROM child_labels 
            WHERE parent_label_id IN (
                SELECT id FROM parent_labels 
                WHERE root_id IN (
                    SELECT id FROM root_labels 
                    WHERE taxonomy_id IN (
                        SELECT id FROM taxonomy_clusters 
                        WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                    )
                )
            )
        """, (project_id,))
        child_count = cursor.fetchone()['count']
        logger.info(f"  │  ✅ {child_count} child label(s) dans la base")

        logger.info("  └─ ✅ Vérification terminée")

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
            try:
                self.connection.close()
                logger.info("✅ Connexion à la base de données fermée")
            except Exception as e:
                logger.warning(f"⚠️  Erreur lors de la fermeture: {e}")