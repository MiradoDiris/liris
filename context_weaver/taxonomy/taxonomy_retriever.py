#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TaxonomyRetriever - VERSION UNION (au lieu de RRF)
✅ Query Expansion intelligente
✅ BM25 Exact Match Boost
✅ Multi-Query Strategy (optionnel)
✅ WHERE clause au lieu de filter_fn (PyQt5-safe)
✅ UNION: Dense + BM25 avec déduplication (pas de fusion RRF)
✅ FIX: Gestion robuste des distances (hex, string, dict, float)
"""

import logging
import time
import inspect
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass

from context_weaver.taxonomy.taxonomy_models import TaxonCandidate  
from context_weaver.utils.uid_helpers import extract_uid_from_metadata
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
    union_top_score: float  # ✅ CHANGÉ: rrf_top_score → union_top_score
    total_time_ms: float
    query_text: str
    enriched_query: str
    union_min_score: float = 0.0  # ✅ CHANGÉ: rrf_min_score → union_min_score
    union_max_score: float = 0.0  # ✅ CHANGÉ: rrf_max_score → union_max_score
    duplicates_removed: int = 0  # ✅ NOUVEAU: nombre de doublons supprimés


@dataclass
class RetrievalConfig:
    """Configuration du retrieval"""
    dense_top_k: int = 100
    bm25_top_k: int = 50
    final_top_n: int = 30
    boost_by_depth: bool = True
    depth_boost_factor: float = 0.1
    normalize_embeddings: bool = True
    
    enable_query_expansion: bool = True
    enable_bm25_exact_boost: bool = True
    bm25_exact_boost_factor: float = 2.5
    enable_multi_query: bool = False
    min_query_length_for_expansion: int = 3
    
    # ✅ NOUVEAU: Stratégie de score pour l'union
    # Options: "max" (prendre le max), "sum" (additionner), "dense" (privilégier dense), "bm25" (privilégier bm25)
    union_score_strategy: str = "max"  # Par défaut: prendre le score maximum


class TaxonomyRetriever:
    """
    ✅ VERSION UNION: Retrieval avec union simple au lieu de RRF
    ✅ FIXED: WHERE clause pour PyQt5 compatibility
    ✅ FIXED: Gestion robuste des distances ChromaDB
    """
    
    def __init__(self, vector_store, embedder, config: Optional[RetrievalConfig] = None):
        self.vector_store = vector_store
        self.embedder = embedder
        self.config = config or RetrievalConfig()
        
        # Pour tracking
        self.last_query = ""
        self.last_enriched_query = ""
        
        # Détecter l'API VectorStore
        self._detect_vector_store_api()
        
        logger.info("✅ TaxonomyRetriever initialisé (mode UNION)")
        logger.info(f"   • Query expansion: {self.config.enable_query_expansion}")
        logger.info(f"   • BM25 exact boost: {self.config.enable_bm25_exact_boost}")
        logger.info(f"   • Multi-query: {self.config.enable_multi_query}")
        logger.info(f"   • Union score strategy: {self.config.union_score_strategy}")

    def _safe_convert_distance(self, distance: Any) -> float:
        """
        ✅ NOUVELLE MÉTHODE: Convertit une distance au format ChromaDB en float robustement
        
        Gère tous les formats possibles:
        - dict: {'distance': 0.5}
        - float: 0.5
        - int: 1
        - string numérique: '0.5'
        - string hexadécimale: '0x8f75'
        
        Args:
            distance: Distance retournée par ChromaDB
            
        Returns:
            float: Distance normalisée >= 0.0
        """
        try:
            # Cas 1: dictionnaire
            if isinstance(distance, dict):
                distance = distance.get('distance', 0.0)
            
            # Cas 2: chaîne de caractères
            if isinstance(distance, str):
                distance = distance.strip()
                
                # Sous-cas 2a: format hexadécimal (ex: '0x8f75')
                if distance.startswith('0x') or distance.startswith('0X'):
                    # Convertir hex en int puis normaliser
                    hex_value = int(distance, 16)
                    # Normalisation assumant que les valeurs hex sont sur 16 bits (0-65535)
                    distance_val = hex_value / 65535.0
                    logger.debug(f"🔧 Hex distance converted: {distance} → {distance_val:.4f}")
                    return distance_val
                
                # Sous-cas 2b: format numérique en string (ex: '0.5')
                else:
                    distance_val = float(distance)
            
            # Cas 3: numérique (int ou float)
            else:
                distance_val = float(distance)
            
            # Validation: s'assurer que la distance est dans un intervalle raisonnable
            if distance_val < 0:
                logger.warning(f"⚠️ Distance négative {distance_val}, mise à 0")
                distance_val = 0.0
            elif distance_val > 2.0:  # Cosine distance max théorique = 2
                logger.warning(f"⚠️ Distance > 2: {distance_val}, clipping à 2.0")
                distance_val = 2.0
            
            return distance_val
        
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"⚠️ Impossible de convertir distance '{distance}' ({type(distance)}): {e}")
            logger.warning(f"   → Utilisation distance par défaut = 1.0")
            return 1.0  # Distance maximale = score minimal

    def _extract_clean_id(self, raw_id: Any) -> Optional[str]:
        # Cas 1: Déjà une string
        if isinstance(raw_id, str):
            return raw_id if raw_id else None
        
        # Cas 2: C'est un dictionnaire
        if isinstance(raw_id, dict):
            # Essayer différentes clés
            for key in ['id', 'taxon_id', 'uid']:
                if key in raw_id:
                    value = raw_id[key]
                    if isinstance(value, str) and value:
                        logger.debug(f"Extracted ID '{value}' from dict key '{key}'")
                        return value
            
            # Si aucune clé trouvée, logger l'erreur
            logger.error(f"❌ Dict sans clé 'id'/'taxon_id'/'uid': {list(raw_id.keys())[:5]}")
            return None
        
        # Cas 3: C'est un nombre (erreur)
        if isinstance(raw_id, (int, float)):
            logger.error(f"❌ ID numérique invalide: {raw_id}")
            return None
        
        # Cas 4: Type inconnu
        logger.error(f"❌ Type d'ID inconnu: {type(raw_id)}")
        return None
    
    
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
                'has_where': 'where' in params,
                'has_query_vector': 'query_vector' in params,
                'has_vector': 'vector' in params,
                'all_params': params
            }
            
            logger.info(f"📍 VectorStore.search() detected params: {params}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not inspect VectorStore.search(): {e}")
            self.search_method = 'search'
            self.search_params = {}
    
    
    def _enrich_query(self, query_text: str, context: Optional[Dict[str, Any]]) -> str:
        """
        ✅ CORRIGÉ: N'ajoute QUE le contexte pertinent, pas de termes génériques
        """
        if not self.config.enable_query_expansion:
            return query_text

        parts = [query_text]

        # ✅ Ajouter UNIQUEMENT le domain si pertinent
        if context and 'domain' in context:
            domain = context['domain']
            if domain and domain not in ['unknown', '', 'none', 'n/a']:
                # Vérifier que domain n'est pas déjà dans la query
                if domain.lower() not in query_text.lower():
                    parts.append(domain)

        # ✅ Ajouter extracted_params comme boost
        if context and 'extracted_params' in context:
            params = context['extracted_params']
            # Prendre les 3 premiers paramètres les plus importants
            priority_categories = ['formes_juridiques', 'regimes_fiscaux', 'domaines_activite']

            for category in priority_categories:
                if category in params and params[category]:
                    # Ajouter le premier élément de chaque catégorie
                    parts.append(params[category][0])

        enriched = " ".join(parts)

        if enriched != query_text:
            logger.info(f"✅ Query enrichie: '{query_text[:50]}...' → '{enriched[:50]}...'")

        return enriched
    
    def _validate_retrieval_results(self, results: List[Tuple], source: str) -> List[Tuple]:
        if not results:
            return results

        validated = []
        issues_found = 0
        skipped = 0

        for idx, result in enumerate(results):
            # Vérifier structure de base
            if not isinstance(result, tuple) or len(result) != 3:
                logger.error(f"❌ {source} #{idx+1}: Format invalide")
                skipped += 1
                continue
            
            taxon_id, score, metadata = result
            corrected = False

            # ✅ CORRECTION 1: Détecter inversion taxon_id <-> score
            if isinstance(taxon_id, (int, float)) and isinstance(score, str):
                logger.warning(f"⚠️ {source} #{idx+1}: Inversion détectée - swap")
                taxon_id, score = score, taxon_id
                corrected = True
                issues_found += 1

            # ✅ CORRECTION 2: taxon_id doit être string
            if not isinstance(taxon_id, str):
                try:
                    float(taxon_id)  # Si c'est un float pur -> erreur
                    logger.error(f"❌ {source} #{idx+1}: taxon_id est un float: {taxon_id} - IGNORÉ")
                    skipped += 1
                    continue
                except (ValueError, TypeError):
                    # Pas un nombre -> on peut le convertir
                    taxon_id = str(taxon_id)
                    corrected = True
                    issues_found += 1

            # ✅ CORRECTION 3: score doit être numérique
            if not isinstance(score, (int, float)):
                try:
                    score = float(score)
                    corrected = True
                    issues_found += 1
                except (ValueError, TypeError):
                    logger.error(f"❌ {source} #{idx+1}: Score invalide - IGNORÉ")
                    skipped += 1
                    continue
                
            # ✅ CORRECTION 4: metadata doit être un dict
            if not isinstance(metadata, dict):
                metadata = {}
                corrected = True
                issues_found += 1

            validated.append((taxon_id, float(score), metadata))

        # Résumé
        if issues_found > 0 or skipped > 0:
            logger.warning(
                f"⚠️ {source}: {issues_found} problème(s) corrigé(s), "
                f"{skipped} ignoré(s), {len(validated)}/{len(results)} valides"
            )

        return validated 
    
    def _generate_query_variants(self, query_text: str) -> List[str]:
        """
        ✅ NOUVEAU: Génère des variantes de la query pour multi-query strategy
        
        Args:
            query_text: Query originale
            
        Returns:
            Liste de variantes (max 3)
        """
        variants = [query_text]  # Original toujours en premier
        
        # Variante avec définition
        variants.append(f"{query_text} définition caractéristiques")
        
        # Variante avec question
        variants.append(f"Qu'est-ce que {query_text}")
        
        return variants
    
    
    def retrieve(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> RetrievalResult:
        """
        Retrieval hybride UNION (Dense + BM25 avec déduplication)
        
        Returns:
            RetrievalResult avec candidats
        """
        start_time = time.time()
        
        self.last_query = query_text
        
        logger.info("🔍 TAXONOMY RETRIEVAL (UNION MODE)")
        logger.info(f"   Query: '{query_text}'")
        
        # Dense Retrieval (avec ou sans multi-query)
        if self.config.enable_multi_query:
            dense_results, dense_time = self._multi_query_dense_retrieval(query_text, context)
             # ✅ VALIDATION des résultats
            dense_results = self._validate_retrieval_results(dense_results, "multi-query-dense")
        else:
            dense_results, dense_time = self._dense_retrieval(query_text, context)
            # ✅ VALIDATION des résultats
            dense_results = self._validate_retrieval_results(dense_results, "dense")
            logger.info(f"✅ Dense: {len(dense_results)} résultats ({dense_time:.2f}ms)")
        
        # BM25 Retrieval
        bm25_results, bm25_time = self._bm25_retrieval(query_text, context)
        # ✅ VALIDATION des résultats
        bm25_results = self._validate_retrieval_results(bm25_results, "bm25")
        logger.info(f"✅ BM25: {len(bm25_results)} résultats ({bm25_time:.2f}ms)")
        
        # ✅ UNION au lieu de RRF Fusion
        candidates, duplicates_removed = self._union_with_deduplication(dense_results, bm25_results, context)
        logger.info(f"✅ Union: {len(candidates)} candidats ({duplicates_removed} doublons supprimés)")

        candidates = self._filter_low_relevance(candidates, context)
        
        # Hierarchical Boost
        if self.config.boost_by_depth:
            candidates = self._apply_hierarchical_boost(candidates)
        
        # TopN final
        final_candidates = candidates[:self.config.final_top_n]
        total_time = (time.time() - start_time) * 1000
        
        # Calculer statistiques
        dense_top_score = dense_results[0][1] if dense_results else 0.0
        bm25_top_score = bm25_results[0][1] if bm25_results else 0.0
        union_top_score = final_candidates[0].final_score if final_candidates else 0.0
        
        union_scores = [c.final_score for c in candidates]
        union_min = min(union_scores) if union_scores else 0.0
        union_max = max(union_scores) if union_scores else 0.0
        
        # Construire résultat avec compatibilité automatique
        # Détecte quelle version de RetrievalResult est disponible
        import inspect
        
        # Inspecter les paramètres acceptés par RetrievalResult
        try:
            sig = inspect.signature(RetrievalResult.__init__)
            all_params = sig.parameters
            accepted_params = set(all_params.keys()) - {'self'}
            
            # Identifier les paramètres REQUIRED (sans valeur par défaut)
            required_params = set()
            for name, param in all_params.items():
                if name != 'self' and param.default == inspect.Parameter.empty:
                    required_params.add(name)
        except:
            # Fallback si inspection échoue - essayer les noms modernes
            accepted_params = {
                'candidates', 'bm25_count', 'dense_count',
                'total_candidates', 'top_union_score',
                'union_min_score', 'union_max_score',
                'execution_time_ms', 'duplicates_removed'
            }
            required_params = set()
        
        # Construire les paramètres selon ce qui est accepté
        params = {'candidates': final_candidates}
        
        # Counts (toujours présents)
        if 'dense_count' in accepted_params:
            params['dense_count'] = len(dense_results)
        if 'bm25_count' in accepted_params:
            params['bm25_count'] = len(bm25_results)
        
        # total_candidates (nouveau) ou total_retrieved (ancien)
        if 'total_candidates' in accepted_params:
            params['total_candidates'] = len(candidates)
        elif 'total_retrieved' in accepted_params:
            params['total_retrieved'] = len(candidates)
        
        # Scores individuels (dense_top_score, bm25_top_score) - souvent REQUIRED
        if 'dense_top_score' in accepted_params:
            params['dense_top_score'] = dense_top_score
        if 'bm25_top_score' in accepted_params:
            params['bm25_top_score'] = bm25_top_score
        
        # Scores union (nouveau) ou RRF (ancien)
        if 'top_union_score' in accepted_params:
            params['top_union_score'] = union_top_score
        elif 'union_top_score' in accepted_params:  # variante
            params['union_top_score'] = union_top_score
        elif 'rrf_top_score' in accepted_params:
            params['rrf_top_score'] = union_top_score
            
        if 'union_min_score' in accepted_params:
            params['union_min_score'] = union_min
        elif 'rrf_min_score' in accepted_params:
            params['rrf_min_score'] = union_min
            
        if 'union_max_score' in accepted_params:
            params['union_max_score'] = union_max
        elif 'rrf_max_score' in accepted_params:
            params['rrf_max_score'] = union_max
        
        # Temps d'exécution (toujours présent, mais nom peut varier)
        if 'execution_time_ms' in accepted_params:
            params['execution_time_ms'] = total_time
        elif 'total_time_ms' in accepted_params:
            params['total_time_ms'] = total_time
        
        # duplicates_removed (nouveau, peut ne pas exister)
        if 'duplicates_removed' in accepted_params:
            params['duplicates_removed'] = duplicates_removed
        
        # Query text (souvent REQUIRED dans anciennes versions)
        if 'query_text' in accepted_params:
            params['query_text'] = query_text
        if 'enriched_query' in accepted_params:
            params['enriched_query'] = self.last_enriched_query if hasattr(self, 'last_enriched_query') else query_text
        
        # Créer le résultat avec les paramètres compatibles
        result = RetrievalResult(**params)
        
        # Ajouter les attributs manquants si nécessaire (pour compatibilité ascendante)
        if not hasattr(result, 'top_union_score'):
            result.top_union_score = union_top_score
        if not hasattr(result, 'union_min_score'):
            result.union_min_score = union_min
        if not hasattr(result, 'union_max_score'):
            result.union_max_score = union_max
        if not hasattr(result, 'total_candidates'):
            result.total_candidates = len(candidates)
        if not hasattr(result, 'duplicates_removed'):
            result.duplicates_removed = duplicates_removed
        
        self._log_summary(result)
        
        return result
    
    
    def _dense_retrieval(
        self, 
        query_text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Tuple], float]:
        """
        ✅ FIXED: Dense retrieval avec gestion robuste des distances
        
        Returns:
            (résultats, temps_ms)
            où résultats = [(taxon_id, score, metadata), ...]
        """
        start = time.time()
        
        # Enrichir la query
        enriched_query = self._enrich_query(query_text, context)
        self.last_enriched_query = enriched_query
        
        # Générer embedding
        try:
            query_embedding = self.embedder.encode(enriched_query)
            
            if self.config.normalize_embeddings:
                query_embedding = query_embedding / np.linalg.norm(query_embedding)
            
        except Exception as e:
            logger.error(f"❌ Erreur génération embedding: {e}")
            return [], 0.0
        
        # Recherche dense
        try:
            search_kwargs = {}
            
            # Adapter les paramètres selon l'API détectée
            if self.search_params.get('has_query_vector'):
                search_kwargs['query_vector'] = query_embedding
            elif self.search_params.get('has_vector'):
                search_kwargs['vector'] = query_embedding
            
            if self.search_params.get('has_k'):
                search_kwargs['k'] = self.config.dense_top_k
            elif self.search_params.get('has_top_k'):
                search_kwargs['top_k'] = self.config.dense_top_k
            
            # Filtres contextuels (WHERE clause pour PyQt5)
            if context and 'domain' in context and context['domain']:
                domain = context['domain']
                if self.search_params.get('has_where'):
                    search_kwargs['where'] = {'domain': domain}
                elif self.search_params.get('has_filters'):
                    search_kwargs['filters'] = {'domain': domain}
            
            results = self.vector_store.search(**search_kwargs)
            
            # Normaliser le format de retour
            # VectorStore peut retourner (ids, distances, metadatas) ou dict
            if isinstance(results, dict):
                # Format dict: {'ids': [...], 'distances': [...], 'metadatas': [...]}
                ids_list = results.get('ids', [])
                distances_list = results.get('distances', [])
                metadatas_list = results.get('metadatas', [])
                
                # Aplatir si nécessaire
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    distances = distances_list[0] if isinstance(distances_list[0], list) else distances_list
                    metadatas = metadatas_list[0] if isinstance(metadatas_list[0], list) else metadatas_list
                else:
                    ids, distances, metadatas = ids_list, distances_list, metadatas_list
                
                formatted_results = []
                # ✅ FIX: Ordre correct - zip(ids, distances, metadatas) → (id, distance, metadata)

                for taxon_id, distance, metadata in zip(ids, distances, metadatas):
                    # ✅ NOUVELLE CORRECTION: Utiliser _safe_convert_distance
                    distance_val = self._safe_convert_distance(distance)
                    score = 1.0 / (1.0 + distance_val)
                    formatted_results.append((taxon_id, score, metadata or {}))
                
                elapsed = (time.time() - start) * 1000
                return formatted_results, elapsed
            
            elif isinstance(results, tuple) and len(results) == 3:
                # Format tuple: (ids, distances, metadatas)
                ids_list, distances_list, metadatas_list = results
                
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    distances = distances_list[0] if isinstance(distances_list[0], list) else distances_list
                    metadatas = metadatas_list[0] if isinstance(metadatas_list[0], list) else metadatas_list
                else:
                    ids, distances, metadatas = ids_list, distances_list, metadatas_list
                
                formatted_results = []
                # ✅ FIX: Ordre correct pour format tuple
                for taxon_id, distance, metadata in zip(ids, distances, metadatas):
                    # ✅ NOUVELLE CORRECTION: Utiliser _safe_convert_distance
                    distance_val = self._safe_convert_distance(distance)
                    score = 1.0 / (1.0 + distance_val)
                    formatted_results.append((taxon_id, score, metadata or {}))
                
                elapsed = (time.time() - start) * 1000
                return formatted_results, elapsed
            
            elif isinstance(results, tuple) and len(results) == 2:
                # Format tuple legacy: (ids, distances) - sans metadatas
                ids_list, distances_list = results
                
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    distances = distances_list[0] if isinstance(distances_list[0], list) else distances_list
                else:
                    ids, distances = ids_list, distances_list
                
                formatted_results = []
                # ✅ FIX: Ordre correct pour format legacy

                for taxon_id, distance in zip(ids, distances):
                    # ✅ NOUVELLE CORRECTION: Utiliser _safe_convert_distance
                    distance_val = self._safe_convert_distance(distance)
                    score = 1.0 / (1.0 + distance_val)
                    # Métadonnées vides car non fournies
                    formatted_results.append((taxon_id, score, {}))
                
                elapsed = (time.time() - start) * 1000
                return formatted_results, elapsed
            
            else:
                logger.warning(f"⚠️ Format de résultats inattendu: {type(results)}")
                return [], 0.0
        
        except Exception as e:
            logger.error(f"❌ Erreur dense retrieval: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], 0.0
    
    
    def _multi_query_dense_retrieval(
        self,
        query_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Tuple], float]:
        """
        ✅ NOUVEAU: Multi-query dense retrieval avec agrégation
        
        Génère plusieurs variantes de la query et agrège les résultats
        """
        start = time.time()
        
        variants = self._generate_query_variants(query_text)
        logger.info(f"🔄 Multi-query avec {len(variants)} variantes")
        
        # Récupérer résultats pour chaque variante
        all_results = {}  # {taxon_id: (best_score, metadata)}
        
        for variant in variants:
            variant_results, _ = self._dense_retrieval(variant, context)
            
            for taxon_id, score, metadata in variant_results:
                if taxon_id not in all_results or score > all_results[taxon_id][0]:
                    all_results[taxon_id] = (score, metadata)
        
        # Convertir en liste triée
        aggregated = [
            (taxon_id, score, metadata)
            for taxon_id, (score, metadata) in all_results.items()
        ]
        aggregated.sort(key=lambda x: x[1], reverse=True)
        
        # Limiter au top_k
        aggregated = aggregated[:self.config.dense_top_k]
        
        elapsed = (time.time() - start) * 1000
        logger.info(f"   ✅ Multi-query: {len(aggregated)} résultats uniques")
        
        return aggregated, elapsed
    
    
    def _bm25_retrieval(
        self,
        query_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Tuple], float]:
        """
        ✅ VERSION CORRIGÉE: BM25 keyword retrieval avec gestion robuste de tous les formats

        Returns:
            (résultats, temps_ms)
            où résultats = [(taxon_id, score, metadata), ...]
        """
        start = time.time()

        enriched_query = self._enrich_query(query_text, context)

        try:
            results = self.vector_store.bm25_search(
                query=enriched_query,
                top_k=self.config.bm25_top_k
            )

            formatted_results = []

            # CAS 1: Tuple de 3 éléments (ids, scores, metadatas) - Format étendu
            if isinstance(results, tuple) and len(results) == 3:
                logger.info("✅ BM25 format détecté: tuple(ids, scores, metadatas)")
                ids_list, scores_list, metadatas_list = results

                # Déballer si imbriqué
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    scores = scores_list[0] if isinstance(scores_list[0], list) else scores_list
                    metadatas = metadatas_list[0] if isinstance(metadatas_list[0], list) else metadatas_list
                else:
                    ids, scores, metadatas = ids_list, scores_list, metadatas_list

                # Construire les résultats
                for taxon_id, score, metadata in zip(ids, scores, metadatas):
                    score_value = self._safe_convert_score(score, taxon_id)
                    formatted_results.append((taxon_id, score_value, metadata or {}))

            # CAS 2: Tuple de 2 éléments (ids, scores) - Format standard
            elif isinstance(results, tuple) and len(results) == 2:
                logger.info("✅ BM25 format détecté: tuple(ids, scores)")
                ids_list, scores_list = results

                # Déballer si imbriqué
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    scores = scores_list[0] if isinstance(scores_list[0], list) else scores_list
                else:
                    ids, scores = ids_list, scores_list

                # Construire les résultats avec récupération de metadata
                for taxon_id, score in zip(ids, scores):
                    score_value = self._safe_convert_score(score, taxon_id)
                    metadata = self._fetch_metadata_for_taxon(taxon_id)
                    formatted_results.append((taxon_id, score_value, metadata))

            # CAS 3: Dict avec clés 'ids' et 'scores' (et optionnellement 'metadatas')
            elif isinstance(results, dict):
                logger.info("✅ BM25 format détecté: dict")
                ids_list = results.get('ids', [])
                scores_list = results.get('scores', [])
                metadatas_list = results.get('metadatas', None)

                # Déballer si imbriqué
                if isinstance(ids_list, list) and len(ids_list) > 0:
                    ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
                    scores = scores_list[0] if isinstance(scores_list[0], list) else scores_list
                    if metadatas_list:
                        metadatas = metadatas_list[0] if isinstance(metadatas_list[0], list) else metadatas_list
                    else:
                        metadatas = [{}] * len(ids)
                else:
                    ids = ids_list
                    scores = scores_list
                    metadatas = metadatas_list or [{}] * len(ids)

                # Construire les résultats
                for taxon_id, score, metadata in zip(ids, scores, metadatas):
                    score_value = self._safe_convert_score(score, taxon_id)
                    formatted_results.append((taxon_id, score_value, metadata or {}))

            # CAS 4: Liste de tuples [(id, score), ...] ou [(id, score, metadata), ...]
            elif isinstance(results, list):
                logger.info("✅ BM25 format détecté: list")
                for item in results:
                    if isinstance(item, tuple):
                        if len(item) == 2:
                            taxon_id, score = item
                            score_value = self._safe_convert_score(score, taxon_id)
                            metadata = self._fetch_metadata_for_taxon(taxon_id)
                            formatted_results.append((taxon_id, score_value, metadata))
                        elif len(item) == 3:
                            taxon_id, score, metadata = item
                            score_value = self._safe_convert_score(score, taxon_id)
                            formatted_results.append((taxon_id, score_value, metadata or {}))
                        else:
                            logger.warning(f"⚠️ Item BM25 avec {len(item)} éléments ignoré")

            # CAS 5: Format inconnu
            else:
                logger.error(f"❌ Format BM25 non supporté: {type(results)}")
                logger.error(f"   Type: {type(results)}")
                logger.error(f"   Valeur: {str(results)[:200]}")

                # Tenter de déboguer le format
                if hasattr(results, '__len__'):
                    logger.error(f"   Longueur: {len(results)}")
                if isinstance(results, tuple):
                    logger.error(f"   Éléments du tuple:")
                    for i, elem in enumerate(results):
                        logger.error(f"     [{i}] Type: {type(elem)}, Longueur: {len(elem) if hasattr(elem, '__len__') else 'N/A'}")

                return [], 0.0

            elapsed = (time.time() - start) * 1000

            # Log succès
            if formatted_results:
                logger.info(f"✅ BM25: {len(formatted_results)} résultats")
            else:
                logger.warning(f"⚠️ BM25: 0 résultats (format détecté mais vide)")

            return formatted_results, elapsed

        except Exception as e:
            logger.error(f"❌ Erreur BM25 retrieval: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], 0.0
        
    def _safe_convert_score(self, score: Any, taxon_id: str) -> float:
        try:
            # Cas 1: dict avec clé 'score'
            if isinstance(score, dict):
                score_value = score.get('score', 0.0) if 'score' in score else 0.0

            # Cas 2: string numérique
            elif isinstance(score, str):
                score_value = float(score)

            # Cas 3: numérique (int ou float)
            elif isinstance(score, (int, float)):
                score_value = float(score)

            # Cas 4: None
            elif score is None:
                score_value = 0.0

            # Cas 5: inconnu
            else:
                logger.warning(f"⚠️ Type de score BM25 inattendu pour {taxon_id}: {type(score)}")
                score_value = 0.0

            # Validation
            if score_value < 0:
                logger.warning(f"⚠️ Score BM25 négatif pour {taxon_id}: {score_value}, mise à 0")
                score_value = 0.0

            return score_value

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"⚠️ Impossible de convertir score BM25 '{score}' pour {taxon_id}: {e}")
            return 0.0
        
    def _fetch_metadata_for_taxon(self, taxon_id: str) -> Dict[str, Any]:
        try:
            # Méthode 1: Via cache si disponible
            if hasattr(self.vector_store, '_metadata_cache') and self.vector_store._metadata_cache:
                metadata = self.vector_store._metadata_cache.get(taxon_id, {})
                if metadata:
                    return metadata

            # Méthode 2: Via méthode publique
            if hasattr(self.vector_store, 'get_metadata'):
                metadata = self.vector_store.get_metadata(taxon_id)
                if metadata:
                    return metadata

            # Méthode 3: Via collection ChromaDB directement
            if hasattr(self.vector_store, 'collection'):
                result = self.vector_store.collection.get(
                    ids=[taxon_id],
                    include=['metadatas']
                )
                if result and result.get('metadatas') and len(result['metadatas']) > 0:
                    return result['metadatas'][0] or {}

            return {}

        except Exception as e:
            logger.debug(f"Metadata non disponible pour {taxon_id}: {e}")
            return {}

    def _filter_low_relevance(
        self,
        candidates: List[TaxonCandidate],
        context: Optional[Dict[str, Any]] = None
    ) -> List[TaxonCandidate]:
        """
        Filtre les candidats de faible pertinence
        
        Critères:
        - Score trop faible (< 10% du max)
        - Domaine incompatible (si contexte fourni)
        """
        if not candidates:
            return candidates
        
        # Seuil relatif (10% du meilleur score)
        max_score = max(c.final_score for c in candidates)
        min_threshold = max_score * 0.1
        
        filtered = [c for c in candidates if c.final_score >= min_threshold]
        
        # Filtre domaine si contexte
        if context and 'domain' in context and context['domain']:
            expected_domain = context['domain']
            filtered = [
                c for c in filtered 
                if c.metadata.get('domain', '') == expected_domain or c.metadata.get('domain', '') == ''
            ]
        
        removed = len(candidates) - len(filtered)
        if removed > 0:
            logger.info(f"🗑️ {removed} candidats filtrés (faible pertinence)")
        
        return filtered
    
    
    def _detect_exact_matches(self, bm25_results: List[Tuple]) -> set:
        """
        ✅ Détecte les exact matches dans les résultats BM25
        
        Args:
            bm25_results: Liste de (taxon_id, score, metadata)
            
        Returns:
            Set de taxon_ids qui sont des exact matches
        """
        if not self.last_enriched_query:
            return set()
        
        query_normalized = self.last_enriched_query.lower().strip()
        query_words = set(query_normalized.split())
        
        exact_matches = set()
        
        for taxon_id, score, metadata in bm25_results:
            name = metadata.get('name', '').lower().strip()
            
            # Exact match complet
            if name == query_normalized:
                exact_matches.add(taxon_id)
                logger.info(f"🎯 Exact match detected: '{name}'")
                continue
            
            # Exact match partiel (tous les mots de la query sont dans le nom)
            name_words = set(name.split())
            if query_words.issubset(name_words):
                exact_matches.add(taxon_id)
                logger.info(f"🎯 Partial match detected: '{name}'")
        
        return exact_matches
    
    
    def _union_with_deduplication(
        self, 
        dense_results: List[Tuple], 
        bm25_results: List[Tuple],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[TaxonCandidate], int]:
        """
        ✅ FIXED: Union simple avec déduplication ET merge des métadonnées
        
        Stratégie:
        1. Collecter tous les résultats (dense + BM25)
        2. Pour les doublons, choisir le meilleur score selon la stratégie configurée
        3. ✅ NOUVEAU: Merger les métadonnées au lieu de les ignorer
        4. Trier par score final
        
        Args:
            dense_results: Résultats dense [(taxon_id, score, metadata), ...]
            bm25_results: Résultats BM25 [(taxon_id, score, metadata), ...]
            context: Contexte optionnel
            
        Returns:
            (candidats, nombre_doublons_supprimés)
        """
        
        # ✅ Détecter exact matches pour boost
        exact_matches = set()
        if self.config.enable_bm25_exact_boost:
            exact_matches = self._detect_exact_matches(bm25_results)
        
        # ✅ Collecter tous les taxons avec leurs scores
        # Format: {taxon_id: {'dense_score': float, 'bm25_score': float, 'metadata': dict}}
        taxon_data = {}
        
        # ============================================================================
        # AJOUTER RÉSULTATS DENSE
        # ============================================================================
        for taxon_id, score, metadata in dense_results:
            if taxon_id not in taxon_data:
                taxon_data[taxon_id] = {
                    'dense_score': score,
                    'bm25_score': 0.0,
                    'metadata': metadata,
                    'is_exact_match': False
                }
            else:
                # ✅ FIX: Mise à jour du score ET des métadonnées
                taxon_data[taxon_id]['dense_score'] = max(taxon_data[taxon_id]['dense_score'], score)
                
                # ✅ Merger les métadonnées: prendre les plus complètes
                existing_meta = taxon_data[taxon_id]['metadata']
                if not existing_meta or len(metadata) > len(existing_meta):
                    taxon_data[taxon_id]['metadata'] = metadata
                elif metadata:
                    # Merger les champs manquants
                    for key, value in metadata.items():
                        if key not in existing_meta:
                            existing_meta[key] = value
        
        # ============================================================================
        # AJOUTER RÉSULTATS BM25
        # ============================================================================
        for taxon_id, score, metadata in bm25_results:
            # Appliquer boost exact match
            boosted_score = score
            if taxon_id in exact_matches:
                boosted_score *= self.config.bm25_exact_boost_factor
            
            if taxon_id not in taxon_data:
                taxon_data[taxon_id] = {
                    'dense_score': 0.0,
                    'bm25_score': boosted_score,
                    'metadata': metadata,
                    'is_exact_match': taxon_id in exact_matches
                }
            else:
                # ✅ FIX: Mise à jour du score ET des métadonnées
                taxon_data[taxon_id]['bm25_score'] = max(taxon_data[taxon_id]['bm25_score'], boosted_score)
                taxon_data[taxon_id]['is_exact_match'] = taxon_id in exact_matches
                
                # ✅ Merger les métadonnées: prendre les plus complètes
                existing_meta = taxon_data[taxon_id]['metadata']
                if not existing_meta or len(metadata) > len(existing_meta):
                    taxon_data[taxon_id]['metadata'] = metadata
                elif metadata:
                    # Merger les champs manquants
                    for key, value in metadata.items():
                        if key not in existing_meta:
                            existing_meta[key] = value
        
        # ✅ Calculer nombre de doublons
        duplicates_removed = len(dense_results) + len(bm25_results) - len(taxon_data)
        
        # ✅ Calculer score final selon la stratégie
        strategy = self.config.union_score_strategy
        
        for taxon_id, data in taxon_data.items():
            dense_score = data['dense_score']
            bm25_score = data['bm25_score']
            
            if strategy == "max":
                final_score = max(dense_score, bm25_score)
            elif strategy == "sum":
                final_score = dense_score + bm25_score
            elif strategy == "dense":
                final_score = dense_score if dense_score > 0 else bm25_score
            elif strategy == "bm25":
                final_score = bm25_score if bm25_score > 0 else dense_score
            else:
                final_score = max(dense_score, bm25_score)
            
            data['final_score'] = final_score
        
        # ✅ Appliquer boost contextuel
        extracted_params = context.get('extracted_params', {}) if context else {}
        if extracted_params:
            taxon_data = self._apply_contextual_boost_to_union(
                taxon_data,
                extracted_params
            )
        
        # ============================================================================
        # ✅ CRÉER CANDIDATS (avec validation des métadonnées)
        # ============================================================================
        candidates = []
        skipped = 0
        
        for taxon_id, data in taxon_data.items():
            metadata = data['metadata']
            
            # ✅ VALIDATION: Vérifier que metadata n'est pas vide
            if not metadata:
                logger.error(f"❌ Taxon {taxon_id}: metadata vide, SKIP")
                skipped += 1
                continue
            
            # Déterminer la source
            has_dense = data['dense_score'] > 0
            has_bm25 = data['bm25_score'] > 0
            
            if has_dense and has_bm25:
                source = "hybrid"
            elif has_dense:
                source = "dense"
            else:
                source = "bm25"
            
            minimal_metadata = {
                'domain': metadata.get('domain', ''),
                'depth': metadata.get('depth', 0),
                'source': source,
                'is_exact_match': data['is_exact_match'],
            }
            
            try:
                candidate = TaxonCandidate(
                    taxon_id=extract_uid_from_metadata(metadata),
                    name=metadata.get('name', 'Unknown'),
                    breadcrumb=metadata.get('breadcrumb', ''),
                    depth=metadata.get('depth', 0),
                    dense_score=data['dense_score'],
                    bm25_score=data['bm25_score'],
                    rrf_score=data['final_score'],
                    final_score=data['final_score'],
                    definition=metadata.get('definition', ''),
                    prereq_hint='',
                    metadata=minimal_metadata
                )
                candidates.append(candidate)
            except ValueError as e:
                logger.error(f"❌ Impossible de créer candidat pour {taxon_id}: {e}")
                logger.error(f"   Metadata disponible: {list(metadata.keys())}")
                skipped += 1
                continue
            
        # ✅ Trier par score final
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        
        logger.info(f"   • Stratégie union: {strategy}")
        logger.info(f"   • Taxons uniques: {len(candidates)}")
        logger.info(f"   • Doublons supprimés: {duplicates_removed}")
        if skipped > 0:
            logger.warning(f"   ⚠️ Candidats ignorés (metadata invalide): {skipped}")
        
        return candidates, duplicates_removed
    
    
    def _apply_contextual_boost_to_union(
        self,
        taxon_data: Dict[str, Dict],
        extracted_params: Dict[str, List[str]]
    ) -> Dict[str, Dict]:
        """
        ✅ Applique un boost contextuel aux scores finaux
        
        Args:
            taxon_data: {taxon_id: {'final_score': float, 'metadata': dict, ...}}
            extracted_params: Paramètres extraits du contexte
            
        Returns:
            taxon_data mis à jour avec scores boostés
        """
        
        for taxon_id, data in taxon_data.items():
            metadata = data['metadata']
            name = metadata.get('name', '').lower()
            breadcrumb = metadata.get('breadcrumb', '').lower()
            
            boost_factor = 1.0
            
            # Boost si forme juridique correspond
            if 'formes_juridiques' in extracted_params:
                for forme in extracted_params['formes_juridiques']:
                    if forme.lower() in name or forme.lower() in breadcrumb:
                        boost_factor *= 2.0
                        logger.info(f"🚀 Forme juridique boost: {taxon_id} ({forme})")
            
            # Boost si régime fiscal correspond
            if 'regimes_fiscaux' in extracted_params:
                for regime in extracted_params['regimes_fiscaux']:
                    if regime.lower() in name or regime.lower() in breadcrumb:
                        boost_factor *= 1.8
                        logger.info(f"🚀 Régime fiscal boost: {taxon_id} ({regime})")
            
            # Boost si domaine activité correspond
            if 'domaines_activite' in extracted_params:
                for domaine in extracted_params['domaines_activite']:
                    if domaine.lower() in name or domaine.lower() in breadcrumb:
                        boost_factor *= 1.5
                        logger.info(f"🚀 Domaine activité boost: {taxon_id} ({domaine})")
            
            # Appliquer le boost
            data['final_score'] *= boost_factor
        
        return taxon_data
    
    def validate_retrieval_results(results: List[Tuple], source: str) -> List[Tuple]:
        if not results:
            return results

        validated = []
        issues_found = 0

        for idx, result in enumerate(results):
            # Vérifier structure de base
            if not isinstance(result, tuple) or len(result) != 3:
                logger.error(f"❌ {source} result #{idx+1}: Format invalide (type: {type(result)}, len: {len(result) if isinstance(result, tuple) else 'N/A'})")
                continue
            
            taxon_id, score, metadata = result
            fixed = False

            # ✅ CORRECTION 1: Détecter inversion taxon_id <-> score
            if isinstance(taxon_id, (int, float)) and isinstance(score, str):
                logger.warning(f"⚠️ {source} #{idx+1}: INVERSION détectée - taxon_id={taxon_id} (float), score={score} (str)")
                logger.warning(f"   🔄 Correction: inversion des valeurs")
                taxon_id, score = score, taxon_id
                fixed = True
                issues_found += 1

            # ✅ CORRECTION 2: taxon_id n'est pas une string
            if not isinstance(taxon_id, str):
                logger.error(f"❌ {source} #{idx+1}: taxon_id n'est PAS une string!")
                logger.error(f"   Type: {type(taxon_id)}")
                logger.error(f"   Valeur: {taxon_id}")

                # Tenter conversion
                try:
                    original = taxon_id
                    taxon_id = str(taxon_id)
                    logger.warning(f"   🔄 Conversion forcée: {original} → '{taxon_id}'")
                    fixed = True
                    issues_found += 1
                except Exception as e:
                    logger.error(f"   ❌ Impossible de convertir: {e}")
                    continue
                
            # ✅ CORRECTION 3: score n'est pas numérique
            if not isinstance(score, (int, float)):
                logger.error(f"❌ {source} #{idx+1}: score n'est PAS numérique (type: {type(score)}, valeur: {score})")

                try:
                    score = float(score)
                    logger.warning(f"   🔄 Conversion score en float: {score}")
                    fixed = True
                    issues_found += 1
                except:
                    logger.error(f"   ❌ Impossible de convertir score, utilisation de 0.0")
                    score = 0.0
                    fixed = True
                    issues_found += 1

            # ✅ CORRECTION 4: metadata n'est pas un dict
            if not isinstance(metadata, dict):
                logger.error(f"❌ {source} #{idx+1}: metadata n'est PAS un dict (type: {type(metadata)})")
                logger.warning(f"   🔄 Création d'un dict vide")
                metadata = {}
                fixed = True
                issues_found += 1

            if fixed:
                logger.info(f"   ✅ Résultat corrigé: taxon_id='{taxon_id}', score={score}")

            validated.append((taxon_id, float(score), metadata))

        # Résumé
        if issues_found > 0:
            logger.warning(f"⚠️ {source}: {issues_found} problème(s) corrigé(s) sur {len(results)} résultats")
            logger.warning(f"   Résultats valides: {len(validated)}/{len(results)}")
        else:
            logger.debug(f"✅ {source}: Tous les résultats sont valides ({len(results)})")

        return validated
    
    
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
            candidate.final_score = candidate.final_score * (1.0 + boost)
        
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        return candidates
    
    
    def _log_summary(self, result: RetrievalResult):
        """Log summary"""
        logger.info(f"\n📊 RETRIEVAL SUMMARY (UNION MODE)")
        logger.info(f"Original query: '{result.query_text}'")
        if result.enriched_query != result.query_text:
            logger.info(f"Enriched query: '{result.enriched_query}'")
        logger.info(f"Total candidates: {result.total_retrieved}")
        logger.info(f"  • Dense: {result.dense_count}")
        logger.info(f"  • BM25: {result.bm25_count}")
        logger.info(f"  • Duplicates removed: {result.duplicates_removed}")
        logger.info(f"  • Final TopN: {len(result.candidates)}")
        logger.info(f"Top Scores: Dense={result.dense_top_score:.4f}, BM25={result.bm25_top_score:.4f}, Union={result.union_top_score:.4f}")
        
        # Afficher top-3 avec détails
        if result.candidates:
            logger.info(f"\nTop 3 candidates:")
            for i, cand in enumerate(result.candidates[:3], 1):
                exact_marker = "🎯" if cand.metadata.get('is_exact_match') else ""
                logger.info(f"  {i}. {exact_marker} {cand.name}")
                logger.info(f"     Score: {cand.final_score:.4f} | Dense: {cand.dense_score:.4f} | BM25: {cand.bm25_score:.4f}")
                logger.info(f"     Source: {cand.metadata.get('source')} | Depth: {cand.depth}")
        
        logger.info(f"Time: {result.total_time_ms:.2f}ms\n")