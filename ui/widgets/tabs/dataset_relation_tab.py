#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime
from utils.logger import logger
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ui.localization.translator import tr
from ui.styles.theme import Theme
from ui.widgets.tabs.batch_viewer_window import BatchViewerWindow


class DatasetRelationTab(QtWidgets.QWidget):
    """
    Onglet de génération de combinaisons de typologies de contexte.
    Navigation hiérarchique avec clic simple pour naviguer, double-clic pour sélectionner.
    """
    
    combinations_generated = pyqtSignal(dict)

    def __init__(self, project_manager, config_data, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data
        self.combinations = []
        self.selected_master_typologie = None
        self._typologies_cache = []

        self.current_batch_id = None
        self.is_batch_saved = False
        
        self._context_navigation = {
            'typologie': None,
            'taxonomy': None,
            'root': None,
            'parent': None,
            'child_path': []
        }
        
        self._init_ui()
        self._load_initial_data()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QtWidgets.QLabel(tr("dataset.combination_title"))
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {Theme.PRIMARY_COLOR}; padding: 10px 0;")
        main_layout.addWidget(title_label)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(15)

        left_widget = self._create_left_section()
        left_widget.setMinimumWidth(280)
        left_widget.setMaximumWidth(320)
        content_layout.addWidget(left_widget, 2)

        right_widget = self._create_right_section()
        content_layout.addWidget(right_widget, 8)

        main_layout.addLayout(content_layout)
        self._create_action_buttons(main_layout)

    def _create_left_section(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._create_batch_info_card())
        layout.addWidget(self._create_master_card())
        layout.addStretch()
        return container

    def _create_batch_info_card(self):
        group = self._create_modern_card("Informations du Batch")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)

        project_label = QtWidgets.QLabel("Projet")
        project_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(project_label)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.setMinimumHeight(32)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        layout.addWidget(self.project_combo)

        self._add_form_field(layout, "Nom du batch", "batch_name_edit", "Ex: Batch_Contexte_2024")
        self._add_form_field(layout, "Famille de batch", "batch_family_edit", "Ex: Production, Test...")

        desc_label = QtWidgets.QLabel("Description (facultatif)")
        desc_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(desc_label)

        self.desc_edit = QtWidgets.QTextEdit()
        self.desc_edit.setPlaceholderText("Description du batch...")
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setStyleSheet("""
            QTextEdit { border: 2px solid #e1e4e8; border-radius: 6px; padding: 6px;
                background-color: white; font-size: 11px; color: #2c3e50; }
            QTextEdit:focus { border: 2px solid #2c3e50; }
        """)
        layout.addWidget(self.desc_edit)

        # ✅ NOUVEAU : Boutons de gestion des batches
        batch_buttons_layout = QtWidgets.QHBoxLayout()
        batch_buttons_layout.setSpacing(6)

        self.load_batch_btn = self._create_mini_button("📂 Charger", self._load_batch_dialog)
        self.load_batch_btn.setToolTip("Charger un batch sauvegardé")
        batch_buttons_layout.addWidget(self.load_batch_btn)

        self.new_batch_btn = self._create_mini_button("📄 Nouveau", self._new_batch)
        self.new_batch_btn.setToolTip("Créer un nouveau batch")
        batch_buttons_layout.addWidget(self.new_batch_btn)

        batch_buttons_layout.addStretch()
        layout.addLayout(batch_buttons_layout)

        # Indicateur de statut
        self.batch_status_label = QtWidgets.QLabel("Nouveau batch")
        self.batch_status_label.setStyleSheet(
            "color: #95a5a6; font-size: 10px; font-style: italic; padding: 4px;"
        )
        layout.addWidget(self.batch_status_label)

        return group
    

    def _create_master_card(self):
        group = self._create_modern_card("Typologie de Contexte Master")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)

        master_label = QtWidgets.QLabel("Sélectionner la typologie master *")
        master_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(master_label)

        self.master_combo = QtWidgets.QComboBox()
        self.master_combo.setStyleSheet(self._get_modern_input_style())
        self.master_combo.setMinimumHeight(32)
        self.master_combo.currentIndexChanged.connect(self._on_master_typologie_changed)
        layout.addWidget(self.master_combo)

        stats_label = QtWidgets.QLabel("Statistiques")
        stats_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px; margin-top: 8px;")
        layout.addWidget(stats_label)

        self.master_stats = QtWidgets.QTextEdit()
        self.master_stats.setReadOnly(True)
        self.master_stats.setMaximumHeight(100)
        self.master_stats.setStyleSheet("""
            QTextEdit { border: 2px solid #e1e4e8; border-radius: 6px; padding: 8px;
                background-color: #f8f9fa; font-size: 11px; color: #2c3e50; }
        """)
        layout.addWidget(self.master_stats)
        return group

    def _create_right_section(self):
        group = self._create_modern_card("Typologie de Contexte à Combiner")
        main_layout = QtWidgets.QVBoxLayout(group)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._create_navigation_breadcrumb())

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)

        grid.addWidget(self._create_hierarchy_selector("Typologie", "context_typologie", False), 0, 0)
        grid.addWidget(self._create_hierarchy_selector("Cluster", "context_taxonomy", True), 0, 1)
        grid.addWidget(self._create_hierarchy_selector("Label Racine", "context_root", True), 0, 2)
        grid.addWidget(self._create_hierarchy_selector("Label Parent", "context_parent", True), 1, 0)
        grid.addWidget(self._create_dynamic_child_section(), 1, 1)
        grid.addWidget(self._create_batch_section_right(), 1, 2)

        for i in range(3):
            grid.setColumnStretch(i, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        main_layout.addLayout(grid)
        self._connect_hierarchy_signals()
        return group

    def _create_navigation_breadcrumb(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        nav_label = QtWidgets.QLabel("Navigation:")
        nav_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(nav_label)

        self.nav_breadcrumb = QtWidgets.QLabel("Sélectionnez une typologie")
        self.nav_breadcrumb.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 4px 10px; background-color: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.nav_breadcrumb)
        layout.addStretch()

        self.reset_nav_btn = self._create_mini_button("↺ Reset", self._reset_navigation)
        layout.addWidget(self.reset_nav_btn)
        return container

    def _create_hierarchy_selector(self, label_text, attr_prefix, multi=False):
        container = QtWidgets.QGroupBox(label_text)
        container.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        if multi:
            info = QtWidgets.QLabel("💡 Ctrl+clic multi-sélection")
            info.setStyleSheet("color: #95a5a6; font-size: 9px; font-style: italic;")
            layout.addWidget(info)

        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_hierarchy_list_style())
        if multi:
            list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        layout.addWidget(list_widget)

        setattr(self, f"{attr_prefix}_list", list_widget)
        return container

    def _create_dynamic_child_section(self):
        """
        Section enfants avec instructions claires
        """
        group = QtWidgets.QGroupBox("Labels Enfants")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # ✅ INSTRUCTIONS CLAIRES
        instructions = QtWidgets.QLabel(
            "💡 <b>Sélection libre :</b> Ctrl+Clic pour multi-sélection<br>"
            "🔹 <b>Double-clic :</b> Ajouter/Retirer du batch<br>"
            "🔹 <b>Bouton Descendre :</b> Naviguer dans la hiérarchie"
        )
        instructions.setStyleSheet(
            "color: #34495e; font-size: 9px; "
            "background-color: #e8f5e9; padding: 6px; "
            "border-radius: 4px; border-left: 3px solid #27ae60;"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # En-tête avec boutons de navigation
        top_container = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 4, 0, 0)
        top_layout.setSpacing(4)

        top_layout.addStretch()

        # Boutons de navigation
        self.child_up_btn = self._create_mini_button("↑ Remonter", self._navigate_up_child)
        self.child_up_btn.setEnabled(False)
        self.child_up_btn.setToolTip("Remonter d'un niveau dans la hiérarchie")
        top_layout.addWidget(self.child_up_btn)

        self.child_down_btn = self._create_mini_button("↓ Descendre", self._navigate_down_child)
        self.child_down_btn.setEnabled(False)
        self.child_down_btn.setToolTip("Descendre dans l'élément sélectionné (doit avoir des enfants)")
        top_layout.addWidget(self.child_down_btn)

        layout.addWidget(top_container)

        # Breadcrumb
        self.child_breadcrumb = QtWidgets.QLabel("Niveau racine")
        self.child_breadcrumb.setStyleSheet(
            "color: #7f8c8d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f0f0f0; border-radius: 3px; font-weight: 600;"
        )
        layout.addWidget(self.child_breadcrumb)

        # Liste des enfants
        self.context_child_list = QtWidgets.QListWidget()
        self.context_child_list.setStyleSheet(self._get_hierarchy_list_style())
        self.context_child_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # ✅ Connexions correctes
        self.context_child_list.itemClicked.connect(self._on_child_clicked)
        self.context_child_list.itemDoubleClicked.connect(self._on_child_double_clicked)
        self.context_child_list.itemSelectionChanged.connect(self._on_child_selection_changed)

        layout.addWidget(self.context_child_list)

        return group

    def _create_batch_section_right(self):
        """Section batch avec bouton pour ouvrir la fenêtre de visualisation"""
        group = QtWidgets.QGroupBox("Éléments du Batch")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # En-tête avec stats et bouton d'ouverture
        header_layout = QtWidgets.QHBoxLayout()

        self.stats_label = QtWidgets.QLabel("Combinaisons: 0")
        self.stats_label.setStyleSheet("font-size: 10px; color: #7f8c8d; font-weight: 600;")
        header_layout.addWidget(self.stats_label)

        header_layout.addStretch()

        # ✅ NOUVEAU : Bouton pour ouvrir la fenêtre de visualisation
        self.view_batch_btn = self._create_mini_button("Voir", self._open_batch_viewer)
        self.view_batch_btn.setEnabled(False)
        self.view_batch_btn.setToolTip("Ouvrir la fenêtre de visualisation complète")
        header_layout.addWidget(self.view_batch_btn)

        layout.addLayout(header_layout)

        # Liste compacte (optionnel - vous pouvez la garder ou la retirer)
        self.batch_list = QtWidgets.QListWidget()
        self.batch_list.setStyleSheet(self._get_hierarchy_list_style())
        self.batch_list.currentItemChanged.connect(self._on_batch_item_selected)
        self.batch_list.setMaximumHeight(150)  # Plus compact
        layout.addWidget(self.batch_list)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(4)

        self.add_to_batch_btn = self._create_mini_button("+ Ajouter", self._add_selected_to_batch)
        self.remove_from_batch_btn = self._create_mini_button("Retirer", self._remove_from_batch)
        self.clear_batch_btn = self._create_mini_button("Vider", self._clear_batch)
        self.remove_from_batch_btn.setEnabled(False)

        btn_layout.addWidget(self.add_to_batch_btn)
        btn_layout.addWidget(self.remove_from_batch_btn)
        btn_layout.addWidget(self.clear_batch_btn)
        layout.addLayout(btn_layout)
        return group
    
    def _get_hierarchy_list_style(self):
        """Style avec marqueur VERT aligné à droite"""
        return """
            QListWidget { 
                border: 2px solid #e1e4e8; 
                border-radius: 6px; 
                background-color: white; 
                padding: 4px; 
                font-size: 11px; 
                color: #2c3e50; 
            } 
            QListWidget::item { 
                padding: 6px 8px 6px 8px;
                border-radius: 4px; 
                margin: 1px 0; 
                color: #2c3e50;
                min-height: 24px;
            } 
            QListWidget::item:selected { 
                background-color: #e8f5e9;
                color: #2c3e50; 
            } 
            QListWidget::item:hover { 
                background-color: #f5f5f5; 
                color: #2c3e50; 
            }
        """
    
    def _open_batch_viewer(self):
        """Ouvrir la fenêtre modale de visualisation du batch"""
        if not self.combinations:
            QtWidgets.QMessageBox.information(
                self, 
                "Info", 
                "Aucune combinaison dans le batch."
            )
            return

        # Préparer les données du batch
        batch_data = {
            'batch_name': self.batch_name_edit.text().strip() or "Batch sans nom",
            'batch_family': self.batch_family_edit.text().strip(),
            'project_name': self.project_combo.currentText() if self.project_combo.currentIndex() > 0 else "N/A",
            'description': self.desc_edit.toPlainText(),
            'combinations': self.combinations,
            'count': len(self.combinations)
        }

        # Ouvrir la fenêtre
        viewer = BatchViewerWindow(batch_data, parent=self)
        viewer.exec_()

    def _connect_hierarchy_signals(self):
        """
        Connecter tous les signaux - VERSION CORRIGÉE
        """
        # Clics simples pour navigation
        self.context_typologie_list.itemClicked.connect(self._on_typologie_clicked)
        self.context_taxonomy_list.itemClicked.connect(self._on_taxonomy_clicked)
        self.context_root_list.itemClicked.connect(self._on_root_clicked)
        self.context_parent_list.itemClicked.connect(self._on_parent_clicked)

        # Double-clics pour toggle batch (sauf enfants qui ont leur propre logique)
        self.context_typologie_list.itemDoubleClicked.connect(self._toggle_item_in_batch)
        self.context_taxonomy_list.itemDoubleClicked.connect(self._toggle_item_in_batch)
        self.context_root_list.itemDoubleClicked.connect(self._toggle_item_in_batch)
        self.context_parent_list.itemDoubleClicked.connect(self._toggle_item_in_batch)

        # ✅ Enfants : comportement spécial avec méthode dédiée
        self.context_child_list.itemClicked.connect(self._on_child_clicked)
        self.context_child_list.itemDoubleClicked.connect(self._on_child_double_clicked)
        self.context_child_list.itemSelectionChanged.connect(self._on_child_selection_changed)

    # ========== NAVIGATION ==========

    def _on_typologie_clicked(self, item):
        if not item:
            return
        typ_name = item.text()
        typologie = self._find_typologie_by_name(typ_name)
        if not typologie:
            return
        
        self._context_navigation = {'typologie': typologie, 'taxonomy': None, 'root': None, 'parent': None, 'child_path': []}
        
        self.context_taxonomy_list.clear()
        for cluster in typologie.get('taxonomy_clusters', []):
            cluster_name = cluster.get('name', '')
            if cluster_name:
                it = QtWidgets.QListWidgetItem(cluster_name)
                it.setData(Qt.UserRole, cluster)
                self.context_taxonomy_list.addItem(it)
        
        self.context_root_list.clear()
        self.context_parent_list.clear()
        self.context_child_list.clear()
        self._update_navigation_breadcrumb()
        self._mark_current_selections()

    def _on_child_selection_changed(self):
        """Appelé quand la sélection change dans la liste des enfants"""
        self._update_child_navigation_buttons()

    def _update_child_navigation_buttons(self):
        """
        Met à jour l'état des boutons avec feedback visuel
        """
        depth = len(self._context_navigation.get('child_path', []))
        self.child_up_btn.setEnabled(depth > 0)

        # Bouton descendre : UN SEUL item sélectionné ET il a des enfants
        selected_items = self.context_child_list.selectedItems()
        can_descend = False

        if len(selected_items) == 1:
            child_data = selected_items[0].data(Qt.UserRole)
            if child_data:
                can_descend = child_data.get('has_children', False)

        self.child_down_btn.setEnabled(can_descend)

        # ✅ Feedback visuel dans le tooltip
        if len(selected_items) > 1:
            self.child_down_btn.setToolTip(
                "⚠️ Sélectionnez UN SEUL élément pour descendre\n"
                "Pour ajouter plusieurs éléments : utilisez le double-clic"
            )
        elif len(selected_items) == 1 and not can_descend:
            self.child_down_btn.setToolTip(
                "⚠️ Cet élément n'a pas d'enfants\n"
                "Vous pouvez l'ajouter au batch avec un double-clic"
            )
        else:
            self.child_down_btn.setToolTip("Descendre dans l'élément sélectionné")

        logger.debug(f"Boutons nav: Remonter={depth > 0}, Descendre={can_descend}")

    def _navigate_down_child(self):
        """
        Bouton "Descendre" : navigation explicite dans la hiérarchie
        """
        selected_items = self.context_child_list.selectedItems()

        if not selected_items:
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Veuillez sélectionner un élément pour naviguer."
            )
            return

        if len(selected_items) > 1:
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Veuillez sélectionner UN SEUL élément pour descendre dans la hiérarchie.\n"
                "Pour ajouter plusieurs éléments au batch, utilisez le double-clic ou le bouton '+ Ajouter'."
            )
            return

        current_item = selected_items[0]
        child_data = current_item.data(Qt.UserRole)

        if not child_data:
            logger.warning("Item sans données")
            return

        child = child_data.get('child')
        if not child or not child.get('children'):
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Cet élément n'a pas d'enfants.\n"
                "Vous pouvez l'ajouter au batch avec un double-clic."
            )
            return

        # ✅ Navigation : descendre d'un niveau
        child_name = child.get('name', '')
        logger.info(f"Navigation vers les enfants de: {child_name}")

        self._context_navigation['child_path'].append(child_name)
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        # Charger le niveau suivant
        self._load_children_at_level(
            child.get('children', []),
            child_data.get('cluster'),
            child_data.get('root'),
            child_data.get('parent')
        )

        self._update_child_breadcrumb()
        self._update_child_navigation_buttons()

    def _get_item_path_for_batch(self, level, data, item=None):
        """Génère une clé de chemin unique pour un élément."""
        nav = self._context_navigation

        if level == 'typologie' and item:
            return f"typologie/{item.text()}"

        elif level == 'taxonomy' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{data.get('name', '')}"

        elif level == 'root' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = data.get('cluster', {}).get('name', '')
            root_name = data.get('root', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root_name}"

        elif level == 'parent' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = data.get('cluster', {}).get('name', '')
            root_name = data.get('root', {}).get('name', '')
            parent_name = data.get('parent', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root_name}/parent/{parent_name}"

        elif level == 'child' and data:
            # ✅ CORRECTION : Utiliser exactement le même format que _generate_path_key_from_selection
            typologie = data.get('typologie', '')
            child_path = data.get('path', [])

            if not typologie or not child_path:
                logger.warning(f"❌ Données incomplètes pour child: typ={typologie}, path={child_path}")
                return None

            return f"typologie/{typologie}/child_path/{' > '.join(child_path)}"

        return None
    
    def _mark_current_selections(self):
        """Marque les éléments dans TOUTES les listes de hiérarchie visibles qui sont déjà dans le batch."""
        
        # 1. Obtenir toutes les clés de chemin actuellement dans le batch
        batch_keys = set(c.get('path_key') for c in self.combinations if c.get('path_key'))
        
        # 2. Marquer TOUTES les listes visibles (pas seulement la plus profonde)
        nav = self._context_navigation
        
        # Toujours marquer la liste des typologies si visible
        if self.context_typologie_list.count() > 0:
            self._mark_list_items(self.context_typologie_list, 'typologie', batch_keys)
        
        # Marquer la liste des taxonomies si une typologie est sélectionnée
        if nav.get('typologie') and self.context_taxonomy_list.count() > 0:
            self._mark_list_items(self.context_taxonomy_list, 'taxonomy', batch_keys)
        
        # Marquer la liste des roots si une taxonomy est sélectionnée
        if nav.get('taxonomy') and self.context_root_list.count() > 0:
            self._mark_list_items(self.context_root_list, 'root', batch_keys)
        
        # Marquer la liste des parents si un root est sélectionné
        if nav.get('root') and self.context_parent_list.count() > 0:
            self._mark_list_items(self.context_parent_list, 'parent', batch_keys)
        
        # Marquer la liste des enfants si un parent est sélectionné
        if nav.get('parent') and self.context_child_list.count() > 0:
            self._mark_list_items(self.context_child_list, 'child', batch_keys)

    def _mark_list_items(self, list_widget, level, batch_keys):
        """Marque les items d'une liste spécifique selon leur présence dans le batch."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            data = item.data(Qt.UserRole)

            # ✅ CORRECTION : Pour les enfants, utiliser la même logique que _generate_path_key_from_selection
            if level == 'child' and data:
                typologie = data.get('typologie', '')
                child_path = data.get('path', [])

                if typologie and child_path:
                    path_key = f"typologie/{typologie}/child_path/{' > '.join(child_path)}"
                else:
                    path_key = None
            else:
                # Pour les autres niveaux, utiliser la méthode existante
                path_key = self._get_item_path_for_batch(level, data, item)

            is_selected = path_key in batch_keys if path_key else False
            self._update_item_icon(item, is_selected)


    def _on_taxonomy_clicked(self, item):
        if not item:
            return
        cluster = item.data(Qt.UserRole)
        if not cluster:
            return
        
        self._context_navigation['taxonomy'] = cluster
        self._context_navigation['root'] = None
        self._context_navigation['parent'] = None
        self._context_navigation['child_path'] = []
        
        self.context_root_list.clear()
        for root in cluster.get('root_labels', []):
            root_name = root.get('name', '')
            if root_name:
                it = QtWidgets.QListWidgetItem(root_name)
                it.setData(Qt.UserRole, {'root': root, 'cluster': cluster})
                self.context_root_list.addItem(it)
        
        self.context_parent_list.clear()
        self.context_child_list.clear()
        self._update_navigation_breadcrumb()
        self._mark_current_selections()

    def _on_root_clicked(self, item):
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        root = data.get('root')
        cluster = data.get('cluster')
        
        self._context_navigation['root'] = root
        self._context_navigation['parent'] = None
        self._context_navigation['child_path'] = []
        
        self.context_parent_list.clear()
        for parent in root.get('parent_labels', []):
            parent_name = parent.get('name', '')
            if parent_name:
                it = QtWidgets.QListWidgetItem(parent_name)
                it.setData(Qt.UserRole, {'parent': parent, 'root': root, 'cluster': cluster})
                self.context_parent_list.addItem(it)
        
        self.context_child_list.clear()
        self._update_navigation_breadcrumb()
        self._mark_current_selections()

    def _on_parent_clicked(self, item):
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        parent = data.get('parent')
        root = data.get('root')
        cluster = data.get('cluster')
        
        self._context_navigation['parent'] = parent
        self._context_navigation['child_path'] = []
        
        self._load_children_at_level(parent.get('children', []), cluster, root, parent)
        self._update_navigation_breadcrumb()
        self._update_child_breadcrumb()
        self._mark_current_selections()

    def _on_child_clicked(self, item):
        """
        Clic simple sur un enfant = sélection uniquement
        CTRL+Clic = sélection multiple
        """
        if not item:
            return

        # ✅ Permettre la sélection libre sans interférer
        logger.debug(f"Sélection enfant: {item.text()}")

        # Mise à jour des boutons de navigation basée sur la sélection
        self._update_child_navigation_buttons()

        # ✅ NOUVEAU : Marquer visuellement si déjà dans le batch
        self._mark_current_selections()

    def _on_child_double_clicked(self, item):
        """
        Double-clic sur enfant : ajouter/retirer DIRECTEMENT du batch
        Sans passer par _get_all_selections() qui peut échouer
        """
        if not item:
            return

        logger.info(f"=== Double-clic sur enfant: {item.text()} ===")

        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return

        # ✅ Récupérer DIRECTEMENT les données de l'item
        child_data = item.data(Qt.UserRole)

        if not child_data:
            logger.error("❌ Pas de données Qt.UserRole sur l'item")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                "Impossible de récupérer les données de l'élément."
            )
            return

        # ✅ Construire la sélection directement
        selection = self._build_selection_from_child_data(child_data)

        if not selection:
            logger.error("❌ Impossible de construire la sélection")
            return

        # ✅ Toggle dans le batch
        self._toggle_single_selection_in_batch(selection)

    def _build_selection_from_child_data(self, child_data):
        """
        Construit un dictionnaire de sélection depuis les données d'un enfant
        VERSION SÉCURISÉE CORRIGÉE
        """
        try:
            child = child_data.get('child', {})
            child_path = child_data.get('path', [])

            if not child_path:
                logger.error("❌ Pas de chemin dans child_data")
                return None

            # ✅ CORRECTION : Toujours récupérer la typologie depuis child_data
            # car elle est stockée lors du _load_children_at_level
            typologie = child_data.get('typologie', '')

            if not typologie:
                logger.error("❌ Pas de typologie dans child_data!")
                logger.debug(f"child_data: {child_data}")
                return None

            child_name = child_path[-1] if child_path else child.get('name', '')

            # Navigation actuelle
            nav = self._context_navigation

            selection = {
                'level': 'child',
                'typologie': typologie,  # ✅ Typologie garantie depuis child_data
                'taxonomy': nav.get('taxonomy', {}).get('name', ''),
                'root': nav.get('root', {}).get('name', ''),
                'parent': nav.get('parent', {}).get('name', ''),
                'child_path': child_path,
                'child': child_name,
                'display': self._build_display_text_from_nav(typologie, child_path)
            }

            logger.debug(f"✅ Sélection construite: {selection['display']}")
            logger.debug(f"   Path key sera: typologie/{typologie}/child_path/{' > '.join(child_path)}")

            return selection

        except Exception as e:
            logger.error(f"❌ Erreur construction sélection: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
    def _build_display_text_from_nav(self, typologie, child_path):
        """
        Construit le texte d'affichage depuis la navigation actuelle
        """
        nav = self._context_navigation
        parts = [typologie]

        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', ''))
        if nav.get('root'):
            parts.append(nav['root'].get('name', ''))
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', ''))

        if child_path:
            parts.append(' > '.join(child_path))

        return ' / '.join(parts)

    def _build_display_text(self, child_data, child_path):
        """
        Construit le texte d'affichage pour une sélection d'enfant
        """
        nav = self._context_navigation
        parts = []

        # Typologie
        typ_name = child_data.get('typologie', '') or nav.get('typologie', {}).get('name', '')
        if typ_name:
            parts.append(typ_name)

        # Taxonomy
        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', ''))

        # Root
        if nav.get('root'):
            parts.append(nav['root'].get('name', ''))

        # Parent
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', ''))

        # Chemin complet des enfants
        if child_path:
            parts.append(' > '.join(child_path))

        return ' / '.join(parts)
    
    def _load_children_at_level(self, children_list, cluster, root, parent):
        """
        Charge les enfants avec TOUTES les données nécessaires
        VERSION AVEC VÉRIFICATION TYPOLOGIE
        """
        logger.debug(f"=== _load_children_at_level ===")

        nav = self._context_navigation
        typologie_name = nav.get('typologie', {}).get('name', '') if nav.get('typologie') else ''

        if not typologie_name:
            logger.error("❌ CRITIQUE: Pas de typologie dans la navigation!")
            logger.debug(f"Navigation state: {nav}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                "Impossible de charger les enfants : typologie non définie."
            )
            return

        logger.info(f"Chargement de {len(children_list)} enfants pour typologie: {typologie_name}")

        self.context_child_list.clear()

        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                continue
            
            current_path = nav.get('child_path', []) + [child_name]
            has_children = bool(child.get('children'))
            prefix = "▶" if has_children else "•"

            it = QtWidgets.QListWidgetItem(f"{prefix} {child_name}")

            # ✅ Stocker TOUTES les infos nécessaires
            item_data = {
                'child': child,
                'parent': parent,
                'root': root,
                'cluster': cluster,
                'path': current_path,
                'typologie': typologie_name,  # ✅ CRITIQUE
                'has_children': has_children,
                'original_name': child_name,
                'prefix': prefix
            }

            it.setData(Qt.UserRole, item_data)
            self.context_child_list.addItem(it)

            logger.debug(f"  ✅ {child_name} | path={current_path} | typ={typologie_name}")

        self._update_child_navigation_buttons()
        self._mark_current_selections()


    def _toggle_single_selection_in_batch(self, selection):
        """
        Toggle UNE SEULE sélection dans le batch
        Utilisé par le double-clic sur les enfants
        """
        if not selection:
            logger.error("❌ Sélection vide")
            return

        logger.info(f"=== Toggle single selection: {selection.get('display', 'N/A')} ===")

        # Générer la clé de chemin
        path_key = self._generate_path_key_from_selection(selection)

        if not path_key:
            logger.error("❌ Impossible de générer path_key")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                "Impossible d'identifier l'élément sélectionné."
            )
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')
        display_text = f"{master_name} ⇒ {selection['display']}"

        logger.debug(f"Path key: {path_key}")
        logger.debug(f"Display: {display_text}")

        # Chercher si cette combinaison existe déjà
        existing_index = None
        for i, combo in enumerate(self.combinations):
            if combo.get('path_key') == path_key:
                existing_index = i
                break

        if existing_index is not None:
            # ✅ RETIRER du batch
            del self.combinations[existing_index]

            # Retirer de la liste visuelle
            for i in range(self.batch_list.count()):
                if self.batch_list.item(i).text() == display_text:
                    self.batch_list.takeItem(i)
                    break

            logger.info(f"✅ RETIRÉ du batch: {display_text}")

            # ✅ Mise à jour immédiate de l'icône
            self._update_specific_child_item(path_key, was_added=False)

        else:
            # ✅ AJOUTER au batch
            combination = {
                'master': {'name': master_name, 'data': self.selected_master_typologie},
                'context': selection,
                'display': display_text,
                'path_key': path_key
            }
            self.combinations.append(combination)
            self.batch_list.addItem(display_text)

            logger.info(f"✅ AJOUTÉ au batch: {display_text}")

            # ✅ Mise à jour immédiate de l'icône
            self._update_specific_child_item(path_key, was_added=True)

        # Rafraîchir les stats
        self._update_stats()

        logger.info(f"Batch contient maintenant {len(self.combinations)} combinaison(s)")

    def _update_specific_child_item(self, path_key, was_added):
        """
        Met à jour UN item enfant spécifique immédiatement après le toggle
        
        Args:
            path_key: La clé du chemin de l'item
            was_added: True si l'item vient d'être AJOUTÉ au batch, False s'il vient d'être RETIRÉ
        """
        for i in range(self.context_child_list.count()):
            item = self.context_child_list.item(i)
            item_data = item.data(Qt.UserRole)
            
            if not item_data:
                continue
                
            # Construire le path_key de cet item
            item_path_key = self._generate_path_key_from_child_data(item_data)
            
            if item_path_key == path_key:
                logger.debug(f"🔄 Mise à jour directe de l'item: {item.text()}")
                logger.debug(f"   was_added={was_added} (True=ajouté, False=retiré)")
                
                # ✅ CORRECTION : Utiliser directement was_added sans inversion
                self._update_item_icon(item, was_added)
                
                # ✅ Forcer le repaint de cet item
                self.context_child_list.update(self.context_child_list.indexFromItem(item))
                
                logger.debug(f"✅ Item mis à jour: is_selected={was_added}")
                break

    def _generate_path_key_from_child_data(self, child_data):
        """
        Génère un path_key depuis les données d'un item enfant
        """
        typologie = child_data.get('typologie', '')
        path = child_data.get('path', [])

        if not typologie or not path:
            return None

        return f"typologie/{typologie}/child_path/{' > '.join(path)}"

    def toggle_batch_selection(self, item_path):
        """Toggle la sélection d'un item dans le batch"""
        if item_path in self.batch_selections:
            self.batch_selections.remove(item_path)
            logger.info(f"✅ RETIRÉ du batch: {item_path}")
        else:
            self.batch_selections.add(item_path)
            logger.info(f"✅ AJOUTÉ au batch: {item_path}")

        self.update_batch_visual_indicators()  # Mettre à jour les checkmarks
        self.update_batch_counter()

    def update_batch_visual_indicators(self):
        """Met à jour les indicateurs visuels (✔) pour tous les items"""
        def update_tree_item(item):
            item_path = self.get_item_full_path(item)
            text = self.tree.item(item, 'text')

            # Retirer l'ancien checkmark
            text = text.replace(' ✔', '').strip()

            # Ajouter le checkmark si dans le batch
            if item_path in self.batch_selections:
                text = f"{text} ✔"
                # Style visuel supplémentaire
                self.tree.item(item, text=text, tags=('in_batch',))
            else:
                self.tree.item(item, text=text, tags=())

            # Récursif pour les enfants
            for child in self.tree.get_children(item):
                update_tree_item(child)

        # Appliquer à tous les items racines
        for item in self.tree.get_children():
            update_tree_item(item)

        # Configurer le style pour les items dans le batch
        self.tree.tag_configure('in_batch', 
                               background='#E8F5E9',  # Vert clair
                               foreground='#2E7D32')  # Vert foncé
        
    def update_batch_counter(self):
        """Met à jour le compteur de sélections"""
        count = len(self.batch_selections)

        # Si vous avez un label pour afficher le compteur :
        if hasattr(self, 'batch_counter_label'):
            self.batch_counter_label.config(
                text=f"📦 Sélectionnés: {count}"
            )

        logger.info(f"Interface mise à jour : {count} combinaison(s) au total")

    def _toggle_item_in_batch(self):
        """Ajoute l'élément sélectionné au batch s'il n'y est pas, sinon le retire"""
        logger.info("=== _toggle_item_in_batch appelée ===")

        if not self.selected_master_typologie:
            logger.warning("Pas de typologie master sélectionnée")
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez sélectionner une typologie master.")
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')
        logger.info(f"Typologie master: {master_name}")

        # Récupérer les sélections
        selections = self._get_all_selections()

        logger.info(f"Nombre de sélections trouvées: {len(selections)}")

        if not selections:
            logger.warning("❌ Aucune sélection trouvée pour toggle!")
            QtWidgets.QMessageBox.information(
                self, 
                "Information", 
                "Aucun élément sélectionné. Veuillez sélectionner un élément dans la hiérarchie."
            )
            return

        # Pour chaque sélection
        toggled_count = 0
        for sel in selections:
            path_key = self._generate_path_key_from_selection(sel)
            display_text = f"{master_name} ⇒ {sel['display']}"

            logger.debug(f"Traitement: {display_text}")
            logger.debug(f"Path key: {path_key}")

            # Chercher si cette combinaison existe déjà 
            existing_index = None
            for i, combo in enumerate(self.combinations):
                if combo.get('path_key') == path_key:
                    existing_index = i
                    break
                
            if existing_index is not None:
                # RETIRER du batch
                del self.combinations[existing_index]

                # Retirer de la liste visuelle
                for i in range(self.batch_list.count()):
                    if self.batch_list.item(i).text() == display_text:
                        self.batch_list.takeItem(i)
                        break
                    
                logger.info(f"✅ Combinaison RETIRÉE: {display_text}")
                toggled_count += 1
            else:
                # AJOUTER au batch
                combination = {
                    'master': {'name': master_name, 'data': self.selected_master_typologie},
                    'context': sel,
                    'display': display_text,
                    'path_key': path_key
                }
                self.combinations.append(combination)
                self.batch_list.addItem(display_text)
                logger.info(f"✅ Combinaison AJOUTÉE: {display_text}")
                toggled_count += 1

        if toggled_count > 0:
            # Rafraîchir l'affichage
            self._update_stats()
            self._mark_current_selections()
            logger.info(f"✅ {toggled_count} élément(s) toggleé(s) avec succès")
        else:
            logger.warning("⚠️ Aucun élément n'a été toggleé")

    def _load_children_at_level(self, children_list, cluster, root, parent):
        """
        Charge les enfants avec TOUTES les données nécessaires
        VERSION CORRIGÉE - Stocke le texte original
        """
        logger.debug(f"=== _load_children_at_level ===")
        logger.debug(f"Nombre d'enfants: {len(children_list)}")
        logger.debug(f"Child path actuel: {self._context_navigation.get('child_path', [])}")

        self.context_child_list.clear()

        if not children_list:
            return

        # ✅ CRITIQUE : Récupérer la typologie depuis la navigation
        nav = self._context_navigation
        typologie_name = nav.get('typologie', {}).get('name', '') if nav.get('typologie') else ''

        if not typologie_name:
            logger.error("❌ Pas de typologie dans la navigation!")
            return

        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                logger.warning(f"⚠️ Enfant sans nom, ignoré")
                continue
            
            # ✅ Construire le chemin COMPLET
            current_path = self._context_navigation.get('child_path', []) + [child_name]

            # Affichage avec indicateur
            has_children = bool(child.get('children'))
            prefix = "▶" if has_children else "•"

            it = QtWidgets.QListWidgetItem(f"{prefix} {child_name}")

            # ✅✅✅ CORRECTION CRITIQUE : Stocker le nom original et le préfixe
            item_data = {
                'child': child,
                'parent': parent,
                'root': root,
                'cluster': cluster,
                'path': current_path,
                'typologie': typologie_name,
                'has_children': has_children,
                'original_name': child_name,  # ✅ AJOUT
                'prefix': prefix  # ✅ AJOUT
            }

            it.setData(Qt.UserRole, item_data)
            self.context_child_list.addItem(it)

            logger.debug(f"✅ Enfant ajouté: {child_name}")
            logger.debug(f"   Typologie: {typologie_name}")
            logger.debug(f"   Path: {current_path}")

        self._update_child_navigation_buttons()
        self._mark_current_selections()

    def _navigate_up_child(self):
        """Remonte d'un niveau dans la hiérarchie des enfants - VERSION CORRIGÉE"""
        logger.info("=== Remontée d'un niveau enfant ===")

        if not self._context_navigation['child_path']:
            logger.warning("Déjà au niveau racine, impossible de remonter")
            return

        # Retirer le dernier élément du chemin
        removed = self._context_navigation['child_path'].pop()
        logger.info(f"Retrait du chemin: {removed}")
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        parent = self._context_navigation.get('parent')
        if not parent:
            logger.warning("Pas de parent défini, vidage de la liste")
            self.context_child_list.clear()
            self._update_child_breadcrumb()
            self._mark_current_selections()
            return

        # Reconstruire la liste des enfants au niveau actuel
        current_children = parent.get('children', [])
        logger.debug(f"Démarrage depuis parent avec {len(current_children)} enfants")

        # Suivre le chemin pour retrouver le bon niveau
        for path_item in self._context_navigation['child_path']:
            logger.debug(f"Navigation vers: {path_item}")
            found = False
            for child in current_children:
                if child.get('name') == path_item:
                    current_children = child.get('children', [])
                    found = True
                    logger.debug(f"  -> Trouvé, {len(current_children)} enfants au niveau suivant")
                    break
            if not found:
                logger.warning(f"❌ Chemin '{path_item}' non trouvé!")
                break
            
        # Recharger la liste
        self._load_children_at_level(
            current_children,
            self._context_navigation.get('taxonomy'),
            self._context_navigation.get('root'),
            parent
        )
    def _navigate_up_child(self):
        """Remonte d'un niveau dans la hiérarchie des enfants"""
        logger.info("=== Remontée d'un niveau enfant ===")

        if not self._context_navigation['child_path']:
            logger.warning("Déjà au niveau racine, impossible de remonter")
            return

        # Retirer le dernier élément du chemin
        removed = self._context_navigation['child_path'].pop()
        logger.info(f"Retrait du chemin: {removed}")
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        parent = self._context_navigation.get('parent')
        if not parent:
            logger.warning("Pas de parent défini, vidage de la liste")
            self.context_child_list.clear()
            self._update_child_breadcrumb()
            self._update_child_navigation_buttons()
            self._mark_current_selections()
            return

        # Reconstruire la liste des enfants au niveau actuel
        current_children = parent.get('children', [])
        logger.debug(f"Démarrage depuis parent avec {len(current_children)} enfants")

        # Suivre le chemin pour retrouver le bon niveau
        for path_item in self._context_navigation['child_path']:
            logger.debug(f"Navigation vers: {path_item}")
            found = False
            for child in current_children:
                if child.get('name') == path_item:
                    current_children = child.get('children', [])
                    found = True
                    logger.debug(f"  -> Trouvé, {len(current_children)} enfants au niveau suivant")
                    break
            if not found:
                logger.warning(f"❌ Chemin '{path_item}' non trouvé!")
                break
            
        # Recharger la liste
        self._load_children_at_level(
            current_children,
            self._context_navigation.get('taxonomy'),
            self._context_navigation.get('root'),
            parent
        )

        self._update_child_breadcrumb()
        self._update_child_navigation_buttons()
        self._update_child_breadcrumb()

    def _reset_navigation(self):
        self._context_navigation = {'typologie': None, 'taxonomy': None, 'root': None, 'parent': None, 'child_path': []}
        self.context_typologie_list.clearSelection()
        self.context_taxonomy_list.clear()
        self.context_root_list.clear()
        self.context_parent_list.clear()
        self.context_child_list.clear()
        self._update_navigation_breadcrumb()
        self._update_child_breadcrumb()

    def _update_navigation_breadcrumb(self):
        parts = []
        nav = self._context_navigation
        if nav.get('typologie'):
            parts.append(nav['typologie'].get('name', '?'))
        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', '?'))
        if nav.get('root'):
            parts.append(nav['root'].get('name', '?'))
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', '?'))
        self.nav_breadcrumb.setText(" → ".join(parts) if parts else "Sélectionnez une typologie")

    def _update_child_breadcrumb(self):
        """Met à jour le breadcrumb de navigation dans les enfants"""
        path = self._context_navigation.get('child_path', [])
        depth = len(path)

        if depth == 0:
            self.child_breadcrumb.setText("Niveau racine (enfants directs)")
        else:
            # Afficher les 2 derniers niveaux si plus de 2
            path_str = " → ".join(path[-2:]) if depth > 2 else " → ".join(path)
            if depth > 2:
                path_str = "... → " + path_str
            self.child_breadcrumb.setText(f"{path_str} (niveau {depth + 1})")

    # ========== BATCH ==========

    def _get_all_selections(self):
        """Récupérer toutes les sélections actives - VERSION SÉCURISÉE"""
        selections = []
        nav = self._context_navigation

        logger.debug(f"=== _get_all_selections ===")

        # ✅ Extraction sécurisée des noms depuis la navigation
        typ_name = nav.get('typologie').get('name') if nav.get('typologie') else None
        tax_name = nav.get('taxonomy').get('name') if nav.get('taxonomy') else None
        root_name = nav.get('root').get('name') if nav.get('root') else None
        parent_name = nav.get('parent').get('name') if nav.get('parent') else None

        logger.debug(f"Navigation state: typ={typ_name}, tax={tax_name}, "
                     f"root={root_name}, parent={parent_name}, "
                     f"child_path={nav.get('child_path', [])}")

        # ENFANTS - Priorité 1
        child_items = self.context_child_list.selectedItems()
        logger.debug(f"Enfants sélectionnés: {len(child_items)}")

        if child_items:
            for item in child_items:
                data = item.data(Qt.UserRole)
                if not data:
                    logger.warning(f"❌ Item enfant sans données Qt.UserRole: {item.text()}")
                    continue
                
                path = data.get('path', [])
                if not path:
                    logger.warning(f"❌ Item enfant sans chemin 'path': {item.text()}")
                    # Essayer de récupérer depuis child_name
                    child_name = item.text().replace('▶ ', '').strip()
                    if nav.get('parent'):
                        # Construire un chemin minimal
                        path = nav.get('child_path', []) + [child_name]
                        logger.info(f"⚠️ Chemin reconstruit: {path}")
                    else:
                        continue
                    
                child_name = path[-1] if path else item.text().replace('▶ ', '').strip()

                # Vérification de la navigation minimale
                if not nav.get('typologie'):
                    logger.error("❌ Navigation incomplète: pas de typologie définie!")
                    continue
                
                # Construction du display
                display_parts = []
                if nav.get('typologie'):
                    display_parts.append(nav['typologie'].get('name', ''))
                if nav.get('taxonomy'):
                    display_parts.append(nav['taxonomy'].get('name', ''))
                if nav.get('root'):
                    display_parts.append(nav['root'].get('name', ''))
                if nav.get('parent'):
                    display_parts.append(nav['parent'].get('name', ''))
                display_parts.append(' > '.join(path))

                selection = {
                    'level': 'child',
                    'typologie': nav.get('typologie', {}).get('name', ''),
                    'taxonomy': nav.get('taxonomy', {}).get('name', ''),
                    'root': nav.get('root', {}).get('name', ''),
                    'parent': nav.get('parent', {}).get('name', ''),
                    'child_path': path,
                    'child': child_name,
                    'display': ' / '.join(display_parts)
                }
                selections.append(selection)
                logger.debug(f"✅ Enfant ajouté: {selection['display']}")

            if not selections:
                logger.warning(f"⚠️ {len(child_items)} enfants sélectionnés mais AUCUNE sélection valide!")
            else:
                logger.info(f"✅ {len(selections)} sélection(s) d'enfants validée(s)")

            return selections

        # PARENTS - Priorité 2
        parent_items = self.context_parent_list.selectedItems()
        logger.debug(f"Parents sélectionnés: {len(parent_items)}")

        if parent_items:
            for item in parent_items:
                data = item.data(Qt.UserRole)
                if not data:
                    logger.warning(f"❌ Item parent sans données: {item.text()}")
                    continue
                
                parent = data.get('parent', {})
                if not parent:
                    logger.warning(f"❌ Item parent sans objet 'parent': {item.text()}")
                    continue
                
                if not nav.get('typologie'):
                    logger.error("❌ Navigation incomplète: pas de typologie!")
                    continue
                
                display_parts = []
                if nav.get('typologie'):
                    display_parts.append(nav['typologie'].get('name', ''))
                if nav.get('taxonomy'):
                    display_parts.append(nav['taxonomy'].get('name', ''))
                if nav.get('root'):
                    display_parts.append(nav['root'].get('name', ''))
                display_parts.append(parent.get('name', ''))

                selection = {
                    'level': 'parent',
                    'typologie': nav.get('typologie', {}).get('name', ''),
                    'taxonomy': nav.get('taxonomy', {}).get('name', ''),
                    'root': nav.get('root', {}).get('name', ''),
                    'parent': parent.get('name', ''),
                    'child_path': [],
                    'child': '',
                    'display': ' / '.join(display_parts)
                }
                selections.append(selection)
                logger.debug(f"✅ Parent ajouté: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) de parents validée(s)")
            return selections

        # ROOTS - Priorité 3
        root_items = self.context_root_list.selectedItems()
        logger.debug(f"Roots sélectionnés: {len(root_items)}")

        if root_items:
            for item in root_items:
                data = item.data(Qt.UserRole)
                if not data:
                    logger.warning(f"❌ Item root sans données: {item.text()}")
                    continue
                
                root = data.get('root', {})
                if not root:
                    logger.warning(f"❌ Item root sans objet 'root': {item.text()}")
                    continue
                
                if not nav.get('typologie'):
                    logger.error("❌ Navigation incomplète: pas de typologie!")
                    continue
                
                display_parts = []
                if nav.get('typologie'):
                    display_parts.append(nav['typologie'].get('name', ''))
                if nav.get('taxonomy'):
                    display_parts.append(nav['taxonomy'].get('name', ''))
                display_parts.append(root.get('name', ''))

                selection = {
                    'level': 'root',
                    'typologie': nav.get('typologie', {}).get('name', ''),
                    'taxonomy': nav.get('taxonomy', {}).get('name', ''),
                    'root': root.get('name', ''),
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': ' / '.join(display_parts)
                }
                selections.append(selection)
                logger.debug(f"✅ Root ajouté: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) de roots validée(s)")
            return selections

        # TAXONOMY - Priorité 4
        tax_items = self.context_taxonomy_list.selectedItems()
        logger.debug(f"Taxonomies sélectionnées: {len(tax_items)}")

        if tax_items:
            for item in tax_items:
                data = item.data(Qt.UserRole)
                if not data:
                    logger.warning(f"❌ Item taxonomy sans données: {item.text()}")
                    continue
                
                if not nav.get('typologie'):
                    logger.error("❌ Navigation incomplète: pas de typologie!")
                    continue
                
                display_parts = []
                if nav.get('typologie'):
                    display_parts.append(nav['typologie'].get('name', ''))
                display_parts.append(data.get('name', ''))

                selection = {
                    'level': 'taxonomy',
                    'typologie': nav.get('typologie', {}).get('name', ''),
                    'taxonomy': data.get('name', ''),
                    'root': '',
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': ' / '.join(display_parts)
                }
                selections.append(selection)
                logger.debug(f"✅ Taxonomy ajoutée: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) de taxonomies validée(s)")
            return selections

        # TYPOLOGIE - Priorité 5
        typ_items = self.context_typologie_list.selectedItems()
        logger.debug(f"Typologies sélectionnées: {len(typ_items)}")

        if typ_items:
            for item in typ_items:
                typ_name = item.text()
                selection = {
                    'level': 'typologie',
                    'typologie': typ_name,
                    'taxonomy': '',
                    'root': '',
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': typ_name
                }
                selections.append(selection)
                logger.debug(f"✅ Typologie ajoutée: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) de typologies validée(s)")
            return selections

        logger.warning("⚠️ Aucune sélection trouvée à aucun niveau!")
        return selections

    def _add_selected_to_batch(self):
        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez sélectionner une typologie master.")
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')
        added_count = 0

        for sel in self._get_all_selections():
            # ✅ AJOUT : Générer la clé de chemin pour cette sélection
            path_key = self._generate_path_key_from_selection(sel)

            display_text = f"{master_name} ⇒ {sel['display']}"
            exists = any(self.batch_list.item(i).text() == display_text for i in range(self.batch_list.count()))

            if not exists:
                combination = {
                    'master': {'name': master_name, 'data': self.selected_master_typologie},
                    'context': sel,
                    'display': display_text,
                    'path_key': path_key  # ✅ Ajouter la clé
                }
                self.combinations.append(combination)
                self.batch_list.addItem(display_text)
                added_count += 1

        if added_count > 0:
            self._update_stats()
            self._mark_current_selections()  # ✅ Rafraîchir les coches
            logger.info(f"{added_count} combinaison(s) ajoutée(s)")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Aucune nouvelle combinaison (doublons ou sélection vide).")

    def _generate_path_key_from_selection(self, sel):
        """
        Génère une clé de chemin unique - VERSION CORRIGÉE
        """
        level = sel.get('level')
        typologie = sel.get('typologie', '')

        logger.debug(f"Génération path_key pour niveau: {level}")
        logger.debug(f"  Typologie: {typologie}")

        if level == 'typologie':
            path_key = f"typologie/{typologie}"

        elif level == 'taxonomy':
            taxonomy = sel.get('taxonomy', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}"

        elif level == 'root':
            taxonomy = sel.get('taxonomy', '')
            root = sel.get('root', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root}"

        elif level == 'parent':
            taxonomy = sel.get('taxonomy', '')
            root = sel.get('root', '')
            parent = sel.get('parent', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root}/parent/{parent}"

        elif level == 'child':
            # ✅ Pour les enfants, utiliser le chemin COMPLET
            child_path = sel.get('child_path', [])

            if not child_path:
                logger.error("❌ child_path vide dans la sélection!")
                return None

            # Construire la clé avec le chemin complet
            path_key = f"typologie/{typologie}/child_path/{' > '.join(child_path)}"

            logger.debug(f"  Child path: {child_path}")
            logger.debug(f"  Path key: {path_key}")

        else:
            logger.error(f"❌ Niveau inconnu: {level}")
            path_key = None

        return path_key

    def _remove_from_batch(self):
        row = self.batch_list.currentRow()
        if row >= 0:
            self.batch_list.takeItem(row)
            if row < len(self.combinations):
                del self.combinations[row]
            self._update_stats()
            self._mark_current_selections()

    def _clear_batch(self):
        if self.batch_list.count() == 0:
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirmation", 
            "Vider toutes les combinaisons?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            self.batch_list.clear()
            self.combinations = []
            self._update_stats()
            self._mark_current_selections()

    def _on_batch_item_selected(self, current, previous):
        self.remove_from_batch_btn.setEnabled(current is not None)

    def _update_stats(self):
        """Mettre à jour les statistiques et activer le bouton de visualisation"""
        count = len(self.combinations)
        self.stats_label.setText(f"Combinaisons: {count}")

        # Activer/désactiver le bouton de visualisation
        if hasattr(self, 'view_batch_btn'):
            self.view_batch_btn.setEnabled(count > 0)

        # Marquer comme non sauvegardé si des modifications ont été faites
        if count > 0 and self.is_batch_saved:
            self.is_batch_saved = False
            if self.current_batch_id:
                self._update_batch_status(f"Batch #{self.current_batch_id} - Modifié (non sauvegardé)")
            else:
                self._update_batch_status("Nouveau batch (non sauvegardé)")

    # ========== ACTIONS ==========

    def _create_action_buttons(self, parent_layout):
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.refresh_btn = self._create_action_button("🔄 Rafraîchir", self.refresh_data)
        btn_layout.addWidget(self.refresh_btn)

        # ✅ NOUVEAU : Bouton Sauvegarder
        self.save_batch_btn = self._create_action_button("💾 Sauvegarder", self._save_batch)
        self.save_batch_btn.setStyleSheet(self._get_secondary_button_style())
        btn_layout.addWidget(self.save_batch_btn)

        # ✅ MODIFIÉ : Bouton Générer ET Sauvegarder
        self.generate_btn = self._create_action_button("⚡ Générer & Enregistrer", self._generate_and_save_batch)
        self.generate_btn.setStyleSheet(self._get_primary_button_style())
        btn_layout.addWidget(self.generate_btn)

        parent_layout.addWidget(btn_container)

    def _new_batch(self):
        """Créer un nouveau batch (réinitialiser l'interface)"""
        if not self.is_batch_saved and self.combinations:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Batch non sauvegardé",
                "Le batch actuel contient des modifications non sauvegardées.\n"
                "Voulez-vous continuer et perdre ces modifications ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        # Réinitialiser
        self.current_batch_id = None
        self.is_batch_saved = False
        self.batch_name_edit.clear()
        self.batch_family_edit.clear()
        self.desc_edit.clear()
        self.batch_list.clear()
        self.combinations = []
        self._update_stats()
        self._update_batch_status("Nouveau batch")

        logger.info("Nouveau batch créé")

    def _save_batch(self):
        """Sauvegarder le batch actuel"""
        batch_name = self.batch_name_edit.text().strip()
        if not batch_name:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez saisir un nom pour le batch."
            )
            return

        if self.project_combo.currentIndex() <= 0:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez sélectionner un projet."
            )
            return

        if not self.combinations:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Aucune combinaison dans le batch."
            )
            return

        # Préparer les données du batch
        batch_data = {
            'batch_name': batch_name,
            'batch_family': self.batch_family_edit.text().strip(),
            'description': self.desc_edit.toPlainText(),
            'master_typologie': self.selected_master_typologie.get('name', '') if self.selected_master_typologie else '',
            'combinations': self.combinations,
            'count': len(self.combinations),
            'created_at': datetime.now().isoformat()
        }

        # Déterminer le batch_number
        project_name = self.project_combo.currentText()
        existing_batches = self.project_manager.get_all_batches()

        if self.current_batch_id:
            # Mise à jour d'un batch existant
            batch_number = self.current_batch_id
            success = self.project_manager.save_batch(
                batch_number,
                len(existing_batches),
                batch_data
            )
            action = "mis à jour"
        else:
            # Nouveau batch
            batch_number = len(existing_batches) + 1
            success = self.project_manager.save_batch(
                batch_number,
                batch_number,
                batch_data
            )
            action = "sauvegardé"
            self.current_batch_id = batch_number

        if success:
            self.is_batch_saved = True
            self._update_batch_status(f"Batch #{batch_number} - Sauvegardé")
            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                f"Batch '{batch_name}' {action} avec succès!\n"
                f"Combinaisons: {len(self.combinations)}"
            )
            logger.info(f"Batch #{batch_number} '{batch_name}' {action}")
        else:
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                f"Impossible de sauvegarder le batch '{batch_name}'"
            )
            logger.error(f"Échec sauvegarde batch '{batch_name}'")

    def _load_batch_dialog(self):
        """Afficher un dialogue pour charger un batch sauvegardé"""
        if self.project_combo.currentIndex() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "Veuillez d'abord sélectionner un projet."
            )
            return

        # Récupérer tous les batches du projet
        batches = self.project_manager.get_all_batches()

        if not batches:
            QtWidgets.QMessageBox.information(
                self,
                "Information",
                "Aucun batch sauvegardé pour ce projet."
            )
            return

        # Créer un dialogue de sélection
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Charger un batch")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Liste des batches
        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_hierarchy_list_style())

        for batch in batches:
            data = batch.get('data', {})
            batch_name = data.get('batch_name', 'Sans nom')
            count = data.get('count', 0)
            status = batch.get('status', 'pending')

            item_text = f"Batch #{batch['batch_number']}: {batch_name} ({count} combinaisons) - {status}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, batch)
            list_widget.addItem(item)

        list_widget.itemDoubleClicked.connect(lambda: dialog.accept())
        layout.addWidget(list_widget)

        # Boutons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        load_btn = QtWidgets.QPushButton("Charger")
        load_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(load_btn)

        cancel_btn = QtWidgets.QPushButton("Annuler")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Afficher le dialogue
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            current_item = list_widget.currentItem()
            if current_item:
                batch = current_item.data(Qt.UserRole)
                self._load_batch(batch)

    def _load_batch(self, batch):
        """Charger un batch dans l'interface"""
        data = batch.get('data', {})

        # Vérifier si le batch actuel a des modifications non sauvegardées
        if not self.is_batch_saved and self.combinations:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Batch non sauvegardé",
                "Le batch actuel contient des modifications non sauvegardées.\n"
                "Voulez-vous continuer et perdre ces modifications ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        # Charger les données
        self.current_batch_id = batch['batch_number']
        self.batch_name_edit.setText(data.get('batch_name', ''))
        self.batch_family_edit.setText(data.get('batch_family', ''))
        self.desc_edit.setPlainText(data.get('description', ''))

        # Charger la typologie master
        master_name = data.get('master_typologie', '')
        if master_name:
            index = self.master_combo.findText(master_name)
            if index > 0:
                self.master_combo.setCurrentIndex(index)

        # Charger les combinaisons
        self.combinations = data.get('combinations', [])

        # Mettre à jour l'affichage
        self.batch_list.clear()
        for combo in self.combinations:
            self.batch_list.addItem(combo.get('display', ''))

        self.is_batch_saved = True
        self._update_stats()
        self._update_batch_status(f"Batch #{batch['batch_number']} - {batch.get('status', 'pending')}")
        self._mark_current_selections()

        logger.info(f"Batch #{batch['batch_number']} '{data.get('batch_name', '')}' chargé")

        QtWidgets.QMessageBox.information(
            self,
            "Succès",
            f"Batch '{data.get('batch_name', '')}' chargé avec succès!\n"
            f"Combinaisons: {len(self.combinations)}"
        )

    def _generate_and_save_batch(self):
        """Générer le batch ET le sauvegarder automatiquement"""
        # Validation
        batch_name = self.batch_name_edit.text().strip()
        if not batch_name:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez saisir un nom pour le batch."
            )
            return

        if self.project_combo.currentIndex() <= 0:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez sélectionner un projet."
            )
            return

        if not self.combinations:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Aucune combinaison dans le batch."
            )
            return

        # 1. Sauvegarder d'abord
        self._save_batch()

        # 2. Émettre le signal pour générer
        if self.is_batch_saved:
            result = {
                'batch_id': self.current_batch_id,
                'batch_name': batch_name,
                'batch_family': self.batch_family_edit.text().strip(),
                'project_name': self.project_combo.currentText(),
                'description': self.desc_edit.toPlainText(),
                'combinations': self.combinations,
                'count': len(self.combinations)
            }
            self.combinations_generated.emit(result)

            # 3. Mettre à jour le statut du batch
            self.project_manager.update_batch_status(
                self.current_batch_id,
                'processing'
            )

            logger.info(f"Batch '{batch_name}' généré et marqué en traitement")

    def _update_batch_status(self, status_text):
        """Mettre à jour l'affichage du statut du batch"""
        self.batch_status_label.setText(status_text)

        # Changer la couleur selon le statut
        if "Sauvegardé" in status_text:
            color = "#27ae60"  # Vert
        elif "Nouveau" in status_text:
            color = "#95a5a6"  # Gris
        elif "processing" in status_text:
            color = "#f39c12"  # Orange
        elif "completed" in status_text:
            color = "#3498db"  # Bleu
        else:
            color = "#95a5a6"

        self.batch_status_label.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 600; padding: 4px;"
        )

    def _get_secondary_button_style(self):
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #95a5a6, stop:1 #7f8c8d);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 25px;
                font-weight: 600;
                font-size: 12px;
                min-width: 140px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7f8c8d, stop:1 #95a5a6);
            }}
            QPushButton:disabled {{
                background: #c0c0c0;
                color: #707070;
            }}
        """

    def _generate_batch(self):
        batch_name = self.batch_name_edit.text().strip()
        if not batch_name:
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez saisir un nom pour le batch.")
            return
        if self.project_combo.currentIndex() <= 0:
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez sélectionner un projet.")
            return
        if not self.combinations:
            QtWidgets.QMessageBox.warning(self, "Attention", "Aucune combinaison dans le batch.")
            return

        result = {
            'batch_name': batch_name,
            'batch_family': self.batch_family_edit.text().strip(),
            'project_name': self.project_combo.currentText(),
            'description': self.desc_edit.toPlainText(),
            'combinations': self.combinations,
            'count': len(self.combinations)
        }
        self.combinations_generated.emit(result)
        QtWidgets.QMessageBox.information(self, "Succès", f"Batch '{batch_name}' généré!\nCombinaisons: {len(self.combinations)}")
        logger.info(f"Batch généré: {batch_name} avec {len(self.combinations)} combinaison(s)")

    # ========== DATA LOADING ==========

    def _load_initial_data(self):
        logger.info("Chargement des données initiales - RelationTab")
        if not self.project_manager:
            return
        self._refresh_typologies_cache()
        self._load_projects()
        self._load_master_typologies()
        self._load_context_typologies()

    def _load_projects(self):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- Sélectionner un projet --")
        
        model = self.project_combo.model()
        if model.rowCount() > 0:
            item = model.item(0)
            if item:
                item.setFont(item.font())
                item.setForeground(QColor("#95a5a6"))

        if self.project_manager:
            for project in self.project_manager.get_all_projects():
                name = project.get('name', '')
                if name:
                    self.project_combo.addItem(name)
            if self.project_manager.current_project_name:
                idx = self.project_combo.findText(self.project_manager.current_project_name)
                if idx >= 0:
                    self.project_combo.setCurrentIndex(idx)
        self.project_combo.blockSignals(False)

    def _on_project_changed(self, index):
        if index <= 0:
            return
        project_name = self.project_combo.currentText()
        if project_name and self.project_manager and self.project_manager.load_project(project_name):
            logger.info(f"Projet '{project_name}' chargé")
            self._refresh_typologies_cache()
            self._load_master_typologies()
            self._load_context_typologies()

    def _refresh_typologies_cache(self):
        self._typologies_cache = []
        if self.project_manager and self.project_manager.current_project_data:
            typologies = self.project_manager.current_project_data.get('typologies', [])
            self._typologies_cache = typologies if isinstance(typologies, list) else []

    def _load_master_typologies(self):
        self.master_combo.blockSignals(True)
        self.master_combo.clear()
        self.master_combo.addItem("-- Sélectionner --")
        
        model = self.master_combo.model()
        if model.rowCount() > 0:
            item = model.item(0)
            if item:
                item.setForeground(QColor("#95a5a6"))

        for typ in self._typologies_cache:
            if isinstance(typ, dict):
                name = typ.get('name', typ.get('nom', ''))
                if name:
                    self.master_combo.addItem(name)
        self.master_combo.blockSignals(False)
        self.master_stats.clear()

    def _load_context_typologies(self):
        self.context_typologie_list.clear()
        master_name = self.selected_master_typologie.get('name', '') if self.selected_master_typologie else None

        for typ in self._typologies_cache:
            if isinstance(typ, dict):
                name = typ.get('name', typ.get('nom', ''))
                if name and name != master_name:
                    it = QtWidgets.QListWidgetItem(name)
                    it.setData(Qt.UserRole, typ)
                    self.context_typologie_list.addItem(it)

        self.context_taxonomy_list.clear()
        self.context_root_list.clear()
        self.context_parent_list.clear()
        self.context_child_list.clear()
        self._context_navigation = {'typologie': None, 'taxonomy': None, 'root': None, 'parent': None, 'child_path': []}
        self._update_navigation_breadcrumb()
        self._update_child_breadcrumb()

    def _on_master_typologie_changed(self, index):
        if index <= 0:
            self.selected_master_typologie = None
            self.master_stats.clear()
            self._load_context_typologies()
            return

        actual_idx = index - 1
        if actual_idx >= len(self._typologies_cache):
            return

        typologie = self._typologies_cache[actual_idx]
        self.selected_master_typologie = typologie

        clusters = typologie.get('taxonomy_clusters', [])
        total_roots = sum(len(c.get('root_labels', [])) for c in clusters)
        total_parents = sum(len(r.get('parent_labels', [])) for c in clusters for r in c.get('root_labels', []))
        total_children = sum(self._count_children_recursive(p.get('children', [])) for c in clusters for r in c.get('root_labels', []) for p in r.get('parent_labels', []))

        self.master_stats.setText(f"{typologie.get('name', 'N/A')}\n\nClusters: {len(clusters)}\nRoots: {total_roots}\nParents: {total_parents}\nEnfants: {total_children}")
        self._load_context_typologies()

    def _count_children_recursive(self, children):
        """Count all children recursively"""
        if not children:
            return 0
        count = len(children)
        for child in children:
            count += self._count_children_recursive(child.get('children', []))
        return count

    def _find_typologie_by_name(self, name):
        for typ in self._typologies_cache:
            if typ.get('name') == name or typ.get('nom') == name:
                return typ
        return None

    # ========== STYLES ==========

    def _create_modern_card(self, title):
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{ font-weight: 600; font-size: 12px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 8px;
                margin-top: 10px; padding-top: 12px; background-color: white; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 8px; background-color: white; color: {Theme.SECONDARY_COLOR}; }}
        """)
        return group

    def _add_form_field(self, layout, label_text, attr_name, placeholder=""):
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(label)
        edit = QtWidgets.QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet("QLineEdit { border: 2px solid #e1e4e8; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; color: #2c3e50; } QLineEdit:focus { border: 2px solid #2c3e50; }")
        edit.setMinimumHeight(32)
        layout.addWidget(edit)
        setattr(self, attr_name, edit)

    def _get_modern_input_style(self):
        svg = self._get_dropdown_svg_path().replace('\\', '/')
        return f"QComboBox {{ border: 2px solid #e1e4e8; border-radius: 6px; padding: 6px 10px; padding-right: 30px; background-color: white; font-size: 12px; color: #2c3e50; }} QComboBox:focus {{ border: 2px solid #2c3e50; }} QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none; border-left: 1px solid #e1e4e8; }} QComboBox::down-arrow {{ image: url({svg}); width: 16px; height: 16px; }}"
    
    def _update_item_icon(self, item, is_selected):
        """
        Ajoute ou retire une coche VERTE à l'extrême droite d'un QListWidgetItem
        VERSION CORRIGÉE - Utilise les données stockées
        """
        data = item.data(Qt.UserRole)

        # ✅ Pour les items avec données complètes (enfants)
        if data and isinstance(data, dict) and 'original_name' in data:
            original_name = data.get('original_name', '')
            prefix = data.get('prefix', '•')

            if is_selected:
                # Afficher avec checkmark vert
                item.setText(f"{prefix} {original_name}        ✔")
                item.setForeground(QColor("#27ae60"))  # VERT
                item.setBackground(QColor("#e8f5e9"))  # Fond vert léger
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                # Afficher sans checkmark
                item.setText(f"{prefix} {original_name}")
                item.setForeground(QColor("#2c3e50"))
                item.setBackground(QColor("#ffffff"))
                font = item.font()
                font.setBold(False)
                item.setFont(font)

        # ✅ Pour les items simples (autres niveaux : typologie, taxonomy, etc.)
        else:
            original_text = item.text()

            # Nettoyer toutes les anciennes marques possibles
            clean_text = (original_text
                          .replace("✔ ", "")
                          .replace(" ✔", "")
                          .replace("✓ ", "")
                          .replace(" ✓", "")
                          .rstrip())

            has_arrow = "▶" in clean_text
            if has_arrow:
                clean_text = clean_text.replace("▶ ", "").strip()

            if is_selected:
                display_text = f"▶ {clean_text}" if has_arrow else clean_text
                item.setText(f"{display_text}        ✔")
                item.setForeground(QColor("#27ae60"))
                item.setBackground(QColor("#e8f5e9"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                display_text = f"▶ {clean_text}" if has_arrow else clean_text
                item.setText(display_text)
                item.setForeground(QColor("#2c3e50"))
                item.setBackground(QColor("#ffffff"))
                font = item.font()
                font.setBold(False)
                item.setFont(font)

    def _create_mini_button(self, text, callback):
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); color: white; border: none; border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 10px; min-height: 24px; }} QPushButton:hover:enabled {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); }} QPushButton:disabled {{ background: #d0d0d0; color: #808080; }}")
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _create_action_button(self, text, callback):
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); color: white; border: none; border-radius: 6px; padding: 10px 25px; font-weight: 600; font-size: 12px; min-width: 140px; }} QPushButton:hover:enabled {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); }} QPushButton:disabled {{ background: #c0c0c0; color: #707070; }}")
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _get_primary_button_style(self):
        return f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); color: white; border: none; border-radius: 6px; padding: 12px 30px; font-weight: 700; font-size: 13px; min-width: 180px; }} QPushButton:hover:enabled {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); }} QPushButton:disabled {{ background: #bdc3c7; color: #7f8c8d; }}"

    def _get_dropdown_svg_path(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(current_dir)), "resources", "icons", "dropdown.svg"))

    # ========== PUBLIC ==========

    def refresh_data(self):
        logger.info("Rafraîchissement des données")
        if self.project_manager and self.project_combo.currentIndex() > 0:
            self.project_manager.load_project(self.project_combo.currentText())
        self._refresh_typologies_cache()
        self._load_projects()
        self._load_master_typologies()
        self._load_context_typologies()
        self.selected_master_typologie = None
        self.master_combo.setCurrentIndex(0)
        self.master_stats.clear()

    def update_combinations(self, project_data):
        if project_data and self.project_manager:
            self.project_manager.current_project_data = project_data
        self.refresh_data()

    def update_relation(self, project_data):
        self.update_combinations(project_data)

    def get_combinations(self):
        return {
            'batch_name': self.batch_name_edit.text().strip(),
            'combinations': self.combinations,
            'count': len(self.combinations)
        }