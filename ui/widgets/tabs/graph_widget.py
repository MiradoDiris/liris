# graph_widget.py - Version complète intégrant le design et principes de relation_import_widget.py
import math
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
from matplotlib.patches import Circle, FancyBboxPatch

from utils.logger import logger
from utils.dgraph_connector import LirisDgraphConnector

class QueryCache:
    """✅ Cache optimisé avec statistiques"""
    
    def __init__(self, ttl_seconds=600):  # 10 minutes
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                self.hits += 1
                return data
            else:
                del self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Dict):
        self.cache[key] = (value, datetime.now())
    
    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> str:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return f"Cache: {len(self.cache)} entrées, {hit_rate:.1f}% hits"


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
        self.persistent_selected_items = []
        self.hierarchy_levels = {}
        self.relation_categories = {}

        # Système de cache
        self.query_cache = QueryCache(ttl_seconds=600)

        # Cache pour les mappings UID
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}

        # ✅ AJOUT CRITIQUE : Caches pour résolution UID
        self.uid_to_name_cache = {}
        self.name_to_uid_cache = {}
        self.uid_metadata_cache = {}

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
        """✅ VERSION CORRIGÉE : Garde l'extension pour les fichiers"""
        if not name or not isinstance(name, str):
            return f"unnamed_{id(name)}"

        name = name.strip()
        if not name or name.lower() == 'n/a':
            return f"unnamed_{id(name)}"

        # Garder seulement le basename (sans chemin)
        base = os.path.basename(name)

        # ✅ CORRECTION : Garder l'extension pour TOUS les fichiers
        # Liste des extensions de code reconnues
        code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg',
            '.html', '.css', '.scss', '.sass', '.md', '.txt'
        }

        # Si le fichier a une extension reconnue, le garder tel quel
        if '.' in base:
            ext = '.' + base.split('.')[-1].lower()
            if ext in code_extensions:
                return base  # ✅ Garde "user.py" au lieu de "user"

        # Pour les noms sans extension (classes, fonctions), supprimer si présent
        name_without_ext = os.path.splitext(base)[0]
        normalized = name_without_ext.strip()

        if not normalized:
            return f"unnamed_{id(name)}"

        return normalized
    
    def _format_node_display_name(self, node_name: str, node_type: str = None) -> str:
        if not node_name:
            return "Unknown"

        # Garder seulement le basename (sans chemin)
        display_name = os.path.basename(node_name)

        # ✅ MAPPING COMPLET : Préfixes longs → courts (multilingue)
        prefix_mapping = {
            # Functions
            'function:': 'F:', 'fonction:': 'F:', 'func:': 'F:',
            'Function:': 'F:', 'Fonction:': 'F:', 'Func:': 'F:',
            'method:': 'M:', 'methode:': 'M:', 'méthode:': 'M:',
            'Method:': 'M:', 'Methode:': 'M:', 'Méthode:': 'M:',
            'class:': 'C:', 'classe:': 'C:',
            'Class:': 'C:', 'Classe:': 'C:',
            'variable:': 'V:', 'var:': 'V:',
            'Variable:': 'V:', 'Var:': 'V:',
            'file:': '', 'fichier:': '',
            'module:': 'Mod:', 'package:': 'Pkg:',
        }

        # ✅ 1. DÉTECTER ET REMPLACER les préfixes dans le nom lui-même
        display_lower = display_name.lower()
        for long_prefix, short_prefix in prefix_mapping.items():
            if display_lower.startswith(long_prefix):
                # Extraire le nom sans le préfixe long
                actual_name = display_name[len(long_prefix):].strip()
                # Si c'est un fichier (préfixe vide), retourner tel quel
                if not short_prefix:
                    return actual_name
                # Sinon ajouter le préfixe court
                return f"{short_prefix} {actual_name}"

        # ✅ 2. Si pas de préfixe détecté dans le nom, utiliser node_type
        type_prefixes = {
            'function': 'F:',
            'method': 'M:',
            'class': 'C:',
            'variable': 'V:',
            'module': 'Mod:',
            'package': 'Pkg:',
        }

        # Pour les fichiers, garder l'extension
        if node_type == 'file' or '.' in display_name:
            return display_name

        # Pour les autres, supprimer l'extension si présente
        name_without_ext = os.path.splitext(display_name)[0]
        final_name = name_without_ext if name_without_ext else display_name

        # ✅ Ajouter le préfixe court si type reconnu
        if node_type and node_type.lower() in type_prefixes:
            prefix = type_prefixes[node_type.lower()]
            return f"{prefix} {final_name}"

        return final_name
    
    def _get_dgraph_to_local_mapping(self):
        """Retourne le mapping Dgraph UID -> Local UID."""
        if not hasattr(self, 'dgraph_to_local') or not self.dgraph_to_local:
            self._load_uid_mappings()
        return getattr(self, 'dgraph_to_local', {})
    
    def _get_node_uid_by_name(self, node_name: str) -> str:
        if not node_name:
            return None

        # Utiliser le nouveau système de résolution
        return self._resolve_name_to_uid(node_name)
    
    def _preload_uid_cache(self, uids: List[str]):
        """✅ VERSION CORRIGÉE : Vérifie que les caches existent"""
        if not uids:
            return

        # ✅ Initialiser les caches s'ils n'existent pas
        if not hasattr(self, 'uid_to_name_cache'):
            self.uid_to_name_cache = {}
        if not hasattr(self, 'name_to_uid_cache'):
            self.name_to_uid_cache = {}
        if not hasattr(self, 'uid_metadata_cache'):
            self.uid_metadata_cache = {}

        logger.info(f"📦 Pré-chargement cache: {len(uids)} UIDs")
        self._resolve_uids_batch(uids)
        logger.info(f"✅ Cache prêt: {len(self.uid_to_name_cache)} entrées")

    def _ensure_caches_initialized(self):
        """✅ NOUVEAU : S'assure que tous les caches sont initialisés"""
        if not hasattr(self, 'uid_to_name_cache'):
            self.uid_to_name_cache = {}
            logger.debug("📦 Initialisation uid_to_name_cache")

        if not hasattr(self, 'name_to_uid_cache'):
            self.name_to_uid_cache = {}
            logger.debug("📦 Initialisation name_to_uid_cache")

        if not hasattr(self, 'uid_metadata_cache'):
            self.uid_metadata_cache = {}
            logger.debug("📦 Initialisation uid_metadata_cache")

    def update_graph_with_internal_structure(self, central_node: str, central_uid: str, 
                                         node_data: Dict, project_data: Dict):
        """
        Affiche la structure INTERNE d'un fichier
        (classes, fonctions, variables) au lieu des relations externes
        """
        logger.info(f"=== UPDATE_GRAPH_WITH_INTERNAL_STRUCTURE ===")
        logger.info(f"  Central: {central_node}, UID: {central_uid}")

        if not central_node or not node_data:
            self._clear_graph()
            return

        self.current_project_data = project_data
        self.central_node = central_node
        self.current_central_uid = central_uid

        # Construire un graphe basé sur la structure INTERNE
        internal_relations = []

        # Récupérer les éléments de code
        classes = node_data.get('classes', [])
        functions = node_data.get('functions', [])
        variables = node_data.get('variables', [])

        # 1. Fichier -> Classes
        for cls in classes:
            cls_name = cls.get('name', 'UnnamedClass')
            internal_relations.append({
                'source': central_node,
                'target': cls_name,
                'relation_type': 'contains_class',
                'category': 'structure'
            })

            # Classe -> Méthodes
            for method in cls.get('methods', []):
                method_name = method.get('name', 'UnnamedMethod')
                internal_relations.append({
                    'source': cls_name,
                    'target': f"{cls_name}.{method_name}",
                    'relation_type': 'has_method',
                    'category': 'structure'
                })

            # Classe -> Variables
            for var in cls.get('variables', []):
                var_name = var.get('name', 'UnnamedVar')
                internal_relations.append({
                    'source': cls_name,
                    'target': f"{cls_name}.{var_name}",
                    'relation_type': 'has_variable',
                    'category': 'structure'
                })

        # 2. Fichier -> Fonctions
        for func in functions:
            func_name = func.get('name', 'UnnamedFunction')
            internal_relations.append({
                'source': central_node,
                'target': func_name,
                'relation_type': 'contains_function',
                'category': 'structure'
            })

        # 3. Fichier -> Variables globales
        for var in variables:
            var_name = var.get('name', 'UnnamedVariable')
            internal_relations.append({
                'source': central_node,
                'target': var_name,
                'relation_type': 'contains_variable',
                'category': 'structure'
            })

        # Construire et afficher le graphe
        self.current_relations = internal_relations
        self.current_graph = self._build_clean_graph(internal_relations)

        # Ajouter les métadonnées de type
        for node in self.current_graph.nodes:
            self.current_graph.nodes[node]['node_type'] = self._detect_node_type(
                node, central_node, classes, functions, variables
            )
            self.current_graph.nodes[node]['level'] = 0

        self._draw_graph()
        self._update_info_label()

    def _detect_hierarchical_context(self, selected_uid: str, selected_name: str) -> Dict:
        """
        ✅ NOUVEAU : Détecte le contexte hiérarchique d'un élément sélectionné
        Retourne les informations sur les parents, enfants et éléments de code associés
        """
        context = {
            'has_hierarchy': False,
            'parents': [],
            'children': [],
            'code_elements': [],
            'display_mode': 'standard'  # 'standard', 'hierarchy', 'internal_structure'
        }

        if not selected_uid or not self.dgraph_connector:
            return context

        # Requête pour récupérer le contexte hiérarchique complet
        query = f"""
        {{
          node(func: uid({selected_uid})) {{
            uid
            name
            nodeType

            # Relations hiérarchiques directes
            parents {{
              uid
              name
              nodeType
              path
            }}

            children: ~parents {{
              uid
              name
              nodeType
              path
              level
            }}

            # Éléments de code contenus
            classes {{
              uid
              name
              description
              line
              methods {{ uid name description line }}
              variables {{ uid name description line }}
            }}

            functions {{
              uid
              name
              description
              line
              variables {{ uid name description line }}
            }}

            variables {{
              uid
              name
              description
              line
            }}

            # Relations inverses (éléments qui pointent vers ce nœud)
            ~classes {{
              uid
              name
              nodeType
            }}

            ~functions {{
              uid
              name
              nodeType
            }}

            ~variables {{
              uid
              name
              nodeType
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if not result or 'node' not in result or not result['node']:
            return context

        node_data = result['node'][0]

        # Analyser les parents
        parents = node_data.get('parents', [])
        context['parents'] = [
            {
                'uid': p.get('uid'),
                'name': self.normalize_node_name(p.get('name', '')),
                'type': p.get('nodeType', 'unknown')
            }
            for p in parents if p.get('uid') and p.get('name')
        ]

        # Analyser les enfants
        children = node_data.get('children', [])
        context['children'] = [
            {
                'uid': c.get('uid'),
                'name': self.normalize_node_name(c.get('name', '')),
                'type': c.get('nodeType', 'unknown'),
                'level': c.get('level', 1)
            }
            for c in children if c.get('uid') and c.get('name')
        ]

        # Analyser les éléments de code
        code_elements = []

        # Classes avec leurs méthodes
        for cls in node_data.get('classes', []):
            if cls.get('name'):
                cls_element = {
                    'uid': cls.get('uid'),
                    'name': cls.get('name'),
                    'type': 'class',
                    'line': cls.get('line'),
                    'children': []
                }

                # Méthodes de la classe
                for method in cls.get('methods', []):
                    if method.get('name'):
                        cls_element['children'].append({
                            'uid': method.get('uid'),
                            'name': method.get('name'),
                            'type': 'method',
                            'line': method.get('line')
                        })

                # Variables de la classe
                for var in cls.get('variables', []):
                    if var.get('name'):
                        cls_element['children'].append({
                            'uid': var.get('uid'),
                            'name': var.get('name'),
                            'type': 'variable',
                            'line': var.get('line')
                        })

                code_elements.append(cls_element)

        # Fonctions
        for func in node_data.get('functions', []):
            if func.get('name'):
                func_element = {
                    'uid': func.get('uid'),
                    'name': func.get('name'),
                    'type': 'function',
                    'line': func.get('line'),
                    'children': []
                }

                # Variables de la fonction
                for var in func.get('variables', []):
                    if var.get('name'):
                        func_element['children'].append({
                            'uid': var.get('uid'),
                            'name': var.get('name'),
                            'type': 'variable',
                            'line': var.get('line')
                        })

                code_elements.append(func_element)

        # Variables globales
        for var in node_data.get('variables', []):
            if var.get('name'):
                code_elements.append({
                    'uid': var.get('uid'),
                    'name': var.get('name'),
                    'type': 'variable',
                    'line': var.get('line'),
                    'children': []
                })

        context['code_elements'] = code_elements

        # Déterminer le mode d'affichage
        has_parents = len(context['parents']) > 0
        has_children = len(context['children']) > 0
        has_code = len(code_elements) > 0

        context['has_hierarchy'] = has_parents or has_children or has_code

        if has_code and (has_parents or has_children):
            context['display_mode'] = 'hierarchy'
        elif has_code:
            context['display_mode'] = 'internal_structure'
        elif has_parents or has_children:
            context['display_mode'] = 'hierarchy'
        else:
            context['display_mode'] = 'standard'

        logger.info(f"🔍 Contexte hiérarchique pour {selected_name}:")
        logger.info(f"  Parents: {len(context['parents'])}")
        logger.info(f"  Enfants: {len(context['children'])}")
        logger.info(f"  Éléments de code: {len(code_elements)}")
        logger.info(f"  Mode d'affichage: {context['display_mode']}")

        return context

    def _detect_node_type(self, node_name, central_node, classes, functions, variables):
        """Détecte le type d'un nœud pour le style"""
        if node_name == central_node:
            return 'file'
        elif '.' in node_name:
            return 'function' if 'method' in node_name else 'variable'
        elif any(cls.get('name') == node_name for cls in classes):
            return 'class'
        elif any(func.get('name') == node_name for func in functions):
            return 'function'
        else:
            return 'variable'

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
        """Exécute une requête Dgraph"""
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
    
    def _calculate_hierarchy_level(self, node_name: str, central_node: str, relations: List[Dict]) -> int:
        if node_name == central_node:
            return 0
        
        # BFS pour trouver le chemin le plus court vers le nœud central
        from collections import deque, defaultdict
        
        # Construire le graphe des connexions
        graph = defaultdict(list)
        for rel in relations:
            source = rel.get('source', '')
            target = rel.get('target', '')
            
            if source and target:
                # Relations bidirectionnelles pour la hiérarchie
                graph[source].append(target)
                graph[target].append(source)
        
        # BFS depuis le nœud central
        queue = deque([(central_node, 0)])
        visited = {central_node}
        
        while queue:
            current_node, level = queue.popleft()
            
            if current_node == node_name:
                return level
            
            for neighbor in graph[current_node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, level + 1))
        
        # Si pas de chemin trouvé, considérer comme niveau 2 (externe)
        return 2

    def update_graph(self, central_node: str, central_uid: str, related_items: List[Dict], 
                project_data: Dict, append_mode: bool = False):
    
        logger.info(f"\n{'='*70}")
        logger.info(f"🕸️ UPDATE_GRAPH (Mode: {'Ajout' if append_mode else 'Remplacement'})")
        logger.info(f"{'='*70}")
        logger.info(f"  Central: {central_node}")
        logger.info(f"  UID: {central_uid}")
        logger.info(f"  Related items: {len(related_items)}")

        # ✅ VALIDATION DE BASE
        if not central_node or not central_uid:
            if not append_mode:
                self._clear_graph()
            logger.warning("⚠️ Nœud central manquant")
            return

        # ✅ Sauvegarder contexte
        self.current_project_data = project_data
        self.central_node = central_node
        self.current_central_uid = central_uid
        self.current_central_name = central_node

        # ✅ Détection niveau
        level = 1
        for item in related_items:
            if item.get('search_depth'):
                level = item['search_depth']
                break
            
        logger.info(f"  Niveau détecté: {level}")

        # ✅ RÉCUPÉRATION RELATIONS (TOUJOURS)
        logger.info(f"📡 Récupération relations niveau {level}...")
        new_relations = self._get_complete_relations(central_uid, level)

        if not new_relations:
            logger.warning("⚠️ Aucune relation récupérée")
            if not append_mode:
                self._clear_graph()
            return

        logger.info(f"📊 {len(new_relations)} relations récupérées")

        # ✅ VALIDATION FORMAT
        validated_relations = self._validate_relations_format(new_relations)

        if not validated_relations:
            logger.error("❌ Aucune relation valide après validation")
            if not append_mode:
                self._clear_graph()
            return

        # ✅ CONSTRUCTION GRAPHE (TOUJOURS)
        logger.info(f"🔨 Construction du graphe...")
        self.current_relations = validated_relations

        G = self._build_clean_graph(validated_relations)

        if not G or len(G.nodes()) == 0:
            logger.error("❌ Graphe vide après construction")
            if not append_mode:
                self._clear_graph()
            return

        # ✅ ENRICHISSEMENT MÉTADONNÉES
        for node in G.nodes():
            node_uid = G.nodes[node].get('uid')

            if node_uid:
                node_details = self._get_node_details(node_uid)
                G.nodes[node]['level'] = node_details.get('level', 0)
                if not G.nodes[node].get('node_type'):
                    G.nodes[node]['node_type'] = node_details.get('nodeType', 'unknown')
            else:
                G.nodes[node]['level'] = 0
                if not G.nodes[node].get('node_type'):
                    G.nodes[node]['node_type'] = 'unknown'

        # ✅ AFFICHAGE
        self.current_graph = G  # CRITIQUE : Sauvegarder avant dessin
        self._draw_graph()

        logger.info(f"✅ Graphe généré avec {len(G.nodes())} nœuds, {len(G.edges())} arêtes")
        logger.info(f"{'='*70}\n")
        if not self.current_graph or len(self.current_graph.nodes()) == 0:
            logger.error("❌ ÉCHEC update_graph - Lancement diagnostic...")
        self._diagnose_graph_display_issue()

    def _diagnose_graph_display_issue(self):
        """
        Diagnostic complet des problèmes d'affichage du graphe
        À ajouter dans la classe GraphWidget
        """
        logger.info("\n" + "="*80)
        logger.info("🔍 DIAGNOSTIC AFFICHAGE GRAPHE")
        logger.info("="*80)
        
        # 1. Vérifier l'état du widget
        logger.info(f"Widget visible: {self.isVisible()}")
        logger.info(f"Widget enabled: {self.isEnabled()}")
        logger.info(f"Widget size: {self.size().width()}x{self.size().height()}")
        
        # 2. Vérifier pyvis
        if not hasattr(self, 'network') or self.network is None:
            logger.error("❌ self.network n'existe pas ou est None")
            return
        
        logger.info(f"✅ Network object exists: {type(self.network)}")
        
        # 3. Vérifier les nœuds et arêtes
        try:
            nodes_count = len(self.network.nodes) if hasattr(self.network, 'nodes') else 0
            edges_count = len(self.network.edges) if hasattr(self.network, 'edges') else 0
            
            logger.info(f"📊 Nœuds: {nodes_count}")
            logger.info(f"📊 Arêtes: {edges_count}")
            
            if nodes_count == 0:
                logger.warning("⚠️ Aucun nœud dans le graphe")
            
            # Afficher les premiers nœuds
            if nodes_count > 0 and hasattr(self.network, 'nodes'):
                logger.info("📋 Premiers nœuds:")
                for i, node in enumerate(self.network.nodes[:3]):
                    logger.info(f"   - Nœud {i+1}: {node}")
            
            # Afficher les premières arêtes
            if edges_count > 0 and hasattr(self.network, 'edges'):
                logger.info("📋 Premières arêtes:")
                for i, edge in enumerate(self.network.edges[:3]):
                    logger.info(f"   - Arête {i+1}: {edge}")
                    
        except Exception as e:
            logger.error(f"❌ Erreur lors du comptage: {e}")
        
        # 4. Vérifier le QWebEngineView
        if not hasattr(self, 'web_view') or self.web_view is None:
            logger.error("❌ self.web_view n'existe pas ou est None")
            return
        
        logger.info(f"✅ WebView exists: {type(self.web_view)}")
        logger.info(f"WebView visible: {self.web_view.isVisible()}")
        logger.info(f"WebView size: {self.web_view.size().width()}x{self.web_view.size().height()}")
        
        # 5. Vérifier l'URL chargée
        try:
            current_url = self.web_view.url().toString()
            logger.info(f"📄 URL actuelle: {current_url}")
            
            if not current_url or current_url == "about:blank":
                logger.warning("⚠️ Aucun contenu chargé dans WebView")
        except Exception as e:
            logger.error(f"❌ Erreur URL: {e}")
        
        # 6. Vérifier le fichier HTML temporaire
        if hasattr(self, 'temp_html_path') and self.temp_html_path:
            import os
            if os.path.exists(self.temp_html_path):
                file_size = os.path.getsize(self.temp_html_path)
                logger.info(f"✅ Fichier HTML: {self.temp_html_path}")
                logger.info(f"   Taille: {file_size} bytes")
                
                # Lire un extrait du fichier
                try:
                    with open(self.temp_html_path, 'r', encoding='utf-8') as f:
                        content = f.read(500)  # Premiers 500 caractères
                        logger.info(f"   Contenu (extrait): {content[:200]}...")
                except Exception as e:
                    logger.error(f"❌ Erreur lecture fichier: {e}")
            else:
                logger.error(f"❌ Fichier HTML introuvable: {self.temp_html_path}")
        else:
            logger.warning("⚠️ Pas de temp_html_path défini")
        
        # 7. Vérifier le layout
        layout = self.layout()
        if layout:
            logger.info(f"✅ Layout exists: {type(layout)}")
            logger.info(f"   Widget count: {layout.count()}")
        else:
            logger.error("❌ Pas de layout")
        
        logger.info("="*80 + "\n")

    def update_graph_with_hierarchical_relations(self, central_node: str, central_uid: str, 
                                           hierarchical_context: Dict, project_data: Dict, 
                                           append_mode: bool = False):

        logger.info(f"=== UPDATE_GRAPH_WITH_HIERARCHICAL_RELATIONS ===")
        logger.info(f"  Central: {central_node}, UID: {central_uid}")

        if not central_node or not hierarchical_context:
            self._clear_graph()
            return

        self.current_project_data = project_data
        self.central_node = central_node
        self.current_central_uid = central_uid

        # Construire un graphe basé sur la hiérarchie COMPLÈTE
        hierarchical_relations = []

        # ✅ 1. RELATIONS AVEC LES PARENTS
        for parent in hierarchical_context.get('parents', []):
            if parent['name'] and parent['name'] != central_node:
                hierarchical_relations.append({
                    'source': parent['name'],
                    'source_uid': parent['uid'],
                    'source_type': parent['type'],
                    'target': central_node,
                    'target_uid': central_uid,
                    'target_type': 'file',  # ou détecté
                    'relation_type': 'parent',
                    'category': 'hierarchy'
                })

        # ✅ 2. RELATIONS AVEC LES ENFANTS
        for child in hierarchical_context.get('children', []):
            if child['name'] and child['name'] != central_node:
                hierarchical_relations.append({
                    'source': central_node,
                    'source_uid': central_uid,
                    'source_type': 'file',
                    'target': child['name'],
                    'target_uid': child['uid'],
                    'target_type': child['type'],
                    'relation_type': 'child',
                    'category': 'hierarchy'
                })

        # ✅ 3. ÉLÉMENTS DE CODE (classes, fonctions, variables)
        for code_element in hierarchical_context.get('code_elements', []):
            element_name = code_element['name']
            element_type = code_element['type']

            # Relation : fichier -> élément de code
            relation_type = f'contains_{element_type}'
            if element_type == 'method':
                relation_type = 'has_method'

            hierarchical_relations.append({
                'source': central_node,
                'source_uid': central_uid,
                'source_type': 'file',
                'target': element_name,
                'target_uid': code_element['uid'],
                'target_type': element_type,
                'relation_type': relation_type,
                'category': 'structure'
            })

            # ✅ 4. RELATIONS ENTRE ÉLÉMENTS DE CODE (classe -> méthodes/variables)
            for child_element in code_element.get('children', []):
                child_name = child_element['name']
                child_type = child_element['type']

                if element_type == 'class':
                    if child_type == 'method':
                        relation_type = 'has_method'
                    elif child_type == 'variable':
                        relation_type = 'has_variable'
                    else:
                        relation_type = 'contains'
                elif element_type == 'function' and child_type == 'variable':
                    relation_type = 'has_variable'
                else:
                    relation_type = 'contains'

                hierarchical_relations.append({
                    'source': element_name,
                    'source_uid': code_element['uid'],
                    'source_type': element_type,
                    'target': child_name,
                    'target_uid': child_element['uid'],
                    'target_type': child_type,
                    'relation_type': relation_type,
                    'category': 'structure'
                })

        logger.info(f"📊 {len(hierarchical_relations)} relations hiérarchiques créées")

        # Construire et afficher le graphe
        self.current_relations = hierarchical_relations
        self.current_graph = self._build_clean_graph(hierarchical_relations)

        # ✅ ENRICHIR LES MÉTADONNÉES avec niveau hiérarchique
        for node in self.current_graph.nodes:
            node_data = self.current_graph.nodes[node]

            # Déterminer le type de nœud
            if node == central_node:
                node_data['node_type'] = 'file'
                node_data['hierarchy_level'] = 0  # Nœud central
            else:
                # Chercher dans le contexte hiérarchique
                node_type = 'unknown'
                hierarchy_level = 1

                # Vérifier si c'est un parent
                for parent in hierarchical_context.get('parents', []):
                    if parent['name'] == node:
                        node_type = parent['type']
                        hierarchy_level = -1  # Parent = niveau supérieur
                        break
                    
                # Vérifier si c'est un enfant
                if node_type == 'unknown':
                    for child in hierarchical_context.get('children', []):
                        if child['name'] == node:
                            node_type = child['type']
                            hierarchy_level = 1
                            break
                        
                # Vérifier si c'est un élément de code
                if node_type == 'unknown':
                    for code_element in hierarchical_context.get('code_elements', []):
                        if code_element['name'] == node:
                            node_type = code_element['type']
                            hierarchy_level = 1
                            break
                        
                        # Vérifier dans les enfants de l'élément de code
                        for child_element in code_element.get('children', []):
                            if child_element['name'] == node:
                                node_type = child_element['type']
                                hierarchy_level = 2
                                break
                            
                node_data['node_type'] = node_type
                node_data['hierarchy_level'] = hierarchy_level

            node_data['level'] = 0  # Pour compatibilité

        self._draw_graph()
        self._update_info_label()

        logger.info(f"✅ Graphe hiérarchique généré avec {len(self.current_graph.nodes)} nœuds, {len(self.current_graph.edges)} arêtes")

    def _get_orbit_color(self, orbit_num: int) -> tuple:
        """✅ NOUVEAU : Retourne les couleurs pour chaque orbite"""
        orbit_colors = {
            1: ('#2196F3', '#1565C0'),  # Bleu pour hiérarchique
            2: ('#00ACC1', '#00838F'),  # Cyan pour code interne
            3: ('#FF8C00', '#E65100')   # Orange pour externe
        }
        return orbit_colors.get(orbit_num, ('#999999', '#666666'))

    def _validate_relations_format(self, relations_list: List[Dict]) -> List[Dict]:
        """✅ CORRECTION : Validation sans perte de relations externes"""
        validated_relations = []

        for rel in relations_list:
            if not isinstance(rel, dict):
                continue

            # ✅ GARDER LES NOMS ORIGINAUX (avec extension)
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()

            # ✅ Validation minimale (permettre même source=target pour import self)
            if not source or not target:
                continue

            # ✅ CORRECTION : Ne rejeter que les vrais doublons (même nom ET pas import)
            rel_type = rel.get('relation_type') or rel.get('relationType', 'unknown')
            if source == target:
                # Accepter auto-imports/références pour tous les systèmes
                if rel_type.lower() not in ['import', 'self_import', 'self_reference', 'from_import', 'require', 'include']:
                    continue

            # ✅ Construire relation normalisée
            normalized_rel = {
                'source': source,
                'source_uid': rel.get('source_uid', ''),
                'source_type': rel.get('source_type', 'file'),  # ✅ Défaut: file
                'target': target,
                'target_uid': rel.get('target_uid', ''),
                'target_type': rel.get('target_type', 'file'),  # ✅ Défaut: file
                'relation_type': rel_type,
                'category': rel.get('category', 'external'),  # ✅ Défaut: external
                'line': rel.get('line'),
                'intraFile': rel.get('intraFile', False)
            }

            validated_relations.append(normalized_rel)

        logger.info(f"✅ {len(validated_relations)} relations validées sur {len(relations_list)}")

        # ✅ DIAGNOSTIC : Compter par type
        type_counts = {}
        for rel in validated_relations:
            rel_type = rel['relation_type']
            type_counts[rel_type] = type_counts.get(rel_type, 0) + 1

        logger.info(f"📊 Types de relations validées:")
        for rel_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"   • {rel_type}: {count}")

        return validated_relations

    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """✅ CORRECTION FINALE : Support complet des relations externes"""
        G = nx.DiGraph()
        nodes_registry = {}
        edges_registry = {}

        logger.info(f"🔨 Construction graphe avec {len(relations_list)} relations")

        # ✅ ÉTAPE 1: Collecter TOUS les nœuds (sans filtrage excessif)
        for rel in relations_list:
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()

            # ✅ CORRECTION : Accepter toutes relations valides (même import, call, use)
            if not source or not target:
                continue
            
            # ✅ Permettre auto-références pour certains types (import self)
            rel_type = rel.get('relation_type', 'unknown').lower()
            if source == target and rel_type not in ['import', 'self_reference']:
                continue
            
            def safe_basename(path):
                """Garde le basename AVEC extension"""
                if not path:
                    return ''
                # Si c'est un chemin, garder seulement le nom de fichier complet
                if '/' in path or '\\' in path:
                    return os.path.basename(path)
                return path
        
            source = safe_basename(source)
            target = safe_basename(target)

            # ✅ Ajouter source avec type par défaut 'file'
            if source not in nodes_registry:
                nodes_registry[source] = {
                    'node_type': rel.get('source_type', 'file'),  # ✅ Défaut: file
                    'uid': rel.get('source_uid', '')
                }

            # ✅ Ajouter target avec type par défaut 'file'
            if target not in nodes_registry:
                nodes_registry[target] = {
                    'node_type': rel.get('target_type', 'file'),  # ✅ Défaut: file
                    'uid': rel.get('target_uid', '')
                }

        logger.info(f"📊 Nœuds collectés: {len(nodes_registry)}")

        # ÉTAPE 2: Ajouter tous les nœuds au graphe
        for node_name, metadata in nodes_registry.items():
            G.add_node(
                node_name,
                node_type=metadata['node_type'],
                uid=metadata['uid']
            )

        # ✅ ÉTAPE 3: Collecter les arêtes (SANS FILTRAGE)
        valid_edges_count = 0
        for rel in relations_list:
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()
            rel_type = rel.get('relation_type', 'unknown')
            category = rel.get('category', 'external')  # ✅ Défaut: external

            if not source or not target:
                continue

            # ✅ Normalisation
            source = os.path.basename(source) if '/' in source or '\\' in source else source
            target = os.path.basename(target) if '/' in target or '\\' in target else target

            # ✅ Vérification existence (devrait toujours passer maintenant)
            if source not in G.nodes or target not in G.nodes:
                logger.error(f"❌ CRITIQUE: Nœuds manquants: {source} -> {target}")
                continue
            
            edge_key = (source, target)
            if edge_key not in edges_registry:
                edges_registry[edge_key] = []

            # ✅ Label clair avec catégorie
            type_label = f"{rel_type} [{category}]"
            if type_label not in edges_registry[edge_key]:
                edges_registry[edge_key].append(type_label)
                valid_edges_count += 1

        logger.info(f"🔗 Arêtes valides collectées: {valid_edges_count}")

        # ÉTAPE 4: Ajouter toutes les arêtes au graphe
        edges_added = 0
        for (source, target), rel_types in edges_registry.items():
            primary_type = rel_types[0]
            combined_label = f"{primary_type} (+{len(rel_types)-1})" if len(rel_types) > 1 else primary_type

            G.add_edge(
                source, target,
                color=self._get_color_for_type(primary_type.split('[')[0].strip()),
                relation_type=primary_type.split('[')[0].strip(),
                all_types=rel_types,
                label=combined_label,
                category=rel_types[0].split('[')[1].strip(']') if '[' in rel_types[0] else 'external'
            )
            edges_added += 1

        logger.info(f"✅ Arêtes ajoutées au graphe: {edges_added}")

        # ÉTAPE 5: Diagnostic final
        final_nodes = len(G.nodes())
        final_edges = len(G.edges())

        logger.info(f"📈 Graphe final: {final_nodes} nœuds, {final_edges} arêtes")

        # ✅ NE PAS supprimer les nœuds isolés (peuvent être pertinents)
        isolated_nodes = list(nx.isolates(G))
        if isolated_nodes:
            logger.info(f"ℹ️  {len(isolated_nodes)} nœuds isolés (conservés)")

        return G
    
    def clear_graph_action(self):
        """✅ NOUVEAU : Vide complètement le graphe et réinitialise l'état"""
        logger.info("🧹 Nettoyage complet du graphe")

        # Réinitialiser toutes les variables d'état
        self.current_graph = None
        self.current_relations = []
        self.current_project_data = None
        self.central_node = None
        self.current_central_uid = None
        self.current_central_name = None
        self.selected_node = None
        self.related_items = []
        self.persistent_selected_items = []
        self.hierarchy_levels = {}
        self.relation_categories = {}

        # Vider les caches
        self.query_cache.clear()
        self.uid_to_name_cache = {}
        self.name_to_uid_cache = {}
        self.uid_metadata_cache = {}

        # Réinitialiser l'affichage
        self._clear_graph()

        # Vider la légende
        while self.legend_layout.count() > 0:
            child = self.legend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        logger.info("✅ Graphe vidé et réinitialisé")
    
    def _diagnose_hierarchy_relations(self, relations_list: List[Dict]) -> Dict:
        """Diagnostic spécifique pour les relations hiérarchiques."""
        logger.info(f"\n{'='*50}")
        logger.info(f"🔬 DIAGNOSTIC RELATIONS HIÉRARCHIQUES")
        logger.info(f"{'='*50}")

        diagnostic = {
            'total_relations': len(relations_list),
            'valid_relations': 0,
            'invalid_relations': 0,
            'node_pairs': set(),
            'relation_types': {},
            'categories': {},
            'missing_sources': [],
            'missing_targets': [],
            'self_references': [],
            'issues': []
        }

        for i, rel in enumerate(relations_list):
            source = rel.get('source')
            target = rel.get('target')
            rel_type = rel.get('relation_type', 'unknown')
            category = rel.get('category', 'unknown')

            # Compteurs par type et catégorie
            diagnostic['relation_types'][rel_type] = diagnostic['relation_types'].get(rel_type, 0) + 1
            diagnostic['categories'][category] = diagnostic['categories'].get(category, 0) + 1

            # Validation de base
            if not source:
                diagnostic['missing_sources'].append(f"Relation {i}")
                diagnostic['invalid_relations'] += 1
                continue

            if not target:
                diagnostic['missing_targets'].append(f"Relation {i}")
                diagnostic['invalid_relations'] += 1
                continue

            if source == target:
                diagnostic['self_references'].append(f"{source} -> {target}")
                diagnostic['invalid_relations'] += 1
                continue
            
            # Normaliser les noms
            norm_source = self.normalize_node_name(source)
            norm_target = self.normalize_node_name(target)

            if norm_source and norm_target and norm_source != norm_target:
                diagnostic['node_pairs'].add((norm_source, norm_target))
                diagnostic['valid_relations'] += 1
            else:
                diagnostic['invalid_relations'] += 1
                diagnostic['issues'].append(f"Normalisation échouée: '{source}' -> '{target}'")

        # Analyse des problèmes
        if diagnostic['invalid_relations'] > diagnostic['valid_relations']:
            diagnostic['issues'].append("Plus de relations invalides que valides")

        if not diagnostic['node_pairs']:
            diagnostic['issues'].append("Aucune paire de nœuds valide trouvée")

        if len(diagnostic['missing_sources']) > 0:
            diagnostic['issues'].append(f"{len(diagnostic['missing_sources'])} relations sans source")

        if len(diagnostic['missing_targets']) > 0:
            diagnostic['issues'].append(f"{len(diagnostic['missing_targets'])} relations sans target")

        # Rapport final
        logger.info(f"📊 Relations totales: {diagnostic['total_relations']}")
        logger.info(f"✅ Relations valides: {diagnostic['valid_relations']}")
        logger.info(f"❌ Relations invalides: {diagnostic['invalid_relations']}")
        logger.info(f"🔗 Paires de nœuds uniques: {len(diagnostic['node_pairs'])}")

        if diagnostic['relation_types']:
            logger.info(f"\n📈 Types de relations:")
            for rel_type, count in sorted(diagnostic['relation_types'].items(), key=lambda x: -x[1]):
                logger.info(f"  • {rel_type}: {count}")

        if diagnostic['categories']:
            logger.info(f"\n📂 Catégories:")
            for category, count in sorted(diagnostic['categories'].items(), key=lambda x: -x[1]):
                logger.info(f"  • {category}: {count}")

        if diagnostic['issues']:
            logger.warning(f"\n⚠️ Problèmes identifiés:")
            for issue in diagnostic['issues']:
                logger.warning(f"  • {issue}")

        logger.info(f"{'='*50}\n")
        return diagnostic

    # ✅ VERSION CORRIGÉE de _get_color_for_type() - Ligne ~1230-1320

    def _get_color_for_type(self, rel_type: str) -> str:
        """✅ MODIFIÉ : Palette de couleurs avec diagnostic"""
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()

        # ===== RELATIONS INTRA-FICHIER (Violets) =====
        call_colors = {
            'call': '#9C27B0',
            'calls': '#AB47BC',
            'method_call': '#BA68C8',
            'function_call': '#CE93D8',
            'called_by': '#E1BEE7',
        }

        # ===== ORBITE 1 : RELATIONS HIÉRARCHIQUES (Bleus) =====
        hierarchical_colors = {
            'parent': '#2196F3',
            'child': '#4CAF50',
            'contains': '#1976D2',
            'belongs_to': '#64B5F6',
            'hierarchy': '#42A5F5',
        }

        # ===== ORBITE 2 : RELATIONS DE CODE (Verts/Cyans) =====
        code_colors = {
            'function_call': '#00ACC1',
            'method_call': '#00BCD4',
            'call': '#26C6DA',
            'called_by': '#4DD0E1',
            'uses': '#66BB6A',
            'used_by': '#81C784',
            'implements': '#43A047',
            'extends': '#00A65A',
            'heritage': '#388E3C',
            'inherit': '#4CAF50',
        }

        # ===== ORBITE 3 : RELATIONS EXTERNES (Oranges/Rouges) =====
        external_colors = {
            'import': '#FF8C00',
            'from_import': '#FFA726',
            'require': '#FFB74D',
            'include': '#FF9800',
            'dependency': '#F57C00',
        }

        # ===== RELATIONS SPÉCIALES (Violets/Roses) =====
        special_colors = {
            'relation': '#8A2BE2',
            'relation_inverse': '#9370DB',
            'custom': '#BA68C8',
        }

        # ===== RECHERCHE DANS LES DICTIONNAIRES =====
        # ✅ CORRECTION ICI - Remplacer intra_file_colors par call_colors
        for key, color in call_colors.items():
            if key in rel_lower:
                return color

        for key, color in hierarchical_colors.items():
            if key in rel_lower:
                return color

        for key, color in code_colors.items():
            if key in rel_lower:
                return color

        for key, color in external_colors.items():
            if key in rel_lower:
                return color

        for key, color in special_colors.items():
            if key in rel_lower:
                return color

        # ===== COULEUR PAR DÉFAUT + DIAGNOSTIC =====
        logger.debug(f"⚠️ Type de relation non reconnu: '{rel_type}' → couleur par défaut (gris)")
        return '#999999'

    def _get_node_color_from_relations(self, G, node, center_node):
        # Récupérer l'orbite du nœud
        node_orbits = {}
        if hasattr(self, 'graph_data') and self.graph_data is not None:
            node_orbits = self.graph_data.get('node_orbits', {})

        orbit = node_orbits.get(node, 3)  # Par défaut orbite 3

        # Retourner la couleur selon l'orbite
        return self._get_orbit_color(orbit)

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.figure = Figure(facecolor='white', figsize=(8, 6))
        self.figure.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self._on_graph_click)
        self.canvas.mpl_connect('motion_notify_event', self._on_graph_motion)
        self.canvas.mpl_connect('button_release_event', self._on_graph_release)
        layout.addWidget(self.canvas)

    def _update_info_label(self):
        """✅ NOUVEAU : Met à jour le label d'information"""
        if not self.current_graph or len(self.current_graph.nodes()) == 0:
            self.info_label.setText("Aucun graphe")
            self.info_label.setStyleSheet("color: #999; font-size: 10px; font-style: italic;")
            self.stats_label.setText("")
            return

        num_nodes = len(self.current_graph.nodes())
        num_edges = len(self.current_graph.edges())

        if self.central_node:
            self.info_label.setText(f"📍 {self.central_node}")
            self.info_label.setStyleSheet("color: #A23B2D; font-size: 10px; font-weight: bold;")
        elif len(self.persistent_selected_items) > 1:
            self.info_label.setText(f"🎯 {len(self.persistent_selected_items)} éléments")
            self.info_label.setStyleSheet("color: #2196F3; font-size: 10px; font-weight: bold;")
        else:
            self.info_label.setText("Graphe chargé")
            self.info_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")

        self.stats_label.setText(f"📊 {num_nodes} nœuds, {num_edges} relations")

    def _get_complete_relations(self, uid: str, level: int = 1, use_cache: bool = True) -> List[Dict]:
        if use_cache:
            cache_key = f"complete_relations_{uid}_{level}"
            cached_data = self.query_cache.get(cache_key)
            if cached_data:
                logger.info(f"📦 Relations depuis cache: {len(cached_data)}")
                return cached_data

            all_relations = []
            processed_uids = set()

            # ✅ ÉTAPE 1 : Relations du nœud central
            central_relations = self._get_node_all_relations(uid)
            all_relations.extend(central_relations)
            processed_uids.add(uid)

            # ✅ ÉTAPE 2 : Si niveau 2, explorer les nœuds connectés
            if level == 2:
                connected_uids = set()

                for rel in central_relations:
                    source_uid = rel.get('source_uid')
                    target_uid = rel.get('target_uid')

                    if source_uid and source_uid != uid and source_uid not in processed_uids:
                        connected_uids.add(source_uid)

                    if target_uid and target_uid != uid and target_uid not in processed_uids:
                        connected_uids.add(target_uid)

                logger.info(f"\n📊 ÉTAPE 2: {len(connected_uids)} nœuds connectés à explorer")

                # ✅ CORRECTION : Ajouter cette boucle qui manquait
                if connected_uids:
                    self._get_nodes_details_batch(list(connected_uids))

                for idx, connected_uid in enumerate(connected_uids, 1):
                    if connected_uid not in processed_uids:
                        logger.debug(f"  [{idx}/{len(connected_uids)}] UID: {connected_uid}")

                        # ✅ LIGNE CRITIQUE QUI MANQUAIT
                        connected_relations = self._get_node_all_relations(connected_uid)
                        all_relations.extend(connected_relations)
                        processed_uids.add(connected_uid)

            # ✅ ÉTAPE 3 : Déduplication
            unique_relations = []
            seen_keys = set()

            for rel in all_relations:
                if 'relation_type' not in rel and 'relationType' in rel:
                    rel['relation_type'] = rel['relationType']

                key = (
                    rel.get('source_uid', ''),
                    rel.get('target_uid', ''),
                    rel.get('relation_type', '')
                )

                if key not in seen_keys and key[0] and key[1]:
                    seen_keys.add(key)
                    unique_relations.append(rel)

            # ✅ ÉTAPE 4 : Mise en cache
            if use_cache:
                cache_key = f"complete_relations_{uid}_{level}"
                self.query_cache.set(cache_key, unique_relations)

        return unique_relations
    
    def _get_node_all_relations(self, uid: str) -> List[Dict]:
        if not uid or not self.dgraph_connector:
            logger.warning("⚠️ Pas d'UID ou pas de connecteur Dgraph")
            return []
    
        all_relations = []
    
        # ✅ ÉTAPE 1: Vérifier le type de nœud AVANT la requête principale
        type_query = f"""
        {{
          check(func: uid({uid})) {{
            uid
            name
            nodeType
            dgraph.type
          }}
        }}
        """
    
        type_result = self._execute_dgraph_query(type_query)
    
        if not type_result or 'check' not in type_result or not type_result['check']:
            logger.warning(f"⚠️ Nœud {uid} introuvable")
            return []
    
        node_info = type_result['check'][0]
        node_type = node_info.get('nodeType', '')
        dgraph_types = node_info.get('dgraph.type', [])
    
        is_function = (
            node_type in ['function', 'method'] or
            'Function' in dgraph_types or
            'Method' in dgraph_types
        )
    
        logger.info(f"🔍 Type détecté: {node_type} (is_function={is_function})")
    
        # ✅ REQUÊTE ADAPTÉE selon le type
        if is_function:
            # 🎯 REQUÊTE SPÉCIALE POUR FONCTIONS/MÉTHODES
            query = f"""
            {{
              node(func: uid({uid})) {{
                uid
                name
                label
                path
                nodeType
    
                # ✅ PARENT FICHIER (si fonction globale)
                ~functions {{
                  uid
                  name
                  label
                  nodeType
                  path
                }}
    
                # ✅ PARENT CLASSE (si méthode)
                ~methods {{
                  uid
                  name
                  label
                  nodeType
                  description
    
                  # ✅ FICHIER DE LA CLASSE
                  ~classes {{
                    uid
                    name
                    label
                    nodeType
                    path
                  }}
                }}
    
                # Relations de code direct
                imports {{ uid name label nodeType }}
                ~imports {{ uid name label nodeType }}
                calls {{ uid name label nodeType }}
                ~calls {{ uid name label nodeType }}
                uses {{ uid name label nodeType }}
                ~uses {{ uid name label nodeType }}
              }}
            }}
            """
        else:
            # 📄 REQUÊTE STANDARD POUR FICHIERS/CLASSES
            query = f"""
            {{
              node(func: uid({uid})) {{
                uid
                name
                label
                path
                nodeType
    
                # Relations hiérarchiques
                parents {{ uid name label nodeType }}
                children: ~parents {{ uid name label nodeType }}
                classes {{ uid name label nodeType }}
                functions {{ uid name label nodeType }}
                variables {{ uid name label nodeType }}
                methods {{ uid name label nodeType }}
    
                # Relations de code direct
                imports {{ uid name label nodeType }}
                ~imports {{ uid name label nodeType }}
                calls {{ uid name label nodeType }}
                ~calls {{ uid name label nodeType }}
                uses {{ uid name label nodeType }}
                ~uses {{ uid name label nodeType }}
                extends {{ uid name label nodeType }}
                ~extends {{ uid name label nodeType }}
                implements {{ uid name label nodeType }}
                ~implements {{ uid name label nodeType }}
              }}
            }}
            """
    
        result = self._execute_dgraph_query(query)
    
        if not result or 'node' not in result or not result['node']:
            logger.warning(f"⚠️ Nœud {uid} introuvable")
            return []
    
        node = result['node'][0]
        central_uid = node.get('uid')
        central_name = self.normalize_node_name(
            node.get('name') or 
            node.get('label') or 
            node.get('path') or 
            f"Node_{uid[-8:]}"
        )
        central_type = node.get('nodeType', 'unknown')
    
        # ✅ TRAITEMENT SPÉCIAL POUR FONCTIONS
        if is_function:
            # 1️⃣ PARENT FICHIER (si fonction globale)
            parent_files = node.get('~functions', [])
    
            for parent_file in parent_files:
                parent_uid = parent_file.get('uid')
                if not parent_uid:
                    continue
                
                parent_name = self.normalize_node_name(
                    parent_file.get('name') or 
                    parent_file.get('label') or 
                    f"File_{parent_uid[-8:]}"
                )
                parent_type = parent_file.get('nodeType', 'file')
    
                if not parent_name or parent_name == central_name:
                    continue
                
                all_relations.append({
                    'source': parent_name,
                    'source_uid': parent_uid,
                    'source_type': parent_type,
                    'target': central_name,
                    'target_uid': central_uid,
                    'target_type': central_type,
                    'relation_type': 'contains_function',
                    'category': 'hierarchy'
                })
    
                logger.info(f"   📄 Parent fichier: {parent_name}")
    
            # 2️⃣ PARENT CLASSE (si méthode)
            parent_classes = node.get('~methods', [])
    
            for parent_class in parent_classes:
                class_uid = parent_class.get('uid')
                if not class_uid:
                    continue
                
                class_name = self.normalize_node_name(
                    parent_class.get('name') or 
                    parent_class.get('label') or 
                    f"Class_{class_uid[-8:]}"
                )
                class_type = parent_class.get('nodeType', 'class')
    
                if not class_name or class_name == central_name:
                    continue
                
                # Relation: Classe → Méthode
                all_relations.append({
                    'source': class_name,
                    'source_uid': class_uid,
                    'source_type': class_type,
                    'target': central_name,
                    'target_uid': central_uid,
                    'target_type': central_type,
                    'relation_type': 'has_method',
                    'category': 'hierarchy'
                })
    
                logger.info(f"   🗂️ Parent classe: {class_name}")
    
                # 3️⃣ FICHIER DE LA CLASSE
                class_files = parent_class.get('~classes', [])
    
                for class_file in class_files:
                    file_uid = class_file.get('uid')
                    if not file_uid:
                        continue
                    
                    file_name = self.normalize_node_name(
                        class_file.get('name') or 
                        class_file.get('label') or 
                        f"File_{file_uid[-8:]}"
                    )
                    file_type = class_file.get('nodeType', 'file')
    
                    if not file_name:
                        continue
                    
                    # Relation: Fichier → Classe
                    all_relations.append({
                        'source': file_name,
                        'source_uid': file_uid,
                        'source_type': file_type,
                        'target': class_name,
                        'target_uid': class_uid,
                        'target_type': class_type,
                        'relation_type': 'contains_class',
                        'category': 'hierarchy'
                    })
    
                    logger.info(f"   📄 Fichier de la classe: {file_name}")
    
        else:
            # 📦 TRAITEMENT STANDARD pour fichiers/classes
            hierarchical_predicates = {
                'parents': ('parent', True),
                'children': ('child', False),
                'classes': ('contains_class', False),
                'functions': ('contains_function', False),
                'variables': ('contains_variable', False),
                'methods': ('has_method', False)
            }
    
            for predicate, (rel_type, is_incoming) in hierarchical_predicates.items():
                related_nodes = node.get(predicate, [])
    
                for related_node in related_nodes:
                    if not isinstance(related_node, dict):
                        continue
                    
                    related_uid = related_node.get('uid')
                    if not related_uid:
                        continue
                    
                    related_name = self.normalize_node_name(
                        related_node.get('name') or 
                        related_node.get('label') or 
                        f"Node_{related_uid[-8:]}"
                    )
                    related_type = related_node.get('nodeType', 'unknown')
    
                    if not central_name or not related_name or central_name == related_name:
                        continue
                    
                    if is_incoming:
                        relation = {
                            'source': related_name,
                            'source_uid': related_uid,
                            'source_type': related_type,
                            'target': central_name,
                            'target_uid': central_uid,
                            'target_type': central_type,
                            'relation_type': rel_type,
                            'category': 'hierarchy'
                        }
                    else:
                        relation = {
                            'source': central_name,
                            'source_uid': central_uid,
                            'source_type': central_type,
                            'target': related_name,
                            'target_uid': related_uid,
                            'target_type': related_type,
                            'relation_type': rel_type,
                            'category': 'hierarchy'
                        }
    
                    if (relation['source'] and relation['target'] and 
                        relation['source'] != relation['target']):
                        all_relations.append(relation)
    
        # ✅ TRAITER RELATIONS DE CODE (commun pour tous les types)
        code_predicates = {
            'imports': ('import', False),
            '~imports': ('imported_by', True),
            'calls': ('call', False),
            '~calls': ('called_by', True),
            'uses': ('use', False),
            '~uses': ('used_by', True),
            'extends': ('extends', False),
            '~extends': ('extended_by', True),
            'implements': ('implements', False),
            '~implements': ('implemented_by', True)
        }
    
        for predicate, (rel_type, is_incoming) in code_predicates.items():
            related_nodes = node.get(predicate, [])
    
            for related_node in related_nodes:
                if not isinstance(related_node, dict):
                    continue
                
                related_uid = related_node.get('uid')
                if not related_uid:
                    continue
                
                related_name = self.normalize_node_name(
                    related_node.get('name') or 
                    related_node.get('label') or 
                    f"Node_{related_uid[-8:]}"
                )
                related_type = related_node.get('nodeType', 'unknown')
    
                if not central_name or not related_name or central_name == related_name:
                    continue
                
                if is_incoming:
                    relation = {
                        'source': related_name,
                        'source_uid': related_uid,
                        'source_type': related_type,
                        'target': central_name,
                        'target_uid': central_uid,
                        'target_type': central_type,
                        'relation_type': rel_type,
                        'category': 'code'
                    }
                else:
                    relation = {
                        'source': central_name,
                        'source_uid': central_uid,
                        'source_type': central_type,
                        'target': related_name,
                        'target_uid': related_uid,
                        'target_type': related_type,
                        'relation_type': rel_type,
                        'category': 'code'
                    }
    
                if (relation['source'] and relation['target'] and 
                    relation['source'] != relation['target']):
                    all_relations.append(relation)
    
        # ✅ ÉTAPE 2: Relations via type Relation (commun pour tous)
        try:
            relation_type_relations = self._get_relation_type_relations_cached(uid)
    
            existing_keys = set()
            for rel in all_relations:
                key = (
                    rel.get('source_uid') or rel.get('source'),
                    rel.get('target_uid') or rel.get('target'),
                    rel.get('relation_type')
                )
                existing_keys.add(key)
    
            added_count = 0
            for rel in relation_type_relations:
                key = (
                    rel.get('source_uid') or rel.get('source'),
                    rel.get('target_uid') or rel.get('target'),
                    rel.get('relation_type')
                )
    
                if key not in existing_keys:
                    all_relations.append(rel)
                    existing_keys.add(key)
                    added_count += 1
    
            logger.info(f"  🔗 Relations type Relation: {len(relation_type_relations)} récupérées, {added_count} ajoutées")
    
        except Exception as e:
            logger.error(f"❌ Erreur récupération relations type Relation: {e}")
    
        # ✅ ÉTAPE 3: Statistiques
        self._log_relation_stats(all_relations)
    
        logger.info(f"✅ Total: {len(all_relations)} relations pour {uid}")
        return all_relations
        
    def _get_nodes_details_batch(self, uids: List[str]) -> Dict[str, Dict]:
        """✅ Récupère plusieurs nœuds en UNE SEULE requête"""

        if not uids:
            return {}

        # Vérifier cache d'abord
        cached_details = {}
        missing_uids = []

        for uid in uids:
            cache_key = f"node_details_{uid}"
            cached_data = self.query_cache.get(cache_key)
            if cached_data:
                cached_details[uid] = cached_data
            else:
                missing_uids.append(uid)

        if not missing_uids:
            logger.info(f"✅ Tous les nœuds en cache ({len(uids)})")
            return cached_details

        logger.info(f"📡 Batch: {len(missing_uids)} nœuds à récupérer")

        # Requête batch
        uid_list = ", ".join(missing_uids)
        query = f"""
        {{
          nodes(func: uid({uid_list})) {{
            uid
            name
            path
            label
            nodeType
            level
            parents {{ uid name }}
            children: ~parents {{ uid name }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'nodes' in result:
            for node in result['nodes']:
                node_uid = node.get('uid')
                if node_uid:
                    cache_key = f"node_details_{node_uid}"
                    self.query_cache.set(cache_key, node)
                    cached_details[node_uid] = node

        logger.info(f"✅ Batch récupéré: {len(cached_details)} nœuds")
        return cached_details
    
    def _diagnose_relation_issues(self, uid: str) -> Dict:
        """
        ✅ DIAGNOSTIC PUBLIC : Peut être appelé par taxonomy_dialog
        """
        if not uid or not self.dgraph_connector:
            return {'error': 'UID ou connecteur manquant'}

        logger.info(f"🔬 DIAGNOSTIC RELATIONS pour UID: {uid}")

        diagnostic = {
            'uid': uid,
            'node_exists': False,
            'node_details': {},
            'relation_counts': {},
            'relation_type_counts': {},
            'issues': []
        }

        # Vérifier existence du nœud
        check_query = f"""
        {{
          check(func: uid({uid})) {{
            uid
            name
            nodeType
            dgraph.type
          }}
        }}
        """

        result = self._execute_dgraph_query(check_query)

        if not result or 'check' not in result or not result['check']:
            diagnostic['issues'].append(f"Nœud {uid} n'existe pas dans Dgraph")
            return diagnostic

        node = result['check'][0]
        diagnostic['node_exists'] = True
        diagnostic['node_details'] = node

        # Compter les relations par prédicat
        count_query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            parents {{ uid }}
            children: ~parents {{ uid }}
            classes {{ uid }}
            functions {{ uid }}
            variables {{ uid }}
            imports {{ uid }}
            ~imports {{ uid }}
            calls {{ uid }}
            ~calls {{ uid }}
            uses {{ uid }}
            ~uses {{ uid }}
          }}

          outgoing_relations(func: type(Relation)) @filter(uid_in(source, {uid})) {{
            uid
            relationType
          }}

          incoming_relations(func: type(Relation)) @filter(uid_in(target, {uid})) {{
            uid
            relationType
          }}
        }}
        """

        result = self._execute_dgraph_query(count_query)

        if result:
            node_data = result.get('node', [{}])[0]

            # Compter relations hiérarchiques
            for predicate in ['parents', 'children', 'classes', 'functions', 'variables']:
                count = len(node_data.get(predicate, []))
                if count > 0:
                    diagnostic['relation_counts'][predicate] = count

            # Compter relations de code
            for predicate in ['imports', '~imports', 'calls', '~calls', 'uses', '~uses']:
                count = len(node_data.get(predicate, []))
                if count > 0:
                    diagnostic['relation_counts'][predicate] = count

            # Compter relations de type Relation
            outgoing_rels = result.get('outgoing_relations', [])
            incoming_rels = result.get('incoming_relations', [])

            if outgoing_rels:
                diagnostic['relation_counts']['outgoing_relation_type'] = len(outgoing_rels)
                for rel in outgoing_rels:
                    rel_type = rel.get('relationType', 'unknown')
                    diagnostic['relation_type_counts'][rel_type] = diagnostic['relation_type_counts'].get(rel_type, 0) + 1

            if incoming_rels:
                diagnostic['relation_counts']['incoming_relation_type'] = len(incoming_rels)
                for rel in incoming_rels:
                    rel_type = rel.get('relationType', 'unknown')
                    diagnostic['relation_type_counts'][f"~{rel_type}"] = diagnostic['relation_type_counts'].get(f"~{rel_type}", 0) + 1

        # Analyser les problèmes
        total_relations = sum(diagnostic['relation_counts'].values())

        if total_relations == 0:
            diagnostic['issues'].append("Aucune relation trouvée - nœud isolé")
        elif total_relations < 3:
            diagnostic['issues'].append(f"Peu de relations ({total_relations}) - possible nœud périphérique")

        if not diagnostic['relation_counts'].get('outgoing_relation_type') and not diagnostic['relation_counts'].get('incoming_relation_type'):
            diagnostic['issues'].append("Aucune relation de type 'Relation' - uniquement relations hiérarchiques/directes")

        logger.info(f"🔬 Diagnostic terminé: {len(diagnostic['issues'])} problème(s) identifié(s)")
        return diagnostic

    def _get_relation_type_relations(self, uid: str) -> List[Dict]:
        """✅ VERSION CORRIGÉE : Récupère TOUTES les relations de type Relation"""

        if not uid or not self.dgraph_connector:
            logger.error("❌ Pas d'UID ou pas de connecteur")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 RÉCUPÉRATION RELATIONS TYPE RELATION (AMÉLIORÉE)")
        logger.info(f"  UID central: {uid}")
        logger.info(f"{'='*70}")

        # ✅ ÉTAPE 1 : Récupérer les informations du nœud
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

        # ✅ CORRECTION : Essayer TOUS les champs possibles + FALLBACK
        node_name = (
            node_data.get('name') or 
            node_data.get('label') or 
            node_data.get('id') or 
            ''
        )
        node_path = node_data.get('path', '')

        # ✅ FALLBACK CRITIQUE : Si toujours vide, utiliser UID uniquement
        if not node_name and not node_path:
            logger.warning(f"⚠️ Nœud {uid} sans nom/path, recherche par UID uniquement")
            # Appeler une méthode de fallback qui cherche UNIQUEMENT par UID
            return self._get_relations_by_uid_only(uid)

        # 2. Construire variantes de recherche
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
            # ✅ CORRECTION : Ne devrait jamais arriver grâce au fallback ci-dessus
            logger.error("❌ Aucun identifiant valide (cas impossible après fallback)")
            return []

        # ✅ ÉTAPE 3 : Requête TRIPLE MODE
        # Mode 1 : Par UID direct
        # Mode 2 : Par sourceName/targetName exact
        # Mode 3 : Par sourcePath/targetPath exact

        relations_by_uid = []
        relations_by_name = []

        # 🔍 MODE 1 : Recherche par UID
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

        # 🔍 MODE 2 : Recherche par nom/path
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

        # ✅ ÉTAPE 4 : Fusionner et dédupliquer
        all_raw_relations = relations_by_uid + relations_by_name

        seen_uids = set()
        unique_raw_relations = []

        for rel in all_raw_relations:
            rel_uid = rel.get('uid')
            if rel_uid and rel_uid not in seen_uids:
                seen_uids.add(rel_uid)
                unique_raw_relations.append(rel)

        logger.info(f"📦 {len(unique_raw_relations)} relations uniques après déduplication")

        # ✅ ÉTAPE 5 : Validation et normalisation
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
    
    def _get_relations_by_uid_only(self, uid: str) -> List[Dict]:
        """
        ✅ FALLBACK CRITIQUE : Récupère relations UNIQUEMENT par UID
        Utilisé quand name/path sont vides
        """
        if not uid or not self.dgraph_connector:
            return []
        
        logger.info(f"🔍 FALLBACK : Recherche par UID uniquement pour {uid}")
        
        # Requête UNIQUEMENT par UID dans les relations
        query = f"""
        {{
          relations_out(func: type(Relation)) @filter(uid_in(source, {uid})) {{
            uid
            relationType
            category
            line
            sourceName
            sourceType
            targetName
            targetType
            target {{ uid name path label }}
          }}
    
          relations_in(func: type(Relation)) @filter(uid_in(target, {uid})) {{
            uid
            relationType
            category
            line
            sourceName
            sourceType
            targetName
            targetType
            source {{ uid name path label }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if not result:
            logger.warning(f"⚠️ Aucune relation trouvée pour UID {uid}")
            return []
        
        all_relations = result.get('relations_out', []) + result.get('relations_in', [])
        
        logger.info(f"📦 {len(all_relations)} relations trouvées via UID")
        
        relations_list = []
        seen_keys = set()
        
        for rel in all_relations:
            # Extraire les noms depuis les relations elles-mêmes
            source_name = rel.get('sourceName', '')
            target_name = rel.get('targetName', '')
            
            # ✅ CORRECTION : Fallback sur les nœuds liés
            if not source_name and 'source' in rel:
                source_node = rel['source']
                source_name = (
                    source_node.get('name') or 
                    source_node.get('label') or 
                    source_node.get('path') or 
                    f"Node_{source_node.get('uid', 'unknown')[-8:]}"
                )
            
            if not target_name and 'target' in rel:
                target_node = rel['target']
                target_name = (
                    target_node.get('name') or 
                    target_node.get('label') or 
                    target_node.get('path') or 
                    f"Node_{target_node.get('uid', 'unknown')[-8:]}"
                )
            
            if not source_name or not target_name:
                continue
            
            # Normaliser
            source_name_norm = os.path.basename(source_name).strip()
            target_name_norm = os.path.basename(target_name).strip()
            
            if not source_name_norm or not target_name_norm:
                continue
            
            # Ignorer auto-références
            if source_name_norm == target_name_norm:
                continue
            
            relation_type = rel.get('relationType', 'relation')
            unique_key = (source_name_norm, target_name_norm, relation_type)
            
            if unique_key in seen_keys:
                continue
            
            seen_keys.add(unique_key)
            
            relations_list.append({
                'source': source_name_norm,
                'source_uid': uid if rel in result.get('relations_out', []) else rel.get('source', {}).get('uid'),
                'source_type': rel.get('sourceType', 'file'),
                'target': target_name_norm,
                'target_uid': rel.get('target', {}).get('uid') if rel in result.get('relations_out', []) else uid,
                'target_type': rel.get('targetType', 'file'),
                'relation_type': relation_type,
                'category': rel.get('category', 'external'),
                'line': rel.get('line')
            })
        
        logger.info(f"✅ FALLBACK : {len(relations_list)} relations validées")
        return relations_list

    def _get_relation_type_relations_cached(self, uid: str) -> List[Dict]:
        cache_key = f"relations_unified_{uid}"
        cached_data = self.query_cache.get(cache_key)

        if cached_data:
            logger.debug(f"✅ Relations type Relation depuis cache: {len(cached_data)}")
            return cached_data

        relations = self._get_relation_type_relations(uid)

        if relations:
            self.query_cache.set(cache_key, relations)

        return relations

    def _draw_graph(self):
        """Dessine le graphe avec le style unifié (utilise self.current_graph)"""

        if not self.current_graph:
            logger.warning("⚠️ Aucun graphe à dessiner")
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, "Aucune relation à afficher", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        # ✅ Maintenant on peut définir G
        G = self.current_graph
        self._diagnose_graph_metadata(G)

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        num_nodes = len(G.nodes())

        # ✅ CAS LIMITES
        if num_nodes == 0:
            ax.text(0.5, 0.5, "Aucune relation à afficher", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic')
            ax.axis('off')
            self.canvas.draw()
            return

        # ✅ LAYOUT AVEC ORBITES
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
                    # Fallback
                    pos = nx.spring_layout(G, k=2.0, iterations=300, seed=42, scale=3.0)
            else:
                pos = {}

        # ✅ COLLISION AVOIDANCE
        pos = self._apply_universal_collision_avoidance(G, pos, num_nodes)

        logger.info(f"🎨 Layout calculé pour {num_nodes} nœuds avec orbites")

        # ✅ PARAMÈTRES ADAPTATIFS SELON LE NOMBRE DE NŒUDS
        if num_nodes <= 15:
            base_char_width = 0.65  # Augmenté significativement
            text_height = 2.5
            font_size = 11
            padding = 3.0  # Augmenté
        elif num_nodes <= 30:
            base_char_width = 0.60  # Augmenté significativement
            text_height = 2.3
            font_size = 10
            padding = 2.8  # Augmenté
        else:
            base_char_width = 0.55  # Augmenté significativement
            text_height = 2.0
            font_size = 9
            padding = 2.5  # Augmenté

        # ✅ PREMIÈRE PASSE : CALCULER LA LARGEUR MAXIMALE NÉCESSAIRE
        max_required_width = 10.0  # Minimum absolu augmenté
        node_display_names = {}
        max_text_length = 0
        longest_name = ""

        for node in G.nodes():
            node_data = G.nodes[node]
            node_type = node_data.get('node_type', None)

            # Formater le nom COMPLET (sans troncature)
            formatted_name = self._format_node_display_name(node, node_type)
            node_display_names[node] = formatted_name

            text_length = len(formatted_name)

            # ✅ CALCUL GÉNÉREUX de la largeur nécessaire
            # Multiplier par un facteur plus important pour tenir compte des caractères larges
            text_width_estimated = text_length * base_char_width * 1.5  # Facteur augmenté de 1.15 à 1.5
            required_width = text_width_estimated + (padding * 2)

            # Mettre à jour la largeur maximale
            if required_width > max_required_width:
                max_required_width = required_width
                max_text_length = text_length
                longest_name = formatted_name

        # ✅ UTILISER CETTE LARGEUR POUR TOUS LES NŒUDS
        node_width = max_required_width
        node_height = text_height

        logger.info(f"📏 Largeur finale des nœuds : {node_width:.2f}")
        logger.info(f"📝 Nom le plus long : '{longest_name}' ({max_text_length} caractères)")

        node_dimensions = {}
        curvature = 0.12 if num_nodes <= 20 else 0.08
        edge_width = 2.0 if num_nodes <= 20 else 1.5
        edge_alpha = 0.7
        arrow_size = 14 if num_nodes <= 20 else 10

        edges = list(G.edges(data=True))
        edge_colors = [d.get('color', '#CCCCCC') for _, _, d in edges]

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

        # ✅ DEUXIÈME PASSE : DESSINER LES NŒUDS AVEC LA LARGEUR UNIFORME
        for node in G.nodes():
            x, y = pos[node]

            # Récupérer le nom complet (sans troncature)
            display_name = node_display_names[node]

            node_dimensions[node] = (node_width, node_height)

            if node == self.current_central_name:
                color = '#8B2E1F'
                edge_color = '#666666'
                linewidth = 3.0
            else:
                # ✅ Récupérer l'orbite
                orbit = node_orbits.get(node, 3)

                # Collecter les types de relations pour déterminer la catégorie dominante
                node_relation_types = {}
                for u, v, data in G.edges(data=True):
                    if u == node or v == node:
                        rel_type = data.get('relation_type', '').lower()
                        if rel_type:
                            node_relation_types[rel_type] = node_relation_types.get(rel_type, 0) + 1

                # ✅ DÉTERMINER LA CATÉGORIE DOMINANTE
                dominant_category = 'unknown'

                if node_relation_types:
                    # Compter par catégorie
                    hierarchy_count = sum(count for rel, count in node_relation_types.items() 
                                         if rel in ['parent', 'child', 'contains', 'hierarchy',
                                                   'contains_class', 'contains_function', 'contains_variable',
                                                   'has_method', 'has_variable', 'belongs_to'])

                    code_count = sum(count for rel, count in node_relation_types.items() 
                                    if rel in ['import', 'from_import', 'use', 'uses', 'used_by',
                                              'implements', 'extends', 'inherits', 'intra_file'])

                    call_count = sum(count for rel, count in node_relation_types.items() 
                                    if rel in ['call', 'calls', 'method_call', 'function_call', 'called_by'])

                    external_count = sum(count for rel, count in node_relation_types.items() 
                                        if rel in ['require', 'dependency', 'external', 'inter_file', 'include'])

                    # Déterminer la catégorie dominante
                    category_counts = {
                        'hierarchy': hierarchy_count,
                        'code': code_count,
                        'call': call_count,
                        'external': external_count
                    }

                    if any(category_counts.values()):
                        dominant_category = max(category_counts, key=category_counts.get)

                # ✅ APPLIQUER LES COULEURS SELON LA CATÉGORIE
                if dominant_category == 'hierarchy':
                    color = '#2196F3'
                    edge_color = '#1565C0'
                elif dominant_category == 'code':
                    color = '#00ACC1'
                    edge_color = '#00838F'
                elif dominant_category == 'call':
                    color = '#9C27B0'
                    edge_color = '#7B1FA2'
                elif dominant_category == 'external':
                    color = '#FF8C00'
                    edge_color = '#E65100'
                else:
                    color = '#999999'
                    edge_color = '#666666'

                linewidth = 2.5

            # ✅ Dessiner le rectangle avec la largeur uniforme LARGE
            rect = FancyBboxPatch(
                (x - node_width/2, y - node_height/2),
                node_width, node_height,
                boxstyle="round,pad=0.35",  # Padding interne du box
                edgecolor=edge_color,
                facecolor=color,
                alpha=0.95,
                linewidth=linewidth,
                zorder=2
            )
            ax.add_patch(rect)

            # ✅ Texte centré dans le conteneur (AUCUNE TRONCATURE)
            ax.text(
                x, y, display_name,
                ha='center', va='center',
                fontsize=font_size,
                fontweight='bold',
                color='white',
                zorder=3,
                wrap=False
            )

        self._draw_orbit_legend(ax, edges, node_orbits)

        ax.axis('off')

        x_coords = [pos[node][0] for node in G.nodes()]
        y_coords = [pos[node][1] for node in G.nodes()]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # ✅ Utiliser la largeur réelle calculée pour les marges (GÉNÉREUSES)
        margin_x = max(node_width * 0.8, 4.0)  # Encore augmenté
        margin_y = max(node_height * 0.8, 2.5)  # Encore augmenté

        ax.set_xlim(x_min - margin_x, x_max + margin_x)
        ax.set_ylim(y_min - margin_y, y_max + margin_y)

        ax.margins(0)
        ax.set_aspect('equal', adjustable='datalim')

        self.figure.tight_layout(pad=0.1)

        self.graph_data = {
            'pos': {node: list(coord) for node, coord in pos.items()},
            'G': G,
            'ax': ax,
            'edges': edges,
            'edge_colors': edge_colors,
            'num_nodes': num_nodes,
            'node_orbits': node_orbits,
            'text_width': node_width,
            'text_height': node_height,
            'font_size': font_size,
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max,
            'node_dimensions': node_dimensions,
            'padding': padding
        }

        self.canvas.draw()

    def _diagnose_graph_metadata(self, G):
        """🔍 DIAGNOSTIC : Affiche les métadonnées des arêtes"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 DIAGNOSTIC MÉTADONNÉES DU GRAPHE")
        logger.info(f"{'='*70}")
        logger.info(f"Nœuds : {len(G.nodes())}")
        logger.info(f"Arêtes : {len(G.edges())}")

        # Échantillon d'arêtes
        sample_size = min(10, len(G.edges()))
        logger.info(f"\n📊 Échantillon de {sample_size} arêtes :")

        for i, (u, v, data) in enumerate(list(G.edges(data=True))[:sample_size]):
            rel_type = data.get('relation_type', 'MANQUANT')
            category = data.get('category', 'MANQUANT')
            color = data.get('color', 'MANQUANT')
            logger.info(f"  {i+1}. {u} → {v}")
            logger.info(f"     type: {rel_type}, catégorie: {category}, couleur: {color}")

        # Statistiques par type
        type_counts = {}
        category_counts = {}

        for u, v, data in G.edges(data=True):
            rel_type = data.get('relation_type', 'unknown')
            category = data.get('category', 'unknown')
            type_counts[rel_type] = type_counts.get(rel_type, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        logger.info(f"\n📈 Types de relations :")
        for rel_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  • {rel_type}: {count}")

        logger.info(f"\n📂 Catégories :")
        for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  • {category}: {count}")

        logger.info(f"{'='*70}\n")

    def _adjust_selected_nodes_positions(self, pos: Dict, selected_nodes: List[str]):
        if not selected_nodes:
            return

        # Calculer le centre du graphe
        center_x = sum(coord[0] for coord in pos.values()) / len(pos)
        center_y = sum(coord[1] for coord in pos.values()) / len(pos)

        # Rapprocher les nœuds sélectionnés du centre
        for node in selected_nodes:
            if node in pos:
                current_x, current_y = pos[node]
                # Déplacer vers le centre (facteur 0.3)
                new_x = current_x + (center_x - current_x) * 0.3
                new_y = current_y + (center_y - current_y) * 0.3
                pos[node] = [new_x, new_y]

    def _is_connected_to_selected(self, G: nx.DiGraph, node: str, selected_nodes: List[str]) -> bool:
        if node in selected_nodes:
            return True

        # Vérifier connexions sortantes et entrantes
        for selected in selected_nodes:
            if G.has_edge(node, selected) or G.has_edge(selected, node):
                return True

        return False
   

    def _get_relation_category(self, rel_type: str) -> str:
        """✅ CORRIGÉ : Catégories sans 'selection'"""
        if not rel_type:
            return 'external'

        rel_lower = rel_type.lower()

        # Relations hiérarchiques
        hierarchy_types = {
            'parent', 'child', 'contains_class', 'contains_function', 
            'contains_variable', 'has_method', 'has_variable'
        }

        # Relations de code
        code_types = {
            'import', 'call', 'use', 'extends', 'implements', 
            'inherit', 'imported_by', 'called_by', 'used_by'
        }

        for category, types in [
            ('hierarchy', hierarchy_types),
            ('code', code_types)
        ]:
            if any(t in rel_lower for t in types):
                return category

        return 'external'

    def _get_short_relation_name(self, rel_type: str) -> str:
        """✅ NOUVELLE MÉTHODE : Nom court pour affichage dans la légende"""
        short_names = {
            'contains_class': 'classe',
            'contains_function': 'fonction', 
            'contains_variable': 'variable',
            'has_method': 'méthode',
            'has_variable': 'var',
            'selected_together': 'sélection',
            'imported_by': 'importé',
            'called_by': 'appelé',
            'used_by': 'utilisé'
        }

        return short_names.get(rel_type, rel_type[:10])
    
    def clear_persistent_selections(self):
        logger.info("🧹 Nettoyage des sélections persistantes")

        self.persistent_selected_items.clear()
        self.hierarchy_levels.clear()
        self.relation_categories.clear()

        # Réinitialiser le graphe
        self._clear_graph()

        logger.info("✅ Sélections persistantes vidées")

    def get_persistent_selection_count(self) -> int:
        return len(getattr(self, 'persistent_selected_items', []))

    def remove_from_persistent_selection(self, item_uid: str):
        """
        ✅ NOUVELLE MÉTHODE : Retire un élément des sélections persistantes
        """
        if not hasattr(self, 'persistent_selected_items'):
            return

        self.persistent_selected_items = [
            item for item in self.persistent_selected_items 
            if item.get('uid') != item_uid
        ]

        logger.info(f"🗑️ Élément {item_uid} retiré des sélections persistantes")

        # Redessiner le graphe avec les éléments restants
        if self.persistent_selected_items:
            self.update_graph_with_persistent_selections(
                self.persistent_selected_items, 
                self.current_project_data, 
                append_mode=False
            )
        else:
            self._clear_graph()

    def _apply_collision_avoidance(self, G, pos, num_nodes):
        """✅ AMÉLIORÉ : Collision avoidance robuste avec distance minimum garantie."""
        import numpy as np

        # 🎯 Distance minimum adaptative selon la taille du graphe
        if num_nodes <= 10:
            min_distance = 0.5
            iterations = 100
        elif num_nodes <= 20:
            min_distance = 0.4
            iterations = 80
        elif num_nodes <= 50:
            min_distance = 0.3
            iterations = 60
        else:
            min_distance = 0.25
            iterations = 40

        nodes = list(G.nodes())

        # 🔄 Algorithme de répulsion par force
        for iteration in range(iterations):
            moved = False

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]
                force_x, force_y = 0.0, 0.0

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    # Calculer distance et direction
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = np.sqrt(dx**2 + dy**2)

                    # ✅ Si collision détectée
                    if distance < min_distance and distance > 0.001:
                        moved = True

                        # Force de répulsion inversement proportionnelle à la distance
                        overlap = min_distance - distance
                        repulsion_strength = overlap / min_distance

                        # Normaliser la direction
                        dx_norm = dx / distance
                        dy_norm = dy / distance

                        # Appliquer force de répulsion
                        force_magnitude = repulsion_strength * 0.1

                        force_x -= force_magnitude * dx_norm
                        force_y -= force_magnitude * dy_norm

                # Appliquer les forces cumulées
                if abs(force_x) > 0.001 or abs(force_y) > 0.001:
                    pos[node1][0] += force_x
                    pos[node1][1] += force_y

            # 🛑 Arrêt anticipé si plus de mouvement
            if not moved and iteration > 20:
                logger.debug(f"✅ Collision avoidance converged at iteration {iteration}")
                break
            
            # 📉 Réduction progressive de la distance minimum
            if iteration % 15 == 0 and iteration > 0:
                min_distance *= 0.98

        # 🔍 Vérification finale et correction des collisions restantes
        collision_count = 0
        for i, node1 in enumerate(nodes):
            x1, y1 = pos[node1]
            for node2 in nodes[i+1:]:
                x2, y2 = pos[node2]
                dx = x2 - x1
                dy = y2 - y1
                distance = np.sqrt(dx**2 + dy**2)

                if distance < min_distance * 0.9:
                    collision_count += 1
                    # Correction d'urgence : déplacer radialement
                    angle = np.arctan2(dy, dx)
                    correction = (min_distance - distance) / 2

                    pos[node1][0] -= correction * np.cos(angle)
                    pos[node1][1] -= correction * np.sin(angle)
                    pos[node2][0] += correction * np.cos(angle)
                    pos[node2][1] += correction * np.sin(angle)

        if collision_count > 0:
            logger.warning(f"⚠️ {collision_count} collisions résiduelles corrigées")
        else:
            logger.debug(f"✅ Aucune collision détectée (distance min: {min_distance:.3f})")

        return pos

    def _apply_local_collision_avoidance(self, dragging_node):
        """✅ VERSION CORRIGÉE : Respecte les orbites pendant le drag"""
        pos = self.graph_data['pos']
        G = self.graph_data['G']
        num_nodes = self.graph_data['num_nodes']
        node_orbits = self.graph_data.get('node_orbits', {})

        # Distance minimale adaptée
        if num_nodes <= 10:
            base_min_distance = 2.5
            orbit_tolerance = 2.0
        elif num_nodes <= 20:
            base_min_distance = 2.0
            orbit_tolerance = 2.5
        else:
            base_min_distance = 1.5
            orbit_tolerance = 3.0

        x1, y1 = pos[dragging_node]
        dist_dragged = (x1**2 + y1**2) ** 0.5
        dragged_orbit = node_orbits.get(dragging_node, 3)

        for node in G.nodes():
            if node == dragging_node or node == self.current_central_name:
                continue
            
            x2, y2 = pos[node]
            dist_node = (x2**2 + y2**2) ** 0.5
            node_orbit = node_orbits.get(node, 3)

            dx = x2 - x1
            dy = y2 - y1
            distance = (dx**2 + dy**2) ** 0.5

            # Dimensions
            text_width = self.graph_data.get('text_width', 5.0)
            text_height = self.graph_data.get('text_height', 1.3)
            required_distance = (text_width + text_height) / 2 + base_min_distance

            if distance < required_distance and distance > 0.01:
                # Vérifier même orbite
                same_orbit_distance = abs(dist_dragged - dist_node) < orbit_tolerance
                same_orbit_number = (dragged_orbit == node_orbit)
                same_orbit = same_orbit_distance and same_orbit_number

                if same_orbit:
                    # Mouvement tangentiel
                    angle_dragged = math.atan2(y1, x1)
                    angle_node = math.atan2(y2, x2)

                    force = (required_distance - distance) * 0.02
                    avg_radius = (dist_dragged + dist_node) / 2

                    if avg_radius > 0.01:
                        angle_force = force / avg_radius
                    else:
                        angle_force = force * 0.1

                    new_angle = angle_node + angle_force

                    pos[node][0] = dist_node * math.cos(new_angle)
                    pos[node][1] = dist_node * math.sin(new_angle)

                else:
                    # Mouvement radial
                    if dist_node > 0.01:
                        radial_dir_x = x2 / dist_node
                        radial_dir_y = y2 / dist_node
                    else:
                        radial_dir_x = 1.0
                        radial_dir_y = 0.0

                    radial_force = (required_distance - distance) * 0.25

                    if dragged_orbit < node_orbit:
                        pos[node][0] += radial_force * radial_dir_x
                        pos[node][1] += radial_force * radial_dir_y
                    elif dragged_orbit > node_orbit:
                        pos[node][0] -= radial_force * radial_dir_x
                        pos[node][1] -= radial_force * radial_dir_y

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
        ax.margins(0)  # ✅ CORRECTION : Pas de marges automatiques
        self.figure.tight_layout(pad=0.1)  # ✅ NOUVEAU
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

        # Vider la légende du périmètre
        if hasattr(self, 'legend_layout'):
            while self.legend_layout.count() > 0:
                child = self.legend_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Ajouter le label par défaut
            default_label = QtWidgets.QLabel("Aucun élément sélectionné")
            default_label.setStyleSheet("color: #999; font-size: 10px; font-style: italic;")
            self.legend_layout.addWidget(default_label)
            self.legend_layout.addStretch()

    def _extract_node_relations(self, node_data: Dict, node_name: str, node_uid: str, 
                          node_type: str, relations_list: List[Dict]):
        relation_predicates = {
            'imports': 'import',
            'calls': 'call', 
            'uses': 'use',
            'extends': 'extends',
            'implements': 'implements'
        }

        for predicate, relation_type in relation_predicates.items():
            related_nodes = node_data.get(predicate, [])

            for related in related_nodes:
                related_uid = related.get('uid')
                related_name = related.get('name', '')
                related_type = related.get('nodeType', 'unknown')

                if not related_uid or not related_name:
                    continue

                related_name_norm = self.normalize_node_name(related_name)

                # Éviter les auto-références
                if related_name_norm == node_name:
                    continue

                relations_list.append({
                    'source': node_name,
                    'source_uid': node_uid,
                    'source_type': node_type,
                    'target': related_name_norm,
                    'target_uid': related_uid,
                    'target_type': related_type,
                    'relation_type': relation_type,
                    'category': 'code'
                })

    def _create_isolated_nodes_graph(self, selected_items: List[Dict]):
        logger.info("📊 Création graphe avec nœuds isolés")

        self.current_graph = nx.DiGraph()
        self.current_relations = []

        for item in selected_items:
            name = self.normalize_node_name(item.get('name', ''))
            node_type = item.get('type', 'file')

            if name:
                self.current_graph.add_node(
                    name,
                    node_type=node_type,
                    level=0,
                    selected=True,
                    uid=item.get('uid'),
                    hierarchy_level=0
                )

        self.central_node = None

        self._draw_graph()
        self._update_info_label()

        logger.info(f"✅ Graphe isolé créé avec {len(self.current_graph.nodes)} nœuds")
    
    def _resolve_uid_to_name(self, uid: str, force_refresh: bool = False) -> str:
        """✅ VERSION SÉCURISÉE : Vérifie les caches avant utilisation"""
        if not uid:
            return f"unknown_{id(uid)}"

        # ✅ S'assurer que les caches existent
        self._ensure_caches_initialized()

        # Vérifier cache
        if not force_refresh and uid in self.uid_to_name_cache:
            return self.uid_to_name_cache[uid]

        # Requête Dgraph dédiée
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            path
            id
            nodeType
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            node = result['node'][0]

            # Extraction intelligente du nom
            resolved_name = (
                node.get('name') or 
                node.get('label') or 
                node.get('path') or 
                node.get('id') or 
                f"Node_{uid[-8:]}"
            )

            resolved_name = self.normalize_node_name(resolved_name)

            # Mise en cache bidirectionnelle
            self.uid_to_name_cache[uid] = resolved_name
            self.name_to_uid_cache[resolved_name] = uid

            # Cache métadonnées complètes
            self.uid_metadata_cache[uid] = {
                'name': resolved_name,
                'type': node.get('nodeType', 'unknown'),
                'path': node.get('path'),
                'raw_data': node
            }

            logger.debug(f"  ✅ Résolu: {uid} → {resolved_name}")
            return resolved_name

        # Fallback si le nœud n'existe pas
        fallback_name = f"Node_{uid[-8:]}"
        self.uid_to_name_cache[uid] = fallback_name
        logger.warning(f"  ⚠️ UID {uid} introuvable, fallback: {fallback_name}")
        return fallback_name
        
    def _compute_grouped_layout(self, G: nx.DiGraph, center_node: str = None):
        """✅ VERSION CORRIGÉE : Classification correcte des orbites avec rayons adaptatifs."""
        if len(G.nodes()) == 0:
            return {}, {}

        import numpy as np

        num_nodes = len(G.nodes())

        # ✅ DÉFINITION DES TYPES PAR ORBITE (identique à relation_import_widget)
        HIERARCHICAL_TYPES = {
            'parent', 'child', 'contains', 'belongs_to', 'hierarchy', 
            'has', 'contains_class', 'contains_function', 'contains_variable',
            'has_method', 'has_variable'
        }

        INTERNAL_CODE_TYPES = {
            'import', 'from_import', 'call', 'calls', 'method_call', 
            'function_call', 'use', 'uses', 'used_by', 'implements', 'extends', 
            'inherits', 'override', 'invoke', 'intra_file'
        }

        EXTERNAL_TYPES = {
            'require', 'include', 'dependency', 'external', 'inter_file'
        }

        # 🎯 CLASSIFICATION DES NŒUDS PAR ORBITE
        hierarchical_nodes = []
        internal_code_nodes = []
        external_nodes = []

        for node in G.nodes():
            if node == center_node:
                continue
            
            relation_types = set()
            categories = set()
            has_intra_file = False

            # Collecter tous les types de relations du nœud
            for u, v, data in G.edges(data=True):
                if u == node or v == node:
                    rel_type = data.get('relation_type', '').lower()
                    category = data.get('category', '').lower()
                    intra = data.get('intraFile', False)

                    if rel_type:
                        relation_types.add(rel_type)
                    if category:
                        categories.add(category)
                    if intra:
                        has_intra_file = True

            # ✅ CLASSIFICATION AVEC PRIORITÉ : hiérarchique > code interne > externe
            is_hierarchical = any(t in HIERARCHICAL_TYPES for t in relation_types) or 'hierarchy' in categories
            is_internal_code = any(t in INTERNAL_CODE_TYPES for t in relation_types) or 'code' in categories or has_intra_file
            is_external = any(t in EXTERNAL_TYPES for t in relation_types) or 'external' in categories

            if is_hierarchical:
                hierarchical_nodes.append(node)
                logger.debug(f"  🔵 {node} -> Orbite 1 (hiérarchie)")
            elif is_internal_code:
                internal_code_nodes.append(node)
                logger.debug(f"  🟢 {node} -> Orbite 2 (code interne)")
            else:
                external_nodes.append(node)
                logger.debug(f"  🟠 {node} -> Orbite 3 (externe)")

        logger.info(f"📊 Classification orbites:")
        logger.info(f"   🔵 Orbite 1 (hiérarchie): {len(hierarchical_nodes)}")
        logger.info(f"   🟢 Orbite 2 (code interne): {len(internal_code_nodes)}")
        logger.info(f"   🟠 Orbite 3 (externe): {len(external_nodes)}")

        # 🎨 CALCUL DES RAYONS ADAPTATIFS
        pos = {}
        if center_node and center_node in G.nodes():
            pos[center_node] = np.array([0.0, 0.0])

        def compute_radius(base, count):
            """Rayon adaptatif selon densité avec marge de sécurité"""
            if count == 0:
                return base

            if num_nodes <= 15:
                avg_node_width = 8.0
                min_spacing = 3.5
            elif num_nodes <= 30:
                avg_node_width = 7.0
                min_spacing = 3.0
            else:
                avg_node_width = 6.0
                min_spacing = 2.5

            required_circumference = (avg_node_width + min_spacing) * count * 1.25  # +25% de marge
            min_required_radius = required_circumference / (2 * math.pi)
            return max(base, min_required_radius)
        
        base_gap = 12.0
        radius_inner = compute_radius(base_gap * 1.8, len(hierarchical_nodes))
        radius_middle = compute_radius(base_gap * 3.0, len(internal_code_nodes))
        radius_outer = compute_radius(base_gap * 4.5, len(external_nodes))     # 6.5 au lieu de 4.5

        logger.info(f"🔍 Rayons calculés : inner={radius_inner:.1f}, middle={radius_middle:.1f}, outer={radius_outer:.1f}")

        def distribute(nodes, radius, angular_offset=0.0):
            n = len(nodes)
            if n == 0:
                return
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / n + angular_offset
                # Décalage aléatoire léger pour briser symétries
                angle += (math.pi / 180) * np.random.uniform(-6, 6)
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                pos[node] = np.array([x, y])

        distribute(hierarchical_nodes, radius_inner)
        distribute(internal_code_nodes, radius_middle, angular_offset=math.pi / 8)
        distribute(external_nodes, radius_outer, angular_offset=math.pi / 5)

        # 🔄 Recentrage global
        if len(pos) > 1:
            coords = np.array(list(pos.values()))
            mean_x, mean_y = coords.mean(axis=0)
            for node in pos:
                pos[node] -= np.array([mean_x, mean_y])

        # 🔍 Enregistrer les orbites
        node_orbits = {}
        if center_node and center_node in G.nodes():
            node_orbits[center_node] = 0  # Centre

        for node in hierarchical_nodes:
            node_orbits[node] = 1
        for node in internal_code_nodes:
            node_orbits[node] = 2
        for node in external_nodes:
            node_orbits[node] = 3

        logger.info(f"✅ Orbites assignées: {len(node_orbits)} nœuds")

        return pos, node_orbits
    
    def _apply_universal_collision_avoidance(self, G, pos, num_nodes):
        """
        ✅ COLLISION AVOIDANCE avec RESPECT STRICT DES ORBITES
        """
        def get_node_dimensions(node_name):
            """Calcule largeur réelle basée sur longueur du texte"""
            # ✅ CORRECTION : Utiliser les dimensions réelles du graphe
            if hasattr(self, 'graph_data') and self.graph_data and 'node_dimensions' in self.graph_data:
                if node_name in self.graph_data['node_dimensions']:
                    return self.graph_data['node_dimensions'][node_name]

            # Fallback si pas encore calculé
            if num_nodes <= 15:
                max_chars = 30
                base_width = 8.0
            elif num_nodes <= 30:
                max_chars = 28
                base_width = 7.5
            else:
                max_chars = 25
                base_width = 7.0

            display_name = node_name[:max_chars] + '..' if len(node_name) > max_chars else node_name
            char_width = base_width / max_chars
            width = len(display_name) * char_width + 1.0
            height = 2.5 if num_nodes <= 15 else 2.2 if num_nodes <= 30 else 2.0

            return width, height

        def get_node_distance_from_center(node):
            """Calcule la distance d'un nœud par rapport au centre"""
            x, y = pos[node]
            return (x**2 + y**2) ** 0.5

        # ✅ PARAMÈTRES ADAPTATIFS
        if num_nodes <= 10:
            base_min_distance = 4.0
            iterations = 150
            orbit_tolerance = 3.0
        elif num_nodes <= 20:
            base_min_distance = 3.5
            iterations = 120
            orbit_tolerance = 3.5
        elif num_nodes <= 40:
            base_min_distance = 3.0
            iterations = 100
            orbit_tolerance = 4.0 
        else:
            base_min_distance = 2.5
            iterations = 80
            orbit_tolerance = 4.5

        node_distances = {}
        initial_distances = {}
        for node in G.nodes():
            dist = get_node_distance_from_center(node)
            node_distances[node] = dist
            initial_distances[node] = dist

        # ✅ RÉCUPÉRER LES ORBITES
        node_orbits = {}
        if hasattr(self, 'graph_data') and self.graph_data is not None:
            node_orbits = self.graph_data.get('node_orbits', {})

        if not node_orbits:
            node_orbits = {node: 3 for node in G.nodes()}

        logger.info(f"🔄 Collision avoidance : {iterations} itérations max, tolérance orbite={orbit_tolerance}")

        for iteration in range(iterations):
            nodes = list(G.nodes())
            max_displacement = 0

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]
                w1, h1 = get_node_dimensions(node1)
                dist1 = node_distances[node1]
                orbit1 = node_orbits.get(node1, 3)
                initial_dist1 = initial_distances[node1]

                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]
                    w2, h2 = get_node_dimensions(node2)
                    dist2 = node_distances[node2]
                    orbit2 = node_orbits.get(node2, 3)
                    initial_dist2 = initial_distances[node2]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    required_distance = (w1 + w2) / 2 + base_min_distance

                    if distance < required_distance and distance > 0.01:
                        force_factor = 1.0 - (iteration / iterations) * 0.5

                        # ✅ VÉRIFIER SI MÊME ORBITE
                        same_orbit_distance = abs(dist1 - dist2) < orbit_tolerance
                        same_orbit_number = (orbit1 == orbit2)
                        same_orbit = same_orbit_distance and same_orbit_number

                        if same_orbit:
                            # ===== MÊME ORBITE : MOUVEMENT TANGENTIEL =====
                            angle1 = math.atan2(y1, x1)
                            angle2 = math.atan2(y2, x2)

                            force = (required_distance - distance) * 0.03 * force_factor
                            avg_radius = (dist1 + dist2) / 2

                            if avg_radius > 0.01:
                                angle_force = force / avg_radius
                            else:
                                angle_force = force * 0.1

                            new_angle1 = angle1 - angle_force
                            new_angle2 = angle2 + angle_force

                            # ✅ CONTRAINTE : Garder la distance orbitale
                            pos[node1][0] = initial_dist1 * math.cos(new_angle1)
                            pos[node1][1] = initial_dist1 * math.sin(new_angle1)
                            pos[node2][0] = initial_dist2 * math.cos(new_angle2)
                            pos[node2][1] = initial_dist2 * math.sin(new_angle2)

                            max_displacement = max(max_displacement, angle_force * avg_radius)

                        else:
                            # ===== ORBITES DIFFÉRENTES : MOUVEMENT RADIAL LIMITÉ =====
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

                            # ✅ Force radiale RÉDUITE pour éviter de changer d'orbite
                            radial_force = (required_distance - distance) * 0.15 * force_factor  # Réduit de 0.3 à 0.15

                            if dist1 < dist2:
                                # node1 plus proche du centre
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

                            # ✅ CONTRAINTE : Ramener vers l'orbite initiale si trop éloigné
                            current_dist1 = get_node_distance_from_center(node1)
                            if abs(current_dist1 - initial_dist1) > orbit_tolerance:
                                # Ramener progressivement
                                correction_factor = 0.1
                                target_x1 = x1 * (initial_dist1 / current_dist1)
                                target_y1 = y1 * (initial_dist1 / current_dist1)
                                pos[node1][0] += (target_x1 - x1) * correction_factor
                                pos[node1][1] += (target_y1 - y1) * correction_factor

                            current_dist2 = get_node_distance_from_center(node2)
                            if abs(current_dist2 - initial_dist2) > orbit_tolerance:
                                correction_factor = 0.1
                                target_x2 = x2 * (initial_dist2 / current_dist2)
                                target_y2 = y2 * (initial_dist2 / current_dist2)
                                pos[node2][0] += (target_x2 - x2) * correction_factor
                                pos[node2][1] += (target_y2 - y2) * correction_factor

                    # ✅ Mettre à jour les distances
                    node_distances[node1] = get_node_distance_from_center(node1)
                    node_distances[node2] = get_node_distance_from_center(node2)

                # ✅ CONVERGENCE
                if max_displacement < 0.01:
                    logger.info(f"✅ Convergence atteinte à l'itération {iteration}")
                    break

        logger.info(f"✅ Collision avoidance terminée")
        return pos
    
    def _log_relation_stats(self, relations_list: List[Dict]):
        """
        📊 Affiche des statistiques sur les relations récupérées
        """
        if not relations_list:
            return
        
        # Par type
        by_type = {}
        for rel in relations_list:
            rel_type = rel.get('relation_type', 'unknown')
            by_type[rel_type] = by_type.get(rel_type, 0) + 1
        
        # Par catégorie
        by_category = {}
        for rel in relations_list:
            category = rel.get('category', 'unknown')
            by_category[category] = by_category.get(category, 0) + 1
        
        # Intra-file vs externe
        intra_count = sum(1 for rel in relations_list if rel.get('intraFile'))
        externe_count = len(relations_list) - intra_count
        
        logger.info(f"\n📊 STATISTIQUES :")
        logger.info(f"   Total : {len(relations_list)}")
        logger.info(f"   Intra-fichier : {intra_count}")
        logger.info(f"   Externes : {externe_count}")
        
        logger.info(f"\n📈 PAR TYPE :")
        for rel_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            logger.info(f"   • {rel_type} : {count}")
        
        logger.info(f"\n📂 PAR CATÉGORIE :")
        for category, count in sorted(by_category.items(), key=lambda x: -x[1]):
            logger.info(f"   • {category} : {count}")

    def _draw_orbit_legend(self, ax, edges, node_orbits):
        """
        ✅ LÉGENDE COMPACTE en haut à droite avec types de relations et statistiques
        """
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch

        legend_elements = []

        # ===== COULEURS PAR TYPE DE NŒUD (au lieu d'orbites) =====
        type_colors = {
            'hierarchy': ('#2196F3', '🔵 Hiérarchie'),
            'code': ('#00ACC1', '🟢 Code interne'),
            'call': ('#9C27B0', '🟣 Appels/Calls'),
            'external': ('#FF8C00', '🟠 Externe'),
            'unknown': ('#999999', '⚪ Autre')
        }

        # ✅ Compter les nœuds par type dominant (au lieu de par orbite)
        if hasattr(self, 'current_graph') and self.current_graph:
            G = self.current_graph
            node_type_counts = {}

            for node in G.nodes():
                # Récupérer le type dominant du nœud
                node_relation_types = {}

                for u, v, data in G.edges(data=True):
                    if u == node or v == node:
                        rel_type = data.get('relation_type', '').lower()
                        if rel_type:
                            node_relation_types[rel_type] = node_relation_types.get(rel_type, 0) + 1

                # Classifier le nœud
                node_category = 'unknown'

                if node_relation_types:
                    dominant_type = max(node_relation_types, key=node_relation_types.get)

                    # Hiérarchique
                    if dominant_type in ['parent', 'child', 'contains', 'hierarchy',
                                        'contains_class', 'contains_function', 'contains_variable',
                                        'has_method', 'has_variable', 'belongs_to']:
                        node_category = 'hierarchy'

                    # Code interne
                    elif dominant_type in ['import', 'from_import', 'use', 'uses', 'used_by',
                                          'implements', 'extends', 'inherits', 'intra_file']:
                        node_category = 'code'

                    # Appels
                    elif dominant_type in ['call', 'calls', 'method_call', 'function_call', 'called_by']:
                        node_category = 'call'

                    # Externe
                    elif dominant_type in ['require', 'dependency', 'external', 'inter_file', 'include']:
                        node_category = 'external'

                node_type_counts[node_category] = node_type_counts.get(node_category, 0) + 1

            # Afficher les catégories avec des nœuds
            for category in ['hierarchy', 'code', 'call', 'external', 'unknown']:
                count = node_type_counts.get(category, 0)
                if count > 0:
                    color, label_text = type_colors[category]
                    legend_elements.append(
                        Patch(facecolor=color, edgecolor='#666666', linewidth=1.5,
                              label=f"{label_text} ({count})")
                    )

        # ===== SÉPARATEUR =====
        if legend_elements:
            legend_elements.append(Line2D([0], [0], color='none', label=''))

        # ===== TOP 5 TYPES DE RELATIONS (arêtes) =====
        edge_types_count = {}
        for _, _, d in edges:
            rel_type = d.get('relation_type', 'unknown')
            color = d.get('color', '#CCCCCC')
            if rel_type not in edge_types_count:
                edge_types_count[rel_type] = {'count': 0, 'color': color}
            edge_types_count[rel_type]['count'] += 1

        # Trier par fréquence
        sorted_types = sorted(edge_types_count.items(), key=lambda x: -x[1]['count'])[:5]

        for rel_type, data in sorted_types:
            count = data['count']
            color = data['color']
            short_name = rel_type[:15] + '..' if len(rel_type) > 15 else rel_type
            legend_elements.append(
                Line2D([0], [0], color=color, linewidth=2.5, 
                      label=f"{short_name} ({count})",
                      marker='>', markersize=6)
            )

        if len(edge_types_count) > 5:
            remaining = len(edge_types_count) - 5
            legend_elements.append(
                Line2D([0], [0], color='#999999', linewidth=1.5, 
                      label=f'... +{remaining} types',
                      linestyle='--')
            )

        # ===== STATISTIQUES GLOBALES =====
        total_nodes = len(self.current_graph.nodes()) if hasattr(self, 'current_graph') and self.current_graph else 0
        total_edges = len(edges)

        legend_elements.append(Line2D([0], [0], color='none', label=''))
        legend_elements.append(
            Line2D([0], [0], color='none', 
                  label=f"📊 {total_nodes} nœuds • {total_edges} relations")
        )

        # ===== AFFICHER LA LÉGENDE =====
        if legend_elements:
            legend = ax.legend(
                handles=legend_elements, 
                loc='upper right',  # ✅ Position de base
                fontsize=7,
                title="Graphe de Relations",
                title_fontsize=9,
                framealpha=0.95,
                edgecolor='#CCCCCC',
                fancybox=True,
                shadow=True,
                ncol=1,
                columnspacing=0.5,
                handlelength=1.8,
                handletextpad=0.6,
                borderpad=0.6,
                labelspacing=0.4
            )

            legend.set_bbox_to_anchor((1.0, 1.0), transform=ax.transAxes)

            legend.get_frame().set_facecolor('#FFFFFF')
            legend.get_frame().set_linewidth(1.5)

    def _resolve_uids_batch(self, uids: List[str]) -> Dict[str, str]:
        """✅ VERSION SÉCURISÉE : Vérifie les caches avant utilisation"""
        if not uids:
            return {}

        # ✅ S'assurer que les caches existent
        self._ensure_caches_initialized()

        # Filtrer les UIDs déjà en cache
        uncached_uids = [uid for uid in uids if uid not in self.uid_to_name_cache]

        if not uncached_uids:
            return {uid: self.uid_to_name_cache[uid] for uid in uids}

        logger.info(f"🔍 Résolution batch: {len(uncached_uids)} UIDs")

        # Requête batch
        uid_list = ", ".join(uncached_uids)
        query = f"""
        {{
          nodes(func: uid({uid_list})) {{
            uid
            name
            label
            path
            id
            nodeType
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'nodes' in result:
            for node in result['nodes']:
                node_uid = node.get('uid')
                if not node_uid:
                    continue
                
                resolved_name = (
                    node.get('name') or 
                    node.get('label') or 
                    node.get('path') or 
                    node.get('id') or 
                    f"Node_{node_uid[-8:]}"
                )

                resolved_name = self.normalize_node_name(resolved_name)

                # Mise en cache
                self.uid_to_name_cache[node_uid] = resolved_name
                self.name_to_uid_cache[resolved_name] = node_uid
                self.uid_metadata_cache[node_uid] = {
                    'name': resolved_name,
                    'type': node.get('nodeType', 'unknown'),
                    'path': node.get('path'),
                    'raw_data': node
                }

        # UIDs non résolus → fallback
        for uid in uncached_uids:
            if uid not in self.uid_to_name_cache:
                fallback = f"Node_{uid[-8:]}"
                self.uid_to_name_cache[uid] = fallback
                logger.warning(f"  ⚠️ UID {uid} non résolu, fallback: {fallback}")

        # Retourner le mapping complet
        return {uid: self.uid_to_name_cache[uid] for uid in uids}
    
    def _resolve_name_to_uid(self, name: str) -> Optional[str]:
        """✅ VERSION SÉCURISÉE : Vérifie les caches avant utilisation"""
        if not name:
            return None

        normalized_name = self.normalize_node_name(name)

        # ✅ S'assurer que les caches existent
        self._ensure_caches_initialized()

        # Vérifier cache
        if normalized_name in self.name_to_uid_cache:
            return self.name_to_uid_cache[normalized_name]

        # Requête Dgraph
        query = f"""
        {{
          node(func: eq(name, "{name}")) {{
            uid
            name
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            uid = result['node'][0].get('uid')
            if uid:
                self.name_to_uid_cache[normalized_name] = uid
                self.uid_to_name_cache[uid] = normalized_name
                return uid

        # Essayer avec label
        query = f"""
        {{
          node(func: eq(label, "{name}")) {{
            uid
            label
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            uid = result['node'][0].get('uid')
            if uid:
                self.name_to_uid_cache[normalized_name] = uid
                self.uid_to_name_cache[uid] = normalized_name
                return uid

        logger.warning(f"⚠️ Nom '{name}' introuvable dans Dgraph")
        return None

    def update_graph_with_code_relations(self, selected_items: List[Dict], project_data: Dict):
        """✅ CORRIGÉ : Affiche UNIQUEMENT les vraies relations entre sélections"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🕸️ RELATIONS ENTRE SÉLECTIONS MULTIPLES")
        logger.info(f"{'='*70}")
        logger.info(f"  Éléments sélectionnés : {len(selected_items)}")

        if not selected_items:
            self._clear_graph()
            return

        self.current_project_data = project_data

        # ✅ COLLECTER LES UIDs ET NOMS
        selected_uids = []
        uid_to_name = {}
        selected_names = []

        for item in selected_items:
            uid = item.get('uid')
            name = self.normalize_node_name(item.get('name', ''))

            if uid and name:
                selected_uids.append(uid)
                uid_to_name[uid] = name
                selected_names.append(name)
                logger.info(f"  ✓ {name} (uid: {uid})")

        if not selected_uids:
            logger.warning("⚠️ Aucun UID valide")
            self._clear_graph()
            return

        # ✅ RÉCUPÉRER TOUTES LES RELATIONS pour chaque élément
        all_relations = []
        for uid in selected_uids:
            relations = self._get_complete_relations(uid, level=1)
            all_relations.extend(relations)

        logger.info(f"\n📊 {len(all_relations)} relations récupérées au total")

        # ✅ VALIDER FORMAT
        validated_relations = self._validate_relations_format(all_relations)

        # ✅ FILTRER : Garder UNIQUEMENT les relations entre éléments sélectionnés
        filtered_relations = []
        selected_uid_set = set(selected_uids)
        selected_name_set = set(selected_names)

        for rel in validated_relations:
            source_uid = rel.get('source_uid')
            target_uid = rel.get('target_uid')
            source_name = rel.get('source', '')
            target_name = rel.get('target', '')

            # Vérifier par UID ET par nom
            source_in_selection = (source_uid in selected_uid_set or source_name in selected_name_set)
            target_in_selection = (target_uid in selected_uid_set or target_name in selected_name_set)

            # ✅ GARDER UNIQUEMENT SI LES DEUX SONT DANS LA SÉLECTION
            if source_in_selection and target_in_selection:
                filtered_relations.append(rel)

        logger.info(f"🔗 {len(filtered_relations)} relations RÉELLES entre sélections")

        # ✅ SI AUCUNE RELATION : Afficher les nœuds SANS LIENS
        if not filtered_relations:
            logger.warning("⚠️ Aucune relation réelle entre les éléments sélectionnés")
            logger.info("ℹ️ Affichage des nœuds sans connexion")

            # Créer un graphe avec les nœuds mais SANS arêtes
            self.current_graph = nx.DiGraph()

            for item in selected_items:
                node_name = self.normalize_node_name(item.get('name', ''))
                node_type = item.get('type', 'file')

                self.current_graph.add_node(
                    node_name,
                    node_type=node_type,
                    level=0,
                    selected=True,
                    uid=item.get('uid')
                )

            self.current_relations = []
            self.central_node = None

            self._draw_graph()

            logger.info(f"✅ {len(self.current_graph.nodes)} nœuds affichés SANS connexion")
            logger.info(f"{'='*70}\n")
            return

        # ✅ CONSTRUIRE LE GRAPHE avec les vraies relations
        self.current_relations = filtered_relations
        self.current_graph = self._build_clean_graph(filtered_relations)

        # ✅ MARQUER les nœuds comme sélectionnés
        for node in self.current_graph.nodes:
            node_type = 'unknown'
            for item in selected_items:
                if self.normalize_node_name(item.get('name', '')) == node:
                    node_type = item.get('type', 'file')
                    break

            self.current_graph.nodes[node]['node_type'] = node_type
            self.current_graph.nodes[node]['level'] = 0
            self.current_graph.nodes[node]['selected'] = True

        self.central_node = None

        self._draw_graph()

        logger.info(f"✅ Graphe multi-sélection généré avec {len(self.current_graph.nodes)} nœuds")
        logger.info(f"✅ {len(filtered_relations)} relations RÉELLES affichées")
        logger.info(f"{'='*70}\n")

    def closeEvent(self, event):
        """Fermeture propre."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)