"""
🔧 CORRECTION : Système de nettoyage renforcé
Exclusions garanties pour .git, env, node_modules, etc.
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Set
from utils.logger import logger


class ProjectCleaner:
    """
    ✅ VERSION CORRIGÉE avec exclusions renforcées
    Filtre les fichiers et dossiers inutiles lors du scan de projets.
    """
    
    # 🗑️ DOSSIERS À EXCLURE - PRIORITÉ ABSOLUE
    CRITICAL_EXCLUDED_DIRECTORIES = {
        # Version Control (PRIORITÉ 1)
        '.git',
        
        # Environnements virtuels Python (PRIORITÉ 1)
        'env', 'venv', '.env', '.venv', 'virtualenv',
        'ENV', 'VENV', '.ENV', '.VENV',
        
        # Node.js (PRIORITÉ 1)
        'node_modules',
        
        # Python cache (PRIORITÉ 1)
        '__pycache__',
        
        # Build (PRIORITÉ 1)
        'dist', 'build', 'target', 'out',
    }
    
    # 🗑️ DOSSIERS À EXCLURE - STANDARD
    EXCLUDED_DIRECTORIES = {
        # Version Control
        '.svn', '.hg', '.bzr', 'CVS',
        
        # Python
        '*.egg-info', '.eggs', '.pytest_cache', '.tox', 
        '.coverage', '.mypy_cache', 'pip-wheel-metadata',
        '.python-version',
        
        # Node.js / JavaScript
        'bower_components', 'jspm_packages',
        '.npm', '.yarn', '.pnp', 'npm-debug.log*', 
        'yarn-debug.log*', 'yarn-error.log*', 
        '.next', '.nuxt', '.cache',
        
        # IDEs et éditeurs
        '.vscode', '.idea', '*.swp', '*.swo', '*~',
        '.project', '.settings', '.classpath',
        '.vs', '*.suo', '*.user', '*.userosscache',
        
        # OS
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
        '$RECYCLE.BIN', '.Trash-*',
        
        # Build systems
        '.gradle', 'cmake-build-*',
        
        # Rust
        'Cargo.lock',
        
        # Go
        'vendor', 'bin', 'pkg',
        
        # Java / Maven / Gradle
        '.m2',
        
        # Ruby
        '.bundle', 'vendor/bundle', 'vendor/cache',
        
        # Logs et temporaires
        'logs', 'log', 'tmp', 'temp', '.tmp',
        
        # Documentation générée
        'docs/_build', 'site', '_site', 'public',
        
        # Autres
        '.sass-cache', '.parcel-cache', '.turbo',
        'coverage', 'htmlcov', '.nyc_output',
    }
    
    # 📄 FICHIERS À EXCLURE
    EXCLUDED_FILES = {
        # Lockfiles
        'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
        'Pipfile.lock', 'poetry.lock', 'Gemfile.lock',
        'composer.lock', 'Cargo.lock', 'go.sum',
        
        # Configs locales et secrets
        '.env', '.env.local', '.env.*.local',
        'secrets.yml', 'credentials.yml',
        '.env.development', '.env.production', '.env.test',
        
        # OS
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
        
        # Logs
        '*.log', 'npm-debug.log*', 'yarn-debug.log*',
        
        # Backups
        '*.swp', '*.swo', '*~', '*.bak', '*.backup',
        
        # Compiled
        '*.pyc', '*.pyo', '*.class', '*.o', '*.obj',
        
        # Certificates
        '*.pem', '*.key', '*.crt', '*.cer',
    }
    
    # ✅ EXTENSIONS DE CODE À GARDER
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.tsx', '.jsx',
        '.java', '.c', '.cpp', '.h', '.hpp',
        '.cs', '.go', '.rs', '.rb', '.php',
        '.swift', '.kt', '.scala', '.r',
        '.lua', '.perl', '.pl', '.sh', '.bash',
        '.ps1', '.bat', '.cmd',
        '.html', '.htm', '.css', '.scss', '.sass',
        '.less', '.vue', '.svelte', '.astro',
        '.json', '.yaml', '.yml', '.toml', '.ini',
        '.xml', '.conf', '.config',
        '.md', '.rst', '.txt', '.adoc',
        '.sql', '.sqlite', '.db',
        '.graphql', '.proto', '.thrift',
    }
    
    # 🔧 FICHIERS DE CONFIG IMPORTANTS
    IMPORTANT_FILES = {
        'README.md', 'readme.md', 'README.txt', 'README',
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'setup.py', 'setup.cfg', 'pyproject.toml',
        'package.json', 'tsconfig.json', 'webpack.config.js',
        'Dockerfile', 'docker-compose.yml', '.dockerignore',
        'Makefile', 'CMakeLists.txt', 'build.gradle',
        'pom.xml', 'Gemfile', 'Cargo.toml', 'go.mod',
        '.gitignore', '.gitattributes',
    }
    
    def __init__(self, 
                 exclude_lockfiles: bool = True,
                 exclude_tests: bool = False,
                 max_file_size_mb: float = 10.0,
                 custom_excludes: Set[str] = None):
        self.exclude_lockfiles = exclude_lockfiles
        self.exclude_tests = exclude_tests
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        
        # ✅ COMBINER CRITIQUES + STANDARD
        self.excluded_dirs = self.CRITICAL_EXCLUDED_DIRECTORIES.copy()
        self.excluded_dirs.update(self.EXCLUDED_DIRECTORIES)
        
        self.excluded_files = self.EXCLUDED_FILES.copy()
        
        if custom_excludes:
            self.excluded_dirs.update(custom_excludes)
        
        if exclude_tests:
            self.excluded_dirs.update({
                'tests', 'test', '__tests__', 'spec',
                'e2e', 'integration', 'unit'
            })
        
        # Stats
        self.stats = {
            'total_scanned': 0,
            'directories_excluded': 0,
            'files_excluded': 0,
            'files_included': 0,
            'total_size_excluded_mb': 0.0,
            'total_size_included_mb': 0.0,
            'critical_dirs_found': [],
        }
    
    def should_exclude_directory(self, dir_name: str, dir_path: str) -> bool:
        """
        🔧 VERSION CORRIGÉE : Vérifie avec PRIORITÉ sur les critiques
        """
        self.stats['total_scanned'] += 1
        
        # 🛡️ VÉRIFICATION PRIORITAIRE : Dossiers critiques
        if dir_name in self.CRITICAL_EXCLUDED_DIRECTORIES:
            self.stats['directories_excluded'] += 1
            self.stats['critical_dirs_found'].append(dir_path)
            logger.warning(f"🛡️ CRITIQUE EXCLU: {dir_name} (chemin: {dir_path})")
            return True
        
        # Vérification case-insensitive pour env/venv
        dir_name_lower = dir_name.lower()
        if dir_name_lower in {'env', 'venv', '.env', '.venv', 'virtualenv'}:
            self.stats['directories_excluded'] += 1
            self.stats['critical_dirs_found'].append(dir_path)
            logger.warning(f"🛡️ CRITIQUE EXCLU (case-insensitive): {dir_name}")
            return True
        
        # Vérification exacte standard
        if dir_name in self.excluded_dirs:
            self.stats['directories_excluded'] += 1
            logger.debug(f"🗑️ Exclusion répertoire (exact): {dir_name}")
            return True
        
        # Vérification wildcards
        for pattern in self.excluded_dirs:
            if fnmatch.fnmatch(dir_name, pattern):
                self.stats['directories_excluded'] += 1
                logger.debug(f"🗑️ Exclusion répertoire (pattern): {dir_name} (match: {pattern})")
                return True
        
        # Répertoires cachés
        if dir_name.startswith('.') and dir_name not in {'.github', '.vscode'}:
            self.stats['directories_excluded'] += 1
            logger.debug(f"🗑️ Exclusion répertoire caché: {dir_name}")
            return True
        
        return False
    
    def should_exclude_file(self, file_name: str, file_path: str) -> bool:
        """
        Détermine si un fichier doit être exclu.
        """
        self.stats['total_scanned'] += 1
        
        # Fichiers importants toujours inclus
        if file_name in self.IMPORTANT_FILES:
            logger.debug(f"✅ Fichier important inclus: {file_name}")
            return False
        
        # Vérification taille
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size_bytes:
                size_mb = file_size / (1024 * 1024)
                self.stats['files_excluded'] += 1
                self.stats['total_size_excluded_mb'] += size_mb
                logger.debug(f"🗑️ Exclusion fichier (trop gros): {file_name} ({size_mb:.2f} MB)")
                return True
        except OSError:
            pass
        
        # Vérification extension
        _, ext = os.path.splitext(file_name)
        ext_lower = ext.lower()
        
        # Si extension de code, GARDER
        if ext_lower in self.CODE_EXTENSIONS:
            if file_name not in self.excluded_files:
                return False
        
        # Vérification nom exact
        if file_name in self.excluded_files:
            self.stats['files_excluded'] += 1
            logger.debug(f"🗑️ Exclusion fichier (exact): {file_name}")
            return True
        
        # Vérification wildcards
        for pattern in self.excluded_files:
            if fnmatch.fnmatch(file_name, pattern):
                self.stats['files_excluded'] += 1
                logger.debug(f"🗑️ Exclusion fichier (pattern): {file_name}")
                return True
        
        # Lockfiles
        if self.exclude_lockfiles and any(lock in file_name.lower() for lock in ['lock', 'lockfile']):
            self.stats['files_excluded'] += 1
            logger.debug(f"🗑️ Exclusion lockfile: {file_name}")
            return True
        
        # Fichiers cachés
        if file_name.startswith('.') and file_name not in self.IMPORTANT_FILES:
            self.stats['files_excluded'] += 1
            logger.debug(f"🗑️ Exclusion fichier caché: {file_name}")
            return True
        
        # Extensions non reconnues
        if ext_lower and ext_lower not in self.CODE_EXTENSIONS:
            if file_name not in {'Makefile', 'Dockerfile', 'LICENSE', 'README'}:
                self.stats['files_excluded'] += 1
                logger.debug(f"🗑️ Exclusion extension inconnue: {file_name}")
                return True
        
        return False
    
    def should_include_file(self, file_name: str, file_path: str) -> bool:
        """
        Version positive: Détermine si un fichier doit être INCLUS.
        """
        included = not self.should_exclude_file(file_name, file_path)
        
        if included:
            self.stats['files_included'] += 1
            try:
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                self.stats['total_size_included_mb'] += size_mb
            except OSError:
                pass
        
        return included
    
    def clean_directory_tree(self, root_path: str) -> List[str]:
        """
        🔧 VERSION CORRIGÉE : Parcourt avec double vérification
        """
        included_files = []
        
        logger.info(f"🧹 Nettoyage du projet: {root_path}")
        logger.info(f"   Paramètres:")
        logger.info(f"      • Exclure lockfiles: {self.exclude_lockfiles}")
        logger.info(f"      • Exclure tests: {self.exclude_tests}")
        logger.info(f"      • Taille max fichier: {self.max_file_size_bytes / (1024*1024):.1f} MB")
        
        # 🔍 PRÉ-SCAN : Détecter les dossiers critiques
        logger.info(f"\n🔍 Pré-scan des dossiers critiques...")
        critical_found = []
        for root, dirs, _ in os.walk(root_path):
            for d in dirs:
                if d in self.CRITICAL_EXCLUDED_DIRECTORIES or d.lower() in {'env', 'venv', '.env', '.venv'}:
                    full_path = os.path.join(root, d)
                    rel_path = os.path.relpath(full_path, root_path)
                    critical_found.append((d, rel_path))
        
        if critical_found:
            logger.info(f"   🛡️ {len(critical_found)} dossier(s) critique(s) détecté(s):")
            for name, path in critical_found[:10]:  # Limiter affichage
                logger.info(f"      • {path}")
            if len(critical_found) > 10:
                logger.info(f"      ... et {len(critical_found) - 10} autres")
        else:
            logger.info(f"   ✅ Aucun dossier critique détecté")
        
        # 🧹 SCAN PRINCIPAL avec filtrage
        logger.info(f"\n🧹 Scan principal avec filtrage...")
        for root, dirs, files in os.walk(root_path):
            # ✅ FILTRER les répertoires IN-PLACE
            original_count = len(dirs)
            dirs[:] = [
                d for d in dirs 
                if not self.should_exclude_directory(d, os.path.join(root, d))
            ]
            excluded_count = original_count - len(dirs)
            
            if excluded_count > 0:
                rel_root = os.path.relpath(root, root_path)
                logger.debug(f"   📂 {rel_root}: {excluded_count} sous-dossier(s) exclu(s)")
            
            # ✅ FILTRER les fichiers
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                # 🛡️ DOUBLE VÉRIFICATION : Le chemin contient-il un dossier critique?
                rel_path = os.path.relpath(file_path, root_path)
                path_parts = Path(rel_path).parts
                
                is_in_critical = False
                for part in path_parts:
                    if (part in self.CRITICAL_EXCLUDED_DIRECTORIES or 
                        part.lower() in {'env', 'venv', '.env', '.venv', 'node_modules', '__pycache__'}):
                        logger.debug(f"   🛡️ Fichier dans dossier critique exclu: {rel_path}")
                        is_in_critical = True
                        break
                
                if is_in_critical:
                    continue
                
                # Vérification normale
                if self.should_include_file(file_name, file_path):
                    included_files.append(file_path)
        
        # Log des statistiques
        self.log_statistics()
        
        return included_files
    
    def log_statistics(self):
        """Affiche les statistiques de nettoyage."""
        logger.info("=" * 60)
        logger.info("📊 STATISTIQUES DE NETTOYAGE")
        logger.info("=" * 60)
        logger.info(f"Total scanné: {self.stats['total_scanned']}")
        logger.info(f"")
        
        # Dossiers critiques trouvés
        if self.stats['critical_dirs_found']:
            logger.info(f"🛡️ DOSSIERS CRITIQUES EXCLUS: {len(self.stats['critical_dirs_found'])}")
            for path in self.stats['critical_dirs_found'][:5]:
                logger.info(f"   • {path}")
            if len(self.stats['critical_dirs_found']) > 5:
                logger.info(f"   ... et {len(self.stats['critical_dirs_found']) - 5} autres")
            logger.info(f"")
        
        logger.info(f"❌ EXCLUS:")
        logger.info(f"   • Répertoires: {self.stats['directories_excluded']}")
        logger.info(f"   • Fichiers: {self.stats['files_excluded']}")
        logger.info(f"   • Taille totale: {self.stats['total_size_excluded_mb']:.2f} MB")
        logger.info(f"")
        logger.info(f"✅ INCLUS:")
        logger.info(f"   • Fichiers: {self.stats['files_included']}")
        logger.info(f"   • Taille totale: {self.stats['total_size_included_mb']:.2f} MB")
        logger.info(f"")
        
        if self.stats['total_scanned'] > 0:
            exclusion_rate = (self.stats['files_excluded'] / self.stats['total_scanned']) * 100
            logger.info(f"📉 Taux d'exclusion: {exclusion_rate:.1f}%")
        
        logger.info("=" * 60)
    
    def get_filtered_file_list(self, root_path: str) -> List[str]:
        """Alias pour clean_directory_tree."""
        return self.clean_directory_tree(root_path)


# 🔧 FACTORY FUNCTIONS

def create_strict_cleaner() -> ProjectCleaner:
    """Nettoyeur STRICT : Exclut tout sauf le code essentiel."""
    return ProjectCleaner(
        exclude_lockfiles=True,
        exclude_tests=True,
        max_file_size_mb=5.0
    )


def create_standard_cleaner() -> ProjectCleaner:
    """Nettoyeur STANDARD : Configuration recommandée."""
    return ProjectCleaner(
        exclude_lockfiles=True,
        exclude_tests=False,
        max_file_size_mb=10.0
    )


def create_lenient_cleaner() -> ProjectCleaner:
    """Nettoyeur PERMISSIF : Garde plus de fichiers."""
    return ProjectCleaner(
        exclude_lockfiles=False,
        exclude_tests=False,
        max_file_size_mb=20.0
    )