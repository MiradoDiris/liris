#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/node_creation_widget.py
Widget pour la création de nœuds dans l'ontologie.
"""

import os
import uuid  # Pour générer des UUIDs pour les nœuds de fonction
import re  # Pour l'extraction des fonctions (si nécessaire, bien que l'IA le fasse)
import time  # Pour les délais dans l'automatisation du navigateur
import pyperclip  # Pour la gestion du presse-papiers
import json  # Pour json.dumps dans les scripts JS
import traceback  # Pour les traces d'erreurs détaillées

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    QTimer,
)  # QTimer pour les mises à jour non bloquantes de l'UI

# Importation du générateur de sélecteurs universel
from utils.selector_generator import UniversalSelectorGenerator
from utils.logger import logger  # Assurez-vous que logger est importé


# --- Nouvelle classe pour la fenêtre de résultats ---
class ResultsDialog(QtWidgets.QDialog):
    """
    Dialogue pour afficher les résultats de la génération de code de mutation.
    """

    def __init__(self, generated_mutations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Résultats")
        self.setMinimumSize(600, 400)
        self.generated_mutations = generated_mutations
        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        title_label = QtWidgets.QLabel("Codes de Mutation Générés")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin-bottom: 10px;"
        )
        main_layout.addWidget(title_label)

        # Zone de défilement pour les résultats par fichier
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QtWidgets.QWidget()
        self.results_layout = QtWidgets.QVBoxLayout(scroll_content_widget)
        self.results_layout.setAlignment(Qt.AlignTop)  # Align items to the top
        scroll_area.setWidget(scroll_content_widget)
        main_layout.addWidget(scroll_area)

        self._populate_results()

        # Bouton "Exécuter tout"
        execute_all_button = QtWidgets.QPushButton("Exécuter tout")
        execute_all_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        execute_all_button.clicked.connect(self._on_execute_all)
        main_layout.addWidget(execute_all_button, alignment=Qt.AlignCenter)

    def _populate_results(self):
        """Remplit la fenêtre de dialogue avec les résultats générés."""
        for result in self.generated_mutations:
            file_name = result.get("file_name", "Nom de fichier inconnu")
            mutation_code = result.get(
                "mutation_code", "Aucun code de mutation généré."
            )

            file_row_layout = QtWidgets.QHBoxLayout()
            file_row_layout.setSpacing(10)

            file_label = QtWidgets.QLabel(f"<b>Fichier:</b> {file_name}")
            file_label.setMinimumWidth(150)
            file_row_layout.addWidget(file_label)

            file_row_layout.addStretch()

            view_code_button = QtWidgets.QPushButton("Afficher le code")
            # Utilisation de functools.partial pour passer des arguments aux slots
            view_code_button.clicked.connect(
                lambda checked,
                code=mutation_code,
                name=file_name: self._show_code_dialog(code, name)
            )
            view_code_button.setStyleSheet("""
                QPushButton {
                    background-color: #17a2b8;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #138496;
                }
            """)
            file_row_layout.addWidget(view_code_button)

            execute_code_button = QtWidgets.QPushButton("Exécuter le code")
            execute_code_button.clicked.connect(
                lambda checked,
                code=mutation_code,
                name=file_name: self._on_execute_code(code, name)
            )
            execute_code_button.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """)
            file_row_layout.addWidget(execute_code_button)

            self.results_layout.addLayout(file_row_layout)

    def _show_code_dialog(self, code, file_name):
        """Affiche le code de mutation dans un nouveau dialogue."""
        code_dialog = QtWidgets.QDialog(self)
        code_dialog.setWindowTitle(f"Code de Mutation pour {file_name}")
        code_dialog.setMinimumSize(700, 500)

        layout = QtWidgets.QVBoxLayout(code_dialog)
        code_editor = QtWidgets.QTextEdit()
        code_editor.setReadOnly(True)
        code_editor.setPlainText(code)
        layout.addWidget(code_editor)

        close_button = QtWidgets.QPushButton("Fermer")
        close_button.clicked.connect(code_dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)

        code_dialog.exec_()

    def _on_execute_code(self, code, file_name):
        """Placeholder pour l'exécution du code de mutation d'un fichier."""
        logger.info(
            f"Action: Exécuter le code pour '{file_name}' (Code: {code[:50]}...)"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Exécuter le Code",
            f"L'exécution du code pour '{file_name}' n'est pas encore implémentée.",
        )

    def _on_execute_all(self):
        """Placeholder pour l'exécution de tous les codes de mutation."""
        logger.info("Action: Exécuter tous les codes de mutation.")
        QtWidgets.QMessageBox.information(
            self,
            "Exécuter Tout",
            "L'exécution de tous les codes n'est pas encore implémentée.",
        )


