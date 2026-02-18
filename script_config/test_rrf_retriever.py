#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Context Weaver Pipeline - Emma Dataset Generation Query
=============================================================

Ce script teste le pipeline Context Weaver avec la requête spécifique
pour générer un dataset d'entraînement pour Emma.

✅ VERSION ADAPTÉE POUR TaxonomyDgraphConnector

Objectifs du test:
1. Vérifier que le pipeline ne crash pas
2. Valider l'extraction des paramètres contextuels
3. Examiner la pertinence des résultats retournés
4. Identifier les problèmes potentiels (UID invalides, métadonnées manquantes, etc.)
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_emma_dataset.log', mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


# =============================================================================
# QUERY DE TEST (LA REQUÊTE COMPLÈTE)
# =============================================================================

EMMA_DATASET_QUERY = """Générer un dataset d'inputs utilisateur réalistes pour entraîner Emma, une IA conversationnelle spécialisée dans macompta.fr. Chaque input doit refléter une situation authentique, avec des formulations variées, naturelles ou familières, et correspondre aux besoins spécifiques d'un utilisateur dans le cadre d'un RDV d'onboarding.

Consignes générales :
Chaque input doit être formulé du point de vue de l'utilisateur et correspondre à un cas concret.
La première question est initiée par Emma ; tous les inputs suivants doivent refléter les réponses ou relances de l'utilisateur.
Aucun output d'Emma n'est demandé à ce stade : uniquement les inputs utilisateur.

Les inputs doivent couvrir toutes les combinaisons possibles des paramètres suivants :
Forme juridique : SARL, etc.
Type fiscal et domaine d'activité : impôt sur les sociétés, prestataire de services, plan standard, etc.
Date d'exercice : 1er janvier – 31 décembre
Type de comptabilité : Créances / Dettes

Typologies à intégrer implicitement dans chaque input :
Intention : ce que l'utilisateur cherche à faire ou comprendre (ex. : obtenir une info, réaliser une action, corriger une erreur, recevoir un conseil).
Niveau de maîtrise : débutant, intermédiaire, avancé ; à déduire de la formulation et du vocabulaire.
Complexité / niveau de confiance : simple ou sensible ; adapte le détail et le ton si la demande est complexe.
Abonnement / fonctionnalités : respecter ce qui est accessible selon l'offre macompta.fr.
Données du compte : type d'activité, statut juridique, régime fiscal, etc.
UI / UX : contexte de l'écran et parcours utilisé, pour guider l'utilisateur avec repères concrets.
Temporalité : tenir compte de la date et des obligations fiscales, sociales et comptables.
Type d'interaction : onboarding, suivi régulier, demande ponctuelle.

Instructions supplémentaires :
Génère des inputs variés, couvrant toutes les combinaisons possibles des paramètres de paramétrage.
Alterne le style : formulation directe, familière, vague ou approximative selon le profil de l'utilisateur.
Intègre naturellement les échanges liés à la liasse fiscale au milieu de la conversation.
Assure que chaque input reste concret, réaliste et exploitable, sans jamais sortir du contexte macompta.fr.
"""


# =============================================================================
# CONFIGURATION DGRAPH (OPTIONNELLE)
# =============================================================================

DGRAPH_CONFIG = {
    'enabled': True,  # ✅ Mettre à True pour activer Dgraph
    'grpc_port': 'localhost:9082',  # ✅ ADAPTÉ pour TaxonomyDgraphConnector
    'http_port': 'localhost:8082',
    'ratel_port': 'http://localhost:8092'
}


# =============================================================================
# FONCTION D'INITIALISATION DGRAPH
# =============================================================================

