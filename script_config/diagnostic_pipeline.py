#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 DIAGNOSTIC - Prérequis pour les tests du Main Pipeline
Vérifie que tous les composants nécessaires sont disponibles
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

logger = logging.getLogger(__name__)


def check_file(filepath: str, description: str) -> bool:
    """Vérifie si un fichier existe"""
    path = Path(filepath)
    exists = path.exists()
    
    if exists:
        size = path.stat().st_size
        size_mb = size / (1024 * 1024)
        logger.info(f"   ✅ {description}")
        logger.info(f"      Path: {filepath}")
        logger.info(f"      Size: {size_mb:.2f} MB")
    else:
        logger.warning(f"   ⚠️ {description} NOT FOUND")
        logger.warning(f"      Path: {filepath}")
    
    return exists


def check_directory(dirpath: str, description: str) -> bool:
    """Vérifie si un répertoire existe"""
    path = Path(dirpath)
    exists = path.exists() and path.is_dir()
    
    if exists:
        files = list(path.iterdir())
        logger.info(f"   ✅ {description}")
        logger.info(f"      Path: {dirpath}")
        logger.info(f"      Files: {len(files)}")
    else:
        logger.warning(f"   ⚠️ {description} NOT FOUND")
        logger.warning(f"      Path: {dirpath}")
    
    return exists


