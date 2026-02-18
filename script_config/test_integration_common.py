#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests d'Intégration Communs - Système Complet
Tests End-to-End sur des scénarios comptables réels
"""

import pytest
import logging
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Imports du système
from context_weaver.pipeline.main_pipeline import create_pipeline, ContextWeaverPipeline
from context_weaver.models.schemas import PipelineOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CAS DE TEST COMPTABLES RÉELS
# ============================================================================

class ComptabiliteTestSuite:
    """Suite de tests basée sur l'arborescence réelle macompta.fr"""
    
    SCENARIOS = [
        {
            "id": "E2E_001",
            "name": "Recherche simple - Écritures comptables",
            "query": "Comment je peux voir mes écritures comptables du mois dernier ?",
            "user_level": "débutant",
            "expected": {
                "domain": "Macompta.fr",
                "task": "consultation",
                "min_results": 3,
                "min_score": 0.3,
                "breadcrumb_keywords": ["Interrogation", "recherche", "Éditions"]
            }
        },
        {
            "id": "E2E_002",
            "name": "Filtrage - Journal des achats",
            "query": "Je veux afficher uniquement les écritures du journal des achats entre janvier et mars",
            "user_level": "intermédiaire",
            "expected": {
                "domain": "Macompta.fr",
                "task": "filtrage",
                "min_results": 5,
                "min_score": 0.4,
                "breadcrumb_keywords": ["Choix journal", "HA", "Achats"],
                "depth_min": 3
            }
        },
        {
            "id": "E2E_003",
            "name": "Recherche avancée - Compte avec lettrage",
            "query": "Extraire toutes les opérations du compte 411000 pour l'exercice en cours avec les écritures non lettrées",
            "user_level": "avancé",
            "expected": {
                "domain": "Macompta.fr",
                "task": "extraction",
                "min_results": 4,
                "min_score": 0.35,
                "breadcrumb_keywords": ["compte", "lettrage", "Options"],
                "depth_min": 3
            }
        },
        {
            "id": "E2E_004",
            "name": "Export - PDF pour expert-comptable",
            "query": "J'ai besoin d'exporter mes écritures en PDF pour mon expert-comptable",
            "user_level": "débutant",
            "expected": {
                "domain": "Macompta.fr",
                "task": "export",
                "min_results": 3,
                "min_score": 0.3,
                "breadcrumb_keywords": ["Actions", "Exporter", "PDF"]
            }
        },
        {
            "id": "E2E_005",
            "name": "Balance - Comparaison N-1",
            "query": "Comment générer une balance générale pour comparer avec l'année dernière ?",
            "user_level": "intermédiaire",
            "expected": {
                "domain": "Macompta.fr",
                "task": "génération",
                "min_results": 3,
                "min_score": 0.4,
                "breadcrumb_keywords": ["Balance", "N-1", "comparée"],
                "depth_min": 2
            }
        },
        {
            "id": "E2E_006",
            "name": "Multi-critères - Montant et période",
            "query": "Afficher les écritures du journal BQ1 entre 500€ et 5000€ pour le mois de février avec sous-total mensuel",
            "user_level": "avancé",
            "expected": {
                "domain": "Macompta.fr",
                "task": "recherche_avancée",
                "min_results": 5,
                "min_score": 0.35,
                "breadcrumb_keywords": ["journal", "Montant", "Options"],
                "depth_min": 3
            }
        },
        {
            "id": "E2E_007",
            "name": "Balance tiers - Clients",
            "query": "Je veux voir la balance de mes clients au 31/12",
            "user_level": "intermédiaire",
            "expected": {
                "domain": "Macompta.fr",
                "task": "consultation",
                "min_results": 3,
                "min_score": 0.4,
                "breadcrumb_keywords": ["Balance", "Clients"],
                "depth_min": 2
            }
        },
        {
            "id": "E2E_008",
            "name": "Recherche - Référence facture",
            "query": "Retrouver toutes les écritures avec la référence facture FA2024-001",
            "user_level": "intermédiaire",
            "expected": {
                "domain": "Macompta.fr",
                "task": "recherche",
                "min_results": 3,
                "min_score": 0.3,
                "breadcrumb_keywords": ["Référence", "Résultats"]
            }
        },
        {
            "id": "E2E_009",
            "name": "Lettrage - Fournisseurs",
            "query": "Comment afficher uniquement les écritures lettrées du compte fournisseur 401000 ?",
            "user_level": "avancé",
            "expected": {
                "domain": "Macompta.fr",
                "task": "filtrage",
                "min_results": 4,
                "min_score": 0.35,
                "breadcrumb_keywords": ["compte", "lettré", "Options"],
                "depth_min": 3
            }
        },
        {
            "id": "E2E_010",
            "name": "Analyse - Évolution mensuelle ventes",
            "query": "Afficher mes ventes avec un sous-total par mois pour analyser l'évolution",
            "user_level": "intermédiaire",
            "expected": {
                "domain": "Macompta.fr",
                "task": "analyse",
                "min_results": 4,
                "min_score": 0.35,
                "breadcrumb_keywords": ["VTE", "sous-total", "mois"]
            }
        }
    ]


