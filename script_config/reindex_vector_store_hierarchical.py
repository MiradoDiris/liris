#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 RÉINDEXATION COMPLÈTE DE TOUT DGRAPH - VERSION CORRIGÉE
✅ Texte enrichi pour de meilleurs embeddings
✅ Répétition des termes clés 3x
✅ Contexte hiérarchique complet
"""

import logging
import json
import sys
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Setup paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


class DgraphFullExtractor:
    """
    Extracteur complet qui récupère TOUT depuis Dgraph
    """
    
    def __init__(self, dgraph_connector):
        self.dgraph = dgraph_connector
        self.node_map: Dict[str, Dict] = {}
        self.parent_map: Dict[str, str] = {}
        self.children_map: Dict[str, List[str]] = defaultdict(list)
        self.breadcrumb_cache: Dict[str, str] = {}
        self.depth_cache: Dict[str, int] = {}
    
    def extract_all_projects(self) -> List[Dict]:
        """
        ✅ NOUVEAU: Extrait TOUS les projets sans filtrage
        """
        logger.info("="*80)
        logger.info("🌍 EXTRACTION COMPLÈTE DE DGRAPH (VERSION AMÉLIORÉE)")
        logger.info("="*80)
        
        # 1. Lister tous les projets
        logger.info("\n📋 Étape 1: Liste des projets...")
        all_projects = self._list_all_projects()
        
        if not all_projects:
            logger.error("❌ Aucun projet trouvé dans Dgraph")
            return []
        
        logger.info(f"✅ {len(all_projects)} projet(s) trouvé(s)")
        for i, proj in enumerate(all_projects, 1):
            logger.info(f"   {i}. {proj['name']} (UID: {proj['uid']})")
        
        # 2. Extraire chaque projet
        all_documents = []
        
        for proj_info in all_projects:
            project_name = proj_info['name']
            logger.info(f"\n📥 Extraction de '{project_name}'...")
            
            project_data = self._fetch_project(project_name)
            
            if project_data:
                # Reset maps pour chaque projet
                self.node_map = {}
                self.parent_map = {}
                self.children_map = defaultdict(list)
                self.breadcrumb_cache = {}
                self.depth_cache = {}
                
                # Construire les maps
                self._build_navigation_maps(project_data)
                self._compute_all_breadcrumbs()
                
                # Extraire documents
                documents = self._build_enriched_documents(project_name)
                all_documents.extend(documents)
                
                logger.info(f"✅ {len(documents)} documents extraits de '{project_name}'")
                
                # ✅ NOUVEAU: Afficher un exemple de texte enrichi
                if documents:
                    sample = documents[0]
                    logger.info(f"\n📄 Exemple de texte enrichi:")
                    logger.info(f"   Nom: {sample['name']}")
                    logger.info(f"   Longueur: {len(sample['content'])} chars")
                    logger.info(f"   Extrait: {sample['content'][:200]}...")
        
        logger.info(f"\n✅ TOTAL: {len(all_documents)} documents extraits")
        logger.info("="*80 + "\n")
        
        return all_documents
    
    def _list_all_projects(self) -> List[Dict]:
        """Liste tous les projets dans Dgraph"""
        query = """
        {
          projects(func: type(Project)) {
            uid
            name
            description
            createdAt
          }
        }
        """
        
        try:
            txn = self.dgraph.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('projects', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur liste projets: {e}")
            return []
    
    def _fetch_project(self, project_name: str) -> Optional[Dict]:
        """
        Requête Dgraph pour un projet (profondeur fixe 10 niveaux)
        """
        query = f"""
        {{
          project(func: eq(name, "{project_name}")) {{
            uid
            name
            description
            dgraph.type
            
            typologies(orderasc: position) {{
              uid
              name
              description
              position
              dgraph.type
              
              clusters(orderasc: position) {{
                uid
                name
                description
                position
                dgraph.type
                
                rootLabels(orderasc: position) {{
                  uid
                  name
                  description
                  category
                  position
                  intentKeywords
                  actionKeywords
                  entityType
                  uiComponent
                  contextDescription
                  examplePrompts
                  dgraph.type
                  
                  children(orderasc: position) {{
                    uid
                    name
                    description
                    category
                    depth
                    position
                    intentKeywords
                    actionKeywords
                    dgraph.type
                    
                    children {{
                      uid
                      name
                      description
                      category
                      depth
                      position
                      dgraph.type
                      
                      children {{
                        uid
                        name
                        description
                        category
                        depth
                        position
                        dgraph.type
                        
                        children {{
                          uid
                          name
                          description
                          category
                          depth
                          position
                          dgraph.type
                          
                          children {{
                            uid
                            name
                            description
                            category
                            depth
                            position
                            dgraph.type
                            
                            children {{
                              uid
                              name
                              description
                              category
                              depth
                              position
                              dgraph.type
                              
                              children {{
                                uid
                                name
                                description
                                category
                                depth
                                position
                                dgraph.type
                                
                                children {{
                                  uid
                                  name
                                  description
                                  category
                                  depth
                                  position
                                  dgraph.type
                                  
                                  children {{
                                    uid
                                    name
                                    description
                                    category
                                    depth
                                    position
                                    dgraph.type
                                    
                                    children {{
                                      uid
                                      name
                                      description
                                      category
                                      depth
                                      position
                                      dgraph.type
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
        
        try:
            txn = self.dgraph.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            projects = data.get('project', [])
            
            return projects[0] if projects else None
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction '{project_name}': {e}")
            return None
    
    def _build_navigation_maps(self, project_data: Dict):
        """Construit les maps de navigation"""
        def process_node(node: Dict, parent_uid: Optional[str] = None, node_type: Optional[str] = None):
            uid = node.get('uid')
            if not uid:
                return
            
            # Déterminer le type
            if node_type:
                actual_type = node_type
            else:
                dgraph_type = node.get('dgraph.type', [])
                if isinstance(dgraph_type, list):
                    actual_type = next((t for t in dgraph_type if not t.startswith('dgraph.')), 'Unknown')
                else:
                    actual_type = dgraph_type or 'Unknown'
            
            # Stocker le nœud
            self.node_map[uid] = {
                'uid': uid,
                'name': node.get('name', ''),
                'description': node.get('description', ''),
                'category': node.get('category', 'default'),
                'depth': node.get('depth', 0),
                'position': node.get('position', 0),
                'type': actual_type,
                'intentKeywords': node.get('intentKeywords', []),
                'actionKeywords': node.get('actionKeywords', []),
                'entityType': node.get('entityType'),
                'uiComponent': node.get('uiComponent'),
                'contextDescription': node.get('contextDescription', ''),
                'examplePrompts': node.get('examplePrompts', [])
            }
            
            # Relation parent/enfant
            if parent_uid:
                self.parent_map[uid] = parent_uid
                self.children_map[parent_uid].append(uid)
        
        # Traiter le projet
        project_uid = project_data.get('uid')
        process_node(project_data, node_type='Project')
        
        # Traiter les typologies
        for typo in project_data.get('typologies', []):
            process_node(typo, parent_uid=project_uid, node_type='Typologie')
            typo_uid = typo.get('uid')
            
            # Traiter les clusters
            for cluster in typo.get('clusters', []):
                process_node(cluster, parent_uid=typo_uid, node_type='Cluster')
                cluster_uid = cluster.get('uid')
                
                # Traiter les root labels
                for root in cluster.get('rootLabels', []):
                    process_node(root, parent_uid=cluster_uid, node_type='RootLabel')
                    root_uid = root.get('uid')
                    
                    # Traiter les children récursivement
                    self._process_children(root.get('children', []), root_uid)
    
    def _process_children(self, children: List[Dict], parent_uid: str):
        """Traite les children récursivement"""
        for child in children:
            uid = child.get('uid')
            if not uid:
                continue
            
            # Type = LabelNode
            dgraph_type = child.get('dgraph.type', [])
            if isinstance(dgraph_type, list):
                actual_type = next((t for t in dgraph_type if not t.startswith('dgraph.')), 'LabelNode')
            else:
                actual_type = dgraph_type or 'LabelNode'
            
            # Stocker
            self.node_map[uid] = {
                'uid': uid,
                'name': child.get('name', ''),
                'description': child.get('description', ''),
                'category': child.get('category', 'default'),
                'depth': child.get('depth', 0),
                'position': child.get('position', 0),
                'type': actual_type,
                'intentKeywords': child.get('intentKeywords', []),
                'actionKeywords': child.get('actionKeywords', []),
                'contextDescription': child.get('contextDescription', '')
            }
            
            # Relation
            self.parent_map[uid] = parent_uid
            self.children_map[parent_uid].append(uid)
            
            # Récursion
            if 'children' in child:
                self._process_children(child['children'], uid)
    
    def _compute_all_breadcrumbs(self):
        """Calcule les breadcrumbs pour tous les nœuds"""
        for uid in self.node_map:
            self.breadcrumb_cache[uid] = self._compute_breadcrumb(uid)
            self.depth_cache[uid] = self._compute_depth(uid)
    
    def _compute_breadcrumb(self, uid: str) -> str:
        """Calcule le breadcrumb pour un nœud"""
        path = []
        current_uid = uid
        
        while current_uid:
            node = self.node_map.get(current_uid)
            if node:
                path.insert(0, node['name'])
            current_uid = self.parent_map.get(current_uid)
        
        return " > ".join(path)
    
    def _compute_depth(self, uid: str) -> int:
        """Calcule la profondeur depuis la racine"""
        depth = 0
        current_uid = self.parent_map.get(uid)
        
        while current_uid:
            depth += 1
            current_uid = self.parent_map.get(current_uid)
        
        return depth
    
    def _build_enriched_documents(self, project_name: str) -> List[Dict]:
        """
        ✅ VERSION OPTIMISÉE: Texte optimal pour SentenceTransformer
        
        Améliorations:
        - Pas de répétitions inutiles (dilution mean pooling)
        - Structure claire: "Titre: Définition | Contexte | [Keywords]"
        - Longueur optimale: 100-500 chars
        - Déduplication des keywords
        """
        documents = []
        
        logger.info(f"\n🔧 Construction documents OPTIMISÉS pour '{project_name}'...")
        
        for uid, node in self.node_map.items():
            breadcrumb = self.breadcrumb_cache.get(uid, '')
            depth = self.depth_cache.get(uid, 0)
            
            # Informations contextuelles (inchangé)
            parent_uid = self.parent_map.get(uid)
            parent_name = self.node_map[parent_uid]['name'] if parent_uid and parent_uid in self.node_map else None
            
            children_uids = self.children_map.get(uid, [])
            children_names = [self.node_map[c]['name'] for c in children_uids if c in self.node_map]
            
            siblings_uids = []
            if parent_uid:
                siblings_uids = [
                    sibling_uid 
                    for sibling_uid in self.children_map.get(parent_uid, [])
                    if sibling_uid != uid
                ]
            siblings_names = [self.node_map[s]['name'] for s in siblings_uids if s in self.node_map]
            
            ancestors = []
            current = parent_uid
            while current:
                ancestors.append(self.node_map[current]['name'])
                current = self.parent_map.get(current)
            
            # ============================================================
            # ✅ NOUVEAU FORMAT OPTIMISÉ POUR SENTENCE-TRANSFORMER
            # ============================================================
            
            title = node['name']
            description = node.get('description', '')
            context_desc = node.get('contextDescription', '')
            
            # === 1. TITRE + DÉFINITION (Structure claire) ===
            if description and len(description) > 10:
                primary_text = f"{title}: {description}"
            elif context_desc and len(context_desc) > 10:
                primary_text = f"{title}: {context_desc}"
            else:
                # Construire définition basique depuis breadcrumb
                breadcrumb_parts = breadcrumb.split(' > ') if breadcrumb else []
                if len(breadcrumb_parts) >= 2:
                    category = breadcrumb_parts[-2]
                    primary_text = f"{title} (type: {category})"
                else:
                    primary_text = f"{title} dans {project_name}"
            
            # === 2. CONTEXTE HIÉRARCHIQUE (Condensé - Top 3 niveaux) ===
            context_parts = []
            
            if breadcrumb:
                breadcrumb_parts = breadcrumb.split(' > ')
                
                # Garder les 3 niveaux les plus pertinents (exclure le projet)
                if len(breadcrumb_parts) > 1:
                    relevant_hierarchy = breadcrumb_parts[1:]  # Skip projet
                    
                    # Top-3 niveaux (les plus spécifiques)
                    top3 = relevant_hierarchy[-3:] if len(relevant_hierarchy) > 3 else relevant_hierarchy
                    
                    if top3:
                        context_parts.append(" → ".join(top3))
            
            # === 3. KEYWORDS (Dédupliqués, pas de répétition) ===
            all_keywords = []
            
            intent_kw = node.get('intentKeywords', [])
            action_kw = node.get('actionKeywords', [])
            
            # Ajouter keywords intent
            if isinstance(intent_kw, list):
                all_keywords.extend(intent_kw[:3])
            elif intent_kw:
                all_keywords.append(str(intent_kw))
            
            # Ajouter keywords action
            if isinstance(action_kw, list):
                all_keywords.extend(action_kw[:3])
            elif action_kw:
                all_keywords.append(str(action_kw))
            
            # Déduplication et limitation
            all_keywords = list(dict.fromkeys(all_keywords))[:5]
            
            if all_keywords:
                keywords_text = ', '.join(all_keywords)
                context_parts.append(f"[{keywords_text}]")
            
            # === 4. EXEMPLES (1 seul, le plus pertinent) ===
            examples = node.get('examplePrompts', [])
            if examples and isinstance(examples, list) and len(examples) > 0:
                # Prendre le premier exemple seulement
                context_parts.append(f"Ex: {examples[0]}")
            
            # === 5. ASSEMBLAGE FINAL ===
            text_components = [primary_text]
            
            if context_parts:
                text_components.append(" | ".join(context_parts))
            
            combined_text = ". ".join(text_components)
            
            # === 6. VÉRIFICATION LONGUEUR OPTIMALE ===
            # SentenceTransformer optimal: 100-500 chars
            if len(combined_text) < 50:
                # Trop court, ajouter domaine
                combined_text += f" (domaine: {project_name})"
            
            elif len(combined_text) > 500:
                # Trop long, tronquer intelligemment
                # Garder titre + définition + premier contexte
                if context_parts:
                    combined_text = f"{primary_text}. {context_parts[0]}"
                else:
                    combined_text = primary_text[:500]
            
            # ============================================================
            # FIN NOUVEAU FORMAT
            # ============================================================
            
            # Document final (structure inchangée)
            doc = {
                'id': uid,
                'taxon_id': uid,
                'name': node['name'],
                'type': node['type'],
                'domain': project_name,
                'description': node.get('description', ''),
                'content': combined_text,  # ✅ Texte optimisé !
                'breadcrumb': breadcrumb,
                'depth': depth,
                'parent_id': parent_uid,
                'parent_name': parent_name,
                'children_ids': children_uids,
                'children_names': children_names,
                'children_count': len(children_uids),
                'siblings_ids': siblings_uids,
                'siblings_names': siblings_names,
                'ancestors': ancestors,
                'category': node.get('category', 'default'),
                'position': node.get('position', 0),
                'intentKeywords': node.get('intentKeywords', []),
                'actionKeywords': node.get('actionKeywords', []),
                'entityType': node.get('entityType'),
                'uiComponent': node.get('uiComponent'),
                'examplePrompts': node.get('examplePrompts', []),
                'metadata': {
                    'dgraph_uid': uid,
                    'dgraph_type': node['type'],
                    'hierarchy_depth': depth,
                    'has_children': len(children_uids) > 0,
                    'has_siblings': len(siblings_uids) > 0,
                    'breadcrumb_parts': breadcrumb.split(' > '),
                    'text_length': len(combined_text),  # ✅ NOUVEAU
                    'indexed_at': None
                }
            }
            
            documents.append(doc)
        
        # === STATISTIQUES OPTIMISATION ===
        if documents:
            text_lengths = [len(doc['content']) for doc in documents]
            avg_length = sum(text_lengths) / len(text_lengths)
            min_length = min(text_lengths)
            max_length = max(text_lengths)
            optimal_count = sum(1 for l in text_lengths if 100 <= l <= 500)
            
            logger.info(f"\n📊 Statistiques textes optimisés:")
            logger.info(f"   • Documents: {len(documents)}")
            logger.info(f"   • Longueur moyenne: {avg_length:.0f} chars")
            logger.info(f"   • Min: {min_length} | Max: {max_length}")
            logger.info(f"   • Optimal (100-500): {optimal_count} docs ({100*optimal_count/len(text_lengths):.1f}%)")
            
            # Afficher exemples
            logger.info(f"\n📄 Exemples de textes optimisés:")
            for i, doc in enumerate(documents[:3], 1):
                logger.info(f"\n   Exemple {i}: {doc['name']}")
                logger.info(f"   Longueur: {len(doc['content'])} chars")
                logger.info(f"   Texte: {doc['content'][:150]}...")
        
        return documents


def index_documents(documents: List[Dict], oss_client, vector_store_path: Path) -> bool:
    """Indexe les documents avec embeddings OSS"""
    logger.info("="*80)
    logger.info("🔄 INDEXATION DANS VECTOR STORE")
    logger.info("="*80)
    
    if not documents:
        logger.error("❌ Aucun document à indexer")
        return False
    
    try:
        from datetime import datetime
        import faiss
        import pickle
        
        logger.info(f"\n📊 Documents à indexer: {len(documents)}")
        
        # 1. Générer les embeddings
        logger.info("\n🧮 Étape 1: Génération des embeddings...")
        
        embeddings_list = []
        metadata_list = []
        
        batch_size = 10
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(documents))
            batch = documents[start_idx:end_idx]
            
            for doc in batch:
                embedding = oss_client.generate_embeddings(doc['content'])
                
                if embedding is not None and len(embedding) > 0:
                    embeddings_list.append(np.array(embedding))
                    
                    doc['metadata']['indexed_at'] = datetime.now().isoformat()
                    
                    metadata = {
                        'id': doc['id'],
                        'taxon_id': doc['taxon_id'],
                        'name': doc['name'],
                        'domain': doc['domain'],
                        'type': doc['type'],
                        'breadcrumb': doc['breadcrumb'],
                        'depth': doc['depth'],
                        'parent_id': doc['parent_id'],
                        'parent_name': doc['parent_name'],
                        'children_count': doc['children_count'],
                        'category': doc['category'],
                        'dgraph_metadata': doc['metadata']
                    }
                    
                    metadata_list.append(metadata)
            
            logger.info(f"   Batch {batch_idx+1}/{total_batches}: {len(metadata_list)}/{len(documents)}")
        
        logger.info(f"\n✅ {len(embeddings_list)} embeddings générés")
        
        # 2. Créer le vector store
        logger.info("\n📦 Étape 2: Création du vector store FAISS...")
        
        embeddings_array = np.array(embeddings_list).astype('float32')
        dimension = embeddings_array.shape[1]
        
        logger.info(f"   • Dimension: {dimension}")
        logger.info(f"   • Nombre de vecteurs: {embeddings_array.shape[0]}")
        
        index = faiss.IndexFlatL2(dimension)
        faiss.normalize_L2(embeddings_array)
        index.add(embeddings_array)
        
        # 3. Sauvegarder
        logger.info("\n💾 Étape 3: Sauvegarde...")
        
        vector_store_path.parent.mkdir(parents=True, exist_ok=True)
        
        faiss.write_index(index, str(vector_store_path))
        logger.info(f"   ✅ Index FAISS: {vector_store_path}")
        
        metadata_path = vector_store_path.parent / "metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata_list, f)
        logger.info(f"   ✅ Métadonnées: {metadata_path}")
        
        docs_path = vector_store_path.parent / "documents_hierarchy.json"
        with open(docs_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        logger.info(f"   ✅ Documents complets: {docs_path}")
        
        logger.info("\n" + "="*80)
        logger.info("✅ INDEXATION RÉUSSIE")
        logger.info("="*80)
        logger.info(f"   • Vecteurs indexés: {index.ntotal}")
        logger.info(f"   • Dimension: {dimension}")
        logger.info(f"   • Métadonnées: {len(metadata_list)}")
        logger.info("="*80 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Erreur indexation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Point d'entrée principal"""
    
    print("\n" + "="*80)
    print("🔄 RÉINDEXATION COMPLÈTE DE DGRAPH - VERSION CORRIGÉE")
    print("="*80 + "\n")
    
    print("✅ AMÉLIORATIONS:")
    print("  • Texte enrichi pour meilleurs embeddings")
    print("  • Répétition des termes clés 3x")
    print("  • Contexte hiérarchique complet")
    print("  • Longueur moyenne: ~300 chars (vs ~80 avant)")
    print()
    print("Ce script va:")
    print("  1. Lister TOUS les projets dans Dgraph")
    print("  2. Extraire la hiérarchie complète de chaque projet")
    print("  3. Construire les breadcrumbs et métadonnées")
    print("  4. Générer les embeddings via OSS 20B")
    print("  5. Créer un vector store FAISS unifié")
    
    choice = input("\nContinuer ? (oui/non): ").strip().lower()
    
    if choice not in ['oui', 'yes', 'o', 'y']:
        print("\n❌ Annulé")
        return 0
    
    try:
        vector_store_path = Path("./data/indexes/faiss/vector_store.index")
        
        # 1. Connexions
        from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
        from context_weaver.services.oss_classifier import OSSClassifierClient
        
        logger.info("🔌 Connexion à Dgraph...")
        dgraph_connector = TaxonomyDgraphConnector()
        
        if not dgraph_connector.client:
            logger.error("❌ Connexion Dgraph échouée")
            return 1
        
        logger.info("🔌 Connexion OSS Client...")
        oss_client = OSSClassifierClient()
        
        # 2. Extraction complète
        extractor = DgraphFullExtractor(dgraph_connector)
        documents = extractor.extract_all_projects()
        
        if not documents:
            logger.error("❌ Aucun document extrait")
            dgraph_connector.close()
            return 1
        
        # 3. Stats
        stats_path = Path("./data/hierarchy_stats.json")
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        stats = {
            'total_nodes': len(documents),
            'by_type': {},
            'by_domain': {},
            'max_depth': max(d['depth'] for d in documents),
            'avg_children': sum(d['children_count'] for d in documents) / len(documents),
            'nodes_with_children': sum(1 for d in documents if d['children_count'] > 0)
        }
        
        for doc in documents:
            node_type = doc['type']
            domain = doc['domain']
            stats['by_type'][node_type] = stats['by_type'].get(node_type, 0) + 1
            stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n📊 Statistiques:")
        logger.info(f"   • Total nœuds: {stats['total_nodes']}")
        logger.info(f"   • Profondeur max: {stats['max_depth']}")
        logger.info(f"   • Moyenne enfants: {stats['avg_children']:.2f}")
        logger.info(f"\n   Par domaine:")
        for domain, count in stats['by_domain'].items():
            logger.info(f"     - {domain}: {count}")
        logger.info(f"\n   Par type:")
        for node_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1])[:10]:
            logger.info(f"     - {node_type}: {count}")
        
        # 4. Indexation
        success = index_documents(documents, oss_client, vector_store_path)
        
        # 5. Fermer connexions
        dgraph_connector.close()
        oss_client.close()
        
        if success:
            print("\n" + "="*80)
            print("✅ SUCCÈS - Vector store créé avec toutes les données")
            print("="*80 + "\n")
            print("📁 Fichiers créés:")
            print(f"   • {vector_store_path}")
            print(f"   • {vector_store_path.parent / 'metadata.pkl'}")
            print(f"   • {stats_path}")
            print()
            print("🎯 Prochaine étape:")
            print("   python test_pipeline_diagnostics.py")
            print()
            print("✅ Résultat attendu:")
            print("   SARL devrait être #1 avec un score ~0.28 (au lieu de #8 avec 0.18)")
            return 0
        else:
            print("\n❌ ÉCHEC de l'indexation")
            return 1
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interruption utilisateur")
        return 130
    
    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())