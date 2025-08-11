#!/usr/bin/env python
# -*- coding: utf-8 -*-\

"""
ui/widgets/tabs/project_config_widget.py - VERSION AVEC HIERARCHIE (Textes en Français, UI 2 colonnes, multiples Labels Racines, Labels Racines déplacés à droite, Catégories supprimées, Importation de Dossier, Fichiers comme Labels, Mise en page 15/85%, Clusters Multiples, Centrage UI, Modifier Catégorie, Exportation Dgraph)
MODIFIÉ pour utiliser la base de données via conductor.database pour la sauvegarde des projets.
AJOUTÉ: Stockage de 'id' (UUID) et 'full_path' pour chaque noeud de l'ontologie lors de l'importation de dossier.
"""

import os
import json
import uuid  # <-- NOUVEL IMPORT
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import translator, tr
# from config.settings import ConfigProvider # Plus nécessaire, utilisation directe de database


class CategoryEditDialog(QtWidgets.QDialog):
    """
    Dialogue pour l'ajout, la modification et la suppression de catégories multiples.
    """

    def __init__(self, current_categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("category_edit_dialog.title"))
        self.setMinimumSize(400, 300)

        self.categories = list(current_categories)  # Travaille sur une copie

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
                )  # Select new item
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
                self.category_list_widget.setCurrentRow(
                    current_row
                )  # Re-select edited item
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
            self._update_button_states()  # Update button states after removal

    def get_categories(self):
        return self.categories


