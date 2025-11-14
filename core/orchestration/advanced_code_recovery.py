import re
import ast
import textwrap
import tokenize
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import io
from utils.logger import logger


@dataclass
class RepairStats:
    """Statistiques de réparation détaillées"""
    original_chars: int = 0
    repaired_chars: int = 0
    lines_merged: int = 0
    dots_fixed: int = 0
    colons_fixed: int = 0
    operators_fixed: int = 0
    pass_removed: int = 0
    indentation_fixed: int = 0
    methods_merged: int = 0
    urls_fixed: int = 0
    strings_fixed: int = 0
    parentheses_closed: int = 0
    keywords_fixed: int = 0
    junk_removed: int = 0
    syntax_valid: bool = False
    corruption_level: int = 0
    repair_attempts: int = 0
    quality_score: float = 0.0
    recoverable: bool = True    

@dataclass
class LineContext:
    """Contexte d'une ligne pour déterminer si elle est incomplète"""
    line: str
    indent: int
    stripped: str
    ends_with_incomplete: bool
    starts_with_continuation: bool
    is_keyword_only: bool
    is_operator_only: bool

class UltimateLineMerger:
    """Fusionneur ultra-intelligent de lignes éclatées"""
    
    # Mots-clés Python qui DOIVENT avoir une suite
    INCOMPLETE_KEYWORDS = {
        'if', 'elif', 'else', 'for', 'while', 'def', 'class',
        'import', 'from', 'return', 'raise', 'assert', 'with',
        'try', 'except', 'finally', 'async', 'await'
    }
    
    # Tokens qui indiquent une continuation nécessaire
    INCOMPLETE_ENDINGS = {
        '(', '[', '{',           # Ouvertures
        ',',                     # Virgule
        '=', '+=', '-=', '*=',   # Affectations
        '+', '-', '*', '/', '//', '**', '%',  # Opérateurs
        '==', '!=', '<', '>', '<=', '>=',     # Comparaisons
        'and', 'or', 'not', 'in', 'is',       # Logiques
        ':', '->'                # Type hints
    }
    
    # Tokens qui indiquent le début d'une continuation
    CONTINUATION_STARTERS = {
        ')', ']', '}',           # Fermetures
        '.', '[',                # Accès
        '+', '-', '*', '/', '//', '**', '%',  # Opérateurs
        '==', '!=', '<', '>', '<=', '>=',     # Comparaisons
        'and', 'or', 'in', 'is', # Logiques
    }
    
    @staticmethod
    def analyze_line(line: str) -> LineContext:
        """Analyse une ligne pour déterminer son contexte"""
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        
        # Vérifier si la ligne se termine par un token incomplet
        ends_with_incomplete = False
        for token in UltimateLineMerger.INCOMPLETE_ENDINGS:
            if stripped.endswith(token):
                ends_with_incomplete = True
                break
        
        # Vérifier si la ligne commence par un token de continuation
        starts_with_continuation = False
        for token in UltimateLineMerger.CONTINUATION_STARTERS:
            if stripped.startswith(token):
                starts_with_continuation = True
                break
        
        # Vérifier si c'est juste un mot-clé
        is_keyword_only = stripped in UltimateLineMerger.INCOMPLETE_KEYWORDS
        
        # Vérifier si c'est juste un opérateur
        is_operator_only = stripped in UltimateLineMerger.INCOMPLETE_ENDINGS
        
        return LineContext(
            line=line,
            indent=indent,
            stripped=stripped,
            ends_with_incomplete=ends_with_incomplete,
            starts_with_continuation=starts_with_continuation,
            is_keyword_only=is_keyword_only,
            is_operator_only=is_operator_only
        )
    
    @staticmethod
    def should_merge_with_next(ctx: LineContext, next_ctx: LineContext) -> bool:
        """Détermine si deux lignes consécutives doivent être fusionnées"""
        
        # Cas 1 : Ligne vide → ne pas fusionner
        if not ctx.stripped or not next_ctx.stripped:
            return False
        
        # Cas 2 : Mot-clé seul (if, def, etc.) → fusionner
        if ctx.is_keyword_only:
            return True
        
        # Cas 3 : Opérateur seul (<, =, etc.) → fusionner
        if ctx.is_operator_only:
            return True
        
        # Cas 4 : Ligne se termine par token incomplet → fusionner
        if ctx.ends_with_incomplete:
            return True
        
        # Cas 5 : Ligne suivante commence par continuation → fusionner
        if next_ctx.starts_with_continuation:
            return True
        
        # Cas 6 : Parenthèses/crochets non fermés
        open_parens = ctx.stripped.count('(') - ctx.stripped.count(')')
        open_brackets = ctx.stripped.count('[') - ctx.stripped.count(']')
        open_braces = ctx.stripped.count('{') - ctx.stripped.count('}')
        
        if open_parens > 0 or open_brackets > 0 or open_braces > 0:
            return True
        
        # Cas 7 : Ligne très courte (< 10 chars) et suivante similaire
        if len(ctx.stripped) < 10 and next_ctx.indent > 0:
            # Vérifier si c'est un opérateur ou un nombre
            if re.match(r'^[<>=!+\-*/]+$|^\d+\.?\d*$', ctx.stripped):
                return True
        
        return False
    
    @staticmethod
    def merge_lines(lines: List[str]) -> List[str]:
        """Fusionne intelligemment les lignes éclatées"""
        if not lines:
            return lines
        
        merged = []
        i = 0
        
        while i < len(lines):
            ctx = UltimateLineMerger.analyze_line(lines[i])
            
            # Construire la ligne fusionnée
            merged_line = lines[i].rstrip()
            j = i + 1
            
            # Fusionner tant que nécessaire
            while j < len(lines):
                next_ctx = UltimateLineMerger.analyze_line(lines[j])
                
                if UltimateLineMerger.should_merge_with_next(ctx, next_ctx):
                    # Fusionner avec espace intelligent
                    if ctx.is_operator_only or next_ctx.is_operator_only:
                        # Opérateur : pas d'espace
                        merged_line = merged_line.rstrip() + next_ctx.stripped
                    elif ctx.ends_with_incomplete and ctx.stripped.endswith(('(', '[', '{')):
                        # Après ouverture : pas d'espace
                        merged_line = merged_line.rstrip() + next_ctx.stripped
                    else:
                        # Cas général : ajouter un espace
                        merged_line = merged_line.rstrip() + ' ' + next_ctx.stripped
                    
                    # Mettre à jour le contexte
                    ctx = UltimateLineMerger.analyze_line(merged_line)
                    j += 1
                else:
                    # Pas de fusion → arrêter
                    break
            
            # Ajouter la ligne fusionnée
            if merged_line.strip():
                merged.append(merged_line)
            
            # Avancer l'index
            i = j
        
        return merged


# ============================================================================
# 🆕 CLASSE ENHANCED DOM FIXER (CORRECTIFS AVANCÉS)
# ============================================================================

