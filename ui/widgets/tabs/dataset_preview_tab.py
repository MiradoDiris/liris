#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

from ui.localization.translator import tr
from ui.styles.theme import Theme

from utils.logger import logger

import logging
import os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice, QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis

from ui.localization.translator import tr
from ui.styles.theme import Theme



class DatasetPreviewTab(QtWidgets.QWidget):
    """Dataset preview tab - Visualisation et analyse des batches et combinaisons"""

    def __init__(self, project_manager, config_data=None, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data or {}
        self.current_batch_data = None
        self.current_project_data = None
        self._init_ui()

    def _init_ui(self):
        """Create dataset preview tab with sub-tabs"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header avec sélection de projet et batch
        header_layout = self._create_header()
        layout.addLayout(header_layout)

        # Onglets de l'aperçu
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet(self._get_tab_style())

        # 1. Vue d'ensemble
        self.overview_tab = self._create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "Vue d'ensemble")

        # 2. Structure des combinaisons
        self.structure_tab = self._create_structure_tab()
        self.tab_widget.addTab(self.structure_tab, "Structure")

        layout.addWidget(self.tab_widget)

        # Définir l'onglet Vue d'ensemble comme actif par défaut
        self.tab_widget.setCurrentIndex(0)

    def _create_header(self):
        """Create header with project and batch selection"""
        layout = QtWidgets.QHBoxLayout()

        # Sélection du projet
        select_label = QtWidgets.QLabel("Projet:")
        select_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #2c3e50;")
        layout.addWidget(select_label)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.project_combo.setMaximumWidth(250)
        layout.addWidget(self.project_combo)

        layout.addSpacing(15)

        # Sélection du batch
        batch_label = QtWidgets.QLabel("Batch:")
        batch_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #2c3e50;")
        layout.addWidget(batch_label)

        self.batch_combo = QtWidgets.QComboBox()
        self.batch_combo.setStyleSheet(self._get_modern_input_style())
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self.batch_combo.setMaximumWidth(250)
        layout.addWidget(self.batch_combo)

        layout.addSpacing(15)

        # Bouton refresh
        refresh_btn = QtWidgets.QPushButton("🔄")
        refresh_btn.setStyleSheet(self._get_button_style())
        refresh_btn.clicked.connect(self.refresh_projects)
        refresh_btn.setFixedSize(35, 35)
        refresh_btn.setToolTip("Actualiser")
        layout.addWidget(refresh_btn)

        layout.addStretch()

        return layout

    def _create_overview_tab(self):
        """Create overview tab - Simple and clear project information"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # ✅ Layout horizontal pour 3 colonnes
        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(10)

        # ✅ Colonne 1 : Informations générales
        info_group = self._create_modern_card("📄 Projet")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        info_layout.setContentsMargins(10, 15, 10, 10)

        self.project_info_label = QtWidgets.QLabel("Aucun projet sélectionné")
        self.project_info_label.setStyleSheet("""
            QLabel {
                background-color: white;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
                color: #2c3e50;
                line-height: 1.5;
            }
        """)
        self.project_info_label.setWordWrap(True)
        info_layout.addWidget(self.project_info_label)
        info_layout.addStretch()

        columns_layout.addWidget(info_group, 1)

        # ✅ Colonne 2 : Liste des typologies avec leurs taxonomies
        typo_group = self._create_modern_card("🎯 Typologies")
        typo_layout = QtWidgets.QVBoxLayout(typo_group)
        typo_layout.setContentsMargins(10, 15, 10, 10)

        # Arbre hiérarchique SIMPLE
        self.typologie_tree = QtWidgets.QTreeWidget()
        self.typologie_tree.setHeaderLabels(["Nom", "Contenu"])
        self.typologie_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f5f5f5;
            }
            QTreeWidget::item:selected {
                background-color: #e8f5e9;
                color: #2c3e50;
            }
        """)
        self.typologie_tree.setAlternatingRowColors(False)
        typo_layout.addWidget(self.typologie_tree, 1)

        columns_layout.addWidget(typo_group, 1)

        # ✅ Colonne 3 : Batches disponibles
        batch_group = self._create_modern_card("📦 Batches")
        batch_layout = QtWidgets.QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(10, 15, 10, 10)

        self.batch_list_widget = QtWidgets.QListWidget()
        self.batch_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f5f5f5;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #2c3e50;
            }
        """)
        batch_layout.addWidget(self.batch_list_widget, 1)

        columns_layout.addWidget(batch_group, 1)

        # Ajouter le layout des colonnes au layout principal
        layout.addLayout(columns_layout, 1)

        return widget
    
    def _count_children_recursive(self, children):
        """Recursively count all children in a hierarchical structure"""
        if not children:
            return 0
        
        count = len(children)
        
        for child in children:
            if isinstance(child, dict) and 'children' in child:
                count += self._count_children_recursive(child.get('children', []))
        
        return count

    def _create_structure_tab(self):
        """Create structure tab - Visualisation de la composition du batch"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Message si aucun batch sélectionné
        self.no_batch_label = QtWidgets.QLabel("Veuillez sélectionner un batch pour visualiser sa composition")
        self.no_batch_label.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 6px;
                padding: 15px;
                font-size: 13px;
                color: #856404;
                text-align: center;
            }
        """)
        self.no_batch_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.no_batch_label)

        # Container pour le graphique (caché par défaut)
        self.batch_composition_container = QtWidgets.QWidget()
        self.batch_composition_container.setVisible(False)
        composition_layout = QtWidgets.QVBoxLayout(self.batch_composition_container)
        composition_layout.setSpacing(10)
        composition_layout.setContentsMargins(0, 0, 0, 0)

        # Informations du batch
        self.batch_info_label = QtWidgets.QLabel()
        self.batch_info_label.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                border-left: 3px solid #2196f3;
                border-radius: 4px;
                padding: 10px;
                font-size: 12px;
                color: #1565c0;
                font-weight: 600;
            }
        """)
        composition_layout.addWidget(self.batch_info_label)

        # Layout horizontal : Tableau à gauche, Camembert à droite
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(10)

        # GAUCHE : Tableau détaillé des combinaisons
        detail_group = QtWidgets.QGroupBox("📋 Détails")
        detail_group.setStyleSheet(self._get_group_style())
        detail_layout = QtWidgets.QVBoxLayout(detail_group)
        detail_layout.setContentsMargins(10, 15, 10, 10)

        self.batch_detail_table = QtWidgets.QTableWidget()
        self.batch_detail_table.setColumnCount(4)
        self.batch_detail_table.setHorizontalHeaderLabels(["Type", "Typologie", "Nombre", "Pourcentage"])
        self.batch_detail_table.horizontalHeader().setStretchLastSection(True)
        self.batch_detail_table.setAlternatingRowColors(False)
        self.batch_detail_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
                gridline-color: #f0f0f0;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-weight: 600;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #e1e4e8;
                font-size: 11px;
            }
        """)
        detail_layout.addWidget(self.batch_detail_table)

        content_layout.addWidget(detail_group, 1)

        # DROITE : Graphique camembert unique
        chart_container = QtWidgets.QGroupBox("📊 Composition")
        chart_container.setStyleSheet(self._get_group_style())
        chart_layout = QtWidgets.QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(10, 15, 10, 10)

        self.batch_composition_chart_view = QChartView()
        self.batch_composition_chart_view.setRenderHint(QPainter.Antialiasing)
        self.batch_composition_chart_view.setMinimumHeight(400)
        chart_layout.addWidget(self.batch_composition_chart_view)

        content_layout.addWidget(chart_container, 1)

        composition_layout.addLayout(content_layout, 1)

        layout.addWidget(self.batch_composition_container)

        return widget

    def _create_typologie_analysis_tab(self):
        """Create typologie analysis tab - Analyse par typologie"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Titre
        title = QtWidgets.QLabel("🔍 Analyse par Typologie")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #2c3e50; padding: 10px;")
        layout.addWidget(title)
        
        # Camembert des typologies master
        master_group = QtWidgets.QGroupBox("🎯 Distribution des Typologies Master")
        master_group.setStyleSheet(self._get_group_style())
        master_layout = QtWidgets.QVBoxLayout(master_group)
        
        self.master_chart_view = QChartView()
        self.master_chart_view.setRenderHint(QPainter.Antialiasing)
        self.master_chart_view.setMinimumHeight(250)
        master_layout.addWidget(self.master_chart_view)
        
        layout.addWidget(master_group)
        
        # Camembert des typologies de contexte
        context_group = QtWidgets.QGroupBox("🔗 Distribution des Typologies de Contexte")
        context_group.setStyleSheet(self._get_group_style())
        context_layout = QtWidgets.QVBoxLayout(context_group)
        
        self.context_chart_view = QChartView()
        self.context_chart_view.setRenderHint(QPainter.Antialiasing)
        self.context_chart_view.setMinimumHeight(250)
        context_layout.addWidget(self.context_chart_view)
        
        layout.addWidget(context_group)
        
        return widget

    def _create_hierarchy_tab(self):
        """Create hierarchy tab - Distribution hiérarchique"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Titre
        title = QtWidgets.QLabel("🌳 Distribution Hiérarchique")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #2c3e50; padding: 10px;")
        layout.addWidget(title)
        
        # Graphique en barres pour la distribution
        chart_group = QtWidgets.QGroupBox("📊 Combinaisons par Niveau Hiérarchique")
        chart_group.setStyleSheet(self._get_group_style())
        chart_layout = QtWidgets.QVBoxLayout(chart_group)
        
        self.hierarchy_chart_view = QChartView()
        self.hierarchy_chart_view.setRenderHint(QPainter.Antialiasing)
        self.hierarchy_chart_view.setMinimumHeight(350)
        chart_layout.addWidget(self.hierarchy_chart_view)
        
        layout.addWidget(chart_group)
        
        # Tableau détaillé
        detail_group = QtWidgets.QGroupBox("📋 Détails par Niveau")
        detail_group.setStyleSheet(self._get_group_style())
        detail_layout = QtWidgets.QVBoxLayout(detail_group)
        
        self.hierarchy_table = QtWidgets.QTableWidget()
        self.hierarchy_table.setColumnCount(4)
        self.hierarchy_table.setHorizontalHeaderLabels(["Niveau", "Combinaisons", "Pourcentage", "Profondeur"])
        self.hierarchy_table.horizontalHeader().setStretchLastSection(True)
        self.hierarchy_table.setAlternatingRowColors(True)
        self.hierarchy_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                background-color: white;
                gridline-color: #e1e4e8;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
            }
        """)
        detail_layout.addWidget(self.hierarchy_table)
        
        layout.addWidget(detail_group)
        
        return widget

    def _create_detailed_stats_tab(self):
        """Create detailed stats tab - Statistiques détaillées"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Titre
        title = QtWidgets.QLabel("📈 Statistiques Détaillées")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #2c3e50; padding: 10px;")
        layout.addWidget(title)
        
        # ScrollArea pour les stats
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # Stats par typologie master
        self.master_stats_group = self._create_modern_card("🎯 Statistiques par Typologie Master")
        master_stats_layout = QtWidgets.QVBoxLayout(self.master_stats_group)
        
        self.master_stats_text = QtWidgets.QTextEdit()
        self.master_stats_text.setReadOnly(True)
        self.master_stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        master_stats_layout.addWidget(self.master_stats_text)
        
        scroll_layout.addWidget(self.master_stats_group)
        
        # Stats par cluster
        self.cluster_stats_group = self._create_modern_card("🔷 Statistiques par Cluster")
        cluster_stats_layout = QtWidgets.QVBoxLayout(self.cluster_stats_group)
        
        self.cluster_stats_text = QtWidgets.QTextEdit()
        self.cluster_stats_text.setReadOnly(True)
        self.cluster_stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        cluster_stats_layout.addWidget(self.cluster_stats_text)
        
        scroll_layout.addWidget(self.cluster_stats_group)
        
        # Stats par profondeur
        self.depth_stats_group = self._create_modern_card("⬇️ Statistiques par Profondeur")
        depth_stats_layout = QtWidgets.QVBoxLayout(self.depth_stats_group)
        
        self.depth_stats_text = QtWidgets.QTextEdit()
        self.depth_stats_text.setReadOnly(True)
        self.depth_stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        depth_stats_layout.addWidget(self.depth_stats_text)
        
        scroll_layout.addWidget(self.depth_stats_group)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget

    def _create_stat_card(self, label, value, icon, color):
        """Create a statistic card"""
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 2px solid #e1e4e8;
                border-left: 5px solid {color};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(5)
        
        # Icon et label
        top_layout = QtWidgets.QHBoxLayout()
        
        icon_label = QtWidgets.QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 24px; color: {color};")
        top_layout.addWidget(icon_label)
        
        text_label = QtWidgets.QLabel(label)
        text_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-weight: 600;")
        top_layout.addWidget(text_label)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # Valeur
        value_label = QtWidgets.QLabel(value)
        value_label.setStyleSheet(f"font-size: 32px; font-weight: 700; color: {color};")
        layout.addWidget(value_label)
        
        # Stocker le label de valeur pour mise à jour
        card.value_label = value_label
        
        return card

    def _create_modern_card(self, title):
        """Create a modern card container"""
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 12px;
                color: #2c3e50;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: white;
                color: #2c3e50;
            }}
        """)
        return group

    def _get_group_style(self):
        """Get group box style"""
        return """
            QGroupBox {
                font-weight: 600;
                font-size: 12px;
                color: #2c3e50;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: white;
            }
        """

    def _on_project_changed(self, index):
        """Handle project selection change"""
        if index <= 0:
            self.current_project_data = None
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Sélectionner un batch --")
            self._clear_all_data()
            return

        project_name = self.project_combo.currentText()

        # ✅ Charger le projet complet
        if self.project_manager:
            if self.project_manager.load_project(project_name):
                self.current_project_data = self.project_manager.current_project_data

                # Mettre à jour l'overview
                self._update_overview(self.current_project_data)

                # Charger les batches dans le combo
                self._load_batches_for_project(project_name)
            else:
                logger.error(f"Impossible de charger le projet: {project_name}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Erreur",
                    f"Impossible de charger le projet '{project_name}'"
                )

    def _on_batch_changed(self, index):
        """Handle batch selection change"""
        if index <= 0:
            self.current_batch_data = None
            # Cacher la composition et afficher le message
            if hasattr(self, 'batch_composition_container'):
                self.batch_composition_container.setVisible(False)
            if hasattr(self, 'no_batch_label'):
                self.no_batch_label.setVisible(True)
            return

        batch_data = self.batch_combo.itemData(index, Qt.UserRole)
        if batch_data:
            self.current_batch_data = batch_data
            logger.info(f"Batch selected: {batch_data.get('batch_name', 'N/A')}")

            # Afficher la composition du batch
            self._update_batch_composition(batch_data)

    def _update_batch_composition(self, batch_data):
        """
        Version CORRIGÉE avec affichage des bonnes informations
        """
        if not batch_data:
            return

        try:
            # Cacher le message et afficher le container
            if hasattr(self, 'no_batch_label'):
                self.no_batch_label.setVisible(False)
            if hasattr(self, 'batch_composition_container'):
                self.batch_composition_container.setVisible(True)

            # === RÉCUPÉRATION DES DONNÉES ===
            batch_name = batch_data.get('batch_name', 'Sans nom')
            combinations = batch_data.get('combinations', [])
            total_count = len(combinations)

            if not combinations:
                logger.warning("No combinations found in batch data")
                return

            # === ANALYSE COMPLÈTE ===
            analysis = self._analyze_batch_combinations(combinations, total_count)

            # === MISE À JOUR INFO BATCH (CORRIGÉE) ===
            self.batch_info_label.setText(
                f"📦 Batch: {batch_name} | "
                f"Combinaisons: {total_count} | "
                f"Masters uniques: {analysis['unique_masters_count']} | "
                f"Contextes uniques: {analysis['unique_contexts_count']}"
            )

            # === CRÉATION DU CAMEMBERT ===
            self._create_single_pie_chart(analysis, total_count)

            # === MISE À JOUR DU TABLEAU ===
            self._update_detail_table(analysis, total_count)

            logger.info(f"Batch composition updated: {batch_name}")

        except Exception as e:
            logger.error(f"Error updating batch composition: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _analyze_batch_combinations(self, combinations, total_count):
        """
        Analyse CORRIGÉE basée sur la structure RÉELLE :
        - 1 Master unique (compte = nombre de combinaisons qui l'utilisent)
        - N Contextes différents (compte = nombre de fois utilisé)

        Le total = Master utilisations + Contexte utilisations = 2 * nb_combinaisons
        """
        analysis = {
            'typologie_counts': {},
            'typologie_types': {},
            'typologie_levels': {},
            'level_distribution': {},
            'depth_stats': {},
            'master_total_uses': 0,
            'context_total_uses': 0,
            'unique_masters': set(),
            'unique_contexts': set()
        }

        for combo in combinations:
            # === 1. MASTER TYPOLOGIE ===
            master = combo.get('master', {})
            master_name = master.get('name', 'Unknown Master')

            # Clé avec préfixe pour distinction visuelle
            key_master = f"🎯 {master_name}"

            # Incrémenter le count (nombre d'utilisations)
            analysis['typologie_counts'][key_master] = \
                analysis['typologie_counts'].get(key_master, 0) + 1

            # Stocker le type et niveau
            analysis['typologie_types'][key_master] = 'master'
            analysis['typologie_levels'][key_master] = 'Master'

            # Compteurs globaux
            analysis['master_total_uses'] += 1
            analysis['unique_masters'].add(master_name)

            # === 2. CONTEXT TYPOLOGIE ===
            context = combo.get('context', {})
            context_name = context.get('typologie', 'Unknown Context')
            level = context.get('level', 'unknown')

            # Clé avec préfixe
            key_context = f"🔗 {context_name}"

            # Incrémenter le count
            analysis['typologie_counts'][key_context] = \
                analysis['typologie_counts'].get(key_context, 0) + 1

            # Stocker le type
            analysis['typologie_types'][key_context] = 'context'

            # Compteurs globaux
            analysis['context_total_uses'] += 1
            analysis['unique_contexts'].add(context_name)

            # === 3. NIVEAU HIÉRARCHIQUE ===
            if level == 'child':
                child_path = context.get('child_path', [])
                depth = len(child_path)
                level_display = f"Enfant Niveau {depth}"

                # Stats de profondeur
                analysis['depth_stats'][depth] = \
                    analysis['depth_stats'].get(depth, 0) + 1
            else:
                level_display = {
                    'typologie': 'Typologie',
                    'taxonomy': 'Cluster',
                    'root': 'Root',
                    'parent': 'Parent'
                }.get(level, level.capitalize())

            analysis['typologie_levels'][key_context] = level_display

            # Distribution par niveau
            analysis['level_distribution'][level_display] = \
                analysis['level_distribution'].get(level_display, 0) + 1

        # === CALCUL DU TOTAL RÉEL ===
        # Total = toutes les utilisations de typologies (Master + Contexte)
        analysis['total_typologies_uses'] = analysis['master_total_uses'] + analysis['context_total_uses']

        # Convertir les sets en nombre
        analysis['unique_masters_count'] = len(analysis['unique_masters'])
        analysis['unique_contexts_count'] = len(analysis['unique_contexts'])

        logger.info(f"📊 Analyse batch:")
        logger.info(f"   Combinaisons: {total_count}")
        logger.info(f"   Total utilisations typologies: {analysis['total_typologies_uses']}")
        logger.info(f"   Master utilisé: {analysis['master_total_uses']} fois ({analysis['unique_masters_count']} unique(s))")
        logger.info(f"   Contexte utilisé: {analysis['context_total_uses']} fois ({analysis['unique_contexts_count']} unique(s))")

        return analysis

    def _create_single_pie_chart(self, analysis, total_count):
        """
        Camembert avec pourcentages CORRECTS :
        Chaque typologie = son nombre d'utilisations / total utilisations
        """
        # ✅ Total = Master uses + Context uses
        total_uses = analysis['total_typologies_uses']

        logger.info(f"🎨 Création camembert avec {total_uses} utilisations de typologies")

        # Palette de couleurs
        master_colors = [
            '#e74c3c', '#c0392b', '#e67e22', '#d35400', 
            '#f39c12', '#f1c40f', '#e84393', '#fd79a8'
        ]

        context_colors = [
            '#3498db', '#2980b9', '#1abc9c', '#16a085', 
            '#27ae60', '#2ecc71', '#9b59b6', '#8e44ad',
            '#34495e', '#2c3e50', '#16a085', '#48c9b0'
        ]

        # Créer la série
        series = QPieSeries()

        master_index = 0
        context_index = 0

        # Trier par count décroissant
        sorted_typologies = sorted(
            analysis['typologie_counts'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )

        for typo_key, count in sorted_typologies:
            # ✅ CORRECTION : Pourcentage sur total_uses
            percentage = (count / total_uses * 100) if total_uses > 0 else 0

            # Nom affiché (garde le préfixe emoji)
            display_name = typo_key

            # Label avec toutes les infos
            label = f"{display_name}\n{count} utilisations\n({percentage:.1f}%)"

            slice_obj = series.append(label, count)
            slice_obj.setLabelVisible(True)
            slice_obj.setLabelColor(QColor("#2c3e50"))

            # Appliquer la couleur selon le type
            if analysis['typologie_types'][typo_key] == 'master':
                color = master_colors[master_index % len(master_colors)]
                slice_obj.setBrush(QColor(color))
                master_index += 1
            else:
                color = context_colors[context_index % len(context_colors)]
                slice_obj.setBrush(QColor(color))
                context_index += 1

            # Bordure pour meilleure visibilité
            slice_obj.setPen(QPen(QColor("#ffffff"), 2))

            logger.debug(f"   {display_name}: {count}/{total_uses} = {percentage:.1f}%")

        # Créer le graphique
        chart = QChart()
        chart.addSeries(series)

        # ✅ Titre corrigé avec les bonnes infos
        master_pct = (analysis['master_total_uses'] / total_uses * 100) if total_uses > 0 else 0
        context_pct = (analysis['context_total_uses'] / total_uses * 100) if total_uses > 0 else 0

        chart.setTitle(
            f"Répartition des Typologies par Utilisation\n"
            f"Master: {analysis['master_total_uses']} ({master_pct:.1f}%) | "
            f"Contexte: {analysis['context_total_uses']} ({context_pct:.1f}%)"
        )
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setAlignment(Qt.AlignRight)
        chart.legend().setFont(self._get_legend_font())
        chart.setBackgroundBrush(QColor("#ffffff"))

        # Afficher
        self.batch_composition_chart_view.setChart(chart)

    def _update_detail_table(self, analysis, total_count):
        """
        Tableau avec colonnes :
        Type | Typologie | Niveau | Utilisations | % sur Total Utilisations
        """
        # ✅ Total utilisations (pas combinaisons)
        total_uses = analysis['total_typologies_uses']
        
        # Configurer le tableau
        self.batch_detail_table.setColumnCount(5)
        self.batch_detail_table.setHorizontalHeaderLabels([
            "Type", 
            "Typologie", 
            "Niveau",
            "Utilisations", 
            "% Total"
        ])
        
        # Vider le tableau
        self.batch_detail_table.setRowCount(0)
        
        # Couleurs simplifiées
        master_color = '#e74c3c'
        context_color = '#3498db'
        
        # Trier par count décroissant
        sorted_typologies = sorted(
            analysis['typologie_counts'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for typo_key, count in sorted_typologies:
            # ✅ Pourcentage sur total_uses
            percentage = (count / total_uses * 100) if total_uses > 0 else 0
            
            row = self.batch_detail_table.rowCount()
            self.batch_detail_table.insertRow(row)
            
            # Déterminer le type
            is_master = analysis['typologie_types'][typo_key] == 'master'
            type_label = "🎯 Master" if is_master else "🔗 Contexte"
            
            # Nom sans préfixe emoji
            typo_name = typo_key.replace("🎯 ", "").replace("🔗 ", "")
            
            level_name = analysis['typologie_levels'][typo_key]
            
            # Couleur
            color = master_color if is_master else context_color
            
            # === COLONNE 1 : Type ===
            type_item = QtWidgets.QTableWidgetItem(type_label)
            type_item.setFont(self._get_bold_font())
            type_item.setForeground(QColor(color))
            self.batch_detail_table.setItem(row, 0, type_item)
            
            # === COLONNE 2 : Typologie ===
            name_item = QtWidgets.QTableWidgetItem(typo_name)
            name_item.setForeground(QColor(color))
            name_item.setFont(self._get_bold_font())
            self.batch_detail_table.setItem(row, 1, name_item)
            
            # === COLONNE 3 : Niveau Hiérarchique ===
            level_item = QtWidgets.QTableWidgetItem(level_name)
            level_item.setTextAlignment(Qt.AlignCenter)
            level_item.setForeground(QColor("#7f8c8d"))
            self.batch_detail_table.setItem(row, 2, level_item)
            
            # === COLONNE 4 : Utilisations ===
            count_item = QtWidgets.QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            count_item.setFont(self._get_bold_font())
            self.batch_detail_table.setItem(row, 3, count_item)
            
            # === COLONNE 5 : Pourcentage ===
            percentage_item = QtWidgets.QTableWidgetItem(f"{percentage:.1f}%")
            percentage_item.setTextAlignment(Qt.AlignCenter)
            self.batch_detail_table.setItem(row, 4, percentage_item)
            
            # Pas de coloration de fond
        
        # Ajuster les colonnes
        self.batch_detail_table.resizeColumnsToContents()
        self.batch_detail_table.setColumnWidth(2, 150)

    def _get_legend_font(self):
        """Retourne une police pour la légende du graphique"""
        from PyQt5.QtGui import QFont
        font = QFont()
        font.setPointSize(9)
        font.setFamily("Segoe UI")
        return font

    def _load_batches_for_project(self, project_name):
        """Load batches for the selected project"""
        self.batch_combo.blockSignals(True)
        self.batch_combo.clear()
        self.batch_combo.addItem("-- Sélectionner un batch --")

        if not self.project_manager:
            self.batch_combo.blockSignals(False)
            return

        try:
            batches = self.project_manager.get_all_batches()

            for batch in batches:
                batch_number = batch.get('batch_number', 0)
                batch_data = batch.get('data', {})
                batch_name = batch_data.get('batch_name', f'Batch #{batch_number}')
                count = batch_data.get('count', 0)
                status = batch.get('status', 'pending')

                display_text = f"#{batch_number} - {batch_name} ({count} combinaisons) [{status}]"
                self.batch_combo.addItem(display_text, batch_data)

            logger.info(f"Loaded {len(batches)} batches for project: {project_name}")

        except Exception as e:
            logger.error(f"Error loading batches: {e}")

        finally:
            self.batch_combo.blockSignals(False)

    def _analyze_combinations(self, combinations):
        """Analyze combinations and extract statistics"""
        analysis = {
            'total': len(combinations),
            'master_typologies': {},
            'context_typologies': {},
            'levels': {},
            'clusters': set(),
            'max_depth': 0,
            'by_depth': {},
            'hierarchy_distribution': {}
        }
        
        for combo in combinations:
            # Master typologie
            master = combo.get('master', {})
            master_name = master.get('name', 'Unknown')
            analysis['master_typologies'][master_name] = analysis['master_typologies'].get(master_name, 0) + 1
            
            # Context
            context = combo.get('context', {})
            level = context.get('level', 'unknown')
            typologie = context.get('typologie', 'Unknown')
            
            # Context typologie
            analysis['context_typologies'][typologie] = analysis['context_typologies'].get(typologie, 0) + 1
            
            # Level
            analysis['levels'][level] = analysis['levels'].get(level, 0) + 1
            
            # Cluster
            taxonomy = context.get('taxonomy', '')
            if taxonomy:
                analysis['clusters'].add(taxonomy)
            
            # Depth calculation
            depth = 0
            if level == 'typologie':
                depth = 1
            elif level == 'taxonomy':
                depth = 2
            elif level == 'root':
                depth = 3
            elif level == 'parent':
                depth = 4
            elif level == 'child':
                child_path = context.get('child_path', [])
                depth = 4 + len(child_path)
            
            analysis['max_depth'] = max(analysis['max_depth'], depth)
            analysis['by_depth'][depth] = analysis['by_depth'].get(depth, 0) + 1
            
            # Hierarchy distribution
            hierarchy_key = f"{level}"
            if level == 'child' and context.get('child_path'):
                hierarchy_key = f"child_level_{len(context.get('child_path', []))}"
            
            analysis['hierarchy_distribution'][hierarchy_key] = \
                analysis['hierarchy_distribution'].get(hierarchy_key, 0) + 1
        
        analysis['clusters'] = len(analysis['clusters'])
        
        return analysis

    def _update_overview(self, project_data):
        """Update overview with actual project data"""
        if not project_data:
            self.project_info_label.setText("Aucun projet chargé")
            self.typologie_tree.clear()
            self.batch_list_widget.clear()
            return

        try:
            # ✅ 1. Informations générales du projet
            project_name = project_data.get('nom', 'Sans nom')
            description = project_data.get('description', 'Aucune description')
            typologies = project_data.get('typologies', [])

            info_text = f"""
            <b style="font-size: 14px; color: #3498db;">📁 {project_name}</b><br><br>
            <b>Description :</b> {description}<br><br>
            <b>Nombre de typologies :</b> {len(typologies)}
            """

            self.project_info_label.setText(info_text)

            # ✅ 2. Arbre des typologies avec leurs taxonomies
            self.typologie_tree.clear()

            for typologie in typologies:
                typ_name = typologie.get('name', 'Sans nom')
                taxonomy_clusters = typologie.get('taxonomy_clusters', [])

                # Item typologie (niveau 1)
                typ_item = QtWidgets.QTreeWidgetItem([
                    typ_name,
                    f"{len(taxonomy_clusters)} taxonomie(s)"
                ])
                typ_item.setFont(0, self._get_bold_font())
                typ_item.setForeground(0, QColor("#9b59b6"))

                # Taxonomies (niveau 2)
                for cluster in taxonomy_clusters:
                    cluster_name = cluster.get('name', 'Sans nom')
                    root_labels = cluster.get('root_labels', [])

                    # Compter le total d'éléments
                    total_roots = len(root_labels)
                    total_parents = sum(len(root.get('parent_labels', [])) for root in root_labels)

                    # Compter les enfants de manière sécurisée
                    total_children = 0
                    for root in root_labels:
                        for parent in root.get('parent_labels', []):
                            children = parent.get('children', [])
                            if children:
                                total_children += self._count_children_recursive(children)

                    cluster_item = QtWidgets.QTreeWidgetItem([
                        cluster_name,
                        f"{total_roots} roots, {total_parents} parents, {total_children} enfants"
                    ])
                    cluster_item.setForeground(0, QColor("#e67e22"))

                    typ_item.addChild(cluster_item)

                self.typologie_tree.addTopLevelItem(typ_item)

            # Expand all
            self.typologie_tree.expandAll()

            # Resize columns
            self.typologie_tree.resizeColumnToContents(0)
            self.typologie_tree.resizeColumnToContents(1)

            # ✅ 3. Liste des batches
            self.batch_list_widget.clear()

            if self.project_manager:
                batches = self.project_manager.get_all_batches()

                if not batches:
                    item = QtWidgets.QListWidgetItem("Aucun batch créé pour ce projet")
                    item.setForeground(QColor("#95a5a6"))
                    self.batch_list_widget.addItem(item)
                else:
                    for batch in batches:
                        batch_number = batch.get('batch_number', 0)
                        batch_data = batch.get('data', {})
                        batch_name = batch_data.get('batch_name', f'Batch #{batch_number}')
                        count = batch_data.get('count', 0)
                        status = batch.get('status', 'pending')

                        # Icône selon le statut
                        if status == 'completed':
                            icon = "✅"
                        elif status == 'processing':
                            icon = "⏳"
                        else:
                            icon = "📦"

                        item_text = f"{icon} Batch #{batch_number}: {batch_name} - {count} combinaison(s) [{status}]"

                        item = QtWidgets.QListWidgetItem(item_text)

                        # Couleur selon statut
                        if status == 'completed':
                            item.setForeground(QColor("#27ae60"))
                        elif status == 'processing':
                            item.setForeground(QColor("#f39c12"))
                        else:
                            item.setForeground(QColor("#3498db"))

                        self.batch_list_widget.addItem(item)

            logger.info(f"Overview updated for project: {project_name}")

        except Exception as e:
            logger.error(f"Error updating overview: {e}")
            import traceback
            logger.error(traceback.format_exc())

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la mise à jour de l'aperçu:\n{str(e)}"
            )

    def _build_project_tree(self, project_data):
        """Build hierarchical tree view of project structure"""
        self.project_tree.clear()

        if not project_data:
            return

        typologies = project_data.get('typologies', [])

        for typ in typologies:
            typ_name = typ.get('name', 'Unnamed')

            # Item typologie
            typ_item = QtWidgets.QTreeWidgetItem([
                f"🎯 {typ_name}",
                f"Typologie de contexte"
            ])
            typ_item.setFont(0, self._get_bold_font())
            typ_item.setForeground(0, QColor("#9b59b6"))

            # Taxonomies
            taxonomy_clusters = typ.get('taxonomy_clusters', [])
            for cluster in taxonomy_clusters:
                cluster_name = cluster.get('name', 'Unnamed')

                cluster_item = QtWidgets.QTreeWidgetItem([
                    f"🔗 {cluster_name}",
                    f"Taxonomy Cluster"
                ])
                cluster_item.setForeground(0, QColor("#e67e22"))

                # Root labels
                root_labels = cluster.get('root_labels', [])
                roots_summary = QtWidgets.QTreeWidgetItem([
                    f"📍 Root Labels",
                    f"{len(root_labels)} labels"
                ])
                roots_summary.setForeground(0, QColor("#3498db"))

                for root in root_labels:
                    root_name = root.get('name', 'Unnamed')
                    root_item = QtWidgets.QTreeWidgetItem([
                        root_name,
                        f"{len(root.get('parent_labels', []))} parents"
                    ])
                    roots_summary.addChild(root_item)

                cluster_item.addChild(roots_summary)
                typ_item.addChild(cluster_item)

            self.project_tree.addTopLevelItem(typ_item)

        # Expand first level
        self.project_tree.expandToDepth(1)

    def _get_bold_font(self):
        """Retourne une police en gras"""
        from PyQt5.QtGui import QFont
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        return font
    
    def _create_mini_button(self, text, callback):
        """Create a small action button"""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
                min-width: 120px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:disabled {{
                background: #c0c0c0;
                color: #707070;
            }}
        """)
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        return btn


    def _update_structure_view(self, analysis):
        """Update structure tab with pie chart and tree"""
        # Create pie chart for level distribution
        series = QPieSeries()
        
        colors = {
            'typologie': '#3498db',
            'taxonomy': '#9b59b6',
            'root': '#e67e22',
            'parent': '#27ae60',
            'child': '#e74c3c'
        }
        
        for level, count in analysis['levels'].items():
            slice = series.append(f"{level.capitalize()} ({count})", count)
            slice.setLabelVisible(True)
            slice.setLabelColor(QColor("#2c3e50"))
            
            if level in colors:
                slice.setBrush(QColor(colors[level]))
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Distribution par Niveau")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setAlignment(Qt.AlignRight)
        
        self.level_chart_view.setChart(chart)
        
        # Update tree
        self.structure_tree.clear()
        
        for level, count in sorted(analysis['levels'].items()):
            percentage = (count / analysis['total']) * 100 if analysis['total'] > 0 else 0
            item = QtWidgets.QTreeWidgetItem([
                level.capitalize(),
                f"{count} ({percentage:.1f}%)"
            ])
            item.setForeground(0, QColor("#2c3e50"))
            item.setFont(0, item.font(0))
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            
            self.structure_tree.addTopLevelItem(item)

    def _update_typologie_view(self, analysis):
        """Update typologie analysis tab with pie charts"""
        # Master typologies pie chart
        master_series = QPieSeries()
        
        for typo, count in analysis['master_typologies'].items():
            slice = master_series.append(f"{typo} ({count})", count)
            slice.setLabelVisible(True)
            slice.setLabelColor(QColor("#2c3e50"))
        
        master_chart = QChart()
        master_chart.addSeries(master_series)
        master_chart.setTitle("Répartition des Typologies Master")
        master_chart.setAnimationOptions(QChart.SeriesAnimations)
        master_chart.legend().setAlignment(Qt.AlignBottom)
        
        self.master_chart_view.setChart(master_chart)
        
        # Context typologies pie chart
        context_series = QPieSeries()
        
        for typo, count in analysis['context_typologies'].items():
            slice = context_series.append(f"{typo} ({count})", count)
            slice.setLabelVisible(True)
            slice.setLabelColor(QColor("#2c3e50"))
        
        context_chart = QChart()
        context_chart.addSeries(context_series)
        context_chart.setTitle("Répartition des Typologies de Contexte")
        context_chart.setAnimationOptions(QChart.SeriesAnimations)
        context_chart.legend().setAlignment(Qt.AlignBottom)
        
        self.context_chart_view.setChart(context_chart)

    def _update_hierarchy_view(self, analysis):
        """Update hierarchy tab with bar chart and table"""
        # Create bar chart
        bar_set = QBarSet("Combinaisons")
        bar_set.setColor(QColor("#3498db"))
        
        categories = []
        depths = sorted(analysis['by_depth'].keys())
        
        for depth in depths:
            count = analysis['by_depth'][depth]
            bar_set.append(count)
            categories.append(f"Niveau {depth}")
        
        bar_series = QBarSeries()
        bar_series.append(bar_set)
        
        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle("Distribution par Profondeur Hiérarchique")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setTitleText("Nombre de combinaisons")
        chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        self.hierarchy_chart_view.setChart(chart)
        
        # Update table
        self.hierarchy_table.setRowCount(0)
        
        level_names = {
            1: "Typologie",
            2: "Taxonomy/Cluster",
            3: "Root Label",
            4: "Parent Label",
        }
        
        total = analysis['total']
        
        for depth in depths:
            count = analysis['by_depth'][depth]
            percentage = (count / total) * 100 if total > 0 else 0
            
            level_name = level_names.get(depth, f"Child Level {depth - 4}")
            
            row = self.hierarchy_table.rowCount()
            self.hierarchy_table.insertRow(row)
            
            self.hierarchy_table.setItem(row, 0, QtWidgets.QTableWidgetItem(level_name))
            self.hierarchy_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(count)))
            self.hierarchy_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{percentage:.1f}%"))
            self.hierarchy_table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(depth)))

    def _update_detailed_stats(self, analysis):
        """Update detailed statistics tab"""
        # Master typologie stats
        master_text = "📊 STATISTIQUES PAR TYPOLOGIE MASTER\n\n"
        
        for typo, count in sorted(analysis['master_typologies'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / analysis['total']) * 100 if analysis['total'] > 0 else 0
            master_text += f"• {typo}:\n"
            master_text += f"  └─ Combinaisons: {count}\n"
            master_text += f"  └─ Pourcentage: {percentage:.2f}%\n\n"
        
        self.master_stats_text.setPlainText(master_text)
        
        # Cluster stats
        cluster_text = "📊 STATISTIQUES PAR CLUSTER\n\n"
        cluster_text += f"Nombre total de clusters uniques: {analysis['clusters']}\n\n"
        
        # Count by level for clusters
        level_counts = {}
        for level, count in analysis['levels'].items():
            level_counts[level] = count
        
        for level, count in sorted(level_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / analysis['total']) * 100 if analysis['total'] > 0 else 0
            cluster_text += f"• {level.capitalize()}:\n"
            cluster_text += f"  └─ Combinaisons: {count}\n"
            cluster_text += f"  └─ Pourcentage: {percentage:.2f}%\n\n"
        
        self.cluster_stats_text.setPlainText(cluster_text)
        
        # Depth stats
        depth_text = "📊 STATISTIQUES PAR PROFONDEUR\n\n"
        depth_text += f"Profondeur maximale: {analysis['max_depth']}\n\n"
        
        for depth in sorted(analysis['by_depth'].keys()):
            count = analysis['by_depth'][depth]
            percentage = (count / analysis['total']) * 100 if analysis['total'] > 0 else 0
            depth_text += f"• Niveau {depth}:\n"
            depth_text += f"  └─ Combinaisons: {count}\n"
            depth_text += f"  └─ Pourcentage: {percentage:.2f}%\n"
            depth_text += f"  └─ Ratio: {count}/{analysis['total']}\n\n"
        
        self.depth_stats_text.setPlainText(depth_text)

    def _clear_all_data(self):
        """Clear all displayed data"""
        # Clear overview
        if hasattr(self, 'project_info_label'):
            self.project_info_label.setText("Aucun projet sélectionné")

        if hasattr(self, 'typologie_tree'):
            self.typologie_tree.clear()

        if hasattr(self, 'batch_list_widget'):
            self.batch_list_widget.clear()

        # Clear validation
        if hasattr(self, 'validation_results'):
            self.validation_results.clear()

        if hasattr(self, 'validation_summary'):
            self.validation_summary.setText("Aucune validation effectuée")

        # Clear batch data
        self.current_batch_data = None

        logger.debug("All data cleared")

    def _get_tab_style(self):
        """Get modern tab style"""
        return f"""
            QTabWidget::pane {{
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
            }}
            QTabBar::tab {{
                background: #f8f9fa;
                border: 1px solid #e1e4e8;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                color: #7f8c8d;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border-bottom: 1px solid white;
            }}
            QTabBar::tab:hover:!selected {{
                background: #ecf0f1;
            }}
        """

    def _get_modern_input_style(self):
        """Modern input field style"""
        svg_path = self._get_dropdown_svg_path()

        return f"""
            QComboBox {{
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: white;
                font-size: 12px;
                min-height: 25px;
                padding-right: 30px;
            }}
            QComboBox:focus {{
                border: 1px solid #3498db;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 25px;
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 14px;
                height: 14px;
            }}
        """

    def _get_button_style(self):
        """Get button style"""
        return """
            QPushButton {
                background: #f8f9fa;
                border: 1px solid #e1e4e8;
                color: #2c3e50;
                font-weight: 600;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e9ecef;
                border-color: #3498db;
            }
        """
    
    def _get_dropdown_svg_path(self):
        """Get absolute path to dropdown SVG icon"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(current_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        return os.path.normpath(svg_path).replace('\\', '/')

    def refresh_projects(self):
        """Refresh project list"""
        if not self.project_manager:
            return
        
        projects = self.project_manager.get_all_projects()
        project_names = sorted([p['name'] for p in projects])

        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- Sélectionner un projet --")
        self.project_combo.addItems(project_names)
        
        if self.project_manager.current_project_name in project_names:
            index = project_names.index(self.project_manager.current_project_name) + 1
            self.project_combo.setCurrentIndex(index)
        
        self.project_combo.blockSignals(False)
        
        if self.project_combo.currentIndex() > 0:
            self._on_project_changed(self.project_combo.currentIndex())

    def update_preview(self, project_data):
        """Update preview with project data - Compatibility method"""
        if not project_data:
            return

        try:
            self.current_project_data = project_data

            # Update overview tab
            self._update_overview(project_data)

            logger.info("Preview updated successfully")

        except Exception as e:
            logger.error(f"Error in update_preview: {e}")
            import traceback
            logger.error(traceback.format_exc())