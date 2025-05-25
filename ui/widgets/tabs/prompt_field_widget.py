#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/prompt_field_widget.py - Version refactorisée
"""

import os
import json
import traceback
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from core.orchestration.state_automation import StateBasedAutomation

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class PromptFieldWidget(QtWidgets.QWidget):
    """Widget de configuration du champ de prompt pour les plateformes d'IA - Version simplifiée"""

    # Signaux
    prompt_field_configured = pyqtSignal(str, dict)  # Plateforme, configuration
    prompt_field_detected = pyqtSignal(str, dict)  # Plateforme, position

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration du champ de prompt
        """
        super().__init__(parent)

        # Debug
        print("PromptFieldWidget: Initialisation (version refactorisée)...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # Système d'automatisation intelligente
        self.state_automation = None

        # Vérifier que pygetwindow est disponible
        if not HAS_PYGETWINDOW:
            logger.warning("pygetwindow non disponible - fonctionnalités de capture limitées")

        try:
            self._init_ui()
            print("PromptFieldWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de PromptFieldWidget: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """Configure l'interface utilisateur du widget - Version simplifiée"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Explication moderne
        explanation = QtWidgets.QLabel(
            "🎯 Configuration intelligente du champ de prompt\n"
            "Détection automatique par analyse de contraste et configuration des raccourcis de soumission."
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
        platform_group = QtWidgets.QGroupBox("🌐 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        # Combo de sélection des plateformes
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_combo)

        left_column.addWidget(platform_group)

        # === Section 2: Détection intelligente ===
        detection_group = QtWidgets.QGroupBox("🔍 Détection intelligente")
        detection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        detection_group.setMaximumWidth(300)
        detection_layout = QtWidgets.QVBoxLayout(detection_group)

        # Explication simple
        detection_explanation = QtWidgets.QLabel(
            "Analyse automatique de l'interface pour détecter le champ de prompt par contraste et structure."
        )
        detection_explanation.setWordWrap(True)
        detection_explanation.setStyleSheet("color: #555; padding: 5px; font-size: 11px;")
        detection_layout.addWidget(detection_explanation)

        # Bouton principal de détection
        self.smart_detect_button = QtWidgets.QPushButton("🚀 Détection intelligente")
        self.smart_detect_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.smart_detect_button.clicked.connect(self._on_smart_detection)
        self.smart_detect_button.setMinimumHeight(40)
        detection_layout.addWidget(self.smart_detect_button)

        # Statut de la détection
        self.detection_status = QtWidgets.QLabel("En attente de détection...")
        self.detection_status.setAlignment(Qt.AlignCenter)
        self.detection_status.setStyleSheet("color: #888; padding: 8px; background-color: #f5f5f5; border-radius: 4px;")
        self.detection_status.setWordWrap(True)
        detection_layout.addWidget(self.detection_status)

        # Options de détection
        options_layout = QtWidgets.QVBoxLayout()
        self.remember_position_check = QtWidgets.QCheckBox("🔒 Mémoriser la position")
        self.remember_position_check.setChecked(True)
        options_layout.addWidget(self.remember_position_check)

        self.force_detection_check = QtWidgets.QCheckBox("🔄 Forcer la re-détection")
        options_layout.addWidget(self.force_detection_check)

        detection_layout.addLayout(options_layout)
        left_column.addWidget(detection_group)

        # === Section 3: Test de soumission ===
        test_group = QtWidgets.QGroupBox("🧪 Test de soumission")
        test_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        test_group.setMaximumWidth(300)
        test_layout = QtWidgets.QVBoxLayout(test_group)

        # Bouton de test
        self.test_submit_button = QtWidgets.QPushButton("🧪 Tester la soumission")
        self.test_submit_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_submit_button.clicked.connect(self._on_test_submission)
        self.test_submit_button.setEnabled(False)
        test_layout.addWidget(self.test_submit_button)

        # Statut du test
        self.test_status = QtWidgets.QLabel("Effectuez d'abord la détection")
        self.test_status.setAlignment(Qt.AlignCenter)
        self.test_status.setStyleSheet("color: #888; padding: 5px; font-size: 11px;")
        self.test_status.setWordWrap(True)
        test_layout.addWidget(self.test_status)

        left_column.addWidget(test_group)

        # === Section 4: Sauvegarde ===
        save_group = QtWidgets.QGroupBox("💾 Sauvegarde")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        # Bouton de prévisualisation
        self.preview_button = QtWidgets.QPushButton("👁 Prévisualiser")
        self.preview_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.preview_button.clicked.connect(self._preview_configuration)
        self.preview_button.setEnabled(False)
        save_layout.addWidget(self.preview_button)

        # Bouton de sauvegarde
        self.save_button = QtWidgets.QPushButton("✅ Enregistrer")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_config)
        save_layout.addWidget(self.save_button)

        left_column.addWidget(save_group)

        # Spacer pour pousser tout vers le haut
        left_column.addStretch()

        # === COLONNE DROITE : Configuration ===
        right_column = QtWidgets.QVBoxLayout()

        # === Section 1: Informations de base ===
        info_group = QtWidgets.QGroupBox("📋 Informations de base")
        info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        info_layout = QtWidgets.QFormLayout(info_group)

        # Placeholder
        self.placeholder_edit = QtWidgets.QLineEdit()
        self.placeholder_edit.setPlaceholderText("Texte placeholder (ex: Message ChatGPT...)")
        self.placeholder_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        info_layout.addRow("Placeholder:", self.placeholder_edit)

        # Type de champ
        self.field_type_combo = QtWidgets.QComboBox()
        self.field_type_combo.addItems(["textarea", "input", "contenteditable"])
        self.field_type_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        info_layout.addRow("Type de champ:", self.field_type_combo)

        right_column.addWidget(info_group)

        # === Section 2: Configuration de soumission ===
        submit_group = QtWidgets.QGroupBox("⌨️ Configuration de soumission")
        submit_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        submit_layout = QtWidgets.QFormLayout(submit_group)

        # Méthode de soumission
        self.submit_method_combo = QtWidgets.QComboBox()
        self.submit_method_combo.addItems([
            "Entrée simple",
            "Ctrl + Entrée",
            "Shift + Entrée",
            "Alt + Entrée"
        ])
        self.submit_method_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        submit_layout.addRow("Méthode:", self.submit_method_combo)

        # Délai avant soumission
        self.submit_delay_spin = QtWidgets.QDoubleSpinBox()
        self.submit_delay_spin.setRange(0.1, 2.0)
        self.submit_delay_spin.setValue(0.5)
        self.submit_delay_spin.setSingleStep(0.1)
        self.submit_delay_spin.setDecimals(1)
        self.submit_delay_spin.setSuffix(" sec")
        self.submit_delay_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        submit_layout.addRow("Délai:", self.submit_delay_spin)

        # Effacement automatique
        self.auto_clear_check = QtWidgets.QCheckBox("Effacer le champ avant saisie")
        self.auto_clear_check.setChecked(True)
        submit_layout.addRow("", self.auto_clear_check)

        right_column.addWidget(submit_group)

        # === Section 3: Résultat de détection ===
        result_group = QtWidgets.QGroupBox("📊 Résultat de détection")
        result_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        result_layout = QtWidgets.QVBoxLayout(result_group)

        # Informations de position
        self.position_info = QtWidgets.QLabel("Aucune position détectée")
        self.position_info.setStyleSheet(
            "padding: 10px; background-color: #f8f9fa; border-radius: 4px; font-family: 'Courier New';")
        self.position_info.setWordWrap(True)
        result_layout.addWidget(self.position_info)

        # Confiance de détection
        confidence_layout = QtWidgets.QHBoxLayout()
        confidence_layout.addWidget(QtWidgets.QLabel("Confiance:"))
        self.confidence_bar = QtWidgets.QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        confidence_layout.addWidget(self.confidence_bar)
        result_layout.addLayout(confidence_layout)

        right_column.addWidget(result_group)

        # Spacer pour équilibrer
        right_column.addStretch()

        # === Assemblage des colonnes ===
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(320)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        columns_layout.addWidget(left_widget)
        columns_layout.addWidget(right_widget, 1)

        main_layout.addLayout(columns_layout)

        # Note d'aide moderne
        help_note = QtWidgets.QLabel(
            "💡 <b>Workflow simplifié:</b> Sélectionnez la plateforme → Détection intelligente → "
            "Test de soumission → Enregistrer"
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #074E68; padding: 10px; font-style: italic; font-size: 11px;")
        help_note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_note)

    # ===================================================================
    # MÉTHODES DE GESTION DES PROFILS (conservées)
    # ===================================================================

    def set_profiles(self, profiles):
        """Met à jour les profils disponibles dans le widget"""
        self.profiles = profiles
        self._update_platform_combo()

    def select_platform(self, platform_name):
        """Sélectionne une plateforme dans la liste déroulante"""
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        """Actualise les données du widget"""
        self._update_platform_combo()
        if self.current_platform:
            self._load_platform_config(self.current_platform)

    def _update_platform_combo(self):
        """Met à jour la liste déroulante des plateformes"""
        current_text = self.platform_combo.currentText()

        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionnez une plateforme --")

        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)

        # Restaurer la sélection précédente si possible
        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_platform_selected(self, index):
        """Gère la sélection d'une plateforme dans la liste"""
        if index <= 0:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()
            return

        platform_name = self.platform_combo.currentText()
        self._load_platform_config(platform_name)

    def _load_platform_config(self, platform_name):
        """Charge la configuration de la plateforme sélectionnée"""
        self.current_platform = platform_name
        self.current_profile = self.profiles.get(platform_name, {})

        if not self.current_profile:
            print(f"DEBUG: Profil vide pour {platform_name}!")
            self._reset_interface()
            return

        # Charger les informations du champ de prompt
        interface = self.current_profile.get('interface', {})
        prompt_field = interface.get('prompt_field', {})

        # Informations de base
        self.placeholder_edit.setText(prompt_field.get('placeholder', ''))

        field_type = prompt_field.get('type', 'textarea')
        index = self.field_type_combo.findText(field_type)
        if index >= 0:
            self.field_type_combo.setCurrentIndex(index)

        # Configuration de soumission
        submission = prompt_field.get('submission', {})
        method = submission.get('method', 'enter')

        method_map = {
            'enter': 0,
            'ctrl_enter': 1,
            'shift_enter': 2,
            'alt_enter': 3
        }

        method_index = method_map.get(method, 0)
        self.submit_method_combo.setCurrentIndex(method_index)

        self.submit_delay_spin.setValue(submission.get('delay', 0.5))
        self.auto_clear_check.setChecked(submission.get('auto_clear', True))

        # Vérifier si des positions sont déjà enregistrées
        positions = self.current_profile.get('interface_positions', {})
        if 'prompt_field' in positions:
            self._update_position_display(positions['prompt_field'])
            self.detection_status.setText("✅ Position enregistrée")
            self.detection_status.setStyleSheet(
                "color: #2e7d32; padding: 8px; background-color: #e8f5e8; border-radius: 4px;")
            self.test_submit_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.test_status.setText("Prêt pour le test")
        else:
            self._reset_interface()

    def _reset_interface(self):
        """Remet à zéro l'interface"""
        self.detection_status.setText("En attente de détection...")
        self.detection_status.setStyleSheet("color: #888; padding: 8px; background-color: #f5f5f5; border-radius: 4px;")
        self.position_info.setText("Aucune position détectée")
        self.confidence_bar.setValue(0)
        self.test_submit_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.test_status.setText("Effectuez d'abord la détection")

    def _update_position_display(self, position):
        """Met à jour l'affichage des informations de position"""
        info_text = f"""Position détectée:
• Centre: ({position.get('center_x', 0)}, {position.get('center_y', 0)})
• Taille: {position.get('width', 0)} × {position.get('height', 0)} px
• Zone: ({position.get('x', 0)}, {position.get('y', 0)}) → ({position.get('x', 0) + position.get('width', 0)}, {position.get('y', 0) + position.get('height', 0)})"""

        self.position_info.setText(info_text)

        # Calculer la confiance basée sur la taille (heuristique simple)
        area = position.get('width', 0) * position.get('height', 0)
        confidence = min(100, max(50, area // 100))  # Entre 50% et 100%
        self.confidence_bar.setValue(confidence)

    # ===================================================================
    # NOUVELLE LOGIQUE DE DÉTECTION INTELLIGENTE
    # ===================================================================

    def _on_smart_detection(self):
        """Lance la détection intelligente avec StateBasedAutomation"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Vérifier la configuration minimale
        browser_info = self.current_profile.get('browser', {})
        browser_url = browser_info.get('url', '')

        if not browser_url:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "URL du navigateur manquante. Configurez d'abord le navigateur dans l'onglet correspondant."
            )
            return

        # Vérifier si forcer la détection
        force_detection = self.force_detection_check.isChecked()
        if not force_detection:
            positions = self.current_profile.get('interface_positions', {})
            if 'prompt_field' in positions:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Position déjà détectée",
                    "Une position est déjà enregistrée pour cette plateforme.\n"
                    "Voulez-vous forcer une nouvelle détection ?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return

        try:
            # Instancier les contrôleurs pour l'automatisation
            from core.interaction.mouse import MouseController
            from core.interaction.keyboard import KeyboardController

            mouse_controller = MouseController()
            keyboard_controller = KeyboardController()

            # Créer le système d'automatisation
            self.state_automation = StateBasedAutomation(
                self.conductor.detector,
                mouse_controller,
                keyboard_controller,
                self.conductor
            )

            # Connecter les signaux
            self.state_automation.state_changed.connect(self._on_automation_state_changed)
            self.state_automation.automation_completed.connect(self._on_detection_completed)

            # Préparer l'interface
            self.smart_detect_button.setEnabled(False)
            self.detection_status.setText("🚀 Détection intelligente en cours...")
            self.detection_status.setStyleSheet(
                "color: #1976D2; padding: 8px; background-color: #e3f2fd; border-radius: 4px;")

            # Démarrer l'automatisation avec profil complet
            browser_type = browser_info.get('type', 'Chrome')

            self.state_automation.start_test_automation(
                self.current_profile,
                0,  # Pas de tabulation pour la détection
                browser_type,
                browser_url
            )

        except ImportError as e:
            logger.error(f"Erreur d'importation contrôleurs: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                "Contrôleurs d'interaction non disponibles."
            )
            self.smart_detect_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Erreur démarrage détection: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Échec du démarrage de la détection: {str(e)}"
            )
            self.smart_detect_button.setEnabled(True)

    def _on_automation_state_changed(self, state, message):
        """Callback pour les changements d'état de la détection"""
        self.detection_status.setText(f"🔄 {message}")
        QtWidgets.QApplication.processEvents()

    def _on_detection_completed(self, success, message, duration):
        """Callback pour la fin de la détection"""
        self.smart_detect_button.setEnabled(True)

        if success:
            # Essayer de détecter les éléments après automatisation
            self._perform_intelligent_detection()
        else:
            self.detection_status.setText(f"❌ Échec: {message}")
            self.detection_status.setStyleSheet(
                "color: #d32f2f; padding: 8px; background-color: #ffebee; border-radius: 4px;")
            QtWidgets.QMessageBox.critical(
                self,
                "Détection échouée",
                f"Erreur pendant la détection automatique :\n{message}"
            )

    def _perform_intelligent_detection(self):
        """Effectue la détection intelligente des éléments"""
        try:
            # Capturer l'écran
            browser_info = self.current_profile.get('browser', {})
            browser_type = browser_info.get('type', 'Chrome')

            screenshot = self.conductor.detector.capture_screen(
                force=True,
                browser_type=browser_type
            )

            if screenshot is None:
                raise Exception("Capture d'écran échouée")

            # Préparer la configuration d'interface pour la détection
            interface_config = {
                "prompt_field": {
                    "type": self.field_type_combo.currentText(),
                    "placeholder": self.placeholder_edit.text(),
                    "detection": {
                        "method": "smart_contrast",  # Nouvelle méthode intelligente
                        "use_ocr": True,
                        "use_contrast": True
                    }
                }
            }

            # Détecter avec la nouvelle méthode intelligente
            positions = self.conductor.detector.detect_interface_elements(
                screenshot,
                interface_config
            )

            if 'prompt_field' in positions:
                field_position = positions['prompt_field']

                # Enregistrer la position si demandé
                if self.remember_position_check.isChecked():
                    if 'interface_positions' not in self.current_profile:
                        self.current_profile['interface_positions'] = {}

                    self.current_profile['interface_positions']['prompt_field'] = field_position
                    self._save_profile()

                # Mettre à jour l'affichage
                self._update_position_display(field_position)

                self.detection_status.setText("✅ Champ détecté avec succès!")
                self.detection_status.setStyleSheet(
                    "color: #2e7d32; padding: 8px; background-color: #e8f5e8; border-radius: 4px;")

                self.test_submit_button.setEnabled(True)
                self.preview_button.setEnabled(True)
                self.test_status.setText("Prêt pour le test")

                # Émettre le signal
                self.prompt_field_detected.emit(self.current_platform, field_position)

                QtWidgets.QMessageBox.information(
                    self,
                    "Détection réussie",
                    "✅ Le champ de prompt a été détecté avec succès !\n\n"
                    "Vous pouvez maintenant tester la soumission ou prévisualiser le résultat."
                )
            else:
                raise Exception("Aucun champ de prompt détecté")

        except Exception as e:
            logger.error(f"Erreur détection intelligente: {str(e)}")
            self.detection_status.setText(f"❌ Détection échouée: {str(e)}")
            self.detection_status.setStyleSheet(
                "color: #d32f2f; padding: 8px; background-color: #ffebee; border-radius: 4px;")

            QtWidgets.QMessageBox.warning(
                self,
                "Détection échouée",
                f"Impossible de détecter le champ de prompt :\n{str(e)}\n\n"
                "Suggestions :\n"
                "• Vérifiez que le navigateur est ouvert sur la bonne page\n"
                "• Vérifiez que le champ de prompt est visible\n"
                "• Essayez de cocher 'Forcer la re-détection'"
            )

    # ===================================================================
    # TEST DE SOUMISSION
    # ===================================================================

    def _on_test_submission(self):
        """Lance un test de soumission en utilisant la méthode configurée"""
        if not self.current_platform:
            return

        positions = self.current_profile.get('interface_positions', {})
        if 'prompt_field' not in positions:
            QtWidgets.QMessageBox.warning(
                self,
                "Position manquante",
                "Veuillez d'abord effectuer la détection du champ."
            )
            return

        try:
            # Instancier les contrôleurs
            from core.interaction.mouse import MouseController
            from core.interaction.keyboard import KeyboardController

            mouse_controller = MouseController()
            keyboard_controller = KeyboardController()

            # Test de soumission
            self.test_submit_button.setEnabled(False)
            self.test_status.setText("🧪 Test en cours...")

            field_pos = positions['prompt_field']

            # 1. Cliquer dans le champ
            mouse_controller.click(field_pos['center_x'], field_pos['center_y'])
            time.sleep(0.3)

            # 2. Effacer si demandé
            if self.auto_clear_check.isChecked():
                keyboard_controller.hotkey('ctrl', 'a')
                keyboard_controller.press('delete')
                time.sleep(0.2)

            # 3. Taper le texte de test
            test_text = f"Test de soumission - {time.strftime('%H:%M:%S')}"
            keyboard_controller.type_text(test_text)

            # 4. Attendre le délai configuré
            delay = self.submit_delay_spin.value()
            time.sleep(delay)

            # 5. Soumettre selon la méthode choisie
            method_index = self.submit_method_combo.currentIndex()
            if method_index == 0:  # Entrée simple
                keyboard_controller.press('return')
            elif method_index == 1:  # Ctrl + Entrée
                keyboard_controller.hotkey('ctrl', 'return')
            elif method_index == 2:  # Shift + Entrée
                keyboard_controller.hotkey('shift', 'return')
            elif method_index == 3:  # Alt + Entrée
                keyboard_controller.hotkey('alt', 'return')

            self.test_status.setText("✅ Test réussi!")
            self.test_status.setStyleSheet("color: #2e7d32;")

            QtWidgets.QMessageBox.information(
                self,
                "Test réussi",
                f"✅ Test de soumission réussi !\n\n"
                f"Méthode: {self.submit_method_combo.currentText()}\n"
                f"Délai: {delay}s\n"
                f"Texte envoyé: {test_text}"
            )

        except ImportError:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                "Contrôleurs d'interaction non disponibles."
            )
        except Exception as e:
            logger.error(f"Erreur test soumission: {str(e)}")
            self.test_status.setText("❌ Échec du test")
            self.test_status.setStyleSheet("color: #d32f2f;")

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de test",
                f"Erreur pendant le test :\n{str(e)}"
            )
        finally:
            self.test_submit_button.setEnabled(True)

    # ===================================================================
    # PRÉVISUALISATION (conservée et améliorée)
    # ===================================================================

    def _preview_configuration(self):
        """Affiche une prévisualisation visuelle du champ détecté"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        positions = self.current_profile.get('interface_positions', {})
        if 'prompt_field' not in positions:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune position détectée",
                "Veuillez d'abord effectuer la détection du champ."
            )
            return

        try:
            # Capturer l'écran
            browser_info = self.current_profile.get('browser', {})
            browser_type = browser_info.get('type', 'Chrome')

            screenshot = self.conductor.detector.capture_screen(
                force=True,
                browser_type=browser_type
            )

            if screenshot is None:
                raise Exception("Capture d'écran échouée")

            # Récupérer la position du champ
            field_pos = positions['prompt_field']
            x = field_pos.get('x', 0)
            y = field_pos.get('y', 0)
            w = field_pos.get('width', 100)
            h = field_pos.get('height', 30)
            center_x = field_pos.get('center_x', x + w // 2)
            center_y = field_pos.get('center_y', y + h // 2)

            # Créer une zone étendue autour du champ
            margin = 80
            img_height, img_width = screenshot.shape[:2]
            extended_x = max(0, x - margin)
            extended_y = max(0, y - margin)
            extended_w = min(img_width - extended_x, w + 2 * margin)
            extended_h = min(img_height - extended_y, h + 2 * margin)

            # Extraire la zone étendue
            preview_region = screenshot[extended_y:extended_y + extended_h, extended_x:extended_x + extended_w].copy()

            # Dessiner les annotations
            import cv2

            rel_x = x - extended_x
            rel_y = y - extended_y
            rel_center_x = center_x - extended_x
            rel_center_y = center_y - extended_y

            # Rectangle du champ en vert
            cv2.rectangle(preview_region, (rel_x, rel_y), (rel_x + w, rel_y + h), (0, 255, 0), 3)

            # Point central en rouge
            cv2.circle(preview_region, (rel_center_x, rel_center_y), 8, (0, 0, 255), -1)
            cv2.circle(preview_region, (rel_center_x, rel_center_y), 6, (255, 255, 255), -1)
            cv2.circle(preview_region, (rel_center_x, rel_center_y), 4, (0, 0, 255), -1)

            # Texte d'annotation
            cv2.putText(preview_region, "Champ detecte", (rel_x + 5, rel_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Créer le dialogue de prévisualisation
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(f"Prévisualisation - {self.current_platform}")
            dialog.setModal(True)
            dialog.resize(900, 700)

            layout = QtWidgets.QVBoxLayout(dialog)

            # Titre
            title = QtWidgets.QLabel(f"👁 Champ détecté pour {self.current_platform}")
            title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            # Convertir l'image OpenCV en QPixmap
            height, width = preview_region.shape[:2]
            bytes_per_line = 3 * width
            q_image = QtGui.QImage(preview_region.data, width, height, bytes_per_line,
                                   QtGui.QImage.Format_RGB888).rgbSwapped()
            pixmap = QtGui.QPixmap.fromImage(q_image)

            # Redimensionner si nécessaire
            max_display_width = 800
            max_display_height = 500
            if pixmap.width() > max_display_width or pixmap.height() > max_display_height:
                pixmap = pixmap.scaled(max_display_width, max_display_height,
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Afficher l'image
            image_label = QtWidgets.QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("border: 2px solid #ddd; background-color: white; padding: 5px;")
            layout.addWidget(image_label)

            # Informations détaillées
            info_layout = QtWidgets.QHBoxLayout()

            # Position
            pos_info = QtWidgets.QLabel(f"""
            <b>📍 Position détectée:</b><br>
            • Centre: ({center_x}, {center_y})<br>
            • Taille: {w} × {h} px<br>
            • Zone: ({x}, {y}) → ({x + w}, {y + h})
            """)
            pos_info.setStyleSheet("background-color: #e8f5e8; padding: 10px; border-radius: 5px;")

            # Configuration
            method_text = self.submit_method_combo.currentText()
            config_info = QtWidgets.QLabel(f"""
            <b>⚙️ Configuration:</b><br>
            • Type: {self.field_type_combo.currentText()}<br>
            • Soumission: {method_text}<br>
            • Délai: {self.submit_delay_spin.value()}s<br>
            • Auto-effacement: {'Oui' if self.auto_clear_check.isChecked() else 'Non'}
            """)
            config_info.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 5px;")

            info_layout.addWidget(pos_info)
            info_layout.addWidget(config_info)
            layout.addLayout(info_layout)

            # Légende
            legend = QtWidgets.QLabel("🟢 Rectangle vert: Zone du champ | 🔴 Point rouge: Centre de clic")
            legend.setAlignment(Qt.AlignCenter)
            legend.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
            layout.addWidget(legend)

            # Boutons
            button_layout = QtWidgets.QHBoxLayout()

            close_button = QtWidgets.QPushButton("✕ Fermer")
            close_button.setStyleSheet(PlatformConfigStyle.get_button_style())
            close_button.clicked.connect(dialog.accept)

            save_button = QtWidgets.QPushButton("✅ Confirmer et sauvegarder")
            save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
            save_button.clicked.connect(lambda: (dialog.accept(), self._on_save_config()))

            button_layout.addWidget(close_button)
            button_layout.addWidget(save_button)
            layout.addLayout(button_layout)

            dialog.exec_()

        except Exception as e:
            logger.error(f"Erreur prévisualisation: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de prévisualisation",
                f"Impossible de générer la prévisualisation:\n{str(e)}"
            )

    # ===================================================================
    # SAUVEGARDE (conservée et améliorée)
    # ===================================================================

    def _on_save_config(self):
        """Enregistre la configuration du champ de prompt"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        try:
            # Mettre à jour la configuration du champ de prompt
            if 'interface' not in self.current_profile:
                self.current_profile['interface'] = {}

            # Mapper la méthode de soumission
            method_map = {
                0: 'enter',
                1: 'ctrl_enter',
                2: 'shift_enter',
                3: 'alt_enter'
            }

            method_index = self.submit_method_combo.currentIndex()
            submit_method = method_map.get(method_index, 'enter')

            # Construire la configuration
            prompt_field_config = {
                "type": self.field_type_combo.currentText(),
                "placeholder": self.placeholder_edit.text(),
                "detection": {
                    "method": "smart_contrast",
                    "use_ocr": True,
                    "use_contrast": True
                },
                "submission": {
                    "method": submit_method,
                    "delay": self.submit_delay_spin.value(),
                    "auto_clear": self.auto_clear_check.isChecked()
                }
            }

            # Mettre à jour le profil
            self.current_profile['interface']['prompt_field'] = prompt_field_config

            # Sauvegarder le profil
            success = self._save_profile()

            if success:
                # Émettre le signal
                self.prompt_field_configured.emit(self.current_platform, prompt_field_config)

                QtWidgets.QMessageBox.information(
                    self,
                    "Configuration enregistrée",
                    f"✅ Configuration du champ de prompt pour {self.current_platform} "
                    f"enregistrée avec succès !\n\n"
                    f"Méthode de soumission: {self.submit_method_combo.currentText()}"
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur d'enregistrement",
                    "❌ Impossible d'enregistrer la configuration."
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'enregistrement: {str(e)}"
            )

    def _save_profile(self):
        """Sauvegarde le profil dans le système"""
        if not self.current_platform or not self.current_profile:
            return False

        try:
            # Méthode 1: Utiliser la base de données
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        success = self.conductor.database.save_platform(self.current_platform, self.current_profile)
                        print(f"DEBUG: Sauvegarde du profil dans la DB: {success}")
                        if success:
                            return True
                    except Exception as e:
                        print(f"DEBUG: Erreur sauvegarde DB: {str(e)}")

            # Méthode 2: Utiliser le provider de configuration
            if hasattr(self.config_provider, 'save_profile'):
                try:
                    success = self.config_provider.save_profile(self.current_platform, self.current_profile)
                    print(f"DEBUG: Sauvegarde du profil via ConfigProvider: {success}")
                    if success:
                        return True
                except Exception as e:
                    print(f"DEBUG: Erreur sauvegarde ConfigProvider: {str(e)}")

            # Méthode 3: Sauvegarde directe dans un fichier
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)

            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            print(f"DEBUG: Profil {self.current_platform} sauvegardé directement dans {file_path}")

            # Mettre à jour le cache global des profils
            self.profiles[self.current_platform] = self.current_profile

            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du profil: {str(e)}")
            print(f"DEBUG: Erreur globale sauvegarde profil: {str(e)}")
            return False