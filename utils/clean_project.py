import os
import shutil

# Extensions et dossiers à supprimer
UNWANTED_DIRS = {'.git', '.vscode', '__pycache__', '.idea', 'node_modules', '.mypy_cache', '.pytest_cache'}
UNWANTED_FILES_EXT = {'.db', '.env', '.log', '.pyc', '.pyo', '.pyd', '.sqlite3', '.DS_Store'}

def delete_unwanted_items(root_path: str):
    """Supprime les fichiers et dossiers inutiles dans un projet."""
    deleted = {'dirs': [], 'files': []}

    for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
        # Supprimer les dossiers indésirables
        for dirname in list(dirnames):
            if dirname in UNWANTED_DIRS:
                full_dir_path = os.path.join(dirpath, dirname)
                try:
                    shutil.rmtree(full_dir_path)
                    deleted['dirs'].append(full_dir_path)
                    print(f"[DIR SUPPRIMÉ] {full_dir_path}")
                except Exception as e:
                    print(f"[ERREUR] Impossible de supprimer {full_dir_path}: {e}")
                # Retirer de la liste pour éviter la descente dans ce dossier
                dirnames.remove(dirname)

        # Supprimer les fichiers indésirables
        for filename in filenames:
            if any(filename.endswith(ext) for ext in UNWANTED_FILES_EXT):
                full_file_path = os.path.join(dirpath, filename)
                try:
                    os.remove(full_file_path)
                    deleted['files'].append(full_file_path)
                    print(f"[FICHIER SUPPRIMÉ] {full_file_path}")
                except Exception as e:
                    print(f"[ERREUR] Impossible de supprimer {full_file_path}: {e}")

    print("\n=== Nettoyage terminé ===")
    print(f"Total dossiers supprimés : {len(deleted['dirs'])}")
    print(f"Total fichiers supprimés : {len(deleted['files'])}")

if __name__ == "__main__":
    project_dir = input("Chemin du projet à nettoyer : ").strip()

    if not os.path.isdir(project_dir):
        print("❌ Le chemin spécifié n'est pas un dossier valide.")
    else:
        delete_unwanted_items(project_dir)
