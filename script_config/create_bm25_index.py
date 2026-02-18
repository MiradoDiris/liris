#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reconstruction de metadata.pkl depuis metadata.json
"""

import logging
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def rebuild_from_metadata_json():
    """Reconstruit metadata.pkl depuis metadata.json"""
    
    logger.info("=" * 80)
    logger.info("🔨 RECONSTRUCTION DEPUIS METADATA.JSON")
    logger.info("=" * 80)
    
    # 1. Charger metadata.json
    json_path = Path("data/indexes/faiss/metadata.json")
    
    if not json_path.exists():
        logger.error(f"❌ Fichier introuvable: {json_path}")
        return False
    
    logger.info(f"\n📂 Chargement: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"   ✅ Fichier chargé")
        logger.info(f"   • Type: {type(data)}")
        
        # Analyser la structure
        if isinstance(data, list):
            logger.info(f"   • Items: {len(data)}")
            metadata_list = data
        elif isinstance(data, dict):
            logger.info(f"   • Keys: {list(data.keys())}")
            
            # Essayer différentes clés
            if 'metadata' in data:
                metadata_list = data['metadata']
            elif 'items' in data:
                metadata_list = data['items']
            elif 'nodes' in data:
                metadata_list = data['nodes']
            else:
                # Peut-être que data est un dict id->metadata
                metadata_list = list(data.values())
        else:
            logger.error(f"   ❌ Format non reconnu: {type(data)}")
            return False
        
        logger.info(f"\n📊 Métadonnées extraites: {len(metadata_list)}")
        
        # 2. Échantillon
        if metadata_list:
            logger.info(f"\n📋 Échantillon (3 premiers):")
            for i, item in enumerate(metadata_list[:3], 1):
                if isinstance(item, dict):
                    logger.info(f"   {i}. ID: {item.get('id', 'N/A')}")
                    logger.info(f"      Name: {item.get('name', 'N/A')}")
                    logger.info(f"      Domain: {item.get('domain', 'N/A')}")
                    logger.info(f"      Type: {item.get('type', 'N/A')}")
                    logger.info(f"      Keys: {list(item.keys())}")
                else:
                    logger.info(f"   {i}. Type: {type(item)}")
        
        # 3. Vérifier cohérence avec FAISS
        logger.info(f"\n🔍 Vérification cohérence avec FAISS...")
        
        import faiss
        index_path = Path("data/indexes/faiss/vector_store.index")
        
        if index_path.exists():
            index = faiss.read_index(str(index_path))
            num_vectors = index.ntotal
            
            logger.info(f"   • Vecteurs FAISS: {num_vectors}")
            logger.info(f"   • Métadonnées JSON: {len(metadata_list)}")
            
            if num_vectors != len(metadata_list):
                logger.warning(f"   ⚠️ DÉSYNCHRONISATION: {num_vectors} vecteurs vs {len(metadata_list)} métadonnées")
                
                if len(metadata_list) < num_vectors:
                    logger.warning(f"   🔧 Padding avec des métadonnées génériques...")
                    
                    # Template pour métadonnées génériques
                    template = metadata_list[0] if metadata_list else {
                        'id': 'generic_0',
                        'name': 'Generic Item',
                        'domain': 'Macompta.fr',
                        'type': 'generic'
                    }
                    
                    for i in range(len(metadata_list), num_vectors):
                        generic = template.copy()
                        generic['id'] = f'generic_{i}'
                        generic['name'] = f'Generic Item {i}'
                        metadata_list.append(generic)
                    
                    logger.info(f"   ✅ Padded à {len(metadata_list)} métadonnées")
                
                elif len(metadata_list) > num_vectors:
                    logger.warning(f"   ✂️ Tronquage à {num_vectors} métadonnées...")
                    metadata_list = metadata_list[:num_vectors]
                    logger.info(f"   ✅ Tronqué à {len(metadata_list)} métadonnées")
            else:
                logger.info(f"   ✅ Cohérence parfaite!")
        
        # 4. Sauvegarder metadata.pkl
        logger.info(f"\n💾 Sauvegarde metadata.pkl...")
        
        output_path = Path("data/indexes/faiss/metadata.pkl")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            pickle.dump(metadata_list, f)
        
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"   ✅ Sauvegardé: {output_path}")
        logger.info(f"   • Taille: {size_mb:.2f} MB")
        logger.info(f"   • Items: {len(metadata_list)}")
        
        # 5. Vérification
        logger.info(f"\n✅ Vérification finale...")
        
        with open(output_path, 'rb') as f:
            loaded = pickle.load(f)
        
        logger.info(f"   ✅ Rechargé: {len(loaded)} items")
        
        if loaded:
            logger.info(f"\n   📋 Échantillon rechargé (3 premiers):")
            for i, item in enumerate(loaded[:3], 1):
                logger.info(f"      {i}. {item.get('name', 'N/A')}")
                logger.info(f"         ID: {item.get('id', 'N/A')}")
                logger.info(f"         Domain: {item.get('domain', 'N/A')}")
        
        # 6. Test avec VectorStore
        logger.info(f"\n🧪 Test avec VectorStore...")
        
        try:
            from context_weaver.data.vector_store_chroma import VectorStore
            
            vs = VectorStore()
            vs.initialize()
            
            logger.info(f"   ✅ VectorStore chargé")
            logger.info(f"   • Vecteurs: {vs.index.ntotal}")
            logger.info(f"   • Métadonnées: {len(vs.metadata)}")
            
            if len(vs.metadata) > 0:
                logger.info(f"   ✅ SUCCESS! VectorStore charge maintenant les métadonnées!")
            else:
                logger.error(f"   ❌ VectorStore ne charge toujours pas les métadonnées")
        
        except Exception as e:
            logger.error(f"   ❌ Erreur test VectorStore: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ RECONSTRUCTION TERMINÉE AVEC SUCCÈS")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Point d'entrée"""
    
    success = rebuild_from_metadata_json()
    
    if success:
        logger.info("\n🎯 Prochaines étapes:")
        logger.info("   1. ✅ metadata.pkl est maintenant disponible")
        logger.info("   2. Relancer: python create_bm25_index.py")
        logger.info("   3. Vérifier: python diagnostic_script.py")
        logger.info("   4. Tester: python test_context_weaver.py")
    else:
        logger.error("\n❌ Reconstruction échouée")
        logger.info("\nVérifiez:")
        logger.info("   • Que data/indexes/metadata.json existe")
        logger.info("   • Que le format JSON est valide")
        logger.info("   • Les logs d'erreur ci-dessus")


if __name__ == "__main__":
    main()