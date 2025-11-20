# relation_import_widget.py - Version avec Cache et Barre de Progression
import math
import os
import json
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
import uuid

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QPushButton

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

import qtawesome as qta
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui.widgets.tabs.pythonSyntax_highlighter import PythonSyntaxHighlighter
from utils.dgraph_connector import LirisDgraphConnector
from utils.logger import logger
from ui.localization.translator import tr


class QueryCache:
    """Système de cache pour les requêtes Dgraph avec expiration."""
    
    def __init__(self, ttl_seconds=300):  # 5 minutes par défaut
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Dict]:
        """Récupère une valeur du cache si elle n'a pas expiré."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                logger.info(f"Cache HIT pour: {key[:50]}...")
                return data
            else:
                logger.info(f"Cache EXPIRED pour: {key[:50]}...")
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        """Stocke une valeur dans le cache."""
        self.cache[key] = (value, datetime.now())
        logger.info(f"Cache SET pour: {key[:50]}...")
    
    def clear(self):
        """Vide le cache."""
        self.cache.clear()
        logger.info("Cache vidé")
    
    def get_stats(self) -> str:
        """Retourne les statistiques du cache."""
        return f"Cache: {len(self.cache)} entrées"

class TaxonomyItem(QtWidgets.QTreeWidgetItem):
    """Item pour l'arbre de taxonomie avec métadonnées."""
    def __init__(self, parent, text, item_type="folder", data=None, level=0):
        super().__init__(parent, [text])
        self.item_type = item_type
        self.item_data = data or {}
        self.level = level
        
        # Palette monochrome professionnelle
        primary = '#A23B2D'
        dark_gray = '#424242'
        strong_gray = '#555555'
        
        icon_map = {
            "folder": ('fa5s.folder', strong_gray),
            "file": ('fa5s.file-code', strong_gray),
            "function": ('fa5s.cog', primary),
            "dependency": ('fa5s.link', strong_gray),
            "class": ('fa5s.cubes', dark_gray),
            "variable": ('fa5s.tag', '#999999'),
        }
        
        icon_name, icon_color = icon_map.get(item_type, ('fa5s.question-circle', strong_gray))
        self.setIcon(0, qta.icon(icon_name, color=icon_color))

