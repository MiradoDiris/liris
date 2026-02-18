#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Final du Pipeline Générique - VERSION CORRIGÉE
✅ Filtre domain ACTIVÉ (Macompta.fr)
✅ Query expansion DÉSACTIVÉE (pas de dilution)
✅ Contextual boost APPLIQUÉ (forme juridique, régime fiscal, etc.)
✅ Filtrage par pertinence contextuelle
✅ Analyse détaillée des résultats
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_final_pipeline_fixed.log', mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# PROMPT DE TEST
# ============================================================================

TEST_PROMPT = """macompta.fr est une plateforme française de gestion et de comptabilité en ligne pour indépendants, TPE, associations et entrepreneurs. Elle permet de gérer la comptabilité, la facturation et les déclarations fiscales et sociales.
 
Générer un dataset d'inputs utilisateur réalistes pour entraîner Emma, une IA conversationnelle spécialisée dans macompta.fr. Chaque input doit refléter une situation authentique, avec des formulations variées, naturelles ou familières, et correspondre aux besoins spécifiques d'un utilisateur dans le cadre d'un RDV d'onboarding.
Consignes générales :
1. Chaque input doit être formulé du point de vue de l'utilisateur et correspondre à un cas concret.
2. La première question est initiée par Emma ; tous les inputs suivants doivent refléter les réponses ou relances de l'utilisateur.
3. Aucun output d'Emma n'est demandé à ce stade : uniquement les inputs utilisateur.
4. Les inputs doivent couvrir toutes les combinaisons possibles des paramètres suivants :
   * Forme juridique : SARL, etc.
   * Type fiscal et domaine d'activité : impôt sur les sociétés, prestataire de services, plan standard, etc.
   * Date d'exercice : 1er au 31 décembre
   * Type de comptabilité : Créances / Dettes
Typologies à intégrer implicitement dans chaque input :
* Intention : ce que l'utilisateur cherche à faire ou comprendre (ex. : obtenir une info, réaliser une action, corriger une erreur, recevoir un conseil).
* Niveau de maîtrise : débutant, intermédiaire, avancé ; à déduire de la formulation et du vocabulaire.
* Complexité / niveau de confiance : simple ou sensible ; adapte le détail et le ton si la demande est complexe.
* Abonnement / fonctionnalités : respecter ce qui est accessible selon l'offre macompta.fr.
* Données du compte : type d'activité, statut juridique, régime fiscal, etc.
* UI / UX : contexte de l'écran et parcours utilisé, pour guider l'utilisateur avec repères concrets.
* Temporalité : tenir compte de la date et des obligations fiscales, sociales et comptables.
* Type d'interaction : onboarding, suivi régulier, demande ponctuelle."""


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def print_section(title: str):
    """Affiche un séparateur de section"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def format_taxon_result(taxon, rank: int) -> Dict[str, Any]:
    """Formate un résultat taxon pour affichage"""
    return {
        'rank': rank,
        'name': taxon.name,
        'score': round(taxon.score, 4),
        'domain': taxon.domain,
        'breadcrumb': taxon.content.get('breadcrumb', 'N/A'),
        'definition': taxon.content.get('definition', 'N/A')[:150] + '...' if taxon.content.get('definition') else 'N/A',
        'taxon_id': taxon.id,
        'metadata': taxon.metadata if hasattr(taxon, 'metadata') else {}
    }


def analyze_result_relevance(results: List[Dict], extracted_params: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Analyse la pertinence des résultats par rapport aux paramètres extraits
    """
    analysis = {
        'highly_relevant': [],
        'partially_relevant': [],
        'low_relevance': [],
        'matches_by_category': {}
    }
    
    # Créer un set de tous les termes extraits (lowercase)
    all_terms = set()
    for category, values in extracted_params.items():
        analysis['matches_by_category'][category] = []
        for value in values:
            all_terms.add(value.lower())
    
    # Analyser chaque résultat
    for result in results:
        name_lower = result['name'].lower()
        breadcrumb_lower = result['breadcrumb'].lower()
        
        # Compter les matches
        matches = []
        for category, values in extracted_params.items():
            for value in values:
                if value.lower() in name_lower or value.lower() in breadcrumb_lower:
                    matches.append((category, value))
                    analysis['matches_by_category'][category].append(result['name'])
        
        # Classer par pertinence
        if len(matches) >= 2:
            analysis['highly_relevant'].append({
                'name': result['name'],
                'score': result['score'],
                'matches': matches
            })
        elif len(matches) == 1:
            analysis['partially_relevant'].append({
                'name': result['name'],
                'score': result['score'],
                'matches': matches
            })
        else:
            analysis['low_relevance'].append({
                'name': result['name'],
                'score': result['score']
            })
    
    return analysis


