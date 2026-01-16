#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Structure Validator - Validation & Scoring avec Apprentissage
Scoring: Low, High, Margin basé sur l'apprentissage des structures
"""

import logging
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class StructureValidator:
    """
    Validateur de structures avec apprentissage
    
    Fonctionnalités:
    1. Scoring des structures (Low, High, Margin)
    2. Apprentissage des patterns de structures valides
    3. Évolution du modèle de scoring au fil du temps
    4. Validation de la cohérence avec le domaine
    """
    
    def __init__(self, model_path: Path = None):
        """
        Initialise le validateur
        
        Args:
            model_path: Chemin vers le modèle d'apprentissage sauvegardé
        """
        self.model_path = model_path or Path("./data/validator_model.json")
        
        # Modèle d'apprentissage
        self.learning_model = {
            'structure_scores': {},  # {structure_id: score_history}
            'domain_patterns': {},   # {domain: pattern_features}
            'feedback_history': [],  # Historique des feedbacks
            'evolution_metrics': {
                'total_validations': 0,
                'successful_structures': 0,
                'failed_structures': 0
            }
        }
        
        # Charger le modèle existant si disponible
        self._load_model()
        
        # Seuils de scoring
        self.THRESHOLD_HIGH = 0.7   # Score >= 0.7 → High quality
        self.THRESHOLD_LOW = 0.3    # Score < 0.3 → Low quality
        # Entre 0.3 et 0.7 → Margin (zone d'incertitude)
        
        logger.info("✅ StructureValidator initialisé")
        logger.info(f"   • Modèle: {self.model_path}")
        logger.info(f"   • Validations totales: {self.learning_model['evolution_metrics']['total_validations']}")
    
    def validate_and_score(
        self,
        structures: List[Dict[str, Any]],
        classification,
        normalized
    ) -> List[Dict[str, Any]]:
        """
        Valide et score les structures récupérées
        
        Args:
            structures: Liste des structures depuis la DB
            classification: Classification OSS
            normalized: Variables normalisées
            
        Returns:
            Liste des structures validées et scorées
        """
        logger.info(f"🎯 Validation de {len(structures)} structures...")
        
        validated = []
        
        for structure in structures:
            # 1. Calculer le score de la structure
            score_result = self._compute_structure_score(
                structure,
                classification,
                normalized
            )
            
            # 2. Déterminer la catégorie (Low, High, Margin)
            category = self._categorize_score(score_result['score'])
            
            # 3. Enrichir la structure avec le scoring
            validated_structure = {
                **structure,
                'validation': {
                    'score': score_result['score'],
                    'category': category,
                    'confidence': score_result['confidence'],
                    'features': score_result['features'],
                    'reasons': score_result['reasons']
                }
            }
            
            validated.append(validated_structure)
            
            # 4. Apprentissage: enregistrer le score
            self._record_validation(structure['id'], score_result['score'])
        
        # Trier par score décroissant
        validated.sort(key=lambda x: x['validation']['score'], reverse=True)
        
        # Log des résultats
        high_count = sum(1 for v in validated if v['validation']['category'] == 'HIGH')
        margin_count = sum(1 for v in validated if v['validation']['category'] == 'MARGIN')
        low_count = sum(1 for v in validated if v['validation']['category'] == 'LOW')
        
        logger.info(f"   • HIGH: {high_count}")
        logger.info(f"   • MARGIN: {margin_count}")
        logger.info(f"   • LOW: {low_count}")
        
        # Mettre à jour les métriques d'évolution
        self.learning_model['evolution_metrics']['total_validations'] += len(structures)
        self.learning_model['evolution_metrics']['successful_structures'] += high_count
        self.learning_model['evolution_metrics']['failed_structures'] += low_count
        
        # Sauvegarder le modèle
        self._save_model()
        
        return validated
    
    def _compute_structure_score(
        self,
        structure: Dict[str, Any],
        classification,
        normalized
    ) -> Dict[str, Any]:
        """
        Calcule le score d'une structure
        
        Combine plusieurs facteurs:
        1. Score de recherche initial (BM25/Vector)
        2. Cohérence avec le domaine
        3. Pertinence des variables
        4. Historique d'apprentissage
        5. Qualité structurelle
        """
        features = {}
        reasons = []
        
        # === FEATURE 1: Score de recherche initial ===
        search_score = structure.get('score', 0.0)
        features['search_score'] = search_score
        
        # === FEATURE 2: Cohérence domaine ===
        domain_match = 1.0 if structure['domain'] == classification.domain else 0.5
        features['domain_match'] = domain_match
        
        if domain_match == 1.0:
            reasons.append(f"Domaine exact: {classification.domain}")
        else:
            reasons.append(f"Domaine différent: {structure['domain']} vs {classification.domain}")
        
        # === FEATURE 3: Pertinence des variables ===
        structure_vars = self._extract_variables_from_structure(structure)
        normalized_vars = set(normalized.variables.values())
        
        if structure_vars and normalized_vars:
            var_overlap = len(structure_vars & normalized_vars) / len(normalized_vars)
        else:
            var_overlap = 0.0
        
        features['variable_overlap'] = var_overlap
        reasons.append(f"Variables communes: {var_overlap:.1%}")
        
        # === FEATURE 4: Historique d'apprentissage ===
        structure_id = structure['id']
        historical_score = self._get_historical_score(structure_id)
        features['historical_score'] = historical_score
        
        if historical_score > 0:
            reasons.append(f"Score historique: {historical_score:.2f}")
        
        # === FEATURE 5: Qualité structurelle ===
        structure_quality = self._assess_structure_quality(structure)
        features['structure_quality'] = structure_quality
        
        # === CALCUL DU SCORE FINAL ===
        # Pondération des features
        weights = {
            'search_score': 0.3,
            'domain_match': 0.2,
            'variable_overlap': 0.25,
            'historical_score': 0.15,
            'structure_quality': 0.1
        }
        
        final_score = sum(
            features[key] * weights[key]
            for key in weights.keys()
        )
        
        # Calculer la confiance
        confidence = self._compute_confidence(features)
        
        return {
            'score': final_score,
            'confidence': confidence,
            'features': features,
            'reasons': reasons
        }
    
    def _categorize_score(self, score: float) -> str:
        """
        Catégorise un score en LOW, MARGIN, ou HIGH
        
        Args:
            score: Score entre 0 et 1
            
        Returns:
            'HIGH', 'MARGIN', ou 'LOW'
        """
        if score >= self.THRESHOLD_HIGH:
            return 'HIGH'
        elif score >= self.THRESHOLD_LOW:
            return 'MARGIN'
        else:
            return 'LOW'
    
    def _extract_variables_from_structure(self, structure: Dict) -> set:
        """Extrait les variables mentionnées dans une structure"""
        variables = set()
        
        # Extraire depuis metadata
        if 'metadata' in structure:
            meta_vars = structure['metadata'].get('variables', [])
            if isinstance(meta_vars, list):
                variables.update(meta_vars)
            elif isinstance(meta_vars, str):
                variables.update(meta_vars.split())
        
        # Extraire depuis content
        if 'content' in structure:
            content_vars = structure['content'].get('variables', '')
            if content_vars:
                variables.update(content_vars.split())
        
        return variables
    
    def _get_historical_score(self, structure_id: str) -> float:
        """
        Récupère le score historique d'une structure
        
        Retourne la moyenne des scores passés si disponible
        """
        if structure_id in self.learning_model['structure_scores']:
            history = self.learning_model['structure_scores'][structure_id]
            if history:
                return np.mean(history)
        
        return 0.0
    
    def _assess_structure_quality(self, structure: Dict) -> float:
        """
        Évalue la qualité structurelle
        
        Critères:
        - Complétude des champs
        - Longueur du contenu
        - Présence de métadonnées
        """
        score = 0.0
        
        # Champs requis présents
        required = ['id', 'name', 'domain', 'type', 'content']
        present = sum(1 for field in required if field in structure and structure[field])
        score += (present / len(required)) * 0.4
        
        # Contenu non vide
        content = structure.get('content', {})
        if isinstance(content, dict):
            content_fields = len([v for v in content.values() if v])
            score += min(content_fields / 3, 1.0) * 0.3
        
        # Métadonnées présentes
        if 'metadata' in structure and structure['metadata']:
            score += 0.3
        
        return score
    
    def _compute_confidence(self, features: Dict[str, float]) -> float:
        """
        Calcule un score de confiance basé sur la cohérence des features
        
        Confiance haute = features cohérentes (toutes hautes ou toutes basses)
        Confiance basse = features contradictoires
        """
        values = list(features.values())
        
        if not values:
            return 0.0
        
        # Variance faible = cohérence haute
        variance = np.var(values)
        confidence = 1.0 - min(variance, 1.0)
        
        return confidence
    
    def _record_validation(self, structure_id: str, score: float):
        """
        Enregistre un score de validation pour apprentissage
        
        Args:
            structure_id: ID de la structure
            score: Score attribué
        """
        if structure_id not in self.learning_model['structure_scores']:
            self.learning_model['structure_scores'][structure_id] = []
        
        self.learning_model['structure_scores'][structure_id].append(score)
        
        # Limiter l'historique à 100 scores
        if len(self.learning_model['structure_scores'][structure_id]) > 100:
            self.learning_model['structure_scores'][structure_id] = \
                self.learning_model['structure_scores'][structure_id][-100:]
    
    def provide_feedback(
        self,
        structure_id: str,
        was_useful: bool,
        feedback_text: str = ""
    ):
        """
        Enregistre un feedback utilisateur pour apprentissage
        
        Args:
            structure_id: ID de la structure
            was_useful: True si la structure était utile
            feedback_text: Commentaire optionnel
        """
        feedback = {
            'structure_id': structure_id,
            'was_useful': was_useful,
            'feedback_text': feedback_text,
            'timestamp': time.time()
        }
        
        self.learning_model['feedback_history'].append(feedback)
        
        # Ajuster le score historique
        if structure_id in self.learning_model['structure_scores']:
            # Ajouter un bonus/malus selon le feedback
            adjustment = 0.1 if was_useful else -0.1
            current_avg = np.mean(self.learning_model['structure_scores'][structure_id])
            new_score = max(0.0, min(1.0, current_avg + adjustment))
            self.learning_model['structure_scores'][structure_id].append(new_score)
        
        logger.info(f"📝 Feedback enregistré: {structure_id} → {'✅' if was_useful else '❌'}")
        
        self._save_model()
    
    def get_evolution_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques d'évolution du modèle"""
        metrics = self.learning_model['evolution_metrics'].copy()
        
        # Calculer des statistiques supplémentaires
        if metrics['total_validations'] > 0:
            metrics['success_rate'] = metrics['successful_structures'] / metrics['total_validations']
            metrics['failure_rate'] = metrics['failed_structures'] / metrics['total_validations']
        else:
            metrics['success_rate'] = 0.0
            metrics['failure_rate'] = 0.0
        
        metrics['structures_learned'] = len(self.learning_model['structure_scores'])
        metrics['feedbacks_received'] = len(self.learning_model['feedback_history'])
        
        return metrics
    
    def _load_model(self):
        """Charge le modèle d'apprentissage depuis le disque"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'r', encoding='utf-8') as f:
                    self.learning_model = json.load(f)
                
                logger.info(f"📂 Modèle chargé: {self.model_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement modèle: {e}")
    
    def _save_model(self):
        """Sauvegarde le modèle d'apprentissage sur le disque"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.model_path, 'w', encoding='utf-8') as f:
                json.dump(self.learning_model, f, indent=2)
            
            logger.debug(f"💾 Modèle sauvegardé: {self.model_path}")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde modèle: {e}")


