#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration pour le Graph Learner Neural

Centralise tous les hyperparamètres et options de configuration
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class NeuralConfig:
    """
    Configuration du modèle neuronal
    
    Attributes:
        node_embed_dim: Dimension des embeddings de nœuds
        edge_embed_dim: Dimension des embeddings d'arêtes
        context_embed_dim: Dimension des embeddings de contexte
        num_transformer_layers: Nombre de couches Transformer
        num_attention_heads: Nombre de têtes d'attention
        transformer_dim: Dimension interne du Transformer
        feedforward_dim: Dimension du feedforward network
        dropout: Taux de dropout
        mlp_hidden_dims: Dimensions des couches cachées du MLP
        mlp_dropout: Dropout spécifique au MLP
        learning_rate: Learning rate pour Adam
        batch_size: Taille des batches
        max_epochs: Nombre maximum d'epochs
        early_stopping_patience: Patience pour early stopping
        online_buffer_size: Taille du buffer pour online learning
        online_update_frequency: Fréquence des updates online
    """
    
    # === Dimensions d'Embedding ===
    node_embed_dim: int = 128
    edge_embed_dim: int = 64
    context_embed_dim: int = 96
    
    # === Architecture Transformer ===
    num_transformer_layers: int = 4
    num_attention_heads: int = 8
    transformer_dim: int = 256
    feedforward_dim: int = 512
    dropout: float = 0.1
    
    # === Architecture MLP ===
    mlp_hidden_dims: List[int] = None
    mlp_dropout: float = 0.2
    
    # === Training ===
    learning_rate: float = 0.001
    batch_size: int = 32
    max_epochs: int = 100
    early_stopping_patience: int = 10
    weight_decay: float = 0.0001
    
    # === Online Learning ===
    online_buffer_size: int = 1000
    online_update_frequency: int = 10
    
    # === Data Processing ===
    max_nodes_per_structure: int = 50
    max_depth: int = 10
    max_fanout: int = 50
    
    # === Device ===
    device: str = 'cpu'  # 'cpu' ou 'cuda'
    
    def __post_init__(self):
        """Initialisation post-dataclass"""
        # Valeurs par défaut pour MLP
        if self.mlp_hidden_dims is None:
            self.mlp_hidden_dims = [512, 256, 128]
        
        # Validation
        assert self.node_embed_dim > 0, "node_embed_dim doit être > 0"
        assert self.num_transformer_layers > 0, "num_transformer_layers doit être > 0"
        assert self.transformer_dim % self.num_attention_heads == 0, \
            "transformer_dim doit être divisible par num_attention_heads"
        assert 0.0 < self.learning_rate < 1.0, "learning_rate doit être dans ]0, 1["
        assert self.batch_size > 0, "batch_size doit être > 0"
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            'node_embed_dim': self.node_embed_dim,
            'edge_embed_dim': self.edge_embed_dim,
            'context_embed_dim': self.context_embed_dim,
            'num_transformer_layers': self.num_transformer_layers,
            'num_attention_heads': self.num_attention_heads,
            'transformer_dim': self.transformer_dim,
            'feedforward_dim': self.feedforward_dim,
            'dropout': self.dropout,
            'mlp_hidden_dims': self.mlp_hidden_dims,
            'mlp_dropout': self.mlp_dropout,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'max_epochs': self.max_epochs,
            'early_stopping_patience': self.early_stopping_patience,
            'online_buffer_size': self.online_buffer_size,
            'online_update_frequency': self.online_update_frequency,
            'max_nodes_per_structure': self.max_nodes_per_structure,
            'max_depth': self.max_depth,
            'max_fanout': self.max_fanout,
            'device': self.device
        }
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'NeuralConfig':
        """Crée depuis un dictionnaire"""
        return cls(**config_dict)
    
    @classmethod
    def small(cls) -> 'NeuralConfig':
        """Configuration légère pour test rapide"""
        return cls(
            node_embed_dim=64,
            num_transformer_layers=2,
            num_attention_heads=4,
            transformer_dim=128,
            feedforward_dim=256,
            mlp_hidden_dims=[256, 128],
            max_epochs=20,
            batch_size=16
        )
    
    @classmethod
    def large(cls) -> 'NeuralConfig':
        """Configuration large pour production"""
        return cls(
            node_embed_dim=256,
            num_transformer_layers=8,
            num_attention_heads=16,
            transformer_dim=512,
            feedforward_dim=2048,
            mlp_hidden_dims=[1024, 512, 256],
            max_epochs=200,
            batch_size=64
        )


@dataclass
class HybridConfig:
    """
    Configuration pour le learner hybride
    
    Attributes:
        stat_confidence_threshold: Seuil pour utiliser stats seul
        stat_weight: Poids du score statistique
        neural_weight: Poids du score neural
        use_adaptive_weights: Utiliser poids adaptatifs basés sur confiance
        stat_model_path: Chemin du modèle statistique
        neural_model_path: Chemin du modèle neural
    """
    
    stat_confidence_threshold: float = 0.8
    stat_weight: float = 0.6
    neural_weight: float = 0.4
    use_adaptive_weights: bool = True
    
    stat_model_path: str = "./data/graph_structure_model.json"
    neural_model_path: str = "./data/neural_graph_model.pt"
    
    def __post_init__(self):
        """Validation"""
        assert 0.0 <= self.stat_confidence_threshold <= 1.0
        assert 0.0 <= self.stat_weight <= 1.0
        assert 0.0 <= self.neural_weight <= 1.0
        assert abs(self.stat_weight + self.neural_weight - 1.0) < 0.01, \
            "Les poids doivent sommer à 1.0"
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire"""
        return {
            'stat_confidence_threshold': self.stat_confidence_threshold,
            'stat_weight': self.stat_weight,
            'neural_weight': self.neural_weight,
            'use_adaptive_weights': self.use_adaptive_weights,
            'stat_model_path': self.stat_model_path,
            'neural_model_path': self.neural_model_path
        }