def initialize_dgraph() -> Optional[Any]:
    """
    Tente d'initialiser Dgraph avec TaxonomyDgraphConnector
    
    Returns:
        TaxonomyDgraphConnector ou None si non disponible/désactivé
    """
    
    if not DGRAPH_CONFIG['enabled']:
        logger.info("   ℹ️  Dgraph: DISABLED (set DGRAPH_CONFIG['enabled']=True to enable)")
        return None
    
    try:
        # ✅ MODIFIÉ: Import du bon connecteur
        import sys
        from pathlib import Path
        
        # Ajouter le chemin vers le module si nécessaire
        # (ajustez selon votre structure de projet)
        # sys.path.insert(0, str(Path(__file__).parent.parent))
        
        from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
        
        logger.info(f"   • Initializing Dgraph: {DGRAPH_CONFIG['grpc_port']}...")
        
        # ✅ MODIFIÉ: TaxonomyDgraphConnector n'a pas de paramètres dans __init__
        # La configuration est faite via les constantes globales du module
        dgraph_connector = TaxonomyDgraphConnector()
        
        # Vérifier que la connexion s'est bien établie
        if dgraph_connector.client is None:
            logger.warning("   ⚠️ Dgraph client is None - connection failed")
            logger.warning(f"   → Check that Dgraph is running on {DGRAPH_CONFIG['grpc_port']}")
            logger.warning("   → Pipeline will run in degraded mode (no enrichment)")
            return None
        
        logger.info("   ✅ Dgraph connected successfully")
        logger.info(f"   ✅ Ratel UI available at: {DGRAPH_CONFIG['ratel_port']}")
        return dgraph_connector
        
    except ImportError as e:
        logger.warning(f"   ⚠️ TaxonomyDgraphConnector module not found: {e}")
        logger.warning("   → Check that dgraph_taxonomy_connector.py is in PYTHONPATH")
        logger.warning("   → Pipeline will run in degraded mode (no enrichment)")
        return None
        
    except ConnectionError as e:
        logger.warning(f"   ⚠️ Cannot connect to Dgraph: {e}")
        logger.warning(f"   → Check that Dgraph is running on {DGRAPH_CONFIG['grpc_port']}")
        logger.warning("   → Try: docker-compose up dgraph")
        logger.warning("   → Pipeline will run in degraded mode (no enrichment)")
        return None
        
    except Exception as e:
        logger.warning(f"   ⚠️ Dgraph initialization error: {e}")
        logger.warning("   → Pipeline will run in degraded mode (no enrichment)")
        import traceback
        logger.debug(traceback.format_exc())
        return None


# =============================================================================
# FONCTION DE TEST PRINCIPALE
# =============================================================================

