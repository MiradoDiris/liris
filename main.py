#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/main.py
Point d'entrée de l'application
"""

import sys
import os
import traceback
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import QSettings

from ui.main_window import MainWindow
from ui.localization.translator import translator, tr
from ui.widgets.language_selector import LanguageSelector
from utils.logger import logger


def setup_application_paths():
    """Configure les chemins de l'application"""
    # S'assurer que le dossier courant est le dossier de l'application
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    # Ajouter le dossier racine au PYTHONPATH
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


def main():
    print("\n=== DÉMARRAGE DE L'APPLICATION ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Répertoire actuel: {os.getcwd()}")

    # Configurer les chemins
    setup_application_paths()

    try:
        # Créer l'application
        print("1. Création de QApplication...")
        app = QtWidgets.QApplication(sys.argv)
        print("   ✓ QApplication créée")

        # Gérer la sélection de langue
        print("2. Sélection de la langue...")
        settings = QSettings("Liris", "IACollaborative")
        saved_language = settings.value("language", None)

        # IMPORTANT: Charger la langue AVANT de créer MainWindow
        if saved_language and saved_language in translator.get_available_languages():
            success = translator.set_language(saved_language)
            if success:
                print(f"   ✓ Langue restaurée: {saved_language}")
            else:
                print(f"   ✗ Erreur lors du chargement de {saved_language}")
                translator.set_language(translator.DEFAULT_LANGUAGE)
        else:
            # Première utilisation ou langue non disponible, montrer le sélecteur
            print("   → Première utilisation, affichage du sélecteur de langue")
            selector = LanguageSelector()

            # Trouver l'index du français par défaut
            for i in range(selector.language_combo.count()):
                if selector.language_combo.itemData(i) == "fr":
                    selector.language_combo.setCurrentIndex(i)
                    break

            if selector.exec_() == QtWidgets.QDialog.Accepted:
                selected_language = selector.get_selected_language()
                success = translator.set_language(selected_language)
                if success:
                    settings.setValue("language", selected_language)
                    print(f"   ✓ Langue sélectionnée: {selected_language}")
                else:
                    print(f"   ✗ Erreur lors du chargement de {selected_language}")
                    translator.set_language(translator.DEFAULT_LANGUAGE)
            else:
                # Si l'utilisateur annule, utiliser la langue par défaut
                translator.set_language(translator.DEFAULT_LANGUAGE)
                settings.setValue("language", translator.DEFAULT_LANGUAGE)
                print(f"   ✓ Langue par défaut utilisée: {translator.DEFAULT_LANGUAGE}")

        # Créer la fenêtre principale
        print("3. Création de la fenêtre principale...")
        window = MainWindow()
        print("   ✓ Fenêtre principale créée")

        # Afficher la fenêtre
        print("4. Affichage de la fenêtre...")
        window.show()
        print("   ✓ Fenêtre affichée")

        # Démarrer la boucle d'événements
        print("5. Démarrage de la boucle d'événements...")
        print("=== APPLICATION EN COURS D'EXÉCUTION ===")
        sys.exit(app.exec_())

    except Exception as e:
        print(f"\n=== ERREUR CRITIQUE ===")
        print(f"Erreur: {str(e)}")
        traceback.print_exc()
        logger.critical(f"Erreur critique lors du démarrage: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()