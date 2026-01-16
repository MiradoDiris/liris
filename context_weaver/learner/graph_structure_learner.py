#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Graph Structure Learner - Apprentissage de la structure Dgraph
Apprend les patterns, relations, et contraintes du graphe pour scorer les validations
✅ AJOUT: Méthodes predict_structure et validate_structure (stubs simples pour compatibilité)
"""

import logging
import numpy as np
from typing import Dict, List, Any, Set, Tuple, Optional
from pathlib import Path
from datetime import datetime
import json
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict

from context_weaver.taxonomy.taxonomy_models import PrereqSnapshot, StructureHypothesis, TaxonCandidate

logger = logging.getLogger(__name__)


# ============================================================================
# STRUCTURES DE DONNÉES
# ============================================================================

@dataclass
class NodePattern:
    """Pattern appris d'un type de nœud"""
    node_type: str
    predicates: Set[str] = field(default_factory=set)
    common_values: Dict[str, List[Any]] = field(default_factory=dict)
    value_distributions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    required_fields: Set[str] = field(default_factory=set)
    optional_fields: Set[str] = field(default_factory=set)
    frequency: int = 0
    
    def to_dict(self):
        """Conversion pour sérialisation"""
        return {
            'node_type': self.node_type,
            'predicates': list(self.predicates),
            'common_values': {k: v[:10] for k, v in self.common_values.items()},  # Limiter
            'value_distributions': self.value_distributions,
            'required_fields': list(self.required_fields),
            'optional_fields': list(self.optional_fields),
            'frequency': self.frequency
        }


@dataclass
class EdgePattern:
    """Pattern appris d'une relation"""
    source_type: str
    edge_type: str
    target_type: str
    cardinality: str  # "one-to-one", "one-to-many", "many-to-many"
    required: bool = False
    bidirectional: bool = False
    frequency: int = 0
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ConstraintPattern:
    """Contrainte apprise du graphe"""
    constraint_type: str  # "uniqueness", "referential", "value_range", "custom"
    applies_to: str  # node_type ou edge_type
    field: str
    rule: Dict[str, Any]
    violations_count: int = 0
    
    def to_dict(self):
        return asdict(self)


@dataclass
class PathPattern:
    """Pattern de chemin dans le graphe"""
    path_signature: str  # "Projet->Typologie->TaxonomyCluster"
    nodes: List[str]
    edges: List[str]
    frequency: int = 0
    avg_depth: float = 0.0
    
    def to_dict(self):
        return asdict(self)


# ============================================================================
# GRAPH STRUCTURE LEARNER
# ============================================================================

