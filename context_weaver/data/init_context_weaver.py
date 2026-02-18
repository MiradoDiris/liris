#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'initialisation de Context Weaver avec la base de données
✅ REFACTORISÉ: Utilise VectorStore au lieu de BM25Search/EmbeddingSearch séparés
"""

import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent))

from utils.dataset_database import DatasetDatabase

logger = logging.getLogger(__name__)


def init_context_weaver_with_database(
    database: DatasetDatabase = None,
    project_name: str = None,
    force_reindex: bool = False
) -> bool:
    """
    Initialise Context Weaver avec les données de la base
    
    Args:
        database: Instance de DatasetDatabase (optionnel, sera créée si None)
        project_name: Nom du projet à indexer (None = tous les projets)
        force_reindex: Forcer la réindexation même si déjà fait
        
    Returns:
        True si succès
    """
    try:
        logger.info("=" * 80)
        logger.info("🚀 INITIALISATION CONTEXT WEAVER AVEC BASE DE DONNÉES")
        logger.info("=" * 80)
        
        # Créer la database si nécessaire
        if database is None:
            logger.info("📦 Création de l'instance DatasetDatabase...")
            database = DatasetDatabase()
        
        # Vérifier la connexion
        if not database.test_connection():
            logger.error("❌ Impossible de se connecter à la base de données")
            return False
        
        logger.info("✅ Connexion à la base OK")
        
        # ✅ REFACTORISÉ: Utiliser VectorStore au lieu de BM25/Embedding séparés
        logger.info("📚 Chargement du Vector Store...")
        
        try:
            from context_weaver.data.vector_store_chroma import VectorStore
            
            vector_store = VectorStore()
            vector_store.initialize()
            
            # Vérifier l'état du vector store
            stats = vector_store.get_stats()
            
            logger.info(f"✅ Vector Store:")
            logger.info(f"   • Documents: {stats.get('total_documents', 0)}")
            logger.info(f"   • Dimension: {stats.get('dimension', 0)}")
            logger.info(f"   • BM25 disponible: {stats.get('bm25_available', False)}")
            
            # Décider si on doit réindexer
            should_index = force_reindex or stats.get('total_documents', 0) == 0
            
            if not should_index:
                logger.info("ℹ️  Index déjà présents, pas de réindexation nécessaire")
                logger.info("   (Utilisez force_reindex=True pour forcer)")
                return True
            
        except ImportError as e:
            logger.error(f"❌ Impossible d'importer VectorStore: {e}")
            logger.error("   → Vérifiez que context_weaver est installé")
            return False
        
        # Indexer les données
        logger.info("\n📊 INDEXATION DES DONNÉES")
        logger.info("-" * 80)
        
        from context_weaver.data.database_indexer import DatabaseIndexer, index_all_projects
        
        if project_name:
            # Indexer un seul projet
            logger.info(f"🎯 Indexation du projet: {project_name}")
            
            indexer = DatabaseIndexer(database)
            success = indexer.index_project_to_vector_store(
                project_name,
                vector_store
            )
            
            if success:
                stats = indexer.get_stats()
                logger.info(f"✅ {stats['indexed_documents']} documents indexés")
            else:
                logger.error(f"❌ Échec de l'indexation de '{project_name}'")
                return False
        
        else:
            # Indexer tous les projets
            logger.info("🌐 Indexation de tous les projets...")
            
            success = index_all_projects(
                database,
                vector_store
            )
            
            if not success:
                logger.error("❌ Échec de l'indexation globale")
                return False
        
        # Statistiques finales
        logger.info("\n📈 STATISTIQUES FINALES")
        logger.info("-" * 80)
        
        final_stats = vector_store.get_stats()
        logger.info(f"  • Total documents: {final_stats.get('total_documents', 0)}")
        logger.info(f"  • Index type: {final_stats.get('index_type', 'unknown')}")
        logger.info(f"  • Dimension: {final_stats.get('dimension', 0)}")
        logger.info(f"  • BM25: {final_stats.get('bm25_available', False)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ CONTEXT WEAVER PRÊT")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ ERREUR D'INITIALISATION: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def check_context_weaver_status(database: DatasetDatabase = None) -> dict:
    """
    Vérifie le statut de Context Weaver
    
    Returns:
        Dict avec les informations de statut
    """
    status = {
        'ready': False,
        'database_connected': False,
        'vector_store_indexed': False,
        'total_documents': 0,
        'bm25_available': False,
        'projects_count': 0,
        'error': None
    }
    
    try:
        # Vérifier la database
        if database is None:
            database = DatasetDatabase()
        
        status['database_connected'] = database.test_connection()
        
        if status['database_connected']:
            projects = database.get_all_projects()
            status['projects_count'] = len(projects)
        
        # ✅ REFACTORISÉ: Vérifier VectorStore au lieu de BM25/Embedding séparés
        try:
            from context_weaver.data.vector_store_chroma import VectorStore
            
            vector_store = VectorStore()
            vector_store.initialize()
            
            stats = vector_store.get_stats()
            
            status['total_documents'] = stats.get('total_documents', 0)
            status['bm25_available'] = stats.get('bm25_available', False)
            status['vector_store_indexed'] = status['total_documents'] > 0
            
        except ImportError:
            status['error'] = "VectorStore non disponible"
        except Exception as e:
            status['error'] = f"Erreur VectorStore: {str(e)}"
        
        # Déterminer si prêt
        status['ready'] = (
            status['database_connected'] and
            status['vector_store_indexed'] and
            status['projects_count'] > 0
        )
        
    except Exception as e:
        status['error'] = str(e)
    
    return status


def print_status(status: dict = None):
    """Affiche le statut de Context Weaver"""
    if status is None:
        status = check_context_weaver_status()
    
    print("\n" + "=" * 60)
    print("CONTEXT WEAVER - STATUT")
    print("=" * 60)
    
    # Statut global
    ready_icon = "✅" if status['ready'] else "❌"
    print(f"\n{ready_icon} Statut: {'PRÊT' if status['ready'] else 'NON PRÊT'}")
    
    # Détails
    print(f"\n📊 Détails:")
    
    db_icon = "✅" if status['database_connected'] else "❌"
    print(f"  {db_icon} Base de données: {'Connectée' if status['database_connected'] else 'Déconnectée'}")
    
    if status['database_connected']:
        print(f"     • Projets: {status['projects_count']}")
    
    vs_icon = "✅" if status['vector_store_indexed'] else "⚠️"
    print(f"  {vs_icon} Vector Store: {status['total_documents']} documents")
    
    bm25_icon = "✅" if status['bm25_available'] else "⚠️"
    print(f"  {bm25_icon} BM25: {'Disponible' if status['bm25_available'] else 'Non disponible'}")
    
    if status['error']:
        print(f"\n❌ Erreur: {status['error']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Vérifier le statut actuel
    print("🔍 Vérification du statut actuel...")
    status = check_context_weaver_status()
    print_status(status)
    
    # Initialiser si nécessaire
    if not status['ready']:
        print("\n🚀 Lancement de l'initialisation...")
        success = init_context_weaver_with_database()
        
        if success:
            print("\n✅ Initialisation réussie!")
            print_status(check_context_weaver_status())
        else:
            print("\n❌ Échec de l'initialisation")
            sys.exit(1)
    else:
        print("\n✅ Context Weaver déjà prêt!")