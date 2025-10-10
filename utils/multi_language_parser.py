import os
import re
import ast
from typing import List, Dict, Set, Tuple, Any
from collections import defaultdict

from utils.logger import logger


class MultiLanguageDependencyParser:
    """
    Parser multi-langages pour détecter les dépendances et relations.
    
    Supporte:
    - Python (.py)
    - Java (.java)
    - JavaScript/TypeScript (.js, .jsx, .ts, .tsx)
    - C/C++ (.c, .cpp, .h)
    
    Retourne un dictionnaire structuré des relations détectées:
    {
        'import': [{'target': 'fichier.py', 'type': 'import', 'line': 1}],
        'heritage': [{'target': 'ClasseParent', 'type': 'extends', 'line': 5}],
        'call': [{'target': 'fonction', 'type': 'function_call', 'line': 10}]
    }
    """
    
    def __init__(self):
        """Initialise le parser avec la mapping des langages supportés."""
        self.supported_languages = {
            '.py': self._parse_python,
            '.java': self._parse_java,
            '.js': self._parse_javascript,
            '.jsx': self._parse_javascript,
            '.ts': self._parse_javascript,
            '.tsx': self._parse_javascript,
            '.cpp': self._parse_cpp,
            '.c': self._parse_cpp,
            '.h': self._parse_cpp,
        }
    
    def parse_content(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse le contenu d'un fichier et retourne les relations détectées.
        
        Args:
            content: Contenu du fichier à parser
            file_path: Chemin du fichier (pour déterminer l'extension)
        
        Returns:
            Dictionnaire avec les relations groupées par type:
            {
                'import': [...],
                'heritage': [...],
                'call': [...]
            }
        """
        if not content:
            logger.warning(f"Contenu vide pour {file_path}")
            return {}
        
        ext = os.path.splitext(file_path)[1].lower()
        parser_func = self.supported_languages.get(ext)
        
        if not parser_func:
            logger.warning(f"Langage non supporté pour {ext}, utilisation de parsing générique.")
            return self._parse_generic(content, file_path)
        
        return parser_func(content, file_path)
    
    def _parse_python(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing Python complet avec AST pour imports, héritage, appels de fonctions.
        
        Détecte:
        - Imports (import, from...import)
        - Héritage de classes (extends)
        - Appels de fonctions/méthodes
        
        Args:
            content: Code Python
            file_path: Chemin du fichier
        
        Returns:
            Dictionnaire des relations détectées
        """
        relations = defaultdict(list)
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"Syntaxe Python invalide dans {file_path}: {e}, fallback regex.")
            return self._parse_generic(content, file_path)
        
        for node in ast.walk(tree):
            # Imports simples: import module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name.split('.')[0]
                    relations['import'].append({
                        'target': target + '.py',
                        'type': 'import',
                        'line': node.lineno
                    })
            
            # Imports relatifs: from module import name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    target = (module + '.' + alias.name).split('.')[0] + '.py'
                    relations['import'].append({
                        'target': target,
                        'type': 'from_import',
                        'line': node.lineno
                    })
            
            # Héritage de classes
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        target = base.id
                        relations['heritage'].append({
                            'target': target,
                            'type': 'extends',
                            'line': node.lineno
                        })
            
            # Appels de fonctions
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    target = node.func.id
                    relations['call'].append({
                        'target': target,
                        'type': 'function_call',
                        'line': node.lineno
                    })
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        target = f"{node.func.value.id}.{node.func.attr}"
                        relations['call'].append({
                            'target': target,
                            'type': 'method_call',
                            'line': node.lineno
                        })
        
        # Dédoublonner les relations
        return self._dedup_relations(relations)
    
    def _parse_java(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing Java via regex: imports, extends/implements, appels de méthodes.
        
        Détecte:
        - Imports
        - Héritage (extends)
        - Appels de méthodes
        
        Args:
            content: Code Java
            file_path: Chemin du fichier
        
        Returns:
            Dictionnaire des relations détectées
        """
        relations = defaultdict(list)
        
        # Pattern pour les imports
        import_pattern = r'^import\s+(?:static\s+)?([\w\.]+);'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            target = match.group(1).split('.')[-1] + '.java'
            line_num = content[:match.start()].count('\n') + 1
            relations['import'].append({
                'target': target,
                'type': 'import',
                'line': line_num
            })
        
        # Pattern pour l'héritage
        extends_pattern = r'(public|private|protected)?\s*class\s+\w+\s*(extends\s+([\w\.]+))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(3):
                target = match.group(3) + '.java'
                line_num = content[:match.start()].count('\n') + 1
                relations['heritage'].append({
                    'target': target,
                    'type': 'extends',
                    'line': line_num
                })
        
        # Pattern pour les appels de méthodes
        call_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'type': 'method_call',
                'line': line_num
            })
        
        return self._dedup_relations(relations)
    
    def _parse_javascript(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing JS/TS: require, import, calls, heritage.
        
        Détecte:
        - Imports ES6 (import...from)
        - Require CommonJS
        - Héritage (extends)
        - Appels de méthodes
        
        Args:
            content: Code JavaScript/TypeScript
            file_path: Chemin du fichier
        
        Returns:
            Dictionnaire des relations détectées
        """
        relations = defaultdict(list)
        
        # Pattern pour les imports ES6
        import_pattern = r'import\s+(?:\{[^}]+\}\s+)?(?:.*\s+)?from\s+[\'\"]([\w\/\.@]+)[\'\"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            target = match.group(1)
            # Ajouter l'extension si manquante
            if not target.endswith(('.js', '.jsx', '.ts', '.tsx')):
                ext = os.path.splitext(file_path)[1]
                target += ext
            line_num = content[:match.start()].count('\n') + 1
            relations['import'].append({
                'target': target,
                'type': 'import',
                'line': line_num
            })
        
        # Pattern pour require (CommonJS)
        require_pattern = r'require\s*\(\s*[\'\"]([\w\/\.@]+)[\'\"]\s*\)'
        for match in re.finditer(require_pattern, content, re.MULTILINE):
            target = match.group(1)
            if not target.endswith(('.js', '.jsx', '.ts', '.tsx')):
                ext = os.path.splitext(file_path)[1]
                target += ext
            line_num = content[:match.start()].count('\n') + 1
            relations['import'].append({
                'target': target,
                'type': 'require',
                'line': line_num
            })
        
        # Pattern pour les appels de méthodes
        method_call_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(method_call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'type': 'method_call',
                'line': line_num
            })
        
        # Pattern pour l'héritage
        extends_pattern = r'class\s+\w+\s*(extends\s+(\w+))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(2):
                target = match.group(2)
                line_num = content[:match.start()].count('\n') + 1
                relations['heritage'].append({
                    'target': target,
                    'type': 'extends',
                    'line': line_num
                })
        
        return self._dedup_relations(relations)
    
    def _parse_cpp(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing C/C++: #include, function calls.
        
        Détecte:
        - Includes (#include)
        - Appels de fonctions (namespace::function)
        
        Args:
            content: Code C/C++
            file_path: Chemin du fichier
        
        Returns:
            Dictionnaire des relations détectées
        """
        relations = defaultdict(list)
        
        # Pattern pour les includes
        include_pattern = r'#include\s*[<"](\w+\.h?)["<]'
        for match in re.finditer(include_pattern, content, re.MULTILINE):
            target = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            relations['import'].append({
                'target': target,
                'type': 'include',
                'line': line_num
            })
        
        # Pattern pour les appels de fonctions avec namespace
        call_pattern = r'(\w+)::(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}::{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'type': 'function_call',
                'line': line_num
            })
        
        return self._dedup_relations(relations)
    
    def _parse_generic(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fallback regex pour tout langage non supporté.
        
        Tente de détecter les imports basiques avec des patterns génériques.
        
        Args:
            content: Contenu du fichier
            file_path: Chemin du fichier
        
        Returns:
            Dictionnaire des relations détectées (limité)
        """
        relations = defaultdict(list)
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Pattern générique pour imports
            import_match = re.search(
                r'(?:import\s+(?:{[^}]*}\s+)?(?:.*\s+)?from\s+|from\s+|import\s+)[\'\"]([\w\.\/@]+)[\'\"]',
                line
            )
            if import_match:
                target = import_match.group(1)
                relations['import'].append({
                    'target': target,
                    'type': 'import_generic',
                    'line': i
                })
        
        return self._dedup_relations(relations)
    
    def _dedup_relations(self, relations: defaultdict) -> Dict[str, List[Dict[str, Any]]]:
        """
        Dédoublonne les relations par target et type.
        
        Garde uniquement la première occurrence de chaque relation unique.
        
        Args:
            relations: defaultdict avec listes de relations
        
        Returns:
            Dictionnaire nettoyé sans doublons
        """
        for rel_type in relations:
            seen = {}
            deduped = []
            for rel in relations[rel_type]:
                key = (rel['target'], rel['type'])
                if key not in seen:
                    seen[key] = rel
                    deduped.append(rel)
            relations[rel_type] = deduped
        
        return dict(relations)


class ProjectStructureScanner:
    """
    Scanner pour parcourir une structure de projet et extraire les fichiers.
    
    Construit une représentation hiérarchique du projet avec:
    - Clusters (dossiers principaux)
    - Labels (sous-dossiers et fichiers)
    - Relations hiérarchiques (parent-enfant)
    """
    
    def __init__(self, parser: MultiLanguageDependencyParser = None):
        """
        Initialise le scanner.
        
        Args:
            parser: Instance du parser multi-langages (optionnel)
        """
        self.parser = parser or MultiLanguageDependencyParser()
    
    def scan_directory(self, directory: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        Scanne un répertoire et construit une structure hiérarchique.
        
        Args:
            directory: Chemin du répertoire à scanner
            max_depth: Profondeur maximale de récursion
        
        Returns:
            Dictionnaire avec la structure du projet:
            {
                'name': 'nom_projet',
                'path': '/chemin/complet',
                'clusters': [
                    {
                        'name': 'cluster1',
                        'type': 'folder',
                        'children': [...]
                    }
                ]
            }
        """
        if not os.path.exists(directory):
            logger.error(f"Répertoire introuvable: {directory}")
            return {}
        
        project_name = os.path.basename(directory)
        
        structure = {
            'name': project_name,
            'path': directory,
            'clusters': []
        }
        
        # Parcourir le niveau supérieur (clusters)
        try:
            items = sorted(os.listdir(directory))
        except PermissionError:
            logger.error(f"Accès refusé: {directory}")
            return structure
        
        for item in items:
            # Ignorer les fichiers/dossiers cachés
            if item.startswith('.'):
                continue
            
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                cluster = self._scan_cluster(item_path, item, max_depth - 1)
                structure['clusters'].append(cluster)
            elif os.path.isfile(item_path):
                # Fichier au niveau racine (rare mais possible)
                file_info = self._scan_file(item_path, item)
                structure['clusters'].append(file_info)
        
        logger.info(f"Scanné {len(structure['clusters'])} clusters dans {project_name}")
        return structure
    
    def _scan_cluster(self, cluster_path: str, cluster_name: str, depth: int) -> Dict[str, Any]:
        """
        Scanne un cluster (dossier principal).
        
        Args:
            cluster_path: Chemin du cluster
            cluster_name: Nom du cluster
            depth: Profondeur restante
        
        Returns:
            Dictionnaire représentant le cluster
        """
        cluster = {
            'name': cluster_name,
            'path': cluster_path,
            'type': 'folder',
            'children': []
        }
        
        if depth <= 0:
            return cluster
        
        try:
            items = sorted(os.listdir(cluster_path))
        except PermissionError:
            logger.warning(f"Accès refusé au cluster: {cluster_path}")
            return cluster
        
        for item in items:
            if item.startswith('.'):
                continue
            
            item_path = os.path.join(cluster_path, item)
            
            if os.path.isdir(item_path):
                child_folder = self._scan_cluster(item_path, item, depth - 1)
                cluster['children'].append(child_folder)
            elif os.path.isfile(item_path):
                file_info = self._scan_file(item_path, item)
                cluster['children'].append(file_info)
        
        return cluster
    
    def _scan_file(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """
        Scanne un fichier et détecte ses relations.
        
        Args:
            file_path: Chemin du fichier
            file_name: Nom du fichier
        
        Returns:
            Dictionnaire représentant le fichier avec ses relations
        """
        file_info = {
            'name': file_name,
            'path': file_path,
            'type': 'file',
            'extension': os.path.splitext(file_name)[1],
            'size': os.path.getsize(file_path),
            'relations': {}
        }
        
        # Lire le contenu pour parser les relations
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Parser les relations
            relations = self.parser.parse_content(content, file_path)
            file_info['relations'] = relations
            
            # Compter les relations
            total_relations = sum(len(rels) for rels in relations.values())
            file_info['relations_count'] = total_relations
            
        except Exception as e:
            logger.warning(f"Erreur lecture fichier {file_path}: {e}")
            file_info['relations'] = {}
            file_info['relations_count'] = 0
        
        return file_info
    
    def get_all_files(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Récupère tous les fichiers d'une structure de manière plate.
        
        Args:
            structure: Structure du projet
        
        Returns:
            Liste de tous les fichiers trouvés
        """
        files = []
        
        def recurse(node):
            if node.get('type') == 'file':
                files.append(node)
            
            for child in node.get('children', []):
                recurse(child)
        
        for cluster in structure.get('clusters', []):
            recurse(cluster)
        
        return files
    
    def get_relations_map(self, structure: Dict[str, Any]) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Construit une map de toutes les relations du projet.
        
        Args:
            structure: Structure du projet
        
        Returns:
            Dictionnaire:
            {
                'fichier1.py': {
                    'import': [...],
                    'heritage': [...],
                    'call': [...]
                }
            }
        """
        relations_map = {}
        files = self.get_all_files(structure)
        
        for file_info in files:
            file_path = file_info['path']
            relations = file_info.get('relations', {})
            
            if relations:
                relations_map[file_path] = relations
        
        logger.info(f"Relations map construite: {len(relations_map)} fichiers avec relations")
        return relations_map


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def normalize_node_name(name: str) -> str:
    """
    Normalise le nom d'un nœud en enlevant l'extension et le chemin.
    
    Args:
        name: Nom complet du fichier/nœud
    
    Returns:
        Nom normalisé sans extension, ou None si invalide
    """
    if not name or not isinstance(name, str):
        return None
    
    name = name.strip()
    if not name or name.lower() == 'n/a':
        return None
    
    # Extraire le nom de base et enlever l'extension
    base = os.path.basename(name)
    name_without_ext = os.path.splitext(base)[0]
    
    return name_without_ext.strip() if name_without_ext.strip() else None


def get_supported_extensions() -> List[str]:
    """
    Retourne la liste des extensions supportées par le parser.
    
    Returns:
        Liste des extensions (ex: ['.py', '.java', '.js'])
    """
    parser = MultiLanguageDependencyParser()
    return list(parser.supported_languages.keys())


def is_supported_file(file_path: str) -> bool:
    """
    Vérifie si un fichier est supporté par le parser.
    
    Args:
        file_path: Chemin du fichier
    
    Returns:
        True si l'extension est supportée
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in get_supported_extensions()
