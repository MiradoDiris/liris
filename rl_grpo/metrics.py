#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/metrics.py - Calcul des métriques et advantages GRPO

Implémente la formule:
A_g = (R_g - mean(R_{1..G})) / std(R_{1..G})

Où:
- R_g: reward de la réponse g
- mean(R_{1..G}): moyenne des rewards du groupe
- std(R_{1..G}): écart-type des rewards du groupe
- A_g: advantage normalisé de la réponse g
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GroupMetrics:
    """Métriques d'un groupe de réponses"""
    group_id: int
    prompt: str
    responses: List[str]
    rewards: List[float]
    advantages: List[float]
    mean_reward: float
    std_reward: float
    best_response_idx: int
    worst_response_idx: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return {
            "group_id": self.group_id,
            "prompt": self.prompt,
            "num_responses": len(self.responses),
            "mean_reward": self.mean_reward,
            "std_reward": self.std_reward,
            "min_reward": min(self.rewards) if self.rewards else 0,
            "max_reward": max(self.rewards) if self.rewards else 0,
            "best_response": self.responses[self.best_response_idx] if self.responses else "",
            "worst_response": self.responses[self.worst_response_idx] if self.responses else "",
            "advantages": self.advantages,
            "timestamp": self.timestamp
        }


def compute_advantages(
    rewards: List[float],
    epsilon: float = 1e-8,
    normalize: bool = True
) -> Tuple[List[float], float, float]:
    """
    Calcule les advantages selon la formule GRPO:
    A_g = (R_g - mean(R)) / std(R)
    
    Args:
        rewards: Liste des G rewards du groupe
        epsilon: Valeur minimale pour éviter division par 0
        normalize: Si True, applique la normalisation
    
    Returns:
        (advantages, mean_reward, std_reward)
    """
    if not rewards:
        return [], 0.0, 0.0
    
    rewards_array = np.array(rewards, dtype=np.float32)
    
    # Calcul de la moyenne
    mean_reward = np.mean(rewards_array)
    
    # Calcul de l'écart-type
    std_reward = np.std(rewards_array)
    
    # Éviter division par zéro
    if std_reward < epsilon:
        std_reward = epsilon
    
    if normalize:
        # Formule GRPO: A_g = (R_g - mean) / std
        advantages = (rewards_array - mean_reward) / std_reward
    else:
        # Sans normalisation: A_g = R_g - mean
        advantages = rewards_array - mean_reward
    
    return advantages.tolist(), float(mean_reward), float(std_reward)


def compute_group_metrics(
    group_id: int,
    prompt: str,
    responses: List[str],
    rewards: List[float],
    epsilon: float = 1e-8,
    normalize: bool = True
) -> GroupMetrics:
    """
    Calcule les métriques complètes d'un groupe
    
    Args:
        group_id: ID du groupe
        prompt: Prompt original
        responses: Liste des G réponses générées
        rewards: Liste des G rewards
        epsilon: Valeur minimale pour éviter division par 0
        normalize: Activer normalisation
    
    Returns:
        GroupMetrics
    """
    advantages, mean_reward, std_reward = compute_advantages(
        rewards, epsilon, normalize
    )
    
    # Trouver meilleure et pire réponse
    best_idx = int(np.argmax(rewards)) if rewards else 0
    worst_idx = int(np.argmin(rewards)) if rewards else 0
    
    return GroupMetrics(
        group_id=group_id,
        prompt=prompt,
        responses=responses,
        rewards=rewards,
        advantages=advantages,
        mean_reward=mean_reward,
        std_reward=std_reward,
        best_response_idx=best_idx,
        worst_response_idx=worst_idx
    )


