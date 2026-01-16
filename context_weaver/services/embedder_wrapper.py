#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Embedder Wrapper - Adapter pour EmbeddingSearch
✅ Fournit une interface .encode() pour TaxonomyRetriever
✅ Retourne toujours np.float32 pour compatibilité FAISS
"""

import logging
import numpy as np
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbedderWrapper:
    """
    Wrapper qui adapte EmbeddingSearch pour TaxonomyRetriever
    
    TaxonomyRetriever attend:
    - embedder.encode(text) -> np.ndarray (float32)
    """
    
    def __init__(self, embedding_search=None, oss_client=None):
        """
        Args:
            embedding_search: Instance EmbeddingSearch (optionnel)
            oss_client: Instance OSSClassifierClient (optionnel)
        """
        self.embedding_search = embedding_search
        self.oss_client = oss_client
        
        # Déterminer quelle méthode utiliser
        if self.oss_client:
            self._encode_method = self._encode_via_oss
            logger.info("EmbedderWrapper: Utilise OSSClassifierClient")
        elif self.embedding_search:
            self._encode_method = self._encode_via_embedding_search
            logger.info("EmbedderWrapper: Utilise EmbeddingSearch")
        else:
            raise ValueError("Au moins un de embedding_search ou oss_client doit être fourni")
    
    
    def encode(self, text: str, normalize: bool = False) -> np.ndarray:
        """
        Interface standard pour TaxonomyRetriever
        
        Args:
            text: Texte à encoder
            normalize: Normaliser le vecteur (optionnel)
            
        Returns:
            np.ndarray de shape (dim,) dtype=float32
        """
        # Obtenir embedding
        embedding = self._encode_method(text)
        
        # 🔥 CRITIQUE: Convertir en numpy array float32
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        elif isinstance(embedding, np.ndarray):
            if embedding.dtype != np.float32:
                embedding = embedding.astype(np.float32)
        else:
            raise TypeError(f"Type d'embedding non supporté: {type(embedding)}")
        
        # S'assurer que c'est 1D
        if embedding.ndim > 1:
            embedding = embedding.flatten()
        
        # Normaliser si demandé
        if normalize:
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
        
        return embedding
    
    
    def _encode_via_oss(self, text: str) -> List[float]:
        """Encode via OSSClassifierClient"""
        try:
            return self.oss_client.generate_embeddings(text)
        except Exception as e:
            logger.error(f"Erreur encode via OSS: {e}")
            raise
    
    
    def _encode_via_embedding_search(self, text: str) -> List[float]:
        """Encode via EmbeddingSearch"""
        try:
            # Tester différentes méthodes possibles
            if hasattr(self.embedding_search, 'generate_embeddings'):
                return self.embedding_search.generate_embeddings(text)
            elif hasattr(self.embedding_search, 'embed'):
                return self.embedding_search.embed(text)
            elif hasattr(self.embedding_search, 'encode'):
                return self.embedding_search.encode(text)
            else:
                raise AttributeError(
                    "EmbeddingSearch n'a ni 'generate_embeddings', ni 'embed', ni 'encode'"
                )
        except Exception as e:
            logger.error(f"Erreur encode via EmbeddingSearch: {e}")
            raise
    
    
    def batch_encode(
        self, 
        texts: List[str], 
        normalize: bool = False
    ) -> np.ndarray:
        """
        Encode un batch de textes
        
        Args:
            texts: Liste de textes
            normalize: Normaliser les vecteurs
            
        Returns:
            np.ndarray de shape (len(texts), dim) dtype=float32
        """
        embeddings = []
        
        for text in texts:
            emb = self.encode(text, normalize=normalize)
            embeddings.append(emb)
        
        return np.array(embeddings, dtype=np.float32)
    
    
    @property
    def model_name(self) -> str:
        """Retourne le nom du modèle (pour logging)"""
        if self.oss_client:
            return "oss-20b"
        elif self.embedding_search:
            return getattr(self.embedding_search, 'model_name', 'embedding_search')
        return "unknown"


# ============================================================================
# FACTORY
# ============================================================================

def create_embedder_for_taxonomy(
    embedding_search=None,
    oss_client=None
) -> EmbedderWrapper:
    """
    Factory pour créer un embedder compatible TaxonomyRetriever
    
    Args:
        embedding_search: Instance EmbeddingSearch (optionnel)
        oss_client: Instance OSSClassifierClient (optionnel)
        
    Returns:
        EmbedderWrapper configuré
    """
    return EmbedderWrapper(
        embedding_search=embedding_search,
        oss_client=oss_client
    )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Exemple avec OSSClassifierClient
    from context_weaver.services.oss_classifier import OSSClassifierClient
    
    oss_client = OSSClassifierClient()
    embedder = EmbedderWrapper(oss_client=oss_client)
    
    # Test encode
    text = "Test embedding"
    embedding = embedder.encode(text)
    
    print(f"✅ Embedding shape: {embedding.shape}")
    print(f"✅ Embedding dtype: {embedding.dtype}")
    print(f"✅ Model: {embedder.model_name}")
    
    # Vérifier que c'est float32
    assert embedding.dtype == np.float32, f"Expected float32, got {embedding.dtype}"
    
    # Test normalize
    embedding_norm = embedder.encode(text, normalize=True)
    print(f"✅ Normalized norm: {np.linalg.norm(embedding_norm):.4f}")
    
    print("\n✅ Tous les tests passent!")