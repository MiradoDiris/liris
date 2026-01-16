#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaxonomyRetriever - CORRECTION COMPLÈTE
✅ Format de retour VectorStore.search() corrigé
✅ BM25 optionnel (fallback si absent)
✅ Logging détaillé des erreurs
"""

import logging
import time
import inspect
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from context_weaver.taxonomy.taxonomy_models import TaxonCandidate

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Résultat complet du retrieval"""
    candidates: List[TaxonCandidate]
    total_retrieved: int
    dense_count: int
    bm25_count: int
    dense_top_score: float
    bm25_top_score: float
    rrf_top_score: float
    total_time_ms: float
    query_text: str
    rrf_min_score: float = 0.0
    rrf_max_score: float = 0.0


@dataclass
class RetrievalConfig:
    """Configuration du retrieval"""
    dense_top_k: int = 100
    bm25_top_k: int = 100
    rrf_k: int = 60
    final_top_n: int = 30
    boost_by_depth: bool = True
    depth_boost_factor: float = 0.1
    normalize_embeddings: bool = True


class TaxonomyRetriever:
    """
    ✅ CORRIGÉ: Retrieval hybrid avec gestion robuste des formats
    """
    
    def __init__(self, vector_store, embedder, config: Optional[RetrievalConfig] = None):
        self.vector_store = vector_store
        self.embedder = embedder
        self.config = config or RetrievalConfig()
        
        # Détecter l'API VectorStore
        self._detect_vector_store_api()
        
        logger.info("✅ TaxonomyRetriever initialisé")
    
    
    def _detect_vector_store_api(self):
        """Détecte la signature de VectorStore.search()"""
        if not hasattr(self.vector_store, 'search'):
            self.search_method = None
            self.search_params = {}
            logger.warning("⚠️ VectorStore has no 'search' method")
            return
        
        try:
            sig = inspect.signature(self.vector_store.search)
            params = list(sig.parameters.keys())
            
            self.search_method = 'search'
            self.search_params = {
                'has_k': 'k' in params,
                'has_top_k': 'top_k' in params,
                'has_filter_fn': 'filter_fn' in params,
                'has_filters': 'filters' in params,
                'has_query_vector': 'query_vector' in params,
                'has_vector': 'vector' in params,
                'all_params': params
            }
            
            logger.info(f"📍 VectorStore.search() detected params: {params}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not inspect VectorStore.search(): {e}")
            self.search_method = 'search'
            self.search_params = {}
    
    
    def retrieve(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> RetrievalResult:
        """Retrieval hybrid complet"""
        start_time = time.time()
        
        logger.info("🔍 TAXONOMY RETRIEVAL")
        
        # Dense Retrieval
        dense_results, dense_time = self._dense_retrieval(query_text, context)
        logger.info(f"✅ Dense: {len(dense_results)} résultats")
        
        # BM25 Retrieval (optionnel)
        bm25_results, bm25_time = self._bm25_retrieval(query_text, context)
        logger.info(f"✅ BM25: {len(bm25_results)} résultats")
        
        # RRF Fusion
        candidates = self._rrf_fusion(dense_results, bm25_results)
        logger.info(f"✅ RRF Fusion: {len(candidates)} candidats")
        
        # Hierarchical Boost
        if self.config.boost_by_depth:
            candidates = self._apply_hierarchical_boost(candidates)
        
        # TopN final
        final_candidates = candidates[:self.config.final_top_n]
        total_time = (time.time() - start_time) * 1000
        
        # Calculer les scores min/max
        rrf_scores = [c.rrf_score for c in candidates] if candidates else [0.0]
        
        result = RetrievalResult(
            candidates=final_candidates,
            total_retrieved=len(candidates),
            dense_count=len(dense_results),
            bm25_count=len(bm25_results),
            dense_top_score=dense_results[0][1] if dense_results else 0.0,
            bm25_top_score=bm25_results[0][1] if bm25_results else 0.0,
            rrf_top_score=final_candidates[0].rrf_score if final_candidates else 0.0,
            rrf_min_score=min(rrf_scores),
            rrf_max_score=max(rrf_scores),
            total_time_ms=total_time,
            query_text=query_text
        )
        
        self._log_summary(result)
        return result
    
    
    def _create_filter_function(self, context: Optional[Dict[str, Any]]) -> Optional[Callable]:
        """Crée une fonction de filtrage pour VectorStore.search()"""
        if not context or 'domain' not in context:
            return None
        
        target_domain = context['domain']
        
        def filter_fn(metadata: Dict[str, Any]) -> bool:
            """Retourne True si metadata correspond au domaine"""
            return metadata.get('domain') == target_domain
        
        return filter_fn
    
    
    def _dense_retrieval(
        self, 
        query_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Tuple[str, float, Dict]], float]:
        """
        ✅ CORRIGÉ: Dense retrieval avec gestion robuste du format
        """
        start_time = time.time()
        
        # Encode query
        logger.info("🧮 Génération embeddings OSS 20B...")
        query_embedding = self.embedder.encode(query_text)
        if self.config.normalize_embeddings:
            query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        logger.info(f"✅ Embeddings générés (dim={len(query_embedding)})")
        
        # Créer filtre
        filter_fn = self._create_filter_function(context)
        
        # ✅ CORRECTION: Appeler VectorStore.search() et gérer le retour
        try:
            result = self._call_vector_store_search(query_embedding, filter_fn)
            formatted = self._format_dense_results(result)
        except Exception as e:
            logger.error(f"❌ Dense retrieval error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            formatted = []
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return formatted, elapsed_ms
    
    
    def _call_vector_store_search(
        self, 
        query_embedding: np.ndarray, 
        filter_fn: Optional[Callable]
    ) -> Any:
        """
        ✅ CORRIGÉ: Appelle VectorStore.search() et retourne le résultat brut
        """
        if not self.search_method or not hasattr(self.vector_store, 'search'):
            logger.error("❌ VectorStore.search() not available")
            return ([], [])
        
        params = self.search_params
        
        # Build kwargs
        kwargs = {}
        
        # Vector parameter
        if params.get('has_query_vector'):
            kwargs['query_vector'] = query_embedding
        elif params.get('has_vector'):
            kwargs['vector'] = query_embedding
        
        # Top k parameter
        if params.get('has_top_k'):
            kwargs['top_k'] = self.config.dense_top_k
        elif params.get('has_k'):
            kwargs['k'] = self.config.dense_top_k
        
        # Filter parameter
        if filter_fn:
            if params.get('has_filter_fn'):
                kwargs['filter_fn'] = filter_fn
            elif params.get('has_filters'):
                logger.warning("⚠️ VectorStore expects 'filters' dict, skipping filter")
        
        # Appel
        try:
            if 'query_vector' not in kwargs and 'vector' not in kwargs:
                # Positional call
                result = self.vector_store.search(query_embedding, **kwargs)
            else:
                result = self.vector_store.search(**kwargs)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ VectorStore.search() failed: {e}")
            logger.error(f"   Attempted kwargs: {list(kwargs.keys())}")
            
            # Fallback minimal
            try:
                logger.warning("⚠️ Trying minimal VectorStore.search() call")
                result = self.vector_store.search(query_embedding)
                return result
            except Exception as e2:
                logger.error(f"❌ Minimal call also failed: {e2}")
                return ([], [])
    
    
    def _format_dense_results(self, result: Any) -> List[Tuple[str, float, Dict]]:
        """
        ✅ CORRIGÉ: Formate le résultat de VectorStore.search()
        
        Gère plusieurs formats possibles:
        1. Tuple (distances, metadata_list) <- FORMAT ACTUEL
        2. List[Dict]
        3. List[Tuple]
        """
        formatted = []
        
        # CAS 1: Tuple (distances, metadata_list)
        if isinstance(result, tuple) and len(result) == 2:
            distances, metadata_list = result
            
            # Vérifier que ce sont des listes
            if isinstance(distances, list) and isinstance(metadata_list, list):
                if len(distances) != len(metadata_list):
                    logger.error(f"❌ Length mismatch: {len(distances)} distances vs {len(metadata_list)} metadata")
                    return []
                
                for distance, metadata in zip(distances, metadata_list):
                    doc_id = metadata.get('id') or metadata.get('taxon_id', 'unknown')
                    score = float(distance)
                    formatted.append((doc_id, score, metadata))
                
                logger.info(f"✅ Formatted {len(formatted)} results from (distances, metadata_list)")
                return formatted
            
            # Sinon, essayer l'ancien format (distances, indices)
            elif isinstance(distances, list) and isinstance(metadata_list, list):
                logger.warning("⚠️ Unknown result format: trying to interpret as (distances, indices)")
                # Pas de métadata disponibles, abandonner
                return []
        
        # CAS 2: List[Dict]
        elif isinstance(result, list):
            for r in result:
                if isinstance(r, dict):
                    doc_id = r.get('id') or r.get('doc_id') or r.get('taxon_id', 'unknown')
                    score = r.get('score') or r.get('distance', 0.0)
                    metadata = r.get('metadata', r)
                    formatted.append((doc_id, float(score), metadata))
            
            logger.info(f"✅ Formatted {len(formatted)} results from List[Dict]")
            return formatted
        
        # CAS 3: Format inconnu
        else:
            logger.warning(f"⚠️ Unknown result format: {type(result)}")
            return []
    
    
    def _bm25_retrieval(
        self, 
        query_text: str, 
        context: Optional[Dict]
    ) -> Tuple[List[Tuple[str, float, Dict]], float]:
        """BM25 retrieval (optionnel)"""
        start_time = time.time()
        
        # Vérifier si BM25 est disponible
        if not hasattr(self.vector_store, 'bm25_search'):
            logger.warning("⚠️ VectorStore.bm25_search() not available")
            return [], (time.time() - start_time) * 1000
        
        # Enrichir query avec contexte
        bm25_query = query_text
        if context:
            if 'domain' in context:
                bm25_query = f"{bm25_query} {context['domain']}"
            if 'key_variables' in context:
                vars_text = ' '.join(context['key_variables'][:5])
                bm25_query = f"{bm25_query} {vars_text}"
        
        # Appel BM25
        try:
            results = self.vector_store.bm25_search(
                query=bm25_query, 
                top_k=self.config.bm25_top_k
            )
            
            formatted = self._format_dense_results(results)
            
        except Exception as e:
            logger.error(f"❌ BM25 search error: {e}")
            formatted = []
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return formatted, elapsed_ms
       
    def _rrf_fusion(self, dense_results: List[Tuple], bm25_results: List[Tuple]) -> List[TaxonCandidate]:
        """Reciprocal Rank Fusion - CORRIGÉ"""
        k = self.config.rrf_k

        dense_ranks = {taxon_id: rank + 1 for rank, (taxon_id, _, _) in enumerate(dense_results)}
        bm25_ranks = {taxon_id: rank + 1 for rank, (taxon_id, _, _) in enumerate(bm25_results)}

        all_taxon_ids = set(dense_ranks.keys()) | set(bm25_ranks.keys())

        rrf_scores = {}
        for taxon_id in all_taxon_ids:
            score = 0.0
            if taxon_id in dense_ranks:
                score += 1.0 / (k + dense_ranks[taxon_id])
            if taxon_id in bm25_ranks:
                score += 1.0 / (k + bm25_ranks[taxon_id])
            rrf_scores[taxon_id] = score

        # Créer candidats
        metadata_map = {}
        dense_scores = {}
        bm25_scores = {}

        for taxon_id, score, metadata in dense_results:
            metadata_map[taxon_id] = metadata
            dense_scores[taxon_id] = score

        for taxon_id, score, metadata in bm25_results:
            if taxon_id not in metadata_map:
                metadata_map[taxon_id] = metadata
            bm25_scores[taxon_id] = score

        candidates = []
        for taxon_id, rrf_score in rrf_scores.items():
            metadata = metadata_map.get(taxon_id, {})

            # ✅ CORRECTION : Enrichir metadata avec tous les champs
            # Au lieu de les passer directement à TaxonCandidate
            enriched_metadata = {
                'domain': metadata.get('domain', ''),
                'parent_ids': metadata.get('parent_ids', []),
                'child_ids': metadata.get('child_ids', []),
                'path_ids': metadata.get('path_ids', []),
                'prereq_hard_ids': metadata.get('prereq_hard_ids', []),
                'prereq_soft_ids': metadata.get('prereq_soft_ids', []),
                'incompatible_ids': metadata.get('incompatible_ids', []),
                'required_slots': metadata.get('required_slots', []),
                'dense_rank': dense_ranks.get(taxon_id),
                'bm25_rank': bm25_ranks.get(taxon_id),
                'source': self._determine_source(taxon_id, dense_ranks, bm25_ranks),
                **metadata  # Préserver metadata originale
            }

            # ✅ CORRECTION : TaxonCandidate selon la définition dans taxonomy_models.py
            candidate = TaxonCandidate(
                taxon_id=taxon_id,
                name=metadata.get('name', 'Unknown'),
                breadcrumb=metadata.get('breadcrumb', ''),
                depth=metadata.get('depth', 0),
                dense_score=dense_scores.get(taxon_id, 0.0),
                bm25_score=bm25_scores.get(taxon_id, 0.0),
                rrf_score=rrf_score,
                final_score=rrf_score,
                definition=metadata.get('definition', ''),
                prereq_hint=metadata.get('prereq_hint', ''),
                metadata=enriched_metadata  # ✅ Tous les autres champs vont ici
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.rrf_score, reverse=True)
        return candidates 
    
    def _determine_source(self, taxon_id: str, dense_ranks: Dict, bm25_ranks: Dict) -> str:
        in_dense = taxon_id in dense_ranks
        in_bm25 = taxon_id in bm25_ranks
        if in_dense and in_bm25:
            return "hybrid"
        elif in_dense:
            return "dense"
        else:
            return "bm25"
    
    
    def _apply_hierarchical_boost(self, candidates: List[TaxonCandidate]) -> List[TaxonCandidate]:
        """Boost selon la profondeur hiérarchique"""
        if not candidates:
            return candidates
        
        max_depth = max(c.depth for c in candidates)
        if max_depth == 0:
            return candidates
        
        for candidate in candidates:
            depth_ratio = candidate.depth / max_depth
            boost = depth_ratio * self.config.depth_boost_factor
            candidate.final_score = candidate.rrf_score * (1.0 + boost)
        
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        return candidates
    
    
    def _log_summary(self, result: RetrievalResult):
        """Log summary"""
        logger.info(f"\n📊 RETRIEVAL SUMMARY")
        logger.info(f"Total candidates: {result.total_retrieved}")
        logger.info(f"  • Dense: {result.dense_count}")
        logger.info(f"  • BM25: {result.bm25_count}")
        logger.info(f"  • Final TopN: {len(result.candidates)}")
        logger.info(f"Top Scores: Dense={result.dense_top_score:.4f}, BM25={result.bm25_top_score:.4f}, RRF={result.rrf_top_score:.4f}")
        logger.info(f"Time: {result.total_time_ms:.2f}ms\n")