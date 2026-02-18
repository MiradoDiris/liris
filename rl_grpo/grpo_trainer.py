#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/grpo_trainer.py - Trainer principal GRPO (OPTIMISÉ)

Optimisations:
1. Cache désactivé par défaut (inutile en GRPO)
2. Batch API pour les rewards (8× plus rapide)
3. Timeouts augmentés pour éviter les erreurs
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time

from openai import OpenAI
import httpx

from rl_grpo.config import GRPOConfig
from rl_grpo.reward_model import RewardModel, CachedRewardModel
from rl_grpo.metrics import (
    MetricsTracker,
    GroupMetrics,
    compute_group_metrics,
    compute_diversity_score
)
from rl_grpo.data_loader import DataLoader, DataBatcher

logger = logging.getLogger(__name__)


class GRPOTrainer:
    """Trainer principal pour GRPO (version optimisée)"""
    
    def __init__(
        self,
        config: GRPOConfig,
        database=None,
        use_cache: bool = False  # ✅ Désactivé par défaut (inutile en GRPO)
    ):
        """
        Args:
            config: Configuration GRPO
            database: Instance de la base de données (optionnel)
            use_cache: Utiliser le cache pour les rewards (non recommandé en GRPO)
        """
        self.config = config
        self.database = database
        
        # Client vLLM pour génération
        self.client = OpenAI(
            base_url=config.vllm_url,
            api_key="EMPTY",
            timeout=httpx.Timeout(600.0, connect=10.0)
        )
        
        # Reward model
        if use_cache:
            logger.warning("⚠️  Cache activé (non recommandé en GRPO)")
            self.reward_model = CachedRewardModel(
                config.reward_api_url,
                config.reward_validation_level
            )
        else:
            self.reward_model = RewardModel(
                config.reward_api_url,
                config.reward_validation_level
            )
        
        # Data loader
        if database:
            self.data_loader = DataLoader(database)
        else:
            self.data_loader = None
        
        # Metrics tracker
        self.metrics = MetricsTracker()
        
        # État de l'entraînement
        self.episode = 0
        self.total_groups_processed = 0
        self.total_samples_generated = 0
        
        # Callback pour UI
        self.on_episode_complete: Optional[Callable] = None
        self.on_group_complete: Optional[Callable] = None
        self.on_log: Optional[Callable] = None
        
        logger.info("🤖 GRPO Trainer initialisé (version optimisée)")
        logger.info(f"   Model: {config.model_name}")
        logger.info(f"   Group size (G): {config.group_size}")
        logger.info(f"   Batch size: {config.batch_size}")
        logger.info(f"   Learning rate: {config.learning_rate}")
        logger.info(f"   Cache: {'✅ Activé' if use_cache else '❌ Désactivé (recommandé)'}")
    
    def _log(self, message: str):
        """Envoie un log (pour UI)"""
        logger.info(message)
        if self.on_log:
            self.on_log(message)
    
    def generate_group_responses(
        self,
        prompt: str,
        system_prompt: str = ""
    ) -> List[str]:
        """
        Génère G réponses pour un prompt donné
        
        Args:
            prompt: Prompt (input)
            system_prompt: Prompt système optionnel
        
        Returns:
            Liste de G réponses générées
        """
        responses = []
        
        logger.debug(f"📝 Génération de {self.config.group_size} réponses...")
        
        for g in range(self.config.group_size):
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                completion = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    n=1
                )
                
                if completion.choices:
                    response_text = completion.choices[0].message.content
                    
                    if response_text is None:
                        logger.warning(f"  ⚠️  Réponse {g+1}: content est None")
                        responses.append("")
                    elif not isinstance(response_text, str):
                        logger.error(f"  ❌ Réponse {g+1}: type inattendu {type(response_text)}")
                        responses.append("")
                    else:
                        responses.append(response_text)
                        self.total_samples_generated += 1
                        logger.debug(f"  ✅ Réponse {g+1}/{self.config.group_size}: {len(response_text)} chars")
                else:
                    responses.append("")
                    logger.warning(f"  ⚠️  Réponse {g+1} vide (pas de choices)")
            
            except Exception as e:
                logger.error(f"  ❌ Erreur génération {g+1}: {e}")
                responses.append("")
        
        return responses
    
    def compute_group_rewards(
        self,
        prompt: str,
        responses: List[str]
    ) -> List[float]:
        """
        Calcule les rewards R_g pour chaque réponse du groupe
        
        ✅ OPTIMISÉ: Utilise l'API batch (1 appel au lieu de G appels)
        
        Args:
            prompt: Prompt original
            responses: Liste des G réponses
        
        Returns:
            Liste des G rewards (scores 0-100)
        """
        # Filtrer les réponses valides
        valid_responses = [
            (idx, r) for idx, r in enumerate(responses) 
            if r and isinstance(r, str) and r.strip()
        ]
        
        if not valid_responses:
            logger.warning("⚠️  Aucune réponse valide dans le groupe")
            return [0.0] * len(responses)
        
        # Préparer les paires pour le batch
        pairs = [(prompt, response) for _, response in valid_responses]
        
        # ✅ OPTIMISATION: 1 SEUL appel API pour tout le groupe
        logger.debug(f"🎯 Calcul batch rewards pour {len(pairs)} réponses...")
        start_time = time.time()
        
        batch_results = self.reward_model.compute_batch_rewards(pairs)
        
        elapsed = time.time() - start_time
        logger.debug(f"✅ Batch rewards calculés en {elapsed:.2f}s")
        
        # Reconstruire la liste complète avec 0.0 pour les réponses vides
        rewards = [0.0] * len(responses)
        for (original_idx, _), (reward, result) in zip(valid_responses, batch_results):
            rewards[original_idx] = reward
            logger.debug(
                f"  ✅ Reward {original_idx+1}: {reward:.2f} "
                f"(status: {result.status})"
            )
        
        return rewards
    
    def process_group(
        self,
        group_id: int,
        prompt: str,
        system_prompt: str = ""
    ) -> GroupMetrics:
        """
        Traite un groupe complet : génération + rewards + advantages
        
        Args:
            group_id: ID du groupe
            prompt: Prompt à traiter
            system_prompt: Prompt système optionnel
        
        Returns:
            GroupMetrics avec toutes les métriques
        """
        start_time = time.time()
        
        # 1. Générer G réponses
        responses = self.generate_group_responses(prompt, system_prompt)
        
        # 2. Calculer les rewards (optimisé: batch API)
        rewards = self.compute_group_rewards(prompt, responses)
        
        # 3. Calculer les advantages selon formule GRPO
        group_metrics = compute_group_metrics(
            group_id=group_id,
            prompt=prompt,
            responses=responses,
            rewards=rewards,
            epsilon=self.config.advantage_epsilon,
            normalize=self.config.normalize_advantages
        )
        
        # 4. Calculer diversité
        diversity = compute_diversity_score(responses)
        
        # Stats groupe
        elapsed = time.time() - start_time
        
        logger.debug(f"\n{'='*60}")
        logger.debug(f"GROUPE {group_id} TERMINÉ")
        logger.debug(f"{'='*60}")
        logger.debug(f"Mean reward: {group_metrics.mean_reward:.2f}")
        logger.debug(f"Std reward: {group_metrics.std_reward:.2f}")
        logger.debug(f"Best reward: {max(rewards):.2f}")
        logger.debug(f"Worst reward: {min(rewards):.2f}")
        logger.debug(f"Diversité: {diversity:.2f}")
        logger.debug(f"Temps: {elapsed:.2f}s")
        logger.debug(f"{'='*60}\n")
        
        # Incrémenter compteur
        self.total_groups_processed += 1
        
        # Callback UI
        if self.on_group_complete:
            self.on_group_complete({
                "group_id": group_id,
                "mean_reward": group_metrics.mean_reward,
                "std_reward": group_metrics.std_reward,
                "best_reward": max(rewards),
                "worst_reward": min(rewards),
                "diversity": diversity,
                "elapsed": elapsed
            })
        
        return group_metrics
    
    def train_episode(
        self,
        prompts: List[str],
        system_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        Entraîne un épisode sur un batch de prompts
        
        Args:
            prompts: Liste des prompts du batch
            system_prompt: Prompt système optionnel
        
        Returns:
            Métriques de l'épisode
        """
        self.episode += 1
        start_time = time.time()
        
        self._log(f"\n{'='*60}")
        self._log(f"📊 ÉPISODE {self.episode}")
        self._log(f"{'='*60}")
        self._log(f"Prompts dans le batch: {len(prompts)}")
        self._log(f"Groupe size: {self.config.group_size}")
        self._log(f"Total samples à générer: {len(prompts) * self.config.group_size}")
        
        episode_groups = []
        all_rewards = []
        all_advantages = []
        
        # Traiter chaque prompt
        for group_id, prompt in enumerate(prompts):
            self._log(f"\n🔄 Groupe {group_id + 1}/{len(prompts)}")
            self._log(f"📝 Prompt: {prompt[:100]}...")
            
            # Traiter le groupe
            group_metrics = self.process_group(
                group_id=group_id,
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            episode_groups.append(group_metrics)
            all_rewards.extend(group_metrics.rewards)
            all_advantages.extend(group_metrics.advantages)
            
            # Ajouter aux métriques globales
            self.metrics.add_group(group_metrics)
        
        # Calculer métriques de l'épisode
        import numpy as np
        
        elapsed = time.time() - start_time
        
        episode_metrics = {
            "episode": self.episode,
            "num_groups": len(episode_groups),
            "num_samples": len(all_rewards),
            "mean_reward": float(np.mean(all_rewards)),
            "std_reward": float(np.std(all_rewards)),
            "min_reward": float(np.min(all_rewards)),
            "max_reward": float(np.max(all_rewards)),
            "mean_advantage": float(np.mean(all_advantages)),
            "std_advantage": float(np.std(all_advantages)),
            "num_positive_advantages": sum(1 for a in all_advantages if a > 0),
            "num_negative_advantages": sum(1 for a in all_advantages if a < 0),
            "elapsed_time": elapsed,
            "samples_per_second": len(all_rewards) / elapsed if elapsed > 0 else 0
        }
        
        # Sauvegarder dans tracker
        self.metrics.add_episode(episode_metrics)
        
        # Log résumé
        self._log(f"\n{'='*60}")
        self._log(f"✅ ÉPISODE {self.episode} TERMINÉ")
        self._log(f"{'='*60}")
        self._log(f"Mean reward: {episode_metrics['mean_reward']:.2f}")
        self._log(f"Std reward: {episode_metrics['std_reward']:.2f}")
        self._log(f"Positive advantages: {episode_metrics['num_positive_advantages']}")
        self._log(f"Negative advantages: {episode_metrics['num_negative_advantages']}")
        self._log(f"Temps: {elapsed:.2f}s ({episode_metrics['samples_per_second']:.2f} samples/s)")
        self._log(f"{'='*60}\n")
        
        # Callback UI
        if self.on_episode_complete:
            self.on_episode_complete(episode_metrics)
        
        return episode_metrics
    
    def train_from_batch(
        self,
        project_name: str,
        batch_number: int,
        num_episodes: Optional[int] = None,
        system_prompt: str = "",
        batch_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Entraîne à partir d'un batch de la base de données ou de données fournies
        
        Args:
            project_name: Nom du projet
            batch_number: Numéro du batch
            num_episodes: Nombre d'épisodes (par défaut config.num_episodes)
            system_prompt: Prompt système optionnel
            batch_data: Données du batch (optionnel, sinon chargé depuis DB)
        
        Returns:
            Historique des métriques
        """
        # Si batch_data fourni, l'utiliser directement
        if batch_data is not None:
            self._log("📦 Utilisation des données de batch fournies")
            # Extraire les prompts directement
            prompts = []
            data = batch_data.get('data', batch_data)
            combinations = data.get('combinations', [])
            
            for combo in combinations:
                samples = combo.get('samples', [])
                for sample in samples:
                    input_text = sample.get('input', '')
                    if input_text and input_text.strip():
                        prompts.append(input_text.strip())
            
            if not prompts:
                raise ValueError("Aucun prompt trouvé dans batch_data")
            
            batch_name = data.get('batch_name', 'Batch uploadé')
            
            self._log(f"\n{'='*70}")
            self._log(f"🎯 DÉMARRAGE ENTRAÎNEMENT GRPO")
            self._log(f"{'='*70}")
            self._log(f"Projet: {project_name}")
            self._log(f"Batch: {batch_name}")
            self._log(f"Prompts disponibles: {len(prompts)}")
            self._log(f"Episodes: {num_episodes or self.config.num_episodes}")
            self._log(f"Batch size: {self.config.batch_size}")
            self._log(f"Group size: {self.config.group_size}")
            self._log(f"{'='*70}\n")
            
            # Entraîner
            return self.train(
                prompts=prompts,
                num_episodes=num_episodes,
                system_prompt=system_prompt
            )
        
        # Sinon, charger depuis la DB
        if not self.data_loader:
            raise ValueError("Data loader non initialisé (database requise)")
        
        # Charger le batch
        batch_data = self.data_loader.load_batch_data(project_name, batch_number)
        if not batch_data:
            raise ValueError(f"Impossible de charger le batch {batch_number}")
        
        # Extraire les prompts
        prompts = self.data_loader.extract_prompts(batch_data)
        if not prompts:
            raise ValueError("Aucun prompt trouvé dans le batch")
        
        # Info batch
        batch_info = self.data_loader.get_batch_info(batch_data)
        
        self._log(f"\n{'='*70}")
        self._log(f"🎯 DÉMARRAGE ENTRAÎNEMENT GRPO")
        self._log(f"{'='*70}")
        self._log(f"Projet: {project_name}")
        self._log(f"Batch: {batch_info['batch_name']} (#{batch_info['batch_number']})")
        self._log(f"Prompts disponibles: {len(prompts)}")
        self._log(f"Episodes: {num_episodes or self.config.num_episodes}")
        self._log(f"Batch size: {self.config.batch_size}")
        self._log(f"Group size: {self.config.group_size}")
        self._log(f"{'='*70}\n")
        
        # Entraîner
        return self.train(
            prompts=prompts,
            num_episodes=num_episodes,
            system_prompt=system_prompt
        )
    
    def train(
        self,
        prompts: List[str],
        num_episodes: Optional[int] = None,
        system_prompt: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Entraîne sur une liste de prompts
        
        Args:
            prompts: Liste des prompts
            num_episodes: Nombre d'épisodes (par défaut config.num_episodes)
            system_prompt: Prompt système optionnel
        
        Returns:
            Historique des métriques
        """
        if not prompts:
            raise ValueError("Liste de prompts vide")
        
        if num_episodes is None:
            num_episodes = self.config.num_episodes
        
        self._log(f"📊 Entraînement: {num_episodes} épisodes sur {len(prompts)} prompts")
        
        # Créer batcher
        batcher = DataBatcher(
            prompts=prompts,
            batch_size=self.config.batch_size,
            shuffle=True
        )
        
        # Entraîner
        for ep in range(num_episodes):
            # Échantillonner un batch
            try:
                batch_prompts = next(iter(batcher))
            except StopIteration:
                # Reset si on a épuisé les prompts
                batcher.reset()
                batch_prompts = next(iter(batcher))
            
            # Entraîner l'épisode
            episode_metrics = self.train_episode(batch_prompts, system_prompt)
            
            # Sauvegarder checkpoint si nécessaire
            if (ep + 1) % self.config.save_every == 0:
                self._save_checkpoint()
        
        self._log(f"\n{'='*70}")
        self._log(f"🎉 ENTRAÎNEMENT TERMINÉ")
        self._log(f"{'='*70}")
        self._log(f"Total épisodes: {self.episode}")
        self._log(f"Total groupes: {self.total_groups_processed}")
        self._log(f"Total samples: {self.total_samples_generated}")
        
        # Stats finales
        final_stats = self.metrics.get_current_stats()
        self._log(f"\n📊 STATISTIQUES FINALES:")
        self._log(f"Mean reward: {final_stats['mean_reward']:.2f}")
        self._log(f"Std reward: {final_stats['std_reward']:.2f}")
        self._log(f"Min reward: {final_stats['min_reward']:.2f}")
        self._log(f"Max reward: {final_stats['max_reward']:.2f}")
        self._log(f"{'='*70}\n")
        
        return self.metrics.get_episode_history()
    
    def _save_checkpoint(self):
        """Sauvegarde un checkpoint"""
        import os
        import json
        
        os.makedirs(self.config.checkpoint_dir, exist_ok=True)
        
        checkpoint_path = os.path.join(
            self.config.checkpoint_dir,
            f"checkpoint_episode_{self.episode}.json"
        )
        
        checkpoint_data = {
            "episode": self.episode,
            "total_groups": self.total_groups_processed,
            "total_samples": self.total_samples_generated,
            "config": self.config.to_dict(),
            "metrics": self.metrics.get_current_stats(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        
        self._log(f"💾 Checkpoint sauvegardé: {checkpoint_path}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de l'entraînement"""
        stats = self.metrics.get_current_stats()
        
        # Stats du cache si applicable
        cache_stats = {}
        if isinstance(self.reward_model, CachedRewardModel):
            cache_stats = self.reward_model.get_cache_stats()
        
        return {
            "training": {
                "episode": self.episode,
                "total_groups": self.total_groups_processed,
                "total_samples": self.total_samples_generated
            },
            "metrics": stats,
            "cache": cache_stats,
            "config": self.config.to_dict()
        }