#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 DIAGNOSTIC: Comparaison Main Pipeline vs RRF Pipeline
Identifie pourquoi Dense search retourne 0 résultats dans main_pipeline
"""

import sys
import logging
from pathlib import Path
import numpy as np

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


def test_embedder_adapter():
    """Test 1: Vérifier l'EmbedderAdapter vs OSS direct"""
    logger.info("="*80)
    logger.info("🧪 TEST 1: EmbedderAdapter vs OSS Direct")
    logger.info("="*80)
    
    from context_weaver.services.oss_classifier import OSSClassifierClient
    
    oss_client = OSSClassifierClient()
    
    test_query = "consulter tableau de bord"
    
    # 1. Embedding direct OSS
    logger.info(f"\n📝 Query: '{test_query}'")
    logger.info("\n🔍 Method 1: Direct OSS Client")
    
    embedding_direct = oss_client.generate_embeddings(test_query)
    
    logger.info(f"   • Type: {type(embedding_direct)}")
    logger.info(f"   • Shape: {np.array(embedding_direct).shape if embedding_direct is not None else 'None'}")
    logger.info(f"   • Dtype: {np.array(embedding_direct).dtype if embedding_direct is not None else 'None'}")
    logger.info(f"   • Norm: {np.linalg.norm(embedding_direct):.4f}" if embedding_direct is not None else "   • None")
    logger.info(f"   • First 5 values: {embedding_direct[:5] if embedding_direct is not None else 'None'}")
    
    # 2. Embedding via Adapter
    logger.info("\n🔍 Method 2: Via EmbedderAdapter")
    
    class EmbedderAdapter:
        def __init__(self, oss_client):
            self.oss_client = oss_client
        
        def encode(self, text: str):
            embedding = self.oss_client.generate_embeddings(text)
            if embedding is None:
                raise ValueError("Failed to generate embedding")
            return np.array(embedding)
    
    adapter = EmbedderAdapter(oss_client)
    embedding_adapter = adapter.encode(test_query)
    
    logger.info(f"   • Type: {type(embedding_adapter)}")
    logger.info(f"   • Shape: {embedding_adapter.shape}")
    logger.info(f"   • Dtype: {embedding_adapter.dtype}")
    logger.info(f"   • Norm: {np.linalg.norm(embedding_adapter):.4f}")
    logger.info(f"   • First 5 values: {embedding_adapter[:5]}")
    
    # 3. Comparaison
    logger.info("\n📊 Comparison:")
    if embedding_direct is not None:
        diff = np.linalg.norm(np.array(embedding_direct) - embedding_adapter)
        logger.info(f"   • Difference norm: {diff:.10f}")
        logger.info(f"   • Are equal: {np.allclose(embedding_direct, embedding_adapter)}")
    
    oss_client.close()
    
    logger.info("\n✅ TEST 1 TERMINÉ\n")
    return True


