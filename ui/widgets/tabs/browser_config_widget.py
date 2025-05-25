#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/browser_config_widget.py
"""

import os
import json
import traceback
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle


class BrowserConfigWidget(QtWidgets.QWidget):
    """Widget de configuration des navigateurs pour les plateformes d'IA"""

    # Signaux
    browser_saved = pyqtSignal(str, dict)  # Nom du navigateur, configuration
    browser_deleted = pyqtSignal(str)  # Nom du navigateur
    browser_used = pyqtSignal(str, str)  # Plateforme, navigateur
    elements_detected = pyqtSignal(str, dict)  # Plateforme, positions

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration des navigateurs
        """
        super().__init__(parent)

        # Debug
        print("BrowserConfigWidget: Initialisation...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.saved_browsers = {}
        self.profiles = {}

        try:
            self._init_ui()
            self._load_saved_browsers()
            print("BrowserConfigWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de BrowserConfigWidget: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """Configure l'interface utilisateur du widget de navigateur"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Explication
        explanation = QtWidgets.QLabel(
            "Ce module permet de configurer le navigateur utilisé pour chaque plateforme d'IA.\n"
            "Commencez par sélectionner votre plateforme, puis configurez le navigateur et testez la connexion."
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)

        # Layout en 2 colonnes
        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(20)

        # === COLONNE GAUCHE : Contrôles ===
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)

        # === Section 1: Sélection de la plateforme ===
        platform_group = QtWidgets.QGroupBox("Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        # Combo de sélection des plateformes
        self.browser_platform_combo = QtWidgets.QComboBox()
        self.browser_platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.browser_platform_combo.currentIndexChanged.connect(self._on_browser_platform_selected)
        platform_layout.addWidget(self.browser_platform_combo)

        left_column.addWidget(platform_group)

        # === Section Actions ===
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(300)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        # Bouton de test principal
        self.test_browser_button = QtWidgets.QPushButton("◉ Tester le navigateur")
        self.test_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_browser_button.clicked.connect(self._on_test_browser)
        actions_layout.addWidget(self.test_browser_button)

        # Statut de la détection
        self.detection_status = QtWidgets.QLabel("Pas de test effectué")
        self.detection_status.setAlignment(Qt.AlignCenter)
        self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        actions_layout.addWidget(self.detection_status)

        # Options de test
        self.remember_positions_check = QtWidgets.QCheckBox("Mémoriser les positions détectées")
        self.remember_positions_check.setChecked(True)
        actions_layout.addWidget(self.remember_positions_check)

        self.force_detect_check = QtWidgets.QCheckBox("Forcer la détection à chaque fois")
        actions_layout.addWidget(self.force_detect_check)

        left_column.addWidget(actions_group)

        # === Section Navigateurs enregistrés ===
        saved_browsers_group = QtWidgets.QGroupBox("Navigateurs enregistrés")
        saved_browsers_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        saved_browsers_group.setMaximumWidth(300)
        saved_browsers_layout = QtWidgets.QVBoxLayout(saved_browsers_group)

        # Liste des navigateurs enregistrés
        self.saved_browsers_list = QtWidgets.QListWidget()
        self.saved_browsers_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.saved_browsers_list.currentItemChanged.connect(self._on_saved_browser_selected)
        self.saved_browsers_list.setStyleSheet(PlatformConfigStyle.get_small_list_style())
        saved_browsers_layout.addWidget(self.saved_browsers_list)

        # Boutons pour gérer les navigateurs enregistrés
        saved_browsers_buttons = QtWidgets.QHBoxLayout()

        self.edit_browser_button = QtWidgets.QPushButton("Modifier")
        self.edit_browser_button.clicked.connect(self._on_edit_browser)
        self.edit_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        self.delete_browser_button = QtWidgets.QPushButton("Supprimer")
        self.delete_browser_button.clicked.connect(self._on_delete_browser)
        self.delete_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        saved_browsers_buttons.addWidget(self.edit_browser_button)
        saved_browsers_buttons.addWidget(self.delete_browser_button)

        saved_browsers_layout.addLayout(saved_browsers_buttons)

        left_column.addWidget(saved_browsers_group)

        # === Section Sauvegarde ===
        save_group = QtWidgets.QGroupBox("Sauvegarde")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        # Bouton de sauvegarde
        self.save_browser_button = QtWidgets.QPushButton("⬇ Enregistrer la configuration")
        self.save_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_browser_button.clicked.connect(self._save_browser_config)
        save_layout.addWidget(self.save_browser_button)

        left_column.addWidget(save_group)

        # Spacer pour pousser tout vers le haut
        left_column.addStretch()

        # === COLONNE DROITE : Configuration ===
        right_column = QtWidgets.QVBoxLayout()

        # === Section Configuration du navigateur ===
        browser_form_group = QtWidgets.QGroupBox("Configuration du navigateur")
        browser_form_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        browser_form = QtWidgets.QFormLayout(browser_form_group)

        # Nom du navigateur
        self.browser_name_edit = QtWidgets.QLineEdit()
        self.browser_name_edit.setPlaceholderText("Nom de cette configuration (ex: Firefox Personnel)")
        self.browser_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("Nom:", self.browser_name_edit)

        # Type de navigateur
        self.browser_type_combo = QtWidgets.QComboBox()
        self.browser_type_combo.addItems(["Chrome", "Firefox", "Edge", "Safari", "Autre"])
        self.browser_type_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("Type de navigateur:", self.browser_type_combo)

        # Chemin du navigateur
        self.browser_path_edit = QtWidgets.QLineEdit()
        self.browser_path_edit.setPlaceholderText("Chemin vers l'exécutable du navigateur (vide = par défaut)")
        self.browser_path_edit.setStyleSheet(PlatformConfigStyle.get_input_style())

        path_layout = QtWidgets.QHBoxLayout()
        self.browser_path_browse = QtWidgets.QPushButton("...")
        self.browser_path_browse.setMaximumWidth(30)
        self.browser_path_browse.clicked.connect(self._browse_browser_path)
        self.browser_path_browse.setStyleSheet(PlatformConfigStyle.get_button_style())
        path_layout.addWidget(self.browser_path_edit)
        path_layout.addWidget(self.browser_path_browse)
        browser_form.addRow("Chemin:", path_layout)

        # URL de la plateforme
        self.browser_url_edit = QtWidgets.QLineEdit()
        self.browser_url_edit.setPlaceholderText("URL de la plateforme (ex: https://chat.openai.com)")
        self.browser_url_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("URL:", self.browser_url_edit)

        right_column.addWidget(browser_form_group)

        # === Section Options avancées ===
        options_group = QtWidgets.QGroupBox("Options de navigateur")
        options_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        options_layout = QtWidgets.QVBoxLayout(options_group)

        # Option maximiser fenêtre
        self.maximize_window_check = QtWidgets.QCheckBox("Maximiser la fenêtre (recommandé)")
        self.maximize_window_check.setChecked(True)
        self.maximize_window_check.setToolTip("Maximise la fenêtre du navigateur pour une meilleure détection")
        options_layout.addWidget(self.maximize_window_check)

        # Option mode incognito
        self.incognito_mode_check = QtWidgets.QCheckBox("Mode navigation privée/incognito")
        self.incognito_mode_check.setChecked(False)
        self.incognito_mode_check.setToolTip("Lance le navigateur en mode navigation privée")
        options_layout.addWidget(self.incognito_mode_check)

        # Option désactiver extensions
        self.disable_extensions_check = QtWidgets.QCheckBox("Désactiver les extensions")
        self.disable_extensions_check.setChecked(False)
        self.disable_extensions_check.setToolTip("Lance le navigateur sans les extensions pour éviter les interférences")
        options_layout.addWidget(self.disable_extensions_check)

        right_column.addWidget(options_group)

        # === Section Information sur la détection ===
        info_group = QtWidgets.QGroupBox("Information sur la détection")
        info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        info_layout = QtWidgets.QVBoxLayout(info_group)

        info_text = QtWidgets.QLabel(
            "Le test du navigateur va :\n"
            "1. Ouvrir automatiquement le navigateur sur l'URL spécifiée\n"
            "2. Détecter les éléments d'interface (champ de prompt, boutons, etc.)\n"
            "3. Mémoriser les positions pour un usage futur\n\n"
            "Assurez-vous que l'URL est correcte avant de lancer le test."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #555; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        info_layout.addWidget(info_text)

        right_column.addWidget(info_group)

        # Assembler les colonnes
        columns_layout.addLayout(left_column, 0)  # 0 = pas d'étirement
        columns_layout.addLayout(right_column, 1)  # 1 = étirement pour prendre l'espace restant

        main_layout.addLayout(columns_layout)

        # Note d'aide en bas
        help_note = QtWidgets.QLabel(
            "<b>Workflow:</b> 1▸ Sélectionnez la plateforme → 2▸ Configurez le navigateur → "
            "3▸ Testez la connexion → 4▸ Enregistrez la configuration"
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #074E68; padding: 10px; font-style: italic;")
        help_note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_note)

    def set_profiles(self, profiles):
        """
        Met à jour les profils disponibles dans le widget

        Args:
            profiles (dict): Dictionnaire des profils de plateformes
        """
        self.profiles = profiles
        self._update_platforms_combo()

    def select_platform(self, platform_name):
        """
        Sélectionne une plateforme dans la liste déroulante

        Args:
            platform_name (str): Nom de la plateforme à sélectionner
        """
        index = self.browser_platform_combo.findText(platform_name)
        if index >= 0:
            self.browser_platform_combo.setCurrentIndex(index)

    def should_force_detect(self):
        """
        Indique si la détection doit être forcée à chaque fois

        Returns:
            bool: True si la détection doit être forcée
        """
        return self.force_detect_check.isChecked()

    def should_remember_positions(self):
        """
        Indique si les positions détectées doivent être mémorisées

        Returns:
            bool: True si les positions doivent être mémorisées
        """
        return self.remember_positions_check.isChecked()

    def refresh(self):
        """Actualise les données du widget"""
        self._load_saved_browsers()
        self._update_platforms_combo()

    def _load_saved_browsers(self):
        """Charge les configurations de navigateurs enregistrées"""
        try:
            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            if not os.path.exists(browsers_dir):
                os.makedirs(browsers_dir, exist_ok=True)
                print(f"DEBUG: Répertoire des navigateurs créé: {browsers_dir}")
                return

            self.saved_browsers = {}  # Réinitialiser le dictionnaire

            for filename in os.listdir(browsers_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(browsers_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            browser_config = json.load(f)
                            name = browser_config.get('name', filename.replace('.json', ''))
                            self.saved_browsers[name] = browser_config
                            print(f"DEBUG: Configuration de navigateur chargée: {name}")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement du navigateur {filename}: {str(e)}")
                        print(f"DEBUG: Erreur chargement navigateur {filename}: {str(e)}")

            # Mettre à jour la liste des navigateurs
            self._update_saved_browsers_list()

        except Exception as e:
            logger.error(f"Erreur lors du chargement des navigateurs: {str(e)}")
            print(f"DEBUG: Erreur chargement navigateurs: {str(e)}")

    def _update_saved_browsers_list(self):
        """Met à jour la liste des navigateurs enregistrés"""
        self.saved_browsers_list.clear()
        for name in sorted(self.saved_browsers.keys()):
            self.saved_browsers_list.addItem(name)

    def _update_platforms_combo(self):
        """Met à jour la liste déroulante des plateformes"""
        current_text = self.browser_platform_combo.currentText()

        self.browser_platform_combo.clear()
        self.browser_platform_combo.addItem("-- Sélectionnez une plateforme --")

        for name in sorted(self.profiles.keys()):
            self.browser_platform_combo.addItem(name)

        # Restaurer la sélection précédente si possible
        if current_text:
            index = self.browser_platform_combo.findText(current_text)
            if index >= 0:
                self.browser_platform_combo.setCurrentIndex(index)

    def _browse_browser_path(self):
        """Ouvre un dialogue pour sélectionner le navigateur"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Sélectionner le navigateur",
            "",
            "Exécutables (*.exe);;Tous les fichiers (*.*)"
        )

        if file_path:
            self.browser_path_edit.setText(file_path)

    def _on_browser_platform_selected(self, index):
        """Gère la sélection d'une plateforme dans l'onglet navigateur"""
        if index <= 0:  # L'index 0 correspond à "-- Sélectionnez une plateforme --"
            return

        platform_name = self.browser_platform_combo.currentText()
        print(f"DEBUG: Plateforme sélectionnée dans l'onglet navigateur: {platform_name}")

        # Charger les informations de navigateur actuelles de cette plateforme
        profile = self.profiles.get(platform_name, {})
        browser_info = profile.get('browser', {})

        # Remplir les champs avec les valeurs actuelles
        self.browser_name_edit.setText(f"Navigateur pour {platform_name}")

        browser_type = browser_info.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_info.get('path', ''))
        self.browser_url_edit.setText(browser_info.get('url', ''))
        self.maximize_window_check.setChecked(True)

        # Mettre à jour le statut de détection
        if 'interface_positions' in profile:
            self.detection_status.setText("Positions d'interface mémorisées")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        else:
            self.detection_status.setText("Pas de test effectué")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def _on_saved_browser_selected(self, current, previous):
        """Gère la sélection d'un navigateur enregistré"""
        if not current:
            return

        browser_name = current.text()
        browser_config = self.saved_browsers.get(browser_name, {})

        # Mettre à jour les champs avec la configuration sélectionnée
        self.browser_name_edit.setText(browser_name)

        browser_type = browser_config.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_config.get('path', ''))
        self.browser_url_edit.setText(browser_config.get('url', ''))
        self.maximize_window_check.setChecked(True)

    def _on_edit_browser(self):
        """Charge un navigateur enregistré pour modification"""
        if not self.saved_browsers_list.currentItem():
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun navigateur sélectionné",
                "Veuillez d'abord sélectionner un navigateur."
            )
            return

        browser_name = self.saved_browsers_list.currentItem().text()
        browser_config = self.saved_browsers.get(browser_name, {})

        # Mettre à jour les champs avec la configuration sélectionnée
        self.browser_name_edit.setText(browser_name)

        browser_type = browser_config.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_config.get('path', ''))
        self.browser_url_edit.setText(browser_config.get('url', ''))
        self.maximize_window_check.setChecked(True)  # Toujours maximisé

        QtWidgets.QMessageBox.information(
            self,
            "Navigateur chargé",
            f"La configuration du navigateur '{browser_name}' a été chargée pour modification. Utilisez le bouton 'Tester le navigateur' pour vérifier et enregistrer les modifications."
        )

    def _on_test_browser(self):
        """Teste le navigateur avec détection des éléments"""
        # Vérifier qu'une plateforme est sélectionnée
        platform_index = self.browser_platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Vérifier que le nom est spécifié
        name = self.browser_name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Nom manquant",
                "Veuillez saisir un nom pour cette configuration de navigateur."
            )
            return

        platform_name = self.browser_platform_combo.currentText()

        # Mettre à jour le statut
        self.detection_status.setText("Test en cours...")
        self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

        # Laisser la possibilité à l'UI de se mettre à jour
        QtWidgets.QApplication.processEvents()

        try:
            # Récupérer les informations du navigateur
            browser_type = self.browser_type_combo.currentText()
            browser_path = self.browser_path_edit.text()
            browser_url = self.browser_url_edit.text().strip()

            # Vérifier l'URL
            if not browser_url:
                QtWidgets.QMessageBox.warning(
                    self,
                    "URL manquante",
                    "Veuillez spécifier l'URL du site."
                )
                self.detection_status.setText("Test annulé: URL manquante")
                self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                return

            # Récupérer le profil et mettre à jour
            profile = self.profiles.get(platform_name, {})

            # Créer une configuration temporaire pour le test
            browser_config = {
                "type": browser_type,
                "path": browser_path,
                "url": browser_url,
                "fullscreen": False  # Mode plein écran désactivé
            }

            # Mettre à jour le profil temporairement
            if 'browser' not in profile:
                profile['browser'] = {}
            profile['browser'].update(browser_config)

            # Sauvegarder dans les profils pour que detect_platform_elements puisse l'utiliser
            self.profiles[platform_name] = profile

            # Afficher un dialogue de progression
            progress = QtWidgets.QProgressDialog(
                f"Test du navigateur pour {platform_name}...",
                "Annuler",
                0, 100,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)

            # Utiliser detect_platform_elements qui gère déjà l'ouverture du navigateur
            progress.setLabelText("Ouverture du navigateur et détection des éléments...")
            progress.setValue(30)

            # Appeler detect_platform_elements qui va:
            # 1. Ouvrir le navigateur via _activate_browser
            # 2. Détecter les éléments d'interface
            detection_result = self.conductor.detect_platform_elements(
                platform_name,
                browser_type=browser_type,
                browser_path=browser_path,
                url=browser_url,
                fullscreen=False
            )

            progress.setValue(80)

            if detection_result.get('success'):
                # Récupérer les positions si elles ont été détectées
                positions = detection_result.get('positions', {})

                if positions and self.remember_positions_check.isChecked():
                    profile['interface_positions'] = positions
                    # Émettre le signal
                    self.elements_detected.emit(platform_name, positions)

                # Sauvegarder le profil mis à jour
                self._save_platform_file(platform_name, profile)

                # Mettre à jour les profils locaux
                self.profiles[platform_name] = profile

                progress.setValue(100)

                # Mettre à jour le statut
                self.detection_status.setText("Test réussi!")
                self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                # Afficher un message de succès
                QtWidgets.QMessageBox.information(
                    self,
                    "Test réussi",
                    f"Le navigateur {browser_type} a été ouvert avec succès pour {platform_name}.\n"
                    f"Les éléments d'interface ont été détectés.\n\n"
                    "Vous pouvez maintenant passer aux onglets suivants pour configurer chaque élément."
                )

                # Émettre le signal
                self.browser_used.emit(platform_name, browser_type)

            else:
                progress.cancel()
                self.detection_status.setText(f"Échec: {detection_result.get('error', 'Erreur inconnue')}")
                self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

                # Si des positions partielles ont été détectées, les afficher
                if 'positions' in detection_result:
                    positions = detection_result['positions']
                    detected_elements = list(positions.keys())
                    if detected_elements:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Détection partielle",
                            f"Certains éléments ont été détectés: {', '.join(detected_elements)}\n\n"
                            f"Éléments manquants: {detection_result.get('message', '')}"
                        )
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Échec du test",
                            f"Aucun élément d'interface n'a pu être détecté.\n"
                            f"Erreur: {detection_result.get('message', 'Erreur inconnue')}"
                        )
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Échec du test",
                        f"Le test a échoué: {detection_result.get('message', 'Erreur inconnue')}"
                    )

        except Exception as e:
            logger.error(f"Erreur lors du test: {str(e)}")
            self.detection_status.setText(f"Erreur: {str(e)}")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors du test: {str(e)}"
            )

    def _save_browser_config(self):
        """Enregistre la configuration actuelle du navigateur"""
        # Récupérer les informations
        name = self.browser_name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Nom manquant",
                "Veuillez saisir un nom pour cette configuration de navigateur."
            )
            return

        # Créer la configuration
        browser_config = {
            "name": name,
            "type": self.browser_type_combo.currentText(),
            "path": self.browser_path_edit.text(),
            "url": self.browser_url_edit.text(),
            "fullscreen": False  # Mode plein écran désactivé
        }

        try:
            # Enregistrer dans le dictionnaire en mémoire
            self.saved_browsers[name] = browser_config

            # Sauvegarder dans un fichier
            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            os.makedirs(browsers_dir, exist_ok=True)

            file_path = os.path.join(browsers_dir, f"{name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(browser_config, f, indent=2, ensure_ascii=False)

            # Mettre à jour la liste
            self._update_saved_browsers_list()

            # Émettre le signal
            self.browser_saved.emit(name, browser_config)

            QtWidgets.QMessageBox.information(
                self,
                "Configuration enregistrée",
                f"La configuration du navigateur '{name}' a été enregistrée avec succès."
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la configuration: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'enregistrement",
                f"Impossible d'enregistrer la configuration: {str(e)}"
            )

    def _on_delete_browser(self):
        """Supprime la configuration de navigateur sélectionnée"""
        if not self.saved_browsers_list.currentItem():
            return

        browser_name = self.saved_browsers_list.currentItem().text()

        # Confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation de suppression",
            f"Êtes-vous sûr de vouloir supprimer la configuration '{browser_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Supprimer du dictionnaire
            if browser_name in self.saved_browsers:
                del self.saved_browsers[browser_name]

            # Supprimer le fichier
            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            file_path = os.path.join(browsers_dir, f"{browser_name}.json")

            if os.path.exists(file_path):
                os.remove(file_path)

            # Mettre à jour la liste
            self._update_saved_browsers_list()

            # Émettre le signal
            self.browser_deleted.emit(browser_name)

            QtWidgets.QMessageBox.information(
                self,
                "Configuration supprimée",
                f"La configuration du navigateur '{browser_name}' a été supprimée."
            )

        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la configuration: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de suppression",
                f"Impossible de supprimer la configuration: {str(e)}"
            )

    def _save_platform_file(self, platform_name, profile):
        """Sauvegarde un profil dans un fichier"""
        try:
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)

            file_path = os.path.join(profiles_dir, f"{platform_name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

            print(f"DEBUG: Profil {platform_name} sauvegardé dans {file_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du fichier {platform_name}: {str(e)}")
            print(f"DEBUG: Erreur sauvegarde fichier {platform_name}: {str(e)}")
            return False