import logging
import os
from datetime import datetime


class Logger:
    """
    Gestionnaire de journalisation pour l'application
    """

    def __init__(self, name="ai_automation", log_level=logging.INFO):
        """
        Initialise le logger avec le niveau spécifié

        Args:
            name (str): Nom du logger
            log_level (int): Niveau de journalisation (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        # Création du répertoire de logs s'il n'existe pas
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)

        # Formateur pour les journaux
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Handler pour le fichier
        log_file = os.path.join(log_dir, f"ai_automation_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def debug(self, message, *args, **kwargs):
        """Enregistre un message de niveau DEBUG"""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        """Enregistre un message de niveau INFO"""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        """Enregistre un message de niveau WARNING"""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """Enregistre un message de niveau ERROR"""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        """Enregistre un message de niveau CRITICAL"""
        self.logger.critical(message, *args, **kwargs)


# Instance globale du logger
logger = Logger()