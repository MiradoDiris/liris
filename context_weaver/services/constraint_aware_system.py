#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Constraint-Aware Reranking avec Prérequis
Système déterministe de validation des contraintes sans appel graph live

Architecture alignée avec l'option 3 (92/100) :
- Hybrid + RRF + constraint-aware reranking
- Prérequis en cache local (KV store)
- Validation déterministe
- Audit complet
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# STRUCTURES DE DONNÉES
# ============================================================================

class ConstraintType(Enum):
    """Types de contraintes"""
    HARD = "hard"           # Prérequis obligatoire - disqualifie si manquant
    SOFT = "soft"           # Prérequis recommandé - pénalité si manquant
    BONUS = "bonus"         # Bonus si présent
    INCOMPATIBLE = "incompatible"  # Exclusion mutuelle


@dataclass
class Prerequisite:
    """Prérequis d'un label"""
    label_id: str                        # Label source
    required_label_id: str               # Label requis
    constraint_type: ConstraintType      # Type de contrainte
    weight: float = 1.0                  # Poids de la contrainte
    depth: int = 1                       # Profondeur dans la hiérarchie
    description: str = ""                # Description optionnelle
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'label_id': self.label_id,
            'required_label_id': self.required_label_id,
            'constraint_type': self.constraint_type.value,
            'weight': self.weight,
            'depth': self.depth,
            'description': self.description
        }


@dataclass
class StructureExpected:
    """
    Structure attendue prédite par le learner
    (Représentation light et déterministe)
    """
    primary_label_id: str                           # Label principal attendu
    label_set_expected: Set[str] = field(default_factory=set)  # Top-M labels attendus
    prereq_set_expected: Set[str] = field(default_factory=set) # Prérequis attendus
    constraints: List[Dict[str, Any]] = field(default_factory=list)  # Règles soft/hard
    confidence: float = 0.0                         # Confiance globale
    margin: float = 0.0                             # Marge de sécurité
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'primary_label_id': self.primary_label_id,
            'label_set_expected': list(self.label_set_expected),
            'prereq_set_expected': list(self.prereq_set_expected),
            'constraints': self.constraints,
            'confidence': self.confidence,
            'margin': self.margin
        }


@dataclass
class StructureObserved:
    """Structure observée post-classification"""
    label_set_pred: Set[str] = field(default_factory=set)     # Labels prédits
    prereq_set_pred: Set[str] = field(default_factory=set)    # Prérequis couverts
    violations: List[Dict[str, Any]] = field(default_factory=list)  # Violations détectées
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'label_set_pred': list(self.label_set_pred),
            'prereq_set_pred': list(self.prereq_set_pred),
            'violations': self.violations
        }


@dataclass
class ValidationResult:
    """Résultat de validation"""
    is_valid: bool
    action: str  # "OK", "DOWNGRADE", "RERANK", "ABSTAIN", "CLARIFY"
    missing_hard_prereq: List[str] = field(default_factory=list)
    missing_soft_prereq: List[str] = field(default_factory=list)
    conflicts: List[Tuple[str, str]] = field(default_factory=list)
    score_adjustment: float = 0.0  # Ajustement du score (-1.0 à +1.0)
    explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'action': self.action,
            'missing_hard_prereq': self.missing_hard_prereq,
            'missing_soft_prereq': self.missing_soft_prereq,
            'conflicts': [{'a': a, 'b': b} for a, b in self.conflicts],
            'score_adjustment': self.score_adjustment,
            'explanation': self.explanation
        }


# ============================================================================
# PREREQUISITE CACHE MANAGER
# ============================================================================

