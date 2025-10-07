#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import os
import sqlite3

from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtCore import Qt

from ui.localization.translator import tr
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.styles.theme import Theme

logger = logging.getLogger(__name__)


class DatasetGeneratorWidget(QtWidgets.QWidget):
    """
    Widget amélioré pour la gestion de la génération de datasets avec une structure hiérarchique
    """

    def __init__(self, conductor=None, parent=None):
        super().__init__(parent)

        self.data = {"context": []}  # Structure de données interne
        self.conductor = conductor

        self.apercu_view = None  

        # Initialiser la connexion à la base de données
        self.db_connection = None
        self._init_database()

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

        # Données de configuration pour l'aperçu
        self.config_data = {
            'platform': '',
            'custom_platform': '',
            'description': '',
            'output_format': 'JSON',
            'sample_count': 100,
            'training_technique': 'Full SFT'
        }

        if self.conductor:
            logger.info("Conducteur initialisé dans le constructeur de DatasetGenerationWidget")
            # Essayer d'obtenir la base de données du conductor s'il en a une
            if hasattr(self.conductor, 'database') and self.conductor.database:
                self.database = self.conductor.database
        else:
            logger.warning("Aucun conducteur fourni lors de l'initialisation")

        # Définir self.database pour la compatibilité
        self.database = self

        self._init_ui()

    def _init_database(self):
        """Initialise la connexion à la base de données SQLite"""
        try:
            # Chemin vers la base de données
            db_path = os.path.join("data", "liris.db")

            # Créer le répertoire data s'il n'existe pas
            os.makedirs("data", exist_ok=True)

            # Créer la connexion
            self.db_connection = sqlite3.connect(db_path)
            self.db_connection.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom

            # SUPPRESSION DIRECTE DE LA TABLE CORROMPUE VIA SQL
            try:
                cursor = self.db_connection.cursor()
                # Tester si la structure est corrompue
                cursor.execute("SELECT id FROM projects LIMIT 1")
                logger.info("Structure de table valide")
            except Exception as e:
                logger.warning(f"Table corrompue détectée : {str(e)}")
                logger.info("Suppression des tables corrompues...")

                # Supprimer les tables corrompues
                cursor = self.db_connection.cursor()
                cursor.execute("DROP TABLE IF EXISTS projects")
                cursor.execute("DROP TABLE IF EXISTS platforms")
                self.db_connection.commit()
                logger.info("Tables corrompues supprimées")

            # Créer les tables avec la bonne structure
            self._create_tables()

            # Tester la connexion
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            logger.info(f"Tables disponibles: {[table['name'] for table in tables]}")

            logger.info(f"Base de données initialisée avec succès : {db_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données : {str(e)}")
            self.db_connection = None
            raise e

    def _create_tables(self):
        """Crée les tables nécessaires dans la base de données"""
        try:
            cursor = self.db_connection.cursor()

            # Table pour les projets de dataset - SQL CORRIGÉ
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS projects (
                                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                   name TEXT UNIQUE NOT NULL,
                                                                   description TEXT,
                                                                   data TEXT,
                                                                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
            ''')

            # Table pour les plateformes
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS platforms (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               name TEXT UNIQUE NOT NULL,
                               config TEXT,
                               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
            ''')

            self.db_connection.commit()
            logger.info("Tables créées avec succès")

        except Exception as e:
            logger.error(f"Erreur lors de la création des tables : {str(e)}")
            raise e

    def set_database(self, database):
        """Méthode pour compatibilité avec l'ancien code"""
        # Si un objet database externe est fourni, l'utiliser
        if database:
            self.database = database
            logger.info("Base de données externe définie pour DatasetGenerationWidget")
        else:
            # Sinon utiliser notre connexion SQLite directe
            self.database = self
            logger.info("Utilisation de la connexion SQLite directe")

    def get_dataset_projet(self, project_name):
        """Récupère un projet de dataset depuis la base de données"""
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données")
                return None

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            row = cursor.fetchone()

            if row:
                project_data = {
                    'nom': row['name'],
                    'description': row['description'] or '',
                }

                # Décoder les données JSON si elles existent
                if row['data']:
                    try:
                        json_data = json.loads(row['data'])
                        project_data.update(json_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Erreur lors du décodage JSON pour le projet '{project_name}': {str(e)}")

                return project_data

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du projet '{project_name}': {str(e)}")
            return None

    def save_dataset_projet(self, project_name, project_data):
        """Sauvegarde un projet de dataset dans la base de données"""
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données")
                return False

            cursor = self.db_connection.cursor()

            # Debug: vérifier les tables existantes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logger.info(f"Tables existantes: {[table['name'] for table in tables]}")

            # Vérifier la structure de la table projects si elle existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(projects)")
                columns = cursor.fetchall()
                logger.info(f"Structure de la table projects: {[(col['name'], col['type']) for col in columns]}")
            else:
                logger.warning("La table 'projects' n'existe pas")
                return False

            # Séparer les données de base des données JSON
            description = project_data.get('description', '')

            # Copier les données sans les champs de base
            json_data = project_data.copy()
            json_data.pop('nom', None)
            json_data.pop('description', None)

            # Convertir les données en JSON string
            json_string = json.dumps(json_data, ensure_ascii=False, indent=2)

            # Vérifier si le projet existe déjà
            cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            existing = cursor.fetchone()

            if existing:
                # Mettre à jour
                cursor.execute('''
                               UPDATE projects
                               SET description = ?,
                                   data        = ?,
                                   updated_at  = CURRENT_TIMESTAMP
                               WHERE name = ?
                               ''', (description, json_string, project_name))
                logger.info(f"Projet '{project_name}' mis à jour")
            else:
                # Insérer
                cursor.execute('''
                               INSERT INTO projects (name, description, data)
                               VALUES (?, ?, ?)
                               ''', (project_name, description, json_string))
                logger.info(f"Nouveau projet '{project_name}' créé")

            self.db_connection.commit()
            logger.info(f"Projet '{project_name}' sauvegardé avec succès")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du projet '{project_name}': {str(e)}")
            return False

    def force_recreate_database(self):
        """Force la recréation de la base de données (méthode de debug)"""
        try:
            if self.db_connection:
                self.db_connection.close()

            # Supprimer le fichier de base de données
            db_path = os.path.join("data", "liris.db")
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info(f"Fichier de base de données supprimé: {db_path}")

            # Réinitialiser la base de données
            self._init_database()
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la recréation de la base de données: {str(e)}")
            return False

    def delete_dataset_projet(self, project_name):
        """Supprime un projet de dataset de la base de données"""
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données")
                return False

            cursor = self.db_connection.cursor()
            cursor.execute("DELETE FROM projects WHERE name = ?", (project_name,))
            self.db_connection.commit()

            if cursor.rowcount > 0:
                logger.info(f"Projet '{project_name}' supprimé avec succès")
                return True
            else:
                logger.warning(f"Aucun projet trouvé avec le nom '{project_name}'")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du projet '{project_name}': {str(e)}")
            return False

    def get_all_projects(self):
        """Récupère tous les projets de la base de données"""
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données")
                return []

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name, description FROM projects ORDER BY name")
            rows = cursor.fetchall()

            projects = []
            for row in rows:
                projects.append({
                    'name': row['name'],
                    'description': row['description'] or ''
                })

            return projects

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des projets: {str(e)}")
            return []

    def get_all_platforms(self):
        """Récupère toutes les plateformes de la base de données"""
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données")
                return []

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM platforms ORDER BY name")
            rows = cursor.fetchall()

            platforms = [row['name'] for row in rows]
            return platforms

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des plateformes: {str(e)}")
            return []

    def test_connection(self):
        """Teste la connexion à la base de données"""
        try:
            if not self.db_connection:
                raise Exception("Aucune connexion à la base de données")

            cursor = self.db_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True

        except Exception as e:
            logger.error(f"Erreur lors du test de connexion: {str(e)}")
            raise e

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

        # Utiliser notre méthode pour obtenir les plateformes
        self.platforms = self.get_all_platforms()

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

        # Ajout de la liste déroulante pour les projets existants
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_combo_changed)
        project_selection_layout.addWidget(self.project_combo)

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
            tr("project_config.edit_child_dialog_title")
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

        # Rafraîchir la combo des projets
        self._refresh_project_combo()

    def _on_project_combo_changed(self, index):
        """Gestion du changement de sélection dans la combo des projets"""
        if index < 0:
            return
        project_name = self.project_combo.currentText()
        if self.load_existing_project(project_name):
            # Exporter automatiquement la stratégie du projet
            self._export_project_strategy(project_name)
        else:
            logger.warning(f"Échec du chargement du projet '{project_name}' pour exportation")

    def _refresh_project_combo(self):
        """Rafraîchit la liste déroulante des projets"""
        self.project_combo.clear()
        projects = self.get_all_projects()
        project_names = [proj['name'] for proj in projects]
        self.project_combo.addItems(sorted(project_names))
        if self.current_project_name:
            self.project_combo.setCurrentText(self.current_project_name)

    def _on_add_new_project(self):
        """Gestion de l'ajout d'un nouveau projet"""
        logger.info("Création d'un nouveau projet demandée")

        new_project_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.new_project_dialog_title"),
            tr("project_config.new_project_dialog_text"),
        )

        # Demander la description du projet
        new_project_description, ok_desc = QtWidgets.QInputDialog.getMultiLineText(
            self,
            tr("project_config.new_project_description_title"),
            tr("project_config.new_project_description_text"),
        )

        if not ok_desc:
            new_project_description = ""

        if ok and new_project_name and ok_desc:
            new_project_name = new_project_name.strip()
            new_project_description = new_project_description.strip()

            if not new_project_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.invalid_name_title"),
                    tr("project_config.invalid_name_msg"),
                )
                return

            # Vérifier l'existence dans la base de données
            if self.get_dataset_projet(new_project_name):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.project_exists_title"),
                    tr("project_config.project_exists_msg").format(
                        project_name=new_project_name
                    ),
                )
                return

            # Créer la nouvelle structure de profil vide
            self.current_project_profile_data = {
                "nom": new_project_name,
                "description": new_project_description,
                "typologies": []  # Initialiser avec une liste vide
            }

            self.current_project_name = new_project_name

            # Mettre à jour l'interface
            self.project_name_edit.setText(new_project_name)

            # Sauvegarder immédiatement le nouveau projet vide dans la base de données
            self._save_configuration(show_message=False)

            # Rafraîchir la combo et sélectionner le nouveau
            self._refresh_project_combo()

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

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
                tr("project_config.no_project_selected_msg")
            )
            return

        # Mettre à jour les données du profil actuel avec le nom du projet
        project_name = self.project_name_edit.text().strip()
        if not project_name:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.invalid_name_title"),
                tr("dataset_project_config.project_name_empty_msg")
            )
            self.project_name_edit.setText(self.current_project_name)
            return

        # Vérifier si le nom a changé et s'il n'existe pas déjà
        if project_name != self.current_project_name:
            if self.get_dataset_projet(project_name):
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.project_exists_title"),
                    tr("project_config.project_exists_msg").format(project_name=project_name)
                )
                return

        # Mettre à jour les données du profil
        self.current_project_profile_data['nom'] = project_name

        # Valider la structure des données - Permettre la sauvegarde même sans typologie
        # if not self.current_project_profile_data.get('typologies'):
        #     if show_message:
        #         QtWidgets.QMessageBox.warning(
        #             self,
        #             tr("dataset_project_config.no_typologie_title"),
        #             tr("dataset_project_config.no_typologie_msg")
        #         )
        #     return

        # Diagnostic de la base de données avant sauvegarde
        try:
            if not self.db_connection:
                logger.error("Aucune connexion à la base de données disponible")
                raise Exception("Aucune connexion à la base de données")

            # Test de la connexion
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT 1")
            logger.info("Test de connexion OK")

            # Vérifier les tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Tables disponibles: {tables}")

            if 'projects' not in tables:
                logger.warning("Table 'projects' manquante, création...")
                self._create_tables()

        except Exception as e:
            logger.error(f"Erreur de diagnostic DB: {str(e)}")
            # Forcer la recréation de la base de données
            if show_message:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Problème de base de données",
                    "La base de données semble corrompue. Voulez-vous la recréer ?\n(Cela supprimera tous les projets existants)",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    if self.force_recreate_database():
                        logger.info("Base de données recréée avec succès")
                    else:
                        QtWidgets.QMessageBox.critical(self, "Erreur", "Impossible de recréer la base de données")
                        return
                else:
                    return

        # Sauvegarder dans la base de données
        try:
            # Si le nom du projet a changé, supprimer l'ancien
            if project_name != self.current_project_name and self.current_project_name:
                self.delete_dataset_projet(self.current_project_name)

            # Sauvegarder le nouveau/modifié projet
            success = self.save_dataset_projet(project_name, self.current_project_profile_data)

            if success:
                # Mettre à jour le nom actuel
                old_name = self.current_project_name
                self.current_project_name = project_name

                # Rafraîchir la combo des projets
                self._refresh_project_combo()
                self._refresh_preview_combo()

                if show_message:
                    QtWidgets.QMessageBox.information(
                        self,
                        tr("project_config.save_success_title"),
                        tr("project_config.save_success_msg").format(project_name=project_name)
                    )

                logger.info(f"Configuration du projet '{project_name}' sauvegardée avec succès")

                # Mettre à jour l'aperçu de la structure après sauvegarde
                self._update_structure_preview()

                # Passer à l'onglet Dataset pour permettre la configuration
                self.tab_widget.setCurrentIndex(1)  # Index 1 = onglet Dataset

                # Charger les données du projet dans l'onglet Dataset
                self._load_project_for_dataset_configuration()

            else:
                raise Exception("Échec de la sauvegarde dans la base de données")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde : {str(e)}")
            if show_message:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("project_config.save_error_title"),
                    tr("project_config.save_error_msg").format(error=str(e))
                )

    def _on_delete_project(self):
        """Gestion de la suppression d'un projet"""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_project_selected_title"),
                tr("project_config.no_project_selected_msg")
            )
            return

        # Confirmation de suppression
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.delete_project_confirm_title"),
            tr("project_config.delete_project_confirm_msg").format(project_name=self.current_project_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.delete_dataset_projet(self.current_project_name)

                if success:
                    project_name = self.current_project_name

                    # Réinitialiser les données
                    self.current_project_name = None
                    self.current_project_profile_data = None

                    # Effacer l'interface
                    self.project_name_edit.clear()
                    self._clear_hierarchy_widgets()
                    self._refresh_typologie_list()

                    # Désactiver les boutons
                    self.save_button.setEnabled(False)
                    self.delete_project_button.setEnabled(False)

                    # Rafraîchir les combos
                    self._refresh_project_combo()
                    self._refresh_preview_combo()

                    # Mettre à jour l'aperçu de la structure
                    self._update_structure_preview()

                    QtWidgets.QMessageBox.information(
                        self,
                        tr("project_config.delete_success_title"),
                        tr("project_config.delete_success_msg").format(project_name=project_name)
                    )

                    logger.info(f"Projet '{project_name}' supprimé avec succès")
                else:
                    raise Exception("Échec de la suppression dans la base de données")

            except Exception as e:
                logger.error(f"Erreur lors de la suppression du projet : {str(e)}")
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("project_config.delete_error_title"),
                    tr("project_config.delete_error_msg").format(error=str(e))
                )

    def _add_typologie(self):
        """Ajoute une nouvelle typologie"""
        typologie_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("dataset_project_config.add_typologie_dialog_title"),
            tr("dataset_project_config.add_typologie_dialog_text")
        )

        if ok and typologie_name:
            typologie_name = typologie_name.strip()
            if not typologie_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("dataset_project_config.typologie_name_empty_msg")
                )
                return

            # Créer la structure si elle n'existe pas
            if not self.current_project_profile_data:
                self.current_project_profile_data = {}

            # S'assurer que la clé 'typologies' existe
            if 'typologies' not in self.current_project_profile_data:
                self.current_project_profile_data['typologies'] = []

            # Vérifier si la typologie existe déjà
            typologies = self.current_project_profile_data['typologies']
            existing_names = [t.get('name') for t in typologies]
            if typologie_name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.typologie_exists_title"),
                    tr("dataset_project_config.typologie_exists_msg").format(typologie_name=typologie_name)
                )
                return

            # Ajouter la nouvelle typologie
            new_typologie = {
                'name': typologie_name,
                'description': '',
                'root_labels': []
            }
            self.current_project_profile_data['typologies'].append(new_typologie)

            # Mettre à jour l'interface
            self._refresh_typologie_list()

            # Sélectionner la nouvelle typologie
            for i in range(self.typologie_list_widget.count()):
                item = self.typologie_list_widget.item(i)
                if item.text() == typologie_name:
                    self.typologie_list_widget.setCurrentItem(item)
                    break

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            logger.info(f"Typologie '{typologie_name}' ajoutée avec succès")

    def _edit_typologie(self):
        """Édite la typologie sélectionnée"""
        current_item = self.typologie_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_typologie_selected_title"),
                tr("dataset_project_config.no_typologie_selected_msg")
            )
            return

        current_name = current_item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("dataset_project_config.edit_typologie_dialog_title"),
            tr("dataset_project_config.edit_typologie_dialog_text"),
            text=current_name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("dataset_project_config.typologie_name_empty_msg")
                )
                return

            if new_name == current_name:
                return  # Pas de changement

            # Vérifier si le nouveau nom existe déjà
            typologies = self.current_project_profile_data.get('typologies', [])
            existing_names = [t.get('name') for t in typologies]
            if new_name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.typologie_exists_title"),
                    tr("dataset_project_config.typologie_exists_msg").format(typologie_name=new_name)
                )
                return

            # Mettre à jour le nom
            current_index = self.typologie_list_widget.currentRow()
            if 0 <= current_index < len(typologies):
                typologies[current_index]['name'] = new_name
                self._refresh_typologie_list()
                self.typologie_list_widget.setCurrentRow(current_index)

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            logger.info(f"Typologie '{current_name}' renommée en '{new_name}'")

    def _remove_typologie(self):
        """Supprime la typologie sélectionnée"""
        current_item = self.typologie_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_typologie_selected_title"),
                tr("dataset_project_config.no_typologie_selected_msg")
            )
            return

        typologie_name = current_item.text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("dataset_project_config.delete_typologie_confirm_title"),
            tr("dataset_project_config.delete_typologie_confirm_msg").format(typologie_name=typologie_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            current_index = self.typologie_list_widget.currentRow()
            typologies = self.current_project_profile_data.get('typologies', [])

            if 0 <= current_index < len(typologies):
                del typologies[current_index]
                self._refresh_typologie_list()
                self._clear_hierarchy_widgets()

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            logger.info(f"Typologie '{typologie_name}' supprimée")

    def _on_typologie_selected(self, current, previous):
        """Gestion du changement de sélection de typologie avec désélection"""
        if not current:
            self._clear_hierarchy_widgets()
            self._update_button_states()
            return

        # Si on clique sur la même typologie, on désélectionne
        if previous and current == previous:
            self.typologie_list_widget.setCurrentItem(None)
            self._clear_hierarchy_widgets()
            self._update_button_states()
            return

        typologie_name = current.text()
        current_index = self.typologie_list_widget.currentRow()

        # Charger les labels racines de la typologie sélectionnée
        typologies = self.current_project_profile_data.get('typologies', [])
        if 0 <= current_index < len(typologies):
            typologie = typologies[current_index]
            self._load_root_labels(typologie.get('root_labels', []))

        self._update_button_states()
        logger.debug(f"Typologie sélectionnée : {typologie_name}")

    def _load_root_labels(self, root_labels):
        """Charge les labels racines dans la liste"""
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()

        for root_label in root_labels:
            item = QtWidgets.QListWidgetItem(root_label.get('name', ''))
            item.setData(Qt.UserRole, root_label)
            self.root_list_widget.addItem(item)

        # Ne pas sélectionner automatiquement le premier élément
        # L'utilisateur doit cliquer explicitement
        self._update_button_states()

    def _add_root_label(self):
        """Ajout d'un label racine"""
        if not self._ensure_typologie_selected():
            return

        root_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("dataset_project_config.add_root_dialog_title"),
            tr("dataset_project_config.add_root_dialog_text")
        )

        if ok and root_name:
            root_name = root_name.strip()
            if not root_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("dataset_project_config.root_name_empty_msg")
                )
                return

            typologie = self._get_current_typologie()

            if typologie:
                # Vérifier si le nom existe déjà
                existing_names = [r.get('name') for r in typologie.get('root_labels', [])]
                if root_name in existing_names:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("dataset_project_config.root_exists_title"),
                        tr("dataset_project_config.root_exists_msg").format(root_name=root_name)
                    )
                    return

                # Ajouter le nouveau label racine
                new_root = {
                    'name': root_name,
                    'description': '',
                    'category': 'default',
                    'parent_labels': []
                }

                typologie.setdefault('root_labels', []).append(new_root)
                self._load_root_labels(typologie['root_labels'])

                # Sélectionner le nouveau label
                for i in range(self.root_list_widget.count()):
                    if self.root_list_widget.item(i).text() == root_name:
                        self.root_list_widget.setCurrentRow(i)
                        break

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label racine '{root_name}' ajouté")

    def _edit_root_label(self):
        """Édition du label racine sélectionné"""
        current_item = self.root_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_root_selected_title"),
                tr("dataset_project_config.no_root_selected_msg")
            )
            return

        current_name = current_item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("dataset_project_config.edit_root_dialog_title"),
            tr("dataset_project_config.edit_root_dialog_text"),
            text=current_name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("dataset_project_config.root_name_empty_msg")
                )
                return

            if new_name == current_name:
                return

            typologie = self._get_current_typologie()
            root_labels = typologie.get('root_labels', [])
            current_index = self.root_list_widget.currentRow()

            # Vérifier si le nouveau nom existe déjà
            existing_names = [r.get('name') for r in root_labels]
            if new_name in existing_names:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.root_exists_title"),
                    tr("dataset_project_config.root_exists_msg").format(root_name=new_name)
                )
                return

            # Mettre à jour le nom
            if 0 <= current_index < len(root_labels):
                root_labels[current_index]['name'] = new_name
                self._load_root_labels(root_labels)
                self.root_list_widget.setCurrentRow(current_index)

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            logger.info(f"Label racine '{current_name}' renommé en '{new_name}'")

    def _remove_root_label(self):
        """Suppression du label racine sélectionné"""
        current_item = self.root_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_root_selected_title"),
                tr("dataset_project_config.no_root_selected_msg")
            )
            return

        root_name = current_item.text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("dataset_project_config.delete_root_confirm_title"),
            tr("dataset_project_config.delete_root_confirm_msg").format(root_name=root_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            typologie = self._get_current_typologie()
            root_labels = typologie.get('root_labels', [])
            current_index = self.root_list_widget.currentRow()

            if 0 <= current_index < len(root_labels):
                del root_labels[current_index]
                self._load_root_labels(root_labels)
                self.parent_list_widget.clear()
                self.child_list_widget.clear()

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            logger.info(f"Label racine '{root_name}' supprimé")

    def _on_root_label_selected(self, current, previous):
        """Gestion de la sélection d'un label racine avec désélection"""
        if not current:
            self.parent_list_widget.clear()
            self.child_list_widget.clear()
            self._update_button_states()
            return

        # Si on clique sur le même élément, on désélectionne
        if previous and current == previous:
            self.root_list_widget.setCurrentItem(None)
            self.parent_list_widget.clear()
            self.child_list_widget.clear()
            self._update_button_states()
            return

        # Charger les labels parents
        current_index = self.root_list_widget.currentRow()
        typologie = self._get_current_typologie()

        if typologie:
            root_labels = typologie.get('root_labels', [])
            if 0 <= current_index < len(root_labels):
                root_label = root_labels[current_index]
                self._load_parent_labels(root_label.get('parent_labels', []))

        self._update_button_states()
        logger.debug(f"Label racine sélectionné : {current.text()}")

    def _load_parent_labels(self, parent_labels):
        """Charge les labels parents dans la liste"""
        self.parent_list_widget.clear()
        self.child_list_widget.clear()

        for parent_label in parent_labels:
            item = QtWidgets.QListWidgetItem(parent_label.get('name', ''))
            item.setData(Qt.UserRole, parent_label)
            self.parent_list_widget.addItem(item)

        # Ne pas sélectionner automatiquement
        self._update_button_states()

    # ======== LABELS PARENTS ========
    def _on_parent_label_selected(self, current, previous):
        """Gestion de la sélection d'un label parent avec désélection"""
        if not current:
            self.child_list_widget.clear()
            self._update_button_states()
            return

        # Si on clique sur le même élément, on désélectionne
        if previous and current == previous:
            self.parent_list_widget.setCurrentItem(None)
            self.child_list_widget.clear()
            self._update_button_states()
            return

        # Charger les labels enfants
        current_index = self.parent_list_widget.currentRow()
        root_label = self._get_current_root_label()

        if root_label:
            parent_labels = root_label.get('parent_labels', [])
            if 0 <= current_index < len(parent_labels):
                parent_label = parent_labels[current_index]
                self._load_child_labels(parent_label.get('child_labels', []))

        self._update_button_states()
        logger.debug(f"Label parent sélectionné : {current.text()}")

    def _add_parent_label(self):
        """Ajout d'un label parent"""
        if not self._ensure_root_selected():
            return

        parent_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_parent_dialog_title"),
            tr("project_config.add_parent_dialog_text")
        )

        if ok and parent_name:
            parent_name = parent_name.strip()
            if not parent_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("project_config.parent_name_empty_msg")
                )
                return

            root_label = self._get_current_root_label()
            if root_label:
                # Vérifier si le nom existe déjà
                existing_names = [p.get('name') for p in root_label.get('parent_labels', [])]
                if parent_name in existing_names:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.parent_exists_title"),
                        tr("project_config.parent_exists_msg").format(parent_name=parent_name)
                    )
                    return

                # Ajouter le nouveau label parent
                new_parent = {
                    'name': parent_name,
                    'description': '',
                    'category': 'default',
                    'child_labels': []
                }

                root_label.setdefault('parent_labels', []).append(new_parent)
                self._load_parent_labels(root_label['parent_labels'])

                # Sélectionner le nouveau label
                for i in range(self.parent_list_widget.count()):
                    if self.parent_list_widget.item(i).text() == parent_name:
                        self.parent_list_widget.setCurrentRow(i)
                        break

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label parent '{parent_name}' ajouté")

    def _edit_parent_label(self):
        """Édition du label parent sélectionné"""
        current_item = self.parent_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_parent_selected_title"),
                tr("project_config.no_parent_selected_msg")
            )
            return

        current_name = current_item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_parent_dialog_title"),
            tr("project_config.edit_parent_dialog_text"),
            text=current_name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("project_config.parent_name_empty_msg")
                )
                return

            if new_name == current_name:
                return

            root_label = self._get_current_root_label()
            if root_label:
                parent_labels = root_label.get('parent_labels', [])
                current_index = self.parent_list_widget.currentRow()

                # Vérifier si le nouveau nom existe déjà
                existing_names = [p.get('name') for p in parent_labels]
                if new_name in existing_names:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.parent_exists_title"),
                        tr("project_config.parent_exists_msg").format(parent_name=new_name)
                    )
                    return

                # Mettre à jour le nom
                if 0 <= current_index < len(parent_labels):
                    parent_labels[current_index]['name'] = new_name
                    self._load_parent_labels(parent_labels)
                    self.parent_list_widget.setCurrentRow(current_index)

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label parent '{current_name}' renommé en '{new_name}'")

    def _remove_parent_label(self):
        """Suppression du label parent sélectionné"""
        current_item = self.parent_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_parent_selected_title"),
                tr("project_config.no_parent_selected_msg")
            )
            return

        parent_name = current_item.text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.delete_parent_confirm_title"),
            tr("project_config.delete_parent_confirm_msg").format(parent_name=parent_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            root_label = self._get_current_root_label()
            if root_label:
                parent_labels = root_label.get('parent_labels', [])
                current_index = self.parent_list_widget.currentRow()

                if 0 <= current_index < len(parent_labels):
                    del parent_labels[current_index]
                    self._load_parent_labels(parent_labels)
                    self.child_list_widget.clear()

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label parent '{parent_name}' supprimé")

    # ======== LABELS ENFANTS ========

    def _load_child_labels(self, child_labels):
        """Charge les labels enfants dans la liste"""
        self.child_list_widget.clear()

        for child_label in child_labels:
            item = QtWidgets.QListWidgetItem(child_label.get('name', ''))
            item.setData(Qt.UserRole, child_label)
            self.child_list_widget.addItem(item)

        # Ne pas sélectionner automatiquement
        self._update_button_states()

    def _on_child_label_selected(self, current, previous):
        """Gestion de la sélection d'un label enfant avec désélection"""
        if not current:
            self._update_button_states()
            return

        # Si on clique sur le même élément, on désélectionne
        if previous and current == previous:
            self.child_list_widget.setCurrentItem(None)
            self._update_button_states()
            return

        self._update_button_states()
        logger.debug(f"Label enfant sélectionné : {current.text()}")

    def _add_child_label(self):
        """Ajout d'un label enfant"""
        if not self._ensure_parent_selected():
            return

        child_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.add_child_dialog_title"),
            tr("project_config.add_child_dialog_text")
        )

        if ok and child_name:
            child_name = child_name.strip()
            if not child_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("project_config.child_name_empty_msg")
                )
                return

            parent_label = self._get_current_parent_label()
            if parent_label:
                # Vérifier si le nom existe déjà
                existing_names = [c.get('name') for c in parent_label.get('child_labels', [])]
                if child_name in existing_names:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.child_exists_title"),
                        tr("project_config.child_exists_msg").format(child_name=child_name)
                    )
                    return

                # Ajouter le nouveau label enfant
                new_child = {
                    'name': child_name,
                    'description': '',
                    'category': 'default'
                }

                parent_label.setdefault('child_labels', []).append(new_child)
                self._load_child_labels(parent_label['child_labels'])

                # Sélectionner le nouveau label
                for i in range(self.child_list_widget.count()):
                    if self.child_list_widget.item(i).text() == child_name:
                        self.child_list_widget.setCurrentRow(i)
                        break

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label enfant '{child_name}' ajouté")

    def _edit_child_label(self):
        """Édition du label enfant sélectionné"""
        current_item = self.child_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_child_selected_title"),
                tr("project_config.no_child_selected_msg")
            )
            return

        current_name = current_item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("project_config.edit_child_dialog_title"),
            tr("project_config.edit_child_dialog_text"),
            text=current_name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.invalid_name_title"),
                    tr("project_config.child_name_empty_msg")
                )
                return

            if new_name == current_name:
                return

            parent_label = self._get_current_parent_label()
            if parent_label:
                child_labels = parent_label.get('child_labels', [])
                current_index = self.child_list_widget.currentRow()

                # Vérifier si le nouveau nom existe déjà
                existing_names = [c.get('name') for c in child_labels]
                if new_name in existing_names:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("project_config.child_exists_title"),
                        tr("project_config.child_exists_msg").format(child_name=new_name)
                    )
                    return

                # Mettre à jour le nom
                if 0 <= current_index < len(child_labels):
                    child_labels[current_index]['name'] = new_name
                    self._load_child_labels(child_labels)
                    self.child_list_widget.setCurrentRow(current_index)

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label enfant '{current_name}' renommé en '{new_name}'")

    def _remove_child_label(self):
        """Suppression du label enfant sélectionné"""
        current_item = self.child_list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_child_selected_title"),
                tr("project_config.no_child_selected_msg")
            )
            return

        child_name = current_item.text()
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("project_config.delete_child_confirm_title"),
            tr("project_config.delete_child_confirm_msg").format(child_name=child_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            parent_label = self._get_current_parent_label()
            if parent_label:
                child_labels = parent_label.get('child_labels', [])
                current_index = self.child_list_widget.currentRow()

                if 0 <= current_index < len(child_labels):
                    del child_labels[current_index]
                    self._load_child_labels(child_labels)

                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

                logger.info(f"Label enfant '{child_name}' supprimé")

    def _create_projet_tab(self, parent):
        """Crée l'onglet Projet avec aperçu de la structure et panneau de configuration"""
        layout = QtWidgets.QHBoxLayout(parent)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        # ======= COLONNE GAUCHE : Aperçu de la structure =======
        left_frame = QtWidgets.QFrame()
        left_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        left_frame.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #ddd;
                padding: 10px;
            }
            """
        )

        left_layout = QtWidgets.QVBoxLayout(left_frame)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        lbl_apercu = QtWidgets.QLabel("📂 Aperçu de la structure")
        lbl_apercu.setStyleSheet(
            """
            font-weight: bold;
            font-size: 16px;
            color: #2c3e50;
            """
        )
        left_layout.addWidget(lbl_apercu)

        # Ajout de la liste déroulante pour sélectionner le projet à afficher
        project_select_layout = QtWidgets.QHBoxLayout()
        lbl_select = QtWidgets.QLabel("Sélectionner un projet :")
        lbl_select.setStyleSheet("color: #495057;")
        project_select_layout.addWidget(lbl_select)

        self.preview_project_combo = QtWidgets.QComboBox()
        self.preview_project_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            """
        )
        self.preview_project_combo.currentIndexChanged.connect(self._on_preview_project_changed)
        project_select_layout.addWidget(self.preview_project_combo)
        left_layout.addLayout(project_select_layout)

        self.apercu_view = QtWidgets.QTextEdit()
        self.apercu_view.setReadOnly(True)
        self.apercu_view.setStyleSheet(
            """
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #ced4da;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
            }
            """
        )
        left_layout.addWidget(self.apercu_view, 1)  # 1 = prend tout l'espace restant

        # ======= COLONNE DROITE : Configuration =======
        right_frame = QtWidgets.QFrame()
        right_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        right_frame.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #ddd;
                padding: 10px;
            }
            """
        )

        right_layout = QtWidgets.QVBoxLayout(right_frame)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(15)

        # Titre configuration
        lbl_config = QtWidgets.QLabel("⚙️ Configuration")
        lbl_config.setStyleSheet(
            """
            font-weight: bold;
            font-size: 16px;
            color: #2c3e50;
            """
        )
        right_layout.addWidget(lbl_config)

        lbl_theme = QtWidgets.QLabel("Sélectionnez un thème à configurer")
        lbl_theme.setStyleSheet(
            """
            background-color: #e9ecef;
            padding: 8px;
            border-radius: 4px;
            color: #495057;
            font-size: 14px;
            """
        )
        right_layout.addWidget(lbl_theme)

        # Champ plateforme
        lbl_plateforme = QtWidgets.QLabel("🖥 Plateforme")
        lbl_plateforme.setStyleSheet("font-weight: bold; color: #495057;")
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.addItems(["Jupyter", "Google Colab", "Kaggle", "Databricks", "SageMaker", "Hugging Face", "OpenAI", "Autre"])
        self.platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        self.platform_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            QComboBox::drop-down {
                border-left: 1px solid #ced4da;
            }
            """
        )
        right_layout.addWidget(lbl_plateforme)
        right_layout.addWidget(self.platform_combo)

        # Champ personnalisé pour plateforme (caché initialement)
        self.custom_platform_edit = QtWidgets.QLineEdit()
        self.custom_platform_edit.setPlaceholderText("Entrez une plateforme personnalisée...")
        self.custom_platform_edit.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            """
        )
        self.custom_platform_edit.textChanged.connect(self._update_config)
        self.custom_platform_edit.setVisible(False)
        right_layout.addWidget(self.custom_platform_edit)

        # Description
        lbl_description = QtWidgets.QLabel("📝 Description")
        lbl_description.setStyleSheet("font-weight: bold; color: #495057;")
        self.txt_description = QtWidgets.QTextEdit()
        self.txt_description.setPlaceholderText(
            "Entrez la description pour la génération du dataset..."
        )
        self.txt_description.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            """
        )
        self.txt_description.textChanged.connect(self._update_config)
        right_layout.addWidget(lbl_description)
        right_layout.addWidget(self.txt_description)

        # Format de sortie
        lbl_format = QtWidgets.QLabel("📄 Format de sortie")
        lbl_format.setStyleSheet("font-weight: bold; color: #495057;")
        self.cb_format = QtWidgets.QComboBox()
        self.cb_format.addItems(["JSON", "CSV", "Parquet"])
        self.cb_format.currentIndexChanged.connect(self._update_config)
        self.cb_format.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            QComboBox::drop-down {
                border-left: 1px solid #ced4da;
            }
            """
        )
        right_layout.addWidget(lbl_format)
        right_layout.addWidget(self.cb_format)

        # Nombre d'échantillons
        lbl_samples = QtWidgets.QLabel("🔢 Nombre d'échantillons")
        lbl_samples.setStyleSheet("font-weight: bold; color: #495057;")
        self.spin_samples = QtWidgets.QSpinBox()
        self.spin_samples.setRange(1, 1000000)
        self.spin_samples.setValue(100)
        self.spin_samples.valueChanged.connect(self._update_config)
        self.spin_samples.setStyleSheet(
            """
            QSpinBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            """
        )
        right_layout.addWidget(lbl_samples)
        right_layout.addWidget(self.spin_samples)

        # Technique d'entraînement
        lbl_technique = QtWidgets.QLabel("🧠 Technique d'entraînement")
        lbl_technique.setStyleSheet("font-weight: bold; color: #495057;")
        self.cb_technique = QtWidgets.QComboBox()
        self.cb_technique.addItems(["Full SFT", "RLHF", "Fine-tuning"])
        self.cb_technique.currentIndexChanged.connect(self._update_config)
        self.cb_technique.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            QComboBox::drop-down {
                border-left: 1px solid #ced4da;
            }
            """
        )
        right_layout.addWidget(lbl_technique)
        right_layout.addWidget(self.cb_technique)

        # Bouton Génération
        btn_generation = QtWidgets.QPushButton("🚀 Génération")
        btn_generation.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {Theme.SECONDARY_COLOR};
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
            """
        )
        right_layout.addWidget(btn_generation)

        # Ajout des colonnes gauche et droite au layout principal
        layout.addWidget(left_frame, 3)  # Poids 3
        layout.addWidget(right_frame, 2)  # Poids 2

        # Rafraîchir la combo de preview
        self._refresh_preview_combo()

    def _refresh_preview_combo(self):
        """Rafraîchit la liste déroulante des projets pour l'aperçu"""
        if not hasattr(self, 'preview_project_combo') or self.preview_project_combo is None:
            return
        self.preview_project_combo.clear()
        self.preview_project_combo.addItem("-- Sélectionnez un projet --")
        projects = self.get_all_projects()
        project_names = [proj['name'] for proj in projects]
        self.preview_project_combo.addItems(sorted(project_names))
        if self.current_project_name:
            self.preview_project_combo.setCurrentText(self.current_project_name)

    def _on_preview_project_changed(self, index):
        """Gestion du changement de sélection dans la combo de preview"""
        if index == 0:
            self.apercu_view.setHtml("""
                <div style='font-family: Arial, sans-serif; padding: 20px; text-align: center; color: #7f8c8d;'>
                    <h3>📋 Sélectionnez un projet</h3>
                    <p>Choisissez un projet pour voir sa structure hiérarchique.</p>
                </div>
            """)
            return

        project_name = self.preview_project_combo.currentText()
        project_data = self.get_dataset_projet(project_name)
        if project_data:
            show_config = (project_name == self.current_project_name)
            self._update_structure_preview(project_data=project_data, show_config=show_config)

    def _on_platform_changed(self, index):
        """Gestion du changement de plateforme"""
        platform = self.platform_combo.currentText()
        if platform == "Autre":
            self.custom_platform_edit.setVisible(True)
        else:
            self.custom_platform_edit.setVisible(False)
            self.custom_platform_edit.clear()
        self._update_config()

    def _update_config(self):
        """Récupère toutes les données insérées dans les formulaires"""
        platform = self.platform_combo.currentText()
        if platform == "Autre":
            self.config_data['platform'] = self.custom_platform_edit.text().strip() or 'Autre'
        else:
            self.config_data['platform'] = platform

        self.config_data['description'] = self.txt_description.toPlainText().strip()
        self.config_data['output_format'] = self.cb_format.currentText()
        self.config_data['sample_count'] = self.spin_samples.value()
        self.config_data['training_technique'] = self.cb_technique.currentText()

        # Mettre à jour l'aperçu après chaque changement
        self._update_structure_preview()

    def _refresh_typologie_list(self):
        """Rafraîchit la liste des typologies"""
        self.typologie_list_widget.clear()

        if self.current_project_profile_data:
            typologies = self.current_project_profile_data.get('typologies', [])
            for typologie in typologies:
                item = QtWidgets.QListWidgetItem(typologie.get('name', ''))
                item.setData(Qt.UserRole, typologie)
                self.typologie_list_widget.addItem(item)

        # Mettre à jour l'état des boutons après le rafraîchissement
        self._update_button_states()

    def _clear_hierarchy_widgets(self):
        """Efface tous les widgets de hiérarchie"""
        self.root_list_widget.clear()
        self.parent_list_widget.clear()
        self.child_list_widget.clear()
        self._update_button_states()

    def _ensure_typologie_selected(self):
        """S'assure qu'une typologie est sélectionnée"""
        if self.typologie_list_widget.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_typologie_selected_title"),
                tr("dataset_project_config.select_typologie_first_msg")
            )
            return False
        return True

    def _ensure_root_selected(self):
        """S'assure qu'un label racine est sélectionné"""
        if not self._ensure_typologie_selected():
            return False

        if self.root_list_widget.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self,
                tr("dataset_project_config.no_root_selected_title"),
                tr("dataset_project_config.select_root_first_msg")
            )
            return False
        return True

    def _ensure_parent_selected(self):
        """S'assure qu'un label parent est sélectionné"""
        if not self._ensure_root_selected():
            return False

        if self.parent_list_widget.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self,
                tr("project_config.no_parent_selected_title"),
                tr("project_config.select_parent_first_msg")
            )
            return False
        return True

    def _get_current_typologie(self):
        """Retourne la typologie actuellement sélectionnée"""
        current_item = self.typologie_list_widget.currentItem()
        if current_item:
            current_index = self.typologie_list_widget.currentRow()
            typologies = self.current_project_profile_data.get('typologies', [])
            if 0 <= current_index < len(typologies):
                return typologies[current_index]
        return None

    def _get_current_root_label(self):
        """Retourne le label racine actuellement sélectionné"""
        typologie = self._get_current_typologie()
        if typologie:
            current_item = self.root_list_widget.currentItem()
            if current_item:
                current_index = self.root_list_widget.currentRow()
                root_labels = typologie.get('root_labels', [])
                if 0 <= current_index < len(root_labels):
                    return root_labels[current_index]
        return None

    def _get_current_parent_label(self):
        """Retourne le label parent actuellement sélectionné"""
        root_label = self._get_current_root_label()
        if root_label:
            current_item = self.parent_list_widget.currentItem()
            if current_item:
                current_index = self.parent_list_widget.currentRow()
                parent_labels = root_label.get('parent_labels', [])
                if 0 <= current_index < len(parent_labels):
                    return parent_labels[current_index]
        return None

    def _get_current_child_label(self):
        """Retourne le label enfant actuellement sélectionné"""
        parent_label = self._get_current_parent_label()
        if parent_label:
            current_item = self.child_list_widget.currentItem()
            if current_item:
                current_index = self.child_list_widget.currentRow()
                child_labels = parent_label.get('child_labels', [])
                if 0 <= current_index < len(child_labels):
                    return child_labels[current_index]
        return None

    def _modify_category_for_selected_label(self, label_type):
        """Modification de la catégorie pour un label"""
        if label_type == "root":
            root_label = self._get_current_root_label()
            if not root_label:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("dataset_project_config.no_root_selected_title"),
                    tr("dataset_project_config.no_root_selected_msg")
                )
                return

            current_category = root_label.get('category', 'default')
            new_category, ok = QtWidgets.QInputDialog.getText(
                self,
                tr("dataset_project_config.modify_category_title"),
                tr("dataset_project_config.modify_category_text"),
                text=current_category
            )

            if ok and new_category:
                root_label['category'] = new_category.strip()
                logger.info(f"Catégorie du label racine '{root_label['name']}' modifiée en '{new_category}'")
                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

        elif label_type == "parent":
            parent_label = self._get_current_parent_label()
            if not parent_label:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.no_parent_selected_title"),
                    tr("project_config.no_parent_selected_msg")
                )
                return

            current_category = parent_label.get('category', 'default')
            new_category, ok = QtWidgets.QInputDialog.getText(
                self,
                tr("project_config.modify_category_title"),
                tr("project_config.modify_category_text"),
                text=current_category
            )

            if ok and new_category:
                parent_label['category'] = new_category.strip()
                logger.info(f"Catégorie du label parent '{parent_label['name']}' modifiée en '{new_category}'")
                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

        elif label_type == "child":
            child_label = self._get_current_child_label()
            if not child_label:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.no_child_selected_title"),
                    tr("project_config.no_child_selected_msg")
                )
                return

            current_category = child_label.get('category', 'default')
            new_category, ok = QtWidgets.QInputDialog.getText(
                self,
                tr("project_config.modify_category_title"),
                tr("project_config.modify_category_text"),
                text=current_category
            )

            if ok and new_category:
                child_label['category'] = new_category.strip()
                logger.info(f"Catégorie du label enfant '{child_label['name']}' modifiée en '{new_category}'")
                # Mettre à jour l'aperçu de la structure
                self._update_structure_preview()

    def _load_project_for_dataset_configuration(self):
        """Charge le projet dans l'onglet Dataset pour permettre la configuration"""
        if not self.current_project_profile_data:
            return

        # Initialiser les données pour l'onglet Dataset si nécessaire
        if not hasattr(self, 'data'):
            self.data = {'categories': []}

        # Convertir la structure de typologie en structure de catégories pour l'onglet Dataset
        categories = []

        typologies = self.current_project_profile_data.get('typologies', [])
        for typologie in typologies:
            # Créer une catégorie pour chaque typologie
            category = {
                'name': typologie.get('name', 'Typologie sans nom'),
                'subcategories': []
            }

            # Parcourir les labels racines
            root_labels = typologie.get('root_labels', [])
            for root_label in root_labels:
                # Créer une sous-catégorie pour chaque label racine
                subcategory = {
                    'name': root_label.get('name', 'Label racine sans nom'),
                    'themes': []
                }

                # Parcourir les labels parents
                parent_labels = root_label.get('parent_labels', [])
                for parent_label in parent_labels:
                    # Parcourir les labels enfants pour créer des thèmes
                    child_labels = parent_label.get('child_labels', [])
                    if child_labels:
                        for child_label in child_labels:
                            theme = {
                                'name': f"{parent_label.get('name', 'Parent')} → {child_label.get('name', 'Enfant')}",
                                'platform': 'ChatGPT',  # Plateforme par défaut
                                'description': '',
                                'output_format': 'JSON',
                                'sample_count': 100,
                                'training_technique': 'Full SFT'
                            }
                            subcategory['themes'].append(theme)
                    else:
                        # Si pas d'enfants, créer un thème pour le parent
                        theme = {
                            'name': parent_label.get('name', 'Parent sans enfant'),
                            'platform': 'ChatGPT',
                            'description': '',
                            'output_format': 'JSON',
                            'sample_count': 100,
                            'training_technique': 'Full SFT'
                        }
                        subcategory['themes'].append(theme)

                # Si pas de parents, créer au moins un thème par défaut
                if not parent_labels:
                    theme = {
                        'name': f"Thème par défaut - {root_label.get('name', 'Racine')}",
                        'platform': 'ChatGPT',
                        'description': '',
                        'output_format': 'JSON',
                        'sample_count': 100,
                        'training_technique': 'Full SFT'
                    }
                    subcategory['themes'].append(theme)

                category['subcategories'].append(subcategory)

            # Si pas de labels racines, créer au moins une sous-catégorie par défaut
            if not root_labels:
                subcategory = {
                    'name': 'Sous-catégorie par défaut',
                    'themes': [{
                        'name': 'Thème par défaut',
                        'platform': 'ChatGPT',
                        'description': '',
                        'output_format': 'JSON',
                        'sample_count': 100,
                        'training_technique': 'Full SFT'
                    }]
                }
                category['subcategories'].append(subcategory)

            categories.append(category)

        # Mettre à jour les données
        self.data['categories'] = categories

        # Charger les catégories dans l'interface Dataset (second fichier)
        if hasattr(self, '_load_categories'):
            self._load_categories()

        # Mettre à jour le graphique si disponible
        if hasattr(self, '_update_summary'):
            self._update_summary()

        logger.info(f"Projet '{self.current_project_name}' chargé pour configuration dans l'onglet Dataset")

    def load_existing_project(self, project_name):
        """Charge un projet existant depuis la base de données"""
        try:
            project_data = self.get_dataset_projet(project_name)

            if not project_data:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("project_config.project_not_found_title"),
                    tr("project_config.project_not_found_msg").format(project_name=project_name)
                )
                return False

            # Charger les données du projet
            self.current_project_name = project_name
            self.current_project_profile_data = project_data

            # Mettre à jour l'interface
            self.project_name_edit.setText(project_data.get('nom', project_name))
            self._refresh_typologie_list()

            # Mettre à jour l'aperçu de la structure
            self._update_structure_preview()

            # Activer les boutons
            self.save_button.setEnabled(True)
            self.delete_project_button.setEnabled(True)

            # Sélectionner la première typologie si disponible
            if self.typologie_list_widget.count() > 0:
                self.typologie_list_widget.setCurrentRow(0)

            # Mettre à jour la combo de preview
            self._refresh_preview_combo()
            if hasattr(self, 'preview_project_combo') and self.preview_project_combo is not None:
                self.preview_project_combo.setCurrentText(project_name)

            logger.info(f"Projet '{project_name}' chargé avec succès")
            return True

        except Exception as e:
            logger.error(f"Erreur lors du chargement du projet '{project_name}': {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                tr("project_config.load_error_title"),
                tr("project_config.load_error_msg").format(project_name=project_name, error=str(e))
            )
            return False

    def _update_structure_preview(self, project_data=None, show_config=True):
        # ✅ Sécurité : si l'UI n'est pas encore prête
        if not hasattr(self, "apercu_view") or self.apercu_view is None:
            return

        if project_data is None:
            project_data = self.current_project_profile_data
            show_config = True

        if not project_data:
            self.apercu_view.setHtml("""
                <div style='font-family: Arial, sans-serif; padding: 20px; text-align: center; color: #7f8c8d;'>
                    <h3>📋 Aucun projet chargé</h3>
                    <p>Créez ou chargez un projet pour voir sa structure.</p>
                </div>
            """)
            return

        project_name = project_data.get('nom', 'Unnamed')

        html = f"""
        <style>
            ul {{ list-style-type: none; padding-left: 20px; }}
            li {{ margin: 5px 0; }}
            .typologie {{ color: #27ae60; font-weight: bold; }}
            .root {{ color: #e74c3c; }}
            .parent {{ color: #3498db; }}
            .child {{ color: #f39c12; }}
            .category {{ color: #7f8c8d; font-size: 12px; font-style: italic; }}
        </style>
        <div style='font-family: Arial, sans-serif; padding: 15px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 8px;'>
            <h2 style='color: #2c3e50; margin-bottom: 20px; text-align: center; font-size: 20px;'>
                📊 Structure du Projet: {project_name}
            </h2>
        """

        html += f"""
            <div style='background: #ecf0f1; padding: 10px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #3498db;'>
                <p style='margin: 0; color: #34495e; font-style: italic;'><strong>Description:</strong> {project_data.get('description', '')}</p>
            </div>
        """

        total_themes = 0
        typologies = project_data.get('typologies', [])
        if typologies:
            html += f"<h3 style='color: #27ae60; margin-bottom: 10px; font-size: 16px;'>🏷️ Typologies ({len(typologies)})</h3><ul>"
            for typologie in typologies:
                typologie_name = typologie.get('name', 'Typologie sans nom')
                root_labels = typologie.get('root_labels', [])
                html += f"<li class='typologie'>📂 {typologie_name}"
                if root_labels:
                    html += "<ul>"
                    for root_label in root_labels:
                        root_name = root_label.get('name', 'Label racine sans nom')
                        category = root_label.get('category', 'default')
                        parent_labels = root_label.get('parent_labels', [])
                        html += f"<li class='root'>🔹 {root_name} <span class='category'>({category})</span>"
                        if parent_labels:
                            html += "<ul>"
                            for parent_label in parent_labels:
                                parent_name = parent_label.get('name', 'Parent sans nom')
                                parent_category = parent_label.get('category', 'default')
                                child_labels = parent_label.get('child_labels', [])
                                html += f"<li class='parent'>🔸 {parent_name} <span class='category'>({parent_category})</span>"
                                if child_labels:
                                    html += "<ul>"
                                    for child_label in child_labels:
                                        child_name = child_label.get('name', 'Enfant sans nom')
                                        child_category = child_label.get('category', 'default')
                                        total_themes += 1
                                        html += f"<li class='child'>🔻 {child_name} <span class='category'>({child_category})</span></li>"
                                    html += "</ul>"
                                else:
                                    total_themes += 1
                                html += "</li>"
                            html += "</ul>"
                        else:
                            total_themes += 1
                        html += "</li>"
                    html += "</ul>"
                else:
                    html += "<p style='color: #7f8c8d; font-style: italic; margin-left: 15px;'>Aucun label racine défini</p>"
                html += "</li>"
            html += "</ul>"

            html += f"""
            <div style='background: #e8f5e8; padding: 8px; border-radius: 4px; margin-bottom: 10px;'>
                <p style='margin: 0; color: #27ae60; font-weight: bold;'>📈 Total de thèmes potentiels: {total_themes}</p>
            </div>
            """
        else:
            html += """
            <div style='background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; text-align: center;'>
                <p style='color: #856404; margin: 0;'>⚠️ Aucune typologie définie</p>
            </div>
            """

        if show_config:
            html += f"""
            <div style='margin-top: 20px; padding: 10px; background: rgba(52, 73, 94, 0.1); border-radius: 5px;'>
                <h4 style='color: #2c3e50; margin: 0 0 10px 0; font-size: 14px;'>🛠️ Configuration</h4>
                <ul style='margin: 0; padding-left: 20px; color: #34495e; font-size: 13px;'>
                    <li><strong>Plateforme:</strong> {self.config_data['platform']}</li>
                    <li><strong>Description:</strong> {self.config_data['description'] or 'Aucune'}</li>
                    <li><strong>Format de sortie:</strong> {self.config_data['output_format']}</li>
                    <li><strong>Nombre d'échantillons:</strong> {self.config_data['sample_count']}</li>
                    <li><strong>Technique d'entraînement:</strong> {self.config_data['training_technique']}</li>
                </ul>
            </div>
            """

        html += "</div>"

        # ✅ Enfin, affichage si disponible
        if self.apercu_view:
            self.apercu_view.setHtml(html)

    def _export_project_strategy(self, project_name):
        """Exporte automatiquement la stratégie d'un projet vers un fichier JSON"""
        try:
            if not self.current_project_profile_data:
                logger.warning(f"Aucune donnée de projet pour '{project_name}' à exporter")
                return

            # Définir le chemin de fichier par défaut
            export_dir = os.path.join("exports")
            os.makedirs(export_dir, exist_ok=True)
            filename = os.path.join(export_dir, f"{project_name}_strategy.json")

            # Préparer les données à exporter
            export_data = {
                'project_info': self.current_project_profile_data,
                'export_timestamp': QtCore.QDateTime.currentDateTime().toString(Qt.ISODate)
            }

            # Exporter vers JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Stratégie du projet '{project_name}' exportée automatiquement vers : {filename}")

        except Exception as e:
            logger.error(f"Erreur lors de l'exportation automatique de la stratégie pour '{project_name}': {str(e)}")

    def _update_button_states(self):
        """Met à jour l'état des boutons selon les sélections"""
        # Typologie buttons
        typologie_selected = self.typologie_list_widget.currentItem() is not None
        self.edit_typologie_button.setEnabled(typologie_selected)
        self.remove_typologie_button.setEnabled(typologie_selected)

        # Root label buttons - nécessite une typologie sélectionnée
        root_selected = self.root_list_widget.currentItem() is not None
        self.add_root_button.setEnabled(typologie_selected)
        self.edit_root_button.setEnabled(root_selected)
        self.remove_root_button.setEnabled(root_selected)
        self.modify_category_root_button.setEnabled(root_selected)

        # Parent label buttons - nécessite un root sélectionné
        parent_selected = self.parent_list_widget.currentItem() is not None
        self.add_parent_button.setEnabled(root_selected)
        self.edit_parent_button.setEnabled(parent_selected)
        self.remove_parent_button.setEnabled(parent_selected)
        self.modify_category_parent_button.setEnabled(parent_selected)

        # Child label buttons - nécessite un parent sélectionné
        child_selected = self.child_list_widget.currentItem() is not None
        self.add_child_button.setEnabled(parent_selected)
        self.edit_child_button.setEnabled(child_selected)
        self.remove_child_button.setEnabled(child_selected)
        self.modify_category_child_button.setEnabled(child_selected)

        # Griser les listes si nécessaire
        self.root_list_widget.setEnabled(typologie_selected)
        self.parent_list_widget.setEnabled(root_selected)
        self.child_list_widget.setEnabled(parent_selected)

    def __del__(self):
        """Ferme la connexion à la base de données lors de la destruction de l'objet"""
        if hasattr(self, 'db_connection') and self.db_connection:
            self.db_connection.close()
            logger.info("Connexion à la base de données fermée")