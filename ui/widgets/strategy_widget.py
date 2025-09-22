from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, 
                             QTextEdit, QGroupBox, QSplitter, QMessageBox, QInputDialog, QFileDialog,
                             QDialog, QDialogButtonBox, QCheckBox, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal
import json
from datetime import datetime

class TypologyDialog(QDialog):
    """Dialogue pour la gestion des typologies"""
    def __init__(self, parent=None, name="", description="", is_hierarchical=False):
        super().__init__(parent)
        self.setWindowTitle("Gestion des Typologies")
        self.setModal(True)
        self.setup_ui(name, description, is_hierarchical)
        
    def setup_ui(self, name, description, is_hierarchical):
        layout = QVBoxLayout(self)
        
        # Nom
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.name_edit = QLineEdit(name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.desc_edit = QTextEdit(description)
        self.desc_edit.setMaximumHeight(100)
        desc_layout.addWidget(self.desc_edit)
        layout.addLayout(desc_layout)
        
        # Hiérarchique
        self.hierarchical_cb = QCheckBox("Structure hiérarchique (taxonomique)")
        self.hierarchical_cb.setChecked(is_hierarchical)
        layout.addWidget(self.hierarchical_cb)
        
        # Boutons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.desc_edit.toPlainText().strip(),
            self.hierarchical_cb.isChecked()
        )


