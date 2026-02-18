#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Trainer pour le Graph Learner Neural - VERSION CORRIGÉE

✅ AJOUTS:
- Support pour adjacency_matrix et attention_mask
- Logging détaillé des métriques structurelles
"""

import logging
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import numpy as np

from .models import NeuralGraphLearner
from .dataset import OnlineLearningBuffer

logger = logging.getLogger(__name__)


class NeuralGraphLearnerTrainer:
    """
    🆕 CORRIGÉ: Entraîneur avec support graph attention
    """
    
    def __init__(self, config, feature_extractor, device: str = 'cpu'):
        self.config = config
        self.feature_extractor = feature_extractor
        self.device = device
        
        # Calculer dimensions
        feature_dims = feature_extractor.get_feature_dims()
        node_input_dim = feature_dims['node']
        context_input_dim = feature_dims['context']
        
        # Créer modèle
        self.model = NeuralGraphLearner(
            node_input_dim=node_input_dim,
            context_input_dim=context_input_dim,
            config=config
        ).to(device)
        
        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay
        )
        
        # Loss function
        self.criterion = nn.BCELoss()
        
        # Online learning buffer
        self.online_buffer = OnlineLearningBuffer(
            max_size=config.online_buffer_size,
            feature_extractor=feature_extractor,
            max_nodes=config.max_nodes_per_structure
        )
        
        self.update_counter = 0
        
        logger.info(f"✅ Trainer initialisé (device: {device})")
        logger.info(f"   • Paramètres: {self._count_parameters():,}")
    
    def train(
        self,
        train_dataset,
        val_dataset: Optional = None, # type: ignore
        verbose: bool = True
    ) -> Dict[str, List[float]]:
        """Entraînement complet avec validation"""
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0
        )
        
        history = {
            'train_loss': [],
            'val_loss': [],
            'val_acc': []
        }
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        if verbose:
            logger.info("🎓 Début entraînement...")
        
        for epoch in range(self.config.max_epochs):
            # Train epoch
            train_loss = self._train_epoch(train_loader)
            history['train_loss'].append(train_loss)
            
            # Validation
            if val_dataset:
                val_loader = DataLoader(
                    val_dataset,
                    batch_size=self.config.batch_size
                )
                val_loss, val_acc = self._validate(val_loader)
                history['val_loss'].append(val_loss)
                history['val_acc'].append(val_acc)
                
                if verbose:
                    logger.info(
                        f"Epoch {epoch+1:3d}/{self.config.max_epochs} | "
                        f"Train: {train_loss:.4f} | "
                        f"Val: {val_loss:.4f} ({val_acc:6.2%})"
                    )
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= self.config.early_stopping_patience:
                        if verbose:
                            logger.info("ℹ️ Early stopping")
                        break
            else:
                if verbose:
                    logger.info(
                        f"Epoch {epoch+1:3d}/{self.config.max_epochs} | "
                        f"Train: {train_loss:.4f}"
                    )
        
        if verbose:
            logger.info("✅ Entraînement terminé")
        
        return history
    
    def _train_epoch(self, dataloader: DataLoader) -> float:
        """🆕 CORRIGÉ: Epoch avec adjacency et attention mask"""
        
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        for batch in dataloader:
            # Move to device
            node_features = batch['node_features'].to(self.device)
            context_features = batch['context_features'].to(self.device)
            adjacency_matrix = batch['adjacency_matrix'].to(self.device)  # 🆕
            attention_mask = batch['attention_mask'].to(self.device)      # 🆕
            node_mask = batch['node_mask'].to(self.device)
            labels = batch['label'].to(self.device)
            
            # Forward
            predictions = self.model(
                node_features,
                context_features,
                adjacency_matrix,  # 🆕
                attention_mask,    # 🆕
                node_mask
            )
            
            loss = self.criterion(predictions, labels)
            
            # Backward
            self.optimizer.zero_grad()
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        return total_loss / num_batches if num_batches > 0 else 0.0
    
    def _validate(self, dataloader: DataLoader) -> Tuple[float, float]:
        """🆕 CORRIGÉ: Validation avec adjacency"""
        
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        num_batches = 0
        
        with torch.no_grad():
            for batch in dataloader:
                node_features = batch['node_features'].to(self.device)
                context_features = batch['context_features'].to(self.device)
                adjacency_matrix = batch['adjacency_matrix'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                node_mask = batch['node_mask'].to(self.device)
                labels = batch['label'].to(self.device)
                
                predictions = self.model(
                    node_features,
                    context_features,
                    adjacency_matrix,
                    attention_mask,
                    node_mask
                )
                
                loss = self.criterion(predictions, labels)
                
                total_loss += loss.item()
                num_batches += 1
                
                # Accuracy
                pred_labels = (predictions > 0.5).float()
                correct += (pred_labels == labels).sum().item()
                total += labels.size(0)
        
        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        accuracy = correct / total if total > 0 else 0.0
        
        return avg_loss, accuracy
    
    def predict(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🆕 CORRIGÉ: Prédit avec support adjacency
        """
        
        self.model.eval()
        
        # Préparer features
        nodes = [structure]
        
        # Node features
        node_features_list = [
            self.feature_extractor.extract_node_features(n) for n in nodes
        ]
        
        # Adjacency (un seul nœud = pas de connexions)
        max_nodes = self.config.max_nodes_per_structure
        adjacency = np.zeros((max_nodes, max_nodes), dtype=np.float32)
        
        # Attention mask
        attention_mask = np.ones((max_nodes, max_nodes), dtype=bool)
        attention_mask[0, 0] = False
        
        # Padding
        while len(node_features_list) < max_nodes:
            node_features_list.append(np.zeros_like(node_features_list[0]))
        
        node_features = np.stack(node_features_list)
        node_mask = np.array(
            [1.0] * len(nodes) + [0.0] * (max_nodes - len(nodes))
        )
        context_features = self.feature_extractor.extract_context_features(context)
        
        # Tensors
        node_features_t = torch.FloatTensor(node_features).unsqueeze(0).to(self.device)
        adjacency_t = torch.FloatTensor(adjacency).unsqueeze(0).to(self.device)
        attention_mask_t = torch.BoolTensor(attention_mask).unsqueeze(0).to(self.device)
        context_features_t = torch.FloatTensor(context_features).unsqueeze(0).to(self.device)
        node_mask_t = torch.FloatTensor(node_mask).unsqueeze(0).to(self.device)
        
        # Predict
        with torch.no_grad():
            score = self.model(
                node_features_t,
                context_features_t,
                adjacency_t,
                attention_mask_t,
                node_mask_t
            )
            score = score.item()
        
        # Catégoriser
        if score >= 0.8:
            category = 'HIGH'
        elif score >= 0.5:
            category = 'MEDIUM'
        else:
            category = 'LOW'
        
        issues = []
        if score < 0.5:
            issues.append('low_neural_score')
        
        return {
            'quality_score': score,
            'confidence': score,
            'quality_category': category,
            'issues': issues
        }
    
    def online_update(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any],
        was_correct: bool
    ):
        """Mise à jour online avec feedback"""
        
        self.online_buffer.add(structure, context, was_correct)
        self.update_counter += 1
        
        if self.update_counter % self.config.online_update_frequency == 0:
            if len(self.online_buffer) >= self.config.batch_size:
                logger.debug("🔄 Online update...")
                self._online_update_step()
    
    def _online_update_step(self):
        """🆕 CORRIGÉ: Online update avec adjacency"""
        
        self.model.train()
        
        batch = self.online_buffer.sample_batch(self.config.batch_size)
        
        node_features = batch['node_features'].to(self.device)
        context_features = batch['context_features'].to(self.device)
        adjacency_matrix = batch['adjacency_matrix'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        node_mask = batch['node_mask'].to(self.device)
        labels = batch['label'].to(self.device)
        
        predictions = self.model(
            node_features,
            context_features,
            adjacency_matrix,
            attention_mask,
            node_mask
        )
        
        loss = self.criterion(predictions, labels)
        
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
        self.optimizer.step()
        
        logger.debug(f"   Loss: {loss.item():.4f}")
    
    def save_model(self, path: Path):
        """Sauvegarde le modèle complet"""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        checkpoint = {
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'config': self.config.to_dict(),
            'update_counter': self.update_counter
        }
        
        torch.save(checkpoint, path)
        logger.info(f"💾 Modèle sauvegardé: {path}")
    
    def load_model(self, path: Path):
        """Charge le modèle"""
        checkpoint = torch.load(path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state'])
        self.update_counter = checkpoint.get('update_counter', 0)
        
        logger.info(f"📂 Modèle chargé: {path}")
    
    def _count_parameters(self) -> int:
        """Compte le nombre de paramètres"""
        return sum(p.numel() for p in self.model.parameters() if p.requires_grad)