def check_oss_service() -> bool:
    """Vérifie si le service OSS Classifier est actif"""
    try:
        import requests
        response = requests.get("http://localhost:8085/health", timeout=2)
        
        if response.status_code == 200:
            logger.info(f"   ✅ OSS Classifier Service")
            logger.info(f"      URL: http://localhost:8085")
            logger.info(f"      Status: {response.status_code}")
            return True
        else:
            logger.warning(f"   ⚠️ OSS Classifier Service - Unexpected status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"   ❌ OSS Classifier Service - Connection refused")
        logger.error(f"      URL: http://localhost:8085")
        logger.error(f"      → Start the service first!")
        return False
    except Exception as e:
        logger.error(f"   ❌ OSS Classifier Service - Error: {e}")
        return False


def check_imports() -> bool:
    """Vérifie que les imports nécessaires fonctionnent"""
    required_modules = [
        ('numpy', 'NumPy'),
        ('faiss', 'Faiss'),
        ('requests', 'Requests'),
    ]
    
    all_ok = True
    
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
            logger.info(f"   ✅ {display_name}")
        except ImportError:
            logger.error(f"   ❌ {display_name} NOT INSTALLED")
            logger.error(f"      → pip install {module_name}")
            all_ok = False
    
    return all_ok


def check_context_weaver_modules() -> bool:
    """Vérifie que les modules Context Weaver sont importables"""
    required_modules = [
        ('context_weaver.pipeline.main_pipeline', 'Main Pipeline'),
        ('context_weaver.services.oss_classifier', 'OSS Classifier Client'),
        ('context_weaver.data.vector_store', 'Vector Store'),
        ('context_weaver.pipeline.taxonomy_pipeline', 'Taxonomy Pipeline'),
        ('context_weaver.learner.graph_structure_learner', 'Graph Structure Learner'),
    ]
    
    all_ok = True
    
    for module_path, display_name in required_modules:
        try:
            __import__(module_path)
            logger.info(f"   ✅ {display_name}")
        except ImportError as e:
            logger.error(f"   ❌ {display_name} - Import error")
            logger.error(f"      {str(e)}")
            all_ok = False
    
    return all_ok


def check_vector_store() -> bool:
    """Vérifie le vector store en détail"""
    try:
        from context_weaver.data.vector_store_chroma import VectorStore
        
        vs = VectorStore()
        vs.initialize()
        
        logger.info(f"   ✅ Vector Store initialized")
        logger.info(f"      Vectors: {vs.index.ntotal}")
        logger.info(f"      Metadata: {len(vs.metadata)}")
        
        # Utiliser getattr pour éviter les erreurs d'attributs manquants
        dimension = getattr(vs, 'dimension', getattr(vs, 'embedding_dim', 768))
        logger.info(f"      Dimension: {dimension}")
        
        bm25_avail = getattr(vs, 'bm25_available', getattr(vs, 'has_bm25', False))
        logger.info(f"      BM25 available: {bm25_avail}")
        
        # Check domains
        if vs.metadata:
            domains = set()
            for meta in vs.metadata:
                if 'domain' in meta:
                    domains.add(meta['domain'])
            
            if domains:
                logger.info(f"      Domains: {', '.join(sorted(domains))}")
            else:
                logger.info(f"      Domains: None found")
        
        # Vérifier que l'index contient des données
        if vs.index.ntotal == 0:
            logger.warning(f"      ⚠️ Index is empty (0 vectors)")
            return False
        
        # Vérifier cohérence metadata
        if len(vs.metadata) != vs.index.ntotal:
            logger.warning(f"      ⚠️ Metadata count ({len(vs.metadata)}) != vector count ({vs.index.ntotal})")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Vector Store - Error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def run_diagnostic():
    """Exécute le diagnostic complet"""
    
    logger.info("\n" + "=" * 80)
    logger.info("🔍 DIAGNOSTIC - Context Weaver Main Pipeline Prerequisites")
    logger.info("=" * 80 + "\n")
    
    results = {}
    
    # 1. Python Packages
    logger.info("📦 1. Python Packages")
    logger.info("─" * 80)
    results['python_packages'] = check_imports()
    logger.info("")
    
    # 2. Context Weaver Modules
    logger.info("🔧 2. Context Weaver Modules")
    logger.info("─" * 80)
    results['context_weaver_modules'] = check_context_weaver_modules()
    logger.info("")
    
    # 3. OSS Classifier Service
    logger.info("🌐 3. OSS Classifier Service")
    logger.info("─" * 80)
    results['oss_service'] = check_oss_service()
    logger.info("")
    
    # 4. Data Files
    logger.info("💾 4. Data Files")
    logger.info("─" * 80)
    
    files_ok = []
    
    # Required files
    files_ok.append(check_file(
        "data/indexes/faiss/vector_store.index",
        "Vector Store Index (REQUIRED)"
    ))
    logger.info("")
    
    files_ok.append(check_file(
        "data/indexes/faiss/bm25_index.pkl",
        "BM25 Index (REQUIRED)"
    ))
    logger.info("")
    
    # Optional files
    optional_ok = []
    
    optional_ok.append(check_file(
        "data/prereq_snapshot_v1.json",
        "Prereq Snapshot (OPTIONAL)"
    ))
    logger.info("")
    
    optional_ok.append(check_file(
        "data/graph_structure_model.json",
        "Graph Structure Model (OPTIONAL)"
    ))
    logger.info("")
    
    results['data_files_required'] = all(files_ok)
    results['data_files_optional'] = all(optional_ok)
    
    # 5. Vector Store Detailed Check
    logger.info("🔍 5. Vector Store Detailed Check")
    logger.info("─" * 80)
    results['vector_store'] = check_vector_store()
    logger.info("")
    
    # 6. Directories
    logger.info("📁 6. Directory Structure")
    logger.info("─" * 80)
    
    dirs_ok = []
    dirs_ok.append(check_directory("data", "Data directory"))
    logger.info("")
    dirs_ok.append(check_directory("data/indexes", "Indexes directory"))
    logger.info("")
    dirs_ok.append(check_directory("data/indexes/faiss", "Faiss directory"))
    logger.info("")
    
    results['directories'] = all(dirs_ok)
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 DIAGNOSTIC SUMMARY")
    logger.info("=" * 80 + "\n")
    
    all_critical_ok = all([
        results['python_packages'],
        results['context_weaver_modules'],
        results['oss_service'],
        results['data_files_required'],
        results['vector_store'],
        results['directories']
    ])
    
    if all_critical_ok:
        logger.info("✅ ALL CRITICAL CHECKS PASSED")
        logger.info("\n   You can now run the tests:")
        logger.info("   • python test_main_pipeline_quick.py")
        logger.info("   • python test_main_pipeline.py")
        
        if not results['data_files_optional']:
            logger.info("\n⚠️ OPTIONAL CHECKS FAILED")
            logger.info("   Some optional features may not work:")
            logger.info("   • Prereq validation")
            logger.info("   • Graph structure learning")
            logger.info("   But core tests should still pass.")
        
    else:
        logger.error("❌ SOME CRITICAL CHECKS FAILED")
        logger.error("\n   Please fix the following:")
        
        if not results['python_packages']:
            logger.error("   • Install missing Python packages")
        
        if not results['context_weaver_modules']:
            logger.error("   • Fix Context Weaver module imports")
        
        if not results['oss_service']:
            logger.error("   • Start OSS Classifier Service:")
            logger.error("     → Check if service is running on port 8085")
        
        if not results['data_files_required']:
            logger.error("   • Provide required data files:")
            logger.error("     → vector_store.index")
            logger.error("     → bm25_index.pkl")
        
        if not results['vector_store']:
            logger.error("   • Fix Vector Store initialization")
        
        if not results['directories']:
            logger.error("   • Create missing directories")
    
    logger.info("\n" + "=" * 80 + "\n")
    
    return all_critical_ok


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)