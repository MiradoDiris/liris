from collections import defaultdict
from datetime import datetime
import json
from typing import Any, Dict, Optional
import uuid
from ui.widgets.tabs.relation_import_widget import TaxonomyItem
from utils.logger import logger
from utils.dgraph_connector import LirisDgraphConnector
from PyQt5 import QtWidgets
import time


class DgraphProjectManager:
    def __init__(self, dgraph_connector: LirisDgraphConnector):
        self.dgraph_connector = dgraph_connector
        self.local_to_dgraph = {}
        self.dgraph_to_local = {}
        self.label_uid_to_info = {}
        self.name_to_uid = {}

    def is_configured(self):
        """Vérifie si le connector Dgraph est configuré et prêt."""
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.warning("⚠️ Dgraph client non disponible ou non configuré")
            return False
        return True

    def _sanitize_uid(self, uid: str, prefix: str = "auto") -> str:

        if uid and isinstance(uid, str):
            # Format 0x... (UID Dgraph existant)
            if uid.startswith("0x"):
                return uid
            
            # Format _:... (blank node)
            if uid.startswith("_:"):
                return uid

        unique_suffix = str(uuid.uuid4()).replace('-', '')[:16]
        return f"_:{prefix}_{unique_suffix}"
    
    def _validate_uid_format(self, uid: str) -> bool:
        if not uid or not isinstance(uid, str):
            return False
        
        # Formats valides Dgraph
        if uid.startswith("_:") or uid.startswith("0x"):
            return True
        
        return False

    def _load_project_profiles(self):
        """✅ Charge depuis Dgraph SANS utiliser self.current_project_profile_data"""
        try:
            logger.info("📡 Chargement des profils depuis Dgraph...")

            if not self.dgraph_connector or not self.dgraph_connector.client:
                logger.warning("⚠️ Dgraph client non disponible")
                return {}

            query_result = self.dgraph_connector.query_workspaces()

            if not query_result or 'q' not in query_result:
                logger.warning("⚠️ Aucun résultat depuis Dgraph")
                return {}

            workspaces = query_result['q']
            logger.info(f"📦 {len(workspaces)} workspace(s) récupéré(s) depuis Dgraph")

            loaded_profiles = {}
            for ws in workspaces:
                profile = self._workspace_to_profile(ws)
                if profile and profile.get('name'):
                    project_name = profile['name']
                    loaded_profiles[project_name] = profile
                    logger.debug(f"   ✅ Chargé: {project_name}")

            logger.info(f"✅ Chargement Dgraph terminé: {len(loaded_profiles)} profil(s)")
            return loaded_profiles

        except Exception as e:
            logger.error(f"❌ ERREUR dans _load_project_profiles: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _workspace_to_profile(self, ws):
        """✅ Parsing robuste avec gestion d'erreurs"""
        try:
            profile_name = ws.get('name', '')
            logger.info(f"📄 Conversion workspace : {profile_name}")

            profile = {
                'uid': ws.get('uid', ''),
                'name': profile_name,
                'description': ws.get('description', ''),
                'files': ws.get('files', []),
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': {}
            }

            file_contents_raw = ws.get('fileContents', '{}')
            profile['file_contents'] = self._safe_json_parse(file_contents_raw, {})

            cm = ws.get('clusterManagement', {})
            if not cm:
                logger.warning(f"Aucun clusterManagement pour workspace '{ws.get('name')}'")
                return profile

            for cluster in cm.get('clusters', []):
                cluster_data = {
                    'name': cluster.get('name', ''),
                    'uid': cluster.get('uid', ''),
                    'description': cluster.get('description', ''),
                    'files': cluster.get('files', []),
                    'file_contents': self._safe_json_parse(cluster.get('fileContents', '{}'), {}),
                    'root_labels': []
                }

                for root_label in cluster.get('root_labels', []):
                    try:
                        root_data = self._label_to_data(root_label)
                        cluster_data['root_labels'].append(root_data)
                        self._fill_hierarchy(root_data, root_label)
                    except Exception as e:
                        logger.error(f"❌ Erreur root_label '{root_label.get('name')}': {e}")
                        continue

                profile['turing_ontology']['clusters_detailed'].append(cluster_data)

            for cluster in profile['turing_ontology']['clusters_detailed']:
                for root_label in cluster['root_labels']:
                    self._map_uids_recursive(root_label)

            return profile

        except Exception as e:
            logger.error(f"❌ ERREUR CRITIQUE dans _workspace_to_profile: {e}")
            import traceback
            traceback.print_exc()
            return {
                'uid': ws.get('uid', ''),
                'name': ws.get('name', 'Projet Erreur'),
                'description': f"Erreur de chargement: {str(e)}",
                'files': [],
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': {}
            }

    def _safe_json_parse(self, data, default=None):
        """✅ Helper pour parser JSON de manière robuste"""
        if default is None:
            default = {}

        if isinstance(data, dict):
            return data
        elif isinstance(data, str):
            data = data.strip()
            if not data or data == '{}':
                return default
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Erreur parsing JSON: {e}")
                return default
        elif isinstance(data, bytes):
            try:
                return json.loads(data.decode('utf-8').strip() or '{}')
            except:
                return default
        else:
            logger.warning(f"Type inattendu pour JSON: {type(data)}")
            return default

    def _label_to_data(self, label):
        """✅ Parser relations avec catégories correctes"""
        try:
            data = {
                'label': label.get('name', ''),
                'id': label.get('id', ''),
                'uid': label.get('uid', ''),
                'description': label.get('description', ''),
                'category': label.get('category', []),
                'files': label.get('files', []),
                'file_contents': self._safe_json_parse(label.get('fileContents', '{}'), {}),
                'parents': [],
                'children': [],
                'outgoing_relations': [],
                'incoming_relations': []
            }

            label_uid = label.get('uid')

            for rel in label.get('relations', []):
                target_node = rel.get('target', {})
                if not target_node or not target_node.get('uid'):
                    continue
                
                rel_type = rel.get('relationType', 'relation')
                category = self._get_relation_category(rel_type)

                data['outgoing_relations'].append({
                    'target_uid': target_node.get('uid'),
                    'target_id': target_node.get('id', ''),
                    'target_name': target_node.get('name', ''),
                    'relation_type': rel_type,
                    'category': category,
                    'line': 0
                })

            for rel in label.get('~target', []):
                source_node = rel.get('source', {})
                if not source_node or not source_node.get('uid'):
                    continue
                
                rel_type = rel.get('relationType', 'relation')
                category = self._get_relation_category(rel_type)

                data['incoming_relations'].append({
                    'source_uid': source_node.get('uid'),
                    'source_id': source_node.get('id', ''),
                    'source_name': source_node.get('name', ''),
                    'relation_type': rel_type,
                    'category': category,
                    'line': 0
                })

            total_rels = len(data['outgoing_relations']) + len(data['incoming_relations'])
            if total_rels > 0:
                logger.debug(f"✅ Label '{label.get('name')}': {len(data['outgoing_relations'])} sortantes, {len(data['incoming_relations'])} entrantes")

            return data

        except Exception as e:
            logger.error(f"❌ Erreur _label_to_data: {e}")
            return {
                'label': label.get('name', 'Unknown'),
                'id': label.get('id', ''),
                'uid': label.get('uid', ''),
                'description': '',
                'category': [],
                'files': [],
                'file_contents': {},
                'parents': [],
                'children': [],
                'outgoing_relations': [],
                'incoming_relations': []
            }

    def _fill_hierarchy(self, data, label_node):
        """✅ Remplit récursivement les enfants"""
        children_key = 'children' if 'children' in label_node else 'parents'
        children = label_node.get(children_key, [])

        for child in children:
            child_data = self._label_to_data(child)
            child_data['parents'] = [data['uid']]
            data['children'].append(child_data)
            self._fill_hierarchy(child_data, child)

    def _map_uids_recursive(self, node):
        """✅ Mappe récursivement les UIDs"""
        dgraph_uid = node.get('uid')
        local_uid = node.get('id') or dgraph_uid

        if dgraph_uid and dgraph_uid.startswith('0x'):
            self.dgraph_to_local[dgraph_uid] = local_uid
            self.local_to_dgraph[local_uid] = dgraph_uid

        for child in node.get('children', []):
            self._map_uids_recursive(child)

    def _transform_profile_to_dgraph_mutations(self, profile_data):
        """
        ✅ CORRIGÉ : Génère mutations avec relations enrichies
        """
        if not profile_data:
            logger.error("❌ profile_data est None")
            return []

        mutations = []
        label_uids = {}  # Mapping local_uid -> dgraph_uid
        seen_uids = set()
        seen_relations = set()

        def add_mutation(mutation):
            """Ajoute une mutation si son UID n'existe pas déjà"""
            mutation_uid = mutation.get("uid")

            if not self._validate_uid_format(mutation_uid):
                logger.error(f"❌ UID INVALIDE détecté: {mutation_uid}")
                return False

            if mutation_uid and mutation_uid not in seen_uids:
                mutations.append(mutation)
                seen_uids.add(mutation_uid)
                return True
            return False

        # 1️⃣ Workspace
        workspace_uid = self._sanitize_uid("", "workspace")

        workspace = {
            "uid": workspace_uid,
            "dgraph.type": "Workspace",
            "name": profile_data.get("name", ""),
            "id": profile_data.get("name", str(uuid.uuid4())),
            "ownerId": "user1",
            "description": profile_data.get("description", ""),
            "updatedAt": datetime.now().isoformat() + "Z",
            "files": profile_data.get("files", []),
            "fileContents": json.dumps(profile_data.get("file_contents", {})),
        }

        # ClusterManagement
        cm_uid = self._sanitize_uid("", "cm")
        workspace["clusterManagement"] = {"uid": cm_uid}

        add_mutation(workspace)

        # 2️⃣ ClusterManagement
        cluster_management = {
            "uid": cm_uid,
            "dgraph.type": "ClusterManagement",
            "version": profile_data.get("version", "1.0"),
            "lastUpdated": datetime.now().isoformat() + "Z",
        }
        add_mutation(cluster_management)

        # 3️⃣ Clusters ET Labels
        clusters_refs = []

        for cluster_data in profile_data.get("turing_ontology", {}).get("clusters_detailed", []):
            cluster_uid = self._sanitize_uid("", "cluster")

            cluster = {
                "uid": cluster_uid,
                "dgraph.type": "Cluster",
                "name": cluster_data.get("name", ""),
                "id": cluster_data.get("name", str(uuid.uuid4())),
                "userId": "user1",
                "nodeType": "cluster",
                "description": cluster_data.get("description", ""),
                "codeContent": "",
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z",
                "files": cluster_data.get("files", []),
                "fileContents": json.dumps(cluster_data.get("file_contents", {})),
            }
            add_mutation(cluster)
            clusters_refs.append({"uid": cluster_uid})

            # Traiter les root labels
            for root_label in cluster_data.get("root_labels", []):
                self._process_label_recursive(
                    root_label,
                    cluster_uid,
                    mutations,
                    label_uids,
                    seen_uids,
                    0,
                    None,
                    ""
                )

        if clusters_refs:
            cluster_management["clusters"] = clusters_refs

        # 4️⃣ ✅ RELATIONS ENRICHIES avec toutes les métadonnées
        logger.info(f"\n🔗 Création des mutations Relation enrichies...")

        all_nodes = self._get_all_nodes(profile_data)
        relations_created = 0
        skipped_invalid_uids = 0

        for node in all_nodes:
            local_uid = node.get('uid')
            source_uid = label_uids.get(local_uid, local_uid)

            if not self._validate_uid_format(source_uid):
                logger.warning(f"⚠️ Source UID invalide ignoré: {source_uid}")
                skipped_invalid_uids += 1
                continue
            
            # ✅ RÉCUPÉRER LES MÉTADONNÉES SOURCE
            source_info = self.label_uid_to_info.get(local_uid, {})
            source_name = source_info.get('name', node.get('label', node.get('name', 'Unknown')))
            source_path = source_info.get('path', node.get('path', ''))
            source_description = source_info.get('description', node.get('description', ''))
            source_type = source_info.get('type', node.get('type', 'unknown'))

            for rel in node.get('outgoing_relations', []):
                target_local_uid = rel.get('target_uid')
                rel_type = rel.get('relation_type', 'relation')

                # Résoudre l'UID cible
                target_uid = label_uids.get(target_local_uid, target_local_uid)

                if not self._validate_uid_format(target_uid):
                    logger.debug(f"⚠️ Target UID non résolu: {target_local_uid}")
                    skipped_invalid_uids += 1
                    continue
                
                # ✅ RÉCUPÉRER LES MÉTADONNÉES TARGET
                target_info = self.label_uid_to_info.get(target_local_uid, {})

                # Priorité 1 : métadonnées dans `rel` (si déjà remplies)
                # Priorité 2 : métadonnées dans `label_uid_to_info`
                # Priorité 3 : fallback sur valeurs par défaut
                target_name = (
                    rel.get('target_name') or 
                    target_info.get('name') or 
                    'Unknown'
                )
                target_path = (
                    rel.get('target_path') or 
                    target_info.get('path') or 
                    target_info.get('file') or 
                    ''
                )
                target_description = (
                    rel.get('target_description') or 
                    target_info.get('description') or 
                    target_info.get('label') or 
                    ''
                )
                target_type = (
                    rel.get('target_type') or 
                    target_info.get('type') or 
                    'unknown'
                )

                # Éviter doublons
                relation_key = f"{source_uid}:{rel_type}:{target_uid}"

                if relation_key not in seen_relations:
                    # ✅ RELATION ENRICHIE COMPLÈTE
                    relation = {
                        "uid": self._sanitize_uid("", "rel"),
                        "dgraph.type": "Relation",
                        "name": f"{rel_type}_relation",
                        "relationType": rel_type,

                        # ✅ Source (référence UID + métadonnées)
                        "source": {"uid": source_uid},
                        "sourceName": source_name,
                        "sourceDescription": source_description,
                        "sourcePath": source_path,
                        "sourceType": source_type,

                        # ✅ Target (référence UID + métadonnées)
                        "target": {"uid": target_uid},
                        "targetName": target_name,
                        "targetDescription": target_description,
                        "targetPath": target_path,
                        "targetType": target_type,

                        # Metadata relation
                        "category": rel.get('category', 'custom'),
                        "line": rel.get('line', 0),
                        "intraFile": rel.get('intra_file', False),

                        "createdAt": datetime.now().isoformat() + "Z",
                    }

                    add_mutation(relation)
                    seen_relations.add(relation_key)
                    relations_created += 1

                    # Log détaillé pour debug
                    if relations_created % 100 == 0:  # Log tous les 100
                        logger.debug(
                            f"  ✅ [{relations_created}] {source_name} "
                            f"--{rel_type}--> "
                            f"{target_name}"
                        )

        # 5️⃣ Pending relations (backup) - aussi enrichies
        pending_rels_created = 0

        for source_local_uid, relations in profile_data.get("pending_relations", {}).items():
            source_uid = label_uids.get(source_local_uid)

            if not source_uid or not self._validate_uid_format(source_uid):
                logger.warning(f"⚠️ Pending relation source invalide: {source_local_uid}")
                continue

            for rel in relations:
                target_local_uid = rel["target_uid"]
                target_uid = label_uids.get(target_local_uid)

                if not target_uid or not self._validate_uid_format(target_uid):
                    logger.debug(f"⚠️ Pending relation target non résolu: {target_local_uid}")
                    continue

                relation_key = f"{source_uid}:{rel['relation_type']}:{target_uid}"

                if relation_key not in seen_relations:
                    relation = {
                        "uid": self._sanitize_uid("", "rel"),
                        "dgraph.type": "Relation",
                        "name": f"{rel['relation_type']}_relation",
                        "relationType": rel["relation_type"],

                        # Source
                        "source": {"uid": source_uid},
                        "sourceName": rel.get('source_name', ''),
                        "sourceDescription": rel.get('source_description', ''),
                        "sourcePath": rel.get('source_path', ''),

                        # Target
                        "target": {"uid": target_uid},
                        "targetName": rel.get("target_name", ""),
                        "targetDescription": rel.get("target_description", ""),
                        "targetPath": rel.get("target_path", ""),

                        "createdAt": datetime.now().isoformat() + "Z",
                    }

                    add_mutation(relation)
                    seen_relations.add(relation_key)
                    pending_rels_created += 1

        # ✅ LOGS AMÉLIORÉS
        logger.info(f"✅ {len(mutations)} mutations générées")
        logger.info(f"📊 {len(label_uids)} labels mappés")
        logger.info(f"🔗 {relations_created} relations enrichies depuis outgoing_relations")
        logger.info(f"🔗 {pending_rels_created} relations enrichies depuis pending_relations")
        logger.info(f"🔗 {len(seen_relations)} relations uniques totales")

        if skipped_invalid_uids > 0:
            logger.warning(f"⚠️ {skipped_invalid_uids} UIDs invalides ignorés")

        return mutations
    
    def _process_label_recursive(self, label_data, cluster_uid, mutations, 
                         label_uids, seen_uids, level=0, parent_uid=None, parent_path=""):
        """
        ✅ AMÉLIORÉ : Collecte aussi les UIDs des éléments de code
        """
        if not label_data:
            logger.warning("⚠️ label_data vide")
            return

        label_name = label_data.get('label') or label_data.get('name', f"Label_level_{level}")
        current_path = f"{parent_path}/{label_name}" if parent_path else label_name
        label_data['path'] = current_path

        logger.debug(f"{'  ' * level}📄 Traitement: {label_name} (path={current_path})")

        # 1️⃣ Créer la mutation du label
        try:
            label_mutation = self._create_label_mutation(
                label_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
        except Exception as e:
            logger.error(f"❌ Erreur création mutation pour '{label_name}': {e}")
            return

        label_uid = label_mutation["uid"]

        if label_uid in seen_uids:
            logger.debug(f"{'  ' * level}⏭️  Label '{label_name}' déjà traité")
            return

        seen_uids.add(label_uid)
        mutations.append(label_mutation)

        # Enregistrer le mapping
        local_uid = label_data.get('uid') or label_data.get('id')
        if local_uid:
            label_uids[local_uid] = label_uid
            logger.debug(f"{'  ' * level}🔗 Mapping: {local_uid} → {label_uid}")

        # 2️⃣ Lier au parent
        if parent_uid:
            if "parents" not in label_mutation:
                label_mutation["parents"] = []
            label_mutation["parents"].append({"uid": parent_uid})
            label_mutation["parentId"] = parent_uid

        # 3️⃣ ✅ NOUVEAU : Enregistrer UIDs des éléments de code
        classes = label_data.get('classes', [])
        functions = label_data.get('functions', [])
        variables = label_data.get('variables', [])

        if classes or functions or variables:
            logger.debug(f"{'  ' * level}📦 Code: {len(classes)} classes, {len(functions)} fonctions, {len(variables)} variables")
            
            # ✅ Enregistrer les mappings AVANT process_code_elements
            for cls in classes:
                cls_uid = cls.get('uid')
                if cls_uid:
                    sanitized = self._sanitize_uid(cls_uid, 'class')
                    label_uids[cls_uid] = sanitized
                    cls['uid'] = sanitized
            
            for func in functions:
                func_uid = func.get('uid')
                if func_uid:
                    sanitized = self._sanitize_uid(func_uid, 'func')
                    label_uids[func_uid] = sanitized
                    func['uid'] = sanitized
            
            for var in variables:
                var_uid = var.get('uid')
                if var_uid:
                    sanitized = self._sanitize_uid(var_uid, 'var')
                    label_uids[var_uid] = sanitized
                    var['uid'] = sanitized
            
            try:
                self._process_code_elements(
                    label_data, 
                    label_uid, 
                    mutations, 
                    label_uids, 
                    seen_uids
                )
            except Exception as e:
                logger.error(f"❌ Erreur traitement code elements: {e}")

        # 4️⃣ Traiter récursivement les enfants
        children = label_data.get('children', [])

        if children:
            logger.debug(f"{'  ' * level}👶 {len(children)} enfant(s)")

            for idx, child in enumerate(children):
                try:
                    self._process_label_recursive(
                        child,
                        cluster_uid,
                        mutations,
                        label_uids,
                        seen_uids,
                        level + 1,
                        label_uid,
                        current_path
                    )
                except Exception as e:
                    child_name = child.get('label') or child.get('name', f'child_{idx}')
                    logger.error(f"❌ Erreur traitement enfant '{child_name}': {e}")
                    continue
                
        logger.debug(f"{'  ' * level}✅ Terminé: {label_name}")

    def verify_relations_in_dgraph(self, project_name: str):
        """
        ✅ AMÉLIORÉ : Vérifie relations avec métadonnées
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("❌ Dgraph client non disponible")
            return False

        escaped_name = project_name.replace('"', '\\"')

        query = f"""
        {{
          workspace(func: type(Workspace)) @filter(eq(name, "{escaped_name}")) {{
            uid
            name

            clusterManagement {{
              clusters {{
                name
                root_labels: ~clusters @filter(eq(level, 0)) {{
                  uid
                  name

                  # ✅ Relations sortantes ENRICHIES
                  outgoing: ~source @filter(type(Relation)) {{
                    uid
                    relationType
                    category
                    line

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

                    # Références
                    target {{
                      uid
                      name
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            data = self.dgraph_connector._parse_response(resp)
            txn.discard()

            stats = {
                'total_labels': 0,
                'labels_with_relations': 0,
                'total_relations': 0,
                'relations_with_metadata': 0,
                'relations_by_type': defaultdict(int),
                'relations_by_category': defaultdict(int)
            }

            for ws in data.get('workspace', []):
                cm = ws.get('clusterManagement', {})
                for cluster in cm.get('clusters', []):
                    for label in cluster.get('root_labels', []):
                        stats['total_labels'] += 1

                        outgoing = label.get('outgoing', [])

                        if outgoing:
                            stats['labels_with_relations'] += 1
                            stats['total_relations'] += len(outgoing)

                            for rel in outgoing:
                                rel_type = rel.get('relationType', 'unknown')
                                category = rel.get('category', 'unknown')

                                stats['relations_by_type'][rel_type] += 1
                                stats['relations_by_category'][category] += 1

                                # Vérifier présence métadonnées
                                if (rel.get('sourceName') and rel.get('targetName')):
                                    stats['relations_with_metadata'] += 1

                                # Log détaillé
                                logger.debug(
                                    f"  📊 {rel.get('sourceName', '?')} "
                                    f"[{rel.get('sourcePath', '?')}] "
                                    f"--{rel_type}--> "
                                    f"{rel.get('targetName', '?')} "
                                    f"[{rel.get('targetPath', '?')}]"
                                )

            logger.info(f"\n📊 VÉRIFICATION DGRAPH:")
            logger.info(f"  • Total labels: {stats['total_labels']}")
            logger.info(f"  • Labels avec relations: {stats['labels_with_relations']}")
            logger.info(f"  • Total relations: {stats['total_relations']}")
            logger.info(f"  • Relations avec métadonnées: {stats['relations_with_metadata']}")

            logger.info(f"\n📋 PAR CATÉGORIE:")
            for cat, count in stats['relations_by_category'].items():
                logger.info(f"  • {cat}: {count}")

            logger.info(f"\n📋 PAR TYPE:")
            for rel_type, count in sorted(stats['relations_by_type'].items(), key=lambda x: -x[1])[:10]:
                logger.info(f"  • {rel_type}: {count}")

            # ✅ AVERTISSEMENT si métadonnées manquantes
            missing_metadata = stats['total_relations'] - stats['relations_with_metadata']
            if missing_metadata > 0:
                logger.warning(f"\n⚠️ {missing_metadata} relations sans métadonnées complètes!")

            return stats

        except Exception as e:
            logger.error(f"❌ Erreur vérification: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_code_elements(self, node_data, parent_uid, mutations, label_uids, seen_uids):
        """
        ✅ CORRECTION COMPLÈTE : Crée les mutations AVEC TOUTES LES DONNÉES
        """

        def get_valid_uid(raw_uid, prefix):
            """Retourne un UID valide : conserve 0x..., sinon génère un blank node."""
            if raw_uid and isinstance(raw_uid, str) and raw_uid.startswith("0x"):
                return raw_uid
            return self._sanitize_uid(raw_uid or "", prefix)

        # ✅ CLASSES AVEC DONNÉES COMPLÈTES
        for cls in node_data.get('classes', []):
            cls_uid = get_valid_uid(cls.get('uid', ''), 'class')

            if cls_uid not in seen_uids:
                # ✅ CRÉER LA MUTATION COMPLÈTE
                cls_mutation = {
                    "uid": cls_uid,
                    "dgraph.type": "Class",
                    "name": cls.get("name", "UnnamedClass"),
                    "description": cls.get("description", ""),
                    "line": cls.get("line", 0),
                    "bases": cls.get("bases", []),
                    "uses_vars": cls.get("uses_vars", [])
                }

                # ✅ AJOUTER LES MÉTHODES COMME RÉFÉRENCES COMPLÈTES
                methods_refs = []
                for method in cls.get('methods', []):
                    method_uid = get_valid_uid(method.get('uid', ''), 'method')

                    if method_uid not in seen_uids:
                        # Créer mutation de la méthode
                        method_mutation = {
                            "uid": method_uid,
                            "dgraph.type": "Function",
                            "name": method.get("name", "UnnamedMethod"),
                            "description": method.get("description", ""),
                            "line": method.get("line", 0),
                            "params": json.dumps(method.get("params", [])),
                            "returns": json.dumps(method.get("returns", {}))
                        }
                        mutations.append(method_mutation)
                        seen_uids.add(method_uid)

                        if method.get('uid'):
                            label_uids[method['uid']] = method_uid

                    methods_refs.append({"uid": method_uid})

                if methods_refs:
                    cls_mutation["methods"] = methods_refs

                # ✅ AJOUTER LES VARIABLES DE LA CLASSE
                vars_refs = []
                for var in cls.get('variables', []):
                    var_uid = get_valid_uid(var.get('uid', ''), 'var')

                    if var_uid not in seen_uids:
                        var_mutation = {
                            "uid": var_uid,
                            "dgraph.type": "Variable",
                            "name": var.get("name", "UnnamedVar"),
                            "description": var.get("description", ""),
                            "line": var.get("line", 0),
                            "var_type": var.get("type", "unknown"),
                            "scope": var.get("scope", "local")
                        }
                        mutations.append(var_mutation)
                        seen_uids.add(var_uid)

                        if var.get('uid'):
                            label_uids[var['uid']] = var_uid

                    vars_refs.append({"uid": var_uid})

                if vars_refs:
                    cls_mutation["variables"] = vars_refs

                # ✅ AJOUTER LA MUTATION DE LA CLASSE
                mutations.append(cls_mutation)
                seen_uids.add(cls_uid)

                if cls.get('uid'):
                    label_uids[cls['uid']] = cls_uid

        # ✅ FONCTIONS GLOBALES AVEC DONNÉES COMPLÈTES
        for func in node_data.get('functions', []):
            func_uid = get_valid_uid(func.get('uid', ''), 'func')

            if func_uid not in seen_uids:
                func_mutation = {
                    "uid": func_uid,
                    "dgraph.type": "Function",
                    "name": func.get("name", "UnnamedFunction"),
                    "description": func.get("description", ""),
                    "line": func.get("line", 0),
                    "params": json.dumps(func.get("params", [])),
                    "returns": json.dumps(func.get("returns", {}))
                }

                # ✅ AJOUTER LES APPELS (CALLS)
                calls_refs = []
                for call in func.get('calls', []):
                    # Si call est un dict avec uid
                    if isinstance(call, dict):
                        call_uid = call.get('uid')
                    else:
                        # Si call est juste un nom, essayer de résoudre
                        call_uid = self.name_to_uid.get(str(call))

                    if call_uid:
                        calls_refs.append({"uid": call_uid})

                if calls_refs:
                    func_mutation["calls"] = calls_refs

                # ✅ VARIABLES DE LA FONCTION
                vars_refs = []
                for var in func.get('variables', []):
                    var_uid = get_valid_uid(var.get('uid', ''), 'var')

                    if var_uid not in seen_uids:
                        var_mutation = {
                            "uid": var_uid,
                            "dgraph.type": "Variable",
                            "name": var.get("name", "UnnamedVar"),
                            "description": var.get("description", ""),
                            "line": var.get("line", 0),
                            "var_type": var.get("type", "unknown"),
                            "scope": "local"
                        }
                        mutations.append(var_mutation)
                        seen_uids.add(var_uid)

                        if var.get('uid'):
                            label_uids[var['uid']] = var_uid

                    vars_refs.append({"uid": var_uid})

                if vars_refs:
                    func_mutation["variables"] = vars_refs

                mutations.append(func_mutation)
                seen_uids.add(func_uid)

                if func.get('uid'):
                    label_uids[func['uid']] = func_uid

        # ✅ VARIABLES GLOBALES
        for var in node_data.get('variables', []):
            var_uid = get_valid_uid(var.get('uid', ''), 'var')

            if var_uid not in seen_uids:
                var_mutation = {
                    "uid": var_uid,
                    "dgraph.type": "Variable",
                    "name": var.get("name", "UnnamedVar"),
                    "description": var.get("description", ""),
                    "line": var.get("line", 0),
                    "var_type": var.get("type", "unknown"),
                    "scope": var.get("scope", "global")
                }

                mutations.append(var_mutation)
                seen_uids.add(var_uid)

                if var.get('uid'):
                    label_uids[var['uid']] = var_uid


    def _create_label_mutation(self, label_data, level, cluster_uid):
        """
        ✅ CORRIGÉ : Génère blank node valide
        """
        # ✅ TOUJOURS générer nouveau blank node
        uid = self._sanitize_uid("", prefix='label')
        
        # Stocker l'UID Dgraph dans label_data pour référence
        label_data['dgraph_uid'] = uid

        path = label_data.get('path', '')
        if not path:
            files = label_data.get('files', [])
            if files:
                path = files[0]
            else:
                path = label_data.get('label', label_data.get('name', ''))

        mutation = {
            "uid": uid,  # ✅ Format _:label_xxxxx
            "dgraph.type": "Label",
            "name": label_data.get('label', label_data.get('name', '')),
            "id": label_data.get('id', str(uuid.uuid4())),
            "level": level,
            "path": path,
            "category": label_data.get('category', []),
            "nodeType": label_data.get('type', 'label'),
            "description": label_data.get('description', ''),
            "codeContent": "",
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z",
            "files": label_data.get('files', []),
            "fileContents": json.dumps(label_data.get('file_contents', {})),
            "clusters": [{"uid": cluster_uid}]
        }

        classes_refs = []
        for cls in label_data.get('classes', []):
            # Utiliser l'UID Dgraph généré précédemment
            cls_uid = cls.get('dgraph_uid', self._sanitize_uid("", 'class'))
            classes_refs.append({"uid": cls_uid})

        if classes_refs:
            mutation["classes"] = classes_refs

        functions_refs = []
        for func in label_data.get('functions', []):
            func_uid = func.get('dgraph_uid', self._sanitize_uid("", 'func'))
            functions_refs.append({"uid": func_uid})

        if functions_refs:
            mutation["functions"] = functions_refs

        variables_refs = []
        for var in label_data.get('variables', []):
            var_uid = var.get('dgraph_uid', self._sanitize_uid("", 'var'))
            variables_refs.append({"uid": var_uid})

        if variables_refs:
            mutation["variables"] = variables_refs

        return mutation
    
    def _remove_duplicate_clusters_before_insert(self, profile_data):
        """
        ✅ NOUVEAU : Nettoie les doublons de clusters AVANT l'insertion Dgraph
        """
        clusters = profile_data.get('turing_ontology', {}).get('clusters_detailed', [])

        # Grouper par nom
        from collections import defaultdict
        clusters_by_name = defaultdict(list)

        for cluster in clusters:
            cluster_name = cluster.get('name', '')
            if cluster_name:
                clusters_by_name[cluster_name].append(cluster)

        # Fusionner doublons
        cleaned_clusters = []

        for cluster_name, duplicates in clusters_by_name.items():
            if len(duplicates) == 1:
                cleaned_clusters.append(duplicates[0])
                continue
            
            logger.info(f"🔄 Fusion de {len(duplicates)} clusters '{cluster_name}'...")

            # Garder le 1er, fusionner les autres
            merged = duplicates[0]

            for dup in duplicates[1:]:
                # Fusionner root_labels (sans doublons)
                existing_labels = {label['label'] for label in merged['root_labels']}

                for label in dup['root_labels']:
                    if label['label'] not in existing_labels:
                        merged['root_labels'].append(label)
                        existing_labels.add(label['label'])

                # Fusionner files
                for file in dup.get('files', []):
                    if file not in merged['files']:
                        merged['files'].append(file)

                # Fusionner file_contents
                merged['file_contents'].update(dup.get('file_contents', {}))

            cleaned_clusters.append(merged)
            logger.info(f"✅ Cluster '{cluster_name}' : {len(merged['root_labels'])} labels")

        # Remplacer
        profile_data['turing_ontology']['clusters_detailed'] = cleaned_clusters
        logger.info(f"✅ Nettoyage terminé : {len(cleaned_clusters)} clusters uniques")
    
    def _build_full_path(self, label_data, level):
        # Méthode 1 : Si files existe, utiliser le premier fichier comme path
        files = label_data.get('files', [])
        if files and files[0]:
            return files[0]

        # Méthode 2 : Si path est déjà défini (par _scan_directory_recursive)
        if label_data.get('path'):
            return label_data['path']

        # Méthode 3 : Construire depuis label_uid_to_info
        uid = label_data.get('uid')
        if uid and uid in self.label_uid_to_info:
            info = self.label_uid_to_info[uid]
            file_path = info.get('file', '')
            if file_path:
                return file_path

        # Méthode 4 : Construire depuis le nom du label
        label_name = label_data.get('label', label_data.get('name', ''))

        # Si c'est un fichier (détecté par extension), retourner le nom
        if label_name.endswith(('.py', '.ts', '.js', '.json', '.java', '.cpp', '.c', '.h')):
            return label_name

        # Sinon retourner vide (sera rempli par les enfants)
        return ''
    
    def _build_path_from_hierarchy(self, label_data, current_path_parts=None):
        """
        ✅ ALTERNATIVE : Construction récursive sécurisée du path

        Args:
            label_data: Données du label
            current_path_parts: Liste des parties du chemin (pour récursion)

        Returns:
            Chemin complet
        """
        if current_path_parts is None:
            current_path_parts = []

        # Ajouter le nom actuel
        label_name = label_data.get('label', label_data.get('name', ''))
        if label_name:
            current_path_parts.append(label_name)

        # Chercher le parent
        parent_ids = label_data.get('parents', [])
        if not parent_ids:
            # Pas de parent, on a atteint la racine
            return '/'.join(reversed(current_path_parts))

        # Récupérer le premier parent
        parent_uid = parent_ids[0] if isinstance(parent_ids, list) else parent_ids

        # Chercher le parent dans label_uid_to_info
        if parent_uid in self.label_uid_to_info:
            parent_info = self.label_uid_to_info[parent_uid]
            parent_name = parent_info.get('name', '')
            if parent_name:
                current_path_parts.append(parent_name)

        return '/'.join(reversed(current_path_parts))
    

    def _find_label_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        if not uid:
            return None

        # Chercher dans label_uid_to_info d'abord (plus rapide)
        if uid in self.label_uid_to_info:
            # Récupérer les infos basiques
            info = self.label_uid_to_info[uid]
            return {
                'uid': uid,
                'name': info.get('name', ''),
                'label': info.get('label', info.get('name', '')),
                'type': info.get('type', 'label')
            }

        # Sinon chercher dans toute la structure
        all_nodes = self._get_all_nodes(self.current_project_profile_data)
        return next((n for n in all_nodes if n.get('uid') == uid), None)
    
    def _clean_empty_clusters_in_dgraph(self):
        """
        ✅ NOUVEAU : Supprime les clusters vides (0 root_labels) de Dgraph
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("❌ Dgraph client non disponible")
            return False

        try:
            # 1️⃣ Identifier les clusters vides
            query = """
            {
              empty_clusters(func: type(Cluster)) {
                uid
                name
                root_labels_count: count(~clusters) @filter(eq(level, 0))
              }
            }
            """

            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            data = self.dgraph_connector._parse_response(resp)
            txn.discard()

            clusters = data.get('empty_clusters', [])
            empty_uids = []

            for cluster in clusters:
                root_count = cluster.get('root_labels_count', 0)
                if root_count == 0:
                    empty_uids.append(cluster['uid'])
                    logger.info(f"🗑️ Cluster vide trouvé : {cluster.get('name')} (UID: {cluster['uid']})")

            if not empty_uids:
                logger.info("✅ Aucun cluster vide à supprimer")
                return True

            # 2️⃣ Supprimer
            logger.info(f"🗑️ Suppression de {len(empty_uids)} cluster(s) vide(s)...")

            txn = self.dgraph_connector.client.txn()
            try:
                del_objs = [{"uid": uid} for uid in empty_uids]
                txn.mutate(del_obj=del_objs)
                txn.commit()
                logger.info(f"✅ {len(empty_uids)} cluster(s) vide(s) supprimé(s)")
                return True
            except Exception as e:
                logger.error(f"❌ Erreur suppression : {e}")
                txn.discard()
                return False

        except Exception as e:
            logger.error(f"❌ Erreur : {e}")
            return False
    
    def _create_class_mutation(self, class_data, parent_uid):
        """✅ CORRECTION : Mutation Class complète"""
        uid = self._sanitize_uid(class_data.get('uid', ''), 'class')

        name = class_data.get('name', '')
        if not name:
            name = class_data.get('label', f"Class_{uid[:8]}")
            class_data['name'] = name

        mutation = {
            "uid": uid,
            "dgraph.type": "Class",
            "name": name,
            "description": class_data.get('description', ''),
            "line": class_data.get('line', 0),
            "bases": class_data.get('bases', []),
            "uses_vars": class_data.get('uses_vars', [])
        }

        # ✅ AJOUTER MÉTHODES COMME MUTATIONS COMPLÈTES (pas juste UIDs)
        methods_mutations = []
        for method in class_data.get('methods', []):
            method_uid = self._sanitize_uid(method.get('uid', ''), 'method')
            method['uid'] = method_uid

            if 'name' not in method or not method['name']:
                method['name'] = method.get('label', f"Method_{method_uid[:8]}")

            # Créer mutation complète pour la méthode
            method_mutation = {
                "uid": method_uid,
                "dgraph.type": "Function",
                "name": method['name'],
                "description": method.get('description', ''),
                "line": method.get('line', 0),
                "params": json.dumps(method.get('params', [])),
                "returns": json.dumps(method.get('returns', {}))
            }
            methods_mutations.append(method_mutation)

        return mutation, methods_mutations 

    def _create_function_mutation(self, func_data, parent_uid):
        """✅ CORRECTION : Mutation Function complète avec calls"""
        uid = self._sanitize_uid(func_data.get('uid', ''), 'func')

        name = func_data.get('name', '')
        if not name:
            name = func_data.get('label', f"Function_{uid[:8]}")
            func_data['name'] = name

        mutation = {
            "uid": uid,
            "dgraph.type": "Function",
            "name": name,
            "description": func_data.get('description', ''),
            "line": func_data.get('line', 0),
            "params": json.dumps(func_data.get('params', [])),
            "returns": json.dumps(func_data.get('returns', {}))
        }

        # ✅ AJOUTER LES CALLS COMME RÉFÉRENCES UID
        calls_refs = []
        for call_name in func_data.get('calls', []):
            call_uid = self._find_uid_by_name(call_name, {})
            if call_uid:
                calls_refs.append({"uid": call_uid})

        if calls_refs:
            mutation["calls"] = calls_refs

        return mutation

    def _create_variable_mutation(self, var_data, parent_uid):
        """✅ CORRECTION : Mutation Variable complète"""
        uid = self._sanitize_uid(var_data.get('uid', ''), 'var')
    
        mutation = {
            "uid": uid,
            "dgraph.type": "Variable",
            "name": var_data.get('name', 'UnnamedVar'),
            "description": var_data.get('description', ''),
            "line": var_data.get('line', 0),
            "var_type": var_data.get('type', 'unknown'),
            "scope": var_data.get('scope', 'local')
        }
    
        return mutation

    def _batch_save_to_dgraph(self, profile_data, initial_batch_size=50, max_retries=5):
        """
        ✅ CORRIGÉ : Avec nettoyage des doublons AVANT insertion
        """
        if not self.dgraph_connector.client:
            logger.error("❌ Dgraph client non disponible")
            return False

        if not profile_data:
            logger.error("❌ profile_data est None")
            return False

        # ✅ NETTOYAGE PRÉVENTIF
        self._remove_duplicate_clusters_before_insert(profile_data)

        # Générer mutations
        mutations = self._transform_profile_to_dgraph_mutations(profile_data)
        if not mutations:
            logger.error("❌ Aucune mutation générée")
            return False

        logger.info(f"📤 Démarrage batch save: {len(mutations)} mutations (batch: {initial_batch_size})")

        # ✅ Utiliser batch_size optimisé avec retry
        success = self.dgraph_connector.insert_mutations(
            mutations, 
            initial_batch_size=initial_batch_size,
            max_retries=max_retries
        )

        if success:
            logger.info("✅ Batch save Dgraph réussi")
        else:
            logger.error("❌ Échec batch save Dgraph")

        return success

    def _find_uid_by_name(self, name, label_uids):
        """✅ Résout UID par nom"""
        if not name:
            return None
        
        for uid, info in self.label_uid_to_info.items():
            if info.get('name', '').lower() == name.lower():
                return label_uids.get(uid, self._sanitize_uid(uid, 'resolved'))
        
        return None

    def _get_relation_category(self, rel_type: str) -> str:
        """✅ Détermine catégorie relation"""
        rel_type_lower = rel_type.lower()

        parsed_types = {
            'import', 'from_import', 'require', 'include',
            'extends', 'implements', 'inherits',
            'calls', 'function_call', 'method_call',
            'uses', 'variable_use', 'references'
        }

        if rel_type_lower in parsed_types:
            return 'parsed'

        if rel_type_lower in {'child', 'parent'}:
            return 'hierarchy'

        return 'custom'

    def _get_all_nodes(self, profile_data=None):
        """✅ Récupère tous les nœuds"""
        if not profile_data:
            return []

        all_nodes = []
        
        def collect_nodes(node_list):
            for node in node_list:
                all_nodes.append(node)
                collect_nodes(node.get('children', []))

        for cluster in profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            collect_nodes(cluster.get('root_labels', []))

        return all_nodes

    def _on_insert_dgraph(self, parent=None):
        """
        ✅ AMÉLIORÉ : Avec vérification post-insertion
        """
        if not self.is_configured():
            from PyQt5 import QtWidgets
            QtWidgets.QMessageBox.warning(
                parent, "Erreur", "Configuration Dgraph incomplète."
            )
            return

        if not hasattr(self, 'current_project_profile_data') or not self.current_project_profile_data:
            from PyQt5 import QtWidgets
            QtWidgets.QMessageBox.warning(
                parent, "Erreur", "Aucun profil de projet chargé."
            )
            logger.error("❌ current_project_profile_data non défini")
            return

        project_name = self.current_project_profile_data.get('name', 'Projet inconnu')
        logger.info(f"📄 Insertion Dgraph pour '{project_name}'")

        # Sauvegarder SQLite si disponible
        if hasattr(self, 'project_storage_manager'):
            logger.info("💾 Sauvegarde SQLite...")
            if not self.project_storage_manager._save_project_to_sqlite(self.current_project_profile_data):
                from PyQt5 import QtWidgets
                QtWidgets.QMessageBox.critical(
                    parent, "Erreur", "Échec sauvegarde SQLite."
                )
                return
            logger.info("✅ SQLite OK")

        logger.info("📤 Génération mutations...")
        mutations = self._transform_profile_to_dgraph_mutations(
            self.current_project_profile_data
        )

        if not mutations:
            from PyQt5 import QtWidgets
            QtWidgets.QMessageBox.warning(
                parent, "Avertissement", "Aucune mutation générée."
            )
            return

        logger.info(f"📊 {len(mutations)} mutations")

        logger.info("📄 Insertion Dgraph...")
        if not self.dgraph_connector.insert_mutations(mutations):
            from PyQt5 import QtWidgets
            QtWidgets.QMessageBox.warning(
                parent, "Avertissement", "Échec insertion Dgraph."
            )
            return

        logger.info("✅ Dgraph OK")
        
        # ✅ NOUVEAU : Vérification post-insertion
        logger.info("\n🔍 Vérification des relations dans Dgraph...")
        self.verify_relations_in_dgraph(project_name)
        
        self._retrieve_assigned_uids(project_name)

        logger.info("="*80)
        logger.info(f"✅ INSERTION COMPLÈTE: '{project_name}'")
        logger.info("="*80)

        from PyQt5 import QtWidgets
        QtWidgets.QMessageBox.information(
            parent, "Succès", 
            f"✅ Projet '{project_name}' inséré!\n\n"
            f"📊 {len(mutations)} mutations insérées\n"
            f"🔗 Relations vérifiées avec succès"
        )

        self.dgraph_connector.open_ratel()

    def _retrieve_assigned_uids(self, project_name):
        """✅ Récupère les UIDs assignés par Dgraph SANS @recurse"""
        escaped_name = project_name.replace('"', '\\"')

        query = f"""
        {{
          workspaces(func: type(Workspace)) @filter(eq(name, "{escaped_name}")) {{
            uid
            id
            name
            clusterManagement {{
              uid
              clusters {{
                uid
                id
                name

                # Labels racines (niveau 0)
                root_labels: ~clusters @filter(eq(level, 0)) {{
                  uid
                  id
                  name

                  # Classes du root label
                  classes {{
                    uid
                    id
                    name
                    methods {{
                      uid
                      id
                      name
                    }}
                  }}

                  # Fonctions du root label
                  functions {{
                    uid
                    id
                    name
                  }}

                  # Variables du root label
                  variables {{
                    uid
                    id
                    name
                  }}

                  # Enfants niveau 1
                  children: ~parents @filter(eq(level, 1)) {{
                    uid
                    id
                    name

                    # Classes niveau 1
                    classes {{
                      uid
                      id
                      name
                    }}

                    # Fonctions niveau 1
                    functions {{
                      uid
                      id
                      name
                    }}

                    # Variables niveau 1
                    variables {{
                      uid
                      id
                      name
                    }}

                    # Enfants niveau 2
                    children: ~parents @filter(eq(level, 2)) {{
                      uid
                      id
                      name

                      # Classes niveau 2
                      classes {{
                        uid
                        id
                        name
                      }}

                      # Fonctions niveau 2
                      functions {{
                        uid
                        id
                        name
                      }}

                      # Variables niveau 2
                      variables {{
                        uid
                        id
                        name
                      }}

                      # Enfants niveau 3 (si nécessaire)
                      children: ~parents @filter(eq(level, 3)) {{
                        uid
                        id
                        name
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
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            data = self.dgraph_connector._parse_response(resp)
            txn.discard()

            assigned_uids = {}

            def collect_uids(node):
                """Collecte récursivement les UIDs avec logging détaillé"""
                local_id = node.get('id')
                dgraph_uid = node.get('uid')

                if local_id and dgraph_uid:
                    self.local_to_dgraph[local_id] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = local_id
                    assigned_uids[local_id] = dgraph_uid
                    logger.debug(f"  ✅ Mappé: {local_id} -> {dgraph_uid}")

                # Collecter classes
                for cls in node.get('classes', []):
                    collect_uids(cls)
                    # Collecter méthodes
                    for method in cls.get('methods', []):
                        collect_uids(method)

                # Collecter fonctions
                for func in node.get('functions', []):
                    collect_uids(func)

                # Collecter variables
                for var in node.get('variables', []):
                    collect_uids(var)

                # Collecter enfants hiérarchiques
                for child in node.get('children', []):
                    collect_uids(child)

            # Parcourir la structure
            for ws in data.get('workspaces', []):
                logger.info(f"📦 Workspace: {ws.get('name')}")
                collect_uids(ws)

                cm = ws.get('clusterManagement', {})
                if cm:
                    collect_uids(cm)

                    for cluster in cm.get('clusters', []):
                        logger.info(f"  📁 Cluster: {cluster.get('name')}")
                        collect_uids(cluster)

                        for root_label in cluster.get('root_labels', []):
                            logger.info(f"    📄 Root label: {root_label.get('name')}")
                            collect_uids(root_label)

            logger.info(f"✅ {len(assigned_uids)} UIDs récupérés")

            # Sauvegarder le mapping dans un fichier
            import os
            mapping_file = f"data/uid_mapping_{project_name.replace(' ', '_')}.json"
            try:
                os.makedirs('data', exist_ok=True)
                with open(mapping_file, 'w') as f:
                    json.dump({
                        'local_to_dgraph': self.local_to_dgraph,
                        'dgraph_to_local': self.dgraph_to_local
                    }, f, indent=2)
                logger.info(f"💾 Mapping sauvegardé dans {mapping_file}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur sauvegarde mapping: {e}")

            return True

        except Exception as e:
            logger.warning(f"⚠️ Impossible récupérer UIDs: {e}")
            import traceback
            traceback.print_exc()
            return False

    def clean_duplicate_files(self):
        """✅ Supprime les fichiers en double (garde le plus récent)."""

        query = """
        {
          files(func: type(Label)) @filter(has(name)) {
            uid
            name
            createdAt
          }
        }
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            data = self.dgraph_connector._parse_response(resp)
            txn.discard()

            files = data.get('files', [])

            # Grouper par nom
            from collections import defaultdict
            file_groups = defaultdict(list)
            for f in files:
                file_name = f.get('name', '')
                if file_name:
                    file_groups[file_name].append(f)

            # Identifier doublons
            uids_to_delete = []
            for file_name, duplicates in file_groups.items():
                if len(duplicates) > 1:
                    logger.info(f"🔍 Doublon : {file_name} ({len(duplicates)} copies)")

                    # Trier par date (garder le plus récent)
                    duplicates.sort(key=lambda x: x.get('createdAt', ''), reverse=True)

                    # Supprimer les anciens
                    for dup in duplicates[1:]:
                        uids_to_delete.append(dup['uid'])
                        logger.debug(f"  ❌ À supprimer : {dup['uid']}")

            # Supprimer
            if uids_to_delete:
                logger.info(f"🗑️ Suppression de {len(uids_to_delete)} doublons...")

                txn = self.dgraph_connector.client.txn()
                try:
                    del_objs = [{"uid": uid} for uid in uids_to_delete]
                    txn.mutate(del_obj=del_objs)
                    txn.commit()
                    logger.info(f"✅ {len(uids_to_delete)} doublons supprimés")
                    return True
                except Exception as e:
                    logger.error(f"❌ Erreur : {e}")
                    txn.discard()
                    return False
            else:
                logger.info("✅ Aucun doublon")
                return True

        except Exception as e:
            logger.error(f"❌ Erreur : {e}")
            return False

    def _test_relations_loading(self, profile_data=None):
        """
        ✅ AJOUTÉ : Méthode de diagnostic pour vérifier les relations
        """
        if not profile_data:
            if hasattr(self, 'current_project_profile_data'):
                profile_data = self.current_project_profile_data
            else:
                logger.warning("❌ Aucun projet chargé")
                return {}

        logger.info("\n" + "="*80)
        logger.info("🧪 TEST CHARGEMENT RELATIONS")
        logger.info("="*80)

        project_name = profile_data.get('name', 'Unknown')
        logger.info(f"📦 Projet: {project_name}")

        all_nodes = self._get_all_nodes(profile_data)

        stats = {
            'total_nodes': len(all_nodes),
            'nodes_with_outgoing': 0,
            'nodes_with_incoming': 0,
            'total_outgoing_relations': 0,
            'total_incoming_relations': 0,
            'parsed_relations_count': 0,
            'custom_relations_count': 0,
            'unresolved_relations': 0,
            'relations_by_type': defaultdict(int)
        }

        for node in all_nodes:
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                stats['nodes_with_outgoing'] += 1
                stats['total_outgoing_relations'] += len(outgoing)

                for rel in outgoing:
                    rel_type = rel.get('relation_type', 'unknown')
                    rel_category = rel.get('category', 'custom')

                    stats['relations_by_type'][rel_type] += 1

                    if rel_category == 'parsed':
                        stats['parsed_relations_count'] += 1
                    else:
                        stats['custom_relations_count'] += 1

                    target_uid = rel.get('target_uid', '')
                    if target_uid.startswith('temp_') or target_uid.startswith('unresolved_'):
                        stats['unresolved_relations'] += 1

            incoming = node.get('incoming_relations', [])
            if incoming:
                stats['nodes_with_incoming'] += 1
                stats['total_incoming_relations'] += len(incoming)

        logger.info("📈 RÉSULTATS:")
        logger.info(f"  • Total nœuds: {stats['total_nodes']}")
        logger.info(f"  • Nœuds avec relations sortantes: {stats['nodes_with_outgoing']}")
        logger.info(f"  • Nœuds avec relations entrantes: {stats['nodes_with_incoming']}")
        logger.info(f"\n🔗 RELATIONS:")
        logger.info(f"  • Total sortantes: {stats['total_outgoing_relations']}")
        logger.info(f"  • Total entrantes: {stats['total_incoming_relations']}")
        logger.info(f"  • Parsées (code): {stats['parsed_relations_count']}")
        logger.info(f"  • Custom (manuelles): {stats['custom_relations_count']}")
        logger.info(f"  • Non résolues: {stats['unresolved_relations']}")

        if stats['relations_by_type']:
            logger.info(f"\n📋 TYPES DE RELATIONS:")
            for rel_type, count in sorted(stats['relations_by_type'].items(), key=lambda x: -x[1]):
                logger.info(f"  • {rel_type}: {count}")

        logger.info(f"\n💡 RECOMMANDATIONS:")
        if stats['unresolved_relations'] > 0:
            logger.warning(f"  ⚠️ {stats['unresolved_relations']} relations non résolues à traiter")

        if stats['total_outgoing_relations'] == 0:
            logger.warning("  ⚠️ AUCUNE relation trouvée!")
            logger.info("  → Lancer un scan avec _on_browse_project()")

        logger.info("="*80 + "\n")

        return stats