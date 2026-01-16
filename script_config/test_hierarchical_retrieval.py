#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 TEST DU RETRIEVAL HIÉRARCHIQUE
Vérifie que le vector store indexé supporte bien les recherches hiérarchiques
"""

import logging
import sys
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


def test_hierarchical_search():
    """Test des capacités de recherche hiérarchique"""
    
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.data.vector_store import VectorStore
    
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST DU RETRIEVAL HIÉRARCHIQUE")
    logger.info("="*80)
    
    # Initialisation
    logger.info("\n📌 Initialisation...")
    oss_client = OSSClassifierClient()
    vector_store = VectorStore()
    vector_store.initialize()
    
    stats = vector_store.get_stats()
    logger.info(f"   ✅ Vector store chargé: {stats['num_vectors']} vecteurs")
    
    # Requêtes de test
    test_queries = [
        {
            'name': 'Test 1: Recherche par nom exact',
            'query': 'Trésorerie',
            'expected': 'breadcrumb contient "Trésorerie"'
        },
        {
            'name': 'Test 2: Recherche par chemin hiérarchique',
            'query': 'TABLEAU DE BORD Trésorerie',
            'expected': 'breadcrumb contient "TABLEAU DE BORD > ... > Trésorerie"'
        },
        {
            'name': 'Test 3: Recherche par intent',
            'query': 'consulter afficher tableau de bord',
            'expected': 'intentKeywords contient "consulter" ou "afficher"'
        },
        {
            'name': 'Test 4: Recherche parent',
            'query': 'interface intention cluster',
            'expected': 'type RootLabel ou Cluster'
        },
        {
            'name': 'Test 5: Recherche avec contexte',
            'query': 'voir les comptes bancaires de trésorerie',
            'expected': 'breadcrumb contient "Trésorerie" et parent_name valide'
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        logger.info("\n" + "-"*80)
        logger.info(f"🔍 {test['name']}")
        logger.info(f"   Query: \"{test['query']}\"")
        logger.info(f"   Attendu: {test['expected']}")
        logger.info("-"*80)
        
        try:
            # Générer embeddings
            embeddings = oss_client.generate_embeddings(test['query'])
            
            # Recherche
            distances, metadata_list = vector_store.search(
                query_vector=embeddings,
                k=5
            )
            
            if not metadata_list:
                logger.warning("   ⚠️  Aucun résultat trouvé")
                continue
            
            logger.info(f"\n   📊 {len(metadata_list)} résultat(s):\n")
            
            for j, (dist, meta) in enumerate(zip(distances, metadata_list), 1):
                logger.info(f"   {j}. {meta.get('name', 'N/A')}")
                logger.info(f"      Score: {dist:.4f}")
                logger.info(f"      Type: {meta.get('type', 'N/A')}")
                logger.info(f"      Breadcrumb: {meta.get('breadcrumb', 'N/A')}")
                
                # Afficher métadonnées hiérarchiques si disponibles
                if 'parent_name' in meta:
                    logger.info(f"      Parent: {meta['parent_name']}")
                
                if 'children_count' in meta:
                    logger.info(f"      Children: {meta['children_count']}")
                
                if 'depth' in meta:
                    logger.info(f"      Depth: {meta['depth']}")
                
                logger.info("")
            
            # Validation du test
            logger.info("   ✅ Test terminé")
            
        except Exception as e:
            logger.error(f"   ❌ Erreur: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Fermer
    oss_client.close()
    
    logger.info("\n" + "="*80)
    logger.info("✅ TOUS LES TESTS TERMINÉS")
    logger.info("="*80 + "\n")


def test_metadata_structure():
    """Test de la structure des métadonnées"""
    
    from context_weaver.data.vector_store import VectorStore
    import json
    
    logger.info("\n" + "="*80)
    logger.info("🔍 TEST DE LA STRUCTURE DES MÉTADONNÉES")
    logger.info("="*80)
    
    # Charger le vector store
    vector_store = VectorStore()
    vector_store.initialize()
    
    if not vector_store.metadata:
        logger.error("❌ Aucune métadonnée trouvée")
        return
    
    logger.info(f"\n📦 Analyse de {len(vector_store.metadata)} documents...")
    
    # Analyser les champs disponibles
    all_fields = set()
    hierarchical_fields = set()
    
    for meta in vector_store.metadata[:10]:  # Échantillon de 10
        all_fields.update(meta.keys())
        
        # Identifier les champs hiérarchiques
        if 'breadcrumb' in meta:
            hierarchical_fields.add('breadcrumb')
        if 'parent_id' in meta:
            hierarchical_fields.add('parent_id')
        if 'parent_name' in meta:
            hierarchical_fields.add('parent_name')
        if 'children_count' in meta:
            hierarchical_fields.add('children_count')
        if 'depth' in meta:
            hierarchical_fields.add('depth')
    
    logger.info("\n📋 Champs disponibles:")
    for field in sorted(all_fields):
        logger.info(f"   • {field}")
    
    logger.info(f"\n🌳 Champs hiérarchiques détectés: {len(hierarchical_fields)}")
    for field in sorted(hierarchical_fields):
        logger.info(f"   ✅ {field}")
    
    # Afficher un exemple complet
    if vector_store.metadata:
        logger.info("\n📝 Exemple de métadonnées (1er document):")
        example = vector_store.metadata[0]
        logger.info(json.dumps(example, indent=2, ensure_ascii=False))
    
    # Statistiques
    logger.info("\n📊 Statistiques:")
    
    types_count = {}
    depths_count = {}
    
    for meta in vector_store.metadata:
        # Types
        node_type = meta.get('type', 'Unknown')
        types_count[node_type] = types_count.get(node_type, 0) + 1
        
        # Depths
        depth = meta.get('depth', 0)
        depths_count[depth] = depths_count.get(depth, 0) + 1
    
    logger.info("\n   Types de nœuds:")
    for node_type, count in sorted(types_count.items(), key=lambda x: -x[1]):
        logger.info(f"     • {node_type}: {count}")
    
    logger.info("\n   Distribution des profondeurs:")
    for depth in sorted(depths_count.keys()):
        count = depths_count[depth]
        logger.info(f"     • Depth {depth}: {count} nœuds")
    
    # Vérifier les breadcrumbs
    with_breadcrumb = sum(1 for m in vector_store.metadata if m.get('breadcrumb'))
    logger.info(f"\n   Breadcrumbs: {with_breadcrumb}/{len(vector_store.metadata)}")
    
    with_parent = sum(1 for m in vector_store.metadata if m.get('parent_id'))
    logger.info(f"   Parent IDs: {with_parent}/{len(vector_store.metadata)}")
    
    logger.info("\n" + "="*80)
    logger.info("✅ ANALYSE TERMINÉE")
    logger.info("="*80 + "\n")


def test_hierarchy_navigation():
    """Test de navigation hiérarchique"""
    
    from context_weaver.data.vector_store import VectorStore
    
    logger.info("\n" + "="*80)
    logger.info("🗺️  TEST DE NAVIGATION HIÉRARCHIQUE")
    logger.info("="*80)
    
    vector_store = VectorStore()
    vector_store.initialize()
    
    if not vector_store.metadata:
        logger.error("❌ Aucune métadonnée")
        return
    
    # Construire un index parent -> enfants
    parent_to_children = {}
    
    for meta in vector_store.metadata:
        parent_id = meta.get('parent_id')
        if parent_id:
            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(meta)
    
    logger.info(f"\n📊 {len(parent_to_children)} nœuds ont des enfants")
    
    # Trouver un nœud racine (sans parent)
    root_nodes = [m for m in vector_store.metadata if not m.get('parent_id')]
    
    if root_nodes:
        logger.info(f"\n🌲 {len(root_nodes)} nœud(s) racine(s) détecté(s)")
        
        # Afficher l'arborescence d'un nœud racine
        root = root_nodes[0]
        logger.info(f"\n📍 Arborescence depuis: {root.get('name', 'N/A')}")
        
        def print_tree(node_id, indent=0):
            """Affiche récursivement l'arbre"""
            children = parent_to_children.get(node_id, [])
            
            for child in children[:3]:  # Limiter à 3 enfants par niveau
                name = child.get('name', 'N/A')
                child_id = child.get('id')
                depth = child.get('depth', 0)
                
                logger.info(f"{'  ' * indent}├─ {name} (depth={depth})")
                
                if indent < 3:  # Limiter la profondeur d'affichage
                    print_tree(child_id, indent + 1)
        
        root_id = root.get('id')
        print_tree(root_id)
    
    logger.info("\n" + "="*80)
    logger.info("✅ NAVIGATION TESTÉE")
    logger.info("="*80 + "\n")


def main():
    """Point d'entrée principal"""
    
    print("\n" + "="*80)
    print("🧪 TESTS DU RETRIEVAL HIÉRARCHIQUE")
    print("="*80 + "\n")
    
    print("Tests disponibles:")
    print("  1. Test de recherche hiérarchique (5 requêtes)")
    print("  2. Test de structure des métadonnées")
    print("  3. Test de navigation dans l'arbre")
    print("  4. Tous les tests")
    print("  5. Quitter")
    
    choice = input("\nVotre choix (1-5): ").strip()
    
    try:
        if choice == "1":
            test_hierarchical_search()
        elif choice == "2":
            test_metadata_structure()
        elif choice == "3":
            test_hierarchy_navigation()
        elif choice == "4":
            test_hierarchical_search()
            test_metadata_structure()
            test_hierarchy_navigation()
        elif choice == "5":
            print("\n👋 Au revoir!")
            return 0
        else:
            print("\n❌ Choix invalide")
            return 1
        
        print("\n" + "="*80)
        print("✅ TESTS TERMINÉS")
        print("="*80 + "\n")
        
        return 0
    
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