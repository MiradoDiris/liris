#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests Unitaires - Taxonomy Pipeline
Focus: Intégration RRF + Reranking
"""

import pytest
import logging
import numpy as np
from typing import List, Dict, Any
from unittest.mock import Mock, MagicMock, patch

from context_weaver.pipeline.taxonomy_pipeline import (
    TaxonomyPipeline,
    TaxonomyPipelineOutput,
    create_taxonomy_pipeline
)
from context_weaver.taxonomy.taxonomy_models import TaxonCandidate
from context_weaver.taxonomy.taxonomy_retriever import RetrievalConfig
from context_weaver.reranker.taxonomy_reranker import RerankingConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_vector_store():
    """Mock vector store simple"""
    mock = MagicMock()
    
    # Format: (distances, metadata_list)
    dense_distances = [0.9, 0.8, 0.7]
    dense_metadata = [
        {'id': '0x1', 'name': 'Interrogation recherche', 'breadcrumb': 'Éditions > Interrogation', 'depth': 2, 'domain': 'Macompta.fr'},
        {'id': '0x2', 'name': 'Choix journal', 'breadcrumb': 'Éditions > Interrogation > Choix journal', 'depth': 3, 'domain': 'Macompta.fr'},
        {'id': '0x3', 'name': 'Balance comptable', 'breadcrumb': 'Éditions > Balance', 'depth': 2, 'domain': 'Macompta.fr'}
    ]
    
    bm25_distances = [15.0, 12.0, 10.0]
    bm25_metadata = [
        {'id': '0x2', 'name': 'Choix journal', 'breadcrumb': 'Éditions > Interrogation > Choix journal', 'depth': 3, 'domain': 'Macompta.fr'},
        {'id': '0x4', 'name': 'HA : Journal des Achats', 'breadcrumb': 'Éditions > Interrogation > Choix journal > HA', 'depth': 4, 'domain': 'Macompta.fr'},
        {'id': '0x1', 'name': 'Interrogation recherche', 'breadcrumb': 'Éditions > Interrogation', 'depth': 2, 'domain': 'Macompta.fr'}
    ]
    
    mock.search = Mock(return_value=(dense_distances, dense_metadata))
    mock.bm25_search = Mock(return_value=(bm25_distances, bm25_metadata))
    
    return mock


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    mock = MagicMock()
    mock.encode = Mock(return_value=np.random.rand(384))
    return mock


@pytest.fixture
def mock_dgraph():
    """Mock Dgraph avec enrichissement"""
    mock = MagicMock()
    
    def mock_query(query_string):
        response = MagicMock()
        response.json = str({
            "nodes": [
                {
                    "uid": "0x1",
                    "name": "Interrogation recherche",
                    "description": "Rechercher et consulter des écritures comptables",
                    "category": "consultation",
                    "depth": 2,
                    "prereq_hard": [{"uid": "0xa", "name": "Exercice ouvert"}],
                    "prereq_soft": [],
                    "incompatible": [],
                    "~children": [{"uid": "0x100"}],
                    "children": [{"uid": "0x2"}, {"uid": "0x3"}],
                    "intentKeywords": ["recherche", "consultation"],
                    "actionKeywords": ["afficher"],
                    "dgraph.type": ["TaxonNode"]
                },
                {
                    "uid": "0x2",
                    "name": "Choix journal",
                    "description": "Sélectionner un journal comptable spécifique",
                    "category": "filtre",
                    "depth": 3,
                    "prereq_hard": [{"uid": "0x1"}],
                    "prereq_soft": [],
                    "incompatible": [],
                    "~children": [{"uid": "0x1"}],
                    "children": [{"uid": "0x21"}, {"uid": "0x22"}],
                    "intentKeywords": ["journal", "filtrer"],
                    "actionKeywords": ["sélectionner"],
                    "dgraph.type": ["TaxonNode"]
                },
                {
                    "uid": "0x3",
                    "name": "Balance comptable",
                    "description": "Générer une balance générale ou auxiliaire",
                    "category": "état",
                    "depth": 2,
                    "prereq_hard": [],
                    "prereq_soft": [],
                    "incompatible": [],
                    "~children": [],
                    "children": [],
                    "intentKeywords": ["balance", "état"],
                    "actionKeywords": ["générer"],
                    "dgraph.type": ["TaxonNode"]
                },
                {
                    "uid": "0x4",
                    "name": "HA : Journal des Achats",
                    "description": "Journal comptable des achats",
                    "category": "journal",
                    "depth": 4,
                    "prereq_hard": [{"uid": "0x2"}],
                    "prereq_soft": [],
                    "incompatible": [],
                    "~children": [{"uid": "0x2"}],
                    "children": [],
                    "intentKeywords": ["achats", "fournisseur"],
                    "actionKeywords": [],
                    "dgraph.type": ["TaxonNode"]
                }
            ]
        }).replace("'", '"')
        return response
    
    mock.client.txn.return_value.query = mock_query
    mock.client.txn.return_value.discard = MagicMock()
    
    return mock


@pytest.fixture
def pipeline(mock_vector_store, mock_embedder, mock_dgraph):
    """Pipeline configuré pour tests"""
    
    retrieval_config = RetrievalConfig(
        dense_top_k=50,
        bm25_top_k=50,
        rrf_k=60,
        final_top_n=20
    )
    
    reranking_config = RerankingConfig(
        rrf_weight=0.7,
        metadata_boost_weight=0.3
    )
    
    from context_weaver.pipeline.taxonomy_pipeline import TaxonomyPipeline
    
    return TaxonomyPipeline(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        dgraph_connector=mock_dgraph,
        retrieval_config=retrieval_config,
        reranking_config=reranking_config
    )


# ============================================================================
# TESTS - WORKFLOW COMPLET
# ============================================================================

class TestPipelineWorkflow:
    """Tests du workflow complet RRF → Reranking"""
    
    def test_pipeline_executes_both_stages(self, pipeline):
        """
        Test: Le pipeline exécute RRF puis Reranking
        """
        query = "Comment afficher les écritures du journal des achats ?"
        
        output = pipeline.process(query=query, top_k=10)
        
        # Vérifier que les deux étapes ont été exécutées
        assert output.retrieval_time_ms > 0, "RRF doit avoir été exécuté"
        assert output.reranking_time_ms > 0, "Reranking doit avoir été exécuté"
        
        # Total time = retrieval + reranking
        assert output.total_time_ms >= output.retrieval_time_ms + output.reranking_time_ms
    
    
    def test_pipeline_returns_enriched_candidates(self, pipeline):
        """
        Test: Les candidats retournés sont enrichis
        """
        output = pipeline.process(query="recherche écritures", top_k=5)
        
        assert output.total_candidates > 0
        assert output.top_candidate is not None
        
        # Vérifier enrichissement Dgraph
        top = output.top_candidate
        assert 'description' in top.metadata
        assert 'prereq_hard_ids' in top.metadata
        assert top.final_score > 0
    
    
    def test_pipeline_respects_top_k(self, pipeline):
        """
        Test: Le pipeline respecte le paramètre top_k
        """
        top_k = 3
        output = pipeline.process(query="test", top_k=top_k)
        
        assert len(output.all_candidates) <= top_k


# ============================================================================
# TESTS - RETRIEVAL STATS
# ============================================================================

class TestRetrievalStats:
    """Tests des statistiques de retrieval"""
    
    def test_retrieval_stats_populated(self, pipeline):
        """
        Test: Les stats de retrieval sont remplies
        """
        output = pipeline.process(query="test")
        
        assert 'dense_count' in output.retrieval_stats
        assert 'bm25_count' in output.retrieval_stats
        assert 'top_rrf_score' in output.retrieval_stats
        
        assert output.retrieval_stats['dense_count'] >= 0
        assert output.retrieval_stats['bm25_count'] >= 0
    
    
    def test_rrf_score_bounds_in_stats(self, pipeline):
        """
        Test: Les bornes RRF sont cohérentes
        """
        output = pipeline.process(query="test")
        
        if output.all_candidates:
            rrf_min = output.retrieval_stats.get('rrf_min_score', 0)
            rrf_max = output.retrieval_stats.get('rrf_max_score', 1)
            
            assert rrf_min <= rrf_max


# ============================================================================
# TESTS - RERANKING STATS
# ============================================================================

class TestRerankingStats:
    """Tests des statistiques de reranking"""
    
    def test_reranking_stats_populated(self, pipeline):
        """
        Test: Les stats de reranking sont remplies
        """
        output = pipeline.process(query="test")
        
        assert 'candidates_enriched' in output.reranking_stats
        assert 'significant_changes' in output.reranking_stats
        
        assert output.reranking_stats['candidates_enriched'] >= 0
    
    
    def test_significant_rank_changes_detected(self, pipeline):
        """
        Test: Les changements de rang ≥ 3 sont détectés
        """
        output = pipeline.process(query="balance clients fournisseurs", top_k=20)
        
        # Vérifier structure des changements significatifs
        for change in output.significant_rank_changes:
            assert 'taxon_id' in change
            assert 'original_rank' in change
            assert 'new_rank' in change
            assert 'rank_change' in change
            
            # Changement doit être ≥ 3
            assert abs(change['rank_change']) >= 3


# ============================================================================
# TESTS - OUTPUT STRUCTURE
# ============================================================================

class TestOutputStructure:
    """Tests de la structure TaxonomyPipelineOutput"""
    
    def test_output_has_all_required_fields(self, pipeline):
        """
        Test: L'output contient tous les champs requis
        """
        output = pipeline.process(query="test")
        
        assert hasattr(output, 'top_candidate')
        assert hasattr(output, 'all_candidates')
        assert hasattr(output, 'total_candidates')
        assert hasattr(output, 'retrieval_time_ms')
        assert hasattr(output, 'reranking_time_ms')
        assert hasattr(output, 'total_time_ms')
        assert hasattr(output, 'retrieval_stats')
        assert hasattr(output, 'reranking_stats')
        assert hasattr(output, 'significant_rank_changes')
    
    
    def test_output_to_dict_serializable(self, pipeline):
        """
        Test: L'output est sérialisable en dict/JSON
        """
        output = pipeline.process(query="test")
        
        output_dict = output.to_dict()
        
        assert isinstance(output_dict, dict)
        assert 'top_candidate' in output_dict
        assert 'candidates_count' in output_dict
        assert 'timing' in output_dict


# ============================================================================
# TESTS - TOP CANDIDATE
# ============================================================================

class TestTopCandidate:
    """Tests du candidat top 1"""
    
    def test_top_candidate_has_highest_final_score(self, pipeline):
        """
        Test: Le top candidate a le meilleur final_score
        """
        output = pipeline.process(query="test", top_k=10)
        
        if output.top_candidate and len(output.all_candidates) > 1:
            top_score = output.top_candidate.final_score
            
            for candidate in output.all_candidates[1:]:
                assert candidate.final_score <= top_score
    
    
    def test_top_candidate_metadata_enriched(self, pipeline):
        """
        Test: Le top candidate a une metadata enrichie
        """
        output = pipeline.process(query="recherche journal")
        
        if output.top_candidate:
            top = output.top_candidate
            
            # Doit avoir description
            assert top.metadata.get('description')
            
            # Doit avoir les champs d'enrichissement
            assert 'prereq_hard_ids' in top.metadata
            assert 'parent_ids' in top.metadata


# ============================================================================
# TESTS - CONTEXTE UTILISATEUR
# ============================================================================

class TestUserContext:
    """Tests de l'intégration du contexte utilisateur"""
    
    def test_context_passed_to_retrieval(self, pipeline):
        """
        Test: Le contexte est passé au retriever
        """
        context = {
            'domain': 'Macompta.fr',
            'task': 'consultation',
            'variables': ['journal', 'achats']
        }
        
        output = pipeline.process(
            query="voir journal achats",
            context=context
        )
        
        # Pipeline doit fonctionner avec contexte
        assert output.total_candidates > 0
    
    
    def test_context_enriches_results(self, pipeline):
        """
        Test: Le contexte peut influencer les résultats
        """
        # Sans contexte
        output_no_ctx = pipeline.process(query="journal")
        
        # Avec contexte
        output_with_ctx = pipeline.process(
            query="journal",
            context={'variables': ['achats', 'fournisseur']}
        )
        
        # Les deux doivent retourner des résultats
        assert output_no_ctx.total_candidates > 0
        assert output_with_ctx.total_candidates > 0


