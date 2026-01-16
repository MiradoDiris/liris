#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Indexation complète Context Weaver - Version Refactorisée
✅ Utilise VectorStore unifié (BM25 + Dense intégrés)
Phase 1 : Taxonomy Projection (Hierarchy + Prerequisites)
"""

import sys
import logging
from pathlib import Path
import numpy as np
from typing import List, Dict, Any

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)

# Ajout du chemin racine
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.dataset_database import DatasetDatabase
from context_weaver.data.vector_store import VectorStore  # ✅ REFACTORISÉ
from context_weaver.services.oss_classifier import OSSClassifierClient


def build_hierarchy_map(database: DatasetDatabase) -> Dict[str, Dict]:
    """
    Récupère tous les taxons et construit une map pour calculer les breadcrumbs.
    """
    logger.info("🌳 Construction de la map hiérarchique...")
    
    try:
        # Récupération des taxons depuis la database
        nodes = database.get_all_taxons()
        logger.info(f"   ✅ {len(nodes)} taxons récupérés")
        return {node['id']: node for node in nodes}
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération taxons: {e}")
        return {}


def get_breadcrumb(node_id: str, hierarchy_map: Dict) -> str:
    """
    Génère la chaîne 'Parent > Enfant' pour un nœud donné.
    """
    path = []
    current_id = hierarchy_map.get(node_id, {}).get('parent_id')
    
    # Limiter la profondeur pour éviter les boucles infinies
    max_depth = 10
    depth = 0
    
    while current_id and current_id in hierarchy_map and depth < max_depth:
        parent = hierarchy_map[current_id]
        path.insert(0, parent['name'])
        current_id = parent.get('parent_id')
        depth += 1
        
    return " > ".join(path) if path else ""


def prepare_densified_documents(hierarchy_map: Dict) -> List[Dict]:
    """
    Transforme les nœuds bruts en documents enrichis pour l'indexation.
    
    ✅ Format compatible avec VectorStore (TaxonDoc)
    """
    logger.info(f"📄 Préparation de {len(hierarchy_map)} documents densifiés...")
    enriched_docs = []
    
    for node_id, node in hierarchy_map.items():
        breadcrumb = get_breadcrumb(node_id, hierarchy_map)
        
        # Densification du texte pour BM25 et Embeddings
        # On inclut le nom, la description et TOUTE la lignée hiérarchique
        full_text = f"{node['name']}. {node.get('description', '')}. "
        if breadcrumb:
            full_text += f"Contexte hiérarchique : {breadcrumb}."
        
        # Ajouter les prérequis comme hint (pour retrieval)
        prereq_hard = node.get('prereq_hard', [])
        if prereq_hard:
            prereq_names = [
                hierarchy_map.get(pid, {}).get('name', pid) 
                for pid in prereq_hard[:3]  # Max 3 pour ne pas surcharger
            ]
            prereq_names = [n for n in prereq_names if n]
            if prereq_names:
                full_text += f" Requis: {', '.join(prereq_names)}."
        
        # ✅ Format TaxonDoc pour VectorStore
        doc = {
            "taxon_id": node_id,
            "name": node['name'],
            "domain": node.get('domain', 'default'),
            "type": node.get('type', 'taxon'),
            "definition": node.get('description', ''),
            "index_text": full_text,  # ✅ Champ principal pour embedding
            
            # Metadata structurée
            "breadcrumb": breadcrumb,
            "depth": len(breadcrumb.split(' > ')) if breadcrumb else 0,
            "parent_ids": [node.get('parent_id')] if node.get('parent_id') else [],
            "path_ids": [],  # À calculer si besoin
            
            # Contraintes (pour Validator)
            "prereq_hard_ids": node.get('prereq_hard', []),
            "prereq_soft_ids": node.get('prereq_soft', []),
            "required_slots": node.get('required_slots', []),
            "incompatible_ids": node.get('incompatible', []),
            
            # Version
            "taxonomy_version": "1.1",
            "category": node.get('category', 'default')
        }
        
        enriched_docs.append(doc)
    
    logger.info(f"   ✅ {len(enriched_docs)} documents préparés")
    return enriched_docs


def run_indexing_pipeline():
    """
    Exécute le pipeline complet de synchronisation Dgraph -> VectorStore
    
    ✅ REFACTORISÉ: Utilise VectorStore unifié
    """
    logger.info("=" * 80)
    logger.info("🚀 DÉMARRAGE DE L'INDEXATION DENSIFIÉE")
    logger.info("=" * 80)
    
    # === 1. Initialisation des services ===
    logger.info("\n📦 Step 1/6: Initialisation des services")
    
    db = DatasetDatabase()
    vector_store = VectorStore()  # ✅ REFACTORISÉ: Un seul service
    oss_client = OSSClassifierClient()
    
    logger.info("   ✅ Services initialisés")

    try:
        # === 2. Extraction et Construction de la hiérarchie ===
        logger.info("\n🌳 Step 2/6: Extraction de la hiérarchie")
        hierarchy_map = build_hierarchy_map(db)
        
        if not hierarchy_map:
            logger.error("❌ Aucun taxon trouvé. Arrêt.")
            return
        
        # === 3. Préparation des documents ===
        logger.info("\n📄 Step 3/6: Préparation des documents")
        documents = prepare_densified_documents(hierarchy_map)
        
        if not documents:
            logger.error("❌ Aucun document préparé. Arrêt.")
            return

        # === 4. Génération des Embeddings via OSS 20B ===
        logger.info("\n🧠 Step 4/6: Génération des embeddings OSS 20B")
        texts_to_embed = [doc['index_text'] for doc in documents]
        
        # Traiter par batch de 10 pour la stabilité
        batch_size = 10
        all_embeddings = []
        
        logger.info(f"   • Total à traiter: {len(texts_to_embed)}")
        logger.info(f"   • Batch size: {batch_size}")
        
        for i in range(0, len(texts_to_embed), batch_size):
            batch = texts_to_embed[i:i+batch_size]
            
            try:
                embeddings = oss_client.generate_embeddings_batch(batch)
                all_embeddings.extend(embeddings)
                
                progress = len(all_embeddings)
                logger.info(f"   • Progress: {progress}/{len(texts_to_embed)} ({progress*100//len(texts_to_embed)}%)")
                
            except Exception as e:
                logger.error(f"   ❌ Erreur batch {i//batch_size + 1}: {e}")
                # Continuer avec des embeddings vides pour ce batch
                all_embeddings.extend([np.zeros(768)] * len(batch))
        
        logger.info(f"   ✅ {len(all_embeddings)} embeddings générés")

        # === 5. Indexation dans VectorStore ===
        logger.info("\n📦 Step 5/6: Indexation VectorStore (FAISS + BM25)")
        
        # Initialiser le vector store
        vector_store.initialize()
        
        # Ajouter les documents avec embeddings
        # ✅ VectorStore gère à la fois FAISS (dense) et BM25
        vector_store.bulk_insert(
            documents=documents,
            embeddings=np.array(all_embeddings).astype('float32')
        )
        
        logger.info("   ✅ Indexation FAISS terminée")
        logger.info("   ✅ Indexation BM25 terminée")
        
        # === 6. Sauvegarde ===
        logger.info("\n💾 Step 6/6: Sauvegarde des indexes")
        vector_store.save()
        logger.info("   ✅ Indexes sauvegardés")
        
        # === Statistiques finales ===
        logger.info("\n" + "=" * 80)
        logger.info("📊 STATISTIQUES FINALES")
        logger.info("=" * 80)
        
        stats = vector_store.get_stats()
        logger.info(f"   • Total documents: {stats.get('total_documents', 0)}")
        logger.info(f"   • Dimension: {stats.get('dimension', 0)}")
        logger.info(f"   • Index type: {stats.get('index_type', 'unknown')}")
        logger.info(f"   • BM25 disponible: {stats.get('bm25_available', False)}")
        logger.info(f"   • Structure: Hiérarchie + Prérequis intégrés")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ INDEXATION TERMINÉE AVEC SUCCÈS")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("💥 ERREUR CRITIQUE LORS DE L'INDEXATION")
        logger.error("=" * 80)
        logger.error(f"Erreur: {e}")
        
        import traceback
        logger.error("\nStack trace:")
        logger.error(traceback.format_exc())
        
    finally:
        logger.info("\n🔒 Fermeture des ressources...")
        db.close()
        oss_client.close()
        logger.info("   ✅ Ressources fermées")


def verify_indexing():
    """
    Vérifie que l'indexation s'est bien passée
    """
    logger.info("\n" + "=" * 80)
    logger.info("🔍 VÉRIFICATION DE L'INDEXATION")
    logger.info("=" * 80)
    
    try:
        vector_store = VectorStore()
        vector_store.initialize()
        
        stats = vector_store.get_stats()
        
        logger.info("\n📊 Statistiques:")
        logger.info(f"   • Documents: {stats.get('total_documents', 0)}")
        logger.info(f"   • Dimension: {stats.get('dimension', 0)}")
        logger.info(f"   • BM25: {stats.get('bm25_available', False)}")
        
        # Test de recherche
        logger.info("\n🔍 Test de recherche...")
        
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        oss_client = OSSClassifierClient()
        test_query = "créer une facture"
        
        # Générer embedding
        embedding = oss_client.generate_embeddings(test_query)
        
        # Recherche dense
        results = vector_store.search(
            query_vector=embedding,
            k=5
        )
        
        logger.info(f"   ✅ Recherche dense: {len(results[0]) if results else 0} résultats")
        
        # Recherche BM25
        if stats.get('bm25_available'):
            bm25_results = vector_store.bm25_search(
                query=test_query,
                top_k=5
            )
            logger.info(f"   ✅ Recherche BM25: {len(bm25_results[0]) if bm25_results else 0} résultats")
        
        oss_client.close()
        
        logger.info("\n✅ Vérification terminée - Indexation OK")
        
    except Exception as e:
        logger.error(f"\n❌ Erreur lors de la vérification: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Indexation Context Weaver")
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Vérifier l\'indexation existante au lieu de réindexer'
    )
    
    args = parser.parse_args()
    
    if args.verify:
        verify_indexing()
    else:
        run_indexing_pipeline()