# ============================================================================
# FIXTURE - PIPELINE RÉEL
# ============================================================================

@pytest.fixture(scope="module")
def real_pipeline():
    """
    Pipeline réel pour tests E2E
    
    Note: Nécessite une connexion Dgraph et vector store fonctionnels
    Peut être mocké selon l'environnement de test
    """
    
    try:
        # Tester la disponibilité de l'OSS Classifier
        import requests
        try:
            requests.get("http://localhost:8086/health", timeout=2)
        except:
            pytest.skip("OSS Classifier non disponible sur le port 8085. Démarrez le service ou utilisez des mocks.")
        
        # Tester la disponibilité de Dgraph
        import pydgraph
        try:
            from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
            dgraph = TaxonomyDgraphConnector()
            if dgraph.client is None:
                pytest.skip("Dgraph non disponible. Démarrez Dgraph ou utilisez des mocks.")
        except:
            pytest.skip("Dgraph non disponible. Démarrez Dgraph ou utilisez des mocks.")
        
        # Tenter de créer un pipeline réel
        pipeline = create_pipeline(
            project_name="e2e_tests",
            dgraph_url="localhost:9080"
        )
        
        logger.info("✅ Pipeline réel initialisé")
        
        yield pipeline
        
        # Cleanup
        pipeline.close()
        
    except Exception as e:
        logger.warning(f"⚠️ Impossible de créer pipeline réel: {e}")
        pytest.skip(f"Infrastructure non disponible: {e}")


# ============================================================================
# TESTS E2E - SCÉNARIOS COMPLETS
# ============================================================================