class MetricsTracker:
    """Tracker pour les métriques d'entraînement GRPO"""
    
    def __init__(self):
        self.episode_metrics = []
        self.group_metrics = []
        self.global_rewards = []
        self.global_advantages = []
    
    def add_group(self, group_metrics: GroupMetrics):
        """Ajoute les métriques d'un groupe"""
        self.group_metrics.append(group_metrics)
        self.global_rewards.extend(group_metrics.rewards)
        self.global_advantages.extend(group_metrics.advantages)
    
    def add_episode(self, episode_data: Dict[str, Any]):
        """Ajoute les métriques d'un épisode"""
        self.episode_metrics.append(episode_data)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques actuelles"""
        if not self.global_rewards:
            return {
                "mean_reward": 0.0,
                "std_reward": 0.0,
                "min_reward": 0.0,
                "max_reward": 0.0,
                "mean_advantage": 0.0,
                "num_groups": 0,
                "num_episodes": len(self.episode_metrics)
            }
        
        return {
            "mean_reward": float(np.mean(self.global_rewards)),
            "std_reward": float(np.std(self.global_rewards)),
            "min_reward": float(np.min(self.global_rewards)),
            "max_reward": float(np.max(self.global_rewards)),
            "mean_advantage": float(np.mean(self.global_advantages)),
            "std_advantage": float(np.std(self.global_advantages)),
            "num_groups": len(self.group_metrics),
            "num_episodes": len(self.episode_metrics),
            "total_samples": len(self.global_rewards)
        }
    
    def get_episode_history(self) -> List[Dict[str, Any]]:
        """Retourne l'historique des épisodes"""
        return self.episode_metrics
    
    def get_recent_groups(self, n: int = 5) -> List[GroupMetrics]:
        """Retourne les N derniers groupes"""
        return self.group_metrics[-n:]
    
    def reset(self):
        """Reset tous les trackers"""
        self.episode_metrics = []
        self.group_metrics = []
        self.global_rewards = []
        self.global_advantages = []
    
    def save_to_file(self, filepath: str):
        """Sauvegarde les métriques dans un fichier JSON"""
        import json
        
        data = {
            "stats": self.get_current_stats(),
            "episode_history": self.episode_metrics,
            "recent_groups": [g.to_dict() for g in self.get_recent_groups(10)]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def clip_advantages(
    advantages: List[float],
    clip_range: float = 0.2
) -> List[float]:
    """
    Clip les advantages (style PPO)
    
    Args:
        advantages: Liste des advantages
        clip_range: Range de clipping [-clip_range, +clip_range]
    
    Returns:
        Advantages clippés
    """
    return np.clip(advantages, -clip_range, clip_range).tolist()


def normalize_rewards(rewards: List[float]) -> List[float]:
    """
    Normalise les rewards entre 0 et 1
    
    Args:
        rewards: Liste des rewards bruts
    
    Returns:
        Rewards normalisés
    """
    if not rewards:
        return []
    
    rewards_array = np.array(rewards, dtype=np.float32)
    
    min_r = np.min(rewards_array)
    max_r = np.max(rewards_array)
    
    if max_r - min_r < 1e-8:
        return [0.5] * len(rewards)
    
    normalized = (rewards_array - min_r) / (max_r - min_r)
    
    return normalized.tolist()


def compute_diversity_score(responses: List[str]) -> float:
    """
    Calcule un score de diversité pour un groupe de réponses
    
    Args:
        responses: Liste des réponses
    
    Returns:
        Score de diversité [0, 1]
    """
    # ✅ FIX: Filtrer les réponses None ou vides AVANT le traitement
    valid_responses = [
        r for r in responses 
        if r is not None and isinstance(r, str) and r.strip()
    ]
    
    if len(valid_responses) < 2:
        return 0.0
    
    # Jaccard similarity moyenne entre toutes les paires
    from itertools import combinations
    
    similarities = []
    for resp1, resp2 in combinations(valid_responses, 2):
        words1 = set(resp1.lower().split())
        words2 = set(resp2.lower().split())
        
        if not words1 or not words2:
            continue
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        similarities.append(similarity)
    
    if not similarities:
        return 0.0
    
    # Diversité = 1 - similarité moyenne
    avg_similarity = np.mean(similarities)
    diversity = 1.0 - avg_similarity
    
    return float(diversity)