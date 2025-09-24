import sqlite3
import os
import json
from datetime import datetime
from utils.logger import logger
from utils.exceptions import DatabaseError


class Database:
    """
    Classe pour gérer les interactions avec la base de données SQLite
    """

    def __init__(self, db_path=None):
        """
        Initialise la connexion à la base de données

        Args:
            db_path (str, optional): Chemin vers le fichier de base de données
        """
        if db_path is None:
            # Utiliser un chemin par défaut s'il n'est pas spécifié
            self.db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
                "liris.db",
            )
        else:
            self.db_path = db_path

        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        logger.info(f"Initialisation de la base de données: {self.db_path}")

        # Établir la connexion
        self.connect()

        # Initialiser les tables
        self._init_tables()

        # Effectuer la migration automatique des profils existants (pour les plateformes IA)
        self._migrate_existing_profiles()

    def connect(self):
        """
        Établit la connexion à la base de données

        Returns:
            bool: True si la connexion est établie, False sinon
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Activer les foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Configurer pour retourner les résultats comme des dictionnaires
            self.conn.row_factory = sqlite3.Row

            logger.debug("Connexion établie à la base de données")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la connexion à la base de données: {str(e)}")
            raise DatabaseError(f"Échec de connexion à la base de données: {str(e)}")

    def _init_tables(self):
        """
        Initialise les tables nécessaires dans la base de données

        Returns:
            bool: True si l'initialisation est réussie, False sinon
        """
        try:
            cursor = self.conn.cursor()

            # Table des plateformes et leurs configurations
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS platforms
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT NOT NULL UNIQUE,
                               profile_data TEXT NOT NULL,
                               created_at TEXT NOT NULL,
                               updated_at TEXT NOT NULL
                           )
                           """)

            # Table de configuration du clavier (simplifiée)
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS keyboard_config
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               layout_type TEXT NOT NULL,
                               key_delay INTEGER DEFAULT 50,
                               accent_delay INTEGER DEFAULT 100,
                               accent_method TEXT NOT NULL,
                               block_alt_tab BOOLEAN DEFAULT 1,
                               focus_lock BOOLEAN DEFAULT 1,
                               protection_timeout INTEGER DEFAULT 30,
                               created_at TEXT NOT NULL,
                               updated_at TEXT NOT NULL,
                               is_active BOOLEAN DEFAULT 1
                           )
                           """)

            # Table des sessions d'IA
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS ai_sessions
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               platform_name TEXT NOT NULL,
                               session_date TEXT NOT NULL,
                               prompt_count INTEGER DEFAULT 0,
                               token_count INTEGER DEFAULT 0,
                               status TEXT DEFAULT 'active'
                           )
                           """)

            # Table des prompts
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS prompts
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               session_id INTEGER,
                               timestamp TEXT NOT NULL,
                               content TEXT NOT NULL,
                               token_count INTEGER DEFAULT 0,
                               operation_type TEXT NOT NULL,
                               FOREIGN KEY (session_id) REFERENCES ai_sessions (id)
                           )
                           """)

            # Table des réponses
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS responses
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               prompt_id INTEGER,
                               timestamp TEXT NOT NULL,
                               content TEXT NOT NULL,
                               status TEXT DEFAULT 'success',
                               FOREIGN KEY (prompt_id) REFERENCES prompts (id)
                           )
                           """)

            # Table des datasets générés
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS datasets
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT NOT NULL,
                               creation_date TEXT NOT NULL,
                               type TEXT NOT NULL,
                               format TEXT NOT NULL,
                               item_count INTEGER DEFAULT 0,
                               filepath TEXT NOT NULL
                           )
                           """)

            # Table des sessions de brainstorming
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS brainstorming_sessions
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT NOT NULL,
                               creation_date TEXT NOT NULL,
                               ai_platforms TEXT NOT NULL,
                               context TEXT NOT NULL,
                               status TEXT DEFAULT 'in_progress'
                           )
                           """)

            # Table des résultats de brainstorming
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS brainstorming_results
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               session_id INTEGER,
                               platform_name TEXT NOT NULL,
                               solution TEXT NOT NULL,
                               evaluations TEXT,
                               final_score INTEGER,
                               FOREIGN KEY (session_id) REFERENCES brainstorming_sessions (id)
                           )
                           """)

            # NOUVELLE TABLE: project_profiles pour les configurations de projets Turing
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS project_profiles
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT NOT NULL UNIQUE,
                               profile_data TEXT NOT NULL,
                               created_at TEXT NOT NULL,
                               updated_at TEXT NOT NULL
                           )
                           """)

            # Table pour stocker les références des noeuds Dgraph
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS graph_nodes
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_name TEXT NOT NULL,
                               dgraph_uid TEXT NOT NULL UNIQUE,
                               cluster_uid TEXT,
                               label_uid TEXT,
                               created_at TEXT NOT NULL,
                               updated_at TEXT NOT NULL
                           )
                           """)
            # Table des projets de typologie
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Table des typologies (appartient à un projet)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_typologies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES typology_projects (id) ON DELETE CASCADE,
                    UNIQUE(project_id, name)
                )
            """)
            
            # Table des clusters (appartient à une typologie)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typology_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (typology_id) REFERENCES context_typologies (id) ON DELETE CASCADE,
                    UNIQUE(typology_id, name)
                )
            """)

            # Table des racines (appartient à un cluster)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_roots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (cluster_id) REFERENCES typology_clusters (id) ON DELETE CASCADE,
                    UNIQUE(cluster_id, name)
                )
            """)
            
            # Table des parents (appartient à une racine)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_parents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (root_id) REFERENCES typology_roots (id) ON DELETE CASCADE,
                    UNIQUE(root_id, name)
                )
            """)
            
            # Table des enfants (appartient à un parent)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_children (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (parent_id) REFERENCES typology_parents (id) ON DELETE CASCADE,
                    UNIQUE(parent_id, name)
                )
            """)
            
            # Table pour stocker les statistiques des batches/exemples
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS typology_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typology_id INTEGER NOT NULL,
                    cluster_name TEXT,
                    root_name TEXT,
                    parent_name TEXT,
                    batch_name TEXT NOT NULL,
                    examples_count INTEGER DEFAULT 0,
                    percentage REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (typology_id) REFERENCES context_typologies (id) ON DELETE CASCADE
                )
            """)
            
             # Index pour optimiser les recherches
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_typology_project ON context_typologies (project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_typology ON typology_clusters (typology_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_root_cluster ON typology_roots (cluster_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_root ON typology_parents (root_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_child_parent ON typology_children (parent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_typology ON typology_statistics (typology_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_label_uid ON graph_nodes (label_uid)")

            # Création de la table des projets dataset
            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dataset_project (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                description TEXT
                            );
                            """)

            # Table typologie (appartient à un dataset_project)
            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS typology (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                project_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                is_hierarchical BOOLEAN NOT NULL DEFAULT 0,
                                FOREIGN KEY (project_id) REFERENCES dataset_project(id)
                            );
                            """)

            # Table des labels (taxonomie pour les typologies)
            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS label (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                typology_id INTEGER NOT NULL,
                                parent_id INTEGER, -- NULL si c'est un label root
                                label_value TEXT NOT NULL,
                                FOREIGN KEY (typology_id) REFERENCES typology(id),
                                FOREIGN KEY (parent_id) REFERENCES label(id)
                            );
                            """)

            self.conn.commit()
            logger.info("Initialisation des tables terminée")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation des tables: {str(e)}")
            raise DatabaseError(f"Échec de l'initialisation des tables: {str(e)}")

    def close(self):
        """
        Ferme la connexion à la base de données

        Returns:
            bool: True si la fermeture est réussie, False sinon
        """
        try:
            if hasattr(self, "conn") and self.conn:
                self.conn.close()
                logger.debug("Connexion à la base de données fermée")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la connexion: {str(e)}")
            return False

    # =====================================================
    # NOUVELLES MÉTHODES POUR GESTION MULTI-FENÊTRES (INCHANGÉES ICI)
    # =====================================================

    def _get_default_browser_config(self):
        """
        Retourne la configuration navigateur par défaut avec support multi-fenêtres

        Returns:
            dict: Configuration par défaut
        """
        return {
            "type": "Chrome",
            "path": "",
            "url": "",
            "fullscreen": False,
            # NOUVELLES OPTIONS MULTI-FENÊTRES (avec valeurs par défaut conservant comportement actuel)
            "window_selection_method": "auto",  # "auto" = comportement actuel (première fenêtre)
            "window_order": 1,  # 1 = première fenêtre = comportement actuel
            "window_title_pattern": "",  # Vide = pas de filtrage par titre
            "window_position": None,  # None = pas de filtrage par position
            "window_id": None,  # None = pas de fenêtre spécifique mémorisée
            "window_size": None,  # None = pas de contrainte de taille
            "remember_window": False,  # False = ne pas mémoriser la sélection
        }

    def _migrate_browser_config(self, browser_config):
        """
        Migre une configuration navigateur vers le nouveau format multi-fenêtres

        Args:
            browser_config (dict): Configuration existante

        Returns:
            dict: Configuration migrée
        """
        if not browser_config:
            return self._get_default_browser_config()

        # Créer la nouvelle configuration en préservant l'existante
        default_config = self._get_default_browser_config()
        migrated_config = default_config.copy()

        # Préserver toutes les valeurs existantes
        for key, value in browser_config.items():
            migrated_config[key] = value

        # Ajouter les nouveaux champs s'ils n'existent pas
        for key, default_value in default_config.items():
            if key not in migrated_config:
                migrated_config[key] = default_value

        logger.debug(f"Configuration navigateur migrée: {list(migrated_config.keys())}")
        return migrated_config

    def _migrate_existing_profiles(self):
        """
        Migre automatiquement tous les profils existants (plateformes) vers le nouveau format
        """
        try:
            logger.info(
                "Vérification de la migration des profils de plateformes existants..."
            )

            cursor = self.conn.cursor()
            cursor.execute("SELECT name, profile_data FROM platforms")
            results = cursor.fetchall()

            migration_count = 0

            for row in results:
                try:
                    platform_name = row["name"]
                    profile_data = json.loads(row["profile_data"])

                    # Vérifier si la migration est nécessaire
                    browser_config = profile_data.get("browser", {})
                    needs_migration = "window_selection_method" not in browser_config

                    if needs_migration:
                        logger.debug(f"Migration du profil {platform_name}...")

                        # Migrer la configuration navigateur
                        profile_data["browser"] = self._migrate_browser_config(
                            browser_config
                        )

                        # Sauvegarder le profil migré
                        now = datetime.now().isoformat()
                        profile_json = json.dumps(
                            profile_data, ensure_ascii=False, indent=2
                        )

                        cursor.execute(
                            """
                                       UPDATE platforms
                                       SET profile_data = ?,
                                           updated_at   = ?
                                       WHERE name = ?
                                       """,
                            (profile_json, now, platform_name),
                        )

                        migration_count += 1
                        logger.debug(f"Profil {platform_name} migré avec succès")

                except Exception as e:
                    logger.error(f"Erreur migration profil {row['name']}: {str(e)}")
                    continue

            if migration_count > 0:
                self.conn.commit()
                logger.info(
                    f"Migration terminée: {migration_count} profils de plateformes migrés"
                )
            else:
                logger.debug("Aucune migration de plateformes nécessaire")

        except Exception as e:
            logger.error(
                f"Erreur lors de la migration automatique des plateformes: {str(e)}"
            )

    def validate_browser_config(self, browser_config):
        """
        Valide et normalise une configuration navigateur

        Args:
            browser_config (dict): Configuration à valider

        Returns:
            tuple: (is_valid, normalized_config, error_message)
        """
        try:
            if not browser_config:
                return True, self._get_default_browser_config(), None

            # Cloner la configuration
            normalized = browser_config.copy()

            # Valider window_selection_method
            valid_methods = ["auto", "order", "title", "position", "manual"]
            method = normalized.get("window_selection_method", "auto")
            if method not in valid_methods:
                normalized["window_selection_method"] = "auto"
                logger.warning(
                    f"Méthode de sélection invalide '{method}', fallback sur 'auto'"
                )

            # Valider window_order
            order = normalized.get("window_order", 1)
            if not isinstance(order, int) or order < 1:
                normalized["window_order"] = 1
                logger.warning(f"Ordre de fenêtre invalide '{order}', fallback sur 1")

            # Valider window_title_pattern
            title_pattern = normalized.get("window_title_pattern")
            if title_pattern is not None and not isinstance(title_pattern, str):
                normalized["window_title_pattern"] = ""
                logger.warning("Pattern de titre invalide, réinitialisé")

            # Valider window_position
            position = normalized.get("window_position")
            if position is not None:
                if (
                    not isinstance(position, dict)
                    or "x" not in position
                    or "y" not in position
                ):
                    normalized["window_position"] = None
                    logger.warning("Position de fenêtre invalide, réinitialisée")
                else:
                    try:
                        normalized["window_position"]["x"] = int(position["x"])
                        normalized["window_position"]["y"] = int(position["y"])
                    except (ValueError, TypeError):
                        normalized["window_position"] = None
                        logger.warning(
                            "Coordonnées de position invalides, réinitialisées"
                        )

            # S'assurer que tous les champs requis existent
            default_config = self._get_default_browser_config()
            for key, default_value in default_config.items():
                if key not in normalized:
                    normalized[key] = default_value

            return True, normalized, None

        except Exception as e:
            error_msg = f"Erreur validation config navigateur: {str(e)}"
            logger.error(error_msg)
            return False, self._get_default_browser_config(), error_msg

    def get_window_selection_info(self, platform_name):
        """
        Récupère les informations de sélection de fenêtre pour une plateforme

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Informations de sélection ou None si non trouvé
        """
        try:
            profile = self.get_platform(platform_name)
            if not profile:
                return None

            browser_config = profile.get("browser", {})

            return {
                "method": browser_config.get("window_selection_method", "auto"),
                "order": browser_config.get("window_order", 1),
                "title_pattern": browser_config.get("window_title_pattern", ""),
                "position": browser_config.get("window_position"),
                "window_id": browser_config.get("window_id"),
                "remember_window": browser_config.get("remember_window", False),
            }

        except Exception as e:
            logger.error(
                f"Erreur récupération info sélection fenêtre {platform_name}: {str(e)}"
            )
            return None

    def update_window_selection(self, platform_name, selection_info):
        """
        Met à jour les informations de sélection de fenêtre pour une plateforme

        Args:
            platform_name (str): Nom de la plateforme
            selection_info (dict): Nouvelles informations de sélection

        Returns:
            bool: True si mise à jour réussie
        """
        try:
            profile = self.get_platform(platform_name)
            if not profile:
                logger.error(
                    f"Plateforme {platform_name} non trouvée pour mise à jour sélection fenêtre"
                )
                return False

            # Mettre à jour la configuration navigateur
            browser_config = profile.get("browser", {})

            if "method" in selection_info:
                browser_config["window_selection_method"] = selection_info["method"]
            if "order" in selection_info:
                browser_config["window_order"] = selection_info["order"]
            if "title_pattern" in selection_info:
                browser_config["window_title_pattern"] = selection_info["title_pattern"]
            if "position" in selection_info:
                browser_config["window_position"] = selection_info["position"]
            if "window_id" in selection_info:
                browser_config["window_id"] = selection_info["window_id"]
            if "remember_window" in selection_info:
                browser_config["remember_window"] = selection_info["remember_window"]

            # Valider la configuration
            is_valid, normalized_config, error = self.validate_browser_config(
                browser_config
            )
            if not is_valid:
                logger.error(f"Configuration invalide: {error}")
                return False

            profile["browser"] = normalized_config

            # Sauvegarder
            return self.save_platform(platform_name, profile)

        except Exception as e:
            logger.error(
                f"Erreur mise à jour sélection fenêtre {platform_name}: {str(e)}"
            )
            return False

    # =====================================================
    # MÉTHODES POUR GESTION DES PLATEFORMES (ENRICHIES)
    # =====================================================

    def save_platform(self, platform_name, profile_data):
        """
        Sauvegarde un profil de plateforme en base de données avec support multi-fenêtres

        Args:
            platform_name (str): Nom de la plateforme
            profile_data (dict): Données du profil à sauvegarder

        Returns:
            bool: True si sauvegarde réussie, False sinon
        """
        try:
            logger.debug(f"Sauvegarde plateforme {platform_name} en base de données")

            # Validation et normalisation de la configuration navigateur
            if "browser" in profile_data:
                is_valid, normalized_browser, error = self.validate_browser_config(
                    profile_data["browser"]
                )
                if not is_valid:
                    logger.error(
                        f"Configuration navigateur invalide pour {platform_name}: {error}"
                    )
                    return False
                profile_data["browser"] = normalized_browser
            else:
                # Ajouter configuration par défaut si absente
                profile_data["browser"] = self._get_default_browser_config()

            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            # Convertir le profil en JSON
            profile_json = json.dumps(profile_data, ensure_ascii=False, indent=2)

            # Vérifier si la plateforme existe déjà
            cursor.execute("SELECT id FROM platforms WHERE name = ?", (platform_name,))
            existing = cursor.fetchone()

            if existing:
                # Mettre à jour
                cursor.execute(
                    """
                               UPDATE platforms
                               SET profile_data = ?,
                                   updated_at   = ?
                               WHERE name = ?
                               """,
                    (profile_json, now, platform_name),
                )
                logger.info(f"Profil {platform_name} mis à jour en base de données")
            else:
                # Créer nouveau
                cursor.execute(
                    """
                               INSERT INTO platforms (name, profile_data, created_at, updated_at)
                               VALUES (?, ?, ?, ?)
                               """,
                    (platform_name, profile_json, now, now),
                )
                logger.info(f"Nouveau profil {platform_name} créé en base de données")

            self.conn.commit()

            # Vérification de la sauvegarde
            saved_profile = self.get_platform(platform_name)
            if saved_profile:
                logger.debug(f"Vérification sauvegarde {platform_name}: OK")
                return True
            else:
                logger.error(f"Échec vérification sauvegarde {platform_name}")
                return False

        except Exception as e:
            logger.error(f"Erreur sauvegarde plateforme {platform_name}: {str(e)}")
            return False

    def get_platform(self, platform_name):
        """
        Récupère un profil de plateforme depuis la base de données avec migration automatique

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Profil de la plateforme ou None si non trouvé
        """
        try:
            logger.debug(
                f"Récupération plateforme {platform_name} depuis la base de données"
            )

            cursor = self.conn.cursor()

            cursor.execute(
                "SELECT profile_data FROM platforms WHERE name = ?", (platform_name,)
            )
            result = cursor.fetchone()

            if result:
                # Décoder le JSON
                profile_data = json.loads(result["profile_data"])

                # Migration automatique si nécessaire
                browser_config = profile_data.get("browser", {})
                if "window_selection_method" not in browser_config:
                    logger.debug(f"Migration automatique du profil {platform_name}")
                    profile_data["browser"] = self._migrate_browser_config(
                        browser_config
                    )

                    # Sauvegarder la version migrée
                    self.save_platform(platform_name, profile_data)

                logger.debug(
                    f"Profil {platform_name} récupéré depuis la base (taille: {len(str(profile_data))} caractères)"
                )

                return profile_data
            else:
                logger.debug(f"Profil {platform_name} non trouvé en base de données")
                return None

        except Exception as e:
            logger.error(f"Erreur récupération plateforme {platform_name}: {str(e)}")
            return None

    def get_all_platforms(self):
        """
        Récupère tous les profils de plateformes avec migration automatique

        Returns:
            dict: Dictionnaire des profils {nom: profil}
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, profile_data FROM platforms")
            results = cursor.fetchall()

            platforms = {}
            migration_needed = False

            for row in results:
                try:
                    platform_name = row["name"]
                    profile_data = json.loads(row["profile_data"])

                    # Migration automatique si nécessaire
                    browser_config = profile_data.get("browser", {})
                    if "window_selection_method" not in browser_config:
                        logger.debug(f"Migration automatique du profil {platform_name}")
                        profile_data["browser"] = self._migrate_browser_config(
                            browser_config
                        )
                        migration_needed = True

                        # Sauvegarder la version migrée
                        now = datetime.now().isoformat()
                        profile_json = json.dumps(
                            profile_data, ensure_ascii=False, indent=2
                        )
                        cursor.execute(
                            """
                                       UPDATE platforms
                                       SET profile_data = ?,
                                           updated_at   = ?
                                       WHERE name = ?
                                       """,
                            (profile_json, now, platform_name),
                        )

                    platforms[platform_name] = profile_data

                except Exception as e:
                    logger.error(f"Erreur décodage profil {row['name']}: {str(e)}")

            if migration_needed:
                self.conn.commit()
                logger.info("Migration automatique effectuée lors de get_all_platforms")

            logger.debug(f"{len(platforms)} profils de plateformes récupérés")
            return platforms

        except Exception as e:
            logger.error(f"Erreur récupération tous les profils: {str(e)}")
            return {}

    def platform_exists(self, platform_name):
        """
        Vérifie si une plateforme existe

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            bool: True si la plateforme existe
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM platforms WHERE name = ?", (platform_name,))
            return cursor.fetchone() is not None

        except Exception as e:
            logger.error(
                f"Erreur vérification existence plateforme {platform_name}: {str(e)}"
            )
            return False

    def was_platform_deleted(self, platform_name):
        """
        Vérifie si une plateforme a été délibérément supprimée

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            bool: True si la plateforme a été supprimée
        """
        # Pour l'instant, retourne toujours False
        return False

    def delete_platform(self, platform_name):
        """
        Supprime une plateforme de la base de données

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            bool: True si suppression réussie
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM platforms WHERE name = ?", (platform_name,))

            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Plateforme {platform_name} supprimée de la base")
                return True
            else:
                logger.warning(
                    f"Plateforme {platform_name} non trouvée pour suppression"
                )
                return False

        except Exception as e:
            logger.error(f"Erreur suppression plateforme {platform_name}: {str(e)}")
            return False

    # =====================================================
    # NOUVELLES MÉTHODES POUR GESTION DES PROJETS
    # =====================================================

    def save_project_profile(self, project_name, profile_data):
        """
        Sauvegarde un profil de projet en base de données.

        Args:
            project_name (str): Nom du projet.
            profile_data (dict): Données du profil de projet à sauvegarder.

        Returns:
            bool: True si sauvegarde réussie, False sinon.
        """
        try:
            logger.debug(
                f"Sauvegarde du profil de projet '{project_name}' en base de données."
            )
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            profile_json = json.dumps(profile_data, ensure_ascii=False, indent=2)

            cursor.execute(
                "SELECT id FROM project_profiles WHERE name = ?", (project_name,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                               UPDATE project_profiles
                               SET profile_data = ?,
                                   updated_at   = ?
                               WHERE name = ?
                               """,
                    (profile_json, now, project_name),
                )
                logger.info(
                    f"Profil de projet '{project_name}' mis à jour en base de données."
                )
            else:
                cursor.execute(
                    """
                               INSERT INTO project_profiles (name, profile_data, created_at, updated_at)
                               VALUES (?, ?, ?, ?)
                               """,
                    (project_name, profile_json, now, now),
                )
                logger.info(
                    f"Nouveau profil de projet '{project_name}' créé en base de données."
                )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(
                f"Erreur lors de la sauvegarde du profil de projet '{project_name}': {str(e)}"
            )
            return False

    def get_project_profile(self, project_name):
        """
        Récupère un profil de projet spécifique depuis la base de données.

        Args:
            project_name (str): Nom du projet.

        Returns:
            dict: Profil du projet ou None si non trouvé.
        """
        try:
            logger.debug(
                f"Récupération du profil de projet '{project_name}' depuis la base de données."
            )
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT profile_data FROM project_profiles WHERE name = ?",
                (project_name,),
            )
            result = cursor.fetchone()
            if result:
                return json.loads(result["profile_data"])
            else:
                logger.debug(
                    f"Profil de projet '{project_name}' non trouvé en base de données."
                )
                return None
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération du profil de projet '{project_name}': {str(e)}"
            )
            return None

    def get_all_project_profiles(self):
        """
        Récupère tous les profils de projets depuis la base de données.

        Returns:
            dict: Dictionnaire des profils {nom_projet: données_profil}.
        """
        try:
            logger.debug(
                "Récupération de tous les profils de projets depuis la base de données."
            )
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, profile_data FROM project_profiles")
            results = cursor.fetchall()
            profiles = {}
            for row in results:
                try:
                    profiles[row["name"]] = json.loads(row["profile_data"])
                except Exception as e:
                    logger.error(
                        f"Erreur décodage profil de projet '{row['name']}': {str(e)}"
                    )
            logger.debug(f"{len(profiles)} profils de projets récupérés.")
            return profiles
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération de tous les profils de projets: {str(e)}"
            )
            return {}

    def delete_project_profile(self, project_name):
        """
        Supprime un profil de projet et tous les noeuds de graphe associés.

        Args:
            project_name (str): Nom du projet à supprimer.

        Returns:
            bool: True si la suppression est réussie, False sinon.
        """
        try:
            logger.debug(
                f"Tentative de suppression du projet '{project_name}' et de ses noeuds associés."
            )
            cursor = self.conn.cursor()

            # Étape 1: Supprimer les noeuds de graphe associés au projet
            cursor.execute(
                "DELETE FROM graph_nodes WHERE project_name = ?", (project_name,)
            )
            nodes_deleted_count = cursor.rowcount
            logger.info(
                f"{nodes_deleted_count} noeuds de graphe associés à '{project_name}' ont été supprimés."
            )

            # Étape 2: Supprimer le profil du projet
            cursor.execute(
                "DELETE FROM project_profiles WHERE name = ?", (project_name,)
            )
            project_deleted_count = cursor.rowcount

            if project_deleted_count > 0:
                self.conn.commit()
                logger.info(f"Profil de projet '{project_name}' supprimé avec succès.")
                return True
            else:
                # Si le projet n'existait pas, on annule la suppression des noeuds
                self.conn.rollback()
                logger.warning(
                    f"Profil de projet '{project_name}' non trouvé pour suppression."
                )
                return False

        except Exception as e:
            self.conn.rollback()
            logger.error(
                f"Erreur lors de la suppression du profil de projet '{project_name}': {str(e)}"
            )
            return False

    # =====================================================
    # MÉTHODES POUR GESTION DU CLAVIER (INCHANGÉES)
    # =====================================================

    def save_keyboard_config(self, config_data):
        """
        Sauvegarde la configuration du clavier

        Args:
            config_data (dict): Configuration du clavier

        Returns:
            bool: True si sauvegarde réussie
        """
        try:
            logger.debug("Sauvegarde configuration clavier")

            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            # Désactiver l'ancienne configuration
            cursor.execute(
                "UPDATE keyboard_config SET is_active = 0 WHERE is_active = 1"
            )

            # Insérer la nouvelle configuration
            cursor.execute(
                """
                           INSERT INTO keyboard_config (layout_type, key_delay, accent_delay, accent_method,
                                                        block_alt_tab, focus_lock, protection_timeout,
                                                        created_at, updated_at, is_active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """,
                (
                    config_data.get("layout", "AZERTY (Français)"),
                    config_data.get("key_delay", 50),
                    config_data.get("accent_delay", 100),
                    config_data.get("accent_method", "direct"),
                    config_data.get("block_alt_tab", True),
                    config_data.get("focus_lock", True),
                    config_data.get("protection_timeout", 30),
                    now,
                    now,
                    True,
                ),
            )

            self.conn.commit()
            logger.info("Configuration clavier sauvegardée")
            return True

        except Exception as e:
            logger.error(f"Erreur sauvegarde configuration clavier: {str(e)}")
            return False

    def get_keyboard_config(self):
        """
        Récupère la configuration active du clavier

        Returns:
            dict: Configuration du clavier ou None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                           SELECT *
                           FROM keyboard_config
                           WHERE is_active = 1
                           ORDER BY updated_at DESC LIMIT 1
                           """)

            result = cursor.fetchone()

            if result:
                config_data = {
                    "layout": result["layout_type"],
                    "key_delay": result["key_delay"],
                    "accent_delay": result["accent_delay"],
                    "accent_method": result["accent_method"],
                    "block_alt_tab": bool(result["block_alt_tab"]),
                    "focus_lock": bool(result["focus_lock"]),
                    "protection_timeout": result["protection_timeout"],
                    "created_at": result["created_at"],
                    "updated_at": result["updated_at"],
                }

                logger.debug("Configuration clavier récupérée")
                return config_data
            else:
                logger.debug("Aucune configuration clavier trouvée")
                return None

        except Exception as e:
            logger.error(f"Erreur récupération configuration clavier: {str(e)}")
            return None

    # =====================================================
    # MÉTHODES EXISTANTES (SESSIONS, PROMPTS, ETC.) - INCHANGÉES
    # =====================================================

    def create_session(self, platform_name):
        """
        Crée une nouvelle session pour une plateforme d'IA

        Args:
            platform_name (str): Nom de la plateforme d'IA

        Returns:
            int: ID de la session créée
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                """
                           INSERT INTO ai_sessions (platform_name, session_date, status)
                           VALUES (?, ?, ?)
                           """,
                (platform_name, now, "active"),
            )

            self.conn.commit()
            session_id = cursor.lastrowid

            logger.debug(
                f"Nouvelle session créée pour {platform_name}, ID: {session_id}"
            )
            return session_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de session: {str(e)}")
            raise DatabaseError(f"Échec de la création de session: {str(e)}")

    def record_prompt(self, session_id, content, token_count, operation_type):
        """
        Enregistre un prompt envoyé

        Args:
            session_id (int): ID de la session
            content (str): Contenu du prompt
            token_count (int): Nombre de tokens
            operation_type (str): Type d'opération (analyse, génération, annotation, brainstorming)

        Returns:
            int: ID du prompt enregistré
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                """
                           INSERT INTO prompts (session_id, timestamp, content, token_count, operation_type)
                           VALUES (?, ?, ?, ?, ?)
                           """,
                (session_id, now, content, token_count, operation_type),
            )

            # Mettre à jour les compteurs de la session
            cursor.execute(
                """
                           UPDATE ai_sessions
                           SET prompt_count = prompt_count + 1,
                               token_count  = token_count + ?
                           WHERE id = ?
                           """,
                (token_count, session_id),
            )

            self.conn.commit()
            prompt_id = cursor.lastrowid

            logger.debug(f"Prompt enregistré, ID: {prompt_id}")
            return prompt_id

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du prompt: {str(e)}")
            raise DatabaseError(f"Échec de l'enregistrement du prompt: {str(e)}")

    def record_response(self, prompt_id, content, status="success"):
        """
        Enregistre une réponse reçue

        Args:
            prompt_id (int): ID du prompt correspondant
            content (str): Contenu de la réponse
            status (str): Statut de la réponse ('success', 'error', etc.)

        Returns:
            int: ID de la réponse enregistrée
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                """
                           INSERT INTO responses (prompt_id, timestamp, content, status)
                           VALUES (?, ?, ?, ?)
                           """,
                (prompt_id, now, content, status),
            )

            self.conn.commit()
            response_id = cursor.lastrowid

            logger.debug(f"Réponse enregistrée, ID: {response_id}")
            return response_id

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la réponse: {str(e)}")
            raise DatabaseError(f"Échec de l'enregistrement de la réponse: {str(e)}")

    def get_session_stats(self, platform_name=None, date_from=None, date_to=None):
        """
        Récupère les statistiques des sessions

        Args:
            platform_name (str, optional): Filtrer par plateforme
            date_from (str, optional): Date de début (format ISO)
            date_to (str, optional): Date de fin (format ISO)

        Returns:
            list: Liste des statistiques de session
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM ai_sessions WHERE 1=1"
            params = []

            if platform_name:
                query += " AND platform_name = ?"
                params.append(platform_name)

            if date_from:
                query += " AND session_date >= ?"
                params.append(date_from)

            if date_to:
                query += " AND session_date <= ?"
                params.append(date_to)

            query += " ORDER BY session_date DESC"

            cursor.execute(query, params)
            results = cursor.fetchall()

            # Convertir les résultats en dictionnaires
            stats = []
            for row in results:
                stats.append(dict(row))

            return stats

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
            raise DatabaseError(f"Échec de la récupération des statistiques: {str(e)}")

    def record_dataset(self, name, dataset_type, format, item_count, filepath):
        """
        Enregistre un dataset généré

        Args:
            name (str): Nom du dataset
            dataset_type (str): Type de dataset
            format (str): Format du dataset (CSV, JSON, etc.)
            item_count (int): Nombre d'éléments
            filepath (str): Chemin vers le fichier

        Returns:
            int: ID du dataset enregistré
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                """
                           INSERT INTO datasets (name, creation_date, type, format, item_count, filepath)
                           VALUES (?, ?, ?, ?, ?, ?)
                           """,
                (name, now, dataset_type, format, item_count, filepath),
            )

            self.conn.commit()
            dataset_id = cursor.lastrowid

            logger.debug(f"Dataset enregistré, ID: {dataset_id}")
            return dataset_id

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du dataset: {str(e)}")
            raise DatabaseError(f"Échec de l'enregistrement du dataset: {str(e)}")

    def create_brainstorming_session(self, name, ai_platforms, context):
        """
        Crée une nouvelle session de brainstorming

        Args:
            name (str): Nom de la session
            ai_platforms (list): Liste des plateformes d'IA participantes
            context (str): Contexte du brainstorming

        Returns:
            int: ID de la session créée
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            # Convertir la liste des plateformes en JSON
            platforms_json = json.dumps(ai_platforms)

            cursor.execute(
                """
                           INSERT INTO brainstorming_sessions (name, creation_date, ai_platforms, context, status)
                           VALUES (?, ?, ?, ?, ?)
                           """,
                (name, now, platforms_json, context, "in_progress"),
            )

            self.conn.commit()
            session_id = cursor.lastrowid

            logger.debug(f"Session de brainstorming créée, ID: {session_id}")
            return session_id

        except Exception as e:
            logger.error(
                f"Erreur lors de la création de session de brainstorming: {str(e)}"
            )
            raise DatabaseError(
                f"Échec de la création de session de brainstorming: {str(e)}"
            )

    def record_brainstorming_result(
        self, session_id, platform_name, solution, evaluations=None, final_score=None
    ):
        """
        Enregistre un résultat de brainstorming

        Args:
            session_id (int): ID de la session
            platform_name (str): Nom de la plateforme d'IA
            solution (str): Solution proposée
            evaluations (dict, optional): Évaluations des autres IA
            final_score (int, optional): Score final

        Returns:
            int: ID du résultat enregistré
        """
        try:
            cursor = self.conn.cursor()

            # Convertir les évaluations en JSON si présentes
            evaluations_json = json.dumps(evaluations) if evaluations else None

            cursor.execute(
                """
                           INSERT INTO brainstorming_results (session_id, platform_name, solution, evaluations, final_score)
                           VALUES (?, ?, ?, ?, ?)
                           """,
                (session_id, platform_name, solution, evaluations_json, final_score),
            )

            self.conn.commit()
            result_id = cursor.lastrowid

            logger.debug(f"Résultat de brainstorming enregistré, ID: {result_id}")
            return result_id

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du résultat: {str(e)}")
            raise DatabaseError(f"Échec de l'enregistrement du résultat: {str(e)}")

    def update_brainstorming_status(self, session_id, status):
        """
        Met à jour le statut d'une session de brainstorming

        Args:
            session_id (int): ID de la session
            status (str): Nouveau statut

        Returns:
            bool: True si la mise à jour est réussie, False sinon
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                           UPDATE brainstorming_sessions
                           SET status = ?
                           WHERE id = ?
                           """,
                (status, session_id),
            )

            self.conn.commit()

            logger.debug(f"Statut de la session {session_id} mis à jour: {status}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {str(e)}")
            raise DatabaseError(f"Échec de la mise à jour du statut: {str(e)}")

    # =====================================================
    # MÉTHODES POUR GESTION DES RÉFÉRENCES DE NOEUDS DGRAPH
    # =====================================================

    def add_node_reference(self, project_name, dgraph_uid, cluster_uid, label_uid):
        """
        Ajoute une référence de noeud Dgraph dans la base de données locale.

        Args:
            project_name (str): Nom du projet auquel le noeud est associé.
            dgraph_uid (str): UID du noeud Dgraph.
            cluster_uid (str): UID du cluster parent.
            label_uid (str): UID du label associé.

        Returns:
            int: ID de la référence locale créée.
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                """
                           INSERT INTO graph_nodes (project_name, dgraph_uid, cluster_uid, label_uid, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)
                           """,
                (project_name, dgraph_uid, cluster_uid, label_uid, now, now),
            )
            self.conn.commit()
            node_id = cursor.lastrowid
            logger.debug(
                f"Référence de noeud Dgraph ajoutée pour UID {dgraph_uid} au projet {project_name}, ID local: {node_id}"
            )
            return node_id
        except Exception as e:
            logger.error(
                f"Erreur lors de l'ajout de la référence de noeud {dgraph_uid}: {str(e)}"
            )
            raise DatabaseError(f"Échec de l'ajout de la référence de noeud: {str(e)}")

    def update_node_reference(
        self, dgraph_uid, new_cluster_uid=None, new_label_uid=None
    ):
        """
        Met à jour la référence d'un noeud Dgraph.

        Args:
            dgraph_uid (str): UID du noeud à mettre à jour.
            new_cluster_uid (str, optional): Nouvel UID du cluster.
            new_label_uid (str, optional): Nouvel UID du label.

        Returns:
            bool: True si la mise à jour est réussie, False sinon.
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            updates = []
            params = []

            if new_cluster_uid is not None:
                updates.append("cluster_uid = ?")
                params.append(new_cluster_uid)

            if new_label_uid is not None:
                updates.append("label_uid = ?")
                params.append(new_label_uid)

            if not updates:
                logger.warning(
                    "Aucune mise à jour spécifiée pour le noeud {dgraph_uid}"
                )
                return False

            updates.append("updated_at = ?")
            params.append(now)
            params.append(dgraph_uid)

            query = f"UPDATE graph_nodes SET {', '.join(updates)} WHERE dgraph_uid = ?"

            cursor.execute(query, tuple(params))
            self.conn.commit()
            logger.info(f"Référence du noeud {dgraph_uid} mise à jour.")
            return True
        except Exception as e:
            logger.error(
                f"Erreur lors de la mise à jour de la référence du noeud {dgraph_uid}: {str(e)}"
            )
            return False

    def delete_node_reference(self, dgraph_uid):
        """
        Supprime la référence d'un noeud Dgraph.

        Args:
            dgraph_uid (str): UID du noeud à supprimer.

        Returns:
            bool: True si la suppression est réussie, False sinon.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM graph_nodes WHERE dgraph_uid = ?", (dgraph_uid,)
            )
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Référence du noeud {dgraph_uid} supprimée.")
                return True
            else:
                logger.warning(
                    f"Référence du noeud {dgraph_uid} non trouvée pour suppression."
                )
                return False
        except Exception as e:
            logger.error(
                f"Erreur lors de la suppression de la référence du noeud {dgraph_uid}: {str(e)}"
            )
            return False

    def get_nodes_by_cluster(self, cluster_uid):
        """
        Récupère toutes les références de noeuds pour un cluster donné.

        Args:
            cluster_uid (str): UID du cluster.

        Returns:
            list: Liste de dictionnaires représentant les références de noeuds.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM graph_nodes WHERE cluster_uid = ?", (cluster_uid,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération des noeuds pour le cluster {cluster_uid}: {str(e)}"
            )
            return []

    def get_nodes_by_label(self, label_uid):
        """
        Récupère toutes les références de noeuds pour un label donné.

        Args:
            label_uid (str): UID du label.

        Returns:
            list: Liste de dictionnaires représentant les références de noeuds.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM graph_nodes WHERE label_uid = ?", (label_uid,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération des noeuds pour le label {label_uid}: {str(e)}"
            )
            return []

    def get_node_reference(self, dgraph_uid):
        """
        Récupère une référence de noeud spécifique par son UID Dgraph.

        Args:
            dgraph_uid (str): UID du noeud Dgraph.

        Returns:
            dict: Dictionnaire représentant la référence du noeud, ou None si non trouvé.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM graph_nodes WHERE dgraph_uid = ?", (dgraph_uid,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération de la référence du noeud {dgraph_uid}: {str(e)}"
            )
            return None

    # =====================================================
    # MÉTHODES POUR GESTION DES  DATASETS_PROJECTS
    # =====================================================

    def save_dataset_projet(self, name, description):
        try:
            logger.debug(f"Sauvegarde projet dataset: {name}")
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute("SELECT id FROM dataset_project WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE dataset_project
                    SET description = ?, updated_at = ?
                    WHERE name = ?
                """,
                    (description, now, name),
                )
                logger.info(f"Dataset projet {name} mis à jour")
            else:
                cursor.execute(
                    """
                    INSERT INTO dataset_project (name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (name, description, now, now),
                )
                logger.info(f"Nouveau projet de dataset {name} créé")

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde projet de dataset {name}: {str(e)}")
            return False

    def get_dataset_projet(self, name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM dataset_project WHERE name = ?", (name,))
        return cursor.fetchone()

    def delete_dataset_project(self, project_id):
        try:
            logger.debug(f"Delete project ID {project_id}")
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM dataset_project WHERE id = ?", (project_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting project ID {project_id}: {e}")
            return False

    # =====================================================
    # MÉTHODES POUR GESTION DES  TYPOLOGIES CONTEXT
    # =====================================================

    def save_typology(self, project_id, name, is_hierarchical=False):
        try:
            logger.debug(f"Save typology: {name}")
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO typology (project_id, name, is_hierarchical, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (project_id, name, int(is_hierarchical), now, now),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving typology '{name}': {e}")
            return False

    def get_typologies(self, project_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM typology WHERE project_id = ?", (project_id,))
        return cursor.fetchall()

    def delete_typology(self, typology_id):
        try:
            logger.debug(f"Delete typology ID {typology_id}")
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM typology WHERE id = ?", (typology_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting typology ID {typology_id}: {e}")
            return False

    # =====================================================
    # MÉTHODES POUR GESTION DES  TAXIONOMIES ET LABELS
    # =====================================================

    def save_label(self, typology_id, label_value, parent_id=None):
        try:
            logger.debug(f"Save label: {label_value}")
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO label (typology_id, parent_id, label_value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (typology_id, parent_id, label_value, now, now),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving label '{label_value}': {e}")
            return False

    def get_labels(self, typology_id, parent_id=None):
        cursor = self.conn.cursor()
        if parent_id is None:
            cursor.execute(
                "SELECT * FROM label WHERE typology_id = ? AND parent_id IS NULL",
                (typology_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM label WHERE typology_id = ? AND parent_id = ?",
                (typology_id, parent_id),
            )
        return cursor.fetchall()

    def delete_label(self, label_id):
        try:
            logger.debug(f"Delete label ID {label_id}")
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM label WHERE id = ?", (label_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting label ID {label_id}: {e}")
            return False

        # =====================================================
        # MÉTHODES POUR GESTION DES TYPOLOGIES DE CONTEXTE
        # =====================================================

    def create_typology_project(self, name, description=""):
        """
        Créer un nouveau projet de typologie
        
        Args:
            name (str): Nom du projet
            description (str): Description du projet
            
        Returns:
            int: ID du projet créé
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO typology_projects (name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, now, now)
            )
            
            self.conn.commit()
            project_id = cursor.lastrowid
            logger.info(f"Projet de typologie '{name}' créé avec ID: {project_id}")
            return project_id
            
        except sqlite3.IntegrityError:
            logger.error(f"Un projet avec le nom '{name}' existe déjà")
            raise DatabaseError(f"Un projet avec le nom '{name}' existe déjà")
        except Exception as e:
            logger.error(f"Erreur création projet typologie '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création du projet: {str(e)}")

    def get_typology_projects(self):
        """
        Récupérer tous les projets de typologie
        
        Returns:
            list: Liste des projets
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM typology_projects ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération projets typologie: {str(e)}")
            return []

    def get_typology_project(self, project_id):
        """
        Récupérer un projet de typologie spécifique
        
        Args:
            project_id (int): ID du projet
            
        Returns:
            dict: Données du projet
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM typology_projects WHERE id = ?", (project_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Erreur récupération projet {project_id}: {str(e)}")
            return None

    def update_typology_project(self, project_id, name=None, description=None):
        """
        Mettre à jour un projet de typologie
        
        Args:
            project_id (int): ID du projet
            name (str): Nouveau nom
            description (str): Nouvelle description
            
        Returns:
            bool: True si succès
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if not updates:
                return True
                
            updates.append("updated_at = ?")
            params.append(now)
            params.append(project_id)
            
            query = f"UPDATE typology_projects SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.conn.commit()
            
            logger.info(f"Projet {project_id} mis à jour")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour projet {project_id}: {str(e)}")
            return False
        
    def update_typology_root(self, root_id, name=None, description=None):
            """Mettre à jour une racine"""
            try:
                cursor = self.conn.cursor()
                now = datetime.now().isoformat()
                
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                
                if not updates:
                    return True
                    
                updates.append("updated_at = ?")
                params.append(now)
                params.append(root_id)
                
                query = f"UPDATE typology_roots SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                self.conn.commit()
                return True
                
            except Exception as e:
                logger.error(f"Erreur mise à jour racine {root_id}: {str(e)}")
                return False

    def delete_typology_root(self, root_id):
            """Supprimer une racine"""
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM typology_roots WHERE id = ?", (root_id,))
                self.conn.commit()
                return True
                
            except Exception as e:
                logger.error(f"Erreur suppression racine {root_id}: {str(e)}")
                return False
        
    def update_typology_cluster(self, cluster_id, name=None, description=None):
        """Mettre à jour un cluster"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if not updates:
                return True
                
            updates.append("updated_at = ?")
            params.append(now)
            params.append(cluster_id)
            
            query = f"UPDATE typology_clusters SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour cluster {cluster_id}: {str(e)}")
            return False

    def delete_typology_cluster(self, cluster_id):
        """Supprimer un cluster"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM typology_clusters WHERE id = ?", (cluster_id,))
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression cluster {cluster_id}: {str(e)}")
            return False

    def update_typology_parent(self, parent_id, name=None, description=None):
        """Mettre à jour un parent"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if not updates:
                return True
                
            updates.append("updated_at = ?")
            params.append(now)
            params.append(parent_id)
            
            query = f"UPDATE typology_parents SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour parent {parent_id}: {str(e)}")
            return False

    def delete_typology_parent(self, parent_id):
        """Supprimer un parent"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM typology_parents WHERE id = ?", (parent_id,))
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression parent {parent_id}: {str(e)}")
            return False

    def delete_typology_project(self, project_id):
        """
        Supprimer un projet de typologie et toutes ses données associées
        
        Args:
            project_id (int): ID du projet
            
        Returns:
            bool: True si succès
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM typology_projects WHERE id = ?", (project_id,))
            self.conn.commit()
            
            logger.info(f"Projet {project_id} supprimé")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression projet {project_id}: {str(e)}")
            return False

    # Méthodes similaires pour les typologies, clusters, racines, parents, enfants...

    def update_typology_child(self, child_id, name=None, description=None):
        """Mettre à jour un enfant"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if not updates:
                return True
                
            updates.append("updated_at = ?")
            params.append(now)
            params.append(child_id)
            
            query = f"UPDATE typology_children SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour enfant {child_id}: {str(e)}")
            return False

    def delete_typology_child(self, child_id):
        """Supprimer un enfant"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM typology_children WHERE id = ?", (child_id,))
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression enfant {child_id}: {str(e)}")
            return False

    def create_context_typology(self, project_id, name, description=""):
        """Créer une nouvelle typologie de contexte"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO context_typologies (project_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, name, description, now, now)
            )
            
            self.conn.commit()
            typology_id = cursor.lastrowid
            logger.info(f"Typologie '{name}' créée avec ID: {typology_id}")
            return typology_id
            
        except sqlite3.IntegrityError:
            logger.error(f"Une typologie avec le nom '{name}' existe déjà dans ce projet")
            raise DatabaseError(f"Une typologie avec le nom '{name}' existe déjà dans ce projet")
        except Exception as e:
            logger.error(f"Erreur création typologie '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création de la typologie: {str(e)}")

    def get_typologies_by_project(self, project_id):
        """Récupérer toutes les typologies d'un projet"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM context_typologies WHERE project_id = ? ORDER BY name",
                (project_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération typologies projet {project_id}: {str(e)}")
            return []

    def create_typology_cluster(self, typology_id, name, description=""):
        """Créer un cluster dans une typologie"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO typology_clusters (typology_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (typology_id, name, description, now, now)
            )
            
            self.conn.commit()
            cluster_id = cursor.lastrowid
            logger.info(f"Cluster '{name}' créé avec ID: {cluster_id}")
            return cluster_id
            
        except Exception as e:
            logger.error(f"Erreur création cluster '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création du cluster: {str(e)}")

    def get_clusters_by_typology(self, typology_id):
        """Récupérer tous les clusters d'une typologie"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM typology_clusters WHERE typology_id = ? ORDER BY name",
                (typology_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération clusters typologie {typology_id}: {str(e)}")
            return []

    # Méthodes similaires pour roots, parents, children...

    def create_typology_root(self, cluster_id, name, description=""):
        """Créer une racine dans un cluster"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO typology_roots (cluster_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cluster_id, name, description, now, now)
            )
            
            self.conn.commit()
            root_id = cursor.lastrowid
            return root_id
            
        except Exception as e:
            logger.error(f"Erreur création racine '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création de la racine: {str(e)}")

    def get_roots_by_cluster(self, cluster_id):
        """Récupérer toutes les racines d'un cluster"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM typology_roots WHERE cluster_id = ? ORDER BY name",
                (cluster_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération racines cluster {cluster_id}: {str(e)}")
            return []

    def create_typology_parent(self, root_id, name, description=""):
        """Créer un parent dans une racine"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO typology_parents (root_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (root_id, name, description, now, now)
            )
            
            self.conn.commit()
            parent_id = cursor.lastrowid
            return parent_id
            
        except Exception as e:
            logger.error(f"Erreur création parent '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création du parent: {str(e)}")

    def get_parents_by_root(self, root_id):
        """Récupérer tous les parents d'une racine"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM typology_parents WHERE root_id = ? ORDER BY name",
                (root_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération parents root {root_id}: {str(e)}")
            return []

    def create_typology_child(self, parent_id, name, description=""):
        """Créer un enfant dans un parent"""
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO typology_children (parent_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (parent_id, name, description, now, now)
            )
            
            self.conn.commit()
            child_id = cursor.lastrowid
            return child_id
            
        except Exception as e:
            logger.error(f"Erreur création enfant '{name}': {str(e)}")
            raise DatabaseError(f"Échec de la création de l'enfant: {str(e)}")

    def get_children_by_parent(self, parent_id):
        """Récupérer tous les enfants d'un parent"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM typology_children WHERE parent_id = ? ORDER BY name",
                (parent_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération enfants parent {parent_id}: {str(e)}")
            return []

    def get_complete_typology_structure(self, typology_id):
        """
        Récupérer la structure complète d'une typologie avec tous les niveaux hiérarchiques
        
        Args:
            typology_id (int): ID de la typologie
            
        Returns:
            dict: Structure complète de la typologie
        """
        try:
            # Récupérer la typologie de base
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM context_typologies WHERE id = ?", (typology_id,))
            typology = dict(cursor.fetchone())
            
            # Récupérer les clusters
            clusters = []
            cursor.execute("SELECT * FROM typology_clusters WHERE typology_id = ?", (typology_id,))
            for cluster_row in cursor.fetchall():
                cluster = dict(cluster_row)
                
                # Récupérer les racines pour ce cluster
                roots = []
                cursor.execute("SELECT * FROM typology_roots WHERE cluster_id = ?", (cluster['id'],))
                for root_row in cursor.fetchall():
                    root = dict(root_row)
                    
                    # Récupérer les parents pour cette racine
                    parents = []
                    cursor.execute("SELECT * FROM typology_parents WHERE root_id = ?", (root['id'],))
                    for parent_row in cursor.fetchall():
                        parent = dict(parent_row)
                        
                        # Récupérer les enfants pour ce parent
                        children = []
                        cursor.execute("SELECT * FROM typology_children WHERE parent_id = ?", (parent['id'],))
                        for child_row in cursor.fetchall():
                            children.append(dict(child_row))
                        
                        parent['children'] = children
                        parents.append(parent)
                    
                    root['parents'] = parents
                    roots.append(root)
                
                cluster['roots'] = roots
                clusters.append(cluster)
            
            typology['clusters'] = clusters
            return typology
            
        except Exception as e:
            logger.error(f"Erreur récupération structure typologie {typology_id}: {str(e)}")
            return None

    def save_typology_statistics(self, typology_id, statistics_data):
        """
        Sauvegarder les statistiques pour une typologie
        
        Args:
            typology_id (int): ID de la typologie
            statistics_data (list): Liste des données statistiques
        """
        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()
            
            # Supprimer les anciennes statistiques
            cursor.execute("DELETE FROM typology_statistics WHERE typology_id = ?", (typology_id,))
            
            # Insérer les nouvelles statistiques
            for stat in statistics_data:
                cursor.execute(
                    """
                    INSERT INTO typology_statistics 
                    (typology_id, cluster_name, root_name, parent_name, batch_name, examples_count, percentage, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        typology_id,
                        stat.get('cluster'),
                        stat.get('root'),
                        stat.get('parent'),
                        stat.get('name'),
                        stat.get('examples', 0),
                        stat.get('percentage', 0.0),
                        now,
                        now
                    )
                )
            
            self.conn.commit()
            logger.info(f"Statistiques sauvegardées pour typologie {typology_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde statistiques typologie {typology_id}: {str(e)}")
            return False

    def get_typology_statistics(self, typology_id):
        """
        Récupérer les statistiques d'une typologie
        
        Args:
            typology_id (int): ID de la typologie
            
        Returns:
            list: Liste des statistiques
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM typology_statistics WHERE typology_id = ? ORDER BY batch_name",
                (typology_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération statistiques typologie {typology_id}: {str(e)}")
            return []