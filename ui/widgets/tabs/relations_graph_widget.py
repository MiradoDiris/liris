from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QLabel
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import logger
from utils.multi_language_parser import (
    normalize_node_name
)

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
        Version enrichie qui collecte TOUTES les relations (hiérarchiques + parsées + dict relations).
        """
        if not self.parent_widget.current_project_profile_data:
            return []

        all_nodes = self.parent_widget._get_all_nodes()
        central_node = next((n for n in all_nodes if n['uid'] == central_uid), None)
        if not central_node:
            return []

        related = []
        visited = set([central_uid])
        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()

        # === 1. RELATIONS SORTANTES (CUSTOM + PARSÉES depuis outgoing_relations) ===
        for rel in central_node.get('outgoing_relations', []):
            target_uid = rel.get('target_uid', rel.get('target_id', ''))

            # Skip temporaires
            if target_uid.startswith('temp_'):
                continue

            # Mapper si hex Dgraph
            if target_uid.startswith('0x') and len(target_uid) == 6:
                target_uid = dgraph_to_local.get(target_uid, target_uid)

            if target_uid in visited:
                continue

            target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
            if target_node:
                rel_type = rel['relation_type']
                category = rel.get('category', 'custom')

                display_type = f"{rel_type} [{'code' if category == 'parsed' else 'custom'}]"

                related.append({
                    'name': target_node.get('label', target_node.get('name', 'Unknown')),
                    'type': display_type,
                    'uid': target_uid,
                    'direction': 'out',
                    'category': category
                })
                visited.add(target_uid)

        # === 2. RELATIONS PARSÉES depuis le dict 'relations' ===
        parsed_relations = central_node.get('relations', {})
        for rel_type, rel_list in parsed_relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                if not target_name:
                    continue
                
                # Essayer de trouver le nœud cible
                normalized = normalize_node_name(target_name)
                target_node = None

                if normalized:
                    target_node = next(
                        (n for n in all_nodes 
                         if normalize_node_name(n.get('name', '')) == normalized or 
                            normalize_node_name(n.get('label', '')) == normalized),
                        None
                    )

                if target_node:
                    target_uid = target_node['uid']
                    if target_uid not in visited:
                        related.append({
                            'name': target_node.get('label', target_node.get('name', target_name)),
                            'type': f"{rel_type} [parsed]",
                            'uid': target_uid,
                            'direction': 'out',
                            'category': 'parsed',
                            'line': rel.get('line', 0)
                        })
                        visited.add(target_uid)
                else:
                    # Si non trouvé, ajouter quand même pour visualisation
                    related.append({
                        'name': target_name,
                        'type': f"{rel_type} [unresolved]",
                        'uid': f"unresolved_{target_name}",
                        'direction': 'out',
                        'category': 'parsed',
                        'line': rel.get('line', 0)
                    })

        # === 3. RELATIONS ENTRANTES ===
        for rel in central_node.get('incoming_relations', []):
            source_uid = rel.get('source_uid', rel.get('source_id', ''))

            if source_uid.startswith('0x') and len(source_uid) == 6:
                source_uid = dgraph_to_local.get(source_uid, source_uid)

            if source_uid in visited or source_uid.startswith('temp_'):
                continue

            source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
            if source_node:
                rel_type = rel.get('relation_type', 'relation')
                category = rel.get('category', 'custom')
                display_type = f"{rel_type} (in) [{'code' if category == 'parsed' else 'custom'}]"

                related.append({
                    'name': source_node.get('label', source_node.get('name', 'Unknown')),
                    'type': display_type,
                    'uid': source_uid,
                    'direction': 'in',
                    'category': category
                })
                visited.add(source_uid)

        # === 4. HIÉRARCHIE : ENFANTS ===
        for child in central_node.get('children', []):
            child_uid = child['uid']
            if child_uid in visited:
                continue

            related.append({
                'name': child.get('label', child.get('name', 'Child')),
                'type': 'child [hierarchy]',
                'uid': child_uid,
                'direction': 'out',
                'category': 'hierarchy'
            })
            visited.add(child_uid)

        # === 5. HIÉRARCHIE : PARENTS ===
        for parent_uid in central_node.get('parents', []):
            if parent_uid.startswith('0x') and len(parent_uid) == 6:
                parent_uid = dgraph_to_local.get(parent_uid, parent_uid)

            if parent_uid in visited:
                continue

            parent_info = self.parent_widget.label_uid_to_info.get(parent_uid)
            if parent_info:
                related.append({
                    'name': parent_info['name'],
                    'type': 'parent [hierarchy]',
                    'uid': parent_uid,
                    'direction': 'in',
                    'category': 'hierarchy'
                })
                visited.add(parent_uid)

        related = related[:max_nodes]
        logger.info(f"Collecté {len(related)} relations pour {central_node.get('label', central_uid)}")

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
        Dessine le graphe avec NetworkX - Version corrigée avec flèches pointant vers la source
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

            # CHANGEMENT CRITIQUE: Inverser le sens des arêtes
            if direction == 'in':
                # Relation entrante : central ← rel_uid devient rel_uid → central
                G.add_edge(rel_uid, central_uid, type=rel_type)
                edge_labels[(rel_uid, central_uid)] = rel_type[:6]
            else:
                # Relation sortante : central → rel_uid devient rel_uid → central
                # CHANGEMENT: Inverser pour que la flèche pointe vers central
                G.add_edge(rel_uid, central_uid, type=rel_type)
                edge_labels[(rel_uid, central_uid)] = rel_type[:6]

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