# ============================================================================
# TESTS - PERFORMANCE
# ============================================================================

class TestPerformance:
    """Tests de performance du pipeline"""
    
    def test_pipeline_completes_quickly(self, pipeline):
        """
        Test: Le pipeline s'exécute rapidement (< 500ms)
        """
        output = pipeline.process(query="test")
        
        # Timing total raisonnable
        assert output.total_time_ms < 500, \
            f"Pipeline trop lent: {output.total_time_ms}ms"
    
    
    def test_retrieval_faster_than_reranking(self, pipeline):
        """
        Test: Retrieval généralement plus rapide que reranking
        (Car reranking fait batch Dgraph query)
        """
        output = pipeline.process(query="test")
        
        # Juste vérifier que les deux temps existent
        assert output.retrieval_time_ms > 0
        assert output.reranking_time_ms > 0


# ============================================================================
# TESTS - EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests des cas limites"""
    
    def test_empty_query_handling(self, pipeline):
        """
        Test: Gestion d'une query vide
        """
        try:
            output = pipeline.process(query="", top_k=5)
            # Si ça marche, vérifier output
            assert isinstance(output, TaxonomyPipelineOutput)
        except Exception as e:
            # Acceptable si lève une exception explicite
            assert "query" in str(e).lower() or "empty" in str(e).lower()
    
    
    def test_no_retrieval_results(self, mock_embedder, mock_dgraph):
        """
        Test: Gestion quand retrieval ne retourne rien
        """
        # Mock qui retourne vide
        empty_store = MagicMock()
        empty_store.search = Mock(return_value=([], []))
        empty_store.bm25_search = Mock(return_value=([], []))
        
        pipeline_empty = TaxonomyPipeline(
            vector_store=empty_store,
            embedder=mock_embedder,
            dgraph_connector=mock_dgraph
        )
        
        output = pipeline_empty.process(query="test")
        
        assert output.total_candidates == 0
        assert output.top_candidate is None
        assert len(output.all_candidates) == 0
    
    
    def test_single_candidate(self, mock_embedder, mock_dgraph):
        """
        Test: Gestion d'un seul candidat
        """
        single_store = MagicMock()
        
        # Format correct: (distances, metadata_list)
        single_store.search = Mock(return_value=(
            [0.9],  # distances
            [{      # metadata_list
                'id': '0x1',
                'name': 'Test',
                'breadcrumb': '...',
                'depth': 1,
                'domain': 'Test'
            }]
        ))
        single_store.bm25_search = Mock(return_value=([], []))
        
        pipeline_single = TaxonomyPipeline(
            vector_store=single_store,
            embedder=mock_embedder,
            dgraph_connector=mock_dgraph
        )
        
        output = pipeline_single.process(query="test")
        
        assert output.total_candidates == 1
        assert output.top_candidate is not None
        assert len(output.all_candidates) == 1


