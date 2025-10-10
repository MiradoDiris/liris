import os
import json
import uuid
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout, QPlainTextEdit, QListWidgetItem, QHBoxLayout, QLabel, QComboBox, QPushButton, QInputDialog, QMessageBox
from collections import defaultdict
import requests  # Added for schema update
import ast  # Added for extraction
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector


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
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Source affichée
        source_layout = QHBoxLayout()
        source_layout.addWidget(QtWidgets.QLabel("Nœud sélectionné:"))
        self.source_label = QtWidgets.QLabel("Aucun sélectionné")
        self.source_label.setStyleSheet("color: #666; font-style: italic;")
        source_layout.addWidget(self.source_label)
        source_layout.addStretch()
        layout.addLayout(source_layout)

        # Liste des relations (sortantes + entrantes)
        relations_label_layout = QHBoxLayout()
        relations_label_layout.addWidget(QtWidgets.QLabel("Relations:"))
        relations_label_layout.addStretch()
        layout.addLayout(relations_label_layout)

        self.relations_list = QtWidgets.QListWidget()
        self.relations_list.setMaximumHeight(200)
        self.relations_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.relations_list)

        # Boutons d'action
        buttons_layout = QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("Nouvelle relation")
        self.add_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_button.setMaximumWidth(150)
        self.add_button.clicked.connect(self._on_add_new_relation)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QtWidgets.QPushButton("Modifier")
        self.edit_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_button.setMaximumWidth(100)
        self.edit_button.clicked.connect(self._on_edit)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QtWidgets.QPushButton("Supprimer")
        self.remove_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_button.setMaximumWidth(100)
        self.remove_button.clicked.connect(self._on_remove)
        buttons_layout.addWidget(self.remove_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)   

    def update_current(self, source_uid):
        self.relations_list.clear()
        if source_uid:
            source_info = self.parent_widget.label_uid_to_info.get(source_uid)
            self.source_label.setText(source_info['name'] if source_info else "Inconnu")
            self._update_relations_list(source_uid)
        else:
            self.source_label.setText("Aucun sélectionné")
            self.relations_list.clear()

    def _on_edit(self):
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        direction = rel.get('direction', '')
        if direction.startswith('hier'):
            QtWidgets.QMessageBox.information(self, "Info", "Les relations hiérarchiques ne peuvent pas être modifiées.")
            return

        src_uid = rel['source']
        tgt_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        # Boîte de dialogue pour choisir une nouvelle cible
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == src_uid:
                continue
            target_uids.append(uid)
            target_names.append(f"{info['name']} ({info['cluster']})")

        new_target_name, ok = QInputDialog.getItem(
            self, "Modifier la relation",
            "Nouvelle cible :", target_names, 0, False
        )
        if ok and new_target_name:
            new_index = target_names.index(new_target_name)
            new_target_uid = target_uids[new_index]

            # Supprimer ancienne
            self.parent_widget._update_local_relations_remove(src_uid, tgt_uid, rel_type)
            old_rel = {"target_uid": tgt_uid, "relation_type": rel_type}
            if old_rel in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(old_rel)

            # Ajouter nouvelle
            new_rel = {"target_uid": new_target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[src_uid].append(new_rel)
            self.parent_widget._update_local_relations(src_uid, new_target_uid, rel_type)

            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation modifiée: {src_uid} → {new_target_uid}")  

    def _on_remove(self):
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        direction = rel.get('direction', '')
        if direction.startswith('hier'):
            QtWidgets.QMessageBox.information(self, "Info", "Les relations hiérarchiques ne peuvent pas être supprimées.")
            return

        src_uid = rel['source']
        tgt_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer", "Voulez-vous vraiment supprimer cette relation ?"
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.parent_widget._update_local_relations_remove(src_uid, tgt_uid, rel_type)
            rel_obj = {"target_uid": tgt_uid, "relation_type": rel_type}
            if rel_obj in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(rel_obj)
            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation supprimée: {src_uid} → {tgt_uid}")

    def _update_relations_list(self, source_uid):
        self.relations_list.clear()
        if not source_uid:
            return

        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if not node:
            return

        # Sortantes (relations custom)
        for r in node.get('outgoing_relations', []):
            target_info = self.parent_widget.label_uid_to_info.get(r['target_uid'], {})
            target_name = target_info.get('name', 'Inconnu')
            rel_type = r.get('relation_type', 'relation')
            display = f"[OUT] {node['label']} ({rel_type}) → {target_name}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "direction": "out",
                "source": source_uid,
                "target": r['target_uid'],
                "type": rel_type
            })
            self.relations_list.addItem(item)

        # Entrantes (relations custom)
        for r in node.get('incoming_relations', []):
            source_info = self.parent_widget.label_uid_to_info.get(r['source_uid'], {})
            source_name = source_info.get('name', 'Inconnu')
            rel_type = r.get('relation_type', 'relation')
            display = f"[IN] {source_name} ({rel_type}) → {node['label']}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "direction": "in",
                "source": r['source_uid'],
                "target": source_uid,
                "type": rel_type
            })
            self.relations_list.addItem(item)

        # Hiérarchie sortante (enfants)
        for child in node.get('children', []):
            child_name = child['label']
            display = f"[HIER-OUT] {node['label']} (child) → {child_name}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "direction": "hier-out",
                "source": source_uid,
                "target": child['uid'],
                "type": "child"
            })
            self.relations_list.addItem(item)

        # Hiérarchie entrante (parents)
        for p_uid in node.get('parents', []):
            parent_info = self.parent_widget.label_uid_to_info.get(p_uid, {})
            parent_name = parent_info.get('name', 'Inconnu')
            display = f"[HIER-IN] {parent_name} (parent) → {node['label']}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, {
                "direction": "hier-in",
                "source": p_uid,
                "target": source_uid,
                "type": "parent"
            })
            self.relations_list.addItem(item)

    def _on_add_new_relation(self):
        source_uid = self.parent_widget.current_selected_label_uid
        if not source_uid:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez un nœud.")
            return

        # Créer une liste de toutes les cibles possibles
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == source_uid:
                continue
            target_uids.append(uid)
            target_names.append(f"{info['name']} ({info['cluster']})")

        # Boîte de sélection
        target_name, ok = QInputDialog.getItem(
            self, "Nouvelle relation",
            "Choisissez une cible :", target_names, 0, False
        )
        if ok and target_name:
            target_index = target_names.index(target_name)
            target_uid = target_uids[target_index]

            # Enregistrer relation
            rel_type = "relation"  # Default type
            relation = {"target_uid": target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[source_uid].append(relation)
            self.parent_widget._update_local_relations(source_uid, target_uid, rel_type)

            self._update_relations_list(source_uid)
            logger.info(f"Nouvelle relation ajoutée: {source_uid} → {target_uid} ({rel_type})")

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

    def update_graph(self, central_uid=None):
        """
        Met à jour le graphe pour le nœud central sélectionné
        Version améliorée avec meilleur diagnostic
        """
        if not central_uid:
            self._draw_empty_graph()
            self.title_label.setText("Graphe des Relations")
            self.legend_label.setText("Aucun nœud sélectionné")
            return

        # Récupérer les données du nœud central
        central_info = self.parent_widget.label_uid_to_info.get(central_uid)
        if not central_info:
            logger.warning(f"Nœud {central_uid} introuvable dans label_uid_to_info")
            self._draw_empty_graph()
            return

        central_name = central_info.get('name', central_uid)

        # Récupérer toutes les relations
        related_items = self._collect_related_items(central_uid, max_depth=1, max_nodes=50)

        if not related_items:
            self.title_label.setText(f"Graphe: {central_name}")
            self.legend_label.setText("Aucune relation trouvée")
            self._draw_empty_graph_with_message(
                f"Le nœud '{central_name}' n'a aucune relation"
            )
            logger.info(f"Aucune relation pour {central_name}")
            return

        # Afficher le graphe
        logger.info(f"Affichage graphe pour {central_name}: {len(related_items)} relations")
        self.title_label.setText(f"Graphe: {central_name}")
        self._draw_graph(central_uid, central_name, related_items)

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
        """
        if not self.parent_widget.dgraph_connector.client:
            return []

        query = f"""
        {{
          q(func: type(Relation)) @filter(uid_in(source, {central_uid}) OR uid_in(target, {central_uid})) {{
            uid
            name
            relationType
            source {{
              uid
              name
              id
              level
            }}
            target {{
              uid
              name
              id
              level
            }}
          }}
        }}
        """
        try:
            txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self.parent_widget.dgraph_connector._parse_response(resp)
            return data.get('q', [])
        except Exception as e:
            logger.error(f"Erreur lors de la query des relations: {e}")
            return []

    def _collect_related_items(self, central_uid, max_depth=1, max_nodes=50):
        """
        Collecte TOUTES les relations d'un nœud (hiérarchiques, imports, héritage, etc.)
        Version améliorée qui récupère tous les types de relations, y compris depuis Dgraph
        """
        if not self.parent_widget.current_project_profile_data:
            return []

        all_nodes = self.parent_widget._get_all_nodes()
        central_node = next((n for n in all_nodes if n['uid'] == central_uid), None)
        if not central_node:
            return []

        related = []
        visited = set([central_uid])

        # 1. Relations sortantes locales (outgoing_relations)
        for rel in central_node.get('outgoing_relations', [])[:max_nodes]:
            target_uid = rel.get('target_uid', rel.get('target_id', ''))
            if target_uid in visited:
                continue
            
            target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
            if target_node:
                related.append({
                    'name': target_node['label'],
                    'type': rel['relation_type'],
                    'uid': target_uid,
                    'direction': 'out'
                })
                visited.add(target_uid)

        # 2. Relations entrantes locales (incoming_relations)
        for rel in central_node.get('incoming_relations', [])[:max_nodes]:
            source_uid = rel.get('source_uid', rel.get('source_id', ''))
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

        # 5. Relations supplémentaires depuis Dgraph (pour cas persistés non locaux)
        dgraph_rels = self._query_relations_for_node(central_uid)
        for rel in dgraph_rels:
            if rel['source']['uid'] == central_uid:
                target_uid = rel['target']['uid']
                if target_uid in visited:
                    continue
                target_name = rel['target']['name']
                related.append({
                    'name': target_name,
                    'type': rel['relationType'],
                    'uid': target_uid,
                    'direction': 'out'
                })
                visited.add(target_uid)
            elif rel['target']['uid'] == central_uid:
                source_uid = rel['source']['uid']
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
            self._load_project_profiles()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

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
    
    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 3 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(15)
        main_vertical_layout.setContentsMargins(15, 15, 15, 15)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)
        left_column_layout.addStretch()

        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
        project_selection_layout.addStretch()

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        self.add_project_button = QtWidgets.QPushButton(
            "➕ " + tr("project_config.new_project_button")
        )
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        self.delete_project_button = QtWidgets.QPushButton(
            "🗑️ " + tr("project_config.delete_project_button")
        )
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)

        self.upload_local_button = QtWidgets.QPushButton("📁 Uploader Projet Local")
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)

        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        details_form_layout.addRow(
            tr("project_config.project_name_label"), self.project_name_edit
        )

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

        self.remove_cluster_button = QtWidgets.QPushButton("✕")
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
        self.root_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
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
        self.level1_list_widget.currentItemChanged.connect(
            self._on_level1_label_selected
        )
        self.level1_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
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
        child_label_title = QtWidgets.QLabel("Labels Niveau 2")
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(80)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        self.child_list_widget.currentItemChanged.connect(lambda curr, prev: self._on_any_label_selected(curr))
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

        # Section graphe des relations (plus grande) - Maintenant dynamique
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

    def _on_root_label_selected(self, current):
        """Gère la sélection d'un root label."""
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

            # Afficher uniquement les enfants de ce root label
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

    def _populate_level1_list(self):
        """Peuple la liste des labels niveau 1 pour le root label sélectionné."""
        self.level1_list_widget.clear()
        if self.current_root_data:
            for level1 in self.current_root_data.get("children", []):
                display = level1['label']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, level1["uid"])
                self.level1_list_widget.addItem(item)
        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """Gère la sélection d'un label niveau 1."""
        if current:
            self.current_level1_label_index = self.level1_list_widget.row(current)
            self.current_level1_data = self.current_root_data["children"][self.current_level1_label_index]
            self.current_selected_label_uid = current.data(Qt.UserRole)

            # Réinitialiser la sélection niveau 2
            self.current_level2_data = None
            self.current_level2_label_index = -1

            # Afficher les détails du label niveau 1
            self._update_selected_details("Label Niveau 1", self.current_level1_data)

            # Afficher uniquement les enfants de ce label niveau 1
            self._populate_child_list()

            # Mettre à jour les relations et graphe
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
        """Peuple la liste des labels niveau 2 pour le label niveau 1 sélectionné."""
        self.child_list_widget.clear()
        if self.current_level1_data:
            for child in self.current_level1_data.get("children", []):
                display = child['label']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child["uid"])
                self.child_list_widget.addItem(item)
        self._update_button_states()

    def _on_child_label_selected(self, current):
        """Gère la sélection d'un label niveau 2."""
        if current:
            self.current_level2_label_index = self.child_list_widget.row(current)
            self.current_level2_data = self.current_level1_data["children"][self.current_level2_label_index]
            self.current_selected_label_uid = current.data(Qt.UserRole)

            # Afficher les détails du niveau 2
            self._update_selected_details("Label Niveau 2", self.current_level2_data)

            # Mettre à jour les relations et graphe
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_level2_data = None
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)
    
        self._update_button_states()

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
        """Collecte tous les labels pour relations."""
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()
        if not self.current_project_profile_data:
            return
        for cluster in self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", []):
            cluster_name = cluster.get('name', '')
            for root in cluster.get("root_labels", []):
                uid = root.get('uid', root['id'])
                info = {'name': root.get('label', ''), 'cluster': cluster_name}
                self.label_uid_to_info[uid] = info
                self.name_to_uid[root['label']] = uid
                self._collect_labels_recursive(root)

    def _collect_labels_recursive(self, node):
        """Collecte récursivement labels dans hierarchy."""
        for child in node.get('children', []):
            uid = child.get('uid', child['id'])
            info = {'name': child.get('label', ''), 'cluster': self.label_uid_to_info.get(node['uid'], {}).get('cluster', '')}
            self.label_uid_to_info[uid] = info
            self.name_to_uid[child['label']] = uid
            self._collect_labels_recursive(child)

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
        """Suppression complète d'un projet depuis l'UI et Dgraph."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        project_name = self.project_combo.currentText()  # ← Fix : Utiliser la combo box
        uid = self.current_project_profile_data.get('uid') if self.current_project_profile_data else None  # ← Récup UID du profil chargé

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

            # Appel avec le nom dynamique
            if self._collect_and_delete_uids(uids_to_delete, project_name):  # ← Ajout du paramètre
                logger.info(f"Supprimé de Dgraph : {project_name}")

                # Supprimer du cache local
                if project_name in self.project_profiles:
                    del self.project_profiles[project_name]
                self._update_project_combo()  # Refresh la combo

                # Reset UI
                self._reset_ui()
                self.current_project_name = None

                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé.")
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur", "Échec de la suppression dans Dgraph.")

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
        """Insère le profil dans Dgraph."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        mutations = self._transform_profile_to_dgraph_mutations()
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(self, "Succès", "Inséré dans Dgraph avec succès. Ratel ouvert pour vérification.")
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Échec insertion Dgraph.")

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

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)