class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        # self.config_provider = config_provider # Plus nécessaire
        self.conductor = conductor
        # Accéder à l'instance de la base de données via le conductor
        self.database = conductor.database
        if not self.database:
            logger.error(
                "Database instance not available from conductor. ProjectConfigWidget cannot function correctly."
            )
            # Vous pouvez choisir de désactiver des fonctionnalités ou de lancer une erreur ici
            # Pour l'instant, le logger suffit.

        # Stocke tous les profils de projet chargés : {nom_projet : données_profil}
        self.project_profiles = {}
        # Le nom du projet actuellement sélectionné
        self.current_project_name = None
        # Les données complètes du profil pour le projet actuellement sélectionné (copie pour modification)
        self.current_project_profile_data = None

        # Nouveau: Index du cluster actuellement sélectionné
        self.current_cluster_index = -1
        # Nouveau: Référence aux données du cluster actuellement sélectionné
        self.current_cluster_data = None

        # Index pour les labels racines/parents/enfants sélectionnés pour les mises à jour dynamiques
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        try:
            self._init_ui()
            self._load_project_profiles()  # Chargement initial des projets depuis la BD
        except Exception as e:
            logger.error(
                f"Erreur lors de l'initialisation de ProjectConfigWidget : {str(e)}"
            )

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 2 colonnes)."""
        # Le layout principal est maintenant vertical pour placer le bouton Enregistrer en bas.
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(20)
        main_vertical_layout.setContentsMargins(20, 20, 20, 20)

        # Conteneur pour les deux colonnes (haut)
        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(20)
        main_vertical_layout.addLayout(top_columns_layout)

        # --- Colonne de gauche (Sélection et Détails du Projet) ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(15)
        left_column_layout.addStretch()  # Ajout pour centrage vertical

        explanation = QtWidgets.QLabel(tr("project_config.explanation"))
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        left_column_layout.addWidget(explanation)

        # Groupe pour la sélection du projet
        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
        project_selection_layout.addStretch()  # Ajout pour centrage horizontal

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
        project_selection_layout.addStretch()  # Ajout pour centrage horizontal

        left_column_layout.addWidget(project_selection_group)

        # Groupe pour les détails du projet (Nom, Cluster)
        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(15)
        details_form_layout.setAlignment(
            Qt.AlignHCenter | Qt.AlignTop
        )  # Alignement horizontal au centre, vertical en haut

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_form_layout.addRow(
            tr("project_config.project_name_label"), self.project_name_edit
        )

        # MODIFICATION: QListWidget pour les clusters multiples
        # Ceci est maintenant le widget principal pour naviguer dans l'ontologie
        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)

        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        # Connecter le signal de changement d'élément pour charger les labels racines du cluster
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

        details_form_layout.addRow(
            cluster_list_layout
        )  # Ajout du layout des clusters au formulaire

        left_column_layout.addWidget(details_group)

        # Bouton Importer dossier (DÉPLACÉ EN BAS DE LA COLONNE DE GAUCHE)
        import_button_layout = QtWidgets.QHBoxLayout()
        import_button_layout.addStretch()
        self.import_folder_button = QtWidgets.QPushButton(
            tr("project_config.import_folder_button")
        )
        self.import_folder_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.import_folder_button.clicked.connect(self._on_import_directory)
        import_button_layout.addWidget(self.import_folder_button)
        import_button_layout.addStretch()
        left_column_layout.addLayout(import_button_layout)

        left_column_layout.addStretch()  # Pousse le contenu vers le haut / centrage vertical

        top_columns_layout.addLayout(
            left_column_layout, 3
        )  # Facteur d'étirement de 3 pour la colonne de gauche (environ 15%)

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
        hierarchy_group_layout.setSpacing(
            10
        )  # Espacement pour les éléments dans ce groupe

        # 1. Labels Racines (MAINTENANT DANS LA COLONNE DE DROITE)
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
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

        # Bouton Modifier Catégorie pour les racines
        self.modify_category_root_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_root_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_root_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("root")
        )
        self.modify_category_root_button.setEnabled(False)  # Désactivé par default
        root_buttons_layout.addWidget(self.modify_category_root_button)

        hierarchy_group_layout.addLayout(root_buttons_layout)

        # 2. Labels Parents (dépend de la sélection du Label Racine)
        parent_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        parent_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(parent_label_title)

        self.parent_list_widget = QtWidgets.QListWidget()
        self.parent_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
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

        # Bouton Modifier Catégorie pour les parents
        self.modify_category_parent_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_parent_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_parent_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("parent")
        )
        self.modify_category_parent_button.setEnabled(False)  # Désactivé par default
        parent_buttons_layout.addWidget(self.modify_category_parent_button)

        hierarchy_group_layout.addLayout(parent_buttons_layout)

        # 3. Labels Enfants (dépend de la sélection du Parent)
        child_label_title = QtWidgets.QLabel(
            tr("project_config.child_labels_list_label")
        )
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
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

        # Bouton Modifier Catégorie pour les enfants
        self.modify_category_child_button = QtWidgets.QPushButton(
            tr("project_config.modify_category_button")
        )
        self.modify_category_child_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.modify_category_child_button.clicked.connect(
            lambda: self._modify_category_for_selected_label("child")
        )
        self.modify_category_child_button.setEnabled(False)  # Désactivé par default
        child_buttons_layout.addWidget(self.modify_category_child_button)

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_group_layout.addStretch()  # Pousse le contenu vers le haut dans le groupbox
        hierarchy_layout.addWidget(
            hierarchy_group
        )  # Ajoute le groupbox de hiérarchie au layout de la colonne droite
        hierarchy_layout.addStretch()  # Pousse le contenu du scroll area vers le haut

        right_column_container.setWidget(hierarchy_scroll_content)
        top_columns_layout.addWidget(
            right_column_container, 17
        )  # Facteur d'étirement de 17 pour la colonne de droite (environ 85%)

        # --- Boutons Enregistrer et Exporter (en bas de la fenêtre, centré) ---
        save_export_layout = QtWidgets.QHBoxLayout()
        save_export_layout.addStretch()

        self.save_button = QtWidgets.QPushButton(
            "💾 " + tr("project_config.save_button")
        )
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._save_configuration)
        self.save_button.setEnabled(
            False
        )  # Désactivé jusqu'à ce qu'un projet soit sélectionné ou ajouté
        save_export_layout.addWidget(self.save_button)

        # Nouveau bouton Exporter requête Dgraph
        self.export_dgraph_query_button = QtWidgets.QPushButton(
            "🚀 " + tr("project_config.export_dgraph_query_button")
        )
        self.export_dgraph_query_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.export_dgraph_query_button.clicked.connect(self._on_export_dgraph_query)
        self.export_dgraph_query_button.setEnabled(False)  # Désactivé par default
        save_export_layout.addWidget(self.export_dgraph_query_button)

        save_export_layout.addStretch()
        main_vertical_layout.addLayout(
            save_export_layout
        )  # Ajoute le layout des boutons au layout vertical principal

        self._set_fields_enabled(False)  # Désactiver tous les champs initialement
        self._update_button_states()  # Définir les états initiaux des boutons

    def update_language(self):
        """Met à jour les textes de l'interface utilisateur lors d'un changement de langue."""
        # Mise à jour de l'explication
        self.findChild(QtWidgets.QLabel, None, Qt.FindDirectChildrenOnly).setText(
            tr("project_config.explanation")
        )

        # Mettre à jour les titres de groupe en utilisant leur objectName pour une meilleure robustesse
        self.findChild(QtWidgets.QGroupBox, "project_selection_group").setTitle(
            tr("project_config.select_profile_group")
        )
        self.findChild(QtWidgets.QGroupBox, "details_group").setTitle(
            tr("project_config.details_group")
        )
        self.findChild(QtWidgets.QGroupBox, "hierarchy_group").setTitle(
            tr("project_config.hierarchy_group")
        )

        # Mettre à jour les labels (ciblage plus précis si nécessaire, sinon itération)
        for label in self.findChildren(QtWidgets.QLabel):
            # Utilisez un dictionnaire pour un mapping plus propre si les labels deviennent nombreux
            # Ou testez le texte d'origine comme fait actuellement
            if (
                label.text() == tr("project_config.project_name_label_old")
            ):  # Pour les cas où tr() retourne le même texte si la clé n'est pas trouvée
                label.setText(tr("project_config.project_name_label"))
            elif label.text() == tr("project_config.cluster_label_old"):  # Ancienne clé
                label.setText(
                    tr("project_config.cluster_label")
                )  # Nouvelle clé pour le titre de la liste
            elif label.text() == tr("project_config.root_labels_list_label_old"):
                label.setText(tr("project_config.root_labels_list_label"))
            elif label.text() == tr(
                "project_config.parent_labels_list_for_root_label_old"
            ):
                label.setText(tr("project_config.parent_labels_list_for_root_label"))
            elif label.text() == tr("project_config.child_labels_list_label_old"):
                label.setText(tr("project_config.child_labels_list_label"))

        # Mettre à jour les placeholder texts
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        # Le placeholder pour cluster_text_edit n'est plus pertinent pour un QListWidget

        # Mettre à jour les boutons
        self.import_folder_button.setText(tr("project_config.import_folder_button"))
        self.add_project_button.setText(tr("project_config.new_project_button"))
        self.delete_project_button.setText(tr("project_config.delete_project_button"))

        self.add_root_button.setText(tr("project_config.add_root_button"))
        self.edit_root_button.setText(tr("project_config.edit_root_button"))
        self.remove_root_button.setText(tr("project_config.remove_root_button"))
        self.modify_category_root_button.setText(
            tr("project_config.modify_category_button")
        )

        self.add_parent_button.setText(tr("project_config.add_parent_button"))
        self.edit_parent_button.setText(tr("project_config.edit_parent_button"))
        self.remove_parent_button.setText(tr("project_config.remove_parent_button"))
        self.modify_category_parent_button.setText(
            tr("project_config.modify_category_button")
        )

        self.add_child_button.setText(tr("project_config.add_child_button"))
        self.edit_child_button.setText(tr("project_config.edit_child_button"))
        self.remove_child_button.setText(tr("project_config.remove_child_button"))
        self.modify_category_child_button.setText(
            tr("project_config.modify_category_button")
        )

        self.add_cluster_button.setText(tr("project_config.add_cluster_button"))
        self.edit_cluster_button.setText(tr("project_config.edit_cluster_button"))
        self.remove_cluster_button.setText(tr("project_config.remove_cluster_button"))

        self.save_button.setText("💾 " + tr("project_config.save_button"))
        self.export_dgraph_query_button.setText(
            "🚀 " + tr("project_config.export_dgraph_query_button")
        )

        # Reconstruire le QComboBox pour mettre à jour l'élément par default
        current_project = self.project_combo.currentText()
        self._update_project_combo()
        if current_project in self.project_profiles:
            self.project_combo.setCurrentText(current_project)
        else:
            self.project_combo.setCurrentIndex(0)

        # Si un projet est sélectionné, recharger l'UI pour s'assurer que toutes les traductions sont appliquées
        if self.current_project_name:
            self._load_profile_into_ui(self.current_project_name)

    # La méthode set_project_profiles n'est plus nécessaire car le widget charge directement depuis la BD.
    # def set_project_profiles(self, profiles):
    #     """Définit les données des profils de projet. Cette méthode est appelée depuis PlatformConfigWidget."""
    #     self.project_profiles = profiles
    #     self._update_project_combo()

    def refresh(self):
        """Actualise le contenu du widget."""
        logger.info("Actualisation de ProjectConfigWidget...")
        self._load_project_profiles()  # Recharge depuis la source pour assurer la fraîcheur
        if self.current_project_name and self.current_project_profile_data:
            # Re-sélectionner le projet actuel pour rafraîchir tous les champs
            self._load_profile_into_ui(self.current_project_name)
        else:
            self._reset_ui()  # Réinitialiser si aucun projet sélectionné

    def _update_project_combo(self):
        """Met à jour la boîte de sélection combinée des projets."""
        current_text = self.project_combo.currentText()
        self.project_combo.clear()
        self.project_combo.addItem(tr("project_config.select_project_default"))

        for name in sorted(self.project_profiles.keys()):
            self.project_combo.addItem(name)

        if current_text and current_text in self.project_profiles:
            index = self.project_combo.findText(current_text)
            if index >= 0:
                self.project_combo.setCurrentIndex(index)
            else:  # Si current_text a été supprimé, réinitialiser
                self.project_combo.setCurrentIndex(0)
        else:
            self.project_combo.setCurrentIndex(0)  # Sélectionner l'élément par default

    def _on_project_selected(self, index):
        """Gère la sélection du projet à partir de la boîte combinée."""
        if index <= 0:
            self._reset_ui()
            self.current_project_name = None
            self.current_project_profile_data = None
            self.delete_project_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.export_dgraph_query_button.setEnabled(
                False
            )  # Désactiver à la désélection
            self._update_button_states()
            return

        project_name = self.project_combo.currentText()
        self.current_project_name = project_name
        # Récupérer les données depuis le cache, qui est rempli par _load_project_profiles
        self.current_project_profile_data = self.project_profiles.get(
            project_name, {}
        ).copy()

        # Charger les données du projet dans l'UI (y compris la liste des clusters)
        self._load_profile_into_ui(project_name)

        self.delete_project_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.export_dgraph_query_button.setEnabled(
            self.is_configured()
        )  # Activer si le projet est configuré
        self._update_button_states()

    def _load_profile_into_ui(self, project_name):
        """
        Charge le profil de projet sélectionné dans les champs de l'interface utilisateur.
        Ceci inclut la population de la liste des clusters et la sélection du premier cluster
        pour charger ses labels racines.
        """
        if not self.current_project_profile_data:
            self._reset_ui()
            return

        profile = self.current_project_profile_data
        turing_config = profile.get("turing_ontology", {})
        self.project_name_edit.setText(project_name)

        # Charger les clusters dans le QListWidget
        self.cluster_list_widget.clear()
        # Utiliser la nouvelle structure clusters_detailed
        clusters_detailed_data = turing_config.get("clusters_detailed", [])
        for cluster_data in clusters_detailed_data:
            self.cluster_list_widget.addItem(cluster_data.get("name", ""))

        # Réinitialiser les sélections de labels et les listes
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1
        self.current_cluster_index = -1  # Réinitialiser l'index du cluster
        self.current_cluster_data = None  # Réinitialiser les données du cluster

        # Si des clusters existent, sélectionner le premier pour charger ses labels racines
        if clusters_detailed_data:
            # Déconnecter temporairement le signal pour éviter le double déclenchement
            self.cluster_list_widget.currentItemChanged.disconnect(
                self._on_cluster_selected
            )
            self.cluster_list_widget.setCurrentRow(
                0
            )  # Ceci déclenchera _on_cluster_selected
            self.cluster_list_widget.currentItemChanged.connect(
                self._on_cluster_selected
            )
            # Appeler explicitement si la sélection de 0 n'a pas changé l'index (e.g. si c'était déjà 0)
            self._on_cluster_selected(self.cluster_list_widget.item(0), None)

        self._update_button_states()  # Mettre à jour l'état des boutons après le chargement

    def _reset_ui(self):
        """Réinitialise tous les champs de l'interface utilisateur à leur état vide par default."""
        self.project_name_edit.clear()
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.save_button.setEnabled(False)  # Désactiver le bouton de sauvegarde
        self.export_dgraph_query_button.setEnabled(
            False
        )  # Désactiver le bouton d'exportation

        self.current_cluster_index = -1
        self.current_cluster_data = None
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        self._update_button_states()  # Mettre à jour les états des boutons après la réinitialisation

    def _set_fields_enabled(self, enabled):
        """Active ou désactive les champs de configuration du projet. (Principalement pour le bouton de sauvegarde global)"""
        # Les champs individuels sont gérés par _update_button_states()
        self.save_button.setEnabled(enabled)

    def _update_button_states(self):
        """Met à jour l'état activé/désactivé des différents boutons en fonction des sélections."""
        is_project_selected = self.current_project_name is not None
        has_cluster_selected = self.current_cluster_data is not None
        has_root_selected = self.root_list_widget.currentRow() != -1
        has_parent_selected = self.parent_list_widget.currentRow() != -1
        has_child_selected = self.child_list_widget.currentRow() != -1
        # has_cluster_selected_in_list = (self.cluster_list_widget.currentRow() != -1) # Redondant si current_cluster_data est mis à jour

        # Contrôles du projet (Nom, Cluster, Boutons projet)
        self.project_name_edit.setEnabled(is_project_selected)
        # Clusters
        self.cluster_list_widget.setEnabled(is_project_selected)
        self.add_cluster_button.setEnabled(is_project_selected)
        self.edit_cluster_button.setEnabled(
            is_project_selected and has_cluster_selected
        )
        self.remove_cluster_button.setEnabled(
            is_project_selected and has_cluster_selected
        )

        self.import_folder_button.setEnabled(
            True
        )  # Toujours enabled pour pouvoir importer
        self.add_project_button.setEnabled(
            True
        )  # Toujours enabled pour ajouter un nouveau projet
        self.delete_project_button.setEnabled(is_project_selected)

        # Contrôles des Labels Racines (dépendent de la sélection d'un cluster)
        self.add_root_button.setEnabled(is_project_selected and has_cluster_selected)
        self.edit_root_button.setEnabled(
            is_project_selected and has_cluster_selected and has_root_selected
        )
        self.remove_root_button.setEnabled(
            is_project_selected and has_cluster_selected and has_root_selected
        )
        self.root_list_widget.setEnabled(is_project_selected and has_cluster_selected)
        # Modify Category for Root
        selected_root_data = self._get_selected_label_data("root")
        self.modify_category_root_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and selected_root_data
            and selected_root_data.get("type") == "file"
        )

        # Contrôles des Labels Parents (dépendent de la sélection d'un cluster et d'une racine)
        self.add_parent_button.setEnabled(
            is_project_selected and has_cluster_selected and has_root_selected
        )
        self.edit_parent_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
        )
        self.remove_parent_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
        )
        self.parent_list_widget.setEnabled(
            is_project_selected and has_cluster_selected and has_root_selected
        )
        # Modify Category for Parent
        selected_parent_data = self._get_selected_label_data("parent")
        self.modify_category_parent_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
            and selected_parent_data
            and selected_parent_data.get("type") == "file"
        )

        # Contrôles des Labels Enfants (dépendent de la sélection d'un cluster, d'une racine et d'un parent)
        self.add_child_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
        )
        self.edit_child_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
            and has_child_selected
        )
        self.remove_child_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
            and has_child_selected
        )
        self.child_list_widget.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
        )
        # Modify Category for Child
        selected_child_data = self._get_selected_label_data("child")
        self.modify_category_child_button.setEnabled(
            is_project_selected
            and has_cluster_selected
            and has_root_selected
            and has_parent_selected
            and has_child_selected
            and selected_child_data
            and selected_child_data.get("type") == "file"
        )

        self.save_button.setEnabled(
            is_project_selected
        )  # Le bouton Save dépend uniquement de la sélection d'un projet
        self.export_dgraph_query_button.setEnabled(
            is_project_selected and self.is_configured()
        )  # Activer si le projet est sélectionné et configuré

    def _on_cluster_selected(self, current, previous):
        """
        Gère la sélection d'un cluster, chargeant ses labels racines.
        """
        if not self.current_project_profile_data:
            return

        self.current_cluster_index = self.cluster_list_widget.currentRow()

        # Réinitialiser les listes de labels et leurs index
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1
        self.current_cluster_data = (
            None  # Réinitialiser avant de potentiellement charger
        )

        turing_config = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed_data = turing_config.get("clusters_detailed", [])

        if 0 <= self.current_cluster_index < len(clusters_detailed_data):
            self.current_cluster_data = clusters_detailed_data[
                self.current_cluster_index
            ]
            logger.debug(
                f"Cluster sélectionné. Index: {self.current_cluster_index}, Nom: {self.current_cluster_data.get('name')}"
            )

            # Charger les labels racines du cluster sélectionné
            root_labels_data = self.current_cluster_data.get("root_labels", [])
            for r_label in root_labels_data:
                display_name = r_label.get("name", "")
                if (
                    r_label.get("type") == "file"
                    and r_label.get("category")
                    and len(r_label["category"]) > 0
                ):
                    display_name = f"{display_name} ({', '.join(r_label['category'])})"
                item = QtWidgets.QListWidgetItem(display_name)
                self.root_list_widget.addItem(item)

            # Sélectionner le premier label racine si disponible
            if root_labels_data:
                self.root_list_widget.setCurrentRow(
                    0
                )  # Cela déclenchera _on_root_label_selected
            else:
                logger.debug(
                    "Aucun label racine dans le cluster sélectionné, les listes parent/enfant sont effacées."
                )

        self._update_button_states()

    def _on_import_directory(self):
        """
        Ouvre une boîte de dialogue pour sélectionner un dossier et importe sa structure
        dans l'ontologie du projet. Les enfants directs du dossier sélectionné
        deviennent des clusters.
        """
        selected_directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            tr("project_config.select_cluster_folder_dialog_title"),
            os.path.expanduser("~"),  # Chemin par défaut
        )

        if not selected_directory:
            logger.info("Importation de dossier annulée.")
            return

        try:
            # No longer getting cluster_name_from_folder from selected_directory directly
            # The clusters will be the direct children of selected_directory

            # Logic to handle project creation/selection remains similar
            if self.current_project_name and self.current_project_profile_data:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    tr("project_config.confirm_import_title"),
                    tr("project_config.confirm_import_add_cluster_text").format(
                        cluster_name=os.path.basename(selected_directory)
                    ),  # Use base name for message
                    QtWidgets.QMessageBox.Yes
                    | QtWidgets.QMessageBox.No,  # Yes: Add to current project, No: Create new project
                    QtWidgets.QMessageBox.Yes,  # Default to adding to current
                )
                if (
                    reply == QtWidgets.QMessageBox.No
                ):  # User chose to create a new project
                    new_project_name, ok = QtWidgets.QInputDialog.getText(
                        self,
                        tr("project_config.new_project_for_import_title"),
                        tr("project_config.new_project_for_import_text").format(
                            cluster_name=os.path.basename(selected_directory)
                        ),
                        QtWidgets.QLineEdit.Normal,
                        os.path.basename(selected_directory),
                    )
                    if not ok or not new_project_name:
                        logger.info("Création de projet pour l'importation annulée.")
                        return

                    if new_project_name in self.project_profiles:
                        QtWidgets.QMessageBox.warning(
                            self,
                            tr("project_config.duplicate_title"),
                            tr("project_config.project_exists_msg").format(
                                project_name=new_project_name
                            ),
                        )
                        return

                    # Create a new empty project profile for import
                    self.current_project_name = new_project_name
                    self.current_project_profile_data = {
                        "name": new_project_name,
                        "turing_ontology": {
                            "cluster": [],  # Noms
                            "clusters_detailed": [],  # Objets détaillés
                        },
                    }
                    self.project_profiles[new_project_name] = (
                        self.current_project_profile_data
                    )
                    self._update_project_combo()
                    self.project_combo.setCurrentText(new_project_name)

            else:  # No project selected, must create one
                new_project_name, ok = QtWidgets.QInputDialog.getText(
                    self,
                    tr("project_config.new_project_for_import_title"),
                    tr("project_config.new_project_for_import_text").format(
                        cluster_name=os.path.basename(selected_directory)
                    ),
                    QtWidgets.QLineEdit.Normal,
                    os.path.basename(selected_directory),
                )
                if not ok or not new_project_name:
                    logger.info("Création de projet pour l'importation annulée.")
                    return

                if new_project_name in self.project_profiles:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.duplicate_title"),
                        tr("project_config.project_exists_msg").format(
                            project_name=new_project_name
                        ),
                    )
                    return

                # Create a new empty project profile for import
                self.current_project_name = new_project_name
                self.current_project_profile_data = {
                    "name": new_project_name,
                    "turing_ontology": {"cluster": [], "clusters_detailed": []},
                }
                self.project_profiles[new_project_name] = (
                    self.current_project_profile_data
                )
                self._update_project_combo()
                self.project_combo.setCurrentText(new_project_name)

            # At this point, self.current_project_profile_data is defined and modifiable.
            turing_ontology = self.current_project_profile_data["turing_ontology"]

            logger.debug(
                f"Début de peuplement de l'ontologie pour '{selected_directory}'"
            )

            # Iterate over direct children of selected_directory to create multiple clusters
            for item_name in sorted(os.listdir(selected_directory)):
                item_full_path = os.path.join(selected_directory, item_name)

                # Each direct child (folder or file) is now a potential cluster
                cluster_name = item_name

                # Check if a cluster with this name already exists
                existing_cluster = next(
                    (
                        c
                        for c in turing_ontology["clusters_detailed"]
                        if c["name"] == cluster_name
                    ),
                    None,
                )

                if existing_cluster:
                    replace_reply = QtWidgets.QMessageBox.question(
                        self,
                        tr("project_config.cluster_exists_title"),
                        tr("project_config.cluster_exists_msg").format(
                            cluster_name=cluster_name
                        ),
                        QtWidgets.QMessageBox.Yes
                        | QtWidgets.QMessageBox.No,  # Yes: Replace, No: Cancel
                    )
                    if replace_reply == QtWidgets.QMessageBox.No:
                        logger.info(
                            f"Importation annulée : cluster '{cluster_name}' existant non remplacé."
                        )
                        continue  # Skip to the next item if user cancels for this cluster
                    else:
                        existing_cluster[
                            "root_labels"
                        ] = []  # Clear existing root labels
                        target_root_labels_list = existing_cluster["root_labels"]
                else:
                    new_cluster_detailed_entry = {
                        "name": cluster_name,
                        "id": str(uuid.uuid4()),  # Assign UUID to cluster
                        "root_labels": [],
                    }
                    turing_ontology["clusters_detailed"].append(
                        new_cluster_detailed_entry
                    )
                    if cluster_name not in turing_ontology["cluster"]:
                        turing_ontology["cluster"].append(cluster_name)
                    target_root_labels_list = new_cluster_detailed_entry["root_labels"]

                # Populate the ontology from the *children* of this new cluster
                # The children of 'item_full_path' are now the 'root_labels' for this cluster
                self._populate_ontology_from_directory(
                    item_full_path,  # This is now the "cluster" path
                    target_root_labels_list,
                    "root",
                )

            logger.debug(
                f"Fin de peuplement de l'ontologie. Données du profil après peuplement: {self.current_project_profile_data}"
            )

            # Save configuration to persist the new clusters/labels
            self._save_configuration(show_message=False)

            self._load_profile_into_ui(
                self.current_project_name
            )  # Refresh UI to show new clusters/labels

            # No single cluster to select anymore; all direct children are clusters
            # Optionally, you could select the first imported cluster, or refresh the list
            # self.cluster_list_widget.setCurrentRow(0) # Select the first if desired

            QtWidgets.QMessageBox.information(
                self,
                tr("project_config.import_success_title"),
                tr("project_config.import_success_msg_multiple").format(
                    directory_name=os.path.basename(selected_directory)
                ),  # New message for multiple clusters
            )
            logger.info(
                f"Structure du dossier '{selected_directory}' importée avec succès, créant plusieurs clusters."
            )

        except Exception as e:
            logger.error(
                f"Erreur lors de l'importation de la structure du dossier : {str(e)}"
            )
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.import_error_title"),
                tr("project_config.import_error_msg").format(error=str(e)),
            )

    def _populate_ontology_from_directory(
        self, current_path, target_list, current_ontology_level
    ):
        """
        Fonction récursive pour parcourir le dossier et peupler l'ontologie.
        Les fichiers sont également traités comme des labels.
        current_path: Le chemin du dossier à explorer.
        target_list: La liste dans l'ontologie où les nouveaux éléments doivent être ajoutés.
                     (ex: root_labels, parent_labels, child_labels - ces listes sont au sein des objets de cluster/label)
        current_ontology_level: La string indiquant le niveau actuel de l'ontologie que nous peuplons
                                ("root", "parent", "child").
        """
        try:
            # If current_path is a file, we treat it as a terminal node and don't descend further
            if os.path.isfile(current_path):
                # This case should ideally be handled by the caller, but good to have a safeguard
                # When _on_import_directory calls this for a file, it adds it directly.
                # If a file path somehow gets passed here for further traversal, it will just return.
                return

            logger.debug(
                f"Parcours de : {current_path} au niveau : {current_ontology_level}"
            )
            for item_name in sorted(
                os.listdir(current_path)
            ):  # Tri pour un ordre cohérent
                item_full_path = os.path.join(current_path, item_name)
                logger.debug(f"  Traitement de l'élément : {item_name}")

                new_node = {
                    "name": item_name,
                    "id": str(uuid.uuid4()),  # Assign a unique ID to each node
                    "full_path": item_full_path,  # Store the full path
                }

                if os.path.isdir(item_full_path):
                    new_node["type"] = "directory"
                    if current_ontology_level == "root":
                        new_node["parents"] = []
                        target_list.append(new_node)
                        logger.debug(
                            f"    Ajout d'un label racine (répertoire) : {item_name} (ID: {new_node['id']})"
                        )
                        self._populate_ontology_from_directory(
                            item_full_path, new_node["parents"], "parent"
                        )
                    elif current_ontology_level == "parent":
                        new_node["children"] = []
                        target_list.append(new_node)
                        logger.debug(
                            f"    Ajout d'un label parent (répertoire) : {item_name} (ID: {new_node['id']})"
                        )
                        self._populate_ontology_from_directory(
                            item_full_path, new_node["children"], "child"
                        )
                    elif current_ontology_level == "child":
                        # If we reach child level and it's a directory, we still add it
                        # but we don't recurse further for grand-child labels based on your schema
                        target_list.append(new_node)
                        logger.debug(
                            f"    Ajout d'un label enfant (répertoire - terminal) : {item_name} (ID: {new_node['id']})"
                        )
                        # If you wanted to go deeper, you would call self._populate_ontology_from_directory here
                        # For now, we assume max depth is Cluster -> Root -> Parent -> Child.
                elif os.path.isfile(item_full_path):
                    new_node["type"] = "file"
                    new_node["category"] = []  # Initialize category as an empty list
                    target_list.append(new_node)
                    logger.debug(
                        f"    Ajout d'un label (fichier - terminal) : {item_name} (ID: {new_node['id']})"
                    )

        except Exception as e:
            logger.error(
                f"Erreur lors du parcours du dossier '{current_path}' : {str(e)}"
            )

    def _get_selected_label_data(self, level):
        """Récupère les données (dictionnaire) du label actuellement sélectionné à un certain niveau."""
        if not self.current_project_profile_data or not self.current_cluster_data:
            return None

        # Accéder aux labels racines via le cluster sélectionné
        root_labels_data = self.current_cluster_data.get("root_labels", [])

        if level == "root" and self.current_root_label_index != -1:
            if 0 <= self.current_root_label_index < len(root_labels_data):
                return root_labels_data[self.current_root_label_index]

        elif (
            level == "parent"
            and self.current_root_label_index != -1
            and self.current_parent_label_index != -1
        ):
            if 0 <= self.current_root_label_index < len(root_labels_data):
                selected_root = root_labels_data[self.current_root_label_index]
                parent_labels_data = selected_root.get("parent_labels", [])
                if 0 <= self.current_parent_label_index < len(parent_labels_data):
                    return parent_labels_data[self.current_parent_label_index]

        elif (
            level == "child"
            and self.current_root_label_index != -1
            and self.current_parent_label_index != -1
            and self.current_child_label_index != -1
        ):
            if 0 <= self.current_root_label_index < len(root_labels_data):
                selected_root = root_labels_data[self.current_root_label_index]
                parent_labels_data = selected_root.get("parent_labels", [])
                if 0 <= self.current_parent_label_index < len(parent_labels_data):
                    selected_parent = parent_labels_data[
                        self.current_parent_label_index
                    ]
                    child_labels_data = selected_parent.get("child_labels", [])
                    if 0 <= self.current_child_label_index < len(child_labels_data):
                        return child_labels_data[self.current_child_label_index]
        return None

    def _update_label_item_text(self, list_widget, label_data):
        """Met à jour le texte d'un élément dans la liste pour inclure la catégorie si c'est un fichier."""
        if not label_data:
            return

        # Trouver l'élément correspondant dans le QListWidget par son nom d'origine
        # Ceci est nécessaire car le texte affiché change avec la catégorie
        current_name = label_data.get("name", "")
        found_item = None
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            # Comparer le nom de base sans la partie catégorie pour retrouver l'élément
            item_text_no_category = item.text().split(" (")[0].strip()
            if item_text_no_category == current_name:
                found_item = item
                break

        if not found_item:
            logger.warning(
                f"Impossible de trouver l'élément '{current_name}' dans la liste pour la mise à jour."
            )
            return

        display_name = label_data.get("name", "")
        # MODIFICATION: Afficher les catégories jointes par des virgules
        if (
            label_data.get("type") == "file"
            and label_data.get("category")
            and len(label_data["category"]) > 0
        ):
            display_name = f"{display_name} ({', '.join(label_data['category'])})"

        found_item.setText(display_name)

    def _on_root_label_selected(self, current, previous):
        """Gère la sélection d'un label racine, mettant à jour la liste des parents."""
        if not self.current_project_profile_data or not self.current_cluster_data:
            return

        self.current_root_label_index = self.root_list_widget.currentRow()
        logger.debug(
            f"Label Racine sélectionné. Index: {self.current_root_label_index}"
        )
        self._update_parent_list()
        self._update_button_states()

    def _update_parent_list(self):
        """Remplit la liste des labels parents en fonction du label racine sélectionné."""
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self.current_parent_label_index = -1  # Réinitialiser la sélection du parent
        self.current_child_label_index = -1  # Réinitialiser la sélection de l'enfant

        if self.current_root_label_index == -1 or not self.current_cluster_data:
            logger.debug(
                "Aucun label racine ou cluster sélectionné, effacement des listes parent/enfant."
            )
            self._update_button_states()
            return

        root_labels_data = self.current_cluster_data.get("root_labels", [])
        logger.debug(f"Données du cluster actuel: {self.current_cluster_data}")

        if 0 <= self.current_root_label_index < len(root_labels_data):
            selected_root = root_labels_data[self.current_root_label_index]
            parent_labels_data = selected_root.get("parent_labels", [])
            logger.debug(
                f"Labels Parents pour la racine '{selected_root.get('name', 'N/A')}' : {parent_labels_data}"
            )
            for p_label in parent_labels_data:
                # MODIFICATION: Afficher la catégorie pour les fichiers dans le nom du label
                display_name = p_label.get("name", "")
                if (
                    p_label.get("type") == "file"
                    and p_label.get("category")
                    and len(p_label["category"]) > 0
                ):
                    display_name = f"{display_name} ({', '.join(p_label['category'])})"
                item = QtWidgets.QListWidgetItem(display_name)
                self.parent_list_widget.addItem(item)

            # S'assurer que le premier parent est sélectionné si elle existe pour charger ses enfants
            if parent_labels_data:
                # Déconnecter temporairement le signal pour éviter le double déclenchement
                self.parent_list_widget.currentItemChanged.disconnect(
                    self._on_parent_label_selected
                )
                self.parent_list_widget.setCurrentRow(0)
                self.parent_list_widget.currentItemChanged.connect(
                    self._on_parent_label_selected
                )
                # Appeler explicitement si la sélection de 0 n'a pas changé l'index
                self._on_parent_label_selected(
                    self.parent_list_widget.currentItem(), None
                )
            else:
                self.child_list_widget.clear()
                self.current_child_label_index = -1

        self._update_button_states()

    def _on_parent_label_selected(self, current, previous):
        """Gère la sélection d'un label parent, mettant à jour la liste des enfants."""
        if not self.current_project_profile_data or not self.current_cluster_data:
            return

        self.current_parent_label_index = self.parent_list_widget.currentRow()
        logger.debug(
            f"Label Parent sélectionné. Index: {self.current_parent_label_index}"
        )
        self._update_child_list()
        self._update_button_states()

    def _update_child_list(self):
        """Remplit la liste des labels enfants en fonction du parent sélectionné."""
        self.child_list_widget.clear()
        self.current_child_label_index = -1  # Réinitialiser la sélection de l'enfant

        if (
            self.current_root_label_index == -1
            or self.current_parent_label_index == -1
            or not self.current_cluster_data
        ):
            logger.debug(
                "Aucun label parent ou racine ou cluster sélectionné, effacement de la liste enfant."
            )
            self._update_button_states()
            return

        root_labels_data = self.current_cluster_data.get("root_labels", [])

        if 0 <= self.current_root_label_index < len(root_labels_data):
            selected_root = root_labels_data[self.current_root_label_index]
            parent_labels_data = selected_root.get("parent_labels", [])

            if 0 <= self.current_parent_label_index < len(parent_labels_data):
                selected_parent = parent_labels_data[self.current_parent_label_index]
                child_labels_data = selected_parent.get("child_labels", [])
                logger.debug(
                    f"Labels Enfants pour le parent '{selected_parent.get('name', 'N/A')}' : {child_labels_data}"
                )
                for c_label in child_labels_data:
                    # MODIFICATION: Afficher la catégorie pour les fichiers dans le nom du label
                    display_name = c_label.get("name", "")
                    if (
                        c_label.get("type") == "file"
                        and c_label.get("category")
                        and len(c_label["category"]) > 0
                    ):
                        display_name = (
                            f"{display_name} ({', '.join(c_label['category'])})"
                        )
                    item = QtWidgets.QListWidgetItem(display_name)
                    self.child_list_widget.addItem(item)

                # S'assurer que le premier enfant est sélectionné si elle existe
                if child_labels_data:
                    # Déconnecter temporairement le signal pour éviter le double déclenchement
                    self.child_list_widget.currentItemChanged.disconnect(
                        self._on_child_label_selected
                    )
                    self.child_list_widget.setCurrentRow(0)
                    self.child_list_widget.currentItemChanged.connect(
                        self._on_child_label_selected
                    )
                    # Appeler explicitement si la sélection de 0 n'a pas changé l'index
                    self._on_child_label_selected(
                        self.child_list_widget.currentItem(), None
                    )

        self._update_button_states()

    def _on_child_label_selected(self, current, previous):
        """Gère la sélection d'un label enfant. (Pas de catégories à mettre à jour directement dans l'UI)"""
        if not self.current_project_profile_data or not self.current_cluster_data:
            return

        self.current_child_label_index = self.child_list_widget.currentRow()
        logger.debug(
            f"Label Enfant sélectionné. Index: {self.current_child_label_index}. Les catégories ne sont plus affichées."
        )
        self._update_button_states()

    def _modify_category_for_selected_label(self, level):
        """
        Ouvre une boîte de dialogue pour assigner ou modifier les catégories du label sélectionné.
        S'applique uniquement aux labels de type 'file'.
        """
        label_data = self._get_selected_label_data(level)
        if not label_data:
            return

        if label_data.get("type") != "file":
            QtWidgets.QMessageBox.information(
                self,
                tr("project_config.modify_category_dialog_title"),
                tr("project_config.modify_category_dialog_file_type_warning"),
            )
            return

        dialog = CategoryEditDialog(label_data.get("category", []))
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_categories = dialog.get_categories()
            label_name = label_data.get("name", tr("project_config.unknown_label"))

            # Mettre à jour la catégorie et rafraîchir l'affichage
            label_data["category"] = new_categories

            # Déterminer le QListWidget à mettre à jour
            if level == "root":
                list_widget = self.root_list_widget
            elif level == "parent":
                list_widget = self.parent_list_widget
            elif level == "child":
                list_widget = self.child_list_widget
            else:
                return  # Should not happen

            self._update_label_item_text(
                list_widget, label_data
            )  # Met à jour le texte affiché
            logger.info(
                f"Catégories de '{label_name}' ({level}) mises à jour à : '{new_categories}'"
            )
            self.save_button.setEnabled(True)  # Activer le bouton de sauvegarde

    def _add_cluster(self):
        """Ajoute un nouveau cluster."""
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_project_selected_title"),
                tr("project_config.no_project_selected_msg_add_cluster"),
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_cluster_dialog_title"),
            tr("project_config.add_cluster_dialog_text"),
        )
        if ok and name:
            name = name.strip()
            if not name:
                return

            turing_ontology = self.current_project_profile_data["turing_ontology"]

            # Vérifier l'unicité du nom dans les clusters_detailed
            if any(
                c["name"] == name for c in turing_ontology.get("clusters_detailed", [])
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_cluster_msg"),
                )
                return

            # Ajouter à clusters_detailed
            new_cluster_detailed_entry = {
                "name": name,
                "id": str(uuid.uuid4()),  # Assign UUID to cluster
                "root_labels": [],  # Nouveau cluster, pas de labels au départ
            }
            turing_ontology.setdefault("clusters_detailed", []).append(
                new_cluster_detailed_entry
            )

            # Synchroniser la liste simple des noms de clusters
            turing_ontology.setdefault("cluster", []).append(name)

            self._load_profile_into_ui(self.current_project_name)  # Rafraîchir l'UI
            self.cluster_list_widget.setCurrentText(
                name
            )  # Sélectionner le nouveau cluster

            logger.info(f"Cluster ajouté : {name}")
            self.save_button.setEnabled(True)
            self._update_button_states()

    def _edit_cluster(self):
        """Modifie le cluster sélectionné."""
        current_row = self.cluster_list_widget.currentRow()
        if current_row == -1 or not self.current_cluster_data:
            return

        old_name = self.current_cluster_data["name"]
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_cluster_dialog_title"),
            tr("project_config.edit_cluster_dialog_text"),
            QtWidgets.QLineEdit.Normal,
            old_name,
        )
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name or new_name == old_name:
                return

            turing_ontology = self.current_project_profile_data["turing_ontology"]

            # Vérifier l'unicité du nouveau nom (en excluant le cluster que nous éditons)
            if any(
                c["name"] == new_name
                for c in turing_ontology.get("clusters_detailed", [])
                if c is not self.current_cluster_data
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_cluster_msg"),
                )
                return

            # Mettre à jour dans clusters_detailed
            self.current_cluster_data["name"] = new_name

            # Synchroniser la liste simple des noms de clusters
            if old_name in turing_ontology.get("cluster", []):
                index_in_simple_list = turing_ontology["cluster"].index(old_name)
                turing_ontology["cluster"][index_in_simple_list] = new_name

            self._load_profile_into_ui(self.current_project_name)  # Rafraîchir l'UI
            self.cluster_list_widget.setCurrentText(
                new_name
            )  # Sélectionner le cluster renommé

            logger.info(f"Cluster renommé de {old_name} en {new_name}")
            self.save_button.setEnabled(True)

    def _remove_cluster(self):
        """Supprime le cluster sélectionné."""
        current_row = self.cluster_list_widget.currentRow()
        if current_row == -1 or not self.current_cluster_data:
            return

        cluster_name = self.current_cluster_data["name"]
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.remove_cluster_dialog_title"),
            tr("project_config.remove_cluster_dialog_text").format(
                cluster_name=cluster_name
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            turing_ontology = self.current_project_profile_data["turing_ontology"]

            # Supprimer de clusters_detailed
            turing_ontology["clusters_detailed"].remove(self.current_cluster_data)

            # Synchroniser la liste simple des noms de clusters
            if cluster_name in turing_ontology.get("cluster", []):
                turing_ontology["cluster"].remove(cluster_name)

            self.current_cluster_data = None  # Réinitialiser la référence
            self._load_profile_into_ui(
                self.current_project_name
            )  # Rafraîchir l'UI pour refléter la suppression

            logger.info(f"Cluster supprimé : {cluster_name}")
            self.save_button.setEnabled(True)
            self._update_button_states()

    def _add_root_label(self):
        """Ajoute un nouveau label racine au cluster actuellement sélectionné."""
        if not self.current_cluster_data:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_cluster_selected_title"),
                tr("project_config.no_cluster_selected_msg_add_root"),
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_root_dialog_title"),
            tr("project_config.add_root_dialog_text"),
        )
        if ok and name:
            name = name.strip()
            if not name:
                return

            root_labels_data = self.current_cluster_data.get("root_labels", [])
            if any(r["name"] == name for r in root_labels_data):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_root_msg"),
                )
                return

            new_label_data = {
                "name": name,
                "type": "directory",
                "id": str(uuid.uuid4()),
                "full_path": "",
                "parent_labels": [],
            }  # Added ID and full_path
            root_labels_data.append(new_label_data)
            self.current_cluster_data["root_labels"] = (
                root_labels_data  # S'assurer que les données sont à jour
            )

            self._update_parent_list()  # Force le rafraîchissement des listes de labels
            self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
            logger.info(
                f"Label racine ajouté à cluster '{self.current_cluster_data['name']}' : {name}"
            )
            self._update_button_states()

    def _edit_root_label(self):
        """Modifie le label racine sélectionné dans le cluster actuel."""
        if not self.current_cluster_data:
            return  # Protection supplémentaire

        current_row = self.root_list_widget.currentRow()
        if current_row == -1:
            return

        label_data = self._get_selected_label_data("root")
        if not label_data:
            return

        old_name = label_data.get("name", "")
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_root_dialog_title"),
            tr("project_config.edit_root_dialog_text"),
            QtWidgets.QLineEdit.Normal,
            old_name,
        )
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name or new_name == old_name:
                return

            root_labels_data = self.current_cluster_data.get("root_labels", [])

            if any(
                r["name"] == new_name for r in root_labels_data if r is not label_data
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_root_msg"),
                )
                return

            label_data["name"] = new_name
            self._update_label_item_text(
                self.root_list_widget, label_data
            )  # Met à jour le texte affiché
            logger.info(
                f"Label racine renommé de {old_name} en {new_name} dans cluster '{self.current_cluster_data['name']}'"
            )
            self.save_button.setEnabled(True)

    def _remove_root_label(self):
        """Supprime le label racine sélectionné du cluster actuel, ainsi que ses enfants et catégories."""
        if not self.current_cluster_data:
            return  # Protection supplémentaire

        current_row = self.root_list_widget.currentRow()
        if current_row == -1:
            return

        root_name = self.root_list_widget.currentItem().text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.remove_root_dialog_title"),
            tr("project_config.remove_root_dialog_text").format(root_name=root_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            root_labels_data = self.current_cluster_data.get("root_labels", [])

            del root_labels_data[current_row]
            self.current_cluster_data["root_labels"] = (
                root_labels_data  # S'assurer que les données sont à jour
            )

            self.root_list_widget.takeItem(current_row)  # Supprimer de l'UI
            self.root_list_widget.setCurrentRow(-1)  # Désélectionner

            self._update_parent_list()  # Ceci effacera également les parents/enfants/catégories
            logger.info(
                f"Label racine supprimé de cluster '{self.current_cluster_data['name']}' : {root_name}"
            )
            self.save_button.setEnabled(True)
            self._update_button_states()

    def _add_parent_label(self):
        """Ajoute un nouveau label parent sous le label racine actuellement sélectionné."""
        if not self.current_cluster_data or self.current_root_label_index == -1:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_root_selected_title"),
                tr("project_config.no_root_selected_msg"),
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_parent_dialog_title"),
            tr("project_config.add_parent_dialog_text"),
        )
        if ok and name:
            name = name.strip()
            if not name:
                return

            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            parent_labels_data = selected_root.get("parent_labels", [])

            if any(p["name"] == name for p in parent_labels_data):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_parent_msg"),
                )
                return

            new_label_data = {
                "name": name,
                "type": "directory",
                "id": str(uuid.uuid4()),
                "full_path": "",
                "child_labels": [],
            }  # Added ID and full_path
            parent_labels_data.append(new_label_data)
            selected_root["parent_labels"] = (
                parent_labels_data  # S'assurer que les données sont à jour
            )

            self._update_child_list()  # Force le rafraîchissement
            self.parent_list_widget.setCurrentRow(self.parent_list_widget.count() - 1)
            logger.info(
                f"Label parent ajouté sous racine '{selected_root['name']}' : {name}"
            )
            self._update_button_states()
            self.save_button.setEnabled(True)

    def _edit_parent_label(self):
        """Modifie le label parent sélectionné."""
        if not self.current_cluster_data or self.current_root_label_index == -1:
            return

        current_parent_row = self.parent_list_widget.currentRow()
        if current_parent_row == -1:
            return

        label_data = self._get_selected_label_data("parent")
        if not label_data:
            return

        old_name = label_data.get("name", "")
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_parent_dialog_title"),
            tr("project_config.edit_parent_dialog_text"),
            QtWidgets.QLineEdit.Normal,
            old_name,
        )
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name or new_name == old_name:
                return

            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            parent_labels_data = selected_root.get("parent_labels", [])

            if any(
                p["name"] == new_name for p in parent_labels_data if p is not label_data
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_parent_msg"),
                )
                return

            label_data["name"] = new_name
            self._update_label_item_text(
                self.parent_list_widget, label_data
            )  # Met à jour le texte affiché
            logger.info(f"Label parent renommé de {old_name} en {new_name}")
            self.save_button.setEnabled(True)

    def _remove_parent_label(self):
        """Supprime le label parent sélectionné, ainsi que ses enfants."""
        if not self.current_cluster_data or self.current_root_label_index == -1:
            return

        current_parent_row = self.parent_list_widget.currentRow()
        if current_parent_row == -1:
            return

        parent_name = self.parent_list_widget.currentItem().text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.remove_parent_dialog_title"),
            tr("project_config.remove_parent_dialog_text").format(
                parent_name=parent_name
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            parent_labels_data = selected_root.get("parent_labels", [])

            del parent_labels_data[current_parent_row]
            selected_root["parent_labels"] = (
                parent_labels_data  # S'assurer que les données sont à jour
            )

            self.parent_list_widget.takeItem(current_parent_row)  # Supprimer de l'UI
            self.parent_list_widget.setCurrentRow(-1)  # Désélectionner

            self._update_child_list()  # Ceci effacera également les enfants
            logger.info(f"Label parent supprimé : {parent_name}")
            self.save_button.setEnabled(True)
            self._update_button_states()

    def _add_child_label(self):
        """Ajoute un nouveau label enfant sous le parent actuellement sélectionné."""
        if (
            not self.current_cluster_data
            or self.current_root_label_index == -1
            or self.current_parent_label_index == -1
        ):
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_parent_selected_title"),
                tr("project_config.no_parent_selected_msg"),
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_child_dialog_title"),
            tr("project_config.add_child_dialog_text"),
        )
        if ok and name:
            name = name.strip()
            if not name:
                return

            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            selected_parent = selected_root["parent_labels"][
                self.current_parent_label_index
            ]
            child_labels_data = selected_parent.get("child_labels", [])

            if any(c["name"] == name for c in child_labels_data):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_child_msg"),
                )
                return

            new_label_data = {
                "name": name,
                "type": "directory",
                "id": str(uuid.uuid4()),
                "full_path": "",
            }  # Added ID and full_path
            child_labels_data.append(new_label_data)
            selected_parent["child_labels"] = (
                child_labels_data  # S'assurer que les données sont à jour
            )

            self.child_list_widget.addItem(name)
            self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
            logger.info(f"Label enfant ajouté : {name}")
            self._update_button_states()
            self.save_button.setEnabled(True)

    def _edit_child_label(self):
        """Modifie le label enfant sélectionné."""
        if (
            not self.current_cluster_data
            or self.current_root_label_index == -1
            or self.current_parent_label_index == -1
        ):
            return

        current_child_row = self.child_list_widget.currentRow()
        if current_child_row == -1:
            return

        label_data = self._get_selected_label_data("child")
        if not label_data:
            return

        old_name = label_data.get("name", "")
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_child_dialog_title"),
            tr("project_config.edit_child_dialog_text"),
            QtWidgets.QLineEdit.Normal,
            old_name,
        )
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name or new_name == old_name:
                return

            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            selected_parent = selected_root["parent_labels"][
                self.current_parent_label_index
            ]
            child_labels_data = selected_parent.get("child_labels", [])

            if any(
                c["name"] == new_name for c in child_labels_data if c is not label_data
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.duplicate_title"),
                    tr("project_config.duplicate_child_msg"),
                )
                return

            label_data["name"] = new_name
            self._update_label_item_text(
                self.child_list_widget, label_data
            )  # Met à jour le texte affiché
            logger.info(f"Label enfant renommé de {old_name} en {new_name}")
            self.save_button.setEnabled(True)

    def _remove_child_label(self):
        """Supprime le label enfant sélectionné."""
        if (
            not self.current_cluster_data
            or self.current_root_label_index == -1
            or self.current_parent_label_index == -1
        ):
            return

        current_child_row = self.child_list_widget.currentRow()
        if current_child_row == -1:
            return

        child_name = self.child_list_widget.currentItem().text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.remove_child_dialog_title"),
            tr("project_config.remove_child_dialog_text").format(child_name=child_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            selected_root = self.current_cluster_data["root_labels"][
                self.current_root_label_index
            ]
            selected_parent = selected_root["parent_labels"][
                self.current_parent_label_index
            ]
            child_labels_data = selected_parent.get("child_labels", [])

            del child_labels_data[current_child_row]
            selected_parent["child_labels"] = (
                child_labels_data  # S'assurer que les données sont à jour
            )

            self.child_list_widget.takeItem(current_child_row)  # Supprimer de l'UI
            self.child_list_widget.setCurrentRow(-1)  # Désélectionner

            logger.info(f"Label enfant supprimé : {child_name}")
            self.save_button.setEnabled(True)
            self._update_button_states()

    def _on_add_new_project(self):
        """Handles adding a new project."""
        new_project_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.new_project_dialog_title"),
            tr("project_config.new_project_dialog_text"),
        )
        if ok and new_project_name:
            new_project_name = new_project_name.strip()
            if not new_project_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.invalid_name_title"),
                    tr("project_config.invalid_name_msg"),
                )
                return

            # Vérifier l'existence dans la base de données via database.get_project_profile
            if self.database and self.database.get_project_profile(new_project_name):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.project_exists_title"),
                    tr("project_config.project_exists_msg").format(
                        project_name=new_project_name
                    ),
                )
                return

            # Créer une nouvelle structure de profil vide avec la nouvelle structure de cluster
            self.current_project_profile_data = {
                "name": new_project_name,
                "turing_ontology": {
                    "cluster": [],
                    "clusters_detailed": [],  # Initialiser avec la nouvelle structure
                },
            }
            # Pas besoin d'ajouter au cache local ici, _save_configuration le fera
            # self.project_profiles[new_project_name] = self.current_project_profile_data
            self.current_project_name = new_project_name

            # Sauvegarder immédiatement le nouveau projet vide dans la base de données
            self._save_configuration(show_message=False)

            self._update_project_combo()  # Actualiser la boîte combinée (cela chargera le nouveau projet)
            self.project_combo.setCurrentText(
                new_project_name
            )  # Sélectionner le nouveau projet
            # _load_profile_into_ui est appelée par _on_project_selected suite au setCurrentText
            # self._load_profile_into_ui(new_project_name)

            self.save_button.setEnabled(True)
            self.delete_project_button.setEnabled(True)
            self.export_dgraph_query_button.setEnabled(
                False
            )  # Nouveau projet, pas encore de données à exporter
            logger.info(f"Nouveau projet '{new_project_name}' initié et sauvegardé.")
        else:
            logger.info("Création du nouveau projet annulée.")

    def _on_delete_project(self):
        """Gère la suppression du projet sélectionné."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_project_selected_title"),
                tr("project_config.no_project_selected_msg_delete"),
            )
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.delete_project_dialog_title"),
            tr("project_config.delete_project_dialog_text").format(
                project_name=self.current_project_name
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                if self.database:
                    success = self.database.delete_project_profile(
                        self.current_project_name
                    )
                    if not success:
                        raise Exception(
                            f"Échec de la suppression du projet '{self.current_project_name}' de la base de données."
                        )
                    logger.info(
                        f"Projet '{self.current_project_name}' supprimé de la base de données."
                    )
                else:
                    raise Exception(
                        "Base de données non disponible pour la suppression du projet."
                    )

                # Supprimer du cache interne après suppression réussie de la BD
                if self.current_project_name in self.project_profiles:
                    del self.project_profiles[self.current_project_name]

                self.project_profile_deleted.emit(self.current_project_name)
                logger.info(
                    f"Projet '{self.current_project_name}' supprimé avec succès."
                )

                self.current_project_name = None
                self.current_project_profile_data = None
                self._update_project_combo()  # Actualiser la boîte combinée
                self._reset_ui()  # Effacer les champs de l'interface utilisateur
                QtWidgets.QMessageBox.information(
                    self,
                    tr("project_config.project_deleted_title"),
                    tr("project_config.project_deleted_msg"),
                )

            except Exception as e:
                logger.error(
                    f"Erreur lors de la suppression du projet '{self.current_project_name}' : {str(e)}"
                )
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("project_config.deletion_error_title"),
                    tr("project_config.deletion_error_msg").format(
                        project_name=self.current_project_name, error=str(e)
                    ),
                )

    def _save_configuration(self, show_message=True):
        """Enregistre la configuration actuelle du projet."""
        if not self.current_project_profile_data:
            if show_message:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.no_project_selected_title"),
                    tr("project_config.no_project_selected_msg_save"),
                )
            return

        project_name = self.project_name_edit.text().strip()
        if not project_name:
            if show_message:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.missing_project_name_title"),
                    tr("project_config.missing_project_name_msg"),
                )
            return

        # Gérer le cas de renommage
        if self.current_project_name and project_name != self.current_project_name:
            reply = QtWidgets.QMessageBox.question(
                self,
                tr("project_config.rename_project_dialog_title"),
                tr("project_config.rename_project_dialog_text").format(
                    old_name=self.current_project_name, new_name=project_name
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                if self.database:
                    # Supprimer l'ancien nom si la base de données est disponible
                    self.database.delete_project_profile(self.current_project_name)
                    logger.info(
                        f"Ancien projet '{self.current_project_name}' supprimé lors du renommage."
                    )

                # Mettre à jour le nom du projet actuel après la suppression réussie de l'ancien
                self.current_project_name = project_name
                self.current_project_profile_data["name"] = (
                    project_name  # Mettre à jour le nom dans les données également
                )
            else:
                return  # L'utilisateur a annulé le renommage

        try:
            if not self.database:
                raise Exception(
                    "Base de données non disponible pour la sauvegarde du projet."
                )

            success = self.database.save_project_profile(
                project_name, self.current_project_profile_data
            )

            if success:
                # Mettre à jour le cache local avec la version finale et enregistrée
                self.project_profiles[project_name] = self.current_project_profile_data
                self.project_profile_saved.emit(
                    project_name, self.current_project_profile_data
                )
                self.current_project_name = project_name  # Assurer que le projet actuel est mis à jour après l'enregistrement
                self._update_project_combo()  # Actualiser la boîte combinée pour refléter les changements
                if show_message:
                    QtWidgets.QMessageBox.information(
                        self,
                        tr("project_config.config_saved_title"),
                        tr("project_config.config_saved_msg").format(
                            project_name=project_name
                        ),
                    )
                logger.info(
                    f"Profil de projet '{project_name}' enregistré avec succès."
                )
            else:
                if show_message:
                    QtWidgets.QMessageBox.critical(
                        self,
                        tr("project_config.save_error_title"),
                        tr("project_config.save_error_msg").format(
                            project_name=project_name
                        ),
                    )
                logger.error(
                    f"Échec de l'enregistrement du profil de projet '{project_name}'."
                )

        except Exception as e:
            logger.error(
                f"Erreur lors de l'enregistrement de la configuration du projet pour '{project_name}' : {str(e)}"
            )
            if show_message:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("project_config.error_title"),
                    tr("project_config.generic_error_msg").format(error=str(e)),
                )
        self._update_button_states()  # Update button states after saving

    def _load_project_profiles(self):
        """Charge tous les profils de projet depuis la base de données."""
        logger.info("Chargement des profils de projet depuis la base de données...")
        try:
            if not self.database:
                logger.error(
                    "Base de données non disponible. Impossible de charger les profils de projet."
                )
                self.project_profiles = {}
                self._update_project_combo()
                self._reset_ui()
                return

            self.project_profiles = self.database.get_all_project_profiles()
            logger.info(
                f"Chargement de {len(self.project_profiles)} profils de projet depuis la base de données."
            )

            # Migration de compatibilité des données après le chargement depuis la BD
            # Ceci est critique pour assurer que les anciennes structures sont mises à jour
            # avant que l'UI ne tente de les lire.
            for project_name, profile in self.project_profiles.items():
                turing_ontology = profile.setdefault("turing_ontology", {})

                # Assurer l'existence de 'clusters_detailed'
                if "clusters_detailed" not in turing_ontology:
                    turing_ontology["clusters_detailed"] = []

                # Migrer l'ancien format 'cluster' (simple liste de noms) vers 'clusters_detailed'
                if (
                    "cluster" in turing_ontology
                    and turing_ontology["cluster"]
                    and not turing_ontology["clusters_detailed"]
                ):
                    logger.warning(
                        f"Migrating old 'cluster' list to 'clusters_detailed' for project '{project_name}'."
                    )
                    for old_cluster_name in turing_ontology["cluster"]:
                        turing_ontology["clusters_detailed"].append(
                            {
                                "name": old_cluster_name,
                                "id": str(uuid.uuid4()),
                                "root_labels": [],
                            }
                        )  # Assign ID during migration
                elif (
                    "cluster" not in turing_ontology
                ):  # Si 'cluster' n'existe pas du tout
                    turing_ontology["cluster"] = []

                # Migrer l'ancien format 'root_labels' s'il était au top-level (avant clusters_detailed)
                if (
                    "root_labels" in turing_ontology
                    and turing_ontology["root_labels"]
                    and not turing_ontology["clusters_detailed"]
                ):
                    logger.warning(
                        f"Migrating top-level 'root_labels' to a default cluster in 'clusters_detailed' for project '{project_name}'."
                    )
                    default_cluster_name = tr(
                        "project_config.default_imported_cluster_name"
                    )  # "Imported_Data"
                    if not turing_ontology[
                        "clusters_detailed"
                    ]:  # Si pas encore de clusters_detailed
                        turing_ontology["clusters_detailed"].append(
                            {
                                "name": default_cluster_name,
                                "id": str(uuid.uuid4()),  # Assign ID during migration
                                "root_labels": turing_ontology.pop(
                                    "root_labels"
                                ),  # Déplacer les labels racines existants
                            }
                        )
                        if default_cluster_name not in turing_ontology["cluster"]:
                            turing_ontology["cluster"].append(default_cluster_name)
                    else:  # Si clusters_detailed existe mais root_labels est top-level
                        # Tenter de fusionner dans le premier cluster existant ou créer un nouveau
                        if (
                            turing_ontology["clusters_detailed"][0]["name"]
                            == default_cluster_name
                        ):
                            turing_ontology["clusters_detailed"][0][
                                "root_labels"
                            ].extend(turing_ontology.pop("root_labels"))
                        else:
                            turing_ontology["clusters_detailed"].append(
                                {
                                    "name": default_cluster_name,
                                    "id": str(
                                        uuid.uuid4()
                                    ),  # Assign ID during migration
                                    "root_labels": turing_ontology.pop("root_labels"),
                                }
                            )
                            if default_cluster_name not in turing_ontology["cluster"]:
                                turing_ontology["cluster"].append(default_cluster_name)
                elif (
                    "root_labels" in turing_ontology
                    and not turing_ontology["root_labels"]
                ):  # S'il est vide, le laisser tel quel ou le supprimer
                    pass  # Laisser vide, la nouvelle logique gérera ça

                # S'assurer que 'cluster' contient les noms de 'clusters_detailed'
                turing_ontology["cluster"] = [
                    c["name"] for c in turing_ontology["clusters_detailed"]
                ]

                # Gérer la rétrocompatibilité pour les types et catégories des labels imbriqués
                def migrate_label_types(labels_list):
                    for label in labels_list:
                        if "id" not in label:  # Assign ID if missing
                            label["id"] = str(uuid.uuid4())
                        if "full_path" not in label:  # Assign full_path if missing
                            label["full_path"] = (
                                ""  # Default empty, should be set on import
                            )

                        if "type" not in label:
                            # Inférence du type basée sur la présence de sous-labels
                            label["type"] = (
                                "directory"
                                if "parent_labels" in label or "child_labels" in label
                                else "file"
                            )

                        if label["type"] == "file":
                            if "category" not in label:
                                label["category"] = []
                            elif isinstance(label["category"], str):
                                label["category"] = [label["category"]]
                        else:  # directory type
                            if (
                                "category" in label
                            ):  # Supprimer la catégorie si c'est un répertoire (ancienne donnée)
                                del label["category"]

                        # Supprimer l'ancienne clé 'categories' si elle existe (très vieilles données)
                        if "categories" in label:
                            del label["categories"]

                        # Assurer que les listes de sous-labels existent
                        if "parent_labels" not in label:
                            label["parent_labels"] = []
                        if "child_labels" not in label:
                            label["child_labels"] = []

                        # Appel récursif pour les sous-labels
                        migrate_label_types(label["parent_labels"])
                        migrate_label_types(label["child_labels"])

                # Appliquer la migration sur tous les labels racines de tous les clusters détaillés
                for cluster_detail in turing_ontology["clusters_detailed"]:
                    migrate_label_types(cluster_detail.get("root_labels", []))

            # Une fois toutes les migrations effectuées, mettez à jour la BD pour chaque profil
            # si des modifications ont été apportées.
            for project_name, profile_data_migrated in self.project_profiles.items():
                # On ne veut pas afficher de QMessageBox ici, juste mettre à jour en arrière-plan
                self.database.save_project_profile(project_name, profile_data_migrated)

            self._update_project_combo()  # Remplir la boîte combinée
            if self.project_profiles:
                # Sélectionner automatiquement le premier projet si disponible
                first_project_name = sorted(self.project_profiles.keys())[0]
                self.project_combo.setCurrentText(first_project_name)
                # La sélection dans le combo box appellera _on_project_selected
                # et donc chargera le profil dans current_project_profile_data et l'UI.
                # Pas besoin d'appeler _load_profile_into_ui directement ici.
                self.current_project_name = first_project_name
                self.current_project_profile_data = self.project_profiles[
                    first_project_name
                ].copy()

                self.delete_project_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.export_dgraph_query_button.setEnabled(
                    self.is_configured()
                )  # Activer si le projet est configuré
            else:
                self._reset_ui()  # Aucun projet, donc réinitialiser l'interface utilisateur
                self.delete_project_button.setEnabled(False)
                self.save_button.setEnabled(False)
                self.export_dgraph_query_button.setEnabled(False)
            self._update_button_states()

        except Exception as e:
            logger.error(
                f"Erreur critique lors du chargement de tous les profils de projet : {str(e)}"
            )
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.loading_error_title"),
                tr("project_config.generic_error_msg").format(error=str(e)),
            )

    def is_configured(self):
        """
        Vérifie si le profil de projet actuel est configuré au minimum.
        Un projet est considéré comme configuré s'il a au moins un cluster ET au moins un label racine
        dans au moins l'un de ses clusters.
        """
        if not self.current_project_profile_data:
            return False
        turing_config = self.current_project_profile_data.get("turing_ontology", {})

        # Vérifier s'il y a des clusters détaillés
        if not turing_config.get("clusters_detailed"):
            return False

        # Vérifier si au moins un cluster détaillé a des labels racines
        for cluster_data in turing_config["clusters_detailed"]:
            if cluster_data.get("root_labels") and len(cluster_data["root_labels"]) > 0:
                return True
        return False

    def _on_export_dgraph_query(self):
        """
        Génère et exporte un fichier Python contenant la requête pydgraph
        pour insérer l'arborescence de l'ontologie du projet actuel.
        """
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.export_dgraph_query_title"),
                tr("project_config.no_project_data_export_msg"),
            )
            return

        if not self.is_configured():
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.export_dgraph_query_title"),
                tr("project_config.not_configured_export_msg"),
            )
            return

        project_name_slug = (
            self.current_project_name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        default_filename = f"dgraph_import_{project_name_slug}.py"

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("project_config.save_dgraph_query_dialog_title"),
            default_filename,
            "Fichiers Python (*.py);;Tous les fichiers (*)",
        )

        if not file_path:
            logger.info("Exportation de la requête Dgraph annulée par l'utilisateur.")
            return

        try:
            generated_code = self._generate_dgraph_import_script(
                self.current_project_profile_data
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(generated_code)

            QtWidgets.QMessageBox.information(
                self,
                tr("project_config.export_dgraph_query_title"),
                tr("project_config.export_dgraph_success_msg").format(
                    file_path=file_path
                ),
            )
            logger.info(f"Requête Dgraph exportée avec succès vers : {file_path}")

        except Exception as e:
            logger.error(
                f"Erreur lors de l'exportation de la requête Dgraph : {str(e)}"
            )
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.export_dgraph_query_title"),
                tr("project_config.export_dgraph_error_msg").format(error=str(e)),
            )

    def _generate_dgraph_import_script(self, project_data):
        """
        Génère le contenu Python complet pour l'insertion Dgraph.
        """
        # User and Workspace IDs (provided by the user)
        USER_ID = "47ea051e-8cce-4bee-bfe8-76489dd98b60"
        WORKSPACE_ID = "e8bfa5a1-512d-46e3-a4cc-69aecbb9cad9"

        script_content = f"""
