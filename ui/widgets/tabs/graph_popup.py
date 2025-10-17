import qtawesome as qta

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import logger

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