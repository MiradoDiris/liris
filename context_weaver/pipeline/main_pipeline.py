#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pipeline Context Weaver - Version CORRIGÉE
✅ Utilise le PROMPT COMPLET (pas de patterns restrictifs)
✅ SmartQueryExtractor amélioré
✅ Logging détaillé pour debug
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import re

from context_weaver.models.schemas import (
    PipelineOutput,
    SearchResult,
    HybridSearchResults,
    OSSClassification,
    NormalizedVariables
)

from context_weaver.taxonomy.taxonomy_models import (
    TaxonCandidate
)
from context_weaver.pipeline.taxonomy_pipeline import (
    TaxonomyPipeline,
    TaxonomyPipelineOutput
)
from context_weaver.taxonomy.taxonomy_retriever import RetrievalConfig

from context_weaver.services.oss_classifier import OSSClassifierClient
from context_weaver.data.vector_store_chroma import VectorStore

logger = logging.getLogger(__name__)


class SmartQueryExtractorV2:
    """
    ✅ CORRIGÉ: Extrait les paramètres SANS limiter la query
    
    Principe:
    - Utilise le PROMPT COMPLET comme query principale
    - Extrait des paramètres uniquement pour contexte additionnel
    """
    
    # Patterns pour contexte additionnel (optionnel)
    CONTEXT_PATTERNS = {
        'formes_juridiques': r'\b(SARL|SAS|SASU|EURL|SCI|SA|EI|EIRL|Micro[- ]entreprise|Auto[- ]entrepreneur|Association|Société|Entreprise Individuelle)\b',
        'regimes_fiscaux': r'\b(Impôt sur les sociétés?|IS|Impôt sur le revenu|IR|BIC|BNC|BA|Bénéfices? Industriels? et Commerciaux|Bénéfices? Non Commerciaux|Bénéfices? Agricoles?|Micro[- ]fiscal|Réel simplifié|Réel normal)\b',
        'domaines_activite': r'\b(Commerce|Prestataire de services?|Prestation de services?|Artisan|Commerçant|Profession libérale|Activité agricole|Commerce de détail|Commerce de gros|Location|Restaurant|Laverie|Centre équestre|Biens d\'occasion|Secrétariat|Assistance administrative)\b',
        'plans': r'\b(Plan standard|Plan simplifié|Plan spécifique|Plan comptable)\b',
        'comptabilite': r'\b(Comptabilité de trésorerie|Créances?|Dettes?|Comptabilité d\'engagement|Comptabilité simplifiée|Comptabilité complète)\b',
        'tva': r'\b(TVA|TVA sur marge|Franchise TVA)\b',
        'exercice': r'\b(Exercice comptable|Date d\'exercice|1er janvier|31 décembre|Clôture|Exercice décalé|janvier\s*[-–]\s*décembre)\b',
        'contexte': r'\b(Onboarding|Facturation|Déclaration|TPE|Association|Entrepreneur|Multi[- ]utilisateurs)\b'
    }
    
    def extract_context_params(self, prompt: str) -> Dict[str, List[str]]:
        """
        Extrait des paramètres contextuels (OPTIONNEL)
        """
        extracted = {}
        
        for category, pattern in self.CONTEXT_PATTERNS.items():
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            unique_matches = list(set(m.strip() for m in matches if m.strip()))
            if unique_matches:
                extracted[category] = unique_matches
        
        return extracted
    
    def build_enhanced_query(
        self, 
        prompt: str,
        strategy: str = "full_prompt"
    ) -> tuple[str, Dict[str, List[str]]]:
        """
        ✅ NOUVELLE APPROCHE: Garde le prompt COMPLET
        
        Args:
            prompt: Prompt utilisateur
            strategy: 
                - "full_prompt" (défaut): Garde le prompt complet
                - "with_boost": Ajoute les mots-clés comme boost
        
        Returns:
            (enhanced_query, extracted_params)
        """
        # Extraire les paramètres contextuels
        context_params = self.extract_context_params(prompt)
        
        if strategy == "full_prompt":
            # ✅ STRATÉGIE 1: Prompt complet tel quel
            enhanced_query = prompt
            
            # Limiter si trop long
            if len(enhanced_query) > 800:
                enhanced_query = enhanced_query[:800]
        
        elif strategy == "with_boost":
            # ✅ STRATÉGIE 2: Prompt + boost avec mots-clés
            query_parts = [prompt]
            
            # Ajouter les paramètres extraits comme contexte
            if context_params:
                for category, values in context_params.items():
                    category_label = category.replace('_', ' ').title()
                    values_text = ', '.join(values[:3])
                    query_parts.append(f"{category_label}: {values_text}")
            
            enhanced_query = '. '.join(query_parts)
            
            # Limiter si trop long
            if len(enhanced_query) > 1000:
                enhanced_query = enhanced_query[:1000]
        
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        return enhanced_query, context_params


