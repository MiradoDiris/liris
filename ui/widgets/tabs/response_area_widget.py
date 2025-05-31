#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/response_area_widget.py - VERSION CORRIGÉE EXTRACTION

CORRECTIONS PRINCIPALES :
1. Priorisation élément ARTICLE pour ChatGPT
2. Sélecteurs CSS optimisés et robustes
3. Détection de plateforme améliorée
4. Validation d'extraction renforcée
5. Fallbacks intelligents pour chaque plateforme
"""

import os
import json
import time
import re
import pyperclip
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle


class ResponseAreaWidget(QtWidgets.QWidget):
    """Widget de configuration zone réponse - EXTRACTION CORRIGÉE"""

    # Signaux
    response_area_configured = pyqtSignal(str, dict)  # Plateforme, configuration
    response_area_detected = pyqtSignal(str, dict)  # Plateforme, position (compatibilité)
    response_received = pyqtSignal(str, str)  # Plateforme, contenu réponse

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # États workflow
        self.configuration_phase_complete = False
        self.validation_phase_complete = False
        self.test_running = False

        # Résultats temporaires (avant validation)
        self.temp_extracted_text = ""
        self.temp_extraction_config = {}

        self._init_ui()

    def _init_ui(self):
        """Interface 2 colonnes avec workflow optimisé"""
        # Layout principal horizontal (2 colonnes)
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ============================
        # COLONNE GAUCHE - CONTRÔLES
        # ============================
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(15)

        # === Section 1: Sélection plateforme ===
        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        # Statut plateforme
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

        # Bouton envoi prompt test
        self.send_prompt_button = QtWidgets.QPushButton("🚀 1. Envoyer un prompt de test")
        self.send_prompt_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.send_prompt_button.clicked.connect(self._send_test_prompt)
        config_actions_layout.addWidget(self.send_prompt_button)

        # Prompt personnalisable
        self.prompt_text_input = QtWidgets.QLineEdit()
        self.prompt_text_input.setText("Explique-moi brièvement les remèdes naturels contre les maux de tête")
        self.prompt_text_input.setPlaceholderText("Prompt pour générer une réponse...")
        self.prompt_text_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        config_actions_layout.addWidget(self.prompt_text_input)

        # Statut phase 1
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

        # Boutons validation utilisateur
        self.validate_ok_button = QtWidgets.QPushButton("✅ Valider & Sauvegarder")
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

        # Statut phase 2
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

        # Instructions améliorées
        instructions = QtWidgets.QLabel(
            "<b>Instructions OPTIMISÉES :</b><br>"
            "1. 🚀 Envoyez d'abord un prompt et attendez la réponse complète<br>"
            "2. 🔧 F12 → Clic droit sur la RÉPONSE IA (pas les boutons) → Inspecter<br>"
            "3. 📋 Clic droit sur l'élément HTML <b>ARTICLE</b> → Copy → Copy element<br>"
            "4. 📥 Collez le HTML ci-dessous (extraction automatique optimisée)<br>"
            "<b>🎯 IMPORTANT : Viser l'élément ARTICLE complet pour ChatGPT</b>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #2196F3; font-size: 10px; margin-bottom: 10px;")
        config_layout.addWidget(instructions)

        # Zone saisie HTML
        self.html_input = QtWidgets.QTextEdit()
        self.html_input.setPlaceholderText(
            "Collez ici le HTML de la réponse IA (élément ARTICLE complet de préférence)...")
        self.html_input.setMaximumHeight(120)
        self.html_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.html_input.textChanged.connect(self._on_html_changed)
        config_layout.addWidget(self.html_input)

        # Sélecteurs générés
        selectors_label = QtWidgets.QLabel("🎯 Sélecteurs CSS générés (OPTIMISÉS) :")
        selectors_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        config_layout.addWidget(selectors_label)

        self.detected_selectors = QtWidgets.QTextEdit()
        self.detected_selectors.setMaximumHeight(80)
        self.detected_selectors.setReadOnly(True)
        self.detected_selectors.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.detected_selectors.setPlaceholderText("Les sélecteurs CSS optimisés apparaîtront ici...")
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

        # Instructions validation
        validation_instructions = QtWidgets.QLabel(
            "<b>⚠️ Instructions de validation :</b><br>"
            "• Vérifiez que le texte extrait correspond exactement à la réponse IA<br>"
            "• Assurez-vous qu'il n'y a pas de code JavaScript ou texte parasite<br>"
            "• Le texte doit commencer par la vraie réponse de l'IA<br>"
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
        # ASSEMBLAGE COLONNES
        # ========================
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(320)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

    # ====================================================================
    # GESTION PLATEFORMES
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
            # Essayer charger depuis DB d'abord
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

            # Fallback vers profils mémoire
            extraction_config = self.current_profile.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})

            if response_area:
                self._display_existing_configuration(response_area)

        except Exception as e:
            logger.error(f"Erreur chargement configuration pour {self.current_platform}: {str(e)}")

    def _display_existing_configuration(self, response_area):
        """Affiche la configuration existante dans l'interface"""
        try:
            # Afficher prompt sauvegardé
            saved_prompt = response_area.get('prompt_text',
                                             'Explique-moi brièvement les remèdes naturels contre les maux de tête')
            self.prompt_text_input.blockSignals(True)
            self.prompt_text_input.setText(saved_prompt)
            self.prompt_text_input.blockSignals(False)

            # Afficher configuration
            platform_config = response_area.get('platform_config', {})
            primary_selector = platform_config.get('primary_selector', 'Non défini')
            fallback_selectors = platform_config.get('fallback_selectors', [])

            config_text = f"Sélecteur principal: {primary_selector}\n"
            if fallback_selectors:
                config_text += f"Sélecteurs de fallback: {', '.join(fallback_selectors[:3])}\n"
            config_text += f"Méthode: {platform_config.get('extraction_method', 'css_selector_with_cleaning')}\n"

            # Afficher texte exemple
            sample_text = response_area.get('sample_text', response_area.get('full_sample', ''))
            if sample_text:
                config_text += f"Texte d'exemple: {sample_text[:100]}..."

            self.detected_selectors.setPlainText(config_text)

            # Afficher texte complet dans zone validation
            full_text = response_area.get('full_sample', sample_text)
            if full_text:
                self.extracted_preview.setPlainText(full_text)

            # Marquer comme configuré et validé
            self.configuration_phase_complete = True
            self.validation_phase_complete = True

            # Mettre à jour statuts
            self.config_phase_status.setText("✅ Configuration existante chargée")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            self.validation_phase_status.setText("✅ Configuration validée précédemment")
            self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Boutons validation
            self.validate_ok_button.setEnabled(False)
            self.validate_retry_button.setEnabled(True)  # Permettre reconfiguration

            self._update_global_status()

            logger.info(f"Configuration existante chargée pour {self.current_platform}")

        except Exception as e:
            logger.error(f"Erreur affichage configuration pour {self.current_platform}: {str(e)}")

    def _update_platform_status(self):
        """Met à jour le statut de la plateforme sélectionnée"""
        if not self.current_platform or not self.current_profile:
            return

        # Vérifier prérequis
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

            # Utiliser automatisation existante
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

            def on_automation_completed(success, message, duration, response):
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
                        f"3. Clic droit sur l'élément HTML ARTICLE → Copy element\n"
                        f"4. Collez dans la zone HTML (extraction automatique optimisée)"
                    )
                else:
                    self.config_phase_status.setText(f"❌ Erreur: {message}")
                    self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            state_automation.automation_completed.connect(on_automation_completed)

            # Paramètres automatisation
            automation_params = {
                'use_tab_navigation': False,
                'use_enter_to_submit': True,
                'wait_before_submit': 1.0,
                'test_text': self.prompt_text_input.text().strip()
            }

            # Démarrer automatisation
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

        if len(html_content) > 100:  # Minimum raisonnable pour HTML réponse
            # Délai pour éviter analyse à chaque caractère
            if hasattr(self, '_analysis_timer'):
                self._analysis_timer.stop()

            self._analysis_timer = QtCore.QTimer()
            self._analysis_timer.setSingleShot(True)
            self._analysis_timer.timeout.connect(self._auto_analyze_html)
            self._analysis_timer.start(1000)  # Attendre 1 seconde après arrêt saisie

    def _auto_analyze_html(self):
        """Analyse automatique du HTML OPTIMISÉE"""
        html_content = self.html_input.toPlainText().strip()

        if not html_content:
            return

        try:
            self.config_phase_status.setText("🔍 Analyse automatique OPTIMISÉE du HTML...")

            # Analyser HTML et générer configuration OPTIMISÉE
            analysis_result = self._analyze_html_structure_optimized(html_content)

            # Afficher sélecteurs générés et texte extrait
            selectors_text = f"Sélecteur principal: {analysis_result['primary_selector']}\n"
            if analysis_result.get('fallback_selectors'):
                selectors_text += f"Sélecteurs de fallback: {', '.join(analysis_result['fallback_selectors'][:3])}\n"
            selectors_text += f"Méthode: {analysis_result['extraction_method']}\n"
            selectors_text += f"Plateforme détectée: {analysis_result.get('platform_type', 'Générique')}\n"
            selectors_text += f"Texte extrait: {analysis_result.get('sample_text', '')[:100]}..."

            self.detected_selectors.setPlainText(selectors_text)

            # Afficher texte extrait pour validation
            full_text = analysis_result.get('sample_text', '')
            self.extracted_preview.setPlainText(full_text)

            # Sauvegarder temporairement
            self.temp_extraction_config = analysis_result
            self.temp_extraction_config['original_html'] = html_content
            self.temp_extracted_text = full_text

            # Validation automatique du texte extrait
            validation_result = self._validate_extracted_text(full_text)

            if validation_result['is_valid']:
                # Marquer phase 1 comme terminée
                self.configuration_phase_complete = True
                self.config_phase_status.setText("✅ HTML analysé automatiquement - Extraction validée")
                self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                # Activer phase 2 directement
                self.validate_ok_button.setEnabled(True)
                self.validate_retry_button.setEnabled(True)
                self.validation_phase_status.setText("✅ Prêt pour validation - Vérifiez le texte extrait")
                self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
            else:
                # Problème détecté dans l'extraction
                self.config_phase_status.setText(f"⚠️ Extraction douteuse: {validation_result['issue']}")
                self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

                self.validate_ok_button.setEnabled(True)  # Permettre validation manuelle
                self.validate_retry_button.setEnabled(True)
                self.validation_phase_status.setText("⚠️ Vérification requise - Extraction suspecte")
                self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            self._update_global_status()

        except Exception as e:
            self.config_phase_status.setText(f"❌ Erreur d'analyse: {str(e)}")
            self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

    def _analyze_html_structure_optimized(self, html_content):
        """Analyse structure HTML OPTIMISÉE avec priorité ARTICLE"""
        # Extraire texte pour référence
        temp_extracted_text = self._extract_text_from_html_optimized(html_content)

        # Analyser structure pour créer sélecteurs OPTIMISÉS
        analysis = {
            'platform_type': self._detect_platform_from_html_enhanced(html_content),
            'primary_selector': '',
            'fallback_selectors': [],
            'extraction_method': 'css_selector_with_cleaning',
            'text_cleaning': 'remove_attributes_and_normalize',
            'sample_text': temp_extracted_text
        }

        # Stratégies de sélecteurs OPTIMISÉES selon plateforme
        if analysis['platform_type'] == 'ChatGPT':
            analysis = self._generate_chatgpt_selectors_optimized(html_content, analysis)
        elif analysis['platform_type'] == 'Claude':
            analysis = self._generate_claude_selectors_optimized(html_content, analysis)
        elif analysis['platform_type'] == 'Gemini':
            analysis = self._generate_gemini_selectors_optimized(html_content, analysis)
        else:
            analysis = self._generate_generic_selectors_optimized(html_content, analysis)

        return analysis

    def _generate_chatgpt_selectors_optimized(self, html_content, analysis):
        """Génère sélecteurs OPTIMISÉS pour ChatGPT avec priorité ARTICLE"""
        # PRIORITÉ 1: Élément ARTICLE avec data-testid conversation-turn
        if 'data-testid' in html_content and 'conversation-turn' in html_content:
            analysis['primary_selector'] = 'article[data-testid*="conversation-turn"]:last-child'
            analysis['fallback_selectors'] = [
                'article[data-testid*="conversation-turn"]:last-of-type',
                'article[data-scroll-anchor="true"]:last-child',
                'article.w-full:last-child'
            ]
            logger.info("🎯 ChatGPT: Utilisation sélecteur ARTICLE optimisé")

        # PRIORITÉ 2: data-message-author-role assistant
        elif 'data-message-author-role="assistant"' in html_content:
            analysis['primary_selector'] = '[data-message-author-role="assistant"]:last-child'
            analysis['fallback_selectors'] = [
                '[data-message-author-role="assistant"]:last-of-type',
                '.group[data-message-author-role="assistant"]:last-child'
            ]

        # PRIORITÉ 3: Classes spécifiques ChatGPT
        elif 'markdown prose' in html_content:
            analysis['primary_selector'] = '.markdown.prose:last-child'
            analysis['fallback_selectors'] = [
                '.prose.dark\\:prose-invert:last-child',
                '.markdown:last-child'
            ]

        # PRIORITÉ 4: Structure générale ChatGPT
        else:
            classes = re.findall(r'class="([^"]*)"', html_content)
            if classes:
                main_classes = [c for c in classes if c and len(c) > 5]
                if main_classes:
                    analysis['primary_selector'] = f'.{main_classes[0].split()[0]}'
                    analysis['fallback_selectors'] = [f'.{c.split()[0]}' for c in main_classes[1:4]]

        # Ajouter sélecteurs de sécurité ChatGPT
        analysis['fallback_selectors'].extend([
            '[data-start][data-end]:last-child',
            '.group.w-full:last-child',
            'div[data-message-id]:last-child'
        ])

        return analysis

    def _generate_claude_selectors_optimized(self, html_content, analysis):
        """Génère sélecteurs OPTIMISÉS pour Claude"""
        if 'data-is-streaming' in html_content:
            analysis['primary_selector'] = '[data-is-streaming="false"]:last-child'
            analysis['fallback_selectors'] = [
                '[data-is-streaming]:last-child',
                '.prose:last-child'
            ]
        elif 'prose' in html_content:
            analysis['primary_selector'] = '.prose:last-child'
            analysis['fallback_selectors'] = [
                '.prose.dark\\:prose-invert:last-child',
                'div.prose:last-child'
            ]
        else:
            analysis['primary_selector'] = self._generate_generic_selector_safe(html_content)

        return analysis

    def _generate_gemini_selectors_optimized(self, html_content, analysis):
        """Génère sélecteurs OPTIMISÉS pour Gemini"""
        # Patterns Gemini spécifiques
        if 'model-response' in html_content:
            analysis['primary_selector'] = '.model-response:last-child'
        elif 'response-container' in html_content:
            analysis['primary_selector'] = '.response-container:last-child'
        else:
            analysis['primary_selector'] = self._generate_generic_selector_safe(html_content)

        analysis['fallback_selectors'] = [
            '[data-response]:last-child',
            '.response:last-child',
            '.markdown:last-child'
        ]

        return analysis

    def _generate_generic_selectors_optimized(self, html_content, analysis):
        """Génère sélecteurs génériques OPTIMISÉS"""
        analysis['primary_selector'] = self._generate_generic_selector_safe(html_content)
        analysis['fallback_selectors'] = [
            'p:last-child',
            'div:last-child',
            '.response:last-child',
            '.message:last-child',
            'article:last-child'
        ]
        return analysis

    def _generate_generic_selector_safe(self, html_content):
        """Génère un sélecteur générique sûr"""
        classes = re.findall(r'class="([^"]*)"', html_content)
        ids = re.findall(r'id="([^"]*)"', html_content)

        if ids and ids[0]:
            return f'#{ids[0]}'
        elif classes:
            # Prendre première classe significative
            for class_list in classes:
                for class_name in class_list.split():
                    if class_name and len(class_name) > 2 and class_name not in ['flex', 'p-2', 'm-1', 'w-full']:
                        return f'.{class_name}'

        return 'div'  # Fallback ultime

    def _detect_platform_from_html_enhanced(self, html_content):
        """Détection de plateforme AMÉLIORÉE"""
        html_lower = html_content.lower()

        # ChatGPT - Indicateurs multiples
        chatgpt_indicators = [
            'data-message-author-role',
            'data-testid="conversation-turn',
            'openai',
            'chatgpt',
            'data-scroll-anchor',
            'markdown prose'
        ]

        if any(indicator in html_content for indicator in chatgpt_indicators):
            return 'ChatGPT'

        # Claude - Indicateurs
        claude_indicators = [
            'data-is-streaming',
            'anthropic',
            'claude.ai',
            'claude'
        ]

        if any(indicator in html_lower for indicator in claude_indicators):
            return 'Claude'

        # Gemini/Bard
        gemini_indicators = [
            'gemini',
            'bard',
            'google.com',
            'model-response'
        ]

        if any(indicator in html_lower for indicator in gemini_indicators):
            return 'Gemini'

        return 'Générique'

    def _extract_text_from_html_optimized(self, html_content):
        """Extraction de texte OPTIMISÉE"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Supprimer éléments indésirables
            for unwanted in soup(['script', 'style', 'button', 'svg', 'nav', 'header', 'footer']):
                unwanted.decompose()

            # Supprimer attributs parasites
            for element in soup.find_all():
                # Garder seulement data-start, data-end pour ChatGPT
                attrs_to_keep = ['data-start', 'data-end', 'data-testid']
                element.attrs = {k: v for k, v in element.attrs.items() if k in attrs_to_keep}

            # Extraire texte
            text = soup.get_text(separator=' ', strip=True)
            # Normaliser espaces et nettoyer
            text = ' '.join(text.split())

            # Supprimer patterns courants indésirables
            unwanted_patterns = [
                r'Send a message\.\.\..*',
                r'Écrivez votre message\.\.\..*',
                r'Copy code.*',
                r'function\(\)\s*\{.*\}',
                r'console\.log.*',
                r'let selectors.*'
            ]

            for pattern in unwanted_patterns:
                text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

            return text.strip()

        except ImportError:
            # Fallback sans BeautifulSoup
            # Supprimer balises HTML
            text = re.sub(r'<[^>]+>', '', html_content)
            # Normaliser espaces
            text = ' '.join(text.split())
            return text

    def _validate_extracted_text(self, extracted_text):
        """Validation INTELLIGENTE du texte extrait"""
        if not extracted_text or len(extracted_text) < 10:
            return {'is_valid': False, 'issue': 'Texte trop court'}

        # Patterns suspects indiquant du code JavaScript au lieu de réponse IA
        javascript_patterns = [
            r'function\s*\(',
            r'console\.log',
            r'let\s+\w+\s*=',
            r'document\.querySelector',
            r'\.textContent',
            r'return\s+\w+',
            r'\{.*\}.*\{.*\}',  # Structures JS imbriquées
            r'selectors\s*=\s*\[',
            r'copy\(',
            r'elements\.forEach'
        ]

        for pattern in javascript_patterns:
            if re.search(pattern, extracted_text, re.IGNORECASE):
                return {'is_valid': False, 'issue': 'Code JavaScript détecté au lieu de réponse IA'}

        # Patterns indiquant interface utilisateur au lieu de contenu
        ui_patterns = [
            r'Send a message',
            r'Écrivez votre message',
            r'Copy code',
            r'Regenerate response',
            r'Stop generating',
            r'Like|Dislike'
        ]

        for pattern in ui_patterns:
            if re.search(pattern, extracted_text, re.IGNORECASE):
                return {'is_valid': False, 'issue': 'Éléments interface utilisateur détectés'}

        # Vérifier cohérence longueur (réponses IA généralement > 50 caractères)
        if len(extracted_text) < 50:
            return {'is_valid': False, 'issue': 'Réponse suspicieusement courte'}

        # Vérifier patterns de réponse IA valides
        ai_response_patterns = [
            r'^(Bien sûr|D\'accord|Voici|Certainement|En effet)',
            r'^(Sure|Of course|Here|Certainly|Indeed)',
            r'(je|nous|il s\'agit|c\'est|voici)',
            r'(I|we|this|here|it)'
        ]

        has_ai_pattern = any(re.search(pattern, extracted_text, re.IGNORECASE)
                             for pattern in ai_response_patterns)

        if not has_ai_pattern and len(extracted_text) < 100:
            return {'is_valid': False, 'issue': 'Ne ressemble pas à une réponse IA typique'}

        return {'is_valid': True, 'issue': None}

    def _create_detection_config_from_extraction(self):
        """Crée automatiquement une configuration de détection depuis la config d'extraction"""
        try:
            if not self.temp_extraction_config:
                return None

            platform_type = self.temp_extraction_config.get('platform_type', 'Unknown')

            # Configuration spécifique selon la plateforme
            if platform_type == 'ChatGPT':
                # Pour ChatGPT : Détecter via data-start/data-end pour la génération
                detection_config = {
                    'platform_type': 'ChatGPT',
                    'primary_selector': '[data-start][data-end]',
                    'fallback_selectors': [
                        '[data-message-author-role="assistant"]:last-child [data-start]',
                        'article[data-testid*="conversation-turn"]:last-child [data-start]'
                    ],
                    'detection_method': 'chatgpt_data_stability',
                    'configured_at': time.time(),
                    'auto_generated': True,
                    'extraction_selector': self.temp_extraction_config.get('primary_selector', ''),
                    'description': 'Configuration de détection automatique pour ChatGPT'
                }

            elif platform_type == 'Claude':
                # Pour Claude : Détecter via data-is-streaming
                detection_config = {
                    'platform_type': 'Claude',
                    'primary_selector': '[data-is-streaming="false"]',
                    'fallback_selectors': [
                        '[data-is-streaming]',
                        '.prose:last-child'
                    ],
                    'detection_method': 'attribute_monitoring',
                    'configured_at': time.time(),
                    'auto_generated': True,
                    'extraction_selector': self.temp_extraction_config.get('primary_selector', ''),
                    'description': 'Configuration de détection automatique pour Claude'
                }

            elif platform_type == 'Gemini':
                # Pour Gemini : Détecter via classes spécifiques
                detection_config = {
                    'platform_type': 'Gemini',
                    'primary_selector': '.model-response:last-child',
                    'fallback_selectors': [
                        '[data-response]:last-child',
                        '.response:last-child'
                    ],
                    'detection_method': 'element_presence',
                    'configured_at': time.time(),
                    'auto_generated': True,
                    'extraction_selector': self.temp_extraction_config.get('primary_selector', ''),
                    'description': 'Configuration de détection automatique pour Gemini'
                }

            else:
                # Configuration générique
                primary_selector = self.temp_extraction_config.get('primary_selector', '')
                detection_config = {
                    'platform_type': 'Générique',
                    'primary_selector': primary_selector,
                    'fallback_selectors': [
                        'p:last-child',
                        'div:last-child',
                        '.response:last-child'
                    ],
                    'detection_method': 'element_stability',
                    'configured_at': time.time(),
                    'auto_generated': True,
                    'extraction_selector': primary_selector,
                    'description': f'Configuration de détection automatique pour {platform_type}'
                }

            logger.info(f"🔄 Configuration de détection créée automatiquement pour {platform_type}")
            logger.info(f"   Sélecteur principal: {detection_config['primary_selector']}")
            logger.info(f"   Méthode: {detection_config['detection_method']}")

            return detection_config

        except Exception as e:
            logger.error(f"Erreur création config détection automatique: {e}")
            return None

    # ====================================================================
    # PHASE 2 : VALIDATION
    # ====================================================================

    def _validate_and_save(self):
        """Validation par l'utilisateur et sauvegarde de la configuration"""
        if not self.temp_extracted_text or not self.temp_extraction_config:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun résultat à valider")
            return

        # Validation automatique finale
        validation_result = self._validate_extracted_text(self.temp_extracted_text)

        if not validation_result['is_valid']:
            reply = QtWidgets.QMessageBox.question(
                self,
                "⚠️ Extraction suspecte détectée",
                f"ATTENTION : {validation_result['issue']}\n\n"
                f"Texte extrait:\n{self.temp_extracted_text[:200]}...\n\n"
                f"❌ Cela ressemble à du CODE JAVASCRIPT au lieu d'une réponse IA.\n\n"
                f"Voulez-vous vraiment continuer ?\n"
                f"✅ OUI : Sauvegarder malgré le problème\n"
                f"❌ NON : Reconfigurer avec le bon élément HTML",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
        else:
            reply = QtWidgets.QMessageBox.question(
                self,
                "✅ Validation de l'extraction",
                f"Le texte extrait semble correct :\n\n"
                f"Texte: {self.temp_extracted_text[:200]}...\n\n"
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
            # Préparer configuration finale
            final_config = {
                'method': 'smart_css_extraction_optimized',
                'platform_config': self.temp_extraction_config,
                'sample_text': self.temp_extracted_text[:200],
                'full_sample': self.temp_extracted_text,
                'configured_at': time.time(),
                'prompt_text': self.prompt_text_input.text().strip(),
                'validation_status': 'user_validated',
                'platform_type': self.temp_extraction_config.get('platform_type', 'Unknown'),
                'extraction_optimized': True
            }

            # Sauvegarder dans profil
            if 'extraction_config' not in self.current_profile:
                self.current_profile['extraction_config'] = {}

            self.current_profile['extraction_config']['response_area'] = final_config

            # 🚀 NOUVEAU : Créer automatiquement la configuration de détection
            detection_config = self._create_detection_config_from_extraction()
            if detection_config:
                self.current_profile['detection_config'] = detection_config
                logger.info("🔄 Configuration de détection créée automatiquement")

            # Sauvegarder en base de données ou fichier
            success = self._save_to_database()

            if success:
                self.validation_phase_complete = True
                self.validation_phase_status.setText("✅ Configuration OPTIMISÉE sauvegardée")
                self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                self._update_global_status()

                # Désactiver boutons validation
                self.validate_ok_button.setEnabled(False)
                self.validate_retry_button.setEnabled(True)  # Permettre reconfiguration

                # Émettre signaux
                self.response_area_configured.emit(self.current_platform, final_config)
                self.response_area_detected.emit(self.current_platform,
                                                 {'response_area': final_config})  # Compatibilité
                self.response_received.emit(self.current_platform, self.temp_extracted_text)

                # 🚀 NOUVEAU : Notifier les autres widgets pour rechargement
                if hasattr(self.parent(), 'refresh_all_widgets'):
                    self.parent().refresh_all_widgets(self.current_platform)

                QtWidgets.QMessageBox.information(
                    self,
                    "✅ Configuration sauvegardée",
                    f"✅ Configuration d'extraction OPTIMISÉE sauvegardée pour {self.current_platform}\n\n"
                    f"Plateforme détectée: {final_config.get('platform_type', 'Unknown')}\n"
                    f"Sélecteur principal: {self.temp_extraction_config.get('primary_selector', 'N/A')}\n"
                    f"Configuration de détection: {'Créée automatiquement' if detection_config else 'Non créée'}\n\n"
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
            # Essayer base de données d'abord
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

        # Réactiver phase 1
        self.config_phase_status.setText("📋 Reconfiguration - Collez le HTML de nouveau")
        self.config_phase_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

        # Désactiver phase 2
        self.validate_ok_button.setEnabled(False)
        self.validate_retry_button.setEnabled(False)

        self.validation_phase_status.setText("⏳ Attendez la nouvelle configuration...")
        self.validation_phase_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

        # Nettoyer affichages
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

        # Réinitialiser interface
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

        # Nettoyer tous affichages
        self.html_input.clear()
        self.detected_selectors.clear()
        self.extracted_preview.clear()

    def _update_global_status(self):
        """Met à jour le statut global du workflow"""
        if self.validation_phase_complete:
            self.global_status.setText("✅ Configuration OPTIMISÉE complète et validée")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        elif self.configuration_phase_complete:
            self.global_status.setText("🧪 Configuration prête - Validation requise")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
        else:
            self.global_status.setText("🔄 Configuration en cours")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def force_reload_from_database(self):
        """Force le rechargement depuis la base de données"""
        if self.current_platform:
            try:
                logger.info(f"🔄 Rechargement forcé depuis DB pour {self.current_platform}")

                # Recharger depuis la base de données
                if hasattr(self.conductor, 'database') and self.conductor.database:
                    if hasattr(self.conductor.database, 'get_platform'):
                        fresh_profile = self.conductor.database.get_platform(self.current_platform)
                        if fresh_profile:
                            self.current_profile = fresh_profile
                            logger.info("✅ Profil rechargé depuis la base de données")

                            # Recharger l'affichage
                            self._load_existing_configuration()
                            return True
                        else:
                            logger.warning("❌ Profil non trouvé en base de données")

                return False

            except Exception as e:
                logger.error(f"Erreur rechargement DB: {e}")
                return False