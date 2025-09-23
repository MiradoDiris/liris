#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Widget de génération de datasets avec système de templates
"""

import os
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QTextEdit, QPushButton, 
                             QScrollArea, QFrame, QMessageBox, QSplitter,
                             QTabWidget, QFormLayout, QSpinBox, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextOption

from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.template_manager import template_manager


class GenerationWidget(QWidget):
    """Widget pour la génération de datasets avec templates"""
    
    # Signal émis lorsqu'un dataset est généré
    dataset_generated = pyqtSignal(dict, str)  # dataset, format
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataset = None
        self.current_format = "JSON"
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(PlatformConfigStyle.SPACING)
        main_layout.setContentsMargins(PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN)
        
        # Titre principal
        title_label = QLabel("Génération de Datasets avec Templates")
        title_label.setStyleSheet(PlatformConfigStyle.get_title_style())
        main_layout.addWidget(title_label)
        
        # Zone d'explication
        explanation_label = QLabel(
            "Générez des datasets dans différents formats (JSON, CSV, XML, YAML, Texte) "
            "avec des templates configurables. Configurez les options de formatage et "
            "prévisualisez le résultat avant export."
        )
        explanation_label.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation_label.setWordWrap(True)
        main_layout.addWidget(explanation_label)
        
        # Splitter pour une disposition flexible
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel de configuration (gauche)
        config_panel = self.create_config_panel()
        splitter.addWidget(config_panel)
        
        # Panel de prévisualisation (droite)
        preview_panel = self.create_preview_panel()
        splitter.addWidget(preview_panel)
        
        # Définir les proportions initiales
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter, 1)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.generate_example_btn = QPushButton("Générer un Exemple")
        self.generate_example_btn.clicked.connect(self.generate_example)
        button_layout.addWidget(self.generate_example_btn)
        
        self.export_btn = QPushButton("Exporter le Dataset")
        self.export_btn.clicked.connect(self.export_dataset)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(button_layout)
        
    def create_config_panel(self):
        """Crée le panel de configuration des templates"""
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        
        # Groupe de sélection du format
        format_group = QGroupBox("Format de Sortie")
        format_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        format_layout = QFormLayout(format_group)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(template_manager.get_supported_formats())
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        format_layout.addRow("Format:", self.format_combo)
        
        layout.addWidget(format_group)
        
        # Options spécifiques au format (dans un QTabWidget)
        self.options_tabs = QTabWidget()
        self.options_tabs.setStyleSheet(PlatformConfigStyle.get_tabs_style())
        self.create_format_options()
        layout.addWidget(self.options_tabs)
        
        # Configuration du template
        template_group = QGroupBox("Configuration du Template")
        template_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        template_layout = QVBoxLayout(template_group)
        
        self.template_config_edit = QTextEdit()
        self.template_config_edit.setPlaceholderText(
            '{\n  "pretty_print": true,\n  "include_metadata": true\n}'
        )
        self.template_config_edit.setMaximumHeight(150)
        template_layout.addWidget(self.template_config_edit)
        
        # Bouton pour réinitialiser la configuration
        reset_btn = QPushButton("Configuration par Défaut")
        reset_btn.clicked.connect(self.reset_template_config)
        template_layout.addWidget(reset_btn)
        
        layout.addWidget(template_group)
        layout.addStretch()
        
        return config_widget
    
    def create_format_options(self):
        """Crée les options spécifiques à chaque format"""
        # Options JSON
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        
        self.json_pretty_print = QCheckBox("Affichage structuré (indentation)")
        self.json_pretty_print.setChecked(True)
        self.json_pretty_print.toggled.connect(self.update_template_config)
        json_layout.addWidget(self.json_pretty_print)
        
        self.json_include_metadata = QCheckBox("Inclure les métadonnées")
        self.json_include_metadata.setChecked(True)
        self.json_include_metadata.toggled.connect(self.update_template_config)
        json_layout.addWidget(self.json_include_metadata)
        
        json_layout.addStretch()
        self.options_tabs.addTab(json_widget, "JSON")
        
        # Options CSV
        csv_widget = QWidget()
        csv_layout = QVBoxLayout(csv_widget)
        
        self.csv_include_headers = QCheckBox("Inclure les en-têtes")
        self.csv_include_headers.setChecked(True)
        self.csv_include_headers.toggled.connect(self.update_template_config)
        csv_layout.addWidget(self.csv_include_headers)
        
        csv_layout.addStretch()
        self.options_tabs.addTab(csv_widget, "CSV")
        
        # Options XML
        xml_widget = QWidget()
        xml_layout = QVBoxLayout(xml_widget)
        
        self.xml_pretty_print = QCheckBox("Affichage structuré (indentation)")
        self.xml_pretty_print.setChecked(True)
        self.xml_pretty_print.toggled.connect(self.update_template_config)
        xml_layout.addWidget(self.xml_pretty_print)
        
        xml_layout.addStretch()
        self.options_tabs.addTab(xml_widget, "XML")
        
        # Options YAML
        yaml_widget = QWidget()
        yaml_layout = QVBoxLayout(yaml_widget)
        
        self.yaml_include_metadata = QCheckBox("Inclure les métadonnées")
        self.yaml_include_metadata.setChecked(True)
        self.yaml_include_metadata.toggled.connect(self.update_template_config)
        yaml_layout.addWidget(self.yaml_include_metadata)
        
        yaml_layout.addStretch()
        self.options_tabs.addTab(yaml_widget, "YAML")
        
        # Options Texte
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        
        self.text_include_timestamp = QCheckBox("Inclure l'horodatage")
        self.text_include_timestamp.setChecked(True)
        self.text_include_timestamp.toggled.connect(self.update_template_config)
        text_layout.addWidget(self.text_include_timestamp)
        
        text_layout.addStretch()
        self.options_tabs.addTab(text_widget, "Texte")
    
    def create_preview_panel(self):
        """Crée le panel de prévisualisation"""
        preview_widget = QWidget()
        layout = QVBoxLayout(preview_widget)
        
        # Titre de prévisualisation
        preview_label = QLabel("Prévisualisation")
        preview_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #A23B2D;
            padding: 8px;
            background-color: #F9F6F6;
            border-radius: 4px;
            margin-bottom: 5px;
        """)
        layout.addWidget(preview_label)
        
        # Éditeur de prévisualisation
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFont(QFont("Courier", 10))
        self.preview_edit.setWordWrapMode(QTextOption.NoWrap)
        
        # Appliquer un style spécifique pour la prévisualisation
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2B2B2B;
                color: #FFFFFF;
                font-family: 'Courier New';
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        
        layout.addWidget(self.preview_edit)
        
        # Statistiques
        stats_group = QGroupBox("Statistiques")
        stats_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        stats_layout = QHBoxLayout(stats_group)
        
        self.stats_label = QLabel("Aucun dataset généré")
        self.stats_label.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        return preview_widget
    
    def apply_styles(self):
        """Applique les styles aux composants"""
        # Styles pour les combobox
        self.format_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        
        # Styles pour les boutons
        button_style = PlatformConfigStyle.get_button_style()
        self.generate_example_btn.setStyleSheet(button_style)
        self.export_btn.setStyleSheet(button_style)
        
        # Style pour l'éditeur de configuration
        self.template_config_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
    
    def on_format_changed(self, format_type):
        """Gère le changement de format"""
        self.current_format = format_type
        self.update_template_config()
        
        # Mettre à jour l'onglet actif
        format_index = template_manager.get_supported_formats().index(format_type)
        self.options_tabs.setCurrentIndex(format_index)
        
        # Régénérer la prévisualisation si un dataset existe
        if self.current_dataset:
            self.update_preview()
    
    def update_template_config(self):
        """Met à jour la configuration du template basée sur les contrôles d'interface"""
        format_type = self.current_format
        config = {}
        
        if format_type == "JSON":
            config = {
                "pretty_print": self.json_pretty_print.isChecked(),
                "include_metadata": self.json_include_metadata.isChecked()
            }
        elif format_type == "CSV":
            config = {
                "include_headers": self.csv_include_headers.isChecked()
            }
        elif format_type == "XML":
            config = {
                "pretty_print": self.xml_pretty_print.isChecked()
            }
        elif format_type == "YAML":
            config = {
                "include_metadata": self.yaml_include_metadata.isChecked()
            }
        elif format_type == "Texte":
            config = {
                "include_timestamp": self.text_include_timestamp.isChecked()
            }
        
        # Mettre à jour l'éditeur de configuration
        self.template_config_edit.setPlainText(json.dumps(config, indent=2))
        
        # Régénérer la prévisualisation si un dataset existe
        if self.current_dataset:
            self.update_preview()
    
    def reset_template_config(self):
        """Réinitialise la configuration du template aux valeurs par défaut"""
        default_config = template_manager.default_templates.get(self.current_format, {})
        self.template_config_edit.setPlainText(json.dumps(default_config, indent=2))
        self.update_ui_from_config()
    
    def update_ui_from_config(self):
        """Met à jour l'interface utilisateur à partir de la configuration JSON"""
        try:
            config_text = self.template_config_edit.toPlainText()
            if config_text.strip():
                config = json.loads(config_text)
                
                # Mettre à jour les contrôles selon le format actuel
                format_type = self.current_format
                if format_type == "JSON":
                    self.json_pretty_print.setChecked(config.get("pretty_print", True))
                    self.json_include_metadata.setChecked(config.get("include_metadata", True))
                elif format_type == "CSV":
                    self.csv_include_headers.setChecked(config.get("include_headers", True))
                elif format_type == "XML":
                    self.xml_pretty_print.setChecked(config.get("pretty_print", True))
                elif format_type == "YAML":
                    self.yaml_include_metadata.setChecked(config.get("include_metadata", True))
                elif format_type == "Texte":
                    self.text_include_timestamp.setChecked(config.get("include_timestamp", True))
                    
        except json.JSONDecodeError:
            # Ignorer les erreurs de parsing pour l'instant
            pass
    
    def generate_example(self):
        """Génère un exemple de dataset"""
        try:
            # Récupérer la configuration du template
            config_text = self.template_config_edit.toPlainText()
            config = json.loads(config_text) if config_text.strip() else {}
            
            # Valider la configuration
            if not template_manager.validate_template_config(self.current_format, config):
                QMessageBox.warning(self, "Configuration invalide", 
                                  "La configuration du template n'est pas valide pour ce format.")
                return
            
            # Générer l'exemple
            example_content = template_manager.generate_example(self.current_format, config)
            self.current_dataset = example_content
            
            # Mettre à jour la prévisualisation
            self.update_preview()
            
            # Activer le bouton d'export
            self.export_btn.setEnabled(True)
            
            # Mettre à jour les statistiques
            self.update_stats(example_content)
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur de génération", 
                               f"Erreur lors de la génération de l'exemple:\n{str(e)}")
    
    def update_preview(self):
        """Met à jour la prévisualisation"""
        if not self.current_dataset:
            return
            
        try:
            # Formater le dataset selon le format actuel
            config_text = self.template_config_edit.toPlainText()
            config = json.loads(config_text) if config_text.strip() else {}
            
            # Pour l'exemple, on affiche directement le contenu généré
            # Dans une implémentation réelle, on formaterait le dataset actuel
            self.preview_edit.setPlainText(str(self.current_dataset))
            
        except Exception as e:
            self.preview_edit.setPlainText(f"Erreur de formatage: {str(e)}")
    
    def update_stats(self, content):
        """Met à jour les statistiques"""
        if content:
            char_count = len(str(content))
            line_count = str(content).count('\n') + 1
            self.stats_label.setText(
                f"Caractères: {char_count} | Lignes: {line_count} | Format: {self.current_format}"
            )
        else:
            self.stats_label.setText("Aucun dataset généré")
    
    def export_dataset(self):
        """Exporte le dataset généré"""
        if not self.current_dataset:
            QMessageBox.warning(self, "Aucun dataset", "Aucun dataset à exporter.")
            return
        
        try:
            # Dans une implémentation réelle, on sauvegarderait le fichier
            # Pour l'instant, on affiche un message de confirmation
            QMessageBox.information(self, "Export réussi", 
                                  f"Dataset exporté au format {self.current_format} avec succès!")
            
            # Émettre le signal pour d'autres composants
            self.dataset_generated.emit({"content": self.current_dataset}, self.current_format)
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'export", 
                               f"Erreur lors de l'export:\n{str(e)}")
    
    def set_dataset(self, dataset: dict):
        """Définit le dataset à formater"""
        self.current_dataset = dataset
        self.export_btn.setEnabled(True)
        self.update_preview()
        self.update_stats(str(dataset))


# Test de la classe
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Tester le widget
    widget = GenerationWidget()
    widget.show()
    
    sys.exit(app.exec_())