class EnhancedDomFixer:
    """Correctifs additionnels pour cas extrêmes DOM"""
    
    @staticmethod
    def fix_broken_imports(code: str) -> Tuple[str, int]:
        """
        Corrige les imports éclatés:
        - 'import Optional' -> 'from typing import Optional'
        - 'from typing' seul -> récupère les imports suivants
        """
        fixes = 0
        
        # Cas 1: "import Optional" sans from typing
        pattern = r'^import\s+(Optional|Dict|List|Union|Tuple|Set)\b'
        matches = re.findall(pattern, code, re.MULTILINE)
        if matches:
            imports_to_fix = set(matches)
            code = re.sub(pattern, '', code, flags=re.MULTILINE)
            # Ajouter au début
            typing_import = f"from typing import {', '.join(sorted(imports_to_fix))}"
            code = typing_import + '\n' + code
            fixes += len(imports_to_fix)
        
        # Cas 2: "from typing\ndef..." -> "from typing import ...\ndef..."
        pattern = r'from\s+typing\s*\n\s*def'
        if re.search(pattern, code):
            # Chercher Optional/Dict/etc. dans le code
            typing_types = re.findall(r'\b(Optional|Dict|List|Union|Tuple)\b', code)
            if typing_types:
                unique_types = sorted(set(typing_types))
                typing_import = f"from typing import {', '.join(unique_types)}"
                code = re.sub(r'from\s+typing\s*\n', typing_import + '\n', code)
                fixes += 1
        
        # Cas 3: "import math\nfrom typing" éclaté
        code = re.sub(r'(import\s+\w+)\s*\n\s*from\s+typing\s*\n', r'\1\nfrom typing import Optional\n', code)
        
        return code, fixes
    
    @staticmethod
    def fix_multiline_type_hints(code: str) -> Tuple[str, int]:
        """
        Corrige les annotations de type éclatées sur plusieurs lignes:
        - 'Optional\n    [float]\n     = \n    None)' -> 'Optional[float] = None)'
        """
        fixes = 0
        
        # Pattern: Optional suivi de [type] éclaté
        pattern = r'Optional\s*\n\s*\[\s*(\w+)\s*\]\s*\n\s*=\s*\n\s*(\w+)\s*\)'
        matches = len(re.findall(pattern, code))
        if matches:
            code = re.sub(pattern, r'Optional[\1] = \2)', code)
            fixes += matches
        
        # Pattern plus simple: Optional[ éclaté
        pattern2 = r'Optional\s*\n\s*\[\s*(\w+)\s*\]'
        matches2 = len(re.findall(pattern2, code))
        if matches2:
            code = re.sub(pattern2, r'Optional[\1]', code)
            fixes += matches2
        
        # Pattern: type] = value éclaté
        pattern3 = r'\]\s*\n\s*=\s*\n\s*(\w+)'
        matches3 = len(re.findall(pattern3, code))
        if matches3:
            code = re.sub(pattern3, r'] = \1', code)
            fixes += matches3
        
        return code, fixes
    
    @staticmethod
    def fix_broken_return_arrow(code: str) -> Tuple[str, int]:
        """
        Corrige '- > float\n:' -> '-> float:'
        """
        fixes = 0
        
        # Pattern: - > type :
        pattern = r'-\s*>\s*(\w+)\s*\n\s*:'
        matches = len(re.findall(pattern, code))
        if matches:
            code = re.sub(pattern, r'-> \1:', code)
            fixes += matches
        
        # Pattern plus agressif: - > seul
        pattern2 = r'-\s*>\s*\n\s*(\w+)'
        matches2 = len(re.findall(pattern2, code))
        if matches2:
            code = re.sub(pattern2, r'-> \1', code)
            fixes += matches2
        
        return code, fixes
    
    @staticmethod
    def fix_broken_docstrings(code: str) -> Tuple[str, int]:
        """
        Corrige les docstrings éclatés:
        - 'Args: param:\n    type' -> 'Args:\n        param: type'
        """
        fixes = 0
        
        # Pattern: Args: description_sans_newline
        pattern = r'(Args:\s*)(\w+)'
        if re.search(pattern, code):
            code = re.sub(pattern, r'\1\n        \2', code)
            fixes += 1
        
        # Pattern: Returns: description_sans_newline
        pattern2 = r'(Returns:\s*)(\w+)'
        if re.search(pattern2, code):
            code = re.sub(pattern2, r'\1\n        \2', code)
            fixes += 1
        
        return code, fixes
    
    @staticmethod
    def fix_broken_conditionals(code: str) -> Tuple[str, int]:
        """
        Corrige les conditions éclatées:
        - 'if earth_cross_section_km2\n    is\n    None:' -> 'if earth_cross_section_km2 is None:'
        """
        fixes = 0
        
        # Pattern: if var\n    is\n    None
        pattern = r'if\s+(\w+)\s*\n\s*is\s*\n\s*None\s*:'
        matches = len(re.findall(pattern, code))
        if matches:
            code = re.sub(pattern, r'if \1 is None:', code)
            fixes += matches
        
        # Pattern plus général: if condition éclatée
        pattern2 = r'if\s+(\w+)\s*\n\s*(is|==|!=|<|>)\s*\n\s*(\w+)\s*:'
        matches2 = len(re.findall(pattern2, code))
        if matches2:
            code = re.sub(pattern2, r'if \1 \2 \3:', code)
            fixes += matches2
        
        return code, fixes
    
    @staticmethod
    def fix_broken_assignments(code: str) -> Tuple[str, int]:
        """
        Corrige les assignations éclatées avec opérateurs arithmétiques:
        - 'var\n     + \n    value' -> 'var + value'
        - 'var\n     / \n    2' -> 'var / 2'
        """
        fixes = 0
        
        # Pattern: var\n     op \n    value
        operators = [r'\+', r'-', r'\*', r'/', r'//', r'\*\*', r'%']
        for op in operators:
            pattern = rf'(\w+)\s*\n\s*{op}\s*\n\s*(\w+|\d+)'
            matches = len(re.findall(pattern, code))
            if matches:
                code = re.sub(pattern, rf'\1 {op.replace(chr(92), "")} \2', code)
                fixes += matches
        
        return code, fixes
    
    @staticmethod
    def fix_broken_function_calls(code: str) -> Tuple[str, int]:
        """
        Corrige les appels de fonction éclatés:
        - 'min\n    (value,' -> 'min(value,'
        - 'func(\n        arg' -> 'func(arg'
        """
        fixes = 0
        
        # Pattern: function_name\n    (
        pattern = r'(\w+)\s*\n\s*\('
        matches = len(re.findall(pattern, code))
        if matches:
            code = re.sub(pattern, r'\1(', code)
            fixes += matches
        
        # Pattern: (\n        arg -> (arg (une seule ligne d'écart)
        pattern2 = r'\(\s*\n\s{1,8}(\w+)'
        matches2 = len(re.findall(pattern2, code))
        if matches2:
            code = re.sub(pattern2, r'(\1', code)
            fixes += matches2
        
        return code, fixes
    
    @staticmethod
    def apply_all_fixes(code: str, verbose: bool = True) -> str:
        """
        Applique tous les correctifs dans l'ordre optimal
        """
        total_fixes = 0
        
        if verbose:
            print("\n🔧 Application des correctifs avancés DOM...")
        
        # 1. Imports (en premier, car affecte début du fichier)
        code, fixes = EnhancedDomFixer.fix_broken_imports(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} import(s) corrigé(s)")
        
        # 2. Type hints (avant function signatures)
        code, fixes = EnhancedDomFixer.fix_multiline_type_hints(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} type hint(s) corrigé(s)")
        
        # 3. Return arrows
        code, fixes = EnhancedDomFixer.fix_broken_return_arrow(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} flèche(s) de retour corrigée(s)")
        
        # 4. Conditionals
        code, fixes = EnhancedDomFixer.fix_broken_conditionals(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} condition(s) corrigée(s)")
        
        # 5. Assignments
        code, fixes = EnhancedDomFixer.fix_broken_assignments(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} assignation(s) corrigée(s)")
        
        # 6. Function calls
        code, fixes = EnhancedDomFixer.fix_broken_function_calls(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} appel(s) de fonction corrigé(s)")
        
        # 7. Docstrings
        code, fixes = EnhancedDomFixer.fix_broken_docstrings(code)
        total_fixes += fixes
        if verbose and fixes:
            print(f"   ✅ {fixes} docstring(s) corrigée(s)")
        
        if verbose:
            print(f"\n📊 Total: {total_fixes} corrections appliquées")
        
        return code