def save_results_to_json(results: List[Dict], filename: str = "pipeline_results.json"):
    """Sauvegarde les résultats en JSON"""
    output_path = Path(filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Résultats sauvegardés: {output_path.absolute()}")


def extract_context_for_llm(results: List[Dict]) -> Dict[str, Any]:
    """
    Extrait le contexte pour un LLM
    """
    return {
        'configurations_macompta': [
            {
                'name': r['name'],
                'breadcrumb': r['breadcrumb'],
                'definition': r['definition'],
                'domain': r['domain'],
                'score': r['score']
            }
            for r in results
        ],
        'summary': {
            'total_configurations': len(results),
            'domains': list(set(r['domain'] for r in results)),
            'top_3_names': [r['name'] for r in results[:3]],
            'avg_score': sum(r['score'] for r in results) / len(results) if results else 0
        }
    }


# ============================================================================
# FONCTION DE TEST PRINCIPALE
# ============================================================================

def test_pipeline_with_full_prompt():
    """
    Test complet du pipeline avec le prompt utilisateur réel
    VERSION CORRIGÉE avec tous les fixes appliqués
    """
    
    print_section("TEST PIPELINE GÉNÉRIQUE - VERSION CORRIGÉE")
    
    print("📝 Prompt utilisateur:")
    print("-" * 80)
    print(TEST_PROMPT)
    print(f"\n📊 Longueur totale: {len(TEST_PROMPT)} caractères")
    
    try:
        # ====================================================================
        # 1. INITIALISATION DU PIPELINE AVEC CORRECTIONS
        # ====================================================================
        print_section("1. INITIALISATION DU PIPELINE (VERSION CORRIGÉE)")
        
        from context_weaver.pipeline.main_pipeline import create_pipeline
        
        print("🔄 Création du pipeline avec optimisations...")
        print("   ✅ Domain filter: ACTIVÉ (Macompta.fr)")
        print("   ✅ Query expansion: DÉSACTIVÉE")
        print("   ✅ Contextual boost: ACTIVÉ")
        print("   ✅ Filtrage pertinence: ACTIVÉ\n")
        
        pipeline = create_pipeline(
            project_name="macompta_test",
            use_domain_filter=True,  # ✅ CORRIGÉ: Activé
            default_domain="Macompta.fr",  # ✅ CORRIGÉ: Forcé
            query_strategy="full_prompt"
        )
        
        # ✅ NOUVEAU: Configurer le retriever pour désactiver query expansion
        pipeline.taxonomy_pipeline.retriever.config.enable_query_expansion = False
        pipeline.taxonomy_pipeline.retriever.config.enable_bm25_exact_boost = True
        pipeline.taxonomy_pipeline.retriever.config.bm25_exact_boost_factor = 2.0
        
        print("✅ Pipeline créé et configuré\n")
        
        # ====================================================================
        # 2. EXÉCUTION DE LA RECHERCHE
        # ====================================================================
        print_section("2. EXÉCUTION DE LA RECHERCHE")
        
        print("🚀 Lancement de la recherche optimisée...")
        print("   • Méthode: Hybrid RRF + Contextual Reranking")
        print("   • Filtre: Macompta.fr (strict)")
        print("   • Query expansion: Désactivée")
        print("   • Top-K: 15\n")
        
        result = pipeline.run(
            user_context=TEST_PROMPT,
            top_k=15,
            domain="Macompta.fr"  # ✅ CORRIGÉ: Force le domain
        )
        
        print(f"✅ Recherche terminée en {result.execution_time_ms:.0f}ms")
        
        # ====================================================================
        # 3. ANALYSE DES RÉSULTATS
        # ====================================================================
        print_section("3. RÉSULTATS DE LA RECHERCHE")
        
        if not result.search_results.results:
            print("❌ Aucun résultat trouvé")
            return None
        
        print(f"📊 Statistiques:")
        print(f"   • Total résultats: {result.search_results.final_count}")
        print(f"   • Méthode: {result.search_results.fusion_method}")
        print(f"   • Dense count: {result.search_results.embedding_count}")
        print(f"   • BM25 count: {result.search_results.bm25_count}")
        
        # Vérifier le filtre domain
        domains = set(r.domain for r in result.search_results.results)
        print(f"\n🔍 Vérification filtre domain:")
        print(f"   • Domains trouvés: {domains}")
        if len(domains) == 1 and 'Macompta.fr' in domains:
            print(f"   ✅ Filtre domain correctement appliqué")
        else:
            print(f"   ⚠️  Filtre domain non appliqué ou partiel")
        
        # Top score
        top_score = result.search_results.results[0].score
        print(f"\n📈 Top score: {top_score:.4f}")
        
        if top_score >= 0.30:
            print("   ✅ EXCELLENT - Résultats très pertinents")
        elif top_score >= 0.20:
            print("   ✅ BON - Résultats pertinents")
        elif top_score >= 0.15:
            print("   ✅ ACCEPTABLE - Résultats partiellement pertinents")
        elif top_score >= 0.10:
            print("   ⚠️  MOYEN - Vérifier la pertinence")
        else:
            print("   ❌ FAIBLE - Résultats peu pertinents")
        
        # ====================================================================
        # 4. AFFICHAGE TOP 15 AVEC ANALYSE
        # ====================================================================
        print_section("4. TOP 15 TAXONS TROUVÉS")
        
        formatted_results = []
        
        for i, taxon in enumerate(result.search_results.results[:15], 1):
            formatted = format_taxon_result(taxon, i)
            formatted_results.append(formatted)
            
            print(f"{i}. {taxon.name}")
            print(f"   • Score: {taxon.score:.4f}")
            print(f"   • Domain: {taxon.domain}")
            
            # Breadcrumb complet
            breadcrumb = taxon.content.get('breadcrumb', '')
            if breadcrumb:
                levels = breadcrumb.split(' > ')
                if len(levels) > 3:
                    short = ' > '.join(levels[-3:])
                    print(f"   • Path: ...{short}")
                else:
                    print(f"   • Path: {breadcrumb}")
            
            # Metadata (si disponible)
            if hasattr(taxon, 'metadata') and taxon.metadata:
                if taxon.metadata.get('is_exact_match'):
                    print(f"   🎯 EXACT MATCH détecté")
                if taxon.metadata.get('source'):
                    print(f"   • Source: {taxon.metadata['source']}")
            
            print()
        
        # ====================================================================
        # 5. ANALYSE DE PERTINENCE CONTEXTUELLE
        # ====================================================================
        print_section("5. ANALYSE DE PERTINENCE CONTEXTUELLE")
        
        # Récupérer les paramètres extraits
        extracted_params = result.metadata.get('extracted_params', {})
        
        if extracted_params:
            print("📋 Paramètres extraits du prompt:")
            for category, values in extracted_params.items():
                print(f"   • {category}: {', '.join(values)}")
            
            # Analyser la pertinence
            relevance = analyze_result_relevance(formatted_results, extracted_params)
            
            print(f"\n🎯 Analyse de pertinence:")
            print(f"   • Hautement pertinent: {len(relevance['highly_relevant'])} résultats")
            print(f"   • Partiellement pertinent: {len(relevance['partially_relevant'])} résultats")
            print(f"   • Faible pertinence: {len(relevance['low_relevance'])} résultats")
            
            # Afficher les résultats hautement pertinents
            if relevance['highly_relevant']:
                print(f"\n🏆 Résultats hautement pertinents:")
                for item in relevance['highly_relevant'][:5]:
                    print(f"   • {item['name']} (score: {item['score']:.3f})")
                    print(f"     Matches: {', '.join(f'{cat}={val}' for cat, val in item['matches'])}")
            
            # Afficher les matches par catégorie
            print(f"\n📊 Matches par catégorie:")
            for category, matches in relevance['matches_by_category'].items():
                if matches:
                    unique_matches = list(set(matches))
                    print(f"   • {category}: {len(unique_matches)} taxons")
                    for match in unique_matches[:3]:
                        print(f"     - {match}")
        else:
            print("⚠️  Aucun paramètre extrait du prompt")
        
        # ====================================================================
        # 6. ANALYSE DES CONFIGURATIONS TROUVÉES
        # ====================================================================
        print_section("6. ANALYSE DES CONFIGURATIONS")
        
        # Extraire les catégories
        categories = {}
        for taxon in result.search_results.results[:10]:
            breadcrumb = taxon.content.get('breadcrumb', '')
            if breadcrumb:
                parts = breadcrumb.split(' > ')
                if len(parts) >= 3:
                    category = parts[2] if len(parts) > 2 else 'Other'
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(taxon.name)
        
        print("📂 Catégories trouvées dans le top 10:")
        for category, items in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n   {category} ({len(items)} items):")
            for item in items[:5]:
                print(f"      • {item}")
            if len(items) > 5:
                print(f"      ... et {len(items) - 5} autres")
        
        # ====================================================================
        # 7. CONTEXTE POUR LLM
        # ====================================================================
        print_section("7. CONTEXTE POUR GÉNÉRATION LLM")
        
        # Extraire top 10 pour LLM
        llm_context = extract_context_for_llm(formatted_results[:10])
        
        print("📋 Contexte extrait pour LLM:")
        print(f"   • Configurations: {llm_context['summary']['total_configurations']}")
        print(f"   • Domaines: {', '.join(llm_context['summary']['domains'])}")
        print(f"   • Score moyen: {llm_context['summary']['avg_score']:.3f}")
        print(f"\n   Top 3:")
        for i, name in enumerate(llm_context['summary']['top_3_names'], 1):
            print(f"      {i}. {name}")
        
        # Exemple de prompt pour LLM
        print("\n💡 Exemple de prompt pour LLM:")
        print("-" * 80)
        
        llm_prompt_example = f"""
Contexte Macompta.fr trouvé dans la taxonomie:

{json.dumps(llm_context['configurations_macompta'][:5], indent=2, ensure_ascii=False)}

Tâche: 
Génère 50 inputs utilisateur réalistes pour un RDV d'onboarding Macompta.fr.

Chaque input doit:
- Couvrir les configurations ci-dessus (SARL, IS, Prestataire services, etc.)
- Être formulé naturellement (comme un vrai utilisateur)
- Refléter différents niveaux de maîtrise (débutant, intermédiaire, expert)
- Correspondre à un cas concret d'onboarding
- Mélanger questions simples et complexes

Format de sortie JSON:
[
  {{
    "input": "Je viens de créer ma SARL, c'est quoi exactement l'IS ?",
    "context": "SARL, IS, Débutant, Onboarding",
    "configuration": "SARL - Impôts sur les sociétés",
    "complexity": "simple"
  }},
  {{
    "input": "Ma SARL est prestataire de services sous IS avec exercice du 1er janvier au 31 décembre. Je dois configurer la comptabilité créances/dettes. Par où commencer ?",
    "context": "SARL, IS, Prestataire services, Configuration complète",
    "configuration": "SARL - IS - Prestataire services - Plan standard",
    "complexity": "complex"
  }},
  ...
]
"""
        
        print(llm_prompt_example[:600] + "...")
        
        # ====================================================================
        # 8. SAUVEGARDE DES RÉSULTATS
        # ====================================================================
        print_section("8. SAUVEGARDE DES RÉSULTATS")
        
        # Sauvegarder résultats bruts
        save_results_to_json(formatted_results, "pipeline_results_fixed.json")
        
        # Sauvegarder contexte LLM
        save_results_to_json([llm_context], "llm_context_fixed.json")
        
        # Sauvegarder prompt LLM
        with open("llm_prompt_example_fixed.txt", 'w', encoding='utf-8') as f:
            f.write(llm_prompt_example)
        
        # Sauvegarder analyse de pertinence
        if extracted_params:
            save_results_to_json([relevance], "relevance_analysis.json")
        
        print("✅ Fichiers créés:")
        print("   • pipeline_results_fixed.json - Résultats détaillés")
        print("   • llm_context_fixed.json - Contexte pour LLM")
        print("   • llm_prompt_example_fixed.txt - Exemple de prompt LLM")
        if extracted_params:
            print("   • relevance_analysis.json - Analyse de pertinence")
        
        # ====================================================================
        # 9. DIAGNOSTIC ET RECOMMANDATIONS
        # ====================================================================
        print_section("9. DIAGNOSTIC ET RECOMMANDATIONS")
        
        # Analyser la qualité des résultats
        if extracted_params and relevance:
            highly_relevant_pct = (len(relevance['highly_relevant']) / len(formatted_results)) * 100
            low_relevance_pct = (len(relevance['low_relevance']) / len(formatted_results)) * 100
            
            print("📊 Qualité des résultats:")
            print(f"   • Hautement pertinent: {highly_relevant_pct:.1f}%")
            print(f"   • Faible pertinence: {low_relevance_pct:.1f}%")
            
            if highly_relevant_pct >= 60:
                print("\n   ✅ EXCELLENT - Résultats très ciblés")
            elif highly_relevant_pct >= 40:
                print("\n   ✅ BON - Résultats globalement pertinents")
            elif highly_relevant_pct >= 20:
                print("\n   ⚠️  MOYEN - Amélioration possible")
            else:
                print("\n   ❌ FAIBLE - Résultats trop dilués")
        
        print("\n💡 Prochaines étapes:")
        print("\n1. Utiliser le contexte pour générer le dataset:")
        print("   • Prendre llm_context_fixed.json")
        print("   • Le passer à Claude/GPT-4")
        print("   • Générer 50-100 inputs utilisateur")
        
        print("\n2. Scores après corrections:")
        print(f"   • Score top actuel: {top_score:.4f}")
        if top_score >= 0.20:
            print("   • ✅ Amélioration significative attendue vs version précédente")
        print("   • Se fier au classement relatif (top 10)")
        
        print("\n3. Vérifications:")
        if len(domains) == 1 and 'Macompta.fr' in domains:
            print("   • ✅ Filtre domain correctement appliqué")
        else:
            print("   • ⚠️  Vérifier le filtre domain")
        
        if extracted_params and highly_relevant_pct >= 40:
            print("   • ✅ Contextual boost fonctionne bien")
        else:
            print("   • ⚠️  Contextual boost à améliorer")
        
        # ====================================================================
        # 10. FERMETURE
        # ====================================================================
        print_section("10. FERMETURE")
        
        pipeline.close()
        print("✅ Pipeline fermé proprement")
        
        # ====================================================================
        # RÉSUMÉ FINAL
        # ====================================================================
        print_section("RÉSUMÉ FINAL")
        
        print(f"✅ Test terminé avec succès!")
        print(f"\n📊 Récapitulatif:")
        print(f"   • Prompt: {len(TEST_PROMPT)} caractères")
        print(f"   • Résultats: {len(formatted_results)} taxons")
        print(f"   • Score top: {top_score:.4f}")
        print(f"   • Temps: {result.execution_time_ms:.0f}ms")
        
        if extracted_params and relevance:
            print(f"   • Hautement pertinent: {len(relevance['highly_relevant'])} taxons")
            print(f"   • Faible pertinence: {len(relevance['low_relevance'])} taxons")
        
        print(f"\n📁 Fichiers générés:")
        print(f"   • pipeline_results_fixed.json")
        print(f"   • llm_context_fixed.json")
        print(f"   • llm_prompt_example_fixed.txt")
        print(f"   • relevance_analysis.json")
        print(f"   • test_final_pipeline_fixed.log")
        
        print(f"\n🎯 Action suivante:")
        print(f"   Utiliser llm_context_fixed.json avec un LLM pour générer le dataset!")
        
        print("\n🔧 Corrections appliquées:")
        print("   ✅ Domain filter activé et forcé")
        print("   ✅ Query expansion désactivée")
        print("   ✅ BM25 exact match boost activé")
        print("   ✅ Analyse de pertinence contextuelle")
        
        print("\n" + "=" * 80)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        logger.exception("Stack trace:")
        return None


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Point d'entrée principal"""
    
    print("\n" + "=" * 80)
    print("  🧪 TEST FINAL - PIPELINE GÉNÉRIQUE (VERSION CORRIGÉE)")
    print("=" * 80)
    print("\n🔧 Corrections appliquées:")
    print("   ✅ Domain filter ACTIVÉ")
    print("   ✅ Query expansion DÉSACTIVÉE")
    print("   ✅ Contextual boost APPLIQUÉ")
    print("   ✅ Filtrage par pertinence")
    
    result = test_pipeline_with_full_prompt()
    
    if result:
        print("\n✅ Test réussi!")
        return 0
    else:
        print("\n❌ Test échoué")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)