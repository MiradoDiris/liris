# Complete code for multi_language_parser.py
import os
import re
import ast
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
import copy
import uuid
import json

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
                'call': [...],
                'uses': [...]  # Nouveau pour variables
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
        
        result = parser_func(content, file_path)
        total_rels = sum(len(v) for v in result.values())
        if total_rels > 0:
            logger.info(f"✅ {file_path}: {total_rels} relations parsées - {dict((k, len(v)) for k, v in result.items())}")
        else:
            logger.warning(f"⚠️ {file_path}: Aucune relation détectée")
        
            return result
        
        return parser_func(content, file_path)
    
    def extract_classes(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrait les classes définies dans le fichier.
        
        Args:
            content: Contenu du fichier
            file_path: Chemin du fichier
        
        Returns:
            Liste des classes: [{'name': 'ClassName', 'line': 10, 'methods': [...], 'uid': '...'}]
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py':
            return self._extract_python_classes(content)
        elif ext == '.java':
            return self._extract_java_classes(content)
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return self._extract_js_classes(content)
        elif ext in ['.cpp', '.c', '.h']:
            return self._extract_cpp_classes(content)
        else:
            return []

    def extract_functions(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrait les fonctions/méthodes définies dans le fichier.
        
        Args:
            content: Contenu du fichier
            file_path: Chemin du fichier
        
        Returns:
            Liste des fonctions: [{'name': 'funcName', 'line': 15, 'type': 'function/method', 'uid': '...', 'calls': [...]}]
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py':
            return self._extract_python_functions(content)
        elif ext == '.java':
            return self._extract_java_functions(content)
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return self._extract_js_functions(content)
        elif ext in ['.cpp', '.c', '.h']:
            return self._extract_cpp_functions(content)
        else:
            return []

    def extract_variables(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrait les variables définies dans le fichier.
        
        Args:
            content: Contenu du fichier
            file_path: Chemin du fichier
        
        Returns:
            Liste des variables: [{'name': 'varName', 'line': 20, 'type': 'global/local/attribute', 'scope': 'class/function/global', 'uid': '...'}]
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py':
            return self._extract_python_variables(content)
        elif ext == '.java':
            return self._extract_java_variables(content)
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return self._extract_js_variables(content)
        elif ext in ['.cpp', '.c', '.h']:
            return self._extract_cpp_variables(content)
        else:
            return []
    
    def _extract_python_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les classes Python avec AST."""
        classes = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [],
                        'bases': [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases],
                        'uid': f"class_{node.name}_{node.lineno}",  # UID unique
                        'uses_vars': []  # Pour liens vers variables
                    }
                    # Extraire méthodes
                    for body_node in node.body:
                        if isinstance(body_node, ast.FunctionDef):
                            method = {'name': body_node.name, 'line': body_node.lineno}
                            class_info['methods'].append(method)
                            # Détecter usages de vars dans méthodes (simplifié)
                            for assign in ast.walk(body_node):
                                if isinstance(assign, ast.Assign) and isinstance(assign.targets[0], ast.Name):
                                    if assign.targets[0].id not in class_info['uses_vars']:
                                        class_info['uses_vars'].append(assign.targets[0].id)
                    classes.append(class_info)
        except SyntaxError:
            # Fallback regex amélioré pour classes avec décorateurs, imbriquées, etc.
            class_pattern = r'(?:@[\w\s]+\n)*\s*class\s+(\w+)(?:\s*\([^)]*\))?'
            for match in re.finditer(class_pattern, content, re.MULTILINE | re.DOTALL):
                classes.append({
                    'name': match.group(1),
                    'line': content[:match.start()].count('\n') + 1,
                    'methods': [],
                    'uid': f"class_{match.group(1)}_approx",
                    'uses_vars': []
                })
        return classes

    def _extract_python_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les fonctions Python avec AST."""
        functions = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_type = 'method' if any(arg.arg == 'self' for arg in node.args.args) else 'function'
                    func_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'type': func_type,
                        'uid': f"func_{node.name}_{node.lineno}",  # UID unique
                        'calls': []  # Pour intra-relations
                    }
                    # Détecter calls internes (simplifié)
                    for body_node in ast.walk(node):
                        if isinstance(body_node, ast.Call) and isinstance(body_node.func, ast.Name):
                            called = body_node.func.id
                            if called not in func_info['calls']:
                                func_info['calls'].append(called)
                    functions.append(func_info)
        except SyntaxError:
            # Fallback regex amélioré pour async, lambda, etc.
            func_pattern = r'(?:async\s+)?def\s+(\w+)|lambda\s*:'
            for match in re.finditer(func_pattern, content, re.MULTILINE):
                name = match.group(1) or 'lambda'
                functions.append({
                    'name': name,
                    'line': content[:match.start()].count('\n') + 1,
                    'type': 'function',
                    'uid': f"func_{name}_approx",
                    'calls': []
                })
        return functions

    def _extract_python_variables(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les variables Python avec AST."""
        variables = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    # CORRECTION: targets au pluriel
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_type = 'global' if any(isinstance(g, ast.Global) for g in ast.walk(node.parent if hasattr(node, 'parent') else tree)) else 'local'
                            var_info = {
                                'name': target.id,
                                'line': node.lineno,
                                'type': var_type,
                                'scope': 'global',  # À affiner
                                'uid': f"var_{target.id}_{node.lineno}"
                            }
                            if var_info not in variables:
                                variables.append(var_info)
                elif isinstance(node, ast.AnnAssign):
                    # CORRECTION: Pour AnnAssign, c'est target (singulier)
                    if isinstance(node.target, ast.Name):
                        var_type = 'global' if any(isinstance(g, ast.Global) for g in ast.walk(node.parent if hasattr(node, 'parent') else tree)) else 'local'
                        var_info = {
                            'name': node.target.id,
                            'line': node.lineno,
                            'type': var_type,
                            'scope': 'global',
                            'uid': f"var_{node.target.id}_{node.lineno}"
                        }
                        if var_info not in variables:
                            variables.append(var_info)
                # Pour attributs de classe
                elif isinstance(node, ast.ClassDef):
                    for body in node.body:
                        if isinstance(body, ast.Assign) and len(body.targets) == 1 and isinstance(body.targets[0], ast.Attribute):
                            attr_info = {
                                'name': body.targets[0].attr,
                                'line': body.lineno,
                                'type': 'attribute',
                                'scope': node.name,
                                'uid': f"attr_{body.targets[0].attr}_{body.lineno}"
                            }
                            if attr_info not in variables:
                                variables.append(attr_info)
        except SyntaxError:
            # Fallback regex amélioré pour = sans mots-clés
            var_pattern = r'^(\s*[\w_][\w\d_]*)\s*=\s*(?!(?:def|class|import|from|if|for|while|try|with|async|def\s|class\s|import\s|from\s))'
            for match in re.finditer(var_pattern, content, re.MULTILINE):
                var_info = {
                    'name': match.group(1).strip(),
                    'line': content[:match.start()].count('\n') + 1,
                    'type': 'local',
                    'scope': 'global',
                    'uid': f"var_{match.group(1).strip()}_approx"
                }
                if var_info not in variables:
                    variables.append(var_info)
        return variables

    def _extract_java_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les classes Java avec regex amélioré."""
        classes = []
        class_pattern = r'(?:public|private|protected|abstract|final|static)?\s*(?:class|interface|enum)\s+(\w+)(?:\s*(?:extends|implements)\s+[\w<>\[\]]+)?'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'methods': [],
                'uid': f"class_{match.group(1)}_approx",
                'uses_vars': []
            })
        return classes

    def _extract_java_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les méthodes Java avec regex amélioré."""
        functions = []
        func_pattern = r'(?:public|private|protected|static|final|abstract|synchronized)?\s*(?:[\w<>\[\]]+\s+)+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w, ]+)?\{?'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'method',
                'uid': f"func_{match.group(1)}_approx",
                'calls': []
            })
        return functions

    def _extract_java_variables(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les variables Java avec regex amélioré."""
        variables = []
        var_pattern = r'(?:public|private|protected|static|final|transient|volatile)?\s*(?:[\w<>\[\]]+\s+)+(\w+)\s*(?:=.*?;|\s*(?:,|\))|;)'
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            variables.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'field',
                'scope': 'class',  # Simplifié
                'uid': f"var_{match.group(1)}_approx"
            })
        return variables

    def _extract_js_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les classes JS/TS avec regex amélioré."""
        classes = []
        class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s*(?:extends|implements)\s+[\w<>\[\]]+)?'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'methods': [],
                'uid': f"class_{match.group(1)}_approx",
                'uses_vars': []
            })
        return classes

    def _extract_js_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les fonctions JS/TS avec regex amélioré pour composants React, async, etc."""
        functions = []
        # Pattern étendu pour function, arrow, async, class methods
        func_pattern = r'(?:export\s+(?:default\s+))?(?:async\s+)?(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?(?:function|[\(\s])|class\s+\w+\s*\{[^}]*(\w+)\s*\([^)]*\)\s*\{)'
        for match in re.finditer(func_pattern, content, re.MULTILINE | re.DOTALL):
            name = match.group(1) or match.group(2) or match.group(4)
            if name:
                functions.append({
                    'name': name,
                    'line': content[:match.start()].count('\n') + 1,
                    'type': 'function',
                    'uid': f"func_{name}_approx",
                    'calls': []
                })
        return functions

    def _extract_js_variables(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les variables JS/TS avec regex amélioré pour destructuring."""
        variables = []
        var_pattern = r'(?:const|let|var)\s+([\w\s,{}[\]]+)\s*(?:=|\;|$)'
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            # Extraire noms multiples si destructuring
            names = re.findall(r'[\w_]+', match.group(1))
            for name in names:
                if name:
                    variables.append({
                        'name': name,
                        'line': content[:match.start()].count('\n') + 1,
                        'type': 'var',
                        'scope': 'global',
                        'uid': f"var_{name}_approx"
                    })
        return variables

    def _extract_cpp_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les classes C++ avec regex amélioré pour templates."""
        classes = []
        class_pattern = r'(?:class|struct)\s+(\w+)(?:\s*(?:<[^>]+>))?(?:\s*:[^}]*)?'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'methods': [],
                'uid': f"class_{match.group(1)}_approx",
                'uses_vars': []
            })
        return classes

    def _extract_cpp_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les fonctions C++ avec regex amélioré pour templates."""
        functions = []
        func_pattern = r'(?:[\w:<>\[\]]+\s+)+(\w+)\s*\([^)]*\)\s*(?:const|override|final|throw\s*\([^)]*\))?\s*\{?'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'function',
                'uid': f"func_{match.group(1)}_approx",
                'calls': []
            })
        return functions

    def _extract_cpp_variables(self, content: str) -> List[Dict[str, Any]]:
        """Extrait les variables C++ avec regex amélioré pour types complexes."""
        variables = []
        var_pattern = r'(?:auto|[\w:<>\[\]&*]+\s+)+(\w+)\s*(?:=.*?;|\s*(?:,|;|\))|;)'
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            variables.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'var',
                'scope': 'global',
                'uid': f"var_{match.group(1)}_approx"
            })
        return variables
    
    def _parse_python(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing Python complet avec AST pour imports, héritage, appels de fonctions, usages de variables.
        
        Détecte:
        - Imports (import, from...import)
        - Héritage de classes (extends)
        - Appels de fonctions/méthodes (intra/inter)
        - Usages de variables
        
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
                        'target_uid': '',  # À mapper plus tard
                        'type': 'import',
                        'line': node.lineno,
                        'intra_file': False
                    })
            
            # Imports relatifs: from module import name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    target = (module + '.' + alias.name).split('.')[0] + '.py'
                    relations['import'].append({
                        'target': target,
                        'target_uid': '',
                        'type': 'from_import',
                        'line': node.lineno,
                        'intra_file': False
                    })
            
            # Héritage de classes
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        target = base.id
                        relations['heritage'].append({
                            'target': target,
                            'target_uid': f"class_{target}_approx",
                            'type': 'extends',
                            'line': node.lineno,
                            'intra_file': False
                        })
            
            # Appels de fonctions
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    target = node.func.id
                    uid_target = f"func_{target}_{node.lineno}"
                    relations['call'].append({
                        'target': target,
                        'target_uid': uid_target,
                        'type': 'function_call',
                        'line': node.lineno,
                        'intra_file': True  # Assumer intra pour simplicité
                    })
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        target = f"{node.func.value.id}.{node.func.attr}"
                        relations['call'].append({
                            'target': target,
                            'target_uid': '',
                            'type': 'method_call',
                            'line': node.lineno,
                            'intra_file': False
                        })
        
        # Détection usages de variables dans calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and any(isinstance(arg, ast.Name) for arg in node.args):
                for arg in node.args:
                    if isinstance(arg, ast.Name):
                        relations['uses'].append({
                            'target': arg.id,
                            'target_uid': f"var_{arg.id}_{node.lineno}",
                            'type': 'variable_use',
                            'line': node.lineno,
                            'intra_file': True
                        })
        
        # Dédoublonner les relations
        return self._dedup_relations(relations)
    
    def _parse_java(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing Java via regex: imports, extends/implements, appels de méthodes, usages de vars.
        
        Détecte:
        - Imports
        - Héritage (extends)
        - Appels de méthodes (intra/inter)
        - Usages de variables (simplifié)
        
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
                'target_uid': '',
                'type': 'import',
                'line': line_num,
                'intra_file': False
            })
        
        # Pattern pour l'héritage
        extends_pattern = r'(public|private|protected)?\s*class\s+\w+\s*(extends\s+([\w\.]+))?|\s*interface\s+\w+\s*(extends\s+([\w\.]+))?|\s*class\s+\w+\s*(implements\s+([\w\.]+(?:,\s*[\w\.]+)*))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(3) or match.group(5) or match.group(7):
                target = (match.group(3) or match.group(5) or match.group(7).split(',')[0]) + '.java'
                line_num = content[:match.start()].count('\n') + 1
                relations['heritage'].append({
                    'target': target,
                    'target_uid': f"class_{target.split('.')[-1]}_approx",
                    'type': 'extends',
                    'line': line_num,
                    'intra_file': False
                })
        
        # Pattern pour les appels de méthodes (intra/inter)
        call_pattern = r'(\w+(?:\.[ \w]+)?)\.(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'target_uid': f"func_{match.group(2)}_approx",
                'type': 'method_call',
                'line': line_num,
                'intra_file': True if match.group(1) in ['this', 'super'] else False
            })
        
        # Pattern pour usages de variables (simplifié, e.g., dans expressions)
        var_use_pattern = r'(\w+(?!\s*(?:class|interface|enum|void|int|float|double|boolean|String|Object|ArrayList|List|Map|Set|\{|;|\)|,|\+|\-|\*|\/|\%|\&|\||\^|~|<<|>>|>>=|<=|>=|==|!=|&&|\|\||\?|:|\+\+|\-\-|\+=|\-=|\*=|\/=|\%=|&=|\/=|<<=|>>=|>>=|&=|!=|=|\.|->|\[\]|\(|\)|\{|\}|,|;|\n|\r|\t|\s+)))\s*[=+\-*/]'
        for match in re.finditer(var_use_pattern, content, re.MULTILINE):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            relations['uses'].append({
                'target': var_name,
                'target_uid': f"var_{var_name}_approx",
                'type': 'variable_use',
                'line': line_num,
                'intra_file': True
            })
        
        return self._dedup_relations(relations)
    
    def _parse_javascript(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing JS/TS: require, import, calls, heritage, var uses.
        
        Détecte:
        - Imports ES6 (import...from)
        - Require CommonJS
        - Héritage (extends)
        - Appels de méthodes (intra)
        - Usages de variables
        
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
                'target_uid': '',
                'type': 'import',
                'line': line_num,
                'intra_file': False
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
                'target_uid': '',
                'type': 'require',
                'line': line_num,
                'intra_file': False
            })
        
        # Pattern pour les appels de méthodes
        method_call_pattern = r'(\w+(?:\.[ \w]+)?)\.(\w+)\s*\('
        for match in re.finditer(method_call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'target_uid': f"func_{match.group(2)}_approx",
                'type': 'method_call',
                'line': line_num,
                'intra_file': True if match.group(1) in ['this'] else False
            })
        
        # Pattern pour l'héritage
        extends_pattern = r'(?:export\s+)?class\s+\w+\s*(extends\s+(\w+|\{[^}]+\}))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(2):
                target = match.group(2)
                line_num = content[:match.start()].count('\n') + 1
                relations['heritage'].append({
                    'target': target,
                    'target_uid': f"class_{target}_approx",
                    'type': 'extends',
                    'line': line_num,
                    'intra_file': False
                })
        
        # Pattern pour usages de variables
        var_use_pattern = r'(\w+(?!\s*(?:function|class|import|from|export|const|let|var|if|for|while|try|with|async|await|return|throw|new|this|super|=>|\{|;|\)|,|\+|\-|\*|\/|\%|\&|\||\^|~|<<|>>|>>=|<=|>=|==|!=|&&|\|\||\?|:|\+\+|\-\-|\+=|\-=|\*=|\/=|\%=|&=|\/=|<<=|>>=|>>=|&=|!=|=|\.|->|\[\]|\(|\)|\{|\}|,|;|\n|\r|\t|\s+)))\s*[=+\-*/]'
        for match in re.finditer(var_use_pattern, content, re.MULTILINE):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            relations['uses'].append({
                'target': var_name,
                'target_uid': f"var_{var_name}_approx",
                'type': 'variable_use',
                'line': line_num,
                'intra_file': True
            })
        
        return self._dedup_relations(relations)
    
    def _parse_cpp(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parsing C/C++: #include, function calls, var uses.
        
        Détecte:
        - Includes (#include)
        - Appels de fonctions (namespace::function)
        - Usages de variables (simplifié)
        
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
                'target_uid': '',
                'type': 'include',
                'line': line_num,
                'intra_file': False
            })
        
        # Pattern pour les appels de fonctions avec namespace
        call_pattern = r'(\w+(?:::\w+)*)::?(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}::{match.group(2)}"
            line_num = content[:match.start()].count('\n') + 1
            relations['call'].append({
                'target': target,
                'target_uid': f"func_{match.group(2)}_approx",
                'type': 'function_call',
                'line': line_num,
                'intra_file': False
            })
        
        # Pattern pour usages de variables
        var_use_pattern = r'(\w+(?!\s*(?:int|float|double|char|bool|void|auto|struct|class|enum|namespace|using|if|for|while|do|switch|case|default|return|break|continue|goto|try|catch|throw|new|delete|this|super|sizeof|typedef|template|inline|extern|static|const|volatile|mutable|register|signed|unsigned|long|short|union|virtual|public|protected|private|friend|operator|->|\.|::|\+\+|\-\-|\+=|\-=|\*=|\/=|\%=|&=|\|=|\^=|<<=|>>=|==|!=|<=|>=|<|>||&|!|~|\?|:|,|;|\(|\)|\[|\]|\{|\}|#|\n|\r|\t|\s+)))\s*[=+\-*/]'
        for match in re.finditer(var_use_pattern, content, re.MULTILINE):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            relations['uses'].append({
                'target': var_name,
                'target_uid': f"var_{var_name}_approx",
                'type': 'variable_use',
                'line': line_num,
                'intra_file': True
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
                r'(?:import\s+(?:{[^}]*}\s+)?(?:.*\s+)?from\s+|from\s+|import\s+|#include\s+|<include\s+|require\s*\()[\'\"]([\w\.\/@]+)[\'\"]',
                line
            )
            if import_match:
                target = import_match.group(1)
                relations['import'].append({
                    'target': target,
                    'target_uid': '',
                    'type': 'import_generic',
                    'line': i,
                    'intra_file': False
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
                key = (rel['target'], rel['type'], rel.get('intra_file', False))
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
    
    def scan_directory(self, directory: str, max_depth: int = None) -> Dict[str, Any]:
        """
        Scanne un répertoire et construit une structure hiérarchique.
        Parcours infini si max_depth est None.
        
        Args:
            directory: Chemin du répertoire à scanner
            max_depth: Profondeur maximale de récursion (None pour illimité)
        
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
            # Ne plus ignorer les fichiers cachés pour récupération maximale
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                cluster = self._scan_cluster(item_path, item, max_depth)
                structure['clusters'].append(cluster)
            elif os.path.isfile(item_path):
                # Fichier au niveau racine (rare mais possible)
                file_info = self._scan_file(item_path, item)
                structure['clusters'].append(file_info)
        
        logger.info(f"Scanné {len(structure['clusters'])} clusters dans {project_name}")
        return structure
    
    def _scan_cluster(self, cluster_path: str, cluster_name: str, max_depth: int) -> Dict[str, Any]:
        """
        Scanne un cluster (dossier principal).
        Parcours infini si max_depth est None.
        
        Args:
            cluster_path: Chemin du cluster
            cluster_name: Nom du cluster
            max_depth: Profondeur restante (None pour illimité)
        
        Returns:
            Dictionnaire représentant le cluster
        """
        cluster = {
            'name': cluster_name,
            'path': cluster_path,
            'type': 'folder',
            'children': []
        }
        
        if max_depth is not None and max_depth <= 0:
            return cluster
        
        try:
            items = sorted(os.listdir(cluster_path))
        except PermissionError:
            logger.warning(f"Accès refusé au cluster: {cluster_path}")
            return cluster
        
        for item in items:
            item_path = os.path.join(cluster_path, item)
            
            if os.path.isdir(item_path):
                new_depth = None if max_depth is None else max_depth - 1
                child_folder = self._scan_cluster(item_path, item, new_depth)
                cluster['children'].append(child_folder)
            elif os.path.isfile(item_path):
                file_info = self._scan_file(item_path, item)
                cluster['children'].append(file_info)
        
        return cluster
    
    def _scan_file(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """
        Version corrigée de _scan_file avec intégration complète des relations.
        """
        file_info = {
            'name': file_name,
            'label': file_name,
            'path': file_path,
            'uid': str(uuid.uuid4()),
            'type': 'file',
            'extension': os.path.splitext(file_name)[1],
            'size': 0,
            'relations': {},
            'children': [],
            'classes': [],
            'functions': [],
            'variables': [],
            'outgoing_relations': [],  # ✅ Relations sortantes
            'incoming_relations': [],  # ✅ Relations entrantes
            'parents': []
        }

        # Lecture du contenu
        content = ''
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                    file_info['size'] = len(content)
                logger.info(f"Lecture réussie de {file_path} avec {encoding}")
                break
            except (UnicodeDecodeError, IOError) as e:
                logger.warning(f"Échec lecture {file_path} avec {encoding}: {e}")
                continue

        # Extraire relations au niveau fichier (imports, heritage, etc.)
        relations = self.parser.parse_content(content, file_path)
        file_info['relations'] = relations

        for rel_type, rel_list in relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    file_info['outgoing_relations'].append({
                        'target_uid': f"temp_{normalized}_{str(uuid.uuid4())[:8]}",
                        'target_name': target_name,
                        'relation_type': rel_type,
                        'category': 'parsed',
                        'line': rel.get('line', 0)
                    })

        # Extraire les éléments (classes, fonctions, variables)
        try:
            classes = self.parser.extract_classes(content, file_path) or []
            functions = self.parser.extract_functions(content, file_path) or []
            variables = self.parser.extract_variables(content, file_path) or []

            file_info['classes'] = classes
            file_info['functions'] = functions
            file_info['variables'] = variables

            # Créer la hiérarchie : Fichier → Classes/Fonctions/Variables
            for cls in classes:
                if not cls.get('uid'):
                    cls['uid'] = str(uuid.uuid4())

                class_node = {
                    'name': cls['name'],
                    'label': f"Class: {cls['name']}",
                    'uid': cls['uid'],
                    'type': 'class',
                    'line': cls.get('line', 0),
                    'description': f"Classe définie dans {file_name}",
                    'children': [],
                    'parents': [file_info['uid']],
                    'outgoing_relations': [],
                    'incoming_relations': [],
                    'methods': cls.get('methods', []),
                    'bases': cls.get('bases', [])
                }

                # ✅ Ajouter relations d'héritage
                for base in cls.get('bases', []):
                    base_uid = f"temp_class_{base}_{str(uuid.uuid4())[:8]}"
                    class_node['outgoing_relations'].append({
                        'target_uid': base_uid,
                        'relation_type': 'extends',
                        'category': 'parsed',
                        'target_name': base
                    })

                # ✅ Ajouter relation hiérarchique parent-enfant
                file_info['outgoing_relations'].append({
                    'target_uid': cls['uid'],
                    'relation_type': 'child',
                    'category': 'hierarchy'
                })

                # Ajouter méthodes comme enfants de la classe
                for method in cls.get('methods', []):
                    method_uid = str(uuid.uuid4())
                    method_node = {
                        'name': method['name'],
                        'label': f"Method: {method['name']}",
                        'uid': method_uid,
                        'type': 'method',
                        'line': method.get('line', 0),
                        'description': f"Méthode dans {cls['name']}",
                        'children': [],
                        'parents': [cls['uid']],
                        'outgoing_relations': [],
                        'incoming_relations': []
                    }

                    # ✅ Relation hiérarchique classe → méthode
                    class_node['outgoing_relations'].append({
                        'target_uid': method_uid,
                        'relation_type': 'child',
                        'category': 'hierarchy'
                    })

                    class_node['children'].append(method_node)

                file_info['children'].append(class_node)

            # Fonctions
            for func in functions:
                if not func.get('uid'):
                    func['uid'] = str(uuid.uuid4())

                func_node = {
                    'name': func['name'],
                    'label': f"Function: {func['name']}",
                    'uid': func['uid'],
                    'type': func.get('type', 'function'),
                    'line': func.get('line', 0),
                    'description': f"Fonction définie dans {file_name}",
                    'children': [],
                    'parents': [file_info['uid']],
                    'outgoing_relations': [],
                    'incoming_relations': [],
                    'params': func.get('params', []),
                    'returns': func.get('returns', {})
                }

                # ✅ Ajouter relations d'appel
                for call in func.get('calls', []):
                    call_uid = f"temp_func_{call}_{str(uuid.uuid4())[:8]}"
                    func_node['outgoing_relations'].append({
                        'target_uid': call_uid,
                        'relation_type': 'calls',
                        'category': 'parsed',
                        'target_name': call
                    })

                # ✅ Relation hiérarchique fichier → fonction
                file_info['outgoing_relations'].append({
                    'target_uid': func['uid'],
                    'relation_type': 'child',
                    'category': 'hierarchy'
                })

                file_info['children'].append(func_node)

            # Variables
            for var in variables:
                if not var.get('uid'):
                    var['uid'] = str(uuid.uuid4())

                var_node = {
                    'name': var['name'],
                    'label': f"Variable: {var['name']}",
                    'uid': var['uid'],
                    'type': 'variable',
                    'line': var.get('line', 0),
                    'description': f"Variable définie dans {file_name}",
                    'children': [],
                    'parents': [file_info['uid']],
                    'outgoing_relations': [],
                    'incoming_relations': [],
                    'var_type': var.get('type', 'local'),
                    'scope': var.get('scope', 'global')
                }

                # ✅ Relation hiérarchique fichier → variable
                file_info['outgoing_relations'].append({
                    'target_uid': var['uid'],
                    'relation_type': 'child',
                    'category': 'hierarchy'
                })

                file_info['children'].append(var_node)

            logger.info(
                f"Fichier {file_name}: "
                f"{len(classes)} classes, "
                f"{len(functions)} fonctions, "
                f"{len(variables)} variables, "
                f"{len(file_info['outgoing_relations'])} relations sortantes"
            )

        except Exception as e:
            logger.error(f"Erreur extraction pour {file_path}: {e}")

        return file_info

    def _create_child_node(self, item: Dict, item_type: str, parent_path: str) -> Dict[str, Any]:
        """Crée un nœud enfant pour class/func/var."""
        uid = str(uuid.uuid4())
        name = item['name']
        return {
            'name': name,
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'parent_uid': os.path.basename(parent_path),  # UID du fichier parent (à ajuster)
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'label': f"{item_type.capitalize()}: {name}"
        }

    def _map_relations_to_child(self, relations: Dict, child: Dict, rel_key: str):
        """Mappe relations vers le child (simplifié)."""
        rel_list = relations.get(rel_key, [])
        for rel in rel_list:
            if rel.get('target') == child['name']:
                child['outgoing_relations'].append({
                    'target_uid': rel.get('target_uid', ''),
                    'relation_type': rel_key
                })
    
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
                    'call': [...],
                    'uses': [...]
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

    def _scan_label(self, label, cluster, project_path):
        """
        Parcourt récursivement les labels et fichiers.
        """
        for child in label.get("children", []):
            self._scan_label(child, cluster, project_path)

        for file_path in label.get("files", []):
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                parsed_data = {
                    "functions": self.parser.extract_functions(content, file_path),
                    "classes": self.parser.extract_classes(content, file_path),
                    "variables": self.parser.extract_variables(content, file_path)
                }
                # Attribution des éléments au bon niveau hiérarchique
                self._assign_extracted_data(
                    file_path, parsed_data,
                    cluster=cluster,
                    label_root=label,
                    label_parent=self._find_parent_label(label, cluster),
                    label_enfant=self._find_child_label(label)
                )
            except Exception as e:
                logger.error(f"Erreur lors du scan du fichier {file_path}: {e}")

    def scan_project(self, project_path):
        """
        Analyse le projet sans recréer la hiérarchie.
        """
        logger.info(f"📁 Scan du projet: {project_path}")
        structure = self._load_existing_structure(project_path)  # Charge la structure existante
        for cluster in structure.get("clusters_detailed", []):
            for label_root in cluster.get("root_labels", []):
                self._scan_label(label_root, cluster, project_path)

        # === AJOUT : Intégrer les relations après scan ===
        self.build_relations_graph(structure)
        logger.info("Relations graph built after scan.")

        return structure

    def _find_parent_label(self, label, cluster):
        """
        Trouve le label parent dans la hiérarchie.
        """
        for root in cluster.get("root_labels", []):
            if label in root.get("children", []):
                return root
            for child in root.get("children", []):
                if label in child.get("children", []):
                    return child
        return None

    def _find_child_label(self, label):
        """Renvoie le premier label enfant si présent."""
        return label["children"][0] if label.get("children") else None

    def _load_existing_structure(self, project_path):
        """
        Charge la structure existante du projet sans recréer les clusters.
        """
        structure_file = os.path.join(project_path, "turing_ontology.json")
        if os.path.exists(structure_file):
            with open(structure_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"clusters_detailed": []}

    def _get_or_create_folder_node(self, root_node: Dict[str, Any], relative_path: str) -> Dict[str, Any]:
        """Fonction utilitaire récursive pour s'assurer que les nœuds de dossier existent dans la structure."""
        # Logique pour créer la hiérarchie Dossier A -> Dossier B
        parts = relative_path.split(os.sep)
        current = root_node
        for part in parts:
            if part == '.': continue
            next_node = next((c for c in current['children'] if c['name'] == part and c['type'] == 'folder'), None)
            
            if not next_node:
                next_node = {'name': part, 'type': 'folder', 'children': []}
                current['children'].append(next_node)
            current = next_node
        return current

    def _assign_extracted_data(self, file_path, parsed_data, cluster=None, label_root=None, label_parent=None, label_enfant=None):
        """
        Place les fonctions/classes/variables extraites dans la bonne hiérarchie.
        """
        if cluster and file_path.startswith(cluster['path']):
            target = label_root
        elif label_root and file_path.startswith(label_root['path']):
            target = label_parent
        elif label_parent and file_path.startswith(label_parent['path']):
            target = label_enfant
        else:
            target = None

        if not target:
            return

        target.setdefault("functions", []).extend(parsed_data.get("functions", []))
        target.setdefault("classes", []).extend(parsed_data.get("classes", []))
        target.setdefault("variables", []).extend(parsed_data.get("variables", []))

    def integrate_file_into_label(self, file_info: Dict[str, Any], label: Dict[str, Any]):
        """
        Intègre les enfants du fichier (classes, fonctions, variables) 
        directement dans le label du fichier au lieu de créer une hiérarchie supplémentaire.

        Args:
            file_info: Information du fichier avec ses classes/fonctions/variables
            label: Le label (fichier racine) où intégrer
        """
        # Assurer que le label a la structure correcte
        if 'children' not in label:
            label['children'] = []

        # Ajouter tous les enfants du fichier au label
        label['children'].extend(file_info.get('children', []))

        # Copier aussi les listes brutes pour référence
        label['classes'] = file_info.get('classes', [])
        label['functions'] = file_info.get('functions', [])
        label['variables'] = file_info.get('variables', [])

        logger.info(f"Intégré {len(file_info.get('children', []))} enfants dans le label {label.get('label', 'unknown')}")

    def build_relations_graph(self, structure: Dict[str, Any]) -> None:
        """
        Version corrigée qui intègre TOUTES les relations :
        - Hiérarchie (parent-child)
        - Parsées (import, extends, calls, uses)
        - Inverses (incoming)
        """
        all_nodes = self._get_all_nodes_from_structure(structure)
        logger.info(f"🔗 Construction du graphe avec {len(all_nodes)} nœuds")

        # Étape 1 : Intégrer les relations hiérarchiques explicites
        logger.info("📊 Étape 1 : Intégration hiérarchie (parent-child)")
        hierarchy_count = self._integrate_hierarchy_into_relations_corrected(structure)
        logger.info(f"✅ {hierarchy_count} relations hiérarchiques ajoutées")

        # Étape 2 : Traiter les relations au niveau fichier (imports, etc.)
        logger.info("📊 Étape 2 : Traitement relations fichiers (import, heritage)")
        file_rel_count = self._process_file_level_relations_corrected(structure, all_nodes)
        logger.info(f"✅ {file_rel_count} relations fichiers ajoutées")

        # Étape 3 : Traiter les relations au niveau éléments (extends, calls, uses)
        logger.info("📊 Étape 3 : Traitement relations code (extends, calls, uses)")
        code_rel_count = self._process_child_level_relations_corrected(structure, all_nodes)
        logger.info(f"✅ {code_rel_count} relations code ajoutées")

        # Étape 4 : Créer les relations inverses (incoming depuis outgoing)
        logger.info("📊 Étape 4 : Création relations inverses")
        inverse_count = self._create_inverse_relations(all_nodes)
        logger.info(f"✅ {inverse_count} relations inverses créées")

        logger.info("✅ Graphe complet construit avec succès")

    def _get_all_nodes_from_structure(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten all nodes from the structure."""
        all_nodes = []
        def recurse(node: Dict[str, Any]):
            all_nodes.append(node)
            for child in node.get('children', []):
                recurse(child)
        try:
            clusters_key = 'clusters_detailed' if 'clusters_detailed' in structure else 'clusters'
            for cluster in structure.get(clusters_key, []):
                recurse(cluster)
            logger.info(f"Flattened {len(all_nodes)} nodes from structure.")
        except Exception as e:
            logger.error(f"Erreur lors du flattening des nœuds: {e}")
        return all_nodes
    
    def _get_all_labels(self, cluster: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all labels (files, folders, code elements) recursively."""
        labels = []
        def recurse(node: Dict[str, Any]):
            if node.get('type') in ['folder', 'file', 'class', 'function', 'method', 'variable']:
                labels.append(node)
            for child in node.get('children', []):
                recurse(child)
        recurse(cluster)
        return labels

    def _integrate_hierarchy_into_relations(self, structure: Dict[str, Any]) -> None:
        """Add hierarchy (children/parents) to outgoing/incoming_relations."""
        count = 0
    
        def process_hierarchy(node: Dict[str, Any]):
            nonlocal count
            node_uid = node.get('uid')
            if not node_uid:
                return

            # Pour chaque enfant, créer la relation bidirectionnelle
            for child in node.get('children', []):
                child_uid = child.get('uid')
                if not child_uid:
                    continue
                
                # Outgoing : parent → child
                outgoing = {
                    'target_uid': child_uid,
                    'relation_type': 'child',
                    'category': 'hierarchy'
                }
                if outgoing not in node.setdefault('outgoing_relations', []):
                    node['outgoing_relations'].append(outgoing)
                    count += 1

                # Incoming : child ← parent
                incoming = {
                    'source_uid': node_uid,
                    'relation_type': 'child',
                    'category': 'hierarchy'
                }
                if incoming not in child.setdefault('incoming_relations', []):
                    child['incoming_relations'].append(incoming)

                # Récursif
                process_hierarchy(child)

        clusters_key = 'clusters_detailed' if 'clusters_detailed' in structure else 'clusters'
        for cluster in structure.get(clusters_key, []):
            process_hierarchy(cluster)
            for root_label in cluster.get('root_labels', []):
                process_hierarchy(root_label)

        return count

    def _process_file_level_relations(self, structure: Dict[str, Any], all_nodes: List[Dict[str, Any]]) -> None:
        """Process relations from node['relations'] (e.g., imports, heritage at file level)."""
        clusters_key = 'clusters_detailed' if 'clusters_detailed' in structure else 'clusters'
        for cluster in structure.get(clusters_key, []):
            for label in self._get_all_labels(cluster):
                if label.get('type') != 'file':
                    continue
                file_uid = label['uid']
                relations = label.get('relations', {})
                for rel_type, rel_list in relations.items():
                    for rel in rel_list:
                        target_name = rel['target']
                        target_norm = normalize_node_name(target_name)
                        if not target_norm:
                            continue
                        target_node = self._find_node_by_name(all_nodes, target_norm)
                        if target_node:
                            target_uid = target_node['uid']
                            outgoing = {'target_uid': target_uid, 'relation_type': rel_type, 'category': 'parsed'}
                            if outgoing not in label.get('outgoing_relations', []):
                                label.setdefault('outgoing_relations', []).append(outgoing)
                            incoming = {'source_uid': file_uid, 'relation_type': rel_type, 'category': 'parsed'}
                            if incoming not in target_node.get('incoming_relations', []):
                                target_node.setdefault('incoming_relations', []).append(incoming)
                        else:
                            logger.debug(f"File-level target '{target_name}' not found from {file_uid} ({rel_type})")

    def _process_child_level_relations(self, structure: Dict[str, Any], all_nodes: List[Dict[str, Any]]) -> None:
        """Process intra/inter relations for code elements (bases, calls, uses_vars)."""
        clusters_key = 'clusters_detailed' if 'clusters_detailed' in structure else 'clusters'
        for cluster in structure.get(clusters_key, []):
            for label in self._get_all_labels(cluster):
                if label.get('type') != 'file':
                    continue
                for child in label.get('children', []):
                    child_uid = child['uid']
                    child_type = child['type']
                    # Classes: bases (extends), uses_vars (uses)
                    if child_type == 'class':
                        for base_name in child.get('bases', []):
                            target_norm = normalize_node_name(base_name)
                            if target_norm:
                                target_node = self._find_node_by_name(all_nodes, target_norm)
                                if target_node:
                                    outgoing = {'target_uid': target_node['uid'], 'relation_type': 'extends', 'category': 'parsed'}
                                    if outgoing not in child.get('outgoing_relations', []):
                                        child.setdefault('outgoing_relations', []).append(outgoing)
                                    incoming = {'source_uid': child_uid, 'relation_type': 'extends', 'category': 'parsed'}
                                    if incoming not in target_node.get('incoming_relations', []):
                                        target_node.setdefault('incoming_relations', []).append(incoming)
                        for var_name in child.get('uses_vars', []):
                            target_norm = normalize_node_name(var_name)
                            if target_norm:
                                target_node = self._find_node_by_name(all_nodes, target_norm)
                                if target_node and target_node['type'] == 'variable':
                                    outgoing = {'target_uid': target_node['uid'], 'relation_type': 'uses', 'category': 'parsed'}
                                    if outgoing not in child.get('outgoing_relations', []):
                                        child.setdefault('outgoing_relations', []).append(outgoing)
                                    incoming = {'source_uid': child_uid, 'relation_type': 'uses', 'category': 'parsed'}
                                    if incoming not in target_node.get('incoming_relations', []):
                                        target_node.setdefault('incoming_relations', []).append(incoming)
                    # Functions/Methods: calls
                    elif child_type in ['function', 'method']:
                        for call_name in child.get('calls', []):
                            target_norm = normalize_node_name(call_name)
                            if target_norm:
                                target_node = self._find_node_by_name(all_nodes, target_norm)
                                if target_node:
                                    outgoing = {'target_uid': target_node['uid'], 'relation_type': 'call', 'category': 'parsed'}
                                    if outgoing not in child.get('outgoing_relations', []):
                                        child.setdefault('outgoing_relations', []).append(outgoing)
                                    incoming = {'source_uid': child_uid, 'relation_type': 'call', 'category': 'parsed'}
                                    if incoming not in target_node.get('incoming_relations', []):
                                        target_node.setdefault('incoming_relations', []).append(incoming)

    def _find_node_by_name(self, all_nodes: List[Dict[str, Any]], target_norm: str) -> Optional[Dict[str, Any]]:
        """Find node by normalized name (exact on 'name' or ends with on 'label')."""
        exact_matches = [n for n in all_nodes if normalize_node_name(n.get('name', '')) == target_norm]
        if exact_matches:
            return exact_matches[0]
        label_matches = [n for n in all_nodes if normalize_node_name(n.get('label', '')) and normalize_node_name(n.get('label', '')).endswith(target_norm)]
        return label_matches[0] if label_matches else None

    def _create_inverse_relations(self, all_nodes: List[Dict[str, Any]]) -> int:
        """
        Crée les relations inverses (incoming) depuis les outgoing existantes.
        """
        count = 0
        node_by_uid = {n['uid']: n for n in all_nodes if 'uid' in n}
        
        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')
                if not target_uid or target_uid not in node_by_uid:
                    continue
                
                target_node = node_by_uid[target_uid]
                
                # Créer l'inverse
                inverse = {
                    'source_uid': node_uid,
                    'relation_type': rel['relation_type'],
                    'category': rel.get('category', 'custom')
                }
                
                if inverse not in target_node.setdefault('incoming_relations', []):
                    target_node['incoming_relations'].append(inverse)
                    count += 1
        
        return count

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