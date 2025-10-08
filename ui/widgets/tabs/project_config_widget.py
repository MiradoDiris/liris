import os
import json
import uuid
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout, QPlainTextEdit, QListWidgetItem, QHBoxLayout, QLabel, QComboBox, QPushButton, QInputDialog, QMessageBox
from collections import defaultdict
import requests  # Added for schema update
import ast  # Added for extraction

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector


class AddEditItemDialog(QDialog):
    """
    Dialogue générique pour ajouter/éditer un item avec nom et description.
    """
    def __init__(self, title, current_name="", current_description="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 200)

        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Nom de l'item...")
        self.name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.description_edit = QTextEdit(current_description)
        self.description_edit.setPlaceholderText("Description de l'item...")
        self.description_edit.setStyleSheet("""
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
        self.description_edit.setMaximumHeight(100)

        layout = QFormLayout(self)
        layout.addRow("Nom:", self.name_edit)
        layout.addRow("Description:", self.description_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip()
        }


class CategoryEditDialog(QtWidgets.QDialog):
    """
    Dialogue pour l'ajout, la modification et la suppression de catégories multiples.
    """

    def __init__(self, current_categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("category_edit_dialog.title"))
        self.setMinimumSize(400, 300)

        self.categories = list(current_categories)

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
        self.category_list_widget.setStyleSheet("""
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
            }
            QListWidget::item:selected {
                background-color: #888888;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
        """)
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

        self.remove_button = QtWidgets.QPushButton(
            tr("category_edit_dialog.remove_button")
        )
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
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("category_edit_dialog.add_category_title"),
            tr("category_edit_dialog.add_category_text"),
        )
        if ok and text:
            category = text.strip()
            if category and category not in self.categories:
                self.categories.append(category)
                self._load_categories_into_list()
                self.category_list_widget.setCurrentRow(
                    self.category_list_widget.count() - 1
                )
                logger.info(f"Catégorie ajoutée : {category}")

    def _edit_category(self):
        current_row = self.category_list_widget.currentRow()
        if current_row == -1:
            return

        old_category = self.categories[current_row]
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("category_edit_dialog.edit_category_title"),
            tr("category_edit_dialog.edit_category_text"),
            QtWidgets.QLineEdit.Normal,
            old_category,
        )
        if ok and text:
            new_category = text.strip()
            if new_category and new_category != old_category:
                if (
                    new_category in self.categories
                    and self.categories.index(new_category) != current_row
                ):
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.duplicate_title"),
                        tr("category_edit_dialog.duplicate_category_msg"),
                    )
                    return
                self.categories[current_row] = new_category
                self._load_categories_into_list()
                self.category_list_widget.setCurrentRow(current_row)
                logger.info(
                    f"Catégorie modifiée de '{old_category}' à '{new_category}'"
                )

    def _remove_category(self):
        current_row = self.category_list_widget.currentRow()
        if current_row == -1:
            return

        category_to_remove = self.categories[current_row]
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("category_edit_dialog.remove_category_title"),
            tr("category_edit_dialog.remove_category_text").format(
                category=category_to_remove
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            del self.categories[current_row]
            self._load_categories_into_list()
            logger.info(f"Catégorie supprimée : {category_to_remove}")
            self._update_button_states()

    def get_categories(self):
        return self.categories


class RelationsConfig(QtWidgets.QWidget):
    """
    Widget pour configurer les relations d'import pour un niveau de hiérarchie spécifique.
    """
    def __init__(self, parent_widget, level="global"):
        super().__init__()
        self.parent_widget = parent_widget
        self.level = level
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QtWidgets.QLabel(f"Relations {self.level.capitalize()}")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Type de relation
        layout.addWidget(QtWidgets.QLabel("Type:"))
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems([
            "import", "heritage", "extend", "implement",
            "depends_on", "calls", "uses", "references"
        ])
        self.type_combo.setMinimumWidth(100)
        layout.addWidget(self.type_combo)

        # Source
        layout.addWidget(QtWidgets.QLabel("Source:"))
        self.source_label = QtWidgets.QLabel("Aucun sélectionné")
        self.source_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.source_label)

        # Cible
        layout.addWidget(QtWidgets.QLabel("Cible:"))
        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.setMinimumWidth(200)
        layout.addWidget(self.target_combo)

        # Bouton ajouter
        self.add_button = QtWidgets.QPushButton("➕ Ajouter Relation")
        self.add_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_button.clicked.connect(self._on_add)
        layout.addWidget(self.add_button)

        # Liste des relations
        layout.addWidget(QtWidgets.QLabel("Relations:"))
        self.relations_list = QtWidgets.QListWidget()
        self.relations_list.setMaximumHeight(100)
        self.relations_list.currentItemChanged.connect(self.parent_widget._update_button_states)
        layout.addWidget(self.relations_list)

        # Bouton supprimer
        self.remove_button = QtWidgets.QPushButton("🗑️ Supprimer")
        self.remove_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_button.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_button)

    def update_current(self, source_id):
        if source_id:
            source_info = self.parent_widget.label_id_to_info.get(source_id)
            self.source_label.setText(source_info['name'] if source_info else "Inconnu")
            self.parent_widget._populate_target_combo(self.target_combo, source_id)
            self._update_relations_list(source_id)
        else:
            self.source_label.setText("Aucun sélectionné")
            self.target_combo.clear()
            self._update_relations_list(None)

    def _on_add(self):
        source_id = self.parent_widget.current_selected_label_id
        if not source_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez un élément source.")
            return
        target_id = self.target_combo.currentData()
        rel_type = self.type_combo.currentText()
        if not target_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez une cible.")
            return
        relation = {'target_id': target_id, 'relation_type': rel_type}
        pending = self.parent_widget.pending_relations
        if relation not in pending[source_id]:
            pending[source_id].append(relation)
            self.parent_widget._update_local_relations(source_id, target_id, rel_type)
            self._update_relations_list(source_id)
            logger.info(f"Relation ajoutée: {rel_type} vers {target_id}")

    def _on_remove(self):
        current_item = self.relations_list.currentItem()
        if not current_item:
            return
        rel = current_item.data(Qt.UserRole)
        source_id = self.parent_widget.current_selected_label_id
        if source_id:
            self.parent_widget.pending_relations[source_id].remove(rel)
            self.parent_widget._update_local_relations_remove(source_id, rel['target_id'], rel['relation_type'])
            self._update_relations_list(source_id)
            logger.info(f"Relation supprimée")

    def _update_relations_list(self, source_id):
        self.relations_list.clear()
        if not source_id:
            return
        pending = self.parent_widget.pending_relations[source_id]
        for r in pending:
            target_info = self.parent_widget.label_id_to_info.get(r['target_id'])
            if target_info:
                display = f"{r['relation_type'].upper()}: -> {target_info['name']} ({target_info['cluster']})"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, r)
                self.relations_list.addItem(item)


class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.conductor = conductor
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)

        self.project_profiles = {}
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
        self.label_id_to_info = {}
        self.name_to_id = {}
        self.current_selected_label_id = None

        self.global_relations_config = RelationsConfig(self, "global")

        # Définir une taille minimale pour le widget et maximiser
        self.setMinimumSize(1400, 900)

        try:
            if self.dgraph_connector.client:
                schema = self.dgraph_connector.get_current_schema()
                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse. Mise à jour recommandée.")

            self._init_ui()
            self._load_project_profiles()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

    def _get_all_nodes(self):
        """Récupère tous les nœuds de labels dans la hiérarchie."""
        if not self.current_project_profile_data:
            return []
        all_nodes = []
        def collect_nodes(node_list):
            for node in node_list:
                all_nodes.append(node)
                collect_nodes(node.get('children', []))
        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            collect_nodes(cluster.get('root_labels', []))
        return all_nodes

    def _update_local_relations(self, source_id, target_id, rel_type):
        """Met à jour les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['id'] == source_id), None)
        if source_node:
            source_node.setdefault('outgoing_relations', []).append({'target_id': target_id, 'relation_type': rel_type})
        target_node = next((n for n in all_nodes if n['id'] == target_id), None)
        if target_node:
            target_node.setdefault('incoming_relations', []).append({'source_id': source_id, 'relation_type': rel_type})

    def _update_local_relations_remove(self, source_id, target_id, rel_type):
        """Supprime les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['id'] == source_id), None)
        if source_node:
            to_remove = next((r for r in source_node.get('outgoing_relations', []) if r['target_id'] == target_id and r['relation_type'] == rel_type), None)
            if to_remove:
                source_node['outgoing_relations'].remove(to_remove)
        target_node = next((n for n in all_nodes if n['id'] == target_id), None)
        if target_node:
            to_remove = next((r for r in target_node.get('incoming_relations', []) if r['source_id'] == source_id and r['relation_type'] == rel_type), None)
            if to_remove:
                target_node['incoming_relations'].remove(to_remove)

    def showEvent(self, event):
        """Maximiser la fenêtre lors de l'affichage"""
        super().showEvent(event)
        if self.window():
            self.window().showMaximized()

    def _get_compact_button_style(self):
        """Style pour les boutons carrés compacts avec icônes améliorées"""
        return """
            QPushButton {
                background-color: #922B3C;
                color: white;
                border: 1px solid #7a2431;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                min-width: 70px;
                max-width: 70px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover {
                background-color: #a63342;
                border: 1px solid #922B3C;
            }
            QPushButton:pressed {
                background-color: #6d1f2b;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
                border: 1px solid #BBBBBB;
            }
        """
    
    def _get_button_style_grenat(self):
        """Style grenat pour les boutons de sauvegarde"""
        return """
            QPushButton {
                background-color: #922B3C;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #6d1f2b;
            }
            QPushButton:pressed {
                background-color: #5a1823;
            }
            QPushButton:disabled {
                background-color: #d3d3d3;
                color: #a0a0a0;
            }
        """

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
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
        """

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 3 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(15)
        main_vertical_layout.setContentsMargins(15, 15, 15, 15)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)
        left_column_layout.addStretch()

        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
        project_selection_layout.addStretch()

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        self.add_project_button = QtWidgets.QPushButton(
            "➕ " + tr("project_config.new_project_button")
        )
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        self.delete_project_button = QtWidgets.QPushButton(
            "🗑️ " + tr("project_config.delete_project_button")
        )
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)

        self.upload_local_button = QtWidgets.QPushButton("📁 Uploader Projet Local")
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)

        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_form_layout.addRow(
            tr("project_config.project_name_label"), self.project_name_edit
        )

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
        self.add_cluster_button.setStyleSheet(self._get_compact_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)
        self.add_cluster_button.setMinimumWidth(70)
        self.add_cluster_button.setMaximumWidth(70)
        self.add_cluster_button.setMinimumHeight(32)
        self.add_cluster_button.setMaximumHeight(32)

        self.edit_cluster_button = QtWidgets.QPushButton("Modif")
        self.edit_cluster_button.setStyleSheet(self._get_compact_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)
        self.edit_cluster_button.setMinimumWidth(70)
        self.edit_cluster_button.setMaximumWidth(70)
        self.edit_cluster_button.setMinimumHeight(32)
        self.edit_cluster_button.setMaximumHeight(32)

        self.remove_cluster_button = QtWidgets.QPushButton("✕")
        self.remove_cluster_button.setStyleSheet(self._get_compact_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)
        self.remove_cluster_button.setMinimumWidth(70)
        self.remove_cluster_button.setMaximumWidth(70)
        self.remove_cluster_button.setMinimumHeight(32)
        self.remove_cluster_button.setMaximumHeight(32)

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

        top_columns_layout.addLayout(left_column_layout, 5)

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
        self.root_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        root_buttons_layout.setSpacing(5)

        self.add_root_button = QtWidgets.QPushButton("Ajouter")
        self.add_root_button.setStyleSheet(self._get_compact_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)
        self.add_root_button.setMinimumWidth(70)
        self.add_root_button.setMaximumWidth(70)
        self.add_root_button.setMinimumHeight(32)
        self.add_root_button.setMaximumHeight(32)

        self.edit_root_button = QtWidgets.QPushButton("Modif")
        self.edit_root_button.setStyleSheet(self._get_compact_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)
        self.edit_root_button.setMinimumWidth(70)
        self.edit_root_button.setMaximumWidth(70)
        self.edit_root_button.setMinimumHeight(32)
        self.edit_root_button.setMaximumHeight(32)

        self.remove_root_button = QtWidgets.QPushButton("✕")
        self.remove_root_button.setStyleSheet(self._get_compact_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)
        self.remove_root_button.setMinimumWidth(70)
        self.remove_root_button.setMaximumWidth(70)
        self.remove_root_button.setMinimumHeight(32)
        self.remove_root_button.setMaximumHeight(32)

        self.modify_category_root_button = QtWidgets.QPushButton("Cat")
        self.modify_category_root_button.setStyleSheet(self._get_compact_button_style())
        self.modify_category_root_button.clicked.connect(lambda: self._modify_category_for_selected_label("root"))
        self.modify_category_root_button.setMinimumWidth(70)
        self.modify_category_root_button.setMaximumWidth(70)
        self.modify_category_root_button.setMinimumHeight(32)
        self.modify_category_root_button.setMaximumHeight(32)

        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        root_buttons_layout.addWidget(self.modify_category_root_button)
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
        self.level1_list_widget.currentItemChanged.connect(
            self._on_level1_label_selected
        )
        self.level1_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
        hierarchy_group_layout.addWidget(self.level1_list_widget)

        level1_buttons_layout = QtWidgets.QHBoxLayout()
        level1_buttons_layout.setSpacing(5)

        self.add_level1_button = QtWidgets.QPushButton("Ajouter")
        self.add_level1_button.setStyleSheet(self._get_compact_button_style())
        self.add_level1_button.clicked.connect(self._add_level1_label)
        self.add_level1_button.setMinimumWidth(70)
        self.add_level1_button.setMaximumWidth(70)
        self.add_level1_button.setMinimumHeight(32)
        self.add_level1_button.setMaximumHeight(32)

        self.edit_level1_button = QtWidgets.QPushButton("Modif")
        self.edit_level1_button.setStyleSheet(self._get_compact_button_style())
        self.edit_level1_button.clicked.connect(self._edit_level1_label)
        self.edit_level1_button.setMinimumWidth(70)
        self.edit_level1_button.setMaximumWidth(70)
        self.edit_level1_button.setMinimumHeight(32)
        self.edit_level1_button.setMaximumHeight(32)

        self.remove_level1_button = QtWidgets.QPushButton("✕")
        self.remove_level1_button.setStyleSheet(self._get_compact_button_style())
        self.remove_level1_button.clicked.connect(self._remove_level1_label)
        self.remove_level1_button.setMinimumWidth(70)
        self.remove_level1_button.setMaximumWidth(70)
        self.remove_level1_button.setMinimumHeight(32)
        self.remove_level1_button.setMaximumHeight(32)

        self.modify_category_level1_button = QtWidgets.QPushButton("Cat")
        self.modify_category_level1_button.setStyleSheet(self._get_compact_button_style())
        self.modify_category_level1_button.clicked.connect(lambda: self._modify_category_for_selected_label("level1"))
        self.modify_category_level1_button.setMinimumWidth(70)
        self.modify_category_level1_button.setMaximumWidth(70)
        self.modify_category_level1_button.setMinimumHeight(32)
        self.modify_category_level1_button.setMaximumHeight(32)

        level1_buttons_layout.addWidget(self.add_level1_button)
        level1_buttons_layout.addWidget(self.edit_level1_button)
        level1_buttons_layout.addWidget(self.remove_level1_button)
        level1_buttons_layout.addWidget(self.modify_category_level1_button)
        level1_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(level1_buttons_layout)

        # 3. Labels Enfants (Niveau 2)
        child_label_title = QtWidgets.QLabel("Labels Niveau 2")
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(80)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        self.child_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        child_buttons_layout.setSpacing(5)

        self.add_child_button = QtWidgets.QPushButton("Ajouter")
        self.add_child_button.setStyleSheet(self._get_compact_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)
        self.add_child_button.setMinimumWidth(70)
        self.add_child_button.setMaximumWidth(70)
        self.add_child_button.setMinimumHeight(32)
        self.add_child_button.setMaximumHeight(32)

        self.edit_child_button = QtWidgets.QPushButton("Modif")
        self.edit_child_button.setStyleSheet(self._get_compact_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)
        self.edit_child_button.setMinimumWidth(70)
        self.edit_child_button.setMaximumWidth(70)
        self.edit_child_button.setMinimumHeight(32)
        self.edit_child_button.setMaximumHeight(32)

        self.remove_child_button = QtWidgets.QPushButton("✕")
        self.remove_child_button.setStyleSheet(self._get_compact_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)
        self.remove_child_button.setMinimumWidth(70)
        self.remove_child_button.setMaximumWidth(70)
        self.remove_child_button.setMinimumHeight(32)
        self.remove_child_button.setMaximumHeight(32)

        self.modify_category_child_button = QtWidgets.QPushButton("Cat")
        self.modify_category_child_button.setStyleSheet(self._get_compact_button_style())
        self.modify_category_child_button.clicked.connect(lambda: self._modify_category_for_selected_label("child"))
        self.modify_category_child_button.setMinimumWidth(70)
        self.modify_category_child_button.setMaximumWidth(70)
        self.modify_category_child_button.setMinimumHeight(32)
        self.modify_category_child_button.setMaximumHeight(32)

        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)
        child_buttons_layout.addWidget(self.modify_category_child_button)
        child_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_layout.addWidget(hierarchy_group)
        middle_scroll.setWidget(middle_content)
        top_columns_layout.addWidget(middle_scroll, 5)

        # --- Colonne de droite: Relations ---
        right_column_layout = QtWidgets.QVBoxLayout()
        right_column_layout.addStretch()

        relations_group = QtWidgets.QGroupBox("Configuration des Relations")
        relations_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        relations_layout.addWidget(self.global_relations_config)
        right_column_layout.addWidget(relations_group)

        # Boutons de sauvegarde/export/insert
        save_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("💾 Sauvegarder Profil")
        self.save_button.setStyleSheet(self._get_button_style_grenat())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False)
        save_layout.addWidget(self.save_button)

        self.export_profile_button = QtWidgets.QPushButton("📤 Exporter Profil")
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(False)
        save_layout.addWidget(self.export_profile_button)

        self.insert_dgraph_button = QtWidgets.QPushButton("🔄 Insérer dans Dgraph")
        self.insert_dgraph_button.setStyleSheet(self._get_button_style_grenat())
        self.insert_dgraph_button.clicked.connect(self._on_insert_dgraph)
        self.insert_dgraph_button.setEnabled(False)
        save_layout.addWidget(self.insert_dgraph_button)

        right_column_layout.addLayout(save_layout)
        right_column_layout.addStretch()

        top_columns_layout.addLayout(right_column_layout, 4)

    def _load_project_profiles(self):
        """Charge les profils depuis Dgraph."""
        query_result = self.dgraph_connector.query_workspaces()
        if query_result and 'q' in query_result:
            for ws in query_result['q']:
                name = ws.get('name', '')
                self.project_profiles[name] = self._workspace_to_profile(ws)
        self._update_project_combo()

    def _label_to_data(self, label):
        """Convertit un label Dgraph en data local."""
        data = {
            'label': label.get('name', ''),
            'id': label.get('id', ''),
            'description': label.get('description', ''),
            'category': label.get('category', []),
            'files': label.get('files', []),
            'file_contents': json.loads(label.get('fileContents', '{}')),
            'parents': [],
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': []
        }
        # Outgoing relations
        for rel in label.get('relations', []):
            target = rel.get('target', {})
            data['outgoing_relations'].append({
                'target_id': target.get('id'),
                'relation_type': rel.get('relationType')
            })
        # Incoming relations
        for rel in label.get('~relations', []):
            source = rel.get('source', {})
            data['incoming_relations'].append({
                'source_id': source.get('id'),
                'relation_type': rel.get('relationType')
            })
        return data

    def _fill_hierarchy(self, data, label_node):
        """Remplit récursivement les enfants."""
        # Gérer l'inconsistance dans les clés de la requête Dgraph ('parents' pour niveau 1, 'children' pour niveau 2)
        children_key = 'children' if 'children' in label_node else 'parents'
        children = label_node.get(children_key, [])
        for child in children:
            child_data = self._label_to_data(child)
            data['children'].append(child_data)
            self._fill_hierarchy(child_data, child)

    def _collect_relations(self, profile):
        """Collecte toutes les relations dans pending_relations."""
        pending = defaultdict(list)
        def collect(node):
            label_id = node['id']
            # Outgoing
            for rel in node.get('outgoing_relations', []):
                pending[label_id].append(rel)
            # Incoming: add to source
            for rel in node.get('incoming_relations', []):
                source_id = rel['source_id']
                target_id = label_id
                rel_type = rel['relation_type']
                pending[source_id].append({'target_id': target_id, 'relation_type': rel_type})
            # Recursive
            for child in node.get('children', []):
                collect(child)
        for cluster in profile['turing_ontology']['clusters_detailed']:
            for root in cluster['root_labels']:
                collect(root)
        profile['pending_relations'] = dict(pending)

    def _workspace_to_profile(self, ws):
        """Convertit un workspace Dgraph en profil local."""
        profile = {
            'name': ws.get('name', ''),
            'description': ws.get('description', ''),
            'files': ws.get('files', []),
            'file_contents': json.loads(ws.get('fileContents', '{}')),
            'turing_ontology': {
                'clusters_detailed': []
            },
            'pending_relations': defaultdict(list)
        }
        cm = ws.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_data = {
                'name': cluster.get('name', ''),
                'id': cluster.get('id', ''),
                'description': cluster.get('description', ''),
                'files': cluster.get('files', []),
                'file_contents': json.loads(cluster.get('fileContents', '{}')),
                'root_labels': []
            }
            for root_label in cluster.get('root_labels', []):
                root_data = self._label_to_data(root_label)
                cluster_data['root_labels'].append(root_data)
                # Remplir enfants récursivement
                self._fill_hierarchy(root_data, root_label)
            profile['turing_ontology']['clusters_detailed'].append(cluster_data)
        # Collect relations
        self._collect_relations(profile)
        return profile

    def _update_project_combo(self):
        self.project_combo.clear()
        for name in self.project_profiles.keys():
            self.project_combo.addItem(name)

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
        self._load_project_data_into_ui()
        self._update_project_details()
        self._update_button_states()

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

        # Réinitialiser les relations
        self.current_selected_label_id = None
        self.global_relations_config.update_current(None)

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
        """Gère la sélection d'un cluster."""
        if current:
            self.current_cluster_index = self.cluster_list_widget.row(current)
            self.current_cluster_data = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][self.current_cluster_index]

            # Réinitialiser les sélections inférieures
            self.current_root_data = None
            self.current_level1_data = None
            self.current_level2_data = None
            self.current_root_label_index = -1
            self.current_level1_label_index = -1
            self.current_level2_label_index = -1

            # Afficher uniquement les root labels du cluster
            self._populate_root_list()

            # Vider les listes inférieures
            self.level1_list_widget.clear()
            self.child_list_widget.clear()

            # Mettre à jour les détails
            details = f"Cluster: {self.current_cluster_data.get('name', '')}\n"
            details += f"Description: {self.current_cluster_data.get('description', '')}\n"
            details += f"Root Labels: {len(self.current_cluster_data.get('root_labels', []))}\n"
            details += f"Fichiers cluster: {len(self.current_cluster_data.get('files', []))}"
            self.details_text.setPlainText(details)

            self.global_relations_config.update_current(None)
        else:
            self.current_cluster_data = None
            self._reset_hierarchy_ui()

        self._update_button_states()

    def _populate_root_list(self):
        """Peuple la liste des root labels pour le cluster sélectionné."""
        self.root_list_widget.clear()
        if self.current_cluster_data:
            for root in self.current_cluster_data.get("root_labels", []):
                display = root['label']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, root["id"])
                self.root_list_widget.addItem(item)
        self._update_button_states()

    def _on_root_label_selected(self, current):
        """Gère la sélection d'un root label."""
        if current:
            self.current_root_label_index = self.root_list_widget.row(current)
            self.current_root_data = self.current_cluster_data["root_labels"][self.current_root_label_index]
            self.current_selected_label_id = current.data(Qt.UserRole)

            # Réinitialiser les sélections inférieures
            self.current_level1_data = None
            self.current_level2_data = None
            self.current_level1_label_index = -1
            self.current_level2_label_index = -1

            # Afficher les détails du root label
            self._update_selected_details("Label Racine", self.current_root_data)

            # Afficher uniquement les enfants de ce root label
            self._populate_level1_list()

            # Vider la liste des niveau 2
            self.child_list_widget.clear()

            # Mettre à jour les relations
            self.global_relations_config.update_current(self.current_selected_label_id)
        else:
            self.current_root_data = None
            self.current_selected_label_id = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)

        self._update_button_states()

    def _populate_level1_list(self):
        """Peuple la liste des labels niveau 1 pour le root label sélectionné."""
        self.level1_list_widget.clear()
        if self.current_root_data:
            for level1 in self.current_root_data.get("children", []):
                display = level1['label']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, level1["id"])
                self.level1_list_widget.addItem(item)
        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """Gère la sélection d'un label niveau 1."""
        if current:
            self.current_level1_label_index = self.level1_list_widget.row(current)
            self.current_level1_data = self.current_root_data["children"][self.current_level1_label_index]
            self.current_selected_label_id = current.data(Qt.UserRole)

            # Réinitialiser la sélection niveau 2
            self.current_level2_data = None
            self.current_level2_label_index = -1

            # Afficher les détails du label niveau 1
            self._update_selected_details("Label Niveau 1", self.current_level1_data)

            # Afficher uniquement les enfants de ce label niveau 1
            self._populate_child_list()

            # Mettre à jour les relations
            self.global_relations_config.update_current(self.current_selected_label_id)
        else:
            self.current_level1_data = None
            self.current_selected_label_id = None
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)

        self._update_button_states()

    def _populate_child_list(self):
        """Peuple la liste des labels niveau 2 pour le label niveau 1 sélectionné."""
        self.child_list_widget.clear()
        if self.current_level1_data:
            for child in self.current_level1_data.get("children", []):
                display = child['label']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child["id"])
                self.child_list_widget.addItem(item)
        self._update_button_states()

    def _on_child_label_selected(self, current):
        """Gère la sélection d'un label niveau 2."""
        if current:
            self.current_level2_label_index = self.child_list_widget.row(current)
            self.current_level2_data = self.current_level1_data["children"][self.current_level2_label_index]
            self.current_selected_label_id = current.data(Qt.UserRole)

            # Afficher les détails du niveau 2
            self._update_selected_details("Label Niveau 2", self.current_level2_data)

            # Mettre à jour les relations
            self.global_relations_config.update_current(self.current_selected_label_id)
        else:
            self.current_level2_data = None
            self.current_selected_label_id = None
            self.global_relations_config.update_current(None)
    
        self._update_button_states()

    def _on_any_label_selected(self, current):
        """Gère la sélection de n'importe quel label pour relations."""
        if current:
            self.current_selected_label_id = current.data(Qt.UserRole)
            self.global_relations_config.update_current(self.current_selected_label_id)
        else:
            self.current_selected_label_id = None
            self.global_relations_config.update_current(None)

    def _update_selected_details(self, title, data):
        """Met à jour les détails de l'élément sélectionné."""
        if not data:
            self.details_text.clear()
            return

        details = f"=== {title} ===\n\n"
        details += f"Nom: {data.get('label', '')}\n"
        details += f"ID: {data.get('id', '')}\n"
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
                target_name = self.label_id_to_info.get(r['target_id'], {}).get('name', 'Inconnu')
                details += f"  {r['relation_type'].upper()} -> {target_name}\n"

        # Relations entrantes
        incoming = data.get('incoming_relations', [])
        if incoming:
            details += f"\nRelations entrantes ({len(incoming)}):\n"
            for r in incoming:
                source_name = self.label_id_to_info.get(r['source_id'], {}).get('name', 'Inconnu')
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

        self.current_selected_label_id = None
        self.global_relations_config.update_current(None)

        self.details_text.clear()

    def _collect_all_labels(self):
        """Collecte tous les labels pour relations."""
        self.label_id_to_info.clear()
        self.name_to_id.clear()
        if not self.current_project_profile_data:
            return
        for cluster in self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", []):
            cluster_name = cluster.get('name', '')
            for root in cluster.get("root_labels", []):
                info = {'name': root.get('label', ''), 'cluster': cluster_name}
                self.label_id_to_info[root['id']] = info
                self.name_to_id[root['label']] = root['id']
                self._collect_labels_recursive(root)
        self._populate_target_combo_for_all()

    def _collect_labels_recursive(self, node):
        """Collecte récursivement labels dans hierarchy."""
        for child in node.get('children', []):
            info = {'name': child.get('label', ''), 'cluster': self.label_id_to_info.get(node['id'], {}).get('cluster', '')}
            self.label_id_to_info[child['id']] = info
            self.name_to_id[child['label']] = child['id']
            self._collect_labels_recursive(child)

    def _populate_target_combo_for_all(self):
        """Peuple les combos cibles avec tous les labels."""
        # Pour global relations
        self._populate_target_combo(self.global_relations_config.target_combo, None)

    def _populate_target_combo(self, combo, source_id):
        """Peuple le combo cible, excluant la source."""
        combo.clear()
        for label_id, info in self.label_id_to_info.items():
            if source_id and label_id == source_id:
                continue
            display = f"{info['name']} ({info['cluster']})"
            combo.addItem(display, label_id)

    def _add_cluster(self):
        dialog = AddEditItemDialog("Ajouter Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "id": str(uuid.uuid4()),
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
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [],
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
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
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

    def _modify_category_for_selected_label(self, level):
        if level == "root" and self.current_root_label_index >= 0:
            label_data = self.current_root_data
            list_widget = self.root_list_widget
        elif level == "level1" and self.current_level1_label_index >= 0:
            label_data = self.current_level1_data
            list_widget = self.level1_list_widget
        elif level == "child" and self.current_level2_label_index >= 0:
            label_data = self.current_level2_data
            list_widget = self.child_list_widget
        else:
            return

        current_categories = label_data.get("category", [])
        dialog = CategoryEditDialog(current_categories, self)
        if dialog.exec_() == QDialog.Accepted:
            new_categories = dialog.get_categories()
            label_data["category"] = new_categories
            current_row = list_widget.currentRow()
            if current_row >= 0:
                current_item = list_widget.item(current_row)
                if current_item:
                    display = label_data['label']
                    current_item.setText(display)
            self._update_button_states()
            logger.info(f"Catégories modifiées pour {label_data['label']}: {new_categories}")

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
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
            elif os.path.isdir(item_path):
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'files': [],
                    'file_contents': {},
                    'parents': [],
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
        """Scanne un dossier et crée une structure hiérarchique avec un cluster par élément de niveau supérieur."""
        profile = {
            'name': os.path.basename(directory),
            'description': f"Projet importé depuis {directory}",
            'files': [],
            'file_contents': {},
            'turing_ontology': {
                'clusters_detailed': []
            },
            'pending_relations': {}
        }
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            cluster = {
                'name': item,
                'id': str(uuid.uuid4()),
                'description': f"{'Fichier' if os.path.isfile(item_path) else 'Dossier'}: {item}",
                'files': [],
                'file_contents': {},
                'root_labels': []
            }
            if os.path.isfile(item_path):
                rel_path = item
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                new_root = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                cluster['root_labels'].append(new_root)
            elif os.path.isdir(item_path):
                # Ajouter les contenus directs comme root_labels
                for subitem in sorted(os.listdir(item_path)):
                    subitem_path = os.path.join(item_path, subitem)
                    sub_rel_path = os.path.relpath(subitem_path, directory)
                    if os.path.isfile(subitem_path):
                        content = ''
                        try:
                            with open(subitem_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read {subitem_path}: {e}")
                        profile['files'].append(sub_rel_path)
                        profile['file_contents'][sub_rel_path] = content
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'description': f"Fichier: {sub_rel_path}",
                            'category': ['file'],
                            'files': [sub_rel_path],
                            'file_contents': {sub_rel_path: content},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                    elif os.path.isdir(subitem_path):
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'description': f"Dossier: {sub_rel_path}",
                            'category': ['folder'],
                            'files': [],
                            'file_contents': {},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                        # Construire la hiérarchie pour ce sous-dossier
                        self._build_sub_hierarchy(subitem_path, directory, new_root, True, profile)
            profile['turing_ontology']['clusters_detailed'].append(cluster)
        logger.info(f"Scanné {len(profile['files'])} fichiers depuis {directory}")
        return profile

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
        """Supprime le projet actuel."""
        if not self.current_project_name:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.delete_project_title"),
            tr("project_config.delete_project_msg").format(project=self.current_project_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            if self.dgraph_connector.client:
                query_result = self.dgraph_connector.query_workspaces()
                if query_result is None:
                    logger.error("Query workspaces failed during delete check.")
                else:
                    uid = next((item['uid'] for item in query_result.get('q', []) if item.get('name') == self.current_project_name), None)
                    if uid:
                        to_delete = self._collect_uids_to_delete(uid)
                        self._collect_and_delete_uids(to_delete)
                        logger.info(f"Supprimé de Dgraph : {self.current_project_name}")
            del self.project_profiles[self.current_project_name]
            self._update_project_combo()
            self._reset_ui()
            self.project_profile_deleted.emit(self.current_project_name)
            logger.info(f"Projet supprimé : {self.current_project_name}")

    def _collect_uids_to_delete(self, workspace_uid):
        """Collecte récursivement tous les UIDs liés au workspace (clusters, labels, functions)."""
        if not self.dgraph_connector.client:
            return []
        
        to_delete = [workspace_uid]
        
        cm_query = f"""
        {{
          q(func: uid({workspace_uid})) {{
            clusterManagement {{
              uid
              clusters {{
                uid
                root_labels {{
                  uid
                  relations {{ uid }}
                  ~relations {{ uid }}
                  parents: ~parents {{
                    uid
                    relations {{ uid }}
                    ~relations {{ uid }}
                    children: ~parents {{
                      uid
                      relations {{ uid }}
                      ~relations {{ uid }}
                      functions {{
                        uid
                        calls {{
                          uid
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        txn = self.dgraph_connector.client.txn(read_only=True)
        resp = txn.query(cm_query)
        txn.discard()
        data = self.dgraph_connector._parse_response(resp)
        
        if data and 'q' in data and data['q']:
            workspace = data['q'][0]
            cm = workspace.get('clusterManagement', {})
            if cm and 'uid' in cm:
                to_delete.append(cm['uid'])
            
            for cluster in cm.get('clusters', []):
                if 'uid' in cluster:
                    to_delete.append(cluster['uid'])    
                    for root_label in cluster.get('root_labels', []):
                        if 'uid' in root_label:
                            to_delete.append(root_label['uid'])
                        for rel in root_label.get('relations', []) + root_label.get('~relations', []):
                            if 'uid' in rel:
                                to_delete.append(rel['uid'])
                        for level1 in root_label.get('parents', []):
                            if 'uid' in level1:
                                to_delete.append(level1['uid'])
                            for rel in level1.get('relations', []) + level1.get('~relations', []):
                                if 'uid' in rel:
                                    to_delete.append(rel['uid'])
                            for level2 in level1.get('children', []):
                                if 'uid' in level2:
                                    to_delete.append(level2['uid'])
                                for rel in level2.get('relations', []) + level2.get('~relations', []):
                                    if 'uid' in rel:
                                        to_delete.append(rel['uid'])
                                for func in level2.get('functions', []):
                                    if 'uid' in func:
                                        to_delete.append(func['uid'])
                                    for call in func.get('calls', []):
                                        if 'uid' in call:
                                            to_delete.append(call['uid'])
        
        logger.info(f"Collectés {len(to_delete)} UIDs à supprimer pour workspace {workspace_uid}")
        return to_delete

    def _collect_and_delete_uids(self, uids):
        """Supprime les UIDs collectés via mutation DELETE."""
        if not uids or not self.dgraph_connector.client:
            return False
        
        txn = self.dgraph_connector.client.txn()
        committed = False
        try:
            delete_json = {uid: None for uid in uids}
            delete_str = json.dumps(delete_json)
            assigned = txn.mutate(set_json=delete_str)
            txn.commit()
            committed = True
            logger.info(f"Supprimés {len(uids)} nœuds avec succès.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression : {e}")
            return False
        finally:
            if not committed:
                txn.discard()

    def _reset_ui(self):
        """Reset l'UI."""
        self.current_project_name = None
        self.current_project_profile_data = None
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self._refresh_cluster_list()
        self._reset_hierarchy_ui()
        self.pending_relations.clear()
        self.label_id_to_info.clear()
        self.name_to_id.clear()
        self.current_selected_label_id = None
        self.global_relations_config.update_current(None)
        self._update_button_states()

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

    def _on_insert_dgraph(self):
        """Insère le profil dans Dgraph."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        mutations = self._transform_profile_to_dgraph_mutations()
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(self, "Succès", "Inséré dans Dgraph avec succès. Ratel ouvert pour vérification.")
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Échec insertion Dgraph.")

    def is_configured(self):
        """Vérifie si la config est complète."""
        return (self.current_project_profile_data and
                self.project_name_edit.text().strip() and
                len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])) > 0)

    def _create_label_mutation(self, label_data, level, cluster_uid):
        """Crée une mutation pour un label avec ses fichiers."""
        uid = f"_:label_{label_data.get('id', str(uuid.uuid4()))}"
        
        # S'assurer que les fichiers sont bien présents
        files = label_data.get('files', [])
        file_contents = label_data.get('file_contents', {})
        
        label = {
            "uid": uid,
            "dgraph.type": "Label",
            "name": label_data.get("label", label_data.get("name", "")),
            "id": label_data.get("id", str(uuid.uuid4())),
            "level": level,
            "path": "",
            "category": label_data.get("category", []),
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z",
            "parentId": "",
            "nodeType": "label",
            "description": label_data.get("description", ""),
            "codeContent": "",
            "files": files,
            "fileContents": json.dumps(file_contents),
            "clusters": [{"uid": cluster_uid}]
        }
        return label

    def _transform_profile_to_dgraph_mutations(self):
        """Transforme le profil actuel en mutations Dgraph avec gestion complète de la hiérarchie."""
        if not self.current_project_profile_data:
            return []

        mutations = []

        # Créer Workspace
        workspace = {
            "uid": "_:workspace_uid",
            "dgraph.type": "Workspace",
            "name": self.current_project_profile_data.get("name", ""),
            "id": self.current_project_profile_data.get("name", str(uuid.uuid4())),
            "ownerId": "user1",
            "description": self.current_project_profile_data.get("description", ""),
            "updatedAt": datetime.now().isoformat() + "Z",
            "files": self.current_project_profile_data.get("files", []),
            "fileContents": json.dumps(self.current_project_profile_data.get("file_contents", {}))
        }
        mutations.append(workspace)

        # Créer ClusterManagement
        cluster_management = {
            "uid": "_:cm_uid",
            "dgraph.type": "ClusterManagement",
            "lastUpdated": datetime.now().isoformat() + "Z",
            "version": "1.0",
            "clusters": []
        }
        mutations.append(cluster_management)

        # Lier ClusterManagement au Workspace
        workspace["clusterManagement"] = {"uid": "_:cm_uid"}

        turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = turing_ontology.get("clusters_detailed", [])

        label_uids = {}  # Map label id to uid

        for cluster_data in clusters_detailed:
            cluster_uid = f"_:cluster_{cluster_data.get('id', str(uuid.uuid4()))}"
            cluster = {
                "uid": cluster_uid,
                "dgraph.type": "Cluster",
                "name": cluster_data.get("name", ""),
                "id": cluster_data.get("id", str(uuid.uuid4())),
                "userId": "user1",
                "nodeType": "cluster",
                "description": cluster_data.get("description", ""),
                "codeContent": "",
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z",
                "files": cluster_data.get("files", []),
                "fileContents": json.dumps(cluster_data.get("file_contents", {})),
                "root_labels": []
            }
            mutations.append(cluster)
            cluster_management["clusters"].append({"uid": cluster_uid})

            # Créer root_labels avec leurs hiérarchies complètes
            root_labels = cluster_data.get("root_labels", [])
            for root in root_labels:
                # Créer le root label
                root_label = self._create_label_mutation(root, level=0, cluster_uid=cluster_uid)
                mutations.append(root_label)
                cluster["root_labels"].append({"uid": root_label["uid"]})
                label_uids[root['id']] = root_label["uid"]

                # Traiter récursivement la hiérarchie complète
                self._process_hierarchy_recursive(
                    root, 
                    root_label, 
                    cluster_uid, 
                    mutations, 
                    label_uids, 
                    level=1
                )

        # Ajouter les relations après création de tous les labels
        for source_id, rels in self.pending_relations.items():
            for rel in rels:
                if source_id in label_uids and rel['target_id'] in label_uids:
                    relation = {
                        "uid": f"_:rel_{uuid.uuid4()}",
                        "dgraph.type": "Relation",
                        "name": f"Relation {rel['relation_type']}",
                        "relationType": rel['relation_type'],
                        "source": {"uid": label_uids[source_id]},
                        "target": {"uid": label_uids[rel['target_id']]}
                    }
                    mutations.append(relation)

        return mutations
    
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
            child_mutation = self._create_label_mutation(
                child_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
            mutations.append(child_mutation)

            # Enregistrer l'UID
            label_uids[child_data['id']] = child_mutation["uid"]

            # Lier au parent via 'parents' sur l'enfant
            if "parents" not in child_mutation:
                child_mutation["parents"] = []
            child_mutation["parents"].append({"uid": parent_uid})

            # Définir le parentId (string)
            child_mutation["parentId"] = node_data.get('id', '')

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
        self.modify_category_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
    
        has_root = bool(self.current_root_data)
        self.add_level1_button.setEnabled(has_root)
        self.edit_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.remove_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.modify_category_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
    
        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(has_level1)
        self.edit_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.modify_category_child_button.setEnabled(self.child_list_widget.currentRow() != -1)

        # Boutons relations
        has_source = bool(self.current_selected_label_id)
        self.global_relations_config.add_button.setEnabled(has_source and self.global_relations_config.target_combo.count() > 0)
        self.global_relations_config.remove_button.setEnabled(self.global_relations_config.relations_list.currentRow() != -1)

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)