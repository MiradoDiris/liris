import os
import sqlite3
import json
import logging
from collections import Counter
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from ui.styles.theme import Theme
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

class DatasetStrategyWidget(QtWidgets.QWidget):
    """
    Widget pour l'onglet 'Stratégie de dataset' du système Liris Data Science.
    Permet de définir les typologies de contextes et visualiser leur représentativité.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Structure de données pour les typologies de contextes
        self.project_data = {
            "nom": "",
            "description": "",
            "typologies": []
        }

        # Données pour le camembert (représentativité des batches/combinaisons)
        self.batch_data = {}  # Renommé pour clarifier : batch = combinaison de typologies

        # États de sélection pour la navigation hiérarchique
        self.selected_typologie = None
        self.selected_cluster = None
        self.selected_root = None
        self.selected_parent = None

        # Connexion à la base de données
        self.db_connection = None
        self._init_database()

        self._init_ui()
        self._load_existing_projects()

    def _init_database(self):
        """Initialise la connexion à la base de données SQLite"""
        try:
            db_path = os.path.join("data", "liris.db")
            os.makedirs("data", exist_ok=True)

            self.db_connection = sqlite3.connect(db_path)
            self.db_connection.row_factory = sqlite3.Row

            self._create_tables()
            logger.info(f"Base de données initialisée : {db_path}")

        except Exception as e:
            logger.error(f"Erreur initialisation DB : {str(e)}")
            self.db_connection = None

    def _create_tables(self):
        """Crée les tables nécessaires dans la base de données SQLite."""
        try:
            cursor = self.db_connection.cursor()

            # Table pour les projets de dataset
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS project (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT UNIQUE NOT NULL,
                               description TEXT,
                               data TEXT,
                               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
            ''')

            # Table pour les batches (combinaisons de contextes)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS dataset_batches (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_name TEXT NOT NULL,
                               batch_name TEXT NOT NULL,
                               sample_count INTEGER DEFAULT 0,
                               percentage REAL DEFAULT 0.0,
                               typologie_combination TEXT,
                               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               FOREIGN KEY (
                                    project_name
                               )
                                REFERENCES projects (
                                    name
                                )
                           )
            ''')

            self.db_connection.commit()
            logger.info("Tables créées avec succès")

        except sqlite3.Error as e:
            logger.error(f"Erreur lors de la création des tables : {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Erreur Base de Données",
                f"Impossible de créer les tables de la base de données : {str(e)}"
            )

    def _init_ui(self):
        """Configure l'interface utilisateur optimisée"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Titre de l'onglet
        title_label = QtWidgets.QLabel("Stratégie de Dataset")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px 0px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Layout horizontal principal (3 colonnes)
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(15)

        # ===== COLONNE 1 : Gestion des projets =====
        self._create_project_panel(content_layout)

        # ===== COLONNE 2 : Structure hiérarchique des typologies =====
        self._create_structure_panel(content_layout)

        # ===== COLONNE 3 : Camembert et représentativité des batches =====
        self._create_strategy_panel(content_layout)

        main_layout.addLayout(content_layout)

        # Boutons d'action en bas
        self._create_action_buttons(main_layout)

    def _create_project_panel(self, parent_layout):
        """Crée le panneau de gestion des projets"""
        project_frame = QtWidgets.QFrame()
        project_frame.setFixedWidth(250)
        project_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        project_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #bdc3c7;
            }
        """)

        layout = QtWidgets.QVBoxLayout(project_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Titre du panneau
        title = QtWidgets.QLabel("Projets")
        title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        layout.addWidget(title)

        # Sélection du projet
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.currentTextChanged.connect(self._on_project_selected)
        layout.addWidget(self.project_combo)

        # Boutons de gestion
        buttons_layout = QtWidgets.QHBoxLayout()

        self.new_project_btn = QtWidgets.QPushButton("Nouveau")
        self.new_project_btn.setFixedSize(70, 25)
        self.new_project_btn.clicked.connect(self._create_new_project)
        buttons_layout.addWidget(self.new_project_btn)

        self.delete_project_btn = QtWidgets.QPushButton("Supprimer")
        self.delete_project_btn.setFixedSize(70, 25)
        self.delete_project_btn.clicked.connect(self._delete_current_project)
        self.delete_project_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_project_btn)

        layout.addLayout(buttons_layout)

        # Détails du projet
        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setPlaceholderText("Nom du projet...")
        layout.addWidget(self.project_name_edit)

        self.project_desc_edit = QtWidgets.QTextEdit()
        self.project_desc_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_desc_edit.setPlaceholderText("Description...")
        self.project_desc_edit.setMaximumHeight(60)
        layout.addWidget(self.project_desc_edit)

        # Informations du projet
        self.project_info = QtWidgets.QLabel()
        self.project_info.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 8px;
            font-size: 11px;
            color: #6c757d;
        """)
        self.project_info.setWordWrap(True)
        self.project_info.setMinimumHeight(80)
        layout.addWidget(self.project_info)

        layout.addStretch()
        parent_layout.addWidget(project_frame)

    def _create_structure_panel(self, parent_layout):
        """Crée le panneau de gestion des typologies de contextes"""
        structure_frame = QtWidgets.QFrame()
        structure_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        structure_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #bdc3c7;
            }
        """)

        layout = QtWidgets.QVBoxLayout(structure_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Titre avec navigation
        header_layout = QtWidgets.QHBoxLayout()

        title = QtWidgets.QLabel("Typologies de Contextes")
        title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        header_layout.addWidget(title)

        # Bouton pour revenir à la racine
        self.reset_selection_btn = QtWidgets.QPushButton("Racine")
        self.reset_selection_btn.setFixedSize(50, 25)
        self.reset_selection_btn.clicked.connect(self._reset_selection)
        header_layout.addWidget(self.reset_selection_btn)

        header_layout.addStretch()

        # Bouton d'ajout contextuel
        self.add_element_btn = QtWidgets.QPushButton("Ajouter")
        self.add_element_btn.setFixedSize(60, 25)
        self.add_element_btn.clicked.connect(self._add_element)
        header_layout.addWidget(self.add_element_btn)

        layout.addLayout(header_layout)

        # Fil d'Ariane (breadcrumb) - Navigation dans la hiérarchie
        self.breadcrumb = QtWidgets.QLabel("")
        self.breadcrumb.setStyleSheet("""
            background-color: #e9ecef;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
            color: #495057;
        """)
        self.breadcrumb.setMinimumHeight(25)
        layout.addWidget(self.breadcrumb)

        # Arborescence principale avec structure hiérarchique expansible
        self.structure_tree = QtWidgets.QTreeWidget()
        self.structure_tree.setHeaderHidden(True)
        self.structure_tree.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                alternate-background-color: #f8f9fa;
                font-family: 'Courier New', monospace;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #e3f2fd;
            }
            QTreeWidget::item:selected {
                background-color: #2196f3;
                color: white;
            }
        """)
        self.structure_tree.setAlternatingRowColors(True)
        self.structure_tree.itemClicked.connect(self._on_item_clicked)
        self.structure_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.structure_tree)

        # Boutons d'action pour l'élément sélectionné
        actions_layout = QtWidgets.QHBoxLayout()

        self.edit_element_btn = QtWidgets.QPushButton("Modifier")
        self.edit_element_btn.setFixedSize(60, 25)
        self.edit_element_btn.clicked.connect(self._edit_element)
        self.edit_element_btn.setEnabled(False)
        actions_layout.addWidget(self.edit_element_btn)

        self.delete_element_btn = QtWidgets.QPushButton("Supprimer")
        self.delete_element_btn.setFixedSize(70, 25)
        self.delete_element_btn.clicked.connect(self._delete_element)
        self.delete_element_btn.setEnabled(False)
        actions_layout.addWidget(self.delete_element_btn)

        actions_layout.addStretch()

        # Indicateur du niveau actuel dans la hiérarchie
        self.level_indicator = QtWidgets.QLabel("")
        self.level_indicator.setStyleSheet("font-size: 11px; color: #6c757d;")
        actions_layout.addWidget(self.level_indicator)

        layout.addLayout(actions_layout)

        parent_layout.addWidget(structure_frame, 2)

    def _create_strategy_panel(self, parent_layout):
        """Crée le panneau de visualisation des batches avec camembert"""
        strategy_frame = QtWidgets.QFrame()
        strategy_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        strategy_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #bdc3c7;
            }
        """)

        layout = QtWidgets.QVBoxLayout(strategy_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Titre
        title = QtWidgets.QLabel("Représentativité des Batches")
        title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Sous-titre explicatif
        subtitle = QtWidgets.QLabel("Nombre d'exemples par batch selon l'élément sélectionné")
        subtitle.setStyleSheet("font-size: 10px; color: #6c757d; margin-bottom: 10px;")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Canvas matplotlib pour le camembert
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(200)
        layout.addWidget(self.canvas)

        # Informations sur les batches
        self.batch_info = QtWidgets.QTextEdit()
        self.batch_info.setReadOnly(True)
        self.batch_info.setMaximumHeight(120)
        self.batch_info.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px;
            font-size: 10px;
        """)
        layout.addWidget(self.batch_info)

        # Boutons d'action pour la stratégie
        strategy_buttons = QtWidgets.QHBoxLayout()

        self.generate_batches_btn = QtWidgets.QPushButton("Générer Batches")
        self.generate_batches_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.generate_batches_btn.clicked.connect(self._generate_intelligent_batches)
        strategy_buttons.addWidget(self.generate_batches_btn)

        self.configure_batches_btn = QtWidgets.QPushButton("Configurer")
        self.configure_batches_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.configure_batches_btn.clicked.connect(self._configure_batch_strategy)
        strategy_buttons.addWidget(self.configure_batches_btn)

        layout.addLayout(strategy_buttons)

        # Initialiser le graphique vide
        self._update_batch_pie_chart()

        parent_layout.addWidget(strategy_frame, 1)

    def _create_action_buttons(self, parent_layout):
        """Crée les boutons d'action principaux"""
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()

        self.save_btn = QtWidgets.QPushButton("Sauvegarder")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SECONDARY_COLOR};
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #27ae60;
            }}
        """)
        self.save_btn.clicked.connect(self._save_strategy)
        self.save_btn.setEnabled(False)
        buttons_layout.addWidget(self.save_btn)

        self.export_btn = QtWidgets.QPushButton("Exporter")
        self.export_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_btn.clicked.connect(self._export_configuration)
        self.export_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_btn)

        buttons_layout.addStretch()
        parent_layout.addLayout(buttons_layout)

    # ===== MÉTHODES DE NAVIGATION HIÉRARCHIQUE =====

    def _reset_selection(self):
        """Remet la sélection à la racine (typologies)"""
        self.selected_typologie = None
        self.selected_cluster = None
        self.selected_root = None
        self.selected_parent = None
        self._refresh_structure_view()

    def _on_item_clicked(self, item, column):
        """Gestion du clic simple (sélection)"""
        self.edit_element_btn.setEnabled(True)
        self.delete_element_btn.setEnabled(True)
        item_data = item.data(0, Qt.UserRole)
        if item_data:
            item_type = item_data.get('type')
            item_obj = item_data.get('object')
            if item_type == 'typologie':
                self.selected_typologie = item_obj
                self.selected_cluster = None
                self.selected_root = None
                self.selected_parent = None
            elif item_type == 'root_label':
                self._find_and_set_parents_for_root(item_obj)
                self.selected_root = item_obj
                self.selected_parent = None
            elif item_type == 'parent_label':
                self._find_and_set_parents_for_parent(item_obj)
                self.selected_parent = item_obj
            elif item_type == 'child_label':
                self._find_and_set_parents_for_child(item_obj)
            self._update_breadcrumb()
            self._update_level_indicator()
            self._update_batch_view_based_on_selection(item)

    def _on_item_double_clicked(self, item, column):
        """Gestion du double-clic pour expander/collapser"""
        if item.isExpanded():
            item.setExpanded(False)
        else:
            item.setExpanded(True)

    def _find_and_set_parents_for_root(self, root_obj):
        """Trouve et définit tous les parents d'un root_label"""
        for typologie in self.project_data.get('typologies', []):
            if root_obj in typologie.get('root_labels', []):
                self.selected_typologie = typologie
                self.selected_cluster = None
                return

    def _find_and_set_parents_for_parent(self, parent_obj):
        """Trouve et définit tous les parents d'un parent_label"""
        for typologie in self.project_data.get('typologies', []):
            for root in typologie.get('root_labels', []):
                if parent_obj in root.get('parent_labels', []):
                    self.selected_typologie = typologie
                    self.selected_cluster = None
                    self.selected_root = root
                    return

    def _find_and_set_parents_for_child(self, child_obj):
        """Trouve et définit tous les parents d'un child_label"""
        for typologie in self.project_data.get('typologies', []):
            for root in typologie.get('root_labels', []):
                for parent in root.get('parent_labels', []):
                    if child_obj in parent.get('child_labels', []):
                        self.selected_typologie = typologie
                        self.selected_cluster = None
                        self.selected_root = root
                        self.selected_parent = parent
                        return

    def _refresh_structure_view(self):
        """Met à jour la vue de structure"""
        self.structure_tree.clear()
        self._show_full_hierarchy()
        self._update_breadcrumb()
        self._update_level_indicator()
        self._update_project_info()

    def _show_full_hierarchy(self):
        """Affiche l'ensemble de la hiérarchie comme une arborescence expansible"""
        typologies = self.project_data.get('typologies', [])
        for typologie in typologies:
            typologie_item = self._create_tree_item(typologie, 'typologie', None)
            self.structure_tree.addTopLevelItem(typologie_item)
            self._add_root_labels_to_tree(typologie, typologie_item)
            typologie_item.setExpanded(True)

    def _add_root_labels_to_tree(self, typologie, parent_item):
        """Ajoute les root_labels à l'arborescence"""
        root_labels = typologie.get('root_labels', [])
        for root in root_labels:
            root_item = self._create_tree_item(root, 'root_label', parent_item)
            self._add_parent_labels_to_tree(root, root_item)
            root_item.setExpanded(True)

    def _add_parent_labels_to_tree(self, root, parent_item):
        """Ajoute les parent_labels à l'arborescence"""
        parent_labels = root.get('parent_labels', [])
        for parent in parent_labels:
            parent_item_child = self._create_tree_item(parent, 'parent_label', parent_item)
            self._add_child_labels_to_tree(parent, parent_item_child)
            parent_item_child.setExpanded(True)

    def _add_child_labels_to_tree(self, parent, parent_item):
        """Ajoute les child_labels à l'arborescence"""
        child_labels = parent.get('child_labels', [])
        for child in child_labels:
            self._create_tree_item(child, 'child_label', parent_item)

    def _create_tree_item(self, obj, obj_type, parent_item):
        """Crée un item pour l'arborescence"""
        name = obj.get('name', 'Sans nom')
        category = obj.get('category', 'default')
        description = obj.get('description', '')

        # Construire le texte de l'item
        text = f"{name}"
        if category and category != 'default':
            text += f" [{category}]"
        if description:
            text += f" - {description[:30]}..." if len(description) > 30 else f" - {description}"

        # Ajouter les informations de comptage
        count_info = self._get_count_info(obj, obj_type)
        if count_info:
            text += f" {count_info}"

        item = QtWidgets.QTreeWidgetItem(parent_item, [text])
        item.setData(0, Qt.UserRole, {'type': obj_type, 'object': obj})

        # Tooltip détaillé
        tooltip = f"Type: {obj_type.capitalize()}\nNom: {name}\nCatégorie: {category}\nDescription: {description}"
        if obj_type == 'typologie':
            root_labels = obj.get('root_labels', [])
            if root_labels:
                tooltip += f"\nLabels Racines: {', '.join([r.get('name', 'Root') for r in root_labels])}"
        elif obj_type == 'root_label':
            parent_labels = obj.get('parent_labels', [])
            if parent_labels:
                tooltip += f"\nLabels Parents: {', '.join([p.get('name', 'Parent') for p in parent_labels])}"
        elif obj_type == 'parent_label':
            child_labels = obj.get('child_labels', [])
            if child_labels:
                tooltip += f"\nLabels Enfants: {', '.join([c.get('name', 'Enfant') for c in child_labels])}"

        item.setToolTip(0, tooltip)

        return item

    def _get_count_info(self, obj, obj_type):
        """Retourne les informations de comptage pour un objet"""
        if obj_type == 'typologie':
            root_labels = obj.get('root_labels', [])
            return f"({len(root_labels)} labels racines)" if root_labels else "(vide)"
        elif obj_type == 'root_label':
            parent_count = len(obj.get('parent_labels', []))
            return f"({parent_count} labels parents)" if parent_count > 0 else "(vide)"
        elif obj_type == 'parent_label':
            child_count = len(obj.get('child_labels', []))
            return f"({child_count} labels enfants)" if child_count > 0 else "(vide)"
        elif obj_type == 'child_label':
            return ""
        return ""

    def _get_selection_prefix(self):
        """Retourne le préfixe du chemin basé sur la sélection actuelle"""
        prefix_parts = []

        if self.selected_typologie:
            prefix_parts.append(self.selected_typologie.get('name', ''))

        if self.selected_root:
            prefix_parts.append(self.selected_root.get('name', ''))

        if self.selected_parent:
            prefix_parts.append(self.selected_parent.get('name', ''))

        return '/'.join(prefix_parts) + '/' if prefix_parts else ''

    def _get_filtered_batches(self, item_type, item_obj):
        """Filtre les batches correspondant exactement à l'élément sélectionné"""
        filtered = {}

        if not item_obj:
            # Sans sélection, afficher tous les batches sauf child_labels
            for batch_name, data in self.batch_data.items():
                if len(batch_name.split('/')) <= 3:  # Jusqu'à parent_labels
                    filtered[batch_name] = data
            return filtered

        name = item_obj.get('name', '')

        if item_type == 'typologie':
            # Batches de la typologie (root_labels et parent_labels)
            for batch_name, data in self.batch_data.items():
                if data['typologie_combination'] == name and len(batch_name.split('/')) <= 3:
                    filtered[batch_name] = data
        elif item_type == 'root_label':
            # Batches du root_label et de ses parent_labels
            prefix = f"{self.selected_typologie.get('name', '')}/{name}"
            for batch_name, data in self.batch_data.items():
                if batch_name == prefix or (batch_name.startswith(prefix + '/') and len(batch_name.split('/')) == 3):
                    filtered[batch_name] = data
        elif item_type == 'parent_label':
            # Batch exact du parent_label
            prefix = f"{self.selected_typologie.get('name', '')}/{self.selected_root.get('name', '')}/{name}"
            if prefix in self.batch_data:
                filtered[prefix] = self.batch_data[prefix]
        elif item_type == 'child_label':
            # Pas de batches pour les child_labels
            return {}

        return filtered

    def _update_breadcrumb(self):
        """Met à jour le fil d'Ariane"""
        breadcrumb_parts = ["Racine"]

        if self.selected_typologie:
            breadcrumb_parts.append(self.selected_typologie.get('name', 'Typologie'))

        if self.selected_root:
            breadcrumb_parts.append(self.selected_root.get('name', 'Root'))

        if self.selected_parent:
            breadcrumb_parts.append(self.selected_parent.get('name', 'Parent'))

        self.breadcrumb.setText(" > ".join(breadcrumb_parts))

    def _update_level_indicator(self):
        """Met à jour l'indicateur de niveau"""
        if self.selected_parent:
            self.level_indicator.setText("Niveau: Labels Parents")
        elif self.selected_root:
            self.level_indicator.setText("Niveau: Labels Racines")
        elif self.selected_typologie:
            self.level_indicator.setText("Niveau: Typologies")
        else:
            self.level_indicator.setText("Niveau: Racine")

    # ===== MÉTHODES DE GESTION DES ÉLÉMENTS =====

    def _add_element(self):
        """Ajoute un élément selon le contexte actuel"""
        if not self.selected_typologie:
            self._add_typologie()
        elif not self.selected_root:
            self._add_root_label()
        elif not self.selected_parent:
            self._add_parent_label()
        else:
            self._add_child_label()

    def _add_typologie(self):
        """Ajoute une nouvelle typologie de contexte"""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouvelle Typologie", "Nom de la typologie de contexte :"
        )

        if ok and name.strip():
            name = name.strip()

            # Vérifier l'unicité
            existing_names = [t.get('name') for t in self.project_data.get('typologies', [])]
            if name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self, "Nom Existant", f"Une typologie '{name}' existe déjà."
                )
                return

            # Demander si c'est une typologie taxonomique (avec hiérarchie)
            reply = QtWidgets.QMessageBox.question(
                self, "Type de Typologie",
                f"La typologie '{name}' est-elle de nature taxonomique (hiérarchique) ?\n\n"
                "Oui = Avec labels racine, parent, enfant\n"
                "Non = Structure simple sans hiérarchie",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            new_typologie = {
                'name': name,
                'description': '',
                'is_taxonomic': reply == QtWidgets.QMessageBox.Yes
            }

            if new_typologie['is_taxonomic']:
                new_typologie['root_labels'] = []
            else:
                new_typologie['simple_labels'] = []

            self.project_data.setdefault('typologies', []).append(new_typologie)
            self._refresh_structure_view()
            logger.info(f"Typologie ajoutée : {name} (taxonomique: {new_typologie['is_taxonomic']})")

    def _add_root_label(self):
        """Ajoute un nouveau label racine"""
        if not self.selected_typologie:
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Label Racine", "Nom du label racine :"
        )

        if ok and name.strip():
            name = name.strip()

            root_labels = self.selected_typologie.get('root_labels', [])
            existing_names = [r.get('name') for r in root_labels]
            if name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self, "Nom Existant", f"Un label racine '{name}' existe déjà."
                )
                return

            new_root = {
                'name': name,
                'description': '',
                'category': 'default',
                'parent_labels': []
            }

            self.selected_typologie.setdefault('root_labels', []).append(new_root)
            self._refresh_structure_view()
            logger.info(f"Label racine ajouté : {name}")

    def _add_parent_label(self):
        """Ajoute un nouveau label parent"""
        if not self.selected_root:
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Label Parent", "Nom du label parent :"
        )

        if ok and name.strip():
            name = name.strip()

            parent_labels = self.selected_root.get('parent_labels', [])
            existing_names = [p.get('name') for p in parent_labels]
            if name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self, "Nom Existant", f"Un label parent '{name}' existe déjà."
                )
                return

            new_parent = {
                'name': name,
                'description': '',
                'category': 'default',
                'child_labels': []
            }

            self.selected_root.setdefault('parent_labels', []).append(new_parent)
            self._refresh_structure_view()
            logger.info(f"Label parent ajouté : {name}")

    def _add_child_label(self):
        """Ajoute un nouveau label enfant"""
        if not self.selected_parent:
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Label Enfant", "Nom du label enfant :"
        )

        if ok and name.strip():
            name = name.strip()

            child_labels = self.selected_parent.get('child_labels', [])
            existing_names = [c.get('name') for c in child_labels]
            if name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self, "Nom Existant", f"Un label enfant '{name}' existe déjà."
                )
                return

            new_child = {
                'name': name,
                'description': '',
                'category': 'default'
            }

            self.selected_parent.setdefault('child_labels', []).append(new_child)
            self._refresh_structure_view()
            logger.info(f"Label enfant ajouté : {name}")

    def _edit_element(self):
        """Modifie l'élément sélectionné"""
        current_item = self.structure_tree.currentItem()
        if not current_item:
            return

        item_data = current_item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_obj = item_data.get('object')

        if not item_obj:
            return

        old_name = item_obj.get('name', '')
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier", "Nouveau nom :", text=old_name
        )

        if ok and new_name.strip() and new_name.strip() != old_name:
            item_obj['name'] = new_name.strip()
            self._refresh_structure_view()
            logger.info(f"Élément modifié : {old_name} -> {new_name}")

    def _delete_element(self):
        """Supprime l'élément sélectionné"""
        current_item = self.structure_tree.currentItem()
        if not current_item:
            return

        item_data = current_item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_obj = item_data.get('object')

        if not item_obj:
            return

        name = item_obj.get('name', 'Élément')
        reply = QtWidgets.QMessageBox.question(
            self, "Confirmer Suppression",
            f"Supprimer '{name}' et tous ses éléments enfants ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self._remove_element_from_data(item_type, item_obj)
            self._refresh_structure_view()
            logger.info(f"Élément supprimé : {name}")

    def _remove_element_from_data(self, item_type, item_obj):
        """Supprime un élément de la structure de données"""
        if item_type == 'typologie':
            typologies = self.project_data.get('typologies', [])
            self.project_data['typologies'] = [t for t in typologies if t != item_obj]
            self._reset_selection()
        elif item_type == 'root_label':
            if self.selected_typologie:
                root_labels = self.selected_typologie.get('root_labels', [])
                self.selected_typologie['root_labels'] = [r for r in root_labels if r != item_obj]
        elif item_type == 'parent_label' and self.selected_root:
            parent_labels = self.selected_root.get('parent_labels', [])
            self.selected_root['parent_labels'] = [p for p in parent_labels if p != item_obj]
        elif item_type == 'child_label' and self.selected_parent:
            child_labels = self.selected_parent.get('child_labels', [])
            self.selected_parent['child_labels'] = [c for c in child_labels if c != item_obj]

    # ===== MÉTHODES DE GESTION DES PROJETS =====

    def showEvent(self, event):
        """Appelé lorsque le widget devient visible"""
        logger.debug("showEvent déclenché, rechargement des projets")
        self._load_existing_projects()
        super().showEvent(event)

    def _load_existing_projects(self):
        """Charge les projets existants depuis la base de données"""
        if not self.db_connection:
            logger.error("Aucune connexion à la base de données disponible")
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM projects ORDER BY name")
            projects = cursor.fetchall()

            current_project = self.project_combo.currentText()
            self.project_combo.clear()

            for project in projects:
                self.project_combo.addItem(project['name'])

            if current_project:
                index = self.project_combo.findText(current_project)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                else:
                    self._clear_project_interface()

            logger.info(f"Chargé {len(projects)} projets existants")

        except Exception as e:
            logger.error(f"Erreur chargement projets : {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Erreur", f"Impossible de charger les projets : {str(e)}"
            )

    def _create_new_project(self):
        """Crée un nouveau projet"""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Projet", "Nom du projet de dataset :"
        )

        if ok and name.strip():
            name = name.strip()

            if self._project_exists(name):
                QtWidgets.QMessageBox.warning(
                    self, "Projet Existant", f"Un projet '{name}' existe déjà."
                )
                return

            self.project_data = {
                "nom": name,
                "description": "",
                "typologies": []
            }

            self.project_combo.addItem(name)
            self.project_combo.setCurrentText(name)
            self.project_name_edit.setText(name)
            self.project_desc_edit.clear()

            self._reset_selection()
            self._enable_project_controls(True)
            self._update_project_info()

            logger.info(f"Nouveau projet créé : {name}")

    def _delete_current_project(self):
        """Supprime le projet actuel"""
        current_project = self.project_combo.currentText()
        if not current_project:
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Confirmer Suppression",
            f"Supprimer le projet '{current_project}' ?\n"
            "Toutes les typologies et batches associés seront perdus.\n"
            "Cette action est irréversible.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("DELETE FROM projects WHERE name = ?", (current_project,))
                cursor.execute("DELETE FROM dataset_batches WHERE project_name = ?", (current_project,))
                self.db_connection.commit()

                index = self.project_combo.findText(current_project)
                if index >= 0:
                    self.project_combo.removeItem(index)

                self._clear_project_interface()
                logger.info(f"Projet supprimé : {current_project}")

            except Exception as e:
                logger.error(f"Erreur suppression projet : {str(e)}")
                QtWidgets.QMessageBox.critical(
                    self, "Erreur", f"Erreur lors de la suppression : {str(e)}"
                )

    def _on_project_selected(self, project_name):
        """Gestion de la sélection d'un projet"""
        if not project_name:
            self._clear_project_interface()
            return

        self._load_project_data(project_name)

    def _load_project_data(self, project_name):
        """Charge les données d'un projet depuis la base de données"""
        try:
            if not self.db_connection:
                return

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            row = cursor.fetchone()

            if row:
                self.project_name_edit.setText(row['name'])
                self.project_desc_edit.setPlainText(row['description'] or '')

                if row['data']:
                    try:
                        self.project_data = json.loads(row['data'])
                    except json.JSONDecodeError:
                        self.project_data = {"nom": project_name, "description": "", "typologies": []}
                else:
                    self.project_data = {"nom": project_name, "description": "", "typologies": []}

                self._reset_selection()
                self._load_batch_data(project_name)
                self._enable_project_controls(True)
                self._update_project_info()

                logger.info(f"Projet chargé : {project_name}")

        except Exception as e:
            logger.error(f"Erreur chargement projet : {str(e)}")

    def _update_project_info(self):
        """Met à jour les informations du projet"""
        if not self.project_data:
            self.project_info.setText("Aucun projet sélectionné")
            return

        typologies_count = len(self.project_data.get('typologies', []))
        total_elements = sum(self._count_typologie_elements(t)
                             for t in self.project_data.get('typologies', []))

        batches_count = len(self.batch_data)

        info_text = f"""Statistiques:
• {typologies_count} typologie(s) de contexte
• {total_elements} élément(s) total
• {batches_count} batch(es) configuré(s)

État: {'Prêt pour génération' if batches_count > 0 else 'Configuration nécessaire'}
        """.strip()

        self.project_info.setText(info_text)

    def _count_typologie_elements(self, typologie):
        """Compte le nombre total d'éléments dans une typologie"""
        if not typologie.get('is_taxonomic', True):
            return len(typologie.get('simple_labels', []))

        total = 0
        root_labels = typologie.get('root_labels', [])
        for root in root_labels:
            total += self._count_root_elements(root)

        return total

    def _count_root_elements(self, root):
        """Compte les éléments dans un label racine"""
        total = 1  # Le root lui-même
        parent_labels = root.get('parent_labels', [])
        for parent in parent_labels:
            total += 1  # Le parent
            total += len(parent.get('child_labels', []))  # Les enfants
        return total

    # ===== MÉTHODES DE GÉNÉRATION DE BATCHES =====

    def _generate_intelligent_batches(self):
        """Génère des batches intelligents basés sur les combinaisons de typologies"""
        current_project = self.project_combo.currentText()
        if not current_project:
            QtWidgets.QMessageBox.warning(
                self, "Aucun Projet", "Veuillez sélectionner un projet."
            )
            return

        typologies = self.project_data.get('typologies', [])
        if not typologies:
            QtWidgets.QMessageBox.warning(
                self, "Aucune Typologie",
                "Veuillez d'abord créer des typologies de contextes."
            )
            return

        batches = self._generate_typologie_combinations()

        if not batches:
            QtWidgets.QMessageBox.warning(
                self, "Aucun Batch",
                "Impossible de générer des batches avec les typologies actuelles."
            )
            return

        self._apply_intelligent_batch_distribution(batches)
        self._save_batch_data(current_project)
        self._update_batch_pie_chart()
        self._update_batch_info()

        QtWidgets.QMessageBox.information(
            self, "Batches Générés",
            f"Stratégie de batches générée avec {len(batches)} combinaisons.\n\n"
            f"Chaque batch correspond à une combinaison spécifique de typologies de contextes."
        )

    def _generate_typologie_combinations(self):
        """Génère les combinaisons possibles entre typologies, jusqu'à parent_labels"""
        batches = []

        for typologie in self.project_data.get('typologies', []):
            typologie_name = typologie.get('name', 'Typologie')

            if typologie.get('is_taxonomic', True):
                batch_combos = self._generate_taxonomic_combinations(typologie)
                for combo in batch_combos:
                    batches.append({
                        'name': f"{typologie_name}/{combo['path']}",
                        'typologie_combination': typologie_name,
                        'context_path': combo['path'],
                        'count': 0,
                        'weight': combo.get('weight', 1.0)
                    })
            else:
                simple_labels = typologie.get('simple_labels', [])
                for label in simple_labels:
                    batches.append({
                        'name': f"{typologie_name}/{label.get('name', 'Label')}",
                        'typologie_combination': typologie_name,
                        'context_path': label.get('name', 'Label'),
                        'count': 0,
                        'weight': 1.0
                    })

        return batches

    def _generate_taxonomic_combinations(self, typologie):
        """Génère les combinaisons pour une typologie taxonomique, jusqu'à parent_labels"""
        combinations = []
        root_labels = typologie.get('root_labels', [])
        for root in root_labels:
            root_combos = self._generate_root_combinations(root, root.get('name', 'Root'))
            combinations.extend(root_combos)

        return combinations

    def _generate_root_combinations(self, root, prefix):
        """Génère les combinaisons pour un root label, jusqu'à parent_labels"""
        combinations = []
        parent_labels = root.get('parent_labels', [])

        # Ajouter le root_label lui-même comme un batch
        combinations.append({
            'path': prefix,
            'weight': 1.0
        })

        # Ajouter chaque parent_label
        for parent in parent_labels:
            parent_name = parent.get('name', 'Parent')
            combinations.append({
                'path': f"{prefix}/{parent_name}",
                'weight': 1.0
            })

        return combinations

    def _apply_intelligent_batch_distribution(self, batches, total_samples=1000):
        """Applique une distribution intelligente aux batches"""
        if not batches:
            return

        min_samples_per_batch = max(100, total_samples // (len(batches) * 3))
        remaining_samples = total_samples - (len(batches) * min_samples_per_batch)

        total_weight = sum(batch['weight'] for batch in batches)

        self.batch_data = {}

        for batch in batches:
            base_count = min_samples_per_batch
            extra_count = int((batch['weight'] / total_weight) * remaining_samples)
            total_count = base_count + extra_count

            self.batch_data[batch['name']] = {
                'count': total_count,
                'percentage': (total_count / total_samples) * 100,
                'typologie_combination': batch['typologie_combination'],
                'context_path': batch['context_path']
            }

    def _configure_batch_strategy(self):
        """Ouvre la configuration avancée des batches"""
        if not self.batch_data:
            QtWidgets.QMessageBox.information(
                self, "Aucun Batch",
                "Veuillez d'abord générer des batches avant de les configurer."
            )
            return

        dialog = BatchConfigDialog(self.batch_data, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.batch_data = dialog.get_configuration()
            self._update_batch_pie_chart()
            self._update_batch_info()

    # ===== MÉTHODES DE VISUALISATION =====

    def _update_batch_pie_chart(self, filtered_data=None):
        """Met à jour le camembert de représentativité des batches"""
        data = filtered_data if filtered_data is not None else self.batch_data

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not data:
            ax.text(0.5, 0.5,
                    'Aucun batch défini pour cette sélection\n\nGénérez des batches ou sélectionnez une autre hiérarchie',
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, fontsize=11, color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
        else:
            labels = list(data.keys())
            sizes = [data[label]['count'] for label in labels]

            if len(labels) > 12:
                sorted_data = sorted(data.items(),
                                     key=lambda x: x[1]['count'], reverse=True)
                top_11 = sorted_data[:11]
                others_count = sum(item[1]['count'] for item in sorted_data[11:])

                labels = [item[0] for item in top_11] + ['Autres']
                sizes = [item[1]['count'] for item in top_11] + [others_count]

            colors = plt.cm.Set3(range(len(labels)))

            short_labels = []
            for label in labels:
                if label == 'Autres':
                    short_labels.append('Autres')
                else:
                    parts = label.split('/')
                    short_labels.append(parts[-1])

            wedges, texts, autotexts = ax.pie(
                sizes, labels=short_labels, colors=colors, autopct='%1.1f%%',
                startangle=90, textprops={'fontsize': 8}
            )

            ax.set_title('Distribution des Batches pour l\'Élément Sélectionné',
                         fontsize=11, fontweight='bold', pad=10)

        self.canvas.draw()

    def _update_batch_info(self, filtered_data=None):
        """Met à jour les informations textuelles des batches"""
        data = filtered_data if filtered_data is not None else self.batch_data

        if not data:
            self.batch_info.setPlainText(
                "Aucun batch défini pour cette sélection.\n\nUn batch correspond à une combinaison spécifique de typologies de contextes.")
            return

        info_lines = []
        total_samples = sum(d['count'] for d in data.values())

        sorted_batches = sorted(data.items(),
                               key=lambda x: x[1]['count'], reverse=True)

        info_lines.append("BATCHES POUR L'ÉLÉMENT SÉLECTIONNÉ:")
        info_lines.append("-" * 40)

        by_typologie = {}
        for batch_name, d in sorted_batches:
            typ = d.get('typologie_combination', 'Inconnu')
            if typ not in by_typologie:
                by_typologie[typ] = []
            by_typologie[typ].append((batch_name, d))

        for typ_name, batches in by_typologie.items():
            info_lines.append(f"\n{typ_name}:")
            for batch_name, d in batches[:3]:
                context = d.get('context_path', '').split('/')[-1]
                level = 'Racine' if len(batch_name.split('/')) == 2 else 'Parent'
                info_lines.append(f"  • {context} ({level}): {d['count']} ({d['percentage']:.1f}%)")
            if len(batches) > 3:
                info_lines.append(f"  ... et {len(batches) - 3} autres")

        info_lines.append(f"\nTOTAL: {total_samples} échantillons répartis sur {len(sorted_batches)} batches")

        self.batch_info.setPlainText('\n'.join(info_lines))

    def _update_batch_view_based_on_selection(self, item):
        """Met à jour le camembert et les infos basés sur la sélection"""
        logger.debug(f"Updating batch view for item: {item.text(0) if item else 'None'}")
        if not item:
            self._update_batch_pie_chart()
            self._update_batch_info()
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            logger.warning("No item data found")
            return

        item_type = item_data.get('type')
        item_obj = item_data.get('object')
        logger.debug(f"Item type: {item_type}, Object: {item_obj.get('name', 'Unknown')}")

        filtered_data = self._get_filtered_batches(item_type, item_obj)
        logger.debug(f"Filtered batches: {len(filtered_data)} found")

        self._update_batch_pie_chart(filtered_data)
        self._update_batch_info(filtered_data)

    # ===== MÉTHODES UTILITAIRES =====

    def _clear_project_interface(self):
        """Efface complètement l'interface du projet"""
        self.project_name_edit.clear()
        self.project_desc_edit.clear()
        self._reset_selection()
        self._enable_project_controls(False)
        self.batch_data = {}
        self._update_batch_pie_chart()
        self.batch_info.clear()
        self.project_info.setText("Aucun projet sélectionné")

    def _enable_project_controls(self, enabled):
        """Active ou désactive les contrôles du projet"""
        self.delete_project_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.export_btn.setEnabled(enabled)
        self.generate_batches_btn.setEnabled(enabled)
        self.configure_batches_btn.setEnabled(enabled)

    def _project_exists(self, project_name):
        """Vérifie si un projet existe déjà"""
        try:
            if not self.db_connection:
                return False

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM projects WHERE name = ?", (project_name,))
            return cursor.fetchone()[0] > 0

        except Exception as e:
            logger.error(f"Erreur vérification existence projet : {str(e)}")
            return False

    def _load_batch_data(self, project_name):
        """Charge les données de batches depuis la base de données"""
        try:
            if not self.db_connection:
                return

            cursor = self.db_connection.cursor()
            cursor.execute("""
                           SELECT batch_name, sample_count, percentage, typologie_combination
                           FROM dataset_batches
                           WHERE project_name = ?
                           """, (project_name,))

            rows = cursor.fetchall()
            self.batch_data = {}

            for row in rows:
                self.batch_data[row['batch_name']] = {
                    'count': row['sample_count'],
                    'percentage': row['percentage'],
                    'typologie_combination': row['typologie_combination'] or 'Inconnu',
                    'context_path': row['batch_name'].split('/', 1)[1] if '/' in row['batch_name'] else row['batch_name']
                }

            if self.batch_data:
                self._update_batch_pie_chart()
                self._update_batch_info()

        except Exception as e:
            logger.error(f"Erreur chargement batches : {str(e)}")

    def _save_batch_data(self, project_name):
        """Sauvegarde les données de batches dans la base de données"""
        try:
            if not self.db_connection:
                return

            cursor = self.db_connection.cursor()
            cursor.execute("DELETE FROM dataset_batches WHERE project_name = ?", (project_name,))

            for batch_name, data in self.batch_data.items():
                cursor.execute("""
                               INSERT INTO dataset_batches (project_name, batch_name, sample_count, percentage,
                                                            typologie_combination)
                               VALUES (?, ?, ?, ?, ?)
                               """, (project_name, batch_name, data['count'], data['percentage'],
                                     data['typologie_combination']))

            self.db_connection.commit()

        except Exception as e:
            logger.error(f"Erreur sauvegarde batches : {str(e)}")

    # ===== MÉTHODES DE SAUVEGARDE ET EXPORT =====

    def _save_strategy(self):
        """Sauvegarde la stratégie actuelle"""
        current_project = self.project_combo.currentText()
        if not current_project:
            QtWidgets.QMessageBox.warning(
                self, "Aucun Projet", "Veuillez sélectionner un projet."
            )
            return

        self.project_data['nom'] = self.project_name_edit.text().strip()
        self.project_data['description'] = self.project_desc_edit.toPlainText().strip()

        if not self.project_data['nom']:
            QtWidgets.QMessageBox.warning(
                self, "Nom Manquant", "Veuillez saisir un nom pour le projet."
            )
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM projects WHERE name = ?", (current_project,))
            existing = cursor.fetchone()

            json_data = json.dumps(self.project_data, ensure_ascii=False, indent=2)

            if existing:
                cursor.execute("""
                               UPDATE projects
                               SET name = ?, description = ?, data = ?, updated_at = CURRENT_TIMESTAMP
                               WHERE name = ?
                               """, (self.project_data['nom'], self.project_data['description'], json_data, current_project))
            else:
                cursor.execute("""
                               INSERT INTO projects (name, description, data)
                               VALUES (?, ?, ?)
                               """, (self.project_data['nom'], self.project_data['description'], json_data))

            self.db_connection.commit()

            if self.project_data['nom'] != current_project:
                index = self.project_combo.findText(current_project)
                if index >= 0:
                    self.project_combo.setItemText(index, self.project_data['nom'])
                    self.project_combo.setCurrentText(self.project_data['nom'])

            if self.batch_data:
                self._save_batch_data(self.project_data['nom'])

            QtWidgets.QMessageBox.information(
                self, "Sauvegarde Réussie",
                f"Stratégie de dataset '{self.project_data['nom']}' sauvegardée."
            )

            logger.info(f"Stratégie sauvegardée : {self.project_data['nom']}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde stratégie : {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Erreur Sauvegarde", f"Erreur : {str(e)}"
            )

    def _export_configuration(self):
        """Exporte la configuration vers un fichier JSON"""
        current_project = self.project_combo.currentText()
        if not current_project:
            QtWidgets.QMessageBox.warning(
                self, "Aucun Projet", "Veuillez sélectionner un projet."
            )
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exporter Configuration de Dataset",
            f"{current_project}_dataset_strategy.json",
            "Fichiers JSON (*.json)"
        )

        if filename:
            try:
                export_data = {
                    'project_info': self.project_data,
                    'batches': self.batch_data,
                    'export_timestamp': QtCore.QDateTime.currentDateTime().toString(Qt.ISODate),
                    'export_type': 'dataset_strategy'
                }

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                QtWidgets.QMessageBox.information(
                    self, "Export Réussi", f"Configuration de dataset exportée vers :\n{filename}"
                )

                logger.info(f"Configuration exportée : {filename}")

            except Exception as e:
                logger.error(f"Erreur export : {str(e)}")
                QtWidgets.QMessageBox.critical(
                    self, "Erreur Export", f"Erreur : {str(e)}"
                )

    def get_project_data_for_generation(self):
        """Retourne les données du projet formatées pour l'onglet génération"""
        if not self.project_data or not self.batch_data:
            return None

        return {
            'project_name': self.project_data.get('nom', ''),
            'description': self.project_data.get('description', ''),
            'typologies': self.project_data.get('typologies', []),
            'batches': self.batch_data,
            'total_batches': len(self.batch_data),
            'total_samples': sum(data['count'] for data in self.batch_data.values())
        }

    def closeEvent(self, event):
        """Gestion de la fermeture du widget"""
        if self.db_connection:
            self.db_connection.close()
            logger.info("Connexion DB fermée")
        super().closeEvent(event)

class BatchConfigDialog(QtWidgets.QDialog):
    """Dialogue pour la configuration avancée des batches"""

    def __init__(self, batch_data, parent=None):
        super().__init__(parent)
        self.batch_data = batch_data.copy()
        self.setWindowTitle("Configuration Avancée des Batches")
        self.setModal(True)
        self.resize(700, 500)

        self._init_ui()
        self._populate_data()

    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Configuration des Batches de Dataset")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(title)

        explanation = QtWidgets.QLabel(
            "Ajustez le nombre d'exemples par batch. Chaque batch correspond à une combinaison "
            "spécifique de typologies de contextes qui sera utilisée pour la génération."
        )
        explanation.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 15px;")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Batch (Combinaison)", "Typologie", "Échantillons", "Pourcentage"
        ])

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.resizeSection(0, 250)
        header.resizeSection(1, 150)
        header.resizeSection(2, 100)
        header.resizeSection(3, 100)

        layout.addWidget(self.table)

        self.total_info = QtWidgets.QLabel()
        self.total_info.setStyleSheet("""
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 8px;
            font-weight: bold;
        """)
        layout.addWidget(self.total_info)

        buttons_layout = QtWidgets.QHBoxLayout()

        self.reset_btn = QtWidgets.QPushButton("Réinitialiser")
        self.reset_btn.clicked.connect(self._reset_values)
        buttons_layout.addWidget(self.reset_btn)

        self.equal_btn = QtWidgets.QPushButton("Répartition Égale")
        self.equal_btn.clicked.connect(self._equal_distribution)
        buttons_layout.addWidget(self.equal_btn)

        buttons_layout.addStretch()

        self.cancel_btn = QtWidgets.QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        self.apply_btn = QtWidgets.QPushButton("Appliquer")
        self.apply_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.apply_btn)

        layout.addLayout(buttons_layout)

    def _populate_data(self):
        """Remplit la table avec les données actuelles"""
        self.table.setRowCount(len(self.batch_data))

        for row, (batch_name, data) in enumerate(self.batch_data.items()):
            name_item = QtWidgets.QTableWidgetItem(batch_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setToolTip(batch_name)
            self.table.setItem(row, 0, name_item)

            typ_item = QtWidgets.QTableWidgetItem(data.get('typologie_combination', 'Inconnu'))
            typ_item.setFlags(typ_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, typ_item)

            count_item = QtWidgets.QTableWidgetItem(str(data['count']))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, count_item)

            percent_item = QtWidgets.QTableWidgetItem(f"{data['percentage']:.1f}%")
            percent_item.setFlags(percent_item.flags() & ~Qt.ItemIsEditable)
            percent_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, percent_item)

        self.table.itemChanged.connect(self._recalculate_percentages)
        self._update_total_info()

    def _recalculate_percentages(self):
        """Recalcule les pourcentages après modification"""
        total = 0

        for row in range(self.table.rowCount()):
            count_item = self.table.item(row, 2)
            if count_item:
                try:
                    count = int(count_item.text())
                    if count < 0:
                        count = 0
                        count_item.setText("0")
                    total += count
                except ValueError:
                    count_item.setText("0")

        for row in range(self.table.rowCount()):
            count_item = self.table.item(row, 2)
            percent_item = self.table.item(row, 3)

            if count_item and percent_item:
                try:
                    count = int(count_item.text())
                    percentage = (count / total * 100) if total > 0 else 0
                    percent_item.setText(f"{percentage:.1f}%")
                except ValueError:
                    percent_item.setText("0.0%")

        self._update_total_info()

    def _update_total_info(self):
        """Met à jour les informations totales"""
        total = 0
        for row in range(self.table.rowCount()):
            count_item = self.table.item(row, 2)
            if count_item:
                try:
                    total += int(count_item.text())
                except ValueError:
                    pass

        self.total_info.setText(f"Total: {total:,} échantillons répartis sur {self.table.rowCount()} batches")

    def _reset_values(self):
        """Remet les valeurs d'origine"""
        for row, (batch_name, original_data) in enumerate(self.batch_data.items()):
            count_item = self.table.item(row, 2)
            if count_item:
                count_item.setText(str(original_data['count']))

        self._recalculate_percentages()

    def _equal_distribution(self):
        """Répartit équitablement les échantillons"""
        total_samples = 10000

        total_text, ok = QtWidgets.QInputDialog.getText(
            self, "Répartition Égale",
            "Nombre total d'échantillons à répartir :",
            text=str(total_samples)
        )

        if ok and total_text.strip():
            try:
                total_samples = int(total_text.strip())
                if total_samples <= 0:
                    raise ValueError("Le nombre doit être positif")

                samples_per_batch = total_samples // self.table.rowCount()
                remainder = total_samples % self.table.rowCount()

                for row in range(self.table.rowCount()):
                    count_item = self.table.item(row, 2)
                    if count_item:
                        extra = 1 if row < remainder else 0
                        count_item.setText(str(samples_per_batch + extra))

                self._recalculate_percentages()

            except ValueError as e:
                QtWidgets.QMessageBox.warning(
                    self, "Valeur Invalide",
                    "Veuillez saisir un nombre entier positif."
                )

    def get_configuration(self):
        """Retourne la configuration modifiée"""
        updated_data = {}

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            typ_item = self.table.item(row, 1)
            count_item = self.table.item(row, 2)
            percent_item = self.table.item(row, 3)

            if name_item and typ_item and count_item and percent_item:
                batch_name = name_item.text()
                count = int(count_item.text())
                percentage = float(percent_item.text().replace('%', ''))

                original_data = self.batch_data.get(batch_name, {})
                updated_data[batch_name] = {
                    'count': count,
                    'percentage': percentage,
                    'typologie_combination': original_data.get('typologie_combination', 'Inconnu'),
                    'context_path': original_data.get('context_path', batch_name)
                }

        return updated_data