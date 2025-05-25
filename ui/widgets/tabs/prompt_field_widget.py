#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/prompt_field_widget.py
"""

import os
import json
import traceback
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from core.vision.color_extractor import ColorExtractor

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class PromptFieldWidget(QtWidgets.QWidget):
    """Widget de configuration du champ de prompt pour les plateformes d'IA"""

    # Signaux
    prompt_field_configured = pyqtSignal(str, dict)  # Plateforme, configuration
    prompt_field_detected = pyqtSignal(str, dict)  # Plateforme, position

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration du champ de prompt
        """
        super().__init__(parent)

        # Debug
        print("PromptFieldWidget: Initialisation...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None

        # Ajouter l'extracteur de couleurs
        self.color_extractor = ColorExtractor(self.conductor.detector if hasattr(self.conductor, 'detector') else None)

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
        """Configure l'interface utilisateur du widget de champ de prompt"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Explication
        explanation = QtWidgets.QLabel(
            "Ce module permet de configurer le champ de texte où vous entrez vos prompts.\n"
            "Commencez par sélectionner votre plateforme, puis configurez les paramètres de détection."
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
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_combo)

        left_column.addWidget(platform_group)

        left_column.addWidget(platform_group)

        # === Section Actions ===
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(300)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        # Bouton de capture
        self.capture_button = QtWidgets.QPushButton("Capturer le champ")
        self.capture_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.capture_button.clicked.connect(self._on_capture_prompt_field)
        actions_layout.addWidget(self.capture_button)

        # Statut de capture
        self.capture_status = QtWidgets.QLabel("Aucune capture")
        self.capture_status.setAlignment(Qt.AlignCenter)
        self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        actions_layout.addWidget(self.capture_status)

        # Options de capture
        self.remember_position_check = QtWidgets.QCheckBox("Mémoriser la position")
        self.remember_position_check.setChecked(True)
        actions_layout.addWidget(self.remember_position_check)

        self.force_capture_check = QtWidgets.QCheckBox("Forcer la capture")
        actions_layout.addWidget(self.force_capture_check)

        left_column.addWidget(actions_group)

        # === Section Sauvegarde ===
        save_group = QtWidgets.QGroupBox("Sauvegarde")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        # Bouton de prévisualisation
        self.preview_button = QtWidgets.QPushButton("◉ Prévisualiser")
        self.preview_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.preview_button.clicked.connect(self._preview_configuration)
        save_layout.addWidget(self.preview_button)

        # Bouton de sauvegarde
        self.save_button = QtWidgets.QPushButton("⬇ Enregistrer")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_config)
        save_layout.addWidget(self.save_button)

        left_column.addWidget(save_group)

        # Spacer pour pousser tout vers le haut
        left_column.addStretch()

        # === COLONNE DROITE : Configuration ===
        right_column = QtWidgets.QVBoxLayout()

        # === Section 2: Configuration du champ de texte ===
        config_group = QtWidgets.QGroupBox("Configuration du champ de prompt")
        config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_layout = QtWidgets.QFormLayout(config_group)

        # Placeholder
        self.placeholder_edit = QtWidgets.QLineEdit()
        self.placeholder_edit.setPlaceholderText("Texte placeholder (ex: Poser une question)")
        self.placeholder_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        config_layout.addRow("Placeholder:", self.placeholder_edit)

        # Type de champ
        self.field_type_combo = QtWidgets.QComboBox()
        self.field_type_combo.addItems(["textarea", "input", "contenteditable"])
        self.field_type_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        config_layout.addRow("Type de champ:", self.field_type_combo)

        # Méthode de détection
        self.detection_method_combo = QtWidgets.QComboBox()
        self.detection_method_combo.addItems(["findContour", "templateMatching", "textRecognition"])
        self.detection_method_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.detection_method_combo.currentIndexChanged.connect(self._on_detection_method_changed)
        config_layout.addRow("Méthode de détection:", self.detection_method_combo)

        # === Section simplifiée pour les couleurs ===
        self.color_config_widget = QtWidgets.QWidget()
        color_layout = QtWidgets.QVBoxLayout(self.color_config_widget)
        color_layout.setContentsMargins(5, 5, 5, 5)
        color_layout.setSpacing(10)

        # Explication simple
        auto_explanation = QtWidgets.QLabel(
            "Cliquez sur 'Auto-détecter' pour analyser automatiquement les couleurs du champ.\n"
            "Assurez-vous que le navigateur est ouvert avec le champ visible."
        )
        auto_explanation.setWordWrap(True)
        auto_explanation.setStyleSheet("color: #555; padding: 5px;")
        color_layout.addWidget(auto_explanation)

        # Bouton principal d'auto-détection
        self.auto_detect_button = QtWidgets.QPushButton("◉ Auto-détecter les couleurs")
        self.auto_detect_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.auto_detect_button.clicked.connect(self._auto_detect_colors)
        self.auto_detect_button.setMinimumHeight(40)
        color_layout.addWidget(self.auto_detect_button)

        # Statut de la détection
        self.color_detection_status = QtWidgets.QLabel("Aucune couleur détectée")
        self.color_detection_status.setAlignment(Qt.AlignCenter)
        self.color_detection_status.setStyleSheet("color: #888; padding: 5px;")
        color_layout.addWidget(self.color_detection_status)

        # Section avancée : Paramètres manuels (masquée par défaut)
        self.advanced_color_section = QtWidgets.QGroupBox("Paramètres avancés")
        self.advanced_color_section.setCheckable(True)
        self.advanced_color_section.setChecked(False)  # Masqué par défaut
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_color_section)

        # Note explicative
        manual_note = QtWidgets.QLabel(
            "⚠ Ces paramètres sont automatiquement configurés par la détection. "
            "Modifiez-les seulement si la détection automatique échoue."
        )
        manual_note.setWordWrap(True)
        manual_note.setStyleSheet("color: #d67a0e; font-size: 11px; padding: 5px;")
        advanced_layout.addWidget(manual_note)

        # Spinboxes RGB (initialisés pour éviter les erreurs)
        self.lower_r_spin = QtWidgets.QSpinBox()
        self.lower_r_spin.setRange(0, 255)
        self.lower_r_spin.setValue(240)
        self.lower_r_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.lower_g_spin = QtWidgets.QSpinBox()
        self.lower_g_spin.setRange(0, 255)
        self.lower_g_spin.setValue(240)
        self.lower_g_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.lower_b_spin = QtWidgets.QSpinBox()
        self.lower_b_spin.setRange(0, 255)
        self.lower_b_spin.setValue(240)
        self.lower_b_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.upper_r_spin = QtWidgets.QSpinBox()
        self.upper_r_spin.setRange(0, 255)
        self.upper_r_spin.setValue(255)
        self.upper_r_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.upper_g_spin = QtWidgets.QSpinBox()
        self.upper_g_spin.setRange(0, 255)
        self.upper_g_spin.setValue(255)
        self.upper_g_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.upper_b_spin = QtWidgets.QSpinBox()
        self.upper_b_spin.setRange(0, 255)
        self.upper_b_spin.setValue(255)
        self.upper_b_spin.setStyleSheet(PlatformConfigStyle.get_input_style())

        # Layout simple pour les RGB
        rgb_layout = QtWidgets.QGridLayout()

        # Couleur inférieure
        rgb_layout.addWidget(QtWidgets.QLabel("Limite inférieure:"), 0, 0)
        rgb_layout.addWidget(QtWidgets.QLabel("R:"), 0, 1)
        rgb_layout.addWidget(self.lower_r_spin, 0, 2)
        rgb_layout.addWidget(QtWidgets.QLabel("G:"), 0, 3)
        rgb_layout.addWidget(self.lower_g_spin, 0, 4)
        rgb_layout.addWidget(QtWidgets.QLabel("B:"), 0, 5)
        rgb_layout.addWidget(self.lower_b_spin, 0, 6)

        # Couleur supérieure
        rgb_layout.addWidget(QtWidgets.QLabel("Limite supérieure:"), 1, 0)
        rgb_layout.addWidget(QtWidgets.QLabel("R:"), 1, 1)
        rgb_layout.addWidget(self.upper_r_spin, 1, 2)
        rgb_layout.addWidget(QtWidgets.QLabel("G:"), 1, 3)
        rgb_layout.addWidget(self.upper_g_spin, 1, 4)
        rgb_layout.addWidget(QtWidgets.QLabel("B:"), 1, 5)
        rgb_layout.addWidget(self.upper_b_spin, 1, 6)

        advanced_layout.addLayout(rgb_layout)

        # Surface minimale
        area_layout = QtWidgets.QHBoxLayout()
        area_layout.addWidget(QtWidgets.QLabel("Surface minimale:"))
        self.min_area_spin = QtWidgets.QSpinBox()
        self.min_area_spin.setRange(10, 1000000)
        self.min_area_spin.setValue(100)
        self.min_area_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.min_area_spin.setSuffix(" px²")
        area_layout.addWidget(self.min_area_spin)
        area_layout.addStretch()

        advanced_layout.addLayout(area_layout)

        # Connecter les événements pour les spinboxes (pour compatibilité)
        self.lower_r_spin.valueChanged.connect(self._update_color_status)
        self.lower_g_spin.valueChanged.connect(self._update_color_status)
        self.lower_b_spin.valueChanged.connect(self._update_color_status)
        self.upper_r_spin.valueChanged.connect(self._update_color_status)
        self.upper_g_spin.valueChanged.connect(self._update_color_status)
        self.upper_b_spin.valueChanged.connect(self._update_color_status)

        color_layout.addWidget(self.advanced_color_section)

        config_layout.addRow("Configuration des couleurs:", self.color_config_widget)

        # === Configuration pour la détection par template matching ===
        self.template_config_widget = QtWidgets.QWidget()
        template_layout = QtWidgets.QVBoxLayout(self.template_config_widget)
        template_layout.setContentsMargins(0, 0, 0, 0)

        template_explanation = QtWidgets.QLabel(
            "La détection par template matching utilise une image de référence. "
            "Capturez une image de l'élément à détecter, puis testez la détection."
        )
        template_explanation.setWordWrap(True)
        template_layout.addWidget(template_explanation)

        template_capture_button = QtWidgets.QPushButton("Capturer l'image de référence")
        template_capture_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        template_capture_button.clicked.connect(self._capture_template)
        template_layout.addWidget(template_capture_button)

        # Seuil de correspondance
        threshold_layout = QtWidgets.QHBoxLayout()
        threshold_layout.addWidget(QtWidgets.QLabel("Seuil de correspondance:"))
        self.threshold_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(80)
        self.threshold_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.threshold_slider.setTickInterval(10)
        threshold_layout.addWidget(self.threshold_slider)
        self.threshold_value = QtWidgets.QLabel("0.8")
        threshold_layout.addWidget(self.threshold_value)
        self.threshold_slider.valueChanged.connect(
            lambda v: self.threshold_value.setText(f"{v / 100:.1f}")
        )
        template_layout.addLayout(threshold_layout)

        # Cacher par défaut
        self.template_config_widget.setVisible(False)
        config_layout.addRow("Template matching:", self.template_config_widget)

        # === Configuration pour la détection par reconnaissance de texte ===
        self.text_config_widget = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(self.text_config_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)

        text_explanation = QtWidgets.QLabel(
            "La détection par reconnaissance de texte recherche le texte placeholder du champ. "
            "Assurez-vous que le texte est visible à l'écran."
        )
        text_explanation.setWordWrap(True)
        text_layout.addWidget(text_explanation)

        # Texte à rechercher
        text_to_search_layout = QtWidgets.QHBoxLayout()
        text_to_search_layout.addWidget(QtWidgets.QLabel("Texte à rechercher:"))
        self.text_to_search_edit = QtWidgets.QLineEdit()
        self.text_to_search_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.text_to_search_edit.textChanged.connect(self._update_placeholder)
        text_to_search_layout.addWidget(self.text_to_search_edit)
        text_layout.addLayout(text_to_search_layout)

        # Cases à cocher pour les options de recherche
        self.case_sensitive_check = QtWidgets.QCheckBox("Sensible à la casse")
        self.case_sensitive_check.setChecked(False)
        text_layout.addWidget(self.case_sensitive_check)

        self.use_regex_check = QtWidgets.QCheckBox("Utiliser des expressions régulières")
        self.use_regex_check.setChecked(False)
        text_layout.addWidget(self.use_regex_check)

        # Option de validation du placeholder
        self.validate_placeholder_check = QtWidgets.QCheckBox("Valider le placeholder par OCR")
        self.validate_placeholder_check.setChecked(True)
        self.validate_placeholder_check.setToolTip(
            "Utilise l'OCR pour vérifier que le texte du placeholder correspond à celui attendu"
        )
        text_layout.addWidget(self.validate_placeholder_check)

        # Options de prétraitement OCR
        self.improve_ocr_check = QtWidgets.QCheckBox("Prétraiter l'image pour améliorer l'OCR")
        self.improve_ocr_check.setChecked(True)
        self.improve_ocr_check.setToolTip(
            "Applique des filtres d'image pour améliorer la précision de la reconnaissance de texte"
        )
        text_layout.addWidget(self.improve_ocr_check)

        # Seuil de similarité pour la validation OCR
        similarity_layout = QtWidgets.QHBoxLayout()
        similarity_layout.addWidget(QtWidgets.QLabel("Seuil de similarité:"))
        self.similarity_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.similarity_slider.setRange(0, 100)
        self.similarity_slider.setValue(70)  # 0.7 par défaut
        self.similarity_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        similarity_layout.addWidget(self.similarity_slider)
        self.similarity_value = QtWidgets.QLabel("0.7")
        similarity_layout.addWidget(self.similarity_value)
        self.similarity_slider.valueChanged.connect(
            lambda v: self.similarity_value.setText(f"{v / 100:.1f}")
        )
        text_layout.addLayout(similarity_layout)

        # Cacher par défaut
        self.text_config_widget.setVisible(False)
        config_layout.addRow("Reconnaissance de texte:", self.text_config_widget)

        right_column.addWidget(config_group)

        # Assembler les colonnes
        columns_layout.addLayout(left_column, 0)  # 0 = pas d'étirement
        columns_layout.addLayout(right_column, 1)  # 1 = étirement pour prendre l'espace restant

        main_layout.addLayout(columns_layout)

        # Note d'aide en bas
        help_note = QtWidgets.QLabel(
            "<b>Workflow:</b> 1▸ Sélectionnez la plateforme → 2▸ Configurez les paramètres → "
            "3▸ Prévisualisez → 4▸ Enregistrez"
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
        self._update_platform_combo()

    def select_platform(self, platform_name):
        """
        Sélectionne une plateforme dans la liste déroulante

        Args:
            platform_name (str): Nom de la plateforme à sélectionner
        """
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        """Actualise les données du widget"""
        self._update_platform_combo()

        # Si une plateforme est déjà sélectionnée, rafraîchir ses données
        if self.current_platform:
            self._load_platform_config(self.current_platform)

    def _update_placeholder(self, text):
        """
        Met à jour le placeholder quand le texte de recherche OCR change

        Args:
            text (str): Nouveau texte de recherche
        """
        # Synchroniser le placeholder et le texte de recherche OCR
        if self.detection_method_combo.currentText() == "textRecognition":
            self.placeholder_edit.setText(text)

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

    def _update_color_status(self):
        """Met à jour le statut des couleurs configurées"""
        if hasattr(self, 'color_detection_status'):
            lower_rgb = f"RGB({self.lower_r_spin.value()}, {self.lower_g_spin.value()}, {self.lower_b_spin.value()})"
            upper_rgb = f"RGB({self.upper_r_spin.value()}, {self.upper_g_spin.value()}, {self.upper_b_spin.value()})"
            self.color_detection_status.setText(f"Couleurs configurées: {lower_rgb} - {upper_rgb}")
            self.color_detection_status.setStyleSheet("color: #2e7d32; padding: 5px;")

    def _on_detection_method_changed(self, index):
        """
        Gère le changement de méthode de détection

        Args:
            index (int): Index de la méthode sélectionnée
        """
        method = self.detection_method_combo.currentText()

        # Afficher/masquer les widgets de configuration en fonction de la méthode
        self.color_config_widget.setVisible(method == "findContour")
        self.template_config_widget.setVisible(method == "templateMatching")
        self.text_config_widget.setVisible(method == "textRecognition")

        # Si textRecognition est sélectionné, synchroniser le placeholder
        if method == "textRecognition":
            self.text_to_search_edit.setText(self.placeholder_edit.text())

    def _on_platform_selected(self, index):
        """
        Gère la sélection d'une plateforme dans la liste

        Args:
            index (int): Index de la plateforme sélectionnée
        """
        if index <= 0:  # L'index 0 correspond à "-- Sélectionnez une plateforme --"
            self.current_platform = None
            self.current_profile = None
            return

        platform_name = self.platform_combo.currentText()
        self._load_platform_config(platform_name)

    def _load_platform_config(self, platform_name):
        """
        Charge la configuration de la plateforme sélectionnée

        Args:
            platform_name (str): Nom de la plateforme
        """
        self.current_platform = platform_name
        self.current_profile = self.profiles.get(platform_name, {})

        if not self.current_profile:
            print(f"DEBUG: Profil vide pour {platform_name}!")
            return

        # Charger les informations du champ de prompt
        interface = self.current_profile.get('interface', {})
        prompt_field = interface.get('prompt_field', {})

        # Placeholder
        self.placeholder_edit.setText(prompt_field.get('placeholder', ''))

        # Type de champ
        field_type = prompt_field.get('type', 'textarea')
        index = self.field_type_combo.findText(field_type)
        if index >= 0:
            self.field_type_combo.setCurrentIndex(index)

        # Méthode de détection
        detection = prompt_field.get('detection', {})
        method = detection.get('method', 'findContour')
        index = self.detection_method_combo.findText(method)
        if index >= 0:
            self.detection_method_combo.setCurrentIndex(index)

        # Plage de couleurs
        color_range = detection.get('color_range', {})
        lower = color_range.get('lower', [240, 240, 240])
        upper = color_range.get('upper', [255, 255, 255])

        if len(lower) >= 3:
            self.lower_r_spin.setValue(lower[0])
            self.lower_g_spin.setValue(lower[1])
            self.lower_b_spin.setValue(lower[2])

        if len(upper) >= 3:
            self.upper_r_spin.setValue(upper[0])
            self.upper_g_spin.setValue(upper[1])
            self.upper_b_spin.setValue(upper[2])

        # Surface minimale
        min_area = detection.get('min_area', 100)
        self.min_area_spin.setValue(min_area)

        # Mettre à jour le statut des couleurs
        self._update_color_status()

        # Configuration TextRecognition
        if method == "textRecognition":
            # Texte à rechercher
            self.text_to_search_edit.setText(prompt_field.get('placeholder', ''))

            # Options OCR
            ocr_config = detection.get('ocr_config', {})
            self.case_sensitive_check.setChecked(ocr_config.get('case_sensitive', False))
            self.use_regex_check.setChecked(ocr_config.get('use_regex', False))
            self.validate_placeholder_check.setChecked(ocr_config.get('validate_placeholder', True))
            self.improve_ocr_check.setChecked(ocr_config.get('improve_ocr', True))

            # Seuil de similarité
            similarity = ocr_config.get('similarity_threshold', 0.7)
            self.similarity_slider.setValue(int(similarity * 100))
            self.similarity_value.setText(f"{similarity:.1f}")

        # Configuration TemplateMatching
        elif method == "templateMatching":
            # Seuil
            threshold = detection.get('threshold', 0.8)
            self.threshold_slider.setValue(int(threshold * 100))
            self.threshold_value.setText(f"{threshold:.1f}")

        # Vérifier si des positions sont déjà enregistrées
        positions = self.current_profile.get('interface_positions', {})
        if 'prompt_field' in positions:
            self.capture_status.setText("Position enregistrée")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        else:
            self.capture_status.setText("Aucune capture effectuée")
            self.capture_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def _auto_detect_colors(self):
        """
        Auto-détecte les couleurs du champ de prompt en analysant l'écran
        """
        try:
            # Vérifier qu'une plateforme est sélectionnée
            if not self.current_platform:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune plateforme sélectionnée",
                    "Veuillez d'abord sélectionner une plateforme."
                )
                return

            # Récupérer le texte du placeholder
            placeholder_text = self.placeholder_edit.text().strip()
            if not placeholder_text:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Placeholder manquant",
                    "Veuillez d'abord saisir le texte du placeholder du champ de prompt."
                )
                return

            # Mettre à jour le statut
            self.color_detection_status.setText("◉ Analyse en cours...")
            self.color_detection_status.setStyleSheet(
                "color: #1976D2; font-style: italic; padding: 8px; "
                "background-color: #e3f2fd; border-radius: 4px; margin: 5px;"
            )
            QtWidgets.QApplication.processEvents()

            # Vérifier que le navigateur est ouvert avec la bonne page
            reply = QtWidgets.QMessageBox.question(
                self,
                "Préparation requise",
                f"Assurez-vous que :\n"
                f"▪ Le navigateur est ouvert sur {self.current_platform}\n"
                f"▪ Le champ de prompt est visible à l'écran\n"
                f"▪ Le placeholder '{placeholder_text}' est affiché\n\n"
                f"Continuer l'auto-détection ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply != QtWidgets.QMessageBox.Yes:
                self.color_detection_status.setText("◯ Aucune couleur détectée")
                self.color_detection_status.setStyleSheet(
                    "color: #888; font-style: italic; padding: 8px; "
                    "background-color: #f5f5f5; border-radius: 4px; margin: 5px;"
                )
                return

            # Attendre un peu pour laisser le temps à l'utilisateur de préparer l'écran
            time.sleep(1)

            # Effectuer l'extraction de couleurs
            result = self.color_extractor.extract_prompt_field_colors(placeholder_text)

            if not result['success']:
                self.color_detection_status.setText(f"✕ Détection échouée: {result['error']}")
                self.color_detection_status.setStyleSheet(
                    "color: #d32f2f; padding: 8px; "
                    "background-color: #ffebee; border-radius: 4px; margin: 5px;"
                )

                QtWidgets.QMessageBox.warning(
                    self,
                    "Détection échouée",
                    f"Impossible de détecter le champ de prompt :\n{result['error']}\n\n"
                    f"Suggestions :\n"
                    f"▪ Vérifiez que le champ est visible\n"
                    f"▪ Vérifiez que le placeholder est correct\n"
                    f"▪ Utilisez les paramètres avancés pour configuration manuelle"
                )
                return

            # Appliquer les couleurs détectées
            suggestions = result['suggested_ranges']
            if suggestions['best_choice']:
                best_colors = suggestions['best_choice']

                # Mettre à jour les spinboxes avec les couleurs suggérées
                lower = best_colors['lower']
                upper = best_colors['upper']

                self.lower_r_spin.setValue(lower[2])  # OpenCV utilise BGR, on veut RGB
                self.lower_g_spin.setValue(lower[1])
                self.lower_b_spin.setValue(lower[0])

                self.upper_r_spin.setValue(upper[2])
                self.upper_g_spin.setValue(upper[1])
                self.upper_b_spin.setValue(upper[0])

                # Mettre à jour le statut
                self._update_color_status()

                # Afficher un message de succès simple
                QtWidgets.QMessageBox.information(
                    self,
                    "Auto-détection réussie",
                    f"✓ Détection réussie !\n\n"
                    f"Méthode utilisée : {best_colors['name']}\n"
                    f"Confiance : {best_colors['confidence']:.1f}%\n\n"
                    f"Les couleurs ont été automatiquement configurées."
                )

            else:
                self.color_detection_status.setText("✕ Aucune couleur appropriée trouvée")
                self.color_detection_status.setStyleSheet(
                    "color: #d32f2f; padding: 8px; "
                    "background-color: #ffebee; border-radius: 4px; margin: 5px;"
                )

                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune couleur détectée",
                    "L'analyse n'a pas pu déterminer de couleurs appropriées.\n"
                    "Utilisez les paramètres avancés pour configuration manuelle."
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'auto-détection des couleurs: {str(e)}")

            self.color_detection_status.setText(f"✕ Erreur: {str(e)}")
            self.color_detection_status.setStyleSheet(
                "color: #d32f2f; padding: 8px; "
                "background-color: #ffebee; border-radius: 4px; margin: 5px;"
            )

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'auto-détection",
                f"Une erreur est survenue lors de l'auto-détection :\n{str(e)}\n\n"
                f"Utilisez les paramètres avancés pour configuration manuelle."
            )

    def _preview_configuration(self):
        """
        Affiche une prévisualisation visuelle du champ détecté
        """
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Vérifier qu'une position a été capturée
        if not self.current_profile or 'interface_positions' not in self.current_profile:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune capture effectuée",
                "Veuillez d'abord capturer le champ de prompt avant de prévisualiser."
            )
            return

        positions = self.current_profile['interface_positions']
        if 'prompt_field' not in positions:
            QtWidgets.QMessageBox.warning(
                self,
                "Champ non capturé",
                "Le champ de prompt n'a pas été capturé. Effectuez une capture d'abord."
            )
            return

        try:
            # Utiliser le screenshot déjà capturé si disponible
            if hasattr(self, 'screenshot') and self.screenshot is not None:
                screenshot = self.screenshot.copy()
            else:
                # Capturer spécifiquement la fenêtre du navigateur
                profile = self.profiles.get(self.current_platform, {})
                browser_info = profile.get('browser', {})
                browser_type = browser_info.get('type', 'Chrome')

                screenshot = self.conductor.detector.capture_screen(
                    force=True,
                    browser_type=browser_type
                )

            # Récupérer la position du champ
            field_pos = positions['prompt_field']
            x = field_pos.get('x', 0)
            y = field_pos.get('y', 0)
            w = field_pos.get('width', 100)
            h = field_pos.get('height', 30)
            center_x = field_pos.get('center_x', x + w // 2)
            center_y = field_pos.get('center_y', y + h // 2)

            # Vérifier que les coordonnées sont valides
            img_height, img_width = screenshot.shape[:2]
            if x < 0 or y < 0 or x + w > img_width or y + h > img_height:
                logger.warning(f"Coordonnées hors limites: champ({x},{y},{w},{h}) vs image({img_width},{img_height})")
                # Ajuster les coordonnées
                x = max(0, min(x, img_width - w))
                y = max(0, min(y, img_height - h))
                w = min(w, img_width - x)
                h = min(h, img_height - y)

            # Créer une zone étendue autour du champ pour le contexte
            margin = 80
            extended_x = max(0, x - margin)
            extended_y = max(0, y - margin)
            extended_w = min(img_width - extended_x, w + 2 * margin)
            extended_h = min(img_height - extended_y, h + 2 * margin)

            # Extraire la zone étendue
            preview_region = screenshot[extended_y:extended_y + extended_h, extended_x:extended_x + extended_w].copy()

            # Dessiner les annotations sur la zone étendue
            import cv2

            # Coordonnées relatives dans la zone étendue
            rel_x = x - extended_x
            rel_y = y - extended_y
            rel_center_x = center_x - extended_x
            rel_center_y = center_y - extended_y

            # Vérifier que les coordonnées relatives sont valides
            if (rel_x >= 0 and rel_y >= 0 and
                    rel_x + w <= extended_w and rel_y + h <= extended_h):

                # Dessiner le rectangle du champ en vert (épaisseur 3 pour bien voir)
                cv2.rectangle(preview_region,
                              (rel_x, rel_y),
                              (rel_x + w, rel_y + h),
                              (0, 255, 0), 3)

                # Dessiner un rectangle intérieur plus fin
                cv2.rectangle(preview_region,
                              (rel_x + 1, rel_y + 1),
                              (rel_x + w - 1, rel_y + h - 1),
                              (0, 200, 0), 1)

                # Dessiner le point central en rouge (plus gros)
                cv2.circle(preview_region, (rel_center_x, rel_center_y), 8, (0, 0, 255), -1)
                cv2.circle(preview_region, (rel_center_x, rel_center_y), 6, (255, 255, 255), -1)
                cv2.circle(preview_region, (rel_center_x, rel_center_y), 4, (0, 0, 255), -1)

                # Ajouter du texte avec fond pour meilleure lisibilité
                text_bg_color = (0, 0, 0)
                text_color = (0, 255, 0)

                # Texte "Champ détecté"
                label_text = "Champ detecte"
                text_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                cv2.rectangle(preview_region,
                              (rel_x, rel_y - 30),
                              (rel_x + text_size[0] + 10, rel_y - 5),
                              text_bg_color, -1)
                cv2.putText(preview_region, label_text, (rel_x + 5, rel_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)

                # Texte coordonnées du centre
                coord_text = f"Centre: ({center_x}, {center_y})"
                coord_size = cv2.getTextSize(coord_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.rectangle(preview_region,
                              (rel_center_x - coord_size[0] // 2 - 5, rel_center_y + 15),
                              (rel_center_x + coord_size[0] // 2 + 5, rel_center_y + 35),
                              text_bg_color, -1)
                cv2.putText(preview_region, coord_text,
                            (rel_center_x - coord_size[0] // 2, rel_center_y + 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                logger.info(
                    f"Contour dessiné: zone étendue {extended_w}x{extended_h}, rectangle ({rel_x},{rel_y},{w},{h})")
            else:
                logger.error(
                    f"Coordonnées relatives invalides: rel_pos({rel_x},{rel_y},{w},{h}) vs zone({extended_w},{extended_h})")

            # Créer le dialogue de prévisualisation
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(f"Prévisualisation - {self.current_platform}")
            dialog.setModal(True)
            dialog.resize(900, 700)

            layout = QtWidgets.QVBoxLayout(dialog)

            # Titre
            title = QtWidgets.QLabel(f"▪ Champ détecté pour {self.current_platform}")
            title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            # Convertir l'image OpenCV en QPixmap pour l'affichage
            height, width = preview_region.shape[:2]
            if len(preview_region.shape) == 3:
                bytes_per_line = 3 * width
                q_image = QtGui.QImage(preview_region.data, width, height, bytes_per_line,
                                       QtGui.QImage.Format_RGB888).rgbSwapped()
            else:
                bytes_per_line = width
                q_image = QtGui.QImage(preview_region.data, width, height, bytes_per_line,
                                       QtGui.QImage.Format_Grayscale8)

            pixmap = QtGui.QPixmap.fromImage(q_image)

            # Afficher l'image dans un QLabel avec scroll si nécessaire
            image_label = QtWidgets.QLabel()
            max_display_width = 800
            max_display_height = 500

            if pixmap.width() > max_display_width or pixmap.height() > max_display_height:
                pixmap = pixmap.scaled(max_display_width, max_display_height, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)

            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("border: 2px solid #ddd; background-color: white; padding: 5px;")
            layout.addWidget(image_label)

            # Informations de détection
            info_layout = QtWidgets.QHBoxLayout()

            # Colonne gauche - Position
            pos_info = QtWidgets.QLabel(f"""
            <b>▪ Position détectée:</b><br>
            • Centre: ({center_x}, {center_y})<br>
            • Taille: {w} × {h} px<br>
            • Zone: ({x}, {y}) → ({x + w}, {y + h})
            """)
            pos_info.setStyleSheet("background-color: #e8f5e8; padding: 10px; border-radius: 5px;")

            # Colonne droite - Configuration
            config_info = QtWidgets.QLabel(f"""
            <b>▪ Configuration:</b><br>
            • Méthode: {self.detection_method_combo.currentText()}<br>
            • Type: {self.field_type_combo.currentText()}<br>
            • Placeholder: {self.placeholder_edit.text()[:30]}...
            """)
            config_info.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 5px;")

            info_layout.addWidget(pos_info)
            info_layout.addWidget(config_info)
            layout.addLayout(info_layout)

            # Légende
            legend = QtWidgets.QLabel(
                "▪ Rectangle vert: Zone du champ détecté  |  ▪ Point rouge: Centre de clic"
            )
            legend.setAlignment(Qt.AlignCenter)
            legend.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
            layout.addWidget(legend)

            # Boutons
            button_layout = QtWidgets.QHBoxLayout()

            cancel_button = QtWidgets.QPushButton("✕ Annuler")
            cancel_button.setStyleSheet(PlatformConfigStyle.get_button_style())
            cancel_button.clicked.connect(dialog.reject)

            save_button = QtWidgets.QPushButton("⬇ Confirmer et sauvegarder")
            save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
            save_button.clicked.connect(lambda: self._confirm_and_save(dialog))

            button_layout.addWidget(cancel_button)
            button_layout.addWidget(save_button)
            layout.addLayout(button_layout)

            dialog.exec_()

        except Exception as e:
            logger.error(f"Erreur lors de la prévisualisation: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de prévisualisation",
                f"Impossible de générer la prévisualisation:\n{str(e)}\n\n"
                f"Vérifiez que le champ a été correctement capturé."
            )

    def _confirm_and_save(self, dialog):
        """
        Confirme et sauvegarde la configuration
        """
        dialog.accept()
        self._on_save_config()

    def _capture_template(self):
        """Capture une image de référence pour le template matching"""
        QtWidgets.QMessageBox.information(
            self,
            "Capture d'image",
            "Cette fonctionnalité sera disponible ultérieurement.\n\n"
            "Pour l'instant, utilisez la méthode findContour qui est plus fiable."
        )

    def _on_capture_prompt_field(self):
        """Lance la capture du champ de prompt avec étapes séparées"""
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune plateforme sélectionnée",
                "Veuillez d'abord sélectionner une plateforme."
            )
            return

        # Vérifier les prérequis
        if not self._check_prerequisites():
            return

        # Message d'avertissement important
        reply = QtWidgets.QMessageBox.question(
            self,
            "⚠ Préparation pour la capture",
            f"<b>IMPORTANT:</b><br><br>"
            f"▪ Assurez-vous que le navigateur est ouvert sur {self.current_platform}<br>"
            f"▪ Le champ de prompt doit être visible à l'écran<br>"
            f"▪ <b style='color: red;'>NE TOUCHEZ PAS à l'ordinateur pendant la capture</b><br>"
            f"▪ <b style='color: red;'>N'utilisez pas la souris ou le clavier</b><br><br>"
            f"La capture va se faire en plusieurs étapes avec feedback.<br>"
            f"Le popup de progression restera visible.<br><br>"
            f"Êtes-vous prêt ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Démarrer le processus de capture avec étapes
        self._start_detection_process()

    def _check_prerequisites(self):
        """
        Vérifie que tous les prérequis sont remplis pour la capture

        Returns:
            bool: True si tous les prérequis sont OK
        """
        # Vérifier pygetwindow
        if not HAS_PYGETWINDOW:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Dépendance manquante",
                f"La bibliothèque 'pygetwindow' n'est pas installée.\n\n"
                f"Cette bibliothèque est nécessaire pour capturer spécifiquement\n"
                f"la fenêtre du navigateur et éviter les interférences.\n\n"
                f"Souhaitez-vous continuer avec la capture d'écran complète ?\n"
                f"(moins précis mais fonctionnel)\n\n"
                f"Pour installer pygetwindow: pip install pygetwindow",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply != QtWidgets.QMessageBox.Yes:
                return False

        # Vérifier la configuration du navigateur
        profile = self.profiles.get(self.current_platform, {})
        browser_info = profile.get('browser', {})
        browser_url = browser_info.get('url', '')

        if not browser_url:
            QtWidgets.QMessageBox.warning(
                self, "URL manquante",
                "Veuillez d'abord configurer l'URL du navigateur dans l'onglet 'Gestion des navigateurs'."
            )
            return False

        return True

    def _start_detection_process(self):
        """Lance le processus de détection en étapes séparées"""
        try:
            # Créer une notification système pour le feedback au lieu d'un dialogue
            self._show_system_notification("Démarrage de la détection...", "Étape 1/5: Préparation")

            # Utiliser des variables pour tracker le progrès sans popup
            self.detection_cancelled = False
            self.current_step = 0
            self.total_steps = 5

            # Mettre à jour le statut dans l'interface
            self.capture_status.setText("Étape 1/5: Préparation du navigateur...")
            self.capture_status.setStyleSheet("color: #1976D2; font-weight: bold;")
            QtWidgets.QApplication.processEvents()

            # Démarrer les étapes
            QtCore.QTimer.singleShot(500, self._step1_prepare_browser)

        except Exception as e:
            logger.error(f"Erreur lors du démarrage de la détection: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")

    def _show_system_notification(self, title, message):
        """Affiche une notification système"""
        try:
            # Utiliser les notifications Windows si possible
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title, message, duration=3, threaded=True)
        except:
            # Fallback: log uniquement
            logger.info(f"Notification: {title} - {message}")

    def _step1_prepare_browser(self):
        """Étape 1: Préparation du navigateur"""
        if self.detection_cancelled:
            return

        self.capture_status.setText("Étape 1/5: Préparation du navigateur...")
        QtWidgets.QApplication.processEvents()

        try:
            # Récupérer les infos du navigateur
            profile = self.profiles.get(self.current_platform, {})
            browser_info = profile.get('browser', {})
            self.browser_type = browser_info.get('type', 'Chrome')
            browser_path = browser_info.get('path', '')
            browser_url = browser_info.get('url', '')

            if not browser_url:
                self.capture_status.setText("❌ URL manquante")
                self.capture_status.setStyleSheet("color: #d32f2f;")
                QtWidgets.QMessageBox.warning(
                    self, "URL manquante",
                    "Veuillez d'abord configurer l'URL du navigateur."
                )
                return

            # Préparer la capture (minimiser Liris, activer navigateur)
            self.capture_status.setText("Étape 1/5: Minimisation de Liris et activation du navigateur...")
            QtWidgets.QApplication.processEvents()

            success = self.conductor.detector.prepare_browser_capture(
                self.browser_type,
                minimize_liris=True
            )

            if not success:
                logger.warning("Impossible de préparer le navigateur automatiquement")

            self._show_system_notification("Capture", "Étape 2/5: Capture en cours...")
            QtCore.QTimer.singleShot(1500, self._step2_capture_screen)

        except Exception as e:
            self.capture_status.setText(f"❌ Erreur étape 1: {str(e)}")
            self.capture_status.setStyleSheet("color: #d32f2f;")
            logger.error(f"Erreur étape 1: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur préparation navigateur: {str(e)}")

    def _step2_capture_screen(self):
        """Étape 2: Capture d'écran du navigateur spécifiquement"""
        if self.detection_cancelled:
            return

        self.capture_status.setText("Étape 2/5: Capture de la fenêtre du navigateur...")
        QtWidgets.QApplication.processEvents()

        try:
            # Capturer SEULEMENT la fenêtre du navigateur
            self.screenshot = self.conductor.detector.capture_screen(
                force=True,
                browser_type=self.browser_type
            )

            # Vérifier que la capture a réussi
            if self.screenshot is None or self.screenshot.size == 0:
                raise Exception("Capture de la fenêtre du navigateur échouée")

            logger.info(f"Capture réussie: {self.screenshot.shape}")
            self._show_system_notification("Capture", "Étape 3/5: Détection OpenCV...")

            QtCore.QTimer.singleShot(500, self._step3_opencv_detection)

        except Exception as e:
            self.capture_status.setText(f"❌ Erreur étape 2: {str(e)}")
            self.capture_status.setStyleSheet("color: #d32f2f;")
            logger.error(f"Erreur étape 2: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Erreur",
                f"Erreur capture du navigateur: {str(e)}\n\n"
                f"Assurez-vous que :\n"
                f"• Le navigateur {self.browser_type} est ouvert\n"
                f"• La fenêtre du navigateur est visible\n"
                f"• pygetwindow est installé (pip install pygetwindow)"
            )

    def _step3_opencv_detection(self):
        """Étape 3: Détection OpenCV"""
        if self.detection_cancelled:
            return

        self.capture_status.setText("Étape 3/5: Détection OpenCV des contours...")
        QtWidgets.QApplication.processEvents()

        try:
            # Configuration de détection
            method = self.detection_method_combo.currentText()
            detection_config = {
                "method": method
            }

            if method == "findContour":
                detection_config["color_range"] = {
                    "lower": [self.lower_r_spin.value(), self.lower_g_spin.value(), self.lower_b_spin.value()],
                    "upper": [self.upper_r_spin.value(), self.upper_g_spin.value(), self.upper_b_spin.value()]
                }
                detection_config["min_area"] = self.min_area_spin.value()

            # Interface temporaire pour la détection
            temp_interface = {
                "prompt_field": {
                    "type": self.field_type_combo.currentText(),
                    "placeholder": self.placeholder_edit.text(),
                    "detection": detection_config
                }
            }

            # Détecter avec OpenCV seulement
            self.detected_positions = self.conductor.detector.detect_interface_elements(
                self.screenshot,
                temp_interface
            )

            if 'prompt_field' in self.detected_positions:
                self._show_system_notification("Détection", "Étape 4/5: Validation OCR...")
                QtCore.QTimer.singleShot(500, self._step4_ocr_validation)
            else:
                self.capture_status.setText("❌ OpenCV n'a pas détecté le champ")
                self.capture_status.setStyleSheet("color: #d32f2f;")
                QtWidgets.QMessageBox.warning(
                    self, "Détection échouée",
                    "OpenCV n'a pas pu détecter le champ. Vérifiez les paramètres de couleur."
                )

        except Exception as e:
            self.capture_status.setText(f"❌ Erreur étape 3: {str(e)}")
            self.capture_status.setStyleSheet("color: #d32f2f;")
            logger.error(f"Erreur étape 3: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur détection OpenCV: {str(e)}")

    def _step4_ocr_validation(self):
        """Étape 4: Validation OCR du placeholder"""
        if self.detection_cancelled:
            return

        self.capture_status.setText("Étape 4/5: Validation OCR du placeholder...")
        QtWidgets.QApplication.processEvents()

        try:
            field_pos = self.detected_positions['prompt_field']
            placeholder_text = self.placeholder_edit.text()

            if not placeholder_text.strip():
                # Pas de validation OCR si pas de placeholder
                self.ocr_validation_result = True
                self.ocr_detected_text = "Aucun placeholder à valider"
                self.ocr_similarity = 1.0
                QtCore.QTimer.singleShot(300, self._step5_finalize)
                return

            # Extraire la zone du champ pour OCR
            x = field_pos.get('x', 0)
            y = field_pos.get('y', 0)
            w = field_pos.get('width', 100)
            h = field_pos.get('height', 30)

            # Zone étendue pour l'OCR
            margin = 10
            extended_x = max(0, x - margin)
            extended_y = max(0, y - margin)
            extended_w = min(self.screenshot.shape[1] - extended_x, w + 2 * margin)
            extended_h = min(self.screenshot.shape[0] - extended_y, h + 2 * margin)

            roi = self.screenshot[extended_y:extended_y + extended_h, extended_x:extended_x + extended_w]

            # OCR avec Tesseract
            import pytesseract
            detected_text = pytesseract.image_to_string(roi, config='--psm 8')

            # Vérifier similarité
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, detected_text.lower().strip(), placeholder_text.lower()).ratio()

            self.ocr_validation_result = similarity > 0.3  # Seuil assez bas car OCR pas toujours parfait
            self.ocr_detected_text = detected_text.strip()
            self.ocr_similarity = similarity

            logger.info(f"OCR: '{self.ocr_detected_text}' vs '{placeholder_text}' = {similarity:.2f}")
            self._show_system_notification("Validation", "Étape 5/5: Finalisation...")
            QtCore.QTimer.singleShot(300, self._step5_finalize)

        except Exception as e:
            # OCR échoué, mais on continue quand même
            logger.warning(f"OCR validation échouée: {str(e)}")
            self.ocr_validation_result = None
            self.ocr_detected_text = "Erreur OCR"
            self.ocr_similarity = 0
            QtCore.QTimer.singleShot(300, self._step5_finalize)

    def _step5_finalize(self):
        """Étape 5: Finalisation et affichage des résultats"""
        if self.detection_cancelled:
            return

        self.capture_status.setText("Étape 5/5: Finalisation...")
        QtWidgets.QApplication.processEvents()

        try:
            # Mettre à jour le profil avec la position détectée
            if self.remember_position_check.isChecked():
                if 'interface_positions' not in self.current_profile:
                    self.current_profile['interface_positions'] = {}

                self.current_profile['interface_positions']['prompt_field'] = self.detected_positions['prompt_field']
                self._save_profile()

            # Afficher les résultats détaillés
            self._show_system_notification("Terminé", "Capture réussie! Voir les résultats.")
            self._show_detection_results()

        except Exception as e:
            self.capture_status.setText(f"❌ Erreur étape 5: {str(e)}")
            self.capture_status.setStyleSheet("color: #d32f2f;")
            logger.error(f"Erreur étape 5: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur finalisation: {str(e)}")

    def _show_detection_results(self):
        """Affiche les résultats détaillés de la détection"""
        field_pos = self.detected_positions['prompt_field']

        # Créer dialogue de résultats
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Résultats de la détection")
        dialog.setModal(True)
        dialog.resize(600, 500)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Titre
        title = QtWidgets.QLabel("✓ Détection réussie")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2e7d32; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Résultats détaillés avec OCR
        results_text = f"""
        <b>▪ Position détectée (OpenCV):</b><br>
        • Centre: ({field_pos['center_x']}, {field_pos['center_y']})<br>
        • Taille: {field_pos['width']} × {field_pos['height']} px<br>
        • Zone: ({field_pos['x']}, {field_pos['y']}) → ({field_pos['x'] + field_pos['width']}, {field_pos['y'] + field_pos['height']})<br><br>

        <b>▪ Validation OCR:</b><br>
        """

        if hasattr(self, 'ocr_validation_result'):
            if self.ocr_validation_result is True:
                results_text += f"• <span style='color: #2e7d32;'>✓ Validation réussie</span> (similarité: {self.ocr_similarity:.1%})<br>"
                results_text += f"• Texte détecté: '<i>{self.ocr_detected_text}</i>'<br>"
                results_text += f"• Texte attendu: '<i>{self.placeholder_edit.text()}</i>'<br>"
            elif self.ocr_validation_result is False:
                results_text += f"• <span style='color: #d67a0e;'>⚠ Validation partielle</span> (similarité: {self.ocr_similarity:.1%})<br>"
                results_text += f"• Texte détecté: '<i>{self.ocr_detected_text}</i>'<br>"
                results_text += f"• Texte attendu: '<i>{self.placeholder_edit.text()}</i>'<br>"
            else:
                results_text += "• <span style='color: #d32f2f;'>⚠ OCR échoué</span>, position basée sur OpenCV uniquement<br>"
        else:
            results_text += "• ⚠ Validation OCR non effectuée<br>"

        results_label = QtWidgets.QLabel(results_text)
        results_label.setWordWrap(True)
        results_label.setStyleSheet("padding: 15px; background-color: #f5f5f5; border-radius: 5px;")
        layout.addWidget(results_label)

        # Boutons
        button_layout = QtWidgets.QHBoxLayout()

        ok_button = QtWidgets.QPushButton("✓ Accepter")
        ok_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        ok_button.clicked.connect(dialog.accept)

        preview_button = QtWidgets.QPushButton("◉ Prévisualiser")
        preview_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        preview_button.clicked.connect(lambda: (dialog.accept(), self._preview_configuration()))

        button_layout.addWidget(ok_button)
        button_layout.addWidget(preview_button)
        layout.addLayout(button_layout)

        # Mettre à jour le statut
        self.capture_status.setText("✓ Capture réussie!")
        self.capture_status.setStyleSheet("color: #2e7d32; font-weight: bold;")

        dialog.exec_()

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

            # Récupérer la méthode de détection
            method = self.detection_method_combo.currentText()

            # Construire la configuration de base
            prompt_field_config = {
                "type": self.field_type_combo.currentText(),
                "placeholder": self.placeholder_edit.text(),
                "detection": {
                    "method": method
                }
            }

            # Ajouter les paramètres spécifiques selon la méthode
            if method == "findContour":
                prompt_field_config["detection"]["color_range"] = {
                    "lower": [self.lower_r_spin.value(), self.lower_g_spin.value(), self.lower_b_spin.value()],
                    "upper": [self.upper_r_spin.value(), self.upper_g_spin.value(), self.upper_b_spin.value()]
                }
                prompt_field_config["detection"]["min_area"] = self.min_area_spin.value()

            elif method == "templateMatching":
                prompt_field_config["detection"]["threshold"] = self.threshold_slider.value() / 100.0

            elif method == "textRecognition":
                # Ajouter le texte et les options OCR
                prompt_field_config["detection"]["text"] = self.text_to_search_edit.text()
                prompt_field_config["detection"]["ocr_config"] = {
                    "case_sensitive": self.case_sensitive_check.isChecked(),
                    "use_regex": self.use_regex_check.isChecked(),
                    "validate_placeholder": self.validate_placeholder_check.isChecked(),
                    "improve_ocr": self.improve_ocr_check.isChecked(),
                    "similarity_threshold": self.similarity_slider.value() / 100.0
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
                    f"La configuration du champ de prompt pour {self.current_platform} a été enregistrée avec succès."
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur d'enregistrement",
                    "Impossible d'enregistrer la configuration."
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement: {str(e)}")
            print(f"DEBUG: Erreur enregistrement prompt field: {str(e)}")
            print(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'enregistrement: {str(e)}"
            )

    def _save_profile(self):
        """
        Sauvegarde le profil dans le système

        Returns:
            bool: True si la sauvegarde a réussi
        """
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