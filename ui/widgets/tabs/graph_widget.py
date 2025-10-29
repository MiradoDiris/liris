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

from utils.logger import logger
from utils.dgraph_connector import LirisDgraphConnector

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
        """✅ CORRIGÉ : Garde l'extension pour les fichiers"""
        if not name or not isinstance(name, str):
            return f"unnamed_{id(name)}"

        name = name.strip()
        if not name or name.lower() == 'n/a':
            return f"unnamed_{id(name)}"

        # ✅ NOUVEAU : Garder le basename complet (avec extension)
        base = os.path.basename(name)

        # Si c'est un fichier (a une extension), garder tel quel
        if '.' in base and len(base.split('.')[-1]) <= 5:
            return base

        # Sinon, supprimer l'extension
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
        self._update_legend()
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

        # ✅ DÉTECTION SÉLECTION MULTIPLE
        if len(related_items) > 1 and all(item.get('uid') for item in related_items):
            logger.info("🎯 Mode sélection multiple détecté")
            return self.update_graph_with_persistent_selections(
                related_items, project_data, append_mode
            )

        # ✅ DÉTECTION STRUCTURE INTERNE
        if (len(related_items) == 1 and 
            related_items[0].get('mode') == 'internal_structure'):
            logger.info("📂 Mode structure interne détecté")
            return self.update_graph_with_internal_structure(
                central_node, central_uid, 
                related_items[0].get('data', {}), 
                project_data
            )

        # ✅ NOUVEAU : DÉTECTION CONTEXTE HIÉRARCHIQUE
        if central_uid and central_node:
            hierarchical_context = self._detect_hierarchical_context(central_uid, central_node)

            if hierarchical_context['has_hierarchy']:
                logger.info(f"🌳 Contexte hiérarchique détecté - Mode: {hierarchical_context['display_mode']}")

                if hierarchical_context['display_mode'] == 'hierarchy':
                    return self.update_graph_with_hierarchical_relations(
                        central_node, central_uid, hierarchical_context, project_data, append_mode
                    )
                elif hierarchical_context['display_mode'] == 'internal_structure':
                    return self.update_graph_with_internal_structure(
                        central_node, central_uid, 
                        {'classes': [elem for elem in hierarchical_context['code_elements'] if elem['type'] == 'class'],
                         'functions': [elem for elem in hierarchical_context['code_elements'] if elem['type'] == 'function'],
                         'variables': [elem for elem in hierarchical_context['code_elements'] if elem['type'] == 'variable']}, 
                        project_data
                    )

        # ✅ MODE STANDARD (code existant inchangé)
        if not central_node or not central_uid:
            if not append_mode:
                self._clear_graph()
            return

        self.current_project_data = project_data
        self.central_node = central_node
        self.current_central_uid = central_uid

        # ✅ GESTION APPEND_MODE
        if append_mode and hasattr(self, 'current_relations'):
            logger.info("🔄 Mode ajout - fusion avec relations existantes")
            existing_relations = self.current_relations.copy()
        else:
            existing_relations = []
            self.related_items = related_items

        # Détecter le niveau
        level = 1
        for item in related_items:
            if item.get('search_depth'):
                level = item['search_depth']
                break
            
        logger.info(f"  Niveau détecté: {level}")

        # ✅ RÉCUPÉRER NOUVELLES RELATIONS
        new_relations = self._get_complete_relations(central_uid, level)
        logger.info(f"📊 {len(new_relations)} nouvelles relations")

        # ✅ DIAGNOSTIC DES RELATIONS AVANT FUSION
        if new_relations:
            diagnostic = self._diagnose_hierarchy_relations(new_relations)
            if diagnostic['issues']:
                logger.warning("⚠️ Problèmes détectés dans les relations")

        # ✅ FUSION avec relations existantes
        if append_mode and existing_relations:
            all_relations = existing_relations + new_relations

            # Dédoublonner
            unique_relations = []
            seen_keys = set()

            for rel in all_relations:
                key = (
                    rel.get('source_uid', ''),
                    rel.get('target_uid', ''),
                    rel.get('relation_type', '')
                )

                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_relations.append(rel)

            validated_relations = self._validate_relations_format(unique_relations)
            logger.info(f"🔗 {len(validated_relations)} relations après fusion")
        else:
            validated_relations = self._validate_relations_format(new_relations)

        if not validated_relations:
            logger.warning("⚠️ Aucune relation valide trouvée")
            if not append_mode:
                self._clear_graph()
            return

        # ✅ DIAGNOSTIC FINAL DES RELATIONS VALIDÉES
        final_diagnostic = self._diagnose_hierarchy_relations(validated_relations)
        if final_diagnostic['valid_relations'] == 0:
            logger.error("❌ CRITIQUE: Aucune relation valide après validation")
            if not append_mode:
                self._clear_graph()
            return

        # ✅ CONSTRUIRE LE GRAPHE
        self.current_relations = validated_relations
        self.current_graph = self._build_clean_graph(validated_relations)

        # Vérification post-construction
        if not self.current_graph or len(self.current_graph.edges()) == 0:
            logger.error("❌ CRITIQUE: Graphe sans arêtes après construction")
            logger.info("🔍 Lancement diagnostic approfondi...")

            # Diagnostic approfondi
            for i, rel in enumerate(validated_relations[:5]):
                logger.info(f"  Relation {i}: {rel.get('source')} -> {rel.get('target')} [{rel.get('relation_type')}]")

        # ✅ ENRICHIR LES MÉTADONNÉES
        for node in self.current_graph.nodes:
            node_uid = self.current_graph.nodes[node].get('uid')

            if node_uid:
                node_details = self._get_node_details(node_uid)
                self.current_graph.nodes[node]['level'] = node_details.get('level', 0)
                if not self.current_graph.nodes[node].get('node_type'):
                    self.current_graph.nodes[node]['node_type'] = node_details.get('nodeType', 'unknown')
            else:
                self.current_graph.nodes[node]['level'] = 0
                if not self.current_graph.nodes[node].get('node_type'):
                    self.current_graph.nodes[node]['node_type'] = 'unknown'

            # ✅ HIÉRARCHIE : Marquer le niveau hiérarchique
            if node == central_node:
                self.current_graph.nodes[node]['hierarchy_level'] = 0  # Nœud central
            else:
                # Calculer niveau hiérarchique basé sur les relations
                self.current_graph.nodes[node]['hierarchy_level'] = self._calculate_hierarchy_level(
                    node, central_node, validated_relations
                )

        all_uids = [central_uid]
        for item in related_items:
            if item.get('uid'):
                all_uids.append(item['uid'])

        self._preload_uid_cache(all_uids)

        self._draw_graph()
        self._update_legend()

        logger.info(f"✅ Graphe généré avec {len(self.current_graph.nodes)} nœuds, {len(self.current_graph.edges)} arêtes")
        logger.info(f"{'='*70}\n")

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
        self._update_legend()
        self._update_info_label()

        logger.info(f"✅ Graphe hiérarchique généré avec {len(self.current_graph.nodes)} nœuds, {len(self.current_graph.edges)} arêtes")

    def _validate_relations_format(self, relations_list: List[Dict]) -> List[Dict]:
        """✅ VERSION CORRIGÉE : Validation sans perte de données"""
        validated_relations = []

        for rel in relations_list:
            if not isinstance(rel, dict):
                continue

            # ✅ GARDER LES NOMS ORIGINAUX (avec extension)
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()

            # ✅ Validation minimale
            if not source or not target or source == target:
                continue

            # ✅ Normalisation unifiée relation_type
            relation_type = rel.get('relation_type') or rel.get('relationType', 'unknown')

            # ✅ Construire relation normalisée
            normalized_rel = {
                'source': source,
                'source_uid': rel.get('source_uid', ''),
                'source_type': rel.get('source_type', 'unknown'),
                'target': target,
                'target_uid': rel.get('target_uid', ''),
                'target_type': rel.get('target_type', 'unknown'),
                'relation_type': relation_type,
                'category': rel.get('category', 'external')
            }

            validated_relations.append(normalized_rel)

        logger.info(f"✅ {len(validated_relations)} relations validées sur {len(relations_list)}")
        return validated_relations

    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """✅ CORRIGÉ : Construction sans normalisation excessive"""
        G = nx.DiGraph()
        nodes_registry = {}
        edges_registry = {}

        logger.info(f"🔨 Construction graphe avec {len(relations_list)} relations")

        # ÉTAPE 1: Collecter tous les nœuds SANS normalisation
        for rel in relations_list:
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()

            if not source or not target or source == target:
                continue
            
            # ✅ PAS de normalisation ici
            if source not in nodes_registry:
                nodes_registry[source] = {
                    'node_type': rel.get('source_type', 'unknown'),
                    'uid': rel.get('source_uid', '')
                }
            if target not in nodes_registry:
                nodes_registry[target] = {
                    'node_type': rel.get('target_type', 'unknown'),
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

        # ÉTAPE 3: Collecter et valider toutes les arêtes
        valid_edges_count = 0
        for rel in relations_list:
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()
            rel_type = rel.get('relation_type', 'unknown')
            category = rel.get('category', 'custom')

            # Validation stricte des arêtes
            if not source or not target or source == target:
                continue

            # Vérifier que les nœuds existent dans le graphe
            if source not in G.nodes or target not in G.nodes:
                logger.warning(f"⚠️ Nœuds manquants pour relation: {source} -> {target}")
                continue
            
            edge_key = (source, target)
            if edge_key not in edges_registry:
                edges_registry[edge_key] = []

            # Créer le label de l'arête
            type_label = f"{rel_type} [{category}]" if category != 'custom' else rel_type
            if type_label not in edges_registry[edge_key]:
                edges_registry[edge_key].append(type_label)
                valid_edges_count += 1

        logger.info(f"🔗 Arêtes valides collectées: {valid_edges_count}")

        # ÉTAPE 4: Ajouter toutes les arêtes au graphe
        edges_added = 0
        for (source, target), rel_types in edges_registry.items():
            # S'assurer que les nœuds existent toujours
            if source in G.nodes and target in G.nodes:
                primary_type = rel_types[0]
                combined_label = f"{primary_type} (+{len(rel_types)-1})" if len(rel_types) > 1 else primary_type

                G.add_edge(
                    source, target,
                    color=self._get_color_for_type(primary_type),
                    relation_type=primary_type,
                    all_types=rel_types,
                    label=combined_label
                )
                edges_added += 1

        logger.info(f"✅ Arêtes ajoutées au graphe: {edges_added}")

        # ÉTAPE 5: Diagnostic final
        final_nodes = len(G.nodes())
        final_edges = len(G.edges())
        isolated_nodes = list(nx.isolates(G))

        logger.info(f"📈 Graphe final: {final_nodes} nœuds, {final_edges} arêtes")

        if isolated_nodes:
            logger.warning(f"⚠️ Nœuds isolés détectés: {len(isolated_nodes)}")
            for node in isolated_nodes[:5]:
                logger.warning(f"  • {node}")

        # Ne supprimer les nœuds isolés que si on a des arêtes
        if final_edges > 0 and isolated_nodes:
            logger.info("🧹 Suppression des nœuds isolés")
            G.remove_nodes_from(isolated_nodes)
            logger.info(f"✅ Graphe nettoyé: {len(G.nodes())} nœuds, {len(G.edges())} arêtes")

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

    def _get_color_for_type(self, rel_type: str) -> str:
        """✅ MODIFIÉ : Ajouter couleurs pour relations Dgraph type Relation"""
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()
    
        color_map = {
            # Relations type Relation (NOUVELLES)
            'import': '#CC5500',        # Orange foncé
            'call': '#2AA198',          # Turquoise foncé
            'use': '#3B7A57',           # Vert menthe sombre
            'inherit': '#C23B22',       # Rouge brique / saumon foncé
            'extends': '#6A5ACD',       # Violet foncé
            'implements': '#2E8B57',    # Vert forêt
            
            # Relations hiérarchiques
            'parent': '#1565C0',        # Bleu profond
            'child': '#1B5E20',         # Vert foncé
            'contains_class': '#6A1B9A',# Violet sombre
            'contains_function': '#E65100', # Orange brûlé
            'contains_variable': '#9E9D24', # Vert olive
            
            # Relations de code existantes
            'from_import': '#B35900',   # Orange terre
            'require': '#B35900',       # Même teinte pour cohérence
            'function_call': '#005A9C', # Bleu foncé
            'relation': '#4B0082',      # Indigo profond
            'uses': '#CC7722',          # Orange ambré
            
            # Relations internes
            'has_method': '#283593',    # Bleu nuit
            'has_variable': '#2E7D32',  # Vert forêt foncé
        }
        for key, color in color_map.items():
            if key in rel_lower:
                return color
        
        return '#999999'  # Défaut gris

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

        # ✅ NOUVEAU : Barre d'outils en haut
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setSpacing(8)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)

        # Bouton vider le graphe
        self.clear_button = QtWidgets.QPushButton("🧹 Vider le graphe")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                color: #333333;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
        """)
        self.clear_button.clicked.connect(self.clear_graph_action)
        self.clear_button.setMaximumWidth(150)
        toolbar_layout.addWidget(self.clear_button)

        # Label info (optionnel)
        self.info_label = QtWidgets.QLabel("Aucun graphe")
        self.info_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        toolbar_layout.addWidget(self.info_label)

        toolbar_layout.addStretch()

        # Statistiques (optionnel)
        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        toolbar_layout.addWidget(self.stats_label)

        layout.addLayout(toolbar_layout)

        # Canvas graphe (existant)
        self.figure = Figure(facecolor='white', figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self._on_graph_click)
        self.canvas.mpl_connect('motion_notify_event', self._on_graph_motion)
        self.canvas.mpl_connect('button_release_event', self._on_graph_release)
        layout.addWidget(self.canvas)

        # Légende dynamique (existant)
        legend_widget = QtWidgets.QWidget()
        self.legend_layout = QtWidgets.QHBoxLayout(legend_widget)
        self.legend_layout.setSpacing(2)
        layout.addWidget(legend_widget)

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
        """
        ✅ CORRIGÉ : Cache optionnel
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 RÉCUPÉRATION RELATIONS COMPLÈTES")
        logger.info(f"  UID: {uid}")
        logger.info(f"  Niveau: {level}")
        logger.info(f"  Cache: {use_cache}")
        logger.info(f"{'='*70}")

        # ✅ Vérifier cache UNIQUEMENT si demandé
        if use_cache:
            cache_key = f"complete_relations_{uid}_{level}"
            cached_data = self.query_cache.get(cache_key)
            if cached_data:
                logger.info(f"📦 Relations récupérées depuis cache: {len(cached_data)}")
                return cached_data

        all_relations = []
        processed_uids = set()

        # ÉTAPE 1 : Relations du nœud central
        central_relations = self._get_node_all_relations(uid)
        all_relations.extend(central_relations)
        processed_uids.add(uid)

        logger.info(f"✅ Nœud central : {len(central_relations)} relations")

        # ÉTAPE 2 : Si niveau 2, récupérer relations des nœuds connectés
        if level == 2:
            connected_uids = set()

            for rel in central_relations:
                source_uid = rel.get('source_uid')
                target_uid = rel.get('target_uid')

                if source_uid and source_uid != uid:
                    connected_uids.add(source_uid)
                if target_uid and target_uid != uid:
                    connected_uids.add(target_uid)

            logger.info(f"🔗 {len(connected_uids)} nœuds connectés à explorer")

            for connected_uid in connected_uids:
                if connected_uid in processed_uids:
                    continue
                
                connected_relations = self._get_node_all_relations(connected_uid)
                all_relations.extend(connected_relations)
                processed_uids.add(connected_uid)

        # ÉTAPE 3 : Dédoublonner
        unique_relations = []
        seen_keys = set()

        for rel in all_relations:
            if 'relation_type' not in rel and 'relationType' in rel:
                rel['relation_type'] = rel['relationType']
            elif 'relation_type' not in rel:
                rel['relation_type'] = 'unknown'

            key = (
                rel.get('source_uid', ''),
                rel.get('target_uid', ''),
                rel.get('relation_type', '')
            )

            if key not in seen_keys and key[0] and key[1]:
                seen_keys.add(key)
                unique_relations.append(rel)

        # ✅ Mettre en cache UNIQUEMENT si demandé
        if use_cache:
            cache_key = f"complete_relations_{uid}_{level}"
            self.query_cache.set(cache_key, unique_relations)

        logger.info(f"\n📊 STATISTIQUES FINALES :")
        logger.info(f"  Total relations : {len(unique_relations)}")
        logger.info(f"  Nœuds traités : {len(processed_uids)}")

        return unique_relations
    
    def _get_node_all_relations(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION CORRIGÉE : Utilise la méthode unifiée pour type Relation
        """
        if not uid or not self.dgraph_connector:
            logger.warning("⚠️ Pas d'UID ou pas de connecteur Dgraph")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 RÉCUPÉRATION RELATIONS COMPLÈTES")
        logger.info(f"  UID: {uid}")
        logger.info(f"{'='*70}")

        all_relations = []

        # 1️⃣ Relations hiérarchiques et de code (requête simplifiée)
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
        else:
            node = result['node'][0]
            central_uid = node.get('uid')
            central_name = self.normalize_node_name(
                node.get('name') or 
                node.get('label') or 
                node.get('path') or 
                f"Node_{uid[-8:]}"
            )
            central_type = node.get('nodeType', 'unknown')

            # Traiter relations hiérarchiques
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

            # Traiter relations de code
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

        # 2️⃣ ✅ Relations via type Relation (MÉTHODE UNIFIÉE CORRIGÉE)
        try:
            relation_type_relations = self._get_relation_type_relations(uid)

            # Fusionner en évitant les doublons
            existing_keys = set()
            for rel in all_relations:
                key = (
                    rel.get('source_uid') or rel.get('source'),
                    rel.get('target_uid') or rel.get('target'),
                    rel.get('relation_type')
                )
                existing_keys.add(key)

            # Ajouter uniquement les nouvelles
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
            import traceback
            traceback.print_exc()

        # 3️⃣ Statistiques finales
        self._log_relation_stats(all_relations)

        logger.info(f"\n✅ Total final: {len(all_relations)} relations pour {uid}")

        return all_relations
    
    def _get_nodes_details_batch(self, uids: List[str]) -> Dict[str, Dict]:
        """
        ✅ NOUVELLE MÉTHODE : Récupère les détails de plusieurs nœuds en une seule requête
        avec système de cache pour optimiser les performances
        """
        if not uids:
            return {}

        # Vérifier le cache d'abord
        cached_details = {}
        missing_uids = []

        for uid in uids:
            cache_key = f"node_details_{uid}"
            cached_data = self.query_cache.get(cache_key)
            if cached_data:
                cached_details[uid] = cached_data
            else:
                missing_uids.append(uid)

        logger.info(f"📦 Cache: {len(cached_details)} trouvés, {len(missing_uids)} à récupérer")

        # Récupérer les nœuds manquants
        if missing_uids:
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
                description

                # Relations de base pour contexte
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
                        # Mettre en cache
                        cache_key = f"node_details_{node_uid}"
                        self.query_cache.set(cache_key, node)
                        cached_details[node_uid] = node

        logger.info(f"✅ Détails récupérés pour {len(cached_details)} nœuds")
        return cached_details
    
    def _diagnose_relation_issues(self, uid: str) -> Dict:
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

          # Compter relations de type Relation
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
            hierarchical_predicates = ['parents', 'children', 'classes', 'functions', 'variables']
            for predicate in hierarchical_predicates:
                count = len(node_data.get(predicate, []))
                if count > 0:
                    diagnostic['relation_counts'][predicate] = count

            # Compter relations de code
            code_predicates = ['imports', '~imports', 'calls', '~calls', 'uses', '~uses']
            for predicate in code_predicates:
                count = len(node_data.get(predicate, []))
                if count > 0:
                    diagnostic['relation_counts'][predicate] = count

            # Compter relations de type Relation
            outgoing_rels = result.get('outgoing_relations', [])
            incoming_rels = result.get('incoming_relations', [])

            if outgoing_rels:
                diagnostic['relation_counts']['outgoing_relation_type'] = len(outgoing_rels)
                # Compter par type
                for rel in outgoing_rels:
                    rel_type = rel.get('relationType', 'unknown')
                    diagnostic['relation_type_counts'][rel_type] = diagnostic['relation_type_counts'].get(rel_type, 0) + 1

            if incoming_rels:
                diagnostic['relation_counts']['incoming_relation_type'] = len(incoming_rels)
                # Compter par type
                for rel in incoming_rels:
                    rel_type = rel.get('relationType', 'unknown')
                    diagnostic['relation_type_counts'][f"~{rel_type}"] = diagnostic['relation_type_counts'].get(f"~{rel_type}", 0) + 1

        # Analyser les problèmes potentiels
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
        """
        ✅ VERSION ULTRA-ROBUSTE : Recherche multi-critères
        - Par UID (source/target)
        - Par nom exact (avec/sans extension)
        - Par sourceName/targetName
        - Par sourcePath/targetPath
        - Par expressions régulières
        """
        if not uid or not self.dgraph_connector:
            logger.error("❌ Pas d'UID ou pas de connecteur")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 RÉCUPÉRATION RELATIONS TYPE RELATION (ROBUSTE)")
        logger.info(f"  UID central: {uid}")
        logger.info(f"{'='*70}")

        # ✅ ÉTAPE 1 : Récupérer TOUS les identifiants possibles du nœud
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
        node_label = node_data.get('label', '')
        node_id = node_data.get('id', '')

        # ✅ Créer TOUTES les variantes possibles
        search_variants = set()

        # Variantes du nom
        if node_name:
            search_variants.add(node_name)  # Ex: "main_window.py"
            search_variants.add(os.path.basename(node_name))  # Ex: "main_window.py"
            name_no_ext = os.path.splitext(node_name)[0]  # Ex: "main_window"
            search_variants.add(name_no_ext)
            search_variants.add(os.path.basename(name_no_ext))

        # Variantes du path
        if node_path:
            search_variants.add(node_path)
            search_variants.add(os.path.basename(node_path))
            path_no_ext = os.path.splitext(node_path)[0]
            search_variants.add(path_no_ext)

        # Autres identifiants
        if node_label:
            search_variants.add(node_label)
        if node_id:
            search_variants.add(node_id)

        # Filtrer les valeurs vides
        search_variants = {v for v in search_variants if v and v.strip()}

        logger.info(f"📋 Identifiants du nœud à rechercher:")
        for variant in sorted(search_variants):
            logger.info(f"   • {variant}")

        if not search_variants:
            logger.error("❌ Aucun identifiant valide pour ce nœud")
            return []

        # ✅ ÉTAPE 2 : Construction de la requête Dgraph MULTI-CRITÈRES

        # Filtres par UID
        uid_filters = f"uid_in(source, {uid}) OR uid_in(target, {uid})"

        # Filtres par nom/path (exact match)
        exact_filters = []
        for variant in search_variants:
            escaped = variant.replace('"', '\\"')
            exact_filters.extend([
                f'eq(sourceName, "{escaped}")',
                f'eq(targetName, "{escaped}")',
                f'eq(sourcePath, "{escaped}")',
                f'eq(targetPath, "{escaped}")'
            ])

        # Filtres par regex (pour les variantes partielles)
        regex_filters = []
        for variant in search_variants:
            # Échapper les caractères spéciaux regex
            escaped_regex = variant.replace('.', r'\.').replace('_', r'\_')
            regex_filters.extend([
                f'regexp(sourceName, /{escaped_regex}/)',
                f'regexp(targetName, /{escaped_regex}/)',
                f'regexp(sourcePath, /{escaped_regex}/)',
                f'regexp(targetPath, /{escaped_regex}/)'
            ])

        # Combiner tous les filtres
        exact_filter_str = " OR ".join(exact_filters)
        regex_filter_str = " OR ".join(regex_filters)

        combined_filter = f"""
        {uid_filters} OR 
        ({exact_filter_str}) OR 
        ({regex_filter_str})
        """

        # ✅ ÉTAPE 3 : Requête unifiée
        unified_query = f"""
        {{
          all_relations(func: type(Relation)) @filter(
            {combined_filter}
          ) {{
            uid
            relationType
            category
            line
            intraFile

            # Métadonnées complètes
            sourceName
            sourceDescription
            sourcePath
            sourceType

            targetName
            targetDescription
            targetPath
            targetType

            # Références UIDs (peuvent être null)
            source {{
              uid
              name
              path
              label
              nodeType
            }}

            target {{
              uid
              name
              path
              label
              nodeType
            }}
          }}
        }}
        """

        logger.info(f"🔍 Exécution requête unifiée...")

        result = self._execute_dgraph_query(unified_query)

        if not result or 'all_relations' not in result:
            logger.warning("⚠️ Aucune relation trouvée")
            return []

        raw_relations = result['all_relations']
        logger.info(f"📦 {len(raw_relations)} relations brutes récupérées")

        # ✅ ÉTAPE 4 : Traitement et validation
        relations_list = []
        seen_keys = set()

        for rel in raw_relations:
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

            # ✅ VALIDATION CRITIQUE : Vérifier pertinence
            is_source_match = False
            is_target_match = False

            # Vérifier si source correspond à notre nœud
            if source_uid_rel == uid:
                is_source_match = True
            else:
                source_basename = os.path.basename(source_name) if source_name else ''
                source_no_ext = os.path.splitext(source_basename)[0]
                if source_basename in search_variants or source_no_ext in search_variants:
                    is_source_match = True

            # Vérifier si target correspond à notre nœud
            if target_uid_rel == uid:
                is_target_match = True
            else:
                target_basename = os.path.basename(target_name) if target_name else ''
                target_no_ext = os.path.splitext(target_basename)[0]
                if target_basename in search_variants or target_no_ext in search_variants:
                    is_target_match = True

            # ✅ La relation doit concerner notre nœud (source OU target)
            if not (is_source_match or is_target_match):
                continue
            
            # Normalisation DOUCE des noms (garde l'extension)
            source_name_norm = os.path.basename(source_name).strip() if source_name else ''
            target_name_norm = os.path.basename(target_name).strip() if target_name else ''

            # ✅ Si un des deux noms manque, utiliser l'identifiant du nœud central
            if not source_name_norm:
                source_name_norm = node_name or f"Node_{uid[-8:]}"
            if not target_name_norm:
                target_name_norm = node_name or f"Node_{uid[-8:]}"

            # Ignorer auto-références
            if source_name_norm == target_name_norm:
                continue
            
            # ✅ Déduplication
            relation_type = rel.get('relationType', 'relation')
            unique_key = (
                source_uid_rel or source_name_norm,
                target_uid_rel or target_name_norm,
                relation_type
            )

            if unique_key in seen_keys:
                continue
            
            seen_keys.add(unique_key)

            # ✅ Créer la relation
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

        # ✅ ÉTAPE 5 : Diagnostic final
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 RÉSULTAT FINAL : {len(relations_list)} relations uniques")
        logger.info(f"{'='*70}")

        if not relations_list:
            logger.warning("⚠️ AUCUNE RELATION VALIDE après filtrage")
            logger.warning(f"   Relations brutes : {len(raw_relations)}")
            logger.warning(f"   Possible cause : Les noms dans Dgraph ne correspondent pas")

            # Afficher échantillon des relations brutes
            logger.warning(f"\n🔬 Échantillon des relations brutes:")
            for idx, rel in enumerate(raw_relations[:3]):
                logger.warning(f"\n  Relation {idx + 1}:")
                logger.warning(f"    UID: {rel.get('uid')}")
                logger.warning(f"    Type: {rel.get('relationType')}")
                logger.warning(f"    sourceName: {rel.get('sourceName', 'N/A')}")
                logger.warning(f"    targetName: {rel.get('targetName', 'N/A')}")
                logger.warning(f"    source.uid: {rel.get('source', {}).get('uid', 'N/A')}")
                logger.warning(f"    target.uid: {rel.get('target', {}).get('uid', 'N/A')}")
        else:
            # Log échantillon des relations valides
            for idx, rel in enumerate(relations_list[:5]):
                logger.info(f"  {idx+1}. {rel['source']} --[{rel['relation_type']}]--> {rel['target']}")
                logger.info(f"      source_uid: {rel['source_uid']}")
                logger.info(f"      target_uid: {rel['target_uid']}")

            if len(relations_list) > 5:
                logger.info(f"  ... et {len(relations_list) - 5} autres")

        return relations_list
    
    def _get_relation_type_relations_cached(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION AVEC CACHE : Évite de refaire la même requête
        """
        # Vérifier cache
        cache_key = f"relations_unified_{uid}"
        cached_data = self.query_cache.get(cache_key)

        if cached_data:
            logger.info(f"✅ Relations récupérées depuis cache: {len(cached_data)} relations")
            return cached_data

        # Sinon, exécuter la requête
        relations = self._get_relation_type_relations(uid)

        # Mettre en cache
        if relations:
            self.query_cache.set(cache_key, relations)

        return relations

    def _draw_graph(self):
        """✅ VERSION AMÉLIORÉE : Dessine avec support sélections multiples"""
        if not self.current_graph:
            return

        G = self.current_graph
        num_nodes = len(G.nodes())

        # ✅ DÉTECTER LE MODE SÉLECTION MULTIPLE
        selected_nodes = [node for node in G.nodes() if G.nodes[node].get('selected', False)]
        is_multi_selection = len(selected_nodes) > 1

        logger.info(f"🎨 Rendu graphique : {num_nodes} nœuds, multi-sélection={is_multi_selection}")

        # Préparer figure
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        self.graph_data = {
            'G': G, 'ax': ax, 'pos': {}, 'edges': [], 'edge_colors': [],
            'node_colors': [], 'node_sizes': [], 'labels': {}, 'edge_labels': {},
            'num_nodes': num_nodes,
            'min_distance': 0.3 if num_nodes <= 20 else 0.2 if num_nodes <= 50 else 0.15,
            'is_multi_selection': is_multi_selection,
            'selected_nodes': selected_nodes
        }
        data = self.graph_data

        # ✅ LAYOUT ADAPTÉ POUR SÉLECTIONS MULTIPLES
        if is_multi_selection:
            if num_nodes <= 10:
                # Disposition circulaire pour petit graphe multi-sélection
                pos = nx.circular_layout(G, scale=2.5)
            elif num_nodes <= 20:
                # Disposition spring avec nœuds sélectionnés au centre
                pos = nx.spring_layout(G, k=2.0, iterations=500, seed=42, scale=3.0)
                # Ajuster positions des nœuds sélectionnés
                self._adjust_selected_nodes_positions(pos, selected_nodes)
            else:
                pos = nx.kamada_kawai_layout(G, scale=3.5)
        else:
            # Layout standard pour sélection simple
            if num_nodes > 100:
                pos = nx.kamada_kawai_layout(G, scale=3.0)
            elif num_nodes > 50:
                pos = nx.spring_layout(G, k=2.0, iterations=300, seed=42, scale=3.0)
            else:
                k_value = 3.0 / (num_nodes ** 0.4) if num_nodes > 0 else 1.0
                pos = nx.spring_layout(G, k=k_value, iterations=300, seed=42, scale=3.0)

        pos = self._apply_collision_avoidance(G, pos, num_nodes)
        data['pos'] = {node: list(coord) for node, coord in pos.items()}

        # ✅ PRÉPARER ARÊTES avec couleurs spéciales pour multi-sélection
        for u, v, edge_data in G.edges(data=True):
            data['edges'].append((u, v))
            edge_color = edge_data.get('color', '#CCCCCC')
            relation_type = edge_data.get('relation_type', '')

            if is_multi_selection:
                # Couleurs spéciales pour relations entre sélectionnés
                if u in selected_nodes and v in selected_nodes:
                    edge_color = '#4CAF50'  # Vert pour relations directes entre sélectionnés
                elif u in selected_nodes or v in selected_nodes:
                    edge_color = '#FF9800'  # Orange pour relations vers/depuis sélectionnés
                else:
                    edge_color = '#E0E0E0'  # Gris clair pour autres relations

            data['edge_colors'].append(edge_color)

        # ✅ PRÉPARER NŒUDS avec styles distincts
        for node in G.nodes():
            node_type = G.nodes[node].get('node_type', 'unknown')
            level = G.nodes[node].get('level', 0)
            is_selected = G.nodes[node].get('selected', False)

            # Couleurs et tailles selon le statut
            if is_multi_selection and is_selected:
                # Nœuds sélectionnés en mode multi : rouge/rose vif
                data['node_colors'].append('#E91E63')
                data['node_sizes'].append(int((500 if num_nodes <= 20 else 400) * 1.3))
            elif node == self.central_node:
                # Nœud central (mode simple)
                data['node_colors'].append('#8B2E1F')
                data['node_sizes'].append(int((400 if num_nodes <= 20 else 300) * 1.4))
            else:
                # Nœuds normaux
                base_color = self._get_color_for_node(node_type, level)
                # Atténuer si pas connecté aux sélectionnés
                if is_multi_selection and not self._is_connected_to_selected(G, node, selected_nodes):
                    data['node_colors'].append('#BDBDBD')  # Gris pour nœuds non connectés
                else:
                    data['node_colors'].append(base_color)

                data['node_sizes'].append(350 if num_nodes <= 20 else 250 if num_nodes <= 50 else 150)

            data['labels'][node] = node

        # Labels arêtes
        data['edge_labels'] = {(u, v): d.get('label', '') for u, v, d in G.edges(data=True)}

        # ✅ DESSINER ARÊTES avec épaisseurs variables
        curvature = 0.1 if num_nodes <= 15 else 0.05

        if data['edges']:
            # Calculer épaisseurs selon importance
            edge_widths = []
            for i, (u, v) in enumerate(data['edges']):
                if is_multi_selection and u in selected_nodes and v in selected_nodes:
                    edge_widths.append(3.0)  # Plus épais pour relations entre sélectionnés
                elif is_multi_selection and (u in selected_nodes or v in selected_nodes):
                    edge_widths.append(2.0)  # Moyen pour relations avec sélectionnés
                else:
                    edge_widths.append(1.0)  # Normal pour autres

            nx.draw_networkx_edges(G, pos, edgelist=data['edges'], ax=ax, 
                                   edge_color=data['edge_colors'],
                                   width=edge_widths,
                                   alpha=0.8, arrows=True,
                                   arrowsize=15 if num_nodes <= 50 else 12,
                                   connectionstyle=f'arc3,rad={curvature}')

        # Dessiner nœuds avec bordures distinctives
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=data['node_colors'],
                               node_size=data['node_sizes'], alpha=0.9,
                               edgecolors='#2C2C2C',
                               linewidths=4.0 if is_multi_selection else 2.5)

        # ✅ CERCLES DISTINCTIFS pour sélections multiples
        if is_multi_selection:
            for node in selected_nodes:
                if node in pos:
                    from matplotlib.patches import Circle
                    circle = Circle(pos[node], 0.20, color='#E91E63', fill=False,
                                    linewidth=3, alpha=0.9, linestyle='--')
                    ax.add_patch(circle)

        # Labels nœuds avec couleurs adaptées
        if data['labels']:
            font_size = 9 if num_nodes <= 15 else 7 if num_nodes <= 30 else 6
            font_colors = []

            for node in data['labels'].keys():
                if is_multi_selection and G.nodes[node].get('selected', False):
                    font_colors.append('#FFFFFF')  # Blanc pour nœuds sélectionnés
                else:
                    font_colors.append('#000000')  # Noir standard

            # Note: networkx ne supporte pas font_color par nœud, on utilise une couleur globale
            nx.draw_networkx_labels(G, pos, data['labels'], ax=ax,
                                    font_size=font_size,
                                    font_weight='bold', font_color='#000000',
                                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                              edgecolor='none', alpha=0.85))

        # Labels arêtes si petit graphe
        if data['edge_labels'] and num_nodes <= 25:
            nx.draw_networkx_edge_labels(G, pos, data['edge_labels'], ax=ax,
                                        font_size=6 if num_nodes > 15 else 7,
                                        font_color='#444444',
                                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                                  edgecolor='none', alpha=0.7))

        # ✅ TITRE adapté au mode
        if is_multi_selection:
            if len(data['edges']) > 0:
                ax.set_title(f"Relations entre {len(selected_nodes)} éléments sélectionnés",
                             fontsize=12, fontweight='bold', color='#E91E63', pad=20)
            else:
                ax.set_title(f"{len(selected_nodes)} éléments sélectionnés (aucune relation directe)",
                             fontsize=12, fontweight='bold', color='#FF9800', pad=20)

        # Détails nœud sélectionné
        if self.selected_node:
            self._show_node_details_in_graph(self.selected_node, G)

        ax.axis('off')
        ax.margins(0.12 if num_nodes <= 50 else 0.08)
        self.canvas.draw_idle()

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


    def _update_legend(self):
    # Nettoyer la légende actuelle
        while self.legend_layout.count() > 0:
            child = self.legend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
        if not self.current_graph:
            return
    
        # Statistiques globales
        total_nodes = len(self.current_graph.nodes())
        total_edges = len(self.current_graph.edges())
    
        stats_label = QtWidgets.QLabel(f"📊 {total_nodes} nœuds, {total_edges} relations")
        stats_label.setStyleSheet("color: #000; font-size: 12px; font-weight: bold; padding: 4px 8px;")
        self.legend_layout.addWidget(stats_label)
    
        # Espacement
        sep = QtWidgets.QLabel(" | ")
        sep.setStyleSheet("color: #999; font-size: 12px; padding: 0 4px;")
        self.legend_layout.addWidget(sep)
    
        # Récupérer tous les types de relations utilisés dans le graphe
        relation_types = defaultdict(int)
        for _, _, d in self.current_graph.edges(data=True):
            rel_type = d.get('relation_type', 'unknown')
            relation_types[rel_type] += 1
    
        # Trier par fréquence
        sorted_relations = sorted(relation_types.items(), key=lambda x: -x[1])
    
        # Afficher chaque type de relation avec un petit tiret coloré
        for rel_type, count in sorted_relations:
            color = self._get_color_for_type(rel_type)
    
            # Conteneur horizontal
            item_widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(item_widget)
            layout.setContentsMargins(5, 0, 5, 0)
            layout.setSpacing(6)
    
            # Tiret coloré (ligne horizontale)
            color_bar = QtWidgets.QFrame()
            color_bar.setFixedSize(25, 4)
            color_bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            layout.addWidget(color_bar)
    
            # Nom du type de relation
            label = QtWidgets.QLabel(f"{rel_type} ({count})")
            label.setStyleSheet("color: #000; font-size: 12px;")
            layout.addWidget(label)
    
            self.legend_layout.addWidget(item_widget)
    
        self.legend_layout.addStretch()


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
        self._update_legend()
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
            self._update_legend()

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
        self._update_legend()

        logger.info(f"✅ Graphe multi-sélection généré avec {len(self.current_graph.nodes)} nœuds")
        logger.info(f"✅ {len(filtered_relations)} relations RÉELLES affichées")
        logger.info(f"{'='*70}\n")

    def closeEvent(self, event):
        """Fermeture propre."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)