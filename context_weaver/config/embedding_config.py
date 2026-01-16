#!/usr/bin/env python
# -*- coding: utf-8 -*-
#config/embedding_config.py
"""
Configuration pour recherche vectorielle (Embeddings + FAISS)
"""

import os
from pathlib import Path

class EmbeddingConfig:
    """Configuration pour recherche par embeddings"""
    MODEL_NAME = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    VECTOR_DIM = 768
    
    # ============================================================
    # CHEMINS DE STOCKAGE
    # ============================================================
    
    # Chemin du store FAISS (index vectoriel)
    FAISS_INDEX_PATH = Path(os.getenv(
        "FAISS_INDEX_DIR",
        "./data/indexes/faiss"
    ))
    
    # Cache pour les modèles téléchargés
    CACHE_DIR = Path(os.getenv(
        "EMBEDDING_CACHE_DIR",
        "./data/cache/embeddings"
    ))
    
    INDEX_TYPE = "Flat"
    
    # Paramètres pour IVF (si INDEX_TYPE = "IVF")
    N_CLUSTERS = 100
    N_PROBES = 10
    
    HNSW_M = 32
    HNSW_EF_CONSTRUCTION = 40
    HNSW_EF_SEARCH = 16
    
    TOP_K = 50

    MIN_SIMILARITY = 0.3
    
    NORMALIZE_EMBEDDINGS = True
    

    BATCH_SIZE = 32
    
    # Options: "cpu", "cuda", "mps" (Mac M1/M2)
    DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
    
    # Utiliser le cache disque pour les embeddings calculés
    USE_CACHE = True
    
    # Nombre de threads pour FAISS (0 = auto)
    FAISS_NUM_THREADS = 0
    
    # ============================================================
    # OPTIONS AVANCÉES
    # ============================================================
    
    # Pooling strategy pour les embeddings
    # Options: "mean", "max", "cls"
    POOLING_STRATEGY = "mean"
    
    # Quantization pour réduire la taille (EXPÉRIMENTAL)
    # None, "int8", "binary"
    QUANTIZATION = None
    
    # Distance metric
    # Options: "cosine", "euclidean", "dot_product"
    DISTANCE_METRIC = "cosine"
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    @staticmethod
    def get_faiss_index_path() -> Path:
        """
        Retourne le chemin de l'index FAISS
        Crée le répertoire si nécessaire
        """
        EmbeddingConfig.FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        return EmbeddingConfig.FAISS_INDEX_PATH / "vector_store.index"
    
    @staticmethod
    def get_metadata_path() -> Path:
        """
        Retourne le chemin du fichier métadonnées
        Contient les infos associées aux vecteurs
        """
        EmbeddingConfig.FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        return EmbeddingConfig.FAISS_INDEX_PATH / "metadata.json"
    
    @staticmethod
    def get_cache_path() -> Path:
        """
        Retourne le chemin du cache
        Pour stocker les modèles téléchargés
        """
        if EmbeddingConfig.USE_CACHE:
            EmbeddingConfig.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            return EmbeddingConfig.CACHE_DIR
        return None
    
    @staticmethod
    def get_model_info() -> dict:
        """Retourne les informations du modèle"""
        return {
            "name": EmbeddingConfig.MODEL_NAME,
            "dimension": EmbeddingConfig.VECTOR_DIM,
            "device": EmbeddingConfig.DEVICE,
            "index_type": EmbeddingConfig.INDEX_TYPE,
            "normalized": EmbeddingConfig.NORMALIZE_EMBEDDINGS
        }
    
    @staticmethod
    def validate_config():
        """Valide la configuration"""
        errors = []
        
        # Vérifier la dimension
        if EmbeddingConfig.VECTOR_DIM <= 0:
            errors.append("VECTOR_DIM doit être > 0")
        
        # Vérifier le device
        if EmbeddingConfig.DEVICE not in ["cpu", "cuda", "mps"]:
            errors.append(f"Device invalide: {EmbeddingConfig.DEVICE}")
        
        # Vérifier TOP_K
        if EmbeddingConfig.TOP_K <= 0:
            errors.append("TOP_K doit être > 0")
        
        # Vérifier MIN_SIMILARITY
        if not 0 <= EmbeddingConfig.MIN_SIMILARITY <= 1:
            errors.append("MIN_SIMILARITY doit être entre 0 et 1")
        
        # Vérifier INDEX_TYPE
        valid_types = ["Flat", "IVF", "HNSW"]
        if EmbeddingConfig.INDEX_TYPE not in valid_types:
            errors.append(f"INDEX_TYPE invalide. Options: {valid_types}")
        
        if errors:
            raise ValueError("Erreurs de configuration:\n" + "\n".join(errors))
        
        return True