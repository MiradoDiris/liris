"""
dgraph_taxonomy_connector.py - Connecteur Dgraph pour arbre de décision taxonomique
Projet: macompta (liris-projet2)
Port gRPC: 9082
Port Ratel: 8092
"""

import pydgraph
import json
from datetime import datetime
from utils.logger import logger

# Configuration des ports pour liris-projet2
DGRAPH_GRPC_PORT = "localhost:9082"
DGRAPH_HTTP_PORT = "localhost:8082"
RATEL_HTTP_PORT = "http://localhost:8092"


class TaxonomyDgraphConnector:
    """
    Connecteur Dgraph optimisé pour arbre de décision taxonomique
    Gère la navigation par UID avec viewport/viewstate
    """
    
    def __init__(self):
        self.client = None
        self.connect()
    
    def connect(self):
        """Établit la connexion à Dgraph avec options optimisées"""
        try:
            logger.info("="*80)
            logger.info("🔌 CONNEXION DGRAPH TAXONOMIE")
            logger.info("="*80)
            logger.info(f"  Port gRPC: {DGRAPH_GRPC_PORT}")
            logger.info(f"  Port HTTP: {DGRAPH_HTTP_PORT}")
            logger.info(f"  Ratel UI: {RATEL_HTTP_PORT}")
            
            # Options de connexion
            options = [
                ('grpc.max_receive_message_length', 2147483647),
                ('grpc.max_send_message_length', 2147483647),
                ('grpc.keepalive_time_ms', 300000),
                ('grpc.keepalive_timeout_ms', 60000),
                ('grpc.keepalive_permit_without_calls', 1),
            ]
            
            client_stub = pydgraph.DgraphClientStub(DGRAPH_GRPC_PORT, options=options)
            self.client = pydgraph.DgraphClient(client_stub)
            
            # Test de connexion
            query = "{ q(func: has(name)) { uid } }"
            resp = self.client.txn(read_only=True).query(query)
            
            logger.info("✅ Connexion réussie!")
            logger.info("="*80 + "\n")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            return False
    
    def apply_schema(self):
        """Applique le schéma taxonomique"""
        schema = """
# Types
type Project {
  name
  description
  createdAt
  updatedAt
  typologies
}

type Typologie {
  name
  description
  position
  createdAt
  updatedAt
  clusters
}

type Cluster {
  name
  description
  position
  createdAt
  updatedAt
  rootLabels
}

type RootLabel {
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
  children
  cluster
}

type LabelNode {
  name
  description
  category
  depth
  position
  createdAt
  updatedAt
  intentKeywords
  actionKeywords
  entityType
  uiComponent
  userRole
  contextDescription
  examplePrompts
  children
  parent
}

# Prédicats
name: string @index(exact, term, fulltext) .
description: string @index(fulltext) .
category: string @index(exact) .
position: int @index(int) .
depth: int @index(int) .
createdAt: datetime @index(hour) .
updatedAt: datetime @index(hour) .
intentKeywords: [string] @index(term) .
actionKeywords: [string] @index(term) .
entityType: string @index(exact) .
uiComponent: string @index(exact) .
userRole: string @index(exact) .
contextDescription: string @index(fulltext) .
examplePrompts: [string] .

# Edges
typologies: [uid] @count @reverse .
clusters: [uid] @count @reverse .
rootLabels: [uid] @count @reverse .
children: [uid] @count @reverse .
cluster: uid @reverse .
parent: uid @reverse .
        """
        
        try:
            op = pydgraph.Operation(schema=schema)
            self.client.alter(op)
            logger.info("✅ Schéma appliqué avec succès")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur application schéma: {e}")
            return False
    
    # ============================================
    # INSERTION DE DONNÉES
    # ============================================
    
    def create_project(self, name, description=""):
        """Crée un nouveau projet"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:project",
                "dgraph.type": "Project",
                "name": name,
                "description": description,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            response = txn.mutate(set_obj=mutation)
            txn.commit()
            
            project_uid = response.uids["project"]
            logger.info(f"✅ Projet créé: {name} (UID: {project_uid})")
            return project_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur création projet: {e}")
            return None
    
    def add_typologie(self, project_uid, name, description="", position=0):
        """Ajoute une typologie à un projet"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:typologie",
                "dgraph.type": "Typologie",
                "name": name,
                "description": description,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            # Lier au projet
            project_link = {
                "uid": project_uid,
                "typologies": [{"uid": "_:typologie"}]
            }
            
            response = txn.mutate(set_obj=[mutation, project_link])
            txn.commit()
            
            typologie_uid = response.uids["typologie"]
            logger.info(f"✅ Typologie créée: {name} (UID: {typologie_uid})")
            return typologie_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur création typologie: {e}")
            return None
    
    def add_cluster(self, typologie_uid, name, description="", position=0):
        """Ajoute un cluster à une typologie"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:cluster",
                "dgraph.type": "Cluster",
                "name": name,
                "description": description,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            typologie_link = {
                "uid": typologie_uid,
                "clusters": [{"uid": "_:cluster"}]
            }
            
            response = txn.mutate(set_obj=[mutation, typologie_link])
            txn.commit()
            
            cluster_uid = response.uids["cluster"]
            logger.info(f"✅ Cluster créé: {name} (UID: {cluster_uid})")
            return cluster_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur création cluster: {e}")
            return None
    
    def add_root_label(self, cluster_uid, name, description="", category="default", position=0):
        """Ajoute un root label à un cluster"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:rootlabel",
                "dgraph.type": "RootLabel",
                "name": name,
                "description": description,
                "category": category,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            cluster_link = {
                "uid": cluster_uid,
                "rootLabels": [{"uid": "_:rootlabel"}]
            }
            
            response = txn.mutate(set_obj=[mutation, cluster_link])
            txn.commit()
            
            rootlabel_uid = response.uids["rootlabel"]
            logger.info(f"✅ RootLabel créé: {name} (UID: {rootlabel_uid})")
            return rootlabel_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur création root label: {e}")
            return None
    
    def add_label_node(self, parent_uid, name, description="", category="default", 
                       depth=0, position=0, **metadata):
        """
        Ajoute un nœud label (enfant)
        parent_uid peut être un RootLabel ou un autre LabelNode
        metadata: intentKeywords, actionKeywords, entityType, etc.
        """
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:labelnode",
                "dgraph.type": "LabelNode",
                "name": name,
                "description": description,
                "category": category,
                "depth": depth,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            # Ajouter métadonnées optionnelles
            for key, value in metadata.items():
                if value is not None:
                    mutation[key] = value
            
            parent_link = {
                "uid": parent_uid,
                "children": [{"uid": "_:labelnode"}]
            }
            
            response = txn.mutate(set_obj=[mutation, parent_link])
            txn.commit()
            
            labelnode_uid = response.uids["labelnode"]
            logger.info(f"✅ LabelNode créé: {name} (UID: {labelnode_uid}, depth: {depth})")
            return labelnode_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur création label node: {e}")
            return None
    
    # ============================================
    # QUERIES - NAVIGATION PAR UID
    # ============================================
    
    def get_project(self, project_name):
        """Récupère un projet par nom avec ses typologies"""
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
              clustersCount: count(clusters)
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('project', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur query projet: {e}")
            return []
    
    def get_node_by_uid(self, uid, load_children=True, children_limit=50, children_offset=0):
        """
        Récupère un nœud par UID avec ses edges
        Optimisé pour viewport/viewstate
        """
        children_query = ""
        if load_children:
            children_query = f"""
            children(first: {children_limit}, offset: {children_offset}, orderasc: position) {{
              uid
              name
              description
              category
              depth
              position
              childrenCount: count(children)
            }}
            totalChildren: count(children)
            """
        
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            description
            dgraph.type
            category
            position
            depth
            createdAt
            updatedAt
            
            {children_query}
            
            # Edges spécifiques par type
            typologies {{ uid name }}
            clusters {{ uid name }}
            rootLabels {{ uid name }}
            parent {{ uid name }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('node', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur query nœud {uid}: {e}")
            return []
    
    def expand_typologie(self, typologie_uid):
        """Charge les clusters d'une typologie"""
        query = f"""
        {{
          typologie(func: uid({typologie_uid})) {{
            uid
            name
            
            clusters(orderasc: position) {{
              uid
              name
              description
              position
              rootLabelsCount: count(rootLabels)
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('typologie', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur expansion typologie: {e}")
            return []
    
    def expand_cluster(self, cluster_uid):
        """Charge les root labels d'un cluster"""
        query = f"""
        {{
          cluster(func: uid({cluster_uid})) {{
            uid
            name
            
            rootLabels(orderasc: position) {{
              uid
              name
              description
              category
              position
              childrenCount: count(children)
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('cluster', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur expansion cluster: {e}")
            return []
    
    def get_path_to_root(self, node_uid):
        """Récupère le chemin complet de la racine au nœud"""
        query = f"""
        {{
          node(func: uid({node_uid})) {{
            uid
            name
            dgraph.type
            
            parent @recurse(depth: 10, loop: false) {{
              uid
              name
              dgraph.type
              parent
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('node', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur chemin: {e}")
            return []
    
    def search_by_name(self, search_term):
        """Recherche globale par nom"""
        query = f"""
        {{
          search(func: allofterms(name, "{search_term}")) {{
            uid
            name
            dgraph.type
            description
            category
            
            parent {{
              uid
              name
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('search', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche: {e}")
            return []
    
    def close(self):
        """Ferme la connexion"""
        if self.client:
            self.client.close()
            logger.info("✅ Connexion fermée")


if __name__ == '__main__':
    # Connexion
    connector = TaxonomyDgraphConnector()
    
    # Appliquer le schéma
    connector.apply_schema()
    
    # Créer un projet
    project_uid = connector.create_project(
        name="macompta",
        description="Projet comptabilité avec arbre de décision"
    )
    
    # Ajouter une typologie
    typo_uid = connector.add_typologie(
        project_uid=project_uid,
        name="UI/UX interface",
        description="Contexte interface utilisateur"
    )
    
    # Ajouter un cluster
    cluster_uid = connector.add_cluster(
        typologie_uid=typo_uid,
        name="intention",
        description="Intentions utilisateur"
    )
    
    # Ajouter un root label
    root_uid = connector.add_root_label(
        cluster_uid=cluster_uid,
        name="TABLEAU DE BORD",
        category="module"
    )
    
    # Ajouter des enfants
    child1_uid = connector.add_label_node(
        parent_uid=root_uid,
        name="Trésorerie",
        depth=0,
        position=0,
        intentKeywords=["consulter", "voir", "afficher"],
        entityType="dashboard"
    )
    
    child2_uid = connector.add_label_node(
        parent_uid=root_uid,
        name="Résultat",
        depth=0,
        position=1,
        intentKeywords=["analyser", "consulter"],
        entityType="report"
    )
    
    # Query: récupérer le projet
    projects = connector.get_project("macompta")
    print(json.dumps(projects, indent=2))
    
    # Fermer
    connector.close()