#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Taxonomy Models - Structures corrigées selon spécifications
✅ AJOUT: TaxonomyPipelineOutput (manquant pour pipeline)
✅ AJOUT: Violation dataclass (pour violations list)
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from enum import Enum
import json

from context_weaver.models.schemas import SearchResult


# ============================================================================
# ENUMS
# ============================================================================

class ValidationStatus(Enum):
    """Statut de validation du validator"""
    PASS = "PASS"           # ✅ Ok, peut aller dans graph SoT
    CLARIFY = "CLARIFY"     # ❓ Manque info, question needed
    FAIL_HARD = "FAIL_HARD" # ❌ Prereq hard manquant (bloquant)
    WARN_SOFT = "WARN_SOFT" # ⚠️ Prereq soft manquant (non bloquant)
    ABSTAIN = "ABSTAIN"     # ⛔ Trop ambigu, ne peut pas décider


class ViolationType(Enum):
    """Type de violation détectée"""
    MISSING_PREREQ_HARD = "missing_prereq_hard"
    MISSING_PREREQ_SOFT = "missing_prereq_soft"
    INCOMPATIBILITY = "incompatibility"
    AMBIGUOUS_LOW_MARGIN = "ambiguous_low_margin"
    LOW_CONFIDENCE = "low_confidence"


# ============================================================================
# VIOLATION MODEL (AJOUTÉ)
# ============================================================================

@dataclass
class Violation:
    """
    ✅ AJOUT: Modèle pour une violation individuelle
    
    Utilisé dans ValidationResult.violations
    """
    
    type: ViolationType
    details: str  # Description de la violation
    affected_entity: Optional[str] = None  # ID du taxon affecté
    severity: str = "medium"  # "low", "medium", "high"
    resolution_hint: Optional[str] = None  # Suggestion de résolution
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# PHASE 1 - BUILD: TaxonDoc enrichi
# ============================================================================

@dataclass
class TaxonDoc:
    """
    ✅ CORRIGÉ: Document taxonomique pour vector store (Phase 1)
    
    Changements vs version originale:
    - ✅ Ajout prereq_hint_text (pour retrieval)
    - ✅ index_text enrichi par hiérarchie
    - ✅ Metadata structurée complète
    """
    
    # === A. TEXTE INDEXÉ (pour embeddings + BM25) ===
    title: str
    definition: str
    synonyms: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    breadcrumb: str = ""  # "Root > Parent > This"
    prereq_hint_text: str = ""  # ✅ NOUVEAU: "souvent requis: X, Y"
    children_names: str = ""  # ✅ NOUVEAU: noms enfants (optionnel)
    index_text: str = ""  # Texte complet pour embedding
    
    # === B. METADATA STRUCTURÉE (non texte) ===
    taxon_id: str = ""
    taxonomy_version: str = ""
    taxon_type: str = ""
    
    # Hiérarchie
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    path_ids: List[str] = field(default_factory=list)  # Ancêtres jusqu'à root
    depth: int = 0
    
    # Contraintes (✅ stockées en metadata, pas dans graph live)
    prereq_hard_ids: List[str] = field(default_factory=list)
    prereq_soft_ids: List[str] = field(default_factory=list)
    incompatible_ids: List[str] = field(default_factory=list)
    required_slots: List[str] = field(default_factory=list)
    
    # Contexte
    domain: str = ""
    category: str = ""
    
    # === C. EMBEDDING ===
    embedding: Optional[List[float]] = None
    embedder_id: str = ""
    
    
    def build_index_text(self) -> str:
        """
        ✅ CORRIGÉ: Construit index_text enrichi par hiérarchie
        
        Changements:
        - Ajout breadcrumb (contexte hiérarchique)
        - Ajout prereq_hint_text (signal pour retrieval)
        - Ajout children_names (optionnel)
        """
        parts = [
            self.title,
            self.definition if self.definition else "",
            f"Contexte: {self.breadcrumb}" if self.breadcrumb else "",
            f"Synonymes: {', '.join(self.synonyms)}" if self.synonyms else "",
            f"Exemples: {' | '.join(self.examples)}" if self.examples else "",
            self.prereq_hint_text if self.prereq_hint_text else "",  # ✅ NOUVEAU
            f"Sous-catégories: {self.children_names}" if self.children_names else "",  # ✅ NOUVEAU
            f"Domaine: {self.domain}" if self.domain else "",
        ]
        
        self.index_text = "\n".join(part for part in parts if part)
        return self.index_text


