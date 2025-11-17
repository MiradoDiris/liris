import os
import sqlite3
import json
import logging
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from ui.styles.platform_config_style import PlatformConfigStyle
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class DatasetStrategyWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_data = {"nom": "", "description": "", "typologies": []}
        self.batch_data = {}
        self.selected_typologie = None
        self.selected_root = None
        self.selected_parent = None
        self.selected_item_data = None
        self.navigation_stack = []
        self.db_connection = None
        self._init_database()
        self._init_ui()
        self._load_existing_projects()

    def _init_database(self):
        try:
            db_path = os.path.join("data", "liris.db")
            os.makedirs("data", exist_ok=True)
            self.db_connection = sqlite3.connect(db_path)
            self.db_connection.row_factory = sqlite3.Row
            self._create_tables()
            logger.info("Base de données initialisée avec succès")
        except Exception as e:
            logger.error(f"Erreur initialisation DB : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur",
                                           f"Erreur lors de l'initialisation de la base de données : {str(e)}")
            self.db_connection = None

    def _create_tables(self):
        #try:
        #    cursor = self.db_connection.cursor()
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS projects (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       name TEXT UNIQUE NOT NULL,
        #                       description TEXT,
        #                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #                       updated_at TIMESTAMP DEFAULT
        #                       CURRENT_TIMESTAMP
        #                   )
        #    ''')
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS typologies (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       project_id INTEGER NOT NULL,
        #                       name TEXT NOT NULL,
        #                       description TEXT,
        #                       is_taxonomic BOOLEAN NOT NULL,
        #                       FOREIGN KEY (
        #                           project_id
        #                       )
        #                       REFERENCES projects (
        #                           id
        #                       )
        #                       ON DELETE CASCADE
        #                   )
        #    ''')
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS root_labels (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       typology_id INTEGER NOT NULL,
        #                       name TEXT NOT NULL,
        #                       description TEXT,
        #                       category TEXT DEFAULT 'default',
        #                       FOREIGN KEY (
        #                           typology_id
        #                       )
        #                       REFERENCES typologies (
        #                           id
        #                       )
        #                       ON DELETE CASCADE
        #                   )
        #    ''')
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS parent_labels (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       root_label_id INTEGER NOT NULL,
        #                       name TEXT NOT NULL,
        #                       description TEXT,
        #                       category TEXT DEFAULT 'default',
        #                       FOREIGN KEY (
        #                            root_label_id
        #                       )
        #                       REFERENCES root_labels (
        #                            id
        #                       )
        #                       ON DELETE CASCADE
        #                   )
        #    ''')
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS child_labels (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       parent_label_id INTEGER NOT NULL,
        #                       name TEXT NOT NULL,
        #                       description TEXT,
        #                       category TEXT DEFAULT
        #                       'default',
        #                       FOREIGN KEY (
        #                            parent_label_id
        #                       )
        #                       REFERENCES parent_labels (
        #                            id
        #                       )
        #                       ON DELETE CASCADE
        #                   )
        #    ''')
        #    cursor.execute('''
        #                   CREATE TABLE IF NOT EXISTS simple_labels (
        #                       id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                       typology_id INTEGER NOT NULL,
        #                       name TEXT NOT NULL,
        #                       description TEXT,
        #                       category TEXT DEFAULT 'default',
        #                       FOREIGN KEY (
        #                           typology_id
        #                       )
        #                       REFERENCES typologies (
        #                           id
        #                       )
        #                       ON DELETE CASCADE
        #                   )
        #    ''')
#
        #    # Vérifier et migrer dataset_batches
        #    cursor.execute("PRAGMA table_info(dataset_batches)")
        #    columns = [col[1] for col in cursor.fetchall()]
#
        #    # Migration si project_name existe
        #    if 'project_name' in columns or 'project_id' not in columns:
        #        logger.warning("Migration de dataset_batches : remplacement de project_name par project_id")
        #        cursor.execute('''
        #                       CREATE TABLE IF NOT EXISTS dataset_batches_new (
        #                           id INTEGER PRIMARY KEY AUTOINCREMENT,
        #                           project_id INTEGER NOT NULL,
        #                           batch_name TEXT NOT NULL,
        #                           sample_count INTEGER DEFAULT 0,
        #                           percentage REAL DEFAULT 0.0,
        #                           typologie_combination TEXT,
        #                           context_path TEXT,
        #                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #                           FOREIGN KEY (
        #                                project_id
        #                           )
        #                           REFERENCES projects (
        #                                id
        #                           )
        #                           ON DELETE CASCADE
        #                       )
        #        ''')
        #        if 'project_name' in columns:
        #            cursor.execute('''
        #                           INSERT INTO dataset_batches_new (id, project_id, batch_name, sample_count,
        #                                                            percentage,
        #                                                            typologie_combination, context_path, created_at)
        #                           SELECT db.id,
        #                                  p.id,
        #                                  db.batch_name,
        #                                  db.sample_count,
        #                                  db.percentage,
        #                                  db.typologie_combination,
        #                                  db.context_path,
        #                                  db.created_at
        #                           FROM dataset_batches db
        #                                    LEFT JOIN projects p ON db.project_name = p.name
        #                           WHERE p.id IS NOT NULL
        #                           ''')
        #            cursor.execute('DROP TABLE dataset_batches')
        #            cursor.execute('ALTER TABLE dataset_batches_new RENAME TO dataset_batches')
        #        logger.info("Migration dataset_batches terminée")
#
        #    # Ajouter context_path si manquant
        #    if 'context_path' not in columns:
        #        cursor.execute('ALTER TABLE dataset_batches ADD COLUMN context_path TEXT')
        #        cursor.execute('''
        #                       UPDATE dataset_batches
        #                       SET context_path = batch_name
        #                       WHERE context_path IS NULL
        #                       ''')
#
        #    self.db_connection.commit()
        #    logger.info("Tables créées/migrées avec succès")
        #except sqlite3.Error as e:
        #    logger.error(f"Erreur lors de la création/migration des tables : {str(e)}")
        #    QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création des tables : {str(e)}")
        pass

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setAlignment(Qt.AlignCenter)

        title_label = QtWidgets.QLabel("Stratégie de Dataset")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setAlignment(Qt.AlignCenter)
        self._create_project_panel(content_layout)
        self._create_structure_panel(content_layout)
        self._create_strategy_panel(content_layout)
        main_layout.addLayout(content_layout)

    def _create_project_panel(self, parent_layout):
        project_frame = QtWidgets.QFrame()
        project_frame.setFixedWidth(250)
        project_frame.setStyleSheet("background: #f9f9f9; border-radius: 8px;")
        layout = QtWidgets.QVBoxLayout(project_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Projets")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.setToolTip("Sélectionnez un projet existant")
        self.project_combo.currentTextChanged.connect(self._on_project_selected)
        layout.addWidget(self.project_combo)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText("Nom du projet...")
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setToolTip("Nom du projet")
        layout.addWidget(self.project_name_edit)

        self.project_desc_edit = QtWidgets.QTextEdit()
        self.project_desc_edit.setPlaceholderText("Description...")
        self.project_desc_edit.setMaximumHeight(80)
        self.project_desc_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_desc_edit.setToolTip("Description du projet")
        layout.addWidget(self.project_desc_edit)

        self.project_info = QtWidgets.QLabel("Aucun projet")
        self.project_info.setWordWrap(True)
        self.project_info.setStyleSheet(
            "font-size: 12px; color: #6c757d; background: #e9ecef; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.project_info)

        project_btn_layout = QtWidgets.QVBoxLayout()
        self.new_project_btn = QtWidgets.QPushButton("Nouveau Projet")
        self.new_project_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.new_project_btn.setToolTip("Créer un nouveau projet")
        self.new_project_btn.clicked.connect(self._create_new_project)
        project_btn_layout.addWidget(self.new_project_btn)

        self.save_project_btn = QtWidgets.QPushButton("Sauvegarder")
        self.save_project_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_project_btn.setToolTip("Sauvegarder toutes les modifications")
        self.save_project_btn.clicked.connect(self._save_all_changes)
        self.save_project_btn.setEnabled(False)
        project_btn_layout.addWidget(self.save_project_btn)

        self.delete_project_btn = QtWidgets.QPushButton("Supprimer")
        self.delete_project_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_btn.setToolTip("Supprimer le projet sélectionné")
        self.delete_project_btn.clicked.connect(self._delete_project)
        self.delete_project_btn.setEnabled(False)
        project_btn_layout.addWidget(self.delete_project_btn)

        layout.addLayout(project_btn_layout)
        layout.addStretch()
        parent_layout.addWidget(project_frame)

    def _on_project_selected(self, project_name):
        if project_name:
            self._load_project_data(project_name)
            self.save_project_btn.setEnabled(True)
            self.delete_project_btn.setEnabled(True)
        else:
            self._clear_project_interface()
            self.save_project_btn.setEnabled(False)
            self.delete_project_btn.setEnabled(False)

    def _create_structure_panel(self, parent_layout):
        structure_frame = QtWidgets.QFrame()
        structure_frame.setStyleSheet("background: #f9f9f9; border-radius: 8px;")
        layout = QtWidgets.QVBoxLayout(structure_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        self.back_btn = QtWidgets.QPushButton("← Retour")
        self.back_btn.setFixedSize(80, 28)
        self.back_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.back_btn.setToolTip("Retour au niveau précédent")
        self.back_btn.clicked.connect(self._navigate_back)
        self.back_btn.setEnabled(False)
        header_layout.addWidget(self.back_btn)

        self.reset_selection_btn = QtWidgets.QPushButton("Racine")
        self.reset_selection_btn.setFixedSize(60, 28)
        self.reset_selection_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.reset_selection_btn.setToolTip("Retour à la racine")
        self.reset_selection_btn.clicked.connect(self._reset_selection)
        header_layout.addWidget(self.reset_selection_btn)

        header_layout.addStretch()
        self.structure_title = QtWidgets.QLabel("Taxonomie")
        self.structure_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        header_layout.addWidget(self.structure_title)
        layout.addLayout(header_layout)

        self.breadcrumb = QtWidgets.QLabel("Racine")
        self.breadcrumb.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #2c3e50; 
            background-color: #e6f3ff; 
            padding: 5px; 
            border-radius: 4px; 
            cursor: pointer;
        """)
        self.breadcrumb.setToolTip("Fil d'Ariane - Cliquez pour naviguer")
        self.breadcrumb.mousePressEvent = self._breadcrumb_clicked
        layout.addWidget(self.breadcrumb)

        self.structure_list = QtWidgets.QListWidget()
        self.structure_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc; 
                border-radius: 4px; 
                background: white;
            }
            QListWidget::item:selected {
                background-color: #e6f3ff; 
                color: #2c3e50;
            }
        """)
        self.structure_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.structure_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.structure_list.itemClicked.connect(self._on_item_clicked)
        self.structure_list.itemSelectionChanged.connect(self._on_item_selection_changed)
        layout.addWidget(self.structure_list)

        self.level_indicator = QtWidgets.QLabel("Niveau: Typologies")
        self.level_indicator.setStyleSheet("font-size: 12px; color: #6c757d; margin-top: 4px;")
        layout.addWidget(self.level_indicator)

        structure_btn_layout = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Ajouter")
        self.add_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_btn.setToolTip("Ajouter un nouvel élément")
        self.add_btn.clicked.connect(self._add_element)
        self.add_btn.setEnabled(False)
        structure_btn_layout.addWidget(self.add_btn)

        self.edit_btn = QtWidgets.QPushButton("Modifier")
        self.edit_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_btn.setToolTip("Modifier l'élément sélectionné")
        self.edit_btn.clicked.connect(self._edit_element)
        self.edit_btn.setEnabled(False)
        structure_btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("Supprimer")
        self.delete_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_btn.setToolTip("Supprimer l'élément sélectionné")
        self.delete_btn.clicked.connect(self._delete_element)
        self.delete_btn.setEnabled(False)
        structure_btn_layout.addWidget(self.delete_btn)

        layout.addLayout(structure_btn_layout)
        parent_layout.addWidget(structure_frame, 1)

    def _create_strategy_panel(self, parent_layout):
        strategy_frame = QtWidgets.QFrame()
        strategy_frame.setStyleSheet("background: #f9f9f9; border-radius: 8px;")
        layout = QtWidgets.QVBoxLayout(strategy_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Représentativité des Batches")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.subtitle = QtWidgets.QLabel("Distribution générale")
        self.subtitle.setStyleSheet("font-size: 12px; color: #6c757d;")
        self.subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle)

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(250)
        layout.addWidget(self.canvas)

        self.batch_info = QtWidgets.QTextEdit()
        self.batch_info.setReadOnly(True)
        self.batch_info.setMaximumHeight(120)
        self.batch_info.setStyleSheet(
            "font-size: 11px; color: #495057; border: 1px solid #ccc; border-radius: 4px; background: white;")
        layout.addWidget(self.batch_info)

        batch_btn_layout = QtWidgets.QHBoxLayout()
        self.generate_batches_btn = QtWidgets.QPushButton("Générer Batches")
        self.generate_batches_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.generate_batches_btn.setToolTip("Générer des batches intelligents")
        self.generate_batches_btn.clicked.connect(self._generate_intelligent_batches)
        self.generate_batches_btn.setEnabled(False)
        batch_btn_layout.addWidget(self.generate_batches_btn)

        self.configure_batches_btn = QtWidgets.QPushButton("Configurer")
        self.configure_batches_btn.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.configure_batches_btn.setToolTip("Configurer les batches existants")
        self.configure_batches_btn.clicked.connect(self._configure_batch_strategy)
        self.configure_batches_btn.setEnabled(False)
        batch_btn_layout.addWidget(self.configure_batches_btn)

        layout.addLayout(batch_btn_layout)
        parent_layout.addWidget(strategy_frame, 1)

    def _format_item_with_relationships(self, name, count, relationships):
        if not relationships:
            return f"{name} ({count})"

        # Première ligne: nom + compteur + relations source/target
        parts = [f"{name} ({count})"]
        rel_labels = []

        for rel in relationships:
            source = rel.get('source', '?')
            target = rel.get('target', '?')
            rel_name = rel.get('name', 'relation')
            parts.append(f"S: {source}  T: {target}")
            rel_labels.append(rel_name)

        first_line = " | ".join(parts)

        # Deuxième ligne: espaces + noms des relations alignés
        spacing = " " * (len(f"{name} ({count})") + 3)  # +3 pour " | "
        rel_names_line = spacing + (" " * 15).join(rel_labels)  # Espacement entre les noms

        return f"{first_line}\n{rel_names_line}"

    def _save_project(self):
        if not self.db_connection:
            logger.error("Connexion DB non disponible pour sauvegarde projet")
            return False

        try:
            project_name = self.project_name_edit.text().strip()
            description = self.project_desc_edit.toPlainText().strip()

            if not project_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le projet doit avoir un nom.")
                return False

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            result = cursor.fetchone()

            if result:
                project_id = result['id']
                cursor.execute("""
                               UPDATE projects
                               SET description = ?,
                                   updated_at  = CURRENT_TIMESTAMP
                               WHERE id = ?
                               """, (description, project_id))
            else:
                cursor.execute("""
                               INSERT INTO projects (name, description)
                               VALUES (?, ?)
                               """, (project_name, description))
                project_id = cursor.lastrowid

            self.db_connection.commit()
            self.project_data['nom'] = project_name
            self.project_data['description'] = description
            logger.info(f"Projet sauvegardé : {project_name} (ID: {project_id})")
            return project_id
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Erreur lors de la sauvegarde du projet : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde du projet : {str(e)}")
            return False

    def _reset_selection(self):
        self.selected_typologie = None
        self.selected_root = None
        self.selected_parent = None
        self.selected_item_data = None
        self.navigation_stack = []
        self._refresh_explorer_view()

    def _navigate_back(self):
        if not self.navigation_stack:
            return

        previous_state = self.navigation_stack.pop()
        self.selected_typologie = previous_state.get('typologie')
        self.selected_root = previous_state.get('root')
        self.selected_parent = previous_state.get('parent')
        self.selected_item_data = None
        self._refresh_explorer_view()

    def _save_navigation_state(self):
        self.navigation_stack.append({
            'typologie': self.selected_typologie,
            'root': self.selected_root,
            'parent': self.selected_parent
        })

    def _refresh_explorer_view(self):
        self.structure_list.clear()

        if self.selected_parent:
            self.structure_title.setText("Labels Enfants")
            self._show_child_labels()
        elif self.selected_root:
            self.structure_title.setText("Labels Parents")
            self._show_parent_labels()
        elif self.selected_typologie:
            if self.selected_typologie.get('is_taxonomic', True):
                self.structure_title.setText("Labels Racines")
            else:
                self.structure_title.setText("Labels")
            self._show_labels_after_typologie()
        else:
            self.structure_title.setText("Typologies")
            self._show_typologies()

        self._update_breadcrumb()
        self._update_level_indicator()
        self._update_navigation_buttons()
        self._update_project_info()
        self._update_batch_view_for_current_level()
        self._update_structure_buttons()

    def _show_typologies(self):
        for typologie in self.project_data.get('typologies', []):
            name = typologie.get('name', 'Sans nom')
            count = len(typologie.get('root_labels' if typologie.get('is_taxonomic', True) else 'simple_labels', []))

            relationships = typologie.get('relationships', [])

            item_text = self._format_item_with_relationships(name, count, relationships)
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {'type': 'typologie', 'object': typologie})
            item.setToolTip(f"Typologie: {name}")
            self.structure_list.addItem(item)

    def _show_labels_after_typologie(self):
        if not self.selected_typologie:
            return
        if self.selected_typologie.get('is_taxonomic', True):
            for root in self.selected_typologie.get('root_labels', []):
                name = root.get('name', 'Sans nom')
                count = len(root.get('parent_labels', []))
                relationships = root.get('relationships', [])

                item_text = self._format_item_with_relationships(name, count, relationships)
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {'type': 'root_label', 'object': root})
                item.setToolTip(f"Label racine: {name}")
                self.structure_list.addItem(item)
        else:
            for simple in self.selected_typologie.get('simple_labels', []):
                name = simple.get('name', 'Sans nom')
                relationships = simple.get('relationships', [])

                item_text = self._format_item_with_relationships(name, 0, relationships)
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {'type': 'simple_label', 'object': simple})
                item.setToolTip(f"Label: {name}")
                self.structure_list.addItem(item)

    def _show_parent_labels(self):
        if not self.selected_root:
            return
        for parent in self.selected_root.get('parent_labels', []):
            name = parent.get('name', 'Sans nom')
            count = len(parent.get('child_labels', []))
            relationships = parent.get('relationships', [])

            item_text = self._format_item_with_relationships(name, count, relationships)
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {'type': 'parent_label', 'object': parent})
            item.setToolTip(f"Label parent: {name}")
            self.structure_list.addItem(item)

    def _show_child_labels(self):
        if not self.selected_parent:
            return
        for child in self.selected_parent.get('child_labels', []):
            name = child.get('name', 'Sans nom')
            relationships = child.get('relationships', [])

            item_text = self._format_item_with_relationships(name, 0, relationships)
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {'type': 'child_label', 'object': child})
            item.setToolTip(f"Label enfant: {name}")
            self.structure_list.addItem(item)

    def _on_item_clicked(self, item):
        self._handle_item_selection(item)

    def _on_item_selection_changed(self):
        current_item = self.structure_list.currentItem()
        if current_item:
            self._handle_item_selection(current_item)
        else:
            self.selected_item_data = None
            self._update_batch_view_for_current_level()
        self._update_structure_buttons()

    def _handle_item_selection(self, item):
        item_data = item.data(Qt.UserRole)
        self.selected_item_data = item_data
        if item_data:
            self._update_batch_view_for_item(item_data)
            self._update_subtitle_for_selection(item_data)

    def _update_subtitle_for_selection(self, item_data):
        if not item_data:
            self.subtitle.setText("Distribution générale")
            return

        item_type = item_data.get('type')
        item_obj = item_data.get('object')
        name = item_obj.get('name', 'Élément') if item_obj else 'Élément'

        if item_type == 'typologie':
            self.subtitle.setText(f"Distribution pour la typologie : {name}")
        elif item_type == 'root_label':
            self.subtitle.setText(f"Distribution pour le label racine : {name}")
        elif item_type == 'parent_label':
            self.subtitle.setText(f"Distribution pour le label parent : {name}")
        elif item_type == 'child_label':
            self.subtitle.setText(f"Distribution pour le label enfant : {name}")
        elif item_type == 'simple_label':
            self.subtitle.setText(f"Distribution pour le label : {name}")
        else:
            self.subtitle.setText("Distribution selon l'élément sélectionné")

    def _on_item_double_clicked(self, item):
        item_data = item.data(Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_obj = item_data.get('object')

        self._save_navigation_state()

        if item_type == 'typologie':
            self.selected_typologie = item_obj
            self.selected_root = None
            self.selected_parent = None
        elif item_type == 'root_label':
            self.selected_root = item_obj
            self.selected_parent = None
        elif item_type == 'parent_label':
            self.selected_parent = item_obj
        elif item_type in ['child_label', 'simple_label']:
            return

        self.selected_item_data = None
        self._refresh_explorer_view()

    def _update_navigation_buttons(self):
        self.back_btn.setEnabled(len(self.navigation_stack) > 0)

    def _update_breadcrumb(self):
        breadcrumb_parts = ["Racine"]

        if self.selected_typologie:
            breadcrumb_parts.append(self.selected_typologie.get('name', 'Typologie'))

        if self.selected_root:
            breadcrumb_parts.append(self.selected_root.get('name', 'Root'))

        if self.selected_parent:
            breadcrumb_parts.append(self.selected_parent.get('name', 'Parent'))

        self.breadcrumb.setText(" > ".join(breadcrumb_parts))

    def _breadcrumb_clicked(self, event):
        self._reset_selection()

    def _update_level_indicator(self):
        if self.selected_parent:
            self.level_indicator.setText("Niveau: Labels Enfants")
        elif self.selected_root:
            self.level_indicator.setText("Niveau: Labels Parents")
        elif self.selected_typologie:
            if self.selected_typologie.get('is_taxonomic', True):
                self.level_indicator.setText("Niveau: Labels Racines")
            else:
                self.level_indicator.setText("Niveau: Labels")
        else:
            self.level_indicator.setText("Niveau: Typologies")

    def _update_batch_view_for_current_level(self):
        if self.selected_item_data:
            self._update_batch_view_for_item(self.selected_item_data)
            return

        if self.selected_parent:
            item_type = 'parent_label'
            item_obj = self.selected_parent
        elif self.selected_root:
            item_type = 'root_label'
            item_obj = self.selected_root
        elif self.selected_typologie:
            item_type = 'typologie'
            item_obj = self.selected_typologie
        else:
            item_type = None
            item_obj = None

        filtered_data = self._get_filtered_batches(item_type, item_obj)
        self._update_batch_pie_chart(filtered_data)
        self._update_batch_info(filtered_data)

        if item_obj:
            name = item_obj.get('name', 'Élément')
            if item_type == 'typologie':
                self.subtitle.setText(f"Distribution dans la typologie : {name}")
            elif item_type == 'root_label':
                self.subtitle.setText(f"Distribution dans le label racine : {name}")
            elif item_type == 'parent_label':
                self.subtitle.setText(f"Distribution dans le label parent : {name}")
        else:
            self.subtitle.setText("Distribution générale")

    def _update_batch_view_for_item(self, item_data):
        item_type = item_data.get('type')
        item_obj = item_data.get('object')

        filtered_data = self._get_filtered_batches(item_type, item_obj)
        self._update_batch_pie_chart(filtered_data)
        self._update_batch_info(filtered_data)

    def _get_filtered_batches(self, item_type, item_obj):
        filtered = {}

        if not item_obj:
            return self.batch_data

        name = item_obj.get('name', '')
        typology_name = self.selected_typologie.get('name', '') if self.selected_typologie else ''

        if item_type == 'typologie':
            prefix = name
            for batch_name, data in self.batch_data.items():
                if batch_name.startswith(prefix):
                    filtered[batch_name] = data
        elif item_type == 'root_label':
            prefix = f"{typology_name}/{name}"
            for batch_name, data in self.batch_data.items():
                if batch_name.startswith(prefix):
                    filtered[batch_name] = data
        elif item_type == 'parent_label':
            prefix = f"{typology_name}/{self.selected_root.get('name', '')}/{name}"
            for batch_name, data in self.batch_data.items():
                if batch_name.startswith(prefix):
                    filtered[batch_name] = data
        elif item_type == 'child_label':
            prefix = f"{typology_name}/{self.selected_root.get('name', '')}/{self.selected_parent.get('name', '')}/{name}"
            if prefix in self.batch_data:
                filtered[prefix] = self.batch_data[prefix]
        elif item_type == 'simple_label':
            prefix = f"{typology_name}/{name}"
            if prefix in self.batch_data:
                filtered[prefix] = self.batch_data[prefix]

        return filtered

    def _update_batch_pie_chart(self, filtered_data=None):
        data = filtered_data if filtered_data is not None else self.batch_data

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not data:
            ax.text(0.5, 0.5, 'Aucun batch\n\nGénérez des batches',
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=12, color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
        else:
            labels = list(data.keys())
            sizes = [data[label]['count'] for label in labels]

            if len(labels) > 12:
                sorted_data = sorted(data.items(), key=lambda x: x[1]['count'], reverse=True)
                top = sorted_data[:11]
                others = sum(item[1]['count'] for item in sorted_data[11:])
                labels = [item[0] for item in top] + ['Autres']
                sizes = [item[1]['count'] for item in top] + [others]

            colors = plt.cm.Set3(range(len(labels)))
            short_labels = [l.split('/')[-1] if l != 'Autres' else 'Autres' for l in labels]

            wedges, texts, autotexts = ax.pie(sizes, labels=None, colors=colors, autopct='%1.1f%%',
                                              startangle=90, textprops={'fontsize': 9})
            ax.set_title('Distribution des Batches', fontsize=12, fontweight='bold', pad=10)

            ax.legend(wedges, short_labels, title="Batches", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                      fontsize=9)

        self.canvas.draw()

    def _update_batch_info(self, filtered_data=None):
        data = filtered_data if filtered_data is not None else self.batch_data

        if not data:
            self.batch_info.setPlainText("Aucun batch défini.")
            return

        info = []
        total = sum(d['count'] for d in data.values())
        sorted_batches = sorted(data.items(), key=lambda x: x[1]['count'], reverse=True)

        info.append("BATCHES:")
        info.append("-" * 40)

        by_typo = {}
        for name, d in sorted_batches:
            typ = d.get('typologie_combination', 'Inconnu')
            by_typo.setdefault(typ, []).append((name, d))

        for typ_name, batches in by_typo.items():
            info.append(f"\n{typ_name}:")
            for batch_name, d in batches[:3]:
                context = d.get('context_path', '').split('/')[-1]
                info.append(f"  • {context}: {d['count']} ({d['percentage']:.1f}%)")
            if len(batches) > 3:
                info.append(f"  ... +{len(batches) - 3} autres")

        info.append(f"\nTOTAL: {total} échantillons sur {len(sorted_batches)} batches")
        self.batch_info.setPlainText('\n'.join(info))

    def _add_element(self):
        if not self.db_connection:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Connexion à la base de données non disponible.")
            return

        project_id = self._get_project_id()
        if not project_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Ajouter un élément")
        layout = QtWidgets.QVBoxLayout(dialog)

        name_label = QtWidgets.QLabel("Nom :")
        name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        desc_label = QtWidgets.QLabel("Description :")
        desc_edit = QtWidgets.QTextEdit()
        layout.addWidget(desc_label)
        layout.addWidget(desc_edit)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        name = name_edit.text().strip()
        description = desc_edit.toPlainText().strip()

        if not name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom est requis.")
            return

        try:
            cursor = self.db_connection.cursor()
            if self.selected_parent:
                cursor.execute("""
                               INSERT INTO child_labels (parent_label_id, name, description, category)
                               VALUES (?, ?, ?, ?)
                               """, (self.selected_parent['id'], name, description, 'default'))
                self.selected_parent.setdefault('child_labels', []).append({
                    'id': cursor.lastrowid,
                    'name': name,
                    'description': description,
                    'category': 'default'
                })
            elif self.selected_root:
                cursor.execute("""
                               INSERT INTO parent_labels (root_label_id, name, description, category)
                               VALUES (?, ?, ?, ?)
                               """, (self.selected_root['id'], name, description, 'default'))
                self.selected_root.setdefault('parent_labels', []).append({
                    'id': cursor.lastrowid,
                    'name': name,
                    'description': description,
                    'category': 'default',
                    'child_labels': []
                })
            elif self.selected_typologie:
                if self.selected_typologie.get('is_taxonomic', True):
                    cursor.execute("""
                                   INSERT INTO root_labels (typology_id, name, description, category)
                                   VALUES (?, ?, ?, ?)
                                   """, (self.selected_typologie['id'], name, description, 'default'))
                    self.selected_typologie.setdefault('root_labels', []).append({
                        'id': cursor.lastrowid,
                        'name': name,
                        'description': description,
                        'category': 'default',
                        'parent_labels': []
                    })
                else:
                    cursor.execute("""
                                   INSERT INTO simple_labels (typology_id, name, description, category)
                                   VALUES (?, ?, ?, ?)
                                   """, (self.selected_typologie['id'], name, description, 'default'))
                    self.selected_typologie.setdefault('simple_labels', []).append({
                        'id': cursor.lastrowid,
                        'name': name,
                        'description': description,
                        'category': 'default'
                    })
            else:
                is_taxonomic, ok = QtWidgets.QInputDialog.getItem(
                    self, "Type de typologie", "La typologie est-elle taxonomique ?",
                    ["Oui", "Non"], 0, False
                )
                if not ok:
                    return
                is_taxonomic = is_taxonomic == "Oui"
                cursor.execute("""
                               INSERT INTO typologies (project_id, name, description, is_taxonomic)
                               VALUES (?, ?, ?, ?)
                               """, (project_id, name, description, is_taxonomic))
                self.project_data['typologies'].append({
                    'id': cursor.lastrowid,
                    'name': name,
                    'description': description,
                    'is_taxonomic': is_taxonomic,
                    'root_labels': [],
                    'simple_labels': []
                })

            self.db_connection.commit()
            self._refresh_explorer_view()
            QtWidgets.QMessageBox.information(self, "Succès", f"Élément '{name}' ajouté avec succès.")
            logger.info(f"Élément ajouté : {name}")
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de l'élément : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de l'ajout de l'élément : {str(e)}")

    def _edit_element(self):
        if not self.db_connection or not self.selected_item_data:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Aucun élément sélectionné ou connexion DB indisponible.")
            return

        item_type = self.selected_item_data.get('type')
        item_obj = self.selected_item_data.get('object')

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Modifier l'élément")
        layout = QtWidgets.QVBoxLayout(dialog)

        name_label = QtWidgets.QLabel("Nom :")
        name_edit = QtWidgets.QLineEdit(item_obj.get('name', ''))
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        desc_label = QtWidgets.QLabel("Description :")
        desc_edit = QtWidgets.QTextEdit(item_obj.get('description', ''))
        layout.addWidget(desc_label)
        layout.addWidget(desc_edit)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        new_name = name_edit.text().strip()
        new_description = desc_edit.toPlainText().strip()

        if not new_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom est requis.")
            return

        try:
            cursor = self.db_connection.cursor()
            old_name = item_obj['name']
            if item_type == 'typologie':
                cursor.execute("UPDATE typologies SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description, item_obj['id']))
                item_obj['name'] = new_name
                item_obj['description'] = new_description
            elif item_type == 'root_label':
                cursor.execute("UPDATE root_labels SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description, item_obj['id']))
                item_obj['name'] = new_name
                item_obj['description'] = new_description
            elif item_type == 'parent_label':
                cursor.execute("UPDATE parent_labels SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description, item_obj['id']))
                item_obj['name'] = new_name
                item_obj['description'] = new_description
            elif item_type == 'child_label':
                cursor.execute("UPDATE child_labels SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description, item_obj['id']))
                item_obj['name'] = new_name
                item_obj['description'] = new_description
            elif item_type == 'simple_label':
                cursor.execute("UPDATE simple_labels SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description, item_obj['id']))
                item_obj['name'] = new_name
                item_obj['description'] = new_description

            self.db_connection.commit()
            if old_name != new_name:
                self._update_batch_names(old_name, new_name, item_type)
            self._refresh_explorer_view()
            QtWidgets.QMessageBox.information(self, "Succès", f"Élément '{new_name}' modifié avec succès.")
            logger.info(f"Élément modifié : {new_name}")
        except Exception as e:
            logger.error(f"Erreur lors de la modification de l'élément : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification de l'élément : {str(e)}")

    def _delete_element(self):
        if not self.db_connection or not self.selected_item_data:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Aucun élément sélectionné ou connexion DB indisponible.")
            return

        item_type = self.selected_item_data.get('type')
        item_obj = self.selected_item_data.get('object')
        name = item_obj.get('name', 'Élément')

        reply = QtWidgets.QMessageBox.question(
            self, "Confirmer Suppression",
            f"Supprimer l'élément '{name}' et ses données associées ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            cursor = self.db_connection.cursor()
            if item_type == 'typologie':
                cursor.execute("DELETE FROM typologies WHERE id = ?", (item_obj['id'],))
                self.project_data['typologies'] = [t for t in self.project_data['typologies'] if
                                                   t['id'] != item_obj['id']]
            elif item_type == 'root_label':
                cursor.execute("DELETE FROM root_labels WHERE id = ?", (item_obj['id'],))
                self.selected_typologie['root_labels'] = [r for r in self.selected_typologie['root_labels'] if
                                                          r['id'] != item_obj['id']]
            elif item_type == 'parent_label':
                cursor.execute("DELETE FROM parent_labels WHERE id = ?", (item_obj['id'],))
                self.selected_root['parent_labels'] = [p for p in self.selected_root['parent_labels'] if
                                                       p['id'] != item_obj['id']]
            elif item_type == 'child_label':
                cursor.execute("DELETE FROM child_labels WHERE id = ?", (item_obj['id'],))
                self.selected_parent['child_labels'] = [c for c in self.selected_parent['child_labels'] if
                                                        c['id'] != item_obj['id']]
            elif item_type == 'simple_label':
                cursor.execute("DELETE FROM simple_labels WHERE id = ?", (item_obj['id'],))
                self.selected_typologie['simple_labels'] = [s for s in self.selected_typologie['simple_labels'] if
                                                            s['id'] != item_obj['id']]

            self.db_connection.commit()
            path = self._get_current_path()[:-1]
            self._set_navigation_by_path(path)
            self._update_batch_data_after_deletion(item_type, name)
            QtWidgets.QMessageBox.information(self, "Succès", f"Élément '{name}' supprimé avec succès.")
            logger.info(f"Élément supprimé : {name}")
        except Exception as e:
            logger.error(f"Erreur suppression élément '{name}' : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression de l'élément : {str(e)}")

    def _update_batch_names(self, old_name, new_name, item_type):
        project_id = self._get_project_id()
        cursor = self.db_connection.cursor()
        for batch_name, data in list(self.batch_data.items()):
            new_batch_name = batch_name
            if item_type == 'typologie':
                if batch_name.startswith(old_name + '/'):
                    new_batch_name = new_name + batch_name[len(old_name):]
            elif item_type == 'root_label':
                prefix = f"{self.selected_typologie['name']}/{old_name}"
                if batch_name.startswith(prefix):
                    new_batch_name = f"{self.selected_typologie['name']}/{new_name}{batch_name[len(prefix):]}"
            elif item_type == 'parent_label':
                prefix = f"{self.selected_typologie['name']}/{self.selected_root['name']}/{old_name}"
                if batch_name.startswith(prefix):
                    new_batch_name = f"{self.selected_typologie['name']}/{self.selected_root['name']}/{new_name}{batch_name[len(prefix):]}"
            elif item_type == 'child_label' or item_type == 'simple_label':
                prefix = f"{self.selected_typologie['name']}/"
                if item_type == 'child_label':
                    prefix += f"{self.selected_root['name']}/{self.selected_parent['name']}/{old_name}"
                else:
                    prefix += old_name
                if batch_name == prefix:
                    new_batch_name = prefix.replace(old_name, new_name)

            if new_batch_name != batch_name:
                cursor.execute("""
                               UPDATE dataset_batches
                               SET batch_name   = ?,
                                   context_path = ?
                               WHERE project_id = ?
                                 AND batch_name = ?
                               """, (new_batch_name,
                                     new_batch_name.split('/', 1)[1] if '/' in new_batch_name else new_batch_name,
                                     project_id, batch_name))
                self.batch_data[new_batch_name] = self.batch_data.pop(batch_name)
        self.db_connection.commit()

    def _update_batch_data_after_deletion(self, item_type, name):
        project_id = self._get_project_id()
        cursor = self.db_connection.cursor()
        for batch_name in list(self.batch_data.keys()):
            if item_type == 'typologie' and batch_name.startswith(name + '/'):
                cursor.execute("DELETE FROM dataset_batches WHERE project_id = ? AND batch_name = ?",
                               (project_id, batch_name))
                del self.batch_data[batch_name]
            elif item_type == 'root_label' and batch_name.startswith(f"{self.selected_typologie['name']}/{name}/"):
                cursor.execute("DELETE FROM dataset_batches WHERE project_id = ? AND batch_name = ?",
                               (project_id, batch_name))
                del self.batch_data[batch_name]
            elif item_type == 'parent_label' and batch_name.startswith(
                    f"{self.selected_typologie['name']}/{self.selected_root['name']}/{name}/"):
                cursor.execute("DELETE FROM dataset_batches WHERE project_id = ? AND batch_name = ?",
                               (project_id, batch_name))
                del self.batch_data[batch_name]
            elif item_type in ['child_label', 'simple_label'] and batch_name == (
                    f"{self.selected_typologie['name']}/{self.selected_root['name']}/{self.selected_parent['name']}/{name}"
                    if item_type == 'child_label' else f"{self.selected_typologie['name']}/{name}"):
                cursor.execute("DELETE FROM dataset_batches WHERE project_id = ? AND batch_name = ?",
                               (project_id, batch_name))
                del self.batch_data[batch_name]
        self.db_connection.commit()

    def _get_current_path(self):
        path = []
        if self.selected_typologie:
            path.append(self.selected_typologie.get('name', 'Typologie'))
        if self.selected_root:
            path.append(self.selected_root.get('name', 'Root'))
        if self.selected_parent:
            path.append(self.selected_parent.get('name', 'Parent'))
        if self.selected_item_data and self.selected_item_data.get('type') in ['child_label', 'simple_label']:
            path.append(self.selected_item_data.get('object', {}).get('name', ''))
        return path

    def _set_navigation_by_path(self, path):
        self._reset_selection()
        if not path:
            return
        for typologie in self.project_data.get('typologies', []):
            if typologie.get('name') == path[0]:
                self.selected_typologie = typologie
                if len(path) > 1 and typologie.get('is_taxonomic', True):
                    for root in typologie.get('root_labels', []):
                        if root.get('name') == path[1]:
                            self.selected_root = root
                            if len(path) > 2:
                                for parent in root.get('parent_labels', []):
                                    if parent.get('name') == path[2]:
                                        self.selected_parent = parent
                                        break
                            break
                break
        self._refresh_explorer_view()

    def _load_existing_projects(self):
        if not self.db_connection:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Connexion à la base de données non disponible.")
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM projects ORDER BY name")
            projects = cursor.fetchall()

            current = self.project_combo.currentText()
            self.project_combo.clear()

            for project in projects:
                self.project_combo.addItem(project['name'])

            if current:
                index = self.project_combo.findText(current)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                else:
                    self._clear_project_interface()

            logger.info(f"Chargé {len(projects)} projets")
        except Exception as e:
            logger.error(f"Erreur chargement projets : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des projets : {str(e)}")

    def _get_project_id(self):
        project_name = self.project_combo.currentText()
        if not project_name:
            return None
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
        result = cursor.fetchone()
        return result['id'] if result else None

    def _load_project_data(self, project_name):
        if not self.db_connection:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Connexion à la base de données non disponible.")
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            row = cursor.fetchone()

            if row:
                self.project_name_edit.setText(row['name'])
                self.project_desc_edit.setPlainText(row['description'] or '')
                project_id = row['id']
                self.project_data = {"nom": project_name, "description": row['description'] or '', "typologies": []}

                cursor.execute("SELECT * FROM typologies WHERE project_id = ?", (project_id,))
                for typo_row in cursor.fetchall():
                    typology = {
                        'id': typo_row['id'],
                        'name': typo_row['name'],
                        'description': typo_row['description'] or '',
                        'is_taxonomic': bool(typo_row['is_taxonomic']),
                        'root_labels': [],
                        'simple_labels': []
                    }

                    if typology['is_taxonomic']:
                        cursor.execute("SELECT * FROM root_labels WHERE typology_id = ?", (typo_row['id'],))
                        for root_row in cursor.fetchall():
                            root = {
                                'id': root_row['id'],
                                'name': root_row['name'],
                                'description': root_row['description'] or '',
                                'category': root_row['category'],
                                'parent_labels': []
                            }

                            cursor.execute("SELECT * FROM parent_labels WHERE root_label_id = ?", (root_row['id'],))
                            for parent_row in cursor.fetchall():
                                parent = {
                                    'id': parent_row['id'],
                                    'name': parent_row['name'],
                                    'description': parent_row['description'] or '',
                                    'category': parent_row['category'],
                                    'child_labels': []
                                }

                                cursor.execute("SELECT * FROM child_labels WHERE parent_label_id = ?",
                                               (parent_row['id'],))
                                for child_row in cursor.fetchall():
                                    child = {
                                        'id': child_row['id'],
                                        'name': child_row['name'],
                                        'description': child_row['description'] or '',
                                        'category': child_row['category']
                                    }
                                    parent['child_labels'].append(child)

                                root['parent_labels'].append(parent)

                            typology['root_labels'].append(root)
                    else:
                        cursor.execute("SELECT * FROM simple_labels WHERE typology_id = ?", (typo_row['id'],))
                        for simple_row in cursor.fetchall():
                            simple = {
                                'id': simple_row['id'],
                                'name': simple_row['name'],
                                'description': simple_row['description'] or '',
                                'category': simple_row['category']
                            }
                            typology['simple_labels'].append(simple)

                    self.project_data['typologies'].append(typology)

                self._reset_selection()
                self._load_batch_data(project_id)
                self._enable_project_controls(True)
                self._update_project_info()
                self._update_project_buttons()
                logger.info(f"Projet chargé : {project_name}")
            else:
                self._clear_project_interface()
        except Exception as e:
            logger.error(f"Erreur chargement projet '{project_name}' : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement du projet : {str(e)}")

    def _update_project_info(self):
        if not self.project_data:
            self.project_info.setText("Aucun projet sélectionné")
            return

        typo_count = len(self.project_data.get('typologies', []))
        total_elements = sum(self._count_typologie_elements(t)
                             for t in self.project_data.get('typologies', []))
        batch_count = len(self.batch_data)

        info = f"""Statistiques:
• {typo_count} typologie(s)
• {total_elements} élément(s) total
• {batch_count} batch(es)

État: {'Prêt' if batch_count > 0 else 'Configuration nécessaire'}"""
        self.project_info.setText(info)

    def _count_typologie_elements(self, typologie):
        if typologie.get('is_taxonomic', True):
            total = 0
            for root in typologie.get('root_labels', []):
                total += 1
                for parent in root.get('parent_labels', []):
                    total += 1
                    total += len(parent.get('child_labels', []))
            return total
        else:
            return len(typologie.get('simple_labels', []))

    def _create_new_project(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Projet", "Nom du nouveau projet :"
        )

        if ok and name.strip():
            name = name.strip()
            if self._project_exists(name):
                QtWidgets.QMessageBox.warning(self, "Nom Existant", f"Un projet '{name}' existe déjà.")
                return

            self.project_data = {"nom": name, "description": "", "typologies": []}
            self.project_name_edit.setText(name)
            self.project_desc_edit.clear()
            self._reset_selection()
            self.batch_data = {}
            try:
                if self._save_project():
                    self._load_existing_projects()
                    index = self.project_combo.findText(name)
                    if index >= 0:
                        self.project_combo.setCurrentIndex(index)
                    else:
                        self.project_combo.addItem(name)
                        self.project_combo.setCurrentIndex(self.project_combo.findText(name))
                    self._update_batch_pie_chart()
                    self.batch_info.clear()
                    self._update_project_info()
                    QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{name}' créé avec succès.")
                    logger.info(f"Nouveau projet créé : {name}")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la création du projet.")
                    self._clear_project_interface()
            except Exception as e:
                logger.error(f"Erreur création projet '{name}' : {str(e)}")
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création du projet : {str(e)}")
                self._clear_project_interface()

    def _save_all_changes(self):
        project_id = self._get_project_id()
        if not project_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        try:
            if self._save_project():
                if self._save_batch_data(project_id):
                    QtWidgets.QMessageBox.information(self, "Succès",
                                                      f"Toutes les modifications pour le projet ont été sauvegardées.")
                    logger.info(f"Toutes les modifications sauvegardées pour le projet ID: {project_id}")
                    self._load_existing_projects()
                    self._on_project_selected(self.project_combo.currentText())
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la sauvegarde des batches.")
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la sauvegarde du projet.")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde globale : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde globale : {str(e)}")

    def _delete_project(self):
        project_id = self._get_project_id()
        project_name = self.project_combo.currentText()
        if not project_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Confirmer Suppression",
            f"Supprimer le projet '{project_name}' et toutes ses données ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("DELETE FROM dataset_batches WHERE project_id = ?", (project_id,))
                cursor.execute(
                    "DELETE FROM child_labels WHERE parent_label_id IN (SELECT id FROM parent_labels WHERE root_label_id IN (SELECT id FROM root_labels WHERE typology_id IN (SELECT id FROM typologies WHERE project_id = ?)))",
                    (project_id,))
                cursor.execute(
                    "DELETE FROM parent_labels WHERE root_label_id IN (SELECT id FROM root_labels WHERE typology_id IN (SELECT id FROM typologies WHERE project_id = ?))",
                    (project_id,))
                cursor.execute(
                    "DELETE FROM root_labels WHERE typology_id IN (SELECT id FROM typologies WHERE project_id = ?)",
                    (project_id,))
                cursor.execute(
                    "DELETE FROM simple_labels WHERE typology_id IN (SELECT id FROM typologies WHERE project_id = ?)",
                    (project_id,))
                cursor.execute("DELETE FROM typologies WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                self.db_connection.commit()
                self._clear_project_interface()
                self._load_existing_projects()
                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé avec succès.")
                logger.info(f"Projet supprimé : {project_name}")
            except Exception as e:
                logger.error(f"Erreur suppression projet '{project_name}' : {str(e)}")
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression : {str(e)}")

    def _update_project_buttons(self):
        has_project = bool(self.project_combo.currentText())
        self.delete_project_btn.setEnabled(has_project)
        self.save_project_btn.setEnabled(has_project)

    def _update_structure_buttons(self):
        has_selection = bool(self.selected_item_data)
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.add_btn.setEnabled(bool(self.project_data.get('nom')))

    def _generate_intelligent_batches(self):
        project_id = self._get_project_id()
        if not project_id:
            QtWidgets.QMessageBox.warning(self, "Aucun Projet", "Veuillez sélectionner un projet.")
            return

        typologies = self.project_data.get('typologies', [])
        if not typologies:
            QtWidgets.QMessageBox.warning(self, "Aucune Typologie", "Créez d'abord des typologies.")
            return

        batches = self._generate_typologie_combinations()
        if not batches:
            QtWidgets.QMessageBox.warning(self, "Aucun Batch", "Impossible de générer des batches.")
            return

        self._apply_intelligent_batch_distribution(batches)
        if self._save_batch_data(project_id):
            self._update_batch_view_for_current_level()
            QtWidgets.QMessageBox.information(
                self, "Batches Générés",
                f"{len(batches)} batches générés avec succès."
            )
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la sauvegarde des batches.")

    def _generate_typologie_combinations(self):
        batches = []

        for typologie in self.project_data.get('typologies', []):
            typo_name = typologie.get('name', 'Typologie')

            if typologie.get('is_taxonomic', True):
                combos = self._generate_taxonomic_combinations(typologie)
            else:
                combos = self._generate_simple_combinations(typologie)
            for combo in combos:
                batches.append({
                    'name': f"{typo_name}/{combo['path']}",
                    'typologie_combination': typo_name,
                    'context_path': combo['path'],
                    'weight': combo.get('weight', 1.0)
                })

        return batches

    def _generate_taxonomic_combinations(self, typologie):
        combinations = []
        for root in typologie.get('root_labels', []):
            combos = self._generate_root_combinations(root, root.get('name', 'Root'))
            combinations.extend(combos)
        return combinations

    def _generate_root_combinations(self, root, prefix):
        combinations = [{'path': prefix, 'weight': 1.0}]

        for parent in root.get('parent_labels', []):
            parent_name = parent.get('name', 'Parent')
            parent_path = f"{prefix}/{parent_name}"
            combinations.append({'path': parent_path, 'weight': 1.0})

            for child in parent.get('child_labels', []):
                child_name = child.get('name', 'Child')
                child_path = f"{parent_path}/{child_name}"
                combinations.append({'path': child_path, 'weight': 1.0})

        return combinations

    def _generate_simple_combinations(self, typologie):
        combinations = []
        for simple in typologie.get('simple_labels', []):
            name = simple.get('name', 'Simple')
            combinations.append({'path': name, 'weight': 1.0})
        return combinations

    def _apply_intelligent_batch_distribution(self, batches, total_samples=1000):
        if not batches:
            return

        min_per_batch = max(100, total_samples // (len(batches) * 3))
        remaining = total_samples - (len(batches) * min_per_batch)
        total_weight = sum(b['weight'] for b in batches)

        self.batch_data = {}

        for batch in batches:
            base = min_per_batch
            extra = int((batch['weight'] / total_weight) * remaining) if total_weight > 0 else 0
            total = base + extra

            self.batch_data[batch['name']] = {
                'count': total,
                'percentage': (total / total_samples) * 100 if total_samples > 0 else 0,
                'typologie_combination': batch['typologie_combination'],
                'context_path': batch['context_path']
            }

    def _configure_batch_strategy(self):
        if not self.batch_data:
            QtWidgets.QMessageBox.information(
                self, "Aucun Batch", "Générez d'abord des batches."
            )
            return

        dialog = BatchConfigDialog(self.batch_data, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.batch_data = dialog.get_configuration()
            if self._save_batch_data(self._get_project_id()):
                self._update_batch_view_for_current_level()
                QtWidgets.QMessageBox.information(self, "Succès", "Configuration des batches appliquée avec succès.")
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur",
                                               "Échec de la sauvegarde de la configuration des batches.")

    def _clear_project_interface(self):
        self.project_name_edit.clear()
        self.project_desc_edit.clear()
        self._reset_selection()
        self._enable_project_controls(False)
        self.batch_data = {}
        self._update_batch_pie_chart()
        self.batch_info.clear()
        self.project_info.setText("Aucun projet")
        self._update_project_buttons()
        self._update_structure_buttons()

    def _enable_project_controls(self, enabled):
        self.generate_batches_btn.setEnabled(enabled)
        self.configure_batches_btn.setEnabled(enabled)
        self.add_btn.setEnabled(enabled)
        self.save_project_btn.setEnabled(enabled)

    def _project_exists(self, project_name):
        try:
            if not self.db_connection:
                return False
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM projects WHERE name = ?", (project_name,))
            return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"Erreur vérification projet '{project_name}' : {str(e)}")
            return False

    def _load_batch_data(self, project_id):
        try:
            if not self.db_connection:
                return

            if not project_id:
                logger.error("project_id invalide pour chargement des batches")
                return

            cursor = self.db_connection.cursor()
            cursor.execute("""
                           SELECT batch_name, sample_count, percentage, typologie_combination, context_path
                           FROM dataset_batches
                           WHERE project_id = ?
                           """, (project_id,))

            self.batch_data = {}
            for row in cursor.fetchall():
                self.batch_data[row['batch_name']] = {
                    'count': row['sample_count'],
                    'percentage': row['percentage'],
                    'typologie_combination': row['typologie_combination'] or 'Inconnu',
                    'context_path': row['context_path']
                }

            if self.batch_data:
                self._update_batch_view_for_current_level()
                logger.debug(f"Batches chargés pour projet ID {project_id} : {json.dumps(self.batch_data, indent=2)}")
        except Exception as e:
            logger.error(f"Erreur chargement batches pour projet ID {project_id} : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des batches : {str(e)}")

    def _save_batch_data(self, project_id):
        try:
            if not self.db_connection:
                return False

            if not project_id:
                logger.error("project_id invalide pour sauvegarde des batches")
                return False

            cursor = self.db_connection.cursor()
            cursor.execute("DELETE FROM dataset_batches WHERE project_id = ?", (project_id,))

            for name, data in self.batch_data.items():
                cursor.execute("""
                               INSERT INTO dataset_batches
                               (project_id, batch_name, sample_count, percentage, typologie_combination, context_path)
                               VALUES (?, ?, ?, ?, ?, ?)
                               """, (project_id, name, data['count'], data['percentage'],
                                     data['typologie_combination'], data['context_path']))
            self.db_connection.commit()
            logger.debug(f"Batches sauvegardés pour projet ID {project_id} : {json.dumps(self.batch_data, indent=2)}")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde batches pour projet ID {project_id} : {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde des batches : {str(e)}")
            return False

    def get_project_data_for_generation(self):
        if not self.project_data or not self.batch_data:
            return None

        return {
            'project_name': self.project_data.get('nom', ''),
            'description': self.project_data.get('description', ''),
            'typologies': self.project_data.get('typologies', []),
            'batches': self.batch_data,
            'total_batches': len(self.batch_data),
            'total_samples': sum(d['count'] for d in self.batch_data.values())
        }

    def closeEvent(self, event):
        if self.db_connection:
            self.db_connection.close()
            logger.info("Connexion DB fermée")
        super().closeEvent(event)


class BatchConfigDialog(QtWidgets.QDialog):
    def __init__(self, batch_data, parent=None):
        super().__init__(parent)
        self.batch_data = batch_data.copy()
        self.setWindowTitle("Configuration des Batches")
        self.setModal(True)
        self.resize(750, 550)
        self._init_ui()
        self._populate_data()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Configuration des Batches")
        title.setStyleSheet("font-weight: bold; font-size: 15px; margin-bottom: 8px;")
        layout.addWidget(title)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Batch", "Typologie", "Échantillons", "Pourcentage"])
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.SelectedClicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_data(self):
        self.table.setRowCount(len(self.batch_data))
        total_count = sum(d['count'] for d in self.batch_data.values())
        row = 0
        for name, data in self.batch_data.items():
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(data.get('typologie_combination', 'Inconnu')))
            count_item = QtWidgets.QTableWidgetItem(str(data['count']))
            count_item.setData(Qt.UserRole, data['count'])
            self.table.setItem(row, 2, count_item)
            percent_item = QtWidgets.QTableWidgetItem(f"{data['percentage']:.1f}%")
            percent_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 3, percent_item)
            row += 1

        self.table.itemChanged.connect(self._update_percentages)

    def _update_percentages(self, item):
        if item.column() == 2:
            try:
                new_count = int(item.text())
                item.setData(Qt.UserRole, new_count)
            except ValueError:
                item.setText(str(item.data(Qt.UserRole)))
                return

            total_count = sum(self.table.item(r, 2).data(Qt.UserRole) for r in range(self.table.rowCount()))
            for r in range(self.table.rowCount()):
                count = self.table.item(r, 2).data(Qt.UserRole)
                percentage = (count / total_count * 100) if total_count > 0 else 0
                self.table.item(r, 3).setText(f"{percentage:.1f}%")

    def get_configuration(self):
        config = {}
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 0).text()
            count = self.table.item(r, 2).data(Qt.UserRole)
            percentage = float(self.table.item(r, 3).text().rstrip('%'))
            typologie = self.table.item(r, 1).text()
            context_path = self.batch_data[name].get('context_path', name.split('/', 1)[1] if '/' in name else name)
            config[name] = {
                'count': count,
                'percentage': percentage,
                'typologie_combination': typologie,
                'context_path': context_path
            }
        return config