class ContextWeaverPipeline:
    """
    Pipeline générique CORRIGÉ
    ✅ Utilise le prompt complet pour le matching
    """
    
    def __init__(
        self,
        dgraph_connector=None,
        vector_store=None,
        oss_client=None,
        project_name: str = None,
        dgraph_url: str = "localhost:9080",
        auto_init: bool = True,
        use_domain_filter: bool = True,
        default_domain: str = "Macompta.fr",
        query_strategy: str = "full_prompt"
    ):
        logger.info("=" * 80)
        logger.info("🗂️ CONTEXT WEAVER PIPELINE - INITIALIZATION (Fixed Version)")
        logger.info("=" * 80)

        self.use_domain_filter = use_domain_filter
        self.default_domain = default_domain
        self.query_strategy = query_strategy

        step_start = time.time()

        # === COMPOSANTS DE BASE ===
        logger.info("\n📦 Step 1/3: Initializing Core Components")

        # ✅ VÉRIFIER SI TOUS LES COMPOSANTS SONT FOURNIS
        all_provided = (
            vector_store is not None and 
            oss_client is not None
        )

        if all_provided:
            # ✅ UTILISER LES COMPOSANTS PRÉ-INITIALISÉS
            logger.info("   ✅ Using pre-initialized components:")
            logger.info(f"      • VectorStore: {vector_store.get_document_count() if vector_store else 0} docs")
            logger.info(f"      • OSS Client: {'✅' if oss_client else '❌'}")
            logger.info(f"      • Dgraph: {'✅' if dgraph_connector else '❌'}")

            self.vector_store = vector_store
            self.oss_client = oss_client
            self.dgraph = dgraph_connector
            self.project_name = project_name or "default_project"

        elif auto_init:
            # ✅ AUTO-INITIALISATION SI NÉCESSAIRE
            logger.info("   🔄 Auto-initializing missing components...")
            self._auto_init(dgraph_url, project_name)

        else:
            # ✅ UTILISER CE QUI EST FOURNI
            self.dgraph = dgraph_connector
            self.vector_store = vector_store
            self.oss_client = oss_client
            self.project_name = project_name or "default_project"

        logger.info(f"   ✅ Core components initialized in {(time.time() - step_start)*1000:.2f}ms")

        # === EMBEDDER ===
        step_start = time.time()
        logger.info("\n🔧 Step 2/3: Initializing Embedder")
        from context_weaver.services.embedder_wrapper import EmbedderWrapper
        self.embedder = EmbedderWrapper(oss_client=self.oss_client)
        logger.info(f"   ✅ Embedder initialized in {(time.time() - step_start)*1000:.2f}ms")

        # === TAXONOMY PIPELINE ===
        step_start = time.time()
        logger.info("\n📚 Step 3/3: Initializing Taxonomy Pipeline")

        retrieval_config = RetrievalConfig(
            dense_top_k=150,
            bm25_top_k=30,
            union_score_strategy="max",  # ✅ CHANGÉ: rrf_k → union_score_strategy
            final_top_n=30,
            boost_by_depth=True,
            enable_bm25_exact_boost=False
        )

        self.taxonomy_pipeline = TaxonomyPipeline(
            vector_store=self.vector_store,
            embedder=self.embedder,
            dgraph_connector=self.dgraph,
            retrieval_config=retrieval_config
        )

        logger.info(f"   ✅ Taxonomy pipeline initialized in {(time.time() - step_start)*1000:.2f}ms")

        logger.info("\n✅ Pipeline Ready")
        logger.info(f"   • Query strategy: {query_strategy}")
        logger.info(f"   • Domain filter: {'ENABLED' if use_domain_filter else 'DISABLED'}")
        if use_domain_filter:
            logger.info(f"   • Default domain: {default_domain}")
        logger.info("=" * 80 + "\n")
    
    
    def run(
        self,
        user_context: str,
        conversation_id: str = "default",
        session_state: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
        top_k: int = 10
    ) -> PipelineOutput:
        """
        ✅ Pipeline CORRIGÉ
        
        Utilise le PROMPT COMPLET pour le matching
        """
        pipeline_start = time.time()
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 CONTEXT WEAVER PIPELINE - EXECUTION (Fixed Version)")
        logger.info("=" * 80)
        logger.info(f"🔍 Query: {user_context[:100]}{'...' if len(user_context) > 100 else ''}")
        logger.info(f"📊 Query length: {len(user_context)} chars")
        
        try:
            # ================================================================
            # EXTRACTION INTELLIGENTE (OPTIONNELLE)
            # ================================================================
            logger.info("\n" + "─" * 80)
            logger.info("🔍 SMART PARAMETER EXTRACTION")
            logger.info("─" * 80)
            
            extractor = SmartQueryExtractorV2()
            enhanced_query, extracted_params = extractor.build_enhanced_query(
                prompt=user_context,
                strategy=self.query_strategy
            )
            
            # ✅ LOG DÉTAILLÉ pour debug
            logger.info(f"📋 Stratégie utilisée: {self.query_strategy}")
            
            if extracted_params:
                logger.info(f"✅ Paramètres contextuels extraits:")
                for category, values in extracted_params.items():
                    logger.info(f"   • {category}: {', '.join(values[:3])}")
            else:
                logger.info("ℹ️  Aucun paramètre contextuel trouvé (normal si query libre)")
            
            logger.info(f"\n🎯 Query pour embedding:")
            logger.info(f"   Original: {user_context[:100]}...")
            logger.info(f"   Enhanced: {enhanced_query[:100]}...")
            logger.info(f"   • Longueur originale: {len(user_context)} chars")
            logger.info(f"   • Longueur enhanced: {len(enhanced_query)} chars")
            
            # ✅ VÉRIFICATION CRITIQUE
            if not enhanced_query or len(enhanced_query.strip()) < 3:
                logger.error("❌ ERREUR: Query enrichie est VIDE ou trop courte!")
                logger.error(f"   Original: '{user_context}'")
                logger.error(f"   Enhanced: '{enhanced_query}'")
                logger.error("   → Utilisation du prompt original comme fallback")
                enhanced_query = user_context
            
            # ================================================================
            # RECHERCHE AVEC QUERY ENRICHIE
            # ================================================================
            logger.info("\n" + "─" * 80)
            logger.info("🎯 TAXONOMY SEARCH")
            logger.info("─" * 80)
            
            # Préparer le contexte
            context = {
                'task': 'smart_search',
                'query': user_context,
                'extracted_params': extracted_params,
                'domain': domain if domain else self.default_domain
            }
            
            logger.info(f"🔒 Domain filter: {context['domain']}")
            # Décider du filtre domain
            if domain:
                context['domain'] = domain
                logger.info(f"🔒 Domain filter: ENABLED (explicit: '{domain}')")
            elif self.use_domain_filter:
                context['domain'] = self.default_domain
                logger.info(f"🔒 Domain filter: ENABLED (default: '{self.default_domain}')")
            else:
                logger.info(f"🔓 Domain filter: DISABLED")
            
            # ================================================================
            # EXÉCUTION DU TAXONOMY PIPELINE
            # ================================================================
            step_start = time.time()
            logger.info("\n🚀 Executing taxonomy search...")
            
            taxonomy_output = self.taxonomy_pipeline.process(
                query=enhanced_query,  # ✅ Query enrichie (ou prompt complet)
                top_k=top_k,
                context=context
            )
            
            step_time = (time.time() - step_start) * 1000
            logger.info(f"✅ Search completed in {step_time:.2f}ms")
            
            # ================================================================
            # BUILD RESULTS
            # ================================================================
            search_results = self._build_search_results_from_taxonomy(taxonomy_output)
            
            # ================================================================
            # ANALYSE DE PERTINENCE (debug)
            # ================================================================
            self._analyze_result_relevance(taxonomy_output, enhanced_query)
            
            # ================================================================
            # BUILD OUTPUT
            # ================================================================
            total_time = (time.time() - pipeline_start) * 1000
            
            minimal_classification = OSSClassification(
                domain=context.get('domain', 'Unknown'),
                task='smart_search',
                decision_type='smart_extraction_v2',
                variables=list(extracted_params.keys()),
                confidence=1.0
            )
            
            minimal_normalized = NormalizedVariables(
                variables={},
                domain_taxonomy=[]
            )
            
            output = PipelineOutput(
                classification=minimal_classification,
                normalized=minimal_normalized,
                search_results=search_results,
                execution_time_ms=total_time,
                context_weaver=None,
                metadata={
                    'method': 'smart_search_v2',
                    'query_strategy': self.query_strategy,
                    'filter_applied': 'domain' in context,
                    'filtered_domain': context.get('domain'),
                    'original_query': user_context,
                    'enhanced_query': enhanced_query,
                    'query_length_original': len(user_context),
                    'query_length_enhanced': len(enhanced_query),
                    'extracted_params': extracted_params,
                    'params_count': sum(len(v) for v in extracted_params.values()) if extracted_params else 0,
                    'taxonomy_output': {
                        'total_candidates': taxonomy_output.total_candidates,
                        'top_candidate': {
                            'taxon_id': taxonomy_output.top_candidate.taxon_id,
                            'name': taxonomy_output.top_candidate.name,
                            'final_score': taxonomy_output.top_candidate.final_score,
                            'breadcrumb': taxonomy_output.top_candidate.breadcrumb
                        } if taxonomy_output.top_candidate else None,
                        'retrieval_time_ms': taxonomy_output.retrieval_time_ms,
                        'reranking_time_ms': taxonomy_output.reranking_time_ms,
                        'total_time_ms': taxonomy_output.total_time_ms
                    }
                }
            )
            
            self._log_final_summary(output, total_time)
            
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
    
    
    def _analyze_result_relevance(
        self, 
        taxonomy_output: TaxonomyPipelineOutput,
        enhanced_query: str
    ):
        """
        ✅ AMÉLIORÉ: Analyse avec plus de détails
        """
        if not taxonomy_output.top_candidate:
            logger.warning("⚠️  No results found")
            return
        
        top_score = taxonomy_output.top_candidate.final_score
        top_name = taxonomy_output.top_candidate.name
        
        # Seuils adaptés à RRF
        HIGH_CONFIDENCE = 0.20
        MEDIUM_CONFIDENCE = 0.15
        LOW_CONFIDENCE = 0.10
        
        logger.info(f"\n📊 RELEVANCE ANALYSIS:")
        logger.info(f"   Query: '{enhanced_query[:60]}...'")
        logger.info(f"   Top result: '{top_name}' (score: {top_score:.3f})")
        
        if top_score >= HIGH_CONFIDENCE:
            logger.info(f"   ✅ HIGH confidence - Excellent match!")
        elif top_score >= MEDIUM_CONFIDENCE:
            logger.info(f"   ✅ MEDIUM confidence - Good match")
        elif top_score >= LOW_CONFIDENCE:
            logger.warning(f"   ⚠️  LOW confidence - Partial match")
        else:
            logger.error(f"   ❌ VERY LOW confidence - Poor match")
        
        # Top 5 pour comparaison
        if len(taxonomy_output.all_candidates) > 1:
            logger.info(f"\n   Top 5 scores:")
            for i, c in enumerate(taxonomy_output.all_candidates[:5], 1):
                logger.info(f"      {i}. {c.name}: {c.final_score:.3f}")
    
    
    def _build_search_results_from_taxonomy(
        self,
        taxonomy_output: TaxonomyPipelineOutput
    ) -> HybridSearchResults:
        """Construit HybridSearchResults depuis TaxonomyPipelineOutput"""
        
        if not taxonomy_output.all_candidates:
            return HybridSearchResults(
                results=[],
                bm25_count=0,
                embedding_count=0,
                final_count=0,
                fusion_method="direct_rrf_reranked"
            )
        
        results = []
        
        for candidate in taxonomy_output.all_candidates:
            result = SearchResult(
                id=candidate.taxon_id,
                name=candidate.name,
                domain=candidate.metadata.get('domain', ''),
                type="taxon",
                score=candidate.final_score,
                method="direct_rrf_reranked",
                content={
                    'definition': candidate.definition,
                    'breadcrumb': candidate.breadcrumb,
                    'depth': candidate.depth
                },
                metadata=candidate.metadata
            )
            results.append(result)
        
        retrieval_stats = taxonomy_output.retrieval_stats
        
        return HybridSearchResults(
            results=results,
            bm25_count=retrieval_stats.get('bm25_count', 0),
            embedding_count=retrieval_stats.get('dense_count', 0),
            final_count=len(results),
            fusion_method="direct_rrf_reranked"
        )
    
    
    def _log_final_summary(self, output: PipelineOutput, total_time: float):
        """Log le résumé final"""
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 PIPELINE EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"⏱️  Total execution time: {total_time:.2f}ms")
        logger.info(f"🔍 Search method: Smart Extraction V2")
        logger.info(f"🎯 Query strategy: {output.metadata.get('query_strategy', 'unknown')}")
        logger.info(f"📊 Results: {output.search_results.final_count} items")
        
        # Info sur les paramètres extraits
        params_count = output.metadata.get('params_count', 0)
        if params_count > 0:
            logger.info(f"🎯 Paramètres extraits: {params_count}")
            extracted = output.metadata.get('extracted_params', {})
            if extracted:
                logger.info(f"   • Catégories: {', '.join(extracted.keys())}")
        
        filter_applied = output.metadata.get('filter_applied', False)
        if filter_applied:
            filtered_domain = output.metadata.get('filtered_domain')
            logger.info(f"🔒 Domain filter: {filtered_domain}")
        else:
            logger.info(f"🔓 Domain filter: DISABLED")
        
        # Log top 5
        if output.search_results.results:
            logger.info("\n🏆 Top 5 results:")
            for i, result in enumerate(output.search_results.results[:5], 1):
                logger.info(f"   {i}. {result.name}")
                logger.info(f"      • Score: {result.score:.4f}")
                logger.info(f"      • Domain: {result.domain}")
                
                if result.content.get('breadcrumb'):
                    breadcrumb = result.content['breadcrumb']
                    levels = breadcrumb.split(' > ')
                    if len(levels) > 3:
                        short = ' > '.join(levels[-3:])
                        logger.info(f"      • Path: ...{short}")
        
        logger.info("\n💡 Tip:")
        logger.info("   Focus on relative ranking, not absolute scores!")
        logger.info("=" * 80 + "\n")
    
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _needs_init(self, dgraph, oss) -> bool:
        return dgraph is None or oss is None
    
    def _auto_init(self, dgraph_url: str, project_name: Optional[str]):
        """Auto-initialise les composants manquants"""
        logger.info("   🔄 Auto-initializing components...")

        try:
            # ✅ OSS CLIENT (seulement si pas déjà fourni)
            if not self.oss_client:
                logger.debug("   • Creating OSS client...")
                self.oss_client = OSSClassifierClient()
            else:
                logger.debug("   • Using provided OSS client")

            # ✅ DGRAPH (seulement si pas déjà fourni)
            if not self.dgraph:
                try:
                    logger.debug("   • Connecting to Dgraph...")
                    from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
                    self.dgraph = TaxonomyDgraphConnector()
                    logger.debug("   ✓ Dgraph connected")
                except Exception as e:
                    logger.warning(f"   ⚠️ Dgraph unavailable: {e}")
                    self.dgraph = None
            else:
                logger.debug("   • Using provided Dgraph connector")

            # ✅ VECTOR STORE (seulement si pas déjà fourni)
            if not self.vector_store:
                logger.debug("   • Initializing vector store...")
                self.vector_store = VectorStore()
                self.vector_store.initialize()
                logger.debug("   ✓ VectorStore initialized")
            else:
                logger.debug("   • Using provided VectorStore")

            self.project_name = project_name or "default_project"

        except Exception as e:
            logger.error(f"   ❌ Auto-init error: {e}")
            raise
    
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


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_pipeline(
    project_name: str = None,
    dgraph_url: str = "localhost:9080",
    vector_store=None,  # ✅ AJOUT DU PARAMÈTRE
    oss_client=None,    # ✅ AJOUT DU PARAMÈTRE
    dgraph_connector=None,  # ✅ AJOUT DU PARAMÈTRE
    use_domain_filter: bool = True,
    default_domain: str = "Macompta.fr",
    query_strategy: str = "full_prompt"
) -> ContextWeaverPipeline:
    """
    Factory pour créer un pipeline corrigé
    
    Args:
        project_name: Nom du projet
        dgraph_url: URL Dgraph
        vector_store: VectorStore pré-initialisé (optionnel)
        oss_client: Client OSS pré-initialisé (optionnel)
        dgraph_connector: Connecteur Dgraph pré-initialisé (optionnel)
        use_domain_filter: Activer le filtre domain
        default_domain: Domain par défaut
        query_strategy: Stratégie de query
            - "full_prompt": Garde le prompt complet (défaut)
            - "with_boost": Ajoute les mots-clés comme boost
    """
    return ContextWeaverPipeline(
        project_name=project_name,
        dgraph_url=dgraph_url,
        dgraph_connector=dgraph_connector,  # ✅ PASSER AU PIPELINE
        vector_store=vector_store,          # ✅ PASSER AU PIPELINE
        oss_client=oss_client,              # ✅ PASSER AU PIPELINE
        auto_init=(vector_store is None),   # ✅ AUTO-INIT SEULEMENT SI PAS FOURNI
        use_domain_filter=use_domain_filter,
        default_domain=default_domain,
        query_strategy=query_strategy
    )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "=" * 80)
    print("EXEMPLE: Pipeline CORRIGÉ")
    print("=" * 80)
    print("""
✅ CORRECTIONS APPLIQUÉES:
1. Utilise le prompt COMPLET (pas de patterns restrictifs)
2. Extraction de paramètres optionnelle (pour contexte seulement)
3. Logging détaillé pour debug
4. Vérification que la query n'est jamais vide

# UTILISATION:

from context_weaver.pipeline.main_pipeline import create_pipeline

# Option 1: Prompt complet (recommandé)
pipeline = create_pipeline(
    query_strategy="full_prompt",  # Défaut
    use_domain_filter=True
)

# Option 2: Avec boost contextuel
pipeline = create_pipeline(
    query_strategy="with_boost",
    use_domain_filter=True
)

# Test
result = pipeline.run(
    user_context="Comment configurer mon plan comptable pour une petite entreprise ?",
    top_k=10
)

# Voir les résultats
for i, taxon in enumerate(result.search_results.results[:5], 1):
    print(f"{i}. {taxon.name} (score: {taxon.score:.3f})")

pipeline.close()
""")