#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/reward_model.py - Interface avec l'API de vérification (OPTIMISÉ GRPO)

OPTIMISATIONS POUR GRPO:
- RLHF désactivé (trop lent : 8×20s = 160s)
- RL classique uniquement (rapide : <5s pour 8 réponses)
- Timeout 120s (sécurité)
- Validation level: quick ou standard (pas strict)
"""

import requests
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RewardResult:
    """Résultat d'une évaluation par le reward model"""
    sample_id: int
    input_text: str
    output_text: str
    quality_score: float  # 0-100
    status: str  # valid, warning, invalid
    issues: List[Dict[str, Any]]
    suggestions: List[str]


class RewardModel:
    """
    Interface avec l'API de vérification pour obtenir les rewards
    
    OPTIMISÉ POUR GRPO:
    - RLHF désactivé (trop lent)
    - Validation rapide uniquement
    """
    
    def __init__(
        self, 
        api_url: str = "http://localhost:8086", 
        validation_level: str = "standard"  # ✅ standard au lieu de strict
    ):
        self.api_url = api_url
        self.validation_level = validation_level
        self.timeout = 180  # ✅ Timeout augmenté à 120s
        
        # Vérifier que l'API est accessible
        self._check_health()
        
        logger.info(f"🎯 Reward Model configuré pour GRPO:")
        logger.info(f"   • API: {api_url}")
        logger.info(f"   • Validation: {validation_level} (RL classique)")
        logger.info(f"   • RLHF: ❌ Désactivé (trop lent pour GRPO)")
        logger.info(f"   • Timeout: {self.timeout}s")
    
    def _check_health(self):
        """Vérifie que l'API est accessible"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"✅ Reward Model API accessible: {self.api_url}")
            else:
                logger.warning(f"⚠️  Reward Model API retourne status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Reward Model API non accessible: {e}")
            raise ConnectionError(f"Impossible de se connecter à l'API de reward: {self.api_url}")
    
    def compute_reward(
        self,
        input_text: str,
        output_text: str,
        sample_id: int = 0
    ) -> Tuple[float, RewardResult]:
        """
        Calcule le reward pour une paire input/output
        
        Args:
            input_text: Texte d'entrée (prompt)
            output_text: Texte de sortie (réponse générée)
            sample_id: ID du sample (optionnel)
        
        Returns:
            (reward, RewardResult)
            reward: Score 0-100
        """
        try:
            response = requests.post(
                f"{self.api_url}/verify-batch",
                params={
                    "validation_level": self.validation_level,  # standard
                    "rlhf_validation": False,  # ✅ RLHF DÉSACTIVÉ
                    "domain": "comptabilité",
                    "enable_cache": True
                },
                json=[{
                    "sample_id": sample_id,
                    "input": input_text,
                    "output": output_text
                }],
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur API reward: {response.status_code}")
                return 0.0, self._create_error_result(sample_id, input_text, output_text, "error")
            
            data = response.json()
            
            if not data.get("results"):
                logger.error("❌ Pas de résultats dans la réponse")
                return 0.0, self._create_error_result(sample_id, input_text, output_text, "error")
            
            result_data = data["results"][0]
            
            # Extraire les informations
            quality_score = result_data.get("quality_score", 0.0)
            status = result_data.get("status", "unknown")
            issues = result_data.get("issues", [])
            suggestions = result_data.get("suggestions", [])
            
            reward_result = RewardResult(
                sample_id=sample_id,
                input_text=input_text,
                output_text=output_text,
                quality_score=quality_score,
                status=status,
                issues=issues,
                suggestions=suggestions
            )
            
            logger.debug(
                f"Reward computed: {quality_score:.2f} "
                f"(status: {status}, issues: {len(issues)})"
            )
            
            return quality_score, reward_result
        
        except requests.Timeout:
            logger.error(f"⏰ Timeout lors de l'appel API reward (>{self.timeout}s)")
            return 0.0, self._create_error_result(sample_id, input_text, output_text, "timeout")
        
        except Exception as e:
            logger.error(f"❌ Erreur reward computation: {e}")
            return 0.0, self._create_error_result(sample_id, input_text, output_text, "error")
    
    def compute_batch_rewards(
        self,
        pairs: List[Tuple[str, str]]
    ) -> List[Tuple[float, RewardResult]]:
        """
        Calcule les rewards pour un batch de paires input/output
        
        ✅ OPTIMISÉ: Appelle l'API UNE SEULE FOIS pour tout le batch
        ✅ SANS RLHF: Rapide (<5s pour 8 réponses)
        
        Args:
            pairs: Liste de tuples (input_text, output_text)
        
        Returns:
            Liste de tuples (reward, RewardResult)
        """
        if not pairs:
            return []
        
        logger.info(f"🎯 Calcul batch rewards pour {len(pairs)} paires (RL classique)...")
        
        try:
            # Préparer le batch
            batch_samples = [
                {
                    "sample_id": idx,
                    "input": input_text,
                    "output": output_text
                }
                for idx, (input_text, output_text) in enumerate(pairs)
            ]
            
            # ✅ UN SEUL appel API pour tout le batch
            logger.debug(f"📤 Envoi de {len(batch_samples)} samples à l'API...")
            
            response = requests.post(
                f"{self.api_url}/verify-batch",
                params={
                    "validation_level": self.validation_level,  # standard
                    "rlhf_validation": False,  # ✅ RLHF DÉSACTIVÉ (critique!)
                    "domain": "comptabilité",
                    "enable_cache": True
                },
                json=batch_samples,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur API batch: {response.status_code}")
                # Retourner des rewards de 0 pour toutes les paires
                return [
                    (0.0, self._create_error_result(idx, input_text, output_text, "error"))
                    for idx, (input_text, output_text) in enumerate(pairs)
                ]
            
            data = response.json()
            results = data.get("results", [])
            
            if len(results) != len(pairs):
                logger.warning(
                    f"⚠️  Nombre de résultats ({len(results)}) != "
                    f"nombre de paires ({len(pairs)})"
                )
            
            # Construire les résultats
            batch_results = []
            for idx, (input_text, output_text) in enumerate(pairs):
                if idx < len(results):
                    result_data = results[idx]
                    quality_score = result_data.get("quality_score", 0.0)
                    status = result_data.get("status", "unknown")
                    issues = result_data.get("issues", [])
                    suggestions = result_data.get("suggestions", [])
                    
                    reward_result = RewardResult(
                        sample_id=idx,
                        input_text=input_text,
                        output_text=output_text,
                        quality_score=quality_score,
                        status=status,
                        issues=issues,
                        suggestions=suggestions
                    )
                    
                    batch_results.append((quality_score, reward_result))
                else:
                    # Résultat manquant
                    batch_results.append(
                        (0.0, self._create_error_result(idx, input_text, output_text, "missing"))
                    )
            
            # Stats
            rewards = [r for r, _ in batch_results]
            mean_reward = sum(rewards) / len(rewards) if rewards else 0
            
            logger.info(
                f"✅ Batch rewards calculés: "
                f"mean={mean_reward:.2f}, "
                f"min={min(rewards) if rewards else 0:.2f}, "
                f"max={max(rewards) if rewards else 0:.2f}"
            )
            
            return batch_results
        
        except requests.Timeout:
            logger.error(f"⏰ Timeout batch API (>{self.timeout}s)")
            logger.error(f"   ⚠️  Vérifier que RLHF est bien désactivé dans l'API")
            return [
                (0.0, self._create_error_result(idx, input_text, output_text, "timeout"))
                for idx, (input_text, output_text) in enumerate(pairs)
            ]
        
        except Exception as e:
            logger.error(f"❌ Erreur batch computation: {e}")
            return [
                (0.0, self._create_error_result(idx, input_text, output_text, "error"))
                for idx, (input_text, output_text) in enumerate(pairs)
            ]
    
    def _create_error_result(
        self, 
        sample_id: int, 
        input_text: str, 
        output_text: str, 
        status: str
    ) -> RewardResult:
        """Crée un RewardResult d'erreur"""
        return RewardResult(
            sample_id=sample_id,
            input_text=input_text,
            output_text=output_text,
            quality_score=0.0,
            status=status,
            issues=[],
            suggestions=[]
        )
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques de l'API"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# CACHE NON RECOMMANDÉ EN GRPO
# ============================================================================

