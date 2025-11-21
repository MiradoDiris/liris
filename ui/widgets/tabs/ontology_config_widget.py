#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/ontology_config_widget.py - Tab for Ontology and Hierarchy Configuration
"""

import os
import json
import traceback
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import translator, tr


class CategoryEditDialog(QtWidgets.QDialog):
    """
    Dialogue pour l'ajout, la modification et la suppression de catégories multiples.
    """
    def __init__(self, current_categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("category_edit_dialog.title"))
        self.setMinimumSize(400, 300)

        self.categories = list(current_categories) # Travaille sur une copie
        
        self._init_ui()
        self._load_categories_into_list()
        self._update_button_states()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        info_label = QtWidgets.QLabel(tr("category_edit_dialog.info_label"))
        info_label.setStyleSheet("font-style: italic; color: #555;")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)

        self.category_list_widget = QtWidgets.QListWidget()
        self.category_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.category_list_widget.currentItemChanged.connect(self._update_button_states)
        main_layout.addWidget(self.category_list_widget)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton(tr("category_edit_dialog.add_button"))
        self.add_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_button.clicked.connect(self._add_category)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QtWidgets.QPushButton(tr("category_edit_dialog.edit_button"))
        self.edit_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_button.clicked.connect(self._edit_category)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QtWidgets.QPushButton(tr("category_edit_dialog.remove_button"))
        self.remove_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_button.clicked.connect(self._remove_category)
        buttons_layout.addWidget(self.remove_button)

        main_layout.addLayout(buttons_layout)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def _load_categories_into_list(self):
        self.category_list_widget.clear()
        for cat in self.categories:
            self.category_list_widget.addItem(cat)

    def _update_button_states(self):
        has_selection = self.category_list_widget.currentRow() != -1
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    def _add_category(self):
        text, ok = QtWidgets.QInputDialog.getText(self, 
                                                tr("category_edit_dialog.add_category_title"),
                                                tr("category_edit_dialog.add_category_text"))
        if ok and text:
            category = text.strip()
            if category and category not in self.categories:
                self.categories.append(category)
                self._load_categories_into_list()
                self.category_list_widget.setCurrentRow(self.category_list_widget.count() - 1) # Select new item
                logger.info(f"Catégorie ajoutée : {category}")

    def _edit_category(self):
        current_row = self.category_list_widget.currentRow()
        if current_row == -1: return

        old_category = self.categories[current_row]
        text, ok = QtWidgets.QInputDialog.getText(self, 
                                                tr("category_edit_dialog.edit_category_title"),
                                                tr("category_edit_dialog.edit_category_text"),
                                                QtWidgets.QLineEdit.Normal, old_category)
        if ok and text:
            new_category = text.strip()
            if new_category and new_category != old_category:
                if new_category in self.categories and self.categories.index(new_category) != current_row:
                    QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("category_edit_dialog.duplicate_category_msg"))
                    return
                self.categories[current_row] = new_category
                self._load_categories_into_list()
                self.category_list_widget.setCurrentRow(current_row) # Re-select edited item
                logger.info(f"Catégorie modifiée de '{old_category}' à '{new_category}'")

    def _remove_category(self):
        current_row = self.category_list_widget.currentRow()
        if current_row == -1: return

        category_to_remove = self.categories[current_row]
        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("category_edit_dialog.remove_category_title"),
                                            tr("category_edit_dialog.remove_category_text").format(category=category_to_remove),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.categories[current_row]
            self._load_categories_into_list()
            logger.info(f"Catégorie supprimée : {category_to_remove}")
            self._update_button_states() # Update button states after removal

    def get_categories(self):
        return self.categories


class OntologyConfigWidget(QtWidgets.QWidget):
    """Widget for configuring project ontology and hierarchy within a tab."""

    # Define signals that this widget might emit to the parent (ProjectConfigWidget)
    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.config_provider = config_provider # Keep if still needed for some reason, otherwise remove
        self.conductor = conductor
        self.database = conductor.database 
        if not self.database:
            logger.error("Database instance not available from conductor. OntologyConfigWidget cannot function correctly.")

        self.project_profiles = {}
        self.current_project_name = None
        self.current_project_profile_data = None
        self.current_cluster_index = -1
        self.current_cluster_data = None 
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        try:
            self._init_ui()
            self._load_project_profiles() # Initial load
            # Ajout d'un log de débogage pour confirmer la présence de la méthode
            if hasattr(self, '_on_child_label_selected'):
                logger.debug("OntologyConfigWidget: _on_child_label_selected method found during init.")
            else:
                logger.critical("OntologyConfigWidget: CRITICAL ERROR: _on_child_label_selected method NOT found during init.")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de OntologyConfigWidget : {str(e)}")

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration de l'ontologie (layout 2 colonnes)."""
        main_horizontal_layout = QtWidgets.QHBoxLayout(self)
        main_horizontal_layout.setSpacing(20)
        main_horizontal_layout.setContentsMargins(20, 20, 20, 20)

        # --- Colonne de gauche (Sélection et Détails du Projet) ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(15)
        left_column_layout.addStretch() 

        explanation = QtWidgets.QLabel(
            tr("project_config.explanation")
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        left_column_layout.addWidget(explanation)

        project_selection_group = QtWidgets.QGroupBox(tr("project_config.select_profile_group"))
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
        project_selection_layout.addStretch()

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        self.add_project_button = QtWidgets.QPushButton(tr("project_config.new_project_button"))
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        self.delete_project_button = QtWidgets.QPushButton(tr("project_config.delete_project_button"))
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)
        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(15)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(tr("project_config.project_name_placeholder"))
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_form_layout.addRow(tr("project_config.project_name_label"), self.project_name_edit)

        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)
        
        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        self.cluster_list_widget.currentItemChanged.connect(self._on_cluster_selected)
        cluster_list_layout.addWidget(self.cluster_list_widget)

        cluster_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_cluster_button = QtWidgets.QPushButton(tr("project_config.add_cluster_button"))
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)
        self.edit_cluster_button = QtWidgets.QPushButton(tr("project_config.edit_cluster_button"))
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)
        self.remove_cluster_button = QtWidgets.QPushButton(tr("project_config.remove_cluster_button"))
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)
        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
        cluster_list_layout.addLayout(cluster_buttons_layout)

        details_form_layout.addRow(cluster_list_layout)

        left_column_layout.addWidget(details_group)

        import_button_layout = QtWidgets.QHBoxLayout()
        import_button_layout.addStretch()
        self.import_folder_button = QtWidgets.QPushButton(tr("project_config.import_folder_button"))
        self.import_folder_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.import_folder_button.clicked.connect(self._on_import_directory)
        import_button_layout.addWidget(self.import_folder_button)
        import_button_layout.addStretch()
        left_column_layout.addLayout(import_button_layout)

        left_column_layout.addStretch()

        main_horizontal_layout.addLayout(left_column_layout, 3)

        # --- Colonne de droite (Hiérarchie de l'Ontologie avec ScrollArea) ---
        right_column_container = QtWidgets.QScrollArea()
        right_column_container.setWidgetResizable(True)
        right_column_container.setStyleSheet("border: none;")

        hierarchy_scroll_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(hierarchy_scroll_content)
        hierarchy_layout.setSpacing(10)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)

        hierarchy_group = QtWidgets.QGroupBox(tr("project_config.hierarchy_group"))
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(10)

        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.root_list_widget.setMinimumHeight(100)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_root_button = QtWidgets.QPushButton(tr("project_config.add_root_button"))
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)
        self.edit_root_button = QtWidgets.QPushButton(tr("project_config.edit_root_button"))
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)
        self.remove_root_button = QtWidgets.QPushButton(tr("project_config.remove_root_button"))
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)
        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        
        self.modify_category_root_button = QtWidgets.QPushButton(tr("project_config.modify_category_button"))
        self.modify_category_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.modify_category_root_button.clicked.connect(lambda: self._modify_category_for_selected_label("root"))
        self.modify_category_root_button.setEnabled(False)
        root_buttons_layout.addWidget(self.modify_category_root_button)

        hierarchy_group_layout.addLayout(root_buttons_layout)

        parent_label_title = QtWidgets.QLabel(tr("project_config.parent_labels_list_for_root_label"))
        parent_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(parent_label_title)

        self.parent_list_widget = QtWidgets.QListWidget()
        self.parent_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.parent_list_widget.setMinimumHeight(100)
        self.parent_list_widget.currentItemChanged.connect(self._on_parent_label_selected)
        hierarchy_group_layout.addWidget(self.parent_list_widget)

        parent_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_parent_button = QtWidgets.QPushButton(tr("project_config.add_parent_button"))
        self.add_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_parent_button.clicked.connect(self._add_parent_label)
        self.edit_parent_button = QtWidgets.QPushButton(tr("project_config.edit_parent_button"))
        self.edit_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_parent_button.clicked.connect(self._edit_parent_label)
        self.remove_parent_button = QtWidgets.QPushButton(tr("project_config.remove_parent_button"))
        self.remove_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_parent_button.clicked.connect(self._remove_parent_label)
        parent_buttons_layout.addWidget(self.add_parent_button)
        parent_buttons_layout.addWidget(self.edit_parent_button)
        parent_buttons_layout.addWidget(self.remove_parent_button)

        self.modify_category_parent_button = QtWidgets.QPushButton(tr("project_config.modify_category_button"))
        self.modify_category_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.modify_category_parent_button.clicked.connect(lambda: self._modify_category_for_selected_label("parent"))
        self.modify_category_parent_button.setEnabled(False)
        parent_buttons_layout.addWidget(self.modify_category_parent_button)

        hierarchy_group_layout.addLayout(parent_buttons_layout)

        child_label_title = QtWidgets.QLabel(tr("project_config.child_labels_list_label"))
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(child_label_title)
        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.child_list_widget.setMinimumHeight(100)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_child_button = QtWidgets.QPushButton(tr("project_config.add_child_button"))
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)
        self.edit_child_button = QtWidgets.QPushButton(tr("project_config.edit_child_button"))
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)
        self.remove_child_button = QtWidgets.QPushButton(tr("project_config.remove_child_button"))
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)
        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)

        self.modify_category_child_button = QtWidgets.QPushButton(tr("project_config.modify_category_button"))
        self.modify_category_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.modify_category_child_button.clicked.connect(lambda: self._modify_category_for_selected_label("child"))
        self.modify_category_child_button.setEnabled(False)
        child_buttons_layout.addWidget(self.modify_category_child_button)

        hierarchy_group_layout.addLayout(child_buttons_layout)
        hierarchy_group_layout.addStretch()
        hierarchy_layout.addWidget(hierarchy_group)
        hierarchy_layout.addStretch()
        right_column_container.setWidget(hierarchy_scroll_content)
        main_horizontal_layout.addWidget(right_column_container, 17)

        # --- Boutons Enregistrer et Exporter (en bas de la fenêtre, centré) ---
        # These buttons will now be part of this OntologyConfigWidget
        save_export_layout = QtWidgets.QHBoxLayout()
        save_export_layout.addStretch()
        self.save_button = QtWidgets.QPushButton("💾 " + tr("project_config.save_button"))
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False) # Désactivé tant qu'aucun projet sélectionné/créé
        save_export_layout.addWidget(self.save_button)

        self.export_dgraph_button = QtWidgets.QPushButton("⚙️ " + tr("project_config.export_dgraph_button"))
        self.export_dgraph_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_dgraph_button.clicked.connect(self._export_to_dgraph_script)
        self.export_dgraph_button.setEnabled(False) # Désactivé tant qu'aucun projet sélectionné/créé
        save_export_layout.addWidget(self.export_dgraph_button)
        save_export_layout.addStretch()
        main_horizontal_layout.addLayout(save_export_layout) # Add this layout to the main horizontal layout of this widget

        self._update_ui_state() # Initial UI state update

    def refresh(self):
        """Refreshes the data displayed in the ontology configuration tab."""
        logger.debug("Refreshing OntologyConfigWidget...")
        self._load_project_profiles() # Reload all profiles to ensure UI is consistent
        self._update_ui_state() # Update button states based on refreshed data
    
    def _load_project_profiles(self):
        """Loads project profiles from the database."""
        logger.info("Chargement des profils de projet depuis la base de données...")
        try:
            # Correction ici : Utiliser get_all_project_profiles()
            db_projects = self.database.get_all_project_profiles()
            self.project_profiles = {p['name']: p for p in db_projects.values()} # get_all_project_profiles retourne un dict de dicts
            logger.info(f"Projets chargés: {list(self.project_profiles.keys())}")
            self.project_combo.clear()
            if self.project_profiles:
                self.project_combo.addItems(sorted(self.project_profiles.keys()))
                self.project_combo.setCurrentIndex(0) # Select the first one
                self._on_project_selected(0) # Trigger selection logic for the first project
            else:
                self._clear_project_details()
                self._update_ui_state()
        except Exception as e:
            logger.error(f"Erreur lors du chargement des profils de projet: {e}")
            self.project_profiles = {}
            self._clear_project_details()
            self._update_ui_state()

    def _clear_project_details(self):
        self.project_name_edit.clear()
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_project_name = None
        self.current_project_profile_data = None
        self.current_cluster_index = -1
        self.current_cluster_data = None
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

    def _on_project_selected(self, index):
        if index < 0 or not self.project_combo.currentText():
            self._clear_project_details()
            self.delete_project_button.setEnabled(False)
            self._update_ui_state()
            return

        selected_name = self.project_combo.currentText()
        if selected_name in self.project_profiles:
            self.current_project_name = selected_name
            # Créer une copie profonde pour éviter de modifier directement les données chargées
            self.current_project_profile_data = json.loads(json.dumps(self.project_profiles[selected_name]))
            logger.info(f"Projet sélectionné : {self.current_project_name}")
            self._display_current_project_data()
            self.delete_project_button.setEnabled(True)
        else:
            logger.warning(f"Projet '{selected_name}' non trouvé après sélection.")
            self._clear_project_details()
            self.delete_project_button.setEnabled(False)
        self._update_ui_state()

    def _on_child_label_selected(self, current, previous):
        """Gère la sélection d'un label enfant. (Pas de catégories à mettre à jour directement dans l'UI)"""
        if not self.current_project_profile_data or not self.current_cluster_data:
            return

        self.current_child_label_index = self.child_list_widget.currentRow()
        logger.debug(f"Label Enfant sélectionné. Index: {self.current_child_label_index}. Les catégories ne sont plus affichées.")
        self._update_button_states()


    def _display_current_project_data(self):
        if not self.current_project_profile_data:
            self._clear_project_details()
            return

        self.project_name_edit.setText(self.current_project_profile_data.get('name', ''))
        
        # Charger les clusters
        self.cluster_list_widget.clear()
        self.current_cluster_index = -1
        self.current_cluster_data = None
        clusters = self.current_project_profile_data.get('clusters', [])
        for cluster in clusters:
            self.cluster_list_widget.addItem(cluster.get('name', ''))
        
        # Sélectionner le premier cluster si disponible
        if clusters:
            self.cluster_list_widget.setCurrentRow(0)
        else:
            self.root_list_widget.clear()
            self.parent_list_widget.clear()
            self.child_list_widget.clear()

        self._update_ui_state()

    def _on_add_new_project(self):
        project_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                tr("project_config.new_project_title"),
                                                tr("project_config.new_project_text"))
        if ok and project_name:
            project_name = project_name.strip()
            if not project_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return
            if project_name in self.project_profiles:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_project_error").format(name=project_name))
                return
            
            # Créer un nouveau profil vide
            new_profile = {
                "name": project_name,
                "clusters": [],
                "created_at": QtCore.QDateTime.currentDateTime().toString(Qt.ISODate),
                "last_modified": QtCore.QDateTime.currentDateTime().toString(Qt.ISODate)
            }
            self.project_profiles[project_name] = new_profile
            self.current_project_name = project_name
            self.current_project_profile_data = json.loads(json.dumps(new_profile)) # Deep copy
            
            # Ajouter à la combobox et sélectionner
            self.project_combo.addItem(project_name)
            index = self.project_combo.findText(project_name)
            if index != -1:
                self.project_combo.setCurrentIndex(index)
            
            self._display_current_project_data()
            self.delete_project_button.setEnabled(True)
            logger.info(f"Nouveau projet créé : {project_name}")
            self._update_ui_state()

    def _on_delete_project(self):
        if not self.current_project_name:
            return

        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("project_config.delete_project_title"),
                                            tr("project_config.delete_project_confirm").format(name=self.current_project_name),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.database.delete_project_profile(self.current_project_name) # Corrected method call
                if success:
                    logger.info(f"Projet supprimé de la base de données : {self.current_project_name}")
                    del self.project_profiles[self.current_project_name]
                    self.project_combo.removeItem(self.project_combo.currentIndex())
                    self.project_profile_deleted.emit(self.current_project_name)
                    self._clear_project_details() # Clear UI after deletion
                    self._load_project_profiles() # Reload to update combo box and state
                else:
                    QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.delete_project_failed").format(name=self.current_project_name))
                    logger.error(f"Échec de la suppression du projet en DB : {self.current_project_name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.delete_project_error").format(error=str(e)))
                logger.error(f"Erreur lors de la suppression du projet : {e}")
            self._update_ui_state()

    def _update_ui_state(self):
        is_project_selected = self.current_project_name is not None
        self.project_name_edit.setEnabled(is_project_selected)
        self.save_button.setEnabled(is_project_selected)
        self.export_dgraph_button.setEnabled(is_project_selected and self.current_project_profile_data and self.current_project_profile_data.get('clusters'))
        self.add_cluster_button.setEnabled(is_project_selected)
        self.delete_project_button.setEnabled(is_project_selected)

        is_cluster_selected = self.current_cluster_index != -1 and self.current_cluster_data is not None
        self.edit_cluster_button.setEnabled(is_cluster_selected)
        self.remove_cluster_button.setEnabled(is_cluster_selected)
        self.import_folder_button.setEnabled(is_cluster_selected)

        is_root_selected = self.current_root_label_index != -1
        self.edit_root_button.setEnabled(is_root_selected)
        self.remove_root_button.setEnabled(is_root_selected)
        self.modify_category_root_button.setEnabled(is_root_selected)
        self.add_parent_button.setEnabled(is_root_selected) # Can only add parent if root is selected

        is_parent_selected = self.current_parent_label_index != -1
        self.edit_parent_button.setEnabled(is_parent_selected)
        self.remove_parent_button.setEnabled(is_parent_selected)
        self.modify_category_parent_button.setEnabled(is_parent_selected)
        self.add_child_button.setEnabled(is_parent_selected) # Can only add child if parent is selected

        is_child_selected = self.current_child_label_index != -1
        self.edit_child_button.setEnabled(is_child_selected)
        self.remove_child_button.setEnabled(is_child_selected)
        self.modify_category_child_button.setEnabled(is_child_selected)

    def _add_cluster(self):
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_project_selected_cluster"))
            return

        cluster_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        tr("project_config.add_cluster_title"),
                                                        tr("project_config.add_cluster_text"))
        if ok and cluster_name:
            cluster_name = cluster_name.strip()
            if not cluster_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return
            
            existing_clusters = [c.get('name') for c in self.current_project_profile_data.get('clusters', [])]
            if cluster_name in existing_clusters:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_cluster_error").format(name=cluster_name))
                return
            
            new_cluster = {"name": cluster_name, "root_labels": []}
            self.current_project_profile_data.setdefault('clusters', []).append(new_cluster)
            self.cluster_list_widget.addItem(cluster_name)
            self.cluster_list_widget.setCurrentRow(self.cluster_list_widget.count() - 1)
            logger.info(f"Cluster '{cluster_name}' ajouté au projet '{self.current_project_name}'")
            self._update_ui_state()

    def _edit_cluster(self):
        if self.current_cluster_index == -1 or not self.current_cluster_data:
            return

        old_cluster_name = self.current_cluster_data['name']
        new_cluster_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                            tr("project_config.edit_cluster_title"),
                                                            tr("project_config.edit_cluster_text"),
                                                            QtWidgets.QLineEdit.Normal, old_cluster_name)
        if ok and new_cluster_name:
            new_cluster_name = new_cluster_name.strip()
            if not new_cluster_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return
            
            existing_clusters = [c.get('name') for c in self.current_project_profile_data.get('clusters', [])]
            if new_cluster_name in existing_clusters and new_cluster_name != old_cluster_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_cluster_error").format(name=new_cluster_name))
                return

            self.current_cluster_data['name'] = new_cluster_name
            self.cluster_list_widget.currentItem().setText(new_cluster_name)
            logger.info(f"Cluster renommé de '{old_cluster_name}' à '{new_cluster_name}'")
            self._update_ui_state()

    def _remove_cluster(self):
        if self.current_cluster_index == -1:
            return

        cluster_name_to_remove = self.cluster_list_widget.currentItem().text()
        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("project_config.remove_cluster_title"),
                                            tr("project_config.remove_cluster_confirm").format(name=cluster_name_to_remove),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_project_profile_data['clusters'][self.current_cluster_index]
            self.cluster_list_widget.takeItem(self.current_cluster_index)
            self.current_cluster_index = -1
            self.current_cluster_data = None
            self.root_list_widget.clear() # Clear dependent lists
            self.parent_list_widget.clear()
            self.child_list_widget.clear()
            logger.info(f"Cluster '{cluster_name_to_remove}' supprimé du projet '{self.current_project_name}'")
            self._update_ui_state()

    def _on_cluster_selected(self, current, previous):
        self.current_cluster_index = self.cluster_list_widget.currentRow()
        if self.current_cluster_index != -1 and self.current_project_profile_data:
            clusters = self.current_project_profile_data.get('clusters', [])
            if 0 <= self.current_cluster_index < len(clusters):
                self.current_cluster_data = clusters[self.current_cluster_index]
                self._load_root_labels()
            else:
                self.current_cluster_data = None
                self.root_list_widget.clear()
                self.parent_list_widget.clear()
                self.child_list_widget.clear()
        else:
            self.current_cluster_data = None
            self.root_list_widget.clear()
            self.parent_list_widget.clear()
            self.child_list_widget.clear()
        self._update_ui_state()

    def _load_root_labels(self):
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        if self.current_cluster_data:
            root_labels = self.current_cluster_data.get('root_labels', [])
            for label_data in root_labels:
                item_text = label_data.get('label')
                category = label_data.get('category')
                if category:
                    item_text += f" ({category})"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.UserRole, label_data) # Store full data
                self.root_list_widget.addItem(item)
            if root_labels:
                self.root_list_widget.setCurrentRow(0) # Select first root label
            logger.debug(f"Loaded {len(root_labels)} root labels. List widget count: {self.root_list_widget.count()}")
        else:
            logger.debug("No current cluster data to load root labels.")

    def _edit_root_label(self):
        current_item = self.root_list_widget.currentItem()
        if not current_item: return

        old_label_data = current_item.data(Qt.UserRole)
        old_label_name = old_label_data['label']

        new_label_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                            tr("project_config.edit_root_label_title"),
                                                            tr("project_config.edit_root_label_text"),
                                                            QtWidgets.QLineEdit.Normal, old_label_name)
        if ok and new_label_name:
            new_label_name = new_label_name.strip()
            if not new_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return

            existing_labels = [l.get('label') for l in self.current_cluster_data.get('root_labels', [])]
            if new_label_name in existing_labels and new_label_name != old_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_label_error").format(name=new_label_name))
                return
            
            old_label_data['label'] = new_label_name # Update the data dict directly
            item_text = new_label_name
            if old_label_data.get('category'):
                item_text += f" ({old_label_data['category']})"
            current_item.setText(item_text) # Update display
            logger.info(f"Label racine renommé de '{old_label_name}' à '{new_label_name}'")
            self._update_ui_state()

    def _remove_root_label(self):
        current_row = self.root_list_widget.currentRow()
        if current_row == -1 or not self.current_cluster_data: return

        label_to_remove_data = self.root_list_widget.currentItem().data(Qt.UserRole)
        label_name_to_remove = label_to_remove_data['label']

        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("project_config.remove_root_label_title"),
                                            tr("project_config.remove_root_label_confirm").format(name=label_name_to_remove),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data['root_labels'][current_row]
            self.root_list_widget.takeItem(current_row)
            self.current_root_label_index = -1
            self.parent_list_widget.clear()
            self.child_list_widget.clear()
            logger.info(f"Label racine '{label_name_to_remove}' supprimé du cluster '{self.current_cluster_data['name']}'")
            self._update_ui_state()

    def _on_root_label_selected(self, current, previous):
        self.current_root_label_index = self.root_list_widget.currentRow()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        if self.current_root_label_index != -1 and self.current_cluster_data:
            root_labels = self.current_cluster_data.get('root_labels', [])
            if 0 <= self.current_root_label_index < len(root_labels):
                root_label_data = root_labels[self.current_root_label_index]
                parents = root_label_data.get('parents', [])
                for parent_data in parents:
                    item_text = parent_data.get('label')
                    category = parent_data.get('category')
                    if category:
                        item_text += f" ({category})"
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, parent_data)
                    self.parent_list_widget.addItem(item)
                if parents:
                    self.parent_list_widget.setCurrentRow(0) # Select first parent label
                logger.debug(f"Loaded {len(parents)} parent labels. List widget count: {self.parent_list_widget.count()}")
            else:
                logger.debug("Selected root label index out of bounds.")
        else:
            logger.debug("No root label selected or no current cluster data.")
        self._update_ui_state()

    def _add_parent_label(self):
        if self.current_root_label_index == -1 or not self.current_cluster_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_root_selected_parent"))
            return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        label_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        tr("project_config.add_parent_label_title"),
                                                        tr("project_config.add_parent_label_text"))
        if ok and label_name:
            label_name = label_name.strip()
            if not label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return
            
            existing_parents = [p.get('label') for p in root_label_data.get('parents', [])]
            if label_name in existing_parents:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_label_error").format(name=label_name))
                return
            
            new_label_data = {"label": label_name, "category": None, "children": []}
            root_label_data.setdefault('parents', []).append(new_label_data)

            item = QtWidgets.QListWidgetItem(label_name)
            item.setData(Qt.UserRole, new_label_data)
            self.parent_list_widget.addItem(item)
            self.parent_list_widget.setCurrentRow(self.parent_list_widget.count() - 1)
            logger.info(f"Label parent '{label_name}' ajouté au label racine '{root_label_data['label']}'")
            self._update_ui_state()

    def _edit_parent_label(self):
        current_item = self.parent_list_widget.currentItem()
        if not current_item or self.current_root_label_index == -1: return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        old_label_data = current_item.data(Qt.UserRole)
        old_label_name = old_label_data['label']

        new_label_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                            tr("project_config.edit_parent_label_title"),
                                                            tr("project_config.edit_parent_label_text"),
                                                            QtWidgets.QLineEdit.Normal, old_label_name)
        if ok and new_label_name:
            new_label_name = new_label_name.strip()
            if not new_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return

            existing_parents = [p.get('label') for p in root_label_data.get('parents', [])]
            if new_label_name in existing_parents and new_label_name != old_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_label_error").format(name=new_label_name))
                return
            
            old_label_data['label'] = new_label_name
            item_text = new_label_name
            if old_label_data.get('category'):
                item_text += f" ({old_label_data['category']})"
            current_item.setText(item_text)
            logger.info(f"Label parent renommé de '{old_label_name}' à '{new_label_name}'")
            self._update_ui_state()

    def _remove_parent_label(self):
        current_row = self.parent_list_widget.currentRow()
        if current_row == -1 or self.current_root_label_index == -1: return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        label_to_remove_data = self.parent_list_widget.currentItem().data(Qt.UserRole)
        label_name_to_remove = label_to_remove_data['label']

        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("project_config.remove_parent_label_title"),
                                            tr("project_config.remove_parent_label_confirm").format(name=label_name_to_remove),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del root_label_data['parents'][current_row]
            self.parent_list_widget.takeItem(current_row)
            self.current_parent_label_index = -1
            self.child_list_widget.clear()
            logger.info(f"Label parent '{label_name_to_remove}' supprimé du label racine '{root_label_data['label']}'")
            self._update_ui_state()

    def _on_parent_label_selected(self, current, previous):
        self.current_parent_label_index = self.parent_list_widget.currentRow()
        self.child_list_widget.clear()
        self.current_child_label_index = -1

        if self.current_parent_label_index != -1 and self.current_root_label_index != -1 and self.current_cluster_data:
            root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
            parents = root_label_data.get('parents', [])
            if 0 <= self.current_parent_label_index < len(parents):
                parent_label_data = parents[self.current_parent_label_index]
                children = parent_label_data.get('children', [])
                for child_data in children:
                    item_text = child_data.get('label')
                    category = child_data.get('category')
                    if category:
                        item_text += f" ({category})"
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, child_data)
                    self.child_list_widget.addItem(item)
                logger.debug(f"Loaded {len(children)} child labels. List widget count: {self.child_list_widget.count()}")
            else:
                logger.debug("Selected parent label index out of bounds.")
        else:
            logger.debug("No parent label selected or no current root/cluster data.")
        self._update_ui_state()

    def _add_child_label(self):
        if self.current_parent_label_index == -1 or self.current_root_label_index == -1 or not self.current_cluster_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_parent_selected_child"))
            return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        parent_label_data = root_label_data['parents'][self.current_parent_label_index]
        label_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        tr("project_config.add_child_label_title"),
                                                        tr("project_config.add_child_label_text"))
        if ok and label_name:
            label_name = label_name.strip()
            if not label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return
            
            existing_children = [c.get('label') for c in parent_label_data.get('children', [])]
            if label_name in existing_children:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_label_error").format(name=label_name))
                return
            
            new_label_data = {"label": label_name, "category": None}
            parent_label_data.setdefault('children', []).append(new_label_data)

            item = QtWidgets.QListWidgetItem(label_name)
            item.setData(Qt.UserRole, new_label_data)
            self.child_list_widget.addItem(item)
            self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
            logger.info(f"Label enfant '{label_name}' ajouté au label parent '{parent_label_data['label']}'")
            self._update_ui_state()

    def _edit_child_label(self):
        current_item = self.child_list_widget.currentItem()
        if not current_item or self.current_parent_label_index == -1 or self.current_root_label_index == -1: return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        parent_label_data = root_label_data['parents'][self.current_parent_label_index]
        old_label_data = current_item.data(Qt.UserRole)
        old_label_name = old_label_data['label']

        new_label_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                            tr("project_config.edit_child_label_title"),
                                                            tr("project_config.edit_child_label_text"),
                                                            QtWidgets.QLineEdit.Normal, old_label_name)
        if ok and new_label_name:
            new_label_name = new_label_name.strip()
            if not new_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
                return

            existing_children = [c.get('label') for c in parent_label_data.get('children', [])]
            if new_label_name in existing_children and new_label_name != old_label_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_label_error").format(name=new_label_name))
                return
            
            old_label_data['label'] = new_label_name
            item_text = new_label_name
            if old_label_data.get('category'):
                item_text += f" ({old_label_data['category']})"
            current_item.setText(item_text)
            logger.info(f"Label enfant renommé de '{old_label_name}' à '{new_label_name}'")
            self._update_ui_state()

    def _remove_child_label(self):
        current_row = self.child_list_widget.currentRow()
        if current_row == -1 or self.current_parent_label_index == -1 or self.current_root_label_index == -1: return

        root_label_data = self.current_cluster_data['root_labels'][self.current_root_label_index]
        parent_label_data = root_label_data['parents'][self.current_parent_label_index]
        label_to_remove_data = self.child_list_widget.currentItem().data(Qt.UserRole)
        label_name_to_remove = label_to_remove_data['label']

        reply = QtWidgets.QMessageBox.question(self, 
                                            tr("project_config.remove_child_label_title"),
                                            tr("project_config.remove_child_label_confirm").format(name=label_name_to_remove),
                                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del parent_label_data['children'][current_row]
            self.child_list_widget.takeItem(current_row)
            self.current_child_label_index = -1
            logger.info(f"Label enfant '{label_name_to_remove}' supprimé du label parent '{parent_label_data['label']}'")
            self._update_ui_state()

    def _modify_category_for_selected_label(self, label_type):
        current_item = None
        current_label_data = None

        if label_type == "root":
            current_item = self.root_list_widget.currentItem()
            if current_item:
                current_label_data = current_item.data(Qt.UserRole)
        elif label_type == "parent":
            current_item = self.parent_list_widget.currentItem()
            if current_item:
                current_label_data = current_item.data(Qt.UserRole)
        elif label_type == "child":
            current_item = self.child_list_widget.currentItem()
            if current_item:
                current_label_data = current_item.data(Qt.UserRole)
        
        if not current_item or not current_label_data:
            return

        current_category = current_label_data.get('category', '')
        
        # Simpler way to get category from user
        category_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                           tr("project_config.modify_category_dialog_title"),
                                                           tr("project_config.modify_category_dialog_text").format(label=current_label_data['label']),
                                                           QtWidgets.QLineEdit.Normal, current_category)
        if ok:
            category_name = category_name.strip()
            if not category_name:
                # If user clears the category, set it to None
                current_label_data['category'] = None
                logger.info(f"Catégorie supprimée pour '{current_label_data['label']}'.")
            else:
                current_label_data['category'] = category_name
                logger.info(f"Catégorie de '{current_label_data['label']}' définie sur '{category_name}'.")

            # Update the display in the QListWidget
            item_text = current_label_data['label']
            if current_label_data.get('category'):
                item_text += f" ({current_label_data['category']})"
            current_item.setText(item_text)
            self._update_ui_state()

    def _on_save_project(self):
        if not self.current_project_name or not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_project_to_save"))
            return

        # Mettre à jour le nom du projet si modifié dans l'UI
        new_project_name = self.project_name_edit.text().strip()
        if not new_project_name:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.empty_name_error"))
            return
        
        if new_project_name != self.current_project_name:
            if new_project_name in self.project_profiles and new_project_name != self.current_project_name:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), tr("project_config.duplicate_project_error").format(name=new_project_name))
                return
            self.current_project_profile_data['name'] = new_project_name
            old_project_name = self.current_project_name
            self.current_project_name = new_project_name
            logger.info(f"Nom du projet mis à jour de '{old_project_name}' à '{new_project_name}'")
            
        self.current_project_profile_data['last_modified'] = QtCore.QDateTime.currentDateTime().toString(Qt.ISODate)

        try:
            # Sauvegarder le profil de projet dans la base de données via le conductor
            success = self.database.save_project_profile(self.current_project_name, self.current_project_profile_data) # Corrected method call
            if success:
                logger.info(f"Projet '{self.current_project_name}' sauvegardé avec succès dans la base de données.")
                QtWidgets.QMessageBox.information(self, tr("project_config.success_title"), tr("project_config.save_success").format(name=self.current_project_name))
                # Update the internal profiles dict and refresh combo box if name changed
                if old_project_name and old_project_name != self.current_project_name:
                    del self.project_profiles[old_project_name]
                    self.project_combo.removeItem(self.project_combo.findText(old_project_name))
                self.project_profiles[self.current_project_name] = self.current_project_profile_data
                self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
                
                # Refresh combobox if name changed
                if self.project_combo.findText(self.current_project_name) == -1:
                    self.project_combo.addItem(self.current_project_name)
                idx = self.project_combo.findText(self.current_project_name)
                self.project_combo.setCurrentIndex(idx)
                
            else:
                QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.save_failed").format(name=self.current_project_name))
                logger.error(f"Échec de la sauvegarde du projet '{self.current_project_name}' en base de données.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.save_error").format(error=str(e)))
            logger.error(f"Erreur lors de la sauvegarde du projet '{self.current_project_name}': {e}")
        self._update_ui_state()

    def _export_to_dgraph_script(self):
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_project_to_export"))
            return
        
        if not self.current_project_profile_data.get('clusters'):
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_ontology_to_export"))
            return

        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, 
                                                            tr("project_config.export_dgraph_title"),
                                                            f"{self.current_project_name}_dgraph_ontology.py",
                                                            "Python Files (*.py);;All Files (*)")
        if file_name:
            try:
                script_content = self._generate_dgraph_script_content(self.current_project_profile_data)
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                QtWidgets.QMessageBox.information(self, tr("project_config.success_title"), tr("project_config.export_success").format(file=file_name))
                logger.info(f"Script Dgraph exporté avec succès vers : {file_name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.export_error").format(error=str(e)))
                logger.error(f"Erreur lors de l'exportation du script Dgraph : {e}")

    def _generate_dgraph_script_content(self, project_data):
        # This function generates the Python script content for Dgraph import
        # This is a direct copy of the original logic
        script_template = """
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pydgraph
import json
import logging
import os

# Configuration du logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Dgraph connection details
DGRAPH_ADDR = os.getenv("DGRAPH_ADDR", "localhost:9080")

def drop_all(client):
    \"\"\"Drops all data and schema from the Dgraph instance.\"\"\"
    logger.info("Dropping all data and schema...")
    return client.alter(pydgraph.Operation(drop_all=True))

def set_schema(client):
    \"\"\"Sets the Dgraph schema for the ontology.\"\"\"
    logger.info("Setting schema...")
    schema = \"\"\"
    name: string @index(exact) .
    type: string @index(exact) .
    category: string @index(exact) .
    parent: [uid] @reverse .
    child: [uid] .
    cluster_of: uid .
    has_root_label: [uid] .
    has_parent_label: [uid] .
    has_child_label: [uid] .
    is_a: [uid] . # Pour les relations de type "is a" (e.g., chat is_a animal)
    # Plus de prédicats si nécessaire, par exemple pour des propriétés de noeuds
    description: string @index(fulltext) .
    created_at: datetime @index(hour) .
    last_modified: datetime @index(hour) .
    project_name: string @index(exact) .
    \"\"\"
    return client.alter(pydgraph.Operation(schema=schema))

def insert_hierarchy(client, project_data):
    \"\"\"Inserts the ontology hierarchy into Dgraph.\"\"\"
    logger.info(f"Inserting hierarchy for project: {project_data['name']}")
    txn = client.txn()
    try:
        # Créer le nœud Projet
        project_uid = f"_:project_{project_data['name'].replace(' ', '_').lower()}"
        project_mu = {
            "uid": project_uid,
            "name": project_data['name'],
            "type": "Project",
            "project_name": project_data['name'],
            "created_at": project_data.get('created_at'),
            "last_modified": project_data.get('last_modified')
        }
        assigned = txn.mutate(set_obj=project_mu)
        project_uid = assigned.uids['project_uid'] if 'project_uid' in assigned.uids else list(assigned.uids.values())[0]
        logger.info(f"Created Project node with UID: {project_uid}")

        cluster_nodes = {} # Pour stocker les UID des clusters
        
        for cluster_idx, cluster_data in enumerate(project_data.get('clusters', [])):
            cluster_name = cluster_data['name']
            cluster_mu = {
                "uid": f"_:cluster_{cluster_name.replace(' ', '_').lower()}",
                "name": cluster_name,
                "type": "Cluster",
                "cluster_of": {"uid": project_uid} # Lier le cluster au projet
            }
            assigned = txn.mutate(set_obj=cluster_mu)
            current_cluster_uid = assigned.uids['cluster_uid'] if 'cluster_uid' in assigned.uids else list(assigned.uids.values())[0]
            cluster_nodes[cluster_name] = current_cluster_uid
            logger.info(f"Created Cluster '{cluster_name}' with UID: {current_cluster_uid}")

            root_labels_map = {} # Pour mapper les labels racines à leurs UIDs
            
            for root_label_data in cluster_data.get('root_labels', []):
                root_label_name = root_label_data['label']
                root_mu = {
                    "uid": f"_:label_{root_label_name.replace(' ', '_').lower()}",
                    "name": root_label_name,
                    "type": "Label",
                    "category": root_label_data.get('category'),
                    "has_root_label": {"uid": current_cluster_uid} # Lier le label racine au cluster
                }
                assigned = txn.mutate(set_obj=root_mu)
                current_root_uid = assigned.uids['label_uid'] if 'label_uid' in assigned.uids else list(assigned.uids.values())[0]
                root_labels_map[root_label_name] = current_root_uid
                logger.info(f"Created Root Label '{root_label_name}' with UID: {current_root_uid}")
                
                parent_labels_map = {} # Pour mapper les labels parents à leurs UIDs

                for parent_label_data in root_label_data.get('parents', []):
                    parent_label_name = parent_label_data['label']
                    parent_mu = {
                        "uid": f"_:label_{parent_label_name.replace(' ', '_').lower()}",
                        "name": parent_label_name,
                        "type": "Label",
                        "category": parent_label_data.get('category'),
                        "parent": {"uid": current_root_uid}, # Parent est le label racine
                        "has_parent_label": {"uid": current_cluster_uid} # Lier au cluster
                    }
                    assigned = txn.mutate(set_obj=parent_mu)
                    current_parent_uid = assigned.uids['label_uid'] if 'label_uid' in assigned.uids else list(assigned.uids.values())[0]
                    parent_labels_map[parent_label_name] = current_parent_uid
                    logger.info(f"Created Parent Label '{parent_label_name}' with UID: {current_parent_uid}")

                    for child_label_data in parent_label_data.get('children', []):
                        child_label_name = child_label_data['label']
                        child_mu = {
                            "uid": f"_:label_{child_label_name.replace(' ', '_').lower()}",
                            "name": child_label_name,
                            "type": "Label",
                            "category": child_label_data.get('category'),
                            "parent": {"uid": current_parent_uid}, # Parent est le label parent
                            "has_child_label": {"uid": current_cluster_uid} # Lier au cluster
                        }
                        assigned = txn.mutate(set_obj=child_mu)
                        current_child_uid = assigned.uids['label_uid'] if 'label_uid' in assigned.uids else list(assigned.uids.values())[0]
                        logger.info(f"Created Child Label '{child_label_name}' with UID: {current_child_uid}")

        txn.commit()
        logger.info(f"Ontology for project '{project_data['name']}' inserted successfully.")
        logger.info(f"Assigned UIDs: {assigned.uids}")

    except Exception as e:
        logger.error(f"Error importing ontology: {e}")
        try:
            txn.discard()
            logger.info("Transaction discarded.")
        except Exception as discard_e:
            logger.error(f"Error discarding transaction: {discard_e}")
    finally:
        # Ensure transaction is always finalized (committed or discarded)
        try:
            txn.discard()
        except pydgraph.AbortedError:
            pass # Already committed or discarded, ignore error


def main():
    # Project data exported from Liris
    # This data will be dynamically inserted by the script generator
    PROJECT_DATA_PLACEHOLDER
    
    client_stub = pydgraph.DgraphClientStub(DGRAPH_ADDR)
    client = pydgraph.DgraphClient(client_stub)

    logger.info(f"Attempting to connect to Dgraph at {DGRAPH_ADDR}")
    
    # Step 1: Insert the ontology hierarchy
    insert_hierarchy(client, PROJECT_DATA)

if __name__ == '__main__':
    main()
"""
        # Insert the actual project JSON data into the generated script
        project_data_json_str = json.dumps(project_data, indent=4, ensure_ascii=False)
        project_data_formatted = "    PROJECT_DATA = " + project_data_json_str.replace('\n', '\n    ') # Indent for Python code

        script_content = script_template.replace("    PROJECT_DATA_PLACEHOLDER", project_data_formatted)
        return script_content

    def _on_import_directory(self):
        if not self.current_cluster_data:
            QtWidgets.QMessageBox.warning(self, tr("project_config.error_title"), tr("project_config.no_cluster_selected_import"))
            return

        directory = QtWidgets.QFileDialog.getExistingDirectory(self, tr("project_config.select_folder_title"))
        if directory:
            try:
                for root, _, files in os.walk(directory):
                    for file_name in files:
                        # Construct a label from the file path relative to the selected directory
                        relative_path = os.path.relpath(os.path.join(root, file_name), directory)
                        label_from_file = relative_path.replace(os.sep, '/') # Use forward slashes for consistency

                        # Simple heuristic: If it contains slashes, treat the last part as the label
                        # and the path before it as potential parent labels.
                        parts = label_from_file.split('/')
                        if len(parts) == 1: # It's a root label (file directly in the selected folder)
                            # Check if it already exists to avoid duplicates
                            existing_root_labels = [l.get('label') for l in self.current_cluster_data.get('root_labels', [])]
                            if label_from_file not in existing_root_labels:
                                new_label_data = {"label": label_from_file, "category": None, "parents": []}
                                self.current_cluster_data.setdefault('root_labels', []).append(new_label_data)
                                item = QtWidgets.QListWidgetItem(label_from_file)
                                item.setData(Qt.UserRole, new_label_data)
                                self.root_list_widget.addItem(item)
                                logger.info(f"Imported file as root label: {label_from_file}")
                            else:
                                logger.warning(f"Root label '{label_from_file}' already exists, skipping import.")
                        else:
                            # It's a child or grandchild, need to build hierarchy
                            # This simplified example only adds direct children to the last existing parent
                            # A more robust solution would involve recursively creating/finding parents
                            
                            # For simplicity, let's just add the file as a new root label for now
                            # A full hierarchical import would be more complex and require user feedback for mapping
                            logger.warning(f"File '{label_from_file}' is in a subfolder. For hierarchical import, this requires more complex logic. Adding as a new root for now.")
                            existing_root_labels = [l.get('label') for l in self.current_cluster_data.get('root_labels', [])]
                            if label_from_file not in existing_root_labels:
                                new_label_data = {"label": label_from_file, "category": None, "parents": []}
                                self.current_cluster_data.setdefault('root_labels', []).append(new_label_data)
                                item = QtWidgets.QListWidgetItem(label_from_file)
                                item.setData(Qt.UserRole, new_label_data)
                                self.root_list_widget.addItem(item)
                                logger.info(f"Imported file as root label (from subfolder): {label_from_file}")
                            else:
                                logger.warning(f"Root label '{label_from_file}' already exists, skipping import.")

                # Refresh UI after import
                self._load_root_labels() 
                self._update_ui_state()
                QtWidgets.QMessageBox.information(self, tr("project_config.success_title"), tr("project_config.import_success"))

            except Exception as e:
                QtWidgets.QMessageBox.critical(self, tr("project_config.error_title"), tr("project_config.import_error").format(error=str(e)))
                logger.error(f"Erreur lors de l'importation du dossier : {e}")