# ============================================================================
# PHASE 2 - RETRIEVAL: TaxonCandidate
# ============================================================================

@dataclass
class TaxonCandidate:
    """
    ✅ CORRIGÉ: Candidat taxonomique post-retrieval
    
    Changements:
    - ✅ Ajout final_score (post-RRF)
    - ✅ Metadata enrichi (prereqs, slots)
    - ✅ Prédiction de validation (hint)
    """
    
    # Identité
    taxon_id: str
    name: str
    breadcrumb: str
    depth: int
    
    # Scores
    dense_score: float = 0.0  # Embedding
    bm25_score: float = 0.0   # Keyword
    rrf_score: float = 0.0    # Fusion
    final_score: float = 0.0  # Score final post-rerank
    
    # Contenu (extrait)
    definition: str = ""
    prereq_hint: str = ""  # "Prereqs: X, Y"
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Ex: {'domain': 'Macompta.fr', 'prereq_hard': ['0x1'], 'required_slots': ['client_id']}
    
    # Prédiction validation (post-retrieval)
    predicted_status: Optional[ValidationStatus] = None
    predicted_confidence: float = 0.0
    
    
    def to_search_result(self) -> 'SearchResult':
        """Convertit en SearchResult pour pipeline"""
        return SearchResult(
            id=self.taxon_id,
            name=self.name,
            domain=self.metadata.get('domain', ''),
            type="taxon",
            score=self.final_score,
            method="taxonomy_rrf",
            content={
                'definition': self.definition,
                'breadcrumb': self.breadcrumb,
                'depth': self.depth,
                'prereq_hint': self.prereq_hint
            },
            metadata=self.metadata
        )


@dataclass
class RetrievalResult:
    """
    ✅ CORRIGÉ: Résultat du retrieval hybride
    
    Changements:
    - ✅ Ajout bm25_count, dense_count pour stats
    - ✅ Candidates limités (top N)
    """
    
    candidates: List[TaxonCandidate]
    bm25_count: int = 0
    dense_count: int = 0
    total_candidates: int = 0
    top_rrf_score: float = 0.0
    execution_time_ms: float = 0.0
    
    
    def get_top_candidates(self, n: int = 5) -> List[TaxonCandidate]:
        """Top N candidats par final_score"""
        return sorted(self.candidates, key=lambda c: c.final_score, reverse=True)[:n]


# ============================================================================
# PHASE 2 - VALIDATION: ValidationResult
# ============================================================================

@dataclass
class ValidationResult:
    """
    ✅ CORRIGÉ: Résultat de validation d'un candidat
    
    Changements:
    - ✅ Ajout violations: List[Violation] (au lieu de Dict)
    - ✅ Confidence calculée (pondérée)
    - ✅ Recommandations (clarify, alternatives)
    """
    
    status: ValidationStatus
    confidence: float  # 0.0-1.0
    primary_taxon_id: Optional[str] = None
    validated_taxon_name: Optional[str] = None
    
    # Détails diagnostics
    violations: List[Violation] = field(default_factory=list)  # ✅ List[Violation] (nouveau type)
    prereqs_check: Dict[str, Any] = field(default_factory=dict)
    slots_check: Dict[str, Any] = field(default_factory=dict)
    hierarchy_check: Dict[str, Any] = field(default_factory=dict)
    
    # ✅ NOUVEAU: Instructions de reranking
    rerank_instructions: Dict[str, Any] = field(default_factory=dict)
    
    validation_time_ms: float = 0.0


# ============================================================================
# PHASE 2 - OUTPUT GLOBAL: TaxonomyPipelineOutput
# ============================================================================

