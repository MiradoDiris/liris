"""
Script de migration pour corriger le format des données de projet
À exécuter une seule fois pour nettoyer la base de données existante
"""

import logging
import sys
import os

# Ajouter le chemin du projet au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.dataset_database import DatasetDatabase

logger = logging.getLogger(__name__)


def migrate_project_data_format():
    """
    Migre tous les projets existants vers le format standard
    Format attendu: {'nom': '...', 'description': '...', 'typologies': [...]}
    """
    print("=" * 60)
    print("MIGRATION: Correction du format des données de projet")
    print("=" * 60)
    
    try:
        # Initialiser la base de données
        db = DatasetDatabase()
        
        # Récupérer tous les projets
        projects = db.get_all_projects()
        print(f"\n📊 Projets trouvés: {len(projects)}")
        
        if not projects:
            print("✅ Aucun projet à migrer")
            return True
        
        migrated_count = 0
        error_count = 0
        
        for project in projects:
            project_name = project.get('name', '')
            print(f"\n--- Analyse du projet: {project_name} ---")
            
            try:
                # Charger les données complètes
                project_data = db.get_dataset_projet(project_name)
                
                if not project_data:
                    print(f"❌ Impossible de charger '{project_name}'")
                    error_count += 1
                    continue
                
                # Vérifier le format
                needs_migration = False
                
                if isinstance(project_data, list):
                    print(f"⚠️  Format: LISTE (legacy) - {len(project_data)} typologie(s)")
                    needs_migration = True
                    
                elif isinstance(project_data, dict):
                    has_nom = 'nom' in project_data
                    has_desc = 'description' in project_data
                    has_typo = 'typologies' in project_data
                    typo_is_list = isinstance(project_data.get('typologies'), list) if has_typo else False
                    
                    print(f"   Format: DICT")
                    print(f"   - 'nom': {'✅' if has_nom else '❌'}")
                    print(f"   - 'description': {'✅' if has_desc else '❌'}")
                    print(f"   - 'typologies': {'✅' if has_typo else '❌'}")
                    if has_typo:
                        print(f"   - typologies is list: {'✅' if typo_is_list else '❌'}")
                    
                    needs_migration = not (has_nom and has_desc and has_typo and typo_is_list)
                
                else:
                    print(f"❌ Format inconnu: {type(project_data)}")
                    error_count += 1
                    continue
                
                if needs_migration:
                    print(f"🔧 Migration nécessaire...")
                    
                    # Normaliser les données
                    if isinstance(project_data, list):
                        normalized_data = {
                            "nom": project_name,
                            "description": "",
                            "typologies": project_data
                        }
                    else:
                        normalized_data = {
                            "nom": project_data.get('nom', project_name),
                            "description": project_data.get('description', ''),
                            "typologies": project_data.get('typologies', [])
                        }
                        
                        # S'assurer que typologies est une liste
                        if not isinstance(normalized_data['typologies'], list):
                            print(f"   ⚠️  Conversion de 'typologies' en liste vide")
                            normalized_data['typologies'] = []
                    
                    # Sauvegarder
                    success = db.save_dataset_projet(project_name, normalized_data)
                    
                    if success:
                        print(f"✅ Migration réussie")
                        migrated_count += 1
                        
                        # Vérifier la migration
                        verify_data = db.get_dataset_projet(project_name)
                        if isinstance(verify_data, dict) and 'typologies' in verify_data:
                            typo_count = len(verify_data.get('typologies', []))
                            print(f"   ✓ Vérification: {typo_count} typologie(s)")
                        else:
                            print(f"   ⚠️  Vérification: format inattendu")
                    else:
                        print(f"❌ Échec de la migration")
                        error_count += 1
                else:
                    print(f"✅ Format correct, pas de migration nécessaire")
                    
            except Exception as e:
                print(f"❌ Erreur pour '{project_name}': {e}")
                import traceback
                traceback.print_exc()
                error_count += 1
        
        # Résumé
        print("\n" + "=" * 60)
        print("RÉSUMÉ DE LA MIGRATION")
        print("=" * 60)
        print(f"Projets analysés: {len(projects)}")
        print(f"Projets migrés: {migrated_count}")
        print(f"Erreurs: {error_count}")
        print(f"Statut: {'✅ SUCCÈS' if error_count == 0 else '⚠️  AVEC ERREURS'}")
        print("=" * 60)
        
        db.close()
        return error_count == 0
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n⚠️  ATTENTION: Cette migration va modifier la base de données")
    print("   Assurez-vous d'avoir une sauvegarde avant de continuer")
    
    response = input("\nContinuer? (oui/non): ").strip().lower()
    
    if response in ['oui', 'o', 'yes', 'y']:
        success = migrate_project_data_format()
        sys.exit(0 if success else 1)
    else:
        print("\n❌ Migration annulée")
        sys.exit(0)