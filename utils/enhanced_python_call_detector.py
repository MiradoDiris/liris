import ast
from typing import Dict, List, Optional
from collections import defaultdict
from utils.logger import logger


class EnhancedPythonCallDetector:
    """
    Détecteur avancé pour capturer TOUS les types d'appels en Python.
    
    Gère :
    - self.fonction() → méthode de la même classe
    - obj.fonction() → méthode d'un objet
    - module.fonction() → fonction d'un module importé
    - fonction() → fonction simple
    - super().fonction() → méthode de la classe parent
    - ClassName.fonction() → méthode statique
    """
    
    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.tree = None
        self.lines = content.split('\n')
        
        try:
            self.tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Erreur AST pour {file_path}: {e}")
    
    def extract_all_calls(self) -> Dict[str, List[Dict]]:
        """
        Extrait TOUS les appels avec leur contexte détaillé.
        
        Returns:
            {
                'function_name': [
                    {
                        'call_type': 'simple'|'method'|'module'|'self'|'super'|'static',
                        'target': 'fonction_cible',
                        'qualifier': 'self'|'obj'|'module'|None,
                        'line': 42,
                        'full_call': 'self.process()'
                    }
                ]
            }
        """
        if not self.tree:
            return {}
        
        function_calls = defaultdict(list)
        
        # Parcourir toutes les fonctions/méthodes
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                calls = self._extract_calls_from_function(node)
                function_calls[func_name].extend(calls)
        
        return dict(function_calls)
    
    def _extract_calls_from_function(self, func_node: ast.FunctionDef) -> List[Dict]:
        """Extrait tous les appels d'une fonction."""
        calls = []
        
        for child in ast.walk(func_node):
            if isinstance(child, ast.Call):
                call_info = self._analyze_call(child)
                if call_info:
                    calls.append(call_info)
        
        return calls
    
    def _analyze_call(self, call_node: ast.Call) -> Optional[Dict]:
        line = call_node.lineno

        # CAS simple
        if isinstance(call_node.func, ast.Name):
            target = call_node.func.id
            return {
                'call_type': 'simple',
                'target': target,
                'qualifier': None,
                'line': line,
                'full_call': f"{target}()",
                'context': 'local_or_imported'
            }

        # CAS attribut (peut être chainé)
        if isinstance(call_node.func, ast.Attribute):
            # extraire la chaîne complète si imbriquée
            # parcours ascend : récupérer la "racine" de la chaîne
            value = call_node.func.value
            chain_parts = []
            last_attr = call_node.func.attr

            # si la valeur est un appel (chained: obj.method().other())
            while isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
                chain_parts.append(value.func.attr)
                value = value.func.value

            # si la valeur est un Name (module, obj, self, super)
            if isinstance(value, ast.Name):
                qualifier = value.id
                # super() est en fait un Call avec func=Name('super') — on le gère plus bas
                if qualifier == 'self':
                    return {
                        'call_type': 'self_method',
                        'target': last_attr,
                        'qualifier': 'self',
                        'line': line,
                        'full_call': f"self.{last_attr}()",
                        'context': 'same_class'
                    }
                if qualifier == 'super':
                    return {
                        'call_type': 'super_method',
                        'target': last_attr,
                        'qualifier': 'super',
                        'line': line,
                        'full_call': f"super().{last_attr}()",
                        'context': 'parent_class'
                    }

                # Si la chaîne avait des appels intermédiaires, marquer comme 'chained'
                if chain_parts:
                    return {
                        'call_type': 'chained',
                        'target': last_attr,
                        'qualifier': qualifier,
                        'line': line,
                        'full_call': f"{qualifier}.{'.'.join(chain_parts)}.{last_attr}()",
                        'context': 'complex'
                    }

                # sinon qualifier simple
                return {
                    'call_type': 'qualified',
                    'target': last_attr,
                    'qualifier': qualifier,
                    'line': line,
                    'full_call': f"{qualifier}.{last_attr}()",
                    'context': 'external'
                }

            # valeur plus complexe (Index, Attribute, etc.) -> chaine non résolue
            return {
                'call_type': 'chained',
                'target': last_attr,
                'qualifier': None,
                'line': line,
                'full_call': f"<chained>.{last_attr}()",
                'context': 'complex'
            }

        return None
