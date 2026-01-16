#!/usr/bin/env python
# -*- coding: utf-8 -*-
#config/bm25_config.py

"""
BM25 Search Configuration
Configuration for BM25 (Best Matching 25) search algorithm
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class BM25Config:
    """
    Configuration class for BM25 search parameters.
    
    BM25 is a ranking function used in information retrieval.
    It ranks documents based on the query terms appearing in each document.
    
    Attributes:
        k1: Controls term frequency saturation (typical range: 1.2-2.0)
            Higher values increase the impact of term frequency.
        b: Controls document length normalization (range: 0.0-1.0)
            0 = no normalization, 1 = full normalization
        epsilon: Floor value for IDF calculation to prevent negative values
        use_stemming: Whether to apply stemming to terms
        use_stopwords: Whether to remove stopwords
        language: Language for stemming and stopwords (e.g., 'english', 'french')
        min_term_length: Minimum term length to consider
        max_terms_per_query: Maximum number of terms to consider per query
        tokenizer: Tokenization method ('standard', 'whitespace', 'ngram')
        ngram_range: Range for n-gram tokenization (min, max)
    """
    
    # Class-level constants for search
    TOP_K: int = 10  # Default number of results to return
    MIN_SCORE: float = 0.1  # Minimum score threshold
    K1: float = 1.5  # Default k1 parameter
    B: float = 0.75  # Default b parameter
    
    # Core BM25 parameters
    k1: float = 1.5
    b: float = 0.75
    epsilon: float = 0.25
    
    # Text processing options
    use_stemming: bool = False
    use_stopwords: bool = True
    language: str = 'english'
    
    # Term filtering
    min_term_length: int = 2
    max_terms_per_query: int = 100
    
    # Tokenization
    tokenizer: str = 'standard'  # 'standard', 'whitespace', 'ngram'
    ngram_range: tuple = (1, 1)  # (min_n, max_n)
    
    # Advanced options
    case_sensitive: bool = False
    remove_punctuation: bool = True
    normalize_unicode: bool = True
    
    # Performance options
    cache_size: int = 1000
    batch_size: int = 100
    
    # Scoring options
    use_idf: bool = True
    use_avg_doc_length: bool = True
    smooth_idf: bool = True
    
    def __post_init__(self):
        """Validate configuration parameters"""
        if not 0.0 <= self.k1 <= 3.0:
            raise ValueError(f"k1 must be between 0.0 and 3.0, got {self.k1}")
        
        if not 0.0 <= self.b <= 1.0:
            raise ValueError(f"b must be between 0.0 and 1.0, got {self.b}")
        
        if self.epsilon < 0:
            raise ValueError(f"epsilon must be non-negative, got {self.epsilon}")
        
        if self.tokenizer not in ['standard', 'whitespace', 'ngram']:
            raise ValueError(f"tokenizer must be 'standard', 'whitespace', or 'ngram', got {self.tokenizer}")
        
        if len(self.ngram_range) != 2 or self.ngram_range[0] > self.ngram_range[1]:
            raise ValueError(f"ngram_range must be (min_n, max_n) where min_n <= max_n")
        
    @staticmethod
    def get_index_path() -> Path:
        """
        Retourne le chemin vers le répertoire d'index BM25
        
        Returns:
            Path: Chemin vers le dossier d'index
        """
        # Déterminer le répertoire racine du projet
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent  # Remonte de 2 niveaux
        
        # Créer le chemin vers les données
        data_dir = project_root / "data" / "bm25_index"
        
        # Créer le dossier s'il n'existe pas
        data_dir.mkdir(parents=True, exist_ok=True)
        
        return data_dir
    
    @staticmethod
    def get_cache_path() -> Path:
        """
        Retourne le chemin vers le cache BM25
        
        Returns:
            Path: Chemin vers le dossier de cache
        """
        cache_dir = BM25Config.get_index_path() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'k1': self.k1,
            'b': self.b,
            'epsilon': self.epsilon,
            'use_stemming': self.use_stemming,
            'use_stopwords': self.use_stopwords,
            'language': self.language,
            'min_term_length': self.min_term_length,
            'max_terms_per_query': self.max_terms_per_query,
            'tokenizer': self.tokenizer,
            'ngram_range': self.ngram_range,
            'case_sensitive': self.case_sensitive,
            'remove_punctuation': self.remove_punctuation,
            'normalize_unicode': self.normalize_unicode,
            'cache_size': self.cache_size,
            'batch_size': self.batch_size,
            'use_idf': self.use_idf,
            'use_avg_doc_length': self.use_avg_doc_length,
            'smooth_idf': self.smooth_idf,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'BM25Config':
        """Create configuration from dictionary"""
        return cls(**config_dict)
    
    @classmethod
    def get_preset(cls, preset_name: str) -> 'BM25Config':
        """
        Get a preset configuration.
        
        Available presets:
            - 'default': Standard BM25 configuration
            - 'strict': Strict matching with high precision
            - 'lenient': Lenient matching with high recall
            - 'short_docs': Optimized for short documents
            - 'long_docs': Optimized for long documents
            - 'multilingual': Configuration for multilingual search
        """
        presets = {
            'default': cls(),
            
            'strict': cls(
                k1=1.2,
                b=0.75,
                use_stemming=False,
                use_stopwords=False,
                min_term_length=3,
            ),
            
            'lenient': cls(
                k1=2.0,
                b=0.5,
                use_stemming=True,
                use_stopwords=True,
                min_term_length=2,
            ),
            
            'short_docs': cls(
                k1=1.2,
                b=0.3,  # Less length normalization
                use_stemming=False,
            ),
            
            'long_docs': cls(
                k1=1.8,
                b=0.9,  # More length normalization
                use_stemming=True,
            ),
            
            'multilingual': cls(
                use_stemming=False,  # Stemming is language-specific
                use_stopwords=False,
                normalize_unicode=True,
                case_sensitive=False,
            ),
        }
        
        if preset_name not in presets:
            raise ValueError(f"Unknown preset: {preset_name}. Available presets: {list(presets.keys())}")
        
        return presets[preset_name]
    
    def copy(self) -> 'BM25Config':
        """Create a copy of the configuration"""
        return BM25Config(**self.to_dict())
    
    def __repr__(self) -> str:
        return f"BM25Config(k1={self.k1}, b={self.b}, language='{self.language}')"


# Default configuration instance
DEFAULT_BM25_CONFIG = BM25Config()


# Preset configurations for common use cases
PRESETS = {
    'default': DEFAULT_BM25_CONFIG,
    'strict': BM25Config.get_preset('strict'),
    'lenient': BM25Config.get_preset('lenient'),
    'short_docs': BM25Config.get_preset('short_docs'),
    'long_docs': BM25Config.get_preset('long_docs'),
    'multilingual': BM25Config.get_preset('multilingual'),
}


def get_config(preset: str = 'default') -> BM25Config:
    """
    Get a BM25 configuration by preset name.
    
    Args:
        preset: Name of the preset configuration
        
    Returns:
        BM25Config instance
    """
    if preset in PRESETS:
        return PRESETS[preset].copy()
    return BM25Config.get_preset(preset)