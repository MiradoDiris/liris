#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Taxonomy Models - VERSION UNION
✅ Ajout de champs pour tracking de l'union
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


# ============================================================================
# PHASE 1 - BUILD: TaxonDoc pour vector store
# ============================================================================

@dataclass
class TaxonDoc:
    """
    Document taxonomique pour vector store (Phase 1)
    
    ✅ SIMPLIFIÉ: Pas d'enrichissement prereq_hint (fait au runtime)
    """
    
    # === A. TEXTE INDEXÉ (pour embeddings + BM25) ===
    title: str
    definition: str
    synonyms: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    breadcrumb: str = ""  # "Root > Parent > This"
    index_text: str = ""  # Texte complet pour embedding
    
    # === B. METADATA STRUCTURÉE (non texte) ===
    taxon_id: str = ""
    taxonomy_version: str = ""
    taxon_type: str = ""
    
    # Hiérarchie
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    path_ids: List[str] = field(default_factory=list)
    depth: int = 0
    
    # Contraintes (stockées en metadata, enrichies au runtime)
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
        ✅ SIMPLIFIÉ: Construit index_text SANS enrichissement prereq
        
        Juste:
        - title, definition
        - breadcrumb (contexte hiérarchique)
        - synonymes, exemples
        - domain
        """
        parts = [
            self.title,
            self.definition if self.definition else "",
            f"Contexte: {self.breadcrumb}" if self.breadcrumb else "",
            f"Synonymes: {', '.join(self.synonyms)}" if self.synonyms else "",
            f"Exemples: {' | '.join(self.examples)}" if self.examples else "",
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
    Candidat taxonomique post-retrieval
    
    ✅ UNION MODE: Metadata enrichie, scores dense/BM25 séparés
    """
    
    # Identité
    taxon_id: str
    name: str
    breadcrumb: str
    depth: int
    
    # Scores individuels
    dense_score: float = 0.0  # Score embedding
    bm25_score: float = 0.0   # Score keyword
    rrf_score: float = 0.0    # ✅ Gardé pour compatibilité (= final_score en mode union)
    final_score: float = 0.0  # Score final après union/boost
    
    # Contenu (extrait)
    definition: str = ""
    prereq_hint: str = ""  # Enrichi par reranker
    
    # Metadata (enrichie par reranker via Dgraph)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Ex après enrichissement:
    # {
    #   'description': str,
    #   'prereq_hard_ids': List[str],
    #   'prereq_soft_ids': List[str],
    #   'incompatible_ids': List[str],
    #   'required_slots': List[str],
    #   'parent_ids': List[str],
    #   'child_ids': List[str],
    #   'category': str,
    #   'source': str,  # ✅ NOUVEAU: "dense", "bm25", "hybrid"
    #   'is_exact_match': bool,  # ✅ NOUVEAU: true si exact match détecté
    #   'intentKeywords': List[str],
    #   'actionKeywords': List[str],
    #   ...
    # }


@dataclass
class RetrievalResult:
    """
    Résultat du retrieval hybride UNION
    
    ✅ CHANGÉ: rrf_* → union_*
    ✅ NOUVEAU: duplicates_removed
    """
    
    candidates: List[TaxonCandidate]
    bm25_count: int = 0
    dense_count: int = 0
    total_candidates: int = 0
    top_union_score: float = 0.0
    union_min_score: float = 0.0
    union_max_score: float = 0.0 
    execution_time_ms: float = 0.0
    duplicates_removed: int = 0
    
    def get_top_candidates(self, n: int = 5) -> List[TaxonCandidate]:
        """Top N candidats par final_score"""
        return sorted(self.candidates, key=lambda c: c.final_score, reverse=True)[:n]