import time

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test du validateur
    validator = StructureValidator()
    
    # Structures de test
    test_structures = [
        {
            'id': 'dt_001',
            'name': 'Fraud Tree',
            'domain': 'fraude_bancaire',
            'type': 'decision_tree',
            'score': 0.85,
            'content': {'variables': 'amount country frequency'},
            'metadata': {'variables': ['amount', 'country']}
        },
        {
            'id': 'dt_002',
            'name': 'Credit Tree',
            'domain': 'credit_scoring',
            'type': 'decision_tree',
            'score': 0.45,
            'content': {'variables': 'age income'},
            'metadata': {}
        }
    ]
    
    # Classification simulée
    from context_weaver.services.oss_classifier import OSSClassification
    classification = OSSClassification(
        domain='fraude_bancaire',
        task='detection',
        decision_type='decision_tree',
        variables=['amount', 'country', 'frequency']
    )
    
    # Normalisation simulée
    from context_weaver.models.schemas import NormalizedVariables
    normalized = NormalizedVariables(
        variables={
            'amount': 'transaction_amount',
            'country': 'country_code',
            'frequency': 'transaction_frequency'
        }
    )
    
    # Validation
    validated = validator.validate_and_score(
        test_structures,
        classification,
        normalized
    )
    
    # Affichage
    print("\n" + "="*70)
    print("RÉSULTATS DE VALIDATION")
    print("="*70)
    for v in validated:
        val = v['validation']
        print(f"\n{v['name']} ({v['id']})")
        print(f"  Score: {val['score']:.3f}")
        print(f"  Catégorie: {val['category']}")
        print(f"  Confiance: {val['confidence']:.3f}")
        print(f"  Raisons: {', '.join(val['reasons'])}")
    
    # Métriques
    print("\n" + "="*70)
    print("MÉTRIQUES D'ÉVOLUTION")
    print("="*70)
    metrics = validator.get_evolution_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")