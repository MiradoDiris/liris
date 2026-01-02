#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Historique de Génération de Datasets
Affiche l'historique des générations avec DEUX camemberts de représentativité,
filtres et recherche.
"""

import os
import json
import traceback
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QBrush

from collections import defaultdict

from utils.logger import logger
from utils.dataset_database import DatasetDatabase
from ui.localization.translator import tr
from ui.styles.theme import Theme


def get_dropdown_svg_path():
    """Retourne le chemin vers l'icône dropdown SVG"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.dirname(current_dir)
    svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
    svg_path = os.path.normpath(svg_path)
    return svg_path.replace('\\', '/')


class ElidedLabel(QtWidgets.QLabel):
    """Label personnalisé qui ajoute '...' si le texte est trop long"""
    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self.text(), Qt.ElideRight, self.width())
        painter.drawText(self.rect(), self.alignment(), elided)




class HierarchicalChartState:
    """Gère l'état de navigation hiérarchique du camembert de typologie - VERSION PROGRESSIVE"""
    
    def __init__(self):
        self.current_level = 0  # 0 = typologie, 1 = cluster, 2 = root, 3+ = enfants
        self.navigation_stack = []  # Stack de navigation: [(name, data), ...]
        self.full_data = []  # Données complètes brutes
        self.total_samples = 0


class BatchProgressionState:
    """Gère l'état de navigation hiérarchique du camembert de progression des batches"""
    
    def __init__(self):
        self.current_level = 0  # 0 = familles, 1 = batches individuels
        self.selected_family = None  # Famille actuellement sélectionnée
        self.family_data = []  # Données de progression par famille
        self.batch_details = []  # Détails des batches individuels de la famille sélectionnée
        
    def reset(self, family_data):
        """Réinitialise l'état avec de nouvelles données de familles"""
        self.current_level = 0
        self.selected_family = None
        self.family_data = family_data
        self.batch_details = []
        
    def navigate_to_family(self, family_name, batch_details):
        """Navigue vers les détails d'une famille spécifique"""
        self.current_level = 1
        self.selected_family = family_name
        self.batch_details = batch_details
        
    def navigate_back(self):
        """Retourne au niveau des familles"""
        if self.current_level > 0:
            self.current_level = 0
            self.selected_family = None
            self.batch_details = []
            return True
        return False
        
    def get_current_data(self):
        """Retourne les données à afficher au niveau actuel"""
        if self.current_level == 0:
            # Niveau 0: Afficher les familles
            return self.family_data
        else:
            # Niveau 1: Afficher les batches de la famille sélectionnée
            return self.batch_details
            
    def can_go_back(self):
        """Vérifie si on peut retourner en arrière"""
        return self.current_level > 0
        
    def get_breadcrumb(self):
        """Retourne le fil d'Ariane"""
        if self.current_level == 0:
            return "Progression par Famille"
        else:
            return f"Progression par Famille > {self.selected_family}"


class HierarchicalChartState:
    """Gère l'état de navigation hiérarchique du camembert de typologie - VERSION PROGRESSIVE"""
    
    def __init__(self):
        self.current_level = 0  # 0 = typologie, 1 = cluster, 2 = root, 3+ = enfants
        self.navigation_stack = []  # Stack de navigation: [(name, data), ...]
        self.full_data = []  # Données complètes brutes
        self.total_samples = 0
        
    def reset(self, chart_data, total_samples):
        """Réinitialise l'état avec de nouvelles données"""
        self.current_level = 0
        self.navigation_stack = []
        self.full_data = chart_data
        self.total_samples = total_samples
        
    def get_current_data(self):
        """Retourne les données à afficher au niveau actuel"""
        if self.current_level == 0:
            # Niveau 0: Afficher uniquement les typologies (premier niveau)
            return self._extract_typologies()
        else:
            # Niveaux supérieurs: Afficher les enfants du dernier élément
            return self._extract_children()
    
    def _extract_typologies(self):
        """Extrait uniquement le premier niveau (typologies) - Support multi-séparateurs"""
        from utils.logger import logger
        
        typologie_map = {}
        
        logger.info(f"🔍 _extract_typologies: Traitement de {len(self.full_data)} items")
        
        for i, item in enumerate(self.full_data):
            name = item.get('name', '')
            samples = item.get('samples', 0)
            
            if i < 3:
                logger.info(f"  Item {i}: name='{name}', samples={samples}")
            
            # Détecter le séparateur utilisé (/, >, →, \)
            separator = None
            if ' / ' in name:
                separator = ' / '
            elif ' > ' in name:
                separator = ' > '
            elif ' → ' in name or ' -> ' in name:
                separator = ' → ' if ' → ' in name else ' -> '
            elif '/' in name:
                separator = '/'
            elif '>' in name:
                separator = '>'
            
            if separator:
                # Extraire la première partie (typologie)
                parts = name.split(separator)
                typologie = parts[0].strip()
                if i < 3:
                    logger.info(f"    → Séparateur '{separator}' détecté, typologie='{typologie}'")
            else:
                # Pas de hiérarchie, c'est déjà une typologie seule
                typologie = name
                if i < 3:
                    logger.info(f"    → Pas de séparateur, typologie='{typologie}'")
            
            if typologie:
                if typologie not in typologie_map:
                    typologie_map[typologie] = {
                        'name': typologie,
                        'samples': 0,
                        'level': 0,
                        'full_path': typologie,
                        'has_children': False,
                        'separator': separator  # Stocker le séparateur pour usage ultérieur
                    }
                
                typologie_map[typologie]['samples'] += samples
                
                # Vérifier si cette typologie a des enfants
                if separator:
                    typologie_map[typologie]['has_children'] = True
        
        result = list(typologie_map.values())
        logger.info(f"✅ Typologies extraites: {[(t['name'], t['samples'], t['has_children']) for t in result[:5]]}")
        return sorted(result, key=lambda x: x['samples'], reverse=True)

    def _extract_children(self):
        """Extrait les éléments enfants du niveau actuel - Support multi-séparateurs"""
        from utils.logger import logger
        
        if not self.navigation_stack:
            return []
        
        current_path = self.navigation_stack[-1][0]
        depth = len(self.navigation_stack)
        
        logger.info(f"🔍 _extract_children: current_path='{current_path}', depth={depth}")
        
        children_map = {}
        
        for item in self.full_data:
            name = item.get('name', '')
            samples = item.get('samples', 0)
            
            if not name:
                continue
            
            # Vérifier si cet item appartient au chemin actuel
            if not name.startswith(current_path):
                continue
            
            # Détecter le séparateur utilisé
            separator = None
            if ' / ' in name:
                separator = ' / '
            elif ' > ' in name:
                separator = ' > '
            elif ' → ' in name or ' -> ' in name:
                separator = ' → ' if ' → ' in name else ' -> '
            elif '/' in name:
                separator = '/'
            elif '>' in name:
                separator = '>'
            
            if not separator:
                continue
            
            # Parser les niveaux
            parts = [p.strip() for p in name.split(separator)]
            
            # On veut les enfants au niveau depth
            if len(parts) > depth:
                # Construire le chemin jusqu'au niveau enfant
                child_full_path = separator.join(parts[:depth + 1])
                child_name = parts[depth]
                
                if child_full_path not in children_map:
                    children_map[child_full_path] = {
                        'name': child_name,
                        'samples': 0,
                        'level': depth,
                        'full_path': child_full_path,
                        'has_children': False
                    }
                
                children_map[child_full_path]['samples'] += samples
                
                # Vérifier s'il y a encore des niveaux plus profonds
                if len(parts) > depth + 1:
                    children_map[child_full_path]['has_children'] = True
        
        result = list(children_map.values())
        logger.info(f"✅ Enfants extraits: {[(c['name'], c['samples'], c['has_children']) for c in result[:5]]}")
        return sorted(result, key=lambda x: x['samples'], reverse=True)

    def navigate_to(self, name, full_path):
        """Navigue vers un élément enfant"""
        self.navigation_stack.append((full_path, name))
        self.current_level += 1
        
    def navigate_back(self):
        """Retourne au niveau précédent"""
        if self.navigation_stack:
            self.navigation_stack.pop()
            self.current_level -= 1
            return True
        return False
    
    def get_breadcrumb(self):
        """Retourne le fil d'Ariane pour l'affichage"""
        if not self.navigation_stack:
            return "Typologie de Contexte"
        
        breadcrumb_parts = []
        for full_path, name in self.navigation_stack:
            breadcrumb_parts.append(name)
        
        return " > ".join(breadcrumb_parts)
    
    def can_go_back(self):
        """Vérifie si on peut retourner en arrière"""
        return len(self.navigation_stack) > 0