# ============================================================================
# CLASSE DOM EXTRACTION FIXER (RÉPARATEUR PRINCIPAL)
# ============================================================================
    
class DomExtractionFixer:
    BLOCK_KEYWORDS = [
        'def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except',
        'finally', 'with', 'async def', 'async for', 'async with'
    ]

    # Nouveaux patterns de junk à détecter
    JUNK_PATTERNS = [
        r'Réduire\s*Réduire',
        r'Envelopper\s*Envelopper',
        r'python\s*Réduire',
        r'Copier\s*le\s*code',
        r'```python',
        r'```',
        r'Rapide',
        r'Ajouter\s+vérification\s+de\s+\w+',
        r'Implémenter\s+logging\s+des\s+erreurs',
        r'Corriger\s+syntaxe\s+et\s+formatage',
        r'Soumettre',
        r'Grok\s*=+',
        r'NOTE:\s*extraction\s+coming\s+soon',
        r'Will\s+support\s+format',
        r'social',
        r'=+\s*$',  # Lignes de séparateurs seuls
        r'^\s*-\s*$',  # Tirets seuls
        r'Réessayer\s*$',
        r'Comment\s+puis\s*-\s*je\s+vous\s+aider\s*\?',
        r'Sonnet\s+\d+\.\d+\s*$',
        r'\(\d+\s*characters?\s*total\)',
        r'Regenerate',
        r'Copy code',
        r'How can I help\?',
        r'^\s*-\s*$',
        r'===+\s*$'  # Lignes vides/junk UI
    ]
    
    @classmethod
    def fix_extracted_code(cls, code: str, verbose: bool = False) -> str:
        """Point d'entrée principal - VERSION 6.0 ENHANCED"""
        try:
            # ✅ PHASE 0: Correctifs avancés DOM
            code = EnhancedDomFixer.apply_all_fixes(code, verbose=verbose)
            
            # ✅ PHASE 1-17: Réparation v5 standard
            repaired, _ = cls.repair_ultra_v5(code, verbose=verbose)
            return repaired
        except Exception as e:
            logger.error(f"Erreur réparation v6: {e}")
            # Fallback vers v5 sans correctifs avancés
            repaired, _ = cls.repair_ultra_v5(code, verbose=verbose)
            return repaired
    
    # ... (TOUTES LES AUTRES MÉTHODES RESTENT IDENTIQUES)
    # Je ne les réécris pas car elles sont déjà bonnes
    
    @classmethod
    def repair_ultra_v5(cls, corrupted_code: str, verbose: bool = True) -> Tuple[str, RepairStats]:
        """Version avec protection anti-sur-suppression"""
        stats = RepairStats()
        stats.original_chars = len(corrupted_code)

        if not corrupted_code or len(corrupted_code.strip()) < 10:
            if verbose:
                logger.warning("Code trop court, aucune réparation nécessaire")
            return corrupted_code, stats

        if verbose:
            print("\n" + "="*80)
            print("RÉPARATION ULTIMATE DOM v6.1 - TOKENS ÉCLATÉS PRIORITAIRES")
            print("="*80)
            print(f"Taille originale: {len(corrupted_code)} chars")

        # ✅ PHASE 0.0 : EXTRACTION ET PROTECTION DES IMPORTS
        if verbose:
            print("\n🔧 PHASE 0.0/18 : Extraction et protection des imports")
        
        imports, code = cls._preserve_imports(corrupted_code)  # ✅ FIX: Extraction imports
        
        if verbose and imports:
            print(f"   ✅ {len(imports)} import(s) préservé(s)")
        
        # PHASE 0.1 : FUSION INTELLIGENTE
        if verbose:
            print("\n🔧 PHASE 0.1/18 : Fusion intelligente des lignes éclatées")

        lines = code.split('\n')
        original_line_count = len(lines)

        merged_lines = UltimateLineMerger.merge_lines(lines)

        code = '\n'.join(merged_lines)

        stats.lines_merged = original_line_count - len(merged_lines)

        if verbose:
            print(f"   ✅ {stats.lines_merged} lignes fusionnées")
            print(f"   📊 {original_line_count} → {len(merged_lines)} lignes")

        # PHASE 0.2 : RECONSTRUCTION TOKENS ÉCLATÉS
        if verbose:
            print("\nPHASE 0.2/17 : Reconstruction tokens Python éclatés (DOM)")
        code = cls._reconstruct_split_tokens(code, stats, verbose)

        if verbose:
            print("\n🔧 PHASE 0.3/17 : Correction indentation excessive")
        code = cls._fix_corrupted_indentation(code, stats, verbose)

        # PHASE 0.4 : CALCUL SCORE PYTHON
        python_score = cls._calculate_python_score(code)
        if verbose:
            print(f"\nScore Python initial: {python_score}/100")
        ultra_safe_mode = (python_score >= 70)
        if ultra_safe_mode:
            logger.info("MODE ULTRA-SAFE ACTIVÉ (code Python de haute qualité détecté)")

        # PHASE 0.5 : DÉTECTION DU NIVEAU DE CORRUPTION
        stats.corruption_level = cls._detect_corruption_level_v5(code)
        if verbose:
            corruption_emoji = "🟢" if stats.corruption_level < 4 else "🟡" if stats.corruption_level < 7 else "🔴"
            print(f"\n{corruption_emoji} NIVEAU DE CORRUPTION: {stats.corruption_level}/10")
        if ultra_safe_mode:
            stats.corruption_level = min(stats.corruption_level, 3)
            if verbose:
                print(f"Niveau abaissé à {stats.corruption_level} (protection code valide)")

        # PHASE 0.6 : NETTOYAGE JUNK
        if verbose:
            print("\nPHASE 0.6/17 : Nettoyage junk sécurisé")
        if not ultra_safe_mode:
            code = cls._remove_junk_aggressive(code, stats, verbose)
        else:
            if verbose:
                print("Nettoyage junk DÉSACTIVÉ (mode ultra-safe)")

        # PHASES 1-16 : RÉPARATIONS STANDARD
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            stats.repair_attempts = attempt
            if verbose and attempt > 1:
                print(f"\nTENTATIVE {attempt}/{max_attempts}")
            aggressive_mode = (stats.corruption_level >= 7) and not ultra_safe_mode

            if verbose: print("\nPHASE 1/17 : Correction points isolés")
            code = cls._fix_isolated_dots(code, stats, verbose)

            if verbose: print("\nPHASE 2/17 : Correction opérateurs espacés")
            code = cls._fix_spaced_operators(code, stats, verbose)

            if verbose: print("\nPHASE 3/17 : Correction mots-clés éclatés")  # ✅ FIX: Renommé
            code = cls._fix_split_keywords(code, stats, verbose)

            if verbose: print("\nPHASE 4/17 : Fusion lignes éclatées")
            code = cls._merge_scattered_lines(code, stats, verbose)

            if verbose: print("\nPHASE 5/17 : Réparation URLs")
            code = cls._fix_broken_urls(code, stats, verbose)

            if verbose: print("\nPHASE 6/17 : Correction strings")
            code = cls._fix_spaced_strings(code, stats, verbose)

            if verbose: print("\nPHASE 7/17 : Restauration sauts de ligne")
            code = cls._restore_line_breaks(code, stats, verbose)

            if verbose: print("\nPHASE 8/17 : Correction deux-points orphelins")
            code = cls._fix_orphan_colons(code, stats, verbose)

            if verbose: print("\nPHASE 9/17 : Fusion signatures")
            code = cls._merge_split_signatures(code, stats, verbose)

            if verbose: print("\nPHASE 10/17 : Réparation méthodes")
            code = cls._fix_split_methods(code, stats, verbose)

            if verbose: print("\nPHASE 11/17 : Suppression pass orphelins")
            code = cls._remove_orphan_pass(code, stats, verbose)

            if verbose: print("\nPHASE 12/17 : Réparation structures incomplètes")
            code = cls._repair_incomplete_structures(code, stats, verbose, aggressive_mode)

            if verbose: print("\nPHASE 13/17 : Indentation intelligente")
            code = cls._intelligent_indentation(code, stats, verbose)

            if verbose: print("\nPHASE 14/17 : Nettoyage post-réparation")
            code = cls._post_repair_cleanup(code, stats, verbose)

            if verbose: print("\nPHASE 15/17 : Normalisation finale")
            code = cls._final_normalization(code, stats, verbose)

            if verbose: print("\nPHASE 16/17 : Indentation avancée")
            code = cls._advanced_indentation_fix(code, stats, verbose)

            # Validation
            stats.repaired_chars = len(code)
            stats.syntax_valid = cls._validate_syntax(code)
            if stats.syntax_valid:
                if verbose:
                    print(f"\n✅ CODE VALIDE après {attempt} tentative(s)")
                break
            elif attempt < max_attempts and not ultra_safe_mode:
                if verbose:
                    print(f"\n⚠️ Syntaxe invalide, escalade...")
                stats.corruption_level = min(10, stats.corruption_level + 2)
            else:
                if verbose:
                    print(f"\n⚠️ Code réparé mais syntaxe invalide après {attempt} tentatives")

        # ✅ RESTAURATION IMPORTS (FIX: Variable définie maintenant)
        if imports:
            code = cls._restore_imports(imports, code)
            if verbose:
                print(f"\n✅ {len(imports)} import(s) restaurés")

        # AFFICHAGE RÉSULTATS
        if verbose:
            print("\n" + "="*80)
            print("RÉSULTATS DE LA RÉPARATION")
            print("="*80)
            print(f"Taille finale: {stats.repaired_chars} chars")
            print(f"Réduction: {stats.original_chars - stats.repaired_chars} chars")
            reduction_percent = 100 * (stats.original_chars - stats.repaired_chars) / stats.original_chars if stats.original_chars > 0 else 0
            if reduction_percent > 50:
                print(f"⚠️ ALERTE: Réduction excessive ({reduction_percent:.1f}%)")
            elif reduction_percent > 30:
                print(f"⚠️ Réduction importante ({reduction_percent:.1f}%)")
            else:
                print(f"✅ Réduction raisonnable ({reduction_percent:.1f}%)")
            print(f"Syntaxe valide: {'✅ OUI' if stats.syntax_valid else '❌ NON'}")
            print("="*80 + "\n")

        return code, stats
    
    # ========================================================================
    # MÉTHODES AUXILIAIRES
    # ========================================================================
    
    @staticmethod
    def _preserve_imports(code: str) -> Tuple[List[str], str]:
        """✅ Extrait et préserve les imports"""
        if not code or len(code.strip()) == 0:
            return [], ""

        lines = code.split('\n')
        imports = []
        other_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                imports.append(stripped)
            elif stripped or other_lines:
                other_lines.append(line)

        return imports, '\n'.join(other_lines)
    
    @staticmethod
    def _restore_imports(imports: List[str], code: str) -> str:
        """Restaure les imports au début du code"""
        if not imports:
            return code

        code = code.lstrip()
        import_block = '\n'.join(imports)

        return f"{import_block}\n\n{code}"
    
    @staticmethod
    def _reconstruct_split_tokens(code: str, stats: RepairStats, verbose: bool) -> str:
        """VERSION 2.0 : Reconstruction ULTRA-ROBUSTE des tokens éclatés"""
        fixes = 0
        original = code

        operators = [
            (r'-\s*>\s*', ' -> '),
            (r'=\s*=\s*', ' == '),
            (r'!\s*=\s*', ' != '),
            (r'<\s*=\s*', ' <= '),
            (r'>\s*=\s*', ' >= '),
            (r'\*\s*\*\s*', '**'),
            (r'/\s*/\s*', '//'),
            (r'\+\s*=\s*', ' += '),
            (r'-\s*=\s*', ' -= '),
            (r'\*\s*=\s*', ' *= '),
            (r'/\s*=\s*', ' /= '),
        ]

        for pattern, replacement in operators:
            matches = len(re.findall(pattern, code))
            if matches > 0:
                code = re.sub(pattern, replacement, code)
                fixes += matches

        # Annotations de type éclatées
        pattern = r'(\w+)\s*:\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1: \2', code)
            fixes += matches

        pattern = r'(\w+)\s*:\s{2,}(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1: \2', code)
            fixes += matches

        pattern = r'->\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'-> \1', code)
            fixes += matches

        # Assignations éclatées
        pattern = r'(\w+)\s*=\s*\n+\s*(["\'\[\{\d\w])'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1 = \2', code)
            fixes += matches

        # Structures éclatées
        pattern = r'\{\s*\n+\s*(["\']?\w+["\']?)\s*:'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'{\1: ', code)
            fixes += matches

        pattern = r'\[\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'[\1', code)
            fixes += matches

        pattern = r'(\w+)\s*\(\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1(\2', code)
            fixes += matches

        # Accès membres éclatés
        pattern = r'(\w+)\s*\.\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1.\2', code)
            fixes += matches

        # Virgules éclatées
        pattern = r'(\w+)\s*,\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1, \2', code)
            fixes += matches

        # Compression espaces
        lines = []
        for line in code.split('\n'):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                content = ' '.join(line.split())
                lines.append(' ' * indent + content.lstrip())
            else:
                lines.append('')

        code = '\n'.join(lines)
        code = re.sub(r'\n{3,}', '\n\n', code)

        stats.operators_fixed += fixes
        if verbose and fixes > 0:
            reduction = len(original) - len(code)
            logger.info(f"   ⚡ {fixes} token(s) éclaté(s) reconstruits")
            logger.info(f"   📉 Réduction: {original.count(chr(10)) - code.count(chr(10))} lignes")

        return code
    
    @staticmethod
    def _fix_corrupted_indentation(code: str, stats: RepairStats, verbose: bool) -> str:
        """Corrige l'indentation corrompue (40+ espaces)"""
        lines = code.split('\n')
        fixed_lines = []
        fixes = 0

        for line in lines:
            if not line.strip():
                fixed_lines.append('')
                continue
            
            indent = len(line) - len(line.lstrip())

            if indent > 40:
                new_indent = ((indent - 40) // 4) * 4
                fixed_line = ' ' * new_indent + line.lstrip()
                fixed_lines.append(fixed_line)
                fixes += 1
            else:
                fixed_lines.append(line)

        stats.indentation_fixed += fixes
        if verbose and fixes > 0:
            logger.info(f"   ✅ {fixes} ligne(s) dé-indentée(s)")

        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _detect_corruption_level_v5(code: str) -> int:
        """Détecte le niveau de corruption 0-10"""
        if not code or len(code.strip()) < 10:
            return 0
        score = 0

        isolated_dots = len(re.findall(r'\.\s*\n\s*\w+\s*\(', code))
        score += min(isolated_dots * 2, 3)

        if re.search(r'pass\s+if\s+not', code):
            score += 3
        if re.search(r'pass\s+\w+\s*=', code):
            score += 3

        spaced_ops = len(re.findall(r'[=!<>]\s+[=!<>]', code))
        score += min(spaced_ops, 2)

        junk_count = sum(1 for pattern in DomExtractionFixer.JUNK_PATTERNS if re.search(pattern, code, re.IGNORECASE))
        score += min(junk_count, 2)

        split_keywords = len(re.findall(r'\b[a-z]\s+[a-z]\s+[a-z]\b', code))
        score += min(split_keywords, 2)

        for line in code.split('\n'):
            indent = len(line) - len(line.lstrip())
            if indent > 40:
                score += 1
                break
        return min(score, 10)
    
    @classmethod
    def _remove_junk_aggressive(cls, code: str, stats: RepairStats, verbose: bool) -> str:
        """Nettoyage junk avec protection anti-sur-suppression"""
        removed = 0
        original_length = len(code)

        if original_length == 0:
            return code

        python_score = cls._calculate_python_score(code)
        if python_score >= 60:
            safe_patterns = [r'```python\s*$', r'```\s*$', r'Copier\s*le\s*code\s*$']
            for pattern in safe_patterns:
                matches = len(re.findall(pattern, code, re.IGNORECASE | re.MULTILINE))
                if matches > 0:
                    code = re.sub(pattern, '', code, flags=re.IGNORECASE | re.MULTILINE)
                    removed += matches
            stats.junk_removed = removed
            return code

        for pattern in cls.JUNK_PATTERNS:
            matches = len(re.findall(pattern, code, re.IGNORECASE))
            if matches > 0:
                code = re.sub(pattern, '', code, flags=re.IGNORECASE)
                removed += matches

        stats.junk_removed = removed
        if verbose and removed > 0:
            logger.info(f"   🗑️ {removed} pattern(s) de junk supprimé(s)")
        return code

    @staticmethod
    def _fix_split_keywords(code: str, stats: RepairStats, verbose: bool) -> str:
        """Corrige les mots-clés Python éclatés"""
        fixes = 0
        keywords_map = {
            r'i\s+n\b': 'in',
            r'f\s+o\s+r\b': 'for',
            r'n\s+o\s+t\b': 'not',
            r'i\s+f\b': 'if',
            r'o\s+r\b': 'or',
            r'i\s+s\b': 'is',
            r'a\s+s\b': 'as',
            r'd\s+e\s+f\b': 'def',
        }
        for pattern, keyword in keywords_map.items():
            matches = len(re.findall(pattern, code))
            if matches > 0:
                code = re.sub(pattern, keyword, code)
                fixes += matches
        stats.keywords_fixed = fixes
        if verbose and fixes > 0:
            print(f"   ✅ {fixes} mot(s)-clé(s) éclaté(s) fusionné(s)")
        return code
    
    @staticmethod
    def _merge_scattered_lines(code: str, stats: RepairStats, verbose: bool) -> str:
        """Fusion intelligente des lignes éclatées"""
        lines = code.split('\n')
        merged_lines = []
        i = 0
        merges = 0

        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()
            if not stripped:
                merged_lines.append(line)
                i += 1
                continue
            
            try:
                token_stream = tokenize.tokenize(io.BytesIO((line + '\n').encode('utf-8')).readline)
                tokens = list(token_stream)
                if (tokens and tokens[-1].type in (tokenize.OP, tokenize.NAME, tokenize.STRING) and 
                    (line.endswith((':','=','>','-')) or re.search(r'\b(float|int|str|dict|list|bool|Optional)\b', line))):
                    if i + 1 < len(lines):
                        next_stripped = lines[i + 1].strip()
                        if (re.match(r'^[=:+\-*/(),\[\]{}>=\w]', next_stripped) or 
                            any(kw in next_stripped for kw in ['float', 'int', '140.0', '100', '1.0'])):
                            merged_lines.append(line + ' ' + lines[i + 1].lstrip())
                            merges += 1
                            i += 2
                            continue
            except tokenize.TokenError:
                if i + 1 < len(lines):
                    merged_lines.append(line + ' ' + lines[i + 1].lstrip())
                    merges += 1
                    i += 2
                    continue
                
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if re.match(r'^[>\-]', stripped) and '>' in next_stripped:
                    merged_lines.append(line.rstrip() + next_stripped)
                    merges += 1
                    i += 2
                    continue
                if re.match(r'^[>]', stripped) and '=' in next_stripped:
                    merged_lines.append(line.rstrip() + next_stripped)
                    merges += 1
                    i += 2
                    continue
                
            if i + 1 < len(lines) and (re.match(r'^[=!<>:,\.]', stripped) or 
                                       stripped in ['elif', 'else'] or len(stripped) < 6):
                merged_lines.append(line.rstrip() + ' ' + lines[i + 1].lstrip())
                merges += 1
                i += 2
                continue
            
            merged_lines.append(line)
            i += 1

        stats.lines_merged += merges
        if verbose and merges > 0:
            print(f"   🔗 {merges} fusions supplémentaires")
        return '\n'.join(merged_lines)
    
    # ========================================================================
    # MÉTHODES STANDARD (Phases 1-16)
    # ========================================================================
    
    @staticmethod
    def _fix_isolated_dots(code: str, stats: RepairStats, verbose: bool) -> str:
        """Correction points isolés"""
        fixes = 0
        pattern1 = r'(\w+)\s*\.\s*\n\s*(\w+)\s*\('
        matches1 = len(re.findall(pattern1, code))
        if matches1 > 0:
            code = re.sub(pattern1, r'\1.\2(', code)
            fixes += matches1
        
        pattern2 = r'(\w+)\s{2,}\.\s{2,}(\w+)'
        matches2 = len(re.findall(pattern2, code))
        if matches2 > 0:
            code = re.sub(pattern2, r'\1.\2', code)
            fixes += matches2
        
        if fixes > 0:
            stats.dots_fixed += fixes
            if verbose:
                print(f"   🔧 {fixes} point(s) isolé(s) fusionné(s)")
        
        return code
    
    @staticmethod
    def _fix_spaced_operators(code: str, stats: RepairStats, verbose: bool) -> str:
        """Corrige les espaces anormaux dans les opérateurs"""
        fixes = 0
        patterns = [
            (r'=\s+=', '=='),
            (r'!\s+=', '!='),
            (r'<\s+=', '<='),
            (r'>\s+=', '>='),
            (r'/\s+/', '//'),
            (r'\*\s+\*', '**'),
        ]
        
        for pattern, replacement in patterns:
            matches = len(re.findall(pattern, code))
            if matches > 0:
                code = re.sub(pattern, replacement, code)
                fixes += matches
        
        if fixes > 0:
            stats.operators_fixed += fixes
            if verbose:
                print(f"   🔧 {fixes} opérateur(s) corrigé(s)")
        
        return code
    
    @staticmethod
    def _fix_broken_urls(code: str, stats: RepairStats, verbose: bool) -> str:
        """Fusionne les URLs cassées"""
        fixes = 0
        pattern1 = r'https?\s*:\s*/\s*/\s*'
        matches1 = len(re.findall(pattern1, code))
        if matches1 > 0:
            code = re.sub(pattern1, lambda m: m.group(0).replace(' ', ''), code)
            fixes += matches1
        
        if fixes > 0:
            stats.urls_fixed += fixes
            if verbose:
                print(f"   🔧 {fixes} URL(s) réparée(s)")
        
        return code
    
    @staticmethod
    def _fix_spaced_strings(code: str, stats: RepairStats, verbose: bool) -> str:
        """Corrige les espaces anormaux dans les chaînes"""
        fixes = 0
        patterns = [
            (r'"\s+([^"]+)"', r'"\1"'),
            (r"'\s+([^']+)'", r"'\1'"),
            (r'f"\s+', 'f"'),
        ]
        
        for pattern, replacement in patterns:
            matches = len(re.findall(pattern, code))
            if matches > 0:
                code = re.sub(pattern, replacement, code)
                fixes += matches
        
        if fixes > 0:
            stats.strings_fixed += fixes
            if verbose:
                print(f"   🔧 {fixes} chaîne(s) corrigée(s)")
        
        return code
    
    @staticmethod
    def _restore_line_breaks(code: str, stats: RepairStats, verbose: bool) -> str:
        """Restaure les sauts de ligne manquants"""
        for keyword in DomExtractionFixer.BLOCK_KEYWORDS:
            pattern = rf'\b{keyword}\b\s+([^:]+):\s*([^\n]+)'
            
            def replacer(match):
                header = match.group(1)
                inline_code = match.group(2).strip()
                if inline_code and not inline_code.startswith('#'):
                    return f"{keyword} {header}:\n    {inline_code}"
                return match.group(0)
            
            code = re.sub(pattern, replacer, code)
        
        code = code.replace(';', '\n')
        
        if verbose:
            print(f"   ✅ Sauts de ligne restaurés")
        
        return code
    
    @staticmethod
    def _fix_orphan_colons(code: str, stats: RepairStats, verbose: bool) -> str:
        """Répare les deux-points orphelins"""
        lines = code.split('\n')
        fixed_lines = []
        fixes = 0
        
        for line in lines:
            stripped = line.strip()
            
            if stripped == ':':
                if fixed_lines and not fixed_lines[-1].rstrip().endswith(':'):
                    fixed_lines[-1] = fixed_lines[-1].rstrip() + ':'
                    fixes += 1
                    continue
            
            fixed_lines.append(line)
        
        stats.colons_fixed = fixes
        
        if verbose and fixes > 0:
            print(f"   🔧 {fixes} deux-points orphelin(s) fixé(s)")
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _merge_split_signatures(code: str, stats: RepairStats, verbose: bool) -> str:
        """Fusionne les signatures éclatées"""
        lines = code.split('\n')
        fixed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if re.match(r'^\s*(def|class|async\s+def)\s+\w+', stripped):
                signature_parts = [stripped]
                j = i + 1
                
                while j < len(lines):
                    next_line = lines[j].strip()
                    
                    if ')' in next_line and ':' in next_line:
                        signature_parts.append(next_line)
                        break
                    
                    if next_line and not next_line.startswith('#'):
                        signature_parts.append(next_line)
                    
                    j += 1
                
                if len(signature_parts) > 1:
                    merged = ' '.join(signature_parts)
                    merged = re.sub(r'\s+', ' ', merged)
                    merged = re.sub(r'\s*,\s*', ', ', merged)
                    merged = re.sub(r'\s*\(\s*', '(', merged)
                    merged = re.sub(r'\s*\)\s*', ')', merged)
                    
                    if not merged.endswith(':'):
                        merged += ':'
                    
                    fixed_lines.append(merged)
                    i = j + 1
                else:
                    fixed_lines.append(line)
                    i += 1
                continue
            
            fixed_lines.append(line)
            i += 1
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_split_methods(code: str, stats: RepairStats, verbose: bool) -> str:
        """Répare les appels de méthodes éclatés"""
        lines = code.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('.') and fixed_lines:
                fixed_lines[-1] = fixed_lines[-1].rstrip() + stripped
                stats.methods_merged += 1
                continue
            
            if stripped.startswith('(') and fixed_lines:
                fixed_lines[-1] = fixed_lines[-1].rstrip() + stripped
                stats.methods_merged += 1
                continue
            
            fixed_lines.append(line)
        
        if verbose and stats.methods_merged > 0:
            print(f"   🔧 {stats.methods_merged} méthode(s) fusionnée(s)")
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _remove_orphan_pass(code: str, stats: RepairStats, verbose: bool) -> str:
        """Supprime les 'pass' orphelins"""
        original = code
        
        code = re.sub(r'\bpass\s+(?=f["\'])', '', code)
        code = re.sub(r'\bpass\s+(?=[a-zA-Z_])', '', code)
        code = re.sub(r'\bpass\s+(?=[\[\{])', '', code)
        
        removed = original.count('pass ') - code.count('pass ')
        
        if removed > 0:
            stats.pass_removed += removed
            if verbose:
                print(f"   🔧 {removed} 'pass' orphelin(s) supprimé(s)")
        
        return code
    
    @staticmethod
    def _repair_incomplete_structures(code: str, stats: RepairStats, verbose: bool, aggressive: bool) -> str:
        """Répare les structures incomplètes"""
        lines = code.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.endswith(':'):
                next_line = lines[i+1] if i+1 < len(lines) else ""
                next_indent = len(next_line) - len(next_line.lstrip())
                current_indent = len(line) - len(line.lstrip())
                
                if not next_line.strip() or next_indent <= current_indent:
                    fixed_lines.append(line)
                    if aggressive:
                        fixed_lines.append(' ' * (current_indent + 4) + 'pass')
                    continue
            
            fixed_lines.append(line)
        
        code = '\n'.join(fixed_lines)
        
        if aggressive:
            open_parens = code.count('(') - code.count(')')
            if open_parens > 0:
                code += ')' * open_parens
                stats.parentheses_closed += open_parens
        
        if verbose and stats.parentheses_closed > 0:
            print(f"   🔧 {stats.parentheses_closed} parenthèse(s) fermée(s)")
        
        return code
    
    @staticmethod
    def _intelligent_indentation(code: str, stats: RepairStats, verbose: bool) -> str:
        """Indentation intelligente"""
        lines = code.split('\n')
        fixed_lines = []
        indent_level = 0
        indent_size = 4
        fixed_count = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                fixed_lines.append(line)
                continue
            
            original_indent = len(line) - len(line.lstrip())
            expected_indent = indent_level * indent_size
            
            if any(stripped.startswith(kw) for kw in ['def ', 'class ', 'if ', 'for ', 'while ', 'try:']):
                indent_level += 1
            elif any(stripped.startswith(kw) for kw in ['else:', 'elif ', 'except', 'finally:']):
                pass
            
            if abs(original_indent - expected_indent) > 2:
                fixed_count += 1
                fixed_line = ' ' * expected_indent + stripped
            else:
                fixed_line = line
            
            fixed_lines.append(fixed_line)
            
            if stripped.startswith('return '):
                indent_level = max(0, indent_level - 1)
        
        stats.indentation_fixed += fixed_count
        if verbose and fixed_count > 0:
            print(f"   📏 {fixed_count} indentations fixées")
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _post_repair_cleanup(code: str, stats: RepairStats, verbose: bool) -> str:
        """Nettoyage post-réparation"""
        code = re.sub(r'\n{4,}', '\n\n', code)

        lines = []
        empty_line_count = 0

        for line in code.split('\n'):
            stripped = line.strip()

            if not stripped:
                empty_line_count += 1
                if empty_line_count <= 1:
                    lines.append('')
            else:
                empty_line_count = 0
                indent = len(line) - len(line.lstrip())
                content = ' '.join(line.split())

                if indent > 0:
                    lines.append(' ' * indent + content.lstrip())
                else:
                    lines.append(content)

        code = '\n'.join(lines)
        code = code.strip()
        code = code.encode('ascii', 'ignore').decode('ascii')
        code = code.strip() + '\n'

        if verbose:
            print(f"   ✅ Nettoyage effectué")

        return code
    
    @staticmethod
    def _final_normalization(code: str, stats: RepairStats, verbose: bool) -> str:
        """Normalisation finale"""
        code = re.sub(r'\n{3,}', '\n\n', code)
        code = re.sub(r'\s+,', ',', code)
        code = re.sub(r',([^\s\n])', r', \1', code)
        
        lines = []
        for line in code.split('\n'):
            if not line.strip().startswith(('#', '"', "'")):
                line = re.sub(r'(\w)\s*=\s*([^=])', r'\1 = \2', line)
                line = re.sub(r'(\w)\s*\+=\s*', r'\1 += ', line)
            lines.append(line)
        code = '\n'.join(lines)
        
        code = re.sub(r'(\w)\s+\(', r'\1(', code)
        code = re.sub(r',(\w)', r', \1', code)
        
        lines = [line.rstrip() for line in code.split('\n')]
        code = '\n'.join(lines)
        code = code.strip() + '\n'
        
        if verbose:
            print(f"   ✅ Normalisation effectuée")
        
        return code
    
    @staticmethod
    def _advanced_indentation_fix(code: str, stats: RepairStats, verbose: bool) -> str:
        """Indentation avancée avec dedent"""
        try:
            code = textwrap.dedent(code)
        except:
            pass
        
        lines = code.split('\n')
        fixed_lines = []
        indent_level = 0
        indent_size = 4
        fixed_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                fixed_lines.append(line)
                continue
            
            original_indent = len(line) - len(line.lstrip())
            expected_indent = indent_level * indent_size

            if any(stripped.startswith(kw) for kw in ['def ', 'class ', 'if ', 'for ', 'while ', 'try:']):
                indent_level += 1
            elif any(stripped.startswith(kw) for kw in ['else:', 'elif ', 'except', 'finally:']):
                pass
            elif stripped in ['return', 'pass', 'raise'] or stripped.endswith(':'):
                if i + 1 < len(lines) and lines[i+1].strip().startswith(' '):
                    indent_level += 1

            if original_indent != expected_indent:
                fixed_count += 1
                fixed_line = ' ' * expected_indent + stripped
            else:
                fixed_line = line

            fixed_lines.append(fixed_line)

            if stripped in ['return', 'break', 'continue']:
                indent_level = max(0, indent_level - 1)

        stats.indentation_fixed += fixed_count
        if verbose and fixed_count > 0:
            print(f"   🔧 {fixed_count} ligne(s) ré-indentée(s)")

        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _validate_syntax(code: str) -> bool:
        """Valide la syntaxe Python avec AST"""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def _calculate_python_score(code: str) -> int:
        """Calcule un score Python (0-100) pour déterminer la confiance"""
        if not code:
            return 0

        score = 0

        definitions = len(re.findall(r'^\s*(def|class)\s+\w+', code, re.MULTILINE))
        score += min(definitions * 5, 30)

        imports = len(re.findall(r'^\s*(import|from)\s+', code, re.MULTILINE))
        score += min(imports * 3, 15)

        control_structures = len(re.findall(r'\b(if|elif|else|for|while|try|except|finally|with)\b', code))
        score += min(control_structures * 2, 20)

        self_refs = code.count('self.')
        score += min(self_refs, 10)

        docstrings = len(re.findall(r'""".*?"""', code, re.DOTALL))
        score += min(docstrings * 5, 10)

        try:
            ast.parse(code)
            score += 15
        except:
            pass
        
        return min(score, 100)
    
    @staticmethod
    def _calculate_quality_score(code: str, syntax_valid: bool, repair_stats=None) -> float:
        """Calcule un score qualité 0-100 pour le code"""
        score = 0.0

        if syntax_valid:
            score += 50.0

        python_keywords = ['def ', 'class ', 'import ', 'return ', 'if ', 'for ', 'while ']
        keyword_count = sum(1 for kw in python_keywords if kw in code)
        score += min(keyword_count * 4, 20.0)

        if 20 <= len(code) <= 10000:
            score += 10.0
        elif len(code) > 10000:
            score += 5.0

        lines = code.split('\n')
        indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
        if indents:
            indent_valid = all(indent % 4 == 0 for indent in indents)
            if indent_valid:
                score += 10.0

        junk_patterns = ['Copier', 'Regenerate', '===', 'NOTE:', 'Rapide']
        has_junk = any(pattern in code for pattern in junk_patterns)
        if not has_junk:
            score += 10.0

        return min(score, 100.0)
    
    @staticmethod
    def repair_snippets_avec_validation(
        snippets: List[Dict], 
        verbose: bool = False,
        keep_invalid: bool = True
    ) -> List[Dict]:
        """Répare et valide une liste de snippets"""

        if not snippets or len(snippets) == 0:
            logger.warning("⚠️ Aucun snippet à réparer")
            return []

        print(f"\n{'='*80}")
        print(f"🔧 RÉPARATION DOM v6.0 ENHANCED + VALIDATION - {len(snippets)} SNIPPET(S)")
        print(f"🛡️ Mode: {'PERMISSIF (garde invalides)' if keep_invalid else 'STRICT (rejette invalides)'}")
        print(f"{'='*80}")

        repaired = []
        stats_global = {'success': 0, 'partial': 0, 'failed': 0, 'kept_invalid': 0}

        # PHASE 1: RÉPARATION
        for idx, snippet in enumerate(snippets, 1):
            try:
                original_code = snippet.get('code', '')

                if not original_code or len(original_code.strip()) < 10:
                    print(f"\n📦 Snippet {idx}: ⚠️ Code trop court, ignoré")
                    stats_global['failed'] += 1
                    continue
                
                print(f"\n📦 Snippet {idx}/{len(snippets)}: {snippet.get('file', 'N/A')}")
                print(f"   📄 Code original: {len(original_code)} chars")

                # Réparation avec Enhanced v6
                repaired_code = DomExtractionFixer.fix_extracted_code(
                    original_code, 
                    verbose=verbose
                )

                if not repaired_code or len(repaired_code.strip()) < 10:
                    logger.warning(f"   ⚠️ Réparation a produit un code vide")

                    if keep_invalid:
                        snippet['code'] = original_code
                        snippet['repair_status'] = 'FAILED'
                        snippet['quality_score'] = 10.0
                        snippet['syntax_valid'] = False
                        repaired.append(snippet)
                        stats_global['kept_invalid'] += 1
                        logger.info(f"   🛡️ Snippet conservé (original) malgré échec")
                    else:
                        stats_global['failed'] += 1

                    continue
                
                snippet['code'] = repaired_code
                repaired.append(snippet)

            except Exception as e:
                print(f"   ❌ Erreur: {e}")

                if keep_invalid and original_code:
                    snippet['code'] = original_code
                    snippet['repair_status'] = 'ERROR'
                    snippet['quality_score'] = 5.0
                    snippet['syntax_valid'] = False
                    repaired.append(snippet)
                    stats_global['kept_invalid'] += 1
                    logger.info(f"   🛡️ Snippet conservé (original) malgré exception")
                else:
                    stats_global['failed'] += 1

        # PHASE 2: VALIDATION
        if repaired and len(repaired) > 0:
            print(f"\n{'='*80}")
            print(f"🔍 VALIDATION FINALE DE {len(repaired)} SNIPPET(S)")
            print(f"{'='*80}")

            for idx, snippet in enumerate(repaired, 1):
                code = snippet.get('code', '')

                syntax_valid = DomExtractionFixer._validate_syntax(code)

                quality_score = DomExtractionFixer._calculate_quality_score(
                    code, 
                    syntax_valid,
                    snippet.get('repair_stats')
                )

                snippet['syntax_valid'] = syntax_valid
                snippet['quality_score'] = quality_score
                snippet['repair_status'] = snippet.get('repair_status', 'SUCCESS' if syntax_valid else 'INVALID')

                if syntax_valid:
                    stats_global['success'] += 1
                    logger.info(f"   ✅ Snippet {idx}: VALIDE (score: {quality_score:.1f})")
                else:
                    if keep_invalid:
                        stats_global['kept_invalid'] += 1
                        logger.warning(f"   ⚠️ Snippet {idx}: INVALIDE mais CONSERVÉ (score: {quality_score:.1f})")
                    else:
                        stats_global['failed'] += 1
                        logger.error(f"   ❌ Snippet {idx}: REJETÉ (invalide)")

            if keep_invalid:
                validated = repaired
            else:
                validated = [s for s in repaired if s.get('syntax_valid', False)]

            print(f"\n{'='*80}")
            print(f"📊 STATISTIQUES FINALES:")
            print(f"   ✅ Succès: {stats_global['success']}")
            print(f"   ⚠️ Partiels: {stats_global['partial']}")
            print(f"   🛡️ Conservés invalides: {stats_global['kept_invalid']}")
            print(f"   ❌ Rejetés: {stats_global['failed']}")

            total_processed = stats_global['success'] + stats_global['partial'] + stats_global['kept_invalid'] + stats_global['failed']
            if total_processed > 0:
                success_rate = 100 * stats_global['success'] / total_processed
                recovery_rate = 100 * (stats_global['success'] + stats_global['kept_invalid']) / total_processed
                print(f"   📈 Taux succès: {success_rate:.1f}%")
                print(f"   🔄 Taux récupération: {recovery_rate:.1f}%")

            print(f"{'='*80}\n")

            return validated
        else:
            logger.warning("⚠️ Aucun snippet réparé à valider")
            return []


# ============================================================================
# FONCTION HELPER POUR UTILISATION SIMPLE
# ============================================================================

def repair_code(corrupted_code: str, verbose: bool = True) -> str:
    """
    Point d'entrée simplifié pour réparer du code corrompu
    
    Args:
        corrupted_code: Code Python corrompu par DOM
        verbose: Afficher les détails de réparation
        
    Returns:
        Code réparé (syntaxiquement valide si possible)
    """
    return DomExtractionFixer.fix_extracted_code(corrupted_code, verbose=verbose)


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    # Code cassé exemple
    broken_code = """import Optional
import math
from typing
def calculate_asteroid_impact_probability(asteroid_diameter_km: float, distance_au: float, orbital_uncertainty_km: float, time_horizon_years: float = 100, earth_cross_section_km2: Optional
    [float]
     = 
    None)
 - > float
: 
    \"\"\"
    Calcule la probabilité qu'un astéroïde heurte la Terre.Args: asteroid_diameter_km: Diamètre de l'astéroïde en kilomètres
    distance_au: Distance en unités astronomiques (1 AU = 150M km)
    orbital_uncertainty_km: Incertitude orbitale en kilomètres
    time_horizon_years: Horizon temporel en années
    earth_cross_section_km2: Section efficace de la Terre (optionnel)
    Returns: Probabilité d'impact (entre 0 et 1)
    \"\"\"
    EARTH_RADIUS_KM = 6371.0
    AU_TO_KM = 149597870.7
    if earth_cross_section_km2
    is
    None: effective_radius = EARTH_RADIUS_KM
     + 
    asteroid_diameter_km
     / 
    2
    earth_cross_section_km2 = math.pi
     * 
    effective_radius
    **2
    distance_km = distance_au
     * 
    AU_TO_KM
    orbit_area_km2 = math.pi
     * 
    distance_km
    **2
    geometric_probability = earth_cross_section_km2
     / 
    orbit_area_km2
    uncertainty_factor = min
    (1.0, orbital_uncertainty_km
         / 
        (2
             * 
            EARTH_RADIUS_KM))
        adjusted_probability = geometric_probability
         * 
        uncertainty_factor
         * 
        time_horizon_years
        return min
        (adjusted_probability, 1.0)
"""
    
    # Réparation
    print("🚀 DÉMARRAGE DE LA RÉPARATION...\n")
    fixed_code = repair_code(broken_code, verbose=True)
    
    print("\n" + "="*80)
    print("✅ CODE CORRIGÉ:")
    print("="*80)
    print(fixed_code)
    
    # Validation finale
    print("\n" + "="*80)
    print("🔍 VALIDATION FINALE")
    print("="*80)
    try:
        ast.parse(fixed_code)
        print("✅ CODE SYNTAXIQUEMENT VALIDE!")
    except SyntaxError as e:
        print(f"❌ Erreur de syntaxe: {e}")