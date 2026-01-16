#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pipeline Context Weaver - Version Refactorisée (Sans ContextWeaver)
✅ CORRIGÉ: PipelineOutput sans context_weaver obligatoire
✅ FIX: Stockage taxonomy_output dans metadata
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from context_weaver.models.schemas import (
    PipelineOutput,
    SearchResult,
    HybridSearchResults,
    OSSClassification,
    NormalizedVariables
)

from context_weaver.taxonomy.taxonomy_models import (
    ConversationState,
    PrereqSnapshot,
    TaxonomyPipelineOutput
)
from context_weaver.pipeline.taxonomy_pipeline import (
    TaxonomyPipeline,
    TaxonomyPipelineOutput
)
from context_weaver.taxonomy.taxonomy_retriever import RetrievalConfig

from context_weaver.services.oss_classifier import OSSClassifierClient
from context_weaver.data.vector_store import VectorStore
from context_weaver.learner.graph_structure_learner import GraphStructureLearner

logger = logging.getLogger(__name__)


class ContextWeaverPipeline:
    """
    ✅ Pipeline Unifié REFACTORISÉ (Sans ContextWeaver)
    
    Changements:
    - ❌ SUPPRIMÉ: ContextWeaver (entièrement)
    - ✅ GraphStructureLearner: Responsable du filtrage des résultats
    - ✅ Output simplifié: PipelineOutput avec filtered_candidates du learner
    - ✅ FIX: context_weaver optionnel dans PipelineOutput
    """
    
    def __init__(
        self,
        dgraph_connector=None,
        vector_store=None,
        oss_client=None,
        project_name: str = None,
        dgraph_url: str = "localhost:9080",
        auto_init: bool = True,
        prereq_snapshot_path: Path = None,
        graph_learner_model_path: Path = None,
        enable_taxonomy_validation: bool = True
    ):
        logger.info("=" * 80)
        logger.info("🗂️ CONTEXT WEAVER PIPELINE - INITIALIZATION (Sans ContextWeaver)")
        logger.info("=" * 80)
        
        step_start = time.time()
        
        # === COMPOSANTS DE BASE ===
        logger.info("\n📦 Step 1/5: Initializing Core Components")
        if auto_init and self._needs_init(dgraph_connector, oss_client):
            self._auto_init(dgraph_url, project_name)
        else:
            self.dgraph = dgraph_connector
            self.vector_store = vector_store
            self.oss_client = oss_client
            self.project_name = project_name or "default_project"
        
        logger.info(f"   ✅ Core components initialized in {(time.time() - step_start)*1000:.2f}ms")
        
        # === SERVICES CLASSIQUES ===
        step_start = time.time()
        logger.info("\n🔧 Step 2/5: Initializing Services")
        self._init_services()
        logger.info(f"   ✅ Services initialized in {(time.time() - step_start)*1000:.2f}ms")
        
        # === CONVERSATION STATE MANAGER ===
        logger.info("\n💬 Step 3/5: Setting up Conversation Manager")
        self.conversation_states: Dict[str, ConversationState] = {}
        logger.info("   ✅ Conversation manager ready")
        
        # === TAXONOMY PIPELINE + GRAPH LEARNER ===
        step_start = time.time()
        logger.info("\n📚 Step 4/5: Initializing Taxonomy Pipeline + Graph Learner")
        self.enable_taxonomy_validation = enable_taxonomy_validation
        
        if enable_taxonomy_validation:
            # Embedder
            logger.info("   • Loading embedder wrapper...")
            from context_weaver.services.embedder_wrapper import EmbedderWrapper
            self.embedder = EmbedderWrapper(oss_client=self.oss_client)
            
            # PrereqSnapshot
            logger.info("   • Loading prereq snapshot...")
            prereq_path = prereq_snapshot_path or Path("./data/prereq_snapshot_v1.json")
            if prereq_path.exists():
                self.prereq_snapshot = PrereqSnapshot.load_from_json(str(prereq_path))
                logger.info(f"     ✓ PrereqSnapshot loaded: {len(self.prereq_snapshot.prereq_hard)} hard prereqs")
            else:
                logger.warning(f"     ⚠️ PrereqSnapshot not found: {prereq_path}")
                self.prereq_snapshot = PrereqSnapshot()
            
            # Graph Structure Learner (responsable du filtrage)
            logger.info("   • Initializing graph structure learner...")
            learner_path = graph_learner_model_path or Path("./data/graph_structure_model.json")
            self.graph_learner = GraphStructureLearner(model_path=learner_path)
            logger.info("     ✓ Graph learner ready (filtrage activé)")
            
            # TaxonomyPipeline
            logger.info("   • Building taxonomy pipeline...")
            retrieval_config = RetrievalConfig(
                dense_top_k=100,
                bm25_top_k=100,
                rrf_k=60,
                final_top_n=30,
                boost_by_depth=True
            )
            
            self.taxonomy_pipeline = TaxonomyPipeline(
                vector_store=self.vector_store,
                embedder=self.embedder,
                retrieval_config=retrieval_config,
                taxonomy_metadata=self._build_taxonomy_metadata()
            )
            
            logger.info(f"   ✅ Taxonomy pipeline + Graph Learner initialized in {(time.time() - step_start)*1000:.2f}ms")
        else:
            self.taxonomy_pipeline = None
            self.prereq_snapshot = None
            self.graph_learner = None
            self.embedder = None
            logger.info("   ⚠️ Taxonomy validation disabled")
        
        logger.info("\n✅ Step 5/5: Pipeline Ready (Learner gère le filtrage)")
        logger.info("=" * 80 + "\n")

    def _get_status_string(self, taxonomy_output):
        """Helper pour extraire status en string (gère enum et string)"""
        if not taxonomy_output:
            return 'NO_TAXONOMY'
        
        from context_weaver.taxonomy.taxonomy_models import ValidationStatus
        
        status = taxonomy_output.status
        
        if isinstance(status, ValidationStatus):
            return status.value
        elif isinstance(status, str):
            return status
        else:
            logger.warning(f"⚠️ Unknown status type: {type(status)}")
            return 'UNKNOWN'
    
    def _normalize_domain(self, oss_domain: str) -> str:
        """
        Normalise le domaine OSS vers le domaine des indexes
        
        Args:
            oss_domain: Domaine retourné par OSS Classifier
            
        Returns:
            Domaine normalisé pour les indexes
        """
        DOMAIN_MAPPING = {
            'compliance': 'Macompta.fr',
            'accounting': 'Macompta.fr',
            'finance': 'Macompta.fr',
            'comptabilité': 'Macompta.fr',
            'gestion': 'Macompta.fr',
        }
        
        normalized = DOMAIN_MAPPING.get(oss_domain.lower(), oss_domain)
        
        if normalized != oss_domain:
            logger.info(f"🔄 Domain mapping: '{oss_domain}' → '{normalized}'")
        
        return normalized
    
    
    def run(
        self,
        user_context: str,
        conversation_id: str = "default",
        session_state: Optional[Dict[str, Any]] = None
    ) -> PipelineOutput:
        """
        ✅ Pipeline principal REFACTORISÉ (Sans ContextWeaver)
        
        Changements:
        - Délègue TOUTE la recherche à taxonomy_pipeline
        - GraphLearner filtre les résultats (sans toucher au scoring)
        - context_weaver optionnel dans PipelineOutput
        """
        pipeline_start = time.time()
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 CONTEXT WEAVER PIPELINE - EXECUTION START (Learner Filtrage)")
        logger.info("=" * 80)
        logger.info(f"🔍 Query: {user_context[:100]}{'...' if len(user_context) > 100 else ''}")
        logger.info(f"🔑 Conversation ID: {conversation_id}")
        logger.info(f"📊 Query length: {len(user_context)} chars")
        if session_state:
            logger.info(f"💾 Session state keys: {list(session_state.keys())}")
        
        try:
            # === ÉTAPE 1: OSS CLASSIFICATION ===
            step_start = time.time()
            logger.info("\n" + "─" * 80)
            logger.info("📊 STEP 1/2: OSS Classification")
            logger.info("─" * 80)
            
            classification = self.oss_client.classify(user_context)
            
            # Normaliser le domaine
            original_domain = classification.domain
            normalized_domain = self._normalize_domain(original_domain)
            classification.domain = normalized_domain
            
            normalized = self._normalize(classification)
            
            step_time = (time.time() - step_start) * 1000
            logger.info(f"✅ Classification completed in {step_time:.2f}ms")
            logger.info(f"   • Domain (original): {original_domain}")
            logger.info(f"   • Domain (normalized): {normalized_domain}")
            logger.info(f"   • Task: {classification.task}")
            logger.info(f"   • Variables count: {len(classification.variables)}")
            
            # === ÉTAPE 2: TAXONOMY PIPELINE + FILTRAGE LEARNER ===
            step_start = time.time()
            logger.info("\n" + "─" * 80)
            logger.info("🔍 STEP 2/2: Taxonomy Pipeline + Learner Filtrage")
            logger.info("─" * 80)
            
            # ✅ TOUJOURS utiliser taxonomy_pipeline
            exec_time = time.time() - pipeline_start
            taxonomy_output = self._run_taxonomy_pipeline(
                user_context,
                classification,
                normalized,
                conversation_id,
                session_state,
                exec_time
            )
            
            # ✅ NOUVEAU: Filtrage par Graph Learner (sans toucher au scoring)
            filtered_results = self._filter_with_graph_learner(
                taxonomy_output,
                classification,
                normalized
            )
            
            step_time = (time.time() - step_start) * 1000
            logger.info(f"✅ Taxonomy + Learner filtrage completed in {step_time:.2f}ms")
            
            # ✅ CORRIGÉ: PipelineOutput avec context_weaver optionnel
            output = PipelineOutput(
                classification=classification,
                normalized=normalized,
                search_results=filtered_results,
                execution_time_ms=(time.time() - pipeline_start) * 1000,
                context_weaver=None,
                metadata={
                    'taxonomy_output': {
                        'status': self._get_status_string(taxonomy_output),
                        'can_access_graph': taxonomy_output.can_access_graph if taxonomy_output else False,
                        'validated_taxon_id': taxonomy_output.validated_taxon_id if taxonomy_output else None,
                        'validated_taxon_name': taxonomy_output.validated_taxon_name if taxonomy_output else None,
                        'clarification_question': taxonomy_output.clarification_question if taxonomy_output else None,
                        
                        # ✅ FIX: missing_requirements est dans details, pas un attribut direct
                        'missing_requirements': (
                            taxonomy_output.details.get('missing_requirements', []) 
                            if taxonomy_output and taxonomy_output.details 
                            else []
                        ),
                        
                        # ✅ FIX: suggested_candidates aussi dans details
                        'suggested_candidates': (
                            taxonomy_output.details.get('suggested_candidates', []) 
                            if taxonomy_output and taxonomy_output.details 
                            else []
                        ),
                        
                        'confidence': (
                            taxonomy_output.details.get('confidence', 0.0) 
                            if taxonomy_output and taxonomy_output.details 
                            else 0.0
                        ),
                        
                        'details': taxonomy_output.details if taxonomy_output else {}
                    }
                }
            )
            
            return output
            
        except Exception as e:
            exec_time = (time.time() - pipeline_start) * 1000
            logger.error("\n" + "=" * 80)
            logger.error("❌ PIPELINE ERROR")
            logger.error("=" * 80)
            logger.error(f"Error: {e}")
            logger.error(f"Execution time before error: {exec_time:.2f}ms")
            logger.exception("Stack trace:")
            raise
    
    
    def _run_taxonomy_pipeline(
        self,
        user_context: str,
        classification: OSSClassification,
        normalized: NormalizedVariables,
        conversation_id: str,
        session_state: Optional[Dict[str, Any]],
        pipeline_start: float
    ) -> TaxonomyPipelineOutput:
        """
        ✅ REFACTORISÉ: Exécute taxonomy_pipeline (validation ON ou OFF)
        
        Mode validation=True: Gate prereqs + validation
        Mode validation=False: Retrieval seul (pas de gate)
        """
        
        if not self.taxonomy_pipeline:
            # Cas où taxonomy_pipeline n'existe pas (erreur config)
            logger.error("❌ Taxonomy pipeline not initialized")
            raise ValueError("Taxonomy pipeline required")
        
        # Préparer contexte enrichi pour taxonomy_pipeline
        enriched_context = {
            'domain': classification.domain,
            'task': classification.task,
            'variables': classification.variables,
            'key_variables': list(normalized.variables.values())[:10]
        }
        
        # Ajouter structure hint du learner (sans modifier scoring)
        if self.graph_learner:
            try:
                structure_hypothesis = self.graph_learner.predict_structure(
                    context={
                        'domain': classification.domain,
                        'variables': enriched_context['key_variables'],
                        'task': classification.task
                    },
                    candidates=[],  # Pas de candidats initiaux
                    prereq_cache=self.prereq_snapshot
                )
                
                enriched_context['structure_hint'] = {
                    'primary_label_id': getattr(structure_hypothesis, 'primary_label_id', None),
                    'expected_prereqs': getattr(structure_hypothesis, 'expected_prereq_hard_ids', []),
                    'confidence': getattr(structure_hypothesis, 'confidence', 0.0)
                }
                
                logger.info(f"   • Structure hint: {enriched_context['structure_hint']}")
                
            except Exception as e:
                logger.warning(f"   ⚠️ Learner prediction failed: {e}")
        
        from context_weaver.taxonomy.taxonomy_models import ConversationState
        
        conv_state = ConversationState(conversation_id=conversation_id)
        if session_state:
            if 'confirmed_taxons' in session_state:
                conv_state.confirmed_taxons = session_state['confirmed_taxons']
            if 'filled_slots' in session_state:
                conv_state.filled_slots = session_state['filled_slots']
        
        taxonomy_output = self.taxonomy_pipeline.process(
            user_query=user_context,
            user_context=enriched_context,
            conversation_state=conv_state
        )
        
        logger.info(f"   • Status: {taxonomy_output.status}")
        logger.info(f"   • Can access graph: {taxonomy_output.can_access_graph}")
        
        # Mise à jour de l'état de conversation
        self._update_conversation_state(conversation_id, taxonomy_output)
        
        return taxonomy_output
    
    
    def _filter_with_graph_learner(
        self,
        taxonomy_output: TaxonomyPipelineOutput,
        classification: OSSClassification,
        normalized: NormalizedVariables
    ) -> HybridSearchResults:
        """
        ✅ NOUVEAU: Filtrage par GraphStructureLearner (sans toucher au scoring)
        
        - Utilise validate_structure pour filtrer (basé sur quality_category)
        - Conserve les scores originaux (RRR du retrieval)
        - Retourne HybridSearchResults avec résultats filtrés
        """
        if not self.graph_learner or not taxonomy_output.retrieval_result:
            # Fallback: Retourner résultats originaux sans filtrage
            return self._build_search_results_from_taxonomy(taxonomy_output)
        
        logger.info(f"   🔍 Filtrage Learner: {len(taxonomy_output.retrieval_result.candidates)} candidats")
        
        context = {
            'domain': classification.domain,
            'variables': list(normalized.variables.values()),
            'task': classification.task
        }
        
        filtered_candidates = []
        for candidate in taxonomy_output.retrieval_result.candidates:
            # Convertir en structure pour validation (sans modifier scoring)
            structure = {
                'id': candidate.taxon_id,
                'name': candidate.name,
                'domain': candidate.metadata.get('domain', ''),
                'type': 'taxon',
                'dgraph.type': 'TaxonomyNode',
                'definition': candidate.definition,
                'breadcrumb': candidate.breadcrumb,
                'depth': candidate.depth
            }
            
            # Valider (ne touche pas au scoring interne du learner)
            try:
                validation = self.graph_learner.validate_structure(structure, context)
                
                # Filtrer basé sur quality_category (ex: garder HIGH/MEDIUM)
                if validation['quality_category'] in ['HIGH', 'MEDIUM']:
                    # Enrichir metadata sans altérer score original
                    if not candidate.metadata:
                        candidate.metadata = {}
                    candidate.metadata['graph_validation'] = {
                        'score': validation['quality_score'],
                        'confidence': validation['confidence'],
                        'category': validation['quality_category'],
                        'issues': validation.get('issues', [])
                    }
                    filtered_candidates.append(candidate)
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Filtrage failed for {candidate.name}: {e}")
                # En cas d'erreur, garder le candidat (conservatif)
                filtered_candidates.append(candidate)
        
        logger.info(f"   ✅ Filtré: {len(filtered_candidates)} / {len(taxonomy_output.retrieval_result.candidates)} gardés")
        
        # Construire HybridSearchResults avec candidats filtrés
        search_results_list = []
        for candidate in filtered_candidates[:10]:  # Limiter top 10
            result = SearchResult(
                id=candidate.taxon_id,
                name=candidate.name,
                domain=candidate.metadata.get('domain', ''),
                type="taxon",
                score=candidate.final_score,  # Score original préservé
                method="taxonomy_rrf_learner_filtered",
                content={
                    'definition': candidate.definition,
                    'breadcrumb': candidate.breadcrumb,
                    'depth': candidate.depth
                },
                metadata=candidate.metadata
            )
            search_results_list.append(result)
        
        retrieval = taxonomy_output.retrieval_result
        return HybridSearchResults(
            results=search_results_list,
            bm25_count=getattr(retrieval, 'bm25_count', 0),
            embedding_count=getattr(retrieval, 'dense_count', 0),
            final_count=len(search_results_list),
            fusion_method="taxonomy_rrf_learner_filtered"
        )
       
    def _update_conversation_state(self, conversation_id: str, taxonomy_output: TaxonomyPipelineOutput):
        """Mise à jour de l'état de conversation (FIX: status handling)"""

        # ✅ FIX: Gérer ValidationStatus enum ET string
        from context_weaver.taxonomy.taxonomy_models import ValidationStatus

        if isinstance(taxonomy_output.status, ValidationStatus):
            status_str = taxonomy_output.status.value
        elif isinstance(taxonomy_output.status, str):
            status_str = taxonomy_output.status
        else:
            logger.warning(f"⚠️ Unknown status type: {type(taxonomy_output.status)}")
            return

        if status_str == 'PASS' and taxonomy_output.validated_taxon_id:
            logger.info(f"💾 Updating conversation state...")
            if conversation_id not in self.conversation_states:
                self.conversation_states[conversation_id] = ConversationState(conversation_id=conversation_id)

            state = self.conversation_states[conversation_id]

            # ✅ FIX: confirmed_taxons est une list → append + check duplicate
            if taxonomy_output.validated_taxon_id not in state.confirmed_taxons:
                state.confirmed_taxons.append(taxonomy_output.validated_taxon_id)
                logger.info(f"   ✔ Added confirmed taxon: {taxonomy_output.validated_taxon_id}")
            else:
                logger.info(f"   ℹ️ Taxon {taxonomy_output.validated_taxon_id} already confirmed")
    
    
    def _log_final_summary(self, output: PipelineOutput, total_time: float):
        """Log le résumé final"""
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 PIPELINE EXECUTION SUMMARY (Learner Filtrage)")
        logger.info("=" * 80)
        logger.info(f"⏱️  Total execution time: {total_time:.2f}ms")
        logger.info(f"📊 Classification: {output.classification.domain} / {output.classification.task}")
        logger.info(f"🔍 Search results: {output.search_results.final_count} items (filtrés)")
        logger.info(f"🔗 Fusion method: {output.search_results.fusion_method}")
        
        # Log top 3 filtrés
        if output.search_results.results:
            logger.info("\n🏆 Top 3 filtrés:")
            for i, result in enumerate(output.search_results.results[:3], 1):
                logger.info(f"   {i}. {result.name} (score: {result.score:.4f})")
                if 'graph_validation' in result.metadata:
                    val = result.metadata['graph_validation']
                    logger.info(f"      • Validation: {val['category']} (learner score: {val['score']:.3f})")
        
        logger.info("=" * 80 + "\n")
    
    
    # ========================================================================
    # HELPERS (conservés, pas de redondance)
    # ========================================================================
    
    def _needs_init(self, dgraph, oss) -> bool:
        return dgraph is None or oss is None
    
    def _auto_init(self, dgraph_url: str, project_name: Optional[str]):
        logger.info("   🔄 Auto-initializing components...")
        
        try:
            logger.debug("   • Creating OSS client...")
            self.oss_client = OSSClassifierClient()
            
            try:
                logger.debug("   • Connecting to Dgraph...")
                from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
                self.dgraph = TaxonomyDgraphConnector()
                logger.debug("   ✓ Dgraph connected")
            except Exception as e:
                logger.warning(f"   ⚠️ Dgraph unavailable: {e}")
                self.dgraph = None
            
            logger.debug("   • Initializing vector store...")
            self.vector_store = VectorStore()
            self.vector_store.initialize()
            
            self.project_name = project_name or "default_project"
            
        except Exception as e:
            logger.error(f"   ❌ Auto-init error: {e}")
            raise
    
    def _init_services(self):
        # Plus de ContextWeaver
        logger.debug("   ✓ Services initialized (sans ContextWeaver)")
    
    def _normalize(self, classification: OSSClassification) -> NormalizedVariables:
        mapping = {v: v for v in classification.variables}
        return NormalizedVariables(
            variables=mapping,
            domain_taxonomy=classification.variables
        )
    
    def _build_taxonomy_metadata(self) -> Dict[str, Any]:
        return {}
    
    def _build_search_results_from_taxonomy(
        self,
        taxonomy_output: TaxonomyPipelineOutput
    ) -> HybridSearchResults:
        """✅ Construit HybridSearchResults depuis TaxonomyPipelineOutput (fallback)"""
        
        if not taxonomy_output.retrieval_result:
            return HybridSearchResults(
                results=[],
                bm25_count=0,
                embedding_count=0,
                final_count=0,
                fusion_method="taxonomy"
            )
        
        retrieval = taxonomy_output.retrieval_result
        results = []
        
        for candidate in retrieval.candidates[:10]:
            result = SearchResult(
                id=candidate.taxon_id,
                name=candidate.name,
                domain=candidate.metadata.get('domain', ''),
                type="taxon",
                score=candidate.final_score,
                method="taxonomy_rrf",
                content={
                    'definition': candidate.definition,
                    'breadcrumb': candidate.breadcrumb,
                    'depth': candidate.depth
                },
                metadata=candidate.metadata
            )
            results.append(result)
        
        return HybridSearchResults(
            results=results,
            bm25_count=retrieval.bm25_count,
            embedding_count=retrieval.dense_count,
            final_count=len(results),
            fusion_method="taxonomy_rrf"
        )
    
    def close(self):
        """Ferme proprement les ressources"""
        logger.info("🔒 Closing pipeline...")
        
        try:
            if self.oss_client:
                self.oss_client.close()
            if self.dgraph and hasattr(self.dgraph, 'close'):
                self.dgraph.close()
            logger.info("✅ Closed successfully")
        except Exception as e:
            logger.warning(f"⚠️ Close warning: {e}")


def create_pipeline(
    project_name: str = None,
    dgraph_url: str = "localhost:9080",
    enable_taxonomy_validation: bool = True
) -> ContextWeaverPipeline:
    """Factory function pour créer un pipeline"""
    return ContextWeaverPipeline(
        project_name=project_name,
        dgraph_url=dgraph_url,
        enable_taxonomy_validation=enable_taxonomy_validation
    )