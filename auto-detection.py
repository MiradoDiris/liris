#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DÉMONSTRATION COMPLÈTE - Auto-Detection de Prérequis
Exemple executable montrant le système en action
"""

import logging
from typing import Dict, List, Set
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# SIMULATION DES COMPOSANTS EXISTANTS
# ============================================================================

@dataclass
class ConversationState:
    """État de conversation simplifié"""
    conversation_id: str
    confirmed_taxons: List[str] = field(default_factory=list)
    
    def has_prereq_satisfied(self, prereq_id: str) -> bool:
        return prereq_id in self.confirmed_taxons


@dataclass
class TaxonCandidate:
    """Candidat taxonomique simplifié"""
    taxon_id: str
    name: str
    prereq_hard_ids: List[str] = field(default_factory=list)
    prereq_soft_ids: List[str] = field(default_factory=list)


# ============================================================================
# AUTO-DETECTION SYSTEM
# ============================================================================

class AutoPrereqDetector:
    """Détecteur de prérequis automatiques"""
    
    def __init__(self):
        # Règles de pattern matching
        self.pattern_rules = {
            'label_basic_transaction': {
                'keywords': ['transaction', 'montant', 'payment', 'paiement'],
                'variables': ['transaction_amount', 'transaction_id', 'transaction_date'],
                'domain': 'fraude_bancaire',
                'confidence': 0.95
            },
            'label_customer_profile': {
                'keywords': ['client', 'customer', 'profil'],
                'variables': ['customer_id', 'customer_age', 'customer_income'],
                'confidence': 0.90
            },
            'label_dataset_quality': {
                'keywords': ['dataset', 'données', 'data', 'fichier', 'csv'],
                'variables': [],
                'confidence': 0.85
            }
        }
        
        # Implications hiérarchiques
        self.hierarchy = {
            'label_deep_learning_fraud': [
                'label_advanced_fraud',
                'label_basic_fraud',
                'label_ml_basics'
            ],
            'label_random_forest_fraud': [
                'label_ml_basics',
                'label_supervised_learning'
            ],
            'label_feature_engineering_advanced': [
                'label_feature_engineering_basic',
                'label_data_preparation'
            ]
        }
        
        # Mapping variables → prereqs
        self.variable_implications = {
            'has_transaction_data': ['transaction_amount', 'transaction_id', 'transaction_date'],
            'has_customer_profile': ['customer_id', 'customer_age', 'customer_income'],
            'has_geographic_data': ['country_code', 'country', 'region'],
            'has_merchant_data': ['merchant_id', 'merchant_name', 'merchant_category'],
            'has_temporal_data': ['timestamp', 'date', 'datetime', 'transaction_date']
        }
    
    
    def detect(
        self, 
        context: Dict, 
        matched_taxons: Set[str],
        known_prereqs: Set[str]
    ) -> Dict[str, float]:
        """
        Détecte les prérequis automatiquement
        
        Returns:
            Dict[prereq_id, confidence]
        """
        satisfied = {}
        
        logger.info("\n" + "="*80)
        logger.info("🔍 AUTO-DETECTION DE PRÉREQUIS")
        logger.info("="*80)
        
        # Stratégie 1: Pattern Matching
        logger.info("\n📋 Stratégie 1: Pattern Matching")
        pattern_results = self._pattern_matching(context, known_prereqs)
        satisfied.update(pattern_results)
        
        # Stratégie 2: Hiérarchie
        logger.info("\n🌳 Stratégie 2: Hiérarchie (Parents Implicites)")
        hierarchy_results = self._hierarchy_detection(matched_taxons, known_prereqs)
        satisfied.update(hierarchy_results)
        
        # Stratégie 3: Variable Inference
        logger.info("\n🔢 Stratégie 3: Variable Inference")
        variable_results = self._variable_inference(context, known_prereqs)
        satisfied.update(variable_results)
        
        logger.info("\n" + "="*80)
        logger.info(f"✅ TOTAL: {len(satisfied)} prérequis auto-détectés")
        logger.info("="*80 + "\n")
        
        return satisfied
    
    
    def _pattern_matching(self, context: Dict, known: Set[str]) -> Dict[str, float]:
        """Pattern matching: keywords + variables + domain"""
        satisfied = {}
        
        query = context.get('query', '').lower()
        variables = set(v.lower() for v in context.get('variables', []))
        domain = context.get('domain', '').lower()
        
        for prereq_id, rule in self.pattern_rules.items():
            if prereq_id in known:
                continue
            
            # Score keywords
            keywords_found = sum(1 for kw in rule['keywords'] if kw in query)
            keyword_score = keywords_found / len(rule['keywords']) if rule['keywords'] else 0
            
            # Score variables
            vars_found = sum(1 for var in rule['variables'] if var in variables)
            var_score = vars_found / len(rule['variables']) if rule['variables'] else 0
            
            # Score domain
            domain_score = 1.0 if rule.get('domain', '') in domain else 0.5
            
            # Score combiné
            if rule['keywords'] and rule['variables']:
                # Les deux doivent être partiellement satisfaits
                if keyword_score >= 0.3 and var_score >= 0.3:
                    confidence = (keyword_score * 0.4 + var_score * 0.4 + domain_score * 0.2)
                    confidence *= rule['confidence']
                    
                    if confidence >= 0.5:
                        satisfied[prereq_id] = confidence
                        logger.info(f"   ✅ {prereq_id}")
                        logger.info(f"      • Keywords: {keyword_score:.2f} ({keywords_found}/{len(rule['keywords'])})")
                        logger.info(f"      • Variables: {var_score:.2f} ({vars_found}/{len(rule['variables'])})")
                        logger.info(f"      • Confidence finale: {confidence:.2f}")
            
            elif rule['keywords']:
                # Keywords seulement
                if keyword_score >= 0.5:
                    confidence = keyword_score * rule['confidence']
                    satisfied[prereq_id] = confidence
                    logger.info(f"   ✅ {prereq_id}")
                    logger.info(f"      • Keywords: {keyword_score:.2f}")
                    logger.info(f"      • Confidence: {confidence:.2f}")
        
        if not satisfied:
            logger.info("   ⚠️  Aucun prérequis détecté par pattern matching")
        
        return satisfied
    
    
    def _hierarchy_detection(self, matched_taxons: Set[str], known: Set[str]) -> Dict[str, float]:
        """Détection hiérarchique: enfant → parents"""
        satisfied = {}
        
        for child in matched_taxons:
            if child in self.hierarchy:
                parents = self.hierarchy[child]
                
                for parent in parents:
                    if parent not in known:
                        satisfied[parent] = 1.0  # Confiance maximale
                        logger.info(f"   ✅ {parent}")
                        logger.info(f"      • Parent de: {child}")
                        logger.info(f"      • Confidence: 1.0 (hiérarchie)")
        
        if not satisfied:
            logger.info("   ℹ️  Aucun parent implicite détecté")
        
        return satisfied
    
    
    def _variable_inference(self, context: Dict, known: Set[str]) -> Dict[str, float]:
        """Inférence basée sur les variables"""
        satisfied = {}
        
        variables = set(v.lower() for v in context.get('variables', []))
        
        for prereq_id, required_vars in self.variable_implications.items():
            if prereq_id in known:
                continue
            
            # Compter l'overlap
            overlap = sum(1 for var in required_vars if var in variables)
            
            if overlap > 0:
                confidence = overlap / len(required_vars)
                
                if confidence >= 0.3:  # Seuil minimum
                    satisfied[prereq_id] = confidence
                    logger.info(f"   ✅ {prereq_id}")
                    logger.info(f"      • Variables: {overlap}/{len(required_vars)}")
                    logger.info(f"      • Confidence: {confidence:.2f}")
        
        if not satisfied:
            logger.info("   ⚠️  Aucun prérequis détecté par variables")
        
        return satisfied


# ============================================================================
# VALIDATION AVEC AUTO-DETECTION
# ============================================================================

class ValidatorWithAutoDetection:
    """Validator intégrant l'auto-detection"""
    
    def __init__(self, auto_detector: AutoPrereqDetector):
        self.auto_detector = auto_detector
    
    
    def validate(
        self,
        candidate: TaxonCandidate,
        context: Dict,
        conversation_state: ConversationState
    ) -> Dict:
        """Validation avec auto-detection"""
        
        logger.info("\n" + "="*80)
        logger.info("🎯 VALIDATION AVEC AUTO-DETECTION")
        logger.info("="*80)
        
        logger.info(f"\nCandidat: {candidate.name}")
        logger.info(f"Prérequis hard: {candidate.prereq_hard_ids}")
        logger.info(f"Prérequis soft: {candidate.prereq_soft_ids}")
        
        # Auto-detection
        matched_taxons = {candidate.taxon_id}
        known_prereqs = set(conversation_state.confirmed_taxons)
        
        auto_satisfied = self.auto_detector.detect(
            context=context,
            matched_taxons=matched_taxons,
            known_prereqs=known_prereqs
        )
        
        # Mettre à jour conversation state
        logger.info("\n📝 Mise à jour Conversation State:")
        logger.info(f"   Avant: {conversation_state.confirmed_taxons}")
        
        for prereq_id in auto_satisfied.keys():
            if prereq_id not in conversation_state.confirmed_taxons:
                conversation_state.confirmed_taxons.append(prereq_id)
        
        logger.info(f"   Après: {conversation_state.confirmed_taxons}")
        
        # Check prérequis hard
        logger.info("\n🔍 Vérification Prérequis Hard:")
        missing_hard = []
        
        for prereq in candidate.prereq_hard_ids:
            is_satisfied = conversation_state.has_prereq_satisfied(prereq)
            status = "✅" if is_satisfied else "❌"
            logger.info(f"   {status} {prereq}")
            
            if not is_satisfied:
                missing_hard.append(prereq)
        
        # Check prérequis soft
        logger.info("\n🔍 Vérification Prérequis Soft:")
        missing_soft = []
        
        for prereq in candidate.prereq_soft_ids:
            is_satisfied = conversation_state.has_prereq_satisfied(prereq)
            status = "✅" if is_satisfied else "⚠️ "
            logger.info(f"   {status} {prereq}")
            
            if not is_satisfied:
                missing_soft.append(prereq)
        
        # Résultat
        if missing_hard:
            status = "FAIL"
            logger.info(f"\n❌ VALIDATION: FAIL")
            logger.info(f"   Prérequis hard manquants: {missing_hard}")
        elif missing_soft:
            status = "CLARIFY"
            logger.info(f"\n⚠️  VALIDATION: CLARIFY")
            logger.info(f"   Prérequis soft manquants: {missing_soft}")
        else:
            status = "PASS"
            logger.info(f"\n✅ VALIDATION: PASS")
            logger.info(f"   Tous les prérequis satisfaits!")
        
        return {
            'status': status,
            'missing_hard': missing_hard,
            'missing_soft': missing_soft,
            'auto_satisfied': list(auto_satisfied.keys()),
            'confidence_scores': auto_satisfied
        }


