#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
✅ Vérification rapide que tout est prêt pour la pipeline RRF
"""

import sys
import logging
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Vérifie que tout est prêt"""
    
    print("\n" + "="*80)
    print("✅ VÉRIFICATION PIPELINE RRF")
    print("="*80 + "\n")
    
    checks = []
    
    # Check 1: Vector store FAISS
    print("1. Vector store FAISS...")
    from context_weaver.data.vector_store import VectorStore
    
    vs = VectorStore()
    vs.initialize()
    stats = vs.get_stats()
    
    if stats['num_vectors'] > 0:
        print(f"   ✅ {stats['num_vectors']} vecteurs chargés")
        checks.append(True)
    else:
        print(f"   ❌ Vector store vide")
        checks.append(False)
    
    # Check 2: BM25
    print("\n2. Index BM25...")
    if stats['bm25_available']:
        print(f"   ✅ BM25 disponible ({stats['bm25_corpus_size']} documents)")
        checks.append(True)
    else:
        print(f"   ❌ BM25 non disponible")
        checks.append(False)
    
    # Check 3: OSS Client
    print("\n3. OSS Classifier Client...")
    try:
        from context_weaver.services.oss_classifier import OSSClassifierClient
        import numpy as np
        
        oss_client = OSSClassifierClient()
        
        # Test embedding
        test_embedding = oss_client.generate_embeddings("test")
        
        # Convertir en array si nécessaire
        if not isinstance(test_embedding, np.ndarray):
            test_embedding = np.array(test_embedding)
        
        # Vérifier la dimension
        if test_embedding is not None and len(test_embedding) == 768:
            print(f"   ✅ OSS Client opérationnel (dim=768)")
            checks.append(True)
        else:
            print(f"   ❌ OSS Client ne génère pas d'embeddings valides")
            checks.append(False)
        
        oss_client.close()
    except Exception as e:
        print(f"   ❌ OSS Client error: {e}")
        import traceback
        traceback.print_exc()
        checks.append(False)
    
    # Check 4: TaxonomyRetriever
    print("\n4. TaxonomyRetriever...")
    try:
        from context_weaver.taxonomy.taxonomy_retriever import TaxonomyRetriever
        print(f"   ✅ TaxonomyRetriever importable")
        checks.append(True)
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        checks.append(False)
    
    # Check 5: TaxonomyPipeline
    print("\n5. TaxonomyPipeline...")
    try:
        from context_weaver.pipeline.taxonomy_pipeline import TaxonomyPipeline
        print(f"   ✅ TaxonomyPipeline importable")
        checks.append(True)
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        checks.append(False)
    
    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ")
    print("="*80)
    
    passed = sum(checks)
    total = len(checks)
    
    print(f"\nChecks passés: {passed}/{total}")
    
    if all(checks):
        print("\n✅ TOUT EST PRÊT!")
        print("\nVous pouvez maintenant:")
        print("  • Lancer les tests: python script_config/test_rrf_pipeline.py")
        print("  • Utiliser TaxonomyPipeline dans votre code")
        return 0
    else:
        print("\n⚠️ CERTAINS CHECKS ONT ÉCHOUÉ")
        print("\nActions à prendre:")
        if not checks[0]:
            print("  • Réindexer: python script_config/reindex_vector_store_hierarchical.py")
        if not checks[1]:
            print("  • Reconstruire BM25: python script_config/rebuild_bm25_index.py")
        if not checks[2]:
            print("  • Vérifier que le service OSS Classifier est running sur le port 8085")
        return 1


if __name__ == "__main__":
    sys.exit(main())