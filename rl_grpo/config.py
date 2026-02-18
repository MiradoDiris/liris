#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/config.py - Configuration GRPO
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GRPOConfig:
    """Configuration pour l'entraînement GRPO"""
    
    # ========================================================================
    # MODÈLE
    # ========================================================================
    model_name: str = "openai/gpt-oss-20b"
    vllm_url: str = "http://localhost:8000/v1"
    
    # ========================================================================
    # REWARD MODEL (API de vérification)
    # ========================================================================
    reward_api_url: str = "http://localhost:8086"  # Port 8086 pour éviter conflit avec OSS Classifier (8085)
    reward_validation_level: str = "strict"  # quick, standard, strict
    
    # ========================================================================
    # HYPERPARAMÈTRES GRPO (selon formule)
    # ========================================================================
    
    # Group size (G) - nombre de réponses générées par prompt
    group_size: int = 8  # G dans la formule A_g = (R_g - mean(R)) / std(R)
    
    # Paramètres d'entraînement
    num_episodes: int = 1000
    batch_size: int = 32  # Nombre de prompts par batch
    learning_rate: float = 1e-4
    
    # ========================================================================
    # GÉNÉRATION (pour diversité dans le groupe)
    # ========================================================================
    temperature: float = 0.8  # Plus haut = plus de diversité
    top_p: float = 0.95
    max_tokens: int = 4096
    
    # ========================================================================
    # OPTIMISATION (PPO-style pour GRPO)
    # ========================================================================
    kl_coef: float = 0.1  # Coefficient KL divergence
    clip_range: float = 0.2  # Clipping des advantages
    value_loss_coef: float = 0.5  # Coefficient value loss
    entropy_coef: float = 0.01  # Encourager exploration
    
    # Gradient
    max_grad_norm: float = 1.0  # Gradient clipping
    
    # ========================================================================
    # NORMALISATION DES ADVANTAGES
    # ========================================================================
    normalize_advantages: bool = True  # Activer normalisation A_g
    advantage_epsilon: float = 1e-8  # Pour éviter division par 0
    
    # ========================================================================
    # CHECKPOINTING
    # ========================================================================
    save_every: int = 100  # Sauvegarder tous les N épisodes
    checkpoint_dir: str = "checkpoints/grpo"
    
    # ========================================================================
    # LOGGING
    # ========================================================================
    log_every: int = 10  # Logger tous les N épisodes
    verbose: bool = True
    
    # ========================================================================
    # CONTEXTE MÉTIER
    # ========================================================================
    domain: str = "comptabilité"  # Pour le reward model
    
    def __post_init__(self):
        """Validation de la config"""
        if self.group_size < 2:
            raise ValueError("group_size doit être >= 2 pour GRPO")
        
        if self.batch_size < 1:
            raise ValueError("batch_size doit être >= 1")
        
        if not (0 < self.learning_rate < 1):
            raise ValueError("learning_rate doit être dans ]0, 1[")
        
        if not (0 <= self.temperature <= 2):
            raise ValueError("temperature doit être dans [0, 2]")
    
    def to_dict(self):
        """Convertit la config en dictionnaire"""
        return {
            "model_name": self.model_name,
            "vllm_url": self.vllm_url,
            "reward_api_url": self.reward_api_url,
            "group_size": self.group_size,
            "num_episodes": self.num_episodes,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "temperature": self.temperature,
            "kl_coef": self.kl_coef,
            "clip_range": self.clip_range,
            "domain": self.domain
        }
    
    @classmethod
    def from_dict(cls, config_dict):
        """Crée une config depuis un dictionnaire"""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})