class NodeCreationWidget(QtWidgets.QWidget):
    """
    Widget pour la création de nœuds (clusters/labels) dans l'ontologie.
    """

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.current_project_files = []  # Pour stocker les fichiers (labels de type 'file') du projet sélectionné
        self.platforms = {}  # Pour stocker les profils des plateformes IA disponibles

        # Initialiser le générateur de sélecteurs universel
        self.selector_generator = UniversalSelectorGenerator()

        self._init_ui()
        self._populate_project_selection()  # Remplir la sélection de projets au démarrage
        self._populate_platform_selection()  # Remplir la sélection des plateformes IA au démarrage

    def _init_ui(self):
        """Initialise l'interface utilisateur du widget de création de nœuds."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # # Titre de l'onglet
        # title_label = QtWidgets.QLabel("Gestion des Nœuds d'Ontologie")
        # title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333333;")
        # main_layout.addWidget(title_label)

        # Section de sélection de projet
        project_selection_group = QtWidgets.QGroupBox("Sélection du Projet")
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
        project_selection_layout.addWidget(QtWidgets.QLabel("Projet :"))
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setMinimumWidth(250)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)
        project_selection_layout.addStretch()  # Pousser le combo vers la gauche
        main_layout.addWidget(project_selection_group)

        # Section d'affichage des fichiers et de filtrage
        files_section_group = QtWidgets.QGroupBox("Fichiers du Projet")
        files_section_layout = QtWidgets.QVBoxLayout(files_section_group)

        # Filtre de catégorie
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Filtrer par catégorie :"))
        self.category_filter_combo = QtWidgets.QComboBox()
        self.category_filter_combo.addItem("Tout")  # Option "Tout" par défaut
        self.category_filter_combo.setMinimumWidth(200)
        # Les autres catégories seront ajoutées dynamiquement après la sélection d'un projet
        self.category_filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.category_filter_combo)
        filter_layout.addStretch()
        files_section_layout.addLayout(filter_layout)

        # Liste des fichiers
        self.file_list_widget = QtWidgets.QListWidget()
        self.file_list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )  # Permettre la sélection multiple
        files_section_layout.addWidget(self.file_list_widget)
        main_layout.addWidget(files_section_group)

        # Section de sélection des plateformes IA
        platform_selection_group = QtWidgets.QGroupBox("Sélection des Plateformes IA")
        platform_selection_layout = QtWidgets.QVBoxLayout(platform_selection_group)
        self.platforms_list_widget = QtWidgets.QListWidget()
        self.platforms_list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.MultiSelection
        )
        self.platforms_list_widget.setMinimumHeight(80)
        platform_selection_layout.addWidget(self.platforms_list_widget)
        main_layout.addWidget(platform_selection_group)

        # Section de zone de logs (anciennement "Réponses des IA")
        log_group = QtWidgets.QGroupBox("Logs")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.response_area = (
            QtWidgets.QTextEdit()
        )  # Renommée pour refléter son rôle de log
        self.response_area.setReadOnly(True)
        self.response_area.setMinimumHeight(150)
        log_layout.addWidget(self.response_area)
        main_layout.addWidget(log_group)

        # Bouton de création
        self.proceed_button = QtWidgets.QPushButton("Procéder à la création")
        self.proceed_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
        """)
        self.proceed_button.clicked.connect(self._on_proceed_creation)
        self.proceed_button.setEnabled(False)  # Désactivé par défaut
        main_layout.addWidget(
            self.proceed_button, alignment=Qt.AlignCenter
        )  # Centrer le bouton

        self.setLayout(main_layout)

    def _debug_log(self, message):
        """Affiche les messages de débogage dans la console et dans la zone de logs."""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] DEBUG: {message}"
        print(log_message)
        self.response_area.append(log_message)
        QtWidgets.QApplication.processEvents()  # Mettre à jour l'UI

    def _populate_project_selection(self):
        """Remplit le QComboBox avec les noms des projets depuis la base de données."""
        self.project_combo.clear()
        self.project_combo.addItem("Sélectionner un projet...")  # Option par défaut

        if not self.conductor or not self.conductor.database:
            print("DEBUG: Conductor ou base de données non disponible.")
            self.project_combo.setEnabled(False)
            self.proceed_button.setEnabled(False)
            return

        try:
            project_profiles = self.conductor.database.get_all_project_profiles()
            if not project_profiles:
                self.project_combo.addItem("Aucun projet disponible")
                self.project_combo.setEnabled(False)
                self.proceed_button.setEnabled(False)
                return

            for project_name in sorted(project_profiles.keys()):
                self.project_combo.addItem(project_name)

            self.project_combo.setEnabled(True)
            # Le bouton Procéder sera activé par _on_project_selected si un projet valide est choisi
            # self.proceed_button.setEnabled(True)

            # Sélectionner le premier projet par défaut si disponible (après l'option "Sélectionner...")
            if self.project_combo.count() > 1:
                self.project_combo.setCurrentIndex(
                    1
                )  # Sélectionne le premier vrai projet
                # _on_project_selected sera appelé automatiquement
            else:
                self._on_project_selected(
                    0
                )  # Appel manuel si un seul élément (l'option par défaut)

        except Exception as e:
            print(
                f"Erreur lors du chargement des projets depuis la base de données: {e}"
            )
            self.project_combo.addItem("Erreur de chargement des projets")
            self.project_combo.setEnabled(False)
            self.proceed_button.setEnabled(False)

    def _populate_platform_selection(self):
        """Remplit le QListWidget avec les plateformes IA disponibles."""
        self.platforms_list_widget.clear()
        if not self.conductor:
            print("DEBUG: Conductor non disponible pour les plateformes IA.")
            self.platforms_list_widget.addItem("Conductor non disponible.")
            self.platforms_list_widget.setEnabled(False)
            return

        try:
            self.platforms = self.conductor.database.get_all_platforms()

            if not self.platforms:
                self.platforms_list_widget.addItem("Aucune plateforme IA disponible.")
                self.platforms_list_widget.setEnabled(False)
                return

            for platform_name in sorted(self.platforms.keys()):
                item = QtWidgets.QListWidgetItem(platform_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                item.setCheckState(Qt.Unchecked)  # Décoché par défaut
                self.platforms_list_widget.addItem(item)
            self.platforms_list_widget.setEnabled(True)

        except Exception as e:
            print(f"Erreur lors du chargement des plateformes IA: {e}")
            self.platforms_list_widget.addItem("Erreur de chargement des plateformes.")
            self.platforms_list_widget.setEnabled(False)

    def _on_project_selected(self, index):
        """
        Gère la sélection d'un projet dans le QComboBox.
        Affiche les fichiers du projet sélectionné et met à jour les catégories de filtre.
        """
        self.file_list_widget.clear()
        self.current_project_files = []  # Réinitialiser la liste des fichiers
        self.category_filter_combo.clear()
        self.category_filter_combo.addItem("Tout")  # Toujours ajouter "Tout"

        selected_project_name = self.project_combo.currentText()

        if (
            index == 0
            or not selected_project_name
            or not self.conductor
            or not self.conductor.database
        ):
            # "Sélectionner un projet..." ou aucun projet valide sélectionné
            self.file_list_widget.addItem("Veuillez sélectionner un projet.")
            self.proceed_button.setEnabled(False)
            return

        print(f"DEBUG: Projet sélectionné : {selected_project_name}")
        self.proceed_button.setEnabled(
            True
        )  # Activer le bouton si un projet valide est sélectionné

        try:
            project_profile_data = self.conductor.database.get_project_profile(
                selected_project_name
            )
            if project_profile_data:
                turing_ontology = project_profile_data.get("turing_ontology", {})
                clusters_detailed = turing_ontology.get("clusters_detailed", [])

                # Collecter tous les fichiers et leurs catégories
                unique_categories = set()
                self.current_project_files = []  # Clear before re-populating

                for cluster_data in clusters_detailed:
                    cluster_id = cluster_data.get("id")  # Récupérer l'ID du cluster
                    # Passer l'ID du cluster aux appels récursifs
                    self._collect_files_from_ontology(
                        cluster_data.get("root_labels", []),
                        unique_categories,
                        cluster_id,
                    )

                # Ajouter les catégories uniques au filtre
                for category in sorted(list(unique_categories)):
                    self.category_filter_combo.addItem(category)

                self._apply_filter()  # Appliquer le filtre initial après chargement des fichiers
            else:
                self.file_list_widget.addItem(
                    "Aucune donnée d'ontologie trouvée pour ce projet."
                )

        except Exception as e:
            print(
                f"Erreur lors du chargement des données d'ontologie pour le projet {selected_project_name}: {e}"
            )
            self.file_list_widget.addItem(f"Erreur de chargement des fichiers: {e}")

    def _collect_files_from_ontology(
        self, nodes_list, unique_categories_set, current_cluster_id=None
    ):
        """
        Collecte récursivement tous les nœuds de fichier de la structure d'ontologie et leurs catégories,
        ainsi que leur full_path, ID et l'ID du cluster conteneur.
        nodes_list: Une liste de dictionnaires représentant les labels (racines, parents, enfants).
        unique_categories_set: Un ensemble pour collecter toutes les catégories uniques trouvées.
        current_cluster_id: L'ID du cluster en cours de traitement.
        """
        if not nodes_list:
            return

        for node in nodes_list:
            node_id = node.get("id")  # Récupérer l'ID du nœud (label)
            node_full_path = node.get(
                "full_path"
            )  # Récupérer le chemin complet du nœud

            if node.get("type") == "file":
                file_name = node.get("name", "N/A")
                file_categories = node.get(
                    "category", []
                )  # category est une liste de chaînes
                print(
                    f"DEBUG: Traitement du fichier: {file_name}, ID: {node_id}, Cluster ID: {current_cluster_id}, Catégories: {file_categories}"
                )

                # S'assurer que full_path, id et cluster_id sont stockés
                self.current_project_files.append(
                    {
                        "name": file_name,
                        "category": file_categories,
                        "full_path": node_full_path,  # Stocker le chemin réel du fichier
                        "id": node_id,  # Stocker l'UUID du label (fichier)
                        "cluster_id": current_cluster_id,  # Stocker l'UUID du cluster parent
                    }
                )
                for cat in file_categories:
                    if cat:
                        unique_categories_set.add(cat)

            # Récursion dans parent_labels (enfants de la racine)
            if "parent_labels" in node and isinstance(node["parent_labels"], list):
                self._collect_files_from_ontology(
                    node["parent_labels"], unique_categories_set, current_cluster_id
                )
                print(f"DEBUG: Parent labels: {node['parent_labels']}")

            # Récursion dans child_labels (enfants du parent)
            if "child_labels" in node and isinstance(node["child_labels"], list):
                self._collect_files_from_ontology(
                    node["child_labels"], unique_categories_set, current_cluster_id
                )
                print(f"DEBUG: Child labels: {node['child_labels']}")

    def _apply_filter(self):
        """Applique le filtre de catégorie aux fichiers affichés."""
        self.file_list_widget.clear()
        selected_category_filter = self.category_filter_combo.currentText()

        # Define non-development file extensions
        NOT_DEV_FILE_EXTENSIONS = {
            # Image formats
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
            ".ico",
            ".psd",
            # Video formats
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".flv",
            ".wmv",
            ".mpeg",
            ".mpg",
            ".3gp",
            ".webm",
            # Document formats
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".odt",
            ".ods",
            ".odp",
            # Audio formats
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",
            ".wma",
            # Archive formats
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            # Other binaries
            ".exe",
            ".dll",
            ".so",
            ".bin",
            ".dat",
        }

        if not self.current_project_files:
            self.file_list_widget.addItem("Aucun fichier à afficher.")
            return

        filtered_files = []
        for file_info in self.current_project_files:
            # Vérifier l'extension du fichier
            file_name = file_info["name"]
            file_extension = os.path.splitext(file_name)[1].lower()

            # Exclure les fichiers non-dev
            if file_extension in NOT_DEV_FILE_EXTENSIONS:
                continue  # Ignorer ce fichier

            file_categories = file_info.get("category", [])  # C'est une liste

            if selected_category_filter == "Tout":
                filtered_files.append(file_info)
            else:
                # Vérifier si la catégorie sélectionnée est présente dans la liste des catégories du fichier
                if selected_category_filter in file_categories:
                    filtered_files.append(file_info)

        if not filtered_files:
            self.file_list_widget.addItem("Aucun fichier correspondant au filtre.")
        else:
            for file_info in filtered_files:
                # Afficher le nom et les catégories pour plus de clarté
                categories_str = ", ".join(file_info.get("category", []))
                item_text = f"{file_info['name']} (Catégories: {categories_str if categories_str else 'N/A'})"
                self.file_list_widget.addItem(item_text)

    def _on_proceed_creation(self):
        """
        Action pour le bouton "Procéder à la création".
        Lit les fichiers sélectionnés, crée des prompts pour l'IA, les envoie,
        et affiche les réponses extraites dans une nouvelle fenêtre de résultats.
        """
        self._debug_log("🎯 DÉBUT DU PROCESSUS DE CRÉATION DE NŒUDS DE FONCTION")
        self.response_area.clear()  # Effacer les logs précédents
        self.proceed_button.setEnabled(
            False
        )  # Désactiver le bouton pendant le traitement
        QtWidgets.QApplication.processEvents()  # Mettre à jour l'UI

        start_time = time.time()

        selected_file_items = self.file_list_widget.selectedItems()
        if not selected_file_items:
            QtWidgets.QMessageBox.warning(
                self,
                "Sélection de Fichier",
                "Veuillez sélectionner au moins un fichier dans la liste.",
            )
            self.proceed_button.setEnabled(True)
            return

        selected_files_info = []
        for item in selected_file_items:
            selected_file_display_text = item.text()
            for file_info in self.current_project_files:
                categories_str = ", ".join(file_info.get("category", []))
                item_text_for_comparison = f"{file_info['name']} (Catégories: {categories_str if categories_str else 'N/A'})"
                if item_text_for_comparison == selected_file_display_text:
                    selected_files_info.append(file_info)
                    break

        if not selected_files_info:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de Fichier",
                "Impossible de trouver les informations détaillées pour les fichiers sélectionnés.",
            )
            self.proceed_button.setEnabled(True)
            return

        # 3. Obtenir les plateformes IA sélectionnées
        selected_platforms_profiles = []
        for i in range(self.platforms_list_widget.count()):
            item = self.platforms_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                platform_name = item.text()
                if platform_name in self.platforms:
                    selected_platforms_profiles.append(self.platforms[platform_name])
                else:
                    self._debug_log(
                        f"WARNING: La plateforme '{platform_name}' n'a pas été trouvée parmi les profils disponibles."
                    )

        if not selected_platforms_profiles:
            QtWidgets.QMessageBox.warning(
                self,
                "Sélection de Plateforme",
                "Veuillez sélectionner au moins une plateforme IA à utiliser.",
            )
            self.proceed_button.setEnabled(True)
            return

        generated_mutations_results = []  # Pour stocker les résultats de chaque fichier

        for file_info in selected_files_info:
            file_name = file_info.get("name")
            file_path = file_info.get("full_path")
            file_label_id = file_info.get("id")
            file_cluster_id = file_info.get("cluster_id")

            self._debug_log(f"\n--- Traitement du fichier: {file_name} ---")

            if not file_path or not os.path.exists(file_path):
                self._debug_log(
                    f"❌ Le chemin du fichier '{file_name}' est invalide ou le fichier n'existe pas: {file_path}"
                )
                generated_mutations_results.append(
                    {
                        "file_name": file_name,
                        "mutation_code": f"Erreur: Fichier introuvable ou chemin invalide: {file_path}",
                    }
                )
                continue

            # 2. Lire le contenu du fichier
            self._debug_log(f"Lecture du contenu du fichier '{file_name}'...")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                self._debug_log(f"Contenu du fichier '{file_name}' lu avec succès.")
            except Exception as e:
                self._debug_log(f"❌ Impossible de lire le fichier '{file_name}': {e}")
                generated_mutations_results.append(
                    {
                        "file_name": file_name,
                        "mutation_code": f"Erreur de lecture du fichier: {e}",
                    }
                )
                continue

            # 4. Construire le prompt pour l'IA
            prompt_template = """
Étant donné le script de code suivant, décomposez toutes ses fonctions. Pour chaque fonction, créez un script de mutation Dgraph (en utilisant la syntaxe du client pydgraph) pour ajouter un 'Node' représentant la fonction.

Le schéma Dgraph pour 'Node' est :
type Node {{
    id: String! @id
    title: String @index(fulltext, term)
    content: String
    clusterIds: [String] @index(hash)
    labelIds: [String] @index(hash)
    properties: [Property]
    userID: String @index(term)
    createdAt: String
    updatedAt: String
    metadata: Metadata
}}

Pour chaque nœud de fonction :
- 'Node.id' doit être un nouvel UUID unique (par exemple, `str(uuid.uuid4())`).
- 'Node.title' doit être le nom de la fonction.
- 'Node.content' doit être le code complet de la fonction.
- 'Node.labelIds' doit être une liste contenant l'ID du nœud Label du fichier parent. L'ID du Label du fichier est '{file_label_id}'.
- 'Node.clusterIds' doit être une liste contenant l'ID du nœud Cluster conteneur. L'ID du Cluster est '{file_cluster_id}'.
- 'Node.userID' doit être un UUID de remplacement (par exemple, "47ea051e-8cce-4bee-bfe8-76489dd98b60").
- 'Node.createdAt' et 'Node.updatedAt' doivent être des horodatages ISO actuels (par exemple, `datetime.now().isoformat() + "Z"`).

Voici le script à analyser :

```code
{file_content}
```

Assurez-vous que le script de mutation est complet et exécutable, y compris les importations nécessaires (pydgraph, json, datetime, uuid, logging) et la configuration du client. Ne pas inclure la fonction `main()` ou la fonction `insert_hierarchy`. Fournissez uniquement la fonction `generate_function_mutations` et son appel, ainsi que la configuration du client Dgraph.
"""
            full_prompt = prompt_template.format(
                file_content=file_content,
                file_label_id=file_label_id,
                file_cluster_id=file_cluster_id,
            )

            self._debug_log(f"--- Envoi du prompt pour {file_name} aux IAs ---")

            # 5. Envoyer le prompt aux IAs sélectionnées
            for platform_profile in selected_platforms_profiles:
                platform_name = platform_profile.get("name", "Unknown Platform")
                browser_type = platform_profile.get("browser", {}).get("type", "Chrome")

                self._debug_log(
                    f"\n--- Traitement avec {platform_name} pour {file_name} ---"
                )

                try:
                    # ÉTAPE 1: Validation configuration (simplifiée pour l'UI)
                    window_position = platform_profile.get("window_position")
                    prompt_field = platform_profile.get("interface_positions", {}).get(
                        "prompt_field"
                    )
                    extraction_config = platform_profile.get("extraction_config", {})
                    detection_config = platform_profile.get("detection_config", {})
                    send_keys_config = platform_profile.get("keyboard", {}).get(
                        "send_keys_config", {}
                    )

                    if (
                        not window_position
                        or "x" not in window_position
                        or "y" not in window_position
                    ):
                        self._debug_log(
                            f"  ❌ Configuration incomplète pour {platform_name}: window_position invalide."
                        )
                        continue  # Passer à la plateforme suivante
                    if (
                        not prompt_field
                        or "center_x" not in prompt_field
                        or "center_y" not in prompt_field
                    ):
                        self._debug_log(
                            f"  ❌ Configuration incomplète pour {platform_name}: prompt_field invalide."
                        )
                        continue  # Passer à la plateforme suivante

                    # ÉTAPE 2: Clic icône fenêtre et ouverture URL
                    self._debug_log(
                        f"  - Clic icône fenêtre et ouverture URL pour {platform_name}..."
                    )
                    try:
                        x, y = window_position["x"], window_position["y"]
                        self._debug_log(f"Clic sur position: ({x}, {y})")
                        self.conductor.mouse_controller.click(x, y)
                        time.sleep(0.5)
                        self._debug_log("Clic icône réussi")
                        QtWidgets.QApplication.processEvents()

                        # Ouverture URL de la plateforme
                        browser_config = platform_profile.get("browser", {})
                        platform_url = browser_config.get("url", "")
                        if platform_url:
                            self._debug_log(f"Ouverture URL plateforme: {platform_url}")
                            result = self.conductor.browser_manager.open_url(
                                platform_url, browser_type, new_window=False
                            )  # Use browser_type here
                            if result.get("success"):
                                time.sleep(4)  # Attendre chargement page
                                self._debug_log("URL ouverte avec succès")
                            else:
                                self._debug_log(
                                    f"⚠️ Échec ouverture URL: {result.get('error', 'Erreur inconnue')}"
                                )
                        else:
                            self._debug_log("⚠️ Aucune URL configurée")

                        self._debug_log(f"  ✅ Navigateur prêt pour {platform_name}.")
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur lors de la préparation du navigateur pour {platform_name}: {e}"
                        )
                        continue

                    # ÉTAPE 3: Clic champ de saisie
                    self._debug_log(
                        f"  - Clic sur le champ de saisie pour {platform_name}..."
                    )
                    try:
                        x, y = prompt_field["center_x"], prompt_field["center_y"]
                        self.conductor.mouse_controller.click(x, y)
                        time.sleep(0.3)
                        QtWidgets.QApplication.processEvents()
                        self._debug_log(f"  ✅ Clic champ de saisie réussi.")
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur clic champ de saisie pour {platform_name}: {e}"
                        )
                        continue

                    # ÉTAPE 4: Nettoyage champ
                    self._debug_log(
                        f"  - Nettoyage du champ de saisie pour {platform_name}..."
                    )
                    try:
                        self.conductor.keyboard_controller.hotkey("ctrl", "a")
                        time.sleep(0.1)
                        self.conductor.keyboard_controller.press_key("delete")
                        time.sleep(0.1)
                        QtWidgets.QApplication.processEvents()
                        self._debug_log(f"  ✅ Nettoyage champ réussi.")
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur nettoyage champ pour {platform_name}: {e}"
                        )
                        continue

                    # ÉTAPE 5: Saisie texte
                    self._debug_log(f"  - Saisie du prompt pour {platform_name}...")
                    try:
                        original_clipboard = pyperclip.paste()
                        pyperclip.copy(full_prompt)
                        time.sleep(0.05)
                        self.conductor.keyboard_controller.hotkey("ctrl", "v")
                        time.sleep(0.3)
                        pyperclip.copy(original_clipboard)
                        QtWidgets.QApplication.processEvents()
                        self._debug_log(f"  ✅ Saisie du prompt réussie.")
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur saisie texte pour {platform_name}: {e}"
                        )
                        continue

                    # ÉTAPE 6: Envoi formulaire
                    self._debug_log(f"  - Envoi du prompt pour {platform_name}...")
                    try:
                        if send_keys_config.get("ctrl_enter_for_send", False):
                            self.conductor.keyboard_controller.hotkey("ctrl", "enter")
                        else:
                            self.conductor.keyboard_controller.press_key("enter")
                        time.sleep(2)
                        QtWidgets.QApplication.processEvents()
                        self._debug_log(f"  ✅ Envoi du formulaire réussi.")
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur envoi formulaire pour {platform_name}: {e}"
                        )
                        continue

                    # ÉTAPE 7: Attente réponse avec DÉTECTION UNIVERSELLE
                    self._debug_log(
                        f"  - Attente de la fin de génération de réponse pour {platform_name}..."
                    )
                    response_completed = False
                    try:
                        response_completed = self._wait_for_ai_completion(
                            detection_config, platform_profile, browser_type
                        )
                        if response_completed:
                            self._debug_log(
                                f"  ✅ Détection de fin de génération réussie pour {platform_name}."
                            )
                        else:
                            self._debug_log(
                                f"  ⚠️ Timeout de détection pour {platform_name}. La réponse pourrait être incomplète."
                            )
                    except Exception as e:
                        self._debug_log(
                            f"  ❌ Erreur lors de la détection de réponse pour {platform_name}: {e}"
                        )
                        print(traceback.format_exc())

                    # ÉTAPE 8: Extraction réponse avec EXTRACTION UNIVERSELLE
                    self._debug_log(
                        f"  - Extraction de la réponse pour {platform_name}..."
                    )
                    ai_response_text = "Aucune réponse extraite."
                    try:
                        extracted_text = self._extract_response_universal(
                            extraction_config, platform_profile, browser_type
                        )
                        if extracted_text:
                            ai_response_text = extracted_text
                        else:
                            ai_response_text = "Réponse extraite, mais vide."
                        self._debug_log(
                            f"  ✅ Extraction de la réponse réussie pour {platform_name}."
                        )
                    except Exception as e:
                        ai_response_text = (
                            f"Erreur lors de l'extraction de la réponse: {e}"
                        )
                        self._debug_log(f"  ❌ {ai_response_text}")
                        print(traceback.format_exc())

                    # Collecter le résultat
                    generated_mutations_results.append(
                        {"file_name": file_name, "mutation_code": ai_response_text}
                    )

                except Exception as e:
                    error_msg = f"Erreur inattendue lors du traitement de {platform_name} pour {file_name}: {e}"
                    self._debug_log(f"Erreur: {error_msg}\n")
                    print(traceback.format_exc())
                    generated_mutations_results.append(
                        {
                            "file_name": file_name,
                            "mutation_code": f"Erreur lors du traitement: {error_msg}",
                        }
                    )

                QtWidgets.QApplication.processEvents()

        self._debug_log("\n--- Traitement terminé ---")

        # Afficher la fenêtre de résultats
        if generated_mutations_results:
            results_dialog = ResultsDialog(generated_mutations_results, self)
            results_dialog.exec_()

        self.proceed_button.setEnabled(True)  # Réactiver le bouton
        duration = time.time() - start_time
        self._debug_log(f"Processus complet terminé en {duration:.2f} secondes.")

    def _wait_for_ai_completion(
        self, detection_config, platform_profile, detected_browser_type
    ):
        """VERSION AMÉLIORÉE avec générateur universel"""
        try:
            if not detection_config:
                self._debug_log("⚠️ Pas de config détection - attente fallback 8s")
                time.sleep(8)
                return True

            # 🎯 NOUVEAU : Utilisation du générateur universel pour les scripts
            universal_config = detection_config.get("universal_config")
            if universal_config:
                self._debug_log(
                    f"🎯 Utilisation détection universelle pour {universal_config['platform']}"
                )
                js_code = self.selector_generator.generate_detection_script(
                    universal_config
                )
                self._debug_log("📜 Script de détection universel généré")
            else:
                # Fallback vers les scripts spécialisés existants
                platform_type = detection_config.get("platform_type", "").lower()
                self._debug_log(f"🔄 Fallback scripts spécialisés pour {platform_type}")
                if "chatgpt" in platform_type:
                    js_code = self._get_chatgpt_detection_script()
                elif "gemini" in platform_type:
                    js_code = self._get_gemini_detection_script()
                elif "claude" in platform_type:
                    js_code = self._get_claude_detection_script()
                else:
                    primary_selector = detection_config.get("primary_selector", "div")
                    js_code = self._get_generic_detection_script(primary_selector)

            # Focus fenêtre avant détection
            window_position = platform_profile.get("window_position", {})
            if window_position:
                self._debug_log(
                    f"Focus fenêtre avant détection: ({window_position['x']}, {window_position['y']})"
                )
                self.conductor.mouse_controller.click(
                    window_position["x"], window_position["y"]
                )
                time.sleep(0.2)

            return self._execute_detection_script(
                js_code, platform_profile, detected_browser_type
            )

        except Exception as e:
            self._debug_log(f"❌ Erreur _wait_for_ai_completion: {e}")
            logger.error(f"Erreur détection IA: {e}")
            time.sleep(6)
            return False

    def _get_chatgpt_detection_script(self):
        """Ancienne méthode ChatGPT en fallback"""
        return """
        (function() {
            let lastDataState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            // Store result in global variable AND console log
            function setDetectionResult(result) {
                window.LIRIS_DETECTION_RESULT = result;
                console.log("LIRIS_DETECTION_COMPLETE:" + result);
                console.log("Detection result stored in window.LIRIS_DETECTION_RESULT");
            }
            
            function checkDataStability() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        setDetectionResult("timeout");
                        return;
                    }
                    
                    let elements = document.querySelectorAll('[data-start][data-end]');
                    let currentState = '';
                    elements.forEach(el => {
                        let start = el.getAttribute('data-start') || '';
                        let end = el.getAttribute('data-end') || '';
                        currentState += start + ':' + end + ';';
                    });
                    
                    if (currentState === lastDataState && currentState.length > 0) {
                        stableCount++;
                        if (stableCount >= 3) {
                            setDetectionResult("success");
                            return;
                        }
                    } else {
                        lastDataState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkDataStability, 300);
                } catch(e) {
                    setDetectionResult("error");
                }
            }
            
            // Initialize detection result
            window.LIRIS_DETECTION_RESULT = "running";
            checkDataStability();
            return "ChatGPT detection started";
        })();
        """

    def _get_gemini_detection_script(self):
        """Ancienne méthode Gemini en fallback"""
        return """
        (function() {
            let lastContentState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            function checkGeminiCompletion() {
                try {
                    checkCount++;
                    console.log("Gemini check #" + checkCount);
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
                        return;
                    }
                    
                    let generatingDiv = document.querySelector('[class*="_ngcontent-ng-c2459883256"]');
                    let completedDiv = document.querySelector('[class*="_ngcontent-ng-c1375136285"]');
                    
                    console.log("Generating div found:", !!generatingDiv);
                    console.log("Completed div found:", !!completedDiv);
                    
                    let currentState = (generatingDiv ? 'generating' : '') + (completedDiv ? 'completed' : '');
                    
                    if (currentState === lastContentState && completedDiv) {
                        stableCount++;
                        console.log("Stable count:", stableCount);
                        if (stableCount >= 2) {
                            console.log("LIRIS_DETECTION_COMPLETE:success");
                            return;
                        }
                    } else {
                        lastContentState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkGeminiCompletion, 400);
                } catch(e) {
                    console.log("Error in Gemini detection:", e);
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }
            }

            checkGeminiCompletion();
            return "Gemini detection started";
        })();
        """

    def _get_claude_detection_script(self):
        """Ancienne méthode Claude en fallback"""
        return """
        (function() {
            let checkCount = 0;
            let maxChecks = 1000;
        
            // Store result in global variable AND console log
            function setDetectionResult(result) {
                window.LIRIS_DETECTION_RESULT = result;
                console.log("LIRIS_DETECTION_COMPLETE:" + result);
                console.log("Detection result stored in window.LIRIS_DETECTION_RESULT");
            }
        
            function checkClaudeCompletion() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        setDetectionResult("timeout");
                        return;
                    }
                
                    let streamingElements = document.querySelectorAll('[data-is-streaming="true"]');
                    let completedElements = document.querySelectorAll('[data-is-streaming="false"]');
                
                    if (streamingElements.length === 0 && completedElements.length > 0) {
                        setDetectionResult("success");
                        return;
                    }
                
                    setTimeout(checkClaudeCompletion, 300);
                } catch(e) {
                    setDetectionResult("error");
                }
            }
        
            // Initialize detection result
            window.LIRIS_DETECTION_RESULT = "running";
            checkClaudeCompletion();
            return "Claude detection started";
        })();
        """

    def _get_generic_detection_script(self, selector):
        """Ancienne méthode générique en fallback"""
        return f'''
        (function() {{
            let lastText = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            function checkTextStability() {{
                try {{
                    checkCount++;
                    console.log("Generic check #" + checkCount + " with selector: {selector}");
                    
                    if (checkCount > maxChecks) {{
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
                        return;
                    }}
                    
                    let element = document.querySelector("{selector}");
                    console.log("Element found:", !!element);
                    
                    let currentText = element ? (element.textContent || '').trim() : '';
                    console.log("Current text length:", currentText.length);
                    
                    if (currentText === lastText && currentText.length > 30) {{
                        stableCount++;
                        console.log("Stable count:", stableCount);
                        if (stableCount >= 3) {{
                            console.log("LIRIS_DETECTION_COMPLETE:success");
                            return;
                        }}
                    }} else {{
                        lastText = currentText;
                        stableCount = 0;
                    }}
                    
                    setTimeout(checkTextStability, 500);
                }} catch(e) {{
                    console.log("Error in generic detection:", e);
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }}
            }}

            checkTextStability();
            return "Generic detection started";
        }})();
        '''

    def _execute_detection_script(
        self, js_code, platform_profile, detected_browser_type
    ):
        """Exécute le script de détection et surveille les résultats"""
        try:
            self._debug_log(f"🖥️ Ouverture console ({detected_browser_type})")

            if detected_browser_type == "firefox":
                self.conductor.keyboard_controller.hotkey("ctrl", "shift", "k")
            else:
                self.conductor.keyboard_controller.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            self._debug_log("🔐 Activation du collage")
            try:
                # Type 'allow pasting' to enable pasting in browser console
                self.conductor.keyboard_controller.type_text("allow pasting")
                self.conductor.keyboard_controller.press_key("enter")
                time.sleep(1)  # Wait for browser to process the allow pasting command
                self._debug_log("✅ Collage autorisé")
            except Exception as e:
                self._debug_log(f"⚠️ Erreur activation collage: {e}")

            self._debug_log("🧹 Nettoyage console")
            pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.2)

            self._debug_log("💉 Injection script de détection")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.5)

            max_wait = 80
            waited = 0
            check_interval = 0.5

            self._debug_log(
                f"👀 Surveillance console (max {max_wait}s, check chaque {check_interval}s)"
            )

            while waited < max_wait:  # Removed self.should_stop
                try:
                    check_script = (
                        "console.log('STATUS_CHECK:' + window.LIRIS_DETECTION_RESULT);"
                    )

                    pyperclip.copy(check_script)
                    self.conductor.keyboard_controller.hotkey("ctrl", "v")
                    self.conductor.keyboard_controller.press_key("enter")
                    time.sleep(0.2)

                    result_copy_script = """
                    if (window.LIRIS_DETECTION_RESULT) {
                        copy('RESULT:' + window.LIRIS_DETECTION_RESULT);
                    } else {
                        copy('RESULT:not_set');
                    }
                    """

                    pyperclip.copy(result_copy_script)
                    self.conductor.keyboard_controller.hotkey("ctrl", "v")
                    self.conductor.keyboard_controller.press_key("enter")
                    time.sleep(0.3)

                    result_content = pyperclip.paste().strip()

                    self._debug_log(f"Detection result: {result_content}")

                    if result_content.startswith("RESULT:"):
                        status = result_content.replace("RESULT:", "").strip()

                        if status == "success":
                            self._debug_log(f"✅ Détection réussie après {waited:.1f}s")
                            logger.info(f"✅ Détection réussie après {waited:.1f}s")
                            return True
                        elif status == "running":
                            pass  # Continue waiting
                        elif status == "timeout":
                            self._debug_log(f"⏱️ Détection timeout après {waited:.1f}s")
                            logger.warning(f"⏱️ Détection timeout après {waited:.1f}s")
                            return False
                        else:
                            self._debug_log(f"❌ Détection erreur: {status}")
                            logger.error(f"❌ Détection erreur: {status}")
                            return False

                except Exception as e:
                    self._debug_log(f"❌ Erreur vérification statut: {e}")

                time.sleep(check_interval)
                waited += check_interval

                if waited % 2 == 0:
                    self._debug_log(
                        f"⏳ Attente détection... {waited:.1f}s/{max_wait}s"
                    )

            self._debug_log(f"⏱️ Timeout global détection après {waited:.1f}s")
            logger.warning(f"⏱️ Timeout global détection après {waited:.1f}s")
            return False

        except Exception as e:
            self._debug_log(f"❌ Erreur exécution détection: {e}")
            logger.error(f"❌ Erreur exécution détection: {e}")
            return False

    def _extract_response_universal(
        self, extraction_config, platform_profile, detected_browser_type
    ):
        """VERSION UNIVERSELLE avec sélecteurs automatiques et stratégie de bouton de copie."""
        try:
            self._debug_log("🎯 Début extraction réponse universelle")

            response_area = extraction_config.get("response_area", {})
            universal_config = response_area.get("universal_config")

            primary_selector = "p:last-child"
            fallback_selectors = []
            cleaning_method = "basic_text_extraction"
            platform = "legacy"

            if universal_config:
                self._debug_log("🎯 Utilisation extraction universelle")
                extraction_selectors = universal_config["extraction"]
                primary_selector = extraction_selectors["primary_selector"]
                fallback_selectors = extraction_selectors.get("fallback_selectors", [])
                cleaning_method = extraction_selectors.get(
                    "text_cleaning", "basic_text_extraction"
                )
                platform = universal_config.get("platform", "unknown")
            else:
                self._debug_log("🔄 Fallback extraction classique")
                platform_config = response_area.get("platform_config", {})
                primary_selector = platform_config.get(
                    "primary_selector", "p:last-child"
                )
                fallback_selectors = platform_config.get("fallback_selectors", [])
                cleaning_method = "basic_text_extraction"  # Default for legacy
                platform = "legacy"

            self._debug_log(f"Primary selector: {primary_selector}")
            self._debug_log(f"Fallback selectors: {fallback_selectors}")

            # Focus fenêtre avant extraction (déjà présent, mais ajouté pour clarté)
            window_position = platform_profile.get("window_position", {})
            if window_position:
                self._debug_log(
                    f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})"
                )
                self.conductor.mouse_controller.click(
                    window_position["x"], window_position["y"]
                )
                time.sleep(0.2)  # Petite pause pour s'assurer que le focus est pris

            selectors = [primary_selector] + fallback_selectors[:3]
            self._debug_log(f"Sélecteurs à tester: {selectors}")

            # Le script JS est maintenant une fonction asynchrone qui retourne le texte
            js_code = f"""
            let selectors = {json.dumps(selectors)};
            let cleaningMethod = "basic_text_extraction";
            let platform = "legacy";

            // Define classes to be excluded from text content
            const excludedClasses = ["pt-3", "pb-3"]; // Add any other classes you want to exclude

            console.log("🎯 Testing universal selectors for " + platform + ":", selectors);
            console.log("🧹 Cleaning method:", cleaningMethod);
            console.log("🚫 Excluded classes:", excludedClasses);

            for (let i = 0; i < selectors.length; i++) {{
                let selector = selectors[i];
                console.log("Testing selector " + (i + 1) + ":", selector);

                try {{
                    let elements = document.querySelectorAll(selector);
                    console.log("Found " + elements.length + " elements for selector:", selector);

                    if (elements.length > 0) {{
                        // Get the last element (the most recent)
                        let element = elements[elements.length - 1];

                        // Create a deep clone of the element to avoid modifying the live DOM
                        let clonedElement = element.cloneNode(true);

                        // Replace elements with excluded classes with a newline character in the cloned element
                        excludedClasses.forEach(className => {{
                            const elementsToExclude = clonedElement.querySelectorAll(`.${{className}}`);
                            elementsToExclude.forEach(el => {{
                                // Create a text node with a newline
                                const newlineTextNode = document.createTextNode('\\n');
                                // Replace the excluded element with the newline text node
                                el.replaceWith(newlineTextNode);
                            }});
                        }});

                        let codeContent = [];
                        const specificCodeBlocks = clonedElement.querySelectorAll('code.language-python');
                        if (specificCodeBlocks.length > 0) {{
                            specificCodeBlocks.forEach(block => {{
                                codeContent.push(block.textContent);
                            }});
                            text = codeContent.join('\\n'); // Joindre tous les blocs de code avec des nouvelles lignes
                            console.log("Extracted specific code content. Length:", text.length);
                        }} else {{
                            // Fallback to full text content if no specific <code> tags are found
                            text = (clonedElement.textContent || '').trim();
                            console.log("No specific <code> tags found. Using full text content. Length:", text.length);
                        }}

                        // Clean the text based on the universal method
                        if (cleaningMethod === 'remove_ui_elements') {{
                            // Claude cleaning
                            text = text.replace(/Send a message\.\.\..*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                            text = text.replace(/Regenerate.*$/gi, '');
                        }} else if (cleaningMethod === 'preserve_markdown_structure') {{
                            // ChatGPT cleaning
                            text = text.replace(/Copy code.*$/gi, '');
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                        }} else if (cleaningMethod === 'extract_from_nested_spans') {{
                            // Gemini cleaning
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Écrivez votre message.*$/gi, '');
                        }}

                        // Common cleaning
                        text = text.replace(/function\\(\\)\\s*\\{{.*\\}}/gi, '');
                        text = text.replace(/console\\.log.*$/gi, '');
                        text = text.replace(/let selectors.*$/gi, '');
                        text = text.replace(/Testing selector.*$/gi, '');
                        text = text.replace(/document\\.querySelector.*$/gi, '');
                        text = text.trim();

                        console.log("Cleaned text length:", text.length);
                        console.log("Text preview:", text.substring(0, 100));

                        if (!text.includes('console.log') &&
                            !text.includes('function()') &&
                            !text.includes('Testing selector') &&
                            !text.includes('document.querySelector') &&
                            !text.includes('Found ') &&
                            !text.includes('elements for selector')) {{
                            console.log("✅ Valid universal extraction found for " + platform + ", copying...");
                            copy(text);
                            break;
                        }} else {{
                            console.log("❌ Text rejected (contains debug info)");
                        }}
                    }}
                }} catch (e) {{
                    console.log("❌ Error with selector " + selector + ":", e);
                    continue;
                }}
            }}
            console.log("🎯 Universal extraction script completed for " + platform);
            """
            return self._execute_extraction_script(js_code, detected_browser_type)
        except Exception as e:
            self._debug_log(f"❌ Erreur extraction universelle: {e}")
            logger.error(f"Erreur extraction: {e}")
            # Fallback vers l'ancienne méthode
            return self._extract_response_simple_fallback(
                extraction_config, platform_profile, detected_browser_type
            )

    def _execute_extraction_script(self, js_code, detected_browser_type):
        """Exécute le script d'extraction universel et retourne le résultat"""
        try:
            self._debug_log("🖥️ Ouverture console pour extraction universelle")

            # These keyboard shortcuts are usually handled by the browser_manager itself
            # if detected_browser_type == 'firefox':
            #     self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            # else:
            #     self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            # time.sleep(0.5)

            # self.should_stop is not used here
            # if self.should_stop:
            #     self.debug_log("🛑 Arrêt pendant ouverture console extraction")
            #     return ""

            self._debug_log("🧹 Nettoyage console pour extraction")
            pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.1)

            self._debug_log("💉 Injection script d'extraction universel")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.8)  # Give JS time to execute and copy to clipboard

            self._debug_log("📋 Lecture résultat extraction universelle")
            result = pyperclip.paste().strip()
            self._debug_log(f"Résultat brut longueur: {len(result)}")

            if result:
                self._debug_log(f"Aperçu résultat: '{result[:100]}...'")

                # Validation supplémentaire pour s'assurer que ce n'est pas du code JS de débogage
                excluded_keywords = []
                has_excluded = any(
                    keyword in result.lower() for keyword in excluded_keywords
                )
                self._debug_log(f"Test exclusion keywords: {has_excluded}")

                if not has_excluded:
                    self._debug_log(
                        f"✅ Réponse universelle valide extraite: {len(result)} caractères"
                    )
                    return result
                else:
                    self._debug_log("❌ Réponse rejetée (contient du code/debug)")
            else:
                self._debug_log("❌ Réponse vide")
            return ""
        except Exception as e:
            self._debug_log(f"❌ Erreur exécution extraction: {e}")
            return ""

    def _extract_response_simple_fallback(
        self, extraction_config, platform_profile, detected_browser_type
    ):
        """
        Ancienne méthode d'extraction en fallback.
        Cette méthode est maintenant un simple wrapper qui construit le JS et appelle _execute_extraction_script.
        La logique de fallback est gérée dans le JS universel.
        """
        self._debug_log("🔄 Fallback vers extraction simple (via script universel)")
        response_area = extraction_config.get("response_area", {})
        platform_config = response_area.get("platform_config", {})
        primary_selector = platform_config.get("primary_selector", "p:last-child")
        fallback_selectors = platform_config.get("fallback_selectors", [])

        self._debug_log(f"Primary selector fallback: {primary_selector}")
        self._debug_log(f"Fallback selectors: {fallback_selectors}")

        window_position = platform_profile.get("window_position", {})
        if window_position:
            self._debug_log(
                f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})"
            )
            self.conductor.mouse_controller.click(
                window_position["x"], window_position["y"]
            )
            time.sleep(0.2)

        selectors = [primary_selector] + fallback_selectors[:3]
        self._debug_log(f"Sélecteurs fallback à tester: {selectors}")

        # Le script JS est le même que pour l'extraction universelle, mais avec les sélecteurs de fallback
        js_code = f"""
            (async () => {{
                let text = '';
                const excludedClasses = ["pt-3", "pb-3"];
                let selectorsToUse = {json.dumps(selectors)}; # Utilise les sélecteurs de fallback

                console.log("🔄 Testing fallback selectors:", selectorsToUse);
                console.log("🚫 Excluded classes:", excludedClasses);

                for (let i = 0; i < selectorsToUse.length; i++) {{
                    let selector = selectorsToUse[i];
                    console.log("Testing selector " + (i + 1) + ":", selector);
                    try {{
                        let elements = document.querySelectorAll(selector);
                        console.log("Found " + elements.length + " elements for selector:", selector);
                        if (elements.length > 0) {{
                            let element = elements[elements.length - 1];
                            let clonedElement = element.cloneNode(true);

                            excludedClasses.forEach(className => {{
                                const elementsToExclude = clonedElement.querySelectorAll(`.${{className}}`);
                                elementsToExclude.forEach(el => el.remove());
                            }});

                            // MODIFICATION ICI : Cibler spécifiquement la balise <code> avec la classe
                            let codeContent = [];
                            const specificCodeBlocks = clonedElement.querySelectorAll('code.whitespace-pre.language-python');
                            
                            if (specificCodeBlocks.length > 0) {{
                                specificCodeBlocks.forEach(block => {{
                                    codeContent.push(block.textContent);
                                }});
                                text = codeContent.join('\\n');
                                console.log("Extracted specific code content. Length:", text.length);
                            }} else {{
                                text = (clonedElement.textContent || '').trim();
                                console.log("No specific <code> tags found. Using full text content. Length:", text.length);
                            }}
                            
                            console.log("Text length:", text.length);
                            console.log("Text preview:", text.substring(0, 50));
                            if (text.length > 15 && !text.includes('console.log') && !text.includes('function()') && !text.includes('Testing selector')) {{
                                console.log("Valid fallback text found, returning...");
                                return text; # Retourne le texte
                            }} else {{
                                console.log("Text rejected (too short or contains debug)");
                            }}
                        }}
                    }} catch(e) {{
                        console.log("Error with selector " + selector + ":", e);
                        continue;
                    }}
                }}
                console.log("Fallback extraction script completed");
                return ''; # Retourne vide si rien n'est trouvé
            }})();
            """
        return self._execute_extraction_script(js_code, detected_browser_type)

    def refresh(self):
        """Méthode de rafraîchissement (peut être étendue plus tard)."""
        self._debug_log("NodeCreationWidget rafraîchi.")
        self._populate_project_selection()
        self._populate_platform_selection()

    def update_language(self):
        """Met à jour les textes si la langue change."""
        pass
