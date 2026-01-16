#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Schémas de données pour Context Weaver
Tous les modèles de données utilisés dans le pipeline
✅ CORRIGÉ: context_weaver rendu optionnel dans PipelineOutput
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ============================================================================
# CLASSIFICATION OSS
# ============================================================================

@dataclass
class OSSClassification:
    """
    Résultat de la classification sémantique OSS 20B
    """
    domain: str
    task: str
    decision_type: str
    variables: List[str]
    risk_axis: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "domain": self.domain,
            "task": self.task,
            "decision_type": self.decision_type,
            "variables": self.variables,
            "risk_axis": self.risk_axis,
            "constraints": self.constraints,
            "confidence": self.confidence
        }


# ============================================================================
# NORMALISATION
# ============================================================================

@dataclass
class NormalizedVariables:
    """
    Variables normalisées selon la taxonomie
    """
    variables: Dict[str, str]  # {variable_user: variable_normalized}
    domain_taxonomy: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "variables": self.variables,
            "domain_taxonomy": self.domain_taxonomy
        }


# ============================================================================
# RÉSULTATS DE RECHERCHE
# ============================================================================

@dataclass
class SearchResult:
    """
    Résultat de recherche individuel (BM25 ou Embedding)
    """
    id: str
    name: str
    domain: str
    type: str  # "decision_tree", "rule", "template", etc.
    score: float
    method: str  # "bm25", "embedding", "hybrid_rrf", "hybrid_weighted"
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "type": self.type,
            "score": self.score,
            "method": self.method,
            "content": self.content,
            "metadata": self.metadata
        }


@dataclass
class HybridSearchResults:
    """
    Résultats de la fusion hybride
    """
    results: List[SearchResult]
    bm25_count: int
    embedding_count: int
    final_count: int
    fusion_method: str  # "rrf", "weighted", "cascade"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "results": [r.to_dict() for r in self.results],
            "bm25_count": self.bm25_count,
            "embedding_count": self.embedding_count,
            "final_count": self.final_count,
            "fusion_method": self.fusion_method
        }


# ============================================================================
# ARBRE DE DÉCISION
# ============================================================================

@dataclass
class DecisionTreeNode:
    """
    Nœud d'arbre de décision
    """
    field: str  # Nom du champ/variable
    ranges: Optional[List[str]] = None  # Pour valeurs numériques: ["<1000", "1000-5000", ">5000"]
    groups: Optional[List[str]] = None  # Pour catégories: ["local", "regional", "international"]
    levels: Optional[List[str]] = None  # Pour niveaux: ["low", "medium", "high"]
    children: List['DecisionTreeNode'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "field": self.field,
            "ranges": self.ranges,
            "groups": self.groups,
            "levels": self.levels,
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class DecisionTreeSkeleton:
    """
    Squelette d'arbre de décision
    Structure exploitable pour générer des datasets
    """
    root: str  # Nom du nœud racine
    nodes: List[DecisionTreeNode]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "root": self.root,
            "nodes": [n.to_dict() for n in self.nodes]
        }


# ============================================================================
# CONTEXT WEAVER OUTPUT
# ============================================================================

@dataclass
class ContextWeaverOutput:
    """
    Sortie finale du Context Weaver
    """
    decision_tree_skeleton: DecisionTreeSkeleton
    metadata: Dict[str, Any]
    confidence_score: float
    sources: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "decision_tree_skeleton": self.decision_tree_skeleton.to_dict(),
            "metadata": self.metadata,
            "confidence_score": self.confidence_score,
            "sources": self.sources
        }


# ============================================================================
# PIPELINE OUTPUT
# ============================================================================

