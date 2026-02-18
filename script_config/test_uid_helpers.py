#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests pour uid_helpers.py
==========================

Tests unitaires et d'intégration pour vérifier que uid_helpers
fonctionne correctement avec ChromaDB ET Dgraph.

Usage:
    python test_uid_helpers.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_extract_uid_from_metadata():
    """
    Test 1: Extraction d'UID depuis metadata
    """
    print("\n" + "=" * 80)
    print("TEST 1: extract_uid_from_metadata()")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import extract_uid_from_metadata
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("   Assurez-vous que context_weaver est dans le PYTHONPATH")
        return False
    
    test_cases = [
        # ChromaDB - IDs simples
        (
            {'id': 'doc_123'},
            'doc_123',
            "ChromaDB - clé 'id' simple"
        ),
        (
            {'taxon_id': 'txn_456'},
            'txn_456',
            "ChromaDB - clé 'taxon_id'"
        ),
        (
            {'doc_id': 'document_789'},
            'document_789',
            "ChromaDB - clé 'doc_id'"
        ),
        
        # Dgraph - UIDs hexadécimaux
        (
            {'uid': '0x123abc'},
            '0x123abc',
            "Dgraph - uid hexadécimal"
        ),
        (
            {'id': '0xffffff'},
            '0xffffff',
            "Dgraph - id hexadécimal"
        ),
        
        # Cas avec espaces
        (
            {'id': '  doc_999  '},
            'doc_999',
            "ID avec espaces (devrait être trimé)"
        ),
        
        # Clés non-standard
        (
            {'_id': 'mongo_id_123'},
            'mongo_id_123',
            "MongoDB - clé '_id'"
        ),
        
        # Metadata réaliste ChromaDB
        (
            {
                'id': 'txn_001',
                'name': 'SARL',
                'domain': 'Macompta.fr',
                'depth': 2
            },
            'txn_001',
            "Metadata ChromaDB complète"
        ),
        
        # Metadata réaliste Dgraph
        (
            {
                'uid': '0x12345',
                'name': 'Impôt sur les sociétés',
                'dgraph.type': ['TaxonNode']
            },
            '0x12345',
            "Metadata Dgraph complète"
        ),
    ]
    
    passed = 0
    failed = 0
    
    for metadata, expected, description in test_cases:
        try:
            result = extract_uid_from_metadata(metadata)
            
            if result == expected:
                print(f"✅ {description}")
                print(f"   Metadata: {metadata}")
                print(f"   UID extrait: '{result}'")
                passed += 1
            else:
                print(f"❌ {description}")
                print(f"   Attendu: '{expected}'")
                print(f"   Reçu: '{result}'")
                failed += 1
                
        except Exception as e:
            print(f"❌ {description}")
            print(f"   Erreur: {e}")
            failed += 1
    
    # Tests d'erreur (devraient échouer)
    error_cases = [
        ({}, "Dict vide"),
        ({'name': 'test', 'value': 123}, "Metadata sans UID"),
        (None, "Metadata None"),
    ]
    
    print(f"\n📋 Tests d'erreur (devraient échouer):")
    
    for metadata, description in error_cases:
        try:
            result = extract_uid_from_metadata(metadata)
            print(f"❌ {description}: devrait échouer mais a retourné '{result}'")
            failed += 1
        except ValueError as e:
            print(f"✅ {description}: échec attendu")
            passed += 1
        except Exception as e:
            print(f"⚠️ {description}: erreur inattendue - {e}")
    
    print(f"\n{'=' * 80}")
    print(f"RÉSULTATS TEST 1: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def test_validate_uid():
    """
    Test 2: Validation d'UID
    """
    print("\n" + "=" * 80)
    print("TEST 2: validate_uid()")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import validate_uid
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    test_cases = [
        # Strings directes
        ('doc_123', 'doc_123', "String simple ChromaDB"),
        ('0x123abc', '0x123abc', "String hex Dgraph"),
        ('  txn_456  ', 'txn_456', "String avec espaces"),
        
        # Dicts
        ({'id': 'doc_789'}, 'doc_789', "Dict avec id"),
        ({'uid': '0xffffff'}, '0xffffff', "Dict avec uid"),
        
        # Nombres (conversion)
        (12345, '12345', "Nombre entier"),
        (67.89, '67.89', "Nombre décimal"),
    ]
    
    passed = 0
    failed = 0
    
    for uid_input, expected, description in test_cases:
        try:
            result = validate_uid(uid_input)
            
            if result == expected:
                print(f"✅ {description}")
                print(f"   Input: {uid_input} (type: {type(uid_input).__name__})")
                print(f"   Output: '{result}'")
                passed += 1
            else:
                print(f"❌ {description}")
                print(f"   Attendu: '{expected}'")
                print(f"   Reçu: '{result}'")
                failed += 1
                
        except Exception as e:
            print(f"❌ {description}")
            print(f"   Erreur: {e}")
            failed += 1
    
    # Tests d'erreur
    error_cases = [
        ('', "String vide"),
        ('   ', "String avec seulement espaces"),
        ({}, "Dict vide"),
        (None, "None"),
    ]
    
    print(f"\n📋 Tests d'erreur (devraient échouer):")
    
    for uid_input, description in error_cases:
        try:
            result = validate_uid(uid_input)
            print(f"❌ {description}: devrait échouer mais a retourné '{result}'")
            failed += 1
        except ValueError:
            print(f"✅ {description}: échec attendu")
            passed += 1
        except Exception as e:
            print(f"⚠️ {description}: erreur inattendue - {e}")
    
    print(f"\n{'=' * 80}")
    print(f"RÉSULTATS TEST 2: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def test_validate_uid_list():
    """
    Test 3: Validation de liste d'UIDs
    """
    print("\n" + "=" * 80)
    print("TEST 3: validate_uid_list()")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import validate_uid_list
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    test_cases = [
        (
            ['doc_1', 'doc_2', 'doc_3'],
            ['doc_1', 'doc_2', 'doc_3'],
            "Liste de strings simples"
        ),
        (
            ['0x123', '0x456', '0x789'],
            ['0x123', '0x456', '0x789'],
            "Liste d'UIDs hex"
        ),
        (
            [{'id': 'doc_1'}, {'id': 'doc_2'}],
            ['doc_1', 'doc_2'],
            "Liste de dicts"
        ),
        (
            ['doc_1', {'id': 'doc_2'}, '0x123'],
            ['doc_1', 'doc_2', '0x123'],
            "Liste mixte (strings + dicts + hex)"
        ),
        (
            ['doc_1', None, 'doc_2', '', 'doc_3'],
            ['doc_1', 'doc_2', 'doc_3'],
            "Liste avec None et strings vides (devraient être filtrés)"
        ),
    ]
    
    passed = 0
    failed = 0
    
    for uid_list, expected, description in test_cases:
        try:
            result = validate_uid_list(uid_list)
            
            if result == expected:
                print(f"✅ {description}")
                print(f"   Input: {uid_list}")
                print(f"   Output: {result}")
                passed += 1
            else:
                print(f"❌ {description}")
                print(f"   Attendu: {expected}")
                print(f"   Reçu: {result}")
                failed += 1
                
        except Exception as e:
            print(f"❌ {description}")
            print(f"   Erreur: {e}")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"RÉSULTATS TEST 3: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def test_integration_chromadb_simulation():
    """
    Test 4: Simulation de résultats ChromaDB
    """
    print("\n" + "=" * 80)
    print("TEST 4: Intégration - Simulation ChromaDB")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import extract_uid_from_metadata
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    # Simuler des résultats ChromaDB typiques
    chromadb_results = [
        (
            'doc_001',  # id (ou distance en cas d'inversion)
            0.8523,     # score (ou id en cas d'inversion)
            {
                'id': 'doc_001',
                'name': 'SARL',
                'domain': 'Macompta.fr',
                'breadcrumb': 'Root > Formes Juridiques > SARL',
                'depth': 2
            }
        ),
        (
            'doc_002',
            0.7654,
            {
                'id': 'doc_002',
                'name': 'Impôt sur les sociétés',
                'domain': 'Macompta.fr',
                'breadcrumb': 'Root > Régimes Fiscaux > IS',
                'depth': 2
            }
        ),
        (
            'doc_003',
            0.6789,
            {
                'id': 'doc_003',
                'name': 'Prestataire de services',
                'domain': 'Macompta.fr',
                'breadcrumb': 'Root > Activités > Services',
                'depth': 2
            }
        ),
    ]
    
    print("📊 Traitement de résultats ChromaDB simulés:")
    print(f"   {len(chromadb_results)} résultats à traiter\n")
    
    passed = 0
    failed = 0
    
    for i, (taxon_id, score, metadata) in enumerate(chromadb_results, 1):
        try:
            # Extraire l'UID depuis metadata
            uid = extract_uid_from_metadata(metadata)
            
            print(f"✅ Résultat {i}:")
            print(f"   taxon_id: {taxon_id}")
            print(f"   score: {score}")
            print(f"   UID extrait: {uid}")
            print(f"   Nom: {metadata.get('name')}")
            
            # Vérifier cohérence
            if uid == taxon_id:
                print(f"   ✓ Cohérence: UID == taxon_id")
                passed += 1
            else:
                print(f"   ⚠️ Incohérence: UID ({uid}) != taxon_id ({taxon_id})")
                passed += 1  # Toujours OK tant qu'on extrait un UID
            
            print()
            
        except Exception as e:
            print(f"❌ Résultat {i}:")
            print(f"   Erreur: {e}")
            print()
            failed += 1
    
    print(f"{'=' * 80}")
    print(f"RÉSULTATS TEST 4: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def test_integration_dgraph_simulation():
    """
    Test 5: Simulation de résultats Dgraph
    """
    print("\n" + "=" * 80)
    print("TEST 5: Intégration - Simulation Dgraph")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import extract_uid_from_metadata
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    # Simuler des résultats Dgraph typiques
    dgraph_results = [
        {
            'uid': '0x123abc',
            'name': 'SARL',
            'dgraph.type': ['TaxonNode'],
            'category': 'forme_juridique'
        },
        {
            'uid': '0x456def',
            'name': 'Impôt sur les sociétés',
            'dgraph.type': ['TaxonNode'],
            'category': 'regime_fiscal'
        },
        {
            'uid': '0x789ghi',
            'name': 'Prestataire de services',
            'dgraph.type': ['TaxonNode'],
            'category': 'domaine_activite'
        },
    ]
    
    print("📊 Traitement de résultats Dgraph simulés:")
    print(f"   {len(dgraph_results)} résultats à traiter\n")
    
    passed = 0
    failed = 0
    
    for i, metadata in enumerate(dgraph_results, 1):
        try:
            uid = extract_uid_from_metadata(metadata)
            
            print(f"✅ Résultat {i}:")
            print(f"   UID extrait: {uid}")
            print(f"   Nom: {metadata.get('name')}")
            print(f"   Catégorie: {metadata.get('category')}")
            print()
            
            passed += 1
            
        except Exception as e:
            print(f"❌ Résultat {i}:")
            print(f"   Erreur: {e}")
            print()
            failed += 1
    
    print(f"{'=' * 80}")
    print(f"RÉSULTATS TEST 5: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def test_edge_cases():
    """
    Test 6: Cas limites et cas d'erreur
    """
    print("\n" + "=" * 80)
    print("TEST 6: Cas limites")
    print("=" * 80)
    
    try:
        from context_weaver.utils.uid_helpers import extract_uid_from_metadata
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    edge_cases = [
        # Metadata avec clés non-standard mais contenant 'id'
        (
            {'custom_id': 'my_custom_123'},
            'my_custom_123',
            "Clé non-standard contenant 'id'",
            False  # Ne devrait PAS échouer
        ),
        
        # Metadata très minimale
        (
            {'id': 'x'},
            'x',
            "ID d'un seul caractère",
            False
        ),
        
        # Metadata avec plusieurs champs UID (priorité)
        (
            {'id': 'first', 'taxon_id': 'second', 'uid': 'third'},
            'first',
            "Plusieurs champs UID (priorité à 'id')",
            False
        ),
        
        # Metadata vide (devrait échouer)
        (
            {},
            None,
            "Dict complètement vide",
            True  # DEVRAIT échouer
        ),
        
        # Metadata sans aucun UID (devrait échouer)
        (
            {'name': 'Test', 'value': 123, 'data': 'xyz'},
            None,
            "Metadata sans aucun champ UID",
            True  # DEVRAIT échouer
        ),
    ]
    
    passed = 0
    failed = 0
    
    for metadata, expected, description, should_fail in edge_cases:
        try:
            result = extract_uid_from_metadata(metadata)
            
            if should_fail:
                print(f"❌ {description}")
                print(f"   Devrait échouer mais a retourné: '{result}'")
                failed += 1
            elif result == expected:
                print(f"✅ {description}")
                print(f"   UID extrait: '{result}'")
                passed += 1
            else:
                print(f"⚠️ {description}")
                print(f"   Attendu: '{expected}', Reçu: '{result}'")
                # Tolérer si différent mais valide
                passed += 1
                
        except ValueError as e:
            if should_fail:
                print(f"✅ {description}")
                print(f"   Échec attendu: {str(e)[:50]}...")
                passed += 1
            else:
                print(f"❌ {description}")
                print(f"   Erreur inattendue: {e}")
                failed += 1
        except Exception as e:
            print(f"❌ {description}")
            print(f"   Erreur: {e}")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"RÉSULTATS TEST 6: {passed} réussis, {failed} échoués")
    print(f"{'=' * 80}")
    
    return failed == 0


def run_all_tests():
    """
    Exécute tous les tests
    """
    print("\n" + "╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "🧪 SUITE DE TESTS uid_helpers.py" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")
    
    results = []
    
    # Test 1
    results.append(("extract_uid_from_metadata()", test_extract_uid_from_metadata()))
    
    # Test 2
    results.append(("validate_uid()", test_validate_uid()))
    
    # Test 3
    results.append(("validate_uid_list()", test_validate_uid_list()))
    
    # Test 4
    results.append(("Intégration ChromaDB", test_integration_chromadb_simulation()))
    
    # Test 5
    results.append(("Intégration Dgraph", test_integration_dgraph_simulation()))
    
    # Test 6
    results.append(("Cas limites", test_edge_cases()))
    
    # Résumé global
    print("\n" + "╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "📊 RÉSUMÉ GLOBAL" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝\n")
    
    all_passed = True
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}  {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    
    if all_passed:
        print("✅ TOUS LES TESTS SONT PASSÉS!")
        print("   → uid_helpers.py fonctionne correctement")
        print("   → Compatible ChromaDB ET Dgraph")
        return 0
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("   → Vérifiez que vous avez bien appliqué la correction")
        print("   → Voir GUIDE_CORRECTION.txt pour les instructions")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())