import os
import json
from utils.logger import logger
from utils.exceptions import ConfigurationError


class ConfigProvider:
    """
    Fournisseur de configuration pour l'application
    """

    def __init__(self, config_dir=None):
        """
        Initialise le fournisseur de configuration

        Args:
            config_dir (str, optional): Répertoire de configuration
        """
        if config_dir is None:
            self.config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        else:
            self.config_dir = config_dir

        self.profiles_dir = os.path.join(self.config_dir, "profiles")
        self._ensure_directories()

        # Cache des profils
        self._profiles = None

        logger.info(f"Configuration chargée depuis: {self.config_dir}")

    def _ensure_directories(self):
        """Crée les répertoires nécessaires s'ils n'existent pas"""
        os.makedirs(self.profiles_dir, exist_ok=True)

    def get_profiles(self, reload=False):
        """
        Récupère les profils d'IA

        Args:
            reload (bool): Force le rechargement depuis le disque

        Returns:
            dict: Profils d'IA indexés par nom
        """
        if self._profiles is None or reload:
            self._profiles = {}

            try:
                for filename in os.listdir(self.profiles_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(self.profiles_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                            name = profile.get('name')
                            if name:
                                self._profiles[name] = profile
                            else:
                                logger.warning(f"Profil sans nom: {filename}")

                logger.debug(f"Chargé {len(self._profiles)} profils")
            except Exception as e:
                logger.error(f"Erreur lors du chargement des profils: {str(e)}")
                raise ConfigurationError(f"Échec du chargement des profils: {str(e)}")

        return self._profiles

    def get_database_config(self):
        """
        Récupère la configuration de la base de données

        Returns:
            dict: Configuration de la base de données
        """
        return {
            "path": os.path.join("data", "liris.db")  # Retourne un string
        }

    def get_scheduler_config(self):
        """
        Récupère la configuration du scheduler

        Returns:
            dict: Configuration du scheduler
        """
        return {
            'config_provider': self
        }

    def get_export_config(self):
        """
        Récupère la configuration de l'exportation

        Returns:
            dict: Configuration de l'exportation
        """
        export_dir = os.path.join(os.path.dirname(self.config_dir), "exports")
        os.makedirs(export_dir, exist_ok=True)

        return {
            'export_dir': export_dir,
            'formats': ['json', 'csv', 'xlsx']
        }

    def get_templates_dir(self):
        """
        Récupère le répertoire des templates

        Returns:
            str: Chemin du répertoire des templates
        """
        return os.path.join(self.config_dir, "templates")

    def save_profile(self, name, profile):
        """
        Sauvegarde un profil d'IA

        Args:
            name (str): Nom du profil
            profile (dict): Configuration du profil

        Returns:
            bool: True si la sauvegarde est réussie
        """
        try:
            filepath = os.path.join(self.profiles_dir, f"{name}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

            # Mettre à jour le cache
            if self._profiles is not None:
                self._profiles[name] = profile

            logger.info(f"Profil {name} sauvegardé")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du profil {name}: {str(e)}")
            return False