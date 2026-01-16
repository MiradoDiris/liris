#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Indexer pour Context Weaver - VERSION CORRIGÉE
Indexe les données de la base SQLite dans BM25 et les embeddings
"""

import logging
from typing import List, Dict, Any
from utils.dataset_database import DatasetDatabase

logger = logging.getLogger(__name__)


class DatabaseIndexer:
    """
    Indexeur qui transforme les données de la base SQLite
    en index BM25 et vecteurs pour Context Weaver
    """
    
    def __init__(self, database: DatasetDatabase):
        self.database = database
        self.indexed_count = 0
    
    def index_project_for_context_weaver(
        self, 
        project_name: str,
        bm25_search=None,
        embedding_search=None,
        oss_client=None
    ) -> bool:
        """
        ✅ VERSION CORRIGÉE : Indexe un projet avec génération embeddings
        
        Args:
            project_name: Nom du projet
            bm25_search: Instance du moteur BM25
            embedding_search: Instance du moteur embeddings
            oss_client: Client OSS pour générer les embeddings
            
        Returns:
            True si succès
        """
        try:
            logger.info(f"📚 Indexation du projet '{project_name}' pour Context Weaver...")
            
            # Récupérer le projet complet
            project_data = self.database.get_dataset_projet(project_name)
            
            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé")
                return False
            
            # Extraire tous les documents indexables
            documents = self._extract_documents_from_project(project_data)
            
            if not documents:
                logger.warning(f"⚠️ Aucun document à indexer pour '{project_name}'")
                return False
            
            logger.info(f"📄 {len(documents)} document(s) extrait(s)")
            
            # ✅ CORRECTION 1: Indexer dans BM25
            if bm25_search:
                try:
                    bm25_search.index_documents(documents)
                    logger.info(f"✅ BM25: {len(documents)} documents indexés")
                except Exception as e:
                    logger.error(f"❌ Erreur indexation BM25: {e}")
            
            # ✅ CORRECTION 2: Générer embeddings + indexer dans Vector Store
            if embedding_search and oss_client:
                try:
                    logger.info(f"🧮 Génération des embeddings via OSS...")
                    embeddings_list = []
                    metadata_list = []
                    
                    for i, doc in enumerate(documents, 1):
                        # Construire le texte combiné
                        combined_text = " ".join(filter(None, [
                            doc.get("name", ""),
                            doc.get("description", ""),
                            doc.get("variables", ""),
                            doc.get("content", "")[:500],
                        ]))
                        
                        # Générer embeddings
                        embeddings = oss_client.generate_embeddings(combined_text)
                        embeddings_list.append(embeddings)
                        metadata_list.append(doc)
                        
                        if i % 10 == 0:
                            logger.info(f"  Progression: {i}/{len(documents)}")
                    
                    # Indexer dans Vector Store
                    embedding_search.index_documents_from_embeddings(
                        embeddings_list,
                        metadata_list
                    )
                    logger.info(f"✅ Vector Store: {len(documents)} documents indexés")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur indexation embeddings: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            self.indexed_count = len(documents)
            logger.info(f"✅ Projet '{project_name}' indexé avec succès")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'indexation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _extract_documents_from_project(self, project_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        ✅ CORRECTION : Variable 'project' remplacée par 'project_name'
        
        Extrait tous les documents indexables d'un projet
        
        Chaque niveau de la hiérarchie devient un document :
        - Typologie
        - Cluster de taxonomie
        - Root label
        - Parent label
        - Child label (tous niveaux)
        """
        documents = []
        
        project_name = project_data.get('nom', 'Unknown')  # ✅ CORRECTION
        typologies = project_data.get('typologies', [])
        
        for typo_idx, typologie in enumerate(typologies):
            typologie_name = typologie.get('name', '')
            
            # 1. Document pour la typologie elle-même
            documents.append({
                'id': f"typologie_{project_name}_{typo_idx}_{typologie_name}".replace(' ', '_'),  # ✅ CORRECTION
                'name': typologie_name,
                'domain': project_name,  # ✅ CORRECTION
                'type': 'typologie',
                'description': typologie.get('description', ''),
                'variables': typologie_name,
                'content': f"Typologie: {typologie_name}. {typologie.get('description', '')}"
            })
            
            # 2. Parcourir les clusters
            for cluster_idx, cluster in enumerate(typologie.get('taxonomy_clusters', [])):
                cluster_name = cluster.get('name', '')
                
                documents.append({
                    'id': f"cluster_{project_name}_{typo_idx}_{cluster_idx}_{typologie_name}_{cluster_name}".replace(' ', '_'),  # ✅ CORRECTION
                    'name': cluster_name,
                    'domain': project_name,  # ✅ CORRECTION
                    'type': 'taxonomy_cluster',
                    'description': cluster.get('description', ''),
                    'variables': f"{typologie_name} {cluster_name}",
                    'content': f"Cluster: {cluster_name} dans {typologie_name}. {cluster.get('description', '')}"
                })
                
                # 3. Parcourir les root labels
                for root_idx, root in enumerate(cluster.get('root_labels', [])):
                    root_name = root.get('name', '')
                    
                    documents.append({
                        'id': f"root_{project_name}_{typo_idx}_{cluster_idx}_{root_idx}_{typologie_name}_{cluster_name}_{root_name}".replace(' ', '_'),  # ✅ CORRECTION
                        'name': root_name,
                        'domain': project_name,  # ✅ CORRECTION
                        'type': 'root_label',
                        'description': root.get('description', ''),
                        'variables': f"{typologie_name} {cluster_name} {root_name}",
                        'content': f"Root Label: {root_name} dans {cluster_name}. Category: {root.get('category', 'default')}. {root.get('description', '')}"
                    })
                    
                    # 4. Parcourir les parent labels
                    for parent_idx, parent in enumerate(root.get('parent_labels', [])):
                        parent_name = parent.get('name', '')
                        
                        documents.append({
                            'id': f"parent_{project_name}_{typo_idx}_{cluster_idx}_{root_idx}_{parent_idx}_{typologie_name}_{cluster_name}_{root_name}_{parent_name}".replace(' ', '_'),  # ✅ CORRECTION
                            'name': parent_name,
                            'domain': project_name,  # ✅ CORRECTION
                            'type': 'parent_label',
                            'description': parent.get('description', ''),
                            'variables': f"{typologie_name} {cluster_name} {root_name} {parent_name}",
                            'content': f"Parent Label: {parent_name} sous {root_name}. Category: {parent.get('category', 'default')}. {parent.get('description', '')}"
                        })
                        
                        # 5. Parcourir les children récursivement
                        self._extract_children_documents(
                            parent.get('children', []),
                            documents,
                            project_name,  # ✅ CORRECTION
                            typologie_name,
                            cluster_name,
                            root_name,
                            parent_name,
                            []
                        )
        
        return documents
    
    def _extract_children_documents(
        self,
        children: List[Dict],
        documents: List[Dict],
        project_name: str,
        typologie_name: str,
        cluster_name: str,
        root_name: str,
        parent_name: str,
        path: List[str]
    ):
        """Extrait récursivement les documents des children"""
        for child in children:
            child_name = child.get('name', '')
            current_path = path + [child_name]
            
            # Path complet pour l'ID
            path_str = '_'.join(current_path)
            
            documents.append({
                'id': f"child_{project_name}_{typologie_name}_{cluster_name}_{root_name}_{parent_name}_{path_str}".replace(' ', '_'),
                'name': child_name,
                'domain': project_name,
                'type': 'child_label',
                'description': child.get('description', ''),
                'variables': f"{typologie_name} {cluster_name} {root_name} {parent_name} {' '.join(current_path)}",
                'content': f"Child Label: {child_name}. Path: {' > '.join(current_path)}. Category: {child.get('category', 'default')}. {child.get('description', '')}"
            })
            
            # Récursion
            self._extract_children_documents(
                child.get('children', []),
                documents,
                project_name,
                typologie_name,
                cluster_name,
                root_name,
                parent_name,
                current_path
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'indexation"""
        return {
            'indexed_documents': self.indexed_count
        }


def index_all_projects(database: DatasetDatabase, bm25_search=None, 
                      embedding_search=None, oss_client=None) -> bool:
    """
    ✅ VERSION CORRIGÉE : Indexe tous les projets avec embeddings OSS
    
    Args:
        database: Instance de la base de données
        bm25_search: Moteur BM25 (optionnel)
        embedding_search: Moteur embeddings (optionnel)
        oss_client: Client OSS pour générer les embeddings (optionnel)
        
    Returns:
        True si succès
    """
    try:
        indexer = DatabaseIndexer(database)
        
        # Récupérer tous les projets
        projects = database.get_all_projects()
        
        if not projects:
            logger.warning("⚠️ Aucun projet à indexer")
            return False
        
        logger.info(f"📚 Indexation de {len(projects)} projet(s)...")
        
        total_indexed = 0
        
        for project in projects:
            project_name = project.get('name')
            
            if indexer.index_project_for_context_weaver(
                project_name,
                bm25_search,
                embedding_search,
                oss_client  # ✅ AJOUT du client OSS
            ):
                total_indexed += 1
        
        logger.info(f"✅ {total_indexed}/{len(projects)} projet(s) indexé(s)")
        
        return total_indexed > 0
        
    except Exception as e:
        logger.error(f"❌ Erreur indexation globale: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False