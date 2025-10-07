import os
import json
import uuid
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout, QPlainTextEdit
import requests  # Added for schema update

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

        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None

        self.current_parent_label_index = -1
        self.current_parent_is_file = False
        self.current_parent_filename = None

        self.current_child_label_index = -1
        self.current_child_is_file = False
        self.current_child_filename = None

        # Définir une taille minimale pour le widget
        self.setMinimumSize(1200, 800)

        try:
            # Vérifier que le schéma est bien configuré
            if self.dgraph_connector.client:
                # Optionnel : vérifier si les reverse edges existent
                schema = self.dgraph_connector.get_current_schema()
                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse. Mise à jour recommandée.")
                    # Décommenter la ligne suivante pour forcer la mise à jour
                    # self.dgraph_connector.update_schema_only_reverse_edges()

            self._init_ui()
            self._load_project_profiles()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

    def _get_improved_list_style(self):
        """Style amélioré pour les listes avec sélection grise"""
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
                background-color: #888888;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
        """

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 2 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(20)
        main_vertical_layout.setContentsMargins(20, 20, 20, 20)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(20)
        main_vertical_layout.addLayout(top_columns_layout)

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(15)
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
            tr("project_config.new_project_button")
        )
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        self.delete_project_button = QtWidgets.QPushButton(
            tr("project_config.delete_project_button")
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
        details_form_layout.setSpacing(15)
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
        self.add_cluster_button = QtWidgets.QPushButton(
            tr("project_config.add_cluster_button")
        )
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)
        self.edit_cluster_button = QtWidgets.QPushButton(
            tr("project_config.edit_cluster_button")
        )
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)
        self.remove_cluster_button = QtWidgets.QPushButton(
            tr("project_config.remove_cluster_button")
        )
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)
        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
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

        import_export_layout = QtWidgets.QHBoxLayout()
        import_export_layout.addStretch()

        self.import_folder_button = QtWidgets.QPushButton(
            tr("project_config.import_folder_button")
        )
        self.import_folder_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.import_folder_button.clicked.connect(self._on_import_directory)
        import_export_layout.addWidget(self.import_folder_button)

        self.export_profile_button = QtWidgets.QPushButton("💾 Exporter")
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(bool(self.current_project_name))
        import_export_layout.addWidget(self.export_profile_button)

        import_export_layout.addStretch()
        left_column_layout.addLayout(import_export_layout)

        save_buttons_layout = QtWidgets.QHBoxLayout()
        save_buttons_layout.addStretch()

        self.save_button = QtWidgets.QPushButton("💾 Sauvegarder")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_profile)
        self.save_button.setEnabled(False)
        save_buttons_layout.addWidget(self.save_button)

        self.insert_dgraph_button = QtWidgets.QPushButton("🔄 Insérer dans Dgraph")
        self.insert_dgraph_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.insert_dgraph_button.clicked.connect(self._on_insert_dgraph)
        self.insert_dgraph_button.setEnabled(False)
        save_buttons_layout.addWidget(self.insert_dgraph_button)

        save_buttons_layout.addStretch()

        left_column_layout.addLayout(save_buttons_layout)

        left_column_layout.addStretch()

        top_columns_layout.addLayout(left_column_layout, 3)

        # --- Colonne de droite ---
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

        # 1. Labels Racines
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(self._get_improved_list_style())
        self.root_list_widget.setMinimumHeight(100)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_root_button = QtWidgets.QPushButton(
            tr("project_config.add_root_button")
        )
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)
        self.edit_root_button = QtWidgets.QPushButton(
            tr("project_config.edit_root_button")
        )
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)
        self.remove_root_button = QtWidgets.QPushButton(
            tr("project_config.remove_root_button")
        )
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)
        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)

        self.modify_category_root_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_root_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_root_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("root")
        )
        self.modify_category_root_button.setEnabled(False)
        root_buttons_layout.addWidget(self.modify_category_root_button)

        hierarchy_group_layout.addLayout(root_buttons_layout)

        # 2. Labels Parents
        parent_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        parent_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(parent_label_title)

        self.parent_list_widget = QtWidgets.QListWidget()
        self.parent_list_widget.setStyleSheet(self._get_improved_list_style())
        self.parent_list_widget.setMinimumHeight(100)
        self.parent_list_widget.currentItemChanged.connect(
            self._on_parent_label_selected
        )
        hierarchy_group_layout.addWidget(self.parent_list_widget)

        parent_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_parent_button = QtWidgets.QPushButton(
            tr("project_config.add_parent_button")
        )
        self.add_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_parent_button.clicked.connect(self._add_parent_label)
        self.edit_parent_button = QtWidgets.QPushButton(
            tr("project_config.edit_parent_button")
        )
        self.edit_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_parent_button.clicked.connect(self._edit_parent_label)
        self.remove_parent_button = QtWidgets.QPushButton(
            tr("project_config.remove_parent_button")
        )
        self.remove_parent_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_parent_button.clicked.connect(self._remove_parent_label)
        parent_buttons_layout.addWidget(self.add_parent_button)
        parent_buttons_layout.addWidget(self.edit_parent_button)
        parent_buttons_layout.addWidget(self.remove_parent_button)

        self.modify_category_parent_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_parent_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_parent_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("parent")
        )
        self.modify_category_parent_button.setEnabled(False)
        parent_buttons_layout.addWidget(self.modify_category_parent_button)

        hierarchy_group_layout.addLayout(parent_buttons_layout)

        # 3. Labels Enfants
        child_label_title = QtWidgets.QLabel(tr("project_config.child_labels_list_label"))
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(100)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_child_button = QtWidgets.QPushButton(
            tr("project_config.add_child_button")
        )
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)
        self.edit_child_button = QtWidgets.QPushButton(
            tr("project_config.edit_child_button")
        )
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)
        self.remove_child_button = QtWidgets.QPushButton(
            tr("project_config.remove_child_button")
        )
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)
        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)

        self.modify_category_child_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_child_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_child_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("child")
        )
        self.modify_category_child_button.setEnabled(False)
        child_buttons_layout.addWidget(self.modify_category_child_button)

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_layout.addWidget(hierarchy_group)

        hierarchy_layout.addStretch()

        right_column_container.setWidget(hierarchy_scroll_content)
        top_columns_layout.addWidget(right_column_container, 4)

    def _update_project_details(self):
        """Met à jour les détails pour le projet."""
        if self.current_project_profile_data:
            self._update_selected_details("Projet", self.current_project_profile_data)

    def _update_selected_details(self, item_type, item_data, source="", target=""):
        """Met à jour l'affichage des détails pour l'item sélectionné."""
        if item_data:
            name = item_data.get("name", item_data.get("label", ""))
            desc = item_data.get("description", "")
            cat = ", ".join(item_data.get("category", []))
            cat_str = f"Catégorie: {cat}" if cat else "Catégorie: "
            source_str = f"Source: {source}" if source else "Source: "
            target_str = f"Cible: {target}" if target else "Cible: "
            files_str = f"Fichiers: {', '.join(item_data.get('files', []))}" if item_data.get('files') else "Fichiers: aucun"

            text = f"{item_type}: {name}\nDescription: {desc}\n{cat_str}\n{files_str}\n{source_str}\n{target_str}"
        else:
            text = ""
        self.details_text.setPlainText(text)

    def _update_selected_details_for_file(self, item_type, filename, content, source=""):
        """Met à jour l'affichage pour un fichier sélectionné."""
        source_str = f"Source: {source}" if source else ""
        text = f"{item_type}: {filename}\n{source_str}"
        self.details_text.setPlainText(text)

    # === SCAN D'UPLOAD DOSSIER ===
    def _scan_project_directory(self, directory):
        """Scanne le dossier projet racine et construit la structure de données."""
        project_name = os.path.basename(directory)
        project_desc = ""
        desc_path = os.path.join(directory, "description.txt")
        if os.path.exists(desc_path):
            with open(desc_path, 'r', encoding='utf-8') as f:
                project_desc = f.read().strip()

        # Collecter les fichiers au niveau projet
        project_files = []
        project_file_contents = {}
        for f in os.listdir(directory):
            fpath = os.path.join(directory, f)
            if os.path.isfile(fpath) and f != "description.txt":
                try:
                    with open(fpath, 'r', encoding='utf-8') as ff:
                        content = ff.read()
                    project_files.append(f)
                    project_file_contents[f] = content
                except Exception as e:
                    logger.warning(f"Impossible de lire {fpath}: {e}")
                    project_files.append(f)
                    project_file_contents[f] = f"(erreur lecture: {e})"

        turing_ontology = {"clusters_detailed": []}
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                cluster_data = self._scan_cluster(item_path, item)
                if cluster_data:
                    turing_ontology["clusters_detailed"].append(cluster_data)

        return {
            "name": project_name,
            "description": project_desc,
            "files": project_files,
            "file_contents": project_file_contents,
            "turing_ontology": turing_ontology,
            "last_modified": datetime.now().isoformat()
        }

    def _scan_cluster(self, cluster_path, cluster_name):
        """Scanne un dossier cluster, incluant le contenu des fichiers."""
        cluster_desc_path = os.path.join(cluster_path, "description.txt")
        cluster_desc = ""
        if os.path.exists(cluster_desc_path):
            with open(cluster_desc_path, 'r', encoding='utf-8') as f:
                cluster_desc = f.read().strip()

        # Collecter tous les fichiers et leur contenu
        files = []
        file_contents = {}
        for f in os.listdir(cluster_path):
            fpath = os.path.join(cluster_path, f)
            if os.path.isfile(fpath) and f != "description.txt":
                try:
                    with open(fpath, 'r', encoding='utf-8') as ff:
                        content = ff.read()
                    files.append(f)
                    file_contents[f] = content
                except Exception as e:
                    logger.warning(f"Impossible de lire {fpath}: {e}")
                    files.append(f)
                    file_contents[f] = f"(erreur lecture: {e})"

        root_labels = []
        for item in os.listdir(cluster_path):
            item_path = os.path.join(cluster_path, item)
            if os.path.isdir(item_path) and item != "description.txt":
                root_data = self._scan_root_label(item_path, item)
                if root_data:
                    root_labels.append(root_data)

        if root_labels or files:  # Inclure même si pas de roots mais des files
            return {
                "name": cluster_name,
                "id": str(uuid.uuid4()),
                "description": cluster_desc,
                "files": files,
                "file_contents": file_contents,
                "root_labels": root_labels
            }
        return None

    def _scan_root_label(self, root_path, root_name):
        """Scanne un dossier label racine, incluant le contenu des fichiers."""
        root_desc_path = os.path.join(root_path, "description.txt")
        root_desc = ""
        if os.path.exists(root_desc_path):
            with open(root_desc_path, 'r', encoding='utf-8') as f:
                root_desc = f.read().strip()

        # Collecter tous les fichiers et leur contenu
        files = []
        file_contents = {}
        for f in os.listdir(root_path):
            fpath = os.path.join(root_path, f)
            if os.path.isfile(fpath) and f != "description.txt":
                try:
                    with open(fpath, 'r', encoding='utf-8') as ff:
                        content = ff.read()
                    files.append(f)
                    file_contents[f] = content
                except Exception as e:
                    logger.warning(f"Impossible de lire {fpath}: {e}")
                    files.append(f)
                    file_contents[f] = f"(erreur lecture: {e})"

        parents = []
        for item in os.listdir(root_path):
            item_path = os.path.join(root_path, item)
            if os.path.isdir(item_path) and item != "description.txt":
                parent_data = self._scan_parent_label(item_path, item)
                if parent_data:
                    parents.append(parent_data)

        return {
            "label": root_name,
            "id": str(uuid.uuid4()),
            "description": root_desc,
            "category": [],
            "files": files,
            "file_contents": file_contents,
            "parents": parents
        }

    def _scan_parent_label(self, parent_path, parent_name):
        """Scanne un dossier label parent, incluant le contenu des fichiers."""
        parent_desc_path = os.path.join(parent_path, "description.txt")
        parent_desc = ""
        if os.path.exists(parent_desc_path):
            with open(parent_desc_path, 'r', encoding='utf-8') as f:
                parent_desc = f.read().strip()

        # Collecter tous les fichiers et leur contenu
        files = []
        file_contents = {}
        for f in os.listdir(parent_path):
            fpath = os.path.join(parent_path, f)
            if os.path.isfile(fpath) and f != "description.txt":
                try:
                    with open(fpath, 'r', encoding='utf-8') as ff:
                        content = ff.read()
                    files.append(f)
                    file_contents[f] = content
                except Exception as e:
                    logger.warning(f"Impossible de lire {fpath}: {e}")
                    files.append(f)
                    file_contents[f] = f"(erreur lecture: {e})"

        children = []
        for item in os.listdir(parent_path):
            item_path = os.path.join(parent_path, item)
            if os.path.isdir(item_path) and item != "description.txt":
                child_data = self._scan_child_label(item_path, item)
                if child_data:
                    children.append(child_data)

        return {
            "label": parent_name,
            "id": str(uuid.uuid4()),
            "description": parent_desc,
            "category": [],
            "files": files,
            "file_contents": file_contents,
            "children": children
        }

    def _scan_child_label(self, child_path, child_name):
        """Scanne un dossier label enfant, incluant le contenu des fichiers."""
        child_desc_path = os.path.join(child_path, "description.txt")
        child_desc = ""
        if os.path.exists(child_desc_path):
            with open(child_desc_path, 'r', encoding='utf-8') as f:
                child_desc = f.read().strip()

        # Collecter tous les fichiers et leur contenu
        files = []
        file_contents = {}
        for f in os.listdir(child_path):
            fpath = os.path.join(child_path, f)
            if os.path.isfile(fpath) and f != "description.txt":
                try:
                    with open(fpath, 'r', encoding='utf-8') as ff:
                        content = ff.read()
                    files.append(f)
                    file_contents[f] = content
                except Exception as e:
                    logger.warning(f"Impossible de lire {fpath}: {e}")
                    files.append(f)
                    file_contents[f] = f"(erreur lecture: {e})"

        return {
            "label": child_name,
            "id": str(uuid.uuid4()),
            "description": child_desc,
            "category": [],
            "files": files,
            "file_contents": file_contents
        }

    # === GESTION DES CLUSTERS ===
    def _add_cluster(self):
        """Ajoute un nouveau cluster avec dialogue pour nom et description."""
        if not self.current_project_name:
            return

        dialog = AddEditItemDialog("Ajouter un Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "id": str(uuid.uuid4()),
                    "description": data["description"],
                    "files": [],
                    "file_contents": {},
                    "root_labels": [],
                }
                turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
                clusters_detailed = turing_ontology.get("clusters_detailed", [])
                clusters_detailed.append(new_cluster)
                turing_ontology["clusters_detailed"] = clusters_detailed
                self.current_project_profile_data["turing_ontology"] = turing_ontology
                self._refresh_cluster_list()
                self.cluster_list_widget.setCurrentRow(len(clusters_detailed) - 1)
                logger.info(f"Cluster ajouté : {data['name']}")

    def _edit_cluster(self):
        """Édite le cluster sélectionné avec dialogue pour nom et description."""
        if not self.current_cluster_data:
            return

        dialog = AddEditItemDialog(
            "Éditer le Cluster",
            current_name=self.current_cluster_data["name"],
            current_description=self.current_cluster_data.get("description", ""),
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                self.current_cluster_data["name"] = data["name"]
                self.current_cluster_data["description"] = data["description"]
                self._refresh_cluster_list()
                self._update_selected_details("Cluster", self.current_cluster_data)
                logger.info(f"Cluster modifié : {data['name']}")

    def _remove_cluster(self):
        """Supprime le cluster sélectionné et sa hiérarchie."""
        if not self.current_cluster_data:
            return
    
        cluster_name = self.current_cluster_data["name"]  # Sauvegarder le nom AVANT la suppression
        
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.remove_cluster_title"),
            tr("project_config.remove_cluster_msg").format(cluster=cluster_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
            clusters_detailed = turing_ontology.get("clusters_detailed", [])
            clusters_detailed.pop(self.current_cluster_index)
            turing_ontology["clusters_detailed"] = clusters_detailed
            self.current_project_profile_data["turing_ontology"] = turing_ontology
            self._refresh_cluster_list()
            self._reset_hierarchy_ui()
            self._update_project_details()
            logger.info(f"Cluster supprimé : {cluster_name}")  # Utiliser la variable sauvegardée

    # === GESTION DES LABELS RACINES ===
    def _add_root_label(self):
        """Ajoute un nouveau label racine avec dialogue pour nom et description."""
        if not self.current_cluster_data:
            return

        dialog = AddEditItemDialog("Ajouter un Label Racine", parent=self)
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
                }
                self.current_cluster_data["root_labels"].append(new_root)
                self._refresh_root_list()
                self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
                logger.info(f"Label racine ajouté : {data['name']}")

    def _edit_root_label(self):
        """Édite le label racine sélectionné avec dialogue pour nom et description."""
        if self.current_root_label_index < 0 or self.current_root_is_file:
            return

        current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
        dialog = AddEditItemDialog(
            "Éditer le Label Racine",
            current_name=current_root["label"],
            current_description=current_root.get("description", ""),
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                current_root["label"] = data["name"]
                current_root["description"] = data["description"]
                self._refresh_root_list()
                self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"])
                logger.info(f"Label racine modifié : {data['name']}")

    def _remove_root_label(self):
        """Supprime le label racine sélectionné."""
        if self.current_root_label_index < 0 or self.current_root_is_file:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmer suppression",
            f"Supprimer le label racine '{self.current_cluster_data['root_labels'][self.current_root_label_index]['label']}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data["root_labels"][self.current_root_label_index]
            self._refresh_root_list()
            self._reset_hierarchy_ui()
            if self.current_cluster_data:
                self._update_selected_details("Cluster", self.current_cluster_data, target=f"Labels racines: {len(self.current_cluster_data.get('root_labels', []))}")
            else:
                self._update_project_details()
            logger.info("Label racine supprimé")

    # === GESTION DES LABELS PARENTS ===
    def _add_parent_label(self):
        """Ajoute un nouveau label parent sous le root sélectionné."""
        if self.current_root_label_index < 0 or self.current_root_is_file:
            return
        current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
        dialog = AddEditItemDialog("Ajouter un Label Parent", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_parent = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "children": [],
                }
                current_root["parents"].append(new_parent)
                self._refresh_parent_list()
                self.parent_list_widget.setCurrentRow(self.parent_list_widget.count() - 1)
                logger.info(f"Label parent ajouté : {data['name']}")

    def _edit_parent_label(self):
        """Édite le label parent sélectionné."""
        if self.current_parent_label_index < 0 or self.current_parent_is_file:
            return
        current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
        current_parent = current_root["parents"][self.current_parent_label_index]
        dialog = AddEditItemDialog(
            "Éditer le Label Parent",
            current_name=current_parent["label"],
            current_description=current_parent.get("description", ""),
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                current_parent["label"] = data["name"]
                current_parent["description"] = data["description"]
                self._refresh_parent_list()
                target = f"Enfants: {len(current_parent.get('children', []))}"
                self._update_selected_details("Label Parent", current_parent, source=current_root["label"], target=target)
                logger.info(f"Label parent modifié : {data['name']}")

    def _remove_parent_label(self):
        """Supprime le label parent sélectionné."""
        if self.current_parent_label_index < 0 or self.current_parent_is_file:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmer suppression",
            f"Supprimer le label parent '{self.current_cluster_data['root_labels'][self.current_root_label_index]['parents'][self.current_parent_label_index]['label']}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            del current_root["parents"][self.current_parent_label_index]
            self._refresh_parent_list()
            self._reset_child_ui()
            self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"], target=f"Parents: {len(current_root.get('parents', []))}")
            logger.info("Label parent supprimé")

    # === GESTION DES LABELS ENFANTS ===
    def _add_child_label(self):
        """Ajoute un nouveau label enfant sous le parent sélectionné."""
        if self.current_parent_label_index < 0 or self.current_parent_is_file:
            return
        current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
        current_parent = current_root["parents"][self.current_parent_label_index]
        dialog = AddEditItemDialog("Ajouter un Label Enfant", parent=self)
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
                }
                current_parent["children"].append(new_child)
                self._refresh_child_list()
                self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
                logger.info(f"Label enfant ajouté : {data['name']}")

    def _edit_child_label(self):
        """Édite le label enfant sélectionné."""
        if self.current_child_label_index < 0 or self.current_child_is_file:
            return
        current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
        current_parent = current_root["parents"][self.current_parent_label_index]
        current_child = current_parent["children"][self.current_child_label_index]
        dialog = AddEditItemDialog(
            "Éditer le Label Enfant",
            current_name=current_child["label"],
            current_description=current_child.get("description", ""),
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                current_child["label"] = data["name"]
                current_child["description"] = data["description"]
                self._refresh_child_list()
                self._update_selected_details("Label Enfant", current_child, source=current_parent["label"])
                logger.info(f"Label enfant modifié : {data['name']}")

    def _remove_child_label(self):
        """Supprime le label enfant sélectionné."""
        if self.current_child_label_index < 0 or self.current_child_is_file:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmer suppression",
            f"Supprimer le label enfant '{self.current_cluster_data['root_labels'][self.current_root_label_index]['parents'][self.current_parent_label_index]['children'][self.current_child_label_index]['label']}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            current_parent = current_root["parents"][self.current_parent_label_index]
            del current_parent["children"][self.current_child_label_index]
            self._refresh_child_list()
            target = f"Enfants: {len(current_parent.get('children', []))}"
            self._update_selected_details("Label Parent", current_parent, source=current_root["label"], target=target)
            logger.info("Label enfant supprimé")

    # === GESTION DE LA HIÉRARCHIE ===
    def _on_cluster_selected(self, current, previous):
        """Gère la sélection d'un cluster ou fichier de niveau supérieur."""
        self.current_cluster_index = -1
        self.current_cluster_data = None
        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        turing_ontology = self.current_project_profile_data.get("turing_ontology", {}) if self.current_project_profile_data else {}
        clusters = turing_ontology.get("clusters_detailed", [])

        if current:
            item_text = current.text()
            if item_text.startswith("📄 "):
                self.current_top_level_is_file = True
                self.current_top_level_filename = item_text[2:]
                content = self.current_project_profile_data.get("file_contents", {}).get(self.current_top_level_filename, "(contenu non disponible)")
                self._update_selected_details_for_file("Fichier (Projet)", self.current_top_level_filename, content)
                self._reset_hierarchy_ui()
            else:
                self.current_top_level_is_file = False
                self.current_cluster_index = self._find_cluster_index_by_name(item_text, clusters)
                if self.current_cluster_index >= 0:
                    self.current_cluster_data = clusters[self.current_cluster_index]
                    target = f"Labels racines: {len(self.current_cluster_data.get('root_labels', []))}"
                    self._update_selected_details("Cluster", self.current_cluster_data, target=target)
                    self._refresh_root_list()
                else:
                    # Inconnu, reset
                    self._update_project_details()
                    self._reset_hierarchy_ui()
        else:
            self._update_project_details()
            self._reset_hierarchy_ui()
        self._update_hierarchy_button_states()

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters et fichiers de niveau supérieur, dossiers en haut, fichiers en bas."""
        self.cluster_list_widget.clear()
        if self.current_project_profile_data:
            turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
            clusters = turing_ontology.get("clusters_detailed", [])
            files = self.current_project_profile_data.get("files", [])
            # Dossiers (clusters) en premier, triés
            cluster_items = sorted([(cluster["name"], "cluster") for cluster in clusters], key=lambda x: x[0].lower())
            for name, _ in cluster_items:
                self.cluster_list_widget.addItem(name)
            # Fichiers ensuite, triés
            file_items = sorted(files)
            for f in file_items:
                self.cluster_list_widget.addItem(f"📄 {f}")

    def _find_cluster_index_by_name(self, item_text, clusters_list):
        """Trouve l'index d'un cluster par son nom dans la liste."""
        for i, cluster in enumerate(clusters_list):
            if cluster["name"] == item_text:
                return i
        return -1

    def _get_grouped_items(self, labels_list, files_list):
        """Retourne d'abord les labels triés, puis les fichiers triés."""
        # Labels en premier, triés
        label_items = sorted([(label["label"], "label") for label in labels_list], key=lambda x: x[0].lower())
        # Fichiers ensuite, triés
        file_items = sorted([(f, "file") for f in files_list], key=lambda x: x[0].lower())
        return label_items + file_items

    def _find_label_index_by_name(self, item_text, labels_list):
        """Trouve l'index d'un label par son nom dans la liste."""
        for i, label in enumerate(labels_list):
            if label["label"] == item_text:
                return i
        return -1

    def _on_root_label_selected(self, current, previous):
        """Gère la sélection d'un label racine ou fichier."""
        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None
        self.current_parent_label_index = -1
        self.current_parent_is_file = False
        self.current_parent_filename = None
        self.current_child_label_index = -1
        self.current_child_is_file = False
        self.current_child_filename = None

        if not self.current_cluster_data:
            self._update_project_details()
            self._reset_parent_ui()
            self._update_hierarchy_button_states()
            return

        # Niveau cluster
        if current:
            item_text = current.text()
            if item_text.startswith("📄 "):
                self.current_root_is_file = True
                self.current_root_filename = item_text[2:]
                self._update_selected_details_for_file("Fichier (Cluster)", self.current_root_filename, self.current_cluster_data["file_contents"].get(self.current_root_filename, ""))
                self._reset_parent_ui()
            else:
                # Chercher l'index dans root_labels
                self.current_root_label_index = self._find_label_index_by_name(item_text, self.current_cluster_data.get("root_labels", []))
                if self.current_root_label_index >= 0:
                    current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
                    target = f"Parents: {len(current_root.get('parents', []))}"
                    self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"], target=target)
                    self._refresh_parent_list()
                else:
                    # Inconnu, reset
                    self._reset_parent_ui()
        else:
            if self.current_cluster_data:
                target = f"Labels racines: {len(self.current_cluster_data.get('root_labels', []))}"
                self._update_selected_details("Cluster", self.current_cluster_data, target=target)
            self._reset_parent_ui()
        self._update_hierarchy_button_states()

    def _refresh_root_list(self):
        """Rafraîchit la liste des labels racines et fichiers du cluster, dossiers en haut, fichiers en bas."""
        self.root_list_widget.clear()
        if self.current_cluster_data:
            items = self._get_grouped_items(self.current_cluster_data.get("root_labels", []), self.current_cluster_data.get("files", []))
            for name, item_type in items:
                if item_type == "file":
                    self.root_list_widget.addItem(f"📄 {name}")
                else:
                    self.root_list_widget.addItem(name)

    def _on_parent_label_selected(self, current, previous):
        """Gère la sélection d'un label parent ou fichier."""
        self.current_parent_label_index = -1
        self.current_parent_is_file = False
        self.current_parent_filename = None
        self.current_child_label_index = -1
        self.current_child_is_file = False
        self.current_child_filename = None
    
        # ✅ CORRECTION : Vérifications de sécurité
        if not self.current_cluster_data:
            self._update_project_details()
            self._reset_child_ui()
            self._update_hierarchy_button_states()
            return
        
        if self.current_root_label_index < 0 or self.current_root_label_index >= len(self.current_cluster_data.get("root_labels", [])):
            self._update_project_details()
            self._reset_child_ui()
            self._update_hierarchy_button_states()
            return
    
        if current and self.current_root_label_index >= 0 and not self.current_root_is_file:
            item_text = current.text()
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            
            if item_text.startswith("📄 "):
                self.current_parent_is_file = True
                self.current_parent_filename = item_text[2:]
                self._update_selected_details_for_file("Fichier (Root)", self.current_parent_filename, current_root.get("file_contents", {}).get(self.current_parent_filename, ""), source=current_root["label"])
                self._reset_child_ui()
            else:
                # Chercher l'index dans parents
                self.current_parent_label_index = self._find_label_index_by_name(item_text, current_root.get("parents", []))
                if self.current_parent_label_index >= 0:
                    current_parent = current_root["parents"][self.current_parent_label_index]
                    target = f"Enfants: {len(current_parent.get('children', []))}"
                    self._update_selected_details("Label Parent", current_parent, source=current_root["label"], target=target)
                    self._refresh_child_list()
                else:
                    # Inconnu, reset
                    self._reset_child_ui()
        else:
            # Gestion des cas de désélection avec vérifications
            if self.current_root_label_index >= 0 and not self.current_root_is_file:
                if self.current_root_label_index < len(self.current_cluster_data.get("root_labels", [])):
                    current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
                    target = f"Parents: {len(current_root.get('parents', []))}"
                    self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"], target=target)
            elif self.current_cluster_index >= 0 and self.current_cluster_data:
                target = f"Labels racines: {len(self.current_cluster_data.get('root_labels', []))}"
                self._update_selected_details("Cluster", self.current_cluster_data, target=target)
            else:
                self._update_project_details()
            self._reset_child_ui()
        
        self._update_hierarchy_button_states()

    def _refresh_parent_list(self):
        """Rafraîchit la liste des labels parents et fichiers du root, dossiers en haut, fichiers en bas."""
        self.parent_list_widget.clear()
        if self.current_root_label_index >= 0 and self.current_cluster_data and not self.current_root_is_file:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            items = self._get_grouped_items(current_root.get("parents", []), current_root.get("files", []))
            for name, item_type in items:
                if item_type == "file":
                    self.parent_list_widget.addItem(f"📄 {name}")
                else:
                    self.parent_list_widget.addItem(name)

    def _on_child_label_selected(self, current, previous):
        """Gère la sélection d'un label enfant ou fichier."""
        self.current_child_label_index = -1
        self.current_child_is_file = False
        self.current_child_filename = None

        # ✅ CORRECTION : Vérification complète avant accès
        if not self.current_cluster_data:
            self._update_project_details()
            self._update_hierarchy_button_states()
            return

        if self.current_root_label_index < 0 or self.current_root_label_index >= len(self.current_cluster_data.get("root_labels", [])):
            self._update_project_details()
            self._update_hierarchy_button_states()
            return

        if current and self.current_parent_label_index >= 0 and not self.current_parent_is_file:
            item_text = current.text()
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]

            # ✅ Vérification que parents existe
            if self.current_parent_label_index >= len(current_root.get("parents", [])):
                self._update_project_details()
                self._update_hierarchy_button_states()
                return

            current_parent = current_root["parents"][self.current_parent_label_index]

            if item_text.startswith("📄 "):
                self.current_child_is_file = True
                self.current_child_filename = item_text[2:]
                self._update_selected_details_for_file("Fichier (Parent)", self.current_child_filename, current_parent.get("file_contents", {}).get(self.current_child_filename, ""), source=current_parent["label"])
            else:
                # Chercher l'index dans children
                self.current_child_label_index = self._find_label_index_by_name(item_text, current_parent.get("children", []))
                if self.current_child_label_index >= 0:
                    current_child = current_parent["children"][self.current_child_label_index]
                    self._update_selected_details("Label Enfant", current_child, source=current_parent["label"])
        else:
            if self.current_parent_label_index >= 0 and not self.current_parent_is_file:
                current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
                if self.current_parent_label_index < len(current_root.get("parents", [])):
                    current_parent = current_root["parents"][self.current_parent_label_index]
                    target = f"Enfants: {len(current_parent.get('children', []))}"
                    self._update_selected_details("Label Parent", current_parent, source=current_root["label"], target=target)
            elif self.current_root_label_index >= 0 and not self.current_root_is_file:
                current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
                target = f"Parents: {len(current_root.get('parents', []))}"
                self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"], target=target)
            elif self.current_cluster_index >= 0:
                target = f"Labels racines: {len(self.current_cluster_data.get('root_labels', []))}"
                self._update_selected_details("Cluster", self.current_cluster_data, target=target)
            else:
                self._update_project_details()

        self._update_hierarchy_button_states()

    def _refresh_child_list(self):
        """Rafraîchit la liste des labels enfants et fichiers du parent, dossiers en haut, fichiers en bas."""
        self.child_list_widget.clear()
        if self.current_parent_label_index >= 0 and self.current_root_label_index >= 0 and self.current_cluster_data and not self.current_parent_is_file:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            current_parent = current_root["parents"][self.current_parent_label_index]
            items = self._get_grouped_items(current_parent.get("children", []), current_parent.get("files", []))
            for name, item_type in items:
                if item_type == "file":
                    self.child_list_widget.addItem(f"📄 {name}")
                else:
                    self.child_list_widget.addItem(name)

    def _reset_hierarchy_ui(self):
        """Réinitialise l'UI de la hiérarchie."""
        self._reset_parent_ui()
        self.root_list_widget.clear()

    def _reset_parent_ui(self):
        """Réinitialise l'UI des parents et enfants."""
        self._reset_child_ui()
        self.parent_list_widget.clear()

    def _reset_child_ui(self):
        """Réinitialise l'UI des enfants."""
        self.child_list_widget.clear()

    def _modify_category_for_selected_label(self, level_type):
        """Modifie les catégories pour le label sélectionné."""
        if level_type == "root" and self.current_root_label_index >= 0 and not self.current_root_is_file:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            dialog = CategoryEditDialog(current_root["category"], self)
        elif level_type == "parent" and self.current_parent_label_index >= 0 and not self.current_parent_is_file:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            current_parent = current_root["parents"][self.current_parent_label_index]
            dialog = CategoryEditDialog(current_parent["category"], self)
        elif level_type == "child" and self.current_child_label_index >= 0 and not self.current_child_is_file:
            current_root = self.current_cluster_data["root_labels"][self.current_root_label_index]
            current_parent = current_root["parents"][self.current_parent_label_index]
            current_child = current_parent["children"][self.current_child_label_index]
            dialog = CategoryEditDialog(current_child["category"], self)
        else:
            return

        if dialog.exec_() == QDialog.Accepted:
            new_categories = dialog.get_categories()
            if level_type == "root":
                current_root["category"] = new_categories
                target = f"Parents: {len(current_root.get('parents', []))}"
                self._update_selected_details("Label Racine", current_root, source=self.current_cluster_data["name"], target=target)
            elif level_type == "parent":
                current_parent["category"] = new_categories
                target = f"Enfants: {len(current_parent.get('children', []))}"
                self._update_selected_details("Label Parent", current_parent, source=current_root["label"], target=target)
            elif level_type == "child":
                current_child["category"] = new_categories
                self._update_selected_details("Label Enfant", current_child, source=current_parent["label"])
            logger.info(f"Catégories modifiées pour {level_type} label.")

    # === ÉTATS DES BOUTONS ===
    def _update_hierarchy_button_states(self):
        """Met à jour l'état des boutons de la hiérarchie."""
        has_cluster = bool(self.current_cluster_data)
        has_root_label = self.current_root_label_index >= 0 and not self.current_root_is_file
        has_root_file = self.current_root_is_file
        has_parent_label = self.current_parent_label_index >= 0 and not self.current_parent_is_file
        has_parent_file = self.current_parent_is_file
        has_child_label = self.current_child_label_index >= 0 and not self.current_child_is_file
        has_child_file = self.current_child_is_file

        self.edit_cluster_button.setEnabled(has_cluster)
        self.remove_cluster_button.setEnabled(has_cluster)
        self.import_folder_button.setEnabled(has_cluster)

        self.add_root_button.setEnabled(has_cluster)
        self.edit_root_button.setEnabled(has_root_label)
        self.remove_root_button.setEnabled(has_root_label)
        self.modify_category_root_button.setEnabled(has_root_label)

        self.add_parent_button.setEnabled(has_root_label)
        self.edit_parent_button.setEnabled(has_parent_label)
        self.remove_parent_button.setEnabled(has_parent_label)
        self.modify_category_parent_button.setEnabled(has_parent_label)

        self.add_child_button.setEnabled(has_parent_label)
        self.edit_child_button.setEnabled(has_child_label)
        self.remove_child_button.setEnabled(has_child_label)
        self.modify_category_child_button.setEnabled(has_child_label)

    def _update_button_states(self):
        """Met à jour l'état des boutons généraux."""
        has_project = bool(self.current_project_name)
        self.delete_project_button.setEnabled(has_project)
        self.save_button.setEnabled(has_project)
        self.insert_dgraph_button.setEnabled(has_project and self.is_configured())
        self.export_profile_button.setEnabled(has_project)
        self.add_cluster_button.setEnabled(has_project)
        self._update_hierarchy_button_states()

    def _on_upload_local_project(self):
        """Charge un projet local depuis un dossier entier avec scan hiérarchique."""
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet")
        if directory:
            try:
                local_data = self._scan_project_directory(directory)
                project_name = local_data["name"]
                if not project_name:
                    QtWidgets.QMessageBox.warning(self, "Erreur", "Le dossier sélectionné ne peut pas être utilisé comme projet (nom manquant).")
                    return
                if project_name in self.project_profiles:
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "Projet existant",
                        f"Le projet '{project_name}' existe déjà. Remplacer ?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    )
                    if reply != QtWidgets.QMessageBox.Yes:
                        return
                self.project_profiles[project_name] = local_data
                self._update_project_combo()
                self.project_combo.setCurrentText(project_name)
                self._on_project_selected(self.project_combo.currentIndex())
                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' uploadé depuis le dossier {directory}.")
                logger.info(f"Projet local uploadé : {project_name} depuis {directory}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec de l'upload : {str(e)}")
                logger.error(f"Erreur upload local : {str(e)}")

    # === SAUVEGARDE ET CHARGEMENT ===
    def _on_save_profile(self):
        """Sauvegarde le profil actuel (local + Dgraph)."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, tr("project_config.save_title"), tr("project_config.no_project_save_msg"))
            return

        old_project_name = None
        current_name_in_edit = self.project_name_edit.text().strip()
        if current_name_in_edit and current_name_in_edit != self.current_project_name:
            old_project_name = self.current_project_name
            rename = True
        else:
            current_name_in_edit = self.current_project_name
            rename = False

        self.current_project_profile_data["name"] = current_name_in_edit
        self.current_project_profile_data["description"] = self.project_description_edit.toPlainText().strip()
        self.current_project_profile_data["last_modified"] = datetime.now().isoformat()

        if rename:
            if not self.dgraph_connector.client:
                self.dgraph_connector.connect()
            query_result = self.dgraph_connector.query_workspaces()
            if query_result is None:
                logger.error("Query workspaces failed during rename check.")
                QtWidgets.QMessageBox.critical(self, "Erreur Dgraph", "Impossible de vérifier les projets existants. Sauvegarde annulée.")
                return
            new_exists = any(item.get('name') == current_name_in_edit for item in query_result.get('q', []))
            if new_exists:
                QtWidgets.QMessageBox.warning(self, tr("project_config.duplicate_title"), "Nom de projet déjà existant dans Dgraph.")
                return
            old_exists = any(item.get('name') == old_project_name for item in query_result.get('q', []))
            if old_exists:
                old_uid = next((item['uid'] for item in query_result['q'] if item['name'] == old_project_name), None)
                if old_uid:
                    to_delete = self._collect_uids_to_delete(old_uid)
                    self._collect_and_delete_uids(to_delete)
                    logger.info(f"Supprimé ancien workspace pour rename : {old_project_name}")
            self.current_project_name = current_name_in_edit
            rename = True

        if not rename:
            if not self.dgraph_connector.client:
                self.dgraph_connector.connect()
            query_result = self.dgraph_connector.query_workspaces()
            if query_result is None:
                logger.error("Query workspaces failed during existence check.")
                QtWidgets.QMessageBox.critical(self, "Erreur Dgraph", "Impossible de vérifier le projet existant. Sauvegarde annulée.")
                return
            exists = any(item.get('name') == self.current_project_name for item in query_result.get('q', []))
            if exists:
                uid = next((item['uid'] for item in query_result['q'] if item['name'] == self.current_project_name), None)
                if uid:
                    to_delete = self._collect_uids_to_delete(uid)
                    self._collect_and_delete_uids(to_delete)
                    logger.info(f"Supprimé workspace existant pour modification : {self.current_project_name}")

        self.project_profiles[self.current_project_name] = self.current_project_profile_data
        
        mutations = self._generate_dgraph_mutations(self.current_project_profile_data)
        success = self.dgraph_connector.insert_mutations(mutations)
        
        if success:
            self._load_project_profiles()
            self._update_project_combo()
            self.project_combo.setCurrentText(self.current_project_name)
            self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
            logger.info(f"Projet '{self.current_project_name}' modifié/sauvegardé.")
            QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{self.current_project_name}' modifié avec succès dans Dgraph.")
        else:
            logger.error("Échec insertion Dgraph lors de la modification.")
            QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la modification dans Dgraph.")

    def _on_export_profile(self):
        """Exporte le profil actuel vers un fichier JSON."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné pour exporter.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le profil de projet",
            f"{self.current_project_name}.json",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                export_data = {
                    "name": self.current_project_name,
                    "description": self.project_description_edit.toPlainText().strip(),
                    "files": self.current_project_profile_data.get("files", []),
                    "file_contents": self.current_project_profile_data.get("file_contents", {}),
                    "turing_ontology": self.current_project_profile_data.get("turing_ontology", {}),
                    "exported_at": datetime.now().isoformat()
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=4, ensure_ascii=False)
                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{self.current_project_name}' exporté vers {file_path}.")
                logger.info(f"Projet exporté : {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec de l'export : {str(e)}")
                logger.error(f"Erreur export : {str(e)}")

    def _on_insert_dgraph(self):
        """Insère directement l'ontologie du projet actuel dans Dgraph."""
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.insert_dgraph_title"),
                tr("project_config.no_project_data_insert_msg"),
            )
            return

        if not self.is_configured():
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.insert_dgraph_title"),
                tr("project_config.not_configured_insert_msg"),
            )
            return

        if not self.dgraph_connector.client:
            reply = QtWidgets.QMessageBox.question(
                self,
                tr("project_config.insert_dgraph_title"),
                "Connexion à Dgraph non disponible. Voulez-vous réessayer de vous connecter ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                if not self.dgraph_connector.connect():
                    QtWidgets.QMessageBox.critical(
                        self,
                        tr("project_config.insert_dgraph_title"),
                        "Impossible de se connecter à Dgraph. Vérifiez que Dgraph est démarré.",
                    )
                    return
            else:
                return

        try:
            mutations = self._generate_dgraph_mutations(self.current_project_profile_data)

            if not mutations:
                logger.info("Aucune mutation à effectuer pour les données du projet actuel.")
                return

            success = self.dgraph_connector.insert_mutations(mutations)

            if success:
                QtWidgets.QMessageBox.information(
                    self,
                    tr("project_config.insert_dgraph_title"),
                    tr("project_config.insert_dgraph_success_msg").format(
                        project_name=self.current_project_name
                    ),
                )
                logger.info(f"Ontologie insérée avec succès dans Dgraph pour le projet : {self.current_project_name}")
                self.dgraph_connector.open_ratel()
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("project_config.insert_dgraph_title"),
                    "Échec de l'insertion dans Dgraph.",
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'insertion dans Dgraph : {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.insert_dgraph_title"),
                tr("project_config.insert_dgraph_error_msg").format(error=str(e)),
            )

    def _generate_dgraph_mutations(self, project_data):
        """Génère la liste des mutations Dgraph à partir des données du projet."""
        USER_ID = self.conductor.get_current_user_id() if hasattr(self.conductor, 'get_current_user_id') else str(uuid.uuid4())
        WORKSPACE_ID = str(uuid.uuid4())

        mutations = []
        
        turing_ontology = project_data.get("turing_ontology", {})
        clusters_detailed_from_project = turing_ontology.get("clusters_detailed", [])

        cluster_uuid_to_blank_uid_map = {} 
        all_cluster_blank_uids_for_workspace = []

        for i, cluster_data in enumerate(clusters_detailed_from_project):
            cluster_name = cluster_data["name"]
            cluster_unique_id = cluster_data["id"]
            cluster_blank_uid = f"_:cluster_{cluster_unique_id.replace('-', '_')}"
            
            cluster_uuid_to_blank_uid_map[cluster_unique_id] = cluster_blank_uid

            now_iso = datetime.now().isoformat() + "Z"
            
            file_contents_str = json.dumps(cluster_data.get("file_contents", {}))
            
            cluster_mutation = {
                "uid": cluster_blank_uid,
                "dgraph.type": "Cluster",
                "id": str(cluster_unique_id),
                "name": cluster_name,
                "description": cluster_data.get("description", ""),
                "files": cluster_data.get("files", []),
                "fileContents": file_contents_str,
                "userId": USER_ID,
                "createdAt": now_iso,
                "updatedAt": now_iso,
            }
            mutations.append(cluster_mutation)
            
            all_cluster_blank_uids_for_workspace.append(cluster_blank_uid)
            logger.debug(f"Prepared cluster: {cluster_name} (ID: {cluster_unique_id})")

        workspace_unique_id = WORKSPACE_ID
        now_iso = datetime.now().isoformat() + "Z"
        
        clusters_list = [{"uid": blank_uid} for blank_uid in all_cluster_blank_uids_for_workspace]
        
        workspace_name = project_data.get("name", "")
        workspace_description = project_data.get("description", "")
        files = project_data.get("files", [])
        file_contents_str = json.dumps(project_data.get("file_contents", {}))
        workspace_mutation = {
            "uid": f"_:workspace_node",
            "dgraph.type": "Workspace",
            "name": workspace_name,
            "description": workspace_description,
            "files": files,
            "fileContents": file_contents_str,
            "id": workspace_unique_id,
            "ownerId": USER_ID,
            "updatedAt": now_iso,
            "clusterManagement": {
                "uid": f"_:cluster_management_node",
                "dgraph.type": "ClusterManagement",
                "lastUpdated": now_iso,
                "version": "1.0",
                "clusters": clusters_list
            }
        }
        mutations.append(workspace_mutation)
        logger.debug(f"Prepared Workspace (ID: {workspace_unique_id})")

        def _process_label_hierarchy(label_data, level_numeric, parent_uid_for_relation, current_path_ids, containing_cluster_unique_id, containing_cluster_blank_uid, all_mutations):
            label_name = label_data.get("label", label_data.get("name", ""))
            label_category = label_data.get("category", [])
            if isinstance(label_category, str):
                label_category = [label_category]
            elif label_category is None:
                label_category = []
            if not isinstance(label_category, list):
                label_category = []
            
            label_unique_id = label_data.get("id", str(uuid.uuid4()))
            label_blank_uid = f"_:label_{label_unique_id.replace('-', '_')}"
            
            if level_numeric == 0:
                full_path = "/"
            else:
                full_path = "/".join(current_path_ids) + "/"
            now_iso = datetime.now().isoformat() + "Z"
            
            file_contents_str = json.dumps(label_data.get("file_contents", {}))
            
            label_node = {
                "uid": label_blank_uid,
                "dgraph.type": "Label",
                "id": label_unique_id,
                "name": label_name,
                "level": level_numeric,
                "path": full_path,
                "category": label_category,
                "description": label_data.get("description", ""),
                "files": label_data.get("files", []),
                "fileContents": file_contents_str,
                "createdAt": now_iso,
                "updatedAt": now_iso,
            }
            if parent_uid_for_relation:
                label_node["parents"] = [{"uid": parent_uid_for_relation}]
                if current_path_ids:
                    label_node["parentId"] = current_path_ids[-1] 
                else:
                    label_node["parentId"] = ""
            if containing_cluster_unique_id and containing_cluster_blank_uid:
                label_node["clusters"] = [{"uid": containing_cluster_blank_uid}]
            all_mutations.append(label_node)
            next_level_numeric = level_numeric + 1
            children_list_key = None
            if level_numeric == 0:
                children_list_key = "parents" 
            elif level_numeric == 1:
                children_list_key = "children"
            if children_list_key and children_list_key in label_data:
                for child_label_data in label_data[children_list_key]:
                    _process_label_hierarchy(
                        child_label_data,
                        next_level_numeric,
                        label_blank_uid,
                        current_path_ids + [label_unique_id],
                        containing_cluster_unique_id,
                        containing_cluster_blank_uid,
                        all_mutations
                    )

        # Process all labels from clusters (moved outside the nested function)
        for cluster_data in clusters_detailed_from_project:
            cluster_name = cluster_data["name"]
            current_cluster_unique_id = cluster_data["id"]
            current_cluster_blank_uid = cluster_uuid_to_blank_uid_map.get(current_cluster_unique_id)

            if not current_cluster_unique_id or not current_cluster_blank_uid:
                logger.warning(f"Could not find Dgraph ID/UID for cluster '{cluster_name}'.")
                continue

            root_labels_of_this_cluster = cluster_data.get("root_labels", [])
            for root_label in root_labels_of_this_cluster:
                _process_label_hierarchy(
                    root_label,
                    0,
                    None,
                    [],
                    current_cluster_unique_id,
                    current_cluster_blank_uid,
                    mutations
                )
        
        return mutations

    def _load_project_profiles(self):
        """Charge tous les profils de projet depuis Dgraph."""
        try:
            dgraph_profiles = {}
            if self.dgraph_connector.client or self.dgraph_connector.connect():
                logger.info("Chargement des profils depuis Dgraph...")
                dgraph_profiles = self._load_profiles_from_dgraph_internal()
                if dgraph_profiles:
                    logger.info(f"{len(dgraph_profiles)} profils chargés depuis Dgraph.")
                    self.project_profiles = dgraph_profiles
                else:
                    logger.warning("Aucun profil trouvé dans Dgraph.")

            self._update_project_combo()

            if self.project_profiles:
                first_project_name = sorted(self.project_profiles.keys())[0]
                self.project_combo.setCurrentText(first_project_name)
                self.current_project_name = first_project_name
                self.current_project_profile_data = json.loads(
                    json.dumps(self.project_profiles[first_project_name])
                )
                self._load_project_data_into_ui()
                self.delete_project_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.insert_dgraph_button.setEnabled(self.is_configured())
            else:
                logger.info("Aucun profil trouvé, démarrage vide.")
                self._reset_ui()

            self._update_button_states()

        except Exception as e:
            logger.error(f"Erreur critique lors du chargement : {str(e)}")
            self.project_profiles = {}
            self._update_project_combo()
            self._reset_ui()
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.loading_error_title"),
                f"Erreur de chargement : {str(e)}",
            )

    def _load_project_data_into_ui(self):
        """Charge les données du projet dans l'UI."""
        if not self.current_project_profile_data:
            return

        self.project_name_edit.setText(self.current_project_profile_data.get("name", ""))
        self.project_description_edit.setPlainText(self.current_project_profile_data.get("description", ""))
        self._refresh_cluster_list()

    def _load_profiles_from_dgraph_internal(self):
        """Charge les profils depuis Dgraph et les transforme en format Liris."""
        if not self.dgraph_connector.client:
            return {}

        try:
            query_result = self.dgraph_connector.query_workspaces()

            if not query_result or not query_result.get('q'):
                logger.info("Aucun workspace trouvé dans Dgraph.")
                return {}

            profiles = {}

            for workspace in query_result['q']:
                workspace_name = workspace.get('name', "")

                # Charger fileContents pour workspace
                file_contents_str = workspace.get('fileContents', '{}')
                try:
                    file_contents = json.loads(file_contents_str) if file_contents_str else {}
                except Exception as e:
                    logger.warning(f"Erreur parse fileContents workspace : {e}")
                    file_contents = {}

                clusters_detailed = []
                cm = workspace.get('clusterManagement', {})

                for cluster in cm.get('clusters', []):
                    # Charger fileContents pour cluster
                    cluster_file_contents_str = cluster.get('fileContents', '{}')
                    try:
                        cluster_file_contents = json.loads(cluster_file_contents_str) if cluster_file_contents_str else {}
                    except Exception as e:
                        logger.warning(f"Erreur parse fileContents cluster : {e}")
                        cluster_file_contents = {}

                    cluster_data = {
                        "name": cluster.get('name', ''),
                        "id": cluster.get('id', str(uuid.uuid4())),
                        "description": cluster.get('description', ''),
                        "files": cluster.get('files', []),
                        "file_contents": cluster_file_contents,
                        "root_labels": self._transform_root_labels(cluster.get('root_labels', []))
                    }
                    clusters_detailed.append(cluster_data)

                profile_data = {
                    "name": workspace_name,
                    "description": workspace.get('description', ""),
                    "files": workspace.get('files', []),
                    "file_contents": file_contents,
                    "created_at": workspace.get('updatedAt', datetime.now().isoformat()),
                    "last_modified": workspace.get('updatedAt', datetime.now().isoformat()),
                    "turing_ontology": {
                        "clusters_detailed": clusters_detailed
                    }
                }

                if workspace_name:
                    profiles[workspace_name] = profile_data

            return profiles

        except Exception as e:
            logger.error(f"Erreur lors du chargement depuis Dgraph : {e}")
            return {}

    def _transform_root_labels(self, dgraph_root_labels):
        """Transforme les root_labels depuis le format Dgraph vers le format Liris."""
        transformed = []
    
        for root in dgraph_root_labels:
            # Charger fileContents pour root
            root_file_contents_str = root.get('fileContents', '{}')
            try:
                root_file_contents = json.loads(root_file_contents_str) if root_file_contents_str else {}
            except Exception as e:
                logger.warning(f"Erreur parse fileContents root : {e}")
                root_file_contents = {}
            
            root_obj = {
                "label": root.get('name', ''),
                "id": root.get('id', str(uuid.uuid4())),
                "description": root.get('description', ''),
                "category": root.get('category', []),
                "files": root.get('files', []),
                "file_contents": root_file_contents,
                "parents": [],
            }
    
            for parent in root.get('parents', []):
                # Charger fileContents pour parent
                parent_file_contents_str = parent.get('fileContents', '{}')
                try:
                    parent_file_contents = json.loads(parent_file_contents_str) if parent_file_contents_str else {}
                except Exception as e:
                    logger.warning(f"Erreur parse fileContents parent : {e}")
                    parent_file_contents = {}
                
                parent_obj = {
                    "label": parent.get('name', ''),
                    "id": parent.get('id', str(uuid.uuid4())),
                    "description": parent.get('description', ''),
                    "category": parent.get('category', []),
                    "files": parent.get('files', []),
                    "file_contents": parent_file_contents,
                    "children": [],
                }
    
                for child in parent.get('children', []):
                    # Charger fileContents pour child
                    child_file_contents_str = child.get('fileContents', '{}')
                    try:
                        child_file_contents = json.loads(child_file_contents_str) if child_file_contents_str else {}
                    except Exception as e:
                        logger.warning(f"Erreur parse fileContents child : {e}")
                        child_file_contents = {}
                    
                    child_obj = {
                        "label": child.get('name', ''),
                        "id": child.get('id', str(uuid.uuid4())),
                        "description": child.get('description', ''),
                        "category": child.get('category', []),
                        "files": child.get('files', []),
                        "file_contents": child_file_contents,
                    }
                    parent_obj['children'].append(child_obj)
    
                root_obj['parents'].append(parent_obj)
    
            transformed.append(root_obj)
    
        return transformed
    
    def _update_project_combo(self):
        """Met à jour la combo box avec les noms de projets."""
        self.project_combo.clear()
        for project_name in sorted(self.project_profiles.keys()):
            self.project_combo.addItem(project_name)

    def _reset_ui(self):
        """Réinitialise l'UI quand aucun projet n'est sélectionné."""
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self.cluster_list_widget.clear()
        self._reset_hierarchy_ui()
        self.details_text.clear()
        self.current_project_name = None
        self.current_project_profile_data = None
        self.current_cluster_index = -1
        self.current_cluster_data = None
        self.current_top_level_is_file = False
        self.current_top_level_filename = None
        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None
        self.current_parent_label_index = -1
        self.current_parent_is_file = False
        self.current_parent_filename = None
        self.current_child_label_index = -1
        self.current_child_is_file = False
        self.current_child_filename = None
        self._update_button_states()

    def is_configured(self):
        """Vérifie si le profil de projet actuel est configuré au minimum."""
        if not self.current_project_profile_data:
            return False
        turing_config = self.current_project_profile_data.get("turing_ontology", {})

        if not turing_config.get("clusters_detailed"):
            return False

        for cluster_data in turing_config["clusters_detailed"]:
            if cluster_data.get("root_labels") and len(cluster_data["root_labels"]) > 0:
                return True
        return False

    def _on_add_new_project(self):
        """Crée un nouveau projet vide."""
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau Projet", "Nom du projet:")
        if ok and name.strip():
            project_name = name.strip()
            if project_name in self.project_profiles:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Projet existant.")
                return
            new_profile = {
                "name": project_name,
                "description": "",
                "files": [],
                "file_contents": {},
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "turing_ontology": {"clusters_detailed": []}
            }
            self.project_profiles[project_name] = new_profile
            self._update_project_combo()
            self.project_combo.setCurrentText(project_name)
            self.current_project_name = project_name
            self.current_project_profile_data = json.loads(json.dumps(new_profile))
            self._load_project_data_into_ui()
            self._update_project_details()
            self._update_button_states()
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

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet dans la combo."""
        if index < 0:
            return
        project_name = self.project_combo.currentText()
        self.current_project_name = project_name
        self.current_project_profile_data = json.loads(json.dumps(self.project_profiles[project_name]))
        self._load_project_data_into_ui()
        self._update_project_details()
        self._update_button_states()

    def _on_import_directory(self):
        """Importe la structure d'un dossier (placeholder)."""
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet")
        if directory:
            logger.info(f"Import du dossier : {directory}")
            QtWidgets.QMessageBox.information(self, "Info", f"Dossier sélectionné : {directory}")

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
                root_labels {{  # Uses ~clusters implicitly via schema reverse
                  uid
                  parents: ~parents {{
                    uid
                    children: ~parents {{
                      uid
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
                            for parent in root_label.get('parents', []):
                                if 'uid' in parent:
                                    to_delete.append(parent['uid'])
                                    for child in parent.get('children', []):
                                        if 'uid' in child:
                                            to_delete.append(child['uid'])
                                            for func in child.get('functions', []):
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

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)