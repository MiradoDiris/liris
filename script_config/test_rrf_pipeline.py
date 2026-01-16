#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 TEST COMPLET: Pipeline RRF Dense + BM25
✅ Test de bout en bout du retrieval hybrid
"""

import sys
import logging
from pathlib import Path
import numpy as np

# Setup paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


def test_vector_store_api():
    """Test 1: Vérifier l'API du VectorStore"""
    logger.info("="*80)
    logger.info("🧪 TEST 1: VectorStore API")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    
    vector_store_path = Path("./data/indexes/faiss/vector_store.index")
    
    if not vector_store_path.exists():
        logger.error(f"❌ Vector store non trouvé: {vector_store_path}")
        return False
    
    # Charger vector store
    vector_store = VectorStore(index_path=vector_store_path)
    vector_store.initialize()
    
    # Vérifier stats
    stats = vector_store.get_stats()
    logger.info(f"\n📊 Stats Vector Store:")
    logger.info(f"   • Vecteurs: {stats['num_vectors']}")
    logger.info(f"   • Metadata: {stats['num_metadata']}")
    logger.info(f"   • Dimension: {stats['dimension']}")
    logger.info(f"   • BM25 disponible: {stats['bm25_available']}")
    
    if stats['num_vectors'] == 0:
        logger.error("❌ Vector store vide")
        return False
    
    # Test search simple
    logger.info("\n🔍 Test search() avec vecteur aléatoire...")
    dummy_vector = np.random.randn(stats['dimension']).astype('float32')
    
    try:
        distances, metadata_list = vector_store.search(dummy_vector, k=5)
        
        logger.info(f"✅ Search OK: {len(distances)} résultats")
        logger.info(f"   Format: distances={type(distances)}, metadata={type(metadata_list)}")
        
        if distances and metadata_list:
            logger.info(f"   Premier résultat:")
            logger.info(f"      Distance: {distances[0]}")
            logger.info(f"      Name: {metadata_list[0].get('name', 'N/A')}")
            logger.info(f"      Type: {metadata_list[0].get('type', 'N/A')}")
    
    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Test BM25
    if stats['bm25_available']:
        logger.info("\n🔍 Test bm25_search()...")
        try:
            bm25_distances, bm25_metadata = vector_store.bm25_search("tableau de bord", top_k=5)
            logger.info(f"✅ BM25 OK: {len(bm25_distances)} résultats")
            
            if bm25_distances and bm25_metadata:
                logger.info(f"   Premier résultat:")
                logger.info(f"      Score: {bm25_distances[0]}")
                logger.info(f"      Name: {bm25_metadata[0].get('name', 'N/A')}")
        
        except Exception as e:
            logger.error(f"❌ BM25 search failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    logger.info("\n✅ TEST 1 TERMINÉ\n")
    return True


def test_embedder():
    """Test 2: Vérifier l'embedder OSS"""
    logger.info("="*80)
    logger.info("🧪 TEST 2: OSS Embedder")
    logger.info("="*80)
    
    from context_weaver.services.oss_classifier import OSSClassifierClient
    
    try:
        oss_client = OSSClassifierClient()
        
        # Test embedding
        test_query = "consulter tableau de bord"
        logger.info(f"\n🔍 Test query: '{test_query}'")
        
        embedding = oss_client.generate_embeddings(test_query)
        
        if embedding is None or len(embedding) == 0:
            logger.error("❌ Embedding generation failed")
            return False
        
        logger.info(f"✅ Embedding généré:")
        logger.info(f"   • Dimension: {len(embedding)}")
        logger.info(f"   • Type: {type(embedding)}")
        logger.info(f"   • Norm: {np.linalg.norm(embedding):.4f}")
        
        oss_client.close()
        
    except Exception as e:
        logger.error(f"❌ Embedder test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    logger.info("\n✅ TEST 2 TERMINÉ\n")
    return True


def test_retriever():
    """Test 3: Vérifier le TaxonomyRetriever"""
    logger.info("="*80)
    logger.info("🧪 TEST 3: TaxonomyRetriever (RRF Pipeline)")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.taxonomy.taxonomy_retriever import TaxonomyRetriever, RetrievalConfig
    
    # Setup
    vector_store = VectorStore(index_path=Path("./data/indexes/faiss/vector_store.index"))
    vector_store.initialize()
    
    oss_client = OSSClassifierClient()
    
    # Adapter l'embedder pour avoir une méthode .encode()
    class EmbedderAdapter:
        def __init__(self, oss_client):
            self.oss_client = oss_client
        
        def encode(self, text: str):
            embedding = self.oss_client.generate_embeddings(text)
            if embedding is None:
                raise ValueError("Failed to generate embedding")
            return np.array(embedding)
    
    embedder = EmbedderAdapter(oss_client)
    
    # Config
    config = RetrievalConfig(
        dense_top_k=50,
        bm25_top_k=50,
        rrf_k=60,
        final_top_n=10,
        boost_by_depth=True
    )
    
    # Créer retriever
    retriever = TaxonomyRetriever(
        vector_store=vector_store,
        embedder=embedder,
        config=config
    )
    
    # Test queries
    test_queries = [
        {
            'query': 'consulter afficher tableau de bord',
            'context': {'domain': 'Macompta.fr'},
            'expected': 'Tableau de bord'
        },
        {
            'query': 'créer une facture',
            'context': {'domain': 'Macompta.fr'},
            'expected': 'facture'
        },
        {
            'query': 'voir les comptes bancaires',
            'context': None,
            'expected': 'compte'
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        logger.info(f"\n{'─'*80}")
        logger.info(f"🔍 Test Query {i}/{len(test_queries)}")
        logger.info(f"{'─'*80}")
        logger.info(f"Query: '{test['query']}'")
        logger.info(f"Context: {test['context']}")
        logger.info(f"Expected: '{test['expected']}'")
        
        try:
            result = retriever.retrieve(
                query_text=test['query'],
                context=test['context']
            )
            
            logger.info(f"\n📊 Résultats:")
            logger.info(f"   • Total candidats: {result.total_retrieved}")
            logger.info(f"   • Dense count: {result.dense_count}")
            logger.info(f"   • BM25 count: {result.bm25_count}")
            logger.info(f"   • Top N retourné: {len(result.candidates)}")
            logger.info(f"   • Time: {result.total_time_ms:.2f}ms")
            logger.info(f"   • Dense top score: {result.dense_top_score:.4f}")
            logger.info(f"   • BM25 top score: {result.bm25_top_score:.4f}")
            logger.info(f"   • RRF top score: {result.rrf_top_score:.4f}")
            logger.info(f"   • RRF score range: [{result.rrf_min_score:.4f}, {result.rrf_max_score:.4f}]")
            
            # Afficher top 3
            logger.info(f"\n   🏆 Top 3 candidats:")
            for idx, candidate in enumerate(result.candidates[:3], 1):
                logger.info(f"      {idx}. {candidate.name}")
                logger.info(f"         • RRF Score: {candidate.rrf_score:.4f}")
                logger.info(f"         • Final Score: {candidate.final_score:.4f}")
                
                # ✅ FIX: Vérifier l'existence des attributs avant d'y accéder
                if hasattr(candidate, 'dense_score'):
                    dense_rank = getattr(candidate, 'dense_rank', 'N/A')
                    logger.info(f"         • Dense: {candidate.dense_score:.4f} (rank={dense_rank})")
                
                if hasattr(candidate, 'bm25_score'):
                    bm25_rank = getattr(candidate, 'bm25_rank', 'N/A')
                    logger.info(f"         • BM25: {candidate.bm25_score:.4f} (rank={bm25_rank})")
                
                # ✅ FIX: 'source' n'existe pas dans TaxonCandidate selon taxonomy_models.py
                logger.info(f"         • Taxon ID: {candidate.taxon_id}")
                logger.info(f"         • Breadcrumb: {candidate.breadcrumb}")
                logger.info(f"         • Depth: {candidate.depth}")
                
                # Afficher metadata si disponible
                if candidate.metadata:
                    domain = candidate.metadata.get('domain', 'N/A')
                    logger.info(f"         • Domain: {domain}")
            
            # Vérifier expected
            found = any(test['expected'].lower() in c.name.lower() for c in result.candidates[:5])
            if found:
                logger.info(f"\n   ✅ Expected term '{test['expected']}' found in top 5")
            else:
                logger.warning(f"\n   ⚠️ Expected term '{test['expected']}' NOT in top 5")
        
        except Exception as e:
            logger.error(f"\n   ❌ Retrieval failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    oss_client.close()
    
    logger.info("\n✅ TEST 3 TERMINÉ\n")
    return True


def test_full_pipeline():
    """Test 4: Pipeline complète avec Validator"""
    logger.info("="*80)
    logger.info("🧪 TEST 4: Pipeline Complète (Retriever + Validator)")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.pipeline.taxonomy_pipeline import TaxonomyPipeline, RetrievalConfig
    from context_weaver.taxonomy.taxonomy_models import ConversationState
    
    # Setup
    vector_store = VectorStore(index_path=Path("./data/indexes/faiss/vector_store.index"))
    vector_store.initialize()
    
    oss_client = OSSClassifierClient()
    
    class EmbedderAdapter:
        def __init__(self, oss_client):
            self.oss_client = oss_client
        
        def encode(self, text: str):
            embedding = self.oss_client.generate_embeddings(text)
            if embedding is None:
                raise ValueError("Failed to generate embedding")
            return np.array(embedding)
    
    embedder = EmbedderAdapter(oss_client)
    
    # Config
    config = RetrievalConfig(
        dense_top_k=50,
        bm25_top_k=50,
        final_top_n=10
    )
    
    # Créer pipeline
    try:
        pipeline = TaxonomyPipeline(
            vector_store=vector_store,
            embedder=embedder,
            retrieval_config=config,
            taxonomy_metadata={}
        )
    except Exception as e:
        logger.error(f"❌ Pipeline initialization failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        oss_client.close()
        return False
    
    # Test query
    test_query = "consulter tableau de bord"
    test_context = {
        'domain': 'Macompta.fr',
        'task': 'view_dashboard'
    }
    
    conversation_state = ConversationState(conversation_id="test_001")
    
    logger.info(f"\n🔍 Test Query: '{test_query}'")
    
    try:
        result = pipeline.process(
            user_query=test_query,
            user_context=test_context,
            conversation_state=conversation_state
        )
        
        logger.info(f"\n📊 Pipeline Result:")
        logger.info(f"   • Status: {result.status}")
        logger.info(f"   • Can access graph: {result.can_access_graph}")
        logger.info(f"   • Validated taxon: {result.validated_taxon_name} (ID: {result.validated_taxon_id})")
        logger.info(f"   • Clarification needed: {result.clarification_needed}")
        
        if result.clarification_question:
            logger.info(f"   • Question: {result.clarification_question}")
        
        if result.abstain_reason:
            logger.info(f"   • Abstain reason: {result.abstain_reason}")
        
        logger.info(f"   • Total time: {result.total_time_ms:.2f}ms")
        
        # Afficher details
        result_dict = result.to_dict()
        logger.info(f"\n📋 Retrieval Stats:")
        for key, value in result_dict.get('retrieval_stats', {}).items():
            logger.info(f"   • {key}: {value}")
        
        logger.info(f"\n📋 Validation Stats:")
        for key, value in result_dict.get('validation_stats', {}).items():
            logger.info(f"   • {key}: {value}")
        
        logger.info(f"\n✅ Pipeline execution successful")
    
    except Exception as e:
        logger.error(f"\n❌ Pipeline execution failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        oss_client.close()
        return False
    
    oss_client.close()
    
    logger.info("\n✅ TEST 4 TERMINÉ\n")
    return True


def main():
    """Exécute tous les tests"""
    
    print("\n" + "="*80)
    print("🧪 SUITE DE TESTS: Pipeline RRF Dense + BM25")
    print("="*80 + "\n")
    
    tests = [
        ("VectorStore API", test_vector_store_api),
        ("OSS Embedder", test_embedder),
        ("TaxonomyRetriever (RRF)", test_retriever),
        ("Pipeline Complète", test_full_pipeline)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            logger.error(f"\n❌ {test_name} crashed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            results[test_name] = False
        
        print("\n" + "─"*80 + "\n")
    
    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80 + "\n")
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}  {test_name}")
    
    total = len(results)
    passed = sum(1 for s in results.values() if s)
    
    print(f"\n   Total: {passed}/{total} tests passés")
    print("="*80 + "\n")
    
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())