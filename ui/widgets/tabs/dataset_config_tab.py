#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dbm import sqlite3
import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
import self

from ui.localization.translator import tr
from ui.styles.theme import Theme
from utils.hierarchy_cache import HierarchyCache
from PyQt5.QtWidgets import QScrollArea
from utils.dataset_dgraph_manager import DgraphDatasetManager


from utils.logger import logger

class PrerequisiteDialog(QtWidgets.QDialog):
    """Dialogue pour créer/éditer une relation de prérequis - VERSION AVEC NOMMAGE"""
    
    def __init__(self, dgraph_manager, current_node_info, parent=None):
        super().__init__(parent)
        self.dgraph_manager = dgraph_manager
        self.current_node_info = current_node_info
        self.selected_targets = []
        self.relation_names = {}  # {target_uid: relation_name}
        
        self.setWindowTitle("Ajouter une relation de prérequis")
        self.setMinimumWidth(1000)  # Plus large pour le tableau
        self.setMinimumHeight(700)
        
        # Style moderne
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
        """)
        
        self._init_ui()
        self._load_available_nodes()
    
    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # === TITRE ===
        title_label = QtWidgets.QLabel("Créer une relation de prérequis")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background-color: white;
                border-radius: 8px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # === LAYOUT 2 COLONNES ===
        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(15)
        
        # COLONNE GAUCHE - Nœud source + Configuration
        left_column = self._create_left_column()
        columns_layout.addWidget(left_column, 3)  # 30% de l'espace
        
        # COLONNE DROITE - Sélection des targets + Nommage
        right_column = self._create_right_column()
        columns_layout.addWidget(right_column, 7)  # 70% de l'espace
        
        main_layout.addLayout(columns_layout)
        
        # === BOUTONS ===
        button_layout = self._create_buttons()
        main_layout.addLayout(button_layout)
    
    def _create_left_column(self):
        """Crée la colonne gauche (source + config)"""
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # === NŒUD SOURCE ===
        source_group = self._create_modern_group("Nœud source")
        source_layout = QtWidgets.QVBoxLayout(source_group)
        
        source_card = QtWidgets.QWidget()
        source_card.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                border: 2px solid #e1e4e8;
            }
        """)
        
        source_card_layout = QtWidgets.QVBoxLayout(source_card)
        source_card_layout.setSpacing(8)
        
        # Nom
        name_label = QtWidgets.QLabel(f"<b>Nom:</b> {self.current_node_info.get('name', 'N/A')}")
        name_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        name_label.setWordWrap(True)
        source_card_layout.addWidget(name_label)
        
        # Type
        type_label = QtWidgets.QLabel(f"<b>Type:</b> {self.current_node_info.get('type', 'N/A')}")
        type_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        source_card_layout.addWidget(type_label)
        
        # UID
        uid_label = QtWidgets.QLabel(f"<b>UID:</b> {self.current_node_info.get('uid', 'N/A')}")
        uid_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        uid_label.setWordWrap(True)
        source_card_layout.addWidget(uid_label)
        
        source_layout.addWidget(source_card)
        left_layout.addWidget(source_group)
        
        # === TYPE DE PRÉREQUIS ===
        type_group = self._create_modern_group("Type de prérequis")
        type_layout = QtWidgets.QVBoxLayout(type_group)
        type_layout.setSpacing(12)
        
        # Radio buttons avec style moderne
        self.mandatory_radio = QtWidgets.QRadioButton("Obligatoire")
        self.mandatory_radio.setChecked(True)
        self.mandatory_radio.setStyleSheet("""
            QRadioButton {
                color: #2c3e50;
                font-size: 13px;
                font-weight: 600;
                padding: 8px;
                background-color: white;
                border-radius: 6px;
            }
            QRadioButton:hover {
                background-color: #fff5f5;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QRadioButton::indicator:checked {
                background-color: #e74c3c;
                border: 2px solid #c0392b;
                border-radius: 9px;
            }
        """)
        
        self.recommended_radio = QtWidgets.QRadioButton("Recommandé")
        self.recommended_radio.setStyleSheet("""
            QRadioButton {
                color: #2c3e50;
                font-size: 13px;
                font-weight: 600;
                padding: 8px;
                background-color: white;
                border-radius: 6px;
            }
            QRadioButton:hover {
                background-color: #f0fff4;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QRadioButton::indicator:checked {
                background-color: #27ae60;
                border: 2px solid #229954;
                border-radius: 9px;
            }
        """)
        
        type_layout.addWidget(self.mandatory_radio)
        type_layout.addWidget(self.recommended_radio)
        
        # Info bulle
        info_label = QtWidgets.QLabel(
            "Obligatoire: L'utilisateur doit compléter les prérequis avant ce nœud\n"
            "Recommandé: Suggestion pour une meilleure compréhension"
        )
        info_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 11px;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 6px;
            }
        """)
        info_label.setWordWrap(True)
        type_layout.addWidget(info_label)
        
        left_layout.addWidget(type_group)
        
        # === DESCRIPTION GLOBALE ===
        desc_group = self._create_modern_group("Description globale")
        desc_layout = QtWidgets.QVBoxLayout(desc_group)
        
        desc_info = QtWidgets.QLabel(
            "Cette description sera ajoutée au nœud source pour être indexée dans le Vector Store"
        )
        desc_info.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 11px;
                padding: 8px;
                background-color: #e8f4f8;
                border-radius: 4px;
            }
        """)
        desc_info.setWordWrap(True)
        desc_layout.addWidget(desc_info)
        
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setPlaceholderText(
            "Exemple: Nécessite d'avoir saisi des écritures comptables au préalable pour générer le rapport..."
        )
        self.description_edit.setMaximumHeight(120)
        self.description_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                background-color: white;
                color: #2c3e50;
            }
            QTextEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        desc_layout.addWidget(self.description_edit)
        
        left_layout.addWidget(desc_group)
        left_layout.addStretch()
        
        return left_widget
    
    def _create_right_column(self):
        """Crée la colonne droite (sélection targets + nommage)"""
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(15)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # === SÉLECTION DES TARGETS ===
        target_group = self._create_modern_group("Nœuds prérequis")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        target_layout.setSpacing(10)
        
        # Zone de recherche
        search_container = QtWidgets.QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        search_layout = QtWidgets.QHBoxLayout(search_container)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(8)
        
        search_icon = QtWidgets.QLabel("Recherche:")
        search_icon.setStyleSheet("font-size: 13px; color: #2c3e50; font-weight: 600;")
        search_layout.addWidget(search_icon)
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un nœud...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                font-size: 13px;
                background-color: transparent;
                color: #2c3e50;
            }
            QLineEdit::placeholder {
                color: #95a5a6;
            }
        """)
        self.search_input.textChanged.connect(self._filter_nodes)
        search_layout.addWidget(self.search_input)
        
        target_layout.addWidget(search_container)
        
        # Liste des nœuds disponibles
        self.nodes_list = QtWidgets.QListWidget()
        self.nodes_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.nodes_list.setMinimumHeight(150)
        self.nodes_list.setMaximumHeight(250)
        self.nodes_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                padding: 5px;
                background-color: white;
                outline: none;
            }
            QListWidget:focus {
                border: 2px solid #3498db;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                margin: 2px;
                color: #2c3e50;
                background-color: white;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #d0d7de;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
                border: 1px solid #2980b9;
            }
        """)
        self.nodes_list.itemSelectionChanged.connect(self._update_relation_table)
        target_layout.addWidget(self.nodes_list)
        
        right_layout.addWidget(target_group)
        
        # === TABLEAU DE NOMMAGE DES RELATIONS ===
        naming_group = self._create_modern_group("Noms des relations")
        naming_layout = QtWidgets.QVBoxLayout(naming_group)
        naming_layout.setSpacing(8)
        
        info_naming = QtWidgets.QLabel(
            "Donnez un nom descriptif à chaque relation de prérequis.\n"
            "Exemples: 'Connaissances de base', 'Formation préalable', 'Prérequis technique'"
        )
        info_naming.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 11px;
                padding: 8px;
                background-color: #fff3cd;
                border-radius: 4px;
                border-left: 4px solid #ffc107;
            }
        """)
        info_naming.setWordWrap(True)
        naming_layout.addWidget(info_naming)
        
        # Tableau pour nommer chaque relation
        self.relation_table = QtWidgets.QTableWidget()
        self.relation_table.setColumnCount(3)
        self.relation_table.setHorizontalHeaderLabels(["Nœud cible", "Type", "Nom de la relation"])
        self.relation_table.horizontalHeader().setStretchLastSection(True)
        self.relation_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.relation_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.relation_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.relation_table.setMinimumHeight(150)
        self.relation_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                background-color: white;
                gridline-color: #e1e4e8;
            }
            QTableWidget::item {
                padding: 8px;
                color: #2c3e50;
            }
            QTableWidget::item:selected {
                background-color: #e8f4f8;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #2c3e50;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        naming_layout.addWidget(self.relation_table)
        
        right_layout.addWidget(naming_group)
        
        return right_widget
    
    def _create_modern_group(self, title):
        """Crée un groupe avec style moderne"""
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 13px;
                color: #2c3e50;
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                background-color: white;
                color: #2c3e50;
            }
        """)
        return group
    
    def _create_buttons(self):
        """Crée les boutons d'action"""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton("Annuler")
        self.cancel_btn.setMinimumHeight(35)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #2c3e50;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QtWidgets.QPushButton("Créer les relations")
        self.save_btn.setMinimumHeight(35)
        self.save_btn.setMinimumWidth(150)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2980b9, stop:1 #3498db);
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.save_btn.clicked.connect(self._save_prerequisite)
        self.save_btn.setEnabled(False)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        return button_layout
    
    def _load_available_nodes(self):
        """Charge tous les nœuds disponibles depuis Dgraph"""
        if not self.dgraph_manager:
            logger.warning("Dgraph manager non disponible")
            return
        
        try:
            # Récupérer tous les nœuds
            all_nodes = self.dgraph_manager.connector.get_all_nodes_for_indexing()
            
            current_uid = self.current_node_info.get('uid')
            
            for node in all_nodes:
                # Ne pas inclure le nœud source lui-même
                if node.get('uid') == current_uid:
                    continue
                
                name = node.get('name', 'Sans nom')
                node_type = node.get('dgraph.type', ['Inconnu'])[0] if isinstance(node.get('dgraph.type'), list) else node.get('dgraph.type', 'Inconnu')
                uid = node.get('uid', '')
                
                # Format d'affichage avec préfixe selon le type
                type_prefix = {
                    'Typologie': 'Typologie',
                    'Cluster': 'Cluster',
                    'RootLabel': 'Racine',
                    'LabelNode': 'label'
                }.get(node_type, 'node')
                
                display_text = f"{type_prefix} [{node_type}] {name}"
                
                item = QtWidgets.QListWidgetItem(display_text)
                item.setData(Qt.UserRole, {
                    'uid': uid,
                    'name': name,
                    'type': node_type
                })
                
                self.nodes_list.addItem(item)
            
            logger.info(f"✅ {self.nodes_list.count()} nœuds chargés")
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement nœuds: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger les nœuds:\n{e}"
            )
    
    def _filter_nodes(self, text):
        """Filtre la liste des nœuds selon la recherche"""
        search_text = text.lower()
        
        for i in range(self.nodes_list.count()):
            item = self.nodes_list.item(i)
            item_text = item.text().lower()
            
            # Afficher/masquer selon la correspondance
            item.setHidden(search_text not in item_text)
    
    def _update_relation_table(self):
        """Met à jour le tableau des relations quand la sélection change"""
        selected_items = self.nodes_list.selectedItems()
        count = len(selected_items)
        
        # Activer/désactiver le bouton de sauvegarde
        self.save_btn.setEnabled(count > 0)
        
        # Mettre à jour le tableau
        self.relation_table.setRowCount(count)
        
        for row, item in enumerate(selected_items):
            node_data = item.data(Qt.UserRole)
            uid = node_data['uid']
            
            # Colonne 1 : Nom du nœud (lecture seule)
            name_item = QtWidgets.QTableWidgetItem(node_data['name'])
            name_item.setFlags(Qt.ItemIsEnabled)
            name_item.setToolTip(f"UID: {uid}")
            self.relation_table.setItem(row, 0, name_item)
            
            # Colonne 2 : Type (lecture seule)
            type_item = QtWidgets.QTableWidgetItem(node_data['type'])
            type_item.setFlags(Qt.ItemIsEnabled)
            self.relation_table.setItem(row, 1, type_item)
            
            # Colonne 3 : Champ de saisie du nom de la relation
            name_edit = QtWidgets.QLineEdit()
            name_edit.setPlaceholderText("Ex: Connaissances de base...")
            name_edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #e1e4e8;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 2px solid #3498db;
                }
            """)
            
            # Restaurer le nom existant si déjà saisi
            if uid in self.relation_names:
                name_edit.setText(self.relation_names[uid])
            
            # Connecter le signal pour sauvegarder automatiquement
            name_edit.textChanged.connect(
                lambda text, u=uid: self.relation_names.update({u: text})
            )
            
            self.relation_table.setCellWidget(row, 2, name_edit)
    
    def _save_prerequisite(self):
        """Sauvegarde les relations de prérequis avec leurs noms"""
        selected_items = self.nodes_list.selectedItems()
        
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self,
                "Sélection requise",
                "Veuillez sélectionner au moins un nœud prérequis"
            )
            return
        
        # Récupérer les UIDs des targets
        target_uids = [item.data(Qt.UserRole)['uid'] for item in selected_items]
        
        # Type de prérequis
        mandatory = self.mandatory_radio.isChecked()
        
        # Explication globale
        explanation = self.description_edit.toPlainText().strip()
        
        # Collecter les noms de relations depuis le tableau
        self.relation_names = {}
        for row in range(self.relation_table.rowCount()):
            name_item = self.relation_table.item(row, 0)
            uid = selected_items[row].data(Qt.UserRole)['uid']
            
            # Récupérer le widget QLineEdit dans la colonne 2
            name_widget = self.relation_table.cellWidget(row, 2)
            if name_widget and isinstance(name_widget, QtWidgets.QLineEdit):
                relation_name = name_widget.text().strip()
                self.relation_names[uid] = relation_name
        
        # Validation : au moins un nom doit être renseigné
        if not any(self.relation_names.values()):
            reply = QtWidgets.QMessageBox.question(
                self,
                "Noms manquants",
                "Aucun nom de relation n'a été renseigné.\n\n"
                "Voulez-vous continuer sans nommer les relations ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply != QtWidgets.QMessageBox.Yes:
                return
        
        # Sauvegarder les données pour récupération
        self.selected_targets = target_uids
        self.is_mandatory = mandatory
        self.explanation = explanation
        
        self.accept()
    
    def get_prerequisite_data(self):
        """Retourne les données de prérequis créées"""
        return {
            'source_uid': self.current_node_info.get('uid'),
            'target_uids': self.selected_targets,
            'mandatory': self.is_mandatory,
            'explanation': self.explanation,
            'relation_names': self.relation_names  # NOUVEAU : noms des relations
        }
    
class DatasetConfigTab(QtWidgets.QWidget):
    """Configuration tab for dataset projects with infinite child hierarchy"""
    
    project_saved = pyqtSignal()
    preview_updated = pyqtSignal(dict)

    def __init__(self, project_manager, config_data, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data
    
        # Cache hiérarchique unifié
        self.hierarchy_cache = HierarchyCache()
    
        # État de navigation pour les enfants
        self._child_navigation_path: list = []
    
        # === MODIFICATION: Initialiser Dgraph avec vérification préalable ===
        self.dgraph_manager = None
        self.dgraph_available = False
    
        # Tentative d'initialisation Dgraph (non bloquant)
        try:
            # Tenter de créer le manager directement
            # Le connecteur gère déjà sa propre vérification de connectivité
            database = project_manager.database if project_manager else None
            self.dgraph_manager = DgraphDatasetManager(database=database)
            self.dgraph_available = True
            logger.info("✅ Dgraph disponible et initialisé avec sync SQLite")
                
        except ConnectionError as e:
            # Le connecteur a levé une erreur de connexion
            logger.info("ℹ️ Dgraph non accessible sur le port 9082")
            logger.info("   Pour activer Dgraph: docker-compose up dgraph")
            self.dgraph_available = False
            self.dgraph_manager = None
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur initialisation Dgraph: {e}")
            logger.info("ℹ️ Le système fonctionnera uniquement avec SQLite")
            self.dgraph_manager = None
            self.dgraph_available = False
    
        self._init_ui()
        self._load_initial_data()
    
        # Afficher l'alerte de disponibilité seulement si critique
        self._show_storage_availability_alert()

    def _show_storage_availability_alert(self):
        """Affiche une alerte sur la disponibilité des systèmes de stockage"""
        sqlite_available = self.project_manager is not None
        dgraph_available = self.dgraph_available

        if sqlite_available and dgraph_available:
            logger.info("✅ SQLite et Dgraph disponibles - Mode dual actif")
            return

        if not sqlite_available and not dgraph_available:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur Critique",
                "❌ Aucun système de stockage disponible !\n\n"
                "Ni SQLite ni Dgraph ne sont accessibles.\n"
                "L'application ne peut pas fonctionner."
            )
            logger.error("❌ CRITIQUE: Aucun système de stockage disponible")
            return

        if not dgraph_available:
            QtWidgets.QMessageBox.warning(
                self,
                "Dgraph Non Disponible",
                "⚠️ Dgraph n'est pas disponible\n\n"
                "Le système fonctionnera uniquement avec SQLite.\n\n"
                "Raison: Connexion Dgraph impossible.\n"
                "Vérifiez que Dgraph est démarré sur le port 9082."
            )
            logger.warning("⚠️ Mode SQLite uniquement - Dgraph non disponible")

        if not sqlite_available:
            QtWidgets.QMessageBox.warning(
                self,
                "SQLite Non Disponible",
                "⚠️ SQLite n'est pas disponible\n\n"
                "Le système fonctionnera uniquement avec Dgraph.\n\n"
                "Raison: Base de données SQLite inaccessible."
            )
            logger.warning("⚠️ Mode Dgraph uniquement - SQLite non disponible")

    def _get_full_path(self) -> list:
        """
        Construire le chemin complet actuel - VERSION CORRIGÉE AVEC EXTRACTION DES COMPTEURS
        [typologie, cluster, root, parent, child1, child2, ...]
        """
        path = []

        typ_item = self.typologie_list.currentItem()
        if typ_item:
            # Extraire le nom sans compteur
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
            path.append(typ_name)
        else:
            logger.debug("Pas de typologie sélectionnée")
            return path

        if hasattr(self, 'taxonomy_list'):
            tax_item = self.taxonomy_list.currentItem()
            if tax_item:
                # Extraire le nom sans compteur
                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display
                path.append(tax_name)
            else:
                logger.debug("Pas de taxonomy sélectionnée")
                return path

        root_item = self.root_list.currentItem()
        if root_item:
            # Extraire le nom sans compteur
            root_display = root_item.text()
            root_name = root_display.split(" (")[0] if " (" in root_display else root_display
            path.append(root_name)
        else:
            logger.debug("Pas de root sélectionné")
            return path

        parent_item = self.parent_list.currentItem()
        if parent_item:
            parent_display = parent_item.text()
            # Extraire le nom sans compteur
            if " (" in parent_display:
                parent_name = parent_display.split(" (")[0]
            else:
                parent_name = parent_display
            path.append(parent_name)
        else:
            logger.debug("Pas de parent sélectionné")
            return path

        # Ajouter le chemin de navigation dans les enfants (déjà sans compteurs)
        path.extend(self._child_navigation_path)

        logger.debug(f"Chemin complet construit: {' > '.join(path)}")
        return path

    
    def _get_parent_path(self) -> list:
        """Chemin jusqu'au parent (excluant la navigation enfants)"""
        path = self._get_full_path()
        if len(path) > 4:
            return path[:4]
        return path
    
    def _sync_list_to_cache(self, list_widget: QtWidgets.QListWidget, 
                    parent_path: list):
        """Synchroniser une liste UI vers le cache - VERSION CORRIGÉE AVEC EXTRACTION DES COMPTEURS"""
        if not parent_path:
            logger.warning("Chemin parent vide pour sync")
            return

        items = []
        for i in range(list_widget.count()):
            item_display = list_widget.item(i).text()
            # CORRECTION: Extraire le nom sans compteur
            if " (" in item_display:
                item_name = item_display.split(" (")[0]
            else:
                item_name = item_display
            items.append(item_name)

        # Obtenir les enfants actuels du cache
        cached = self.hierarchy_cache.get_children_at_path(parent_path)

        # Ajouter les nouveaux
        for item in items:
            if item not in cached:
                self.hierarchy_cache.add_child_at_path(parent_path, item)

        logger.debug(f"Synced {len(items)} items to cache at {' > '.join(parent_path)}")


    def _load_list_from_cache(self, list_widget: QtWidgets.QListWidget,
                           parent_path: list):
        """Charger une liste UI depuis le cache avec comptage des enfants"""
        list_widget.clear()
        children = self.hierarchy_cache.get_children_at_path(parent_path)

        level = len(parent_path)

        for name in children:
            child_path = parent_path + [name]

            child_count = len(self.hierarchy_cache.get_children_at_path(child_path))

            if child_count > 0:
                display_name = f"{name} ({child_count})"
            else:
                display_name = name

            item = QtWidgets.QListWidgetItem(display_name)
            list_widget.addItem(item)

        logger.debug(f"Chargé {len(children)} éléments pour {' > '.join(parent_path) if parent_path else 'racine'}")

    def _refresh_parent_counts(self):
        """Rafraîchir les compteurs d'enfants pour tous les parents visibles - REMPLACÉ PAR _refresh_all_counts"""
        self._refresh_all_counts()

    def _get_current_cache_path(self):
        """
        Obtenir le chemin de cache actuel basé sur les sélections
        Retourne un tuple (typologie, taxonomy, root, parent) ou None
        """
        typologie_item = self.typologie_list.currentItem()
        if not typologie_item:
            return None
        
        typologie_name = typologie_item.text()
        
        taxonomy_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None
        if not taxonomy_item:
            return (typologie_name, None, None, None)
        
        taxonomy_name = taxonomy_item.text()
        
        root_item = self.root_list.currentItem()
        if not root_item:
            return (typologie_name, taxonomy_name, None, None)
        
        root_name = root_item.text()
        
        parent_item = self.parent_list.currentItem()
        if not parent_item:
            return (typologie_name, taxonomy_name, root_name, None)
        
        parent_name = parent_item.text()

        return (typologie_name, taxonomy_name, root_name, parent_name)

    def _load_children_from_cache(self):
        logger.debug("=" * 60)
        logger.debug("DÉBUT _load_children_from_cache")
        logger.debug("=" * 60)

        # Vider la liste
        logger.debug(f"Nombre d'items avant clear: {self.child_list.count()}")
        self.child_list.clear()
        logger.debug(f"Nombre d'items après clear: {self.child_list.count()}")

        # Construire le chemin
        path = self._get_full_path()

        logger.debug(f"Chemin complet obtenu: {path}")
        logger.debug(f"Longueur du chemin: {len(path)}")
        logger.debug(f"Navigation enfants actuelle: {self._child_navigation_path}")

        # Vérifier validité du chemin
        if len(path) < 4:
            logger.warning(f"⚠️ Chemin incomplet (longueur {len(path)}): {path}")
            logger.debug("Détails des sélections:")
            logger.debug(f"  - Typologie: {self.typologie_list.currentItem().text() if self.typologie_list.currentItem() else 'None'}")
            logger.debug(f"  - Taxonomy: {self.taxonomy_list.currentItem().text() if self.taxonomy_list.currentItem() else 'None'}")
            logger.debug(f"  - Root: {self.root_list.currentItem().text() if self.root_list.currentItem() else 'None'}")
            logger.debug(f"  - Parent: {self.parent_list.currentItem().text() if self.parent_list.currentItem() else 'None'}")
            return

        logger.debug(f"✓ Chemin valide: {' > '.join(path)}")

        # Récupérer les enfants du cache
        logger.debug(f"Appel hierarchy_cache.get_children_at_path({path})")
        children = self.hierarchy_cache.get_children_at_path(path)

        logger.debug(f"✓ Enfants trouvés dans le cache: {children}")
        logger.debug(f"✓ Nombre d'enfants: {len(children)}")

        # Ajouter chaque enfant à la liste UI
        for idx, name in enumerate(children):
            logger.debug(f"  Traitement enfant {idx + 1}/{len(children)}: '{name}'")

            # Compter les sous-enfants
            child_path = path + [name]
            logger.debug(f"    Chemin enfant: {' > '.join(child_path)}")

            subchildren = self.hierarchy_cache.get_children_at_path(child_path)
            subchild_count = len(subchildren)
            logger.debug(f"    Sous-enfants: {subchild_count} ({subchildren})")

            # Créer le nom d'affichage
            if subchild_count > 0:
                display_name = f"{name} ({subchild_count})"
            else:
                display_name = name

            logger.debug(f"    Nom d'affichage: '{display_name}'")

            # Ajouter à la liste UI
            item = QtWidgets.QListWidgetItem(display_name)
            self.child_list.addItem(item)
            logger.debug(f"    ✓ Ajouté à child_list")

        # Vérification finale
        final_count = self.child_list.count()
        logger.debug(f"✓ Total d'items dans child_list: {final_count}")

        if final_count != len(children):
            logger.error(f"⚠️ INCOHÉRENCE: {len(children)} dans cache mais {final_count} dans UI!")

        depth = len(self._child_navigation_path)
        logger.debug(f"Profondeur actuelle: {depth}")
        logger.debug("=" * 60)
        logger.debug("FIN _load_children_from_cache")
        logger.debug("=" * 60)

    def _refresh_all_counts(self):
        """Rafraîchir tous les compteurs d'enfants dans toutes les listes"""
        # Rafraîchir la liste des typologies
        self._load_list_from_cache(self.typologie_list, [])
        
        # Rafraîchir taxonomy si une typologie est sélectionnée
        typ_item = self.typologie_list.currentItem()
        if typ_item:
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
            self._load_list_from_cache(self.taxonomy_list, [typ_name])
            
            # Rafraîchir root si un taxonomy est sélectionné
            tax_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None
            if tax_item:
                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display
                self._load_list_from_cache(self.root_list, [typ_name, tax_name])
                
                # Rafraîchir parent si un root est sélectionné
                root_item = self.root_list.currentItem()
                if root_item:
                    root_display = root_item.text()
                    root_name = root_display.split(" (")[0] if " (" in root_display else root_display
                    self._load_list_from_cache(self.parent_list, [typ_name, tax_name, root_name])

    def _get_or_create_cache_structure(self, typologie_name, taxonomy_name=None, 
                                       root_name=None, parent_name=None):
        """
        Obtenir ou créer la structure de cache pour un chemin donné
        Retourne le nœud du cache correspondant au niveau demandé
        """
        if typologie_name not in self.temp_hierarchy_cache:
            self.temp_hierarchy_cache[typologie_name] = {}
        
        if taxonomy_name is None:
            return self.temp_hierarchy_cache[typologie_name]
        
        if taxonomy_name not in self.temp_hierarchy_cache[typologie_name]:
            self.temp_hierarchy_cache[typologie_name][taxonomy_name] = {}
        
        if root_name is None:
            return self.temp_hierarchy_cache[typologie_name][taxonomy_name]
        
        if root_name not in self.temp_hierarchy_cache[typologie_name][taxonomy_name]:
            self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name] = {}
        
        if parent_name is None:
            return self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name]
        
        if parent_name not in self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name]:
            # Initialiser avec une structure pour les enfants récursifs
            self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name][parent_name] = {
                '_children': [],  # Liste des enfants directs
                '_sublevels': {}   # Dictionnaire récursif pour les sous-niveaux
            }
        
        return self.temp_hierarchy_cache[typologie_name][taxonomy_name][root_name][parent_name]

    def _init_ui(self):
        """Create configuration tab with responsive design"""
        # Container principal avec scroll
        main_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(main_container)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(10)

        left_layout = self._create_left_column()
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        # Largeur confortable pour la colonne gauche
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(350)
        left_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        columns_layout.addWidget(left_widget, 3)

        right_layout = self._create_right_column()
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setMinimumWidth(350)  # Réduit de 400 à 350
        right_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        columns_layout.addWidget(right_widget, 7)

        layout.addLayout(columns_layout)
        self._create_action_buttons(layout)

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

    def _create_left_column(self):
        """Create left column (project selection and details) - responsive"""
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(10)

        project_group = self._create_modern_group(tr("dataset.select_project"))
        project_layout = QtWidgets.QVBoxLayout(project_group)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.setMinimumHeight(32)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_layout.addWidget(self.project_combo)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(4)

        self.add_project_btn = self._create_compact_button(tr("dataset.new_project"), self._add_project)
        self.delete_project_btn = self._create_compact_button(tr("dataset.delete_project"), self._delete_project)

        self.add_project_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(False)

        btn_layout.addWidget(self.add_project_btn)
        btn_layout.addWidget(self.delete_project_btn)
        btn_layout.addStretch()
        project_layout.addLayout(btn_layout)

        left_layout.addWidget(project_group)

        details_group = self._create_modern_group(tr("dataset.project_details"))
        details_group.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        details_layout = QtWidgets.QFormLayout(details_group)
        details_layout.setSpacing(8)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(tr("dataset.project_name_placeholder"))
        self.project_name_edit.setStyleSheet(self._get_modern_input_style())
        self.project_name_edit.setMinimumHeight(32)
        details_layout.addRow(tr("dataset.project_name"), self.project_name_edit)

        typologie_section = self._create_typologie_section()
        details_layout.addRow(typologie_section)

        left_layout.addWidget(details_group)

        return left_layout

    def _create_typologie_section(self):
        """Create typologies section - responsive with grid buttons"""
        container = QtWidgets.QWidget()
        container.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QtWidgets.QLabel(tr("dataset.typologies"))
        title.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 12px;")
        layout.addWidget(title)

        self.typologie_list = QtWidgets.QListWidget()
        self.typologie_list.setStyleSheet(self._get_modern_list_style())
        self.typologie_list.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.typologie_list.setMinimumHeight(80)
        self.typologie_list.currentItemChanged.connect(self._on_typologie_selected)
        layout.addWidget(self.typologie_list)

        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QGridLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(3)

        self.add_typologie_btn = self._create_compact_button(tr("dataset.add"), self._add_typologie)
        self.edit_typologie_btn = self._create_compact_button(tr("dataset.edit"), self._edit_typologie)
        self.remove_typologie_btn = self._create_compact_button(tr("dataset.delete"), self._remove_typologie)

        # NOUVEAU: Bouton relation pour typologie
        self.relation_typologie_btn = self._create_compact_button(
            "Relation", 
            lambda: self._open_relation_dialog('typologie')
        )

        self.add_typologie_btn.setEnabled(False)
        self.edit_typologie_btn.setEnabled(False)
        self.remove_typologie_btn.setEnabled(False)
        self.relation_typologie_btn.setEnabled(False)  # NOUVEAU

        # Disposition en grille 2x2
        btn_layout.addWidget(self.add_typologie_btn, 0, 0)
        btn_layout.addWidget(self.edit_typologie_btn, 0, 1)
        btn_layout.addWidget(self.remove_typologie_btn, 1, 0)
        btn_layout.addWidget(self.relation_typologie_btn, 1, 1)  # NOUVEAU

        layout.addWidget(btn_container)

        return container
    
    def _load_initial_data(self):
        """Charge les données initiales"""
        try:
            self._refresh_project_combos()
            
            if self.project_manager.current_project_name:
                index = self.project_combo.findText(self.project_manager.current_project_name)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                    self._load_project_ui()
            
            logger.info(f"Projets chargés: {self.project_combo.count()} projet(s) trouvé(s)")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement initial des données: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self, 
                "Erreur de chargement", 
                f"Impossible de charger les projets: {str(e)}"
            )

    def resizeEvent(self, event):
        """Handle resize to switch between horizontal and vertical layouts"""
        super().resizeEvent(event)
        width = self.width()
        pass

    def _create_right_column(self):
        """Create right column (hierarchy in 2x2 grid) - responsive"""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        taxonomy_widget = self._create_label_section('taxonomy', tr("dataset.taxonomy_clusters"))
        grid.addWidget(taxonomy_widget, 0, 0)

        root_widget = self._create_label_section('root', tr("dataset.root_labels"))
        grid.addWidget(root_widget, 0, 1)

        parent_widget = self._create_label_section('parent', tr("dataset.parent_labels"))
        grid.addWidget(parent_widget, 1, 0)

        child_widget = self._create_dynamic_child_section()
        grid.addWidget(child_widget, 1, 1)

        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        layout.addLayout(grid)

        return layout

    def _create_label_section(self, level, title):
        """Create a label section with list and action buttons - VERSION AVEC RELATION"""
        group = self._create_modern_group(title)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_modern_list_style())
        list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        list_widget.setMinimumHeight(100)
        layout.addWidget(list_widget)

        if level == 'taxonomy':
            self.taxonomy_list = list_widget
            list_widget.currentItemChanged.connect(self._on_taxonomy_selected)
        elif level == 'root':
            self.root_list = list_widget
            list_widget.currentItemChanged.connect(self._on_root_selected)
        elif level == 'parent':
            self.parent_list = list_widget
            list_widget.currentItemChanged.connect(self._on_parent_selected)

        # === LIGNE 1: Boutons principaux ===
        btn_container1 = QtWidgets.QWidget()
        btn_layout1 = QtWidgets.QHBoxLayout(btn_container1)
        btn_layout1.setContentsMargins(0, 0, 0, 0)
        btn_layout1.setSpacing(2)

        add_btn = self._create_compact_button(tr("dataset.add"), lambda: self._add_label(level))
        edit_btn = self._create_compact_button(tr("dataset.edit"), lambda: self._edit_label(level))
        delete_btn = self._create_compact_button(tr("dataset.delete"), lambda: self._remove_label(level))

        setattr(self, f'add_{level}_btn', add_btn)
        setattr(self, f'edit_{level}_btn', edit_btn)
        setattr(self, f'remove_{level}_btn', delete_btn)

        add_btn.setEnabled(False)
        edit_btn.setEnabled(False)
        delete_btn.setEnabled(False)

        btn_layout1.addWidget(add_btn, 1)
        btn_layout1.addWidget(edit_btn, 1)
        btn_layout1.addWidget(delete_btn, 1)

        layout.addWidget(btn_container1)

        # === LIGNE 2: Boutons d'insertion ===
        btn_container2 = QtWidgets.QWidget()
        btn_layout2 = QtWidgets.QHBoxLayout(btn_container2)
        btn_layout2.setContentsMargins(0, 0, 0, 0)
        btn_layout2.setSpacing(2)

        insert_parent_btn = self._create_compact_button(
            "↑ Parent", 
            lambda: self._insert_parent_above(level)
        )
        insert_child_btn = self._create_compact_button(
            "↓ Enfant", 
            lambda: self._insert_child_below(level)
        )
        setattr(self, f'insert_parent_{level}_btn', insert_parent_btn)
        setattr(self, f'insert_child_{level}_btn', insert_child_btn)

        insert_parent_btn.setEnabled(False)
        insert_child_btn.setEnabled(False)

        btn_layout2.addWidget(insert_parent_btn, 1)
        btn_layout2.addWidget(insert_child_btn, 1)

        layout.addWidget(btn_container2)

        # === LIGNE 3: Bouton de relation (NOUVEAU) ===
        btn_container3 = QtWidgets.QWidget()
        btn_layout3 = QtWidgets.QHBoxLayout(btn_container3)
        btn_layout3.setContentsMargins(0, 0, 0, 0)
        btn_layout3.setSpacing(2)

        relation_btn = self._create_compact_button(
            "Relation", 
            lambda: self._open_relation_dialog(level)
        )
        setattr(self, f'relation_{level}_btn', relation_btn)
        relation_btn.setEnabled(False)

        btn_layout3.addWidget(relation_btn, 1)

        layout.addWidget(btn_container3)

        return group

    def _create_dynamic_child_section(self):
        """Create dynamic child section with breadcrumb navigation - VERSION AVEC RELATION"""
        group = self._create_modern_group(tr("dataset.child_labels"))
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        # Breadcrumb
        breadcrumb_container = QtWidgets.QWidget()
        breadcrumb_layout = QtWidgets.QHBoxLayout(breadcrumb_container)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        breadcrumb_layout.setSpacing(3)

        self.breadcrumb_label = QtWidgets.QLabel(tr("dataset.root"))
        self.breadcrumb_label.setStyleSheet("""
            color: #7f8c8d;
            font-size: 10px;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 3px 6px;
            background-color: #f8f9fa;
            border-radius: 3px;
        """)
        self.breadcrumb_label.setWordWrap(True)
        self.breadcrumb_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        breadcrumb_layout.addWidget(self.breadcrumb_label, 3)

        self.up_btn = self._create_compact_button(tr("dataset.up"), self._navigate_up)
        self.up_btn.setEnabled(False)
        breadcrumb_layout.addWidget(self.up_btn, 1)

        self.dive_btn = self._create_compact_button(tr("dataset.dive"), self._navigate_into_child)
        self.dive_btn.setEnabled(False)
        breadcrumb_layout.addWidget(self.dive_btn, 1)

        layout.addWidget(breadcrumb_container)

        # Liste
        self.child_list = QtWidgets.QListWidget()
        self.child_list.setStyleSheet(self._get_modern_list_style())
        self.child_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.child_list.setMinimumHeight(100)
        self.child_list.currentItemChanged.connect(self._on_child_selected)
        self.child_list.itemDoubleClicked.connect(self._navigate_into_child)
        layout.addWidget(self.child_list)

        # === LIGNE 1: Boutons principaux ===
        btn_container1 = QtWidgets.QWidget()
        btn_layout1 = QtWidgets.QHBoxLayout(btn_container1)
        btn_layout1.setContentsMargins(0, 0, 0, 0)
        btn_layout1.setSpacing(2)

        self.add_child_btn = self._create_compact_button(tr("dataset.add"), self._add_child)
        self.edit_child_btn = self._create_compact_button(tr("dataset.edit"), self._edit_child)
        self.remove_child_btn = self._create_compact_button(tr("dataset.delete"), self._remove_child)

        self.add_child_btn.setEnabled(False)
        self.edit_child_btn.setEnabled(False)
        self.remove_child_btn.setEnabled(False)

        btn_layout1.addWidget(self.add_child_btn, 1)
        btn_layout1.addWidget(self.edit_child_btn, 1)
        btn_layout1.addWidget(self.remove_child_btn, 1)

        layout.addWidget(btn_container1)

        # === LIGNE 2: Boutons d'insertion ===
        btn_container2 = QtWidgets.QWidget()
        btn_layout2 = QtWidgets.QHBoxLayout(btn_container2)
        btn_layout2.setContentsMargins(0, 0, 0, 0)
        btn_layout2.setSpacing(2)

        self.insert_parent_child_btn = self._create_compact_button(
            "↑ Parent", 
            lambda: self._insert_parent_above('child')
        )

        self.insert_child_child_btn = self._create_compact_button(
            "↓ Enfant", 
            lambda: self._insert_child_below('child')
        )

        self.insert_parent_child_btn.setEnabled(False)
        self.insert_child_child_btn.setEnabled(False)

        btn_layout2.addWidget(self.insert_parent_child_btn, 1)
        btn_layout2.addWidget(self.insert_child_child_btn, 1)

        layout.addWidget(btn_container2)

        # === LIGNE 3: Bouton de relation (NOUVEAU) ===
        btn_container3 = QtWidgets.QWidget()
        btn_layout3 = QtWidgets.QHBoxLayout(btn_container3)
        btn_layout3.setContentsMargins(0, 0, 0, 0)
        btn_layout3.setSpacing(2)

        self.relation_child_btn = self._create_compact_button(
            "Relation", 
            lambda: self._open_relation_dialog('child')
        )
        self.relation_child_btn.setEnabled(False)

        btn_layout3.addWidget(self.relation_child_btn, 1)

        layout.addWidget(btn_container3)

        return group
    
    def _open_relation_dialog(self, level):
        """
        Ouvre le dialogue de création de relation de prérequis
        VERSION COMPLÈTE avec nommage des relations et synchronisation SQLite
        """
        logger.info("=" * 80)
        logger.info(f"🔗 OUVERTURE DIALOGUE RELATION - Niveau: {level}")
        logger.info("=" * 80)

        # Vérifier disponibilité Dgraph
        if not self.dgraph_available or not self.dgraph_manager:
            logger.warning("⚠️ Dgraph non disponible")
            QtWidgets.QMessageBox.warning(
                self,
                "Dgraph non disponible",
                "Les relations de prérequis nécessitent Dgraph.\n\n"
                "Dgraph n'est pas disponible actuellement."
            )
            return

        logger.info(f"✓ Dgraph disponible et connecté")

        # Récupérer l'élément sélectionné
        if level == 'typologie':
            list_widget = self.typologie_list
        else:
            list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()

        if not current:
            logger.warning(f"⚠️ Aucun élément sélectionné au niveau '{level}'")
            QtWidgets.QMessageBox.warning(
                self,
                "Sélection requise",
                f"Veuillez sélectionner un élément au niveau '{level}'"
            )
            return

        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display

        logger.info(f"📝 Élément sélectionné:")
        logger.info(f"   - Niveau: {level}")
        logger.info(f"   - Nom affiché: '{element_display}'")
        logger.info(f"   - Nom extrait: '{element_name}'")

        # Récupérer l'UID du nœud source
        logger.info(f"🔍 Recherche de l'UID dans Dgraph...")

        try:
            source_uid = self.dgraph_manager.get_node_uid_by_path(level, element_name, self)

            if not source_uid:
                logger.error(f"❌ UID non trouvé pour '{element_name}' au niveau '{level}'")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible de trouver le nœud '{element_name}' dans Dgraph"
                )
                return

            logger.info(f"✅ UID trouvé: {source_uid}")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de l'UID: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la recherche du nœud:\n{e}"
            )
            return

        # Préparer les infos du nœud source pour le dialogue
        current_node_info = {
            'uid': source_uid,
            'name': element_name,
            'type': level.capitalize()
        }

        logger.info(f"📋 Informations du nœud source:")
        logger.info(f"   - UID: {current_node_info['uid']}")
        logger.info(f"   - Nom: {current_node_info['name']}")
        logger.info(f"   - Type: {current_node_info['type']}")

        # Ouvrir le dialogue
        logger.info(f"🎨 Ouverture du dialogue PrerequisiteDialog...")

        try:
            dialog = PrerequisiteDialog(
                dgraph_manager=self.dgraph_manager,
                current_node_info=current_node_info,
                parent=self
            )

            logger.info(f"✓ Dialogue créé avec succès")

            result = dialog.exec_()

            if result == QtWidgets.QDialog.Accepted:
                logger.info(f"✓ Dialogue accepté par l'utilisateur")

                # Récupérer les données de prérequis
                prereq_data = dialog.get_prerequisite_data()

                logger.info(f"📊 Données de prérequis récupérées:")
                logger.info(f"   - Source UID: {prereq_data['source_uid']}")
                logger.info(f"   - Nombre de targets: {len(prereq_data['target_uids'])}")
                logger.info(f"   - Obligatoire: {prereq_data['mandatory']}")
                logger.info(f"   - Noms de relations:")
                for uid, name in prereq_data['relation_names'].items():
                    logger.info(f"      • {uid}: '{name}'")

                # === CRÉATION DANS DGRAPH AVEC NOMS ===
                dgraph_success = self.dgraph_manager.create_prerequisites(
                    source_uid=prereq_data['source_uid'],
                    target_uids=prereq_data['target_uids'],
                    mandatory=prereq_data['mandatory'],
                    explanation=prereq_data['explanation'],
                    relation_names=prereq_data['relation_names']  # NOUVEAU
                )

                if not dgraph_success:
                    logger.error(f"❌ ÉCHEC: Impossible de créer les relations de prérequis")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Échec",
                        f"❌ Impossible de créer les relations de prérequis\n\n"
                        f"Vérifiez les logs pour plus de détails."
                    )
                    return

                # === SYNCHRONISATION SQLITE ===
                sqlite_success = False

                try:
                    # Récupérer l'ID SQLite du source
                    source_id = self._get_sqlite_id_for_node(level, element_name)

                    if source_id:
                        logger.info(f"📊 Synchronisation SQLite pour source ID: {source_id}")

                        # Pour chaque target, créer la relation dans SQLite
                        for target_uid in prereq_data['target_uids']:
                            # Récupérer le type et l'ID depuis Dgraph
                            entity_info = self.dgraph_manager.database.get_entity_id_by_uid(target_uid)

                            if entity_info:
                                target_type, target_id = entity_info
                                relation_name = prereq_data['relation_names'].get(target_uid, '')

                                # Sauvegarder dans SQLite avec le nom de la relation
                                self.dgraph_manager.sync_prerequisite_to_sqlite(
                                    level, source_id,
                                    target_type, target_id,
                                    prereq_data['mandatory'],
                                    prereq_data['explanation'],
                                    relation_name  # NOUVEAU
                                )

                                logger.info(f"   ✓ Relation '{relation_name}' synchronisée vers SQLite")

                        sqlite_success = True
                        logger.info(f"✅ {len(prereq_data['target_uids'])} prérequis synchronisés vers SQLite")

                except Exception as sync_error:
                    logger.warning(f"⚠️ Erreur sync SQLite: {sync_error}")
                    import traceback
                    logger.warning(traceback.format_exc())

                # === MESSAGE FINAL DÉTAILLÉ ===
                prereq_type = "obligatoires" if prereq_data['mandatory'] else "recommandés"

                # Construire le résumé des relations créées
                relations_summary = []
                for target_uid in prereq_data['target_uids']:
                    relation_name = prereq_data['relation_names'].get(target_uid, "(sans nom)")
                    if relation_name and relation_name.strip():
                        relations_summary.append(f"  • {relation_name}")
                    else:
                        relations_summary.append(f"  • Relation sans nom")

                summary_text = "\n".join(relations_summary) if relations_summary else "  (aucun nom spécifié)"

                if sqlite_success:
                    logger.info(f"✅✅✅ SUCCÈS COMPLET: {len(prereq_data['target_uids'])} prérequis {prereq_type} créés")
                    logger.info(f"   Pour: '{element_name}' ({source_uid})")
                    logger.info(f"   Synchronisés: Dgraph + SQLite")
                    logger.info(f"   Relations créées:\n{summary_text}")

                    QtWidgets.QMessageBox.information(
                        self,
                        "Succès",
                        f"✅ {len(prereq_data['target_uids'])} relation(s) créée(s) pour '{element_name}'\n\n"
                        f"Type: {'Obligatoire' if prereq_data['mandatory'] else 'Recommandé'}\n"
                        f"Synchronisé: Dgraph + SQLite\n\n"
                        f"Relations créées:\n{summary_text}"
                    )
                else:
                    logger.warning(f"⚠️ SUCCÈS PARTIEL: Créé dans Dgraph uniquement")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Succès partiel",
                        f"⚠️ {len(prereq_data['target_uids'])} relation(s) créée(s) pour '{element_name}'\n\n"
                        f"Type: {'Obligatoire' if prereq_data['mandatory'] else 'Recommandé'}\n"
                        f"Synchronisé: Dgraph uniquement (SQLite a échoué)\n\n"
                        f"Relations créées:\n{summary_text}"
                    )
            else:
                logger.info(f"⚠️ Dialogue annulé par l'utilisateur")

        except Exception as e:
            logger.error(f"❌ Erreur lors du dialogue de relation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue:\n{e}"
            )

        logger.info("=" * 80)
        logger.info(f"🔗 FIN DIALOGUE RELATION")
        logger.info("=" * 80)

    def _get_sqlite_id_for_node(self, level, name):
        if not self.project_manager:
            logger.warning("⚠️ Project manager non disponible")
            return None

        try:
            if level == 'typologie':
                return self._get_typologie_sqlite_id(name)
            elif level == 'taxonomy':
                return self._get_taxonomy_sqlite_id(name)
            elif level == 'root':
                return self._get_root_sqlite_id(name)
            elif level == 'parent':
                return self._get_parent_sqlite_id(name)
            elif level == 'child':
                return self._get_child_sqlite_id(name)
            else:
                logger.warning(f"⚠️ Niveau inconnu: {level}")
                return None

        except Exception as e:
            logger.error(f"❌ Erreur récupération ID SQLite pour {level} '{name}': {e}")
            return None
        
    def _get_child_sqlite_id(self, name):
        """Récupère l'ID SQLite d'un child label"""
        # Pour les enfants, c'est plus complexe car on doit naviguer dans la hiérarchie
        typologie = self.project_manager.get_current_typologie()
        taxonomy = self.project_manager.get_current_taxonomy()
        root = self.project_manager.get_current_root()
        parent = self.project_manager.get_current_parent()

        if not all([typologie, taxonomy, root, parent]):
            return None

        # Construire le chemin complet
        path = self._get_full_path()

        # Chercher dans la base en utilisant le chemin
        cursor = self.project_manager.database.connection.cursor()

        # Stratégie : chercher par nom et parent_label_id ou parent_child_id
        # On commence par le parent direct
        cursor.execute("""
            SELECT pl.id FROM parent_labels pl
            JOIN root_labels rl ON pl.root_id = rl.id
            JOIN taxonomy_clusters tc ON rl.taxonomy_id = tc.id
            JOIN typologies t ON tc.typologie_id = t.id
            JOIN projects p ON t.project_id = p.id
            WHERE p.name = ? AND t.name = ? AND tc.name = ? 
            AND rl.name = ? AND pl.name = ?
        """, (
            self.project_manager.current_project_name,
            typologie.get('name'),
            taxonomy.get('name'),
            root.get('name'),
            parent.get('name')
        ))

        parent_row = cursor.fetchone()
        if not parent_row:
            return None

        parent_id = parent_row['id']

        # Naviguer dans les enfants selon le chemin
        current_parent_id = parent_id
        current_parent_child_id = None

        # Naviguer jusqu'à l'avant-dernier élément du chemin
        for i in range(4, len(path) - 1):  # Commencer après typologie, taxonomy, root, parent
            child_name = path[i]

            if current_parent_child_id is None:
                # Premier niveau d'enfants
                cursor.execute("""
                    SELECT id FROM child_labels
                    WHERE parent_label_id = ? AND parent_child_id IS NULL AND name = ?
                """, (current_parent_id, child_name))
            else:
                # Niveaux suivants
                cursor.execute("""
                    SELECT id FROM child_labels
                    WHERE parent_child_id = ? AND name = ?
                """, (current_parent_child_id, child_name))

            row = cursor.fetchone()
            if not row:
                return None

            current_parent_child_id = row['id']
            current_parent_id = None

        # Chercher l'enfant final
        if current_parent_child_id is None:
            # Premier niveau
            cursor.execute("""
                SELECT id FROM child_labels
                WHERE parent_label_id = ? AND parent_child_id IS NULL AND name = ?
            """, (parent_id, name))
        else:
            # Niveaux profonds
            cursor.execute("""
                SELECT id FROM child_labels
                WHERE parent_child_id = ? AND name = ?
            """, (current_parent_child_id, name))

        row = cursor.fetchone()
        return row['id'] if row else None
        
    def _get_parent_sqlite_id(self, name):
        """Récupère l'ID SQLite d'un parent label"""
        typologie = self.project_manager.get_current_typologie()
        taxonomy = self.project_manager.get_current_taxonomy()
        root = self.project_manager.get_current_root()

        if not typologie or not taxonomy or not root:
            return None

        parents = root.get('parent_labels', [])
        for parent in parents:
            if parent.get('name') == name:
                if 'id' in parent:
                    return parent['id']

                # Chercher dans la base
                cursor = self.project_manager.database.connection.cursor()
                cursor.execute("""
                    SELECT pl.id FROM parent_labels pl
                    JOIN root_labels rl ON pl.root_id = rl.id
                    JOIN taxonomy_clusters tc ON rl.taxonomy_id = tc.id
                    JOIN typologies t ON tc.typologie_id = t.id
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.name = ? AND t.name = ? AND tc.name = ? 
                    AND rl.name = ? AND pl.name = ?
                """, (
                    self.project_manager.current_project_name,
                    typologie.get('name'),
                    taxonomy.get('name'),
                    root.get('name'),
                    name
                ))

                row = cursor.fetchone()
                return row['id'] if row else None

        return None
        
    def _get_root_sqlite_id(self, name):
        """Récupère l'ID SQLite d'un root label"""
        typologie = self.project_manager.get_current_typologie()
        taxonomy = self.project_manager.get_current_taxonomy()

        if not typologie or not taxonomy:
            return None

        roots = taxonomy.get('root_labels', [])
        for root in roots:
            if root.get('name') == name:
                if 'id' in root:
                    return root['id']

                # Chercher dans la base
                cursor = self.project_manager.database.connection.cursor()
                cursor.execute("""
                    SELECT rl.id FROM root_labels rl
                    JOIN taxonomy_clusters tc ON rl.taxonomy_id = tc.id
                    JOIN typologies t ON tc.typologie_id = t.id
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.name = ? AND t.name = ? AND tc.name = ? AND rl.name = ?
                """, (
                    self.project_manager.current_project_name,
                    typologie.get('name'),
                    taxonomy.get('name'),
                    name
                ))

                row = cursor.fetchone()
                return row['id'] if row else None

        return None
    
        
    def _get_typologie_sqlite_id(self, name):
        """Récupère l'ID SQLite d'une typologie"""
        if not self.project_manager.current_project_data:
            return None

        typologies = self.project_manager.current_project_data.get('typologies', [])
        for idx, typologie in enumerate(typologies):
            if typologie.get('name') == name:
                # Si l'ID est stocké
                if 'id' in typologie:
                    return typologie['id']

                # Sinon, chercher dans la base
                cursor = self.project_manager.database.connection.cursor()
                cursor.execute("""
                    SELECT t.id FROM typologies t
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.name = ? AND t.name = ?
                """, (self.project_manager.current_project_name, name))

                row = cursor.fetchone()
                return row['id'] if row else None

        return None
    
    def _get_taxonomy_sqlite_id(self, name):
        """Récupère l'ID SQLite d'un cluster de taxonomie"""
        typologie = self.project_manager.get_current_typologie()
        if not typologie:
            return None

        clusters = typologie.get('taxonomy_clusters', [])
        for cluster in clusters:
            if cluster.get('name') == name:
                if 'id' in cluster:
                    return cluster['id']

                # Chercher dans la base
                cursor = self.project_manager.database.connection.cursor()
                cursor.execute("""
                    SELECT tc.id FROM taxonomy_clusters tc
                    JOIN typologies t ON tc.typologie_id = t.id
                    JOIN projects p ON t.project_id = p.id
                    WHERE p.name = ? AND t.name = ? AND tc.name = ?
                """, (
                    self.project_manager.current_project_name,
                    typologie.get('name'),
                    name
                ))

                row = cursor.fetchone()
                return row['id'] if row else None

        return None
    
    def _create_label_section_with_insert(self, level, title):
        """
        Version étendue de _create_label_section avec boutons d'insertion
        Remplace la méthode existante
        """
        group = self._create_modern_group(title)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(6)

        list_widget = QtWidgets.QListWidget()
        list_widget.setStyleSheet(self._get_modern_list_style())
        list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        list_widget.setMinimumHeight(100)
        layout.addWidget(list_widget)

        if level == 'taxonomy':
            self.taxonomy_list = list_widget
            list_widget.currentItemChanged.connect(self._on_taxonomy_selected)
        elif level == 'root':
            self.root_list = list_widget
            list_widget.currentItemChanged.connect(self._on_root_selected)
        elif level == 'parent':
            self.parent_list = list_widget
            list_widget.currentItemChanged.connect(self._on_parent_selected)

        # === BOUTONS PRINCIPAUX (ligne 1) ===
        btn_container1 = QtWidgets.QWidget()
        btn_layout1 = QtWidgets.QHBoxLayout(btn_container1)
        btn_layout1.setContentsMargins(0, 0, 0, 0)
        btn_layout1.setSpacing(2)

        add_btn = self._create_compact_button(tr("dataset.add"), lambda: self._add_label(level))
        edit_btn = self._create_compact_button(tr("dataset.edit"), lambda: self._edit_label(level))
        delete_btn = self._create_compact_button(tr("dataset.delete"), lambda: self._remove_label(level))

        setattr(self, f'add_{level}_btn', add_btn)
        setattr(self, f'edit_{level}_btn', edit_btn)
        setattr(self, f'remove_{level}_btn', delete_btn)

        add_btn.setEnabled(False)
        edit_btn.setEnabled(False)
        delete_btn.setEnabled(False)

        btn_layout1.addWidget(add_btn, 1)
        btn_layout1.addWidget(edit_btn, 1)
        btn_layout1.addWidget(delete_btn, 1)

        layout.addWidget(btn_container1)

        # === BOUTONS D'INSERTION (ligne 2) ===
        btn_container2 = QtWidgets.QWidget()
        btn_layout2 = QtWidgets.QHBoxLayout(btn_container2)
        btn_layout2.setContentsMargins(0, 0, 0, 0)
        btn_layout2.setSpacing(2)

        # Bouton "Insérer Parent Au-Dessus"
        insert_parent_btn = self._create_compact_button(
            "↑ Parent", 
            lambda: self._insert_parent_above_selected(level)
        )

        # Bouton "Insérer Enfant Entre"
        insert_child_btn = self._create_compact_button(
            "↓ Enfant", 
            lambda: self._insert_child_between_selected(level)
        )
        # Bouton "Promouvoir"
        promote_btn = self._create_compact_button(
            "⬆ Niveau+", 
            lambda: self._promote_selected(level)
        )

        setattr(self, f'insert_parent_{level}_btn', insert_parent_btn)
        setattr(self, f'insert_child_{level}_btn', insert_child_btn)
        setattr(self, f'promote_{level}_btn', promote_btn)

        insert_parent_btn.setEnabled(False)
        insert_child_btn.setEnabled(False)
        promote_btn.setEnabled(False)

        btn_layout2.addWidget(insert_parent_btn, 1)
        btn_layout2.addWidget(insert_child_btn, 1)
        btn_layout2.addWidget(promote_btn, 1)

        layout.addWidget(btn_container2)

        return group
    
    def _insert_parent_above_selected(self, level):
        """
        Insère un nouveau parent au-dessus de l'élément sélectionné
        """
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(
                self, "Sélection requise",
                "Veuillez sélectionner un élément pour insérer un parent au-dessus"
            )
            return
        
        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display
        
        # Demander le nom du nouveau parent
        new_parent_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Insérer Parent Au-Dessus",
            f"Nouveau parent pour '{element_name}':\n\n"
            f"Structure: ... → NOUVEAU → {element_name} → ...",
            QtWidgets.QLineEdit.Normal
        )
        
        if not ok or not new_parent_name.strip():
            return
        
        new_parent_name = new_parent_name.strip()
        
        # Obtenir le chemin parent
        path = self._get_path_for_level(level)
        if path is None:
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                "Impossible de déterminer le chemin"
            )
            return
        
        # Sauvegarder les sélections
        saved_selections = self._save_current_selections()
        
        # Effectuer l'insertion dans le cache
        if self.hierarchy_cache.insert_parent_above(path, element_name, new_parent_name):
            # Recharger l'interface
            self._refresh_ui_after_insert(level, saved_selections)
            
            QtWidgets.QMessageBox.information(
                self, "Succès",
                f"✅ Parent '{new_parent_name}' inséré au-dessus de '{element_name}'\n\n"
                f"Nouvelle structure:\n"
                f"{' → '.join(path)} → {new_parent_name} → {element_name}"
            )
            
            logger.info(f"✅ Parent inséré: {new_parent_name} > {element_name}")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Échec",
                f"Impossible d'insérer le parent '{new_parent_name}'"
            )

    def _insert_parent_above(self, level):
        """
        Insère un nouveau parent AU-DESSUS de l'élément sélectionné
        Décale l'élément actuel d'un niveau vers le bas
        """
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(
                self, "Sélection requise",
                "Veuillez sélectionner un élément"
            )
            return

        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display

        # Demander le nom du nouveau parent
        new_parent_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Insérer Parent Au-Dessus",
            f"Nouveau parent pour '{element_name}':\n\n"
            f"'{element_name}' sera décalé d'un niveau vers le bas.\n\n"
            f"Nom du nouveau parent:",
            QtWidgets.QLineEdit.Normal
        )

        if not ok or not new_parent_name.strip():
            return

        new_parent_name = new_parent_name.strip()

        # Obtenir le chemin parent
        path = self._get_path_for_level(level)
        if path is None:
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                "Impossible de déterminer le chemin"
            )
            return

        # Sauvegarder les sélections
        saved_selections = self._save_current_selections()

        # Effectuer l'insertion dans le cache
        if self.hierarchy_cache.shift_level_down(path, element_name, new_parent_name):
            # Recharger l'interface
            self._refresh_ui_after_structure_change(level, saved_selections)

            QtWidgets.QMessageBox.information(
                self, "Succès",
                f"✅ '{element_name}' décalé vers le bas\n\n"
                f"Nouveau parent '{new_parent_name}' créé\n"
                f"Structure: {' → '.join(path)} → {new_parent_name} → {element_name}"
            )

            logger.info(f"✅ Parent inséré: {new_parent_name} > {element_name}")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Échec",
                f"Impossible d'insérer le parent '{new_parent_name}'"
            )

    def _insert_child_below(self, level):
        """
        Insère un nouvel enfant SOUS l'élément sélectionné
        Décale tous les enfants existants d'un niveau vers le bas
        """
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(
                self, "Sélection requise",
                "Veuillez sélectionner un élément"
            )
            return

        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display

        # Construire le chemin jusqu'à l'élément
        path = self._get_path_for_level(level)
        if path is None:
            return

        # Vérifier si l'élément a des enfants
        element_path = path + [element_name] if level != 'child' else self._get_full_path()
        children = self.hierarchy_cache.get_children_at_path(element_path)

        # Message différent selon qu'il y a des enfants ou non
        if children:
            message = (
                f"Nouvel enfant intermédiaire pour '{element_name}':\n\n"
                f"Tous les {len(children)} enfants existants seront décalés d'un niveau vers le bas.\n\n"
                f"Nom du nouvel enfant:"
            )
        else:
            message = (
                f"Nouvel enfant pour '{element_name}':\n\n"
                f"(Aucun enfant existant ne sera décalé)\n\n"
                f"Nom du nouvel enfant:"
            )

        # Demander le nom du nouvel enfant
        new_child_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Insérer Enfant Intermédiaire",
            message,
            QtWidgets.QLineEdit.Normal
        )

        if not ok or not new_child_name.strip():
            return

        new_child_name = new_child_name.strip()

        # Sauvegarder les sélections
        saved_selections = self._save_current_selections()

        # Effectuer l'insertion dans le cache
        if self.hierarchy_cache.shift_level_up(path, element_name, new_child_name):
            # Recharger l'interface
            self._refresh_ui_after_structure_change(level, saved_selections)

            if children:
                QtWidgets.QMessageBox.information(
                    self, "Succès",
                    f"✅ Enfant intermédiaire '{new_child_name}' créé\n\n"
                    f"{len(children)} enfants décalés d'un niveau vers le bas"
                )
            else:
                QtWidgets.QMessageBox.information(
                    self, "Succès",
                    f"✅ Enfant '{new_child_name}' créé sous '{element_name}'"
                )

            logger.info(f"✅ Enfant inséré: {element_name} > {new_child_name} > {len(children)} enfants")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Échec",
                f"Impossible d'insérer l'enfant '{new_child_name}'"
            )

    def _refresh_ui_after_structure_change(self, level, saved_selections):
        """
        Rafraîchit l'interface après un changement structurel (insertion parent/enfant)
        """
        logger.debug(f"=== REFRESH UI AFTER STRUCTURE CHANGE: {level} ===")

        # Bloquer les signaux
        widgets = {
            'typologie': self.typologie_list,
            'taxonomy': self.taxonomy_list if hasattr(self, 'taxonomy_list') else None,
            'root': self.root_list,
            'parent': self.parent_list,
            'child': self.child_list
        }

        for widget in widgets.values():
            if widget:
                widget.blockSignals(True)

        # Recharger toutes les listes depuis le cache avec les compteurs
        self._refresh_all_counts()

        # Restaurer les sélections
        self._restore_selections(saved_selections)

        # Débloquer les signaux
        for widget in widgets.values():
            if widget:
                widget.blockSignals(False)

        # Mettre à jour les boutons
        self._update_button_states()

        logger.debug("✅ UI rafraîchie après changement structurel")

    def _insert_child_between_selected(self, level):
        """
        Insère un nouveau niveau d'enfant entre l'élément sélectionné et ses enfants
        """
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(
                self, "Sélection requise",
                "Veuillez sélectionner un élément"
            )
            return

        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display

        # Construire le chemin jusqu'à l'élément
        path = self._get_path_for_level(level)
        if path is None:
            return

        element_path = path + [element_name]

        # Vérifier si l'élément a des enfants
        children = self.hierarchy_cache.get_children_at_path(element_path)

        if not children:
            QtWidgets.QMessageBox.information(
                self, "Aucun enfant",
                f"'{element_name}' n'a pas encore d'enfants.\n\n"
                f"Utilisez 'Ajouter' pour créer des enfants d'abord."
            )
            return

        # Demander le nom du nouvel enfant intermédiaire
        new_child_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Insérer Enfant Intermédiaire",
            f"Nouvel enfant pour '{element_name}':\n\n"
            f"Structure: {element_name} → NOUVEAU → [{', '.join(children[:3])}{'...' if len(children) > 3 else ''}]\n\n"
            f"Tous les {len(children)} enfants existants seront déplacés sous le nouveau niveau.",
            QtWidgets.QLineEdit.Normal
        )

        if not ok or not new_child_name.strip():
            return

        new_child_name = new_child_name.strip()

        # Sauvegarder les sélections
        saved_selections = self._save_current_selections()

        # Effectuer l'insertion dans le cache
        if self.hierarchy_cache.insert_child_between(element_path, new_child_name, move_existing_children=True):
            # Recharger l'interface
            self._refresh_ui_after_insert(level, saved_selections)

            QtWidgets.QMessageBox.information(
                self, "Succès",
                f"✅ Enfant intermédiaire '{new_child_name}' créé\n\n"
                f"{len(children)} enfants déplacés sous le nouveau niveau"
            )

            logger.info(f"✅ Enfant intermédiaire inséré: {element_name} > {new_child_name} > {len(children)} enfants")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Échec",
                f"Impossible d'insérer l'enfant '{new_child_name}'"
            )

    def _promote_selected(self, level):
        """
        Promouvoir l'élément sélectionné d'un niveau vers le haut
        """
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(
                self, "Sélection requise",
                "Veuillez sélectionner un élément à promouvoir"
            )
            return

        # Extraire le nom sans compteur
        element_display = current.text()
        element_name = element_display.split(" (")[0] if " (" in element_display else element_display

        # Obtenir le chemin parent
        path = self._get_path_for_level(level)
        if path is None or len(path) < 1:
            QtWidgets.QMessageBox.warning(
                self, "Impossible",
                "Cet élément est déjà au niveau le plus haut"
            )
            return

        # Confirmer l'action
        grandparent_level = " → ".join(path[:-1]) if len(path) > 1 else "Racine"
        reply = QtWidgets.QMessageBox.question(
            self, "Confirmer la promotion",
            f"Promouvoir '{element_name}' ?\n\n"
            f"De: {' → '.join(path)} → {element_name}\n"
            f"Vers: {grandparent_level} → {element_name}\n\n"
            f"L'élément deviendra frère de son ancien parent.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Sauvegarder les sélections
        saved_selections = self._save_current_selections()

        # Effectuer la promotion dans le cache
        if self.hierarchy_cache.promote_to_higher_level(path, element_name):
            # Recharger l'interface
            self._refresh_ui_after_insert(level, saved_selections)

            QtWidgets.QMessageBox.information(
                self, "Succès",
                f"✅ '{element_name}' promu avec succès"
            )

            logger.info(f"✅ Promotion: {element_name} de niveau {len(path)} à {len(path)-1}")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Échec",
                f"Impossible de promouvoir '{element_name}'"
            )

    def _refresh_ui_after_insert(self, level, saved_selections):
        """
        Rafraîchit l'interface après une opération d'insertion/promotion
        """
        logger.debug(f"=== REFRESH UI AFTER INSERT: {level} ===")

        # Bloquer les signaux
        widgets = {
            'typologie': self.typologie_list,
            'taxonomy': self.taxonomy_list if hasattr(self, 'taxonomy_list') else None,
            'root': self.root_list,
            'parent': self.parent_list,
            'child': self.child_list
        }

        for widget in widgets.values():
            if widget:
                widget.blockSignals(True)

        # Recharger toutes les listes depuis le cache avec les compteurs
        self._refresh_all_counts()

        # Restaurer les sélections
        self._restore_selections(saved_selections)

        # Débloquer les signaux
        for widget in widgets.values():
            if widget:
                widget.blockSignals(False)

        # Mettre à jour les boutons
        self._update_button_states()

        logger.debug("✅ UI rafraîchie après insertion")

    def _create_modern_group(self, title):
        """Create modern styled group box - responsive"""
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: white;
                color: {Theme.SECONDARY_COLOR};
            }}
        """)
        return group

    def _create_compact_button(self, text, callback):
        """Create compact gradient button - fully responsive"""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 3px;
                padding: 3px 4px;
                font-weight: 600;
                font-size: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-height: 22px;
                min-width: 40px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, 
                    stop:1 {Theme.PRIMARY_COLOR});
                color: white;
            }}
            QPushButton:pressed {{
                background: #1f5f8b;
                color: white;
            }}
            QPushButton:disabled {{
                background: #d0d0d0;
                color: #2c3e50;
            }}
        """)
        btn.clicked.connect(callback)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return btn

    def _get_modern_input_style(self):
        """Modern input field style with correct dropdown icon - responsive"""
        svg_path = self._get_dropdown_svg_path()
        svg_path = svg_path.replace('\\', '/')

        return f"""
            QLineEdit, QComboBox {{
                border: 2px solid #e1e4e8;
                border-radius: 5px;
                padding: 6px 10px;
                background-color: white;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid #2c3e50;
            }}
            QComboBox {{
                min-height: 30px;
                padding-left: 10px;
                padding-right: 30px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 28px;
                border: none;
                border-left: 1px solid #e1e4e8;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background: linear-gradient(to bottom, #fafafa, #f5f5f5);
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 16px;
                height: 16px;
            }}
        """
    
    def _get_dropdown_svg_path(self):
        """Get absolute path to dropdown SVG icon"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        widgets_dir = os.path.dirname(current_dir)
        ui_dir = os.path.dirname(widgets_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        svg_path = os.path.normpath(svg_path)
        return svg_path

    def _get_modern_list_style(self):
        """Modern list widget style - responsive"""
        return """
            QListWidget {
                border: 2px solid #e1e4e8;
                border-radius: 5px;
                background-color: white;
                padding: 4px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 1px 0;
                color: #2c3e50;
            }
            QListWidget::item:selected {
                background-color: #e8e8e8;
                color: #2c3e50;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                color: #2c3e50;
            }
        """

    def _create_action_buttons(self, parent_layout):
        """Create main action buttons - responsive"""
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(8)

        btn_layout.addStretch()

        self.save_btn = QtWidgets.QPushButton(tr("dataset.save"))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 90px;
                min-height: 32px;
            }}
            QPushButton:hover:enabled {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, 
                    stop:1 {Theme.PRIMARY_COLOR});
                color: white;
            }}
            QPushButton:disabled {{
                background: #c0c0c0;
                color: #2c3e50;
            }}
        """)
        self.save_btn.clicked.connect(self._save_project)

        btn_layout.addWidget(self.save_btn)
        parent_layout.addWidget(btn_container)

    # ========== EVENT HANDLERS ==========

    def _on_project_selected(self, index):
        """Charge un projet (priorité SQLite, fallback Dgraph)"""
        if index < 0:
            return

        project_name = self.project_combo.currentText()

        if not project_name or not project_name.strip():
            logger.warning("Nom de projet vide détecté")
            return

        sqlite_loaded = False
        dgraph_loaded = False

        # Tentative de chargement SQLite
        if self.project_manager:
            try:
                logger.info(f"📂 Chargement depuis SQLite: '{project_name}'")
                sqlite_loaded = self.project_manager.load_project(project_name)

                if sqlite_loaded:
                    logger.info(f"✅ Projet chargé depuis SQLite")
            except Exception as e:
                logger.error(f"❌ Erreur chargement SQLite: {e}")

        # Si SQLite échoue, essayer Dgraph
        if not sqlite_loaded and self.dgraph_available and self.dgraph_manager:
            try:
                logger.info(f"📊 Chargement depuis Dgraph: '{project_name}'")
                dgraph_project = self.dgraph_manager.get_project_by_name(project_name)

                if dgraph_project:
                    # Exporter depuis Dgraph
                    dgraph_data = self.dgraph_manager.export_project_to_json(project_name)

                    if dgraph_data and self.project_manager:
                        # Créer dans SQLite si nécessaire
                        if not self.project_manager.create_new_project(project_name, dgraph_data['project'].get('description', '')):
                            # Projet existe déjà, le charger
                            self.project_manager.load_project(project_name)

                        # Importer les données
                        self.project_manager.current_project_data['typologies'] = dgraph_data.get('typologies', [])
                        dgraph_loaded = True
                        logger.info(f"✅ Projet chargé depuis Dgraph")
            except Exception as e:
                logger.error(f"❌ Erreur chargement Dgraph: {e}")

        # Résultat
        if sqlite_loaded or dgraph_loaded:
            # Charger dans le cache et l'UI
            self.hierarchy_cache.clear()
            self._child_navigation_path.clear()

            self._load_project_from_db_to_cache()
            self._load_project_ui()
            self._export_strategy()

            if sqlite_loaded:
                logger.info(f"✅ Projet '{project_name}' chargé depuis SQLite")
            else:
                logger.info(f"✅ Projet '{project_name}' chargé depuis Dgraph")
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger le projet '{project_name}'\n\n"
                f"Non trouvé dans SQLite ni dans Dgraph."
            )
        
    def _on_typologie_selected(self, current, previous):
        """
        Gestion de la sélection de typologie - VERSION CORRIGÉE
        """
        # Sauvegarder l'état précédent dans le cache (déjà fait en temps réel)

        if not current:
            self._clear_hierarchy()
            self._update_button_states()
            return

        # CORRECTION: Extraire le nom SANS le compteur
        typologie_display = current.text()
        if " (" in typologie_display:
            typologie_name = typologie_display.split(" (")[0]
        else:
            typologie_name = typologie_display

        index = self.typologie_list.currentRow()

        # Mettre à jour le project_manager
        self.project_manager.set_current_typologie_index(index)

        # Charger les clusters de taxonomie depuis le cache AVEC LE NOM SANS COMPTEUR
        path = [typologie_name]
        self._load_list_from_cache(self.taxonomy_list, path)

        # Effacer les niveaux inférieurs
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self._child_navigation_path.clear()

        self._update_button_states()
        logger.debug(f"Typologie sélectionnée: '{typologie_name}'")


    def _save_full_hierarchy_to_cache(self, typologie_name):
        """Sauvegarder toute la hiérarchie d'une typologie dans le cache"""
        if not typologie_name:
            return

        # Sauvegarder les clusters de taxonomie
        self._save_taxonomy_to_cache(typologie_name)

        # Sauvegarder tous les root labels de tous les clusters
        if hasattr(self, 'taxonomy_list'):
            for i in range(self.taxonomy_list.count()):
                taxonomy_item = self.taxonomy_list.item(i)
                taxonomy_name = taxonomy_item.text()
                self._save_root_to_cache(typologie_name, taxonomy_name)

        logger.debug(f"Hiérarchie complète sauvegardée pour typologie '{typologie_name}'")

    def _on_taxonomy_selected(self, current, previous):
        """
        Gestion de la sélection de taxonomie - VERSION COMPLÈTEMENT CORRIGÉE
        """
        if not current:
            self.root_list.clear()
            self.parent_list.clear()
            self.child_list.clear()
            self._update_button_states()
            return

        typ_item = self.typologie_list.currentItem()
        if not typ_item:
            logger.warning("Typologie non sélectionnée")
            return

        # CORRECTION CRITIQUE: Extraire les noms SANS les compteurs
        taxonomy_display = current.text()
        taxonomy_name = taxonomy_display.split(" (")[0] if " (" in taxonomy_display else taxonomy_display

        typologie_display = typ_item.text()
        typologie_name = typologie_display.split(" (")[0] if " (" in typologie_display else typologie_display

        logger.debug(f"Sélection taxonomy: '{taxonomy_name}' dans typologie '{typologie_name}'")

        # === SYNCHRONISER LE PROJECT_MANAGER ===
        typologie = self.project_manager.get_current_typologie()
        if not typologie:
            logger.error(f"Typologie '{typologie_name}' non trouvée dans project_manager!")
            return

        taxonomy_clusters = typologie.get('taxonomy_clusters', [])
        taxonomy_index = -1

        for idx, cluster in enumerate(taxonomy_clusters):
            if cluster.get('name') == taxonomy_name:
                taxonomy_index = idx
                break
            
        if taxonomy_index == -1:
            # Le cluster n'existe pas encore dans le manager, le créer
            logger.warning(f"Taxonomy '{taxonomy_name}' pas dans manager, ajout automatique")
            new_cluster = {
                'name': taxonomy_name,
                'description': '',
                'root_labels': []
            }
            taxonomy_clusters.append(new_cluster)
            taxonomy_index = len(taxonomy_clusters) - 1

        # 2. Définir l'index dans le project_manager
        self.project_manager.current_taxonomy_index = taxonomy_index

        logger.info(f"✓ Taxonomy index synchronisé: {taxonomy_index} pour '{taxonomy_name}'")

        # === SYNCHRONISER DGRAPH (NOUVEAU) ===
        if self.dgraph_available and self.dgraph_manager:
            try:
                # Obtenir l'UID de la typologie dans Dgraph
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    self.project_manager.current_project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    # Vérifier si le cluster existe dans Dgraph
                    cluster_exists = self.dgraph_manager.get_cluster_by_name(
                        typologie_dgraph['uid'],
                        taxonomy_name
                    )

                    if not cluster_exists:
                        # Créer le cluster dans Dgraph
                        cluster_uid = self.dgraph_manager.add_cluster(
                            typologie_dgraph['uid'],
                            taxonomy_name,
                            '',
                            taxonomy_index
                        )
                        logger.info(f"✅ Cluster '{taxonomy_name}' créé dans Dgraph (UID: {cluster_uid})")
            except Exception as e:
                logger.warning(f"⚠️ Erreur sync Dgraph pour taxonomy: {e}")

        # Charger les roots depuis le cache AVEC LES NOMS SANS COMPTEURS
        path = [typologie_name, taxonomy_name]
        self._load_list_from_cache(self.root_list, path)

        # Effacer les niveaux inférieurs
        self.parent_list.clear()
        self.child_list.clear()
        self._child_navigation_path.clear()

        self._update_button_states()
        logger.debug(f"Taxonomie '{taxonomy_name}' sélectionnée et synchronisée")

    def _on_root_selected(self, current, previous):
        """
        Gestion de la sélection de root - VERSION CORRIGÉE
        """
        if not current:
            self.parent_list.clear()
            self.child_list.clear()
            self._update_button_states()
            return

        # CORRECTION: Extraire le nom SANS le compteur
        root_display = current.text()
        if " (" in root_display:
            root_name = root_display.split(" (")[0]
        else:
            root_name = root_display

        index = self.root_list.currentRow()

        # Mettre à jour le project_manager
        self.project_manager.set_current_root_index(index)

        # Construire le chemin AVEC LES NOMS SANS COMPTEURS
        typ_item = self.typologie_list.currentItem()
        tax_item = self.taxonomy_list.currentItem()

        if typ_item and tax_item:
            # Extraire les noms sans compteurs
            typ_display = typ_item.text()
            typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

            tax_display = tax_item.text()
            tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

            path = [typ_name, tax_name, root_name]
            self._load_list_from_cache(self.parent_list, path)

        # Effacer les enfants
        self.child_list.clear()
        self._child_navigation_path.clear()

        self._update_button_states()
        logger.debug(f"Root sélectionné: '{root_name}'")

    def _on_parent_selected(self, current, previous):
        """
        Gestion de la sélection de parent - VERSION CORRIGÉE avec extraction du nom réel
        """
        if not current:
            self.child_list.clear()
            self._update_button_states()
            return

        parent_display = current.text()
        # CORRECTION: Extraire le nom réel sans le compteur
        if " (" in parent_display:
            parent_name = parent_display.split(" (")[0]
        else:
            parent_name = parent_display

        index = self.parent_list.currentRow()

        # Mettre à jour le project_manager avec le NOM RÉEL
        self.project_manager.set_current_parent_index(index)

        # Réinitialiser la navigation enfants
        self._child_navigation_path.clear()

        # Charger les enfants directs depuis le cache
        self._load_children_from_cache()

        # Mettre à jour le breadcrumb
        self._update_breadcrumb()

        self._update_button_states()
        logger.debug(f"Parent sélectionné: '{parent_name}' (affiché: '{parent_display}')")

    def _on_child_selected(self, current, previous):
        """Handle child selection - VERSION CORRIGÉE"""
        # Mettre à jour les boutons quand la sélection change
        self._update_button_states()
    
        # Activer le bouton "Plonger" si un enfant est sélectionné
        has_selection = current is not None
        self.dive_btn.setEnabled(has_selection)
        
        if has_selection:
            child_display = current.text()
            # Extraire le nom sans compteur
            if " (" in child_display:
                child_name = child_display.split(" (")[0]
            else:
                child_name = child_display
            logger.debug(f"Enfant sélectionné: '{child_name}'")
    
    def _navigate_into_child(self):
        """Navigation dans un enfant - VERSION CORRIGÉE avec extraction du nom"""
        current_item = self.child_list.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(self, "Sélection requise",
                "Veuillez sélectionner un enfant pour naviguer dedans")
            return

        child_display = current_item.text()

        # CORRECTION: Extraire le nom réel sans le compteur
        if " (" in child_display:
            child_name = child_display.split(" (")[0]
        else:
            child_name = child_display

        current_path = self._get_full_path()
        self._sync_list_to_cache(self.child_list, current_path)

        self._child_navigation_path.append(child_name)

        self.project_manager.navigate_into_child(child_name)

        self._load_children_from_cache()

        # Mettre à jour l'affichage
        self._update_breadcrumb()
        self._update_button_states()

        depth = len(self._child_navigation_path)
        logger.debug(f"Navigation dans '{child_name}': niveau {depth}")


    def _navigate_up(self):
        """
        Remonte d'un niveau - VERSION CORRIGÉE
        Synchronise avec le project_manager
        """
        if not self._child_navigation_path:
            logger.warning("Impossible de remonter: chemin vide")
            return

        # Sauvegarder l'état actuel
        current_path = self._get_full_path()
        self._sync_list_to_cache(self.child_list, current_path)

        # Remonter d'un niveau
        removed_child = self._child_navigation_path.pop()

        # Synchroniser avec le project_manager
        self.project_manager.navigate_up()

        # Recharger les enfants du niveau parent
        self._load_children_from_cache()

        # Mettre à jour l'affichage
        self._update_breadcrumb()
        self._update_button_states()

        depth = len(self._child_navigation_path)
        logger.debug(f"Remonté depuis '{removed_child}': niveau {depth}")

    def _update_breadcrumb(self):
        """Mettre à jour le fil d'Ariane - VERSION CORRIGÉE"""
        depth = len(self._child_navigation_path)

        if depth == 0:
            # Afficher le parent SANS le compteur
            parent_item = self.parent_list.currentItem()
            if parent_item:
                parent_display = parent_item.text()
                # Extraire le nom sans compteur
                if " (" in parent_display:
                    parent_name = parent_display.split(" (")[0]
                else:
                    parent_name = parent_display
                display = f"{parent_name}"
            else:
                display = "Racine"
        else:
            # Afficher le chemin dans les enfants (déjà sans compteurs)
            if depth <= 2:
                display = " → ".join(self._child_navigation_path)
            else:
                display = "... → " + " → ".join(self._child_navigation_path[-2:])

            display = f"{display} (Niveau {depth})"

        self.breadcrumb_label.setText(display)

        # Activer/désactiver les boutons de navigation
        self.up_btn.setEnabled(depth > 0)

        # Le bouton "Plonger" est activé s'il y a un enfant sélectionné
        child_selected = self.child_list.currentItem() is not None
        self.dive_btn.setEnabled(child_selected)

    # ========== CRUD ACTIONS ==========

    def _add_project(self):
        """Créer un nouveau projet dans les deux systèmes"""
        name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.new_project"), 
            tr("dataset.project_name") + ":"
        )
        if not ok or not name.strip():
            return

        description, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, tr("dataset.description"), 
            tr("dataset.description") + " (optional):"
        )
        if not ok:
            description = ""

        name = name.strip()
        description = description.strip()

        sqlite_success = False
        dgraph_success = False

        # Tentative SQLite
        if self.project_manager:
            try:
                sqlite_success = self.project_manager.create_new_project(name, description)
                if sqlite_success:
                    logger.info(f"✅ Projet '{name}' créé dans SQLite")
            except Exception as e:
                logger.error(f"❌ Erreur création SQLite: {e}")

        # Tentative Dgraph
        if self.dgraph_available and self.dgraph_manager:
            try:
                dgraph_uid = self.dgraph_manager.create_project(name, description)
                dgraph_success = dgraph_uid is not None
                if dgraph_success:
                    logger.info(f"✅ Projet '{name}' créé dans Dgraph (UID: {dgraph_uid})")
            except Exception as e:
                logger.error(f"❌ Erreur création Dgraph: {e}")

        # Résultat
        if sqlite_success or dgraph_success:
            self._refresh_project_combos()
            self.project_combo.setCurrentText(name)
            self._load_project_ui()

            if sqlite_success and dgraph_success:
                logger.info(f"✅✅ Projet '{name}' créé dans les deux systèmes")
            elif sqlite_success:
                logger.warning(f"⚠️ Projet '{name}' créé dans SQLite uniquement")
            elif dgraph_success:
                logger.warning(f"⚠️ Projet '{name}' créé dans Dgraph uniquement")
        else:
            QtWidgets.QMessageBox.critical(
                self, "Erreur",
                f"Impossible de créer le projet '{name}' dans aucun système"
            )

    def _delete_project(self):
        """Supprimer un projet des deux systèmes"""
        project_name = self.project_manager.current_project_name if self.project_manager else None

        if not project_name:
            return

        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"), 
            f"{tr('dataset.delete_project_confirm')}: '{project_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        sqlite_success = False
        dgraph_success = False

        # Suppression SQLite
        if self.project_manager:
            try:
                sqlite_success = self.project_manager.delete_project(project_name)
                if sqlite_success:
                    logger.info(f"✅ Projet '{project_name}' supprimé de SQLite")
            except Exception as e:
                logger.error(f"❌ Erreur suppression SQLite: {e}")

        # Suppression Dgraph
        if self.dgraph_available and self.dgraph_manager:
            try:
                dgraph_project = self.dgraph_manager.get_project_by_name(project_name)
                if dgraph_project:
                    dgraph_success = self.dgraph_manager.delete_project(dgraph_project['uid'])
                    if dgraph_success:
                        logger.info(f"✅ Projet '{project_name}' supprimé de Dgraph")
            except Exception as e:
                logger.error(f"❌ Erreur suppression Dgraph: {e}")

        # Résultat
        if sqlite_success or dgraph_success:
            self._clear_ui()
            self._refresh_project_combos()

            if sqlite_success and dgraph_success:
                logger.info(f"✅✅ Projet '{project_name}' supprimé des deux systèmes")
            elif sqlite_success:
                logger.warning(f"⚠️ Projet '{project_name}' supprimé de SQLite uniquement")
            elif dgraph_success:
                logger.warning(f"⚠️ Projet '{project_name}' supprimé de Dgraph uniquement")

    def _save_project(self):
        """Sauvegarde le projet dans les deux systèmes"""
        logger.info("=" * 100)
        logger.info("🚀 DÉBUT DU PROCESSUS DE SAUVEGARDE DUAL")
        logger.info("=" * 100)

        # Validation initiale
        if self.project_manager and not self.project_manager.current_project_name:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Projet sans nom valide")
            return

        new_name = self.project_name_edit.text().strip()
        if not new_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Nom manquant")
            return

        sqlite_success = False
        dgraph_success = False

        # === SAUVEGARDE SQLITE ===
        if self.project_manager:
            try:
                logger.info("\n📦 SAUVEGARDE SQLITE")
                logger.info("-" * 80)

                if not self.project_manager.current_project_data:
                    raise Exception("Données non initialisées")

                # Synchronisation cache → manager
                if not self._sync_cache_to_project_manager():
                    raise Exception("Échec sync cache")

                # Mise à jour du nom
                old_name = self.project_manager.current_project_name
                self.project_manager.current_project_data['nom'] = new_name
                self.project_manager.current_project_name = new_name

                # Sauvegarde
                sqlite_success = self.project_manager.save_project()

                if sqlite_success:
                    logger.info(f"✅ SQLite: Projet '{new_name}' sauvegardé")
                else:
                    logger.error("❌ SQLite: Échec de sauvegarde")

            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde SQLite: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # === SAUVEGARDE DGRAPH ===
        if self.dgraph_available and self.dgraph_manager:
            try:
                logger.info("\n📊 SAUVEGARDE DGRAPH")
                logger.info("-" * 80)

                # Vérifier si le projet existe
                existing = self.dgraph_manager.get_project_by_name(new_name)

                if existing:
                    # Mettre à jour le projet existant
                    logger.info(f"Projet '{new_name}' existe, écrasement...")
                    self.dgraph_manager.delete_project(existing['uid'])

                # Créer le projet
                project_uid = self.dgraph_manager.create_project(
                    new_name,
                    self.project_manager.current_project_data.get('description', '') if self.project_manager else ''
                )

                if not project_uid:
                    raise Exception("Échec création projet Dgraph")

                # Synchroniser les données
                if self.project_manager:
                    self._sync_sqlite_data_to_dgraph(project_uid)

                dgraph_success = True
                logger.info(f"✅ Dgraph: Projet '{new_name}' sauvegardé (UID: {project_uid})")

            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde Dgraph: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # === RÉSULTAT FINAL ===
        logger.info("\n" + "=" * 100)

        if sqlite_success and dgraph_success:
            logger.info(f"✅✅ SUCCÈS COMPLET: '{new_name}' sauvegardé dans SQLite ET Dgraph")
            QtWidgets.QMessageBox.information(
                self, "Succès",
                f"✅ Projet '{new_name}' sauvegardé dans les deux systèmes !"
            )
        elif sqlite_success:
            logger.warning(f"⚠️ SUCCÈS PARTIEL: '{new_name}' sauvegardé dans SQLite uniquement")
            QtWidgets.QMessageBox.warning(
                self, "Succès Partiel",
                f"⚠️ Projet '{new_name}' sauvegardé dans SQLite uniquement.\n\n"
                f"Dgraph non disponible ou erreur."
            )
        elif dgraph_success:
            logger.warning(f"⚠️ SUCCÈS PARTIEL: '{new_name}' sauvegardé dans Dgraph uniquement")
            QtWidgets.QMessageBox.warning(
                self, "Succès Partiel",
                f"⚠️ Projet '{new_name}' sauvegardé dans Dgraph uniquement.\n\n"
                f"SQLite non disponible ou erreur."
            )
        else:
            logger.error(f"❌ ÉCHEC TOTAL: '{new_name}' non sauvegardé")
            QtWidgets.QMessageBox.critical(
                self, "Échec",
                f"❌ Impossible de sauvegarder le projet '{new_name}'.\n\n"
                f"Aucun système de stockage n'a réussi."
            )
            return

        logger.info("=" * 100)

        # Post-traitement (uniquement si au moins un succès)
        self.hierarchy_cache.mark_clean()
        self._refresh_project_combos()
        index = self.project_combo.findText(new_name)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
        self.project_saved.emit()

    def _sync_sqlite_data_to_dgraph(self, project_uid: str):
        """Synchronise les données SQLite vers Dgraph"""
        if not self.project_manager or not self.project_manager.current_project_data:
            return

        project_data = self.project_manager.current_project_data
        typologies = project_data.get('typologies', [])

        logger.info(f"  📊 Synchronisation de {len(typologies)} typologie(s)")

        for typ_idx, typologie in enumerate(typologies):
            typ_name = typologie.get('name', '')

            typ_uid = self.dgraph_manager.add_typologie(
                typ_name,
                typologie.get('description', ''),
                typologie.get('position', typ_idx)
            )

            if not typ_uid:
                continue
            
            # Clusters
            clusters = typologie.get('taxonomy_clusters', [])
            for cluster_idx, cluster in enumerate(clusters):
                cluster_name = cluster.get('name', '')

                cluster_uid = self.dgraph_manager.add_cluster(
                    typ_uid,
                    cluster_name,
                    cluster.get('description', ''),
                    cluster.get('position', cluster_idx)
                )

                if not cluster_uid:
                    continue
                
                # Root labels
                roots = cluster.get('root_labels', [])
                for root_idx, root in enumerate(roots):
                    root_name = root.get('name', '')

                    root_uid = self.dgraph_manager.add_root_label(
                        cluster_uid,
                        root_name,
                        root.get('description', ''),
                        root.get('category', 'default'),
                        root.get('position', root_idx)
                    )

                    if not root_uid:
                        continue
                    
                    # Parent labels
                    parents = root.get('parent_labels', [])
                    for parent_idx, parent in enumerate(parents):
                        parent_name = parent.get('name', '')

                        parent_uid = self.dgraph_manager.add_label_node(
                            root_uid,
                            parent_name,
                            parent.get('description', ''),
                            parent.get('category', 'default'),
                            depth=0,
                            position=parent.get('position', parent_idx)
                        )

                        if not parent_uid:
                            continue
                        
                        # Enfants récursifs
                        children = parent.get('children', [])
                        if children:
                            self._sync_children_recursive_to_dgraph(
                                parent_uid, 
                                children, 
                                depth=1
                            )

    def _sync_children_recursive_to_dgraph(self, parent_uid: str, children: list, depth: int):
        """Synchronise récursivement les enfants vers Dgraph"""
        for child_idx, child in enumerate(children):
            child_name = child.get('name', '')

            child_uid = self.dgraph_manager.add_label_node(
                parent_uid,
                child_name,
                child.get('description', ''),
                child.get('category', 'default'),
                depth=depth,
                position=child.get('position', child_idx)
            )

            if child_uid:
                sub_children = child.get('children', [])
                if sub_children:
                    self._sync_children_recursive_to_dgraph(child_uid, sub_children, depth + 1)
            
    def _verify_database_content(self, project_name):
        """
        Vérifie le contenu réel de la base de données SQLite
        À appeler après une sauvegarde pour confirmer l'insertion
        """
        logger.info("\n" + "=" * 100)
        logger.info("🔍 VÉRIFICATION DIRECTE DU CONTENU DE LA BASE DE DONNÉES SQLite")
        logger.info("=" * 100)

        try:
            # Accès direct à la connexion SQLite
            db = self.project_manager.database
            if not db.connection:
                logger.error("❌ Pas de connexion à la base de données")
                return

            cursor = db.connection.cursor()

            # 1. Vérifier le projet
            logger.info(f"\n📋 1. VÉRIFICATION DU PROJET '{project_name}'")
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            project = cursor.fetchone()

            if project:
                logger.info(f"  ✅ Projet trouvé dans la base")
                logger.info(f"     - ID: {project['id']}")
                logger.info(f"     - Nom: {project['name']}")
                logger.info(f"     - Description: {project['description']}")
                logger.info(f"     - Créé le: {project['created_at']}")
                logger.info(f"     - Modifié le: {project['updated_at']}")
                project_id = project['id']
            else:
                logger.error(f"  ❌ Projet '{project_name}' NON TROUVÉ dans la base!")
                return

            # 2. Vérifier les typologies
            logger.info(f"\n📁 2. VÉRIFICATION DES TYPOLOGIES")
            cursor.execute("""
                SELECT * FROM typologies 
                WHERE project_id = ? 
                ORDER BY position
            """, (project_id,))
            typologies = cursor.fetchall()

            if typologies:
                logger.info(f"  ✅ {len(typologies)} typologie(s) trouvée(s)")
                for idx, typ in enumerate(typologies):
                    logger.info(f"\n     [{idx+1}] Typologie:")
                    logger.info(f"         - ID: {typ['id']}")
                    logger.info(f"         - Nom: {typ['name']}")
                    logger.info(f"         - Description: {typ['description']}")
                    logger.info(f"         - Position: {typ['position']}")

                    # 3. Vérifier les clusters de taxonomie
                    logger.info(f"\n     📊 Clusters de taxonomie pour '{typ['name']}':")
                    cursor.execute("""
                        SELECT * FROM taxonomy_clusters 
                        WHERE typologie_id = ? 
                        ORDER BY position
                    """, (typ['id'],))
                    clusters = cursor.fetchall()

                    if clusters:
                        logger.info(f"        ✅ {len(clusters)} cluster(s) trouvé(s)")
                        for c_idx, cluster in enumerate(clusters):
                            logger.info(f"\n        [{c_idx+1}] Cluster:")
                            logger.info(f"            - ID: {cluster['id']}")
                            logger.info(f"            - Nom: {cluster['name']}")
                            logger.info(f"            - Description: {cluster['description']}")
                            logger.info(f"            - Position: {cluster['position']}")

                            # 4. Vérifier les root labels
                            logger.info(f"\n        🏷️  Root labels pour '{cluster['name']}':")
                            cursor.execute("""
                                SELECT * FROM root_labels 
                                WHERE taxonomy_id = ? 
                                ORDER BY position
                            """, (cluster['id'],))
                            roots = cursor.fetchall()

                            if roots:
                                logger.info(f"           ✅ {len(roots)} root(s) trouvé(s)")
                                for r_idx, root in enumerate(roots):
                                    logger.info(f"\n           [{r_idx+1}] Root:")
                                    logger.info(f"               - ID: {root['id']}")
                                    logger.info(f"               - Nom: {root['name']}")
                                    logger.info(f"               - Catégorie: {root['category']}")
                                    logger.info(f"               - Position: {root['position']}")

                                    # 5. Vérifier les parent labels
                                    logger.info(f"\n           👨 Parent labels pour '{root['name']}':")
                                    cursor.execute("""
                                        SELECT * FROM parent_labels 
                                        WHERE root_id = ? 
                                        ORDER BY position
                                    """, (root['id'],))
                                    parents = cursor.fetchall()

                                    if parents:
                                        logger.info(f"              ✅ {len(parents)} parent(s) trouvé(s)")
                                        for p_idx, parent in enumerate(parents):
                                            logger.info(f"\n              [{p_idx+1}] Parent:")
                                            logger.info(f"                  - ID: {parent['id']}")
                                            logger.info(f"                  - Nom: {parent['name']}")
                                            logger.info(f"                  - Catégorie: {parent['category']}")
                                            logger.info(f"                  - Position: {parent['position']}")

                                            # 6. Vérifier les child labels
                                            logger.info(f"\n              👶 Child labels pour '{parent['name']}':")
                                            cursor.execute("""
                                                SELECT * FROM child_labels 
                                                WHERE parent_label_id = ? AND parent_child_id IS NULL
                                                ORDER BY position
                                            """, (parent['id'],))
                                            children = cursor.fetchall()

                                            if children:
                                                logger.info(f"                 ✅ {len(children)} enfant(s) direct(s) trouvé(s)")
                                                for ch_idx, child in enumerate(children):
                                                    logger.info(f"\n                 [{ch_idx+1}] Child:")
                                                    logger.info(f"                     - ID: {child['id']}")
                                                    logger.info(f"                     - Nom: {child['name']}")
                                                    logger.info(f"                     - Catégorie: {child['category']}")
                                                    logger.info(f"                     - Profondeur: {child['depth']}")
                                                    logger.info(f"                     - Position: {child['position']}")

                                                    # Vérifier les sous-enfants récursivement
                                                    self._verify_children_recursive(cursor, child['id'], 1)
                                            else:
                                                logger.info(f"                 ⚠️  Aucun enfant trouvé")
                                    else:
                                        logger.info(f"              ⚠️  Aucun parent trouvé")
                            else:
                                logger.info(f"           ⚠️  Aucun root trouvé")
                    else:
                        logger.info(f"        ⚠️  Aucun cluster trouvé")
            else:
                logger.info(f"  ⚠️  Aucune typologie trouvée")

            # 7. RÉSUMÉ FINAL
            logger.info("\n" + "=" * 100)
            logger.info("📊 RÉSUMÉ DE LA VÉRIFICATION")
            logger.info("=" * 100)

            # Compter tous les éléments
            cursor.execute("SELECT COUNT(*) as count FROM typologies WHERE project_id = ?", (project_id,))
            typ_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM taxonomy_clusters 
                WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
            """, (project_id,))
            cluster_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM root_labels 
                WHERE taxonomy_id IN (
                    SELECT id FROM taxonomy_clusters 
                    WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                )
            """, (project_id,))
            root_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM parent_labels 
                WHERE root_id IN (
                    SELECT id FROM root_labels 
                    WHERE taxonomy_id IN (
                        SELECT id FROM taxonomy_clusters 
                        WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                    )
                )
            """, (project_id,))
            parent_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) as count FROM child_labels 
                WHERE parent_label_id IN (
                    SELECT id FROM parent_labels 
                    WHERE root_id IN (
                        SELECT id FROM root_labels 
                        WHERE taxonomy_id IN (
                            SELECT id FROM taxonomy_clusters 
                            WHERE typologie_id IN (SELECT id FROM typologies WHERE project_id = ?)
                        )
                    )
                )
            """, (project_id,))
            child_count = cursor.fetchone()['count']

            logger.info(f"  ✅ Projet: '{project_name}' (ID: {project_id})")
            logger.info(f"  ✅ {typ_count} typologie(s)")
            logger.info(f"  ✅ {cluster_count} cluster(s) de taxonomie")
            logger.info(f"  ✅ {root_count} root label(s)")
            logger.info(f"  ✅ {parent_count} parent label(s)")
            logger.info(f"  ✅ {child_count} child label(s)")
            logger.info(f"\n  🎯 TOTAL: {typ_count + cluster_count + root_count + parent_count + child_count} enregistrements")

            logger.info("\n" + "=" * 100)
            logger.info("✅ VÉRIFICATION TERMINÉE - TOUTES LES DONNÉES SONT BIEN EN BASE")
            logger.info("=" * 100 + "\n")

        except Exception as e:
            logger.error(f"\n❌ ERREUR lors de la vérification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _verify_children_recursive(self, cursor, parent_child_id, depth):
        """Vérifie récursivement les enfants imbriqués"""
        indent = "                     " + ("  " * depth)

        cursor.execute("""
            SELECT * FROM child_labels 
            WHERE parent_child_id = ? 
            ORDER BY position
        """, (parent_child_id,))
        sub_children = cursor.fetchall()

        if sub_children:
            logger.info(f"{indent}👶 {len(sub_children)} sous-enfant(s) (profondeur {depth})")
            for idx, child in enumerate(sub_children):
                logger.info(f"\n{indent}[{idx+1}] Sous-enfant:")
                logger.info(f"{indent}    - ID: {child['id']}")
                logger.info(f"{indent}    - Nom: {child['name']}")
                logger.info(f"{indent}    - Profondeur: {child['depth']}")
                logger.info(f"{indent}    - Position: {child['position']}")

                # Vérifier les enfants de cet enfant
                self._verify_children_recursive(cursor, child['id'], depth + 1)

    def _add_typologie(self):
        """Ajoute une typologie avec synchronisation complète"""
        name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.new_typologie"), 
            tr("dataset.name") + ":"
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        # Ajouter au cache hiérarchique
        if not self.hierarchy_cache.add_typologie(name):
            QtWidgets.QMessageBox.warning(
                self, "Erreur", 
                f"La typologie '{name}' existe déjà"
            )
            return

        # Ajouter au project_manager (SQLite)
        sqlite_success = self.project_manager.add_typologie(name, self)

        # === SYNC DGRAPH ===
        dgraph_success = False
        typologie_uid = None

        if sqlite_success and self.dgraph_available and self.dgraph_manager:
            try:
                project_name = self.project_manager.current_project_name

                # Vérifier si le projet existe dans Dgraph
                dgraph_project = self.dgraph_manager.get_project_by_name(project_name)

                if dgraph_project:
                    # Créer la typologie dans Dgraph
                    typologie_uid = self.dgraph_manager.add_typologie(
                        name,
                        '',  # description
                        len(self.hierarchy_cache.get_typologies()) - 1  # position
                    )

                    if typologie_uid:
                        dgraph_success = True

                        # ✅ SYNC UID vers SQLite
                        # Récupérer l'ID SQLite de la typologie
                        typologie = self.project_manager.get_current_typologie()
                        if typologie:
                            # Note: Vous devez ajouter un champ 'id' dans votre structure
                            # ou récupérer l'ID depuis la base
                            # Pour l'instant, on skip cette partie
                            logger.info(f"✅ Typologie '{name}' créée dans Dgraph (UID: {typologie_uid})")

            except Exception as e:
                logger.error(f"❌ Erreur sync Dgraph typologie: {e}")

        # Résultat
        if sqlite_success:
            self._refresh_typologie_list()
            self._refresh_all_counts()

            if dgraph_success:
                logger.info(f"✅✅ Typologie '{name}' créée (SQLite + Dgraph)")
            else:
                logger.warning(f"⚠️ Typologie '{name}' créée (SQLite uniquement)")
        else:
            # Rollback cache
            self.hierarchy_cache.remove_typologie(name)
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                f"Impossible d'ajouter la typologie '{name}'"
            )

    def _edit_typologie(self):
        """Edit selected typologie"""
        current = self.typologie_list.currentItem()
        if not current:
            return
        old_name = current.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.edit_typologie"), 
            tr("dataset.new_name") + ":", 
            text=old_name
        )
        if ok and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()

            # Renommer dans le cache
            if self.hierarchy_cache.rename_typologie(old_name, new_name):
                # Aussi dans le manager
                if self.project_manager.edit_typologie(old_name, new_name, self):
                    self._refresh_typologie_list()
                    logger.info(f"Typologie '{old_name}' renamed to '{new_name}'")

    def _remove_typologie(self):
        """Supprime une typologie avec synchronisation complète"""
        current = self.typologie_list.currentItem()
        if not current:
            return

        name = current.text()

        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"), 
            f"{tr('dataset.delete_typologie_confirm')}: '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Supprimer du cache
        self.hierarchy_cache.remove_typologie(name)

        # Supprimer du project_manager (SQLite)
        sqlite_success = self.project_manager.remove_typologie(name)

        # === SYNC DGRAPH ===
        dgraph_success = False

        if self.dgraph_available and self.dgraph_manager:
            try:
                project_name = self.project_manager.current_project_name

                # Récupérer l'UID de la typologie
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    name
                )

                if typologie_dgraph:
                    dgraph_success = self.dgraph_manager.delete_typologie(
                        typologie_dgraph['uid']
                    )

                    if dgraph_success:
                        logger.info(f"✅ Typologie '{name}' supprimée de Dgraph")

            except Exception as e:
                logger.error(f"❌ Erreur suppression Dgraph typologie: {e}")

        # Résultat
        if sqlite_success:
            self._refresh_typologie_list()
            self._clear_hierarchy()

            if dgraph_success:
                logger.info(f"✅✅ Typologie '{name}' supprimée (SQLite + Dgraph)")
            else:
                logger.warning(f"⚠️ Typologie '{name}' supprimée (SQLite uniquement)")

    def _add_label(self, level):
        """
        Ajoute un label avec synchronisation complète SQLite ↔ Dgraph
        """
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Nouveau {level}", "Nom :"
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        # Sauvegarder les sélections actuelles
        saved_selections = self._save_current_selections()
        logger.debug(f"Sélections sauvegardées: {saved_selections}")

        # Validation du contexte selon le niveau
        if level == "root":
            taxonomy = self.project_manager.get_current_taxonomy()
            if not taxonomy:
                logger.error("ÉCHEC: get_current_taxonomy() retourne None")
                QtWidgets.QMessageBox.critical(
                    self, 
                    "Erreur de synchronisation",
                    "Le cluster de taxonomie n'est pas correctement sélectionné."
                )
                return
            logger.debug(f"✓ Taxonomy validé: '{taxonomy.get('name')}'")

        elif level == "parent":
            root = self.project_manager.get_current_root()
            if not root:
                logger.error("ÉCHEC: get_current_root() retourne None")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur de synchronisation",
                    "Le root label n'est pas correctement sélectionné."
                )
                return
            logger.debug(f"✓ Root validé: '{root.get('name')}'")

        # Obtenir le chemin parent
        path = self._get_path_for_level(level)
        if path is None:
            QtWidgets.QMessageBox.warning(self, "Erreur", 
                "Veuillez d'abord sélectionner le niveau parent")
            return

        logger.debug(f"Chemin pour {level}: {' > '.join(path)}")

        # Vérifier les doublons
        existing = self.hierarchy_cache.get_children_at_path(path)
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Doublon", 
                f"'{name}' existe déjà à ce niveau")
            return

        # Ajouter au cache
        if not self.hierarchy_cache.add_child_at_path(path, name):
            QtWidgets.QMessageBox.warning(self, "Erreur",
                f"Impossible d'ajouter '{name}' au cache")
            return

        logger.info(f"✓ '{name}' ajouté au cache")

        # === AJOUT AU PROJECT_MANAGER (SQLite) ===
        sqlite_success = False
        sqlite_id = None

        if level == "taxonomy":
            sqlite_success = True
        elif level == "root":
            logger.debug(f"Appel add_root_label('{name}')")
            sqlite_success = self.project_manager.add_root_label(name, self)

            if sqlite_success:
                # Récupérer l'ID SQLite créé
                root = self.project_manager.get_current_root()
                if root and 'id' in root:
                    sqlite_id = root['id']

        elif level == "parent":
            logger.debug(f"Appel add_parent_label('{name}')")
            sqlite_success = self.project_manager.add_parent_label(name, self)

            if sqlite_success:
                parent = self.project_manager.get_current_parent()
                if parent and 'id' in parent:
                    sqlite_id = parent['id']

        if not sqlite_success:
            # Rollback cache
            self.hierarchy_cache.remove_child_at_path(path, name)
            logger.error(f"✗✗✗ Rollback: '{name}' retiré du cache")
            QtWidgets.QMessageBox.warning(self, "Erreur",
                f"Impossible d'ajouter le {level} dans SQLite.")
            return

        logger.info(f"✓ '{name}' ajouté au project_manager (SQLite)")

        # === SYNC DGRAPH ===
        dgraph_success = False
        dgraph_uid = None

        if self.dgraph_available and self.dgraph_manager:
            try:
                dgraph_uid, dgraph_success = self._sync_label_to_dgraph_complete(
                    level, name, path
                )

                # ✅ SYNC UID vers SQLite (si les deux ont réussi)
                if dgraph_success and dgraph_uid and sqlite_id:
                    self.dgraph_manager.sync_uid_to_sqlite(
                        level, sqlite_id, dgraph_uid
                    )
                    logger.info(f"✅ UID mappé: {level}#{sqlite_id} ↔ {dgraph_uid}")

            except Exception as e:
                logger.error(f"❌ Erreur sync Dgraph pour '{name}': {e}")

        # Recharger l'interface de manière fluide
        self._refresh_ui_after_add(level, saved_selections)

        # Message selon résultat
        if dgraph_success:
            logger.info(f"✓✓✓ {level.capitalize()} '{name}' ajouté (SQLite + Dgraph + Mapping)")
        else:
            logger.warning(f"⚠️ {level.capitalize()} '{name}' ajouté (SQLite uniquement)")

    def _sync_label_to_dgraph_complete(self, level: str, name: str, path: list) -> tuple:
        if not self.dgraph_available or not self.dgraph_manager:
            return (None, False)

        try:
            project_name = self.project_manager.current_project_name

            if level == "taxonomy":
                # Obtenir l'UID de la typologie
                typologie_name = path[0]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    position = len(self.hierarchy_cache.get_children_at_path([typologie_name]))
                    cluster_uid = self.dgraph_manager.add_cluster(
                        typologie_dgraph['uid'],
                        name,
                        '',
                        position
                    )
                    return (cluster_uid, cluster_uid is not None)

            elif level == "root":
                # Obtenir l'UID du cluster
                typologie_name, cluster_name = path[:2]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                        typologie_dgraph['uid'],
                        cluster_name
                    )

                    if cluster_dgraph:
                        position = len(self.hierarchy_cache.get_children_at_path(path))
                        root_uid = self.dgraph_manager.add_root_label(
                            cluster_dgraph['uid'],
                            name,
                            '',
                            'default',
                            position
                        )
                        return (root_uid, root_uid is not None)

            elif level == "parent":
                # Obtenir l'UID du root
                typologie_name, cluster_name, root_name = path[:3]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                        typologie_dgraph['uid'],
                        cluster_name
                    )

                    if cluster_dgraph:
                        root_dgraph = self.dgraph_manager.get_root_label_by_name(
                            cluster_dgraph['uid'],
                            root_name
                        )

                        if root_dgraph:
                            position = len(self.hierarchy_cache.get_children_at_path(path))
                            parent_uid = self.dgraph_manager.add_label_node(
                                root_dgraph['uid'],
                                name,
                                '',
                                'default',
                                depth=0,
                                position=position
                            )
                            return (parent_uid, parent_uid is not None)

            return (None, False)

        except Exception as e:
            logger.error(f"Erreur _sync_label_to_dgraph_complete: {e}")
            return (None, False)

    def _sync_label_to_dgraph(self, level: str, name: str, path: list) -> bool:
        if not self.dgraph_available or not self.dgraph_manager:
            return False

        try:
            project_name = self.project_manager.current_project_name

            if level == "taxonomy":
                # Obtenir l'UID de la typologie
                typologie_name = path[0]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    position = len(self.hierarchy_cache.get_children_at_path([typologie_name]))
                    cluster_uid = self.dgraph_manager.add_cluster(
                        typologie_dgraph['uid'],
                        name,
                        '',
                        position
                    )
                    return cluster_uid is not None

            elif level == "root":
                # Obtenir l'UID du cluster
                typologie_name, cluster_name = path[:2]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                        typologie_dgraph['uid'],
                        cluster_name
                    )

                    if cluster_dgraph:
                        position = len(self.hierarchy_cache.get_children_at_path(path))
                        root_uid = self.dgraph_manager.add_root_label(
                            cluster_dgraph['uid'],
                            name,
                            '',
                            'default',
                            position
                        )
                        return root_uid is not None

            elif level == "parent":
                # Obtenir l'UID du root
                typologie_name, cluster_name, root_name = path[:3]
                typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                    project_name,
                    typologie_name
                )

                if typologie_dgraph:
                    cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                        typologie_dgraph['uid'],
                        cluster_name
                    )

                    if cluster_dgraph:
                        root_dgraph = self.dgraph_manager.get_root_label_by_name(
                            cluster_dgraph['uid'],
                            root_name
                        )

                        if root_dgraph:
                            position = len(self.hierarchy_cache.get_children_at_path(path))
                            parent_uid = self.dgraph_manager.add_label_node(
                                root_dgraph['uid'],
                                name,
                                '',
                                'default',
                                depth=0,
                                position=position
                            )
                            return parent_uid is not None

            return False

        except Exception as e:
            logger.error(f"Erreur _sync_label_to_dgraph: {e}")
            return False

    def _edit_label(self, level):
        """Modifier un label"""
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            return
        
        old_name = current.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, f"{tr('dataset.edit')} {level}",
            tr("dataset.new_name") + ":",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name == old_name:
            return
        
        new_name = new_name.strip()
        path = self._get_path_for_level(level)
        
        if path is None:
            return
        
        # Renommer dans le cache
        if self.hierarchy_cache.rename_child_at_path(path, old_name, new_name):
            current.setText(new_name)
            logger.info(f"{level.capitalize()} renommé: '{old_name}' -> '{new_name}'")

    def _remove_label(self, level):
        """Supprime un label avec synchronisation complète"""
        list_widget = self._get_list_for_level(level)
        current = list_widget.currentItem()
        if not current:
            return

        name_display = current.text()
        name = name_display.split(" (")[0] if " (" in name_display else name_display

        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"),
            f"Supprimer '{name}' et tous ses sous-éléments?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        path = self._get_path_for_level(level)

        if path is None:
            return

        # Supprimer du cache
        cache_success = self.hierarchy_cache.remove_child_at_path(path, name)

        if not cache_success:
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                f"Impossible de supprimer '{name}' du cache"
            )
            return

        # === SUPPRESSION DGRAPH ===
        dgraph_success = False

        if self.dgraph_available and self.dgraph_manager:
            try:
                # Récupérer l'UID du label
                label_uid = self.dgraph_manager.get_node_uid_by_path(level, name, self)

                if label_uid:
                    # Supprimer selon le type
                    if level == "taxonomy":
                        dgraph_success = self.dgraph_manager.delete_cluster(label_uid)
                    elif level == "root":
                        dgraph_success = self.dgraph_manager.delete_root_label(label_uid)
                    elif level == "parent":
                        dgraph_success = self.dgraph_manager.delete_label_node(
                            label_uid, 
                            recursive=True
                        )

                    if dgraph_success:
                        logger.info(f"✅ '{name}' supprimé de Dgraph")

            except Exception as e:
                logger.error(f"❌ Erreur suppression Dgraph: {e}")

        # Recharger l'UI
        row = list_widget.currentRow()
        list_widget.takeItem(row)

        # Effacer les niveaux inférieurs si nécessaire
        self._clear_levels_below(level)

        # Message
        if dgraph_success:
            logger.info(f"✅✅ {level.capitalize()} '{name}' supprimé (Cache + Dgraph)")
        else:
            logger.warning(f"⚠️ {level.capitalize()} '{name}' supprimé (Cache uniquement)")

    def _get_path_for_level(self, level: str) -> list:
        """Obtenir le chemin parent pour un niveau donné - EXTRAIT LES NOMS SANS COMPTEURS"""
        typ_item = self.typologie_list.currentItem()

        if level == "taxonomy":
            if typ_item:
                # Extraire le nom sans compteur
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display
                return [typ_name]
            return None

        tax_item = self.taxonomy_list.currentItem() if hasattr(self, 'taxonomy_list') else None

        if level == "root":
            if typ_item and tax_item:
                # Extraire les noms sans compteurs
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

                return [typ_name, tax_name]
            return None

        root_item = self.root_list.currentItem()

        if level == "parent":
            if typ_item and tax_item and root_item:
                # Extraire les noms sans compteurs
                typ_display = typ_item.text()
                typ_name = typ_display.split(" (")[0] if " (" in typ_display else typ_display

                tax_display = tax_item.text()
                tax_name = tax_display.split(" (")[0] if " (" in tax_display else tax_display

                root_display = root_item.text()
                root_name = root_display.split(" (")[0] if " (" in root_display else root_display

                return [typ_name, tax_name, root_name]
            return None

        return None
    
    def _sync_child_to_dgraph(self, name: str, path: list) -> bool:
        if not self.dgraph_available or not self.dgraph_manager:
            return False

        try:
            project_name = self.project_manager.current_project_name

            # Déterminer le parent direct et la profondeur
            if len(path) == 4:
                # Parent direct = parent_label
                typologie_name, cluster_name, root_name, parent_name = path
                depth = 1
                parent_level = "parent"
            else:
                # Parent direct = child label à (len(path) - 4) niveaux
                typologie_name, cluster_name, root_name = path[:3]
                depth = len(path) - 3
                parent_level = "child"

            # Obtenir l'UID du parent
            typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                project_name,
                typologie_name
            )

            if not typologie_dgraph:
                return False

            cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                typologie_dgraph['uid'],
                cluster_name
            )

            if not cluster_dgraph:
                return False

            root_dgraph = self.dgraph_manager.get_root_label_by_name(
                cluster_dgraph['uid'],
                root_name
            )

            if not root_dgraph:
                return False

            # Naviguer jusqu'au parent direct
            parent_uid = root_dgraph['uid']

            for i in range(3, len(path)):
                parent_name = path[i]
                # Chercher le parent dans Dgraph
                parent_dgraph = self.dgraph_manager.get_label_node_by_name(
                    parent_uid,
                    parent_name
                )

                if not parent_dgraph:
                    logger.warning(f"Parent '{parent_name}' non trouvé dans Dgraph")
                    return False

                parent_uid = parent_dgraph['uid']

            # Créer l'enfant
            position = len(self.hierarchy_cache.get_children_at_path(path))
            child_uid = self.dgraph_manager.add_label_node(
                parent_uid,
                name,
                '',
                'default',
                depth=depth,
                position=position
            )

            return child_uid is not None

        except Exception as e:
            logger.error(f"Erreur _sync_child_to_dgraph: {e}")
            return False
        
    def _reload_ui_after_child_add(self, saved_names):
        """
        Recharge l'UI après ajout d'enfant - VERSION OPTIMISÉE
        """
        # Bloquer signaux
        widgets = [
            self.typologie_list,
            self.taxonomy_list,
            self.root_list,
            self.parent_list,
            self.child_list
        ]

        for widget in widgets:
            if widget:
                widget.blockSignals(True)

        # Recharger et restaurer chaque niveau
        if 'typologie' in saved_names:
            self._load_list_from_cache(self.typologie_list, [])
            self._restore_selection(self.typologie_list, saved_names['typologie'])

        if 'taxonomy' in saved_names and saved_names['typologie']:
            self._load_list_from_cache(
                self.taxonomy_list,
                [saved_names['typologie']]
            )
            self._restore_selection(self.taxonomy_list, saved_names['taxonomy'])

        if 'root' in saved_names and all([saved_names['typologie'], saved_names['taxonomy']]):
            self._load_list_from_cache(
                self.root_list,
                [saved_names['typologie'], saved_names['taxonomy']]
            )
            self._restore_selection(self.root_list, saved_names['root'])

        if 'parent' in saved_names and all([
            saved_names['typologie'],
            saved_names['taxonomy'],
            saved_names['root']
        ]):
            self._load_list_from_cache(
                self.parent_list,
                [saved_names['typologie'], saved_names['taxonomy'], saved_names['root']]
            )
            self._restore_selection(self.parent_list, saved_names['parent'])

        # Recharger enfants
        self._load_children_from_cache()

        # Débloquer signaux
        for widget in widgets:
            if widget:
                widget.blockSignals(False)

        # Mettre à jour boutons
        self._update_button_states()

    def _add_child(self):
        """Ajoute un enfant avec synchronisation complète"""
        parent_item = self.parent_list.currentItem()
        if not parent_item:
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Veuillez d'abord sélectionner un parent")
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouvel enfant", "Nom :"
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        path = self._get_full_path()
        logger.debug(f"=== AJOUT ENFANT ===")
        logger.debug(f"Nom: '{name}'")
        logger.debug(f"Chemin: {' > '.join(path)}")

        if len(path) < 4:
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Chemin incomplet. Veuillez sélectionner typologie, taxonomy, root et parent.")
            return

        # Vérifier les doublons
        existing = self.hierarchy_cache.get_children_at_path(path)
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Doublon",
                f"'{name}' existe déjà à ce niveau")
            return

        # Sauvegarder les noms
        saved_names = self._save_current_selections()
        logger.debug(f"Noms sauvegardés: {saved_names}")

        # Ajouter au cache
        if not self.hierarchy_cache.add_child_at_path(path, name):
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                f"Impossible d'ajouter '{name}' au cache"
            )
            return

        logger.info(f"✓ '{name}' ajouté au cache")

        # === AJOUT AU PROJECT_MANAGER (SQLite) ===
        sqlite_success = self.project_manager.add_child_label(name, self)
        sqlite_id = None

        if not sqlite_success:
            # Rollback
            self.hierarchy_cache.remove_child_at_path(path, name)
            logger.error(f"✗ Échec ajout au project_manager, rollback")
            QtWidgets.QMessageBox.warning(self, "Erreur",
                "Impossible d'ajouter l'enfant au project_manager")
            return

        logger.info(f"✓ '{name}' ajouté au project_manager")

        # Récupérer l'ID SQLite (si disponible)
        # Note: Vous devrez ajouter une méthode pour récupérer l'ID du dernier enfant créé

        # === SYNC DGRAPH ===
        dgraph_success = False
        dgraph_uid = None

        if self.dgraph_available and self.dgraph_manager:
            try:
                dgraph_uid, dgraph_success = self._sync_child_to_dgraph_complete(
                    name, path
                )

                # ✅ SYNC UID vers SQLite
                if dgraph_success and dgraph_uid and sqlite_id:
                    self.dgraph_manager.sync_uid_to_sqlite(
                        'child', sqlite_id, dgraph_uid
                    )
                    logger.info(f"✅ UID mappé: child#{sqlite_id} ↔ {dgraph_uid}")

            except Exception as e:
                logger.error(f"❌ Erreur sync Dgraph: {e}")

        # Recharger l'UI
        self._reload_ui_after_child_add(saved_names)

        # Message selon résultat
        if dgraph_success:
            logger.info(f"✓✓✓ Enfant '{name}' ajouté (SQLite + Dgraph + Mapping)")
        else:
            logger.warning(f"⚠️ Enfant '{name}' ajouté (SQLite uniquement)")

    def _sync_child_to_dgraph_complete(self, name: str, path: list) -> tuple:
        if not self.dgraph_available or not self.dgraph_manager:
            return (None, False)

        try:
            project_name = self.project_manager.current_project_name

            # Déterminer le parent direct et la profondeur
            if len(path) == 4:
                # Parent direct = parent_label
                typologie_name, cluster_name, root_name, parent_name = path
                depth = 1
            else:
                # Parent direct = child label à (len(path) - 4) niveaux
                typologie_name, cluster_name, root_name = path[:3]
                depth = len(path) - 3

            # Obtenir l'UID du parent
            typologie_dgraph = self.dgraph_manager.get_typologie_by_name(
                project_name,
                typologie_name
            )

            if not typologie_dgraph:
                return (None, False)

            cluster_dgraph = self.dgraph_manager.get_cluster_by_name(
                typologie_dgraph['uid'],
                cluster_name
            )

            if not cluster_dgraph:
                return (None, False)

            root_dgraph = self.dgraph_manager.get_root_label_by_name(
                cluster_dgraph['uid'],
                root_name
            )

            if not root_dgraph:
                return (None, False)

            # Naviguer jusqu'au parent direct
            parent_uid = root_dgraph['uid']

            for i in range(3, len(path)):
                parent_name = path[i]
                # Chercher le parent dans Dgraph
                parent_dgraph = self.dgraph_manager.get_label_node_by_name(
                    parent_uid,
                    parent_name
                )

                if not parent_dgraph:
                    logger.warning(f"Parent '{parent_name}' non trouvé dans Dgraph")
                    return (None, False)

                parent_uid = parent_dgraph['uid']

            # Créer l'enfant
            position = len(self.hierarchy_cache.get_children_at_path(path))
            child_uid = self.dgraph_manager.add_label_node(
                parent_uid,
                name,
                '',
                'default',
                depth=depth,
                position=position
            )

            return (child_uid, child_uid is not None)

        except Exception as e:
            logger.error(f"Erreur _sync_child_to_dgraph_complete: {e}")
            return (None, False)
    
    def _refresh_ui_after_add(self, level, saved_selections):
        """
        Recharge l'interface après ajout d'un élément - VERSION FLUIDE
        Maintient les sélections et permet l'ajout successif

        Args:
            level: Le niveau ajouté ('taxonomy', 'root', 'parent', 'child')
            saved_selections: Les sélections sauvegardées avant l'ajout
        """
        logger.debug(f"=== REFRESH UI AFTER ADD: {level} ===")

        # Déterminer quelles listes recharger selon le niveau
        lists_to_refresh = {
            'taxonomy': ['typologie', 'taxonomy'],
            'root': ['typologie', 'taxonomy', 'root'],
            'parent': ['typologie', 'taxonomy', 'root', 'parent'],
            'child': ['typologie', 'taxonomy', 'root', 'parent', 'child']
        }

        refresh_levels = lists_to_refresh.get(level, [])

        # Bloquer temporairement les signaux pour éviter les cascades
        widgets = {
            'typologie': self.typologie_list,
            'taxonomy': self.taxonomy_list if hasattr(self, 'taxonomy_list') else None,
            'root': self.root_list,
            'parent': self.parent_list,
            'child': self.child_list
        }

        # Bloquer les signaux
        for widget in widgets.values():
            if widget:
                widget.blockSignals(True)

        # Recharger les listes nécessaires
        if 'typologie' in refresh_levels:
            self._load_list_from_cache(self.typologie_list, [])

        if 'taxonomy' in refresh_levels and saved_selections['typologie']:
            self._load_list_from_cache(
                self.taxonomy_list, 
                [saved_selections['typologie']]
            )

        if 'root' in refresh_levels and saved_selections['typologie'] and saved_selections['taxonomy']:
            self._load_list_from_cache(
                self.root_list, 
                [saved_selections['typologie'], saved_selections['taxonomy']]
            )

        if 'parent' in refresh_levels and all([
            saved_selections['typologie'], 
            saved_selections['taxonomy'], 
            saved_selections['root']
        ]):
            self._load_list_from_cache(
                self.parent_list, 
                [saved_selections['typologie'], saved_selections['taxonomy'], saved_selections['root']]
            )

        if 'child' in refresh_levels and all([
            saved_selections['typologie'],
            saved_selections['taxonomy'],
            saved_selections['root'],
            saved_selections['parent']
        ]):
            self._load_children_from_cache()

        # Restaurer les sélections
        self._restore_selections(saved_selections)

        # Débloquer les signaux
        for widget in widgets.values():
            if widget:
                widget.blockSignals(False)

        # Réactiver les listes
        if hasattr(self, 'taxonomy_list'):
            self.taxonomy_list.setEnabled(saved_selections['typologie'] is not None)
        self.root_list.setEnabled(saved_selections['taxonomy'] is not None)
        self.parent_list.setEnabled(saved_selections['root'] is not None)
        self.child_list.setEnabled(saved_selections['parent'] is not None)

        # Mettre à jour les boutons - CRITIQUE pour permettre l'ajout successif
        self._update_button_states()

        logger.debug(f"✓ UI rafraîchie, boutons réactivés pour ajout successif")
            
    def _clear_all_caches(self):
        """Vide tous les caches"""
        self.hierarchy_cache.clear()
        self._child_navigation_path.clear()

        logger.debug("Cache hiérarchique vidé")

    def _edit_child(self):
        """Modifier un enfant - VERSION CORRIGÉE avec extraction du nom"""
        current = self.child_list.currentItem()
        if not current:
            return

        old_display = current.text()
        # CORRECTION: Extraire le nom réel pour l'édition
        if " (" in old_display:
            old_name = old_display.split(" (")[0]
        else:
            old_name = old_display

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, tr("dataset.edit_child"),
            tr("dataset.new_name") + ":",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name == old_name:
            return

        new_name = new_name.strip()
        path = self._get_full_path()

        # Renommer avec le NOM RÉEL (sans compteur)
        if self.hierarchy_cache.rename_child_at_path(path, old_name, new_name):
            # Recharger pour afficher le nouveau nom avec compteur mis à jour
            self._load_children_from_cache()
            logger.info(f"Enfant renommé: '{old_name}' -> '{new_name}'")

    def _remove_child(self):
        """Supprime un enfant avec synchronisation complète"""
        current = self.child_list.currentItem()
        if not current:
            return

        child_display = current.text()
        # Extraire le nom réel pour la suppression
        child_name = child_display.split(" (")[0] if " (" in child_display else child_display

        reply = QtWidgets.QMessageBox.question(
            self, tr("dataset.confirm"),
            f"Supprimer '{child_name}' et tous ses sous-éléments?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        path = self._get_full_path()

        # Supprimer du cache
        cache_success = self.hierarchy_cache.remove_child_at_path(path, child_name)

        if not cache_success:
            QtWidgets.QMessageBox.warning(
                self, "Erreur",
                f"Impossible de supprimer '{child_name}' du cache"
            )
            return

        # === SUPPRESSION DGRAPH ===
        dgraph_success = False

        if self.dgraph_available and self.dgraph_manager:
            try:
                # Récupérer l'UID de l'enfant
                child_uid = self.dgraph_manager.get_node_uid_by_path('child', child_name, self)

                if child_uid:
                    # Supprimer récursivement
                    dgraph_success = self.dgraph_manager.delete_label_node(
                        child_uid,
                        recursive=True
                    )

                    if dgraph_success:
                        logger.info(f"✅ Enfant '{child_name}' supprimé de Dgraph")

            except Exception as e:
                logger.error(f"❌ Erreur suppression Dgraph enfant: {e}")

        # Recharger l'UI
        self._load_children_from_cache()
        self._refresh_all_counts()

        # Message
        if dgraph_success:
            logger.info(f"✅✅ Enfant '{child_name}' supprimé (Cache + Dgraph)")
        else:
            logger.warning(f"⚠️ Enfant '{child_name}' supprimé (Cache uniquement)")

    # ========== UI HELPERS ==========

    def _get_list_for_level(self, level: str) -> QtWidgets.QListWidget:
        """Retourner le widget liste pour un niveau"""
        mapping = {
            "taxonomy": self.taxonomy_list,
            "root": self.root_list,
            "parent": self.parent_list,
            "child": self.child_list
        }
        return mapping.get(level, self.child_list)
    
    def _clear_levels_below(self, level: str):
        """Effacer les niveaux sous un niveau donné"""
        levels = ["taxonomy", "root", "parent", "child"]
        try:
            idx = levels.index(level)
            for lvl in levels[idx + 1:]:
                self._get_list_for_level(lvl).clear()
            if level in ["taxonomy", "root", "parent"]:
                self._child_navigation_path.clear()
        except ValueError:
            pass

    def _sync_current_level_to_cache(self):
        """Synchroniser le niveau actuel vers le cache"""
        # Cette méthode est appelée avant de changer de sélection
        # pour s'assurer que l'état actuel est sauvegardé
        pass

    def _ensure_typologie_selected(self):
        """Ensure typologie is selected"""
        if self.typologie_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_typologie_first")
            )
            return False
        return True

    def _ensure_taxonomy_selected(self):
        """Ensure taxonomy cluster is selected"""
        if not self._ensure_typologie_selected():
            return False
        # If taxonomy clusters are not being used yet, skip this check
        if not hasattr(self, 'taxonomy_list'):
            return True
        if self.taxonomy_list.count() == 0:
            # No taxonomy clusters yet, show warning
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), "Veuillez d'abord ajouter un cluster de taxonomie"
            )
            return False
        if self.taxonomy_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), "Veuillez d'abord sélectionner un cluster de taxonomie"
            )
            return False
        return True

    def _ensure_root_selected(self):
        """Ensure root label is selected"""
        if not self._ensure_taxonomy_selected():
            return False
        if self.root_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_root_first")
            )
            return False
        return True

    def _ensure_parent_selected(self):
        """Ensure parent label is selected"""
        if not self._ensure_root_selected():
            return False
        if self.parent_list.currentItem() is None:
            QtWidgets.QMessageBox.warning(
                self, tr("dataset.selection_required"), tr("dataset.select_parent_first")
            )
            return False
        return True

    def _load_project_ui(self):
        data = self.project_manager.get_current_project_data()
        if not data:
            return

        # Charger le nom du projet
        self.project_name_edit.setText(data.get('nom', ''))

        # Charger les typologies depuis le cache (déjà peuplé)
        self._refresh_typologie_list()

        # Activer les boutons
        self.save_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(True)

        # Mettre à jour l'état des boutons
        self._update_button_states()

        logger.debug("Interface projet chargée")

    def _refresh_typologie_list(self):
        """Refresh typologies list from cache"""
        self.typologie_list.clear()

        # Charger depuis le cache
        typologies = self.hierarchy_cache.get_typologies()
        for typ_name in typologies:
            item = QtWidgets.QListWidgetItem(typ_name)
            self.typologie_list.addItem(item)

        # Si vide, charger depuis le manager
        if not typologies:
            db_typologies = self.project_manager.get_typologies()
            for typ in db_typologies:
                typ_name = typ.get('name', '')
                if typ_name:
                    self.hierarchy_cache.add_typologie(typ_name)
                    item = QtWidgets.QListWidgetItem(typ_name)
                    self.typologie_list.addItem(item)

        self._update_button_states()

    def _load_taxonomy_clusters(self):
        """Load taxonomy clusters"""
        if not hasattr(self, 'taxonomy_list'):
            return
        self.taxonomy_list.clear()
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self._update_button_states()

    def _load_root_labels(self):
        """Load root labels for the currently selected taxonomy cluster"""
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()

        if not hasattr(self, 'taxonomy_list'):
            logger.warning("taxonomy_list n'existe pas")
            self._update_button_states()
            return

        current_taxonomy = self.taxonomy_list.currentItem()
        if not current_taxonomy:
            logger.debug("Aucun cluster de taxonomie sélectionné")
            self._update_button_states()
            return

        taxonomy_name = current_taxonomy.text()
        logger.debug(f"Chargement des labels racines pour le cluster: '{taxonomy_name}'")

        root_labels = self.project_manager.get_root_labels()

        if not root_labels:
            logger.debug(f"Aucun label racine trouvé pour le cluster '{taxonomy_name}'")
        else:
            logger.debug(f"{len(root_labels)} label(s) racine(s) trouvé(s) pour '{taxonomy_name}'")

        for label in root_labels:
            item = QtWidgets.QListWidgetItem(label.get('name', ''))
            self.root_list.addItem(item)

        self._update_button_states()

    def _load_parent_labels(self):
        """Load parent labels"""
        self.parent_list.clear()
        self.child_list.clear()
        parent_labels = self.project_manager.get_parent_labels()
        for label in parent_labels:
            item = QtWidgets.QListWidgetItem(label.get('name', ''))
            self.parent_list.addItem(item)
        self._update_button_states()

    def _load_child_labels(self):
        """Load child labels at current depth - DEPRECATED, use _load_child_from_cache instead"""
        # Cette méthode est maintenant remplacée par _load_child_from_cache
        self._load_child_from_cache()

    def _clear_ui(self):
        """Clear entire UI"""
        self.project_name_edit.clear()
        self.typologie_list.clear()
        self._clear_hierarchy()

        # Vider le cache unifié
        self.hierarchy_cache.clear()

        self.save_btn.setEnabled(False)
        self.delete_project_btn.setEnabled(False)
        self._update_button_states()

    def _clear_hierarchy(self):
        """Clear label hierarchy"""
        if hasattr(self, 'taxonomy_list'):
            self.taxonomy_list.clear()
        self.root_list.clear()
        self.parent_list.clear()
        self.child_list.clear()
        self.breadcrumb_label.setText(tr("dataset.root"))
        self.up_btn.setEnabled(False)
        self._update_button_states()

    def _update_button_states(self):
        """Update button states - VERSION COMPLÈTE AVEC BOUTONS RELATION"""
        project_selected = bool(
            self.project_combo.currentIndex() >= 0 and 
            self.project_combo.currentText()
        )

        typologie_selected = self.typologie_list.currentItem() is not None
        taxonomy_selected = hasattr(self, 'taxonomy_list') and self.taxonomy_list.currentItem() is not None
        root_selected = self.root_list.currentItem() is not None
        parent_selected = self.parent_list.currentItem() is not None
        child_selected = self.child_list.currentItem() is not None

        # ========== BOUTONS DE PROJET ==========
        self.add_project_btn.setEnabled(True)
        self.delete_project_btn.setEnabled(project_selected)

        # ========== BOUTONS DE TYPOLOGIE ==========
        self.add_typologie_btn.setEnabled(project_selected)
        self.edit_typologie_btn.setEnabled(typologie_selected)
        self.remove_typologie_btn.setEnabled(typologie_selected)

        if hasattr(self, 'relation_typologie_btn'):
            self.relation_typologie_btn.setEnabled(typologie_selected and self.dgraph_available)

        # ========== BOUTONS DE TAXONOMY ==========
        if hasattr(self, 'add_taxonomy_btn'):
            # Boutons principaux
            self.add_taxonomy_btn.setEnabled(typologie_selected)
            self.edit_taxonomy_btn.setEnabled(taxonomy_selected)
            self.remove_taxonomy_btn.setEnabled(taxonomy_selected)

            # Boutons d'insertion
            if hasattr(self, 'insert_parent_taxonomy_btn'):
                self.insert_parent_taxonomy_btn.setEnabled(taxonomy_selected)
                self.insert_child_taxonomy_btn.setEnabled(taxonomy_selected)

            # NOUVEAU: Bouton relation
            if hasattr(self, 'relation_taxonomy_btn'):
                self.relation_taxonomy_btn.setEnabled(taxonomy_selected and self.dgraph_available)

            # Activer/désactiver la liste
            self.taxonomy_list.setEnabled(typologie_selected or self.taxonomy_list.count() > 0)

        # ========== BOUTONS DE ROOT ==========
        # Boutons principaux
        self.add_root_btn.setEnabled(taxonomy_selected)
        self.edit_root_btn.setEnabled(root_selected)
        self.remove_root_btn.setEnabled(root_selected)

        # Boutons d'insertion
        if hasattr(self, 'insert_parent_root_btn'):
            self.insert_parent_root_btn.setEnabled(root_selected)
            self.insert_child_root_btn.setEnabled(root_selected)

        # NOUVEAU: Bouton relation
        if hasattr(self, 'relation_root_btn'):
            self.relation_root_btn.setEnabled(root_selected and self.dgraph_available)

        # Activer/désactiver la liste
        self.root_list.setEnabled(taxonomy_selected or self.root_list.count() > 0)

        # ========== BOUTONS DE PARENT ==========
        # Boutons principaux
        self.add_parent_btn.setEnabled(root_selected)
        self.edit_parent_btn.setEnabled(parent_selected)
        self.remove_parent_btn.setEnabled(parent_selected)

        # Boutons d'insertion
        if hasattr(self, 'insert_parent_parent_btn'):
            self.insert_parent_parent_btn.setEnabled(parent_selected)
            self.insert_child_parent_btn.setEnabled(parent_selected)

        # NOUVEAU: Bouton relation
        if hasattr(self, 'relation_parent_btn'):
            self.relation_parent_btn.setEnabled(parent_selected and self.dgraph_available)

        # Activer/désactiver la liste
        self.parent_list.setEnabled(root_selected or self.parent_list.count() > 0)

        # ========== BOUTONS DE CHILD ==========
        # Boutons principaux
        self.add_child_btn.setEnabled(parent_selected)
        self.edit_child_btn.setEnabled(child_selected)
        self.remove_child_btn.setEnabled(child_selected)

        # Boutons d'insertion
        if hasattr(self, 'insert_parent_child_btn'):
            self.insert_parent_child_btn.setEnabled(child_selected)
            self.insert_child_child_btn.setEnabled(child_selected)

        # NOUVEAU: Bouton relation (pour les enfants)
        if hasattr(self, 'relation_child_btn'):
            self.relation_child_btn.setEnabled(child_selected and self.dgraph_available)

        # Boutons de navigation
        self.dive_btn.setEnabled(child_selected)

        # Activer/désactiver la liste
        self.child_list.setEnabled(parent_selected or self.child_list.count() > 0)

        # ========== BOUTON DE NAVIGATION UP ==========
        depth = len(self._child_navigation_path)
        self.up_btn.setEnabled(depth > 0)

        # ========== BOUTON DE SAUVEGARDE ==========
        self.save_btn.setEnabled(project_selected)

        # ========== LOGGING DEBUG ==========
        logger.debug(f"Boutons mis à jour - Projet: {project_selected}, Typo: {typologie_selected}, "
                    f"Tax: {taxonomy_selected}, Root: {root_selected}, Parent: {parent_selected}, "
                    f"Child: {child_selected}, Dgraph: {self.dgraph_available}")

    def _refresh_project_combos(self):
        """Refresh all project combos"""
        try:
            projects = self.project_manager.get_all_projects()
            project_names = sorted([p['name'] for p in projects])
            current_project = self.project_combo.currentText()
            
            self.project_combo.blockSignals(True)
            self.project_combo.clear()
            
            if project_names:
                self.project_combo.addItems(project_names)
                logger.info(f"{len(project_names)} projet(s) chargé(s): {', '.join(project_names)}")
            else:
                logger.info("Aucun projet trouvé dans la base de données")
            
            self.project_combo.blockSignals(False)
            
            # Resélectionner le projet courant et forcer le chargement
            if current_project in project_names:
                index = self.project_combo.findText(current_project)
                self.project_combo.setCurrentIndex(index)
                # Forcer le chargement même si l'index n'a pas changé
                self._on_project_selected(index)
            elif project_names:
                # Si le projet courant n'existe plus, sélectionner le premier
                self.project_combo.setCurrentIndex(0)
                self._on_project_selected(0)
            else:
                # Aucun projet disponible, nettoyer l'interface
                self._clear_ui()
            
            self._update_button_states()
            
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement des projets: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger les projets: {str(e)}"
            )

    def _load_project_from_db_to_cache(self):
        """
        Charge un projet depuis la base de données vers le cache hiérarchique
        VERSION AVEC VALIDATION STRICTE
        """
        if not self.project_manager.current_project_data:
            logger.warning("⚠️ Aucun projet à charger dans le cache")
            return

        # Vider le cache actuel
        self.hierarchy_cache.clear()

        project_data = self.project_manager.current_project_data

        # Validation stricte
        if not isinstance(project_data, dict):
            raise TypeError(f"project_data doit être un dict, pas {type(project_data)}")

        typologies = project_data.get('typologies', [])

        if not isinstance(typologies, list):
            raise TypeError(f"typologies doit être une liste, pas {type(typologies)}")

        logger.info(f"📊 Chargement de {len(typologies)} typologie(s)...")

        for typ_idx, typologie in enumerate(typologies):
            # Validation de la typologie
            if not isinstance(typologie, dict):
                logger.warning(f"⚠️ Typologie #{typ_idx} n'est pas un dict, ignorée")
                continue
            
            typ_name = typologie.get('name', '').strip()

            if not typ_name:
                logger.warning(f"⚠️ Typologie #{typ_idx} sans nom, ignorée")
                continue
            
            logger.debug(f"  📁 Chargement typologie '{typ_name}'...")

            # Ajouter la typologie
            self.hierarchy_cache.add_typologie(typ_name)

            # Charger les clusters de taxonomie
            taxonomy_clusters = typologie.get('taxonomy_clusters', [])

            if not isinstance(taxonomy_clusters, list):
                logger.warning(f"⚠️ taxonomy_clusters n'est pas une liste pour '{typ_name}'")
                taxonomy_clusters = []

            for tax_idx, cluster in enumerate(taxonomy_clusters):
                # Validation du cluster
                if not isinstance(cluster, dict):
                    logger.warning(f"⚠️ Cluster #{tax_idx} n'est pas un dict, ignoré")
                    continue
                
                cluster_name = cluster.get('name', '').strip()

                if not cluster_name:
                    logger.warning(f"⚠️ Cluster #{tax_idx} sans nom, ignoré")
                    continue
                
                logger.debug(f"    🏷️ Chargement cluster '{cluster_name}'...")

                # Ajouter le cluster au cache
                path = [typ_name]
                self.hierarchy_cache.add_child_at_path(path, cluster_name)

                # Charger les root labels
                root_labels = cluster.get('root_labels', [])

                if not isinstance(root_labels, list):
                    logger.warning(f"⚠️ root_labels n'est pas une liste pour '{cluster_name}'")
                    root_labels = []

                for root_idx, root in enumerate(root_labels):
                    # Validation du root
                    if not isinstance(root, dict):
                        logger.warning(f"⚠️ Root #{root_idx} n'est pas un dict, ignoré")
                        continue
                    
                    root_name = root.get('name', '').strip()

                    if not root_name:
                        logger.warning(f"⚠️ Root #{root_idx} sans nom, ignoré")
                        continue
                    
                    logger.debug(f"      🌳 Chargement root '{root_name}'...")

                    path = [typ_name, cluster_name]
                    self.hierarchy_cache.add_child_at_path(path, root_name)

                    # Charger les parent labels
                    parent_labels = root.get('parent_labels', [])

                    if not isinstance(parent_labels, list):
                        logger.warning(f"⚠️ parent_labels n'est pas une liste pour '{root_name}'")
                        parent_labels = []

                    for parent_idx, parent in enumerate(parent_labels):
                        # Validation du parent
                        if not isinstance(parent, dict):
                            logger.warning(f"⚠️ Parent #{parent_idx} n'est pas un dict, ignoré")
                            continue
                        
                        parent_name = parent.get('name', '').strip()

                        if not parent_name:
                            logger.warning(f"⚠️ Parent #{parent_idx} sans nom, ignoré")
                            continue
                        
                        logger.debug(f"        👨 Chargement parent '{parent_name}'...")

                        path = [typ_name, cluster_name, root_name]
                        self.hierarchy_cache.add_child_at_path(path, parent_name)

                        # Charger les enfants récursivement
                        children = parent.get('children', [])

                        if not isinstance(children, list):
                            logger.warning(f"⚠️ children n'est pas une liste pour '{parent_name}'")
                            children = []

                        path = [typ_name, cluster_name, root_name, parent_name]

                        try:
                            self._load_children_recursive_to_cache(path, children)
                        except Exception as child_error:
                            logger.error(f"❌ Erreur chargement enfants de '{parent_name}': {child_error}")

        logger.info(f"✅ Projet chargé dans le cache: {len(typologies)} typologie(s)")

    def _has_unsaved_changes(self):
        """
        Vérifie s'il y a des modifications non sauvegardées
        """
        return self.hierarchy_cache.has_changes()

    def _load_children_recursive_to_cache(self, parent_path, children_list):
        """
        Charge récursivement les enfants dans le cache
        VERSION AVEC VALIDATION

        Args:
            parent_path: Chemin jusqu'au parent (liste de noms)
            children_list: Liste des enfants à charger
        """
        if not isinstance(children_list, list):
            logger.warning(f"⚠️ children_list n'est pas une liste: {type(children_list)}")
            return

        for child_idx, child in enumerate(children_list):
            # Validation de l'enfant
            if not isinstance(child, dict):
                logger.warning(f"⚠️ Enfant #{child_idx} n'est pas un dict, ignoré")
                continue
            
            child_name = child.get('name', '').strip()

            if not child_name:
                logger.warning(f"⚠️ Enfant #{child_idx} sans nom, ignoré")
                continue
            
            # Ajouter l'enfant au cache
            self.hierarchy_cache.add_child_at_path(parent_path, child_name)

            logger.debug(f"{'  ' * len(parent_path)}👶 Enfant '{child_name}' ajouté")

            # Charger les sous-enfants récursivement
            sub_children = child.get('children', [])

            if sub_children:
                if not isinstance(sub_children, list):
                    logger.warning(f"⚠️ Sous-enfants de '{child_name}' ne sont pas une liste")
                else:
                    child_path = parent_path + [child_name]
                    self._load_children_recursive_to_cache(child_path, sub_children)

    def _prompt_save_if_needed(self):
        """
        Demande à l'utilisateur s'il veut sauvegarder avant de continuer
        """
        if self._has_unsaved_changes():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Modifications non sauvegardées",
                "Le projet contient des modifications non sauvegardées. Voulez-vous sauvegarder ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self._save_project()
                return True
            elif reply == QtWidgets.QMessageBox.Cancel:
                return False

        return True
    
    def _validate_hierarchy_integrity(self):
        """
        Valide l'intégrité de la hiérarchie cache <-> project_manager
        Utile pour le débogage
        """
        try:
            # Vérifier que toutes les typologies du cache sont dans le manager
            cache_typologies = set(self.hierarchy_cache.get_typologies())
            manager_typologies = set(t.get('name', '') for t in self.project_manager.get_typologies())

            if cache_typologies != manager_typologies:
                logger.warning(f"Incohérence typologies: cache={cache_typologies}, manager={manager_typologies}")
                return False

            logger.debug("Intégrité de la hiérarchie validée")
            return True

        except Exception as e:
            logger.error(f"Erreur validation intégrité: {e}")
            return False

    def _sync_cache_to_project_manager(self):
        """
        Synchronise le cache hiérarchique vers le project_manager
        À appeler avant save_project()
        """
        if not self.project_manager.current_project_data:
            logger.error("Aucun projet actuel")
            return False

        # Construire la structure de données depuis le cache
        typologies = []

        for typ_name in self.hierarchy_cache.get_typologies():
            typologie = {
                'name': typ_name,
                'description': '',
                'taxonomy_clusters': []
            }

            # Récupérer les clusters de taxonomie
            typ_path = [typ_name]
            clusters = self.hierarchy_cache.get_children_at_path(typ_path)

            for cluster_name in clusters:
                cluster = {
                    'name': cluster_name,
                    'description': '',
                    'root_labels': []
                }

                # Récupérer les root labels
                cluster_path = [typ_name, cluster_name]
                roots = self.hierarchy_cache.get_children_at_path(cluster_path)

                for root_name in roots:
                    root = {
                        'name': root_name,
                        'description': '',
                        'category': 'default',
                        'parent_labels': []
                    }

                    # Récupérer les parent labels
                    root_path = [typ_name, cluster_name, root_name]
                    parents = self.hierarchy_cache.get_children_at_path(root_path)

                    for parent_name in parents:
                        parent = {
                            'name': parent_name,
                            'description': '',
                            'category': 'default',
                            'children': []
                        }

                        # Récupérer les enfants récursivement
                        parent_path = [typ_name, cluster_name, root_name, parent_name]
                        parent['children'] = self._build_children_from_cache(parent_path)

                        root['parent_labels'].append(parent)

                    cluster['root_labels'].append(root)

                typologie['taxonomy_clusters'].append(cluster)

            typologies.append(typologie)

        # Mettre à jour le project_manager
        self.project_manager.current_project_data['typologies'] = typologies

        logger.info(f"Cache synchronisé: {len(typologies)} typologie(s)")
        return True
    def _debug_print_cache(self):
        """Affiche le contenu du cache pour debug"""
        logger.info("=== DEBUG CACHE ===")
        for typ_name in self.hierarchy_cache.get_typologies():
            logger.info(f"Typologie: {typ_name}")
            for cluster in self.hierarchy_cache.get_children_at_path([typ_name]):
                logger.info(f"  Cluster: {cluster}")
                for root in self.hierarchy_cache.get_children_at_path([typ_name, cluster]):
                    logger.info(f"    Root: {root}")
                    for parent in self.hierarchy_cache.get_children_at_path([typ_name, cluster, root]):
                        logger.info(f"      Parent: {parent}")
                        self._debug_print_children([typ_name, cluster, root, parent], 8)

    def _restore_selection(self, list_widget, name):
        """Restaure la sélection d'un item par nom"""
        for i in range(list_widget.count()):
            item_text = list_widget.item(i).text()
            item_name = item_text.split(" (")[0] if " (" in item_text else item_text
            if item_name == name:
                list_widget.setCurrentRow(i)
                break

    def _restore_selections(self, selections):
        """
        Restaure les sélections sauvegardées - VERSION AMÉLIORÉE
        Maintient l'état actif pour permettre l'ajout successif
        """
        if not selections:
            return

        logger.debug(f"Restauration des sélections: {selections}")

        # Restaurer typologie
        if selections['typologie']:
            restored = False
            for i in range(self.typologie_list.count()):
                item = self.typologie_list.item(i)
                item_name = item.text().split(" (")[0] if " (" in item.text() else item.text()
                if item_name == selections['typologie']:
                    self.typologie_list.setCurrentRow(i)
                    restored = True
                    logger.debug(f"  ✓ Typologie restaurée: '{item_name}'")
                    break
            if not restored:
                logger.warning(f"  ✗ Typologie '{selections['typologie']}' non trouvée")

        # Restaurer taxonomy
        if selections['taxonomy'] and hasattr(self, 'taxonomy_list'):
            restored = False
            for i in range(self.taxonomy_list.count()):
                item = self.taxonomy_list.item(i)
                item_name = item.text().split(" (")[0] if " (" in item.text() else item.text()
                if item_name == selections['taxonomy']:
                    self.taxonomy_list.setCurrentRow(i)
                    restored = True
                    logger.debug(f"  ✓ Taxonomy restaurée: '{item_name}'")
                    break
            if not restored:
                logger.warning(f"  ✗ Taxonomy '{selections['taxonomy']}' non trouvée")

        # Restaurer root
        if selections['root']:
            restored = False
            for i in range(self.root_list.count()):
                item = self.root_list.item(i)
                item_name = item.text().split(" (")[0] if " (" in item.text() else item.text()
                if item_name == selections['root']:
                    self.root_list.setCurrentRow(i)
                    restored = True
                    logger.debug(f"  ✓ Root restauré: '{item_name}'")
                    break
            if not restored:
                logger.warning(f"  ✗ Root '{selections['root']}' non trouvé")

        # Restaurer parent
        if selections['parent']:
            restored = False
            for i in range(self.parent_list.count()):
                item = self.parent_list.item(i)
                item_name = item.text().split(" (")[0] if " (" in item.text() else item.text()
                if item_name == selections['parent']:
                    self.parent_list.setCurrentRow(i)
                    restored = True
                    logger.debug(f"  ✓ Parent restauré: '{item_name}'")
                    break
            if not restored:
                logger.warning(f"  ✗ Parent '{selections['parent']}' non trouvé")

        logger.debug("✓ Restauration des sélections terminée")

    def _save_current_selections(self):
        """Sauvegarde l'état actuel des sélections"""
        selections = {
            'typologie': None,
            'taxonomy': None,
            'root': None,
            'parent': None
        }

        typ_item = self.typologie_list.currentItem()
        if typ_item:
            typ_display = typ_item.text()
            selections['typologie'] = typ_display.split(" (")[0] if " (" in typ_display else typ_display

        if hasattr(self, 'taxonomy_list'):
            tax_item = self.taxonomy_list.currentItem()
            if tax_item:
                tax_display = tax_item.text()
                selections['taxonomy'] = tax_display.split(" (")[0] if " (" in tax_display else tax_display

        root_item = self.root_list.currentItem()
        if root_item:
            root_display = root_item.text()
            selections['root'] = root_display.split(" (")[0] if " (" in root_display else root_display

        parent_item = self.parent_list.currentItem()
        if parent_item:
            parent_display = parent_item.text()
            selections['parent'] = parent_display.split(" (")[0] if " (" in parent_display else parent_display

        return selections
    
    def _debug_print_children(self, path, indent):
        """Affiche récursivement les enfants"""
        children = self.hierarchy_cache.get_children_at_path(path)
        for child in children:
            logger.info(f"{' ' * indent}Child: {child}")
            self._debug_print_children(path + [child], indent + 2)
    
    def _debug_print_project_data(self):
        """Affiche le contenu du project_manager pour debug"""
        logger.info("=== DEBUG PROJECT DATA ===")
        data = self.project_manager.current_project_data
        if not data:
            logger.info("Aucune donnée de projet")
            return
        
        import json
        logger.info(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    
    def _build_children_from_cache(self, parent_path):
        children = []
        child_names = self.hierarchy_cache.get_children_at_path(parent_path)
        
        for child_name in child_names:
            child = {
                'name': child_name,
                'description': '',
                'category': 'default',
                'children': []
            }
            
            # Récupérer les sous-enfants récursivement
            child_path = parent_path + [child_name]
            child['children'] = self._build_children_from_cache(child_path)
            
            children.append(child)
        
        return children



    def _export_strategy(self):
        """Automatically export strategy"""
        if self.project_manager.current_project_name:
            self.project_manager.export_strategy()

    # ========== PUBLIC METHODS ==========

    def refresh(self):
        """Refresh widget data"""
        self._refresh_project_combos()
        if self.project_manager.current_project_name:
            self._load_project_ui()

    def closeEvent(self, event):
        """Appelé à la fermeture du widget"""
        if self.dgraph_manager:
            try:
                self.dgraph_manager.close()
                logger.info("✅ Dgraph manager fermé proprement")
            except Exception as e:
                logger.warning(f"⚠️ Erreur fermeture Dgraph: {e}")
        
        event.accept()