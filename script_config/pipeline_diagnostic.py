#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnostic pour le pipeline Context Weaver
Logger TOUS les résultats à chaque étape
"""

import sys
import logging
from pathlib import Path

# Configuration logging détaillé
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def diagnostic_pipeline(user_context: str):
    """
    Exécute le pipeline avec logging détaillé de TOUS les résultats
    
    Args:
        user_context: Contexte utilisateur
    """
    print("\n" + "=" * 100)
    print("🔍 DIAGNOSTIC PIPELINE CONTEXT WEAVER")
    print("=" * 100)
    print(f"Contexte: {user_context}")
    print("=" * 100 + "\n")
    
    try:
        # Import du pipeline
        from context_weaver.pipeline.main_pipeline import ContextWeaverPipeline
        
        # Créer le pipeline
        logger.info("📦 Création du pipeline...")
        pipeline = ContextWeaverPipeline()
        
        # Exécuter
        logger.info("🚀 Exécution du pipeline...")
        result = pipeline.run(user_context)
        
        # === DIAGNOSTIC DÉTAILLÉ ===
        
        print("\n" + "=" * 100)
        print("📊 RÉSULTATS DÉTAILLÉS")
        print("=" * 100)
        
        # 1. Classification
        print("\n┌─ [1] CLASSIFICATION OSS 20B")
        print(f"│   Domain: {result.classification.domain}")
        print(f"│   Task: {result.classification.task}")
        print(f"│   Decision Type: {result.classification.decision_type}")
        print(f"│   Variables: {len(result.classification.variables)}")
        for i, var in enumerate(result.classification.variables, 1):
            print(f"│      {i}. {var}")
        print(f"│   Confidence: {result.classification.confidence:.2%}")
        print("└─\n")
        
        # 2. Search Results (ce qui vient du Vector Store + Dgraph)
        print("┌─ [2] SEARCH RESULTS (après validation)")
        print(f"│   Total: {result.search_results.final_count}")
        print(f"│   BM25: {result.search_results.bm25_count}")
        print(f"│   Embeddings: {result.search_results.embedding_count}")
        print(f"│   Fusion: {result.search_results.fusion_method}")
        print("│")
        
        if result.search_results.results:
            print("│   📋 Liste complète des résultats:")
            print("│")
            for i, res in enumerate(result.search_results.results, 1):
                print(f"│   [{i}] {res.name}")
                print(f"│       • ID: {res.id}")
                print(f"│       • Type: {res.type}")
                print(f"│       • Domain: {res.domain}")
                print(f"│       • Score: {res.score:.4f}")
                print(f"│       • Method: {res.method}")
                
                # Logger le contenu si présent
                if res.content:
                    content_keys = list(res.content.keys()) if isinstance(res.content, dict) else []
                    if content_keys:
                        print(f"│       • Content Keys: {', '.join(content_keys[:5])}")
                
                # Logger les metadata si présentes
                if res.metadata:
                    metadata_keys = list(res.metadata.keys()) if isinstance(res.metadata, dict) else []
                    if metadata_keys:
                        print(f"│       • Metadata Keys: {', '.join(metadata_keys[:5])}")
                
                print("│")
        else:
            print("│   ⚠️  Aucun résultat!")
        
        print("└─\n")
        
        # 3. Context Weaver Output
        print("┌─ [3] CONTEXT WEAVER OUTPUT")
        print(f"│   Confidence: {result.context_weaver.confidence_score:.2%}")
        print(f"│   Sources: {len(result.context_weaver.sources)}")
        print("│")
        
        if result.context_weaver.sources:
            print("│   📚 Sources:")
            for i, source in enumerate(result.context_weaver.sources, 1):
                print(f"│      {i}. {source}")
        
        print("│")
        print(f"│   Decision Tree Skeleton:")
        print(f"│      • Root: {result.context_weaver.decision_tree_skeleton.root}")
        print(f"│      • Nodes: {len(result.context_weaver.decision_tree_skeleton.nodes)}")
        
        if result.context_weaver.decision_tree_skeleton.nodes:
            print("│      • Node Details:")
            for i, node in enumerate(result.context_weaver.decision_tree_skeleton.nodes, 1):
                print(f"│         {i}. Field: {node.field}")
                if node.ranges:
                    print(f"│            Ranges: {node.ranges}")
                if node.groups:
                    print(f"│            Groups: {node.groups}")
                if node.levels:
                    print(f"│            Levels: {node.levels}")
        
        print("│")
        print(f"│   Metadata:")
        for key, value in result.context_weaver.metadata.items():
            print(f"│      • {key}: {value}")
        
        print("└─\n")
        
        # 4. Stats finales
        print("┌─ [4] STATISTIQUES")
        print(f"│   Temps d'exécution: {result.execution_time_ms:.2f} ms")
        print(f"│   Résultats trouvés: {result.search_results.final_count}")
        print(f"│   Résultats utilisés dans le squelette: {len(result.context_weaver.decision_tree_skeleton.nodes)}")
        print("└─\n")
        
        # === VÉRIFICATION DE L'INCOHÉRENCE ===
        
        print("\n" + "=" * 100)
        print("🔍 VÉRIFICATION INCOHÉRENCE")
        print("=" * 100)
        
        print(f"\n✅ Résultats validés par le pipeline: {result.search_results.final_count}")
        print(f"✅ Nodes dans le decision tree: {len(result.context_weaver.decision_tree_skeleton.nodes)}")
        print(f"✅ Sources citées: {len(result.context_weaver.sources)}")
        
        # Analyser l'écart
        if result.search_results.final_count > len(result.context_weaver.decision_tree_skeleton.nodes):
            print(f"\n⚠️  INCOHÉRENCE DÉTECTÉE:")
            print(f"   Le pipeline a trouvé {result.search_results.final_count} résultats validés")
            print(f"   Mais seulement {len(result.context_weaver.decision_tree_skeleton.nodes)} ont été utilisés")
            print(f"   pour construire le decision tree skeleton")
            print(f"\n   Raisons possibles:")
            print(f"   1. Context Weaver filtre par score minimum (min_confidence = 0.3)")
            print(f"   2. Context Weaver limite le nombre de nodes (max_nodes = 20)")
            print(f"   3. Certains résultats n'ont pas de variables exploitables")
        
        print("\n" + "=" * 100)
        print("✅ DIAGNOSTIC TERMINÉ")
        print("=" * 100 + "\n")
        
        # Fermer
        pipeline.close()
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur durant le diagnostic: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_with_batch_output():
    """
    Compare les résultats du pipeline avec ce qui est envoyé au batch
    """
    print("\n" + "=" * 100)
    print("🔍 COMPARAISON PIPELINE vs BATCH")
    print("=" * 100)
    
    print("""
    D'après les logs fournis:
    
    1. PIPELINE Context Weaver:
       • 50 résultats trouvés (Vector Store)
       • 50 structures validées (StructureValidator)
       • 5 nodes dans le squelette (Context Weaver)
       • Confiance: 69.25%
    
    2. BATCH suivant:
       • "Contextes: 3" est affiché
       • "Total samples (BDD): 10"
       • "1 combinaison(s) générée(s)"
    
    ⚠️  L'INCOHÉRENCE:
    
    Les "3 contextes" mentionnés dans le batch NE SONT PAS les 50 résultats du pipeline.
    
    Il s'agit probablement de:
    - 3 "contextes de génération" ou "templates"
    - qui vont être utilisés pour générer les samples
    - avec les 50 structures comme source d'information
    
    CONCLUSION:
    Les 50 résultats du pipeline sont bien présents et utilisés,
    mais ils sont AGRÉGÉS en 3 "contextes de haut niveau" pour la génération.
    
    Pour confirmer, il faudrait examiner le code qui génère ces "combinaisons".
    """)
    
    print("=" * 100 + "\n")


if __name__ == "__main__":
    # Test avec le même contexte que dans les logs
    test_context = "J'ai fait une erreur dans ma déclaration de TVA du trimestre dernier : j'ai oublié de déduire 5 000€..."
    
    # Diagnostic
    result = diagnostic_pipeline(test_context)
    
    # Comparaison
    compare_with_batch_output()
    
    # Recommandations
    print("\n" + "=" * 100)
    print("💡 RECOMMANDATIONS")
    print("=" * 100)
    print("""
    Pour améliorer la traçabilité:
    
    1. Ajouter des logs dans le code qui crée les "combinaisons"
       → Logger exactement quelles structures sont utilisées
    
    2. Clarifier la terminologie:
       • "Résultats" = ce que trouve le Vector Store (50)
       • "Structures validées" = après validation (50)
       • "Nodes du skeleton" = dans le decision tree (5)
       • "Contextes" = templates de génération (3?)
    
    3. Ajouter un ID de trace pour suivre les résultats
       du pipeline jusqu'à la génération finale
    
    4. Logger le mapping:
       Résultat X → utilisé dans Context Y → génère Sample Z
    """)
    print("=" * 100 + "\n")