def test_context_weaver_with_emma_query():
    """
    Test principal du pipeline Context Weaver avec la requête Emma
    """
    
    print("\n" + "=" * 80)
    print("🧪 TEST CONTEXT WEAVER - EMMA DATASET GENERATION")
    print("=" * 80)
    print()
    
    # =========================================================================
    # STEP 1: Import et initialisation
    # =========================================================================
    
    logger.info("📦 STEP 1: Importing modules...")
    
    try:
        from context_weaver.pipeline.main_pipeline import create_pipeline
        from context_weaver.services.oss_classifier import OSSClassifierClient
        from context_weaver.data.vector_store_chroma import VectorStore
        logger.info("✅ Modules imported successfully")
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Assurez-vous que context_weaver est dans le PYTHONPATH")
        return False
    
    # =========================================================================
    # STEP 2: Initialisation des composants
    # =========================================================================
    
    logger.info("\n📦 STEP 2: Initializing components...")
    
    try:
        # VectorStore
        logger.info("   • Initializing VectorStore...")
        vector_store = VectorStore()
        vector_store.initialize()
        doc_count = vector_store.get_document_count()
        logger.info(f"   ✅ VectorStore ready: {doc_count} documents")
        
        if doc_count == 0:
            logger.warning("   ⚠️ VectorStore is EMPTY - results may be limited")
        
        # OSS Client
        logger.info("   • Initializing OSS Client...")
        oss_client = OSSClassifierClient()
        logger.info("   ✅ OSS Client ready")
        
        # ✅ NOUVEAU: Dgraph (optionnel) avec TaxonomyDgraphConnector
        dgraph_connector = initialize_dgraph()
        
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}")
        logger.exception("Full traceback:")
        return False
    
    # =========================================================================
    # STEP 3: Création du pipeline
    # =========================================================================
    
    logger.info("\n🔧 STEP 3: Creating pipeline...")
    
    try:
        # Passer dgraph_connector (peut être None)
        pipeline = create_pipeline(
            project_name="macompta_fr",
            vector_store=vector_store,
            oss_client=oss_client,
            dgraph_connector=dgraph_connector,  # ✅ TaxonomyDgraphConnector ou None
            use_domain_filter=True,
            default_domain="Macompta.fr",
            query_strategy="full_prompt"  # Utilise le prompt complet
        )
        logger.info("✅ Pipeline created successfully")
        
        # Log du mode d'opération
        if dgraph_connector is not None:
            logger.info("   🔗 Mode: FULL (with Dgraph enrichment via TaxonomyDgraphConnector)")
        else:
            logger.info("   ⚡ Mode: DEGRADED (without Dgraph enrichment)")
        
    except Exception as e:
        logger.error(f"❌ Pipeline creation error: {e}")
        logger.exception("Full traceback:")
        return False
    
    # =========================================================================
    # STEP 4: Exécution de la requête
    # =========================================================================
    
    logger.info("\n🚀 STEP 4: Executing query...")
    logger.info(f"   Query length: {len(EMMA_DATASET_QUERY)} chars")
    logger.info(f"   Query preview: {EMMA_DATASET_QUERY[:100]}...")
    
    try:
        result = pipeline.run(
            user_context=EMMA_DATASET_QUERY,
            top_k=20,  # Demander plus de résultats pour analyse
            domain="Macompta.fr"
        )
        logger.info("✅ Query executed successfully")
        
    except Exception as e:
        logger.error(f"❌ Query execution error: {e}")
        logger.exception("Full traceback:")
        
        # Fermer le pipeline avant de retourner
        try:
            pipeline.close()
        except:
            pass
        
        return False
    
    # =========================================================================
    # STEP 5: Analyse des résultats
    # =========================================================================
    
    logger.info("\n📊 STEP 5: Analyzing results...")
    
    try:
        analyze_results(result, dgraph_enabled=(dgraph_connector is not None))
    except Exception as e:
        logger.error(f"❌ Result analysis error: {e}")
        logger.exception("Full traceback:")
    
    # =========================================================================
    # STEP 6: Fermeture propre
    # =========================================================================
    
    logger.info("\n🔒 STEP 6: Closing pipeline...")
    
    try:
        pipeline.close()
        logger.info("✅ Pipeline closed successfully")
        
        # ✅ AJOUTÉ: Fermer explicitement le connecteur Dgraph
        if dgraph_connector is not None:
            dgraph_connector.close()
            logger.info("✅ Dgraph connector closed")
            
    except Exception as e:
        logger.warning(f"⚠️ Close warning: {e}")
    
    # =========================================================================
    # CONCLUSION
    # =========================================================================
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETED")
    print("=" * 80)
    print(f"\nLogs saved to: test_emma_dataset.log")
    print()
    
    return True


# =============================================================================
# FONCTION D'ANALYSE DES RÉSULTATS
# =============================================================================