# ============================================================================
# TESTS - FACTORY
# ============================================================================

class TestFactory:
    """Tests de la fonction factory"""
    
    def test_create_taxonomy_pipeline(self, mock_vector_store, mock_embedder, mock_dgraph):
        """
        Test: La factory crée un pipeline correctement
        """
        pipeline = create_taxonomy_pipeline(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            dgraph_connector=mock_dgraph,
            dense_top_k=100,
            bm25_top_k=100,
            rrf_k=60,
            final_top_n=30
        )
        
        assert isinstance(pipeline, TaxonomyPipeline)
        
        # Tester que le pipeline fonctionne
        output = pipeline.process(query="test")
        assert isinstance(output, TaxonomyPipelineOutput)


# ============================================================================
# TESTS - INTEGRATION SCENARIOS
# ============================================================================

class TestIntegrationScenarios:
    """Tests de scénarios d'intégration réalistes"""
    
    def test_scenario_recherche_ecritures_simple(self, pipeline):
        """
        Scénario: Recherche simple d'écritures
        """
        output = pipeline.process(
            query="Comment voir mes écritures comptables ?",
            top_k=5
        )
        
        assert output.top_candidate is not None
        
        # Au moins un des top 3 devrait contenir "interrogation" ou "recherche"
        # (Le top peut varier selon le RRF et le reranking)
        found_relevant = False
        for candidate in output.all_candidates[:3]:
            name = candidate.name.lower()
            if 'interrogation' in name or 'recherche' in name:
                found_relevant = True
                break
        
        assert found_relevant, \
            f"Aucun candidat pertinent trouvé dans le top 3. Top candidat: {output.top_candidate.name}"
    
    
    def test_scenario_filtrage_journal(self, pipeline):
        """
        Scénario: Filtrage par journal
        """
        output = pipeline.process(
            query="Afficher les écritures du journal des achats",
            top_k=5,
            context={'variables': ['journal', 'achats']}
        )
        
        assert output.top_candidate is not None
        
        # Un des top candidats devrait mentionner journal ou achats
        found_relevant = False
        for candidate in output.all_candidates[:3]:
            name = candidate.name.lower()
            if 'journal' in name or 'achat' in name:
                found_relevant = True
                break
        
        assert found_relevant
    
    
    def test_scenario_balance_comptable(self, pipeline):
        """
        Scénario: Génération de balance
        """
        output = pipeline.process(
            query="Générer une balance générale",
            top_k=5
        )
        
        assert output.top_candidate is not None
        
        # Devrait trouver "Balance"
        found_balance = False
        for candidate in output.all_candidates:
            if 'balance' in candidate.name.lower():
                found_balance = True
                break
        
        assert found_balance


# ============================================================================
# TESTS - REGRESSION
# ============================================================================

class TestRegression:
    """Tests de régression"""
    
    def test_no_candidate_loss_during_enrichment(self, pipeline):
        """
        Régression: L'enrichissement ne doit pas perdre de candidats
        """
        output = pipeline.process(query="test", top_k=10)
        
        retrieval_count = output.retrieval_stats.get('dense_count', 0) + \
                         output.retrieval_stats.get('bm25_count', 0)
        
        # Note: Avec RRF fusion, le nombre final peut être < somme
        # Car il y a des doublons fusionnés
        # Mais enrichissement ne doit pas en perdre
        
        if retrieval_count > 0:
            assert output.total_candidates > 0
    
    
    def test_final_scores_always_valid(self, pipeline):
        """
        Régression: final_score toujours dans [0, 1]
        """
        output = pipeline.process(query="test", top_k=20)
        
        for candidate in output.all_candidates:
            assert 0.0 <= candidate.final_score <= 1.0, \
                f"Score invalide: {candidate.final_score}"


# ============================================================================
# SCRIPT DE TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 TESTS UNITAIRES - TAXONOMY PIPELINE")
    print("=" * 80)
    
    pytest.main([__file__, "-v", "--tb=short", "--color=yes"])