def test_vector_store_search():
    """Test 2: Vérifier VectorStore.search() avec différents formats"""
    logger.info("="*80)
    logger.info("🧪 TEST 2: VectorStore Search Formats")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.services.oss_classifier import OSSClassifierClient
    
    vector_store = VectorStore(index_path=Path("./data/indexes/faiss/vector_store.index"))
    vector_store.initialize()
    
    oss_client = OSSClassifierClient()
    
    test_query = "consulter tableau de bord"
    embedding = oss_client.generate_embeddings(test_query)
    
    logger.info(f"\n📝 Query: '{test_query}'")
    logger.info(f"📊 Embedding info:")
    logger.info(f"   • Type before conversion: {type(embedding)}")
    logger.info(f"   • Len: {len(embedding) if embedding else 'None'}")
    
    # Test 1: Embedding as-is (list)
    logger.info("\n🔍 Test 1: Search with embedding as list")
    try:
        distances1, metadata1 = vector_store.search(embedding, k=5)
        logger.info(f"   ✅ Success: {len(distances1)} results")
        if distances1:
            logger.info(f"   • First distance: {distances1[0]}")
            logger.info(f"   • First name: {metadata1[0].get('name', 'N/A')}")
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
    
    # Test 2: Embedding as numpy array (float32)
    logger.info("\n🔍 Test 2: Search with numpy.float32 array")
    try:
        embedding_np32 = np.array(embedding, dtype=np.float32)
        logger.info(f"   • Type: {type(embedding_np32)}")
        logger.info(f"   • Dtype: {embedding_np32.dtype}")
        logger.info(f"   • Shape: {embedding_np32.shape}")
        
        distances2, metadata2 = vector_store.search(embedding_np32, k=5)
        logger.info(f"   ✅ Success: {len(distances2)} results")
        if distances2:
            logger.info(f"   • First distance: {distances2[0]}")
            logger.info(f"   • First name: {metadata2[0].get('name', 'N/A')}")
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
    
    # Test 3: Embedding as numpy array (float64)
    logger.info("\n🔍 Test 3: Search with numpy.float64 array")
    try:
        embedding_np64 = np.array(embedding, dtype=np.float64)
        logger.info(f"   • Type: {type(embedding_np64)}")
        logger.info(f"   • Dtype: {embedding_np64.dtype}")
        logger.info(f"   • Shape: {embedding_np64.shape}")
        
        distances3, metadata3 = vector_store.search(embedding_np64, k=5)
        logger.info(f"   ✅ Success: {len(distances3)} results")
        if distances3:
            logger.info(f"   • First distance: {distances3[0]}")
            logger.info(f"   • First name: {metadata3[0].get('name', 'N/A')}")
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
    
    # Test 4: Avec reshape si nécessaire
    logger.info("\n🔍 Test 4: Search with reshaped array")
    try:
        embedding_reshaped = np.array(embedding, dtype=np.float32).reshape(1, -1)[0]
        logger.info(f"   • Type: {type(embedding_reshaped)}")
        logger.info(f"   • Dtype: {embedding_reshaped.dtype}")
        logger.info(f"   • Shape: {embedding_reshaped.shape}")
        
        distances4, metadata4 = vector_store.search(embedding_reshaped, k=5)
        logger.info(f"   ✅ Success: {len(distances4)} results")
        if distances4:
            logger.info(f"   • First distance: {distances4[0]}")
            logger.info(f"   • First name: {metadata4[0].get('name', 'N/A')}")
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
    
    oss_client.close()
    
    logger.info("\n✅ TEST 2 TERMINÉ\n")
    return True


def test_main_pipeline_embedder():
    """Test 3: Vérifier l'embedder utilisé dans main_pipeline"""
    logger.info("="*80)
    logger.info("🧪 TEST 3: Main Pipeline Embedder Wrapper")
    logger.info("="*80)
    
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.services.embedder_wrapper import EmbedderWrapper
    
    oss_client = OSSClassifierClient()
    
    logger.info("\n🔧 Creating EmbedderWrapper...")
    embedder_wrapper = EmbedderWrapper(oss_client=oss_client)
    
    test_query = "consulter tableau de bord"
    logger.info(f"\n📝 Query: '{test_query}'")
    
    # Test encode
    logger.info("\n🔍 Testing embedder_wrapper.encode()...")
    try:
        embedding = embedder_wrapper.encode(test_query)
        
        logger.info(f"   ✅ Encoding successful")
        logger.info(f"   • Type: {type(embedding)}")
        logger.info(f"   • Shape: {embedding.shape if hasattr(embedding, 'shape') else 'N/A'}")
        logger.info(f"   • Dtype: {embedding.dtype if hasattr(embedding, 'dtype') else 'N/A'}")
        logger.info(f"   • Norm: {np.linalg.norm(embedding):.4f}")
        logger.info(f"   • First 5: {embedding[:5] if hasattr(embedding, '__getitem__') else 'N/A'}")
        
        # Vérifier si None ou vide
        if embedding is None:
            logger.error("   ❌ Embedding is None!")
        elif hasattr(embedding, '__len__') and len(embedding) == 0:
            logger.error("   ❌ Embedding is empty!")
        
        # Test avec VectorStore
        logger.info("\n🔍 Testing with VectorStore.search()...")
        from context_weaver.data.vector_store import VectorStore
        
        vector_store = VectorStore(index_path=Path("./data/indexes/faiss/vector_store.index"))
        vector_store.initialize()
        
        distances, metadata = vector_store.search(embedding, k=5)
        
        logger.info(f"   ✅ Search successful: {len(distances)} results")
        if distances:
            logger.info(f"   • First distance: {distances[0]}")
            logger.info(f"   • First result: {metadata[0].get('name', 'N/A')}")
        else:
            logger.error("   ❌ No results returned!")
        
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    oss_client.close()
    
    logger.info("\n✅ TEST 3 TERMINÉ\n")
    return True


