import os
import pyperclip
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.Qsci import (
    QsciScintilla,
    QsciLexerPython,
    QsciLexerCPP,
    QsciLexerJavaScript,
    QsciLexerHTML,
)

import qtawesome as qta

from utils.logger import logger
from ui.localization.translator import tr
from ui.widgets.workers.simple_test_worker import SimpleTestWorker
from utils.dgraph_connector import LirisDgraphConnector


class TaxonomyItem(QtWidgets.QTreeWidgetItem):
    """Item pour l'arbre de taxonomie avec métadonnées"""
    def __init__(self, parent, text, item_type="folder", data=None, level=0):
        super().__init__(parent, [text])
        self.item_type = item_type
        self.item_data = data or {}
        self.level = level
        
        # Palette monochrome professionnelle (gris et rouge thème uniquement)
        primary = '#A23B2D'  # Rouge thème
        dark_gray = '#424242'
        medium_gray = '#666666'
        light_gray = '#999999'
        
        # Icônes professionnelles avec couleurs sobres
        if item_type == "folder":
            self.setIcon(0, qta.icon('fa5s.folder', color=dark_gray))
        elif item_type == "file":
            self.setIcon(0, qta.icon('fa5s.file-code', color=medium_gray))
        elif item_type == "function":
            self.setIcon(0, qta.icon('fa5s.cube', color=primary))
        elif item_type == "dependency":
            self.setIcon(0, qta.icon('fa5s.link', color=light_gray))
        elif item_type == "class":
            self.setIcon(0, qta.icon('fa5s.cubes', color=dark_gray))
        elif item_type == "variable":
            self.setIcon(0, qta.icon('fa5s.tag', color=light_gray))