@dataclass
class TaxonomyPipelineOutput:
    """
    ✅ AJOUT: Output global du TaxonomyPipeline (manquant)
    
    Structure:
    - Status global (PASS/CLARIFY/FAIL)
    - Retrieval results
    - Validation result
    - Access graph authorized?
    - Clarification si needed
    - Metadata pour logging
    """
    
    status: ValidationStatus  # Global status
    can_access_graph: bool = False  # Autorisation graph SoT
    validated_taxon_id: Optional[str] = None
    validated_taxon_name: Optional[str] = None
    
    # Composants
    retrieval_result: Optional[RetrievalResult] = None
    validation_result: Optional[ValidationResult] = None
    
    # Si CLARIFY
    clarification_question: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)
    suggested_candidates: List[Dict[str, str]] = field(default_factory=list)  # [{'id': str, 'name': str}]
    
    # Métriques
    execution_time_ms: float = 0.0
    confidence: float = 0.0  # Global confidence
    
    # Metadata
    details: Dict[str, Any] = field(default_factory=dict)  # Pour logging/debug
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour JSON"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaxonomyPipelineOutput':
        """Crée depuis dict"""
        return cls(**data)


# ============================================================================
# PHASE 2 - PREREQ CACHE
# ============================================================================

@dataclass
class PrereqSnapshot:
    """
    ✅ NOUVEAU: Cache KV des prereqs (évite accès graph live)
    
    Construit en Phase 1, utilisé en Phase 2 par Validator
    """
    
    # Mappings prereq
    prereq_hard: Dict[str, Set[str]] = field(default_factory=dict)  # label_id → set(prereq_ids)
    prereq_soft: Dict[str, Set[str]] = field(default_factory=dict)
    
    # ✅ Fermeture transitive (optionnel mais recommandé)
    closure_hard: Dict[str, Set[str]] = field(default_factory=dict)  # Prereqs transitifs
    
    # Incompatibilités
    incompatible: Dict[str, Set[str]] = field(default_factory=dict)
    
    # Metadata
    taxonomy_version: str = ""
    created_at: str = ""
    
    
    def get_hard_prereqs(self, label_id: str, transitive: bool = False) -> Set[str]:
        """Retourne prereqs hard (transitifs ou non)"""
        if transitive and label_id in self.closure_hard:
            return self.closure_hard[label_id]
        return self.prereq_hard.get(label_id, set())
    
    
    def get_soft_prereqs(self, label_id: str) -> Set[str]:
        """Retourne prereqs soft"""
        return self.prereq_soft.get(label_id, set())
    
    
    def save_to_json(self, path: str):
        """Sauvegarde le cache"""
        data = {
            'prereq_hard': {k: list(v) for k, v in self.prereq_hard.items()},
            'prereq_soft': {k: list(v) for k, v in self.prereq_soft.items()},
            'closure_hard': {k: list(v) for k, v in self.closure_hard.items()},
            'incompatible': {k: list(v) for k, v in self.incompatible.items()},
            'taxonomy_version': self.taxonomy_version,
            'created_at': self.created_at
        }
        
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    
    @classmethod
    def load_from_json(cls, path: str) -> 'PrereqSnapshot':
        """Charge le cache depuis JSON"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(
            prereq_hard={k: set(v) for k, v in data.get('prereq_hard', {}).items()},
            prereq_soft={k: set(v) for k, v in data.get('prereq_soft', {}).items()},
            closure_hard={k: set(v) for k, v in data.get('closure_hard', {}).items()},
            incompatible={k: set(v) for k, v in data.get('incompatible', {}).items()},
            taxonomy_version=data.get('taxonomy_version', ''),
            created_at=data.get('created_at', '')
        )


# ============================================================================
# CONVERSATION STATE (inchangé)
# ============================================================================

@dataclass
class ConversationState:
    """État de conversation pour tracking des prereqs"""
    
    conversation_id: str
    confirmed_taxons: List[str] = field(default_factory=list)
    filled_slots: Dict[str, Any] = field(default_factory=dict)
    current_path: List[str] = field(default_factory=list)
    
    
    def has_prereq_satisfied(self, prereq_id: str) -> bool:
        return prereq_id in self.confirmed_taxons
    
    def has_slot_filled(self, slot_name: str) -> bool:
        return slot_name in self.filled_slots


# ============================================================================
# STRUCTURE HYPOTHESIS (pour Graph Learner)
# ============================================================================

@dataclass
class StructureHypothesis:
    """
    ✅ NOUVEAU: Hypothèse de structure du Graph Learner
    
    Utilisé pour hint retrieval/validation
    """
    
    primary_label_id: Optional[str] = None
    expected_prereq_hard_ids: List[str] = field(default_factory=list)
    expected_prereq_soft_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    predicted_depth: int = 0
    suggested_path: List[str] = field(default_factory=list)  # IDs chemin suggéré
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)