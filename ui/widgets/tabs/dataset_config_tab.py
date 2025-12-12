#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import traceback
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal

from ui.localization.translator import tr
from ui.styles.theme import Theme
from utils.hierarchy_cache import HierarchyCache
from PyQt5.QtWidgets import QScrollArea


from utils.logger import logger


class DatasetConfigTab(QtWidgets.QWidget):
    """Configuration tab for dataset projects with infinite child hierarchy"""
    
    project_saved = pyqtSignal()
    preview_updated = pyqtSignal(dict)

    def __init__(self, project_manager, config_data, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data

        # Cache hiérarchique unifié
        self.hierarchy_cache = HierarchyCache()

        # État de navigation pour les enfants (au-delà du parent)
        self._child_navigation_path: list = []

        self._init_ui()
        self._load_initial_data()

    def _get_full_path(self) -> list:
        """
        Construire le chemin complet actuel - VERSION CORRIGÉE AVEC EXTRACTION DES COMPTEURS
        [typologie, cluster, root, parent, child1, child2, ...]
        """
        path = []

        typ_item = self.typologie_list.currentItem()
        if typ_item:
            # Extraire le nom sans compteur
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
            path.append(typ_name)
        else:
            logger.debug("Pas de typologie sélectionnée")
            return path

        if hasattr(self, 'taxonomy_list'):
            tax_item = self.taxonomy_list.currentItem()
            if tax_item:
                # Extraire le nom sans compteur
                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display
                path.append(tax_name)
            else:
                logger.debug("Pas de taxonomy sélectionnée")
                return path

        root_item = self.root_list.currentItem()
        if root_item:
            # Extraire le nom sans compteur
            root_display = root_item.text()
            root_name = root_display.split(" (")[0] if " (" in root_display else root_display
            path.append(root_name)
        else:
            logger.debug("Pas de root sélectionné")
            return path

        parent_item = self.parent_list.currentItem()
        if parent_item:
            parent_display = parent_item.text()
            # Extraire le nom sans compteur
            if " (" in parent_display:
                parent_name = parent_display.split(" (")[0]
            else:
                parent_name = parent_display
            path.append(parent_name)
        else:
            logger.debug("Pas de parent sélectionné")
            return path

        # Ajouter le chemin de navigation dans les enfants (déjà sans compteurs)
        path.extend(self._child_navigation_path)

        logger.debug(f"Chemin complet construit: {' > '.join(path)}")
        return path

    
    def _get_parent_path(self) -> list:
        """Chemin jusqu'au parent (excluant la navigation enfants)"""
        path = self._get_full_path()
        if len(path) > 4:
            return path[:4]
        return path
    
    def _sync_list_to_cache(self, list_widget: QtWidgets.QListWidget, 
                    parent_path: list):
        """Synchroniser une liste UI vers le cache - VERSION CORRIGÉE AVEC EXTRACTION DES COMPTEURS"""
        if not parent_path:
            logger.warning("Chemin parent vide pour sync")
            return

        items = []
        for i in range(list_widget.count()):
            item_display = list_widget.item(i).text()
            # CORRECTION: Extraire le nom sans compteur
            if " (" in item_display:
                item_name = item_display.split(" (")[0]
            else:
                item_name = item_display
            items.append(item_name)

        # Obtenir les enfants actuels du cache
        cached = self.hierarchy_cache.get_children_at_path(parent_path)

        # Ajouter les nouveaux
        for item in items:
            if item not in cached:
                self.hierarchy_cache.add_child_at_path(parent_path, item)

        logger.debug(f"Synced {len(items)} items to cache at {' > '.join(parent_path)}")


    def _load_list_from_cache(self, list_widget: QtWidgets.QListWidget,
                           parent_path: list):
        """Charger une liste UI depuis le cache avec comptage des enfants"""
        list_widget.clear()
        children = self.hierarchy_cache.get_children_at_path(parent_path)

        level = len(parent_path)

        for name in children:
            child_path = parent_path + [name]

            child_count = len(self.hierarchy_cache.get_children_at_path(child_path))

            if child_count > 0:
                display_name = f"{name} ({child_count})"
            else:
                display_name = name

            item = QtWidgets.QListWidgetItem(display_name)
            list_widget.addItem(item)

        logger.debug(f"Chargé {len(children)} éléments pour {' > '.join(parent_path) if parent_path else 'racine'}")

    def _refresh_parent_counts(self):
        """Rafraîchir les compteurs d'enfants pour tous les parents visibles - REMPLACÉ PAR _refresh_all_counts"""
        self._refresh_all_counts()

    def _get_current_cache_path(self):
        """
        Obtenir le chemin de cache actuel basé sur les sélections
        Retourne un tuple (typologie, taxonomy, root, parent) ou None
        """
        typologie_item = self.typologie_list.currentItem()
        if not typologie_item:
            return None
        
        typologie_name = typologie_item.text()
        
        taxonomy_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None
        if not taxonomy_item:
            return (typologie_name, None, None, None)
        
        taxonomy_name = taxonomy_item.text()
        
        root_item = self.root_list.currentItem()
        if not root_item:
            return (typologie_name, taxonomy_name, None, None)
        
        root_name = root_item.text()
        
        parent_item = self.parent_list.currentItem()
        if not parent_item:
            return (typologie_name, taxonomy_name, root_name, None)
        
        parent_name = parent_item.text()

        return (typologie_name, taxonomy_name, root_name, parent_name)

    def _load_children_from_cache(self):
        logger.debug("=" * 60)
        logger.debug("DÉBUT _load_children_from_cache")
        logger.debug("=" * 60)

        # Vider la liste
        logger.debug(f"Nombre d'items avant clear: {self.child_list.count()}")
        self.child_list.clear()
        logger.debug(f"Nombre d'items après clear: {self.child_list.count()}")

        # Construire le chemin
        path = self._get_full_path()

        logger.debug(f"Chemin complet obtenu: {path}")
        logger.debug(f"Longueur du chemin: {len(path)}")
        logger.debug(f"Navigation enfants actuelle: {self._child_navigation_path}")

        # Vérifier validité du chemin
        if len(path) < 4:
            logger.warning(f"⚠️ Chemin incomplet (longueur {len(path)}): {path}")
            logger.debug("Détails des sélections:")
            logger.debug(f"  - Typologie: {self.typologie_list.currentItem().text() if self.typologie_list.currentItem() else 'None'}")
            logger.debug(f"  - Taxonomy: {self.taxonomy_list.currentItem().text() if self.taxonomy_list.currentItem() else 'None'}")
            logger.debug(f"  - Root: {self.root_list.currentItem().text() if self.root_list.currentItem() else 'None'}")
            logger.debug(f"  - Parent: {self.parent_list.currentItem().text() if self.parent_list.currentItem() else 'None'}")
            return

        logger.debug(f"✓ Chemin valide: {' > '.join(path)}")

        # Récupérer les enfants du cache
        logger.debug(f"Appel hierarchy_cache.get_children_at_path({path})")
        children = self.hierarchy_cache.get_children_at_path(path)

        logger.debug(f"✓ Enfants trouvés dans le cache: {children}")
        logger.debug(f"✓ Nombre d'enfants: {len(children)}")

        # Ajouter chaque enfant à la liste UI
        for idx, name in enumerate(children):
            logger.debug(f"  Traitement enfant {idx + 1}/{len(children)}: '{name}'")

            # Compter les sous-enfants
            child_path = path + [name]
            logger.debug(f"    Chemin enfant: {' > '.join(child_path)}")

            subchildren = self.hierarchy_cache.get_children_at_path(child_path)
            subchild_count = len(subchildren)
            logger.debug(f"    Sous-enfants: {subchild_count} ({subchildren})")

            # Créer le nom d'affichage
            if subchild_count > 0:
                display_name = f"{name} ({subchild_count})"
            else:
                display_name = name

            logger.debug(f"    Nom d'affichage: '{display_name}'")

            # Ajouter à la liste UI
            item = QtWidgets.QListWidgetItem(display_name)
            self.child_list.addItem(item)
            logger.debug(f"    ✓ Ajouté à child_list")

        # Vérification finale
        final_count = self.child_list.count()
        logger.debug(f"✓ Total d'items dans child_list: {final_count}")

        if final_count != len(children):
            logger.error(f"⚠️ INCOHÉRENCE: {len(children)} dans cache mais {final_count} dans UI!")

        depth = len(self._child_navigation_path)
        logger.debug(f"Profondeur actuelle: {depth}")
        logger.debug("=" * 60)
        logger.debug("FIN _load_children_from_cache")
        logger.debug("=" * 60)

    def _refresh_all_counts(self):
        """Rafraîchir tous les compteurs d'enfants dans toutes les listes"""
        # Rafraîchir la liste des typologies
        self._load_list_from_cache(self.typologie_list, [])
        
        # Rafraîchir taxonomy si une typologie est sélectionnée
        typ_item = self.typologie_list.currentItem()
        if typ_item:
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
            self._load_list_from_cache(self.taxonomy_list, [typ_name])
            
            # Rafraîchir root si un taxonomy est sélectionné
            tax_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None
            if tax_item:
                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display
                self._load_list_from_cache(self.root_list, [typ_name, tax_name])
                
                # Rafraîchir parent si un root est sélectionné
                root_item = self.root_list.currentItem()
                if root_item:
                    root_display = root_item.text()
                    root_name = root_display.split(" (")[0] if " (" in root_display else root_display
                    self._load_list_from_cache(self.parent_list, [typ_name, tax_name, root_name])

    def _get_or_create_cache_structure(self, typologie_name, taxonomy_name=None, 
                                       root_name=None, parent_name=None):
        """
        Obtenir ou créer la structure de cache pour un chemin donné
        Retourne le nœud du cache correspondant au niveau demandé
        """
        if typologie_name not in self.temp_hierarchy_cache:
            self.temp_hierarchy_cache[typologie_name] = {}
        
        if taxonomy_name is None:
            return self.temp_hierarchy_cache[typologie_name]
        
        if taxonomy_name not in self.temp_hierarchy_cache[typologie_name]:
            self.temp_hierarchy_cache[typologie_name][taxonomy_name] = {}
        
        if root_name is None:
            return self.temp_hierarchy_cache[typologie_name][taxonomy_name]
        
        if root_name not in self.temp_hierarchy_cache[typologie_name][taxonomy_name]:
            self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name] = {}
        
        if parent_name is None:
            return self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name]
        
        if parent_name not in self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name]:
            # Initialiser avec une structure pour les enfants récursifs
            self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name][parent_name] = {
                '_children': [],  # Liste des enfants directs
                '_sublevels': {}   # Dictionnaire récursif pour les sous-niveaux
            }
        
        return self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name][parent_name]

    def _init_ui(self):
        """Create configuration tab with responsive design"""
        # Container principal avec scroll
        main_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(main_container)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(10)

        left_layout = self._create_left_column()
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        # Largeur confortable pour la colonne gauche
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(350)
        left_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        columns_layout.addWidget(left_widget, 3)

        right_layout = self._create_right_column()
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setMinimumWidth(350)  # Réduit de 400 à 350
        right_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        columns_layout.addWidget(right_widget, 7)

        layout.addLayout(columns_layout)
        self._create_action_buttons(layout)

        # Envelopper dans un QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(main_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        final_layout = QtWidgets.QVBoxLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll)

    def _create_left_column(self):
        """Create left column (project selection and details) - responsive"""
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(10)

        project_group = self._create_modern_group(tr("dataset.select_project"))
        project_layout = QtWidgets.QVBoxLayout(project_group)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.setMinimumHeight(32)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_layout.addWidget(self.project_combo)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(4)

        self.add_project_btn = self._create_compact_button(tr("dataset.new_project"), self._add_project)
        self.delete_project_btn = self._create_compact_button(tr("dataset.delete_project"), self._delete_project)

        self.add_project_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(False)

        btn_layout.addWidget(self.add_project_btn)
        btn_layout.addWidget(self.delete_project_btn)
        btn_layout.addStretch()
        project_layout.addLayout(btn_layout)

        left_layout.addWidget(project_group)

        details_group = self._create_modern_group(tr("dataset.project_details"))
        details_group.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        details_layout = QtWidgets.QFormLayout(details_group)
        details_layout.setSpacing(8)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(tr("dataset.project_name_placeholder"))
        self.project_name_edit.setStyleSheet(self._get_modern_input_style())
        self.project_name_edit.setMinimumHeight(32)
        details_layout.addRow(tr("dataset.project_name"), self.project_name_edit)

        typologie_section = self._create_typologie_section()
        details_layout.addRow(typologie_section)

        left_layout.addWidget(details_group)

        return left_layout

    def _create_typologie_section(self):
        """Create typologies section - responsive with grid buttons"""
        container = QtWidgets.QWidget()
        container.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QtWidgets.QLabel(tr("dataset.typologies"))
        title.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 12px;")
        layout.addWidget(title)

        self.typologie_list = QtWidgets.QListWidget()
        self.typologie_list.setStyleSheet(self._get_modern_list_style())
        self.typologie_list.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.typologie_list.setMinimumHeight(80)
        self.typologie_list.currentItemChanged.connect(self._on_typologie_selected)
        layout.addWidget(self.typologie_list)

        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QGridLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(3)

        self.add_typologie_btn = self._create_compact_button(tr("dataset.add"), self._add_typologie)
        self.edit_typologie_btn = self._create_compact_button(tr("dataset.edit"), self._edit_typologie)
        self.remove_typologie_btn = self._create_compact_button(tr("dataset.delete"), self._remove_typologie)

        self.add_typologie_btn.setEnabled(False)
        self.edit_typologie_btn.setEnabled(False)
        self.remove_typologie_btn.setEnabled(False)

        # Disposition en grille 2x2
        btn_layout.addWidget(self.add_typologie_btn, 0, 0)
        btn_layout.addWidget(self.edit_typologie_btn, 0, 1)
        btn_layout.addWidget(self.remove_typologie_btn, 1, 0, 1, 2)  # S'étend sur 2 colonnes

        layout.addWidget(btn_container)

        return container
    
    def _load_initial_data(self):
        """Charge les données initiales"""
        try:
            self._refresh_project_combos()
            
            if self.project_manager.current_project_name:
                index = self.project_combo.findText(self.project_manager.current_project_name)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                    self._load_project_ui()
            
            logger.info(f"Projets chargés: {self.project_combo.count()} projet(s) trouvé(s)")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement initial des données: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self, 
                "Erreur de chargement", 
                f"Impossible de charger les projets: {str(e)}"
            )

    def resizeEvent(self, event):
        """Handle resize to switch between horizontal and vertical layouts"""
        super().resizeEvent(event)
        width = self.width()
        pass

    def _create_right_column(self):
        """Create right column (hierarchy in 2x2 grid) - responsive"""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        taxonomy_widget = self._create_label_section('taxonomy', tr("dataset.taxonomy_clusters"))
        grid.addWidget(taxonomy_widget, 0, 0)

        root_widget = self._create_label_section('root', tr("dataset.root_labels"))
        grid.addWidget(root_widget, 0, 1)

        parent_widget = self._create_label_section('parent', tr("dataset.parent_labels"))
        grid.addWidget(parent_widget, 1, 0)

        child_widget = self._create_dynamic_child_section()
        grid.addWidget(child_widget, 1, 1)

        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        layout.addLayout(grid)

        return layout

    def _create_label_section(self, level, title):
        """Create a label section with list and CRUD buttons - responsive single line"""
        group = self._create_modern_group(title)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_modern_list_style())
        list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        list_widget.setMinimumHeight(100)
        layout.addWidget(list_widget)

        if level == 'taxonomy':
            self.taxonomy_list = list_widget
            list_widget.currentItemChanged.connect(self._on_taxonomy_selected)
        elif level == 'root':
            self.root_list = list_widget
            list_widget.currentItemChanged.connect(self._on_root_selected)
        elif level == 'parent':
            self.parent_list = list_widget
            list_widget.currentItemChanged.connect(self._on_parent_selected)

        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        add_btn = self._create_compact_button(tr("dataset.add"), lambda: self._add_label(level))
        edit_btn = self._create_compact_button(tr("dataset.edit"), lambda: self._edit_label(level))
        delete_btn = self._create_compact_button(tr("dataset.delete"), lambda: self._remove_label(level))
        category_btn = self._create_compact_button(tr("dataset.category"), lambda: self._modify_category(level))

        setattr(self, f'add_{level}_btn', add_btn)
        setattr(self, f'edit_{level}_btn', edit_btn)
        setattr(self, f'remove_{level}_btn', delete_btn)
        setattr(self, f'category_{level}_btn', category_btn)

        add_btn.setEnabled(False)
        edit_btn.setEnabled(False)
        delete_btn.setEnabled(False)
        category_btn.setEnabled(False)

        # Tous les boutons ont le même poids pour se partager l'espace
        btn_layout.addWidget(add_btn, 1)
        btn_layout.addWidget(edit_btn, 1)
        btn_layout.addWidget(delete_btn, 1)
        btn_layout.addWidget(category_btn, 1)

        layout.addWidget(btn_container)

        return group

    def _create_dynamic_child_section(self):
        """Create dynamic child section with breadcrumb navigation - responsive single line"""
        group = self._create_modern_group(tr("dataset.child_labels"))
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        breadcrumb_container = QtWidgets.QWidget()
        breadcrumb_layout = QtWidgets.QHBoxLayout(breadcrumb_container)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        breadcrumb_layout.setSpacing(3)

        self.breadcrumb_label = QtWidgets.QLabel(tr("dataset.root"))
        self.breadcrumb_label.setStyleSheet("""
            color: #7f8c8d;
            font-size: 10px;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 3px 6px;
            background-color: #f8f9fa;
            border-radius: 3px;
        """)
        self.breadcrumb_label.setWordWrap(True)
        self.breadcrumb_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        breadcrumb_layout.addWidget(self.breadcrumb_label, 3)

        self.up_btn = self._create_compact_button(tr("dataset.up"), self._navigate_up)
        self.up_btn.setEnabled(False)
        breadcrumb_layout.addWidget(self.up_btn, 1)

        self.dive_btn = self._create_compact_button(tr("dataset.dive"), self._navigate_into_child)
        self.dive_btn.setEnabled(False)
        breadcrumb_layout.addWidget(self.dive_btn, 1)

        layout.addWidget(breadcrumb_container)

        self.child_list = QtWidgets.QListWidget()
        self.child_list.setStyleSheet(self._get_modern_list_style())
        self.child_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.child_list.setMinimumHeight(100)
        self.child_list.currentItemChanged.connect(self._on_child_selected)
        self.child_list.itemDoubleClicked.connect(self._navigate_into_child)
        layout.addWidget(self.child_list)

        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        self.add_child_btn = self._create_compact_button(tr("dataset.add"), self._add_child)
        self.edit_child_btn = self._create_compact_button(tr("dataset.edit"), self._edit_child)
        self.remove_child_btn = self._create_compact_button(tr("dataset.delete"), self._remove_child)
        self.category_child_btn = self._create_compact_button(tr("dataset.category"), lambda: self._modify_category('child'))

        self.add_child_btn.setEnabled(False)
        self.edit_child_btn.setEnabled(False)
        self.remove_child_btn.setEnabled(False)
        self.category_child_btn.setEnabled(False)

        # Tous les boutons ont le même poids
        btn_layout.addWidget(self.add_child_btn, 1)
        btn_layout.addWidget(self.edit_child_btn, 1)
        btn_layout.addWidget(self.remove_child_btn, 1)
        btn_layout.addWidget(self.category_child_btn, 1)

        layout.addWidget(btn_container)

        return group

    def _create_modern_group(self, title):
        """Create modern styled group box - responsive"""
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: white;
                color: {Theme.SECONDARY_COLOR};
            }}
        """)
        return group

    def _create_compact_button(self, text, callback):
        """Create compact gradient button - fully responsive"""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 3px;
                padding: 3px 4px;
                font-weight: 600;
                font-size: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-height: 22px;
                min-width: 40px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, 
                    stop:1 {Theme.PRIMARY_COLOR});
                color: white;
            }}
            QPushButton:pressed {{
                background: #1f5f8b;
                color: white;
            }}
            QPushButton:disabled {{
                background: #d0d0d0;
                color: #2c3e50;
            }}
        """)
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return btn

    def _get_modern_input_style(self):
        """Modern input field style with correct dropdown icon - responsive"""
        svg_path = self._get_dropdown_svg_path()
        svg_path = svg_path.replace('\\', '/')

        return f"""
            QLineEdit, QComboBox {{
                border: 2px solid #e1e4e8;
                border-radius: 5px;
                padding: 6px 10px;
                background-color: white;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid #2c3e50;
            }}
            QComboBox {{
                min-height: 30px;
                padding-left: 10px;
                padding-right: 30px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 28px;
                border: none;
                border-left: 1px solid #e1e4e8;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background: linear-gradient(to bottom, #fafafa, #f5f5f5);
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 16px;
                height: 16px;
            }}
        """
    
    def _get_dropdown_svg_path(self):
        """Get absolute path to dropdown SVG icon"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        widgets_dir = os.path.dirname(current_dir)
        ui_dir = os.path.dirname(widgets_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        svg_path = os.path.normpath(svg_path)
        return svg_path

    def _get_modern_list_style(self):
        """Modern list widget style - responsive"""
        return """
            QListWidget {
                border: 2px solid #e1e4e8;
                border-radius: 5px;
                background-color: white;
                padding: 4px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 1px 0;
                color: #2c3e50;
            }
            QListWidget::item:selected {
                background-color: #e8e8e8;
                color: #2c3e50;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                color: #2c3e50;
            }
        """

    def _create_action_buttons(self, parent_layout):
        """Create main action buttons - responsive"""
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(8)

        btn_layout.addStretch()

        self.save_btn = QtWidgets.QPushButton(tr("dataset.save"))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 90px;
                min-height: 32px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, 
                    stop:1 {Theme.PRIMARY_COLOR});
                color: white;
            }}
            QPushButton:disabled {{
                background: #c0c0c0;
                color: #2c3e50;
            }}
        """)
        self.save_btn.clicked.connect(self._save_project)

        btn_layout.addWidget(self.save_btn)
        parent_layout.addWidget(btn_container)

    # ========== EVENT HANDLERS ==========

    def _on_project_selected(self, index):
        """
        Gestion de la sélection de projet - VERSION CORRIGÉE
        """
        if index < 0:
            return

        project_name = self.project_combo.currentText()

        try:
            # 1. Charger le projet depuis la DB
            if self.project_manager.load_project(project_name):

                # 2. Vider le cache et réinitialiser la navigation
                self.hierarchy_cache.clear()
                self._child_navigation_path.clear()

                # 3. Charger le projet dans le cache
                self._load_project_from_db_to_cache()

                # 4. Charger l'UI
                self._load_project_ui()

                # 5. Exporter la stratégie
                self._export_strategy()

                logger.info(f"Projet '{project_name}' chargé et affiché")
            else:
                QtWidgets.QMessageBox.warning(self, "Erreur",
                    f"Impossible de charger le projet '{project_name}'")

        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement des projets: {str(e)}\n{traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(self, "Erreur",
                f"Erreur lors du chargement: {e}")
        
    def _on_typologie_selected(self, current, previous):
        """
        Gestion de la sélection de typologie - VERSION CORRIGÉE
        """
        # Sauvegarder l'état précédent dans le cache (déjà fait en temps réel)

        if not current:
            self._clear_hierarchy()
            self._update_button_states()
            return

        # CORRECTION: Extraire le nom SANS le compteur
        typologie_display = current.text()
        if " (" in typologie_display:
            typologie_name = typologie_display.split(" (")[0]
        else:
            typologie_name = typologie_display

        index = self.typologie_list.currentRow()

        # Mettre à jour le project_manager
        self.project_manager.set_current_typologie_index(index)

        # Charger les clusters de taxonomie depuis le cache AVEC LE NOM SANS COMPTEUR
        path = [typologie_name]
        self._load_list_from_cache(self.taxonomy_list, path)

        # Effacer les niveaux inférieurs
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self._child_navigation_path.clear()

        self._update_button_states()
        logger.debug(f"Typologie sélectionnée: '{typologie_name}'")


    def _save_full_hierarchy_to_cache(self, typologie_name):
        """Sauvegarder toute la hiérarchie d'une typologie dans le cache"""
        if not typologie_name:
            return

        # Sauvegarder les clusters de taxonomie
        self._save_taxonomy_to_cache(typologie_name)

        # Sauvegarder tous les root labels de tous les clusters
        if hasattr(self, 'taxonomy_list'):
            for i in range(self.taxonomy_list.count()):
                taxonomy_item = self.taxonomy_list.item(i)
                taxonomy_name = taxonomy_item.text()
                self._save_root_to_cache(typologie_name, taxonomy_name)

        logger.debug(f"Hiérarchie complète sauvegardée pour typologie '{typologie_name}'")

    def _on_taxonomy_selected(self, current, previous):
        """
        Gestion de la sélection de taxonomie - VERSION COMPLÈTEMENT CORRIGÉE
        """
        if not current:
            self.root_list.clear()
            self.parent_list.clear()
            self.child_list.clear()
            self._update_button_states()
            return
    
        typ_item = self.typologie_list.currentItem()
        if not typ_item:
            logger.warning("Typologie non sélectionnée")
            return
    
        # CORRECTION CRITIQUE: Extraire les noms SANS les compteurs
        taxonomy_display = current.text()
        if " (" in taxonomy_display:
            taxonomy_name = taxonomy_display.split(" (")[0]
        else:
            taxonomy_name = taxonomy_display
    
        typologie_display = typ_item.text()
        if " (" in typologie_display:
            typologie_name = typologie_display.split(" (")[0]
        else:
            typologie_name = typologie_display
    
        logger.debug(f"Sélection taxonomy: '{taxonomy_name}' dans typologie '{typologie_name}'")
    
        # === PARTIE CRITIQUE: SYNCHRONISER LE PROJECT_MANAGER ===
    
        # 1. Trouver l'index du taxonomy dans le project_manager
        typologie = self.project_manager.get_current_typologie()
        if not typologie:
            logger.error(f"Typologie '{typologie_name}' non trouvée dans project_manager!")
            return
    
        taxonomy_clusters = typologie.get('taxonomy_clusters', [])
        taxonomy_index = -1
    
        for idx, cluster in enumerate(taxonomy_clusters):
            if cluster.get('name') == taxonomy_name:
                taxonomy_index = idx
                break
            
        if taxonomy_index == -1:
            # Le cluster n'existe pas encore dans le manager, le créer
            logger.warning(f"Taxonomy '{taxonomy_name}' pas dans manager, ajout automatique")
            new_cluster = {
                'name': taxonomy_name,
                'description': '',
                'root_labels': []
            }
            taxonomy_clusters.append(new_cluster)
            taxonomy_index = len(taxonomy_clusters) - 1
    
        # 2. Définir l'index dans le project_manager
        self.project_manager.current_taxonomy_index = taxonomy_index
    
        logger.info(f"✓ Taxonomy index synchronisé: {taxonomy_index} pour '{taxonomy_name}'")
    
        # Vérification: S'assurer que get_current_taxonomy() fonctionne
        current_tax = self.project_manager.get_current_taxonomy()
        if current_tax:
            logger.debug(f"✓ get_current_taxonomy() retourne: '{current_tax.get('name')}'")
        else:
            logger.error("✗ get_current_taxonomy() retourne None!")
            return
    
        # === FIN PARTIE CRITIQUE ===
    
        # Charger les roots depuis le cache AVEC LES NOMS SANS COMPTEURS
        path = [typologie_name, taxonomy_name]
        self._load_list_from_cache(self.root_list, path)
    
        # Effacer les niveaux inférieurs
        self.parent_list.clear()
        self.child_list.clear()
        self._child_navigation_path.clear()
    
        self._update_button_states()
        logger.debug(f"Taxonomie '{taxonomy_name}' sélectionnée et synchronisée")

    def _on_root_selected(self, current, previous):
        """
        Gestion de la sélection de root - VERSION CORRIGÉE
        """
        if not current:
            self.parent_list.clear()
            self.child_list.clear()
            self._update_button_states()
            return

        # CORRECTION: Extraire le nom SANS le compteur
        root_display = current.text()
        if " (" in root_display:
            root_name = root_display.split(" (")[0]
        else:
            root_name = root_display

        index = self.root_list.currentRow()

        # Mettre à jour le project_manager
        self.project_manager.set_current_root_index(index)

        # Construire le chemin AVEC LES NOMS SANS COMPTEURS
        typ_item = self.typologie_list.currentItem()
        tax_item = self.taxonomy_list.currentItem()

        if typ_item and tax_item:
            # Extraire les noms sans compteurs
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

            tax_display = tax_item.text()
            tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

            path = [typ_name, tax_name, root_name]
            self._load_list_from_cache(self.parent_list, path)

        # Effacer les enfants
        self.child_list.clear()
        self._child_navigation_path.clear()

        self._update_button_states()
        logger.debug(f"Root sélectionné: '{root_name}'")

    def _on_parent_selected(self, current, previous):
        """
        Gestion de la sélection de parent - VERSION CORRIGÉE avec extraction du nom réel
        """
        if not current:
            self.child_list.clear()
            self._update_button_states()
            return

        parent_display = current.text()
        # CORRECTION: Extraire le nom réel sans le compteur
        if " (" in parent_display:
            parent_name = parent_display.split(" (")[0]
        else:
            parent_name = parent_display

        index = self.parent_list.currentRow()

        # Mettre à jour le project_manager avec le NOM RÉEL
        self.project_manager.set_current_parent_index(index)

        # Réinitialiser la navigation enfants
        self._child_navigation_path.clear()

        # Charger les enfants directs depuis le cache
        self._load_children_from_cache()

        # Mettre à jour le breadcrumb
        self._update_breadcrumb()

        self._update_button_states()
        logger.debug(f"Parent sélectionné: '{parent_name}' (affiché: '{parent_display}')")

    def _on_child_selected(self, current, previous):
        """Handle child selection - VERSION CORRIGÉE"""
        # Mettre à jour les boutons quand la sélection change
        self._update_button_states()
    
        # Activer le bouton "Plonger" si un enfant est sélectionné
        has_selection = current is not None
        self.dive_btn.setEnabled(has_selection)
        
        if has_selection:
            child_display = current.text()
            # Extraire le nom sans compteur
            if " (" in child_display:
                child_name = child_display.split(" (")[0]
            else:
                child_name = child_display
            logger.debug(f"Enfant sélectionné: '{child_name}'")
    
    def _navigate_into_child(self):
        """Navigation dans un enfant - VERSION CORRIGÉE avec extraction du nom"""
        current_item = self.child_list.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(self, "Sélection requise",
                "Veuillez sélectionner un enfant pour naviguer dedans")
            return

        child_display = current_item.text()

        # CORRECTION: Extraire le nom réel sans le compteur
        if " (" in child_display:
            child_name = child_display.split(" (")[0]
        else:
            child_name = child_display

        current_path = self._get_full_path()
        self._sync_list_to_cache(self.child_list, current_path)

        self._child_navigation_path.append(child_name)

        self.project_manager.navigate_into_child(child_name)

        self._load_children_from_cache()

        # Mettre à jour l'affichage
        self._update_breadcrumb()
        self._update_button_states()

        depth = len(self._child_navigation_path)
        logger.debug(f"Navigation dans '{child_name}': niveau {depth}")


    def _navigate_up(self):
        """
        Remonte d'un niveau - VERSION CORRIGÉE
        Synchronise avec le project_manager
        """
        if not self._child_navigation_path:
            logger.warning("Impossible de remonter: chemin vide")
            return

        # Sauvegarder l'état actuel
        current_path = self._get_full_path()
        self._sync_list_to_cache(self.child_list, current_path)

        # Remonter d'un niveau
        removed_child = self._child_navigation_path.pop()

        # Synchroniser avec le project_manager
        self.project_manager.navigate_up()

        # Recharger les enfants du niveau parent
        self._load_children_from_cache()

        # Mettre à jour l'affichage
        self._update_breadcrumb()
        self._update_button_states()

        depth = len(self._child_navigation_path)
        logger.debug(f"Remonté depuis '{removed_child}': niveau {depth}")

    def _update_breadcrumb(self):
        """Mettre à jour le fil d'Ariane - VERSION CORRIGÉE"""
        depth = len(self._child_navigation_path)

        if depth == 0:
            # Afficher le parent SANS le compteur
            parent_item = self.parent_list.currentItem()
            if parent_item:
                parent_display = parent_item.text()
                # Extraire le nom sans compteur
                if " (" in parent_display:
                    parent_name = parent_display.split(" (")[0]
                else:
                    parent_name = parent_display
                display = f"{parent_name}"
            else:
                display = "Racine"
        else:
            # Afficher le chemin dans les enfants (déjà sans compteurs)
            if depth <= 2:
                display = " → ".join(self._child_navigation_path)
            else:
                display = "... → " + " → ".join(self._child_navigation_path[-2:])

            display = f"{display} (Niveau {depth})"

        self.breadcrumb_label.setText(display)

        # Activer/désactiver les boutons de navigation
        self.up_btn.setEnabled(depth > 0)

        # Le bouton "Plonger" est activé s'il y a un enfant sélectionné
        child_selected = self.child_list.currentItem() is not None
        self.dive_btn.setEnabled(child_selected)

    # ========== CRUD ACTIONS ==========

    def _add_project(self):
        """Add new project"""
        name, ok = QtWidgets.QInputDialog.getText(self, tr("dataset.new_project"), tr("dataset.project_name") + ":")
        if not ok or not name.strip():
            return
        description, ok = QtWidgets.QInputDialog.getMultiLineText(self, tr("dataset.description"), tr("dataset.description") + " (optional):")
        if not ok:
            description = ""
        if self.project_manager.create_new_project(name.strip(), description.strip()):
            self._refresh_project_combos()
            self.project_combo.setCurrentText(name.strip())
            self._load_project_ui()
            logger.info(f"Project '{name}' created")
        else:
            QtWidgets.QMessageBox.warning(self, tr("dataset.error"), f"{tr('dataset.project_exists')}: '{name}'")

    def _delete_project(self):
        """Delete current project"""
        project_name = self.project_manager.current_project_name
        if not project_name:
            return
        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"), f"{tr('dataset.delete_project_confirm')}: '{project_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            if self.project_manager.delete_project(project_name):
                self._clear_ui()
                self._refresh_project_combos()
                logger.info(f"Project '{project_name}' deleted")

    def _save_project(self):
        """Sauvegarde le projet - VERSION COMPLÈTE AVEC DIAGNOSTIC"""
        logger.info("=" * 100)
        logger.info("🚀 DÉBUT DU PROCESSUS DE SAUVEGARDE")
        logger.info("=" * 100)
    
        # POINT 1: État Initial
        logger.info("\n📋 DIAGNOSTIC POINT 1: État Initial")
        logger.info(f"  project_manager.current_project_name: '{self.project_manager.current_project_name}'")
        logger.info(f"  project_manager.current_project_data existe: {self.project_manager.current_project_data is not None}")
        logger.info(f"  project_combo.currentText(): '{self.project_combo.currentText()}'")
        logger.info(f"  project_name_edit.text(): '{self.project_name_edit.text()}'")
    
        # POINT 2: Récupération du nom
        logger.info("\n📋 DIAGNOSTIC POINT 2: Récupération du nom")
        project_name = self.project_manager.current_project_name
        logger.info(f"  current_project_name: '{project_name}'")
    
        if not project_name:
            combo_text = self.project_combo.currentText()
            if combo_text:
                if self.project_manager.load_project(combo_text):
                    project_name = combo_text
                    logger.info(f"  ✅ Chargé depuis combo: '{project_name}'")
    
        if not project_name:
            new_name = self.project_name_edit.text().strip()
            if new_name:
                if self.project_manager.create_new_project(new_name, ""):
                    project_name = new_name
                    logger.info(f"  ✅ Nouveau projet créé: '{project_name}'")
    
        # POINT 3: Validation
        logger.info("\n📋 DIAGNOSTIC POINT 3: Validation")
        if not self.project_manager.current_project_name:
            logger.error("❌ BLOCAGE: current_project_name est None")
            QtWidgets.QMessageBox.critical(self, "Erreur", "Projet sans nom valide")
            return
    
        if not self.project_manager.current_project_data:
            logger.error("❌ BLOCAGE: current_project_data est None")
            QtWidgets.QMessageBox.critical(self, "Erreur", "Données non initialisées")
            return
    
        new_name = self.project_name_edit.text().strip()
        if not new_name:
            logger.error("❌ BLOCAGE: project_name_edit vide")
            QtWidgets.QMessageBox.warning(self, "Erreur", "Nom manquant")
            return
    
        logger.info(f"✅ Validations OK - Projet: '{new_name}'")
    
        # POINT 4: Contenu du cache
        logger.info("\n📋 DIAGNOSTIC POINT 4: Cache")
        typologies_cache = self.hierarchy_cache.get_typologies()
        logger.info(f"  {len(typologies_cache)} typologie(s) dans cache")
    
        # POINT 5: Synchronisation
        logger.info("\n📋 DIAGNOSTIC POINT 5: Synchronisation")
        try:
            sync_success = self._sync_cache_to_project_manager()
            logger.info(f"  sync result: {sync_success}")
            if not sync_success:
                logger.error("❌ BLOCAGE: Sync failed")
                QtWidgets.QMessageBox.critical(self, "Erreur", "Sync échouée")
                return
        except Exception as e:
            logger.error(f"❌ EXCEPTION SYNC: {e}")
            QtWidgets.QMessageBox.critical(self, "Exception", str(e))
            return
    
        logger.info("✅ Sync OK")
    
        # POINT 6: Project Manager Content
        logger.info("\n📋 DIAGNOSTIC POINT 6: Project Manager")
        typologies_manager = self.project_manager.current_project_data.get('typologies', [])
        logger.info(f"  {len(typologies_manager)} typologie(s) dans manager")
    
        # POINT 7: Nom
        logger.info("\n📋 DIAGNOSTIC POINT 7: Mise à jour nom")
        old_name = self.project_manager.current_project_name
        self.project_manager.current_project_data['nom'] = new_name
        self.project_manager.current_project_name = new_name
        logger.info(f"  '{old_name}' → '{new_name}'")
    
        # POINT 8: Save Project
        logger.info("\n📋 DIAGNOSTIC POINT 8: Appel save_project()")
        try:
            save_success = self.project_manager.save_project()
            logger.info(f"  save_project() result: {save_success}")
            
            if not save_success:
                logger.error("❌ BLOCAGE: save_project() = False")
                QtWidgets.QMessageBox.critical(self, "Échec", "save_project() a échoué")
                return
        except Exception as e:
            logger.error(f"❌ EXCEPTION SAVE: {e}")
            logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Exception", str(e))
            return
    
        logger.info("✅ save_project() OK")
    
        # ================================================================
        # POINT 9: VÉRIFICATION EN BASE - SECTION CRITIQUE
        # ================================================================
        logger.info("\n" + "=" * 100)
        logger.info("📋 DIAGNOSTIC POINT 9: VÉRIFICATION BASE DE DONNÉES")
        logger.info("=" * 100)
    
        try:
            db = self.project_manager.database
            
            if not db.connection:
                logger.error("❌ CRITIQUE: Pas de connexion DB!")
                QtWidgets.QMessageBox.critical(self, "Erreur", "Pas de connexion DB")
                return
            
            logger.info(f"DB path: {db.db_path}")
            cursor = db.connection.cursor()
            
            # Recherche du projet
            logger.info(f"\n🔍 Recherche projet '{new_name}'...")
            cursor.execute("SELECT * FROM projects WHERE name = ?", (new_name,))
            project_row = cursor.fetchone()
            
            if project_row:
                logger.info("✅ PROJET TROUVÉ EN BASE!")
                logger.info(f"   ID: {project_row['id']}")
                logger.info(f"   Nom: {project_row['name']}")
                
                project_id = project_row['id']
                
                # Compter les éléments
                cursor.execute("SELECT COUNT(*) as c FROM typologies WHERE project_id = ?", (project_id,))
                typ_count = cursor.fetchone()['c']
                
                cursor.execute("""
                    SELECT COUNT(*) as c FROM taxonomy_clusters 
                    WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                """, (project_id,))
                cluster_count = cursor.fetchone()['c']
                
                cursor.execute("""
                    SELECT COUNT(*) as c FROM root_labels 
                    WHERE taxonomy_id IN (
                        SELECT id FROM taxonomy_clusters 
                        WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                    )
                """, (project_id,))
                root_count = cursor.fetchone()['c']
                
                cursor.execute("""
                    SELECT COUNT(*) as c FROM parent_labels 
                    WHERE root_id IN (
                        SELECT id FROM root_labels 
                        WHERE taxonomy_id IN (
                            SELECT id FROM taxonomy_clusters 
                            WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                        )
                    )
                """, (project_id,))
                parent_count = cursor.fetchone()['c']
                
                cursor.execute("""
                    SELECT COUNT(*) as c FROM child_labels 
                    WHERE parent_label_id IN (
                        SELECT id FROM parent_labels 
                        WHERE root_id IN (
                            SELECT id FROM root_labels 
                            WHERE taxonomy_id IN (
                                SELECT id FROM taxonomy_clusters 
                                WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                            )
                        )
                    )
                """, (project_id,))
                child_count = cursor.fetchone()['c']
                
                logger.info(f"\n📊 Contenu:")
                logger.info(f"   - {typ_count} typologie(s)")
                logger.info(f"   - {cluster_count} cluster(s)")
                logger.info(f"   - {root_count} root(s)")
                logger.info(f"   - {parent_count} parent(s)")
                logger.info(f"   - {child_count} enfant(s)")
                
                total = typ_count + cluster_count + root_count + parent_count + child_count
                logger.info(f"\n🎯 TOTAL: {total} enregistrements")
                
                if total == 0:
                    logger.error("⚠️ ALERTE: Projet VIDE!")
                    QtWidgets.QMessageBox.warning(
                        self, "Projet Vide",
                        f"Le projet '{new_name}' existe en base mais est VIDE!\n\n"
                        f"Ajoutez des typologies avant de sauvegarder."
                    )
                else:
                    logger.info("✅ PROJET CORRECTEMENT SAUVEGARDÉ!")
                    
            else:
                logger.error(f"❌ PROJET '{new_name}' NON TROUVÉ!")
                
                cursor.execute("SELECT name FROM projects")
                all_projects = [r['name'] for r in cursor.fetchall()]
                logger.error(f"Projets existants: {all_projects}")
                
                QtWidgets.QMessageBox.critical(
                    self, "Échec",
                    f"Le projet '{new_name}' N'EST PAS en base!\n\n"
                    f"Projets existants: {', '.join(all_projects) if all_projects else 'Aucun'}"
                )
                return
                
        except Exception as e:
            logger.error(f"❌ EXCEPTION POINT 9: {e}")
            logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Exception: {e}")
            return
    
        logger.info("\n" + "=" * 100)
        logger.info("✅ VÉRIFICATION POINT 9 TERMINÉE")
        logger.info("=" * 100)
    
        # POINT 10: Post-traitement
        logger.info("\n📋 DIAGNOSTIC POINT 10: Post-traitement")
        self.hierarchy_cache.mark_clean()
        self._refresh_project_combos()
        index = self.project_combo.findText(new_name)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
        self.project_saved.emit()
    
        logger.info("\n" + "=" * 100)
        logger.info(f"🎉 SAUVEGARDE TERMINÉE AVEC SUCCÈS: '{new_name}'")
        logger.info("=" * 100)
        
        QtWidgets.QMessageBox.information(
            self, "Succès",
            f"✅ Projet '{new_name}' sauvegardé!\n\nConsultez les logs."
        )
            
    def _verify_database_content(self, project_name):
        """
        Vérifie le contenu réel de la base de données SQLite
        À appeler après une sauvegarde pour confirmer l'insertion
        """
        logger.info("\n" + "=" * 100)
        logger.info("🔍 VÉRIFICATION DIRECTE DU CONTENU DE LA BASE DE DONNÉES SQLite")
        logger.info("=" * 100)

        try:
            # Accès direct à la connexion SQLite
            db = self.project_manager.database
            if not db.connection:
                logger.error("❌ Pas de connexion à la base de données")
                return

            cursor = db.connection.cursor()

            # 1. Vérifier le projet
            logger.info(f"\n📋 1. VÉRIFICATION DU PROJET '{project_name}'")
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            project = cursor.fetchone()

            if project:
                logger.info(f"  ✅ Projet trouvé dans la base")
                logger.info(f"     - ID: {project['id']}")
                logger.info(f"     - Nom: {project['name']}")
                logger.info(f"     - Description: {project['description']}")
                logger.info(f"     - Créé le: {project['created_at']}")
                logger.info(f"     - Modifié le: {project['updated_at']}")
                project_id = project['id']
            else:
                logger.error(f"  ❌ Projet '{project_name}' NON TROUVÉ dans la base!")
                return

            # 2. Vérifier les typologies
            logger.info(f"\n📁 2. VÉRIFICATION DES TYPOLOGIES")
            cursor.execute("""
                SELECT * FROM typologies 
                WHERE project_id = ? 
                ORDER BY position
            """, (project_id,))
            typologies = cursor.fetchall()

            if typologies:
                logger.info(f"  ✅ {len(typologies)} typologie(s) trouvée(s)")
                for idx, typ in enumerate(typologies):
                    logger.info(f"\n     [{idx+1}] Typologie:")
                    logger.info(f"         - ID: {typ['id']}")
                    logger.info(f"         - Nom: {typ['name']}")
                    logger.info(f"         - Description: {typ['description']}")
                    logger.info(f"         - Position: {typ['position']}")

                    # 3. Vérifier les clusters de taxonomie
                    logger.info(f"\n     📊 Clusters de taxonomie pour '{typ['name']}':")
                    cursor.execute("""
                        SELECT * FROM taxonomy_clusters 
                        WHERE typologie_id = ? 
                        ORDER BY position
                    """, (typ['id'],))
                    clusters = cursor.fetchall()

                    if clusters:
                        logger.info(f"        ✅ {len(clusters)} cluster(s) trouvé(s)")
                        for c_idx, cluster in enumerate(clusters):
                            logger.info(f"\n        [{c_idx+1}] Cluster:")
                            logger.info(f"            - ID: {cluster['id']}")
                            logger.info(f"            - Nom: {cluster['name']}")
                            logger.info(f"            - Description: {cluster['description']}")
                            logger.info(f"            - Position: {cluster['position']}")

                            # 4. Vérifier les root labels
                            logger.info(f"\n        🏷️  Root labels pour '{cluster['name']}':")
                            cursor.execute("""
                                SELECT * FROM root_labels 
                                WHERE taxonomy_id = ? 
                                ORDER BY position
                            """, (cluster['id'],))
                            roots = cursor.fetchall()

                            if roots:
                                logger.info(f"           ✅ {len(roots)} root(s) trouvé(s)")
                                for r_idx, root in enumerate(roots):
                                    logger.info(f"\n           [{r_idx+1}] Root:")
                                    logger.info(f"               - ID: {root['id']}")
                                    logger.info(f"               - Nom: {root['name']}")
                                    logger.info(f"               - Catégorie: {root['category']}")
                                    logger.info(f"               - Position: {root['position']}")

                                    # 5. Vérifier les parent labels
                                    logger.info(f"\n           👨 Parent labels pour '{root['name']}':")
                                    cursor.execute("""
                                        SELECT * FROM parent_labels 
                                        WHERE root_id = ? 
                                        ORDER BY position
                                    """, (root['id'],))
                                    parents = cursor.fetchall()

                                    if parents:
                                        logger.info(f"              ✅ {len(parents)} parent(s) trouvé(s)")
                                        for p_idx, parent in enumerate(parents):
                                            logger.info(f"\n              [{p_idx+1}] Parent:")
                                            logger.info(f"                  - ID: {parent['id']}")
                                            logger.info(f"                  - Nom: {parent['name']}")
                                            logger.info(f"                  - Catégorie: {parent['category']}")
                                            logger.info(f"                  - Position: {parent['position']}")

                                            # 6. Vérifier les child labels
                                            logger.info(f"\n              👶 Child labels pour '{parent['name']}':")
                                            cursor.execute("""
                                                SELECT * FROM child_labels 
                                                WHERE parent_label_id = ? AND parent_child_id IS NULL
                                                ORDER BY position
                                            """, (parent['id'],))
                                            children = cursor.fetchall()

                                            if children:
                                                logger.info(f"                 ✅ {len(children)} enfant(s) direct(s) trouvé(s)")
                                                for ch_idx, child in enumerate(children):
                                                    logger.info(f"\n                 [{ch_idx+1}] Child:")
                                                    logger.info(f"                     - ID: {child['id']}")
                                                    logger.info(f"                     - Nom: {child['name']}")
                                                    logger.info(f"                     - Catégorie: {child['category']}")
                                                    logger.info(f"                     - Profondeur: {child['depth']}")
                                                    logger.info(f"                     - Position: {child['position']}")

                                                    # Vérifier les sous-enfants récursivement
                                                    self._verify_children_recursive(cursor, child['id'], 1)
                                            else:
                                                logger.info(f"                 ⚠️  Aucun enfant trouvé")
                                    else:
                                        logger.info(f"              ⚠️  Aucun parent trouvé")
                            else:
                                logger.info(f"           ⚠️  Aucun root trouvé")
                    else:
                        logger.info(f"        ⚠️  Aucun cluster trouvé")
            else:
                logger.info(f"  ⚠️  Aucune typologie trouvée")

            # 7. RÉSUMÉ FINAL
            logger.info("\n" + "=" * 100)
            logger.info("📊 RÉSUMÉ DE LA VÉRIFICATION")
            logger.info("=" * 100)

            # Compter tous les éléments
            cursor.execute("SELECT COUNT(*) as count FROM typologies WHERE project_id = ?", (project_id,))
            typ_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM taxonomy_clusters 
                WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
            """, (project_id,))
            cluster_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM root_labels 
                WHERE taxonomy_id IN (
                    SELECT id FROM taxonomy_clusters 
                    WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                )
            """, (project_id,))
            root_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM parent_labels 
                WHERE root_id IN (
                    SELECT id FROM root_labels 
                    WHERE taxonomy_id IN (
                        SELECT id FROM taxonomy_clusters 
                        WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                    )
                )
            """, (project_id,))
            parent_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM child_labels 
                WHERE parent_label_id IN (
                    SELECT id FROM parent_labels 
                    WHERE root_id IN (
                        SELECT id FROM root_labels 
                        WHERE taxonomy_id IN (
                            SELECT id FROM taxonomy_clusters 
                            WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                        )
                    )
                )
            """, (project_id,))
            child_count = cursor.fetchone()['count']

            logger.info(f"  ✅ Projet: '{project_name}' (ID: {project_id})")
            logger.info(f"  ✅ {typ_count} typologie(s)")
            logger.info(f"  ✅ {cluster_count} cluster(s) de taxonomie")
            logger.info(f"  ✅ {root_count} root label(s)")
            logger.info(f"  ✅ {parent_count} parent label(s)")
            logger.info(f"  ✅ {child_count} child label(s)")
            logger.info(f"\n  🎯 TOTAL: {typ_count + cluster_count + root_count + parent_count + child_count} enregistrements")

            logger.info("\n" + "=" * 100)
            logger.info("✅ VÉRIFICATION TERMINÉE - TOUTES LES DONNÉES SONT BIEN EN BASE")
            logger.info("=" * 100 + "\n")

        except Exception as e:
            logger.error(f"\n❌ ERREUR lors de la vérification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _verify_children_recursive(self, cursor, parent_child_id, depth):
        """Vérifie récursivement les enfants imbriqués"""
        indent = "                     " + ("  " * depth)

        cursor.execute("""
            SELECT * FROM child_labels 
            WHERE parent_child_id = ? 
            ORDER BY position
        """, (parent_child_id,))
        sub_children = cursor.fetchall()

        if sub_children:
            logger.info(f"{indent}👶 {len(sub_children)} sous-enfant(s) (profondeur {depth})")
            for idx, child in enumerate(sub_children):
                logger.info(f"\n{indent}[{idx+1}] Sous-enfant:")
                logger.info(f"{indent}    - ID: {child['id']}")
                logger.info(f"{indent}    - Nom: {child['name']}")
                logger.info(f"{indent}    - Profondeur: {child['depth']}")
                logger.info(f"{indent}    - Position: {child['position']}")

                # Vérifier les enfants de cet enfant
                self._verify_children_recursive(cursor, child['id'], depth + 1)

    def _add_typologie(self):
        """Add typologie"""
        name, ok = QtWidgets.QInputDialog.getText(self, tr("dataset.new_typologie"), tr("dataset.name") + ":")
        if ok and name.strip():
            name = name.strip()

            # Ajouter au cache hiérarchique
            if self.hierarchy_cache.add_typologie(name):
                # Aussi dans le manager
                if self.project_manager.add_typologie(name, self):
                    self._refresh_typologie_list()
                    self._refresh_all_counts()  # ← AJOUTER CETTE LIGNE
                    logger.info(f"Typologie '{name}' added")
            else:
                QtWidgets.QMessageBox.warning(self, "Erreur", 
                    f"La typologie '{name}' existe déjà")

    def _edit_typologie(self):
        """Edit selected typologie"""
        current = self.typologie_list.currentItem()
        if not current:
            return
        old_name = current.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.edit_typologie"), 
            tr("dataset.new_name") + ":", 
            text=old_name
        )
        if ok and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()

            # Renommer dans le cache
            if self.hierarchy_cache.rename_typologie(old_name, new_name):
                # Aussi dans le manager
                if self.project_manager.edit_typologie(old_name, new_name, self):
                    self._refresh_typologie_list()
                    logger.info(f"Typologie '{old_name}' renamed to '{new_name}'")

    def _remove_typologie(self):
        """Remove selected typologie"""
        current = self.typologie_list.currentItem()
        if not current:
            return
        name = current.text()
        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"), 
            f"{tr('dataset.delete_typologie_confirm')}: '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            # Supprimer du cache
            self.hierarchy_cache.remove_typologie(name)

            # Aussi du manager
            if self.project_manager.remove_typologie(name):
                self._refresh_typologie_list()
                self._clear_hierarchy()
                logger.info(f"Typologie '{name}' deleted")

    def _add_label(self, level):
        """
        Ajoute un label à un niveau - VERSION AVEC VALIDATION COMPLÈTE
        """
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Nouveau {level}", "Nom :"
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        if level == "root":
            taxonomy = self.project_manager.get_current_taxonomy()
            if not taxonomy:
                logger.error("ÉCHEC: get_current_taxonomy() retourne None")
                logger.error(f"État manager: typologie_idx={self.project_manager.current_typologie_index}, "
                            f"taxonomy_idx={self.project_manager.current_taxonomy_index}")

                QtWidgets.QMessageBox.critical(
                    self, 
                    "Erreur de synchronisation",
                    "Le cluster de taxonomie n'est pas correctement sélectionné.\n\n"
                    "Veuillez:\n"
                    "1. Resélectionner la typologie\n"
                    "2. Resélectionner le cluster de taxonomie\n"
                    "3. Réessayer d'ajouter le root"
                )
                return

            logger.debug(f"✓ Taxonomy validé: '{taxonomy.get('name')}'")

        elif level == "parent":
            root = self.project_manager.get_current_root()
            if not root:
                logger.error("ÉCHEC: get_current_root() retourne None")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur de synchronisation",
                    "Le root label n'est pas correctement sélectionné."
                )
                return

            logger.debug(f"✓ Root validé: '{root.get('name')}'")

        path = self._get_path_for_level(level)
        if path is None:
            QtWidgets.QMessageBox.warning(self, "Erreur", 
                "Veuillez d'abord sélectionner le niveau parent")
            return

        logger.debug(f"Chemin pour {level}: {' > '.join(path)}")

        existing = self.hierarchy_cache.get_children_at_path(path)
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Doublon", 
                f"'{name}' existe déjà à ce niveau")
            return

        if not self.hierarchy_cache.add_child_at_path(path, name):
            QtWidgets.QMessageBox.warning(self, "Erreur",
                f"Impossible d'ajouter '{name}' au cache")
            return

        logger.info(f"✓ '{name}' ajouté au cache")

        success = False

        if level == "taxonomy":
            success = True

        elif level == "root":
            logger.debug(f"Appel add_root_label('{name}')")
            success = self.project_manager.add_root_label(name, self)

            if not success:
                logger.error(f"✗ Échec add_root_label pour '{name}'")
                # Diagnostic
                taxonomy = self.project_manager.get_current_taxonomy()
                logger.error(f"Taxonomy actuel: {taxonomy}")
            else:
                logger.info(f"✓ '{name}' ajouté au project_manager")

        elif level == "parent":
            logger.debug(f"Appel add_parent_label('{name}')")
            success = self.project_manager.add_parent_label(name, self)

            if not success:
                logger.error(f"✗ Échec add_parent_label pour '{name}'")
            else:
                logger.info(f"✓ '{name}' ajouté au project_manager")

        if success:
            list_widget = self._get_list_for_level(level)
            self._load_list_from_cache(list_widget, path)

            self._refresh_all_counts()

            logger.info(f"✓✓✓ {level.capitalize()} '{name}' ajouté avec succès")
        else:
            self.hierarchy_cache.remove_child_at_path(path, name)
            logger.error(f"✗✗✗ Rollback: '{name}' retiré du cache")

            QtWidgets.QMessageBox.warning(self, "Erreur",
                f"Impossible d'ajouter le {level} dans le gestionnaire de projet.\n\n"
                f"Vérifez les logs pour plus de détails.")

    def _edit_label(self, level):
        """Modifier un label"""
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            return
        
        old_name = current.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, f"{tr('dataset.edit')} {level}",
            tr("dataset.new_name") + ":",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name == old_name:
            return
        
        new_name = new_name.strip()
        path = self._get_path_for_level(level)
        
        if path is None:
            return
        
        # Renommer dans le cache
        if self.hierarchy_cache.rename_child_at_path(path, old_name, new_name):
            current.setText(new_name)
            logger.info(f"{level.capitalize()} renommé: '{old_name}' -> '{new_name}'")

    def _remove_label(self, level):
        """Supprimer un label"""
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            return
        
        name = current.text()
        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"),
            f"Supprimer '{name}' et tous ses sous-éléments?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        path = self._get_path_for_level(level)
        
        if path is None:
            return
        
        # Supprimer du cache
        if self.hierarchy_cache.remove_child_at_path(path, name):
            row = list_widget.currentRow()
            list_widget.takeItem(row)
            
            # Effacer les niveaux inférieurs si nécessaire
            self._clear_levels_below(level)
            
            logger.info(f"{level.capitalize()} '{name}' supprimé")

    def _get_path_for_level(self, level: str) -> list:
        """Obtenir le chemin parent pour un niveau donné - EXTRAIT LES NOMS SANS COMPTEURS"""
        typ_item = self.typologie_list.currentItem()

        if level == "taxonomy":
            if typ_item:
                # Extraire le nom sans compteur
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
                return [typ_name]
            return None

        tax_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None

        if level == "root":
            if typ_item and tax_item:
                # Extraire les noms sans compteurs
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

                return [typ_name, tax_name]
            return None

        root_item = self.root_list.currentItem()

        if level == "parent":
            if typ_item and tax_item and root_item:
                # Extraire les noms sans compteurs
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

                root_display = root_item.text()
                root_name = root_display.split(" (")[0] if " (" in root_display else root_display

                return [typ_name, tax_name, root_name]
            return None

        return None


    def _add_child(self):
        """
        Ajoute un enfant - VERSION TOTALEMENT CORRIGÉE
        """
        parent_item = self.parent_list.currentItem()
        if not parent_item:
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Veuillez d'abord sélectionner un parent")
            return
    
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouvel enfant", "Nom :"
        )
        if not ok or not name.strip():
            return
    
        name = name.strip()
    
        # CORRECTION: Construire le chemin complet
        path = self._get_full_path()
    
        logger.debug(f"=== AJOUT ENFANT ===")
        logger.debug(f"Nom: '{name}'")
        logger.debug(f"Chemin: {' > '.join(path)}")
        logger.debug(f"Longueur chemin: {len(path)}")
    
        if len(path) < 4:
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Chemin incomplet. Veuillez sélectionner typologie, taxonomy, root et parent.")
            return
    
        # Vérifier doublon dans le cache
        existing = self.hierarchy_cache.get_children_at_path(path)
        logger.debug(f"Enfants existants à ce niveau: {existing}")
    
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Doublon",
                f"'{name}' existe déjà à ce niveau")
            return
    
        # Ajouter au cache
        if self.hierarchy_cache.add_child_at_path(path, name):
            logger.info(f"✓ '{name}' ajouté au cache")
    
            # Ajouter au project_manager
            if self.project_manager.add_child_label(name, self):
                logger.info(f"✓ '{name}' ajouté au project_manager")

                logger.debug("🔄 Rechargement de la liste des enfants...")
                self._load_children_from_cache()
                logger.debug("✓ Liste rechargée")

                logger.debug("🔄 Rafraîchissement de tous les compteurs...")
                self._refresh_all_counts()
                logger.debug("✓ Compteurs rafraîchis")
            else:
                # Retirer du cache si échec
                self.hierarchy_cache.remove_child_at_path(path, name)
                logger.error(f"✗ Échec ajout au project_manager, rollback")
                QtWidgets.QMessageBox.warning(self, "Erreur",
                    "Impossible d'ajouter l'enfant au project_manager")
        else:
            logger.error(f"✗ Échec ajout au cache")
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Impossible d'ajouter l'enfant au cache")
            
    def _clear_all_caches(self):
        """Vide tous les caches"""
        self.hierarchy_cache.clear()
        self._child_navigation_path.clear()

        logger.debug("Cache hiérarchique vidé")

    def _edit_child(self):
        """Modifier un enfant - VERSION CORRIGÉE avec extraction du nom"""
        current = self.child_list.currentItem()
        if not current:
            return

        old_display = current.text()
        # CORRECTION: Extraire le nom réel pour l'édition
        if " (" in old_display:
            old_name = old_display.split(" (")[0]
        else:
            old_name = old_display

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.edit_child"),
            tr("dataset.new_name") + ":",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name == old_name:
            return

        new_name = new_name.strip()
        path = self._get_full_path()

        # Renommer avec le NOM RÉEL (sans compteur)
        if self.hierarchy_cache.rename_child_at_path(path, old_name, new_name):
            # Recharger pour afficher le nouveau nom avec compteur mis à jour
            self._load_children_from_cache()
            logger.info(f"Enfant renommé: '{old_name}' -> '{new_name}'")

    def _remove_child(self):
        """Supprimer un enfant - VERSION CORRIGÉE avec extraction du nom"""
        current = self.child_list.currentItem()
        if not current:
            return

        child_display = current.text()
        # CORRECTION: Extraire le nom réel pour la suppression
        if " (" in child_display:
            child_name = child_display.split(" (")[0]
        else:
            child_name = child_display

        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"),
            f"Supprimer '{child_name}' et tous ses sous-éléments?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        path = self._get_full_path()

        if self.hierarchy_cache.remove_child_at_path(path, child_name):
            self._load_children_from_cache()

            self._refresh_all_counts()

            logger.info(f"Enfant '{child_name}' supprimé")

    def _modify_category(self, level):
        """Modify label category"""
        categories = ["default", "technique", "business", "creative"]
        category, ok = QtWidgets.QInputDialog.getItem(
            self, tr("dataset.modify_category"), tr("dataset.choose_category") + ":", categories, 0, False
        )
        if ok:
            if self.project_manager.modify_label_category(level, category):
                project_data = self.project_manager.get_current_project_data()
                if project_data:
                    self.preview_updated.emit(project_data)
                logger.info(f"Category of {level} modified to '{category}'")

    # ========== UI HELPERS ==========

    def _get_list_for_level(self, level: str) -> QtWidgets.QListWidget:
        """Retourner le widget liste pour un niveau"""
        mapping = {
            "taxonomy": self.taxonomy_list,
            "root": self.root_list,
            "parent": self.parent_list,
            "child": self.child_list
        }
        return mapping.get(level, self.child_list)
    
    def _clear_levels_below(self, level: str):
        """Effacer les niveaux sous un niveau donné"""
        levels = ["taxonomy", "root", "parent", "child"]
        try:
            idx = levels.index(level)
            for lvl in levels[idx + 1:]:
                self._get_list_for_level(lvl).clear()
            if level in ["taxonomy", "root", "parent"]:
                self._child_navigation_path.clear()
        except ValueError:
            pass

    def _sync_current_level_to_cache(self):
        """Synchroniser le niveau actuel vers le cache"""
        # Cette méthode est appelée avant de changer de sélection
        # pour s'assurer que l'état actuel est sauvegardé
        pass

    def _ensure_typologie_selected(self):
        """Ensure typologie is selected"""
        if self.typologie_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_typologie_first")
            )
            return False
        return True

    def _ensure_taxonomy_selected(self):
        """Ensure taxonomy cluster is selected"""
        if not self._ensure_typologie_selected():
            return False
        # If taxonomy clusters are not being used yet, skip this check
        if not hasattr(self, 'taxonomy_list'):
            return True
        if self.taxonomy_list.count() == 0:
            # No taxonomy clusters yet, show warning
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), "Veuillez d'abord ajouter un cluster de taxonomie"
            )
            return False
        if self.taxonomy_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), "Veuillez d'abord sélectionner un cluster de taxonomie"
            )
            return False
        return True

    def _ensure_root_selected(self):
        """Ensure root label is selected"""
        if not self._ensure_taxonomy_selected():
            return False
        if self.root_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_root_first")
            )
            return False
        return True

    def _ensure_parent_selected(self):
        """Ensure parent label is selected"""
        if not self._ensure_root_selected():
            return False
        if self.parent_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_parent_first")
            )
            return False
        return True

    def _load_project_ui(self):
        data = self.project_manager.get_current_project_data()
        if not data:
            return

        # Charger le nom du projet
        self.project_name_edit.setText(data.get('nom', ''))

        # Charger les typologies depuis le cache (déjà peuplé)
        self._refresh_typologie_list()

        # Activer les boutons
        self.save_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(True)

        # Mettre à jour l'état des boutons
        self._update_button_states()

        logger.debug("Interface projet chargée")

    def _refresh_typologie_list(self):
        """Refresh typologies list from cache"""
        self.typologie_list.clear()

        # Charger depuis le cache
        typologies = self.hierarchy_cache.get_typologies()
        for typ_name in typologies:
            item = QtWidgets.QListWidgetItem(typ_name)
            self.typologie_list.addItem(item)

        # Si vide, charger depuis le manager
        if not typologies:
            db_typologies = self.project_manager.get_typologies()
            for typ in db_typologies:
                typ_name = typ.get('name', '')
                if typ_name:
                    self.hierarchy_cache.add_typologie(typ_name)
                    item = QtWidgets.QListWidgetItem(typ_name)
                    self.typologie_list.addItem(item)

        self._update_button_states()

    def _load_taxonomy_clusters(self):
        """Load taxonomy clusters"""
        if not hasattr(self, 'taxonomy_list'):
            return
        self.taxonomy_list.clear()
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self._update_button_states()

    def _load_root_labels(self):
        """Load root labels for the currently selected taxonomy cluster"""
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()

        if not hasattr(self, 'taxonomy_list'):
            logger.warning("taxonomy_list n'existe pas")
            self._update_button_states()
            return

        current_taxonomy = self.taxonomy_list.currentItem()
        if not current_taxonomy:
            logger.debug("Aucun cluster de taxonomie sélectionné")
            self._update_button_states()
            return

        taxonomy_name = current_taxonomy.text()
        logger.debug(f"Chargement des labels racines pour le cluster: '{taxonomy_name}'")

        root_labels = self.project_manager.get_root_labels()

        if not root_labels:
            logger.debug(f"Aucun label racine trouvé pour le cluster '{taxonomy_name}'")
        else:
            logger.debug(f"{len(root_labels)} label(s) racine(s) trouvé(s) pour '{taxonomy_name}'")

        for label in root_labels:
            item = QtWidgets.QListWidgetItem(label.get('name', ''))
            self.root_list.addItem(item)

        self._update_button_states()

    def _load_parent_labels(self):
        """Load parent labels"""
        self.parent_list.clear()
        self.child_list.clear()
        parent_labels = self.project_manager.get_parent_labels()
        for label in parent_labels:
            item = QtWidgets.QListWidgetItem(label.get('name', ''))
            self.parent_list.addItem(item)
        self._update_button_states()

    def _load_child_labels(self):
        """Load child labels at current depth - DEPRECATED, use _load_child_from_cache instead"""
        # Cette méthode est maintenant remplacée par _load_child_from_cache
        self._load_child_from_cache()

    def _clear_ui(self):
        """Clear entire UI"""
        self.project_name_edit.clear()
        self.typologie_list.clear()
        self._clear_hierarchy()

        # Vider le cache unifié
        self.hierarchy_cache.clear()

        self.save_btn.setEnabled(False)
        self.delete_project_btn.setEnabled(False)
        self._update_button_states()

    def _clear_hierarchy(self):
        """Clear label hierarchy"""
        if hasattr(self, 'taxonomy_list'):
            self.taxonomy_list.clear()
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self.breadcrumb_label.setText(tr("dataset.root"))
        self.up_btn.setEnabled(False)
        self._update_button_states()

    def _update_button_states(self):
        """Update button states based on selections and hierarchy"""
        project_selected = bool(
            self.project_combo.currentIndex() >= 0 and 
            self.project_combo.currentText()
        )

        typologie_selected = self.typologie_list.currentItem() is not None
        taxonomy_selected = hasattr(self, 'taxonomy_list') and self.taxonomy_list.currentItem() is not None
        root_selected = self.root_list.currentItem() is not None
        parent_selected = self.parent_list.currentItem() is not None
        child_selected = self.child_list.currentItem() is not None

        self.add_project_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(project_selected)

        self.add_typologie_btn.setEnabled(project_selected)
        self.edit_typologie_btn.setEnabled(typologie_selected)
        self.remove_typologie_btn.setEnabled(typologie_selected)

        if hasattr(self, 'add_taxonomy_btn'):
            self.add_taxonomy_btn.setEnabled(typologie_selected)
            self.edit_taxonomy_btn.setEnabled(taxonomy_selected)
            self.remove_taxonomy_btn.setEnabled(taxonomy_selected)
            self.category_taxonomy_btn.setEnabled(taxonomy_selected)
            self.taxonomy_list.setEnabled(typologie_selected)

        self.add_root_btn.setEnabled(taxonomy_selected)
        self.edit_root_btn.setEnabled(root_selected)
        self.remove_root_btn.setEnabled(root_selected)
        self.category_root_btn.setEnabled(root_selected)
        self.root_list.setEnabled(taxonomy_selected)

        self.add_parent_btn.setEnabled(root_selected)
        self.edit_parent_btn.setEnabled(parent_selected)
        self.remove_parent_btn.setEnabled(parent_selected)
        self.category_parent_btn.setEnabled(parent_selected)
        self.parent_list.setEnabled(root_selected)

        self.add_child_btn.setEnabled(parent_selected)
        self.edit_child_btn.setEnabled(child_selected)
        self.remove_child_btn.setEnabled(child_selected)
        self.category_child_btn.setEnabled(child_selected)
        self.dive_btn.setEnabled(child_selected)
        self.child_list.setEnabled(parent_selected)

        depth = len(self._child_navigation_path)
        self.up_btn.setEnabled(depth > 0)

        self.save_btn.setEnabled(project_selected)

    def _refresh_project_combos(self):
        """Refresh all project combos"""
        try:
            projects = self.project_manager.get_all_projects()
            project_names = sorted([p['name'] for p in projects])
            current_project = self.project_combo.currentText()
            
            self.project_combo.blockSignals(True)
            self.project_combo.clear()
            
            if project_names:
                self.project_combo.addItems(project_names)
                logger.info(f"{len(project_names)} projet(s) chargé(s): {', '.join(project_names)}")
            else:
                logger.info("Aucun projet trouvé dans la base de données")
            
            self.project_combo.blockSignals(False)
            
            # Resélectionner le projet courant et forcer le chargement
            if current_project in project_names:
                index = self.project_combo.findText(current_project)
                self.project_combo.setCurrentIndex(index)
                # Forcer le chargement même si l'index n'a pas changé
                self._on_project_selected(index)
            elif project_names:
                # Si le projet courant n'existe plus, sélectionner le premier
                self.project_combo.setCurrentIndex(0)
                self._on_project_selected(0)
            else:
                # Aucun projet disponible, nettoyer l'interface
                self._clear_ui()
            
            self._update_button_states()
            
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement des projets: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger les projets: {str(e)}"
            )

    def _load_project_from_db_to_cache(self):
        """
        Charge un projet depuis la base de données vers le cache hiérarchique
        VERSION AVEC SYNCHRONISATION DES INDEX
        """
        if not self.project_manager.current_project_data:
            logger.warning("Aucun projet à charger dans le cache")
            return

        # Vider le cache actuel
        self.hierarchy_cache.clear()

        project_data = self.project_manager.current_project_data
        typologies = project_data.get('typologies', [])

        for typ_idx, typologie in enumerate(typologies):
            typ_name = typologie.get('name', '')
            if not typ_name:
                continue
            
            # Ajouter la typologie
            self.hierarchy_cache.add_typologie(typ_name)

            # Charger les clusters de taxonomie
            taxonomy_clusters = typologie.get('taxonomy_clusters', [])

            for tax_idx, cluster in enumerate(taxonomy_clusters):
                cluster_name = cluster.get('name', '')
                if not cluster_name:
                    continue
                
                logger.debug(f"Chargement taxonomy '{cluster_name}' (index {tax_idx}) "
                            f"pour typologie '{typ_name}' (index {typ_idx})")

                # Ajouter le cluster au cache
                path = [typ_name]
                self.hierarchy_cache.add_child_at_path(path, cluster_name)

                # Charger les root labels
                root_labels = cluster.get('root_labels', [])
                for root in root_labels:
                    root_name = root.get('name', '')
                    if not root_name:
                        continue
                    
                    path = [typ_name, cluster_name]
                    self.hierarchy_cache.add_child_at_path(path, root_name)

                    # Charger les parent labels
                    parent_labels = root.get('parent_labels', [])
                    for parent in parent_labels:
                        parent_name = parent.get('name', '')
                        if not parent_name:
                            continue
                        
                        path = [typ_name, cluster_name, root_name]
                        self.hierarchy_cache.add_child_at_path(path, parent_name)

                        # Charger les enfants récursivement
                        children = parent.get('children', [])
                        path = [typ_name, cluster_name, root_name, parent_name]
                        self._load_children_recursive_to_cache(path, children)

        logger.info(f"✓ Projet chargé dans le cache: {len(typologies)} typologie(s)")

    def _has_unsaved_changes(self):
        """
        Vérifie s'il y a des modifications non sauvegardées
        """
        return self.hierarchy_cache.has_changes()

    def _load_children_recursive_to_cache(self, parent_path, children_list):
        """
        Charge récursivement les enfants dans le cache

        Args:
            parent_path: Chemin jusqu'au parent (liste de noms)
            children_list: Liste des enfants à charger
        """
        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                continue
            
            # Ajouter l'enfant au cache
            self.hierarchy_cache.add_child_at_path(parent_path, child_name)

            # Charger les sous-enfants récursivement
            sub_children = child.get('children', [])
            if sub_children:
                child_path = parent_path + [child_name]
                self._load_children_recursive_to_cache(child_path, sub_children)

    def _prompt_save_if_needed(self):
        """
        Demande à l'utilisateur s'il veut sauvegarder avant de continuer
        """
        if self._has_unsaved_changes():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Modifications non sauvegardées",
                "Le projet contient des modifications non sauvegardées. Voulez-vous sauvegarder ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self._save_project()
                return True
            elif reply == QtWidgets.QMessageBox.Cancel:
                return False

        return True
    
    def _validate_hierarchy_integrity(self):
        """
        Valide l'intégrité de la hiérarchie cache <-> project_manager
        Utile pour le débogage
        """
        try:
            # Vérifier que toutes les typologies du cache sont dans le manager
            cache_typologies = set(self.hierarchy_cache.get_typologies())
            manager_typologies = set(t.get('name', '') for t in self.project_manager.get_typologies())

            if cache_typologies != manager_typologies:
                logger.warning(f"Incohérence typologies: cache={cache_typologies}, manager={manager_typologies}")
                return False

            logger.debug("Intégrité de la hiérarchie validée")
            return True

        except Exception as e:
            logger.error(f"Erreur validation intégrité: {e}")
            return False

    def _sync_cache_to_project_manager(self):
        """
        Synchronise le cache hiérarchique vers le project_manager
        À appeler avant save_project()
        """
        if not self.project_manager.current_project_data:
            logger.error("Aucun projet actuel")
            return False

        # Construire la structure de données depuis le cache
        typologies = []

        for typ_name in self.hierarchy_cache.get_typologies():
            typologie = {
                'name': typ_name,
                'description': '',
                'taxonomy_clusters': []
            }

            # Récupérer les clusters de taxonomie
            typ_path = [typ_name]
            clusters = self.hierarchy_cache.get_children_at_path(typ_path)

            for cluster_name in clusters:
                cluster = {
                    'name': cluster_name,
                    'description': '',
                    'root_labels': []
                }

                # Récupérer les root labels
                cluster_path = [typ_name, cluster_name]
                roots = self.hierarchy_cache.get_children_at_path(cluster_path)

                for root_name in roots:
                    root = {
                        'name': root_name,
                        'description': '',
                        'category': 'default',
                        'parent_labels': []
                    }

                    # Récupérer les parent labels
                    root_path = [typ_name, cluster_name, root_name]
                    parents = self.hierarchy_cache.get_children_at_path(root_path)

                    for parent_name in parents:
                        parent = {
                            'name': parent_name,
                            'description': '',
                            'category': 'default',
                            'children': []
                        }

                        # Récupérer les enfants récursivement
                        parent_path = [typ_name, cluster_name, root_name, parent_name]
                        parent['children'] = self._build_children_from_cache(parent_path)

                        root['parent_labels'].append(parent)

                    cluster['root_labels'].append(root)

                typologie['taxonomy_clusters'].append(cluster)

            typologies.append(typologie)

        # Mettre à jour le project_manager
        self.project_manager.current_project_data['typologies'] = typologies

        logger.info(f"Cache synchronisé: {len(typologies)} typologie(s)")
        return True
    def _debug_print_cache(self):
        """Affiche le contenu du cache pour debug"""
        logger.info("=== DEBUG CACHE ===")
        for typ_name in self.hierarchy_cache.get_typologies():
            logger.info(f"Typologie: {typ_name}")
            for cluster in self.hierarchy_cache.get_children_at_path([typ_name]):
                logger.info(f"  Cluster: {cluster}")
                for root in self.hierarchy_cache.get_children_at_path([typ_name, cluster]):
                    logger.info(f"    Root: {root}")
                    for parent in self.hierarchy_cache.get_children_at_path([typ_name, cluster, root]):
                        logger.info(f"      Parent: {parent}")
                        self._debug_print_children([typ_name, cluster, root, parent], 8)
    
    def _debug_print_children(self, path, indent):
        """Affiche récursivement les enfants"""
        children = self.hierarchy_cache.get_children_at_path(path)
        for child in children:
            logger.info(f"{' ' * indent}Child: {child}")
            self._debug_print_children(path + [child], indent + 2)
    
    def _debug_print_project_data(self):
        """Affiche le contenu du project_manager pour debug"""
        logger.info("=== DEBUG PROJECT DATA ===")
        data = self.project_manager.current_project_data
        if not data:
            logger.info("Aucune donnée de projet")
            return
        
        import json
        logger.info(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    
    def _build_children_from_cache(self, parent_path):
        children = []
        child_names = self.hierarchy_cache.get_children_at_path(parent_path)
        
        for child_name in child_names:
            child = {
                'name': child_name,
                'description': '',
                'category': 'default',
                'children': []
            }
            
            # Récupérer les sous-enfants récursivement
            child_path = parent_path + [child_name]
            child['children'] = self._build_children_from_cache(child_path)
            
            children.append(child)
        
        return children



    def _export_strategy(self):
        """Automatically export strategy"""
        if self.project_manager.current_project_name:
            self.project_manager.export_strategy()

    # ========== PUBLIC METHODS ==========

    def refresh(self):
        """Refresh widget data"""
        self._refresh_project_combos()
        if self.project_manager.current_project_name:
            self._load_project_ui()