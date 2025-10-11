import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import sqlite3
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout, QPlainTextEdit, QListWidgetItem, QHBoxLayout, QLabel, QComboBox, QPushButton, QInputDialog, QMessageBox
from collections import defaultdict
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector
from utils.multi_language_parser import (
    MultiLanguageDependencyParser, 
    ProjectStructureScanner,
    normalize_node_name,
    is_supported_file
)


class AddEditItemDialog(QDialog):
    """
    Dialogue générique pour ajouter/éditer un item avec nom et description.
    """
    def __init__(self, title, current_name="", current_description="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 200)

        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Nom de l'item...")
        self.name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.description_edit = QTextEdit(current_description)
        self.description_edit.setPlaceholderText("Description de l'item...")
        self.description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.description_edit.setMaximumHeight(100)

        layout = QFormLayout(self)
        layout.addRow("Nom:", self.name_edit)
        layout.addRow("Description:", self.description_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip()
        }

class RelationsConfig(QtWidgets.QWidget):
    """
    Widget pour configurer les relations d'import pour un niveau de hiérarchie spécifique.
    Version corrigée avec logique source/target cohérente et affichage tableau.
    """
    def __init__(self, parent_widget, level="global"):
        super().__init__()
        self.parent_widget = parent_widget
        self.level = level
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QtWidgets.QLabel(f"Relations {self.level.capitalize()}")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: black;
        """)
        layout.addWidget(title)

        # Tableau Source/Target (horizontal, sans bordure)
        table_layout = QHBoxLayout()
        table_layout.setSpacing(20)

        # Colonne Source
        source_container = QVBoxLayout()
        source_header = QLabel("Source")
        source_header.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #333;
            padding: 5px;
        """)
        source_container.addWidget(source_header)

        self.source_label = QLabel("Aucun sélectionné")
        self.source_label.setStyleSheet("""
            color: black;
            font-weight: bold;
            padding: 8px;
            background-color: #f2f2f2;
            border-radius: 4px;
            min-width: 150px;
        """)
        self.source_label.setAlignment(Qt.AlignCenter)
        source_container.addWidget(self.source_label)

        # Flèche
        arrow_container = QVBoxLayout()
        arrow_container.addWidget(QLabel(""))  # Spacer pour header
        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #666;
            padding: 8px;
        """)
        arrow_label.setAlignment(Qt.AlignCenter)
        arrow_container.addWidget(arrow_label)

        # Colonne Target
        target_container = QVBoxLayout()
        target_header = QLabel("Target")
        target_header.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #333;
            padding: 5px;
        """)
        target_container.addWidget(target_header)

        self.target_label = QLabel("—")
        self.target_label.setStyleSheet("""
            color: black;
            font-weight: bold;
            padding: 8px;
            background-color: #f2f2f2;
            border-radius: 4px;
            min-width: 150px;
        """)
        self.target_label.setAlignment(Qt.AlignCenter)
        target_container.addWidget(self.target_label)

        table_layout.addLayout(source_container)
        table_layout.addLayout(arrow_container)
        table_layout.addLayout(target_container)
        table_layout.addStretch()

        layout.addLayout(table_layout)

        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet("background-color: #ccc; max-height: 1px;")
        layout.addWidget(separator)

        # Liste des relations
        relations_label_layout = QHBoxLayout()
        relations_label = QtWidgets.QLabel("Relations :")
        relations_label.setStyleSheet("color: black; font-weight: bold;")
        relations_label_layout.addWidget(relations_label)
        relations_label_layout.addStretch()
        layout.addLayout(relations_label_layout)

        self.relations_list = QtWidgets.QListWidget()
        self.relations_list.setMaximumHeight(200)
        self.relations_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.relations_list.currentItemChanged.connect(self._on_relation_selected)
        self.relations_list.setStyleSheet("""
            QListWidget {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                color: black;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #dcdcdc;
            }
            QListWidget::item:hover {
                background-color: #eaeaea;
            }
        """)
        layout.addWidget(self.relations_list)

        # Boutons d’action
        buttons_layout = QHBoxLayout()

        button_style = """
            QPushButton {
                background-color: #f2f2f2;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

        self.add_button = QtWidgets.QPushButton("Nouvelle relation")
        self.add_button.setStyleSheet(button_style)
        self.add_button.setMaximumWidth(150)
        self.add_button.clicked.connect(self._on_add_new_relation)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QtWidgets.QPushButton("Modifier")
        self.edit_button.setStyleSheet(button_style)
        self.edit_button.setMaximumWidth(100)
        self.edit_button.clicked.connect(self._on_edit)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QtWidgets.QPushButton("Supprimer")
        self.remove_button.setStyleSheet(button_style)
        self.remove_button.setMaximumWidth(100)
        self.remove_button.clicked.connect(self._on_remove)
        buttons_layout.addWidget(self.remove_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

    def _on_relation_selected(self, current):
        """Gère la sélection d'une relation pour afficher source/target."""
        if not current:
            self.target_label.setText("—")
            return
        
        rel = current.data(Qt.UserRole)
        if not rel:
            return
        
        # Récupérer les infos source et target
        source_uid = rel.get('source')
        target_uid = rel.get('target')
        
        source_info = self.parent_widget.label_uid_to_info.get(source_uid, {})
        target_info = self.parent_widget.label_uid_to_info.get(target_uid, {})
        
        source_name = source_info.get('name', source_info.get('label', 'Inconnu'))
        target_name = target_info.get('name', target_info.get('label', 'Inconnu'))
        
        # Mettre à jour l'affichage
        self.source_label.setText(source_name)
        self.target_label.setText(target_name)

    def update_current(self, source_uid):
        """Met à jour l'affichage pour le nœud source sélectionné."""
        self.relations_list.clear()
        self.target_label.setText("—")
        
        if source_uid:
            source_info = self.parent_widget.label_uid_to_info.get(source_uid, {})
            source_name = source_info.get('name', source_info.get('label', 'Inconnu'))
            self.source_label.setText(source_name)
            self._update_relations_list(source_uid)
        else:
            self.source_label.setText("Aucun sélectionné")
            self.relations_list.clear()

    def _get_node_name(self, uid):
        """Récupère le nom d'un nœud par son UID avec fallback robuste."""
        if not uid:
            return None
        
        # Chercher dans label_uid_to_info
        info = self.parent_widget.label_uid_to_info.get(uid)
        if info:
            return info.get('name') or info.get('label')
        
        # Fallback: chercher directement dans les nœuds
        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n.get('uid') == uid), None)
        if node:
            return node.get('label') or node.get('name')
        
        return None

    def _on_edit(self):
        """Modifie une relation existante (change la target)."""
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        rel_category = rel.get('category', 'custom')
        
        # Ne pas permettre modification des relations hiérarchiques
        if rel_category == 'hierarchy':
            QtWidgets.QMessageBox.information(
                self, 
                "Info", 
                "Les relations hiérarchiques (parent/child) ne peuvent pas être modifiées."
            )
            return

        src_uid = rel['source']
        old_target_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        # Boîte de dialogue pour choisir une nouvelle cible
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == src_uid:
                continue
            name = info.get('name') or info.get('label', 'N/A')
            cluster = info.get('cluster', 'N/A')
            target_uids.append(uid)
            target_names.append(f"{name} ({cluster})")

        if not target_names:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune cible",
                "Aucun nœud disponible comme nouvelle cible."
            )
            return

        new_target_name, ok = QInputDialog.getItem(
            self, 
            "Modifier la relation",
            "Nouvelle cible:", 
            target_names, 
            0, 
            False
        )
        
        if ok and new_target_name:
            new_index = target_names.index(new_target_name)
            new_target_uid = target_uids[new_index]

            # Supprimer ancienne relation
            self.parent_widget._update_local_relations_remove(src_uid, old_target_uid, rel_type)
            old_rel = {"target_uid": old_target_uid, "relation_type": rel_type}
            if old_rel in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(old_rel)

            # Ajouter nouvelle relation
            new_rel = {"target_uid": new_target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[src_uid].append(new_rel)
            self.parent_widget._update_local_relations(src_uid, new_target_uid, rel_type)

            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation modifiée: {src_uid} → {new_target_uid}")

    def _on_remove(self):
        """Supprime une relation."""
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        rel_category = rel.get('category', 'custom')
        
        # Ne pas permettre suppression des relations hiérarchiques
        if rel_category == 'hierarchy':
            QtWidgets.QMessageBox.information(
                self,
                "Info",
                "Les relations hiérarchiques (parent/child) ne peuvent pas être supprimées."
            )
            return

        src_uid = rel['source']
        tgt_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        reply = QtWidgets.QMessageBox.question(
            self, 
            "Supprimer", 
            "Voulez-vous vraiment supprimer cette relation?"
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.parent_widget._update_local_relations_remove(src_uid, tgt_uid, rel_type)
            rel_obj = {"target_uid": tgt_uid, "relation_type": rel_type}
            if rel_obj in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(rel_obj)
            
            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation supprimée: {src_uid} → {tgt_uid}")

    def _update_relations_list(self, source_uid):
        """Met à jour la liste des relations avec affichage source/target cohérent."""
        self.relations_list.clear()
        if not source_uid:
            return

        # Mapping Dgraph -> local pour résolution
        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()

        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if not node:
            return

        # === 1. Relations sortantes (custom) ===
        for r in node.get('outgoing_relations', []):
            target_uid = r['target_uid']
            
            # Mapper si hex Dgraph
            if target_uid.startswith('0x') and len(target_uid) == 6:
                target_uid = dgraph_to_local.get(target_uid, target_uid)
            
            target_name = self._get_node_name(target_uid)
            if not target_name:
                continue  # Skip si nom introuvable
            
            rel_type = r.get('relation_type', 'relation')
            
            # Affichage: Source → (type) → Target
            source_name = self._get_node_name(source_uid) or 'Source'
            
            display = f"{source_name} →({rel_type})→ {target_name}"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "category": "custom",
                "direction": "out",
                "source": source_uid,
                "target": r['target_uid'],  # Garder original
                "type": rel_type
            })
            item.setForeground(QtGui.QColor("#2196F3"))  # Bleu pour sortantes
            self.relations_list.addItem(item)

        # === 2. Relations entrantes (custom) ===
        for r in node.get('incoming_relations', []):
            source_uid_rel = r['source_uid']
            
            # Mapper si hex
            if source_uid_rel.startswith('0x') and len(source_uid_rel) == 6:
                source_uid_rel = dgraph_to_local.get(source_uid_rel, source_uid_rel)
            
            source_name = self._get_node_name(source_uid_rel)
            if not source_name:
                continue  # Skip si nom introuvable
            
            rel_type = r.get('relation_type', 'relation')
            
            # Affichage: Source → (type) → Target (current node)
            target_name = self._get_node_name(source_uid) or 'Target'
            
            display = f"{source_name} →({rel_type})→ {target_name}"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "category": "custom",
                "direction": "in",
                "source": r['source_uid'],  # Original
                "target": source_uid,
                "type": rel_type
            })
            item.setForeground(QtGui.QColor("#FF9800"))  # Orange pour entrantes
            self.relations_list.addItem(item)

        # === 3. Hiérarchie: Enfants ===
        children = node.get('children', [])
        if children:  # Afficher seulement s'il y a des enfants
            for child in children:
                child_uid = child['uid']
                child_name = child.get('label') or child.get('name')
                
                if not child_name:
                    continue  # Skip si pas de nom
                
                # Affichage: Source → (child) → Target
                source_name = self._get_node_name(source_uid) or 'Source'
                
                display = f"{source_name} →(child)→ {child_name}"
                
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": "hierarchy",
                    "direction": "out",
                    "source": source_uid,
                    "target": child_uid,
                    "type": "child"
                })
                item.setForeground(QtGui.QColor("#4CAF50"))  # Vert pour hiérarchie
                self.relations_list.addItem(item)

        # === 4. Hiérarchie: Parents ===
        parents = node.get('parents', [])
        if parents:  # Afficher seulement s'il y a des parents
            for p_uid in parents:
                # Mapper si hex
                if p_uid.startswith('0x') and len(p_uid) == 6:
                    p_uid_mapped = dgraph_to_local.get(p_uid, p_uid)
                else:
                    p_uid_mapped = p_uid
                
                parent_name = self._get_node_name(p_uid_mapped)
                if not parent_name:
                    continue  # Skip si nom introuvable
                
                # Affichage: Parent → (parent) → Current
                source_name = self._get_node_name(source_uid) or 'Current'
                
                display = f"{parent_name} →(parent)→ {source_name}"
                
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": "hierarchy",
                    "direction": "in",
                    "source": p_uid,  # Original
                    "target": source_uid,
                    "type": "parent"
                })
                item.setForeground(QtGui.QColor("#9C27B0"))  # Violet pour parents
                self.relations_list.addItem(item)

    def _on_add_new_relation(self):
        """Ajoute une nouvelle relation custom."""
        source_uid = self.parent_widget.current_selected_label_uid
        if not source_uid:
            QtWidgets.QMessageBox.warning(
                self, 
                "Erreur", 
                "Sélectionnez un nœud source."
            )
            return

        # Créer une liste de toutes les cibles possibles
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == source_uid:
                continue
            name = info.get('name') or info.get('label', 'N/A')
            cluster = info.get('cluster', 'N/A')
            target_uids.append(uid)
            target_names.append(f"{name} ({cluster})")

        if not target_names:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune cible",
                "Aucun nœud disponible comme cible."
            )
            return

        # Boîte de sélection de la cible
        target_name, ok = QInputDialog.getItem(
            self, 
            "Nouvelle relation",
            "Choisissez une cible:", 
            target_names, 
            0, 
            False
        )
        
        if ok and target_name:
            target_index = target_names.index(target_name)
            target_uid = target_uids[target_index]

            # Boîte pour le type de relation
            rel_types = [
                "import", 
                "extends", 
                "implements", 
                "uses", 
                "calls", 
                "depends_on",
                "relation"
            ]
            
            rel_type, ok2 = QInputDialog.getItem(
                self,
                "Type de relation",
                "Type de relation:",
                rel_types,
                0,
                True  # Editable
            )
            
            if not ok2 or not rel_type:
                rel_type = "relation"

            # Enregistrer relation
            relation = {"target_uid": target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[source_uid].append(relation)
            self.parent_widget._update_local_relations(source_uid, target_uid, rel_type)

            self._update_relations_list(source_uid)
            logger.info(f"Nouvelle relation ajoutée: {source_uid} →({rel_type})→ {target_uid}")

class RelationsGraphWidget(QtWidgets.QWidget):
    """Widget optimisé pour afficher le graphe des relations du nœud sélectionné"""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget
        self.figure = None
        self.canvas = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Titre dynamique
        self.title_label = QLabel("Graphe des Relations")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50;")
        layout.addWidget(self.title_label)

        # Canvas pour le graphe
        self.figure = Figure(figsize=(5, 3), facecolor='white', dpi=100)  # Taille optimisée pour le panneau
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        layout.addWidget(self.canvas)

        # Légende simplifiée
        self.legend_label = QLabel("Aucun nœud sélectionné")
        self.legend_label.setStyleSheet("font-size: 10px; color: #666; font-style: italic;")
        layout.addWidget(self.legend_label)

        # Message initial
        self._draw_empty_graph()

    def _init_uid_mappings(self):
        """Initialize UID mapping dictionaries."""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
        logger.debug("UID mappings initialized")

    def update_graph(self, central_uid=None):
        """
        Updates the graph for the selected central node.
        Improved version with better Dgraph UID mapping and fallback handling.
        """
        if not central_uid:
            self._draw_empty_graph()
            self.title_label.setText("Graphe des Relations")
            self.legend_label.setText("Aucun nœud sélectionné")
            return

        # Try to get the node info (local first, then Dgraph)
        central_info = self.parent_widget.label_uid_to_info.get(central_uid)

        if not central_info:
            # Fallback: try Dgraph query
            central_info = self._query_node_info_from_dgraph(central_uid)

            if central_info:
                # Cache it locally for next time
                self.parent_widget.label_uid_to_info[central_uid] = central_info
            else:
                # If still not found, use minimal info
                logger.warning(f"Nœud {central_uid} introuvable, utilisation de fallback")
                central_info = {
                    'name': central_uid if len(central_uid) < 20 else central_uid[:17] + '...',
                    'cluster': 'unknown',
                    'type': 'unknown'
                }
                # Don't cache fallback info

        central_name = central_info.get('name', central_uid)

        # Collect related items
        related_items = self._collect_related_items(central_uid, max_depth=1, max_nodes=50)

        if not related_items:
            self.title_label.setText(f"Graphe: {central_name}")
            self.legend_label.setText("Aucune relation trouvée")
            self._draw_empty_graph_with_message(
                f"Le nœud '{central_name}' n'a aucune relation"
            )
            logger.info(f"Aucune relation pour {central_name}")
            return

        # Display the graph
        logger.info(f"Affichage graphe pour {central_name}: {len(related_items)} relations")
        self.title_label.setText(f"Graphe: {central_name}")
        self._draw_graph(central_uid, central_name, related_items)

    def _query_node_info_from_dgraph(self, central_uid):
        """
        Query Dgraph for node information with improved error handling.
        Returns node info or None if not found.
        """
        if not self.parent_widget.dgraph_connector or not self.parent_widget.dgraph_connector.client:
            logger.debug("No Dgraph client available.")
            return None

        # Check if it's already a hex Dgraph UID (format: 0x...)
        is_hex_uid = isinstance(central_uid, str) and central_uid.startswith('0x')

        if is_hex_uid:
            # Direct Dgraph query with hex UID
            query = f"""
            {{
              q(func: uid({central_uid})) {{
                uid
                name
                id
                local_id
                label
                description
              }}
            }}
            """
        else:
            # Try local UUID first via local_id field
            query = f"""
            {{
              q(func: eq(local_id, "{central_uid}")) {{
                uid
                name
                id
                local_id
                label
                description
              }}
            }}
            """

        try:
            txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            data = self.parent_widget.dgraph_connector._parse_response(resp)
            nodes = data.get("q", [])

            if nodes:
                node = nodes[0]
                node_uid = node.get('uid', central_uid)

                # Map the Dgraph UID to local UID if not already mapped
                if is_hex_uid and node.get('local_id'):
                    self.parent_widget.local_to_dgraph[node['local_id']] = central_uid
                    self.parent_widget.dgraph_to_local[central_uid] = node['local_id']

                return {
                    'uid': node_uid,
                    'name': node.get('name') or node.get('label', 'Unknown'),
                    'label': node.get('label', node.get('name', 'Unknown')),
                    'description': node.get('description', ''),
                    'id': node.get('id', central_uid)
                }

            # No node found in Dgraph
            logger.warning(f"Nœud {central_uid} non trouvé dans Dgraph")
            return None

        except Exception as e:
            logger.error(f"Erreur query Dgraph pour {central_uid}: {e}")
            return None

    def _draw_empty_graph_with_message(self, message):
        """
        Dessine un graphe vide avec un message personnalisé
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5, 0.5, 
            message, 
            ha='center', 
            va='center', 
            transform=ax.transAxes, 
            fontsize=11, 
            color='#666',
            style='italic'
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.figure.tight_layout()
        self.canvas.draw()

    def _query_relations_for_node(self, central_uid):
        """
        Query Dgraph pour les relations impliquant le nœud central.
        Corrigée pour supporter les identifiants non numériques (UUID string) et mapper.
        """
        if not self.parent_widget.dgraph_connector.client:
            logger.warning("Aucun client Dgraph connecté.")
            return []

        # Mapping pour query : local -> Dgraph UID
        local_to_dgraph = self.parent_widget._get_local_to_dgraph_mapping()
        dgraph_uid = local_to_dgraph.get(central_uid)
        if not dgraph_uid:
            # Fallback : query par 'local_id' si stocké comme champ
            query = f"""
            {{
              q(func: eq(local_id, "{central_uid}")) {{
                uid
                name
                id
                local_id
              }}
            }}
            """
            try:
                txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
                resp = txn.query(query)
                txn.discard()
                data = self.parent_widget.dgraph_connector._parse_response(resp)
                nodes = data.get("q", [])
                if nodes:
                    dgraph_uid = nodes[0]['uid']
                else:
                    logger.warning(f"Pas de Dgraph UID pour local {central_uid}")
                    return []
            except Exception as e:
                logger.error(f"Erreur fallback query pour {central_uid}: {e}")
                return []

        # Query principale avec Dgraph UID (hex)
        query = f"""
        {{
          q(func: uid({dgraph_uid})) {{
            uid
            name
            relationType
            source {{
              uid
              name
              id
              local_id
              level
            }}
            target {{
              uid
              name
              id
              local_id
              level
            }}
          }}
          incoming(func: type(Relation)) @filter(eq(target.uid, {dgraph_uid})) {{
            uid
            name
            relationType
            source {{
              uid
              name
              id
              local_id
              level
            }}
            target {{
              uid
              name
              id
              local_id
              level
            }}
          }}
        }}
        """

        try:
            logger.debug(f"Envoi de la requête Dgraph pour le nœud dgraph_uid={dgraph_uid} (local={central_uid})")
            txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            data = self.parent_widget.dgraph_connector._parse_response(resp)
            relations = data.get("q", []) + data.get("incoming", [])

            logger.info(f"{len(relations)} relations récupérées depuis Dgraph pour {central_uid}")
            return relations

        except Exception as e:
            logger.error(f"Erreur lors de la query des relations (dgraph={dgraph_uid}): {e}")
            return []

    def _collect_related_items(self, central_uid, max_depth=1, max_nodes=50):
        """
        Collecte TOUTES les relations d'un nœud (hiérarchiques, imports, héritage, etc.)
        Version améliorée avec mapping UID local <-> Dgraph pour éviter mismatches
        """
        if not self.parent_widget.current_project_profile_data:
            return []

        all_nodes = self.parent_widget._get_all_nodes()
        central_node = next((n for n in all_nodes if n['uid'] == central_uid), None)
        if not central_node:
            return []

        related = []
        visited = set([central_uid])

        # Mapping pour résolution Dgraph -> local
        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()

        # 1. Relations sortantes locales (outgoing_relations)
        for rel in central_node.get('outgoing_relations', [])[:max_nodes]:
            target_uid = rel.get('target_uid', rel.get('target_id', ''))
            # Mapper si hex Dgraph
            if target_uid.startswith('0x') and len(target_uid) == 6:  # Format hex court
                target_uid = dgraph_to_local.get(target_uid, target_uid)
            if target_uid in visited:
                continue
            
            target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
            if target_node:
                related.append({
                    'name': target_node['label'],
                    'type': rel['relation_type'],
                    'uid': target_uid,  # UID local mappé
                    'direction': 'out'
                })
                visited.add(target_uid)

        # 2. Relations entrantes locales (incoming_relations)
        for rel in central_node.get('incoming_relations', [])[:max_nodes]:
            source_uid = rel.get('source_uid', rel.get('source_id', ''))
            # Mapper si hex Dgraph
            if source_uid.startswith('0x') and len(source_uid) == 6:
                source_uid = dgraph_to_local.get(source_uid, source_uid)
            if source_uid in visited:
                continue
            
            source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
            if source_node:
                related.append({
                    'name': source_node['label'],
                    'type': rel['relation_type'] + ' (inverse)',
                    'uid': source_uid,
                    'direction': 'in'
                })
                visited.add(source_uid)

        # 3. Enfants hiérarchiques locaux
        for child in central_node.get('children', [])[:max_nodes]:
            child_uid = child['uid']
            if child_uid in visited:
                continue
            
            related.append({
                'name': child['label'],
                'type': 'child',
                'uid': child_uid,
                'direction': 'out'
            })
            visited.add(child_uid)

        # 4. Parents hiérarchiques locaux (si présents)
        for parent_uid in central_node.get('parents', [])[:max_nodes]:
            # Mapper si hex
            if parent_uid.startswith('0x') and len(parent_uid) == 6:
                parent_uid = dgraph_to_local.get(parent_uid, parent_uid)
            if parent_uid in visited:
                continue
            
            parent_info = self.parent_widget.label_uid_to_info.get(parent_uid)
            if parent_info:
                related.append({
                    'name': parent_info['name'],
                    'type': 'parent',
                    'uid': parent_uid,
                    'direction': 'in'
                })
                visited.add(parent_uid)

        # 5. Relations supplémentaires depuis Dgraph (mappées vers local)
        dgraph_rels = self._query_relations_for_node(central_uid)
        for rel in dgraph_rels:
            if rel['source']['uid'] == central_uid:  # Utiliser local central_uid
                target_dgraph_uid = rel['target']['uid']
                target_uid = dgraph_to_local.get(target_dgraph_uid, target_dgraph_uid)
                if target_uid in visited:
                    continue
                target_name = rel['target']['name']
                related.append({
                    'name': target_name,
                    'type': rel['relationType'],
                    'uid': target_uid,  # Mappé local
                    'direction': 'out'
                })
                visited.add(target_uid)
            elif rel['target']['uid'] == central_uid:
                source_dgraph_uid = rel['source']['uid']
                source_uid = dgraph_to_local.get(source_dgraph_uid, source_dgraph_uid)
                if source_uid in visited:
                    continue
                source_name = rel['source']['name']
                related.append({
                    'name': source_name,
                    'type': rel['relationType'] + ' (inverse)',
                    'uid': source_uid,
                    'direction': 'in'
                })
                visited.add(source_uid)

        # Limiter le nombre total pour la performance
        related = related[:max_nodes]

        logger.info(f"Collecté {len(related)} relations pour {central_node['label']}")
        return related

    def _draw_empty_graph(self):
        """Dessine un graphe vide avec message"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'Sélectionnez un nœud pour voir ses relations', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12, color='#666')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.figure.tight_layout()
        self.canvas.draw()

    def _draw_graph(self, central_uid, central_name, related_items):
        """
        Dessine le graphe avec NetworkX - Version améliorée avec tous types de relations
        Utilise les UIDs comme identifiants de nœuds pour éviter les doublons de noms
        """
        self.figure.clear()
        G = nx.DiGraph()

        # Nœud central
        G.add_node(central_uid, node_type='central', label=central_name)

        if not related_items:
            self._draw_empty_graph()
            return

        # Grouper par type pour statistiques
        relation_types = {}
        seen_nodes = set([central_uid])
        edge_colors = []
        edge_labels = {}

        for item in related_items:
            rel_uid = item['uid']
            rel_name = item['name']
            rel_type = item['type']
            direction = item.get('direction', 'out')

            # Éviter doublons
            if rel_uid in seen_nodes:
                continue
            
            # Ajouter nœud
            G.add_node(rel_uid, node_type='related', label=rel_name)
            seen_nodes.add(rel_uid)

            # Ajouter arête selon direction
            if direction == 'in':
                # Relation entrante : de rel_uid vers central
                G.add_edge(rel_uid, central_uid, type=rel_type)
                edge_labels[(rel_uid, central_uid)] = rel_type[:6]
            else:
                # Relation sortante ou hiérarchique : de central vers rel_uid
                G.add_edge(central_uid, rel_uid, type=rel_type)
                edge_labels[(central_uid, rel_uid)] = rel_type[:6]

            # Couleur selon type
            edge_colors.append(self._get_color_for_type(rel_type))

            # Comptage
            base_type = rel_type.replace(' (inverse)', '')
            relation_types[base_type] = relation_types.get(base_type, 0) + 1

        if len(G.nodes()) == 1:
            self._draw_empty_graph()
            return

        # Layout optimisé selon taille
        num_nodes = len(G.nodes())

        if num_nodes <= 10:
            pos = nx.spring_layout(G, k=2.5, iterations=100, seed=42)
        elif num_nodes <= 30:
            pos = nx.kamada_kawai_layout(G)
        else:
            # Layout circulaire pour grands graphes
            pos = nx.circular_layout(G)
            pos[central_uid] = (0, 0)

        # Dessiner
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Arêtes avec couleurs
        if G.edges():
            edges_list = list(G.edges())
            nx.draw_networkx_edges(
                G, pos, 
                edgelist=edges_list,
                edge_color=edge_colors,
                ax=ax,
                width=2.0 if num_nodes <= 20 else 1.5,
                alpha=0.7,
                arrows=True,
                arrowsize=15 if num_nodes <= 20 else 12,
                arrowstyle='->',
                connectionstyle='arc3,rad=0.1'
            )

        # Nœuds avec couleurs distinctes
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if node == central_uid:
                node_colors.append('#A23B2D')  # Rouge pour central
                node_sizes.append(800)
            else:
                node_colors.append('#4CAF50')  # Vert pour liés
                node_sizes.append(500)

        nx.draw_networkx_nodes(
            G, pos, 
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.85,
            linewidths=2,
            edgecolors='white'
        )

        # Labels des nœuds
        labels = {}
        for node in G.nodes():
            node_label = G.nodes[node].get('label', node)
            # Tronquer les noms longs
            label = node_label if len(node_label) <= 15 else node_label[:12] + "..."
            labels[node] = label

        label_opts = {
            'ax': ax,
            'font_size': 9 if num_nodes > 20 else 10,
            'font_weight': 'bold',
        }

        if num_nodes <= 30:
            label_opts.update({
                'font_color': 'white',
                'bbox': dict(
                    boxstyle='round,pad=0.3', 
                    facecolor='black', 
                    alpha=0.7, 
                    edgecolor='none'
                )
            })
        else:
            label_opts['font_color'] = 'black'

        nx.draw_networkx_labels(G, pos, labels, **label_opts)

        # Labels des arêtes pour petits graphes
        if num_nodes <= 15 and edge_labels:
            nx.draw_networkx_edge_labels(
                G, pos, 
                edge_labels,
                ax=ax,
                font_size=7,
                font_color='#333',
                bbox=dict(
                    boxstyle='round,pad=0.2', 
                    facecolor='white', 
                    alpha=0.9
                )
            )

        # Titre informatif
        title_text = (
            f"Réseau de relations\n"
            f"Nœud central: {central_name}\n"
            f"({num_nodes} nœuds, {len(G.edges())} relations)"
        )
        ax.set_title(title_text, fontsize=11, fontweight='bold', pad=15)

        ax.axis('off')
        ax.margins(0.15)

        self.figure.tight_layout()
        self.canvas.draw()

        # Mettre à jour la légende avec tous les types
        self._update_legend_with_types(relation_types)

    def _get_color_for_type(self, rel_type):
        """
        Retourne une couleur selon le type de relation
        Version étendue avec plus de types
        """
        # Normaliser le type (retirer "(inverse)" si présent)
        rel_lower = rel_type.lower().replace(' (inverse)', '')

        colors = {
            'import': '#FF9800',
            'heritage': '#2196F3',
            'extend': '#4CAF50',
            'implement': '#9C27B0',
            'depends_on': '#FF5722',
            'calls': '#00BCD4',
            'uses': '#795548',
            'references': '#607D8B',
            'child': '#00BCD4',
            'parent': '#3F51B5',
            'relation': '#E91E63',
        }

        # Recherche exacte puis partielle
        if rel_lower in colors:
            return colors[rel_lower]

        for key, color in colors.items():
            if key in rel_lower:
                return color

        return '#999999'  # Couleur par défaut

    def _update_legend_with_types(self, relation_types):
        """
        Met à jour la légende avec tous les types de relations
        """
        if not relation_types:
            self.legend_label.setText("Aucune relation")
            return

        # Construire texte de légende avec compteurs
        legend_parts = []
        for rel_type, count in sorted(relation_types.items()):
            color = self._get_color_for_type(rel_type)
            legend_parts.append(f"{rel_type}: {count}")

        legend_text = " | ".join(legend_parts)

        # Tronquer si trop long
        if len(legend_text) > 80:
            legend_text = legend_text[:77] + "..."

        self.legend_label.setText(legend_text)

    def _update_legend(self, related_items):
        """
        Version alternative : légende simple avec comptage
        """
        if not related_items:
            self.legend_label.setText("Aucune relation")
            return
    
        # Grouper par type
        types = {}
        for item in related_items:
            rel_type = item['type'].replace(' (inverse)', '')
            types[rel_type] = types.get(rel_type, 0) + 1
    
        # Construire texte
        legend_text = " | ".join([f"{k}: {v}" for k, v in sorted(types.items())])
        
        if len(legend_text) > 80:
            legend_text = legend_text[:77] + "..."
        
        self.legend_label.setText(legend_text)

class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.conductor = conductor
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.db_path = os.path.join("data", "liris.db")
        self._init_sqlite_db()

        self.dependency_parser = MultiLanguageDependencyParser()
        self.project_scanner = ProjectStructureScanner(self.dependency_parser)

            # 🔁 Alias rétrocompatible
        self.structure_scanner = self.project_scanner
        
        self.parsed_relations_cache = {}
        self.file_content_cache = {}

        self.project_profiles = {}
        self.current_project_name = None
        self.current_project_profile_data = None

        self.current_cluster_index = -1
        self.current_cluster_data = None

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None

        self.current_level1_label_index = -1
        self.current_level1_is_file = False
        self.current_level1_filename = None

        self.current_level2_label_index = -1
        self.current_level2_is_file = False
        self.current_level2_filename = None

        # Pour les relations
        self.pending_relations = defaultdict(list)
        self.label_uid_to_info = {}
        self.name_to_uid = {}
        self.current_selected_label_uid = None

        self.global_relations_config = RelationsConfig(self, "global")
        self.relations_graph = RelationsGraphWidget(self)  # Nouveau widget graphe

        # Définir une taille minimale pour le widget et maximiser
        self.setMinimumSize(1400, 900)

        try:
            if self.dgraph_connector.client:
                schema = self.dgraph_connector.get_current_schema()
                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse. Mise à jour recommandée.")

            self._init_ui()
            self._load_project_profiles()  # Load from Dgraph
            self._load_projects_from_sqlite()  # Load from SQLite, avoiding duplicates
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

    def _init_sqlite_db(self):
        """Initialise la base de données SQLite avec schéma aligné à Dgraph."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table des Workspaces (correspond à type Workspace en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT UNIQUE,
                    ownerId TEXT,
                    description TEXT,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table ClusterManagement (correspond à type ClusterManagement en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cluster_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    workspace_uid TEXT NOT NULL,
                    lastUpdated TIMESTAMP,
                    version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_uid) REFERENCES workspaces(uid)
                )
            """)
            
            # Table des Clusters (correspond à type Cluster en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_management_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    userId TEXT,
                    nodeType TEXT DEFAULT 'cluster',
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    is_file_cluster BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_management_uid) REFERENCES cluster_management(uid)
                )
            """)
            
            # Table des Labels (correspond à type Label en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_uid TEXT NOT NULL,
                    parent_uid TEXT,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    level INTEGER,
                    path TEXT,
                    parentId TEXT,
                    nodeType TEXT DEFAULT 'label',
                    category TEXT,
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_uid) REFERENCES clusters(uid),
                    FOREIGN KEY (parent_uid) REFERENCES labels(uid)
                )
            """)
            
            # Table des Relations (correspond à type Relation implicite en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT,
                    relationType TEXT NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)
            
            # Table des Functions (correspond à type Function en Dgraph)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    label_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (label_uid) REFERENCES labels(uid)
                )
            """)
            
            # Table des Imports (relations de type import)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)
            
            # Créer des index pour améliorer les performances
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_cm ON clusters(cluster_management_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_cluster ON labels(cluster_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_parent ON labels(parent_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_uid)")
            
            conn.commit()
            conn.close()
            logger.info(f"Base de données SQLite initialisée : {self.db_path}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation SQLite : {e}")

    def _create_workspace_in_sqlite(self, project_data):
        """CRUD Create: Crée un nouveau workspace en évitant les doublons via uid unique."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid
            
            # Vérifier si existe déjà (bien que uid unique)
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if cursor.fetchone():
                logger.warning(f"Workspace {project_uid} existe déjà.")
                conn.close()
                return False
            
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace créé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du workspace SQLite : {e}")
            return False

    def _read_workspace_from_sqlite(self, workspace_uid):
        """CRUD Read: Lit un workspace spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM workspaces WHERE uid = ?", (workspace_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du workspace SQLite : {e}")
            return None

    def _update_workspace_in_sqlite(self, project_data):
        """CRUD Update: Met à jour un workspace existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid')
            if not project_uid:
                logger.error("UID manquant pour update.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {project_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE workspaces SET
                name = ?, description = ?, files = ?, fileContents = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                project_data.get('name', ''),
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat(),
                project_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace mis à jour dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du workspace SQLite : {e}")
            return False

    def _delete_workspace_in_sqlite(self, workspace_uid):
        """CRUD Delete: Supprime un workspace et ses dépendances en cascade."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (workspace_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {workspace_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade (ordre inverse des FK)
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid IN (
                        SELECT uid FROM clusters 
                        WHERE cluster_management_uid IN (
                            SELECT uid FROM cluster_management 
                            WHERE workspace_uid = ?
                        )
                    )
                )
            """, (workspace_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))  # Remplacer ... par la sous-requête ci-dessus
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))
            
            # Labels
            cursor.execute("""
                DELETE FROM labels 
                WHERE cluster_uid IN (
                    SELECT uid FROM clusters 
                    WHERE cluster_management_uid IN (
                        SELECT uid FROM cluster_management 
                        WHERE workspace_uid = ?
                    )
                )
            """, (workspace_uid,))
            
            # Clusters
            cursor.execute("""
                DELETE FROM clusters 
                WHERE cluster_management_uid IN (
                    SELECT uid FROM cluster_management 
                    WHERE workspace_uid = ?
                )
            """, (workspace_uid,))
            
            # Cluster Management
            cursor.execute("""
                DELETE FROM cluster_management 
                WHERE workspace_uid = ?
            """, (workspace_uid,))
            
            # Workspace
            cursor.execute("DELETE FROM workspaces WHERE uid = ?", (workspace_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace supprimé de SQLite : {workspace_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du workspace SQLite : {e}")
            return False

    def _create_cluster_in_sqlite(self, cluster_data, workspace_uid):
        """CRUD Create: Crée un cluster en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
            cluster_data['uid'] = cluster_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} existe déjà.")
                conn.close()
                return False
            
            # Assurer cluster_management existe
            cm_uid = f"cm_{workspace_uid}"
            cursor.execute("""
                INSERT OR IGNORE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (cm_uid, workspace_uid, datetime.now().isoformat(), '1.0'))
            
            cursor.execute("""
                INSERT INTO clusters 
                (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                 description, codeContent, files, fileContents, is_file_cluster, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cluster_uid,
                cm_uid,
                cluster_data.get('name', ''),
                cluster_data.get('uid', str(uuid.uuid4())),
                'user1',
                'cluster',
                cluster_data.get('description', ''),
                '',
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster créé dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création cluster SQLite : {e}")
            return False

    def _update_cluster_in_sqlite(self, cluster_data):
        """CRUD Update: Met à jour un cluster existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid')
            if not cluster_uid:
                logger.error("UID manquant pour update cluster.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE clusters SET
                name = ?, description = ?, files = ?, fileContents = ?, is_file_cluster = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                cluster_data.get('name', ''),
                cluster_data.get('description', ''),
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                cluster_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster mis à jour dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour cluster SQLite : {e}")
            return False

    def _delete_cluster_in_sqlite(self, cluster_uid):
        """CRUD Delete: Supprime un cluster et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Labels
            cursor.execute("DELETE FROM labels WHERE cluster_uid = ?", (cluster_uid,))
            
            # Cluster
            cursor.execute("DELETE FROM clusters WHERE uid = ?", (cluster_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster supprimé de SQLite : {cluster_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression cluster SQLite : {e}")
            return False

    def _create_label_in_sqlite(self, label_data, cluster_uid, parent_uid=None, level=0):
        """CRUD Create: Crée un label en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid', str(uuid.uuid4()))
            label_data['uid'] = label_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if cursor.fetchone():
                logger.warning(f"Label {label_uid} existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label_uid,
                cluster_uid,
                parent_uid,
                label_data.get('label', ''),
                label_data.get('id', label_uid),
                level,
                '',  # path
                parent_uid,  # parentId
                'label',
                json.dumps(label_data.get('category', [])),
                label_data.get('description', ''),
                '',  # codeContent
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label créé dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création label SQLite : {e}")
            return False

    def _read_label_from_sqlite(self, label_uid):
        """CRUD Read: Lit un label spécifique et ses enfants récursivement."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM labels WHERE uid = ?", (label_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['category'] = json.loads(data['category'])
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            data['children'] = []
            data['parents'] = [data['parent_uid']] if data['parent_uid'] else []
            
            # Charger enfants récursivement
            cursor.execute("SELECT uid FROM labels WHERE parent_uid = ?", (label_uid,))
            for child_row in cursor.fetchall():
                child_data = self._read_label_from_sqlite(child_row['uid'])
                if child_data:
                    data['children'].append(child_data)
            
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture label SQLite : {e}")
            return None

    def _update_label_in_sqlite(self, label_data):
        """CRUD Update: Met à jour un label existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid')
            if not label_uid:
                logger.error("UID manquant pour update label.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour update.")
                conn.close()
                return False
            
            parent_uid = label_data.get('parents', [None])[0] if label_data.get('parents') else None
            
            cursor.execute("""
                UPDATE labels SET
                name = ?, description = ?, category = ?, files = ?, fileContents = ?, parent_uid = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                label_data.get('label', ''),
                label_data.get('description', ''),
                json.dumps(label_data.get('category', [])),
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                parent_uid,
                datetime.now().isoformat(),
                label_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label mis à jour dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour label SQLite : {e}")
            return False

    def _delete_label_in_sqlite(self, label_uid):
        """CRUD Delete: Supprime un label et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("DELETE FROM functions WHERE label_uid = ?", (label_uid,))
            
            # Imports
            cursor.execute("DELETE FROM imports WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Relations
            cursor.execute("DELETE FROM relations WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Enfants récursifs
            cursor.execute("""
                WITH RECURSIVE label_tree AS (
                    SELECT uid FROM labels WHERE uid = ?
                    UNION ALL
                    SELECT l.uid FROM labels l
                    JOIN label_tree lt ON l.parent_uid = lt.uid
                )
                DELETE FROM labels WHERE uid IN (SELECT uid FROM label_tree)
            """, (label_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Label supprimé de SQLite : {label_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression label SQLite : {e}")
            return False

    def _create_relation_in_sqlite(self, source_uid, target_uid, relation_type='relation'):
        """CRUD Create: Crée une relation en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            rel_uid = f"rel_{str(uuid.uuid4())}"
            
            # Vérifier doublon (même source, target, type)
            cursor.execute("""
                SELECT uid FROM relations 
                WHERE source_uid = ? AND target_uid = ? AND relationType = ?
            """, (source_uid, target_uid, relation_type))
            if cursor.fetchone():
                logger.warning(f"Relation {source_uid} -> {target_uid} ({relation_type}) existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO relations 
                (uid, name, relationType, source_uid, target_uid, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rel_uid,
                f"{relation_type}_relation",
                relation_type,
                source_uid,
                target_uid,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation créée dans SQLite : {source_uid} -> {target_uid} ({relation_type})")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création relation SQLite : {e}")
            return False

    def _read_relation_from_sqlite(self, rel_uid):
        """CRUD Read: Lit une relation spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM relations WHERE uid = ?", (rel_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture relation SQLite : {e}")
            return None

    def _update_relation_in_sqlite(self, rel_uid, new_target_uid=None, new_relation_type=None):
        """CRUD Update: Met à jour une relation existante."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if not rel_uid:
                logger.error("UID manquant pour update relation.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour update.")
                conn.close()
                return False
            
            updates = []
            params = []
            if new_target_uid is not None:
                updates.append("target_uid = ?")
                params.append(new_target_uid)
            if new_relation_type is not None:
                updates.append("relationType = ?")
                params.append(new_relation_type)
            updates.append("updatedAt = ?")  # Toujours updater la date
            params.append(datetime.now().isoformat())
            params.append(rel_uid)
            
            if updates:
                query = f"UPDATE relations SET {', '.join(updates)} WHERE uid = ?"
                cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            logger.info(f"Relation mise à jour dans SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour relation SQLite : {e}")
            return False

    def _delete_relation_in_sqlite(self, rel_uid):
        """CRUD Delete: Supprime une relation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour suppression.")
                conn.close()
                return False
            
            cursor.execute("DELETE FROM relations WHERE uid = ?", (rel_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation supprimée de SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression relation SQLite : {e}")
            return False

    def _save_project_to_sqlite(self, project_data):
        """Sauvegarde le projet complet dans SQLite avec schéma aligné à Dgraph (Upsert)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid  # Ensure uid is set
            
            # Upsert Workspace
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT OR REPLACE INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            # Upsert ClusterManagement
            cluster_management_uid = f"cm_{project_uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (
                cluster_management_uid,
                project_uid,
                datetime.now().isoformat(),
                '1.0'
            ))
            
            # Upsert clusters et labels
            for cluster_data in project_data.get('turing_ontology', {}).get('clusters_detailed', []):
                cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
                cluster_data['uid'] = cluster_uid
                
                cursor.execute("""
                    INSERT OR REPLACE INTO clusters 
                    (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                     description, codeContent, files, fileContents, is_file_cluster, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster_uid,
                    cluster_management_uid,
                    cluster_data.get('name', ''),
                    cluster_data.get('uid', str(uuid.uuid4())),
                    'user1',
                    'cluster',
                    cluster_data.get('description', ''),
                    '',
                    json.dumps(cluster_data.get('files', [])),
                    json.dumps(cluster_data.get('file_contents', {})),
                    1 if cluster_data.get('is_file_cluster') else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                # Upsert labels hiérarchiquement
                for root_label in cluster_data.get('root_labels', []):
                    self._save_label_recursive_sqlite(
                        cursor, root_label, cluster_uid, None, 0
                    )
            
            # Upsert relations
            for source_uid, relations in self.pending_relations.items():
                for rel in relations:
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    relation_type = rel.get('relation_type', 'relation')
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{relation_type}_relation",
                        relation_type,
                        source_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Projet sauvegardé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde SQLite : {e}")
            return False

    def _delete_project_from_sqlite(self, workspace_uid):
        """Supprime un projet entier de SQLite (CRUD Delete pour projet)."""
        return self._delete_workspace_in_sqlite(workspace_uid)

    def _save_label_recursive_sqlite(self, cursor, label_data, cluster_uid, parent_uid, level):
        """Sauvegarde récursivement les labels dans SQLite (Upsert)."""
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid
        
        cursor.execute("""
            INSERT OR REPLACE INTO labels 
            (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
             nodeType, category, description, codeContent, files, fileContents, 
             createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label_uid,
            cluster_uid,
            parent_uid,
            label_data.get('label', ''),
            label_data.get('id', label_uid),
            level,
            '',  # path
            parent_uid,  # parentId
            'label',
            json.dumps(label_data.get('category', [])),
            label_data.get('description', ''),
            '',  # codeContent
            json.dumps(label_data.get('files', [])),
            json.dumps(label_data.get('file_contents', {})),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        # Traiter les enfants récursivement
        for child in label_data.get('children', []):
            self._save_label_recursive_sqlite(cursor, child, cluster_uid, label_uid, level + 1)

    def _load_projects_from_sqlite(self):
        """Charge les projets depuis SQLite au démarrage, en évitant les doublons avec Dgraph."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM workspaces")
            workspaces = cursor.fetchall()
            
            for ws_row in workspaces:
                workspace_uid = ws_row['uid']
                project_name = ws_row['name']
                
                # Éviter doublon : skip si déjà chargé (de Dgraph)
                if project_name in self.project_profiles:
                    logger.info(f"Projet {project_name} déjà chargé (Dgraph), skip SQLite.")
                    continue
                
                # Utiliser CRUD Read pour workspace
                ws_data = self._read_workspace_from_sqlite(workspace_uid)
                if not ws_data:
                    continue
                
                project_data = {
                    'uid': ws_data['uid'],
                    'name': ws_data['name'],
                    'description': ws_data['description'],
                    'files': ws_data['files'],
                    'file_contents': ws_data['fileContents'],
                    'turing_ontology': {'clusters_detailed': []},
                    'pending_relations': {}
                }
                
                # Charger clusters via Read
                cursor.execute("""
                    SELECT c.* FROM clusters c 
                    JOIN cluster_management cm ON c.cluster_management_uid = cm.uid 
                    WHERE cm.workspace_uid = ?
                """, (workspace_uid,))
                
                for cluster_row in cursor.fetchall():
                    cluster_uid = cluster_row['uid']
                    cluster_data = self._read_cluster_from_sqlite(cluster_uid)
                    if not cluster_data:
                        continue
                    cluster_data['root_labels'] = []
                    
                    # Charger labels racines
                    cursor.execute("""
                        SELECT * FROM labels 
                        WHERE cluster_uid = ? AND parent_uid IS NULL
                    """, (cluster_uid,))
                    
                    for label_row in cursor.fetchall():
                        root_label = self._read_label_from_sqlite(label_row['uid'])
                        if root_label:
                            cluster_data['root_labels'].append(root_label)
                    
                    project_data['turing_ontology']['clusters_detailed'].append(cluster_data)
                
                # Charger relations
                cursor.execute("""
                    SELECT * FROM relations ORDER BY source_uid
                """)
                
                relations_by_source = {}
                for rel_row in cursor.fetchall():
                    source_uid = rel_row['source_uid']
                    if source_uid not in relations_by_source:
                        relations_by_source[source_uid] = []
                    relations_by_source[source_uid].append({
                        'target_uid': rel_row['target_uid'],
                        'relation_type': rel_row['relationType']
                    })
                
                project_data['pending_relations'] = relations_by_source
                self.project_profiles[project_name] = project_data
            
            conn.close()
            logger.info(f"Chargé {len(self.project_profiles)} projets depuis SQLite (sans doublons)")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement SQLite : {e}")

    def _load_label_from_sqlite(self, cursor, label_row):
        """Charge un label et ses enfants depuis SQLite."""
        label_uid = label_row['uid']
        label_data = {
            'uid': label_uid,
            'label': label_row['name'],
            'id': label_row['id_field'],
            'description': label_row['description'],
            'category': json.loads(label_row['category']),
            'files': json.loads(label_row['files']),
            'file_contents': json.loads(label_row['fileContents']),
            'parents': [label_row['parent_uid']] if label_row['parent_uid'] else [],
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': []
        }
        
        # Charger les enfants
        cursor.execute("""
            SELECT * FROM labels WHERE parent_uid = ?
        """, (label_uid,))
        
        for child_row in cursor.fetchall():
            child_label = self._load_label_from_sqlite(cursor, child_row)
            label_data['children'].append(child_label)
        
        return label_data

    def _get_all_nodes(self):
        """Récupère tous les nœuds de labels dans la hiérarchie."""
        if not self.current_project_profile_data:
            return []
        all_nodes = []
        def collect_nodes(node_list):
            for node in node_list:
                all_nodes.append(node)
                collect_nodes(node.get('children', []))
        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            collect_nodes(cluster.get('root_labels', []))
        return all_nodes

    def _update_local_relations(self, source_uid, target_uid, rel_type):
        """Met à jour les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if source_node:
            source_node.setdefault('outgoing_relations', []).append({'target_uid': target_uid, 'relation_type': rel_type})
        target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
        if target_node:
            target_node.setdefault('incoming_relations', []).append({'source_uid': source_uid, 'relation_type': rel_type})

    def _update_local_relations_remove(self, source_uid, target_uid, rel_type):
        """Supprime les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if source_node:
            to_remove = next((r for r in source_node.get('outgoing_relations', []) if r['target_uid'] == target_uid and (rel_type is None or r['relation_type'] == rel_type)), None)
            if to_remove:
                source_node['outgoing_relations'].remove(to_remove)
        target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
        if target_node:
            to_remove = next((r for r in target_node.get('incoming_relations', []) if r['source_uid'] == source_uid and (rel_type is None or r['relation_type'] == rel_type)), None)
            if to_remove:
                target_node['incoming_relations'].remove(to_remove)

    def showEvent(self, event):
        """Maximiser la fenêtre lors de l'affichage"""
        super().showEvent(event)
        if self.window():
            self.window().showMaximized()

    def _get_improved_list_style(self):
        """Style amélioré pour les listes avec sélection gris clair"""
        return """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
                margin: 2px 0px;
                color: #000000;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            QListWidget::item:selected:hover {
                background-color: #d5d5d5;
                color: #000000;
            }
        """

    def _on_insert_dgraph(self):
        """Insère le profil dans Dgraph après sauvegarde SQLite."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        
        # Étape 1 : Sauvegarder d'abord dans SQLite
        if not self._save_project_to_sqlite(self.current_project_profile_data):
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                "Échec de la sauvegarde dans SQLite. Insertion Dgraph annulée."
            )
            return
        
        QtWidgets.QMessageBox.information(
            self,
            "Succès partiel",
            "Projet sauvegardé dans SQLite. Insertion dans Dgraph en cours..."
        )
        
        # Étape 2 : Insérer dans Dgraph
        mutations = self._transform_profile_to_dgraph_mutations()
        
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                "Inséré dans SQLite et Dgraph avec succès. Ratel ouvert pour vérification."
            )
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.warning(
                self, 
                "Avertissement", 
                "Sauvegardé dans SQLite mais échec insertion Dgraph.\n"
                "Les données sont disponibles dans SQLite."
            )

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 3 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(15)
        main_vertical_layout.setContentsMargins(15, 15, 15, 15)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)

        self.label_uid_to_info = {}
        self.pending_relations = defaultdict(list)
        self.current_selected_label_uid = None

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)

        # Groupe sélection projet
        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.setMinimumWidth(200)
        self.project_combo.setMaximumWidth(350)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        # Bouton "Ajouter"
        self.add_project_button = QtWidgets.QPushButton("Ajouter")
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        # Bouton "Supprimer"
        self.delete_project_button = QtWidgets.QPushButton("Supprimer")
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)

        # Bouton "Uploader"
        self.upload_local_button = QtWidgets.QPushButton("📁 Uploader")
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)

        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        # Groupe détails
        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # Layout horizontal pour le nom du projet avec bouton Parcourir
        project_name_widget = QtWidgets.QWidget()
        project_name_layout = QtWidgets.QHBoxLayout(project_name_widget)
        project_name_layout.setContentsMargins(0, 0, 0, 0)
        project_name_layout.setSpacing(8)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setMinimumWidth(200)
        self.project_name_edit.setMaximumWidth(350)
        project_name_layout.addWidget(self.project_name_edit)

        # Bouton Parcourir
        self.browse_button = QtWidgets.QPushButton("Scanner les noeuds")
        self.browse_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.browse_button.setMaximumWidth(120)
        if hasattr(self, '_on_browse_project'):
            self.browse_button.clicked.connect(self._on_browse_project)
        project_name_layout.addWidget(self.browse_button)

        project_name_layout.addStretch()

        details_form_layout.addRow("", project_name_widget)

        self.project_description_edit = QtWidgets.QTextEdit()
        self.project_description_edit.setPlaceholderText("Description du projet...")
        self.project_description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.project_description_edit.setMaximumHeight(80)
        details_form_layout.addRow("Description:", self.project_description_edit)

        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)

        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(self._get_improved_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        self.cluster_list_widget.currentItemChanged.connect(self._on_cluster_selected)
        cluster_list_layout.addWidget(self.cluster_list_widget)

        cluster_buttons_layout = QtWidgets.QHBoxLayout()
        cluster_buttons_layout.setSpacing(5)

        self.add_cluster_button = QtWidgets.QPushButton("Ajouter")
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)

        self.edit_cluster_button = QtWidgets.QPushButton("Modifier")
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)

        self.remove_cluster_button = QtWidgets.QPushButton("Supprimer")
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)

        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
        cluster_buttons_layout.addStretch()
        cluster_list_layout.addLayout(cluster_buttons_layout)

        details_form_layout.addRow(cluster_list_layout)

        left_column_layout.addWidget(details_group)

        details_selected_group = QtWidgets.QGroupBox("Détails sélectionné")
        details_selected_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_selected_layout = QtWidgets.QVBoxLayout(details_selected_group)
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.details_text.setMaximumHeight(400)
        details_selected_layout.addWidget(self.details_text)
        left_column_layout.addWidget(details_selected_group)

        left_column_layout.addStretch()

        top_columns_layout.addLayout(left_column_layout, 4)

        # --- Colonne du milieu: Hiérarchie (largeur augmentée) ---
        middle_scroll = QtWidgets.QScrollArea()
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setStyleSheet("border: none;")

        middle_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(middle_content)
        hierarchy_layout.setSpacing(8)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)

        hierarchy_group = QtWidgets.QGroupBox(tr("project_config.hierarchy_group"))
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(8)

        # 1. Labels Racines
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(self._get_improved_list_style())
        self.root_list_widget.setMinimumHeight(80)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        root_buttons_layout.setSpacing(5)

        self.add_root_button = QtWidgets.QPushButton("Ajouter")
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)

        self.edit_root_button = QtWidgets.QPushButton("Modifier")
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)

        self.remove_root_button = QtWidgets.QPushButton("Supprimer")
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)

        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        root_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(root_buttons_layout)

        # 2. Labels Niveau 1 (anciennement Parents)
        level1_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        level1_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(level1_label_title)

        self.level1_list_widget = QtWidgets.QListWidget()
        self.level1_list_widget.setStyleSheet(self._get_improved_list_style())
        self.level1_list_widget.setMinimumHeight(80)
        self.level1_list_widget.currentItemChanged.connect(self._on_level1_label_selected)
        hierarchy_group_layout.addWidget(self.level1_list_widget)

        level1_buttons_layout = QtWidgets.QHBoxLayout()
        level1_buttons_layout.setSpacing(5)

        self.add_level1_button = QtWidgets.QPushButton("Ajouter")
        self.add_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_level1_button.clicked.connect(self._add_level1_label)

        self.edit_level1_button = QtWidgets.QPushButton("Modifier")
        self.edit_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_level1_button.clicked.connect(self._edit_level1_label)

        self.remove_level1_button = QtWidgets.QPushButton("Supprimer")
        self.remove_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_level1_button.clicked.connect(self._remove_level1_label)

        level1_buttons_layout.addWidget(self.add_level1_button)
        level1_buttons_layout.addWidget(self.edit_level1_button)
        level1_buttons_layout.addWidget(self.remove_level1_button)
        level1_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(level1_buttons_layout)

        # 3. Labels Enfants (Niveau 2)
        child_label_title = QtWidgets.QLabel("Labels enfants")
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(80)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        child_buttons_layout.setSpacing(5)

        self.add_child_button = QtWidgets.QPushButton("Ajouter")
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)

        self.edit_child_button = QtWidgets.QPushButton("Modifier")
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)

        self.remove_child_button = QtWidgets.QPushButton("Supprimer")
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)

        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)
        child_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_layout.addWidget(hierarchy_group)
        middle_scroll.setWidget(middle_content)
        top_columns_layout.addWidget(middle_scroll, 4)

        # --- Colonne de droite: Relations ---
        right_column_layout = QtWidgets.QVBoxLayout()

        # Configuration des Relations en haut
        relations_group = QtWidgets.QGroupBox("Configuration des Relations")
        relations_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        relations_layout.addWidget(self.global_relations_config)
        right_column_layout.addWidget(relations_group)

        # Section graphe des relations
        graph_group = QtWidgets.QGroupBox("Graphe des Relations")
        graph_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        graph_layout = QtWidgets.QVBoxLayout(graph_group)
        graph_layout.addWidget(self.relations_graph)
        graph_group.setMinimumHeight(400)
        right_column_layout.addWidget(graph_group)

        # Boutons de sauvegarde/export/insert en bas
        save_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("💾 Sauvegarder Profil")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False)
        save_layout.addWidget(self.save_button)

        self.export_profile_button = QtWidgets.QPushButton("📤 Exporter Profil")
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(False)
        save_layout.addWidget(self.export_profile_button)

        self.insert_dgraph_button = QtWidgets.QPushButton("🔄 Insérer dans Dgraph")
        self.insert_dgraph_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.insert_dgraph_button.clicked.connect(self._on_insert_dgraph)
        self.insert_dgraph_button.setEnabled(False)
        save_layout.addWidget(self.insert_dgraph_button)

        right_column_layout.addLayout(save_layout)
        right_column_layout.addStretch()

        top_columns_layout.addLayout(right_column_layout, 5)

    def _load_project_profiles(self):
        """Charge les profils depuis Dgraph."""
        query_result = self.dgraph_connector.query_workspaces()
        if query_result and 'q' in query_result:
            for ws in query_result['q']:
                name = ws.get('name', '')
                self.project_profiles[name] = self._workspace_to_profile(ws)
        self._update_project_combo()

    def _label_to_data(self, label):
        """Convertit un label Dgraph en data local."""
        data = {
            'label': label.get('name', ''),
            'id': label.get('id', ''),
            'uid': label.get('uid', ''),
            'description': label.get('description', ''),
            'category': label.get('category', []),
            'files': label.get('files', []),
            'file_contents': json.loads(label.get('fileContents', '{}')),
            'parents': [],
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': []
        }
        # Outgoing relations
        for rel in label.get('relations', []):
            target = rel.get('target', {})
            data['outgoing_relations'].append({
                'target_uid': target.get('uid', ''),
                'target_id': target.get('id', ''),
                'relation_type': rel.get('relationType')
            })
        # Incoming relations
        for rel in label.get('~relations', []):
            source = rel.get('source', {})
            data['incoming_relations'].append({
                'source_uid': source.get('uid', ''),
                'source_id': source.get('id', ''),
                'relation_type': rel.get('relationType')
            })
        return data

    def _fill_hierarchy(self, data, label_node):
        """Remplit récursivement les enfants et set les parents comme uids."""
        # Gérer l'inconsistance dans les clés de la requête Dgraph ('parents' pour niveau 1, 'children' pour niveau 2)
        children_key = 'children' if 'children' in label_node else 'parents'
        children = label_node.get(children_key, [])
        for child in children:
            child_data = self._label_to_data(child)
            child_data['parents'] = [data['uid']]  # Set parent uid
            data['children'].append(child_data)
            self._fill_hierarchy(child_data, child)

    def _collect_relations(self, profile):
        """Collecte toutes les relations dans pending_relations."""
        pending = defaultdict(list)
        def collect(node):
            label_uid = node['uid']
            # Outgoing
            for rel in node.get('outgoing_relations', []):
                pending[label_uid].append(rel)
            # Incoming: add to source
            for rel in node.get('incoming_relations', []):
                source_uid = rel['source_uid']
                target_uid = label_uid
                rel_type = rel['relation_type']
                pending[source_uid].append({'target_uid': target_uid, 'relation_type': rel_type})
            # Recursive
            for child in node.get('children', []):
                collect(child)
        for cluster in profile['turing_ontology']['clusters_detailed']:
            for root in cluster['root_labels']:
                collect(root)
        profile['pending_relations'] = dict(pending)

    def _workspace_to_profile(self, ws):
        """Convertit un workspace Dgraph en profil local."""
        profile = {
            'uid': ws.get('uid', ''),
            'name': ws.get('name', ''),
            'description': ws.get('description', ''),
            'files': ws.get('files', []),
            'file_contents': json.loads(ws.get('fileContents', '{}')),
            'turing_ontology': {
                'clusters_detailed': []
            },
            'pending_relations': defaultdict(list)
        }
        cm = ws.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_data = {
                'name': cluster.get('name', ''),
                'uid': cluster.get('uid', ''),
                'description': cluster.get('description', ''),
                'files': cluster.get('files', []),
                'file_contents': json.loads(cluster.get('fileContents', '{}')),
                'root_labels': []
            }
            for root_label in cluster.get('root_labels', []):
                root_data = self._label_to_data(root_label)
                cluster_data['root_labels'].append(root_data)
                # Remplir enfants récursivement
                self._fill_hierarchy(root_data, root_label)
            profile['turing_ontology']['clusters_detailed'].append(cluster_data)
        # Collect relations
        self._collect_relations(profile)
        return profile

    def _update_project_combo(self):
        self.project_combo.clear()
        for name in self.project_profiles.keys():
            self.project_combo.addItem(name)

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet dans la combo."""
        if index < 0:
            return
        project_name = self.project_combo.currentText()
        self.current_project_name = project_name
        self.current_project_profile_data = json.loads(json.dumps(self.project_profiles[project_name]))
        # Restore relations
        pending_relations_data = self.current_project_profile_data.get("pending_relations", {})
        self.pending_relations = defaultdict(list, pending_relations_data)
        self._load_project_data_into_ui()
        self._update_project_details()
        self._update_button_states()

    def _load_project_data_into_ui(self):
        """Charge les données du projet dans l'UI avec réinitialisation complète."""
        if not self.current_project_profile_data:
            return

        # Réinitialiser toute la hiérarchie
        self.current_cluster_data = None
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_cluster_index = -1
        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        # Vider toutes les listes
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Charger les informations de base
        self.project_name_edit.setText(self.current_project_profile_data.get('name', ''))
        self.project_description_edit.setPlainText(self.current_project_profile_data.get('description', ''))

        # Charger uniquement la liste des clusters
        self._refresh_cluster_list()

        # Collecter tous les labels pour les relations
        self._collect_all_labels()

        # Réinitialiser les relations et graphe
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

    def _update_project_details(self):
        """Met à jour les détails du projet sélectionné."""
        if self.current_project_name:
            details = f"Projet: {self.current_project_name}\n"
            details += f"Clusters: {len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []))}\n"
            details += f"Fichiers: {len(self.current_project_profile_data.get('files', []))}"
            self.details_text.setPlainText(details)

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters sans charger les niveaux inférieurs."""
        self.cluster_list_widget.clear()
        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        for cluster in clusters:
            self.cluster_list_widget.addItem(cluster["name"])

    def _on_cluster_selected(self, current):    
        """Gère la sélection d'un cluster. Adaptation pour clusters-fichiers."""
        if current:
            self.current_cluster_index = self.cluster_list_widget.row(current)
            self.current_cluster_data = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][self.current_cluster_index]

            self.current_root_data = None
            self.current_level1_data = None
            self.current_level2_data = None
            self.current_root_label_index = -1
            self.current_level1_label_index = -1
            self.current_level2_label_index = -1

            self.level1_list_widget.clear()
            self.child_list_widget.clear()

            is_file_cluster = self.current_cluster_data.get('is_file_cluster', False)
            if is_file_cluster:
                self.root_list_widget.clear()
                self.root_list_widget.setEnabled(False)
                self._update_selected_details("Cluster-Fichier", self.current_cluster_data)
                self.global_relations_config.update_current(None)
                self.relations_graph.update_graph(None)
            else:
                self.root_list_widget.setEnabled(True)
                self._populate_root_list()
                details = f"Cluster: {self.current_cluster_data.get('name', '')}\n"
                details += f"Description: {self.current_cluster_data.get('description', '')}\n"
                details += f"Root Labels: {len(self.current_cluster_data.get('root_labels', []))}\n"
                details += f"Fichiers cluster: {len(self.current_cluster_data.get('files', []))}"
                self.details_text.setPlainText(details)

            self._update_button_states()
        else:
            self.current_cluster_data = None
            self._reset_hierarchy_ui()

        self._update_button_states()

    def _populate_root_list(self):
        """Peuple la liste des root labels pour le cluster sélectionné. Adaptation pour file-clusters."""
        self.root_list_widget.clear()
        if self.current_cluster_data:
            is_file_cluster = self.current_cluster_data.get('is_file_cluster', False)
            if is_file_cluster:
                pass
            else:
                for root in self.current_cluster_data.get("root_labels", []):
                    display = root['label']
                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, root["uid"])
                    self.root_list_widget.addItem(item)
        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """
        Gère la sélection d'un label niveau 1.
        CORRIGÉ: Affiche les classes, fonctions et variables DU FICHIER SÉLECTIONNÉ dans le niveau enfant.
        """
        if current:
            item_type = current.data(Qt.UserRole + 1)
            item_uid = current.data(Qt.UserRole)

            if item_type in ["child", "class", "function", "variable", "file", "folder"]:
                self.current_level1_label_index = self._get_child_index_by_uid(item_uid)
                if self.current_level1_label_index >= 0:
                    self.current_level1_data = self.current_root_data["children"][self.current_level1_label_index]
                    self.current_selected_label_uid = item_uid

                    # Réinitialiser niveau 2
                    self.current_level2_data = None
                    self.current_level2_label_index = -1

                    # Afficher les détails
                    self._update_selected_details(f"{item_type.capitalize()}", self.current_level1_data)

                    # CORRIGÉ: Peupler le niveau enfant UNIQUEMENT avec les classes/fonctions/variables DE CE FICHIER
                    self._populate_children_for_file(self.current_level1_data, self.child_list_widget)

                    # Mettre à jour relations et graphe
                    self.global_relations_config.update_current(self.current_selected_label_uid)
                    self.relations_graph.update_graph(self.current_selected_label_uid)
            else:
                logger.warning(f"Type d'item inconnu: {item_type}")
        else:
            self.current_level1_data = None
            self.current_selected_label_uid = None
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

        self._update_button_states()

    def _populate_level1_list(self):
        """
        Peuple TOUS les enfants du root label : 
        - Hiérarchiques (fichiers/dossiers)
        - Extraits (classes/fonctions/variables du fichier racine)
        """
        self.level1_list_widget.clear()
    
        if not self.current_root_data:
            return
    
        # 1. Afficher les enfants hiérarchiques
        for level1 in self.current_root_data.get("children", []):
            child_type = level1.get('type', 'folder')
            icon = self._get_node_icon(child_type)
            display = f"{icon} {level1.get('label', level1.get('name', 'Sans nom'))}"
    
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, level1.get("uid", level1.get("id", "")))
            item.setData(Qt.UserRole + 1, child_type)
            item.setData(Qt.UserRole + 2, None)  # Pas de ligne
            self.level1_list_widget.addItem(item)
    
        # 2. Afficher les classes du root label lui-même
        classes = self.current_root_data.get('classes', [])
        for cls in classes:
            display = f"🛑 {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)
            
            cls_uid = cls.get('uid', f"cls_{str(uuid.uuid4())}")
            if 'uid' not in cls:
                cls['uid'] = cls_uid
            
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            self.level1_list_widget.addItem(item)
    
        # 3. Afficher les fonctions du root label lui-même
        functions = self.current_root_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "⚙️" if func_type == "method" else "🔧"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)
            
            func_uid = func.get('uid', f"func_{str(uuid.uuid4())}")
            if 'uid' not in func:
                func['uid'] = func_uid
            
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            self.level1_list_widget.addItem(item)
    
        # 4. Afficher les variables du root label
        variables = self.current_root_data.get('variables', [])
        for var in variables:
            display = f"📦 {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)
            
            var_uid = var.get('uid', f"var_{str(uuid.uuid4())}")
            if 'uid' not in var:
                var['uid'] = var_uid
            
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            self.level1_list_widget.addItem(item)
    
        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """Gère la sélection d'un label niveau 1 (fichier, classe, fonction, variable)."""
        if current:
            item_type = current.data(Qt.UserRole + 1)
            item_uid = current.data(Qt.UserRole)
            item_line = current.data(Qt.UserRole + 2)
    
            self.current_selected_label_uid = item_uid
    
            # Cas 1: Élément hiérarchique (sous-dossier/fichier)
            if item_type in ["folder", "file"]:
                self.current_level1_label_index = self._get_child_index_by_uid(item_uid)
    
                if self.current_level1_label_index >= 0:
                    self.current_level1_data = self.current_root_data["children"][self.current_level1_label_index]
                else:
                    self.current_level1_data = None
    
                self.current_level2_data = None
                self.current_level2_label_index = -1
    
                self._update_selected_details(f"Niveau 1 - {item_type.capitalize()}", 
                                             self.current_level1_data if self.current_level1_data else {})
    
                if self.current_level1_data:
                    self._populate_child_list()
                else:
                    self.child_list_widget.clear()
    
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
    
            # Cas 2: Classe extraite
            elif item_type == "class":
                self.current_level1_data = None
                self.current_level2_data = None
    
                class_info = next(
                    (c for c in self.current_root_data.get('classes', []) 
                     if c.get('uid') == item_uid),
                    {}
                )
    
                details = f"=== Classe ===\n\n"
                details += f"Nom: {class_info.get('name', 'N/A')}\n"
                details += f"Ligne: {item_line}\n"
                details += f"Fichier: {self.current_root_data.get('label', 'N/A')}\n"
                details += f"Description: {class_info.get('description', 'N/A')}\n"
    
                methods = class_info.get('methods', [])
                if methods:
                    details += f"\nMéthodes ({len(methods)}):\n"
                    for method in methods[:10]:
                        details += f"  - {method.get('name', 'N/A')} (ligne {method.get('line', '?')})\n"
                    if len(methods) > 10:
                        details += f"  ... et {len(methods) - 10} autres\n"
    
                self.details_text.setPlainText(details)
                self.child_list_widget.clear()
    
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
    
            # Cas 3: Fonction/Méthode extraite
            elif item_type in ["function", "method"]:
                self.current_level1_data = None
                self.current_level2_data = None
    
                func_info = next(
                    (f for f in self.current_root_data.get('functions', []) 
                     if f.get('uid') == item_uid),
                    {}
                )
    
                details = f"=== {'Méthode' if item_type == 'method' else 'Fonction'} ===\n\n"
                details += f"Nom: {func_info.get('name', 'N/A')}\n"
                details += f"Type: {func_info.get('type', 'N/A')}\n"
                details += f"Ligne: {item_line}\n"
                details += f"Fichier: {self.current_root_data.get('label', 'N/A')}\n"
                details += f"Description: {func_info.get('description', 'N/A')}\n"
    
                params = func_info.get('params', [])
                if params:
                    details += f"\nParamètres ({len(params)}):\n"
                    for param in params:
                        details += f"  - {param.get('name', 'param')}: {param.get('type', 'N/A')}\n"
    
                returns = func_info.get('returns', {})
                if returns:
                    details += f"\nRetour: {returns.get('type', 'N/A')}\n"
    
                self.details_text.setPlainText(details)
                self.child_list_widget.clear()
    
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
    
            # Cas 4: Variable extraite
            elif item_type == "variable":
                self.current_level1_data = None
                self.current_level2_data = None
    
                var_info = next(
                    (v for v in self.current_root_data.get('variables', []) 
                     if v.get('uid') == item_uid),
                    {}
                )
    
                details = f"=== Variable ===\n\n"
                details += f"Nom: {var_info.get('name', 'N/A')}\n"
                details += f"Type: {var_info.get('type', 'N/A')}\n"
                details += f"Ligne: {item_line}\n"
                details += f"Fichier: {self.current_root_data.get('label', 'N/A')}\n"
                details += f"Scope: {var_info.get('scope', 'N/A')}\n"
                details += f"Description: {var_info.get('description', 'N/A')}\n"
    
                self.details_text.setPlainText(details)
                self.child_list_widget.clear()
    
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
    
        else:
            self.current_level1_data = None
            self.current_selected_label_uid = None
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)
    
        self._update_button_states()

    def _populate_child_list(self):
        """
        Peuple le niveau 2 avec les enfants hiérarchiques du level1 sélectionné,
        y compris les sous-dossiers imbriqués.
        """
        self.child_list_widget.clear()

        if not self.current_level1_data:
            return

        # Afficher tous les enfants de manière récursive avec indentation
        for child in self.current_level1_data.get("children", []):
            self._add_child_to_list(child, self.child_list_widget)

        self._update_button_states()

    def _add_child_to_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste, récursivement pour les sous-dossiers.
        SANS icônes.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_list(grandchild, list_widget, indent + "  ")

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        Peuple la liste enfant avec la hiérarchie correcte:
        - Classes (avec sous-items méthodes)
        - Fonctions
        - Variables

        Chaque élément peut être sélectionné pour voir ses relations et détails.
        """
        list_widget.clear()
        if not file_data:
            return

        children = file_data.get('children', [])

        if not children:
            list_widget.addItem(QListWidgetItem("(Aucun élément trouvé)"))
            return

        # Afficher les enfants organisés par type
        for child in children:
            child_type = child.get('type', 'unknown')
            child_uid = child.get('uid')

            if not child_uid:
                child_uid = child.get('id', str(uuid.uuid4()))
                child['uid'] = child_uid

            # === CLASSE ===
            if child_type == 'class':
                icon = '[CLS]'
                class_name = child.get('name', 'Class')
                line_num = child.get('line', '?')
                methods_count = len(child.get('children', []))

                # Format: [CLS] ClassName (3 methods) - line 42
                display = f"{icon} {class_name}"
                if methods_count > 0:
                    display += f" ({methods_count} methods)"
                display += f" - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'class')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#FF9800"))  # Orange
                list_widget.addItem(item)

                # Ajouter les méthodes comme sous-items indentés
                for method in child.get('children', []):
                    method_uid = method.get('uid')
                    if not method_uid:
                        method_uid = str(uuid.uuid4())
                        method['uid'] = method_uid

                    method_name = method.get('name', 'method')
                    method_line = method.get('line', '?')

                    # Indentation pour sous-item
                    method_display = f"  ├─ {method_name} (ligne {method_line})"
                    method_item = QListWidgetItem(method_display)
                    method_item.setData(Qt.UserRole, method_uid)
                    method_item.setData(Qt.UserRole + 1, 'method')
                    method_item.setData(Qt.UserRole + 2, method_line)
                    method_item.setForeground(QtGui.QColor("#FFA500"))  # Orange clair
                    list_widget.addItem(method_item)

            # === FONCTION ===
            elif child_type in ['function', 'method']:
                icon = '[FNC]'
                func_name = child.get('name', 'Function')
                line_num = child.get('line', '?')
                func_type = child.get('type', 'function')

                display = f"{icon} {func_name} - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, func_type)
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#2196F3"))  # Bleu
                list_widget.addItem(item)

            # === VARIABLE ===
            elif child_type == 'variable':
                icon = '[VAR]'
                var_name = child.get('name', 'Variable')
                var_type = child.get('var_type', 'local')
                line_num = child.get('line', '?')

                display = f"{icon} {var_name} ({var_type}) - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'variable')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#4CAF50"))  # Vert
                list_widget.addItem(item)

            # === AUTRES (fichiers, dossiers, etc.) ===
            else:
                icon = self._get_node_icon(child_type)
                child_name = child.get('label', child.get('name', 'unknown'))

                display = f"{icon} {child_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _on_child_label_selected(self, current):
        """
        Gère la sélection d'un enfant au niveau 2.
        """
        if current:
            item_type = current.data(Qt.UserRole + 1)
            item_uid = current.data(Qt.UserRole)

            self.current_selected_label_uid = item_uid

            # Chercher cet enfant dans la structure (peut être imbriqué)
            child_data = self._find_child_by_uid(self.current_level1_data, item_uid)

            if child_data:
                self.current_level2_data = child_data

                # Afficher les détails
                details = f"Nom: {child_data.get('label', child_data.get('name', 'N/A'))}\n"
                details += f"Type: {item_type}\n"
                details += f"UID: {item_uid}\n"
                details += f"Description: {child_data.get('description', 'N/A')}\n"

                # Si c'est un fichier, afficher son contenu
                files = child_data.get('files', [])
                if files:
                    details += f"\nFichiers: {len(files)}\n"
                    for f in files[:5]:
                        details += f"  - {f}\n"
                    if len(files) > 5:
                        details += f"  ... et {len(files) - 5} autres\n"

                self.details_text.setPlainText(details)

                # Mettre à jour relations et graphe
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
            else:
                self.details_text.clear()

        else:
            self.current_level2_data = None
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

        self._update_button_states()
    
    def _on_any_label_selected(self, current):
        """
        Handles selection of ANY label (root, level1, level2, child).
        Updates relations config and graph for the selected node.

        This is a unified handler to avoid code duplication across different
        list widgets.
        """
        if current:
            # Get UID from the selected item
            uid = current.data(Qt.UserRole)

            if not uid:
                logger.warning("Selected item has no UID")
                self.current_selected_label_uid = None
                self.global_relations_config.update_current(None)
                self.relations_graph.update_graph(None)
                return

            self.current_selected_label_uid = uid

            # Update relations config and graph
            self.global_relations_config.update_current(uid)
            self.relations_graph.update_graph(uid)

            logger.debug(f"Label sélectionné: {uid}")
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _on_any_label_selected(self, current):
        """Gère la sélection de n'importe quel label pour relations et graphe."""
        if current:
            self.current_selected_label_uid = current.data(Qt.UserRole)
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _update_selected_details(self, title, data):
        """Met à jour les détails de l'élément sélectionné. Amélioration pour clusters-fichiers."""
        if not data:
            self.details_text.clear()
            return

        is_file_cluster = data.get('is_file_cluster', False)
        if is_file_cluster:
            details = f"=== {title} ===\n\n"
            details += f"Nom: {data.get('name', '')}\n"
            details += f"Description: {data.get('description', '')}\n\n"
            files = data.get('files', [])
            if files:
                details += f"Fichier: {files[0]}\n"  # Un seul fichier pour file-cluster
                content = data.get('file_contents', {}).get(files[0], '')
                details += f"Contenu (résumé): {content[:200]}..." if len(content) > 200 else f"Contenu: {content}"
            else:
                details += "Aucun fichier associé\n"
            # Pas de hiérarchie/relations pour file-cluster
            details += "\nNote: Pas de hiérarchie ni relations pour un cluster-fichier."
            self.details_text.setPlainText(details)
            return

        # Comportement normal pour labels (inchangé)
        details = f"=== {title} ===\n\n"
        details += f"Nom: {data.get('label', '')}\n"
        details += f"ID: {data.get('id', '')}\n"
        details += f"UID: {data.get('uid', '')}\n"
        details += f"Description: {data.get('description', '')}\n\n"

        categories = data.get('category', [])
        if categories:
            details += f"Catégories: {', '.join(categories)}\n\n"

        files = data.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:10]:  # Limiter à 10 fichiers pour l'affichage
                details += f"  - {f}\n"
            if len(files) > 10:
                details += f"  ... et {len(files) - 10} autres\n"
        else:
            details += "Aucun fichier associé\n"

        # Relations sortantes
        outgoing = data.get('outgoing_relations', [])
        if outgoing:
            details += f"\nRelations sortantes ({len(outgoing)}):\n"
            for r in outgoing:
                target_name = self.label_uid_to_info.get(r['target_uid'], {}).get('name', 'Inconnu')
                details += f"  {r['relation_type'].upper()} -> {target_name}\n"

        # Relations entrantes
        incoming = data.get('incoming_relations', [])
        if incoming:
            details += f"\nRelations entrantes ({len(incoming)}):\n"
            for r in incoming:
                source_name = self.label_uid_to_info.get(r['source_uid'], {}).get('name', 'Inconnu')
                details += f"  {source_name} {r['relation_type'].upper()} -> \n"

        # Ajouter info sur la hiérarchie
        if title == "Label Racine":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"
        elif title == "Label Niveau 1":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"

        self.details_text.setPlainText(details)

    def _reset_hierarchy_ui(self):
        """Réinitialise complètement l'interface hiérarchique."""
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

        self.details_text.clear()

    def _collect_all_labels(self):
        """
        MODIFIÉE: Collecte tous les labels ET les classes, fonctions, variables
        pour les ajouter à label_uid_to_info.
        """
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()

        if not self.current_project_profile_data:
            return

        ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = ontology.get("clusters_detailed", [])

        for cluster in clusters_detailed:
            cluster_name = cluster.get('name', '')
            root_labels = cluster.get("root_labels", [])

            for root in root_labels:
                uid = root.get('uid') or root.get('id') or str(uuid.uuid4())

                # S'assurer que uid est défini
                if 'uid' not in root:
                    root['uid'] = uid

                info = {'name': root.get('label', ''), 'cluster': cluster_name, 'type': 'label'}
                self.label_uid_to_info[uid] = info
                self.name_to_uid[root.get('label', '')] = uid

                # Collecter récursivement les enfants et les classes/fonctions/variables
                self._collect_labels_recursive(root, cluster_name)

    def _collect_labels_recursive(self, node, cluster_name=''):
        """
        MODIFIÉE: Collecte récursivement labels, classes, fonctions et variables
        dans label_uid_to_info.
        """
        children = node.get('children', [])

        for child in children:
            # Safe fallback: priorité uid > id > générer nouveau
            uid = child.get('uid')
            if not uid:
                uid = child.get('id')
            if not uid:
                uid = str(uuid.uuid4())

            # S'assurer que uid est défini sur le nœud
            if 'uid' not in child:
                child['uid'] = uid

            # Récupérer le cluster du parent
            parent_uid = node.get('uid')
            parent_cluster = self.label_uid_to_info.get(parent_uid, {}).get('cluster', cluster_name)

            info = {
                'name': child.get('label', ''),
                'cluster': parent_cluster,
                'type': child.get('type', 'label')
            }
            self.label_uid_to_info[uid] = info

            label_name = child.get('label', '')
            if label_name:
                self.name_to_uid[label_name] = uid

            # Appel récursif pour les enfants
            self._collect_labels_recursive(child, parent_cluster)

        # NOUVEAU: Collecter les classes du nœud courant
        classes = node.get('classes', [])
        for cls in classes:
            cls_uid = cls.get('uid', f"cls_{cls.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            info = {
                'name': cls.get('name', ''),
                'cluster': cluster_name,
                'type': 'class',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[cls_uid] = info

        # NOUVEAU: Collecter les fonctions du nœud courant
        functions = node.get('functions', [])
        for func in functions:
            func_uid = func.get('uid', f"func_{func.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in func:
                func['uid'] = func_uid

            info = {
                'name': func.get('name', ''),
                'cluster': cluster_name,
                'type': 'function',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[func_uid] = info

        # NOUVEAU: Collecter les variables du nœud courant
        variables = node.get('variables', [])
        for var in variables:
            var_uid = var.get('uid', f"var_{var.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in var:
                var['uid'] = var_uid

            info = {
                'name': var.get('name', ''),
                'cluster': cluster_name,
                'type': 'variable',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[var_uid] = info

    def _add_cluster(self):
        dialog = AddEditItemDialog("Ajouter Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "files": [],
                    "file_contents": {},
                    "root_labels": []
                }
                self.current_project_profile_data["turing_ontology"]["clusters_detailed"].append(new_cluster)
                self._refresh_cluster_list()
                self._collect_all_labels()
                self.cluster_list_widget.setCurrentRow(self.cluster_list_widget.count() - 1)
                self._update_button_states()
                logger.info(f"Cluster ajouté: {data['name']}")

    def _edit_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
        dialog = AddEditItemDialog("Modifier Cluster", cluster["name"], cluster["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                cluster["name"] = data["name"]
                cluster["description"] = data["description"]
                self._refresh_cluster_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Cluster modifié: {data['name']}")

    def _remove_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster_name = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]["name"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le cluster '{cluster_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
            self._refresh_cluster_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Cluster supprimé: {cluster_name}")

    def _add_root_label(self):
        """Ajoute un label racine avec vérification des fichiers."""
        if not self.current_cluster_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Racine", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_root = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_cluster_data["root_labels"].append(new_root)
                self._populate_root_list()
                self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine ajouté: {data['name']}")

    def _edit_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root = self.current_cluster_data["root_labels"][index]
        dialog = AddEditItemDialog("Modifier Label Racine", root["label"], root["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                root["label"] = data["name"]
                root["description"] = data["description"]
                self._populate_root_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine modifié: {data['name']}")

    def _remove_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root_name = self.current_cluster_data["root_labels"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label racine '{root_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data["root_labels"][index]
            self._populate_root_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label racine supprimé: {root_name}")

    def _add_level1_label(self):
        """Ajoute un label niveau 1 avec vérification des fichiers."""
        if not self.current_root_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 1", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_level1 = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_root_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_root_data["children"].append(new_level1)
                self._populate_level1_list()
                self.level1_list_widget.setCurrentRow(self.level1_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 ajouté: {data['name']}")

    def _edit_level1_label(self):
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1 = self.current_root_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 1", level1["label"], level1["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                level1["label"] = data["name"]
                level1["description"] = data["description"]
                self._populate_level1_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 modifié: {data['name']}")

    def _remove_level1_label(self): 
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1_name = self.current_root_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 1 '{level1_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_root_data["children"][index]
            self._populate_level1_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 1 supprimé: {level1_name}")

    def _add_child_label(self):
        """Ajoute un label enfant avec vérification des fichiers."""
        if not self.current_level1_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 2", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_child = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_level1_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_level1_data["children"].append(new_child)
                self._populate_child_list()
                self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 ajouté: {data['name']}")

    def _edit_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child = self.current_level1_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 2", child["label"], child["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                child["label"] = data["name"]
                child["description"] = data["description"]
                self._populate_child_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 modifié: {data['name']}")

    def _remove_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child_name = self.current_level1_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 2 '{child_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_level1_data["children"][index]
            self._populate_child_list()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 2 supprimé: {child_name}")

    def _add_all_files_from_dir(self, dir_path, base_dir, label, profile):
        """Ajoute récursivement tous les fichiers d'un dossier à un label."""
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                content = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                label['files'].append(rel_path)
                label['file_contents'][rel_path] = content

    def _build_sub_hierarchy(self, dir_path, base_dir, parent_label, is_parents=True, profile=None):
        """Construit la hiérarchie récursivement à partir d'un dossier."""
        level_key = 'children' if is_parents else 'children'
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
            if os.path.isfile(item_path):
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                if profile:
                    profile['files'].append(rel_path)
                    profile['file_contents'][rel_path] = content
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
            elif os.path.isdir(item_path):
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'files': [],
                    'file_contents': {},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
                if is_parents:
                    self._build_sub_hierarchy(item_path, base_dir, new_label, False, profile)
                else:
                    # Pour le niveau children, ajouter les fichiers profonds au label
                    self._add_all_files_from_dir(item_path, base_dir, new_label, profile)

    def _scan_project_directory(self, directory):
        """Scanne un dossier et crée une structure hiérarchique avec un cluster par élément de niveau supérieur."""
        profile = {
            'name': os.path.basename(directory),
            'description': f"Projet importé depuis {directory}",
            'files': [],
            'file_contents': {},
            'turing_ontology': {
                'clusters_detailed': []
            },
            'pending_relations': {}
        }
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            cluster = {
                'name': item,
                'uid': str(uuid.uuid4()),
                'description': f"{'Fichier' if os.path.isfile(item_path) else 'Dossier'}: {item}",
                'files': [],
                'file_contents': {},
                'root_labels': [],
                'is_file_cluster': False  # Nouveau flag
            }
            if os.path.isfile(item_path):
                # Traitement pour fichier : associer directement au cluster, sans root_labels
                rel_path = item
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                cluster['files'].append(rel_path)
                cluster['file_contents'][rel_path] = content
                cluster['is_file_cluster'] = True  # Flag pour indiquer cluster-fichier
                cluster['description'] += f"\nContenu résumé: {content[:100]}..." if len(content) > 100 else f"\nContenu: {content}"
            elif os.path.isdir(item_path):
                # Comportement inchangé pour dossiers : créer root_labels
                cluster['is_file_cluster'] = False
                # Ajouter les contenus directs comme root_labels
                for subitem in sorted(os.listdir(item_path)):
                    subitem_path = os.path.join(item_path, subitem)
                    sub_rel_path = os.path.relpath(subitem_path, directory)
                    if os.path.isfile(subitem_path):
                        content = ''
                        try:
                            with open(subitem_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read {subitem_path}: {e}")
                        profile['files'].append(sub_rel_path)
                        profile['file_contents'][sub_rel_path] = content
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'uid': str(uuid.uuid4()),
                            'description': f"Fichier: {sub_rel_path}",
                            'category': ['file'],
                            'files': [sub_rel_path],
                            'file_contents': {sub_rel_path: content},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                    elif os.path.isdir(subitem_path):
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'uid': str(uuid.uuid4()),
                            'description': f"Dossier: {sub_rel_path}",
                            'category': ['folder'],
                            'files': [],
                            'file_contents': {},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                        # Construire la hiérarchie pour ce sous-dossier
                        self._build_sub_hierarchy(subitem_path, directory, new_root, True, profile)
            profile['turing_ontology']['clusters_detailed'].append(cluster)
        logger.info(f"Scanné {len(profile['files'])} fichiers depuis {directory}")
        return profile

    def _on_upload_local_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet local")
        if directory:
            scanned_data = self._scan_project_directory(directory)
            project_name = scanned_data['name']
            self.project_profiles[project_name] = json.loads(json.dumps(scanned_data))
            self._update_project_combo()
            self.project_combo.setCurrentText(project_name)
            self._on_project_selected(self.project_combo.currentIndex())
            logger.info(f"Upload local complété pour: {directory}")

    def _on_add_new_project(self):
        """Crée un nouveau projet vide."""
        dialog = AddEditItemDialog("Nouveau Projet", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                project_name = data["name"]
                self.project_profiles[project_name] = {
                    'name': project_name,
                    'description': data["description"],
                    'files': [],
                    'file_contents': {},
                    'turing_ontology': {
                        'clusters_detailed': []
                    },
                    'pending_relations': {}
                }
                self._update_project_combo()
                self.project_combo.setCurrentText(project_name)
                self._on_project_selected(self.project_combo.currentIndex())
                logger.info(f"Nouveau projet créé : {project_name}")

    def _on_delete_project(self):
        """Suppression complète d'un projet depuis l'UI, Dgraph et SQLite."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        project_name = self.project_combo.currentText()
        uid = self.current_project_profile_data.get('uid') if self.current_project_profile_data else None

        if not uid:
            logger.warning(f"Aucun UID trouvé pour le projet {project_name}")
            QtWidgets.QMessageBox.warning(self, "Erreur", f"UID manquant pour '{project_name}'.")
            return

        # Confirmation utilisateur
        reply = QtWidgets.QMessageBox.question(
            self,
            "Suppression du projet",
            f"Voulez-vous vraiment supprimer le projet '{project_name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            uids_to_delete = self._collect_uids_to_delete(uid)
            if not uids_to_delete:
                logger.warning("Aucun UID à supprimer.")
                return

            # Supprimer de Dgraph si disponible
            dgraph_deleted = True
            if self.dgraph_connector.client:
                dgraph_deleted = self._collect_and_delete_uids(uids_to_delete, project_name)

            # Supprimer de SQLite via CRUD
            sqlite_deleted = self._delete_project_from_sqlite(uid)

            if dgraph_deleted and sqlite_deleted:
                logger.info(f"Supprimé de Dgraph et SQLite : {project_name}")

                # Supprimer du cache local
                if project_name in self.project_profiles:
                    del self.project_profiles[project_name]
                self._update_project_combo()  # Refresh la combo

                # Reset UI
                self._reset_ui()
                self.current_project_name = None

                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé.")
            else:
                QtWidgets.QMessageBox.warning(self, "Partiel", f"Supprimé de {'Dgraph et ' if dgraph_deleted else ''}SQLite, mais échec sur {'Dgraph' if not dgraph_deleted else 'SQLite'}.")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression : {e}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur : {str(e)}")

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters."""
        # Guard pour éviter AttributeError si current_project_profile_data est None
        if not self.current_project_profile_data:
            self.cluster_list_widget.clear()
            self._update_button_states()
            return

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        self.cluster_list_widget.clear()
        for cluster in clusters:
            item = QListWidgetItem(cluster['name'])
            item.setData(Qt.UserRole, cluster)
            self.cluster_list_widget.addItem(item)
        self._update_button_states()

    def _collect_uids_to_delete(self, uid):
        """
        Collecte récursivement tous les UIDs à supprimer liés à un workspace.
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph client non initialisé.")
            return []

        uids_to_delete = set()

        # Requête récursive pour collecter tous les noeuds liés
        gc_query = f"""
        {{
          nodes(func: uid({uid})) @recurse(loop: false) {{
            uid
            children
            parents
            clusters
            relations
            imports
          }}
        }}
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp_gc = txn.query(gc_query)
            txn.discard()

            data_gc = self.dgraph_connector._parse_response(resp_gc)
            for node in data_gc.get('nodes', []):
                if 'uid' in node:
                    uids_to_delete.add(node['uid'])

            logger.info(f"{len(uids_to_delete)} UID(s) collecté(s) pour suppression.")
            return list(uids_to_delete)

        except Exception as e:
            logger.error(f"Erreur lors de la collecte des UID à supprimer : {e}")
            return []

    def _collect_and_delete_uids(self, uids, project_name=None):
        """Supprime les UIDs collectés via mutation DELETE + vérif post-suppression dynamique (non-bloquante)."""
        if not uids or not self.dgraph_connector.client:
            return False

        txn = self.dgraph_connector.client.txn()
        committed = False
        try:
            del_objs = [{"uid": uid} for uid in uids]
            assigned = txn.mutate(del_obj=del_objs)
            txn.commit()
            committed = True
            logger.info(f"Supprimés {len(uids)} nœuds avec succès.")

            # Vérification optionnelle : Dynamique sur le nom du projet
            if project_name:
                try:
                    # Échappement basique pour le regexp (ajustez si noms complexes)
                    escaped_name = project_name.replace('/', '\\/').replace('\\', '\\\\')
                    verify_query = f"""
                    {{
                      q(func: has(name)) @filter(regexp(name, /.*{escaped_name}.*/i)) {{
                        uid
                      }}
                    }}
                    """
                    txn_verify = self.dgraph_connector.client.txn(read_only=True)
                    resp_verify = txn_verify.query(verify_query)
                    txn_verify.discard()
                    data_verify = self.dgraph_connector._parse_response(resp_verify)
                    remaining = len(data_verify.get('q', []))
                    if remaining > 0:
                        logger.warning(f"ATTENTION : {remaining} résidus pour '{project_name}' encore présents après suppression. Relance manuelle recommandée.")
                    else:
                        logger.info(f"Vérification OK : Aucune résidu pour '{project_name}' trouvé.")
                except Exception as ve:
                    logger.warning(f"Vérification post-suppression pour '{project_name}' échouée (non critique) : {ve}. La suppression principale a réussi.")

            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression principale : {e}")
            return False
        finally:
            if not committed:
                txn.discard()

    def _reset_ui(self):
        """Reset l'UI."""
        self.current_project_name = None

        # Appel AVANT le reset des données pour éviter AttributeError
        self._refresh_cluster_list()

        # Maintenant safe de set à None
        self.current_project_profile_data = None
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self._reset_hierarchy_ui()
        self.pending_relations.clear()
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)
        self._update_button_states()

        # Log pour debug
        logger.info("UI reset complété.")

    def _on_save_project(self):
        """Sauvegarde le profil local."""
        if not self.current_project_name:
            return
        self.current_project_profile_data['name'] = self.project_name_edit.text().strip()
        self.current_project_profile_data['description'] = self.project_description_edit.toPlainText().strip()
        self.current_project_profile_data['pending_relations'] = dict(self.pending_relations)
        self.project_profiles[self.current_project_name] = json.loads(json.dumps(self.current_project_profile_data))
        self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
        logger.info(f"Profil sauvegardé : {self.current_project_name}")

    def _on_export_profile(self):
        """Exporte le profil en JSON."""
        if not self.current_project_name:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Profil", f"{self.current_project_name}.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.current_project_profile_data, f, indent=4)
            logger.info(f"Profil exporté : {file_path}")

    def _on_insert_dgraph(self):
        """Insère le profil dans Dgraph après sauvegarde SQLite."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        
        # Étape 1 : Sauvegarder d'abord dans SQLite (via CRUD)
        if not self._save_project_to_sqlite(self.current_project_profile_data):
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                "Échec de la sauvegarde dans SQLite. Insertion Dgraph annulée."
            )
            return
        
        QtWidgets.QMessageBox.information(
            self,
            "Succès partiel",
            "Projet sauvegardé dans SQLite. Insertion dans Dgraph en cours..."
        )
        
        # Étape 2 : Insérer dans Dgraph
        mutations = self._transform_profile_to_dgraph_mutations()
        
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                "Inséré dans SQLite et Dgraph avec succès. Ratel ouvert pour vérification."
            )
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh Dgraph
            self._load_projects_from_sqlite()  # Refresh SQLite
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.warning(
                self, 
                "Avertissement", 
                "Sauvegardé dans SQLite mais échec insertion Dgraph.\n"
                "Les données sont disponibles dans SQLite."
            )

    def is_configured(self):
        """Vérifie si la config est complète."""
        return (self.current_project_profile_data and
                self.project_name_edit.text().strip() and
                len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])) > 0)

    def _create_label_mutation(self, label_data, level, cluster_uid):
        """Crée une mutation pour un label avec ses fichiers."""
        uid = f"_:label_{label_data.get('uid', str(uuid.uuid4()))}"
        
        # S'assurer que les fichiers sont bien présents
        files = label_data.get('files', [])
        file_contents = label_data.get('file_contents', {})
        
        label = {
            "uid": uid,
            "dgraph.type": "Label",
            "name": label_data.get("label", label_data.get("name", "")),
            "id": label_data.get("id", str(uuid.uuid4())),
            "level": level,
            "path": "",
            "category": label_data.get("category", []),
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z",
            "parentId": "",
            "nodeType": "label",
            "description": label_data.get("description", ""),
            "codeContent": "",
            "files": files,
            "fileContents": json.dumps(file_contents),
            "clusters": [{"uid": cluster_uid}]
        }
        return label

    def _transform_profile_to_dgraph_mutations(self):
        """Transforme le profil actuel en mutations Dgraph avec gestion complète de la hiérarchie."""
        if not self.current_project_profile_data:
            return []

        mutations = []

        # Créer Workspace
        workspace = {
            "uid": "_:workspace_uid",
            "dgraph.type": "Workspace",
            "name": self.current_project_profile_data.get("name", ""),
            "id": self.current_project_profile_data.get("name", str(uuid.uuid4())),
            "ownerId": "user1",
            "description": self.current_project_profile_data.get("description", ""),
            "updatedAt": datetime.now().isoformat() + "Z",
            "files": self.current_project_profile_data.get("files", []),
            "fileContents": json.dumps(self.current_project_profile_data.get("file_contents", {}))
        }
        mutations.append(workspace)

        # Créer ClusterManagement
        cluster_management = {
            "uid": "_:cm_uid",
            "dgraph.type": "ClusterManagement",
            "lastUpdated": datetime.now().isoformat() + "Z",
            "version": "1.0",
            "clusters": []
        }
        mutations.append(cluster_management)

        # Lier ClusterManagement au Workspace
        workspace["clusterManagement"] = {"uid": "_:cm_uid"}

        turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = turing_ontology.get("clusters_detailed", [])

        label_uids = {}  # Map label uid to dgraph uid

        for cluster_data in clusters_detailed:
            cluster_uid = f"_:cluster_{cluster_data.get('uid', str(uuid.uuid4()))}"
            cluster = {
                "uid": cluster_uid,
                "dgraph.type": "Cluster",
                "name": cluster_data.get("name", ""),
                "id": cluster_data.get("uid", str(uuid.uuid4())),
                "userId": "user1",
                "nodeType": "cluster",
                "description": cluster_data.get("description", ""),
                "codeContent": "",
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z",
                "files": cluster_data.get("files", []),
                "fileContents": json.dumps(cluster_data.get("file_contents", {})),
                "root_labels": []
            }
            mutations.append(cluster)
            cluster_management["clusters"].append({"uid": cluster_uid})

            # Créer root_labels avec leurs hiérarchies complètes
            root_labels = cluster_data.get("root_labels", [])
            for root in root_labels:
                # Créer le root label
                root_label = self._create_label_mutation(root, level=0, cluster_uid=cluster_uid)
                mutations.append(root_label)
                cluster["root_labels"].append({"uid": root_label["uid"]})
                label_uids[root['uid']] = root_label["uid"]

                # Traiter récursivement la hiérarchie complète
                self._process_hierarchy_recursive(
                    root, 
                    root_label, 
                    cluster_uid, 
                    mutations, 
                    label_uids, 
                    level=1
                )

        # Ajouter les relations après création de tous les labels
        for source_uid, rels in self.pending_relations.items():
            for rel in rels:
                if source_uid in label_uids and rel['target_uid'] in label_uids:
                    relation = {
                        "uid": f"_:rel_{uuid.uuid4()}",
                        "dgraph.type": "Relation",
                        "name": f"Relation {rel['relation_type']}",
                        "relationType": rel['relation_type'],
                        "source": {"uid": label_uids[source_uid]},
                        "target": {"uid": label_uids[rel['target_uid']]}
                    }
                    mutations.append(relation)

        return mutations
    
    def _process_hierarchy_recursive(self, node_data, parent_mutation, cluster_uid, 
                                 mutations, label_uids, level):
        """
        Traite récursivement la hiérarchie en créant les mutations.
        Utilise le prédicat 'parents' sur l'enfant pour lier au parent (reverse ~parents).
        """
        children_list = node_data.get('children', [])

        if not children_list:
            return

        parent_uid = parent_mutation["uid"]

        for child_data in children_list:
            # Créer la mutation pour cet enfant
            child_mutation = self._create_label_mutation(
                child_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
            mutations.append(child_mutation)

            # Enregistrer l'UID
            label_uids[child_data['uid']] = child_mutation["uid"]

            # Lier au parent via 'parents' sur l'enfant
            if "parents" not in child_mutation:
                child_mutation["parents"] = []
            child_mutation["parents"].append({"uid": parent_uid})

            # Définir le parentId (string)
            child_mutation["parentId"] = node_data.get('uid', '')

            # Traiter récursivement les enfants de cet enfant
            self._process_hierarchy_recursive(
                child_data,
                child_mutation,
                cluster_uid,
                mutations,
                label_uids,
                level + 1
            )

    def _update_button_states(self):
        """Met à jour l'état des boutons en fonction de la sélection."""
        has_project = bool(self.current_project_name)
        self.delete_project_button.setEnabled(has_project)
        self.save_button.setEnabled(has_project)
        self.export_profile_button.setEnabled(has_project)
        self.insert_dgraph_button.setEnabled(has_project and self.is_configured())
    
        has_cluster = bool(self.current_cluster_data)
        self.add_root_button.setEnabled(has_cluster)
        self.edit_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
        self.remove_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
    
        has_root = bool(self.current_root_data)
        self.add_level1_button.setEnabled(has_root)
        self.edit_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.remove_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
    
        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(has_level1)
        self.edit_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(self.child_list_widget.currentRow() != -1)

        # Boutons relations
        has_source = bool(self.current_selected_label_uid)
        self.global_relations_config.add_button.setEnabled(has_source and len(self.label_uid_to_info) > 1)
        has_rel_selected = self.global_relations_config.relations_list.currentRow() != -1
        self.global_relations_config.edit_button.setEnabled(has_rel_selected)
        self.global_relations_config.remove_button.setEnabled(has_rel_selected)

    def _on_browse_project(self):
        """
        Bouton 'Afficher les nœuds' – scanne le projet et analyse les fichiers.
        CORRIGÉ: Appelle _collect_all_labels() APRÈS l'analyse.
        """
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(
                self, 
                "Erreur", 
                "Aucun projet sélectionné dans la configuration."
            )
            return

        project_name = self.current_project_profile_data.get("name", "Projet inconnu")
        files = self.current_project_profile_data.get("files", [])
        file_contents = self.current_project_profile_data.get("file_contents", {})

        if not files:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun fichier trouvé",
                f"Aucun fichier enregistré pour le projet '{project_name}'."
            )
            return

        logger.info(f"Analyse du projet '{project_name}' chargé depuis Dgraph/SQLite...")

        progress = QtWidgets.QProgressDialog(
            "Analyse des fichiers du projet...", 
            "Annuler", 
            0, 
            len(files), 
            self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)

        # Mémoriser la sélection actuelle
        current_cluster_row = self.cluster_list_widget.currentRow()
        current_root_row = -1

        if (current_cluster_row != -1 and self.current_cluster_data and 
            not self.current_cluster_data.get('is_file_cluster')):
            current_root_row = self.root_list_widget.currentRow()

        try:
            # Récupérer les clusters existants
            clusters_detailed = self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])

            if not clusters_detailed:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucun cluster",
                    "Aucun cluster trouvé dans le projet. Créez d'abord des clusters."
                )
                return

            # Mapper les fichiers aux clusters existants par chemin
            file_to_cluster = {}

            for cluster in clusters_detailed:
                cluster_path = cluster.get('path', '')
                cluster_name = cluster.get('name', '')

                for file_path in files:
                    if cluster_path and file_path.startswith(cluster_path):
                        file_to_cluster[file_path] = cluster_name
                    elif not cluster_path:
                        first_dir = file_path.split(os.sep)[0] if os.sep in file_path else file_path
                        if first_dir == cluster_name or cluster_name == first_dir:
                            file_to_cluster[file_path] = cluster_name

            # Analyser chaque fichier et l'attacher à son cluster
            updated_clusters = {}

            for i, file_path in enumerate(files, 1):
                progress.setValue(i)
                QtWidgets.QApplication.processEvents()

                if progress.wasCanceled():
                    break

                abs_path = file_path
                content = file_contents.get(file_path, "")

                if not content and os.path.exists(abs_path):
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    except Exception as e:
                        logger.warning(f"Impossible de lire {abs_path}: {e}")
                        content = ""

                target_cluster_name = file_to_cluster.get(file_path)

                if not target_cluster_name:
                    target_cluster_name = clusters_detailed[0]['name']
                    logger.warning(f"Aucun cluster trouvé pour {file_path}, utilisation de {target_cluster_name}")

                try:
                    classes = self.dependency_parser.extract_classes(content, abs_path) if content else []
                    functions = self.dependency_parser.extract_functions(content, abs_path) if content else []
                    variables = self.dependency_parser.extract_variables(content, abs_path) if content else []

                    if target_cluster_name not in updated_clusters:
                        updated_clusters[target_cluster_name] = {
                            'classes': [],
                            'functions': [],
                            'variables': [],
                            'files_processed': []
                        }

                    updated_clusters[target_cluster_name]['files_processed'].append(file_path)

                    for cls in classes:
                        cls_data = {
                            'name': cls.get('name', 'Unknown'),
                            'uid': cls.get('uid', str(uuid.uuid4())),
                            'line': cls.get('line', 0),
                            'file': file_path,
                            'methods': cls.get('methods', []),
                            'description': f"Classe dans {file_path}"
                        }
                        updated_clusters[target_cluster_name]['classes'].append(cls_data)

                    for func in functions:
                        func_data = {
                            'name': func.get('name', 'Unknown'),
                            'uid': func.get('uid', str(uuid.uuid4())),
                            'type': func.get('type', 'function'),
                            'line': func.get('line', 0),
                            'file': file_path,
                            'calls': func.get('calls', []),
                            'description': f"Fonction dans {file_path}"
                        }
                        updated_clusters[target_cluster_name]['functions'].append(func_data)

                    for var in variables:
                        var_data = {
                            'name': var.get('name', 'Unknown'),
                            'uid': var.get('uid', str(uuid.uuid4())),
                            'type': var.get('type', 'variable'),
                            'line': var.get('line', 0),
                            'file': file_path,
                            'scope': var.get('scope', 'global'),
                            'description': f"Variable dans {file_path}"
                        }
                        updated_clusters[target_cluster_name]['variables'].append(var_data)

                except Exception as e:
                    logger.warning(f"Erreur extraction enfants pour {abs_path}: {e}")

            progress.setValue(len(files))

            # Mettre à jour les clusters existants avec les données extraites
            for cluster in clusters_detailed:
                cluster_name = cluster.get('name', '')
                if cluster_name in updated_clusters:
                    cluster_updates = updated_clusters[cluster_name]

                    for cls in cluster_updates['classes']:
                        self._add_extracted_item_to_cluster(cluster, cls, 'class')

                    for func in cluster_updates['functions']:
                        self._add_extracted_item_to_cluster(cluster, func, 'function')

                    for var in cluster_updates['variables']:
                        self._add_extracted_item_to_cluster(cluster, var, 'variable')

                    logger.info(
                        f"Cluster '{cluster_name}': "
                        f"{len(cluster_updates['classes'])} classes, "
                        f"{len(cluster_updates['functions'])} fonctions, "
                        f"{len(cluster_updates['variables'])} variables"
                    )

            # CORRIGÉ: Appeler _collect_all_labels() APRÈS l'ajout des éléments
            self._collect_all_labels()

            # Rafraîchir l'affichage
            self._refresh_cluster_list()
            self.relations_graph.update_graph(None)

            # Re-sélectionner le cluster pour déclencher la mise à jour
            if current_cluster_row != -1 and self.cluster_list_widget.count() > current_cluster_row:
                self.cluster_list_widget.setCurrentRow(current_cluster_row)

                if current_root_row != -1 and self.root_list_widget.count() > current_root_row:
                    self.root_list_widget.setCurrentRow(current_root_row)

            progress.close()

            # Statistiques finales
            total_classes = sum(len(u['classes']) for u in updated_clusters.values())
            total_functions = sum(len(u['functions']) for u in updated_clusters.values())
            total_variables = sum(len(u['variables']) for u in updated_clusters.values())

            QtWidgets.QMessageBox.information(
                self,
                "Analyse terminée",
                f"Projet '{project_name}' analysé avec succès.\n\n"
                f"Fichiers analysés : {len(files)}\n"
                f"Classes trouvées : {total_classes}\n"
                f"Fonctions trouvées : {total_functions}\n"
                f"Variables trouvées : {total_variables}"
            )

            logger.info(
                f"Analyse terminée pour '{project_name}': "
                f"{total_classes} classes, {total_functions} fonctions, {total_variables} variables"
            )

        except Exception as e:
            progress.close()
            logger.error(f"Erreur lors du scan du projet Dgraph: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                f"Erreur lors de l'analyse du projet :\n{str(e)}"
            )

    def _add_extracted_item_to_cluster(self, cluster: Dict, item: Dict, item_type: str):
        """
        Ajoute un élément extrait (classe, fonction, variable) comme nœud enfant dans la hiérarchie du cluster.

        Args:
            cluster: Dict du cluster
            item: Dict de l'élément extrait (avec 'name', 'uid', 'line', 'file', etc.)
            item_type: Type ('class', 'function', 'variable')
        """
        # Créer le nœud enfant
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'parents': []  # Sera défini si target trouvé
        }

        # Chercher le root_label correspondant au fichier (utiliser nom de fichier pour matching, pas chemin complet)
        file_name = os.path.basename(item.get('file', ''))
        if not file_name:
            logger.warning(f"Aucun fichier associé à l'élément {item['name']} ({item_type})")
            return

        target_label = None
        for root_label in cluster.get('root_labels', []):
            files_in_label = root_label.get('files', [])
            if any(os.path.basename(f) == file_name for f in files_in_label):
                target_label = root_label
                break

        if target_label:
            # Ajouter comme enfant
            target_label.setdefault('children', []).append(child)
            child['parents'] = [target_label['uid']]

            # Ajouter à label_uid_to_info pour cohérence (sera mis à jour dans _collect_all_labels)
            self.label_uid_to_info[uid] = {
                'name': child['name'],
                'label': child['label'],
                'type': item_type,
                'cluster': cluster['name'],
                'file': file_name  # Utiliser nom relatif
            }

            logger.debug(f"Ajouté {item_type} '{item['name']}' comme enfant de {target_label['label']}")
        else:
            # Fallback: ajouter au premier root_label
            if cluster.get('root_labels'):
                target_label = cluster['root_labels'][0]
                target_label.setdefault('children', []).append(child)
                child['parents'] = [target_label['uid']]
                self.label_uid_to_info[uid] = {
                    'name': child['name'],
                    'label': child['label'],
                    'type': item_type,
                    'cluster': cluster['name'],
                    'file': file_name
                }
                logger.warning(f"Fichier {file_name} non trouvé, ajouté au premier label de {cluster['name']}")
            else:
                logger.error(f"Aucun root_label dans cluster {cluster['name']} pour ajouter {item_type} '{item['name']}'")

    def scan_dgraph_project(self, project_path: str):
        """
        Analyse le projet et intègre les éléments extraits (classes, fonctions, variables) dans la hiérarchie Dgraph.
        Utilise le parser multi-langages pour extraire et mapper les éléments.

        Args:
            project_path: Chemin du projet à scanner
        """
        logger.info(f"📁 Scan du projet Dgraph: {project_path}")

        # Charger la structure existante
        structure = self._load_existing_structure(project_path)
        clusters_detailed = structure.get("clusters_detailed", [])

        if not clusters_detailed:
            logger.warning("Aucune structure de clusters trouvée.")
            return structure

        # Mapper des relations global
        relations_map = {}
        scanner = ProjectStructureScanner()
        files = scanner.get_all_files(structure)
        for file_info in files:
            if is_supported_file(file_info['path']):
                relations = file_info.get('relations', {})
                if relations:
                    relations_map[file_info['path']] = relations

        # Compteurs pour log par cluster
        cluster_stats = {}

        # Pour chaque cluster
        for cluster in clusters_detailed:
            cluster_name = cluster.get('name', '')
            cluster_stats[cluster_name] = {'classes': 0, 'functions': 0, 'variables': 0}

            logger.info(f"Traitement du cluster '{cluster_name}': {len(cluster.get('root_labels', []))} labels")

            # Pour chaque root_label (fichier ou dossier de fichiers)
            for root_label in cluster.get('root_labels', []):
                files_in_label = root_label.get('files', [])
                if not files_in_label:
                    continue
                
                # Pour chaque fichier dans ce label
                for file_path in files_in_label:
                    if not os.path.exists(file_path):
                        continue
                    
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        parser = MultiLanguageDependencyParser()
                        parsed_data = {
                            "classes": parser.extract_classes(content, file_path),
                            "functions": parser.extract_functions(content, file_path),
                            "variables": parser.extract_variables(content, file_path)
                        }

                        # Mapper relations pour ce fichier (au niveau du root_label pour l'instant)
                        relations = relations_map.get(file_path, {})
                        if relations:
                            # Ajouter les relations au root_label (simplifié)
                            for rel_type, rel_list in relations.items():
                                for rel in rel_list:
                                    target = rel.get('target', '')
                                    normalized_target = normalize_node_name(target)
                                    if normalized_target:
                                        target_uid = self._find_label_uid_by_name(normalized_target)
                                        if target_uid:
                                            relation_entry = {
                                                'target_uid': target_uid,
                                                'relation_type': rel_type,
                                                'line': rel.get('line', 0)
                                            }
                                            root_label.setdefault('outgoing_relations', []).append(relation_entry)

                        # Créer et ajouter les enfants pour ce fichier au root_label
                        for cls in parsed_data.get("classes", []):
                            cls['file'] = file_path
                            child = self._create_child_node_from_item(cls, 'class')
                            root_label.setdefault('children', []).append(child)
                            cluster_stats[cluster_name]['classes'] += 1

                        for func in parsed_data.get("functions", []):
                            func['file'] = file_path
                            child = self._create_child_node_from_item(func, 'function')
                            root_label.setdefault('children', []).append(child)
                            cluster_stats[cluster_name]['functions'] += 1

                        for var in parsed_data.get("variables", []):
                            var['file'] = file_path
                            child = self._create_child_node_from_item(var, 'variable')
                            root_label.setdefault('children', []).append(child)
                            cluster_stats[cluster_name]['variables'] += 1

                    except Exception as e:
                        logger.error(f"Erreur lors du scan du fichier {file_path}: {e}")

            # Log par cluster
            stats = cluster_stats[cluster_name]
            logger.info(f"Cluster '{cluster_name}': {stats['classes']} classes, {stats['functions']} fonctions, {stats['variables']} variables")

        # Sauvegarder la structure mise à jour
        structure_file = os.path.join(project_path, "turing_ontology.json")
        try:
            with open(structure_file, "w", encoding="utf-8") as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)
            logger.info(f"Structure sauvegardée: {structure_file}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")

        # Mettre à jour les données locales
        self.current_project_path = project_path
        self.current_project_profile_data = structure
        self._collect_all_labels()

        return structure

    def _create_child_node_from_item(self, item: Dict, item_type: str) -> Dict[str, Any]:
        """
        Crée un nœud enfant à partir d'un élément extrait (classe, fonction, variable).
        
        Args:
            item: Dict de l'élément extrait
            item_type: Type ('class', 'function', 'variable')
        
        Returns:
            Dict du nœud enfant
        """
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'parents': []  # Sera mis à jour si nécessaire
        }
        
        # Ajouter à label_uid_to_info
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_name if hasattr(self, 'current_cluster_name') else 'unknown',
            'file': os.path.basename(item.get('file', ''))
        }
        
        return child

    def _collect_all_labels(self):
        """
        Collecte tous les labels et met à jour label_uid_to_info avec mapping Dgraph.
        À appeler après scan pour rafraîchir.
        """
        self.label_uid_to_info = {}
        if not self.current_project_profile_data:
            return

        def recurse(node, cluster_name=''):
            if 'uid' in node:
                uid = node['uid']
                # Stocker mapping local -> Dgraph si présent
                dgraph_uid = node.get('dgraph_uid', None)
                if dgraph_uid:
                    self.local_to_dgraph[uid] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = uid
                self.label_uid_to_info[uid] = {
                    'name': node.get('name', node.get('label', 'N/A')),
                    'label': node.get('label', 'N/A'),
                    'type': node.get('type', 'unknown'),
                    'cluster': cluster_name,
                    'file': node.get('file', 'N/A')
                }

            for child in node.get('children', []):
                recurse(child, cluster_name)

        for cluster in self.current_project_profile_data.get('clusters_detailed', []):
            cluster_name = cluster.get('name', 'unknown')
            for root_label in cluster.get('root_labels', []):
                recurse(root_label, cluster_name)

        # Charger mappings persistés depuis Dgraph si connector actif
        if self.dgraph_connector:
            self._load_mappings_from_dgraph()

        logger.info(f"label_uid_to_info mis à jour: {len(self.label_uid_to_info)} entrées")

    def _get_local_to_dgraph_mapping(self):
        """Retourne {local_uuid: dgraph_hex}"""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
            self._collect_all_labels()  # Rafraîchir si besoin
        return self.local_to_dgraph

    def _get_dgraph_to_local_mapping(self):
        """Retourne {dgraph_hex: local_uuid}"""
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
            self._collect_all_labels()
        return self.dgraph_to_local

    def _load_mappings_from_dgraph(self):
        """Charge les mappings depuis Dgraph pour sync."""
        query = """
        {
          q(func: type(Node)) {
            uid
            local_id
          }
        }
        """
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self.dgraph_connector._parse_response(resp)
            for node in data.get("q", []):
                local_id = node.get('local_id')
                dgraph_uid = node['uid']
                if local_id:
                    self.local_to_dgraph[local_id] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = local_id
        except Exception as e:
            logger.error(f"Erreur chargement mappings Dgraph: {e}")

    def _load_existing_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Charge la structure existante du projet.
        """
        structure_file = os.path.join(project_path, "turing_ontology.json")
        if os.path.exists(structure_file):
            try:
                with open(structure_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement structure: {e}")
        return {"clusters_detailed": []}    
    
    def _integrate_scanned_structure(self, scanned_structure: Dict[str, Any], base_dir: str):
            """
            Intègre la structure scannée dans le projet, en calculant relations_map à l'intérieur.

            Args:
                scanned_structure: Structure scannée par le scanner
                base_dir: Répertoire de base du projet
            """
            # Calculer relations_map ici pour matcher l'appel (3 args)
            relations_map = self.project_scanner.get_relations_map(scanned_structure)

            clusters_detailed = []
            for cluster in scanned_structure.get('clusters', []):
                new_cluster = {
                    'name': cluster.get('name', 'Unknown'),
                    'path': cluster.get('path', ''),
                    'type': 'cluster',
                    'root_labels': []
                }

                # Traiter chaque fichier avec force
                all_files_in_cluster = self.project_scanner.get_all_files({'clusters': [cluster]})
                for file_info in all_files_in_cluster:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    rel_path = os.path.relpath(file_path, base_dir) if base_dir and file_path else file_path

                    # Contenu déjà lu dans _scan_file, fallback si absent
                    content = file_info.get('file_contents', {}).get(rel_path, '')
                    if not content and file_path:
                        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                        for encoding in encodings:
                            try:
                                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                                    content = f.read()
                                break
                            except (UnicodeDecodeError, IOError):
                                continue
                        else:
                            try:
                                with open(file_path, 'rb') as f:
                                    raw = f.read()
                                    content = raw.decode('utf-8', errors='replace')
                            except Exception:
                                content = ''

                    new_label = {
                        'label': file_name,
                        'id': str(uuid.uuid4()),
                        'uid': file_info.get('uid', str(uuid.uuid4())),
                        'type': 'file',
                        'description': f"Fichier: {rel_path}",
                        'category': ['file'],
                        'files': [rel_path],
                        'file_contents': {rel_path: content},
                        'children': [],
                        'parents': [],
                        'outgoing_relations': [],
                        'incoming_relations': [],
                        'classes': file_info.get('classes', []),  # Forcé depuis scan
                        'functions': file_info.get('functions', []),  # Forcé depuis scan
                        'variables': file_info.get('variables', [])  # Forcé depuis scan
                    }

                    # Ajouter le fichier au projet global
                    files_list = self.current_project_profile_data.get('files', [])
                    if rel_path not in files_list:
                        files_list.append(rel_path)
                        self.current_project_profile_data['files'] = files_list
                    file_contents = self.current_project_profile_data.get('file_contents', {})
                    file_contents[rel_path] = content
                    self.current_project_profile_data['file_contents'] = file_contents

                    # Mapper relations
                    relations = relations_map.get(file_path, {})
                    if relations:
                        for rel_type, rel_list in relations.items():
                            for rel in rel_list:
                                target = rel.get('target', '')
                                normalized_target = normalize_node_name(target)

                                if normalized_target:
                                    target_uid = self._find_label_uid_by_name(normalized_target)

                                    if target_uid:
                                        relation_entry = {
                                            'target_uid': target_uid,
                                            'relation_type': rel_type,
                                            'line': rel.get('line', 0)
                                        }
                                        new_label['outgoing_relations'].append(relation_entry)

                                        pending_rels = self.pending_relations.get(new_label['uid'], [])
                                        pending_rels.append({
                                            'target_uid': target_uid,
                                            'relation_type': rel_type
                                        })
                                        self.pending_relations[new_label['uid']] = pending_rels

                    # Ajouter enfants depuis scan (classes, functions, variables)
                    for child in file_info.get('children', []):
                        if 'uid' not in child:
                            child['uid'] = str(uuid.uuid4())
                        new_label['children'].append(child)

                    new_cluster['root_labels'].append(new_label)

                clusters_detailed.append(new_cluster)

            logger.info(f"{len(clusters_detailed)} clusters intégrés avec classes/fonctions/variables")
            turing_ontology = self.current_project_profile_data.get('turing_ontology', {})
            turing_ontology['clusters_detailed'] = clusters_detailed
            self.current_project_profile_data['turing_ontology'] = turing_ontology

    def _find_label_uid_by_name(self, name: str) -> Optional[str]:
        """
        Trouve l'UID d'un label par son nom (sans extension).
        
        Args:
            name: Nom du label à chercher
        
        Returns:
            UID du label ou None
        """
        if not name:
            return None
        
        normalized_search = name.lower().strip()
        
        for uid, info in self.label_uid_to_info.items():
            label_name = info.get('name', '')
            normalized_label = normalize_node_name(label_name)
            
            if normalized_label and normalized_label.lower() == normalized_search:
                return uid
        
        return None

    def _on_root_label_selected(self, current):
        """
        Gère la sélection d'un root label.
        """
        if current:
            self.current_root_label_index = self.root_list_widget.row(current)
            self.current_root_data = self.current_cluster_data["root_labels"][self.current_root_label_index]
            self.current_selected_label_uid = current.data(Qt.UserRole)

            # Réinitialiser les sélections inférieures
            self.current_level1_data = None
            self.current_level2_data = None
            self.current_level1_label_index = -1
            self.current_level2_label_index = -1

            # Afficher les détails du root label
            self._update_selected_details("Label Racine", self.current_root_data)

            # Peupler la liste level1 avec TOUS les enfants hiérarchiques
            self._populate_level1_list()

            # Vider la liste des niveau 2
            self.child_list_widget.clear()

            # Mettre à jour les relations et graphe
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_root_data = None
            self.current_selected_label_uid = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

        self._update_button_states()

    def _populate_children_list(self, parent_data: Dict, list_widget=None):
        """
        MODIFIÉE: Ne peuple que les enfants hiérarchiques.
        Les classes/fonctions/variables sont affichées via _populate_children_for_file().
        """
        if list_widget is None:
            list_widget = self.level1_list_widget if hasattr(self, 'current_root_data') else self.child_list_widget

        list_widget.clear()
        if not parent_data:
            return

        # UNIQUEMENT les enfants hiérarchiques (fichiers, dossiers) 
        # PAS les classes, fonctions, variables
        for child in parent_data.get('children', []):
            child_type = child.get('type', 'child')

            # Filtrer: ne montrer que les vrais enfants hiérarchiques
            if child_type not in ['class', 'function', 'variable']:
                icon = self._get_node_icon(child_type)
                display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child.get('uid'))
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _get_node_icon(self, node_type: str) -> str:
        """
        Retourne une icône selon le type de nœud.
        
        Args:
            node_type: Type de nœud
        
        Returns:
            Icône Unicode
        """
        icons = {
            'class': '👨‍💻',
            'function': '⚙️',
            'variable': '🔹',  # NOUVEAU
            'method': '🔧',
            'child': ''
        }
        
        return icons.get(node_type, '🔸')

    def _get_relation_icon(self, rel_type: str) -> str:
        """
        Retourne une icône selon le type de relation.
        
        Args:
            rel_type: Type de relation
        
        Returns:
            Icône Unicode
        """
        icons = {
            'import': '📦',
            'from_import': '📦',
            'require': '📦',
            'include': '📦',
            'heritage': '🔗',
            'extends': '🔗',
            'implements': '🔗',
            'call': '📞',
            'function_call': '📞',
            'method_call': '📞',
            'uses': '🔹',  # NOUVEAU pour variables
            'variable_use': '🔹'
        }
        
        return icons.get(rel_type, '🔸')

    def _on_level1_label_selected(self, current):
        """
        Gère la sélection d'un label niveau 1.
        Peut être un fichier ou un dossier contenant d'autres fichiers/dossiers.
        """
        if current:
            item_type = current.data(Qt.UserRole + 1)
            item_uid = current.data(Qt.UserRole)

            self.current_selected_label_uid = item_uid

            # Chercher cet enfant dans la structure (peut être imbriqué)
            child_data = self._find_child_by_uid(self.current_root_data, item_uid)

            if child_data:
                self.current_level1_data = child_data
                self.current_level1_label_index = self._get_child_index_by_uid(item_uid)

                # Réinitialiser niveau 2
                self.current_level2_data = None
                self.current_level2_label_index = -1

                # Afficher les détails
                self._update_selected_details(f"Niveau 1 - {item_type.capitalize()}", self.current_level1_data)

                # Peupler le niveau 2 avec les enfants de ce niveau 1
                self._populate_child_list()

                # Mettre à jour relations et graphe
                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)
            else:
                self.current_level1_data = None
                self.child_list_widget.clear()

        else:
            self.current_level1_data = None
            self.current_selected_label_uid = None
            self.child_list_widget.clear()
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

        self._update_button_states()

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        MODIFIÉE: Peuple la liste enfant avec les classes, fonctions et variables
        DU FICHIER SÉLECTIONNÉ. Les UIDs sont stockés correctement dans Qt.UserRole.
        """
        list_widget.clear()
        if not file_data:
            return

        # Afficher d'abord les classes du fichier
        classes = file_data.get('classes', [])
        for cls in classes:
            icon = '[CLS]'
            display = f"{icon} {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            cls_uid = cls.get('uid')
            if not cls_uid:
                cls_uid = f"cls_{cls.get('name', '')}_{str(uuid.uuid4())}"
                cls['uid'] = cls_uid

            # Stocker le UID STRING, pas l'ID mémoire
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            list_widget.addItem(item)

        # Afficher les fonctions du fichier
        functions = file_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "[MTH]" if func_type == "method" else "[FNC]"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            func_uid = func.get('uid')
            if not func_uid:
                func_uid = f"func_{func.get('name', '')}_{str(uuid.uuid4())}"
                func['uid'] = func_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            list_widget.addItem(item)

        # Afficher les variables du fichier
        variables = file_data.get('variables', [])
        for var in variables:
            display = f"[VAR] {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            var_uid = var.get('uid')
            if not var_uid:
                var_uid = f"var_{var.get('name', '')}_{str(uuid.uuid4())}"
                var['uid'] = var_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            list_widget.addItem(item)

        # Afficher les enfants hiérarchiques (sous-dossiers/fichiers) APRÈS les classes/foncs/vars
        for child in file_data.get('children', []):
            if child.get('type') in ['folder', 'file', 'child']:
                icon = self._get_node_icon(child.get('type', 'child'))
                display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"
                item = QListWidgetItem(display)

                # Stocker le UID STRING de l'enfant
                child_uid = child.get('uid')
                if not child_uid:
                    child_uid = child.get('id', str(uuid.uuid4()))
                    child['uid'] = child_uid

                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child.get('type', 'child'))
                list_widget.addItem(item)

        self._update_button_states()

    def _format_child_details(self, child: Dict[str, Any]) -> str:
        """
        Formate les détails d'un enfant (classe, fonction, variable) pour affichage.
        """
        child_type = child.get('type', 'unknown')
        details = ""

        if child_type == 'class':
            details = f"=== CLASSE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            bases = child.get('bases', [])
            if bases:
                details += f"\nHérite de:\n"
                for base in bases:
                    details += f"  - {base}\n"

            methods = child.get('children', [])
            if methods:
                details += f"\nMéthodes ({len(methods)}):\n"
                for method in methods[:10]:
                    details += f"  - {method.get('name', 'N/A')} (ligne {method.get('line', '?')})\n"
                if len(methods) > 10:
                    details += f"  ... et {len(methods) - 10} autres\n"

        elif child_type in ['function', 'method']:
            details = f"=== {'MÉTHODE' if child_type == 'method' else 'FONCTION'} ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('type', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            params = child.get('params', [])
            if params:
                details += f"\nParamètres ({len(params)}):\n"
                for param in params:
                    param_name = param.get('name', 'param')
                    param_type = param.get('type', 'unknown')
                    details += f"  - {param_name}: {param_type}\n"

            returns = child.get('returns', {})
            if returns:
                details += f"\nRetour: {returns.get('type', 'N/A')}\n"

            calls = child.get('outgoing_relations', [])
            if calls:
                details += f"\nAppelle ({len(calls)}):\n"
                for call in calls[:5]:
                    details += f"  - {call}\n"
                if len(calls) > 5:
                    details += f"  ... et {len(calls) - 5} autres\n"

        elif child_type == 'variable':
            details = f"=== VARIABLE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('var_type', 'N/A')}\n"
            details += f"Scope: {child.get('scope', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

        return details

    def _populate_level1_list(self):
        """
        Peuple la liste niveau 1 avec TOUS les enfants hiérarchiques,
        y compris les fichiers dans les sous-dossiers.
        """
        self.level1_list_widget.clear()

        if not self.current_root_data:
            return

        # Afficher récursivement tous les enfants
        for child in self.current_root_data.get("children", []):
            self._add_child_to_level1_list(child, self.level1_list_widget)

        self._update_button_states()

    def _get_child_index_by_uid(self, uid: str) -> int:
        """
        Trouve l'index d'un enfant par son UID.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Index ou -1
        """
        if not self.current_root_data:
            return -1
        
        for i, child in enumerate(self.current_root_data.get('children', [])):
            if child.get('uid') == uid:
                return i
        
        return -1

    def _find_label_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un label par son UID dans toute la hiérarchie.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Dictionnaire du label ou None
        """
        all_nodes = self._get_all_nodes()
        return next((n for n in all_nodes if n.get('uid') == uid), None)

    def _find_child_by_uid(self, parent: Dict, uid: str) -> Optional[Dict]:
        """
        Cherche récursivement un enfant par son UID dans la structure.
        """
        for child in parent.get("children", []):
            if child.get('uid') == uid or child.get('id') == uid:
                return child

            # Chercher récursivement dans les sous-dossiers
            result = self._find_child_by_uid(child, uid)
            if result:
                return result

        return None

    def _format_label_details(self, label: Dict[str, Any]) -> str:
        """
        Formate les détails d'un label pour affichage, incluant classes, fonctions et variables.
        
        Args:
            label: Dictionnaire du label
        
        Returns:
            String formaté
        """
        details = f"Nom: {label.get('label', 'N/A')}\n"
        details += f"UID: {label.get('uid', 'N/A')}\n"
        details += f"Type: {label.get('type', 'N/A')}\n"  # NOUVEAU
        details += f"Description: {label.get('description', 'N/A')}\n\n"
        
        files = label.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:5]:
                details += f"  - {f}\n"
            if len(files) > 5:
                details += f"  ... et {len(files) - 5} autres\n"
        
        # Ajouter classes si présentes
        classes = label.get('classes', [])
        if classes:
            details += f"\nClasses ({len(classes)}):\n"
            for cls in classes[:5]:
                details += f"  - {cls['name']} (ligne {cls['line']})\n"
            if len(classes) > 5:
                details += f"  ... et {len(classes) - 5} autres\n"
        
        # Ajouter fonctions si présentes
        functions = label.get('functions', [])
        if functions:
            details += f"\nFonctions/Méthodes ({len(functions)}):\n"
            for func in functions[:5]:
                details += f"  - {func['name']} ({func['type']}, ligne {func['line']})\n"
            if len(functions) > 5:
                details += f"  ... et {len(functions) - 5} autres\n"

        # NOUVEAU : Ajouter variables si présentes
        variables = label.get('variables', [])
        if variables:
            details += f"\nVariables ({len(variables)}):\n"
            for var in variables[:5]:
                details += f"  - {var['name']} ({var['type']}, ligne {var['line']})\n"
            if len(variables) > 5:
                details += f"  ... et {len(variables) - 5} autres\n"
        
        return details

    def _on_double_click_label(self, item):
        """
        Double-clic sur un label - Affiche le contenu du fichier avec snippet highlighté.
        MODIFIÉ: Centré sur ligne pour classes/foncs/vars.
        """
        if not item:
            return
        
        uid = item.data(Qt.UserRole)
        label = self._find_label_by_uid(uid)
        
        if not label:
            return
        
        files = label.get('files', [])
        if not files:
            QtWidgets.QMessageBox.information(
                self,
                "Aucun fichier",
                "Ce label n'a pas de fichier associé."
            )
            return
        
        # Si plusieurs fichiers, demander lequel afficher
        file_to_show = files[0]
        if len(files) > 1:
            file_to_show, ok = QInputDialog.getItem(
                self,
                "Sélectionner un fichier",
                "Fichier à afficher:",
                files,
                0,
                False
            )
            if not ok:
                return
        
        # Récupérer le contenu
        content = label.get('file_contents', {}).get(file_to_show, '')
        
        if not content:
            QtWidgets.QMessageBox.warning(
                self,
                "Contenu vide",
                f"Le fichier {file_to_show} est vide."
            )
            return
        
        # Afficher dans une fenêtre de dialogue avec highlight
        self._show_file_content_dialog(file_to_show, content, label)

    def _show_file_content_dialog(self, filename: str, content: str, label: Dict[str, Any]):
        """
        Affiche le contenu d'un fichier dans une fenêtre modale avec snippet highlighté.
        
        Args:
            filename: Nom du fichier
            content: Contenu du fichier
            label: Label associé
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Contenu: {filename}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # Info header
        info_label = QLabel(f"<b>Fichier:</b> {filename}<br><b>Label:</b> {label.get('label', 'N/A')}")
        layout.addWidget(info_label)
        
        # Éditeur de code (lecture seule)
        code_editor = QPlainTextEdit()
        code_editor.setReadOnly(True)
        code_editor.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)

        # NOUVEAU : Highlight si type spécifique (centrer sur ligne)
        if label.get('type') in ['class', 'function', 'variable']:
            line = label.get('line', 1)
            # Slice approximatif autour de la ligne
            lines = content.split('\n')
            start_line = max(0, line - 10)
            end_line = min(len(lines), line + 10)
            highlighted = '\n'.join(lines[start_line:end_line])
            # Ajouter marqueur
            highlighted = f"--- Ligne {line} ---\n{highlighted}\n--- Fin snippet ---"
            code_editor.setPlainText(highlighted)
        else:
            code_editor.setPlainText(content)
        
        layout.addWidget(code_editor)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        copy_button = QPushButton("📋 Copier tout")
        copy_button.clicked.connect(lambda: self._copy_to_clipboard(content))
        button_layout.addWidget(copy_button)
        
        snippet_button = QPushButton("✂️ Copier snippet (50 lignes)")
        snippet_button.clicked.connect(lambda: self._copy_snippet(content))
        button_layout.addWidget(snippet_button)
        
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()

    def _copy_to_clipboard(self, text: str):
        """Copie le texte dans le presse-papier."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        
        QtWidgets.QMessageBox.information(
            self,
            "Copié",
            "Contenu copié dans le presse-papier."
        )

    def _copy_snippet(self, text: str, max_lines: int = 50):
        """Copie un snippet (extrait) du texte."""
        lines = text.split('\n')
        snippet = '\n'.join(lines[:max_lines])
        
        if len(lines) > max_lines:
            snippet += f"\n\n... ({len(lines) - max_lines} lignes supplémentaires)"
        
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(snippet)
        
        QtWidgets.QMessageBox.information(
            self,
            "Snippet copié",
            f"Les {min(max_lines, len(lines))} premières lignes ont été copiées."
        )

    def _read_file_content(self, file_path: str) -> str:
        """Lit un fichier en UTF-8 avec gestion d’erreur."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _map_relations_to_child_local(self, relations: Dict, child_label: Dict):
        for rel_type, rels in relations.items():
            for rel in rels:
                if rel.get('target') == normalize_node_name(child_label['label']):
                    child_label['outgoing_relations'].append({
                        'target_uid': rel.get('target_uid', self._find_label_uid_by_name(rel['target'])),
                        'relation_type': rel_type
                    })

    def _add_child_to_level1_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste niveau 1, récursivement pour les sous-dossiers.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant SANS icône
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_level1_list(grandchild, list_widget, indent + "  ")

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector: 
            self.dgraph_connector.close()
        super().closeEvent(event)