class PrerequisiteCache:
    """
    Cache local des prérequis (snapshot depuis le graph)
    KV store en mémoire pour validation déterministe
    """
    
    def __init__(self, cache_path: Path = None):
        """
        Initialise le cache
        
        Args:
            cache_path: Chemin du fichier de cache (JSON)
        """
        self.cache_path = cache_path or Path("./data/prerequisite_cache.json")
        
        # Structure : {label_id: [Prerequisite, ...]}
        self.prerequisites: Dict[str, List[Prerequisite]] = {}
        
        # Index inversé : {required_label_id: [label_id, ...]}
        self.inverse_index: Dict[str, List[str]] = defaultdict(list)
        
        # Incompatibilités : {label_id: [incompatible_label_id, ...]}
        self.incompatibilities: Dict[str, Set[str]] = defaultdict(set)
        
        # Métadonnées du cache
        self.metadata = {
            'version': '1.0',
            'source': 'dgraph',
            'last_sync': None,
            'total_prereqs': 0
        }
        
        # Charger depuis le disque
        self._load_cache()
        
        logger.info("✅ PrerequisiteCache initialisé")
        logger.info(f"   • Cache: {self.cache_path}")
        logger.info(f"   • Prérequis: {self.metadata['total_prereqs']}")
    
    
    def _load_cache(self):
        """Charge le cache depuis le disque"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.metadata = data.get('metadata', {})
                
                # Reconstruire les prérequis
                prereqs_data = data.get('prerequisites', {})
                for label_id, prereq_list in prereqs_data.items():
                    self.prerequisites[label_id] = [
                        Prerequisite(
                            label_id=p['label_id'],
                            required_label_id=p['required_label_id'],
                            constraint_type=ConstraintType(p['constraint_type']),
                            weight=p.get('weight', 1.0),
                            depth=p.get('depth', 1),
                            description=p.get('description', '')
                        )
                        for p in prereq_list
                    ]
                
                # Reconstruire incompatibilités
                incomp_data = data.get('incompatibilities', {})
                for label_id, incomp_list in incomp_data.items():
                    self.incompatibilities[label_id] = set(incomp_list)
                
                # Reconstruire index inversé
                self._rebuild_inverse_index()
                
                logger.info(f"📂 Cache chargé: {self.cache_path}")
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement cache: {e}")
    
    
    def _rebuild_inverse_index(self):
        """Reconstruit l'index inversé"""
        self.inverse_index.clear()
        
        for label_id, prereq_list in self.prerequisites.items():
            for prereq in prereq_list:
                self.inverse_index[prereq.required_label_id].append(label_id)
    
    
    def save_cache(self):
        """Sauvegarde le cache sur disque"""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'metadata': self.metadata,
                'prerequisites': {
                    label_id: [p.to_dict() for p in prereq_list]
                    for label_id, prereq_list in self.prerequisites.items()
                },
                'incompatibilities': {
                    label_id: list(incomp_set)
                    for label_id, incomp_set in self.incompatibilities.items()
                }
            }
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Cache sauvegardé: {self.cache_path}")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache: {e}")
    
    
    def get_prerequisites(
        self,
        label_id: str,
        constraint_type: Optional[ConstraintType] = None
    ) -> List[Prerequisite]:
        """
        Retourne les prérequis d'un label
        
        Args:
            label_id: ID du label
            constraint_type: Filtrer par type (optionnel)
            
        Returns:
            Liste de prérequis
        """
        prereqs = self.prerequisites.get(label_id, [])
        
        if constraint_type:
            prereqs = [p for p in prereqs if p.constraint_type == constraint_type]
        
        return prereqs
    
    
    def get_hard_prerequisites(self, label_id: str) -> List[Prerequisite]:
        """Retourne uniquement les prérequis HARD"""
        return self.get_prerequisites(label_id, ConstraintType.HARD)
    
    
    def get_soft_prerequisites(self, label_id: str) -> List[Prerequisite]:
        """Retourne uniquement les prérequis SOFT"""
        return self.get_prerequisites(label_id, ConstraintType.SOFT)
    
    
    def is_incompatible(self, label_a: str, label_b: str) -> bool:
        """Vérifie si deux labels sont incompatibles"""
        return (
            label_b in self.incompatibilities.get(label_a, set()) or
            label_a in self.incompatibilities.get(label_b, set())
        )
    
    
    def get_dependents(self, required_label_id: str) -> List[str]:
        """
        Retourne tous les labels qui dépendent de required_label_id
        (index inversé)
        """
        return self.inverse_index.get(required_label_id, [])
    
    
    def add_prerequisite(
        self,
        label_id: str,
        required_label_id: str,
        constraint_type: ConstraintType,
        weight: float = 1.0,
        depth: int = 1,
        description: str = ""
    ):
        """Ajoute un prérequis au cache"""
        prereq = Prerequisite(
            label_id=label_id,
            required_label_id=required_label_id,
            constraint_type=constraint_type,
            weight=weight,
            depth=depth,
            description=description
        )
        
        if label_id not in self.prerequisites:
            self.prerequisites[label_id] = []
        
        self.prerequisites[label_id].append(prereq)
        
        # Mettre à jour index inversé
        self.inverse_index[required_label_id].append(label_id)
        
        self.metadata['total_prereqs'] += 1
    
    
    def add_incompatibility(self, label_a: str, label_b: str):
        """Ajoute une incompatibilité (bidirectionnelle)"""
        self.incompatibilities[label_a].add(label_b)
        self.incompatibilities[label_b].add(label_a)
    
    
    def sync_from_graph(self, dgraph_client):
        """
        Synchronise le cache depuis Dgraph
        (À appeler offline périodiquement)
        
        Args:
            dgraph_client: Client Dgraph connecté
        """
        logger.info("🔄 Synchronisation du cache depuis Dgraph...")
        
        # Requête pour extraire tous les prérequis
        query = """
        {
            all_labels(func: type(Label)) {
                uid
                label_id: label.id
                prerequisites @facets {
                    uid
                    prereq_id: label.id
                }
            }
        }
        """
        
        try:
            result = dgraph_client.query(query)
            labels = result.get('all_labels', [])
            
            # Réinitialiser
            self.prerequisites.clear()
            self.inverse_index.clear()
            self.metadata['total_prereqs'] = 0
            
            # Reconstruire
            for label in labels:
                label_id = label.get('label_id')
                prereqs = label.get('prerequisites', [])
                
                for prereq in prereqs:
                    # Récupérer les facets pour le type de contrainte
                    facets = prereq.get('prerequisites|facets', {})
                    constraint_type_str = facets.get('type', 'soft')
                    weight = facets.get('weight', 1.0)
                    
                    constraint_type = ConstraintType(constraint_type_str)
                    
                    self.add_prerequisite(
                        label_id=label_id,
                        required_label_id=prereq.get('prereq_id'),
                        constraint_type=constraint_type,
                        weight=weight
                    )
            
            # Mettre à jour métadonnées
            from datetime import datetime
            self.metadata['last_sync'] = datetime.now().isoformat()
            
            # Sauvegarder
            self.save_cache()
            
            logger.info(f"✅ Synchronisation terminée: {self.metadata['total_prereqs']} prérequis")
            
        except Exception as e:
            logger.error(f"❌ Erreur synchronisation: {e}")
            import traceback
            logger.error(traceback.format_exc())


