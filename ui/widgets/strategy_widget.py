from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, 
                             QTextEdit, QGroupBox, QSplitter, QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal
import sqlite3
import json


class StrategyWidget(QWidget):
    """
    Widget pour l'onglet Stratégie - Gestion des typologies de contextes
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_path = None
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Gestion des Stratégies et Typologies de Contexte")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Partie gauche - Arbre des typologies
        left_widget = self._create_tree_section()
        main_splitter.addWidget(left_widget)
        
        # Partie droite - Détails et édition
        right_widget = self._create_details_section()
        main_splitter.addWidget(right_widget)
        
        # Définir les proportions
        main_splitter.setSizes([400, 600])
        
        # Barre de boutons en bas
        button_layout = self._create_button_bar()
        layout.addLayout(button_layout)
        
    def _create_tree_section(self):
        """Crée la section avec l'arbre des typologies"""
        widget = QGroupBox("Structure Hiérarchique")
        layout = QVBoxLayout(widget)
        
        # Boutons de gestion de l'arbre
        tree_buttons = QHBoxLayout()
        self.add_cluster_btn = QPushButton("Ajouter Cluster")
        self.add_root_btn = QPushButton("Ajouter Racine")
        self.add_parent_btn = QPushButton("Ajouter Parent")
        self.add_child_btn = QPushButton("Ajouter Enfant")
        self.delete_item_btn = QPushButton("Supprimer")
        
        tree_buttons.addWidget(self.add_cluster_btn)
        tree_buttons.addWidget(self.add_root_btn)
        tree_buttons.addWidget(self.add_parent_btn)
        tree_buttons.addWidget(self.add_child_btn)
        tree_buttons.addWidget(self.delete_item_btn)
        
        layout.addLayout(tree_buttons)
        
        # Arbre des typologies
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Nom", "Type", "ID"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setColumnWidth(1, 100)
        layout.addWidget(self.tree_widget)
        
        return widget
        
    def _create_details_section(self):
        """Crée la section des détails et de l'édition"""
        widget = QGroupBox("Détails et Édition")
        layout = QVBoxLayout(widget)
        
        # Informations de base
        info_layout = QVBoxLayout()
        
        # Nom
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        info_layout.addLayout(name_layout)
        
        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_label = QLabel("Aucun élément sélectionné")
        type_layout.addWidget(self.type_label)
        info_layout.addLayout(type_layout)
        
        # Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        desc_layout.addWidget(self.description_edit)
        info_layout.addLayout(desc_layout)
        
        layout.addLayout(info_layout)
        
        # Propriétés spécifiques
        properties_group = QGroupBox("Propriétés Spécifiques")
        properties_layout = QVBoxLayout(properties_group)
        
        self.properties_edit = QTextEdit()
        self.properties_edit.setPlaceholderText("Propriétés JSON spécifiques à ce type d'élément...")
        properties_layout.addWidget(self.properties_edit)
        
        layout.addWidget(properties_group)
        
        # Boutons de sauvegarde
        save_layout = QHBoxLayout()
        self.save_item_btn = QPushButton("Sauvegarder l'élément")
        self.reset_item_btn = QPushButton("Réinitialiser")
        save_layout.addWidget(self.save_item_btn)
        save_layout.addWidget(self.reset_item_btn)
        layout.addLayout(save_layout)
        
        return widget
        
    def _create_button_bar(self):
        """Crée la barre de boutons en bas"""
        layout = QHBoxLayout()
        
        self.load_strategy_btn = QPushButton("Charger Stratégie")
        self.save_strategy_btn = QPushButton("Sauvegarder Stratégie")
        self.export_strategy_btn = QPushButton("Exporter")
        self.import_strategy_btn = QPushButton("Importer")
        
        layout.addWidget(self.load_strategy_btn)
        layout.addWidget(self.save_strategy_btn)
        layout.addWidget(self.export_strategy_btn)
        layout.addWidget(self.import_strategy_btn)
        layout.addStretch()
        
        return layout
        
    def setup_connections(self):
        """Configure les connexions des signaux"""
        # Connexions des boutons de l'arbre
        self.add_cluster_btn.clicked.connect(self.add_cluster)
        self.add_root_btn.clicked.connect(self.add_root_label)
        self.add_parent_btn.clicked.connect(self.add_parent)
        self.add_child_btn.clicked.connect(self.add_child)
        self.delete_item_btn.clicked.connect(self.delete_item)
        
        # Connexions de l'édition
        self.save_item_btn.clicked.connect(self.save_current_item)
        self.reset_item_btn.clicked.connect(self.reset_current_item)
        
        # Connexions de la stratégie
        self.load_strategy_btn.clicked.connect(self.load_strategy)
        self.save_strategy_btn.clicked.connect(self.save_strategy)
        self.export_strategy_btn.clicked.connect(self.export_strategy)
        self.import_strategy_btn.clicked.connect(self.import_strategy)
        
        # Sélection dans l'arbre
        self.tree_widget.itemSelectionChanged.connect(self.on_item_selected)
        
    def set_database(self, db_path):
        """Définit le chemin de la base de données"""
        self.db_path = db_path
        self.init_database()
        self.load_strategy()
        
    def init_database(self):
        """Initialise les tables de la base de données"""
        if not self.db_path:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table pour les éléments de stratégie
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                parent_id INTEGER,
                description TEXT,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES strategy_items (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def add_cluster(self):
        """Ajoute un nouveau cluster"""
        name, ok = QInputDialog.getText(self, 'Nouveau Cluster', 'Nom du cluster:')
        if ok and name:
            item = QTreeWidgetItem(self.tree_widget)
            item.setText(0, name)
            item.setText(1, "Cluster")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {"type": "cluster", "name": name})
            
    def add_root_label(self):
        """Ajoute un libellé racine"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Cluster":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un cluster")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Libellé Racine', 'Nom du libellé:')
        if ok and name:
            item = QTreeWidgetItem(current)
            item.setText(0, name)
            item.setText(1, "Racine")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {"type": "root", "name": name})
            current.setExpanded(True)
            
    def add_parent(self):
        """Ajoute un élément parent"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) not in ["Racine", "Parent"]:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une racine ou un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Parent', 'Nom du parent:')
        if ok and name:
            item = QTreeWidgetItem(current)
            item.setText(0, name)
            item.setText(1, "Parent")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {"type": "parent", "name": name})
            current.setExpanded(True)
            
    def add_child(self):
        """Ajoute un élément enfant"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Parent":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouvel Enfant', 'Nom de l\'enfant:')
        if ok and name:
            item = QTreeWidgetItem(current)
            item.setText(0, name)
            item.setText(1, "Enfant")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {"type": "child", "name": name})
            current.setExpanded(True)
            
    def delete_item(self):
        """Supprime l'élément sélectionné"""
        current = self.tree_widget.currentItem()
        if not current:
            return
            
        reply = QMessageBox.question(self, 'Confirmer la suppression', 
                                   f'Êtes-vous sûr de vouloir supprimer "{current.text(0)}" ?')
        if reply == QMessageBox.Yes:
            parent = current.parent()
            if parent:
                parent.removeChild(current)
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(current))
                
    def on_item_selected(self):
        """Gère la sélection d'un élément dans l'arbre"""
        current = self.tree_widget.currentItem()
        if not current:
            self._clear_details()
            return
            
        data = current.data(0, Qt.UserRole)
        if data:
            self.name_edit.setText(data.get("name", ""))
            self.type_label.setText(data.get("type", ""))
            self.description_edit.setText(data.get("description", ""))
            self.properties_edit.setText(json.dumps(data.get("properties", {}), indent=2))
            
    def _clear_details(self):
        """Vide les champs de détails"""
        self.name_edit.clear()
        self.type_label.setText("Aucun élément sélectionné")
        self.description_edit.clear()
        self.properties_edit.clear()
        
    def save_current_item(self):
        """Sauvegarde l'élément actuellement sélectionné"""
        current = self.tree_widget.currentItem()
        if not current:
            return
            
        data = current.data(0, Qt.UserRole) or {}
        data["name"] = self.name_edit.text()
        data["description"] = self.description_edit.toPlainText()
        
        try:
            properties_text = self.properties_edit.toPlainText()
            if properties_text.strip():
                data["properties"] = json.loads(properties_text)
            else:
                data["properties"] = {}
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Erreur", "Format JSON invalide dans les propriétés")
            return
            
        current.setData(0, Qt.UserRole, data)
        current.setText(0, data["name"])
        
        QMessageBox.information(self, "Succès", "Élément sauvegardé avec succès")
        
    def reset_current_item(self):
        """Réinitialise les champs de l'élément actuel"""
        self.on_item_selected()
        
    def save_strategy(self):
        """Sauvegarde la stratégie complète dans la base de données"""
        if not self.db_path:
            QMessageBox.warning(self, "Erreur", "Aucune base de données configurée")
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vider la table existante
            cursor.execute("DELETE FROM strategy_items")
            
            # Sauvegarder tous les éléments
            self._save_tree_items(cursor, None, self.tree_widget.invisibleRootItem())
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Succès", "Stratégie sauvegardée avec succès")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
            
    def _save_tree_items(self, cursor, parent_id, parent_item):
        """Sauvegarde récursivement les éléments de l'arbre"""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            data = item.data(0, Qt.UserRole) or {}
            
            cursor.execute('''
                INSERT INTO strategy_items (name, type, parent_id, description, properties)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data.get("name", ""),
                data.get("type", ""),
                parent_id,
                data.get("description", ""),
                json.dumps(data.get("properties", {}))
            ))
            
            item_id = cursor.lastrowid
            item.setText(2, str(item_id))
            
            # Sauvegarder les enfants
            self._save_tree_items(cursor, item_id, item)
            
    def load_strategy(self):
        """Charge la stratégie depuis la base de données"""
        if not self.db_path:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM strategy_items ORDER BY id")
            items = cursor.fetchall()
            
            conn.close()
            
            # Vider l'arbre
            self.tree_widget.clear()
            
            # Reconstruire l'arbre
            items_dict = {}
            for item_data in items:
                item_id, name, item_type, parent_id, description, properties, created_at = item_data
                
                if parent_id is None:
                    # Élément racine
                    tree_item = QTreeWidgetItem(self.tree_widget)
                else:
                    # Élément enfant
                    parent_tree_item = items_dict.get(parent_id)
                    if parent_tree_item:
                        tree_item = QTreeWidgetItem(parent_tree_item)
                        parent_tree_item.setExpanded(True)
                    else:
                        continue
                        
                tree_item.setText(0, name)
                tree_item.setText(1, item_type)
                tree_item.setText(2, str(item_id))
                
                data = {
                    "name": name,
                    "type": item_type,
                    "description": description or "",
                    "properties": json.loads(properties) if properties else {}
                }
                tree_item.setData(0, Qt.UserRole, data)
                
                items_dict[item_id] = tree_item
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement: {str(e)}")
            
    def export_strategy(self):
        """Exporte la stratégie vers un fichier JSON"""
        # À implémenter
        QMessageBox.information(self, "Info", "Fonction d'export à implémenter")
        
    def import_strategy(self):
        """Importe une stratégie depuis un fichier JSON"""
        # À implémenter
        QMessageBox.information(self, "Info", "Fonction d'import à implémenter")
        
    def _get_next_id(self):
        """Génère un ID temporaire pour les nouveaux éléments"""
        import time
        return int(time.time() * 1000) % 1000000