class DatasetHistoryWidget(QtWidgets.QWidget):
    """
    Widget pour l'historique des générations de datasets
    Layout en colonnes avec thème cohérent et DEUX camemberts
    """

    generation_selected = pyqtSignal(int)
    generation_deleted = pyqtSignal(int)
    
    prompt_selected = generation_selected
    prompt_deleted = generation_deleted

    def __init__(self, parent=None):
        super().__init__(parent)

        logger.info("INITIALISATION DatasetHistoryWidget")

        try:
            from utils.dataset_database import DatasetDatabase
            self.database = DatasetDatabase()
        except Exception as e:
            logger.error(f"Erreur initialisation database: {e}")
            self.database = None

        self.current_generation_id = None
        self.generations = []
        self.dropdown_svg = get_dropdown_svg_path()
        self.current_project_name = None  # Pour le camembert de progression

        # État hiérarchique pour le camembert de typologie
        self.hierarchical_state = HierarchicalChartState()
        
        # État hiérarchique pour le camembert de progression des batches
        self.batch_progression_state = BatchProgressionState()

        self._init_ui()

        if self.database:
            self.refresh_list()

    def _init_ui(self):
        """Initialise l'interface en layout colonnes"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        left_column = self._create_left_column()
        main_layout.addWidget(left_column, 25)

        right_column = self._create_right_column()
        main_layout.addWidget(right_column, 75)

    def _create_left_column(self):
        """Crée la colonne gauche avec filtres et liste"""
        column = QtWidgets.QWidget()
        column.setStyleSheet(f"""
            QWidget {{
                background: white;
                border-right: 2px solid #E0E0E0;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        header = self._create_header()
        layout.addWidget(header)

        search_group = self._create_search_bar()
        layout.addWidget(search_group)

        filters_group = self._create_filters()
        layout.addWidget(filters_group)

        self.generations_list = QtWidgets.QListWidget()
        self.generations_list.setAlternatingRowColors(True)
        self.generations_list.setStyleSheet(f"""
            QListWidget {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background: white;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 12px;
                border-radius: 4px;
                margin: 2px 0;
                color: #333333;
            }}
            QListWidget::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background: #F8F9FA;
                color: #333333;
            }}
        """)
        self.generations_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.generations_list)

        self.count_label = QtWidgets.QLabel("0 génération(s)")
        self.count_label.setStyleSheet(f"""
            color: {Theme.PRIMARY_COLOR};
            font-weight: bold;
            font-size: 11pt;
            border: none;
        """)
        layout.addWidget(self.count_label)

        return column

    def _create_header(self):
        """Crée l'en-tête avec titre et actions"""
        header = QtWidgets.QWidget()
        header.setStyleSheet("border: none;")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QtWidgets.QLabel("Historique des Générations")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.export_btn = QtWidgets.QPushButton("Exporter")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {Theme.PRIMARY_COLOR};
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                padding: 6px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #F5F5F5;
            }}
        """)
        self.export_btn.clicked.connect(self._on_export_history)
        header_layout.addWidget(self.export_btn)

        return header

    def _create_search_bar(self):
        """Crée la barre de recherche"""
        group = QtWidgets.QGroupBox("Recherche")
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
        """)
        layout = QtWidgets.QVBoxLayout(group)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher par projet, batch, date...")
        self.search_edit.setMinimumHeight(35)
        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 5px 10px;
                background: white;
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        layout.addWidget(self.search_edit)

        return group

    def _create_filters(self):
        """Crée les filtres"""
        group = QtWidgets.QGroupBox("Filtres")
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
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)

        project_label = QtWidgets.QLabel("Projet:")
        project_label.setStyleSheet("font-weight: bold; font-size: 9pt; border: none;")
        layout.addWidget(project_label)

        self.project_filter = QtWidgets.QComboBox()
        self.project_filter.addItem("Tous les projets", "")
        self.project_filter.setMinimumHeight(35)
        self.project_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._apply_combo_style(self.project_filter)
        layout.addWidget(self.project_filter)

        format_status_layout = QtWidgets.QHBoxLayout()
        format_status_layout.setSpacing(10)

        format_column = QtWidgets.QVBoxLayout()
        format_label = QtWidgets.QLabel("Format:")
        format_label.setStyleSheet("font-weight: bold; font-size: 9pt; border: none;")
        format_column.addWidget(format_label)

        self.format_filter = QtWidgets.QComboBox()
        self.format_filter.addItems(["Tous les formats", "JSON", "CSV", "JSONL", "Parquet"])
        self.format_filter.setMinimumHeight(35)
        self.format_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._apply_combo_style(self.format_filter)
        format_column.addWidget(self.format_filter)

        status_column = QtWidgets.QVBoxLayout()
        status_label = QtWidgets.QLabel("Statut:")
        status_label.setStyleSheet("font-weight: bold; font-size: 9pt; border: none;")
        status_column.addWidget(status_label)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(["Tous les statuts", "Complété", "Échoué", "En cours"])
        self.status_filter.setMinimumHeight(35)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._apply_combo_style(self.status_filter)
        status_column.addWidget(self.status_filter)

        format_status_layout.addLayout(format_column)
        format_status_layout.addLayout(status_column)

        layout.addLayout(format_status_layout)

        return group

    def _apply_combo_style(self, combo):
        """Applique le style aux combobox avec gestion icône SVG"""
        
        arrow_style = ""
        if self.dropdown_svg:
            arrow_style = f"""
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 16px;
                height: 16px;
            }}
            """
        
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 5px 10px;
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
                background: #FAFAFA;
            }}
            {arrow_style}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: {Theme.PRIMARY_COLOR};
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
        """)

    def _create_right_column(self):
        """Crée la colonne droite avec détails et DEUX visualisations"""
        column = QtWidgets.QWidget()
        column.setStyleSheet("background: white; border: none;")
        layout = QtWidgets.QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ✅ Container pour les DEUX camemberts côte à côte
        charts_container = QtWidgets.QWidget()
        charts_layout = QtWidgets.QHBoxLayout(charts_container)
        charts_layout.setSpacing(10)
        charts_layout.setContentsMargins(0, 0, 0, 0)

        # Camembert 1: Distribution des typologies
        typologie_chart = self._create_typologie_chart_group()
        charts_layout.addWidget(typologie_chart, 50)

        # Camembert 2: Progression par batch
        batch_chart = self._create_batch_chart_group()
        charts_layout.addWidget(batch_chart, 50)

        layout.addWidget(charts_container, 70)

        # Section détails (RÉDUITE)
        details_group = self._create_details_group()
        layout.addWidget(details_group, 30)

        return column

    def _create_typologie_chart_group(self):
        """Crée le camembert de distribution des typologies"""
        group = QtWidgets.QGroupBox("Distribution des Typologies")
        group.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        layout = QtWidgets.QVBoxLayout(group)

        self.typologie_series = QPieSeries()
        self.typologie_series.setHoleSize(0.0)

        slice_default = self.typologie_series.append("Aucune donnée", 1)
        slice_default.setColor(QColor("#E0E0E0"))
        slice_default.setBorderColor(Qt.transparent)
        slice_default.setLabelVisible(False)

        self.typologie_chart = QChart()
        self.typologie_chart.addSeries(self.typologie_series)
        self.typologie_chart.setTitle("Sélectionnez une génération")
        self.typologie_chart.setTitleFont(QFont("Segoe UI", 11, QFont.Bold))
        self.typologie_chart.setTitleBrush(QBrush(QColor("#1e293b")))

        self.typologie_chart.legend().setVisible(True)
        self.typologie_chart.legend().setAlignment(Qt.AlignBottom)
        self.typologie_chart.legend().setFont(QFont("Segoe UI", 8))
        self.typologie_chart.legend().setLabelColor(QColor("#1e293b"))
        self.typologie_chart.legend().setBackgroundVisible(False)
        self.typologie_chart.legend().setBorderColor(Qt.transparent)

        self.typologie_chart.setBackgroundVisible(False)
        self.typologie_chart.setBackgroundRoundness(0)
        self.typologie_chart.setMargins(QtCore.QMargins(10, 10, 10, 10))
        self.typologie_chart.setAnimationOptions(QChart.SeriesAnimations)

        self.typologie_chart_view = QChartView(self.typologie_chart)
        self.typologie_chart_view.setRenderHint(QPainter.Antialiasing)
        self.typologie_chart_view.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.typologie_chart_view)

        # Bouton de retour pour la navigation hiérarchique
        self.typologie_back_btn = QtWidgets.QPushButton("← Retour")
        self.typologie_back_btn.setEnabled(False)
        self.typologie_back_btn.setCursor(Qt.PointingHandCursor)
        self.typologie_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.PRIMARY_COLOR};
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                padding: 2px 8px;
                font-weight: normal;
                font-size: 8pt;
            }}
            QPushButton:hover:enabled {{
                background: #F5F5F5;
                border-color: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: transparent;
                color: #CCCCCC;
                border-color: #E0E0E0;
            }}
        """)
        self.typologie_back_btn.clicked.connect(self._on_typologie_back)
        layout.addWidget(self.typologie_back_btn)


        # Bouton de retour pour la navigation hiérarchique
        self.typologie_back_btn = QtWidgets.QPushButton("← Retour")
        self.typologie_back_btn.setEnabled(False)
        self.typologie_back_btn.setCursor(Qt.PointingHandCursor)
        self.typologie_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.PRIMARY_COLOR};
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                padding: 2px 8px;
                font-weight: normal;
                font-size: 8pt;
            }}
            QPushButton:hover:enabled {{
                background: #F5F5F5;
                border-color: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: transparent;
                color: #CCCCCC;
                border-color: #E0E0E0;
            }}
        """)
        self.typologie_back_btn.clicked.connect(self._on_typologie_back)
        layout.addWidget(self.typologie_back_btn)
        
        self.typologie_info = QtWidgets.QLabel("Sélectionnez une génération")
        self.typologie_info.setAlignment(Qt.AlignCenter)
        self.typologie_info.setStyleSheet("color: #666; font-style: italic; border: none; font-size: 8pt;")
        layout.addWidget(self.typologie_info)

        return group

    def _create_batch_chart_group(self):
        """Crée le camembert de progression par batch"""
        group = QtWidgets.QGroupBox("Progression par Batch")
        group.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        layout = QtWidgets.QVBoxLayout(group)

        self.batch_series = QPieSeries()
        self.batch_series.setHoleSize(0.0)

        slice_default = self.batch_series.append("Aucune donnée", 1)
        slice_default.setColor(QColor("#E0E0E0"))
        slice_default.setBorderColor(Qt.transparent)
        slice_default.setLabelVisible(False)

        self.batch_chart = QChart()
        self.batch_chart.addSeries(self.batch_series)
        self.batch_chart.setTitle("Sélectionnez une génération")
        self.batch_chart.setTitleFont(QFont("Segoe UI", 11, QFont.Bold))
        self.batch_chart.setTitleBrush(QBrush(QColor("#1e293b")))

        self.batch_chart.legend().setVisible(True)
        self.batch_chart.legend().setAlignment(Qt.AlignBottom)
        self.batch_chart.legend().setFont(QFont("Segoe UI", 8))
        self.batch_chart.legend().setLabelColor(QColor("#1e293b"))
        self.batch_chart.legend().setBackgroundVisible(False)
        self.batch_chart.legend().setBorderColor(Qt.transparent)

        self.batch_chart.setBackgroundVisible(False)
        self.batch_chart.setBackgroundRoundness(0)
        self.batch_chart.setMargins(QtCore.QMargins(10, 10, 10, 10))
        self.batch_chart.setAnimationOptions(QChart.SeriesAnimations)

        self.batch_chart_view = QChartView(self.batch_chart)
        self.batch_chart_view.setRenderHint(QPainter.Antialiasing)
        self.batch_chart_view.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.batch_chart_view)

        # Bouton de retour pour la navigation hiérarchique
        self.batch_back_btn = QtWidgets.QPushButton("← Retour")
        self.batch_back_btn.setEnabled(False)
        self.batch_back_btn.setCursor(Qt.PointingHandCursor)
        self.batch_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.PRIMARY_COLOR};
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                padding: 2px 8px;
                font-weight: normal;
                font-size: 8pt;
            }}
            QPushButton:hover:enabled {{
                background: #F5F5F5;
                border-color: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: transparent;
                color: #CCCCCC;
                border-color: #E0E0E0;
            }}
        """)
        self.batch_back_btn.clicked.connect(self._on_batch_back)
        layout.addWidget(self.batch_back_btn)

        self.batch_info = QtWidgets.QLabel("Sélectionnez une génération")
        self.batch_info.setAlignment(Qt.AlignCenter)
        self.batch_info.setStyleSheet("color: #666; font-style: italic; border: none; font-size: 8pt;")
        layout.addWidget(self.batch_info)

        return group

    def _create_details_group(self):
        """Crée le groupe des détails (TRÈS COMPACT)"""
        group = QtWidgets.QGroupBox("Détails de la Génération")
        group.setFont(QFont("Segoe UI", 9, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        # Zone scrollable ultra-compacte
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setMaximumHeight(120)  # ✅ LIMITE DE HAUTEUR

        details_widget = QtWidgets.QWidget()
        
        self.details_layout = QtWidgets.QGridLayout(details_widget)
        self.details_layout.setAlignment(Qt.AlignTop)
        self.details_layout.setSpacing(3)
        self.details_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(details_widget)
        layout.addWidget(scroll)

        # Boutons d'action
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.addStretch()

        self.view_btn = QtWidgets.QPushButton("Voir tout")
        self.view_btn.setMinimumHeight(28)
        self.view_btn.setCursor(Qt.PointingHandCursor)
        self.view_btn.setEnabled(False)
        self.view_btn.clicked.connect(self._on_view_generation)
        self._apply_button_style(self.view_btn)
        actions_layout.addWidget(self.view_btn)

        self.delete_btn = QtWidgets.QPushButton("Supprimer")
        self.delete_btn.setMinimumHeight(28)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_generation)
        self._apply_button_style(self.delete_btn)
        actions_layout.addWidget(self.delete_btn)

        layout.addLayout(actions_layout)

        return group

    def _apply_button_style(self, button):
        """Applique le style aux boutons"""
        button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                min-width: 70px;
                font-size: 8pt;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)

    def set_database(self, database):
        """Définit la connexion à la base de données avec validation"""
        if database is None:
            return

        from utils.dataset_database import DatasetDatabase

        if isinstance(database, DatasetDatabase) and hasattr(database, 'get_all_generations'):
            self.database = database
            self.refresh_list()

    def refresh_list(self):
        """Actualise la liste"""
        if not self.database:
            return

        try:
            self.generations = self._fetch_generations()

            if not self.generations:
                self.count_label.setText("0 génération(s)")
                self.generations_list.clear()
                self.project_filter.clear()
                self.project_filter.addItem("Tous les projets", "")
                return

            self._update_filters()
            self._display_generations()

            count = len(self.generations)
            self.count_label.setText(f"{count} génération(s)")

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {str(e)}")
            logger.error(traceback.format_exc())

    def _fetch_generations(self):
        """Récupère les générations avec extraction des métadonnées ET calcul progression batch"""
        if not self.database:
            return []

        try:
            generations = self.database.get_all_generations(limit=100)
            display_generations = []
            
            logger.info(f"\n📋 FETCH GENERATIONS - {len(generations) if generations else 0} trouvées")
            
            for idx, gen in enumerate(generations):
                try:
                    if not gen.get('id') or not gen.get('project_name'):
                        continue
                    
                    gen_id = gen['id']
                    logger.info(f"\n=== Génération #{gen_id} === ")
                    
                    metadata = self._safe_parse_metadata(gen.get('metadata'))
                    logger.info(f"  Metadata keys: {list(metadata.keys()) if metadata else 'EMPTY'}")
                    
                    # Load the predefined batch composition
                    batch = self.database.get_batch(gen['project_name'], gen.get('batch_number'))
                    if batch:
                        batch_data = batch.get('data', {})
                        combinations = batch_data.get('combinations', [])
                        master_typologie = batch_data.get('master_typologie', {})
                        master_name = master_typologie.get('name', 'N/A')
                        display_combos = []
                        for combo in combinations:
                            contexts = combo.get('contexts', [])
                            nb_samples = combo.get('nb_samples', 1)
                            display_combo = {
                                'master': master_name,
                                'contexts': [{'level': ctx.get('level'), 'display': ctx.get('display'), 'data': ctx.get('data', {})} for ctx in contexts],
                                'nb_samples': nb_samples,
                                'master_data': master_typologie
                            }
                            display_combos.append(display_combo)

                        # Compute chart_data pour typologie
                        typologie_counts = {}
                        total_contexts = 0
                        for combo in display_combos:
                            master_name = combo.get('master', 'N/A')
                            if master_name != 'N/A':
                                if master_name not in typologie_counts:
                                    typologie_counts[master_name] = {'count': 0, 'level': 'master', 'data': combo.get('master_data', {})}
                                typologie_counts[master_name]['count'] += 1
                                total_contexts += 1
                            for ctx in combo['contexts']:
                                display = ctx.get('display', 'Inconnu')
                                level = ctx.get('level', 'unknown')
                                if display != 'Inconnu' and display != 'N/A':
                                    if display not in typologie_counts:
                                        typologie_counts[display] = {'count': 0, 'level': level, 'data': ctx['data']}
                                    typologie_counts[display]['count'] += 1
                                    total_contexts += 1

                        chart_data = []
                        for name, info in typologie_counts.items():
                            chart_data.append({
                                'name': name,
                                'samples': info['count'],
                                'level': info['level'],
                                'data': info['data']
                            })
                        logger.info(f"  Chart data (typologie): {len(chart_data)} entrées")
                    else:
                        chart_data = []
                        logger.warning(f"  Batch not found for generation {gen_id}")

                    # ✅ NOUVEAU: Calculer la progression par batch du projet
                    batch_progression_data = self._calculate_batch_progression(gen)

                    contexts_list = self._extract_contexts_from_generation(gen, metadata)
                    
                    status_map = {
                        'completed': 'Complété',
                        'failed': 'Échoué',
                        'running': 'En cours',
                        'pending': 'En attente'
                    }
                    status_raw = gen.get('status', 'unknown')
                    status = status_map.get(status_raw, status_raw.capitalize())

                    batch_number = gen.get('batch_number')
                    batch_name = gen.get('batch_name') or f"Batch {batch_number}" if batch_number else "N/A"

                    display_gen = {
                        "id": gen['id'],
                        "project": gen.get('project_name', 'Projet inconnu'),
                        "project_name": gen.get('project_name'),  # ✅ AJOUT pour le camembert de progression
                        "batch": batch_name,
                        "date": gen.get('started_at') or datetime.now().isoformat(),
                        "format": gen.get('output_format', 'JSON'),
                        "samples": gen.get('total_samples') or 0,
                        "combinations": gen.get('total_combinations') or 0,
                        "master": gen.get('master_typologie_name') or "N/A",
                        "status": status,
                        "status_raw": status_raw,
                        "duration": gen.get('duration_seconds'),
                        "output_file": gen.get('output_file_path'),
                        "error": gen.get('error_message'),
                        "contexts": contexts_list,
                        "metadata": metadata,
                        "chart_data": chart_data,
                        "batch_progression": batch_progression_data  # ✅ NOUVEAU
                    }

                    logger.info(f"  ✅ Génération ajoutée: {display_gen['project']} - {display_gen['batch']}")
                    display_generations.append(display_gen)

                except Exception as gen_error:
                    logger.error(f"❌ Erreur génération #{idx}: {gen_error}")
                    logger.error(traceback.format_exc())
                    continue
            
            logger.info(f"\n✅ Total générations traitées: {len(display_generations)}")
            return display_generations

        except Exception as e:
            logger.error(f"❌ Erreur récupération: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def _calculate_batch_progression(self, gen):
        """
        ✅ CORRIGÉ: Calcule la progression de génération par FAMILLE de batch
        Retourne les données pour le camembert de progression
        """
        try:
            project_name = gen.get('project_name')
            if not project_name:
                return []

            # Récupérer TOUS les batches du projet
            all_batches = self.database.get_all_batches(project_name)

            if not all_batches:
                return []

            # Récupérer TOUTES les générations du projet
            all_project_gens = self.database.get_all_generations(project_name=project_name, limit=1000)

            # Organiser par famille de batch
            family_stats = {}

            for batch in all_batches:
                batch_num = batch['batch_number']
                batch_data = batch.get('data', {})

                # ✅ NOUVEAU: Récupérer la famille de batch
                batch_family = batch_data.get('batch_family', 'Sans famille')
                if not batch_family or batch_family.strip() == '':
                    batch_family = 'Sans famille'

                combinations = batch_data.get('combinations', [])

                # Calculer le total de samples prévus pour ce batch
                total_expected = sum(combo.get('nb_samples', 1) for combo in combinations)

                # Chercher si ce batch a été généré
                generated = 0
                for pg in all_project_gens:
                    if pg.get('batch_number') == batch_num and pg.get('status') == 'completed':
                        generated = pg.get('total_samples', 0)
                        break
                    
                # Agréger par famille
                if batch_family not in family_stats:
                    family_stats[batch_family] = {
                        'expected': 0,
                        'generated': 0,
                        'batch_count': 0,
                        'completed_batches': 0,
                        'batch_numbers': []
                    }

                family_stats[batch_family]['expected'] += total_expected
                family_stats[batch_family]['generated'] += generated
                family_stats[batch_family]['batch_count'] += 1
                family_stats[batch_family]['batch_numbers'].append(batch_num)

                if generated >= total_expected and total_expected > 0:
                    family_stats[batch_family]['completed_batches'] += 1

            # Créer les données pour le camembert
            progression_data = []
            for family_name in sorted(family_stats.keys()):
                stats = family_stats[family_name]
                percentage = (stats['generated'] / stats['expected'] * 100) if stats['expected'] > 0 else 0

                # Déterminer le statut de la famille
                if stats['completed_batches'] == stats['batch_count'] and stats['batch_count'] > 0:
                    status = 'completed'
                elif stats['generated'] > 0:
                    status = 'partial'
                else:
                    status = 'pending'

                progression_data.append({
                    'family_name': family_name,
                    'expected': stats['expected'],
                    'generated': stats['generated'],
                    'percentage': percentage,
                    'batch_count': stats['batch_count'],
                    'completed_batches': stats['completed_batches'],
                    'batch_numbers': stats['batch_numbers'],
                    'status': status
                })

            logger.info(f"📊 Progression par famille calculée: {len(progression_data)} famille(s)")
            for fam in progression_data:
                logger.info(f"  • {fam['family_name']}: {fam['generated']}/{fam['expected']} "
                           f"({fam['completed_batches']}/{fam['batch_count']} batches) - {fam['status']}")

            return progression_data

        except Exception as e:
            logger.error(f"Erreur calcul progression: {e}")
            logger.error(traceback.format_exc())
            return []

    def _extract_contexts_from_generation(self, gen, metadata):
        """Extrait les contextes depuis une génération pour la vue détaillée"""
        contexts = []

        if 'combinations' in metadata and isinstance(metadata['combinations'], list):
            for combo in metadata['combinations']:
                if not isinstance(combo, dict):
                    continue
                
                master_info = combo.get('master', {})
                if isinstance(master_info, dict):
                    master_name = master_info.get('name', 'N/A')
                    contexts.append(f"Master: {master_name}")

                combo_contexts = combo.get('contexts', [])
                if isinstance(combo_contexts, list):
                    for ctx in combo_contexts:
                        if isinstance(ctx, dict):
                            ctx_display = ctx.get('display') or ctx.get('level') or 'N/A'
                            contexts.append(f"• {ctx_display}")
                            
        if not contexts and gen.get('master_typologie_name'):
            contexts.append(f"Master: {gen['master_typologie_name']}")

        if not contexts:
            contexts.append("Aucun contexte disponible")

        return contexts
        
    def _safe_parse_metadata(self, metadata_value):
        """Parse les métadonnées de manière sécurisée avec logging"""
        if not metadata_value:
            logger.debug("  Metadata vide")
            return {}

        if isinstance(metadata_value, dict):
            logger.debug(f"  Metadata dict avec {len(metadata_value)} clés")
            return metadata_value

        if isinstance(metadata_value, str):
            try:
                parsed = json.loads(metadata_value)
                logger.debug(f"  Metadata parsée: {len(parsed)} clés")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"  ❌ Erreur JSON: {e}")
                return {}

        logger.warning(f"  ⚠️ Type metadata inconnu: {type(metadata_value)}")
        return {}

    def _update_filters(self):
        """Met à jour les options de filtres"""
        try:
            projects = set()
            for g in self.generations:
                project_name = g.get("project")
                if project_name and isinstance(project_name, str):
                    projects.add(project_name)

            current_project = self.project_filter.currentData()

            self.project_filter.clear()
            self.project_filter.addItem("Tous les projets", "")

            for project in sorted(projects):
                self.project_filter.addItem(project, project)

            if current_project:
                index = self.project_filter.findData(current_project)
                if index >= 0:
                    self.project_filter.setCurrentIndex(index)

        except Exception as e:
            logger.error(f"Erreur mise à jour filtres: {e}")

    def _display_generations(self):
        """Affiche les générations sans icônes"""
        self.generations_list.clear()

        filtered = self._apply_filters()

        for gen in filtered:
            item = QtWidgets.QListWidgetItem()
            
            date_str = datetime.fromisoformat(gen["date"]).strftime("%d/%m/%Y %H:%M")
            
            line1 = f"{gen['project']} - {gen['batch']}"
            line2 = f"{gen['status']} - {date_str} - {gen['format']} - {gen['samples']} samples"
            
            text = f"{line1}\n{line2}"
            
            item.setText(text)
            item.setData(Qt.UserRole, gen["id"])
            
            font = QFont("Segoe UI", 9)
            item.setFont(font)
            
            self.generations_list.addItem(item)

    def _apply_filters(self):
        """Applique les filtres"""
        filtered = self.generations

        project = self.project_filter.currentData()
        if project:
            filtered = [g for g in filtered if g["project"] == project]

        format_text = self.format_filter.currentText()
        if format_text != "Tous les formats":
            filtered = [g for g in filtered if g["format"] == format_text]

        status_text = self.status_filter.currentText()
        if status_text != "Tous les statuts":
            status_map = {
                "Complété": "completed",
                "Échoué": "failed",
                "En cours": "running"
            }
            status_filter = status_map.get(status_text)
            if status_filter:
                filtered = [g for g in filtered if g.get("status_raw") == status_filter]

        search = self.search_edit.text().strip().lower()
        if search:
            filtered = [
                g for g in filtered
                if search in g["project"].lower()
                or search in g["batch"].lower()
                or search in g["date"].lower()
                or search in g.get("master", "").lower()
            ]

        return filtered

    def _on_filter_changed(self):
        """Gère le changement des filtres"""
        self._display_generations()

    def _on_selection_changed(self):
        """Gère le changement de sélection"""
        selected = self.generations_list.selectedItems()
        
        if not selected:
            self._clear_details()
            self.view_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        gen_id = selected[0].data(Qt.UserRole)
        generation = next((g for g in self.generations if g["id"] == gen_id), None)

        if generation:
            self.current_generation_id = gen_id
            self._display_details(generation)
            self._update_typologie_chart(generation)
            self._update_batch_chart(generation)  # ✅ NOUVEAU
            self.view_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.generation_selected.emit(gen_id)

    def _clear_details(self):
        """Efface les détails"""
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.typologie_chart.removeAllSeries()
        self.batch_chart.removeAllSeries()
        self.typologie_info.setText("Sélectionnez une génération")
        self.batch_info.setText("Sélectionnez une génération")

    def _display_details(self, generation):
        """Affiche les détails en mode ULTRA-COMPACT"""
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Informations essentielles seulement
        info_data = [
            ("Projet", generation["project"]),
            ("Batch", generation["batch"]),
            ("Date", datetime.fromisoformat(generation["date"]).strftime("%d/%m/%Y")),
            ("Samples", str(generation["samples"])),
            ("Format", generation["format"]),
            ("Statut", generation["status"])
        ]
        
        row = 0
        col = 0
        max_cols = 3  # ✅ 3 colonnes pour plus de compacité

        for label, value in info_data:
            container = QtWidgets.QWidget()
            h_layout = QtWidgets.QHBoxLayout(container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(4)

            lbl = QtWidgets.QLabel(f"{label}:")
            lbl.setStyleSheet("font-weight: bold; color: #333; font-size: 8pt; border: none;")
            h_layout.addWidget(lbl)

            val = ElidedLabel(value)
            val.setStyleSheet("color: #555; font-size: 8pt; border: none;")
            h_layout.addWidget(val, 1)

            self.details_layout.addWidget(container, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        if generation.get("error"):
            row += 1
            error_label = QtWidgets.QLabel("Erreur:")
            error_label.setStyleSheet("font-weight: bold; color: #D32F2F; font-size: 8pt; border: none;")
            self.details_layout.addWidget(error_label, row, 0, 1, 3)
            
            row += 1
            error_text = QtWidgets.QLabel(generation["error"][:100] + "...")  # ✅ Tronquer
            error_text.setStyleSheet("color: #D32F2F; padding: 3px; background: #FFEBEE; border-radius: 3px; font-size: 8pt;")
            error_text.setWordWrap(True)
            self.details_layout.addWidget(error_text, row, 0, 1, 3)

    def _update_typologie_chart(self, generation):
        """Met à jour le camembert des typologies avec navigation hiérarchique PROGRESSIVE"""
        chart_data = generation.get("chart_data", [])
        total_samples = generation.get("samples", 0)
        
        # Réinitialiser l'état hiérarchique avec les nouvelles données
        self.hierarchical_state.reset(chart_data, total_samples)
        
        # Afficher le niveau initial (typologies uniquement)
        self._render_typologie_chart()
    
    def _render_typologie_chart(self):
        """Rend le camembert au niveau hiérarchique actuel - PROGRESSIF"""
        self.typologie_chart.removeAllSeries()
        self.typologie_series = QPieSeries()
        self.typologie_series.setHoleSize(0.0)
        
        current_data = self.hierarchical_state.get_current_data()
        
        if not current_data:
            slice_default = self.typologie_series.append("Aucune donnée", 1)
            slice_default.setColor(QColor("#E0E0E0"))
            slice_default.setBorderColor(Qt.transparent)
            slice_default.setLabelVisible(False)
            self.typologie_chart.addSeries(self.typologie_series)
            self.typologie_info.setText("Aucune donnée")
            self.typologie_chart.setTitle("Aucune donnée")
            if hasattr(self, 'typologie_back_btn'):
                self.typologie_back_btn.setEnabled(False)
            return
        
        colors = [
            "#e63946", "#f77f00", "#fcbf49", "#06d6a0", "#118ab2",
            "#073b4c", "#d62828", "#f77f00", "#3a86ff", "#8338ec",
            "#ff6b6b", "#ee5a6f", "#fca311", "#e85d04", "#4ecdc4"
        ]
        
        for i, item in enumerate(current_data):
            samples = item.get('samples', 0)
            name = item.get('name', 'Inconnu')
            full_path = item.get('full_path', name)
            has_children = item.get('has_children', False)
            
            slice_obj = self.typologie_series.append(name, samples)
            color = QColor(colors[i % len(colors)])
            slice_obj.setColor(color)
            slice_obj.setBorderColor(Qt.transparent)
            
            percentage = (samples / self.hierarchical_state.total_samples) * 100 if self.hierarchical_state.total_samples > 0 else 0
            
            slice_obj.setLabelVisible(True)
            slice_obj.setLabelPosition(QPieSlice.LabelOutside)
            slice_obj.setLabelArmLengthFactor(0.12)
            slice_obj.setLabelColor(QColor("#1e293b"))
            slice_obj.setLabelFont(QFont("Segoe UI", 8, QFont.Bold))
            
            # Indicateur visuel si l'élément a des enfants
            if has_children:
                slice_obj.setLabel(f"{name} {percentage:.1f}%")
                # Connecter le clic uniquement si il y a des enfants
                slice_obj.clicked.connect(lambda checked=False, n=name, fp=full_path: self._on_slice_clicked(n, fp))
                slice_obj.hovered.connect(lambda state, s=slice_obj: self._on_slice_hovered(state, s))
            else:
                slice_obj.setLabel(f"{name} {percentage:.1f}%")
        
        self.typologie_chart.addSeries(self.typologie_series)
        
        # Mettre à jour le titre avec le fil d'Ariane
        breadcrumb = self.hierarchical_state.get_breadcrumb()
        self.typologie_chart.setTitle(breadcrumb)
        
        # Info avec nombre d'éléments affichés
        level_name = ["Typologies", "Clusters", "Labels"][min(self.hierarchical_state.current_level, 2)]
        self.typologie_info.setText(f"{len(current_data)} {level_name} - {self.hierarchical_state.total_samples} samples totaux")
        
        # Activer/désactiver le bouton retour
        if hasattr(self, 'typologie_back_btn'):
            self.typologie_back_btn.setEnabled(self.hierarchical_state.can_go_back())
    
    def _on_slice_clicked(self, name, full_path):
        """Gère le clic sur une part du camembert - Navigation progressive"""
        self.hierarchical_state.navigate_to(name, full_path)
        self._render_typologie_chart()
    
    def _on_slice_hovered(self, state, slice_obj):
        """Gère le survol d'une part"""
        if state:
            slice_obj.setExploded(True)
            slice_obj.setExplodeDistanceFactor(0.06)
        else:
            slice_obj.setExploded(False)
    
    def _on_typologie_back(self):
        """Retourne au niveau précédent dans la hiérarchie"""
        if self.hierarchical_state.navigate_back():
            self._render_typologie_chart()

    def _update_batch_chart(self, generation):
        """
        ✅ CORRIGÉ: Met à jour le camembert de progression avec navigation hiérarchique
        Niveau 0: Affiche les familles
        Niveau 1: Affiche les batches individuels de la famille sélectionnée
        """
        from utils.logger import logger
        
        batch_progression = generation.get("batch_progression", [])
        
        # Réinitialiser l'état avec les nouvelles données
        self.batch_progression_state.reset(batch_progression)
        
        # Récupérer le projet pour les détails des batches
        project_name = generation.get('project_name')
        
        logger.info(f"📊 _update_batch_chart: project_name from generation = '{project_name}' (type: {type(project_name)})")
        logger.info(f"📊 _update_batch_chart: generation keys = {list(generation.keys())}")
        
        # Validation et nettoyage
        if project_name is None or project_name == 'None' or project_name == '':
            logger.error(f"❌ project_name invalide: '{project_name}'")
            # Essayer de récupérer depuis self.current_generation_id
            if self.current_generation_id:
                for gen in self.generations:
                    if gen.get('id') == self.current_generation_id:
                        project_name = gen.get('project_name')
                        logger.info(f"📊 project_name récupéré depuis generations: '{project_name}'")
                        break
        
        self.current_project_name = project_name if project_name and project_name != 'None' else None
        logger.info(f"✅ self.current_project_name défini: '{self.current_project_name}'")
        
        # Rendre le camembert
        self._render_batch_chart()
    
    def _render_batch_chart(self):
        """
        Rend le camembert de progression selon le niveau hiérarchique actuel
        """
        self.batch_chart.removeAllSeries()
        self.batch_series = QPieSeries()
        self.batch_series.setHoleSize(0.0)
        
        current_data = self.batch_progression_state.get_current_data()
        
        if not current_data:
            slice_default = self.batch_series.append("Aucune donnée", 1)
            slice_default.setColor(QColor("#E0E0E0"))
            slice_default.setBorderColor(Qt.transparent)
            slice_default.setLabelVisible(False)
            self.batch_chart.addSeries(self.batch_series)
            self.batch_info.setText("Aucune donnée de batch")
            self.batch_chart.setTitle("Aucune donnée")
            if hasattr(self, 'batch_back_btn'):
                self.batch_back_btn.setEnabled(False)
            return

        # Palette de couleurs (gris clair)
        status_colors = {
            'completed': ["#B0BEC5", "#CFD8DC"],  # Gris clair, gris très clair
            'partial': ["#90A4AE", "#B0BEC5"],     # Gris moyen, gris clair
            'pending': ["#757575", "#BDBDBD"]      # Gris foncé, gris clair
        }
        
        if self.batch_progression_state.current_level == 0:
            # Niveau 0: Afficher les familles
            self._render_family_level(current_data, status_colors)
        else:
            # Niveau 1: Afficher les batches individuels
            self._render_batch_level(current_data, status_colors)
        
        # Activer/désactiver le bouton retour
        if hasattr(self, 'batch_back_btn'):
            self.batch_back_btn.setEnabled(self.batch_progression_state.can_go_back())
    
    def _render_family_level(self, family_data, status_colors):
        """Rend le camembert au niveau des familles"""
        # Calculer le total pour les proportions
        total_expected = sum(f['expected'] for f in family_data)
        total_generated = sum(f['generated'] for f in family_data)

        # Créer une part pour chaque famille
        for idx, family_info in enumerate(family_data):
            family_name = family_info['family_name']
            generated = family_info['generated']
            expected = family_info['expected']
            percentage = family_info['percentage']
            batch_count = family_info['batch_count']
            completed = family_info['completed_batches']
            status = family_info['status']
            batch_numbers = family_info.get('batch_numbers', [])

            # Choisir la couleur selon le statut
            colors = status_colors.get(status, status_colors['pending'])
            color = QColor(colors[idx % len(colors)])

            # Valeur pour la part
            slice_value = generated if generated > 0 else (expected * 0.05)

            # Créer la part
            slice_obj = self.batch_series.append(family_name, slice_value)

            slice_obj.setColor(color)
            slice_obj.setBorderColor(Qt.transparent)
            slice_obj.setLabelVisible(True)
            slice_obj.setLabelPosition(QPieSlice.LabelOutside)
            slice_obj.setLabelArmLengthFactor(0.15)
            slice_obj.setLabelColor(QColor("#1e293b"))
            slice_obj.setLabelFont(QFont("Segoe UI", 8, QFont.Bold))

            # Label avec informations détaillées
            slice_obj.setLabel(
                f"{family_name}\n"
                f"{percentage:.0f}% ({generated}/{expected})\n"
                f"{completed}/{batch_count} batches"
            )

            # Mettre en surbrillance les familles complétées
            if status == 'completed':
                slice_obj.setExploded(True)
                slice_obj.setExplodeDistanceFactor(0.05)

            # Effet au survol
            slice_obj.hovered.connect(
                lambda state, s=slice_obj: self._on_batch_slice_hovered(state, s)
            )
            
            # Gestionnaire de clic pour naviguer vers les batches de la famille
            slice_obj.clicked.connect(
                lambda checked=False, fi=family_info: self._on_family_clicked(fi)
            )

        self.batch_chart.addSeries(self.batch_series)

        # Calculer la progression globale
        overall_percentage = (total_generated / total_expected * 100) if total_expected > 0 else 0

        # Compter les familles par statut
        completed_families = sum(1 for f in family_data if f['status'] == 'completed')
        total_families = len(family_data)

        # Titre avec fil d'Ariane
        breadcrumb = self.batch_progression_state.get_breadcrumb()
        self.batch_chart.setTitle(breadcrumb)

        # Info détaillée par famille
        family_details = []
        for f in family_data:
            status_icon = "✅" if f['status'] == 'completed' else "🔄" if f['status'] == 'partial' else "⏳"
            family_details.append(
                f"{f['family_name']}: {f['generated']}/{f['expected']} "
                f"({f['completed_batches']}/{f['batch_count']}B) {status_icon}"
            )

        self.batch_info.setText(" | ".join(family_details) if family_details else "Aucune donnée")
    
    def _render_batch_level(self, batch_details, status_colors):
        """Rend le camembert au niveau des batches individuels"""
        from utils.logger import logger
        
        logger.info(f"🎨 _render_batch_level: {len(batch_details)} batches à afficher")
        
        if not batch_details:
            logger.warning("⚠️  batch_details est vide!")
            return
        
        # Créer une part pour chaque batch
        for idx, batch_info in enumerate(batch_details):
            batch_number = batch_info['batch_number']
            generated = batch_info['generated']
            expected = batch_info['expected']
            status = batch_info['status']
            percentage = (generated / expected * 100) if expected > 0 else 0
            
            logger.info(f"  • Batch {batch_number}: {generated}/{expected} ({percentage:.0f}%) - {status}")

            # Choisir la couleur selon le statut
            colors = status_colors.get(status, status_colors['pending'])
            color = QColor(colors[idx % len(colors)])

            # Valeur pour la part
            slice_value = generated if generated > 0 else (expected * 0.05)

            # Créer la part
            slice_obj = self.batch_series.append(f"Batch {batch_number}", slice_value)

            slice_obj.setColor(color)
            slice_obj.setBorderColor(Qt.transparent)
            slice_obj.setLabelVisible(True)
            slice_obj.setLabelPosition(QPieSlice.LabelOutside)
            slice_obj.setLabelArmLengthFactor(0.15)
            slice_obj.setLabelColor(QColor("#1e293b"))
            slice_obj.setLabelFont(QFont("Segoe UI", 8, QFont.Bold))

            # Label avec informations
            status_icon = "✅" if status == 'completed' else "🔄" if status == 'partial' else "⏳"
            slice_obj.setLabel(
                f"Batch {batch_number}\n"
                f"{percentage:.0f}% ({generated}/{expected})\n"
                f"{status_icon}"
            )

            # Mettre en surbrillance les batches complétés
            if status == 'completed':
                slice_obj.setExploded(True)
                slice_obj.setExplodeDistanceFactor(0.05)

            # Effet au survol
            slice_obj.hovered.connect(
                lambda state, s=slice_obj: self._on_batch_slice_hovered(state, s)
            )

        self.batch_chart.addSeries(self.batch_series)

        # Titre avec fil d'Ariane
        breadcrumb = self.batch_progression_state.get_breadcrumb()
        self.batch_chart.setTitle(breadcrumb)

        # Info détaillée par batch
        batch_details_text = []
        for b in batch_details:
            status_icon = "✅" if b['status'] == 'completed' else "🔄" if b['status'] == 'partial' else "⏳"
            percentage_text = f"{(b['generated']/b['expected']*100):.0f}%" if b['expected'] > 0 else "0%"
            batch_details_text.append(
                f"B{b['batch_number']}: {b['generated']}/{b['expected']} ({percentage_text}) {status_icon}"
            )

        self.batch_info.setText(" | ".join(batch_details_text) if batch_details_text else "Aucune donnée")

    def _on_batch_slice_hovered(self, state, slice_obj):
        """Gère le survol d'une part du camembert de batch"""
        if state:
            slice_obj.setExploded(True)
            slice_obj.setExplodeDistanceFactor(0.08)
        else:
            # Ne remettre à zéro que si ce n'est pas une famille completed
            if not slice_obj.isExploded() or slice_obj.explodeDistanceFactor() > 0.05:
                slice_obj.setExplodeDistanceFactor(0.05)
    
    def _on_family_clicked(self, family_data):
        """
        Gère le clic sur une portion du camembert de progression
        Navigue vers les détails des batches de la famille
        """
        from utils.logger import logger
        
        family_name = family_data['family_name']
        batch_numbers = family_data.get('batch_numbers', [])
        
        logger.info(f"🔍 _on_family_clicked: famille='{family_name}', batch_numbers={batch_numbers}")
        
        if not batch_numbers:
            logger.warning(f"⚠️  Aucun batch_numbers pour la famille '{family_name}'")
            return
        
        # Récupérer les détails des batches de cette famille
        batch_details = []
        
        logger.info(f"📊 current_project_name='{getattr(self, 'current_project_name', None)}'")
        logger.info(f"📊 database={self.database}")
        
        if hasattr(self, 'current_project_name') and self.current_project_name and self.database:
            logger.info(f"✅ Récupération des batches pour le projet '{self.current_project_name}'")
            
            all_batches = self.database.get_all_batches(self.current_project_name)
            logger.info(f"📦 Nombre total de batches récupérés: {len(all_batches)}")
            
            all_project_gens = self.database.get_all_generations(project_name=self.current_project_name, limit=1000)
            logger.info(f"📋 Nombre total de générations récupérées: {len(all_project_gens)}")
            
            # Filtrer les batches de cette famille
            for batch in all_batches:
                if batch['batch_number'] in batch_numbers:
                    logger.info(f"  ✅ Batch {batch['batch_number']} trouvé dans la famille")
                    
                    batch_data = batch.get('data', {})
                    combinations = batch_data.get('combinations', [])
                    total_expected = sum(combo.get('nb_samples', 1) for combo in combinations)
                    
                    logger.info(f"    • Expected samples: {total_expected}")
                    
                    # Trouver la génération correspondante
                    generated = 0
                    gen_status = 'pending'
                    for pg in all_project_gens:
                        if pg.get('batch_number') == batch['batch_number'] and pg.get('status') == 'completed':
                            generated = pg.get('total_samples', 0)
                            gen_status = 'completed'
                            logger.info(f"    • Génération completed trouvée: {generated} samples")
                            break
                    
                    if generated == 0:
                        # Vérifier s'il y a une génération en cours
                        for pg in all_project_gens:
                            if pg.get('batch_number') == batch['batch_number'] and pg.get('status') in ['running', 'partial']:
                                generated = pg.get('total_samples', 0)
                                gen_status = 'partial'
                                logger.info(f"    • Génération partielle trouvée: {generated} samples")
                                break
                    
                    batch_details.append({
                        'batch_number': batch['batch_number'],
                        'expected': total_expected,
                        'generated': generated,
                        'status': gen_status
                    })
            
            # Trier par numéro de batch
            batch_details.sort(key=lambda x: x['batch_number'])
            logger.info(f"📊 Total batch_details créés: {len(batch_details)}")
            for bd in batch_details:
                logger.info(f"  • Batch {bd['batch_number']}: {bd['generated']}/{bd['expected']} ({bd['status']})")
        else:
            logger.error(f"❌ Impossible de récupérer les batches:")
            logger.error(f"   • hasattr current_project_name: {hasattr(self, 'current_project_name')}")
            logger.error(f"   • current_project_name: {getattr(self, 'current_project_name', 'NON DEFINI')}")
            logger.error(f"   • database: {self.database}")
        
        logger.info(f"🔄 Navigation vers famille '{family_name}' avec {len(batch_details)} batches")
        
        # Naviguer vers le niveau des batches
        self.batch_progression_state.navigate_to_family(family_name, batch_details)
        self._render_batch_chart()
    
    def _on_batch_back(self):
        """Retourne au niveau précédent (familles)"""
        if self.batch_progression_state.navigate_back():
            self._render_batch_chart()

    def _on_view_generation(self):
        """Affiche les détails complets"""
        if not self.current_generation_id:
            return

        generation = next((g for g in self.generations if g["id"] == self.current_generation_id), None)
        if not generation:
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Génération #{self.current_generation_id}")
        dialog.resize(700, 500)
        dialog.setStyleSheet(f"background: white;")

        layout = QtWidgets.QVBoxLayout(dialog)

        title = QtWidgets.QLabel(f"<h2>{generation['project']} - {generation['batch']}</h2>")
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        layout.addWidget(title)

        details = QtWidgets.QTextEdit()
        details.setReadOnly(True)
        
        details_text = f"""
=== INFORMATIONS GÉNÉRALES ===
Projet: {generation['project']}
Batch: {generation['batch']}
Master typologie: {generation['master']}
Date: {generation['date']}
Statut: {generation['status']}
Format: {generation['format']}

=== STATISTIQUES ===
Total samples: {generation['samples']}
Total combinaisons: {generation['combinations']}
Durée: {generation.get('duration', 'N/A')}s

=== ANALYSE DE REPRÉSENTATIVITÉ ===
Données utilisées pour le graphique (Typologie de Contexte - Samples):
{chr(10).join([f"- {d['name']}: {d['samples']}" for d in generation.get('chart_data', [])])}

=== PROGRESSION PAR BATCH ===
{chr(10).join([f"- Batch {b['batch_number']}: {b['generated']}/{b['expected']} ({b['percentage']:.1f}%)" for b in generation.get('batch_progression', [])])}

=== CONTEXTES DÉTAILLÉS ===
{chr(10).join(generation.get('contexts', ['Aucun contexte']))}

=== FICHIER DE SORTIE ===
{generation.get('output_file', 'Non disponible')}
"""

        if generation.get('error'):
            details_text += f"\n=== ERREUR ===\n{generation['error']}\n"

        details.setPlainText(details_text)
        layout.addWidget(details)

        buttons_layout = QtWidgets.QHBoxLayout()
        
        copy_btn = QtWidgets.QPushButton("Copier")
        copy_btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(details_text))
        self._apply_button_style(copy_btn)
        buttons_layout.addWidget(copy_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.clicked.connect(dialog.close)
        self._apply_button_style(close_btn)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)

        dialog.exec_()

    def _on_delete_generation(self):
        """Supprime une génération de l'historique"""
        if not self.current_generation_id:
            return

        generation = next((g for g in self.generations if g["id"] == self.current_generation_id), None)
        if not generation:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Voulez-vous vraiment supprimer cette génération ?\n\n"
            f"Projet: {generation['project']}\n"
            f"Batch: {generation['batch']}\n"
            f"Cette action est irréversible !",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            cursor = self.database.connection.cursor()
            cursor.execute("DELETE FROM dataset_generations WHERE id = ?", (self.current_generation_id,))
            self.database.connection.commit()

            self.generation_deleted.emit(self.current_generation_id)
            self.refresh_list()

            QtWidgets.QMessageBox.information(
                self,
                "Suppression réussie",
                f"La génération #{self.current_generation_id} a été supprimée."
            )

        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de supprimer la génération:\n\n{str(e)}"
            )

    def _on_export_history(self):
        """Exporte l'historique"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter l'historique",
            f"historique_generations_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON (*.json);;CSV (*.csv)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                export_data = self.generations
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            else:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'id', 'project', 'batch', 'date', 'format', 
                        'samples', 'combinations', 'master', 'status'
                    ])
                    writer.writeheader()
                    for gen in self.generations:
                        row = {
                            'id': gen['id'],
                            'project': gen['project'],
                            'batch': gen['batch'],
                            'date': gen['date'],
                            'format': gen['format'],
                            'samples': gen['samples'],
                            'combinations': gen['combinations'],
                            'master': gen['master'],
                            'status': gen['status']
                        }
                        writer.writerow(row)

            QtWidgets.QMessageBox.information(
                self,
                "Export réussi",
                f"Historique exporté vers:\n{file_path}"
            )

        except Exception as e:
            logger.error(f"Erreur export: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'exporter:\n{str(e)}"
            )

    def update_language(self):
        """Met à jour les textes après changement de langue"""
        pass

PromptList = DatasetHistoryWidget