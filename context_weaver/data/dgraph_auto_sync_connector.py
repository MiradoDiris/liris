#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Connecteur Dgraph avec synchronisation automatique du Vector Store
Wrapper autour de TaxonomyDgraphConnector qui déclenche la mise à jour
du Vector Store à chaque modification
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DgraphAutoSyncConnector:
    """
    Wrapper autour du connecteur Dgraph qui synchronise automatiquement
    le Vector Store lors de toute modification
    
    Usage:
        connector = DgraphAutoSyncConnector(
            base_connector=dgraph_connector,
            syncer=dgraph_vector_sync,
            project_name="macompta"
        )
        
        # Toute modification déclenchera automatiquement la mise à jour
        uid = connector.add_typologie(...)
    """
    
    def __init__(
        self,
        base_connector,
        syncer,
        project_name: str,
        auto_sync: bool = True
    ):
        """
        Args:
            base_connector: Instance de TaxonomyDgraphConnector
            syncer: Instance de DgraphVectorSync
            project_name: Nom du projet
            auto_sync: Activer la synchronisation automatique
        """
        self.base = base_connector
        self.syncer = syncer
        self.project_name = project_name
        self.auto_sync = auto_sync
        
        # Compteurs de modifications
        self.modifications_count = 0
        self.last_sync_trigger = None
        
        logger.info(f"✅ DgraphAutoSyncConnector initialisé (auto_sync={'ON' if auto_sync else 'OFF'})")
    
    # ============================================
    # MÉTHODES WRAPPÉES AVEC AUTO-SYNC
    # ============================================
    
    def create_project(self, name: str, description: str = "") -> Optional[str]:
        """Crée un projet et déclenche la synchronisation"""
        project_uid = self.base.create_project(name, description)
        
        if project_uid and self.auto_sync:
            self._trigger_sync("create_project", project_uid)
        
        return project_uid
    
    def add_typologie(
        self,
        project_uid: str,
        name: str,
        description: str = "",
        position: int = 0
    ) -> Optional[str]:
        """Ajoute une typologie et déclenche la synchronisation"""
        typologie_uid = self.base.add_typologie(
            project_uid, name, description, position
        )
        
        if typologie_uid and self.auto_sync:
            self._trigger_sync("add_typologie", typologie_uid)
        
        return typologie_uid
    
    def add_cluster(
        self,
        typologie_uid: str,
        name: str,
        description: str = "",
        position: int = 0
    ) -> Optional[str]:
        """Ajoute un cluster et déclenche la synchronisation"""
        cluster_uid = self.base.add_cluster(
            typologie_uid, name, description, position
        )
        
        if cluster_uid and self.auto_sync:
            self._trigger_sync("add_cluster", cluster_uid)
        
        return cluster_uid
    
    def add_root_label(
        self,
        cluster_uid: str,
        name: str,
        description: str = "",
        category: str = "default",
        position: int = 0,
        **metadata
    ) -> Optional[str]:
        """Ajoute un root label et déclenche la synchronisation"""
        root_uid = self.base.add_root_label(
            cluster_uid, name, description, category, position
        )
        
        # Ajouter les métadonnées si fournies
        if root_uid and metadata:
            self._update_node_metadata(root_uid, metadata)
        
        if root_uid and self.auto_sync:
            self._trigger_sync("add_root_label", root_uid)
        
        return root_uid
    
    def add_label_node(
        self,
        parent_uid: str,
        name: str,
        description: str = "",
        category: str = "default",
        depth: int = 0,
        position: int = 0,
        **metadata
    ) -> Optional[str]:
        """Ajoute un label node et déclenche la synchronisation"""
        label_uid = self.base.add_label_node(
            parent_uid, name, description, category, depth, position, **metadata
        )
        
        if label_uid and self.auto_sync:
            self._trigger_sync("add_label_node", label_uid)
        
        return label_uid
    
    def update_node(
        self,
        node_uid: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Met à jour un nœud et déclenche la synchronisation
        
        Args:
            node_uid: UID du nœud à mettre à jour
            updates: Dictionnaire des champs à mettre à jour
        """
        try:
            txn = self.base.client.txn()
            
            mutation = {
                "uid": node_uid,
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            mutation.update(updates)
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Nœud {node_uid} mis à jour")
            
            if self.auto_sync:
                self._trigger_sync("update_node", node_uid, is_update=True)
            
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour nœud: {e}")
            return False
    
    def delete_node(self, node_uid: str) -> bool:
        """
        Supprime un nœud et met à jour le Vector Store
        
        Note: Dgraph avec CASCADE supprimera automatiquement les enfants
        """
        try:
            txn = self.base.client.txn()
            
            # Supprimer le nœud (CASCADE via schéma)
            txn.mutate(del_obj={"uid": node_uid})
            txn.commit()
            
            logger.info(f"✅ Nœud {node_uid} supprimé")
            
            if self.auto_sync:
                self._trigger_sync("delete_node", node_uid, is_delete=True)
            
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression nœud: {e}")
            return False
    
    # ============================================
    # MÉTHODES DE SYNCHRONISATION
    # ============================================
    
    def _trigger_sync(
        self,
        operation: str,
        node_uid: str,
        is_update: bool = False,
        is_delete: bool = False
    ):
        """
        Déclenche la synchronisation après une modification
        
        Args:
            operation: Type d'opération (create, update, delete)
            node_uid: UID du nœud modifié
            is_update: True si mise à jour
            is_delete: True si suppression
        """
        try:
            logger.info(f"🔄 Déclenchement sync: {operation} ({node_uid})")
            
            if is_delete:
                # Suppression: retirer du Vector Store
                self.syncer.on_node_deleted(node_uid)
            
            elif is_update:
                # Mise à jour: réindexer
                self.syncer.on_node_updated(node_uid, self.project_name)
            
            else:
                # Création: indexer
                self.syncer.on_node_created(node_uid, self.project_name)
            
            self.modifications_count += 1
            self.last_sync_trigger = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"❌ Erreur synchronisation: {e}")
    
    def force_full_sync(self) -> bool:
        """Force une synchronisation complète"""
        logger.info("🔄 Synchronisation complète forcée...")
        return self.syncer.full_sync(self.project_name)
    
    def force_incremental_sync(self) -> bool:
        """Force une synchronisation incrémentale"""
        logger.info("🔄 Synchronisation incrémentale forcée...")
        return self.syncer.incremental_sync(self.project_name)
    
    # ============================================
    # MÉTHODES UTILITAIRES
    # ============================================
    
    def _update_node_metadata(self, node_uid: str, metadata: Dict[str, Any]):
        """Met à jour les métadonnées d'un nœud"""
        try:
            txn = self.base.client.txn()
            
            mutation = {
                "uid": node_uid,
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            mutation.update(metadata)
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur update metadata: {e}")
    
    def get_sync_status(self) -> Dict:
        """Retourne le statut de synchronisation"""
        sync_status = self.syncer.get_sync_status()
        
        return {
            'auto_sync_enabled': self.auto_sync,
            'modifications_count': self.modifications_count,
            'last_sync_trigger': self.last_sync_trigger,
            **sync_status
        }
    
    def enable_auto_sync(self):
        """Active la synchronisation automatique"""
        self.auto_sync = True
        logger.info("✅ Auto-sync activé")
    
    def disable_auto_sync(self):
        """Désactive la synchronisation automatique"""
        self.auto_sync = False
        logger.warning("⚠️ Auto-sync désactivé")
    
    # ============================================
    # PROXY DES MÉTHODES DE LECTURE
    # ============================================
    
    def get_project(self, project_name: str):
        """Proxy vers la méthode de lecture"""
        return self.base.get_project(project_name)
    
    def get_node_by_uid(self, uid: str, **kwargs):
        """Proxy vers la méthode de lecture"""
        return self.base.get_node_by_uid(uid, **kwargs)
    
    def expand_typologie(self, typologie_uid: str):
        """Proxy vers la méthode de lecture"""
        return self.base.expand_typologie(typologie_uid)
    
    def expand_cluster(self, cluster_uid: str):
        """Proxy vers la méthode de lecture"""
        return self.base.expand_cluster(cluster_uid)
    
    def get_path_to_root(self, node_uid: str):
        """Proxy vers la méthode de lecture"""
        return self.base.get_path_to_root(node_uid)
    
    def search_by_name(self, search_term: str):
        """Proxy vers la méthode de lecture"""
        return self.base.search_by_name(search_term)
    
    def close(self):
        """Ferme les connexions"""
        self.base.close()


# ============================================
# FONCTION D'INITIALISATION COMPLÈTE
# ============================================

def setup_dgraph_with_vector_sync(
    project_name: str,
    oss_client,
    force_full_sync: bool = False
):
    """
    Configure un environnement Dgraph complet avec synchronisation Vector Store
    
    Args:
        project_name: Nom du projet à synchroniser
        oss_client: Client OSS pour générer les embeddings
        force_full_sync: Forcer une synchronisation complète initiale
        
    Returns:
        Tuple (connector, syncer) prêt à l'emploi
    """
    from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.services.embedding_search import EmbeddingSearch
    from context_weaver.data.dgraph_vector_sync import DgraphVectorSync, init_dgraph_vector_sync
    
    logger.info("=" * 80)
    logger.info("🚀 CONFIGURATION DGRAPH + VECTOR STORE")
    logger.info("=" * 80)
    
    # 1. Initialiser Dgraph
    logger.info("📊 Connexion à Dgraph...")
    dgraph_connector = TaxonomyDgraphConnector()
    
    if not dgraph_connector.client:
        logger.error("❌ Échec connexion Dgraph")
        return None, None
    
    # 2. Initialiser Vector Store
    logger.info("🧮 Initialisation Vector Store...")
    vector_store = VectorStore()
    vector_store.initialize()
    
    # 3. Initialiser EmbeddingSearch
    logger.info("🔍 Initialisation EmbeddingSearch...")
    embedding_search = EmbeddingSearch()
    
    # 4. Initialiser le synchroniseur
    logger.info("🔄 Initialisation synchroniseur...")
    syncer = init_dgraph_vector_sync(
        dgraph_connector,
        vector_store,
        embedding_search,
        oss_client,
        project_name,
        force_full_sync
    )
    
    # 5. Créer le connecteur auto-sync
    logger.info("🔌 Création connecteur auto-sync...")
    auto_connector = DgraphAutoSyncConnector(
        dgraph_connector,
        syncer,
        project_name,
        auto_sync=True
    )
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ CONFIGURATION TERMINÉE")
    logger.info("=" * 80)
    logger.info("Utilisation:")
    logger.info("  connector.add_typologie(...)  # Auto-sync activé")
    logger.info("  connector.update_node(...)    # Auto-sync activé")
    logger.info("  connector.delete_node(...)    # Auto-sync activé")
    logger.info("=" * 80 + "\n")
    
    return auto_connector, syncer


# ============================================
# EXEMPLE D'UTILISATION
# ============================================

if __name__ == '__main__':
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Simuler un client OSS (vous devez importer le vrai)
    class MockOSSClient:
        def generate_embeddings(self, text):
            import numpy as np
            return np.random.rand(384)  # Dimension exemple
    
    oss_client = MockOSSClient()
    
    # Configuration complète
    connector, syncer = setup_dgraph_with_vector_sync(
        project_name="macompta",
        oss_client=oss_client,
        force_full_sync=True
    )
    
    if connector:
        # Exemple d'utilisation avec auto-sync
        print("\n🧪 TEST AUTO-SYNC")
        print("=" * 80)
        
        # Créer un projet
        project_uid = connector.create_project(
            name="test_auto_sync",
            description="Test de synchronisation automatique"
        )
        print(f"✅ Projet créé: {project_uid}")
        
        # Ajouter une typologie (auto-sync se déclenche)
        typo_uid = connector.add_typologie(
            project_uid=project_uid,
            name="Test Typologie",
            description="Synchronisation automatique"
        )
        print(f"✅ Typologie créée: {typo_uid}")
        
        # Vérifier le statut
        status = connector.get_sync_status()
        print(f"\n📊 STATUT SYNCHRONISATION:")
        print(f"  • Auto-sync: {status['auto_sync_enabled']}")
        print(f"  • Modifications: {status['modifications_count']}")
        print(f"  • Documents indexés: {status['indexed_count']}")
        print(f"  • Vector Store: {status['vector_store_count']} vecteurs")
        
        # Fermer
        connector.close()
        print("\n✅ Test terminé")