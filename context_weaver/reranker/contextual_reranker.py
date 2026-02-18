#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Contextual Reranker - Boost basé sur les paramètres extraits

✅ Boost x10 pour match exact sur forme juridique
✅ Boost x8 pour match exact sur régime fiscal
✅ Boost x5 pour match exact sur domaine d'activité
✅ Penalty x0.1 pour incompatibilités (BNC + IS, etc.)
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from context_weaver.taxonomy.taxonomy_models import TaxonCandidate

logger = logging.getLogger(__name__)


@dataclass
class ContextualBoostConfig:
    """Configuration des boosts contextuels"""
    
    # Boosts par catégorie
    forme_juridique_boost: float = 10.0
    regime_fiscal_boost: float = 8.0
    domaine_activite_boost: float = 5.0
    plan_comptable_boost: float = 3.0
    
    # Penalties
    incompatibility_penalty: float = 0.1
    partial_match_penalty: float = 0.5
    
    # Seuils
    min_score_threshold: float = 0.01
    exact_match_threshold: float = 0.9  # Similarité string pour "exact match"


class ContextualReranker:
    """
    Reranker qui ajuste les scores basés sur les paramètres extraits
    
    Workflow:
    1. Prend les candidats RRF+Dgraph
    2. Extrait les paramètres de la query (formes juridiques, régimes, etc.)
    3. Boost les candidats qui matchent exactement
    4. Penalty les candidats incompatibles
    5. Re-trie par final_score
    """
    
    def __init__(self, config: ContextualBoostConfig = None):
        self.config = config or ContextualBoostConfig()
        
        # Dictionnaire d'incompatibilités
        self._build_incompatibility_rules()
        
        logger.info("✅ ContextualReranker initialisé")
        logger.info(f"   • Forme juridique boost: {self.config.forme_juridique_boost}x")
        logger.info(f"   • Régime fiscal boost: {self.config.regime_fiscal_boost}x")
        logger.info(f"   • Domaine activité boost: {self.config.domaine_activite_boost}x")
        logger.info(f"   • Incompatibility penalty: {self.config.incompatibility_penalty}x")
    
    
    def _build_incompatibility_rules(self):
        """
        Construit les règles d'incompatibilité
        
        Format:
        {
            'concept1': ['incompatible_concept_1', 'incompatible_concept_2'],
            ...
        }
        """
        self.incompatibilities = {
            # BNC incompatible avec IS
            'Bénéfices Non Commerciaux': ['Impôt sur les sociétés', 'IS', 'Impôts sur les sociétés'],
            'BNC': ['Impôt sur les sociétés', 'IS', 'Impôts sur les sociétés'],
            
            # BIC incompatible avec BNC
            'Bénéfices Industriels et Commerciaux': ['Bénéfices Non Commerciaux', 'BNC'],
            'BIC': ['Bénéfices Non Commerciaux', 'BNC'],
            
            # Certaines formes juridiques incompatibles avec certains régimes
            'Association': ['Impôt sur les sociétés', 'IS', 'BIC', 'BNC'],
            
            # Activités agricoles vs commerciales
            'Bénéfices Agricoles': ['Bénéfices Industriels et Commerciaux', 'BIC'],
            'BA': ['BIC', 'BNC'],
            
            # Profession libérale incompatible avec commerce
            'Profession Libérale': ['Artisan / Commerçant', 'Commerce', 'BIC'],
        }
    
    
    def rerank(
        self,
        candidates: List[TaxonCandidate],
        extracted_params: Dict[str, List[str]],
        context: Dict[str, Any] = None
    ) -> List[TaxonCandidate]:
        """
        Re-score les candidats basés sur les paramètres extraits
        
        Args:
            candidates: Liste des candidats RRF+Dgraph
            extracted_params: Paramètres extraits de la query
                Format: {
                    'formes_juridiques': ['SARL'],
                    'regimes_fiscaux': ['Impôt sur les sociétés'],
                    'domaines_activite': ['Prestataire de services'],
                    ...
                }
            context: Contexte additionnel (optionnel)
        
        Returns:
            Liste des candidats re-triés
        """
        logger.info("\n" + "=" * 80)
        logger.info("🎯 CONTEXTUAL RERANKING")
        logger.info("=" * 80)
        logger.info(f"📊 Input: {len(candidates)} candidats")
        logger.info(f"🔍 Extracted params: {list(extracted_params.keys())}")
        
        if not extracted_params:
            logger.warning("⚠️ No extracted params, returning original ranking")
            return candidates
        
        # === PHASE 1: Calculer les boosts ===
        
        for candidate in candidates:
            # Initialiser le boost à 1.0
            total_boost = 1.0
            boost_reasons = []
            
            # Check forme juridique
            if 'formes_juridiques' in extracted_params:
                boost, reason = self._check_forme_juridique(candidate, extracted_params['formes_juridiques'])
                total_boost *= boost
                if reason:
                    boost_reasons.append(reason)
            
            # Check régime fiscal
            if 'regimes_fiscaux' in extracted_params:
                boost, reason = self._check_regime_fiscal(candidate, extracted_params['regimes_fiscaux'])
                total_boost *= boost
                if reason:
                    boost_reasons.append(reason)
            
            # Check domaine d'activité
            if 'domaines_activite' in extracted_params:
                boost, reason = self._check_domaine_activite(candidate, extracted_params['domaines_activite'])
                total_boost *= boost
                if reason:
                    boost_reasons.append(reason)
            
            # Check plan comptable
            if 'plans' in extracted_params:
                boost, reason = self._check_plan_comptable(candidate, extracted_params['plans'])
                total_boost *= boost
                if reason:
                    boost_reasons.append(reason)
            
            # === PHASE 2: Check incompatibilités ===
            
            is_incompatible, incomp_reason = self._check_incompatibility(candidate, extracted_params)
            
            if is_incompatible:
                total_boost *= self.config.incompatibility_penalty
                boost_reasons.append(f"❌ {incomp_reason}")
            
            # === PHASE 3: Appliquer le boost ===
            
            original_score = candidate.final_score
            candidate.final_score *= total_boost
            
            # Stocker les metadata de boost
            candidate.metadata['boost_factor'] = total_boost
            candidate.metadata['boost_reasons'] = boost_reasons
            candidate.metadata['original_score'] = original_score
        
        # === PHASE 4: Re-trier ===
        
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        
        # === PHASE 5: Logging ===
        
        self._log_reranking_changes(candidates)
        
        logger.info("=" * 80 + "\n")
        
        return candidates
    
    
    def _check_forme_juridique(
        self, 
        candidate: TaxonCandidate, 
        formes: List[str]
    ) -> tuple[float, str]:
        """
        Check si le candidat match une forme juridique
        
        Returns:
            (boost_factor, reason)
        """
        for forme in formes:
            # Match exact dans le nom
            if self._is_exact_match(forme, candidate.name):
                return (self.config.forme_juridique_boost, f"✅ Forme juridique: {forme}")
            
            # Match dans le breadcrumb
            if candidate.breadcrumb and self._is_in_breadcrumb(forme, candidate.breadcrumb):
                return (self.config.forme_juridique_boost * 0.8, f"✅ Forme dans path: {forme}")
        
        return (1.0, "")
    
    
    def _check_regime_fiscal(
        self, 
        candidate: TaxonCandidate, 
        regimes: List[str]
    ) -> tuple[float, str]:
        """Check si le candidat match un régime fiscal"""
        
        for regime in regimes:
            # Normaliser les variantes (IS = Impôt sur les sociétés)
            normalized_regime = self._normalize_regime(regime)
            normalized_name = self._normalize_regime(candidate.name)
            normalized_breadcrumb = self._normalize_regime(candidate.breadcrumb)
            
            # Match exact dans le nom
            if normalized_regime in normalized_name:
                return (self.config.regime_fiscal_boost, f"✅ Régime fiscal: {regime}")
            
            # Match dans le breadcrumb
            if normalized_regime in normalized_breadcrumb:
                return (self.config.regime_fiscal_boost * 0.8, f"✅ Régime dans path: {regime}")
        
        return (1.0, "")
    
    
    def _check_domaine_activite(
        self, 
        candidate: TaxonCandidate, 
        domaines: List[str]
    ) -> tuple[float, str]:
        """Check si le candidat match un domaine d'activité"""
        
        for domaine in domaines:
            # Match exact
            if self._is_exact_match(domaine, candidate.name):
                return (self.config.domaine_activite_boost, f"✅ Domaine: {domaine}")
            
            # Match partiel (ex: "Prestataire de services" in "Prestataire de services – plan standard")
            if domaine.lower() in candidate.name.lower():
                return (self.config.domaine_activite_boost * 0.9, f"✅ Domaine partiel: {domaine}")
            
            # Match dans breadcrumb
            if candidate.breadcrumb and domaine.lower() in candidate.breadcrumb.lower():
                return (self.config.domaine_activite_boost * 0.7, f"✅ Domaine dans path: {domaine}")
        
        return (1.0, "")
    
    
    def _check_plan_comptable(
        self, 
        candidate: TaxonCandidate, 
        plans: List[str]
    ) -> tuple[float, str]:
        """Check si le candidat match un plan comptable"""
        
        for plan in plans:
            if plan.lower() in candidate.name.lower():
                return (self.config.plan_comptable_boost, f"✅ Plan: {plan}")
        
        return (1.0, "")
    
    
    def _check_incompatibility(
        self, 
        candidate: TaxonCandidate, 
        extracted_params: Dict[str, List[str]]
    ) -> tuple[bool, str]:
        """
        Check si le candidat est incompatible avec les paramètres extraits
        
        Returns:
            (is_incompatible, reason)
        """
        # Pour chaque concept dans le candidat
        for concept, incompatible_list in self.incompatibilities.items():
            
            # Si le concept est dans le nom ou breadcrumb du candidat
            if concept in candidate.name or (candidate.breadcrumb and concept in candidate.breadcrumb):
                
                # Check si un des paramètres extraits est incompatible
                for category, values in extracted_params.items():
                    for value in values:
                        # Normaliser
                        normalized_value = self._normalize_regime(value)
                        
                        for incompatible in incompatible_list:
                            normalized_incomp = self._normalize_regime(incompatible)
                            
                            if normalized_value == normalized_incomp or normalized_incomp in normalized_value:
                                return (True, f"{concept} incompatible avec {value}")
        
        return (False, "")
    
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _is_exact_match(self, term: str, text: str, threshold: float = 0.9) -> bool:
        """Check si term match exactement text"""
        term_lower = term.lower().strip()
        text_lower = text.lower().strip()
        
        # Match exact
        if term_lower == text_lower:
            return True
        
        # Match avec différence mineure (accents, pluriel, etc.)
        # Utiliser Levenshtein ou ratio simple
        if term_lower in text_lower or text_lower in term_lower:
            return True
        
        return False
    
    
    def _is_in_breadcrumb(self, term: str, breadcrumb: str) -> bool:
        """Check si term est dans le breadcrumb"""
        if not breadcrumb:
            return False
        
        term_lower = term.lower().strip()
        breadcrumb_lower = breadcrumb.lower()
        
        # Check dans chaque niveau
        levels = breadcrumb_lower.split(' > ')
        for level in levels:
            if term_lower in level or level in term_lower:
                return True
        
        return False
    
    
    def _normalize_regime(self, text: str) -> str:
        """
        Normalise les variantes de régimes fiscaux
        
        Ex: "IS" → "impôt sur les sociétés"
        """
        text_lower = text.lower().strip()
        
        # Mapping des variantes
        mappings = {
            'is': 'impôt sur les sociétés',
            'i.s.': 'impôt sur les sociétés',
            'impots sur les societes': 'impôt sur les sociétés',
            'ir': 'impôt sur le revenu',
            'i.r.': 'impôt sur le revenu',
            'bnc': 'bénéfices non commerciaux',
            'b.n.c.': 'bénéfices non commerciaux',
            'bic': 'bénéfices industriels et commerciaux',
            'b.i.c.': 'bénéfices industriels et commerciaux',
            'ba': 'bénéfices agricoles',
            'b.a.': 'bénéfices agricoles',
        }
        
        # Check exact match
        if text_lower in mappings:
            return mappings[text_lower]
        
        # Check si une variante est dans le texte
        for variant, normalized in mappings.items():
            if variant in text_lower:
                return normalized
        
        return text_lower
    
    
    def _log_reranking_changes(self, candidates: List[TaxonCandidate]):
        """Log les changements significatifs de ranking"""
        
        logger.info("\n📊 RERANKING SUMMARY:")
        logger.info(f"   Total candidates: {len(candidates)}")
        
        # Compter les boosts
        boosted = [c for c in candidates if c.metadata.get('boost_factor', 1.0) > 1.0]
        penalized = [c for c in candidates if c.metadata.get('boost_factor', 1.0) < 1.0]
        
        logger.info(f"   • Boosted: {len(boosted)}")
        logger.info(f"   • Penalized: {len(penalized)}")
        logger.info(f"   • Unchanged: {len(candidates) - len(boosted) - len(penalized)}")
        
        # Top 5 avec boost
        logger.info("\n🏆 Top 5 après reranking:\n")
        for i, candidate in enumerate(candidates[:5], 1):
            boost_factor = candidate.metadata.get('boost_factor', 1.0)
            original_score = candidate.metadata.get('original_score', candidate.final_score)
            boost_reasons = candidate.metadata.get('boost_reasons', [])
            
            logger.info(f"   {i}. {candidate.name}")
            logger.info(f"      • Score: {original_score:.4f} → {candidate.final_score:.4f} (x{boost_factor:.1f})")
            
            if boost_reasons:
                logger.info(f"      • Reasons: {', '.join(boost_reasons)}")
            
            logger.info("")


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("\n" + "=" * 80)
    print("  📝 EXEMPLE: Contextual Reranker")
    print("=" * 80)
    
    print("""
Ce reranker boost les résultats basés sur les paramètres extraits.

Exemple:
  Query: "SARL, impôt sur les sociétés, prestataire de services"
  
  Paramètres extraits:
    • formes_juridiques: ['SARL']
    • regimes_fiscaux: ['Impôt sur les sociétés']
    • domaines_activite: ['Prestataire de services']
  
  Candidats AVANT reranking:
    1. Bénéfices Non Commerciaux (score: 0.1892)
    2. Centre équestre (score: 0.1864)
    3. Prestataire de services (score: 0.1858)
    ...
    8. SARL (score: 0.1819)
  
  Candidats APRÈS reranking:
    1. SARL (score: 1.819) ← Boost x10
    2. Impôt sur les sociétés (score: 1.454) ← Boost x8
    3. Prestataire de services (score: 0.929) ← Boost x5
    ...
    28. Bénéfices Non Commerciaux (score: 0.019) ← Penalty x0.1 (incompatible IS)

Intégration dans le pipeline:
  
  from context_weaver.reranker.contextual_reranker import ContextualReranker
  
  # Dans taxonomy_pipeline.py
  self.contextual_reranker = ContextualReranker()
  
  # Après le reranking Dgraph
  candidates = self.dgraph_reranker.rerank(candidates, context)
  
  # Appliquer le reranking contextuel
  if 'extracted_params' in context:
      candidates = self.contextual_reranker.rerank(
          candidates, 
          context['extracted_params']
      )
""")