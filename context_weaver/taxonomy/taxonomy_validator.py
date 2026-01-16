#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaxonomyValidator - Phase 2: Gate de sécurité AVANT d'accéder au graph SoT

✅ CORRIGÉ: Utilise Violation et ViolationType (pas MissingRequirement)
"""

import logging
import time
from typing import Dict, List, Any, Optional

from context_weaver.taxonomy.taxonomy_models import (
    TaxonCandidate,
    ValidationResult,
    ValidationStatus,
    Violation,           # ✅ CORRIGÉ
    ViolationType,       # ✅ CORRIGÉ
    ConversationState
)

logger = logging.getLogger(__name__)


class TaxonomyValidator:
    """
    Gate de sécurité AVANT d'aller dans le graph SoT
    
    Check:
    1. Prereqs hard satisfaits ?
    2. Required slots remplis ?
    3. Cohérence hiérarchique ?
    
    Retourne: PASS / CLARIFY / ABSTAIN
    """
    
    def __init__(self, taxonomy_metadata: Optional[Dict] = None):
        """
        Args:
            taxonomy_metadata: Metadata de la taxonomie (optionnel)
        """
        self.taxonomy_metadata = taxonomy_metadata or {}
        
        # Seuils ajustés pour RRF
        # Les scores RRF sont typiquement entre 0.01 et 0.04
        self.confidence_threshold_pass = 0.025      # ✅ Ajusté pour RRF
        self.confidence_threshold_abstain = 0.015   # ✅ Ajusté pour RRF
        
        logger.info("✅ TaxonomyValidator initialisé")
    
    
    def validate(
        self,
        candidates: List[TaxonCandidate],
        user_context: Dict[str, Any],
        conversation_state: Optional[ConversationState] = None
    ) -> ValidationResult:
        """
        Valide les candidats et décide: PASS / CLARIFY / ABSTAIN
        
        Args:
            candidates: Candidats du retrieval (triés par score)
            user_context: Contexte utilisateur (query, domain, variables, etc.)
            conversation_state: État de la conversation (prereqs déjà satisfaits)
        
        Returns:
            ValidationResult avec status et détails
        """
        start_time = time.time()
        
        logger.info("=" * 80)
        logger.info("✅ TAXONOMY VALIDATOR")
        logger.info("=" * 80)
        
        if not candidates:
            return self._abstain("Aucun candidat trouvé", start_time)
        
        # Candidat principal
        primary = candidates[0]
        logger.info(f"Primary candidate: {primary.name} (score={primary.final_score:.3f})")
        
        # Initialiser conversation state si absent
        if conversation_state is None:
            conversation_state = ConversationState(conversation_id="default")
        
        # === CHECK 1: Prereqs Hard ===
        prereqs_check = self._check_prereqs_hard(primary, conversation_state)
        logger.info(f"Prereqs hard: {prereqs_check['status']}")
        
        if not prereqs_check['satisfied']:
            return self._clarify_prereqs(
                primary,
                prereqs_check['missing'],
                start_time
            )
        
        # === CHECK 2: Required Slots ===
        slots_check = self._check_required_slots(primary, user_context)
        logger.info(f"Required slots: {slots_check['status']}")
        
        if not slots_check['satisfied']:
            return self._clarify_slots(
                primary,
                slots_check['missing'],
                start_time
            )
        
        # === CHECK 3: Cohérence hiérarchique ===
        hierarchy_check = self._check_hierarchical_coherence(candidates, conversation_state)
        logger.info(f"Hierarchy coherence: {hierarchy_check['status']}")
        
        if not hierarchy_check['coherent']:
            return self._abstain(hierarchy_check['reason'], start_time)
        
        # === CHECK 4: Confiance ===
        confidence = self._calculate_confidence(primary, user_context)
        logger.info(f"Confidence: {confidence:.3f}")
        
        if confidence < self.confidence_threshold_abstain:
            return self._abstain(f"Confiance trop faible ({confidence:.2f})", start_time)
        
        if confidence < self.confidence_threshold_pass:
            # Confiance moyenne → demander confirmation
            return self._clarify_confirmation(primary, confidence, candidates[1:3], start_time)
        
        # === PASS ===
        return self._pass(primary, confidence, prereqs_check, slots_check, hierarchy_check, start_time)
    
    
    # ========================================================================
    # CHECKS
    # ========================================================================
    
    def _check_prereqs_hard(
        self,
        candidate: TaxonCandidate,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Check si les prereqs hard sont satisfaits - CORRIGÉ"""

        # ✅ FIX: Accès via metadata
        prereq_hard_ids = candidate.metadata.get('prereq_hard_ids', [])

        if not prereq_hard_ids:
            return {
                'satisfied': True,
                'status': 'OK (no prereqs)',
                'missing': []
            }

        missing = []
        for prereq_id in prereq_hard_ids:
            if not conversation_state.has_prereq_satisfied(prereq_id):
                # Chercher le nom du prereq (optionnel, si metadata disponible)
                prereq_name = self._get_taxon_name(prereq_id)
                missing.append({
                    'id': prereq_id,
                    'name': prereq_name
                })

        if missing:
            return {
                'satisfied': False,
                'status': f'MISSING ({len(missing)} prereqs)',
                'missing': missing
            }

        return {
            'satisfied': True,
            'status': f'OK ({len(prereq_hard_ids)} prereqs satisfied)',
            'missing': []
        }
    
    
    def _check_required_slots(
        self,
        candidate: TaxonCandidate,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check si les required slots sont remplis - CORRIGÉ"""

        # ✅ FIX: Accès via metadata
        required_slots = candidate.metadata.get('required_slots', [])

        if not required_slots:
            return {
                'satisfied': True,
                'status': 'OK (no required slots)',
                'missing': []
            }

        # Extraire les slots depuis user_context (ou conversation_state)
        provided_slots = user_context.get('slots', {})

        missing = []
        for slot_name in required_slots:
            if slot_name not in provided_slots:
                missing.append(slot_name)

        if missing:
            return {
                'satisfied': False,
                'status': f'MISSING ({len(missing)} slots)',
                'missing': missing
            }

        return {
            'satisfied': True,
            'status': f'OK ({len(required_slots)} slots filled)',
            'missing': []
        }
    
    
    def _check_hierarchical_coherence(
        self,
        candidates: List[TaxonCandidate],
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Check cohérence hiérarchique - CORRIGÉ"""

        # Check 1: Si on a déjà un path dans conversation_state,
        # le nouveau candidat doit être compatible

        if conversation_state.current_path:
            primary = candidates[0]

            # ✅ FIX: Accès path_ids via metadata
            path_ids = primary.metadata.get('path_ids', [])

            # Le candidat doit être dans le sous-arbre du path actuel
            # OU être un frère dans la même branche
            has_overlap = any(
                path_id in path_ids
                for path_id in conversation_state.current_path
            )

            if not has_overlap:
                return {
                    'coherent': False,
                    'status': 'INCOHERENT',
                    'reason': 'Candidat hors du path actuel de conversation'
                }

        # Check 2: Top candidates ne doivent pas être incompatibles
        primary = candidates[0]

        # ✅ FIX: Accès incompatible_ids via metadata
        incompatible_ids = primary.metadata.get('incompatible_ids', [])

        for other in candidates[1:5]:  # Check top 5
            if other.taxon_id in incompatible_ids:
                return {
                    'coherent': False,
                    'status': 'INCOHERENT',
                    'reason': f'Candidats incompatibles détectés: {primary.name} vs {other.name}'
                }

        return {
            'coherent': True,
            'status': 'OK',
            'reason': ''
        }
    
    
    def _calculate_confidence(
        self,
        candidate: TaxonCandidate,
        user_context: Dict[str, Any]
    ) -> float:
        """Calcule la confiance dans le candidat - CORRIGÉ"""

        # Base: score final du retrieval
        confidence = candidate.final_score

        # ✅ FIX: Accès source via metadata
        source = candidate.metadata.get('source', 'unknown')

        # Boost si:
        # - Source = hybrid (présent dans dense ET bm25)
        if source == "hybrid":
            confidence *= 1.1

        # - Profondeur élevée (plus spécifique)
        if candidate.depth >= 3:
            confidence *= 1.05

        # - Match domain
        if user_context.get('domain') and candidate.metadata.get('domain'):
            if user_context['domain'].lower() in candidate.metadata['domain'].lower():
                confidence *= 1.1

        # Normaliser dans [0, 1]
        confidence = min(confidence, 1.0)

        return confidence
    
    
    # ========================================================================
    # RESULT BUILDERS (✅ CORRIGÉ: Utilise Violation au lieu de MissingRequirement)
    # ========================================================================
    
    def _pass(
        self,
        candidate: TaxonCandidate,
        confidence: float,
        prereqs_check: Dict,
        slots_check: Dict,
        hierarchy_check: Dict,
        start_time: float
    ) -> ValidationResult:
        """Construit un résultat PASS - CORRIGÉ"""

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(f"✅ PASS - {candidate.name} (confidence={confidence:.3f})")

        # ✅ CORRIGÉ: ValidationResult n'a pas validated_taxon, utiliser primary_taxon_id et validated_taxon_name
        return ValidationResult(
            status=ValidationStatus.PASS,
            confidence=confidence,
            primary_taxon_id=candidate.taxon_id,  # ✅ Utiliser primary_taxon_id
            validated_taxon_name=candidate.name,   # ✅ Utiliser validated_taxon_name
            prereqs_check=prereqs_check,
            slots_check=slots_check,
            hierarchy_check=hierarchy_check,
            validation_time_ms=elapsed_ms
        )
    
    
    def _clarify_prereqs(
        self,
        candidate: TaxonCandidate,
        missing_prereqs: List[Dict],
        start_time: float
    ) -> ValidationResult:
        """Construit un résultat CLARIFY pour prereqs manquants - CORRIGÉ"""

        elapsed_ms = (time.time() - start_time) * 1000

        # ✅ CORRIGÉ: Utiliser 'type' au lieu de 'violation_type'
        violations = [
            Violation(
                type=ViolationType.MISSING_PREREQ_HARD,  # ✅ 'type' pas 'violation_type'
                details=f"Prérequis nécessaire: {prereq['name']}",
                affected_entity=prereq['id'],
                severity="high"
            )
            for prereq in missing_prereqs
        ]

        if len(missing_prereqs) == 1:
            question = f"Avant de continuer avec '{candidate.name}', confirmez-vous que vous avez : {missing_prereqs[0]['name']} ?"
        else:
            prereq_names = [p['name'] for p in missing_prereqs]
            question = f"Avant de continuer avec '{candidate.name}', confirmez-vous que vous avez : {', '.join(prereq_names)} ?"

        logger.info(f"❓ CLARIFY - Missing prereqs: {[p['name'] for p in missing_prereqs]}")

        # ✅ CORRIGÉ: Sans validated_taxon
        return ValidationResult(
            status=ValidationStatus.CLARIFY,
            confidence=0.5,
            primary_taxon_id=candidate.taxon_id,
            validated_taxon_name=candidate.name,
            violations=violations,
            clarification_question=question,
            validation_time_ms=elapsed_ms
        )    
    
    def _clarify_slots(
        self,
        candidate: TaxonCandidate,
        missing_slots: List[str],
        start_time: float
    ) -> ValidationResult:
        """Construit un résultat CLARIFY pour slots manquants - CORRIGÉ"""

        elapsed_ms = (time.time() - start_time) * 1000

        # ✅ CORRIGÉ: Utiliser 'type' au lieu de 'violation_type'
        violations = [
            Violation(
                type=ViolationType.MISSING_PREREQ_SOFT,
                details=f"Information nécessaire: {slot}",
                affected_entity=candidate.taxon_id,
                severity="medium"
            )
            for slot in missing_slots
        ]

        if len(missing_slots) == 1:
            question = f"Pour '{candidate.name}', pouvez-vous préciser : {missing_slots[0]} ?"
        else:
            question = f"Pour '{candidate.name}', pouvez-vous préciser : {', '.join(missing_slots)} ?"

        logger.info(f"❓ CLARIFY - Missing slots: {missing_slots}")

        # ✅ CORRIGÉ: Sans validated_taxon
        return ValidationResult(
            status=ValidationStatus.CLARIFY,
            confidence=0.5,
            primary_taxon_id=candidate.taxon_id,
            validated_taxon_name=candidate.name,
            violations=violations,
            clarification_question=question,
            validation_time_ms=elapsed_ms
        )
    
    
    def _clarify_confirmation(
        self,
        candidate: TaxonCandidate,
        confidence: float,
        alternatives: List[TaxonCandidate],
        start_time: float
    ) -> ValidationResult:
        """Demande confirmation car confiance moyenne - CORRIGÉ"""

        elapsed_ms = (time.time() - start_time) * 1000

        question = f"Voulez-vous dire '{candidate.name}' ?"
        if alternatives:
            alt_names = [c.name for c in alternatives]
            question += f" Ou peut-être : {', '.join(alt_names)} ?"

        logger.info(f"❓ CLARIFY - Low confidence ({confidence:.3f}), asking confirmation")

        # ✅ CORRIGÉ: Utiliser 'type' au lieu de 'violation_type'
        violations = [
            Violation(
                type=ViolationType.AMBIGUOUS_LOW_MARGIN,
                details=f"Confiance moyenne ({confidence:.2f}), confirmation requise",
                affected_entity=candidate.taxon_id,
                severity="low"
            )
        ]

        # ✅ CORRIGÉ: Sans validated_taxon
        return ValidationResult(
            status=ValidationStatus.CLARIFY,
            confidence=confidence,
            primary_taxon_id=candidate.taxon_id,
            validated_taxon_name=candidate.name,
            violations=violations,
            clarification_question=question,
            suggested_candidates=alternatives,  # ✅ Liste de TaxonCandidate
            validation_time_ms=elapsed_ms
        )
    
    
    def _abstain(self, reason: str, start_time: float) -> ValidationResult:
        """Construit un résultat ABSTAIN - CORRIGÉ"""
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        logger.info(f"⛔ ABSTAIN - {reason}")
        
        # ✅ CORRIGÉ: ValidationResult minimal pour ABSTAIN
        return ValidationResult(
            status=ValidationStatus.ABSTAIN,
            confidence=0.0,
            validation_time_ms=elapsed_ms
        )
    
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def _get_taxon_name(self, taxon_id: str) -> str:
        """Récupère le nom d'un taxon depuis metadata (si disponible)"""
        if self.taxonomy_metadata:
            return self.taxonomy_metadata.get(taxon_id, {}).get('name', f'Taxon {taxon_id}')
        return f'Taxon {taxon_id}'