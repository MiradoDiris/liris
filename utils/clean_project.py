"""
Module de nettoyage de projet pour ProjectConfigWidget.
Supprime les fichiers non-essentiels avant le traitement.
"""

import os
import shutil
from typing import Dict, List, Set, Tuple
from utils.logger import logger


class ProjectCleaner:
    """Nettoie un projet en supprimant les fichiers non-essentiels."""
    
    # Dossiers à supprimer
    UNWANTED_DIRS: Set[str] = {
        '.git', '.vscode', '__pycache__', '.idea', 'node_modules', 
        '.mypy_cache', '.pytest_cache', '.venv', 'venv', 'env',
        '.tox', '.eggs', '*.egg-info', 'dist', 'build',
        '.coverage', 'htmlcov', '.sass-cache', '.cache',
        'coverage', '.nyc_output', 'vendor', '.bundle',
        '.next', '.nuxt', '.output', 'out', '.vercel'
    }

    # Extensions de fichiers à supprimer
    UNWANTED_FILES_EXT: Set[str] = {
        # Bases de données
        '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal',
        # Environnement et config
        '.env', '.env.local', '.env.development', '.env.production',
        # Logs
        '.log',
        # Python compilé
        '.pyc', '.pyo', '.pyd',
        # Système
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
        # Packages
        '.whl', '.egg',
        # Temporaires
        '.tmp', '.temp', '.swp', '.swo',
        # Compilation
        '.o', '.obj', '.exe', '.dll', '.so', '.dylib',
        # Couverture de code
        '.coverage',
        # Images et icônes
        '.ico', '.icon', '.icns', '.png', '.jpg', '.jpeg', 
        '.gif', '.svg', '.bmp', '.webp', '.tiff', '.psd',
    }

    # Fichiers spécifiques à supprimer
    UNWANTED_FILES: Set[str] = {
        '.gitignore', '.gitattributes', '.gitmodules',
        '.dockerignore', 'Dockerfile', 'docker-compose.yml',
        '.editorconfig', '.eslintrc', '.prettierrc',
        'package-lock.json', 'yarn.lock', 'poetry.lock',
        'Pipfile.lock', 'requirements-dev.txt',
        '.pylintrc', 'pytest.ini', 'setup.cfg', 'tox.ini',
        'Makefile', '.travis.yml', '.gitlab-ci.yml',
        'LICENSE', 'CHANGELOG.md',
        'favicon.ico', 'apple-touch-icon.png', 
        'android-chrome-192x192.png', 'android-chrome-512x512.png',
        'mstile-150x150.png',
    }

    def __init__(self, keep_readme: bool = True):
        """
        Initialise le nettoyeur.
        
        Args:
            keep_readme: Si True, conserve les fichiers README
        """
        self.keep_readme = keep_readme
        self.stats = {
            'dirs_deleted': 0,
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }

    def clean_project(self, root_path: str) -> Dict[str, any]:
        """
        Nettoie un projet en supprimant les fichiers non-essentiels.
        
        Args:
            root_path: Chemin du projet à nettoyer
            
        Returns:
            Dictionnaire avec les statistiques de nettoyage
        """
        if not os.path.isdir(root_path):
            logger.error(f"❌ Le chemin '{root_path}' n'est pas un dossier valide")
            return self.stats

        logger.info(f"🧹 Démarrage du nettoyage de: {root_path}")
        
        # Préparer les fichiers à exclure
        unwanted_files = self.UNWANTED_FILES.copy()
        if self.keep_readme:
            unwanted_files.discard('README.md')

        # Parcourir récursivement
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            # Supprimer les dossiers indésirables
            self._clean_directories(dirpath, dirnames)
            
            # Supprimer les fichiers indésirables
            self._clean_files(dirpath, filenames, unwanted_files)

        self._log_summary()
        return self.stats

    def _clean_directories(self, dirpath: str, dirnames: List[str]) -> None:
        """Supprime les dossiers indésirables."""
        dirs_to_remove = []
        
        for dirname in dirnames:
            if self._should_delete_dir(dirname):
                full_dir_path = os.path.join(dirpath, dirname)
                
                # Calculer la taille avant suppression
                size = self._get_directory_size(full_dir_path)
                
                try:
                    shutil.rmtree(full_dir_path)
                    self.stats['dirs_deleted'] += 1
                    self.stats['bytes_freed'] += size
                    logger.debug(f"📁 Dossier supprimé: {dirname}")
                    dirs_to_remove.append(dirname)
                except Exception as e:
                    error_msg = f"Impossible de supprimer {full_dir_path}: {e}"
                    self.stats['errors'].append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
        
        # Retirer les dossiers supprimés de la liste
        for dirname in dirs_to_remove:
            dirnames.remove(dirname)

    def _clean_files(self, dirpath: str, filenames: List[str], 
                     unwanted_files: Set[str]) -> None:
        """Supprime les fichiers indésirables."""
        for filename in filenames:
            if self._should_delete_file(filename, unwanted_files):
                full_file_path = os.path.join(dirpath, filename)
                
                # Obtenir la taille avant suppression
                try:
                    size = os.path.getsize(full_file_path)
                except:
                    size = 0
                
                try:
                    os.remove(full_file_path)
                    self.stats['files_deleted'] += 1
                    self.stats['bytes_freed'] += size
                    logger.debug(f"📄 Fichier supprimé: {filename}")
                except Exception as e:
                    error_msg = f"Impossible de supprimer {full_file_path}: {e}"
                    self.stats['errors'].append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")

    def _should_delete_dir(self, dirname: str) -> bool:
        """
        Détermine si un dossier doit être supprimé.
        
        Ordre de priorité :
        1. .git est TOUJOURS supprimé
        2. Exceptions explicites sont TOUJOURS gardées
        3. Liste noire des dossiers
        4. Dossiers cachés (.)
        """
        # ✅ PRIORITÉ 1 : .git est TOUJOURS supprimé
        if dirname == '.git':
            logger.debug(f"🗑️ .git détecté pour suppression")
            return True
        
        # ✅ PRIORITÉ 2 : Exceptions explicites (à garder)
        KEEP_DIRS = {'.github', '.vscode'}
        if dirname in KEEP_DIRS:
            logger.debug(f"✋ Dossier protégé : {dirname}")
            return False
        
        # ✅ PRIORITÉ 3 : Liste noire explicite
        if dirname in self.UNWANTED_DIRS:
            logger.debug(f"🗑️ Dossier dans liste noire : {dirname}")
            return True
        
        # ✅ PRIORITÉ 4 : Tous les autres dossiers cachés
        if dirname.startswith('.'):
            logger.debug(f"🗑️ Dossier caché détecté : {dirname}")
            return True
        
        return False

    def _should_delete_file(self, filename: str, unwanted_files: Set[str]) -> bool:
        """Détermine si un fichier doit être supprimé."""
        # Vérifier par nom exact
        if filename in unwanted_files:
            return True
        
        # Vérifier par extension
        if any(filename.endswith(ext) for ext in self.UNWANTED_FILES_EXT):
            return True
        
        # Vérifier les fichiers cachés (sauf .htaccess)
        if filename.startswith('.') and filename not in {'.htaccess'}:
            return True
        
        return False

    def _get_directory_size(self, path: str) -> int:
        """Calcule la taille totale d'un dossier en octets."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except:
                        pass
        except:
            pass
        return total_size

    def _log_summary(self) -> None:
        """Affiche un résumé du nettoyage."""
        logger.info("=" * 60)
        logger.info("=== RÉSUMÉ DU NETTOYAGE ===")
        logger.info("=" * 60)
        logger.info(f"📁 Dossiers supprimés: {self.stats['dirs_deleted']}")
        logger.info(f"📄 Fichiers supprimés: {self.stats['files_deleted']}")
        logger.info(f"💾 Espace libéré: {self._format_bytes(self.stats['bytes_freed'])}")
        
        if self.stats['errors']:
            logger.warning(f"⚠️ Erreurs rencontrées: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:  # Afficher les 5 premières
                logger.warning(f"   • {error}")
        else:
            logger.info("✅ Aucune erreur rencontrée")

    def _format_bytes(self, bytes_size: int) -> str:
        """Formate une taille en octets de manière lisible."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"

    def get_cleanable_items(self, root_path: str) -> Tuple[List[str], List[str]]:
        """
        Analyse un projet et retourne les items qui seraient supprimés.
        Utile pour prévisualisation avant nettoyage.
        
        Args:
            root_path: Chemin du projet à analyser
            
        Returns:
            Tuple de (liste_dossiers, liste_fichiers) à supprimer
        """
        dirs_to_clean = []
        files_to_clean = []
        
        unwanted_files = self.UNWANTED_FILES.copy()
        if self.keep_readme:
            unwanted_files.discard('README.md')

        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            # Analyser les dossiers
            for dirname in dirnames:
                if self._should_delete_dir(dirname):
                    dirs_to_clean.append(os.path.join(dirpath, dirname))
            
            # Analyser les fichiers
            for filename in filenames:
                if self._should_delete_file(filename, unwanted_files):
                    files_to_clean.append(os.path.join(dirpath, filename))

        return dirs_to_clean, files_to_clean