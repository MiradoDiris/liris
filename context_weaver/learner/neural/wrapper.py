#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wrapper pour compatibilité avec l'API GraphStructureLearner

Permet de remplacer GraphStructureLearner sans changer le code appelant
"""

import logging
import torch
from pathlib import Path
from typing import Dict, List, Any, Optional

from context_weaver.taxonomy.taxonomy_models import StructureHypothesis

from .config import NeuralConfig
from .feature_extractor import GraphFeatureExtractor
from .dataset import GraphStructureDataset
from .trainer import NeuralGraphLearnerTrainer

logger = logging.getLogger(__name__)


class NeuralGraphLearnerWrapper:
    """
    Wrapper compatible avec l'API de GraphStructureLearner
    
    Interface identique, implémentation neuronale différente.
    
    Args:
        model_path: Chemin du modèle PyTorch
        config: NeuralConfig (optionnel, auto si None)
    """
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        config: Optional[NeuralConfig] = None
    ):
        self.model_path = model_path or Path("./data/neural_graph_model.pt")
        self.config = config or NeuralConfig()
        
        # Feature extractor
        self.feature_extractor = GraphFeatureExtractor(
            max_depth=self.config.max_depth,
            max_fanout=self.config.max_fanout
        )
        
        # Trainer (modèle sera créé après build_vocabularies)
        self.trainer = None
        
        # Charger si existe
        if self.model_path.exists():
            self._load_model()
        
        logger.info("✅ Neural Graph Learner Wrapper initialisé")
    
    def train_from_graph(self, graph_data: Dict[str, Any]):
        """
        Entraîne le modèle (compatible avec API existante)
        
        Args:
            graph_data: {'nodes': [...], 'edges': [...]}
        """
        logger.info("🎓 Entraînement neural en cours...")
        
        # Build vocabularies
        self.feature_extractor.build_vocabularies(graph_data)
        
        # Create dataset
        dataset = GraphStructureDataset(
            graph_data,
            self.feature_extractor,
            max_nodes=self.config.max_nodes_per_structure,
            include_negative_samples=False
        )
        
        if len(dataset) == 0:
            logger.warning("⚠️  Dataset vide, skip training")
            return
        
        # Split train/val
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        
        if val_size == 0:
            val_size = 1
            train_size = len(dataset) - 1
        
        train_ds, val_ds = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )
        
        # Create trainer
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.trainer = NeuralGraphLearnerTrainer(
            self.config,
            self.feature_extractor,
            device
        )
        
        # Train
        history = self.trainer.train(train_ds, val_ds)
        
        # Save
        self.trainer.save_model(self.model_path)
        
        # Save vocabularies aussi
        vocab_path = self.model_path.parent / "neural_vocabularies.json"
        self.feature_extractor.save_vocabularies(str(vocab_path))
        
        final_loss = history['train_loss'][-1] if history['train_loss'] else 0.0
        logger.info(f"✅ Entraînement terminé (loss: {final_loss:.4f})")
    
    def validate_structure(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Valide une structure (compatible avec API existante)
        
        Returns:
            {
                'quality_score': float,
                'confidence': float,
                'quality_category': str,
                'issues': List[str]
            }
        """
        if not self.trainer:
            logger.warning("⚠️  Modèle non entraîné, retour score neutre")
            return {
                'quality_score': 0.5,
                'confidence': 0.0,
                'quality_category': 'MEDIUM',
                'issues': ['model_not_trained']
            }
        
        return self.trainer.predict(structure, context)
    
    def predict_structure(
        self,
        context: Dict[str, Any],
        candidates: List,
        prereq_cache: Optional = None # type: ignore
    ) -> StructureHypothesis:
        """
        Prédit la structure (compatible avec API existante)
        
        Args:
            context: Context utilisateur
            candidates: Liste de TaxonCandidate
            prereq_cache: PrereqSnapshot (optionnel)
        
        Returns:
            StructureHypothesis
        """
        if not candidates:
            return StructureHypothesis(
                primary_label_id=None,
                expected_prereq_hard_ids=[],
                confidence=0.5
            )
        
        if not self.trainer:
            # Fallback: retourner premier candidat
            first_candidate = candidates[0]
            return StructureHypothesis(
                primary_label_id=getattr(first_candidate, 'taxon_id', None),
                expected_prereq_hard_ids=[],
                confidence=0.5
            )
        
        # Scorer chaque candidat
        best_score = 0.0
        best_candidate = None
        
        for candidate in candidates[:10]:  # Top 10 pour vitesse
            # Convertir candidate en structure dict
            struct = {
                'uid': getattr(candidate, 'taxon_id', 'unknown'),
                'dgraph.type': 'LabelNode',
                'depth': getattr(candidate, 'depth', 3),
                'name': getattr(candidate, 'name', '')
            }
            
            result = self.validate_structure(struct, context)
            
            if result['quality_score'] > best_score:
                best_score = result['quality_score']
                best_candidate = candidate
        
        # Retourner hypothesis
        primary_id = getattr(best_candidate, 'taxon_id', None) if best_candidate else None
        
        return StructureHypothesis(
            primary_label_id=primary_id,
            expected_prereq_hard_ids=[],
            confidence=best_score
        )
    
    def provide_feedback(
        self,
        structure_id: str,
        was_correct: bool,
        feedback_details: Optional[Dict] = None
    ):
        """Feedback pour online learning (compatible API)"""
        if not self.trainer:
            return
        
        # Reconstruire structure depuis ID (simplification)
        structure = {
            'uid': structure_id,
            'dgraph.type': 'LabelNode',
            'depth': 3
        }
        
        context = {}
        if feedback_details and 'context' in feedback_details:
            context = feedback_details['context']
        
        self.trainer.online_update(structure, context, was_correct)
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """Métriques (compatible API)"""
        metrics = {
            'total_graphs_seen': 1,
            'model_type': 'neural',
            'model_path': str(self.model_path),
            'device': 'cuda' if torch.cuda.is_available() else 'cpu'
        }
        
        if self.trainer:
            metrics['num_parameters'] = self.trainer._count_parameters()
            metrics['update_counter'] = self.trainer.update_counter
        
        return metrics
    
    def get_all_patterns(self) -> Dict[str, Any]:
        """
        Retourne patterns (pour compatibilité)
        
        Note: Les patterns ne sont plus explicites dans neural,
        donc on retourne des infos sur les vocabulaires
        """
        return {
            'node_patterns': {
                t: {'frequency': 0, 'type': t}
                for t in self.feature_extractor.node_type_vocab.keys()
            },
            'edge_patterns': {
                t: {'frequency': 0, 'type': t}
                for t in self.feature_extractor.edge_type_vocab.keys()
            },
            'constraints': [],
            'path_patterns': {}
        }
    
    def _load_model(self):
        """Charge le modèle depuis le disque"""
        # Charger vocabulaires d'abord
        vocab_path = self.model_path.parent / "neural_vocabularies.json"
        if vocab_path.exists():
            self.feature_extractor.load_vocabularies(str(vocab_path))
        
        # Créer trainer
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.trainer = NeuralGraphLearnerTrainer(
            self.config,
            self.feature_extractor,
            device
        )
        
        # Charger checkpoint
        self.trainer.load_model(self.model_path)
        
        logger.info(f"📂 Modèle neural chargé: {self.model_path}")