def analyze_results(result, dgraph_enabled: bool = False):
    """
    Analyse détaillée des résultats du pipeline
    
    Args:
        result: PipelineOutput
        dgraph_enabled: Indique si Dgraph était activé
    """
    
    logger.info("=" * 80)
    logger.info("📈 DETAILED RESULTS ANALYSIS")
    logger.info("=" * 80)
    
    # -------------------------------------------------------------------------
    # 1. Informations générales
    # -------------------------------------------------------------------------
    
    logger.info("\n1️⃣ GENERAL INFORMATION:")
    logger.info(f"   • Execution time: {result.execution_time_ms:.2f}ms")
    logger.info(f"   • Results count: {result.search_results.final_count}")
    logger.info(f"   • Classification domain: {result.classification.domain}")
    logger.info(f"   • Classification task: {result.classification.task}")
    logger.info(f"   • Decision type: {result.classification.decision_type}")
    logger.info(f"   • Dgraph enrichment: {'✅ ENABLED (TaxonomyDgraphConnector)' if dgraph_enabled else '❌ DISABLED'}")
    
    # -------------------------------------------------------------------------
    # 2. Paramètres extraits
    # -------------------------------------------------------------------------
    
    logger.info("\n2️⃣ EXTRACTED PARAMETERS:")
    
    extracted_params = result.metadata.get('extracted_params', {})
    params_count = result.metadata.get('params_count', 0)
    
    if extracted_params:
        logger.info(f"   ✅ {params_count} parameter(s) extracted:")
        for category, values in extracted_params.items():
            logger.info(f"      • {category}: {', '.join(values)}")
    else:
        logger.warning("   ⚠️ No parameters extracted (may be normal for this query)")
    
    # -------------------------------------------------------------------------
    # 3. Query processing
    # -------------------------------------------------------------------------
    
    logger.info("\n3️⃣ QUERY PROCESSING:")
    logger.info(f"   • Original query length: {result.metadata.get('query_length_original', 0)} chars")
    logger.info(f"   • Enhanced query length: {result.metadata.get('query_length_enhanced', 0)} chars")
    logger.info(f"   • Query strategy: {result.metadata.get('query_strategy', 'unknown')}")
    
    enhanced_query = result.metadata.get('enhanced_query', '')
    if enhanced_query:
        logger.info(f"   • Enhanced query preview: {enhanced_query[:100]}...")
    
    # -------------------------------------------------------------------------
    # 4. Taxonomy pipeline stats
    # -------------------------------------------------------------------------
    
    logger.info("\n4️⃣ TAXONOMY PIPELINE STATISTICS:")
    
    taxonomy_output = result.metadata.get('taxonomy_output', {})
    
    if taxonomy_output:
        logger.info(f"   • Total candidates: {taxonomy_output.get('total_candidates', 0)}")
        logger.info(f"   • Retrieval time: {taxonomy_output.get('retrieval_time_ms', 0):.2f}ms")
        logger.info(f"   • Reranking time: {taxonomy_output.get('reranking_time_ms', 0):.2f}ms")
        logger.info(f"   • Total time: {taxonomy_output.get('total_time_ms', 0):.2f}ms")
        
        top_candidate = taxonomy_output.get('top_candidate')
        if top_candidate:
            logger.info(f"\n   🏆 TOP CANDIDATE:")
            logger.info(f"      • Taxon ID: {top_candidate.get('taxon_id', 'N/A')}")
            logger.info(f"      • Name: {top_candidate.get('name', 'N/A')}")
            logger.info(f"      • Final score: {top_candidate.get('final_score', 0):.4f}")
            logger.info(f"      • Breadcrumb: {top_candidate.get('breadcrumb', 'N/A')}")
            
            # Indication si enrichi par Dgraph
            if dgraph_enabled:
                has_description = bool(top_candidate.get('metadata', {}).get('description'))
                has_prereqs = bool(top_candidate.get('metadata', {}).get('prereq_hard_ids'))
                
                if has_description or has_prereqs:
                    logger.info(f"      • Dgraph enrichment: ✅ Active")
                    if has_description:
                        logger.info(f"         - Description enrichie")
                    if has_prereqs:
                        logger.info(f"         - Prérequis disponibles")
                else:
                    logger.info(f"      • Dgraph enrichment: ⚠️ No data retrieved")
    
    # -------------------------------------------------------------------------
    # 5. Top résultats détaillés
    # -------------------------------------------------------------------------
    
    logger.info("\n5️⃣ TOP 10 RESULTS (DETAILED):")
    
    if result.search_results.results:
        for i, res in enumerate(result.search_results.results[:10], 1):
            logger.info(f"\n   [{i}] {res.name}")
            logger.info(f"       • Score: {res.score:.4f}")
            logger.info(f"       • Type: {res.type}")
            logger.info(f"       • Domain: {res.domain}")
            logger.info(f"       • Method: {res.method}")
            
            # Breadcrumb
            breadcrumb = res.content.get('breadcrumb', '')
            if breadcrumb:
                # Afficher seulement les 3 derniers niveaux
                levels = breadcrumb.split(' > ')
                if len(levels) > 3:
                    short_breadcrumb = ' > '.join(levels[-3:])
                    logger.info(f"       • Path: ...{short_breadcrumb}")
                else:
                    logger.info(f"       • Path: {breadcrumb}")
            
            # Definition (extrait)
            definition = res.content.get('definition', '')
            if definition:
                logger.info(f"       • Definition: {definition[:80]}...")
            
            # Metadata importantes
            if res.metadata:
                source = res.metadata.get('source', 'unknown')
                is_exact = res.metadata.get('is_exact_match', False)
                
                if is_exact:
                    logger.info(f"       • 🎯 EXACT MATCH")
                
                logger.info(f"       • Source: {source}")
                
                # Indiquer si enrichi par Dgraph
                if dgraph_enabled and res.metadata.get('description'):
                    logger.info(f"       • 🔗 Dgraph: enriched")
    else:
        logger.warning("   ⚠️ No results returned")
    
    # -------------------------------------------------------------------------
    # 6. Statistiques retrieval
    # -------------------------------------------------------------------------
    
    logger.info("\n6️⃣ RETRIEVAL STATISTICS:")
    logger.info(f"   • BM25 count: {result.search_results.bm25_count}")
    logger.info(f"   • Embedding count: {result.search_results.embedding_count}")
    logger.info(f"   • Final count: {result.search_results.final_count}")
    logger.info(f"   • Fusion method: {result.search_results.fusion_method}")
    
    # -------------------------------------------------------------------------
    # 7. Analyse de pertinence
    # -------------------------------------------------------------------------
    
    logger.info("\n7️⃣ RELEVANCE ANALYSIS:")
    
    if result.search_results.results:
        scores = [r.score for r in result.search_results.results]
        
        logger.info(f"   • Top score: {max(scores):.4f}")
        logger.info(f"   • Median score: {sorted(scores)[len(scores)//2]:.4f}")
        logger.info(f"   • Min score: {min(scores):.4f}")
        logger.info(f"   • Score range: {max(scores) - min(scores):.4f}")
        
        # Analyse du top 1
        top_score = result.search_results.results[0].score
        
        if top_score >= 0.20:
            logger.info(f"   ✅ HIGH CONFIDENCE (score ≥ 0.20)")
        elif top_score >= 0.15:
            logger.info(f"   ✅ MEDIUM CONFIDENCE (score ≥ 0.15)")
        elif top_score >= 0.10:
            logger.warning(f"   ⚠️ LOW CONFIDENCE (score ≥ 0.10)")
        else:
            logger.error(f"   ❌ VERY LOW CONFIDENCE (score < 0.10)")
            logger.error(f"   → Les résultats sont probablement peu pertinents")
    
    # -------------------------------------------------------------------------
    # 8. Recommandations
    # -------------------------------------------------------------------------
    
    logger.info("\n8️⃣ RECOMMENDATIONS:")
    
    recommendations = []
    
    # Check params extraction
    if not extracted_params or params_count == 0:
        recommendations.append("Aucun paramètre extrait - vérifier SmartQueryExtractor")
    
    # Check scores
    if result.search_results.results:
        top_score = result.search_results.results[0].score
        if top_score < 0.10:
            recommendations.append("Scores très faibles - query peut être trop générique")
            recommendations.append("Suggestion: Vérifier le VectorStore et les embeddings")
    
    # Check results count
    if result.search_results.final_count < 5:
        recommendations.append(f"Peu de résultats ({result.search_results.final_count}) - vérifier le filtrage")
    
    # Recommandations Dgraph
    if not dgraph_enabled:
        recommendations.append("Dgraph désactivé - activer pour enrichissement complet")
        recommendations.append("Set DGRAPH_CONFIG['enabled']=True au début du script")
        recommendations.append("Vérifier que Dgraph tourne: docker-compose up dgraph")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            logger.warning(f"   {i}. {rec}")
    else:
        logger.info("   ✅ Pas de problème détecté")
    
    logger.info("\n" + "=" * 80)


