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
            self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                        "data", "liris.db")
        else:
            self.db_path = db_path

        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        logger.info(f"Initialisation de la base de données: {self.db_path}")

        # Établir la connexion
        self.connect()

        # Initialiser les tables
        self._init_tables()

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

            # Table des plateformes et leurs configurations (NOUVELLE)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS platforms
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               name
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               profile_data
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TEXT
                               NOT
                               NULL,
                               updated_at
                               TEXT
                               NOT
                               NULL
                           )
                           ''')

            # Table des sessions d'IA
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS ai_sessions
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               platform_name
                               TEXT
                               NOT
                               NULL,
                               session_date
                               TEXT
                               NOT
                               NULL,
                               prompt_count
                               INTEGER
                               DEFAULT
                               0,
                               token_count
                               INTEGER
                               DEFAULT
                               0,
                               status
                               TEXT
                               DEFAULT
                               'active'
                           )
                           ''')

            # Table des prompts
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS prompts
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               session_id
                               INTEGER,
                               timestamp
                               TEXT
                               NOT
                               NULL,
                               content
                               TEXT
                               NOT
                               NULL,
                               token_count
                               INTEGER
                               DEFAULT
                               0,
                               operation_type
                               TEXT
                               NOT
                               NULL,
                               FOREIGN
                               KEY
                           (
                               session_id
                           ) REFERENCES ai_sessions
                           (
                               id
                           )
                               )
                           ''')

            # Table des réponses
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS responses
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               prompt_id
                               INTEGER,
                               timestamp
                               TEXT
                               NOT
                               NULL,
                               content
                               TEXT
                               NOT
                               NULL,
                               status
                               TEXT
                               DEFAULT
                               'success',
                               FOREIGN
                               KEY
                           (
                               prompt_id
                           ) REFERENCES prompts
                           (
                               id
                           )
                               )
                           ''')

            # Table des datasets générés
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS datasets
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               name
                               TEXT
                               NOT
                               NULL,
                               creation_date
                               TEXT
                               NOT
                               NULL,
                               type
                               TEXT
                               NOT
                               NULL,
                               format
                               TEXT
                               NOT
                               NULL,
                               item_count
                               INTEGER
                               DEFAULT
                               0,
                               filepath
                               TEXT
                               NOT
                               NULL
                           )
                           ''')

            # Table des sessions de brainstorming
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS brainstorming_sessions
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               name
                               TEXT
                               NOT
                               NULL,
                               creation_date
                               TEXT
                               NOT
                               NULL,
                               ai_platforms
                               TEXT
                               NOT
                               NULL,
                               context
                               TEXT
                               NOT
                               NULL,
                               status
                               TEXT
                               DEFAULT
                               'in_progress'
                           )
                           ''')

            # Table des résultats de brainstorming
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS brainstorming_results
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               session_id
                               INTEGER,
                               platform_name
                               TEXT
                               NOT
                               NULL,
                               solution
                               TEXT
                               NOT
                               NULL,
                               evaluations
                               TEXT,
                               final_score
                               INTEGER,
                               FOREIGN
                               KEY
                           (
                               session_id
                           ) REFERENCES brainstorming_sessions
                           (
                               id
                           )
                               )
                           ''')

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
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                logger.debug("Connexion à la base de données fermée")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la connexion: {str(e)}")
            return False

    # =====================================================
    # NOUVELLES MÉTHODES POUR GESTION DES PLATEFORMES
    # =====================================================

    def save_platform(self, platform_name, profile_data):
        """
        Sauvegarde un profil de plateforme en base de données

        Args:
            platform_name (str): Nom de la plateforme
            profile_data (dict): Données du profil à sauvegarder

        Returns:
            bool: True si sauvegarde réussie, False sinon
        """
        try:
            logger.debug(f"Sauvegarde plateforme {platform_name} en base de données")

            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            # Convertir le profil en JSON
            profile_json = json.dumps(profile_data, ensure_ascii=False, indent=2)

            # Vérifier si la plateforme existe déjà
            cursor.execute('SELECT id FROM platforms WHERE name = ?', (platform_name,))
            existing = cursor.fetchone()

            if existing:
                # Mettre à jour
                cursor.execute('''
                               UPDATE platforms
                               SET profile_data = ?,
                                   updated_at   = ?
                               WHERE name = ?
                               ''', (profile_json, now, platform_name))
                logger.info(f"Profil {platform_name} mis à jour en base de données")
            else:
                # Créer nouveau
                cursor.execute('''
                               INSERT INTO platforms (name, profile_data, created_at, updated_at)
                               VALUES (?, ?, ?, ?)
                               ''', (platform_name, profile_json, now, now))
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
        Récupère un profil de plateforme depuis la base de données

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Profil de la plateforme ou None si non trouvé
        """
        try:
            logger.debug(f"Récupération plateforme {platform_name} depuis la base de données")

            cursor = self.conn.cursor()

            cursor.execute('SELECT profile_data FROM platforms WHERE name = ?', (platform_name,))
            result = cursor.fetchone()

            if result:
                # Décoder le JSON
                profile_data = json.loads(result['profile_data'])
                logger.debug(
                    f"Profil {platform_name} récupéré depuis la base (taille: {len(str(profile_data))} caractères)")

                # Validation des patterns d'extraction
                self._validate_extraction_patterns(platform_name, profile_data)

                return profile_data
            else:
                logger.debug(f"Profil {platform_name} non trouvé en base de données")
                return None

        except Exception as e:
            logger.error(f"Erreur récupération plateforme {platform_name}: {str(e)}")
            return None

    def _validate_extraction_patterns(self, platform_name, profile_data):
        """
        Valide et optimise les patterns d'extraction selon la plateforme

        Args:
            platform_name (str): Nom de la plateforme
            profile_data (dict): Données du profil
        """
        try:
            extraction_config = profile_data.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})

            if not response_area:
                return

            # Analyser les patterns selon la plateforme
            html_sample = response_area.get('complete_html', '')

            if platform_name.lower() == 'chatgpt' and html_sample:
                # ChatGPT utilise data-start et data-end
                import re
                data_patterns = re.findall(r'data-start="(\d+)" data-end="(\d+)"', html_sample)
                if data_patterns:
                    logger.debug(f"ChatGPT: {len(data_patterns)} segments data-start/data-end détectés")
                    response_area['platform_patterns'] = {
                        'type': 'data_attributes',
                        'start_attr': 'data-start',
                        'end_attr': 'data-end',
                        'segments_count': len(data_patterns)
                    }

            elif platform_name.lower() == 'claude' and html_sample:
                # Claude utilise des classes CSS spécifiques
                import re
                css_classes = re.findall(r'class="([^"]*whitespace-normal[^"]*)"', html_sample)
                if css_classes:
                    logger.debug(f"Claude: {len(css_classes)} éléments whitespace-normal détectés")
                    response_area['platform_patterns'] = {
                        'type': 'css_classes',
                        'main_class': 'whitespace-normal',
                        'break_words': 'break-words' in html_sample,
                        'classes_count': len(css_classes)
                    }

            elif html_sample:
                # Autres plateformes - analyse générique
                import re

                # Détecter les patterns communs
                patterns = {
                    'divs': len(re.findall(r'<div[^>]*>', html_sample)),
                    'paragraphs': len(re.findall(r'<p[^>]*>', html_sample)),
                    'spans': len(re.findall(r'<span[^>]*>', html_sample)),
                    'has_ids': bool(re.search(r'id="[^"]*"', html_sample)),
                    'has_data_attrs': bool(re.search(r'data-[^=]*="[^"]*"', html_sample)),
                    'has_classes': bool(re.search(r'class="[^"]*"', html_sample))
                }

                logger.debug(f"{platform_name}: Patterns génériques détectés: {patterns}")
                response_area['platform_patterns'] = {
                    'type': 'generic',
                    **patterns
                }

        except Exception as e:
            logger.error(f"Erreur validation patterns pour {platform_name}: {str(e)}")

    def get_platform_extraction_config(self, platform_name):
        """
        Récupère spécifiquement la configuration d'extraction d'une plateforme

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Configuration d'extraction ou None
        """
        try:
            profile = self.get_platform(platform_name)
            if profile:
                extraction_config = profile.get('extraction_config', {})
                response_area = extraction_config.get('response_area', {})

                if response_area:
                    logger.debug(f"Configuration d'extraction trouvée pour {platform_name}")
                    return response_area

            logger.debug(f"Pas de configuration d'extraction pour {platform_name}")
            return None

        except Exception as e:
            logger.error(f"Erreur récupération config extraction {platform_name}: {str(e)}")
            return None

    def update_platform_extraction(self, platform_name, extraction_config):
        """
        Met à jour uniquement la configuration d'extraction d'une plateforme

        Args:
            platform_name (str): Nom de la plateforme
            extraction_config (dict): Nouvelle configuration d'extraction

        Returns:
            bool: True si mise à jour réussie
        """
        try:
            # Récupérer le profil existant
            profile = self.get_platform(platform_name)
            if not profile:
                logger.error(f"Profil {platform_name} non trouvé pour mise à jour extraction")
                return False

            # Mettre à jour seulement la section extraction
            if 'extraction_config' not in profile:
                profile['extraction_config'] = {}

            profile['extraction_config']['response_area'] = extraction_config

            # Sauvegarder le profil complet
            success = self.save_platform(platform_name, profile)

            if success:
                logger.info(f"Configuration d'extraction mise à jour pour {platform_name}")

            return success

        except Exception as e:
            logger.error(f"Erreur mise à jour extraction {platform_name}: {str(e)}")
            return False

    def list_platforms(self):
        """
        Liste toutes les plateformes enregistrées

        Returns:
            list: Liste des noms de plateformes
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name, updated_at FROM platforms ORDER BY updated_at DESC')
            results = cursor.fetchall()

            platforms = [{'name': row['name'], 'updated_at': row['updated_at']} for row in results]
            logger.debug(f"{len(platforms)} plateformes trouvées en base")

            return platforms

        except Exception as e:
            logger.error(f"Erreur listage plateformes: {str(e)}")
            return []

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
            cursor.execute('DELETE FROM platforms WHERE name = ?', (platform_name,))

            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Plateforme {platform_name} supprimée de la base")
                return True
            else:
                logger.warning(f"Plateforme {platform_name} non trouvée pour suppression")
                return False

        except Exception as e:
            logger.error(f"Erreur suppression plateforme {platform_name}: {str(e)}")
            return False

    # =====================================================
    # MÉTHODES EXISTANTES (SESSIONS, PROMPTS, ETC.)
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

            cursor.execute('''
                           INSERT INTO ai_sessions (platform_name, session_date, status)
                           VALUES (?, ?, ?)
                           ''', (platform_name, now, 'active'))

            self.conn.commit()
            session_id = cursor.lastrowid

            logger.debug(f"Nouvelle session créée pour {platform_name}, ID: {session_id}")
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

            cursor.execute('''
                           INSERT INTO prompts (session_id, timestamp, content, token_count, operation_type)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (session_id, now, content, token_count, operation_type))

            # Mettre à jour les compteurs de la session
            cursor.execute('''
                           UPDATE ai_sessions
                           SET prompt_count = prompt_count + 1,
                               token_count  = token_count + ?
                           WHERE id = ?
                           ''', (token_count, session_id))

            self.conn.commit()
            prompt_id = cursor.lastrowid

            logger.debug(f"Prompt enregistré, ID: {prompt_id}")
            return prompt_id

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du prompt: {str(e)}")
            raise DatabaseError(f"Échec de l'enregistrement du prompt: {str(e)}")

    def record_response(self, prompt_id, content, status='success'):
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

            cursor.execute('''
                           INSERT INTO responses (prompt_id, timestamp, content, status)
                           VALUES (?, ?, ?, ?)
                           ''', (prompt_id, now, content, status))

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

            cursor.execute('''
                           INSERT INTO datasets (name, creation_date, type, format, item_count, filepath)
                           VALUES (?, ?, ?, ?, ?, ?)
                           ''', (name, now, dataset_type, format, item_count, filepath))

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

            cursor.execute('''
                           INSERT INTO brainstorming_sessions (name, creation_date, ai_platforms, context, status)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (name, now, platforms_json, context, 'in_progress'))

            self.conn.commit()
            session_id = cursor.lastrowid

            logger.debug(f"Session de brainstorming créée, ID: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de session de brainstorming: {str(e)}")
            raise DatabaseError(f"Échec de la création de session de brainstorming: {str(e)}")

    def record_brainstorming_result(self, session_id, platform_name, solution, evaluations=None, final_score=None):
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

            cursor.execute('''
                           INSERT INTO brainstorming_results (session_id, platform_name, solution, evaluations, final_score)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (session_id, platform_name, solution, evaluations_json, final_score))

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

            cursor.execute('''
                           UPDATE brainstorming_sessions
                           SET status = ?
                           WHERE id = ?
                           ''', (status, session_id))

            self.conn.commit()

            logger.debug(f"Statut de la session {session_id} mis à jour: {status}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {str(e)}")
            raise DatabaseError(f"Échec de la mise à jour du statut: {str(e)}")