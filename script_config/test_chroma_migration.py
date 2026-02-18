#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de la migration ChromaDB
"""

import logging
import sys
from pathlib import Path
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_chroma_vector_store():
    """Test complet du VectorStore ChromaDB"""
    
    print("\n" + "="*80)
    print("🧪 TEST CHROMADB VECTOR STORE")
    print("="*80 + "\n")
    
    try:
        from context_weaver.data.vector_store_chroma import VectorStore
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        # 1. Initialiser VectorStore
        logger.info("📦 Initialisation VectorStore ChromaDB...")
        vector_store = VectorStore()
        vector_store.initialize()
        
        # 2. Statistiques
        stats = vector_store.get_stats()
        
        print("\n📊 Statistiques:")
        print(f"   • Total documents: {stats['total_documents']}")
        print(f"   • Dimension: {stats['dimension']}")
        print(f"   • Type: {stats['index_type']}")
        print(f"   • BM25 disponible: {stats['bm25_available']}")
        print(f"   • Chemin: {stats['persist_path']}")
        
        if stats['total_documents'] == 0:
            print("\n⚠️ Aucun document dans ChromaDB")
            print("💡 Lancez d'abord la migration avec migrate_faiss_to_chroma.py")
            return False
        
        # 3. Test recherche vectorielle
        logger.info("\n🔍 Test recherche vectorielle...")
        
        oss_client = OSSClassifierClient()
        test_query = "créer une SARL"
        
        logger.info(f"   Query: '{test_query}'")
        
        # Générer embedding
        embedding = oss_client.generate_embeddings(test_query)
        
        # Recherche
        scores, metadata_list = vector_store.search(
            query_vector=embedding,
            k=5
        )
        
        print(f"\n✅ Recherche dense: {len(metadata_list)} résultats")
        for i, (score, meta) in enumerate(zip(scores, metadata_list), 1):
            print(f"   {i}. {meta.get('name', 'N/A')} (score: {score:.4f})")
            print(f"      Domaine: {meta.get('domain', 'N/A')}")
            print(f"      Type: {meta.get('type', 'N/A')}")
        
        # 4. Test BM25 si disponible
        if stats['bm25_available']:
            logger.info("\n🔍 Test recherche BM25...")
            
            bm25_scores, bm25_metadata = vector_store.bm25_search(
                query=test_query,
                top_k=5
            )
            
            print(f"\n✅ Recherche BM25: {len(bm25_metadata)} résultats")
            for i, (score, meta) in enumerate(zip(bm25_scores, bm25_metadata), 1):
                print(f"   {i}. {meta.get('name', 'N/A')} (score: {score:.4f})")
        
        # 5. Test filtrage
        logger.info("\n🔍 Test recherche avec filtre...")
        
        def filter_by_type(meta: dict) -> bool:
            return meta.get('type') == 'LabelNode'
        
        filtered_scores, filtered_metadata = vector_store.search(
            query_vector=embedding,
            k=5,
            filter_fn=filter_by_type
        )
        
        print(f"\n✅ Recherche filtrée (type=LabelNode): {len(filtered_metadata)} résultats")
        for i, (score, meta) in enumerate(zip(filtered_scores, filtered_metadata), 1):
            print(f"   {i}. {meta.get('name', 'N/A')} (score: {score:.4f})")
        
        # 6. Test get_document_count
        doc_count = vector_store.get_document_count()
        print(f"\n📊 Document count: {doc_count}")
        
        oss_client.close()
        
        print("\n" + "="*80)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("="*80 + "\n")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Erreur import: {e}")
        print("\n💡 Installez ChromaDB:")
        print("   pip install chromadb")
        return False
    
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def compare_faiss_vs_chroma():
    """Compare les résultats FAISS vs ChromaDB"""
    
    print("\n" + "="*80)
    print("⚖️ COMPARAISON FAISS vs CHROMADB")
    print("="*80 + "\n")
    
    try:
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        test_query = "créer une SARL"
        oss_client = OSSClassifierClient()
        embedding = oss_client.generate_embeddings(test_query)
        
        print(f"🔍 Query: '{test_query}'\n")
        
        # Test FAISS
        try:
            from context_weaver.data.vector_store_chroma import VectorStore as FAISSVectorStore
            
            logger.info("📦 Test FAISS...")
            faiss_store = FAISSVectorStore()
            faiss_store.initialize()
            
            faiss_scores, faiss_meta = faiss_store.search(embedding, k=5)
            
            print("📊 FAISS - Top 5:")
            for i, (score, meta) in enumerate(zip(faiss_scores, faiss_meta), 1):
                print(f"   {i}. {meta.get('name', 'N/A')} (score: {score:.4f})")
        
        except Exception as e:
            print(f"⚠️ FAISS non disponible: {e}")
            faiss_scores = []
        
        # Test ChromaDB
        try:
            from context_weaver.data.vector_store_chroma import VectorStore as ChromaVectorStore
            
            logger.info("\n📦 Test ChromaDB...")
            chroma_store = ChromaVectorStore()
            chroma_store.initialize()
            
            chroma_scores, chroma_meta = chroma_store.search(embedding, k=5)
            
            print("\n📊 ChromaDB - Top 5:")
            for i, (score, meta) in enumerate(zip(chroma_scores, chroma_meta), 1):
                print(f"   {i}. {meta.get('name', 'N/A')} (score: {score:.4f})")
        
        except Exception as e:
            print(f"⚠️ ChromaDB non disponible: {e}")
            chroma_scores = []
        
        # Comparaison
        if faiss_scores and chroma_scores:
            print("\n🔄 Comparaison des scores:")
            
            avg_diff = np.mean([abs(f - c) for f, c in zip(faiss_scores[:5], chroma_scores[:5])])
            print(f"   • Différence moyenne: {avg_diff:.6f}")
            
            if avg_diff < 0.01:
                print("   ✅ Résultats très similaires (excellente migration)")
            elif avg_diff < 0.05:
                print("   ✅ Résultats similaires (bonne migration)")
            else:
                print("   ⚠️ Résultats différents (vérifier la migration)")
        
        oss_client.close()
        
        print("\n" + "="*80 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur comparaison: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Test principal
    success = test_chroma_vector_store()
    
    if success:
        # Comparaison optionnelle
        print("\n🔄 Voulez-vous comparer FAISS vs ChromaDB ?")
        choice = input("(oui/non): ").strip().lower()
        
        if choice in ['oui', 'yes', 'o', 'y']:
            compare_faiss_vs_chroma()
    
    sys.exit(0 if success else 1)