class RelationImportWidget(QtWidgets.QWidget):
    """Widget pour gérer les relations et imports du projet"""
    
    dependency_analysis_finished = pyqtSignal(dict)
    
    def __init__(self, config_provider=None, conductor=None, dgraph_connector=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.dgraph_connector = dgraph_connector or LirisDgraphConnector(auto_reset=False)
        self.current_project_data = None
        self.current_graph = None
        self.current_relations = []
        self.hidden_relations = set()
        self._node_cache = {}
        self._name_cache = {}
        self._uid_set = set()
        self.current_central_uid = None
        self.current_central_name = None

        self.navigation_history = []
        self.info_text_obj = None
        self.info_text_obj = None
        self.origins_text_obj = None
        
        # Système de cache
        self.query_cache = QueryCache(ttl_seconds=600)  # 10 minutes
        
        # Cache pour les mappings UID
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}

        from PyQt5.QtCore import QTimer
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._handle_single_click)
        self.pending_click_node = None
        self.pending_click_graph = None

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"

        self.setStyleSheet(self._get_stylesheet())
        self._init_ui()
        self._load_projects_list()

    def _get_clusters_data(self):
        """
        ✅ VERSION CORRIGÉE : Récupère TOUTE la hiérarchie récursivement
        """
        clusters = []

        if self.dgraph_connector and self.dgraph_connector.client:
            logger.info("📡 Chargement depuis Dgraph (avec hiérarchie complète)...")

            # ✅ CORRECTION : Requête récursive sur TOUS les niveaux
            query_labels = """
            {
              all_labels(func: type(Label)) @filter(eq(level, 0)) {
                uid
                name
                id
                level
                path
                nodeType
                category
                description
                files
                fileContents

                parent_clusters: clusters {
                  uid
                  name
                  id
                  description
                  nodeType
                  files
                  fileContents
                  createdAt
                  updatedAt
                }

                # ✅ Éléments de code du niveau 0
                classes {
                  uid
                  name
                  description
                  line
                  bases
                  uses_vars
                  methods { uid name description line params returns }
                  variables { uid name description line var_type scope }
                }

                functions {
                  uid
                  name
                  description
                  line
                  params
                  returns
                  variables { uid name description line var_type scope }
                }

                variables {
                  uid
                  name
                  description
                  line
                  var_type
                  scope
                }

                # ✅ NIVEAU 1 (enfants directs)
                level1: ~parents @filter(eq(level, 1)) {
                  uid
                  name
                  id
                  level
                  nodeType
                  path
                  description
                  files
                  fileContents

                  classes {
                    uid
                    name
                    description
                    line
                    methods { uid name description line }
                    variables { uid name description line }
                  }

                  functions {
                    uid
                    name
                    description
                    line
                    variables { uid name description line }
                  }

                  variables {
                    uid
                    name
                    description
                    line
                  }

                  # ✅ NIVEAU 2
                  level2: ~parents @filter(eq(level, 2)) {
                    uid
                    name
                    id
                    level
                    nodeType
                    path
                    description
                    files
                    fileContents

                    classes {
                      uid
                      name
                      description
                      line
                      methods { uid name description line }
                    }

                    functions {
                      uid
                      name
                      description
                      line
                    }

                    variables {
                      uid
                      name
                      description
                      line
                    }

                    # ✅ NIVEAU 3
                    level3: ~parents @filter(eq(level, 3)) {
                      uid
                      name
                      id
                      level
                      nodeType
                      path
                      description
                      files
                      fileContents

                      classes { uid name description line }
                      functions { uid name description line }
                      variables { uid name description line }

                      # ✅ NIVEAU 4
                      level4: ~parents @filter(eq(level, 4)) {
                        uid
                        name
                        id
                        level
                        nodeType
                        path
                        description
                        files
                        fileContents

                        classes { uid name description line }
                        functions { uid name description line }
                        variables { uid name description line }
                      }
                    }
                  }
                }
              }
            }
            """

            try:
                txn = self.dgraph_connector.client.txn(read_only=True)
                resp = txn.query(query_labels)
                txn.discard()

                result = self.dgraph_connector._parse_response(resp)
                all_labels = result.get('all_labels', [])

                logger.info(f"📥 Récupéré {len(all_labels)} labels niveau 0 depuis Dgraph")

                clusters_dict = {}

                # Regrouper par cluster parent
                for label in all_labels:
                    parent_clusters = label.get('parent_clusters', [])

                    if not parent_clusters:
                        # Label orphelin → créer un cluster virtuel
                        uid = label.get('uid', f"generated_{uuid.uuid4()}")
                        clusters_dict[uid] = {
                            'uid': uid,
                            'name': label.get('name', 'Label isolé'),
                            'id': uid,
                            'nodeType': label.get('nodeType', 'file'),
                            'root_labels': [label]
                        }
                        continue

                    for cluster_data in parent_clusters:
                        cluster_uid = cluster_data.get('uid')
                        if not cluster_uid:
                            continue
                        
                        if cluster_uid not in clusters_dict:
                            clusters_dict[cluster_uid] = {
                                'uid': cluster_uid,
                                'name': cluster_data.get('name', 'Cluster sans nom'),
                                'description': cluster_data.get('description', ''),
                                'nodeType': cluster_data.get('nodeType', 'cluster'),
                                'files': cluster_data.get('files', []),
                                'fileContents': cluster_data.get('fileContents', ''),
                                'root_labels': []
                            }

                        clusters_dict[cluster_uid]['root_labels'].append(label)

                clusters = list(clusters_dict.values())
                logger.info(f"📦 {len(clusters)} clusters chargés avec hiérarchie complète.")

                return clusters

            except Exception as e:
                logger.error(f"❌ Erreur Dgraph lors du chargement : {e}")
                import traceback
                traceback.print_exc()

        logger.warning("⚠️ Aucune source Dgraph active, fallback local.")
        return []
    
    def normalize_node_name(self, name: str) -> str:
        """Normalise le nom d'un nœud en enlevant l'extension et le chemin."""
        if not name or not isinstance(name, str):
            logger.warning(f"Invalid name input: {name}")
            return f"unnamed_{id(name)}"

        name = name.strip()
        if not name or name.lower() == 'n/a':
            logger.warning(f"Empty or 'n/a' name: {name}")
            return f"unnamed_{id(name)}"

        base = os.path.basename(name)
        name_without_ext = os.path.splitext(base)[0]
        normalized = name_without_ext.strip()

        if not normalized:
            logger.warning(f"Normalized name is empty: {name}")
            return f"unnamed_{id(name)}"

        return normalized
    
    def _compute_grouped_layout(self, G: nx.DiGraph, center_node: str = None, existing_orbits=None):
        """
        ✅ VERSION AMÉLIORÉE : Rayons adaptatifs selon la densité
        """
        import numpy as np
    
        if len(G.nodes()) == 0:
            return {}, {}
    
        # Reprendre les orbites existantes si elles existent
        node_orbits = existing_orbits.copy() if existing_orbits else {}
    
        # Grouper par type
        HIERARCHICAL_TYPES = {'parent', 'child', 'contains', 'belongs_to', 'hierarchy', 'has'}
        CODE_TYPES = {'call', 'calls', 'method_call', 'function_call', 'uses', 'used_by',
                      'implements', 'extends', 'inherits', 'override', 'invoke'}
        EXTERNAL_TYPES = {'import', 'from_import', 'require', 'include', 'dependency', 'external'}
    
        # Identifier les nouveaux nœuds
        hierarchical_nodes, code_nodes, external_nodes = [], [], []
        for node in G.nodes():
            if node == center_node:
                continue
            if node in node_orbits:
                continue  # déjà positionné
            
            primary_types = {data.get('relation_type', '').lower()
                             for _, _, data in G.edges(data=True)
                             if _ == node or data.get('target') == node}
            categories = {data.get('category', '').lower()
                          for _, _, data in G.edges(data=True)
                          if _ == node or data.get('target') == node}
    
            if any(t in HIERARCHICAL_TYPES for t in primary_types) or 'hierarchy' in categories:
                hierarchical_nodes.append(node)
            elif any(t in CODE_TYPES for t in primary_types) or 'code' in categories:
                code_nodes.append(node)
            else:
                external_nodes.append(node)
    
        # ✅ CALCUL ADAPTATIF DES RAYONS selon nombre de nœuds
        num_nodes = len(G.nodes())
        max_existing_orbit = max(node_orbits.values()) if node_orbits else 0
        
        # ✅ NOUVEAU : Calculer la circonférence nécessaire pour chaque orbite
        # Dimension fixe d'un nœud : ~4.0 de largeur
        node_width = 4.0
        min_spacing = 1.5  # Espace minimal entre nœuds
        
        def calculate_optimal_radius(num_nodes_on_orbit, base_radius):
            """Calcule le rayon optimal pour éviter les superpositions"""
            if num_nodes_on_orbit == 0:
                return base_radius
            
            # Circonférence requise = (largeur nœud + espacement) * nombre de nœuds
            required_circumference = (node_width + min_spacing) * num_nodes_on_orbit
            
            # Rayon minimal requis = circonférence / (2π)
            min_required_radius = required_circumference / (2 * math.pi)
            
            # Retourner le maximum entre rayon de base et rayon requis
            return max(base_radius, min_required_radius)
    
        # ✅ Rayons de base (augmentés progressivement)
        base_gap = 8.0  # Augmenté de 6.0 à 8.0
        
        # Calculer rayons optimaux pour chaque orbite
        radius_inner = calculate_optimal_radius(
            len(hierarchical_nodes),
            base_gap * (1 + max_existing_orbit)
        )
        
        radius_middle = calculate_optimal_radius(
            len(code_nodes),
            base_gap * (2 + max_existing_orbit)
        )
        
        radius_outer = calculate_optimal_radius(
            len(external_nodes),
            base_gap * (3 + max_existing_orbit)
        )
        
        logger.info(f"📏 Rayons calculés : inner={radius_inner:.1f}, middle={radius_middle:.1f}, outer={radius_outer:.1f}")
    
        pos = {}
    
        # Garder les anciennes positions
        if hasattr(self, 'graph_data') and 'pos' in self.graph_data:
            for n, coords in self.graph_data['pos'].items():
                pos[n] = np.array(coords)
    
        def distribute(nodes, radius, orbit_id, angular_offset=0.0):
            n = len(nodes)
            if n == 0:
                return
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / n + angular_offset
                # Petite variation aléatoire réduite
                angle += (math.pi / 180) * np.random.uniform(-3, 3)
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                pos[node] = np.array([x, y])
                node_orbits[node] = orbit_id
    
        # Placer les nouveaux nœuds
        distribute(hierarchical_nodes, radius_inner, max_existing_orbit + 1)
        distribute(code_nodes, radius_middle, max_existing_orbit + 2)
        distribute(external_nodes, radius_outer, max_existing_orbit + 3)
    
        if center_node and center_node in G.nodes():
            pos[center_node] = np.array([0.0, 0.0])
            node_orbits[center_node] = 0
    
        # Sauvegarder orbites
        if hasattr(self, 'graph_data'):
            self.graph_data['node_orbits'] = node_orbits
    
        return pos, node_orbits

    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """Construit un graphe NetworkX propre avec regroupement par type de relation + nœuds externes."""
        G = nx.DiGraph()
        nodes_registry = {}
        edges_registry = {}

        # ✅ VALIDATION ET NETTOYAGE DES RELATIONS
        valid_relations = []
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))
            relation_type = rel.get('relation_type', rel.get('relationType', 'unknown'))

            if not source or not target:
                continue
            if source == target:
                continue
            
            rel_normalized = {
                'source': source,
                'target': target,
                'relation_type': relation_type,
                'category': rel.get('category', 'custom'),
                'source_uid': rel.get('source_uid'),
                'target_uid': rel.get('target_uid'),
                'source_type': rel.get('source_type', 'unknown'),
                'target_type': rel.get('target_type', 'unknown')
            }
            valid_relations.append(rel_normalized)

        logger.info(f"🔍 Relations valides après nettoyage: {len(valid_relations)}")

        # ✅ Regrouper les relations par type et catégorie
        relations_by_type = defaultdict(list)
        for rel in valid_relations:
            key = (rel['relation_type'], rel['category'])
            relations_by_type[key].append(rel)

        logger.info(f"📊 Types de relations détectés: {len(relations_by_type)}")
        for (rel_type, category), rels in relations_by_type.items():
            logger.info(f"  • {rel_type} [{category}]: {len(rels)} relations")

        # ✅ Création ou récupération des nœuds
        for rel in valid_relations:
            source = rel['source']
            target = rel['target']

            # --- SOURCE ---
            if source not in nodes_registry:
                node_type = rel.get('source_type') or 'unknown'

                # ✅ CORRECTION : Détection améliorée du type de nœud
                if node_type in ['unknown', '', None]:
                    # Essayer de déduire depuis le nom
                    if source.startswith(('F:', 'M:')):
                        node_type = 'function'
                    elif source.startswith('C:'):
                        node_type = 'class'
                    elif source.startswith('V:'):
                        node_type = 'variable'
                    elif self._has_extension(source):
                        node_type = 'file'
                    else:
                        node_type = 'external'

                    logger.debug(f"   🔍 Type déduit pour source '{source}': {node_type}")

                nodes_registry[source] = {
                    'node_type': node_type,
                    'uid': rel.get('source_uid') or f"ext_{uuid.uuid4()}",
                    'relation_types': {rel['relation_type']}
                }
            else:
                nodes_registry[source]['relation_types'].add(rel['relation_type'])

            # --- TARGET ---
            if target not in nodes_registry:
                node_type = rel.get('target_type') or 'unknown'

                # ✅ CORRECTION : Détection améliorée du type de nœud
                if node_type in ['unknown', '', None]:
                    # Essayer de déduire depuis le nom
                    if target.startswith(('F:', 'M:')):
                        node_type = 'function'
                    elif target.startswith('C:'):
                        node_type = 'class'
                    elif target.startswith('V:'):
                        node_type = 'variable'
                    elif self._has_extension(target):
                        node_type = 'file'
                    else:
                        node_type = 'external'

                    logger.debug(f"   🔍 Type déduit pour target '{target}': {node_type}")

                nodes_registry[target] = {
                    'node_type': node_type,
                    'uid': rel.get('target_uid') or f"ext_{uuid.uuid4()}",
                    'relation_types': {rel['relation_type']}
                }
            else:
                nodes_registry[target]['relation_types'].add(rel['relation_type'])

        # ✅ Ajouter nœuds au graphe
        for node_name, node_info in nodes_registry.items():
            node_type = node_info.get('node_type', 'unknown')

            # ✅ COULEURS ADAPTÉES PAR TYPE
            color_map = {
                'function': '#00BCD4',      # Cyan pour fonctions
                'method': '#26C6DA',        # Cyan clair pour méthodes
                'class': '#9C27B0',         # Violet pour classes
                'variable': '#FFA726',      # Orange pour variables
                'file': '#5CAD56',          # Vert pour fichiers
                'folder': '#66BB6A',        # Vert clair pour dossiers
                'external': '#CCCCCC',      # Gris pour externes
                'unknown': '#999999'        # Gris foncé pour inconnus
            }

            color = color_map.get(node_type, '#5CAD56')

            G.add_node(
                node_name,
                node_type=node_type,
                uid=node_info['uid'],
                relation_types=list(node_info['relation_types']),
                color=color
            )

            # ✅ LOG pour debug
            logger.debug(f"   ➕ Nœud ajouté : {node_name} (type={node_type}, color={color})")

        # ✅ Gestion des arêtes avec multi-types
        for rel in valid_relations:
            source = rel['source']
            target = rel['target']
            rel_type = rel['relation_type']
            category = rel['category']

            edge_key = (source, target)
            if edge_key not in edges_registry:
                edges_registry[edge_key] = {
                    'types': [],
                    'categories': set(),
                    'primary_type': rel_type,
                    'primary_category': category
                }

            type_label = f"{rel_type} [{category}]" if category != 'custom' else rel_type
            if type_label not in edges_registry[edge_key]['types']:
                edges_registry[edge_key]['types'].append(type_label)
                edges_registry[edge_key]['categories'].add(category)

        for (source, target), edge_info in edges_registry.items():
            rel_types = edge_info['types']
            primary_type = edge_info['primary_type'].lower()
            primary_category = edge_info['primary_category'].lower()

            combined_label = (
                rel_types[0] if len(rel_types) == 1 else f"{rel_types[0]} (+{len(rel_types)-1})"
            )

            # 🎨 CORRECTION : Couleurs basées sur catégorie + type de relation

            # 1. Relations intra-fichier (VIOLET - checkbox)
            if primary_category == 'intra_file' or 'intra' in primary_category:
                edge_color = '#9C27B0'  # Violet

            # 2. Relations hiérarchiques (VERT)
            elif primary_category in ['hierarchy', 'internal'] or primary_type in ['parent', 'child', 'contains', 'belongs_to']:
                edge_color = '#5CAD56'  # Vert

            # 3. Relations externes/imports (ORANGE)
            elif primary_category in ['external', 'import', 'from_import', 'require'] or \
                 any(k in primary_type for k in ['import', 'require', 'include', 'dependency', 'from_import']):
                edge_color = '#FF8C00'  # Orange

            # 4. Appels inter-fichiers (CYAN)
            elif primary_category == 'inter_file' or \
                 (any(k in primary_type for k in ['call', 'calls', 'invoke', 'use', 'uses']) and primary_category != 'intra_file'):
                edge_color = '#00BCD4'  # Cyan

            # 5. Par défaut (gris)
            else:
                edge_color = '#999999'

            G.add_edge(
                source,
                target,
                color=edge_color,
                relation_type=primary_type,
                all_types=rel_types,
                label=combined_label,
                categories=list(edge_info['categories'])
            )

        # ✅ STATISTIQUES FINALES
        logger.info(f"✅ Graphe construit avec {len(G.nodes)} nœuds et {len(G.edges)} arêtes")

        # Log des externes
        externals = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'external']
        if externals:
            logger.info(f"🌐 {len(externals)} nœuds externes ajoutés automatiquement")

        # Log détaillé des types de nœuds
        node_types_count = {}
        for node, data in G.nodes(data=True):
            ntype = data.get('node_type', 'unknown')
            node_types_count[ntype] = node_types_count.get(ntype, 0) + 1

        logger.info(f"📊 Types de nœuds :")
        for ntype, count in sorted(node_types_count.items()):
            logger.info(f"   • {ntype}: {count}")

        # Log des catégories de relations
        edge_categories_count = {}
        for u, v, data in G.edges(data=True):
            categories = data.get('categories', ['unknown'])
            for cat in categories:
                edge_categories_count[cat] = edge_categories_count.get(cat, 0) + 1

        logger.info(f"📊 Catégories de relations :")
        for cat, count in sorted(edge_categories_count.items()):
            logger.info(f"   • {cat}: {count}")

        return G

    def _get_edge_color_by_category(self, category: str, rel_type: str = None) -> str:
        """
        ✅ CORRIGÉ : Retourne la couleur d'arête selon la catégorie et le type
        """
        category_lower = category.lower() if category else ''
        rel_type_lower = rel_type.lower() if rel_type else ''

        # 1. Relations intra-fichier (VIOLET - activées par checkbox)
        if category_lower in ['intra_file', 'code_internal'] or 'intra' in category_lower:
            return '#9C27B0'  # Violet pour appels internes

        # 2. Relations inter-fichiers (cyan)
        if category_lower in ['inter_file'] or 'inter' in category_lower:
            return '#00BCD4'  # Cyan

        # 3. Relations hiérarchiques (VERT - structure du projet)
        if category_lower in ['hierarchy', 'internal']:
            return '#5CAD56'  # Vert comme les nœuds hiérarchiques

        # 4. Relations de code (calls, uses)
        if category_lower in ['code', 'parsed']:
            if 'call' in rel_type_lower:
                return '#00BCD4'  # Cyan pour appels inter-fichiers
            if 'use' in rel_type_lower:
                return '#00BCD4'  # Cyan pour usages
            return '#66BB6A'  # Vert par défaut

        # 5. Relations externes/imports (ORANGE)
        if category_lower in ['external', 'import', 'from_import', 'require']:
            return '#FF8C00'  # Orange pour imports/dépendances externes

        # 6. Détection par type de relation
        if rel_type_lower:
            # Imports/dépendances externes
            if any(k in rel_type_lower for k in ['import', 'require', 'include', 'dependency', 'from_import']):
                return '#FF8C00'  # Orange

            # Appels/usages internes
            if any(k in rel_type_lower for k in ['call', 'calls', 'use', 'uses', 'invoke']):
                return '#00BCD4'  # Cyan

            # Relations hiérarchiques
            if any(k in rel_type_lower for k in ['parent', 'child', 'contains', 'belongs_to']):
                return '#5CAD56'  # Vert

        # 7. Relations custom (gris)
        if category_lower == 'custom':
            return '#999999'  # Gris

        # 8. Fallback final
        return '#CCCCCC'  # Gris clairr
    
    def _get_function_source_content(self, function_uid: str, function_name: str) -> Dict:
        """✅ CORRIGÉ : Récupère le code avec fallback automatique si l'UID est incorrect."""

        # ✅ AJOUT : Logs console + fichier
        print(f"\n{'='*70}")
        print(f"🔍 RÉCUPÉRATION CONTENU FONCTION")
        print(f"   Nom : {function_name}")
        print(f"   UID : {function_uid}")
        print(f"{'='*70}")

        if not function_uid or not self.dgraph_connector:
            print("❌ UID ou connecteur manquant")
            logger.error("❌ UID ou connecteur manquant")
            return {}

        logger.info(f"\n{'='*70}")
        logger.info(f"📄 RÉCUPÉRATION CONTENU FONCTION : {function_name}")
        logger.info(f"   UID: {function_uid}")
        logger.info(f"{'='*70}")

        # ✅ Normaliser le nom de la fonction
        normalized_name = self.normalize_node_name(function_name)

        # Retirer préfixe "F: " ou "M: " si présent
        search_name = normalized_name
        if ':' in search_name:
            search_name = search_name.split(':', 1)[1].strip()

        logger.info(f"🔍 Recherche avec nom: '{search_name}'")
        print(f"🔍 Recherche avec nom: '{search_name}'")

        # ✅ ÉTAPE 1 : Essayer avec l'UID direct (sans filtre de type)
        query_by_uid = f"""
        {{
          by_uid(func: uid({function_uid})) {{
            uid
            name
            description
            line
            params
            returns
            path
            sourcePath
            full_path
            codeContent
            dgraph.type
            nodeType

            # Parent fichier (si fonction globale)
            ~functions {{
              uid
              name
              path
              sourcePath
              full_path
              fileContents
              codeContent
            }}

            # Parent classe (si méthode)
            ~methods {{
              uid
              name
              description
              line

              # Fichier de la classe
              ~classes {{
                uid
                name
                path
                sourcePath
                full_path
                fileContents
                codeContent
              }}
            }}
          }}
        }}
        """

        print(f"📡 Requête 1 : Par UID direct...")
        result = self._execute_dgraph_query(query_by_uid)

        if result and 'by_uid' in result and result['by_uid']:
            node_data = result['by_uid'][0]

            # Vérifier si on a plus que juste l'UID
            if len(node_data) > 1:
                print(f"✅ Données reçues pour UID {function_uid}")
                logger.info(f"✅ Données reçues pour UID {function_uid}")

                # Essayer d'extraire le code
                code_result = self._extract_code_from_node_data(
                    node_data, 
                    search_name, 
                    function_uid, 
                    function_name
                )

                if code_result and code_result.get('content') and not code_result['content'].startswith('# Code source non disponible'):
                    print(f"✅ Code récupéré avec UID direct ({len(code_result['content'])} chars)")
                    logger.info(f"✅ Code récupéré avec UID direct")
                    return code_result
            else:
                print(f"⚠️ UID {function_uid} retourne seulement l'UID (nœud vide)")
                logger.warning(f"⚠️ UID {function_uid} retourne seulement l'UID (nœud vide)")

        # ❌ ÉTAPE 2 : L'UID ne retourne pas de code → Chercher par nom
        print(f"\n🔄 FALLBACK : Recherche par nom...")
        logger.warning(f"🔄 UID {function_uid} vide ou invalide, recherche par nom...")

        query_by_name = f"""
        {{
          by_name(func: eq(name, "{search_name}")) {{
            uid
            name
            description
            line
            params
            returns
            path
            sourcePath
            full_path
            codeContent
            dgraph.type
            nodeType

            ~functions {{
              uid
              name
              path
              sourcePath
              full_path
              fileContents
              codeContent
            }}

            ~methods {{
              uid
              name
              description

              ~classes {{
                uid
                name
                path
                sourcePath
                full_path
                fileContents
                codeContent
              }}
            }}
          }}
        }}
        """

        print(f"📡 Requête 2 : Par nom '{search_name}'...")
        result = self._execute_dgraph_query(query_by_name)

        if not result or 'by_name' not in result:
            print("❌ Aucun résultat par nom")
            logger.error("❌ Aucun résultat par nom")
            return self._create_error_response(function_uid, function_name, "Fonction introuvable")

        candidates = result['by_name']

        if not candidates:
            print("❌ Aucune fonction trouvée avec ce nom")
            logger.error("❌ Aucune fonction trouvée avec ce nom")
            return self._create_error_response(function_uid, function_name, "Aucune fonction trouvée")

        print(f"📊 {len(candidates)} candidat(s) trouvé(s)")
        logger.info(f"📊 {len(candidates)} candidat(s) trouvé(s) par nom")

        # ✅ Si plusieurs candidats, prendre celui avec du code
        best_candidate = None

        for i, candidate in enumerate(candidates):
            candidate_uid = candidate.get('uid')
            code = candidate.get('codeContent', '').strip()

            print(f"\n  Candidat {i+1}/{len(candidates)}:")
            print(f"    UID: {candidate_uid}")
            print(f"    Code: {len(code) if code else 0} chars")

            logger.info(f"  Candidat {i+1}: UID={candidate_uid}, code={len(code) if code else 0} chars")

            if code:
                best_candidate = candidate
                correct_uid = candidate_uid

                print(f"    ✅ MEILLEUR candidat (a du code)")
                logger.info(f"✅ BON nœud trouvé ! UID correct: {correct_uid} (au lieu de {function_uid})")
                logger.info(f"   Code: {len(code)} caractères")

                # ✅ MISE À JOUR : Corriger l'UID dans le cache pour les prochaines fois
                if hasattr(self, '_node_cache') and function_uid in self._node_cache:
                    old_item = self._node_cache[function_uid]

                    # Créer/mettre à jour avec le bon UID
                    self._node_cache[correct_uid] = old_item
                    old_item.item_data['uid'] = correct_uid

                    print(f"    🔄 Cache mis à jour : {function_uid} → {correct_uid}")
                    logger.info(f"🔄 Cache mis à jour : {function_uid} → {correct_uid}")

                break  # Prendre le premier avec du code
            
        if best_candidate:
            code_result = self._extract_code_from_node_data(
                best_candidate,
                search_name,
                best_candidate.get('uid'),
                function_name
            )

            if code_result and code_result.get('content'):
                print(f"\n✅ CODE FINAL RÉCUPÉRÉ : {len(code_result['content'])} chars")
                logger.info(f"✅ Code récupéré via recherche par nom")
                return code_result

        # ❌ Aucun candidat avec du code
        print(f"\n❌ {len(candidates)} nœud(s) trouvé(s) mais tous vides")
        logger.error(f"❌ {len(candidates)} nœud(s) trouvé(s) mais tous vides")

        return self._create_error_response(
            function_uid, 
            function_name, 
            f"Code vide dans tous les nœuds ({len(candidates)} doublons détectés)"
        )

    def _extract_code_from_node_data(self, node_data: Dict, search_name: str, function_uid: str, function_name: str) -> Dict:
        """✅ NOUVEAU : Extrait le code depuis les données d'un nœud."""

        file_path = None
        file_content = None
        line_number = None
        description = None
        function_content = None

        # Description
        description = node_data.get('description', '')

        # Ligne
        line_number = node_data.get('line')

        # Path depuis la fonction
        file_path = (node_data.get('full_path') or 
                    node_data.get('path') or 
                    node_data.get('sourcePath', ''))

        if file_path and '/' in file_path:
            file_path = file_path.split('/')[0]
        file_path = file_path.replace('\\', '/')

        # ✅ Code content depuis la fonction directement
        function_content = node_data.get('codeContent', '')

        if function_content and function_content.strip():
            logger.info(f"✅ Code trouvé dans codeContent de la fonction ({len(function_content)} chars)")
            print(f"✅ Code trouvé dans codeContent")

            return {
                'content': function_content,
                'file_path': file_path or 'unknown',
                'line': line_number or 0,
                'description': description or f"Fonction: {function_name}"
            }
        else:
            logger.info("ℹ️ Pas de codeContent dans la fonction, recherche dans le parent...")
            print(f"⚠️ Pas de codeContent, recherche parent...")

            # ✅ Chercher dans les parents (fichier)
            parents = node_data.get('~functions', [])

            if parents:
                parent_file = parents[0]
                file_content = (parent_file.get('fileContents') or 
                              parent_file.get('codeContent', ''))

                if not file_path:
                    file_path = (parent_file.get('full_path') or
                               parent_file.get('path') or 
                               parent_file.get('sourcePath', ''))
                    if file_path:
                        file_path = os.path.basename(file_path)

                if file_content:
                    logger.info(f"📄 Contenu fichier récupéré depuis parent (taille: {len(file_content)} chars)")
                    print(f"✅ Contenu fichier récupéré depuis parent")

            # ✅ Si méthode, chercher dans la classe
            class_parents = node_data.get('~methods', [])

            if class_parents and not file_content:
                class_data = class_parents[0]

                # Fichier de la classe
                class_files = class_data.get('~classes', [])

                if class_files:
                    class_file = class_files[0]
                    file_content = (class_file.get('fileContents') or 
                                  class_file.get('codeContent', ''))

                    if not file_path:
                        file_path = (class_file.get('full_path') or
                                   class_file.get('path') or 
                                   class_file.get('sourcePath', ''))
                        if file_path:
                            file_path = os.path.basename(file_path)

                    if file_content:
                        logger.info(f"📄 Contenu fichier récupéré depuis classe parent (taille: {len(file_content)} chars)")
                        print(f"✅ Contenu fichier récupéré depuis classe")

        # ✅ EXTRACTION DU CODE
        extracted_code = None

        if file_content and line_number:
            # Extraire depuis le fichier complet
            print(f"📄 Appel _extract_function_from_file_content()...")
            print(f"   Nom recherché : {search_name}")
            print(f"   Ligne départ : {line_number}")

            extracted_code = self._extract_function_from_file_content(
                file_content, 
                search_name, 
                line_number
            )

            if extracted_code and extracted_code.strip():
                logger.info(f"✅ Code extrait depuis fileContents (ligne {line_number})")
                print(f"✅ Code extrait depuis fileContents : {len(extracted_code)} chars")
            else:
                logger.warning("⚠️ Impossible d'extraire le code depuis le fichier")
                print("❌ Échec extraction depuis fileContents")
                extracted_code = None

        # ✅ Fallback si aucun code trouvé
        if not extracted_code or not extracted_code.strip():
            logger.warning("⚠️ Aucun contenu disponible")
            print("❌ AUCUN CODE EXTRAIT")

            extracted_code = f"# Code source non disponible\n# Fonction: {function_name}\n# UID: {function_uid}\n\n# Le code n'a pas pu être récupéré depuis Dgraph.\n# Vérifiez que le parsing a bien été effectué."

        # ✅ RÉSULTAT FINAL
        result_dict = {
            'content': extracted_code,
            'file_path': file_path or 'unknown',
            'line': line_number or 0,
            'description': description or f"Fonction: {function_name}"
        }

        logger.info(f"\n✅ RÉSULTAT :")
        logger.info(f"   📂 Fichier: {result_dict['file_path']}")
        logger.info(f"   📍 Ligne: {result_dict['line']}")
        logger.info(f"   📏 Taille code: {len(result_dict['content'])} chars")
        logger.info(f"{'='*70}\n")

        return result_dict

    def _create_error_response(self, uid: str, name: str, reason: str) -> Dict:
        """Crée une réponse d'erreur formatée."""

        print(f"\n❌ ERREUR : {reason}")

        return {
            'content': f"""# ❌ Code non disponible
    # Fonction: {name}
    # UID fourni: {uid}

    # Raison: {reason}

    # Causes possibles:
    # 1. Nœud fantôme (doublon vide dans Dgraph)
    # 2. UID incorrect dans la structure
    # 3. Code source jamais parsé/stocké

    # Actions:
    # - ✅ Recherche automatique par nom activée
    # - 🔍 Vérifiez les doublons dans Dgraph
    # - 🔄 Re-parsez le projet si nécessaire

    # Query pour voir les doublons:
    # {{
    #   all(func: eq(name, "{name}")) {{
    #     uid
    #     codeContent
    #   }}
    # }}
    """,
            'file_path': 'error',
            'line': 0,
            'description': reason
        }

    def _extract_function_from_file_content(self, file_content: str, function_name: str, start_line: int) -> str:
        if not file_content:
            logger.warning("⚠️ Contenu fichier vide")
            return ""

        lines = file_content.split('\n')

        if start_line < 1 or start_line > len(lines):
            logger.warning(f"⚠️ Numéro de ligne invalide: {start_line} (fichier: {len(lines)} lignes)")
            return ""

        logger.info(f"🔍 Extraction fonction '{function_name}' depuis ligne {start_line}")
        logger.info(f"📄 Fichier: {len(lines)} lignes totales")

        # ✅ STRATÉGIE 1 : Recherche par ligne de début
        # Convertir en index 0-based
        start_index = start_line - 1

        # Vérifier que c'est bien le début de la fonction
        line_content = lines[start_index].strip()

        # Pattern pour détecter une définition de fonction Python
        import re

        # Patterns possibles
        function_patterns = [
            rf'^\s*def\s+{re.escape(function_name)}\s*\(',  # def function_name(
            rf'^\s*async\s+def\s+{re.escape(function_name)}\s*\(',  # async def function_name(
        ]

        is_function_def = any(re.match(pattern, lines[start_index]) for pattern in function_patterns)

        if not is_function_def:
            logger.warning(f"⚠️ La ligne {start_line} ne semble pas être une définition de fonction")
            logger.debug(f"   Contenu: {line_content}")

            # ✅ FALLBACK : Chercher la fonction dans les lignes précédentes (max 10 lignes)
            for offset in range(1, min(11, start_index + 1)):
                check_index = start_index - offset
                check_line = lines[check_index]

                if any(re.match(pattern, check_line) for pattern in function_patterns):
                    logger.info(f"✅ Fonction trouvée {offset} lignes avant (ligne {check_index + 1})")
                    start_index = check_index
                    break

        # ✅ Déterminer l'indentation de base
        base_line = lines[start_index]
        base_indent = len(base_line) - len(base_line.lstrip())

        logger.info(f"📏 Indentation de base: {base_indent} espaces")

        # ✅ EXTRACTION : Lire jusqu'à la fin de la fonction
        function_lines = [lines[start_index]]
        current_index = start_index + 1

        # Variables pour suivre l'état
        in_docstring = False
        docstring_delimiter = None
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0

        # Compter les parenthèses dans la première ligne (signature)
        paren_depth = base_line.count('(') - base_line.count(')')

        while current_index < len(lines):
            line = lines[current_index]
            stripped = line.strip()

            # ✅ Ligne vide : continuer si on est dans la fonction
            if not stripped:
                if in_docstring or paren_depth > 0:
                    function_lines.append(line)
                    current_index += 1
                    continue
                else:
                    # Ligne vide après le corps : possiblement la fin
                    # Vérifier la ligne suivante
                    if current_index + 1 < len(lines):
                        next_line = lines[current_index + 1]
                        next_indent = len(next_line) - len(next_line.lstrip())

                        # Si la ligne suivante est au même niveau ou moins indentée : fin
                        if next_line.strip() and next_indent <= base_indent:
                            break
                        else:
                            # Sinon continuer (ligne vide dans le corps)
                            function_lines.append(line)
                            current_index += 1
                            continue
                    else:
                        break

            # ✅ Gestion des docstrings
            if '"""' in stripped or "'''" in stripped:
                delimiter = '"""' if '"""' in stripped else "'''"

                if not in_docstring:
                    in_docstring = True
                    docstring_delimiter = delimiter
                    function_lines.append(line)

                    # Vérifier si le docstring se ferme sur la même ligne
                    if stripped.count(delimiter) >= 2:
                        in_docstring = False
                        docstring_delimiter = None

                    current_index += 1
                    continue
                else:
                    # Fin du docstring
                    if delimiter == docstring_delimiter:
                        function_lines.append(line)
                        in_docstring = False
                        docstring_delimiter = None
                        current_index += 1
                        continue

            # Si on est dans un docstring, tout ajouter
            if in_docstring:
                function_lines.append(line)
                current_index += 1
                continue

            # ✅ Si on est encore dans la signature (parenthèses non fermées)
            if paren_depth > 0:
                function_lines.append(line)
                paren_depth += line.count('(') - line.count(')')
                current_index += 1
                continue

            # ✅ Calculer l'indentation de la ligne actuelle
            current_indent = len(line) - len(line.lstrip())

            # ✅ CONDITION D'ARRÊT : Ligne moins ou également indentée que la def
            if current_indent <= base_indent:
                # Exceptions : commentaires, lignes vides déjà gérées
                if stripped.startswith('#'):
                    function_lines.append(line)
                    current_index += 1
                    continue
                else:
                    # Fin de la fonction
                    logger.info(f"✅ Fin de fonction détectée à la ligne {current_index + 1}")
                    break

            # ✅ Ligne faisant partie du corps de la fonction
            function_lines.append(line)

            # ✅ Suivre les délimiteurs pour détecter les blocs imbriqués
            paren_depth += line.count('(') - line.count(')')
            bracket_depth += line.count('[') - line.count(']')
            brace_depth += line.count('{') - line.count('}')

            current_index += 1

            # ✅ Limite de sécurité (éviter boucle infinie)
            if len(function_lines) > 1000:
                logger.warning("⚠️ Fonction trop longue (>1000 lignes), arrêt")
                break

        # ✅ RÉSULTAT
        extracted_code = '\n'.join(function_lines)

        logger.info(f"✅ Code extrait : {len(function_lines)} lignes")
        logger.info(f"   Début: ligne {start_index + 1}")
        logger.info(f"   Fin: ligne {start_index + len(function_lines)}")

        return extracted_code

    def _validate_relations_format(self, relations_list: List[Dict]) -> List[Dict]:
        """
        ✅ NOUVELLE MÉTHODE : Valide et normalise le format des relations
        """
        if not relations_list:
            logger.warning("⚠️ Liste de relations vide")
            return []
    
        validated_relations = []
        issues_count = 0
    
        for i, rel in enumerate(relations_list):
            if not isinstance(rel, dict):
                logger.warning(f"⚠️ Relation {i} n'est pas un dictionnaire: {type(rel)}")
                issues_count += 1
                continue
            
            # Vérifier les champs obligatoires
            source = rel.get('source')
            target = rel.get('target')
            
            if not source or not target:
                logger.warning(f"⚠️ Relation {i} manque source ou target: {rel}")
                issues_count += 1
                continue
            
            # Normaliser la relation
            normalized_rel = {
                'source': self.normalize_node_name(str(source)),
                'target': self.normalize_node_name(str(target)),
                'relation_type': rel.get('relation_type') or rel.get('relationType', 'unknown'),
                'category': rel.get('category', 'custom'),
                'source_uid': rel.get('source_uid'),
                'target_uid': rel.get('target_uid'),
                'source_type': rel.get('source_type', 'unknown'),
                'target_type': rel.get('target_type', 'unknown')
            }
    
            # Vérifier que source != target
            if normalized_rel['source'] == normalized_rel['target']:
                logger.debug(f"⚠️ Relation auto-référentielle ignorée: {normalized_rel['source']}")
                continue
            
            validated_relations.append(normalized_rel)
    
        if issues_count > 0:
            logger.warning(f"⚠️ {issues_count} relations invalides ignorées sur {len(relations_list)}")
    
        logger.info(f"✅ Relations validées: {len(validated_relations)}/{len(relations_list)}")
        
        return validated_relations

    def _get_dgraph_to_local_mapping(self):
        """Retourne le mapping Dgraph UID -> Local UID."""
        if not self.dgraph_to_local:
            self._load_uid_mappings()
        return self.dgraph_to_local

    def _load_uid_mappings(self):
        """Charge les mappings UID depuis Dgraph avec cache."""
        cache_key = "uid_mappings"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            self.dgraph_to_local = cached_data.get('dgraph_to_local', {})
            self.local_to_dgraph = cached_data.get('local_to_dgraph', {})
            logger.info(f"Mappings UID chargés depuis cache: {len(self.dgraph_to_local)} entrées")
            return
        
        query = """
        {
          q(func: has(local_id)) {
            uid
            local_id
          }
        }
        """
        
        self._show_progress("Chargement des mappings UID...", 0)
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result:
            for node in result['q']:
                dgraph_uid = node.get('uid')
                local_id = node.get('local_id')
                
                if dgraph_uid and local_id:
                    self.dgraph_to_local[dgraph_uid] = local_id
                    self.local_to_dgraph[local_id] = dgraph_uid
            
            # Sauvegarder dans le cache
            self.query_cache.set(cache_key, {
                'dgraph_to_local': self.dgraph_to_local,
                'local_to_dgraph': self.local_to_dgraph
            })
        
        self._hide_progress()
        logger.info(f"Mappings UID chargés: {len(self.dgraph_to_local)} entrées")

    def _get_node_details(self, uid: str) -> Dict:
        """✅ Récupère les détails complets d'un nœud (avec enfants récursifs jusqu'à 3 niveaux)."""
        if not uid:
            return {}

        cache_key = f"node_details_{uid}"
        cached_data = self.query_cache.get(cache_key)
        if cached_data:
            return cached_data

        logger.info(f"🔎 Récupération des détails complets pour UID: {uid}")

        # ✅ Requête étendue : inclut path, sourcePath, full_path
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            level
            nodeType
            category
            description
            path
            sourcePath
            full_path

            outgoing_relations {{
              target_uid
              target_name
              relation_type
              category
              line
            }}

            incoming_relations {{
              source_uid
              source_name
              relation_type
              category
            }}

            relations

            parents {{
              uid
              name
              label
              nodeType
              level
              category
              path
              sourcePath
            }}

            # ✅ Enfants récursifs jusqu'à 3 niveaux
            children: ~parents {{
              uid
              name
              label
              nodeType
              level
              category
              path
              sourcePath

              children: ~parents {{
                uid
                name
                label
                nodeType
                level
                category
                path
                sourcePath

                children: ~parents {{
                  uid
                  name
                  label
                  nodeType
                  level
                  category
                  path
                  sourcePath
                }}
              }}
            }}

            clusters {{
              uid
              name
              path
            }}
          }}
        }}
        """

        try:
            result = self._execute_dgraph_query(query)
            if result and 'node' in result and result['node']:
                node = result['node'][0]

                # ✅ Nettoyage : filtrer les enfants sans nom
                def _clean_children(data):
                    if not data or not isinstance(data, list):
                        return []
                    cleaned = []
                    for c in data:
                        name = c.get('name') or c.get('label', '')
                        if not name or name.strip() == "":
                            continue
                        c['name'] = name.strip()
                        if 'children' in c:
                            c['children'] = _clean_children(c['children'])
                        cleaned.append(c)
                    return cleaned

                node['children'] = _clean_children(node.get('children', []))

                # ✅ Cache résultat
                self.query_cache.set(cache_key, node)
                logger.info(
                    f"✅ Nœud trouvé: {node.get('name', 'N/A')} "
                    f"avec {len(node.get('children', []))} enfants "
                    f"et {len(node.get('outgoing_relations', []))} relations sortantes"
                )
                return node

            logger.warning(f"⚠️  Aucun nœud trouvé pour UID: {uid}")
            return {}

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du nœud {uid}: {e}")
            import traceback
            traceback.print_exc()
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
        
        self._show_progress("Chargement des relations globales...", 20)
        
        # 1. Relations via type Relation
        query = """
        {
          allRelations(func: type(Relation)) {
            uid
            name
            relationType
            source {
              uid
              name
              label
              local_id
            }
            target {
              uid
              name
              label
              local_id
            }
          }
        }
        """
        
        self._update_progress(40, "Traitement des relations custom...")
        result = self._execute_dgraph_query(query)
        
        if result and 'allRelations' in result:
            logger.info(f"Found {len(result['allRelations'])} relations of type(Relation)")
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
                        'category': 'custom',
                        'is_analyzed': False
                    })
        
        # 2. Relations hiérarchiques
        self._update_progress(70, "Traitement des relations hiérarchiques...")
        hierarchy_query = """
        {
          allLabels(func: type(Label)) {
            uid
            name
            label
            local_id
            parents {
              uid
              name
              label
              local_id
            }
            children: ~parents {
              uid
              name
              label
              local_id
            }
          }
        }
        """
        
        hierarchy_result = self._execute_dgraph_query(hierarchy_query)
        
        if hierarchy_result and 'allLabels' in hierarchy_result:
            for node in hierarchy_result['allLabels']:
                node_name = self.normalize_node_name(node.get('name') or node.get('label', ''))
                
                if not node_name:
                    continue
                
                for parent in node.get('parents', []):
                    parent_name = self.normalize_node_name(parent.get('name') or parent.get('label', ''))
                    if parent_name:
                        relations_list.append({
                            'source': parent_name,
                            'target': node_name,
                            'relation_type': 'parent',
                            'category': 'hierarchy',
                            'is_analyzed': False
                        })
                
                for child in node.get('children', []):
                    child_name = self.normalize_node_name(child.get('name') or child.get('label', ''))
                    if child_name:
                        relations_list.append({
                            'source': node_name,
                            'target': child_name,
                            'relation_type': 'child',
                            'category': 'hierarchy',
                            'is_analyzed': False
                        })
        
        self._update_progress(100, "Finalisation...")
        self.query_cache.set(cache_key, relations_list)
        self._hide_progress()
        
        logger.info(f"Relations globales récupérées: {len(relations_list)}")
        return relations_list

    def _get_level_1_relations(self, uid: str) -> List[Dict]:
        """✅ CORRIGÉ : Récupère les relations niveau 1 avec tri hiérarchiques/externes"""
        if not uid or not self.current_central_name:
            return []

        cache_key = f"level1_{uid}"
        cached_data = self.query_cache.get(cache_key)

        if cached_data:
            return cached_data

        relations = []
        dgraph_to_local = self._get_dgraph_to_local_mapping()

        self._show_progress(f"Chargement relations niveau 1...", 10)

        node_details = self._get_node_details(uid)

        if not node_details:
            self._hide_progress()
            return []

        central_name = self.current_central_name

        # ========== RELATIONS SORTANTES ==========
        self._update_progress(30, "Relations sortantes...")
        try:
            for rel in node_details.get('outgoing_relations', []):
                target_uid = rel.get('target_uid', '')

                if target_uid.startswith('0x'):
                    target_uid = dgraph_to_local.get(target_uid, target_uid)

                if target_uid.startswith('temp_'):
                    continue
                
                target_name = rel.get('target_name', '')
                if not target_name or target_name.strip() == '':
                    target_name = self._get_node_name_by_uid(target_uid)

                target_name = self.normalize_node_name(target_name)

                if target_name:
                    relations.append({
                        'source': central_name,
                        'target': target_name,
                        'relation_type': rel.get('relation_type', 'relation'),
                        'category': rel.get('category', 'custom'),
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement outgoing_relations: {e}")

        # ========== RELATIONS PARSÉES (JSON) ==========
        self._update_progress(50, "Relations parsées...")
        try:
            relations_json = node_details.get('relations', '{}')
            if isinstance(relations_json, str):
                parsed_relations = json.loads(relations_json) if relations_json else {}
            else:
                parsed_relations = relations_json or {}

            for rel_type, rel_list in parsed_relations.items():
                if not isinstance(rel_list, list):
                    continue

                for rel in rel_list:
                    target_name = self.normalize_node_name(rel.get('target', ''))
                    if target_name:
                        relations.append({
                            'source': central_name,
                            'target': target_name,
                            'relation_type': rel_type,
                            'category': 'parsed',
                            'is_analyzed': True,
                            'line': rel.get('line', 0)
                        })
        except Exception as e:
            logger.warning(f"Erreur parsing relations JSON: {e}")

        # ========== RELATIONS ENTRANTES ==========
        self._update_progress(70, "Relations entrantes...")
        try:
            for rel in node_details.get('incoming_relations', []):
                source_uid = rel.get('source_uid', '')

                if source_uid.startswith('0x'):
                    source_uid = dgraph_to_local.get(source_uid, source_uid)

                if source_uid.startswith('temp_'):
                    continue
                
                source_name = rel.get('source_name', '')
                if not source_name or source_name.strip() == '':
                    source_name = self._get_node_name_by_uid(source_uid)

                source_name = self.normalize_node_name(source_name)

                if source_name:
                    relations.append({
                        'source': source_name,
                        'target': central_name,
                        'relation_type': rel.get('relation_type', 'relation'),
                        'category': rel.get('category', 'custom'),
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement incoming_relations: {e}")

        # ========== HIÉRARCHIE (PARENTS) ==========
        self._update_progress(80, "Hiérarchie...")
        try:
            for parent in node_details.get('parents', []):
                parent_name = self.normalize_node_name(parent.get('name') or parent.get('label', ''))
                if parent_name:
                    relations.append({
                        'source': parent_name,
                        'target': central_name,
                        'relation_type': 'parent',
                        'category': 'hierarchy',
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement parents: {e}")

        # ========== HIÉRARCHIE (CHILDREN) ==========
        try:
            for child in node_details.get('children', []):
                child_name = self.normalize_node_name(child.get('name') or child.get('label', ''))
                if child_name:
                    relations.append({
                        'source': central_name,
                        'target': child_name,
                        'relation_type': 'child',
                        'category': 'hierarchy',
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement children: {e}")

        # ========== RELATIONS TYPE RELATION ==========
        self._update_progress(90, "Relations additionnelles...")
        try:
            relation_type_relations = self._get_relation_type_relations(uid)

            # Fusionner en évitant les doublons
            existing_keys = set()
            for rel in relations:
                key = (
                    rel.get('source'),
                    rel.get('target'),
                    rel.get('relation_type')
                )
                existing_keys.add(key)

            added_count = 0
            for rel in relation_type_relations:
                key = (
                    rel.get('source'),
                    rel.get('target'),
                    rel.get('relation_type')
                )

                if key not in existing_keys:
                    relations.append(rel)
                    existing_keys.add(key)
                    added_count += 1

            logger.info(f"  🔗 Relations type Relation: {len(relation_type_relations)} récupérées, {added_count} ajoutées")

        except Exception as e:
            logger.error(f"❌ Erreur récupération relations type Relation: {e}")
            import traceback
            traceback.print_exc()

        # ✅ NOUVEAU : TRI DES RELATIONS (hiérarchiques à gauche, externes à droite)
        def sort_relations(relations_list):
            """Tri les relations : hiérarchiques d'abord, puis externes"""
            hierarchical = []
            external = []

            for rel in relations_list:
                rel_type = rel.get('relation_type', '').lower()
                category = rel.get('category', '').lower()

                # Critères hiérarchiques
                is_hierarchical = (
                    rel_type in ['parent', 'child', 'contains', 'belongs_to'] or
                    category in ['hierarchy', 'internal']
                )

                if is_hierarchical:
                    hierarchical.append(rel)
                else:
                    external.append(rel)

            # Retourner hiérarchiques d'abord, puis externes
            return hierarchical + external

        # ✅ Appliquer le tri
        relations = sort_relations(relations)

        # Sauvegarder dans le cache
        self.query_cache.set(cache_key, relations)
        self._hide_progress()

        # Log du résultat
        hierarchical_count = sum(1 for r in relations if r.get('category') in ['hierarchy', 'internal'])
        external_count = len(relations) - hierarchical_count

        logger.info(f"Niveau 1: {len(relations)} relations trouvées pour {central_name}")
        logger.info(f"  📊 {hierarchical_count} hiérarchiques (à gauche), {external_count} externes (à droite)")

        return relations
    
    def _get_relation_type_relations(self, uid: str) -> List[Dict]:
        if not uid or not self.dgraph_connector:
            logger.error("❌ Pas d'UID ou pas de connecteur")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 RÉCUPÉRATION RELATIONS TYPE RELATION")
        logger.info(f"  UID central: {uid}")
        logger.info(f"{'='*70}")

        node_query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            path
            label
            id
          }}
        }}
        """

        node_result = self._execute_dgraph_query(node_query)

        if not node_result or 'node' not in node_result or not node_result['node']:
            logger.error(f"❌ Nœud {uid} introuvable")
            return []

        node_data = node_result['node'][0]
        node_name = node_data.get('name', '')
        node_path = node_data.get('path', '')

        search_variants = set()

        if node_name:
            search_variants.add(node_name)
            search_variants.add(os.path.basename(node_name))
            name_no_ext = os.path.splitext(node_name)[0]
            search_variants.add(name_no_ext)
            search_variants.add(os.path.basename(name_no_ext))

        if node_path:
            search_variants.add(node_path)
            search_variants.add(os.path.basename(node_path))

        search_variants = {v for v in search_variants if v and v.strip()}

        logger.info(f"🔍 Identifiants à rechercher:")
        for variant in sorted(search_variants):
            logger.info(f"   • {variant}")

        if not search_variants:
            logger.error("❌ Aucun identifiant valide")
            return []
        
        relations_by_uid = []
        relations_by_name = []

        query_by_uid = f"""
        {{
          relations_out(func: type(Relation)) @filter(uid_in(source, {uid})) {{
            uid
            relationType
            category
            line
            intraFile
            sourceName
            sourceDescription
            sourcePath
            sourceType
            targetName
            targetDescription
            targetPath
            targetType
            source {{ uid name path label nodeType }}
            target {{ uid name path label nodeType }}
          }}

          relations_in(func: type(Relation)) @filter(uid_in(target, {uid})) {{
            uid
            relationType
            category
            line
            intraFile
            sourceName
            sourceDescription
            sourcePath
            sourceType
            targetName
            targetDescription
            targetPath
            targetType
            source {{ uid name path label nodeType }}
            target {{ uid name path label nodeType }}
          }}
        }}
        """

        result_uid = self._execute_dgraph_query(query_by_uid)

        if result_uid:
            relations_by_uid = (result_uid.get('relations_out', []) + 
                               result_uid.get('relations_in', []))

        logger.info(f"🎯 Mode UID: {len(relations_by_uid)} relations trouvées")

        for variant in search_variants:
            escaped = variant.replace('"', '\\"')

            query_by_name = f"""
            {{
              by_source_name(func: type(Relation)) @filter(
                eq(sourceName, "{escaped}") OR eq(sourcePath, "{escaped}")
              ) {{
                uid
                relationType
                category
                line
                intraFile
                sourceName
                sourceDescription
                sourcePath
                sourceType
                targetName
                targetDescription
                targetPath
                targetType
                source {{ uid name path label nodeType }}
                target {{ uid name path label nodeType }}
              }}

              by_target_name(func: type(Relation)) @filter(
                eq(targetName, "{escaped}") OR eq(targetPath, "{escaped}")
              ) {{
                uid
                relationType
                category
                line
                intraFile
                sourceName
                sourceDescription
                sourcePath
                sourceType
                targetName
                targetDescription
                targetPath
                targetType
                source {{ uid name path label nodeType }}
                target {{ uid name path label nodeType }}
              }}
            }}
            """

            result_name = self._execute_dgraph_query(query_by_name)

            if result_name:
                found = (result_name.get('by_source_name', []) + 
                        result_name.get('by_target_name', []))
                relations_by_name.extend(found)

        logger.info(f"🎯 Mode Nom/Path: {len(relations_by_name)} relations trouvées")

        all_raw_relations = relations_by_uid + relations_by_name

        seen_uids = set()
        unique_raw_relations = []

        for rel in all_raw_relations:
            rel_uid = rel.get('uid')
            if rel_uid and rel_uid not in seen_uids:
                seen_uids.add(rel_uid)
                unique_raw_relations.append(rel)

        logger.info(f"📦 {len(unique_raw_relations)} relations uniques après déduplication")

        relations_list = []
        seen_keys = set()

        for rel in unique_raw_relations:
            # Extraction source
            source_node = rel.get('source', {})
            source_uid_rel = source_node.get('uid') if source_node else None
            source_name = (
                source_node.get('name') if source_node else None
            ) or rel.get('sourceName') or rel.get('sourcePath', '')

            # Extraction target
            target_node = rel.get('target', {})
            target_uid_rel = target_node.get('uid') if target_node else None
            target_name = (
                target_node.get('name') if target_node else None
            ) or rel.get('targetName') or rel.get('targetPath', '')

            # Validation pertinence
            is_source_match = False
            is_target_match = False

            if source_uid_rel == uid:
                is_source_match = True
            else:
                source_basename = os.path.basename(source_name) if source_name else ''
                source_no_ext = os.path.splitext(source_basename)[0]
                if source_basename in search_variants or source_no_ext in search_variants:
                    is_source_match = True

            if target_uid_rel == uid:
                is_target_match = True
            else:
                target_basename = os.path.basename(target_name) if target_name else ''
                target_no_ext = os.path.splitext(target_basename)[0]
                if target_basename in search_variants or target_no_ext in search_variants:
                    is_target_match = True

            if not (is_source_match or is_target_match):
                continue
            
            # Normalisation noms
            source_name_norm = os.path.basename(source_name).strip() if source_name else ''
            target_name_norm = os.path.basename(target_name).strip() if target_name else ''

            if not source_name_norm or not target_name_norm:
                continue

            # Ignorer auto-références
            if source_name_norm == target_name_norm:
                continue
            
            # Déduplication
            relation_type = rel.get('relationType', 'relation')
            unique_key = (
                source_uid_rel or source_name_norm,
                target_uid_rel or target_name_norm,
                relation_type
            )

            if unique_key in seen_keys:
                continue
            
            seen_keys.add(unique_key)

            # Créer la relation
            relations_list.append({
                'source': source_name_norm,
                'source_uid': source_uid_rel or uid,
                'source_type': rel.get('sourceType', 'file'),
                'target': target_name_norm,
                'target_uid': target_uid_rel or uid,
                'target_type': rel.get('targetType', 'file'),
                'relation_type': relation_type,
                'category': rel.get('category', 'external'),
                'line': rel.get('line'),
                'intraFile': rel.get('intraFile', False)
            })

        logger.info(f"✅ {len(relations_list)} relations finales validées")
        logger.info(f"{'='*70}\n")

        return relations_list

    def _get_node_name_by_uid(self, uid: str) -> str:
        """Récupère le nom d'un nœud par son UID avec cache."""
        if not uid:
            return ""
        
        cache_key = f"node_name_{uid}"
        cached_name = self.query_cache.get(cache_key)
        
        if cached_name:
            return cached_name
        
        # Correction des requêtes pour utiliser les fonctions correctes
        # Essayer d'abord avec uid()
        query = f"""
        {{
          q(func: uid({uid})) {{
            name
            label
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result and result['q']:
            node = result['q'][0]
            name = node.get('name') or node.get('label', '')
            self.query_cache.set(cache_key, name)
            return name
        
        return ""

    def _get_node_uid_by_name(self, node_name: str) -> str:
        """Récupère l'UID d'un nœud par son nom avec cache (CORRIGÉ)."""
        if not node_name:
            return None

        cache_key = f"uid_by_name_{node_name}"
        cached_uid = self.query_cache.get(cache_key)
        
        if cached_uid:
            return cached_uid

        # Utiliser uid() au lieu de eq() qui nécessite un index
        query = f"""
        {{
          q(func: has(name)) @filter(eq(name, "{node_name}")) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid

        # Essayer avec le label
        query = f"""
        {{
          q(func: has(label)) @filter(eq(label, "{node_name}")) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid

        logger.warning(f"UID non trouvé pour: {node_name}")
        return None

    def _on_level_changed(self, index):
        """✅ CORRIGÉ : Navigation cohérente avec exploration progressive."""
        level = self.level_combo.itemData(index)

        if level == 0:
            if not self.current_project_data:
                if self.project_combo.count() > 1:
                    self.project_combo.setCurrentIndex(1)
                    return
                else:
                    self._show_empty_graph("Sélectionnez un projet")
                    return

            self._show_project_cluster_view()

        elif level == 1:  # Relations directes d'un nœud
            if not self.current_central_uid:
                self._show_empty_graph("Sélectionnez un nœud dans l'arbre")
                return

            # ✅ Si déjà dans une vue fichier/cluster, utiliser ça
            if hasattr(self, 'graph_data') and self.graph_data.get('is_file_list_view'):
                # Déjà dans la vue fichiers, ne rien faire
                return

            # Sinon, charger les relations du nœud sélectionné
            relations_list = self._get_level_1_relations(self.current_central_uid)
            self.current_relations = relations_list
            self.hidden_relations.clear()
            self.figure.clear()

            G = self._build_clean_graph(relations_list)
            self.current_graph = G
            self._draw_graph(G)

            self._update_status(f"Relations directes : {len(relations_list)} relations affichées")

    def _show_project_cluster_view(self):
        """✅ Affiche le projet central avec ses clusters - DESIGN AMÉLIORÉ"""
        clusters = self._get_clusters_data()

        if not clusters:
            self._show_empty_graph("Aucun cluster disponible")
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Créer un graphe avec le projet au centre
        G = nx.DiGraph()

        # Nœud projet central
        project_uid = self.current_project_data.get('uid', 'project_root')
        project_name = self.current_project_data.get('name', 'Projet')

        G.add_node(
            project_uid,
            node_type='project',
            display_name=project_name
        )

        # Statistiques par cluster
        cluster_stats = {}

        for cluster in clusters:
            cluster_uid = cluster.get('uid', f"cluster_{uuid.uuid4()}")
            cluster_name = cluster.get('name', 'Cluster sans nom')

            # Compter les éléments
            root_labels = cluster.get('root_labels', [])
            total_elements = self._count_total_elements(root_labels)
            total_files = len(root_labels)

            cluster_stats[cluster_uid] = {
                'cluster_name': cluster_name,
                'files': total_files,
                'total_elements': total_elements,
                'root_labels': root_labels
            }

            G.add_node(
                cluster_uid,
                node_type='cluster',
                display_name=cluster_name,
                files=total_files,
                total_elements=total_elements
            )

            # Relation hiérarchique Projet → Cluster
            G.add_edge(
                project_uid,
                cluster_uid,
                relation_type='contains',
                color='#4A90E2',
                label='contient'
            )

        # Ajouter les relations inter-clusters
        self._add_inter_cluster_relations(G, clusters, cluster_stats)

        # Layout radial centré sur le projet
        pos = self._compute_radial_layout(G, project_uid, len(clusters))

        # ✅ AMÉLIORATION : Dessiner les arêtes avec style uniforme
        for u, v, data in G.edges(data=True):
            rel_type = data.get('relation_type', 'relation')
            color = data.get('color', '#95A5A6')

            if rel_type == 'contains':
                # Liens hiérarchiques : épais et bleus
                nx.draw_networkx_edges(
                    G, pos, [(u, v)], ax=ax,
                    edge_color=color,
                    width=3.0,
                    alpha=0.7,
                    arrows=True,
                    arrowsize=15,
                    connectionstyle='arc3,rad=0.05'
                )
            else:
                # Relations inter-clusters : fins et gris
                nx.draw_networkx_edges(
                    G, pos, [(u, v)], ax=ax,
                    edge_color=color,
                    width=1.5,
                    alpha=0.4,
                    arrows=True,
                    arrowsize=10,
                    connectionstyle='arc3,rad=0.15',
                    style='dashed'
                )

        # ✅ AMÉLIORATION : Dessiner les nœuds avec style uniforme
        from matplotlib.patches import FancyBboxPatch

        for node in G.nodes():
            x, y = pos[node]
            node_data = G.nodes[node]
            node_type = node_data.get('node_type')

            if node_type == 'project':
                # ✅ PROJET : Rectangle arrondi rouge (dimensions fixes)
                formatted_name = self._format_node_display_name(project_name, 'project')
                display_name = formatted_name[:20] + '..' if len(formatted_name) > 20 else formatted_name

                rect = FancyBboxPatch(
                    (x - 3.5, y - 1.0),  # ✅ Dimensions fixes : 7.0 x 2.0
                    7.0, 2.0,
                    boxstyle="round,pad=0.2",
                    edgecolor='#999999',
                    facecolor=self.primary_color,
                    alpha=0.95,
                    linewidth=3.0,
                    zorder=5
                )
                ax.add_patch(rect)

                ax.text(
                    x, y, display_name,
                    ha='center', va='center',
                    fontsize=11,
                    fontweight='bold',
                    color='white',
                    zorder=6
                )

            elif node_type == 'cluster':
                stats = cluster_stats.get(node, {})
                display_name = stats.get('cluster_name', 'Cluster')
                formatted_name = self._format_node_display_name(stats.get('cluster_name', 'Cluster'), 'cluster')
                isplay_name = formatted_name[:18] + '..' if len(formatted_name) > 18 else formatted_name

                width = 6.0
                height = 1.8

                rect = FancyBboxPatch(
                    (x - width/2, y - height/2),
                    width, height,
                    boxstyle="round,pad=0.2",
                    edgecolor='#999999',
                    facecolor='#5CAD56',
                    alpha=0.95,
                    linewidth=2.5,
                    zorder=2
                )
                ax.add_patch(rect)

                ax.text(
                    x, y + 0.35,
                    display_name,
                    ha='center', va='center',
                    fontsize=9,
                    fontweight='bold',
                    color='white',
                    zorder=3
                )
                
                # ✅ CORRECTION : Statistiques en format HORIZONTAL
                files_count = stats.get('files', 0)
                stats_text = f"{files_count} fichiers  -  {total_elements} éléments"  # Format horizontal avec séparateur
                ax.text(
                    x, y - 0.35,
                    stats_text,
                    ha='center', va='center',
                    fontsize=7.5,
                    color='white',
                    alpha=1.0,
                    fontweight='600',  # Légèrement réduit pour meilleure lisibilité
                    zorder=3
                )

        ax.axis('off')

        # Marges adaptatives
        x_coords = [pos[n][0] for n in G.nodes()]
        y_coords = [pos[n][1] for n in G.nodes()]

        margin = 4.0
        ax.set_xlim(min(x_coords) - margin, max(x_coords) + margin)
        ax.set_ylim(min(y_coords) - margin, max(y_coords) + margin)

        # ✅ AMÉLIORATION : Instructions avec meilleur contraste
        ax.text(
            0.5, 0.02,
            "💡 Double-cliquez sur un cluster pour explorer les nœuds",
            transform=ax.transAxes,
            ha='center', va='bottom',
            fontsize=9,
            style='italic',
            color='#555555',
            bbox=dict(
                boxstyle='round,pad=0.5', 
                facecolor='#FFFFFF', 
                edgecolor='#CCCCCC',
                alpha=0.95,
                linewidth=1.5
            )
        )

        # Configuration interactive pour navigation
        self._setup_cluster_navigation_enhanced(ax, G, pos, cluster_stats)

        # Sauvegarder données pour navigation
        self.graph_data = {
            'pos': {node: list(coord) for node, coord in pos.items()},
            'G': G,
            'ax': ax,
            'cluster_stats': cluster_stats,
            'is_cluster_view': True
        }

        self.canvas.draw()
        self._update_status(f"Vue projet : {len(clusters)} clusters")

    def _setup_cluster_navigation_enhanced(self, ax, G, pos, cluster_stats):
        """✅ Navigation interactive : double-clic = explorer cluster (fichiers)."""

        def on_cluster_click(event):
            if event.inaxes != ax or event.xdata is None:
                return

            # Trouver le nœud cliqué
            clicked_node = None
            for node, coords in pos.items():
                x, y = coords
                dist = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5

                node_data = G.nodes[node]
                if node_data.get('node_type') == 'project':
                    threshold = 2.5
                else:
                    threshold = 2.0

                if dist < threshold:
                    clicked_node = node
                    break
                
            if clicked_node:
                node_type = G.nodes[clicked_node].get('node_type')

                if event.dblclick:  # Double-clic
                    if node_type == 'cluster':
                        # ✅ Explorer le cluster (afficher fichiers)
                        self._explore_cluster_relations(clicked_node, cluster_stats[clicked_node])
                    elif node_type == 'project':
                        # Déjà dans la vue projet
                        pass
                    
                elif event.button == 3:  # Clic droit
                    self._show_node_context_menu(clicked_node, node_type, cluster_stats)

        self.canvas.mpl_connect('button_press_event', on_cluster_click)

    def _show_node_context_menu(self, node_uid, node_type, cluster_stats):
        """Menu contextuel clic droit."""
        if node_type == 'cluster':
            stats = cluster_stats.get(node_uid, {})
            details = f"""
            <h3>📦 {stats.get('cluster_name', 'Cluster')}</h3>
            <p><b>Fichiers :</b> {stats.get('files', 0)}</p>
            <p><b>Éléments totaux :</b> {stats.get('total_elements', 0)}</p>
            <br>
            <p><i>Double-cliquez pour explorer les relations</i></p>
            """
        else:
            details = "<p>Projet racine</p>"

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Détails")
        msg.setTextFormat(Qt.RichText)
        msg.setText(details)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.exec_()

    def _explore_cluster_relations(self, cluster_uid, cluster_info):
        cluster_name = cluster_info.get('cluster_name', 'Cluster')
        logger.info(f"\n{'='*70}")
        logger.info(f"📂 EXPLORATION DU CLUSTER : {cluster_name}")
        logger.info(f"{'='*70}")
        self.current_central_uid = cluster_uid
        self.current_central_name = cluster_name

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # ✅ Récupérer TOUS les fichiers (récursif)
        all_files = self._get_all_files_in_cluster_recursive(cluster_info)

        if not all_files:
            ax.text(0.5, 0.5, f"Cluster vide\n'{cluster_name}'", 
                   ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        logger.info(f"\n📊 AFFICHAGE DE {len(all_files)} FICHIERS")

        # ✅ VALIDATION : Vérifier qu'on n'a que des fichiers
        valid_files = []
        for file_data in all_files:
            file_name = file_data.get('name') or file_data.get('label', '')
            file_type = file_data.get('nodeType', '')

            # ✅ FILTRE STRICT : uniquement les vrais fichiers
            if file_type in ['class', 'function', 'method', 'variable']:
                logger.warning(f"  ⚠️ Ignoré (type={file_type}): {file_name}")
                continue
            
            if not self._has_extension(file_name):
                # Si pas d'extension, vérifier que c'est bien un fichier
                if not (file_data.get('fileContents') or file_data.get('files')):
                    logger.debug(f"  ⏩ Ignoré (pas fichier): {file_name}")
                    continue
                
            valid_files.append(file_data)
            logger.info(f"  ✅ Fichier valide: {file_name}")

        if not valid_files:
            ax.text(0.5, 0.5, f"Aucun fichier dans le cluster\n'{cluster_name}'", 
                   ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        logger.info(f"\n✅ {len(valid_files)} fichiers valides affichés")

        # ✅ Créer un graphe hiérarchique : cluster → fichiers
        G = nx.DiGraph()

        # Nœud cluster central
        G.add_node(
            cluster_uid,
            node_type='cluster_center',
            display_name=cluster_name
        )

        # Ajouter chaque fichier comme nœud enfant
        files_metadata = {}  # Stockage séparé des métadonnées

        for file_data in valid_files:
            file_name = self.normalize_node_name(
                file_data.get('name') or file_data.get('label', '')
            )
            file_uid = file_data.get('uid')

            if not file_name or not file_uid:
                continue

            G.add_node(
                file_uid,
                node_type='file',
                display_name=file_name
            )

            # Stocker les métadonnées séparément
            files_metadata[file_uid] = file_data

            # Lien hiérarchique cluster → fichier
            G.add_edge(
                cluster_uid,
                file_uid,
                relation_type='contains',
                color='#4A90E2'
            )

        # ✅ Layout radial : cluster au centre
        pos = self._compute_radial_layout(G, cluster_uid, len(valid_files))

        # ✅ AMÉLIORATION DESIGN : Dessiner les arêtes avec style moderne
        nx.draw_networkx_edges(
            G, pos, ax=ax,
            edge_color='#4A90E2',
            width=2.5,
            alpha=0.7,
            arrows=True,
            arrowsize=14,
            connectionstyle='arc3,rad=0.1'
        )

        # ✅ AMÉLIORATION DESIGN : Dessiner les nœuds avec style uniforme
        from matplotlib.patches import FancyBboxPatch

        for node in G.nodes():
            x, y = pos[node]
            node_data = G.nodes[node]
            node_type = node_data.get('node_type')

            if node_type == 'cluster_center':
                # ✅ CLUSTER : Rectangle arrondi rouge (style uniforme)
                formatted_name = self._format_node_display_name(cluster_name, 'cluster')
                display_name = formatted_name[:20] + '..' if len(formatted_name) > 20 else formatted_name

                rect = FancyBboxPatch(
                    (x - 2.5, y - 1.0),
                    5.0, 2.0,
                    boxstyle="round,pad=0.2",
                    edgecolor='#999999',
                    facecolor=self.primary_color,  # Rouge #A23B2D
                    alpha=0.95,
                    linewidth=3.0,
                    zorder=5
                )
                ax.add_patch(rect)

                ax.text(
                    x, y, display_name,
                    ha='center', va='center',
                    fontsize=11,
                    fontweight='bold',
                    color='white',
                    zorder=6
                )

            elif node_type == 'file':
                # ✅ FICHIER : Rectangle arrondi vert (MÊME STYLE que cluster)
                display_name = node_data.get('display_name', 'Fichier')
                node_type = 'file' if self._has_extension(node_data.get('display_name', '')) else 'folder'
                formatted_name = self._format_node_display_name(node_data.get('display_name', 'Fichier'), node_type)
                display_name = formatted_name[:22] + '..' if len(formatted_name) > 22 else formatted_name

                # Dimensions uniformes avec les relations directes
                rect = FancyBboxPatch(
                    (x - 1.75, y - 0.5),
                    3.5, 1.0,
                    boxstyle="round,pad=0.15",
                    edgecolor='#999999',
                    facecolor='#5CAD56',  # Vert pour fichiers
                    alpha=0.95,
                    linewidth=2.5,
                    zorder=2
                )
                ax.add_patch(rect)

                ax.text(
                    x, y, display_name,
                    ha='center', va='center',
                    fontsize=9,
                    fontweight='bold',
                    color='white',
                    zorder=3
                )

        ax.axis('off')

        # Marges
        x_coords = [pos[n][0] for n in G.nodes()]
        y_coords = [pos[n][1] for n in G.nodes()]
        margin = 3.0
        ax.set_xlim(min(x_coords) - margin, max(x_coords) + margin)
        ax.set_ylim(min(y_coords) - margin, max(y_coords) + margin)

        # ✅ AMÉLIORATION DESIGN : Titre avec style moderne
        ax.text(
            0.5, 0.98,
            f"📦 Cluster : {cluster_name} ({len(valid_files)} fichiers)",
            transform=ax.transAxes,
            ha='center', va='top',
            fontsize=12,
            fontweight='bold',
            color='#2C2C2C',
            bbox=dict(
                boxstyle='round,pad=0.5', 
                facecolor='#E8F4F8', 
                edgecolor='#4A90E2', 
                linewidth=2,
                alpha=0.95
            )
        )

        # ✅ AMÉLIORATION DESIGN : Instructions avec meilleur contraste
        ax.text(
            0.5, 0.02,
            "💡 Double-cliquez sur un fichier pour voir ses dépendances externes",
            transform=ax.transAxes,
            ha='center', va='bottom',
            fontsize=9,
            style='italic',
            color='#555555',
            bbox=dict(
                boxstyle='round,pad=0.4',
                facecolor='#FFFFFF',
                edgecolor='#CCCCCC',
                alpha=0.9
            )
        )

        # ✅ Configuration interactive avec métadonnées stockées
        self._setup_file_exploration_navigation(ax, G, pos, files_metadata)

        # Sauvegarder pour navigation
        self.graph_data = {
            'pos': {node: list(coord) for node, coord in pos.items()},
            'G': G,
            'ax': ax,
            'is_file_list_view': True,
            'cluster_name': cluster_name,
            'cluster_uid': cluster_uid,
            'files_metadata': files_metadata  # ✅ Métadonnées séparées
        }

        self.canvas.draw()
        self._update_status(f"Cluster '{cluster_name}' : {len(valid_files)} fichiers")

    def _setup_file_exploration_navigation(self, ax, G, pos, files_metadata):

        def on_file_click(event):
            if event.inaxes != ax or event.xdata is None:
                return

            # Trouver le nœud cliqué
            clicked_node = None
            for node, coords in pos.items():
                x, y = coords
                dist = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5

                node_type = G.nodes[node].get('node_type')
                threshold = 2.0 if node_type == 'cluster_center' else 2.5

                if dist < threshold:
                    clicked_node = node
                    break

            if clicked_node and event.dblclick:  # Double-clic
                node_type = G.nodes[clicked_node].get('node_type')

                if node_type == 'file':
                    # ✅ Récupérer les métadonnées depuis le stockage séparé
                    file_data = files_metadata.get(clicked_node)

                    if not file_data:
                        logger.error(f"❌ Métadonnées introuvables pour {clicked_node}")
                        return

                    file_name = file_data.get('name') or file_data.get('label', '')
                    file_uid = file_data.get('uid')

                    logger.info(f"🔎 Chargement relations pour: {file_name}")
                    logger.info(f"📦 État actuel AVANT navigation:")
                    logger.info(f"   - current_central_uid: {self.current_central_uid}")
                    logger.info(f"   - current_central_name: {self.current_central_name}")
                    logger.info(f"   - graph_data cluster_uid: {self.graph_data.get('cluster_uid') if hasattr(self, 'graph_data') else 'N/A'}")

                    self._show_file_dependencies(file_uid, file_name, file_data)

                elif node_type == 'cluster_center':
                    # Retour à la vue clusters
                    logger.info("🔙 Retour vue clusters")
                    self._on_level_changed(0)

        self.canvas.mpl_connect('button_press_event', on_file_click)

    def _show_file_dependencies(self, file_uid, file_name, file_data):
        """
        ✅ CORRIGÉ : Affiche les relations/dépendances EXTERNES d'un fichier
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📄 DÉPENDANCES DU FICHIER: {file_name}")
        logger.info(f"{'='*70}")

        # ✅ Sauvegarder dans l'historique AVANT de changer d'état
        if self.current_central_uid and self.current_central_name:
            # Déterminer le type de vue actuelle
            current_view_type = 'relations'
            cluster_uid_to_save = None
            cluster_name_to_save = None

            if hasattr(self, 'graph_data') and self.graph_data:
                if self.graph_data.get('is_file_list_view'):
                    current_view_type = 'file_list'
                    cluster_uid_to_save = self.graph_data.get('cluster_uid')
                    cluster_name_to_save = self.graph_data.get('cluster_name')
                elif self.graph_data.get('is_cluster_view'):
                    current_view_type = 'cluster'

            logger.info(f"💾 Sauvegarde état fichier: {self.current_central_name} (type={current_view_type})")

            self.navigation_history.append({
                'uid': self.current_central_uid,
                'name': self.current_central_name,
                'relations': self.current_relations.copy() if self.current_relations else [],
                'view_type': current_view_type,
                'cluster_uid': cluster_uid_to_save,
                'cluster_name': cluster_name_to_save
            })

            if len(self.navigation_history) > 10:
                self.navigation_history.pop(0)

            self.back_btn.setEnabled(True)
            logger.info(f"✅ Historique fichier: {len(self.navigation_history)} états")

        # Mettre à jour le contexte
        self.current_central_uid = file_uid
        self.current_central_name = file_name

        # Afficher chargement
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')
        ax.text(0.5, 0.5, f"Chargement des dépendances\nde '{file_name}'...", 
               ha='center', va='center', 
               color='#666666', fontsize=12)
        ax.axis('off')
        self.canvas.draw()
        QtWidgets.QApplication.processEvents()

        # ✅ Récupérer les relations (utilise la méthode existante)
        relations_list = self._get_level_1_relations(file_uid)

        if not relations_list:
            self._show_empty_graph(f"Aucune dépendance externe\npour '{file_name}'")
            return

        # ✅ CORRECTION : Forcer level_combo à "Relations directes" pour style uniforme
        self.level_combo.blockSignals(True)
        self.level_combo.setCurrentIndex(1)  # Index 1 = Relations directes
        self.level_combo.blockSignals(False)

        # Construire et afficher le graphe avec style uniforme
        self.current_relations = relations_list
        self.hidden_relations.clear()
        self.figure.clear()

        G = self._build_clean_graph(relations_list)
        self.current_graph = G

        # ✅ Le style sera automatiquement uniforme via _draw_graph()
        # car level_combo.currentIndex() == 1
        self._draw_graph(G)

        self._update_status(f"Fichier '{file_name}' : {len(relations_list)} dépendances")
        logger.info(f"✅ {len(relations_list)} relations affichées pour {file_name}")

    def _get_all_files_in_cluster_recursive(self, cluster_info):
        all_files = []
        seen_uids = set()

        def extract_files_recursive(node_data, depth=0):
            """Fonction récursive pour extraire tous les fichiers"""

            node_type = node_data.get('nodeType', '').lower()
            node_name = node_data.get('name') or node_data.get('label', '')
            node_uid = node_data.get('uid')

            if not node_name or not node_uid:
                return

            # ✅ DÉTECTION STRICTE : uniquement les fichiers avec extension
            is_file = self._has_extension(node_name)

            # ✅ Vérifications supplémentaires pour confirmer que c'est un fichier
            if not is_file:
                # Vérifier si c'est explicitement marqué comme fichier
                if node_type == 'file' and (
                    node_data.get('fileContents') or 
                    node_data.get('files') or
                    node_data.get('path', '').endswith(('.py', '.js', '.java', '.cpp'))
                ):
                    is_file = True

            # ✅ EXCLUSION STRICTE : Ignorer classes, fonctions, variables
            if node_type in ['class', 'function', 'method', 'variable']:
                logger.debug(f"  ⏩ Ignoré (type={node_type}): {node_name}")
                return

            # ✅ Si c'est un fichier, l'ajouter
            if is_file and node_uid not in seen_uids:
                seen_uids.add(node_uid)
                all_files.append(node_data)
                logger.debug(f"  {'  '*depth}✅ Fichier: {node_name} (uid={node_uid})")
            else:
                # C'est un dossier, explorer ses enfants
                logger.debug(f"  {'  '*depth}📁 Dossier: {node_name}")

            # ✅ Explorer récursivement TOUS les niveaux (sauf classes/fonctions/variables)
            # Ne pas descendre dans les éléments de code
            if node_type not in ['class', 'function', 'method', 'variable']:
                for level_key in ['level1', 'level2', 'level3', 'level4', 'level5', 'children', '~parents']:
                    children = node_data.get(level_key, [])
                    if children:
                        for child in children:
                            extract_files_recursive(child, depth + 1)

        # Commencer par les root_labels
        root_labels = cluster_info.get('root_labels', [])

        logger.info(f"\n🔍 EXPLORATION RÉCURSIVE DE {len(root_labels)} ROOT_LABELS")
        logger.info("="*60)

        for idx, root_label in enumerate(root_labels):
            logger.info(f"\n[{idx+1}/{len(root_labels)}] Root label: {root_label.get('name', 'N/A')}")
            extract_files_recursive(root_label)

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TOTAL FICHIERS TROUVÉS: {len(all_files)}")

        # ✅ VALIDATION FINALE : Vérifier qu'on n'a que des fichiers
        for f in all_files:
            fname = f.get('name', '')
            ftype = f.get('nodeType', '')
            if ftype in ['class', 'function', 'method', 'variable']:
                logger.warning(f"⚠️ ATTENTION : élément de code détecté: {fname} (type={ftype})")

        return all_files

    def _compute_radial_layout(self, G: nx.DiGraph, center_node: str, num_nodes: int):
        """
        ✅ Version améliorée :
           - Orbite 1 : max 10 nœuds (rayon élargi)
           - Orbite 2 : reste des nœuds (plus éloignés)
           - Anti-collision locale + recentrage automatique
        """
        import numpy as np

        pos = {}
        if not G or center_node not in G.nodes:
            return pos

        # ✅ Centre
        pos[center_node] = np.array([0.0, 0.0])

        # ✅ Récupérer les voisins directs du centre
        neighbors = [n for n in G.neighbors(center_node)]
        n = len(neighbors)
        if n == 0:
            return pos

        # ✅ Séparer en deux orbites
        first_orbit = neighbors[:10]
        second_orbit = neighbors[10:]

        # ✅ Rayons ajustés (plus large pour le premier cercle)
        base_radius_1 = 13.0   # anciennement 10.0 → élargi pour aérer le premier cercle
        base_radius_2 = 20.0 if second_orbit else 0.0

        # ✅ Ajustement progressif selon le nombre total
        if n > 20:
            base_radius_1 += (n - 10) * 0.15
            base_radius_2 += (n - 20) * 0.25

        # ✅ Fonction d’espacement circulaire avec anti-collision
        def distribute_circle(nodes, radius, angular_offset=0.0):
            count = len(nodes)
            if count == 0:
                return

            min_angle = 2 * math.pi / max(count, 1)
            for i, node in enumerate(nodes):
                angle = (min_angle * i) + angular_offset + np.random.uniform(-0.05, 0.05)

                # Vérifier la distance avec les nœuds existants (anti-collision locale)
                for other in pos.keys():
                    if other == center_node:
                        continue
                    ox, oy = pos[other]
                    dx, dy = radius * math.cos(angle), radius * math.sin(angle)
                    dist = ((dx - ox) ** 2 + (dy - oy) ** 2) ** 0.5
                    if dist < 2.0:  # distance minimale pour éviter chevauchement
                        radius += 0.8
                        break

                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                pos[node] = np.array([x, y])

        # ✅ Placer les orbites
        distribute_circle(first_orbit, base_radius_1, angular_offset=0.0)
        distribute_circle(second_orbit, base_radius_2, angular_offset=math.pi / 8)

        # ✅ Recentrage global
        coords = np.array(list(pos.values()))
        mean_x, mean_y = coords.mean(axis=0)
        for node in pos:
            pos[node] -= np.array([mean_x, mean_y])

        # ✅ Éloigner un peu plus la deuxième orbite
        if second_orbit:
            for node in second_orbit:
                pos[node] *= 1.2  # plus de marge entre orbites

        return pos
  
    def _get_cluster_all_relations(self, cluster_uid, cluster_info):
        """✅ VERSION OPTIMISÉE : Une seule requête pour tout le cluster."""
        relations_list = []
        root_labels = cluster_info.get('root_labels', [])
    
        if not root_labels:
            logger.warning("⚠️ Aucun root_label dans le cluster")
            return []
    
        # Collecter tous les UIDs et noms
        cluster_files = {}  # nom_normalisé -> uid
        all_uids = []
        
        for label in root_labels:
            label_name = self.normalize_node_name(label.get('name') or label.get('label', ''))
            label_uid = label.get('uid')
            
            if label_name and label_uid:
                cluster_files[label_name] = label_uid
                all_uids.append(label_uid)
    
        logger.info(f"📂 Cluster contient {len(cluster_files)} fichiers")
    
        if not all_uids:
            return []
    
        # ✅ REQUÊTE GROUPÉE pour tous les fichiers
        uids_str = ", ".join(all_uids)
        
        query = f"""
        {{
          cluster_nodes(func: uid({uids_str})) {{
            uid
            name
            label
            path
            
            # Relations sortantes explicites
            outgoing_relations {{
              target_uid
              target_name
              relation_type
              category
              line
            }}
            
            # Relations entrantes explicites
            incoming_relations {{
              source_uid
              source_name
              relation_type
              category
            }}
            
            # Relations parsées
            relations
            
            # Hiérarchie
            parents {{
              uid
              name
              label
            }}
            
            children: ~parents {{
              uid
              name
              label
            }}
          }}
        }}
        """
        
        logger.info(f"🔍 Requête groupée pour {len(all_uids)} fichiers")
        
        result = self._execute_dgraph_query(query)
        
        if not result or 'cluster_nodes' not in result:
            logger.error("❌ Échec de la requête Dgraph")
            return []
        
        nodes_data = result['cluster_nodes']
        logger.info(f"📥 Reçu données pour {len(nodes_data)} nœuds")
        
        # Traiter chaque nœud
        for node_data in nodes_data:
            node_name = self.normalize_node_name(node_data.get('name') or node_data.get('label', ''))
            node_uid = node_data.get('uid')
            
            if not node_name:
                continue
            
            # ✅ 1. Relations sortantes
            for rel in node_data.get('outgoing_relations', []):
                target_name = self.normalize_node_name(rel.get('target_name', ''))
                if not target_name:
                    continue
                
                is_internal = target_name in cluster_files
                
                relations_list.append({
                    'source': node_name,
                    'target': target_name,
                    'relation_type': rel.get('relation_type', 'relation'),
                    'category': 'internal' if is_internal else 'external',
                    'is_analyzed': True,
                    'source_type': 'internal',
                    'target_type': 'internal' if is_internal else 'external'
                })
            
            # ✅ 2. Relations entrantes
            for rel in node_data.get('incoming_relations', []):
                source_name = self.normalize_node_name(rel.get('source_name', ''))
                if not source_name:
                    continue
                
                is_internal = source_name in cluster_files
                
                relations_list.append({
                    'source': source_name,
                    'target': node_name,
                    'relation_type': rel.get('relation_type', 'relation'),
                    'category': 'internal' if is_internal else 'external',
                    'is_analyzed': True,
                    'source_type': 'internal' if is_internal else 'external',
                    'target_type': 'internal'
                })
            
            # ✅ 3. Relations parsées (JSON)
            try:
                relations_json = node_data.get('relations', '{}')
                if isinstance(relations_json, str):
                    parsed_relations = json.loads(relations_json) if relations_json else {}
                else:
                    parsed_relations = relations_json or {}
                
                for rel_type, rel_list in parsed_relations.items():
                    if not isinstance(rel_list, list):
                        continue
                    
                    for rel in rel_list:
                        target_name = self.normalize_node_name(rel.get('target', ''))
                        if not target_name:
                            continue
                        
                        is_internal = target_name in cluster_files
                        
                        relations_list.append({
                            'source': node_name,
                            'target': target_name,
                            'relation_type': rel_type,
                            'category': 'internal' if is_internal else 'external',
                            'is_analyzed': True,
                            'source_type': 'internal',
                            'target_type': 'internal' if is_internal else 'external',
                            'line': rel.get('line', 0)
                        })
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing JSON pour {node_name}: {e}")
            
            # ✅ 4. Hiérarchie
            for parent in node_data.get('parents', []):
                parent_name = self.normalize_node_name(parent.get('name') or parent.get('label', ''))
                if parent_name:
                    is_internal = parent_name in cluster_files
                    relations_list.append({
                        'source': parent_name,
                        'target': node_name,
                        'relation_type': 'parent',
                        'category': 'internal' if is_internal else 'external',
                        'is_analyzed': True
                    })
            
            for child in node_data.get('children', []):
                child_name = self.normalize_node_name(child.get('name') or child.get('label', ''))
                if child_name:
                    is_internal = child_name in cluster_files
                    relations_list.append({
                        'source': node_name,
                        'target': child_name,
                        'relation_type': 'child',
                        'category': 'internal' if is_internal else 'external',
                        'is_analyzed': True
                    })
        
        # ✅ 5. Relations type Relation (pour chaque fichier)
        for node_name, node_uid in cluster_files.items():
            try:
                rel_type_rels = self._get_relation_type_relations(node_uid)
                
                for rel in rel_type_rels:
                    source = rel.get('source')
                    target = rel.get('target')
                    
                    source_internal = source in cluster_files
                    target_internal = target in cluster_files
                    
                    if source_internal or target_internal:
                        is_internal = source_internal and target_internal
                        rel['category'] = 'internal' if is_internal else 'external'
                        relations_list.append(rel)
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur relations type Relation pour {node_name}: {e}")
        
        # Déduplication
        seen_keys = set()
        unique_relations = []
        
        for rel in relations_list:
            key = (rel.get('source'), rel.get('target'), rel.get('relation_type'))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_relations.append(rel)
        
        internal_count = sum(1 for r in unique_relations if r.get('category') == 'internal')
        external_count = len(unique_relations) - internal_count
        
        logger.info(f"🔗 {len(unique_relations)} relations uniques")
        logger.info(f"   📊 {internal_count} internes, {external_count} externes")
    
        return unique_relations

    def _show_cluster_navigation_view(self):
        """✅ NOUVEAU : Affiche une vue navigable des clusters au lieu du graphe complet."""
        clusters = self._get_clusters_data()

        if not clusters:
            self._show_empty_graph("Aucun cluster disponible")
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Créer un graphe simplifié : uniquement les clusters
        G = nx.DiGraph()

        # Statistiques par cluster
        cluster_stats = {}

        for cluster in clusters:
            cluster_uid = cluster.get('uid', f"cluster_{uuid.uuid4()}")
            cluster_name = cluster.get('name', 'Cluster sans nom')

            # Compter les éléments
            root_labels = cluster.get('root_labels', [])
            total_elements = self._count_total_elements(root_labels)

            cluster_stats[cluster_uid] = {
                'name': cluster_name,
                'files': len(root_labels),
                'total_elements': total_elements
            }

            G.add_node(cluster_uid, **cluster_stats[cluster_uid])

        # Ajouter les relations inter-clusters (si disponibles)
        self._add_inter_cluster_relations(G, clusters)

        # Layout simple et lisible
        if len(G.nodes()) <= 10:
            pos = nx.spring_layout(G, k=3, iterations=100, seed=42, scale=10)
        else:
            pos = nx.kamada_kawai_layout(G, scale=15)

        # Dessiner les nœuds clusters
        from matplotlib.patches import FancyBboxPatch

        for node in G.nodes():
            x, y = pos[node]
            stats = cluster_stats[node]

            # Nom du cluster (tronqué)
            display_name = stats['name'][:20] + '..' if len(stats['name']) > 20 else stats['name']

            # Taille proportionnelle au nombre d'éléments
            size_factor = min(1.5, 0.5 + stats['total_elements'] / 100)
            width = 4.0 * size_factor
            height = 1.5 * size_factor

            # Rectangle
            rect = FancyBboxPatch(
                (x - width/2, y - height/2),
                width, height,
                boxstyle="round,pad=0.2",
                edgecolor='#2C2C2C',
                facecolor='#4A90E2',
                alpha=0.9,
                linewidth=2.5,
                zorder=2
            )
            ax.add_patch(rect)

            # Texte principal
            ax.text(
                x, y + 0.2, display_name,
                ha='center', va='center',
                fontsize=10,
                fontweight='bold',
                color='white',
                zorder=3
            )

            # Statistiques
            stats_text = f"{stats['files']} fichiers\n{stats['total_elements']} éléments"
            ax.text(
                x, y - 0.3, stats_text,
                ha='center', va='center',
                fontsize=7,
                color='white',
                alpha=0.9,
                zorder=3
            )

        # Dessiner les arêtes inter-clusters
        if len(G.edges()) > 0:
            nx.draw_networkx_edges(
                G, pos, ax=ax,
                edge_color='#95A5A6',
                width=2.0,
                alpha=0.5,
                arrows=True,
                arrowsize=12,
                connectionstyle='arc3,rad=0.1'
            )

        ax.axis('off')

        # Marges
        x_coords = [pos[n][0] for n in G.nodes()]
        y_coords = [pos[n][1] for n in G.nodes()]

        margin = 3.0
        ax.set_xlim(min(x_coords) - margin, max(x_coords) + margin)
        ax.set_ylim(min(y_coords) - margin, max(y_coords) + margin)

        # Instructions
        ax.text(
            0.5, 0.02,
            "💡 Double-cliquez sur un cluster pour explorer ses fichiers",
            transform=ax.transAxes,
            ha='center', va='bottom',
            fontsize=9,
            style='italic',
            color='#666666',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#F0F0F0', alpha=0.8)
        )

        # Configuration interactive
        self._setup_cluster_navigation(ax, G, pos, cluster_stats)

        self.canvas.draw()
        self._update_status(f"Vue clusters : {len(G.nodes())} clusters affichés")

    def _setup_cluster_navigation(self, ax, G, pos, cluster_stats):
        """✅ Configure l'interactivité pour naviguer dans les clusters."""

        def on_cluster_click(event):
            if event.inaxes != ax or event.xdata is None:
                return

            # Trouver le cluster cliqué
            for node, coords in pos.items():
                x, y = coords
                dist = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5

                if dist < 2.0:  # Zone de clic
                    if event.dblclick:  # Double-clic = explorer
                        self._explore_cluster(node, cluster_stats[node])
                    elif event.button == 3:  # Clic droit = détails
                        self._show_cluster_details(node, cluster_stats[node])
                    break
                
        self.canvas.mpl_connect('button_press_event', on_cluster_click)

    def _show_cluster_details(self, cluster_uid, cluster_info):
        """Affiche les détails d'un cluster dans un popup."""
        details = f"""
        <h3>📦 {cluster_info['name']}</h3>
        <p><b>Fichiers :</b> {cluster_info['files']}</p>
        <p><b>Éléments totaux :</b> {cluster_info['total_elements']}</p>
        <br>
        <p><i>Double-cliquez pour explorer le contenu</i></p>
        """

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Détails du cluster")
        msg.setTextFormat(Qt.RichText)
        msg.setText(details)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.exec_()

    def _explore_cluster(self, cluster_uid, cluster_info):
        """✅ Explore un cluster en affichant ses fichiers principaux."""
        logger.info(f"🔍 Exploration du cluster : {cluster_info['name']}")

        # Récupérer les détails du cluster
        cluster_data = self._get_cluster_details(cluster_uid)

        if not cluster_data:
            QtWidgets.QMessageBox.warning(
                self,
                "Cluster vide",
                f"Le cluster '{cluster_info['name']}' ne contient aucun fichier."
            )
            return

        # Afficher un sous-graphe du cluster
        self._show_cluster_subgraph(cluster_data, cluster_info['name'])

    def _show_cluster_subgraph(self, cluster_data, cluster_name):
        """✅ Affiche un sous-graphe lisible du cluster."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Extraire les relations du cluster
        relations_list = []
        root_labels = cluster_data.get('root_labels', [])

        for label in root_labels:
            label_name = self.normalize_node_name(label.get('name') or label.get('label', ''))

            # Relations sortantes
            for rel in label.get('outgoing_relations', []):
                target_name = self.normalize_node_name(rel.get('target_name', ''))
                if target_name:
                    relations_list.append({
                        'source': label_name,
                        'target': target_name,
                        'relation_type': rel.get('relation_type', 'relation'),
                        'category': 'cluster',
                        'is_analyzed': True
                    })

        # Construire et dessiner le graphe
        G = self._build_clean_graph(relations_list)
        self.current_graph = G
        self.current_relations = relations_list

        self._draw_graph(G)

        # Titre
        ax.text(
            0.5, 0.98,
            f"📦 Cluster : {cluster_name}",
            transform=ax.transAxes,
            ha='center', va='top',
            fontsize=12,
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#E8F4F8', edgecolor='#4A90E2', linewidth=2)
        )

        self.canvas.draw()
        self._update_status(f"Cluster '{cluster_name}' : {len(relations_list)} relations")

    def _get_cluster_details(self, cluster_uid):
        """Récupère les détails d'un cluster depuis Dgraph."""
        query = f"""
        {{
          cluster(func: uid({cluster_uid})) {{
            uid
            name
            root_labels: ~clusters @filter(eq(level, 0)) {{
              uid
              name
              label
              nodeType

              outgoing_relations {{
                target_uid
                target_name
                relation_type
              }}

              level1: ~parents @filter(eq(level, 1)) {{
                uid
                name
                nodeType
              }}
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'cluster' in result and result['cluster']:
            return result['cluster'][0]

        return None
    
    def _count_total_elements(self, root_labels):
        """Compte récursivement tous les éléments dans une hiérarchie."""
        total = 0

        for label in root_labels:
            total += 1  # Le label lui-même

            # Classes, fonctions, variables
            total += len(label.get('classes', []))
            total += len(label.get('functions', []))
            total += len(label.get('variables', []))

            # Récursif sur les enfants
            for level_key in ['level1', 'level2', 'level3', 'level4', 'children']:
                children = label.get(level_key, [])
                if children:
                    total += self._count_total_elements(children)

        return total
    
    def _add_inter_cluster_relations(self, G, clusters, cluster_stats):
        """✅ Détecte et ajoute les relations entre clusters (imports externes)."""

        # Map: nom_fichier → cluster_uid
        file_to_cluster = {}

        for cluster in clusters:
            cluster_uid = cluster.get('uid')
            root_labels = cluster.get('root_labels', [])

            for label in root_labels:
                label_name = self.normalize_node_name(label.get('name') or label.get('label', ''))
                if label_name:
                    file_to_cluster[label_name] = cluster_uid

        # Analyser les relations sortantes de chaque cluster
        inter_cluster_relations = defaultdict(lambda: defaultdict(int))

        for cluster in clusters:
            cluster_uid = cluster.get('uid')
            root_labels = cluster.get('root_labels', [])

            for label in root_labels:
                label_name = self.normalize_node_name(label.get('name') or label.get('label', ''))

                # Relations sortantes
                for rel in label.get('outgoing_relations', []):
                    target_name = self.normalize_node_name(rel.get('target_name', ''))

                    if target_name and target_name in file_to_cluster:
                        target_cluster = file_to_cluster[target_name]

                        # Si c'est un cluster différent
                        if target_cluster != cluster_uid:
                            inter_cluster_relations[cluster_uid][target_cluster] += 1

        # Ajouter les arêtes inter-clusters
        for source_cluster, targets in inter_cluster_relations.items():
            for target_cluster, count in targets.items():
                if source_cluster in G and target_cluster in G:
                    G.add_edge(
                        source_cluster,
                        target_cluster,
                        relation_type='imports',
                        color='#FFA500',
                        label=f"{count} imports",
                        weight=count
                    )

        logger.info(f"🔗 {len(inter_cluster_relations)} relations inter-clusters détectées")

    def _show_empty_graph(self, message: str):
        """Affiche un message dans le graphe vide."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, message, ha='center', va='center', 
               color='#999999', fontsize=12, style='italic')
        ax.axis('off')
        self.canvas.draw()

    def _show_progress(self, message_key: str, value: int, **kwargs):
        """Affiche la barre de progression avec message traduit"""
        message = tr(f"relation_import.progress.{message_key}", **kwargs)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} - {value}%")
        QtWidgets.QApplication.processEvents()
    
    def _update_progress(self, value: int, message: str = ""):
        """Met à jour la barre de progression."""
        self.progress_bar.setValue(value)
        if message:
            self.progress_bar.setFormat(f"{message} - {value}%")
        QtWidgets.QApplication.processEvents()
    
    def _hide_progress(self):
        """Cache la barre de progression."""
        self.progress_bar.setVisible(False)
        QtWidgets.QApplication.processEvents()

    def _get_stylesheet(self):
        """Stylesheet responsive avec gestion adaptative - ✅ TOUT EN BLANC."""
        return f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        /* Boutons responsive */
        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            min-height: 32px;
            min-width: 80px;
        }}
        QPushButton:hover {{ background-color: {self.secondary_color}; }}
        QPushButton:disabled {{ background-color: #CCCCCC; color: #666666; }}

        /* ComboBox responsive - ✅ FOND BLANC */
        QComboBox {{
            padding: 8px 12px;
            border: 2px solid #E0E0E0;
            border-radius: 6px;
            background-color: #FFFFFF;  /* ✅ BLANC */
            font-size: 13px;
            font-weight: 500;
            color: {self.text_color};
            min-height: 32px;
            min-width: 150px;
        }}
        QComboBox:focus {{ 
            border: 2px solid {self.primary_color}; 
            background-color: #FFFFFF;  /* ✅ RESTE BLANC au focus */
        }}
        QComboBox::drop-down {{
            border: none;
            width: 25px;
            background-color: transparent;  /* ✅ TRANSPARENT */
        }}
        QComboBox QAbstractItemView {{
            background-color: #FFFFFF;  /* ✅ Liste déroulante blanche */
            selection-background-color: #E8F4F8;  /* ✅ Sélection claire */
            selection-color: #1A1A1A;
            border: 1px solid #E0E0E0;
        }}

        /* TreeWidget responsive - ✅ FOND BLANC */
        QTreeWidget {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            background-color: #FFFFFF;  /* ✅ BLANC */
            padding: 3px;
            min-width: 200px;
        }}
        QTreeWidget::item {{ 
            padding: 6px 4px;
            min-height: 24px;
            background-color: transparent;  /* ✅ TRANSPARENT par défaut */
        }}
        QTreeWidget::item:selected {{
            background-color: #E8F4F8;  /* ✅ Sélection claire */
            color: #1A1A1A;
        }}
        QTreeWidget::item:hover {{
            background-color: #F5F5F5;  /* ✅ Hover très clair */
        }}

        /* ProgressBar responsive - ✅ FOND BLANC */
        QProgressBar {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            text-align: center;
            background-color: #FFFFFF;  /* ✅ BLANC */
            padding: 1px;
            height: 24px;
            min-width: 200px;
            max-width: 400px;
            font-size: 10px;
            font-weight: 500;
            color: #333333;
        }}
        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 3px;
        }}

        /* Labels responsive - ✅ FOND TRANSPARENT/BLANC */
        QLabel {{
            font-size: 12px;
            padding: 2px;
            background-color: transparent;  /* ✅ TRANSPARENT (hérite du parent blanc) */
            color: {self.text_color};
        }}

        /* Checkboxes responsive - ✅ FOND BLANC */
        QCheckBox {{
            font-size: 11px;
            font-weight: 600;
            color: #333333;
            spacing: 8px;
            padding: 4px;
            background-color: transparent;  /* ✅ TRANSPARENT */
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid #CCCCCC;
            border-radius: 3px;
            background: #FFFFFF;  /* ✅ BLANC */
        }}
        QCheckBox::indicator:hover {{
            border-color: #999999;
            background: #FFFFFF;  /* ✅ RESTE BLANC */
        }}
        QCheckBox::indicator:checked {{
            border: 2px solid #A23B2D;
            background-color: #A23B2D;
        }}

        /* Splitter responsive */
        QSplitter::handle {{
            background-color: #E0E0E0;
            width: 3px;
        }}
        QSplitter::handle:hover {{
            background-color: #CCCCCC;
        }}

        /* ✅ NOUVEAU : Frame backgrounds (pour popups/dialogs) */
        QFrame {{
            background-color: #FFFFFF;
        }}

        /* ✅ NOUVEAU : TextEdit (pour affichage de code) */
        QTextEdit {{
            background-color: #FAFAFA;
            color: #1A1A1A;
            border: 1px solid #E0E0E0;
            selection-background-color: #B3D7FF;
            selection-color: #000000;
        }}

        /* ✅ NOUVEAU : ScrollBars (uniformes partout) */
        QScrollBar:vertical {{
            background: #F5F5F5;
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: #C0C0C0;
            border-radius: 6px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #A0A0A0;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background: #F5F5F5;
            height: 12px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: #C0C0C0;
            border-radius: 6px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #A0A0A0;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* ✅ NOUVEAU : TabWidget (si utilisé) */
        QTabWidget::pane {{
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
        }}
        QTabBar::tab {{
            background-color: #F5F5F5;
            color: #666666;
            padding: 8px 16px;
            border: 1px solid #E0E0E0;
            border-bottom: none;
        }}
        QTabBar::tab:selected {{
            background-color: #FFFFFF;
            color: #1A1A1A;
        }}
        QTabBar::tab:hover {{
            background-color: #FAFAFA;
        }}
        """
    
    def _init_ui(self):
        """Interface responsive avec layouts adaptatifs."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ===== HEADER FIXE =====
        header_widget = QtWidgets.QWidget()
        header_widget.setFixedHeight(70)
        header_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Label Projet (largeur fixe)
        proj_label = QtWidgets.QLabel(tr("relation_import.project_label"))
        proj_label.setStyleSheet("font-weight: 600; font-size: 13px; background-color: transparent;")
        proj_label.setFixedWidth(50)
        proj_label.setAlignment(Qt.AlignVCenter)
        header_layout.addWidget(proj_label)

        # ComboBox Projet
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setFixedWidth(200)
        self.project_combo.setFixedHeight(32)
        self.project_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox:hover {
                border: 1px solid #999999;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        header_layout.addWidget(self.project_combo, 0, Qt.AlignVCenter)

        # Bouton Clear Cache
        self.clear_cache_btn = QtWidgets.QPushButton(
            qta.icon('fa5s.trash', color='#B71C1C'), 
            " " + tr("relation_import.clear_cache")
        )
        self.clear_cache_btn.setFixedWidth(120)
        self.clear_cache_btn.setFixedHeight(32)
        self.clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #F5F5F5;
                border: 1px solid #999999;
            }
        """)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        header_layout.addWidget(self.clear_cache_btn, 0, Qt.AlignVCenter)

        # Bouton Back
        self.back_btn = QtWidgets.QPushButton(
            qta.icon('fa5s.arrow-left', color='black'), 
            " " + tr("relation_import.back")
        )
        self.back_btn.setFixedWidth(100)
        self.back_btn.setFixedHeight(32)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #F5F5F5;
                border: 1px solid #999999;
            }
            QPushButton:disabled {
                background-color: #F5F5F5;
                color: #CCCCCC;
                border: 1px solid #E0E0E0;
            }
        """)
        self.back_btn.clicked.connect(self._navigate_back)
        self.back_btn.setEnabled(False)
        header_layout.addWidget(self.back_btn, 0, Qt.AlignVCenter)

        # Container fixe pour info + progress
        info_progress_widget = QtWidgets.QWidget()
        info_progress_widget.setFixedWidth(300)
        info_progress_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        info_progress_layout = QtWidgets.QVBoxLayout(info_progress_widget)
        info_progress_layout.setContentsMargins(0, 0, 0, 0)
        info_progress_layout.setSpacing(4)

        self.cache_info_label = QtWidgets.QLabel(self.query_cache.get_stats())
        self.cache_info_label.setStyleSheet("font-size: 10px; color: #666666; background-color: transparent;")
        self.cache_info_label.setFixedHeight(16)
        self.cache_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_progress_layout.addWidget(self.cache_info_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #999999;
                border-radius: 3px;
            }
        """)
        info_progress_layout.addWidget(self.progress_bar)

        header_layout.addWidget(info_progress_widget, 0, Qt.AlignVCenter)
        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        # margin-bottom du header augmenté
        main_layout.addSpacing(20)

        # ===== SPLITTER =====
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setChildrenCollapsible(True)

        # LEFT PANEL
        left_widget = QtWidgets.QWidget()
        left_widget.setMinimumWidth(200)
        left_widget.setMaximumWidth(400)
        left_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        tree_label = QtWidgets.QLabel(tr("relation_import.structure_label"))
        tree_label.setStyleSheet("font-weight: 600; font-size: 12px; background-color: transparent;")
        left_layout.addWidget(tree_label)

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabel(tr("relation_import.elements"))
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        left_layout.addWidget(self.tree_widget)

        splitter.addWidget(left_widget)

        # RIGHT PANEL
        right_widget = QtWidgets.QWidget()
        right_widget.setMinimumWidth(400)
        right_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # ===== TOOLBAR =====
        toolbar_widget = QtWidgets.QWidget()
        toolbar_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar_widget)
        toolbar_layout.setSpacing(8)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        # Level combo
        level_label = QtWidgets.QLabel(tr("relation_import.level_label"))
        level_label.setStyleSheet("font-weight: 600; font-size: 11px; background-color: transparent;")
        toolbar_layout.addWidget(level_label)

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.setMinimumWidth(160)
        self.level_combo.setMaximumWidth(240)
        self.level_combo.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.level_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox:hover {
                border: 1px solid #999999;
            }
        """)
        self.level_combo.addItem(qta.icon('fa5s.th', color=self.primary_color), tr("relation_import.view_clusters"), 0)
        self.level_combo.addItem(qta.icon('fa5s.project-diagram', color=self.primary_color), tr("relation_import.direct_relations"), 1)
        self.level_combo.setCurrentIndex(0)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar_layout.addWidget(self.level_combo)

        toolbar_layout.addSpacing(10)

        # stretch déplacé ici → zoom et navigation vont complètement à droite
        toolbar_layout.addStretch()

        # Zoom controls
        zoom_widget = QtWidgets.QWidget()
        zoom_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        zoom_layout = QtWidgets.QHBoxLayout(zoom_widget)
        zoom_layout.setSpacing(4)
        zoom_layout.setContentsMargins(0, 0, 0, 0)

        zoom_label = QtWidgets.QLabel(tr("relation_import.zoom"))
        zoom_label.setStyleSheet("font-weight: 600; font-size: 11px; background-color: transparent;")
        zoom_layout.addWidget(zoom_label)

        btn_style = """
            QPushButton {
                background-color: white; 
                border: 1px solid #CCCCCC; 
                border-radius: 4px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #F5F5F5;
                border: 1px solid #999999;
            }
        """

        self.zoom_in_btn = QtWidgets.QPushButton(qta.icon('fa5s.search-plus', color='black'), "")
        self.zoom_in_btn.setStyleSheet(btn_style)
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QtWidgets.QPushButton(qta.icon('fa5s.search-minus', color='black'), "")
        self.zoom_out_btn.setStyleSheet(btn_style)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_layout.addWidget(self.zoom_out_btn)

        self.zoom_reset_btn = QtWidgets.QPushButton(qta.icon('fa5s.sync', color='black'), "")
        self.zoom_reset_btn.setStyleSheet(btn_style)
        self.zoom_reset_btn.clicked.connect(self._zoom_reset)
        zoom_layout.addWidget(self.zoom_reset_btn)

        toolbar_layout.addWidget(zoom_widget)

        # Navigation controls
        nav_widget = QtWidgets.QWidget()
        nav_widget.setStyleSheet("background-color: transparent;")  # Fond transparent
        nav_layout = QtWidgets.QHBoxLayout(nav_widget)
        nav_layout.setSpacing(4)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        nav_label = QtWidgets.QLabel(tr("relation_import.navigation"))
        nav_label.setStyleSheet("font-weight: 600; font-size: 11px; background-color: transparent;")
        nav_layout.addWidget(nav_label)

        self.pan_up_btn = QtWidgets.QPushButton(qta.icon('fa5s.arrow-up', color='black'), "")
        self.pan_up_btn.setStyleSheet(btn_style)
        self.pan_up_btn.clicked.connect(lambda: self._pan_view(0, 50))
        nav_layout.addWidget(self.pan_up_btn)

        self.pan_down_btn = QtWidgets.QPushButton(qta.icon('fa5s.arrow-down', color='black'), "")
        self.pan_down_btn.setStyleSheet(btn_style)
        self.pan_down_btn.clicked.connect(lambda: self._pan_view(0, -50))
        nav_layout.addWidget(self.pan_down_btn)

        self.pan_left_btn = QtWidgets.QPushButton(qta.icon('fa5s.arrow-left', color='black'), "")
        self.pan_left_btn.setStyleSheet(btn_style)
        self.pan_left_btn.clicked.connect(lambda: self._pan_view(-50, 0))
        nav_layout.addWidget(self.pan_left_btn)

        self.pan_right_btn = QtWidgets.QPushButton(qta.icon('fa5s.arrow-right', color='black'), "")
        self.pan_right_btn.setStyleSheet(btn_style)
        self.pan_right_btn.clicked.connect(lambda: self._pan_view(50, 0))
        nav_layout.addWidget(self.pan_right_btn)

        toolbar_layout.addWidget(nav_widget)

        right_layout.addWidget(toolbar_widget)

        # CHECKBOXES
        checkbox_layout = QtWidgets.QHBoxLayout()
        checkbox_layout.setSpacing(15)
        checkbox_layout.setContentsMargins(0, 5, 0, 5)

        self.show_internal_relations_cb = QtWidgets.QCheckBox(tr("relation_import.interdependence"))
        self.show_internal_relations_cb.setStyleSheet(self._get_checkbox_style())
        self.show_internal_relations_cb.setChecked(False)
        self.show_internal_relations_cb.stateChanged.connect(self._on_internal_relations_changed)
        checkbox_layout.addWidget(self.show_internal_relations_cb)

        self.show_node_origins_cb = QtWidgets.QCheckBox(tr("relation_import.show_node_origins"))
        self.show_node_origins_cb.setStyleSheet(self._get_checkbox_style())
        self.show_node_origins_cb.setChecked(False)
        self.show_node_origins_cb.stateChanged.connect(self._on_node_origins_changed)
        checkbox_layout.addWidget(self.show_node_origins_cb)

        checkbox_layout.addStretch()
        right_layout.addLayout(checkbox_layout)

        # CANVAS
        self.figure = Figure(figsize=(10, 8), facecolor='white', tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: white; border: 1px solid #E0E0E0; border-radius: 4px;")
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.canvas.setMinimumSize(400, 400)
        right_layout.addWidget(self.canvas)

        splitter.addWidget(right_widget)

        # Tailles proportionnelles
        splitter.setSizes([250, 800])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # Initialisation
        self.current_zoom = 1.0
        self.zoom_step = 0.2

    def resizeEvent(self, event):
        """Gère le redimensionnement de la fenêtre."""
        super().resizeEvent(event)

        # Ajuster l'affichage selon la largeur
        width = self.width()

        if width < 1024:  # Petit écran
            # Masquer certains éléments non essentiels
            if hasattr(self, 'cache_info_label'):
                self.cache_info_label.setVisible(False)
        else:
            if hasattr(self, 'cache_info_label'):
                self.cache_info_label.setVisible(True)

        # Redessiner le graphe si nécessaire
        if hasattr(self, 'canvas') and hasattr(self, 'current_graph'):
            if self.current_graph and len(self.current_graph.nodes()) > 0:
                self.canvas.draw_idle()

    def _adjust_ui_for_size(self):
        """Ajuste l'UI selon la taille de la fenêtre."""
        width = self.width()
        height = self.height()

        # Adapter les tailles de police
        if width < 1024:
            font_scale = 0.9
        elif width < 1280:
            font_scale = 1.0
        else:
            font_scale = 1.1

        # Adapter le graphe si nécessaire
        if hasattr(self, 'graph_data') and self.graph_data:
            # Recalculer les dimensions de texte
            num_nodes = self.graph_data.get('num_nodes', 0)

            if width < 1024:
                self.graph_data['text_width'] = 4.5
                self.graph_data['text_height'] = 1.2
                self.graph_data['font_size'] = 7
            elif width < 1440:
                self.graph_data['text_width'] = 5.0
                self.graph_data['text_height'] = 1.3
                self.graph_data['font_size'] = 8
            else:
                self.graph_data['text_width'] = 5.5
                self.graph_data['text_height'] = 1.4
                self.graph_data['font_size'] = 9

    def _get_checkbox_style(self):
        """Style responsive pour les checkboxes."""
        return """
            QCheckBox {
                font-size: 11px;
                font-weight: 600;
                color: #333333;
                spacing: 8px;
                padding: 4px 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #CCCCCC;
                border-radius: 3px;
                background: #FFFFFF;
            }
            QCheckBox::indicator:hover {
                border-color: #999999;
                background: #F8F8F8;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #A23B2D;
                background-color: #A23B2D;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #8B2E1F;
            }
        """

    def _format_node_display_name(self, node_name: str, node_type: str = None) -> str:

        if not node_name or not isinstance(node_name, str):
            return "N/A"

        node_name = node_name.strip()

        # ========== EXTRACTION NOM SANS EXTENSION ==========
        has_extension = self._has_extension(node_name)
        if has_extension:
            base_name = os.path.splitext(os.path.basename(node_name))[0]
            extension = os.path.splitext(node_name)[1]
        else:
            base_name = os.path.basename(node_name)
            extension = ''

        # ========== 1. NŒUD CENTRAL → TOUJOURS FICHIER AVEC EXTENSION ==========
        if self.current_central_name and base_name == self.normalize_node_name(self.current_central_name):
            if has_extension:
                return os.path.basename(node_name)

            # Chercher l'extension dans les métadonnées
            if self.current_central_uid and self.current_central_uid in self._node_cache:
                cached_item = self._node_cache[self.current_central_uid]
                item_data = cached_item.item_data

                full_path = item_data.get('path') or item_data.get('sourcePath')
                if full_path and self._has_extension(full_path):
                    return os.path.basename(full_path)

            # Ajouter .py par défaut
            return f"{base_name}.py"

        # ========== 2. DOSSIERS/MODULES EXPLICITES ==========
        if node_type in ['folder', 'directory', 'module', 'package']:
            return base_name

        # ========== 3. NETTOYER PRÉFIXES EXISTANTS ==========
        import re

        patterns = [
            r'^[Cc]lass\s*:?\s*',
            r'^[Cc]lasse\s*:?\s*',
            r'^[Ff]unction\s*:?\s*',
            r'^[Ff]onction\s*:?\s*',
            r'^[Mm]ethod\s*:?\s*',
            r'^[Mm]éthode\s*:?\s*',
            r'^[Vv]ariable\s*:?\s*',
            r'^[Vv]ar\s*:?\s*',
            r'^[Cc]onst\s*:?\s*',
            r'^[Cc]onstante\s*:?\s*',
        ]

        clean_name = base_name
        for pattern in patterns:
            match = re.match(pattern, clean_name)
            if match:
                clean_name = clean_name[match.end():].strip()
                break
            
        # ========== 4. TYPE EXPLICITE (PRIORITÉ ABSOLUE) ==========
        if node_type:
            type_to_initial = {
                'class': 'C',
                'function': 'F',
                'method': 'M',
                'variable': 'V',
                'const': 'C',
                'file': '',
            }

            if node_type in type_to_initial:
                prefix = type_to_initial[node_type]
                if prefix:
                    return f"{prefix}: {clean_name}"
                else:
                    # Type 'file' : retourner avec extension
                    if has_extension:
                        return os.path.basename(node_name)
                    return f"{clean_name}.py"

        clean_lower = clean_name.lower()

        # ========== 5. ✅ FONCTIONS DE TEST (priorité absolue) ==========
        # Pattern: _test_*, test_*, *_test
        if (clean_name.startswith('_test_') or 
            clean_name.startswith('test_') or 
            clean_name.endswith('_test')):
            return f"F: {clean_name}"

        # ========== 6. ✅ MODULES/DOSSIERS PYTHON COURANTS (SANS extension) ==========
        python_module_patterns = {
            # Configuration
            'config', 'settings', 'constants', 'env', 'secrets',

            # Utilitaires
            'utils', 'helpers', 'tools', 'common', 'shared',

            # Structure
            'models', 'views', 'controllers', 'services', 'routes',
            'handlers', 'middleware', 'decorators',

            # Données
            'data', 'database', 'db', 'schema', 'fixtures',

            # Application
            'main', 'app', 'run', 'server', 'client',

            # Logging
            'logger', 'logging', 'log',

            # Tests
            'conftest', 'setup', 'teardown', 'tests',

            # Auth
            'auth', 'authentication', 'authorization', 'permissions',
        }

        # ✅ CORRECTION : Utiliser clean_name (sans extension) pour la comparaison
        if clean_lower in python_module_patterns:
            return clean_name  # Retourner SANS extension

        # ========== 7. ✅ CLASSES (PascalCase) - AVANT les fonctions ==========
        if clean_name and clean_name[0].isupper() and not clean_name.isupper():
            uppercase_count = sum(1 for c in clean_name if c.isupper())
            has_lowercase = any(c.islower() for c in clean_name)

            # PascalCase : MyClass, ApiTester, HttpClient
            if uppercase_count >= 1 and has_lowercase and '_' not in clean_name:
                return f"C: {clean_name}"

        # ========== 8. CONSTANTES (UPPER_SNAKE_CASE) ==========
        if clean_name.isupper() and '_' in clean_name and len(clean_name) > 2:
            return f"C: {clean_name}"

        # ========== 9. ✅ FONCTIONS (verbes d'action avec underscore) ==========
        if '_' in clean_name and not clean_name.isupper():
            function_verbs = [
                'get_', 'set_', 'create_', 'delete_', 'update_', 'fetch_',
                'load_', 'save_', 'parse_', 'validate_', 'check_', 'verify_',
                'build_', 'make_', 'generate_', 'calculate_', 'compute_',
                'process_', 'handle_', 'execute_', 'run_', 'start_', 'stop_',
                'open_', 'close_', 'read_', 'write_', 'send_', 'receive_',
            ]

            # Si commence par un verbe d'action → fonction
            if any(clean_lower.startswith(verb) for verb in function_verbs):
                return f"F: {clean_name}"

            # Si 3+ underscores → probablement fonction
            underscore_count = clean_name.count('_')
            if underscore_count >= 3:
                return f"F: {clean_name}"

        # ========== 10. ✅ FICHIERS PYTHON (snake_case avec underscore) ==========
        if '_' in clean_name and not clean_name.isupper():
            # C'est un fichier Python (ex: api_config, test_api_key)
            if has_extension:
                return os.path.basename(node_name)
            return f"{clean_name}.py"

        # ========== 11. VARIABLES (snake_case simple, SANS underscore) ==========
        if clean_name and clean_name[0].islower() and '_' not in clean_name:
            return f"V: {clean_name}"

        # ========== 12. DERNIER RECOURS ==========
        # Si a déjà une extension, la garder
        if has_extension:
            return os.path.basename(node_name)

        return clean_name
    
    def _on_node_origins_changed(self, state):
        """✅ Gère l'affichage des origines des nœuds en bas à droite."""
        is_checked = (state == Qt.Checked)

        logger.info(f"🔄 Origines nœuds: {'ACTIVÉES' if is_checked else 'DÉSACTIVÉES'}")

        if not hasattr(self, 'graph_data') or not self.graph_data:
            logger.warning("⚠️ Aucun graphe actif")
            return

        # Redessiner le graphe avec/sans les origines
        if is_checked:
            self._add_node_origins_display()
        else:
            self._remove_node_origins_display()

        # ✅ CORRECTION : Forcer le redraw complet
        self.canvas.draw()  # Changé de draw_idle() à draw()

        self._update_status(
            f"Origines nœuds: {'Affichées' if is_checked else 'Masquées'}"
        )

    def _add_node_origins_display(self):
        """✅ CORRIGÉ : Affiche l'origine en bas à droite de CHAQUE nœud individuellement."""
        if not hasattr(self, 'graph_data') or 'ax' not in self.graph_data:
            logger.warning("⚠️ graph_data ou ax non disponible")
            return

        ax = self.graph_data['ax']
        G = self.graph_data.get('G')
        pos = self.graph_data.get('pos')

        if not G or not pos:
            logger.warning("⚠️ Graphe ou positions non disponibles")
            return

        logger.info(f"\n{'='*70}")
        logger.info(f"📍 AFFICHAGE ORIGINES SUR CHAQUE NŒUD")
        logger.info(f"{'='*70}")

        # Supprimer les anciens textes d'origine s'ils existent
        if hasattr(self, 'origin_text_objects') and self.origin_text_objects:
            for text_obj in self.origin_text_objects:
                try:
                    text_obj.remove()
                except:
                    pass
                
        self.origin_text_objects = []

        # Collecter les noms de tous les nœuds du graphe
        graph_nodes = set(G.nodes())
        logger.info(f"📊 {len(graph_nodes)} nœuds dans le graphe")

        # Mapping : nom_nœud -> path d'origine
        node_origins = {}

        # ===== STRATÉGIE 1 : Métadonnées du graphe =====
        for node_name in graph_nodes:
            node_data = G.nodes[node_name]

            path = (node_data.get('path') or 
                   node_data.get('sourcePath') or 
                   node_data.get('full_path', ''))

            if path:
                filename = os.path.basename(path)
                if filename and filename.strip():
                    node_origins[node_name] = filename
                    logger.debug(f"   ✅ Métadonnées graphe: {node_name} -> {filename}")

        # ===== STRATÉGIE 2 : Cache _node_cache =====
        for node_name in graph_nodes:
            if node_name in node_origins:
                continue  # Déjà trouvé
            
            # Chercher dans le cache par nom
            for uid, cached_item in self._node_cache.items():
                item_name = self.normalize_node_name(
                    cached_item.item_data.get('name') or 
                    cached_item.item_data.get('label') or 
                    cached_item.text(0)
                )

                # Comparer noms nettoyés
                clean_node = node_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()
                clean_item = item_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()

                if clean_node == clean_item or clean_node in clean_item or clean_item in clean_node:
                    path = (cached_item.item_data.get('path') or 
                           cached_item.item_data.get('sourcePath') or 
                           cached_item.item_data.get('full_path', ''))

                    if path:
                        filename = os.path.basename(path)
                        if filename and filename.strip():
                            node_origins[node_name] = filename
                            logger.debug(f"   ✅ Cache: {node_name} -> {filename}")
                            break

        # ===== STRATÉGIE 3 : Relations Dgraph =====
        missing_nodes = [n for n in graph_nodes if n not in node_origins]

        if missing_nodes and self.dgraph_connector:
            logger.info(f"\n🔍 Stratégie 3 : Relations Dgraph ({len(missing_nodes)} nœuds sans path)...")

            for node_name in missing_nodes[:20]:  # Limiter pour performance
                clean_name = node_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()
                escaped = clean_name.replace('"', '\\"')

                query = f"""
                {{
                  by_source(func: type(Relation)) @filter(regexp(sourceName, /{escaped}/i)) {{
                    sourceName
                    sourcePath
                  }}

                  by_target(func: type(Relation)) @filter(regexp(targetName, /{escaped}/i)) {{
                    targetName
                    targetPath
                  }}
                }}
                """

                result = self._execute_dgraph_query(query)
                if not result:
                    continue
                
                # Traiter sourcePath
                for rel in result.get('by_source', []):
                    source_name = rel.get('sourceName', '')
                    source_path = rel.get('sourcePath', '')

                    if source_name and source_path:
                        clean_source = source_name.replace('Function: ', '').replace('Method: ', '').replace('Class: ', '').strip()

                        if clean_source == clean_name or clean_name in clean_source or clean_source in clean_name:
                            filename = self._extract_filename_from_relation_path(source_path)
                            if filename:
                                node_origins[node_name] = filename
                                logger.debug(f"   ✅ Relations (source): {node_name} -> {filename}")
                                break

        logger.info(f"\n📊 RÉSUMÉ :")
        logger.info(f"   ✅ {len(node_origins)} nœuds avec origines")
        logger.info(f"   ❌ {len(graph_nodes) - len(node_origins)} nœuds sans origines")

        text_height = self.graph_data.get('text_height', 1.3)
    
        for node_name, origin_file in node_origins.items():
            if node_name not in pos:
                continue
            
            x, y = pos[node_name]
            
            # ✅ NOUVEAU : Récupérer le PATH COMPLET depuis les métadonnées
            full_path = None
            
            # 1. Essayer depuis les métadonnées du graphe
            if node_name in G.nodes():
                node_data = G.nodes[node_name]
                full_path = (node_data.get('path') or 
                            node_data.get('sourcePath') or 
                            node_data.get('full_path', ''))
            
            # 2. Si pas trouvé, essayer depuis le cache
            if not full_path:
                for uid, cached_item in self._node_cache.items():
                    item_name = self.normalize_node_name(
                        cached_item.item_data.get('name') or 
                        cached_item.item_data.get('label') or 
                        cached_item.text(0)
                    )
                    
                    clean_node = node_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()
                    clean_item = item_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()
                    
                    if clean_node == clean_item or clean_node in clean_item or clean_item in clean_node:
                        full_path = (cached_item.item_data.get('path') or 
                                   cached_item.item_data.get('sourcePath') or 
                                   cached_item.item_data.get('full_path', ''))
                        if full_path:
                            break
                        
            # 3. Fallback : utiliser origin_file si pas de path complet
            if not full_path:
                full_path = origin_file
            
            # Nettoyer le path (enlever les suffixes de type comme /Function:xxx)
            if full_path:
                # Séparer si format "path/Function:name"
                if '/Function:' in full_path or '/Method:' in full_path or '/Class:' in full_path:
                    full_path = full_path.split('/Function:')[0].split('/Method:')[0].split('/Class:')[0]
                
                # Normaliser les séparateurs
                full_path = full_path.replace('\\', '/')
            
            # Afficher le path complet (pas de troncature)
            display_origin = full_path if full_path else origin_file
            
            # Position : juste en dessous du rectangle du nœud
            text_x = x + 0.7
            text_y = y - (text_height / 2) - 0.35  # Un peu plus d'espace pour paths longs
            
            # Créer le texte d'origine avec le PATH COMPLET
            origin_text = ax.text(
                text_x, text_y,
                display_origin,
                ha='center',      # Centré horizontalement avec le nœud
                va='top',         # Aligné en haut (donc en dessous du rectangle)
                color='#1A1A1A',  # Noir pour meilleure visibilité
                fontsize=6.5,     # ✅ Réduit légèrement car paths plus longs
                style='italic',   # En italique
                family='monospace',  # ✅ Monospace pour paths
                fontweight='500', # Légèrement gras pour visibilité
                alpha=0.95,       # Presque totalement opaque
                zorder=4,         # Au-dessus des arêtes mais sous les nœuds
                wrap=True         # ✅ Permettre le retour à la ligne si nécessaire
            )
            
            self.origin_text_objects.append(origin_text)
            logger.debug(f"   📍 Origine affichée pour {node_name}: {display_origin}")
    
        logger.info(f"✅ {len(self.origin_text_objects)} origines affichées sur les nœuds")
        logger.info(f"{'='*70}\n")

    def _extract_filename_from_relation_path(self, path: str) -> str:
        """✅ Extrait le nom de fichier depuis sourcePath/targetPath des Relations."""
        if not path:
            return ""
        
        # Normaliser les séparateurs
        path = path.replace('\\', '/')
        
        # Si le path contient "/Function:" ou "/Method:", prendre la partie avant
        for separator in ['/Function:', '/Method:', '/Class:', '/Variable:']:
            if separator in path:
                path = path.split(separator)[0]
                break
            
        # Prendre le basename
        filename = os.path.basename(path)
        
        return filename if filename else ""
    
    def _show_error(self, title_key: str, message_key: str, **kwargs):
        """Affiche une erreur avec messages traduits"""
        title = tr(f"relation_import.{title_key}")
        message = tr(f"relation_import.errors.{message_key}", **kwargs)
        QtWidgets.QMessageBox.critical(self, title, message)

    def _add_intra_file_relations(self):
        """✅ CORRIGÉ : Ajoute TOUTES les relations d'appels + CRÉE les nœuds manquants."""
        if not self.current_central_uid:
            logger.warning("⚠️ Aucun nœud central")
            return

        logger.info("\n" + "="*70)
        logger.info("🔍 CHARGEMENT APPELS (INTRA + INTER-FICHIERS)")
        logger.info("="*70)

        node_details = self._get_node_details(self.current_central_uid)
        if not node_details:
            logger.warning("⚠️ Impossible de récupérer les détails")
            return

        central_path = node_details.get('path') or node_details.get('sourcePath') or node_details.get('full_path')
        central_name = node_details.get('name') or node_details.get('label') or self.current_central_name

        logger.info(f"📂 Path : {central_path}")
        logger.info(f"📄 Name : {central_name}")

        def extract_filename(path):
            if not path:
                return None
            import os
            if '/' in path and ':' in path:
                path = path.split('/')[0]
            path = path.replace('\\', '/').strip()
            basename = os.path.basename(path)
            name_no_ext = os.path.splitext(basename)[0]
            return name_no_ext.lower()

        central_file = extract_filename(central_path or central_name)

        if not central_file:
            logger.error("❌ Impossible de normaliser le fichier")
            return

        logger.info(f"🎯 Fichier normalisé : '{central_file}'")

        # ✅ COLLECTER LES NŒUDS EXISTANTS
        existing_nodes_map = {}
        if hasattr(self, 'graph_data') and 'G' in self.graph_data:
            G = self.graph_data['G']
            for node in G.nodes():
                existing_nodes_map[node] = node
                normalized = self.normalize_node_name(node)
                existing_nodes_map[normalized] = node
                if ':' in node:
                    without_prefix = node.split(':', 1)[1].strip()
                    existing_nodes_map[without_prefix] = node
                    existing_nodes_map[self.normalize_node_name(without_prefix)] = node

        logger.info(f"📊 {len(set(existing_nodes_map.values()))} nœuds existants dans le graphe")

        # ✅ REQUÊTE DGRAPH
        escaped_name = central_file.replace('.', r'\.')

        query = f"""
        {{
          outgoing(func: type(Relation)) @filter(
            (eq(relationType, "calls") OR eq(relationType, "call")) AND
            regexp(sourcePath, /{escaped_name}/i)
          ) {{
            uid
            relationType
            category
            line
            intraFile

            source {{ uid name nodeType }}
            target {{ uid name nodeType }}

            sourceName
            sourceType
            sourcePath
            sourceDescription

            targetName
            targetType
            targetPath
            targetDescription
          }}

          incoming(func: type(Relation)) @filter(
            (eq(relationType, "calls") OR eq(relationType, "call")) AND
            regexp(targetPath, /{escaped_name}/i)
          ) {{
            uid
            relationType
            category
            line
            intraFile

            source {{ uid name nodeType }}
            target {{ uid name nodeType }}

            sourceName
            sourceType
            sourcePath
            sourceDescription

            targetName
            targetType
            targetPath
            targetDescription
          }}
        }}
        """

        logger.info(f"📡 Requête Dgraph pour '{central_file}'...")
        result = self._execute_dgraph_query(query)

        if not result:
            logger.error("❌ Échec requête")
            return

        all_calls = result.get('outgoing', []) + result.get('incoming', [])
        logger.info(f"📦 {len(all_calls)} relations récupérées de Dgraph")

        # ✅ Déduplication par UID
        seen_uids = set()
        unique_calls = []
        for call in all_calls:
            uid = call.get('uid')
            if uid and uid not in seen_uids:
                seen_uids.add(uid)
                unique_calls.append(call)

        logger.info(f"🔹 {len(unique_calls)} relations uniques après déduplication")

        intra_file_relations = []
        matched_count = 0

        # ✅ NOUVEAU : Stocker les nœuds à créer
        nodes_to_create = {}  # nom_nœud -> metadata
        nodes_created_count = 0

        for call in unique_calls:
            source_path = call.get('sourcePath', '')
            target_path = call.get('targetPath', '')

            source_file = extract_filename(source_path)
            target_file = extract_filename(target_path)

            if not source_file or not target_file:
                continue

            is_intra = (source_file == target_file == central_file)
            is_related = (source_file == central_file or target_file == central_file)

            if not is_related:
                logger.debug(f"   ⛔ Relation non liée : {source_file} -> {target_file}")
                continue

            source_node = call.get('source', {})
            target_node = call.get('target', {})

            source_name = source_node.get('name') or call.get('sourceName', '')
            target_name = target_node.get('name') or call.get('targetName', '')

            if not source_name or not target_name:
                continue

            logger.debug(f"\n   🔍 Tentative match :")
            logger.debug(f"      Source brut : {source_name}")
            logger.debug(f"      Target brut : {target_name}")

            def find_existing_node(name):
                if name in existing_nodes_map:
                    return existing_nodes_map[name]
                normalized = self.normalize_node_name(name)
                if normalized in existing_nodes_map:
                    return existing_nodes_map[normalized]
                name_no_ext = os.path.splitext(name)[0]
                if name_no_ext in existing_nodes_map:
                    return existing_nodes_map[name_no_ext]
                normalized_no_ext = self.normalize_node_name(name_no_ext)
                if normalized_no_ext in existing_nodes_map:
                    return existing_nodes_map[normalized_no_ext]
                basename = os.path.basename(name)
                if basename in existing_nodes_map:
                    return existing_nodes_map[basename]
                basename_no_ext = os.path.splitext(basename)[0]
                if basename_no_ext in existing_nodes_map:
                    return existing_nodes_map[basename_no_ext]
                normalized_basename = self.normalize_node_name(basename_no_ext)
                if normalized_basename in existing_nodes_map:
                    return existing_nodes_map[normalized_basename]
                for key, display_name in existing_nodes_map.items():
                    if basename_no_ext.lower() in key.lower() or key.lower() in basename_no_ext.lower():
                        logger.debug(f"         Match partiel : {basename_no_ext} ~ {key}")
                        return display_name
                return None

            source_display = find_existing_node(source_name)
            target_display = find_existing_node(target_name)

            # ✅ CORRECTION : Si nœud non trouvé, préparer sa création ET l'enregistrer immédiatement
            if not source_display:
                source_display = self.normalize_node_name(source_name)
                if source_display not in nodes_to_create:
                    nodes_to_create[source_display] = {
                        'uid': source_node.get('uid') or f"ext_{uuid.uuid4()}",
                        'type': call.get('sourceType', 'function'),
                        'path': source_path
                    }
                    # ✅ AJOUT : Enregistrer dans existing_nodes_map pour éviter les doublons
                    existing_nodes_map[source_display] = source_display
                    nodes_created_count += 1
                    logger.info(f"   🆕 Nœud à créer : {source_display}")

            if not target_display:
                target_display = self.normalize_node_name(target_name)
                if target_display not in nodes_to_create:
                    nodes_to_create[target_display] = {
                        'uid': target_node.get('uid') or f"ext_{uuid.uuid4()}",
                        'type': call.get('targetType', 'function'),
                        'path': target_path
                    }
                    # ✅ AJOUT : Enregistrer dans existing_nodes_map pour éviter les doublons
                    existing_nodes_map[target_display] = target_display
                    nodes_created_count += 1
                    logger.info(f"   🆕 Nœud à créer : {target_display}")

            if source_display == target_display:
                logger.debug(f"   ⛔ Auto-référence : {source_display}")
                continue

            matched_count += 1
            logger.info(f"   ✅ MATCH {matched_count} : {source_display} → {target_display} (ligne {call.get('line', 'N/A')}, {'INTRA' if is_intra else 'INTER'})")

            relation = {
                'source': source_display,
                'source_uid': source_node.get('uid') or nodes_to_create.get(source_display, {}).get('uid'),
                'source_type': call.get('sourceType', 'function'),
                'target': target_display,
                'target_uid': target_node.get('uid') or nodes_to_create.get(target_display, {}).get('uid'),
                'target_type': call.get('targetType', 'function'),
                'relation_type': call.get('relationType', 'calls'),
                'category': 'intra_file' if is_intra else 'inter_file',
                'line': call.get('line'),
                'is_analyzed': True,
                'intraFile': is_intra
            }

            intra_file_relations.append(relation)

        logger.info(f"\n📊 Résultat matching :")
        logger.info(f"   ✅ {matched_count} relations matchées")
        logger.info(f"   🆕 {len(nodes_to_create)} nouveaux nœuds à créer")

        if not intra_file_relations:
            logger.warning("⚠️ Aucun appel détecté")
            QtWidgets.QMessageBox.information(
                self,
                "Aucune relation",
                "Aucun appel détecté pour les nœuds affichés."
            )
            return

        # Déduplication
        seen = set()
        unique = []

        for rel in intra_file_relations:
            key = (rel['source'], rel['target'], rel['relation_type'])
            if key not in seen:
                seen.add(key)
                unique.append(rel)

        logger.info(f"✅ {len(unique)} appels uniques après déduplication")

        intra_count = sum(1 for r in unique if r['category'] == 'intra_file')
        inter_count = sum(1 for r in unique if r['category'] == 'inter_file')

        logger.info(f"   🔹 INTRA-fichier : {intra_count}")
        logger.info(f"   🔹 INTER-fichiers : {inter_count}")

        # ✅ AJOUT : Ajouter les nouveaux nœuds au cache AVANT d'ajouter les relations
        for node_name, metadata in nodes_to_create.items():
            if node_name not in self._node_cache:
                # Créer un TaxonomyItem virtuel pour le cache
                from PyQt5.QtWidgets import QTreeWidgetItem

                virtual_item = TaxonomyItem(
                    None,  # Pas de parent visuel
                    node_name,
                    'function',  # Type par défaut
                    {
                        'uid': metadata['uid'],
                        'name': node_name,
                        'nodeType': metadata['type'],
                        'path': metadata['path']
                    },
                    0
                )

                self._node_cache[metadata['uid']] = virtual_item
                self._uid_set.add(metadata['uid'])

                logger.info(f"   ✅ Nœud créé dans cache : {node_name} (uid={metadata['uid']})")

        # ✅ AJOUTER LES RELATIONS (incluant les nouveaux nœuds)
        existing = {
            (r['source'], r['target'], r['relation_type']) 
            for r in self.current_relations
        }

        added = 0
        for rel in unique:
            key = (rel['source'], rel['target'], rel['relation_type'])
            if key not in existing:
                self.current_relations.append(rel)
                existing.add(key)
                added += 1

        logger.info(f"➕ {added} relations ajoutées aux relations actuelles")
        logger.info("="*70 + "\n")

        if added > 0:
            examples = [f"  • {r['source']} → {r['target']} ({'INTRA' if r['category'] == 'intra_file' else 'INTER'})" for r in unique[:5]]
            if len(unique) > 5:
                examples.append(f"  ... et {len(unique) - 5} autres")

            message = f"✅ {added} appels ajoutés !\n\n"
            message += f"📄 {self.current_central_name}\n"
            message += f"📊 Total : {len(self.current_relations)} relations\n"
            message += f"🔹 INTRA : {intra_count} | INTER : {inter_count}\n"

            # ✅ NOUVEAU : Indiquer si des nœuds ont été créés
            if nodes_created_count > 0:
                message += f"🆕 {nodes_created_count} nouveaux nœuds créés\n"

            message += f"\nExemples :\n" + "\n".join(examples) + "\n\n"
            message += f" INTRA = violet | 🟦 INTER = bleu cyan"

            QtWidgets.QMessageBox.information(
                self,
                "Relations chargées",
                message
            )

    def _remove_intra_file_relations(self):
        """❌ Supprime les relations d'appels intra-fichier."""
        if not self.current_relations:
            return

        # Filtrer pour garder uniquement les relations NON intra-fichier
        original_count = len(self.current_relations)

        self.current_relations = [
            rel for rel in self.current_relations
            if rel.get('category') != 'intra_file' and not rel.get('intraFile', False)
        ]

        removed_count = original_count - len(self.current_relations)
        logger.info(f"🗑️ {removed_count} relations intra-fichier supprimées")

    def _remove_node_origins_display(self):
        """❌ Supprime l'affichage des origines sous chaque nœud."""
        if hasattr(self, 'origin_text_objects') and self.origin_text_objects:
            for text_obj in self.origin_text_objects:
                try:
                    text_obj.remove()
                except:
                    pass
            self.origin_text_objects = []

    logger.info("🗑️ Origines masquées")

    def _get_node_path_from_relations(self, node_name: str) -> Optional[str]:
        """
        ✅ NOUVEAU : Récupère le path d'un nœud depuis les Relations Dgraph
        Utilise sourceName/targetName + sourcePath/targetPath
        """
        if not self.dgraph_connector or not node_name:
            return None

        # Nettoyer le nom (enlever préfixes)
        clean_name = node_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()

        # Échapper pour regex
        escaped = clean_name.replace('.', r'\.').replace('(', r'\(').replace(')', r'\)')

        query = f"""
        {{
          by_source(func: type(Relation)) @filter(regexp(sourceName, /{escaped}/i)) {{
            sourceName
            sourcePath
          }}

          by_target(func: type(Relation)) @filter(regexp(targetName, /{escaped}/i)) {{
            targetName
            targetPath
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if not result:
            return None

        # Chercher dans source
        for rel in result.get('by_source', []):
            source_name = rel.get('sourceName', '')
            source_path = rel.get('sourcePath', '')

            # Vérifier correspondance
            if clean_name in source_name or source_name in clean_name:
                if source_path and source_path.strip():
                    logger.debug(f"   🎯 Path trouvé via Relations (source): {source_path}")
                    return os.path.basename(source_path)

        # Chercher dans target
        for rel in result.get('by_target', []):
            target_name = rel.get('targetName', '')
            target_path = rel.get('targetPath', '')

            # Vérifier correspondance
            if clean_name in target_name or target_name in clean_name:
                if target_path and target_path.strip():
                    logger.debug(f"   🎯 Path trouvé via Relations (target): {target_path}")
                    return os.path.basename(target_path)

        return None

    def _on_internal_relations_changed(self, state):
        """✅ CORRIGÉ : Gère l'affichage/masquage des relations internes du code."""
        is_checked = (state == Qt.Checked)
    
        logger.info(f"🔄 Relations internes: {'ACTIVÉES' if is_checked else 'DÉSACTIVÉES'}")
    
        if not self.current_graph:
            logger.warning("⚠️ Aucun graphe actif")
            return
    
        if is_checked:
            # ✅ AJOUTER les relations intra-fichier
            self._add_intra_file_relations()
        else:
            # ✅ FILTRER TEMPORAIREMENT sans modifier current_relations
            # (pour permettre le re-cochage)
            relations_filtered = [
                rel for rel in self.current_relations
                if rel.get('category') != 'intra_file' and not rel.get('intraFile', False)
            ]
    
            logger.info(f"🗑️ {len(self.current_relations) - len(relations_filtered)} relations intra-fichier masquées")
    
            # ✅ Redessiner avec relations filtrées (SANS modifier current_relations)
            self.figure.clear()
            G = self._build_clean_graph(relations_filtered)
            self.current_graph = G
            self._draw_graph(G)
    
            self._update_status(
                f"Relations internes: Masquées ({len(relations_filtered)} relations affichées)"
            )
            return
    
        # ✅ Si cochage : redessiner avec TOUTES les relations
        self.figure.clear()
        G = self._build_clean_graph(self.current_relations)
        self.current_graph = G
        self._draw_graph(G)
    
        self._update_status(
            f"Relations internes: {'Affichées' if is_checked else 'Masquées'} "
            f"({len(self.current_relations)} relations totales)"
        )

    def _redraw_edges_only(self):
        """✅ NOUVEAU : Redessine uniquement les arêtes sans modifier les nœuds."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return
    
        ax = self.graph_data['ax']
        G = self.graph_data['G']
        pos = self.graph_data['pos']
        num_nodes = self.graph_data['num_nodes']
    
        # ✅ Reconstruire le graphe avec les nouvelles relations
        G_new = self._build_clean_graph(self.current_relations)
        
        # ✅ IMPORTANT : Garder les mêmes positions des nœuds
        for node in G_new.nodes():
            if node in pos:
                # Conserver position existante
                pass
            else:
                # Si nouveau nœud (ne devrait pas arriver), position par défaut
                logger.warning(f"⚠️ Nœud inattendu : {node}")
                pos[node] = [0.0, 0.0]
    
        # ✅ Mettre à jour graph_data
        self.graph_data['G'] = G_new
        self.current_graph = G_new
    
        # ✅ Effacer UNIQUEMENT les arêtes
        for artist in ax.collections + ax.patches:
            if hasattr(artist, 'get_label') and 'edge' in str(type(artist)).lower():
                artist.remove()
    
        # ✅ Redessiner UNIQUEMENT les arêtes
        edges = list(G_new.edges(data=True))
        edge_colors = [d.get('color', '#CCCCCC') for _, _, d in edges]
    
        is_global_mode = self.level_combo.currentIndex() == 0
    
        if is_global_mode:
            curvature = 0.02
            edge_width = 1.5
            edge_alpha = 0.6
            arrow_size = 12
        else:
            curvature = 0.12 if num_nodes <= 20 else 0.08
            edge_width = 2.0 if num_nodes <= 20 else 1.5
            edge_alpha = 0.7
            arrow_size = 14 if num_nodes <= 20 else 10
    
        # ✅ Dessiner les arêtes
        if num_nodes > 30:
            nx.draw_networkx_edges(
                G_new, pos, ax=ax,
                edge_color=edge_colors,
                width=edge_width,
                alpha=edge_alpha,
                arrows=True,
                arrowsize=arrow_size,
                arrowstyle='->'
            )
        else:
            nx.draw_networkx_edges(
                G_new, pos, ax=ax,
                edge_color=edge_colors,
                width=edge_width,
                alpha=edge_alpha,
                arrows=True,
                arrowsize=arrow_size,
                connectionstyle=f'arc3,rad={curvature}'
            )
    
        # ✅ Redessiner la légende
        self._draw_orbit_legend(ax, edges, self.graph_data.get('node_orbits', {}))
    
        # ✅ Rafraîchir le canvas
        self.canvas.draw_idle()
    
        logger.info(f"✅ Arêtes redessinées : {len(edges)} relations")

    def _add_internal_code_relations(self):
        """✅ Ancienne méthode : Ajoute les relations internes entre éléments de code (deprecated)."""
        logger.warning("⚠️ Méthode deprecated : utilisez _add_intra_file_relations() à la place")
        # Rediriger vers la nouvelle méthode
        self._add_intra_file_relations()


    def _remove_internal_code_relations(self):
        """❌ Supprime les relations internes du code."""
        if not self.current_relations:
            return

        # Filtrer pour garder uniquement les relations NON internes
        original_count = len(self.current_relations)

        self.current_relations = [
            rel for rel in self.current_relations
            if rel.get('category') != 'code_internal'
        ]

        removed_count = original_count - len(self.current_relations)
        logger.info(f"🗑️ {removed_count} relations internes supprimées")

    def _zoom_in(self):
        """Zoom avant centré sur le point de vue actuel."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return

        self.current_zoom += self.zoom_step
        self._apply_zoom()
        logger.info(f"🔍 Zoom avant: {self.current_zoom:.1f}x")

    def _zoom_out(self):
        """Zoom arrière."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return

        # Limite minimale
        if self.current_zoom <= 0.3:
            return

        self.current_zoom -= self.zoom_step
        self._apply_zoom()
        logger.info(f"🔍 Zoom arrière: {self.current_zoom:.1f}x")

    def _pan_view(self, dx, dy):
        """Déplace la vue dans la direction spécifiée."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            logger.warning("⚠️ Impossible de déplacer la vue : graph_data non disponible")
            return
    
        if 'ax' not in self.graph_data:
            logger.error("❌ Clé 'ax' manquante dans graph_data")
            return
    
        ax = self.graph_data['ax']
    
        # Récupérer les limites actuelles
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
    
        # ✅ CORRECTION : Facteur de déplacement adaptatif selon zoom
        # Plus on est zoomé, moins on se déplace (pour contrôle précis)
        pan_factor = 0.1 / self.current_zoom
    
        # ✅ Calculer le déplacement réel
        x_shift = dx * pan_factor * (xlim[1] - xlim[0])
        y_shift = dy * pan_factor * (ylim[1] - ylim[0])
    
        # ✅ Appliquer le déplacement
        new_xlim = (xlim[0] + x_shift, xlim[1] + x_shift)
        new_ylim = (ylim[0] + y_shift, ylim[1] + y_shift)
    
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
    
        # ✅ NE PAS redessiner les nœuds
        self.canvas.draw_idle()
    
        logger.info(f"➡️ Vue déplacée: dx={dx}, dy={dy}, zoom={self.current_zoom:.1f}x")

    def _add_minimap(self):
        """Ajoute une mini-carte pour la navigation dans les grands graphes."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return

        is_global_mode = self.graph_data.get('is_global_mode', False)

        if not is_global_mode or self.graph_data['num_nodes'] < 50:
            return  # Pas nécessaire pour petits graphes

        # Créer un petit axes en haut à gauche
        minimap_ax = self.figure.add_axes([0.02, 0.75, 0.15, 0.15])
        minimap_ax.set_facecolor('#F5F5F5')

        pos = self.graph_data['pos']
        G = self.graph_data['G']

        # Dessiner tous les nœuds en petit
        for node in G.nodes():
            x, y = pos[node]
            minimap_ax.plot(x, y, 'o', color='#888888', markersize=2)

        # Dessiner le viewport actuel
        ax = self.graph_data['ax']
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        from matplotlib.patches import Rectangle
        viewport_rect = Rectangle(
            (xlim[0], ylim[0]),
            xlim[1] - xlim[0],
            ylim[1] - ylim[0],
            fill=False,
            edgecolor='red',
            linewidth=2
        )
        minimap_ax.add_patch(viewport_rect)

        # Limites de la minimap
        minimap_ax.set_xlim(self.graph_data['x_min'] - 5, self.graph_data['x_max'] + 5)
        minimap_ax.set_ylim(self.graph_data['y_min'] - 5, self.graph_data['y_max'] + 5)
        minimap_ax.axis('off')

        self.minimap_ax = minimap_ax

    def _zoom_reset(self):
        """Réinitialise le zoom et centre la vue."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return

        ax = self.graph_data['ax']
        x_min = self.graph_data['x_min']
        x_max = self.graph_data['x_max']
        y_min = self.graph_data['y_min']
        y_max = self.graph_data['y_max']

        margin = 5.0

        # ✅ Remettre les limites originales
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        # ✅ Réinitialiser le facteur de zoom
        self.current_zoom = 1.0

        # ✅ NE PAS redessiner les nœuds
        self.canvas.draw_idle()

        logger.info("🔄 Zoom réinitialisé : vue d'ensemble")

    def _apply_zoom(self):
        """Applique le zoom en gardant le centre de la vue actuelle."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            logger.warning("⚠️ Impossible d'appliquer le zoom : graph_data non disponible")
            return

        # Vérifier les clés nécessaires
        required_keys = ['ax', 'x_min', 'x_max', 'y_min', 'y_max']
        for key in required_keys:
            if key not in self.graph_data:
                logger.error(f"❌ Clé manquante dans graph_data : {key}")
                return

        ax = self.graph_data['ax']

        # Récupérer les limites actuelles pour trouver le centre
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2

        # ✅ CORRECTION : Calculer la plage ORIGINALE (référence fixe)
        x_range_original = self.graph_data['x_max'] - self.graph_data['x_min']
        y_range_original = self.graph_data['y_max'] - self.graph_data['y_min']

        # ✅ Ajouter marges aux plages originales
        margin = 5.0
        x_range_original += 2 * margin
        y_range_original += 2 * margin

        # ✅ CORRECTION : Calculer les nouvelles plages BASÉES sur le zoom
        # Plus le zoom est grand, plus la plage est petite (effet loupe)
        x_range_zoomed = x_range_original / self.current_zoom
        y_range_zoomed = y_range_original / self.current_zoom

        # ✅ Appliquer les nouvelles limites centrées sur le point focal
        new_xlim = (x_center - x_range_zoomed/2, x_center + x_range_zoomed/2)
        new_ylim = (y_center - y_range_zoomed/2, y_center + y_range_zoomed/2)

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        # ✅ NE PAS redessiner les nœuds (ils gardent leur taille)
        # Juste rafraîchir l'affichage
        self.canvas.draw_idle()

        logger.info(f"🔍 Zoom appliqué: {self.current_zoom:.1f}x (xlim={new_xlim}, ylim={new_ylim})")

    def _clear_cache(self):
        """Vide le cache et met à jour l'interface."""
        self.query_cache.clear()
        self._update_cache_info()
        self._update_status("Cache vidé")
        QtWidgets.QMessageBox.information(self, "Cache", "Le cache a été vidé avec succès!")
    
    def _update_cache_info(self):
        """Met à jour l'affichage des infos du cache."""
        self.cache_info_label.setText(self.query_cache.get_stats())

    def _update_status(self, message_key: str, **kwargs):
        """Met à jour le statut avec message traduit"""
        message = tr(f"relation_import.status.{message_key}", **kwargs)
        logger.info(message)
        QtWidgets.QApplication.processEvents()
    
    def _draw_graph(self, G: nx.DiGraph):
        self.figure.clear()

        gs = self.figure.add_gridspec(1, 1)
        ax = self.figure.add_subplot(gs[0])
        ax.set_facecolor('white')

        num_nodes = len(G.nodes())

        if num_nodes == 0:
            ax.text(0.5, 0.5, "Aucune relation à afficher", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        if num_nodes == 1:
            ax.text(0.5, 0.5, "Un seul nœud - Aucune relation", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        is_global_mode = self.level_combo.currentIndex() == 0

        node_orbits = {}

        if self.current_central_name:
            pos, node_orbits = self._compute_grouped_layout(G, self.current_central_name)
        else:
            if num_nodes > 0:
                node_degrees = dict(G.degree())
                if node_degrees:
                    central_node = max(node_degrees, key=node_degrees.get)
                    pos, node_orbits = self._compute_grouped_layout(G, central_node)
                else:
                    if num_nodes <= 15:
                        scale = 80.0
                        k = 4.0
                        iterations = 400
                    elif num_nodes <= 30:
                        scale = 120.0
                        k = 5.5
                        iterations = 350
                    else:
                        scale = 180.0
                        k = 7.0
                        iterations = 300

                    pos = nx.spring_layout(G, k=k, iterations=iterations, seed=42, scale=scale)
            else:
                pos = {}

        # ✅ NOUVEAU : ÉCHELLE GLOBALE si graphe très dense
        if num_nodes > 50:
            # Calculer l'échelle nécessaire selon densité
            scale_factor = 1.0 + (num_nodes - 50) * 0.01  # +1% par nœud au-delà de 50
            scale_factor = min(scale_factor, 3.0)  # Maximum 3x

            logger.info(f"🔍 Application échelle globale : {scale_factor:.2f}x pour {num_nodes} nœuds")

            # Appliquer l'échelle à toutes les positions
            for node in pos:
                pos[node] *= scale_factor

        # ✅ DIMENSIONS DES NŒUDS : FIXES (pas de modification)
        if num_nodes <= 15:
            text_width = 6.0
            text_height = 1.5
            font_size = 10
            max_chars = 30
        elif num_nodes <= 30:
            text_width = 5.5
            text_height = 1.4
            font_size = 9
            max_chars = 28
        else:
            text_width = 5.0
            text_height = 1.3
            font_size = 8
            max_chars = 25
            logger.info(f"🎨 Layout calculé pour {num_nodes} nœuds (mode={'Global' if is_global_mode else 'Groupé'})")

        # ✅ DIMENSIONS AUGMENTÉES
        if num_nodes <= 15:
            text_width = 6.0
            text_height = 1.5
            font_size = 10
            max_chars = 30
        elif num_nodes <= 30:
            text_width = 5.5
            text_height = 1.4
            font_size = 9
            max_chars = 28
        else:
            text_width = 5.0
            text_height = 1.3
            font_size = 8
            max_chars = 25

        # ✅ PARAMÈTRES D'ARÊTES ADAPTÉS
        if is_global_mode:
            curvature = 0.01
            edge_width = 0.8 if num_nodes > 50 else 1.0
            edge_alpha = 0.3 if num_nodes > 50 else 0.4
            arrow_size = 6 if num_nodes > 50 else 8
        else:
            curvature = 0.12 if num_nodes <= 20 else 0.08
            edge_width = 2.0 if num_nodes <= 20 else 1.5
            edge_alpha = 0.7
            arrow_size = 14 if num_nodes <= 20 else 10

        edges = list(G.edges(data=True))
        edge_colors = [d.get('color', '#CCCCCC') for _, _, d in edges]

        # ✅ DESSINER LES ARÊTES AVEC COURBURE ADAPTATIVE
        if num_nodes > 30:
            nx.draw_networkx_edges(
                G, pos, ax=ax, 
                edge_color=edge_colors, 
                width=edge_width,
                alpha=edge_alpha, 
                arrows=True, 
                arrowsize=arrow_size,
                arrowstyle='->'
            )
        else:
            nx.draw_networkx_edges(
                G, pos, ax=ax, 
                edge_color=edge_colors, 
                width=edge_width,
                alpha=edge_alpha, 
                arrows=True, 
                arrowsize=arrow_size,
                connectionstyle=f'arc3,rad={curvature}'
            )

        from matplotlib.patches import FancyBboxPatch

        node_display_names = {}
        
        for node in G.nodes():
            x, y = pos[node]

            # Récupérer les données du nœud
            node_data = G.nodes[node]
            node_type = node_data.get('node_type', None)
            node_uid = node_data.get('uid', node)

            if node_uid in self._node_cache:
                cached_item = self._node_cache[node_uid]
                real_name = cached_item.item_data.get('name') or cached_item.item_data.get('label') or node
            else:
                real_name = node

            # ✅ CORRECTION : Formater TOUS les nœuds (y compris le central)
            formatted_name = self._format_node_display_name(node, node_type)
            display_name = formatted_name[:max_chars] + '..' if len(formatted_name) > max_chars else formatted_name

            # Déterminer la couleur APRÈS le formatage
            if node == self.current_central_name:
                color = '#8B2E1F'  # Rouge central
                edge_color = '#666666'
                linewidth = 3.0
            else:
                # Obtenir couleur depuis les relations
                color, edge_color = self._get_node_color_from_relations(G, node, self.current_central_name)
                linewidth = 2.5

            # Rectangle avec couleur de relation
            rect = FancyBboxPatch(
                (x - text_width/2, y - text_height/2),
                text_width, text_height,
                boxstyle="round,pad=0.15",
                edgecolor=edge_color,
                facecolor=color,
                alpha=0.95,
                linewidth=linewidth,
                zorder=2
            )
            ax.add_patch(rect)

            ax.text(
                x, y, display_name,
                ha='center', va='center',
                fontsize=font_size,
                fontweight='bold',
                color='white',
                zorder=3
            )
        
        # ✅ LÉGENDE AMÉLIORÉE AVEC ORBITES
        self._draw_orbit_legend(ax, edges, node_orbits)

        ax.axis('off')

        # ✅ LIMITES AVEC MARGES ADAPTATIVES
        x_coords = [pos[node][0] for node in G.nodes()]
        y_coords = [pos[node][1] for node in G.nodes()]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        if num_nodes <= 15:
            margin = 5.0
        elif num_nodes <= 30:
            margin = 4.0
        else:
            margin = 3.0

        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        # Configuration interactive
        self._setup_interactive_graph(ax, G, pos, edges, edge_colors, 
                                      {}, {}, [], [], num_nodes)

        self.info_text_obj = None

        if is_global_mode:
            self._reset_view_to_overview()
        else:
            self.current_zoom = 1.0

        self.graph_data = {
            'pos': {node: list(coord) for node, coord in pos.items()},
            'G': G,
            'ax': ax,
            'edges': edges,
            'edge_colors': edge_colors,
            'num_nodes': num_nodes,
            'dragging_node': None,
            'selected_node': None,
            'text_width': text_width,
            'text_height': text_height,
            'font_size': font_size,
            'max_chars': max_chars,
            'is_global_mode': is_global_mode,
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max,
            'node_orbits': node_orbits,
            'scale_factor': scale_factor if num_nodes > 50 else 1.0  # ✅ Sauvegarder l'échelle
        }

        self.canvas.draw()

    def _draw_orbit_legend(self, ax, edges, node_orbits):
        """
        ✅ NOUVEAU : Légende simplifiée sans orbites (seulement types de relations)
        """
        from matplotlib.lines import Line2D

        legend_elements = []

        # ===== TYPES DE RELATIONS (ARÊTES) - Afficher max 8 =====
        edge_types_seen = {}
        for _, _, d in edges:
            rel_type = d.get('relation_type', 'unknown')
            color = d.get('color', '#CCCCCC')
            if rel_type not in edge_types_seen:
                edge_types_seen[rel_type] = color

        sorted_types = sorted(edge_types_seen.items())[:8]

        for rel_type, color in sorted_types:
            legend_elements.append(
                Line2D([0], [0], color=color, linewidth=2.5, 
                      label=rel_type[:18] + '..' if len(rel_type) > 18 else rel_type,
                      marker='>', markersize=8)
            )

        if len(edge_types_seen) > 8:
            legend_elements.append(
                Line2D([0], [0], color='#999999', linewidth=2, 
                      label=f'... +{len(edge_types_seen)-8} types',
                      linestyle='--')
            )

        # ===== AFFICHER LA LÉGENDE =====
        if legend_elements:
            legend = ax.legend(
                handles=legend_elements, 
                loc='upper right',
                fontsize=7,
                title="Types de relations",
                title_fontsize=8,
                framealpha=0.95,
                edgecolor='#CCCCCC',
                fancybox=True,
                shadow=False,
                ncol=1,
                columnspacing=0.5,
                handlelength=1.5,
                handletextpad=0.5,
                borderpad=0.4,
                labelspacing=0.3
            )

            legend.set_bbox_to_anchor((0.98, 0.98))

        if hasattr(self, 'show_node_origins_cb') and self.show_node_origins_cb.isChecked():
            # Réafficher les origines sous chaque nœud
            self._add_node_origins_display()

    def _on_mouse_scroll(self, event):
        """✅ Gère le zoom à la molette de la souris."""
        if not hasattr(self, 'graph_data') or 'ax' not in self.graph_data:
            return

        if event.inaxes != self.graph_data['ax']:
            return

        # Direction du scroll (up = zoom in, down = zoom out)
        if event.button == 'up':
            # Zoom avant
            if self.current_zoom < 5.0:  # Limite max
                self.current_zoom += self.zoom_step
        elif event.button == 'down':
            # Zoom arrière
            if self.current_zoom > 0.3:  # Limite min
                self.current_zoom -= self.zoom_step
        else:
            return

        # Appliquer le zoom centré sur la position de la souris
        self._apply_zoom_at_point(event.xdata, event.ydata)

        logger.info(f"🔍 Zoom molette: {self.current_zoom:.1f}x")

    def _apply_zoom_at_point(self, x_focus, y_focus):
        """Applique le zoom en gardant le point focal fixe."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            return

        required_keys = ['ax', 'x_min', 'x_max', 'y_min', 'y_max']
        for key in required_keys:
            if key not in self.graph_data:
                return

        ax = self.graph_data['ax']

        # Si pas de point focal (zoom depuis boutons), utiliser le centre
        if x_focus is None or y_focus is None:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_focus = (xlim[0] + xlim[1]) / 2
            y_focus = (ylim[0] + ylim[1]) / 2

        # ✅ CORRECTION : Calculer la plage ORIGINALE (référence fixe)
        x_range_original = self.graph_data['x_max'] - self.graph_data['x_min']
        y_range_original = self.graph_data['y_max'] - self.graph_data['y_min']

        # ✅ Ajouter marges
        margin = 5.0
        x_range_original += 2 * margin
        y_range_original += 2 * margin

        # ✅ Nouvelles plages basées sur le zoom
        x_range = x_range_original / self.current_zoom
        y_range = y_range_original / self.current_zoom

        # ✅ Centrer sur le point focal
        new_xlim = (x_focus - x_range/2, x_focus + x_range/2)
        new_ylim = (y_focus - y_range/2, y_focus + y_range/2)

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        # ✅ NE PAS redessiner les nœuds
        self.canvas.draw_idle()

    def _apply_universal_collision_avoidance(self, G, pos, num_nodes):
        import numpy as np

        def get_node_distance_from_center(node):
            """Calcule la distance d'un nœud par rapport au centre"""
            x, y = pos[node]
            return (x**2 + y**2) ** 0.5

        # ✅ PARAMÈTRES ADAPTATIFS (distances minimales RÉDUITES car on a des rayons plus grands)
        if num_nodes <= 10:
            base_min_distance = 1.8  # Réduit de 2.5
            iterations = 100
            orbit_tolerance = 2.0
        elif num_nodes <= 20:
            base_min_distance = 1.5  # Réduit de 2.0
            iterations = 80
            orbit_tolerance = 2.5
        elif num_nodes <= 40:
            base_min_distance = 1.2  # Réduit de 1.8
            iterations = 60
            orbit_tolerance = 3.0
        else:
            base_min_distance = 1.0  # Réduit de 1.5
            iterations = 50
            orbit_tolerance = 3.5

        # ✅ Dimensions FIXES des nœuds (récupérées depuis graph_data)
        text_width = self.graph_data.get('text_width', 5.0)
        text_height = self.graph_data.get('text_height', 1.3)

        # Calculer les distances initiales
        node_distances = {}
        for node in G.nodes():
            node_distances[node] = get_node_distance_from_center(node)

        node_orbits = self.graph_data.get('node_orbits', {})

        for iteration in range(iterations):
            nodes = list(G.nodes())
            max_displacement = 0

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]
                dist1 = node_distances[node1]

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]
                    dist2 = node_distances[node2]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # ✅ Distance requise basée sur dimensions FIXES + marge
                    required_distance = (text_width + text_height) / 2 + base_min_distance

                    if distance < required_distance and distance > 0.01:
                        # Force diminuant avec les itérations
                        force_factor = 1.0 - (iteration / iterations) * 0.5

                        # Vérifier même orbite
                        orbit1 = node_orbits.get(node1, 3)
                        orbit2 = node_orbits.get(node2, 3)
                        same_orbit = (orbit1 == orbit2) or (abs(dist1 - dist2) < orbit_tolerance)

                        if same_orbit:
                            # ✅ MOUVEMENT TANGENTIEL (rotation)
                            angle1 = math.atan2(y1, x1)
                            angle2 = math.atan2(y2, x2)

                            force = (required_distance - distance) * 0.015 * force_factor  # Force réduite
                            avg_radius = (dist1 + dist2) / 2

                            if avg_radius > 0.01:
                                angle_force = force / avg_radius
                            else:
                                angle_force = force * 0.1

                            # Rotation inverse
                            new_angle1 = angle1 - angle_force
                            new_angle2 = angle2 + angle_force

                            # ✅ GARDER LE MÊME RAYON
                            pos[node1][0] = dist1 * math.cos(new_angle1)
                            pos[node1][1] = dist1 * math.sin(new_angle1)
                            pos[node2][0] = dist2 * math.cos(new_angle2)
                            pos[node2][1] = dist2 * math.sin(new_angle2)

                            max_displacement = max(max_displacement, angle_force * avg_radius)

                        else:
                            # ✅ MOUVEMENT RADIAL
                            if dist1 > 0.01:
                                radial_dir1_x = x1 / dist1
                                radial_dir1_y = y1 / dist1
                            else:
                                radial_dir1_x = 1.0
                                radial_dir1_y = 0.0

                            if dist2 > 0.01:
                                radial_dir2_x = x2 / dist2
                                radial_dir2_y = y2 / dist2
                            else:
                                radial_dir2_x = 1.0
                                radial_dir2_y = 0.0

                            radial_force = (required_distance - distance) * 0.2 * force_factor  # Force réduite

                            if dist1 < dist2:
                                pos[node1][0] -= radial_force * radial_dir1_x
                                pos[node1][1] -= radial_force * radial_dir1_y
                                pos[node2][0] += radial_force * radial_dir2_x
                                pos[node2][1] += radial_force * radial_dir2_y
                            else:
                                pos[node2][0] -= radial_force * radial_dir2_x
                                pos[node2][1] -= radial_force * radial_dir2_y
                                pos[node1][0] += radial_force * radial_dir1_x
                                pos[node1][1] += radial_force * radial_dir1_y

                            max_displacement = max(max_displacement, radial_force)

                    # Mettre à jour distance
                    node_distances[node1] = get_node_distance_from_center(node1)

            # Convergence
            if max_displacement < 0.01:
                logger.info(f"✅ Convergence à l'itération {iteration}")
                break

        return pos

    def _reset_view_to_overview(self):
        """Réinitialise la vue pour afficher tout le graphe."""
        if not hasattr(self, 'graph_data') or not self.graph_data:
            logger.warning("⚠️ Impossible de réinitialiser la vue : graph_data non disponible")
            return

        # Vérifier que toutes les clés nécessaires existent
        required_keys = ['ax', 'x_min', 'x_max', 'y_min', 'y_max']
        for key in required_keys:
            if key not in self.graph_data:
                logger.error(f"❌ Clé manquante dans graph_data : {key}")
                return

        ax = self.graph_data['ax']
        x_min = self.graph_data['x_min']
        x_max = self.graph_data['x_max']
        y_min = self.graph_data['y_min']
        y_max = self.graph_data['y_max']

        margin = 5.0

        # ✅ Remettre les limites originales
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        # ✅ Réinitialiser le zoom
        self.current_zoom = 1.0

        # ✅ NE PAS redessiner les nœuds
        self.canvas.draw_idle()

        logger.info("🔄 Vue réinitialisée : vue d'ensemble")

    def _apply_rectangle_collision_avoidance_global(self, G, pos, num_nodes):
        """✅ Collision avoidance pour mode GLOBAL - DIMENSIONS FIXES 4.0 x 1.2"""

        # ✅ Distances minimales TRÈS LARGES basées sur dimensions fixes
        if num_nodes <= 20:
            min_distance = 8.0   # Augmenté pour rectangles 4.0 x 1.2
        elif num_nodes <= 50:
            min_distance = 7.0
        elif num_nodes <= 100:
            min_distance = 6.5
        elif num_nodes <= 200:
            min_distance = 6.0
        else:
            min_distance = 5.5

        iterations = 120 if num_nodes <= 50 else 100

        for iteration in range(iterations):
            nodes = list(G.nodes())

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]

                # ✅ Dimensions STRICTEMENT FIXES (même que dans _draw_graph)
                w1 = 4.0
                h1 = 1.2

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    w2 = 4.0
                    h2 = 1.2

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # Distance requise basée sur rectangles fixes + marge
                    required_distance = (w1 + w2) / 2 + min_distance

                    if distance < required_distance and distance > 0.01:
                        angle_cos = dx / distance
                        angle_sin = dy / distance

                        # Force de répulsion
                        force = (required_distance - distance) / 8

                        # Appliquer la force
                        pos[node1][0] -= force * angle_cos
                        pos[node1][1] -= force * angle_sin
                        pos[node2][0] += force * angle_cos
                        pos[node2][1] += force * angle_sin

            # Réduction très progressive
            if iteration % 50 == 0:
                min_distance *= 0.985

        return pos

    def _apply_rectangle_collision_avoidance(self, G, pos, num_nodes):
        """✅ Collision avoidance adapté aux rectangles avec noms"""

        # Distance minimale adaptée
        if num_nodes <= 10:
            min_distance = 1.2
        elif num_nodes <= 20:
            min_distance = 1.0
        elif num_nodes <= 50:
            min_distance = 0.8
        else:
            min_distance = 0.6

        iterations = 150 if num_nodes <= 30 else 100

        for iteration in range(iterations):
            nodes = list(G.nodes())

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]

                # Calculer largeur rectangle node1
                name1 = node1[:25] if len(node1) <= 25 else node1[:25] + '..'
                w1 = len(name1) * 0.08
                h1 = 0.3

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    # Calculer largeur rectangle node2
                    name2 = node2[:25] if len(node2) <= 25 else node2[:25] + '..'
                    w2 = len(name2) * 0.08
                    h2 = 0.3

                    # Distance entre centres
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # Distance minimale = somme des demi-largeurs + marge
                    required_distance = (w1 + w2) / 2 + min_distance

                    if distance < required_distance and distance > 0.01:
                        # Calculer force de répulsion
                        angle_cos = dx / distance
                        angle_sin = dy / distance

                        force = (required_distance - distance) / 6

                        # Appliquer la force
                        pos[node1][0] -= force * angle_cos
                        pos[node1][1] -= force * angle_sin
                        pos[node2][0] += force * angle_cos
                        pos[node2][1] += force * angle_sin

            # Réduction progressive de la distance minimale
            if iteration % 20 == 0:
                min_distance *= 0.98

        return pos

    def _load_projects_list(self):
        """Charge la liste des projets depuis Dgraph."""
        if not self.dgraph_connector or not self.dgraph_connector.client:
            self._update_status("Erreur: Connexion Dgraph non disponible")
            return
        
        try:
            self._show_progress("Chargement des projets...", 0)
            
            query = """
            {
              q(func: type(Workspace)) {
                uid
                name
                description
                ownerId
                updatedAt
              }
            }
            """
            result = self._execute_dgraph_query(query)
            
            if not result or 'q' not in result:
                self._update_status("Aucun projet trouvé")
                self._hide_progress()
                return
            
            self.project_combo.blockSignals(True)
            self.project_combo.clear()
            self.project_combo.addItem("Sélectionnez un projet...", None)
            
            # ✅ CORRECTION : Dédupliquer par UID ET par nom
            seen_uids = set()
            seen_names = set()  # ✅ NOUVEAU : Suivre aussi les noms
            
            for ws in result['q']:
                uid = ws.get('uid')
                name = ws.get('name', 'Projet')
                
                # ✅ CORRECTION : Ignorer si UID déjà vu OU nom déjà vu
                if uid and uid not in seen_uids and name not in seen_names:
                    seen_uids.add(uid)
                    seen_names.add(name)  # ✅ NOUVEAU : Enregistrer le nom
                    self.project_combo.addItem(f"{name}", ws)
            
            self.project_combo.blockSignals(False)
            
            self._hide_progress()
            self._update_status(f"{self.project_combo.count() - 1} projet(s) disponible(s)")
    
        
        except Exception as e:
            logger.error(f"Erreur chargement projets: {e}")
            self._update_status(f"Erreur: {str(e)}")
            self._hide_progress()
    
    def _on_project_selected(self, index):
        """Gestion du changement de projet sélectionné."""
        if index <= 0:
            self.tree_widget.clear()
            self.current_project_data = None
            self.current_central_uid = None
            self.current_central_name = None
            self._show_empty_graph("Sélectionnez un projet")
            return

        selected_data = self.project_combo.itemData(index)
        
        if selected_data:
            self._load_project_data(selected_data)
            self._update_status(f"Projet sélectionné: {selected_data.get('name', '')}")
    
    def _load_project_data(self, selected_data):
        """Charge les données du projet depuis Dgraph avec hiérarchie complète."""
        self.current_project_data = selected_data
        
        self.current_central_uid = None
        self.current_central_name = None
        
        self._show_progress("Chargement des mappings...", 10)
        self._load_uid_mappings()
        
        self._update_progress(30, "Chargement de la hiérarchie...")
        
        uid = selected_data.get('uid')
        query = f"""
        {{
          project(func: uid({uid})) {{
            uid name
            clusterManagement {{
              uid
              clusters {{
                uid name path nodeType
                root_labels: ~clusters @filter(eq(level, 0)) {{
                  uid name label path category nodeType local_id
                  level1: ~parents @filter(eq(level, 1)) {{
                    uid name label path category nodeType local_id
                    level2: ~parents @filter(eq(level, 2)) {{
                      uid name label path category nodeType local_id
                      level3: ~parents @filter(eq(level, 3)) {{
                        uid name label path category nodeType local_id
                        level4: ~parents @filter(eq(level, 4)) {{
                          uid name label path category nodeType local_id
                          level5: ~parents @filter(eq(level, 5)) {{
                            uid name label path category nodeType local_id
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        if result and 'project' in result and result['project']:
            self.current_project_data = result['project'][0]
            self._update_progress(80, "Construction de l'arbre...")
            self._build_project_tree()
            
            self._hide_progress()

            if self.level_combo.currentIndex() == 0:
                self._show_project_cluster_view()
            else:
                self._show_empty_graph("Sélectionnez un nœud dans l'arbre\npour afficher ses relations")
    
    def _build_project_tree(self):
        """
        ✅ CORRIGÉ : Construit l'arbre du projet avec tous les clusters
        """
        self.tree_widget.clear()
        if not self.current_project_data:
            return

        cm = self.current_project_data.get('clusterManagement', {})

        self._node_cache.clear()
        self._name_cache.clear()
        self._uid_set.clear()

        seen_uids = set()
        clusters = cm.get('clusters', [])
        total_clusters = len(clusters)

        logger.info(f"🗂️ Construction de l'arbre avec {total_clusters} clusters")

        for cluster_idx, cluster in enumerate(clusters):
            cluster_uid = cluster.get('uid')
            if cluster_uid in seen_uids:
                continue
            seen_uids.add(cluster_uid)

            self._build_cluster_tree(cluster, cluster_idx, total_clusters)

        self.tree_widget.expandAll()
        self._load_taxonomy_structure()
        logger.info(f"✅ Arbre construit: {len(self._uid_set)} éléments uniques")

    def _build_cluster_tree(self, cluster, cluster_idx, total_clusters):
        """
        Construction récursive COMPLÈTE d'un cluster (une seule définition !)
        """
        cluster_name = cluster.get('name') or cluster.get('id') or "Cluster sans nom"
        cluster_uid = cluster.get('uid', '')

        logger.info(f"\n[{cluster_idx + 1}/{total_clusters}] 📦 Cluster: {cluster_name}")

        # Vérification doublon
        if cluster_uid and cluster_uid in self._uid_set:
            logger.debug(f"  ⏭️ Cluster déjà affiché (uid={cluster_uid})")
            return

        cache_key = (cluster_name, 0)
        if cache_key in self._name_cache:
            logger.debug(f"  ⏭️ Cluster déjà affiché (nom={cluster_name})")
            return

        # Créer l'item cluster
        cluster_item = TaxonomyItem(
            self.tree_widget,
            cluster_name,
            'folder',
            cluster,
            0
        )
        cluster_item.is_expandable = False
        cluster_item.loaded = True

        # Cache
        if cluster_uid:
            self._node_cache[cluster_uid] = cluster_item
            self._uid_set.add(cluster_uid)
        self._name_cache[cache_key] = cluster_item

        # Traiter les root_labels
        root_labels = cluster.get('root_labels', [])

        if not root_labels:
            logger.info(f"  ⚠️ Aucun root_label → Création label virtuel")
            virtual_label = {
                'uid': cluster_uid,
                'name': cluster_name,
                'label': cluster_name,
                'level': 1,
                'nodeType': cluster.get('nodeType', 'file'),
                'path': '',
                'description': cluster.get('description', ''),
                'files': cluster.get('files', []),
                'fileContents': cluster.get('fileContents', ''),
                'classes': [],
                'functions': [],
                'variables': [],
                'level1': []
            }

            self._build_label_tree_recursive(
                parent_item=cluster_item,
                label_data=virtual_label,
                level=1
            )
        else:
            logger.info(f"  📄 {len(root_labels)} root_labels")

            for root_label in root_labels:
                label_name = root_label.get('name') or root_label.get('label', '')

                # Forcer type correct si extension détectée
                if self._has_extension(label_name):
                    root_label['nodeType'] = 'file'

                self._build_label_tree_recursive(
                    parent_item=cluster_item,
                    label_data=root_label,
                    level=1
                )

    def _build_label_tree_recursive(self, parent_item, label_data, level):
        """
        ✅ Construction récursive des labels (fichiers / sous-dossiers)
        """
        label_name = label_data.get("name") or label_data.get("label") or f"Label_{level}"
        label_uid = label_data.get("uid", f"label_{uuid.uuid4()}")

        # ✅ S'assurer que path est présent dans item_data
        if 'path' not in label_data and 'sourcePath' not in label_data:
            # Essayer de construire un path depuis le parent
            if hasattr(parent_item, 'item_data'):
                parent_path = parent_item.item_data.get('path') or parent_item.item_data.get('sourcePath', '')
                if parent_path:
                    label_data['path'] = os.path.join(parent_path, label_name)

        # Déterminer le type de nœud
        node_type = label_data.get("nodeType", "folder")
        if label_name.endswith((".py", ".js", ".java", ".cpp")):
            node_type = "file"

        label_item = TaxonomyItem(
            parent_item,
            label_name,
            node_type,
            label_data,
            level
        )
        label_item.loaded = True
        label_item.is_expandable = False

        if label_uid:
            self._node_cache[label_uid] = label_item
            self._uid_set.add(label_uid)

        # Ajouter les éléments internes (classes, fonctions, variables)
        for cls in label_data.get("classes", []):
            cls_item = TaxonomyItem(label_item, cls.get("name", "Classe"), "class", cls, level + 1)
            cls_item.loaded = True

        for func in label_data.get("functions", []):
            func_item = TaxonomyItem(label_item, func.get("name", "Fonction"), "function", func, level + 1)
            func_item.loaded = True

        for var in label_data.get("variables", []):
            var_item = TaxonomyItem(label_item, var.get("name", "Variable"), "variable", var, level + 1)
            var_item.loaded = True

        # Charger récursivement les sous-niveaux
        for child_level in [f"level{level}", "children", "level1", "level2", "level3"]:
            children = label_data.get(child_level, [])
            for child in children:
                self._build_label_tree_recursive(label_item, child, level + 1)
    
    def _detect_item_type_improved(self, item_data, item_name):
        """✅ Détection robuste du type d'élément avec priorité aux fichiers"""
        if self._has_extension(item_name):
            return "file"

        node_type = item_data.get('nodeType', '').lower()
        if node_type:
            type_mapping = {
                'file': 'file',
                'folder': 'folder',
                'directory': 'folder',
                'function': 'function',
                'class': 'class',
                'method': 'function',
                'variable': 'variable',
                'module': 'folder',
                'label': 'folder'
            }
            if node_type in type_mapping:
                return type_mapping[node_type]

        item_type = item_data.get('type', '').lower()
        if item_type in ['file', 'folder', 'directory', 'function', 'class', 'variable']:
            return item_type if item_type != 'directory' else 'folder'

        categories = item_data.get('category', [])
        if 'file' in categories:
            return "file"
        if 'folder' in categories or 'directory' in categories:
            return "folder"

        if item_data.get('files') or item_data.get('fileContents'):
            return "file"

        has_children = (
            len(item_data.get('children', [])) > 0 or
            len(item_data.get('classes', [])) > 0 or
            len(item_data.get('functions', [])) > 0 or
            len(item_data.get('variables', [])) > 0
        )

        return "folder" if has_children else "file"
    
    def _load_taxonomy_structure(self):
        """
        ✅ VERSION CORRIGÉE : Charge TOUS les éléments (clusters + orphelins)
        """
        logger.info("\n" + "="*70)
        logger.info("📂 CHARGEMENT STRUCTURE TAXONOMY HIÉRARCHIQUE")
        logger.info("="*70)

        self.tree_widget.clear()

        # ✅ Réinitialiser les caches
        self._node_cache.clear()
        self._name_cache.clear()
        self._uid_set.clear()

        # Récupérer clusters
        clusters = self._get_clusters_data()

        logger.info(f"📦 {len(clusters)} clusters récupérés")

        if not clusters:
            empty = QtWidgets.QTreeWidgetItem(self.tree_widget)
            empty.setText(0, "(Aucune donnée disponible)")
            empty.setForeground(0, QBrush(QColor("#999999")))
            return

        # ✅ Tracer tous les UIDs déjà affichés dans les clusters
        displayed_in_clusters = set()

        # Construire l'arbre des clusters
        for cluster_idx, cluster in enumerate(clusters):
            self._build_cluster_tree(cluster, cluster_idx, len(clusters))

            # ✅ Enregistrer tous les root_labels de ce cluster
            for root_label in cluster.get('root_labels', []):
                label_uid = root_label.get('uid')
                if label_uid:
                    displayed_in_clusters.add(label_uid)

        # ✅ NOUVEAU : Charger les labels orphelins (pas dans les clusters)
        self._load_orphan_labels(displayed_in_clusters)

        logger.info(f"\n✅ Structure complète affichée")
        logger.info(f"📊 Total items: {len(self._node_cache)}")
        logger.info(f"🔒 UIDs uniques: {len(self._uid_set)}")

    def _load_orphan_labels(self, displayed_uids: set):
        """
        ✅ NOUVEAU : Charge les labels niveau 0 NON affichés dans les clusters
        """
        if not self.dgraph_connector:
            return

        query = """
        {
          orphans(func: type(Label)) @filter(eq(level, 0)) {
            uid
            name
            label
            nodeType
            path
            files
            fileContents
            description

            classes {
              uid
              name
              description
              line
            }

            functions {
              uid
              name
              description
              line
            }

            variables {
              uid
              name
              description
              line
            }

            children: ~parents {
              uid
              name
              label
              nodeType
              level
            }
          }
        }
        """

        result = self._execute_dgraph_query(query)

        if not result or 'orphans' not in result:
            logger.info("ℹ️  Aucun label orphelin trouvé")
            return

        orphans = result['orphans']

        # ✅ Filtrer ceux déjà affichés
        true_orphans = [
            label for label in orphans 
            if label.get('uid') and label.get('uid') not in displayed_uids
        ]

        if not true_orphans:
            logger.info("ℹ️  Tous les labels sont dans des clusters")
            return

        logger.info(f"\n📌 {len(true_orphans)} LABELS ORPHELINS DÉTECTÉS")

        # ✅ Créer un groupe "Fichiers isolés"
        orphan_group = TaxonomyItem(
            self.tree_widget,
            f"📦 Fichiers isolés ({len(true_orphans)})",
            "folder",
            {'uid': 'orphan_group', 'name': 'Orphans'},
            0
        )
        orphan_group.loaded = True
        orphan_group.is_expandable = False

        # ✅ Ajouter chaque orphelin
        for orphan in true_orphans:
            orphan_name = orphan.get('name') or orphan.get('label', 'Fichier sans nom')
            orphan_uid = orphan.get('uid')

            # Détection type
            orphan_type = 'file' if self._has_extension(orphan_name) else 'folder'

            logger.info(f"  ➕ {orphan_name} (type={orphan_type}, uid={orphan_uid})")

            orphan_item = TaxonomyItem(
                orphan_group,
                orphan_name,
                orphan_type,
                orphan,
                1
            )
            orphan_item.loaded = True
            orphan_item.is_expandable = False

            # Ajouter éléments de code
            self._add_all_code_elements(orphan_item, orphan, 1)

            # Cache
            if orphan_uid:
                self._node_cache[orphan_uid] = orphan_item
                self._uid_set.add(orphan_uid)
    
    def _add_all_code_elements(self, parent_item, data, level):
        """
        ✅ VERSION SANS FALLBACK : Affiche uniquement les éléments avec noms valides
        (IDENTIQUE à taxonomy_dialog.py)
        """
        stats = {
            'classes': 0,
            'functions': 0,
            'variables': 0,
            'total': 0
        }

        def has_valid_name(element):
            """Vérifie si un élément a un nom RÉEL (non vide, non None)"""
            name = element.get('name')
            if not name:
                return False

            name = name.strip()
            if not name:
                return False

            # Rejeter les noms génériques/générés
            if name.startswith(('Unnamed', 'class-', 'func-', 'var-', 'method-')):
                return False

            return True

        # ✅ 1. CLASSES
        classes = data.get('classes', [])
        for cls in classes:
            cls_uid = cls.get('uid', '')

            if cls_uid and cls_uid in self._uid_set:
                continue
            
            if not has_valid_name(cls):
                logger.debug(f"   ⏭️ Classe ignorée : pas de nom valide (uid={cls_uid})")
                continue
            
            cls_name = cls.get('name').strip()

            logger.debug(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

            cls_item = TaxonomyItem(
                parent_item,
                cls_name,
                'class',
                cls,
                level + 1
            )
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            stats['classes'] += 1
            stats['total'] += 1

            methods = cls.get('methods', [])
            for method in methods:
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                if not has_valid_name(method):
                    logger.debug(f"      ⏭️ Méthode ignorée : pas de nom valide")
                    continue
                
                method_name = method.get('name').strip()

                logger.debug(f"      ⚙️ Méthode: '{method_name}' (uid={method_uid})")

                method_item = TaxonomyItem(
                    cls_item,
                    method_name,
                    'function',
                    method,
                    level + 2
                )
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

            cls_vars = cls.get('variables', [])
            for var in cls_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                if not has_valid_name(var):
                    logger.debug(f"      ⏭️ Variable ignorée : pas de nom valide")
                    continue
                
                var_name = var.get('name').strip()

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                var_item = TaxonomyItem(
                    cls_item,
                    var_name,
                    'variable',
                    var,
                    level + 2
                )
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        functions = data.get('functions', [])
        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            if not has_valid_name(func):
                logger.debug(f"   ⏭️ Fonction ignorée : pas de nom valide (uid={func_uid})")
                continue
            
            func_name = func.get('name').strip()

            logger.debug(f"   ⚙️ Fonction: '{func_name}' (uid={func_uid})")

            func_item = TaxonomyItem(
                parent_item,
                func_name,
                'function',
                func,
                level + 1
            )
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

            stats['functions'] += 1
            stats['total'] += 1

            # Variables de la fonction
            func_vars = func.get('variables', [])
            for var in func_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                if not has_valid_name(var):
                    continue
                
                var_name = var.get('name').strip()

                var_item = TaxonomyItem(
                    func_item,
                    var_name,
                    'variable',
                    var,
                    level + 2
                )
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        # ✅ 3. VARIABLES GLOBALES
        variables = data.get('variables', [])
        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            if not has_valid_name(var):
                logger.debug(f"   ⏭️ Variable globale ignorée : pas de nom valide")
                continue
            
            var_name = var.get('name').strip()

            logger.debug(f"   📦 Variable globale: '{var_name}' (uid={var_uid})")

            var_item = TaxonomyItem(
                parent_item,
                var_name,
                'variable',
                var,
                level + 1
            )
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

            stats['variables'] += 1
            stats['total'] += 1

        return stats

    def _add_labels_to_tree(self, parent_item, labels, level, current_path):
        """Ajoute récursivement tous les labels dans l'arbre."""
        if not labels:
            return
            
        seen_uids = set()
        for label in labels:
            label_uid = label.get('uid')
            if label_uid in seen_uids:
                continue
            seen_uids.add(label_uid)
            
            name = label.get('name') or label.get('label', 'Item')
            full_path = os.path.join(current_path, name) if current_path else name
            item_type = self._detect_item_type(label, name, parent_item)
            
            item_data = label.copy()
            if item_type == "file":
                item_data['full_path'] = full_path
            
            item = TaxonomyItem(parent_item, name, item_type, item_data, level)
            
            children = []
            
            for level_key in [f'level{i}' for i in range(1, 11)]:
                if level_key in label:
                    children.extend(label.get(level_key, []))
            
            if not children:
                children = label.get('~parents', [])
            
            if not children:
                children = label.get('parents', [])
            
            child_path = full_path if item_type == "folder" else current_path
            if children:
                self._add_labels_to_tree(item, children, level + 1, child_path)

    def _on_tree_selection(self):
        items = self.tree_widget.selectedItems()
        if not items:
            self._show_empty_graph("Aucun élément sélectionné")
            return

        item = items[0]
        if isinstance(item, TaxonomyItem):
            self.current_central_uid = item.item_data.get('uid')
            self.current_central_name = self.normalize_node_name(
                item.item_data.get('name') or item.item_data.get('label') or item.text(0)
            )

            logger.info(f"📍 Nœud sélectionné: {self.current_central_name} (UID: {self.current_central_uid})")

            if not self.current_central_uid:
                logger.error("❌ UID du nœud sélectionné est None/vide!")
                self._show_empty_graph(f"Erreur: UID manquant pour {self.current_central_name}")
                return

            if not self.current_central_name:
                logger.error("❌ Nom du nœud normalisé est None/vide!")
                self._show_empty_graph("Erreur: Nom invalide")
                return

            current_index = self.level_combo.currentIndex()
            self._on_level_changed(current_index)

    def _execute_dgraph_query(self, query):
        """Exécute une requête Dgraph."""
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph connector non disponible")
            return None
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            try:
                resp = txn.query(query)
                return self.dgraph_connector._parse_response(resp)
            finally:
                txn.discard()
        except Exception as e:
            logger.error(f"Erreur requête Dgraph: {e}")
            return None

    def _detect_item_type(self, item_data, item_name, parent_item):
        """Détecte intelligemment le type d'item - CORRIGÉ pour classes/variables."""
        if self._has_extension(item_name):
            return "file"

        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "folder":
            return "folder"

        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "file":
            if item_data.get('type') == 'class' or self._is_class_name(item_name):
                return "class"
            if self._is_function_name(item_name) or item_data.get('type') == 'method':
                return "method" if parent_item.item_type == "class" else "function"
            if self._is_variable_name(item_name) or item_data.get('type') == 'variable':
                return "variable"
            return "function"

        return "folder"

    def _has_extension(self, filename):
        """✅ Vérifie si le nom a une extension de fichier (amélioré)"""
        if not filename or not isinstance(filename, str):
            return False

        filename = filename.strip()

        known_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', 
            '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg',
            '.html', '.css', '.scss', '.sass', '.less',
            '.md', '.txt', '.log', '.csv',
            '.sh', '.bat', '.ps1'
        }

        filename_lower = filename.lower()
        for ext in known_extensions:    
            if filename_lower.endswith(ext):
                return True

        if '.' in filename:
            ext = filename.split('.')[-1]
            if 2 <= len(ext) <= 5 and ext.isalnum():
                return True

        return False

    def _get_color_for_type(self, rel_type):
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()

        # ===== PRIORITÉ 1 : RELATIONS INTRA-FICHIER (VIOLET) =====
        intra_file_colors = {
            'intra_file': '#9C27B0',      # Violet
            'calls': '#9C27B0',           # Violet pour appels internes
            'method_call': '#9C27B0',     # Violet pour appels de méthodes
        }

        # ===== ORBITE 1 : RELATIONS HIÉRARCHIQUES (Verts) =====
        hierarchical_colors = {
            'parent': '#5CAD56',        # Vert standard
            'child': '#66BB6A',         # Vert clair
            'contains': '#4CAF50',      # Vert moyen
            'belongs_to': '#81C784',    # Vert très clair
            'hierarchy': '#5CAD56',     # Vert standard
        }

        # ===== ORBITE 2 : RELATIONS DE CODE (Cyans) =====
        code_colors = {
            'function_call': '#00BCD4',    # Cyan
            'call': '#00BCD4',             # Cyan
            'called_by': '#26C6DA',        # Cyan clair
            'uses': '#00ACC1',             # Cyan foncé
            'used_by': '#4DD0E1',          # Cyan très clair
            'implements': '#00838F',       # Cyan très foncé
            'extends': '#006064',          # Cyan ultra foncé
            'heritage': '#00695C',         # Teal foncé
            'inherit': '#00796B',          # Teal
        }

        # ===== ORBITE 3 : RELATIONS EXTERNES (Oranges) =====
        external_colors = {
            'import': '#FF8C00',           # Orange foncé
            'from_import': '#FF9800',      # Orange standard
            'require': '#FFA726',          # Orange clair
            'include': '#FFB74D',          # Orange très clair
            'dependency': '#F57C00',       # Orange très foncé
        }

        # ===== RELATIONS SPÉCIALES (Violets/Roses) =====
        special_colors = {
            'relation': '#8A2BE2',         # Violet
            'relation_inverse': '#9370DB', # Violet clair
            'custom': '#BA68C8',           # Violet-rose
        }

        # ===== RECHERCHE DANS LES DICTIONNAIRES =====
        # 0. Intra-file (PRIORITÉ ABSOLUE)
        for key, color in intra_file_colors.items():
            if key in rel_lower:
                return color

        # 1. Hiérarchiques
        for key, color in hierarchical_colors.items():
            if key in rel_lower:
                return color

        # 2. Code
        for key, color in code_colors.items():
            if key in rel_lower:
                return color

        # 3. Externes
        for key, color in external_colors.items():
            if key in rel_lower:
                return color

        # 4. Spéciales
        for key, color in special_colors.items():
            if key in rel_lower:
                return color

        # ===== COULEUR PAR DÉFAUT (Gris) =====
        return '#999999'
    
    def _setup_checkbox_style(self):
        """Configure le style des checkboxes pour afficher une vraie coche"""
        checkbox_style = """
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #999;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #4CAF50;
                border-color: #4CAF50;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZpZXdCb3g9IjAgMCAxOCAxOCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNNiAxMEw4IDEyTDEyIDgiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
            }
            QCheckBox::indicator:hover {
                border-color: #666;
            }
        """
        return checkbox_style

    def _get_node_color_from_relations(self, G, node, center_node):
        """
        ✅ NOUVEAU : Détermine la couleur d'un nœud selon ses relations dominantes
        Retourne (node_color, edge_color)
        """
        HIERARCHICAL_TYPES = {'parent', 'child', 'contains', 'belongs_to', 'hierarchy', 'has'}
        CODE_TYPES = {'call', 'calls', 'method_call', 'function_call', 'uses', 'used_by',
                      'implements', 'extends', 'inherits', 'override', 'invoke'}
        EXTERNAL_TYPES = {'import', 'from_import', 'require', 'include', 'dependency', 'external'}

        # Compter les types de relations
        hierarchical_count = 0
        code_count = 0
        external_count = 0

        # Relations sortantes depuis le centre
        if center_node and G.has_edge(center_node, node):
            edge_data = G[center_node][node]
            rel_type = edge_data.get('relation_type', '').lower()
            category = edge_data.get('category', '').lower()

            if any(t in rel_type for t in HIERARCHICAL_TYPES) or category == 'hierarchy':
                hierarchical_count += 1
            elif any(t in rel_type for t in CODE_TYPES) or category in ['code', 'internal']:
                code_count += 1
            elif any(t in rel_type for t in EXTERNAL_TYPES) or category == 'external':
                external_count += 1

        # Relations entrantes vers le centre
        if center_node and G.has_edge(node, center_node):
            edge_data = G[node][center_node]
            rel_type = edge_data.get('relation_type', '').lower()
            category = edge_data.get('category', '').lower()

            if any(t in rel_type for t in HIERARCHICAL_TYPES) or category == 'hierarchy':
                hierarchical_count += 1
            elif any(t in rel_type for t in CODE_TYPES) or category in ['code', 'internal']:
                code_count += 1
            elif any(t in rel_type for t in EXTERNAL_TYPES) or category == 'external':
                external_count += 1

        # Déterminer la couleur dominante (priorité : hiérarchique > code > externe)
        if hierarchical_count > 0:
            # Bleus pour hiérarchiques
            return '#66BB6A', '#388E3C'  # Bleu standard, Bleu foncé
        elif code_count > 0:
            # Verts/Cyans pour code
            return '#00ACC1', '#00838F'  # Cyan, Cyan foncé
        elif external_count > 0:
            # Oranges pour externes
            return '#FF8C00', '#E65100'  # Orange, Orange foncé
        else:
            # Par défaut : vert neutre
            return '#66BB6A', '#388E3C'  # Vert clair, Vert foncé
    
    def _get_node_color_for_type(self, node_type, relation_type=None): 
        if node_type == 'central':
            return '#8B2E1F'

        if node_type == 'analyzed':
            if relation_type:
                rel_lower = relation_type.lower() if isinstance(relation_type, str) else str(relation_type).lower()

                # Hiérarchiques : Bleu
                if any(t in rel_lower for t in ['parent', 'child', 'contains', 'belongs_to', 'hierarchy']):
                    return '#1976D2'  # Bleu foncé

                # Code : Vert
                if any(t in rel_lower for t in ['call', 'uses', 'implements', 'extends']):
                    return '#43A047'  # Vert foncé

                # Externes : Orange
                if any(t in rel_lower for t in ['import', 'require', 'include', 'dependency']):
                    return '#F57C00'  # Orange foncé

            return self.primary_color  # #A23B2D
        
        return '#5CAD56'  # Vert standard
    
    def _determine_node_orbit(self, G, node, center_node):
        HIERARCHICAL_TYPES = {'parent', 'child', 'contains', 'belongs_to', 'hierarchy', 'has'}
        CODE_TYPES = {'call', 'calls', 'method_call', 'function_call', 'uses', 'used_by', 
                      'implements', 'extends', 'inherits', 'override', 'invoke'}
        EXTERNAL_TYPES = {'import', 'from_import', 'require', 'include', 'dependency', 'external'}

        # Collecter TOUS les types de relations
        primary_types = set()
        categories = set()

        # Relations sortantes depuis le centre
        if center_node and G.has_edge(center_node, node):
            edge_data = G[center_node][node]
            rel_type = edge_data.get('relation_type', 'other').lower()
            category = edge_data.get('category', '').lower()
            primary_types.add(rel_type)
            if category:
                categories.add(category)

        # Relations entrantes vers le centre
        if center_node and G.has_edge(node, center_node):
            edge_data = G[node][center_node]
            rel_type = edge_data.get('relation_type', 'other').lower()
            category = edge_data.get('category', '').lower()
            primary_types.add(rel_type)
            if category:
                categories.add(category)

        # Déterminer l'orbite avec priorité : hiérarchique > code > externe
        is_hierarchical = any(t in HIERARCHICAL_TYPES for t in primary_types) or 'hierarchy' in categories
        is_code = any(t in CODE_TYPES for t in primary_types) or 'code' in categories or 'internal' in categories
        is_external = any(t in EXTERNAL_TYPES for t in primary_types) or 'external' in categories

        if is_hierarchical:
            return 1
        elif is_code:
            return 2
        elif is_external:
            return 3
        else:
            return 3  # Par défaut : externe

    def _setup_interactive_graph(self, ax, G, pos, edges, edge_colors, 
                        edge_labels, labels, node_colors, node_sizes, num_nodes):
        """Configure l'interactivité du graphe avec affichage des détails au clic."""
    
        self.graph_data = {
            'pos': {node: list(coord) for node, coord in pos.items()},
            'G': G,
            'ax': ax,
            'dragging_node': None,
            'selected_node': None,
            'edges': edges,
            'edge_colors': edge_colors,
            'edge_labels': edge_labels,
            'labels': labels,
            'node_colors': node_colors,
            'node_sizes': node_sizes,
            'num_nodes': num_nodes,
            'min_distance': 0.3 if num_nodes <= 20 else 0.2 if num_nodes <= 50 else 0.15,
        }
    
        # Connecter les événements
        self.canvas.mpl_connect('button_press_event', self._on_graph_press)
        self.canvas.mpl_connect('button_release_event', self._on_graph_release)
        self.canvas.mpl_connect('motion_notify_event', self._on_graph_motion)
        self.canvas.mpl_connect('scroll_event', self._on_mouse_scroll)
    
    def _on_graph_press(self, event):
        """Gère le clic de la souris : double-clic = explorer OU afficher code selon le type."""
        if not hasattr(self, 'graph_data') or event.inaxes != self.graph_data['ax']:
            return

        if event.xdata is None or event.ydata is None:
            return

        pos = self.graph_data['pos']
        G = self.graph_data['G']

        # ✅ RÉCUPÉRER LES DIMENSIONS RÉELLES DES NŒUDS
        text_width = self.graph_data.get('text_width', 5.0)
        text_height = self.graph_data.get('text_height', 1.3)

        # ✅ ZONE DE CLIC BASÉE SUR LES RECTANGLES
        clicked_node = None
        min_distance = float('inf')

        for node, coords in pos.items():
            x, y = coords

            dx = abs(event.xdata - x)
            dy = abs(event.ydata - y)

            half_width = text_width / 2 + 0.5
            half_height = text_height / 2 + 0.3

            if dx <= half_width and dy <= half_height:
                distance = (dx**2 + dy**2) ** 0.5

                if distance < min_distance:
                    min_distance = distance
                    clicked_node = node

        if clicked_node:
            # ✅ DOUBLE-CLIC : Action immédiate (priorité absolue)
            if event.dblclick and event.button == 1:
                # ✅ ANNULER le timer du clic simple en attente
                self.click_timer.stop()
                self.pending_click_node = None
                self.pending_click_graph = None

                logger.info(f"🎯 DOUBLE-CLIC CONFIRMÉ sur {clicked_node}")

                node_data = G.nodes[clicked_node]
                node_type = node_data.get('node_type', 'unknown')

                if node_type in ['function', 'method']:
                    logger.info(f"⚙️ Appel _show_function_code_snippet()...")
                    self._show_function_code_snippet(clicked_node, G)
                else:
                    logger.info(f"🔍 Navigation classique vers {clicked_node}")
                    self._explore_node_from_graph(clicked_node)

            # ✅ CLIC SIMPLE GAUCHE : Différer l'action (attendre 250ms pour détecter un éventuel double-clic)
            elif event.button == 1 and not event.dblclick:
                # ✅ Sauvegarder les infos du clic
                self.pending_click_node = clicked_node
                self.pending_click_graph = G

                # ✅ Démarrer le timer (250ms)
                self.click_timer.start(250)

                # Préparer le drag
                self.graph_data['dragging_node'] = clicked_node
                self.graph_data['drag_start'] = (event.xdata, event.ydata)

                from PyQt5.QtGui import QCursor
                from PyQt5.QtCore import Qt
                self.canvas.setCursor(QCursor(Qt.ClosedHandCursor))

            # Clic droit = afficher détails
            elif event.button == 3:
                logger.info(f"🖱️ CLIC DROIT sur {clicked_node}")
                self._show_node_details_in_graph(clicked_node, G)

    def _handle_single_click(self):
        """✅ NOUVEAU : Traite le clic simple après le délai (si pas de double-clic détecté)"""
        if self.pending_click_node and self.pending_click_graph:
            logger.info(f"👆 CLIC SIMPLE confirmé sur {self.pending_click_node} - Affichage origines")
            self._show_node_origins_popup(self.pending_click_node, self.pending_click_graph)

            # Réinitialiser
            self.pending_click_node = None
            self.pending_click_graph = None

    def _show_node_origins_popup(self, node_name, G):
        """
        Affiche les origines d'un nœud via tooltip au survol.
        """
        if not self.dgraph_connector or node_name not in G.nodes():
            return
        # Nettoyer le nom
        clean_name = node_name.replace('F: ', '').replace('M: ', '').replace('C: ', '').replace('V: ', '').strip()
        escaped = clean_name.replace('.', r'\.').replace('(', r'\(').replace(')', r'\)')

        query = f"""
        {{
          node_path(func: type(Relation)) @filter(
            regexp(sourceName, /{escaped}/i)
          ) {{
            sourcePath
          }}

          origins(func: type(Relation)) @filter(
            regexp(targetName, /{escaped}/i) OR regexp(targetPath, /{escaped}/i)
          ) {{
            sourcePath
            relationType
          }}
        }}
        """
        try:
            result = self._execute_dgraph_query(query)

            # Récupérer le path du nœud lui-même
            node_path = "N/A"
            if result and 'node_path' in result and result['node_path']:
                node_path = result['node_path'][0].get('sourcePath', 'N/A')

            # Récupérer les origines
            origins = result.get('origins', []) if result else []
            # Dédupliquer par sourcePath
            seen_paths = set()
            unique_origins = []
            for o in origins:
                path = o.get('sourcePath')
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    unique_origins.append(o)

            # Construire le tooltip ligne par ligne
            lines = [
                f"<b>{node_name}</b>",
                f" Path: {node_path}",
                ""
            ]

            if unique_origins:
                lines.append("<b>Origines:</b>")
                for o in unique_origins:
                    rel = o.get('relationType', '?')
                    path = o.get('sourcePath', 'N/A')
                    lines.append(f"  • {rel}: {path}")
            else:
                lines.append("<i>Aucune origine trouvée</i>")

            # Afficher le tooltip à la position de la souris
            tooltip_text = "<br>".join(lines)
            QtWidgets.QToolTip.showText(
                QtGui.QCursor.pos(),  # Position actuelle de la souris
                tooltip_text,
                None,  # Pas de widget parent
                QtCore.QRect(),  # Pas de rectangle spécifique
                5000  # Durée d'affichage : 5 secondes
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Erreur", str(e))

    def _show_popup(self, title, markdown_content):
        """
        ✅ Affiche un popup avec contenu Markdown
        Réutilise le design du popup de code
        """
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, 
                                      QPushButton, QHBoxLayout, QLabel, QFrame)
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont

        # Créer le dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(750, 600)
        dialog.setModal(False)

        # Style global
        dialog.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
        """)

        # Layout principal
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== HEADER =====
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 15, 20, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # ===== ZONE DE CONTENU =====
        content_viewer = QTextEdit()
        content_viewer.setMarkdown(markdown_content)
        content_viewer.setReadOnly(True)

        # Police
        content_font = QFont("Segoe UI", 10)
        content_viewer.setFont(content_font)

        # Style
        content_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #1A1A1A;
                border: none;
                padding: 20px;
                selection-background-color: #B3D7FF;
                selection-color: #000000;
            }

            QScrollBar:vertical {
                background: #F5F5F5;
                width: 12px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #C0C0C0;
                border-radius: 6px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #A0A0A0;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        main_layout.addWidget(content_viewer, 1)

        # ===== FOOTER =====
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E0E0E0;
            }
        """)
        footer.setFixedHeight(55)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.addStretch()

        # Bouton Fermer
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E8E8E8;
                color: #333333;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.close)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer)

        # Afficher
        dialog.exec_()

    def _show_function_code_snippet(self, node_name, G):
        """✅ CORRIGÉ : Affiche le code avec dialogue non-bloquant."""

        print(f"\n{'='*70}")
        print(f"🎯 DOUBLE-CLIC DÉTECTÉ SUR : {node_name}")
        print(f"{'='*70}")

        logger.info(f"\n{'='*70}")
        logger.info(f"📄 AFFICHAGE CODE FONCTION : {node_name}")
        logger.info(f"{'='*70}")

        # 1️⃣ Récupérer l'UID de la fonction
        node_data = G.nodes[node_name]
        function_uid = node_data.get('uid')

        print(f"🔑 UID fonction : {function_uid}")
        print(f"📦 Type nœud : {node_data.get('node_type', 'unknown')}")
        logger.info(f"🔑 UID fonction : {function_uid}")

        if not function_uid:
            print("❌ UID de la fonction manquant")
            logger.error("❌ UID de la fonction manquant")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de récupérer l'UID de la fonction '{node_name}'"
            )
            return

        # ✅ CORRECTION : Utiliser la barre de progression existante au lieu d'un dialogue
        self._show_progress(f"Récupération du code de '{node_name}'...", 0)

        try:
            # 3️⃣ Récupérer le contenu
            print(f"🔄 Appel de _get_function_source_content()...")
            self._update_progress(30, "Analyse du code...")

            result = self._get_function_source_content(function_uid, node_name)

            self._update_progress(60, "Préparation de l'affichage...")
            print(f"📥 Résultat reçu : {bool(result)}")

            if result:
                print(f"📏 Taille code : {len(result.get('content', ''))} chars")
                print(f"📂 Fichier : {result.get('file_path', 'N/A')}")
                print(f"📍 Ligne : {result.get('line', 'N/A')}")

            self._update_progress(90, "Finalisation...")

            if not result or not result.get('content'):
                self._hide_progress()  # ✅ Masquer la barre
                print("❌ Aucun code récupéré")
                logger.warning("❌ Code vide ou introuvable")

                error_msg = f"Impossible de récupérer le code de '{node_name}'\n\n"
                error_msg += "Causes possibles :\n"
                error_msg += "• La fonction n'existe pas dans Dgraph\n"
                error_msg += "• Le champ 'codeContent' ou 'fileContents' est vide\n"
                error_msg += "• Les relations sourcePath/targetPath sont manquantes\n\n"
                error_msg += f"UID recherché : {function_uid}"

                QtWidgets.QMessageBox.warning(
                    self,
                    "Code non disponible",
                    error_msg
                )
                return

            # 4️⃣ Extraire les données
            code_content = result.get('content', '# Code non disponible')
            file_path = result.get('file_path', 'unknown')
            line_number = result.get('line', 0)
            description = result.get('description', '')

            print(f"✅ Code prêt à afficher : {len(code_content)} caractères")
            logger.info(f"✅ Code récupéré : {len(code_content)} caractères")

            # ✅ VÉRIFICATION : Si le code est vide ou invalide
            if not code_content or code_content.strip() == '' or code_content == '# Code non disponible':
                self._hide_progress()  # ✅ Masquer la barre
                print("⚠️ Code vide ou invalide")
                logger.warning("⚠️ Code vide ou invalide récupéré")

                QtWidgets.QMessageBox.warning(
                    self,
                    "Code vide",
                    f"Le code de '{node_name}' est vide ou non disponible.\n\n"
                    f"Fichier : {file_path}\n"
                    f"Ligne : {line_number}\n\n"
                    f"Vérifiez que le parsing du code source a bien été effectué."
                )
                return

            self._update_progress(100, "Ouverture du popup...")
            self._hide_progress()  # ✅ Masquer la barre AVANT d'afficher le popup

            # 5️⃣ Créer et afficher le popup
            print(f"🎨 Affichage du popup...")
            self._display_code_popup(node_name, code_content, file_path, line_number, description)
            print(f"✅ Popup affiché avec succès")

        except Exception as e:
            self._hide_progress()  # ✅ Toujours masquer en cas d'erreur
            print(f"❌ ERREUR : {e}")
            logger.error(f"❌ Erreur affichage code : {e}")
            import traceback
            traceback.print_exc()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de l'affichage du code :\n{str(e)}\n\n"
                f"Consultez les logs pour plus de détails."
            )

    def _display_code_popup(self, function_name, code_content, file_path, line_number, description):
        """Popup moderne en mode clair - design épuré et professionnel."""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                                      QPushButton, QLabel, QFrame)
        from PyQt5.QtGui import QFont
        from PyQt5.QtCore import Qt

        # Créer le dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Code : {function_name}")
        dialog.setMinimumSize(850, 650)
        dialog.setModal(False)

        # Style global
        dialog.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
        """)

        # Layout principal
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== HEADER (texte simple sans fond) =====
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 15, 20, 10)
        header_layout.setSpacing(12)

        # Titre
        title_label = QLabel(function_name)
        title_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        header_layout.addWidget(title_label)

        # Séparateur
        sep_label = QLabel("·")
        sep_label.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 12px;")
        header_layout.addWidget(sep_label)

        # Fichier
        file_label = QLabel(file_path)
        file_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        header_layout.addWidget(file_label)

        # Séparateur
        sep_label2 = QLabel("·")
        sep_label2.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 12px;")
        header_layout.addWidget(sep_label2)

        # Ligne
        line_label = QLabel(f"Ligne {line_number}")
        line_label.setStyleSheet("""
            QLabel {
                color: #0066CC;
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        header_layout.addWidget(line_label)

        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # ===== DESCRIPTION (simple, sans conteneur) =====
        if description and description.strip():
            desc_layout = QHBoxLayout()
            desc_layout.setContentsMargins(20, 5, 20, 10)

            desc_label = QLabel(description[:200] + ("..." if len(description) > 200 else ""))
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-size: 11px;
                    font-style: italic;
                    background: transparent;
                }
            """)
            desc_layout.addWidget(desc_label, 1)

            main_layout.addLayout(desc_layout)

        # ===== ZONE DE CODE =====
        code_editor = QTextEdit()
        code_editor.setPlainText(code_content)
        code_editor.setReadOnly(True)
        code_editor.setLineWrapMode(QTextEdit.NoWrap)

        # Police monospace
        code_font = QFont("Consolas", 10)
        code_font.setStyleHint(QFont.Monospace)
        code_font.setFixedPitch(True)
        code_editor.setFont(code_font)

        # Style clair
        code_editor.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #1A1A1A;
                border: none;
                padding: 15px;
                selection-background-color: #B3D7FF;
                selection-color: #000000;
            }

            QScrollBar:vertical {
                background: #F5F5F5;
                width: 12px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #C0C0C0;
                border-radius: 6px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #A0A0A0;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                background: #F5F5F5;
                height: 12px;
                border: none;
            }

            QScrollBar::handle:horizontal {
                background: #C0C0C0;
                border-radius: 6px;
                min-width: 30px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #A0A0A0;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        # Coloration syntaxique
        highlighter = PythonSyntaxHighlighter(code_editor.document())

        main_layout.addWidget(code_editor, 1)

        # ===== FOOTER =====
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E0E0E0;
            }
        """)
        footer.setFixedHeight(55)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.setSpacing(10)

        # Statistiques
        lines_count = len(code_content.split('\n'))
        chars_count = len(code_content)

        stats_label = QLabel(f"{lines_count} lignes · {chars_count} caractères")
        stats_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        footer_layout.addWidget(stats_label)

        footer_layout.addStretch()

        # Bouton Copier (gris foncé)
        copy_btn = QPushButton("Copier")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #5A5A5A;
                color: #FFFFFF;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #6A6A6A;
            }
            QPushButton:pressed {
                background-color: #4A4A4A;
            }
        """)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self._copy_code_with_feedback(code_content, copy_btn))
        footer_layout.addWidget(copy_btn)

        # Bouton Fermer
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E8E8E8;
                color: #333333;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.close)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer)

        # Afficher
        dialog.exec_()

    def _copy_code_with_feedback(self, code: str, button: QPushButton):
        """Copie le code avec feedback visuel."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(code)

        # Feedback visuel
        original_text = button.text()
        button.setText("Copié !")
        button.setStyleSheet("""
            QPushButton {
                background-color: #00AA66;
                color: #FFFFFF;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
        """)

        # Restaurer après 2 secondes
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._reset_copy_button(button, original_text))

    def _reset_copy_button(self, button: QPushButton, original_text: str):
        """Restaure le bouton copier."""
        button.setText(original_text)
        button.setStyleSheet("""
            QPushButton {
                background-color: #5A5A5A;
                color: #FFFFFF;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6A6A6A;
            }
            QPushButton:pressed {
                background-color: #4A4A4A;
            }
        """)

    def _cleanup_duplicate_functions(self, function_name: str):
        """Supprime les doublons d'une fonction et garde seulement celui avec du code."""

        query = f"""
        {{
          all(func: eq(name, "{function_name}")) @filter(type(Function)) {{
            uid
            name
            codeContent
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if not result or 'all' not in result:
            return

        nodes = result['all']

        if len(nodes) <= 1:
            logger.info(f"✅ Pas de doublon pour {function_name}")
            return

        logger.warning(f"⚠️ {len(nodes)} versions de {function_name} trouvées")

        # Trouver le bon nœud (avec du code)
        valid_node = None
        empty_nodes = []

        for node in nodes:
            code = node.get('codeContent', '').strip()

            if code:
                if valid_node:
                    logger.warning(f"⚠️ Plusieurs nœuds avec du code !")
                else:
                    valid_node = node
            else:
                empty_nodes.append(node.get('uid'))

        if not valid_node:
            logger.error(f"❌ Aucun nœud valide trouvé pour {function_name}")
            return

        if not empty_nodes:
            logger.info(f"✅ Tous les nœuds ont du code (pas de nettoyage nécessaire)")
            return

        # Supprimer les nœuds vides
        logger.info(f"🗑️ Suppression de {len(empty_nodes)} nœud(s) vide(s)...")

        for uid in empty_nodes:
            delete_mutation = f"""
            {{
              delete {{
                <{uid}> * * .
              }}
            }}
            """

            try:
                txn = self.dgraph_connector.client.txn()
                txn.mutate(del_nquads=f"<{uid}> * * .")
                txn.commit()
                logger.info(f"  ✅ Supprimé : {uid}")
            except Exception as e:
                logger.error(f"  ❌ Erreur suppression {uid}: {e}")
            finally:
                txn.discard()

        logger.info(f"✅ Nettoyage terminé. Nœud valide: {valid_node['uid']}")

    def _extract_function_from_file_content(self, file_content: str, function_name: str, start_line: int) -> str:
        """✅ CORRIGÉ : Extrait une fonction depuis le contenu d'un fichier avec logs."""

        print(f"\n{'='*70}")
        print(f"🔍 EXTRACTION FONCTION DEPUIS FICHIER")
        print(f"{'='*70}")
        print(f"   Fonction recherchée : {function_name}")
        print(f"   Ligne de départ : {start_line}")
        print(f"   Taille fichier : {len(file_content)} chars")

        if not file_content:
            logger.warning("⚠️ Contenu fichier vide")
            print("❌ Contenu fichier vide")
            return ""

        lines = file_content.split('\n')
        print(f"   Nombre de lignes : {len(lines)}")

        if start_line < 1 or start_line > len(lines):
            logger.warning(f"⚠️ Numéro de ligne invalide: {start_line} (fichier: {len(lines)} lignes)")
            print(f"❌ Ligne invalide : {start_line} (max: {len(lines)})")
            return ""

        logger.info(f"🔍 Extraction fonction '{function_name}' depuis ligne {start_line}")
        logger.info(f"📄 Fichier: {len(lines)} lignes totales")

        # Convertir en index 0-based
        start_index = start_line - 1

        print(f"   Index 0-based : {start_index}")
        print(f"   Ligne content : {lines[start_index][:100]}")

        # ✅ Pattern pour détecter une définition de fonction Python
        import re

        # Patterns possibles
        function_patterns = [
            rf'^\s*def\s+{re.escape(function_name)}\s*\(',  # def function_name(
            rf'^\s*async\s+def\s+{re.escape(function_name)}\s*\(',  # async def function_name(
        ]

        print(f"   Patterns recherchés :")
        for p in function_patterns:
            print(f"      • {p}")

        is_function_def = any(re.match(pattern, lines[start_index]) for pattern in function_patterns)

        print(f"   Match pattern : {is_function_def}")

        if not is_function_def:
            logger.warning(f"⚠️ La ligne {start_line} ne semble pas être une définition de fonction")
            print(f"⚠️ Pas de match sur ligne {start_line}")

            # ✅ FALLBACK : Chercher la fonction dans les lignes précédentes (max 10 lignes)
            print(f"   🔄 Recherche dans les 10 lignes précédentes...")
            for offset in range(1, min(11, start_index + 1)):
                check_index = start_index - offset
                check_line = lines[check_index]

                print(f"      Ligne {check_index + 1} : {check_line[:80]}")

                if any(re.match(pattern, check_line) for pattern in function_patterns):
                    logger.info(f"✅ Fonction trouvée {offset} lignes avant (ligne {check_index + 1})")
                    print(f"   ✅ Trouvée à la ligne {check_index + 1}")
                    start_index = check_index
                    break

        # ✅ Déterminer l'indentation de base
        base_line = lines[start_index]
        base_indent = len(base_line) - len(base_line.lstrip())

        logger.info(f"📏 Indentation de base: {base_indent} espaces")

        # ✅ EXTRACTION : Lire jusqu'à la fin de la fonction
        function_lines = [lines[start_index]]
        current_index = start_index + 1

        # Variables pour suivre l'état
        in_docstring = False
        docstring_delimiter = None
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0

        # Compter les parenthèses dans la première ligne (signature)
        paren_depth = base_line.count('(') - base_line.count(')')

        while current_index < len(lines):
            line = lines[current_index]
            stripped = line.strip()

            # ✅ Ligne vide : continuer si on est dans la fonction
            if not stripped:
                if in_docstring or paren_depth > 0:
                    function_lines.append(line)
                    current_index += 1
                    continue
                else:
                    # Ligne vide après le corps : possiblement la fin
                    # Vérifier la ligne suivante
                    if current_index + 1 < len(lines):
                        next_line = lines[current_index + 1]
                        next_indent = len(next_line) - len(next_line.lstrip())

                        # Si la ligne suivante est au même niveau ou moins indentée : fin
                        if next_line.strip() and next_indent <= base_indent:
                            break
                        else:
                            # Sinon continuer (ligne vide dans le corps)
                            function_lines.append(line)
                            current_index += 1
                            continue
                    else:
                        break

            # ✅ Gestion des docstrings
            if '"""' in stripped or "'''" in stripped:
                delimiter = '"""' if '"""' in stripped else "'''"

                if not in_docstring:
                    in_docstring = True
                    docstring_delimiter = delimiter
                    function_lines.append(line)

                    # Vérifier si le docstring se ferme sur la même ligne
                    if stripped.count(delimiter) >= 2:
                        in_docstring = False
                        docstring_delimiter = None

                    current_index += 1
                    continue
                else:
                    # Fin du docstring
                    if delimiter == docstring_delimiter:
                        function_lines.append(line)
                        in_docstring = False
                        docstring_delimiter = None
                        current_index += 1
                        continue

            # Si on est dans un docstring, tout ajouter
            if in_docstring:
                function_lines.append(line)
                current_index += 1
                continue

            # ✅ Si on est encore dans la signature (parenthèses non fermées)
            if paren_depth > 0:
                function_lines.append(line)
                paren_depth += line.count('(') - line.count(')')
                current_index += 1
                continue

            # ✅ Calculer l'indentation de la ligne actuelle
            current_indent = len(line) - len(line.lstrip())

            # ✅ CONDITION D'ARRÊT : Ligne moins ou également indentée que la def
            if current_indent <= base_indent:
                # Exceptions : commentaires, lignes vides déjà gérées
                if stripped.startswith('#'):
                    function_lines.append(line)
                    current_index += 1
                    continue
                else:
                    # Fin de la fonction
                    logger.info(f"✅ Fin de fonction détectée à la ligne {current_index + 1}")
                    break

            # ✅ Ligne faisant partie du corps de la fonction
            function_lines.append(line)

            # ✅ Suivre les délimiteurs pour détecter les blocs imbriqués
            paren_depth += line.count('(') - line.count(')')
            bracket_depth += line.count('[') - line.count(']')
            brace_depth += line.count('{') - line.count('}')

            current_index += 1

            # ✅ Limite de sécurité (éviter boucle infinie)
            if len(function_lines) > 1000:
                logger.warning("⚠️ Fonction trop longue (>1000 lignes), arrêt")
                break

        # ✅ RÉSULTAT
        extracted_code = '\n'.join(function_lines)

        logger.info(f"✅ Code extrait : {len(function_lines)} lignes")
        logger.info(f"   Début: ligne {start_index + 1}")
        logger.info(f"   Fin: ligne {start_index + len(function_lines)}")

        return extracted_code
    
    def _copy_code_to_clipboard(self, code: str):
        """✅ Copie le code dans le presse-papiers."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(code)

        # Message de confirmation
        QtWidgets.QMessageBox.information(
            self,
            "Code copié",
            "Le code a été copié dans le presse-papiers !",
            QtWidgets.QMessageBox.Ok
        )

    def _explore_node_from_graph(self, node_name):
        """✅ NOUVEAU : Explore les relations d'un nœud cliqué dans le graphe."""
        logger.info(f"🔍 Navigation vers : {node_name}")

        # ✅ CORRECTION : Sauvegarder l'état ACTUEL avant navigation
        if self.current_central_uid and self.current_central_name:
            # Déterminer le type de vue actuelle
            current_view_type = 'relations'
            if hasattr(self, 'graph_data'):
                if self.graph_data.get('is_file_list_view'):
                    current_view_type = 'file_list'
                elif self.graph_data.get('is_cluster_view'):
                    current_view_type = 'cluster'

            logger.info(f"💾 Sauvegarde état: {self.current_central_name} (type={current_view_type})")

            self.navigation_history.append({
                'uid': self.current_central_uid,
                'name': self.current_central_name,
                'relations': self.current_relations.copy() if self.current_relations else [],
                'view_type': current_view_type,
                'cluster_uid': self.graph_data.get('cluster_uid') if hasattr(self, 'graph_data') else None,
                'cluster_name': self.graph_data.get('cluster_name') if hasattr(self, 'graph_data') else None
            })

            # Limiter l'historique à 10 éléments
            if len(self.navigation_history) > 10:
                self.navigation_history.pop(0)

            self.back_btn.setEnabled(True)
            logger.info(f"✅ Historique: {len(self.navigation_history)} états sauvegardés")

        # 1. Chercher dans le graphe actuel
        if hasattr(self, 'graph_data') and 'G' in self.graph_data:
            G = self.graph_data['G']
            if node_name in G.nodes():
                node_uid = G.nodes[node_name].get('uid')

        # 2. Chercher dans le cache
        if not node_uid:
            node_uid = self._get_node_uid_by_name(node_name)

        # 3. Chercher dans l'arbre
        if not node_uid:
            for uid, item in self._node_cache.items():
                item_name = self.normalize_node_name(
                    item.item_data.get('name') or item.item_data.get('label') or item.text(0)
                )
                if item_name == node_name:
                    node_uid = uid
                    break
                
        if not node_uid:
            QtWidgets.QMessageBox.warning(
                self,
                "Nœud introuvable",
                f"Impossible de trouver l'UID pour '{node_name}'.\n"
                f"Sélectionnez le nœud dans l'arbre à gauche pour l'explorer."
            )
            return

        logger.info(f"✅ UID trouvé : {node_uid}")

        # Mettre à jour le contexte
        self.current_central_uid = node_uid
        self.current_central_name = node_name

        # Afficher un message de chargement
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')
        ax.text(0.5, 0.5, f"Chargement des relations\nde '{node_name}'...", 
               ha='center', va='center', 
               color='#666666', fontsize=12)
        ax.axis('off')
        self.canvas.draw()
        QtWidgets.QApplication.processEvents()

        # Récupérer et afficher les relations
        try:
            relations_list = self._get_level_1_relations(node_uid)

            if not relations_list:
                self._show_empty_graph(f"Aucune relation trouvée\npour '{node_name}'")
                return

            self.current_relations = relations_list
            self.hidden_relations.clear()
            self.figure.clear()

            G = self._build_clean_graph(relations_list)
            self.current_graph = G
            self._draw_graph(G)

            self._update_status(f"Navigation : {node_name} - {len(relations_list)} relations")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exploration de {node_name}: {e}")
            import traceback
            traceback.print_exc()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors du chargement des relations :\n{str(e)}"
            )

    def _navigate_back(self):
        """✅ CORRIGÉ : Retour à l'état précédent avec gestion des vues."""
        if not self.navigation_history:
            # Si l'historique est vide mais qu'on n'est pas sur la vue clusters, y retourner
            if self.level_combo.currentIndex() != 0 or self.current_central_uid:
                logger.info("🔙 Retour à la vue clusters initiale")
                self.current_central_uid = None
                self.current_central_name = None
                self.current_relations = []
                self.level_combo.blockSignals(True)
                self.level_combo.setCurrentIndex(0)
                self.level_combo.blockSignals(False)
                self._show_project_cluster_view()
                self.back_btn.setEnabled(False)
                self._update_status("Retour à la vue clusters")
                return
            else:
                logger.warning("⚠️ Déjà sur la vue clusters initiale")
                self.back_btn.setEnabled(False)  # ✅ AJOUT : Désactiver le bouton
                return

        previous_state = self.navigation_history.pop()

        logger.info(f"🔙 Navigation retour vers: {previous_state.get('name')}")
        logger.info(f"   Type de vue: {previous_state.get('view_type', 'relations')}")

        # Restaurer l'état
        self.current_central_uid = previous_state.get('uid')
        self.current_central_name = previous_state.get('name')
        self.current_relations = previous_state.get('relations', [])

        # ✅ Vérifier le type de vue
        view_type = previous_state.get('view_type', 'relations')

        if view_type == 'cluster':
            # Retour à la vue clusters
            logger.info("📦 Retour à la vue clusters")
            self.level_combo.blockSignals(True)
            self.level_combo.setCurrentIndex(0)
            self.level_combo.blockSignals(False)
            self._show_project_cluster_view()

        elif view_type == 'file_list':
            # Retour à la vue fichiers d'un cluster
            cluster_uid = previous_state.get('cluster_uid')
            cluster_name = previous_state.get('cluster_name')

            logger.info(f"📂 Retour à la vue fichiers du cluster: {cluster_name}")

            if cluster_uid and cluster_name:
                # Récupérer les données complètes du cluster
                clusters = self._get_clusters_data()
                cluster_info = None

                for cluster in clusters:
                    if cluster.get('uid') == cluster_uid:
                        cluster_info = {
                            'cluster_name': cluster.get('name', cluster_name),
                            'root_labels': cluster.get('root_labels', [])
                        }
                        break
                    
                if cluster_info:
                    self._explore_cluster_relations(cluster_uid, cluster_info)
                else:
                    logger.error(f"❌ Cluster {cluster_uid} introuvable")
                    self._show_empty_graph(f"Cluster '{cluster_name}' introuvable")
            else:
                logger.error("❌ Données cluster manquantes dans l'historique")
                self._show_empty_graph("Erreur de navigation")

        else:
            # Retour à une vue relations normale
            logger.info("🔗 Retour à la vue relations")

            if self.current_relations:
                self.figure.clear()
                G = self._build_clean_graph(self.current_relations)
                self.current_graph = G
                self.level_combo.blockSignals(True)
                self.level_combo.setCurrentIndex(1)  # Relations directes
                self.level_combo.blockSignals(False)
                self._draw_graph(G)
            else:
                self._show_empty_graph("État précédent sans relations")

        is_on_initial_cluster_view = (
            self.level_combo.currentIndex() == 0 and 
            not self.current_central_uid
        )

        self.back_btn.setEnabled(
            bool(self.navigation_history) or not is_on_initial_cluster_view
        )

        self._update_status(f"Retour à : {self.current_central_name or 'Vue clusters'}")

    def _show_node_details_in_graph(self, node_name, G):
        """Affiche les détails du nœud dans un encadré sur le graphe."""
        ax = self.graph_data['ax']

        # Supprimer l'ancien texte d'info s'il existe
        if self.info_text_obj:
            try:
                self.info_text_obj.remove()
            except:
                pass
            self.info_text_obj = None

        # Récupérer les informations du nœud
        node_data = G.nodes[node_name]
        node_type = node_data.get('node_type', 'unknown')

        # Relations sortantes et entrantes
        outgoing = list(G.out_edges(node_name, data=True))
        incoming = list(G.in_edges(node_name, data=True))

        # Construire le texte compact
        info_lines = []

        # Titre avec nom du nœud (tronqué si nécessaire)
        display_name = node_name[:25] + '..' if len(node_name) > 25 else node_name
        info_lines.append(f"╔═ {display_name} ═╗")
        info_lines.append(f"Type: {node_type}")
        info_lines.append("")

        # Relations sortantes (max 4)
        info_lines.append(f"↑ Sortantes ({len(outgoing)}):")
        for i, (source, target, data) in enumerate(outgoing[:4]):
            rel_type = data.get('relation_type', 'relation')
            target_short = target[:20] + '..' if len(target) > 20 else target
            rel_short = rel_type[:15] + '..' if len(rel_type) > 15 else rel_type
            info_lines.append(f"  → {target_short}")
            info_lines.append(f"     [{rel_short}]")

        if len(outgoing) > 4:
            info_lines.append(f"  ... +{len(outgoing) - 4} autres")

        info_lines.append("")

        # Relations entrantes (max 4)
        info_lines.append(f"↓ Entrantes ({len(incoming)}):")
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

        # Afficher le texte en haut à gauche
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
        self.canvas.draw_idle()

    def _on_graph_release(self, event):
        """Gère le relâchement du clic de la souris."""
        if not hasattr(self, 'graph_data'):
            return

        # ✅ Si double-clic sur une zone vide, masquer les détails ET les origines
        if event.dblclick and event.button == 1 and self.graph_data.get('dragging_node') is None:
            # Masquer les détails
            if self.info_text_obj:
                try:
                    self.info_text_obj.remove()
                except:
                    pass
                self.info_text_obj = None
                self.graph_data['selected_node'] = None

            # ✅ Masquer les origines compactes
            if hasattr(self, 'origins_compact_text') and self.origins_compact_text:
                try:
                    self.origins_compact_text.remove()
                except:
                    pass
                self.origins_compact_text = None

            self.canvas.draw_idle()

        self.graph_data['dragging_node'] = None

        from PyQt5.QtGui import QCursor
        from PyQt5.QtCore import Qt
        self.canvas.setCursor(QCursor(Qt.ArrowCursor))

    def _on_graph_motion(self, event):
        """
        ✅ AMÉLIORÉ : Gère le mouvement de la souris pour déplacer les nœuds
        Avec contrainte d'orbite (optionnel)
        """
        if not hasattr(self, 'graph_data') or event.inaxes != self.graph_data['ax']:
            return

        dragging_node = self.graph_data.get('dragging_node')

        if dragging_node is None or event.xdata is None or event.ydata is None:
            return

        self.graph_data['pos'][dragging_node] = [event.xdata, event.ydata]

        self._apply_local_collision_avoidance(dragging_node)

        self._redraw_graph_with_positions()

    def _redraw_legend(self, ax, edges):
        """Redessine la légende après un redraw."""
        edge_types_seen = {}
        for _, _, d in edges:
            rel_type = d.get('relation_type', 'unknown')
            color = d.get('color', '#CCCCCC')
            if rel_type not in edge_types_seen:
                edge_types_seen[rel_type] = color

        if edge_types_seen:
            from matplotlib.lines import Line2D
            legend_elements = []
            sorted_types = sorted(edge_types_seen.items())

            for rel_type, color in sorted_types[:8]:
                legend_elements.append(
                    Line2D([0], [0], color=color, linewidth=2.5, 
                          label=rel_type[:15] + '..' if len(rel_type) > 15 else rel_type,
                          marker='>', markersize=8)
                )

            if len(sorted_types) > 8:
                legend_elements.append(
                    Line2D([0], [0], color='#999999', linewidth=2, 
                          label=f'... +{len(sorted_types)-8} types',
                          linestyle='--')
                )

            legend = ax.legend(
                handles=legend_elements, 
                loc='upper right',
                fontsize=7,
                title="Relations",
                title_fontsize=8,
                framealpha=0.95,
                edgecolor='#CCCCCC',
                fancybox=True,
                shadow=False,
                ncol=1 if len(legend_elements) <= 6 else 2,
                columnspacing=0.5,
                handlelength=1.5,
                handletextpad=0.5,
                borderpad=0.4,
                labelspacing=0.3
            )

            legend.set_bbox_to_anchor((0.98, 0.98))

    def _redraw_graph_with_positions(self):
        data = self.graph_data
        ax = data['ax']
        G = data['G']
        pos = data['pos']
        num_nodes = data['num_nodes']
        node_orbits = data.get('node_orbits', {})

        text_width = data.get('text_width', 5.0)
        text_height = data.get('text_height', 1.3)
        font_size = data.get('font_size', 8)
        max_chars = data.get('max_chars', 25)

        pos = self._apply_universal_collision_avoidance(G, pos, num_nodes)

        # Mettre à jour les positions dans graph_data
        self.graph_data['pos'] = pos

        ax.clear()
        ax.set_facecolor('white')

        edges = data['edges']
        edge_colors = data['edge_colors']

        is_global_mode = self.level_combo.currentIndex() == 0

        # Paramètres d'arêtes
        if is_global_mode:
            curvature = 0.02
            edge_width = 1.5
            edge_alpha = 0.6
            arrow_size = 12
        else:
            curvature = 0.12 if num_nodes <= 20 else 0.08
            edge_width = 2.0 if num_nodes <= 20 else 1.5
            edge_alpha = 0.7
            arrow_size = 14 if num_nodes <= 20 else 10

        if num_nodes > 30:
            nx.draw_networkx_edges(
                G, pos, ax=ax, 
                edge_color=edge_colors,
                width=edge_width,
                alpha=edge_alpha, 
                arrows=True,
                arrowsize=arrow_size,
                arrowstyle='->'
            )
        else:
            nx.draw_networkx_edges(
                G, pos, ax=ax, 
                edge_color=edge_colors,
                width=edge_width,
                alpha=edge_alpha, 
                arrows=True,
                arrowsize=arrow_size,
                connectionstyle=f'arc3,rad={curvature}'
            )

        from matplotlib.patches import FancyBboxPatch

        for node in G.nodes():
            x, y = pos[node]

            # Récupérer les données du nœud
            node_data = G.nodes[node]
            node_type = node_data.get('node_type', None)

            # ✅ CORRECTION : Formater AVANT de déterminer la couleur
            formatted_name = self._format_node_display_name(node, node_type)
            display_name = formatted_name[:max_chars] + '..' if len(formatted_name) > max_chars else formatted_name

            # Déterminer la couleur APRÈS le formatage
            if node == self.current_central_name:
                color = '#8B2E1F'
                edge_color = '#666666'
                linewidth = 3.0
            else:
                color, edge_color = self._get_node_color_from_relations(G, node, self.current_central_name)
                linewidth = 2.5

            rect = FancyBboxPatch(
                (x - text_width/2, y - text_height/2),
                text_width, text_height,
                boxstyle="round,pad=0.15",
                edgecolor=edge_color,
                facecolor=color,
                alpha=0.95,
                linewidth=linewidth,
                zorder=2
            )
            ax.add_patch(rect)

            ax.text(
                x, y, display_name,
                ha='center', va='center',
                fontsize=font_size,
                fontweight='bold',
                color='white',
                zorder=3
            )

        # ✅ LABELS D'ARÊTES (uniquement en mode local et graphes petits)
        if not is_global_mode and num_nodes <= 25:
            edge_labels = {(u, v): d.get('label', '') for u, v, d in edges}
            nx.draw_networkx_edge_labels(
                G, pos, edge_labels, ax=ax, 
                font_size=7,
                font_color='#444444',
                bbox=dict(
                    boxstyle='round,pad=0.3', 
                    facecolor='white', 
                    edgecolor='none', 
                    alpha=0.8
                )
            )

        # ✅ Légende avec orbites
        self._draw_orbit_legend(ax, edges, node_orbits)

        # Réafficher détails si sélectionné
        if self.graph_data.get('selected_node'):
            self._show_node_details_in_graph(self.graph_data['selected_node'], G)

        # ✅ NOUVEAU : Réafficher les origines si checkbox activée
        if hasattr(self, 'show_node_origins_cb') and self.show_node_origins_cb.isChecked():
            self._add_node_origins_display()

        ax.axis('off')

        ax.axis('off')

        # ✅ Recalculer limites avec marges adaptées
        x_coords = [pos[node][0] for node in G.nodes()]
        y_coords = [pos[node][1] for node in G.nodes()]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Marges plus grandes pour les cadres plus larges
        if num_nodes <= 15:
            margin = 6.0
        elif num_nodes <= 30:
            margin = 5.0
        else:
            margin = 4.0

        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        self.graph_data['x_min'] = x_min
        self.graph_data['x_max'] = x_max
        self.graph_data['y_min'] = y_min
        self.graph_data['y_max'] = y_max

        self.canvas.draw_idle()

        # Mettre à jour minimap si existe
        if hasattr(self, 'minimap_ax') and self.minimap_ax:
            self._update_minimap()
        if hasattr(self, 'show_node_origins_cb') and self.show_node_origins_cb.isChecked():
            self._add_node_origins_display()

        ax.axis('off')

    def _apply_fixed_dimension_collision_avoidance(self, G, pos, num_nodes):
        """
        ✅ COLLISION AVOIDANCE avec DIMENSIONS FIXES (4.0 x 1.2)
        Respecte l'alignement vertical tout en évitant les superpositions
        """
        FIXED_WIDTH = 4.0
        FIXED_HEIGHT = 1.2

        # Distance minimale adaptée
        if num_nodes <= 10:
            base_min_distance = 2.5
            iterations = 60
        elif num_nodes <= 20:
            base_min_distance = 2.0
            iterations = 50
        elif num_nodes <= 40:
            base_min_distance = 1.5
            iterations = 40
        else:
            base_min_distance = 1.2
            iterations = 30

        for iteration in range(iterations):
            nodes = list(G.nodes())
            max_displacement = 0

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # Distance requise basée sur dimensions fixes
                    required_distance = (FIXED_WIDTH + FIXED_HEIGHT) / 2 + base_min_distance

                    if distance < required_distance and distance > 0.01:
                        # Vecteur unitaire
                        ux = dx / distance
                        uy = dy / distance

                        # Force de répulsion FORTE au début, diminue progressivement
                        force_factor = 1.0 - (iteration / iterations) * 0.6
                        force = (required_distance - distance) * 0.2 * force_factor

                        # ✅ PRIORITÉ VERTICALE : Déplacer plus sur Y que sur X
                        # Pour préserver l'alignement en colonnes
                        vertical_bias = 1.5

                        pos[node1][0] -= force * ux * 0.5  # Moins de mouvement horizontal
                        pos[node1][1] -= force * uy * vertical_bias  # Plus de mouvement vertical
                        pos[node2][0] += force * ux * 0.5
                        pos[node2][1] += force * uy * vertical_bias

                        max_displacement = max(max_displacement, force)

            # Convergence anticipée
            if max_displacement < 0.02:
                logger.info(f"✅ Collision avoidance convergée à l'itération {iteration}")
                break
            
            # Réduction progressive
            if iteration % 20 == 0 and iteration > 0:
                base_min_distance *= 0.95

        return pos

    def _align_nodes_by_type(self, G, pos, num_nodes):
        """
        ✅ NOUVEAU : Aligne verticalement les nœuds de même type
        Crée des "colonnes" par type de nœud pour un rendu organisé
        """
        from collections import defaultdict

        # Grouper les nœuds par type
        nodes_by_type = defaultdict(list)
        for node in G.nodes():
            node_type = G.nodes[node].get('node_type', 'dependency')
            nodes_by_type[node_type].append(node)

        logger.info(f"🎯 Alignement vertical : {len(nodes_by_type)} types détectés")

        # Déterminer les colonnes (positions X fixes)
        type_order = ['central', 'analyzed', 'dependency']
        available_types = [t for t in type_order if t in nodes_by_type]
        other_types = [t for t in nodes_by_type.keys() if t not in type_order]
        all_types = available_types + other_types

        # Calculer positions X pour chaque type
        if len(all_types) == 1:
            x_positions = {all_types[0]: 0.0}
        else:
            # Espacement horizontal entre colonnes
            column_spacing = 12.0 if num_nodes <= 20 else 10.0
            total_width = (len(all_types) - 1) * column_spacing
            start_x = -total_width / 2

            x_positions = {}
            for i, node_type in enumerate(all_types):
                x_positions[node_type] = start_x + (i * column_spacing)

        # Aligner chaque groupe verticalement
        for node_type, nodes in nodes_by_type.items():
            if node_type not in x_positions:
                continue

            x_col = x_positions[node_type]

            # Trier les nœuds par leur Y actuel pour garder l'ordre relatif
            nodes_sorted = sorted(nodes, key=lambda n: pos[n][1])

            # Espacement vertical adaptatif
            if len(nodes_sorted) == 1:
                # Nœud unique : centrer verticalement
                pos[nodes_sorted[0]][0] = x_col
                pos[nodes_sorted[0]][1] = 0.0
            else:
                # Calculer espacement vertical
                vertical_spacing = 3.0 if num_nodes <= 20 else 2.5
                total_height = (len(nodes_sorted) - 1) * vertical_spacing
                start_y = total_height / 2

                # Positionner chaque nœud
                for i, node in enumerate(nodes_sorted):
                    pos[node][0] = x_col
                    pos[node][1] = start_y - (i * vertical_spacing)

        logger.info(f"✅ Alignement terminé : {len(all_types)} colonnes créées")

        return pos

    def _apply_aggressive_collision_avoidance(self, G, pos, num_nodes):
        """
        ✅ NOUVELLE MÉTHODE : Collision avoidance ULTRA-EFFICACE pour redraw
        Empêche toute superposition en temps réel
        """

        def get_node_dimensions(node_name):
            """Calcule largeur réelle basée sur longueur du texte avec marge"""
            # ✅ 1. Vérifier cache d'abord
            if hasattr(self, 'graph_data') and self.graph_data and 'node_dimensions' in self.graph_data:
                if node_name in self.graph_data['node_dimensions']:
                    return self.graph_data['node_dimensions'][node_name]
            
            # ✅ 2. Fallback avec valeurs AUGMENTÉES
            if num_nodes <= 15:
                max_chars = 35        # ✅ Augmenté de 30 à 35
                base_width = 10.0     # ✅ Augmenté de 8.0 à 10.0
                height = 2.8          # ✅ Augmenté de 2.5 à 2.8
            elif num_nodes <= 30:
                max_chars = 32        # ✅ Augmenté de 28 à 32
                base_width = 9.0      # ✅ Augmenté de 7.5 à 9.0
                height = 2.5          # ✅ Augmenté de 2.2 à 2.5
            else:
                max_chars = 28        # ✅ Augmenté de 25 à 28
                base_width = 8.0      # ✅ Augmenté de 7.0 à 8.0
                height = 2.2          # ✅ Augmenté de 2.0 à 2.2
            
            display_name = node_name[:max_chars] + '..' if len(node_name) > max_chars else node_name
            
            # ✅ 3. Calcul avec facteur de sécurité
            char_width = base_width / max_chars
            width = len(display_name) * char_width * 1.2 + 1.5  # ✅ +20% + padding augmenté
            
            return width, height

        # ✅ Distance minimale VARIABLE selon densité
        if num_nodes <= 10:
            base_min_distance = 2.5  # Augmenté pour plus d'espace
            iterations = 80
        elif num_nodes <= 20:
            base_min_distance = 2.0
            iterations = 60
        elif num_nodes <= 40:
            base_min_distance = 1.5
            iterations = 50
        else:
            base_min_distance = 1.2
            iterations = 40

        # ✅ Algorithme de répulsion RAPIDE mais efficace
        for iteration in range(iterations):
            nodes = list(G.nodes())
            max_displacement = 0

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]
                w1, h1 = get_node_dimensions(node1)

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]
                    w2, h2 = get_node_dimensions(node2)

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # Distance requise = somme des demi-largeurs + marge
                    required_distance = (w1 + w2) / 2 + base_min_distance

                    if distance < required_distance and distance > 0.01:
                        # Vecteur unitaire
                        ux = dx / distance
                        uy = dy / distance

                        # ✅ Force PLUS FORTE pour redraw rapide
                        force = (required_distance - distance) * 0.25

                        # Appliquer déplacement
                        pos[node1][0] -= force * ux
                        pos[node1][1] -= force * uy
                        pos[node2][0] += force * ux
                        pos[node2][1] += force * uy

                        max_displacement = max(max_displacement, force)

            # ✅ Convergence anticipée
            if max_displacement < 0.02:
                logger.info(f"✅ Collision avoidance convergée à l'itération {iteration}")
                break

        return pos


    def _update_minimap(self):
        """Met à jour la minimap avec le viewport actuel."""
        if not hasattr(self, 'minimap_ax') or not self.minimap_ax:
            return

        # Effacer et redessiner
        self.minimap_ax.clear()
        self.minimap_ax.set_facecolor('#F5F5F5')

        pos = self.graph_data['pos']
        G = self.graph_data['G']

        for node in G.nodes():
            x, y = pos[node]
            self.minimap_ax.plot(x, y, 'o', color='#888888', markersize=2)

        # Viewport actuel
        ax = self.graph_data['ax']
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        from matplotlib.patches import Rectangle
        viewport_rect = Rectangle(
            (xlim[0], ylim[0]),
            xlim[1] - xlim[0],
            ylim[1] - ylim[0],
            fill=False,
            edgecolor='red',
            linewidth=2
        )
        self.minimap_ax.add_patch(viewport_rect)

        self.minimap_ax.set_xlim(self.graph_data['x_min'] - 5, self.graph_data['x_max'] + 5)
        self.minimap_ax.set_ylim(self.graph_data['y_min'] - 5, self.graph_data['y_max'] + 5)
        self.minimap_ax.axis('off')

    def _apply_collision_avoidance(self, G, pos, num_nodes):
        if num_nodes <= 10:
            min_distance = 0.6
        elif num_nodes <= 20:
            min_distance = 0.5
        elif num_nodes <= 50:
            min_distance = 0.4
        else:
            min_distance = 0.3

        iterations = 100 if num_nodes <= 30 else 60

        for iteration in range(iterations):
            nodes = list(G.nodes())

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    if distance < min_distance and distance > 0:
                        angle_cos = dx / distance if distance > 0 else 1
                        angle_sin = dy / distance if distance > 0 else 0

                        force = (min_distance - distance) / 8

                        pos[node1][0] -= force * angle_cos
                        pos[node1][1] -= force * angle_sin
                        pos[node2][0] += force * angle_cos
                        pos[node2][1] += force * angle_sin

            if iteration % 15 == 0:
                min_distance *= 0.99

        return pos

    def _show_node_info(self, node_name, G):
        """Affiche les informations du nœud sélectionné."""

        # Construire les informations
        info_text = f"<b>Nœud sélectionné:</b><br><br>"
        info_text += f"<b>Nom:</b> {node_name}<br>"

        node_data = G.nodes[node_name]
        node_type = node_data.get('node_type', 'unknown')
        info_text += f"<b>Type:</b> {node_type}<br><br>"

        # Relations sortantes
        outgoing = list(G.out_edges(node_name, data=True))
        info_text += f"<b>Relations sortantes ({len(outgoing)}):</b><br>"
        if outgoing:
            for source, target, data in outgoing[:10]:  # Afficher max 10
                rel_type = data.get('relation_type', 'relation')
                info_text += f"  → {target} ({rel_type})<br>"
            if len(outgoing) > 10:
                info_text += f"  ... et {len(outgoing) - 10} autres<br>"
        else:
            info_text += "  Aucune<br>"

        info_text += "<br>"

        # Relations entrantes
        incoming = list(G.in_edges(node_name, data=True))
        info_text += f"<b>Relations entrantes ({len(incoming)}):</b><br>"
        if incoming:
            for source, target, data in incoming[:10]:  # Afficher max 10
                rel_type = data.get('relation_type', 'relation')
                info_text += f"  ← {source} ({rel_type})<br>"
            if len(incoming) > 10:
                info_text += f"  ... et {len(incoming) - 10} autres<br>"
        else:
            info_text += "  Aucune<br>"

        # Afficher dans la barre de statut ou une fenêtre popup
        self._show_node_details_popup(node_name, info_text)

    def _show_node_details_popup(self, node_name, info_text):
        """Affiche un popup avec les détails du nœud."""
        from PyQt5 import QtWidgets

        popup = QtWidgets.QMessageBox(self)
        popup.setWindowTitle(f"Détails: {node_name}")
        popup.setText("")
        popup.setInformativeText(info_text)
        popup.setIcon(QtWidgets.QMessageBox.Information)
        popup.setStandardButtons(QtWidgets.QMessageBox.Ok)
        popup.setTextFormat(1)  # RichText
        popup.setMinimumWidth(400)
        popup.exec_()
    
    def refresh(self):
        """Rafraîchit le widget."""
        self._update_status("Rafraîchissement...")
        self._load_projects_list()
        self._update_cache_info()
    
    def _update_node_info_display(self, node_name, G):
        """Affiche les informations du nœud sélectionné dans la zone dédiée."""
        if not hasattr(self, 'info_ax'):
            return

        self.info_ax.clear()
        self.info_ax.axis('off')

        if node_name is None:
            # Afficher un message par défaut
            self.info_ax.text(0.5, 0.5, "Cliquez sur un nœud\npour voir ses détails", 
                             ha='center', va='center', 
                             color='#999999', fontsize=10, 
                             style='italic', wrap=True)
            return

        # Récupérer les informations du nœud
        node_data = G.nodes[node_name]
        node_type = node_data.get('node_type', 'unknown')

        # Relations sortantes
        outgoing = list(G.out_edges(node_name, data=True))
        # Relations entrantes
        incoming = list(G.in_edges(node_name, data=True))

        # Construire le texte d'information
        info_lines = []
        info_lines.append("NŒUD SÉLECTIONNÉ")
        info_lines.append("─" * 25)
        info_lines.append("")

        # Afficher le nom complet sur plusieurs lignes si nécessaire
        if len(node_name) <= 25:
            info_lines.append(f"Nom: {node_name}")
        else:
            info_lines.append(f"Nom:")
            # Découper le nom en morceaux de 25 caractères
            for i in range(0, len(node_name), 25):
                info_lines.append(f"  {node_name[i:i+25]}")

        info_lines.append("")
        info_lines.append(f"Type: {node_type}")
        info_lines.append("")
        info_lines.append(f"Relations sortantes: {len(outgoing)}")

        # Afficher quelques relations sortantes
        for i, (source, target, data) in enumerate(outgoing[:3]):
            rel_type = data.get('relation_type', 'relation')
            target_short = target[:18] + ".." if len(target) > 18 else target
            info_lines.append(f"  → {target_short}")
            if len(rel_type) <= 20:
                info_lines.append(f"    [{rel_type}]")
            else:
                info_lines.append(f"    [{rel_type[:17]}...]")

        if len(outgoing) > 3:
            info_lines.append(f"  ... +{len(outgoing) - 3} autre(s)")

        info_lines.append("")
        info_lines.append(f"Relations entrantes: {len(incoming)}")

        # Afficher quelques relations entrantes
        for i, (source, target, data) in enumerate(incoming[:3]):
            rel_type = data.get('relation_type', 'relation')
            source_short = source[:18] + ".." if len(source) > 18 else source
            info_lines.append(f"  ← {source_short}")
            if len(rel_type) <= 20:
                info_lines.append(f"    [{rel_type}]")
            else:
                info_lines.append(f"    [{rel_type[:17]}...]")

        if len(incoming) > 3:
            info_lines.append(f"  ... +{len(incoming) - 3} autre(s)")

        # Afficher le texte
        text = "\n".join(info_lines)
        self.info_ax.text(0.05, 0.95, text, 
                         ha='left', va='top', 
                         color='#333333', fontsize=8, 
                         family='monospace',
                         bbox=dict(boxstyle='round,pad=0.5', 
                                 facecolor='#F9F9F9', 
                                 edgecolor='#CCCCCC', 
                                 alpha=0.95))

    def _apply_local_collision_avoidance(self, dragging_node):
        pos = self.graph_data['pos']
        G = self.graph_data['G']
        num_nodes = self.graph_data['num_nodes']
        node_orbits = self.graph_data.get('node_orbits', {})

        # ✅ RÉCUPÉRER LES DIMENSIONS depuis graph_data (garantit cohérence)
        text_width = self.graph_data.get('text_width', 5.0)
        text_height = self.graph_data.get('text_height', 1.3)
        max_chars = self.graph_data.get('max_chars', 25)

        # Distance minimale adaptée
        if num_nodes <= 10:
            base_min_distance = 2.5
            orbit_tolerance = 2.0
        elif num_nodes <= 20:
            base_min_distance = 2.0
            orbit_tolerance = 2.5
        elif num_nodes <= 40:
            base_min_distance = 1.8
            orbit_tolerance = 3.0
        else:
            base_min_distance = 1.5
            orbit_tolerance = 3.5

        x1, y1 = pos[dragging_node]

        # ✅ Calculer la distance du nœud draggé par rapport au centre
        dist_dragged = (x1**2 + y1**2) ** 0.5

        # ✅ Récupérer l'orbite du nœud draggé
        dragged_orbit = node_orbits.get(dragging_node, 3)

        # Déplacer les nœuds qui sont trop proches
        for node in G.nodes():
            if node == dragging_node or node == self.current_central_name:
                continue
            
            x2, y2 = pos[node]
            dist_node = (x2**2 + y2**2) ** 0.5

            # ✅ Récupérer l'orbite de l'autre nœud
            node_orbit = node_orbits.get(node, 3)

            dx = x2 - x1
            dy = y2 - y1
            distance = (dx**2 + dy**2) ** 0.5

            # ✅ Distance requise basée sur dimensions AUGMENTÉES de graph_data
            required_distance = (text_width + text_height) / 2 + base_min_distance

            if distance < required_distance and distance > 0.01:

                # ✅ VÉRIFIER SI MÊME ORBITE
                # Utiliser à la fois la distance ET le numéro d'orbite
                same_orbit_distance = abs(dist_dragged - dist_node) < orbit_tolerance
                same_orbit_number = (dragged_orbit == node_orbit)
                same_orbit = same_orbit_distance and same_orbit_number

                if same_orbit:
                    # ===== MÊME ORBITE : MOUVEMENT TANGENTIEL (ROTATION) =====

                    # Calculer les angles
                    angle_dragged = math.atan2(y1, x1)
                    angle_node = math.atan2(y2, x2)

                    # Force angulaire pour écarter sans changer de rayon
                    force = (required_distance - distance) * 0.02

                    # Calculer le rayon moyen
                    avg_radius = (dist_dragged + dist_node) / 2

                    # Convertir force linéaire en angle
                    if avg_radius > 0.01:
                        angle_force = force / avg_radius
                    else:
                        angle_force = force * 0.1

                    # Rotation : éloigner l'autre nœud
                    new_angle = angle_node + angle_force

                    # Recalculer position EN GARDANT LE MÊME RAYON
                    pos[node][0] = dist_node * math.cos(new_angle)
                    pos[node][1] = dist_node * math.sin(new_angle)

                    logger.debug(f"  🔄 Rotation tangentielle: {node} (orbite {node_orbit})")

                else:
                    # ===== ORBITES DIFFÉRENTES : MOUVEMENT RADIAL =====

                    # Direction radiale pour l'autre nœud
                    if dist_node > 0.01:
                        radial_dir_x = x2 / dist_node
                        radial_dir_y = y2 / dist_node
                    else:
                        radial_dir_x = 1.0
                        radial_dir_y = 0.0

                    # Force radiale pour éloigner
                    radial_force = (required_distance - distance) * 0.25

                    # Déterminer la direction selon les orbites
                    if dragged_orbit < node_orbit:
                        # Nœud draggé sur orbite intérieure : pousser l'autre vers l'extérieur
                        pos[node][0] += radial_force * radial_dir_x
                        pos[node][1] += radial_force * radial_dir_y
                        logger.debug(f"  ↗️ Poussée radiale vers extérieur: {node} "
                                   f"(orbite {dragged_orbit} → {node_orbit})")
                    elif dragged_orbit > node_orbit:
                        # Nœud draggé sur orbite extérieure : pousser l'autre vers l'intérieur
                        pos[node][0] -= radial_force * radial_dir_x
                        pos[node][1] -= radial_force * radial_dir_y
                        logger.debug(f"  ↙️ Poussée radiale vers intérieur: {node} "
                                   f"(orbite {dragged_orbit} → {node_orbit})")
                    else:
                        # Même numéro d'orbite mais distance différente : 
                        # ajuster radialement selon distance
                        if dist_node < dist_dragged:
                            pos[node][0] -= radial_force * radial_dir_x
                            pos[node][1] -= radial_force * radial_dir_y
                        else:
                            pos[node][0] += radial_force * radial_dir_x
                            pos[node][1] += radial_force * radial_dir_y

    def closeEvent(self, event):
        """Fermeture propre."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)