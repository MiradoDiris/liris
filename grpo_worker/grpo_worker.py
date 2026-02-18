#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/workers/grpo_worker.py - Worker PyQt5 pour GRPO
"""

from PyQt5.QtCore import QThread, pyqtSignal
from typing import Dict, Any
import logging

from rl_grpo.config import GRPOConfig
from rl_grpo.grpo_trainer import GRPOTrainer

logger = logging.getLogger(__name__)


class GRPOWorker(QThread):
    """Worker thread pour entraînement GRPO"""
    
    # Signaux
    progress = pyqtSignal(dict)      # Progression (métriques groupe/épisode)
    finished = pyqtSignal(dict)      # Fin de l'entraînement (résumé)
    error = pyqtSignal(str)          # Erreur
    log = pyqtSignal(str)            # Message de log
    episode_complete = pyqtSignal(dict)  # Épisode terminé
    group_complete = pyqtSignal(dict)    # Groupe terminé
    
    def __init__(
        self,
        project_name: str,
        batch_number: int,
        config: GRPOConfig,
        database,
        batch_data: Dict[str, Any] = None,  # Nouveau paramètre optionnel
        parent=None
    ):
        super().__init__(parent)
        
        self.project_name = project_name
        self.batch_number = batch_number
        self.config = config
        self.database = database
        self.batch_data = batch_data  # Données du batch (si uploadé)
        
        self.trainer = None
        self._stop_requested = False
    
    def run(self):
        """Exécute l'entraînement GRPO"""
        try:
            self.log.emit("🤖 Initialisation GRPO Trainer...")
            
            # Créer le trainer
            # ✅ FIX: Cache désactivé car inutile en GRPO (réponses toujours uniques)
            self.trainer = GRPOTrainer(
                config=self.config,
                database=self.database,
                use_cache=False  # ❌ Cache inutile: chaque (input,output) est unique
            )
            
            # Connecter les callbacks
            self.trainer.on_log = self._on_log
            self.trainer.on_episode_complete = self._on_episode_complete
            self.trainer.on_group_complete = self._on_group_complete
            
            self.log.emit(f"📦 Projet: {self.project_name}")
            if self.batch_data:
                self.log.emit(f"📊 Batch: Uploadé")
            else:
                self.log.emit(f"📊 Batch: #{self.batch_number}")
            self.log.emit(f"⚙️  Group size: {self.config.group_size}")
            self.log.emit(f"📈 Episodes: {self.config.num_episodes}")
            self.log.emit(f"🎯 Batch size: {self.config.batch_size}")
            self.log.emit("")
            
            # Lancer l'entraînement
            history = self.trainer.train_from_batch(
                project_name=self.project_name,
                batch_number=self.batch_number,
                num_episodes=self.config.num_episodes,
                batch_data=self.batch_data  # Passer batch_data si disponible
            )
            
            # Vérifier si arrêt demandé
            if self._stop_requested:
                self.log.emit("\n⚠️  Entraînement arrêté par l'utilisateur")
                self.error.emit("Entraînement arrêté")
                return
            
            # Obtenir résumé
            summary = self.trainer.get_summary()
            
            # Stats finales
            training = summary.get("training", {})
            metrics = summary.get("metrics", {})
            cache = summary.get("cache", {})
            
            self.log.emit("")
            self.log.emit("="*60)
            self.log.emit("🎉 ENTRAÎNEMENT TERMINÉ")
            self.log.emit("="*60)
            self.log.emit(f"Episodes: {training.get('episode', 0)}")
            self.log.emit(f"Groupes traités: {training.get('total_groups', 0)}")
            self.log.emit(f"Samples générés: {training.get('total_samples', 0)}")
            self.log.emit(f"Mean reward: {metrics.get('mean_reward', 0):.2f}")
            self.log.emit(f"Best reward: {metrics.get('max_reward', 0):.2f}")
            
            # Note: Plus de stats de cache car désactivé
            if cache and cache.get('cache_size', 0) > 0:
                self.log.emit(f"\n⚠️  Cache activé (non recommandé en GRPO)")
                self.log.emit(f"Cache: {cache.get('cache_size', 0)} entrées")
                self.log.emit(f"Hit rate: {cache.get('hit_rate', 0)*100:.1f}%")
            
            # Envoyer résumé
            self.finished.emit(summary)
            
        except Exception as e:
            logger.error(f"❌ Erreur GRPO: {e}", exc_info=True)
            self.error.emit(str(e))
    
    def _on_log(self, message: str):
        """Callback pour logs"""
        if not self._stop_requested:
            self.log.emit(message)
    
    def _on_episode_complete(self, metrics: Dict[str, Any]):
        """Callback fin d'épisode"""
        if not self._stop_requested:
            self.episode_complete.emit(metrics)
            self.progress.emit({
                "type": "episode",
                "data": metrics
            })
    
    def _on_group_complete(self, metrics: Dict[str, Any]):
        """Callback fin de groupe"""
        if not self._stop_requested:
            self.group_complete.emit(metrics)
            self.progress.emit({
                "type": "group",
                "data": metrics
            })
    
    def stop(self):
        """Arrête l'entraînement"""
        self._stop_requested = True
        self.log.emit("\n⚠️  Arrêt demandé...")