# dgraph_connector.py (version corrigée avec reverse edges et méthodes complètes)
"""
dgraph_connector.py - Connector Dgraph pour Liris (version étendue pour mutations directes)
"""

import webbrowser
import socket
import pydgraph
import json
from datetime import datetime
from utils.logger import logger

# Configuration des ports
DGRAPH_GRPC_PORT = "localhost:9080"
RATEL_HTTP_PORT = "http://localhost:8001"

class LirisDgraphConnector:
    """
    Classe pour connecter Liris à Dgraph.
    Gère la connexion client, tests basiques, ouverture de Ratel, et insertions de mutations.
    """
    
    def __init__(self, auto_reset=False):
        self.client = None
        self.auto_reset = auto_reset
        self.connect()
    
    def _parse_response(self, resp):
        """Helper pour parser resp.json (gère bytes)."""
        resp_bytes = resp.json
        if isinstance(resp_bytes, bytes):
            resp_bytes = resp_bytes.decode('utf-8')
        return json.loads(resp_bytes)
    
    def test_port(self, host="localhost", port=9080):
        """Teste si le port gRPC est ouvert avant connexion."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            logger.info(f"Port gRPC {port} est ouvert et prêt.")
            return True
        else:
            logger.warning(f"Port gRPC {port} non ouvert (erreur {result}). Démarrez Dgraph via Docker.")
            return False
    
    def connect(self):
        """Établit la connexion à Dgraph via gRPC."""
        if not self.test_port():
            return False
        
        try:
            client_stub = pydgraph.DgraphClientStub(DGRAPH_GRPC_PORT)
            self.client = pydgraph.DgraphClient(client_stub)
            
            # Test de connexion
            query = """
            {
              q(func: has(name)) {
                name
              }
            }
            """
            resp = self.client.txn(read_only=True).query(query)
            data = self._parse_response(resp)
            logger.info(f"Connexion Liris-Dgraph réussie ! Réponse: {data}")
            
            # Vérification et reset auto si nécessaire
            if self.auto_reset and self.needs_schema_reset():
                logger.warning("Reset auto activé : Cela effacera TOUTES les données Dgraph.")
                self.reset_and_apply_schema()
            else:
                # Application standard (idempotente)
                self.setup_schema()
            
            return True
        except Exception as e:
            logger.error(f"Erreur de connexion à Dgraph: {e}")
            return False
    
    def needs_schema_reset(self):
        """Vérifie si le schéma a des prédicats invalides."""
        if not self.client:
            return False
        try:
            query = """
            {
              q(func: has(dgraph.type)) {
                expand(_all_)
              }
            }
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = self._parse_response(resp)
            
            if data and 'q' in data and data['q']:
                for node in data['q']:
                    for pred in node:
                        if ('.' in pred and 
                            not pred.startswith('dgraph.') and 
                            not pred.startswith('dgraph.graphql.')):
                            logger.warning(f"Prédicat invalide détecté : {pred}")
                            return True
            return False
        except Exception as e:
            logger.warning(f"Erreur vérif schéma : {e}. Assume reset nécessaire.")
            return True
    
    def reset_and_apply_schema(self):
        """Drop all et applique schéma propre (version mise à jour avec @reverse sur imports)."""
        if not self.client:
            logger.error("Pas de client connecté.")
            return False
        
        logger.warning("ATTENTION: reset_and_apply_schema efface TOUS les données Dgraph !")
        try:
            # Drop tout
            op_drop = pydgraph.Operation(drop_all=True)
            self.client.alter(op_drop)
            logger.info("Drop all exécuté : schéma et données supprimés.")
            
            # Même schéma avec @reverse sur imports
            clean_schema = """
# Types (inchangés)
type Cluster {
  name
  id
  userId
  createdAt
  updatedAt
  nodeType
  description
  codeContent
  functions
  imports
  relations
  files
  fileContents
}

type Label {
  name
  id
  level
  path
  category
  createdAt
  updatedAt
  parentId
  parents
  clusters
  nodeType
  codeContent
  description
  functions
  imports
  relations
  files
  fileContents
}

type Workspace {
  name
  id
  ownerId
  updatedAt
  clusterManagement
  description
  files
  fileContents
}

type ClusterManagement {
  lastUpdated
  version
  clusters
}

type Function {
  name
  description
  calls
}

# Prédicats avec types, index et reverse (ajout @reverse sur imports)
name: string @index(exact) .
id: string @index(exact) .
level: int @index(int) .
path: string .
category: [string] .
parents: [uid] @reverse .
clusters: [uid] @reverse .
parentId: string .
userId: string .
createdAt: datetime .
updatedAt: datetime .
ownerId: string .
lastUpdated: datetime .
version: string .
clusterManagement: uid .
nodeType: string @index(exact) .
codeContent: string .
description: string .
functions: [uid] .
imports: [uid] @reverse .  # AJOUT : @reverse pour supporter ~imports
calls: [uid] @reverse .
relations: [uid] @reverse .
relationType: string @index(exact) .
files: [string] .
fileContents: string .
"""

            op_schema = pydgraph.Operation(schema=clean_schema)
            self.client.alter(op_schema)
            logger.info("Schéma mis à jour appliqué avec succès (avec @reverse sur imports).")
            return True
        except Exception as e:
            logger.error(f"Erreur reset/apply schema: {e}")
            return False
    
    def setup_schema(self):
        """Applique le schéma standard (idempotent, sans drop)."""
        if not self.client:
            return
        
        # Schéma mis à jour avec @reverse sur imports (et autres pour cohérence)
        schema = """
# Types
type Cluster {
  name
  id
  userId
  createdAt
  updatedAt
  nodeType
  description
  codeContent
  functions
  imports
  relations
  files
  fileContents
}

type Label {
  name
  id
  level
  path
  category
  createdAt
  updatedAt
  parentId
  parents
  clusters
  nodeType
  codeContent
  description
  functions
  imports
  relations
  files
  fileContents
}

type Workspace {
  name
  id
  ownerId
  updatedAt
  clusterManagement
  description
  files
  fileContents
}

type ClusterManagement {
  lastUpdated
  version
  clusters
}

type Function {
  name
  description
  calls
}

# Prédicats avec types, index et reverse (ajout @reverse sur imports)
name: string @index(exact) .
id: string @index(exact) .
level: int @index(int) .
path: string .
category: [string] .
parents: [uid] @reverse .
clusters: [uid] @reverse .
parentId: string .
userId: string .
createdAt: datetime .
updatedAt: datetime .
ownerId: string .
lastUpdated: datetime .
version: string .
clusterManagement: uid .
nodeType: string @index(exact) .
codeContent: string .
description: string .
functions: [uid] .
imports: [uid] @reverse .  # AJOUT : @reverse pour supporter ~imports
calls: [uid] @reverse .
relations: [uid] @reverse .
relationType: string @index(exact) .
files: [string] .
fileContents: string .
"""
        
        try:
            op = pydgraph.Operation(schema=schema)
            self.client.alter(op)
            logger.info("Schéma Dgraph configuré avec succès (avec @reverse sur imports, clusters, parents, calls, relations).")
        except Exception as e:
            logger.warning(f"Erreur lors de la configuration du schéma (peut-être déjà existant): {e}")
    
    def update_schema_only_reverse_edges(self):
        """Ajoute les directives @reverse sans drop (pour mise à jour sans perte de données)."""
        if not self.client:
            logger.error("Pas de client connecté.")
            return False
        
        try:
            schema_update = """
imports: [uid] @reverse .
parents: [uid] @reverse .
clusters: [uid] @reverse .
calls: [uid] @reverse .
relations: [uid] @reverse .
"""
            op = pydgraph.Operation(schema=schema_update)
            self.client.alter(op)
            logger.info("Reverse edges ajoutées au schéma avec succès (incluant imports).")
            return True
        except Exception as e:
            logger.error(f"Erreur update reverse edges: {e}")
            return False
    
    def get_current_schema(self):
        """Récupère et affiche le schéma actuel de Dgraph."""
        if not self.client:
            return None
        try:
            query = "schema {}"
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            schema_str = resp.json.decode('utf-8') if isinstance(resp.json, bytes) else resp.json
            logger.info(f"Schéma actuel récupéré.")
            return schema_str
        except Exception as e:
            logger.error(f"Erreur get schema: {e}")
            return None
    
    def open_ratel(self):
        """Ouvre Ratel (UI Dgraph) dans le navigateur."""
        try:
            webbrowser.open(RATEL_HTTP_PORT)
            logger.info(f"Ratel ouvert sur {RATEL_HTTP_PORT}")
        except Exception as e:
            logger.error(f"Erreur ouverture Ratel: {e}")
    
    def insert_mutations(self, mutations):
        """Insère des mutations dans Dgraph."""
        if not self.client:
            logger.error("Pas de client connecté.")
            return False

        txn = self.client.txn()
        committed = False
        try:
            # Remplacer les placeholders datetime
            for mutation in mutations:
                self._replace_datetime_placeholders(mutation)

            assigned = txn.mutate(set_obj=mutations)
            txn.commit()
            committed = True

            logger.info("Mutations exécutées avec succès dans Dgraph.")
            logger.info(f"Assigned UIDs: {assigned.uids}")

            # Vérification post-insertion
            verified_data = self.query_workspaces()
            if verified_data:
                logger.info(f"Vérification post-insertion : {len(verified_data.get('q', []))} workspaces trouvés.")
            else:
                logger.warning("Vérification post-insertion échouée.")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution des mutations: {e}")
            return False

        finally:
            if not committed:
                try:
                    txn.discard()
                except Exception:
                    pass

    def _replace_datetime_placeholders(self, obj):
        """Remplace les placeholders datetime par des timestamps réels."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and "datetime.now().isoformat() + 'Z'" in value:
                    obj[key] = datetime.now().isoformat() + "Z"
                else:
                    self._replace_datetime_placeholders(value)
        elif isinstance(obj, list):
            for item in obj:
                self._replace_datetime_placeholders(item)
    
    def insert_sample_data(self, project_name="lirisdev", project_description="Projet Liris connecté à Dgraph"):
        """Exemple d'insertion de données."""
        if not self.client:
            logger.error("Pas de client connecté.")
            return
        
        txn = self.client.txn()
        try:
            mu = {
                "uid": "_:project_uid",
                "dgraph.type": "Workspace",
                "name": project_name,
                "description": project_description,
                "ownerId": "user1",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            assigned = txn.mutate(set_obj=mu)
            txn.commit()
            logger.info(f"Données insérées avec succès. UID: {assigned.uids}")
        except Exception as e:
            txn.discard()
            logger.error(f"Erreur insertion: {e}")
    
    def query_projects(self):
        """Query exemple : Récupérer les projets."""
        if not self.client:
            logger.error("Pas de client connecté.")
            return None
        
        try:
            query = """
            {
              q(func: eq(name, "lirisdev")) {
                uid
                name
                description
              }
            }
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Query projets: {data}")
            return data
        except Exception as e:
            logger.error(f"Erreur query: {e}")
            return None

    def query_clusters(self):
        """Query pour lister tous les clusters et leurs labels."""
        if not self.client:
            return None
        try:
            query = """
            {
              q(func: type(Cluster)) {
                uid
                name
                id
                nodeType
                description
                codeContent
                createdAt
                files
                fileContents
                root_labels: ~clusters @filter(eq(dgraph.type, "Label") and eq(level, 0)) {
                  uid
                  name
                  path
                  nodeType
                  codeContent
                  description
                  files
                  fileContents
                  parents: ~parents {
                    uid
                    name
                    files
                    fileContents
                    children: ~parents {
                      uid
                      name
                      files
                      fileContents
                    }
                  }
                }
              }
            }
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Clusters query: {data}")
            return data
        except Exception as e:
            logger.error(f"Erreur query clusters: {e}")
            return None

    def query_workspaces(self):
        """Query pour récupérer workspaces avec hiérarchie complète."""
        if not self.client:
            return None
        try:
            query = """
            {
              q(func: type(Workspace)) {
                uid
                name
                id
                ownerId
                updatedAt
                description
                files
                fileContents
                clusterManagement {
                  clusters {
                    uid
                    name
                    id
                    nodeType
                    description
                    codeContent
                    files
                    fileContents
                    root_labels: ~clusters @filter(eq(level, 0)) {
                      uid
                      name
                      id
                      path
                      category
                      nodeType
                      codeContent
                      description
                      files
                      fileContents
                      parents: ~parents @filter(eq(level, 1)) {
                        uid
                        name
                        id
                        category
                        nodeType
                        codeContent
                        description
                        files
                        fileContents
                        children: ~parents @filter(eq(level, 2)) {
                          uid
                          name
                          id
                          category
                          nodeType
                          codeContent
                          description
                          files
                          fileContents
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Query workspaces réussie : {len(data.get('q', []))} résultats.")
            return data
        except Exception as e:
            logger.error(f"Erreur query workspaces : {e}")
            return None

    def query_full_context(self, workspace_id=None, cluster_type=None):
        """Récupère contexte avec filtre optionnel. MODIFIÉ : Ajout de ~calls et ~relations à chaque niveau pour supporter le niveau 2 (relations inverses récursives)."""
        if not self.client:
            return None
        try:
            filter_ws = f"eq(id, \"{workspace_id}\")" if workspace_id else "type(Workspace)"
            filter_cluster = f" and eq(nodeType, \"{cluster_type}\")" if cluster_type else ""
            query = f"""
            {{
              q(func: {filter_ws}) {{
                uid name description
                clusterManagement {{
                  clusters @filter(type(Cluster){filter_cluster}) {{
                    uid name id nodeType description codeContent
                    functions {{ uid name description calls {{ name }} }}
                    imports {{ name description }}
                    relations {{ uid name relationType }}
                    ~calls {{ uid name description }}
                    ~relations {{ uid name relationType }}
                    root_labels: ~clusters @filter(eq(level, 0)) {{
                      uid name id path category nodeType codeContent description
                      functions {{ uid name description calls {{ name }} }}
                      imports {{ name description }}
                      relations {{ uid name relationType }}
                      ~calls {{ uid name description }}
                      ~relations {{ uid name relationType }}
                      parents: ~parents @filter(eq(level, 1)) {{
                        uid name id path category nodeType codeContent description
                        functions {{ uid name description calls {{ name }} }}
                        imports {{ name description }}
                        relations {{ uid name relationType }}
                        ~calls {{ uid name description }}
                        ~relations {{ uid name relationType }}
                        children: ~parents @filter(eq(level, 2)) {{
                          uid name id path category nodeType codeContent description
                          functions {{ uid name description calls {{ name }} }}
                          imports {{ name description }}
                          relations {{ uid name relationType }}
                          ~calls {{ uid name description }}
                          ~relations {{ uid name relationType }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Contexte complet : {len(data.get('q', []))} workspaces (avec relations inverses).")
            return data
        except Exception as e:
            logger.error(f"Erreur query full context: {e}")
            return None

    def query_cluster_details(self, cluster_id):
        """Détails d'un cluster."""
        if not self.client:
            return None
        try:
            query = f"""
            {{
              q(func: eq(id, "{cluster_id}")) {{
                uid name path nodeType codeContent description
                functions {{ uid name description calls {{ uid name }} }}
                ~calls {{ uid name }}
                imports {{ uid name description }}
                relations {{ uid name relationType }}
                ~relations {{ uid name relationType }}
                children_labels: ~clusters {{
                  uid name nodeType
                }}
              }}
            }}
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Cluster details: {data}")
            return data
        except Exception as e:
            logger.error(f"Erreur query cluster details: {e}")
            return None

    def query_label_details(self, label_id):
        """Détails d'un label."""
        if not self.client:
            return None
        try:
            query = f"""
            {{
              q(func: eq(id, "{label_id}")) {{
                uid name path nodeType codeContent description
                functions {{ uid name description calls {{ uid name }} }}
                ~calls {{ uid name }}
                imports {{ uid name description }}
                relations {{ uid name relationType }}
                ~relations {{ uid name relationType }}
              }}
            }}
            """
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self._parse_response(resp)
            logger.info(f"Label details: {data}")
            return data
        except Exception as e:
            logger.error(f"Erreur query label details: {e}")
            return None
    
    def close(self):
        """Ferme la connexion."""
        if self.client:
            self.client.close()

# Utilisation Standalone
def main():
    connector = LirisDgraphConnector(auto_reset=False)
    if connector.connect():
        # Afficher le schéma actuel
        schema = connector.get_current_schema()
        print("Schéma actuel:", schema)
        
        connector.open_ratel()
        connector.insert_sample_data(project_description="Projet Liris Dev : Automatisation IA")
        connector.query_projects()
        connector.query_full_context()
    else:
        print("Démarrez Dgraph d'abord.")
    connector.close()

if __name__ == '__main__':
    main()