#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test rapide de la synchronisation corrigée
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


def test_sync():
    """
    Test de synchronisation avec la version corrigée
    """
    print("\n" + "=" * 80)
    print("🧪 TEST SYNCHRONISATION CORRIGÉE")
    print("=" * 80)
    
    try:
        # 1. Connexion Dgraph
        logger.info("1️⃣  Connexion Dgraph...")
        from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
        
        dgraph = TaxonomyDgraphConnector()
        
        if not dgraph.client:
            logger.error("❌ Dgraph non accessible")
            return False
        
        logger.info("✅ Dgraph connecté")
        
        # 2. Initialiser services
        logger.info("\n2️⃣  Initialisation services...")
        
        from context_weaver.data.vector_store import VectorStore
        from context_weaver.services.embedding_search import EmbeddingSearch
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        vector_store = VectorStore()
        vector_store.initialize()
        
        embedding_search = EmbeddingSearch()
        oss_client = OSSClassifierClient()
        
        logger.info("✅ Services initialisés")
        
        # 3. Créer le synchroniseur avec la version corrigée
        logger.info("\n3️⃣  Création synchroniseur...")
        
        # Importer la version corrigée
        from context_weaver.data.dgraph_vector_sync import DgraphVectorSync
        
        syncer = DgraphVectorSync(
            dgraph,
            vector_store,
            embedding_search,
            oss_client
        )
        
        logger.info("✅ Synchroniseur créé")
        
        # 4. Lancer la synchronisation
        logger.info("\n4️⃣  Synchronisation...")
        
        success = syncer.full_sync("Macompta.fr")
        
        if success:
            logger.info("\n✅ SYNCHRONISATION RÉUSSIE")
            
            # 5. Vérifier le résultat
            stats = syncer.get_sync_status()
            logger.info(f"\n📊 Statistiques:")
            logger.info(f"   • Documents: {stats['indexed_count']}")
            logger.info(f"   • Vecteurs: {stats['vector_store_count']}")
            
            # 6. Test de recherche
            logger.info("\n5️⃣  Test de recherche...")
            
            test_embeddings = oss_client.generate_embeddings("comptabilité")
            results = embedding_search.search_with_embeddings(
                embeddings=test_embeddings,
                top_k=5
            )
            
            logger.info(f"✅ {len(results)} résultats trouvés")
            
            if results:
                logger.info("\n📋 Top 3:")
                for i, r in enumerate(results[:3], 1):
                    logger.info(f"   {i}. {r.name} (score: {r.score:.3f})")
            
            return True
        else:
            logger.error("❌ Synchronisation échouée")
            return False
        
    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == '__main__':
    success = test_sync()
    
    if success:
        print("\n" + "=" * 80)
        print("✅ TEST RÉUSSI")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("❌ TEST ÉCHOUÉ")
        print("=" * 80)
        sys.exit(1)