import pydgraph
import json
import logging
import uuid # For generating unique IDs
from datetime import datetime

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dgraph Configuration ---
DGRAPH_ADDR = 'localhost:9080' # Dgraph gRPC server address

USER_ID = "{USER_ID}"
WORKSPACE_ID = "{WORKSPACE_ID}"

def generate_dgraph_mutations(client, project_data):
    \"\"\"
    Generates the list of Dgraph mutations from the Liris project ontology data.
    Uses blank node identifiers (_:name) to create nodes and establish relationships.
    Workspace, Cluster, and Label nodes are managed with @upsert via their 'id'.
    \"\"\"
    mutations = []
    
    turing_ontology = project_data.get("turing_ontology", {{}})
    # Maintenant, nous utilisons 'clusters_detailed' qui contient la structure hiérarchique
    clusters_detailed_from_project = turing_ontology.get("clusters_detailed", [])

    # Dictionary to map cluster's unique_id (UUID) to its Dgraph blank UID
    # This is needed for linking the ClusterManagement node to specific Cluster UIDs
    cluster_uuid_to_blank_uid_map = {{}} 
    
    # List to hold the blank UIDs of all clusters, to be linked to ClusterManagement
    all_cluster_blank_uids_for_workspace = []

    # 1. Prepare mutations for Cluster nodes
    for i, cluster_data in enumerate(clusters_detailed_from_project):
        cluster_name = cluster_data["name"]
        cluster_unique_id = cluster_data["id"] # Use the ID already assigned during import
        cluster_blank_uid = f"_:cluster_{{cluster_unique_id.replace('-', '_')}}"
        
        cluster_uuid_to_blank_uid_map[cluster_unique_id] = cluster_blank_uid

        cluster_mutation = {{
            "uid": cluster_blank_uid,
            "dgraph.type": "Cluster",
            "id": str(cluster_unique_id), # Used by @upsert to find/create
            "name": cluster_name,
            "userId": USER_ID, # Corrected to userId
            "createdAt": datetime.now().isoformat() + "Z", # Add creation timestamp
            "updatedAt": datetime.now().isoformat() + "Z", # Add update timestamp
        }}
        mutations.append(cluster_mutation)
        
        # MODIFICATION ICI: Stocker l'UUID string au lieu de la référence UID
        all_cluster_blank_uids_for_workspace.append(cluster_unique_id)
        logger.debug(f"Prepared cluster: {{cluster_name}} (ID: {{cluster_unique_id}}, Blank UID: {{cluster_blank_uid}})")

    # 2. Prepare mutations for Workspace and its ClusterManagement
    workspace_unique_id = WORKSPACE_ID # Use the provided WORKSPACE_ID as its unique ID
    workspace_mutation = {{
        "uid": f"_:workspace_node", # Blank UID for the Workspace
        "dgraph.type": "Workspace",
        "id": workspace_unique_id, # The unique ID of the Workspace for upsert
        "ownerId": USER_ID, # The user ID of the workspace owner
        "updatedAt": datetime.now().isoformat() + "Z",
        "clusterManagement": {{
            "uid": f"_:cluster_management_node", # Blank UID for the ClusterManagement
            "dgraph.type": "ClusterManagement",
            "lastUpdated": datetime.now().isoformat() + "Z",
            "version": "1.0", # Default version
            # MODIFICATION CRITIQUE ICI
            "ClusterManagement.clusters": all_cluster_blank_uids_for_workspace
        }}
    }}
    mutations.append(workspace_mutation)
    logger.debug(f"Prepared Workspace (ID: {{workspace_unique_id}}) and its ClusterManagement.")

    # Helper function to process labels recursively
    # It takes:
    #   label_data: The current dictionary from Liris ontology data (e.g., a root_label, parent_label, or child_label)
    #   level_numeric: 0 for root, 1 for parent, 2 for child (for Label.level)
    #   parent_uid_for_relation: Dgraph blank UID of the direct parent (for Label.parents relationship)
    #   current_path_ids: List of UUID strings for building Label.path (IDs of ancestors)
    #   containing_cluster_unique_id: The UUID of the specific cluster this label belongs to
    #   containing_cluster_blank_uid: The blank UID of the specific cluster this label belongs to
    #   all_mutations: The list to append generated mutations to

    def _process_label_hierarchy(label_data, level_numeric, parent_uid_for_relation, current_path_ids, containing_cluster_unique_id, containing_cluster_blank_uid, all_mutations):
        label_name = label_data["name"]
        label_category = label_data.get("category", [])
        
        # Generate a full UUID for the label's unique ID
        label_unique_id = label_data["id"] # Use the ID already assigned during import

        # Dgraph blank UID for this new label node
        label_blank_uid = f"_:label_{{label_unique_id.replace('-', '_')}}"
        
        # Build the full path for Label.path using unique IDs
        if level_numeric == 0: # Root label
            full_path = "/"
        else:
            full_path = "/".join(current_path_ids) + "/"

        label_node = {{
            "uid": label_blank_uid,
            "dgraph.type": "Label",
            "id": label_unique_id, # Used by @upsert
            "name": label_name,
            "level": str(level_numeric), # Store as string "0", "1", "2"
            "path": full_path,
            "category": label_category,
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z"
            # Removed "type": label_type as requested
        }}

        # Link to parent if exists using 'parents' predicate and set 'parentId' string
        if parent_uid_for_relation:
            label_node["parents"] = [{{"uid": parent_uid_for_relation}}]
            # parentId refers to the 'id' string of the parent
            # The last element in current_path_ids is the immediate parent's ID
            if current_path_ids:
                label_node["parentId"] = current_path_ids[-1] 
            else:
                label_node["parentId"] = "" # Should not happen for non-root labels with parent_uid

        # Link this label ONLY to its containing cluster
        if containing_cluster_unique_id and containing_cluster_blank_uid:
            # MODIFICATION CRITIQUE ICI
            label_node["Label.clusters"] = [{{"uid": containing_cluster_blank_uid}}]
            label_node["clusterIds"] = [containing_cluster_unique_id]
            logger.debug(f"  Linked label '{{label_name}}' (level {{level_numeric}}) to its containing cluster (ID: {{containing_cluster_unique_id}}).")
        else:
            logger.warning(f"  No specific containing cluster info for label '{{label_name}}' (level {{level_numeric}}).")


        all_mutations.append(label_node)
        logger.debug(f"Prepared Label (level {{level_numeric}}): {{label_name}} (ID: {{label_unique_id}}, Blank UID: {{label_blank_uid}})")

        # Recursively process children based on the Liris data model structure
        next_level_numeric = level_numeric + 1
        children_list_key = None # Key in the Liris data model for children of current level

        if level_numeric == 0: # Root level
            children_list_key = "parents" 
        elif level_numeric == 1: # Parent level
            children_list_key = "children"
        # For level_numeric == 2 (child), there are no further nested labels in the current Liris data model

        if children_list_key and children_list_key in label_data:
            for child_label_data in label_data[children_list_key]:
                _process_label_hierarchy(
                    child_label_data,
                    next_level_numeric,
                    label_blank_uid, # Current label's blank UID is parent_uid for child
                    current_path_ids + [label_unique_id], # Add current label's ID to path for next level
                    containing_cluster_unique_id, # Pass the same containing cluster info down
                    containing_cluster_blank_uid,
                    all_mutations
                )
    
    # 3. Process Labels for EACH Cluster in 'clusters_detailed'
    for cluster_data in clusters_detailed_from_project:
        cluster_name = cluster_data["name"]
        current_cluster_unique_id = cluster_data["id"] # Use the ID from the Liris data
        current_cluster_blank_uid = cluster_uuid_to_blank_uid_map.get(current_cluster_unique_id)

        if not current_cluster_unique_id or not current_cluster_blank_uid:
            logger.warning(f"Could not find Dgraph ID/UID for cluster '{{cluster_name}}'. Labels within this cluster may not be correctly linked.")
            continue

        root_labels_of_this_cluster = cluster_data.get("root_labels", [])
        for root_label in root_labels_of_this_cluster:
            _process_label_hierarchy(
                root_label,
                0, # Numeric level 0 for root
                None, # Root labels have no Dgraph parent UID for relation
                [], # Start with an empty path of IDs for root
                current_cluster_unique_id, # Pass the specific unique ID of the containing cluster
                current_cluster_blank_uid, # Pass the specific blank UID of the containing cluster
                mutations
            )
    
    return mutations

