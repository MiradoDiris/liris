import json
import logging
import hashlib
from datetime import datetime
from typing import Optional, List, Dict
import pydgraph

logger = logging.getLogger(__name__)


class DgraphTaxonomyManager:
    def __init__(self, dgraph_url="localhost:8090"):
        """Initialise la connexion à Dgraph"""
        self.dgraph_url = dgraph_url
        self.client_stub = None
        self.client = None
        self._init_connection()
        self._init_schema()

    def _init_connection(self):
        """Établit la connexion avec Dgraph"""
        try:
            self.client_stub = pydgraph.DgraphClientStub(self.dgraph_url)
            self.client = pydgraph.DgraphClient(self.client_stub)
            logger.info(f"Connexion Dgraph établie: {self.dgraph_url}")
        except Exception as e:
            logger.error(f"Erreur connexion Dgraph: {str(e)}")
            raise e

    def _init_schema(self):
        """Définit le schéma Dgraph avec la taxonomie complète"""
        schema = """
        
        type Project {
            project_name
            description
            typologies
            batches
            created_at
            updated_at
        }

        type Typologie {
            typologie_name
            description
            position
            project
            taxonomy_clusters
        }

        type TaxonomyCluster {
            cluster_name
            description
            position
            typologie
            root_labels
        }

        type RootLabel {
            label_name
            description
            category
            position
            taxonomy_cluster
            parent_labels
        }

        type ParentLabel {
            label_name
            description
            category
            position
            root_label
            children
        }

        type ChildLabel {
            label_name
            description
            category
            depth
            position
            parent_label
            parent_child
            children
        }

        # ==========================================
        # TYPES POUR COMBINAISONS
        # ==========================================

        type Batch {
            batch_uuid
            batch_number
            total_batches
            project_name
            project
            combinations
            status
            prompt_template
            created_at
            processed_at
        }

        type ContextCombination {
            combination_uuid
            combination_hash
            batch
            selected_nodes
            sample_count
            typologie_distribution
            created_at
        }

        # ==========================================
        # PRÉDICATS
        # ==========================================
        
        # Noms et descriptions
        project_name: string @index(exact, term) .
        typologie_name: string @index(exact, term) .
        cluster_name: string @index(exact, term) .
        label_name: string @index(exact, term, fulltext) .
        description: string @index(fulltext) .
        
        # Métadonnées taxonomiques
        category: string @index(exact) .
        position: int @index(int) .
        depth: int @index(int) .
        
        # Métadonnées batch/combinaisons
        batch_uuid: string @index(exact) .
        batch_number: int @index(int) .
        total_batches: int .
        combination_uuid: string @index(exact) .
        combination_hash: string @index(exact) .
        sample_count: int .
        status: string @index(exact) .
        prompt_template: string .
        typologie_distribution: string .
        
        # Relations hiérarchiques (un seul parent)
        project: uid @reverse .
        typologie: uid @reverse .
        taxonomy_cluster: uid @reverse .
        root_label: uid @reverse .
        parent_label: uid @reverse .
        parent_child: uid @reverse .
        batch: uid @reverse .
        
        # Relations de collection (plusieurs enfants)
        typologies: [uid] @reverse .
        taxonomy_clusters: [uid] @reverse .
        root_labels: [uid] @reverse .
        parent_labels: [uid] @reverse .
        children: [uid] @reverse .
        batches: [uid] @reverse .
        combinations: [uid] @reverse .
        selected_nodes: [uid] @reverse .
        
        # Timestamps
        created_at: datetime @index(hour) .
        updated_at: datetime @index(hour) .
        processed_at: datetime .
        """

        try:
            op = pydgraph.Operation(schema=schema)
            self.client.alter(op)
            logger.info("Schéma Dgraph avec taxonomie complète initialisé")
        except Exception as e:
            logger.error(f"Erreur initialisation schéma: {str(e)}")
            raise e

    def sync_project_from_sqlite(self, project_data: Dict) -> Optional[str]:
        """
        Synchronise AUTOMATIQUEMENT un projet complet depuis SQLite vers Dgraph
        Crée toute la hiérarchie: Typologie → Cluster → Root → Parent → Child → ...
        
        project_data: Structure complète depuis dataset_database.get_dataset_projet()
        {
            'nom': 'mon_projet',
            'description': '...',
            'typologies': [...]
        }
        """
        try:
            project_name = project_data['nom']
            
            txn = self.client.txn()
            try:
                # Vérifier si le projet existe déjà
                query = f'''
                {{
                    existing(func: eq(project_name, "{project_name}")) @filter(type(Project)) {{
                        uid
                    }}
                }}
                '''
                res = json.loads(txn.query(query).json)
                
                # Si existe, le supprimer pour recréer (synchronisation complète)
                if res.get('existing'):
                    existing_uid = res['existing'][0]['uid']
                    txn.mutate(del_obj={'uid': existing_uid})
                    logger.info(f"Projet existant '{project_name}' supprimé pour resync")

                # Créer le projet complet
                project_node = {
                    'dgraph.type': 'Project',
                    'project_name': project_name,
                    'description': project_data.get('description', ''),
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'typologies': []
                }

                # Créer toutes les typologies
                for typ_idx, typologie in enumerate(project_data.get('typologies', [])):
                    typologie_node = self._create_typologie_node(
                        typologie, 
                        typ_idx
                    )
                    project_node['typologies'].append(typologie_node)

                # Sauvegarder tout
                mutation = txn.mutate(set_obj=project_node)
                txn.commit()
                
                project_uid = list(mutation.uids.values())[0]
                logger.info(f"Projet '{project_name}' synchronisé dans Dgraph avec hiérarchie complète")
                return project_uid

            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur sync projet: {str(e)}")
            return None

    def _create_typologie_node(self, typologie: Dict, position: int) -> Dict:
        """Crée un nœud Typologie avec tous ses clusters"""
        typologie_node = {
            'dgraph.type': 'Typologie',
            'typologie_name': typologie['name'],
            'description': typologie.get('description', ''),
            'position': position,
            'taxonomy_clusters': []
        }

        for cluster_idx, cluster in enumerate(typologie.get('taxonomy_clusters', [])):
            cluster_node = self._create_cluster_node(cluster, cluster_idx)
            typologie_node['taxonomy_clusters'].append(cluster_node)

        return typologie_node

    def _create_cluster_node(self, cluster: Dict, position: int) -> Dict:
        """Crée un nœud TaxonomyCluster avec tous ses root labels"""
        cluster_node = {
            'dgraph.type': 'TaxonomyCluster',
            'cluster_name': cluster['name'],
            'description': cluster.get('description', ''),
            'position': position,
            'root_labels': []
        }

        for root_idx, root in enumerate(cluster.get('root_labels', [])):
            root_node = self._create_root_label_node(root, root_idx)
            cluster_node['root_labels'].append(root_node)

        return cluster_node

    def _create_root_label_node(self, root: Dict, position: int) -> Dict:
        """Crée un nœud RootLabel avec tous ses parent labels"""
        root_node = {
            'dgraph.type': 'RootLabel',
            'label_name': root['name'],
            'description': root.get('description', ''),
            'category': root.get('category', 'default'),
            'position': position,
            'parent_labels': []
        }

        for parent_idx, parent in enumerate(root.get('parent_labels', [])):
            parent_node = self._create_parent_label_node(parent, parent_idx)
            root_node['parent_labels'].append(parent_node)

        return root_node

    def _create_parent_label_node(self, parent: Dict, position: int) -> Dict:
        """Crée un nœud ParentLabel avec tous ses enfants"""
        parent_node = {
            'dgraph.type': 'ParentLabel',
            'label_name': parent['name'],
            'description': parent.get('description', ''),
            'category': parent.get('category', 'default'),
            'position': position,
            'children': []
        }

        for child_idx, child in enumerate(parent.get('children', [])):
            child_node = self._create_child_label_node(child, child_idx, depth=0)
            parent_node['children'].append(child_node)

        return parent_node

    def _create_child_label_node(self, child: Dict, position: int, depth: int) -> Dict:
        """Crée un nœud ChildLabel RÉCURSIVEMENT (profondeur infinie)"""
        child_node = {
            'dgraph.type': 'ChildLabel',
            'label_name': child['name'],
            'description': child.get('description', ''),
            'category': child.get('category', 'default'),
            'depth': depth,
            'position': position,
            'children': []
        }

        # RÉCURSION pour les sous-enfants (infini)
        for sub_idx, sub_child in enumerate(child.get('children', [])):
            sub_node = self._create_child_label_node(sub_child, sub_idx, depth=depth+1)
            child_node['children'].append(sub_node)

        return child_node

    def get_full_taxonomy(self, project_name: str) -> Optional[Dict]:
        """
        Récupère la taxonomie COMPLÈTE d'un projet depuis Dgraph
        Retourne la structure hiérarchique entière
        """
        try:
            query = f'''
            {{
                project(func: eq(project_name, "{project_name}")) @filter(type(Project)) {{
                    uid
                    project_name
                    description
                    created_at
                    typologies (orderasc: position) {{
                        uid
                        typologie_name
                        description
                        position
                        taxonomy_clusters (orderasc: position) {{
                            uid
                            cluster_name
                            description
                            position
                            root_labels (orderasc: position) {{
                                uid
                                label_name
                                description
                                category
                                position
                                parent_labels (orderasc: position) {{
                                    uid
                                    label_name
                                    description
                                    category
                                    position
                                    children (orderasc: position) @recurse(depth: 20) {{
                                        uid
                                        label_name
                                        description
                                        category
                                        depth
                                        position
                                        children
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            '''
            
            txn = self.client.txn(read_only=True)
            try:
                res = json.loads(txn.query(query).json)
                projects = res.get('project', [])
                return projects[0] if projects else None
            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur récupération taxonomie: {str(e)}")
            return None

    def find_node_by_path(
        self,
        project_name: str,
        typologie_name: str,
        path: str
    ) -> Optional[str]:
        """
        Trouve l'UID d'un nœud via son chemin
        path: 'cluster_name/root_name/parent_name/child1/child2/...'
        """
        try:
            parts = path.split('/')
            
            # Construire la query progressive
            query = f'''
            {{
                project(func: eq(project_name, "{project_name}")) @filter(type(Project)) {{
                    typologies @filter(eq(typologie_name, "{typologie_name}")) {{
            '''
            
            # Niveau cluster
            if len(parts) >= 1:
                query += f'''
                        taxonomy_clusters @filter(eq(cluster_name, "{parts[0]}")) {{
                '''
            
            # Niveau root
            if len(parts) >= 2:
                query += f'''
                            root_labels @filter(eq(label_name, "{parts[1]}")) {{
                '''
            
            # Niveau parent
            if len(parts) >= 3:
                query += f'''
                                parent_labels @filter(eq(label_name, "{parts[2]}")) {{
                '''
            
            # Niveaux children (récursif)
            if len(parts) >= 4:
                for i in range(3, len(parts)):
                    query += f'''
                                    children @filter(eq(label_name, "{parts[i]}")) {{
                    '''
            
            # Fermer toutes les accolades et récupérer l'UID
            query += 'uid ' + '}' * len(parts) + '}}}'
            
            txn = self.client.txn(read_only=True)
            try:
                res = json.loads(txn.query(query).json)
                
                # Naviguer dans le résultat pour extraire l'UID
                node = res.get('project', [{}])[0]
                
                if 'typologies' in node and node['typologies']:
                    node = node['typologies'][0]
                else:
                    return None
                
                for level in ['taxonomy_clusters', 'root_labels', 'parent_labels'] + ['children'] * (len(parts) - 3):
                    if level in node and node[level]:
                        node = node[level][0]
                    else:
                        return None
                
                return node.get('uid')
                
            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur recherche nœud: {str(e)}")
            return None

    def save_batch_combinations(
        self,
        project_name: str,
        batch_number: int,
        total_batches: int,
        combinations: List[Dict],
        prompt_template: str = "",
        status: str = "pending"
    ) -> Optional[str]:
        """
        Sauvegarde un batch avec ses combinaisons
        Les combinaisons référencent directement les nœuds de la taxonomie
        
        combinations: [
            {
                'nodes': [
                    {
                        'typologie': 'Contexte Géographique',
                        'path': 'Lieux urbains/Ville/Paris'
                    },
                    {
                        'typologie': 'Contexte Temporel',
                        'path': 'Périodes/Jour/Matin/Début'
                    }
                ],
                'sample_count': 5
            }
        ]
        """
        try:
            # Vérifier que le projet existe
            query = f'''
            {{
                project(func: eq(project_name, "{project_name}")) @filter(type(Project)) {{
                    uid
                }}
            }}
            '''
            
            txn = self.client.txn()
            try:
                res = json.loads(txn.query(query).json)
                
                if not res.get('project'):
                    logger.error(f"Projet '{project_name}' non trouvé dans Dgraph. Synchronisez d'abord.")
                    return None
                
                project_uid = res['project'][0]['uid']
                batch_uuid = f"{project_name}_batch_{batch_number}"

                # Créer le batch
                batch_node = {
                    'dgraph.type': 'Batch',
                    'batch_uuid': batch_uuid,
                    'batch_number': batch_number,
                    'total_batches': total_batches,
                    'project_name': project_name,
                    'project': {'uid': project_uid},
                    'status': status,
                    'prompt_template': prompt_template,
                    'created_at': datetime.now().isoformat(),
                    'combinations': []
                }

                # Créer les combinaisons
                for idx, combo in enumerate(combinations):
                    combo_hash = self._generate_combination_hash(combo['nodes'])
                    combo_uuid = f"{batch_uuid}_combo_{idx}"

                    # Récupérer les UIDs des nœuds sélectionnés
                    node_uids = []
                    typologie_dist = {}

                    for node_ref in combo['nodes']:
                        typologie = node_ref['typologie']
                        path = node_ref['path']
                        
                        # Trouver le nœud dans la taxonomie
                        node_uid = self.find_node_by_path(project_name, typologie, path)
                        
                        if node_uid:
                            node_uids.append({'uid': node_uid})
                            typologie_dist[typologie] = typologie_dist.get(typologie, 0) + 1
                        else:
                            logger.warning(f"Nœud non trouvé: {typologie}/{path}")

                    # Créer la combinaison
                    combo_node = {
                        'dgraph.type': 'ContextCombination',
                        'combination_uuid': combo_uuid,
                        'combination_hash': combo_hash,
                        'sample_count': combo.get('sample_count', 1),
                        'typologie_distribution': json.dumps(typologie_dist),
                        'created_at': datetime.now().isoformat(),
                        'selected_nodes': node_uids
                    }

                    batch_node['combinations'].append(combo_node)

                # Sauvegarder
                mutation = txn.mutate(set_obj=batch_node)
                txn.commit()
                
                logger.info(f"Batch {batch_number} créé avec {len(combinations)} combinaisons")
                return batch_uuid

            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur sauvegarde batch: {str(e)}")
            return None

    def _generate_combination_hash(self, nodes: List[Dict]) -> str:
        """Génère un hash unique pour une combinaison"""
        nodes_str = json.dumps(sorted(
            [f"{n['typologie']}:{n['path']}" for n in nodes]
        ))
        return hashlib.sha256(nodes_str.encode()).hexdigest()[:16]

    def get_batch_combinations(self, project_name: str, batch_number: int) -> List[Dict]:
        """Récupère les combinaisons d'un batch avec les détails des nœuds"""
        try:
            batch_uuid = f"{project_name}_batch_{batch_number}"
            
            query = f'''
            {{
                batch(func: eq(batch_uuid, "{batch_uuid}")) @filter(type(Batch)) {{
                    batch_uuid
                    batch_number
                    status
                    prompt_template
                    combinations {{
                        combination_uuid
                        combination_hash
                        sample_count
                        typologie_distribution
                        selected_nodes {{
                            uid
                            label_name
                            description
                            category
                            dgraph.type
                        }}
                    }}
                }}
            }}
            '''
            
            txn = self.client.txn(read_only=True)
            try:
                res = json.loads(txn.query(query).json)
                return res.get('batch', [])
            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur récupération combinaisons: {str(e)}")
            return []

    def get_distribution_stats(self, project_name: str) -> Dict:
        """Calcule les statistiques pour le camembert"""
        try:
            query = f'''
            {{
                project(func: eq(project_name, "{project_name}")) @filter(type(Project)) {{
                    batches {{
                        combinations {{
                            typologie_distribution
                            sample_count
                        }}
                    }}
                }}
            }}
            '''
            
            txn = self.client.txn(read_only=True)
            try:
                res = json.loads(txn.query(query).json)
                
                if not res.get('project'):
                    return {}

                typologie_totals = {}
                total_samples = 0

                for batch in res['project'][0].get('batches', []):
                    for combo in batch.get('combinations', []):
                        sample_count = combo.get('sample_count', 1)
                        total_samples += sample_count
                        
                        dist = json.loads(combo.get('typologie_distribution', '{}'))
                        for typ, count in dist.items():
                            typologie_totals[typ] = typologie_totals.get(typ, 0) + (sample_count * count)

                stats = {
                    'total_samples': total_samples,
                    'typologies': {}
                }

                for typ, count in typologie_totals.items():
                    stats['typologies'][typ] = {
                        'count': count,
                        'percentage': (count / total_samples * 100) if total_samples > 0 else 0
                    }

                return stats

            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Erreur calcul stats: {str(e)}")
            return {}

    def close(self):
        """Ferme la connexion Dgraph"""
        if self.client_stub:
            self.client_stub.close()
            logger.info("Connexion Dgraph fermée")
