#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/response_area_widget.py
"""

import os
import json
import time
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from utils.selector_generator import UniversalSelectorGenerator
from ui.styles.platform_config_style import PlatformConfigStyle


class ResponseAreaWidget(QtWidgets.QWidget):

    response_area_configured = pyqtSignal(str, dict)
    response_area_detected = pyqtSignal(str, dict)
    response_received = pyqtSignal(str, str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # Générateur universel pour thinking + détection
        self.selector_generator = UniversalSelectorGenerator()

        self.configuration_complete = False
        self.temp_thinking_config = {}
        self.temp_detection_config = {}
        self.temp_extraction_config = {}  # 🆕 3ème sélecteur automatique

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # === COLONNE GAUCHE (contrôles) ===
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)

        # Plateforme
        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(280)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        self.platform_status = QtWidgets.QLabel("Sélectionnez une plateforme...")
        self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.platform_status.setWordWrap(True)
        platform_layout.addWidget(self.platform_status)

        left_column.addWidget(platform_group)

        # Actions
        actions_group = QtWidgets.QGroupBox("⚙️ Configuration")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(280)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        self.send_prompt_button = QtWidgets.QPushButton("🚀 Envoyer un prompt")
        self.send_prompt_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.send_prompt_button.clicked.connect(self._send_test_prompt)
        actions_layout.addWidget(self.send_prompt_button)

        self.prompt_text_input = QtWidgets.QLineEdit()
        self.prompt_text_input.setText("Explique-moi brièvement les antioxydants")
        self.prompt_text_input.setPlaceholderText("Prompt de test...")
        self.prompt_text_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        actions_layout.addWidget(self.prompt_text_input)

        # Boutons validation
        buttons_layout = QtWidgets.QHBoxLayout()
        
        self.validate_button = QtWidgets.QPushButton("✅ Valider")
        self.validate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45A049; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        self.validate_button.clicked.connect(self._validate_and_save)
        self.validate_button.setEnabled(False)
        
        self.retry_button = QtWidgets.QPushButton("🔄 Reset")
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        self.retry_button.clicked.connect(self._reset_configuration)
        self.retry_button.setEnabled(False)
        
        buttons_layout.addWidget(self.validate_button)
        buttons_layout.addWidget(self.retry_button)
        actions_layout.addLayout(buttons_layout)

        # Status
        self.config_status = QtWidgets.QLabel("⏳ Envoyez d'abord un prompt")
        self.config_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.config_status.setWordWrap(True)
        actions_layout.addWidget(self.config_status)

        left_column.addWidget(actions_group)

        # Statut global
        global_group = QtWidgets.QGroupBox("📊 Statut")
        global_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        global_group.setMaximumWidth(280)
        global_layout = QtWidgets.QVBoxLayout(global_group)

        self.global_status = QtWidgets.QLabel("🔄 En attente")
        self.global_status.setAlignment(Qt.AlignCenter)
        self.global_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.global_status.setWordWrap(True)
        global_layout.addWidget(self.global_status)

        left_column.addWidget(global_group)
        left_column.addStretch(1)

        # === COLONNE DROITE (HTML inputs) ===
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)

        # Instructions
        instructions = QtWidgets.QLabel(
            "<b>🧠 THINKING + 🔍 DÉTECTION + 📝 EXTRACTION</b><br>"
            "1. 🚀 Envoyez un prompt et attendez la réponse<br>"
            "2. 🧠 F12 → Clic droit sur élément THINKING → Copy outerHTML<br>"
            "3. 🔍 F12 → Clic droit sur indicateur FIN → Copy outerHTML<br>"
            "<i>💡 Le 2ème champ génère automatiquement détection + extraction !</i>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #2196F3; font-size: 9px; margin: 5px;")
        right_column.addWidget(instructions)

        # Zone THINKING
        thinking_group = QtWidgets.QGroupBox("🧠 THINKING (outerHTML)")
        thinking_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        thinking_layout = QtWidgets.QVBoxLayout(thinking_group)

        self.thinking_html_input = QtWidgets.QTextEdit()
        self.thinking_html_input.setPlaceholderText("Collez le outerHTML de l'élément thinking...")
        self.thinking_html_input.setMaximumHeight(80)
        self.thinking_html_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.thinking_html_input.textChanged.connect(self._on_thinking_html_changed)
        thinking_layout.addWidget(self.thinking_html_input)

        self.thinking_result = QtWidgets.QLabel("⏳ En attente du HTML thinking")
        self.thinking_result.setStyleSheet("font-size: 9px; color: #666;")
        self.thinking_result.setWordWrap(True)
        thinking_layout.addWidget(self.thinking_result)

        right_column.addWidget(thinking_group)

        # Zone DÉTECTION
        detection_group = QtWidgets.QGroupBox("🔍 DÉTECTION fin génération (outerHTML)")
        detection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        detection_layout = QtWidgets.QVBoxLayout(detection_group)

        self.detection_html_input = QtWidgets.QTextEdit()
        self.detection_html_input.setPlaceholderText("Collez le outerHTML de l'indicateur de fin de génération...")
        self.detection_html_input.setMaximumHeight(80)
        self.detection_html_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.detection_html_input.textChanged.connect(self._on_detection_html_changed)
        detection_layout.addWidget(self.detection_html_input)

        self.detection_result = QtWidgets.QLabel("⏳ En attente du HTML détection")
        self.detection_result.setStyleSheet("font-size: 9px; color: #666;")
        self.detection_result.setWordWrap(True)
        detection_layout.addWidget(self.detection_result)

        right_column.addWidget(detection_group)

        # Zone résultats
        results_group = QtWidgets.QGroupBox("📋 Sélecteurs générés")
        results_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        results_layout = QtWidgets.QVBoxLayout(results_group)

        self.generated_selectors = QtWidgets.QTextEdit()
        self.generated_selectors.setMaximumHeight(80)
        self.generated_selectors.setReadOnly(True)
        self.generated_selectors.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 8px;"
        )
        self.generated_selectors.setPlaceholderText("Les sélecteurs thinking + détection apparaîtront ici...")
        results_layout.addWidget(self.generated_selectors)

        right_column.addWidget(results_group)
        right_column.addStretch(1)

        # Assemblage final
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(300)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

    def set_profiles(self, profiles):
        self.profiles = profiles
        self._update_platform_combo()

    def select_platform(self, platform_name):
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        self._update_platform_combo()

    def _update_platform_combo(self):
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
        if platform_name and platform_name != "-- Sélectionnez une plateforme --":
            self.current_platform = platform_name
            self.current_profile = self.profiles.get(platform_name, {})
            self._update_platform_status()
            self._reset_configuration()
            self._load_existing_configuration()
        else:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()

    def _update_platform_status(self):
        if not self.current_platform or not self.current_profile:
            return

        browser_config = self.current_profile.get('browser', {})
        interface_positions = self.current_profile.get('interface_positions', {})
        window_position = self.current_profile.get('window_position')

        missing_items = []
        if not browser_config.get('url'):
            missing_items.append("URL")
        if not interface_positions.get('prompt_field'):
            missing_items.append("Prompt")
        if not window_position or not window_position.get('x'):
            missing_items.append("Position")

        if missing_items:
            self.platform_status.setText(f"⚠️ Manque: {', '.join(missing_items)}")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
            self.send_prompt_button.setEnabled(False)
        else:
            self.platform_status.setText("✅ Prête")
            self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.send_prompt_button.setEnabled(True)

    def _load_existing_configuration(self):
        if not self.current_platform:
            return

        try:
            # Charger configuration existante si disponible
            saved_profile = None
            
            if hasattr(self.conductor, 'get_platform_profile'):
                saved_profile = self.conductor.get_platform_profile(self.current_platform)
            elif hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_platform'):
                    saved_profile = self.conductor.database.get_platform(self.current_platform)

            if saved_profile:
                self.current_profile = saved_profile

            # Vérifier si thinking+détection existent
            thinking_detection = self.current_profile.get('thinking_detection_config', {})
            
            if thinking_detection:
                self._display_existing_thinking_detection(thinking_detection)

        except Exception as e:
            logger.error(f"Erreur chargement config thinking/détection: {e}")

    def _display_existing_thinking_detection(self, config):
        """Affiche une configuration thinking+détection existante"""
        try:
            thinking_config = config.get('thinking_config')
            detection_config = config.get('detection_config')
            
            if thinking_config:
                selector = thinking_config.get('selector', 'N/A')
                self.thinking_result.setText(f"✅ Thinking: {selector}")
                self.thinking_result.setStyleSheet("font-size: 9px; color: #4CAF50;")
            else:
                self.thinking_result.setText("ℹ️ Pas de thinking pour cette plateforme")
                self.thinking_result.setStyleSheet("font-size: 9px; color: #666;")

            if detection_config:
                selector = detection_config.get('primary_selector', 'N/A')
                method = detection_config.get('method', 'N/A')
                self.detection_result.setText(f"✅ Détection: {method}")
                self.detection_result.setStyleSheet("font-size: 9px; color: #4CAF50;")
            
            # Affichage synthèse
            platform = config.get('platform_type', self.current_platform)
            has_thinking = thinking_config is not None
            
            summary = f"🎯 {platform.upper()}\n"
            summary += f"🧠 THINKING: {'Oui' if has_thinking else 'Non'}\n"
            if has_thinking:
                summary += f"   {thinking_config.get('selector', 'N/A')}\n"
            summary += f"🔍 DÉTECTION: {detection_config.get('method', 'N/A')}\n"
            summary += f"   {detection_config.get('primary_selector', 'N/A')[:50]}..."

            self.generated_selectors.setPlainText(summary)
            
            self.configuration_complete = True
            self.config_status.setText("✅ Configuration existante chargée")
            self.config_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.validate_button.setEnabled(False)
            self.retry_button.setEnabled(True)
            self._update_global_status()

        except Exception as e:
            logger.error(f"Erreur affichage config existante: {e}")

    def _send_test_prompt(self):
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune plateforme sélectionnée")
            return

        try:
            self.send_prompt_button.setEnabled(False)
            self.config_status.setText("🚀 Envoi du prompt...")
            self.config_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

            # Utiliser le state_automation du conductor
            if not hasattr(self.conductor, 'state_automation'):
                from core.interaction.mouse import MouseController
                from core.interaction.keyboard import KeyboardController
                
                mouse_controller = MouseController()
                keyboard_controller = KeyboardController()
                
                self.conductor.state_automation = StateBasedAutomation(
                    None, mouse_controller, keyboard_controller, self.conductor
                )

            state_automation = self.conductor.state_automation

            def on_automation_completed(success, message, duration, response):
                self.send_prompt_button.setEnabled(True)
                if success:
                    self.config_status.setText("✅ Prompt envoyé - Copiez maintenant les HTML")
                    self.config_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                    QtWidgets.QMessageBox.information(
                        self,
                        "Prompt envoyé",
                        f"✅ Prompt envoyé avec succès en {duration:.1f}s\n\n"
                        f"Maintenant :\n"
                        f"1. 🧠 F12 → Clic droit sur THINKING → Copy outerHTML\n"
                        f"2. 📥 Collez dans le premier champ\n"
                        f"3. 🔍 F12 → Clic droit sur indicateur FIN → Copy outerHTML\n"
                        f"4. 📥 Collez dans le deuxième champ"
                    )
                else:
                    self.config_status.setText(f"❌ Erreur: {message}")
                    self.config_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            try:
                state_automation.automation_completed.disconnect()
            except:
                pass
            
            state_automation.automation_completed.connect(on_automation_completed)

            automation_params = {
                'use_tab_navigation': False,
                'use_enter_to_submit': True,
                'wait_before_submit': 1.0,
                'test_text': self.prompt_text_input.text().strip(),
                'skip_browser_activation': True
            }

            browser_type = self.current_profile.get('browser', {}).get('type', 'Chrome')
            browser_url = self.current_profile.get('browser', {}).get('url', '')

            state_automation.start_test_automation(
                self.current_profile, 0, browser_type, browser_url, automation_params
            )

        except Exception as e:
            self.send_prompt_button.setEnabled(True)
            self.config_status.setText(f"❌ Erreur: {str(e)}")
            self.config_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec envoi: {str(e)}")

    def _on_thinking_html_changed(self):
        html_content = self.thinking_html_input.toPlainText().strip()
        
        if len(html_content) > 50:
            if hasattr(self, '_thinking_timer'):
                self._thinking_timer.stop()

            self._thinking_timer = QtCore.QTimer()
            self._thinking_timer.setSingleShot(True)
            self._thinking_timer.timeout.connect(self._analyze_thinking_html)
            self._thinking_timer.start(800)

    def _on_detection_html_changed(self):
        html_content = self.detection_html_input.toPlainText().strip()
        
        if len(html_content) > 50:
            if hasattr(self, '_detection_timer'):
                self._detection_timer.stop()

            self._detection_timer = QtCore.QTimer()
            self._detection_timer.setSingleShot(True)
            self._detection_timer.timeout.connect(self._analyze_detection_html)
            self._detection_timer.start(800)

    def _analyze_thinking_html(self):
        html_content = self.thinking_html_input.toPlainText().strip()
        
        if not html_content:
            return

        try:
            # Analyser spécifiquement le thinking
            thinking_config = self._extract_thinking_selector(html_content)
            
            if thinking_config:
                self.temp_thinking_config = thinking_config
                selector = thinking_config.get('selector', 'N/A')
                completion = thinking_config.get('completion_indicator', 'N/A')
                
                self.thinking_result.setText(f"✅ Thinking: {selector[:30]}...")
                self.thinking_result.setStyleSheet("font-size: 9px; color: #4CAF50;")
                
                logger.info(f"🧠 Thinking configuré: {selector}")
            else:
                self.thinking_result.setText("❌ Aucun thinking détecté")
                self.thinking_result.setStyleSheet("font-size: 9px; color: #f44336;")
                self.temp_thinking_config = {}

            self._update_generated_selectors()

        except Exception as e:
            self.thinking_result.setText(f"❌ Erreur: {str(e)[:30]}...")
            self.thinking_result.setStyleSheet("font-size: 9px; color: #f44336;")
            logger.error(f"Erreur analyse thinking: {e}")

    def _analyze_detection_html(self):
        html_content = self.detection_html_input.toPlainText().strip()
        
        if not html_content:
            return

        try:
            # 🔍 Analyser la détection
            detection_config = self._extract_detection_selector(html_content)
            
            if detection_config:
                self.temp_detection_config = detection_config
                method = detection_config.get('method', 'N/A')
                
                self.detection_result.setText(f"✅ Détection: {method}")
                self.detection_result.setStyleSheet("font-size: 9px; color: #4CAF50;")
                
                logger.info(f"🔍 Détection configurée: {method}")
                
                # 🆕 GÉNÉRER AUTOMATIQUEMENT L'EXTRACTION depuis le même HTML
                extraction_config = self._extract_extraction_selector(html_content)
                if extraction_config:
                    self.temp_extraction_config = extraction_config
                    logger.info(f"📝 Extraction générée automatiquement: {extraction_config.get('primary_selector', 'N/A')}")
                else:
                    self.temp_extraction_config = {}
            else:
                self.detection_result.setText("❌ Pas de détection trouvée")
                self.detection_result.setStyleSheet("font-size: 9px; color: #f44336;")
                self.temp_detection_config = {}
                self.temp_extraction_config = {}  # Reset extraction aussi

            self._update_generated_selectors()

        except Exception as e:
            self.detection_result.setText(f"❌ Erreur: {str(e)[:30]}...")
            self.detection_result.setStyleSheet("font-size: 9px; color: #f44336;")
            logger.error(f"Erreur analyse détection: {e}")
            self.temp_detection_config = {}
            self.temp_extraction_config = {}

    def _extract_thinking_selector(self, html_content):
        """🔧 CORRIGÉ : Extrait la configuration thinking depuis le HTML"""
        try:
            platform = self._detect_platform_from_html(html_content)
            
            # 🔧 PATTERNS THINKING CORRIGÉS
            thinking_patterns = {
                'claude': {
                    'selectors': ['antml\\:thinking', 'thinking-block'],
                    'completion_indicators': ['antml\\:thinking[complete="true"]', '[thinking-complete="true"]']
                },
                'chatgpt': {
                    'selectors': ['.thinking-indicator', '.o1-thinking'],
                    'completion_indicators': ['.thinking-indicator[complete]', '.o1-thinking[data-complete="true"]']
                },
                'gemini': {
                    'selectors': ['ms-thought-chunk', 'thinking-progress-icon', 'thought-panel'],  # 🆕 RÉELS
                    'completion_indicators': [
                        'ms-thought-chunk:not(:has(.thinking-progress-icon.in-progress))',      # 🆕 RÉEL
                        'mat-expansion-panel.thought-panel:not(:has(.in-progress))'            # 🆕 RÉEL
                    ]
                },
                'grok': {
                    'selectors': ['.thought-process', '.reasoning-mode'],
                    'completion_indicators': ['.thought-process[complete]', '.reasoning-mode[done]']
                },
                'deepseek': {
                    'selectors': ['.thinking-stage', '.analysis-phase'],
                    'completion_indicators': ['.thinking-stage[complete]', '.analysis-phase[done]']
                }
            }
            
            if platform in thinking_patterns:
                patterns = thinking_patterns[platform]
                
                # Vérifier si du thinking est présent
                html_lower = html_content.lower()
                for selector in patterns['selectors']:
                    selector_clean = selector.replace('\\:', ':').replace('\\\\', '\\').lower()
                    if selector_clean in html_lower:
                        return {
                            'platform': platform,
                            'selector': selector,
                            'completion_indicator': patterns['completion_indicators'][0],
                            'description': f'Thinking {platform}',
                            'detected_from_html': True
                        }
            
            # Pas de thinking détecté
            return None

        except Exception as e:
            logger.error(f"Erreur extraction thinking: {e}")
            return None

    def _extract_detection_selector(self, html_content):
        """🔧 CORRIGÉ : Extrait la configuration détection depuis le HTML"""
        try:
            platform = self._detect_platform_from_html(html_content)
            
            # 🔧 PATTERNS DE DÉTECTION CORRIGÉS (synchronisés avec selector_generator.py)
            detection_patterns = {
                'claude': {
                    'method': 'attribute_monitoring',
                    'primary_selector': '[data-is-streaming="false"]',
                    'fallbacks': ['[data-is-streaming]', '.font-claude-message']
                },
                'chatgpt': {
                    'method': 'chatgpt_data_stability',
                    'primary_selector': '[data-start][data-end]',
                    'fallbacks': ['[data-message-author-role="assistant"]:last-child', 'article:last-child']
                },
                'gemini': {
                    'method': 'gemini_completion_detection',  # 🆕 CORRIGÉ
                    'primary_selector': 'ms-chat-turn:not(:has(loading-indicator)):has(.model-run-time-pill)',  # 🆕 CORRIGÉ
                    'fallbacks': [
                        'ms-chat-turn:not(:has(loading-indicator))',           # Fallback 1
                        'ms-text-chunk:not(:has(.in-progress))',               # Fallback 2
                        'ms-prompt-chunk:has(.model-run-time-pill)',           # Fallback 3
                        'ms-chat-turn:has(.turn-footer)',                      # Fallback 4
                        '.model-response:last-child'                           # Fallback 5 (ancien)
                    ]
                },
                'grok': {
                    'method': 'class_absence',
                    'primary_selector': '.response-content-markdown:not(:has(.generating))',
                    'fallbacks': ['.response-content-markdown', 'div[class*="response"]']
                },
                'deepseek': {
                    'method': 'element_stability',
                    'primary_selector': '.ds-markdown.ds-markdown--block',
                    'fallbacks': ['.ds-markdown:last-child', 'div[class*="ds-"]']
                }
            }
            
            if platform in detection_patterns:
                config = detection_patterns[platform].copy()
                config['platform'] = platform
                config['fallback_selectors'] = config.pop('fallbacks', [])
                config['detected_from_html'] = True
                return config
            
            # Détection générique
            return {
                'platform': 'generic',
                'method': 'text_stability',
                'primary_selector': 'div:last-child',
                'fallback_selectors': ['p:last-child', 'span:last-child'],
                'detected_from_html': True
            }

        except Exception as e:
            logger.error(f"Erreur extraction détection: {e}")
            return None

    def _detect_platform_from_html(self, html_content):
        """🔧 CORRIGÉ : Détecte la plateforme depuis le HTML avec scores pondérés"""
        html_lower = html_content.lower()
        
        # 🔧 SCORES PONDÉRÉS pour meilleure détection
        scores = {'claude': 0, 'chatgpt': 0, 'gemini': 0, 'grok': 0, 'deepseek': 0}
        
        # Patterns Claude
        if any(pattern in html_lower for pattern in ['antml:thinking', 'claude.ai', 'anthropic']):
            scores['claude'] += 3
        if any(pattern in html_lower for pattern in ['data-is-streaming', 'claude-message']):
            scores['claude'] += 2
            
        # Patterns ChatGPT  
        if any(pattern in html_lower for pattern in ['data-message-author-role', 'openai', 'chatgpt']):
            scores['chatgpt'] += 3
        if any(pattern in html_lower for pattern in ['data-start', 'data-end']):
            scores['chatgpt'] += 2
            
        # 🆕 PATTERNS GEMINI RENFORCÉS
        if any(pattern in html_lower for pattern in ['model-run-time-pill', 'ms-thought-chunk']):
            scores['gemini'] += 4  # Score élevé pour ces patterns très spécifiques
        if any(pattern in html_lower for pattern in ['ms-text-chunk', 'ms-cmark-node', 'ms-chat-turn']):
            scores['gemini'] += 3  # Score moyen-élevé
        if any(pattern in html_lower for pattern in ['_ngcontent-ng-c', 'ms-prompt-chunk']):
            scores['gemini'] += 2  # Score moyen
        if 'gemini' in html_lower or 'aistudio.google.com' in html_lower:
            scores['gemini'] += 3
            
        # Patterns Grok
        if any(pattern in html_lower for pattern in ['response-content-markdown', 'grok', 'x.ai']):
            scores['grok'] += 3
            
        # Patterns DeepSeek
        if any(pattern in html_lower for pattern in ['ds-markdown', 'deepseek']):
            scores['deepseek'] += 3
        
        # Détecter le max
        detected = max(scores, key=scores.get)
        max_score = scores[detected]
        
        print(f"🔍 Scores détection: {scores}")
        print(f"🎯 Plateforme détectée: {detected} (score: {max_score})")
        
        # Si score trop faible, retourner generic
        if max_score < 2:
            return 'generic'
            
        return detected

    def _extract_extraction_selector(self, html_content):
        """🆕 NOUVEAU : Extrait automatiquement la configuration extraction depuis le HTML"""
        try:
            platform = self._detect_platform_from_html(html_content)
            
            # 🔧 PATTERNS D'EXTRACTION par plateforme (synchronisés avec selector_generator.py)
            extraction_patterns = {
                'claude': {
                    'primary_selector': '.font-claude-message:last-child',
                    'fallbacks': [
                        '[data-is-streaming="false"] .font-claude-message',
                        'div[data-test-render-count] div:last-child',
                        '.group.relative:last-child'
                    ],
                    'text_cleaning': 'remove_ui_elements'
                },
                'chatgpt': {
                    'primary_selector': 'article[data-testid*="conversation-turn"]:last-child',
                    'fallbacks': [
                        '[data-message-author-role="assistant"]:last-child .markdown',
                        'div[data-message-id]:last-child .prose'
                    ],
                    'text_cleaning': 'preserve_markdown_structure'
                },
                'gemini': {
                    'primary_selector': 'ms-text-chunk:last-child',                          # 🎯 Principal
                    'fallbacks': [
                        'ms-text-chunk ms-cmark-node span.ng-star-inserted',                # Spans imbriqués
                        'ms-cmark-node span',                                               # Spans markdown
                        'ms-prompt-chunk ms-text-chunk:last-child',                        # Via prompt chunk
                        'ms-chat-turn .model-prompt-container ms-text-chunk:last-child'    # Via conteneur
                    ],
                    'text_cleaning': 'gemini_enhanced_extraction'
                },
                'grok': {
                    'primary_selector': '.response-content-markdown',
                    'fallbacks': [
                        '.response-content-markdown p:last-child'
                    ],
                    'text_cleaning': 'grok_text_extraction'
                },
                'deepseek': {
                    'primary_selector': '.ds-markdown.ds-markdown--block',
                    'fallbacks': [
                        '.ds-markdown:last-child'
                    ],
                    'text_cleaning': 'deepseek_text_extraction'
                }
            }
            
            if platform in extraction_patterns:
                config = extraction_patterns[platform].copy()
                config['platform'] = platform
                config['fallback_selectors'] = config.pop('fallbacks', [])
                config['detected_from_html'] = True
                config['description'] = f'Extraction automatique {platform}'
                return config
            
            # Extraction générique
            return {
                'platform': 'generic',
                'primary_selector': 'div:last-child',
                'fallback_selectors': ['p:last-child', 'span:last-child'],
                'text_cleaning': 'basic_text_extraction',
                'detected_from_html': True,
                'description': 'Extraction générique'
            }

        except Exception as e:
            logger.error(f"Erreur extraction automatique: {e}")
            return None
        """🔧 CORRIGÉ : Détecte la plateforme depuis le HTML avec scores pondérés"""
        html_lower = html_content.lower()
        
        # 🔧 SCORES PONDÉRÉS pour meilleure détection
        scores = {'claude': 0, 'chatgpt': 0, 'gemini': 0, 'grok': 0, 'deepseek': 0}
        
        # Patterns Claude
        if any(pattern in html_lower for pattern in ['antml:thinking', 'claude.ai', 'anthropic']):
            scores['claude'] += 3
        if any(pattern in html_lower for pattern in ['data-is-streaming', 'claude-message']):
            scores['claude'] += 2
            
        # Patterns ChatGPT  
        if any(pattern in html_lower for pattern in ['data-message-author-role', 'openai', 'chatgpt']):
            scores['chatgpt'] += 3
        if any(pattern in html_lower for pattern in ['data-start', 'data-end']):
            scores['chatgpt'] += 2
            
        # 🆕 PATTERNS GEMINI RENFORCÉS
        if any(pattern in html_lower for pattern in ['model-run-time-pill', 'ms-thought-chunk']):
            scores['gemini'] += 4  # Score élevé pour ces patterns très spécifiques
        if any(pattern in html_lower for pattern in ['ms-text-chunk', 'ms-cmark-node', 'ms-chat-turn']):
            scores['gemini'] += 3  # Score moyen-élevé
        if any(pattern in html_lower for pattern in ['_ngcontent-ng-c', 'ms-prompt-chunk']):
            scores['gemini'] += 2  # Score moyen
        if 'gemini' in html_lower or 'aistudio.google.com' in html_lower:
            scores['gemini'] += 3
            
        # Patterns Grok
        if any(pattern in html_lower for pattern in ['response-content-markdown', 'grok', 'x.ai']):
            scores['grok'] += 3
            
        # Patterns DeepSeek
        if any(pattern in html_lower for pattern in ['ds-markdown', 'deepseek']):
            scores['deepseek'] += 3
        
        # Détecter le max
        detected = max(scores, key=scores.get)
        max_score = scores[detected]
        
        print(f"🔍 Scores détection: {scores}")
        print(f"🎯 Plateforme détectée: {detected} (score: {max_score})")
        
        # Si score trop faible, retourner generic
        if max_score < 2:
            return 'generic'
            
        return detected

    def _update_generated_selectors(self):
        """🆕 AMÉLIORÉ : Met à jour l'affichage des 3 sélecteurs générés"""
        try:
            has_thinking = bool(self.temp_thinking_config)
            has_detection = bool(self.temp_detection_config)
            has_extraction = bool(self.temp_extraction_config)  # 🆕
            
            if not has_thinking and not has_detection:
                self.generated_selectors.setPlaceholderText("En attente des configurations...")
                self.validate_button.setEnabled(False)
                self.retry_button.setEnabled(False)
                return

            platform = 'Unknown'
            if has_thinking:
                platform = self.temp_thinking_config.get('platform', 'Unknown')
            elif has_detection:
                platform = self.temp_detection_config.get('platform', 'Unknown')

            summary = f"🎯 {platform.upper()}\n"
            
            # 🧠 THINKING
            if has_thinking:
                thinking = self.temp_thinking_config
                summary += f"🧠 THINKING: {thinking.get('selector', 'N/A')}\n"
                summary += f"   Completion: {thinking.get('completion_indicator', 'N/A')[:35]}...\n"
            else:
                summary += f"🧠 THINKING: Non configuré\n"
            
            # 🔍 DÉTECTION
            if has_detection:
                detection = self.temp_detection_config
                summary += f"🔍 DÉTECTION: {detection.get('method', 'N/A')}\n"
                summary += f"   Selector: {detection.get('primary_selector', 'N/A')[:35]}...\n"
            else:
                summary += f"🔍 DÉTECTION: Non configuré\n"
            
            # 🆕 📝 EXTRACTION
            if has_extraction:
                extraction = self.temp_extraction_config
                summary += f"📝 EXTRACTION: {extraction.get('primary_selector', 'N/A')[:35]}...\n"
                summary += f"   Fallbacks: {len(extraction.get('fallback_selectors', []))} sélecteurs\n"
            else:
                summary += f"📝 EXTRACTION: Non configuré\n"

            self.generated_selectors.setPlainText(summary)

            # Activer validation si au moins détection est configurée
            can_validate = has_detection
            self.validate_button.setEnabled(can_validate)
            self.retry_button.setEnabled(has_thinking or has_detection)
            
            if can_validate:
                if has_extraction:
                    self.config_status.setText("✅ Prêt pour validation (3 sélecteurs)")
                else:
                    self.config_status.setText("✅ Prêt pour validation (thinking + détection)")
                self.config_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            else:
                self.config_status.setText("⏳ Configurez au moins la détection")
                self.config_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

            self._update_global_status()

        except Exception as e:
            logger.error(f"Erreur mise à jour sélecteurs: {e}")

    def _validate_and_save(self):
        """🆕 AMÉLIORÉ : Valide et sauvegarde les 3 configurations (thinking+détection+extraction)"""
        if not self.temp_detection_config:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration de détection manquante")
            return

        try:
            # Construire la configuration finale avec les 3 sélecteurs
            final_config = {
                'platform_type': self.temp_detection_config.get('platform', self.current_platform),
                'configured_at': time.time(),
                'prompt_text': self.prompt_text_input.text().strip(),
                'thinking_config': self.temp_thinking_config if self.temp_thinking_config else None,
                'detection_config': self.temp_detection_config,
                'extraction_config': self.temp_extraction_config if self.temp_extraction_config else None,  # 🆕
                'has_thinking_phase': bool(self.temp_thinking_config),
                'has_extraction_auto': bool(self.temp_extraction_config),  # 🆕
                'method': 'thinking_detection_extraction_specialized'  # 🆕
            }

            # Sauvegarder dans le profil
            if 'thinking_detection_config' not in self.current_profile:
                self.current_profile['thinking_detection_config'] = {}

            self.current_profile['thinking_detection_config'] = final_config

            # Sauvegarder en base
            success = self._save_to_database()

            if success:
                self.configuration_complete = True
                self.config_status.setText("✅ 3 sélecteurs sauvegardés")  # 🆕
                self.config_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                self.validate_button.setEnabled(False)
                self.retry_button.setEnabled(True)
                
                self._update_global_status()

                # Signaler la configuration
                self.response_area_configured.emit(self.current_platform, final_config)
                self.response_area_detected.emit(self.current_platform, {'thinking_detection_extraction': final_config})  # 🆕

                # Message de succès amélioré
                has_thinking = bool(self.temp_thinking_config)
                has_extraction = bool(self.temp_extraction_config)
                platform = final_config['platform_type']
                
                message = f"✅ Configuration sauvegardée pour {self.current_platform}\n\n"
                message += f"🎯 Plateforme: {platform}\n"
                message += f"🧠 Thinking: {'Configuré' if has_thinking else 'Non applicable'}\n"
                message += f"🔍 Détection: {self.temp_detection_config.get('method', 'N/A')}\n"
                message += f"📝 Extraction: {'Auto-générée' if has_extraction else 'Non disponible'}\n\n"  # 🆕
                message += "Configuration complète ! Les 3 sélecteurs sont prêts."

                QtWidgets.QMessageBox.information(self, "✅ Configuration sauvegardée", message)
            else:
                raise Exception("Échec de sauvegarde en base de données")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec sauvegarde: {str(e)}")
            logger.error(f"Erreur sauvegarde thinking+détection+extraction: {e}")

    def _save_to_database(self):
        """Sauvegarde le profil en base de données"""
        try:
            if hasattr(self.conductor, 'get_platform_profile'):
                success = self._save_via_conductor()
                if success:
                    return True
            
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    return self.conductor.database.save_platform(self.current_platform, self.current_profile)

            # Fallback fichier
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            logger.error(f"Erreur sauvegarde: {str(e)}")
            return False

    def _save_via_conductor(self):
        try:
            if hasattr(self.conductor, 'config_provider'):
                profiles = self.conductor.config_provider.get_profiles()
                profiles[self.current_platform] = self.current_profile
                if hasattr(self.conductor.config_provider, 'save_profiles'):
                    return self.conductor.config_provider.save_profiles(profiles)
            return False
        except Exception:
            return False

    def _reset_configuration(self):
        """🆕 AMÉLIORÉ : Reset les 3 configurations"""
        self.temp_thinking_config = {}
        self.temp_detection_config = {}
        self.temp_extraction_config = {}  # 🆕
        self.configuration_complete = False

        self.thinking_html_input.clear()
        self.detection_html_input.clear()
        self.generated_selectors.clear()

        self.thinking_result.setText("⏳ En attente du HTML thinking")
        self.thinking_result.setStyleSheet("font-size: 9px; color: #666;")
        
        self.detection_result.setText("⏳ En attente du HTML détection")
        self.detection_result.setStyleSheet("font-size: 9px; color: #666;")

        self.config_status.setText("📋 Configuration reset - Envoyez un prompt")
        self.config_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())

        self.validate_button.setEnabled(False)
        self.retry_button.setEnabled(False)

        self._update_global_status()

    def _reset_interface(self):
        self._reset_configuration()
        self.platform_status.setText("Sélectionnez une plateforme...")
        self.platform_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def _update_global_status(self):
        """🆕 AMÉLIORÉ : Statut global avec 3 sélecteurs"""
        if self.configuration_complete:
            self.global_status.setText("✅ 3 sélecteurs OK")  # 🆕
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        elif self.temp_detection_config:
            has_extraction = bool(self.temp_extraction_config)
            if has_extraction:
                self.global_status.setText("🧪 Prêt (avec extraction)")  # 🆕
            else:
                self.global_status.setText("🧪 Prêt pour validation")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
        else:
            self.global_status.setText("🔄 En configuration")
            self.global_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def force_reload_from_database(self):
        """Recharge la configuration depuis la base de données"""
        if self.current_platform:
            try:
                logger.info(f"🔄 Rechargement thinking+détection pour {self.current_platform}")

                if hasattr(self.conductor, 'database') and self.conductor.database:
                    if hasattr(self.conductor.database, 'get_platform'):
                        fresh_profile = self.conductor.database.get_platform(self.current_platform)
                        if fresh_profile:
                            self.current_profile = fresh_profile
                            self._load_existing_configuration()
                            return True

                return False

            except Exception as e:
                logger.error(f"Erreur rechargement: {e}")
                return False