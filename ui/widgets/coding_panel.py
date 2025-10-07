import os
import json
import uuid
import pyperclip
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.Qsci import (
    QsciScintilla,
    QsciLexerPython,
    QsciLexerCPP,
    QsciLexerJavaScript,
    QsciLexerHTML,
)

from utils.logger import logger
from ui.localization.translator import tr
from ui.widgets.workers.simple_test_worker import SimpleTestWorker
from utils.dgraph_connector import LirisDgraphConnector


class TaxonomyItem(QtWidgets.QTreeWidgetItem):
    """Item pour l'arbre de taxonomie avec métadonnées"""
    def __init__(self, parent, text, item_type="folder", data=None, level=0):
        super().__init__(parent, [text])
        self.item_type = item_type  # "file", "function", "dependency"
        self.item_data = data or {}
        self.level = level
        
        # Icônes selon le type
        if item_type == "file":
            self.setIcon(0, self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))
        elif item_type == "function":
            self.setIcon(0, self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        elif item_type == "dependency":
            self.setIcon(0, self.style().standardIcon(QtWidgets.QStyle.SP_ArrowRight))
    
    def style(self):
        return QtWidgets.QApplication.style()


class TaxonomyDialog(QtWidgets.QDialog):
    """Dialogue pour sélectionner les taxonomies (fichiers/fonctions) avec niveaux"""
    
    def __init__(self, project_data, dgraph_connector, parent=None):
        super().__init__(parent)
        self.project_data = project_data
        self.dgraph_connector = dgraph_connector
        self.selected_items = []
        
        self.setWindowTitle("Définir les Bornes - Taxonomies")
        self.resize(900, 600)
        self.setModal(True)
        
        self._init_ui()
        self._load_taxonomy()
    
    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # En-tête
        header = QtWidgets.QLabel("Sélectionnez les fichiers/fonctions à implémenter")
        header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #A23B2D;
            padding: 10px;
        """)
        layout.addWidget(header)
        
        # Sélecteur de niveau
        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel("Niveau de profondeur:")
        level_label.setStyleSheet("font-weight: bold;")
        
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItem("Niveau 1: Relations directes uniquement", 1)
        self.level_combo.addItem("Niveau 2: Toutes relations + enfants (récursif)", 2)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        layout.addLayout(level_layout)
        
        # Zone principale divisée
        main_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # Arbre de taxonomie (gauche)
        tree_container = QtWidgets.QWidget()
        tree_layout = QtWidgets.QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        
        tree_label = QtWidgets.QLabel("Structure du projet:")
        tree_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        tree_layout.addWidget(tree_label)
        
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.tree_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 8px;
            }
            QTreeWidget::item:selected {
                background-color: #A23B2D;
                color: white;
            }
        """)
        tree_layout.addWidget(self.tree_widget)
        
        main_splitter.addWidget(tree_container)
        
        # Zone de description (droite)
        desc_container = QtWidgets.QWidget()
        desc_layout = QtWidgets.QVBoxLayout(desc_container)
        desc_layout.setContentsMargins(0, 0, 0, 0)
        
        desc_label = QtWidgets.QLabel("Description:")
        desc_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        desc_layout.addWidget(desc_label)
        
        self.description_text = QtWidgets.QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText("Sélectionnez un élément pour voir sa description")
        self.description_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: #F9F6F6;
                padding: 10px;
            }
        """)
        desc_layout.addWidget(self.description_text)
        
        # Liste des sélections
        selected_label = QtWidgets.QLabel("Éléments sélectionnés:")
        selected_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 10px;")
        desc_layout.addWidget(selected_label)
        
        self.selected_list = QtWidgets.QListWidget()
        self.selected_list.setMaximumHeight(120)
        self.selected_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
        """)
        desc_layout.addWidget(self.selected_list)
        
        main_splitter.addWidget(desc_container)
        main_splitter.setSizes([500, 400])
        
        layout.addWidget(main_splitter)
        
        # Boutons d'action
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.validate_button = QtWidgets.QPushButton("Valider la sélection")
        self.validate_button.clicked.connect(self.accept)
        self.validate_button.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35A4A;
            }
        """)
        
        cancel_button = QtWidgets.QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #777;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #999;
            }
        """)
        
        button_layout.addWidget(self.validate_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def _load_taxonomy(self):
        """Charge la taxonomie du projet avec relations"""
        self.tree_widget.clear()
        
        if not self.project_data:
            return
        
        # Parcourir les clusters
        cm = self.project_data.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_item = TaxonomyItem(
                self.tree_widget,
                f"Cluster: {cluster.get('name', 'Cluster')}",
                "file",
                cluster,
                0
            )
            
            # Ajouter les root_labels avec leurs relations
            self._add_labels_with_relations(cluster_item, cluster.get('root_labels', []))
        
        self.tree_widget.expandAll()
    
    def _add_labels_with_relations(self, parent_item, labels):
        """Ajoute les labels avec leurs relations (fonctions, classes, dépendances)"""
        for label in labels:
            label_name = label.get('name', label.get('label', 'Item'))
            
            # Déterminer le type
            if self._has_extension(label_name):
                item_type = "file"
                icon = "File"
            else:
                item_type = "function"
                icon = "Func"
            
            label_item = TaxonomyItem(
                parent_item,
                f"{icon}: {label_name}",
                item_type,
                label,
                0
            )
            
            # Ajouter les fonctions du fichier/label
            functions = label.get('functions', [])
            for func in functions:
                func_name = func.get('name', 'function')
                func_item = TaxonomyItem(
                    label_item,
                    f"Func: {func_name}",
                    "function",
                    func,
                    0
                )
            
            # Parcourir récursivement les parents et children
            if label.get('parents'):
                self._add_labels_with_relations(label_item, label['parents'])
            if label.get('children'):
                self._add_labels_with_relations(label_item, label['children'])
    
    def _has_extension(self, filename):
        """Vérifie si le nom a une extension de fichier"""
        return bool(os.path.splitext(filename)[1])
    
    def _on_level_changed(self, index):
        """Gère le changement de niveau"""
        selected_level = self.level_combo.currentData()
        
        if selected_level == 1:
            logger.info("Niveau 1 sélectionné : Relations directes uniquement")
        else:
            logger.info("Niveau 2 sélectionné : Toutes relations + enfants (récursif)")
        
        self._update_selection_display()
    
    def _update_selection_display(self):
        """Met à jour l'affichage"""
        pass
    
    def _on_selection_changed(self):
        """Gère le changement de sélection - Charge dynamiquement les relations"""
        selected_items = self.tree_widget.selectedItems()
        
        if not selected_items:
            self.description_text.clear()
            self.selected_list.clear()
            return
        
        # Afficher la description du dernier item sélectionné
        last_item = selected_items[-1]
        if isinstance(last_item, TaxonomyItem):
            data = last_item.item_data
            selected_level = self.level_combo.currentData()
            
            # Charger les relations selon le niveau
            related_items = self._get_related_items(data, selected_level)
            
            desc = data.get('description', 'Aucune description disponible')
            
            desc_html = f"""
            <b>Élément:</b> {data.get('name', data.get('label', 'N/A'))}<br>
            <b>Type:</b> {last_item.item_type}<br>
            <b>Niveau sélectionné:</b> {selected_level}<br><br>
            <b>Description:</b><br>
            {desc}<br><br>
            """
            
            # Afficher les relations
            if related_items:
                desc_html += f"<b>Éléments liés (Niveau {selected_level}):</b><br>"
                desc_html += "<ul>"
                for rel in related_items[:10]:  # Limiter à 10 pour l'aperçu
                    desc_html += f"<li>{rel['name']} ({rel['type']})</li>"
                desc_html += "</ul>"
                if len(related_items) > 10:
                    desc_html += f"<i>... et {len(related_items) - 10} autre(s)</i>"
                
                # Log pour tracer (nouveau)
                if selected_level == 2:
                    logger.info(f"Niveau 2 - Récupéré {len(related_items)} relations pour '{data.get('name', 'N/A')}' (incl. enfants et importations)")
            
            self.description_text.setHtml(desc_html)
        
        # Mettre à jour la liste des sélections
        self.selected_list.clear()
        for item in selected_items:
            if isinstance(item, TaxonomyItem):
                name = item.item_data.get('name', item.item_data.get('label', 'Item'))
                self.selected_list.addItem(f"- {name}")
        
        self.selected_items = selected_items
    
    def _get_related_items(self, data, level):
        """
        Récupère les éléments liés selon le niveau
        Niveau 1: Fonctions/classes directement liées (appels directs, pas de récursion)
        Niveau 2: Tous les fichiers/classes/fonctions enfants + toutes relations (imports, dépendances, héritage, etc.)
        """
        related = []
        
        if level == 1:
            # Niveau 1: Relations DIRECTES uniquement (pas de récursion)
            
            # 1. Fonctions définies dans cet élément
            functions = data.get('functions', [])
            for func in functions:
                related.append({
                    'name': func.get('name', 'function'),
                    'type': 'fonction',
                    'data': func
                })
                
                # Fonctions appelées par cette fonction (appels directs)
                calls = func.get('calls', [])
                for call in calls:
                    related.append({
                        'name': call.get('name', 'call'),
                        'type': 'appel direct',
                        'data': call
                    })
            
            # 2. Relations directes (sans récursion)
            relations = data.get('relations', [])
            for rel in relations:
                related.append({
                    'name': rel.get('name', 'relation'),
                    'type': rel.get('relationType', 'relation'),
                    'data': rel
                })
            
            # 3. Imports directs
            imports = data.get('imports', [])
            for imp in imports:
                related.append({
                    'name': imp.get('name', 'import'),
                    'type': 'import',
                    'data': imp
                })
            
            # 4. Relations inverses directes
            reverse_calls = data.get('~calls', [])
            for rcall in reverse_calls:
                related.append({
                    'name': rcall.get('name', 'caller'),
                    'type': 'appelant',
                    'data': rcall
                })
            
            reverse_relations = data.get('~relations', [])
            for rrel in reverse_relations:
                related.append({
                    'name': rrel.get('name', 'related_from'),
                    'type': 'relation inverse',
                    'data': rrel
                })
        
        elif level == 2:
            # Niveau 2: TOUT le graphe (récursif) - enfants + toutes relations
            visited = set()
            self._collect_all_relations_recursive(data, related, visited)
        
        return related
    
    def _collect_all_relations_recursive(self, data, collected, visited):
        """
        Collecte récursivement TOUS les éléments liés:
        - Enfants (children/parents dans la hiérarchie)
        - Fonctions et leurs appels
        - Imports/dépendances
        - Toutes relations (héritage, composition, etc.)
        """
        # Identifier l'élément pour éviter les boucles infinies
        item_id = data.get('id', data.get('uid', str(data)))
        
        if item_id in visited:
            return
        visited.add(item_id)
        
        # 1. Fonctions et leurs appels (récursif)
        functions = data.get('functions', [])
        for func in functions:
            func_id = func.get('id', func.get('uid', func.get('name', '')))
            if func_id not in visited:
                collected.append({
                    'name': func.get('name', 'function'),
                    'type': 'fonction',
                    'data': func
                })
                visited.add(func_id)
                
                # Appels de fonction (récursif)
                calls = func.get('calls', [])
                for call in calls:
                    call_id = call.get('id', call.get('uid', call.get('name', '')))
                    if call_id not in visited:
                        collected.append({
                            'name': call.get('name', 'call'),
                            'type': 'appel',
                            'data': call
                        })
                        # Récursion sur l'appel pour trouver ses dépendances
                        self._collect_all_relations_recursive(call, collected, visited)
        
        # 2. Imports/dépendances
        imports = data.get('imports', [])
        for imp in imports:
            imp_id = imp.get('id', imp.get('uid', imp.get('name', '')))
            if imp_id not in visited:
                collected.append({
                    'name': imp.get('name', 'import'),
                    'type': 'import',
                    'data': imp
                })
                visited.add(imp_id)
                # Récursion sur l'import
                self._collect_all_relations_recursive(imp, collected, visited)
        
        # 3. Relations (héritage, composition, dépendances, etc.)
        relations = data.get('relations', [])
        for rel in relations:
            rel_id = rel.get('id', rel.get('uid', str(rel)))
            if rel_id not in visited:
                collected.append({
                    'name': rel.get('name', 'relation'),
                    'type': rel.get('relationType', 'relation'),
                    'data': rel
                })
                # Récursion sur la relation
                self._collect_all_relations_recursive(rel, collected, visited)
        
        # 4. Enfants dans la hiérarchie (parents dans le graphe inversé)
        parents = data.get('parents', [])
        for parent in parents:
            parent_id = parent.get('id', parent.get('uid', str(parent)))
            if parent_id not in visited:
                collected.append({
                    'name': parent.get('name', 'parent'),
                    'type': 'enfant hiérarchique',
                    'data': parent
                })
                # Récursion sur le parent
                self._collect_all_relations_recursive(parent, collected, visited)
        
        # 5. Enfants directs
        children = data.get('children', [])
        for child in children:
            child_id = child.get('id', child.get('uid', str(child)))
            if child_id not in visited:
                collected.append({
                    'name': child.get('name', 'child'),
                    'type': 'enfant',
                    'data': child
                })
                # Récursion sur l'enfant
                self._collect_all_relations_recursive(child, collected, visited)
        
        # 6. Fichiers liés
        files = data.get('files', [])
        for file_path in files:
            if isinstance(file_path, str):
                collected.append({
                    'name': file_path,
                    'type': 'fichier',
                    'data': {'path': file_path}
                })
        
        # 7. Reverse relations (~calls, ~relations depuis dgraph)
        reverse_calls = data.get('~calls', [])
        for rcall in reverse_calls:
            rcall_id = rcall.get('id', rcall.get('uid', str(rcall)))
            if rcall_id not in visited:
                collected.append({
                    'name': rcall.get('name', 'caller'),
                    'type': 'appelant (inverse)',
                    'data': rcall
                })
                self._collect_all_relations_recursive(rcall, collected, visited)
        
        reverse_relations = data.get('~relations', [])
        for rrel in reverse_relations:
            rrel_id = rrel.get('id', rrel.get('uid', str(rrel)))
            if rrel_id not in visited:
                collected.append({
                    'name': rrel.get('name', 'related_from'),
                    'type': 'relation inverse',
                    'data': rrel
                })
                self._collect_all_relations_recursive(rrel, collected, visited)
    
    def get_selected_taxonomy(self):
        """Retourne les taxonomies sélectionnées avec leurs relations selon le niveau"""
        taxonomy_data = []
        selected_level = self.level_combo.currentData()
        
        for item in self.selected_items:
            if isinstance(item, TaxonomyItem):
                data = item.item_data
                
                # Collecter les relations selon le niveau
                related_items = self._get_related_items(data, selected_level)
                
                taxonomy_data.append({
                    'name': data.get('name', data.get('label', '')),
                    'type': item.item_type,
                    'level': selected_level,
                    'data': data,
                    'related': related_items
                })
                
                # Log pour tracer (nouveau)
                if selected_level == 2:
                    logger.info(f"Taxonomie sélectionnée - Niveau 2: {len(related_items)} relations pour '{data.get('name', 'N/A')}' (incl. enfants, importations et toutes relations)")
        
        return taxonomy_data


class CodingPanel(QtWidgets.QWidget):
    """Widget pour les sessions du coding multi-IA"""

    # Signaux
    session_started = pyqtSignal(int)
    session_completed = pyqtSignal(int)
    session_failed = pyqtSignal(int, str)
    export_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.conductor = None
        self.profiles = {}
        self.running_workers = []
        self.current_session_id = None
        self.orchestrator = None
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.current_project_data = None
        self.selected_taxonomy = []

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"
        self.accent_color = "#E8E0DF"

        self._init_style()
        self._init_ui()
        self._update_ui_texts()
        self._load_projects_list()

    def _init_style(self):
        """Configure le style global du widget"""
        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QGroupBox {{
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            margin-top: 1.2em;
            padding: 15px;
            background-color: white;
            font-weight: bold;
            font-size: 14px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px;
            color: {self.primary_color};
        }}

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
            min-width: 100px;
        }}

        QPushButton:hover {{
            background-color: {self.secondary_color};
        }}

        QPushButton:pressed {{
            background-color: #922E23;
        }}

        QPushButton:disabled {{
            background-color: #CCCCCC;
            color: #888;
        }}

        QLineEdit, QComboBox {{
            padding: 8px 12px;
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            background-color: white;
            font-size: 13px;
        }}

        QLineEdit:focus, QComboBox:focus {{
            border: 2px solid {self.primary_color};
        }}

        QTextEdit {{
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            padding: 12px;
            background-color: white;
            font-size: 14px;
        }}

        QTextEdit:focus {{
            border: 2px solid {self.primary_color};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {self.text_color};
            margin-right: 10px;
        }}

        QTableWidget {{
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            background-color: white;
            gridline-color: #E0E0E0;
        }}

        QTableWidget::item {{
            padding: 8px;
        }}

        QTableWidget::item:selected {{
            background-color: {self.primary_color};
            color: white;
        }}

        QHeaderView::section {{
            background-color: {self.primary_color};
            color: white;
            padding: 10px;
            border: none;
            font-weight: bold;
            font-size: 12px;
        }}

        QProgressBar {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            text-align: center;
            background-color: #F0F0F0;
            height: 20px;
        }}

        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 4px;
        }}
        """
        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ===== COLONNE GAUCHE: Paramètres =====
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(12)

        # En-tête
        self.title_label = QtWidgets.QLabel("Coding Multi-IA")
        self.title_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {self.primary_color};
            padding: 8px 0;
        """)
        left_column.addWidget(self.title_label)

        # Groupe paramètres
        self.session_group = QtWidgets.QGroupBox("Paramètres de Session")
        session_layout = QtWidgets.QVBoxLayout(self.session_group)
        session_layout.setSpacing(10)
        session_layout.setContentsMargins(10, 18, 10, 10)

        # Sélection du projet
        project_label = QtWidgets.QLabel("Projet:")
        project_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        session_layout.addWidget(project_label)
        session_layout.addWidget(self.project_combo)
        
        # Plateforme IA
        platform_label = QtWidgets.QLabel("Plateforme IA:")
        platform_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.platforms_combo = QtWidgets.QComboBox()
        session_layout.addWidget(platform_label)
        session_layout.addWidget(self.platforms_combo)

        # Contexte/Fonctionnalité
        context_label = QtWidgets.QLabel("Contexte (Fonctionnalité souhaitée):")
        context_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        session_layout.addWidget(context_label)
        
        self.context_edit = QtWidgets.QTextEdit()
        self.context_edit.setPlaceholderText("Décrivez la fonctionnalité à implémenter...")
        self.context_edit.setMinimumHeight(150)
        session_layout.addWidget(self.context_edit)

        # Bouton Bornes/Taxonomie
        self.taxonomy_button = QtWidgets.QPushButton("Définir les Bornes")
        self.taxonomy_button.clicked.connect(self._on_define_taxonomy)
        self.taxonomy_button.setEnabled(False)
        self.taxonomy_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.secondary_color};
                padding: 8px 16px;
            }}
        """)
        session_layout.addWidget(self.taxonomy_button)

        # Affichage des taxonomies sélectionnées
        self.taxonomy_label = QtWidgets.QLabel("Aucune borne définie")
        self.taxonomy_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        self.taxonomy_label.setWordWrap(True)
        session_layout.addWidget(self.taxonomy_label)

        # Boutons d'action
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.start_button = QtWidgets.QPushButton("Démarrer")
        self.start_button.clicked.connect(self._on_start_session)
        buttons_layout.addWidget(self.start_button)

        self.export_button = QtWidgets.QPushButton("Export")
        self.export_button.clicked.connect(self._on_export_results)
        self.export_button.setEnabled(False)
        buttons_layout.addWidget(self.export_button)

        session_layout.addLayout(buttons_layout)
        session_layout.addStretch()
        
        left_column.addWidget(self.session_group)
        
        # Statut
        status_container = QtWidgets.QVBoxLayout()
        status_container.setSpacing(6)
        
        self.status_label = QtWidgets.QLabel("Prêt")
        self.status_label.setStyleSheet(f"""
            color: {self.primary_color}; 
            font-weight: bold;
            font-size: 11px;
            padding: 4px;
        """)
        status_container.addWidget(self.status_label)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(18)
        status_container.addWidget(self.progress_bar)
        
        left_column.addLayout(status_container)

        # ===== COLONNE DROITE: Résultats =====
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)

        self.results_group = QtWidgets.QGroupBox("Résultats")
        results_layout = QtWidgets.QVBoxLayout(self.results_group)
        results_layout.setSpacing(8)
        results_layout.setContentsMargins(10, 18, 10, 10)

        self.solutions_table = QtWidgets.QTableWidget()
        self.solutions_table.setColumnCount(2)
        self.solutions_table.setHorizontalHeaderLabels(["Plateforme", "Solution"])
        self.solutions_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )
        self.solutions_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.solutions_table.verticalHeader().setVisible(False)
        self.solutions_table.setAlternatingRowColors(True)
        self.solutions_table.cellDoubleClicked.connect(self._on_solution_double_clicked)
        results_layout.addWidget(self.solutions_table)

        right_column.addWidget(self.results_group)

        # Ajouter les colonnes
        main_layout.addLayout(left_column, 1)
        main_layout.addLayout(right_column, 2)

    def _load_projects_list(self):
        """Charge la liste des projets depuis Dgraph. MODIFIÉ : Utilise query_full_context pour charger toutes les relations dès le départ."""
        if not self.dgraph_connector.client:
            if not self.dgraph_connector.connect():
                logger.warning("Cannot connect to Dgraph")
                return
        
        query_result = self.dgraph_connector.query_full_context()  # Changé : charge full context avec relations
        if not query_result or not query_result.get('q'):
            logger.info("No projects found in Dgraph")
            return
        
        self.project_combo.clear()
        self.project_combo.addItem("Sélectionnez un projet...", None)
        
        seen_projects = set()
        for workspace in query_result['q']:
            project_name = workspace.get('name', '')
            if project_name and project_name not in seen_projects:
                seen_projects.add(project_name)
                self.project_combo.addItem(f"Projet: {project_name}", workspace)
        
        logger.info(f"Loaded {len(seen_projects)} projects with full relations context")

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet"""
        if index <= 0:
            self.current_project_data = None
            self.taxonomy_button.setEnabled(False)
            self.selected_taxonomy = []
            self.taxonomy_label.setText("Aucune borne définie")
            return
        
        self.current_project_data = self.project_combo.currentData()
        self.taxonomy_button.setEnabled(True)
        logger.info(f"Selected project: {self.current_project_data.get('name')} (full data loaded)")

    def _on_define_taxonomy(self):
        """Ouvre le dialogue de définition des taxonomies"""
        if not self.current_project_data:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun projet",
                "Veuillez d'abord sélectionner un projet."
            )
            return
        
        dialog = TaxonomyDialog(self.current_project_data, self.dgraph_connector, self)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.selected_taxonomy = dialog.get_selected_taxonomy()
            
            if self.selected_taxonomy:
                count = len(self.selected_taxonomy)
                level = self.selected_taxonomy[0]['level'] if self.selected_taxonomy else 1
                
                total_items = count
                for tax in self.selected_taxonomy:
                    total_items += len(tax.get('related', []))
                
                names = [t['name'] for t in self.selected_taxonomy[:3]]
                display = ", ".join(names)
                if count > 3:
                    display += f" et {count - 3} autre(s)"
                
                self.taxonomy_label.setText(
                    f"{count} borne(s) [Niveau {level}]: {display}\n"
                    f"Total: {total_items} éléments (avec relations)"
                )
                self.taxonomy_label.setStyleSheet("font-size: 11px; color: #A23B2D; font-weight: bold;")
                logger.info(f"Selected {count} taxonomy items with {total_items} total elements")
            else:
                self.taxonomy_label.setText("Aucune borne définie")
                self.taxonomy_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")

    def _on_start_session(self):
        """Lance une session de coding"""
        if not self.conductor:
            self.update_status("Erreur: Conductor non initialisé", 0)
            return

        if self.platforms_combo.currentIndex() == 0:
            self.update_status("Erreur: Sélectionnez une plateforme", 0)
            return

        test_message = self.context_edit.toPlainText().strip()
        if not test_message:
            self.update_status("Erreur: Décrivez le contexte", 0)
            return

        if self.selected_taxonomy:
            taxonomy_info = "\n\n=== BORNES DÉFINIES ===\n"
            taxonomy_info += f"Niveau de profondeur: {self.selected_taxonomy[0]['level']}\n\n"
            
            for item in self.selected_taxonomy:
                taxonomy_info += f"Element: {item['name']} ({item['type']})\n"
                
                related = item.get('related', [])
                if related:
                    taxonomy_info += f"   Relations ({len(related)}):\n"
                    for rel in related[:20]:
                        taxonomy_info += f"   - {rel['name']} ({rel['type']})\n"
                    if len(related) > 20:
                        taxonomy_info += f"   ... et {len(related) - 20} autre(s)\n"
                taxonomy_info += "\n"
            
            test_message += taxonomy_info
            logger.info(f"Taxonomies ajoutées au message: {len(self.selected_taxonomy)} bornes")

        platform_name = self.platforms_combo.currentData()
        if platform_name not in self.profiles:
            self.update_status("Erreur: Profil plateforme introuvable", 0)
            return

        selected_platforms = [(platform_name, self.profiles[platform_name])]

        self.solutions_table.setRowCount(0)
        self.update_status("Démarrage de la session...", 0)
        self.start_button.setEnabled(False)
        self.export_button.setEnabled(False)

        self.running_workers = []
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.current_worker_index = -1

        for i, (platform_name, platform_profile) in enumerate(selected_platforms):
            detected_browser_type = platform_profile.get("browser", {}).get("type", "chrome")

            worker = SimpleTestWorker(
                self.conductor, platform_profile, test_message, detected_browser_type
            )
            worker.platform_name = platform_name
            worker.platform_index = i

            worker.test_completed.connect(self._on_test_completed)
            worker.step_update.connect(self._on_step_update)
            worker.debug_info.connect(self._on_debug_info)
            worker.finished.connect(self._on_worker_finished)

            self.running_workers.append(worker)

        self._start_next_worker()
        self.session_started.emit(len(selected_platforms))

    def _start_next_worker(self):
        """Démarre le worker suivant dans la séquence"""
        self.current_worker_index += 1
        if self.current_worker_index < len(self.running_workers):
            worker = self.running_workers[self.current_worker_index]
            logger.info(
                f"Starting test for platform: {worker.platform_name} "
                f"(Worker {self.current_worker_index + 1}/{len(self.running_workers)})"
            )
            worker.start()
        else:
            logger.info("All test workers have completed.")

    def _on_worker_finished(self):
        """Appelé quand un worker a terminé"""
        sender_worker = self.sender()
        logger.info(f"Worker for platform {sender_worker.platform_name} finished.")
        self._start_next_worker()

    def _on_step_update(self, step_name, message):
        """Mise à jour des étapes du test"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        self.update_status(f"[{platform_name}] {message}")

    def _on_debug_info(self, message):
        """Information de débogage"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        logger.debug(f"[{platform_name} DEBUG] {message}")

    def _on_test_completed(self, success, message, duration, response):
        """Gère la complétion d'un test"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        platform_index = getattr(sender_worker, "platform_index", 0)

        logger.info(
            f"Test for {platform_name} completed. "
            f"Success: {success}, Duration: {duration:.2f}s"
        )

        row_position = self.solutions_table.rowCount()
        self.solutions_table.insertRow(row_position)

        platform_item = QtWidgets.QTableWidgetItem(platform_name)
        platform_item.setTextAlignment(Qt.AlignCenter)
        self.solutions_table.setItem(row_position, 0, platform_item)

        preview = response[:80] + "..." if len(response) > 80 else response
        self.solutions_table.setItem(
            row_position, 1, QtWidgets.QTableWidgetItem(preview)
        )

        current_progress = (platform_index + 1) * 100
        self.progress_bar.setValue(current_progress)

        self._check_all_workers_finished()

    def _check_all_workers_finished(self):
        """Vérifie si tous les workers ont terminé"""
        if self.current_worker_index >= len(self.running_workers) - 1:
            self.update_status("Session terminée", 100)
            self.start_button.setEnabled(True)
            self.export_button.setEnabled(True)
            if self.current_session_id:
                self.session_completed.emit(self.current_session_id)
            logger.info("All code tests completed.")

    def _on_export_results(self):
        """Exporte les résultats de la session"""
        logger.info("Export results button clicked.")
        
        project_name = ""
        if self.project_combo.currentIndex() > 0:
            project_name = self.current_project_data.get('name', 'project')
        
        session_name = project_name if project_name else "coding_results"
        self.export_requested.emit(session_name)
        
        QtWidgets.QMessageBox.information(
            self, 
            "Export", 
            f"Résultats exportés pour: {session_name}"
        )

    def _on_solution_double_clicked(self, row, column):
        """Affiche le contenu complet de la solution"""
        if column == 1:
            item = self.solutions_table.item(row, column)
            solution_text = item.text() if item else "(aucune solution)"
            platform_item = self.solutions_table.item(row, 0)
            platform_name = platform_item.text() if platform_item else "Unknown"

            detail_dialog = QtWidgets.QDialog(self)
            detail_dialog.setWindowTitle(f"Solution de {platform_name}")
            detail_dialog.resize(900, 650)

            detail_layout = QtWidgets.QVBoxLayout(detail_dialog)
            detail_layout.setContentsMargins(20, 20, 20, 20)
            detail_layout.setSpacing(15)

            header_label = QtWidgets.QLabel(f"<b>Solution de {platform_name}</b>")
            header_label.setStyleSheet(f"""
                font-size: 16px;
                color: {self.primary_color};
                padding: 10px;
                background-color: {self.background_color};
                border-radius: 6px;
            """)
            detail_layout.addWidget(header_label)

            code_viewer = QsciScintilla()
            code_viewer.setUtf8(True)
            code_viewer.setReadOnly(True)
            code_viewer.setText(solution_text)

            lexer = self._get_lexer_for_solution(solution_text)
            code_font = QtGui.QFont("Consolas", 11)

            if lexer:
                lexer.setDefaultFont(code_font)
                code_viewer.setLexer(lexer)

            fontmetrics = QtGui.QFontMetrics(code_font)
            code_viewer.setMarginWidth(0, fontmetrics.width("00000") + 8)
            code_viewer.setMarginLineNumbers(0, True)
            code_viewer.setMarginsBackgroundColor(QtGui.QColor("#f5f5f5"))
            code_viewer.setMarginsForegroundColor(QtGui.QColor("#666666"))
            code_viewer.setMarginsFont(code_font)

            code_viewer.setCaretLineVisible(True)
            code_viewer.setCaretLineBackgroundColor(QtGui.QColor("#f0f8ff"))

            detail_layout.addWidget(code_viewer)

            button_layout = QtWidgets.QHBoxLayout()
            button_layout.addStretch()

            copy_button = QtWidgets.QPushButton("Copier")
            copy_button.clicked.connect(lambda: self._copy_to_clipboard(solution_text))
            copy_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.primary_color};
                    padding: 10px 20px;
                }}
            """)
            button_layout.addWidget(copy_button)

            close_button = QtWidgets.QPushButton("Fermer")
            close_button.clicked.connect(detail_dialog.close)
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: #777;
                    padding: 10px 20px;
                }
            """)
            button_layout.addWidget(close_button)

            detail_layout.addLayout(button_layout)

            detail_dialog.exec_()

    def _copy_to_clipboard(self, text):
        """Copie le texte dans le presse-papier"""
        try:
            pyperclip.copy(text)
            QtWidgets.QMessageBox.information(
                self,
                "Copié",
                "Le code a été copié dans le presse-papier !"
            )
        except Exception as e:
            logger.error(f"Erreur lors de la copie: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de copier: {str(e)}"
            )

    def _get_lexer_for_solution(self, text):
        """Détermine le lexer approprié selon le contenu"""
        text_lower = text.lower()
        
        if "def " in text_lower or "import " in text_lower or "class " in text_lower:
            return QsciLexerPython()
        
        if "#include" in text_lower or "std::" in text_lower or "cout" in text_lower:
            return QsciLexerCPP()
        
        if ("function" in text_lower or "const " in text_lower or "let " in text_lower) and "{" in text_lower:
            return QsciLexerJavaScript()
        
        if "<!doctype" in text_lower or "<html" in text_lower or "<div" in text_lower:
            return QsciLexerHTML()
        
        return QsciLexerPython()

    def set_conductor(self, conductor):
        """Définit le chef d'orchestre"""
        self.conductor = conductor
        if hasattr(conductor, "modules") and hasattr(
            conductor.modules, "brainstorming_orchestrator"
        ):
            self.orchestrator = conductor.modules.brainstorming_orchestrator
        else:
            try:
                from modules.brainstorming.orchestrator import BrainstormingOrchestrator

                self.orchestrator = BrainstormingOrchestrator(
                    conductor, conductor.database
                )
                logger.info("Orchestrateur de Coding initialisé manuellement")
            except Exception as e:
                logger.error(
                    f"Impossible d'initialiser l'orchestrateur de coding: {str(e)}"
                )

    def set_platforms(self, profiles=None):
        """Définit la liste des profils de plateformes disponibles"""
        self.platforms_combo.clear()
        self.platforms_combo.addItem("Sélectionnez une plateforme IA", "")
        ai_platforms = ["claud ai", "chatgpt", "grok", "gemini"]
        
        for name in ai_platforms:
            self.platforms_combo.addItem(name.title(), name)
        
        logger.info("Loaded AI platforms: claud ai, chatgpt, grok, gemini.")

    def update_status(self, message, progress=None):
        """Met à jour le statut de la session"""
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)

    def new_session(self):
        """Crée une nouvelle session"""
        self.project_combo.setCurrentIndex(0)
        self.context_edit.clear()
        self.platforms_combo.setCurrentIndex(0)
        self.selected_taxonomy = []
        self.taxonomy_label.setText("Aucune borne définie")
        self.solutions_table.setRowCount(0)
        self.current_session_id = None
        self.export_button.setEnabled(False)
        self.update_status("Nouvelle session créée")

    def load_file(self, file_path):
        """Charge une session depuis un fichier"""
        try:
            if not file_path.lower().endswith((".json", ".txt", ".py", ".js", ".cpp", ".java")):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Format non supporté",
                    "Le format de fichier n'est pas supporté.",
                )
                return
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.context_edit.setPlainText(content)
            self.update_status(f"Fichier chargé: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Erreur chargement fichier: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de chargement",
                f"Impossible de charger le fichier: {str(e)}",
            )

    def _update_ui_texts(self):
        """Met à jour les textes de l'interface pour la traduction"""
        pass