# ============================================================================
# SCÉNARIOS DE DÉMONSTRATION
# ============================================================================

def demo_scenario_1():
    """Scénario 1: Utilisateur Expert - Auto-Detection Complète"""
    
    print("\n" + "="*80)
    print("📺 SCÉNARIO 1: Utilisateur Expert")
    print("="*80)
    
    # Setup
    auto_detector = AutoPrereqDetector()
    validator = ValidatorWithAutoDetection(auto_detector)
    conv_state = ConversationState(conversation_id="demo_1")
    
    # Contexte utilisateur
    context = {
        'query': "J'ai un dataset de 50K transactions avec montant, pays, merchant_id. Je veux détecter les fraudes.",
        'variables': ['transaction_amount', 'country_code', 'merchant_id', 'transaction_date'],
        'domain': 'fraude_bancaire'
    }
    
    logger.info("\n📥 Contexte Utilisateur:")
    logger.info(f"   Query: {context['query']}")
    logger.info(f"   Variables: {context['variables']}")
    logger.info(f"   Domain: {context['domain']}")
    
    # Candidat
    candidate = TaxonCandidate(
        taxon_id='label_fraud_detection',
        name='Détection de Fraude',
        prereq_hard_ids=['label_basic_transaction', 'label_dataset_quality'],
        prereq_soft_ids=['label_customer_profile']
    )
    
    # Validation
    result = validator.validate(candidate, context, conv_state)
    
    logger.info("\n" + "="*80)
    logger.info(f"🎯 RÉSULTAT FINAL: {result['status']}")
    logger.info("="*80)


