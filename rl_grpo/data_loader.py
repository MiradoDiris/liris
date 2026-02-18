#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rl_grpo/data_loader.py - Chargement des données depuis la base de données
"""

import logging
from typing import List, Dict, Any, Optional
import random

logger = logging.getLogger(__name__)


class DataLoader:
    """Charge les données depuis la base de données pour GRPO"""
    
    def __init__(self, database):
        """
        Args:
            database: Instance de la base de données
        """
        self.database = database
    
    def load_batch_data(
        self,
        project_name: str,
        batch_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Charge les données d'un batch depuis la DB
        
        Args:
            project_name: Nom du projet
            batch_number: Numéro du batch
        
        Returns:
            Données du batch ou None si erreur
        """
        try:
            logger.info(f"📦 Chargement batch {batch_number} du projet {project_name}")
            
            batch_data = self.database.get_batch(project_name, batch_number)
            
            if not batch_data:
                logger.error(f"❌ Batch {batch_number} introuvable")
                return None
            
            logger.info(f"✅ Batch chargé")
            return batch_data
        
        except Exception as e:
            logger.error(f"❌ Erreur chargement batch: {e}")
            return None
    
    def extract_prompts(self, batch_data: Dict[str, Any]) -> List[str]:
        """
        Extrait les prompts (inputs) d'un batch
        
        Args:
            batch_data: Données du batch
        
        Returns:
            Liste des prompts
        """
        prompts = []
        
        data = batch_data.get('data', {})
        combinations = data.get('combinations', [])
        
        for combo in combinations:
            samples = combo.get('samples', [])
            for sample in samples:
                input_text = sample.get('input', '')
                if input_text and input_text.strip():
                    prompts.append(input_text.strip())
        
        logger.info(f"📝 {len(prompts)} prompts extraits")
        return prompts
    
    def extract_dataset(self, batch_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extrait le dataset complet (input + output) d'un batch
        
        Args:
            batch_data: Données du batch
        
        Returns:
            Liste de dicts avec clés 'input' et 'output'
        """
        dataset = []
        
        data = batch_data.get('data', {})
        combinations = data.get('combinations', [])
        
        for combo in combinations:
            samples = combo.get('samples', [])
            for sample in samples:
                input_text = sample.get('input', '').strip()
                output_text = sample.get('output', '').strip()
                
                if input_text:  # Output peut être vide (on va le générer)
                    dataset.append({
                        'input': input_text,
                        'output': output_text
                    })
        
        logger.info(f"📊 {len(dataset)} samples extraits")
        return dataset
    
    def sample_prompts(
        self,
        prompts: List[str],
        batch_size: int,
        shuffle: bool = True
    ) -> List[str]:
        """
        Échantillonne un sous-ensemble de prompts
        
        Args:
            prompts: Liste complète des prompts
            batch_size: Nombre de prompts à échantillonner
            shuffle: Mélanger avant échantillonnage
        
        Returns:
            Liste de prompts échantillonnés
        """
        if not prompts:
            return []
        
        # Limiter batch_size au nombre de prompts disponibles
        actual_batch_size = min(batch_size, len(prompts))
        
        if shuffle:
            # Échantillonnage aléatoire sans remplacement
            sampled = random.sample(prompts, actual_batch_size)
        else:
            # Prendre les premiers
            sampled = prompts[:actual_batch_size]
        
        logger.debug(f"🎲 {len(sampled)} prompts échantillonnés")
        return sampled
    
    def get_batch_info(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retourne les informations d'un batch
        
        Args:
            batch_data: Données du batch
        
        Returns:
            Informations du batch
        """
        data = batch_data.get('data', {})
        combinations = data.get('combinations', [])
        
        total_samples = sum(
            len(c.get('samples', [])) 
            for c in combinations
        )
        
        return {
            'batch_number': batch_data.get('batch_number', 0),
            'batch_name': data.get('batch_name', 'N/A'),
            'batch_family': data.get('batch_family', 'N/A'),
            'total_combinations': len(combinations),
            'total_samples': total_samples,
            'created_at': batch_data.get('created_at', 'N/A')
        }


class DataBatcher:
    """Crée des batches de prompts pour l'entraînement"""
    
    def __init__(self, prompts: List[str], batch_size: int, shuffle: bool = True):
        self.prompts = prompts
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.current_idx = 0
        
        if shuffle:
            random.shuffle(self.prompts)
    
    def __iter__(self):
        self.current_idx = 0
        if self.shuffle:
            random.shuffle(self.prompts)
        return self
    
    def __next__(self) -> List[str]:
        if self.current_idx >= len(self.prompts):
            raise StopIteration
        
        batch = self.prompts[
            self.current_idx:self.current_idx + self.batch_size
        ]
        self.current_idx += self.batch_size
        
        return batch
    
    def __len__(self):
        return (len(self.prompts) + self.batch_size - 1) // self.batch_size
    
    def reset(self):
        """Reset l'itérateur"""
        self.current_idx = 0
        if self.shuffle:
            random.shuffle(self.prompts)