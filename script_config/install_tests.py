#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📦 INSTALLATION - Copie les fichiers de test aux bons emplacements
"""

import shutil
from pathlib import Path
import sys

def install_file(source: Path, dest: Path, description: str) -> bool:
    """Copie un fichier avec vérification"""
    try:
        if not source.exists():
            print(f"   ❌ {description} - Source non trouvée: {source}")
            return False
        
        # Créer le répertoire destination si nécessaire
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup si le fichier existe déjà
        if dest.exists():
            backup = dest.with_suffix(dest.suffix + '.backup')
            shutil.copy2(dest, backup)
            print(f"   💾 Backup: {backup.name}")
        
        # Copier
        shutil.copy2(source, dest)
        print(f"   ✅ {description}")
        print(f"      → {dest}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ {description} - Erreur: {e}")
        return False


def main():
    print("\n" + "=" * 80)
    print("📦 INSTALLATION DES FICHIERS DE TEST")
    print("=" * 80 + "\n")
    
    # Déterminer les chemins
    # Les fichiers sources sont dans le répertoire courant ou outputs
    current_dir = Path.cwd()
    
    # Vérifier si on est dans le bon répertoire
    if not (current_dir / "context_weaver").exists():
        print("❌ Erreur: Ce script doit être exécuté depuis la racine du projet")
        print("   (le répertoire qui contient 'context_weaver/')")
        return 1
    
    results = []
    
    print("📁 Installation des fichiers de test:\n")
    
    # 1. Diagnostic pipeline
    results.append(install_file(
        source=Path("diagnostic_pipeline.py"),
        dest=Path("script_config/diagnostic_pipeline.py"),
        description="Diagnostic Pipeline"
    ))
    
    # 2. Test rapide
    results.append(install_file(
        source=Path("test_main_pipeline_quick.py"),
        dest=Path("script_config/test_main_pipeline_quick.py"),
        description="Test Rapide"
    ))
    
    # 3. Suite de tests complète
    results.append(install_file(
        source=Path("test_main_pipeline.py"),
        dest=Path("script_config/test_main_pipeline.py"),
        description="Suite de Tests Complète"
    ))
    
    # 4. README
    results.append(install_file(
        source=Path("README_TESTS.md"),
        dest=Path("script_config/README_TESTS.md"),
        description="Documentation"
    ))
    
    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ")
    print("=" * 80 + "\n")
    
    success_count = sum(results)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"✅ {success_count}/{total_count} fichiers installés avec succès\n")
        print("🚀 Vous pouvez maintenant exécuter:")
        print("   python script_config/diagnostic_pipeline.py")
        print("   python script_config/test_main_pipeline_quick.py")
        print("   python script_config/test_main_pipeline.py")
    else:
        print(f"⚠️ {success_count}/{total_count} fichiers installés")
        print("\nVérifiez les erreurs ci-dessus.")
    
    print("\n" + "=" * 80 + "\n")
    
    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())