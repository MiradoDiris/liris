#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 INSERTION DIRECTE DGRAPH → CHROMADB (FIXED)
Contourne FAISS complètement
✅ Fix: Utilise la bonne méthode pour construire l'index BM25
"""

import logging
import json
import sys
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
import pickle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


def index_directly_to_chromadb(
    documents: List[Dict[str, Any]],
    oss_client,
    chroma_path: Path
) -> bool:
    """
    Indexation directe dans ChromaDB sans passer par FAISS
    """
    try:
        logger.info("="*80)
        logger.info("📦 INDEXATION DIRECTE CHROMADB")
        logger.info("="*80)
        
        # 1. Importer ChromaDB
        from context_weaver.data.vector_store_chroma import VectorStore
        
        # 2. Créer/charger VectorStore
        logger.info(f"\n📂 Initialisation ChromaDB: {chroma_path}")
        vector_store = VectorStore(persist_path=chroma_path)
        vector_store.initialize()
        
        # 3. Vider si déjà des données
        if vector_store.get_document_count() > 0:
            logger.warning(f"⚠️  {vector_store.get_document_count()} docs existants")
            choice = input("Vider la collection ? (oui/non): ").strip().lower()
            if choice in ['oui', 'yes', 'o', 'y']:
                vector_store.reset()
                vector_store.initialize()
                logger.info("✅ Collection vidée et réinitialisée")
        
        # 4. Générer embeddings + préparer données
        logger.info(f"\n🧮 Génération embeddings pour {len(documents)} documents...")
        
        embeddings_list = []
        ids_list = []
        metadata_list = []
        
        batch_size = 10
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(documents))
            batch = documents[start_idx:end_idx]
            
            for doc in batch:
                # Générer embedding
                embedding = oss_client.generate_embeddings(doc['content'])
                
                if embedding is not None and len(embedding) > 0:
                    embeddings_list.append(np.array(embedding))
                    
                    # ID unique
                    doc_id = doc.get('id') or doc.get('taxon_id') or f"doc_{len(ids_list)}"
                    ids_list.append(doc_id)
                    
                    # Métadonnées aplaties (ChromaDB compatible)
                    # ✅ CRITIQUE: ChromaDB refuse None, remplacer par valeurs par défaut
                    meta = {
                        'id': str(doc.get('id') or ''),
                        'taxon_id': str(doc.get('taxon_id') or ''),
                        'name': str(doc.get('name') or 'Unknown'),
                        'domain': str(doc.get('domain') or 'Unknown'),
                        'type': str(doc.get('type') or 'Unknown'),
                        'breadcrumb': str(doc.get('breadcrumb') or ''),
                        'depth': int(doc.get('depth') or 0),
                        'parent_id': str(doc.get('parent_id') or ''),
                        'parent_name': str(doc.get('parent_name') or ''),
                        'category': str(doc.get('category') or 'default'),
                        'children_count': int(doc.get('children_count') or 0),
                    }
                    
                    # ✅ Validation finale: supprimer les clés avec None
                    meta = {k: v for k, v in meta.items() if v is not None}
                    
                    metadata_list.append(meta)
            
            logger.info(f"   Batch {batch_idx+1}/{total_batches}: {len(embeddings_list)} embeddings")
        
        logger.info(f"\n✅ {len(embeddings_list)} embeddings générés")
        
        # 5. Convertir en numpy array
        embeddings_array = np.array(embeddings_list).astype('float32')
        
        logger.info(f"\n📊 Dimensions:")
        logger.info(f"   • Embeddings: {embeddings_array.shape}")
        logger.info(f"   • Métadonnées: {len(metadata_list)}")
        logger.info(f"   • IDs: {len(ids_list)}")
        
        # 6. Insertion dans ChromaDB
        logger.info(f"\n💾 Insertion dans ChromaDB...")
        
        vector_store.add_vectors(
            vectors=embeddings_array,
            metadata_list=metadata_list,
            ids=ids_list
        )
        
        # 7. ✅ FIX: Construire BM25 manuellement
        logger.info(f"\n🔧 Construction index BM25...")
        try:
            import rank_bm25
            
            # Préparer les textes pour BM25
            texts = []
            for doc in documents:
                content = doc.get('content', '') or doc.get('text', '')
                if content:
                    texts.append(content.lower().split())
                else:
                    texts.append([])
            
            # Créer l'index BM25
            vector_store.bm25_index = rank_bm25.BM25Okapi(texts)
            vector_store.bm25_ids = ids_list
            vector_store.bm25_available = True
            
            # Sauvegarder l'index
            bm25_data = {
                'index': vector_store.bm25_index,
                'ids': vector_store.bm25_ids
            }
            
            with open(vector_store.bm25_path, 'wb') as f:
                pickle.dump(bm25_data, f)
            
            logger.info(f"✅ Index BM25 créé: {len(ids_list)} documents")
            
        except ImportError:
            logger.warning("⚠️ rank_bm25 non installé - BM25 désactivé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur création BM25: {e}")
            logger.warning("   → Continuant sans BM25")
        
        # 8. Stats finales
        stats = vector_store.get_stats()
        
        logger.info("\n" + "="*80)
        logger.info("✅ INDEXATION RÉUSSIE")
        logger.info("="*80)
        logger.info(f"   • Total documents: {stats['num_vectors']}")
        logger.info(f"   • Dimension: {stats['dimension']}")
        logger.info(f"   • BM25 disponible: {stats['bm25_available']}")
        logger.info(f"   • Cache size: {stats['cache_size']}")
        logger.info(f"   • Chemin: {chroma_path}")
        logger.info("="*80 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Erreur indexation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Point d'entrée principal"""
    
    print("\n" + "="*80)
    print("🚀 INDEXATION DIRECTE DGRAPH → CHROMADB (FIXED)")
    print("="*80 + "\n")
    
    print("Cette méthode:")
    print("  ✅ Évite les problèmes de conversion FAISS/ChromaDB")
    print("  ✅ Utilise ChromaDB nativement")
    print("  ✅ Garde la métrique L2 cohérente")
    print("  ✅ Construit correctement l'index BM25")
    print()
    
    choice = input("Continuer ? (oui/non): ").strip().lower()
    
    if choice not in ['oui', 'yes', 'o', 'y']:
        print("\n❌ Annulé")
        return 0
    
    try:
        # Ajouter paths
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
        sys.path.insert(0, str(project_root))
        
        # 1. Connexions
        from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        logger.info("🔌 Connexion Dgraph...")
        dgraph_connector = TaxonomyDgraphConnector()
        
        if not dgraph_connector.client:
            logger.error("❌ Connexion Dgraph échouée")
            return 1
        
        logger.info("🔌 Connexion OSS Client...")
        oss_client = OSSClassifierClient()
        
        # 2. Extraction Dgraph
        from script_config.reindex_vector_store_hierarchical import DgraphFullExtractor
        
        extractor = DgraphFullExtractor(dgraph_connector)
        documents = extractor.extract_all_projects()
        
        if not documents:
            logger.error("❌ Aucun document extrait")
            dgraph_connector.close()
            return 1
        
        # 3. Indexation directe ChromaDB
        chroma_path = Path("./data/indexes/chroma")
        
        success = index_directly_to_chromadb(
            documents,
            oss_client,
            chroma_path
        )
        
        # 4. Fermer connexions
        dgraph_connector.close()
        oss_client.close()
        
        if success:
            print("\n" + "="*80)
            print("✅ SUCCÈS - ChromaDB prêt")
            print("="*80 + "\n")
            print("📝 Prochaines étapes:")
            print("   1. Tester: python script_config/test_chroma_migration.py")
            print("   2. Les scores devraient maintenant être cohérents")
            print()
            return 0
        else:
            print("\n❌ ÉCHEC de l'indexation")
            return 1
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interruption utilisateur")
        return 130
    
    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())