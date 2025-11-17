from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QLabel
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui.localization.translator import tr
from utils.logger import logger
from utils.multi_language_parser import (
    normalize_node_name
)

class RelationsGraphWidget(QtWidgets.QWidget):
    """Widget optimisé pour afficher le graphe des relations du nœud sélectionné"""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget
        self.current_project_profile_data = None
        self.figure = None
        self.canvas = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(5)
    
        # Titre dynamique / Dynamic Title
        self.title_label = QLabel(tr("relations_graph.title"))
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50;")
        layout.addWidget(self.title_label)
    
        # Canvas pour le graphe / Canvas for the graph
        self.figure = Figure(figsize=(5, 3), facecolor='white', dpi=100)  # Taille optimisée pour le panneau
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(250)
        layout.addWidget(self.canvas)
    
        # Légende simplifiée / Simplified legend
        self.legend_label = QLabel(tr("relations_graph.no_node_selected"))
        self.legend_label.setStyleSheet("font-size: 10px; color: #666; font-style: italic;")
        layout.addWidget(self.legend_label)
    
        # Message initial / Initial message
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
        Met à jour le graphe pour le nœud central sélectionné.
        Version corrigée : affiche toujours le NOM du nœud central au lieu de l'UID.
        """
        if not central_uid:
            self._draw_empty_graph()
            self.title_label.setText("Graphe des Relations")
            self.legend_label.setText("Aucun nœud sélectionné")
            return

        # 🔸 1. Récupérer les infos du nœud central
        central_info = self.parent_widget.label_uid_to_info.get(central_uid)

        if not central_info:
            # Fallback : essayer via Dgraph
            central_info = self._query_node_info_from_dgraph(central_uid)

            if central_info:
                # Mettre en cache local pour réutilisation
                self.parent_widget.label_uid_to_info[central_uid] = central_info
            else:
                # Si toujours rien, utiliser fallback minimal
                logger.warning(f"Nœud {central_uid} introuvable, utilisation de fallback")
                central_info = {
                    'name': f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid,
                    'label': f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid,
                    'cluster': 'inconnu',
                    'type': 'unknown'
                }

        # 🔸 2. Déterminer le nom à afficher
        central_name = (
            central_info.get('name') 
            or central_info.get('label') 
            or self.parent_widget.name_to_uid.get(central_uid) 
            or f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid
        )

        related_items = self._collect_related_items(central_uid, max_depth=1, max_nodes=50)

        if not related_items:
            self.title_label.setText(f"Graphe des relations : {central_name}")
            self.legend_label.setText("Aucune relation trouvée")
            self._draw_empty_graph_with_message(
                f"Le nœud « {central_name} » n'a aucune relation"
            )
            logger.info(f"Aucune relation pour {central_name}")
            return

        # 🔸 4. Affichage du graphe
        logger.info(f"Affichage du graphe pour {central_name}: {len(related_items)} relations")
        self.title_label.setText(f"Graphe des relations : {central_name}")
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
        # CORRECTION: eq(target, {dgraph_uid}) au lieu de eq(target.uid, ...)
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
          incoming(func: type(Relation)) @filter(eq(target, {dgraph_uid})) {{
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
        Collecte les nœuds liés au nœud central jusqu'à une profondeur donnée.
        VERSION COMPLÈTE ET CORRIGÉE : Inclut enfants, classes, fonctions, variables, Dgraph mappings
        
        Args:
            central_uid: UID du nœud central
            max_depth: Profondeur maximale de recherche
            max_nodes: Nombre maximum de nœuds à collecter
        
        Returns:
            Dict avec 'nodes' et 'edges'
        """
        if not central_uid:
            return {'nodes': [], 'edges': []}
        
        # ✅ Synchroniser les données si nécessaire
        if not self.current_project_profile_data:
            self.current_project_profile_data = getattr(
                self.parent_widget,
                'current_project_profile_data',
                None
            )
        
        if not self.current_project_profile_data:
            logger.warning("❌ Aucune donnée de projet pour le graphe")
            return {'nodes': [], 'edges': []}
        
        # ✅ Résoudre les mappings Dgraph <-> local
        local_to_dgraph = self.parent_widget._get_local_to_dgraph_mapping()
        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()
        
        # Si central_uid est un UID Dgraph, mapper vers local
        if isinstance(central_uid, str) and central_uid.startswith('0x'):
            central_uid = dgraph_to_local.get(central_uid, central_uid)
        
        # ✅ Récupérer tous les nœuds connus
        all_nodes = self.parent_widget.dgraph_manager._get_all_nodes(
            self.current_project_profile_data
        )
        
        if not all_nodes:
            logger.warning("❌ Aucun nœud disponible dans le graphe")
            return {'nodes': [], 'edges': []}
        
        node_map = {node['uid']: node for node in all_nodes if 'uid' in node}
        central_node = node_map.get(central_uid)
        if not central_node:
            logger.warning(f"Nœud central {central_uid} non trouvé")
            return {'nodes': [], 'edges': []}
        
        collected_nodes = {}
        collected_edges = []
        visited = set()
        
        def collect_recursive(uid, depth):
            """Récursion pour collecter les nœuds liés."""
            if depth > max_depth or len(collected_nodes) >= max_nodes or uid in visited:
                return
            
            visited.add(uid)
            node = node_map.get(uid)
            if not node:
                return
            
            # Informations sur le nœud
            node_info = self.parent_widget.label_uid_to_info.get(uid, {})
            collected_nodes[uid] = {
                'uid': uid,
                'name': node_info.get('name', node.get('label', node.get('name', 'Unknown'))),
                'type': node_info.get('type', node.get('type', 'unknown')),
                'cluster': node_info.get('cluster', 'unknown'),
                'depth': depth
            }
            
            # === 1. RELATIONS SORTANTES ===
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')
                if not target_uid:
                    continue
                
                if target_uid.startswith('0x'):
                    target_uid = dgraph_to_local.get(target_uid, target_uid)
                
                edge = {
                    'source': uid,
                    'target': target_uid,
                    'type': rel.get('relation_type', 'relation'),
                    'category': rel.get('category', 'custom'),
                    'unresolved': target_uid.startswith('temp_') or target_uid.startswith('unresolved_')
                }
                collected_edges.append(edge)
                
                if not edge['unresolved'] and depth < max_depth and len(collected_nodes) < max_nodes:
                    collect_recursive(target_uid, depth + 1)
            
            # === 2. RELATIONS ENTRANTES ===
            for rel in node.get('incoming_relations', []):
                source_uid = rel.get('source_uid')
                if not source_uid:
                    continue
                
                if source_uid.startswith('0x'):
                    source_uid = dgraph_to_local.get(source_uid, source_uid)
                
                edge = {
                    'source': source_uid,
                    'target': uid,
                    'type': rel.get('relation_type', 'relation'),
                    'category': rel.get('category', 'custom'),
                    'unresolved': source_uid.startswith('temp_') or source_uid.startswith('unresolved_')
                }
                collected_edges.append(edge)
                
                if not edge['unresolved'] and depth < max_depth and len(collected_nodes) < max_nodes:
                    collect_recursive(source_uid, depth + 1)
            
            # === 3. ENFANTS HIÉRARCHIQUES ===
            for child in node.get('children', []):
                child_uid = child.get('uid')
                if not child_uid:
                    continue
                
                edge = {
                    'source': uid,
                    'target': child_uid,
                    'type': 'child',
                    'category': 'hierarchy',
                    'unresolved': False
                }
                collected_edges.append(edge)
                
                if depth < max_depth and len(collected_nodes) < max_nodes:
                    collect_recursive(child_uid, depth + 1)
            
            # === 4. CLASSES ===
            for cls in node.get('classes', []):
                cls_uid = cls.get('uid')
                if not cls_uid:
                    continue
                
                edge = {
                    'source': uid,
                    'target': cls_uid,
                    'type': 'contains_class',
                    'category': 'code',
                    'unresolved': False
                }
                collected_edges.append(edge)
                
                if cls_uid not in collected_nodes and len(collected_nodes) < max_nodes:
                    collected_nodes[cls_uid] = {
                        'uid': cls_uid,
                        'name': cls.get('name', 'Class'),
                        'type': 'class',
                        'cluster': node_info.get('cluster', 'unknown'),
                        'depth': depth + 1
                    }
                
                if depth < max_depth and len(collected_nodes) < max_nodes:
                    collect_recursive(cls_uid, depth + 1)
            
            # === 5. FONCTIONS ===
            for func in node.get('functions', []):
                func_uid = func.get('uid')
                if not func_uid:
                    continue
                
                edge = {
                    'source': uid,
                    'target': func_uid,
                    'type': 'contains_function',
                    'category': 'code',
                    'unresolved': False
                }
                collected_edges.append(edge)
                
                if func_uid not in collected_nodes and len(collected_nodes) < max_nodes:
                    collected_nodes[func_uid] = {
                        'uid': func_uid,
                        'name': func.get('name', 'Function'),
                        'type': func.get('type', 'function'),
                        'cluster': node_info.get('cluster', 'unknown'),
                        'depth': depth + 1
                    }
                
                if depth < max_depth and len(collected_nodes) < max_nodes:
                    collect_recursive(func_uid, depth + 1)
            
            # === 6. VARIABLES ===
            for var in node.get('variables', []):
                var_uid = var.get('uid')
                if not var_uid:
                    continue
                
                edge = {
                    'source': uid,
                    'target': var_uid,
                    'type': 'contains_variable',
                    'category': 'code',
                    'unresolved': False
                }
                collected_edges.append(edge)
                
                if var_uid not in collected_nodes and len(collected_nodes) < max_nodes:
                    collected_nodes[var_uid] = {
                        'uid': var_uid,
                        'name': var.get('name', 'Variable'),
                        'type': var.get('type', 'variable'),
                        'cluster': node_info.get('cluster', 'unknown'),
                        'depth': depth + 1
                    }
        
        # === Début de la collecte ===
        collect_recursive(central_uid, 0)
        
        return {
            'nodes': list(collected_nodes.values()),
            'edges': collected_edges
        }

    
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
        Dessine le graphe avec NetworkX using nodes and edges
        """
        nodes = related_items.get('nodes', [])
        edges = related_items.get('edges', [])
        
        self.figure.clear()
        G = nx.DiGraph()

        # Add central node
        G.add_node(central_uid, node_type='central', label=central_name)

        # Add related nodes
        node_map = {node['uid']: node for node in nodes}
        for node in nodes:
            G.add_node(node['uid'], node_type='related', label=node['name'])

        # Add edges
        relation_types = {}
        edge_colors_map = {}
        for edge in edges:
            source = edge['source']
            target = edge['target']
            rel_type = edge['type']
            
            if source not in G.nodes or target not in G.nodes:
                continue
                
            G.add_edge(source, target, type=rel_type)
            
            # Count types
            base_type = rel_type.replace(' (inverse)', '')
            relation_types[base_type] = relation_types.get(base_type, 0) + 1
            
            # Color for this edge
            color = self._get_color_for_type(rel_type)
            edge_colors_map[(source, target)] = color

        if len(G.nodes()) == 1:
            self._draw_empty_graph()
            return

        # Layout
        num_nodes = len(G.nodes())
        if num_nodes <= 10:
            pos = nx.spring_layout(G, k=2.5, iterations=100, seed=42)
        elif num_nodes <= 30:
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.circular_layout(G)
            if central_uid in pos:
                pos[central_uid] = (0, 0)

        # Draw
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Edges with colors
        if G.edges():
            nx.draw_networkx_edges(
                G, pos, 
                edgelist=list(G.edges()),
                edge_color=[edge_colors_map.get(edge, '#999999') for edge in G.edges()],
                ax=ax,
                width=2.0 if num_nodes <= 20 else 1.5,
                alpha=0.7,
                arrows=True,
                arrowsize=15 if num_nodes <= 20 else 12,
                arrowstyle='->',
                connectionstyle='arc3,rad=0.1'
            )

        # Nodes
        node_colors = ['#A23B2D' if node == central_uid else '#4CAF50' for node in G.nodes()]
        node_sizes = [800 if node == central_uid else 500 for node in G.nodes()]

        nx.draw_networkx_nodes(
            G, pos, 
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.85,
            linewidths=2,
            edgecolors='white'
        )

        # Labels
        labels = {node: G.nodes[node].get('label', node)[:15] + "..." if len(G.nodes[node].get('label', node)) > 15 else G.nodes[node].get('label', node) for node in G.nodes()}
        label_opts = {
            'ax': ax,
            'font_size': 9 if num_nodes > 20 else 10,
            'font_weight': 'bold',
        }

        if num_nodes <= 30:
            label_opts.update({
                'font_color': 'white',
                'bbox': dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7, edgecolor='none')
            })
        else:
            label_opts['font_color'] = 'black'

        nx.draw_networkx_labels(G, pos, labels, **label_opts)

        # Edge labels for small graphs
        if num_nodes <= 15:
            edge_labels = {(u,v): d['type'][:6] for u,v,d in G.edges(data=True)}
            nx.draw_networkx_edge_labels(
                G, pos, 
                edge_labels,
                ax=ax,
                font_size=7,
                font_color='#333',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.9)
            )

        # Title
        title_text = f"Réseau de relations\nNœud central: {central_name}\n({num_nodes} nœuds, {len(G.edges())} relations)"
        ax.set_title(title_text, fontsize=11, fontweight='bold', pad=15)

        ax.axis('off')
        ax.margins(0.15)

        self.figure.tight_layout()
        self.canvas.draw()

        # Update legend
        self._update_legend_with_types(relation_types)

    def _get_color_for_type(self, rel_type):
        """
        Retourne une couleur selon le type de relation.
        Ajoute support pour les types parsés.
        """
        rel_lower = rel_type.lower().replace(' (inverse)', '').replace('[code]', '').replace('[custom]', '').replace('[hierarchy]', '').strip()

        colors = {
            'import': '#FF9800',           # Orange pour imports
            'heritage': '#2196F3',         # Bleu pour héritage
            'extends': '#4CAF50',          # Vert pour extends
            'implement': '#9C27B0',        # Violet pour implement
            'depends_on': '#FF5722',       # Rouge pour dépendances
            'calls': '#00BCD4',            # Cyan pour appels
            'uses': '#795548',             # Marron pour usages
            'references': '#607D8B',       # Gris-bleu pour références
            'child': '#00BCD4',            # Cyan pour hiérarchie
            'parent': '#3F51B5',           # Bleu foncé pour parents
            'relation': '#E91E63',         # Rose pour relations génériques
        }

        # Recherche exacte puis partielle
        if rel_lower in colors:
            return colors[rel_lower]

        for key, color in colors.items():
            if key in rel_lower:
                return color

        return '#999999'

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

    def query_enriched_relations(self, project_name=None, relation_type=None, limit=100):
        """
        ✅ Requête pour récupérer les relations enrichies avec toutes les métadonnées
        
        Args:
            project_name: Filtrer par projet (optionnel)
            relation_type: Filtrer par type de relation (optionnel)
            limit: Nombre max de relations
        
        Returns:
            Dict avec les relations enrichies
        """
        if not self.client:
            logger.error("❌ Dgraph client non disponible")
            return None
    
        # Construire les filtres
        filters = []
        if relation_type:
            filters.append(f'eq(relationType, "{relation_type}")')
        
        filter_str = " and ".join(filters) if filters else ""
        filter_clause = f"@filter({filter_str})" if filter_str else ""
    
        query = f"""
        {{
          relations(func: type(Relation), first: {limit}) {filter_clause} {{
            uid
            name
            relationType
            category
            line
            intraFile
            createdAt
            
            # ✅ MÉTADONNÉES SOURCE
            sourceName
            sourceDescription
            sourcePath
            sourceType
            
            # ✅ MÉTADONNÉES TARGET
            targetName
            targetDescription
            targetPath
            targetType
            
            # ✅ RÉFÉRENCES COMPLÈTES
            source {{
              uid
              name
              path
              nodeType
              dgraph.type
            }}
            
            target {{
              uid
              name
              path
              nodeType
              dgraph.type
            }}
          }}
        }}
        """
    
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            data = self._parse_response(resp)
            txn.discard()
    
            relations = data.get('relations', [])
            logger.info(f"✅ {len(relations)} relations enrichies récupérées")
    
            # Statistiques
            stats = {
                'total': len(relations),
                'by_type': {},
                'by_category': {},
                'with_metadata': 0
            }
    
            for rel in relations:
                rel_type = rel.get('relationType', 'unknown')
                category = rel.get('category', 'unknown')
                
                stats['by_type'][rel_type] = stats['by_type'].get(rel_type, 0) + 1
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
                
                if rel.get('sourceName') and rel.get('targetName'):
                    stats['with_metadata'] += 1
    
            logger.info(f"📊 Statistiques:")
            logger.info(f"  • Total: {stats['total']}")
            logger.info(f"  • Avec métadonnées: {stats['with_metadata']}")
            logger.info(f"  • Par type: {stats['by_type']}")
            logger.info(f"  • Par catégorie: {stats['by_category']}")
    
            return data
    
        except Exception as e:
            logger.error(f"❌ Erreur requête relations enrichies: {e}")
            import traceback
            traceback.print_exc()
            return None
    

    def query_node_relations(self, node_uid, include_incoming=True, include_outgoing=True):
        """
        ✅ Récupère toutes les relations d'un nœud spécifique (entrantes + sortantes) avec métadonnées

        Args:
            node_uid: UID du nœud
            include_incoming: Inclure relations entrantes
            include_outgoing: Inclure relations sortantes

        Returns:
            Dict avec les relations du nœud
        """
        if not self.client:
            logger.error("❌ Dgraph client non disponible")
            return None

        query = f"""
        {{
          node(func: uid({node_uid})) {{
            uid
            name
            path
            nodeType
            dgraph.type

            {f'''
            # ✅ RELATIONS SORTANTES (ce nœud est la SOURCE)
            outgoing: ~source @filter(type(Relation)) {{
              uid
              relationType
              category
              line

              # Métadonnées source (ce nœud)
              sourceName
              sourcePath
              sourceType

              # Métadonnées target
              targetName
              targetPath
              targetType

              # Référence target
              target {{
                uid
                name
                path
                nodeType
              }}
            }}
            ''' if include_outgoing else ''}

            {f'''
            # ✅ RELATIONS ENTRANTES (ce nœud est la TARGET)
            incoming: ~target @filter(type(Relation)) {{
              uid
              relationType
              category
              line

              # Métadonnées source
              sourceName
              sourcePath
              sourceType

              # Métadonnées target (ce nœud)
              targetName
              targetPath
              targetType

              # Référence source
              source {{
                uid
                name
                path
                nodeType
              }}
            }}
            ''' if include_incoming else ''}
          }}
        }}
        """

        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            data = self._parse_response(resp)
            txn.discard()

            nodes = data.get('node', [])
            if not nodes:
                logger.warning(f"⚠️ Nœud {node_uid} non trouvé")
                return None

            node = nodes[0]
            outgoing = node.get('outgoing', [])
            incoming = node.get('incoming', [])

            logger.info(f"✅ Nœud: {node.get('name', 'Unknown')}")
            logger.info(f"  • Relations sortantes: {len(outgoing)}")
            logger.info(f"  • Relations entrantes: {len(incoming)}")

            # Affichage détaillé
            if outgoing:
                logger.info(f"\n  📤 SORTANTES:")
                for rel in outgoing[:5]:  # Limiter l'affichage
                    logger.info(
                        f"    • {rel.get('sourceName', '?')} "
                        f"--{rel.get('relationType')}--> "
                        f"{rel.get('targetName', '?')} "
                        f"[{rel.get('targetPath', '?')}]"
                    )

            if incoming:
                logger.info(f"\n  📥 ENTRANTES:")
                for rel in incoming[:5]:
                    logger.info(
                        f"    • {rel.get('sourceName', '?')} "
                        f"[{rel.get('sourcePath', '?')}] "
                        f"--{rel.get('relationType')}--> "
                        f"{rel.get('targetName', '?')}"
                    )

            return data

        except Exception as e:
            logger.error(f"❌ Erreur requête relations nœud: {e}")
            import traceback
            traceback.print_exc()
            return None


    def search_relations_by_path(self, source_path=None, target_path=None, relation_type=None):
        """
        ✅ Recherche de relations par chemin source/target

        Args:
            source_path: Chemin du fichier source (ex: "src/main.py")
            target_path: Chemin du fichier target
            relation_type: Type de relation (optionnel)

        Returns:
            Dict avec les relations trouvées
        """
        if not self.client:
            logger.error("❌ Dgraph client non disponible")
            return None

        # Construire les filtres
        filters = []
        if source_path:
            filters.append(f'eq(sourcePath, "{source_path}")')
        if target_path:
            filters.append(f'eq(targetPath, "{target_path}")')
        if relation_type:
            filters.append(f'eq(relationType, "{relation_type}")')

        filter_str = " and ".join(filters)

        query = f"""
        {{
          relations(func: type(Relation)) @filter({filter_str}) {{
            uid
            relationType
            category
            line

            sourceName
            sourcePath
            sourceType

            targetName
            targetPath
            targetType

            source {{
              uid
              name
            }}

            target {{
              uid
              name
            }}
          }}
        }}
        """

        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            data = self._parse_response(resp)
            txn.discard()

            relations = data.get('relations', [])
            logger.info(f"✅ {len(relations)} relations trouvées")

            for rel in relations:
                logger.info(
                    f"  • {rel.get('sourceName')} [{rel.get('sourcePath')}] "
                    f"--{rel.get('relationType')}--> "
                    f"{rel.get('targetName')} [{rel.get('targetPath')}]"
                )

            return data

        except Exception as e:
            logger.error(f"❌ Erreur recherche relations: {e}")
            return None