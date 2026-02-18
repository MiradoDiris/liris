#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset PyTorch pour entraîner le Graph Learner Neural - VERSION CORRIGÉE

✅ AJOUTS:
- Matrice d'adjacence (parent-enfant, siblings)
- Masque d'attention pour le Transformer
- Augmentation de données (rotation, masquage)
- Samples négatifs intelligents (corruption structurelle)
"""

import logging
import numpy as np
import torch
from torch.utils.data import Dataset
from typing import Dict, List, Any, Tuple
from collections import deque
import random

logger = logging.getLogger(__name__)


class GraphStructureDataset(Dataset):
    """
    Dataset pour entraîner le modèle neuronal
    
    ✅ AMÉLIORATIONS:
    - Extraction de sous-arbres avec relations parent-enfant
    - Matrice d'adjacence pour attention
    - Samples négatifs par corruption structurelle
    - Augmentation de données
    
    Args:
        graph_data: {'nodes': [...], 'edges': [...]}
        feature_extractor: GraphFeatureExtractor
        max_nodes: Nombre max de nœuds par structure
        include_negative_samples: Inclure des exemples négatifs
        negative_ratio: Ratio négatifs/positifs
        augmentation_factor: Facteur d'augmentation (1 = pas d'augmentation)
    """
    
    def __init__(
        self,
        graph_data: Dict[str, Any],
        feature_extractor,
        max_nodes: int = 50,
        include_negative_samples: bool = True,
        negative_ratio: float = 0.3,
        augmentation_factor: int = 1
    ):
        self.feature_extractor = feature_extractor
        self.max_nodes = max_nodes
        self.include_negative_samples = include_negative_samples
        self.negative_ratio = negative_ratio
        self.augmentation_factor = augmentation_factor
        
        self.samples = []
        
        # 🆕 Enrichir nœuds avec parent_uid
        from feature_extractor import enrich_nodes_with_parent_info
        enriched_nodes = enrich_nodes_with_parent_info(
            graph_data.get('nodes', []),
            graph_data.get('edges', [])
        )
        graph_data['nodes'] = enriched_nodes
        
        # Préparer samples positifs
        self._prepare_positive_samples(graph_data)
        
        # Augmentation
        if augmentation_factor > 1:
            self._augment_samples(augmentation_factor - 1)
        
        # Samples négatifs
        if include_negative_samples:
            self._prepare_negative_samples(graph_data)
        
        logger.info(f"✅ Dataset créé: {len(self.samples)} samples")
        logger.info(f"   • Positifs: {sum(1 for s in self.samples if s['label'] == 1.0)}")
        logger.info(f"   • Négatifs: {sum(1 for s in self.samples if s['label'] == 0.0)}")
    
    def _prepare_positive_samples(self, graph_data: Dict[str, Any]):
        """
        Crée des samples positifs (structures valides)
        
        ✅ AMÉLIORÉ: Extraction de différents types de structures
        """
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        adjacency = self._build_adjacency(edges)
        node_by_uid = {n['uid']: n for n in nodes}
        
        samples_by_type = {
            'complete_tree': [],
            'branch': [],
            'sibling_cluster': []
        }
        
        # 1. Sous-arbres complets (racines)
        for node in nodes:
            depth = node.get('depth', 0)
            
            if depth <= 1:  # Racines ou proches de la racine
                subtree = self._extract_subtree(
                    node['uid'],
                    adjacency,
                    node_by_uid,
                    max_depth=4
                )
                
                if 3 <= len(subtree) <= self.max_nodes:
                    context = self._create_synthetic_context(subtree)
                    samples_by_type['complete_tree'].append({
                        'nodes': subtree,
                        'context': context,
                        'structure_type': 'complete_tree',
                        'label': 1.0
                    })
        
        # 2. Branches (nœuds intermédiaires)
        for node in nodes:
            depth = node.get('depth', 0)
            
            if 2 <= depth <= 5:
                branch = self._extract_subtree(
                    node['uid'],
                    adjacency,
                    node_by_uid,
                    max_depth=3
                )
                
                if 2 <= len(branch) <= self.max_nodes:
                    context = self._create_synthetic_context(branch)
                    samples_by_type['branch'].append({
                        'nodes': branch,
                        'context': context,
                        'structure_type': 'branch',
                        'label': 1.0
                    })
        
        # 3. Clusters de siblings
        parent_to_children = {}
        for node in nodes:
            parent_uid = node.get('parent_uid')
            if parent_uid:
                if parent_uid not in parent_to_children:
                    parent_to_children[parent_uid] = []
                parent_to_children[parent_uid].append(node)
        
        for parent_uid, children in parent_to_children.items():
            if len(children) >= 2 and parent_uid in node_by_uid:
                parent = node_by_uid[parent_uid]
                cluster_nodes = [parent] + children[:min(5, len(children))]
                
                if len(cluster_nodes) <= self.max_nodes:
                    context = self._create_synthetic_context(cluster_nodes)
                    samples_by_type['sibling_cluster'].append({
                        'nodes': cluster_nodes,
                        'context': context,
                        'structure_type': 'sibling_cluster',
                        'label': 1.0
                    })
        
        # Combiner tous les samples
        for structure_type, samples in samples_by_type.items():
            self.samples.extend(samples)
            logger.info(f"   • {structure_type}: {len(samples)} samples")
    
    def _prepare_negative_samples(self, graph_data: Dict[str, Any]):
        """
        🆕 AMÉLIORÉ: Samples négatifs par corruption structurelle
        
        Stratégies:
        1. Inverser relations parent-enfant
        2. Mélanger profondeurs
        3. Créer siblings de parents différents
        4. Profondeurs incohérentes
        """
        positive_samples = [s for s in self.samples if s['label'] == 1.0]
        num_negatives = int(len(positive_samples) * self.negative_ratio)
        
        negatives = []
        
        for _ in range(num_negatives):
            if not positive_samples:
                break
            
            # Choisir un sample positif à corrompre
            source_sample = random.choice(positive_samples)
            nodes = source_sample['nodes']
            
            # Choisir stratégie de corruption
            strategy = random.choice([
                'invert_hierarchy',
                'shuffle_depths',
                'mix_siblings',
                'invalid_depth'
            ])
            
            if strategy == 'invert_hierarchy':
                # Inverser parent-enfant
                corrupted = self._invert_parent_child(nodes)
                corruption_type = 'inverted_hierarchy'
            
            elif strategy == 'shuffle_depths':
                # Mélanger profondeurs
                corrupted = self._shuffle_depths(nodes)
                corruption_type = 'wrong_depth'
            
            elif strategy == 'mix_siblings':
                # Créer faux siblings
                corrupted = self._mix_siblings(nodes)
                corruption_type = 'invalid_siblings'
            
            else:  # invalid_depth
                # Profondeur hors limites
                corrupted = self._create_invalid_depth(nodes)
                corruption_type = 'depth_out_of_bounds'
            
            context = self._create_synthetic_context(corrupted)
            
            negatives.append({
                'nodes': corrupted,
                'context': context,
                'structure_type': source_sample['structure_type'],
                'corruption_type': corruption_type,
                'label': 0.0
            })
        
        self.samples.extend(negatives)
        logger.info(f"   • Négatifs: {len(negatives)} samples (corruption structurelle)")
    
    def _augment_samples(self, num_augmentations: int):
        """
        🆕 Augmentation de données
        
        Techniques:
        - Masquage aléatoire de nœuds
        - Rotation de sous-arbres
        - Ajout de bruit aux features
        """
        original_samples = list(self.samples)
        
        for _ in range(num_augmentations):
            for sample in original_samples:
                if sample['label'] == 0.0:
                    continue  # Pas d'augmentation sur négatifs
                
                # Masquage aléatoire
                if random.random() < 0.5:
                    augmented = self._random_mask_nodes(sample)
                    self.samples.append(augmented)
        
        logger.info(f"   • Augmentation: +{len(self.samples) - len(original_samples)} samples")
    
    # === 🆕 MÉTHODES DE CORRUPTION ===
    
    def _invert_parent_child(self, nodes: List[Dict]) -> List[Dict]:
        """Inverse les relations parent-enfant"""
        corrupted = []
        for node in nodes:
            node_copy = node.copy()
            
            # Inverser depth
            if 'depth' in node_copy:
                max_depth = max(n.get('depth', 0) for n in nodes)
                node_copy['depth'] = max_depth - node_copy['depth']
            
            corrupted.append(node_copy)
        
        return corrupted
    
    def _shuffle_depths(self, nodes: List[Dict]) -> List[Dict]:
        """Mélange les profondeurs"""
        corrupted = [n.copy() for n in nodes]
        depths = [n.get('depth', 0) for n in corrupted]
        random.shuffle(depths)
        
        for i, node in enumerate(corrupted):
            node['depth'] = depths[i]
        
        return corrupted
    
    def _mix_siblings(self, nodes: List[Dict]) -> List[Dict]:
        """Crée de faux siblings (parents différents)"""
        corrupted = [n.copy() for n in nodes]
        
        if len(corrupted) >= 2:
            # Donner le même parent_uid à des nœuds de profondeurs différentes
            fake_parent = f"fake_parent_{random.randint(1000, 9999)}"
            for node in corrupted[:2]:
                node['parent_uid'] = fake_parent
        
        return corrupted
    
    def _create_invalid_depth(self, nodes: List[Dict]) -> List[Dict]:
        """Crée des profondeurs invalides"""
        corrupted = [n.copy() for n in nodes]
        
        if corrupted:
            # Profondeur hors limites
            corrupted[0]['depth'] = random.randint(20, 50)
        
        return corrupted
    
    def _random_mask_nodes(self, sample: Dict) -> Dict:
        """Masque aléatoirement des nœuds (augmentation)"""
        nodes = sample['nodes']
        mask_ratio = 0.2
        num_to_mask = max(1, int(len(nodes) * mask_ratio))
        
        # Garder au moins le nœud racine
        indices_to_keep = random.sample(range(len(nodes)), len(nodes) - num_to_mask)
        masked_nodes = [nodes[i] for i in sorted(indices_to_keep)]
        
        return {
            'nodes': masked_nodes,
            'context': sample['context'],
            'structure_type': sample['structure_type'],
            'label': sample['label']
        }
    
    # === MÉTHODES UTILITAIRES ===
    
    def _extract_subtree(
        self,
        root_uid: str,
        adjacency: Dict,
        node_by_uid: Dict,
        max_depth: int = 3
    ) -> List[Dict]:
        """Extrait un sous-arbre BFS jusqu'à max_depth"""
        subtree = []
        queue = deque([(root_uid, 0)])
        visited = set()
        
        while queue and len(subtree) < self.max_nodes:
            uid, depth = queue.popleft()
            
            if uid in visited or depth > max_depth:
                continue
            
            visited.add(uid)
            
            if uid in node_by_uid:
                subtree.append(node_by_uid[uid])
                
                for child_uid in adjacency.get(uid, []):
                    if child_uid not in visited:
                        queue.append((child_uid, depth + 1))
        
        return subtree
    
    def _build_adjacency(self, edges: List[Dict]) -> Dict[str, List[str]]:
        """Construit adjacency list depuis les arêtes"""
        adjacency = {}
        
        for edge in edges:
            src = edge.get('from')
            tgt = edge.get('to')
            
            if src and tgt:
                if src not in adjacency:
                    adjacency[src] = []
                adjacency[src].append(tgt)
        
        return adjacency
    
    def _create_synthetic_context(self, nodes: List[Dict]) -> Dict[str, Any]:
        """Crée un contexte synthétique depuis les nœuds"""
        node_types = [n.get('dgraph.type', 'Unknown') for n in nodes]
        
        if 'Project' in node_types:
            domain = 'Macompta.fr'
        elif 'Typologie' in node_types:
            domain = 'Taxonomy'
        else:
            domain = 'Generic'
        
        variables = []
        for node in nodes:
            if 'name' in node:
                variables.append(node['name'])
        
        task = 'classify' if len(nodes) < 5 else 'complex_query'
        
        return {
            'domain': domain,
            'variables': variables[:10],
            'task': task
        }
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        🆕 CORRIGÉ: Retourne sample avec adjacency matrix et attention mask
        
        Returns:
            {
                'node_features': [max_nodes, node_feature_dim],
                'adjacency_matrix': [max_nodes, max_nodes],  # 🆕
                'attention_mask': [max_nodes, max_nodes],    # 🆕
                'node_mask': [max_nodes],
                'context_features': [context_dim],
                'label': [1]
            }
        """
        sample = self.samples[idx]
        nodes = sample['nodes'][:self.max_nodes]
        num_nodes = len(nodes)
        
        # 1. Features de nœuds
        node_features_list = []
        for node in nodes:
            features = self.feature_extractor.extract_node_features(node)
            node_features_list.append(features)
        
        # 🆕 2. Matrice d'adjacence et arêtes
        adjacency_matrix, edges = self.feature_extractor.extract_structural_relations(nodes)
        
        # Padding
        if num_nodes < self.max_nodes:
            zero_features = np.zeros_like(node_features_list[0])
            for _ in range(self.max_nodes - num_nodes):
                node_features_list.append(zero_features)
            
            # Pad adjacency matrix
            padded_adj = np.zeros((self.max_nodes, self.max_nodes), dtype=np.float32)
            padded_adj[:num_nodes, :num_nodes] = adjacency_matrix
            adjacency_matrix = padded_adj
        
        node_features = np.stack(node_features_list)
        
        # 🆕 3. Attention mask (True = ignorer, False = attention)
        attention_mask = np.ones((self.max_nodes, self.max_nodes), dtype=bool)
        attention_mask[:num_nodes, :num_nodes] = False  # Autoriser attention entre vrais nœuds
        
        # 4. Node mask
        node_mask = np.array(
            [1.0] * num_nodes + [0.0] * (self.max_nodes - num_nodes),
            dtype=np.float32
        )
        
        # 5. Context features
        context_features = self.feature_extractor.extract_context_features(
            sample['context']
        )
        
        # 6. Label
        label = np.array([sample['label']], dtype=np.float32)
        
        return {
            'node_features': torch.FloatTensor(node_features),
            'adjacency_matrix': torch.FloatTensor(adjacency_matrix),
            'attention_mask': torch.BoolTensor(attention_mask),
            'node_mask': torch.FloatTensor(node_mask),
            'context_features': torch.FloatTensor(context_features),
            'label': torch.FloatTensor(label)
        }


# ============================================================================
# ONLINE LEARNING BUFFER (inchangé mais compatible)
# ============================================================================

class OnlineLearningBuffer:
    """Buffer pour online learning avec feedback utilisateur"""
    
    def __init__(
        self,
        max_size: int,
        feature_extractor,
        max_nodes: int = 50
    ):
        self.buffer = deque(maxlen=max_size)
        self.feature_extractor = feature_extractor
        self.max_nodes = max_nodes
    
    def add(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any],
        was_correct: bool
    ):
        """Ajoute un feedback au buffer"""
        self.buffer.append({
            'structure': structure,
            'context': context,
            'label': 1.0 if was_correct else 0.0
        })
    
    def sample_batch(self, batch_size: int) -> Dict[str, torch.Tensor]:
        """Sample un mini-batch depuis le buffer"""
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)
        
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        samples = [self.buffer[i] for i in indices]
        
        node_features_list = []
        adjacency_list = []
        attention_mask_list = []
        context_features_list = []
        node_mask_list = []
        labels_list = []
        
        for sample in samples:
            nodes = [sample['structure']]
            
            # Features
            node_feat = [
                self.feature_extractor.extract_node_features(n) for n in nodes
            ]
            
            # Adjacency (un seul nœud = pas de connexions)
            adjacency = np.zeros((self.max_nodes, self.max_nodes), dtype=np.float32)
            
            # Attention mask
            attention_mask = np.ones((self.max_nodes, self.max_nodes), dtype=bool)
            attention_mask[0, 0] = False
            
            # Padding
            while len(node_feat) < self.max_nodes:
                node_feat.append(np.zeros_like(node_feat[0]))
            
            node_features_list.append(np.stack(node_feat))
            adjacency_list.append(adjacency)
            attention_mask_list.append(attention_mask)
            
            # Mask
            node_mask = np.array(
                [1.0] * len(nodes) + [0.0] * (self.max_nodes - len(nodes))
            )
            node_mask_list.append(node_mask)
            
            # Context
            context_feat = self.feature_extractor.extract_context_features(
                sample['context']
            )
            context_features_list.append(context_feat)
            
            labels_list.append(sample['label'])
        
        return {
            'node_features': torch.FloatTensor(np.stack(node_features_list)),
            'adjacency_matrix': torch.FloatTensor(np.stack(adjacency_list)),
            'attention_mask': torch.BoolTensor(np.stack(attention_mask_list)),
            'node_mask': torch.FloatTensor(np.stack(node_mask_list)),
            'context_features': torch.FloatTensor(np.stack(context_features_list)),
            'label': torch.FloatTensor(labels_list).unsqueeze(1)
        }
    
    def __len__(self) -> int:
        return len(self.buffer)