def insert_hierarchy(client, project_data):
    \"\"\"
    Executes Dgraph mutations to insert the ontology.
    \"\"\"
    txn = client.txn()
    try:
        mutations = generate_dgraph_mutations(client, project_data)
        if not mutations:
            logger.info("No mutations to perform for the current project data.")
            return

        assigned = txn.mutate(set_obj=mutations)
        txn.commit()

        logger.info("Ontology imported successfully.")
        logger.info(f"Assigned UIDs: {{assigned.uids}}")

    except Exception as e:
        logger.error(f"Error importing ontology: {{e}}")
        try:
            txn.discard()
            logger.info("Transaction discarded.")
        except Exception as discard_e:
            logger.error(f"Error discarding transaction: {{discard_e}}")
    finally:
        # Ensure transaction is always finalized (committed or discarded)
        try:
            txn.discard()
        except pydgraph.AbortedError:
            pass # Already committed or discarded, ignore error


def main():
    # Project data exported from Liris
    # This data will be dynamically inserted by the script generator
    # PROJECT_DATA_PLACEHOLDER
    
    client_stub = pydgraph.DgraphClientStub(DGRAPH_ADDR)
    client = pydgraph.DgraphClient(client_stub)

    logger.info(f"Attempting to connect to Dgraph at {{DGRAPH_ADDR}}")
    
    # Step 1: Insert the ontology hierarchy
    insert_hierarchy(client, PROJECT_DATA)

if __name__ == '__main__':
    main()
"""

        # Insert the actual project JSON data into the generated script
        project_data_json_str = json.dumps(project_data, indent=4, ensure_ascii=False)
        project_data_formatted = (
            "    PROJECT_DATA = " + project_data_json_str.replace("\n", "\n    ") + "\n"
        )

        final_script_content = script_content.replace(
            "    # PROJECT_DATA_PLACEHOLDER", project_data_formatted
        )

        return final_script_content
