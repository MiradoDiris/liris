#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de test pour valider les corrections apportées à la base de données
et au widget de stratégie.
"""

import sys
import os
import tempfile
import sqlite3
from contextlib import contextmanager

# Ajouter le répertoire courant au path pour les imports
sys.path.insert(0, '/home/ubuntu')

# Mock des dépendances manquantes
class MockLogger:
    def info(self, msg, *args):
        print(f"INFO: {msg % args if args else msg}")
    
    def error(self, msg, *args):
        print(f"ERROR: {msg % args if args else msg}")
    
    def warning(self, msg, *args):
        print(f"WARNING: {msg % args if args else msg}")

class MockDatabaseError(Exception):
    pass

# Créer les modules mock
class MockUtils:
    logger = MockLogger()
    
    class exceptions:
        DatabaseError = MockDatabaseError

sys.modules['utils'] = MockUtils()
sys.modules['utils.logger'] = MockUtils()
sys.modules['utils.exceptions'] = MockUtils.exceptions()

# Importer la classe Database corrigée
from database import Database

def test_database_basic_operations():
    """Test des opérations de base de la base de données"""
    print("=== Test des opérations de base de la base de données ===")
    
    # Créer une base de données temporaire
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialiser la base de données
        print("1. Initialisation de la base de données...")
        db = Database(db_path)
        print("✓ Base de données initialisée avec succès")
        
        # Test de la propriété conn (compatibilité)
        print("2. Test de la propriété conn...")
        conn = db.conn
        if conn:
            conn.close()
            print("✓ Propriété conn accessible (compatibilité)")
        else:
            print("✗ Erreur: propriété conn non accessible")
            return False
        
        # Test de connexion
        print("3. Test de connexion...")
        if db.test_connection():
            print("✓ Test de connexion réussi")
        else:
            print("✗ Test de connexion échoué")
            return False
        
        # Test d'ajout de typologie
        print("4. Test d'ajout de typologie...")
        typology_id = db.add_typology("Test Typologie", "Description de test", True)
        if typology_id:
            print(f"✓ Typologie ajoutée avec ID: {typology_id}")
        else:
            print("✗ Erreur lors de l'ajout de typologie")
            return False
        
        # Test de récupération des typologies
        print("5. Test de récupération des typologies...")
        typologies = db.get_typologies()
        if typologies and len(typologies) > 0:
            print(f"✓ {len(typologies)} typologie(s) récupérée(s)")
            for typ in typologies:
                print(f"  - {typ['name']} (ID: {typ['id']})")
        else:
            print("✗ Aucune typologie récupérée")
            return False
        
        # Test de récupération des détails
        print("6. Test de récupération des détails...")
        details = db.get_typology_details(typology_id)
        if details:
            print(f"✓ Détails récupérés: {details['name']}")
        else:
            print("✗ Erreur lors de la récupération des détails")
            return False
        
        # Test de mise à jour
        print("7. Test de mise à jour...")
        db.update_typology(typology_id, "Test Typologie Modifiée", "Description modifiée", False)
        updated_details = db.get_typology_details(typology_id)
        if updated_details and updated_details['name'] == "Test Typologie Modifiée":
            print("✓ Typologie mise à jour avec succès")
        else:
            print("✗ Erreur lors de la mise à jour")
            return False
        
        # Test d'ajout d'éléments de stratégie
        print("8. Test d'ajout d'éléments de stratégie...")
        item_id = db.add_strategy_item("Test Item", "cluster", None, "Description item", "{}", typology_id)
        if item_id:
            print(f"✓ Élément de stratégie ajouté avec ID: {item_id}")
        else:
            print("✗ Erreur lors de l'ajout d'élément de stratégie")
            return False
        
        # Test de récupération des éléments de stratégie
        print("9. Test de récupération des éléments de stratégie...")
        items = db.get_strategy_items(typology_id)
        if items and len(items) > 0:
            print(f"✓ {len(items)} élément(s) de stratégie récupéré(s)")
        else:
            print("✗ Aucun élément de stratégie récupéré")
            return False
        
        # Test des statistiques
        print("10. Test des statistiques...")
        stats = db.get_statistics()
        if stats:
            print(f"✓ Statistiques récupérées: {stats}")
        else:
            print("✗ Erreur lors de la récupération des statistiques")
            return False
        
        # Test de suppression (doit échouer car il y a des éléments)
        print("11. Test de suppression avec éléments liés...")
        try:
            db.delete_typology(typology_id)
            print("✗ La suppression aurait dû échouer")
            return False
        except ValueError as e:
            print(f"✓ Suppression correctement bloquée: {e}")
        
        # Nettoyer les éléments et tester la suppression
        print("12. Test de nettoyage et suppression...")
        db.clear_strategy_items(typology_id)
        db.delete_typology(typology_id)
        remaining_typologies = db.get_typologies()
        if len(remaining_typologies) == 0:
            print("✓ Typologie supprimée avec succès")
        else:
            print("✗ Erreur lors de la suppression")
            return False
        
        print("✓ Tous les tests de base de données ont réussi!")
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors des tests: {e}")
        return False
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_error_handling():
    """Test de la gestion d'erreur"""
    print("\n=== Test de la gestion d'erreur ===")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        db = Database(db_path)
        
        # Test d'ajout avec nom vide
        print("1. Test d'ajout avec nom vide...")
        try:
            db.add_typology("", "Description", True)
            print("✗ L'ajout aurait dû échouer")
            return False
        except ValueError:
            print("✓ Erreur correctement gérée pour nom vide")
        
        # Test d'ajout avec nom en double
        print("2. Test d'ajout avec nom en double...")
        db.add_typology("Test", "Description", True)
        try:
            db.add_typology("Test", "Description 2", False)
            print("✗ L'ajout aurait dû échouer")
            return False
        except ValueError:
            print("✓ Erreur correctement gérée pour nom en double")
        
        # Test avec ID invalide
        print("3. Test avec ID invalide...")
        details = db.get_typology_details(99999)
        if details is None:
            print("✓ ID invalide correctement géré")
        else:
            print("✗ ID invalide mal géré")
            return False
        
        print("✓ Tous les tests de gestion d'erreur ont réussi!")
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors des tests: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_edge_cases():
    """Test des cas limites"""
    print("\n=== Test des cas limites ===")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        db = Database(db_path)
        
        # Test avec des noms contenant des espaces
        print("1. Test avec des noms contenant des espaces...")
        typology_id = db.add_typology("  Test avec espaces  ", "  Description  ", True)
        details = db.get_typology_details(typology_id)
        if details['name'] == "Test avec espaces":
            print("✓ Espaces correctement supprimés")
        else:
            print(f"✗ Espaces mal gérés: '{details['name']}'")
            return False
        
        # Test avec description None
        print("2. Test avec description None...")
        typology_id2 = db.add_typology("Test None", None, False)
        details2 = db.get_typology_details(typology_id2)
        if details2['description'] == "":
            print("✓ Description None correctement gérée")
        else:
            print(f"✗ Description None mal gérée: '{details2['description']}'")
            return False
        
        # Test avec base de données vide
        print("3. Test avec base de données vide...")
        db.clear_strategy_items(typology_id)
        db.clear_strategy_items(typology_id2)
        db.delete_typology(typology_id)
        db.delete_typology(typology_id2)
        
        empty_typologies = db.get_typologies()
        empty_stats = db.get_statistics()
        empty_names = db.get_typology_names()
        
        if (len(empty_typologies) == 0 and 
            empty_stats['typologies_count'] == 0 and 
            len(empty_names) == 0):
            print("✓ Base de données vide correctement gérée")
        else:
            print("✗ Base de données vide mal gérée")
            return False
        
        print("✓ Tous les tests de cas limites ont réussi!")
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors des tests: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

def main():
    """Fonction principale de test"""
    print("Démarrage des tests de validation des corrections...")
    print("=" * 60)
    
    success = True
    
    # Test des opérations de base
    if not test_database_basic_operations():
        success = False
    
    # Test de la gestion d'erreur
    if not test_error_handling():
        success = False
    
    # Test des cas limites
    if not test_edge_cases():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ TOUS LES TESTS ONT RÉUSSI!")
        print("Les corrections apportées fonctionnent correctement.")
        return 0
    else:
        print("✗ CERTAINS TESTS ONT ÉCHOUÉ!")
        print("Des problèmes subsistent dans les corrections.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
