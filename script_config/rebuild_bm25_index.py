#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Reconstruction de l'index BM25
Sans réinsérer les données - utilise le vector store existant
"""

import sys
import logging
from pathlib import Path

# Setup paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


def rebuild_bm25_index():
    """
    Reconstruit l'index BM25 à partir du vector store existant
    
    ✅ Pas besoin de réindexer - utilise les métadonnées déjà présentes
    """
    
    logger.info("="*80)
    logger.info("🔧 RECONSTRUCTION INDEX BM25")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    
    vector_store_path = Path("./data/indexes/faiss/vector_store.index")
    
    if not vector_store_path.exists():
        logger.error(f"❌ Vector store non trouvé: {vector_store_path}")
        logger.error("   Veuillez d'abord réindexer avec: python script_config/reindex_vector_store_hierarchical.py")
        return 1
    
    # 1. Charger le vector store existant
    logger.info("\n📂 Chargement du vector store existant...")
    vector_store = VectorStore(index_path=vector_store_path)
    vector_store.initialize()
    
    stats = vector_store.get_stats()
    logger.info(f"   • Vecteurs: {stats['num_vectors']}")
    logger.info(f"   • Metadata: {stats['num_metadata']}")
    logger.info(f"   • BM25 déjà disponible: {stats['bm25_available']}")
    
    if stats['num_vectors'] == 0:
        logger.error("❌ Vector store vide - rien à indexer")
        return 1
    
    # 2. Vérifier rank-bm25
    try:
        import rank_bm25
        logger.info("\n✅ rank-bm25 installé")
    except ImportError:
        logger.error("\n❌ rank-bm25 non installé")
        logger.error("   Installer avec: pip install rank-bm25")
        return 1
    
    # 3. Construire l'index BM25
    logger.info("\n🔨 Construction de l'index BM25...")
    logger.info(f"   Source: {stats['num_metadata']} documents")
    
    try:
        vector_store.build_bm25_index()
        
        # Vérifier le résultat
        new_stats = vector_store.get_stats()
        
        if new_stats['bm25_available']:
            logger.info(f"\n✅ Index BM25 créé avec succès!")
            logger.info(f"   • Corpus size: {new_stats['bm25_corpus_size']} documents")
            logger.info(f"   • Fichier: {vector_store.bm25_path}")
        else:
            logger.error("\n❌ Échec de la création de l'index BM25")
            return 1
    
    except Exception as e:
        logger.error(f"\n❌ Erreur lors de la construction BM25: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    
    logger.info("\n" + "="*80)
    logger.info("✅ RECONSTRUCTION TERMINÉE")
    logger.info("="*80)
    
    return 0


def test_bm25_search():
    """Test rapide de l'index BM25"""
    
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST BM25")
    logger.info("="*80)
    
    from context_weaver.data.vector_store import VectorStore
    
    vector_store = VectorStore()
    vector_store.initialize()
    
    if not vector_store.bm25_available:
        logger.warning("⚠️ BM25 non disponible - impossible de tester")
        return
    
    # Test queries
    test_queries = [
        "tableau de bord",
        "créer facture",
        "compte bancaire",
        "trésorerie"
    ]
    
    logger.info(f"\n🔍 Test de {len(test_queries)} queries:\n")
    
    for query in test_queries:
        logger.info(f"Query: '{query}'")
        
        try:
            scores, metadata = vector_store.bm25_search(query, top_k=3)
            
            if scores:
                logger.info(f"   Résultats: {len(scores)}")
                for i, (score, meta) in enumerate(zip(scores, metadata), 1):
                    logger.info(f"      {i}. {meta.get('name', 'N/A')} (score={score:.4f})")
            else:
                logger.warning(f"   Aucun résultat")
        
        except Exception as e:
            logger.error(f"   ❌ Erreur: {e}")
        
        logger.info("")
    
    logger.info("✅ Test BM25 terminé\n")


def main():
    """Point d'entrée"""
    
    print("\n" + "="*80)
    print("🔧 RECONSTRUCTION INDEX BM25")
    print("="*80)
    print("\nCe script va:")
    print("  1. Charger le vector store existant")
    print("  2. Construire l'index BM25 depuis les métadonnées")
    print("  3. Sauvegarder l'index BM25")
    print("  4. Tester avec quelques queries")
    print("\n⚠️  Prérequis: rank-bm25 doit être installé (pip install rank-bm25)")
    
    choice = input("\nContinuer ? (oui/non): ").strip().lower()
    
    if choice not in ['oui', 'yes', 'o', 'y']:
        print("\n❌ Annulé")
        return 0
    
    # Reconstruction
    result = rebuild_bm25_index()
    
    if result == 0:
        # Test
        test_bm25_search()
        
        print("\n" + "="*80)
        print("✅ SUCCÈS - Index BM25 prêt à l'emploi")
        print("="*80)
        print("\nFichiers créés:")
        print("  • data/indexes/faiss/bm25_index.pkl")
        print("\nVous pouvez maintenant utiliser:")
        print("  • vector_store.bm25_search(query, top_k=10)")
        print("  • TaxonomyRetriever avec RRF (Dense + BM25)")
        print("")
    
    return result


if __name__ == "__main__":
    sys.exit(main())