#!/usr/bin/env python
# -*- coding: utf-8 -*-
# config/hybrid_config.py
"""
Configuration pour la fusion hybride (BM25 + Embeddings)
Implémente Reciprocal Rank Fusion (RRF) et autres stratégies
"""

import os

class HybridConfig:
    """Configuration pour fusion hybride des résultats de recherche"""
    
    # ============================================================
    # MÉTHODE DE FUSION
    # ============================================================
    
    # Méthode de fusion à utiliser
    # Options:
    # - "rrf": Reciprocal Rank Fusion (recommandé, état de l'art)
    # - "weighted": Moyenne pondérée des scores
    # - "cascade": BM25 d'abord, puis embeddings si insuffisant
    FUSION_METHOD = os.getenv("FUSION_METHOD", "rrf")
    
    # ============================================================
    # PARAMÈTRES RRF (Reciprocal Rank Fusion)
    # ============================================================
    
    # Constante k pour RRF
    # Formula: score = sum(1 / (k + rank))
    # Valeurs typiques:
    # - 60: standard (valeur par défaut dans la littérature)
    # - 30: favorise les premiers résultats
    # - 100: plus de poids aux résultats éloignés
    RRF_K = 60
    
    # ============================================================
    # PARAMÈTRES WEIGHTED FUSION
    # ============================================================
    
    # Poids pour BM25 (si FUSION_METHOD = "weighted")
    # Range: 0.0 à 1.0
    # Plus élevé = plus d'importance à BM25
    BM25_WEIGHT = 0.6
    
    # Poids pour embeddings (doit satisfaire: BM25_WEIGHT + EMBEDDING_WEIGHT = 1.0)
    EMBEDDING_WEIGHT = 0.4
    
    # ============================================================
    # PARAMÈTRES CASCADE FUSION
    # ============================================================
    
    # Nombre minimum de résultats BM25 avant d'utiliser embeddings
    # (si FUSION_METHOD = "cascade")
    CASCADE_MIN_RESULTS = 5
    
    # Score minimum BM25 pour considérer le résultat suffisant
    CASCADE_MIN_BM25_SCORE = 0.3
    
    # ============================================================
    # FILTRAGE DES RÉSULTATS
    # ============================================================
    
    # Score minimum BM25 pour inclusion dans la fusion
    # Résultats en dessous seront exclus
    MIN_BM25_SCORE = 0.1
    
    # Score minimum embeddings pour inclusion (cosine similarity)
    MIN_EMBEDDING_SCORE = 0.5
    
    # Nombre maximum de résultats après fusion
    FINAL_TOP_K = 10
    
    # ============================================================
    # DÉDUPLICATION
    # ============================================================
    
    # Activer la déduplication des résultats
    # Élimine les documents apparaissant dans les deux sources
    DEDUPLICATE = True
    
    # Seuil de similarité pour détecter les doublons
    # Basé sur la similarité du contenu (0.0 - 1.0)
    # 0.95 = quasi-identiques
    # 0.85 = très similaires
    # 0.70 = similaires
    SIMILARITY_THRESHOLD = 0.95
    
    # Stratégie de déduplication
    # Options:
    # - "id": Basé uniquement sur l'ID
    # - "content": Basé sur la similarité du contenu
    # - "both": Combinaison des deux
    DEDUP_STRATEGY = "id"
    
    # ============================================================
    # DIVERSITÉ DES RÉSULTATS
    # ============================================================
    
    # Assurer la diversité des résultats finaux
    ENSURE_DIVERSITY = True
    
    # Nombre maximum de résultats par domaine
    # Évite qu'un seul domaine domine les résultats
    MAX_RESULTS_PER_DOMAIN = 3
    
    # Nombre maximum de résultats par type
    # (decision_tree, rule, template, etc.)
    MAX_RESULTS_PER_TYPE = 4
    
    # Pénalité pour résultats trop similaires
    # Réduit le score des résultats redondants
    DIVERSITY_PENALTY = 0.2  # 20% de réduction
    
    # ============================================================
    # RE-RANKING (OPTIONNEL)
    # ============================================================
    
    # Activer le re-ranking avec un modèle cross-encoder
    # Plus précis mais plus lent
    USE_RERANKING = False
    
    # Modèle de re-ranking (si USE_RERANKING = True)
    # Options populaires:
    # - cross-encoder/ms-marco-MiniLM-L-6-v2 (rapide)
    # - cross-encoder/ms-marco-electra-base (précis)
    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Nombre de résultats à re-ranker
    # Re-ranker seulement les top résultats (coûteux)
    RERANK_TOP_K = 20
    
    # ============================================================
    # SCORE NORMALIZATION
    # ============================================================
    
    # Normaliser les scores avant fusion
    # Utile si BM25 et embeddings ont des échelles différentes
    NORMALIZE_SCORES = True
    
    # Méthode de normalisation
    # Options:
    # - "minmax": (x - min) / (max - min)
    # - "zscore": (x - mean) / std
    # - "sigmoid": 1 / (1 + exp(-x))
    NORMALIZATION_METHOD = "minmax"
    
    # ============================================================
    # BOOSTING PAR CONTEXTE
    # ============================================================
    
    # Booster les résultats correspondant au domaine de la requête
    BOOST_DOMAIN_MATCH = True
    DOMAIN_BOOST_FACTOR = 1.2  # +20% de score
    
    # Booster les résultats avec variables correspondantes
    BOOST_VARIABLE_MATCH = True
    VARIABLE_BOOST_FACTOR = 1.15  # +15% de score
    
    # Pénaliser les résultats hors contexte
    PENALIZE_OFF_CONTEXT = True
    OFF_CONTEXT_PENALTY = 0.8  # -20% de score
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    @staticmethod
    def compute_rrf_score(rank: int, k: int = None) -> float:
        """
        Calcule le score RRF pour un rang donné
        
        Formula: score = 1 / (k + rank)
        
        Args:
            rank: Position dans le classement (1-indexed)
            k: Constante RRF (défaut: RRF_K)
            
        Returns:
            Score RRF (float)
        """
        k = k or HybridConfig.RRF_K
        return 1.0 / (k + rank)
    
    @staticmethod
    def compute_weighted_score(
        bm25_score: float,
        embedding_score: float,
        bm25_weight: float = None,
        embedding_weight: float = None
    ) -> float:
        """
        Calcule le score pondéré combiné
        
        Args:
            bm25_score: Score BM25
            embedding_score: Score embedding
            bm25_weight: Poids BM25 (défaut: BM25_WEIGHT)
            embedding_weight: Poids embedding (défaut: EMBEDDING_WEIGHT)
            
        Returns:
            Score combiné (float)
        """
        bm25_w = bm25_weight or HybridConfig.BM25_WEIGHT
        embed_w = embedding_weight or HybridConfig.EMBEDDING_WEIGHT
        
        return (bm25_w * bm25_score) + (embed_w * embedding_score)
    
    @staticmethod
    def should_filter_result(score: float, method: str) -> bool:
        """
        Détermine si un résultat doit être filtré
        
        Args:
            score: Score du résultat
            method: "bm25" ou "embedding"
            
        Returns:
            True si le résultat doit être filtré
        """
        if method == "bm25":
            return score < HybridConfig.MIN_BM25_SCORE
        elif method == "embedding":
            return score < HybridConfig.MIN_EMBEDDING_SCORE
        return False
    
    @staticmethod
    def normalize_score(score: float, min_val: float, max_val: float) -> float:
        """
        Normalise un score selon la méthode configurée
        
        Args:
            score: Score à normaliser
            min_val: Valeur minimum observée
            max_val: Valeur maximum observée
            
        Returns:
            Score normalisé (0.0 - 1.0)
        """
        if HybridConfig.NORMALIZATION_METHOD == "minmax":
            if max_val == min_val:
                return 1.0
            return (score - min_val) / (max_val - min_val)
        
        elif HybridConfig.NORMALIZATION_METHOD == "sigmoid":
            import math
            return 1.0 / (1.0 + math.exp(-score))
        
        # zscore nécessite mean et std
        return score
    
    @staticmethod
    def validate_config():
        """Valide la configuration"""
        errors = []
        
        # Vérifier la méthode de fusion
        valid_methods = ["rrf", "weighted", "cascade"]
        if HybridConfig.FUSION_METHOD not in valid_methods:
            errors.append(f"FUSION_METHOD invalide. Options: {valid_methods}")
        
        # Vérifier les poids pour weighted
        if HybridConfig.FUSION_METHOD == "weighted":
            total_weight = HybridConfig.BM25_WEIGHT + HybridConfig.EMBEDDING_WEIGHT
            if abs(total_weight - 1.0) > 0.001:
                errors.append(f"BM25_WEIGHT + EMBEDDING_WEIGHT doit = 1.0 (actuel: {total_weight})")
        
        # Vérifier RRF_K
        if HybridConfig.RRF_K <= 0:
            errors.append("RRF_K doit être > 0")
        
        # Vérifier FINAL_TOP_K
        if HybridConfig.FINAL_TOP_K <= 0:
            errors.append("FINAL_TOP_K doit être > 0")
        
        # Vérifier les seuils
        if not 0 <= HybridConfig.MIN_BM25_SCORE <= 1:
            errors.append("MIN_BM25_SCORE doit être entre 0 et 1")
        
        if not 0 <= HybridConfig.MIN_EMBEDDING_SCORE <= 1:
            errors.append("MIN_EMBEDDING_SCORE doit être entre 0 et 1")
        
        if errors:
            raise ValueError("Erreurs de configuration:\n" + "\n".join(errors))
        
        return True
    
    @staticmethod
    def get_config_summary() -> dict:
        """Retourne un résumé de la configuration"""
        return {
            "fusion_method": HybridConfig.FUSION_METHOD,
            "rrf_k": HybridConfig.RRF_K,
            "bm25_weight": HybridConfig.BM25_WEIGHT,
            "embedding_weight": HybridConfig.EMBEDDING_WEIGHT,
            "final_top_k": HybridConfig.FINAL_TOP_K,
            "deduplicate": HybridConfig.DEDUPLICATE,
            "ensure_diversity": HybridConfig.ENSURE_DIVERSITY,
            "use_reranking": HybridConfig.USE_RERANKING
        }