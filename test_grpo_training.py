#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_grpo_training.py - Test d'entraînement GRPO avec Ministral-3-14B
Utilise l'API Ministral Verification (port 8085)

Usage:
    python test_grpo_training.py
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import time

from rl_grpo.config import GRPOConfig
from rl_grpo.grpo_trainer import GRPOTrainer

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_jsonl_batch(filepath: str, max_samples: int = None) -> List[Dict[str, str]]:
    """
    Charge un fichier JSONL et extrait les prompts
    
    Args:
        filepath: Chemin vers le fichier JSONL
        max_samples: Limite le nombre de samples chargés (None = tous)
    
    Returns:
        Liste de dicts avec 'input' et 'output'
    """
    logger.info(f"📂 Chargement du batch: {filepath}")
    
    dataset = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Limite optionnelle
                if max_samples and len(dataset) >= max_samples:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    sample = json.loads(line)
                    
                    # Extraire input et output
                    input_text = sample.get('input', sample.get('prompt', '')).strip()
                    output_text = sample.get('output', sample.get('completion', '')).strip()
                    
                    if input_text:
                        dataset.append({
                            'input': input_text,
                            'output': output_text
                        })
                
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️  Ligne {line_num} invalide: {e}")
                    continue
        
        logger.info(f"✅ {len(dataset)} samples chargés")
        
        # Afficher quelques exemples
        logger.info("\n📋 Exemples de prompts:")
        for i, sample in enumerate(dataset[:3], 1):
            logger.info(f"\n  Sample {i}:")
            logger.info(f"    Input: {sample['input'][:100]}...")
            if sample['output']:
                logger.info(f"    Output: {sample['output'][:100]}...")
        
        return dataset
    
    except FileNotFoundError:
        logger.error(f"❌ Fichier introuvable: {filepath}")
        return []
    
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
        return []