class StrategyWidget(QWidget):
    """
    Widget pour l'onglet Stratégie - Gestion des typologies de contextes
    """
    strategy_saved = pyqtSignal()
    strategy_loaded = pyqtSignal()

    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Gestion des Stratégies et Typologies de Contexte")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Barre de gestion des typologies
        typology_layout = QHBoxLayout()
        typology_layout.addWidget(QLabel("Typologie:"))
        
        self.typology_combo = QComboBox()
        self.typology_combo.setMinimumWidth(200)
        typology_layout.addWidget(self.typology_combo)
        
        self.add_typology_btn = QPushButton("Nouvelle")
        self.edit_typology_btn = QPushButton("Modifier")
        self.delete_typology_btn = QPushButton("Supprimer")
        
        typology_layout.addWidget(self.add_typology_btn)
        typology_layout.addWidget(self.edit_typology_btn)
        typology_layout.addWidget(self.delete_typology_btn)
        typology_layout.addStretch()
        
        layout.addLayout(typology_layout)
        
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
     
    def set_database(self, database):
        """Définit l'objet Database et initialise"""
        self.database = database
        self.load_typologies()
        
    def _create_tree_section(self):
        """Crée la section avec l'arbre des typologies"""
        widget = QGroupBox("Structure Hiérarchique")
        layout = QVBoxLayout(widget)
        
        # Boutons de gestion de l'arbre
        tree_buttons = QHBoxLayout()
        
        # Boutons avec styles améliorés
        self.add_cluster_btn = QPushButton("Cluster")
        self.add_cluster_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_root_btn = QPushButton("Racine")
        self.add_root_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_parent_btn = QPushButton("Parent")
        self.add_parent_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_child_btn = QPushButton("Enfant")
        self.add_child_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.delete_item_btn = QPushButton("Supprimer")
        self.delete_item_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
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
        
        # Boutons avec styles améliorés
        self.load_strategy_btn = QPushButton("Charger Stratégie")
        self.load_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.save_strategy_btn = QPushButton("Sauvegarder Stratégie")
        self.save_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.export_strategy_btn = QPushButton("Exporter")
        self.export_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.import_strategy_btn = QPushButton("Importer")
        self.import_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
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
        
        # Connexions des typologies
        self.add_typology_btn.clicked.connect(self.add_typology)
        self.edit_typology_btn.clicked.connect(self.edit_typology)
        self.delete_typology_btn.clicked.connect(self.delete_typology)
        self.typology_combo.currentIndexChanged.connect(self.on_typology_changed)
        
        # Sélection dans l'arbre
        self.tree_widget.itemSelectionChanged.connect(self.on_item_selected)
        
    def load_typologies(self):
        """Charge la liste des typologies depuis la base de données"""
        if not self.database:
            return
            
        self.typology_combo.clear()
        
        try:
            typologies = self.database.get_typologies()
            
            self.typology_combo.addItem("-- Sélectionnez une typologie --", None)
            
            for typology in typologies:
                display_text = f"{typology['name']} {'(Hiérarchique)' if typology['is_hierarchical'] else ''}"
                self.typology_combo.addItem(display_text, typology['id'])
                
        except Exception as e:
            print(f"Erreur lors du chargement des typologies: {str(e)}")
            self.typology_combo.addItem("-- Erreur de chargement --", None)
            
    def on_typology_changed(self):
        """Gère le changement de typologie sélectionnée"""
        current_typology_id = self.typology_combo.currentData()
        if current_typology_id:
            self.load_strategy()
            
    def add_typology(self):
        """Ajoute une nouvelle typologie"""

        dialog = TypologyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, description, is_hierarchical = dialog.get_data()
            if not name:
                QMessageBox.warning(self, "Erreur", "Le nom de la typologie est obligatoire")
                return
                
            try:
                self.database.add_typology(name, description, is_hierarchical)
                self.load_typologies()
                QMessageBox.information(self, "Succès", f"Typologie '{name}' créée avec succès")
                
            except ValueError as e:
                QMessageBox.warning(self, "Erreur", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")      
                
    def edit_typology(self):
        """Modifie une typologie existante"""
        current_id = self.typology_combo.currentData()
        if not current_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée")
            return
            
        try:
            result = self.database.get_typology_details(current_id)
            
            if result:
                dialog = TypologyDialog(self, result['name'], result['description'], bool(result['is_hierarchical']))
                if dialog.exec_() == QDialog.Accepted:
                    name, description, is_hierarchical = dialog.get_data()
                    if not name:
                        QMessageBox.warning(self, "Erreur", "Le nom de la typologie est obligatoire")
                        return
                        
                    self.database.update_typology(current_id, name, description, is_hierarchical)
                    self.load_typologies()
                    QMessageBox.information(self, "Succès", f"Typologie '{name}' modifiée avec succès")
                    
        except ValueError as e:
            QMessageBox.warning(self, "Erreur", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")
            
    def delete_typology(self):
        """Supprime une typologie"""
        current_id = self.typology_combo.currentData()
        if not current_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée")
            return
            
        try:
            typology_name = self.typology_combo.currentText()
            reply = QMessageBox.question(
                self, "Confirmation", 
                f"Êtes-vous sûr de vouloir supprimer la typologie '{typology_name}' ?"
            )
            
            if reply == QMessageBox.Yes:
                self.database.delete_typology(current_id)
                self.load_typologies()
                QMessageBox.information(self, "Succès", "Typologie supprimée avec succès")
                
        except ValueError as e:
            QMessageBox.warning(self, "Erreur", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")   
            
    def add_cluster(self):
        """Ajoute un nouveau cluster"""
        name, ok = QInputDialog.getText(self, 'Nouveau Cluster', 'Nom du cluster:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), None):
                QMessageBox.warning(self, "Erreur", f"Un cluster nommé '{name.strip()}' existe déjà")
                return
                
            item = QTreeWidgetItem(self.tree_widget)
            item.setText(0, name.strip())
            item.setText(1, "Cluster")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "cluster", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Cluster '{name.strip()}' créé avec succès")
            
    def add_root_label(self):
        """Ajoute un libellé racine"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Cluster":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un cluster")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Libellé Racine', 'Nom du libellé:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un libellé racine nommé '{name.strip()}' existe déjà dans ce cluster")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Racine")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "root", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Libellé racine '{name.strip()}' créé avec succès")
            
    def add_parent(self):
        """Ajoute un élément parent"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) not in ["Racine", "Parent"]:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une racine ou un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Parent', 'Nom du parent:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un parent nommé '{name.strip()}' existe déjà sous cet élément")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Parent")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "parent", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Parent '{name.strip()}' créé avec succès")
            
    def add_child(self):
        """Ajoute un élément enfant"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Parent":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouvel Enfant', 'Nom de l\'enfant:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un enfant nommé '{name.strip()}' existe déjà sous ce parent")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Enfant")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "child", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Enfant '{name.strip()}' créé avec succès")
            
    def delete_item(self):
        """Supprime l'élément sélectionné"""
        current = self.tree_widget.currentItem()
        if not current:
            return
            
        child_count = current.childCount()
        if child_count > 0:
            reply = QMessageBox.question(
                self, 'Confirmer la suppression', 
                f'L\'élément "{current.text(0)}" contient {child_count} enfant(s). ' 
                f'Voulez-vous vraiment le supprimer avec tous ses enfants ?'
            )
        else:
            reply = QMessageBox.question(
                self, 'Confirmer la suppression', 
                f'Êtes-vous sûr de vouloir supprimer "{current.text(0)}" ?'
            )
            
        if reply == QMessageBox.Yes:
            parent = current.parent()
            if parent:
                parent.removeChild(current)
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(current))
            QMessageBox.information(self, "Succès", "Élément supprimé avec succès")
                
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
        new_name = self.name_edit.text().strip()
        
        if new_name != data.get("name", "") and new_name:
            parent = current.parent()
            if self._name_exists_at_level(new_name, parent, exclude_item=current):
                QMessageBox.warning(self, "Erreur", f"Le nom '{new_name}' existe déjà à ce niveau")
                return
        
        data["name"] = new_name
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
        if not self.database:
            QMessageBox.warning(self, "Erreur", "Aucune base de données configurée")
            return
        
        current_typology_id = self.typology_combo.currentData()
        if not current_typology_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée pour la sauvegarde")
            return

        try:
            self.database.clear_strategy_items(current_typology_id)
            self._save_tree_items(None, self.tree_widget.invisibleRootItem(), current_typology_id)
            
            QMessageBox.information(self, "Succès", "Stratégie sauvegardée avec succès")
            self.strategy_saved.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
            
    def _save_tree_items(self, parent_id, parent_item, typology_id):
        """Sauvegarde récursivement les éléments de l'arbre"""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            data = item.data(0, Qt.UserRole) or {}
            
            item_id = self.database.add_strategy_item(
                data.get("name", ""),
                data.get("type", ""),
                parent_id,
                data.get("description", ""),
                json.dumps(data.get("properties", {})),
                typology_id
            )
            
            item.setText(2, str(item_id))
            
            self._save_tree_items(item_id, item, typology_id)
            
    def load_strategy(self):
        """Charge la stratégie depuis la base de données"""
        if not self.database:
            return

        current_typology_id = self.typology_combo.currentData()
        if not current_typology_id:
            self.tree_widget.clear()
            return
            
        try:
            items = self.database.get_strategy_items(current_typology_id)
            
            self.tree_widget.clear()
            
            items_dict = {}
            for item_data in items:
                item_id = item_data['id']
                name = item_data['name']
                item_type = item_data['type']
                parent_id = item_data['parent_id']
                description = item_data['description']
                properties = item_data['properties']

                if parent_id is None:
                    tree_item = QTreeWidgetItem(self.tree_widget)
                else:
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
            
            self.strategy_loaded.emit()
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement: {str(e)}")
            
    def export_strategy(self):
        """Exporte la stratégie vers un fichier JSON"""
        if self.tree_widget.topLevelItemCount() == 0:
            QMessageBox.warning(self, "Erreur", "Aucune stratégie à exporter")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter la stratégie", 
            f"strategie_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                strategy_data = self._export_tree_to_dict()
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(strategy_data, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Succès", f"Stratégie exportée vers {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l\'export: {str(e)}")
        
    def import_strategy(self):
        """Importe une stratégie depuis un fichier JSON"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importer une stratégie", "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)
                
                if not isinstance(strategy_data, dict) or 'items' not in strategy_data:
                    QMessageBox.warning(self, "Erreur", "Format de fichier invalide")
                    return
                
                reply = QMessageBox.question(
                    self, 'Confirmer l\'import',
                    'Cette action remplacera la stratégie actuelle. Continuer ?'
                )
                
                if reply == QMessageBox.Yes:
                    self.tree_widget.clear()
                    self._import_dict_to_tree(strategy_data['items'])
                    QMessageBox.information(self, "Succès", "Stratégie importée avec succès")
                    
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l\'import: {str(e)}")
    
    def _export_tree_to_dict(self):
        """Convertit l'arbre en dictionnaire pour l\'export"""
        strategy_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "items": []
        }
        
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            strategy_data["items"].append(self._export_item_to_dict(item))
            
        return strategy_data
    
    def _export_item_to_dict(self, item):
        """Convertit un élément de l\'arbre en dictionnaire"""
        data = item.data(0, Qt.UserRole) or {}
        item_dict = {
            "name": data.get("name", ""),
            "type": data.get("type", ""),
            "description": data.get("description", ""),
            "properties": data.get("properties", {}),
            "children": []
        }
        
        for i in range(item.childCount()):
            child = item.child(i)
            item_dict["children"].append(self._export_item_to_dict(child))
            
        return item_dict
    
    def _import_dict_to_tree(self, items_data, parent_item=None):
        """Importe les données depuis un dictionnaire vers l\'arbre"""
        for item_data in items_data:
            if parent_item is None:
                tree_item = QTreeWidgetItem(self.tree_widget)
            else:
                tree_item = QTreeWidgetItem(parent_item)
                parent_item.setExpanded(True)
            
            tree_item.setText(0, item_data.get("name", ""))
            tree_item.setText(1, item_data.get("type", ""))
            tree_item.setText(2, str(self._get_next_id()))
            
            data = {
                "name": item_data.get("name", ""),
                "type": item_data.get("type", ""),
                "description": item_data.get("description", ""),
                "properties": item_data.get("properties", {})
            }
            tree_item.setData(0, Qt.UserRole, data)
            
            if "children" in item_data and item_data["children"]:
                self._import_dict_to_tree(item_data["children"], tree_item)
    
    def _name_exists_at_level(self, name, parent_item, exclude_item=None):
        """Vérifie si un nom existe déjà au même niveau hiérarchique"""
        if parent_item is None:
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                if item != exclude_item and item.text(0) == name:
                    return True
        else:
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                if item != exclude_item and item.text(0) == name:
                    return True
        return False
        
    def _get_next_id(self):
        """Génère un ID temporaire pour les nouveaux éléments"""
        import time
        return int(time.time() * 1000) % 1000000
