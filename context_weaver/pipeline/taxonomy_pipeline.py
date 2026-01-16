#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaxonomyPipeline - CORRECTION des attributs ValidationResult
✅ Utilise violations au lieu de missing_requirements
✅ Utilise missing_prereq_hard/soft
"""

import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from context_weaver.taxonomy.taxonomy_models import (
    ValidationResult,
    ValidationStatus,
    ConversationState,
    Violation,
    ViolationType
)
from context_weaver.taxonomy.taxonomy_retriever import TaxonomyRetriever, RetrievalResult, RetrievalConfig
from context_weaver.taxonomy.taxonomy_validator import TaxonomyValidator

logger = logging.getLogger(__name__)


@dataclass
class TaxonomyPipelineOutput:
    """Résultat complet du pipeline taxonomy"""
    
    status: str  # "PASS", "CLARIFY", "ABSTAIN", "ERROR"
    retrieval_result: Optional[RetrievalResult] = None
    validation_result: Optional[ValidationResult] = None
    can_access_graph: bool = False
    validated_taxon_id: Optional[str] = None
    validated_taxon_name: Optional[str] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    abstain_reason: Optional[str] = None
    total_time_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'can_access_graph': self.can_access_graph,
            'validated_taxon_id': self.validated_taxon_id,
            'validated_taxon_name': self.validated_taxon_name,
            'clarification_needed': self.clarification_needed,
            'clarification_question': self.clarification_question,
            'abstain_reason': self.abstain_reason,
            'total_time_ms': self.total_time_ms,
            'retrieval_stats': {
                'total_candidates': self.retrieval_result.total_retrieved if self.retrieval_result else 0,
                'top_score': self.retrieval_result.rrf_top_score if self.retrieval_result else 0.0
            } if self.retrieval_result else {},
            'validation_stats': {
                'confidence': self.validation_result.confidence if self.validation_result else 0.0,
                'validation_time_ms': self.validation_result.validation_time_ms if self.validation_result else 0.0
            } if self.validation_result else {},
            'details': self.details
        }


class TaxonomyPipeline:
    """Pipeline complet Phase 2 avec Enhanced Logging"""
    
    def __init__(
        self,
        vector_store,
        embedder,
        retrieval_config: Optional[RetrievalConfig] = None,
        taxonomy_metadata: Optional[Dict] = None
    ):
        logger.info("=" * 80)
        logger.info("📚 TAXONOMY PIPELINE - INITIALIZATION")
        logger.info("=" * 80)
        
        init_start = time.time()
        
        # Retriever
        logger.info("🔍 Step 1/2: Initializing Retriever")
        config = retrieval_config or RetrievalConfig()
        
        self.retriever = TaxonomyRetriever(
            vector_store=vector_store,
            embedder=embedder,
            config=config
        )
        logger.info("   ✅ Retriever ready")
        
        # Validator
        logger.info("\n🔍 Step 2/2: Initializing Validator")
        self.validator = TaxonomyValidator(taxonomy_metadata=taxonomy_metadata)
        logger.info("   ✅ Validator ready")
        
        init_time = (time.time() - init_start) * 1000
        logger.info(f"\n✅ TaxonomyPipeline initialized in {init_time:.2f}ms")
        logger.info("=" * 80 + "\n")
    
    
    def process(
        self,
        user_query: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_state: Optional[ConversationState] = None
    ) -> TaxonomyPipelineOutput:
        """Traite une requête utilisateur"""
        start_time = time.time()
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 TAXONOMY PIPELINE - EXECUTION START")
        logger.info("=" * 80)
        logger.info(f"📝 Query: {user_query[:100]}{'...' if len(user_query) > 100 else ''}")
        logger.info(f"📏 Query length: {len(user_query)} chars")
        
        user_context = user_context or {}
        
        # Log context
        if user_context:
            logger.info(f"🔧 Context provided:")
            logger.info(f"   • Domain: {user_context.get('domain', 'N/A')}")
            logger.info(f"   • Task: {user_context.get('task', 'N/A')}")
            logger.info(f"   • Variables: {len(user_context.get('variables', []))} items")
            logger.info(f"   • Slots: {len(user_context.get('slots', {}))} filled")
        
        # Log conversation state
        if conversation_state:
            logger.info(f"💬 Conversation state:")
            logger.info(f"   • ID: {conversation_state.conversation_id}")
            logger.info(f"   • Confirmed taxons: {len(conversation_state.confirmed_taxons)}")
            logger.info(f"   • Filled slots: {len(conversation_state.filled_slots)}")
        
        try:
            # ÉTAPE 1: RETRIEVAL
            step_start = time.time()
            logger.info("\n" + "─" * 80)
            logger.info("🔍 STEP 1/3: Retrieval (Hybrid Search)")
            logger.info("─" * 80)
            
            retrieval_result = self.retriever.retrieve(
                query_text=user_query,
                context=user_context
            )
            
            step_time = (time.time() - step_start) * 1000
            
            if not retrieval_result.candidates:
                logger.warning(f"⚠️ No candidates found in {step_time:.2f}ms")
                return self._error_output(
                    "Aucun candidat trouvé",
                    retrieval_result,
                    None,
                    start_time
                )
            
            logger.info(f"✅ Retrieval completed in {step_time:.2f}ms")
            logger.info(f"📊 Retrieval statistics:")
            logger.info(f"   • Dense results: {retrieval_result.dense_count}")
            logger.info(f"   • BM25 results: {retrieval_result.bm25_count}")
            logger.info(f"   • Total candidates: {retrieval_result.total_retrieved}")
            logger.info(f"   • Top RRF score: {retrieval_result.rrf_top_score:.4f}")
            logger.info(f"   • Score range: [{retrieval_result.rrf_min_score:.4f}, {retrieval_result.rrf_max_score:.4f}]")
            
            # Top 5 candidates
            logger.info(f"\n🏆 Top 5 candidates:")
            for i, candidate in enumerate(retrieval_result.candidates[:5], 1):
                logger.info(f"   {i}. {candidate.name}")
                logger.info(f"      • ID: {candidate.taxon_id}")
                logger.info(f"      • Score: {candidate.final_score:.4f}")
                logger.info(f"      • Breadcrumb: {candidate.breadcrumb}")
                logger.info(f"      • Depth: {candidate.depth}")
            
            if retrieval_result.total_retrieved > 5:
                logger.info(f"   ... and {retrieval_result.total_retrieved - 5} more")
            
            # ÉTAPE 2: VALIDATION
            step_start = time.time()
            logger.info("\n" + "─" * 80)
            logger.info("🔍 STEP 2/3: Validation")
            logger.info("─" * 80)
            logger.info(f"🎯 Validating {len(retrieval_result.candidates)} candidates...")
            
            validation_result = self.validator.validate(
                candidates=retrieval_result.candidates,
                user_context=user_context,
                conversation_state=conversation_state
            )
            
            step_time = (time.time() - step_start) * 1000
            logger.info(f"✅ Validation completed in {step_time:.2f}ms")
            
            # Log validation details
            logger.info(f"📊 Validation result:")
            logger.info(f"   • Status: {validation_result.status.value}")
            logger.info(f"   • Confidence: {validation_result.confidence:.3f}")

            # ✅ FIX: Tous les attributs avec hasattr
            if hasattr(validation_result, 'primary_taxon_id') and validation_result.primary_taxon_id:
                logger.info(f"   • Validated taxon: {validation_result.validated_taxon_name}")
                logger.info(f"     - ID: {validation_result.primary_taxon_id}")

            if hasattr(validation_result, 'violations') and validation_result.violations:
                logger.info(f"   • Violations: {len(validation_result.violations)}")
                for violation in validation_result.violations[:3]:
                    logger.info(f"     - {violation.type.value}: {violation.details}")

            if hasattr(validation_result, 'suggested_candidates') and validation_result.suggested_candidates:
                logger.info(f"   • Suggested candidates: {len(validation_result.suggested_candidates)}")
                for cand in validation_result.suggested_candidates[:3]:
                    logger.info(f"     - {cand.name} ({cand.taxon_id})")

            if hasattr(validation_result, 'clarification_question') and validation_result.clarification_question:
                logger.info(f"   • Clarification: {validation_result.clarification_question}")

            if hasattr(validation_result, 'abstain_reason') and validation_result.abstain_reason:
                logger.info(f"   • Abstain reason: {validation_result.abstain_reason}")
            
            # ÉTAPE 3: DECISION
            step_start = time.time()
            logger.info("\n" + "─" * 80)
            logger.info("🎯 STEP 3/3: Decision & Output Building")
            logger.info("─" * 80)
            
            output = self._build_output(
                retrieval_result,
                validation_result,
                start_time
            )
            
            step_time = (time.time() - step_start) * 1000
            logger.info(f"✅ Output built in {step_time:.2f}ms")
            
            self._log_final_summary(output)
            
            return output
        
        except Exception as e:
            exec_time = (time.time() - start_time) * 1000
            logger.error("\n" + "=" * 80)
            logger.error("❌ PIPELINE ERROR")
            logger.error("=" * 80)
            logger.error(f"Error: {e}")
            logger.error(f"Execution time before error: {exec_time:.2f}ms")
            logger.exception("Stack trace:")
            
            return self._error_output(
                f"Pipeline error: {str(e)}",
                None,
                None,
                start_time
            )
    
    
    def _build_output(
        self,
        retrieval_result: RetrievalResult,
        validation_result: ValidationResult,
        start_time: float
    ) -> TaxonomyPipelineOutput:
        """Construit l'output selon le status - CORRIGÉ"""
        
        total_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"📄 Building output for status: {validation_result.status.value}")
        
        # PASS
        if validation_result.status == ValidationStatus.PASS:
            logger.debug("   • Building PASS output...")
            
            # ✅ FIX: Utiliser primary_taxon_id et validated_taxon_name
            output = TaxonomyPipelineOutput(
                status="PASS",
                retrieval_result=retrieval_result,
                validation_result=validation_result,
                can_access_graph=True,
                validated_taxon_id=validation_result.primary_taxon_id,      # ✅ FIX
                validated_taxon_name=validation_result.validated_taxon_name, # ✅ FIX
                total_time_ms=total_time_ms,
                details={
                    'confidence': validation_result.confidence,
                    # ✅ Ces champs ne sont plus dans validated_taxon
                    # 'breadcrumb': validation_result.validated_taxon.breadcrumb,
                    # 'depth': validation_result.validated_taxon.depth
                }
            )
            
            logger.debug(f"   ✓ PASS output ready (taxon: {output.validated_taxon_name})")
            return output
        
        # CLARIFY
        elif validation_result.status == ValidationStatus.CLARIFY:
            logger.debug("   • Building CLARIFY output...")
            
            # ✅ CORRECTION: Convertir violations en format compatible
            missing_reqs = []
            if validation_result.violations:
                for violation in validation_result.violations:
                    missing_reqs.append({
                        'type': violation.type.value,  # ✅ 'type' pas 'violation_type'
                        'description': violation.details,
                        'affected_entity': violation.affected_entity
                    })
            
            output = TaxonomyPipelineOutput(
                status="CLARIFY",
                retrieval_result=retrieval_result,
                validation_result=validation_result,
                can_access_graph=False,
                clarification_needed=True,
                clarification_question=validation_result.clarification_question,
                total_time_ms=total_time_ms,
                details={
                    'missing_requirements': missing_reqs,
                    'suggested_candidates': [
                        {'id': c.taxon_id, 'name': c.name}
                        for c in validation_result.suggested_candidates
                    ] if validation_result.suggested_candidates else []
                }
            )
            
            logger.debug(f"   ✓ CLARIFY output ready ({len(missing_reqs)} missing)")
            return output
        
        # ABSTAIN ou autres
        else:
            logger.debug("   • Building ABSTAIN output...")
            
            # ✅ FIX: abstain_reason peut ne pas exister
            abstain_reason = getattr(validation_result, 'abstain_reason', 'Unknown reason')
            
            output = TaxonomyPipelineOutput(
                status="ABSTAIN",
                retrieval_result=retrieval_result,
                validation_result=validation_result,
                can_access_graph=False,
                abstain_reason=abstain_reason,
                total_time_ms=total_time_ms,
                details={
                    'reason': abstain_reason
                }
            )
            
            logger.debug(f"   ✓ ABSTAIN output ready (reason: {output.abstain_reason})")
            return output
        
    
    def _error_output(
        self,
        error_message: str,
        retrieval_result: Optional[RetrievalResult],
        validation_result: Optional[ValidationResult],
        start_time: float
    ) -> TaxonomyPipelineOutput:
        """Construit un output d'erreur"""
        
        total_time_ms = (time.time() - start_time) * 1000
        
        logger.error(f"🔴 Creating ERROR output: {error_message}")
        
        return TaxonomyPipelineOutput(
            status="ERROR",
            retrieval_result=retrieval_result,
            validation_result=validation_result,
            can_access_graph=False,
            total_time_ms=total_time_ms,
            details={'error': error_message}
        )
    
    
    def _log_final_summary(self, output: TaxonomyPipelineOutput):
        """Log le résumé final détaillé"""
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 TAXONOMY PIPELINE - EXECUTION SUMMARY")
        logger.info("=" * 80)
        
        # Status
        status_emoji = {
            "PASS": "✅",
            "CLARIFY": "❓",
            "ABSTAIN": "⛔",
            "ERROR": "❌"
        }
        emoji = status_emoji.get(output.status, "❓")
        
        logger.info(f"{emoji} Final Status: {output.status}")
        logger.info(f"⏱️  Total execution time: {output.total_time_ms:.2f}ms")
        
        # Détails par status
        logger.info("")
        
        if output.status == "PASS":
            logger.info("✅ GRAPH ACCESS AUTHORIZED")
            logger.info(f"   • Validated taxon: {output.validated_taxon_name}")
            logger.info(f"   • Taxon ID: {output.validated_taxon_id}")
            logger.info(f"   • Confidence: {output.details.get('confidence', 0):.3f}")
        
        elif output.status == "CLARIFY":
            logger.info("❓ CLARIFICATION REQUIRED")
            logger.info(f"   • Question: {output.clarification_question}")
            missing = output.details.get('missing_requirements', [])
            logger.info(f"   • Missing requirements: {len(missing)}")
            for i, req in enumerate(missing[:5], 1):
                logger.info(f"     {i}. {req.get('type')}: {req.get('description')}")
        
        elif output.status == "ABSTAIN":
            logger.info("⛔ ABSTAIN - Cannot proceed")
            logger.info(f"   • Reason: {output.abstain_reason}")
        
        else:  # ERROR
            logger.info("❌ ERROR - Pipeline failed")
            logger.info(f"   • Error: {output.details.get('error', 'Unknown error')}")
        
        logger.info("\n" + "=" * 80 + "\n")