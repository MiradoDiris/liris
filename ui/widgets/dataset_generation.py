#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/dataset_generation_panel.py
Panel de génération de datasets avec typologies combinées
"""

import json
import os
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QComboBox, QProgressBar, QScrollArea,
    QFrame, QGroupBox, QCheckBox, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush
from ui.styles.theme import Theme
from utils.logger import logger


def get_dropdown_svg_path():
    """Retourne le chemin vers l'icône dropdown SVG"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.dirname(current_dir)
    svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
    svg_path = os.path.normpath(svg_path)
    return svg_path.replace('\\', '/')


class GradientProgressBar(QProgressBar):
    """Barre de progression avec dégradé personnalisé"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(30)
        
    def paintEvent(self, event):
        """Dessine la barre avec le dégradé PRIMARY -> SECONDARY"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fond
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 245, 245))
        painter.drawRoundedRect(self.rect(), 4, 4)
        
        # Calcul de la largeur remplie
        if self.maximum() > 0:
            progress = self.value() / self.maximum()
            filled_width = int(self.width() * progress)
            
            if filled_width > 0:
                # Dégradé vertical PRIMARY -> SECONDARY
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0, QColor(Theme.PRIMARY_COLOR))
                gradient.setColorAt(1, QColor(Theme.SECONDARY_COLOR))
                
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(0, 0, filled_width, self.height(), 4, 4)
        
        # Texte
        painter.setPen(QColor(255, 255, 255) if self.value() > self.maximum() / 2 else QColor(100, 100, 100))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class GradientButton(QPushButton):
    """Bouton avec dégradé personnalisé"""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        # Style avec dégradé
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:pressed {{
                background: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)


class CombinationVisualizer(QWidget):
    """Widget de visualisation des combinaisons de typologies"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.combinations = []
        self.completed = []
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Zone de scroll pour les combinaisons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        self.combinations_widget = QWidget()
        self.combinations_layout = QVBoxLayout(self.combinations_widget)
        self.combinations_layout.setSpacing(8)
        scroll.setWidget(self.combinations_widget)
        
        layout.addWidget(scroll)
        
    def set_combinations(self, combinations):
        """Définit les combinaisons à afficher"""
        self.combinations = combinations
        self.completed = [False] * len(combinations)
        self._update_display()
        
    def mark_completed(self, index):
        """Marque une combinaison comme complétée"""
        if 0 <= index < len(self.completed):
            self.completed[index] = True
            self._update_display()
            
    def _update_display(self):
        """Met à jour l'affichage des combinaisons"""
        # Nettoyer l'affichage précédent
        while self.combinations_layout.count():
            item = self.combinations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Afficher chaque combinaison
        for i, combo in enumerate(self.combinations):
            combo_frame = QFrame()
            combo_frame.setFrameShape(QFrame.StyledPanel)
            
            is_completed = self.completed[i] if i < len(self.completed) else False
            
            if is_completed:
                combo_frame.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        border-radius: 6px;
                        padding: 10px;
                    }}
                """)
                text_color = "white"
            else:
                combo_frame.setStyleSheet("""
                    QFrame {
                        background: #F5F5F5;
                        border-radius: 6px;
                        padding: 10px;
                    }
                """)
                text_color = "#333333"
            
            combo_layout = QHBoxLayout(combo_frame)
            
            # Numéro
            num_label = QLabel(f"#{i+1}")
            num_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            num_label.setStyleSheet(f"color: {text_color};")
            num_label.setFixedWidth(40)
            combo_layout.addWidget(num_label)
            
            # Détails de la combinaison
            details = " → ".join([f"{k}: {v}" for k, v in combo.items()])
            detail_label = QLabel(details)
            detail_label.setFont(QFont("Segoe UI", 9))
            detail_label.setStyleSheet(f"color: {text_color};")
            detail_label.setWordWrap(True)
            combo_layout.addWidget(detail_label, 1)
            
            # Icône de statut
            status_label = QLabel("✓" if is_completed else "○")
            status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            status_label.setStyleSheet(f"color: {text_color};")
            combo_layout.addWidget(status_label)
            
            self.combinations_layout.addWidget(combo_frame)
        
        self.combinations_layout.addStretch()


class DatasetGenerationPanel(QWidget):
    """Panel principal de génération de datasets"""
    
    generation_started = pyqtSignal(str)  # project_name
    generation_completed = pyqtSignal(str, str)  # project_name, output_path
    generation_failed = pyqtSignal(str, str)  # project_name, error
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.database = None
        self.current_project = None
        self.combinations = []
        self.dropdown_svg = get_dropdown_svg_path()
        self._init_ui()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Zone de scroll principale
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(20)
        
        # === COLONNE GAUCHE (25% de largeur) ===
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setSpacing(20)
        
        # Section 1: Sélection du projet
        project_section = self._create_project_section()
        left_layout.addWidget(project_section)
        
        # Section 2: Configuration de génération
        config_section = self._create_config_section()
        left_layout.addWidget(config_section)
        
        # Section 3: Éditeur de prompt
        prompt_section = self._create_prompt_section()
        left_layout.addWidget(prompt_section, 1)  # Stretch pour prendre l'espace
        
        content_layout.addWidget(left_column, 1)  # 1 part (25%)
        
        # === COLONNE DROITE (75% de largeur) ===
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setSpacing(20)
        
        # Visualisation des combinaisons (sans titre)
        self.visualizer = CombinationVisualizer()
        viz_group = self._create_group("", self.visualizer)  # Titre vide
        right_layout.addWidget(viz_group, 1)
        
        content_layout.addWidget(right_column, 3)  # 3 parts (75%)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Barre de progression
        self.progress_bar = GradientProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Boutons d'action
        actions = self._create_actions()
        main_layout.addWidget(actions)
        

    def _create_project_section(self):
        """Crée la section de sélection du projet"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        label = QLabel("Projet:")
        label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(label)
        
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(40)
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self.project_combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 35px;
                background: white;
                font-size: 11pt;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QComboBox:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #E0E0E0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
            }}
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 18px;
                height: 18px;
            }}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border: none;
                margin: 2px 4px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #F0F0F0;
            }}
            QComboBox QAbstractItemView::indicator {{
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView::indicator:checked {{
                image: none;
            }}
        """)
        layout.addWidget(self.project_combo)
        
        return self._create_group("Sélection du projet", widget)
        
    def _create_config_section(self):
        """Crée la section de configuration"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Sélection du batch
        batch_select_label = QLabel("Batch à générer:")
        batch_select_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(batch_select_label)
        
        self.batch_select_combo = QComboBox()
        self.batch_select_combo.setMinimumHeight(40)
        self.batch_select_combo.addItem("-- Tous les batchs --", "all")
        self.batch_select_combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 35px;
                background: white;
                font-size: 10pt;
            }}
            QComboBox:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #E0E0E0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
            }}
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 18px;
                height: 18px;
            }}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border: none;
                margin: 2px 4px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #F0F0F0;
            }}
            QComboBox QAbstractItemView::indicator {{
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView::indicator:checked {{
                image: none;
            }}
        """)
        layout.addWidget(self.batch_select_combo)
        
        # Nombre de lots
        batch_label = QLabel("Nombre de lots:")
        batch_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(batch_label)
        
        self.batch_spin = QSpinBox()
        self.batch_spin.setMinimum(1)
        self.batch_spin.setMaximum(1000)
        self.batch_spin.setValue(10)
        self.batch_spin.setMinimumHeight(40)
        self.batch_spin.valueChanged.connect(self._on_batch_count_changed)
        self.batch_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                font-size: 10pt;
            }}
            QSpinBox:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QSpinBox:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                border: none;
                background: {Theme.PRIMARY_COLOR};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {Theme.SECONDARY_COLOR};
            }}
            QSpinBox::up-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid white;
            }}
            QSpinBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
            }}
        """)
        layout.addWidget(self.batch_spin)
        
        # Format de sortie
        format_label = QLabel("Format de sortie:")
        format_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "JSONL", "Parquet"])
        self.format_combo.setMinimumHeight(40)
        self.format_combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 35px;
                background: white;
                font-size: 10pt;
            }}
            QComboBox:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #E0E0E0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
            }}
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 18px;
                height: 18px;
            }}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border: none;
                margin: 2px 4px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #F0F0F0;
            }}
            QComboBox QAbstractItemView::indicator {{
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView::indicator:checked {{
                image: none;
            }}
        """)
        layout.addWidget(self.format_combo)
        
        return self._create_group("Configuration", widget)
        
    def _create_prompt_section(self):
        """Crée la section d'édition du prompt"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Éditeur de prompt
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setMinimumHeight(200)
        self.prompt_editor.setPlaceholderText(
            "Exemple:\n\n"
            "Générez des exemples d'entraînement basés sur les typologies suivantes:\n"
            "{typologie}\n\n"
            "Format attendu: {'input': '...', 'output': '...'}"
        )
        self.prompt_editor.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 2px solid """ + Theme.PRIMARY_COLOR + """;
            }
        """)
        layout.addWidget(self.prompt_editor)
        
        return self._create_group("Prompt de génération", widget)
        
    def _create_actions(self):
        """Crée la barre d'actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        
        layout.addStretch()
        
        # Bouton Générer
        self.generate_btn = GradientButton("Générer le Dataset")
        self.generate_btn.clicked.connect(self._on_generate)
        self.generate_btn.setMinimumWidth(200)
        layout.addWidget(self.generate_btn)
        
        # Bouton Exporter
        self.export_btn = GradientButton("Exporter")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
        return widget
        
    def _create_group(self, title, widget):
        """Crée un groupe avec titre"""
        group = QGroupBox(title)
        group.setFont(QFont("Segoe UI", 11, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)
        
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        
        return group
        
    def set_conductor(self, conductor):
        """Définit le conductor"""
        self.conductor = conductor
        
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        self._load_projects()
        
    def _load_projects(self):
        """Charge les projets disponibles"""
        if not self.database:
            return
            
        try:
            projects = self.database.get_all_projects()
            self.project_combo.clear()
            self.project_combo.addItem("-- Sélectionner un projet --", None)
            
            for project in projects:
                self.project_combo.addItem(project['name'], project)
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement des projets: {str(e)}")
            
    def _on_project_changed(self, project_name):
        """Gère le changement de projet"""
        if project_name == "-- Sélectionner un projet --":
            self.current_project = None
            self.combinations = []
            self.visualizer.set_combinations([])
            return
            
        try:
            # Charger le projet complet
            project_data = self.database.get_dataset_projet(project_name)
            if project_data:
                self.current_project = project_data
                self._generate_combinations()
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement du projet: {str(e)}")
            QMessageBox.critical(self, "Erreur", f"Impossible de charger le projet:\n\n{str(e)}")
            
    def _generate_combinations(self):
        """Génère toutes les combinaisons de typologies"""
        if not self.current_project:
            return
            
        combinations = []
        typologies = self.current_project.get('typologies', [])
        
        # Générer les combinaisons (logique simplifiée)
        for typo in typologies:
            for cluster in typo.get('taxonomy_clusters', []):
                for root in cluster.get('root_labels', []):
                    for parent in root.get('parent_labels', []):
                        combination = {
                            'typologie': typo['name'],
                            'cluster': cluster['name'],
                            'root': root['name'],
                            'parent': parent['name']
                        }
                        combinations.append(combination)
        
        self.combinations = combinations
        self.visualizer.set_combinations(combinations)
        
        # Mettre à jour le combo de sélection de batch
        self._update_batch_combo(len(combinations))
        
        logger.info(f"{len(combinations)} combinaisons générées")
        
    def _update_batch_combo(self, total_combinations):
        """Met à jour le combo de sélection de batch selon le nombre total de combinaisons"""
        self.batch_select_combo.clear()
        self.batch_select_combo.addItem("-- Tous les batchs --", "all")
        
        batch_count = self.batch_spin.value()
        
        if total_combinations > 0 and batch_count > 0:
            items_per_batch = max(1, total_combinations // batch_count)
            
            for i in range(1, batch_count + 1):
                start_idx = (i - 1) * items_per_batch + 1
                end_idx = min(i * items_per_batch, total_combinations)
                
                # Pour le dernier batch, inclure les éléments restants
                if i == batch_count:
                    end_idx = total_combinations
                    
                label = f"Batch {i} (Items {start_idx}-{end_idx})"
                self.batch_select_combo.addItem(label, i)
        
        logger.info(f"Combo de batch mis à jour: {batch_count} batchs pour {total_combinations} combinaisons")
        
    def _on_batch_count_changed(self, value):
        """Gère le changement du nombre de batchs"""
        if self.combinations:
            self._update_batch_combo(len(self.combinations))
        
    def _on_generate(self):
        """Lance la génération du dataset"""
        if not self.current_project or not self.combinations:
            QMessageBox.warning(self, "Attention", "Veuillez d'abord sélectionner un projet")
            return
            
        if not self.prompt_editor.toPlainText().strip():
            QMessageBox.warning(self, "Attention", "Veuillez rédiger un prompt de génération")
            return
        
        # Récupérer le batch sélectionné
        selected_batch = self.batch_select_combo.currentData()
        
        if selected_batch == "all":
            message = f"Générer {len(self.combinations)} exemples en {self.batch_spin.value()} lots ?"
        else:
            batch_idx = selected_batch - 1
            items_per_batch = max(1, len(self.combinations) // self.batch_spin.value())
            start_idx = batch_idx * items_per_batch
            end_idx = min((batch_idx + 1) * items_per_batch, len(self.combinations))
            if selected_batch == self.batch_spin.value():
                end_idx = len(self.combinations)
            count = end_idx - start_idx
            message = f"Générer le batch {selected_batch} ({count} exemples) ?"
            
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirmation",
            message,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Démarrer la génération
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.combinations))
        self.progress_bar.setValue(0)
        
        self.generation_started.emit(self.current_project['nom'])
        
        # TODO: Implémenter la génération asynchrone avec l'IA
        # Pour l'instant, simulation
        QMessageBox.information(self, "Génération", "La génération du dataset va démarrer...")
        
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
    def _on_export(self):
        """Exporte le dataset généré"""
        if not self.current_project:
            return
            
        format_ext = {
            "JSON": ".json",
            "CSV": ".csv",
            "JSONL": ".jsonl",
            "Parquet": ".parquet"
        }
        
        ext = format_ext.get(self.format_combo.currentText(), ".json")
        filename = f"dataset_{self.current_project['nom']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le dataset",
            filename,
            f"Fichiers {self.format_combo.currentText()} (*{ext})"
        )
        
        if filepath:
            # TODO: Implémenter l'export réel
            QMessageBox.information(self, "Export", f"Dataset exporté vers:\n{filepath}")
            self.generation_completed.emit(self.current_project['nom'], filepath)