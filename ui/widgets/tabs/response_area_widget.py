#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/response_area_widget.py - Version refactorisée avec extraction HTML
"""

import os
import json
import traceback
import time
import re
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from utils.exceptions import VisionDetectionError, ValidationError, OrchestrationError
from ui.styles.platform_config_style import PlatformConfigStyle
from core.orchestration.state_automation import StateBasedAutomation


class ResponseAreaWidget(QtWidgets.QWidget):
    """Widget de configuration de la zone de réponse pour les plateformes d'IA"""

    # Signaux
    response_area_configured = pyqtSignal(str, dict)  # Plateforme, configuration
    response_area_detected = pyqtSignal(str, dict)  # Plateforme, position
    response_received = pyqtSignal(str, str)  # Plateforme, contenu de la réponse

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration de la zone de réponse
        """
        super().__init__(parent)

        # Debug
        print("ResponseAreaWidget: Initialisation...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # Système d'automatisation intelligente
        self.state_automation = None

        try:
            self._init_ui()
            print("ResponseAreaWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de ResponseAreaWidget: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """Configure l'interface utilisateur du widget de zone de réponse - DISPOSITION 2 COLONNES"""

        # Layout principal horizontal (2 colonnes)
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ============================
        # COLONNE GAUCHE - CONTRÔLES
        # ============================
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(15)

        # === Section 1: Sélection de la plateforme ===
        platform_group = QtWidgets.QGroupBox("🎯 Choisissez votre plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        # Combo de sélection des plateformes
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_combo)

        left_column.addWidget(platform_group)

        # === Section 2: Actions ===
        actions_group = QtWidgets.QGroupBox("⚡ Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(300)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        # Bouton de test automatique
        self.auto_test_button = QtWidgets.QPushButton("🚀 Test automatique + Position")
        self.auto_test_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.auto_test_button.clicked.connect(self._on_auto_test)
        actions_layout.addWidget(self.auto_test_button)

        # Bouton d'extraction HTML
        self.html_extract_button = QtWidgets.QPushButton("📋 Extraire via Console HTML")
        self.html_extract_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.html_extract_button.clicked.connect(self._on_html_extraction)
        self.html_extract_button.setEnabled(False)  # Activé après test automatique
        actions_layout.addWidget(self.html_extract_button)

        # Statut de capture
        self.capture_status = QtWidgets.QLabel("Aucune capture effectuée")
        self.capture_status.setAlignment(Qt.AlignCenter)
        self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.capture_status.setWordWrap(True)
        actions_layout.addWidget(self.capture_status)

        # Options de capture
        options_layout = QtWidgets.QVBoxLayout()
        self.remember_position_check = QtWidgets.QCheckBox("🔒 Mémoriser la position")
        self.remember_position_check.setChecked(True)
        options_layout.addWidget(self.remember_position_check)

        self.force_capture_check = QtWidgets.QCheckBox("🔄 Forcer la capture")
        options_layout.addWidget(self.force_capture_check)

        actions_layout.addLayout(options_layout)

        left_column.addWidget(actions_group)

        # === Section 3: Sauvegarde ===
        save_group = QtWidgets.QGroupBox("💾 Sauvegarde")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        # Bouton de sauvegarde
        self.save_button = QtWidgets.QPushButton("✅ Enregistrer la configuration")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_config)
        save_layout.addWidget(self.save_button)

        # Note sur la fin du processus
        help_note = QtWidgets.QLabel(
            "<b>💡 Note:</b> Après avoir configuré tous les éléments d'interface, "
            "vous pouvez tester la connexion complète depuis l'onglet 'Configuration Générale'."
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #074E68; font-size: 11px;")
        save_layout.addWidget(help_note)

        left_column.addWidget(save_group)

        # Espacer pour pousser vers le haut
        left_column.addStretch(1)

        # =============================
        # COLONNE DROITE - CONFIGURATION
        # =============================
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(15)

        # Explication en haut de la colonne droite
        explanation = QtWidgets.QLabel(
            "🎯 <b>Extraction de réponses IA via Console HTML</b><br>"
            "Méthode précise pour extraire les réponses sans OCR ni sélection manuelle."
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignLeft)
        right_column.addWidget(explanation)

        # === Guide HTML F12 ===
        guide_group = QtWidgets.QGroupBox("📋 Guide Console HTML")
        guide_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        guide_layout = QtWidgets.QVBoxLayout(guide_group)

        # Instructions
        instructions = QtWidgets.QLabel(
            "<b>Instructions :</b><br>"
            "1. 🚀 Lancez d'abord le test automatique<br>"
            "2. ⏳ Attendez la réponse de l'IA<br>"
            "3. 🔧 Appuyez sur F12 pour ouvrir les outils<br>"
            "4. 🎯 Clic droit sur la zone de réponse → Inspecter<br>"
            "5. 📋 Clic droit sur l'élément HTML → Copy → Copy element<br>"
            "6. 📥 Collez le HTML ci-dessous et validez"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #2196F3; font-size: 11px;")
        guide_layout.addWidget(instructions)

        right_column.addWidget(guide_group)

        # === Zone HTML ===
        html_group = QtWidgets.QGroupBox("📝 HTML de la zone de réponse")
        html_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        html_layout = QtWidgets.QVBoxLayout(html_group)

        self.html_input = QtWidgets.QTextEdit()
        self.html_input.setPlaceholderText("Collez ici le HTML copié depuis la console (F12)...")
        self.html_input.setMaximumHeight(100)
        self.html_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        html_layout.addWidget(self.html_input)

        # Boutons HTML
        html_buttons_layout = QtWidgets.QHBoxLayout()

        self.validate_html_button = QtWidgets.QPushButton("✅ Valider HTML")
        self.validate_html_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.validate_html_button.clicked.connect(self._on_validate_html)
        html_buttons_layout.addWidget(self.validate_html_button)

        self.clear_html_button = QtWidgets.QPushButton("🗑️ Effacer")
        self.clear_html_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.clear_html_button.clicked.connect(lambda: self.html_input.clear())
        html_buttons_layout.addWidget(self.clear_html_button)

        html_layout.addLayout(html_buttons_layout)
        right_column.addWidget(html_group)

        # === Validation et Preview ===
        result_group = QtWidgets.QGroupBox("📋 Résultat et validation")
        result_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        result_layout = QtWidgets.QVBoxLayout(result_group)

        # Status validation
        self.validation_status = QtWidgets.QLabel("En attente de HTML...")
        self.validation_status.setAlignment(Qt.AlignCenter)
        self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.validation_status.setWordWrap(True)
        result_layout.addWidget(self.validation_status)

        # Preview du texte extrait
        self.extracted_text_preview = QtWidgets.QTextEdit()
        self.extracted_text_preview.setReadOnly(True)
        self.extracted_text_preview.setMaximumHeight(120)
        self.extracted_text_preview.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; padding: 5px;"
        )
        self.extracted_text_preview.setPlaceholderText("Le texte extrait apparaîtra ici...")
        result_layout.addWidget(self.extracted_text_preview)

        right_column.addWidget(result_group)

        # === Configuration d'extraction ===
        extraction_group = QtWidgets.QGroupBox("⚙️ Configuration d'extraction")
        extraction_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        extraction_layout = QtWidgets.QFormLayout(extraction_group)

        # Méthode d'extraction
        self.extraction_method_combo = QtWidgets.QComboBox()
        self.extraction_method_combo.addItems(
            ["Console HTML (Recommandé)", "Presse-papiers (Ctrl+A, Ctrl+C)", "Reconnaissance de texte (OCR)"])
        self.extraction_method_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        extraction_layout.addRow("Méthode:", self.extraction_method_combo)

        # Attente après détection
        self.wait_extraction_spin = QtWidgets.QDoubleSpinBox()
        self.wait_extraction_spin.setRange(2.0, 10.0)
        self.wait_extraction_spin.setValue(3.0)
        self.wait_extraction_spin.setSingleStep(0.5)
        self.wait_extraction_spin.setDecimals(1)
        self.wait_extraction_spin.setSuffix(" secondes")
        self.wait_extraction_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        extraction_layout.addRow("Attente réponse IA:", self.wait_extraction_spin)

        right_column.addWidget(extraction_group)

        # Spacer pour équilibrer
        right_column.addStretch(1)

        # ========================
        # ASSEMBLAGE DES COLONNES
        # ========================

        # Ajouter les colonnes au layout principal
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(320)  # Largeur fixe pour la colonne gauche

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)  # Stretch factor pour expandre

    # ====================================================================
    # NOUVELLE LOGIQUE - AUTOMATISATION INTELLIGENTE + EXTRACTION HTML
    # ====================================================================

    def _on_auto_test(self):
        """Lance le test automatique avec positionnement de la zone de réponse"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Vérifier la configuration minimale
        browser_info = self.current_profile.get('browser', {})
        browser_type = browser_info.get('type', 'Chrome')
        browser_url = browser_info.get('url', '')

        if not browser_url:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "URL du navigateur manquante. Configurez d'abord le navigateur."
            )
            return

        # Vérifier les positions prompt/submit
        positions = self.current_profile.get('interface_positions', {})
        if not positions.get('prompt_field') or not positions.get('submit_button'):
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "Positions du champ de prompt et bouton submit manquantes."
            )
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
            self.state_automation.automation_completed.connect(self._on_automation_completed)

            # Préparer l'interface
            self.auto_test_button.setEnabled(False)
            self.capture_status.setText("🚀 Test automatique en cours...")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

            # Démarrer l'automatisation avec prompt test
            self.state_automation.start_test_automation(
                self.current_profile,
                3,  # 3 tabulations par défaut
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
            self.auto_test_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Erreur démarrage automatisation: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Échec du démarrage: {str(e)}"
            )
            self.auto_test_button.setEnabled(True)

    def _on_automation_state_changed(self, state, message):
        """Callback pour les changements d'état du test automatique"""
        self.capture_status.setText(f"🔄 {message}")
        self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        QtWidgets.QApplication.processEvents()

    def _on_automation_completed(self, success, message, duration):
        """Callback pour la fin de l'automatisation"""
        self.auto_test_button.setEnabled(True)

        if success:
            self.capture_status.setText(f"✅ Test réussi - Attendez la réponse IA")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Activer le bouton d'extraction HTML
            self.html_extract_button.setEnabled(True)

            QtWidgets.QMessageBox.information(
                self,
                "Test automatique réussi",
                f"🎉 Test réussi en {duration:.1f}s !<br><br>"
                f"Maintenant :<br>"
                f"1. Attendez la réponse de l'IA<br>"
                f"2. Utilisez 'Extraire via Console HTML'"
            )
        else:
            self.capture_status.setText(f"❌ Erreur: {message}")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de test",
                f"Erreur pendant le test automatique :<br>{message}"
            )

    def _on_html_extraction(self):
        """Guide l'utilisateur pour l'extraction HTML"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Instructions détaillées
        reply = QtWidgets.QMessageBox.information(
            self,
            "🔧 Guide extraction HTML",
            "<b>Suivez ces étapes :</b><br><br>"
            "1. 🎯 <b>Assurez-vous que l'IA a répondu</b><br>"
            "2. 🔧 <b>Appuyez sur F12</b> (ouvre les outils développeur)<br>"
            "3. 🎯 <b>Clic droit sur la zone de réponse</b> → Inspecter<br>"
            "4. 📋 <b>Dans l'inspecteur :</b> Clic droit sur l'élément HTML → Copy → Copy element<br>"
            "5. 📥 <b>Collez le HTML</b> dans la zone de texte ci-dessous<br>"
            "6. ✅ <b>Cliquez 'Valider HTML'</b><br><br>"
            "<i>Cette méthode est 100% précise !</i>",
            QtWidgets.QMessageBox.Ok
        )

        # Focus sur la zone HTML
        self.html_input.setFocus()

    def _on_validate_html(self):
        """Valide le HTML et extrait le texte"""
        html_content = self.html_input.toPlainText().strip()

        if not html_content:
            QtWidgets.QMessageBox.warning(
                self,
                "HTML manquant",
                "Veuillez coller le HTML dans la zone de texte."
            )
            return

        try:
            # Valider la structure HTML
            is_valid, validation_message = self._validate_html_structure(html_content)

            if not is_valid:
                self.validation_status.setText(f"❌ {validation_message}")
                self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                QtWidgets.QMessageBox.warning(
                    self,
                    "HTML invalide",
                    f"Problème avec le HTML :\n{validation_message}"
                )
                return

            # Extraire le texte
            extracted_text = self.conductor.detector.extract_text_from_html(html_content)

            if not extracted_text:
                self.validation_status.setText("❌ Aucun texte extrait")
                self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                QtWidgets.QMessageBox.warning(
                    self,
                    "Extraction échouée",
                    "Aucun texte n'a pu être extrait du HTML."
                )
                return

            # Afficher le résultat
            self.extracted_text_preview.setPlainText(extracted_text)
            self.validation_status.setText("✅ HTML validé - Texte extrait avec succès")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Mémoriser la position si demandé
            if self.remember_position_check.isChecked():
                self._save_html_extraction_config(html_content, extracted_text)

            # Émettre le signal
            self.response_received.emit(self.current_platform, extracted_text)

            QtWidgets.QMessageBox.information(
                self,
                "Extraction réussie",
                f"✅ Texte extrait avec succès !<br><br>"
                f"Longueur : {len(extracted_text)} caractères<br>"
                f"Configuration {'sauvegardée' if self.remember_position_check.isChecked() else 'temporaire'}"
            )

        except Exception as e:
            logger.error(f"Erreur validation HTML: {str(e)}")
            self.validation_status.setText(f"❌ Erreur: {str(e)}")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la validation :\n{str(e)}"
            )

    def _validate_html_structure(self, html_content):
        """
        Valide la structure HTML selon les critères définis
        Args:
            html_content (str): HTML à valider
        Returns:
            tuple: (bool, str) - (is_valid, message)
        """
        try:
            # Vérifications basiques
            if len(html_content) < 10:
                return False, "HTML trop court"

            # Vérifier qu'il y a des balises
            if '<' not in html_content or '>' not in html_content:
                return False, "Format HTML invalide"

            # Logique de validation : balises ouvrantes/fermantes
            import re

            # Extraire toutes les balises
            opening_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>', html_content)
            closing_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9]*)>', html_content)

            # Validation spécifique : si plusieurs <p>, vérifier la fin
            p_count = html_content.count('<p')
            if p_count > 1:
                # Chercher la balise suivant le dernier </p>
                last_p_pos = html_content.rfind('</p>')
                if last_p_pos != -1:
                    remaining_html = html_content[last_p_pos + 4:].strip()
                    if remaining_html:
                        next_tag_match = re.search(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)', remaining_html)
                        if next_tag_match:
                            tag_name = next_tag_match.group(2).lower()
                            if tag_name not in ['div', 'span', 'article', 'section']:
                                return False, f"Balise après dernier <p> non valide: {tag_name}"

            # Vérification générale des balises équilibrées
            tag_balance = {}
            for tag in opening_tags:
                tag_balance[tag] = tag_balance.get(tag, 0) + 1
            for tag in closing_tags:
                tag_balance[tag] = tag_balance.get(tag, 0) - 1

            unbalanced = [tag for tag, count in tag_balance.items() if count != 0]
            if unbalanced:
                return False, f"Balises non équilibrées: {', '.join(unbalanced)}"

            return True, "HTML validé avec succès"

        except Exception as e:
            return False, f"Erreur validation: {str(e)}"

    def _save_html_extraction_config(self, html_content, extracted_text):
        """Sauvegarde la configuration d'extraction HTML"""
        try:
            if 'extraction_config' not in self.current_profile:
                self.current_profile['extraction_config'] = {}

            self.current_profile['extraction_config']['response_area'] = {
                'method': 'html',
                'sample_html': html_content[:500],  # Échantillon pour référence
                'sample_text': extracted_text[:200],  # Échantillon du texte
                'configured_at': time.time(),
                'wait_time': self.wait_extraction_spin.value()
            }

            # Sauvegarder en BDD
            self._save_profile()

        except Exception as e:
            logger.error(f"Erreur sauvegarde config HTML: {str(e)}")

    # ====================================================================
    # MÉTHODES CONSERVÉES (compatibilité et fonctionnalités de base)
    # ====================================================================

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
        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_platform_selected(self, index):
        """Gère la sélection d'une plateforme dans la liste"""
        if index <= 0:
            self.current_platform = None
            self.current_profile = None
            return
        platform_name = self.platform_combo.currentText()
        self._load_platform_config(platform_name)

    def _load_platform_config(self, platform_name):
        """Charge la configuration de la plateforme sélectionnée"""
        self.current_platform = platform_name
        self.current_profile = self.profiles.get(platform_name, {})

        if not self.current_profile:
            print(f"DEBUG: Profil vide pour {platform_name}!")
            return

        # Charger la configuration d'extraction
        extraction_config = self.current_profile.get('extraction_config', {})
        response_config = extraction_config.get('response_area', {})

        # Méthode d'extraction
        method = response_config.get('method', 'html')
        if method == 'html':
            self.extraction_method_combo.setCurrentIndex(0)
        elif method == 'clipboard':
            self.extraction_method_combo.setCurrentIndex(1)
        else:
            self.extraction_method_combo.setCurrentIndex(2)  # OCR

        # Temps d'attente
        self.wait_extraction_spin.setValue(response_config.get('wait_time', 3.0))

        # Vérifier si la configuration existe
        if response_config:
            self.capture_status.setText("✅ Configuration sauvegardée")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Si config HTML existe, activer l'extraction
            if response_config.get('method') == 'html':
                self.html_extract_button.setEnabled(True)
        else:
            self.capture_status.setText("⚠️ Aucune configuration")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def _on_save_config(self):
        """Enregistre la configuration de la zone de réponse"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        try:
            # Vérifier qu'on a une configuration d'extraction
            extraction_config = self.current_profile.get('extraction_config', {})
            if not extraction_config.get('response_area'):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Configuration manquante",
                    "Aucune configuration d'extraction. Effectuez d'abord le test et l'extraction HTML."
                )
                return

            # Mettre à jour les paramètres
            response_config = extraction_config['response_area']

            # Méthode
            method_index = self.extraction_method_combo.currentIndex()
            if method_index == 0:
                response_config['method'] = 'html'
            elif method_index == 1:
                response_config['method'] = 'clipboard'
            else:
                response_config['method'] = 'ocr'

            # Temps d'attente
            response_config['wait_time'] = self.wait_extraction_spin.value()

            # Sauvegarder
            success = self._save_profile()

            if success:
                self.response_area_configured.emit(self.current_platform, response_config)
                QtWidgets.QMessageBox.information(
                    self,
                    "Configuration enregistrée",
                    f"Configuration d'extraction pour {self.current_platform} sauvegardée avec succès."
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur d'enregistrement",
                    "Impossible d'enregistrer la configuration."
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

            # Méthode 3: Sauvegarde directe dans un fichier (fallback)
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