#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaxonomyPipeline - ULTRA-SIMPLIFIÉ
✅ Pipeline à 2 étapes: RRF → Reranking
❌ SUPPRIMÉ: Validation, Projection, PrereqSnapshot
"""

import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from context_weaver.taxonomy.taxonomy_models import TaxonCandidate
from context_weaver.taxonomy.taxonomy_retriever import (
    TaxonomyRetriever, 
    RetrievalResult, 
    RetrievalConfig
)
from context_weaver.reranker.taxonomy_reranker import (
    TaxonomyReranker,
    RerankingConfig,
    RerankingResult
)
from context_weaver.reranker.contextual_reranker import (
    ContextualReranker,
    ContextualBoostConfig
)

logger = logging.getLogger(__name__)


# ============================================================================
# OUTPUT MODEL
# ============================================================================

@dataclass
class TaxonomyPipelineOutput:
    """Résultat simplifié du pipeline"""
    
    # Résultat principal
    top_candidate: Optional[TaxonCandidate] = None
    all_candidates: List[TaxonCandidate] = field(default_factory=list)
    
    # Statistiques
    total_candidates: int = 0
    retrieval_time_ms: float = 0.0
    reranking_time_ms: float = 0.0
    total_time_ms: float = 0.0
    
    # Détails retrieval
    retrieval_stats: Dict[str, Any] = field(default_factory=dict)
    
    # Détails reranking
    reranking_stats: Dict[str, Any] = field(default_factory=dict)
    significant_rank_changes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export en dict pour JSON"""
        return {
            'top_candidate': {
                'taxon_id': self.top_candidate.taxon_id,
                'name': self.top_candidate.name,
                'final_score': self.top_candidate.final_score,
                'breadcrumb': self.top_candidate.breadcrumb,
                'depth': self.top_candidate.depth,
                'metadata': self.top_candidate.metadata
            } if self.top_candidate else None,
            
            'candidates_count': len(self.all_candidates),
            'total_candidates': self.total_candidates,
            
            'timing': {
                'retrieval_ms': self.retrieval_time_ms,
                'reranking_ms': self.reranking_time_ms,
                'total_ms': self.total_time_ms
            },
            
            'retrieval_stats': self.retrieval_stats,
            'reranking_stats': self.reranking_stats,
            'significant_changes': self.significant_rank_changes
        }


# ============================================================================
# SIMPLIFIED PIPELINE
# ============================================================================

