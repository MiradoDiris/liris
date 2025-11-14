import re
import ast
from typing import Tuple, Dict, List
from utils.logger import logger


class CodeValidator:
    """Validateur et nettoyeur final de code Python"""
    
    @staticmethod
    def validate_and_clean(code: str, strict: bool = True) -> Tuple[str, bool, List[str]]:
        """
        Valide et nettoie le code Python
        
        Args:
            code: Code à valider
            strict: Si True, rejette le code invalide. Si False, tente de réparer
            
        Returns:
            (code_cleaned, is_valid, errors)
        """
        errors = []
        
        # 1. Nettoyage initial
        code = CodeValidator._initial_cleanup(code)
        
        # 2. Validation syntaxe
        is_valid, syntax_errors = CodeValidator._validate_syntax(code)
        
        if not is_valid:
            errors.extend(syntax_errors)
            
            if not strict:
                logger.warning("⚠️ Syntaxe invalide, tentative de réparation...")
                code = CodeValidator._attempt_repair(code)
                is_valid, _ = CodeValidator._validate_syntax(code)
        
        # 3. Nettoyage final (même si invalide)
        code = CodeValidator._final_cleanup(code)
        
        # 4. Vérifications supplémentaires
        warnings = CodeValidator._check_code_quality(code)
        if warnings:
            for warning in warnings:
                logger.warning(f"   ⚠️ {warning}")
        
        return code, is_valid, errors
    
    @staticmethod
    def _initial_cleanup(code: str) -> str:
        """Nettoyage initial basique"""
        
        # Supprimer BOM UTF-8
        if code.startswith('\ufeff'):
            code = code[1:]
        
        # Normaliser retours à la ligne
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
        # Supprimer trailing whitespace
        lines = [line.rstrip() for line in code.split('\n')]
        code = '\n'.join(lines)
        
        return code
    
    @staticmethod
    def _validate_syntax(code: str) -> Tuple[bool, List[str]]:
        """Valide la syntaxe Python avec AST"""
        errors = []
        
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            errors.append(f"SyntaxError ligne {e.lineno}: {e.msg}")
            return False, errors
        except Exception as e:
            errors.append(f"Erreur parsing: {str(e)}")
            return False, errors
    
    @staticmethod
    def _attempt_repair(code: str) -> str:
        """Tentative de réparation automatique simple"""
        
        # 1. Fermer parenthèses/crochets non fermés
        open_parens = code.count('(') - code.count(')')
        if open_parens > 0:
            code += ')' * open_parens
        
        open_brackets = code.count('[') - code.count(']')
        if open_brackets > 0:
            code += ']' * open_brackets
        
        open_braces = code.count('{') - code.count('}')
        if open_braces > 0:
            code += '}' * open_braces
        
        # 2. Fermer quotes non fermées
        single_quotes = code.count("'") % 2
        if single_quotes != 0:
            code += "'"
        
        double_quotes = code.count('"') % 2
        if double_quotes != 0:
            code += '"'
        
        return code
    
    @staticmethod
    def _final_cleanup(code: str) -> str:
        """
        🧼 NETTOYAGE FINAL ULTRA-STRICT
        
        Garantit un formatage propre sans sauts de ligne excessifs
        """
        
        # 1. Supprimer lignes vides excessives
        code = re.sub(r'\n{4,}', '\n\n', code)
        
        # 2. Traitement ligne par ligne avec contrôle strict
        cleaned_lines = []
        consecutive_empty = 0
        
        for line in code.split('\n'):
            stripped = line.strip()
            
            if not stripped:
                # Ligne vide
                consecutive_empty += 1
                # Max 1 ligne vide consécutive
                if consecutive_empty <= 1:
                    cleaned_lines.append('')
            else:
                # Ligne avec contenu
                consecutive_empty = 0
                
                # Nettoyer espaces multiples (conserver indentation)
                indent = len(line) - len(line.lstrip())
                content = ' '.join(line.split())
                
                if indent > 0:
                    cleaned_lines.append(' ' * indent + content.lstrip())
                else:
                    cleaned_lines.append(content)
        
        code = '\n'.join(cleaned_lines)
        
        # 3. Supprimer lignes vides début/fin
        code = code.strip()
        
        # 4. Normaliser espacement autour des opérateurs
        lines = []
        for line in code.split('\n'):
            if line.strip() and not line.strip().startswith('#'):
                # Espaces autour de '='
                line = re.sub(r'(\w)\s*=\s*([^=])', r'\1 = \2', line)
                # Supprimer espaces avant parenthèses
                line = re.sub(r'(\w)\s+\(', r'\1(', line)
            lines.append(line)
        
        code = '\n'.join(lines)
        
        # 5. Normaliser fin de fichier (1 seul \n)
        if not code.endswith('\n'):
            code += '\n'
        
        return code
    
    @staticmethod
    def _check_code_quality(code: str) -> List[str]:
        """Vérifie la qualité du code et retourne des avertissements"""
        warnings = []
        lines = code.split('\n')
        
        # 1. Lignes trop longues (> 120 chars)
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                warnings.append(f"Ligne {i} trop longue ({len(line)} chars)")
        
        # 2. Indentation excessive (> 40 espaces)
        for i, line in enumerate(lines, 1):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                if indent > 40:
                    warnings.append(f"Ligne {i} indentation excessive ({indent} espaces)")
        
        # 3. Imports non standard en milieu de fichier
        first_non_import_seen = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                if stripped.startswith(('import ', 'from ')):
                    if first_non_import_seen:
                        warnings.append(f"Ligne {i}: import au milieu du fichier")
                else:
                    first_non_import_seen = True
        
        # 4. Code trop court (probablement incomplet)
        if len(code.strip()) < 20:
            warnings.append("Code très court (< 20 chars), probablement incomplet")
        
        # 5. Fonctions sans docstring
        func_pattern = r'^\s*def\s+\w+\s*\([^)]*\)\s*:\s*$'
        for i, line in enumerate(lines):
            if re.match(func_pattern, line):
                # Vérifier si ligne suivante est docstring
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not next_line.startswith(('"""', "'''")):
                        func_name = re.search(r'def\s+(\w+)', line).group(1)
                        warnings.append(f"Fonction '{func_name}' ligne {i+1} sans docstring")
        
        return warnings
    
    @staticmethod
    def batch_validate(snippets: List[Dict]) -> Tuple[List[Dict], int, int]:
        """
        Valide un batch de snippets
        
        Returns:
            (snippets_valides, count_valides, count_invalides)
        """
        if not snippets or len(snippets) == 0:
            logger.warning("⚠️ Aucun snippet à valider")
            return [], 0, 0  # ✅ Retour sûr au lieu de lever une erreur
        
        valid_snippets = []
        invalid_count = 0
        
        for idx, snippet in enumerate(snippets, 1):
            code = snippet.get('code', '')
            
            try:
                # Validation syntaxe
                ast.parse(code)
                valid_snippets.append(snippet)
                logger.debug(f"  ✅ Snippet {idx} valide")
                
            except SyntaxError as e:
                invalid_count += 1
                logger.warning(f"  ❌ Snippet {idx} invalide: {e}")
            except Exception as e:
                invalid_count += 1
                logger.error(f"  ❌ Erreur validation snippet {idx}: {e}")
        
        valid_count = len(valid_snippets)
        
        # ✅ PROTECTION : Éviter division par zéro dans les statistiques
        total = valid_count + invalid_count
        if total > 0:
            success_rate = 100 * valid_count / total
            logger.info(f"📊 Taux réussite: {success_rate:.1f}%")
        else:
            logger.warning("⚠️ Aucun snippet traité")
        
        return valid_snippets, valid_count, invalid_count