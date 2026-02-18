#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Feature Extractor pour Graph Learner Neural - VERSION CORRIGÉE

✅ AJOUTS:
- Features d'arêtes (edge_type, depth_delta, is_sibling)
- Extraction de relations parent-enfant
- Support pour matrice d'adjacence
"""

import logging
import numpy as np
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class GraphFeatureExtractor:
    """
    Extraction de features structurelles pour le réseau neuronal
    
    ✅ NOUVEAU: Support complet pour relations parent-enfant
    
    Features extraites:
    - Type de nœud (one-hot)
    - Profondeur dans l'arbre (normalisée)
    - Prédicats présents (multi-hot)
    - Fanout (nombre d'enfants, normalisé)
    - 🆕 Relations parent-enfant (pour attention)
    - 🆕 Features d'arêtes (type, delta profondeur, sibling)
    """
    
    def __init__(self, max_depth: int = 10, max_fanout: int = 50):
        self.node_type_vocab: Dict[str, int] = {}
        self.edge_type_vocab: Dict[str, int] = {}
        self.predicate_vocab: Dict[str, int] = {}
        
        self.max_depth = max_depth
        self.max_fanout = max_fanout
        
        # Stats pour normalisation
        self.stats = {
            'depth_mean': 3.0,
            'depth_std': 2.0,
            'fanout_mean': 2.0,
            'fanout_std': 3.0
        }
    
    def build_vocabularies(self, graph_data: Dict[str, Any]):
        """
        Construit les vocabulaires depuis les données du graphe
        
        ✅ AMÉLIORATION: Gère aussi les types d'arêtes
        """
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        logger.info("🔨 Construction des vocabulaires...")
        
        # Types de nœuds
        node_types = set()
        for node in nodes:
            node_type = self._get_node_type(node)
            node_types.add(node_type)
        
        self.node_type_vocab = {t: i for i, t in enumerate(sorted(node_types))}
        
        # 🆕 Types d'arêtes (avec types sémantiques)
        edge_types = {
            'parent_child',      # Parent → Enfant
            'child_parent',      # Enfant → Parent
            'sibling',           # Même parent
            'unknown'            # Type inconnu
        }
        
        for edge in edges:
            edge_type = edge.get('edge_type', edge.get('predicate', 'unknown'))
            edge_types.add(edge_type)
        
        self.edge_type_vocab = {t: i for i, t in enumerate(sorted(edge_types))}
        
        # Prédicats (champs des nœuds)
        all_predicates = set()
        for node in nodes:
            predicates = self._get_node_predicates(node)
            all_predicates.update(predicates)
        
        self.predicate_vocab = {p: i for i, p in enumerate(sorted(all_predicates))}
        
        # Stats pour normalisation
        depths = [node.get('depth', 0) for node in nodes]
        if depths:
            self.stats['depth_mean'] = np.mean(depths)
            self.stats['depth_std'] = np.std(depths) or 1.0
        
        logger.info(f"✅ Vocabulaires construits:")
        logger.info(f"   • Types nœuds: {len(self.node_type_vocab)}")
        logger.info(f"   • Types arêtes: {len(self.edge_type_vocab)}")
        logger.info(f"   • Prédicats: {len(self.predicate_vocab)}")
    
    def extract_node_features(self, node: Dict[str, Any]) -> np.ndarray:
        """
        Extrait les features d'un nœud
        
        Returns:
            Array [type_onehot + depth_norm + predicates + fanout + 🆕 parent_info]
        """
        features = []
        
        # 1. Type de nœud (one-hot)
        node_type = self._get_node_type(node)
        type_onehot = self._onehot_encode(node_type, self.node_type_vocab)
        features.append(type_onehot)
        
        # 2. Profondeur (normalisée)
        depth = node.get('depth', 0)
        depth_norm = self._normalize_depth(depth)
        features.append([depth_norm])
        
        # 3. Prédicats présents (multi-hot)
        predicates = self._get_node_predicates(node)
        predicates_multihot = self._multihot_encode(predicates, self.predicate_vocab)
        features.append(predicates_multihot)
        
        # 4. Fanout (normalisé)
        fanout = node.get('fanout', 0)
        fanout_norm = self._normalize_fanout(fanout)
        features.append([fanout_norm])
        
        # 🆕 5. Info parent (a un parent ?)
        has_parent = 1.0 if 'parent_uid' in node and node['parent_uid'] else 0.0
        features.append([has_parent])
        
        return np.concatenate(features)
    
    def extract_edge_features(self, edge: Dict[str, Any]) -> np.ndarray:
        """
        🆕 AMÉLIORATION: Extrait features d'arête avec info structurelle
        
        Returns:
            Array [type_onehot + depth_delta + is_sibling]
        """
        features = []
        
        # 1. Type d'arête
        edge_type = edge.get('edge_type', edge.get('predicate', 'unknown'))
        type_onehot = self._onehot_encode(edge_type, self.edge_type_vocab)
        features.append(type_onehot)
        
        # 🆕 2. Delta de profondeur (parent=-1, enfant=+1, sibling=0)
        depth_delta = edge.get('depth_delta', 0.0)
        features.append([depth_delta])
        
        # 🆕 3. Est sibling (même parent)
        is_sibling = 1.0 if edge.get('is_sibling', False) else 0.0
        features.append([is_sibling])
        
        return np.concatenate(features)
    
    def extract_context_features(self, context: Dict[str, Any]) -> np.ndarray:
        """Extrait les features du contexte utilisateur (inchangé)"""
        features = []
        
        domain = context.get('domain', '')
        task = context.get('task', '')
        variables = context.get('variables', [])
        
        domain_hash = self._hash_string(domain)
        task_hash = self._hash_string(task)
        num_vars = len(variables)
        num_vars_norm = min(num_vars / 20.0, 1.0)
        
        features.extend([domain_hash, task_hash, num_vars_norm])
        
        return np.array(features, dtype=np.float32)
    
    def get_feature_dims(self) -> Dict[str, int]:
        """
        Retourne les dimensions de chaque type de feature
        
        ✅ CORRIGÉ: Inclut has_parent et edge features
        """
        node_dim = (
            len(self.node_type_vocab) +  # type one-hot
            1 +                           # depth
            len(self.predicate_vocab) +   # predicates multi-hot
            1 +                           # fanout
            1                             # 🆕 has_parent
        )
        
        edge_dim = (
            len(self.edge_type_vocab) +   # type one-hot
            1 +                           # 🆕 depth_delta
            1                             # 🆕 is_sibling
        )
        
        context_dim = 3  # domain_hash, task_hash, num_vars
        
        return {
            'node': node_dim,
            'edge': edge_dim,
            'context': context_dim
        }
    
    # === 🆕 NOUVELLES MÉTHODES POUR STRUCTURE ===
    
    def extract_structural_relations(
        self,
        nodes: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        🆕 Extrait matrice d'adjacence et arêtes enrichies
        
        Returns:
            adjacency_matrix: [N, N] - 1 si connexion existe
            edges: Liste d'arêtes avec features enrichies
        """
        n = len(nodes)
        adjacency = np.zeros((n, n), dtype=np.float32)
        
        # Mapping uid → index
        uid_to_idx = {node['uid']: i for i, node in enumerate(nodes)}
        
        edges = []
        
        for i, node in enumerate(nodes):
            # Relation parent-enfant
            if 'parent_uid' in node and node['parent_uid']:
                parent_uid = node['parent_uid']
                
                if parent_uid in uid_to_idx:
                    parent_idx = uid_to_idx[parent_uid]
                    
                    # Bidirectionnel
                    adjacency[i, parent_idx] = 1.0  # Enfant → Parent
                    adjacency[parent_idx, i] = 1.0  # Parent → Enfant
                    
                    # Arête enfant → parent
                    edges.append({
                        'from_idx': i,
                        'to_idx': parent_idx,
                        'edge_type': 'child_parent',
                        'depth_delta': -1.0,
                        'is_sibling': False
                    })
                    
                    # Arête parent → enfant
                    edges.append({
                        'from_idx': parent_idx,
                        'to_idx': i,
                        'edge_type': 'parent_child',
                        'depth_delta': 1.0,
                        'is_sibling': False
                    })
        
        # 🆕 Détecter relations sibling
        parent_to_children = defaultdict(list)
        for i, node in enumerate(nodes):
            parent_uid = node.get('parent_uid')
            if parent_uid:
                parent_to_children[parent_uid].append(i)
        
        # Ajouter arêtes sibling
        for parent_uid, children_indices in parent_to_children.items():
            if len(children_indices) > 1:
                for i in range(len(children_indices)):
                    for j in range(i + 1, len(children_indices)):
                        idx1, idx2 = children_indices[i], children_indices[j]
                        
                        adjacency[idx1, idx2] = 1.0
                        adjacency[idx2, idx1] = 1.0
                        
                        edges.append({
                            'from_idx': idx1,
                            'to_idx': idx2,
                            'edge_type': 'sibling',
                            'depth_delta': 0.0,
                            'is_sibling': True
                        })
        
        return adjacency, edges
    
    # === MÉTHODES PRIVÉES (inchangées) ===
    
    def _get_node_type(self, node: Dict[str, Any]) -> str:
        """Extrait le type du nœud"""
        node_type = node.get('dgraph.type', 'Unknown')
        
        if isinstance(node_type, list):
            for t in node_type:
                if not t.startswith('dgraph.'):
                    return t
            return 'Unknown'
        
        return node_type if node_type else 'Unknown'
    
    def _get_node_predicates(self, node: Dict[str, Any]) -> Set[str]:
        """Extrait les prédicats (champs) du nœud"""
        predicates = set()
        
        for key in node.keys():
            if key not in ['uid', 'dgraph.type', 'depth', 'fanout', 'parent_uid']:
                predicates.add(key)
        
        return predicates
    
    def _onehot_encode(self, value: str, vocab: Dict[str, int]) -> np.ndarray:
        """Encode une valeur en one-hot"""
        vector = np.zeros(len(vocab), dtype=np.float32)
        
        if value in vocab:
            vector[vocab[value]] = 1.0
        
        return vector
    
    def _multihot_encode(self, values: Set[str], vocab: Dict[str, int]) -> np.ndarray:
        """Encode un ensemble de valeurs en multi-hot"""
        vector = np.zeros(len(vocab), dtype=np.float32)
        
        for value in values:
            if value in vocab:
                vector[vocab[value]] = 1.0
        
        return vector
    
    def _normalize_depth(self, depth: float) -> float:
        """Normalise la profondeur"""
        normalized = (depth - self.stats['depth_mean']) / self.stats['depth_std']
        return np.clip(normalized, -3.0, 3.0)
    
    def _normalize_fanout(self, fanout: float) -> float:
        """Normalise le fanout"""
        return min(fanout / self.max_fanout, 1.0)
    
    def _hash_string(self, s: str) -> float:
        """Hash simple d'une string en [0, 1]"""
        if not s:
            return 0.0
        return (hash(s) % 100000) / 100000.0
    
    def save_vocabularies(self, path: str):
        """Sauvegarde les vocabulaires"""
        import json
        
        data = {
            'node_type_vocab': self.node_type_vocab,
            'edge_type_vocab': self.edge_type_vocab,
            'predicate_vocab': self.predicate_vocab,
            'stats': self.stats,
            'max_depth': self.max_depth,
            'max_fanout': self.max_fanout
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Vocabulaires sauvegardés: {path}")
    
    def load_vocabularies(self, path: str):
        """Charge les vocabulaires"""
        import json
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        self.node_type_vocab = data['node_type_vocab']
        self.edge_type_vocab = data['edge_type_vocab']
        self.predicate_vocab = data['predicate_vocab']
        self.stats = data['stats']
        self.max_depth = data['max_depth']
        self.max_fanout = data['max_fanout']
        
        logger.info(f"📂 Vocabulaires chargés: {path}")


# ============================================================================
# UTILITAIRES
# ============================================================================

def compute_fanout_from_edges(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Calcule le fanout de chaque nœud depuis les arêtes
    """
    fanout_counts = defaultdict(int)
    
    for edge in edges:
        source = edge.get('from')
        if source:
            fanout_counts[source] += 1
    
    return dict(fanout_counts)


def enrich_nodes_with_parent_info(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    🆕 Enrichit les nœuds avec info parent depuis les arêtes
    
    Args:
        nodes: Liste des nœuds
        edges: Liste des arêtes
    
    Returns:
        Nœuds enrichis avec 'parent_uid'
    """
    # Construire mapping enfant → parent
    child_to_parent = {}
    
    for edge in edges:
        if edge.get('predicate') in ['taxonomy.parent', 'parent']:
            child_uid = edge.get('from')
            parent_uid = edge.get('to')
            if child_uid and parent_uid:
                child_to_parent[child_uid] = parent_uid
        elif edge.get('predicate') in ['taxonomy.children', 'children']:
            parent_uid = edge.get('from')
            child_uid = edge.get('to')
            if child_uid and parent_uid:
                child_to_parent[child_uid] = parent_uid
    
    # Enrichir nœuds
    enriched_nodes = []
    for node in nodes:
        node_copy = node.copy()
        uid = node['uid']
        
        if uid in child_to_parent:
            node_copy['parent_uid'] = child_to_parent[uid]
        
        enriched_nodes.append(node_copy)
    
    logger.info(f"✅ {len(child_to_parent)} nœuds enrichis avec parent_uid")
    
    return enriched_nodes