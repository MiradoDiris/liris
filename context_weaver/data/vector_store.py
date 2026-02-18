#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VectorStore - VERSION COMPLÈTE avec BM25 optionnel
✅ Retourne (distances, metadata_list)
✅ Support BM25 via rank_bm25
✅ Gestion robuste des types
✅ Méthode get_document_count() ajoutée
"""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """
    VectorStore FAISS + BM25 optionnel
    """
    
    def __init__(self, index_path: Path = None):
        self.index_path = index_path or Path("data/indexes/faiss/vector_store.index")
        self.metadata_path = self.index_path.parent / "metadata.pkl"
        self.bm25_path = self.index_path.parent / "bm25_index.pkl"
        
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self.dimension = 768
        
        # BM25 (optionnel)
        self.bm25_index = None
        self.bm25_available = False
    
    
    def initialize(self):
        """Charge l'index FAISS et métadonnées"""
        if self.index_path.exists():
            logger.info(f"📂 Chargement vector store: {self.index_path}")
            self.index = faiss.read_index(str(self.index_path))
            
            # Charger metadata
            if self.metadata_path.exists():
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
            
            logger.info(f"✅ Vector store chargé: {self.index.ntotal} vecteurs")
        else:
            logger.warning(f"⚠️ Index non trouvé: {self.index_path}")
            self._create_empty_index()
        
        # Tenter de charger BM25
        self._load_bm25_index()
    
    
    def _create_empty_index(self):
        """Crée un index vide"""
        self.index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"✅ Index vide créé (dim={self.dimension})")
    
    
    def _load_bm25_index(self):
        """Charge l'index BM25 si disponible"""
        try:
            import rank_bm25
            
            if self.bm25_path.exists():
                with open(self.bm25_path, 'rb') as f:
                    bm25_data = pickle.load(f)
                    self.bm25_index = bm25_data['index']
                    self.bm25_corpus = bm25_data.get('corpus', [])
                
                self.bm25_available = True
                logger.info(f"✅ BM25 index chargé: {len(self.bm25_corpus)} documents")
            else:
                logger.info("ℹ️ BM25 index non trouvé (optionnel)")
        
        except ImportError:
            logger.info("ℹ️ rank-bm25 non installé (BM25 désactivé)")
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement BM25: {e}")
    
    
    def get_document_count(self) -> int:
        """
        ✅ NOUVEAU: Retourne le nombre de documents dans le VectorStore
        
        Returns:
            int: Nombre de vecteurs/documents
        """
        if self.index is None:
            return 0
        return self.index.ntotal
    
    
    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """
        ✅ CORRIGÉ: Retourne (distances, metadata_list)
        
        Returns:
            Tuple[List[float], List[Dict[str, Any]]]:
                - distances: Scores/distances
                - metadata_list: Métadonnées correspondantes
        """
        
        if self.index is None or self.index.ntotal == 0:
            logger.warning("⚠️ Index vide")
            return [], []
        
        # Conversion en float32
        if not isinstance(query_vector, np.ndarray):
            query_vector = np.array(query_vector, dtype=np.float32)
        elif query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)
        
        # Reshape si nécessaire
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # Contiguous
        if not query_vector.flags['C_CONTIGUOUS']:
            query_vector = np.ascontiguousarray(query_vector)
        
        # Normaliser pour cosine similarity
        faiss.normalize_L2(query_vector)
        
        # Search FAISS
        if filter_fn is None:
            # Pas de filtre
            distances, indices = self.index.search(query_vector, k)
            
            distances = distances[0].tolist()
            indices = indices[0].tolist()
            
            metadata_list = [
                self.metadata[idx] 
                for idx in indices 
                if 0 <= idx < len(self.metadata)
            ]
            
            return distances, metadata_list
        
        else:
            # Avec filtre: recherche élargie
            search_k = min(k * 5, self.index.ntotal)
            distances, indices = self.index.search(query_vector, search_k)
            
            distances = distances[0].tolist()
            indices = indices[0].tolist()
            
            filtered_distances = []
            filtered_metadata = []
            
            for dist, idx in zip(distances, indices):
                if 0 <= idx < len(self.metadata):
                    meta = self.metadata[idx]
                    if filter_fn(meta):
                        filtered_distances.append(dist)
                        filtered_metadata.append(meta)
                        
                        if len(filtered_metadata) >= k:
                            break
            
            return filtered_distances, filtered_metadata
    
    
    def bm25_search(
        self,
        query: str,
        top_k: int = 10,
        domain: Optional[str] = None
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """
        ✅ NOUVEAU: Recherche BM25
        
        Returns:
            Tuple[List[float], List[Dict[str, Any]]]:
                - scores: Scores BM25
                - metadata_list: Métadonnées correspondantes
        """
        
        if not self.bm25_available or self.bm25_index is None:
            logger.warning("⚠️ BM25 non disponible")
            return [], []
        
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            
            # BM25 scores
            scores = self.bm25_index.get_scores(tokenized_query)
            
            # Trier par score
            ranked_indices = np.argsort(scores)[::-1][:top_k]
            
            # Filtrer par domaine si nécessaire
            results_distances = []
            results_metadata = []
            
            for idx in ranked_indices:
                if idx >= len(self.metadata):
                    continue
                
                score = float(scores[idx])
                metadata = self.metadata[idx]
                
                # Filtre domaine
                if domain and metadata.get('domain') != domain:
                    continue
                
                results_distances.append(score)
                results_metadata.append(metadata)
                
                if len(results_metadata) >= top_k:
                    break
            
            logger.info(f"✅ BM25: {len(results_metadata)} résultats")
            return results_distances, results_metadata
        
        except Exception as e:
            logger.error(f"❌ BM25 search error: {e}")
            return [], []
    
    
    def add_vectors(
        self,
        vectors: np.ndarray,
        metadata_list: List[Dict[str, Any]]
    ):
        """Ajoute des vecteurs et leurs métadonnées"""
        
        if vectors.shape[0] != len(metadata_list):
            raise ValueError(f"Mismatch: {vectors.shape[0]} vectors vs {len(metadata_list)} metadata")
        
        # Normaliser pour cosine similarity
        faiss.normalize_L2(vectors)
        
        # Ajouter à l'index
        self.index.add(vectors)
        
        # Ajouter metadata
        self.metadata.extend(metadata_list)
        
        logger.info(f"✅ {len(metadata_list)} vecteurs ajoutés (total: {self.index.ntotal})")
    
    
    def build_bm25_index(self):
        """
        ✅ NOUVEAU: Construit l'index BM25 à partir des métadonnées
        """
        try:
            from rank_bm25 import BM25Okapi
            
            # Construire corpus
            corpus = []
            for meta in self.metadata:
                # Combiner les champs textuels
                text_parts = [
                    meta.get('name', ''),
                    meta.get('definition', ''),
                    meta.get('description', ''),
                    meta.get('content', '')
                ]
                combined = ' '.join(filter(None, text_parts))
                
                # Tokenize
                tokens = combined.lower().split()
                corpus.append(tokens)
            
            # Créer index BM25
            self.bm25_index = BM25Okapi(corpus)
            self.bm25_corpus = corpus
            self.bm25_available = True
            
            logger.info(f"✅ BM25 index construit: {len(corpus)} documents")
            
            # Sauvegarder
            self._save_bm25_index()
            
        except ImportError:
            logger.warning("⚠️ rank-bm25 non installé, BM25 désactivé")
        except Exception as e:
            logger.error(f"❌ Erreur construction BM25: {e}")
    
    
    def _save_bm25_index(self):
        """Sauvegarde l'index BM25"""
        if not self.bm25_available:
            return
        
        try:
            self.bm25_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.bm25_path, 'wb') as f:
                pickle.dump({
                    'index': self.bm25_index,
                    'corpus': self.bm25_corpus
                }, f)
            
            logger.info(f"✅ BM25 index sauvegardé: {self.bm25_path}")
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde BM25: {e}")
    
    
    def save(self):
        """Sauvegarde l'index FAISS et les métadonnées"""
        
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder index FAISS
        faiss.write_index(self.index, str(self.index_path))
        
        # Sauvegarder metadata
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        
        logger.info(f"✅ Vector store sauvegardé: {self.index_path}")
        
        # Construire BM25 si pas encore fait
        if not self.bm25_available and len(self.metadata) > 0:
            self.build_bm25_index()
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques"""
        return {
            'num_vectors': self.index.ntotal if self.index else 0,
            'num_metadata': len(self.metadata),
            'dimension': self.dimension,
            'index_path': str(self.index_path),
            'bm25_available': self.bm25_available,
            'bm25_corpus_size': len(self.bm25_corpus) if self.bm25_available else 0
        }
    
    
    def clear(self):
        """Vide l'index"""
        self._create_empty_index()
        self.metadata = []
        self.bm25_index = None
        self.bm25_corpus = []
        self.bm25_available = False
        logger.info("✅ Index vidé")


# ============================================================================
# INSTALLATION BM25
# ============================================================================

def install_bm25_requirements():
    """
    Helper pour installer rank-bm25
    
    Usage:
        pip install rank-bm25
    """
    print("Pour activer BM25, installer:")
    print("  pip install rank-bm25")