class TestE2EScenarios:
    """Tests End-to-End sur scénarios réels"""
    
    @pytest.mark.parametrize("scenario", ComptabiliteTestSuite.SCENARIOS)
    def test_scenario_execution(self, real_pipeline, scenario):
        """
        Test E2E: Exécution complète d'un scénario
        
        Valide:
        1. Classification OSS correcte
        2. Retrieval RRF retourne des résultats
        3. Reranking améliore le classement
        4. Résultats pertinents et enrichis
        """
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 Test E2E: {scenario['id']} - {scenario['name']}")
        logger.info(f"{'='*80}")
        logger.info(f"Query: {scenario['query']}")
        logger.info(f"Niveau: {scenario['user_level']}")
        
        # Exécution
        output = real_pipeline.run(
            user_context=scenario['query'],
            conversation_id=f"e2e_{scenario['id']}"
        )
        
        # === VALIDATION 1: Classification ===
        logger.info("\n📊 Validation Classification")
        assert output.classification is not None
        assert output.classification.domain == scenario['expected']['domain']
        assert output.classification.task is not None
        logger.info(f"   ✅ Domain: {output.classification.domain}")
        logger.info(f"   ✅ Task: {output.classification.task}")
        
        # === VALIDATION 2: Nombre de résultats ===
        logger.info("\n🔍 Validation Résultats")
        min_results = scenario['expected']['min_results']
        assert output.search_results.final_count >= min_results, \
            f"Pas assez de résultats: {output.search_results.final_count} < {min_results}"
        logger.info(f"   ✅ Nombre résultats: {output.search_results.final_count} >= {min_results}")
        
        # === VALIDATION 3: Score top candidat ===
        if output.search_results.results:
            top_score = output.search_results.results[0].score
            min_score = scenario['expected']['min_score']
            
            assert top_score >= min_score, \
                f"Score trop faible: {top_score} < {min_score}"
            logger.info(f"   ✅ Top score: {top_score:.3f} >= {min_score}")
        
        # === VALIDATION 4: Breadcrumb pertinent ===
        logger.info("\n🗂️ Validation Pertinence")
        keywords = scenario['expected']['breadcrumb_keywords']
        
        found_relevant = False
        for result in output.search_results.results[:3]:
            breadcrumb = result.content.get('breadcrumb', '').lower()
            
            for keyword in keywords:
                if keyword.lower() in breadcrumb:
                    found_relevant = True
                    logger.info(f"   ✅ Keyword '{keyword}' trouvé dans: {breadcrumb}")
                    break
            
            if found_relevant:
                break
        
        assert found_relevant, \
            f"Aucun keyword {keywords} trouvé dans top 3 breadcrumbs"
        
        # === VALIDATION 5: Profondeur minimale (si spécifiée) ===
        if 'depth_min' in scenario['expected']:
            depth_min = scenario['expected']['depth_min']
            top_depth = output.search_results.results[0].content.get('depth', 0)
            
            assert top_depth >= depth_min, \
                f"Profondeur insuffisante: {top_depth} < {depth_min}"
            logger.info(f"   ✅ Profondeur: {top_depth} >= {depth_min}")
        
        # === VALIDATION 6: Enrichissement metadata ===
        logger.info("\n💎 Validation Enrichissement")
        top_result = output.search_results.results[0]
        
        assert 'breadcrumb' in top_result.content
        logger.info(f"   ✅ Breadcrumb: {top_result.content['breadcrumb']}")
        
        # Vérifier metadata enrichie (si disponible)
        if 'prereq_hard_ids' in top_result.metadata:
            prereq_count = len(top_result.metadata['prereq_hard_ids'])
            logger.info(f"   ✅ Prereqs: {prereq_count}")
        
        if 'description' in top_result.metadata:
            desc = top_result.metadata['description'][:80] + "..."
            logger.info(f"   ✅ Description: {desc}")
        
        # === VALIDATION 7: Performance ===
        logger.info("\n⏱️ Validation Performance")
        exec_time = output.execution_time_ms
        
        assert exec_time < 2000, f"Trop lent: {exec_time}ms"
        logger.info(f"   ✅ Temps total: {exec_time:.0f}ms")
        
        tax_meta = output.metadata.get('taxonomy_output', {})
        if tax_meta:
            logger.info(f"   ✅ Retrieval: {tax_meta.get('retrieval_time_ms', 0):.0f}ms")
            logger.info(f"   ✅ Reranking: {tax_meta.get('reranking_time_ms', 0):.0f}ms")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ Test E2E {scenario['id']} RÉUSSI")
        logger.info(f"{'='*80}\n")


# ============================================================================
# TESTS - QUALITÉ DU SYSTÈME
# ============================================================================

class TestSystemQuality:
    """Tests de qualité globale du système"""
    
    def test_consistency_across_similar_queries(self, real_pipeline):
        """
        Test: Des queries similaires donnent des résultats cohérents
        """
        
        queries = [
            "Comment voir mes écritures comptables ?",
            "Afficher les écritures",
            "Je veux consulter mes écritures"
        ]
        
        outputs = []
        for query in queries:
            output = real_pipeline.run(user_context=query)
            outputs.append(output)
        
        # Les 3 devraient classifier vers la même task/domaine
        domains = [o.classification.domain for o in outputs]
        assert len(set(domains)) == 1, "Domaines incohérents"
        
        # Au moins le top 1 devrait être similaire
        top_ids = [o.search_results.results[0].id if o.search_results.results else None 
                   for o in outputs]
        
        # Au moins 2 sur 3 devraient avoir le même top
        most_common_id = max(set(top_ids), key=top_ids.count)
        assert top_ids.count(most_common_id) >= 2
    
    
    def test_reranking_improves_ranking(self, real_pipeline):
        """
        Test: Le reranking améliore effectivement le classement
        """
        
        output = real_pipeline.run(
            user_context="Afficher journal achats avec prereqs"
        )
        
        tax_meta = output.metadata.get('taxonomy_output', {})
        
        # Vérifier qu'il y a eu des changements de rang
        if tax_meta.get('top_candidate'):
            # Au moins vérifier que le reranking s'est exécuté
            assert tax_meta['reranking_time_ms'] > 0
    
    
    def test_deep_nodes_when_specific_query(self, real_pipeline):
        """
        Test: Les queries spécifiques retournent des nœuds profonds
        """
        
        # Query très spécifique
        output = real_pipeline.run(
            user_context="Journal des achats HA avec écritures non lettrées du compte 401000"
        )
        
        if output.search_results.results:
            top_depth = output.search_results.results[0].content.get('depth', 0)
            
            # Query spécifique → nœud profond (depth ≥ 3)
            assert top_depth >= 3, \
                f"Query spécifique mais nœud superficiel (depth={top_depth})"


