# relation_import_widget.py - Version avec Cache et Barre de Progression
import os
import json
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QColor

import qtawesome as qta
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.dgraph_connector import LirisDgraphConnector
from utils.logger import logger


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
            "function": ('fa5s.cube', primary),
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
        self.current_central_uid = None
        self.current_central_name = None
        
        # Système de cache
        self.query_cache = QueryCache(ttl_seconds=600)  # 10 minutes
        
        # Cache pour les mappings UID
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"

        self.setStyleSheet(self._get_stylesheet())
        self._init_ui()
        self._load_projects_list()
    
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
    
    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """Construit un graphe NetworkX propre en éliminant tous les doublons."""
        G = nx.DiGraph()

        nodes_registry = {}
        edges_registry = {}

        # Phase 1: Collecter tous les nœuds uniques
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))

            if not source or not target:
                continue
            
            if source not in nodes_registry:
                if rel.get('is_analyzed', False):
                    nodes_registry[source] = 'analyzed'
                else:
                    nodes_registry[source] = 'dependency'
            else:
                if rel.get('is_analyzed', False) and nodes_registry[source] != 'analyzed':
                    nodes_registry[source] = 'analyzed'

            if target not in nodes_registry:
                nodes_registry[target] = 'dependency'

        # Phase 2: Ajouter tous les nœuds uniques au graphe
        for node_name, node_type in nodes_registry.items():
            G.add_node(node_name, node_type=node_type)

        # Phase 3: Collecter les arêtes uniques
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

        # Phase 4: Ajouter les arêtes au graphe
        for (source, target), rel_types in edges_registry.items():
            primary_type = rel_types[0]

            if len(rel_types) > 1:
                combined_label = f"{primary_type} (+{len(rel_types)-1})"
            else:
                combined_label = primary_type

            G.add_edge(
                source, 
                target,
                color=self._get_color_for_type(primary_type),
                relation_type=primary_type,
                all_types=rel_types,
                label=combined_label
            )

        # Phase 5: Supprimer les nœuds isolés
        isolated_nodes = list(nx.isolates(G))
        if isolated_nodes:
            logger.info(f"Suppression de {len(isolated_nodes)} nœud(s) isolé(s)")
            G.remove_nodes_from(isolated_nodes)

        logger.info(f"Graphe construit: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")

        return G

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
        """Récupère les détails complets d'un nœud avec cache."""
        if not uid:
            return {}
        
        cache_key = f"node_details_{uid}"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        logger.info(f"Récupération détails pour UID: {uid}")
        
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            level
            nodeType
            
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
            }}
            
            children: ~parents {{
              uid
              name
              label
            }}
            
            clusters {{
              uid
              name
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'node' in result and result['node']:
            node = result['node'][0]
            self.query_cache.set(cache_key, node)
            logger.info(f"Nœud trouvé: {node.get('name', 'N/A')} avec {len(node.get('outgoing_relations', []))} relations sortantes")
            return node
        
        logger.warning(f"Aucun nœud trouvé pour UID: {uid}")
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
        """Niveau 1: TOUTES les relations directes avec cache."""
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

        # 1. Relations sortantes CUSTOM
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

        # 2. Relations PARSÉES
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

        # 3. Relations entrantes CUSTOM
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

        # 4. HIÉRARCHIE - Parents
        self._update_progress(85, "Hiérarchie...")
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

        # 5. HIÉRARCHIE - Enfants
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

        # 6. Relations type(Relation)
        self._update_progress(95, "Relations additionnelles...")
        query = f"""
        {{
          relations(func: type(Relation)) @filter(uid_in(source, {uid}) OR uid_in(target, {uid})) {{
            uid
            relationType
            source {{
              uid
              name
              label
            }}
            target {{
              uid
              name
              label
            }}
          }}
        }}
        """
        result = self._execute_dgraph_query(query)
        
        if result and 'relations' in result:
            for rel in result['relations']:
                source_node = rel.get('source', {})
                target_node = rel.get('target', {})
                
                source_name = self.normalize_node_name(
                    source_node.get('name') or source_node.get('label', '')
                )
                target_name = self.normalize_node_name(
                    target_node.get('name') or target_node.get('label', '')
                )
                
                if source_name and target_name:
                    relations.append({
                        'source': source_name,
                        'target': target_name,
                        'relation_type': rel.get('relationType', 'relation'),
                        'category': 'custom',
                        'is_analyzed': True
                    })

        self.query_cache.set(cache_key, relations)
        self._hide_progress()
        
        logger.info(f"Niveau 1: {len(relations)} relations trouvées pour {central_name}")
        return relations

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

    def _get_level_2_relations(self, uid: str) -> List[Dict]:
        """Niveau 2: Niveau 1 + relations des nœuds connectés."""
        if not uid or not self.current_central_name:
            return []
        
        level1_relations = self._get_level_1_relations(uid)
        
        connected_names = set()
        for rel in level1_relations:
            connected_names.add(rel['source'])
            connected_names.add(rel['target'])
        
        connected_names.discard(self.current_central_name)
        
        connected_uids_names = set()
        for name in connected_names:
            node_uid = self._get_node_uid_by_name(name)
            if node_uid:
                connected_uids_names.add((node_uid, name))
        
        all_relations = list(level1_relations)
        
        original_central_uid = self.current_central_uid
        original_central_name = self.current_central_name
        
        total = len(connected_uids_names)
        for idx, (connected_uid, node_name) in enumerate(connected_uids_names):
            progress = int(((idx + 1) / total) * 100)
            self._show_progress(f"Niveau 2: {idx+1}/{total}", progress)
            
            self.current_central_uid = connected_uid
            self.current_central_name = node_name
            connected_rels = self._get_level_1_relations(connected_uid)
            
            for rel in connected_rels:
                rel['is_analyzed'] = False
            all_relations.extend(connected_rels)
        
        self.current_central_uid = original_central_uid
        self.current_central_name = original_central_name
        self._hide_progress()
        
        logger.info(f"Niveau 2: {len(all_relations)} relations trouvées")
        return all_relations

    def _get_level_3_relations(self, uid: str) -> List[Dict]:
        """Niveau 3: Niveau 2 + relations des relations."""
        if not uid or not self.current_central_name:
            return []
        
        level_2_relations = self._get_level_2_relations(uid)
        
        all_node_names = set()
        for rel in level_2_relations:
            all_node_names.add(rel['source'])
            all_node_names.add(rel['target'])
        
        level2_uids_names = set()
        for node_name in all_node_names:
            node_uid = self._get_node_uid_by_name(node_name)
            if node_uid:
                level2_uids_names.add((node_uid, node_name))
        
        all_relations = list(level_2_relations)
        
        original_central_uid = self.current_central_uid
        original_central_name = self.current_central_name
        
        total = len(level2_uids_names)
        for idx, (node_uid, node_name) in enumerate(level2_uids_names):
            if node_name == self.current_central_name:
                continue
            
            progress = int(((idx + 1) / total) * 100)
            self._show_progress(f"Niveau 3: {idx+1}/{total}", progress)
            
            self.current_central_uid = node_uid
            self.current_central_name = node_name
            connected_rels = self._get_level_1_relations(node_uid)
            
            for rel in connected_rels:
                rel['is_analyzed'] = False
            all_relations.extend(connected_rels)
        
        self.current_central_uid = original_central_uid
        self.current_central_name = original_central_name
        self._hide_progress()
        
        logger.info(f"Niveau 3: {len(all_relations)} relations trouvées")
        return all_relations

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
        """Gère le changement de niveau de profondeur."""
        level = self.level_combo.itemData(index)

        if level == 0:  # Global
            if not self.current_project_data:
                self._show_empty_graph("Sélectionnez un projet")
                return
            relations_list = self._get_global_relations()
        else:
            if not self.current_central_uid:
                self._show_empty_graph("Sélectionnez un nœud dans l'arbre")
                return
            
            if level == 1:
                relations_list = self._get_level_1_relations(self.current_central_uid)
            elif level == 2:
                relations_list = self._get_level_2_relations(self.current_central_uid)
            elif level == 3:
                relations_list = self._get_level_3_relations(self.current_central_uid)
            else:
                relations_list = []

        # Mettre à jour les relations courantes
        self.current_relations = relations_list

        # Réinitialiser les relations masquées
        self.hidden_relations.clear()

        # Effacer complètement la figure avant de redessiner
        self.figure.clear()

        # Reconstruire et redessiner le graphe
        G = self._build_clean_graph(relations_list)
        self.current_graph = G

        self._draw_graph(G)
        
        # Message de statut
        level_names = {0: "global", 1: "directes", 2: "niveau 2", 3: "niveau 3"}
        self._update_status(f"Niveau {level} ({level_names.get(level, '')}): {len(relations_list)} relations affichées")

    def _show_empty_graph(self, message: str):
        """Affiche un message dans le graphe vide."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, message, ha='center', va='center', 
               color='#999999', fontsize=12, style='italic')
        ax.axis('off')
        self.canvas.draw()

    def _show_progress(self, message: str, value: int):
        """Affiche la barre de progression."""
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
        """Stylesheet sobre moderne."""
        return f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: {self.secondary_color}; }}
        QPushButton:disabled {{ background-color: #CCCCCC; color: #666666; }}
        QComboBox {{
            padding: 8px 12px;
            border: 2px solid #E0E0E0;
            border-radius: 6px;
            background-color: #FFFFFF;
            font-size: 13px;
            font-weight: 500;
            color: {self.text_color};
        }}
        QComboBox:focus {{ 
            border: 2px solid {self.primary_color}; 
            background-color: #FAFAFA;
        }}
        QTreeWidget {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            background-color: white;
            padding: 3px;
        }}
        QTreeWidget::item {{ padding: 4px; }}
        QTreeWidget::item:selected {{
            background-color: #E0E0E0;
            color: #000000;
        }}
        QProgressBar {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            text-align: center;
            background-color: #FFFFFF;
            padding: 1px;
            height: 20px;
            font-size: 10px;
            font-weight: 500;
        }}
        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 3px;
        }}
        """
    
    def _init_ui(self):
        """Interface unifiée: arbre à gauche, graphe à droite."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
    
        # HEADER: Sélection du projet + Progress Bar + Cache Info
        header_layout = QtWidgets.QHBoxLayout()
        
        proj_label = QtWidgets.QLabel("Projet:")
        proj_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        header_layout.addWidget(proj_label)
        
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        header_layout.addWidget(self.project_combo)
        
        # Bouton pour vider le cache
        self.clear_cache_btn = QtWidgets.QPushButton(qta.icon('fa5s.trash', color='white'), " Vider Cache")
        self.clear_cache_btn.setMaximumWidth(120)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        header_layout.addWidget(self.clear_cache_btn)
        
        header_layout.addStretch()
        
        # Label d'info cache
        self.cache_info_label = QtWidgets.QLabel(self.query_cache.get_stats())
        self.cache_info_label.setStyleSheet("font-size: 10px; color: #666666;")
        header_layout.addWidget(self.cache_info_label)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximumWidth(250)
        self.progress_bar.setVisible(False)
        header_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(header_layout)
    
        # SPLITTER: Arbre gauche | Graph droite
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # GAUCHE: Arbre
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        tree_label = QtWidgets.QLabel("Structure du Projet")
        tree_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        left_layout.addWidget(tree_label)
        
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabel("Éléments")
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree_widget.setMinimumWidth(250)
        left_layout.addWidget(self.tree_widget)
        
        splitter.addWidget(left_widget)
    
        # DROITE: Graph + Toolbar
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar avec combo niveau
        toolbar_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel("Niveau:")
        level_label.setStyleSheet("font-weight: 600; font-size: 11px;")
        toolbar_layout.addWidget(level_label)
        
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.setMinimumWidth(180)
        self.level_combo.addItem(qta.icon('fa5s.globe', color=self.primary_color), "Global: Tout le projet", 0)
        self.level_combo.addItem(qta.icon('fa5s.layer-group', color=self.primary_color), "Niveau 1: Relations directes", 1)
        self.level_combo.addItem(qta.icon('fa5s.sitemap', color=self.primary_color), "Niveau 2: Relations direct + indirectes", 2)
        #self.level_combo.addItem(qta.icon('fa5s.project-diagram', color=self.primary_color), "Niveau 3: avec les enfants des enfants ", 3)
        self.level_combo.setCurrentIndex(1)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar_layout.addWidget(self.level_combo)
        
        toolbar_layout.addStretch()
    
        right_layout.addLayout(toolbar_layout)
    
        # Canvas du graphe
        self.figure = Figure(figsize=(10, 8), facecolor='white', tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: white; border: 1px solid #E0E0E0; border-radius: 4px;")
        right_layout.addWidget(self.canvas)
    
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 800])
    
        main_layout.addWidget(splitter)

    def _clear_cache(self):
        """Vide le cache et met à jour l'interface."""
        self.query_cache.clear()
        self._update_cache_info()
        self._update_status("Cache vidé")
        QtWidgets.QMessageBox.information(self, "Cache", "Le cache a été vidé avec succès!")
    
    def _update_cache_info(self):
        """Met à jour l'affichage des infos du cache."""
        self.cache_info_label.setText(self.query_cache.get_stats())

    def _update_status(self, message):
        """Met à jour le statut (logs uniquement)."""
        logger.info(message)
        QtWidgets.QApplication.processEvents()
    
    def _draw_graph(self, G: nx.DiGraph):
        """Dessine le graphe NetworkX avec légende compacte et info nœud interactif."""
        self.figure.clear()

        # Layout optimisé: graphe principal + légende compacte en haut à droite
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

        # Disposition avec meilleure séparation
        if num_nodes > 100:
            pos = nx.kamada_kawai_layout(G, scale=3.0)
        elif num_nodes > 50:
            pos = nx.spring_layout(G, k=2.0, iterations=300, seed=42, scale=3.0)
        else:
            k_value = 3.0 / (num_nodes ** 0.4)
            pos = nx.spring_layout(G, k=k_value, iterations=300, seed=42, scale=3.0)

        # Appliquer collision avoidance
        pos = self._apply_collision_avoidance(G, pos, num_nodes)

        # Arêtes
        edges = list(G.edges(data=True))
        edge_colors = [d.get('color', '#CCCCCC') for _, _, d in edges]
        edge_types_seen = {}

        curvature = 0.1 if num_nodes <= 15 else 0.05
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors, 
                             width=1.5 if num_nodes > 50 else 2.0, 
                             alpha=0.6, arrows=True, 
                             arrowsize=10 if num_nodes > 50 else 14, 
                             connectionstyle=f'arc3,rad={curvature}')

        for _, _, d in edges:
            rel_type = d.get('relation_type', 'unknown')
            color = d.get('color', '#CCCCCC')
            if rel_type not in edge_types_seen:
                edge_types_seen[rel_type] = color

        # Étiquettes des arêtes (seulement pour petits graphes)
        if num_nodes <= 30:
            edge_labels = {(u, v): d.get('label', '') for u, v, d in edges}
            nx.draw_networkx_edge_labels(G, pos, edge_labels, ax=ax, 
                                        font_size=6 if num_nodes > 15 else 7, 
                                        font_color='#444444',
                                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                                edgecolor='none', alpha=0.7))
        else:
            edge_labels = {}

        # Nœuds
        node_colors = []
        for n in G.nodes():
            node_type = G.nodes[n].get('node_type', 'dependency')
            if node_type == 'analyzed':
                node_colors.append(self.primary_color)
            elif node_type == 'central':
                node_colors.append('#8B2E1F')
            else:
                node_colors.append('#5CAD56')

        node_sizes = []
        for n in G.nodes():
            base_size = 1500 if num_nodes <= 20 else 1000 if num_nodes <= 50 else 600 if num_nodes <= 100 else 400
            node_type = G.nodes[n].get('node_type', 'dependency')
            if node_type in ['analyzed', 'central']:
                node_sizes.append(base_size * 1.3)
            else:
                node_sizes.append(base_size)

        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, 
                             node_size=node_sizes, alpha=0.9, 
                             edgecolors='#2C2C2C', linewidths=2.5 if num_nodes <= 50 else 1.5)

        # Labels des nœuds
        labels = {}
        for n in G.nodes():
            node_type = G.nodes[n].get('node_type', 'dependency')

            if node_type in ['analyzed', 'central']:
                if num_nodes <= 30:
                    max_len = 20
                elif num_nodes <= 100:
                    max_len = 15
                else:
                    max_len = 12
                labels[n] = n[:max_len] + ".." if len(n) > max_len else n

            elif num_nodes <= 50:
                if num_nodes <= 15:
                    max_len = 20
                elif num_nodes <= 30:
                    max_len = 15
                else:
                    max_len = 10
                labels[n] = n[:max_len] + ".." if len(n) > max_len else n

        # Adapter la taille de police
        if num_nodes <= 15:
            font_size = 9
        elif num_nodes <= 30:
            font_size = 8
        elif num_nodes <= 50:
            font_size = 7
        elif num_nodes <= 100:
            font_size = 6
        else:
            font_size = 5

        if labels:
            nx.draw_networkx_labels(G, pos, labels, ax=ax, 
                                  font_size=font_size, 
                                  font_weight='bold', 
                                  font_color='#000000',
                                  bbox=dict(boxstyle='round,pad=0.3', 
                                          facecolor='white', 
                                          edgecolor='none', 
                                          alpha=0.85))

        # LÉGENDE COMPACTE EN HAUT À DROITE
        if edge_types_seen:
            from matplotlib.lines import Line2D
            legend_elements = []
            sorted_types = sorted(edge_types_seen.items())

            for rel_type, color in sorted_types[:8]:  # Limiter à 8 types max
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

            # Positionner la légende dans le coin
            legend.set_bbox_to_anchor((0.98, 0.98))

        ax.axis('off')
        ax.margins(0.12 if num_nodes <= 50 else 0.08)

        # Configurer l'interactivité
        self._setup_interactive_graph(ax, G, pos, edges, edge_colors, 
                                      edge_labels, labels, node_colors, 
                                      node_sizes, num_nodes)

        # Zone de texte pour les détails (initialement vide)
        self.info_text_obj = None

        self.canvas.draw()

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
            
            seen_uids = set()
            for ws in result['q']:
                uid = ws.get('uid')
                if uid and uid not in seen_uids:
                    seen_uids.add(uid)
                    name = ws.get('name', 'Projet')
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
            self._show_empty_graph("Sélectionnez un nœud dans l'arbre\npour afficher ses relations")
    
    def _build_project_tree(self):
        """Construit l'arborescence du projet."""
        self.tree_widget.clear()
        if not self.current_project_data:
            return
        
        cm = self.current_project_data.get('clusterManagement', {})
        seen_uids = set()
        
        for cluster in cm.get('clusters', []):
            cluster_uid = cluster.get('uid')
            if cluster_uid in seen_uids:
                continue
            seen_uids.add(cluster_uid)
            
            cluster_name = cluster.get('name', 'Cluster')
            cluster_path = cluster.get('path', cluster_name.replace(' ', '_').lower())
            cluster_item = TaxonomyItem(self.tree_widget, cluster_name, "folder", cluster, 0)
            
            self._add_labels_to_tree(cluster_item, cluster.get('root_labels', []), 1, cluster_path)
        
        self.tree_widget.expandAll()

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
        """Gère la sélection dans l'arbre."""
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

            logger.info(f"Nœud sélectionné: {self.current_central_name}")

            if not self.current_central_uid:
                logger.error("UID du nœud sélectionné est None/vide!")
                self._show_empty_graph(f"Erreur: UID manquant pour {self.current_central_name}")
                return

            if not self.current_central_name:
                logger.error("Nom du nœud normalisé est None/vide!")
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
        """Détecte le type d'élément."""
        if self._has_extension(item_name):
            return "file"
        node_type = item_data.get('nodeType', '').lower()
        if node_type in ['class', 'function', 'variable']:
            return node_type
        if '()' in item_name or item_name.startswith('def '):
            return "function"
        if item_name.isupper():
            return "variable"
        if item_name[0].isupper() and parent_item.item_type == 'file':
            return "class"
        return "folder"

    def _has_extension(self, filename):
        """Vérifie si le nom a une extension."""
        return '.' in os.path.basename(filename)

    def _get_color_for_type(self, rel_type):
        """Associe une couleur à chaque type de relation."""
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()
        
        color_map = {
            'import': '#FF8C00',
            'from_import': '#FF8C00',
            'require': '#FF8C00',
            'include': '#FF8C00',
            'extends': '#00A65A',
            'heritage': '#00A65A',
            'inherit': '#00A65A',
            'function_call': '#007ACC',
            'method_call': '#007ACC',
            'call': '#007ACC',
            'called_by': '#00B0F0',
            'relation': '#8A2BE2',
            'relation_inverse': '#9370DB',
            'parent': '#2196F3',
            'child': '#4CAF50',
            'belongs_to': '#FF6B6B',
            'uses': '#FFA500',
            'used_by': '#FFD700',
        }
        
        for key, color in color_map.items():
            if key in rel_lower:
                return color
                
        return '#999999'

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
    
    def _on_graph_press(self, event):
        """Gère le clic de la souris pour commencer le drag OU afficher les détails."""
        if not hasattr(self, 'graph_data') or event.inaxes != self.graph_data['ax']:
            return

        if event.xdata is None or event.ydata is None:
            return

        pos = self.graph_data['pos']
        G = self.graph_data['G']

        # Vérifier si un nœud a été cliqué
        clicked_node = None
        for node, coords in pos.items():
            x, y = coords
            dist = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5

            if dist < 0.12:  # Rayon de sélection
                clicked_node = node
                break

        if clicked_node:
            # Clic gauche: drag, Clic droit ou double-clic: afficher détails
            if event.button == 1 and event.dblclick:  # Double-clic gauche
                self._show_node_details_in_graph(clicked_node, G)
            elif event.button == 3:  # Clic droit
                self._show_node_details_in_graph(clicked_node, G)
            elif event.button == 1:  # Clic gauche simple: drag
                self.graph_data['dragging_node'] = clicked_node
                self.graph_data['drag_start'] = (event.xdata, event.ydata)

                from PyQt5.QtGui import QCursor
                from PyQt5.QtCore import Qt
                self.canvas.setCursor(QCursor(Qt.ClosedHandCursor))

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

        # Si double-clic sur une zone vide, masquer les détails
        if event.dblclick and event.button == 1 and self.graph_data.get('dragging_node') is None:
            if self.info_text_obj:
                try:
                    self.info_text_obj.remove()
                except:
                    pass
                self.info_text_obj = None
                self.graph_data['selected_node'] = None
                self.canvas.draw_idle()

        self.graph_data['dragging_node'] = None

        from PyQt5.QtGui import QCursor
        from PyQt5.QtCore import Qt
        self.canvas.setCursor(QCursor(Qt.ArrowCursor))

    def _on_graph_motion(self, event):
        """Gère le mouvement de la souris pour déplacer les nœuds."""
        if not hasattr(self, 'graph_data') or event.inaxes != self.graph_data['ax']:
            return

        dragging_node = self.graph_data.get('dragging_node')

        if dragging_node is None or event.xdata is None or event.ydata is None:
            return

        # Mettre à jour la position du nœud
        self.graph_data['pos'][dragging_node] = [event.xdata, event.ydata]

        # Appliquer la collision avoidance
        self._apply_local_collision_avoidance(dragging_node)

        # Redessiner
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
        """Redessine le graphe avec les positions mises à jour."""
        data = self.graph_data
        ax = data['ax']
        G = data['G']
        pos = data['pos']

        ax.clear()
        ax.set_facecolor('white')

        # Redessiner les arêtes
        edges = data['edges']
        edge_colors = data['edge_colors']
        num_nodes = data['num_nodes']

        curvature = 0.1 if num_nodes <= 15 else 0.05
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                             width=1.5 if num_nodes > 50 else 2.0,
                             alpha=0.6, arrows=True,
                             arrowsize=10 if num_nodes > 50 else 14,
                             connectionstyle=f'arc3,rad={curvature}')

        # Redessiner les nœuds
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=data['node_colors'],
                             node_size=data['node_sizes'], alpha=0.9,
                             edgecolors='#2C2C2C', 
                             linewidths=2.5 if num_nodes <= 50 else 1.5)

        # Redessiner les labels
        if data['labels']:
            font_size = 9 if num_nodes <= 15 else 7 if num_nodes <= 30 else 6
            nx.draw_networkx_labels(G, pos, data['labels'], ax=ax,
                                  font_size=font_size,
                                  font_weight='bold', font_color='#000000',
                                  bbox=dict(boxstyle='round,pad=0.3',
                                          facecolor='white', edgecolor='none', alpha=0.85))

        # Redessiner les labels des arêtes
        if data['edge_labels'] and num_nodes <= 30:
            nx.draw_networkx_edge_labels(G, pos, data['edge_labels'], ax=ax,
                                        font_size=6 if num_nodes > 15 else 7,
                                        font_color='#444444',
                                        bbox=dict(boxstyle='round,pad=0.3',
                                                facecolor='white', edgecolor='none', alpha=0.7))

        # Re-afficher la légende si elle existe
        self._redraw_legend(ax, edges)

        # Re-afficher les détails du nœud si un nœud était sélectionné
        if self.graph_data.get('selected_node'):
            self._show_node_details_in_graph(self.graph_data['selected_node'], G)

        ax.axis('off')
        ax.margins(0.12 if num_nodes <= 50 else 0.08)

        self.canvas.draw_idle()

    def _apply_collision_avoidance(self, G, pos, num_nodes):
        """Applique un algorithme pour éviter la superposition des nœuds."""

        # Distance minimale entre les nœuds (adaptée à la taille du graphe)
        min_distance = 0.3 if num_nodes <= 20 else 0.2 if num_nodes <= 50 else 0.15

        # Nombre d'itérations
        iterations = 50 if num_nodes <= 30 else 30

        for iteration in range(iterations):
            nodes = list(G.nodes())

            for i, node1 in enumerate(nodes):
                x1, y1 = pos[node1]

                # Vérifier la distance avec tous les autres nœuds
                for node2 in nodes[i+1:]:
                    x2, y2 = pos[node2]

                    # Calculer la distance
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx**2 + dy**2) ** 0.5

                    # Si la distance est trop petite, repousser les nœuds
                    if distance < min_distance and distance > 0:
                        # Direction de répulsion
                        angle = (dy / distance) if distance > 0 else 0
                        angle_cos = (dx / distance) if distance > 0 else 1

                        # Force de répulsion inversement proportionnelle à la distance
                        force = (min_distance - distance) / 10

                        # Appliquer la force
                        pos[node1][0] -= force * angle_cos
                        pos[node1][1] -= force * angle
                        pos[node2][0] += force * angle_cos
                        pos[node2][1] += force * angle

            # Réduire progressivement la force
            if iteration % 10 == 0:
                min_distance *= 0.98

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
        """Applique la collision avoidance locale au nœud en déplacement."""
        pos = self.graph_data['pos']
        G = self.graph_data['G']
        min_distance = self.graph_data['min_distance']
    
        x1, y1 = pos[dragging_node]
    
        for node in G.nodes():
            if node == dragging_node:
                continue
            
            x2, y2 = pos[node]
            dx = x2 - x1
            dy = y2 - y1
            distance = (dx**2 + dy**2) ** 0.5
    
            if distance < min_distance and distance > 0.01:
                # Repousser légèrement le nœud statique
                angle_cos = dx / distance
                angle_sin = dy / distance
                force = (min_distance - distance) / 20
    
                pos[node][0] += force * angle_cos
                pos[node][1] += force * angle_sin

    def closeEvent(self, event):
        """Fermeture propre."""
        if self.dgraph_connector:
            self.dgraph_connector.close()
        super().closeEvent(event)