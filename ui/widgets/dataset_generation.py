#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Generation Panel - Improved 3-column layout
Left: Project & Config | Center: Prompt Editor | Right: Combinations Visualizer
"""

import json
import os
from datetime import datetime
from typing import Dict
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QComboBox, QProgressBar, QScrollArea,
    QFrame, QGroupBox, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush
import sys
from pathlib import Path
from typing import Dict, Any
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager
import qtawesome as qta
from PyQt5.QtGui import QPainter


def get_dropdown_svg_path():
    """Retourne le chemin vers l'icône dropdown SVG"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.dirname(current_dir)
    svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
    svg_path = os.path.normpath(svg_path)
    return svg_path.replace('\\', '/')

class CollapsibleSection(QWidget):
    """Section collapsible avec chevron - VERSION RESPONSIVE"""
    
    def __init__(self, title="Section", parent=None):
        super().__init__(parent)
        self.is_collapsed = True
        self.section_title = title
        
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header avec chevron
        self.header = QPushButton()
        self.header.setMinimumHeight(40)  # ✅ Hauteur minimum
        self.header.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.header.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
        """)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        self.update_header_text(title)
        
        layout.addWidget(self.header)
        
        # Content
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content.setVisible(False)
        self.content.setMaximumHeight(0)
        self.content.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Maximum
        )
        self.content.setStyleSheet("""
            QWidget {
                background: #F8F9FA;
                border: 2px solid #E0E0E0;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)
        
        layout.addWidget(self.content)
        
    def update_header_text(self, title):
        """Met à jour le texte du header avec chevron"""
        chevron = "▲" if not self.is_collapsed else "▼"
        self.header.setText(f"{chevron}  {title}")
        self.section_title = title  # Mettre à jour le titre stocké
        
    def toggle(self):
        """Bascule l'état collapsed/expanded"""
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self.update_header_text(self.section_title)  # Utiliser le titre stocké
        
        # Animation
        if hasattr(self, 'animation'):
            self.animation.stop()
        
        self.animation = QPropertyAnimation(self.content, b"maximumHeight")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        if self.is_collapsed:
            # Fermeture
            self.animation.setStartValue(self.content.sizeHint().height())
            self.animation.setEndValue(0)
        else:
            # Ouverture
            self.animation.setStartValue(0)
            # Calculer la hauteur nécessaire
            target_height = self.content.sizeHint().height()
            if target_height < 100:  # Hauteur minimum raisonnable
                target_height = 200
            self.animation.setEndValue(target_height)
        
        self.animation.start()
        
    def add_widget(self, widget):
        """Ajoute un widget au contenu"""
        self.content_layout.addWidget(widget)
        
    def set_title(self, title):
        """Définit le titre"""
        self.section_title = title
        self.update_header_text(title)


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
    """Widget de visualisation - LISTE UNIQUEMENT (sans camembert)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.combinations = []
        self.completed = []
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # === LISTE DÉFILANTE UNIQUEMENT (PAS DE CAMEMBERT) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        self.combinations_widget = QWidget()
        self.combinations_layout = QVBoxLayout(self.combinations_widget)
        self.combinations_layout.setSpacing(8)
        self.combinations_layout.setAlignment(Qt.AlignTop)
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
        """Met à jour l'affichage - VERSION AVEC MASTER"""
        # Vider le layout
        while self.combinations_layout.count():
            item = self.combinations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Si aucune combinaison, afficher un message
        if not self.combinations:
            empty_label = QLabel("Aucune combinaison à afficher.\nSélectionnez un batch pour commencer.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; font-style: italic; padding: 50px;")
            self.combinations_layout.addWidget(empty_label)
            return
        
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
            
            combo_layout = QVBoxLayout(combo_frame)
            
            # En-tête : Numéro + Master + Samples
            header_layout = QHBoxLayout()
            
            num_label = QLabel(f"#{i+1}")
            num_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            num_label.setStyleSheet(f"color: {text_color};")
            num_label.setFixedWidth(40)
            header_layout.addWidget(num_label)
            
            # AFFICHAGE DU MASTER
            master_name = combo.get('master', 'N/A')
            master_label = QLabel(f"Master: {master_name}")
            master_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            master_label.setStyleSheet(f"color: {text_color}; text-decoration: underline;")
            header_layout.addWidget(master_label)
            
            header_layout.addStretch()
            
            # Nombre de contextes et samples
            nb_contexts = len(combo.get('contexts', []))
            nb_samples = combo.get('nb_samples', 1)
            
            info_label = QLabel(f"{nb_contexts} contexte(s) • {nb_samples} sample(s)")
            info_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            info_label.setStyleSheet(f"color: {text_color};")
            header_layout.addWidget(info_label)
            
            # Icône de statut
            status_label = QLabel("✓" if is_completed else "○")
            status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            status_label.setStyleSheet(f"color: {text_color};")
            header_layout.addWidget(status_label)
            
            combo_layout.addLayout(header_layout)
            
            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet(f"background-color: {text_color}; max-height: 1px;")
            combo_layout.addWidget(separator)
            
            # Liste des contextes
            contexts = combo.get('contexts', [])
            for ctx_idx, ctx in enumerate(contexts):
                ctx_label = QLabel(f"  {ctx_idx + 1}. {ctx.get('display', 'N/A')}")
                ctx_label.setFont(QFont("Segoe UI", 8))
                ctx_label.setStyleSheet(f"color: {text_color}; padding-left: 20px;")
                ctx_label.setWordWrap(True)
                combo_layout.addWidget(ctx_label)
            
            self.combinations_layout.addWidget(combo_frame)
        
        self.combinations_layout.addStretch()


class DatasetGenerationPanel(QWidget):
    """Panel principal de génération de datasets - Layout 3 colonnes"""
    
    generation_started = pyqtSignal(str)  # project_name
    generation_completed = pyqtSignal(str, str)  # project_name, output_path
    generation_failed = pyqtSignal(str, str)  # project_name, error
    
    def __init__(self, parent=None, database=None, project_manager=None):
        super().__init__(parent)
        
        # ⚠️ INITIALISATION DE LA DATABASE ET DU MANAGER
        self.conductor = None
        
        # Initialize database and project_manager
        if database is not None:
            self.database = database
            self.db = database
        else:
            self.db = DatasetDatabase()
            self.database = self.db
            
        if project_manager is not None:
            self.project_manager = project_manager
        else:
            self.project_manager = DatasetProjectManager(self.db)
        
        self.current_project = None
        self.current_project_name = None
        self.current_batch_number = None
        self.current_batch_data = None
        self.combinations = []
        self.dropdown_svg = get_dropdown_svg_path()

        self.generation_results = []
        self.generation_metadata = {}
        self.worker = None
        
        # Log d'initialisation
        print("=" * 60)
        print("🚀 INITIALISATION DatasetGenerationPanel")
        print("=" * 60)
        logger.info("🚀 DatasetGenerationPanel initialisé")

        self.primary_color = Theme.PRIMARY_COLOR
        self.secondary_color = Theme.SECONDARY_COLOR
        self.base_height = 800

        # ✅ CORRECTION ICI : D'abord l'UI, ENSUITE le bouton overlay
        self._init_ui()            # Crée self.snippets_container
        self._init_overlay_button() # Utilise self.snippets_container
        
        print("✅ UI initialisée")
        logger.info("✅ UI initialisée")
        
        # Charger les projets si la database est disponible
        if self.database:
            self._load_projects()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur - 3 colonnes RESPONSIVE + Panel Latéral"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Container principal (Scroll + Panel)
        h_container = QWidget()
        h_layout = QHBoxLayout(h_container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ✅ UTILISER UN QSPLITTER POUR LES 3 COLONNES RESPONSIVE
        from PyQt5.QtWidgets import QSplitter

        self.columns_splitter = QSplitter(Qt.Horizontal)
        self.columns_splitter.setHandleWidth(1)
        self.columns_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E0E0E0;
            }
            QSplitter::handle:hover {
                background: #4A90E2;
            }
        """)

        # Zone scrollable pour chaque colonne
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === COLONNE GAUCHE (Responsive) ===
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_column = self._create_left_column()
        left_scroll.setWidget(left_column)
        self.columns_splitter.addWidget(left_scroll)

        # === COLONNE CENTRALE (Responsive) ===
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QFrame.NoFrame)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        center_column = self._create_center_column()
        center_scroll.setWidget(center_column)
        self.columns_splitter.addWidget(center_scroll)

        # === COLONNE DROITE (Responsive) ===
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_column = self._create_right_column()
        right_scroll.setWidget(right_column)
        self.columns_splitter.addWidget(right_scroll)

        # ✅ DÉFINIR LES PROPORTIONS INITIALES (25% - 35% - 40%)
        total_width = 1200  # Largeur de référence
        self.columns_splitter.setSizes([
            int(total_width * 0.25),  # Gauche: 25%
            int(total_width * 0.35),  # Centre: 35%
            int(total_width * 0.40)   # Droite: 40%
        ])

        # ✅ DÉFINIR LES LARGEURS MINIMALES POUR ÉVITER L'ÉCRASEMENT
        left_scroll.setMinimumWidth(250)
        center_scroll.setMinimumWidth(300)
        right_scroll.setMinimumWidth(350)

        h_layout.addWidget(self.columns_splitter)

        # === PANNEAU DE SNIPPETS ===
        self.snippets_container = QWidget()
        self.snippets_container.setFixedWidth(0)
        h_layout.addWidget(self.snippets_container)

        main_layout.addWidget(h_container)

        # ✅ BARRE D'ACTIONS EN BAS (sans progress bar)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(20, 10, 20, 20)

        # ❌ PROGRESS BAR SUPPRIMÉE D'ICI - Maintenant dans la colonne 1

        actions = self._create_actions()
        bottom_layout.addWidget(actions)

        main_layout.addWidget(bottom_widget)

    def _create_left_column(self):
        """Crée la colonne gauche - Projet, Configuration RESPONSIVE + Progress Bar"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # ✅ Padding uniforme

        # Section Projet
        project_section = self._create_project_section()
        layout.addWidget(project_section)

        # Section Configuration
        config_section = self._create_config_section()
        layout.addWidget(config_section)

        # INFO: Affichage des infos du batch sélectionné
        self.batch_info_label = QLabel()
        self.batch_info_label.setWordWrap(True)
        self.batch_info_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        self.batch_info_label.setStyleSheet("""
            QLabel {
                background: #F0F8FF;
                border: 2px solid #4A90E2;
                border-radius: 6px;
                padding: 10px;
                font-size: 9pt;
                color: #333;
            }
        """)
        self.batch_info_label.setVisible(False)
        layout.addWidget(self.batch_info_label)

        layout.addStretch()

        # ✅ BARRE DE PROGRESSION EN BAS DE LA COLONNE 1
        self.progress_bar = GradientProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(self.progress_bar)

        return column
        
    def _create_center_column(self):
        """Crée la colonne centrale - Éditeur de Prompt RESPONSIVE + Bouton Combinaisons"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # ✅ Padding uniforme

        # === CONTEXTE GLOBAL (Collapsible) ===
        self.global_section = CollapsibleSection("Contexte Global du Projet")

        global_info = QLabel("ℹ️ Contexte partagé pour tous les batches du projet")
        global_info.setFont(QFont("Segoe UI", 8))
        global_info.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        global_info.setWordWrap(True)  # ✅ Responsive text
        self.global_section.add_widget(global_info)

        # ✅ Éditeur contexte global - Hauteur adaptative
        self.global_context_editor = QTextEdit()
        self.global_context_editor.setPlaceholderText(
            "Définissez ici le contexte général du projet...\n\n"
            "Exemple:\n"
            "- Objectif du dataset\n"
            "- Domaine d'application\n"
            "- Contraintes générales\n"
            "- Style de sortie attendu"
        )
        self.global_context_editor.setMinimumHeight(100)  # ✅ Min height
        self.global_context_editor.setMaximumHeight(200)  # ✅ Max height
        self.global_context_editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        self.global_context_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        self.global_section.add_widget(self.global_context_editor)

        layout.addWidget(self.global_section)

        # === CONTEXTE LOCAL ===
        local_header = QWidget()
        local_header_layout = QHBoxLayout(local_header)
        local_header_layout.setContentsMargins(0, 0, 0, 0)

        local_title = QLabel("✏️ Prompt Local (Batch)")
        local_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        local_title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        local_header_layout.addWidget(local_title)

        local_info = QLabel("Instructions spécifiques pour ce batch")
        local_info.setFont(QFont("Segoe UI", 8))
        local_info.setStyleSheet("color: #666; font-style: italic;")
        local_info.setWordWrap(True)  # ✅ Responsive text
        local_header_layout.addWidget(local_info)
        local_header_layout.addStretch()

        layout.addWidget(local_header)

        # ✅ Éditeur contexte local - Hauteur adaptative et responsive
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText(
            "Exemple:\n\n"
            "Générez des exemples d'entraînement basés sur les typologies suivantes:\n"
            "{typologie}\n\n"
            "Format attendu: {'input': '...', 'output': '...'}"
        )
        self.prompt_editor.setMinimumHeight(200)  # ✅ Min height
        self.prompt_editor.setMaximumHeight(500)  # ✅ Max height augmentée
        self.prompt_editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.prompt_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        layout.addWidget(self.prompt_editor, 1)  # ✅ Stretch pour utiliser l'espace

        return column
        
    def _create_right_column(self):
        """Crée la colonne droite - Visualiseur de Combinaisons SANS CAMEMBERT"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre avec compteur
        title_layout = QHBoxLayout()
        title = QLabel("Combinaisons à Générer")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        title_layout.addWidget(title)

        self.combo_count_label = QLabel("(0)")
        self.combo_count_label.setFont(QFont("Segoe UI", 10))
        self.combo_count_label.setStyleSheet("color: #666;")
        title_layout.addWidget(self.combo_count_label)
        title_layout.addStretch()

        layout.addLayout(title_layout)

        # Visualiseur (SANS CAMEMBERT - juste la liste)
        self.visualizer = CombinationVisualizer()
        viz_container = QFrame()
        viz_container.setFrameShape(QFrame.StyledPanel)
        viz_container.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(10, 10, 10, 10)
        viz_layout.addWidget(self.visualizer)

        layout.addWidget(viz_container, 1)

        return column

    def _create_project_section(self):
        """Crée la section de sélection du projet - RESPONSIVE + REFRESH"""
        widget = QWidget()
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Groupe encadré
        group = QGroupBox("Sélection du Projet")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
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

        group_layout = QVBoxLayout(group)

        # ✅ EN-TÊTE AVEC BOUTON REFRESH (UNIQUE)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        header_title = QLabel("Projet:")
        header_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        # ✅ BOUTON REFRESH UNIQUE
        self.refresh_btn = QPushButton()
        try:
            import qtawesome as qta
            self.refresh_btn.setIcon(qta.icon('fa5s.sync-alt', color=Theme.PRIMARY_COLOR))
        except:
            self.refresh_btn.setText("🔄")

        self.refresh_btn.setToolTip("Rafraîchir les données depuis la base")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 16px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                border: none;
            }}
            QPushButton:pressed {{
                background: {Theme.SECONDARY_COLOR};
            }}
        """)
        self.refresh_btn.clicked.connect(self._on_refresh_data)
        header_layout.addWidget(self.refresh_btn)

        group_layout.addLayout(header_layout)

        # ✅ 1. COMBO PROJET
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(40)
        self.project_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self._apply_combo_style(self.project_combo)
        group_layout.addWidget(self.project_combo)

        # ✅ 2. COMBO FAMILLE DE BATCH
        family_label = QLabel("Famille de batch:")
        family_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        family_label.setWordWrap(True)
        group_layout.addWidget(family_label)

        self.batch_family_combo = QComboBox()
        self.batch_family_combo.setMinimumHeight(40)
        self.batch_family_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batch_family_combo.currentTextChanged.connect(self._on_batch_family_changed)
        self._apply_combo_style(self.batch_family_combo)
        group_layout.addWidget(self.batch_family_combo)

        # ✅ 3. COMBO BATCH
        batch_label = QLabel("Batch:")
        batch_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_label.setWordWrap(True)
        group_layout.addWidget(batch_label)

        self.batch_combo = QComboBox()
        self.batch_combo.setMinimumHeight(40)
        self.batch_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self._apply_combo_style(self.batch_combo)
        group_layout.addWidget(self.batch_combo)

        layout.addWidget(group)

        return widget
    
    def _on_refresh_data(self):
        """
        Rafraîchit toutes les données depuis la base de données
        Réinitialise les combos et recharge les projets
        """
        try:
            logger.info("\n" + "="*60)
            logger.info("🔄 RAFRAÎCHISSEMENT DES DONNÉES")
            logger.info("="*60)
            
            # ✅ ANIMATION DU BOUTON
            self.refresh_btn.setEnabled(False)
            
            # Effet de rotation
            try:
                import qtawesome as qta
                self.refresh_btn.setIcon(qta.icon('fa5s.spinner', color=Theme.SECONDARY_COLOR, animation=qta.Spin(self.refresh_btn)))
            except:
                self.refresh_btn.setText("⏳")
            
            # ✅ SAUVEGARDER LES SÉLECTIONS ACTUELLES
            current_project = self.project_combo.currentData()
            current_family = self.batch_family_combo.currentData()
            current_batch = self.batch_combo.currentData()
            
            logger.info(f"   📌 Sélections actuelles:")
            logger.info(f"      • Projet: {current_project}")
            logger.info(f"      • Famille: {current_family}")
            logger.info(f"      • Batch: {current_batch}")
            
            # ✅ RÉINITIALISER TOUS LES COMBOS
            self.project_combo.blockSignals(True)
            self.batch_family_combo.blockSignals(True)
            self.batch_combo.blockSignals(True)
            
            self.project_combo.clear()
            self.batch_family_combo.clear()
            self.batch_combo.clear()
            
            # ✅ RECHARGER LES PROJETS
            if not self.database:
                logger.error("   ❌ Database non initialisée")
                QMessageBox.warning(
                    self,
                    "Erreur",
                    "La base de données n'est pas accessible.\nImpossible de rafraîchir."
                )
                return
            
            logger.info("   📂 Rechargement des projets...")
            projects = self.database.get_all_projects()
            
            if not projects:
                logger.warning("   ⚠️ Aucun projet trouvé")
                self.project_combo.addItem("-- Aucun projet disponible --", None)
            else:
                logger.info(f"   ✅ {len(projects)} projet(s) trouvé(s)")
                
                self.project_combo.addItem("-- Sélectionner un projet --", None)
                
                for project in projects:
                    if isinstance(project, dict):
                        project_name = project.get('name', project.get('nom', 'Sans nom'))
                        self.project_combo.addItem(project_name, project_name)
                        logger.debug(f"      ✓ {project_name}")
            
            # ✅ RESTAURER LES SÉLECTIONS SI POSSIBLE
            restore_success = False
            
            if current_project:
                index = self.project_combo.findData(current_project)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                    logger.info(f"   ✅ Projet restauré: {current_project}")
                    restore_success = True
                    
                    # Recharger les familles pour ce projet
                    self._load_batch_families()
                    
                    # Restaurer la famille
                    if current_family:
                        family_index = self.batch_family_combo.findData(current_family)
                        if family_index >= 0:
                            self.batch_family_combo.setCurrentIndex(family_index)
                            logger.info(f"   ✅ Famille restaurée: {current_family}")
                            
                            # Recharger les batches
                            self._load_batches_by_family(current_family)
                            
                            # Restaurer le batch
                            if current_batch:
                                batch_index = self.batch_combo.findData(current_batch)
                                if batch_index >= 0:
                                    self.batch_combo.setCurrentIndex(batch_index)
                                    logger.info(f"   ✅ Batch restauré: {current_batch}")
            
            # ✅ RÉACTIVER LES SIGNAUX
            self.project_combo.blockSignals(False)
            self.batch_family_combo.blockSignals(False)
            self.batch_combo.blockSignals(False)
            
            # ✅ MESSAGE DE SUCCÈS (QMESSAGEBOX UNIQUEMENT)
            if restore_success:
                msg = f"✅ Données rafraîchies avec succès!\n\n"
                msg += f"Sélections restaurées:\n"
                msg += f"• Projet: {current_project}\n"
                if current_family:
                    msg += f"• Famille: {current_family}\n"
                if current_batch:
                    msg += f"• Batch: {current_batch}"
            else:
                msg = f"✅ Données rafraîchies avec succès!\n\n"
                msg += f"{len(projects) if projects else 0} projet(s) disponible(s)"
            
            QMessageBox.information(
                self,
                "Rafraîchissement réussi",
                msg
            )
            
            logger.info("="*60)
            logger.info("✅ Rafraîchissement terminé")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du rafraîchissement: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            QMessageBox.critical(
                self,
                "Erreur de rafraîchissement",
                f"Impossible de rafraîchir les données:\n\n{str(e)}"
            )
        
        finally:
            # ✅ RÉACTIVER LE BOUTON
            self.refresh_btn.setEnabled(True)
            try:
                import qtawesome as qta
                self.refresh_btn.setIcon(qta.icon('fa5s.sync-alt', color=Theme.PRIMARY_COLOR))
            except:
                self.refresh_btn.setText("🔄")
        
    def _create_config_section(self):
        """Crée la section de configuration - RESPONSIVE"""
        widget = QWidget()
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Groupe encadré
        group = QGroupBox("Configuration")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
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

        group_layout = QVBoxLayout(group)

        # ✅ LINEEDIT NOMBRE DE BATCHES - RESPONSIVE
        batches_label = QLabel("Nombre de batches à traiter:")
        batches_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batches_label.setWordWrap(True)
        group_layout.addWidget(batches_label)

        self.batches_input = QtWidgets.QLineEdit()
        self.batches_input.setPlaceholderText("Nombre de batches...")
        self.batches_input.setText("1")
        self.batches_input.setMinimumHeight(40)
        self.batches_input.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batches_input.setValidator(QtGui.QIntValidator(1, 100))
        self.batches_input.setAlignment(Qt.AlignCenter)
        self._apply_lineedit_style(self.batches_input)
        group_layout.addWidget(self.batches_input)

        # Info
        info_label = QLabel("ℹ️ Le nombre de samples par combinaison\nest défini dans le batch")
        info_label.setFont(QFont("Segoe UI", 8))
        info_label.setStyleSheet("color: #666; font-style: italic;")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setWordWrap(True)
        group_layout.addWidget(info_label)

        # ✅ COMBO FORMAT - RESPONSIVE
        format_label = QLabel("Format de sortie:")
        format_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        format_label.setWordWrap(True)
        group_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "JSONL", "Parquet"])
        self.format_combo.setMinimumHeight(40)
        self.format_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self._apply_combo_style(self.format_combo)
        group_layout.addWidget(self.format_combo)

        layout.addWidget(group)

        return widget
    
    def _apply_lineedit_style(self, lineedit):
        """Applique le style aux champs de texte"""
        lineedit.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px 15px;
                background: white;
                font-size: 11pt;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QLineEdit:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.SECONDARY_COLOR};
                background: #FAFAFA;
            }}
            QLineEdit::placeholder {{
                color: #AAAAAA;
                font-weight: normal;
                font-style: italic;
            }}
        """)
        
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
        
    def _apply_combo_style(self, combo):
        """Applique le style aux combobox"""
        combo.setStyleSheet(f"""
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
        """)
        
    def set_conductor(self, conductor):
        """Définit le conductor"""
        self.conductor = conductor
        logger.info(f"🎼 Conductor défini: {conductor}")
        
    def set_database(self, database):
        """Définit la base de données"""
        logger.info(f"💾 set_database appelé avec: {database}")
        self.database = database
        
        if database is None:
            logger.warning("⚠️ Database est None!")
            return
            
        self._load_projects()
        logger.info("✅ set_database terminé")
        
    def set_project_manager(self, project_manager):
        """Définit le project manager"""
        self.project_manager = project_manager
        logger.info(f"📋 Project Manager défini: {project_manager}")
        
    def _load_projects(self):
        """Charge les projets disponibles"""
        logger.info("📋 _load_projects démarré")
        
        if not self.database:
            logger.error("❌ Database non initialisée")
            return
            
        try:
            projects = self.database.get_all_projects()
            logger.info(f"📦 {len(projects) if projects else 0} projet(s) trouvé(s)")
            
            self.project_combo.clear()
            self.project_combo.addItem("-- Sélectionner un projet --", None)
            
            for project in projects:
                if isinstance(project, dict):
                    project_name = project.get('name', project.get('nom', 'Sans nom'))
                    self.project_combo.addItem(project_name, project_name)
                    logger.debug(f"✓ Projet ajouté: {project_name}")
            
            logger.info(f"✅ {self.project_combo.count() - 1} projet(s) chargé(s)")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des projets: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
    def _on_project_changed(self, project_name):
        """Gère le changement de projet"""
        logger.info(f"🔄 Changement de projet: {project_name}")

        # Reset si sélection vide
        if project_name == "-- Sélectionner un projet --" or not project_name:
            self.current_project = None
            self.current_project_name = None
            self.current_batch_number = None
            self.current_batch_data = None
            self.combinations = []
            self.batch_family_combo.clear()
            self.batch_family_combo.addItem("-- Aucun projet sélectionné --", None)
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Aucun projet sélectionné --", None)
            self.batch_info_label.setVisible(False)
            logger.info("Reset de la sélection")
            return

        try:
            self.current_project_name = project_name
            project_data = self.database.get_dataset_projet(project_name)

            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé")
                QMessageBox.warning(
                    self, 
                    "Projet introuvable", 
                    f"Le projet '{project_name}' n'a pas pu être chargé."
                )
                return

            self.current_project = project_data
            logger.info(f"✅ Projet chargé: {project_name}")

            # ✅ CHARGER LES FAMILLES DE BATCH
            self._load_batch_families()

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _on_batch_changed(self, index):
        """Gère le changement de batch - VERSION AVEC RÉCUPÉRATION SAMPLES"""
        batch_number = self.batch_combo.currentData()
        logger.info(f"🔄 Changement de batch: index={index}, batch_number={batch_number}")

        if batch_number is None:
            self.current_batch_number = None
            self.current_batch_data = None
            self.current_master_typologie = None
            self.combinations = []
            self.batch_info_label.setVisible(False)
            logger.info("Reset des combinaisons")
            return

        try:
            logger.info(f"📂 Chargement du batch {batch_number}")
            batch_result = self.database.get_batch(self.current_project_name, batch_number)

            if not batch_result:
                logger.error(f"❌ Batch {batch_number} non trouvé")
                QMessageBox.warning(
                    self,
                    "Batch introuvable",
                    f"Le batch {batch_number} n'a pas pu être chargé."
                )
                return

            logger.info(f"✅ Batch récupéré")

            # Stocker les données du batch
            self.current_batch_number = batch_number
            self.current_batch_data = batch_result

            # Extraire les données depuis le champ 'data'
            batch_data = batch_result.get('data', {})

            if not batch_data:
                logger.error(f"❌ Le champ 'data' est vide")
                self.combinations = []
                return

            # ✅ EXTRACTION DE LA TYPOLOGIE MASTER COMPLÈTE
            logger.info(f"\n📊 EXTRACTION TYPOLOGIE MASTER")
            master_typologie = batch_data.get('master_typologie', {})

            if master_typologie:
                master_name = master_typologie.get('name', 'N/A')
                clusters = master_typologie.get('taxonomy_clusters', [])

                logger.info(f"  Master: {master_name}")
                logger.info(f"  Clusters: {len(clusters)}")

                # Compter tous les éléments
                total_roots = sum(len(c.get('root_labels', [])) for c in clusters)
                total_parents = sum(
                    len(r.get('parent_labels', []))
                    for c in clusters
                    for r in c.get('root_labels', [])
                )
                total_children = sum(
                    self._count_children_recursive(p.get('children', []))
                    for c in clusters
                    for r in c.get('root_labels', [])
                    for p in r.get('parent_labels', [])
                )

                logger.info(f"  Structure complète:")
                logger.info(f"    • Roots: {total_roots}")
                logger.info(f"    • Parents: {total_parents}")
                logger.info(f"    • Children: {total_children}")

                # Stocker la typologie master complète
                self.current_master_typologie = master_typologie
                logger.info(f"✅ Typologie master complète chargée")
            else:
                logger.warning(f"⚠️ Pas de typologie master dans le batch")
                self.current_master_typologie = None

            # Extraire les informations du batch
            batch_name = batch_data.get('batch_name', 'Sans nom')
            batch_family = batch_data.get('batch_family', '')
            total_batches = batch_result.get('total_batches', 0)
            combinations = batch_data.get('combinations', [])

            if not combinations:
                logger.warning(f"⚠️ Aucune combinaison")
                self.combinations = []
                return

            logger.info(f"\n📊 {len(combinations)} combinaison(s) trouvée(s)")

            # ⭐ CALCUL DU TOTAL DE SAMPLES DEPUIS LA BDD
            total_samples_in_batch = sum(combo.get('nb_samples', 0) for combo in combinations)
            logger.info(f"⭐ Total samples définis dans le batch: {total_samples_in_batch}")

            # Afficher les infos du batch avec samples
            info_text = f"<b>Batch:</b> {batch_name}<br>"
            if batch_family:
                info_text += f"<b>Famille:</b> {batch_family}<br>"
            info_text += f"<b>Numéro:</b> {batch_number}/{total_batches}<br>"
            if master_typologie:
                info_text += f"<b>Master:</b> {master_typologie.get('name', 'N/A')}<br>"
            info_text += f"<b>Combinaisons:</b> {len(combinations)}<br>"
            info_text += f"<b>⭐ Total samples:</b> {total_samples_in_batch}"
            self.batch_info_label.setText(info_text)
            self.batch_info_label.setVisible(True)

            # ✅ Construire l'affichage avec MASTER + CONTEXTES + SAMPLES
            display_combos = []

            for i, combo in enumerate(combinations):
                try:
                    logger.info(f"\n=== Combinaison {i + 1} ===")

                    # Nouveau format : {contexts: [...], nb_samples: N}
                    contexts = combo.get('contexts', [])
                    nb_samples = combo.get('nb_samples', 1)  # ⭐ DEPUIS LA BDD

                    logger.info(f"  Contextes: {len(contexts)}")
                    logger.info(f"  ⭐ Samples (BDD): {nb_samples}")

                    # Créer l'objet d'affichage avec MASTER + SAMPLES
                    display_combo = {
                        'master': master_name if master_typologie else 'N/A',
                        'contexts': [],
                        'nb_samples': nb_samples,  # ⭐ CONSERVÉ DEPUIS LA BDD
                        'master_data': master_typologie
                    }

                    # Extraire chaque contexte
                    for ctx_idx, ctx in enumerate(contexts):
                        level = ctx.get('level', 'unknown')
                        display = ctx.get('display', 'N/A')
                        ctx_data = ctx.get('data', {})

                        logger.debug(f"    Contexte {ctx_idx + 1}: {level} - {display}")

                        display_combo['contexts'].append({
                            'level': level,
                            'display': display,
                            'data': ctx_data
                        })

                    display_combos.append(display_combo)
                    logger.info(f"  ✅ Combinaison {i + 1} traitée")

                except Exception as combo_error:
                    logger.error(f"Erreur combo {i}: {combo_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    display_combos.append({
                        'master': 'Error',
                        'contexts': [{'level': 'error', 'display': 'Erreur de chargement'}],
                        'nb_samples': 1,
                        'master_data': None
                    })

            # Mettre à jour l'affichage
            self.combinations = combinations
            self.visualizer.set_combinations(display_combos)
            self.combo_count_label.setText(f"({len(display_combos)})")

            # ✅ METTRE À JOUR LE CHART AVEC LES VRAIES DONNÉES
            logger.info(f"\n📊 Mise à jour du chart de représentativité")
            logger.info(f"✅ Chart mis à jour avec {len(display_combos)} combinaisons")

            logger.info(f"\n✅ Batch {batch_number} chargé:")
            logger.info(f"  • Master: {master_name if master_typologie else 'N/A'}")
            logger.info(f"  • Combinaisons: {len(combinations)}")
            logger.info(f"  • ⭐ Total samples (BDD): {total_samples_in_batch}")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger le batch:\n\n{str(e)}"
            )

    def _count_children_recursive(self, children):
        """Compte récursivement tous les enfants"""
        if not children:
            return 0
        count = len(children)
        for child in children:
            count += self._count_children_recursive(child.get('children', []))
        return count

    def _on_generate(self):
        """Lance la génération du dataset - VERSION AVEC WORKER + LOGGING"""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 GÉNÉRATION DATASET - DÉMARRAGE")
        logger.info("=" * 80)
    
        if not self.current_project or not self.combinations:
            QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner un projet et un batch"
            )
            return
    
        # ✅ VÉRIFICATION TYPOLOGIE MASTER
        if not self.current_master_typologie:
            logger.error("❌ Pas de typologie master chargée!")
            QMessageBox.warning(
                self,
                "Attention",
                "La typologie master n'est pas chargée.\n"
                "Impossible de générer le dataset."
            )
            return
    
        # ✅ RÉCUPÉRATION DU NOMBRE DE BATCHES À TRAITER
        try:
            num_batches_to_process = int(self.batches_input.text())
            if num_batches_to_process < 1:
                raise ValueError("Le nombre de batches doit être >= 1")
        except (ValueError, AttributeError) as e:
            logger.error(f"❌ Nombre de batches invalide: {self.batches_input.text()}")
            QMessageBox.warning(
                self,
                "Nombre de batches invalide",
                "Veuillez entrer un nombre entier valide (minimum 1)"
            )
            return
    
        # ⭐ CALCUL DU TOTAL DE SAMPLES
        total_samples_per_batch = sum(combo.get('nb_samples', 0) for combo in self.combinations)
        total_samples_all_batches = total_samples_per_batch * num_batches_to_process
    
        # ✅ RÉCUPÉRATION DES PROMPTS
        global_context = self.global_context_editor.toPlainText().strip()
        local_prompt = self.prompt_editor.toPlainText().strip()
    
        if not local_prompt:
            QMessageBox.warning(
                self,
                "Prompt manquant",
                "Veuillez définir au moins un prompt local de génération"
            )
            return
    
        # Combiner les contextes
        if global_context:
            combined_prompt = f"{global_context}\n\n---\n\n{local_prompt}"
            logger.info("✅ Contexte global et local combinés")
        else:
            combined_prompt = local_prompt
            logger.info("ℹ️ Utilisation du contexte local uniquement")
    
        # 📦 PRÉPARER LA CONFIGURATION POUR LE WORKER
        batch_data = self.current_batch_data.get('data', {})
    
        generation_config = {
            "metadata": {
                "project_name": self.current_project_name,
                "batch_number": self.current_batch_number,
                "batch_name": batch_data.get('batch_name', 'Sans nom'),
                "batch_family": batch_data.get('batch_family', ''),
                "num_batches_to_process": num_batches_to_process,
                "total_samples_per_batch": total_samples_per_batch,
                "total_samples_all_batches": total_samples_all_batches,
                "output_format": self.format_combo.currentText()
            },
            "prompts": {
                "global_context": global_context or None,
                "local_prompt": local_prompt,
                "combined_prompt": combined_prompt
            },
            "prompt": combined_prompt,  # Pour le worker
            "master_typologie": {
                "name": self.current_master_typologie.get('name', 'N/A'),
                "full_data": self.current_master_typologie
            },
            "combinations": []
        }
    
        # 📋 CONSTRUIRE LES COMBINAISONS COMPLÈTES
        for i, combo in enumerate(self.combinations):
            contexts = combo.get('contexts', [])
            nb_samples = combo.get('nb_samples', 1)
    
            # ✅ DEBUG : Vérifier ce qu'on envoie
            logger.debug(f"\n🔍 DEBUG Combination {i+1} preparation:")
            logger.debug(f"   Master typologie keys: {self.current_master_typologie.keys()}")
            logger.debug(f"   Master has taxonomy_clusters: {bool(self.current_master_typologie.get('taxonomy_clusters'))}")
    
            if self.current_master_typologie.get('taxonomy_clusters'):
                clusters = self.current_master_typologie['taxonomy_clusters']
                logger.debug(f"   Master clusters count: {len(clusters)}")
                if clusters:
                    logger.debug(f"   First cluster keys: {clusters[0].keys()}")
                    logger.debug(f"   First cluster name: {clusters[0].get('cluster_name', 'NO NAME')}")
    
            combo_export = {
                "combination_index": i + 1,
                "nb_samples": nb_samples,
                "master": {
                    "name": self.current_master_typologie.get('name', 'N/A'),
                    "full_data": self.current_master_typologie  # ✅ Doit contenir taxonomy_clusters
                },
                "contexts": []
            }
    
            for ctx_idx, ctx in enumerate(contexts):
                ctx_data = ctx.get('data', {})
    
                # ✅ DEBUG : Vérifier chaque contexte
                logger.debug(f"   Context {ctx_idx+1} data keys: {ctx_data.keys() if ctx_data else 'EMPTY'}")
                logger.debug(f"   Context {ctx_idx+1} has taxonomy_clusters: {bool(ctx_data.get('taxonomy_clusters'))}")
    
                context_export = {
                    "level": ctx.get('level', 'unknown'),
                    "display": ctx.get('display', 'N/A'),
                    "full_data": ctx_data  # ✅ Doit contenir taxonomy_clusters
                }
                combo_export["contexts"].append(context_export)
    
            generation_config["combinations"].append(combo_export)
    
        # 📝 EXPORTER LA CONFIGURATION COMPLÈTE DANS UN FICHIER DE LOG
        config_filepath = self._export_generation_config_to_file(generation_config)
        generation_id = self.database.save_generation_start(generation_config)

        if not generation_id:
            logger.error("❌ Impossible d'enregistrer la génération dans l'historique")
            QMessageBox.warning(
                self,
                "Erreur",
                "Impossible d'enregistrer la génération dans l'historique"
            )
            return

        logger.info(f"📝 Génération #{generation_id} enregistrée dans l'historique")

        self.current_generation_id = generation_id
    
        # ✅ CONFIRMATION
        msg = f"<b>🚀 Prêt à générer le dataset</b><br><br>"
        msg += f"<b>Configuration :</b><br>"
        msg += f"• Projet : {self.current_project_name}<br>"
        msg += f"• Batch : {batch_data.get('batch_name', 'Sans nom')}<br>"
        msg += f"• Master : {self.current_master_typologie.get('name', 'N/A')}<br>"
        msg += f"• Combinaisons : {len(self.combinations)}<br>"
        msg += f"• Batches à traiter : {num_batches_to_process}<br>"
        msg += f"• Samples par batch : {total_samples_per_batch}<br>"
        msg += f"• <b>Total samples : {total_samples_all_batches}</b><br>"
        msg += f"• Format : {self.format_combo.currentText()}<br>"
        if config_filepath:
            msg += f"<br>📝 <b>Config exportée :</b><br><small>{config_filepath}</small><br>"
        msg += f"<br><b>Lancer la génération ?</b>"
    
        reply = QMessageBox.question(
            self,
            "🚀 Confirmer la génération",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
    
        if reply != QMessageBox.Yes:
            logger.info("❌ Génération annulée par l'utilisateur")
            return
    
        # 🎬 LANCER LE WORKER
        try:
            from ui.widgets.workers.gemini_dataset_worker import GeminiDatasetWorker
    
            self.worker = GeminiDatasetWorker(generation_config)
    
            # Connecter les signaux
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.combination_completed.connect(self._on_combination_completed)
            self.worker.batch_completed.connect(self._on_batch_completed)
            self.worker.generation_completed.connect(self._on_generation_completed)
            self.worker.generation_failed.connect(self._on_generation_failed)
            self.worker.log_message.connect(self._on_log_message)
    
            # Démarrer
            self.worker.start()
    
            # UI : mode génération
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("⏳ Génération en cours...")
            self.export_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(total_samples_all_batches)
    
            logger.info("✅ Worker lancé avec succès")
    
        except Exception as e:
            logger.error(f"❌ Erreur lors du lancement: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de lancer la génération:\n\n{str(e)}"
            )

    def _load_batch_families(self):
        """Charge les familles de batch du projet actuel"""
        self.batch_family_combo.clear()
        self.batch_family_combo.addItem("-- Sélectionner une famille --", None)

        if not self.current_project_name:
            logger.warning("Aucun projet actuel")
            return

        try:
            logger.info(f"🔍 Recherche des familles de batch pour: {self.current_project_name}")
            batches = self.database.get_all_batches(self.current_project_name)

            if not batches or len(batches) == 0:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_family_combo.addItem("-- Aucune famille disponible --", None)
                return

            # Extraire les familles uniques
            families = set()
            for batch in batches:
                batch_data = batch.get('data', {})
                family = batch_data.get('batch_family', '')
                if family:
                    families.add(family)

            if not families:
                logger.info(f"⚠️ Aucune famille définie")
                self.batch_family_combo.addItem("-- Aucune famille définie --", None)
                return

            # Trier et ajouter les familles
            families_sorted = sorted(list(families))
            logger.info(f"📦 {len(families_sorted)} famille(s) trouvée(s)")

            for family in families_sorted:
                # Compter les batches dans cette famille
                count = sum(1 for b in batches if b.get('data', {}).get('batch_family', '') == family)
                display_name = f"{family} ({count} batch{'es' if count > 1 else ''})"
                self.batch_family_combo.addItem(display_name, family)
                logger.debug(f"  ✓ Famille ajoutée: {display_name}")

            logger.info(f"✅ {len(families_sorted)} famille(s) chargée(s)")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.batch_family_combo.addItem("-- Erreur de chargement --", None)

    def _on_batch_family_changed(self, family_name):
        """Gère le changement de famille de batch - VERSION AVEC CHART UPDATE"""
        family = self.batch_family_combo.currentData()
        logger.info(f"🔄 Changement de famille: {family_name} (data: {family})")

        # Reset des combinaisons
        self.current_batch_number = None
        self.current_batch_data = None
        self.combinations = []
        self.batch_info_label.setVisible(False)

        if family is None:
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Sélectionner une famille --", None)
            logger.info("Reset des batches")
            return

        # Charger les batches de cette famille
        self._load_batches_by_family(family)

        # ✅ METTRE À JOUR LE CHART DE REPRÉSENTATIVITÉ
        try:
            all_batches = self.database.get_all_batches(self.current_project_name)
            batches_in_family = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]

            # Préparer les données pour le chart
            chart_data = []
            for batch in batches_in_family:
                batch_num = batch.get('batch_number', 0)
                batch_data_content = batch.get('data', {})
                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                total_samples = sum(c.get('nb_samples', 0) for c in combinations)

                chart_data.append({
                    'batch_number': batch_num,
                    'batch_name': batch_name,
                    'batch_family': family,
                    'combinations_count': len(combinations),
                    'total_samples': total_samples
                })

            logger.info(f"✅ Chart mis à jour avec {len(chart_data)} batches")

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour chart: {str(e)}")

    def _load_batches_by_family(self, family):
        """Charge les batches d'une famille spécifique"""
        self.batch_combo.clear()
        self.batch_combo.addItem("-- Sélectionner un batch --", None)

        if not self.current_project_name or not family:
            logger.warning("Projet ou famille manquant")
            return

        try:
            logger.info(f"🔍 Recherche des batches pour famille: {family}")
            all_batches = self.database.get_all_batches(self.current_project_name)

            if not all_batches:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_combo.addItem("-- Aucun batch disponible --", None)
                return

            # Filtrer par famille
            batches = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]

            if not batches:
                logger.info(f"⚠️ Aucun batch dans cette famille")
                self.batch_combo.addItem("-- Aucun batch dans cette famille --", None)
                return

            logger.info(f"📦 {len(batches)} batch(es) trouvé(s) dans {family}")

            # Trier par numéro
            try:
                batches_sorted = sorted(batches, key=lambda x: x.get('batch_number', 0))
            except:
                batches_sorted = batches

            # Ajouter chaque batch
            for batch in batches_sorted:
                batch_num = batch.get('batch_number', 0)
                total_batches = batch.get('total_batches', 0)
                batch_data_content = batch.get('data', {})

                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                combinations_count = len(combinations)

                if total_batches > 0:
                    display_name = f"Batch {batch_num}/{total_batches} - {batch_name} ({combinations_count} combos)"
                else:
                    display_name = f"Batch {batch_num} - {batch_name} ({combinations_count} combos)"

                self.batch_combo.addItem(display_name, batch_num)
                logger.debug(f"  ✓ Batch ajouté: {display_name}")

            logger.info(f"✅ {len(batches)} batch(es) chargé(s)")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.batch_combo.addItem("-- Erreur de chargement --", None)

    def _on_progress_updated(self, current: int, total: int, message: str):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{message} - {current}/{total} samples ({current*100//total if total > 0 else 0}%)")
        logger.debug(f"📊 Progression: {current}/{total} - {message}")

    def _on_combination_completed(self, combo_idx: int, info: dict):
        """Marque une combinaison comme complétée"""
        samples_generated = info.get('samples_generated', 0)
        logger.info(f"✅ Combinaison {combo_idx + 1} complétée: {samples_generated} samples")

    def _on_batch_completed(self, batch_number: int, results: list):
        """Appelé quand un batch est terminé"""
        logger.info(f"✅ Batch {batch_number} terminé: {len(results)} samples")

    def _on_generation_completed(self, results: list, metadata: dict):
        """Appelé quand toute la génération est terminée"""
        logger.info(f"\n{'=' * 80}")
        logger.info(f"🎉 GÉNÉRATION TERMINÉE")
        logger.info(f"   • Total samples: {len(results)}")
        logger.info(f"{'=' * 80}")

        # Stocker les résultats
        self.generation_results = results
        self.generation_metadata = metadata

        # ✅ METTRE À JOUR L'HISTORIQUE
        if hasattr(self, 'current_generation_id'):
            duration = metadata.get('duration_seconds')
            self.database.update_generation_completion(
                self.current_generation_id,
                output_file_path=None,  # Sera défini lors de l'export
                duration_seconds=duration
            )

        # ✅ AJOUTER AU PANNEAU DATASET
        if self.current_project_name and self.current_batch_number:
            batch_name = metadata.get('batch_name', f'Batch {self.current_batch_number}')
            self._add_to_history(
                project=self.current_project_name,
                batch=batch_name,
                count=len(results)
            )
            
            # Ouvrir automatiquement le panneau si fermé
            if self.snippets_panel.width() == 0:
                self._toggle_snippets_panel()

        # UI : réactiver les boutons
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Générer le Dataset")
        self.export_btn.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())

        # Message de succès
        QMessageBox.information(
            self,
            "✅ Génération terminée",
            f"<b>Dataset généré avec succès !</b><br><br>"
            f"• Total samples: {len(results)}<br>"
            f"• Format: {metadata.get('output_format', 'JSON')}<br><br>"
            f"Utilisez le bouton 'Exporter' pour sauvegarder."
        )

    def _on_generation_failed(self, error: str):
        """Appelé en cas d'erreur"""
        logger.error(f"❌ Génération échouée: {error}")

        # ✅ METTRE À JOUR L'HISTORIQUE AVEC L'ERREUR
        if hasattr(self, 'current_generation_id'):
            self.database.update_generation_completion(
                self.current_generation_id,
                error_message=error
            )

        # UI : réactiver les boutons
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Générer le Dataset")
        self.progress_bar.setVisible(False)

        QMessageBox.critical(
            self,
            "❌ Erreur de génération",
            f"La génération a échoué:\n\n{error}"
        )

    def _on_log_message(self, level: str, message: str):
        """Reçoit les logs du worker"""
        # Optionnel : afficher dans une console de logs dans l'UI
        pass

    def _on_export(self):
        """Exporte le dataset généré avec données nettoyées"""
        if not self.generation_results:
            QMessageBox.warning(
                self,
                "Aucune donnée",
                "Aucun dataset à exporter.\nVeuillez d'abord générer un dataset."
            )
            return

        output_format = self.format_combo.currentText()

        # Extensions
        format_ext = {
            "JSON": ".json",
            "CSV": ".csv",
            "JSONL": ".jsonl",
            "Parquet": ".parquet"
        }

        ext = format_ext.get(output_format, ".json")
        default_filename = f"dataset_{self.current_project_name}_batch{self.current_batch_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "💾 Exporter le dataset",
            default_filename,
            f"Fichiers {output_format} (*{ext})"
        )

        if not filepath:
            logger.info("❌ Export annulé")
            return

        try:
            # Export selon le format
            if output_format == "JSON":
                self._export_json(filepath)
            elif output_format == "JSONL":
                self._export_jsonl(filepath)
            elif output_format == "CSV":
                self._export_csv(filepath)
            elif output_format == "Parquet":
                self._export_parquet(filepath)

            # ✅ METTRE À JOUR L'HISTORIQUE AVEC LE CHEMIN (POUR TOUS LES FORMATS)
            if hasattr(self, 'current_generation_id') and self.current_generation_id:
                cursor = self.database.connection.cursor()
                cursor.execute("""
                    UPDATE dataset_generations 
                    SET output_file_path = ?
                    WHERE id = ?
                """, (filepath, self.current_generation_id))
                self.database.connection.commit()
                logger.info(f"📝 Chemin d'export enregistré dans l'historique: {filepath}")

            logger.info(f"✅ Dataset exporté: {filepath}")

            QMessageBox.information(
                self,
                "✅ Export réussi",
                f"Dataset exporté avec succès vers:\n\n{filepath}\n\n"
                f"Format: {output_format}\n"
                f"Samples: {len(self.generation_results)}"
            )

        except Exception as e:
            logger.error(f"❌ Erreur export: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur d'export",
                f"Impossible d'exporter le dataset:\n\n{str(e)}"
            )

    def _export_json(self, filepath: str):
        """Exporte en JSON avec samples nettoyés"""
        # ✅ Nettoyer les samples
        cleaned_samples = [self._clean_sample_for_export(s) for s in self.generation_results]

        output = {
            "metadata": self.generation_metadata,
            "samples": cleaned_samples
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON exporté: {filepath}")


    def _export_jsonl(self, filepath: str):
        """Exporte en JSONL (une ligne par sample) avec données nettoyées"""
        with open(filepath, 'w', encoding='utf-8') as f:
            for sample in self.generation_results:
                # ✅ Nettoyer chaque sample
                cleaned = self._clean_sample_for_export(sample)
                f.write(json.dumps(cleaned, ensure_ascii=False) + '\n')

        logger.info(f"✅ JSONL exporté: {filepath}")

    def _export_csv(self, filepath: str):
        """
        Exporte en CSV avec données nettoyées
        Format aplati pour CSV : une ligne par combinaison
        Gère la hiérarchie complète : label_root, label_parent, label_enfant, label_enfant_1, label_enfant_2, ...
        """
        import csv

        if not self.generation_results:
            return

        # ✅ DÉTERMINER LE NOMBRE MAXIMUM DE NIVEAUX D'ENFANTS
        max_enfant_levels = 0
        for sample in self.generation_results:
            combinaisons = sample.get('combinaisons', [])
            for combo in combinaisons:
                # Chercher les clés label_enfant_N
                enfant_keys = [k for k in combo.keys() if k.startswith('label_enfant_') and k != 'label_enfant']
                if enfant_keys:
                    # Extraire le niveau max (label_enfant_1 -> 1, label_enfant_2 -> 2, etc.)
                    levels = [int(k.split('_')[-1]) for k in enfant_keys if k.split('_')[-1].isdigit()]
                    if levels:
                        max_enfant_levels = max(max_enfant_levels, max(levels))

        # Construire les colonnes dynamiquement avec la hiérarchie complète
        fieldnames = [
            'sample_id', 'input', 'output',
            'typologie_de_contexte', 'cluster', 
            'label',           # Label simple (si pas de hiérarchie)
            'label_root',      # Niveau 1 : ROOT
            'label_parent',    # Niveau 2 : PARENT
            'label_enfant'     # Niveau 3 : ENFANT/CHILD
        ]

        # Ajouter label_enfant_1, label_enfant_2, ... selon le max trouvé (Niveau 4+)
        for i in range(1, max_enfant_levels + 1):
            fieldnames.append(f'label_enfant_{i}')

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sample in self.generation_results:
                sample_id = sample.get('sample_id')
                input_text = sample.get('input', '')
                output_text = sample.get('output', '')
                combinaisons = sample.get('combinaisons', [])

                # ✅ Une ligne par combinaison
                if not combinaisons:
                    # Si pas de combinaisons, écrire une ligne vide
                    row = {
                        'sample_id': sample_id,
                        'input': input_text,
                        'output': output_text
                    }
                    # Remplir les colonnes manquantes avec vide
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    writer.writerow(row)
                else:
                    for combo in combinaisons:
                        row = {
                            'sample_id': sample_id,
                            'input': input_text,
                            'output': output_text,
                            'typologie_de_contexte': combo.get('typologie_de_contexte', ''),
                            'cluster': combo.get('cluster', ''),
                            'label': combo.get('label', ''),           # Label simple
                            'label_root': combo.get('label_root', ''),     # ROOT
                            'label_parent': combo.get('label_parent', ''), # PARENT
                            'label_enfant': combo.get('label_enfant', '')  # ENFANT
                        }

                        # Ajouter les label_enfant_N dynamiquement (sous-enfants)
                        for i in range(1, max_enfant_levels + 1):
                            row[f'label_enfant_{i}'] = combo.get(f'label_enfant_{i}', '')

                        writer.writerow(row)

        logger.info(f"✅ CSV exporté: {filepath}")

    def _clean_sample_for_export(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Nettoie un sample en ne gardant que les champs essentiels
        FORMAT : sample_id, input, combinaisons[], output
        """
        return {
            'sample_id': sample.get('sample_id'),
            'input': sample.get('input', ''),
            'combinaisons': sample.get('combinaisons', []),
            'output': sample.get('output', '')
        }

    def _export_parquet(self, filepath: str):
        """
        Exporte en Parquet avec données nettoyées
        Format aplati avec hiérarchie complète : label_root, label_parent, label_enfant, label_enfant_1, ...
        """
        try:
            import pandas as pd

            # ✅ DÉTERMINER LE NOMBRE MAXIMUM DE NIVEAUX D'ENFANTS
            max_enfant_levels = 0
            for sample in self.generation_results:
                combinaisons = sample.get('combinaisons', [])
                for combo in combinaisons:
                    enfant_keys = [k for k in combo.keys() if k.startswith('label_enfant_') and k != 'label_enfant']
                    if enfant_keys:
                        levels = [int(k.split('_')[-1]) for k in enfant_keys if k.split('_')[-1].isdigit()]
                        if levels:
                            max_enfant_levels = max(max_enfant_levels, max(levels))

            # Aplatir les données
            rows = []
            for sample in self.generation_results:
                sample_id = sample.get('sample_id')
                input_text = sample.get('input', '')
                output_text = sample.get('output', '')
                combinaisons = sample.get('combinaisons', [])

                if not combinaisons:
                    row = {
                        'sample_id': sample_id,
                        'input': input_text,
                        'output': output_text,
                        'typologie_de_contexte': '',
                        'cluster': '',
                        'label': '',
                        'label_root': '',
                        'label_parent': '',
                        'label_enfant': ''
                    }
                    # Ajouter colonnes label_enfant_N vides
                    for i in range(1, max_enfant_levels + 1):
                        row[f'label_enfant_{i}'] = ''
                    rows.append(row)
                else:
                    for combo in combinaisons:
                        row = {
                            'sample_id': sample_id,
                            'input': input_text,
                            'output': output_text,
                            'typologie_de_contexte': combo.get('typologie_de_contexte', ''),
                            'cluster': combo.get('cluster', ''),
                            'label': combo.get('label', ''),
                            'label_root': combo.get('label_root', ''),
                            'label_parent': combo.get('label_parent', ''),
                            'label_enfant': combo.get('label_enfant', '')
                        }
                        # Ajouter label_enfant_N dynamiquement
                        for i in range(1, max_enfant_levels + 1):
                            row[f'label_enfant_{i}'] = combo.get(f'label_enfant_{i}', '')
                        rows.append(row)

            df = pd.DataFrame(rows)
            df.to_parquet(filepath, index=False)

            logger.info(f"✅ Parquet exporté: {filepath}")

        except ImportError:
            raise Exception(
                "Le module 'pandas' est requis pour exporter en Parquet.\n"
                "Installez-le avec: pip install pandas pyarrow"
            )
        
    def resizeEvent(self, event):
        """Repositionne le bouton toggle et gère le responsive"""
        super().resizeEvent(event)

        # ✅ Repositionner le bouton toggle snippets
        if hasattr(self, 'toggle_snippets_button'):
            self.update_button_position()

        # ✅ Ajuster la hauteur du bouton toggle selon la fenêtre
        if hasattr(self, 'toggle_snippets_button'):
            button_height = min(200, int(self.height() * 0.20))
            self.toggle_snippets_button.setMaximumHeight(button_height)

        # ✅ Gérer les petites largeurs (mobile-like)
        window_width = self.width()

        if window_width < 800:
            # Mode compact: ajuster les proportions
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.30),  # Gauche: 30%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.35)   # Droite: 35%
                ])
        elif window_width < 1200:
            # Mode moyen
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.27),  # Gauche: 27%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.38)   # Droite: 38%
                ])
        else:
            # Mode large: proportions par défaut
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.25),  # Gauche: 25%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.40)   # Droite: 40%
                ])

    def _init_overlay_button(self):
        """Initialise le bouton chevron et le panneau latéral (Style Snippet)"""
        
        # Pour simuler la fonction tr() si elle n'existe pas
        def tr(text): return {"generated_code": "Dataset"}.get(text, text)
        
        graph_container = self

        self.toggle_snippets_button = QtWidgets.QWidget(self)
        button_height = min(200, int(self.height() * 0.20))
        self.toggle_snippets_button.setMinimumSize(36, 150)
        self.toggle_snippets_button.setMaximumSize(36, button_height)
        self.toggle_snippets_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_snippets_button.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                border: none;
                border-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QWidget:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """)

        # Layout interne du bouton
        button_layout = QtWidgets.QVBoxLayout(self.toggle_snippets_button)
        button_layout.setContentsMargins(0, 15, 0, 15)
        button_layout.setSpacing(10)
        button_layout.setAlignment(Qt.AlignCenter)

        # Icône chevron
        self.chevron_icon_label = QtWidgets.QLabel()
        self.chevron_icon_label.setAlignment(Qt.AlignCenter)
        try:
            self.chevron_icon_label.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(18, 18))
        except:
            self.chevron_icon_label.setText("<") # Fallback si qtawesome manque

        button_layout.addWidget(self.chevron_icon_label)

        # Texte vertical "DATASET"
        self.toggle_button_text = QtWidgets.QLabel("D\nA\nT\nA\nS\nE\nT")
        self.toggle_button_text.setAlignment(Qt.AlignCenter)
        self.toggle_button_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }
        """)
        button_layout.addWidget(self.toggle_button_text)

        # Rendre le widget cliquable
        self.toggle_snippets_button.mousePressEvent = lambda event: self._toggle_snippets_panel()

        # Position initiale (sera mis à jour par resizeEvent)
        self.toggle_snippets_button.move(self.width() - 40, 80)
        self.toggle_snippets_button.show()

        # ===== PANNEAU DE SNIPPETS =====
        # On utilise self.snippets_container créé dans _init_ui comme hôte
        self.snippets_panel = self.snippets_container
        self.snippets_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.97);
                border-left: 3px solid #D0D0D0;
                border-radius: 0px;
            }
        """)

        snippets_panel_layout = QtWidgets.QVBoxLayout(self.snippets_panel)
        snippets_panel_layout.setContentsMargins(15, 15, 15, 15)
        snippets_panel_layout.setSpacing(10)

        # En-tête du panneau
        snippets_header = QtWidgets.QHBoxLayout()
        snippets_title = QtWidgets.QLabel(f"💻 Dataset")
        snippets_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; background-color: transparent; border: none;")
        snippets_header.addWidget(snippets_title)
        snippets_header.addStretch()

        # Bouton Dataset Global
        self.global_history_button = QtWidgets.QPushButton()
        try:
            self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))
        except:
            self.global_history_button.setText("H")
            
        self.global_history_button.setToolTip("Voir le dataset")
        self.global_history_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.global_history_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 6px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        
        # Menu Dataset
        history_menu = QtWidgets.QMenu(self)
        view_current_action = QtWidgets.QAction("📜 Dataset de la session", self)
        view_current_action.triggered.connect(self._toggle_global_history)
        history_menu.addAction(view_current_action)
        self.global_history_button.setMenu(history_menu)
        
        snippets_header.addWidget(self.global_history_button)

        # Badge compteur
        self.snippets_count_badge = QtWidgets.QLabel("0")
        self.snippets_count_badge.setStyleSheet(f"""
            background-color: {self.primary_color};
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        snippets_header.addWidget(self.snippets_count_badge)

        snippets_panel_layout.addLayout(snippets_header)

        # Accordéon Dataset Global (Contenu)
        self.global_history_accordion = QtWidgets.QWidget()
        self.global_history_accordion.setVisible(True) # Toujours visible par défaut pour voir les résultats
        
        global_history_layout = QtWidgets.QVBoxLayout(self.global_history_accordion)
        global_history_layout.setContentsMargins(0, 0, 0, 0)
        
        # Zone scrollable pour la liste des générations passées
        self.history_scroll_area = QScrollArea()
        self.history_scroll_area.setWidgetResizable(True)
        self.history_scroll_area.setFrameShape(QFrame.NoFrame)
        self.history_scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.history_content_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_content_widget)
        self.history_layout.setAlignment(Qt.AlignTop)
        self.history_layout.setSpacing(10)
        
        self.history_scroll_area.setWidget(self.history_content_widget)
        global_history_layout.addWidget(self.history_scroll_area)
        
        snippets_panel_layout.addWidget(self.global_history_accordion)

    def _toggle_snippets_panel(self):
        """Animation d'ouverture/fermeture du panneau latéral"""
        width = self.snippets_panel.width()
        target_width = 350 if width == 0 else 0
        
        # Changer l'icône du chevron
        try:
            icon_name = 'fa5s.chevron-right' if width == 0 else 'fa5s.chevron-left'
            self.chevron_icon_label.setPixmap(qta.icon(icon_name, color='white').pixmap(18, 18))
        except:
            self.chevron_icon_label.setText(">" if width == 0 else "<")

        # Animation du Panel
        self.anim_panel = QPropertyAnimation(self.snippets_panel, b"minimumWidth")
        self.anim_panel.setDuration(300)
        self.anim_panel.setStartValue(width)
        self.anim_panel.setEndValue(target_width)
        self.anim_panel.setEasingCurve(QEasingCurve.InOutQuart)
        
        # Mettre à jour maximumWidth aussi pour forcer le layout
        self.anim_panel.valueChanged.connect(lambda v: self.snippets_panel.setMaximumWidth(v))
        
        # Repositionner le bouton pendant l'animation
        self.anim_panel.valueChanged.connect(lambda: self.update_button_position())
        
        self.anim_panel.start()

    def update_button_position(self):
        """Helper pour resizeEvent et animation"""
        panel_width = self.snippets_panel.width()
        x_pos = self.width() - panel_width - self.toggle_snippets_button.width()
        self.toggle_snippets_button.move(x_pos, 80)

    def _open_sessions_history(self):
        pass # Placeholder

    def _toggle_global_history(self):
        """Affiche/Masque le dataset"""
        # Dans cette implémentation simple, on peut juste s'assurer que le panneau est ouvert
        if self.snippets_panel.width() == 0:
            self._toggle_snippets_panel()

    def _export_generation_config_to_file(self, generation_config: Dict[str, Any]) -> str:
        """
        Exporte la configuration complète de génération dans un fichier JSON
        Retourne le chemin du fichier créé
        """
        try:
            # Créer le dossier de logs s'il n'existe pas
            logs_dir = Path("generation_logs")
            logs_dir.mkdir(exist_ok=True)

            # Nom du fichier avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = generation_config['metadata']['project_name']
            batch_number = generation_config['metadata']['batch_number']
            filename = f"generation_config_{project_name}_batch{batch_number}_{timestamp}.json"
            filepath = logs_dir / filename

            # Préparer les données à exporter (format lisible)
            export_data = {
                "export_info": {
                    "exported_at": datetime.now().isoformat(),
                    "purpose": "Vérification de la configuration de génération avant envoi à Gemini"
                },
                "metadata": generation_config['metadata'],
                "prompts": generation_config['prompts'],
                "master_typologie": {
                    "name": generation_config['master_typologie']['name'],
                    "full_structure": generation_config['master_typologie']['full_data']
                },
                "combinations_details": []
            }

            # Détailler chaque combinaison
            for combo in generation_config['combinations']:
                combo_detail = {
                    "combination_index": combo['combination_index'],
                    "nb_samples": combo['nb_samples'],
                    "master": {
                        "name": combo['master']['name'],
                        "taxonomy_clusters": combo['master']['full_data'].get('taxonomy_clusters', [])
                    },
                    "contexts": []
                }

                for ctx in combo['contexts']:
                    ctx_detail = {
                        "level": ctx['level'],
                        "display": ctx['display'],
                        "taxonomy_clusters": ctx['full_data'].get('taxonomy_clusters', [])
                    }
                    combo_detail['contexts'].append(ctx_detail)

                export_data['combinations_details'].append(combo_detail)

            # Sauvegarder le fichier
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Configuration exportée : {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"❌ Erreur export config : {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return ""

    def _add_to_history(self, project, batch, count):
        """Ajoute une entrée dans le dataset après génération"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #4A90E2;
                background: #F8FBFF;
            }
        """)
        layout = QVBoxLayout(card)
        
        time_str = datetime.now().strftime("%H:%M")
        
        title = QLabel(f"<b>{project}</b>")
        layout.addWidget(title)
        
        info = QLabel(f"Batch {batch} • {count} samples\n🕒 {time_str}")
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)
        
        # Insérer en haut
        self.history_layout.insertWidget(0, card)
        
        # Mettre à jour le badge
        current_count = int(self.snippets_count_badge.text())
        self.snippets_count_badge.setText(str(current_count + 1))