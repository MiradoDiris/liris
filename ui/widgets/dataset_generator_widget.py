from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from ui.styles.theme import Theme
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
import logging

logger = logging.getLogger(__name__)


class DatasetGeneratorWidget(QtWidgets.QWidget):
    """
    Widget amélioré pour la gestion de la génération de datasets avec une structure hiérarchique
    """

    def __init__(self, conductor=None, parent=None):
        super().__init__(parent)

        self.data = {"context": []}  # Structure de données interne
        self.conductor = conductor
        # Accéder à l'instance de la base de données via le conductor
        self.database = None
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

        # Index pour les labels racines/parents/enfants sélectionnés pour les mises à jour dynamiques
        self.current_root_label_index = -1
        self.current_parent_label_index = -1
        self.current_child_label_index = -1

        self.current_platform = None

        if self.conductor:
            logger.info(
                "Conducteur initialisé dans le constructeur de DatasetGenerationWidget"
            )
        else:
            logger.warning("Aucun conducteur fourni lors de l'initialisation")

        self._init_ui()

    def set_database(self, database):
        """Définir la base de données pour accéder aux projets et aux plateformes."""
        self.database = database
        if self.database:
            logger.info("Base de données définie pour DatasetGenerationWidget")
        else:
            logger.error("Aucune base de données fournie au DatasetGenerationWidget")

    def set_conductor(self, conductor):
        """Définir le conducteur pour le contrôle du navigateur et des entrées."""
        self.conductor = conductor
        logger.info("Conducteur défini pour DatasetGenerationWidget")

    def set_platforms(self, profiles):
        """
        Définit la liste des profils de plateformes disponibles
        Args:
            profiles (dict): Dictionnaire des profils de plateformes {name: profile_data}
        """
        self.profiles = profiles
        self.platforms = self.conductor.database.get_all_platforms()

        for name in self.profiles:
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked)

        logger.info(f"Chargé {len(profiles)} profils de plateformes.")

    def _init_ui(self):
        """Configure l'interface utilisateur améliorée"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: %s;
                color: white;
            }
        """
            % Theme.SECONDARY_COLOR
        )

        ajouter_tab = QtWidgets.QWidget()
        self._create_ajouter_tab(ajouter_tab)
        self.tab_widget.addTab(ajouter_tab, "➕ Créer projet")

        projet_tab = QtWidgets.QWidget()
        self._create_projet_tab(projet_tab)
        self.tab_widget.addTab(projet_tab, "📊 Dataset")

        main_layout.addWidget(self.tab_widget)

    def _create_ajouter_tab(self, parent):
        """Crée l'onglet Ajouter avec une disposition verticale"""
        layout = QtWidgets.QVBoxLayout(parent)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        # Conteneur pour les deux colonnes (haut)
        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(20)
        layout.addLayout(top_columns_layout)

        # --- Colonne de gauche (Sélection et Détails du Projet) ---
        left_column_layout = QtWidgets.QVBoxLayout()

        explanation = QtWidgets.QLabel(tr("dataset_project_config.explanation"))
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        left_column_layout.addWidget(explanation)

        # Groupe pour la sélection du projet
        project_selection_group = QtWidgets.QGroupBox(
            tr("dataset_project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)

        self.add_project_button = QtWidgets.QPushButton(
            tr("dataset_project_config.new_project_button")
        )
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        self.delete_project_button = QtWidgets.QPushButton(
            tr("dataset_project_config.delete_project_button")
        )
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)
        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        # Groupe pour les détails du projet (Nom, Typologie de contexte)
        details_group = QtWidgets.QGroupBox(tr("dataset_project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(15)
        details_form_layout.setAlignment(
            Qt.AlignHCenter | Qt.AlignTop
        )  # Alignement horizontal au centre, vertical en haut

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("dataset_project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_form_layout.addRow(
            tr("dataset_project_config.project_name_label"), self.project_name_edit
        )

        # MODIFICATION: QListWidget pour la gestion des typologies multiples
        # Ceci est maintenant le widget principal pour naviguer dans la typologie
        typologie_list_layout = QtWidgets.QVBoxLayout()
        typologie_list_title = QtWidgets.QLabel(
            tr("dataset_project_config.typologie_label")
        )
        typologie_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        typologie_list_layout.addWidget(typologie_list_title)

        self.typologie_list_widget = QtWidgets.QListWidget()
        self.typologie_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.typologie_list_widget.setMinimumHeight(60)
        # Connecter le signal de changement d'élément pour charger les labels racines de la typologie
        self.typologie_list_widget.currentItemChanged.connect(
            self._on_typologie_selected
        )
        typologie_list_layout.addWidget(self.typologie_list_widget)

        typologie_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_typologie_button = QtWidgets.QPushButton(
            tr("dataset_project_config.add_typologie_button")
        )
        self.add_typologie_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_typologie_button.clicked.connect(self._add_typologie)

        self.edit_typologie_button = QtWidgets.QPushButton(
            tr("dataset_project_config.edit_typologie_button")
        )
        self.edit_typologie_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_typologie_button.clicked.connect(self._edit_typologie)

        self.remove_typologie_button = QtWidgets.QPushButton(
            tr("dataset_project_config.delete_typologie_button")
        )
        self.remove_typologie_button.setStyleSheet(
            PlatformConfigStyle.get_button_style()
        )
        self.remove_typologie_button.clicked.connect(self._remove_typologie)

        typologie_buttons_layout.addWidget(self.add_typologie_button)
        typologie_buttons_layout.addWidget(self.edit_typologie_button)
        typologie_buttons_layout.addWidget(self.remove_typologie_button)
        typologie_list_layout.addLayout(typologie_buttons_layout)

        details_form_layout.addRow(
            typologie_list_layout
        )  # Ajout du layout des typologies au formulaire

        left_column_layout.addWidget(details_group)

        top_columns_layout.addLayout(
            left_column_layout, 7
        )  # Facteur d'étirement de 3 pour la colonne de gauche (environ 15%)

        # --- Colonne de droite (Taxionomie: Hiérarchie avec ScrollArea) ---
        right_column_container = QtWidgets.QScrollArea()
        right_column_container.setWidgetResizable(True)
        right_column_container.setStyleSheet("border: none;")

        hierarchy_scroll_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(hierarchy_scroll_content)
        hierarchy_layout.setSpacing(10)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)

        hierarchy_group = QtWidgets.QGroupBox(
            tr("dataset_project_config.hierarchy_group")
        )
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(
            10
        )  # Espacement pour les éléments dans ce groupe

        # 1. Labels Racines (MAINTENANT DANS LA COLONNE DE DROITE)
        root_label_title = QtWidgets.QLabel(
            tr("dataset_project_config.root_labels_list_label")
        )
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(PlatformConfigStyle.get_list_style())
        self.root_list_widget.setMinimumHeight(100)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        self.add_root_button = QtWidgets.QPushButton(
            tr("dataset_project_config.add_root_button")
        )
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)
        self.edit_root_button = QtWidgets.QPushButton(
            tr("dataset_project_config.edit_root_button")
        )
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)
        self.remove_root_button = QtWidgets.QPushButton(
            tr("dataset_project_config.remove_root_button")
        )
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)
        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)

        # Bouton Modifier Catégorie pour les racines
        self.modify_category_root_button = QtWidgets.QPushButton(
            tr("dataset_project_config.modify_category_button")
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
            right_column_container, 13
        )  # Facteur d'étirement de 17 pour la colonne de droite (environ 85%)

        # --- Boutons Enregistrer et Exporter (en bas de la fenêtre, centré) ---
        save_export_layout = QtWidgets.QHBoxLayout()
        save_export_layout.addStretch()

        self.save_button = QtWidgets.QPushButton(
            "💾 " + tr("dataset_project_config.save_button")
        )
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._save_configuration)
        self.save_button.setEnabled(
            False
        )  # Désactivé jusqu'à ce qu'un projet soit sélectionné ou ajouté
        save_export_layout.addWidget(self.save_button)

        save_export_layout.addStretch()
        layout.addLayout(
            save_export_layout
        )  # Ajoute le layout des boutons au layout vertical principal

    def _on_project_selected(self, index):
        """Gestion du changement de projet sélectionné"""
        if index >= 0:
            project_name = self.project_combo.itemText(index)
            print(f"[Projet] Projet sélectionné : {project_name}")
        else:
            print("[Projet] Aucun projet sélectionné")

    def _on_add_new_project(self):
        """Gestion de l'ajout d'un nouveau projet"""
        print("[Projet] Création d'un nouveau projet demandée")
        """Handles adding a new project."""
        new_project_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.new_project_dialog_title"),
            tr("project_config.new_project_dialog_text"),
        )
        # 2. Demander la description du projet
        new_project_description, ok_desc = QtWidgets.QInputDialog.getMultiLineText(
            self,
            tr("project_config.new_project_description_title"),
            tr("project_config.new_project_description_text"),
        )
        if not ok_desc:
            new_project_description = ""

        if ok and new_project_name and new_project_description and ok_desc:
            new_project_name = new_project_name.strip()
            new_project_description = new_project_description.strip()
            if not new_project_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.invalid_name_title"),
                    tr("project_config.invalid_name_msg"),
                )
                return

            # Vérifier l'existence dans la base de données via database.get_project_profile
            if self.database and self.database.get_dataset_projet(new_project_name):
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
                "nom": new_project_name,
                "description": new_project_description,
            }
            # Pas besoin d'ajouter au cache local ici, _save_configuration le fera
            # self.project_profiles[new_project_name] = self.current_project_profile_data
            self.current_project_name = new_project_name

            # Sauvegarder immédiatement le nouveau projet vide dans la base de données
            self._save_configuration(show_message=False)

            self.save_button.setEnabled(True)
            self.delete_project_button.setEnabled(True)
            logger.info(f"Nouveau projet '{new_project_name}' initié et sauvegardé.")
        else:
            logger.info("Création du nouveau projet annulée.")

    def _save_configuration(self, show_message=True):
        """Sauvegarde la configuration actuelle du projet dans la base de données"""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_project_selected_title"),
                tr("project_config.no_project_selected_msg"),
            )
            return

        # Mettre à jour les données du profil actuel
        self.current_project_profile_data["nom"] = self.project_name_edit.text().strip()

    def _on_delete_project(self):
        """Gestion de la suppression d'un projet"""
        current_index = self.project_combo.currentIndex()
        if current_index >= 0:
            project_name = self.project_combo.itemText(current_index)
            print(f"[Projet] Suppression du projet : {project_name}")
        else:
            print("[Projet] Aucun projet sélectionné pour suppression")

    def _add_typologie(self):
        """Ajoute une nouvelle typologie"""
        print("[Typologie] Ajout d'une nouvelle typologie")

    def _edit_typologie(self):
        """Édite la typologie sélectionnée"""
        current_item = self.typologie_list_widget.currentItem()
        if current_item:
            print(f"[Typologie] Édition de la typologie : {current_item.text()}")
        else:
            print("[Typologie] Aucune typologie sélectionnée pour édition")

    def _remove_typologie(self):
        """Supprime la typologie sélectionnée"""
        current_item = self.typologie_list_widget.currentItem()
        if current_item:
            print(f"[Typologie] Suppression de la typologie : {current_item.text()}")
        else:
            print("[Typologie] Aucune typologie sélectionnée pour suppression")

    def _on_typologie_selected(self, current, previous):
        """Gestion du changement de sélection de typologie"""
        if current:
            print(f"[Typologie] Typologie sélectionnée : {current.text()}")
        else:
            print("[Typologie] Aucune typologie sélectionnée")

    def _on_root_label_selected(self, current, previous):
        """Gestion de la sélection d'un label racine"""
        if current:
            print(f"[Root Label] Sélectionné : {current.text()}")
        else:
            print("[Root Label] Aucune sélection")

    def _add_root_label(self):
        """Ajout d'un label racine"""
        print("[Root Label] Ajout d'un nouveau label racine")

    def _edit_root_label(self):
        """Édition du label racine sélectionné"""
        current_item = self.root_list_widget.currentItem()
        if current_item:
            print(f"[Root Label] Édition de : {current_item.text()}")
        else:
            print("[Root Label] Aucun label racine sélectionné pour édition")

    def _remove_root_label(self):
        """Suppression du label racine sélectionné"""
        current_item = self.root_list_widget.currentItem()
        if current_item:
            print(f"[Root Label] Suppression de : {current_item.text()}")
        else:
            print("[Root Label] Aucun label racine sélectionné pour suppression")

    def _modify_category_for_selected_label(self, label_type):
        """Modification de la catégorie pour un label"""
        if label_type == "root":
            current_item = self.root_list_widget.currentItem()
            if current_item:
                print(
                    f"[Root Label] Modification catégorie pour : {current_item.text()}"
                )
            else:
                print(
                    "[Root Label] Aucun label racine sélectionné pour modification de catégorie"
                )
        else:
            print(
                f"[Label] Modification catégorie non gérée pour le type : {label_type}"
            )

    # ======== LABELS PARENTS ========
    def _on_parent_label_selected(self, current, previous):
        """Gestion de la sélection d'un label parent"""
        if current:
            print(f"[Parent Label] Sélectionné : {current.text()}")
        else:
            print("[Parent Label] Aucune sélection")

    def _add_parent_label(self):
        """Ajout d'un label parent"""
        print("[Parent Label] Ajout d'un nouveau label parent")

    def _edit_parent_label(self):
        """Édition du label parent sélectionné"""
        current_item = self.parent_list_widget.currentItem()
        if current_item:
            print(f"[Parent Label] Édition de : {current_item.text()}")
        else:
            print("[Parent Label] Aucun label parent sélectionné pour édition")

    def _remove_parent_label(self):
        """Suppression du label parent sélectionné"""
        current_item = self.parent_list_widget.currentItem()
        if current_item:
            print(f"[Parent Label] Suppression de : {current_item.text()}")
        else:
            print("[Parent Label] Aucun label parent sélectionné pour suppression")

    # ======== LABELS ENFANTS ========
    def _on_child_label_selected(self, current, previous):
        """Gestion de la sélection d'un label enfant"""
        if current:
            print(f"[Child Label] Sélectionné : {current.text()}")
        else:
            print("[Child Label] Aucune sélection")

    def _add_child_label(self):
        """Ajout d'un label enfant"""
        print("[Child Label] Ajout d'un nouveau label enfant")

    def _edit_child_label(self):
        """Édition du label enfant sélectionné"""
        current_item = self.child_list_widget.currentItem()
        if current_item:
            print(f"[Child Label] Édition de : {current_item.text()}")
        else:
            print("[Child Label] Aucun label enfant sélectionné pour édition")

    def _remove_child_label(self):
        """Suppression du label enfant sélectionné"""
        current_item = self.child_list_widget.currentItem()
        if current_item:
            print(f"[Child Label] Suppression de : {current_item.text()}")
        else:
            print("[Child Label] Aucun label enfant sélectionné pour suppression")

    def _create_projet_tab(self, parent):
        """Crée l'onglet Projet avec aperçu de la structure et panneau de configuration"""
        layout = QtWidgets.QHBoxLayout(parent)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        # ======= COLONNE GAUCHE : Aperçu de la structure =======
        left_frame = QtWidgets.QFrame()
        left_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        left_frame.setStyleSheet(
            "background-color: white; border-radius: 6px; border: 1px solid #ccc;"
        )

        left_layout = QtWidgets.QVBoxLayout(left_frame)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)

        lbl_apercu = QtWidgets.QLabel("📂 Aperçu de la structure")
        lbl_apercu.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(lbl_apercu)

        apercu_view = QtWidgets.QTextEdit()
        apercu_view.setReadOnly(True)
        apercu_view.setStyleSheet(
            "background-color: #fafafa; border: 1px solid #ddd; border-radius: 4px;"
        )
        left_layout.addWidget(apercu_view, 1)  # 1 = prend tout l'espace restant

        # ======= COLONNE DROITE : Configuration =======
        right_frame = QtWidgets.QFrame()
        right_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        right_frame.setStyleSheet(
            "background-color: white; border-radius: 6px; border: 1px solid #ccc;"
        )

        right_layout = QtWidgets.QVBoxLayout(right_frame)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        # Titre configuration
        lbl_config = QtWidgets.QLabel("⚙️ Configuration")
        lbl_config.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(lbl_config)

        lbl_theme = QtWidgets.QLabel("Sélectionnez un thème à configurer")
        lbl_theme.setStyleSheet(
            "background-color: #f1f1f1; padding: 6px; border-radius: 4px;"
        )
        right_layout.addWidget(lbl_theme)

        # Champ plateforme
        lbl_plateforme = QtWidgets.QLabel("🖥 Plateforme")
        cb_plateforme = QtWidgets.QComboBox()
        cb_plateforme.setPlaceholderText("Sélectionnez une plateforme...")
        right_layout.addWidget(lbl_plateforme)
        right_layout.addWidget(cb_plateforme)

        # Description
        lbl_description = QtWidgets.QLabel("📝 Description")
        txt_description = QtWidgets.QTextEdit()
        txt_description.setPlaceholderText(
            "Entrez la description pour la génération du dataset..."
        )
        right_layout.addWidget(lbl_description)
        right_layout.addWidget(txt_description)

        # Format de sortie
        lbl_format = QtWidgets.QLabel("📄 Format de sortie")
        cb_format = QtWidgets.QComboBox()
        cb_format.addItems(["JSON", "CSV", "Parquet"])
        right_layout.addWidget(lbl_format)
        right_layout.addWidget(cb_format)

        # Nombre d'échantillons
        lbl_samples = QtWidgets.QLabel("🔢 Nombre d'échantillons")
        spin_samples = QtWidgets.QSpinBox()
        spin_samples.setRange(1, 1000000)
        spin_samples.setValue(100)
        right_layout.addWidget(lbl_samples)
        right_layout.addWidget(spin_samples)

        # Technique d'entraînement
        lbl_technique = QtWidgets.QLabel("🧠 Technique d'entraînement")
        cb_technique = QtWidgets.QComboBox()
        cb_technique.addItems(["Full SFT", "RLHF", "Fine-tuning"])
        right_layout.addWidget(lbl_technique)
        right_layout.addWidget(cb_technique)

        # Bouton Génération
        btn_generation = QtWidgets.QPushButton("🚀 Génération")
        btn_generation.setStyleSheet(f"""
            background-color: {Theme.SECONDARY_COLOR};
            color: white;
            font-weight: bold;
            padding: 10px;
            border-radius: 6px;
        """)
        right_layout.addWidget(btn_generation)

        # Ajout des colonnes gauche et droite au layout principal
        layout.addWidget(left_frame, 3)  # Poids 3
        layout.addWidget(right_frame, 2)  # Poids 2