class CachedRewardModel(RewardModel):
    """
    Reward Model avec cache
    
    ⚠️  NON RECOMMANDÉ EN GRPO car chaque (input, output) est unique
    """
    
    def __init__(self, api_url: str = "http://localhost:8086", validation_level: str = "standard"):
        super().__init__(api_url, validation_level)
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.warning(
            "⚠️  CachedRewardModel utilisé. "
            "Le cache sera inefficace (0% hits attendus) en GRPO."
        )
    
    def _get_cache_key(self, input_text: str, output_text: str) -> str:
        """Génère une clé de cache"""
        import hashlib
        combined = f"{input_text}|{output_text}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def compute_reward(
        self,
        input_text: str,
        output_text: str,
        sample_id: int = 0
    ) -> Tuple[float, RewardResult]:
        """Compute reward avec cache"""
        
        # Vérifier cache
        cache_key = self._get_cache_key(input_text, output_text)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            logger.debug(f"✅ Cache hit ({self.cache_hits} hits)")
            reward, result = self.cache[cache_key]
            result.sample_id = sample_id
            return reward, result
        
        # Cache miss
        self.cache_misses += 1
        logger.debug(f"❌ Cache miss ({self.cache_misses} misses)")
        
        reward, result = super().compute_reward(input_text, output_text, sample_id)
        
        # Sauvegarder en cache
        self.cache[cache_key] = (reward, result)
        
        return reward, result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les stats du cache"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        
        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate
        }
    
    def clear_cache(self):
        """Vide le cache"""
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("🗑️  Cache cleared")