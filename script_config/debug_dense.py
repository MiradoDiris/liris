#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Debug Dense Retrieval
🔍 Diagnostique pourquoi vector_store.search() retourne 0 résultats
"""

import logging
import numpy as np
from context_weaver.data.vector_store_chroma import VectorStore
from context_weaver.services.oss_classifier import OSSClassifierClient

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def debug_vector_store():
    """Debug complet du VectorStore et dense retrieval"""
    
    print("\n" + "="*80)
    print("🔍 DEBUG DENSE RETRIEVAL")
    print("="*80)
    
    # === 1. CHARGER VECTOR STORE ===
    print("\n📂 Step 1: Chargement VectorStore")
    vector_store = VectorStore()
    vector_store.initialize()
    
    print(f"✅ VectorStore chargé")
    
    # 🔧 FIX: Utiliser index.ntotal au lieu de len(index)
    if hasattr(vector_store, 'index') and vector_store.index is not None:
        try:
            num_vectors = vector_store.index.ntotal
            print(f"   • Nombre de vecteurs: {num_vectors}")
        except Exception as e:
            print(f"   ⚠️ Impossible de lire index.ntotal: {e}")
    
    # Vérifier qu'il y a des données
    if hasattr(vector_store, 'metadata'):
        print(f"   • Nombre de metadata: {len(vector_store.metadata)}")
        
        # Afficher les domaines disponibles
        domains = set()
        for meta in vector_store.metadata[:10]:
            domain = meta.get('domain', 'NO_DOMAIN')
            domains.add(domain)
        
        print(f"   • Domaines trouvés (échantillon): {domains}")
    
    # === 2. CRÉER EMBEDDER ===
    print("\n🧮 Step 2: Initialisation Embedder")
    oss_client = OSSClassifierClient()
    
    from context_weaver.services.embedder_wrapper import EmbedderWrapper
    embedder = EmbedderWrapper(oss_client=oss_client)
    
    # === 3. TESTER AVEC ET SANS FILTRE ===
    print("\n🔬 Step 3: Tests de recherche")
    
    test_query = "Tableau de bord comptabilité"
    
    print(f"\n🔍 Query: '{test_query}'")
    
    # Générer embedding
    print("   Génération embedding...")
    query_embedding = embedder.encode(test_query)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    print(f"   ✅ Embedding généré (dim={len(query_embedding)})")
    
    # TEST 1: Sans filtre
    print("\n📊 TEST 1: Recherche SANS FILTRE")
    try:
        result_no_filter = vector_store.search(
            query_vector=query_embedding,
            k=10
        )
        
        distances, metadata_list = result_no_filter
        print(f"   ✅ Résultats: {len(distances)} documents")
        
        if distances:
            print(f"   • Top 3 scores: {distances[:3]}")
            print(f"   • Top 3 noms:")
            for i, meta in enumerate(metadata_list[:3], 1):
                print(f"      {i}. {meta.get('name', 'Unknown')} (domain: {meta.get('domain', 'N/A')})")
        else:
            print("   ⚠️ Aucun résultat trouvé")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 2: Avec filtre "unknown"
    print("\n📊 TEST 2: Recherche avec filtre domain='unknown'")
    
    def filter_unknown(meta):
        return meta.get('domain') == 'unknown'
    
    try:
        result_filter_unknown = vector_store.search(
            query_vector=query_embedding,
            k=10,
            filter_fn=filter_unknown
        )
        
        distances, metadata_list = result_filter_unknown
        print(f"   ✅ Résultats: {len(distances)} documents")
        
        if distances:
            print(f"   • Top 3 scores: {distances[:3]}")
        else:
            print("   ⚠️ Aucun résultat (filtre trop restrictif?)")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # TEST 3: Avec filtre "Macompta.fr"
    print("\n📊 TEST 3: Recherche avec filtre domain='Macompta.fr'")
    
    def filter_macompta(meta):
        return meta.get('domain') == 'Macompta.fr'
    
    try:
        result_filter_macompta = vector_store.search(
            query_vector=query_embedding,
            k=10,
            filter_fn=filter_macompta
        )
        
        distances, metadata_list = result_filter_macompta
        print(f"   ✅ Résultats: {len(distances)} documents")
        
        if distances:
            print(f"   • Top 3 scores: {distances[:3]}")
            print(f"   • Top 3 noms:")
            for i, meta in enumerate(metadata_list[:3], 1):
                print(f"      {i}. {meta.get('name', 'Unknown')}")
        else:
            print("   ⚠️ Aucun résultat (filtre trop restrictif?)")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # === 4. VÉRIFIER LA DISTRIBUTION DES DOMAINES ===
    print("\n📊 Step 4: Distribution des domaines dans le VectorStore")
    
    if hasattr(vector_store, 'metadata'):
        domain_counts = {}
        for meta in vector_store.metadata:
            domain = meta.get('domain', 'NO_DOMAIN')
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        print(f"\n   Distribution:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
            print(f"      • {domain}: {count} documents")
    
    # === 5. CONCLUSION ===
    print("\n" + "="*80)
    print("📋 DIAGNOSTIC")
    print("="*80)
    
    if not distances:
        print("\n❌ PROBLÈME IDENTIFIÉ:")
        print("   Le VectorStore retourne 0 résultats même sans filtre.")
        print("\nCAUSES POSSIBLES:")
        print("   1. Les embeddings ne sont pas chargés correctement")
        print("   2. Le FAISS index est vide ou corrompu")
        print("   3. Problème de dimension des embeddings")
        print("\nSOLUTION RECOMMANDÉE:")
        print("   Vérifiez le fichier vector_store.index et régénérez-le si nécessaire")
    else:
        print("\n✅ VectorStore fonctionne")
        print(f"   • {len(distances)} résultats trouvés sans filtre")
        
        if result_filter_unknown[0]:
            print(f"   • Filtre 'unknown' retourne {len(result_filter_unknown[0])} résultats")
        else:
            print("   ⚠️ Filtre 'unknown' bloque tous les résultats")
            print("   → Le domaine 'unknown' n'existe pas dans les metadata")
            print("   → Solution: Ne pas appliquer de filtre si domain='unknown'")
    
    print("="*80 + "\n")
    
    # Fermer
    oss_client.close()


if __name__ == "__main__":
    debug_vector_store()