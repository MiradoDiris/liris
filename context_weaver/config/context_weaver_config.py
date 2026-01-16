#!/usr/bin/env python
# -*- coding: utf-8 -*-
# config/context_weaver_config.py
"""
Configuration pour Context Weaver avec support de la base de données
"""

import os
from pathlib import Path


class ContextWeaverConfig:
    """Configuration pour Context Weaver avec base de données"""

    DATA_SOURCE = os.getenv("CONTEXT_WEAVER_DATA_SOURCE", "database")
    
    AUTO_INDEX_ON_STARTUP = os.getenv("AUTO_INDEX_ON_STARTUP", "true").lower() == "true"
    
    REINDEX_ON_EACH_USE = os.getenv("REINDEX_ON_EACH_USE", "false").lower() == "true"

    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/liris.db")
    
    AUTO_INDEX_PROJECTS = None
    
    SEARCH_CACHE_SIZE = 1000
    
    CACHE_TTL = 3600  # 1 heure
    
    USE_CACHE = True
    
    # ============================================================
    # LOGGING
    # ============================================================
    
    # Niveau de log pour l'indexation
    INDEX_LOG_LEVEL = os.getenv("INDEX_LOG_LEVEL", "INFO")
    
    # Logger les statistiques d'indexation
    LOG_INDEX_STATS = True
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    @staticmethod
    def get_database_path() -> Path:
        """Retourne le chemin de la base de données"""
        db_path = Path(ContextWeaverConfig.DATABASE_PATH)
        
        # Créer le répertoire si nécessaire
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        return db_path
    
    @staticmethod
    def should_auto_index() -> bool:
        """Détermine si l'indexation auto doit avoir lieu"""
        return ContextWeaverConfig.AUTO_INDEX_ON_STARTUP
    
    @staticmethod
    def should_reindex() -> bool:
        """Détermine si on doit réindexer à chaque utilisation"""
        return ContextWeaverConfig.REINDEX_ON_EACH_USE
    
    @staticmethod
    def get_projects_to_index() -> list:
        """
        Retourne la liste des projets à indexer
        None = tous les projets
        """
        return ContextWeaverConfig.AUTO_INDEX_PROJECTS
    
    @staticmethod
    def validate_config() -> bool:
        """Valide la configuration"""
        errors = []
        
        # Vérifier que la base existe si DATA_SOURCE = "database"
        if ContextWeaverConfig.DATA_SOURCE == "database":
            db_path = ContextWeaverConfig.get_database_path()
            if not db_path.exists():
                errors.append(f"Base de données introuvable: {db_path}")
        
        # Vérifier DATA_SOURCE
        valid_sources = ["database", "files", "hybrid"]
        if ContextWeaverConfig.DATA_SOURCE not in valid_sources:
            errors.append(f"DATA_SOURCE invalide. Options: {valid_sources}")
        
        if errors:
            raise ValueError("Erreurs de configuration:\n" + "\n".join(errors))
        
        return True
    
    @staticmethod
    def get_config_summary() -> dict:
        """Retourne un résumé de la configuration"""
        return {
            "data_source": ContextWeaverConfig.DATA_SOURCE,
            "database_path": str(ContextWeaverConfig.DATABASE_PATH),
            "auto_index": ContextWeaverConfig.AUTO_INDEX_ON_STARTUP,
            "reindex_on_use": ContextWeaverConfig.REINDEX_ON_EACH_USE,
            "use_cache": ContextWeaverConfig.USE_CACHE,
            "cache_ttl": ContextWeaverConfig.CACHE_TTL
        }


# ============================================================
# CONFIGURATION PAR DÉFAUT
# ============================================================

DEFAULT_CONFIG = ContextWeaverConfig()


def print_config():
    """Affiche la configuration actuelle"""
    print("=" * 60)
    print("CONTEXT WEAVER - CONFIGURATION")
    print("=" * 60)
    
    config = ContextWeaverConfig.get_config_summary()
    
    for key, value in config.items():
        print(f"  • {key}: {value}")
    
    print("=" * 60)


if __name__ == "__main__":
    # Afficher la config si exécuté directement
    print_config()
    
    # Valider
    try:
        ContextWeaverConfig.validate_config()
        print("\n✅ Configuration valide")
    except ValueError as e:
        print(f"\n❌ Configuration invalide:\n{e}")