#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/response_area_widget.py - Version simple focalisée sur la configuration d'extraction
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
        print("[DEBUG] ===== ResponseAreaWidget: INITIALISATION =====")
        print(f"[DEBUG] config_provider = {type(config_provider)}")
        print(f"[DEBUG] conductor = {type(conductor)}")
        print(
            f"[DEBUG] conductor.database = {type(conductor.database) if hasattr(conductor, 'database') else 'PAS DE DATABASE'}")

        if hasattr(conductor, 'database') and conductor.database:
            print(f"[DEBUG] DATABASE TROUVÉE - Type: {type(conductor.database)}")
            print(
                f"[DEBUG] Méthodes database disponibles: {[method for method in dir(conductor.database) if not method.startswith('_')]}")
            print(f"[DEBUG] Database a get_platform? {hasattr(conductor.database, 'get_platform')}")
            print(f"[DEBUG] Database a save_platform? {hasattr(conductor.database, 'save_platform')}")
        else:
            print("[DEBUG] PAS DE DATABASE DISPONIBLE !")

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # Système d'automatisation intelligente
        self.state_automation = None

        try:
            self._init_ui()
            print("[DEBUG] ResponseAreaWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de ResponseAreaWidget: {str(e)}")
            print(f"[DEBUG] ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """Configure l'interface utilisateur du widget de zone de réponse - VERSION SIMPLIFIÉE"""
        print("[DEBUG] _init_ui: Début de la création de l'interface")

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

        # Bouton d'envoi de prompt (pour générer une réponse IA)
        self.send_prompt_button = QtWidgets.QPushButton("🚀 Envoyer prompt pour réponse IA")
        self.send_prompt_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.send_prompt_button.clicked.connect(self._on_send_prompt)
        actions_layout.addWidget(self.send_prompt_button)

        # Champ pour personnaliser le prompt d'envoi
        prompt_text_layout = QtWidgets.QHBoxLayout()
        prompt_text_label = QtWidgets.QLabel("Prompt d'envoi:")
        prompt_text_label.setMinimumWidth(80)
        prompt_text_layout.addWidget(prompt_text_label)

        self.prompt_text_input = QtWidgets.QLineEdit()
        self.prompt_text_input.setText("Bonjour, pouvez-vous me répondre ?")  # Valeur par défaut
        self.prompt_text_input.setPlaceholderText("Prompt à envoyer pour que l'IA génère une réponse...")
        self.prompt_text_input.setStyleSheet(PlatformConfigStyle.get_input_style())
        # Connecter le signal pour sauvegarder automatiquement quand l'utilisateur change le texte
        self.prompt_text_input.textChanged.connect(self._on_prompt_text_changed)
        prompt_text_layout.addWidget(self.prompt_text_input)

        actions_layout.addLayout(prompt_text_layout)

        # Bouton d'extraction HTML
        self.html_extract_button = QtWidgets.QPushButton("📋 Extraire via Console HTML")
        self.html_extract_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.html_extract_button.clicked.connect(self._on_html_extraction)
        self.html_extract_button.setEnabled(False)  # Activé après envoi de prompt
        actions_layout.addWidget(self.html_extract_button)

        # Statut de capture
        self.capture_status = QtWidgets.QLabel("Aucune réponse IA capturée")
        self.capture_status.setAlignment(Qt.AlignCenter)
        self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.capture_status.setWordWrap(True)
        actions_layout.addWidget(self.capture_status)

        # Options de capture
        options_layout = QtWidgets.QVBoxLayout()
        self.remember_config_check = QtWidgets.QCheckBox("🔒 Mémoriser la configuration")
        self.remember_config_check.setChecked(True)
        options_layout.addWidget(self.remember_config_check)

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

        # Note sur la suite du processus
        help_note = QtWidgets.QLabel(
            "<b>💡 Note:</b> Après avoir configuré l'extraction, "
            "vous pouvez utiliser la conversation complète depuis l'onglet 'Utilisation complète'.<br><br>"
            "<b>🔧 Cette section configure seulement l'extraction de réponses IA.</b>"
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
            "🎯 <b>Configuration d'extraction de réponses IA</b><br>"
            "Configurez comment extraire les réponses des plateformes d'IA de manière précise."
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
            "1. 🚀 Envoyez d'abord un prompt pour générer une réponse IA<br>"
            "2. ⏳ Attendez qu'une réponse complète apparaisse sur la plateforme<br>"
            "3. 🔧 Appuyez sur F12 pour ouvrir les outils développeur<br>"
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
            ["Console HTML (Recommandé)", "Presse-papiers (Ctrl+A, Ctrl+C)"])
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

        print("[DEBUG] _init_ui: Interface créée avec succès")

    # ====================================================================
    # NOUVEAU: Gestion du changement de prompt d'envoi
    # ====================================================================

    def _on_prompt_text_changed(self):
        """Callback appelé quand l'utilisateur modifie le prompt d'envoi"""
        new_prompt = self.prompt_text_input.text()
        print(f"[DEBUG] ===== _on_prompt_text_changed =====")
        print(f"[DEBUG] Nouveau prompt saisi par utilisateur: '{new_prompt}'")
        print(f"[DEBUG] Current platform: {self.current_platform}")
        print(f"[DEBUG] Current profile exists: {self.current_profile is not None}")

        if self.current_platform and self.current_profile:
            print(f"[DEBUG] Tentative de sauvegarde automatique...")
            # Sauvegarder automatiquement le nouveau prompt
            self._save_prompt_text_to_profile()
        else:
            print(f"[DEBUG] Pas de sauvegarde - pas de plateforme ou profil")

    def _save_prompt_text_to_profile(self):
        """Sauvegarde le prompt d'envoi dans le profil actuel"""
        print(f"[DEBUG] ===== _save_prompt_text_to_profile =====")
        try:
            if 'extraction_config' not in self.current_profile:
                self.current_profile['extraction_config'] = {}
                print(f"[DEBUG] Création extraction_config dans profil")

            if 'response_area' not in self.current_profile['extraction_config']:
                self.current_profile['extraction_config']['response_area'] = {}
                print(f"[DEBUG] Création response_area dans extraction_config")

            # Sauvegarder le prompt d'envoi
            prompt_text = self.prompt_text_input.text().strip()
            self.current_profile['extraction_config']['response_area']['prompt_text'] = prompt_text
            print(f"[DEBUG] Prompt sauvegardé dans profil: '{prompt_text}'")
            print(f"[DEBUG] Profil actuel après modification:")
            print(f"[DEBUG] - extraction_config: {self.current_profile.get('extraction_config', 'MANQUANT')}")

            # Sauvegarder le profil (mais silencieusement, sans message)
            success = self._save_profile_silent()
            print(f"[DEBUG] Résultat sauvegarde silencieuse: {success}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde prompt: {str(e)}")
            print(f"[DEBUG] ERREUR _save_prompt_text_to_profile: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")

    def _save_profile_silent(self):
        """Sauvegarde silencieuse du profil (sans message utilisateur)"""
        print(f"[DEBUG] ===== _save_profile_silent =====")
        print(f"[DEBUG] Current platform: {self.current_platform}")
        print(f"[DEBUG] Current profile exists: {self.current_profile is not None}")

        if not self.current_platform or not self.current_profile:
            print("[DEBUG] _save_profile_silent: Pas de plateforme ou profil - ABANDON")
            return False

        try:
            print(f"[DEBUG] Tentative de sauvegarde silencieuse pour: {self.current_platform}")

            # Méthode 1: Base de données (PRIORITAIRE)
            print(f"[DEBUG] === MÉTHODE 1: Base de données ===")
            print(
                f"[DEBUG] conductor.database exists: {hasattr(self.conductor, 'database') and self.conductor.database}")

            if hasattr(self.conductor, 'database') and self.conductor.database:
                print(f"[DEBUG] Database trouvée: {type(self.conductor.database)}")
                print(f"[DEBUG] Database a save_platform: {hasattr(self.conductor.database, 'save_platform')}")

                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        print(f"[DEBUG] Appel database.save_platform('{self.current_platform}', profile)")
                        print(f"[DEBUG] Profil à sauvegarder: {json.dumps(self.current_profile, indent=2)}")
                        success = self.conductor.database.save_platform(self.current_platform, self.current_profile)
                        print(f"[DEBUG] Résultat database.save_platform: {success}")
                        if success:
                            print("[DEBUG] Sauvegarde DATABASE réussie - RETOUR")
                            return True
                    except Exception as e:
                        print(f"[DEBUG] ERREUR database.save_platform: {str(e)}")
                        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                else:
                    print("[DEBUG] Database n'a pas save_platform - méthode inexistante")
            else:
                print("[DEBUG] Pas de database disponible")

            # Méthode 2: ConfigProvider
            print(f"[DEBUG] === MÉTHODE 2: ConfigProvider ===")
            print(f"[DEBUG] config_provider exists: {self.config_provider is not None}")
            print(f"[DEBUG] config_provider has save_profile: {hasattr(self.config_provider, 'save_profile')}")

            if hasattr(self.config_provider, 'save_profile'):
                try:
                    print(f"[DEBUG] Appel config_provider.save_profile('{self.current_platform}', profile)")
                    success = self.config_provider.save_profile(self.current_platform, self.current_profile)
                    print(f"[DEBUG] Résultat config_provider.save_profile: {success}")
                    if success:
                        print("[DEBUG] Sauvegarde ConfigProvider réussie - RETOUR")
                        return True
                except Exception as e:
                    print(f"[DEBUG] ERREUR config_provider.save_profile: {str(e)}")
                    print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                print("[DEBUG] ConfigProvider n'a pas save_profile")

            # Méthode 3: Sauvegarde directe fichier (DERNIER RECOURS)
            print(f"[DEBUG] === MÉTHODE 3: Fichier direct ===")
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            print(f"[DEBUG] Profiles dir: {profiles_dir}")

            os.makedirs(profiles_dir, exist_ok=True)
            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")
            print(f"[DEBUG] Chemin fichier: {file_path}")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            print(f"[DEBUG] Fichier écrit avec succès")

            # Mettre à jour le cache
            self.profiles[self.current_platform] = self.current_profile
            print(f"[DEBUG] Cache mis à jour")
            print(f"[DEBUG] Sauvegarde fichier réussie: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde silencieuse du profil: {str(e)}")
            print(f"[DEBUG] ERREUR GLOBALE _save_profile_silent: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return False

    # ====================================================================
    # ENVOI DE PROMPT POUR GÉNÉRER UNE RÉPONSE IA
    # ====================================================================

    def _on_send_prompt(self):
        """Envoie un prompt pour que l'IA génère une réponse"""
        print("[DEBUG] ===== _on_send_prompt =====")
        print("[DEBUG] Début de l'envoi de prompt")

        if not self.current_platform:
            print("[DEBUG] Pas de plateforme sélectionnée")
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        print(f"[DEBUG] Plateforme: {self.current_platform}")

        # Vérifier la configuration minimale
        browser_info = self.current_profile.get('browser', {})
        browser_type = browser_info.get('type', 'Chrome')
        browser_url = browser_info.get('url', '')

        print(f"[DEBUG] Browser info: {browser_info}")
        print(f"[DEBUG] Browser type: {browser_type}")
        print(f"[DEBUG] Browser URL: {browser_url}")

        if not browser_url:
            print("[DEBUG] URL manquante")
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "URL du navigateur manquante. Configurez d'abord le navigateur."
            )
            return

        # Vérifier les positions prompt/submit
        positions = self.current_profile.get('interface_positions', {})
        print(f"[DEBUG] Positions disponibles: {list(positions.keys()) if positions else 'AUCUNE'}")

        if not positions.get('prompt_field'):
            print("[DEBUG] Position prompt_field manquante")
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "Position du champ de prompt manquante. Configurez d'abord le champ de prompt."
            )
            return

        print(f"[DEBUG] Position prompt_field: {positions.get('prompt_field')}")

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
            self.send_prompt_button.setEnabled(False)
            self.capture_status.setText("🚀 Envoi du prompt en cours...")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

            # Récupérer le prompt saisi par l'utilisateur
            prompt_text = self.prompt_text_input.text().strip()
            if not prompt_text:
                prompt_text = "Bonjour, pouvez-vous me répondre ?"  # Fallback si vide

            print(f"[DEBUG] Prompt à envoyer: '{prompt_text}'")

            # Paramètres pour envoi de prompt
            automation_params = {
                'use_tab_navigation': False,
                'use_enter_to_submit': True,
                'wait_before_submit': 1.0,
                'skip_tab_count': 0,
                'test_text': prompt_text  # Le prompt à envoyer
            }

            print(f"[DEBUG] Paramètres automation: {automation_params}")

            # Démarrer l'automatisation
            self.state_automation.start_test_automation(
                self.current_profile,
                0,
                browser_type,
                browser_url,
                automation_params
            )

        except ImportError as e:
            logger.error(f"Erreur d'importation contrôleurs: {str(e)}")
            print(f"[DEBUG] Erreur import contrôleurs: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                "Contrôleurs d'interaction non disponibles."
            )
            self.send_prompt_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Erreur démarrage automatisation: {str(e)}")
            print(f"[DEBUG] Erreur démarrage automatisation: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Échec du démarrage: {str(e)}"
            )
            self.send_prompt_button.setEnabled(True)

    def _on_automation_state_changed(self, state, message):
        """Callback pour les changements d'état de l'envoi de prompt"""
        print(f"[DEBUG] _on_automation_state_changed: État = {state}, Message = {message}")
        self.capture_status.setText(f"🔄 {message}")
        self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        QtWidgets.QApplication.processEvents()

    def _on_automation_completed(self, success, message, duration):
        """Callback pour la fin de l'automatisation"""
        print(f"[DEBUG] ===== _on_automation_completed =====")
        print(f"[DEBUG] Success: {success}")
        print(f"[DEBUG] Message: {message}")
        print(f"[DEBUG] Duration: {duration}")

        self.send_prompt_button.setEnabled(True)

        if success:
            self.capture_status.setText(f"✅ Prompt envoyé avec succès")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Activer le bouton d'extraction
            self.html_extract_button.setEnabled(True)

            QtWidgets.QMessageBox.information(
                self,
                "Prompt envoyé avec succès",
                f"🎉 Prompt envoyé en {duration:.1f}s !<br><br>"
                f"Maintenant vous pouvez :<br>"
                f"1. ⏳ Attendre que l'IA génère sa réponse complète<br>"
                f"2. 🔧 Utiliser F12 pour inspecter la réponse<br>"
                f"3. 📋 Extraire le HTML de la réponse<br>"
                f"4. ✅ Sauvegarder la configuration"
            )
        else:
            self.capture_status.setText(f"❌ Erreur: {message}")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'envoi",
                f"Erreur pendant l'envoi du prompt :<br>{message}"
            )

    # ====================================================================
    # EXTRACTION HTML MANUELLE
    # ====================================================================

    def _on_html_extraction(self):
        """Guide l'utilisateur pour l'extraction HTML"""
        print("[DEBUG] _on_html_extraction: Début du guide d'extraction")

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
            "1. 🎯 <b>Assurez-vous qu'il y a une réponse IA complète visible</b><br>"
            "2. 🔧 <b>Appuyez sur F12</b> (ouvre les outils développeur)<br>"
            "3. 🎯 <b>Clic droit sur la zone de réponse IA</b> → Inspecter<br>"
            "4. 📋 <b>Dans l'inspecteur :</b> Clic droit sur l'élément HTML → Copy → Copy element<br>"
            "5. 📥 <b>Collez le HTML</b> dans la zone de texte ci-dessous<br>"
            "6. ✅ <b>Cliquez 'Valider HTML'</b><br><br>"
            "<i>Cette méthode capture précisément la structure de la réponse !</i>",
            QtWidgets.QMessageBox.Ok
        )

        # Focus sur la zone HTML
        self.html_input.setFocus()
        print("[DEBUG] _on_html_extraction: Focus mis sur la zone HTML")

    def _on_validate_html(self):
        """Valide le HTML et extrait le texte"""
        print("[DEBUG] ===== _on_validate_html =====")

        html_content = self.html_input.toPlainText().strip()
        print(f"[DEBUG] HTML content length: {len(html_content)}")
        print(f"[DEBUG] HTML preview (100 chars): '{html_content[:100]}...'")

        if not html_content:
            print("[DEBUG] Pas de HTML fourni")
            QtWidgets.QMessageBox.warning(
                self,
                "HTML manquant",
                "Veuillez coller le HTML dans la zone de texte."
            )
            return

        try:
            # Valider la structure HTML
            is_valid, validation_message = self._validate_html_structure(html_content)
            print(f"[DEBUG] Validation HTML: {is_valid}, Message: {validation_message}")

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
            print("[DEBUG] Tentative d'extraction de texte depuis le HTML")
            extracted_text = self.conductor.detector.extract_text_from_html(html_content)
            print(f"[DEBUG] Texte extrait: '{extracted_text[:200] if extracted_text else 'RIEN'}...'")
            print(f"[DEBUG] Longueur texte extrait: {len(extracted_text) if extracted_text else 0}")

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

            # Mémoriser la configuration si demandé
            if self.remember_config_check.isChecked():
                print("[DEBUG] Sauvegarde configuration demandée")
                success = self._save_html_extraction_config(html_content, extracted_text)
                print(f"[DEBUG] Sauvegarde config HTML: {success}")
                if success:
                    # Test automatique après sauvegarde
                    self._test_saved_configuration()

            # Émettre le signal
            self.response_received.emit(self.current_platform, extracted_text)
            print(f"[DEBUG] Signal response_received émis pour {self.current_platform}")

            QtWidgets.QMessageBox.information(
                self,
                "Extraction réussie",
                f"✅ Texte extrait avec succès !<br><br>"
                f"Longueur : {len(extracted_text)} caractères<br>"
                f"Configuration {'sauvegardée et testée' if self.remember_config_check.isChecked() else 'temporaire'}<br><br>"
                f"{"🎯 Vous pouvez maintenant utiliser l\\'onglet Utilisation complète !" if self.remember_config_check.isChecked() else ''}"
            )

        except Exception as e:
            logger.error(f"Erreur validation HTML: {str(e)}")
            print(f"[DEBUG] ERREUR _on_validate_html: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
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
        """
        try:
            print(f"[DEBUG] _validate_html_structure: Validation de {len(html_content)} caractères")

            # Vérifications basiques
            if len(html_content) < 10:
                return False, "HTML trop court"

            # Vérifier qu'il y a des balises
            if '<' not in html_content or '>' not in html_content:
                return False, "Format HTML invalide"

            # Validation simple des balises
            import re
            opening_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>', html_content)
            closing_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9]*)>', html_content)

            print(f"[DEBUG] Balises ouvrantes: {len(opening_tags)}, fermantes: {len(closing_tags)}")

            # Vérification générale des balises équilibrées
            tag_balance = {}
            for tag in opening_tags:
                tag_balance[tag] = tag_balance.get(tag, 0) + 1
            for tag in closing_tags:
                tag_balance[tag] = tag_balance.get(tag, 0) - 1

            unbalanced = [tag for tag, count in tag_balance.items() if count != 0]
            if unbalanced:
                print(f"[DEBUG] Balises déséquilibrées: {unbalanced}")
                return False, f"Balises non équilibrées: {', '.join(unbalanced)}"

            print("[DEBUG] HTML validé avec succès")
            return True, "HTML validé avec succès"

        except Exception as e:
            print(f"[DEBUG] ERREUR _validate_html_structure: {str(e)}")
            return False, f"Erreur validation: {str(e)}"

    def _save_html_extraction_config(self, html_content, extracted_text):
        """Sauvegarde la configuration d'extraction HTML"""
        print(f"[DEBUG] ===== _save_html_extraction_config =====")
        try:
            print(f"[DEBUG] Sauvegarde config HTML pour: {self.current_platform}")
            print(f"[DEBUG] HTML length: {len(html_content)}")
            print(f"[DEBUG] Extracted text length: {len(extracted_text)}")

            if 'extraction_config' not in self.current_profile:
                self.current_profile['extraction_config'] = {}
                print("[DEBUG] Création extraction_config")

            # Récupérer le prompt actuel
            current_prompt_text = self.prompt_text_input.text().strip()
            if not current_prompt_text:
                current_prompt_text = "Bonjour, pouvez-vous me répondre ?"

            print(f"[DEBUG] Prompt actuel: '{current_prompt_text}'")

            config_to_save = {
                'method': 'html',
                'complete_html': html_content,
                'sample_html': html_content[:500],
                'sample_text': extracted_text[:200],
                'full_extracted_text': extracted_text,
                'configured_at': time.time(),
                'wait_time': self.wait_extraction_spin.value(),
                'prompt_text': current_prompt_text,  # ✅ SAUVEGARDE DU PROMPT
                'extraction_patterns': self._extract_html_patterns(html_content)
            }

            self.current_profile['extraction_config']['response_area'] = config_to_save

            print(f"[DEBUG] Config response_area créée:")
            print(f"[DEBUG] - method: {config_to_save['method']}")
            print(f"[DEBUG] - prompt_text: '{config_to_save['prompt_text']}'")
            print(f"[DEBUG] - wait_time: {config_to_save['wait_time']}")
            print(f"[DEBUG] - configured_at: {config_to_save['configured_at']}")

            # Sauvegarder le profil complet
            success = self._save_profile()
            print(f"[DEBUG] Résultat sauvegarde profil: {success}")
            return success

        except Exception as e:
            logger.error(f"Erreur sauvegarde config HTML: {str(e)}")
            print(f"[DEBUG] ERREUR _save_html_extraction_config: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return False

    def _extract_html_patterns(self, html_content):
        """Extrait des patterns de reconnaissance pour la validation future"""
        print("[DEBUG] _extract_html_patterns: Extraction des patterns")
        import re
        patterns = {}

        # Pattern de balises principales
        main_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>', html_content)
        patterns['main_tags'] = list(set(main_tags))

        # Classes CSS utilisées
        classes = re.findall(r'class="([^"]*)"', html_content)
        patterns['css_classes'] = list(set(' '.join(classes).split()))

        # IDs utilisés
        ids = re.findall(r'id="([^"]*)"', html_content)
        patterns['ids'] = list(set(ids))

        # Structure approximative
        patterns['structure_hash'] = hash(re.sub(r'>[^<]*<', '><', html_content))

        print(f"[DEBUG] Patterns extraits: {patterns}")
        return patterns

    def _test_saved_configuration(self):
        """Test automatique de la configuration sauvegardée"""
        print("[DEBUG] ===== _test_saved_configuration =====")
        try:
            print("[DEBUG] Test de la configuration sauvegardée")

            extraction_config = self.current_profile.get('extraction_config', {})
            response_config = extraction_config.get('response_area', {})
            print(f"[DEBUG] Response config trouvée: {bool(response_config)}")

            if not response_config:
                raise Exception("Aucune configuration à tester")

            # Test de re-extraction
            complete_html = response_config.get('complete_html', '')
            print(f"[DEBUG] HTML complet length: {len(complete_html)}")

            if len(complete_html) < 100:
                raise Exception(f"HTML trop court: {len(complete_html)} caractères")

            re_extracted = self.conductor.detector.extract_text_from_html(complete_html)
            print(f"[DEBUG] Re-extraction: {len(re_extracted) if re_extracted else 0} caractères")

            if not re_extracted or len(re_extracted) < 10:
                raise Exception("Re-extraction échoue")

            print(f"[DEBUG] Test réussi - {len(re_extracted)} caractères extraits")

            # Succès du test
            self.validation_status.setText("✅ Configuration testée et validée")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            QtWidgets.QMessageBox.information(
                self,
                "✅ Configuration validée",
                f"Configuration testée avec succès !\n\n"
                f"📄 HTML: {len(complete_html)} caractères\n"
                f"📝 Texte: {len(re_extracted)} caractères\n\n"
                f"✅ Re-extraction: OK"
            )

            return True

        except Exception as e:
            print(f"[DEBUG] ERREUR _test_saved_configuration: {str(e)}")
            self.validation_status.setText(f"❌ Test échoué: {str(e)}")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            return False

    # ====================================================================
    # MÉTHODES DE BASE (GESTION PLATEFORMES ET SAUVEGARDE)
    # ====================================================================

    def set_profiles(self, profiles):
        """Met à jour les profils disponibles dans le widget"""
        print(f"[DEBUG] ===== set_profiles =====")
        print(f"[DEBUG] Nombre de profils reçus: {len(profiles)}")
        print(f"[DEBUG] Profils: {list(profiles.keys())}")
        self.profiles = profiles
        self._update_platform_combo()

    def select_platform(self, platform_name):
        """Sélectionne une plateforme dans la liste déroulante"""
        print(f"[DEBUG] ===== select_platform =====")
        print(f"[DEBUG] Sélection demandée: {platform_name}")
        index = self.platform_combo.findText(platform_name)
        print(f"[DEBUG] Index trouvé: {index}")
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        """Actualise les données du widget"""
        print("[DEBUG] ===== refresh =====")
        self._update_platform_combo()
        if self.current_platform:
            print(f"[DEBUG] Rechargement de la plateforme: {self.current_platform}")
            self._load_platform_config(self.current_platform)

    def _update_platform_combo(self):
        """Met à jour la liste déroulante des plateformes"""
        print("[DEBUG] ===== _update_platform_combo =====")
        current_text = self.platform_combo.currentText()
        print(f"[DEBUG] Texte actuel: '{current_text}'")

        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionnez une plateforme --")

        platforms = sorted(self.profiles.keys())
        print(f"[DEBUG] Plateformes à ajouter: {platforms}")

        for name in platforms:
            self.platform_combo.addItem(name)

        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)
                print(f"[DEBUG] Plateforme restaurée: '{current_text}' à l'index {index}")

    def _on_platform_selected(self, index):
        """Gère la sélection d'une plateforme dans la liste"""
        print(f"[DEBUG] ===== _on_platform_selected =====")
        print(f"[DEBUG] Index sélectionné: {index}")

        if index <= 0:
            print("[DEBUG] Index 0 ou négatif - reset")
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()
            return

        platform_name = self.platform_combo.currentText()
        print(f"[DEBUG] Plateforme sélectionnée: '{platform_name}'")
        self._load_platform_config(platform_name)

    def _load_platform_config(self, platform_name):
        """Charge la configuration de la plateforme sélectionnée"""
        print(f"[DEBUG] ===== _load_platform_config =====")
        print(f"[DEBUG] Chargement de: '{platform_name}'")

        self.current_platform = platform_name
        profile_loaded = False

        # ===== MÉTHODE 1: Base de données (PRIORITAIRE) =====
        print(f"[DEBUG] === TENTATIVE 1: Base de données ===")
        print(f"[DEBUG] conductor existe: {hasattr(self, 'conductor')}")
        print(f"[DEBUG] conductor.database existe: {hasattr(self.conductor, 'database') and self.conductor.database}")

        if hasattr(self.conductor, 'database') and self.conductor.database:
            print(f"[DEBUG] Database trouvée: {type(self.conductor.database)}")
            print(f"[DEBUG] Database a get_platform: {hasattr(self.conductor.database, 'get_platform')}")

            if hasattr(self.conductor.database, 'get_platform'):
                try:
                    print(f"[DEBUG] Appel database.get_platform('{platform_name}')")
                    self.current_profile = self.conductor.database.get_platform(platform_name)
                    print(f"[DEBUG] Résultat database.get_platform: {self.current_profile}")

                    if self.current_profile:
                        profile_loaded = True
                        print(f"[DEBUG] ✅ PROFIL CHARGÉ DEPUIS DATABASE")
                        print(f"[DEBUG] Contenu profil: {json.dumps(self.current_profile, indent=2)}")
                    else:
                        print(f"[DEBUG] ❌ Database.get_platform a retourné None/False")

                except Exception as e:
                    print(f"[DEBUG] ❌ ERREUR database.get_platform: {str(e)}")
                    print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                print(f"[DEBUG] ❌ Database n'a pas la méthode get_platform")
        else:
            print(f"[DEBUG] ❌ Pas de database disponible")

        # ===== MÉTHODE 2: ConfigProvider =====
        if not profile_loaded:
            print(f"[DEBUG] === TENTATIVE 2: ConfigProvider ===")
            print(f"[DEBUG] config_provider existe: {self.config_provider is not None}")
            print(f"[DEBUG] config_provider a get_profile: {hasattr(self.config_provider, 'get_profile')}")

            if hasattr(self.config_provider, 'get_profile'):
                try:
                    print(f"[DEBUG] Appel config_provider.get_profile('{platform_name}')")
                    self.current_profile = self.config_provider.get_profile(platform_name)
                    print(f"[DEBUG] Résultat config_provider.get_profile: {self.current_profile}")

                    if self.current_profile:
                        profile_loaded = True
                        print(f"[DEBUG] ✅ PROFIL CHARGÉ DEPUIS CONFIGPROVIDER")
                        print(f"[DEBUG] Contenu profil: {json.dumps(self.current_profile, indent=2)}")
                    else:
                        print(f"[DEBUG] ❌ ConfigProvider.get_profile a retourné None/False")

                except Exception as e:
                    print(f"[DEBUG] ❌ ERREUR config_provider.get_profile: {str(e)}")
                    print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                print(f"[DEBUG] ❌ ConfigProvider n'a pas get_profile")

        # ===== MÉTHODE 3: Fichier direct =====
        if not profile_loaded:
            print(f"[DEBUG] === TENTATIVE 3: Fichier direct ===")
            try:
                profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                file_path = os.path.join(profiles_dir, f"{platform_name}.json")
                print(f"[DEBUG] Chemin fichier: {file_path}")
                print(f"[DEBUG] Fichier existe: {os.path.exists(file_path)}")

                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.current_profile = json.load(f)
                        profile_loaded = True
                        print(f"[DEBUG] ✅ PROFIL CHARGÉ DEPUIS FICHIER")
                        print(f"[DEBUG] Contenu profil: {json.dumps(self.current_profile, indent=2)}")
                else:
                    print(f"[DEBUG] ❌ Fichier inexistant")

            except Exception as e:
                print(f"[DEBUG] ❌ ERREUR fichier: {str(e)}")
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")

        # ===== MÉTHODE 4: Cache profiles =====
        if not profile_loaded:
            print(f"[DEBUG] === TENTATIVE 4: Cache profiles ===")
            print(f"[DEBUG] Cache profiles keys: {list(self.profiles.keys())}")
            print(f"[DEBUG] Platform '{platform_name}' dans cache: {platform_name in self.profiles}")

            self.current_profile = self.profiles.get(platform_name, {})
            if self.current_profile:
                print(f"[DEBUG] ✅ PROFIL CHARGÉ DEPUIS CACHE")
                print(f"[DEBUG] Contenu profil cache: {json.dumps(self.current_profile, indent=2)}")
            else:
                print(f"[DEBUG] ❌ Pas de profil dans le cache")

        # ===== VÉRIFICATION FINALE =====
        if not self.current_profile:
            print(f"[DEBUG] ❌ AUCUN PROFIL TROUVÉ - RESET INTERFACE")
            self._reset_interface()
            return

        print(f"[DEBUG] ✅ PROFIL FINAL CHARGÉ")
        print(
            f"[DEBUG] Profil source: {'DATABASE' if profile_loaded and hasattr(self.conductor, 'database') and hasattr(self.conductor.database, 'get_platform') else 'AUTRE'}")

        # Charger la configuration d'extraction
        extraction_config = self.current_profile.get('extraction_config', {})
        response_config = extraction_config.get('response_area', {})

        print(f"[DEBUG] === CHARGEMENT CONFIG EXTRACTION ===")
        print(f"[DEBUG] extraction_config existe: {bool(extraction_config)}")
        print(f"[DEBUG] response_area existe: {bool(response_config)}")

        if response_config:
            print(f"[DEBUG] Response config contenu: {json.dumps(response_config, indent=2)}")

        # Méthode d'extraction
        method = response_config.get('method', 'html')
        print(f"[DEBUG] Méthode d'extraction: {method}")
        if method == 'html':
            self.extraction_method_combo.setCurrentIndex(0)
        else:
            self.extraction_method_combo.setCurrentIndex(1)  # clipboard

        # Temps d'attente
        wait_time = response_config.get('wait_time', 3.0)
        print(f"[DEBUG] Temps d'attente: {wait_time}")
        self.wait_extraction_spin.setValue(wait_time)

        # ✅ CHARGER LE PROMPT SAUVEGARDÉ
        saved_prompt_text = response_config.get('prompt_text', 'Bonjour, pouvez-vous me répondre ?')
        print(f"[DEBUG] ===== CHARGEMENT PROMPT =====")
        print(f"[DEBUG] Prompt sauvegardé trouvé: '{saved_prompt_text}'")
        print(f"[DEBUG] Ancien prompt dans input: '{self.prompt_text_input.text()}'")

        self.prompt_text_input.setText(saved_prompt_text)
        print(f"[DEBUG] Nouveau prompt dans input: '{self.prompt_text_input.text()}'")

        # Vérifier si la configuration existe
        if response_config:
            print(f"[DEBUG] Configuration trouvée - mise à jour interface")
            self.capture_status.setText("✅ Configuration sauvegardée")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            if response_config.get('method') == 'html':
                self.html_extract_button.setEnabled(True)

            sample_text = response_config.get('sample_text', '')
            if sample_text:
                self.extracted_text_preview.setPlainText(f"[Aperçu sauvegardé] {sample_text}")
                self.validation_status.setText("✅ Configuration HTML trouvée")
                self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            # Test automatique de la configuration chargée
            QtCore.QTimer.singleShot(100, self._test_loaded_configuration)
        else:
            print(f"[DEBUG] Pas de configuration - reset interface")
            self.capture_status.setText("⚠️ Aucune configuration")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
            self._reset_interface()

    def _test_loaded_configuration(self):
        """Test rapide de la configuration chargée"""
        print("[DEBUG] ===== _test_loaded_configuration =====")
        try:
            extraction_config = self.current_profile.get('extraction_config', {})
            response_config = extraction_config.get('response_area', {})
            complete_html = response_config.get('complete_html', '')

            print(f"[DEBUG] Test config chargée - HTML length: {len(complete_html)}")

            if len(complete_html) > 100:
                re_extracted = self.conductor.detector.extract_text_from_html(complete_html)
                print(f"[DEBUG] Re-extraction test: {len(re_extracted) if re_extracted else 0} caractères")

                if re_extracted and len(re_extracted) > 10:
                    self.validation_status.setText("✅ Configuration valide (testée)")
                    self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
                    self.extracted_text_preview.setPlainText(f"[Config validée] {re_extracted[:200]}...")
                    print("[DEBUG] ✅ Configuration valide")
                    return

            self.validation_status.setText("⚠️ Configuration douteuse")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_warning_style())
            print("[DEBUG] ⚠️ Configuration douteuse")

        except Exception as e:
            print(f"[DEBUG] ❌ ERREUR _test_loaded_configuration: {str(e)}")
            self.validation_status.setText("❌ Test de config échoué")
            self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

    def _reset_interface(self):
        """Remet l'interface à zéro"""
        print("[DEBUG] ===== _reset_interface =====")
        self.validation_status.setText("En attente de HTML...")
        self.validation_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.extracted_text_preview.clear()
        self.html_extract_button.setEnabled(False)
        self.html_input.clear()
        # Réinitialiser le prompt à la valeur par défaut
        self.prompt_text_input.setText("Bonjour, pouvez-vous me répondre ?")
        print("[DEBUG] Interface remise à zéro")

    def _on_save_config(self):
        """Enregistre la configuration de la zone de réponse"""
        print("[DEBUG] ===== _on_save_config =====")

        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        try:
            extraction_config = self.current_profile.get('extraction_config', {})
            print(f"[DEBUG] Extraction config existe: {bool(extraction_config)}")

            if not extraction_config.get('response_area'):
                print("[DEBUG] Pas de response_area dans extraction_config")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Configuration manquante",
                    "Aucune configuration d'extraction. Effectuez d'abord l'envoi de prompt et l'extraction HTML."
                )
                return

            # Mettre à jour les paramètres
            response_config = extraction_config['response_area']
            print(f"[DEBUG] Response config avant modification: {response_config}")

            # Méthode
            method_index = self.extraction_method_combo.currentIndex()
            if method_index == 0:
                response_config['method'] = 'html'
            else:
                response_config['method'] = 'clipboard'

            # Temps d'attente
            response_config['wait_time'] = self.wait_extraction_spin.value()

            # ✅ SAUVEGARDER LE PROMPT ACTUEL
            current_prompt_text = self.prompt_text_input.text().strip()
            if not current_prompt_text:
                current_prompt_text = "Bonjour, pouvez-vous me répondre ?"
            response_config['prompt_text'] = current_prompt_text

            print(f"[DEBUG] Response config après modification:")
            print(f"[DEBUG] - method: {response_config['method']}")
            print(f"[DEBUG] - wait_time: {response_config['wait_time']}")
            print(f"[DEBUG] - prompt_text: '{response_config['prompt_text']}'")

            # Sauvegarder
            success = self._save_profile()
            print(f"[DEBUG] Résultat sauvegarde: {success}")

            if success:
                self.response_area_configured.emit(self.current_platform, response_config)
                QtWidgets.QMessageBox.information(
                    self,
                    "Configuration enregistrée",
                    f"Configuration d'extraction pour {self.current_platform} sauvegardée avec succès.\n\n"
                    f"Prompt: '{current_prompt_text}'"
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur d'enregistrement",
                    "Impossible d'enregistrer la configuration."
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement: {str(e)}")
            print(f"[DEBUG] ERREUR _on_save_config: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'enregistrement: {str(e)}"
            )

    def _save_profile(self):
        """Sauvegarde le profil dans le système"""
        print(f"[DEBUG] ===== _save_profile =====")
        print(f"[DEBUG] Current platform: {self.current_platform}")
        print(f"[DEBUG] Current profile exists: {self.current_profile is not None}")

        if not self.current_platform or not self.current_profile:
            print("[DEBUG] Pas de plateforme ou profil - ABANDON")
            return False

        try:
            print(f"[DEBUG] Tentative de sauvegarde pour: {self.current_platform}")
            print(f"[DEBUG] Profil complet à sauvegarder:")
            print(f"{json.dumps(self.current_profile, indent=2)}")

            # Méthode 1: Base de données (PRIORITAIRE)
            print(f"[DEBUG] === MÉTHODE 1: Base de données ===")
            if hasattr(self.conductor, 'database') and self.conductor.database:
                print(f"[DEBUG] Database trouvée: {type(self.conductor.database)}")
                print(f"[DEBUG] Database a save_platform: {hasattr(self.conductor.database, 'save_platform')}")

                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        print(f"[DEBUG] Appel database.save_platform('{self.current_platform}', profile)")
                        success = self.conductor.database.save_platform(self.current_platform, self.current_profile)
                        print(f"[DEBUG] Résultat database.save_platform: {success}")
                        if success:
                            print("[DEBUG] ✅ SAUVEGARDE DATABASE RÉUSSIE")
                            return True
                    except Exception as e:
                        print(f"[DEBUG] ❌ ERREUR database.save_platform: {str(e)}")
                        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                else:
                    print("[DEBUG] ❌ Database n'a pas save_platform")
            else:
                print("[DEBUG] ❌ Pas de database")

            # Méthode 2: ConfigProvider
            print(f"[DEBUG] === MÉTHODE 2: ConfigProvider ===")
            print(f"[DEBUG] config_provider a save_profile: {hasattr(self.config_provider, 'save_profile')}")

            if hasattr(self.config_provider, 'save_profile'):
                try:
                    print(f"[DEBUG] Appel config_provider.save_profile('{self.current_platform}', profile)")
                    success = self.config_provider.save_profile(self.current_platform, self.current_profile)
                    print(f"[DEBUG] Résultat config_provider.save_profile: {success}")
                    if success:
                        print("[DEBUG] ✅ SAUVEGARDE CONFIGPROVIDER RÉUSSIE")
                        return True
                except Exception as e:
                    print(f"[DEBUG] ❌ ERREUR config_provider.save_profile: {str(e)}")
                    print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                print("[DEBUG] ❌ ConfigProvider n'a pas save_profile")

            # Méthode 3: Sauvegarde directe fichier (DERNIER RECOURS)
            print(f"[DEBUG] === MÉTHODE 3: Fichier direct ===")
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")

            print(f"[DEBUG] Écriture fichier: {file_path}")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            # Mettre à jour le cache
            self.profiles[self.current_platform] = self.current_profile
            print(f"[DEBUG] ✅ SAUVEGARDE FICHIER RÉUSSIE: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du profil: {str(e)}")
            print(f"[DEBUG] ❌ ERREUR GLOBALE _save_profile: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return False