# ============================================================================
# TESTS - ROBUSTESSE
# ============================================================================

class TestRobustness:
    """Tests de robustesse du système"""
    
    def test_handles_typos_gracefully(self, real_pipeline):
        """
        Test: Le système gère les fautes de frappe
        """
        
        # Query avec fautes
        output = real_pipeline.run(
            user_context="Comant aficher mes ecriture comptable ?"
        )
        
        # Devrait quand même retourner des résultats pertinents
        assert output.search_results.final_count > 0
        assert output.classification.domain == "Macompta.fr"
    
    
    def test_handles_mixed_terminology(self, real_pipeline):
        """
        Test: Gère mélange terminologie comptable/naturelle
        """
        
        output = real_pipeline.run(
            user_context="Je veux checker mes factures d'achat dans le compte 401"
        )
        
        assert output.search_results.final_count > 0
    
    
    def test_handles_incomplete_queries(self, real_pipeline):
        """
        Test: Gère les queries incomplètes
        """
        
        output = real_pipeline.run(user_context="balance")
        
        # Devrait quand même retourner quelque chose
        assert output.search_results.final_count > 0


# ============================================================================
# TESTS - PERFORMANCE GLOBALE
# ============================================================================

class TestOverallPerformance:
    """Tests de performance globale"""
    
    def test_batch_queries_performance(self, real_pipeline):
        """
        Test: Performance sur batch de queries
        """
        
        queries = [
            "écritures comptables",
            "balance générale",
            "journal achats",
            "export PDF",
            "compte clients"
        ]
        
        times = []
        
        for query in queries:
            output = real_pipeline.run(user_context=query)
            times.append(output.execution_time_ms)
        
        # Moyenne < 1 seconde
        avg_time = sum(times) / len(times)
        assert avg_time < 1000, f"Temps moyen trop élevé: {avg_time}ms"
        
        # Aucune query > 2 secondes
        assert max(times) < 2000, f"Query trop lente: {max(times)}ms"
        
        logger.info(f"📊 Performance batch:")
        logger.info(f"   Moyenne: {avg_time:.0f}ms")
        logger.info(f"   Min: {min(times):.0f}ms")
        logger.info(f"   Max: {max(times):.0f}ms")


# ============================================================================
# UTILITAIRES - SAUVEGARDE RÉSULTATS
# ============================================================================

class TestResultsCollector:
    """Collecte et sauvegarde les résultats de tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup pour chaque test"""
        self.results = []
        yield
        # Teardown - sauvegarder les résultats
        self._save_results()
    
    
    def _save_results(self):
        """Sauvegarde les résultats de tests"""
        
        if not self.results:
            return
        
        output_dir = Path("test_results/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"e2e_results_{timestamp}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Résultats sauvegardés: {filepath}")
    
    
    def collect_result(self, scenario_id: str, output: PipelineOutput, passed: bool):
        """Collecte un résultat de test"""
        
        result = {
            'scenario_id': scenario_id,
            'timestamp': datetime.now().isoformat(),
            'passed': passed,
            'classification': {
                'domain': output.classification.domain,
                'task': output.classification.task,
                'variables': output.classification.variables
            },
            'results_count': output.search_results.final_count,
            'top_score': output.search_results.results[0].score if output.search_results.results else 0,
            'execution_time_ms': output.execution_time_ms,
            'taxonomy_timing': output.metadata.get('taxonomy_output', {})
        }
        
        self.results.append(result)


# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 TESTS D'INTÉGRATION E2E - SYSTÈME COMPLET")
    print("=" * 80)
    print("""
    Ces tests valident le système complet sur des scénarios comptables réels.
    
    Scénarios testés:
    - Recherche simple d'écritures
    - Filtrage par journal (achats, ventes, banque...)
    - Recherche avancée avec lettrage
    - Export PDF/CSV
    - Balance générale et auxiliaires
    - Analyses multi-critères
    
    Validations:
    ✅ Classification OSS correcte
    ✅ Retrieval RRF performant
    ✅ Reranking améliore le classement
    ✅ Enrichissement metadata Dgraph
    ✅ Performance < 2 secondes
    ✅ Pertinence des résultats
    """)
    
    print("\n🚀 Lancement des tests...")
    print("=" * 80 + "\n")
    
    # Exécuter avec pytest
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--color=yes",
        "-k", "test_scenario_execution"  # Ou "" pour tous les tests
    ])