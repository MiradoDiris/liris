import os
from datetime import datetime
from utils.logger import logger
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea

from ui.localization.translator import tr
from ui.styles.theme import Theme


class DatasetRelationTab(QtWidgets.QWidget):
    """
    Onglet de génération de combinaisons de typologies de contexte.
    Navigation hiérarchique avec clic simple pour naviguer, double-clic pour sélectionner.
    """
    
    combinations_generated = pyqtSignal(dict)

    def __init__(self, project_manager, config_data, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data
        self.combinations = []  # Liste de combinaisons
        self.current_combination = {
            'contexts': [],  # Liste des contextes pour la combinaison en cours
            'master': None
        }
        self.current_combination_index = 0
        self.selected_master_typologie = None
        self._typologies_cache = []

        self.current_batch_id = None
        self.is_batch_saved = False
        
        self._context_navigation = {
            'typologie': None,
            'taxonomy': None,
            'root': None,
            'parent': None,
            'child_path': []
        }

        self._modification_in_progress = None
        
        self._init_ui()
        self._load_initial_data()

    def _init_ui(self):
        # Container principal avec scroll
        main_container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_container)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QtWidgets.QLabel(tr("dataset.combination_title"))
        title_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Theme.PRIMARY_COLOR}; padding: 8px 0;")
        main_layout.addWidget(title_label)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(10)

        left_widget = self._create_left_section()
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(350)
        content_layout.addWidget(left_widget, 2)

        right_widget = self._create_right_section()
        content_layout.addWidget(right_widget, 8)

        main_layout.addLayout(content_layout)
        self._create_action_buttons(main_layout)

        # Envelopper dans un QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(main_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        final_layout = QtWidgets.QVBoxLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll)

    def _create_left_section(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._create_batch_info_card())
        layout.addWidget(self._create_master_card())
        layout.addStretch()
        return container

    def _create_batch_info_card(self):
        group = self._create_modern_card("Informations du Batch")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(8)

        project_label = QtWidgets.QLabel("Projet")
        project_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 10px;")
        layout.addWidget(project_label)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.setMinimumHeight(28)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        layout.addWidget(self.project_combo)

        self._add_form_field(layout, "Famille de batch", "batch_family_edit", "Ex: Production, Test...")
        self._add_form_field(layout, "Nom du batch", "batch_name_edit", "Ex: Batch_Contexte")

        desc_label = QtWidgets.QLabel("Input")
        desc_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 10px;")
        layout.addWidget(desc_label)

        self.desc_edit = QtWidgets.QTextEdit()
        self.desc_edit.setPlaceholderText("Input...")
        self.desc_edit.setMaximumHeight(70)
        self.desc_edit.setStyleSheet("""
            QTextEdit { border: 2px solid #e1e4e8; border-radius: 5px; padding: 5px;
                background-color: white; font-size: 10px; color: #2c3e50; }
            QTextEdit:focus { border: 2px solid #2c3e50; }
        """)
        layout.addWidget(self.desc_edit)

        # Boutons de gestion des batches - VERSION CÔTE À CÔTE OPTIMISÉE
        batch_buttons_layout = QtWidgets.QHBoxLayout()
        batch_buttons_layout.setSpacing(4)  # Espacement réduit

        self.load_batch_btn = self._create_mini_button("Charger", self._load_batch_dialog)
        self.load_batch_btn.setToolTip("Charger un batch sauvegardé")
        self.load_batch_btn.setFixedWidth(65)  # 🔧 Largeur fixe compacte
        batch_buttons_layout.addWidget(self.load_batch_btn)

        self.new_batch_btn = self._create_mini_button("Nouveau", self._new_batch)
        self.new_batch_btn.setToolTip("Créer un nouveau batch")
        self.new_batch_btn.setFixedWidth(70)  # 🔧 Largeur fixe compacte
        batch_buttons_layout.addWidget(self.new_batch_btn)

        # Ajouter un stretch pour pousser les boutons à gauche
        batch_buttons_layout.addStretch()

        layout.addLayout(batch_buttons_layout)

        # Indicateur de statut
        self.batch_status_label = QtWidgets.QLabel("Nouveau batch")
        self.batch_status_label.setStyleSheet(
            "color: #95a5a6; font-size: 9px; font-style: italic; padding: 3px;"
        )
        layout.addWidget(self.batch_status_label)

        return group

    def _create_master_card(self):
        group = self._create_modern_card("Typologie de Contexte Master")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(8)

        master_label = QtWidgets.QLabel("Sélectionner la typologie master")
        master_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 10px;")
        layout.addWidget(master_label)

        self.master_combo = QtWidgets.QComboBox()
        self.master_combo.setStyleSheet(self._get_modern_input_style())
        self.master_combo.setMinimumHeight(28)
        self.master_combo.currentIndexChanged.connect(self._on_master_typologie_changed)
        layout.addWidget(self.master_combo)

        stats_label = QtWidgets.QLabel("Statistiques")
        stats_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 10px; margin-top: 6px;")
        layout.addWidget(stats_label)

        self.master_stats = QtWidgets.QTextEdit()
        self.master_stats.setReadOnly(True)
        self.master_stats.setMaximumHeight(80)
        self.master_stats.setStyleSheet("""
            QTextEdit { border: 2px solid #e1e4e8; border-radius: 5px; padding: 6px;
                background-color: #f8f9fa; font-size: 10px; color: #2c3e50; }
        """)
        layout.addWidget(self.master_stats)
        return group

    def _create_right_section(self):
        group = self._create_modern_card("Typologie de Contexte à Combiner")
        main_layout = QtWidgets.QVBoxLayout(group)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._create_navigation_breadcrumb())

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)

        # Ligne 1: Typologie, Cluster, Labels (dynamique)
        grid.addWidget(self._create_hierarchy_selector("Typologie", "context_typologie", False), 0, 0)
        grid.addWidget(self._create_hierarchy_selector("Cluster", "context_taxonomy", True), 0, 1)
        grid.addWidget(self._create_dynamic_labels_section(), 0, 2)

        # Ligne 2: Tableau de combinaisons
        grid.addWidget(self._create_batch_table_section(), 1, 0, 1, 3)

        for i in range(3):
            grid.setColumnStretch(i, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 2)

        main_layout.addLayout(grid)
        self._connect_hierarchy_signals()
        return group
    
    def _create_batch_table_section(self):
        """Tableau de combinaisons avec colonnes dynamiques pour chaque contexte"""
        group = QtWidgets.QGroupBox("Tableau des Combinaisons")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # Sélecteur de batch existant
        batch_selector_layout = QtWidgets.QHBoxLayout()
        batch_selector_layout.setSpacing(8)

        batch_selector_label = QtWidgets.QLabel("Charger un batch:")
        batch_selector_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        batch_selector_layout.addWidget(batch_selector_label)

        self.batch_selector_combo = QtWidgets.QComboBox()
        self.batch_selector_combo.setStyleSheet(self._get_modern_input_style())
        self.batch_selector_combo.setMinimumHeight(28)
        self.batch_selector_combo.setMaximumWidth(280)
        self.batch_selector_combo.addItem("-- Sélectionner un batch --")
        self.batch_selector_combo.currentIndexChanged.connect(self._on_batch_selected_from_combo)
        batch_selector_layout.addWidget(self.batch_selector_combo)

        self.refresh_batches_btn = self._create_mini_button("actualiser", self._refresh_batch_list)
        self.refresh_batches_btn.setToolTip("Actualiser la liste des batches")
        self.refresh_batches_btn.setMaximumWidth(80)
        batch_selector_layout.addWidget(self.refresh_batches_btn)

        batch_selector_layout.addStretch()
        layout.addLayout(batch_selector_layout)

        # En-tête avec stats et boutons
        header_layout = QtWidgets.QHBoxLayout()

        # Indicateur de combinaison en cours
        self.current_combo_label = QtWidgets.QLabel("Combinaison 1 | Contextes: 0")
        self.current_combo_label.setStyleSheet("""
            font-size: 12px; 
            color: #2c3e50; 
            font-weight: 700;
            padding: 6px 12px;
            background-color: #e3f2fd;
            border-radius: 4px;
            border: 2px solid #2196f3;
        """)
        header_layout.addWidget(self.current_combo_label)

        header_layout.addStretch()

        # Bouton "Nouvelle Combinaison"
        self.new_combo_btn = self._create_mini_button("+ Combinaison", self._start_new_combination)
        header_layout.addWidget(self.new_combo_btn)

        self.modify_selection_btn = self._create_mini_button("Modifier", self._modify_selected_row)
        self.modify_selection_btn.setEnabled(False)
        header_layout.addWidget(self.modify_selection_btn)

        self.delete_selection_btn = self._create_mini_button("Supprimer", self._delete_selected_row)
        self.delete_selection_btn.setEnabled(False)
        header_layout.addWidget(self.delete_selection_btn)

        self.clear_batch_btn = self._create_mini_button("Effacer    ", self._permanent_clear_batch)
        self.clear_batch_btn.setToolTip("Effacer définitivement tous les batches et combinaisons")
        header_layout.addWidget(self.clear_batch_btn)

        layout.addLayout(header_layout)

        # Stats globales
        self.stats_label = QtWidgets.QLabel("Combinaisons totales: 0 | Samples: 0")
        self.stats_label.setStyleSheet("""
            font-size: 10px; 
            color: #7f8c8d; 
            font-weight: 600;
            padding: 4px 8px;
            background-color: #f8f9fa;
            border-radius: 4px;
        """)
        layout.addWidget(self.stats_label)

        # Tableau avec colonnes dynamiques
        self.batch_table = QtWidgets.QTableWidget()
        self.batch_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
                gridline-color: #e1e4e8;
            }
            QTableWidget::item {
                padding: 4px 6px;
                color: #2c3e50;
            }
            QTableWidget::item:selected {
                background-color: #d4edda;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: 600;
                color: #2c3e50;
            }
        """)

        # Initialiser avec 3 colonnes minimum
        self.batch_table.setColumnCount(3)
        self.batch_table.setHorizontalHeaderLabels(["Combinaison", "samples", "Contexte 1"])

        self.batch_table.horizontalHeader().setStretchLastSection(False)
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self.batch_table.setColumnWidth(0, 150)
        self.batch_table.setColumnWidth(1, 80)  # Largeur fixe pour Nb samples

        # Les colonnes de contexte sont étirables
        for i in range(2, self.batch_table.columnCount()):
            self.batch_table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        self.batch_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.batch_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.batch_table.verticalHeader().setVisible(False)

        self.batch_table.itemSelectionChanged.connect(self._on_batch_row_selected)
        self.batch_table.cellChanged.connect(self._on_nb_samples_changed)

        layout.addWidget(self.batch_table)

        return group
    
    def _start_new_combination(self):
        """Démarrer une nouvelle combinaison"""
        # Vérifier qu'il y a au moins 1 contexte dans la combinaison actuelle
        if not self.current_combination['contexts']:
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "La combinaison actuelle ne contient aucun contexte.\n"
                "Ajoutez au moins un contexte avant de créer une nouvelle combinaison."
            )
            return

        # Sauvegarder la combinaison actuelle
        self._save_current_combination()

        # Réinitialiser pour une nouvelle combinaison
        self.current_combination = {
            'contexts': [],
            'master': self.selected_master_typologie
        }
        self.current_combination_index += 1

        # Mettre à jour l'affichage
        self._update_current_combo_label()
        self._mark_current_selections()

        logger.info(f"✅ Nouvelle combinaison {self.current_combination_index + 1} créée")

        QtWidgets.QMessageBox.information(
            self,
            "Nouvelle Combinaison",
            f"Combinaison {self.current_combination_index + 1} créée.\n"
            "Ajoutez des contextes à cette nouvelle combinaison."
        )
    
    def _build_unified_context_display(self, context_info):
        """
        Affichage simplifié : [Typologie_Contexte] Élément_le_plus_bas
        """
        typologie = context_info.get('typologie', '')
        level = context_info.get('level', '')

        if not typologie:
            return 'N/A'

        # Toujours commencer par la typologie entre crochets
        display = f"[{typologie}]"

        if level == 'typologie':
            # Si on sélectionne juste la typologie (sans enfants)
            return display

        elif level == 'taxonomy':
            taxonomy = context_info.get('taxonomy', '')
            if taxonomy:
                display += f" {taxonomy}"

        elif level == 'root':
            root = context_info.get('root', '')
            if root:
                display += f" {root}"

        elif level == 'parent':
            parent = context_info.get('parent', '')
            if parent:
                display += f" {parent}"

        elif level == 'child':
            # Prendre SEULEMENT le dernier enfant (le plus bas)
            child_path = context_info.get('child_path', [])
            if child_path:
                lowest_child = child_path[-1]
                display += f" {lowest_child}"

        return display

    def _count_taxonomy_samples(self, taxonomy):
        """Compte le nombre total de labels dans un cluster (taxonomy)"""
        if not taxonomy:
            return 0

        total = 0
        # Compter les root labels
        root_labels = taxonomy.get('root_labels', [])

        for root in root_labels:
            # +1 pour le root lui-même
            total += 1

            # Compter les parent labels
            parent_labels = root.get('parent_labels', [])
            for parent in parent_labels:
                # +1 pour le parent lui-même
                total += 1

                # Compter tous les enfants récursivement
                total += self._count_children_recursive(parent.get('children', []))

        return total
    
    def _count_root_samples(self, root):
        """Compte le nombre total de labels dans un root"""
        if not root:
            return 0

        total = 0
        parent_labels = root.get('parent_labels', [])

        for parent in parent_labels:
            # +1 pour le parent lui-même
            total += 1
            # Ajouter tous les enfants
            total += self._count_children_recursive(parent.get('children', []))

        return total
    
    def _count_parent_samples(self, parent):
        """Compte le nombre total d'enfants dans un parent"""
        if not parent:
            return 0

        return self._count_children_recursive(parent.get('children', []))
    
    def _cancel_modification(self):
        """Annuler la modification en cours"""
        if not self._modification_in_progress:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Annuler la modification en cours ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Restaurer la checkbox originale
            original_path_key = self._modification_in_progress.get('original_path_key', '')
            if original_path_key:
                self._mark_current_selections()

            # Quitter le mode modification
            self._show_modification_mode(False)
            self._modification_in_progress = None

            logger.info("❌ Modification annulée")

            QtWidgets.QMessageBox.information(
                self,
                "Annulation",
                "La modification a été annulée."
            )
    
    def _save_modification(self):
        """Sauvegarder la modification - VERSION SIMPLIFIÉE"""
        if not self._modification_in_progress:
            return

        new_selection = self._modification_in_progress.get('new_selection')
        if not new_selection:
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "Veuillez d'abord sélectionner un nouvel élément avant de sauvegarder."
            )
            return

        index = self._modification_in_progress['index']

        # Générer le nouveau path_key
        new_path_key = self._generate_path_key_from_selection(new_selection)

        # Vérifier si ce path_key existe déjà ailleurs
        for i, combo in enumerate(self.combinations):
            if i != index and combo.get('path_key') == new_path_key:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Doublon détecté",
                    f"Cette combinaison existe déjà à la ligne {i + 1}."
                )
                return

        # Remplacer la combinaison
        master_name = self.selected_master_typologie.get('name', 'N/A')

        new_combination = {
            'master': {'name': master_name, 'data': self.selected_master_typologie},
            'context': new_selection,
            'display': new_selection['display'],
            'path_key': new_path_key
        }

        # Mettre à jour dans la liste
        self.combinations[index] = new_combination

        # ✅ Mettre à jour SEULEMENT cette ligne dans le tableau
        context_item = self.batch_table.item(index, 1)
        if context_item:
            display_text = self._build_unified_context_display(new_selection)
            context_item.setText(display_text)
            context_item.setData(Qt.UserRole, new_combination)

        # Quitter le mode modification
        self._show_modification_mode(False)
        self._modification_in_progress = None

        # Mettre à jour l'interface
        self._update_stats()
        self._mark_current_selections()

        QtWidgets.QMessageBox.information(
            self,
            "Succès",
            f"Combinaison {index + 1} modifiée avec succès!"
        )

        logger.info(f"✅ Combinaison {index + 1} remplacée avec succès")
    
    def _modify_selected_row(self):
        """Modifier la combinaison sélectionnée - ACTIVE LE MODE MODIFICATION"""
        selected_rows = self.batch_table.selectionModel().selectedRows()

        if not selected_rows:
            return

        row = selected_rows[0].row()

        if row >= len(self.combinations):
            logger.error(f"Index invalide: {row} >= {len(self.combinations)}")
            return

        combination = self.combinations[row]
        context = combination.get('context', {})

        logger.info(f"=== Modification de la combinaison {row + 1} ===")
        logger.debug(f"Context: {context}")

        self._modification_in_progress = {
            'index': row,
            'original_combination': combination.copy(),
            'original_path_key': combination.get('path_key', '')
        }

        self._show_modification_mode(True)

        typologie_name = context.get('typologie', '')
        if typologie_name:
            typologie = self._find_typologie_by_name(typologie_name)
            if typologie:
                for i in range(self.context_typologie_tree.topLevelItemCount()):
                    item = self.context_typologie_tree.topLevelItem(i)
                    if item.text(0) == typologie_name:
                        self.context_typologie_tree.setCurrentItem(item)
                        self._on_typologie_item_clicked(item, 0)
                        logger.info(f"✅ Navigation vers typologie: {typologie_name}")
                        break

        taxonomy_name = context.get('taxonomy', '')
        level = context.get('level', '')

        if taxonomy_name and level in ['taxonomy', 'root', 'parent', 'child']:
            for i in range(self.context_taxonomy_tree.topLevelItemCount()):
                item = self.context_taxonomy_tree.topLevelItem(i)
                if item.text(0) == taxonomy_name:
                    self.context_taxonomy_tree.setCurrentItem(item)
                    self._on_taxonomy_item_clicked(item, 0)
                    logger.info(f"✅ Navigation vers taxonomy: {taxonomy_name}")
                    break

        root_name = context.get('root', '')
        if root_name and level in ['root', 'parent', 'child']:
            for i in range(self.dynamic_labels_tree.topLevelItemCount()):
                item = self.dynamic_labels_tree.topLevelItem(i)
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('level') == 'root':
                    if item_data.get('data', {}).get('name', '') == root_name:
                        self.dynamic_labels_tree.setCurrentItem(item)
                        logger.info(f"✅ Navigation vers root: {root_name}")
                        if level in ['parent', 'child']:
                            self._navigate_down_labels()
                        break

        parent_name = context.get('parent', '')
        if parent_name and level in ['parent', 'child']:
            for i in range(self.dynamic_labels_tree.topLevelItemCount()):
                item = self.dynamic_labels_tree.topLevelItem(i)
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('level') == 'parent':
                    if item_data.get('data', {}).get('name', '') == parent_name:
                        self.dynamic_labels_tree.setCurrentItem(item)
                        logger.info(f"✅ Navigation vers parent: {parent_name}")
                        if level == 'child':
                            self._navigate_down_labels()
                        break

        child_path = context.get('child_path', [])
        if child_path and level == 'child':
            for path_segment in child_path[:-1]:
                for i in range(self.dynamic_labels_tree.topLevelItemCount()):
                    item = self.dynamic_labels_tree.topLevelItem(i)
                    item_data = item.data(0, Qt.UserRole)
                    if item_data:
                        current_path = item_data.get('path', [])
                        if current_path and current_path[-1] == path_segment:
                            self.dynamic_labels_tree.setCurrentItem(item)
                            self._navigate_down_labels()
                            logger.info(f"✅ Navigation vers segment: {path_segment}")
                            break

            target_child = child_path[-1]
            for i in range(self.dynamic_labels_tree.topLevelItemCount()):
                item = self.dynamic_labels_tree.topLevelItem(i)
                item_data = item.data(0, Qt.UserRole)
                if item_data:
                    current_path = item_data.get('path', [])
                    if current_path and current_path[-1] == target_child:
                        self.dynamic_labels_tree.setCurrentItem(item)
                        logger.info(f"✅ Sélection finale: {target_child}")
                        break

        path_key = combination.get('path_key', '')
        if path_key:
            self._uncheck_current_selection(path_key)

        # Message de confirmation
        QtWidgets.QMessageBox.information(
            self,
            "Mode Modification",
            f"Mode modification activé pour Combinaison {row + 1}\n\n"
            f"Élément actuel:\n"
            f"{context.get('display', 'N/A')}\n\n"
            f"• Sélectionnez un nouvel élément avec les checkboxes\n"
            f"• Cliquez sur 'Sauvegarder Modif' pour enregistrer\n"
            f"• Cliquez sur 'Annuler' pour annuler la modification"
        )

        logger.info(f"✅ Mode modification activé pour Combinaison {row + 1}")

    def _uncheck_current_selection(self, path_key):
        """Décocher la checkbox correspondant au path_key"""
        # Chercher dans tous les arbres
        trees = [
            (self.context_typologie_tree, 'typologie'),
            (self.context_taxonomy_tree, 'taxonomy'),
            (self.dynamic_labels_tree, 'dynamic')
        ]

        for tree_widget, tree_name in trees:
            for i in range(tree_widget.topLevelItemCount()):
                item = tree_widget.topLevelItem(i)
                item_data = item.data(0, Qt.UserRole)

                # Construire le path_key de cet item
                item_path_key = self._get_item_path_for_batch_tree(
                    item_data.get('level', tree_name), 
                    item_data, 
                    item
                )

                if item_path_key == path_key:
                    checkbox = tree_widget.itemWidget(item, 1)
                    if checkbox:
                        checkbox.blockSignals(True)
                        checkbox.setChecked(False)
                        checkbox.blockSignals(False)
                        logger.debug(f"✅ Checkbox décochée pour: {path_key}")
                    return
                
    def _show_modification_mode(self, show):
        """Afficher/masquer les boutons de modification"""
        self.save_modification_btn.setVisible(show)
        self.cancel_modification_btn.setVisible(show)
        self.modify_selection_btn.setEnabled(not show)
        self.delete_selection_btn.setEnabled(not show)

        if show:
            logger.info("🔧 Mode modification activé - Boutons affichés")
        else:
            logger.info("✅ Mode modification désactivé - Boutons cachés")

    def _refresh_batch_list(self):
        """Actualiser la liste des batches disponibles"""
        self.batch_selector_combo.blockSignals(True)
        self.batch_selector_combo.clear()
        self.batch_selector_combo.addItem("-- Sélectionner un batch --")

        # Désactiver l'item par défaut
        model = self.batch_selector_combo.model()
        if model.rowCount() > 0:
            item = model.item(0)
            if item:
                item.setForeground(QColor("#95a5a6"))

        if self.project_manager and self.project_combo.currentIndex() > 0:
            batches = self.project_manager.get_all_batches()

            for batch in batches:
                data = batch.get('data', {})
                batch_name = data.get('batch_name', 'Sans nom')
                count = data.get('count', 0)
                status = batch.get('status', 'pending')

                # Formatage avec émojis selon le statut
                status_emoji = {
                    'pending': '⏳',
                    'processing': '⚙️',
                    'completed': '✅',
                    'error': '❌'
                }.get(status, '❓')

                display_text = f"{status_emoji} Batch #{batch['batch_number']}: {batch_name} ({count})"
                self.batch_selector_combo.addItem(display_text)
                self.batch_selector_combo.setItemData(
                    self.batch_selector_combo.count() - 1,
                    batch,
                    Qt.UserRole
                )

        self.batch_selector_combo.blockSignals(False)
        logger.info(f"Liste des batches actualisée: {self.batch_selector_combo.count() - 1} batch(es)")

    def _on_batch_selected_from_combo(self, index):
        """Appelée quand un batch est sélectionné dans le combo"""
        if index <= 0:
            return

        batch = self.batch_selector_combo.itemData(index, Qt.UserRole)
        if not batch:
            return

        # Vérifier si des modifications non sauvegardées existent
        if not self.is_batch_saved and self.combinations:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Batch non sauvegardé",
                "Le batch actuel contient des modifications non sauvegardées.\n"
                "Voulez-vous continuer et perdre ces modifications ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                # Remettre la sélection précédente
                self.batch_selector_combo.blockSignals(True)
                self.batch_selector_combo.setCurrentIndex(0)
                self.batch_selector_combo.blockSignals(False)
                return

        # Charger le batch
        self._load_batch_into_table(batch)

    def _load_batch_into_table(self, batch):
        """Charger un batch - VERSION CORRIGÉE AVEC NOUVELLE STRUCTURE"""
        logger.info("=" * 100)
        logger.info(f"📂 CHARGEMENT BATCH #{batch['batch_number']}")
        logger.info("=" * 100)

        data = batch.get('data', {})

        logger.info(f"Nom: {data.get('batch_name')}")
        logger.info(f"Famille: {data.get('batch_family')}")

        # Remplir les informations
        self.current_batch_id = batch['batch_number']
        self.batch_name_edit.setText(data.get('batch_name', ''))
        self.batch_family_edit.setText(data.get('batch_family', ''))
        self.desc_edit.setPlainText(data.get('description', ''))

        # Charger la typologie master
        master_data = data.get('master_typologie', {})

        if isinstance(master_data, dict):
            # Nouvelle structure (complète)
            master_name = master_data.get('name', '')
            logger.info(f"Master typologie (complète): {master_name}")
            logger.info(f"  - {len(master_data.get('taxonomy_clusters', []))} clusters")
        else:
            # Ancienne structure (juste le nom)
            master_name = master_data if isinstance(master_data, str) else str(master_data)
            logger.info(f"Master typologie (nom seul): {master_name}")

        if master_name:
            # Chercher dans la combo
            index = self.master_combo.findText(master_name)
            if index > 0:
                self.master_combo.blockSignals(True)
                self.master_combo.setCurrentIndex(index)
                self.master_combo.blockSignals(False)
                self._on_master_typologie_changed(index)
                logger.info(f"✅ Master sélectionné: {master_name}")

        # Charger les combinaisons avec la nouvelle structure
        self.combinations = []
        raw_combinations = data.get('combinations', [])

        logger.info(f"\n📊 {len(raw_combinations)} combinaison(s) à charger")

        for i, raw_combo in enumerate(raw_combinations):
            logger.info(f"\n[Combinaison {i + 1}]")

            # Convertir au format interne
            converted_combo = self._convert_batch_combination(raw_combo, master_name, i)

            if converted_combo:
                self.combinations.append(converted_combo)
                logger.info(f"  ✅ Combinaison {i + 1} chargée")

        # Vider et remplir le tableau
        self.batch_table.setRowCount(0)
        for i, combo in enumerate(self.combinations):
            self._update_table_row(i, combo)

        # Marquer comme sauvegardé
        self.is_batch_saved = True
        self._update_batch_status(f"Batch #{batch['batch_number']} - {batch.get('status', 'pending')}")

        self._update_stats()
        self._mark_current_selections()

        logger.info(f"\n✅ Batch chargé: {len(self.combinations)} combinaisons")
        logger.info("=" * 100 + "\n")

        QtWidgets.QMessageBox.information(
            self,
            "Succès",
            f"Batch '{data.get('batch_name', '')}' chargé avec succès!\n"
            f"Combinaisons: {len(self.combinations)}"
        )

    def _convert_batch_combination(self, batch_combo, master_name, index):
        """
        Convertit une combinaison du batch vers le format interne
        """
        contexts_data = batch_combo.get('contexts', [])
        nb_samples = batch_combo.get('nb_samples', 1)

        logger.info(f"  - {len(contexts_data)} contexte(s)")
        logger.info(f"  - {nb_samples} samples")

        # Construire les contextes au format interne
        internal_contexts = []

        for ctx_idx, ctx in enumerate(contexts_data):
            level = ctx.get('level', '')
            context_data = ctx.get('data', {})
            display = ctx.get('display', '')

            logger.info(f"    [Contexte {ctx_idx + 1}] {level}: {display}")

            # Reconstruire la sélection depuis les données
            selection = self._rebuild_selection_from_context(level, context_data, display)

            if selection:
                path_key = self._generate_path_key_from_selection(selection)

                internal_contexts.append({
                    'selection': selection,
                    'path_key': path_key,
                    'display': display
                })

                logger.info(f"      ✅ Contexte converti")

        return {
            'index': index,
            'master': {
                'name': master_name,
                'data': self.selected_master_typologie
            },
            'contexts': internal_contexts,
            'nb_samples': nb_samples
        }
    
    def _rebuild_selection_from_context(self, level, context_data, display):
        """
        Reconstruit un objet selection depuis les données du contexte
        """
        typologie_name = context_data.get('name', '')

        if level == 'typologie':
            return {
                'level': 'typologie',
                'typologie': typologie_name,
                'taxonomy': '',
                'root': '',
                'parent': '',
                'child_path': [],
                'child': '',
                'display': display
            }

        clusters = context_data.get('taxonomy_clusters', [])
        if not clusters:
            return None

        cluster = clusters[0]
        taxonomy_name = cluster.get('name', '')

        if level == 'taxonomy':
            return {
                'level': 'taxonomy',
                'typologie': typologie_name,
                'taxonomy': taxonomy_name,
                'root': '',
                'parent': '',
                'child_path': [],
                'child': '',
                'display': display
            }

        roots = cluster.get('root_labels', [])
        if not roots:
            return None

        root = roots[0]
        root_name = root.get('name', '')

        if level == 'root':
            return {
                'level': 'root',
                'typologie': typologie_name,
                'taxonomy': taxonomy_name,
                'root': root_name,
                'parent': '',
                'child_path': [],
                'child': '',
                'display': display
            }

        parents = root.get('parent_labels', [])
        if not parents:
            return None

        parent = parents[0]
        parent_name = parent.get('name', '')

        if level == 'parent':
            return {
                'level': 'parent',
                'typologie': typologie_name,
                'taxonomy': taxonomy_name,
                'root': root_name,
                'parent': parent_name,
                'child_path': [],
                'child': '',
                'display': display
            }

        if level == 'child':
            # Reconstruire le chemin enfant depuis la hiérarchie
            child_path = self._extract_child_path_from_hierarchy(parent.get('children', []))

            return {
                'level': 'child',
                'typologie': typologie_name,
                'taxonomy': taxonomy_name,
                'root': root_name,
                'parent': parent_name,
                'child_path': child_path,
                'child': child_path[-1] if child_path else '',
                'display': display
            }

        return None
    
    def _extract_child_path_from_hierarchy(self, children):
        """
        Extrait le chemin des enfants depuis une hiérarchie
        """
        if not children:
            return []
        
        path = []
        current = children[0]  # Prendre le premier (c'est la sélection)
        
        while current:
            path.append(current.get('name', ''))
            sub_children = current.get('children', [])
            if sub_children:
                current = sub_children[0]
            else:
                break
            
        return path
    
    def _add_to_batch_table(self, master_name, contexts_dict, combination_data):
        """Ajouter une ligne au tableau - VERSION 3 COLONNES"""
        row = self.batch_table.rowCount()
        self.batch_table.insertRow(row)

        # Colonne 0 : Numéro
        num_item = QtWidgets.QTableWidgetItem(f"Combinaison {row + 1}")
        num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        font = num_item.font()
        font.setBold(True)
        num_item.setFont(font)
        num_item.setBackground(QColor("#f8f9fa"))
        self.batch_table.setItem(row, 0, num_item)

        # Colonne 1 : Nb samples (éditable, défaut 1 si non défini)
        nb_samples = combination_data.get('nb_samples', 1)
        nb_item = QtWidgets.QTableWidgetItem(str(nb_samples))
        nb_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        nb_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.batch_table.setItem(row, 1, nb_item)

        # Colonne 2 : Contexte unifié
        context_selection = combination_data.get('context', {})
        display_text = self._build_unified_context_display(context_selection)

        context_item = QtWidgets.QTableWidgetItem(display_text)
        context_item.setFlags(context_item.flags() & ~Qt.ItemIsEditable)
        context_item.setData(Qt.UserRole, combination_data)
        self.batch_table.setItem(row, 2, context_item)

        # Stocker les données complètes dans la première colonne pour accès
        num_item.setData(Qt.UserRole, combination_data)

    def _on_batch_row_selected(self):
        """Appelée quand une ligne du tableau est sélectionnée"""
        selected_rows = self.batch_table.selectionModel().selectedRows()

        # Désactiver les boutons si en mode modification
        if self._modification_in_progress:
            self.delete_selection_btn.setEnabled(False)
            self.modify_selection_btn.setEnabled(False)
            return

        # Activer/désactiver les boutons selon la sélection
        has_selection = len(selected_rows) > 0
        self.delete_selection_btn.setEnabled(has_selection)
        self.modify_selection_btn.setEnabled(has_selection)

        if selected_rows:
            row = selected_rows[0].row()
            logger.debug(f"Ligne sélectionnée : {row}")

            # ✅ NOUVEAU : Colorer toute la hiérarchie de cette combinaison
            if row < len(self.combinations):
                combination = self.combinations[row]
                self._highlight_combination_hierarchy(combination)

    def _highlight_combination_hierarchy(self, combination):
        """
        Met en surbrillance TOUTE la hiérarchie d'une combinaison sélectionnée
        Colore en vert clair : Typologie > Cluster > Root > Parent > Enfant
        """
        # D'abord, réinitialiser toutes les couleurs
        self._reset_all_hierarchy_colors()

        context = combination.get('context', {})
        if not context:
            return

        level = context.get('level', '')
        typologie_name = context.get('typologie', '')

        logger.info(f"=== Mise en évidence hiérarchie : {level} ===")
        logger.debug(f"Typologie: {typologie_name}")

        # Couleur de surbrillance
        highlight_color = QColor("#c8e6c9")  # Vert clair

        # 1️⃣ COLORER LA TYPOLOGIE
        if typologie_name:
            self._highlight_typologie_item(typologie_name, highlight_color)

        # 2️⃣ COLORER LE CLUSTER (si applicable)
        taxonomy_name = context.get('taxonomy', '')
        if taxonomy_name and level in ['taxonomy', 'root', 'parent', 'child']:
            self._highlight_taxonomy_item(taxonomy_name, highlight_color)

        # 3️⃣ COLORER LE ROOT (si applicable)
        root_name = context.get('root', '')
        if root_name and level in ['root', 'parent', 'child']:
            self._highlight_dynamic_label_item(root_name, 'root', highlight_color)

        # 4️⃣ COLORER LE PARENT (si applicable)
        parent_name = context.get('parent', '')
        if parent_name and level in ['parent', 'child']:
            self._highlight_dynamic_label_item(parent_name, 'parent', highlight_color)

        # 5️⃣ COLORER L'ENFANT (si applicable)
        if level == 'child':
            child_path = context.get('child_path', [])
            if child_path:
                # Colorer le dernier enfant (le plus bas dans la hiérarchie)
                last_child = child_path[-1]
                self._highlight_dynamic_label_item(last_child, 'child', highlight_color)

    def _highlight_typologie_item(self, typologie_name, color):
        """Colore un item de typologie"""
        for i in range(self.context_typologie_tree.topLevelItemCount()):
            item = self.context_typologie_tree.topLevelItem(i)
            full_text = item.text(0)
            item_name = full_text.split(' (')[0] if ' (' in full_text else full_text
            
            if item_name == typologie_name:
                # Utiliser setData avec BackgroundRole pour forcer la couleur
                item.setData(0, Qt.BackgroundRole, color)
                item.setBackground(0, color)
                
                # Police en gras pour plus de visibilité
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
                
                # Couleur de texte pour contraste
                item.setForeground(0, QColor("#1b5e20"))  # Vert foncé
                
                logger.debug(f"✅ Typologie colorée: {typologie_name}")
                break

    def _highlight_taxonomy_item(self, taxonomy_name, color):
        """Colore un item de taxonomy (cluster)"""
        for i in range(self.context_taxonomy_tree.topLevelItemCount()):
            item = self.context_taxonomy_tree.topLevelItem(i)
            full_text = item.text(0)
            item_name = full_text.split(' (')[0] if ' (' in full_text else full_text

            if item_name == taxonomy_name:
                # Utiliser setData avec BackgroundRole pour forcer la couleur
                item.setData(0, Qt.BackgroundRole, color)
                item.setBackground(0, color)

                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

                item.setForeground(0, QColor("#1b5e20"))

                logger.debug(f"✅ Taxonomy coloré: {taxonomy_name}")
                break

    def _highlight_dynamic_label_item(self, item_name, expected_level, color):
        """
        Colore un item dans la liste dynamique (root, parent, ou child)
        """
        for i in range(self.dynamic_labels_tree.topLevelItemCount()):
            item = self.dynamic_labels_tree.topLevelItem(i)
            item_data = item.data(0, Qt.UserRole)

            if not item_data:
                continue
            
            item_level = item_data.get('level', '')

            # Pour les enfants, utiliser le chemin complet
            if expected_level == 'child' and item_level == 'child':
                child_path = item_data.get('path', [])
                if child_path and child_path[-1] == item_name:
                    # Utiliser setData avec BackgroundRole
                    item.setData(0, Qt.BackgroundRole, color)
                    item.setBackground(0, color)

                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)

                    item.setForeground(0, QColor("#1b5e20"))

                    logger.debug(f"✅ Child coloré: {item_name}")
                    break
                
            # Pour root et parent
            elif item_level == expected_level:
                data_name = item_data.get('data', {}).get('name', '')
                if data_name == item_name:
                    # Utiliser setData avec BackgroundRole
                    item.setData(0, Qt.BackgroundRole, color)
                    item.setBackground(0, color)

                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)

                    item.setForeground(0, QColor("#1b5e20"))

                    logger.debug(f"✅ {expected_level.capitalize()} coloré: {item_name}")
                    break

    def _reset_all_hierarchy_colors(self):
        """
        Réinitialise toutes les couleurs dans tous les arbres
        """
        default_bg = QColor("white")
        default_fg = QColor("#2c3e50")

        # Réinitialiser les typologies
        for i in range(self.context_typologie_tree.topLevelItemCount()):
            item = self.context_typologie_tree.topLevelItem(i)
            item.setData(0, Qt.BackgroundRole, default_bg)
            item.setBackground(0, default_bg)
            item.setForeground(0, default_fg)
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)

        # Réinitialiser les taxonomies
        for i in range(self.context_taxonomy_tree.topLevelItemCount()):
            item = self.context_taxonomy_tree.topLevelItem(i)
            item.setData(0, Qt.BackgroundRole, default_bg)
            item.setBackground(0, default_bg)
            item.setForeground(0, default_fg)
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)

        # Réinitialiser les labels dynamiques
        for i in range(self.dynamic_labels_tree.topLevelItemCount()):
            item = self.dynamic_labels_tree.topLevelItem(i)
            item.setData(0, Qt.BackgroundRole, default_bg)
            item.setBackground(0, default_bg)
            item.setForeground(0, default_fg)
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)

    def _delete_selected_row(self):
        """Supprimer la ligne sélectionnée dans le tableau"""
        selected_rows = self.batch_table.selectionModel().selectedRows()

        if not selected_rows:
            return

        row = selected_rows[0].row()

        # Confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Supprimer cette combinaison ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
    
        if reply == QtWidgets.QMessageBox.Yes:
            self._remove_batch_row(row)

    def _build_context_display_text(self, context_info):
        level = context_info.get('level', '')
        parts = []

        if level == 'typologie':
            return context_info.get('typologie', 'N/A')

        elif level == 'taxonomy':
            taxonomy = context_info.get('taxonomy', '')
            if taxonomy:
                parts.append(taxonomy)

        elif level == 'root':
            taxonomy = context_info.get('taxonomy', '')
            root = context_info.get('root', '')
            if taxonomy:
                parts.append(taxonomy)
            if root:
                parts.append(root)

        elif level == 'parent':
            taxonomy = context_info.get('taxonomy', '')
            root = context_info.get('root', '')
            parent = context_info.get('parent', '')
            if taxonomy:
                parts.append(taxonomy)
            if root:
                parts.append(root)
            if parent:
                parts.append(parent)

        elif level == 'child':
            taxonomy = context_info.get('taxonomy', '')
            root = context_info.get('root', '')
            parent = context_info.get('parent', '')
            child_path = context_info.get('child_path', [])

            if taxonomy:
                parts.append(taxonomy)
            if root:
                parts.append(root)
            if parent:
                parts.append(parent)
            if child_path:
                parts.append(' > '.join(child_path))

        return ' / '.join(parts) if parts else 'N/A'

    def _remove_batch_row(self, row):
        """Supprimer une ligne du tableau - VERSION MODIFIÉE"""
        if row < len(self.combinations):
            self.combinations.pop(row)
            self.batch_table.removeRow(row)

            for i in range(self.batch_table.rowCount()):
                num_item = self.batch_table.item(i, 0)
                if num_item:
                    num_item.setText(f"Combinaison {i + 1}")

            self._update_stats()
            self._mark_current_selections()

            selected_rows = self.batch_table.selectionModel().selectedRows()
            if selected_rows and selected_rows[0].row() < len(self.combinations):
                new_row = selected_rows[0].row()
                self._highlight_combination_hierarchy(self.combinations[new_row])
            else:
                self._reset_all_hierarchy_colors()

        # Marquer comme modifié si batch chargé
        if self.current_batch_id and self.is_batch_saved:
            self.is_batch_saved = False
            self._update_batch_status(f"Batch #{self.current_batch_id} - Modifié (non sauvegardé)")

    def _create_dynamic_labels_section(self):
        """Section pour naviguer dans la hiérarchie complète avec checkboxes à droite"""
        group = QtWidgets.QGroupBox("Labels Dynamique")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # Boutons de navigation
        nav_container = QtWidgets.QWidget()
        nav_layout = QtWidgets.QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 4, 0, 0)
        nav_layout.setSpacing(4)

        nav_layout.addStretch()

        self.labels_up_btn = self._create_mini_button("↑ Remonter", self._navigate_up_labels)
        self.labels_up_btn.setEnabled(False)
        nav_layout.addWidget(self.labels_up_btn)

        self.labels_down_btn = self._create_mini_button("↓ Descendre", self._navigate_down_labels)
        self.labels_down_btn.setEnabled(False)
        nav_layout.addWidget(self.labels_down_btn)

        layout.addWidget(nav_container)

        # Breadcrumb
        self.labels_breadcrumb = QtWidgets.QLabel("Sélectionnez un cluster")
        self.labels_breadcrumb.setStyleSheet(
            "color: #7f8c8d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f0f0f0; border-radius: 3px; font-weight: 600;"
        )
        layout.addWidget(self.labels_breadcrumb)

        # ✅ QTreeWidget avec checkboxes à droite
        self.dynamic_labels_tree = QtWidgets.QTreeWidget()
        self.dynamic_labels_tree.setHeaderHidden(True)
        self.dynamic_labels_tree.setColumnCount(2)
        self.dynamic_labels_tree.setStyleSheet(self._get_hierarchy_tree_style())
        self.dynamic_labels_tree.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.dynamic_labels_tree.setFocusPolicy(Qt.NoFocus)

        # ✅ CORRECTION : Configurer les colonnes
        self.dynamic_labels_tree.header().setStretchLastSection(False)
        self.dynamic_labels_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.dynamic_labels_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.dynamic_labels_tree.setColumnWidth(1, 40)

        # ✅ Connexions pour navigation (clic sur texte) et toggle batch (clic sur checkbox)
        self.dynamic_labels_tree.itemClicked.connect(self._on_label_item_clicked)

        layout.addWidget(self.dynamic_labels_tree)

        return group

    def _create_navigation_breadcrumb(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        nav_label = QtWidgets.QLabel("Navigation:")
        nav_label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 11px;")
        layout.addWidget(nav_label)

        self.nav_breadcrumb = QtWidgets.QLabel("Sélectionnez une typologie")
        self.nav_breadcrumb.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 4px 10px; background-color: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.nav_breadcrumb)
        layout.addStretch()

        self.reset_nav_btn = self._create_mini_button("Reset", self._reset_navigation)
        layout.addWidget(self.reset_nav_btn)
        return container

    def _create_hierarchy_selector(self, label_text, attr_prefix, multi=False):
        container = QtWidgets.QGroupBox(label_text)
        container.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        tree_widget = QtWidgets.QTreeWidget()
        tree_widget.setHeaderHidden(True)
        tree_widget.setColumnCount(2)
        tree_widget.setStyleSheet(self._get_hierarchy_tree_style())
        tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        tree_widget.setFocusPolicy(Qt.NoFocus)

        tree_widget.header().setStretchLastSection(False)
        tree_widget.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        tree_widget.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        tree_widget.setColumnWidth(1, 40)

        layout.addWidget(tree_widget)

        setattr(self, f"{attr_prefix}_tree", tree_widget)
        return container

    def _get_hierarchy_tree_style(self):
        """Style pour QTreeWidget avec checkboxes à droite"""
        return """
            QTreeWidget { 
                border: 2px solid #e1e4e8; 
                border-radius: 6px; 
                background-color: white; 
                padding: 4px; 
                font-size: 11px; 
                color: #2c3e50;
                outline: none;
            } 
            QTreeWidget::item { 
                padding: 6px 8px;
                border-radius: 4px; 
                margin: 1px 0; 
                color: #2c3e50;
                min-height: 24px;
            } 
            QTreeWidget::item:hover { 
                background-color: #f5f5f5; 
            }
            QTreeWidget::branch {
                background: transparent;
            }
        """
    
    def _create_styled_checkbox(self):
        checkbox = QtWidgets.QCheckBox()
        # s'assurer qu'il n'y ait pas de texte (on affiche le check dans l'indicateur)
        checkbox.setText("")
        # fixe une taille suffisante pour être sûre que l'indicateur s'affiche
        checkbox.setFixedSize(26, 26)
        checkbox.setContentsMargins(0, 0, 0, 0)
    
        # SVG simple (check blanc) encodé en base64 — tu peux changer la couleur en modifiant le fill dans le SVG
        svg_check_base64 = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIgdmlld0JveD0iMCAwIDE0IDE0Ij4KICA8cGF0aCBmaWxsPSJ3aGl0ZSIgZD0iTTEyLjI1IDMuMjVsLTMuNjI1IDMuNjI1LTIuNS0yLjUtMS4yNSA xLjI1IDMuNzUgMy43NSA0Ljc1LTQuNzV6Ii8+Cjwvc3ZnPgo="
        )
    
        # style : background + indicator avec image pour :checked
        checkbox.setStyleSheet(f"""
            QCheckBox {{
                spacing: 4px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #cfd8dc;
                background-color: #ffffff;
                margin: 0px;
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid #90a4ae;
                background-color: #f5f7f6;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid #27ae60;
                background-color: #27ae60;
                image: url({svg_check_base64});
                image-position: center;
                image-repeat: no-repeat;
            }}
            QCheckBox::indicator:checked:hover {{
                border: 2px solid #229954;
                background-color: #229954;
            }}
        """)
    
        # Empêcher le texte par défaut d'apparaître
        checkbox.setFocusPolicy(QtCore.Qt.NoFocus)
        return checkbox

    def _create_dynamic_child_section(self):
        """
        Section enfants avec instructions claires
        """
        group = QtWidgets.QGroupBox("Labels Enfants")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # En-tête avec boutons de navigation
        top_container = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 4, 0, 0)
        top_layout.setSpacing(4)

        top_layout.addStretch()

        # Boutons de navigation
        self.child_up_btn = self._create_mini_button("↑ Remonter", self._navigate_up_child)
        self.child_up_btn.setEnabled(False)
        self.child_up_btn.setToolTip("Remonter d'un niveau dans la hiérarchie")
        top_layout.addWidget(self.child_up_btn)

        self.child_down_btn = self._create_mini_button("↓ Descendre", self._navigate_down_child)
        self.child_down_btn.setEnabled(False)
        self.child_down_btn.setToolTip("Descendre dans l'élément sélectionné (doit avoir des enfants)")
        top_layout.addWidget(self.child_down_btn)

        layout.addWidget(top_container)

        # Breadcrumb
        self.child_breadcrumb = QtWidgets.QLabel("Niveau racine")
        self.child_breadcrumb.setStyleSheet(
            "color: #7f8c8d; font-size: 10px; padding: 4px 8px; "
            "background-color: #f0f0f0; border-radius: 3px; font-weight: 600;"
        )
        layout.addWidget(self.child_breadcrumb)

        # Liste des enfants
        self.context_child_list = QtWidgets.QListWidget()
        self.context_child_list.setStyleSheet(self._get_hierarchy_list_style())
        self.context_child_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # ✅ Connexions correctes
        self.context_child_list.itemClicked.connect(self._on_child_clicked)
        self.context_child_list.itemDoubleClicked.connect(self._on_child_double_clicked)
        self.context_child_list.itemSelectionChanged.connect(self._on_child_selection_changed)

        layout.addWidget(self.context_child_list)

        return group

    def _create_batch_section_right(self):
        """Section batch avec bouton pour ouvrir la fenêtre de visualisation"""
        group = QtWidgets.QGroupBox("Éléments du Batch")
        group.setStyleSheet("""
            QGroupBox { font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 8px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # En-tête avec stats et bouton d'ouverture
        header_layout = QtWidgets.QHBoxLayout()

        self.stats_label = QtWidgets.QLabel("Combinaisons: 0")
        self.stats_label.setStyleSheet("font-size: 10px; color: #7f8c8d; font-weight: 600;")
        header_layout.addWidget(self.stats_label)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Liste compacte (optionnel - vous pouvez la garder ou la retirer)
        self.batch_list = QtWidgets.QListWidget()
        self.batch_list.setStyleSheet(self._get_hierarchy_list_style())
        self.batch_list.currentItemChanged.connect(self._on_batch_item_selected)
        self.batch_list.setMaximumHeight(150)  # Plus compact
        layout.addWidget(self.batch_list)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(4)

        self.add_to_batch_btn = self._create_mini_button("+ Ajouter", self._add_selected_to_batch)
        self.remove_from_batch_btn = self._create_mini_button("Retirer", self._remove_from_batch)
        self.clear_batch_btn = self._create_mini_button("Vider", self._clear_batch)
        self.remove_from_batch_btn.setEnabled(False)

        btn_layout.addWidget(self.add_to_batch_btn)
        btn_layout.addWidget(self.remove_from_batch_btn)
        btn_layout.addWidget(self.clear_batch_btn)
        layout.addLayout(btn_layout)
        return group
    
    def _get_hierarchy_list_style(self):
        """Style avec marqueur VERT aligné à droite"""
        return """
            QListWidget { 
                border: 2px solid #e1e4e8; 
                border-radius: 6px; 
                background-color: white; 
                padding: 4px; 
                font-size: 11px; 
                color: #2c3e50; 
            } 
            QListWidget::item { 
                padding: 6px 8px 6px 8px;
                border-radius: 4px; 
                margin: 1px 0; 
                color: #2c3e50;
                min-height: 24px;
            } 
            QListWidget::item:selected { 
                background-color: #e8f5e9;
                color: #2c3e50; 
            } 
            QListWidget::item:hover { 
                background-color: #f5f5f5; 
                color: #2c3e50; 
            }
        """

    def _connect_hierarchy_signals(self):
        """Connecter tous les signaux - VERSION AVEC DOUBLE-CLIC"""
        self.context_typologie_tree.itemClicked.connect(self._on_typologie_item_clicked)
        self.context_taxonomy_tree.itemClicked.connect(self._on_taxonomy_item_clicked)
        self.dynamic_labels_tree.itemClicked.connect(self._on_label_item_clicked)

        self.context_typologie_tree.itemDoubleClicked.connect(self._on_typologie_double_clicked)
        self.context_taxonomy_tree.itemDoubleClicked.connect(self._on_taxonomy_double_clicked)
        self.dynamic_labels_tree.itemDoubleClicked.connect(self._on_label_double_clicked)

    def _on_typologie_item_clicked(self, item, column):
        """Gérer le clic sur typologie - Double-clic pour ajouter au batch"""
        if column == 1:
            return

        self.context_typologie_tree.setCurrentItem(item)

        full_text = item.text(0)
        typ_name = full_text.split(' (')[0] if ' (' in full_text else full_text

        typologie = self._find_typologie_by_name(typ_name)
        if not typologie:
            return

        self._context_navigation = {
            'typologie': typologie, 
            'taxonomy': None, 
            'root': None, 
            'parent': None, 
            'child_path': [],
            'current_level': 'typologie'
        }

        # Charger les taxonomies
        self.context_taxonomy_tree.clear()
        for cluster in typologie.get('taxonomy_clusters', []):
            cluster_name = cluster.get('name', '')
            if cluster_name:
                sample_count = self._count_taxonomy_samples(cluster)
                display_text = f"{cluster_name} ({sample_count})"

                tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                tree_item.setData(0, Qt.UserRole, cluster)

                # ✅ MODIFICATION: Checkbox uniquement pour éléments sans enfants
                has_children = bool(cluster.get('root_labels', []))

                if not has_children:
                    # Élément feuille : checkbox visible
                    checkbox = self._create_styled_checkbox()
                    self.context_taxonomy_tree.setItemWidget(tree_item, 1, checkbox)
                    checkbox.stateChanged.connect(
                        lambda state, it=tree_item: self._on_checkbox_changed(it, 'taxonomy')
                    )

                self.context_taxonomy_tree.addTopLevelItem(tree_item)

        self.dynamic_labels_tree.clear()
        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()
        self._mark_current_selections()

    def _on_typologie_double_clicked(self, item, column):
        """Double-clic sur typologie pour ajouter au batch"""
        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return
    
        full_text = item.text(0)
        typ_name = full_text.split(' (')[0] if ' (' in full_text else full_text
        
        typologie = self._find_typologie_by_name(typ_name)
        if not typologie:
            return
    
        # Construire la sélection
        selection = {
            'level': 'typologie',
            'typologie': typ_name,
            'taxonomy': '',
            'root': '',
            'parent': '',
            'child_path': [],
            'child': '',
            'display': typ_name
        }
    
        self._toggle_single_selection_in_batch(selection)

    def _on_taxonomy_item_clicked(self, item, column):
        """Gérer le clic sur taxonomy - Double-clic pour ajouter au batch"""
        if column == 1:
            return

        self.context_taxonomy_tree.setCurrentItem(item)

        cluster = item.data(0, Qt.UserRole)
        if not cluster:
            return

        self._context_navigation['taxonomy'] = cluster
        self._context_navigation['root'] = None
        self._context_navigation['parent'] = None
        self._context_navigation['child_path'] = []
        self._context_navigation['current_level'] = 'taxonomy'

        # Charger les root labels
        self.dynamic_labels_tree.clear()
        for root in cluster.get('root_labels', []):
            root_name = root.get('name', '')
            if root_name:
                sample_count = self._count_root_samples(root)
                display_text = f"{root_name} ({sample_count})"

                tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                tree_item.setData(0, Qt.UserRole, {
                    'level': 'root',
                    'data': root,
                    'cluster': cluster,
                    'has_children': bool(root.get('parent_labels', [])),
                    'name': root_name
                })

                # ✅ MODIFICATION: Checkbox uniquement pour éléments sans enfants
                has_children = bool(root.get('parent_labels', []))

                if not has_children:
                    # Élément feuille : checkbox visible
                    checkbox = self._create_styled_checkbox()
                    self.dynamic_labels_tree.setItemWidget(tree_item, 1, checkbox)
                    checkbox.stateChanged.connect(
                        lambda state, it=tree_item: self._on_checkbox_changed(it, 'root')
                    )

                self.dynamic_labels_tree.addTopLevelItem(tree_item)

        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()

    def _on_taxonomy_double_clicked(self, item, column):
        """Double-clic sur taxonomy pour ajouter au batch"""
        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return

        cluster = item.data(0, Qt.UserRole)
        if not cluster:
            return

        nav = self._context_navigation
        if not nav.get('typologie'):
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie de contexte."
            )
            return

        typologie_name = nav['typologie'].get('name', '')
        cluster_name = cluster.get('name', '')

        # Construire la sélection
        selection = {
            'level': 'taxonomy',
            'typologie': typologie_name,
            'taxonomy': cluster_name,
            'root': '',
            'parent': '',
            'child_path': [],
            'child': '',
            'display': f"{typologie_name} / {cluster_name}"
        }

        self._toggle_single_selection_in_batch(selection)

    def _on_label_item_clicked(self, item, column):
        """Gérer le clic sur labels dynamiques : colonne 0 = navigation, colonne 1 = ignoré"""
        if column == 1:  # Clic sur checkbox - géré par stateChanged
            return

        # Clic sur texte = sélectionner l'item pour la navigation
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        # Sélectionner visuellement l'item
        self.dynamic_labels_tree.setCurrentItem(item)

        # Mettre à jour les boutons de navigation
        if item_data.get('has_children', False):
            self.labels_down_btn.setEnabled(True)
        else:
            self.labels_down_btn.setEnabled(False)

    def _replace_combination_in_modification_mode(self, item, level):
        """Remplacer la combinaison en mode modification"""
        if not self._modification_in_progress:
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        # Construire la nouvelle sélection
        new_selection = self._build_selection_from_item_data(item_data, level)
        if not new_selection:
            logger.error("❌ Impossible de construire la nouvelle sélection")
            return

        # Stocker temporairement la nouvelle sélection
        self._modification_in_progress['new_selection'] = new_selection

        # Activer le bouton de sauvegarde
        self.save_modification_btn.setEnabled(True)

        logger.info(f"✅ Nouvelle sélection préparée: {new_selection.get('display', 'N/A')}")

    def _build_selection_from_item_data(self, item_data, level):
        """Construire une sélection depuis les données d'un item"""
        try:
            nav = self._context_navigation

            if level == 'typologie':
                # ✅ Pour typologie, item_data EST l'objet typologie complet
                # Pas besoin de vérifier nav.get('typologie') car on est en train de le créer
                return {
                    'level': 'typologie',
                    'typologie': item_data.get('name', ''),
                    'taxonomy': '',
                    'root': '',
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': item_data.get('name', '')
                }

            # ✅ Pour les autres niveaux, vérifier que la navigation a une typologie
            if not nav.get('typologie'):
                logger.error("❌ Pas de typologie dans la navigation")
                return None

            typologie_name = nav['typologie'].get('name', '')

            if level == 'taxonomy':
                # Pour taxonomy
                return {
                    'level': 'taxonomy',
                    'typologie': typologie_name,
                    'taxonomy': item_data.get('name', ''),
                    'root': '',
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': f"{typologie_name} / {item_data.get('name', '')}"
                }

            elif level == 'root':
                root = item_data.get('data', {})
                taxonomy_name = nav.get('taxonomy', {}).get('name', '')
                return {
                    'level': 'root',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', ''),
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': f"{typologie_name} / {taxonomy_name} / {root.get('name', '')}"
                }

            elif level == 'parent':
                parent = item_data.get('data', {})
                root = item_data.get('root', {})
                taxonomy_name = nav.get('taxonomy', {}).get('name', '')
                return {
                    'level': 'parent',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', ''),
                    'parent': parent.get('name', ''),
                    'child_path': [],
                    'child': '',
                    'display': f"{typologie_name} / {taxonomy_name} / {root.get('name', '')} / {parent.get('name', '')}"
                }

            elif level == 'child':
                child_path = item_data.get('path', [])
                if not child_path:
                    return None

                taxonomy_name = nav.get('taxonomy', {}).get('name', '')
                root = nav.get('root', {})
                parent = nav.get('parent', {})

                display_parts = [typologie_name]
                if taxonomy_name:
                    display_parts.append(taxonomy_name)
                if root:
                    display_parts.append(root.get('name', ''))
                if parent:
                    display_parts.append(parent.get('name', ''))
                display_parts.append(' > '.join(child_path))

                return {
                    'level': 'child',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', '') if root else '',
                    'parent': parent.get('name', '') if parent else '',
                    'child_path': child_path,
                    'child': child_path[-1] if child_path else '',
                    'display': ' / '.join(display_parts)
                }

            return None

        except Exception as e:
            logger.error(f"❌ Erreur construction sélection: {e}")
            return None

    # ========== NAVIGATION ==========

    def _on_typologie_clicked(self, item):
        """✅ VERSION MODIFIÉE : Charger les taxonomies avec checkboxes"""
        if not item:
            return
        typ_name = item.text()
        typologie = self._find_typologie_by_name(typ_name)
        if not typologie:
            return

        self._context_navigation = {
            'typologie': typologie, 
            'taxonomy': None, 
            'root': None, 
            'parent': None, 
            'child_path': [],
            'current_level': 'typologie'
        }

        # ✅ Charger les taxonomies avec checkboxes DÉSACTIVÉES
        self.context_taxonomy_list.clear()
        for cluster in typologie.get('taxonomy_clusters', []):
            cluster_name = cluster.get('name', '')
            if cluster_name:
                it = QtWidgets.QListWidgetItem(cluster_name)
                it.setData(Qt.UserRole, cluster)
                # ✅ Ajouter checkbox DÉSACTIVÉE par défaut
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                self.context_taxonomy_list.addItem(it)

        self.dynamic_labels_list.clear()
        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()
        self._mark_current_selections()


    def _on_child_selection_changed(self):
        """Appelé quand la sélection change dans la liste des enfants"""
        self._update_child_navigation_buttons()

    def _update_child_navigation_buttons(self):
        """
        Met à jour l'état des boutons avec feedback visuel
        """
        depth = len(self._context_navigation.get('child_path', []))
        self.child_up_btn.setEnabled(depth > 0)

        # Bouton descendre : UN SEUL item sélectionné ET il a des enfants
        selected_items = self.context_child_list.selectedItems()
        can_descend = False

        if len(selected_items) == 1:
            child_data = selected_items[0].data(Qt.UserRole)
            if child_data:
                can_descend = child_data.get('has_children', False)

        self.child_down_btn.setEnabled(can_descend)

        # ✅ Feedback visuel dans le tooltip
        if len(selected_items) > 1:
            self.child_down_btn.setToolTip(
                "⚠️ Sélectionnez UN SEUL élément pour descendre\n"
                "Pour ajouter plusieurs éléments : utilisez le double-clic"
            )
        elif len(selected_items) == 1 and not can_descend:
            self.child_down_btn.setToolTip(
                "⚠️ Cet élément n'a pas d'enfants\n"
                "Vous pouvez l'ajouter au batch avec un double-clic"
            )
        else:
            self.child_down_btn.setToolTip("Descendre dans l'élément sélectionné")

        logger.debug(f"Boutons nav: Remonter={depth > 0}, Descendre={can_descend}")

    def _navigate_down_child(self):
        """
        Bouton "Descendre" : navigation explicite dans la hiérarchie
        """
        selected_items = self.context_child_list.selectedItems()

        if not selected_items:
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Veuillez sélectionner un élément pour naviguer."
            )
            return

        if len(selected_items) > 1:
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Veuillez sélectionner UN SEUL élément pour descendre dans la hiérarchie.\n"
                "Pour ajouter plusieurs éléments au batch, utilisez le double-clic ou le bouton '+ Ajouter'."
            )
            return

        current_item = selected_items[0]
        child_data = current_item.data(Qt.UserRole)

        if not child_data:
            logger.warning("Item sans données")
            return

        child = child_data.get('child')
        if not child or not child.get('children'):
            QtWidgets.QMessageBox.information(
                self, "Info", 
                "Cet élément n'a pas d'enfants.\n"
                "Vous pouvez l'ajouter au batch avec un double-clic."
            )
            return

        # ✅ Navigation : descendre d'un niveau
        child_name = child.get('name', '')
        logger.info(f"Navigation vers les enfants de: {child_name}")

        self._context_navigation['child_path'].append(child_name)
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        # Charger le niveau suivant
        self._load_children_at_level(
            child.get('children', []),
            child_data.get('cluster'),
            child_data.get('root'),
            child_data.get('parent')
        )

        self._update_child_breadcrumb()
        self._update_child_navigation_buttons()

    def _get_item_path_for_batch(self, level, data, item=None):
        """Génère une clé de chemin unique pour un élément."""
        nav = self._context_navigation

        if level == 'typologie' and item:
            return f"typologie/{item.text()}"

        elif level == 'taxonomy' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{data.get('name', '')}"

        elif level == 'root' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = data.get('cluster', {}).get('name', '')
            root_name = data.get('root', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root_name}"

        elif level == 'parent' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = data.get('cluster', {}).get('name', '')
            root_name = data.get('root', {}).get('name', '')
            parent_name = data.get('parent', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root_name}/parent/{parent_name}"

        elif level == 'child' and data:
            # ✅ CORRECTION : Utiliser exactement le même format que _generate_path_key_from_selection
            typologie = data.get('typologie', '')
            child_path = data.get('path', [])

            if not typologie or not child_path:
                logger.warning(f"❌ Données incomplètes pour child: typ={typologie}, path={child_path}")
                return None

            return f"typologie/{typologie}/child_path/{' > '.join(child_path)}"

        return None
    
    def _mark_current_selections(self):
        """Marquer les checkboxes selon la combinaison en cours"""
        # Construire un set avec les path_keys de la combinaison en cours
        current_keys = set(ctx.get('path_key') for ctx in self.current_combination.get('contexts', []) if ctx.get('path_key'))

        self._mark_tree_checkboxes(self.context_typologie_tree, 'typologie', current_keys)
        self._mark_tree_checkboxes(self.context_taxonomy_tree, 'taxonomy', current_keys)

        current_level = self._context_navigation.get('current_level', '')
        if current_level in ['root', 'parent', 'child', 'taxonomy']:
            self._mark_tree_checkboxes(self.dynamic_labels_tree, current_level, current_keys)

    def _mark_tree_checkboxes(self, tree_widget, level, batch_keys):
        """Cocher/décocher les checkboxes selon le batch"""
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            data = item.data(0, Qt.UserRole)

            # Construire la clé de chemin
            if level == 'child' and data:
                typologie = data.get('typologie', '')
                child_path = data.get('path', [])
                if typologie and child_path:
                    path_key = f"typologie/{typologie}/child_path/{' > '.join(child_path)}"
                else:
                    path_key = None
            else:
                path_key = self._get_item_path_for_batch_tree(level, data, item)

            is_selected = path_key in batch_keys if path_key else False

            # Cocher/décocher la checkbox
            checkbox = tree_widget.itemWidget(item, 1)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(is_selected)
                checkbox.blockSignals(False)

    def _get_item_path_for_batch_tree(self, level, data, item):
        """Générer une clé de chemin unique pour un élément tree"""
        nav = self._context_navigation

        if level == 'typologie' and data:
            return f"typologie/{data.get('name', '')}"

        elif level == 'taxonomy' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{data.get('name', '')}"

        elif level == 'root' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = nav.get('taxonomy', {}).get('name', '')
            root_name = data.get('data', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root_name}"

        elif level == 'parent' and data:
            typ_name = nav.get('typologie', {}).get('name', '')
            taxonomy_name = nav.get('taxonomy', {}).get('name', '')
            root = data.get('root', {})
            parent_name = data.get('data', {}).get('name', '')
            return f"typologie/{typ_name}/taxonomy/{taxonomy_name}/root/{root.get('name', '')}/parent/{parent_name}"

        return None

    def _mark_list_items(self, list_widget, level, batch_keys):
        """✅ VERSION MODIFIÉE : Marquer les items avec checkboxes pour taxonomies"""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            data = item.data(Qt.UserRole)

            if level == 'child' and data:
                typologie = data.get('typologie', '')
                child_path = data.get('path', [])

                if typologie and child_path:
                    path_key = f"typologie/{typologie}/child_path/{' > '.join(child_path)}"
                else:
                    path_key = None
            else:
                path_key = self._get_item_path_for_batch(level, data, item)

            is_selected = path_key in batch_keys if path_key else False

            # ✅ Pour les taxonomies, cocher/décocher la checkbox au lieu d'utiliser _update_item_icon
            if level == 'taxonomy':
                if is_selected:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            else:
                self._update_item_icon(item, is_selected)


    def _on_taxonomy_clicked(self, item):
        """✅ NOUVELLE VERSION : Gérer le clic sur taxonomy avec checkbox"""
        if not item:
            return

        cluster = item.data(Qt.UserRole)
        if not cluster:
            return

        # ✅ Toggle la checkbox
        current_state = item.checkState()
        new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
        item.setCheckState(new_state)

        # Charger les root labels dans la liste dynamique pour navigation
        self._context_navigation['taxonomy'] = cluster
        self._context_navigation['root'] = None
        self._context_navigation['parent'] = None
        self._context_navigation['child_path'] = []
        self._context_navigation['current_level'] = 'taxonomy'

        self.dynamic_labels_list.clear()
        for root in cluster.get('root_labels', []):
            root_name = root.get('name', '')
            if root_name:
                it = QtWidgets.QListWidgetItem(f"{root_name}")
                it.setData(Qt.UserRole, {
                    'level': 'root',
                    'data': root,
                    'cluster': cluster,
                    'has_children': bool(root.get('parent_labels', [])),
                    'name': root_name
                })
                self.dynamic_labels_list.addItem(it)

        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()

    def _on_root_clicked(self, item):
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        root = data.get('root')
        cluster = data.get('cluster')
        
        self._context_navigation['root'] = root
        self._context_navigation['parent'] = None
        self._context_navigation['child_path'] = []
        
        self.context_parent_list.clear()
        for parent in root.get('parent_labels', []):
            parent_name = parent.get('name', '')
            if parent_name:
                it = QtWidgets.QListWidgetItem(parent_name)
                it.setData(Qt.UserRole, {'parent': parent, 'root': root, 'cluster': cluster})
                self.context_parent_list.addItem(it)
        
        self.context_child_list.clear()
        self._update_navigation_breadcrumb()
        self._mark_current_selections()

    def _on_parent_clicked(self, item):
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        parent = data.get('parent')
        root = data.get('root')
        cluster = data.get('cluster')
        
        self._context_navigation['parent'] = parent
        self._context_navigation['child_path'] = []
        
        self._load_children_at_level(parent.get('children', []), cluster, root, parent)
        self._update_navigation_breadcrumb()
        self._update_child_breadcrumb()
        self._mark_current_selections()

    def _on_child_clicked(self, item):
        """
        Clic simple sur un enfant = sélection uniquement
        CTRL+Clic = sélection multiple
        """
        if not item:
            return

        # ✅ Permettre la sélection libre sans interférer
        logger.debug(f"Sélection enfant: {item.text()}")

        # Mise à jour des boutons de navigation basée sur la sélection
        self._update_child_navigation_buttons()

        # ✅ NOUVEAU : Marquer visuellement si déjà dans le batch
        self._mark_current_selections()

    def _on_child_double_clicked(self, item):
        """
        Double-clic sur enfant : ajouter/retirer DIRECTEMENT du batch
        Sans passer par _get_all_selections() qui peut échouer
        """
        if not item:
            return

        logger.info(f"=== Double-clic sur enfant: {item.text()} ===")

        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return

        # ✅ Récupérer DIRECTEMENT les données de l'item
        child_data = item.data(Qt.UserRole)

        if not child_data:
            logger.error("❌ Pas de données Qt.UserRole sur l'item")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                "Impossible de récupérer les données de l'élément."
            )
            return

        # ✅ Construire la sélection directement
        selection = self._build_selection_from_child_data(child_data)

        if not selection:
            logger.error("❌ Impossible de construire la sélection")
            return

        # ✅ Toggle dans le batch
        self._toggle_single_selection_in_batch(selection)

    def _build_selection_from_child_data(self, child_data):
        """
        Construit un dictionnaire de sélection depuis les données d'un enfant
        VERSION SÉCURISÉE CORRIGÉE
        """
        try:
            child = child_data.get('child', {})
            child_path = child_data.get('path', [])

            if not child_path:
                logger.error("❌ Pas de chemin dans child_data")
                return None

            # ✅ CORRECTION : Toujours récupérer la typologie depuis child_data
            # car elle est stockée lors du _load_children_at_level
            typologie = child_data.get('typologie', '')

            if not typologie:
                logger.error("❌ Pas de typologie dans child_data!")
                logger.debug(f"child_data: {child_data}")
                return None

            child_name = child_path[-1] if child_path else child.get('name', '')

            # Navigation actuelle
            nav = self._context_navigation

            selection = {
                'level': 'child',
                'typologie': typologie,  # ✅ Typologie garantie depuis child_data
                'taxonomy': nav.get('taxonomy', {}).get('name', ''),
                'root': nav.get('root', {}).get('name', ''),
                'parent': nav.get('parent', {}).get('name', ''),
                'child_path': child_path,
                'child': child_name,
                'display': self._build_display_text_from_nav(typologie, child_path)
            }

            logger.debug(f"✅ Sélection construite: {selection['display']}")
            logger.debug(f"   Path key sera: typologie/{typologie}/child_path/{' > '.join(child_path)}")

            return selection

        except Exception as e:
            logger.error(f"❌ Erreur construction sélection: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
    def _build_display_text_from_nav(self, typologie, child_path):
        """
        Construit le texte d'affichage depuis la navigation actuelle
        """
        nav = self._context_navigation
        parts = [typologie]

        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', ''))
        if nav.get('root'):
            parts.append(nav['root'].get('name', ''))
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', ''))

        if child_path:
            parts.append(' > '.join(child_path))

        return ' / '.join(parts)

    def _build_display_text(self, child_data, child_path):
        """
        Construit le texte d'affichage pour une sélection d'enfant
        """
        nav = self._context_navigation
        parts = []

        # Typologie
        typ_name = child_data.get('typologie', '') or nav.get('typologie', {}).get('name', '')
        if typ_name:
            parts.append(typ_name)

        # Taxonomy
        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', ''))

        # Root
        if nav.get('root'):
            parts.append(nav['root'].get('name', ''))

        # Parent
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', ''))

        # Chemin complet des enfants
        if child_path:
            parts.append(' > '.join(child_path))

        return ' / '.join(parts)
    
    def _load_children_at_level(self, children_list, cluster, root, parent):
        """
        Charge les enfants avec TOUTES les données nécessaires
        VERSION AVEC VÉRIFICATION TYPOLOGIE
        """
        logger.debug(f"=== _load_children_at_level ===")

        nav = self._context_navigation
        typologie_name = nav.get('typologie', {}).get('name', '') if nav.get('typologie') else ''

        if not typologie_name:
            logger.error("❌ CRITIQUE: Pas de typologie dans la navigation!")
            logger.debug(f"Navigation state: {nav}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                "Impossible de charger les enfants : typologie non définie."
            )
            return

        logger.info(f"Chargement de {len(children_list)} enfants pour typologie: {typologie_name}")

        self.context_child_list.clear()

        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                continue
            
            current_path = nav.get('child_path', []) + [child_name]
            has_children = bool(child.get('children'))
            prefix = "▶" if has_children else "•"

            it = QtWidgets.QListWidgetItem(f"{prefix} {child_name}")

            # ✅ Stocker TOUTES les infos nécessaires
            item_data = {
                'child': child,
                'parent': parent,
                'root': root,
                'cluster': cluster,
                'path': current_path,
                'typologie': typologie_name,  # ✅ CRITIQUE
                'has_children': has_children,
                'original_name': child_name,
                'prefix': prefix
            }

            it.setData(Qt.UserRole, item_data)
            self.context_child_list.addItem(it)

            logger.debug(f"  ✅ {child_name} | path={current_path} | typ={typologie_name}")

        self._update_child_navigation_buttons()
        self._mark_current_selections()


    def _toggle_single_selection_in_batch(self, selection):
        """Version adaptée pour le nouveau système multi-contextes"""
        level = selection.get('level', '')
        self._toggle_context_in_current_combination(selection, None, level)

    def _update_specific_child_item(self, path_key, was_added):
        # ✅ CORRECTION : Utiliser dynamic_labels_tree au lieu de dynamic_labels_list
        for i in range(self.dynamic_labels_tree.topLevelItemCount()):
            item = self.dynamic_labels_tree.topLevelItem(i)
            item_data = item.data(0, Qt.UserRole)

            if not item_data:
                continue

            # Build the path_key for this item
            item_path_key = self._generate_path_key_from_item_data(item_data)

            if item_path_key == path_key:
                logger.debug(f"🔄 Mise à jour directe de l'item: {item.text(0)}")
                logger.debug(f"   was_added={was_added} (True=ajouté, False=retiré)")

                # Update the checkbox
                checkbox = self.dynamic_labels_tree.itemWidget(item, 1)
                if checkbox:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(was_added)
                    checkbox.blockSignals(False)

                # Force repaint
                self.dynamic_labels_tree.update(self.dynamic_labels_tree.indexFromItem(item))

                logger.debug(f"✅ Item mis à jour: is_selected={was_added}")
                break

    def _generate_path_key_from_item_data(self, item_data):
        """
        Generate path key from item data (for dynamic label items)
        """
        level = item_data.get('level', '')
        
        if level == 'root':
            nav = self._context_navigation
            typologie = nav.get('typologie', {}).get('name', '')
            taxonomy = nav.get('taxonomy', {}).get('name', '')
            root_name = item_data.get('data', {}).get('name', '')
            return f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root_name}"
        
        elif level == 'parent':
            nav = self._context_navigation
            typologie = nav.get('typologie', {}).get('name', '')
            taxonomy = nav.get('taxonomy', {}).get('name', '')
            root = item_data.get('root', {})
            parent_name = item_data.get('data', {}).get('name', '')
            return f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root.get('name', '')}/parent/{parent_name}"
        
        elif level == 'child':
            typologie = item_data.get('typologie', '')
            path = item_data.get('path', [])
            
            if not typologie or not path:
                return None
            
            return f"typologie/{typologie}/child_path/{' > '.join(path)}"
        
        return None

    def _generate_path_key_from_child_data(self, child_data):
        """
        Génère un path_key depuis les données d'un item enfant
        """
        typologie = child_data.get('typologie', '')
        path = child_data.get('path', [])

        if not typologie or not path:
            return None

        return f"typologie/{typologie}/child_path/{' > '.join(path)}"

    def toggle_batch_selection(self, item_path):
        """Toggle la sélection d'un item dans le batch"""
        if item_path in self.batch_selections:
            self.batch_selections.remove(item_path)
            logger.info(f"✅ RETIRÉ du batch: {item_path}")
        else:
            self.batch_selections.add(item_path)
            logger.info(f"✅ AJOUTÉ au batch: {item_path}")

        self.update_batch_visual_indicators()  # Mettre à jour les checkmarks
        self.update_batch_counter()

    def update_batch_visual_indicators(self):
        """Met à jour les indicateurs visuels (✔) pour tous les items"""
        def update_tree_item(item):
            item_path = self.get_item_full_path(item)
            text = self.tree.item(item, 'text')

            # Retirer l'ancien checkmark
            text = text.replace(' ✔', '').strip()

            # Ajouter le checkmark si dans le batch
            if item_path in self.batch_selections:
                text = f"{text} ✔"
                # Style visuel supplémentaire
                self.tree.item(item, text=text, tags=('in_batch',))
            else:
                self.tree.item(item, text=text, tags=())

            # Récursif pour les enfants
            for child in self.tree.get_children(item):
                update_tree_item(child)

        # Appliquer à tous les items racines
        for item in self.tree.get_children():
            update_tree_item(item)

        # Configurer le style pour les items dans le batch
        self.tree.tag_configure('in_batch', 
                               background='#E8F5E9',  # Vert clair
                               foreground='#2E7D32')  # Vert foncé
        
    def update_batch_counter(self):
        """Met à jour le compteur de sélections"""
        count = len(self.batch_selections)

        # Si vous avez un label pour afficher le compteur :
        if hasattr(self, 'batch_counter_label'):
            self.batch_counter_label.config(
                text=f"Sélectionnés: {count}"
            )

        logger.info(f"Interface mise à jour : {count} combinaison(s) au total")

    def _toggle_item_in_batch(self):
        """Toggle item in batch - FIXED VERSION using batch_table"""
        logger.info("=== _toggle_item_in_batch appelée ===")

        if not self.selected_master_typologie:
            logger.warning("Pas de typologie master sélectionnée")
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez sélectionner une typologie master.")
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')
        logger.info(f"Typologie master: {master_name}")

        # Récupérer les sélections
        selections = self._get_all_selections()
        logger.info(f"Nombre de sélections trouvées: {len(selections)}")

        if not selections:
            logger.warning("❌ Aucune sélection trouvée pour toggle!")
            QtWidgets.QMessageBox.information(
                self, 
                "Information", 
                "Aucun élément sélectionné. Veuillez sélectionner un élément dans la hiérarchie."
            )
            return

        # Pour chaque sélection
        toggled_count = 0
        for sel in selections:
            path_key = self._generate_path_key_from_selection(sel)
            context_display = sel['display']

            logger.debug(f"Traitement: {master_name} ⇒ {context_display}")
            logger.debug(f"Path key: {path_key}")

            # Chercher si cette combinaison existe déjà 
            existing_index = None
            for i, combo in enumerate(self.combinations):
                if combo.get('path_key') == path_key:
                    existing_index = i
                    break
                
            if existing_index is not None:
                # RETIRER du batch
                del self.combinations[existing_index]
                self.batch_table.removeRow(existing_index)

                # Réindexer les boutons
                for i in range(self.batch_table.rowCount()):
                    delete_btn = self.batch_table.cellWidget(i, 2)
                    if delete_btn:
                        delete_btn.clicked.disconnect()
                        delete_btn.clicked.connect(lambda checked, idx=i: self._remove_batch_row(idx))

                logger.info(f"✅ Combinaison RETIRÉE: {master_name} ⇒ {context_display}")
                toggled_count += 1
            else:
                # AJOUTER au batch
                combination = {
                    'master': {'name': master_name, 'data': self.selected_master_typologie},
                    'context': sel,
                    'display': f"{master_name} ⇒ {context_display}",
                    'path_key': path_key
                }
                self.combinations.append(combination)
                self._add_to_batch_table(master_name, context_display, combination)
                logger.info(f"✅ Combinaison AJOUTÉE: {master_name} ⇒ {context_display}")
                toggled_count += 1

        if toggled_count > 0:
            # Rafraîchir l'affichage
            self._update_stats()
            self._mark_current_selections()
            logger.info(f"✅ {toggled_count} élément(s) toggleé(s) avec succès")
        else:
            logger.warning("⚠️ Aucun élément n'a été toggleé")

    def _load_children_at_level(self, children_list, cluster, root, parent):
        """
        Charge les enfants avec TOUTES les données nécessaires
        VERSION CORRIGÉE - Stocke le texte original
        """
        logger.debug(f"=== _load_children_at_level ===")
        logger.debug(f"Nombre d'enfants: {len(children_list)}")
        logger.debug(f"Child path actuel: {self._context_navigation.get('child_path', [])}")

        self.context_child_list.clear()

        if not children_list:
            return

        # ✅ CRITIQUE : Récupérer la typologie depuis la navigation
        nav = self._context_navigation
        typologie_name = nav.get('typologie', {}).get('name', '') if nav.get('typologie') else ''

        if not typologie_name:
            logger.error("❌ Pas de typologie dans la navigation!")
            return

        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                logger.warning(f"⚠️ Enfant sans nom, ignoré")
                continue
            
            # ✅ Construire le chemin COMPLET
            current_path = self._context_navigation.get('child_path', []) + [child_name]

            # Affichage avec indicateur
            has_children = bool(child.get('children'))
            prefix = "▶" if has_children else "•"

            it = QtWidgets.QListWidgetItem(f"{prefix} {child_name}")

            # ✅✅✅ CORRECTION CRITIQUE : Stocker le nom original et le préfixe
            item_data = {
                'child': child,
                'parent': parent,
                'root': root,
                'cluster': cluster,
                'path': current_path,
                'typologie': typologie_name,
                'has_children': has_children,
                'original_name': child_name,  # ✅ AJOUT
                'prefix': prefix  # ✅ AJOUT
            }

            it.setData(Qt.UserRole, item_data)
            self.context_child_list.addItem(it)

            logger.debug(f"✅ Enfant ajouté: {child_name}")
            logger.debug(f"   Typologie: {typologie_name}")
            logger.debug(f"   Path: {current_path}")

        self._update_child_navigation_buttons()
        self._mark_current_selections()

    def _navigate_up_child(self):
        """Remonte d'un niveau dans la hiérarchie des enfants - VERSION CORRIGÉE"""
        logger.info("=== Remontée d'un niveau enfant ===")

        if not self._context_navigation['child_path']:
            logger.warning("Déjà au niveau racine, impossible de remonter")
            return

        # Retirer le dernier élément du chemin
        removed = self._context_navigation['child_path'].pop()
        logger.info(f"Retrait du chemin: {removed}")
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        parent = self._context_navigation.get('parent')
        if not parent:
            logger.warning("Pas de parent défini, vidage de la liste")
            self.context_child_list.clear()
            self._update_child_breadcrumb()
            self._mark_current_selections()
            return

        # Reconstruire la liste des enfants au niveau actuel
        current_children = parent.get('children', [])
        logger.debug(f"Démarrage depuis parent avec {len(current_children)} enfants")

        # Suivre le chemin pour retrouver le bon niveau
        for path_item in self._context_navigation['child_path']:
            logger.debug(f"Navigation vers: {path_item}")
            found = False
            for child in current_children:
                if child.get('name') == path_item:
                    current_children = child.get('children', [])
                    found = True
                    logger.debug(f"  -> Trouvé, {len(current_children)} enfants au niveau suivant")
                    break
            if not found:
                logger.warning(f"❌ Chemin '{path_item}' non trouvé!")
                break
            
        # Recharger la liste
        self._load_children_at_level(
            current_children,
            self._context_navigation.get('taxonomy'),
            self._context_navigation.get('root'),
            parent
        )
    def _navigate_up_child(self):
        """Remonte d'un niveau dans la hiérarchie des enfants"""
        logger.info("=== Remontée d'un niveau enfant ===")

        if not self._context_navigation['child_path']:
            logger.warning("Déjà au niveau racine, impossible de remonter")
            return

        # Retirer le dernier élément du chemin
        removed = self._context_navigation['child_path'].pop()
        logger.info(f"Retrait du chemin: {removed}")
        logger.debug(f"Nouveau child_path: {self._context_navigation['child_path']}")

        parent = self._context_navigation.get('parent')
        if not parent:
            logger.warning("Pas de parent défini, vidage de la liste")
            self.context_child_list.clear()
            self._update_child_breadcrumb()
            self._update_child_navigation_buttons()
            self._mark_current_selections()
            return

        # Reconstruire la liste des enfants au niveau actuel
        current_children = parent.get('children', [])
        logger.debug(f"Démarrage depuis parent avec {len(current_children)} enfants")

        # Suivre le chemin pour retrouver le bon niveau
        for path_item in self._context_navigation['child_path']:
            logger.debug(f"Navigation vers: {path_item}")
            found = False
            for child in current_children:
                if child.get('name') == path_item:
                    current_children = child.get('children', [])
                    found = True
                    logger.debug(f"  -> Trouvé, {len(current_children)} enfants au niveau suivant")
                    break
            if not found:
                logger.warning(f"❌ Chemin '{path_item}' non trouvé!")
                break
            
        # Recharger la liste
        self._load_children_at_level(
            current_children,
            self._context_navigation.get('taxonomy'),
            self._context_navigation.get('root'),
            parent
        )

        self._update_child_breadcrumb()
        self._update_child_navigation_buttons()
        self._update_child_breadcrumb()

    def _reset_navigation(self):
        self._context_navigation = {
            'typologie': None, 
            'taxonomy': None, 
            'root': None, 
            'parent': None, 
            'child_path': [],
            'current_level': ''
        }
        self.context_typologie_list.clearSelection()
        self.context_taxonomy_list.clear()
        self.dynamic_labels_list.clear()
        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()

    def _update_navigation_breadcrumb(self):
        parts = []
        nav = self._context_navigation
        if nav.get('typologie'):
            parts.append(nav['typologie'].get('name', '?'))
        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', '?'))
        if nav.get('root'):
            parts.append(nav['root'].get('name', '?'))
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', '?'))
        self.nav_breadcrumb.setText(" → ".join(parts) if parts else "Sélectionnez une typologie")

    def _update_child_breadcrumb(self):
        """Met à jour le breadcrumb de navigation dans les enfants"""
        path = self._context_navigation.get('child_path', [])
        depth = len(path)

        if depth == 0:
            self.child_breadcrumb.setText("Niveau racine (enfants directs)")
        else:
            # Afficher les 2 derniers niveaux si plus de 2
            path_str = " → ".join(path[-2:]) if depth > 2 else " → ".join(path)
            if depth > 2:
                path_str = "... → " + path_str
            self.child_breadcrumb.setText(f"{path_str} (niveau {depth + 1})")

    # ========== BATCH ==========

    def _get_all_selections(self):
        """✅ VERSION MODIFIÉE : Récupérer les taxonomies COCHÉES"""
        selections = []
        nav = self._context_navigation

        logger.debug(f"=== _get_all_selections ===")

        typ_name = nav.get('typologie').get('name') if nav.get('typologie') else None
        logger.debug(f"Navigation state: typ={typ_name}")

        # LABELS DYNAMIQUES - Priorité 1
        dynamic_items = self.dynamic_labels_list.selectedItems()
        logger.debug(f"Items dynamiques sélectionnés: {len(dynamic_items)}")

        if dynamic_items:
            for item in dynamic_items:
                item_data = item.data(Qt.UserRole)
                if not item_data:
                    continue
                
                selection = self._build_selection_from_label_item(item_data)
                if selection:
                    selections.append(selection)
                    logger.debug(f"✅ Item ajouté: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) depuis les labels dynamiques")
            return selections

        # ✅ TAXONOMY - Priorité 2 : SEULEMENT LES COCHÉES
        for i in range(self.context_taxonomy_list.count()):
            item = self.context_taxonomy_list.item(i)

            # ✅ Vérifier si la checkbox est cochée
            if item.checkState() != Qt.Checked:
                continue

            data = item.data(Qt.UserRole)
            if not data:
                continue
            
            if not nav.get('typologie'):
                continue
            
            display_parts = []
            if nav.get('typologie'):
                display_parts.append(nav['typologie'].get('name', ''))
            display_parts.append(data.get('name', ''))

            selection = {
                'level': 'taxonomy',
                'typologie': nav.get('typologie', {}).get('name', ''),
                'taxonomy': data.get('name', ''),
                'root': '',
                'parent': '',
                'child_path': [],
                'child': '',
                'display': ' / '.join(display_parts)
            }
            selections.append(selection)
            logger.debug(f"✅ Taxonomy cochée ajoutée: {selection['display']}")

        if selections:
            logger.info(f"✅ {len(selections)} sélection(s) de taxonomies cochées validée(s)")
            return selections

        # TYPOLOGIE - Priorité 3
        typ_items = self.context_typologie_list.selectedItems()
        logger.debug(f"Typologies sélectionnées: {len(typ_items)}")

        if typ_items:
            for item in typ_items:
                typ_name = item.text()
                selection = {
                    'level': 'typologie',
                    'typologie': typ_name,
                    'taxonomy': '',
                    'root': '',
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': typ_name
                }
                selections.append(selection)
                logger.debug(f"✅ Typologie ajoutée: {selection['display']}")

            logger.info(f"✅ {len(selections)} sélection(s) de typologies validée(s)")
            return selections

        logger.warning("⚠️ Aucune sélection trouvée à aucun niveau!")
        return selections

    def _add_selected_to_batch(self):
        """Add selected items to batch - FIXED VERSION using batch_table"""
        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(self, "Attention", "Veuillez sélectionner une typologie master.")
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')
        added_count = 0

        for sel in self._get_all_selections():
            # Générer la clé de chemin pour cette sélection
            path_key = self._generate_path_key_from_selection(sel)
            context_display = sel['display']

            # Vérifier si existe déjà
            exists = any(combo.get('path_key') == path_key for combo in self.combinations)

            if not exists:
                combination = {
                    'master': {'name': master_name, 'data': self.selected_master_typologie},
                    'context': sel,
                    'display': f"{master_name} ⇒ {context_display}",
                    'path_key': path_key
                }
                self.combinations.append(combination)
                self._add_to_batch_table(master_name, context_display, combination)
                added_count += 1

        if added_count > 0:
            self._update_stats()
            self._mark_current_selections()
            logger.info(f"{added_count} combinaison(s) ajoutée(s)")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Aucune nouvelle combinaison (doublons ou sélection vide).")

    def _generate_path_key_from_selection(self, sel):
        """
        Génère une clé de chemin unique - VERSION CORRIGÉE
        """
        level = sel.get('level')
        typologie = sel.get('typologie', '')

        logger.debug(f"Génération path_key pour niveau: {level}")
        logger.debug(f"  Typologie: {typologie}")

        if level == 'typologie':
            path_key = f"typologie/{typologie}"

        elif level == 'taxonomy':
            taxonomy = sel.get('taxonomy', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}"

        elif level == 'root':
            taxonomy = sel.get('taxonomy', '')
            root = sel.get('root', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root}"

        elif level == 'parent':
            taxonomy = sel.get('taxonomy', '')
            root = sel.get('root', '')
            parent = sel.get('parent', '')
            path_key = f"typologie/{typologie}/taxonomy/{taxonomy}/root/{root}/parent/{parent}"

        elif level == 'child':
            # ✅ Pour les enfants, utiliser le chemin COMPLET
            child_path = sel.get('child_path', [])

            if not child_path:
                logger.error("❌ child_path vide dans la sélection!")
                return None

            # Construire la clé avec le chemin complet
            path_key = f"typologie/{typologie}/child_path/{' > '.join(child_path)}"

            logger.debug(f"  Child path: {child_path}")
            logger.debug(f"  Path key: {path_key}")

        else:
            logger.error(f"❌ Niveau inconnu: {level}")
            path_key = None

        return path_key

    def _remove_from_batch(self):
        """Remove selected item from batch - FIXED VERSION"""
        current_row = self.batch_table.currentRow()
        if current_row >= 0:
            self._remove_batch_row(current_row)

    def _clear_batch(self):
        """Vider toutes les combinaisons"""
        if self.batch_table.rowCount() == 0 and not self.current_combination.get('contexts', []):
            return

        if QtWidgets.QMessageBox.question(
            self, "Confirmation", 
            "Vider toutes les combinaisons?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            self.batch_table.setRowCount(0)
            self.combinations = []
            self.current_combination = {
                'contexts': [],
                'master': self.selected_master_typologie
            }
            self.current_combination_index = 0
            self._update_stats()
            self._update_current_combo_label()
            self._mark_current_selections()
            self._reset_all_hierarchy_colors()

    def _on_label_clicked(self, item):
        """Gestion des clics sur la liste dynamique"""
        if not item:
            return

        self._update_label_navigation_buttons()
        self._mark_current_selections()

    def _on_label_double_clicked(self, item, column):
        """Double-clic sur label pour ajouter au batch"""
        if not self.selected_master_typologie:
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        level = item_data.get('level', '')

        # Construire la sélection selon le niveau
        selection = self._build_selection_from_item_data(item_data, level)
        if selection:
            self._toggle_single_selection_in_batch(selection)

        elif level == 'parent':
            parent = item_data.get('data', {})
            root = item_data.get('root', {})
            cluster = item_data.get('cluster', {})

            self._context_navigation['parent'] = parent
            self._context_navigation['current_level'] = 'parent'
            self._context_navigation['child_path'] = []

            self._load_children_in_dynamic_list(
                parent.get('children', []),
                cluster,
                root,
                parent
            )

        elif level == 'child':
            child = item_data.get('data', {})
            child_path = item_data.get('path', [])

            if child and child.get('children'):
                self._context_navigation['child_path'] = child_path
                self._context_navigation['current_level'] = 'child'

                self._load_children_in_dynamic_list(
                    child.get('children', []),
                    self._context_navigation.get('taxonomy'),
                    self._context_navigation.get('root'),
                    self._context_navigation.get('parent')
                )

        self._update_labels_breadcrumb()
        self._update_label_navigation_buttons()

    def _on_label_selection_changed(self):
        """Mise à jour des boutons de navigation"""
        self._update_label_navigation_buttons()

    def _update_label_navigation_buttons(self):
        """Active/désactive les boutons selon le contexte"""
        current_level = self._context_navigation.get('current_level', '')
        child_path = self._context_navigation.get('child_path', [])

        # Bouton remonter : actif si on est dans une hiérarchie profonde
        can_go_up = len(child_path) > 0 or current_level in ['parent', 'child']
        self.labels_up_btn.setEnabled(can_go_up)

        # ✅ CORRECTION : Vérifier l'item SÉLECTIONNÉ (currentItem) au lieu de chercher les cochés
        selected_item = self.dynamic_labels_tree.currentItem()
        can_descend = False

        if selected_item:
            item_data = selected_item.data(0, Qt.UserRole)
            if item_data and item_data.get('has_children', False):
                can_descend = True

        self.labels_down_btn.setEnabled(can_descend)

    def _build_selection_from_label_item(self, item_data):
        """Construire une sélection depuis un item de la liste dynamique"""
        try:
            level = item_data.get('level', '')
            nav = self._context_navigation

            if not nav.get('typologie'):
                logger.error("❌ Pas de typologie dans la navigation")
                return None

            typologie_name = nav['typologie'].get('name', '')

            if level == 'root':
                root = item_data.get('data', {})
                taxonomy_name = nav.get('taxonomy', {}).get('name', '')

                return {
                    'level': 'root',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', ''),
                    'parent': '',
                    'child_path': [],
                    'child': '',
                    'display': f"{typologie_name} / {taxonomy_name} / {root.get('name', '')}"
                }

            elif level == 'parent':
                parent = item_data.get('data', {})
                root = item_data.get('root', {})
                taxonomy_name = nav.get('taxonomy', {}).get('name', '')

                return {
                    'level': 'parent',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', ''),
                    'parent': parent.get('name', ''),
                    'child_path': [],
                    'child': '',
                    'display': f"{typologie_name} / {taxonomy_name} / {root.get('name', '')} / {parent.get('name', '')}"
                }

            elif level == 'child':
                child_path = item_data.get('path', [])
                if not child_path:
                    return None

                taxonomy_name = nav.get('taxonomy', {}).get('name', '')
                root = nav.get('root', {})
                parent = nav.get('parent', {})

                child_name = child_path[-1] if child_path else ''

                display_parts = [typologie_name]
                if taxonomy_name:
                    display_parts.append(taxonomy_name)
                if root:
                    display_parts.append(root.get('name', ''))
                if parent:
                    display_parts.append(parent.get('name', ''))
                display_parts.append(' > '.join(child_path))

                return {
                    'level': 'child',
                    'typologie': typologie_name,
                    'taxonomy': taxonomy_name,
                    'root': root.get('name', '') if root else '',
                    'parent': parent.get('name', '') if parent else '',
                    'child_path': child_path,
                    'child': child_name,
                    'display': ' / '.join(display_parts)
                }

            return None

        except Exception as e:
            logger.error(f"❌ Erreur construction sélection: {e}")
            return None

    def _navigate_down_labels(self):
        """Descendre dans la hiérarchie - PAS de checkbox pour niveaux intermédiaires"""
        selected_item = self.dynamic_labels_tree.currentItem()

        if not selected_item:
            QtWidgets.QMessageBox.information(
                self, "Info",
                "Sélectionnez UN élément pour descendre (cliquez sur le texte)."
            )
            return

        item_data = selected_item.data(0, Qt.UserRole)

        if not item_data or not item_data.get('has_children'):
            QtWidgets.QMessageBox.information(
                self, "Info",
                "Cet élément n'a pas d'enfants."
            )
            return

        level = item_data.get('level', '')

        if level == 'root':
            root = item_data.get('data', {})
            cluster = item_data.get('cluster', {})

            self._context_navigation['root'] = root
            self._context_navigation['current_level'] = 'root'

            self.dynamic_labels_tree.clear()
            for parent in root.get('parent_labels', []):
                parent_name = parent.get('name', '')
                if parent_name:
                    sample_count = self._count_parent_samples(parent)
                    display_text = f"{parent_name} ({sample_count})"

                    tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                    tree_item.setData(0, Qt.UserRole, {
                        'level': 'parent',
                        'data': parent,
                        'root': root,
                        'cluster': cluster,
                        'has_children': bool(parent.get('children', [])),
                        'name': parent_name
                    })

                    # ✅ MODIFICATION: Checkbox uniquement pour éléments sans enfants
                    has_children = bool(parent.get('children', []))

                    if not has_children:
                        # Élément feuille : checkbox visible
                        checkbox = self._create_styled_checkbox()
                        self.dynamic_labels_tree.setItemWidget(tree_item, 1, checkbox)
                        checkbox.stateChanged.connect(
                            lambda state, it=tree_item: self._on_checkbox_changed(it, 'parent')
                        )

                    self.dynamic_labels_tree.addTopLevelItem(tree_item)

    def _navigate_up_labels(self):
        """Remonter dans la hiérarchie avec compteurs"""
        current_level = self._context_navigation.get('current_level', '')
        child_path = self._context_navigation.get('child_path', [])

        if child_path:
            child_path.pop()
            self._context_navigation['child_path'] = child_path

            if child_path:
                parent = self._context_navigation.get('parent', {})
                current_children = parent.get('children', [])

                for path_item in child_path:
                    for child in current_children:
                        if child.get('name') == path_item:
                            current_children = child.get('children', [])
                            break
                        
                self._load_children_in_dynamic_list(
                    current_children,
                    self._context_navigation.get('taxonomy'),
                    self._context_navigation.get('root'),
                    parent
                )
            else:
                parent = self._context_navigation.get('parent', {})
                self._load_children_in_dynamic_list(
                    parent.get('children', []),
                    self._context_navigation.get('taxonomy'),
                    self._context_navigation.get('root'),
                    parent
                )

        elif current_level == 'child':
            root = self._context_navigation.get('root', {})
            cluster = self._context_navigation.get('taxonomy', {})

            self._context_navigation['parent'] = None
            self._context_navigation['current_level'] = 'root'

            self.dynamic_labels_tree.clear()
            for parent in root.get('parent_labels', []):
                parent_name = parent.get('name', '')
                if parent_name:
                    sample_count = self._count_parent_samples(parent)
                    display_text = f"{parent_name} ({sample_count})"

                    tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                    tree_item.setData(0, Qt.UserRole, {
                        'level': 'parent',
                        'data': parent,
                        'root': root,
                        'cluster': cluster,
                        'has_children': bool(parent.get('children', [])),
                        'name': parent_name
                    })

                    checkbox = self._create_styled_checkbox()
                    self.dynamic_labels_tree.addTopLevelItem(tree_item)
                    self.dynamic_labels_tree.setItemWidget(tree_item, 1, checkbox)
                    checkbox.stateChanged.connect(
                        lambda state, it=tree_item: self._on_checkbox_changed(it, 'parent')
                    )

        elif current_level == 'parent':
            cluster = self._context_navigation.get('taxonomy', {})

            self._context_navigation['root'] = None
            self._context_navigation['parent'] = None
            self._context_navigation['current_level'] = 'taxonomy'

            self.dynamic_labels_tree.clear()
            for root in cluster.get('root_labels', []):
                root_name = root.get('name', '')
                if root_name:
                    sample_count = self._count_root_samples(root)
                    display_text = f"{root_name} ({sample_count})"

                    tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                    tree_item.setData(0, Qt.UserRole, {
                        'level': 'root',
                        'data': root,
                        'cluster': cluster,
                        'has_children': bool(root.get('parent_labels', [])),
                        'name': root_name
                    })

                    checkbox = self._create_styled_checkbox()
                    self.dynamic_labels_tree.addTopLevelItem(tree_item)
                    self.dynamic_labels_tree.setItemWidget(tree_item, 1, checkbox)
                    checkbox.stateChanged.connect(
                        lambda state, it=tree_item: self._on_checkbox_changed(it, 'root')
                    )

        self._update_labels_breadcrumb()
        self._update_label_navigation_buttons()

    def _permanent_clear_batch(self):
        """Efface définitivement tous les batches et combinaisons avec confirmation UI."""
        if not self.project_manager.current_project_name:
            QtWidgets.QMessageBox.warning(self, tr("Aucun projet"), "Aucun projet sélectionné.")
            return

        # Dialogue de confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation de Suppression",
            f"Êtes-vous sûr de vouloir effacer définitivement tous les batches et leurs combinaisons pour le projet '{self.project_manager.current_project_name}' ?\n\nCette action est irréversible et supprimera toutes les données sauvegardées.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            success = self.project_manager.permanent_delete_batches_and_combinations(
                confirm_callback=None  # Déjà confirmé via dialogue
            )
            if success:
                # Réinitialiser l'UI après suppression
                self._clear_batch_ui()
                self.batch_status_label.setText("Tous les batches effacés définitivement")
                self.batch_status_label.setStyleSheet("color: #e74c3c; font-size: 9px; font-style: italic; padding: 3px;")
                QtWidgets.QMessageBox.information(self, "Succès", "Tous les batches et combinaisons ont été effacés définitivement.")
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la suppression. Vérifiez les logs.")

    def _clear_batch_ui(self):
        """Réinitialise l'UI après effacement des batches."""
        self.combinations = []
        self.current_combination_index = 0
        self.batch_table.setRowCount(0)
        self.batch_table.setColumnCount(3)
        self.batch_table.setHorizontalHeaderLabels(["Combinaison", "samples", "Contexte 1"])
        self.stats_label.setText("Combinaisons totales: 0 | Samples: 0")
        self.current_combo_label.setText("Combinaison 1 | Contextes: 0")
        self.batch_selector_combo.clear()
        self.batch_selector_combo.addItem("-- Sélectionner un batch --")
        self.batch_status_label.setText("Nouveau batch")
        self.batch_status_label.setStyleSheet("color: #95a5a6; font-size: 9px; font-style: italic; padding: 3px;")
        self.is_batch_saved = False
        self.current_batch_id = None

    def _on_checkbox_changed(self, item, level):
        """Ajouter/retirer un contexte à la combinaison en cours"""
        if not self.selected_master_typologie:
            checkbox = None
            if level == 'typologie':
                checkbox = self.context_typologie_tree.itemWidget(item, 1)
            elif level == 'taxonomy':
                checkbox = self.context_taxonomy_tree.itemWidget(item, 1)
            elif level in ['root', 'parent', 'child']:
                checkbox = self.dynamic_labels_tree.itemWidget(item, 1)

            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)

            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie master."
            )
            return

        # Vérifier la navigation pour les niveaux autres que typologie
        nav = self._context_navigation

        if level != 'typologie' and not nav.get('typologie'):
            checkbox = None
            if level == 'taxonomy':
                checkbox = self.context_taxonomy_tree.itemWidget(item, 1)
            elif level in ['root', 'parent', 'child']:
                checkbox = self.dynamic_labels_tree.itemWidget(item, 1)

            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)

            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner une typologie de contexte."
            )
            logger.warning("❌ Tentative de sélection sans typologie dans la navigation")
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        selection = self._build_selection_from_item_data(item_data, level)
        if not selection:
            logger.error(f"❌ Impossible de construire la sélection pour level={level}")
            return

        # Ajouter/retirer le contexte à la combinaison en cours
        self._toggle_context_in_current_combination(selection, item, level)

    def _toggle_context_in_current_combination(self, selection, item, level):
        """Ajouter ou retirer un contexte de la combinaison en cours"""
        path_key = self._generate_path_key_from_selection(selection)

        if not path_key:
            return

        # Vérifier si le contexte existe déjà dans la combinaison actuelle
        existing_index = None
        for i, ctx in enumerate(self.current_combination['contexts']):
            if ctx.get('path_key') == path_key:
                existing_index = i
                break
            
        if existing_index is not None:
            # RETIRER le contexte
            self.current_combination['contexts'].pop(existing_index)
            logger.info(f"🗑️ Contexte RETIRÉ de la combinaison {self.current_combination_index + 1}")
        else:
            # AJOUTER le contexte
            context_data = {
                'selection': selection,
                'path_key': path_key,
                'display': selection['display']
            }
            self.current_combination['contexts'].append(context_data)
            logger.info(f"✅ Contexte AJOUTÉ à la combinaison {self.current_combination_index + 1}")

        # Mettre à jour l'affichage
        self._update_current_combo_label()
        self._update_table_current_row()
        self._update_stats()

    def _update_current_combo_label(self):
        """Mettre à jour l'indicateur de combinaison en cours"""
        combo_num = self.current_combination_index + 1
        context_count = len(self.current_combination['contexts'])

        self.current_combo_label.setText(
            f"Combinaison {combo_num} | Contextes: {context_count}"
        )


    def _save_current_combination(self):
        """Sauvegarder la combinaison actuelle dans la liste - VERSION CORRIGÉE"""
        if not self.current_combination['contexts']:
            return

        if not self.selected_master_typologie:
            logger.warning("Aucune typologie master sélectionnée")
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "Veuillez sélectionner une typologie master avant de sauvegarder la combinaison."
            )
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')

        # ✅ CORRECTION : Récupérer nb_samples depuis le tableau
        nb_samples = 1  # Valeur par défaut

        if self.current_combination_index < self.batch_table.rowCount():
            nb_item = self.batch_table.item(self.current_combination_index, 1)
            if nb_item:
                try:
                    nb_samples = int(nb_item.text()) if nb_item.text().strip() else 1
                    if nb_samples < 1:
                        nb_samples = 1
                except ValueError:
                    logger.warning(f"Valeur nb_samples invalide pour combinaison {self.current_combination_index + 1}, utilisation de 1")
                    nb_samples = 1

        logger.info(f"💾 Sauvegarde combinaison {self.current_combination_index + 1} avec {nb_samples} samples")

        combination = {
            'index': self.current_combination_index,
            'master': {'name': master_name, 'data': self.selected_master_typologie},
            'contexts': self.current_combination['contexts'].copy(),
            'nb_samples': nb_samples  # ✅ Valeur récupérée du tableau
        }

        # Remplacer si existe déjà, sinon ajouter
        if self.current_combination_index < len(self.combinations):
            self.combinations[self.current_combination_index] = combination
        else:
            self.combinations.append(combination)

        # Ajouter/mettre à jour dans le tableau
        self._update_table_row(self.current_combination_index, combination)

        logger.info(f"✅ Combinaison {self.current_combination_index + 1} sauvegardée avec {len(self.current_combination['contexts'])} contextes et {nb_samples} samples")

    def _update_table_row(self, row_index, combination):
        """Mettre à jour ou créer une ligne dans le tableau - Compatible ancien et nouveau format"""
        # Migration automatique si ancien format
        combination = self._migrate_old_combination_format(combination)

        contexts = combination.get('contexts', [])
        num_contexts = len(contexts)

        # Ajuster le nombre de colonnes si nécessaire (Combinaison + Nb samples + contextes)
        current_cols = self.batch_table.columnCount()
        needed_cols = num_contexts + 2  # +1 pour Nb samples

        if needed_cols > current_cols:
            self.batch_table.setColumnCount(needed_cols)
            headers = ["Combinaison", "Nb samples"]
            for i in range(1, num_contexts + 1):
                headers.append(f"Contexte {i}")
            self.batch_table.setHorizontalHeaderLabels(headers)

            self.batch_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
            self.batch_table.setColumnWidth(0, 150)
            self.batch_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
            self.batch_table.setColumnWidth(1, 80)
            for i in range(2, needed_cols):
                self.batch_table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        if row_index >= self.batch_table.rowCount():
            self.batch_table.insertRow(row_index)

        # Colonne 0 : Numéro
        num_item = QtWidgets.QTableWidgetItem(f"Combinaison {row_index + 1}")
        num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        font = num_item.font()
        font.setBold(True)
        num_item.setFont(font)
        num_item.setBackground(QColor("#f8f9fa"))
        num_item.setData(Qt.UserRole, combination)
        self.batch_table.setItem(row_index, 0, num_item)

        # Colonne 1 : Nb samples (éditable)
        nb_samples = combination.get('nb_samples', 1)
        nb_item = QtWidgets.QTableWidgetItem(str(nb_samples))
        nb_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        nb_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.batch_table.setItem(row_index, 1, nb_item)

        # Colonnes de contextes (à partir de la colonne 2)
        for ctx_index, ctx in enumerate(contexts):
            col = ctx_index + 2

            if 'selection' in ctx:
                display_text = self._build_unified_context_display(ctx['selection'])
            else:
                display_text = ctx.get('display', 'N/A')

            context_item = QtWidgets.QTableWidgetItem(display_text)
            context_item.setFlags(context_item.flags() & ~Qt.ItemIsEditable)
            context_item.setData(Qt.UserRole, ctx)
            self.batch_table.setItem(row_index, col, context_item)

        for col in range(num_contexts + 2, self.batch_table.columnCount()):
            empty_item = QtWidgets.QTableWidgetItem("")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
            self.batch_table.setItem(row_index, col, empty_item)

    def _update_table_current_row(self):
        """Mettre à jour la ligne de la combinaison en cours d'édition - VERSION CORRIGÉE"""
        if not self.current_combination['contexts']:
            # Si pas de contextes, supprimer la ligne si elle existe
            if self.current_combination_index < self.batch_table.rowCount():
                self.batch_table.removeRow(self.current_combination_index)
            return

        master_name = self.selected_master_typologie.get('name', 'N/A')

        # ✅ CORRECTION : Récupérer nb_samples depuis le tableau existant
        nb_samples = 1

        if self.current_combination_index < self.batch_table.rowCount():
            nb_item = self.batch_table.item(self.current_combination_index, 1)
            if nb_item:
                try:
                    nb_samples = int(nb_item.text()) if nb_item.text().strip() else 1
                    if nb_samples < 1:
                        nb_samples = 1
                except ValueError:
                    nb_samples = 1

        combination = {
            'index': self.current_combination_index,
            'master': {'name': master_name, 'data': self.selected_master_typologie},
            'contexts': self.current_combination['contexts'].copy(),
            'nb_samples': nb_samples  # ✅ Préserver la valeur du tableau
        }

        self._update_table_row(self.current_combination_index, combination)

    def _migrate_old_combination_format(self, combination):
        """Convertit l'ancien format (context) vers le nouveau format (contexts)"""
        if 'contexts' in combination:
            # Ajouter nb_samples si absent
            if 'nb_samples' not in combination:
                combination['nb_samples'] = 1
            return combination

        if 'context' in combination:
            old_context = combination['context']

            new_combination = {
                'index': combination.get('index', 0),
                'master': combination.get('master', {}),
                'contexts': [{
                    'selection': old_context,
                    'path_key': combination.get('path_key', ''),
                    'display': combination.get('display', old_context.get('display', ''))
                }],
                'nb_samples': 1  # Défaut pour ancien format
            }

            logger.info(f"🔄 Migration d'une combinaison de l'ancien format vers le nouveau")
            return new_combination

        logger.warning(f"⚠️ Format de combinaison inconnu : {combination}")
        return combination

    def _load_children_in_dynamic_list(self, children_list, cluster, root, parent):
        """Charger les enfants - checkbox UNIQUEMENT si pas d'enfants"""
        nav = self._context_navigation
        typologie_name = nav.get('typologie', {}).get('name', '') if nav.get('typologie') else ''

        if not typologie_name:
            logger.error("❌ Pas de typologie")
            return

        self.dynamic_labels_tree.clear()

        for child in children_list:
            child_name = child.get('name', '')
            if not child_name:
                continue
            
            current_path = nav.get('child_path', []) + [child_name]
            has_children = bool(child.get('children'))

            # Affichage
            if has_children:
                child_count = self._count_children_recursive(child.get('children', []))
                prefix = "▶"
                display_text = f"{prefix} {child_name} ({child_count})"
            else:
                prefix = "•"
                display_text = f"{prefix} {child_name}"

            tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])

            item_data = {
                'level': 'child',
                'data': child,
                'parent': parent,
                'root': root,
                'cluster': cluster,
                'path': current_path,
                'typologie': typologie_name,
                'has_children': has_children,
                'original_name': child_name,
                'prefix': prefix,
                'name': child_name
            }

            tree_item.setData(0, Qt.UserRole, item_data)

            # ✅ MODIFICATION: Checkbox uniquement pour éléments sans enfants
            if not has_children:
                # Élément feuille : checkbox visible
                checkbox = self._create_styled_checkbox()
                self.dynamic_labels_tree.setItemWidget(tree_item, 1, checkbox)
                checkbox.stateChanged.connect(
                    lambda state, it=tree_item: self._on_checkbox_changed(it, 'child')
                )

            self.dynamic_labels_tree.addTopLevelItem(tree_item)

        self.dynamic_labels_tree.header().setStretchLastSection(False)
        self.dynamic_labels_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.dynamic_labels_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.dynamic_labels_tree.setColumnWidth(1, 40)

        self._update_label_navigation_buttons()

    def _get_checkbox_style(self):
        """Return the CSS style for checkboxes with visible checkmark"""
        return """
            QCheckBox {
                padding-left: 8px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #c8e6c9;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #81c784;
                background-color: #f1f8f4;
            }
            QCheckBox::indicator:checked {
                background-color: #66bb6a;
                border: 2px solid #4caf50;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTMuNSAzLjVMNiAxMSAyLjUgNy41IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #4caf50;
                border: 2px solid #388e3c;
            }
        """

    def _update_labels_breadcrumb(self):
        """Mise à jour du breadcrumb"""
        nav = self._context_navigation
        parts = []

        if nav.get('taxonomy'):
            parts.append(nav['taxonomy'].get('name', '?'))
        if nav.get('root'):
            parts.append(nav['root'].get('name', '?'))
        if nav.get('parent'):
            parts.append(nav['parent'].get('name', '?'))

        child_path = nav.get('child_path', [])
        if child_path:
            path_str = " → ".join(child_path[-2:]) if len(child_path) > 2 else " → ".join(child_path)
            if len(child_path) > 2:
                path_str = "... → " + path_str
            parts.append(path_str)

        if parts:
            self.labels_breadcrumb.setText(" → ".join(parts))
        else:
            self.labels_breadcrumb.setText("Sélectionnez un cluster")

    def _on_batch_item_selected(self, current, previous):
        self.remove_from_batch_btn.setEnabled(current is not None)

    def _update_stats(self):
        """Mettre à jour les statistiques globales - Somme des nb_samples"""
        total_combos = len(self.combinations)

        # Ajouter 1 si la combinaison en cours a des contextes
        if self.current_combination.get('contexts', []):
            total_combos += 1

        # Calculer le total de samples via somme des nb_samples
        total_samples = 0
        for combo in self.combinations:
            total_samples += combo.get('nb_samples', 1)

        # Ajouter pour la combinaison en cours
        if self.current_combination.get('contexts', []):
            current_nb = 1  # Défaut, ou récupérer depuis table si ligne existe
            if self.current_combination_index < self.batch_table.rowCount():
                nb_item = self.batch_table.item(self.current_combination_index, 1)
                if nb_item:
                    try:
                        current_nb = int(nb_item.text()) if nb_item.text().strip() else 1
                    except ValueError:
                        current_nb = 1
            total_samples += current_nb

        self.stats_label.setText(f"Combinaisons totales: {total_combos} | Samples: {total_samples}")

    def _on_nb_samples_changed(self, row, column):
        """Gérer la modification du champ Nb samples - VERSION AMÉLIORÉE"""
        if column != 1:  # Seulement pour la colonne Nb samples
            return
    
        if row >= len(self.combinations):
            return
    
        item = self.batch_table.item(row, column)
        if not item:
            return
    
        try:
            value = int(item.text()) if item.text().strip() else 1
            if value < 1:
                value = 1
                item.setText("1")
        except ValueError:
            value = 1
            item.setText("1")
            logger.warning(f"Valeur invalide pour nb_samples ligne {row + 1}, réinitialisation à 1")
    
        # ✅ Mettre à jour dans les données ET bloquer les signaux pour éviter la boucle
        old_value = self.combinations[row].get('nb_samples', 1)
        self.combinations[row]['nb_samples'] = value
    
        # Marquer comme modifié si batch chargé
        if self.current_batch_id and self.is_batch_saved:
            self.is_batch_saved = False
            self._update_batch_status(f"Batch #{self.current_batch_id} - Modifié (non sauvegardé)")
    
        # Mettre à jour stats
        self._update_stats()
    
        if old_value != value:
            logger.info(f"✅ Nb samples mis à jour pour combinaison {row + 1}: {old_value} → {value}")
    
    # ========== ACTIONS ==========

    def _create_action_buttons(self, parent_layout):
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.refresh_btn = self._create_action_button("Rafraîchir", self.refresh_data)
        btn_layout.addWidget(self.refresh_btn)

        # ✅ NOUVEAU : Bouton Sauvegarder
        self.save_batch_btn = self._create_action_button("Sauvegarder", self._save_batch)
        btn_layout.addWidget(self.save_batch_btn)

        parent_layout.addWidget(btn_container)

    def _new_batch(self):
        """Créer un nouveau batch (réinitialiser l'interface)"""
        if not self.is_batch_saved and self.combinations:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Batch non sauvegardé",
                "Le batch actuel contient des modifications non sauvegardées.\n"
                "Voulez-vous continuer et perdre ces modifications ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
    
        # Réinitialiser l'ID et le statut
        self.current_batch_id = None
        self.is_batch_saved = False
        
        # Réinitialiser les champs du formulaire
        self.batch_name_edit.clear()
        self.batch_family_edit.clear()
        self.desc_edit.clear()
        
        # ✅ CORRECTION : Réinitialiser le tableau au lieu de batch_list
        self.batch_table.setRowCount(0)
        self.batch_table.setColumnCount(3)
        self.batch_table.setHorizontalHeaderLabels(["Combinaison", "samples", "Contexte 1"])
        
        # Réinitialiser les combinaisons
        self.combinations = []
        self.current_combination = {
            'contexts': [],
            'master': self.selected_master_typologie
        }
        self.current_combination_index = 0
        
        # Mettre à jour l'affichage
        self._update_stats()
        self._update_current_combo_label()
        self._update_batch_status("Nouveau batch")
        self._mark_current_selections()
        self._reset_all_hierarchy_colors()
        
        # Réinitialiser le sélecteur de batch
        self.batch_selector_combo.blockSignals(True)
        self.batch_selector_combo.setCurrentIndex(0)
        self.batch_selector_combo.blockSignals(False)
    
        logger.info("✅ Nouveau batch créé")
        
        QtWidgets.QMessageBox.information(
            self,
            "Nouveau Batch",
            "Un nouveau batch a été créé.\n"
            "Vous pouvez maintenant ajouter des combinaisons."
        )

    def _save_batch(self):
        """Sauvegarder le batch avec le nouveau format multi-contextes - VERSION CORRIGÉE AVEC LOGS"""
        logger.info("=" * 100)
        logger.info("🚀 DÉBUT SAUVEGARDE BATCH - VERSION DÉTAILLÉE")
        logger.info("=" * 100)

        batch_name = self.batch_name_edit.text().strip()
        if not batch_name:
            logger.error("❌ Nom du batch vide")
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez saisir un nom pour le batch."
            )
            return

        if self.project_combo.currentIndex() <= 0:
            logger.error("❌ Aucun projet sélectionné")
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez sélectionner un projet."
            )
            return

        # Sauvegarder la combinaison en cours si elle a des contextes
        if self.current_combination['contexts']:
            logger.info(f"📦 Sauvegarde combinaison en cours: {len(self.current_combination['contexts'])} contextes")
            self._save_current_combination()

        if not self.combinations:
            logger.error("❌ Aucune combinaison dans le batch")
            QtWidgets.QMessageBox.warning(
                self, 
                "Attention", 
                "Aucune combinaison dans le batch."
            )
            return
        
        logger.info("\n🔄 SYNCHRONISATION nb_samples depuis le tableau")
        logger.info("-" * 80)
        
        for row_idx in range(self.batch_table.rowCount()):
            if row_idx < len(self.combinations):
                nb_item = self.batch_table.item(row_idx, 1)  # Colonne Nb samples
                if nb_item:
                    try:
                        nb_samples = int(nb_item.text()) if nb_item.text().strip() else 1
                        if nb_samples < 1:
                            nb_samples = 1
                        
                        old_value = self.combinations[row_idx].get('nb_samples', 1)
                        self.combinations[row_idx]['nb_samples'] = nb_samples
                        
                        if old_value != nb_samples:
                            logger.info(f"  Ligne {row_idx + 1}: {old_value} → {nb_samples} samples")
                        
                    except ValueError:
                        logger.warning(f"  Ligne {row_idx + 1}: Valeur invalide, utilisation de 1 par défaut")
                        self.combinations[row_idx]['nb_samples'] = 1
    
        logger.info("✅ Synchronisation terminée")

        logger.info("\n📊 VÉRIFICATION AVANT EXTRACTION")
        logger.info("-" * 80)
        for idx, combo in enumerate(self.combinations):
            nb = combo.get('nb_samples', 1)
            ctx_count = len(combo.get('contexts', []))
            logger.info(f"  Combinaison {idx + 1}: {ctx_count} contextes, {nb} samples")

        # Puis continuer avec l'extraction des contextes...
        processed_combinations = []

        for combo_idx, combo in enumerate(self.combinations):
            logger.info(f"\n[Combinaison {combo_idx + 1}/{len(self.combinations)}]")

            contexts = combo.get('contexts', [])
            nb_samples = combo.get('nb_samples', 1)

            logger.info(f"  - {len(contexts)} contexte(s)")
            logger.info(f"  - {nb_samples} samples")
    
        # ========================================
        # EXTRACTION DE LA TYPOLOGIE MASTER COMPLÈTE
        # ========================================
        logger.info("\n📊 EXTRACTION TYPOLOGIE MASTER")
        logger.info("-" * 80)

        if not self.selected_master_typologie:
            logger.error("❌ Aucune typologie master sélectionnée")
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "Veuillez sélectionner une typologie master."
            )
            return

        master_name = self.selected_master_typologie.get('name', '')
        logger.info(f"Master typologie: {master_name}")

        # Extraire TOUTE la hiérarchie de la typologie master
        master_full_data = {
            'name': master_name,
            'description': self.selected_master_typologie.get('description', ''),
            'taxonomy_clusters': []
        }

        # Copier tous les clusters avec leur hiérarchie complète
        clusters = self.selected_master_typologie.get('taxonomy_clusters', [])
        logger.info(f"  - {len(clusters)} cluster(s) de taxonomie")

        total_roots = 0
        total_parents = 0
        total_children = 0

        for cluster in clusters:
            cluster_data = {
                'name': cluster.get('name', ''),
                'description': cluster.get('description', ''),
                'root_labels': []
            }

            roots = cluster.get('root_labels', [])
            total_roots += len(roots)

            for root in roots:
                root_data = {
                    'name': root.get('name', ''),
                    'description': root.get('description', ''),
                    'category': root.get('category', 'default'),
                    'parent_labels': []
                }

                parents = root.get('parent_labels', [])
                total_parents += len(parents)

                for parent in parents:
                    parent_data = {
                        'name': parent.get('name', ''),
                        'description': parent.get('description', ''),
                        'category': parent.get('category', 'default'),
                        'children': self._extract_children_hierarchy(parent.get('children', []))
                    }

                    total_children += self._count_children_recursive(parent.get('children', []))
                    root_data['parent_labels'].append(parent_data)

                cluster_data['root_labels'].append(root_data)

            master_full_data['taxonomy_clusters'].append(cluster_data)

        logger.info(f"  - {total_roots} root labels")
        logger.info(f"  - {total_parents} parent labels")
        logger.info(f"  - {total_children} children labels")
        logger.info(f"✅ Typologie master complète extraite")

        # ========================================
        # EXTRACTION DES CONTEXTES (SEULEMENT SÉLECTION)
        # ========================================
        logger.info("\n📊 EXTRACTION CONTEXTES À COMBINER")
        logger.info("-" * 80)

        processed_combinations = []

        for combo_idx, combo in enumerate(self.combinations):
            logger.info(f"\n[Combinaison {combo_idx + 1}/{len(self.combinations)}]")

            contexts = combo.get('contexts', [])
            logger.info(f"  - {len(contexts)} contexte(s)")

            processed_contexts = []

            for ctx_idx, ctx in enumerate(contexts):
                logger.info(f"\n    [Contexte {ctx_idx + 1}]")

                selection = ctx.get('selection', {})
                level = selection.get('level', '')
                typologie = selection.get('typologie', '')

                logger.info(f"      Typologie: {typologie}")
                logger.info(f"      Niveau: {level}")

                # Construire le contexte avec seulement la hiérarchie sélectionnée
                context_data = self._extract_context_hierarchy(selection)

                if context_data:
                    processed_contexts.append({
                        'level': level,
                        'data': context_data,
                        'display': ctx.get('display', '')
                    })
                    logger.info(f"      ✅ Contexte extrait")
                else:
                    logger.warning(f"      ⚠️ Contexte vide")

            processed_combinations.append({
                'contexts': processed_contexts,
                'nb_samples': combo.get('nb_samples', 1)
            })

            logger.info(f"  ✅ Combinaison {combo_idx + 1} traitée")

        # ========================================
        # PRÉPARATION DES DONNÉES BATCH
        # ========================================
        logger.info("\n📦 PRÉPARATION BATCH DATA")
        logger.info("-" * 80)

        batch_data = {
            'batch_name': batch_name,
            'batch_family': self.batch_family_edit.text().strip(),
            'description': self.desc_edit.toPlainText(),
            'master_typologie': master_full_data,  # ✅ TYPOLOGIE COMPLÈTE
            'combinations': processed_combinations,  # ✅ CONTEXTES SÉLECTIONNÉS
            'count': len(processed_combinations),
            'created_at': datetime.now().isoformat()
        }

        logger.info(f"  - Nom: {batch_name}")
        logger.info(f"  - Famille: {batch_data['batch_family']}")
        logger.info(f"  - Master: {master_name} (complet)")
        logger.info(f"  - Combinaisons: {len(processed_combinations)}")

        # ========================================
        # SAUVEGARDE DANS LA BASE DE DONNÉES
        # ========================================
        logger.info("\n💾 SAUVEGARDE DANS SQLITE")
        logger.info("-" * 80)

        project_name = self.project_combo.currentText()
        existing_batches = self.project_manager.get_all_batches()

        if self.current_batch_id:
            batch_number = self.current_batch_id
            logger.info(f"  Mode: Mise à jour (Batch #{batch_number})")
            success = self.project_manager.save_batch(
                batch_number,
                len(existing_batches),
                batch_data
            )
            action = "mis à jour"
        else:
            batch_number = len(existing_batches) + 1
            logger.info(f"  Mode: Nouveau (Batch #{batch_number})")
            success = self.project_manager.save_batch(
                batch_number,
                batch_number,
                batch_data
            )
            action = "sauvegardé"
            self.current_batch_id = batch_number

        # ========================================
        # VÉRIFICATION POST-SAUVEGARDE
        # ========================================
        if success:
            logger.info(f"\n✅ SAUVEGARDE RÉUSSIE")
            logger.info("-" * 80)

            # Vérifier dans la base
            logger.info("🔍 Vérification dans la base...")

            try:
                cursor = self.project_manager.database.connection.cursor()

                # Récupérer le projet
                cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
                project_row = cursor.fetchone()

                if project_row:
                    project_id = project_row['id']
                    logger.info(f"  ✅ Projet trouvé (ID: {project_id})")

                    # Récupérer le batch
                    cursor.execute("""
                        SELECT * FROM batches 
                        WHERE project_id = ? AND batch_number = ?
                    """, (project_id, batch_number))

                    batch_row = cursor.fetchone()

                    if batch_row:
                        logger.info(f"  ✅ Batch trouvé en base")
                        logger.info(f"     - ID: {batch_row['id']}")
                        logger.info(f"     - Numéro: {batch_row['batch_number']}")
                        logger.info(f"     - Statut: {batch_row['status']}")
                        logger.info(f"     - Créé: {batch_row['created_at']}")

                        # Vérifier le contenu
                        import json
                        saved_data = json.loads(batch_row['data'])

                        logger.info(f"\n  📊 Contenu sauvegardé:")
                        logger.info(f"     - Nom: {saved_data.get('batch_name')}")
                        logger.info(f"     - Master: {saved_data.get('master_typologie', {}).get('name')}")
                        logger.info(f"     - Clusters master: {len(saved_data.get('master_typologie', {}).get('taxonomy_clusters', []))}")
                        logger.info(f"     - Combinaisons: {len(saved_data.get('combinations', []))}")

                        # Vérifier chaque combinaison
                        for idx, combo in enumerate(saved_data.get('combinations', [])):
                            logger.info(f"\n     [Combinaison {idx + 1}]")
                            logger.info(f"       - Contextes: {len(combo.get('contexts', []))}")
                            logger.info(f"       - Samples: {combo.get('nb_samples', 1)}")

                            for ctx_idx, ctx in enumerate(combo.get('contexts', [])):
                                logger.info(f"       [Contexte {ctx_idx + 1}]")
                                logger.info(f"         - Niveau: {ctx.get('level')}")
                                logger.info(f"         - Display: {ctx.get('display')}")

                        logger.info(f"\n✅ DONNÉES VÉRIFIÉES EN BASE")
                    else:
                        logger.error("  ❌ Batch NON TROUVÉ en base!")
                else:
                    logger.error("  ❌ Projet NON TROUVÉ!")

            except Exception as e:
                logger.error(f"❌ Erreur vérification: {e}")
                import traceback
                logger.error(traceback.format_exc())

            # Mise à jour UI
            self.is_batch_saved = True
            self._update_batch_status(f"Batch #{batch_number} - Sauvegardé")
            self._refresh_batch_list()

            logger.info("\n" + "=" * 100)
            logger.info(f"🎉 SAUVEGARDE TERMINÉE: Batch #{batch_number} - {batch_name}")
            logger.info("=" * 100 + "\n")

            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                f"Batch '{batch_name}' {action} avec succès!\n"
                f"Batch #{batch_number}\n"
                f"Combinaisons: {len(self.combinations)}\n\n"
                f"Consultez les logs pour les détails."
            )
        else:
            logger.error(f"\n❌ ÉCHEC SAUVEGARDE")
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                f"Impossible de sauvegarder le batch '{batch_name}'"
            )


    def _extract_context_hierarchy(self, selection):
        """
        Extrait UNIQUEMENT la hiérarchie sélectionnée pour un contexte
        Retourne la structure hiérarchique minimale
        """
        level = selection.get('level', '')
        typologie_name = selection.get('typologie', '')

        logger.info(f"        Extraction hiérarchie: {level}")

        # Trouver la typologie complète dans le cache
        typologie = self._find_typologie_by_name(typologie_name)
        if not typologie:
            logger.error(f"        ❌ Typologie '{typologie_name}' non trouvée")
            return None

        if level == 'typologie':
            # Toute la typologie
            logger.info(f"        → Niveau typologie (complète)")
            return {
                'name': typologie_name,
                'taxonomy_clusters': typologie.get('taxonomy_clusters', [])
            }

        elif level == 'taxonomy':
            taxonomy_name = selection.get('taxonomy', '')
            logger.info(f"        → Niveau taxonomy: {taxonomy_name}")

            # Trouver le cluster
            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == taxonomy_name:
                    return {
                        'name': typologie_name,
                        'taxonomy_clusters': [{
                            'name': taxonomy_name,
                            'root_labels': cluster.get('root_labels', [])
                        }]
                    }

            logger.error(f"        ❌ Cluster '{taxonomy_name}' non trouvé")
            return None

        elif level == 'root':
            taxonomy_name = selection.get('taxonomy', '')
            root_name = selection.get('root', '')
            logger.info(f"        → Niveau root: {taxonomy_name} > {root_name}")

            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == taxonomy_name:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == root_name:
                            return {
                                'name': typologie_name,
                                'taxonomy_clusters': [{
                                    'name': taxonomy_name,
                                    'root_labels': [root]
                                }]
                            }

            logger.error(f"        ❌ Root '{root_name}' non trouvé")
            return None

        elif level == 'parent':
            taxonomy_name = selection.get('taxonomy', '')
            root_name = selection.get('root', '')
            parent_name = selection.get('parent', '')
            logger.info(f"        → Niveau parent: {taxonomy_name} > {root_name} > {parent_name}")

            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == taxonomy_name:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == root_name:
                            for parent in root.get('parent_labels', []):
                                if parent.get('name') == parent_name:
                                    return {
                                        'name': typologie_name,
                                        'taxonomy_clusters': [{
                                            'name': taxonomy_name,
                                            'root_labels': [{
                                                'name': root_name,
                                                'parent_labels': [parent]
                                            }]
                                        }]
                                    }

            logger.error(f"        ❌ Parent '{parent_name}' non trouvé")
            return None

        elif level == 'child':
            taxonomy_name = selection.get('taxonomy', '')
            root_name = selection.get('root', '')
            parent_name = selection.get('parent', '')
            child_path = selection.get('child_path', [])

            logger.info(f"        → Niveau child: {' > '.join(child_path)}")

            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == taxonomy_name:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == root_name:
                            for parent in root.get('parent_labels', []):
                                if parent.get('name') == parent_name:
                                    # Extraire le chemin enfant spécifique
                                    child_hierarchy = self._extract_child_path(
                                        parent.get('children', []),
                                        child_path
                                    )

                                    if child_hierarchy:
                                        return {
                                            'name': typologie_name,
                                            'taxonomy_clusters': [{
                                                'name': taxonomy_name,
                                                'root_labels': [{
                                                    'name': root_name,
                                                    'parent_labels': [{
                                                        'name': parent_name,
                                                        'children': child_hierarchy
                                                    }]
                                                }]
                                            }]
                                        }

            logger.error(f"        ❌ Chemin child non trouvé")
            return None

        return None
    
    def _extract_child_path(self, children_list, target_path):
        """
        Extrait un chemin spécifique dans la hiérarchie des enfants
        """
        if not target_path:
            return children_list

        target_name = target_path[0]
        remaining_path = target_path[1:]

        for child in children_list:
            if child.get('name') == target_name:
                if not remaining_path:
                    # C'est l'enfant cible, retourner sa hiérarchie complète
                    return [child]
                else:
                    # Continuer dans les sous-enfants
                    sub_hierarchy = self._extract_child_path(
                        child.get('children', []),
                        remaining_path
                    )
                    if sub_hierarchy:
                        return [{
                            'name': child.get('name'),
                            'description': child.get('description', ''),
                            'category': child.get('category', 'default'),
                            'children': sub_hierarchy
                        }]

        return None


    def _extract_children_hierarchy(self, children):
        """Copie récursive de la hiérarchie des enfants"""
        result = []
        for child in children:
            child_copy = {
                'name': child.get('name', ''),
                'description': child.get('description', ''),
                'category': child.get('category', 'default'),
                'children': self._extract_children_hierarchy(child.get('children', []))
            }
            result.append(child_copy)
        return result

    def _load_batch_dialog(self):
        """Afficher un dialogue pour charger un batch sauvegardé"""
        if self.project_combo.currentIndex() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Attention",
                "Veuillez d'abord sélectionner un projet."
            )
            return

        # Récupérer tous les batches du projet
        batches = self.project_manager.get_all_batches()

        if not batches:
            QtWidgets.QMessageBox.information(
                self,
                "Information",
                "Aucun batch sauvegardé pour ce projet."
            )
            return

        # Créer un dialogue de sélection
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Charger un batch")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Liste des batches
        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_hierarchy_list_style())

        for batch in batches:
            data = batch.get('data', {})
            batch_name = data.get('batch_name', 'Sans nom')
            count = data.get('count', 0)
            status = batch.get('status', 'pending')

            item_text = f"Batch #{batch['batch_number']}: {batch_name} ({count} combinaisons) - {status}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, batch)
            list_widget.addItem(item)

        list_widget.itemDoubleClicked.connect(lambda: dialog.accept())
        layout.addWidget(list_widget)

        # Boutons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        load_btn = QtWidgets.QPushButton("Charger")
        load_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(load_btn)

        cancel_btn = QtWidgets.QPushButton("Annuler")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Afficher le dialogue
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            current_item = list_widget.currentItem()
            if current_item:
                batch = current_item.data(Qt.UserRole)
                self._load_batch(batch)

    def _load_batch(self, batch):
        """Charger un batch dans l'interface"""
        data = batch.get('data', {})

        # Vérifier si le batch actuel a des modifications non sauvegardées
        if not self.is_batch_saved and self.combinations:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Batch non sauvegardé",
                "Le batch actuel contient des modifications non sauvegardées.\n"
                "Voulez-vous continuer et perdre ces modifications ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        # Charger les données
        self.current_batch_id = batch['batch_number']
        self.batch_name_edit.setText(data.get('batch_name', ''))
        self.batch_family_edit.setText(data.get('batch_family', ''))
        self.desc_edit.setPlainText(data.get('description', ''))

        # Charger la typologie master
        master_name = data.get('master_typologie', '')
        if master_name:
            index = self.master_combo.findText(master_name)
            if index > 0:
                self.master_combo.setCurrentIndex(index)

        # Charger les combinaisons
        self.combinations = data.get('combinations', [])

        # Mettre à jour l'affichage
        self.batch_list.clear()
        for combo in self.combinations:
            self.batch_list.addItem(combo.get('display', ''))

        self.is_batch_saved = True
        self._update_stats()
        self._update_batch_status(f"Batch #{batch['batch_number']} - {batch.get('status', 'pending')}")
        self._mark_current_selections()

        logger.info(f"Batch #{batch['batch_number']} '{data.get('batch_name', '')}' chargé")

        QtWidgets.QMessageBox.information(
            self,
            "Succès",
            f"Batch '{data.get('batch_name', '')}' chargé avec succès!\n"
            f"Combinaisons: {len(self.combinations)}"
        )

    def _update_batch_status(self, status_text):
        """Mettre à jour l'affichage du statut du batch"""
        self.batch_status_label.setText(status_text)

        # Changer la couleur selon le statut
        if "Sauvegardé" in status_text:
            color = "#27ae60"  # Vert
        elif "Nouveau" in status_text:
            color = "#95a5a6"  # Gris
        elif "processing" in status_text:
            color = "#f39c12"  # Orange
        elif "completed" in status_text:
            color = "#3498db"  # Bleu
        else:
            color = "#95a5a6"

        self.batch_status_label.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 600; padding: 4px;"
        )

    def _get_secondary_button_style(self):
        """Style pour boutons secondaires compacts"""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #95a5a6, stop:1 #7f8c8d);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;  /* Réduit de 25px à 15px */
                font-weight: 600;
                font-size: 12px;
                min-width: 90px;  /* Réduit de 140px à 90px */
                max-width: 120px;  /* Limite la largeur maximale */
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7f8c8d, stop:1 #95a5a6);
            }}
            QPushButton:disabled {{
                background: #c0c0c0;
                color: #707070;
            }}
        """
    
    def _on_batch_modified(self):
        """Marquer le batch comme modifié"""
        if self.is_batch_saved and self.current_batch_id:
            self.is_batch_saved = False
            self._update_batch_status(f"Batch #{self.current_batch_id} - Modifié (non sauvegardé)")

    # ========== DATA LOADING ==========

    def _load_initial_data(self):
        logger.info("Chargement des données initiales - RelationTab")
        if not self.project_manager:
            return
        self._refresh_typologies_cache()
        self._load_projects()
        self._load_master_typologies()
        self._load_context_typologies()
        self._refresh_batch_list()

    def _load_projects(self):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- Sélectionner un projet --")
        
        model = self.project_combo.model()
        if model.rowCount() > 0:
            item = model.item(0)
            if item:
                item.setFont(item.font())
                item.setForeground(QColor("#95a5a6"))

        if self.project_manager:
            for project in self.project_manager.get_all_projects():
                name = project.get('name', '')
                if name:
                    self.project_combo.addItem(name)
            if self.project_manager.current_project_name:
                idx = self.project_combo.findText(self.project_manager.current_project_name)
                if idx >= 0:
                    self.project_combo.setCurrentIndex(idx)
        self.project_combo.blockSignals(False)

    def _on_project_changed(self, index):
        if index <= 0:
            return
        project_name = self.project_combo.currentText()
        if project_name and self.project_manager and self.project_manager.load_project(project_name):
            logger.info(f"Projet '{project_name}' chargé")
            self._refresh_typologies_cache()
            self._load_master_typologies()
            self._load_context_typologies()
            self._refresh_batch_list()

    def _refresh_typologies_cache(self):
        self._typologies_cache = []
        if self.project_manager and self.project_manager.current_project_data:
            typologies = self.project_manager.current_project_data.get('typologies', [])
            self._typologies_cache = typologies if isinstance(typologies, list) else []

    def _load_master_typologies(self):
        self.master_combo.blockSignals(True)
        self.master_combo.clear()
        self.master_combo.addItem("-- Sélectionner --")
        
        model = self.master_combo.model()
        if model.rowCount() > 0:
            item = model.item(0)
            if item:
                item.setForeground(QColor("#95a5a6"))

        for typ in self._typologies_cache:
            if isinstance(typ, dict):
                name = typ.get('name', typ.get('nom', ''))
                if name:
                    self.master_combo.addItem(name)
        self.master_combo.blockSignals(False)
        self.master_stats.clear()

    def _load_context_typologies(self):
        """Charger les typologies - PAS de checkbox si ont des enfants"""
        self.context_typologie_tree.clear()
        master_name = self.selected_master_typologie.get('name', '') if self.selected_master_typologie else None

        for typ in self._typologies_cache:
            if isinstance(typ, dict):
                name = typ.get('name', typ.get('nom', ''))
                if name and name != master_name:
                    clusters = typ.get('taxonomy_clusters', [])
                    cluster_count = len(clusters)

                    display_text = f"{name} ({cluster_count})"

                    tree_item = QtWidgets.QTreeWidgetItem([display_text, ""])
                    tree_item.setData(0, Qt.UserRole, typ)

                    # ✅ MODIFICATION: Checkbox uniquement pour éléments sans enfants
                    has_children = bool(clusters)

                    if not has_children:
                        # Élément feuille : checkbox visible
                        checkbox = self._create_styled_checkbox()
                        self.context_typologie_tree.setItemWidget(tree_item, 1, checkbox)
                        checkbox.stateChanged.connect(
                            lambda state, it=tree_item: self._on_checkbox_changed(it, 'typologie')
                        )

                    self.context_typologie_tree.addTopLevelItem(tree_item)

        self.context_taxonomy_tree.clear()
        self.dynamic_labels_tree.clear()

        self._context_navigation = {
            'typologie': None, 
            'taxonomy': None, 
            'root': None, 
            'parent': None, 
            'child_path': [],
            'current_level': ''
        }

        self._update_navigation_breadcrumb()
        self._update_labels_breadcrumb()

    def _on_master_typologie_changed(self, index):
        if index <= 0:
            self.selected_master_typologie = None
            self.master_stats.clear()
            self._load_context_typologies()
            return

        actual_idx = index - 1
        if actual_idx >= len(self._typologies_cache):
            return

        typologie = self._typologies_cache[actual_idx]
        self.selected_master_typologie = typologie

        clusters = typologie.get('taxonomy_clusters', [])
        total_roots = sum(len(c.get('root_labels', [])) for c in clusters)
        total_parents = sum(len(r.get('parent_labels', [])) for c in clusters for r in c.get('root_labels', []))
        total_children = sum(self._count_children_recursive(p.get('children', [])) for c in clusters for r in c.get('root_labels', []) for p in r.get('parent_labels', []))

        self.master_stats.setText(f"{typologie.get('name', 'N/A')}\n\nClusters: {len(clusters)}\nRoots: {total_roots}\nParents: {total_parents}\nEnfants: {total_children}")
        self._load_context_typologies()

    def _count_children_recursive(self, children):
        """Count all children recursively"""
        if not children:
            return 0
        count = len(children)
        for child in children:
            count += self._count_children_recursive(child.get('children', []))
        return count

    def _find_typologie_by_name(self, name):
        for typ in self._typologies_cache:
            if typ.get('name') == name or typ.get('nom') == name:
                return typ
        return None
    
    def _get_group_style(self):
        """Style pour les groupes dans les dialogues"""
        return """
            QGroupBox {
                font-weight: 600;
                font-size: 11px;
                color: #2c3e50;
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: white;
            }
        """
    
    def _get_dialog_button_style(self):
        """Style pour boutons de dialogue compacts"""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;  /* Réduit de 20px à 12px */
                font-weight: 600;
                font-size: 11px;
                min-width: 70px;  /* Réduit de 100px à 70px */
                max-width: 100px;  /* Limite la largeur maximale */
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
        """

    # ========== STYLES ==========

    def _create_modern_card(self, title):
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{ font-weight: 600; font-size: 11px; color: #2c3e50;
                border: 2px solid #e1e4e8; border-radius: 6px;
                margin-top: 8px; padding-top: 10px; background-color: white; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; background-color: white; color: {Theme.SECONDARY_COLOR}; }}
        """)
        return group

    def _add_form_field(self, layout, label_text, attr_name, placeholder=""):
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 10px;")
        layout.addWidget(label)
        edit = QtWidgets.QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet("""
            QLineEdit { border: 2px solid #e1e4e8; border-radius: 5px; padding: 5px 8px; 
                background-color: white; font-size: 10px; color: #2c3e50; } 
            QLineEdit:focus { border: 2px solid #2c3e50; }
        """)
        edit.setMinimumHeight(28)
        layout.addWidget(edit)
        setattr(self, attr_name, edit)

    def _get_modern_input_style(self):
        svg = self._get_dropdown_svg_path().replace('\\', '/')
        return f"""
            QComboBox {{ 
                border: 2px solid #e1e4e8; 
                border-radius: 5px; 
                padding: 5px 8px; 
                padding-right: 28px; 
                background-color: white; 
                font-size: 10px; 
                color: #2c3e50; 
                min-height: 26px;
            }} 
            QComboBox:focus {{ 
                border: 2px solid #2c3e50; 
            }} 
            QComboBox::drop-down {{ 
                subcontrol-origin: padding; 
                subcontrol-position: center right; 
                width: 26px; 
                border: none; 
                border-left: 1px solid #e1e4e8; 
            }} 
            QComboBox::down-arrow {{ 
                image: url({svg}); 
                width: 14px; 
                height: 14px; 
            }}
        """    
    def _update_item_icon(self, item, is_selected):
        """
        Ajoute ou retire une coche VERTE à l'extrême droite d'un QListWidgetItem
        VERSION CORRIGÉE - Utilise les données stockées
        """
        data = item.data(Qt.UserRole)

        # ✅ Pour les items avec données complètes (enfants)
        if data and isinstance(data, dict) and 'original_name' in data:
            original_name = data.get('original_name', '')
            prefix = data.get('prefix', '•')

            if is_selected:
                # Afficher avec checkmark vert
                item.setText(f"{prefix} {original_name}        ✔")
                item.setForeground(QColor("#27ae60"))  # VERT
                item.setBackground(QColor("#e8f5e9"))  # Fond vert léger
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                # Afficher sans checkmark
                item.setText(f"{prefix} {original_name}")
                item.setForeground(QColor("#2c3e50"))
                item.setBackground(QColor("#ffffff"))
                font = item.font()
                font.setBold(False)
                item.setFont(font)

        # ✅ Pour les items simples (autres niveaux : typologie, taxonomy, etc.)
        else:
            original_text = item.text()

            # Nettoyer toutes les anciennes marques possibles
            clean_text = (original_text
                          .replace("✔ ", "")
                          .replace(" ✔", "")
                          .replace("✓ ", "")
                          .replace(" ✓", "")
                          .rstrip())

            has_arrow = "▶" in clean_text
            if has_arrow:
                clean_text = clean_text.replace("▶ ", "").strip()

            if is_selected:
                display_text = f"▶ {clean_text}" if has_arrow else clean_text
                item.setText(f"{display_text}        ✔")
                item.setForeground(QColor("#27ae60"))
                item.setBackground(QColor("#e8f5e9"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                display_text = f"▶ {clean_text}" if has_arrow else clean_text
                item.setText(display_text)
                item.setForeground(QColor("#2c3e50"))
                item.setBackground(QColor("#ffffff"))
                font = item.font()
                font.setBold(False)
                item.setFont(font)

    def _create_mini_button(self, text, callback):
        """Boutons mini avec largeur minimale réduite"""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 3px 6px;  /* Réduit de 8px à 6px */
                font-weight: 600; 
                font-size: 11px; 
                min-height: 22px;
                min-width: 50px;  /* Ajout d'une largeur minimale compacte */
                max-width: 100px;  /* Limite la largeur maximale */
            }} 
            QPushButton:hover:enabled {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); 
            }} 
            QPushButton:disabled {{ 
                background: #d0d0d0; 
                color: #808080; 
            }}
        """)
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        # Changement de politique de taille pour éviter l'expansion
        btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        return btn

    def _create_action_button(self, text, callback):
        """Boutons d'action avec largeur réduite"""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); 
                color: white; 
                border: none; 
                border-radius: 6px; 
                padding: 8px 15px;  /* Réduit de 25px à 15px */
                font-weight: 600; 
                font-size: 12px; 
                min-width: 90px;  /* Réduit de 140px à 90px */
                max-width: 120px;  /* Limite la largeur maximale */
            }} 
            QPushButton:hover:enabled {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); 
            }} 
            QPushButton:disabled {{ 
                background: #c0c0c0; 
                color: #707070; 
            }}
        """)
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        return btn
    
    def _count_typologie_total_samples(self, typologie_name):
        """Compte le nombre total de labels dans une typologie"""
        if not typologie_name:
            return 0

        total = 0
        # Parcourir tous les clusters
        typ_path = [typologie_name]
        clusters = self.hierarchy_cache.get_children_at_path(typ_path)

        for cluster_name in clusters:
            total += self._count_cluster_total_samples(typologie_name, cluster_name)

        return total
    
    def _count_cluster_total_samples(self, typologie_name, cluster_name):
        """Compte le nombre total de labels dans un cluster"""
        if not typologie_name or not cluster_name:
            return 0

        total = 0
        cluster_path = [typologie_name, cluster_name]
        roots = self.hierarchy_cache.get_children_at_path(cluster_path)

        for root_name in roots:
            # +1 pour le root lui-même
            total += 1

            root_path = [typologie_name, cluster_name, root_name]
            parents = self.hierarchy_cache.get_children_at_path(root_path)

            for parent_name in parents:
                # +1 pour le parent lui-même
                total += 1

                # Compter tous les enfants récursivement
                parent_path = [typologie_name, cluster_name, root_name, parent_name]
                total += self._count_children_recursive_in_cache(parent_path)

        return total
    
    def _count_children_recursive_in_cache(self, path):
        """Compte récursivement tous les enfants à un chemin donné"""
        children = self.hierarchy_cache.get_children_at_path(path)
        count = len(children)

        for child_name in children:
            child_path = path + [child_name]
            count += self._count_children_recursive_in_cache(child_path)

        return count

    def _get_primary_button_style(self):
        """Style pour boutons primaires compacts"""
        return f"""
            QPushButton {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR}); 
                color: white; 
                border: none; 
                border-radius: 6px; 
                padding: 10px 20px;  /* Réduit de 30px à 20px */
                font-weight: 700; 
                font-size: 13px; 
                min-width: 100px;  /* Réduit de 180px à 100px */
                max-width: 140px;  /* Limite la largeur maximale */
            }} 
            QPushButton:hover:enabled {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR}); 
            }} 
            QPushButton:disabled {{ 
                background: #bdc3c7; 
                color: #7f8c8d; 
            }}
        """
    def _get_dropdown_svg_path(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(current_dir)), "resources", "icons", "dropdown.svg"))

    # ========== PUBLIC ==========

    def refresh_data(self):
        logger.info("Rafraîchissement des données")
        if self.project_manager and self.project_combo.currentIndex() > 0:
            self.project_manager.load_project(self.project_combo.currentText())
        self._refresh_typologies_cache()
        self._load_projects()
        self._load_master_typologies()
        self._load_context_typologies()
        self.selected_master_typologie = None
        self.master_combo.setCurrentIndex(0)
        self.master_stats.clear()

    def update_combinations(self, project_data):
        if project_data and self.project_manager:
            self.project_manager.current_project_data = project_data
        self.refresh_data()

    def update_relation(self, project_data):
        self.update_combinations(project_data)

    def get_combinations(self):
        return {
            'batch_name': self.batch_name_edit.text().strip(),
            'combinations': self.combinations,
            'count': len(self.combinations)
        }