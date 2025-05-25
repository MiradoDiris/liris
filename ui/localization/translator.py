#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/localization/translator.py
Gestionnaire de traductions pour l'application Liris
"""

import json
import os
from PyQt5 import QtCore


class Translator:
    """Gestionnaire de traductions pour l'application"""

    DEFAULT_LANGUAGE = "fr"
    TRANSLATIONS_DIR = os.path.join("ui", "localization", "translations")

    def __init__(self):
        self.current_language = self.DEFAULT_LANGUAGE
        self.translations = {}
        self.available_languages = {}
        self._load_languages()
        self._load_translation(self.DEFAULT_LANGUAGE)

    def _load_languages(self):
        """Charge la liste des langues disponibles"""
        # Scanner le dossier translations
        if os.path.exists(self.TRANSLATIONS_DIR):
            for file in os.listdir(self.TRANSLATIONS_DIR):
                if file.endswith('.json'):
                    lang_code = file.replace('.json', '')
                    # Essayer de charger le nom de la langue depuis le fichier
                    try:
                        with open(os.path.join(self.TRANSLATIONS_DIR, file), 'r',
                                  encoding='utf-8') as f:
                            data = json.load(f)
                            self.available_languages[lang_code] = data.get('_language_name', lang_code)
                    except Exception as e:
                        print(f"Erreur lors du chargement des métadonnées de {lang_code}: {e}")
                        self.available_languages[lang_code] = lang_code

    def _load_translation(self, language_code):
        """Charge un fichier de traduction"""
        file_path = os.path.join(self.TRANSLATIONS_DIR, f"{language_code}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                    self.current_language = language_code
                    print(f"Traductions chargées pour la langue: {language_code}")
                    return True
            except Exception as e:
                print(f"Erreur lors du chargement de {language_code}: {e}")
                return False
        else:
            print(f"Fichier de traduction non trouvé: {file_path}")
        return False

    def set_language(self, language_code):
        """Change la langue courante"""
        if language_code in self.available_languages:
            if self._load_translation(language_code):
                print(f"Langue changée vers: {language_code}")
                return True
        print(f"Impossible de changer vers la langue: {language_code}")
        return False

    def translate(self, key, **kwargs):
        """
        Traduit une clé avec des paramètres optionnels

        Args:
            key (str): Clé de traduction (peut utiliser la notation point pour les objets imbriqués)
            **kwargs: Paramètres pour le formatage de la chaîne

        Returns:
            str: Texte traduit ou clé originale si non trouvée
        """
        if not key:
            return ""

        parts = key.split('.')
        text = self.translations

        # Navigation dans les objets imbriqués
        try:
            for part in parts:
                if isinstance(text, dict) and part in text:
                    text = text[part]
                else:
                    # Si on ne trouve pas la clé, retourner la clé originale
                    return key
        except (KeyError, TypeError):
            return key

        # S'assurer que le résultat final est une chaîne
        if not isinstance(text, str):
            # Si on a trouvé un dictionnaire ou autre chose qu'une chaîne,
            # retourner la clé originale
            print(f"Attention: La clé '{key}' ne pointe pas vers une chaîne mais vers {type(text)}")
            return key

        # Appliquer le formatage si des paramètres sont fournis
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, TypeError) as e:
                print(f"Erreur de formatage pour la clé '{key}': {e}")
                return text

        return text

    def get_available_languages(self):
        """Retourne la liste des langues disponibles"""
        return self.available_languages

    def get_current_language(self):
        """Retourne la langue courante"""
        return self.current_language

    def has_translation(self, key):
        """Vérifie si une traduction existe pour une clé donnée"""
        parts = key.split('.')
        text = self.translations

        try:
            for part in parts:
                if isinstance(text, dict) and part in text:
                    text = text[part]
                else:
                    return False
            return isinstance(text, str)
        except (KeyError, TypeError):
            return False

    def get_all_translations(self):
        """Retourne toutes les traductions de la langue courante"""
        return self.translations.copy()

    def reload_translations(self):
        """Recharge les traductions de la langue courante"""
        return self._load_translation(self.current_language)


# Instance globale du traducteur
translator = Translator()


# Fonction raccourci pour les traductions
def tr(key, **kwargs):
    """
    Fonction raccourci pour les traductions

    Args:
        key (str): Clé de traduction
        **kwargs: Paramètres pour le formatage

    Returns:
        str: Texte traduit
    """
    return translator.translate(key, **kwargs)


# Fonction pour changer la langue globalement
def set_language(language_code):
    """Change la langue de l'application"""
    return translator.set_language(language_code)


# Fonction pour obtenir les langues disponibles
def get_available_languages():
    """Retourne les langues disponibles"""
    return translator.get_available_languages()


# Fonction pour obtenir la langue courante
def get_current_language():
    """Retourne la langue courante"""
    return translator.get_current_language()