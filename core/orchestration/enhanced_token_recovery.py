"""
Enhanced Token Recovery System - Phase 0 Renforcée
Correction PRIORITAIRE des tokens éclatés AVANT toute autre réparation
"""

import re
from dataclasses import dataclass
from typing import Tuple


@dataclass
class TokenRecoveryStats:
    """Statistiques de reconstruction des tokens"""
    operators_fixed: int = 0
    arrows_fixed: int = 0
    comparisons_fixed: int = 0
    assignments_fixed: int = 0
    indents_normalized: int = 0
    line_breaks_restored: int = 0


class EnhancedTokenRecovery:
    """Système de reconstruction avancé pour tokens Python éclatés"""
    
    @staticmethod
    def reconstruct_all_tokens(code: str, verbose: bool = False) -> Tuple[str, TokenRecoveryStats]:
        stats = TokenRecoveryStats()
        
        if not code or len(code.strip()) < 10:
            return code, stats
        
        if verbose:
            print("\n" + "="*80)
            print("⚡ RECONSTRUCTION TOKENS - PHASE 0 PRIORITAIRE")
            print("="*80)
            print(f"📊 Taille originale: {len(code)} chars\n")
        
        if verbose:
            print("🔧 Étape 1/7 : Opérateurs de comparaison")
        
        # >= et <=
        pattern = r'>\s*=\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ' >= ', code)
            stats.comparisons_fixed += matches
            if verbose:
                print(f"   ✅ {matches} occurrence(s) de '>=' corrigées")
        
        pattern = r'<\s*=\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ' <= ', code)
            stats.comparisons_fixed += matches
            if verbose:
                print(f"   ✅ {matches} occurrence(s) de '<=' corrigées")
        
        # == et !=
        pattern = r'=\s*=\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ' == ', code)
            stats.comparisons_fixed += matches
            if verbose:
                print(f"   ✅ {matches} occurrence(s) de '==' corrigées")
        
        pattern = r'!\s*=\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ' != ', code)
            stats.comparisons_fixed += matches
            if verbose:
                print(f"   ✅ {matches} occurrence(s) de '!=' corrigées")
        
        if verbose:
            print("\n🔧 Étape 2/7 : Flèches de retour")
        
        # Cas 1: - > avec espaces
        pattern = r'-\s*>\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ' -> ', code)
            stats.arrows_fixed += matches
            if verbose:
                print(f"   ✅ {matches} flèche(s) '->' corrigée(s)")
        
        # Cas 2: ) \n -> ou ) \n - >
        pattern = r'\)\s*\n+\s*-\s*>\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, ') -> ', code)
            stats.arrows_fixed += matches
            if verbose:
                print(f"   ✅ {matches} flèche(s) après ')' corrigée(s)")
        
        if verbose:
            print("\n🔧 Étape 3/7 : Opérateurs composés")
        
        compound_ops = [
            (r'\*\s*\*\s*', '**', 'Exposant'),
            (r'/\s*/\s*', '//', 'Division entière'),
            (r'\+\s*=\s*', ' += ', 'Addition assignée'),
            (r'-\s*=\s*', ' -= ', 'Soustraction assignée'),
            (r'\*\s*=\s*', ' *= ', 'Multiplication assignée'),
        ]
        
        for pattern, replacement, name in compound_ops:
            matches = len(re.findall(pattern, code))
            if matches > 0:
                code = re.sub(pattern, replacement, code)
                stats.operators_fixed += matches
                if verbose:
                    print(f"   ✅ {matches} occurrence(s) de '{name}' corrigée(s)")
        
        if verbose:
            print("\n🔧 Étape 4/7 : Assignations")
        
        # Cas 1: variable \n = valeur
        pattern = r'(\w+)\s*\n+\s*=\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1 = ', code)
            stats.assignments_fixed += matches
            if verbose:
                print(f"   ✅ {matches} assignation(s) avec saut de ligne corrigée(s)")
        
        # Cas 2: Espaces excessifs autour de =
        pattern = r'(\w+)\s{2,}=\s{2,}'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1 = ', code)
            stats.assignments_fixed += matches
            if verbose:
                print(f"   ✅ {matches} assignation(s) avec espaces corrigée(s)")
        
        if verbose:
            print("\n🔧 Étape 5/7 : Deux-points")
        
        # Cas 1: ) \n :
        pattern = r'\)\s*\n+\s*:\s*'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, '):', code)
            if verbose:
                print(f"   ✅ {matches} deux-points après ')' corrigé(s)")
        
        # Cas 2: : \n type (annotations)
        pattern = r':\s*\n+\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r': \1', code)
            if verbose:
                print(f"   ✅ {matches} annotation(s) de type corrigée(s)")
        
        if verbose:
            print("\n🔧 Étape 6/7 : Parenthèses/crochets")
        
        # Fonction \n (
        pattern = r'(\w+)\s*\n+\s*\('
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1(', code)
            if verbose:
                print(f"   ✅ {matches} appel(s) de fonction corrigé(s)")
        
        # Liste \n [
        pattern = r'(\w+)\s*\n+\s*\['
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1[', code)
            if verbose:
                print(f"   ✅ {matches} accès liste corrigé(s)")
        
        if verbose:
            print("\n🔧 Étape 7/7 : Points d'accès")
        
        # obj \n . method
        pattern = r'(\w+)\s*\n+\s*\.\s*(\w+)'
        matches = len(re.findall(pattern, code))
        if matches > 0:
            code = re.sub(pattern, r'\1.\2', code)
            if verbose:
                print(f"   ✅ {matches} accès méthode corrigé(s)")
        
        if verbose:
            print("\n🔧 Bonus : Normalisation indentation")
        
        lines = code.split('\n')
        normalized_lines = []
        
        for line in lines:
            if not line.strip():
                normalized_lines.append('')
                continue
            
            # Détecter indentation excessive (> 40 espaces)
            indent = len(line) - len(line.lstrip())
            
            if indent > 40:
                # Réduire à un niveau raisonnable
                max_indent = 16  # 4 niveaux max
                new_indent = min(indent, max_indent)
                normalized_lines.append(' ' * new_indent + line.lstrip())
                stats.indents_normalized += 1
            else:
                normalized_lines.append(line)
        
        code = '\n'.join(normalized_lines)
        
        if verbose:
            if stats.indents_normalized > 0:
                print(f"   ✅ {stats.indents_normalized} ligne(s) ré-indentée(s)")
        
        if verbose:
            print("\n" + "="*80)
            print("📊 RÉSULTATS RECONSTRUCTION TOKENS")
            print("="*80)
            print(f"✅ Comparaisons: {stats.comparisons_fixed}")
            print(f"✅ Flèches: {stats.arrows_fixed}")
            print(f"✅ Opérateurs: {stats.operators_fixed}")
            print(f"✅ Assignations: {stats.assignments_fixed}")
            print(f"✅ Indentations: {stats.indents_normalized}")
            total = (stats.comparisons_fixed + stats.arrows_fixed + 
                    stats.operators_fixed + stats.assignments_fixed + 
                    stats.indents_normalized)
            print(f"📈 TOTAL: {total} corrections")
            print(f"📏 Taille finale: {len(code)} chars")
            print("="*80 + "\n")
        
        return code, stats

def integrate_enhanced_recovery_into_existing_system(code: str, verbose: bool = False) -> str:
    """
    🔌 Fonction d'intégration dans advanced_code_recovery.py
    
    À appeler en PHASE 0.1 (avant toute autre réparation)
    """
    enhanced_recovery = EnhancedTokenRecovery()
    repaired_code, stats = enhanced_recovery.reconstruct_all_tokens(code, verbose)
    
    return repaired_code