# =============================================================================
# FONCTION POUR TESTER UNIQUEMENT L'EXTRACTION
# =============================================================================

def test_parameter_extraction_only():
    """
    Test uniquement l'extraction de paramètres (sans pipeline complet)
    """
    
    print("\n" + "=" * 80)
    print("🧪 TEST PARAMETER EXTRACTION ONLY")
    print("=" * 80)
    print()
    
    try:
        from context_weaver.pipeline.main_pipeline import SmartQueryExtractorV2
        
        extractor = SmartQueryExtractorV2()
        
        # Test avec la requête Emma
        enhanced_query, extracted_params = extractor.build_enhanced_query(
            prompt=EMMA_DATASET_QUERY,
            strategy="full_prompt"
        )
        
        print("📊 EXTRACTION RESULTS:")
        print(f"\n✅ Enhanced query length: {len(enhanced_query)} chars")
        print(f"   Preview: {enhanced_query[:200]}...\n")
        
        if extracted_params:
            print(f"✅ Extracted {sum(len(v) for v in extracted_params.values())} parameters:")
            for category, values in extracted_params.items():
                print(f"   • {category}: {', '.join(values)}")
        else:
            print("ℹ️  No parameters extracted (normal for this generic query)")
        
        print("\n" + "=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# FONCTION POUR TESTER LA CONNEXION DGRAPH
# =============================================================================

def test_dgraph_connection():
    """
    Test de la connexion Dgraph uniquement avec TaxonomyDgraphConnector
    """
    
    print("\n" + "=" * 80)
    print("🧪 TEST DGRAPH CONNECTION (TaxonomyDgraphConnector)")
    print("=" * 80)
    print()
    
    if not DGRAPH_CONFIG['enabled']:
        print("❌ Dgraph is DISABLED in config")
        print(f"   Set DGRAPH_CONFIG['enabled']=True to enable")
        print()
        return False
    
    print(f"📡 Testing connection to {DGRAPH_CONFIG['grpc_port']}...")
    print()
    
    dgraph_connector = initialize_dgraph()
    
    if dgraph_connector is not None:
        print("✅ Dgraph connection successful!")
        print(f"   • gRPC: {DGRAPH_CONFIG['grpc_port']}")
        print(f"   • HTTP: {DGRAPH_CONFIG['http_port']}")
        print(f"   • Ratel UI: {DGRAPH_CONFIG['ratel_port']}")
        
        # ✅ AJOUTÉ: Test de requête simple
        try:
            print("\n🔍 Testing basic query...")
            all_nodes = dgraph_connector.get_all_nodes_for_indexing()
            print(f"   ✅ Found {len(all_nodes)} nodes in Dgraph")
            
            if all_nodes:
                print(f"   📊 Sample nodes:")
                for node in all_nodes[:3]:
                    print(f"      • {node.get('name', 'N/A')} ({node.get('uid', 'N/A')})")
        except Exception as e:
            print(f"   ⚠️ Query test failed: {e}")
        
        # Fermer la connexion
        dgraph_connector.close()
        
        print("\n" + "=" * 80)
        return True
    else:
        print("❌ Dgraph connection failed")
        print("   Check:")
        print(f"   1. Dgraph is running on {DGRAPH_CONFIG['grpc_port']}")
        print("   2. Try: docker-compose up dgraph")
        print("   3. Network connectivity")
        print("   4. Firewall rules")
        print("\n" + "=" * 80)
        return False


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("  🧪 CONTEXT WEAVER TEST SUITE - EMMA DATASET GENERATION")
    print("  📦 Using TaxonomyDgraphConnector")
    print("=" * 100)
    
    # Menu de sélection
    print("\nSelect test to run:")
    print("  1. Full pipeline test (recommended)")
    print("  2. Parameter extraction only (quick)")
    print("  3. Dgraph connection test (TaxonomyDgraphConnector)")
    print("  4. All tests")
    print()
    
    choice = input("Your choice (1-4): ").strip()
    
    if choice == "1":
        success = test_context_weaver_with_emma_query()
    
    elif choice == "2":
        success = test_parameter_extraction_only()
    
    elif choice == "3":
        success = test_dgraph_connection()
    
    elif choice == "4":
        print("\n" + "-" * 100)
        success1 = test_dgraph_connection()
        print("\n" + "-" * 100)
        success2 = test_parameter_extraction_only()
        print("\n" + "-" * 100)
        success3 = test_context_weaver_with_emma_query()
        success = success1 and success2 and success3
    
    else:
        print("❌ Invalid choice")
        success = False
    
    # Résultat final
    print("\n" + "=" * 100)
    if success:
        print("✅ TEST SUITE COMPLETED SUCCESSFULLY")
    else:
        print("❌ TEST SUITE FAILED")
    print("=" * 100)
    print()