#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/platform_config_widget.py
"""

import os
import json
import traceback
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from utils.exceptions import ConfigurationError
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.tabs.browser_config_widget import BrowserConfigWidget
from ui.widgets.tabs.prompt_field_widget import PromptFieldWidget
from ui.widgets.tabs.response_area_widget import ResponseAreaWidget


class PlatformConfigWidget(QtWidgets.QWidget):
    """Widget de configuration des plateformes d'IA"""

    # Signaux
    platform_added = pyqtSignal(str)
    platform_updated = pyqtSignal(str)
    platform_deleted = pyqtSignal(str)
    platform_tested = pyqtSignal(str, bool, str)

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration des plateformes
        """
        super().__init__(parent)

        # Activer l'attribut pour capturer les événements de souris
        self.setMouseTracking(True)

        # Debug
        print("PlatformConfigWidget: Initialisation...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.current_platform = None
        self.profiles = {}
        self.is_new_platform = False  # Flag pour indiquer si on est en mode création

        try:
            self._init_ui()
            self._ensure_default_platforms()
            self._load_profiles_from_files()  # Ajout de chargement robuste des fichiers d'abord
            self._load_platforms()

            # Force tous les widgets à être activés après l'initialisation
            self._force_enable_all_widgets()

            print("PlatformConfigWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de PlatformConfigWidget: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    # Capture explicite des événements de souris pour garantir que les clics sont traités
    def mousePressEvent(self, event):
        """Traite les événements de clic de souris"""
        print(f"DEBUG: Clic dans PlatformConfigWidget à {event.pos()}")
        super().mousePressEvent(event)

    def _force_enable_all_widgets(self):
        """Force l'activation de tous les widgets interactifs"""
        # Liste des widgets principaux à activer
        main_widgets = [
            self.platform_list,
            self.details_group,
            self.tabs,
            self.name_edit,
            self.tokens_spin,
            self.prompts_spin,
            self.cooldown_spin,
            self.reset_time_edit,
            self.error_patterns_edit,
            self.save_button,
            self.test_button,
            self.cancel_button,
            self.add_button,
            self.delete_button
        ]

        # S'assurer que chaque widget est activé
        for widget in main_widgets:
            if hasattr(widget, 'setEnabled'):
                widget.setEnabled(True)
                print(f"DEBUG: Widget {widget.__class__.__name__} activé")

        # Activer aussi tous les onglets
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                tab.setEnabled(True)
                print(f"DEBUG: Onglet {i} activé")

                # Activer tous les widgets dans cet onglet
                for child in tab.findChildren(QtWidgets.QWidget):
                    child.setEnabled(True)

        # S'assurer que les widgets clés sont au premier plan
        self.raise_()
        self.tabs.raise_()
        self.platform_list.raise_()

    def _init_ui(self):
        """Configure l'interface utilisateur - version améliorée avec panneau d'aide"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(PlatformConfigStyle.SPACING)
        main_layout.setContentsMargins(PlatformConfigStyle.MARGIN, PlatformConfigStyle.MARGIN,
                                       PlatformConfigStyle.MARGIN, PlatformConfigStyle.MARGIN)

        # Titre
        title_label = QtWidgets.QLabel("Configuration des Plateformes d'IA")
        title_label.setStyleSheet(PlatformConfigStyle.get_title_style())
        main_layout.addWidget(title_label)

        # Créer le panneau d'aide contextuel (invisible par défaut)
        self.workflow_help = QtWidgets.QWidget()
        workflow_layout = QtWidgets.QVBoxLayout(self.workflow_help)
        workflow_layout.setContentsMargins(10, 10, 10, 10)

        help_title = QtWidgets.QLabel("<b>Guide de configuration</b>")
        help_title.setStyleSheet("font-size: 14px; color: #074E68;")

        help_steps = QtWidgets.QLabel(
            "Pour configurer correctement une plateforme d'IA, suivez cet ordre:<br>"
            "1. Complétez les informations générales (nom, limites)<br>"
            "2. Configurez le navigateur dans l'onglet correspondant<br>"
            "3. Configurez le champ de prompt<br>"
            "4. Configurez la zone de réponse<br>"
            "<br>Terminez en testant la connexion."
        )
        help_steps.setStyleSheet("padding: 12px; background-color: #E8F4F8; border-radius: 4px;")
        help_steps.setWordWrap(True)

        dismiss_button = QtWidgets.QPushButton("Masquer ce guide")
        dismiss_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        dismiss_button.clicked.connect(lambda: self.workflow_help.setVisible(False))

        workflow_layout.addWidget(help_title)
        workflow_layout.addWidget(help_steps)
        workflow_layout.addWidget(dismiss_button)

        # Ajouter au layout principal mais cacher par défaut
        main_layout.addWidget(self.workflow_help)
        self.workflow_help.setVisible(False)

        # Créer les onglets principaux
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(PlatformConfigStyle.get_tabs_style())
        main_layout.addWidget(self.tabs)

        # === DISPOSITION PRINCIPALE ===
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)

        # Panneau gauche (liste des plateformes)
        left_panel = QtWidgets.QGroupBox("Plateformes disponibles")
        left_panel.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        left_layout = QtWidgets.QVBoxLayout(left_panel)

        # Liste des plateformes
        self.platform_list = QtWidgets.QListWidget()
        self.platform_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.platform_list.currentItemChanged.connect(self._on_platform_selected)
        self.platform_list.setMinimumWidth(200)
        self.platform_list.setStyleSheet(PlatformConfigStyle.get_list_style())
        left_layout.addWidget(self.platform_list)

        # Boutons pour la liste
        buttons_layout = QtWidgets.QHBoxLayout()

        self.add_button = QtWidgets.QPushButton("Ajouter")
        self.add_button.clicked.connect(self._on_add_platform)
        self.add_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        self.delete_button = QtWidgets.QPushButton("Supprimer")
        self.delete_button.clicked.connect(self._on_delete_platform)
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.delete_button)
        left_layout.addLayout(buttons_layout)

        # Panneau droit (détails)
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)

        # Groupbox des détails
        self.details_group = QtWidgets.QGroupBox("Détails de la plateforme")
        self.details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_layout = QtWidgets.QFormLayout(self.details_group)

        # Nom
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Nom de la plateforme (ex. ChatGPT, Claude)")
        self.name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Nom:", self.name_edit)

        # Limites
        self.tokens_spin = QtWidgets.QSpinBox()
        self.tokens_spin.setRange(1, 100000)
        self.tokens_spin.setValue(8000)
        self.tokens_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Tokens par prompt:", self.tokens_spin)

        self.prompts_spin = QtWidgets.QSpinBox()
        self.prompts_spin.setRange(1, 1000)
        self.prompts_spin.setValue(30)
        self.prompts_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Prompts par jour:", self.prompts_spin)

        self.cooldown_spin = QtWidgets.QSpinBox()
        self.cooldown_spin.setRange(0, 3600)
        self.cooldown_spin.setValue(120)
        self.cooldown_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Période de refroidissement (s):", self.cooldown_spin)

        self.reset_time_edit = QtWidgets.QTimeEdit()
        self.reset_time_edit.setDisplayFormat("HH:mm:ss")
        self.reset_time_edit.setTime(QtCore.QTime(0, 0, 0))
        self.reset_time_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Heure de réinitialisation:", self.reset_time_edit)

        # Patterns d'erreur
        self.error_patterns_edit = QtWidgets.QTextEdit()
        self.error_patterns_edit.setPlaceholderText("Un pattern par ligne (ex: 'rate limited')")
        self.error_patterns_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_layout.addRow("Patterns d'erreur:", self.error_patterns_edit)

        right_layout.addWidget(self.details_group)

        # Boutons d'action
        action_layout = QtWidgets.QHBoxLayout()

        self.save_button = QtWidgets.QPushButton("Enregistrer")
        self.save_button.clicked.connect(self._on_save_platform)
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        self.test_button = QtWidgets.QPushButton("Tester la connexion")
        self.test_button.clicked.connect(self._on_test_platform)
        self.test_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        self.cancel_button = QtWidgets.QPushButton("Annuler")
        self.cancel_button.clicked.connect(self._on_cancel_edit)
        self.cancel_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        action_layout.addWidget(self.save_button)
        action_layout.addWidget(self.test_button)
        action_layout.addWidget(self.cancel_button)

        right_layout.addLayout(action_layout)

        # Compléter le layout principal
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 2)

        # === CRÉATION DES ONGLETS ===

        # Onglet 1: Configuration générale
        general_tab = QtWidgets.QWidget()
        general_tab.setLayout(QtWidgets.QVBoxLayout())
        general_tab.layout().addWidget(content_widget)
        self.tabs.addTab(general_tab, "Configuration Générale")

        # Onglet 2: Navigateur
        self.browser_widget = BrowserConfigWidget(self.config_provider, self.conductor)
        self.browser_widget.browser_saved.connect(self._on_browser_config_saved)
        self.browser_widget.browser_used.connect(self._on_browser_used)
        self.browser_widget.elements_detected.connect(self._on_elements_detected)
        self.tabs.addTab(self.browser_widget, "Gestion des navigateurs")

        # Onglet 3: Champ de prompt
        self.prompt_field_widget = PromptFieldWidget(self.config_provider, self.conductor)
        self.prompt_field_widget.prompt_field_configured.connect(self._on_prompt_field_configured)
        self.prompt_field_widget.prompt_field_detected.connect(self._on_prompt_field_detected)
        self.tabs.addTab(self.prompt_field_widget, "Champ de prompt")

        # Onglet 4: Zone de réponse
        self.response_area_widget = ResponseAreaWidget(self.config_provider, self.conductor)
        self.response_area_widget.response_area_configured.connect(self._on_response_area_configured)
        self.response_area_widget.response_area_detected.connect(self._on_response_area_detected)
        self.response_area_widget.response_received.connect(self._on_response_received)
        self.tabs.addTab(self.response_area_widget, "Zone de réponse")

        # Pour la compatibilité avec le code existant
        self.main_tabs = self.tabs
        self.interface_tabs = self.tabs

        # Garantir que tous les widgets sont activés - IMPORTANT
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.setEnabled(True)

        # Lever au premier plan les widgets interactifs clés
        self.tabs.raise_()
        self.platform_list.raise_()
        self.details_group.raise_()

    def _on_prompt_field_configured(self, platform_name, config):
        """Gère l'événement de configuration du champ de prompt"""
        print(f"DEBUG: Configuration du champ de prompt pour '{platform_name}' mise à jour")
        self._update_tab_status()

    def _on_prompt_field_detected(self, platform_name, position):
        """Gère l'événement de détection du champ de prompt"""
        print(f"DEBUG: Position du champ de prompt détectée pour '{platform_name}'")
        self._update_tab_status()

    def _on_submit_button_detected(self, platform_name, position):
        """Gère l'événement de détection du bouton de soumission"""
        print(f"DEBUG: Position du bouton de soumission détectée pour '{platform_name}'")
        self._update_tab_status()

    def _on_response_area_configured(self, platform_name, config):
        """Gère l'événement de configuration de la zone de réponse"""
        print(f"DEBUG: Configuration de la zone de réponse pour '{platform_name}' mise à jour")
        self._update_tab_status()

    def _on_response_area_detected(self, platform_name, position):
        """Gère l'événement de détection de la zone de réponse"""
        print(f"DEBUG: Position de la zone de réponse détectée pour '{platform_name}'")
        self._update_tab_status()

    def _on_response_received(self, platform_name, response_text):
        """Gère l'événement de réception d'une réponse"""
        print(f"DEBUG: Réponse reçue de '{platform_name}': {len(response_text)} caractères")
        # Implémenter ici la logique de traitement de la réponse si nécessaire

    def _update_tab_status(self):
        """Met à jour les indicateurs visuels d'état des onglets"""
        if not self.current_platform:
            return

        profile = self.profiles.get(self.current_platform, {})
        interface_positions = profile.get('interface_positions', {})

        # Définir les icônes pour les états configurés/non configurés
        if not hasattr(self, 'configured_icon') or not self.configured_icon:
            # Créer des icônes d'état (à faire une seule fois)
            self.configured_icon = QtGui.QIcon()
            self.unconfigured_icon = QtGui.QIcon()
            # Note: Dans une implémentation réelle, vous chargeriez des icônes

        # Vérifier l'état de configuration de chaque onglet
        config_states = {
            0: True,  # Config générale toujours configurée
            1: 'browser' in profile and profile['browser'].get('url'),  # Navigateur configuré?
            2: 'prompt_field' in interface_positions,  # Champ prompt configuré?
            3: 'response_area' in interface_positions  # Zone réponse configurée?
        }

        # Mettre à jour les titres des onglets en fonction de l'état
        base_titles = ["Configuration Générale", "Gestion des navigateurs",
                       "Champ de prompt", "Zone de réponse"]

        for i, title in enumerate(base_titles):
            configured = config_states.get(i, False)

            # Ajouter une indication visuelle pour les onglets non configurés
            if self.is_new_platform and not configured and i > 0:
                # Ajouter un astérisque pour indiquer les onglets à configurer
                self.tabs.setTabText(i, f"{title} *")
            else:
                self.tabs.setTabText(i, title)

    def _on_browser_config_saved(self, name, config):
        """Gère l'événement de sauvegarde d'une configuration de navigateur"""
        print(f"DEBUG: Configuration de navigateur '{name}' sauvegardée")
        self._update_tab_status()

    def _on_browser_used(self, platform_name, browser_name):
        """Gère l'événement d'utilisation d'un navigateur pour une plateforme"""
        print(f"DEBUG: Navigateur '{browser_name}' utilisé pour la plateforme '{platform_name}'")

        # Mise à jour de l'interface si nécessaire
        self._load_profiles_from_files()  # Recharger les profils

        # Si la plateforme courante est celle qui a été modifiée, actualiser l'affichage
        if self.current_platform == platform_name:
            self._on_platform_selected(self.platform_list.currentItem(), None)
            self._update_tab_status()

    def _on_elements_detected(self, platform_name, positions):
        """Gère l'événement de détection des éléments d'interface"""
        print(f"DEBUG: Éléments d'interface détectés pour '{platform_name}'")

        # Mise à jour de l'interface si nécessaire
        self._load_profiles_from_files()  # Recharger les profils

        # Si la plateforme courante est celle qui a été modifiée, actualiser l'affichage
        if self.current_platform == platform_name:
            self._on_platform_selected(self.platform_list.currentItem(), None)
            self._update_tab_status()

    def _load_profiles_from_files(self):
        """Charge directement les profils depuis les fichiers pour garantir un chargement robuste"""
        try:
            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            print(f"DEBUG: Chargement direct des profils depuis {profiles_dir}")

            if not os.path.exists(profiles_dir):
                os.makedirs(profiles_dir, exist_ok=True)
                print(f"DEBUG: Répertoire des profils créé: {profiles_dir}")

            file_count = 0
            for filename in os.listdir(profiles_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(profiles_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                            name = profile.get('name', filename.replace('.json', ''))
                            self.profiles[name] = profile
                            file_count += 1
                            print(f"DEBUG: Profil chargé depuis fichier: {name}")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement du fichier {filename}: {str(e)}")
                        print(f"DEBUG: Erreur fichier {filename}: {str(e)}")

            print(f"DEBUG: {file_count} profils chargés depuis les fichiers")

            # Mettre à jour le widget navigateur avec les profils
            if hasattr(self, 'browser_widget'):
                self.browser_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de champ de prompt avec les profils
            if hasattr(self, 'prompt_field_widget'):
                self.prompt_field_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de la zone de réponse avec les profils
            if hasattr(self, 'response_area_widget'):
                self.response_area_widget.set_profiles(self.profiles)

        except Exception as e:
            logger.error(f"Erreur lors du chargement direct des profils: {str(e)}")
            print(f"DEBUG: Erreur chargement direct: {str(e)}")

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

    def _ensure_default_platforms(self):
        """
        S'assure que les plateformes par défaut existent
        Ne les recrée pas si elles ont été supprimées délibérément
        """
        # Vérifier si c'est la première exécution
        first_run_marker = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".platforms_initialized")

        print(f"DEBUG: Vérification du marqueur d'initialisation: {first_run_marker}")
        print(f"DEBUG: Le marqueur existe: {os.path.exists(first_run_marker)}")

        if os.path.exists(first_run_marker):
            # Ce n'est pas la première exécution, ne rien faire
            print("DEBUG: Ce n'est pas la première exécution, pas de création des plateformes par défaut")
            return

        print("DEBUG: Création des plateformes par défaut (première exécution)")
        logger.info("Création des plateformes par défaut (première exécution)")

        # Définir les plateformes par défaut
        default_platforms = {
            "ChatGPT": {
                "name": "ChatGPT",
                "interface": {
                    "prompt_field": {
                        "type": "textarea",
                        "placeholder": "Envoyez un message à ChatGPT...",
                        "detection": {
                            "method": "findContour",
                            "color_range": {
                                "lower": [240, 240, 240],
                                "upper": [255, 255, 255]
                            }
                        }
                    },
                    "response_area": {
                        "type": "div",
                        "detection": {
                            "method": "findContour",
                            "color_range": {
                                "lower": [245, 245, 245],
                                "upper": [255, 255, 255]
                            }
                        }
                    }
                },
                "browser": {
                    "type": "Chrome",
                    "path": "",
                    "url": "https://chat.openai.com",
                },
                "limits": {
                    "tokens_per_prompt": 8000,
                    "prompts_per_day": 30,
                    "reset_time": "00:00:00",
                    "cooldown_period": 120
                },
                "error_detection": {
                    "patterns": [
                        "rate limited",
                        "please try again later",
                        "too many requests"
                    ]
                }
            },
            "Claude": {
                "name": "Claude",
                "interface": {
                    "prompt_field": {
                        "type": "textarea",
                        "placeholder": "Message Claude...",
                        "detection": {
                            "method": "findContour",
                            "color_range": {
                                "lower": [240, 240, 240],
                                "upper": [255, 255, 255]
                            }
                        }
                    },
                    "response_area": {
                        "type": "div",
                        "detection": {
                            "method": "findContour",
                            "color_range": {
                                "lower": [245, 245, 245],
                                "upper": [255, 255, 255]
                            }
                        }
                    }
                },
                "browser": {
                    "type": "Chrome",
                    "path": "",
                    "url": "https://claude.ai",
                },
                "limits": {
                    "tokens_per_prompt": 10000,
                    "prompts_per_day": 25,
                    "reset_time": "00:00:00",
                    "cooldown_period": 180
                },
                "error_detection": {
                    "patterns": [
                        "rate limited",
                        "please try again later",
                        "too many requests"
                    ]
                }
            }
        }

        # Créer chaque plateforme par défaut si elle n'existe pas déjà
        try:
            for name, profile in default_platforms.items():
                print(f"DEBUG: Traitement de la plateforme par défaut: {name}")

                # Vérifier si cette plateforme a été supprimée délibérément
                platform_was_deleted = False
                if hasattr(self.conductor, 'database') and self.conductor.database:
                    if hasattr(self.conductor.database, 'was_platform_deleted'):
                        try:
                            platform_was_deleted = self.conductor.database.was_platform_deleted(name)
                            print(f"DEBUG: Plateforme {name} précédemment supprimée: {platform_was_deleted}")
                        except Exception as e:
                            logger.error(f"Erreur lors de la vérification de suppression: {str(e)}")
                            print(f"DEBUG: Erreur vérification suppression: {str(e)}")

                if platform_was_deleted:
                    logger.info(f"Plateforme {name} précédemment supprimée, ne pas recréer")
                    print(f"DEBUG: Plateforme {name} précédemment supprimée, ne pas recréer")
                    continue

                # Vérifier si la plateforme existe déjà
                platform_exists = False

                # Méthode 1: Vérifier dans la base de données
                if hasattr(self.conductor, 'database') and self.conductor.database:
                    if hasattr(self.conductor.database, 'platform_exists'):
                        try:
                            platform_exists = self.conductor.database.platform_exists(name)
                            print(f"DEBUG: Existence dans la base de données pour {name}: {platform_exists}")
                        except Exception as e:
                            logger.error(f"Erreur lors de la vérification d'existence: {str(e)}")
                            print(f"DEBUG: Erreur vérification existence DB: {str(e)}")

                # Méthode 2: Vérifier dans les fichiers (plus fiable)
                if not platform_exists:
                    profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                    platform_file = os.path.join(profiles_dir, f"{name}.json")
                    platform_exists = os.path.exists(platform_file)
                    print(f"DEBUG: Existence dans les fichiers pour {name}: {platform_exists} ({platform_file})")

                # Créer la plateforme si elle n'existe pas
                if not platform_exists:
                    success = self._create_platform(name, profile)
                    print(f"DEBUG: Création plateforme {name}: {'Succès' if success else 'Échec'}")
                    if success:
                        logger.info(f"Plateforme par défaut créée: {name}")
                else:
                    print(f"DEBUG: Plateforme {name} existe déjà, pas de création")

            # Créer le marqueur pour indiquer que l'initialisation a été effectuée
            try:
                with open(first_run_marker, 'w') as f:
                    f.write(f"Plateformes initialisées le {datetime.now().isoformat()}")
                print(f"DEBUG: Marqueur d'initialisation créé: {first_run_marker}")
            except Exception as e:
                logger.error(f"Erreur lors de la création du marqueur: {str(e)}")
                print(f"DEBUG: Erreur création marqueur: {str(e)}")

        except Exception as e:
            logger.error(f"Erreur lors de la création des plateformes par défaut: {str(e)}")
            print(f"DEBUG: Erreur globale création plateformes: {str(e)}")
            print(traceback.format_exc())

    def _create_platform(self, name, profile):
        """
        Crée une nouvelle plateforme

        Args:
            name (str): Nom de la plateforme
            profile (dict): Configuration de la plateforme

        Returns:
            bool: True si la création est réussie
        """
        try:
            print(f"DEBUG: Tentative de création de la plateforme {name}")

            # Essayer d'abord la base de données
            db_success = False
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        db_success = self.conductor.database.save_platform(name, profile)
                        print(f"DEBUG: Sauvegarde dans la DB: {db_success}")
                    except Exception as e:
                        print(f"DEBUG: Erreur sauvegarde DB: {str(e)}")

                    if db_success:
                        return True

            # Fallback sur le ConfigProvider
            config_success = False
            if hasattr(self.config_provider, 'save_profile'):
                try:
                    config_success = self.config_provider.save_profile(name, profile)
                    print(f"DEBUG: Sauvegarde via ConfigProvider: {config_success}")
                except Exception as e:
                    print(f"DEBUG: Erreur sauvegarde ConfigProvider: {str(e)}")

                if config_success:
                    return True

            # Fallback direct sur les fichiers (méthode la plus robuste)
            try:
                profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                os.makedirs(profiles_dir, exist_ok=True)

                file_path = os.path.join(profiles_dir, f"{name}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False)

                print(f"DEBUG: Sauvegarde directe fichier: {file_path}")

                # Mettre à jour le cache interne
                self.profiles[name] = profile

                return True
            except Exception as e:
                print(f"DEBUG: Erreur sauvegarde fichier: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la création de la plateforme {name}: {str(e)}")
            print(f"DEBUG: Erreur globale création plateforme: {str(e)}")
            return False

    def _load_platforms(self):
        """Charge la liste des plateformes depuis toutes les sources disponibles"""
        print("DEBUG: Chargement des plateformes...")

        try:
            # Essayer plusieurs méthodes pour charger les plateformes
            loaded = False

            # Méthode 1: Charger depuis la base de données
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_all_platforms'):
                    try:
                        # Utiliser la base de données
                        platforms = self.conductor.database.get_all_platforms()
                        if platforms:
                            self.profiles.update(platforms)
                            loaded = True
                            print(f"DEBUG: Plateformes chargées depuis la base de données: {len(platforms)}")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement depuis la base de données: {str(e)}")
                        print(f"DEBUG: Erreur chargement DB: {str(e)}")

            # Méthode 2: Utiliser le provider de configuration
            if not loaded and hasattr(self.config_provider, 'get_profiles'):
                try:
                    platforms = self.config_provider.get_profiles(reload=True)
                    if platforms:
                        self.profiles.update(platforms)
                        loaded = True
                        print(f"DEBUG: Plateformes chargées depuis ConfigProvider: {len(platforms)}")
                except Exception as e:
                    logger.error(f"Erreur lors du chargement depuis ConfigProvider: {str(e)}")
                    print(f"DEBUG: Erreur chargement ConfigProvider: {str(e)}")

            # Méthode 3: Les fichiers ont déjà été chargés dans _load_profiles_from_files
            # Assurons-nous que self.profiles n'est pas vide
            if not self.profiles:
                logger.warning("Aucune source de données pour les plateformes d'IA")
                print("DEBUG: Aucune plateforme trouvée dans aucune source!")
            else:
                print(f"DEBUG: Plateformes disponibles: {list(self.profiles.keys())}")

            # Mettre à jour la liste
            self.platform_list.clear()

            for name, profile in self.profiles.items():
                item = QtWidgets.QListWidgetItem(name)
                item.setData(Qt.UserRole, name)
                self.platform_list.addItem(item)
                print(f"DEBUG: Plateforme ajoutée à la liste: {name}")

            # Mettre à jour le widget navigateur avec les profils chargés
            if hasattr(self, 'browser_widget'):
                self.browser_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de champ de prompt avec les profils
            if hasattr(self, 'prompt_field_widget'):
                self.prompt_field_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de la zone de réponse avec les profils
            if hasattr(self, 'response_area_widget'):
                self.response_area_widget.set_profiles(self.profiles)

            # S'assurer que tous les widgets restent activés après le chargement
            self._force_enable_all_widgets()

            # Initialiser avec aucune plateforme sélectionnée mais widgets activés
            self.current_platform = None

        except Exception as e:
            logger.error(f"Erreur lors du chargement des plateformes: {str(e)}")
            print(f"DEBUG: Erreur globale chargement: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de chargement",
                f"Impossible de charger les plateformes: {str(e)}"
            )

    def _set_details_enabled(self, enabled):
        """Active ou désactive le panneau de détails - MODIFIÉ pour garantir l'activation"""
        # Toujours forcer l'activation des widgets lors de l'initialisation
        if not enabled:
            print("ATTENTION: Tentative de désactiver des widgets - ignorée pour garantir l'interactivité")
            enabled = True  # Forcer l'activation

        # Activer les widgets spécifiques
        self.details_group.setEnabled(enabled)
        self.tabs.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.test_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)

        # S'assurer que les widgets sont au premier plan
        self.tabs.raise_()
        self.platform_list.raise_()

        print(f"DEBUG: Widgets activés (_set_details_enabled({enabled}))")

    def _on_platform_selected(self, current, previous):
        """Gère la sélection d'une plateforme dans la liste"""
        # Masquer le guide d'aide contextuel
        self.workflow_help.setVisible(False)
        self.is_new_platform = False

        if not current:
            self._set_details_enabled(True)  # Toujours true pour garantir l'interactivité
            self.delete_button.setEnabled(False)
            self.current_platform = None
            return

        try:
            # Récupérer le nom de la plateforme
            platform_name = current.data(Qt.UserRole)
            self.current_platform = platform_name
            print(f"DEBUG: Plateforme sélectionnée: {platform_name}")

            # Charger le profil
            profile = self.profiles.get(platform_name, {})

            if not profile:
                print(f"DEBUG: Profil vide pour {platform_name}!")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Profil incomplet",
                    f"Le profil de la plateforme {platform_name} semble incomplet ou corrompu."
                )
                return

            # Mettre à jour les champs
            self.name_edit.setText(platform_name)

            # Limites
            limits = profile.get('limits', {})
            self.tokens_spin.setValue(limits.get('tokens_per_prompt', 8000))
            self.prompts_spin.setValue(limits.get('prompts_per_day', 30))
            self.cooldown_spin.setValue(limits.get('cooldown_period', 120))

            # Heure de réinitialisation
            reset_time = limits.get('reset_time', '00:00:00')
            try:
                time_parts = reset_time.split(':')
                qtime = QtCore.QTime(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
                self.reset_time_edit.setTime(qtime)
            except:
                self.reset_time_edit.setTime(QtCore.QTime(0, 0, 0))

            # Patterns d'erreur
            error_patterns = profile.get('error_detection', {}).get('patterns', [])
            self.error_patterns_edit.setPlainText('\n'.join(error_patterns))

            # Sélectionner cette plateforme dans le widget navigateur
            if hasattr(self, 'browser_widget'):
                self.browser_widget.select_platform(platform_name)

            # Sélectionner cette plateforme dans le widget de champ de prompt
            if hasattr(self, 'prompt_field_widget'):
                self.prompt_field_widget.select_platform(platform_name)

            # Sélectionner cette plateforme dans le widget de zone de réponse
            if hasattr(self, 'response_area_widget'):
                self.response_area_widget.select_platform(platform_name)

            # Mise à jour des indicateurs d'état des onglets
            self._update_tab_status()

            # Activer le panneau et le bouton de suppression
            self._set_details_enabled(True)
            self.delete_button.setEnabled(True)

            # Garantir que tous les widgets sont activés
            self._force_enable_all_widgets()

        except Exception as e:
            logger.error(f"Erreur lors de la sélection de la plateforme: {str(e)}")
            print(f"DEBUG: Erreur sélection plateforme: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de sélection",
                f"Impossible de charger les détails de la plateforme: {str(e)}"
            )

    def _on_add_platform(self):
        """Crée une nouvelle plateforme"""
        # Réinitialiser les champs
        self.name_edit.setText("Custom AI Platform")
        self.tokens_spin.setValue(8000)
        self.prompts_spin.setValue(30)
        self.cooldown_spin.setValue(120)
        self.reset_time_edit.setTime(QtCore.QTime(0, 0, 0))
        self.error_patterns_edit.setPlainText("rate limited\nplease try again later\ntoo many requests")

        # Activer le panneau de détails et désactiver le bouton de suppression
        self._set_details_enabled(True)
        self.delete_button.setEnabled(False)
        self.current_platform = None

        # Activer le mode "nouvelle plateforme" et afficher le guide
        self.is_new_platform = True
        self.workflow_help.setVisible(True)

        # Sélectionner le premier onglet (Informations générales)
        self.tabs.setCurrentIndex(0)

        # Mettre à jour les indicateurs visuels
        self._update_tab_status()

        # S'assurer que les widgets sont toujours activés
        self._force_enable_all_widgets()

    def _on_save_platform(self):
        """Enregistre la plateforme actuelle"""
        # Vérifier le nom
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Nom manquant",
                "Veuillez saisir un nom pour la plateforme."
            )
            return

        # Construire le profil
        profile = {
            "name": name,
            "interface": {
                "prompt_field": {
                    "type": "textarea",
                    "placeholder": "",  # Sera rempli par le PromptFieldWidget
                    "detection": {
                        "method": "findContour",
                        "color_range": {
                            "lower": [240, 240, 240],
                            "upper": [255, 255, 255]
                        }
                    }
                },
                "response_area": {
                    "type": "div",
                    "detection": {
                        "method": "findContour",
                        "color_range": {
                            "lower": [245, 245, 245],
                            "upper": [255, 255, 255]
                        }
                    }
                }
            },
            "browser": {
                "type": "Chrome",  # Valeurs par défaut - seront remplacées par le navigateur choisi
                "path": "",
                "url": "",
            },
            "limits": {
                "tokens_per_prompt": self.tokens_spin.value(),
                "prompts_per_day": self.prompts_spin.value(),
                "reset_time": self.reset_time_edit.time().toString("HH:mm:ss"),
                "cooldown_period": self.cooldown_spin.value()
            },
            "error_detection": {
                "patterns": [p.strip() for p in self.error_patterns_edit.toPlainText().split('\n') if p.strip()]
            }
        }

        # Si des positions d'interface existaient déjà, les conserver
        if self.current_platform and 'interface_positions' in self.profiles.get(self.current_platform, {}):
            profile['interface_positions'] = self.profiles[self.current_platform]['interface_positions']

        # Conserver les informations de navigateur si on met à jour une plateforme existante
        if self.current_platform and 'browser' in self.profiles.get(self.current_platform, {}):
            profile['browser'] = self.profiles[self.current_platform]['browser']

        try:
            print(f"DEBUG: Sauvegarde de la plateforme {name}")

            # Déterminer si c'est une mise à jour ou une création
            is_update = self.current_platform is not None and self.current_platform != name
            was_new = self.is_new_platform

            if is_update:
                print(f"DEBUG: C'est une mise à jour avec changement de nom: {self.current_platform} -> {name}")
            elif self.current_platform:
                print(f"DEBUG: C'est une mise à jour sans changement de nom: {name}")
            else:
                print(f"DEBUG: C'est une création: {name}")

            # Sauvegarder dans la base de données si disponible
            db_success = False
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        # Sauvegarder dans la base de données
                        db_success = self.conductor.database.save_platform(name, profile)
                        print(f"DEBUG: Sauvegarde DB: {db_success}")

                        if is_update and self.current_platform != name:
                            # Si le nom a changé et que c'est une mise à jour, supprimer l'ancien
                            deleted = self.conductor.database.delete_platform(self.current_platform)
                            print(f"DEBUG: Suppression ancien nom dans DB: {deleted}")
                    except Exception as e:
                        print(f"DEBUG: Erreur sauvegarde DB: {str(e)}")

            # Si la sauvegarde dans la base de données a échoué ou n'est pas disponible, utiliser le provider de configuration
            if not db_success:
                print("DEBUG: Sauvegarde DB échouée ou non disponible, utilisation alternatives")

                # Si c'est une mise à jour et que le nom a changé, supprimer l'ancien fichier
                if is_update:
                    profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                    old_file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")
                    if os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                            print(f"DEBUG: Ancien fichier supprimé: {old_file_path}")
                        except Exception as e:
                            print(f"DEBUG: Erreur suppression ancien fichier: {str(e)}")

                # Vérifier que save_profile existe
                if hasattr(self.config_provider, 'save_profile'):
                    try:
                        success = self.config_provider.save_profile(name, profile)
                        print(f"DEBUG: Sauvegarde ConfigProvider: {success}")

                        if not success:
                            raise ConfigurationError("Échec de l'enregistrement du profil")
                    except Exception as e:
                        print(f"DEBUG: Erreur sauvegarde ConfigProvider: {str(e)}")

                        # Sauvegarde manuelle du fichier si la méthode échoue
                        self._save_platform_file(name, profile)
                else:
                    # Sauvegarde manuelle du fichier si la méthode n'existe pas
                    print("DEBUG: ConfigProvider.save_profile n'existe pas, sauvegarde directe fichier")
                    self._save_platform_file(name, profile)

            # Mettre à jour le cache interne
            self.profiles[name] = profile
            print(f"DEBUG: Cache interne mis à jour pour {name}")

            # Supprimer l'ancienne entrée si le nom a changé
            if is_update and self.current_platform != name:
                self.profiles.pop(self.current_platform, None)
                print(f"DEBUG: Ancienne entrée supprimée du cache: {self.current_platform}")

            # Actualiser la liste
            self._load_platforms()

            # Sélectionner le profil enregistré
            for i in range(self.platform_list.count()):
                item = self.platform_list.item(i)
                if item.data(Qt.UserRole) == name:
                    self.platform_list.setCurrentItem(item)
                    print(f"DEBUG: Plateforme {name} sélectionnée dans la liste")
                    break

            # Reset le mode nouvelle plateforme
            self.is_new_platform = False
            self.workflow_help.setVisible(False)

            # Si c'était une nouvelle plateforme, suggérer de configurer le navigateur
            if was_new:
                QtWidgets.QMessageBox.information(
                    self,
                    "Enregistrement réussi",
                    f"La plateforme {name} a été créée. Vous devriez maintenant configurer "
                    f"le navigateur dans l'onglet 'Gestion des navigateurs'."
                )
                # Passer automatiquement à l'onglet navigateur
                self.tabs.setCurrentIndex(1)
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Enregistrement réussi",
                    f"La plateforme {name} a été enregistrée avec succès."
                )

            # Mettre à jour les indicateurs d'état
            self._update_tab_status()

            # Émettre le signal
            if self.current_platform:
                if self.current_platform != name:
                    # Si le nom a changé, c'est une suppression + création
                    self.platform_deleted.emit(self.current_platform)
                    self.platform_added.emit(name)
                    print(f"DEBUG: Signaux émis: suppression de {self.current_platform} + ajout de {name}")
                else:
                    # Sinon c'est une mise à jour
                    self.platform_updated.emit(name)
                    print(f"DEBUG: Signal émis: mise à jour de {name}")
            else:
                self.platform_added.emit(name)
                print(f"DEBUG: Signal émis: ajout de {name}")

            # Mettre à jour le current_platform
            self.current_platform = name

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du profil: {str(e)}")
            print(f"DEBUG: Erreur globale enregistrement: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'enregistrement",
                f"Impossible d'enregistrer le profil: {str(e)}"
            )

    def _on_delete_platform(self):
        """Supprime la plateforme sélectionnée"""
        if not self.current_platform:
            return

        # Sauvegarder le nom de la plateforme avant toute opération
        platform_to_delete = self.current_platform
        print(f"DEBUG: Suppression de la plateforme: {platform_to_delete}")

        # Confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation de suppression",
            f"Êtes-vous sûr de vouloir supprimer la plateforme {platform_to_delete}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            print("DEBUG: Suppression annulée par l'utilisateur")
            return

        try:
            # Supprimer d'abord le profil du dictionnaire en mémoire
            if platform_to_delete in self.profiles:
                self.profiles.pop(platform_to_delete, None)
                print(f"DEBUG: Supprimé du cache interne: {platform_to_delete}")

            # Supprimer de la base de données si disponible
            db_success = False
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'delete_platform'):
                    try:
                        # Marquer comme supprimée dans la base de données
                        db_success = self.conductor.database.delete_platform(platform_to_delete)
                        print(f"DEBUG: Suppression de la DB: {db_success}")
                    except Exception as e:
                        print(f"DEBUG: Erreur suppression DB: {str(e)}")

            # Si la suppression dans la base de données a échoué ou n'est pas disponible, supprimer le fichier
            if not db_success:
                print("DEBUG: Suppression DB échouée, suppression directe fichier")

                # Tenter de supprimer le fichier physique
                profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                file_path = os.path.join(profiles_dir, f"{platform_to_delete}.json")

                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"DEBUG: Fichier supprimé: {file_path}")

                    # Créer un marqueur de suppression pour les fichiers
                    marker_path = os.path.join(profiles_dir, f".{platform_to_delete}.deleted")
                    with open(marker_path, 'w') as f:
                        f.write(f"Plateforme supprimée le {datetime.now().isoformat()}")
                    print(f"DEBUG: Marqueur de suppression créé: {marker_path}")

                except Exception as file_error:
                    logger.warning(f"Impossible de supprimer le fichier {file_path}: {str(file_error)}")
                    print(f"DEBUG: Erreur suppression fichier: {str(file_error)}")
                    # Continuer malgré l'erreur de suppression du fichier

            # IMPORTANT: Forcer l'actualisation du cache dans ConfigProvider
            if hasattr(self.config_provider, 'get_profiles'):
                try:
                    # Forcer le rechargement complet des profils
                    self.config_provider.get_profiles(reload=True)
                    print("DEBUG: Cache du ConfigProvider actualisé")
                except Exception as e:
                    print(f"DEBUG: Erreur actualisation cache ConfigProvider: {str(e)}")

            # Émettre le signal
            self.platform_deleted.emit(platform_to_delete)
            print(f"DEBUG: Signal émis: suppression de {platform_to_delete}")

            # Mettre à jour le widget navigateur
            if hasattr(self, 'browser_widget'):
                self.browser_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de champ de prompt
            if hasattr(self, 'prompt_field_widget'):
                self.prompt_field_widget.set_profiles(self.profiles)

            # Mettre à jour le widget de la zone de réponse
            if hasattr(self, 'response_area_widget'):
                self.response_area_widget.set_profiles(self.profiles)

            # Actualiser la liste
            self._load_platforms()

            # S'assurer que les widgets restent activés
            self._force_enable_all_widgets()

            QtWidgets.QMessageBox.information(
                self,
                "Suppression réussie",
                f"La plateforme {platform_to_delete} a été supprimée."
            )

            # Réinitialiser les indicateurs
            self.current_platform = None
            self.is_new_platform = False
            self.workflow_help.setVisible(False)

        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {str(e)}")
            print(f"DEBUG: Erreur globale suppression: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de suppression",
                f"Impossible de supprimer la plateforme: {str(e)}"
            )

    def _on_test_platform(self):
        """Teste la connexion avec la plateforme"""
        if not self.current_platform:
            return

        try:
            print(f"DEBUG: Test de connexion pour {self.current_platform}")

            # Vérifier si la plateforme est disponible
            available_platforms = []
            if hasattr(self.conductor, 'get_available_platforms'):
                try:
                    available_platforms = self.conductor.get_available_platforms()
                    print(f"DEBUG: Plateformes disponibles: {available_platforms}")
                except Exception as e:
                    print(f"DEBUG: Erreur récupération plateformes: {str(e)}")
            else:
                print("DEBUG: Méthode get_available_platforms non disponible")

            if self.current_platform not in available_platforms:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Plateforme non disponible",
                    f"La plateforme {self.current_platform} n'est pas disponible actuellement."
                )
                self.platform_tested.emit(self.current_platform, False, "Plateforme non disponible")
                return

            # Récupérer les informations du navigateur
            profile = self.profiles.get(self.current_platform, {})
            browser_info = profile.get('browser', {})

            # Vérifier si les informations essentielles sont présentes
            if not browser_info.get('url'):
                # Si aucun navigateur n'est configuré, suggérer de le faire
                QtWidgets.QMessageBox.warning(
                    self,
                    "Configuration incomplète",
                    "Veuillez configurer l'URL du navigateur dans l'onglet Navigateur avant de tester la connexion."
                )
                # Passer automatiquement à l'onglet navigateur
                self.tabs.setCurrentIndex(1)
                return

            # Afficher un dialogue de progression
            progress = QtWidgets.QProgressDialog(
                f"Test de la connexion avec {self.current_platform}...",
                "Annuler",
                0, 100,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)

            # Récupérer les options de détection depuis le widget navigateur
            force_detection = False
            remember_positions = True

            if hasattr(self, 'browser_widget'):
                force_detection = self.browser_widget.should_force_detect()
                remember_positions = self.browser_widget.should_remember_positions()

            print(f"DEBUG: Force détection: {force_detection}")

            try:
                # Utiliser la nouvelle méthode de test
                if hasattr(self.conductor, 'test_platform_connection'):
                    print("DEBUG: Utilisation de test_platform_connection")
                    progress.setValue(20)
                    progress.setLabelText("Connexion au navigateur...")

                    # Appeler la méthode de test avec les informations du navigateur
                    result = self.conductor.test_platform_connection(
                        self.current_platform,
                        force_detection=force_detection,
                        browser_type=browser_info.get('type', 'Chrome'),
                        browser_path=browser_info.get('path', ''),
                        url=browser_info.get('url', ''),
                        timeout=30
                    )

                    print(f"DEBUG: Résultat du test: {result}")
                    progress.setValue(90)

                    if result.get('success'):
                        progress.setValue(100)

                        # Si des positions ont été détectées, les enregistrer
                        if 'positions' in result and remember_positions:
                            profile['interface_positions'] = result['positions']
                            print(f"DEBUG: Positions enregistrées: {len(result['positions'])}")

                            # Sauvegarder le profil mis à jour
                            if hasattr(self.conductor.database, 'save_platform'):
                                try:
                                    self.conductor.database.save_platform(self.current_platform, profile)
                                    print("DEBUG: Profil avec positions sauvegardé dans DB")
                                except Exception as e:
                                    print(f"DEBUG: Erreur sauvegarde positions DB: {str(e)}")
                                    self._save_platform_file(self.current_platform, profile)
                            else:
                                # Fallback sur le système de fichiers
                                self._save_platform_file(self.current_platform, profile)

                        # Mettre à jour les indicateurs d'état après un test réussi
                        self._update_tab_status()

                        QtWidgets.QMessageBox.information(
                            self,
                            "Test réussi",
                            f"La connexion avec {self.current_platform} fonctionne correctement."
                        )
                        self.platform_tested.emit(self.current_platform, True, "Test réussi")
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Échec du test",
                            f"La connexion avec {self.current_platform} a échoué: {result.get('message', 'Erreur inconnue')}"
                        )
                        self.platform_tested.emit(self.current_platform, False, result.get('error', 'Erreur inconnue'))
                else:
                    # Fallback sur l'ancienne méthode (simulation)
                    print("DEBUG: Méthode test_platform_connection non disponible, fallback sur send_prompt")
                    if hasattr(self.conductor, 'send_prompt'):
                        # Envoyer le prompt
                        result = self.conductor.send_prompt(
                            self.current_platform,
                            "Ceci est un test de connexion. Veuillez répondre avec 'OK'.",
                            mode="standard",
                            sync=True,
                            timeout=10
                        )

                        print(f"DEBUG: Résultat send_prompt: {result}")
                        progress.setValue(100)

                        # Vérifier le résultat
                        if result and 'result' in result and 'response' in result['result']:
                            response = result['result']['response']

                            if 'OK' in response:
                                QtWidgets.QMessageBox.information(
                                    self,
                                    "Test réussi",
                                    f"La connexion avec {self.current_platform} fonctionne correctement."
                                )
                                self.platform_tested.emit(self.current_platform, True, "Test réussi")
                            else:
                                QtWidgets.QMessageBox.warning(
                                    self,
                                    "Test partiellement réussi",
                                    f"La plateforme {self.current_platform} a répondu, mais pas avec le texte attendu."
                                )
                                self.platform_tested.emit(self.current_platform, True, "Réponse incorrecte")
                        else:
                            QtWidgets.QMessageBox.critical(
                                self,
                                "Échec du test",
                                f"La plateforme {self.current_platform} n'a pas répondu correctement."
                            )
                            self.platform_tested.emit(self.current_platform, False, "Pas de réponse")
                    else:
                        # Si send_prompt n'existe pas
                        print("DEBUG: Ni test_platform_connection ni send_prompt disponibles, simulation")
                        QtWidgets.QMessageBox.information(
                            self,
                            "Simulation",
                            f"Test simulé pour {self.current_platform} (functionality non disponible)"
                        )
                        self.platform_tested.emit(self.current_platform, True, "Test simulé")

            except Exception as e:
                logger.error(f"Erreur test interne: {str(e)}")
                print(f"DEBUG: Erreur test interne: {str(e)}")
                print(traceback.format_exc())
                progress.cancel()
                raise e

        except Exception as e:
            logger.error(f"Erreur lors du test: {str(e)}")
            print(f"DEBUG: Erreur globale test: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de test",
                f"Impossible de tester la connexion: {str(e)}"
            )
            self.platform_tested.emit(self.current_platform, False, str(e))

    def _on_cancel_edit(self):
        """Annule l'édition en cours"""
        # Si une plateforme est sélectionnée, recharger ses données
        print("DEBUG: Annulation de l'édition")

        # Masquer le guide d'aide
        self.workflow_help.setVisible(False)
        self.is_new_platform = False

        if self.current_platform:
            current_item = None
            print(f"DEBUG: Rechargement de {self.current_platform}")

            for i in range(self.platform_list.count()):
                item = self.platform_list.item(i)
                if item.data(Qt.UserRole) == self.current_platform:
                    current_item = item
                    break

            if current_item:
                self.platform_list.setCurrentItem(current_item)
        else:
            # Toujours activer les widgets, même en annulant
            self._set_details_enabled(True)

        # S'assurer que les widgets restent activés
        self._force_enable_all_widgets()

    def refresh(self):
        """Actualise la liste des plateformes"""
        print("DEBUG: Rafraîchissement de la liste des plateformes")
        # Charger directement depuis les fichiers pour être sûr
        self._load_profiles_from_files()
        self._load_platforms()

        # Actualiser le widget navigateur
        if hasattr(self, 'browser_widget'):
            self.browser_widget.refresh()

        # Actualiser le widget de champ de prompt
        if hasattr(self, 'prompt_field_widget'):
            self.prompt_field_widget.refresh()

        # Actualiser le widget de la zone de réponse
        if hasattr(self, 'response_area_widget'):
            self.response_area_widget.refresh()

        # S'assurer que les widgets restent activés
        self._force_enable_all_widgets()

        # Mettre à jour les indicateurs d'état
        self._update_tab_status()