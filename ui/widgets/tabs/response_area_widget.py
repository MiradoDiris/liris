#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/response_area_widget.py - VERSION REFACTORISÉE

Approche en 2 phases distinctes :
1. PARAMÉTRAGE : Configuration des sélecteurs CSS et extraction
2. VALIDATION : Test utilisateur OBLIGATOIRE avant sauvegarde
"""

import os
import json
import time
import pyperclip
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle


class ResponseAreaWidget(QtWidgets.QWidget):
    """Widget de configuration de la zone de réponse - 2 phases distinctes"""

    # Signaux
    response_area_configured = pyqtSignal(str, dict)  # Plateforme, configuration
    response_area_detected = pyqtSignal(str, dict)  # Plateforme, position (pour compatibilité)
    response_received = pyqtSignal(str, str)  # Plateforme, contenu de la réponse

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # États de workflow
        self.configuration_phase_complete = False
        self.validation_phase_complete = False
        self.test_running = False

        # Résultats temporaires (avant validation)
        self.temp_extracted_text = ""
        self.temp_extraction_config = {}

        self._init_ui()

    def _init_ui(self):
        """Interface 2 colonnes avec workflow en 2 phases distinctes"""
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
        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        # Statut de la plateforme
        self.platform_status = QtWidgets.QLabel("Sélectionnez une plateforme...")
        self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.platform_status.setWordWrap(True)
        platform_layout.addWidget(self.platform_status)

        left_column.addWidget(platform_group)

        # === Section 2: Actions Phase 1 - Paramétrage ===
        config_actions_group = QtWidgets.QGroupBox("⚙️ Phase 1 : Paramétrage")
        config_actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_actions_group.setMaximumWidth(300)
        config_actions_layout = QtWidgets.QVBoxLayout(config_actions_group)

        # Bouton d'envoi de prompt pour générer une réponse
        self.send_prompt_button = QtWidgets.QPushButton("🚀 1. Envoyer un prompt de test")
        self.send_prompt_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.send_prompt_button.clicked.connect(self._send_test_prompt)
        config_actions_layout.addWidget(self.send_prompt_button)

        # Prompt personnalisable
        self.prompt_text_input = QtWidgets.QLineEdit()
        self.prompt_text_input.setText("Explique-moi brièvement ce qu'est l'intelligence artificielle")
        self.prompt_text_input.setPlaceholderText("Prompt pour générer une réponse...")
        self.prompt_text_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        config_actions_layout.addWidget(self.prompt_text_input)

        # Statut de la phase 1
        self.config_phase_status = QtWidgets.QLabel("⏳ Envoyez d'abord un prompt")
        self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.config_phase_status.setWordWrap(True)
        config_actions_layout.addWidget(self.config_phase_status)

        left_column.addWidget(config_actions_group)

        # === Section 3: Actions Phase 2 - Validation ===
        validation_actions_group = QtWidgets.QGroupBox("✅ Phase 2 : Validation")
        validation_actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        validation_actions_group.setMaximumWidth(300)
        validation_actions_layout = QtWidgets.QVBoxLayout(validation_actions_group)

        # Boutons de validation utilisateur (verticaux)
        self.validate_ok_button = QtWidgets.QPushButton("✅ Valider")
        self.validate_ok_button.setToolTip("Valider et sauvegarder la configuration")
        self.validate_ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
                min-height: 25px;
            }
            QPushButton:hover { background-color: #45A049; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        self.validate_ok_button.clicked.connect(self._validate_and_save)
        self.validate_ok_button.setEnabled(False)
        validation_actions_layout.addWidget(self.validate_ok_button)

        self.validate_retry_button = QtWidgets.QPushButton("🔄 Reconfigurer")
        self.validate_retry_button.setToolTip("Recommencer la configuration")
        self.validate_retry_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
                min-height: 25px;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        self.validate_retry_button.clicked.connect(self._retry_configuration)
        self.validate_retry_button.setEnabled(False)
        validation_actions_layout.addWidget(self.validate_retry_button)

        # Statut de la phase 2
        self.validation_phase_status = QtWidgets.QLabel("⏳ Attendez la configuration...")
        self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.validation_phase_status.setWordWrap(True)
        validation_actions_layout.addWidget(self.validation_phase_status)

        left_column.addWidget(validation_actions_group)

        # === Section 4: Statut global ===
        global_status_group = QtWidgets.QGroupBox("📊 Statut Global")
        global_status_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        global_status_group.setMaximumWidth(300)
        global_status_layout = QtWidgets.QVBoxLayout(global_status_group)

        self.global_status = QtWidgets.QLabel("🔄 Configuration en attente")
        self.global_status.setAlignment(Qt.AlignCenter)
        self.global_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.global_status.setWordWrap(True)
        global_status_layout.addWidget(self.global_status)

        left_column.addWidget(global_status_group)

        # Spacer
        left_column.addStretch(1)

        # =============================
        # COLONNE DROITE - CONFIGURATION ET VALIDATION
        # =============================
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(15)

        # === PHASE 1 : Sélection manuelle HTML ===
        config_group = QtWidgets.QGroupBox("📋 PHASE 1 : Collez le HTML de la réponse")
        config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_layout = QtWidgets.QVBoxLayout(config_group)

        # Instructions
        instructions = QtWidgets.QLabel(
            "<b>Instructions :</b><br>"
            "1. 🚀 Envoyez d'abord un prompt et attendez la réponse complète<br>"
            "2. 🔧 F12 → Clic droit sur la réponse IA → Inspecter<br>"
            "3. 📋 Clic droit sur l'élément HTML → Copy → Copy element<br>"
            "4. 📥 Collez le HTML ci-dessous (extraction automatique)"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #2196F3; font-size: 10px; margin-bottom: 10px;")
        config_layout.addWidget(instructions)

        # Zone de saisie HTML
        self.html_input = QtWidgets.QTextEdit()
        self.html_input.setPlaceholderText(
            "Collez ici le HTML de la réponse IA (extraction automatique dès collage)...")
        self.html_input.setMaximumHeight(120)
        self.html_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.html_input.textChanged.connect(self._on_html_changed)
        config_layout.addWidget(self.html_input)

        # Sélecteurs générés
        selectors_label = QtWidgets.QLabel("🎯 Sélecteurs CSS générés :")
        selectors_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        config_layout.addWidget(selectors_label)

        self.detected_selectors = QtWidgets.QTextEdit()
        self.detected_selectors.setMaximumHeight(80)
        self.detected_selectors.setReadOnly(True)
        self.detected_selectors.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.detected_selectors.setPlaceholderText("Les sélecteurs CSS et le texte extrait apparaîtront ici...")
        config_layout.addWidget(self.detected_selectors)

        right_column.addWidget(config_group)

        # === PHASE 2 : Validation ===
        validation_group = QtWidgets.QGroupBox("✅ PHASE 2 : Validation du texte extrait")
        validation_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        validation_layout = QtWidgets.QVBoxLayout(validation_group)

        # Texte extrait pour validation
        extracted_label = QtWidgets.QLabel("📄 Texte extrait (vérifiez qu'il est correct) :")
        extracted_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        validation_layout.addWidget(extracted_label)

        self.extracted_preview = QtWidgets.QTextEdit()
        self.extracted_preview.setMaximumHeight(150)
        self.extracted_preview.setReadOnly(True)
        self.extracted_preview.setStyleSheet(
            "background-color: #f0f8ff; border: 1px solid #2196F3; border-radius: 4px; padding: 8px;"
        )
        self.extracted_preview.setPlaceholderText("Le texte extrait apparaîtra ici pour validation...")
        validation_layout.addWidget(self.extracted_preview)

        # Instructions de validation
        validation_instructions = QtWidgets.QLabel(
            "<b>⚠️ Instructions de validation :</b><br>"
            "• Vérifiez que le texte extrait correspond exactement à la réponse IA<br>"
            "• Assurez-vous qu'il n'y a pas de texte parasite (boutons, menus, etc.)<br>"
            "• Cliquez 'Valider' seulement si l'extraction est parfaite<br>"
            "• Sinon, cliquez 'Reconfigurer' pour recommencer"
        )
        validation_instructions.setWordWrap(True)
        validation_instructions.setStyleSheet("color: #D32F2F; font-size: 10px; margin-top: 10px;")
        validation_layout.addWidget(validation_instructions)

        right_column.addWidget(validation_group)

        # Spacer
        right_column.addStretch(1)

        # ========================
        # ASSEMBLAGE DES COLONNES
        # ========================
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(320)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

    # ====================================================================
    # GESTION DES PLATEFORMES
    # ====================================================================

    def set_profiles(self, profiles):
        """Met à jour les profils disponibles"""
        self.profiles = profiles
        self._update_platform_combo()

    def select_platform(self, platform_name):
        """Sélectionne une plateforme"""
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        """Actualise le widget"""
        self._update_platform_combo()

    def _update_platform_combo(self):
        """Met à jour la liste des plateformes"""
        current_text = self.platform_combo.currentText()

        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionnez une plateforme --")

        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)

        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_platform_changed(self, platform_name):
        """Gère le changement de plateforme"""
        if platform_name and platform_name != "-- Sélectionnez une plateforme --":
            self.current_platform = platform_name
            self.current_profile = self.profiles.get(platform_name, {})
            self._update_platform_status()
            self._reset_workflow()
            # NOUVEAU : Charger la configuration existante depuis la DB
            self._load_existing_configuration()
        else:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()

    def _load_existing_configuration(self):
        """Charge la configuration existante depuis la base de données"""
        if not self.current_platform:
            return

        try:
            # Essayer de charger depuis la DB d'abord
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_platform'):
                    saved_profile = self.conductor.database.get_platform(self.current_platform)

                    if saved_profile:
                        self.current_profile = saved_profile
                        extraction_config = saved_profile.get('extraction_config', {})
                        response_area = extraction_config.get('response_area', {})

                        if response_area:
                            self._display_existing_configuration(response_area)
                            return

            # Fallback vers les profils en mémoire
            extraction_config = self.current_profile.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})

            if response_area:
                self._display_existing_configuration(response_area)

        except Exception as e:
            logger.error(f"Erreur chargement configuration pour {self.current_platform}: {str(e)}")

    def _display_existing_configuration(self, response_area):
        """Affiche la configuration existante dans l'interface"""
        try:
            # Afficher le prompt sauvegardé
            saved_prompt = response_area.get('prompt_text',
                                             'Explique-moi brièvement ce qu\'est l\'intelligence artificielle')
            self.prompt_text_input.blockSignals(True)  # Éviter les callbacks
            self.prompt_text_input.setText(saved_prompt)
            self.prompt_text_input.blockSignals(False)

            # Afficher la configuration
            platform_config = response_area.get('platform_config', {})
            primary_selector = platform_config.get('primary_selector', 'Non défini')
            fallback_selectors = platform_config.get('fallback_selectors', [])

            config_text = f"Sélecteur principal: {primary_selector}\n"
            if fallback_selectors:
                config_text += f"Sélecteurs de fallback: {', '.join(fallback_selectors)}\n"
            config_text += f"Méthode: {platform_config.get('extraction_method', 'css_selector_with_cleaning')}\n"

            # Afficher le texte d'exemple
            sample_text = response_area.get('sample_text', response_area.get('full_sample', ''))
            if sample_text:
                config_text += f"Texte d'exemple: {sample_text[:100]}..."

            self.detected_selectors.setPlainText(config_text)

            # Afficher le texte complet dans la zone de validation
            full_text = response_area.get('full_sample', sample_text)
            if full_text:
                self.extracted_preview.setPlainText(full_text)

            # Marquer comme configuré et validé
            self.configuration_phase_complete = True
            self.validation_phase_complete = True

            # Mettre à jour les statuts
            self.config_phase_status.setText("✅ Configuration existante chargée")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            self.validation_phase_status.setText("✅ Configuration validée précédemment")
            self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Désactiver les boutons de validation (déjà fait)
            self.validate_ok_button.setEnabled(False)
            self.validate_retry_button.setEnabled(True)  # Permettre la reconfiguration

            self._update_global_status()

            logger.info(f"Configuration existante chargée pour {self.current_platform}")

        except Exception as e:
            logger.error(f"Erreur affichage configuration pour {self.current_platform}: {str(e)}")

    def _update_platform_status(self):
        """Met à jour le statut de la plateforme sélectionnée"""
        if not self.current_platform or not self.current_profile:
            return

        # Vérifier les prérequis
        browser_config = self.current_profile.get('browser', {})
        interface_positions = self.current_profile.get('interface_positions', {})

        missing_items = []
        if not browser_config.get('url'):
            missing_items.append("URL navigateur")
        if not interface_positions.get('prompt_field'):
            missing_items.append("Champ prompt")

        if missing_items:
            self.platform_status.setText(f"⚠️ Manque: {', '.join(missing_items)}")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
            self.send_prompt_button.setEnabled(False)
        else:
            self.platform_status.setText("✅ Plateforme prête pour configuration")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.send_prompt_button.setEnabled(True)
        """Met à jour le statut de la plateforme sélectionnée"""
        if not self.current_platform or not self.current_profile:
            return

        # Vérifier les prérequis
        browser_config = self.current_profile.get('browser', {})
        interface_positions = self.current_profile.get('interface_positions', {})

        missing_items = []
        if not browser_config.get('url'):
            missing_items.append("URL navigateur")
        if not interface_positions.get('prompt_field'):
            missing_items.append("Champ prompt")

        if missing_items:
            self.platform_status.setText(f"⚠️ Manque: {', '.join(missing_items)}")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
            self.send_prompt_button.setEnabled(False)
        else:
            self.platform_status.setText("✅ Plateforme prête pour configuration")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.send_prompt_button.setEnabled(True)

    # ====================================================================
    # PHASE 1 : PARAMÉTRAGE
    # ====================================================================

    def _send_test_prompt(self):
        """Envoie un prompt de test pour générer une réponse IA"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune plateforme sélectionnée")
            return

        try:
            self.send_prompt_button.setEnabled(False)
            self.config_phase_status.setText("🚀 Envoi du prompt en cours...")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

            # Utiliser l'automatisation existante
            from core.interaction.mouse import MouseController
            from core.interaction.keyboard import KeyboardController
            from core.orchestration.state_automation import StateBasedAutomation

            mouse_controller = MouseController()
            keyboard_controller = KeyboardController()

            state_automation = StateBasedAutomation(
                self.conductor.detector,
                mouse_controller,
                keyboard_controller,
                self.conductor
            )

            def on_automation_completed(success, message, duration):
                self.send_prompt_button.setEnabled(True)
                if success:
                    self.config_phase_status.setText("✅ Prompt envoyé - Collez maintenant le HTML")
                    self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                    QtWidgets.QMessageBox.information(
                        self,
                        "Prompt envoyé",
                        f"✅ Prompt envoyé avec succès en {duration:.1f}s\n\n"
                        f"Maintenant :\n"
                        f"1. Attendez que l'IA termine sa réponse complètement\n"
                        f"2. F12 → Clic droit sur la réponse → Inspecter\n"
                        f"3. Clic droit sur l'élément HTML → Copy element\n"
                        f"4. Collez dans la zone HTML (extraction automatique)"
                    )
                else:
                    self.config_phase_status.setText(f"❌ Erreur: {message}")
                    self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            state_automation.automation_completed.connect(on_automation_completed)

            # Paramètres d'automatisation
            automation_params = {
                'use_tab_navigation': False,
                'use_enter_to_submit': True,
                'wait_before_submit': 1.0,
                'test_text': self.prompt_text_input.text().strip()
            }

            # Démarrer l'automatisation
            state_automation.start_test_automation(
                self.current_profile,
                0,
                self.current_profile.get('browser', {}).get('type', 'Chrome'),
                self.current_profile.get('browser', {}).get('url'),
                automation_params
            )

        except Exception as e:
            self.send_prompt_button.setEnabled(True)
            self.config_phase_status.setText(f"❌ Erreur: {str(e)}")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec de l'envoi: {str(e)}")

    def _on_html_changed(self):
        """Analyse automatique dès qu'il y a du HTML valide"""
        html_content = self.html_input.toPlainText().strip()

        if len(html_content) > 100:  # Minimum raisonnable pour du HTML de réponse
            # Délai pour éviter l'analyse à chaque caractère
            if hasattr(self, '_analysis_timer'):
                self._analysis_timer.stop()

            self._analysis_timer = QtCore.QTimer()
            self._analysis_timer.setSingleShot(True)
            self._analysis_timer.timeout.connect(self._auto_analyze_html)
            self._analysis_timer.start(1000)  # Attendre 1 seconde après arrêt de saisie

    def _auto_analyze_html(self):
        """Analyse automatique du HTML"""
        html_content = self.html_input.toPlainText().strip()

        if not html_content:
            return

        try:
            self.config_phase_status.setText("🔍 Analyse automatique du HTML...")

            # Analyser le HTML et générer la configuration
            analysis_result = self._analyze_html_structure(html_content)

            # Afficher les sélecteurs générés et le texte extrait
            selectors_text = f"Sélecteur principal: {analysis_result['primary_selector']}\n"
            if analysis_result.get('fallback_selectors'):
                selectors_text += f"Sélecteurs de fallback: {', '.join(analysis_result['fallback_selectors'])}\n"
            selectors_text += f"Méthode: {analysis_result['extraction_method']}\n"
            selectors_text += f"Texte extrait: {analysis_result.get('sample_text', '')[:100]}..."

            self.detected_selectors.setPlainText(selectors_text)

            # Afficher le texte extrait pour validation
            full_text = analysis_result.get('sample_text', '')
            self.extracted_preview.setPlainText(full_text)

            # Sauvegarder temporairement
            self.temp_extraction_config = analysis_result
            self.temp_extraction_config['original_html'] = html_content
            self.temp_extracted_text = full_text

            # Marquer la phase 1 comme terminée
            self.configuration_phase_complete = True
            self.config_phase_status.setText("✅ HTML analysé automatiquement")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Activer la phase 2 directement
            self.validate_ok_button.setEnabled(True)
            self.validate_retry_button.setEnabled(True)
            self.validation_phase_status.setText("✅ Prêt pour validation - Vérifiez le texte extrait")
            self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

            self._update_global_status()

        except Exception as e:
            self.config_phase_status.setText(f"❌ Erreur d'analyse: {str(e)}")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

    def _analyze_html(self):
        """Analyse le HTML fourni par l'utilisateur et génère les sélecteurs"""
        html_content = self.html_input.toPlainText().strip()

        if not html_content:
            QtWidgets.QMessageBox.warning(self, "HTML manquant", "Veuillez coller le HTML dans la zone de texte.")
            return

        try:
            self.analyze_html_button.setEnabled(False)
            self.config_phase_status.setText("🔍 Analyse du HTML en cours...")

            # Analyser le HTML et générer la configuration
            analysis_result = self._analyze_html_structure(html_content)

            # Afficher les sélecteurs générés
            selectors_text = f"Sélecteur principal: {analysis_result['primary_selector']}\n"
            if analysis_result['fallback_selectors']:
                selectors_text += f"Sélecteurs de fallback: {', '.join(analysis_result['fallback_selectors'])}\n"
            selectors_text += f"Méthode: {analysis_result['extraction_method']}"

            self.detected_selectors.setPlainText(selectors_text)

            # Sauvegarder temporairement
            self.temp_extraction_config = analysis_result
            self.temp_extraction_config['original_html'] = html_content

            # Marquer la phase 1 comme terminée
            self.configuration_phase_complete = True
            self.config_phase_status.setText("✅ HTML analysé - Configuration prête")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Activer la phase 2
            self.test_extraction_button.setEnabled(True)
            self.validation_phase_status.setText("🧪 Prêt pour le test d'extraction")
            self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

            self._update_global_status()

            QtWidgets.QMessageBox.information(
                self,
                "Analyse terminée",
                f"✅ HTML analysé avec succès !\n\n"
                f"Sélecteur généré: {analysis_result['primary_selector']}\n\n"
                f"Cliquez maintenant sur 'Tester l'extraction' pour valider."
            )

        except Exception as e:
            self.analyze_html_button.setEnabled(True)
            self.config_phase_status.setText(f"❌ Erreur d'analyse: {str(e)}")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(self, "Erreur d'analyse", f"Impossible d'analyser le HTML:\n{str(e)}")

    def _analyze_html_structure(self, html_content):
        """Analyse la structure HTML et génère les sélecteurs appropriés"""
        import re

        # Extraire d'abord le texte pour référence
        temp_extracted_text = self._extract_text_from_html(html_content)

        # Analyser la structure pour créer des sélecteurs
        analysis = {
            'platform_type': self._detect_platform_from_html(html_content),
            'primary_selector': '',
            'fallback_selectors': [],
            'extraction_method': 'css_selector_with_cleaning',
            'text_cleaning': 'remove_attributes_and_normalize',
            'sample_text': temp_extracted_text
        }

        # Générer le sélecteur principal basé sur les attributs trouvés
        classes = re.findall(r'class="([^"]*)"', html_content)
        ids = re.findall(r'id="([^"]*)"', html_content)

        # Stratégie de sélecteur selon la plateforme détectée
        if analysis['platform_type'] == 'ChatGPT':
            # Chercher les attributs spécifiques ChatGPT
            if 'data-message-author-role' in html_content:
                analysis['primary_selector'] = '[data-message-author-role="assistant"]'
            elif classes and any('markdown' in c for c in classes):
                analysis['primary_selector'] = '.markdown'
            else:
                analysis['primary_selector'] = self._generate_generic_selector(classes, ids)
        elif analysis['platform_type'] == 'Claude':
            if 'data-is-streaming' in html_content:
                analysis['primary_selector'] = '[data-is-streaming="false"]'
            elif classes and any('prose' in c for c in classes):
                analysis['primary_selector'] = '.prose'
            else:
                analysis['primary_selector'] = self._generate_generic_selector(classes, ids)
        else:
            # Générique
            analysis['primary_selector'] = self._generate_generic_selector(classes, ids)

        # Générer des sélecteurs de fallback
        if classes:
            main_classes = [c for c in classes if c and len(c) > 2 and not c.startswith('[')]
            analysis['fallback_selectors'] = [f'.{c}' for c in main_classes[:3]]

        return analysis

    def _detect_platform_from_html(self, html_content):
        """Détecte la plateforme à partir du HTML"""
        if 'data-message-author-role' in html_content:
            return 'ChatGPT'
        elif 'data-is-streaming' in html_content or 'claude' in html_content.lower():
            return 'Claude'
        elif 'gemini' in html_content.lower() or 'bard' in html_content.lower():
            return 'Gemini'
        else:
            return 'Générique'

    def _generate_generic_selector(self, classes, ids):
        """Génère un sélecteur générique basé sur les classes et IDs"""
        if ids:
            return f'#{ids[0]}'
        elif classes:
            # Prendre la première classe significative
            for class_name in classes:
                if class_name and len(class_name) > 2 and class_name not in ['flex', 'p-2', 'm-1']:
                    return f'.{class_name}'
        return 'div'  # Fallback ultime

    def _extract_text_from_html(self, html_content):
        """Extrait le texte pur du HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Supprimer les éléments indésirables
            for unwanted in soup(['script', 'style', 'button', 'svg']):
                unwanted.decompose()

            # Extraire le texte
            text = soup.get_text(separator=' ', strip=True)
            return ' '.join(text.split())  # Normaliser les espaces
        except ImportError:
            # Fallback sans BeautifulSoup
            import re
            # Supprimer les balises HTML
            text = re.sub(r'<[^>]+>', '', html_content)
            # Normaliser les espaces
            text = ' '.join(text.split())
            return text

    # ====================================================================
    # PHASE 2 : VALIDATION
    # ====================================================================

    def _validate_and_save(self):
        """Validation par l'utilisateur et sauvegarde de la configuration"""
        if not self.temp_extracted_text or not self.temp_extraction_config:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun résultat à valider")
            return

        # Demander confirmation à l'utilisateur
        reply = QtWidgets.QMessageBox.question(
            self,
            "Validation de l'extraction",
            f"Le texte extrait vous semble-t-il correct ?\n\n"
            f"Texte: {self.temp_extracted_text[:100]}...\n\n"
            f"✅ OUI : Sauvegarder cette configuration\n"
            f"❌ NON : Recommencer la configuration",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self._save_validated_configuration()
        else:
            self._retry_configuration()

    def _save_validated_configuration(self):
        """Sauvegarde la configuration validée"""
        try:
            # Préparer la configuration finale
            final_config = {
                'method': 'smart_css_extraction',
                'platform_config': self.temp_extraction_config,
                'sample_text': self.temp_extracted_text[:200],
                'full_sample': self.temp_extracted_text,
                'configured_at': time.time(),
                'prompt_text': self.prompt_text_input.text().strip(),
                'validation_status': 'user_validated'
            }

            # Sauvegarder dans le profil
            if 'extraction_config' not in self.current_profile:
                self.current_profile['extraction_config'] = {}

            self.current_profile['extraction_config']['response_area'] = final_config

            # Sauvegarder en base de données ou fichier
            success = self._save_to_database()

            if success:
                self.validation_phase_complete = True
                self.validation_phase_status.setText("✅ Configuration sauvegardée avec succès")
                self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                self._update_global_status()

                # Désactiver les boutons de validation
                self.validate_ok_button.setEnabled(False)
                self.validate_retry_button.setEnabled(False)

                # Émettre les signaux
                self.response_area_configured.emit(self.current_platform, final_config)
                self.response_area_detected.emit(self.current_platform,
                                                 {'response_area': final_config})  # Compatibilité
                self.response_received.emit(self.current_platform, self.temp_extracted_text)

                QtWidgets.QMessageBox.information(
                    self,
                    "Configuration sauvegardée",
                    f"✅ Configuration d'extraction sauvegardée avec succès pour {self.current_platform}\n\n"
                    f"Vous pouvez maintenant utiliser l'onglet 'Test Final' pour valider le workflow complet."
                )
            else:
                raise Exception("Échec de sauvegarde en base de données")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de sauvegarde",
                f"Impossible de sauvegarder la configuration:\n{str(e)}"
            )

    def _save_to_database(self):
        """Sauvegarde en base de données avec fallback vers fichier"""
        try:
            # Essayer la base de données d'abord
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    return self.conductor.database.save_platform(self.current_platform, self.current_profile)

            # Fallback vers fichier JSON
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {str(e)}")
            return False

    def _retry_configuration(self):
        """Recommence la configuration"""
        self.temp_extracted_text = ""
        self.temp_extraction_config = {}
        self.configuration_phase_complete = False
        self.validation_phase_complete = False

        # Réactiver la phase 1
        self.config_phase_status.setText("📋 Reconfiguration - Collez le HTML de nouveau")
        self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

        # Désactiver la phase 2
        self.validate_ok_button.setEnabled(False)
        self.validate_retry_button.setEnabled(False)

        # Nettoyer les affichages
        self.html_input.clear()
        self.detected_selectors.clear()
        self.extracted_preview.clear()

        self._update_global_status()

    # ====================================================================
    # UTILITAIRES
    # ====================================================================

    def _reset_workflow(self):
        """Remet à zéro le workflow"""
        self.configuration_phase_complete = False
        self.validation_phase_complete = False
        self.temp_extracted_text = ""
        self.temp_extraction_config = {}

        # Réinitialiser l'interface
        self.validate_ok_button.setEnabled(False)
        self.validate_retry_button.setEnabled(False)

        self.config_phase_status.setText("⏳ Envoyez d'abord un prompt")
        self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

        self.validation_phase_status.setText("⏳ Attendez la configuration...")
        self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

        self._update_global_status()

    def _reset_interface(self):
        """Remet l'interface complètement à zéro"""
        self._reset_workflow()

        self.platform_status.setText("Sélectionnez une plateforme...")
        self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

        # Nettoyer tous les affichages
        self.html_input.clear()
        self.detected_selectors.clear()
        self.extracted_preview.clear()

    def _update_global_status(self):
        """Met à jour le statut global du workflow"""
        if self.validation_phase_complete:
            self.global_status.setText("✅ Configuration complète et validée")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        elif self.configuration_phase_complete:
            self.global_status.setText("🧪 Configuration prête - Validation requise")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
        else:
            self.global_status.setText("🔄 Configuration en cours")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())