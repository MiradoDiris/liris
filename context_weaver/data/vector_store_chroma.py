#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VectorStore - VERSION CHROMADB (PYQT5 FIX - LAZY LOADING)
✅ Timeout sur collection.query()
✅ Gestion d'erreur maximale
✅ Fallback graceful
✅ LAZY CACHE LOADING pour éviter le blocage PyQt5
"""

import chromadb
from chromadb.config import Settings
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import logging
import threading
import time

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Exception pour timeout"""
    pass


def run_with_timeout(func, timeout_seconds=10):
    """
    Exécute une fonction avec timeout (compatible Windows/PyQt5)
    """
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        raise TimeoutException(f"Function timed out after {timeout_seconds}s")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]


class VectorStore:
    """
    VectorStore ChromaDB + BM25 (PYQT5 FIX - LAZY LOADING)
    
    ✅ CHANGEMENT MAJEUR:
    Le cache de métadonnées n'est PAS chargé à l'initialisation
    pour éviter les blocages PyQt5. Il est chargé à la demande.
    """
    
    def __init__(self, persist_path: Path = None):
        self.persist_path = persist_path or Path("data/indexes/chroma")
        self.bm25_path = self.persist_path / "bm25_index.pkl"
        
        self.client = None
        self.collection = None
        self.dimension = 768
        
        # BM25 (optionnel)
        self.bm25_index = None
        self.bm25_available = False
        
        # Cache pour les métadonnées
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_loaded = False  # ✅ NOUVEAU FLAG
        self._cache_loading = False  # Pour éviter les loads concurrents
        
        # Timeout pour ChromaDB
        self.chromadb_timeout = 30  # secondes
        self.cache_timeout = 5  # timeout spécial pour cache
    
    
    def initialize(self):
        """
        Initialise ChromaDB - VERSION RÉELLE
        Pas de mock, pas de simulation
        """
        logger.info(f"📂 Initialisation ChromaDB: {self.persist_path}")
        
        # Créer le dossier RÉEL
        self.persist_path.mkdir(parents=True, exist_ok=True)
        logger.info("   ✅ Dossier créé/vérifié")
        
        # Créer le client ChromaDB RÉEL
        logger.info("   🔧 Création du client ChromaDB...")
        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=Settings(
                anonymized_telemetry=False,  # Désactivation RÉELLE
                allow_reset=True,
                is_persistent=True
            )
        )
        logger.info("   ✅ Client ChromaDB créé")
        
        # Charger la collection RÉELLE
        logger.info("   📋 Chargement de la collection...")
        try:
            self.collection = self.client.get_collection(
                name="context_weaver",
                embedding_function=None
            )
            doc_count = self.collection.count()
            logger.info(f"   ✅ Collection existante chargée: {doc_count} documents")
        except:
            self.collection = self.client.create_collection(
                name="context_weaver",
                embedding_function=None,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("   ✅ Nouvelle collection créée")
        
        # Charger BM25 RÉEL
        self._load_bm25_index()
        
        logger.info("✅ VectorStore initialized (lazy cache mode)")
    
    
    def _load_metadata_cache(self):
        """
        ✅ FIX: Charge les métadonnées UNIQUEMENT si demandé (lazy loading)
        Appelé automatiquement au premier besoin
        """
        if self._cache_loaded:
            return  # Déjà chargé
        
        if self._cache_loading:
            logger.debug("Cache loading already in progress, skipping...")
            return
        
        self._cache_loading = True
        
        try:
            logger.info("📦 Loading metadata cache on-demand...")
            
            if self.collection.count() > 0:
                # ✅ TIMEOUT PROTECTION
                def load_cache():
                    return self.collection.get(include=['metadatas'])
                
                try:
                    results = run_with_timeout(load_cache, timeout_seconds=self.cache_timeout)
                    
                    for doc_id, metadata in zip(results['ids'], results['metadatas']):
                        self.metadata_cache[doc_id] = metadata
                    
                    logger.info(f"✅ Cache métadonnées: {len(self.metadata_cache)} documents")
                    self._cache_loaded = True
                    
                except TimeoutException:
                    logger.warning(f"⚠️ Cache loading timeout après {self.cache_timeout}s")
                    logger.warning("   → Continuant sans cache (métadonnées récupérées à la volée)")
                    self._cache_loaded = False
                    
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement cache: {e}")
            self._cache_loaded = False
        finally:
            self._cache_loading = False
    
    
    def _load_bm25_index(self):
        """Charge l'index BM25 si disponible"""
        try:
            import rank_bm25
            
            if self.bm25_path.exists():
                with open(self.bm25_path, 'rb') as f:
                    bm25_data = pickle.load(f)
                
                self.bm25_index = bm25_data['index']
                self.bm25_ids = bm25_data['ids']
                self.bm25_available = True
                
                logger.info(f"✅ BM25 index chargé: {len(self.bm25_ids)} documents")
            else:
                logger.info("ℹ️ Pas d'index BM25")
        except ImportError:
            logger.warning("⚠️ rank_bm25 non installé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement BM25: {e}")
    
    
    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        where: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[str], List[float], List[Dict[str, Any]]]:
        """
        ✅ Recherche avec TIMEOUT et LAZY CACHE LOADING

        Returns:
            (ids, similarities, metadatas)
        """

        # ✅ FIX: Charger le cache si nécessaire ET si on a un filtre
        if not self._cache_loaded and (filter_fn is not None or where is not None):
            logger.info("🔄 Lazy loading cache for filtering...")
            self._load_metadata_cache()

        if self.collection is None or self.collection.count() == 0:
            logger.warning("⚠️ Collection vide")
            return [], [], []  # ← 3 éléments vides

        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()

        collection_count = self.collection.count()

        logger.info(f"🔍 ChromaDB search:")
        logger.info(f"   k={k}, collection_size={collection_count}")
        logger.info(f"   filter_fn={'SET' if filter_fn else 'None'}")
        logger.info(f"   where={where}")
        logger.info(f"   cache_loaded={self._cache_loaded}")

        try:
            # Calculer n_results
            if where or filter_fn:
                n_results = min(k * 5, collection_count, 250)
                logger.info(f"   Filtrage actif → requesting {n_results} results")
            else:
                n_results = min(k, collection_count)

            logger.info(f"   ⏳ Calling ChromaDB collection.query() with {self.chromadb_timeout}s timeout...")

            # ✅ FONCTION WRAPPER POUR TIMEOUT
            def chromadb_query():
                return self.collection.query(
                    query_embeddings=[query_vector],
                    n_results=n_results,
                    include=['metadatas', 'distances']
                )

            # ✅ EXÉCUTER AVEC TIMEOUT
            try:
                results = run_with_timeout(chromadb_query, timeout_seconds=self.chromadb_timeout)
                logger.info(f"   ✅ ChromaDB returned successfully")

            except TimeoutException:
                logger.error(f"   ❌ ChromaDB TIMEOUT après {self.chromadb_timeout}s")
                logger.error(f"   → Ceci indique un problème ChromaDB + PyQt5 QThread")
                logger.error(f"   → Solutions:")
                logger.error(f"      1. Augmenter timeout: vector_store.chromadb_timeout = 30")
                logger.error(f"      2. Reconstruire l'index ChromaDB")
                logger.error(f"      3. Utiliser ChromaDB dans un process séparé")
                return [], [], []  # ← 3 éléments vides

            except Exception as e:
                logger.error(f"   ❌ ChromaDB error: {e}")
                logger.exception("   Full traceback:")
                return [], [], []  # ← 3 éléments vides

            if not results['ids'] or not results['ids'][0]:
                logger.warning("   ⚠️ No results from ChromaDB")
                return [], [], []  # ← 3 éléments vides

            # Extraire résultats
            ids = results['ids'][0]
            distances = results['distances'][0]
            metadatas = results['metadatas'][0]

            logger.info(f"   📊 Got {len(ids)} results from ChromaDB")

            # Convertir distances en similarités
            similarities = [1 - d for d in distances]

            # ✅ FILTRAGE POST-QUERY
            if where or filter_fn:
                logger.info(f"   🔄 Applying filters...")
                filtered_ids = []
                filtered_similarities = []
                filtered_metadata = []

                for doc_id, sim, meta in zip(ids, similarities, metadatas):
                    # WHERE filter
                    if where:
                        match = all(meta.get(k) == v for k, v in where.items())
                        if not match:
                            continue
                        
                    # filter_fn
                    if filter_fn:
                        try:
                            if not filter_fn(meta):
                                continue
                        except:
                            continue
                        
                    filtered_ids.append(doc_id)
                    filtered_similarities.append(sim)
                    filtered_metadata.append(meta)

                    if len(filtered_metadata) >= k:
                        break
                    
                logger.info(f"   ✅ After filtering: {len(filtered_metadata)}/{len(metadatas)} results")
                return filtered_ids, filtered_similarities, filtered_metadata

            else:
                # Pas de filtrage
                return ids[:k], similarities[:k], metadatas[:k]

        except Exception as e:
            logger.error(f"❌ Unexpected error in search(): {e}")
            logger.exception("Full traceback:")
            return [], [], []
    
    
    def bm25_search(
        self,
        query: str,
        top_k: int = 10,
        domain: Optional[str] = None
    ) -> Tuple[List[str], List[float], List[Dict[str, Any]]]:  # ← 3 éléments !
        """Recherche BM25"""
        
        if not self.bm25_available or self.bm25_index is None:
            logger.warning("⚠️ BM25 non disponible")
            return [], [], []  # ← 3 éléments vides
        
        try:
            tokenized_query = query.lower().split()
            scores = self.bm25_index.get_scores(tokenized_query)
            ranked_indices = np.argsort(scores)[::-1]
            
            results_ids = []           # ← NOUVEAU
            results_scores = []
            results_metadata = []
            
            for idx in ranked_indices:
                if idx >= len(self.bm25_ids):
                    continue
                
                doc_id = self.bm25_ids[idx]
                score = float(scores[idx])
                
                # ✅ Essayer le cache d'abord
                metadata = self.metadata_cache.get(doc_id)
                
                # Si pas dans le cache, récupérer à la volée
                if metadata is None:
                    try:
                        result = self.collection.get(ids=[doc_id], include=['metadatas'])
                        if result['metadatas']:
                            metadata = result['metadatas'][0]
                            # Mettre en cache pour la prochaine fois
                            self.metadata_cache[doc_id] = metadata
                    except:
                        continue
                    
                if metadata is None:
                    continue
                
                if domain and metadata.get('domain') != domain:
                    continue
                
                results_ids.append(doc_id)        # ← NOUVEAU
                results_scores.append(score)
                results_metadata.append(metadata)
                
                if len(results_metadata) >= top_k:
                    break
                
            logger.info(f"✅ BM25: {len(results_metadata)} résultats")
            return results_ids, results_scores, results_metadata  # ← 3 éléments !
        
        except Exception as e:
            logger.error(f"❌ BM25 search error: {e}")
            return [], [], []
    
    
    def add_vectors(
        self,
        vectors: np.ndarray,
        metadata_list: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ):
        """Ajoute des vecteurs"""
        
        if vectors.shape[0] != len(metadata_list):
            raise ValueError(f"Mismatch: {vectors.shape[0]} vectors vs {len(metadata_list)} metadata")
        
        if ids is None:
            current_count = self.collection.count()
            ids = [f"doc_{i}" for i in range(current_count, current_count + len(metadata_list))]
        
        embeddings_list = vectors.tolist()
        
        flattened_metadata = []
        for meta in metadata_list:
            needs_flattening = any(isinstance(v, dict) for v in meta.values())
            
            if needs_flattening:
                flat_meta = _flatten_metadata(meta)
                flattened_metadata.append(flat_meta)
            else:
                flattened_metadata.append(meta)
        
        self.collection.add(
            embeddings=embeddings_list,
            metadatas=flattened_metadata,
            ids=ids
        )
        
        # ✅ Mettre à jour le cache si chargé
        if self._cache_loaded:
            for doc_id, metadata in zip(ids, flattened_metadata):
                self.metadata_cache[doc_id] = metadata
        
        logger.info(f"✅ {len(metadata_list)} vecteurs ajoutés")
    
    
    def bulk_insert(
        self,
        documents: List[Dict[str, Any]],
        embeddings: np.ndarray
    ):
        """Insertion en masse"""
        
        if len(documents) != embeddings.shape[0]:
            raise ValueError(f"Mismatch: {len(documents)} docs vs {embeddings.shape[0]} embeddings")
        
        ids = [doc['id'] for doc in documents]
        metadata_list = [doc.get('metadata', {}) for doc in documents]
        
        self.add_vectors(embeddings, metadata_list, ids)
        
        try:
            import rank_bm25
            
            texts = []
            for doc in documents:
                content = doc.get('content', '') or doc.get('text', '')
                if content:
                    texts.append(content.lower().split())
                else:
                    texts.append([])
            
            self.bm25_index = rank_bm25.BM25Okapi(texts)
            self.bm25_ids = ids
            self.bm25_available = True
            
            bm25_data = {'index': self.bm25_index, 'ids': self.bm25_ids}
            
            with open(self.bm25_path, 'wb') as f:
                pickle.dump(bm25_data, f)
            
            logger.info(f"✅ Index BM25 créé: {len(ids)} documents")
            
        except ImportError:
            logger.warning("⚠️ rank_bm25 non installé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur création BM25: {e}")
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiques"""
        stats = {
            'num_vectors': self.collection.count() if self.collection else 0,
            'dimension': self.dimension,
            'bm25_available': self.bm25_available,
            'cache_size': len(self.metadata_cache),
            'cache_loaded': self._cache_loaded  # ✅ NOUVEAU
        }
        
        if self.bm25_available:
            stats['bm25_docs'] = len(self.bm25_ids)
        
        return stats
    
    
    def get_document_count(self) -> int:
        """Nombre de documents"""
        if self.collection:
            return self.collection.count()
        return 0
    
    
    def reset(self):
        """Reset complet"""
        logger.warning("⚠️ Resetting VectorStore...")
        
        if self.client and self.collection:
            try:
                self.client.delete_collection(name="context_weaver")
                logger.info("✅ Collection supprimée")
            except:
                pass
        
        if self.bm25_path.exists():
            self.bm25_path.unlink()
        
        self.collection = None
        self.bm25_index = None
        self.bm25_available = False
        self.metadata_cache = {}
        self._cache_loaded = False  # ✅ Reset flag
        
        logger.info("✅ VectorStore reset")
    
    
    def clear(self):
        """Alias pour reset() pour compatibilité"""
        self.reset()


def _flatten_metadata(metadata: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
    """Aplatit les métadonnées"""
    flat = {}
    
    for key, value in metadata.items():
        new_key = f"{prefix}{key}" if prefix else key
        
        if isinstance(value, dict):
            flat.update(_flatten_metadata(value, prefix=f"{new_key}_"))
        elif isinstance(value, (list, tuple)):
            flat[new_key] = str(value)
        else:
            flat[new_key] = value
    
    return flat