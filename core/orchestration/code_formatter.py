"""
code_formatter.py - Formateur de code Python pour snippets

Nettoie et normalise le code Python généré par les IA:
- Corrige les indentations
- Normalise les sauts de ligne
- Supprime les espaces en trop
- Répare le code corrompu
- Respecte les conventions PEP 8
"""

import re
import ast
from typing import List, Tuple
from utils.logger import logger


class PythonCodeFormatter:
    """Formateur de code Python avec réparation automatique"""
    
    def __init__(self, indent_size: int = 4):
        """
        Initialize formatter
        
        Args:
            indent_size: Nombre d'espaces pour l'indentation (défaut: 4)
        """
        self.indent_size = indent_size
    
    def format(self, code: str) -> str:
        """
        Formate le code Python
        
        Args:
            code: Code source à formater
            
        Returns:
            Code formaté
        """
        try:
            # Étape 0: Détecter et réparer le code corrompu
            code = self._repair_corrupted_code(code)
            
            # Étape 1: Nettoyage préliminaire
            code = self._preliminary_cleanup(code)
            
            # Étape 2: Normaliser les indentations
            code = self._normalize_indentation(code)
            
            # Étape 3: Normaliser les sauts de ligne
            code = self._normalize_line_breaks(code)
            
            # Étape 4: Nettoyer les espaces
            code = self._clean_whitespace(code)
            
            # Étape 5: Formater les imports
            code = self._format_imports(code)
            
            # Étape 6: Vérifier la syntaxe
            if not self._verify_syntax(code):
                logger.warning("⚠️ Syntaxe Python invalide détectée après formatage")
            
            return code
            
        except Exception as e:
            logger.error(f"❌ Erreur formatage: {e}")
            return code
    
    def _repair_corrupted_code(self, code: str) -> str:
        """
        Répare le code corrompu avec espaces et retours à la ligne anormaux
        """
        logger.info("🔧 Détection et réparation du code corrompu...")
        
        # 1. Détecter si le code est corrompu (beaucoup d'espaces entre tokens)
        if re.search(r'\w\s{3,}\w', code):
            logger.warning("⚠️ Code corrompu détecté - Réparation en cours...")
            
            # 2. Supprimer tous les espaces multiples entre les tokens
            lines = code.split('\n')
            repaired_lines = []
            
            for line in lines:
                # Mesurer l'indentation d'origine
                indent = len(line) - len(line.lstrip())
                stripped = line.strip()
                
                if stripped:
                    # Supprimer tous les espaces multiples
                    repaired = re.sub(r'\s+', ' ', stripped)
                    
                    # Restaurer les espaces corrects autour des opérateurs
                    repaired = self._fix_operators_spacing(repaired)
                    
                    # Restaurer l'indentation
                    repaired_lines.append(' ' * indent + repaired)
                else:
                    repaired_lines.append('')
            
            code = '\n'.join(repaired_lines)
        
        # 3. Réparer les structures Python cassées
        code = self._repair_python_structures(code)
        
        return code
    
    def _fix_operators_spacing(self, line: str) -> str:
        """Corrige l'espacement autour des opérateurs Python"""
        
        # Supprimer espaces avant : et ,
        line = re.sub(r'\s+:', ':', line)
        line = re.sub(r'\s+,', ',', line)
        
        # Ajouter espace après : et , (sauf dans les slices)
        line = re.sub(r':(?![:\]])', ': ', line)
        line = re.sub(r',(?!\s)', ', ', line)
        
        # Opérateurs de comparaison
        line = re.sub(r'\s*(==|!=|<=|>=|<|>)\s*', r' \1 ', line)
        
        # Opérateurs arithmétiques (sauf ** et //)
        line = re.sub(r'(?<!\*)\s*([+\-*/%])\s*(?!\*)', r' \1 ', line)
        
        # Opérateur d'affectation =
        line = re.sub(r'\s*=\s*(?!=)', ' = ', line)
        
        # Nettoyer les espaces multiples créés
        line = re.sub(r' {2,}', ' ', line)
        
        return line
    
    def _repair_python_structures(self, code: str) -> str:
        """Répare les structures Python cassées"""
        
        # 1. Réparer les définitions de fonctions/classes
        code = re.sub(r'def\s+(\w+)\s*\(\s*', r'def \1(', code)
        code = re.sub(r'class\s+(\w+)\s*\(\s*', r'class \1(', code)
        code = re.sub(r'class\s+(\w+)\s*:', r'class \1:', code)
        
        # 2. Réparer les imports
        code = re.sub(r'import\s+', r'import ', code)
        code = re.sub(r'from\s+', r'from ', code)
        
        # 3. Réparer les mots-clés
        keywords = ['if', 'elif', 'else', 'while', 'for', 'try', 'except', 
                   'finally', 'with', 'return', 'yield', 'raise', 'pass',
                   'break', 'continue', 'assert', 'lambda']
        
        for keyword in keywords:
            code = re.sub(rf'\b{keyword}\s+', f'{keyword} ', code)
        
        # 4. Réparer les parenthèses, crochets et accolades
        code = re.sub(r'\(\s+', '(', code)
        code = re.sub(r'\s+\)', ')', code)
        code = re.sub(r'\[\s+', '[', code)
        code = re.sub(r'\s+\]', ']', code)
        code = re.sub(r'\{\s+', '{', code)
        code = re.sub(r'\s+\}', '}', code)
        
        # 5. Réparer les strings avec f-strings
        code = re.sub(r'f\s+"', 'f"', code)
        code = re.sub(r"f\s+'", "f'", code)
        
        return code
    
    def _preliminary_cleanup(self, code: str) -> str:
        """Nettoyage préliminaire du code"""
        
        # Supprimer les métadonnées résiduelles
        code = re.sub(r'^\s*#\s*(ACTION|FILE|TARGET|DESCRIPTION):\s*[^\n]*\n', '', code, flags=re.MULTILINE | re.IGNORECASE)
        
        # Supprimer les backticks markdown
        code = re.sub(r'```python\s*\n?', '', code)
        code = re.sub(r'```\s*$', '', code)
        
        # Supprimer les notes de bas de page
        code = re.sub(r'\d+,\s*\d+s\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^(Rapide|Ajouter|Implémenter|Optimiser|Soumettre|bas).*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^={50,}$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^NOTE:.*$', '', code, flags=re.MULTILINE)
        
        # Supprimer les lignes vides au début et à la fin
        code = code.strip()
        
        return code
    
    def _normalize_indentation(self, code: str) -> str:
        """Normalise les indentations selon PEP 8"""
        
        lines = code.split('\n')
        normalized_lines = []
        indent_stack = [0]
        
        for line in lines:
            stripped = line.lstrip()
            
            # Ligne vide
            if not stripped:
                normalized_lines.append('')
                continue
            
            # Calculer le niveau d'indentation
            indent_level = self._calculate_indent_level(stripped, indent_stack)
            
            # Appliquer l'indentation
            indented_line = ' ' * (indent_level * self.indent_size) + stripped
            normalized_lines.append(indented_line)
            
            # Mettre à jour la pile d'indentation
            indent_stack = self._update_indent_stack(stripped, indent_stack, indent_level)
        
        return '\n'.join(normalized_lines)
    
    def _calculate_indent_level(self, line: str, indent_stack: List[int]) -> int:
        """Calcule le niveau d'indentation pour une ligne"""
        
        current_level = indent_stack[-1] if indent_stack else 0
        
        # elif/else/except/finally - même niveau que if/try
        if re.match(r'^(elif|else|except|finally)\b', line):
            return max(0, current_level - 1) if current_level > 0 else 0
        
        # Ligne de fermeture
        if line.rstrip().startswith((')', ']', '}')):
            return max(0, current_level - 1)
        
        return current_level
    
    def _update_indent_stack(self, line: str, indent_stack: List[int], current_level: int) -> List[int]:
        """Met à jour la pile d'indentation après une ligne"""
        
        stripped = line.rstrip()
        
        # Augmenter l'indentation après :
        if stripped.endswith(':'):
            return indent_stack + [current_level + 1]
        
        # elif/else/except/finally - ajuster la pile
        if re.match(r'^(elif|else|except|finally)\b', line):
            if len(indent_stack) > 1:
                indent_stack = indent_stack[:-1]
            return indent_stack + [current_level + 1]
        
        # Gérer les parenthèses
        open_count = stripped.count('(') + stripped.count('[') + stripped.count('{')
        close_count = stripped.count(')') + stripped.count(']') + stripped.count('}')
        
        if open_count > close_count:
            return indent_stack + [current_level + 1]
        elif close_count > open_count and len(indent_stack) > 1:
            return indent_stack[:-1]
        
        return indent_stack
    
    def _normalize_line_breaks(self, code: str) -> str:
        """Normalise les sauts de ligne selon PEP 8"""
        
        lines = code.split('\n')
        normalized = []
        prev_line_type = None
        
        for line in lines:
            stripped = line.strip()
            
            # Déterminer le type de ligne
            line_type = self._get_line_type(stripped)
            
            # Ajouter des lignes vides selon PEP 8
            if prev_line_type and line_type:
                blank_lines = self._get_blank_lines_between(prev_line_type, line_type)
                for _ in range(blank_lines):
                    normalized.append('')
            
            normalized.append(line)
            
            if stripped:
                prev_line_type = line_type
        
        # Supprimer les lignes vides multiples
        result = []
        blank_count = 0
        
        for line in normalized:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    result.append(line)
            else:
                blank_count = 0
                result.append(line)
        
        return '\n'.join(result)
    
    def _get_line_type(self, line: str) -> str:
        """Détermine le type d'une ligne"""
        
        if not line:
            return 'blank'
        if line.startswith('#'):
            return 'comment'
        if line.startswith('import ') or line.startswith('from '):
            return 'import'
        if line.startswith('class '):
            return 'class'
        if line.startswith('def ') or line.startswith('async def '):
            return 'function'
        if line.startswith('@'):
            return 'decorator'
        
        return 'code'
    
    def _get_blank_lines_between(self, prev_type: str, curr_type: str) -> int:
        """Retourne le nombre de lignes vides à insérer selon PEP 8"""
        
        # 2 lignes vides avant les classes et fonctions top-level
        if curr_type == 'class':
            if prev_type in ['import', 'class', 'function']:
                return 2
        
        if curr_type == 'function' and prev_type in ['class', 'function']:
            return 2
        
        # 1 ligne vide entre les méthodes
        if curr_type == 'function' and prev_type == 'code':
            return 1
        
        # Pas de ligne vide entre décorateur et définition
        if prev_type == 'decorator':
            return 0
        
        return 0
    
    def _clean_whitespace(self, code: str) -> str:
        """Nettoie les espaces superflus"""
        
        lines = code.split('\n')
        cleaned = []
        
        for line in lines:
            # Supprimer les espaces en fin de ligne
            line = line.rstrip()
            
            if line.strip():
                # Nettoyer les espaces multiples dans le contenu
                indent = len(line) - len(line.lstrip())
                content = line.lstrip()
                
                # Normaliser les espaces (sauf dans les strings)
                content = self._normalize_content_spacing(content)
                
                line = ' ' * indent + content
            
            cleaned.append(line)
        
        return '\n'.join(cleaned)
    
    def _normalize_content_spacing(self, content: str) -> str:
        """Normalise l'espacement du contenu en préservant les strings"""
        
        # Préserver les strings
        strings = []
        placeholder = '___STRING_{}___'
        
        # Extraire les strings
        for i, match in enumerate(re.finditer(r'(["\'])(?:(?=(\\?))\2.)*?\1', content)):
            strings.append(match.group())
            content = content.replace(match.group(), placeholder.format(i), 1)
        
        # Normaliser les espaces
        content = self._fix_operators_spacing(content)
        
        # Restaurer les strings
        for i, string in enumerate(strings):
            content = content.replace(placeholder.format(i), string)
        
        return content
    
    def _format_imports(self, code: str) -> str:
        """Formate les imports selon PEP 8"""
        
        lines = code.split('\n')
        imports = []
        from_imports = []
        other_lines = []
        
        in_imports = True
        
        for line in lines:
            stripped = line.strip()
            
            if in_imports:
                if stripped.startswith('import '):
                    imports.append(stripped)
                elif stripped.startswith('from '):
                    from_imports.append(stripped)
                elif stripped and not stripped.startswith('#'):
                    in_imports = False
                    other_lines.append(line)
                else:
                    other_lines.append(line)
            else:
                other_lines.append(line)
        
        # Trier les imports
        imports.sort()
        from_imports.sort()
        
        # Reconstruire
        result = []
        
        if imports:
            result.extend(imports)
            if from_imports or other_lines:
                result.append('')
        
        if from_imports:
            result.extend(from_imports)
            if other_lines:
                result.append('')
        
        result.extend(other_lines)
        
        return '\n'.join(result)
    
    def _verify_syntax(self, code: str) -> bool:
        """Vérifie la syntaxe Python du code"""
        
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning(f"⚠️ Erreur syntaxe Python: {e}")
            return False
    
    def format_snippet(self, snippet: dict) -> dict:
        """
        Formate un snippet complet
        
        Args:
            snippet: Dict contenant le snippet (avec clé 'code')
            
        Returns:
            Snippet avec code formaté
        """
        try:
            original_code = snippet.get('code', '')
            
            if not original_code or not original_code.strip():
                return snippet
            
            logger.info(f"🎨 Formatage du snippet: {snippet.get('file', 'N/A')}")
            logger.debug(f"   Code original: {len(original_code)} chars")
            
            # Formater le code
            formatted_code = self.format(original_code)
            
            logger.debug(f"   Code formaté: {len(formatted_code)} chars")
            
            # Mettre à jour le snippet
            snippet['code'] = formatted_code
            snippet['formatted'] = True
            
            return snippet
            
        except Exception as e:
            logger.error(f"❌ Erreur formatage snippet: {e}")
            return snippet