class GraphStructureLearner:
    """
    Apprend la structure du graphe Dgraph et fournit du scoring de validation
    
    Fonctionnalités:
    1. **Apprentissage des patterns de nœuds**: types, prédicats, valeurs
    2. **Apprentissage des relations**: arêtes, cardinalités, contraintes
    3. **Détection d'anomalies**: validation contre les patterns appris
    4. **Scoring de qualité**: évaluation de nouvelles structures
    5. **Évolution adaptative**: amélioration continue avec feedback
    ✅ AJOUT: predict_structure et validate_structure pour pipeline
    """
    
    def __init__(self, model_path: Path = None):
        """
        Initialise le learner
        
        Args:
            model_path: Chemin de sauvegarde du modèle appris
        """
        self.model_path = model_path or Path("./data/graph_structure_model.json")
        
        # === MODÈLE APPRIS ===
        self.learned_model = {
            # Patterns de nœuds par type
            'node_patterns': {},  # {node_type: NodePattern}
            
            # Patterns d'arêtes
            'edge_patterns': {},  # {edge_signature: EdgePattern}
            
            # Contraintes apprises
            'constraints': [],  # [ConstraintPattern]
            
            # Patterns de chemins
            'path_patterns': {},  # {path_signature: PathPattern}
            
            # Distributions statistiques
            'statistics': {
                'node_type_distribution': {},
                'edge_type_distribution': {},
                'depth_distribution': {},
                'fanout_distribution': {}
            },
            
            # Métriques d'apprentissage
            'learning_metrics': {
                'total_graphs_seen': 0,
                'total_nodes_analyzed': 0,
                'total_edges_analyzed': 0,
                'last_training_date': None,
                'training_iterations': 0
            },
            
            # Historique de validation
            'validation_history': {
                'successes': [],
                'failures': [],
                'anomalies': []
            }
        }
        
        # === PARAMÈTRES D'APPRENTISSAGE ===
        self.learning_params = {
            # Seuil de fréquence pour considérer un pattern comme stable
            'min_pattern_frequency': 3,
            
            # Seuil de confiance pour les distributions de valeurs
            'confidence_threshold': 0.7,
            
            # Nombre max d'exemples à garder par pattern
            'max_examples_per_pattern': 100,
            
            # Poids pour l'apprentissage incrémental (0-1)
            'learning_rate': 0.1,
            
            # Activer l'apprentissage en ligne
            'online_learning': True,
            
            # Fenêtre temporelle pour patterns (en jours)
            'temporal_window': 30
        }
        
        # === SEUILS DE SCORING ===
        self.scoring_thresholds = {
            'high_quality': 0.8,      # Score >= 0.8 → HIGH
            'medium_quality': 0.5,    # 0.5 <= Score < 0.8 → MEDIUM
            'low_quality': 0.3        # Score < 0.3 → LOW
        }
        
        # Charger le modèle existant
        self._load_model()
        
        logger.info("✅ GraphStructureLearner initialisé")
        logger.info(f"   • Modèle: {self.model_path}")
        logger.info(f"   • Graphes vus: {self.learned_model['learning_metrics']['total_graphs_seen']}")
        logger.info(f"   • Patterns de nœuds: {len(self.learned_model['node_patterns'])}")
        logger.info(f"   • Patterns d'arêtes: {len(self.learned_model['edge_patterns'])}")
    
    
    # ========================================================================
    # APPRENTISSAGE - PHASE 1: EXTRACTION DES PATTERNS
    # ========================================================================
    
    def train_from_graph(self, graph_data: Dict[str, Any]):
        """
        Entraîne le modèle à partir d'un graphe complet
        
        Args:
            graph_data: Structure complète du graphe depuis Dgraph
                Format attendu:
                {
                    'nodes': [{'uid': '0x1', 'type': 'Projet', ...}],
                    'edges': [{'from': '0x1', 'to': '0x2', 'predicate': 'typologies'}]
                }
        """
        logger.info("🎓 Entraînement sur graphe...")
        
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        # Mettre à jour métriques
        self.learned_model['learning_metrics']['total_graphs_seen'] += 1
        self.learned_model['learning_metrics']['total_nodes_analyzed'] += len(nodes)
        self.learned_model['learning_metrics']['total_edges_analyzed'] += len(edges)
        self.learned_model['learning_metrics']['last_training_date'] = datetime.now().isoformat()
        self.learned_model['learning_metrics']['training_iterations'] += 1
        
        # Apprendre patterns de nœuds
        for node in nodes:
            node_type = node.get('dgraph.type', 'Unknown')
            if node_type not in self.learned_model['node_patterns']:
                self.learned_model['node_patterns'][node_type] = NodePattern(node_type=node_type)
            
            pattern = self.learned_model['node_patterns'][node_type]
            pattern.frequency += 1
            # Ajouter prédicats (simplifié)
            for key in node.keys():
                if key != 'uid' and key != 'dgraph.type':
                    pattern.predicates.add(key)
                    if key not in pattern.required_fields:
                        pattern.required_fields.add(key)
        
        # Apprendre patterns d'arêtes
        for edge in edges:
            source_type = 'Unknown'
            target_type = 'Unknown'
            # Trouver types source/target (simplifié)
            for node in nodes:
                if node['uid'] == edge['from']:
                    source_type = node.get('dgraph.type', 'Unknown')
                if node['uid'] == edge['to']:
                    target_type = node.get('dgraph.type', 'Unknown')
            
            edge_sig = f"{source_type}--{edge['predicate']}-->{target_type}"
            if edge_sig not in self.learned_model['edge_patterns']:
                self.learned_model['edge_patterns'][edge_sig] = EdgePattern(
                    source_type=source_type,
                    edge_type=edge['predicate'],
                    target_type=target_type,
                    cardinality='one-to-many',  # Default
                    frequency=0
                )
            
            pattern = self.learned_model['edge_patterns'][edge_sig]
            pattern.frequency += 1
        
        # Sauvegarder
        self._save_model()
        
        logger.info(f"✅ Entraînement terminé: {len(nodes)} nœuds, {len(edges)} arêtes")
    
    
    # ========================================================================
    # PRÉDICTION ET VALIDATION (NOUVEAU)
    # ========================================================================
    
    def predict_structure(
        self,
        context: Dict[str, Any],
        candidates: List[TaxonCandidate],
        prereq_cache: Optional[PrereqSnapshot] = None
    ) -> StructureHypothesis:
        """
        ✅ NOUVEAU: Prédit la structure attendue basée sur patterns appris
        
        Args:
            context: {'domain': str, 'variables': List[str], 'task': str}
            candidates: Liste de TaxonCandidate (optionnel)
            prereq_cache: PrereqSnapshot pour prereqs hard
            
        Returns:
            StructureHypothesis avec hint structure
        """
        logger.debug("🔮 Prédiction de structure...")
        
        domain = context.get('domain', 'unknown')
        task = context.get('task', 'unknown')
        variables = context.get('variables', [])
        
        # Stub simple: Basé sur domain et task
        primary_label_id = None
        expected_prereq_hard_ids = []
        confidence = 0.5  # Default medium confidence
        
        # Logique basique (à enrichir)
        if domain == 'Macompta.fr' and 'TVA' in ' '.join(variables):
            primary_label_id = '0x27fd'  # Ex: Régime de déclaration du TVA
            expected_prereq_hard_ids = ['0x1']  # Ex: Prereq compte
            confidence = 0.7
        
        if prereq_cache:
            # Utiliser cache pour prereqs
            for var in variables:
                if var in prereq_cache.prereq_hard:
                    expected_prereq_hard_ids.extend(prereq_cache.prereq_hard[var])
        
        hypothesis = StructureHypothesis(
            primary_label_id=primary_label_id,
            expected_prereq_hard_ids=expected_prereq_hard_ids,
            confidence=confidence
        )
        
        if not candidates:
            logger.warning("⚠️ Aucun candidat pour prédire la structure")
        
        logger.debug(f"   • Predicted: {primary_label_id} (conf: {confidence:.2f})")
        
        return hypothesis
    
    
    def validate_structure(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ✅ NOUVEAU: Valide une structure contre patterns appris (sans altérer scoring interne)
        
        Args:
            structure: Dict représentant la structure {'id', 'name', 'type', 'depth', ...}
            context: Dict contexte {'domain', 'variables', 'task'}
            
        Returns:
            Dict avec {'quality_score': float, 'confidence': float, 'quality_category': str, 'issues': List[str]}
        """
        logger.debug(f"🔍 Validation structure: {structure.get('name', 'unknown')}")
        
        # Récupérer pattern pour ce type
        node_type = structure.get('dgraph.type', structure.get('type', 'Unknown'))
        pattern = self.learned_model['node_patterns'].get(node_type)
        
        quality_score = 0.5  # Default medium
        confidence = 0.6
        issues = []
        category = 'MEDIUM'
        
        if pattern:
            # Vérifier fréquence (stabilité)
            if pattern.frequency >= self.learning_params['min_pattern_frequency']:
                quality_score += 0.2
                confidence += 0.1
            
            # Vérifier champs requis
            missing_fields = pattern.required_fields - set(structure.keys())
            if missing_fields:
                issues.append(f"Champs manquants: {missing_fields}")
                quality_score -= 0.1 * len(missing_fields)
            else:
                quality_score += 0.2
            
            # Vérifier profondeur/coherence avec context
            depth = structure.get('depth', 0)
            if 'depth' in self.learned_model['statistics']['depth_distribution']:
                avg_depth = self.learned_model['statistics']['depth_distribution'].get(node_type, 3)
                if abs(depth - avg_depth) <= 1:
                    quality_score += 0.1
        
        # Catégoriser basé sur seuils (sans toucher scoring interne)
        if quality_score >= self.scoring_thresholds['high_quality']:
            category = 'HIGH'
        elif quality_score >= self.scoring_thresholds['medium_quality']:
            category = 'MEDIUM'
        else:
            category = 'LOW'
        
        # Limiter score 0-1
        quality_score = max(0.0, min(1.0, quality_score))
        confidence = max(0.0, min(1.0, confidence))
        
        validation = {
            'quality_score': quality_score,
            'confidence': confidence,
            'quality_category': category,
            'issues': issues
        }
        
        logger.debug(f"   • {category} (score: {quality_score:.2f}, conf: {confidence:.2f})")
        
        return validation
    
    
    # ========================================================================
    # FEEDBACK & AMÉLIORATION
    # ========================================================================
    
    def provide_feedback(self, structure_id: str, was_correct: bool, feedback_details: Dict[str, Any] = None):
        """
        Fournit du feedback pour améliorer le modèle
        
        Args:
            structure_id: ID de la structure validée
            was_correct: True si validation correcte
            feedback_details: Détails supplémentaires
        """
        logger.info(f"📝 Feedback reçu: {structure_id} → {'✅' if was_correct else '❌'}")
        
        if self.learning_params['online_learning']:
            # Ajuster les patterns selon le feedback
            # (Implémentation simplifiée)
            pass
        
        # Enregistrer
        feedback = {
            'structure_id': structure_id,
            'was_correct': was_correct,
            'details': feedback_details,
            'timestamp': datetime.now().isoformat()
        }
        
        # Garder un historique limité
        if len(self.learned_model['validation_history']['successes']) > 1000:
            self.learned_model['validation_history']['successes'] = \
                self.learned_model['validation_history']['successes'][-500:]
        
        self._save_model()
    
    
    # ========================================================================
    # MÉTRIQUES & ANALYSE
    # ========================================================================
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques d'apprentissage"""
        metrics = self.learned_model['learning_metrics'].copy()
        
        # Ajouter statistiques
        metrics['node_patterns_count'] = len(self.learned_model['node_patterns'])
        metrics['edge_patterns_count'] = len(self.learned_model['edge_patterns'])
        metrics['constraints_count'] = len(self.learned_model['constraints'])
        metrics['path_patterns_count'] = len(self.learned_model['path_patterns'])
        
        # Taux de succès
        successes = len(self.learned_model['validation_history']['successes'])
        failures = len(self.learned_model['validation_history']['failures'])
        total_validations = successes + failures
        
        if total_validations > 0:
            metrics['success_rate'] = successes / total_validations
        else:
            metrics['success_rate'] = 0.0
        
        return metrics
    
    
    def get_node_pattern(self, node_type: str) -> Optional[Dict[str, Any]]:
        """Retourne le pattern appris pour un type de nœud"""
        pattern = self.learned_model['node_patterns'].get(node_type)
        return pattern.to_dict() if pattern else None
    
    
    def get_all_patterns(self) -> Dict[str, Any]:
        """Retourne tous les patterns appris"""
        return {
            'node_patterns': {
                k: v.to_dict() for k, v in self.learned_model['node_patterns'].items()
            },
            'edge_patterns': {
                k: v.to_dict() for k, v in self.learned_model['edge_patterns'].items()
            },
            'constraints': [c.to_dict() for c in self.learned_model['constraints']],
            'path_patterns': {
                k: v.to_dict() for k, v in self.learned_model['path_patterns'].items()
            }
        }
    
    
    # ========================================================================
    # PERSISTANCE
    # ========================================================================
    
    def _load_model(self):
        """Charge le modèle depuis le disque - VERSION CORRIGÉE"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # ✅ CORRECTIF: Convertir les listes en sets lors du chargement
                node_patterns = {}
                for k, v in data.get('node_patterns', {}).items():
                    # Convertir les listes en sets
                    pattern_data = v.copy()
                    pattern_data['predicates'] = set(pattern_data.get('predicates', []))
                    pattern_data['required_fields'] = set(pattern_data.get('required_fields', []))
                    pattern_data['optional_fields'] = set(pattern_data.get('optional_fields', []))

                    node_patterns[k] = NodePattern(**pattern_data)

                self.learned_model['node_patterns'] = node_patterns

                # Edge patterns (pas de problème ici normalement)
                self.learned_model['edge_patterns'] = {
                    k: EdgePattern(**v) for k, v in data.get('edge_patterns', {}).items()
                }

                # Constraints
                self.learned_model['constraints'] = [
                    ConstraintPattern(**c) for c in data.get('constraints', [])
                ]

                # Path patterns
                path_patterns = {}
                for k, v in data.get('path_patterns', {}).items():
                    pattern_data = v.copy()
                    # Si nodes et edges sont aussi des sets, les convertir
                    if 'nodes' in pattern_data and isinstance(pattern_data['nodes'], set):
                        pattern_data['nodes'] = list(pattern_data['nodes'])
                    if 'edges' in pattern_data and isinstance(pattern_data['edges'], set):
                        pattern_data['edges'] = list(pattern_data['edges'])

                    path_patterns[k] = PathPattern(**pattern_data)

                self.learned_model['path_patterns'] = path_patterns

                self.learned_model['statistics'] = data.get('statistics', {})
                self.learned_model['learning_metrics'] = data.get('learning_metrics', {})
                self.learned_model['validation_history'] = data.get('validation_history', {})

                logger.info(f"📂 Modèle chargé: {self.model_path}")

            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement modèle: {e}")
                import traceback
                logger.warning(traceback.format_exc())
    
    
    def _save_model(self):
        """Sauvegarde le modèle sur le disque"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convertir en dict sérialisable
            save_data = {
                'node_patterns': {
                    k: v.to_dict() for k, v in self.learned_model['node_patterns'].items()
                },
                'edge_patterns': {
                    k: v.to_dict() for k, v in self.learned_model['edge_patterns'].items()
                },
                'constraints': [c.to_dict() for c in self.learned_model['constraints']],
                'path_patterns': {
                    k: v.to_dict() for k, v in self.learned_model['path_patterns'].items()
                },
                'statistics': self.learned_model['statistics'],
                'learning_metrics': self.learned_model['learning_metrics'],
                'validation_history': self.learned_model['validation_history']
            }
            
            with open(self.model_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"💾 Modèle sauvegardé: {self.model_path}")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde modèle: {e}")