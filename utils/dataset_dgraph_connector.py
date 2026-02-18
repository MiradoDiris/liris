"""
dgraph_taxonomy_connector.py - Version MINIMALISTE pour Vector Store
Projet: macompta (liris-projet2)

PRINCIPE:
- Dgraph = Structure hiérarchique + Relations de prérequis
- Prérequis = Simple edge avec type "mandatory" (synchronisation)
- Explications = Dans description du nœud (pour Vector Store)
"""

import pydgraph
import json
from datetime import datetime
from utils.logger import logger

DGRAPH_GRPC_PORT = "localhost:9082"
DGRAPH_HTTP_PORT = "localhost:8082"
RATEL_HTTP_PORT = "http://localhost:8092"


class TaxonomyDgraphConnector:
    """
    Connecteur Dgraph minimaliste
    - Hiérarchie: Project > Typologie > Cluster > RootLabel > LabelNode
    - Prérequis: Simple edge avec attribut mandatory
    - Métadonnées: description, entityType uniquement
    """
    
    def __init__(self):
        self.client = None
        self.connect()
    
    def connect(self):
        """Établit la connexion à Dgraph avec gestion d'erreur robuste"""
        try:
            logger.info("="*80)
            logger.info("🔌 TENTATIVE CONNEXION DGRAPH TAXONOMIE")
            logger.info("="*80)
            logger.info(f"  Port gRPC: {DGRAPH_GRPC_PORT}")
            logger.info(f"  Ratel UI: {RATEL_HTTP_PORT}")
            
            # Vérifier d'abord si le port est accessible
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # Timeout de 2 secondes
            
            host, port = DGRAPH_GRPC_PORT.split(':')
            result = sock.connect_ex((host, int(port)))
            sock.close()
            
            if result != 0:
                logger.warning(f"⚠️ Port {DGRAPH_GRPC_PORT} non accessible")
                logger.info("   Pour démarrer Dgraph: docker-compose up dgraph")
                return False
            
            logger.debug(f"✓ Port {DGRAPH_GRPC_PORT} accessible")
            
            options = [
                ('grpc.max_receive_message_length', 2147483647),
                ('grpc.max_send_message_length', 2147483647),
                ('grpc.keepalive_time_ms', 300000),
                ('grpc.keepalive_timeout_ms', 60000),
                ('grpc.keepalive_permit_without_calls', 1),
            ]
            
            client_stub = pydgraph.DgraphClientStub(DGRAPH_GRPC_PORT, options=options)
            self.client = pydgraph.DgraphClient(client_stub)
            
            # Test de connexion avec timeout
            query = "{ q(func: has(name)) { uid } }"
            resp = self.client.txn(read_only=True).query(query)
            
            logger.info("✅ Connexion réussie!")
            logger.info("="*80 + "\n")
            return True
            
        except socket.error as e:
            logger.warning(f"⚠️ Dgraph non accessible: {e}")
            logger.info("   Pour démarrer Dgraph: docker-compose up dgraph")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Erreur connexion Dgraph: {e}")
            logger.info("   Vérifiez que Dgraph est démarré")
            return False
    
    def apply_schema(self):
        """
        Schéma minimaliste optimisé pour Vector Store
        VERSION AVEC NOM DE RELATION
        """
        schema = """
    # Types de nœuds (inchangé)
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
      prerequisite
    }

    type Cluster {
      name
      description
      position
      createdAt
      updatedAt
      rootLabels
      prerequisite
    }

    type RootLabel {
      name
      description
      entityType
      position
      createdAt
      updatedAt
      children
      cluster
      prerequisite
    }

    type LabelNode {
      name
      description
      entityType
      depth
      position
      createdAt
      updatedAt
      children
      parent
      prerequisite
    }

    # Prédicats de base (inchangé)
    name: string @index(exact, term, fulltext) .
    description: string @index(fulltext) .
    entityType: string @index(exact) .
    position: int @index(int) .
    depth: int @index(int) .
    createdAt: datetime @index(hour) .
    updatedAt: datetime @index(hour) .

    # Edges hiérarchiques (inchangé)
    typologies: [uid] @count @reverse .
    clusters: [uid] @count @reverse .
    rootLabels: [uid] @count @reverse .
    children: [uid] @count @reverse .
    cluster: uid @reverse .
    parent: uid @reverse .

    # Edge de prérequis avec facets mandatory ET name
    prerequisite: [uid] @reverse @count .
    prerequisite|mandatory: bool .
    prerequisite|name: string @index(term, fulltext) .
        """

        try:
            op = pydgraph.Operation(schema=schema)
            self.client.alter(op)
            logger.info("✅ Schéma appliqué avec succès (avec facet name)")
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
    
    def add_root_label(self, cluster_uid, name, description="", entity_type="", position=0):
        """Ajoute un root label à un cluster"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:rootlabel",
                "dgraph.type": "RootLabel",
                "name": name,
                "description": description,
                "entityType": entity_type,
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
    
    def add_label_node(self, parent_uid, name, description="", entity_type="", 
                       depth=0, position=0):
        """Ajoute un nœud label (enfant)"""
        try:
            txn = self.client.txn()
            
            mutation = {
                "uid": "_:labelnode",
                "dgraph.type": "LabelNode",
                "name": name,
                "description": description,
                "entityType": entity_type,
                "depth": depth,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
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
    # GESTION DES PRÉREQUIS (SIMPLIFIÉ)
    # ============================================
    
    def add_prerequisite(self, source_uid, target_uid, mandatory=True, name=""):
        """
        Ajoute une relation de prérequis avec un nom

        Args:
            source_uid: UID du nœud source (qui dépend)
            target_uid: UID du nœud target (prérequis)
            mandatory: True = obligatoire (sync), False = recommandé
            name: Nom descriptif de la relation (ex: "Connaissances de base")

        Note:
            Les explications du prérequis sont dans la description du nœud source
            pour être indexées dans le Vector Store
        """
        try:
            txn = self.client.txn()

            # Mutation avec facets (mandatory + name)
            mandatory_str = str(mandatory).lower()

            # Échapper les guillemets dans le nom
            name_escaped = name.replace('"', '\\"').replace('\n', ' ')

            # Construire le nquad avec les facets
            if name and name.strip():
                nquad = f'<{source_uid}> <prerequisite> <{target_uid}> (mandatory={mandatory_str}, name="{name_escaped}") .'
            else:
                # Si pas de nom, juste mandatory
                nquad = f'<{source_uid}> <prerequisite> <{target_uid}> (mandatory={mandatory_str}) .'

            txn.mutate(set_nquads=nquad)
            txn.commit()

            prereq_type = "obligatoire" if mandatory else "recommandé"
            name_info = f" (nom: '{name}')" if name else ""
            logger.info(f"✅ Prérequis {prereq_type} ajouté: {source_uid} -> {target_uid}{name_info}")
            return True

        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur ajout prérequis: {e}")
            return False
    
    def add_multiple_prerequisites(self, source_uid, target_uids, mandatory=True, relation_names=None):
        """
        Ajoute plusieurs prérequis à un nœud source avec noms optionnels

        Args:
            source_uid: UID du nœud source
            target_uids: Liste des UIDs des nœuds targets (prérequis)
            mandatory: True = tous obligatoires, False = tous recommandés
            relation_names: Dict {target_uid: relation_name} optionnel
        """
        try:
            relation_names = relation_names or {}

            txn = self.client.txn()

            nquads = []
            for target_uid in target_uids:
                mandatory_str = str(mandatory).lower()

                # Récupérer le nom de la relation pour ce target
                relation_name = relation_names.get(target_uid, '')

                if relation_name and relation_name.strip():
                    # Échapper les guillemets
                    name_escaped = relation_name.replace('"', '\\"').replace('\n', ' ')
                    nquad = f'<{source_uid}> <prerequisite> <{target_uid}> (mandatory={mandatory_str}, name="{name_escaped}") .'
                else:
                    nquad = f'<{source_uid}> <prerequisite> <{target_uid}> (mandatory={mandatory_str}) .'

                nquads.append(nquad)

            txn.mutate(set_nquads='\n'.join(nquads))
            txn.commit()

            prereq_type = "obligatoires" if mandatory else "recommandés"
            logger.info(f"✅ {len(target_uids)} prérequis {prereq_type} ajoutés au nœud {source_uid}")
            return True

        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur ajout prérequis multiples: {e}")
            return False
        
    def get_prerequisites_with_names(self, source_uid):
        """Récupère les prérequis avec leurs noms de relations"""
        query = f"""
        {{
          node(func: uid({source_uid})) {{
            uid
            name
            
            prerequisite @facets {{
              uid
              name
              description
              entityType
              dgraph.type
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            
            # Parser les résultats pour extraire les noms de relations
            if data.get('node') and len(data['node']) > 0:
                node = data['node'][0]
                prerequisites = []
                
                for prereq in node.get('prerequisite', []):
                    prereq_data = {
                        'uid': prereq.get('uid'),
                        'name': prereq.get('name'),
                        'type': prereq.get('dgraph.type'),
                        'mandatory': prereq.get('prerequisite|mandatory', True),
                        'relation_name': prereq.get('prerequisite|name', '')  # NOUVEAU
                    }
                    prerequisites.append(prereq_data)
                
                return prerequisites
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur query prérequis: {e}")
            return []
    
    def remove_prerequisite(self, source_uid, target_uid):
        """Supprime une relation de prérequis"""
        try:
            txn = self.client.txn()
            
            nquad = f'<{source_uid}> <prerequisite> <{target_uid}> .'
            txn.mutate(del_nquads=nquad)
            txn.commit()
            
            logger.info(f"✅ Prérequis supprimé: {source_uid} -/-> {target_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression prérequis: {e}")
            return False
    
    # ============================================
    # QUERIES
    # ============================================
    
    def get_node_by_uid(self, uid, load_children=True, load_prerequisites=True):
        """
        Récupère un nœud par UID avec ses relations
        """
        children_query = ""
        if load_children:
            children_query = """
            children(orderasc: position) {
              uid
              name
              description
              entityType
              depth
              position
              childrenCount: count(children)
            }
            """
        
        prereq_query = ""
        if load_prerequisites:
            prereq_query = """
            prerequisite @facets {
              uid
              name
              description
              entityType
              dgraph.type
            }
            
            ~prerequisite @facets {
              uid
              name
              description
              entityType
              dgraph.type
            }
            """
        
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            description
            dgraph.type
            entityType
            position
            depth
            createdAt
            updatedAt
            
            {children_query}
            {prereq_query}
            
            # Edges hiérarchiques
            parent {{ uid name }}
            cluster {{ uid name }}
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
    
    def get_mandatory_prerequisites(self, source_uid):
        """Récupère uniquement les prérequis obligatoires (mandatory=true)"""
        query = f"""
        {{
          node(func: uid({source_uid})) {{
            uid
            name
            
            prerequisite @facets(eq(mandatory, true)) {{
              uid
              name
              description
              entityType
              dgraph.type
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
            logger.error(f"❌ Erreur query prérequis obligatoires: {e}")
            return []
    
    def get_dependent_nodes(self, target_uid):
        """Récupère tous les nœuds sources qui dépendent de ce target"""
        query = f"""
        {{
          target(func: uid({target_uid})) {{
            uid
            name
            description
            entityType
            
            ~prerequisite @facets {{
              uid
              name
              description
              dgraph.type
              entityType
            }}
          }}
        }}
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('target', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur query nœuds dépendants: {e}")
            return []
    
    def get_prerequisites_graph(self, source_uid, depth=3):
        """Récupère le graphe des prérequis avec récursion"""
        query = f"""
        {{
          node(func: uid({source_uid})) {{
            uid
            name
            description
            entityType
            
            prerequisite @facets @recurse(depth: {depth}, loop: false) {{
              uid
              name
              description
              entityType
              dgraph.type
              prerequisite
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
            logger.error(f"❌ Erreur query graphe prérequis: {e}")
            return []
    
    def get_all_nodes_for_indexing(self):
        """Récupère tous les nœuds pour indexation Vector Store"""
        query = """
        {
          nodes(func: has(name)) {
            uid
            name
            description
            dgraph.type
            entityType
          }
        }
        """
        
        try:
            txn = self.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            return data.get('nodes', [])
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération nœuds: {e}")
            return []
    
    def close(self):
        """Ferme la connexion"""
        if self.client:
            self.client.close()
            logger.info("✅ Connexion fermée")


# ============================================
# EXEMPLE D'UTILISATION
# ============================================

if __name__ == '__main__':
    connector = TaxonomyDgraphConnector()
    connector.apply_schema()
    
    # Créer la structure
    project_uid = connector.create_project(
        name="macompta",
        description="Projet comptabilité avec arbre de décision"
    )
    
    # Typologies avec prérequis
    typo_base = connector.add_typologie(
        project_uid=project_uid,
        name="Gestion Base",
        description="Contexte de gestion de base pour tous les utilisateurs. Fonctionnalités essentielles et simples."
    )
    
    typo_avancee = connector.add_typologie(
        project_uid=project_uid,
        name="Gestion Avancée",
        description="Contexte de gestion avancée avec fonctionnalités expertes. NÉCESSITE d'avoir maîtrisé la Gestion Base au préalable pour comprendre les concepts avancés."
    )
    
    # Prérequis: Gestion Avancée nécessite Gestion Base
    connector.add_prerequisite(
        source_uid=typo_avancee,
        target_uid=typo_base,
        mandatory=True
    )
    logger.info("  ➡️ Typologie 'Gestion Avancée' NÉCESSITE 'Gestion Base'")
    
    # Clusters
    cluster_saisie = connector.add_cluster(
        typologie_uid=typo_base,
        name="Saisie de données",
        description="Cluster pour la saisie des informations de base"
    )
    
    cluster_reporting = connector.add_cluster(
        typologie_uid=typo_base,
        name="Reporting",
        description="Cluster pour la consultation des rapports. NÉCESSITE que des données aient été saisies dans le cluster 'Saisie de données' pour générer les rapports."
    )
    
    # Prérequis: Reporting nécessite Saisie
    connector.add_prerequisite(
        source_uid=cluster_reporting,
        target_uid=cluster_saisie,
        mandatory=True
    )
    logger.info("  ➡️ Cluster 'Reporting' NÉCESSITE 'Saisie de données'")
    
    cluster_analytics = connector.add_cluster(
        typologie_uid=typo_avancee,
        name="Analytics Avancé",
        description="Cluster d'analyse avancée. NÉCESSITE le cluster Reporting pour avoir les données de base à analyser."
    )
    
    # Prérequis cross-niveau: Cluster Analytics nécessite Cluster Reporting
    connector.add_prerequisite(
        source_uid=cluster_analytics,
        target_uid=cluster_reporting,
        mandatory=True
    )
    logger.info("  ➡️ Cluster 'Analytics Avancé' NÉCESSITE 'Reporting' (cross-niveau)")
    
    # Root labels
    root_dashboard = connector.add_root_label(
        cluster_uid=cluster_reporting,
        name="TABLEAU DE BORD",
        description="Vue d'ensemble des indicateurs clés de gestion",
        entity_type="dashboard"
    )
    
    root_compta = connector.add_root_label(
        cluster_uid=cluster_saisie,
        name="COMPTABILITÉ",
        description="Module de gestion comptable et saisie d'écritures",
        entity_type="module"
    )
    
    # Enfants
    tresorerie = connector.add_label_node(
        parent_uid=root_dashboard,
        name="Trésorerie",
        description="Suivi des flux de trésorerie et soldes bancaires. Permet de visualiser la situation financière en temps réel.",
        entity_type="dashboard",
        depth=0,
        position=0
    )
    
    resultat = connector.add_label_node(
        parent_uid=root_dashboard,
        name="Résultat",
        description="Analyse du compte de résultat et rentabilité. NÉCESSITE d'avoir saisi des écritures comptables au préalable pour générer le rapport. Recommande de consulter la trésorerie pour avoir une vision complète.",
        entity_type="report",
        depth=0,
        position=1
    )
    
    saisie = connector.add_label_node(
        parent_uid=root_compta,
        name="Saisie d'écriture",
        description="Formulaire de saisie des écritures comptables. Point d'entrée pour enregistrer les transactions.",
        entity_type="form",
        depth=0,
        position=0
    )
    
    print("\n" + "="*80)
    print("📊 AJOUT DES PRÉREQUIS")
    print("="*80)
    
    # Prérequis obligatoire (synchronisation)
    connector.add_prerequisite(
        source_uid=resultat,
        target_uid=saisie,
        mandatory=True  # Obligatoire = synchronisation nécessaire
    )
    logger.info("  ➡️ 'Résultat' NÉCESSITE 'Saisie d'écriture' (obligatoire)")
    
    # Prérequis recommandé
    connector.add_prerequisite(
        source_uid=resultat,
        target_uid=tresorerie,
        mandatory=False  # Recommandé
    )
    logger.info("  ➡️ 'Résultat' RECOMMANDE 'Trésorerie' (optionnel)")
    
    # Prérequis multiples
    connector.add_multiple_prerequisites(
        source_uid=root_dashboard,
        target_uids=[saisie, root_compta],
        mandatory=True
    )
    logger.info("  ➡️ 'Tableau de bord' NÉCESSITE 'Saisie' et 'Comptabilité' (obligatoires)")
    
    print("\n" + "="*80)
    print("🔍 REQUÊTES")
    print("="*80)
    
    # Query 1: Nœud avec prérequis
    print("\n1. Nœud 'Résultat' avec ses prérequis:")
    result_node = connector.get_node_by_uid(resultat)
    print(json.dumps(result_node, indent=2, ensure_ascii=False))
    
    # Query 2: Prérequis obligatoires uniquement
    print("\n2. Prérequis obligatoires de 'Résultat':")
    mandatory = connector.get_mandatory_prerequisites(resultat)
    print(json.dumps(mandatory, indent=2, ensure_ascii=False))
    
    # Query 3: Qui dépend de 'Saisie'
    print("\n3. Nœuds qui dépendent de 'Saisie d'écriture':")
    dependents = connector.get_dependent_nodes(saisie)
    print(json.dumps(dependents, indent=2, ensure_ascii=False))
    
    connector.close()