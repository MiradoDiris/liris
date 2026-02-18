#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 RÉINDEXATION COMPLÈTE DE DGRAPH → CHROMADB
✅ Embeddings via Liris API (http://192.168.0.101:7777)
✅ Stockage dans ChromaDB (persistant)
✅ Texte enrichi avec contexte hiérarchique complet
✅ Compatible avec VectorStore Context Weaver
"""

import logging
import json
import sys
import time
import requests
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

# Setup paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent if current_dir.name == 'script_config' else current_dir
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# LIRIS EMBEDDING CLIENT
# ============================================================================

class LirisEmbedderClient:
    """
    Client pour l'API Liris Embedding (http://localhost:7777)
    
    API:
        POST /api/embeddings
        Body: {"model": "liris", "prompt": "<texte>"}
        Returns: vecteur d'embeddings
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7777",
        model: str = "liris",
        timeout: int = 60,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._embedding_dim: Optional[int] = None

        logger.info(f"✅ LirisEmbedderClient initialisé: {base_url} | modèle: {model}")
        self._check_health()

    def _check_health(self):
        """Vérifie que le service Liris est accessible via un embedding test."""
        try:
            emb = self.generate_embeddings("test de connectivité")
            self._embedding_dim = len(emb)
            logger.info(f"   ✅ Service Liris opérationnel — dimension: {self._embedding_dim}")
        except Exception as e:
            logger.warning(f"   ⚠️  Service Liris non accessible: {e}")
            logger.warning("      Assurez-vous que le service tourne sur 192.168.0.101:7777")

    def generate_embeddings(self, text: str) -> np.ndarray:
        """
        Génère un embedding via l'API Liris.

        Args:
            text: Texte à encoder

        Returns:
            np.ndarray float32 de shape (dim,)
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()

                # L'API peut retourner {"embedding": [...]} ou directement une liste
                if isinstance(data, list):
                    vector = data
                elif isinstance(data, dict):
                    vector = (
                        data.get("embedding")
                        or data.get("embeddings")
                        or data.get("data")
                        or data.get("vector")
                    )
                    if vector is None:
                        raise ValueError(f"Clé d'embedding introuvable dans la réponse: {list(data.keys())}")
                else:
                    raise ValueError(f"Format de réponse inattendu: {type(data)}")

                arr = np.array(vector, dtype=np.float32)
                if self._embedding_dim is None:
                    self._embedding_dim = arr.shape[0]
                return arr

            except requests.exceptions.RequestException as e:
                logger.warning(f"   ⚠️  Tentative {attempt}/{self.retry_attempts} échouée: {e}")
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay * attempt)
                else:
                    logger.error("   ❌ Toutes les tentatives ont échoué — retour vecteur nul")
                    return self._fallback_embedding()

            except Exception as e:
                logger.error(f"   ❌ Erreur inattendue (tentative {attempt}): {e}")
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay)
                else:
                    return self._fallback_embedding()

    def generate_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Encode un batch de textes (appels séquentiels — l'API est mono-texte).

        Args:
            texts: Liste de textes

        Returns:
            Liste de np.ndarray float32
        """
        results = []
        for text in texts:
            emb = self.generate_embeddings(text)
            results.append(emb)
        return results

    def _fallback_embedding(self) -> np.ndarray:
        dim = self._embedding_dim or 768
        logger.warning(f"   ⚠️  Utilisation d'un vecteur nul de dim={dim}")
        return np.zeros(dim, dtype=np.float32)

    @property
    def embedding_dim(self) -> Optional[int]:
        return self._embedding_dim

    def close(self):
        logger.info("✅ LirisEmbedderClient fermé")


# ============================================================================
# CHROMA VECTOR STORE
# ============================================================================

class ChromaVectorStore:
    """
    Wrapper ChromaDB pour le vector store Context Weaver.

    Stocke les documents + embeddings dans une collection persistante.
    Compatible avec le pipeline Context Weaver (BM25 géré séparément si besoin).
    """

    def __init__(
        self,
        persist_dir: str = "./data/indexes/chroma",
        collection_name: str = "context_weaver_taxonomy"
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def initialize(self):
        """Initialise ChromaDB en mode persistant."""
        try:
            import chromadb
            from chromadb.config import Settings

            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(path=self.persist_dir)
            logger.info(f"✅ ChromaDB initialisé: {self.persist_dir}")
        except ImportError:
            raise ImportError(
                "ChromaDB non installé. Exécutez: pip install chromadb"
            )

    def reset_collection(self):
        """Supprime et recrée la collection (réindexation complète)."""
        try:
            self._client.delete_collection(self.collection_name)
            logger.info(f"   🗑️  Collection '{self.collection_name}' supprimée")
        except Exception:
            pass  # N'existe pas encore

        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"   ✅ Collection '{self.collection_name}' créée (cosine similarity)")

    def bulk_insert(
        self,
        documents: List[Dict[str, Any]],
        embeddings: np.ndarray,
        batch_size: int = 100
    ):
        """
        Insère en masse les documents et leurs embeddings dans ChromaDB.

        Args:
            documents: Liste de dicts avec id, name, content, breadcrumb, etc.
            embeddings: np.ndarray float32 de shape (N, dim)
            batch_size: Taille des lots d'insertion
        """
        if self._collection is None:
            raise RuntimeError("Appelez initialize() puis reset_collection() d'abord")

        total = len(documents)
        logger.info(f"   📦 Insertion de {total} documents par batches de {batch_size}...")

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_docs = documents[start:end]
            batch_embs = embeddings[start:end]

            ids = []
            embs = []
            metas = []
            raw_docs = []

            for doc, emb in zip(batch_docs, batch_embs):
                doc_id = str(doc.get('id') or doc.get('taxon_id') or doc.get('uid', f"doc_{start}"))
                ids.append(doc_id)
                embs.append(emb.tolist())
                raw_docs.append(doc.get('content', doc.get('index_text', '')))

                # ChromaDB n'accepte que des valeurs scalaires dans metadata
                meta = {
                    "taxon_id":       str(doc.get('taxon_id', doc_id)),
                    "name":           str(doc.get('name', '')),
                    "domain":         str(doc.get('domain', '')),
                    "type":           str(doc.get('type', '')),
                    "breadcrumb":     str(doc.get('breadcrumb', '')),
                    "depth":          int(doc.get('depth', 0)),
                    "parent_id":      str(doc.get('parent_id') or ''),
                    "parent_name":    str(doc.get('parent_name', '')),
                    "children_count": int(doc.get('children_count', 0)),
                    "category":       str(doc.get('category', 'default')),
                    "indexed_at":     datetime.now().isoformat(),
                }
                metas.append(meta)

            self._collection.add(
                ids=ids,
                embeddings=embs,
                documents=raw_docs,
                metadatas=metas
            )

            pct = int(end * 100 / total)
            logger.info(f"   • Batch {start // batch_size + 1}: {end}/{total} ({pct}%)")

        logger.info(f"   ✅ {total} documents insérés dans ChromaDB")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la collection."""
        if self._collection is None:
            return {}
        count = self._collection.count()
        return {
            "total_documents": count,
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir,
        }

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recherche les k plus proches voisins par similarité cosinus.

        Args:
            query_vector: Vecteur de requête (float32)
            k: Nombre de résultats

        Returns:
            Liste de dicts {id, name, breadcrumb, score, ...}
        """
        if self._collection is None:
            return []

        results = self._collection.query(
            query_embeddings=[query_vector.tolist()],
            n_results=k,
            include=["metadatas", "documents", "distances"]
        )

        hits = []
        for i, doc_id in enumerate(results['ids'][0]):
            meta = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            score = 1.0 - distance  # cosine distance → similarity

            hits.append({
                "id":         doc_id,
                "name":       meta.get("name", ""),
                "domain":     meta.get("domain", ""),
                "breadcrumb": meta.get("breadcrumb", ""),
                "depth":      meta.get("depth", 0),
                "score":      round(score, 4),
                "metadata":   meta,
                "document":   results['documents'][0][i]
            })

        return hits

    def save(self):
        """ChromaDB persiste automatiquement — méthode conservée pour compatibilité."""
        logger.info("   ✅ ChromaDB persisté automatiquement")


# ============================================================================
# EXTRACTION DGRAPH (inchangée par rapport à l'original)
# ============================================================================

class DgraphFullExtractor:
    """
    Extracteur complet qui récupère TOUT depuis Dgraph.
    Identique à la version originale.
    """

    def __init__(self, dgraph_connector):
        self.dgraph = dgraph_connector
        self.node_map: Dict[str, Dict] = {}
        self.parent_map: Dict[str, str] = {}
        self.children_map: Dict[str, List[str]] = defaultdict(list)
        self.breadcrumb_cache: Dict[str, str] = {}
        self.depth_cache: Dict[str, int] = {}

    def extract_all_projects(self) -> List[Dict]:
        logger.info("="*80)
        logger.info("🌍 EXTRACTION COMPLÈTE DE DGRAPH")
        logger.info("="*80)

        all_projects = self._list_all_projects()
        if not all_projects:
            logger.error("❌ Aucun projet trouvé dans Dgraph")
            return []

        logger.info(f"✅ {len(all_projects)} projet(s) trouvé(s)")
        for i, proj in enumerate(all_projects, 1):
            logger.info(f"   {i}. {proj['name']} (UID: {proj['uid']})")

        all_documents = []
        for proj_info in all_projects:
            project_name = proj_info['name']
            logger.info(f"\n📥 Extraction de '{project_name}'...")

            project_data = self._fetch_project(project_name)
            if project_data:
                self.node_map = {}
                self.parent_map = {}
                self.children_map = defaultdict(list)
                self.breadcrumb_cache = {}
                self.depth_cache = {}

                self._build_navigation_maps(project_data)
                self._compute_all_breadcrumbs()

                documents = self._build_enriched_documents(project_name)
                all_documents.extend(documents)
                logger.info(f"✅ {len(documents)} documents extraits de '{project_name}'")

                if documents:
                    sample = documents[0]
                    logger.info(f"\n📄 Exemple: {sample['name']} — {len(sample['content'])} chars")
                    logger.info(f"   {sample['content'][:200]}...")

        logger.info(f"\n✅ TOTAL: {len(all_documents)} documents extraits")
        return all_documents

    def _list_all_projects(self) -> List[Dict]:
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
                      uid name description category depth position dgraph.type
                      children {{
                        uid name description category depth position dgraph.type
                        children {{
                          uid name description category depth position dgraph.type
                          children {{
                            uid name description category depth position dgraph.type
                            children {{
                              uid name description category depth position dgraph.type
                              children {{
                                uid name description category depth position dgraph.type
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
        def process_node(node, parent_uid=None, node_type=None):
            uid = node.get('uid')
            if not uid:
                return
            actual_type = node_type or (
                next((t for t in node.get('dgraph.type', []) if not t.startswith('dgraph.')), 'Unknown')
                if isinstance(node.get('dgraph.type'), list) else node.get('dgraph.type', 'Unknown')
            )
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
            if parent_uid:
                self.parent_map[uid] = parent_uid
                self.children_map[parent_uid].append(uid)

        project_uid = project_data.get('uid')
        process_node(project_data, node_type='Project')

        for typo in project_data.get('typologies', []):
            process_node(typo, parent_uid=project_uid, node_type='Typologie')
            typo_uid = typo.get('uid')
            for cluster in typo.get('clusters', []):
                process_node(cluster, parent_uid=typo_uid, node_type='Cluster')
                cluster_uid = cluster.get('uid')
                for root in cluster.get('rootLabels', []):
                    process_node(root, parent_uid=cluster_uid, node_type='RootLabel')
                    root_uid = root.get('uid')
                    self._process_children(root.get('children', []), root_uid)

    def _process_children(self, children: List[Dict], parent_uid: str):
        for child in children:
            uid = child.get('uid')
            if not uid:
                continue
            dgraph_type = child.get('dgraph.type', [])
            actual_type = (
                next((t for t in dgraph_type if not t.startswith('dgraph.')), 'LabelNode')
                if isinstance(dgraph_type, list) else dgraph_type or 'LabelNode'
            )
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
            self.parent_map[uid] = parent_uid
            self.children_map[parent_uid].append(uid)
            if 'children' in child:
                self._process_children(child['children'], uid)

    def _compute_all_breadcrumbs(self):
        for uid in self.node_map:
            self.breadcrumb_cache[uid] = self._compute_breadcrumb(uid)
            self.depth_cache[uid] = self._compute_depth(uid)

    def _compute_breadcrumb(self, uid: str) -> str:
        path = []
        current_uid = uid
        while current_uid:
            node = self.node_map.get(current_uid)
            if node:
                path.insert(0, node['name'])
            current_uid = self.parent_map.get(current_uid)
        return " > ".join(path)

    def _compute_depth(self, uid: str) -> int:
        depth = 0
        current_uid = self.parent_map.get(uid)
        while current_uid:
            depth += 1
            current_uid = self.parent_map.get(current_uid)
        return depth

    def _build_enriched_documents(self, project_name: str) -> List[Dict]:
        documents = []

        for uid, node in self.node_map.items():
            breadcrumb = self.breadcrumb_cache.get(uid, '')
            depth = self.depth_cache.get(uid, 0)
            parent_uid = self.parent_map.get(uid)
            parent_name = self.node_map[parent_uid]['name'] if parent_uid and parent_uid in self.node_map else ''
            children_uids = self.children_map.get(uid, [])
            children_names = [self.node_map[c]['name'] for c in children_uids if c in self.node_map]
            siblings_uids = [
                s for s in self.children_map.get(parent_uid, []) if s != uid
            ] if parent_uid else []
            siblings_names = [self.node_map[s]['name'] for s in siblings_uids if s in self.node_map]
            ancestors = []
            current = parent_uid
            while current:
                ancestors.append(self.node_map[current]['name'])
                current = self.parent_map.get(current)

            # --- Texte enrichi (identique à l'original) ---
            title = node['name']
            description = node.get('description', '')
            context_desc = node.get('contextDescription', '')

            if description and len(description) > 10:
                primary_text = f"{title}: {description}"
            elif context_desc and len(context_desc) > 10:
                primary_text = f"{title}: {context_desc}"
            else:
                parts = breadcrumb.split(' > ') if breadcrumb else []
                if len(parts) >= 2:
                    primary_text = f"{title} (type: {parts[-2]})"
                else:
                    primary_text = f"{title} dans {project_name}"

            context_parts = []
            if breadcrumb:
                bc_parts = breadcrumb.split(' > ')
                if len(bc_parts) > 1:
                    relevant = bc_parts[1:]
                    top3 = relevant[-3:] if len(relevant) > 3 else relevant
                    if top3:
                        context_parts.append(" → ".join(top3))

            all_keywords = []
            intent_kw = node.get('intentKeywords', [])
            action_kw = node.get('actionKeywords', [])
            if isinstance(intent_kw, list):
                all_keywords.extend(intent_kw[:3])
            elif intent_kw:
                all_keywords.append(str(intent_kw))
            if isinstance(action_kw, list):
                all_keywords.extend(action_kw[:3])
            elif action_kw:
                all_keywords.append(str(action_kw))
            all_keywords = list(dict.fromkeys(all_keywords))[:5]
            if all_keywords:
                context_parts.append(f"[{', '.join(all_keywords)}]")

            examples = node.get('examplePrompts', [])
            if examples and isinstance(examples, list) and len(examples) > 0:
                context_parts.append(f"Ex: {examples[0]}")

            text_components = [primary_text]
            if context_parts:
                text_components.append(" | ".join(context_parts))
            combined_text = ". ".join(text_components)

            if len(combined_text) < 50:
                combined_text += f" (domaine: {project_name})"
            elif len(combined_text) > 500:
                combined_text = f"{primary_text}. {context_parts[0]}" if context_parts else primary_text[:500]

            doc = {
                'id':             uid,
                'taxon_id':       uid,
                'name':           node['name'],
                'type':           node['type'],
                'domain':         project_name,
                'description':    node.get('description', ''),
                'content':        combined_text,
                'breadcrumb':     breadcrumb,
                'depth':          depth,
                'parent_id':      parent_uid,
                'parent_name':    parent_name,
                'children_ids':   children_uids,
                'children_names': children_names,
                'children_count': len(children_uids),
                'siblings_ids':   siblings_uids,
                'siblings_names': siblings_names,
                'ancestors':      ancestors,
                'category':       node.get('category', 'default'),
                'position':       node.get('position', 0),
                'intentKeywords': node.get('intentKeywords', []),
                'actionKeywords': node.get('actionKeywords', []),
                'entityType':     node.get('entityType'),
                'uiComponent':    node.get('uiComponent'),
                'examplePrompts': node.get('examplePrompts', []),
                'metadata': {
                    'dgraph_uid':       uid,
                    'dgraph_type':      node['type'],
                    'hierarchy_depth':  depth,
                    'has_children':     len(children_uids) > 0,
                    'has_siblings':     len(siblings_uids) > 0,
                    'breadcrumb_parts': breadcrumb.split(' > '),
                    'text_length':      len(combined_text),
                    'indexed_at':       None
                }
            }
            documents.append(doc)

        if documents:
            lengths = [len(d['content']) for d in documents]
            avg = sum(lengths) / len(lengths)
            optimal = sum(1 for l in lengths if 100 <= l <= 500)
            logger.info(f"\n📊 Textes enrichis — avg: {avg:.0f} chars | optimal (100-500): {optimal}/{len(documents)}")

        return documents


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def run_indexing_pipeline():
    """
    Pipeline complet:
      Dgraph → DgraphFullExtractor → LirisEmbedderClient → ChromaVectorStore
    """
    print("\n" + "="*80)
    print("🔄 RÉINDEXATION DGRAPH → CHROMADB (Liris Embeddings)")
    print("="*80 + "\n")
    print("✅ Embeddings: Liris API (http://localhost:7777)")
    print("✅ Vector Store: ChromaDB (persistant)")
    print("✅ Texte enrichi avec contexte hiérarchique\n")

    choice = input("Continuer ? (oui/non): ").strip().lower()
    if choice not in ('oui', 'yes', 'o', 'y'):
        print("\n❌ Annulé")
        return 0

    try:
        # ── Chemins ──────────────────────────────────────────────────────────
        chroma_dir     = Path("./data/indexes/chroma")
        stats_path     = Path("./data/hierarchy_stats.json")
        docs_dump_path = Path("./data/documents_hierarchy.json")

        # ── Connexions ───────────────────────────────────────────────────────
        logger.info("\n📦 Step 1/6: Initialisation des services")

        from utils.dataset_dgraph_connector import TaxonomyDgraphConnector

        logger.info("🔌 Connexion à Dgraph...")
        dgraph_connector = TaxonomyDgraphConnector()
        if not dgraph_connector.client:
            logger.error("❌ Connexion Dgraph échouée")
            return 1

        logger.info("🔌 Connexion Liris Embedder...")
        liris_client = LirisEmbedderClient(
            base_url="http://localhost:7777",
            model="liris"
        )

        vector_store = ChromaVectorStore(
            persist_dir=str(chroma_dir),
            collection_name="context_weaver_taxonomy"
        )
        vector_store.initialize()

        # ── Extraction ───────────────────────────────────────────────────────
        logger.info("\n🌳 Step 2/6: Extraction de la hiérarchie Dgraph")
        extractor = DgraphFullExtractor(dgraph_connector)
        documents = extractor.extract_all_projects()

        if not documents:
            logger.error("❌ Aucun document extrait")
            dgraph_connector.close()
            return 1

        # ── Stats & dump JSON ─────────────────────────────────────────────────
        logger.info("\n📊 Step 3/6: Calcul des statistiques")
        stats = {
            'total_nodes':       len(documents),
            'by_type':           {},
            'by_domain':         {},
            'max_depth':         max(d['depth'] for d in documents),
            'avg_children':      sum(d['children_count'] for d in documents) / len(documents),
            'nodes_with_children': sum(1 for d in documents if d['children_count'] > 0),
            'indexed_at':        datetime.now().isoformat(),
            'embedding_model':   'liris',
            'vector_store':      'chromadb'
        }
        for doc in documents:
            stats['by_type'][doc['type']] = stats['by_type'].get(doc['type'], 0) + 1
            stats['by_domain'][doc['domain']] = stats['by_domain'].get(doc['domain'], 0) + 1

        stats_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        logger.info(f"   • Total nœuds:      {stats['total_nodes']}")
        logger.info(f"   • Profondeur max:   {stats['max_depth']}")
        logger.info(f"   • Moyenne enfants:  {stats['avg_children']:.2f}")
        for domain, count in stats['by_domain'].items():
            logger.info(f"     - {domain}: {count}")

        docs_dump_path.parent.mkdir(parents=True, exist_ok=True)
        with open(docs_dump_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        logger.info(f"   ✅ Documents JSON: {docs_dump_path}")

        # ── Embeddings ────────────────────────────────────────────────────────
        logger.info(f"\n🧮 Step 4/6: Génération des embeddings Liris ({len(documents)} textes)")

        batch_size = 10
        total_batches = (len(documents) + batch_size - 1) // batch_size
        all_embeddings: List[np.ndarray] = []

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end   = min(start + batch_size, len(documents))
            batch_texts = [documents[i]['content'] for i in range(start, end)]

            batch_embs = liris_client.generate_embeddings_batch(batch_texts)
            all_embeddings.extend(batch_embs)

            pct = int(end * 100 / len(documents))
            logger.info(f"   Batch {batch_idx+1}/{total_batches}: {end}/{len(documents)} ({pct}%)")

        logger.info(f"   ✅ {len(all_embeddings)} embeddings générés — dim: {liris_client.embedding_dim}")

        embeddings_array = np.array(all_embeddings, dtype=np.float32)

        # ── Indexation ChromaDB ───────────────────────────────────────────────
        logger.info("\n📦 Step 5/6: Indexation dans ChromaDB")
        vector_store.reset_collection()
        vector_store.bulk_insert(documents, embeddings_array, batch_size=100)

        # ── Vérification ─────────────────────────────────────────────────────
        logger.info("\n🔍 Step 6/6: Vérification")
        chroma_stats = vector_store.get_stats()
        logger.info(f"   • Documents dans ChromaDB: {chroma_stats.get('total_documents', 0)}")
        logger.info(f"   • Collection: {chroma_stats.get('collection_name', '')}")
        logger.info(f"   • Répertoire: {chroma_stats.get('persist_dir', '')}")

        # Test rapide de recherche
        test_query = documents[0]['content'] if documents else "test"
        test_emb = liris_client.generate_embeddings(test_query)
        test_results = vector_store.search(test_emb, k=3)
        logger.info(f"   ✅ Recherche test: {len(test_results)} résultats")
        if test_results:
            logger.info(f"      Top 1: {test_results[0]['name']} (score: {test_results[0]['score']:.4f})")

        # ── Fermeture ─────────────────────────────────────────────────────────
        dgraph_connector.close()
        liris_client.close()

        # ── Résumé ────────────────────────────────────────────────────────────
        print("\n" + "="*80)
        print("✅ RÉINDEXATION TERMINÉE AVEC SUCCÈS")
        print("="*80)
        print(f"\n📁 Fichiers créés:")
        print(f"   • ChromaDB:  {chroma_dir}/")
        print(f"   • Stats:     {stats_path}")
        print(f"   • Documents: {docs_dump_path}")
        print(f"\n📊 Résultat:")
        print(f"   • {len(documents)} nœuds indexés")
        print(f"   • Dimension embeddings: {liris_client.embedding_dim}")
        print(f"   • Modèle: liris @ http://192.168.0.101:7777")
        print()

        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interruption utilisateur")
        return 130

    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


# ============================================================================
# MODE VÉRIFICATION
# ============================================================================

def verify_indexing():
    """Vérifie l'état de l'index ChromaDB existant."""
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION DE L'INDEX CHROMADB")
    print("="*80 + "\n")

    try:
        vector_store = ChromaVectorStore(
            persist_dir="./data/indexes/chroma",
            collection_name="context_weaver_taxonomy"
        )
        vector_store.initialize()

        stats = vector_store.get_stats()
        logger.info(f"✅ Collection: {stats.get('collection_name')}")
        logger.info(f"   • Documents: {stats.get('total_documents', 0)}")
        logger.info(f"   • Répertoire: {stats.get('persist_dir')}")

        liris_client = LirisEmbedderClient()
        test_emb = liris_client.generate_embeddings("créer une facture")
        results = vector_store.search(test_emb, k=5)

        logger.info(f"\n🔎 Test recherche 'créer une facture':")
        for i, r in enumerate(results, 1):
            logger.info(f"   {i}. {r['name']} — score: {r['score']:.4f} | {r['breadcrumb'][:60]}")

        liris_client.close()

    except Exception as e:
        logger.error(f"❌ Erreur vérification: {e}")
        import traceback
        logger.error(traceback.format_exc())


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Réindexation Context Weaver → ChromaDB (Liris)")
    parser.add_argument('--verify', action='store_true', help="Vérifier l'index existant")
    args = parser.parse_args()

    if args.verify:
        verify_indexing()
    else:
        sys.exit(run_indexing_pipeline())