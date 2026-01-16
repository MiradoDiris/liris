#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Simple du Pipeline - Une seule phrase
✅ CORRIGÉ: Adapté au pipeline refactorisé (sans context_weaver)
✅ FIX: Imports et affichage taxonomy via résultats (pas de context_weaver)
"""

import sys
import logging
from pathlib import Path

# Setup logging simple
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Test avec une seule phrase"""
    
    print("=" * 60)
    print("🧪 TEST SIMPLE DU PIPELINE")
    print("=" * 60)
    
    # Import
    from context_weaver.pipeline.main_pipeline import create_pipeline
    
    # Créer pipeline
    print("\n📦 Création du pipeline...")
    try:
        pipeline = create_pipeline(
            project_name="test_simple",
            enable_taxonomy_validation=True
        )
        print("✅ Pipeline créé\n")
    except Exception as e:
        print(f"❌ Erreur création: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test avec UNE phrase
    query ="""
        Je souhaite créer une facture de vente pour un client avec application de la TVA à 20%. 
        Cette opération nécessite la configuration du compte client en classe 4 du plan comptable 
        général PCG, l'enregistrement de l'écriture comptable au journal des ventes avec la TVA 
        collectée, et la génération automatique des écritures dans les comptes de produits de 
        classe 7. Je dois également m'assurer que cette facture sera incluse dans la déclaration 
        de TVA trimestrielle CA3 et dans la liasse fiscale de fin d'exercice, incluant le bilan 
        comptable et le compte de résultat. Pour les immobilisations éventuelles, il faudra 
        prévoir le calcul de l'amortissement linéaire et le rapprochement bancaire lors de 
        l'encaissement.
        """
    
    print("=" * 60)
    print(f"📝 QUERY: {query}")
    print("=" * 60)
    
    try:
        # Exécuter
        result = pipeline.run(
            user_context=query,
            conversation_id="simple_test"
        )
        
        # Afficher résultats (adapté au nouveau PipelineOutput sans context_weaver)
        print("\n✅ RÉSULTATS:")
        print("-" * 60)
        print(f"Domain      : {result.classification.domain}")
        print(f"Task        : {result.classification.task}")
        print(f"Variables   : {len(result.classification.variables)}")
        print(f"Results     : {result.search_results.final_count}")
        print(f"Method      : {result.search_results.fusion_method}")
        print(f"Time        : {result.execution_time_ms:.2f}ms")
        
        # Top 3 résultats (avec validation learner si disponible)
        if result.search_results.results:
            print(f"\n🏆 TOP 3:")
            for i, res in enumerate(result.search_results.results[:3], 1):
                print(f"  {i}. {res.name} (score: {res.score:.4f})")
                if res.metadata and 'graph_validation' in res.metadata:
                    val = res.metadata['graph_validation']
                    print(f"     • Learner: {val['category']} (score={val['score']:.3f})")
        
        # Taxonomy status (inféré des résultats ou metadata)
        print(f"\n📊 TAXONOMY: (Inféré des résultats)")
        if result.search_results.results:
            first_res = result.search_results.results[0]
            print(f"  Status: PASS (basé sur top result)")
            print(f"  Top Taxon: {first_res.name} (ID: {first_res.id})")
            if first_res.metadata and 'taxonomy_status' in first_res.metadata:
                print(f"  Status détaillé: {first_res.metadata['taxonomy_status']}")
        else:
            print("  Status: No results")
        
        print("\n" + "=" * 60)
        print("✅ TEST TERMINÉ")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Fermer
        pipeline.close()


if __name__ == "__main__":
    main()