# ============================================================================
# CONSTRAINT-AWARE VALIDATOR
# ============================================================================

class ConstraintAwareValidator:
    """
    Validateur déterministe avec gestion des prérequis
    
    Responsabilités:
    1. Comparer structure attendue vs observée
    2. Détecter violations (hard/soft)
    3. Calculer ajustements de score
    4. Produire audit explicable
    """
    
    def __init__(self, prereq_cache: PrerequisiteCache):
        """
        Initialise le validateur
        
        Args:
            prereq_cache: Cache de prérequis
        """
        self.prereq_cache = prereq_cache
        
        # Paramètres de pénalité
        self.penalties = {
            'hard_missing': -1.0,      # Disqualification
            'soft_missing': -0.2,      # Pénalité modérée
            'conflict': -0.5,          # Conflit détecté
            'bonus': +0.1              # Bonus si prérequis présent
        }
        
        logger.info("✅ ConstraintAwareValidator initialisé")
    
    
    def validate(
        self,
        structure_expected: StructureExpected,
        structure_observed: StructureObserved
    ) -> ValidationResult:
        """
        Valide la structure observée contre la structure attendue
        
        Args:
            structure_expected: Structure prédite par le learner
            structure_observed: Structure post-classification
            
        Returns:
            ValidationResult avec action et ajustements
        """
        logger.debug(f"🔍 Validation: expected={structure_expected.primary_label_id}")
        
        result = ValidationResult(is_valid=True, action="OK")
        
        # === CHECK 1: Prérequis HARD ===
        missing_hard = self._check_hard_prerequisites(
            structure_expected,
            structure_observed
        )
        
        if missing_hard:
            result.is_valid = False
            result.action = "DISQUALIFY"
            result.missing_hard_prereq = missing_hard
            result.score_adjustment = self.penalties['hard_missing']
            result.explanation = f"Prérequis obligatoires manquants: {', '.join(missing_hard)}"
            
            logger.warning(f"   ❌ HARD prereqs manquants: {missing_hard}")
            return result  # Arrêt immédiat
        
        # === CHECK 2: Prérequis SOFT ===
        missing_soft = self._check_soft_prerequisites(
            structure_expected,
            structure_observed
        )
        
        if missing_soft:
            result.missing_soft_prereq = missing_soft
            result.score_adjustment += self.penalties['soft_missing'] * len(missing_soft)
            result.explanation = f"Prérequis recommandés manquants: {', '.join(missing_soft)}"
            result.action = "DOWNGRADE"
            
            logger.debug(f"   ⚠️ SOFT prereqs manquants: {missing_soft}")
        
        # === CHECK 3: Incompatibilités ===
        conflicts = self._check_incompatibilities(structure_observed)
        
        if conflicts:
            result.conflicts = conflicts
            result.score_adjustment += self.penalties['conflict'] * len(conflicts)
            result.explanation += f" | Conflits: {len(conflicts)}"
            result.action = "DOWNGRADE"
            
            logger.warning(f"   ⚠️ Conflits détectés: {conflicts}")
        
        # === CHECK 4: Bonus ===
        bonus_count = self._count_bonus_prereqs(
            structure_expected,
            structure_observed
        )
        
        if bonus_count > 0:
            result.score_adjustment += self.penalties['bonus'] * bonus_count
            logger.debug(f"   ✅ Bonus: {bonus_count} prérequis présents")
        
        # Décision finale
        if result.score_adjustment < -0.3:
            result.action = "DOWNGRADE"
        elif result.score_adjustment > 0.1:
            result.action = "UPGRADE"
        
        return result
    
    
    def _check_hard_prerequisites(
        self,
        expected: StructureExpected,
        observed: StructureObserved
    ) -> List[str]:
        """Vérifie les prérequis HARD manquants"""
        missing = []
        
        # Pour chaque label prédit
        for label_id in observed.label_set_pred:
            # Récupérer prérequis HARD
            hard_prereqs = self.prereq_cache.get_hard_prerequisites(label_id)
            
            for prereq in hard_prereqs:
                required_id = prereq.required_label_id
                
                # Vérifier si le prérequis est satisfait
                if required_id not in observed.prereq_set_pred:
                    missing.append(required_id)
        
        return missing
    
    
    def _check_soft_prerequisites(
        self,
        expected: StructureExpected,
        observed: StructureObserved
    ) -> List[str]:
        """Vérifie les prérequis SOFT manquants"""
        missing = []
        
        for label_id in observed.label_set_pred:
            soft_prereqs = self.prereq_cache.get_soft_prerequisites(label_id)
            
            for prereq in soft_prereqs:
                required_id = prereq.required_label_id
                
                if required_id not in observed.prereq_set_pred:
                    missing.append(required_id)
        
        return missing
    
    
    def _check_incompatibilities(
        self,
        observed: StructureObserved
    ) -> List[Tuple[str, str]]:
        """Détecte les incompatibilités entre labels prédits"""
        conflicts = []
        
        labels = list(observed.label_set_pred)
        
        for i, label_a in enumerate(labels):
            for label_b in labels[i+1:]:
                if self.prereq_cache.is_incompatible(label_a, label_b):
                    conflicts.append((label_a, label_b))
        
        return conflicts
    
    
    def _count_bonus_prereqs(
        self,
        expected: StructureExpected,
        observed: StructureObserved
    ) -> int:
        """Compte les prérequis bonus présents"""
        bonus_count = 0
        
        for label_id in observed.label_set_pred:
            bonus_prereqs = self.prereq_cache.get_prerequisites(
                label_id,
                ConstraintType.BONUS
            )
            
            for prereq in bonus_prereqs:
                if prereq.required_label_id in observed.prereq_set_pred:
                    bonus_count += 1
        
        return bonus_count


