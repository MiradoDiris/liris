#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/utils.py - Fonctions utilitaires pour GRPO
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime
import logging

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# FICHIERS ET CHECKPOINTS
# ============================================================================

def save_json(data: Dict[str, Any], filepath: str, indent: int = 2):
    """
    Sauvegarde des données en JSON
    
    Args:
        data: Données à sauvegarder
        filepath: Chemin du fichier
        indent: Indentation JSON
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    
    logger.debug(f"💾 Saved: {filepath}")


def load_json(filepath: str) -> Dict[str, Any]:
    """
    Charge des données depuis JSON
    
    Args:
        filepath: Chemin du fichier
    
    Returns:
        Données chargées
    """
    if not os.path.exists(filepath):
        logger.warning(f"⚠️  File not found: {filepath}")
        return {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.debug(f"📂 Loaded: {filepath}")
    return data


def list_checkpoints(checkpoint_dir: str) -> List[str]:
    """
    Liste tous les checkpoints disponibles
    
    Args:
        checkpoint_dir: Répertoire des checkpoints
    
    Returns:
        Liste des chemins de checkpoints
    """
    if not os.path.exists(checkpoint_dir):
        return []
    
    checkpoints = [
        os.path.join(checkpoint_dir, f)
        for f in os.listdir(checkpoint_dir)
        if f.endswith('.json')
    ]
    
    return sorted(checkpoints)


def load_latest_checkpoint(checkpoint_dir: str) -> Dict[str, Any]:
    """
    Charge le checkpoint le plus récent
    
    Args:
        checkpoint_dir: Répertoire des checkpoints
    
    Returns:
        Données du checkpoint ou {}
    """
    checkpoints = list_checkpoints(checkpoint_dir)
    
    if not checkpoints:
        logger.warning("⚠️  No checkpoints found")
        return {}
    
    latest = checkpoints[-1]
    logger.info(f"📂 Loading latest checkpoint: {latest}")
    
    return load_json(latest)


# ============================================================================
# FORMATAGE ET AFFICHAGE
# ============================================================================

def format_time(seconds: float) -> str:
    """
    Formate une durée en secondes
    
    Args:
        seconds: Durée en secondes
    
    Returns:
        Durée formatée (ex: "1h 23m 45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {seconds:.1f}s"
    
    hours = minutes // 60
    minutes = minutes % 60
    
    return f"{hours}h {minutes}m {seconds:.0f}s"


def format_number(num: float, precision: int = 2) -> str:
    """
    Formate un nombre avec séparateurs de milliers
    
    Args:
        num: Nombre à formater
        precision: Nombre de décimales
    
    Returns:
        Nombre formaté
    """
    if isinstance(num, int):
        return f"{num:,}".replace(',', ' ')
    else:
        return f"{num:,.{precision}f}".replace(',', ' ')


def format_percent(value: float, precision: int = 1) -> str:
    """
    Formate un pourcentage
    
    Args:
        value: Valeur entre 0 et 1
        precision: Nombre de décimales
    
    Returns:
        Pourcentage formaté (ex: "85.3%")
    """
    return f"{value * 100:.{precision}f}%"


def print_summary_table(data: Dict[str, Any], title: str = "Summary"):
    """
    Affiche un tableau de résumé
    
    Args:
        data: Données à afficher
        title: Titre du tableau
    """
    print("\n" + "="*60)
    print(f"{title:^60}")
    print("="*60)
    
    for key, value in data.items():
        if isinstance(value, float):
            print(f"{key:.<40} {value:>15.2f}")
        elif isinstance(value, int):
            print(f"{key:.<40} {value:>15,}")
        else:
            print(f"{key:.<40} {str(value):>15}")
    
    print("="*60 + "\n")


# ============================================================================
# STATISTIQUES
# ============================================================================

def compute_percentiles(values: List[float], percentiles: List[int] = [25, 50, 75]) -> Dict[int, float]:
    """
    Calcule les percentiles
    
    Args:
        values: Liste de valeurs
        percentiles: Liste des percentiles à calculer
    
    Returns:
        Dict {percentile: valeur}
    """
    import numpy as np
    
    if not values:
        return {p: 0.0 for p in percentiles}
    
    return {
        p: float(np.percentile(values, p))
        for p in percentiles
    }


def moving_average(values: List[float], window: int = 10) -> List[float]:
    """
    Calcule la moyenne mobile
    
    Args:
        values: Liste de valeurs
        window: Taille de la fenêtre
    
    Returns:
        Moyennes mobiles
    """
    import numpy as np
    
    if len(values) < window:
        return values
    
    return np.convolve(values, np.ones(window)/window, mode='valid').tolist()


def detect_trend(values: List[float]) -> str:
    """
    Détecte la tendance d'une série
    
    Args:
        values: Liste de valeurs
    
    Returns:
        "increasing", "decreasing", ou "stable"
    """
    import numpy as np
    
    if len(values) < 3:
        return "stable"
    
    # Régression linéaire simple
    x = np.arange(len(values))
    y = np.array(values)
    
    # Coefficients
    slope = np.polyfit(x, y, 1)[0]
    
    # Seuil relatif
    threshold = np.std(values) * 0.1
    
    if slope > threshold:
        return "increasing"
    elif slope < -threshold:
        return "decreasing"
    else:
        return "stable"


# ============================================================================
# VALIDATION
# ============================================================================

def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Valide une configuration GRPO
    
    Args:
        config: Configuration à valider
    
    Returns:
        Liste des erreurs (vide si OK)
    """
    errors = []
    
    # Vérifier champs requis
    required = ['group_size', 'num_episodes', 'batch_size', 'learning_rate']
    for field in required:
        if field not in config:
            errors.append(f"Champ requis manquant: {field}")
    
    # Vérifier valeurs
    if config.get('group_size', 0) < 2:
        errors.append("group_size doit être >= 2")
    
    if config.get('num_episodes', 0) < 1:
        errors.append("num_episodes doit être >= 1")
    
    if config.get('batch_size', 0) < 1:
        errors.append("batch_size doit être >= 1")
    
    lr = config.get('learning_rate', 0)
    if not (0 < lr < 1):
        errors.append("learning_rate doit être dans ]0, 1[")
    
    temp = config.get('temperature', 0)
    if not (0 <= temp <= 2):
        errors.append("temperature doit être dans [0, 2]")
    
    return errors


def check_services() -> Dict[str, bool]:
    """
    Vérifie que les services requis sont accessibles
    
    Returns:
        Dict {service: accessible}
    """
    import requests
    
    services = {
        'vllm': 'http://localhost:8000/health',
        'reward_api': 'http://localhost:8086/health'
    }
    
    status = {}
    
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=2)
            status[name] = response.status_code == 200
        except:
            status[name] = False
    
    return status


# ============================================================================
# LOGGING AVANCÉ
# ============================================================================

def setup_logger(name: str, log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure un logger
    
    Args:
        name: Nom du logger
        log_file: Fichier de log (optionnel)
        level: Niveau de log
    
    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler fichier (optionnel)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_config(config: Dict[str, Any], logger: logging.Logger):
    """
    Log une configuration
    
    Args:
        config: Configuration à logger
        logger: Logger à utiliser
    """
    logger.info("="*60)
    logger.info("CONFIGURATION GRPO")
    logger.info("="*60)
    
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("="*60)


# ============================================================================
# EXPORT
# ============================================================================

def export_results_csv(results: List[Dict[str, Any]], filepath: str):
    """
    Export résultats en CSV
    
    Args:
        results: Liste de résultats
        filepath: Chemin du fichier
    """
    import csv
    
    if not results:
        logger.warning("⚠️  No results to export")
        return
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Colonnes
    fieldnames = list(results[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    logger.info(f"💾 Results exported to CSV: {filepath}")


def export_results_jsonl(results: List[Dict[str, Any]], filepath: str):
    """
    Export résultats en JSONL (un JSON par ligne)
    
    Args:
        results: Liste de résultats
        filepath: Chemin du fichier
    """
    if not results:
        logger.warning("⚠️  No results to export")
        return
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    logger.info(f"💾 Results exported to JSONL: {filepath}")


# ============================================================================
# ANALYSE
# ============================================================================

def analyze_rewards_distribution(rewards: List[float]) -> Dict[str, Any]:
    """
    Analyse la distribution des rewards
    
    Args:
        rewards: Liste des rewards
    
    Returns:
        Statistiques
    """
    import numpy as np
    
    if not rewards:
        return {}
    
    rewards_array = np.array(rewards)
    
    return {
        'count': len(rewards),
        'mean': float(np.mean(rewards_array)),
        'std': float(np.std(rewards_array)),
        'min': float(np.min(rewards_array)),
        'max': float(np.max(rewards_array)),
        'median': float(np.median(rewards_array)),
        'percentiles': compute_percentiles(rewards, [10, 25, 50, 75, 90]),
        'skewness': float(np.mean((rewards_array - np.mean(rewards_array))**3) / np.std(rewards_array)**3)
    }


def compare_episodes(episode_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare les épisodes pour détecter progression
    
    Args:
        episode_history: Historique des épisodes
    
    Returns:
        Analyse comparative
    """
    if not episode_history or len(episode_history) < 2:
        return {}
    
    first = episode_history[0]
    last = episode_history[-1]
    
    rewards = [ep['mean_reward'] for ep in episode_history]
    
    improvement = last['mean_reward'] - first['mean_reward']
    improvement_pct = (improvement / first['mean_reward'] * 100) if first['mean_reward'] > 0 else 0
    
    return {
        'num_episodes': len(episode_history),
        'first_reward': first['mean_reward'],
        'last_reward': last['mean_reward'],
        'improvement': improvement,
        'improvement_pct': improvement_pct,
        'best_episode': max(episode_history, key=lambda x: x['mean_reward'])['episode'],
        'best_reward': max(rewards),
        'worst_episode': min(episode_history, key=lambda x: x['mean_reward'])['episode'],
        'worst_reward': min(rewards),
        'trend': detect_trend(rewards),
        'volatility': float(np.std(rewards))
    }