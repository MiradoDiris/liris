# dgraph_connector.py (version corrigée avec reverse edges et méthodes complètes)
"""
dgraph_connector.py - Connector Dgraph pour Liris (version étendue pour mutations directes)
"""

import time
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
      """Établit la connexion à Dgraph via gRPC avec limite augmentée."""
      if not self.test_port():
          return False
      
      try:
          # ✅ CORRECTION : Augmenter la limite de message à 100MB
          options = [
            ('grpc.max_receive_message_length', 2147483647),
            ('grpc.max_send_message_length', 2147483647),
            
            # Timeouts généreux
            ('grpc.keepalive_time_ms', 300000),  # 5 min
            ('grpc.keepalive_timeout_ms', 60000),  # 1 min
            
            # Désactiver limites ping
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.keepalive_permit_without_calls', 1),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.max_ping_strikes', 999999),
          ]
          
          client_stub = pydgraph.DgraphClientStub(
              DGRAPH_GRPC_PORT,
              options=options  # ✅ Passer les options ici
          )
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
          logger.info(f"✅ Connexion Liris-Dgraph réussie avec limite 100MB")
          
          # Vérification et reset auto si nécessaire
          if self.auto_reset and self.needs_schema_reset():
              logger.warning("Reset auto activé : Cela effacera TOUTES les données Dgraph.")
              self.reset_and_apply_schema()
          else:
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
        
    def drop_predicate(self, predicate_name: str):
      """Supprime un prédicat spécifique sans toucher aux autres données."""
      if not self.client:
          logger.error("❌ Pas de client connecté.")
          return False
      
      logger.warning(f"⚠️ SUPPRESSION du prédicat '{predicate_name}'...")
      
      try:
          op = pydgraph.Operation(drop_attr=predicate_name)
          self.client.alter(op)
          logger.info(f"✅ Prédicat '{predicate_name}' supprimé avec succès")
          return True
      except Exception as e:
          logger.error(f"❌ Erreur suppression : {e}")
          return False
    
    def setup_schema(self):
      """✅ Schéma avec gestion automatique des conflits de type."""
      if not self.client:
          return
  
      schema = """
      # ============================================
      # TYPES PRINCIPAUX
      # ============================================
  
      type Relation {
        name
        relationType
        category
        line
        intraFile
  
        # Références UID
        source
        target
  
        # Métadonnées source
        sourceName
        sourceDescription
        sourcePath
        sourceType
  
        # Métadonnées target
        targetName
        targetDescription
        targetPath
        targetType
  
        createdAt
      }
  
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
        classes
        methods
        variables
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
        line
        params
        returns
      }
  
      type Class {
        name
        description
        line
        bases
        methods
        uses_vars
        variables
      }
  
      type Variable {
        name
        description
        line
        var_type
        scope
      }
  
      # ============================================
      # PRÉDICATS
      # ============================================
  
      name: string @index(exact, term, fulltext) .
      id: string @index(exact) .
      level: int @index(int) .
      path: string @index(exact, term) .
  
      # ✅ CATÉGORIE (scalaire uniquement pour Relations)
      category: string @index(exact) .
  
      parents: [uid] @reverse .
      clusters: [uid] @reverse .
  
      parentId: string .
      userId: string .
      createdAt: datetime @index(hour) .
      updatedAt: datetime @index(hour) .
      ownerId: string .
      lastUpdated: datetime .
      version: string .
      clusterManagement: uid .
  
      nodeType: string @index(exact) .
      codeContent: string .
      description: string @index(fulltext) .
      files: [string] .
      fileContents: string .
  
      functions: [uid] @reverse .
      imports: [uid] @reverse .
      calls: [uid] @reverse .
      uses: [uid] @reverse .
      inherits: [uid] @reverse .
      extends: [uid] @reverse .
      implements: [uid] @reverse .
      used_by: [uid] @reverse .
  
      relations: [uid] @reverse .
      classes: [uid] @reverse .
      methods: [uid] @reverse .
      variables: [uid] @reverse .
  
      relationType: string @index(exact) .
      line: int .
      params: string .
      returns: string .
      bases: [string] .
      uses_vars: [string] .
      var_type: string .
      scope: string .
  
      source: uid @reverse .
      target: uid @reverse .
  
      sourceName: string @index(term, fulltext) .
      sourceDescription: string .
      sourcePath: string @index(exact) .
      sourceType: string @index(exact) .
  
      targetName: string @index(term, fulltext) .
      targetDescription: string .
      targetPath: string @index(exact) .
      targetType: string @index(exact) .
  
      intraFile: bool .
      """
  
      try:
          op = pydgraph.Operation(schema=schema)
          self.client.alter(op)
          logger.info("✅ Schéma Dgraph configuré avec succès")
      except Exception as e:
          error_msg = str(e)
          
          # ✅ GESTION AUTOMATIQUE DU CONFLIT DE TYPE
          if "can't be changed from list to scalar" in error_msg and "category" in error_msg:
              logger.warning("⚠️ Conflit détecté sur 'category' : tentative de correction...")
              
              # Supprimer le prédicat problématique
              if self.drop_predicate('category'):
                  logger.info("🔄 Nouvelle tentative d'application du schéma...")
                  
                  # Réessayer
                  try:
                      op = pydgraph.Operation(schema=schema)
                      self.client.alter(op)
                      logger.info("✅ Schéma appliqué avec succès après correction")
                      return
                  except Exception as e2:
                      logger.error(f"❌ Échec après correction : {e2}")
              else:
                  logger.error("❌ Impossible de corriger automatiquement")
          
          logger.warning(f"⚠️ Erreur lors de la configuration du schéma : {e}")
  
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
    
    def insert_mutations(self, mutations, initial_batch_size=500, max_retries=3):
        """
        VERSION CORRIGÉE (ITÉRATIVE)
        
        Gère les erreurs de taille et de timeout de manière itérative (non récursive)
        pour une gestion fiable du total inséré et des échecs.
        """
        if not self.client:
            logger.error("❌ Pas de client Dgraph")
            return False
    
        total_inserted = 0
        total_mutations = len(mutations)
        failed_mutations = []
    
        logger.info(f"📦 Démarrage insertion: {total_mutations} mutations (batch: {initial_batch_size})")
    
        start_time = time.time()
        i = 0
        current_batch_size = initial_batch_size
    
        while i < total_mutations:
            batch_start_time = time.time()
            batch_end = min(i + current_batch_size, total_mutations)
            batch = mutations[i:batch_end]
            batch_num_calc = (i // initial_batch_size) + 1 
    
            is_size_error = False # Indicateur si l'erreur était la taille du lot
            
            try:
                batch_json = json.dumps(batch, ensure_ascii=False)
                batch_size_mb = len(batch_json.encode('utf-8')) / (1024 * 1024)
            except Exception as e:
                logger.error(f"❌ Erreur sérialisation: {e}")
                failed_mutations.extend(batch)
                i = batch_end
                continue
            
            retry_count = 0
            success = False
    
            while retry_count < max_retries and not success:
                txn = self.client.txn()
                committed = False
    
                try:
                    # Remplacer placeholders
                    for mutation in batch:
                        self._replace_datetime_placeholders(mutation)
    
                    # MUTATION UNIQUE
                    assigned = txn.mutate(set_obj=batch)
                    txn.commit()
                    committed = True
                    success = True
                    
                    batch_duration = time.time() - batch_start_time
                    throughput = len(batch) / batch_duration if batch_duration > 0 else 0
                    
                    # Log optimisé
                    if batch_num_calc % 10 == 0 or total_mutations < 500:
                        logger.info(
                            f"✅ Batch {batch_num_calc}: {len(batch)} mutations "
                            f"({batch_size_mb:.2f} MB) en {batch_duration:.2f}s "
                            f"({throughput:.0f} mut/s)"
                        )
    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    if not committed:
                        txn.discard()
    
                    if "too large" in error_msg or "exceeds" in error_msg:
                        
                        # Calculer la nouvelle taille de lot
                        new_batch_size = max(1, current_batch_size // 2)
                        
                        # Point d'échec critique (impossible de réduire davantage)
                        if new_batch_size == current_batch_size or current_batch_size == 1:
                             logger.error(f"❌ La mutation à l'index {i} est trop grosse (taille max: {batch_size_mb:.2f} MB), skip.")
                             failed_mutations.extend(batch)
                             # Laisser is_size_error à False pour que l'index avance
                        else:
                            # Réduction réussie, mettre à jour la taille et activer le flag
                            current_batch_size = new_batch_size
                            logger.warning(
                                f"⚠️ Batch trop gros ({batch_size_mb:.2f} MB). Réduction du batch à {current_batch_size}."
                            )
                            is_size_error = True
                            
                        break # Sortir du retry loop, pour recommencer à l'index 'i' avec le nouveau batch size
                    
                    elif "timeout" in error_msg or "deadline" in error_msg:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count
                            logger.warning(f"⏱️ Timeout, retry {retry_count}/{max_retries} dans {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"❌ Timeout définitif batch {batch_num_calc}")
                            failed_mutations.extend(batch)
    
                    else:
                        logger.error(f"❌ Erreur batch {batch_num_calc}: {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)
                        else:
                            failed_mutations.extend(batch)
    
                finally:
                    if not committed:
                        txn.discard()
    
            if is_size_error:
                continue
            
            if success:
                total_inserted += len(batch)
            
            i = batch_end
    
        # ✅ RAPPORT FINAL (inchangé)
        total_duration = time.time() - start_time
        throughput = total_inserted / total_duration if total_duration > 0 else 0
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ INSERTION TERMINÉE en {total_duration:.2f}s")
        logger.info(f"  • Total: {total_inserted}/{total_mutations} mutations")
        logger.info(f"  • Débit moyen: {throughput:.0f} mut/s")
        
        if failed_mutations:
            logger.error(f"  • Échecs: {len(failed_mutations)} mutations")
            
            # Sauvegarder les échecs
            failed_file = f"data/failed_mutations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                import os
                os.makedirs('data', exist_ok=True)
                with open(failed_file, 'w') as f:
                    json.dump(failed_mutations, f, indent=2)
                logger.info(f"💾 Échecs sauvegardés dans {failed_file}")
            except Exception as e:
                logger.warning(f"⚠️ Impossible sauvegarder échecs: {e}")
    
        logger.info(f"{'='*80}\n")
    
        return total_inserted == total_mutations
    
    def _try_compress_mutation(self, mutation):
      """
      ✅ Tente de compresser une mutation trop grosse
      Compresse fileContents en base64+gzip
      """
      import gzip
      import base64
      
      try:
          if mutation.get('dgraph.type') != 'Label':
              return None
          
          file_contents = mutation.get('fileContents', '')
          if not file_contents or len(file_contents) < 1024*1024:  # < 1MB
              return None
          
          logger.info("🗜️ Compression fileContents...")
          
          # Compression
          compressed = gzip.compress(file_contents.encode('utf-8'), compresslevel=9)
          encoded = base64.b64encode(compressed).decode('ascii')
          
          # Ratio
          original_size = len(file_contents)
          compressed_size = len(encoded)
          ratio = (1 - compressed_size / original_size) * 100
          
          logger.info(f"   Avant: {original_size / (1024*1024):.2f} MB")
          logger.info(f"   Après: {compressed_size / (1024*1024):.2f} MB")
          logger.info(f"   Ratio: {ratio:.1f}% réduction")
          
          # Remplacer dans mutation
          mutation['fileContents'] = f"COMPRESSED_BASE64:{encoded}"
          
          return mutation
          
      except Exception as e:
          logger.error(f"❌ Erreur compression: {e}")
          return None

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
      """
      ✅ VERSION CORRIGÉE : Utilise ~clusters pour récupérer les labels
      """
      if not self.client:
          return None

      try:
          # ✅ CORRECTION : Utiliser ~clusters au lieu de labels
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
                uid
                lastUpdated
                version

                clusters @filter(type(Cluster)) {
                  uid
                  name
                  id
                  nodeType
                  description
                  codeContent
                  files
                  fileContents
                  createdAt
                  updatedAt

                  # ✅ CORRECTION : ~clusters au lieu de labels
                  root_labels: ~clusters @filter(eq(level, 0)) {
                    uid
                    name
                    id
                    path
                    category
                    nodeType
                    codeContent
                    description
                    level
                    files
                    fileContents

                    classes {
                      uid
                      name
                      description
                      line
                      bases
                      uses_vars

                      methods {
                        uid
                        name
                        description
                        line
                        params
                        returns
                      }

                      variables {
                        uid
                        name
                        description
                        line
                        var_type
                        scope
                      }
                    }

                    functions {
                      uid
                      name
                      description
                      line
                      params
                      returns

                      calls {
                        uid
                        name
                      }

                      variables {
                        uid
                        name
                        description
                        line
                        var_type
                        scope
                      }
                    }

                    variables {
                      uid
                      name
                      description
                      line
                      var_type
                      scope
                    }

                    # ✅ ENFANTS HIÉRARCHIQUES
                    children: ~parents @filter(eq(level, 1)) {
                      uid
                      name
                      id
                      path
                      category
                      nodeType
                      codeContent
                      description
                      level
                      files
                      fileContents

                      classes {
                        uid
                        name
                        description
                        line

                        methods {
                          uid
                          name
                          description
                          line
                        }

                        variables {
                          uid
                          name
                          description
                        }
                      }

                      functions {
                        uid
                        name
                        description
                        line
                      }

                      variables {
                        uid
                        name
                        description
                        line
                      }

                      # ✅ NIVEAU 2
                      children: ~parents @filter(eq(level, 2)) {
                        uid
                        name
                        id
                        nodeType
                        level

                        classes {
                          uid
                          name
                        }

                        functions {
                          uid
                          name
                        }

                        variables {
                          uid
                          name
                        }
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

          logger.info(f"✅ Query workspaces réussie")

          # ✅ NORMALISATION : Renommer pour compatibilité
          if data and 'q' in data and data['q']:
              for workspace in data['q']:
                  cm = workspace.get('clusterManagement', {})
                  clusters = cm.get('clusters', [])

                  for cluster in clusters:
                      # Les root_labels sont déjà corrects via ~clusters
                      labels_count = len(cluster.get('root_labels', []))
                      logger.info(f"  📂 Cluster '{cluster.get('name')}': {labels_count} labels")

          return data

      except Exception as e:
          logger.error(f"❌ Erreur query workspaces : {e}")
          import traceback
          traceback.print_exc()
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