# ============================================================================
# CONSTRAINT-AWARE RERANKER
# ============================================================================

class ConstraintAwareReranker:
    """
    Reranker qui intègre les contraintes de prérequis
    
    Flow:
    1. Hybrid retrieval + RRF → Top-K labels
    2. Structure learner → structure attendue
    3. Validator → ajustements de score
    4. Rerank final
    """
    
    def __init__(
        self,
        prereq_cache: PrerequisiteCache,
        validator: ConstraintAwareValidator
    ):
        """
        Initialise le reranker
        
        Args:
            prereq_cache: Cache de prérequis
            validator: Validateur de contraintes
        """
        self.prereq_cache = prereq_cache
        self.validator = validator
        
        logger.info("✅ ConstraintAwareReranker initialisé")
    
    
    def rerank(
        self,
        search_results: List[Any],  # SearchResult objects
        structure_expected: StructureExpected,
        context_decomposition: Dict[str, Any]
    ) -> List[Any]:
        """
        Rerank les résultats en appliquant les contraintes
        
        Args:
            search_results: Résultats du hybrid search
            structure_expected: Structure attendue du learner
            context_decomposition: Décomposition du contexte (entités, slots)
            
        Returns:
            Résultats rerankés avec scores ajustés
        """
        logger.info(f"🔄 Reranking avec contraintes: {len(search_results)} résultats")
        
        reranked = []
        
        for result in search_results:
            # Construire structure observée
            structure_observed = self._build_observed_structure(
                result,
                context_decomposition
            )
            
            # Valider
            validation = self.validator.validate(
                structure_expected,
                structure_observed
            )
            
            # Ajuster le score
            original_score = result.score
            adjusted_score = original_score + validation.score_adjustment
            adjusted_score = max(0.0, min(1.0, adjusted_score))  # Clamp [0, 1]
            
            # Enrichir avec validation
            result.score = adjusted_score
            result.metadata['constraint_validation'] = validation.to_dict()
            result.metadata['original_score'] = original_score
            
            # Filtrer si disqualifié
            if validation.action != "DISQUALIFY":
                reranked.append(result)
            else:
                logger.debug(f"   ❌ Disqualifié: {result.id} - {validation.explanation}")
        
        # Re-trier par score ajusté
        reranked.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"✅ {len(reranked)} résultats après reranking")
        
        return reranked
    
    
    def _build_observed_structure(
        self,
        search_result: Any,
        context_decomposition: Dict[str, Any]
    ) -> StructureObserved:
        """
        Construit la structure observée depuis le résultat
        
        Args:
            search_result: Résultat de recherche
            context_decomposition: Contexte décomposé
            
        Returns:
            StructureObserved
        """
        # Labels prédits = le label du résultat
        label_set_pred = {search_result.id}
        
        # Prérequis couverts = extraits du contexte
        # (en vrai, on devrait parser context_decomposition pour détecter les concepts)
        prereq_set_pred = set()
        
        # Exemple simpliste : si le contexte mentionne un concept, on considère le prérequis couvert
        context_text = str(context_decomposition.get('text', '')).lower()
        
        # Parser les entités détectées dans le contexte
        entities = context_decomposition.get('entities', [])
        for entity in entities:
            entity_id = entity.get('id')
            if entity_id:
                prereq_set_pred.add(entity_id)
        
        return StructureObserved(
            label_set_pred=label_set_pred,
            prereq_set_pred=prereq_set_pred
        )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 80)
    print("🎯 CONSTRAINT-AWARE RERANKING - EXEMPLE")
    print("=" * 80 + "\n")
    
    # === SETUP ===
    
    # 1. Cache de prérequis
    prereq_cache = PrerequisiteCache(Path("./data/prerequisite_cache.json"))
    
    # Ajouter quelques prérequis d'exemple
    prereq_cache.add_prerequisite(
        label_id="label_advanced_fraud",
        required_label_id="label_basic_transaction",
        constraint_type=ConstraintType.HARD,
        description="Fraude avancée nécessite transaction de base"
    )
    
    prereq_cache.add_prerequisite(
        label_id="label_advanced_fraud",
        required_label_id="label_customer_profile",
        constraint_type=ConstraintType.SOFT,
        description="Profile client recommandé"
    )
    
    prereq_cache.add_incompatibility("label_retail", "label_wholesale")
    
    prereq_cache.save_cache()
    
    # 2. Validator
    validator = ConstraintAwareValidator(prereq_cache)
    
    # 3. Reranker
    reranker = ConstraintAwareReranker(prereq_cache, validator)
    
    # === TEST ===
    
    print("📋 Test 1: Validation avec prérequis manquant (HARD)")
    print("-" * 80)
    
    expected = StructureExpected(
        primary_label_id="label_advanced_fraud",
        prereq_set_expected={"label_basic_transaction", "label_customer_profile"}
    )
    
    observed = StructureObserved(
        label_set_pred={"label_advanced_fraud"},
        prereq_set_pred=set()  # Aucun prérequis couvert
    )
    
    result = validator.validate(expected, observed)
    
    print(f"Valide: {result.is_valid}")
    print(f"Action: {result.action}")
    print(f"Ajustement: {result.score_adjustment:.3f}")
    print(f"Explication: {result.explanation}")
    
    print("\n" + "=" * 80)
    print("✅ TERMINÉ")
    print("=" * 80 + "\n")