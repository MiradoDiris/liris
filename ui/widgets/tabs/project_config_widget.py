import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import sqlite3
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QListWidgetItem, QHBoxLayout, QLabel, QPushButton, QInputDialog
from collections import defaultdict
from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.code_elements_popup import CodeElementsPopup
from utils.progress_dialog import ModernProgressDialog
from utils.multi_language_parser import (
    MultiLanguageDependencyParser, 
    ProjectStructureScanner,
    normalize_node_name,
)
from ui.widgets.tabs.relations_graph_widget import RelationsGraphWidget
from ui.widgets.tabs.add_editItem_dialog import AddEditItemDialog
from ui.widgets.tabs.relations_config import RelationsConfig
from utils.project_storage_manager import ProjectStorageManager
from utils.dgraph_project_manager import DgraphProjectManager
from ui.widgets.dialogs.code_dialogs import CodeDialogs

class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.conductor = conductor
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.db_path = os.path.join("data", "liris.db")
        self.project_storage_manager = ProjectStorageManager(
            parent_widget=self,
            db_path=self.db_path,
            dgraph_connector=self.dgraph_connector
        )
        self.dgraph_manager = DgraphProjectManager(self.dgraph_connector)
        self.project_storage_manager._init_sqlite_db()

        self.local_to_dgraph = {}
        self.dgraph_to_local = {}

        self.dependency_parser = MultiLanguageDependencyParser()
        self.project_scanner = ProjectStructureScanner(self.dependency_parser)
        

        self.project_profiles = {}

        self.structure_scanner = self.project_scanner
        
        self.parsed_relations_cache = {}
        self.file_content_cache = {}

        
        self.current_project_name = None
        self.current_project_profile_data = None

        self.current_cluster_index = -1
        self.current_cluster_data = None

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None

        self.current_level1_label_index = -1
        self.current_level1_is_file = False
        self.current_level1_filename = None

        self.current_level2_label_index = -1
        self.current_level2_is_file = False
        self.current_level2_filename = None

        # Pour les relations
        self.pending_relations = defaultdict(list)
        self.label_uid_to_info = {}
        self.name_to_uid = {}
        self.current_selected_label_uid = None
        self.child_navigation_stack = []

        self.current_child_parent = None

        self.global_relations_config = RelationsConfig(self, "global")
        self.relations_graph = RelationsGraphWidget(self)  # Nouveau widget graphe
        self.code_dialogs = CodeDialogs(self)

        self.setMinimumSize(1400, 900)

        self._init_ui()

        try:
            if self.dgraph_connector.client:
                self.dgraph_manager._load_project_profiles()
                schema = self.dgraph_connector.get_current_schema()

                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse...")
 
            self.project_storage_manager._load_projects_from_sqlite()
            
            # ← NOUVELLE LIGNE :
            self._update_project_combo()
            logger.debug(f"Initialisation : {len(self.project_profiles)} projets affichés")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")
            

    def _on_insert_dgraph_clicked(self):
        """
        ✅ CORRECTION: Prépare et lance l'insertion avec synchronisation correcte
        """
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné pour l'insertion.")
            logger.error("❌ Aucun projet sélectionné pour l'insertion.")
            return

        # ✅ Synchroniser TOUTES les données nécessaires
        self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
        self.dgraph_manager.project_storage_manager = self.project_storage_manager
        self.dgraph_manager.project_profiles = self.project_profiles
        self.dgraph_manager.current_project_name = self.current_project_name
        self.dgraph_manager.label_uid_to_info = self.label_uid_to_info  # ✅ NOUVEAU
        self.dgraph_manager.pending_relations = self.pending_relations  # ✅ NOUVEAU
        self.dgraph_manager.local_to_dgraph = self.local_to_dgraph      # ✅ NOUVEAU
        self.dgraph_manager.dgraph_to_local = self.dgraph_to_local      # ✅ NOUVEAU

        logger.info(f"🔍 Insertion Dgraph demandée pour le projet : {self.current_project_name}")

        # Lancer l'insertion avec ce widget comme parent
        self.dgraph_manager._on_insert_dgraph(self)


    def showEvent(self, event):
        """Maximiser la fenêtre lors de l'affichage"""
        super().showEvent(event)
        if self.window():
            self.window().showMaximized()

    def _get_improved_list_style(self):
        """Style amélioré pour les listes avec sélection gris clair"""
        return """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
                margin: 2px 0px;
                color: #000000;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            QListWidget::item:selected:hover {
                background-color: #d5d5d5;
                color: #000000;
            }
        """

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 3 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(8)
        main_vertical_layout.setContentsMargins(15, 5, 15, 15)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)

        self.label_uid_to_info = {}
        self.pending_relations = defaultdict(list)
        self.current_selected_label_uid = None

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)

        # Groupe sélection projet
        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.setMinimumWidth(200)
        self.project_combo.setMaximumWidth(350)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        # Bouton "Ajouter"
        self.add_project_button = QtWidgets.QPushButton("Ajouter")
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        # Bouton "Supprimer"
        self.delete_project_button = QtWidgets.QPushButton("Supprimer")
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)

        # Bouton "Uploader"
        self.upload_local_button = QtWidgets.QPushButton("📁 Uploader")
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)

        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        # Groupe détails
        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # Layout horizontal pour le nom du projet avec bouton Parcourir
        project_name_widget = QtWidgets.QWidget()
        project_name_layout = QtWidgets.QHBoxLayout(project_name_widget)
        project_name_layout.setContentsMargins(0, 0, 0, 0)
        project_name_layout.setSpacing(8)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setMinimumWidth(200)
        self.project_name_edit.setMaximumWidth(350)
        project_name_layout.addWidget(self.project_name_edit)

        # Bouton Parcourir
        self.browse_button = QtWidgets.QPushButton("Scanner les noeuds")
        self.browse_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.browse_button.setMaximumWidth(120)
        if hasattr(self, '_on_browse_project'):
            self.browse_button.clicked.connect(self._on_browse_project)
        project_name_layout.addWidget(self.browse_button)

        project_name_layout.addStretch()

        details_form_layout.addRow("", project_name_widget)

        self.project_description_edit = QtWidgets.QTextEdit()
        self.project_description_edit.setPlaceholderText("Description du projet...")
        self.project_description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.project_description_edit.setMaximumHeight(80)
        details_form_layout.addRow("Description:", self.project_description_edit)

        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)

        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(self._get_improved_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        self.cluster_list_widget.currentItemChanged.connect(self._on_cluster_selected)
        cluster_list_layout.addWidget(self.cluster_list_widget)

        cluster_buttons_layout = QtWidgets.QHBoxLayout()
        cluster_buttons_layout.setSpacing(5)

        self.add_cluster_button = QtWidgets.QPushButton("Ajouter")
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)

        self.edit_cluster_button = QtWidgets.QPushButton("Modifier")
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)

        self.remove_cluster_button = QtWidgets.QPushButton("Supprimer")
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)

        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
        cluster_buttons_layout.addStretch()
        cluster_list_layout.addLayout(cluster_buttons_layout)

        details_form_layout.addRow(cluster_list_layout)

        left_column_layout.addWidget(details_group)

        details_selected_group = QtWidgets.QGroupBox("Détails sélectionné")
        details_selected_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_selected_layout = QtWidgets.QVBoxLayout(details_selected_group)
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.details_text.setMaximumHeight(400)
        details_selected_layout.addWidget(self.details_text)
        left_column_layout.addWidget(details_selected_group)

        left_column_layout.addStretch()

        top_columns_layout.addLayout(left_column_layout, 4)

        # --- Colonne du milieu: Hiérarchie (largeur augmentée) ---
        middle_scroll = QtWidgets.QScrollArea()
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setStyleSheet("border: none;")

        middle_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(middle_content)
        hierarchy_layout.setSpacing(8)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)

        hierarchy_group = QtWidgets.QGroupBox(tr("project_config.hierarchy_group"))
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(8)

        # 1. Labels Racines
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(self._get_improved_list_style())
        self.root_list_widget.setMinimumHeight(80)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        root_buttons_layout.setSpacing(5)

        self.add_root_button = QtWidgets.QPushButton("Ajouter")
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)

        self.edit_root_button = QtWidgets.QPushButton("Modifier")
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)

        self.remove_root_button = QtWidgets.QPushButton("Supprimer")
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)

        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        root_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(root_buttons_layout)

        # 2. Labels Niveau 1 (anciennement Parents)
        level1_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        level1_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(level1_label_title)

        self.level1_list_widget = QtWidgets.QListWidget()
        self.level1_list_widget.setStyleSheet(self._get_improved_list_style())
        self.level1_list_widget.setMinimumHeight(80)
        self.level1_list_widget.currentItemChanged.connect(self._on_level1_label_selected)
        hierarchy_group_layout.addWidget(self.level1_list_widget)

        level1_buttons_layout = QtWidgets.QHBoxLayout()
        level1_buttons_layout.setSpacing(5)

        self.add_level1_button = QtWidgets.QPushButton("Ajouter")
        self.add_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_level1_button.clicked.connect(self._add_level1_label)

        self.edit_level1_button = QtWidgets.QPushButton("Modifier")
        self.edit_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_level1_button.clicked.connect(self._edit_level1_label)

        self.remove_level1_button = QtWidgets.QPushButton("Supprimer")
        self.remove_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_level1_button.clicked.connect(self._remove_level1_label)

        level1_buttons_layout.addWidget(self.add_level1_button)
        level1_buttons_layout.addWidget(self.edit_level1_button)
        level1_buttons_layout.addWidget(self.remove_level1_button)
        level1_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(level1_buttons_layout)

        # 3. Labels Enfants (Niveau 2)
        child_label_title = QtWidgets.QLabel("Labels enfants")
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(80)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        child_buttons_layout.setSpacing(5)

        self.add_child_button = QtWidgets.QPushButton("Ajouter")
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)

        self.edit_child_button = QtWidgets.QPushButton("Modifier")
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)

        self.remove_child_button = QtWidgets.QPushButton("Supprimer")
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)

        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)
        child_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_layout.addWidget(hierarchy_group)
        middle_scroll.setWidget(middle_content)
        top_columns_layout.addWidget(middle_scroll, 4)

        # --- Colonne de droite: Relations ---
        right_column_layout = QtWidgets.QVBoxLayout()

        # Configuration des Relations en haut
        relations_group = QtWidgets.QGroupBox("Configuration des Relations")
        relations_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        relations_layout.addWidget(self.global_relations_config)
        right_column_layout.addWidget(relations_group)

        # Section graphe des relations
        graph_group = QtWidgets.QGroupBox("Graphe des Relations")
        graph_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        graph_layout = QtWidgets.QVBoxLayout(graph_group)
        graph_layout.addWidget(self.relations_graph)
        graph_group.setMinimumHeight(350)
        right_column_layout.addWidget(graph_group)

        # Boutons de sauvegarde/export/insert en bas
        save_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("💾 Sauvegarder Profil")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False)
        save_layout.addWidget(self.save_button)

        self.export_profile_button = QtWidgets.QPushButton("📤 Exporter Profil")
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(False)
        save_layout.addWidget(self.export_profile_button)

        self.insert_dgraph_button = QtWidgets.QPushButton("🔄 Insérer dans Dgraph")
        self.insert_dgraph_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.insert_dgraph_button.clicked.connect(self._on_insert_dgraph_clicked)
        self.insert_dgraph_button.setEnabled(False)
        save_layout.addWidget(self.insert_dgraph_button)

        right_column_layout.addLayout(save_layout)
        right_column_layout.addStretch()

        top_columns_layout.addLayout(right_column_layout, 5)

        self.level1_list_widget.itemDoubleClicked.connect(self._on_double_click_item)
        self.child_list_widget.itemDoubleClicked.connect(self._on_double_click_item)

    def _get_file_content(self, file_path: str) -> str:
        """
        Récupère le contenu d'un fichier depuis la structure en mémoire ou le disque.
        """
        if not file_path:
            return ""

        # Essayer depuis current_root_data (pour les fichiers ouverts)
        if self.current_root_data:
            content = self.current_root_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Essayer depuis project_profile_data global
        if self.current_project_profile_data:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Fallback : lecture directe du disque
        return self._read_file_content(file_path)  # Méthode existante
    #Interface a ameliorer
    


    def _on_double_click_item(self, item):
        """
        Gère le double-clic sur un item de liste.
        - Pour classes/fonctions/variables : Affiche un snippet du fichier centré sur la ligne.
        - Pour fichiers/labels : Réutilise l'affichage existant (_on_double_click_label).
        """
        if not item:
            return

        item_type = item.data(Qt.UserRole + 1)  # Type stocké (ex. 'class', 'function', 'variable', 'file')

        if item_type in ['class', 'function', 'variable', 'method']:
            # Cas spécifique : snippet pour élément de code
            file_path = item.data(Qt.UserRole + 2)  # Chemin du fichier stocké
            line_num = item.data(Qt.UserRole + 3) or 1  # Numéro de ligne (int)

            # Récupérer le contenu du fichier (depuis current_root_data ou project_profile_data)
            content = self._get_file_content(file_path)
            if not content:
                QtWidgets.QMessageBox.warning(self, "Erreur", f"Impossible de charger le fichier {file_path}.")
                return

            # Extraire et afficher le snippet
            self.code_dialogs._show_code_snippet_dialog(file_path, content, item_type, line_num, item.text())

        elif item_type in ['file', 'root_file', 'level1_file']:
            # Fallback : affichage complet du fichier (comme existant)
            uid = item.data(Qt.UserRole)
            label = self._find_label_by_uid(uid)
            if label:
                self._on_double_click_label(item)  # Réutilise la méthode existante si applicable
            else:
                # Ou directement afficher le fichier
                content = self._get_file_content(file_path)
                if content:
                    self.code_dialogs._show_file_content_dialog(file_path, content, {'label': item.text()})

        else:
            # Pour les dossiers/labels généraux : affichage existant
            self._on_double_click_label(item)

    def _update_project_combo(self):
        """
        CORRECTION: Mise à jour robuste avec gestion d'erreurs
        """
        try:
            logger.info(f"🔄 Mise à jour combo: {len(self.project_profiles)} projet(s)")

            if not hasattr(self, 'project_combo') or self.project_combo is None:
                logger.error("❌ project_combo n'existe pas ou est None!")
                return

            self.project_combo.blockSignals(True)
            current_text = self.project_combo.currentText()
            self.project_combo.clear()

            if not self.project_profiles:
                logger.warning("⚠️ Aucun projet à afficher")
                self.project_combo.addItem("(Aucun projet)")
                self.project_combo.blockSignals(False)
                return

            count = 0
            for name in sorted(self.project_profiles.keys()):
                self.project_combo.addItem(name)
                count += 1
                logger.debug(f"   ✅ Ajouté: {name}")

            self.project_combo.blockSignals(False)
            self.project_combo.update()
            self.project_combo.repaint()

            logger.info(f"✅ Combo mis à jour: {count} projet(s) affiché(s)")

            # Restaurer sélection précédente si possible
            if current_text and current_text != "(Aucun projet)":
                index = self.project_combo.findText(current_text)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                elif count > 0:
                    self.project_combo.setCurrentIndex(0)
                    self._on_project_selected(0)
            elif count > 0 and not self.current_project_name:
                self.project_combo.setCurrentIndex(0)
                self._on_project_selected(0)

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour combo: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet dans la combo."""
        if index < 0:
            return
        project_name = self.project_combo.currentText()
        self.current_project_name = project_name
        self.current_project_profile_data = json.loads(json.dumps(self.project_profiles[project_name]))

        # Restore relations
        pending_relations_data = self.current_project_profile_data.get("pending_relations", {})
        self.pending_relations = defaultdict(list, pending_relations_data)

        # ✅ NOUVEAU : Synchroniser les données avec les widgets enfants
        self.global_relations_config.current_project_profile_data = self.current_project_profile_data
        self.relations_graph.current_project_profile_data = self.current_project_profile_data

        self._load_project_data_into_ui()
        self._update_project_details()
        self._update_button_states()
        self.dgraph_manager._test_relations_loading()

    def _load_project_data_into_ui(self):
        """Charge les données du projet dans l'UI avec réinitialisation complète."""
        if not self.current_project_profile_data:
            return

        # Réinitialiser toute la hiérarchie
        self.current_cluster_data = None
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_cluster_index = -1
        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        # Vider toutes les listes
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Charger les informations de base
        self.project_name_edit.setText(self.current_project_profile_data.get('name', ''))
        self.project_description_edit.setPlainText(self.current_project_profile_data.get('description', ''))

        # Charger uniquement la liste des clusters
        self._refresh_cluster_list()

        # Collecter tous les labels pour les relations
        self._collect_all_labels()

        # Réinitialiser les relations et graphe
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

    def _update_project_details(self):
        """Met à jour les détails du projet sélectionné."""
        if self.current_project_name:
            details = f"Projet: {self.current_project_name}\n"
            details += f"Clusters: {len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []))}\n"
            details += f"Fichiers: {len(self.current_project_profile_data.get('files', []))}"
            self.details_text.setPlainText(details)

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters sans charger les niveaux inférieurs."""
        self.cluster_list_widget.clear()
        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        for cluster in clusters:
            self.cluster_list_widget.addItem(cluster["name"])

    def _on_cluster_selected(self, current):
        """
        Gère la sélection d'un cluster.
        Affiche les root labels + classes/fonctions/variables des fichiers du cluster.
        """
        if not current:
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_index = self.cluster_list_widget.row(current)

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        if self.current_cluster_index < 0 or self.current_cluster_index >= len(clusters):
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_data = clusters[self.current_cluster_index]

        # Réinitialiser niveaux inférieurs
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        # Afficher root labels + éléments de code des fichiers du cluster
        self._populate_root_list_with_cluster_files()

        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Afficher détails
        details = f"Cluster: {self.current_cluster_data.get('name', '')}\n"
        details += f"Description: {self.current_cluster_data.get('description', '')}\n"
        details += f"Root Labels: {len(self.current_cluster_data.get('root_labels', []))}\n"
        details += f"Fichiers: {len(self.current_cluster_data.get('files', []))}\n"
        self.details_text.setPlainText(details)

        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """
        Gère la sélection dans level1_list (fichiers, children OU éléments de code).
        """
        if not current:
            self.current_level1_data = None
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)

        # === CAS 1 : Fichier sélectionné → afficher ses éléments dans child_list ===
        if item_type == 'root_file':
            file_path = current.data(Qt.UserRole + 2)
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            classes = self.dependency_parser.extract_classes(content, file_path)
            functions = self.dependency_parser.extract_functions(content, file_path)
            variables = self.dependency_parser.extract_variables(content, file_path)

            self._display_code_elements_in_list(
                self.child_list_widget,
                classes,
                functions,
                variables,
                file_path
            )

            details = f"📄 Fichier: {os.path.basename(file_path)}\n\n"
            details += f"Classes: {len(classes)}\n"
            details += f"Fonctions: {len(functions)}\n"
            details += f"Variables: {len(variables)}\n"
            self.details_text.setPlainText(details)

            self.current_selected_label_uid = None
            self.current_level1_data = None

        # === CAS 2 : Child sélectionné → afficher ses fichiers + children + éléments ===
        elif item_type in ['folder', 'file', 'child']:
            item_uid = current.data(Qt.UserRole)
            self.current_selected_label_uid = item_uid

            child_data = self._find_child_by_uid(self.current_root_data, item_uid)

            if child_data:
                self.current_level1_data = child_data
                self._update_selected_details("Niveau 1", child_data)

                self._populate_child_list_with_parent_files()

                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)

        # === CAS 3 : Élément de code sélectionné ===
        elif item_type in ['class', 'function', 'variable']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            details = f"Type: {item_type.upper()}\n"
            details += f"Fichier: {os.path.basename(file_path)}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

            self.child_list_widget.clear()

        self._update_button_states()

    def _populate_level1_list(self):
        """
        Peuple TOUS les enfants du root label : 
        - Hiérarchiques (fichiers/dossiers)
        - Extraits (classes/fonctions/variables du fichier racine)
        """
        self.level1_list_widget.clear()
    
        if not self.current_root_data:
            return
    
        # 1. Afficher les enfants hiérarchiques
        for level1 in self.current_root_data.get("children", []):
            child_type = level1.get('type', 'folder')
            icon = self._get_node_icon(child_type)
            display = f"{icon} {level1.get('label', level1.get('name', 'Sans nom'))}"
    
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, level1.get("uid", level1.get("id", "")))
            item.setData(Qt.UserRole + 1, child_type)
            item.setData(Qt.UserRole + 2, None)  # Pas de ligne
            self.level1_list_widget.addItem(item)
    
        # 2. Afficher les classes du root label lui-même
        classes = self.current_root_data.get('classes', [])
        for cls in classes:
            display = f"🛑 {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)
            
            cls_uid = cls.get('uid', f"cls_{str(uuid.uuid4())}")
            if 'uid' not in cls:
                cls['uid'] = cls_uid
            
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            self.level1_list_widget.addItem(item)
    
        # 3. Afficher les fonctions du root label lui-même
        functions = self.current_root_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "⚙️" if func_type == "method" else "🔧"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)
            
            func_uid = func.get('uid', f"func_{str(uuid.uuid4())}")
            if 'uid' not in func:
                func['uid'] = func_uid
            
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            self.level1_list_widget.addItem(item)
    
        # 4. Afficher les variables du root label
        variables = self.current_root_data.get('variables', [])
        for var in variables:
            display = f"📦 {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)
            
            var_uid = var.get('uid', f"var_{str(uuid.uuid4())}")
            if 'uid' not in var:
                var['uid'] = var_uid
            
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            self.level1_list_widget.addItem(item)
    
        self._update_button_states()

    def _add_child_to_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste, récursivement pour les sous-dossiers.
        SANS icônes.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_list(grandchild, list_widget, indent + "  ")

    def _show_code_elements_popup(self, file_name, classes, functions, variables, file_path):
        """
        Affiche une popup avec les classes/fonctions/variables d'un fichier.
        Utilisé pour les fichiers des labels enfants (plus de place dans l'UI).

        Args:
            file_name: Nom du fichier
            classes: Liste des classes
            functions: Liste des fonctions
            variables: Liste des variables
            file_path: Chemin complet du fichier
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Éléments de code : {file_name}")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"<b>Fichier :</b> {file_name}<br><b>Chemin :</b> {file_path}")
        header.setWordWrap(True)
        layout.addWidget(header)

        # Stats
        stats = QLabel(
            f"<b>Classes :</b> {len(classes)} | "
            f"<b>Fonctions :</b> {len(functions)} | "
            f"<b>Variables :</b> {len(variables)}"
        )
        stats.setStyleSheet("color: #34495e; font-size: 11pt; padding: 5px;")
        layout.addWidget(stats)

        # Liste
        list_widget = QListWidget()
        list_widget.setStyleSheet(self._get_improved_list_style())
        self._display_code_elements_in_list(list_widget, classes, functions, variables, file_path)
        layout.addWidget(list_widget)

        # Boutons
        button_layout = QHBoxLayout()

        view_file_button = QPushButton("📄 Voir le fichier")
        view_file_button.clicked.connect(
            lambda: self.code_dialogs._show_file_content_dialog(
                file_name,
                self.current_project_profile_data.get('file_contents', {}).get(file_path, ''),
                {'label': file_name, 'uid': str(uuid.uuid4())}
            )
        )
        button_layout.addWidget(view_file_button)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.exec_()

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        Peuple la liste enfant avec la hiérarchie correcte:
        - Classes (avec sous-items méthodes)
        - Fonctions
        - Variables

        Chaque élément peut être sélectionné pour voir ses relations et détails.
        """
        list_widget.clear()
        if not file_data:
            return

        children = file_data.get('children', [])

        if not children:
            list_widget.addItem(QListWidgetItem("(Aucun élément trouvé)"))
            return

        # Afficher les enfants organisés par type
        for child in children:
            child_type = child.get('type', 'unknown')
            child_uid = child.get('uid')

            if not child_uid:
                child_uid = child.get('id', str(uuid.uuid4()))
                child['uid'] = child_uid

            # === CLASSE ===
            if child_type == 'class':
                icon = '[CLS]'
                class_name = child.get('name', 'Class')
                line_num = child.get('line', '?')
                methods_count = len(child.get('children', []))

                # Format: [CLS] ClassName (3 methods) - line 42
                display = f"{icon} {class_name}"
                if methods_count > 0:
                    display += f" ({methods_count} methods)"
                display += f" - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'class')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#FF9800"))  # Orange
                list_widget.addItem(item)

                # Ajouter les méthodes comme sous-items indentés
                for method in child.get('children', []):
                    method_uid = method.get('uid')
                    if not method_uid:
                        method_uid = str(uuid.uuid4())
                        method['uid'] = method_uid

                    method_name = method.get('name', 'method')
                    method_line = method.get('line', '?')

                    # Indentation pour sous-item
                    method_display = f"  ├─ {method_name} (ligne {method_line})"
                    method_item = QListWidgetItem(method_display)
                    method_item.setData(Qt.UserRole, method_uid)
                    method_item.setData(Qt.UserRole + 1, 'method')
                    method_item.setData(Qt.UserRole + 2, method_line)
                    method_item.setForeground(QtGui.QColor("#FFA500"))  # Orange clair
                    list_widget.addItem(method_item)

            # === FONCTION ===
            elif child_type in ['function', 'method']:
                icon = '[FNC]'
                func_name = child.get('name', 'Function')
                line_num = child.get('line', '?')
                func_type = child.get('type', 'function')

                display = f"{icon} {func_name} - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, func_type)
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#2196F3"))  # Bleu
                list_widget.addItem(item)

            # === VARIABLE ===
            elif child_type == 'variable':
                icon = '[VAR]'
                var_name = child.get('name', 'Variable')
                var_type = child.get('var_type', 'local')
                line_num = child.get('line', '?')

                display = f"{icon} {var_name} ({var_type}) - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'variable')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#4CAF50"))  # Vert
                list_widget.addItem(item)

            # === AUTRES (fichiers, dossiers, etc.) ===
            else:
                icon = self._get_node_icon(child_type)
                child_name = child.get('label', child.get('name', 'unknown'))

                display = f"{icon} {child_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _on_child_label_selected(self, current):
        if not current:
            self.current_level2_data = None
            return

        item_type = current.data(Qt.UserRole + 1)
        item_uid = current.data(Qt.UserRole)

        # === CAS 1 : DOSSIER sélectionné ===
        if item_type in ['folder', 'directory', 'child']:
            folder_data = self._find_child_by_uid(self.current_level1_data, item_uid)

            if folder_data:
                # Sauvegarder l'état actuel dans la pile
                self.child_navigation_stack.append({
                    'parent': self.current_child_parent,
                    'list_items': self._save_list_state(self.child_list_widget)
                })

                # Mettre à jour le parent courant
                self.current_child_parent = folder_data
                self.current_level2_data = folder_data
                self.current_selected_label_uid = item_uid

                # Afficher les enfants du dossier
                self._populate_child_list_for_folder(folder_data)

                # Mettre à jour les détails
                self._update_selected_details("Dossier", folder_data)

                # Mettre à jour relations
                self.global_relations_config.update_current(item_uid)
                self.relations_graph.update_graph(item_uid)

        # === CAS 2 : FICHIER sélectionné ===
        elif item_type == 'level1_file':
            file_path = current.data(Qt.UserRole + 2)
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            if content:
                # Extraire les éléments de code
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)

                # Sauvegarder l'état actuel
                self.child_navigation_stack.append({
                    'parent': self.current_child_parent,
                    'list_items': self._save_list_state(self.child_list_widget)
                })

                # Créer un pseudo-parent pour le fichier
                file_parent = {
                    'label': os.path.basename(file_path),
                    'uid': f"file_{file_path}",
                    'type': 'file',
                    'path': file_path,
                    'classes': classes,
                    'functions': functions,
                    'variables': variables
                }

                self.current_child_parent = file_parent

                # Afficher les éléments de code du fichier
                self._populate_child_list_for_file(file_path, classes, functions, variables)

                # Afficher détails
                details = f"📄 Fichier: {os.path.basename(file_path)}\n\n"
                details += f"Classes: {len(classes)}\n"
                details += f"Fonctions: {len(functions)}\n"
                details += f"Variables: {len(variables)}\n"
                self.details_text.setPlainText(details)

        # === CAS 3 : ÉLÉMENT DE CODE sélectionné ===
        elif item_type in ['class', 'function', 'variable', 'method']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            details = f"Type: {item_type.upper()}\n"
            details += f"Nom: {current.text().split('[')[1].split(']')[1].strip().split('(')[0].strip()}\n"
            details += f"Fichier: {os.path.basename(file_path) if file_path else 'N/A'}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

            self.current_selected_label_uid = item_uid
            self.global_relations_config.update_current(item_uid)
            self.relations_graph.update_graph(item_uid)

        self._update_button_states()
        self._update_navigation_buttons()

    def _populate_child_list_for_file(self, file_path: str, classes: List, functions: List, variables: List):
        self.child_list_widget.clear()

        # Bouton retour
        back_item = QListWidgetItem("⬅️ Retour")
        back_item.setData(Qt.UserRole, 'back_navigation')
        back_item.setData(Qt.UserRole + 1, 'navigation')
        back_item.setForeground(QtGui.QColor("#3498db"))
        back_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.child_list_widget.addItem(back_item)

        # Séparateur
        separator = QListWidgetItem("─" * 50)
        separator.setFlags(separator.flags() & ~Qt.ItemIsSelectable)
        separator.setForeground(QtGui.QColor("#95a5a6"))
        self.child_list_widget.addItem(separator)

        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément de code trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            self.child_list_widget.addItem(empty_item)
            return

        # Afficher les CLASSES
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#e74c3c"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

            # Méthodes indentées
            for method in cls.get('methods', []):
                method_item = QListWidgetItem(f"  ↳ {method.get('name', 'method')} (ligne {method.get('line', '?')})")
                method_item.setData(Qt.UserRole, method.get('uid', str(uuid.uuid4())))
                method_item.setData(Qt.UserRole + 1, 'method')
                method_item.setData(Qt.UserRole + 2, file_path)
                method_item.setData(Qt.UserRole + 3, method.get('line', 0))
                method_item.setForeground(QtGui.QColor("#c0392b"))
                self.child_list_widget.addItem(method_item)

        # Afficher les FONCTIONS
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, func.get('line', 0))
            item.setForeground(QtGui.QColor("#3498db"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

        # Afficher les VARIABLES
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'local')

            item = QListWidgetItem(f"[VAR] {var['name']} ({var_type}, ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, var.get('line', 0))
            item.setForeground(QtGui.QColor("#2ecc71"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

    def _on_child_navigation_back(self):
        if not self.child_navigation_stack:
            if self.current_level1_data:
                self._populate_child_list_with_parent_files()
            self.current_child_parent = None
            self._update_navigation_buttons()
            return

        previous_state = self.child_navigation_stack.pop()
        self.current_child_parent = previous_state['parent']

        self._restore_list_state(self.child_list_widget, previous_state['list_items'])

        self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        is_navigating = bool(self.child_navigation_stack)

        self.add_child_button.setEnabled(not is_navigating and bool(self.current_level1_data))
        self.edit_child_button.setEnabled(not is_navigating and self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(not is_navigating and self.child_list_widget.currentRow() != -1)

    def _restore_list_state(self, list_widget, items):
        list_widget.clear()
        for item_data in items:
            item = QListWidgetItem(item_data['text'])
            item.setData(Qt.UserRole, item_data['uid'])
            item.setData(Qt.UserRole + 1, item_data['type'])
            item.setData(Qt.UserRole + 2, item_data['data2'])
            item.setData(Qt.UserRole + 3, item_data['data3'])
            item.setForeground(QtGui.QColor(item_data['color']))
            list_widget.addItem(item)

    def _setup_child_list_connections(self):
        self.child_list_widget.itemClicked.connect(self._on_child_item_clicked)
        self.child_list_widget.itemDoubleClicked.connect(self._on_double_click_item)

    def _on_child_item_clicked(self, item):
        if not item:
            return

        item_type = item.data(Qt.UserRole + 1)

        if item_type == 'navigation':
            uid = item.data(Qt.UserRole)
            if uid == 'back_navigation':
                self._on_child_navigation_back()
                return

        self._on_child_label_selected(item)

    def _populate_child_list_for_folder(self, folder_data: Dict):
        self.child_list_widget.clear()

        if not folder_data:
            return

        # Bouton retour
        back_item = QListWidgetItem("⬅️ Retour")
        back_item.setData(Qt.UserRole, 'back_navigation')
        back_item.setData(Qt.UserRole + 1, 'navigation')
        back_item.setForeground(QtGui.QColor("#3498db"))
        back_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.child_list_widget.addItem(back_item)

        # Séparateur
        separator = QListWidgetItem("─" * 50)
        separator.setFlags(separator.flags() & ~Qt.ItemIsSelectable)
        separator.setForeground(QtGui.QColor("#95a5a6"))
        self.child_list_widget.addItem(separator)

        # Afficher les enfants
        for child in folder_data.get('children', []):
            child_type = child.get('type', 'folder')
            child_label = child.get('label', child.get('name', 'Sans nom'))
            child_uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = child_uid

            # Icône selon le type
            if child_type == 'file' or child_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net')):
                icon = "📄"
                display_type = 'level1_file'
                color = QtGui.QColor("#7f8c8d")
            elif child_type in ['folder', 'directory']:
                icon = "📁"
                display_type = 'folder'
                color = QtGui.QColor("#f39c12")
            else:
                icon = self._get_node_icon(child_type)
                display_type = child_type
                color = QtGui.QColor("#27ae60")

            display = f"{icon} {child_label}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, child_uid)
            item.setData(Qt.UserRole + 1, display_type)

            # Pour les fichiers, stocker le chemin
            if display_type == 'level1_file':
                file_path = child.get('files', [None])[0] if child.get('files') else None
                item.setData(Qt.UserRole + 2, file_path)

            item.setForeground(color)
            self.child_list_widget.addItem(item)

        if not folder_data.get('children'):
            empty_item = QListWidgetItem("(Dossier vide)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            self.child_list_widget.addItem(empty_item)

    def _save_list_state(self, list_widget):
        items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            items.append({
                'text': item.text(),
                'uid': item.data(Qt.UserRole),
                'type': item.data(Qt.UserRole + 1),
                'data2': item.data(Qt.UserRole + 2),
                'data3': item.data(Qt.UserRole + 3),
                'color': item.foreground().color().name()
            })
        return items

    def _display_code_elements_in_list(self, list_widget, classes, functions, variables, file_path):
        """
        Affiche classes/fonctions/variables dans une liste avec préfixes distinctifs.

        Args:
            list_widget: QListWidget cible
            classes: Liste des classes
            functions: Liste des fonctions
            variables: Liste des variables
            file_path: Chemin du fichier source
        """
        list_widget.clear()

        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            list_widget.addItem(empty_item)
            return

        # === CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#e74c3c"))  # Rouge
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

            # Méthodes indentées
            for method in cls.get('methods', []):
                method_item = QListWidgetItem(f"  ↳ {method.get('name', 'method')} (ligne {method.get('line', '?')})")
                method_item.setData(Qt.UserRole, str(uuid.uuid4()))
                method_item.setData(Qt.UserRole + 1, 'method')
                method_item.setData(Qt.UserRole + 2, method.get('line', 0))
                method_item.setForeground(QtGui.QColor("#c0392b"))
                list_widget.addItem(method_item)

        # === FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#3498db"))  # Bleu
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        # === VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'local')

            item = QListWidgetItem(f"[VAR] {var['name']} ({var_type}, ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#2ecc71"))  # Vert
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        logger.info(f"Affiché {len(classes)} classes, {len(functions)} fonctions, {len(variables)} variables")

    def _on_any_label_selected(self, current):
        """
        Handles selection of ANY label (root, level1, level2, child).
        Updates relations config and graph for the selected node.

        This is a unified handler to avoid code duplication across different
        list widgets.
        """
        if current:
            # Get UID from the selected item
            uid = current.data(Qt.UserRole)

            if not uid:
                logger.warning("Selected item has no UID")
                self.current_selected_label_uid = None
                self.global_relations_config.update_current(None)
                self.relations_graph.update_graph(None)
                return

            self.current_selected_label_uid = uid

            # Update relations config and graph
            self.global_relations_config.update_current(uid)
            self.relations_graph.update_graph(uid)

            logger.debug(f"Label sélectionné: {uid}")
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _on_any_label_selected(self, current):
        """Gère la sélection de n'importe quel label pour relations et graphe."""
        if current:
            self.current_selected_label_uid = current.data(Qt.UserRole)
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _update_selected_details(self, title, data):
        """Met à jour les détails de l'élément sélectionné. Amélioration pour clusters-fichiers."""
        if not data:
            self.details_text.clear()
            return

        is_file_cluster = data.get('is_file_cluster', False)
        if is_file_cluster:
            details = f"=== {title} ===\n\n"
            details += f"Nom: {data.get('name', '')}\n"
            details += f"Description: {data.get('description', '')}\n\n"
            files = data.get('files', [])
            if files:
                details += f"Fichier: {files[0]}\n"  # Un seul fichier pour file-cluster
                content = data.get('file_contents', {}).get(files[0], '')
                details += f"Contenu (résumé): {content[:200]}..." if len(content) > 200 else f"Contenu: {content}"
            else:
                details += "Aucun fichier associé\n"
            # Pas de hiérarchie/relations pour file-cluster
            details += "\nNote: Pas de hiérarchie ni relations pour un cluster-fichier."
            self.details_text.setPlainText(details)
            return

        # Comportement normal pour labels (inchangé)
        details = f"=== {title} ===\n\n"
        details += f"Nom: {data.get('label', '')}\n"
        details += f"ID: {data.get('id', '')}\n"
        details += f"UID: {data.get('uid', '')}\n"
        details += f"Description: {data.get('description', '')}\n\n"

        categories = data.get('category', [])
        if categories:
            details += f"Catégories: {', '.join(categories)}\n\n"

        files = data.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:10]:  # Limiter à 10 fichiers pour l'affichage
                details += f"  - {f}\n"
            if len(files) > 10:
                details += f"  ... et {len(files) - 10} autres\n"
        else:
            details += "Aucun fichier associé\n"

        # Relations sortantes
        outgoing = data.get('outgoing_relations', [])
        if outgoing:
            details += f"\nRelations sortantes ({len(outgoing)}):\n"
            for r in outgoing:
                target_name = self.label_uid_to_info.get(r['target_uid'], {}).get('name', 'Inconnu')
                details += f"  {r['relation_type'].upper()} -> {target_name}\n"

        # Relations entrantes
        incoming = data.get('incoming_relations', [])
        if incoming:
            details += f"\nRelations entrantes ({len(incoming)}):\n"
            for r in incoming:
                source_name = self.label_uid_to_info.get(r['source_uid'], {}).get('name', 'Inconnu')
                details += f"  {source_name} {r['relation_type'].upper()} -> \n"

        # Ajouter info sur la hiérarchie
        if title == "Label Racine":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"
        elif title == "Label Niveau 1":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"

        self.details_text.setPlainText(details)

    def _reset_hierarchy_ui(self):
        """Réinitialise complètement l'interface hiérarchique."""
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

        self.details_text.clear()

    def _collect_all_labels(self):
        """
        CORRECTION: Collecte avec génération systématique d'UIDs
        """
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()

        if not self.current_project_profile_data:
            return

        ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = ontology.get("clusters_detailed", [])

        for cluster in clusters_detailed:
            cluster_name = cluster.get('name', '')
            root_labels = cluster.get("root_labels", [])

            for root in root_labels:
                # ✅ Assurer qu'un UID existe
                if 'uid' not in root or not root['uid']:
                    root['uid'] = root.get('id') or str(uuid.uuid4())

                uid = root['uid']

                info = {
                    'name': root.get('label', ''),
                    'cluster': cluster_name,
                    'type': 'label'
                }
                self.label_uid_to_info[uid] = info
                self.name_to_uid[root.get('label', '')] = uid

                # Collecter récursivement
                self._collect_labels_recursive(root, cluster_name)

    def _collect_labels_recursive(self, node, cluster_name=''):
        """
         CORRECTION: Collecte récursive avec génération d'UIDs
        """
        children = node.get('children', [])

        for child in children:
            # Assurer qu'un UID existe
            if 'uid' not in child or not child['uid']:
                child['uid'] = child.get('id') or str(uuid.uuid4())

            uid = child['uid']

            # Récupérer cluster du parent
            parent_uid = node.get('uid')
            parent_cluster = self.label_uid_to_info.get(parent_uid, {}).get('cluster', cluster_name)

            info = {
                'name': child.get('label', child.get('name', '')),
                'cluster': parent_cluster,
                'type': child.get('type', 'label')
            }
            self.label_uid_to_info[uid] = info

            label_name = child.get('label', child.get('name', ''))
            if label_name:
                self.name_to_uid[label_name] = uid

            # Appel récursif
            self._collect_labels_recursive(child, parent_cluster)

        # Collecter les classes
        for cls in node.get('classes', []):
            if 'uid' not in cls or not cls['uid']:
                cls['uid'] = f"cls_{cls.get('name', '')}_{str(uuid.uuid4())[:8]}"

            cls_uid = cls['uid']

            info = {
                'name': cls.get('name', ''),
                'label': cls.get('name', ''),
                'cluster': cluster_name,
                'type': 'class',
                'parent_label': node.get('label', ''),
                'file': cls.get('file', '')
            }
            self.label_uid_to_info[cls_uid] = info

            cls_name = cls.get('name', '')
            if cls_name:
                self.name_to_uid[cls_name] = cls_uid

        # Collecter les fonctions
        for func in node.get('functions', []):
            if 'uid' not in func or not func['uid']:
                func['uid'] = f"func_{func.get('name', '')}_{str(uuid.uuid4())[:8]}"

            func_uid = func['uid']

            info = {
                'name': func.get('name', ''),
                'label': func.get('name', ''),
                'cluster': cluster_name,
                'type': func.get('type', 'function'),
                'parent_label': node.get('label', ''),
                'file': func.get('file', '')
            }
            self.label_uid_to_info[func_uid] = info

            func_name = func.get('name', '')
            if func_name:
                self.name_to_uid[func_name] = func_uid

        # Collecter les variables
        for var in node.get('variables', []):
            if 'uid' not in var or not var['uid']:
                var['uid'] = f"var_{var.get('name', '')}_{str(uuid.uuid4())[:8]}"

            var_uid = var['uid']

            info = {
                'name': var.get('name', ''),
                'label': var.get('name', ''),
                'cluster': cluster_name,
                'type': 'variable',
                'parent_label': node.get('label', ''),
                'file': var.get('file', '')
            }
            self.label_uid_to_info[var_uid] = info

            var_name = var.get('name', '')
            if var_name:
                self.name_to_uid[var_name] = var_uid

    def _add_cluster(self):
        dialog = AddEditItemDialog("Ajouter Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "files": [],
                    "file_contents": {},
                    "root_labels": []
                }
                self.current_project_profile_data["turing_ontology"]["clusters_detailed"].append(new_cluster)
                self._refresh_cluster_list()
                self._collect_all_labels()
                self.cluster_list_widget.setCurrentRow(self.cluster_list_widget.count() - 1)
                self._update_button_states()
                logger.info(f"Cluster ajouté: {data['name']}")

    def _edit_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
        dialog = AddEditItemDialog("Modifier Cluster", cluster["name"], cluster["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                cluster["name"] = data["name"]
                cluster["description"] = data["description"]
                self._refresh_cluster_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Cluster modifié: {data['name']}")

    def _remove_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster_name = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]["name"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le cluster '{cluster_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
            self._refresh_cluster_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Cluster supprimé: {cluster_name}")

    def _add_root_label(self):
        """Ajoute un label racine avec vérification des fichiers."""
        if not self.current_cluster_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Racine", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_root = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_cluster_data["root_labels"].append(new_root)
                self._populate_root_list()
                self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine ajouté: {data['name']}")

    def _edit_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root = self.current_cluster_data["root_labels"][index]
        dialog = AddEditItemDialog("Modifier Label Racine", root["label"], root["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                root["label"] = data["name"]
                root["description"] = data["description"]
                self._populate_root_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine modifié: {data['name']}")

    def _remove_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root_name = self.current_cluster_data["root_labels"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label racine '{root_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data["root_labels"][index]
            self._populate_root_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label racine supprimé: {root_name}")

    def _add_level1_label(self):
        """Ajoute un label niveau 1 avec vérification des fichiers."""
        if not self.current_root_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 1", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_level1 = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_root_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_root_data["children"].append(new_level1)
                self._populate_level1_list()
                self.level1_list_widget.setCurrentRow(self.level1_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 ajouté: {data['name']}")

    def _edit_level1_label(self):
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1 = self.current_root_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 1", level1["label"], level1["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                level1["label"] = data["name"]
                level1["description"] = data["description"]
                self._populate_level1_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 modifié: {data['name']}")

    def _remove_level1_label(self): 
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1_name = self.current_root_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 1 '{level1_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_root_data["children"][index]
            self._populate_level1_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 1 supprimé: {level1_name}")

    def _add_child_label(self):
        """Ajoute un label enfant avec vérification des fichiers."""
        if not self.current_level1_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 2", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_child = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_level1_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_level1_data["children"].append(new_child)
                self._populate_child_list()
                self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 ajouté: {data['name']}")

    def _edit_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child = self.current_level1_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 2", child["label"], child["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                child["label"] = data["name"]
                child["description"] = data["description"]
                self._populate_child_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 modifié: {data['name']}")

    def _remove_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child_name = self.current_level1_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 2 '{child_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_level1_data["children"][index]
            self._populate_child_list()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 2 supprimé: {child_name}")

    def _add_all_files_from_dir(self, dir_path, base_dir, label, profile):
        """Ajoute récursivement tous les fichiers d'un dossier à un label."""
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                content = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                label['files'].append(rel_path)
                label['file_contents'][rel_path] = content

    def _build_sub_hierarchy(self, dir_path, base_dir, parent_label, is_parents=True, profile=None):
        """Construit la hiérarchie récursivement à partir d'un dossier."""
        level_key = 'children' if is_parents else 'children'
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
            if os.path.isfile(item_path):
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                if profile:
                    profile['files'].append(rel_path)
                    profile['file_contents'][rel_path] = content
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
            elif os.path.isdir(item_path):
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'files': [],
                    'file_contents': {},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
                if is_parents:
                    self._build_sub_hierarchy(item_path, base_dir, new_label, False, profile)
                else:
                    # Pour le niveau children, ajouter les fichiers profonds au label
                    self._add_all_files_from_dir(item_path, base_dir, new_label, profile)

    def _scan_project_directory(self, directory):
        """
        ✅ VERSION CORRIGÉE : Merge avec clusters existants au lieu de dupliquer
        """
        project_name = os.path.basename(directory)

        # ✅ RÉCUPÉRER LE PROFIL EXISTANT (si présent)
        if project_name in self.project_profiles:
            profile = self.project_profiles[project_name]
            logger.info(f"🔄 Mise à jour du projet existant : {project_name}")
        else:
            profile = {
                'name': project_name,
                'description': f"Projet importé depuis {directory}",
                'files': [],
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': {}
            }
            logger.info(f"✅ Création nouveau projet : {project_name}")

        # ✅ CRÉER UN INDEX DES CLUSTERS EXISTANTS
        existing_clusters = {
            cluster['name']: cluster 
            for cluster in profile['turing_ontology']['clusters_detailed']
        }

        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            cluster_name = item

            # ✅ MERGE AU LIEU DE CRÉER UN DOUBLON
            if cluster_name in existing_clusters:
                cluster = existing_clusters[cluster_name]
                logger.info(f"🔄 Mise à jour cluster existant : {cluster_name}")
            else:
                cluster = {
                    'name': cluster_name,
                    'uid': str(uuid.uuid4()),
                    'description': f"{'Fichier' if os.path.isfile(item_path) else 'Dossier'}: {item}",
                    'files': [],
                    'file_contents': {},
                    'root_labels': [],
                    'is_file_cluster': False
                }
                profile['turing_ontology']['clusters_detailed'].append(cluster)
                existing_clusters[cluster_name] = cluster
                logger.info(f"✅ Nouveau cluster : {cluster_name}")

            # === CAS 1 : FICHIER DIRECT ===
            if os.path.isfile(item_path):
                rel_path = item
                content = self._read_file_safe(item_path)

                if rel_path not in profile['files']:
                    profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content

                if rel_path not in cluster['files']:
                    cluster['files'].append(rel_path)
                cluster['file_contents'][rel_path] = content
                cluster['is_file_cluster'] = True

            # === CAS 2 : DOSSIER ===
            elif os.path.isdir(item_path):
                cluster['is_file_cluster'] = False

                # ✅ SCANNER RÉCURSIF (sans dupliquer les labels)
                self._scan_directory_recursive(
                    item_path,
                    directory,
                    cluster,
                    profile,
                    parent_label=None,
                    level=0
                )

        logger.info(f"✅ Scanné {len(profile['files'])} fichiers depuis {directory}")
        return profile
    
    def _scan_directory_recursive(self, dir_path, base_dir, cluster, profile, 
                          parent_label=None, level=0):
        """
        ✅ CORRIGÉ : Évite les doublons de labels dans les scans successifs
        """
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
    
            # === FICHIER ===
            if os.path.isfile(item_path):
                content = self._read_file_safe(item_path)
    
                # ✅ VÉRIFIER SI DÉJÀ EXISTANT (éviter doublon)
                existing_label = None
                search_list = cluster['root_labels'] if parent_label is None else parent_label['children']
                
                for existing in search_list:
                    if existing.get('label') == item or rel_path in existing.get('files', []):
                        existing_label = existing
                        logger.debug(f"🔄 Label existant trouvé : {item}")
                        break
                    
                if existing_label:
                    # ✅ MISE À JOUR DU LABEL EXISTANT
                    if rel_path not in existing_label['files']:
                        existing_label['files'].append(rel_path)
                    existing_label['file_contents'][rel_path] = content
                    continue  # ⚠️ NE PAS CRÉER DE DOUBLON
                
                # Créer le label fichier (nouveau)
                file_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'type': 'file',
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
    
                # Ajouter au profile global
                if rel_path not in profile['files']:
                    profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
    
                # ✅ AJOUT SELON LE NIVEAU (sans doublon)
                if parent_label is None:
                    cluster['root_labels'].append(file_label)
                else:
                    parent_label['children'].append(file_label)
                    file_label['parents'] = [parent_label['uid']]
    
            # === DOSSIER ===
            elif os.path.isdir(item_path):
                # ✅ MÊME LOGIQUE : Vérifier existence avant création
                existing_folder = None
                search_list = cluster['root_labels'] if parent_label is None else parent_label['children']
                
                for existing in search_list:
                    if existing.get('label') == item:
                        existing_folder = existing
                        logger.debug(f"🔄 Dossier existant trouvé : {item}")
                        break
                    
                if existing_folder:
                    # ✅ SCANNER RÉCURSIF DANS LE DOSSIER EXISTANT
                    self._scan_directory_recursive(
                        item_path,
                        base_dir,
                        cluster,
                        profile,
                        parent_label=existing_folder,
                        level=level + 1
                    )
                    continue  # ⚠️ NE PAS CRÉER DE DOUBLON
                
                # Créer le label dossier (nouveau)
                folder_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'type': 'folder',
                    'files': [],
                    'file_contents': {},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
    
                if parent_label is None:
                    cluster['root_labels'].append(folder_label)
                else:
                    parent_label['children'].append(folder_label)
                    folder_label['parents'] = [parent_label['uid']]
    
                # ✅ RÉCURSION
                self._scan_directory_recursive(
                    item_path,
                    base_dir,
                    cluster,
                    profile,
                    parent_label=folder_label,
                    level=level + 1
                )

    def _read_file_safe(self, file_path):
        """
        ✅ Lit un fichier de manière sécurisée avec gestion d'erreurs
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _on_upload_local_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet local")
        if directory:
            scanned_data = self._scan_project_directory(directory)
            project_name = scanned_data['name']
            self.project_profiles[project_name] = json.loads(json.dumps(scanned_data))
            self._update_project_combo()
            self.project_combo.setCurrentText(project_name)
            self._on_project_selected(self.project_combo.currentIndex())
            logger.info(f"Upload local complété pour: {directory}")

    def _on_add_new_project(self):
        """Crée un nouveau projet vide."""
        dialog = AddEditItemDialog("Nouveau Projet", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                project_name = data["name"]
                self.project_profiles[project_name] = {
                    'name': project_name,
                    'description': data["description"],
                    'files': [],
                    'file_contents': {},
                    'turing_ontology': {
                        'clusters_detailed': []
                    },
                    'pending_relations': {}
                }
                self._update_project_combo()
                self.project_combo.setCurrentText(project_name)
                self._on_project_selected(self.project_combo.currentIndex())
                logger.info(f"Nouveau projet créé : {project_name}")

    def _on_delete_project(self):
        """Suppression complète d'un projet depuis l'UI, Dgraph et SQLite."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        project_name = self.project_combo.currentText()
        uid = self.current_project_profile_data.get('uid') if self.current_project_profile_data else None

        if not uid:
            logger.warning(f"Aucun UID trouvé pour le projet {project_name}")
            QtWidgets.QMessageBox.warning(self, "Erreur", f"UID manquant pour '{project_name}'.")
            return

        # Confirmation utilisateur
        reply = QtWidgets.QMessageBox.question(
            self,
            "Suppression du projet",
            f"Voulez-vous vraiment supprimer le projet '{project_name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            uids_to_delete = self._collect_uids_to_delete(uid)
            if not uids_to_delete:
                logger.warning("Aucun UID à supprimer.")
                return

            # Supprimer de Dgraph si disponible
            dgraph_deleted = True
            if self.dgraph_connector.client:
                dgraph_deleted = self._collect_and_delete_uids(uids_to_delete, project_name)

            # Supprimer de SQLite via CRUD
            sqlite_deleted = self.project_storage_manager._delete_project_from_sqlite(uid)

            if dgraph_deleted and sqlite_deleted:
                logger.info(f"Supprimé de Dgraph et SQLite : {project_name}")

                # Supprimer du cache local
                if project_name in self.project_profiles:
                    del self.project_profiles[project_name]
                self._update_project_combo()  # Refresh la combo

                # Reset UI
                self._reset_ui()
                self.current_project_name = None

                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé.")
            else:
                QtWidgets.QMessageBox.warning(self, "Partiel", f"Supprimé de {'Dgraph et ' if dgraph_deleted else ''}SQLite, mais échec sur {'Dgraph' if not dgraph_deleted else 'SQLite'}.")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression : {e}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur : {str(e)}")

    def _collect_uids_to_delete(self, uid):
        """
        ✅ Collecte récursivement tous les UIDs à supprimer liés à un workspace.
        VERSION CORRIGÉE : Sans @recurse
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph client non initialisé.")
            return []
    
        uids_to_delete = set()
    
        # Requête EXPLICITE sans @recurse
        gc_query = f"""
        {{
          workspace(func: uid({uid})) {{
            uid
            clusterManagement {{
              uid
              clusters {{
                uid
                
                # Labels niveau 0
                root_labels: ~clusters @filter(eq(level, 0)) {{
                  uid
                  
                  # Classes
                  classes {{
                    uid
                    methods {{
                      uid
                    }}
                  }}
                  
                  # Fonctions
                  functions {{
                    uid
                  }}
                  
                  # Variables
                  variables {{
                    uid
                  }}
                  
                  # Relations sortantes
                  relations {{
                    uid
                  }}
                  
                  # Relations entrantes
                  ~target {{
                    uid
                  }}
                  
                  # Enfants niveau 1
                  children: ~parents @filter(eq(level, 1)) {{
                    uid
                    
                    classes {{
                      uid
                      methods {{
                        uid
                      }}
                    }}
                    
                    functions {{
                      uid
                    }}
                    
                    variables {{
                      uid
                    }}
                    
                    relations {{
                      uid
                    }}
                    
                    ~target {{
                      uid
                    }}
                    
                    # Enfants niveau 2
                    children: ~parents @filter(eq(level, 2)) {{
                      uid
                      
                      classes {{
                        uid
                      }}
                      
                      functions {{
                        uid
                      }}
                      
                      variables {{
                        uid
                      }}
                      
                      relations {{
                        uid
                      }}
                      
                      ~target {{
                        uid
                      }}
                      
                      # Enfants niveau 3
                      children: ~parents @filter(eq(level, 3)) {{
                        uid
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
    
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp_gc = txn.query(gc_query)
            txn.discard()
    
            data_gc = self.dgraph_connector._parse_response(resp_gc)
            
            def collect_recursive(node):
                """Collecte récursivement les UIDs"""
                if 'uid' in node:
                    uids_to_delete.add(node['uid'])
                
                # Parcourir tous les champs possibles
                for key, value in node.items():
                    if key == 'uid':
                        continue
                    
                    if isinstance(value, dict):
                        collect_recursive(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                collect_recursive(item)
            
            # Collecter depuis la racine
            for ws in data_gc.get('workspace', []):
                collect_recursive(ws)
    
            logger.info(f"✅ {len(uids_to_delete)} UID(s) collecté(s) pour suppression.")
            return list(uids_to_delete)
    
        except Exception as e:
            logger.error(f"❌ Erreur lors de la collecte des UID à supprimer : {e}")
            import traceback
            traceback.print_exc()
            return []

    def _collect_and_delete_uids(self, uids, project_name=None):
        """Supprime les UIDs collectés via mutation DELETE + vérif post-suppression dynamique (non-bloquante)."""
        if not uids or not self.dgraph_connector.client:
            return False

        txn = self.dgraph_connector.client.txn()
        committed = False
        try:
            del_objs = [{"uid": uid} for uid in uids]
            assigned = txn.mutate(del_obj=del_objs)
            txn.commit()
            committed = True
            logger.info(f"Supprimés {len(uids)} nœuds avec succès.")

            # Vérification optionnelle : Dynamique sur le nom du projet
            if project_name:
                try:
                    # Échappement basique pour le regexp (ajustez si noms complexes)
                    escaped_name = project_name.replace('/', '\\/').replace('\\', '\\\\')
                    verify_query = f"""
                    {{
                      q(func: has(name)) @filter(regexp(name, /.*{escaped_name}.*/i)) {{
                        uid
                      }}
                    }}
                    """
                    txn_verify = self.dgraph_connector.client.txn(read_only=True)
                    resp_verify = txn_verify.query(verify_query)
                    txn_verify.discard()
                    data_verify = self.dgraph_connector._parse_response(resp_verify)
                    remaining = len(data_verify.get('q', []))
                    if remaining > 0:
                        logger.warning(f"ATTENTION : {remaining} résidus pour '{project_name}' encore présents après suppression. Relance manuelle recommandée.")
                    else:
                        logger.info(f"Vérification OK : Aucune résidu pour '{project_name}' trouvé.")
                except Exception as ve:
                    logger.warning(f"Vérification post-suppression pour '{project_name}' échouée (non critique) : {ve}. La suppression principale a réussi.")

            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression principale : {e}")
            return False
        finally:
            if not committed:
                txn.discard()

    def _reset_ui(self):
        """Reset l'UI."""
        self.current_project_name = None

        # Appel AVANT le reset des données pour éviter AttributeError
        self._refresh_cluster_list()

        # Maintenant safe de set à None
        self.current_project_profile_data = None
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self._reset_hierarchy_ui()
        self.pending_relations.clear()
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)
        self._update_button_states()

        # Log pour debug
        logger.info("UI reset complété.")

    def _on_save_project(self):
        """Sauvegarde le profil local."""
        if not self.current_project_name:
            return
        self.current_project_profile_data['name'] = self.project_name_edit.text().strip()
        self.current_project_profile_data['description'] = self.project_description_edit.toPlainText().strip()
        self.current_project_profile_data['pending_relations'] = dict(self.pending_relations)
        self.project_profiles[self.current_project_name] = json.loads(json.dumps(self.current_project_profile_data))
        self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
        logger.info(f"Profil sauvegardé : {self.current_project_name}")

    def _on_export_profile(self):
        """Exporte le profil en JSON."""
        if not self.current_project_name:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Profil", f"{self.current_project_name}.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.current_project_profile_data, f, indent=4)
            logger.info(f"Profil exporté : {file_path}")

    def is_configured(self):
        """Vérifie si la config est complète."""
        return (self.current_project_profile_data and
                self.project_name_edit.text().strip() and
                len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])) > 0)




    def _process_hierarchy_recursive(self, node_data, parent_mutation, cluster_uid, 
                                 mutations, label_uids, level):
        """
        Traite récursivement la hiérarchie en créant les mutations.
        Utilise le prédicat 'parents' sur l'enfant pour lier au parent (reverse ~parents).
        """
        children_list = node_data.get('children', [])

        if not children_list:
            return

        parent_uid = parent_mutation["uid"]

        for child_data in children_list:
            # Créer la mutation pour cet enfant
            child_mutation = self.dgraph_manager._create_label_mutation(
                child_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
            mutations.append(child_mutation)

            # Enregistrer l'UID
            label_uids[child_data['uid']] = child_mutation["uid"]

            # Lier au parent via 'parents' sur l'enfant
            if "parents" not in child_mutation:
                child_mutation["parents"] = []
            child_mutation["parents"].append({"uid": parent_uid})

            # Définir le parentId (string)
            child_mutation["parentId"] = node_data.get('uid', '')

            # Traiter récursivement les enfants de cet enfant
            self._process_hierarchy_recursive(
                child_data,
                child_mutation,
                cluster_uid,
                mutations,
                label_uids,
                level + 1
            )

    def _update_button_states(self):
        """Met à jour l'état des boutons en fonction de la sélection."""
        has_project = bool(self.current_project_name)
        self.delete_project_button.setEnabled(has_project)
        self.save_button.setEnabled(has_project)
        self.export_profile_button.setEnabled(has_project)
        self.insert_dgraph_button.setEnabled(has_project and self.is_configured())
    
        has_cluster = bool(self.current_cluster_data)
        self.add_root_button.setEnabled(has_cluster)
        self.edit_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
        self.remove_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
    
        has_root = bool(self.current_root_data)
        self.add_level1_button.setEnabled(has_root)
        self.edit_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.remove_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
    
        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(has_level1)
        self.edit_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(self.child_list_widget.currentRow() != -1)

        # Boutons relations
        has_source = bool(self.current_selected_label_uid)
        self.global_relations_config.add_button.setEnabled(has_source and len(self.label_uid_to_info) > 1)
        has_rel_selected = self.global_relations_config.relations_list.currentRow() != -1
        self.global_relations_config.edit_button.setEnabled(has_rel_selected)
        self.global_relations_config.remove_button.setEnabled(has_rel_selected)

    def _on_browse_project(self):
        """Version avec barre de progression moderne."""
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné")
            return
    
        project_name = self.current_project_profile_data.get("name", "Projet inconnu")
        files = self.current_project_profile_data.get("files", [])
        file_contents = self.current_project_profile_data.get("file_contents", {})
    
        if not files:
            QtWidgets.QMessageBox.warning(
                self, 
                "Aucun fichier trouvé", 
                f"Aucun fichier enregistré pour le projet '{project_name}'."
            )
            return
    
        logger.info(f"🔍 Analyse du projet '{project_name}'...")
    
        # 🎨 CRÉER LE DIALOGUE DE PROGRESSION
        progress = ModernProgressDialog(
            title=f"Analyse du projet : {project_name}",
            parent=self,
            show_log=True,  # Activer le log détaillé
            cancelable=True
        )
        progress.set_title(f"📊 Scan du projet {project_name}")
        progress.set_status(f"Analyse de {len(files)} fichiers...")
        progress.set_progress(0, len(files))
        progress.show()
    
        self.parsed_relations_cache = {}
        files_processed = 0
        files_with_content = 0
        files_with_relations = 0
    
        try:
            for i, file_path in enumerate(files, 1):
                # 🔄 MISE À JOUR DE LA PROGRESSION
                progress.set_progress(i, len(files))
                progress.set_status(f"Traitement du fichier {i}/{len(files)}")
                progress.set_details(f"📄 {os.path.basename(file_path)}")
                progress.add_log(f"[{i}/{len(files)}] Traitement: {file_path}")
                
                QtWidgets.QApplication.processEvents()
    
                # Vérifier annulation
                if progress.is_cancelled:
                    progress.add_log("❌ Opération annulée par l'utilisateur")
                    logger.warning("Scan annulé par l'utilisateur")
                    progress.reject()
                    return
    
                # Récupérer le contenu
                content = file_contents.get(file_path, "")
                
                if content:
                    files_with_content += 1
                    progress.add_log(f"   ✅ Contenu récupéré ({len(content)} chars)")
                else:
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            files_with_content += 1
                            progress.add_log(f"   ✅ Contenu lu depuis disque ({len(content)} chars)")
                        except Exception as e:
                            progress.add_log(f"   ⚠️ Erreur lecture: {e}")
                            logger.warning(f"Impossible de lire {file_path}: {e}")
                            continue
                    else:
                        progress.add_log(f"   ❌ Fichier introuvable sur disque")
                        continue
                    
                if not content:
                    progress.add_log(f"   ⚠️ Contenu vide, skip")
                    continue
                
                # Parser les relations
                parsed_rels = self.dependency_parser.parse_content(content, file_path)
                
                if parsed_rels:
                    total_rels = sum(len(v) for v in parsed_rels.values())
                    progress.add_log(f"   ✅ {total_rels} relations détectées")
                    files_with_relations += 1
                    self.parsed_relations_cache[file_path] = parsed_rels
                else:
                    progress.add_log(f"   ℹ️ Aucune relation détectée")
                
                # Extraire classes/fonctions/variables
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)
                
                progress.add_log(
                    f"   📦 Extraits: {len(classes)} classes, "
                    f"{len(functions)} fonctions, {len(variables)} variables"
                )
    
                # Trouver le label correspondant
                target_label = self._find_label_by_file_path(file_path)
                
                if target_label:
                    # Stocker le dict relations
                    target_label['relations'] = parsed_rels
                    
                    # Intégrer dans outgoing_relations
                    if parsed_rels:
                        self._integrate_parsed_relations_to_label(target_label, parsed_rels, file_path)
                    
                    # Stocker les éléments
                    target_label['classes'] = classes
                    target_label['functions'] = functions
                    target_label['variables'] = variables
                    
                    # Créer les enfants
                    for cls in classes:
                        cls['file'] = file_path
                        if 'uid' not in cls:
                            cls['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(cls, 'class')
                        target_label.setdefault('children', []).append(child)
    
                    for func in functions:
                        func['file'] = file_path
                        if 'uid' not in func:
                            func['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(func, 'function')
                        target_label.setdefault('children', []).append(child)
    
                    for var in variables:
                        var['file'] = file_path
                        if 'uid' not in var:
                            var['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(var, 'variable')
                        target_label.setdefault('children', []).append(child)
                    
                    files_processed += 1
                else:
                    progress.add_log(f"   ⚠️ Aucun label trouvé pour ce fichier")
    
            # Construction du graphe
            progress.set_indeterminate(True)
            progress.set_status("🔗 Construction du graphe de relations...")
            progress.add_log("\n🔗 Construction du graphe de relations...")
            QtWidgets.QApplication.processEvents()
            
            self._build_complete_relations_graph()
            
            progress.set_indeterminate(False)
    
            # Validation
            progress.set_status("🔍 Validation des relations...")
            progress.add_log("🔍 Validation des relations parsées...")
            validation_stats = self._validate_parsed_relations()
    
            # Rafraîchir l'UI
            progress.set_status("♻️ Rafraîchissement de l'interface...")
            progress.add_log("♻️ Rafraîchissement de l'interface...")
            self._collect_all_labels()
            self._refresh_cluster_list()
            
            # Sauvegarde
            progress.set_status("💾 Sauvegarde dans SQLite et Dgraph...")
            progress.add_log("\n💾 Démarrage de la sauvegarde...")
            
            save_success = self._save_scan_results_to_storage()
            
            if save_success:
                progress.finish(
                    success=True,
                    message=f"✅ {files_processed} fichiers traités, "
                            f"{validation_stats['total_parsed_in_dict']} relations détectées"
                )
                progress.add_log("\n✅ Sauvegarde complète réussie!")
            else:
                progress.finish(
                    success=False,
                    message="Le scan a réussi mais la sauvegarde a échoué"
                )
                progress.add_log("\n❌ Échec de la sauvegarde")
    
        except Exception as e:
            logger.error(f"Erreur lors du scan: {str(e)}")
            import traceback
            traceback.print_exc()
            
            progress.finish(
                success=False,
                message=f"Erreur : {str(e)}"
            )
            progress.add_log(f"\n❌ ERREUR: {str(e)}")

    def _create_child_node_from_item(self, item: Dict, item_type: str) -> Dict[str, Any]:
        """
        Crée un nœud enfant à partir d'un élément extrait (classe, fonction, variable).
        
        Args:
            item: Dict de l'élément extrait
            item_type: Type ('class', 'function', 'variable')
        
        Returns:
            Dict du nœud enfant
        """
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'parents': []  # Sera mis à jour si nécessaire
        }
        
        # Ajouter à label_uid_to_info
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_name if hasattr(self, 'current_cluster_name') else 'unknown',
            'file': os.path.basename(item.get('file', ''))
        }
        
        return child

    def _get_local_to_dgraph_mapping(self):
        """Retourne {local_uuid: dgraph_hex}"""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
            self._collect_all_labels()  # Rafraîchir si besoin
        return self.local_to_dgraph

    def _get_dgraph_to_local_mapping(self):
        """Retourne {dgraph_hex: local_uuid}"""
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
            self._collect_all_labels()
        return self.dgraph_to_local

    def _load_mappings_from_dgraph(self):
        """Charge les mappings depuis Dgraph pour sync."""
        query = """
        {
          q(func: type(Node)) {
            uid
            local_id
          }
        }
        """
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self.dgraph_connector._parse_response(resp)
            for node in data.get("q", []):
                local_id = node.get('local_id')
                dgraph_uid = node['uid']
                if local_id:
                    self.local_to_dgraph[local_id] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = local_id
        except Exception as e:
            logger.error(f"Erreur chargement mappings Dgraph: {e}")

    def _load_existing_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Charge la structure existante du projet.
        """
        structure_file = os.path.join(project_path, "turing_ontology.json")
        if os.path.exists(structure_file):
            try:
                with open(structure_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement structure: {e}")
        return {"clusters_detailed": []}    
    
    def _integrate_scanned_structure(self, scanned_structure: Dict[str, Any], base_dir: str):
            """
            Intègre la structure scannée dans le projet, en calculant relations_map à l'intérieur.

            Args:
                scanned_structure: Structure scannée par le scanner
                base_dir: Répertoire de base du projet
            """
            # Calculer relations_map ici pour matcher l'appel (3 args)
            relations_map = self.project_scanner.get_relations_map(scanned_structure)

            clusters_detailed = []
            for cluster in scanned_structure.get('clusters', []):
                new_cluster = {
                    'name': cluster.get('name', 'Unknown'),
                    'path': cluster.get('path', ''),
                    'type': 'cluster',
                    'root_labels': []
                }

                # Traiter chaque fichier avec force
                all_files_in_cluster = self.project_scanner.get_all_files({'clusters': [cluster]})
                for file_info in all_files_in_cluster:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    rel_path = os.path.relpath(file_path, base_dir) if base_dir and file_path else file_path

                    # Contenu déjà lu dans _scan_file, fallback si absent
                    content = file_info.get('file_contents', {}).get(rel_path, '')
                    if not content and file_path:
                        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                        for encoding in encodings:
                            try:
                                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                                    content = f.read()
                                break
                            except (UnicodeDecodeError, IOError):
                                continue
                        else:
                            try:
                                with open(file_path, 'rb') as f:
                                    raw = f.read()
                                    content = raw.decode('utf-8', errors='replace')
                            except Exception:
                                content = ''

                    new_label = {
                        'label': file_name,
                        'id': str(uuid.uuid4()),
                        'uid': file_info.get('uid', str(uuid.uuid4())),
                        'type': 'file',
                        'description': f"Fichier: {rel_path}",
                        'category': ['file'],
                        'files': [rel_path],
                        'file_contents': {rel_path: content},
                        'children': [],
                        'parents': [],
                        'outgoing_relations': [],
                        'incoming_relations': [],
                        'classes': file_info.get('classes', []),  # Forcé depuis scan
                        'functions': file_info.get('functions', []),  # Forcé depuis scan
                        'variables': file_info.get('variables', [])  # Forcé depuis scan
                    }

                    # Ajouter le fichier au projet global
                    files_list = self.current_project_profile_data.get('files', [])
                    if rel_path not in files_list:
                        files_list.append(rel_path)
                        self.current_project_profile_data['files'] = files_list
                    file_contents = self.current_project_profile_data.get('file_contents', {})
                    file_contents[rel_path] = content
                    self.current_project_profile_data['file_contents'] = file_contents

                    # Mapper relations
                    relations = relations_map.get(file_path, {})
                    if relations:
                        for rel_type, rel_list in relations.items():
                            for rel in rel_list:
                                target = rel.get('target', '')
                                normalized_target = normalize_node_name(target)

                                if normalized_target:
                                    target_uid = self._find_label_uid_by_name(normalized_target)

                                    if target_uid:
                                        relation_entry = {
                                            'target_uid': target_uid,
                                            'relation_type': rel_type,
                                            'line': rel.get('line', 0)
                                        }
                                        new_label['outgoing_relations'].append(relation_entry)

                                        pending_rels = self.pending_relations.get(new_label['uid'], [])
                                        pending_rels.append({
                                            'target_uid': target_uid,
                                            'relation_type': rel_type
                                        })
                                        self.pending_relations[new_label['uid']] = pending_rels

                    # Ajouter enfants depuis scan (classes, functions, variables)
                    for child in file_info.get('children', []):
                        if 'uid' not in child:
                            child['uid'] = str(uuid.uuid4())
                        new_label['children'].append(child)

                    new_cluster['root_labels'].append(new_label)

                clusters_detailed.append(new_cluster)

            logger.info(f"{len(clusters_detailed)} clusters intégrés avec classes/fonctions/variables")
            turing_ontology = self.current_project_profile_data.get('turing_ontology', {})
            turing_ontology['clusters_detailed'] = clusters_detailed
            self.current_project_profile_data['turing_ontology'] = turing_ontology

    def _find_label_uid_by_name(self, name: str) -> Optional[str]:
        """
        Trouve l'UID d'un label par son nom (sans extension).
        
        Args:
            name: Nom du label à chercher
        
        Returns:
            UID du label ou None
        """
        if not name:
            return None
        
        normalized_search = name.lower().strip()
        
        for uid, info in self.label_uid_to_info.items():
            label_name = info.get('name', '')
            normalized_label = normalize_node_name(label_name)
            
            if normalized_label and normalized_label.lower() == normalized_search:
                return uid
        
        return None

    def _on_root_label_selected(self, current):
        """
        Gère la sélection dans root_list.
        - Si FICHIER → affiche directement classes/fonctions/variables dans level1_list
        - Si DOSSIER → affiche fichiers + children dans level1_list
        """
        if not current:
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)
        self.current_root_label_index = self.root_list_widget.row(current)

        root_labels = self.current_cluster_data.get("root_labels", [])

        if self.current_root_label_index < 0 or self.current_root_label_index >= len(root_labels):
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        self.current_root_data = root_labels[self.current_root_label_index]
        self.current_selected_label_uid = current.data(Qt.UserRole)

        # 🔍 LOG: Vérifier les relations du fichier sélectionné
        file_name = self.current_root_data.get('label', 'Unknown')
        logger.info(f"📂 Fichier sélectionné: {file_name} (UID: {self.current_selected_label_uid})")
        
        # Log des relations sortantes
        outgoing = self.current_root_data.get('outgoing_relations', [])
        logger.info(f"   → Relations sortantes: {len(outgoing)}")
        for rel in outgoing:
            target_uid = rel.get('target_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            category = rel.get('category', 'unknown')
            target_name = self.label_uid_to_info.get(target_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {rel_type} [{category}] → {target_name} (UID: {target_uid})")
        
        # Log des relations entrantes
        incoming = self.current_root_data.get('incoming_relations', [])
        logger.info(f"   ← Relations entrantes: {len(incoming)}")
        for rel in incoming:
            source_uid = rel.get('source_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            category = rel.get('category', 'unknown')
            source_name = self.label_uid_to_info.get(source_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {source_name} (UID: {source_uid}) {rel_type} [{category}] →")
        
        # Log des relations en attente (pending_relations)
        pending = self.pending_relations.get(self.current_selected_label_uid, [])
        logger.info(f"   ⏳ Relations en attente: {len(pending)}")
        for rel in pending:
            target_uid = rel.get('target_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            target_name = self.label_uid_to_info.get(target_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {rel_type} → {target_name} (UID: {target_uid})")

        # Réinitialiser niveaux inférieurs
        self.current_level1_data = None
        self.current_level2_data = None
        self.child_list_widget.clear()

        # Logique selon le type
        if item_type == 'file':
            # FICHIER : afficher détails + éléments de code directement
            self._update_selected_details("Fichier", self.current_root_data)
            self._populate_level1_with_file_elements(self.current_root_data)
        else:
            # DOSSIER : afficher détails + hiérarchie
            self._update_selected_details("Label Racine", self.current_root_data)
            self._populate_level1_list_with_root_files()

        # Mettre à jour relations
        self.global_relations_config.update_current(self.current_selected_label_uid)
        self.relations_graph.update_graph(self.current_selected_label_uid)

        self._update_button_states()

    def _populate_children_list(self, parent_data: Dict, list_widget=None):
        """
        Corrigée : 
        - Les fichiers .ts/.py/... s'affichent directement avec icône 📄
        - Seuls les sous-dossiers apparaissent comme 📁
        - Plus de double affichage du fichier lors du clic
        """
        if list_widget is None:
            list_widget = (
                self.level1_list_widget
                if hasattr(self, 'current_root_data')
                else self.child_list_widget
            )

        list_widget.clear()
        if not parent_data:
            return

        for child in parent_data.get('children', []):
            child_type = child.get('type', 'child')
            label = child.get('label', child.get('name', 'Sans nom'))
            uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = uid

            # === CAS 1 : Sous-dossier ===
            if child_type in ['folder', 'directory']:
                icon = self._get_node_icon('folder')
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'folder')
                list_widget.addItem(item)

            # === CAS 2 : Fichier ===
            elif child_type == 'file' or label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net')):
                icon = self._get_node_icon('file')
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'file')
                list_widget.addItem(item)

            # === CAS 3 : Éléments de code internes (classe, fonction, variable) ===
            elif child_type in ['class', 'function', 'variable']:
                # Ces éléments ne sont pas affichés ici : ils seront dans la partie inférieure
                continue

            # === Autres types (fallback générique) ===
            else:
                icon = self._get_node_icon(child_type)
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _populate_level1_with_file_elements(self, file_data: Dict):
        """
        Affiche UNIQUEMENT les classes/fonctions/variables d'un fichier dans level1_list.
        PAS de réaffichage du fichier lui-même.

        Args:
            file_data: Dictionnaire du fichier (root_data)
        """
        self.level1_list_widget.clear()

        if not file_data:
            return

        # Récupérer le contenu du fichier
        files = file_data.get('files', [])
        if not files:
            self.level1_list_widget.addItem(QListWidgetItem("(Aucun contenu)"))
            return

        file_path = files[0]  # Fichier principal
        content = file_data.get('file_contents', {}).get(file_path, '')

        if not content:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

        if not content:
            self.level1_list_widget.addItem(QListWidgetItem("(Contenu vide)"))
            return

        # Extraire les éléments de code
        classes = self.dependency_parser.extract_classes(content, file_path)
        functions = self.dependency_parser.extract_functions(content, file_path)
        variables = self.dependency_parser.extract_variables(content, file_path)

        # === Afficher les CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#e74c3c"))  # Rouge
            self.level1_list_widget.addItem(item)

        # === Afficher les FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, func.get('line', 0))
            item.setForeground(QtGui.QColor("#3498db"))  # Bleu
            self.level1_list_widget.addItem(item)

        # === Afficher les VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'variable')

            item = QListWidgetItem(f"[VAR] {var['name']} (ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, var.get('line', 0))
            item.setForeground(QtGui.QColor("#2ecc71"))  # Vert
            self.level1_list_widget.addItem(item)

        # Message si aucun élément trouvé
        if not classes and not functions and not variables:
            self.level1_list_widget.addItem(QListWidgetItem("(Aucun élément de code trouvé)"))

        self._update_button_states()

    def _populate_root_list(self):
        """
        Affiche la liste des root labels avec détection automatique fichier/dossier.
        """
        self.root_list_widget.clear()

        if not self.current_cluster_data:
            return

        for root in self.current_cluster_data.get("root_labels", []):
            root_type = root.get('type', 'folder')
            root_label = root.get('label', root.get('name', 'Sans nom'))

            # Détection automatique : si le label se termine par une extension, c'est un fichier
            is_file = root_type == 'file' or root_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h'))

            if is_file:
                icon = "📄"
                item_type = 'file'
                color = QtGui.QColor("#7f8c8d")
            else:
                icon = "📂"
                item_type = 'root_label'
                color = QtGui.QColor("#2980b9")

            display = f"{icon} {root_label}"
            root_item = QListWidgetItem(display)
            root_item.setData(Qt.UserRole, root.get("uid"))
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)

        self._update_button_states()

    def _get_node_icon(self, node_type: str) -> str:
        """
        Retourne une icône selon le type de nœud.
        ÉTENDU pour supporter class, function, variable.
        """
        icons = {
            'folder': '📁',
            'file': '📄',
            'class': '[CLASS]',
            'function': '[FUNC]',
            'method': '[METH]',
            'variable': '[VAR]',
            'child': '📂'
        }
        return icons.get(node_type, '📦')

    def _get_relation_icon(self, rel_type: str) -> str:
        """
        Retourne une icône selon le type de relation.
        
        Args:
            rel_type: Type de relation
        
        Returns:
            Icône Unicode
        """
        icons = {
            'import': '📦',
            'from_import': '📦',
            'require': '📦',
            'include': '📦',
            'heritage': '🔗',
            'extends': '🔗',
            'implements': '🔗',
            'call': '📞',
            'function_call': '📞',
            'method_call': '📞',
            'uses': '🔹',  # NOUVEAU pour variables
            'variable_use': '🔹'
        }
        
        return icons.get(rel_type, '🔸')

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        MODIFIÉE: Peuple la liste enfant avec les classes, fonctions et variables
        DU FICHIER SÉLECTIONNÉ. Les UIDs sont stockés correctement dans Qt.UserRole.
        """
        list_widget.clear()
        if not file_data:
            return

        # Afficher d'abord les classes du fichier
        classes = file_data.get('classes', [])
        for cls in classes:
            icon = '[CLS]'
            display = f"{icon} {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            cls_uid = cls.get('uid')
            if not cls_uid:
                cls_uid = f"cls_{cls.get('name', '')}_{str(uuid.uuid4())}"
                cls['uid'] = cls_uid

            # Stocker le UID STRING, pas l'ID mémoire
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            list_widget.addItem(item)

        # Afficher les fonctions du fichier
        functions = file_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "[MTH]" if func_type == "method" else "[FNC]"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            func_uid = func.get('uid')
            if not func_uid:
                func_uid = f"func_{func.get('name', '')}_{str(uuid.uuid4())}"
                func['uid'] = func_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            list_widget.addItem(item)

        # Afficher les variables du fichier
        variables = file_data.get('variables', [])
        for var in variables:
            display = f"[VAR] {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            var_uid = var.get('uid')
            if not var_uid:
                var_uid = f"var_{var.get('name', '')}_{str(uuid.uuid4())}"
                var['uid'] = var_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            list_widget.addItem(item)

        # Afficher les enfants hiérarchiques (sous-dossiers/fichiers) APRÈS les classes/foncs/vars
        for child in file_data.get('children', []):
            if child.get('type') in ['folder', 'file', 'child']:
                icon = self._get_node_icon(child.get('type', 'child'))
                display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"
                item = QListWidgetItem(display)

                # Stocker le UID STRING de l'enfant
                child_uid = child.get('uid')
                if not child_uid:
                    child_uid = child.get('id', str(uuid.uuid4()))
                    child['uid'] = child_uid

                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child.get('type', 'child'))
                list_widget.addItem(item)

        self._update_button_states()

    def _format_child_details(self, child: Dict[str, Any]) -> str:
        """
        Formate les détails d'un enfant (classe, fonction, variable) pour affichage.
        """
        child_type = child.get('type', 'unknown')
        details = ""

        if child_type == 'class':
            details = f"=== CLASSE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            bases = child.get('bases', [])
            if bases:
                details += f"\nHérite de:\n"
                for base in bases:
                    details += f"  - {base}\n"

            methods = child.get('children', [])
            if methods:
                details += f"\nMéthodes ({len(methods)}):\n"
                for method in methods[:10]:
                    details += f"  - {method.get('name', 'N/A')} (ligne {method.get('line', '?')})\n"
                if len(methods) > 10:
                    details += f"  ... et {len(methods) - 10} autres\n"

        elif child_type in ['function', 'method']:
            details = f"=== {'MÉTHODE' if child_type == 'method' else 'FONCTION'} ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('type', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            params = child.get('params', [])
            if params:
                details += f"\nParamètres ({len(params)}):\n"
                for param in params:
                    param_name = param.get('name', 'param')
                    param_type = param.get('type', 'unknown')
                    details += f"  - {param_name}: {param_type}\n"

            returns = child.get('returns', {})
            if returns:
                details += f"\nRetour: {returns.get('type', 'N/A')}\n"

            calls = child.get('outgoing_relations', [])
            if calls:
                details += f"\nAppelle ({len(calls)}):\n"
                for call in calls[:5]:
                    details += f"  - {call}\n"
                if len(calls) > 5:
                    details += f"  ... et {len(calls) - 5} autres\n"

        elif child_type == 'variable':
            details = f"=== VARIABLE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('var_type', 'N/A')}\n"
            details += f"Scope: {child.get('scope', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

        return details

    def _get_child_index_by_uid(self, uid: str) -> int:
        """
        Trouve l'index d'un enfant par son UID.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Index ou -1
        """
        if not self.current_root_data:
            return -1
        
        for i, child in enumerate(self.current_root_data.get('children', [])):
            if child.get('uid') == uid:
                return i
        
        return -1

    def _find_label_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un label par son UID dans toute la hiérarchie.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Dictionnaire du label ou None
        """
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)

        return next((n for n in all_nodes if n.get('uid') == uid), None)

    def _find_child_by_uid(self, parent: Dict, uid: str) -> Optional[Dict]:
        """
        Cherche récursivement un enfant par son UID dans la structure.
        """
        for child in parent.get("children", []):
            if child.get('uid') == uid or child.get('id') == uid:
                return child

            # Chercher récursivement dans les sous-dossiers
            result = self._find_child_by_uid(child, uid)
            if result:
                return result

        return None

    def _format_label_details(self, label: Dict[str, Any]) -> str:
        """
        Formate les détails d'un label pour affichage, incluant classes, fonctions et variables.
        
        Args:
            label: Dictionnaire du label
        
        Returns:
            String formaté
        """
        details = f"Nom: {label.get('label', 'N/A')}\n"
        details += f"UID: {label.get('uid', 'N/A')}\n"
        details += f"Type: {label.get('type', 'N/A')}\n"  # NOUVEAU
        details += f"Description: {label.get('description', 'N/A')}\n\n"
        
        files = label.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:5]:
                details += f"  - {f}\n"
            if len(files) > 5:
                details += f"  ... et {len(files) - 5} autres\n"
        
        # Ajouter classes si présentes
        classes = label.get('classes', [])
        if classes:
            details += f"\nClasses ({len(classes)}):\n"
            for cls in classes[:5]:
                details += f"  - {cls['name']} (ligne {cls['line']})\n"
            if len(classes) > 5:
                details += f"  ... et {len(classes) - 5} autres\n"
        
        # Ajouter fonctions si présentes
        functions = label.get('functions', [])
        if functions:
            details += f"\nFonctions/Méthodes ({len(functions)}):\n"
            for func in functions[:5]:
                details += f"  - {func['name']} ({func['type']}, ligne {func['line']})\n"
            if len(functions) > 5:
                details += f"  ... et {len(functions) - 5} autres\n"

        # NOUVEAU : Ajouter variables si présentes
        variables = label.get('variables', [])
        if variables:
            details += f"\nVariables ({len(variables)}):\n"
            for var in variables[:5]:
                details += f"  - {var['name']} ({var['type']}, ligne {var['line']})\n"
            if len(variables) > 5:
                details += f"  ... et {len(variables) - 5} autres\n"
        
        return details

    def _on_double_click_label(self, item):
        """
        Double-clic sur un label - Affiche le contenu du fichier avec snippet highlighté.
        MODIFIÉ: Centré sur ligne pour classes/foncs/vars.
        """
        if not item:
            return
        
        uid = item.data(Qt.UserRole)
        label = self._find_label_by_uid(uid)
        
        if not label:
            return
        
        files = label.get('files', [])
        if not files:
            QtWidgets.QMessageBox.information(
                self,
                "Aucun fichier",
                "Ce label n'a pas de fichier associé."
            )
            return
        
        # Si plusieurs fichiers, demander lequel afficher
        file_to_show = files[0]
        if len(files) > 1:
            file_to_show, ok = QInputDialog.getItem(
                self,
                "Sélectionner un fichier",
                "Fichier à afficher:",
                files,
                0,
                False
            )
            if not ok:
                return
        
        # Récupérer le contenu
        content = label.get('file_contents', {}).get(file_to_show, '')
        
        if not content:
            QtWidgets.QMessageBox.warning(
                self,
                "Contenu vide",
                f"Le fichier {file_to_show} est vide."
            )
            return
        
        # Afficher dans une fenêtre de dialogue avec highlight
        self.code_dialogs._show_file_content_dialog(file_to_show, content, label)

    def _read_file_content(self, file_path: str) -> str:
        """Lit un fichier en UTF-8 avec gestion d’erreur."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _add_child_to_level1_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste niveau 1, récursivement pour les sous-dossiers.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant SANS icône
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_level1_list(grandchild, list_widget, indent + "  ")

    def _populate_cluster_list(self):
        """
        CORRIGÉ : Affiche UNIQUEMENT les clusters (pas leurs fichiers).
        """
        self.cluster_list_widget.clear()

        if not self.current_project_profile_data:
            return

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])

        for cluster in clusters:
            cluster_item = QListWidgetItem(f"📁 {cluster['name']}")
            cluster_item.setData(Qt.UserRole, cluster['uid'])
            cluster_item.setData(Qt.UserRole + 1, 'cluster')
            cluster_item.setForeground(QtGui.QColor("#2c3e50"))
            self.cluster_list_widget.addItem(cluster_item)

    def _populate_root_list_with_cluster_files(self):   
        """
        Affiche dans root_list :
        1. Les root labels du cluster (fichiers ET dossiers détectés automatiquement)
        """
        self.root_list_widget.clear()
    
        if not self.current_cluster_data:
            return
    
        # Afficher tous les root labels avec détection automatique
        for root in self.current_cluster_data.get("root_labels", []):
            root_label = root.get('label', root.get('name', 'Sans nom'))
            root_uid = root.get("uid")
            
            # Détection automatique par extension OU par type
            root_type = root.get('type', 'folder')
            is_file = (
                root_type == 'file' or 
                root_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h', '.tsx', '.jsx'))
            )
            
            if is_file:
                # C'est un fichier
                icon = "📄"
                item_type = 'file'
                color = QtGui.QColor("#7f8c8d")
            else:
                # C'est un dossier
                icon = "📂"
                item_type = 'root_label'
                color = QtGui.QColor("#2980b9")
            
            display = f"{icon} {root_label}"
            root_item = QListWidgetItem(display)
            root_item.setData(Qt.UserRole, root_uid)
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)
    
        self._update_button_states()

    def _populate_level1_list_with_root_files(self):
        """
        Affiche dans level1_list (pour les DOSSIERS uniquement) :
        1. Les fichiers du root label avec icône fichier
        2. Les children (sous-dossiers) du root label

        NE PAS afficher les classes/fonctions/variables ici (réservé aux fichiers directs)
        """
        self.level1_list_widget.clear()

        if not self.current_root_data:
            return

        # 1. Afficher les FICHIERS du root label
        for file_path in self.current_root_data.get('files', []):
            file_name = os.path.basename(file_path)
            file_item = QListWidgetItem(f"📄 {file_name}")
            file_item.setData(Qt.UserRole, f"root_file_{file_path}")
            file_item.setData(Qt.UserRole + 1, 'root_file')
            file_item.setData(Qt.UserRole + 2, file_path)
            file_item.setForeground(QtGui.QColor("#7f8c8d"))
            self.level1_list_widget.addItem(file_item)

        # 2. Afficher les CHILDREN (sous-dossiers/fichiers hiérarchiques)
        for child in self.current_root_data.get("children", []):
            child_type = child.get('type', 'folder')

            # SKIP les éléments de code (ils seront affichés via les fichiers)
            if child_type in ['class', 'function', 'variable', 'method']:
                continue
            
            # Déterminer l'icône selon le type
            if child_type == 'file' or child.get('label', '').endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net')):
                icon = "📄"
                display_type = 'file'
            else:
                icon = self._get_node_icon(child_type)
                display_type = child_type

            display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, child.get("uid"))
            item.setData(Qt.UserRole + 1, display_type)
            item.setForeground(QtGui.QColor("#16a085"))
            self.level1_list_widget.addItem(item)

        self._update_button_states()

    def _populate_child_list_with_parent_files(self):
        """
        Affiche dans child_list :
        1. Les fichiers du parent label
        2. Les children du parent label
        3. Les classes/fonctions/variables des fichiers du parent label
        """
        self.child_list_widget.clear()

        if not self.current_level1_data:
            return

        # 1. Afficher les fichiers
        for file_path in self.current_level1_data.get('files', []):
            file_name = os.path.basename(file_path)
            file_item = QListWidgetItem(f"📄 {file_name}")
            file_item.setData(Qt.UserRole, f"level1_file_{file_path}")
            file_item.setData(Qt.UserRole + 1, 'level1_file')
            file_item.setData(Qt.UserRole + 2, file_path)
            file_item.setForeground(QtGui.QColor("#7f8c8d"))
            self.child_list_widget.addItem(file_item)

        # 2. Afficher les children hiérarchiques
        for child in self.current_level1_data.get("children", []):
            child_type = child.get('type', 'folder')

            if child_type in ['class', 'function', 'variable', 'method']:
                continue
            
            icon = self._get_node_icon(child_type)
            display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, child.get("uid"))
            item.setData(Qt.UserRole + 1, child_type)
            item.setForeground(QtGui.QColor("#27ae60"))
            self.child_list_widget.addItem(item)

        # 3. Afficher les éléments de code des fichiers du parent label
        parent_files = self.current_level1_data.get('files', [])
        file_contents = self.current_level1_data.get('file_contents', {})

        for file_path in parent_files:
            content = file_contents.get(file_path, '')
            if not content:
                content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            if content:
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)

                # Ajouter classes
                for cls in classes:
                    item = QListWidgetItem(f"[CLASS] {cls['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, cls.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'class')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, cls.get('line', 0))
                    item.setForeground(QtGui.QColor("#e74c3c"))
                    self.child_list_widget.addItem(item)

                # Ajouter fonctions
                for func in functions:
                    item = QListWidgetItem(f"[FUNC] {func['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, func.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'function')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, func.get('line', 0))
                    item.setForeground(QtGui.QColor("#3498db"))
                    self.child_list_widget.addItem(item)

                # Ajouter variables
                for var in variables:
                    item = QListWidgetItem(f"[VAR] {var['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, var.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'variable')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, var.get('line', 0))
                    item.setForeground(QtGui.QColor("#2ecc71"))
                    self.child_list_widget.addItem(item)

    def _integrate_parsed_relations_to_node(self, node: Dict, parsed_relations: Dict, node_type: str):
        """
        Intègre les relations parsées (import, extends, calls, uses) au nœud.

        Args:
            node: Nœud cible (classe, fonction, variable)
            parsed_relations: Dict avec clés 'import', 'heritage', 'call', 'uses'
            node_type: Type du nœud ('class', 'function', 'variable')
        """
        if not parsed_relations:
            return

        # Pour les CLASSES : les héritages (extends)
        if node_type == 'class':
            for base_rel in parsed_relations.get('heritage', []):
                target_name = base_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'extends',
                            'category': 'parsed',
                            'line': base_rel.get('line', 0)
                        })

            # Usages de variables par la classe
            for use_rel in parsed_relations.get('uses', []):
                target_name = use_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'uses',
                            'category': 'parsed',
                            'line': use_rel.get('line', 0)
                        })

        # Pour les FONCTIONS : les appels (calls)
        elif node_type == 'function':
            for call_rel in parsed_relations.get('call', []):
                target_name = call_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'calls',
                            'category': 'parsed',
                            'line': call_rel.get('line', 0)
                        })

        # Pour les FICHIERS (root_labels) : imports
        if 'import' in parsed_relations:
            for import_rel in parsed_relations['import']:
                target_name = import_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'import',
                            'category': 'parsed',
                            'line': import_rel.get('line', 0)
                        })

    def _validate_parsed_relations(self):
        """
        Méthode de debug pour vérifier que les relations parsées sont bien présentes.
        """
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)

        stats = {
            'nodes_with_relations_dict': 0,
            'nodes_with_outgoing': 0,
            'total_parsed_in_dict': 0,
            'total_parsed_in_outgoing': 0
        }

        for node in all_nodes:
            node_name = node.get('label', node.get('name', 'Unknown'))

            # Vérifier dict 'relations'
            relations_dict = node.get('relations', {})
            if relations_dict:
                stats['nodes_with_relations_dict'] += 1
                for rel_type, rel_list in relations_dict.items():
                    stats['total_parsed_in_dict'] += len(rel_list)
                    logger.debug(f"  {node_name} - relations['{rel_type}']: {len(rel_list)} items")

            # Vérifier outgoing_relations
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                stats['nodes_with_outgoing'] += 1
                parsed_out = [r for r in outgoing if r.get('category') == 'parsed']
                stats['total_parsed_in_outgoing'] += len(parsed_out)
                if parsed_out:
                    logger.debug(f"  {node_name} - outgoing_relations (parsed): {len(parsed_out)}")

        logger.info(f"\n📊 VALIDATION RELATIONS PARSÉES:")
        logger.info(f"  Nœuds avec 'relations' dict: {stats['nodes_with_relations_dict']}")
        logger.info(f"  Nœuds avec outgoing_relations: {stats['nodes_with_outgoing']}")
        logger.info(f"  Total relations dans dict: {stats['total_parsed_in_dict']}")
        logger.info(f"  Total relations parsées dans outgoing: {stats['total_parsed_in_outgoing']}")

        return stats

    def _find_label_by_file_path(self, file_path: str) -> Optional[Dict]:
        """
        Trouve le label correspondant à un fichier dans la structure.
        """
        if not self.current_project_profile_data:
            return None

        file_name = os.path.basename(file_path)

        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            for root_label in cluster.get('root_labels', []):
                # Vérifier si c'est le bon label
                if root_label.get('label') == file_name:
                    return root_label

                # Chercher dans les fichiers du label
                if file_path in root_label.get('files', []):
                    return root_label

                # Chercher récursivement dans les enfants
                result = self._find_label_in_children(root_label, file_path, file_name)
                if result:
                    return result

        return None
    
    def _find_label_in_children(self, parent: Dict, file_path: str, file_name: str) -> Optional[Dict]:
        """Cherche récursivement un label par fichier."""
        for child in parent.get('children', []):
            if child.get('label') == file_name or file_path in child.get('files', []):
                return child

            result = self._find_label_in_children(child, file_path, file_name)
            if result:
                return result

        return None

    def _integrate_parsed_relations_to_label(self, label: Dict, parsed_relations: Dict, file_path: str):

        label_uid = label.get('uid')
        if not label_uid:
            return

        # Récupérer les infos complètes du label source
        source_info = {
            'uid': label_uid,
            'name': label.get('label', label.get('name', '')),
            'description': label.get('description', ''),
            'path': label.get('path', file_path),
            'type': label.get('type', 'file')
        }

        for rel_type, rel_list in parsed_relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                if not target_name:
                    continue
                
                # Normaliser le nom de la cible
                normalized_target = normalize_node_name(target_name)
                if not normalized_target:
                    continue
                
                # Essayer de trouver l'UID de la cible
                target_uid = self._find_label_uid_by_name(normalized_target)

                # ✅ RÉCUPÉRER LES INFOS COMPLÈTES DE LA CIBLE
                if target_uid and target_uid in self.label_uid_to_info:
                    target_info = self.label_uid_to_info[target_uid]
                    target_data = {
                        'uid': target_uid,
                        'name': target_info.get('name', target_name),
                        'description': target_info.get('label', ''),
                        'path': target_info.get('file', ''),
                        'type': target_info.get('type', 'unknown')
                    }
                else:
                    # Si pas trouvé, créer un UID temporaire avec infos minimales
                    target_uid = f"temp_{normalized_target}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': target_uid,
                        'name': target_name,
                        'description': f"Unresolved: {target_name}",
                        'path': '',
                        'type': 'unresolved'
                    }
                    logger.debug(f"UID temporaire créé pour {normalized_target}: {target_uid}")

                # ✅ CRÉER L'ENTRÉE DE RELATION ENRICHIE
                relation_entry = {
                    # Target info
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],

                    # Source info
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],

                    # Relation metadata
                    'relation_type': rel_type,
                    'category': 'parsed',
                    'line': rel.get('line', 0),
                    'intra_file': rel.get('intra_file', False)
                }

                # Ajouter à outgoing_relations si pas déjà présent
                outgoing = label.setdefault('outgoing_relations', [])
                if not any(r['target_uid'] == target_data['uid'] and r['relation_type'] == rel_type for r in outgoing):
                    outgoing.append(relation_entry)
                    logger.debug(f"Relation enrichie ajoutée: {source_info['name']} --{rel_type}--> {target_data['name']}")

                # Ajouter aussi aux pending_relations pour synchronisation Dgraph
                pending = self.pending_relations.get(label_uid, [])
                pending_entry = {
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'relation_type': rel_type
                }
                if pending_entry not in pending:
                    pending.append(pending_entry)
                    self.pending_relations[label_uid] = pending

    def _create_child_node_from_extracted(self, item: Dict, item_type: str) -> Dict:
        """
        ✅ CORRIGÉ : Crée un nœud enfant avec relations enrichies
        """
        uid = item.get('uid', str(uuid.uuid4()))
        
        # Récupérer infos du fichier parent
        file_path = item.get('file', '')
        
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'path': file_path,
            'description': item.get('description', f"{item_type} {item['name']} at line {item.get('line', 0)}"),
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': [],
            'parents': []
        }
    
        # ✅ Infos source complètes
        source_info = {
            'uid': uid,
            'name': item['name'],
            'description': child['description'],
            'path': file_path,
            'type': item_type
        }
    
        if item_type == 'class':
            # Héritage (bases)
            for base_name in item.get('bases', []):
                base_uid = self._find_label_uid_by_name(normalize_node_name(base_name))
                
                # ✅ Récupérer infos complètes de la base
                if base_uid and base_uid in self.label_uid_to_info:
                    base_info = self.label_uid_to_info[base_uid]
                    target_data = {
                        'uid': base_uid,
                        'name': base_info.get('name', base_name),
                        'description': base_info.get('label', ''),
                        'path': base_info.get('file', ''),
                        'type': base_info.get('type', 'class')
                    }
                else:
                    base_uid = f"temp_class_{base_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': base_uid,
                        'name': base_name,
                        'description': f"Base class: {base_name}",
                        'path': '',
                        'type': 'class'
                    }
    
                child['outgoing_relations'].append({
                    # Target
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    
                    # Source
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    
                    # Metadata
                    'relation_type': 'extends',
                    'category': 'parsed'
                })
    
            # Usages de variables (même pattern)
            for var_name in item.get('uses_vars', []):
                var_uid = self._find_label_uid_by_name(normalize_node_name(var_name))
                
                if var_uid and var_uid in self.label_uid_to_info:
                    var_info = self.label_uid_to_info[var_uid]
                    target_data = {
                        'uid': var_uid,
                        'name': var_info.get('name', var_name),
                        'description': var_info.get('label', ''),
                        'path': var_info.get('file', ''),
                        'type': var_info.get('type', 'variable')
                    }
                else:
                    var_uid = f"temp_var_{var_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': var_uid,
                        'name': var_name,
                        'description': f"Variable: {var_name}",
                        'path': '',
                        'type': 'variable'
                    }
    
                child['outgoing_relations'].append({
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    'relation_type': 'uses',
                    'category': 'parsed'
                })
    
        elif item_type == 'function':
            # Appels de fonction (même pattern)
            for call_name in item.get('calls', []):
                call_uid = self._find_label_uid_by_name(normalize_node_name(call_name))
                
                if call_uid and call_uid in self.label_uid_to_info:
                    call_info = self.label_uid_to_info[call_uid]
                    target_data = {
                        'uid': call_uid,
                        'name': call_info.get('name', call_name),
                        'description': call_info.get('label', ''),
                        'path': call_info.get('file', ''),
                        'type': call_info.get('type', 'function')
                    }
                else:
                    call_uid = f"temp_func_{call_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': call_uid,
                        'name': call_name,
                        'description': f"Function: {call_name}",
                        'path': '',
                        'type': 'function'
                    }
    
                child['outgoing_relations'].append({
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    'relation_type': 'calls',
                    'category': 'parsed'
                })
    
        # Ajouter aux infos globales
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_data.get('name', 'unknown') if self.current_cluster_data else 'unknown',
            'file': file_path,
            'path': file_path,
            'description': child['description']
        }
    
        return child

    def _build_complete_relations_graph(self):
        """
        - Résout les UIDs temporaires
        - Crée les relations inverses
        - Valide la cohérence
        """
        logger.info("🔗 Construction du graphe de relations...")

        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)
        resolved_count = 0
        inverse_count = 0

        # Étape 1 : Résoudre les UIDs temporaires
        logger.info("📝 Résolution des UIDs temporaires...")
        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid', '')

                # Si c'est un UID temporaire, essayer de le résoudre
                if target_uid.startswith('temp_'):
                    target_name = rel.get('target_name', '')
                    normalized = normalize_node_name(target_name)

                    if normalized:
                        real_uid = self._find_label_uid_by_name(normalized)
                        if real_uid:
                            rel['target_uid'] = real_uid
                            resolved_count += 1
                            logger.debug(f"✅ UID résolu: {target_uid} -> {real_uid}")

        logger.info(f"✅ {resolved_count} UIDs temporaires résolus")

        # Étape 2 : Créer les relations inverses
        logger.info("🔄 Création des relations inverses...")
        node_by_uid = {n['uid']: n for n in all_nodes if 'uid' in n}

        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')

                # Skip si c'est toujours un UID temporaire
                if not target_uid or target_uid.startswith('temp_'):
                    continue
                
                target_node = node_by_uid.get(target_uid)
                if not target_node:
                    continue
                
                # Créer la relation inverse
                inverse = {
                    'source_uid': node_uid,
                    'relation_type': rel['relation_type'],
                    'category': rel.get('category', 'custom'),
                    'source_name': node.get('label', node.get('name', 'Unknown'))
                }

                incoming = target_node.setdefault('incoming_relations', [])
                if not any(r['source_uid'] == node_uid and r['relation_type'] == rel['relation_type'] for r in incoming):
                    incoming.append(inverse)
                    inverse_count += 1

        logger.info(f"✅ {inverse_count} relations inverses créées")

        # Étape 3 : Log statistiques
        total_relations = sum(len(n.get('outgoing_relations', [])) for n in all_nodes)
        logger.info(f"📊 Graphe complet: {len(all_nodes)} nœuds, {total_relations} relations")

    def _save_scan_results_to_storage(self):
        """
         CORRECTION: Sauvegarde avec passage explicite de profile_data
        """
        if not self.current_project_name or not self.current_project_profile_data:
            logger.error("Aucun projet sélectionné pour la sauvegarde.")
            return False

        logger.info("=" * 80)
        logger.info("💾 SAUVEGARDE DES RÉSULTATS DE SCAN")
        logger.info("=" * 80)

        try:
            # ÉTAPE 1: Finaliser les données
            logger.info("\n🔄 Étape 1: Mise à jour des structures en mémoire...")
            self._finalize_project_data_after_scan()

            # ÉTAPE 2: SQLite
            logger.info("\n💾 Étape 2: Sauvegarde dans SQLite...")
            sqlite_success = self.project_storage_manager._save_project_to_sqlite(
                self.current_project_profile_data
            )
            if not sqlite_success:
                logger.error("❌ Échec sauvegarde SQLite")
                return False
            logger.info("✅ Sauvegarde SQLite réussie")

            # ÉTAPE 3: Dgraph
            logger.info("\n🔄 Étape 3: Insertion dans Dgraph...")

            # ✅ CORRECTION: Synchroniser avant transformation
            self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
            self.dgraph_manager.label_uid_to_info = self.label_uid_to_info
            self.dgraph_manager.pending_relations = self.pending_relations

            # ✅ CORRECTION: Passer explicitement profile_data
            mutations = self.dgraph_manager._transform_profile_to_dgraph_mutations(
                profile_data=self.current_project_profile_data
            )

            if not mutations:
                logger.error("❌ Aucune mutation générée")
                return False

            logger.info(f"📊 {len(mutations)} mutations à insérer")

            dgraph_success = self.dgraph_connector.insert_mutations(mutations)
            if not dgraph_success:
                logger.error("❌ Échec insertion Dgraph")
                return False

            logger.info("✅ Insertion Dgraph réussie")
            self.dgraph_manager.clean_duplicate_files()

            # ÉTAPE 4: Rafraîchir
            logger.info("\n🔄 Étape 4: Rafraîchissement des données...")

            # Recharger depuis Dgraph
            loaded_profiles = self.dgraph_manager._load_project_profiles()
            if loaded_profiles:
                self.project_profiles.update(loaded_profiles)
                logger.info(f"✅ {len(loaded_profiles)} profil(s) rechargé(s)")

            # Recharger depuis SQLite
            self.project_storage_manager._load_projects_from_sqlite()

            # Réafficher dans l'UI
            if self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())

            logger.info("\n" + "=" * 80)
            logger.info("✅ SAUVEGARDE COMPLÈTE: Scan enregistré dans SQLite ET Dgraph")
            logger.info("=" * 80 + "\n")

            QtWidgets.QMessageBox.information(
                self,
                "Succès",
                "Résultats du scan sauvegardés dans SQLite et Dgraph avec succès!"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            import traceback
            traceback.print_exc()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la sauvegarde: {str(e)}"
            )
            return False

    def _finalize_project_data_after_scan(self):
        """
         CORRECTION: Finalise avec passage explicite de profile_data
        """
        logger.info("Finalisation des données du projet...")

        if not self.current_project_profile_data:
            return

        all_nodes = self.dgraph_manager._get_all_nodes(
            self.current_project_profile_data
        )

        # 1. Résolution des UIDs temporaires
        logger.info("✓ Résolution des UIDs temporaires...")
        uid_mapping = {}

        for node in all_nodes:
            uid = node.get('uid')
            if not uid or uid.startswith('temp_') or uid.startswith('unresolved_'):
                new_uid = str(uuid.uuid4())
                if uid:
                    uid_mapping[uid] = new_uid
                node['uid'] = new_uid

        # 2. Mettre à jour les références
        logger.info("✓ Mise à jour des références aux UIDs...")
        for node in all_nodes:
            for rel in node.get('outgoing_relations', []):
                old_target = rel.get('target_uid')
                if old_target in uid_mapping:
                    rel['target_uid'] = uid_mapping[old_target]

        # 3. Synchroniser pending_relations
        logger.info("✓ Synchronisation pending_relations...")
        self.pending_relations.clear()

        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            relations_list = []
            for rel in node.get('outgoing_relations', []):
                relations_list.append({
                    'target_uid': rel.get('target_uid'),
                    'relation_type': rel.get('relation_type', 'relation')
                })

            if relations_list:
                self.pending_relations[node_uid] = relations_list

        # 4. Validation
        logger.info("✓ Validation de la cohérence...")
        validation_stats = self._validate_parsed_relations()
        logger.info(f"  Validation: {validation_stats['total_parsed_in_outgoing']} relations validées")

        # 5. Construction du graphe complet
        logger.info("✓ Construction du graphe complet...")
        self._build_complete_relations_graph()

        # 6. Batch insertion Dgraph
        logger.info("✓ Insertion batchée dans Dgraph...")

        #  CORRECTION: Synchroniser avant batch save
        self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
        self.dgraph_manager.label_uid_to_info = self.label_uid_to_info
        self.dgraph_manager.pending_relations = self.pending_relations

        # CORRECTION: Passer explicitement profile_data
        if self.dgraph_manager._batch_save_to_dgraph(
            profile_data=self.current_project_profile_data
        ):
            logger.info(" Batch Dgraph réussi")
        else:
            logger.warning("⚠️ Échec batch Dgraph, retry manuel requis")

        logger.info("Finalisation terminée ✓")

    def _save_label_and_children_recursive(self, cursor, label_data, cluster_uid, parent_uid, level):
        """
        ✅ CORRIGÉ : Sauvegarde SANS troncature avec commit optimisé
        """
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid

        # ✅ DIRECT - Pas de truncate_json()
        files = label_data.get('files', [])
        file_contents = label_data.get('file_contents', {})

        # Log taille pour monitoring
        try:
            file_contents_json = json.dumps(file_contents, ensure_ascii=False)
            size_mb = len(file_contents_json.encode('utf-8')) / (1024 * 1024)

            if size_mb > 10:
                logger.warning(f"⚠️ Gros fileContents: {label_data.get('label')} ({size_mb:.2f} MB)")
        except Exception as e:
            logger.error(f"❌ Erreur calcul taille: {e}")
            file_contents_json = "{}"
            size_mb = 0

        # Sauvegarder le label
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label_uid,
                cluster_uid,
                parent_uid,
                label_data.get('label', ''),
                label_data.get('id', label_uid),
                level,
                label_data.get('path', ''),
                parent_uid,
                label_data.get('type', 'label'),
                json.dumps(label_data.get('category', []), ensure_ascii=False),
                label_data.get('description', ''),
                '',
                json.dumps(files, ensure_ascii=False),
                file_contents_json,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
        except Exception as e:
            logger.error(f"❌ Erreur insertion label {label_data.get('label')}: {e}")
            return

        # ✅ Commit après CHAQUE root label
        if level == 0:
            try:
                cursor.connection.commit()
                logger.info(f"✅ Commit: {label_data.get('label')} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.error(f"❌ Erreur commit: {e}")

        # Sauvegarder les classes du label
        for cls in label_data.get('classes', []):
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            cls['uid'] = cls_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cls_uid,
                    cluster_uid,
                    label_uid,
                    cls.get('name', ''),
                    cls.get('uid', cls_uid),
                    level + 1,
                    '',
                    label_uid,
                    'class',
                    json.dumps(['code_element', 'class']),
                    cls.get('description', ''),
                    '',
                    json.dumps(cls.get('files', []), ensure_ascii=False),
                    json.dumps(cls.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Relations de la classe
                for rel in cls.get('outgoing_relations', []):
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        cls_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            except Exception as e:
                logger.error(f"❌ Erreur classe {cls.get('name')}: {e}")
                continue

        # Sauvegarder les fonctions
        for func in label_data.get('functions', []):
            func_uid = func.get('uid', str(uuid.uuid4()))
            func['uid'] = func_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    func_uid,
                    cluster_uid,
                    label_uid,
                    func.get('name', ''),
                    func.get('uid', func_uid),
                    level + 1,
                    '',
                    label_uid,
                    func.get('type', 'function'),
                    json.dumps(['code_element', 'function']),
                    func.get('description', ''),
                    '',
                    json.dumps(func.get('files', []), ensure_ascii=False),
                    json.dumps(func.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Relations
                for rel in func.get('outgoing_relations', []):
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        func_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            except Exception as e:
                logger.error(f"❌ Erreur fonction {func.get('name')}: {e}")
                continue

        # Sauvegarder les variables
        for var in label_data.get('variables', []):
            var_uid = var.get('uid', str(uuid.uuid4()))
            var['uid'] = var_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    var_uid,
                    cluster_uid,
                    label_uid,
                    var.get('name', ''),
                    var.get('uid', var_uid),
                    level + 1,
                    '',
                    label_uid,
                    'variable',
                    json.dumps(['code_element', 'variable']),
                    var.get('description', ''),
                    '',
                    json.dumps(var.get('files', []), ensure_ascii=False),
                    json.dumps(var.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.error(f"❌ Erreur variable {var.get('name')}: {e}")
                continue

        # Traiter récursivement les enfants hiérarchiques
        for child in label_data.get('children', []):
            if child.get('type') not in ['class', 'function', 'variable']:
                self._save_label_and_children_recursive(
                    cursor, child, cluster_uid, label_uid, level + 1
                )

    
    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector: 
            self.dgraph_connector.close()
        super().closeEvent(event)