def test_grpo_training(quick_test: bool = True):
    """
    Test d'entraînement GRPO avec Ministral-3-14B
    
    Args:
        quick_test: Si True, utilise des paramètres réduits pour test rapide (3-5 min)
                    Si False, utilise des paramètres complets (30-45 min)
    """
    
    print("="*70)
    print("🔥 ENTRAÎNEMENT GRPO - Ministral-3-14B")
    if quick_test:
        print("⚡ MODE RAPIDE (3-5 minutes)")
    else:
        print("🚀 MODE COMPLET (30-45 minutes)")
    print("="*70)
    
    # === ÉTAPE 1: CHARGER LE BATCH ===
    batch_path = r"D:\Dataset\dataset_Macompta.fr_semaine2_batch14.jsonl"
    
    # Pour test rapide, limiter à 3 samples
    max_samples = 3 if quick_test else None
    dataset = load_jsonl_batch(batch_path, max_samples=max_samples)
    
    if not dataset:
        logger.error("❌ Aucune donnée chargée - arrêt du test")
        return
    
    # Extraire seulement les prompts (inputs)
    prompts = [sample['input'] for sample in dataset]
    
    logger.info(f"\n📊 Dataset:")
    logger.info(f"   Total samples: {len(dataset)}")
    logger.info(f"   Total prompts: {len(prompts)}")
    
    # === ÉTAPE 2: CONFIGURER GRPO ===
    
    if quick_test:
        # ⚡ TEST RAPIDE (3-5 minutes)
        config = GRPOConfig(
            model_name="mistralai/Ministral-3-14B-Instruct-2512",
            vllm_url="http://localhost:8002/v1",              # Via tunnel SSH vers Venus
            reward_api_url="http://localhost:8086",           # API Ministral Verification
            reward_validation_level="quick",                  # Validation rapide sans RLHF
            
            # Paramètres réduits
            group_size=2,           # 2 réponses par prompt
            num_episodes=1,         # 1 seul épisode
            batch_size=2,           # 2 prompts par batch
            learning_rate=3e-4,
            
            # Génération
            temperature=0.8,
            top_p=0.95,
            max_tokens=256,         # Réponses courtes
            
            # Optimisation
            kl_coef=0.1,
            clip_range=0.2,
            normalize_advantages=True,
            
            # Logging
            log_every=1,
            save_every=1,
            checkpoint_dir="checkpoints/grpo_ministral_quick",
            verbose=True,
            
            domain="comptabilité"
        )
        
        logger.info(f"\n⚡ MODE TEST RAPIDE")
        logger.info(f"   Samples générés: {config.batch_size * config.group_size}")
        logger.info(f"   Temps estimé: 3-5 minutes")
    
    else:
        # 🚀 TEST COMPLET (30-45 minutes)
        config = GRPOConfig(
            model_name="mistralai/Ministral-3-14B-Instruct-2512",
            vllm_url="http://localhost:8002/v1",
            reward_api_url="http://localhost:8086",
            reward_validation_level="strict",                 # Validation RLHF complète
            
            # Paramètres complets
            group_size=8,           # 8 réponses par prompt
            num_episodes=5,         # 5 épisodes
            batch_size=4,           # 4 prompts par batch
            learning_rate=3e-4,
            
            # Génération
            temperature=0.8,
            top_p=0.95,
            max_tokens=512,
            
            # Optimisation
            kl_coef=0.1,
            clip_range=0.2,
            normalize_advantages=True,
            
            # Logging
            log_every=1,
            save_every=2,
            checkpoint_dir="checkpoints/grpo_ministral_full",
            verbose=True,
            
            domain="comptabilité"
        )
        
        logger.info(f"\n🚀 MODE TEST COMPLET")
        logger.info(f"   Samples générés par épisode: {config.batch_size * config.group_size}")
        logger.info(f"   Temps estimé: 30-45 minutes")
    
    logger.info(f"\n⚙️  Configuration GRPO:")
    logger.info(f"   Model: {config.model_name}")
    logger.info(f"   vLLM URL: {config.vllm_url}")
    logger.info(f"   Reward API: {config.reward_api_url}")
    logger.info(f"   Group size (G): {config.group_size}")
    logger.info(f"   Episodes: {config.num_episodes}")
    logger.info(f"   Batch size: {config.batch_size}")
    logger.info(f"   Learning rate: {config.learning_rate}")
    logger.info(f"   Temperature: {config.temperature}")
    logger.info(f"   Max tokens: {config.max_tokens}")
    logger.info(f"   Validation level: {config.reward_validation_level}")
    
    # === ÉTAPE 3: CRÉER LE TRAINER ===
    logger.info(f"\n🏗️  Création du GRPO Trainer...")
    
    try:
        trainer = GRPOTrainer(
            config=config,
            database=None,
            use_cache=True
        )
        
        logger.info(f"✅ Trainer créé avec succès")
    
    except Exception as e:
        logger.error(f"❌ Erreur création trainer: {e}")
        logger.error(f"\n⚠️  Vérifiez que:")
        logger.error(f"   1. Le tunnel SSH est actif: ssh -L 8002:localhost:8002 Venus")
        logger.error(f"   2. L'API Ministral tourne: python ministral_verification_api.py")
        return
    
    # === ÉTAPE 4: DÉFINIR LES CALLBACKS ===
    
    start_time = time.time()
    current_episode = [0]
    
    def on_log(message: str):
        """Callback pour les logs"""
        logger.info(message)
    
    def on_episode_complete(metrics: Dict[str, Any]):
        """Callback fin d'épisode"""
        current_episode[0] = metrics['episode']
        
        elapsed_total = time.time() - start_time
        
        logger.info("\n" + "="*60)
        logger.info(f"✅ ÉPISODE {metrics['episode']}/{config.num_episodes} TERMINÉ")
        logger.info("="*60)
        logger.info(f"Mean reward: {metrics['mean_reward']:.2f}")
        logger.info(f"Std reward: {metrics['std_reward']:.2f}")
        logger.info(f"Best reward: {metrics['max_reward']:.2f}")
        logger.info(f"Worst reward: {metrics['min_reward']:.2f}")
        logger.info(f"Positive advantages: {metrics['num_positive_advantages']}")
        logger.info(f"Negative advantages: {metrics['num_negative_advantages']}")
        logger.info(f"Temps épisode: {metrics['elapsed_time']:.2f}s")
        logger.info(f"Temps total: {elapsed_total:.2f}s ({elapsed_total/60:.1f} min)")
        
        # Estimation temps restant
        if metrics['episode'] < config.num_episodes:
            avg_time_per_episode = elapsed_total / metrics['episode']
            remaining_episodes = config.num_episodes - metrics['episode']
            eta = avg_time_per_episode * remaining_episodes
            logger.info(f"ETA: ~{eta:.0f}s (~{eta/60:.1f} min)")
        
        logger.info("="*60 + "\n")
    
    def on_group_complete(metrics: Dict[str, Any]):
        """Callback fin de groupe"""
        elapsed = time.time() - start_time
        
        logger.info(
            f"  ✅ Groupe {metrics['group_id']+1}/{config.batch_size} | "
            f"Reward={metrics['mean_reward']:.2f} | "
            f"Diversity={metrics.get('diversity', 0):.2f} | "
            f"Temps: {elapsed:.0f}s"
        )
    
    trainer.on_log = on_log
    trainer.on_episode_complete = on_episode_complete
    trainer.on_group_complete = on_group_complete
    
    # === ÉTAPE 5: VÉRIFICATIONS PRÉALABLES ===
    logger.info(f"\n⚠️  VÉRIFICATIONS PRÉALABLES:")
    logger.info(f"   1. Tunnel SSH actif ? → ssh -L 8002:localhost:8002 Venus")
    logger.info(f"   2. API Ministral lancée ? → python ministral_verification_api.py")
    logger.info(f"   3. Ministral répond sur port 8002 ?")
    logger.info(f"   4. API Verification répond sur port 8085 ?")
    logger.info(f"")
    
    input("Appuyez sur Entrée quand tout est prêt...")
    
    # === ÉTAPE 6: LANCER L'ENTRAÎNEMENT ===
    logger.info(f"\n🚀 DÉMARRAGE DE L'ENTRAÎNEMENT")
    logger.info(f"="*70)
    logger.info(f"Heure de début: {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # Entraîner sur tous les prompts
        history = trainer.train(
            prompts=prompts,
            num_episodes=config.num_episodes,
            system_prompt="Tu es un expert en comptabilité française. Réponds de manière claire et professionnelle."
        )
        
        # === ÉTAPE 7: AFFICHER LE RÉSUMÉ ===
        summary = trainer.get_summary()
        
        training_stats = summary.get("training", {})
        metrics_stats = summary.get("metrics", {})
        cache_stats = summary.get("cache", {})
        
        total_time = time.time() - start_time
        
        logger.info("\n" + "="*70)
        logger.info("🎉 ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("="*70)
        logger.info(f"Temps total: {total_time:.2f}s ({total_time/60:.2f} min)")
        logger.info(f"Heure de fin: {datetime.now().strftime('%H:%M:%S')}")
        
        logger.info(f"\n📊 STATISTIQUES D'ENTRAÎNEMENT:")
        logger.info(f"   Episodes complétés: {training_stats.get('episode', 0)}")
        logger.info(f"   Groupes traités: {training_stats.get('total_groups', 0)}")
        logger.info(f"   Samples générés: {training_stats.get('total_samples', 0)}")
        logger.info(f"   Temps moyen/épisode: {total_time/config.num_episodes:.2f}s")
        
        logger.info(f"\n📈 MÉTRIQUES FINALES:")
        logger.info(f"   Mean reward: {metrics_stats.get('mean_reward', 0):.2f}")
        logger.info(f"   Std reward: {metrics_stats.get('std_reward', 0):.2f}")
        logger.info(f"   Min reward: {metrics_stats.get('min_reward', 0):.2f}")
        logger.info(f"   Max reward: {metrics_stats.get('max_reward', 0):.2f}")
        logger.info(f"   Mean advantage: {metrics_stats.get('mean_advantage', 0):.4f}")
        
        if cache_stats:
            logger.info(f"\n💾 STATISTIQUES DU CACHE:")
            logger.info(f"   Taille du cache: {cache_stats.get('cache_size', 0)}")
            logger.info(f"   Cache hits: {cache_stats.get('cache_hits', 0)}")
            logger.info(f"   Cache misses: {cache_stats.get('cache_misses', 0)}")
            logger.info(f"   Hit rate: {cache_stats.get('hit_rate', 0)*100:.1f}%")
        
        logger.info("\n" + "="*70)
        logger.info("✅ TEST GRPO TERMINÉ AVEC SUCCÈS")
        logger.info("="*70)
        
        # Sauvegarder les métriques
        metrics_path = f"grpo_ministral_{'quick' if quick_test else 'full'}_metrics.json"
        trainer.metrics.save_to_file(metrics_path)
        logger.info(f"\n💾 Métriques sauvegardées: {metrics_path}")
        
        # Résumé final concis
        print("\n" + "="*70)
        print("📊 RÉSUMÉ FINAL")
        print("="*70)
        print(f"🤖 Modèle: Ministral-3-14B-Instruct-2512")
        print(f"✅ {training_stats.get('total_samples', 0)} samples générés en {total_time/60:.1f} min")
        print(f"🎯 Mean reward: {metrics_stats.get('mean_reward', 0):.2f}")
        print(f"⭐ Best reward: {metrics_stats.get('max_reward', 0):.2f}")
        print(f"💾 Cache hit rate: {cache_stats.get('hit_rate', 0)*100:.1f}%")
        print(f"📁 Checkpoints: {config.checkpoint_dir}")
        print("="*70)
    
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Entraînement interrompu par l'utilisateur")
        logger.info(f"Temps écoulé: {(time.time() - start_time)/60:.1f} min")
        logger.info(f"Progression: Épisode {current_episode[0]}/{config.num_episodes}")
    
    except Exception as e:
        logger.error(f"\n❌ Erreur durant l'entraînement: {e}", exc_info=True)


if __name__ == "__main__":
    # ⚡ CHOISIR LE MODE DE TEST
    
    # MODE 1: Test rapide (3-5 minutes) - RECOMMANDÉ POUR DÉBUTER
    test_grpo_training(quick_test=True)
    
    # MODE 2: Test complet (30-45 minutes) - Décommenter pour utiliser
    # test_grpo_training(quick_test=False)