def format_extracted_snippets(snippets: List[dict], indent_size: int = 4) -> List[dict]:
    """
    Formate une liste de snippets extraits
    
    Args:
        snippets: Liste de snippets à formater
        indent_size: Taille de l'indentation (défaut: 4)
        
    Returns:
        Liste de snippets formatés
    """
    formatter = PythonCodeFormatter(indent_size=indent_size)
    formatted_snippets = []
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🎨 FORMATAGE DE {len(snippets)} SNIPPET(S)")
    logger.info(f"{'='*80}")
    
    for idx, snippet in enumerate(snippets, 1):
        logger.info(f"\n📦 Snippet {idx}/{len(snippets)}")
        formatted_snippet = formatter.format_snippet(snippet.copy())
        formatted_snippets.append(formatted_snippet)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ {len(formatted_snippets)} snippet(s) formaté(s)")
    logger.info(f"{'='*80}\n")
    
    return formatted_snippets


# ============================================================================
# TESTS
# ============================================================================

def test_formatter():
    """Test du formateur"""
    
    # Code mal formaté
    messy_code = """
# ACTION: AJOUTER
# FILE: test.py
def   validate_email(  email:str)->bool:
    import re
    pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    if    re.match(pattern,email):
        return True
    else:
        return False


class   EmailValidator:
    def __init__(self,strict=True):
        self.strict=strict
    
    def validate(self,email):
        return validate_email(email)
"""
    
    print("="*80)
    print("CODE ORIGINAL:")
    print("="*80)
    print(messy_code)
    
    # Formater
    formatter = PythonCodeFormatter()
    formatted = formatter.format(messy_code)
    
    print("\n" + "="*80)
    print("CODE FORMATÉ:")
    print("="*80)
    print(formatted)
    
    # Test avec snippet
    snippet = {
        'action': 'AJOUTER',
        'file': 'test.py',
        'code': messy_code,
        'language': 'python'
    }
    
    formatted_snippet = formatter.format_snippet(snippet)
    
    print("\n" + "="*80)
    print("SNIPPET FORMATÉ:")
    print("="*80)
    print(f"Action: {formatted_snippet['action']}")
    print(f"File: {formatted_snippet['file']}")
    print(f"Formatted: {formatted_snippet.get('formatted', False)}")
    print(f"\nCode:")
    print(formatted_snippet['code'])


def test_corrupted_code():
    """Test de réparation du code corrompu"""
    
    # Code corrompu (comme dans document 2)
    corrupted_code = """
import
    requests
from
    utils.logger
import
    logger
class ApiTester
    :
    @
    staticmethod
    def test_api_key
    (
        platform_name,
        api_config
    ):
        pass
"""
    
    print("="*80)
    print("CODE CORROMPU:")
    print("="*80)
    print(corrupted_code)
    
    # Formater
    formatter = PythonCodeFormatter()
    repaired = formatter.format(corrupted_code)
    
    print("\n" + "="*80)
    print("CODE RÉPARÉ:")
    print("="*80)
    print(repaired)


if __name__ == "__main__":
    print("TEST 1: Formatage standard")
    test_formatter()
    
    print("\n\n" + "="*100)
    print("TEST 2: Réparation code corrompu")
    print("="*100 + "\n")
    test_corrupted_code()