def test_retriever_direct_call():
    """Test 4: Appeler directement TaxonomyRetriever comme dans main_pipeline"""
    logger.info("="*80)
    logger.info("🧪 TEST 4: Direct TaxonomyRetriever Call (Main Pipeline Style)")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.services.embedder_wrapper import EmbedderWrapper
    from context_weaver.taxonomy.taxonomy_retriever import TaxonomyRetriever, RetrievalConfig
    
    # Setup exactly as main_pipeline
    vector_store = VectorStore(index_path=Path("./data/indexes/faiss/vector_store.index"))
    vector_store.initialize()
    
    oss_client = OSSClassifierClient()
    embedder_wrapper = EmbedderWrapper(oss_client=oss_client)
    
    config = RetrievalConfig(
        dense_top_k=50,
        bm25_top_k=100,
        final_top_n=30
    )
    
    retriever = TaxonomyRetriever(
        vector_store=vector_store,
        embedder=embedder_wrapper,
        config=config
    )
    
    test_query = "consulter tableau de bord"
    context = {'domain': 'unknown', 'task': 'unknown'}
    
    logger.info(f"\n📝 Query: '{test_query}'")
    logger.info(f"📊 Context: {context}")
    logger.info(f"⚙️  Config: dense_k={config.dense_top_k}, bm25_k={config.bm25_top_k}")
    
    logger.info("\n🔍 Calling retriever.retrieve()...")
    
    try:
        result = retriever.retrieve(
            query_text=test_query,
            context=context
        )
        
        logger.info(f"\n📊 Results:")
        logger.info(f"   • Total candidates: {result.total_retrieved}")
        logger.info(f"   • Dense count: {result.dense_count}")
        logger.info(f"   • BM25 count: {result.bm25_count}")
        logger.info(f"   • Final top N: {len(result.candidates)}")
        logger.info(f"   • Dense top score: {result.dense_top_score:.4f}")
        logger.info(f"   • BM25 top score: {result.bm25_top_score:.4f}")
        logger.info(f"   • RRF top score: {result.rrf_top_score:.4f}")
        
        if result.dense_count == 0:
            logger.error("\n❌ PROBLÈME IDENTIFIÉ: Dense count = 0")
            logger.error("   Le retriever ne retourne aucun résultat dense!")
        
        if result.candidates:
            logger.info(f"\n🏆 Top 3:")
            for i, c in enumerate(result.candidates[:3], 1):
                logger.info(f"   {i}. {c.name}")
                logger.info(f"      • RRF: {c.rrf_score:.4f}")
                logger.info(f"      • Dense: {c.dense_score:.4f} (rank={c.dense_rank})")
                logger.info(f"      • BM25: {c.bm25_score:.4f} (rank={c.bm25_rank})")
        
    except Exception as e:
        logger.error(f"❌ Retrieval failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    oss_client.close()
    
    logger.info("\n✅ TEST 4 TERMINÉ\n")
    return True


def main():
    """Exécute tous les tests de diagnostic"""
    
    print("\n" + "="*80)
    print("🔍 DIAGNOSTIC: Main Pipeline vs RRF Pipeline")
    print("="*80 + "\n")
    
    tests = [
        ("EmbedderAdapter vs OSS Direct", test_embedder_adapter),
        ("VectorStore Search Formats", test_vector_store_search),
        ("Main Pipeline Embedder Wrapper", test_main_pipeline_embedder),
        ("Direct TaxonomyRetriever Call", test_retriever_direct_call)
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
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
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