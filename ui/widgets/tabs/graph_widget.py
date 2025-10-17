# graph_widget.py - Version complète intégrant le design et principes de relation_import_widget.py
import os
import json
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

import qtawesome as qta
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor

import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

from utils.logger import logger
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.taxonomy_item import TaxonomyItem

class QueryCache:
    """Système de cache pour les requêtes Dgraph avec expiration."""
    
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        self.cache[key] = (value, datetime.now())
    
    def clear(self):
        self.cache.clear()
    
    def get_stats(self) -> str:
        return f"Cache: {len(self.cache)} entrées"


class GraphWidget(QtWidgets.QWidget):
    """Widget intégré pour afficher un graphe des relations avec design de relation_import_widget"""

    node_selected = pyqtSignal(str, dict)  # Émet (nom_noeud, détails)
    
    def __init__(self, config_provider=None, conductor=None, dgraph_connector=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.dgraph_connector = dgraph_connector or LirisDgraphConnector(auto_reset=False)
        self.current_project_data = None
        self.current_graph = None
        self.current_relations = []
        self.hidden_relations = set()
        self.current_central_uid = None
        self.current_central_name = None
        
        # Système de cache
        self.query_cache = QueryCache(ttl_seconds=600)
        
        # Cache pour les mappings UID
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}
        
        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"
        
        # Données graphe pour interactions
        self.graph_data = None
        self.central_node = None
        self.related_items = []
        self.figure = None
        self.canvas = None
        self.selected_node = None
        self.info_text_obj = None
        
        self._init_ui()
        self._load_uid_mappings()
    
    def normalize_node_name(self, name: str) -> str:
        """Normalise le nom d'un nœud."""
        if not name or not isinstance(name, str):
            return f"unnamed_{id(name)}"
        name = name.strip()
        if not name or name.lower() == 'n/a':
            return f"unnamed_{id(name)}"
        base = os.path.basename(name)
        name_without_ext = os.path.splitext(base)[0]
        normalized = name_without_ext.strip()
        if not normalized:
            return f"unnamed_{id(name)}"
        return normalized
    
    def _get_dgraph_to_local_mapping(self):
        """Retourne le mapping Dgraph UID -> Local UID."""
        if not self.dgraph_to_local:
            self._load_uid_mappings()
        return self.dgraph_to_local
    
    def _get_node_uid_by_name(self, node_name: str) -> str:
        """Récupère l'UID d'un nœud par son nom avec cache."""
        if not node_name:
            return None
        cache_key = f"uid_by_name_{node_name}"
        cached_uid = self.query_cache.get(cache_key)
        if cached_uid:
            return cached_uid
        
        # Chercher dans mappings locaux
        for local_uid, dgraph_uid in self.local_to_dgraph.items():
            query = f"""{{q(func: uid({dgraph_uid})) {{name label}}}}"""
            result = self._execute_dgraph_query(query)
            if result and 'q' in result and result['q']:
                found_name = self.normalize_node_name(
                    result['q'][0].get('name') or result['q'][0].get('label', '')
                )
                if found_name == node_name:
                    self.query_cache.set(cache_key, dgraph_uid)
                    return dgraph_uid
        
        query = f"""{{q(func: has(name)) @filter(eq(name, "{node_name}")) {{uid}}}}"""
        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid
        
        query = f"""{{q(func: has(label)) @filter(eq(label, "{node_name}")) {{uid}}}}"""
        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid
        
        return None

    def _load_uid_mappings(self):
        """Charge les mappings UID depuis Dgraph avec cache."""
        cache_key = "uid_mappings"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            self.dgraph_to_local = cached_data.get('dgraph_to_local', {})
            self.local_to_dgraph = cached_data.get('local_to_dgraph', {})
            logger.info(f"Mappings UID chargés depuis cache: {len(self.dgraph_to_local)} entrées")
            return
        
        query = """{q(func: has(local_id)) {uid local_id}}"""
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result:
            for node in result['q']:
                dgraph_uid = node.get('uid')
                local_id = node.get('local_id')
                if dgraph_uid and local_id:
                    self.dgraph_to_local[dgraph_uid] = local_id
                    self.local_to_dgraph[local_id] = dgraph_uid
            
            self.query_cache.set(cache_key, {
                'dgraph_to_local': self.dgraph_to_local,
                'local_to_dgraph': self.local_to_dgraph
            })
        
        logger.info(f"Mappings UID chargés: {len(self.dgraph_to_local)} entrées")

    def _execute_dgraph_query(self, query: str) -> Optional[Dict]:
        """Exécute une requête Dgraph."""
        if not self.dgraph_connector:
            logger.error("Dgraph connector non initialisé")
            return None
        try:
            return self.dgraph_connector.query(query)
        except Exception as e:
            logger.error(f"Erreur requête Dgraph: {e}")
            return None

    def _get_node_details(self, uid: str) -> Dict:
        """Récupère les détails complets d'un nœud avec cache."""
        if not uid:
            return {}
        
        cache_key = f"node_details_{uid}"
        cached_data = self.query_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid name label level nodeType
            outgoing_relations {{target_uid target_name relation_type category line}}
            incoming_relations {{source_uid source_name relation_type category}}
            relations
            parents {{uid name label}}
            children: ~parents {{uid name label}}
            clusters {{uid name}}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        if result and 'node' in result and result['node']:
            node = result['node'][0]
            self.query_cache.set(cache_key, node)
            return node
        return {}

    def _get_global_relations(self) -> List[Dict]:
        """Récupère toutes les relations du projet avec cache."""
        if not self.current_project_data:
            return []
        
        project_uid = self.current_project_data.get('uid')
        cache_key = f"global_relations_{project_uid}"
        cached_data = self.query_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        relations_list = []
        dgraph_to_local = self._get_dgraph_to_local_mapping()
        
        query = """
        {
          allRelations(func: type(Relation)) {
            uid name relationType
            source {uid name label local_id}
            target {uid name label local_id}
          }
        }
        """
        
        result = self._execute_dgraph_query(query)
        if result and 'allRelations' in result:
            for rel in result['allRelations']:
                source_node = rel.get('source', {})
                target_node = rel.get('target', {})
                
                source_uid = source_node.get('uid')
                if source_uid and source_uid in dgraph_to_local:
                    source_uid = dgraph_to_local[source_uid]
                
                target_uid = target_node.get('uid')
                if target_uid and target_uid in dgraph_to_local:
                    target_uid = dgraph_to_local[target_uid]
                
                source_name = self.normalize_node_name(
                    source_node.get('name') or source_node.get('label', '')
                )
                target_name = self.normalize_node_name(
                    target_node.get('name') or target_node.get('label', '')
                )
                
                if source_name and target_name:
                    relations_list.append({
                        'source': source_name,
                        'target': target_name,
                        'relation_type': rel.get('relationType', 'relation'),
                        'category': 'parsed',
                        'is_analyzed': True
                    })
        
        self.query_cache.set(cache_key, relations_list)
        return relations_list

    def update_graph(self, central_node: str, central_uid: str, related_items: List[Dict], project_data: Dict):
        """Met à jour le graphe pour le nœud central sélectionné."""
        logger.info(f"=== UPDATE_GRAPH appelé ===")
        logger.info(f"  Central: {central_node}, UID: {central_uid}, Related: {len(related_items)}")
        
        if not central_node or not central_uid:
            self._clear_graph()
            return
        
        self.current_project_data = project_data
        self.central_node = central_node
        self.current_central_uid = central_uid
        self.related_items = related_items
        
        # Collecter nœuds sélectionnés
        selected_nodes_set = {central_node}
        for item in related_items:
            item_name = self.normalize_node_name(item.get('name', ''))
            if item_name:
                selected_nodes_set.add(item_name)
        
        # Récupérer relations globales et filtrer
        all_relations = self._get_global_relations()
        filtered_relations = []
        
        for rel in all_relations:
            source = rel.get('source', '')
            target = rel.get('target', '')
            if source in selected_nodes_set and target in selected_nodes_set:
                for item in related_items:
                    if item.get('name') == source or item.get('name') == target:
                        rel['taxonomy_level'] = item.get('taxonomy_level', 0)
                        break
                filtered_relations.append(rel)
        
        # Si pas de relations, créer artificielles
        if not filtered_relations:
            for item in related_items[:10]:
                item_name = self.normalize_node_name(item.get('name', ''))
                if item_name and item_name != central_node:
                    filtered_relations.append({
                        'source': central_node,
                        'target': item_name,
                        'relation_type': 'connected',
                        'category': 'taxonomy',
                        'taxonomy_level': item.get('taxonomy_level', 0)
                    })
        
        self.current_relations = filtered_relations
        self.current_graph = self._build_clean_graph(filtered_relations)
        
        # Récupérer détails nœuds
        for node in self.current_graph.nodes:
            dgraph_uid = self.local_to_dgraph.get(node, '')
            if dgraph_uid:
                node_details = self._get_node_details(dgraph_uid)
                self.current_graph.nodes[node]['level'] = node_details.get('level', 0)
                self.current_graph.nodes[node]['node_type'] = node_details.get('nodeType', 'unknown')
            else:
                for item in related_items:
                    if self.normalize_node_name(item.get('name', '')) == node:
                        self.current_graph.nodes[node]['level'] = item.get('taxonomy_level', 0)
                        self.current_graph.nodes[node]['node_type'] = item.get('type', 'unknown')
                        break
        
        self._draw_graph()
        self._update_legend()

    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """Construit un graphe NetworkX propre."""
        G = nx.DiGraph()
        nodes_registry = {}
        edges_registry = {}

        # Collecter nœuds uniques
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))
            if not source or not target:
                continue
            
            if source not in nodes_registry:
                nodes_registry[source] = 'dependency'
            if target not in nodes_registry:
                nodes_registry[target] = 'dependency'

        # Ajouter nœuds
        for node_name in nodes_registry:
            G.add_node(node_name, node_type='dependency')

        # Collecter arêtes uniques
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))
            rel_type = rel.get('relation_type', 'unknown')
            category = rel.get('category', 'custom')
            if not source or not target:
                continue
            
            edge_key = (source, target)
            if edge_key not in edges_registry:
                edges_registry[edge_key] = []
            
            type_label = f"{rel_type} [{category}]" if category == 'parsed' else rel_type
            if type_label not in edges_registry[edge_key]:
                edges_registry[edge_key].append(type_label)

        # Ajouter arêtes
        for (source, target), rel_types in edges_registry.items():
            primary_type = rel_types[0]
            combined_label = f"{primary_type} (+{len(rel_types)-1})" if len(rel_types) > 1 else primary_type
            G.add_edge(source, target,
                      color=self._get_color_for_type(primary_type),
                      relation_type=primary_type,
                      all_types=rel_types,
                      label=combined_label)

        # Supprimer nœuds isolés
        isolated_nodes = list(nx.isolates(G))
        if isolated_nodes:
            G.remove_nodes_from(isolated_nodes)

        return G

    def _get_color_for_type(self, rel_type: str) -> str:
        """Retourne une couleur pour le type de relation."""
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()
        
        color_map = {
            'import': '#FF8C00', 'from_import': '#FF8C00', 'require': '#FF8C00',
            'extends': '#00A65A', 'inherit': '#00A65A',
            'call': '#007ACC', 'function_call': '#007ACC',
            'parent': '#2196F3', 'child': '#4CAF50',
            'relation': '#8A2BE2', 'uses': '#FFA500',
        }
        
        for key, color in color_map.items():
            if key in rel_lower:
                return color
        return '#999999'

    def _get_color_for_node(self, node_type: str, level: int) -> str:
        """Retourne couleur nœud basée sur type et niveau."""
        color_map = {
            "folder": '#424242', "file": '#555555',
            "function": '#A23B2D', "dependency": '#555555',
            "class": '#424242', "variable": '#999999',
            "unknown": '#607D8B',
        }
        base_color = color_map.get(node_type, '#607D8B')
        if level > 1 and base_color == '#A23B2D':
            base_color = '#D35A4A'
        return base_color

    def _init_ui(self):
        """Initialise l'UI du widget graphe."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Canvas graphe
        self.figure = Figure(facecolor='white', figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self._on_graph_click)
        self.canvas.mpl_connect('motion_notify_event', self._on_graph_motion)
        self.canvas.mpl_connect('button_release_event', self._on_graph_release)
        layout.addWidget(self.canvas)
        
        # Légende dynamique
        legend_widget = QtWidgets.QWidget()
        self.legend_layout = QtWidgets.QHBoxLayout(legend_widget)
        self.legend_layout.setSpacing(2)
        layout.addWidget(legend_widget)

    def _draw_graph(self):
        """Dessine le graphe avec style relation_import_widget."""
        if not self.current_graph:
            return
        
        G = self.current_graph
        num_nodes = len(G.nodes())
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')
        
        self.graph_data = {
            'G': G, 'ax': ax, 'pos': {}, 'edges': [], 'edge_colors': [],
            'node_colors': [], 'node_sizes': [], 'labels': {}, 'edge_labels': {},
            'num_nodes': num_nodes,
            'min_distance': 0.3 if num_nodes <= 20 else 0.2 if num_nodes <= 50 else 0.15
        }
        data = self.graph_data
        
        # Layout avec collision avoidance
        if num_nodes > 100:
            pos = nx.kamada_kawai_layout(G, scale=3.0)
        elif num_nodes > 50:
            pos = nx.spring_layout(G, k=2.0, iterations=300, seed=42, scale=3.0)
        else:
            k_value = 3.0 / (num_nodes ** 0.4)
            pos = nx.spring_layout(G, k=k_value, iterations=300, seed=42, scale=3.0)
        
        pos = self._apply_collision_avoidance(G, pos, num_nodes)
        data['pos'] = {node: list(coord) for node, coord in pos.items()}
        
        # Préparer arêtes et couleurs - CORRECTION ICI
        for u, v, edge_data in G.edges(data=True):
            data['edges'].append((u, v))
            data['edge_colors'].append(edge_data.get('color', '#CCCCCC'))
        
        # Préparer nœuds avec couleurs modulées
        for node in G.nodes():
            node_type = G.nodes[node].get('node_type', 'unknown')
            level = G.nodes[node].get('level', 0)
            
            # Couleur spéciale pour nœud central
            if node == self.central_node:
                data['node_colors'].append('#8B2E1F')
                data['node_sizes'].append(int((300 if num_nodes <= 20 else 200) * 1.3))
            else:
                data['node_colors'].append(self._get_color_for_node(node_type, level))
                data['node_sizes'].append(300 if num_nodes <= 20 else 200 if num_nodes <= 50 else 100)
            
            data['labels'][node] = node
        
        # Préparer labels arêtes
        data['edge_labels'] = {(u, v): d['label'] for u, v, d in G.edges(data=True)}
        
        # Dessiner arêtes
        curvature = 0.1 if num_nodes <= 15 else 0.05
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=data['edge_colors'],
                               width=1.5 if num_nodes > 50 else 2.0,
                               alpha=0.6, arrows=True,
                               arrowsize=10 if num_nodes > 50 else 14,
                               connectionstyle=f'arc3,rad={curvature}')
        
        # Dessiner nœuds
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=data['node_colors'],
                               node_size=data['node_sizes'], alpha=0.9,
                               edgecolors='#2C2C2C', 
                               linewidths=2.5 if num_nodes <= 50 else 1.5)
        
        # Labels nœuds
        if data['labels']:
            font_size = 9 if num_nodes <= 15 else 7 if num_nodes <= 30 else 6
            nx.draw_networkx_labels(G, pos, data['labels'], ax=ax,
                                    font_size=font_size,
                                    font_weight='bold', font_color='#000000',
                                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                            edgecolor='none', alpha=0.85))
        
        # Labels arêtes si petit graphe
        if data['edge_labels'] and num_nodes <= 30:
            nx.draw_networkx_edge_labels(G, pos, data['edge_labels'], ax=ax,
                                        font_size=6 if num_nodes > 15 else 7,
                                        font_color='#444444',
                                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                                edgecolor='none', alpha=0.7))
        
        # Cercle central
        if self.central_node and self.central_node in G.nodes:
            circle = Circle(pos[self.central_node], 0.15, color='red', fill=False, 
                          linewidth=3, alpha=0.8)
            ax.add_patch(circle)
        
        # Détails nœud sélectionné
        if self.selected_node:
            self._show_node_details_in_graph(self.selected_node, G)

        ax.axis('off')
        ax.margins(0.12 if num_nodes <= 50 else 0.08)
        self.canvas.draw_idle()

    def _update_legend(self):
        """Met à jour la légende."""
        while self.legend_layout.count() > 0:
            child = self.legend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_graph:
            return
        
        relation_types = defaultdict(int)
        for _, _, d in self.current_graph.edges(data=True):
            rel_type = d.get('relation_type', 'unknown')
            relation_types[rel_type] += 1
        
        for rel_type, count in sorted(relation_types.items()):
            color = self._get_color_for_type(rel_type)
            type_label = QtWidgets.QLabel(f"● {rel_type} ({count})")
            type_label.setStyleSheet(f"color: {color}; font-size: 9px; padding: 0 6px;")
            self.legend_layout.addWidget(type_label)

    def _apply_collision_avoidance(self, G, pos, num_nodes):
        """Applique collision avoidance."""
        min_distance = 0.3 if num_nodes <= 20 else 0.2 if num_nodes <= 50 else 0.15
        iterations = 50 if num_nodes <= 30 else 30

        for iteration in range(iterations):
            nodes = list(G.nodes())
            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]
                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]
                    dx, dy = x2 - x1, y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5
                    if distance < min_distance and distance > 0:
                        angle = dy / distance if distance > 0 else 0
                        angle_cos = dx / distance if distance > 0 else 1
                        force = (min_distance - distance) / 10
                        pos[node1][0] -= force * angle_cos
                        pos[node1][1] -= force * angle
                        pos[node2][0] += force * angle_cos
                        pos[node2][1] += force * angle
            if iteration % 10 == 0:
                min_distance *= 0.98
        return pos

    def _apply_local_collision_avoidance(self, dragging_node):
        """Collision avoidance locale."""
        pos = self.graph_data['pos']
        G = self.graph_data['G']
        min_distance = self.graph_data['min_distance']
        x1, y1 = pos[dragging_node]
        
        for node in G.nodes():
            if node == dragging_node:
                continue
            x2, y2 = pos[node]
            dx, dy = x2 - x1, y2 - y1
            distance = (dx**2 + dy**2) ** 0.5
            if distance < min_distance and distance > 0.01:
                angle_cos = dx / distance
                angle_sin = dy / distance
                force = (min_distance - distance) / 20
                pos[node][0] += force * angle_cos
                pos[node][1] += force * angle_sin

    def _show_node_details_in_graph(self, node_name, G):
        """Affiche détails nœud dans graphe - STYLE RELATION_IMPORT_WIDGET."""
        ax = self.graph_data['ax']
        
        # Supprimer ancien texte
        if self.info_text_obj:
            try:
                self.info_text_obj.remove()
            except:
                pass
            self.info_text_obj = None
        
        node_data = G.nodes[node_name]
        node_type = node_data.get('node_type', 'unknown')
        outgoing = list(G.out_edges(node_name, data=True))
        incoming = list(G.in_edges(node_name, data=True))
        
        # Construire texte compact
        info_lines = []
        display_name = node_name[:25] + '..' if len(node_name) > 25 else node_name
        info_lines.append(f"╔═ {display_name} ═╗")
        info_lines.append(f"Type: {node_type}")
        info_lines.append("")
        
        info_lines.append(f"→ Sortantes ({len(outgoing)}):")
        for i, (source, target, data) in enumerate(outgoing[:4]):
            rel_type = data.get('relation_type', 'relation')
            target_short = target[:20] + '..' if len(target) > 20 else target
            rel_short = rel_type[:15] + '..' if len(rel_type) > 15 else rel_type
            info_lines.append(f"  → {target_short}")
            info_lines.append(f"     [{rel_short}]")
        if len(outgoing) > 4:
            info_lines.append(f"  ... +{len(outgoing) - 4} autres")
        
        info_lines.append("")
        info_lines.append(f"← Entrantes ({len(incoming)}):")
        for i, (source, target, data) in enumerate(incoming[:4]):
            rel_type = data.get('relation_type', 'relation')
            source_short = source[:20] + '..' if len(source) > 20 else source
            rel_short = rel_type[:15] + '..' if len(rel_type) > 15 else rel_type
            info_lines.append(f"  ← {source_short}")
            info_lines.append(f"     [{rel_short}]")
        if len(incoming) > 4:
            info_lines.append(f"  ... +{len(incoming) - 4} autres")
        
        info_lines.append("")
        info_lines.append("Double-clic: masquer")
        
        # Afficher texte en haut à gauche
        text = "\n".join(info_lines)
        self.info_text_obj = ax.text(
            0.02, 0.98, text,
            transform=ax.transAxes,
            ha='left', va='top',
            color='#222222', 
            fontsize=7,
            family='monospace',
            bbox=dict(
                boxstyle='round,pad=0.6',
                facecolor='#FFFFFF',
                edgecolor='#666666',
                alpha=0.95,
                linewidth=1.5
            ),
            zorder=1000
        )
        
        self.graph_data['selected_node'] = node_name
        
        # Émettre signal avec détails pour mise à jour externe
        node_details = {
            'name': node_name,
            'type': node_type,
            'outgoing': [(s, t, d.get('relation_type', 'relation')) for s, t, d in outgoing],
            'incoming': [(s, t, d.get('relation_type', 'relation')) for s, t, d in incoming],
            'level': node_data.get('level', 0)
        }
        self.node_selected.emit(node_name, node_details)
        
        self.canvas.draw_idle()

    def _on_graph_click(self, event):
        """Gère le clic pour sélection et drag - STYLE RELATION_IMPORT_WIDGET."""
        if not self.graph_data or event.inaxes != self.graph_data['ax']:
            return

        node_name = None
        for node, pos in self.graph_data['pos'].items():
            dist = ((event.xdata - pos[0])**2 + (event.ydata - pos[1])**2)**0.5
            if dist < 0.1:
                node_name = node
                break
        
        if event.button == 1:  # Clic gauche
            if event.dblclick and node_name:  # Double-clic sur nœud
                self._show_node_details_in_graph(node_name, self.current_graph)
            elif event.dblclick and not node_name:  # Double-clic zone vide: masquer
                if self.info_text_obj:
                    try:
                        self.info_text_obj.remove()
                    except:
                        pass
                    self.info_text_obj = None
                    self.graph_data['selected_node'] = None
                    self.canvas.draw_idle()
            elif node_name:  # Clic simple: préparer drag
                self.graph_data['dragging_node'] = node_name
                self.canvas.setCursor(QCursor(Qt.ClosedHandCursor))
        
        elif event.button == 3 and node_name:  # Clic droit: afficher détails
            self._show_node_details_in_graph(node_name, self.current_graph)

    def _redraw_graph_with_positions(self):
        """Redessine le graphe en gardant positions actuelles."""
        if not self.graph_data:
            return
        
        G = self.graph_data['G']
        pos = self.graph_data['pos']
        ax = self.graph_data['ax']
        ax.clear()
        ax.set_facecolor('white')

        edges = self.graph_data['edges']
        edge_colors = self.graph_data['edge_colors']
        num_nodes = self.graph_data['num_nodes']

        # Redessiner arêtes
        curvature = 0.1 if num_nodes <= 15 else 0.05
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                             width=1.5 if num_nodes > 50 else 2.0,
                             alpha=0.6, arrows=True,
                             arrowsize=10 if num_nodes > 50 else 14,
                             connectionstyle=f'arc3,rad={curvature}')

        # Redessiner nœuds
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=self.graph_data['node_colors'],
                             node_size=self.graph_data['node_sizes'], alpha=0.9,
                             edgecolors='#2C2C2C', 
                             linewidths=2.5 if num_nodes <= 50 else 1.5)

        # Redessiner labels
        if self.graph_data['labels']:
            font_size = 9 if num_nodes <= 15 else 7 if num_nodes <= 30 else 6
            nx.draw_networkx_labels(G, pos, self.graph_data['labels'], ax=ax,
                                  font_size=font_size,
                                  font_weight='bold', font_color='#000000',
                                  bbox=dict(boxstyle='round,pad=0.3',
                                          facecolor='white', edgecolor='none', alpha=0.85))

        # Redessiner labels arêtes
        if self.graph_data['edge_labels'] and num_nodes <= 30:
            nx.draw_networkx_edge_labels(G, pos, self.graph_data['edge_labels'], ax=ax,
                                        font_size=6 if num_nodes > 15 else 7,
                                        font_color='#444444',
                                        bbox=dict(boxstyle='round,pad=0.3',
                                                facecolor='white', edgecolor='none', alpha=0.7))

        # Cercle central
        if self.central_node and self.central_node in G.nodes:
            circle = Circle(pos[self.central_node], 0.15, color='red', fill=False, 
                          linewidth=3, alpha=0.8)
            ax.add_patch(circle)

        # Re-afficher détails si nœud était sélectionné
        if self.selected_node:
            self._show_node_details_in_graph(self.selected_node, G)

        ax.axis('off')
        ax.margins(0.12 if num_nodes <= 50 else 0.08)
        self.canvas.draw_idle()

    def _on_graph_motion(self, event):
        """Gère mouvement souris pour déplacer nœuds."""
        if not self.graph_data or event.inaxes != self.graph_data['ax']:
            return

        dragging_node = self.graph_data.get('dragging_node')
        if dragging_node is None or event.xdata is None or event.ydata is None:
            return

        self.graph_data['pos'][dragging_node] = [event.xdata, event.ydata]
        self._apply_local_collision_avoidance(dragging_node)
        self._redraw_graph_with_positions()

    def _on_graph_release(self, event):
        """Fin du drag."""
        if self.graph_data and self.graph_data.get('dragging_node'):
            self.graph_data['dragging_node'] = None
            self.canvas.setCursor(QCursor(Qt.ArrowCursor))

    def _export_graph(self):
        """Exporte le graphe en PNG."""
        if not self.central_node:
            return
        try:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Exporter le graphe",
                f"graph_{self.central_node}.png",
                "PNG Files (*.png);;All Files (*)"
            )
            
            if file_path:
                self.figure.savefig(file_path, dpi=150, bbox_inches='tight', facecolor='white')
                QtWidgets.QMessageBox.information(
                    self,
                    "Succès",
                    f"Graphe exporté vers:\n{file_path}"
                )
                logger.info(f"Graph exported to: {file_path}")
        except Exception as e:
            logger.error(f"Error exporting graph: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible d'exporter le graphe:\n{str(e)}"
            )

    def refresh(self):
        """Rafraîchit le graphe et cache."""
        self.query_cache.clear()
        self._load_uid_mappings()
        if self.central_node:
            self.update_graph(self.central_node, self.current_central_uid, 
                            self.related_items, self.current_project_data)

    def _clear_graph(self):
        """Vide le graphe."""
        self.current_graph = None
        if self.figure:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "Aucune donnée à afficher", ha='center', va='center',
                   color='#999999', fontsize=12, style='italic')
            ax.axis('off')
            self.canvas.draw()
        
        # Clear dynamic legend items
        while self.legend_layout.count() > 0:
            child = self.legend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def closeEvent(self, event):
        """Fermeture propre."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)