@dataclass
class PipelineOutput:
    """
    ✅ CORRIGÉ: Résultat complet du pipeline Context Weaver
    
    Changements:
    - context_weaver rendu OPTIONNEL (plus nécessaire dans pipeline refactorisé)
    - metadata pour stocker taxonomy_output et autres infos
    """
    classification: OSSClassification
    normalized: NormalizedVariables
    search_results: HybridSearchResults
    execution_time_ms: float
    context_weaver: Optional[ContextWeaverOutput] = None  # ✅ RENDU OPTIONNEL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # ✅ PROPRIÉTÉS HELPER POUR ACCÈS TAXONOMY
    
    @property
    def can_access_graph(self) -> bool:
        """
        Helper pour vérifier si l'accès au graphe est autorisé
        
        Returns:
            True si validation taxonomy = PASS, False sinon
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('can_access_graph', False)
        
        # Fallback: check context_weaver metadata
        if self.context_weaver and hasattr(self.context_weaver, 'metadata'):
            if 'taxonomy_validation' in self.context_weaver.metadata:
                return self.context_weaver.metadata['taxonomy_validation'].get('can_access_graph', False)
        
        return False
    
    @property
    def needs_clarification(self) -> bool:
        """
        Helper pour savoir si une clarification utilisateur est nécessaire
        
        Returns:
            True si validation taxonomy = CLARIFY, False sinon
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('status') == 'CLARIFY'
        
        return False
    
    @property
    def validated_taxon(self) -> Optional[Dict[str, Any]]:
        """
        Helper pour accéder au taxon validé (si PASS)
        
        Returns:
            Dict avec taxon_id, name, breadcrumb si validé, None sinon
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            if tax_output.get('validated_taxon_id'):
                return {
                    'taxon_id': tax_output.get('validated_taxon_id'),
                    'name': tax_output.get('validated_taxon_name'),
                    'breadcrumb': tax_output.get('details', {}).get('breadcrumb'),
                    'depth': tax_output.get('details', {}).get('depth')
                }
        
        return None
    
    @property
    def taxonomy_status(self) -> str:
        """
        Helper pour obtenir le statut de validation taxonomy
        
        Returns:
            "PASS", "CLARIFY", "ABSTAIN", "ERROR", ou "NO_TAXONOMY"
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('status', 'NO_TAXONOMY')
        
        return 'NO_TAXONOMY'
    
    @property
    def clarification_question(self) -> Optional[str]:
        """
        Helper pour obtenir la question de clarification (si CLARIFY)
        
        Returns:
            Question de clarification ou None
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('clarification_question')
        
        return None
    
    @property
    def missing_requirements(self) -> List[Dict[str, Any]]:
        """
        Helper pour obtenir les requirements manquants (si CLARIFY)
        
        Returns:
            Liste des requirements manquants
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('missing_requirements', [])
        
        return []
    
    @property
    def suggested_candidates(self) -> List[Dict[str, str]]:
        """
        Helper pour obtenir les candidats suggérés (si CLARIFY)
        
        Returns:
            Liste des candidats suggérés avec id et name
        """
        if 'taxonomy_output' in self.metadata:
            tax_output = self.metadata['taxonomy_output']
            return tax_output.get('suggested_candidates', [])
        
        return []
    
    # ✅ MÉTHODES EXISTANTES
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        result = {
            "classification": self.classification.to_dict(),
            "normalized": self.normalized.to_dict(),
            "search_results": self.search_results.to_dict(),
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata
        }
        
        # Ajouter context_weaver seulement s'il existe
        if self.context_weaver:
            result["context_weaver"] = self.context_weaver.to_dict()
        
        return result
    
    def to_json(self) -> str:
        """Convertit en JSON"""
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ============================================================================
# UTILITAIRES
# ============================================================================

def create_search_result(
    doc_id: str,
    name: str,
    domain: str,
    doc_type: str,
    score: float,
    method: str,
    **kwargs
) -> SearchResult:
    """
    Factory pour créer un SearchResult
    """
    return SearchResult(
        id=doc_id,
        name=name,
        domain=domain,
        type=doc_type,
        score=score,
        method=method,
        content=kwargs.get('content', {}),
        metadata=kwargs.get('metadata', {})
    )


def create_decision_node(
    field: str,
    node_type: str = "numeric",
    **kwargs
) -> DecisionTreeNode:
    """
    Factory pour créer un DecisionTreeNode
    
    Args:
        field: Nom du champ
        node_type: "numeric", "categorical", "levels"
        **kwargs: ranges, groups, ou levels selon le type
    """
    if node_type == "numeric":
        return DecisionTreeNode(
            field=field,
            ranges=kwargs.get('ranges', [])
        )
    elif node_type == "categorical":
        return DecisionTreeNode(
            field=field,
            groups=kwargs.get('groups', [])
        )
    elif node_type == "levels":
        return DecisionTreeNode(
            field=field,
            levels=kwargs.get('levels', [])
        )
    else:
        return DecisionTreeNode(field=field)


# ============================================================================
# VALIDATION
# ============================================================================

def validate_classification(classification: OSSClassification) -> bool:
    """Valide une classification"""
    if not classification.domain or classification.domain == "":
        return False
    if not classification.task or classification.task == "":
        return False
    if not classification.decision_type or classification.decision_type == "":
        return False
    if not classification.variables or len(classification.variables) == 0:
        return False
    
    return True


def validate_search_result(result: SearchResult) -> bool:
    """Valide un résultat de recherche"""
    if not result.id or result.id == "":
        return False
    if not result.name or result.name == "":
        return False
    if result.score < 0 or result.score > 1:
        return False
    if result.method not in ["bm25", "embedding", "hybrid_rrf", "hybrid_weighted", "hybrid_cascade"]:
        return False
    
    return True


def validate_pipeline_output(output: PipelineOutput) -> bool:
    """
    ✅ CORRIGÉ: Valide un PipelineOutput complet
    
    Args:
        output: PipelineOutput à valider
        
    Returns:
        True si valide, False sinon
    """
    # Valider classification
    if not validate_classification(output.classification):
        return False
    
    # Valider normalized
    if not output.normalized.variables:
        return False
    
    # Valider search_results
    if output.search_results.final_count < 0:
        return False
    
    # Valider context_weaver (si présent)
    if output.context_weaver:
        if output.context_weaver.confidence_score < 0 or output.context_weaver.confidence_score > 1:
            return False
    
    # Valider execution_time
    if output.execution_time_ms < 0:
        return False
    
    return True