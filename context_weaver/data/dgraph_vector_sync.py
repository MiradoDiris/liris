#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CORRECTIF: dgraph_vector_sync.py
Remplace la requête @recurse par une requête à profondeur fixe
Compatible avec toutes les versions de Dgraph
"""

import logging
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DgraphVectorSync:
    """
    Synchroniseur Dgraph → Vector Store
    VERSION CORRIGÉE: Sans @recurse
    """
    
    def __init__(self, dgraph_connector, vector_store, embedding_search, oss_client):
        self.dgraph = dgraph_connector
        self.vector_store = vector_store
        self.embedding_search = embedding_search
        self.oss_client = oss_client
        
        self.sync_metadata_path = Path("./data/dgraph_sync_metadata.json")
        self.last_sync_time = None
        self.indexed_uids = set()
        
        self._load_sync_metadata()
        
        logger.info("✅ DgraphVectorSync initialisé")
    
    def full_sync(self, project_name: str) -> bool:
        """
        Synchronisation complète
        VERSION CORRIGÉE: Sans @recurse
        """
        try:
            logger.info("=" * 80)
            logger.info(f"🔄 SYNCHRONISATION COMPLÈTE: {project_name}")
            logger.info("=" * 80)
            
            start_time = time.time()
            
            # 1. Récupérer le projet depuis Dgraph
            logger.info("📥 Récupération du projet depuis Dgraph...")
            project_data = self._fetch_complete_project_iterative(project_name)
            
            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé dans Dgraph")
                return False
            
            # 2. Extraire les documents
            logger.info("📊 Extraction des documents...")
            documents = self._extract_documents_from_dgraph(project_data)
            
            if not documents:
                logger.warning("⚠️  Aucun document à indexer")
                return False
            
            logger.info(f"✅ {len(documents)} documents extraits")
            
            # 3. Générer embeddings et indexer
            logger.info("🧮 Génération des embeddings...")
            success = self._index_documents_with_embeddings_validated(documents)
            
            if success:
                self.last_sync_time = datetime.now().isoformat()
                self.indexed_uids = {doc['uid'] for doc in documents}
                self._save_sync_metadata()
                
                duration = time.time() - start_time
                logger.info(f"\n✅ SYNCHRONISATION RÉUSSIE en {duration:.2f}s")
                logger.info(f"   • Documents indexés: {len(documents)}")
                logger.info(f"   • Vector Store: {self.vector_store.get_stats()['num_vectors']} vecteurs")
                
                return True
            else:
                logger.error("❌ Échec de l'indexation")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur synchronisation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _fetch_complete_project_iterative(self, project_name: str) -> Optional[Dict]:
        """
        VERSION CORRIGÉE: Récupération itérative sans @recurse
        Récupère la hiérarchie niveau par niveau
        """
        try:
            # Requête à profondeur fixe (jusqu'à 10 niveaux)
            query = f"""
            {{
              project(func: eq(name, "{project_name}")) {{
                uid
                name
                description
                createdAt
                updatedAt
                
                typologies(orderasc: position) {{
                  uid
                  name
                  description
                  position
                  createdAt
                  updatedAt
                  
                  clusters(orderasc: position) {{
                    uid
                    name
                    description
                    position
                    createdAt
                    updatedAt
                    
                    rootLabels(orderasc: position) {{
                      uid
                      name
                      description
                      category
                      position
                      createdAt
                      updatedAt
                      intentKeywords
                      actionKeywords
                      entityType
                      uiComponent
                      contextDescription
                      examplePrompts
                      
                      children(orderasc: position) {{
                        uid
                        name
                        description
                        category
                        depth
                        position
                        intentKeywords
                        actionKeywords
                        
                        children {{
                          uid
                          name
                          description
                          category
                          depth
                          position
                          
                          children {{
                            uid
                            name
                            description
                            category
                            depth
                            position
                            
                            children {{
                              uid
                              name
                              description
                              category
                              depth
                              position
                              
                              children {{
                                uid
                                name
                                description
                                category
                                depth
                                position
                                
                                children {{
                                  uid
                                  name
                                  description
                                  category
                                  depth
                                  position
                                  
                                  children {{
                                    uid
                                    name
                                    description
                                    category
                                    depth
                                    position
                                    
                                    children {{
                                      uid
                                      name
                                      description
                                      category
                                      depth
                                      position
                                      
                                      children {{
                                        uid
                                        name
                                        description
                                        category
                                        depth
                                        position
                                        
                                        children {{
                                          uid
                                          name
                                          description
                                          category
                                          depth
                                          position
                                        }}
                                      }}
                                    }}
                                  }}
                                }}
                              }}
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            
            txn = self.dgraph.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            projects = data.get('project', [])
            
            if projects:
                return projects[0]
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération Dgraph: {e}")
            return None
    
    def _extract_documents_from_dgraph(self, project_data: Dict) -> List[Dict]:
        """
        Extrait tous les documents de la hiérarchie
        """
        documents = []
        project_name = project_data.get('name', 'Unknown')
        
        # Parcourir toute la hiérarchie
        for typo in project_data.get('typologies', []):
            typo_name = typo.get('name', '')
            
            # Document pour la typologie
            documents.append({
                'uid': typo['uid'],
                'id': f"typo_{typo['uid']}",
                'name': typo_name,
                'domain': project_name,
                'type': 'typologie',
                'description': typo.get('description', ''),
                'variables': typo_name,
                'content': f"Typologie: {typo_name}. {typo.get('description', '')}",
                'metadata': {
                    'dgraph_uid': typo['uid'],
                    'createdAt': typo.get('createdAt'),
                    'updatedAt': typo.get('updatedAt')
                }
            })
            
            # Parcourir les clusters
            for cluster in typo.get('clusters', []):
                cluster_name = cluster.get('name', '')
                
                documents.append({
                    'uid': cluster['uid'],
                    'id': f"cluster_{cluster['uid']}",
                    'name': cluster_name,
                    'domain': project_name,
                    'type': 'cluster',
                    'description': cluster.get('description', ''),
                    'variables': f"{typo_name} {cluster_name}",
                    'content': f"Cluster: {cluster_name} dans {typo_name}. {cluster.get('description', '')}",
                    'metadata': {
                        'dgraph_uid': cluster['uid'],
                        'typologie': typo_name,
                        'createdAt': cluster.get('createdAt'),
                        'updatedAt': cluster.get('updatedAt')
                    }
                })
                
                # Parcourir les root labels
                for root in cluster.get('rootLabels', []):
                    root_name = root.get('name', '')
                    
                    # Enrichir avec keywords
                    intent_kw = root.get('intentKeywords', [])
                    action_kw = root.get('actionKeywords', [])
                    
                    content_parts = [
                        f"Root Label: {root_name}",
                        f"Cluster: {cluster_name}",
                        f"Typologie: {typo_name}",
                        f"Category: {root.get('category', 'default')}",
                        root.get('description', ''),
                        root.get('contextDescription', '')
                    ]
                    
                    if intent_kw:
                        content_parts.append(f"Intentions: {', '.join(intent_kw)}")
                    if action_kw:
                        content_parts.append(f"Actions: {', '.join(action_kw)}")
                    
                    documents.append({
                        'uid': root['uid'],
                        'id': f"root_{root['uid']}",
                        'name': root_name,
                        'domain': project_name,
                        'type': 'root_label',
                        'description': root.get('description', ''),
                        'variables': f"{typo_name} {cluster_name} {root_name}",
                        'content': ' '.join(filter(None, content_parts)),
                        'metadata': {
                            'dgraph_uid': root['uid'],
                            'typologie': typo_name,
                            'cluster': cluster_name,
                            'category': root.get('category', 'default'),
                            'intentKeywords': intent_kw,
                            'actionKeywords': action_kw,
                            'entityType': root.get('entityType'),
                            'uiComponent': root.get('uiComponent'),
                            'examplePrompts': root.get('examplePrompts', []),
                            'createdAt': root.get('createdAt'),
                            'updatedAt': root.get('updatedAt')
                        }
                    })
                    
                    # Parcourir les enfants récursivement
                    self._extract_children_documents(
                        root.get('children', []),
                        documents,
                        project_name,
                        typo_name,
                        cluster_name,
                        root_name,
                        []
                    )
        
        return documents
    
    def _extract_children_documents(
        self,
        children: List[Dict],
        documents: List[Dict],
        project_name: str,
        typo_name: str,
        cluster_name: str,
        root_name: str,
        path: List[str]
    ):
        """Extrait récursivement les documents des enfants"""
        for child in children:
            child_name = child.get('name', '')
            current_path = path + [child_name]
            
            # Enrichir avec metadata
            intent_kw = child.get('intentKeywords', [])
            action_kw = child.get('actionKeywords', [])
            
            content_parts = [
                f"Child Label: {child_name}",
                f"Path: {' > '.join(current_path)}",
                f"Depth: {child.get('depth', 0)}",
                f"Category: {child.get('category', 'default')}",
                child.get('description', ''),
                child.get('contextDescription', '')
            ]
            
            if intent_kw:
                content_parts.append(f"Intentions: {', '.join(intent_kw)}")
            if action_kw:
                content_parts.append(f"Actions: {', '.join(action_kw)}")
            
            documents.append({
                'uid': child['uid'],
                'id': f"child_{child['uid']}",
                'name': child_name,
                'domain': project_name,
                'type': 'child_label',
                'description': child.get('description', ''),
                'variables': f"{typo_name} {cluster_name} {root_name} {' '.join(current_path)}",
                'content': ' '.join(filter(None, content_parts)),
                'metadata': {
                    'dgraph_uid': child['uid'],
                    'typologie': typo_name,
                    'cluster': cluster_name,
                    'root': root_name,
                    'path': current_path,
                    'depth': child.get('depth', 0),
                    'category': child.get('category', 'default'),
                    'intentKeywords': intent_kw,
                    'actionKeywords': action_kw,
                    'createdAt': child.get('createdAt'),
                    'updatedAt': child.get('updatedAt')
                }
            })
            
            # Récursion
            if 'children' in child:
                self._extract_children_documents(
                    child['children'],
                    documents,
                    project_name,
                    typo_name,
                    cluster_name,
                    root_name,
                    current_path
                )

    def _index_documents_with_embeddings_validated(self, documents: List[Dict]) -> bool:
        """
        Indexe les documents avec validation RRF pour détecter les doublons
        """
        try:
            logger.info(f"🧮 Indexation avec validation RRF: {len(documents)} documents...")

            embeddings_list = []
            metadata_list = []
            warnings = []

            from context_weaver.services.hybrid_fusion import HybridFusion
            fusion = HybridFusion()

            for i, doc in enumerate(documents, 1):
                # 1. Générer embedding
                combined_text = " ".join(filter(None, [
                    doc.get('name', ''),
                    doc.get('description', ''),
                    doc.get('variables', ''),
                    doc.get('content', '')[:500],
                ]))

                embeddings = self.oss_client.generate_embeddings(combined_text)

                # 2. Validation RRF si >= 10 docs déjà indexés
                if len(embeddings_list) >= 10:
                    # Créer un vector store temporaire avec les docs déjà traités
                    import numpy as np
                    temp_embeddings = np.array(embeddings_list)

                    # Dense retrieval simulé (recherche dans les embeddings existants)
                    # Calculer similarité cosine avec tous les embeddings existants
                    from numpy.linalg import norm
                    similarities = []
                    for existing_emb in embeddings_list:
                        sim = np.dot(embeddings, existing_emb) / (norm(embeddings) * norm(existing_emb))
                        similarities.append(sim)

                    # Top-10 plus similaires
                    top_indices = np.argsort(similarities)[-10:][::-1]
                    dense_results = []

                    from context_weaver.models.schemas import SearchResult
                    for rank, idx in enumerate(top_indices, 1):
                        dense_results.append(SearchResult(
                            id=metadata_list[idx]['id'],
                            name=metadata_list[idx]['name'],
                            domain=metadata_list[idx]['domain'],
                            type=metadata_list[idx]['type'],
                            score=similarities[idx],
                            method="dense"
                        ))

                    # BM25 retrieval simulé (recherche textuelle simple)
                    bm25_results = []
                    doc_words = set(combined_text.lower().split())

                    for idx, meta in enumerate(metadata_list):
                        existing_text = meta.get('name', '') + ' ' + meta.get('description', '')
                        existing_words = set(existing_text.lower().split())
                        overlap = len(doc_words & existing_words)

                        if overlap > 0:
                            bm25_results.append(SearchResult(
                                id=meta['id'],
                                name=meta['name'],
                                domain=meta['domain'],
                                type=meta['type'],
                                score=overlap / len(doc_words | existing_words),
                                method="bm25"
                            ))

                    bm25_results.sort(key=lambda x: x.score, reverse=True)
                    bm25_results = bm25_results[:10]

                    # RRF fusion
                    if dense_results and bm25_results:
                        hybrid_results = fusion.fuse(bm25_results, dense_results)

                        if hybrid_results.results:
                            top_match = hybrid_results.results[0]

                            # Calculer similarité de nom
                            import difflib
                            name_similarity = difflib.SequenceMatcher(
                                None,
                                doc['name'].lower(),
                                top_match.name.lower()
                            ).ratio()

                            # Warning si très similaire
                            if name_similarity > 0.85 and top_match.score > 0.7:
                                warnings.append({
                                    'doc': doc['name'],
                                    'similar_to': top_match.name,
                                    'name_similarity': name_similarity,
                                    'rrf_score': top_match.score,
                                    'recommendation': 'POTENTIAL_DUPLICATE'
                                })
                                logger.warning(
                                    f"   ⚠️ Doublon potentiel: {doc['name']} ≈ "
                                    f"{top_match.name} (sim={name_similarity:.2f}, RRF={top_match.score:.2f})"
                                )

                # 3. Ajouter aux listes
                embeddings_list.append(embeddings)

                metadata = {
                    'id': doc['id'],
                    'uid': doc['uid'],
                    'name': doc['name'],
                    'domain': doc['domain'],
                    'type': doc['type'],
                    'description': doc.get('description', ''),
                    'dgraph_metadata': doc.get('metadata', {})
                }
                metadata_list.append(metadata)

                if i % 10 == 0:
                    logger.info(f"  Progression: {i}/{len(documents)}")

            # 4. Indexation finale
            self.embedding_search.index_documents_from_embeddings(
                embeddings_list,
                metadata_list
            )

            # 5. Sauvegarder warnings
            if warnings:
                warnings_path = Path("./data/indexation_warnings.json")
                warnings_path.parent.mkdir(parents=True, exist_ok=True)

                import json
                with open(warnings_path, 'w') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'total_warnings': len(warnings),
                        'warnings': warnings
                    }, f, indent=2)

                logger.info(f"⚠️ {len(warnings)} warnings sauvegardés: {warnings_path}")
            else:
                logger.info("✅ Aucun doublon détecté!")

            logger.info(f"✅ {len(documents)} documents indexés avec validation RRF")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur indexation validée: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _index_documents_with_embeddings(self, documents: List[Dict]) -> bool:
        """
        Génère les embeddings et indexe dans le Vector Store
        """
        try:
            logger.info(f"🧮 Génération des embeddings pour {len(documents)} documents...")
            
            embeddings_list = []
            metadata_list = []
            
            for i, doc in enumerate(documents, 1):
                # Construire le texte combiné
                combined_text = " ".join(filter(None, [
                    doc.get('name', ''),
                    doc.get('description', ''),
                    doc.get('variables', ''),
                    doc.get('content', '')[:500],
                ]))
                
                # Générer embeddings via OSS
                embeddings = self.oss_client.generate_embeddings(combined_text)
                embeddings_list.append(embeddings)
                
                # Préparer metadata
                metadata = {
                    'id': doc['id'],
                    'uid': doc['uid'],
                    'name': doc['name'],
                    'domain': doc['domain'],
                    'type': doc['type'],
                    'description': doc.get('description', ''),
                    'dgraph_metadata': doc.get('metadata', {})
                }
                metadata_list.append(metadata)
                
                if i % 10 == 0:
                    logger.info(f"  Progression: {i}/{len(documents)}")
            
            # Indexer dans Vector Store
            self.embedding_search.index_documents_from_embeddings(
                embeddings_list,
                metadata_list
            )
            
            logger.info(f"✅ {len(documents)} documents indexés dans le Vector Store")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur génération embeddings: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def incremental_sync(self, project_name: str) -> bool:
        """Synchronisation incrémentale (placeholder)"""
        logger.warning("⚠️  Sync incrémentale non implémentée, utilisation full_sync")
        return self.full_sync(project_name)
    
    def on_node_created(self, node_uid: str, project_name: str):
        """Callback création nœud"""
        logger.info(f"🆕 Nouveau nœud créé: {node_uid}")
    
    def on_node_updated(self, node_uid: str, project_name: str):
        """Callback mise à jour nœud"""
        logger.info(f"🔄 Nœud mis à jour: {node_uid}")
    
    def on_node_deleted(self, node_uid: str):
        """Callback suppression nœud"""
        logger.info(f"🗑️  Nœud supprimé: {node_uid}")
    
    def _load_sync_metadata(self):
        """Charge les métadonnées de synchronisation"""
        if self.sync_metadata_path.exists():
            try:
                with open(self.sync_metadata_path, 'r') as f:
                    data = json.load(f)
                    self.last_sync_time = data.get('last_sync_time')
                    self.indexed_uids = set(data.get('indexed_uids', []))
                    logger.info(f"📥 Métadonnées chargées: {len(self.indexed_uids)} UIDs")
            except Exception as e:
                logger.warning(f"⚠️  Erreur chargement metadata: {e}")
    
    def _save_sync_metadata(self):
        """Sauvegarde les métadonnées de synchronisation"""
        try:
            self.sync_metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'last_sync_time': self.last_sync_time,
                'indexed_uids': list(self.indexed_uids),
                'total_indexed': len(self.indexed_uids)
            }
            
            with open(self.sync_metadata_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info("💾 Métadonnées sauvegardées")
            
        except Exception as e:
            logger.warning(f"⚠️  Erreur sauvegarde metadata: {e}")
    
    def get_sync_status(self) -> Dict:
        """Retourne le statut de la synchronisation"""
        return {
            'last_sync': self.last_sync_time,
            'indexed_count': len(self.indexed_uids),
            'vector_store_count': self.vector_store.get_stats()['num_vectors']
        }


def init_dgraph_vector_sync(
    dgraph_connector,
    vector_store,
    embedding_search,
    oss_client,
    project_name: str,
    force_full_sync: bool = False
) -> DgraphVectorSync:
    """
    Initialise la synchronisation
    """
    logger.info("=" * 80)
    logger.info("🚀 INITIALISATION SYNCHRONISATION DGRAPH → VECTOR STORE")
    logger.info("=" * 80)
    
    syncer = DgraphVectorSync(
        dgraph_connector,
        vector_store,
        embedding_search,
        oss_client
    )
    
    if force_full_sync or not syncer.last_sync_time:
        logger.info("📊 Synchronisation complète...")
        syncer.full_sync(project_name)
    else:
        logger.info("🔄 Synchronisation incrémentale...")
        syncer.incremental_sync(project_name)
    
    status = syncer.get_sync_status()
    logger.info("\n📈 STATUT DE SYNCHRONISATION")
    logger.info(f"  • Dernière sync: {status['last_sync']}")
    logger.info(f"  • Documents indexés: {status['indexed_count']}")
    logger.info(f"  • Vector Store: {status['vector_store_count']} vecteurs")
    logger.info("=" * 80 + "\n")
    
    return syncer