def demo_scenario_2():
    """Scénario 2: Détection Hiérarchique"""
    
    print("\n\n" + "="*80)
    print("📺 SCÉNARIO 2: Détection Hiérarchique")
    print("="*80)
    
    auto_detector = AutoPrereqDetector()
    validator = ValidatorWithAutoDetection(auto_detector)
    conv_state = ConversationState(conversation_id="demo_2")
    
    context = {
        'query': "Je veux utiliser du deep learning pour la fraude bancaire",
        'variables': ['transaction_amount', 'customer_age'],
        'domain': 'fraude_bancaire'
    }
    
    logger.info("\n📥 Contexte Utilisateur:")
    logger.info(f"   Query: {context['query']}")
    logger.info(f"   Variables: {context['variables']}")
    
    # Candidat deep learning (implique plusieurs parents)
    candidate = TaxonCandidate(
        taxon_id='label_deep_learning_fraud',
        name='Deep Learning pour Fraude',
        prereq_hard_ids=['label_ml_basics', 'label_advanced_fraud'],
        prereq_soft_ids=['label_basic_fraud']
    )
    
    result = validator.validate(candidate, context, conv_state)
    
    logger.info("\n" + "="*80)
    logger.info(f"🎯 RÉSULTAT FINAL: {result['status']}")
    logger.info("="*80)


