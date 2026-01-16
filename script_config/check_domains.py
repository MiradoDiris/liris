#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour analyser les domaines présents dans les métadonnées
"""

from context_weaver.data.vector_store import VectorStore

def check_domains():
    print("=" * 80)
    print("🔍 ANALYSE DES DOMAINES DANS VECTOR STORE")
    print("=" * 80)
    
    # Charger Vector Store
    vs = VectorStore()
    vs.initialize()
    
    total = vs.index.ntotal if hasattr(vs.index, 'ntotal') else 0
    print(f"\n📊 Total vecteurs: {total}")
    print(f"📊 Total métadonnées: {len(vs.metadata)}")
    
    # Analyser domaines
    domains = {}
    no_domain = 0
    
    # vs.metadata est une LISTE
    for i, meta in enumerate(vs.metadata):
        domain = meta.get('domain', None)
        
        if domain is None or domain == '':
            no_domain += 1
        else:
            domains[domain] = domains.get(domain, 0) + 1
    
    print(f"\n📋 DISTRIBUTION PAR DOMAINE:")
    print(f"   Sans domaine: {no_domain}")
    print("")
    
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"   • '{domain}': {count} ({count/len(vs.metadata)*100:.1f}%)")
    
    print(f"\n🔍 ÉCHANTILLON DE MÉTADONNÉES (5 premiers):")
    for i, meta in enumerate(vs.metadata[:5], 1):
        print(f"\n   [{i}]")
        print(f"      name: {meta.get('name', 'N/A')}")
        print(f"      domain: '{meta.get('domain', 'N/A')}'")
        print(f"      type: {meta.get('type', 'N/A')}")
        if 'taxon_id' in meta:
            print(f"      taxon_id: {meta.get('taxon_id')}")
        if 'breadcrumb' in meta:
            print(f"      breadcrumb: {meta.get('breadcrumb', '')[:80]}...")
    
    # Recherche 'compliance' (insensible à la casse)
    print(f"\n🔎 RECHERCHE 'compliance' (insensible à la casse):")
    
    compliance_variants = []
    for domain in domains.keys():
        if 'compliance' in domain.lower():
            compliance_variants.append(domain)
    
    if compliance_variants:
        print(f"   ✅ Variantes trouvées:")
        for variant in compliance_variants:
            print(f"      • '{variant}': {domains[variant]} entrées")
    else:
        print(f"   ❌ Aucune variante de 'compliance' trouvée")
    
    print("\n" + "=" * 80)
    print("💡 RECOMMANDATION")
    print("=" * 80)
    
    if 'compliance' in domains:
        print("✅ Le domaine 'compliance' existe dans les métadonnées")
        print(f"   → Vérifier pourquoi le filtre ne fonctionne pas")
    elif compliance_variants:
        print(f"⚠️ Le domaine exact 'compliance' n'existe pas")
        print(f"   Mais des variantes existent: {compliance_variants}")
        print(f"\n   SOLUTION: Modifier le code pour utiliser '{compliance_variants[0]}'")
        print(f"   OU normaliser tous les domaines en minuscules lors de l'indexation")
    else:
        print("❌ Aucun domaine 'compliance' (ou variante) trouvé")
        print("\n   SOLUTIONS:")
        print("   1. Utiliser un autre domaine disponible")
        print("   2. Désactiver le filtre domaine")
        print("   3. Ré-indexer avec le bon domaine")
    
    print("=" * 80)


if __name__ == "__main__":
    check_domains()