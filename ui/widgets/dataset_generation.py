#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Generation Panel - Improved 3-column layout
Left: Project & Config | Center: Prompt Editor | Right: Combinations Visualizer
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

# ⚠️ IMPORTS CORRIGÉS - Chemins relatifs depuis ui/panels/
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# Imports des modules nécessaires
from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager


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
    """Panel principal de génération de datasets - Layout 3 colonnes"""
    
    generation_started = pyqtSignal(str)  # project_name
    generation_completed = pyqtSignal(str, str)  # project_name, output_path
    generation_failed = pyqtSignal(str, str)  # project_name, error
    
    def __init__(self, parent=None, database=None, project_manager=None):
        super().__init__(parent)
        
        # ⚠️ INITIALISATION DE LA DATABASE ET DU MANAGER
        self.conductor = None
        
        # Initialize database and project_manager
        # Use passed instances or create new ones
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
        self.combinations = []
        self.dropdown_svg = get_dropdown_svg_path()
        
        # Log d'initialisation
        print("=" * 60)
        print("🚀 INITIALISATION DatasetGenerationPanel")
        print("=" * 60)
        logger.info("🚀 DatasetGenerationPanel initialisé")
        
        self._init_ui()
        
        print("✅ UI initialisée")
        logger.info("✅ UI initialisée")
        
        # Charger les projets si la database est disponible
        if self.database:
            self._load_projects()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur - 3 colonnes"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Zone de scroll principale
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(15)
        
        # === COLONNE GAUCHE (25%) - Projet et Configuration ===
        left_column = self._create_left_column()
        content_layout.addWidget(left_column, 1)
        
        # === COLONNE CENTRALE (35%) - Éditeur de Prompt ===
        center_column = self._create_center_column()
        content_layout.addWidget(center_column, 2)
        
        # === COLONNE DROITE (40%) - Visualiseur de Combinaisons ===
        right_column = self._create_right_column()
        content_layout.addWidget(right_column, 2)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Barre de progression
        self.progress_bar = GradientProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Boutons d'action
        actions = self._create_actions()
        main_layout.addWidget(actions)
        
    def _create_left_column(self):
        """Crée la colonne gauche - Projet et Configuration"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Section Projet
        project_section = self._create_project_section()
        layout.addWidget(project_section)
        
        # Section Configuration
        config_section = self._create_config_section()
        layout.addWidget(config_section)
        
        layout.addStretch()
        
        return column
        
    def _create_center_column(self):
        """Crée la colonne centrale - Éditeur de Prompt"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Titre
        title = QLabel("Prompt de Génération")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        layout.addWidget(title)
        
        # Éditeur de prompt
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText(
            "Exemple:\n\n"
            "Générez des exemples d'entraînement basés sur les typologies suivantes:\n"
            "{typologie}\n\n"
            "Format attendu: {'input': '...', 'output': '...'}"
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
        layout.addWidget(self.prompt_editor, 1)
        
        return column
        
    def _create_right_column(self):
        """Crée la colonne droite - Visualiseur de Combinaisons"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Titre
        title = QLabel("Combinaisons à Générer")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        layout.addWidget(title)
        
        # Visualiseur
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
        """Crée la section de sélection du projet"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Groupe encadré
        group = QGroupBox("Sélection du Projet")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
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
        
        # Bouton de test/refresh
        test_btn = QPushButton("🔄 Recharger les projets")
        test_btn.setMinimumHeight(35)
        test_btn.clicked.connect(self._test_load_projects)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        group_layout.addWidget(test_btn)
        
        # Combo projet
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(40)
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self._apply_combo_style(self.project_combo)
        group_layout.addWidget(self.project_combo)
        
        # Combo batch
        batch_label = QLabel("Batch:")
        batch_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group_layout.addWidget(batch_label)
        
        self.batch_combo = QComboBox()
        self.batch_combo.setMinimumHeight(40)
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self._apply_combo_style(self.batch_combo)
        group_layout.addWidget(self.batch_combo)
        
        layout.addWidget(group)
        
        return widget
        
    def _create_config_section(self):
        """Crée la section de configuration"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Groupe encadré
        group = QGroupBox("Configuration")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
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
        
        # Nombre de samples par combinaison
        samples_label = QLabel("Samples par combinaison:")
        samples_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group_layout.addWidget(samples_label)
        
        self.samples_spin = QSpinBox()
        self.samples_spin.setMinimum(1)
        self.samples_spin.setMaximum(10000)
        self.samples_spin.setValue(10)
        self.samples_spin.setMinimumHeight(40)
        self._apply_spinbox_style(self.samples_spin)
        group_layout.addWidget(self.samples_spin)
        
        # Format de sortie
        format_label = QLabel("Format de sortie:")
        format_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group_layout.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "JSONL", "Parquet"])
        self.format_combo.setMinimumHeight(40)
        self._apply_combo_style(self.format_combo)
        group_layout.addWidget(self.format_combo)
        
        layout.addWidget(group)
        
        return widget
        
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
        
    def _apply_spinbox_style(self, spinbox):
        """Applique le style aux spinbox"""
        spinbox.setStyleSheet(f"""
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
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                border: none;
                background: {Theme.PRIMARY_COLOR};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {Theme.SECONDARY_COLOR};
            }}
        """)
    
    def _test_load_projects(self):
        """Méthode de test pour forcer le rechargement des projets"""
        print("\n" + "=" * 60)
        print("🧪 TEST: Rechargement manuel des projets")
        print("=" * 60)
        
        if not self.database:
            print("❌ Database est None!")
            QMessageBox.critical(
                self,
                "Erreur",
                "La base de données n'est pas initialisée!\n\n"
                "Vérifiez que set_database() a été appelé."
            )
            return
        
        print(f"✅ Database: {self.database}")
        print(f"✅ Type: {type(self.database)}")
        
        # Test direct
        try:
            print("\n🔍 Test direct de get_all_projects()...")
            projects = self.database.get_all_projects()
            print(f"📦 Résultat: {projects}")
            print(f"📦 Nombre: {len(projects) if projects else 0}")
            
            if projects:
                print("\n📋 Détails des projets:")
                for i, proj in enumerate(projects):
                    print(f"  {i+1}. {proj}")
            
            QMessageBox.information(
                self,
                "Test Database",
                f"Projets trouvés: {len(projects) if projects else 0}\n\n"
                f"Voir la console pour les détails."
            )
            
        except Exception as e:
            print(f"\n❌ ERREUR: {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors du test:\n\n{str(e)}"
            )
            return
        
        # Recharger
        print("\n🔄 Rechargement via _load_projects()...")
        self._load_projects()
        
        print("=" * 60)
        print("🧪 TEST terminé")
        print("=" * 60 + "\n")
    
    def set_conductor(self, conductor):
        """Définit le conductor"""
        self.conductor = conductor
        print(f"🎼 Conductor défini: {conductor}")
        logger.info(f"🎼 Conductor défini: {conductor}")
        
    def set_database(self, database):
        """Définit la base de données"""
        print("=" * 60)
        print(f"💾 SET_DATABASE appelé avec: {database}")
        print(f"💾 Type: {type(database)}")
        print("=" * 60)
        
        logger.info(f"💾 set_database appelé avec: {database}")
        logger.info(f"💾 Type de database: {type(database)}")
        
        self.database = database
        
        if database is None:
            print("⚠️ ATTENTION: Database est None!")
            logger.warning("⚠️ Database est None!")
            return
            
        print("📂 Appel de _load_projects()...")
        logger.info("📂 Appel de _load_projects()...")
        
        self._load_projects()
        
        print("✅ set_database terminé")
        logger.info("✅ set_database terminé")
        
    def set_project_manager(self, project_manager):
        """Définit le project manager"""
        self.project_manager = project_manager
        logger.info(f"📋 Project Manager défini: {project_manager}")
        
    def _load_projects(self):
        """Charge les projets disponibles - CORRIGÉ"""
        print("=" * 60)
        print("📋 _LOAD_PROJECTS appelé")
        print("=" * 60)
        
        logger.info("📋 _load_projects démarré")
        
        if not self.database:
            print("❌ ERREUR: self.database est None!")
            logger.error("❌ Database non initialisée dans _load_projects")
            return
        
        print(f"✅ Database OK: {self.database}")
        print(f"✅ Type: {type(self.database)}")
        logger.info(f"✅ Database présente: {type(self.database)}")
            
        try:
            print("🔍 Appel de get_all_projects()...")
            logger.info("🔍 Appel de get_all_projects()")
            
            # Récupération similaire au dashboard
            projects = self.database.get_all_projects()
            
            print(f"📦 Résultat: {projects}")
            print(f"📦 Type: {type(projects)}")
            print(f"📦 Nombre: {len(projects) if projects else 0}")
            logger.info(f"📦 Projets récupérés: {len(projects) if projects else 0}")
            
            if not projects:
                print("⚠️ ATTENTION: Aucun projet trouvé!")
                logger.warning("⚠️ Aucun projet trouvé dans la base de données")
            
            print("🧹 Clear du combo...")
            self.project_combo.clear()
            
            print("➕ Ajout de l'option par défaut...")
            self.project_combo.addItem("-- Sélectionner un projet --", None)
            
            print(f"🔄 Parcours de {len(projects) if projects else 0} projets...")
            
            for i, project in enumerate(projects):
                print(f"\n  Projet {i+1}:")
                print(f"    Type: {type(project)}")
                print(f"    Contenu: {project}")
                
                # Le get_all_projects retourne une liste de dicts avec la clé 'name'
                if isinstance(project, dict):
                    project_name = project.get('name', project.get('nom', 'Sans nom'))
                    print(f"    Nom extrait: {project_name}")
                else:
                    print(f"    ⚠️ Format inattendu!")
                    logger.warning(f"Format de projet inattendu: {type(project)}")
                    continue
                
                print(f"    ➕ Ajout au combo: {project_name}")
                self.project_combo.addItem(project_name, project_name)
                logger.debug(f"✓ Projet ajouté: {project_name}")
            
            combo_count = self.project_combo.count() - 1  # -1 pour l'option par défaut
            print(f"\n✅ {combo_count} projets ajoutés au combo")
            print(f"✅ Total items dans combo: {self.project_combo.count()}")
            logger.info(f"✅ {combo_count} projets chargés dans le combo")
                
        except Exception as e:
            print(f"\n❌ EXCEPTION dans _load_projects:")
            print(f"❌ Type: {type(e)}")
            print(f"❌ Message: {str(e)}")
            logger.error(f"❌ Erreur lors du chargement des projets: {str(e)}")
        
            import traceback
            print(f"\n📋 Traceback complet:")
            traceback.print_exc()
            logger.error(traceback.format_exc())
    
        print("=" * 60)
        print("📋 _LOAD_PROJECTS terminé")
        print("=" * 60)
        
    def _on_project_changed(self, project_name):
        """Gère le changement de projet - CORRIGÉ"""
        logger.info(f"🔄 Changement de projet: {project_name}")

        # Reset si sélection vide
        if project_name == "-- Sélectionner un projet --" or not project_name:
            self.current_project = None
            self.current_project_name = None
            self.combinations = []
            self.visualizer.set_combinations([])
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Aucun projet sélectionné --", None)
            logger.info("Reset de la sélection")
            return

        try:
            # Stocker le nom du projet
            self.current_project_name = project_name

            # Charger le projet complet depuis la BD
            project_data = self.database.get_dataset_projet(project_name)

            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé dans la BD")
                QMessageBox.warning(
                    self, 
                    "Projet introuvable", 
                    f"Le projet '{project_name}' n'a pas pu être chargé."
                )
                return

            self.current_project = project_data
            logger.info(f"✅ Projet chargé: {project_name}")
            logger.debug(f"Données du projet: {project_data.keys() if isinstance(project_data, dict) else type(project_data)}")

            # Charger les batches pour ce projet
            self._load_batches()

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement du projet '{project_name}': {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self, 
                "Erreur", 
                f"Impossible de charger le projet:\n\n{str(e)}"
            )

    def _load_batches(self):
        """Charge les batches du projet actuel - CORRIGÉ AVEC ACCÈS AU CHAMP 'data'"""
        self.batch_combo.clear()
        self.batch_combo.addItem("-- Sélectionner un batch --", None)

        if not self.current_project_name:
            logger.warning("Aucun projet actuel pour charger les batches")
            return

        try:
            logger.info(f"🔍 Recherche des batches pour le projet: {self.current_project_name}")

            # Récupération des batches depuis la BD
            batches = self.database.get_all_batches(self.current_project_name)

            if not batches or len(batches) == 0:
                logger.info(f"⚠️ Aucun batch trouvé pour le projet '{self.current_project_name}'")
                self.batch_combo.addItem("-- Aucun batch disponible --", None)
                return

            logger.info(f"📦 {len(batches)} batches trouvés")

            # Trier par numéro de batch
            try:
                batches_sorted = sorted(batches, key=lambda x: x.get('batch_number', 0))
            except Exception as sort_error:
                logger.warning(f"Impossible de trier les batches: {sort_error}")
                batches_sorted = batches

            # Ajouter chaque batch au combo
            for batch in batches_sorted:
                batch_num = batch.get('batch_number', 0)
                total_batches = batch.get('total_batches', 0)

                # ⚠️ CORRECTION: Les données sont dans le champ 'data' qui est un dict parsé
                batch_data_content = batch.get('data', {})

                # Extraire le nom et les combinaisons depuis 'data'
                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                combinations_count = len(combinations)

                # Format d'affichage cohérent avec le dashboard
                if total_batches > 0:
                    display_name = f"Batch {batch_num}/{total_batches} - {batch_name} ({combinations_count} combos)"
                else:
                    display_name = f"Batch {batch_num} - {batch_name} ({combinations_count} combos)"

                self.batch_combo.addItem(display_name, batch_num)
                logger.debug(f"  ✓ Batch ajouté: {display_name}")

            logger.info(f"✅ {len(batches)} batches chargés dans le combo")

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des batches: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.batch_combo.addItem("-- Erreur de chargement --", None)

    def _on_batch_changed(self, index):
        """Gère le changement de batch - CORRIGÉ AVEC ACCÈS AU CHAMP 'data'"""
        batch_number = self.batch_combo.currentData()

        logger.info(f"🔄 Changement de batch: index={index}, batch_number={batch_number}")

        if batch_number is None:
            self.combinations = []
            self.visualizer.set_combinations([])
            logger.info("Reset des combinaisons")
            return

        try:
            logger.info(f"🔍 Chargement du batch {batch_number} pour le projet {self.current_project_name}")

            # Charger le batch depuis la BD
            batch_result = self.database.get_batch(self.current_project_name, batch_number)

            if not batch_result:
                logger.error(f"❌ Batch {batch_number} non trouvé pour le projet {self.current_project_name}")
                QMessageBox.warning(
                    self,
                    "Batch introuvable",
                    f"Le batch {batch_number} n'a pas pu être chargé."
                )
                return

            logger.debug(f"Batch récupéré: {batch_result.keys() if isinstance(batch_result, dict) else type(batch_result)}")

            # ⚠️ CORRECTION: Les données sont dans batch_result['data']
            batch_data = batch_result.get('data', {})

            if not batch_data:
                logger.error(f"❌ Le champ 'data' est vide dans le batch {batch_number}")
                self.combinations = []
                self.visualizer.set_combinations([])
                return

            # Extraire les combinaisons depuis 'data'
            combinations = batch_data.get('combinations', [])

            if not combinations:
                logger.warning(f"⚠️ Le batch {batch_number} ne contient aucune combinaison")
                self.combinations = []
                self.visualizer.set_combinations([])
                return

            logger.info(f"📊 {len(combinations)} combinaisons trouvées dans le batch")

            # Créer l'affichage des combinaisons
            display_combos = []
            for i, combo in enumerate(combinations):
                try:
                    master = combo.get('master', {})
                    context = combo.get('context', {})

                    # Extraction robuste des informations
                    master_name = 'Unknown'
                    if isinstance(master, dict):
                        master_name = master.get('name', master.get('typologie', 'Unknown'))
                    elif isinstance(master, str):
                        master_name = master

                    context_name = 'Unknown'
                    context_level = 'unknown'
                    if isinstance(context, dict):
                        context_name = context.get('typologie', context.get('name', 'Unknown'))
                        context_level = context.get('level', 'unknown')
                    elif isinstance(context, str):
                        context_name = context

                    display_combo = {
                        'Master': master_name,
                        'Context': context_name,
                        'Level': context_level
                    }
                    display_combos.append(display_combo)

                except Exception as combo_error:
                    logger.error(f"Erreur lors du traitement de la combinaison {i}: {combo_error}")
                    display_combos.append({
                        'Master': 'Error',
                        'Context': 'Error',
                        'Level': 'error'
                    })

            self.combinations = combinations
            self.visualizer.set_combinations(display_combos)

            logger.info(f"✅ Batch {batch_number} chargé avec {len(combinations)} combinaisons")

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement du batch {batch_number}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger le batch:\n\n{str(e)}"
            )

    def _on_generate(self):
        """Lance la génération du dataset"""
        if not self.current_project or not self.combinations:
            QMessageBox.warning(self, "Attention", "Veuillez d'abord sélectionner un projet et un batch")
            return

        if not self.prompt_editor.toPlainText().strip():
            QMessageBox.warning(self, "Attention", "Veuillez rédiger un prompt de génération")
            return

        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Générer {len(self.combinations)} exemples avec {self.samples_spin.value()} samples chacun ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Démarrer la génération
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.combinations))
        self.progress_bar.setValue(0)

        self.generation_started.emit(self.current_project_name)

        # TODO: Implémenter la génération asynchrone avec l'IA
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
        filename = f"dataset_{self.current_project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le dataset",
            filename,
            f"Fichiers {self.format_combo.currentText()} (*{ext})"
        )

        if filepath:
            # TODO: Implémenter l'export réel
            QMessageBox.information(self, "Export", f"Dataset exporté vers:\n{filepath}")
            self.generation_completed.emit(self.current_project_name, filepath)