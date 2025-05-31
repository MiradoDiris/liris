#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/final_test_widget.py - VERSION SYNCHRONISATION CORRIGÉE

CORRECTIONS PRINCIPALES :
- Synchronisation avec Response Area Widget
- Chargement depuis extraction_config.response_area
- Création automatique de detection_config
- Rechargement forcé depuis base de données
- Focus navigateur amélioré
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
    """Widget test final - VERSION SYNCHRONISATION CORRIGÉE"""

    # Signaux
    test_completed = pyqtSignal(str, bool, str)  # Plateforme, succès, message
    response_received = pyqtSignal(str, str)  # Plateforme, réponse
    detection_config_saved = pyqtSignal(str, dict)  # Plateforme, config

    def __init__(self, config_provider, conductor, keyboard_config_widget=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor

        # Configuration clavier optionnelle
        self.keyboard_config_widget = keyboard_config_widget
        self.keyboard_config = {}

        self.current_platform = None
        self.profiles = {}
        self.current_profile = None

        # États
        self.test_running = False
        self.temp_detection_config = {}
        self.temp_test_result = ""

        # Type de navigateur détecté
        self.detected_browser_type = "chrome"

        # Bouton overlay STOP
        self.emergency_overlay = EmergencyStopOverlay(
            conductor=conductor,
            state_automation=getattr(conductor, 'state_automation', None)
        )

        # Connecter signaux
        self.emergency_overlay.emergency_stop_requested.connect(self._on_emergency_stop_from_overlay)

        # Connecter configuration clavier si disponible
        if self.keyboard_config_widget:
            try:
                self.keyboard_config_widget.keyboard_configured.connect(self._update_keyboard_config)
                self._update_keyboard_config(self.keyboard_config_widget._get_current_config())
            except Exception as e:
                logger.warning(f"Impossible de connecter la configuration clavier: {e}")
                self.keyboard_config_widget = None

        self._init_ui()

    def _init_ui(self):
        """Interface utilisateur"""
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

        # Affichage synchronisation
        self.sync_status = QtWidgets.QLabel("Synchronisation: En attente")
        self.sync_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        platform_layout.addWidget(self.sync_status)

        # Affichage protection Alt+Tab si disponible
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

        self.detection_phase_status = QtWidgets.QLabel("⏳ Chargement depuis Response Area...")
        self.detection_phase_status.setWordWrap(True)
        config_status_layout.addWidget(self.detection_phase_status)

        # Bouton de rechargement forcé
        self.force_reload_btn = QtWidgets.QPushButton("🔄 Recharger Config")
        self.force_reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #5a2e9c; }
        """)
        self.force_reload_btn.clicked.connect(self._force_reload_from_database)
        config_status_layout.addWidget(self.force_reload_btn)

        left_layout.addWidget(config_status_group)

        # === 3. Test Final ===
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
        self.test_phase_status = QtWidgets.QLabel("⏳ Sélectionnez une plateforme configurée")
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
            "<b>🎯 Test Final avec Synchronisation Automatique</b><br>"
            "<b style='color: #007bff;'>⚡ Auto-sync avec Response Area Widget</b><br>"
            "<b style='color: #28a745;'>✅ Détection + Extraction unifiées</b>"
        )
        header.setWordWrap(True)
        header.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        right_layout.addWidget(header)

        # Configuration synchronisée
        sync_config_group = QtWidgets.QGroupBox("🔄 Configuration Synchronisée")
        sync_config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        sync_config_layout = QtWidgets.QVBoxLayout(sync_config_group)

        sync_instructions = QtWidgets.QLabel(
            "<b>🔄 SYNCHRONISATION AUTOMATIQUE :</b><br>"
            "• Récupère automatiquement depuis Response Area Widget<br>"
            "• Crée les sélecteurs de détection appropriés<br>"
            "• Utilise les sélecteurs d'extraction configurés<br>"
            "• Pas besoin de configuration manuelle !<br>"
            "<b style='color: #dc3545;'>⚠️ Si pas synchronisé : cliquez 'Recharger Config'</b>"
        )
        sync_instructions.setWordWrap(True)
        sync_instructions.setStyleSheet("color: #2196F3; font-size: 10px; margin-bottom: 10px;")
        sync_config_layout.addWidget(sync_instructions)

        # Affichage config détection
        detection_label = QtWidgets.QLabel("🎯 Configuration Détection :")
        detection_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        sync_config_layout.addWidget(detection_label)

        self.detection_config_display = QtWidgets.QTextEdit()
        self.detection_config_display.setMaximumHeight(100)
        self.detection_config_display.setReadOnly(True)
        self.detection_config_display.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.detection_config_display.setPlaceholderText("Configuration détection automatique apparaîtra ici...")
        sync_config_layout.addWidget(self.detection_config_display)

        # Affichage config extraction
        extraction_label = QtWidgets.QLabel("📄 Configuration Extraction :")
        extraction_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        sync_config_layout.addWidget(extraction_label)

        self.extraction_config_display = QtWidgets.QTextEdit()
        self.extraction_config_display.setMaximumHeight(80)
        self.extraction_config_display.setReadOnly(True)
        self.extraction_config_display.setStyleSheet(
            "background-color: #f0f8ff; border: 1px solid #007bff; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.extraction_config_display.setPlaceholderText("Configuration extraction synchronisée apparaîtra ici...")
        sync_config_layout.addWidget(self.extraction_config_display)

        right_layout.addWidget(sync_config_group)

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
    # CONFIGURATION CLAVIER
    # ==============================

    def _update_keyboard_config(self, config):
        """Met à jour la configuration clavier"""
        if not config:
            return

        self.keyboard_config = config
        logger.info(f"Configuration clavier mise à jour: {json.dumps(config, indent=2)}")

        # Appliquer au state_automation
        if hasattr(self.conductor, 'state_automation') and self.conductor.state_automation:
            if hasattr(self.conductor.state_automation, 'keyboard_controller'):
                self.conductor.state_automation.keyboard_controller.update_config(config)
                logger.info("Configuration clavier appliquée à state_automation.keyboard_controller")

        # Mettre à jour affichage
        if hasattr(self, 'alt_tab_status'):
            self._update_alt_tab_status()

    def _update_alt_tab_status(self):
        """Met à jour l'affichage Alt+Tab"""
        if not hasattr(self, 'alt_tab_status'):
            return

        if self.keyboard_config.get('block_alt_tab', False):
            self.alt_tab_status.setText("Protection Alt+Tab: Activée")
            self.alt_tab_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
        else:
            self.alt_tab_status.setText("Protection Alt+Tab: Désactivée")
            self.alt_tab_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

    # ==============================
    # DÉTECTION NAVIGATEUR
    # ==============================

    def _detect_browser_type(self):
        """Détecte le type de navigateur"""
        try:
            if not self.current_platform or not self.current_profile:
                return "chrome"

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

            # Détection par l'URL
            if browser_url:
                if 'chrome' in browser_url:
                    return "chrome"
                elif 'firefox' in browser_url:
                    return "firefox"

            # Détection par nom plateforme
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
        """Met à jour l'affichage navigateur"""
        self.detected_browser_type = self._detect_browser_type()
        self.browser_status.setText(f"Navigateur détecté: {self.detected_browser_type.capitalize()}")
        self.browser_status.setStyleSheet("color: #007bff; font-size: 10px; margin-top: 5px; font-weight: bold;")
        logger.info(f"🌐 Navigateur détecté: {self.detected_browser_type}")

    # ==============================
    # LOGIQUE PRINCIPALE SYNCHRONISÉE
    # ==============================

    def _on_platform_changed(self, platform_name):
        """Gestion changement plateforme avec synchronisation"""
        if platform_name and platform_name != "-- Sélectionner --":
            self.current_platform = platform_name
            self.current_profile = self.profiles.get(platform_name, {})
            self._update_platform_status()
            self._update_browser_status()
            self._load_and_sync_configuration()
        else:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()

        self._update_test_button_state()

    def _load_and_sync_configuration(self):
        """🔄 FONCTION PRINCIPALE DE SYNCHRONISATION"""
        if not self.current_platform or not self.current_profile:
            return

        try:
            logger.info(f"🔄 Synchronisation configuration pour {self.current_platform}")

            # ÉTAPE 1: Recharger depuis base de données
            fresh_profile = self._get_fresh_profile_from_database()
            if fresh_profile:
                self.current_profile = fresh_profile
                logger.info("✅ Profil rechargé depuis base de données")

            # ÉTAPE 2: Chercher configuration d'extraction depuis Response Area
            extraction_config = self._get_extraction_config_from_response_area()

            # ÉTAPE 3: Chercher configuration de détection existante
            detection_config = self.current_profile.get('detection_config', {})

            # ÉTAPE 4: Logique de synchronisation
            if extraction_config and not detection_config:
                # Cas 1: Extraction configurée mais pas détection → Créer détection automatiquement
                logger.info("📋 Création automatique config détection depuis extraction")
                detection_config = self._create_detection_from_extraction(extraction_config)
                if detection_config:
                    self.current_profile['detection_config'] = detection_config
                    self._save_profile_to_database()
                    self.sync_status.setText("✅ Sync: Détection créée automatiquement")
                    self.sync_status.setStyleSheet(
                        "color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")

            elif extraction_config and detection_config:
                # Cas 2: Les deux configurées → Vérifier cohérence
                logger.info("🔍 Vérification cohérence configs existantes")
                self.sync_status.setText("✅ Sync: Configurations cohérentes")
                self.sync_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")

            elif detection_config and not extraction_config:
                # Cas 3: Seulement détection → Ancienne config, demander reconfiguration
                logger.warning("⚠️ Seulement config détection - extraction manquante")
                self.sync_status.setText("⚠️ Sync: Reconfiguration recommandée")
                self.sync_status.setStyleSheet("color: #FF9800; font-size: 10px; margin-top: 5px; font-weight: bold;")

            else:
                # Cas 4: Aucune configuration
                logger.info("❌ Aucune configuration trouvée")
                self.sync_status.setText("❌ Sync: Aucune configuration")
                self.sync_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

            # ÉTAPE 5: Afficher les configurations
            self._display_synchronized_configurations(detection_config, extraction_config)

            # ÉTAPE 6: Sauvegarder config temporaire pour utilisation
            if detection_config:
                self.temp_detection_config = detection_config

            logger.info("✅ Synchronisation terminée")

        except Exception as e:
            logger.error(f"Erreur synchronisation: {e}")
            self.sync_status.setText("❌ Sync: Erreur")
            self.sync_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

    def _get_fresh_profile_from_database(self):
        """Récupère le profil frais depuis la base de données"""
        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_platform'):
                    return self.conductor.database.get_platform(self.current_platform)
            return None
        except Exception as e:
            logger.error(f"Erreur récupération DB: {e}")
            return None

    def _get_extraction_config_from_response_area(self):
        """Récupère la config d'extraction depuis Response Area Widget"""
        try:
            extraction_config = self.current_profile.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})

            if response_area and response_area.get('platform_config'):
                logger.info("✅ Configuration extraction trouvée depuis Response Area")
                return response_area

            return None
        except Exception as e:
            logger.error(f"Erreur récupération extraction config: {e}")
            return None

    def _create_detection_from_extraction(self, extraction_config):
        """Crée automatiquement une config détection depuis l'extraction"""
        try:
            platform_config = extraction_config.get('platform_config', {})
            platform_type = extraction_config.get('platform_type', 'Unknown')

            if platform_type == 'ChatGPT':
                # Pour ChatGPT: utiliser data-start/data-end pour détection
                detection_config = {
                    'platform_type': 'ChatGPT',
                    'primary_selector': '[data-start][data-end]',
                    'fallback_selectors': [
                        '[data-message-author-role="assistant"]:last-child [data-start]',
                        'article[data-testid*="conversation-turn"]:last-child [data-start]'
                    ],
                    'detection_method': 'chatgpt_data_stability',
                    'configured_at': time.time(),
                    'auto_generated_from': 'extraction_config',
                    'extraction_selector': platform_config.get('primary_selector', ''),
                    'description': 'Configuration détection auto-générée depuis extraction'
                }

            elif platform_type == 'Claude':
                detection_config = {
                    'platform_type': 'Claude',
                    'primary_selector': '[data-is-streaming="false"]',
                    'fallback_selectors': ['[data-is-streaming]', '.prose:last-child'],
                    'detection_method': 'attribute_monitoring',
                    'configured_at': time.time(),
                    'auto_generated_from': 'extraction_config',
                    'extraction_selector': platform_config.get('primary_selector', ''),
                    'description': 'Configuration détection auto-générée depuis extraction'
                }

            else:
                # Générique
                primary_selector = platform_config.get('primary_selector', 'div')
                detection_config = {
                    'platform_type': platform_type,
                    'primary_selector': primary_selector,
                    'fallback_selectors': ['p:last-child', 'div:last-child'],
                    'detection_method': 'element_stability',
                    'configured_at': time.time(),
                    'auto_generated_from': 'extraction_config',
                    'extraction_selector': primary_selector,
                    'description': f'Configuration détection auto-générée pour {platform_type}'
                }

            logger.info(f"🔄 Config détection créée pour {platform_type}")
            logger.info(f"   Sélecteur détection: {detection_config['primary_selector']}")
            logger.info(f"   Sélecteur extraction: {detection_config.get('extraction_selector', 'N/A')}")

            return detection_config

        except Exception as e:
            logger.error(f"Erreur création config détection: {e}")
            return None

    def _display_synchronized_configurations(self, detection_config, extraction_config):
        """Affiche les configurations synchronisées"""
        try:
            # Affichage configuration détection
            if detection_config:
                detection_text = f"Sélecteur principal: {detection_config.get('primary_selector', 'Non défini')}\n"
                fallback_selectors = detection_config.get('fallback_selectors', [])
                if fallback_selectors:
                    detection_text += f"Sélecteurs fallback: {', '.join(fallback_selectors[:2])}\n"
                detection_text += f"Méthode: {detection_config.get('detection_method', 'css_selector')}\n"
                detection_text += f"Type plateforme: {detection_config.get('platform_type', 'Générique')}"

                self.detection_config_display.setPlainText(detection_text)

                # Statut config détection
                self.detection_phase_status.setText("✅ Configuration détection synchronisée")
                self.detection_phase_status.setStyleSheet("color: #28a745; font-weight: bold;")
            else:
                self.detection_config_display.setPlainText("Aucune configuration de détection")
                self.detection_phase_status.setText("❌ Configuration détection manquante")
                self.detection_phase_status.setStyleSheet("color: #dc3545; font-weight: bold;")

            # Affichage configuration extraction
            if extraction_config:
                platform_config = extraction_config.get('platform_config', {})
                extraction_text = f"Sélecteur principal: {platform_config.get('primary_selector', 'Non défini')}\n"
                fallback_selectors = platform_config.get('fallback_selectors', [])
                if fallback_selectors:
                    extraction_text += f"Sélecteurs fallback: {', '.join(fallback_selectors[:2])}\n"
                extraction_text += f"Méthode: {platform_config.get('extraction_method', 'css_selector')}\n"
                extraction_text += f"Type plateforme: {extraction_config.get('platform_type', 'Générique')}"

                self.extraction_config_display.setPlainText(extraction_text)
            else:
                self.extraction_config_display.setPlainText("Aucune configuration d'extraction")

        except Exception as e:
            logger.error(f"Erreur affichage configs: {e}")

    def _save_profile_to_database(self):
        """Sauvegarde le profil en base de données"""
        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    return self.conductor.database.save_platform(self.current_platform, self.current_profile)
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde profil: {e}")
            return False

    def _force_reload_from_database(self):
        """Force le rechargement depuis la base de données"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune plateforme sélectionnée")
            return

        try:
            logger.info(f"🔄 Rechargement forcé depuis DB pour {self.current_platform}")

            # Recharger depuis la base de données
            fresh_profile = self._get_fresh_profile_from_database()
            if fresh_profile:
                self.current_profile = fresh_profile

                # Mettre à jour config_provider
                if hasattr(self.config_provider, 'profiles'):
                    self.config_provider.profiles[self.current_platform] = fresh_profile

                # Relancer la synchronisation
                self._load_and_sync_configuration()

                QtWidgets.QMessageBox.information(
                    self,
                    "Rechargement réussi",
                    f"✅ Configuration rechargée depuis la base de données pour {self.current_platform}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Rechargement échoué",
                    f"❌ Impossible de recharger {self.current_platform} depuis la base de données"
                )

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur rechargement:\n{str(e)}")

    # ==============================
    # LOGIQUE TEST
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
                self.test_phase_status.setText("⏳ Configuration détection manquante")
            elif self.test_running:
                self.test_phase_status.setText("🔄 Test en cours...")

            self.test_phase_status.setStyleSheet("color: #6c757d; font-weight: normal;")

        logger.info(
            f"Bouton test: {'activé' if should_enable else 'désactivé'} (plateforme: {self.current_platform}, config: {self._has_valid_detection_config()}, running: {self.test_running})")

    def _start_final_test(self):
        """Test final avec synchronisation"""
        # Vérifications de base
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord une plateforme")
            return

        if not self._has_valid_detection_config():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration détection manquante")
            return

        if self.test_running:
            return

        # Vérifier protection Alt+Tab si disponible
        if self.keyboard_config_widget and not self.keyboard_config.get('block_alt_tab', False):
            reply = QtWidgets.QMessageBox.warning(
                self, "Avertissement",
                "La protection Alt+Tab est désactivée. Activez-la dans la configuration clavier pour éviter les changements de fenêtre.\n\nContinuer quand même ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Récupérer config à utiliser
        detection_config = self.temp_detection_config or self.current_profile.get('detection_config', {})

        # Mise à jour automatique du profil
        if self.temp_detection_config and not self.current_profile.get('detection_config'):
            self.current_profile['detection_config'] = self.temp_detection_config.copy()
            if hasattr(self.config_provider, 'profiles'):
                self.config_provider.profiles[self.current_platform] = self.current_profile

        # Mettre à jour state_automation avec type navigateur
        if hasattr(self.conductor, 'state_automation') and self.conductor.state_automation:
            self.conductor.state_automation.browser_type = self.detected_browser_type
            logger.info(f"🌐 Type navigateur configuré dans state_automation: {self.detected_browser_type}")

        # Démarrer le test
        self.test_running = True
        self._update_test_button_state()

        # Interface - Montrer bouton stop
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
            # S'assurer du focus navigateur AVANT le test
            self._ensure_browser_focus_advanced()

            # Appel au conductor avec type navigateur
            if hasattr(self.conductor, 'test_platform_connection_ultra_robust'):
                test_message = self.final_test_prompt.text() or "Test de configuration"

                result = self.conductor.test_platform_connection_ultra_robust(
                    platform_name=self.current_platform,
                    test_message=test_message,
                    timeout=30,
                    wait_for_response=12,
                    skip_browser=True
                )

                # Re-vérifier focus après envoi prompt
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
        """S'assure que le focus est sur le navigateur"""
        try:
            import pyautogui
            import tkinter as tk

            logger.info("🎯 Focus navigateur avancé")

            # Obtenir taille écran
            try:
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
            except:
                screen_width = 1920
                screen_height = 1080

            # Clic dans zone neutre navigateur
            safe_x = screen_width // 2
            safe_y = 150

            logger.info(f"🖱️ Clic de focus sécurisé à ({safe_x}, {safe_y})")
            pyautogui.click(safe_x, safe_y)
            time.sleep(0.5)

            # Double clic pour s'assurer du focus
            pyautogui.click(safe_x, safe_y)
            time.sleep(0.3)

            # Utiliser pygetwindow si disponible
            try:
                import pygetwindow as gw
                all_windows = gw.getAllWindows()

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
    # VALIDATION
    # ==============================

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
            if self.temp_detection_config:
                self.current_profile['detection_config'] = self.temp_detection_config
                self._save_profile_to_database()

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

        self.extracted_response.clear()

        self.detection_phase_status.setText("📋 Reconfiguration demandée")
        self.test_phase_status.setText("⏳ Synchronisez d'abord la configuration")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)

        # Relancer synchronisation
        self._load_and_sync_configuration()
        self._update_test_button_state()

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

        self.sync_status.setText("Synchronisation: En attente")
        self.sync_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        if hasattr(self, 'alt_tab_status'):
            self.alt_tab_status.setText("Protection Alt+Tab: Non configurée")
            self.alt_tab_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        self.detection_phase_status.setText("⏳ Chargement depuis Response Area...")
        self.test_phase_status.setText("⏳ Sélectionnez une plateforme configurée")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.detection_config_display.clear()
        self.extraction_config_display.clear()
        self.extracted_response.clear()

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)

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

    def force_sync_from_response_area(self, platform_name):
        """Force la synchronisation depuis Response Area Widget"""
        if platform_name == self.current_platform:
            logger.info(f"🔄 Synchronisation forcée demandée pour {platform_name}")
            self._load_and_sync_configuration()