#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/final_test_widget.py - VERSION CORRIGÉE FINALE

CORRECTIONS PRINCIPALES :
- Détection du navigateur depuis la configuration
- Passage du type de navigateur au state_automation
- Gestion optionnelle de la configuration clavier (pour éviter les crashes)
- Focus navigateur amélioré pour éviter les changements de fenêtre
- Interface préservée et fonctionnelle
- Bouton stop opérationnel
"""

import time
import pyperclip
import json
import os
import re
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.emergency_stop_overlay import EmergencyStopOverlay


class FinalTestWidget(QtWidgets.QWidget):
    """Widget test final - VERSION CORRIGÉE avec détection navigateur et focus amélioré"""

    # Signaux
    test_completed = pyqtSignal(str, bool, str)  # Plateforme, succès, message
    response_received = pyqtSignal(str, str)  # Plateforme, réponse
    detection_config_saved = pyqtSignal(str, dict)  # Plateforme, config

    def __init__(self, config_provider, conductor, keyboard_config_widget=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor

        # Configuration clavier optionnelle (pour éviter les crashes)
        self.keyboard_config_widget = keyboard_config_widget
        self.keyboard_config = {}

        self.current_platform = None
        self.profiles = {}
        self.current_profile = None

        # États SIMPLIFIÉS
        self.test_running = False
        self.temp_detection_config = {}
        self.temp_test_result = ""

        # Type de navigateur détecté
        self.detected_browser_type = "chrome"  # Par défaut

        # Bouton overlay STOP
        self.emergency_overlay = EmergencyStopOverlay(
            conductor=conductor,
            state_automation=getattr(conductor, 'state_automation', None)
        )

        # Connecter le signal d'arrêt d'urgence
        self.emergency_overlay.emergency_stop_requested.connect(self._on_emergency_stop_from_overlay)

        # Connecter la configuration clavier si disponible
        if self.keyboard_config_widget:
            try:
                self.keyboard_config_widget.keyboard_configured.connect(self._update_keyboard_config)
                # Initialiser la configuration clavier
                self._update_keyboard_config(self.keyboard_config_widget._get_current_config())
            except Exception as e:
                logger.warning(f"Impossible de connecter la configuration clavier: {e}")
                self.keyboard_config_widget = None

        self._init_ui()

    def _init_ui(self):
        """Interface simplifiée"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ===========================
        # COLONNE GAUCHE : ACTIONS ET STATUT
        # ===========================
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(15)

        # === 1. Sélection plateforme ===
        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        self.platform_status = QtWidgets.QLabel("Sélectionnez une plateforme...")
        self.platform_status.setWordWrap(True)
        platform_layout.addWidget(self.platform_status)

        # Affichage du navigateur détecté
        self.browser_status = QtWidgets.QLabel("Navigateur: Non détecté")
        self.browser_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        platform_layout.addWidget(self.browser_status)

        # Affichage de l'état de la protection Alt+Tab (si config clavier disponible)
        if self.keyboard_config_widget:
            self.alt_tab_status = QtWidgets.QLabel("Protection Alt+Tab: Non configurée")
            self.alt_tab_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
            platform_layout.addWidget(self.alt_tab_status)
            self._update_alt_tab_status()

        left_layout.addWidget(platform_group)

        # === 2. Statut Configuration ===
        config_status_group = QtWidgets.QGroupBox("🔍 Configuration Détection")
        config_status_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_status_layout = QtWidgets.QVBoxLayout(config_status_group)

        self.detection_phase_status = QtWidgets.QLabel("⏳ Collez le HTML de l'indicateur de fin")
        self.detection_phase_status.setWordWrap(True)
        config_status_layout.addWidget(self.detection_phase_status)

        left_layout.addWidget(config_status_group)

        # === 3. Test Final SIMPLIFIÉ ===
        test_actions_group = QtWidgets.QGroupBox("🚀 Test Final")
        test_actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        test_actions_layout = QtWidgets.QVBoxLayout(test_actions_group)

        # Prompt pour le test final
        prompt_label = QtWidgets.QLabel("Message de test :")
        prompt_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        test_actions_layout.addWidget(prompt_label)

        self.final_test_prompt = QtWidgets.QLineEdit("Bonjour ! Dites simplement 'Hello' pour tester.")
        self.final_test_prompt.setPlaceholderText("Prompt pour test final...")
        test_actions_layout.addWidget(self.final_test_prompt)

        # Bouton test final
        self.start_final_test_btn = QtWidgets.QPushButton("🚀 Test Final")
        self.start_final_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.start_final_test_btn.clicked.connect(self._start_final_test)
        self.start_final_test_btn.setEnabled(False)
        test_actions_layout.addWidget(self.start_final_test_btn)

        # Bouton stop
        self.stop_test_btn = QtWidgets.QPushButton("⏹️ Arrêter Test")
        self.stop_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #c82333; }
        """)
        self.stop_test_btn.clicked.connect(self._stop_test)
        self.stop_test_btn.setVisible(False)
        test_actions_layout.addWidget(self.stop_test_btn)

        # Statut test
        self.test_phase_status = QtWidgets.QLabel("⏳ Sélectionnez une plateforme avec configuration")
        self.test_phase_status.setWordWrap(True)
        test_actions_layout.addWidget(self.test_phase_status)

        left_layout.addWidget(test_actions_group)

        # === 4. Validation ===
        validation_group = QtWidgets.QGroupBox("✅ Validation")
        validation_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        validation_layout = QtWidgets.QVBoxLayout(validation_group)

        self.validate_success_btn = QtWidgets.QPushButton("✅ Valider - Config OK")
        self.validate_success_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.validate_success_btn.clicked.connect(self._validate_success)
        self.validate_success_btn.setEnabled(False)
        validation_layout.addWidget(self.validate_success_btn)

        self.validate_retry_btn = QtWidgets.QPushButton("🔄 Reconfigurer")
        self.validate_retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.validate_retry_btn.clicked.connect(self._retry_configuration)
        self.validate_retry_btn.setEnabled(False)
        validation_layout.addWidget(self.validate_retry_btn)

        self.validation_status = QtWidgets.QLabel("⏳ Effectuez d'abord le test")
        self.validation_status.setWordWrap(True)
        validation_layout.addWidget(self.validation_status)

        left_layout.addWidget(validation_group)
        left_layout.addStretch(1)

        # ===========================
        # COLONNE DROITE : CONFIGURATION
        # ===========================
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(15)

        # Instructions
        header = QtWidgets.QLabel(
            "<b>🎯 Configuration Détection Fin IA</b><br>"
            "<b style='color: #007bff;'>Le Conductor gère automatiquement : navigateur + automation + extraction</b><br>"
            "<b style='color: #28a745;'>✅ WORKFLOW SIMPLIFIÉ : Générer sélecteurs → Tester immédiatement</b>"
        )
        header.setWordWrap(True)
        header.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        right_layout.addWidget(header)

        # Configuration détection via HTML
        detection_config_group = QtWidgets.QGroupBox("🔍 Configuration Détection")
        detection_config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        detection_config_layout = QtWidgets.QVBoxLayout(detection_config_group)

        detection_instructions = QtWidgets.QLabel(
            "<b>Instructions :</b><br>"
            "1. 💬 Envoyez un message sur votre plateforme IA<br>"
            "2. ⏳ Attendez la fin complète de la réponse<br>"
            "3. 🔧 F12 → Clic droit sur l'indicateur de fin → Inspecter<br>"
            "4. 📋 Clic droit → Copy → Copy outerHTML<br>"
            "5. 📥 Collez ci-dessous → Test immédiatement disponible !"
        )
        detection_instructions.setWordWrap(True)
        detection_instructions.setStyleSheet("color: #2196F3; font-size: 10px; margin-bottom: 10px;")
        detection_config_layout.addWidget(detection_instructions)

        self.detection_html_input = QtWidgets.QTextEdit()
        self.detection_html_input.setPlaceholderText(
            "Collez ici le HTML de l'indicateur de fin (génération automatique des sélecteurs)...")
        self.detection_html_input.setMaximumHeight(100)
        self.detection_html_input.textChanged.connect(self._on_detection_html_changed)
        detection_config_layout.addWidget(self.detection_html_input)

        detection_selectors_label = QtWidgets.QLabel("🎯 Sélecteurs de détection générés :")
        detection_selectors_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        detection_config_layout.addWidget(detection_selectors_label)

        self.detection_selectors_display = QtWidgets.QTextEdit()
        self.detection_selectors_display.setMaximumHeight(80)
        self.detection_selectors_display.setReadOnly(True)
        self.detection_selectors_display.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.detection_selectors_display.setPlaceholderText("Les sélecteurs de détection apparaîtront ici...")
        detection_config_layout.addWidget(self.detection_selectors_display)

        # Bouton sauvegarde (optionnel)
        self.save_selectors_btn = QtWidgets.QPushButton("💾 Sauvegarder Sélecteurs")
        self.save_selectors_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
                margin-top: 8px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.save_selectors_btn.clicked.connect(self._save_selectors_to_database)
        self.save_selectors_btn.setEnabled(False)
        detection_config_layout.addWidget(self.save_selectors_btn)

        right_layout.addWidget(detection_config_group)

        # Réponse extraite
        response_group = QtWidgets.QGroupBox("🤖 Réponse IA Extraite")
        response_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        response_layout = QtWidgets.QVBoxLayout(response_group)

        self.extracted_response = QtWidgets.QTextEdit()
        self.extracted_response.setMaximumHeight(150)
        self.extracted_response.setReadOnly(True)
        self.extracted_response.setStyleSheet(
            "background-color: #f0f8ff; border: 2px solid #4CAF50; border-radius: 4px; padding: 8px;"
        )
        self.extracted_response.setPlaceholderText("Réponse IA extraite...")
        response_layout.addWidget(self.extracted_response)

        right_layout.addWidget(response_group)
        right_layout.addStretch(1)

        # Assemblage final
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(350)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

    # ==============================
    # GESTION CONFIGURATION CLAVIER (OPTIONNELLE)
    # ==============================

    def _update_keyboard_config(self, config):
        """Met à jour la configuration clavier et l'applique (si disponible)"""
        if not config:
            return

        self.keyboard_config = config
        logger.info(f"Configuration clavier mise à jour: {json.dumps(config, indent=2)}")

        # Appliquer au state_automation
        if hasattr(self.conductor, 'state_automation') and self.conductor.state_automation:
            if hasattr(self.conductor.state_automation, 'keyboard_controller'):
                self.conductor.state_automation.keyboard_controller.update_config(config)
                logger.info("Configuration clavier appliquée à state_automation.keyboard_controller")

        # Mettre à jour l'affichage si le widget est disponible
        if hasattr(self, 'alt_tab_status'):
            self._update_alt_tab_status()

    def _update_alt_tab_status(self):
        """Met à jour l'affichage de l'état de la protection Alt+Tab"""
        if not hasattr(self, 'alt_tab_status'):
            return

        if self.keyboard_config.get('block_alt_tab', False):
            self.alt_tab_status.setText("Protection Alt+Tab: Activée")
            self.alt_tab_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
        else:
            self.alt_tab_status.setText("Protection Alt+Tab: Désactivée")
            self.alt_tab_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

    # ==============================
    # DÉTECTION DU NAVIGATEUR
    # ==============================

    def _detect_browser_type(self):
        """Détecte le type de navigateur depuis la configuration"""
        try:
            if not self.current_platform or not self.current_profile:
                return "chrome"

            # Vérifier la config navigateur
            browser_config = self.current_profile.get('browser', {})
            browser_path = browser_config.get('path', '').lower()
            browser_url = browser_config.get('url', '').lower()

            # Détection par le chemin
            if browser_path:
                if 'chrome' in browser_path:
                    return "chrome"
                elif 'firefox' in browser_path or 'mozilla' in browser_path:
                    return "firefox"
                elif 'edge' in browser_path:
                    return "edge"
                elif 'safari' in browser_path:
                    return "safari"
                elif 'opera' in browser_path:
                    return "opera"
                elif 'brave' in browser_path:
                    return "brave"

            # Détection par l'URL (moins fiable mais utile)
            if browser_url:
                if 'chrome' in browser_url:
                    return "chrome"
                elif 'firefox' in browser_url:
                    return "firefox"

            # Détection par le nom de la plateforme
            platform_lower = self.current_platform.lower()
            if 'firefox' in platform_lower:
                return "firefox"
            elif 'chrome' in platform_lower:
                return "chrome"
            elif 'edge' in platform_lower:
                return "edge"

            return "chrome"  # Par défaut

        except Exception as e:
            logger.error(f"Erreur détection navigateur: {e}")
            return "chrome"

    def _update_browser_status(self):
        """Met à jour l'affichage du navigateur détecté"""
        self.detected_browser_type = self._detect_browser_type()
        self.browser_status.setText(f"Navigateur détecté: {self.detected_browser_type.capitalize()}")
        self.browser_status.setStyleSheet("color: #007bff; font-size: 10px; margin-top: 5px; font-weight: bold;")
        logger.info(f"🌐 Navigateur détecté: {self.detected_browser_type}")

    # ==============================
    # LOGIQUE PRINCIPALE
    # ==============================

    def _has_valid_detection_config(self):
        """Vérifie si on a une configuration de détection valide"""
        if not self.current_platform or not self.current_profile:
            return False

        # Config temporaire générée
        if self.temp_detection_config and self.temp_detection_config.get('primary_selector'):
            return True

        # Config sauvée dans le profil
        detection_config = self.current_profile.get('detection_config', {})
        if detection_config and detection_config.get('primary_selector'):
            return True

        return False

    def _update_test_button_state(self):
        """Met à jour l'état du bouton de test"""
        should_enable = self._has_valid_detection_config() and not self.test_running

        self.start_final_test_btn.setEnabled(should_enable)

        if should_enable:
            self.test_phase_status.setText("🚀 PRÊT POUR LE TEST")
            self.test_phase_status.setStyleSheet(
                "color: #007bff; font-weight: bold; background-color: #E3F2FD; padding: 8px; border-radius: 4px;")
        else:
            if not self.current_platform:
                self.test_phase_status.setText("⏳ Sélectionnez une plateforme")
            elif not self._has_valid_detection_config():
                self.test_phase_status.setText("⏳ Collez du HTML pour générer les sélecteurs")
            elif self.test_running:
                self.test_phase_status.setText("🔄 Test en cours...")

            self.test_phase_status.setStyleSheet("color: #6c757d; font-weight: normal;")

        logger.info(
            f"Bouton test: {'activé' if should_enable else 'désactivé'} (plateforme: {self.current_platform}, config: {self._has_valid_detection_config()}, running: {self.test_running})")

    def _on_platform_changed(self, platform_name):
        """Gestion changement plateforme"""
        if platform_name and platform_name != "-- Sélectionner --":
            self.current_platform = platform_name
            self.current_profile = self.profiles.get(platform_name, {})
            self._update_platform_status()
            self._update_browser_status()  # Détection du navigateur
            self._load_existing_detection_config()
        else:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()

        self._update_test_button_state()

    def _load_existing_detection_config(self):
        """Chargement config existante"""
        if not self.current_platform or not self.current_profile:
            return

        try:
            # Essayer DB d'abord
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_platform'):
                    saved_profile = self.conductor.database.get_platform(self.current_platform)
                    if saved_profile:
                        self.current_profile = saved_profile

            # Vérifier si on a une config
            detection_config = self.current_profile.get('detection_config', {})
            if detection_config and detection_config.get('primary_selector'):
                self._display_existing_detection_config(detection_config)

        except Exception as e:
            logger.error(f"Erreur chargement config: {e}")

    def _display_existing_detection_config(self, detection_config):
        """Affichage config existante"""
        try:
            # Afficher les sélecteurs
            selectors_text = f"Sélecteur principal: {detection_config.get('primary_selector', 'Non défini')}\n"
            fallback_selectors = detection_config.get('fallback_selectors', [])
            if fallback_selectors:
                selectors_text += f"Sélecteurs fallback: {', '.join(fallback_selectors)}\n"
            selectors_text += f"Méthode: {detection_config.get('detection_method', 'css_selector')}\n"
            selectors_text += f"Type plateforme: {detection_config.get('platform_type', 'Générique')}"

            self.detection_selectors_display.setPlainText(selectors_text)

            # Sauvegarder en temp pour utilisation
            self.temp_detection_config = detection_config

            # Mettre à jour les statuts
            self.detection_phase_status.setText("✅ Configuration existante chargée")
            self.detection_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Marquer bouton sauvegarde comme fait
            self.save_selectors_btn.setText("✅ Sélecteurs sauvés")
            self.save_selectors_btn.setEnabled(False)
            self.save_selectors_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                    margin-top: 8px;
                }
            """)

            # Mettre à jour bouton test
            self._update_test_button_state()

            logger.info("Configuration existante chargée et prête")

        except Exception as e:
            logger.error(f"Erreur affichage config: {e}")

    def _on_detection_html_changed(self):
        """Analyse HTML automatique"""
        html_content = self.detection_html_input.toPlainText().strip()

        if len(html_content) > 50:
            if hasattr(self, '_detection_analysis_timer'):
                self._detection_analysis_timer.stop()

            self._detection_analysis_timer = QtCore.QTimer()
            self._detection_analysis_timer.setSingleShot(True)
            self._detection_analysis_timer.timeout.connect(self._analyze_detection_html)
            self._detection_analysis_timer.start(1000)

    def _analyze_detection_html(self):
        """Analyse HTML et génération config"""
        html_content = self.detection_html_input.toPlainText().strip()

        if not html_content:
            return

        try:
            logger.info("Analyse HTML de détection...")

            # Générer la config
            detection_config = self._generate_detection_config(html_content)

            # Afficher les sélecteurs
            selectors_text = f"Sélecteur principal: {detection_config['primary_selector']}\n"
            if detection_config.get('fallback_selectors'):
                selectors_text += f"Sélecteurs fallback: {', '.join(detection_config['fallback_selectors'])}\n"
            selectors_text += f"Méthode: {detection_config['detection_method']}\n"
            selectors_text += f"Type plateforme: {detection_config['platform_type']}"

            self.detection_selectors_display.setPlainText(selectors_text)

            # Sauvegarder en temp
            self.temp_detection_config = detection_config
            self.temp_detection_config['original_html'] = html_content

            # Mettre à jour statuts
            self.detection_phase_status.setText("✅ Sélecteurs générés")
            self.detection_phase_status.setStyleSheet(
                "color: #28a745; font-weight: bold; background-color: #E8F5E8; padding: 8px; border-radius: 4px;")

            # Activer bouton sauvegarde
            self.save_selectors_btn.setEnabled(True)
            self.save_selectors_btn.setText("💾 Sauvegarder Sélecteurs")
            self.save_selectors_btn.setStyleSheet("""
                QPushButton {
                    background-color: #17a2b8;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                    margin-top: 8px;
                }
                QPushButton:hover { background-color: #138496; }
            """)

            # ACTIVER LE TEST IMMÉDIATEMENT
            self._update_test_button_state()

            logger.info("Configuration générée - Test disponible")

        except Exception as e:
            self.detection_phase_status.setText(f"❌ Erreur: {str(e)}")
            self.detection_phase_status.setStyleSheet("color: #FF0000; font-weight: bold;")
            logger.error(f"Erreur analyse HTML: {e}")

    def _generate_detection_config(self, html_content):
        """Génération config détection"""
        classes = re.findall(r'class="([^"]*)"', html_content)
        ids = re.findall(r'id="([^"]*)"', html_content)
        data_attrs = re.findall(r'(data-[^=]+)="[^"]*"', html_content)

        platform_type = self._detect_platform_from_html(html_content)

        config = {
            'platform_type': platform_type,
            'primary_selector': '',
            'fallback_selectors': [],
            'detection_method': 'css_selector_presence',
            'configured_at': time.time()
        }

        # Logique ChatGPT
        if 'data-start' in html_content and 'data-end' in html_content:
            config.update({
                'primary_selector': '[data-start][data-end]',
                'detection_method': 'chatgpt_data_stability',
                'platform_type': 'ChatGPT',
                'extraction_selector': '.markdown.prose'
            })
            config['fallback_selectors'] = [
                '[data-message-author-role="assistant"]:last-child .markdown.prose',
                '[data-message-author-role="assistant"]:last-child'
            ]
        # Logique générique
        elif 'data-end' in html_content:
            config['primary_selector'] = '[data-end]'
            config['detection_method'] = 'attribute_presence'
        elif classes:
            config['primary_selector'] = f'.{classes[0]}'
        elif ids:
            config['primary_selector'] = f'#{ids[0]}'
        else:
            config['primary_selector'] = 'div'

        return config

    def _detect_platform_from_html(self, html_content):
        """Détection plateforme"""
        html_lower = html_content.lower()
        if 'data-message-author-role' in html_content or 'chatgpt' in html_lower:
            return 'ChatGPT'
        elif 'data-is-streaming' in html_content or 'claude' in html_lower:
            return 'Claude'
        elif 'gemini' in html_lower or 'bard' in html_lower:
            return 'Gemini'
        else:
            return 'Générique'

    # ==============================
    # TEST FINAL AVEC NAVIGATEUR ET FOCUS AMÉLIORÉ
    # ==============================

    def _start_final_test(self):
        """Test final avec détection du navigateur et gestion du focus améliorée"""
        # Vérifications de base
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord une plateforme")
            return

        if not self._has_valid_detection_config():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Générez d'abord des sélecteurs de détection")
            return

        if self.test_running:
            return

        # Vérifier la protection Alt+Tab si disponible
        if self.keyboard_config_widget and not self.keyboard_config.get('block_alt_tab', False):
            reply = QtWidgets.QMessageBox.warning(
                self, "Avertissement",
                "La protection Alt+Tab est désactivée. Activez-la dans la configuration clavier pour éviter les changements de fenêtre.\n\nContinuer quand même ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Récupérer la config à utiliser
        detection_config = self.temp_detection_config or self.current_profile.get('detection_config', {})

        # Mise à jour automatique du profil
        if self.temp_detection_config and not self.current_profile.get('detection_config'):
            self.current_profile['detection_config'] = self.temp_detection_config.copy()
            if hasattr(self.config_provider, 'profiles'):
                self.config_provider.profiles[self.current_platform] = self.current_profile

        # Mettre à jour le state_automation avec le type de navigateur
        if hasattr(self.conductor, 'state_automation') and self.conductor.state_automation:
            self.conductor.state_automation.browser_type = self.detected_browser_type
            logger.info(f"🌐 Type navigateur configuré dans state_automation: {self.detected_browser_type}")

        # Démarrer le test
        self.test_running = True
        self._update_test_button_state()

        # Interface - Montrer le bouton stop
        self.start_final_test_btn.setVisible(False)
        self.stop_test_btn.setVisible(True)

        # Overlay STOP
        self.emergency_overlay.show_overlay()
        self.emergency_overlay.update_references(
            conductor=self.conductor,
            state_automation=getattr(self.conductor, 'state_automation', None)
        )

        self.test_phase_status.setText("🚀 Test en cours...")
        self.test_phase_status.setStyleSheet("color: #FF6B35; font-weight: bold;")

        logger.info(f"Début test pour {self.current_platform} avec navigateur {self.detected_browser_type}")

        try:
            # S'assurer du focus sur le navigateur AVANT le test
            self._ensure_browser_focus_advanced()

            # Appel au conductor avec le type de navigateur
            if hasattr(self.conductor, 'test_platform_connection_ultra_robust'):
                test_message = self.final_test_prompt.text() or "Test de configuration"

                result = self.conductor.test_platform_connection_ultra_robust(
                    platform_name=self.current_platform,
                    test_message=test_message,
                    timeout=30,
                    wait_for_response=12,
                    skip_browser=True
                )

                # Re-vérifier le focus après l'envoi du prompt (point critique)
                self._ensure_browser_focus_advanced()

                if result['success']:
                    response = result.get('response', '')
                    duration = result.get('duration', 0)

                    # Afficher la réponse
                    self.extracted_response.setPlainText(response)
                    self.temp_test_result = response

                    # Statuts de succès
                    self.test_phase_status.setText(f"✅ Test réussi en {duration:.1f}s")
                    self.test_phase_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                    # Activer validation
                    self.validate_success_btn.setEnabled(True)
                    self.validate_retry_btn.setEnabled(True)
                    self.validation_status.setText("✅ Test terminé - Validez le résultat")

                    # Marquer sauvegarde comme faite
                    if self.save_selectors_btn.isEnabled():
                        self.save_selectors_btn.setText("✅ Sélecteurs sauvés")
                        self.save_selectors_btn.setEnabled(False)

                    self.emergency_overlay.hide_overlay()
                    logger.info("Test réussi")

                else:
                    self._handle_test_error(result.get('message', 'Erreur inconnue'))

            else:
                self._handle_test_error("Conductor non disponible")

        except Exception as e:
            self._handle_test_error(str(e))
        finally:
            self._reset_test_buttons()

    def _ensure_browser_focus_advanced(self):
        """S'assure que le focus est sur le navigateur avec méthode avancée"""
        try:
            import pyautogui
            import tkinter as tk

            logger.info("🎯 Focus navigateur avancé - méthode anti-changement de fenêtre")

            # Obtenir la taille de l'écran
            try:
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
            except:
                screen_width = 1920
                screen_height = 1080

            # MÉTHODE 1: Clic dans une zone neutre du navigateur
            # Zone centre-haute pour éviter les éléments interactifs
            safe_x = screen_width // 2
            safe_y = 150  # Assez bas pour éviter les onglets, assez haut pour éviter le contenu

            logger.info(f"🖱️ Clic de focus sécurisé à ({safe_x}, {safe_y})")
            pyautogui.click(safe_x, safe_y)
            time.sleep(0.5)

            # MÉTHODE 2: Double clic pour s'assurer du focus
            pyautogui.click(safe_x, safe_y)
            time.sleep(0.3)

            # MÉTHODE 3: Utiliser pygetwindow si disponible pour forcer l'activation
            try:
                import pygetwindow as gw
                all_windows = gw.getAllWindows()

                # Chercher une fenêtre de navigateur correspondant au type détecté
                browser_keywords = {
                    'chrome': ['chrome', 'chromium'],
                    'firefox': ['firefox', 'mozilla'],
                    'edge': ['edge', 'microsoft edge'],
                    'safari': ['safari'],
                    'opera': ['opera'],
                    'brave': ['brave']
                }

                keywords = browser_keywords.get(self.detected_browser_type.lower(), ['chrome', 'firefox', 'edge'])

                for window in all_windows:
                    window_title = window.title.lower()
                    if any(keyword in window_title for keyword in keywords):
                        try:
                            window.activate()
                            if not window.isMaximized:
                                window.maximize()
                            logger.info(f"✅ Fenêtre {self.detected_browser_type} activée: {window.title}")
                            time.sleep(0.3)
                            break
                        except Exception as e:
                            logger.debug(f"Erreur activation fenêtre: {e}")
                            continue

            except ImportError:
                logger.debug("pygetwindow non disponible")
            except Exception as e:
                logger.debug(f"Erreur pygetwindow: {e}")

            logger.info("✅ Focus navigateur avancé terminé")

        except Exception as e:
            logger.error(f"Erreur focus navigateur avancé: {e}")
            # Fallback simple
            try:
                pyautogui.click(960, 300)
                time.sleep(0.3)
            except:
                pass

    def _stop_test(self):
        """Arrêt du test"""
        if self.test_running:
            logger.info("Arrêt du test demandé")
            self.test_running = False

            try:
                if hasattr(self.conductor, 'emergency_stop'):
                    self.conductor.emergency_stop()
            except Exception as e:
                logger.warning(f"Erreur arrêt conductor: {e}")

            self._reset_test_buttons()
            self.test_phase_status.setText("🛑 Test arrêté")
            self.emergency_overlay.hide_overlay()

    def _handle_test_error(self, error_msg):
        """Gestion erreur test"""
        logger.error(f"Erreur test: {error_msg}")
        self.test_phase_status.setText(f"❌ Erreur: {error_msg}")
        self.test_phase_status.setStyleSheet("color: #FF0000; font-weight: bold;")
        self.emergency_overlay.hide_overlay()

    def _reset_test_buttons(self):
        """Reset boutons test"""
        self.test_running = False
        self.start_final_test_btn.setVisible(True)
        self.stop_test_btn.setVisible(False)
        self._update_test_button_state()

    def _on_emergency_stop_from_overlay(self):
        """Arrêt d'urgence overlay"""
        logger.warning("Arrêt d'urgence depuis overlay")
        self.test_running = False
        self._reset_test_buttons()
        self.test_phase_status.setText("🛑 STOP d'urgence")
        self.emergency_overlay.hide_overlay()

    # ==============================
    # SAUVEGARDE ET VALIDATION
    # ==============================

    def _save_selectors_to_database(self):
        """Sauvegarde sélecteurs"""
        try:
            if not self.temp_detection_config:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune configuration à sauvegarder")
                return

            # Sauvegarder dans le profil
            self.current_profile['detection_config'] = self.temp_detection_config.copy()

            # Sauvegarder en base
            success = self._save_to_database()

            if success:
                self.save_selectors_btn.setText("✅ Sélecteurs sauvés")
                self.save_selectors_btn.setEnabled(False)

                # Mettre à jour config_provider
                if hasattr(self.config_provider, 'profiles'):
                    self.config_provider.profiles[self.current_platform] = self.current_profile

                QtWidgets.QMessageBox.information(self, "Sauvegardé", "✅ Sélecteurs sauvegardés !")
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur", "❌ Échec sauvegarde")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")

    def _validate_success(self):
        """Validation succès"""
        reply = QtWidgets.QMessageBox.question(
            self, "Validation",
            "Confirmez-vous que la configuration fonctionne correctement ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self._save_final_configuration()

    def _save_final_configuration(self):
        """Sauvegarde finale"""
        try:
            self.current_profile['detection_config'] = self.temp_detection_config
            self._save_to_database()

            self.validation_status.setText("✅ Configuration validée")
            self.validate_success_btn.setEnabled(False)
            self.validate_retry_btn.setEnabled(False)

            QtWidgets.QMessageBox.information(self, "Validé", "✅ Configuration validée et sauvegardée !")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec sauvegarde:\n{str(e)}")

    def _retry_configuration(self):
        """Reconfiguration"""
        self.temp_detection_config = {}
        self.temp_test_result = ""

        self.detection_html_input.clear()
        self.detection_selectors_display.clear()
        self.extracted_response.clear()

        self.detection_phase_status.setText("📋 Collez le HTML de nouveau")
        self.test_phase_status.setText("⏳ Configurez d'abord la détection")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)

        self.save_selectors_btn.setText("💾 Sauvegarder Sélecteurs")
        self.save_selectors_btn.setEnabled(False)

        self._update_test_button_state()

    def _save_to_database(self):
        """Sauvegarde DB"""
        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    return self.conductor.database.save_platform(self.current_platform, self.current_profile)
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            return False

    # ==============================
    # UTILITAIRES
    # ==============================

    def _update_platform_status(self):
        """Mise à jour statut plateforme"""
        if not self.current_platform or not self.current_profile:
            self.platform_status.setText("Sélectionnez une plateforme...")
            return

        browser_config = self.current_profile.get('browser', {})
        interface_positions = self.current_profile.get('interface_positions', {})

        missing = []
        if not browser_config.get('url'):
            missing.append("URL navigateur")
        if not interface_positions.get('prompt_field'):
            missing.append("Position champ prompt")

        if missing:
            self.platform_status.setText(f"⚠️ Manque: {', '.join(missing)}")
            self.platform_status.setStyleSheet("color: #FF9800; font-weight: bold;")
        else:
            self.platform_status.setText("✅ Plateforme configurée")
            self.platform_status.setStyleSheet("color: #28a745; font-weight: bold;")

    def _reset_interface(self):
        """Reset interface"""
        self.temp_detection_config = {}
        self.temp_test_result = ""
        self.detected_browser_type = "chrome"

        self.platform_status.setText("Sélectionnez une plateforme...")
        self.browser_status.setText("Navigateur: Non détecté")
        self.browser_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        if hasattr(self, 'alt_tab_status'):
            self.alt_tab_status.setText("Protection Alt+Tab: Non configurée")
            self.alt_tab_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        self.detection_phase_status.setText("⏳ Collez le HTML de l'indicateur de fin")
        self.test_phase_status.setText("⏳ Sélectionnez une plateforme avec configuration")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.detection_html_input.clear()
        self.detection_selectors_display.clear()
        self.extracted_response.clear()

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)
        self.save_selectors_btn.setEnabled(False)

        self._update_test_button_state()

    def closeEvent(self, event):
        """Nettoyage fermeture"""
        try:
            if hasattr(self, 'emergency_overlay'):
                self.emergency_overlay.hide_overlay()
                self.emergency_overlay.close()
        except Exception as e:
            logger.debug(f"Erreur nettoyage: {e}")
        super().closeEvent(event)

    # ==============================
    # API PUBLIQUE
    # ==============================

    def set_profiles(self, profiles):
        """Mise à jour profils"""
        self.profiles = profiles or {}

        current_text = self.platform_combo.currentText()
        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionner --")

        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)

        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def select_platform(self, platform_name):
        """Sélection plateforme"""
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        """Rafraîchissement"""
        self.set_profiles(self.profiles)
        if self.keyboard_config_widget:
            try:
                self._update_keyboard_config(self.keyboard_config_widget._get_current_config())
            except Exception as e:
                logger.warning(f"Erreur refresh config clavier: {e}")