class GraphPopup(QtWidgets.QDialog):
    """Popup pour afficher un mini graphe des relations avec meilleure représentation"""
    
    def __init__(self, central_node, related_items, parent=None):
        super().__init__(parent)
        self.central_node = central_node
        self.related_items = related_items
        self.setWindowTitle(f"Graphe des Relations - {central_node}")
        self.resize(1000, 700)
        self.setModal(True)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface de la popup"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # En-tête avec informations
        header_layout = QtWidgets.QHBoxLayout()
        
        title = QtWidgets.QLabel(f"Nœud central: {self.central_node}")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #A23B2D;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Statistiques
        stats_label = QtWidgets.QLabel(
            f"Relations: {len(self.related_items)} | "
            f"Types: {len(set(r['type'] for r in self.related_items))}"
        )
        stats_label.setStyleSheet("font-size: 12px; color: #666;")
        header_layout.addWidget(stats_label)
        
        layout.addLayout(header_layout)
        
        # Séparateur
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        
        # Canvas pour le graphe
        self.figure = Figure(figsize=(10, 7), facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Légende des types de relations
        legend_layout = QtWidgets.QHBoxLayout()
        legend_label = QtWidgets.QLabel("Légende:")
        legend_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        legend_layout.addWidget(legend_label)
        
        # Grouper les types de relations
        relation_types = {}
        for rel in self.related_items:
            rel_type = rel['type']
            relation_types[rel_type] = relation_types.get(rel_type, 0) + 1
        
        for rel_type, count in sorted(relation_types.items()):
            color = self._get_color_for_type(rel_type)
            type_label = QtWidgets.QLabel(f"● {rel_type} ({count})")
            type_label.setStyleSheet(f"color: {color}; font-size: 10px; padding: 0 8px;")
            legend_layout.addWidget(type_label)
        
        legend_layout.addStretch()
        layout.addLayout(legend_layout)
        
        # Boutons d'action
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        
        # Bouton pour exporter
        export_button = QtWidgets.QPushButton("Exporter PNG")
        export_button.clicked.connect(self._export_graph)
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #888;
            }
        """)
        buttons_layout.addWidget(export_button)
        
        # Bouton fermer
        close_button = QtWidgets.QPushButton("Fermer")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35A4A;
            }
        """)
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        
        # Dessiner le graphe
        self._draw_graph()
    
    def _get_color_for_type(self, rel_type):
        """Retourne une couleur selon le type de relation"""
        color_map = {
            'fonction': '#4CAF50',
            'appel': '#2196F3',
            'appel direct': '#2196F3',
            'import': '#FF9800',
            'relation': '#9C27B0',
            'relation_out': '#E91E63',
            'relation_in': '#3F51B5',
            'enfant': '#00BCD4',
            'enfant hiérarchique': '#009688',
            'fichier': '#795548',
            'appelant': '#FFC107',
            'appelant (inverse)': '#FFC107',
            'relation inverse': '#673AB7',
            'reverse_import': '#FF5722',
        }
        
        # Chercher une correspondance partielle
        rel_lower = rel_type.lower()
        for key, color in color_map.items():
            if key in rel_lower:
                return color
        
        return '#607D8B'  # Couleur par défaut
    
    def _draw_graph(self):
        """Dessine le graphe avec NetworkX et Matplotlib"""
        G = nx.DiGraph()  # Graphe dirigé pour montrer les directions
        
        # Nœud central
        G.add_node(self.central_node, node_type='central')
        
        # Grouper les relations par type
        relation_groups = {}
        for rel in self.related_items:
            rel_type = rel['type']
            if rel_type not in relation_groups:
                relation_groups[rel_type] = []
            relation_groups[rel_type].append(rel)
        
        # Ajouter nœuds liés et arêtes avec couleurs
        edge_labels = {}
        
        for rel_type, relations in relation_groups.items():
            color = self._get_color_for_type(rel_type)
            
            for rel in relations:
                rel_name = rel['name']
                
                # Éviter les doublons de nœuds
                if not G.has_node(rel_name):
                    G.add_node(rel_name, node_type='related')
                
                # Ajouter l'arête avec le type comme label
                if not G.has_edge(self.central_node, rel_name):
                    G.add_edge(self.central_node, rel_name, label=rel_type, color=color)
                    edge_labels[(self.central_node, rel_name)] = rel_type
        
        # Choisir le layout selon le nombre de nœuds
        num_nodes = len(G.nodes())
        
        if num_nodes <= 10:
            pos = nx.spring_layout(G, k=3, iterations=100, seed=42)  # Augmenté pour meilleure séparation
        elif num_nodes <= 30:
            pos = nx.kamada_kawai_layout(G)
        else:
            # Pour les grands graphes, utiliser un layout circulaire
            pos = nx.circular_layout(G)
            # Le nœud central au centre
            pos[self.central_node] = (0, 0)
        
        # Préparer les couleurs et tailles des nœuds (ajustées pour moins de chevauchement)
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if G.nodes[node]['node_type'] == 'central':
                node_colors.append('#A23B2D')  # Rouge pour central
                node_sizes.append(1000)  # Taille réduite
            else:
                node_colors.append('#4CAF50')  # Vert pour relations
                node_sizes.append(500)  # Taille réduite
        
        # Dessiner
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')
        
        # Dessiner les arêtes en une seule fois pour meilleure performance et apparence
        if G.edges():
            edges_list = [(u, v) for u, v, d in G.edges(data=True)]
            edge_colors_list = [d.get('color', '#999') for u, v, d in G.edges(data=True)]
            
            nx.draw_networkx_edges(
                G, pos, 
                edgelist=edges_list,
                edge_color=edge_colors_list,
                ax=ax,
                width=1.5 if num_nodes > 20 else 2.5,
                alpha=0.7,
                arrows=True,
                arrowsize=15 if num_nodes > 20 else 20,
                arrowstyle='->',
                connectionstyle='arc3,rad=0.05'  # Courbure réduite pour moins d'encombrement
            )
        
        # Dessiner les nœuds
        nx.draw_networkx_nodes(
            G, pos, 
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.85,
            linewidths=1.5,
            edgecolors='white'
        )
        
        # Labels des nœuds avec meilleure lisibilité
        labels = {}
        for node in G.nodes():
            # Tronquer les noms trop longs
            label = node if len(node) <= 15 else node[:12] + "..."
            labels[node] = label
        
        label_opts = {
            'ax': ax,
            'font_size': 8 if num_nodes > 20 else 10,
            'font_weight': 'bold',
        }
        
        if num_nodes <= 30:
            label_opts.update({
                'font_color': 'white',
                'bbox': dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7, edgecolor='none')
            })
        else:
            label_opts['font_color'] = 'black'
            label_opts['bbox'] = None
        
        nx.draw_networkx_labels(G, pos, labels, **label_opts)
        
        # Ajouter labels sur arêtes pour petits graphes
        if num_nodes <= 15:
            nx.draw_networkx_edge_labels(
                G, pos, 
                edge_labels,
                ax=ax,
                font_size=6,
                font_color='#333',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.9)
            )
        
        # Titre et style
        ax.set_title(
            f"Réseau de relations\nNœud central: {self.central_node}\n"
            f"({num_nodes} nœuds, {len(G.edges())} relations)",
            fontsize=12,
            fontweight='bold',
            pad=20
        )
        
        ax.axis('off')
        ax.margins(0.1)  # Marges réduites pour mieux utiliser l'espace
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _export_graph(self):
        """Exporte le graphe en PNG"""
        try:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Exporter le graphe",
                f"graph_{self.central_node}.png",
                "PNG Files (*.png);;All Files (*)"
            )
            
            if file_path:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight', facecolor='white')
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
        self.level_combo.addItem("Niveau 3: Niveau 2 + enfants des enfants", 3)
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
        
        # Bouton pour afficher le graphe
        graph_button = QtWidgets.QPushButton("Afficher le Graphe des Relations")
        graph_button.clicked.connect(self._show_graph)
        graph_button.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35A4A;
            }
            QPushButton:disabled {
                background-color: #CCC;
            }
        """)
        graph_button.setEnabled(False)
        self.graph_button = graph_button
        desc_layout.addWidget(graph_button)
        
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
    
    def _show_graph(self):
        """Affiche la popup du graphe"""
        if not hasattr(self, 'current_central_node') or not self.current_related_items:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune relation disponible pour le graphe.")
            return
        
        if len(self.current_related_items) == 0:
            # Diagnostic: vérifier si le nœud existe vraiment dans Dgraph
            selected_items = self.tree_widget.selectedItems()
            if selected_items:
                last_item = selected_items[-1]
                if isinstance(last_item, TaxonomyItem):
                    data = last_item.item_data
                    node_uid = data.get('uid') or data.get('id')
                    
                    if node_uid and self.dgraph_connector.client:
                        # Requête de diagnostic
                        diagnostic_query = f"""
                        {{
                          node(func: uid({node_uid})) {{
                            uid
                            name
                            dgraph.type
                            expand(_all_) {{
                              uid
                              name
                            }}
                          }}
                          
                          all_relations(func: type(Relation)) @filter(uid_in(source, {node_uid}) OR uid_in(target, {node_uid})) {{
                            uid
                            name
                            relationType
                            source {{ uid name }}
                            target {{ uid name }}
                          }}
                        }}
                        """
                        
                        try:
                            diag_result = self.dgraph_connector.query(diagnostic_query)
                            
                            # Afficher les informations de diagnostic
                            diag_msg = f"Diagnostic pour le nœud '{self.current_central_node}':\n\n"
                            
                            if diag_result and diag_result.get('node'):
                                node_info = diag_result['node'][0] if diag_result['node'] else {}
                                diag_msg += f"UID: {node_info.get('uid', 'N/A')}\n"
                                diag_msg += f"Type: {node_info.get('dgraph.type', 'N/A')}\n"
                                diag_msg += f"Attributs trouvés: {len(node_info.keys())}\n\n"
                            
                            relations = diag_result.get('all_relations', []) if diag_result else []
                            diag_msg += f"Relations trouvées dans Dgraph: {len(relations)}\n"
                            
                            if relations:
                                diag_msg += "\nPremières relations:\n"
                                for rel in relations[:5]:
                                    src = rel.get('source', {}).get('name', 'unknown')
                                    tgt = rel.get('target', {}).get('name', 'unknown')
                                    rel_type = rel.get('relationType', 'unknown')
                                    diag_msg += f"  - {src} --[{rel_type}]--> {tgt}\n"
                            
                            QtWidgets.QMessageBox.information(
                                self, 
                                "Diagnostic", 
                                diag_msg
                            )
                            
                        except Exception as e:
                            logger.error(f"Erreur diagnostic: {e}")
                            QtWidgets.QMessageBox.information(
                                self, 
                                "Information", 
                                f"Le nœud '{self.current_central_node}' n'a aucune relation à afficher.\n\n"
                                f"Erreur diagnostic: {str(e)}"
                            )
                    else:
                        QtWidgets.QMessageBox.information(
                            self, 
                            "Information", 
                            f"Le nœud '{self.current_central_node}' n'a aucune relation à afficher."
                        )
            return
        
        popup = GraphPopup(self.current_central_node, self.current_related_items, self)
        popup.exec_()
    
    def _execute_dgraph_query(self, query):
        """
        Exécute une requête Dgraph en utilisant la méthode standard du connecteur
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph connector ou client non disponible")
            return None

        try:
            # Le LirisDgraphConnector utilise toujours txn.query() + _parse_response()
            txn = self.dgraph_connector.client.txn(read_only=True)
            try:
                resp = txn.query(query)
                result = self.dgraph_connector._parse_response(resp)
                logger.debug(f"Requête exécutée avec succès, résultat: {list(result.keys()) if result else 'None'}")
                return result
            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la requête Dgraph: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _query_dgraph_relations(self, start_uid, max_depth):
        """Exécute des requêtes Dgraph itératives pour récupérer les relations jusqu'à la profondeur donnée"""
        if not self.dgraph_connector.client:
            logger.warning("Dgraph non connecté pour les relations")
            return []

        all_related = []
        current_layer_uids = [start_uid]
        visited = set([str(start_uid)])

        for depth in range(1, max_depth + 1):
            if not current_layer_uids:
                break
            
            # Nettoyer les UIDs - s'assurer qu'ils sont au format 0xABC
            clean_uids = []
            for uid in current_layer_uids:
                uid_str = str(uid).strip()
                if not uid_str.startswith('0x'):
                    uid_str = '0x' + uid_str
                clean_uids.append(uid_str)

            # Construire la requête pour chaque UID
            # On récupère : relations sortantes, relations entrantes (~relations), 
            # calls sortants, appelants (~calls), imports, parents, children
            uids_list = ', '.join(clean_uids)

            query = f"""
            {{
              nodes(func: uid({uids_list})) {{
                uid
                name
                id
                dgraph.type

                # Relations sortantes directes
                relations {{
                  uid
                  name
                  id
                  relationType
                  dgraph.type
                }}

                # Relations entrantes (reverse edge)
                ~relations {{
                  uid
                  name
                  id
                  relationType
                  dgraph.type
                }}

                # Appels de fonctions
                calls {{
                  uid
                  name
                  id
                  dgraph.type
                }}

                # Appelants (reverse)
                ~calls {{
                  uid
                  name
                  id
                  dgraph.type
                }}

                # Imports
                imports {{
                  uid
                  name
                  id
                  dgraph.type
                }}

                # Fonctions définies
                functions {{
                  uid
                  name
                  description
                  calls {{
                    uid
                    name
                  }}
                }}

                # Parents hiérarchiques
                parents {{
                  uid
                  name
                  id
                  dgraph.type
                }}

                # Enfants hiérarchiques (reverse)
                ~parents {{
                  uid
                  name
                  id
                  dgraph.type
                }}

                # Appartenance à des clusters (reverse)
                ~clusters {{
                  uid
                  name
                  id
                  dgraph.type
                }}
              }}
            }}
            """

            logger.debug(f"=== Profondeur {depth} ===")
            logger.debug(f"UIDs recherchés: {clean_uids}")
            logger.debug(f"Requête Dgraph:\n{query}")

            try:
                result = self._execute_dgraph_query(query)

                if not result:
                    logger.warning(f"Profondeur {depth}: Aucun résultat de la requête")
                    break
                
                layer_related = []
                next_layer = set()

                if result and 'nodes' in result:
                    nodes = result['nodes']
                    logger.info(f"Profondeur {depth}: {len(nodes)} nœuds récupérés")

                    for node in nodes:
                        node_uid = node.get('uid', '').strip()
                        if node_uid and not node_uid.startswith('0x'):
                            node_uid = '0x' + node_uid

                        # 1. Relations sortantes
                        for rel in node.get('relations', []):
                            rel_uid = rel.get('uid', '').strip()
                            if rel_uid and not rel_uid.startswith('0x'):
                                rel_uid = '0x' + rel_uid

                            if rel_uid and rel_uid not in visited:
                                rel_name = rel.get('name') or rel.get('id') or 'relation'
                                rel_type = rel.get('relationType', 'relation')
                                layer_related.append({
                                    'name': rel_name,
                                    'type': rel_type,
                                    'data': rel
                                })
                                next_layer.add(rel_uid)
                                visited.add(rel_uid)
                                logger.debug(f"  → Relation sortante: {rel_name} ({rel_type})")

                        # 2. Relations entrantes (~relations)
                        for rel in node.get('~relations', []):
                            rel_uid = rel.get('uid', '').strip()
                            if rel_uid and not rel_uid.startswith('0x'):
                                rel_uid = '0x' + rel_uid

                            if rel_uid and rel_uid not in visited:
                                rel_name = rel.get('name') or rel.get('id') or 'relation'
                                rel_type = rel.get('relationType', 'relation')
                                layer_related.append({
                                    'name': rel_name,
                                    'type': f'{rel_type} (inverse)',
                                    'data': rel
                                })
                                next_layer.add(rel_uid)
                                visited.add(rel_uid)
                                logger.debug(f"  → Relation entrante: {rel_name} ({rel_type} inverse)")

                        # 3. Appels de fonctions
                        for call in node.get('calls', []):
                            call_uid = call.get('uid', '').strip()
                            if call_uid and not call_uid.startswith('0x'):
                                call_uid = '0x' + call_uid

                            if call_uid and call_uid not in visited:
                                call_name = call.get('name') or call.get('id') or 'call'
                                layer_related.append({
                                    'name': call_name,
                                    'type': 'appel',
                                    'data': call
                                })
                                next_layer.add(call_uid)
                                visited.add(call_uid)
                                logger.debug(f"  → Appel: {call_name}")

                        # 4. Appelants (~calls)
                        for caller in node.get('~calls', []):
                            caller_uid = caller.get('uid', '').strip()
                            if caller_uid and not caller_uid.startswith('0x'):
                                caller_uid = '0x' + caller_uid

                            if caller_uid and caller_uid not in visited:
                                caller_name = caller.get('name') or caller.get('id') or 'caller'
                                layer_related.append({
                                    'name': caller_name,
                                    'type': 'appelant',
                                    'data': caller
                                })
                                next_layer.add(caller_uid)
                                visited.add(caller_uid)
                                logger.debug(f"  → Appelant: {caller_name}")

                        # 5. Imports
                        for imp in node.get('imports', []):
                            imp_uid = imp.get('uid', '').strip()
                            if imp_uid and not imp_uid.startswith('0x'):
                                imp_uid = '0x' + imp_uid

                            if imp_uid and imp_uid not in visited:
                                imp_name = imp.get('name') or imp.get('id') or 'import'
                                layer_related.append({
                                    'name': imp_name,
                                    'type': 'import',
                                    'data': imp
                                })
                                next_layer.add(imp_uid)
                                visited.add(imp_uid)
                                logger.debug(f"  → Import: {imp_name}")

                        # 6. Fonctions définies dans ce nœud
                        for func in node.get('functions', []):
                            func_uid = func.get('uid', '').strip()
                            if func_uid and not func_uid.startswith('0x'):
                                func_uid = '0x' + func_uid

                            if func_uid and func_uid not in visited:
                                func_name = func.get('name') or 'function'
                                layer_related.append({
                                    'name': func_name,
                                    'type': 'fonction',
                                    'data': func
                                })
                                next_layer.add(func_uid)
                                visited.add(func_uid)
                                logger.debug(f"  → Fonction: {func_name}")

                                # Appels de cette fonction
                                for call in func.get('calls', []):
                                    call_uid = call.get('uid', '').strip()
                                    if call_uid and not call_uid.startswith('0x'):
                                        call_uid = '0x' + call_uid

                                    if call_uid and call_uid not in visited:
                                        call_name = call.get('name') or 'call'
                                        layer_related.append({
                                            'name': call_name,
                                            'type': 'appel de fonction',
                                            'data': call
                                        })
                                        next_layer.add(call_uid)
                                        visited.add(call_uid)

                        # 7. Parents hiérarchiques
                        for parent in node.get('parents', []):
                            parent_uid = parent.get('uid', '').strip()
                            if parent_uid and not parent_uid.startswith('0x'):
                                parent_uid = '0x' + parent_uid

                            if parent_uid and parent_uid not in visited:
                                parent_name = parent.get('name') or parent.get('id') or 'parent'
                                layer_related.append({
                                    'name': parent_name,
                                    'type': 'parent',
                                    'data': parent
                                })
                                next_layer.add(parent_uid)
                                visited.add(parent_uid)
                                logger.debug(f"  → Parent: {parent_name}")

                        # 8. Enfants hiérarchiques (~parents)
                        for child in node.get('~parents', []):
                            child_uid = child.get('uid', '').strip()
                            if child_uid and not child_uid.startswith('0x'):
                                child_uid = '0x' + child_uid

                            if child_uid and child_uid not in visited:
                                child_name = child.get('name') or child.get('id') or 'child'
                                layer_related.append({
                                    'name': child_name,
                                    'type': 'enfant',
                                    'data': child
                                })
                                next_layer.add(child_uid)
                                visited.add(child_uid)
                                logger.debug(f"  → Enfant: {child_name}")

                        # 9. Clusters parents (~clusters)
                        for cluster in node.get('~clusters', []):
                            cluster_uid = cluster.get('uid', '').strip()
                            if cluster_uid and not cluster_uid.startswith('0x'):
                                cluster_uid = '0x' + cluster_uid

                            if cluster_uid and cluster_uid not in visited:
                                cluster_name = cluster.get('name') or cluster.get('id') or 'cluster'
                                layer_related.append({
                                    'name': cluster_name,
                                    'type': 'cluster parent',
                                    'data': cluster
                                })
                                next_layer.add(cluster_uid)
                                visited.add(cluster_uid)
                                logger.debug(f"  → Cluster parent: {cluster_name}")

                    logger.info(f"Profondeur {depth}: {len(layer_related)} nouveaux éléments, {len(next_layer)} pour couche suivante")
                else:
                    logger.warning(f"Profondeur {depth}: Aucune relation trouvée dans le résultat")

                all_related.extend(layer_related)
                current_layer_uids = list(next_layer)

            except Exception as e:
                logger.error(f"Erreur requête Dgraph à profondeur {depth}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break
            
        logger.info(f"=== TOTAL: {len(all_related)} relations récupérées pour UID {start_uid} (profondeur max: {max_depth}) ===")

        return all_related
    
    def _load_taxonomy(self):
        """Charge la taxonomie du projet avec relations"""
        self.tree_widget.clear()
        
        if not self.project_data:
            return
        
        # Parcourir les clusters
        cm = self.project_data.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_name = f"Cluster: {cluster.get('name', 'Cluster')}"
            # Détecter le type pour le cluster : si pas d'extension, folder
            cluster_type = "folder" if not self._has_extension(cluster.get('name', '')) else "file"
            cluster_item = TaxonomyItem(
                self.tree_widget,
                cluster_name,
                cluster_type,
                cluster,
                0
            )
            
            # Ajouter les root_labels avec leurs relations
            self._add_labels_with_relations(cluster_item, cluster.get('root_labels', []))
        
        self.tree_widget.expandAll()
    
    def _add_labels_with_relations(self, parent_item, labels):
        """Ajoute les labels avec leurs relations et icônes appropriées"""
        for label in labels:
            label_name = label.get('name', label.get('label', 'Item'))

            # Déterminer le type et l'icône avec la nouvelle logique
            item_type = self._detect_item_type(label, label_name, parent_item)

            label_item = TaxonomyItem(
                parent_item,
                label_name,
                item_type,
                label,
                0
            )

            # Ajouter les fonctions du fichier/label avec détection de type
            functions = label.get('functions', [])
            for func in functions:
                func_name = func.get('name', 'function')
                func_type = self._detect_function_type(func, func_name)
                func_item = TaxonomyItem(
                    label_item,
                    func_name,
                    func_type,
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
        elif selected_level == 2:
            logger.info("Niveau 2 sélectionné : Toutes relations + enfants (récursif)")
        else:
            logger.info("Niveau 3 sélectionné : Niveau 2 + enfants des enfants")
        
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
            self.graph_button.setEnabled(False)
            return
        
        # Afficher la description du dernier item sélectionné
        last_item = selected_items[-1]
        if isinstance(last_item, TaxonomyItem):
            data = last_item.item_data
            selected_level = self.level_combo.currentData()
            
            # Charger les relations selon le niveau
            related_items = self._get_related_items(data, selected_level)
            
            # Stocker pour le graphe
            self.current_central_node = data.get('name', data.get('label', 'N/A'))
            self.current_related_items = related_items if selected_level >= 2 else []
            self.graph_button.setEnabled(selected_level >= 2 and len(related_items) > 0)
            
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
                
                # Log pour tracer
                if selected_level >= 2:
                    logger.info(f"Niveau {selected_level} - Récupéré {len(related_items)} relations pour '{data.get('name', 'N/A')}'")
            
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
        Niveau 3: Niveau 2 + enfants des enfants (profondeur supplémentaire)
        """
        related = []
        
        if level == 1:
            # Niveau 1: Relations DIRECTES uniquement
            self._collect_direct_relations(data, related)
        
        elif level == 2 or level == 3:
    # Nouvelle logique : Requête Dgraph dynamique + fallback local
            file_uid = data.get('uid') or data.get('id')
            
            if not file_uid:
                logger.warning(f"Pas d'UID trouvé pour '{data.get('name', 'unknown')}', fallback local uniquement")
                visited = set()
                self._collect_all_relations_recursive(data, related, visited, depth=1, max_depth=(level - 1))
                return related
            
            # Nettoyer l'UID
            file_uid = str(file_uid).strip()
            if not file_uid.startswith('0x'):
                file_uid = '0x' + file_uid
            
            logger.info(f"Recherche relations Dgraph pour UID: {file_uid} (niveau {level})")
            
            max_depth = 1 if level == 2 else 2
            dgraph_related = self._query_dgraph_relations(file_uid, max_depth)
            
            # Fusionner avec local (pour fonctions/appels non couverts par relations)
            visited = set([str(file_uid)])
            self._collect_all_relations_recursive(data, related, visited, depth=1, max_depth=max_depth)
            
            # Ajouter les résultats Dgraph (priorité aux fichiers liés, éviter doublons)
            for item in dgraph_related:
                item_uid = item['data'].get('uid')
                if item_uid and str(item_uid) not in visited:
                    related.append(item)
                    visited.add(str(item_uid))
            
            # Trier par type pour lisibilité
            related.sort(key=lambda x: x['type'])
        
        return related
    
    def _collect_direct_relations(self, data, related):
        """Collecte les relations directes uniquement (Niveau 1)"""
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
        
        # 2. Relations directes
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
    
    def _collect_all_relations_recursive(self, data, collected, visited, depth=1, max_depth=1):
        """
        Collecte récursivement TOUS les éléments liés avec contrôle de profondeur
        depth: profondeur actuelle
        max_depth: profondeur maximale (1 pour niveau 2, 2 pour niveau 3)
        """
        # Identifier l'élément pour éviter les boucles infinies
        item_id = data.get('id', data.get('uid', str(data)))
        
        if item_id in visited:
            return
        visited.add(item_id)
        
        # Si on a dépassé la profondeur max, ne pas continuer la récursion
        if depth > max_depth:
            return
        
        # 1. Fonctions et leurs appels
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
                        self._collect_all_relations_recursive(call, collected, visited, depth + 1, max_depth)
        
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
                self._collect_all_relations_recursive(imp, collected, visited, depth + 1, max_depth)
        
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
                self._collect_all_relations_recursive(rel, collected, visited, depth + 1, max_depth)
        
        # 4. Enfants dans la hiérarchie
        parents = data.get('parents', [])
        for parent in parents:
            parent_id = parent.get('id', parent.get('uid', str(parent)))
            if parent_id not in visited:
                collected.append({
                    'name': parent.get('name', 'parent'),
                    'type': 'enfant hiérarchique',
                    'data': parent
                })
                self._collect_all_relations_recursive(parent, collected, visited, depth + 1, max_depth)
        
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
                self._collect_all_relations_recursive(child, collected, visited, depth + 1, max_depth)
        
        # 6. Fichiers liés
        files = data.get('files', [])
        for file_path in files:
            if isinstance(file_path, str):
                collected.append({
                    'name': file_path,
                    'type': 'fichier',
                    'data': {'path': file_path}
                })
        
        # 7. Reverse relations
        reverse_calls = data.get('~calls', [])
        for rcall in reverse_calls:
            rcall_id = rcall.get('id', rcall.get('uid', str(rcall)))
            if rcall_id not in visited:
                collected.append({
                    'name': rcall.get('name', 'caller'),
                    'type': 'appelant (inverse)',
                    'data': rcall
                })
                self._collect_all_relations_recursive(rcall, collected, visited, depth + 1, max_depth)
        
        reverse_relations = data.get('~relations', [])
        for rrel in reverse_relations:
            rrel_id = rrel.get('id', rrel.get('uid', str(rrel)))
            if rrel_id not in visited:
                collected.append({
                    'name': rrel.get('name', 'related_from'),
                    'type': 'relation inverse',
                    'data': rrel
                })
                self._collect_all_relations_recursive(rrel, collected, visited, depth + 1, max_depth)
    
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
                
                logger.info(f"Taxonomie sélectionnée - Niveau {selected_level}: {len(related_items)} relations pour '{data.get('name', 'N/A')}'")
        
        return taxonomy_data

    def _detect_item_type(self, item_data, item_name, parent_item):
        """
        Détecte intelligemment le type d'item (folder, file, class, function, variable)

        Règles prioritaires :
        - Si a une extension : "file" (code)
        - Si parent est "folder" et pas d'extension : "folder"
        - Si parent est "file" : détecter class, function ou variable
        - Default : "folder"

        Args:
            item_data: Dictionnaire contenant les données de l'item
            item_name: Nom de l'item
            parent_item: Item parent dans l'arbre

        Returns:
            str: Type détecté ('folder', 'file', 'class', 'function', 'variable')
        """
        # Règle 1: Si a extension → file (code)
        if self._has_extension(item_name):
            return "file"

        # Règle 2: Si parent est folder et pas d'extension → folder
        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "folder":
            return "folder"

        # Règle 3: Si parent est file → détecter class, function ou variable
        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "file":
            # Utiliser les détections existantes pour class, function, variable
            if item_data.get('type') == 'class' or self._is_class_name(item_name):
                return "class"
            if self._is_function_name(item_name):
                return "function"
            if self._is_variable_name(item_name):
                return "variable"
            # Default pour enfant de file non détecté : function
            return "function"

        # Default : folder (pour parents ou racine sans extension)
        return "folder"

    def _detect_function_type(self, func_data, func_name):
        """
        Détecte le type d'une fonction (function ou variable pour enfants de file)

        Args:
            func_data: Dictionnaire contenant les données de la fonction
            func_name: Nom de la fonction

        Returns:
            str: Type détecté ('function' ou 'variable')
        """
        # Vérifier si c'est une variable déguisée en fonction
        if self._is_variable_name(func_name):
            return "variable"

        # Vérifier le type explicite dans les métadonnées
        if func_data.get('type') == 'variable':
            return "variable"

        return "function"

    def _is_class_name(self, name):
        """
        Détecte si un nom correspond à une classe

        Critères de détection:
        - Commence par public, private, protected, abstract, static, final
        - Commence par 'class '
        - Format PascalCase (première lettre majuscule)

        Args:
            name: Nom à analyser

        Returns:
            bool: True si c'est une classe
        """
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Modificateurs d'accès et mots-clés de classe
        class_keywords = [
            'public class', 'private class', 'protected class',
            'abstract class', 'static class', 'final class',
            'sealed class', 'internal class',
            'public ', 'private ', 'protected ', 'abstract ',
            'class ', 'interface ', 'trait ', 'struct '
        ]

        for keyword in class_keywords:
            if name_lower.startswith(keyword):
                return True

        # PascalCase: première lettre majuscule et pas de parenthèses
        # Exclure les noms avec des caractères spéciaux qui indiquent autre chose
        if (name_stripped and 
            name_stripped[0].isupper() and 
            '(' not in name_stripped and 
            '=' not in name_stripped and
            ':' not in name_stripped.split()[0] if ' ' in name_stripped else ':' not in name_stripped and
            '.' not in name_stripped.split()[0] if ' ' in name_stripped else True):

            # Vérifier que ce n'est pas juste un mot en majuscule (constante)
            if not name_stripped.isupper():
                return True

        return False

    def _is_function_name(self, name):
        """
        Détecte si un nom correspond à une fonction

        Critères de détection:
        - Commence par 'def ' ou 'function '
        - Contient des parenthèses () (signature de fonction)
        - Format camelCase ou snake_case

        Args:
            name: Nom à analyser

        Returns:
            bool: True si c'est une fonction
        """
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Mots-clés de fonction
        function_keywords = ['def ', 'function ', 'fn ', 'func ', 'async def ', 'async function ']
        for keyword in function_keywords:
            if name_lower.startswith(keyword):
                return True

        # Contient des parenthèses (signature de fonction)
        if '(' in name_stripped and ')' in name_stripped:
            # Vérifier que ce n'est pas juste une expression mathématique
            if not self._is_variable_declaration(name_stripped):
                return True

        # camelCase ou snake_case sans majuscule initiale
        if name_stripped and name_stripped[0].islower():
            # Vérifier que ce n'est pas une variable
            if not self._is_variable_declaration(name_stripped):
                # Si pas de caractères spéciaux de variable, probablement une fonction
                if '=' not in name_stripped.split('(')[0] and ':' not in name_stripped.split('(')[0]:
                    return True

        return False

    def _is_variable_name(self, name):
        """
        Détecte si un nom correspond à une variable

        Critères de détection:
        - Contient un type explicite (: type)
        - Commence par var, let, const, val, final
        - Contient une affectation =

        Args:
            name: Nom à analyser

        Returns:
            bool: True si c'est une variable
        """
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Mots-clés de déclaration de variable
        variable_keywords = [
            'var ', 'let ', 'const ', 'val ', 'final ',
            'static ', 'public static ', 'private static ',
            'protected static ', 'readonly '
        ]

        for keyword in variable_keywords:
            if name_lower.startswith(keyword):
                # Vérifier que ce n'est pas une fonction statique
                if '(' not in name_stripped or '=' in name_stripped:
                    return True

        # Contient un typage explicite
        if self._is_variable_declaration(name_stripped):
            return True

        # Variables constantes (tout en majuscules avec underscores)
        if name_stripped.isupper() and '_' in name_stripped:
            return True

        return False

    def _is_variable_declaration(self, name):
        """
        Détecte une déclaration de variable typée

        Formats détectés:
        - name: type
        - name = value
        - name: type = value

        Args:
            name: Nom à analyser

        Returns:
            bool: True si c'est une déclaration de variable
        """
        if not name:
            return False

        name_stripped = name.strip()

        # Format: name: type (mais pas pour les fonctions avec paramètres)
        if ':' in name_stripped and '(' not in name_stripped.split(':')[0]:
            # Vérifier que ce n'est pas une URL ou un namespace avec plusieurs ':'
            parts = name_stripped.split(':')
            if len(parts) >= 2:
                # Le deuxième élément doit ressembler à un type
                type_part = parts[1].strip().split('=')[0].strip()

                if type_part:
                    # Types primitifs courants
                    primitive_types = [
                        'int', 'str', 'float', 'bool', 'double', 'long',
                        'string', 'boolean', 'number', 'any', 'void',
                        'list', 'dict', 'tuple', 'set', 'array', 'object',
                        'List', 'Dict', 'Tuple', 'Set', 'Array', 'Object'
                    ]

                    # Vérifier si c'est un type connu ou commence par une majuscule
                    type_name = type_part.split('[')[0].split('<')[0].strip()
                    if type_name in primitive_types or (type_name and type_name[0].isupper()):
                        return True

        # Affectation simple (mais pas def ou function)
        if '=' in name_stripped:
            before_equal = name_stripped.split('=')[0].strip().lower()
            # Exclure les définitions de fonctions
            if 'def' not in before_equal and 'function' not in before_equal and 'fn' not in before_equal:
                # Exclure les comparaisons (==, !=, <=, >=)
                if not name_stripped.replace('=', '').strip().endswith('='):
                    return True

        return False

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
        """Style global : flèche SVG, pas de bordure grenat, scrollbar cachée dans les listes."""
        # Petite flèche SVG (chevron) encodée en base64 pour fiabilité cross-platform
        svg_b64 = "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScxMicgaGVpZ2h0PSc3JyB2aWV3Qm94PScwIDAgMTIgNyc+PHBhdGggZD0nTTEgMSBMNiA2IEwxMSAxJyBzdHJva2U9JyUyMzU1NScgc3Ryb2tlLXdpZHRoPScxLjYnIGZpbGw9J25vbmUnIHN0cm9rZS1saW5lY2FwPSdyb3VuZCcgLz48L3N2Zz4="

        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QGroupBox {{
            border: 1px solid #D0D0D0;
            border-radius: 8px;
            margin-top: 1.2em;
            padding: 15px;
            background-color: #FFFFFF;
            font-weight: bold;
            font-size: 14px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px;
            color: #333333;
        }}

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {self.secondary_color}; }}
        QPushButton:disabled {{ background-color: #CCCCCC; color: #888888; }}

        /* Champs sobres avec effet subtil au focus */
        QLineEdit, QComboBox, QTextEdit {{
            padding: 8px 12px;
            border: 2px solid #E0E0E0;
            border-radius: 6px;
            background-color: #FFFFFF;
            font-size: 13px;
        }}
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
            border: 2px solid {self.primary_color};
            background-color: #FFFBFA;
            outline: none;
        }}
        QLineEdit:hover, QComboBox:hover, QTextEdit:hover {{
            border: 2px solid #C0C0C0;
        }}

        /* Style de la ComboBox fermée - plus haute et espacée */
        QComboBox {{
            min-height: 38px;
            padding-left: 12px;
            padding-right: 35px;
        }}

        /* Menu déroulant (la liste) : design moderne et attractif */
        QComboBox QAbstractItemView {{
            border: 2px solid #E0E0E0;
            border-radius: 8px;
            background-color: #FFFFFF;
            selection-background-color: {self.primary_color};
            selection-color: white;
            outline: none;
            padding: 4px;
        }}
        
        /* Items de la liste avec espacement et effet hover */
        QComboBox QAbstractItemView::item {{
            min-height: 36px;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 2px 4px;
        }}
        
        QComboBox QAbstractItemView::item:hover {{
            background-color: #FFF3F0;
            color: {self.primary_color};
        }}
        
        QComboBox QAbstractItemView::item:selected {{
            background-color: {self.primary_color};
            color: white;
        }}
        
        /* Premier item (placeholder) en italique et grisé */
        QComboBox QAbstractItemView::item:first {{
            font-style: italic;
            color: #999999;
        }}

        /* Cache la scrollbar verticale dans le pop-up du combo */
        QComboBox QAbstractItemView QScrollBar:vertical {{
            background: transparent;
            width: 0px;
            margin: 0px;
        }}
        QComboBox QAbstractItemView QScrollBar::handle:vertical {{
            background: transparent;
        }}

        /* Drop-down area (zone du bouton) avec léger effet visuel */
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 32px;
            border: none;
            border-left: 1px solid #E0E0E0;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
        }}
        
        QComboBox:hover::drop-down {{
            background: linear-gradient(to bottom, #F5F5F5, #F0F0F0);
        }}

        /* Flèche stable avec transition */
        QComboBox::down-arrow {{
            image: url("data:image/svg+xml;base64,{svg_b64}");
            width: 12px;
            height: 7px;
        }}
        QComboBox:hover::down-arrow {{
            image: url("data:image/svg+xml;base64,{svg_b64}");
        }}
        
        /* Animation d'ouverture */
        QComboBox:on {{
            border: 2px solid {self.primary_color};
        }}

        QTableWidget {{
            border: 1px solid #D0D0D0;
            border-radius: 8px;
            background-color: #FFFFFF;
            gridline-color: #E0E0E0;
        }}

        QHeaderView::section {{
            background-color: {self.primary_color};
            color: white;
            padding: 10px;
            border: none;
            font-weight: bold;
            font-size: 12px;
        }}

        QLabel {{ background-color: transparent; }}
        """

        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Interface : combos côte-à-côte, menus sans scroll visible, flèche côté droit."""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ===== COLONNE GAUCHE =====
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(12)

        # En-tête
        header_layout = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel()
        title_icon.setPixmap(qta.icon('fa5s.laptop-code', color='#666').pixmap(24, 24))
        header_layout.addWidget(title_icon)

        self.title_label = QtWidgets.QLabel("Coding")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; padding: 0 8px;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        left_column.addLayout(header_layout)

        # Groupe Paramètres
        self.session_group = QtWidgets.QGroupBox("Paramètres de Session")
        session_layout = QtWidgets.QVBoxLayout(self.session_group)
        session_layout.setSpacing(10)
        session_layout.setContentsMargins(10, 18, 10, 10)

        # Projet + Plateforme côte à côte
        proj_platform_layout = QtWidgets.QHBoxLayout()

        project_label = QtWidgets.QLabel("📁 Projet")
        project_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setMinimumWidth(180)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)

        platform_label = QtWidgets.QLabel("Plateforme IA")
        platform_label.setStyleSheet("font-weight: 600; font-size: 12px; margin-left: 20px;")
        self.platforms_combo = QtWidgets.QComboBox()
        self.platforms_combo.setMinimumWidth(180)

        # Forcer l'affichage de la liste au clic et cacher la scrollbar
        for combo in (self.project_combo, self.platforms_combo):
            combo.setMaxVisibleItems(10)
            combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            combo.setStyleSheet("QComboBox::drop-down { border: none; background: transparent; }")

        proj_platform_layout.addWidget(project_label)
        proj_platform_layout.addWidget(self.project_combo)
        proj_platform_layout.addWidget(platform_label)
        proj_platform_layout.addWidget(self.platforms_combo)
        proj_platform_layout.addStretch()
        session_layout.addLayout(proj_platform_layout)

        # Contexte
        context_label = QtWidgets.QLabel("💡 Contexte (Fonctionnalité souhaitée)")
        context_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        session_layout.addWidget(context_label)

        self.context_edit = QtWidgets.QTextEdit()
        self.context_edit.setPlaceholderText("Décrivez la fonctionnalité à implémenter...")
        self.context_edit.setMinimumHeight(150)
        session_layout.addWidget(self.context_edit)

        # === NOUVELLE SECTION : Bouton Périmètre amélioré ===
        perimeter_container = QtWidgets.QVBoxLayout()
        perimeter_container.setSpacing(10)

        # Label et Bouton sur la même ligne
        perimeter_header = QtWidgets.QHBoxLayout()
        perimeter_label_title = QtWidgets.QLabel(" Périmètre d'implémentation")
        perimeter_label_title.setStyleSheet("font-weight: 600; font-size: 12px;")
        perimeter_header.addWidget(perimeter_label_title)
        perimeter_header.addStretch()

        # Bouton Définir le Périmètre - Dimensions réduites
        self.taxonomy_button = QtWidgets.QPushButton()
        self.taxonomy_button.setIcon(qta.icon('fa5s.sitemap', color='white'))
        self.taxonomy_button.setText("  Définir le Périmètre")
        self.taxonomy_button.clicked.connect(self._on_define_taxonomy)
        self.taxonomy_button.setEnabled(False)
        self.taxonomy_button.setFixedWidth(180)  # Largeur fixe réduite
        self.taxonomy_button.setFixedHeight(32)   # Hauteur réduite

        # Style dynamique selon l'état
        self.taxonomy_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CCCCCC;
                color: #888888;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:enabled {{
                background-color: {self.secondary_color};
                color: white;
            }}
            QPushButton:enabled:hover {{
                background-color: {self.primary_color};
            }}
            QPushButton:disabled {{
                background-color: #E8E8E8;
                color: #AAAAAA;
            }}
        """)

        perimeter_header.addWidget(self.taxonomy_button)
        perimeter_container.addLayout(perimeter_header)

        # Zone d'affichage du périmètre - Sans cadre, texte plus grand
        perimeter_display_layout = QtWidgets.QVBoxLayout()
        perimeter_display_layout.setContentsMargins(0, 5, 0, 5)
        perimeter_display_layout.setSpacing(8)

        # Label d'état - Texte plus grand et visible
        self.perimeter_status_label = QtWidgets.QLabel("Aucun périmètre défini")
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #888888;
            font-style: italic;
            padding: 8px;
            background-color: transparent;
        """)
        perimeter_display_layout.addWidget(self.perimeter_status_label)

        # Zone détaillée - Sans cadre, texte lisible
        self.perimeter_details_label = QtWidgets.QLabel()
        self.perimeter_details_label.setStyleSheet("""
            font-size: 12px;
            color: #333333;
            padding: 10px;
            background-color: #F9F9F9;
            border-left: 3px solid #A23B2D;
            line-height: 1.6;
        """)
        self.perimeter_details_label.setWordWrap(True)
        self.perimeter_details_label.setVisible(False)
        perimeter_display_layout.addWidget(self.perimeter_details_label)

        perimeter_container.addLayout(perimeter_display_layout)
        session_layout.addLayout(perimeter_container)

        # Boutons Action
        buttons_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("  Démarrer")
        self.start_button.setIcon(qta.icon('fa5s.play', color='white'))
        self.start_button.clicked.connect(self._on_start_session)

        self.export_button = QtWidgets.QPushButton("  Export")
        self.export_button.setIcon(qta.icon('fa5s.download', color='white'))
        self.export_button.clicked.connect(self._on_export_results)
        self.export_button.setEnabled(False)

        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.export_button)
        session_layout.addLayout(buttons_layout)
        session_layout.addStretch()
        left_column.addWidget(self.session_group)

        # Statut
        status_container = QtWidgets.QVBoxLayout()
        status_header = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel()
        status_icon.setPixmap(qta.icon('fa5s.info-circle', color='#666').pixmap(16, 16))
        status_header.addWidget(status_icon)

        self.status_label = QtWidgets.QLabel("Prêt")
        self.status_label.setStyleSheet("color: #333; font-weight: bold; font-size: 11px; padding: 4px;")
        status_header.addWidget(self.status_label)
        status_header.addStretch()
        status_container.addLayout(status_header)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(18)
        status_container.addWidget(self.progress_bar)
        left_column.addLayout(status_container)

        # Colonne droite (résultats)
        right_column = QtWidgets.QVBoxLayout()
        self.results_group = QtWidgets.QGroupBox("Résultats")
        results_layout = QtWidgets.QVBoxLayout(self.results_group)
        self.solutions_table = QtWidgets.QTableWidget()
        self.solutions_table.setColumnCount(2)
        self.solutions_table.setHorizontalHeaderLabels(["Plateforme", "Solution"])
        self.solutions_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.solutions_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.solutions_table.verticalHeader().setVisible(False)
        self.solutions_table.cellDoubleClicked.connect(self._on_solution_double_clicked)
        results_layout.addWidget(self.solutions_table)
        right_column.addWidget(self.results_group)

        main_layout.addLayout(left_column, 1)
        main_layout.addLayout(right_column, 2)

    def _load_projects_list(self):
        """Charge la liste des projets avec icônes"""
        if not self.dgraph_connector.client:
            if not self.dgraph_connector.connect():
                logger.warning("Cannot connect to Dgraph")
                return
        
        query_result = self.dgraph_connector.query_full_context()
        if not query_result or not query_result.get('q'):
            logger.info("No projects found in Dgraph")
            return
        
        self.project_combo.clear()
        
        # Option par défaut avec icône
        self.project_combo.addItem(
            qta.icon('fa5s.folder-open', color='#999999'),
            "Sélectionnez un projet...",
            None
        )
        
        seen_projects = set()
        for workspace in query_result['q']:
            project_name = workspace.get('name', '')
            if project_name and project_name not in seen_projects:
                seen_projects.add(project_name)
                # Icône de projet avec couleur distinctive
                self.project_combo.addItem(
                    qta.icon('fa5s.project-diagram', color='#A23B2D'),
                    f"📁 {project_name}",
                    workspace
                )
        
        logger.info(f"Loaded {len(seen_projects)} projects with icons")

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet - Active le bouton périmètre"""
        if index <= 0:
            self.current_project_data = None
            self.taxonomy_button.setEnabled(False)
            self.selected_taxonomy = []
            self._update_perimeter_display()
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
            self._update_perimeter_display()

    def _update_perimeter_display(self):
        """Met à jour l'affichage du périmètre défini"""
        if not self.selected_taxonomy:
            # État : Aucun périmètre
            self.perimeter_status_label.setText("⚪ Aucun périmètre défini")
            self.perimeter_status_label.setStyleSheet("""
                font-size: 13px;
                color: #888888;
                font-style: italic;
                padding: 8px;
                background-color: transparent;
            """)
            self.perimeter_details_label.setVisible(False)
            return

        # Calculer les statistiques
        count = len(self.selected_taxonomy)
        level = self.selected_taxonomy[0]['level'] if self.selected_taxonomy else 1

        total_items = count
        total_relations = 0
        for tax in self.selected_taxonomy:
            related = tax.get('related', [])
            total_relations += len(related)
            total_items += len(related)

        # Noms des éléments principaux
        names = [t['name'] for t in self.selected_taxonomy[:3]]
        display_names = ", ".join(names)
        if count > 3:
            display_names += f" et {count - 3} autre(s)"

        # Mise à jour du label d'état - Texte plus grand et visible
        self.perimeter_status_label.setText(f" {count} élément(s) sélectionné(s) • Niveau {level}")
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #2E7D32;
            font-weight: bold;
            padding: 8px;
            background-color: transparent;
        """)

        # Détails complets - Texte lisible sans cadre
        details_html = f"""
        <div style='line-height: 1.8;'>
            <p style='margin: 0 0 12px 0;'>
                <span style='color: #A23B2D; font-weight: bold; font-size: 13px;'> Éléments sélectionnés:</span><br/>
                <span style='color: #333; font-size: 12px; margin-left: 8px;'>{display_names}</span>
            </p>
            <p style='margin: 0;'>
                <span style='color: #555; font-weight: bold; font-size: 12px;'> Statistiques du périmètre:</span><br/>
                <span style='color: #333; font-size: 12px;'>
                    • <b>{total_relations}</b> relations incluses<br/>
                    • <b>{total_items}</b> éléments au total<br/>
                    • <b>Niveau {level}</b> de profondeur
                </span>
            </p>
        </div>
        """

        self.perimeter_details_label.setTextFormat(QtCore.Qt.RichText)
        self.perimeter_details_label.setText(details_html)
        self.perimeter_details_label.setVisible(True)

        logger.info(
            f"Perimeter updated: {count} main items, {total_relations} relations, "
            f"{total_items} total elements (Level {level})"
        )

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
        """Définit la liste des profils de plateformes avec icônes"""
        self.platforms_combo.clear()

        # Option par défaut
        default_item = "Sélectionnez une plateforme IA"
        self.platforms_combo.addItem(
            qta.icon('fa5s.robot', color='#999999'),
            default_item,
            ""
        )

        # Plateformes IA avec icônes colorées
        ai_platforms = [
            ("Claude AI", "claud ai", '#A23B2D'),
            ("ChatGPT", "chatgpt", '#10A37F'),
            ("Grok", "grok", '#000000'),
            ("Gemini", "gemini", '#4285F4')
        ]

        for display_name, internal_name, color in ai_platforms:
            self.platforms_combo.addItem(
                display_name,
                internal_name
            )

        logger.info("Loaded AI platforms with custom icons")

    def update_status(self, message, progress=None):
        """Met à jour le statut de la session"""
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)

    def new_session(self):
        """Crée une nouvelle session - Réinitialise le périmètre"""
        self.project_combo.setCurrentIndex(0)
        self.context_edit.clear()
        self.platforms_combo.setCurrentIndex(0)
        self.selected_taxonomy = []
        self._update_perimeter_display()
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