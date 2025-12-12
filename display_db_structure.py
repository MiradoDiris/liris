#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test minimal de sauvegarde SQLite
À exécuter dans votre environnement pour diagnostiquer
"""

from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager

def test_minimal_save():
    """Test minimal de sauvegarde"""
    print("=" * 80)
    print("TEST MINIMAL DE SAUVEGARDE")
    print("=" * 80)
    
    # 1. Initialiser la DB
    print("\n1. Initialisation de la base de données...")
    db = DatasetDatabase("data/test_liris.db")
    print(f"   ✅ DB initialisée: {db.db_path}")
    print(f"   ✅ Connection: {db.connection is not None}")
    
    # 2. Créer un project manager
    print("\n2. Création du project manager...")
    manager = DatasetProjectManager(db)
    print(f"   ✅ Manager créé")
    
    # 3. Créer un projet minimal
    print("\n3. Création d'un projet minimal...")
    project_name = "TEST_MINIMAL"
    success = manager.create_new_project(project_name, "Test de diagnostic")
    print(f"   Résultat create_new_project: {success}")
    print(f"   current_project_name: {manager.current_project_name}")
    print(f"   current_project_data: {manager.current_project_data is not None}")
    
    # 4. Vérifier la structure
    print("\n4. Vérification de la structure...")
    if manager.current_project_data:
        print(f"   Structure: {manager.current_project_data.keys()}")
        print(f"   Nom: {manager.current_project_data.get('nom')}")
        print(f"   Typologies: {manager.current_project_data.get('typologies')}")
    
    # 5. Tenter la sauvegarde
    print("\n5. Tentative de sauvegarde...")
    save_success = manager.save_project()
    print(f"   Résultat save_project: {save_success}")
    
    # 6. Vérifier en base
    print("\n6. Vérification en base de données...")
    cursor = db.connection.cursor()
    cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
    result = cursor.fetchone()
    
    if result:
        print(f"   ✅ Projet trouvé en base!")
        print(f"      ID: {result['id']}")
        print(f"      Nom: {result['name']}")
        print(f"      Description: {result['description']}")
    else:
        print(f"   ❌ Projet NON trouvé en base!")
        
        # Debug: Lister tous les projets
        cursor.execute("SELECT name FROM projects")
        all_projects = cursor.fetchall()
        print(f"   Projets existants: {[p['name'] for p in all_projects]}")
    
    # 7. Cleanup
    print("\n7. Nettoyage...")
    db.close()
    print("   ✅ Connexion fermée")
    
    print("\n" + "=" * 80)
    if result:
        print("🎉 TEST RÉUSSI: Le projet a été sauvegardé en SQLite")
    else:
        print("❌ TEST ÉCHOUÉ: Le projet n'est PAS en SQLite")
    print("=" * 80)

if __name__ == "__main__":
    test_minimal_save()