class TaxonomyPipeline:
    """
    ✅ Pipeline ultra-simplifié à 2 étapes
    
    Workflow:
    1. RRF Retrieval → candidats avec metadata minimale
    2. Reranking → enrichissement Dgraph + final_score
    
    ❌ Plus de:
    - Validation
    - Projection
    - PrereqSnapshot
    """
    
    def __init__(
        self,
        vector_store,
        embedder,
        dgraph_connector,
        retrieval_config: Optional[RetrievalConfig] = None,
        reranking_config: Optional[RerankingConfig] = None,
        use_contextual_reranker: bool = True
    ):
        """
        Args:
            vector_store: Vector store pour retrieval
            embedder: Embedder pour dense retrieval
            dgraph_connector: Connector Dgraph pour enrichissement
            retrieval_config: Config retrieval (optionnel)
            reranking_config: Config reranking (optionnel)
        """
        
        logger.info("=" * 80)
        logger.info("🚀 TAXONOMY PIPELINE - SIMPLIFIED ARCHITECTURE")
        logger.info("=" * 80)
        
        # 1. Retriever (RRF)
        logger.info("📊 Initializing Retriever (RRF matching)")
        self.retriever = TaxonomyRetriever(
            vector_store=vector_store,
            embedder=embedder,
            config=retrieval_config or RetrievalConfig()
        )
        logger.info("   ✅ Retriever ready")
        
        # 2. Reranker (Dgraph enrichment + scoring)
        logger.info("\n🔄 Initializing Reranker (Dgraph enrichment)")
        self.reranker = TaxonomyReranker(
            dgraph_connector=dgraph_connector,
            config=reranking_config or RerankingConfig()
        )
        if use_contextual_reranker:
            boost_config = ContextualBoostConfig(
                forme_juridique_boost=10.0,
                regime_fiscal_boost=8.0,
                domaine_activite_boost=5.0,
                plan_comptable_boost=3.0,
                incompatibility_penalty=0.1
            )
            self.contextual_reranker = ContextualReranker(config=boost_config)
            logger.info("✅ Contextual Reranker activé")
        else:   
            self.contextual_reranker = None
        logger.info("   ✅ Reranker ready")
        
        logger.info("\n✅ Pipeline initialized")
        logger.info("   Architecture: RRF → Reranking")
        logger.info("=" * 80 + "\n")
    
    
    def process(
        self,
        query: str,
        top_k: int = 10,
        context: Optional[Dict[str, Any]] = None
    ) -> TaxonomyPipelineOutput:
        """
        Traite une requête avec le pipeline simplifié
        
        Args:
            query: Requête utilisateur
            top_k: Nombre de candidats à retourner
            context: Contexte utilisateur (optionnel)
            
        Returns:
            TaxonomyPipelineOutput avec candidats enrichis
        """
        
        start_time = time.time()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 TAXONOMY PIPELINE - EXECUTION")
        logger.info("=" * 80)
        logger.info(f"📝 Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        logger.info(f"🎯 Top-K: {top_k}")
        
        if context:
            logger.info(f"🔧 Context: {list(context.keys())}")
        
        try:
            # ══════════════════════════════════════════════════════════════
            # STEP 1: RRF RETRIEVAL
            # ══════════════════════════════════════════════════════════════
            logger.info("\n" + "─" * 80)
            logger.info("📊 STEP 1/2: RRF Retrieval")
            logger.info("─" * 80)
            
            retrieval_start = time.time()
            
            retrieval_result = self.retriever.retrieve(
                query_text=query,
                context=context
            )
            
            retrieval_time = (time.time() - retrieval_start) * 1000
            
            if not retrieval_result.candidates:
                logger.warning("⚠️ No candidates found")
                return self._empty_output(retrieval_time, 0.0, start_time)
            
            logger.info(f"✅ Retrieval completed in {retrieval_time:.2f}ms")
            logger.info(f"   • Total candidates: {len(retrieval_result.candidates)}")
            logger.info(f"   • Dense: {retrieval_result.dense_count}")
            logger.info(f"   • BM25: {retrieval_result.bm25_count}")
            logger.info(f"   • Top Union score: {retrieval_result.top_union_score:.4f}")
            
            # Top 3 avant reranking
            logger.info(f"\n🏆 Top 3 (before reranking):")
            for i, c in enumerate(retrieval_result.candidates[:3], 1):
                logger.info(f"   {i}. {c.name} (Union: {c.final_score:.4f})")
            
            # ══════════════════════════════════════════════════════════════
            # STEP 2: RERANKING (Enrichissement + Scoring)
            # ══════════════════════════════════════════════════════════════
            logger.info("\n" + "─" * 80)
            logger.info("🔄 STEP 2/2: Reranking (Dgraph Enrichment)")
            logger.info("─" * 80)
            
            reranking_start = time.time()
            
            # Reranking (sans validation - juste enrichissement + scoring)
            enriched_candidates, reranking_details = self.reranker.rerank(
                candidates=retrieval_result.candidates
            )
            
            reranking_time = (time.time() - reranking_start) * 1000
            
            logger.info(f"✅ Reranking completed in {reranking_time:.2f}ms")
            logger.info(f"   • Candidates enriched: {len(enriched_candidates)}")
                
            # Calculer changements significatifs
            significant_changes = self._compute_significant_changes(reranking_details)
            
            if significant_changes:
                logger.info(f"   • Significant rank changes: {len(significant_changes)}")
            
            # Top 3 après reranking
            logger.info(f"\n🎯 Top 3 (after reranking):")
            for i, c in enumerate(enriched_candidates[:3], 1):
                logger.info(f"   {i}. {c.name} (Final: {c.final_score:.4f})")
                
                # Vérifier enrichissement
                if 'prereq_hard_ids' in c.metadata:
                    prereq_count = len(c.metadata['prereq_hard_ids'])
                    logger.info(f"      ✅ {prereq_count} prereqs hard")
                
                if c.metadata.get('description'):
                    desc = c.metadata['description'][:50] + "..."
                    logger.info(f"      ✅ Description: {desc}")
            
            # ══════════════════════════════════════════════════════════════
            # BUILD OUTPUT
            # ══════════════════════════════════════════════════════════════
            total_time = (time.time() - start_time) * 1000
            
            output = TaxonomyPipelineOutput(
                top_candidate=enriched_candidates[0] if enriched_candidates else None,
                all_candidates=enriched_candidates[:top_k],
                total_candidates=len(enriched_candidates),
                retrieval_time_ms=retrieval_time,
                reranking_time_ms=reranking_time,
                total_time_ms=total_time,
                retrieval_stats={
                    'dense_count': retrieval_result.dense_count,
                    'bm25_count': retrieval_result.bm25_count,
                    'top_union_score': retrieval_result.top_union_score,
                    'union_min_score': retrieval_result.union_min_score,
                    'union_max_score': retrieval_result.union_max_score
                },
                reranking_stats={
                    'candidates_enriched': len(enriched_candidates),
                    'significant_changes': len(significant_changes),
                    'top_final_score': enriched_candidates[0].final_score if enriched_candidates else 0.0
                },
                significant_rank_changes=significant_changes
            )
            
            self._log_summary(output)
            
            return output
        
        except Exception as e:
            logger.error(f"\n❌ PIPELINE ERROR: {e}")
            logger.exception("Stack trace:")
            raise
    
    
    def _compute_significant_changes(
        self,
        reranking_details: List[RerankingResult]
    ) -> List[Dict[str, Any]]:
        """Calcule les changements de rang significatifs (≥3 positions)"""
        
        changes = []
        
        for detail in reranking_details:
            rank_change = abs(detail.new_rank - detail.original_rank)
            
            if rank_change >= 3:
                changes.append({
                    'taxon_id': detail.taxon_id,
                    'original_rank': detail.original_rank,
                    'new_rank': detail.new_rank,
                    'rank_change': detail.new_rank - detail.original_rank,
                    'score_adjustment': detail.total_adjustment,
                    'original_final_score': detail.original_rrf_score,  # Score avant reranking
                    'final_score': detail.final_score
                })
        
        # Trier par amplitude du changement
        changes.sort(key=lambda x: abs(x['rank_change']), reverse=True)
        
        return changes
    
    
    def _empty_output(
        self,
        retrieval_time: float,
        reranking_time: float,
        start_time: float
    ) -> TaxonomyPipelineOutput:
        """Crée un output vide"""
        
        total_time = (time.time() - start_time) * 1000
        
        return TaxonomyPipelineOutput(
            top_candidate=None,
            all_candidates=[],
            total_candidates=0,
            retrieval_time_ms=retrieval_time,
            reranking_time_ms=reranking_time,
            total_time_ms=total_time,
            retrieval_stats={},
            reranking_stats={}
        )
    
    
    def _log_summary(self, output: TaxonomyPipelineOutput):
        """Log le résumé final"""
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 PIPELINE SUMMARY")
        logger.info("=" * 80)
        
        if output.top_candidate:
            logger.info(f"🏆 Top candidate: {output.top_candidate.name}")
            logger.info(f"   • Final score: {output.top_candidate.final_score:.4f}")
            logger.info(f"   • Taxon ID: {output.top_candidate.taxon_id}")
            logger.info(f"   • Breadcrumb: {output.top_candidate.breadcrumb}")
        else:
            logger.info("⚠️ No candidates found")
        
        logger.info(f"\n⏱️ Timing:")
        logger.info(f"   • Retrieval: {output.retrieval_time_ms:.2f}ms")
        logger.info(f"   • Reranking: {output.reranking_time_ms:.2f}ms")
        logger.info(f"   • Total: {output.total_time_ms:.2f}ms")
        
        logger.info(f"\n📊 Statistics:")
        logger.info(f"   • Total candidates: {output.total_candidates}")
        logger.info(f"   • Returned: {len(output.all_candidates)}")
        
        if output.significant_rank_changes:
            logger.info(f"   • Significant rank changes: {len(output.significant_rank_changes)}")
            
            for change in output.significant_rank_changes[:3]:
                direction = "⬆️" if change['rank_change'] < 0 else "⬇️"
                logger.info(
                    f"      {direction} Rank {change['original_rank']} → {change['new_rank']} "
                    f"(Δscore: {change['score_adjustment']:+.3f})"
                )
        
        logger.info("=" * 80 + "\n")


# ============================================================================
# FACTORY
# ============================================================================

def create_taxonomy_pipeline(
    vector_store,
    embedder,
    dgraph_connector,
    dense_top_k: int = 50,
    bm25_top_k: int = 100,
    union_score_strategy: str = "max",  # ✅ CHANGÉ: rrf_k → union_score_strategy
    final_top_n: int = 30
) -> TaxonomyPipeline:
    """
    Factory pour créer un pipeline simplifié
    
    Args:
        vector_store: Vector store
        embedder: Embedder
        dgraph_connector: Dgraph connector
        dense_top_k: Top-K pour dense retrieval
        bm25_top_k: Top-K pour BM25
        union_score_strategy: Stratégie de score union ("max", "sum", "dense", "bm25")
        final_top_n: Top-N final après union
        
    Returns:
        TaxonomyPipeline configuré
    """
    
    retrieval_config = RetrievalConfig(
        dense_top_k=dense_top_k,
        bm25_top_k=bm25_top_k,
        union_score_strategy=union_score_strategy,  # ✅ CHANGÉ: rrf_k → union_score_strategy
        final_top_n=final_top_n
    )
    
    reranking_config = RerankingConfig()
    
    return TaxonomyPipeline(
        vector_store=vector_store,
        embedder=embedder,
        dgraph_connector=dgraph_connector,
        retrieval_config=retrieval_config,
        reranking_config=reranking_config
    )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "=" * 80)
    print("EXEMPLE: Taxonomy Pipeline Simplifié")
    print("=" * 80)
    print("""
    # Exemple de code:
    
    from context_weaver.taxonomy.taxonomy_pipeline import create_taxonomy_pipeline
    
    # 1. Créer le pipeline
    pipeline = create_taxonomy_pipeline(
        vector_store=your_vector_store,
        embedder=your_embedder,
        dgraph_connector=your_dgraph_connector,
        dense_top_k=100,
        bm25_top_k=100,
        final_top_n=30
    )
    
    # 2. Traiter une requête
    result = pipeline.process(
        query="Je veux créer une facture de vente",
        top_k=5,
        context={'domain': 'Macompta.fr'}
    )
    
    # 3. Utiliser les résultats
    if result.top_candidate:
        print(f"Top: {result.top_candidate.name}")
        print(f"Score: {result.top_candidate.final_score:.3f}")
        
        # Metadata enrichie disponible
        prereqs = result.top_candidate.metadata.get('prereq_hard_ids', [])
        description = result.top_candidate.metadata.get('description', '')
        
        print(f"Prereqs: {len(prereqs)}")
        print(f"Description: {description[:100]}...")
    """)
    
    print("\n" + "=" * 80)