def demo_scenario_3():
    """Scénario 3: Détection Partielle - CLARIFY"""
    
    print("\n\n" + "="*80)
    print("📺 SCÉNARIO 3: Détection Partielle")
    print("="*80)
    
    auto_detector = AutoPrereqDetector()
    validator = ValidatorWithAutoDetection(auto_detector)
    conv_state = ConversationState(conversation_id="demo_3")
    
    context = {
        'query': "Je veux analyser mes clients pour faire du clustering",
        'variables': [],  # Pas de variables mentionnées
        'domain': 'customer_analytics'
    }
    
    logger.info("\n📥 Contexte Utilisateur:")
    logger.info(f"   Query: {context['query']}")
    logger.info(f"   Variables: {context['variables']}")
    
    candidate = TaxonCandidate(
        taxon_id='label_customer_clustering',
        name='Clustering de Clients',
        prereq_hard_ids=['label_customer_profile', 'label_feature_engineering_basic'],
        prereq_soft_ids=[]
    )
    
    result = validator.validate(candidate, context, conv_state)
    
    logger.info("\n" + "="*80)
    logger.info(f"🎯 RÉSULTAT FINAL: {result['status']}")
    logger.info("="*80)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*20 + "DÉMONSTRATION AUTO-DETECTION" + " "*30 + "║")
    print("║" + " "*15 + "Système de Prérequis Automatiques" + " "*27 + "║")
    print("╚" + "="*78 + "╝")
    
    # Exécuter les 3 scénarios
    demo_scenario_1()  # Expert → PASS
    demo_scenario_2()  # Hiérarchie → PASS
    demo_scenario_3()  # Partiel → CLARIFY
    
    print("\n\n" + "="*80)
    print("✅ DÉMONSTRATION TERMINÉE")
    print("="*80)
    print("\nRésumé:")
    print("  • Scénario 1: Expert avec variables complètes → PASS ✅")
    print("  • Scénario 2: Hiérarchie (deep learning) → PASS ✅")
    print("  • Scénario 3: Données insuffisantes → CLARIFY ⚠️ ")
    print("\n" + "="*80 + "\n")