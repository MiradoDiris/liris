"""
dataset_dgraph_manager.py - Gestionnaire CRUD complet pour Dgraph
Projet: macompta (liris-projet2)

Gère toutes les opérations de manipulation des données avec Dgraph:
- Création, lecture, mise à jour, suppression (CRUD)
- Navigation hiérarchique
- Synchronisation avec l'interface
- Gestion des transactions
"""

import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from utils.logger import logger
from utils.dataset_dgraph_connector import TaxonomyDgraphConnector


class DgraphDatasetManager:
    """
    Gestionnaire principal pour toutes les opérations CRUD sur Dgraph
    Abstrait la complexité du connecteur et fournit une API simple
    """
    
    def __init__(self):
        """Initialise le gestionnaire avec connexion Dgraph"""
        self.connector = TaxonomyDgraphConnector()
        self.current_project_uid = None
        self.current_project_name = None
        
        # Cache local pour optimiser les requêtes
        self._cache = {
            'projects': {},
            'typologies': {},
            'clusters': {},
            'roots': {},
            'parents': {},
            'children': {}
        }
        
        logger.info("✅ DgraphDatasetManager initialisé")
    
    # ============================================
    # GESTION DES PROJETS
    # ============================================
    
    def create_project(self, name: str, description: str = "") -> Optional[str]:
        """
        Crée un nouveau projet
        
        Args:
            name: Nom du projet
            description: Description optionnelle
            
        Returns:
            UID du projet créé ou None en cas d'erreur
        """
        try:
            # Vérifier si le projet existe déjà
            existing = self.get_project_by_name(name)
            if existing:
                logger.warning(f"Le projet '{name}' existe déjà")
                return None
            
            project_uid = self.connector.create_project(name, description)
            
            if project_uid:
                self.current_project_uid = project_uid
                self.current_project_name = name
                self._cache['projects'][name] = project_uid
                logger.info(f"✅ Projet créé: {name} (UID: {project_uid})")
            
            return project_uid
            
        except Exception as e:
            logger.error(f"❌ Erreur création projet: {e}")
            return None
    
    def get_all_projects(self) -> List[Dict]:
        """
        Récupère tous les projets
        
        Returns:
            Liste des projets avec leurs métadonnées
        """
        try:
            query = """
            {
              projects(func: type(Project)) {
                uid
                name
                description
                createdAt
                updatedAt
                typologiesCount: count(typologies)
              }
            }
            """
            
            txn = self.connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            projects = data.get('projects', [])
            
            logger.info(f"📊 {len(projects)} projet(s) récupéré(s)")
            return projects
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération projets: {e}")
            return []
    
    def get_project_by_name(self, name: str) -> Optional[Dict]:
        """
        Récupère un projet par son nom
        
        Args:
            name: Nom du projet
            
        Returns:
            Dictionnaire contenant les données du projet ou None
        """
        try:
            projects = self.connector.get_project(name)
            if projects and len(projects) > 0:
                project = projects[0]
                self.current_project_uid = project.get('uid')
                self.current_project_name = name
                return project
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération projet '{name}': {e}")
            return None
    
    def update_project(self, project_uid: str, name: str = None, 
                      description: str = None) -> bool:
        """
        Met à jour un projet
        
        Args:
            project_uid: UID du projet
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {"uid": project_uid}
            
            if name is not None:
                mutation["name"] = name
            if description is not None:
                mutation["description"] = description
            
            mutation["updatedAt"] = datetime.now().isoformat() + "Z"
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            if name:
                self.current_project_name = name
            
            logger.info(f"✅ Projet mis à jour: {project_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour projet: {e}")
            return False
    
    def delete_project(self, project_uid: str) -> bool:
        """
        Supprime un projet et toutes ses données
        
        Args:
            project_uid: UID du projet
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            # Supprimer le projet (cascade via edges)
            mutation = {
                "uid": project_uid,
                "dgraph.type": None,
                "name": None,
                "description": None,
                "typologies": None
            }
            
            txn.mutate(del_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Projet supprimé: {project_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression projet: {e}")
            return False
    
    # ============================================
    # GESTION DES TYPOLOGIES
    # ============================================
    
    def add_typologie(self, typologie_name: str, description: str = "", 
                     position: int = 0) -> Optional[str]:
        """
        Ajoute une typologie au projet actuel
        
        Args:
            typologie_name: Nom de la typologie
            description: Description optionnelle
            position: Position dans la liste
            
        Returns:
            UID de la typologie créée ou None
        """
        if not self.current_project_uid:
            logger.error("Aucun projet actuel sélectionné")
            return None
        
        try:
            return self.connector.add_typologie(
                self.current_project_uid, 
                typologie_name, 
                description, 
                position
            )
        except Exception as e:
            logger.error(f"❌ Erreur ajout typologie: {e}")
            return None
    
    def get_typologies(self) -> List[Dict]:
        """
        Récupère toutes les typologies du projet actuel
        
        Returns:
            Liste des typologies
        """
        if not self.current_project_name:
            return []
        
        try:
            projects = self.connector.get_project(self.current_project_name)
            if projects and len(projects) > 0:
                return projects[0].get('typologies', [])
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération typologies: {e}")
            return []
    
    def update_typologie(self, typologie_uid: str, name: str = None, 
                        description: str = None, position: int = None) -> bool:
        """
        Met à jour une typologie
        
        Args:
            typologie_uid: UID de la typologie
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)
            position: Nouvelle position (optionnel)
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {"uid": typologie_uid}
            
            if name is not None:
                mutation["name"] = name
            if description is not None:
                mutation["description"] = description
            if position is not None:
                mutation["position"] = position
            
            mutation["updatedAt"] = datetime.now().isoformat() + "Z"
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Typologie mise à jour: {typologie_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour typologie: {e}")
            return False
    
    def delete_typologie(self, typologie_uid: str) -> bool:
        """
        Supprime une typologie et tous ses clusters
        
        Args:
            typologie_uid: UID de la typologie
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {
                "uid": typologie_uid,
                "dgraph.type": None,
                "name": None,
                "clusters": None
            }
            
            txn.mutate(del_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Typologie supprimée: {typologie_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression typologie: {e}")
            return False
    
    # ============================================
    # GESTION DES CLUSTERS DE TAXONOMIE
    # ============================================
    
    def add_cluster(self, typologie_uid: str, cluster_name: str, 
                   description: str = "", position: int = 0) -> Optional[str]:
        """
        Ajoute un cluster à une typologie
        
        Args:
            typologie_uid: UID de la typologie parent
            cluster_name: Nom du cluster
            description: Description optionnelle
            position: Position dans la liste
            
        Returns:
            UID du cluster créé ou None
        """
        try:
            return self.connector.add_cluster(
                typologie_uid, 
                cluster_name, 
                description, 
                position
            )
        except Exception as e:
            logger.error(f"❌ Erreur ajout cluster: {e}")
            return None
    
    def get_clusters(self, typologie_uid: str) -> List[Dict]:
        """
        Récupère tous les clusters d'une typologie
        
        Args:
            typologie_uid: UID de la typologie
            
        Returns:
            Liste des clusters
        """
        try:
            result = self.connector.expand_typologie(typologie_uid)
            if result and len(result) > 0:
                return result[0].get('clusters', [])
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération clusters: {e}")
            return []
    
    def update_cluster(self, cluster_uid: str, name: str = None, 
                      description: str = None, position: int = None) -> bool:
        """
        Met à jour un cluster
        
        Args:
            cluster_uid: UID du cluster
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)
            position: Nouvelle position (optionnel)
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {"uid": cluster_uid}
            
            if name is not None:
                mutation["name"] = name
            if description is not None:
                mutation["description"] = description
            if position is not None:
                mutation["position"] = position
            
            mutation["updatedAt"] = datetime.now().isoformat() + "Z"
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Cluster mis à jour: {cluster_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour cluster: {e}")
            return False
    
    def delete_cluster(self, cluster_uid: str) -> bool:
        """
        Supprime un cluster et tous ses root labels
        
        Args:
            cluster_uid: UID du cluster
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {
                "uid": cluster_uid,
                "dgraph.type": None,
                "name": None,
                "rootLabels": None
            }
            
            txn.mutate(del_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Cluster supprimé: {cluster_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression cluster: {e}")
            return False
    
    # ============================================
    # GESTION DES ROOT LABELS
    # ============================================
    
    def add_root_label(self, cluster_uid: str, label_name: str, 
                      description: str = "", category: str = "default", 
                      position: int = 0, **metadata) -> Optional[str]:
        """
        Ajoute un root label à un cluster
        
        Args:
            cluster_uid: UID du cluster parent
            label_name: Nom du label
            description: Description optionnelle
            category: Catégorie du label
            position: Position dans la liste
            **metadata: Métadonnées additionnelles (intentKeywords, etc.)
            
        Returns:
            UID du root label créé ou None
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {
                "uid": "_:rootlabel",
                "dgraph.type": "RootLabel",
                "name": label_name,
                "description": description,
                "category": category,
                "position": position,
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            # Ajouter métadonnées
            for key, value in metadata.items():
                if value is not None:
                    mutation[key] = value
            
            cluster_link = {
                "uid": cluster_uid,
                "rootLabels": [{"uid": "_:rootlabel"}]
            }
            
            response = txn.mutate(set_obj=[mutation, cluster_link])
            txn.commit()
            
            rootlabel_uid = response.uids["rootlabel"]
            logger.info(f"✅ Root label créé: {label_name} (UID: {rootlabel_uid})")
            return rootlabel_uid
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur ajout root label: {e}")
            return None
    
    def get_root_labels(self, cluster_uid: str) -> List[Dict]:
        """
        Récupère tous les root labels d'un cluster
        
        Args:
            cluster_uid: UID du cluster
            
        Returns:
            Liste des root labels
        """
        try:
            result = self.connector.expand_cluster(cluster_uid)
            if result and len(result) > 0:
                return result[0].get('rootLabels', [])
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération root labels: {e}")
            return []
    
    def update_root_label(self, root_uid: str, name: str = None, 
                         description: str = None, category: str = None,
                         position: int = None, **metadata) -> bool:
        """
        Met à jour un root label
        
        Args:
            root_uid: UID du root label
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)
            category: Nouvelle catégorie (optionnel)
            position: Nouvelle position (optionnel)
            **metadata: Métadonnées à mettre à jour
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {"uid": root_uid}
            
            if name is not None:
                mutation["name"] = name
            if description is not None:
                mutation["description"] = description
            if category is not None:
                mutation["category"] = category
            if position is not None:
                mutation["position"] = position
            
            # Ajouter métadonnées
            for key, value in metadata.items():
                if value is not None:
                    mutation[key] = value
            
            mutation["updatedAt"] = datetime.now().isoformat() + "Z"
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Root label mis à jour: {root_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour root label: {e}")
            return False
    
    def delete_root_label(self, root_uid: str) -> bool:
        """
        Supprime un root label
        
        Args:
            root_uid: UID du root label
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {
                "uid": root_uid,
                "dgraph.type": None,
                "name": None,
                "children": None
            }
            
            txn.mutate(del_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Root label supprimé: {root_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression root label: {e}")
            return False
    
    # ============================================
    # GESTION DES LABEL NODES (Parents/Children)
    # ============================================
    
    def add_label_node(self, parent_uid: str, label_name: str, 
                      description: str = "", category: str = "default",
                      depth: int = 0, position: int = 0, **metadata) -> Optional[str]:
        """
        Ajoute un label node (parent ou enfant)
        
        Args:
            parent_uid: UID du parent (RootLabel ou LabelNode)
            label_name: Nom du label
            description: Description optionnelle
            category: Catégorie du label
            depth: Profondeur dans l'arbre
            position: Position dans la liste
            **metadata: Métadonnées additionnelles
            
        Returns:
            UID du label node créé ou None
        """
        try:
            return self.connector.add_label_node(
                parent_uid, 
                label_name, 
                description, 
                category, 
                depth, 
                position, 
                **metadata
            )
        except Exception as e:
            logger.error(f"❌ Erreur ajout label node: {e}")
            return None
    
    def get_children(self, parent_uid: str, limit: int = 50, 
                    offset: int = 0) -> Tuple[List[Dict], int]:
        """
        Récupère les enfants d'un nœud avec pagination
        
        Args:
            parent_uid: UID du parent
            limit: Nombre maximum d'enfants à retourner
            offset: Décalage pour la pagination
            
        Returns:
            Tuple (liste des enfants, nombre total d'enfants)
        """
        try:
            result = self.connector.get_node_by_uid(
                parent_uid, 
                load_children=True, 
                children_limit=limit, 
                children_offset=offset
            )
            
            if result and len(result) > 0:
                node = result[0]
                children = node.get('children', [])
                total = node.get('totalChildren', len(children))
                return children, total
            
            return [], 0
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération enfants: {e}")
            return [], 0
    
    def update_label_node(self, node_uid: str, name: str = None, 
                         description: str = None, category: str = None,
                         position: int = None, depth: int = None, 
                         **metadata) -> bool:
        """
        Met à jour un label node
        
        Args:
            node_uid: UID du nœud
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)
            category: Nouvelle catégorie (optionnel)
            position: Nouvelle position (optionnel)
            depth: Nouvelle profondeur (optionnel)
            **metadata: Métadonnées à mettre à jour
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            mutation = {"uid": node_uid}
            
            if name is not None:
                mutation["name"] = name
            if description is not None:
                mutation["description"] = description
            if category is not None:
                mutation["category"] = category
            if position is not None:
                mutation["position"] = position
            if depth is not None:
                mutation["depth"] = depth
            
            # Ajouter métadonnées
            for key, value in metadata.items():
                if value is not None:
                    mutation[key] = value
            
            mutation["updatedAt"] = datetime.now().isoformat() + "Z"
            
            txn.mutate(set_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Label node mis à jour: {node_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur mise à jour label node: {e}")
            return False
    
    def delete_label_node(self, node_uid: str, recursive: bool = True) -> bool:
        """
        Supprime un label node
        
        Args:
            node_uid: UID du nœud
            recursive: Si True, supprime aussi les enfants
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            if recursive:
                # Récupérer tous les descendants
                descendants = self._get_all_descendants(node_uid)
                
                # Supprimer tous les descendants
                for desc_uid in descendants:
                    mutation = {
                        "uid": desc_uid,
                        "dgraph.type": None,
                        "name": None,
                        "children": None
                    }
                    txn.mutate(del_obj=mutation)
            
            # Supprimer le nœud principal
            mutation = {
                "uid": node_uid,
                "dgraph.type": None,
                "name": None,
                "children": None
            }
            
            txn.mutate(del_obj=mutation)
            txn.commit()
            
            logger.info(f"✅ Label node supprimé: {node_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur suppression label node: {e}")
            return False
    
    # ============================================
    # OPÉRATIONS DE RÉORGANISATION
    # ============================================
    
    def move_node(self, node_uid: str, new_parent_uid: str, 
                 new_position: int = 0) -> bool:
        """
        Déplace un nœud vers un nouveau parent
        
        Args:
            node_uid: UID du nœud à déplacer
            new_parent_uid: UID du nouveau parent
            new_position: Nouvelle position dans la liste
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            # Récupérer l'ancien parent
            old_parent_query = f"""
            {{
              node(func: uid({node_uid})) {{
                parent {{
                  uid
                }}
              }}
            }}
            """
            
            resp = txn.query(old_parent_query)
            data = json.loads(resp.json)
            
            old_parent_uid = None
            if data.get('node') and len(data['node']) > 0:
                parent = data['node'][0].get('parent')
                if parent:
                    old_parent_uid = parent.get('uid')
            
            # Supprimer l'ancien lien
            if old_parent_uid:
                remove_mutation = {
                    "uid": old_parent_uid,
                    "children": [{"uid": node_uid}]
                }
                txn.mutate(del_obj=remove_mutation)
            
            # Créer le nouveau lien
            add_mutation = {
                "uid": new_parent_uid,
                "children": [{"uid": node_uid}]
            }
            
            # Mettre à jour la position
            position_mutation = {
                "uid": node_uid,
                "position": new_position,
                "updatedAt": datetime.now().isoformat() + "Z"
            }
            
            txn.mutate(set_obj=[add_mutation, position_mutation])
            txn.commit()
            
            logger.info(f"✅ Nœud déplacé: {node_uid} vers {new_parent_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur déplacement nœud: {e}")
            return False
    
    def reorder_children(self, parent_uid: str, 
                        ordered_child_uids: List[str]) -> bool:
        """
        Réorganise les enfants d'un parent
        
        Args:
            parent_uid: UID du parent
            ordered_child_uids: Liste ordonnée des UIDs des enfants
            
        Returns:
            True si succès, False sinon
        """
        try:
            txn = self.connector.client.txn()
            
            # Mettre à jour la position de chaque enfant
            for position, child_uid in enumerate(ordered_child_uids):
                mutation = {
                    "uid": child_uid,
                    "position": position,
                    "updatedAt": datetime.now().isoformat() + "Z"
                }
                txn.mutate(set_obj=mutation)
            
            txn.commit()
            
            logger.info(f"✅ Enfants réordonnés pour: {parent_uid}")
            return True
            
        except Exception as e:
            txn.discard()
            logger.error(f"❌ Erreur réorganisation enfants: {e}")
            return False
    
    # ============================================
    # RECHERCHE ET NAVIGATION
    # ============================================
    
    def search_by_name(self, search_term: str, node_types: List[str] = None) -> List[Dict]:
        """
        Recherche globale par nom
        
        Args:
            search_term: Terme de recherche
            node_types: Types de nœuds à rechercher (optionnel)
            
        Returns:
            Liste des résultats
        """
        try:
            type_filter = ""
            if node_types:
                type_conditions = " OR ".join([f'eq(dgraph.type, "{t}")' for t in node_types])
                type_filter = f"@filter({type_conditions})"
            
            query = f"""
            {{
              search(func: allofterms(name, "{search_term}")) {type_filter} {{
                uid
                name
                dgraph.type
                description
                category
                position
                depth
                
                parent {{
                  uid
                  name
                }}
              }}
            }}
            """
            
            txn = self.connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            results = data.get('search', [])
            
            logger.info(f"🔍 Recherche '{search_term}': {len(results)} résultat(s)")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche: {e}")
            return []
    
    def get_path_to_root(self, node_uid: str) -> List[Dict]:
        """
        Récupère le chemin complet de la racine au nœud
        
        Args:
            node_uid: UID du nœud
            
        Returns:
            Liste des nœuds du chemin (de la racine au nœud)
        """
        try:
            result = self.connector.get_path_to_root(node_uid)
            if result and len(result) > 0:
                # Reconstruire le chemin dans l'ordre
                path = []
                current = result[0]
                
                # Remonter récursivement
                def build_path(node, accumulated):
                    accumulated.insert(0, {
                        'uid': node.get('uid'),
                        'name': node.get('name'),
                        'type': node.get('dgraph.type')
                    })
                    
                    parent = node.get('parent')
                    if parent:
                        build_path(parent, accumulated)
                
                build_path(current, path)
                return path
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération chemin: {e}")
            return []
    
    def get_node_statistics(self, node_uid: str) -> Dict[str, Any]:
        """
        Récupère les statistiques d'un nœud
        
        Args:
            node_uid: UID du nœud
            
        Returns:
            Dictionnaire contenant les statistiques
        """
        try:
            query = f"""
            {{
              node(func: uid({node_uid})) {{
                uid
                name
                dgraph.type
                depth
                childrenCount: count(children)
                
                # Compter les descendants récursivement
                children @recurse(depth: 20) {{
                  uid
                  children
                }}
              }}
            }}
            """
            
            txn = self.connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            
            if data.get('node') and len(data['node']) > 0:
                node = data['node'][0]
                
                # Compter tous les descendants
                descendants = self._count_descendants(node)
                
                stats = {
                    'uid': node.get('uid'),
                    'name': node.get('name'),
                    'type': node.get('dgraph.type'),
                    'depth': node.get('depth', 0),
                    'direct_children': node.get('childrenCount', 0),
                    'total_descendants': descendants
                }
                
                return stats
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération statistiques: {e}")
            return {}
    
    # ============================================
    # IMPORT/EXPORT
    # ============================================
    
    def export_project_to_json(self, project_name: str) -> Optional[Dict]:
        """
        Exporte un projet complet en JSON
        
        Args:
            project_name: Nom du projet
            
        Returns:
            Dictionnaire contenant toutes les données du projet
        """
        try:
            project = self.get_project_by_name(project_name)
            if not project:
                logger.error(f"Projet '{project_name}' non trouvé")
                return None
            
            # Construire la structure complète
            export_data = {
                'project': {
                    'uid': project.get('uid'),
                    'name': project.get('name'),
                    'description': project.get('description'),
                    'createdAt': project.get('createdAt'),
                    'updatedAt': project.get('updatedAt')
                },
                'typologies': []
            }
            
            # Récupérer toutes les typologies
            for typologie in project.get('typologies', []):
                typ_data = {
                    'uid': typologie.get('uid'),
                    'name': typologie.get('name'),
                    'description': typologie.get('description'),
                    'position': typologie.get('position'),
                    'clusters': []
                }
                
                # Récupérer les clusters
                clusters = self.get_clusters(typologie.get('uid'))
                for cluster in clusters:
                    cluster_data = {
                        'uid': cluster.get('uid'),
                        'name': cluster.get('name'),
                        'description': cluster.get('description'),
                        'position': cluster.get('position'),
                        'rootLabels': []
                    }
                    
                    # Récupérer les root labels
                    roots = self.get_root_labels(cluster.get('uid'))
                    for root in roots:
                        root_data = {
                            'uid': root.get('uid'),
                            'name': root.get('name'),
                            'description': root.get('description'),
                            'category': root.get('category'),
                            'position': root.get('position'),
                            'children': self._export_children_recursive(root.get('uid'))
                        }
                        cluster_data['rootLabels'].append(root_data)
                    
                    typ_data['clusters'].append(cluster_data)
                
                export_data['typologies'].append(typ_data)
            
            logger.info(f"✅ Projet '{project_name}' exporté")
            return export_data
            
        except Exception as e:
            logger.error(f"❌ Erreur export projet: {e}")
            return None
    
    def import_project_from_json(self, data: Dict) -> Optional[str]:
        """
        Importe un projet depuis JSON
        
        Args:
            data: Données du projet au format JSON
            
        Returns:
            UID du projet créé ou None
        """
        try:
            project_data = data.get('project', {})
            project_name = project_data.get('name')
            project_desc = project_data.get('description', '')
            
            # Créer le projet
            project_uid = self.create_project(project_name, project_desc)
            if not project_uid:
                return None
            
            # Importer les typologies
            for typ_data in data.get('typologies', []):
                typ_uid = self.add_typologie(
                    typ_data.get('name'),
                    typ_data.get('description', ''),
                    typ_data.get('position', 0)
                )
                
                if not typ_uid:
                    continue
                
                # Importer les clusters
                for cluster_data in typ_data.get('clusters', []):
                    cluster_uid = self.add_cluster(
                        typ_uid,
                        cluster_data.get('name'),
                        cluster_data.get('description', ''),
                        cluster_data.get('position', 0)
                    )
                    
                    if not cluster_uid:
                        continue
                    
                    # Importer les root labels
                    for root_data in cluster_data.get('rootLabels', []):
                        root_uid = self.add_root_label(
                            cluster_uid,
                            root_data.get('name'),
                            root_data.get('description', ''),
                            root_data.get('category', 'default'),
                            root_data.get('position', 0)
                        )
                        
                        if not root_uid:
                            continue
                        
                        # Importer les enfants récursivement
                        self._import_children_recursive(
                            root_uid, 
                            root_data.get('children', []),
                            depth=0
                        )
            
            logger.info(f"✅ Projet '{project_name}' importé")
            return project_uid
            
        except Exception as e:
            logger.error(f"❌ Erreur import projet: {e}")
            return None
    
    # ============================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # ============================================
    
    def _get_all_descendants(self, node_uid: str) -> List[str]:
        """Récupère tous les UIDs des descendants"""
        try:
            query = f"""
            {{
              descendants(func: uid({node_uid})) @recurse(depth: 20) {{
                uid
                children
              }}
            }}
            """
            
            txn = self.connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json)
            descendants = []
            
            def collect_uids(nodes):
                for node in nodes:
                    uid = node.get('uid')
                    if uid and uid != node_uid:
                        descendants.append(uid)
                    
                    children = node.get('children', [])
                    if children:
                        collect_uids(children)
            
            if data.get('descendants'):
                collect_uids(data['descendants'])
            
            return descendants
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération descendants: {e}")
            return []
        
    def get_typologie_by_name(self, project_name: str, typologie_name: str):
        """
        Récupère une typologie par nom

        Returns:
            dict avec 'uid', 'name' ou None
        """
        query = f"""
        {{
          typologie(func: type(Typologie)) @filter(eq(name, "{typologie_name}")) {{
            uid
            name
            description
            position
          }}
        }}
        """

        try:
            resp = self.connector.client.txn(read_only=True).query(query)
            data = json.loads(resp.json)
            results = data.get('typologie', [])
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Erreur get_typologie_by_name: {e}")
            return None

    def get_cluster_by_name(self, typologie_uid: str, cluster_name: str):
        """
        Récupère un cluster par nom dans une typologie

        Returns:
            dict avec 'uid', 'name' ou None
        """
        query = f"""
        {{
          cluster(func: uid({typologie_uid})) {{
            clusters @filter(eq(name, "{cluster_name}")) {{
              uid
              name
              description
              position
            }}
          }}
        }}
        """

        try:
            resp = self.connector.client.txn(read_only=True).query(query)
            data = json.loads(resp.json)
            results = data.get('cluster', [])
            if results and results[0].get('clusters'):
                return results[0]['clusters'][0]
            return None
        except Exception as e:
            logger.error(f"Erreur get_cluster_by_name: {e}")
            return None

    def get_root_label_by_name(self, cluster_uid: str, root_name: str):
        """
        Récupère un root label par nom
        """
        query = f"""
        {{
          root(func: uid({cluster_uid})) {{
            rootLabels @filter(eq(name, "{root_name}")) {{
              uid
              name
              description
              category
              position
            }}
          }}
        }}
        """

        try:
            resp = self.connector.client.txn(read_only=True).query(query)
            data = json.loads(resp.json)
            results = data.get('root', [])
            if results and results[0].get('rootLabels'):
                return results[0]['rootLabels'][0]
            return None
        except Exception as e:
            logger.error(f"Erreur get_root_label_by_name: {e}")
            return None

    def get_label_node_by_name(self, parent_uid: str, label_name: str):
        """
        Récupère un label node enfant par nom
        """
        query = f"""
        {{
          parent(func: uid({parent_uid})) {{
            children @filter(eq(name, "{label_name}")) {{
              uid
              name
              description
              depth
              position
            }}
          }}
        }}
        """

        try:
            resp = self.connector.client.txn(read_only=True).query(query)
            data = json.loads(resp.json)
            results = data.get('parent', [])
            if results and results[0].get('children'):
                return results[0]['children'][0]
            return None
        except Exception as e:
            logger.error(f"Erreur get_label_node_by_name: {e}")
            return None
    
    def _count_descendants(self, node: Dict) -> int:
        """Compte récursivement tous les descendants"""
        count = 0
        children = node.get('children', [])
        
        for child in children:
            count += 1
            count += self._count_descendants(child)
        
        return count
    
    def _export_children_recursive(self, parent_uid: str) -> List[Dict]:
        """Exporte récursivement les enfants"""
        children_data = []
        children, _ = self.get_children(parent_uid, limit=1000)
        
        for child in children:
            child_data = {
                'uid': child.get('uid'),
                'name': child.get('name'),
                'description': child.get('description', ''),
                'category': child.get('category', 'default'),
                'depth': child.get('depth', 0),
                'position': child.get('position', 0),
                'children': self._export_children_recursive(child.get('uid'))
            }
            children_data.append(child_data)
        
        return children_data
    
    def _import_children_recursive(self, parent_uid: str, children_data: List[Dict], 
                                   depth: int = 0):
        """Importe récursivement les enfants"""
        for child_data in children_data:
            child_uid = self.add_label_node(
                parent_uid,
                child_data.get('name'),
                child_data.get('description', ''),
                child_data.get('category', 'default'),
                depth,
                child_data.get('position', 0)
            )
            
            if child_uid:
                # Importer les sous-enfants
                sub_children = child_data.get('children', [])
                if sub_children:
                    self._import_children_recursive(child_uid, sub_children, depth + 1)
    
    # ============================================
    # GESTION DU CACHE
    # ============================================
    
    def clear_cache(self):
        """Vide le cache local"""
        self._cache = {
            'projects': {},
            'typologies': {},
            'clusters': {},
            'roots': {},
            'parents': {},
            'children': {}
        }
        logger.debug("🗑️ Cache vidé")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Retourne les statistiques du cache"""
        return {
            'projects': len(self._cache['projects']),
            'typologies': len(self._cache['typologies']),
            'clusters': len(self._cache['clusters']),
            'roots': len(self._cache['roots']),
            'parents': len(self._cache['parents']),
            'children': len(self._cache['children'])
        }
    
    # ============================================
    # FERMETURE
    # ============================================
    
    def close(self):
        """Ferme la connexion Dgraph"""
        if self.connector:
            self.connector.close()
            logger.info("✅ DgraphDatasetManager fermé")