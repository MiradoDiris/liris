
import pydgraph
import json
import logging
import uuid # For generating unique IDs
from datetime import datetime

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dgraph Configuration ---
DGRAPH_ADDR = 'localhost:9080' # Dgraph gRPC server address

USER_ID = "47ea051e-8cce-4bee-bfe8-76489dd98b60"
WORKSPACE_ID = "e8bfa5a1-512d-46e3-a4cc-69aecbb9cad9"

def generate_dgraph_mutations(client, project_data):
    """
    Generates the list of Dgraph mutations from the Liris project ontology data.
    Uses blank node identifiers (_:name) to create nodes and establish relationships.
    Workspace, Cluster, and Label nodes are managed with @upsert via their 'id'.
    """
    mutations = []
    
    turing_ontology = project_data.get("turing_ontology", {})
    # Maintenant, nous utilisons 'clusters_detailed' qui contient la structure hiérarchique
    clusters_detailed_from_project = turing_ontology.get("clusters_detailed", [])

    # Dictionary to map cluster's unique_id (UUID) to its Dgraph blank UID
    # This is needed for linking the ClusterManagement node to specific Cluster UIDs
    cluster_uuid_to_blank_uid_map = {} 
    
    # List to hold the blank UIDs of all clusters, to be linked to ClusterManagement
    all_cluster_blank_uids_for_workspace = []

    # 1. Prepare mutations for Cluster nodes
    for i, cluster_data in enumerate(clusters_detailed_from_project):
        cluster_name = cluster_data["name"]
        cluster_unique_id = cluster_data["id"] # Use the ID already assigned during import
        cluster_blank_uid = f"_:cluster_{cluster_unique_id.replace('-', '_')}"
        
        cluster_uuid_to_blank_uid_map[cluster_unique_id] = cluster_blank_uid

        cluster_mutation = {
            "uid": cluster_blank_uid,
            "dgraph.type": "Cluster",
            "id": str(cluster_unique_id), # Used by @upsert to find/create
            "name": cluster_name,
            "userId": USER_ID, # Corrected to userId
            "createdAt": datetime.now().isoformat() + "Z", # Add creation timestamp
            "updatedAt": datetime.now().isoformat() + "Z", # Add update timestamp
        }
        mutations.append(cluster_mutation)
        
        # MODIFICATION ICI: Stocker l'UUID string au lieu de la référence UID
        all_cluster_blank_uids_for_workspace.append(cluster_unique_id)
        logger.debug(f"Prepared cluster: {cluster_name} (ID: {cluster_unique_id}, Blank UID: {cluster_blank_uid})")

    # 2. Prepare mutations for Workspace and its ClusterManagement
    workspace_unique_id = WORKSPACE_ID # Use the provided WORKSPACE_ID as its unique ID
    workspace_mutation = {
        "uid": f"_:workspace_node", # Blank UID for the Workspace
        "dgraph.type": "Workspace",
        "id": workspace_unique_id, # The unique ID of the Workspace for upsert
        "ownerId": USER_ID, # The user ID of the workspace owner
        "updatedAt": datetime.now().isoformat() + "Z",
        "clusterManagement": {
            "uid": f"_:cluster_management_node", # Blank UID for the ClusterManagement
            "dgraph.type": "ClusterManagement",
            "lastUpdated": datetime.now().isoformat() + "Z",
            "version": "1.0", # Default version
            # MODIFICATION CRITIQUE ICI
            "ClusterManagement.clusters": all_cluster_blank_uids_for_workspace
        }
    }
    mutations.append(workspace_mutation)
    logger.debug(f"Prepared Workspace (ID: {workspace_unique_id}) and its ClusterManagement.")

    # Helper function to process labels recursively
    # It takes:
    #   label_data: The current dictionary from Liris ontology data (e.g., a root_label, parent_label, or child_label)
    #   level_numeric: 0 for root, 1 for parent, 2 for child (for Label.level)
    #   parent_uid_for_relation: Dgraph blank UID of the direct parent (for Label.parents relationship)
    #   current_path_ids: List of UUID strings for building Label.path (IDs of ancestors)
    #   containing_cluster_unique_id: The UUID of the specific cluster this label belongs to
    #   containing_cluster_blank_uid: The blank UID of the specific cluster this label belongs to
    #   all_mutations: The list to append generated mutations to

    def _process_label_hierarchy(label_data, level_numeric, parent_uid_for_relation, current_path_ids, containing_cluster_unique_id, containing_cluster_blank_uid, all_mutations):
        label_name = label_data["name"]
        label_category = label_data.get("category", [])
        
        # Generate a full UUID for the label's unique ID
        label_unique_id = label_data["id"] # Use the ID already assigned during import

        # Dgraph blank UID for this new label node
        label_blank_uid = f"_:label_{label_unique_id.replace('-', '_')}"
        
        # Build the full path for Label.path using unique IDs
        if level_numeric == 0: # Root label
            full_path = "/"
        else:
            full_path = "/".join(current_path_ids) + "/"

        label_node = {
            "uid": label_blank_uid,
            "dgraph.type": "Label",
            "id": label_unique_id, # Used by @upsert
            "name": label_name,
            "level": str(level_numeric), # Store as string "0", "1", "2"
            "path": full_path,
            "category": label_category,
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z"
            # Removed "type": label_type as requested
        }

        # Link to parent if exists using 'parents' predicate and set 'parentId' string
        if parent_uid_for_relation:
            label_node["parents"] = [{"uid": parent_uid_for_relation}]
            # parentId refers to the 'id' string of the parent
            # The last element in current_path_ids is the immediate parent's ID
            if current_path_ids:
                label_node["parentId"] = current_path_ids[-1] 
            else:
                label_node["parentId"] = "" # Should not happen for non-root labels with parent_uid

        # Link this label ONLY to its containing cluster
        if containing_cluster_unique_id and containing_cluster_blank_uid:
            # MODIFICATION CRITIQUE ICI
            label_node["Label.clusters"] = [{"uid": containing_cluster_blank_uid}]
            label_node["clusterIds"] = [containing_cluster_unique_id]
            logger.debug(f"  Linked label '{label_name}' (level {level_numeric}) to its containing cluster (ID: {containing_cluster_unique_id}).")
        else:
            logger.warning(f"  No specific containing cluster info for label '{label_name}' (level {level_numeric}).")


        all_mutations.append(label_node)
        logger.debug(f"Prepared Label (level {level_numeric}): {label_name} (ID: {label_unique_id}, Blank UID: {label_blank_uid})")

        # Recursively process children based on the Liris data model structure
        next_level_numeric = level_numeric + 1
        children_list_key = None # Key in the Liris data model for children of current level

        if level_numeric == 0: # Root level
            children_list_key = "parents" 
        elif level_numeric == 1: # Parent level
            children_list_key = "children"
        # For level_numeric == 2 (child), there are no further nested labels in the current Liris data model

        if children_list_key and children_list_key in label_data:
            for child_label_data in label_data[children_list_key]:
                _process_label_hierarchy(
                    child_label_data,
                    next_level_numeric,
                    label_blank_uid, # Current label's blank UID is parent_uid for child
                    current_path_ids + [label_unique_id], # Add current label's ID to path for next level
                    containing_cluster_unique_id, # Pass the same containing cluster info down
                    containing_cluster_blank_uid,
                    all_mutations
                )
    
    # 3. Process Labels for EACH Cluster in 'clusters_detailed'
    for cluster_data in clusters_detailed_from_project:
        cluster_name = cluster_data["name"]
        current_cluster_unique_id = cluster_data["id"] # Use the ID from the Liris data
        current_cluster_blank_uid = cluster_uuid_to_blank_uid_map.get(current_cluster_unique_id)

        if not current_cluster_unique_id or not current_cluster_blank_uid:
            logger.warning(f"Could not find Dgraph ID/UID for cluster '{cluster_name}'. Labels within this cluster may not be correctly linked.")
            continue

        root_labels_of_this_cluster = cluster_data.get("root_labels", [])
        for root_label in root_labels_of_this_cluster:
            _process_label_hierarchy(
                root_label,
                0, # Numeric level 0 for root
                None, # Root labels have no Dgraph parent UID for relation
                [], # Start with an empty path of IDs for root
                current_cluster_unique_id, # Pass the specific unique ID of the containing cluster
                current_cluster_blank_uid, # Pass the specific blank UID of the containing cluster
                mutations
            )
    
    return mutations

def insert_hierarchy(client, project_data):
    """
    Executes Dgraph mutations to insert the ontology.
    """
    txn = client.txn()
    try:
        mutations = generate_dgraph_mutations(client, project_data)
        if not mutations:
            logger.info("No mutations to perform for the current project data.")
            return

        assigned = txn.mutate(set_obj=mutations)
        txn.commit()

        logger.info("Ontology imported successfully.")
        logger.info(f"Assigned UIDs: {assigned.uids}")

    except Exception as e:
        logger.error(f"Error importing ontology: {e}")
        try:
            txn.discard()
            logger.info("Transaction discarded.")
        except Exception as discard_e:
            logger.error(f"Error discarding transaction: {discard_e}")
    finally:
        # Ensure transaction is always finalized (committed or discarded)
        try:
            txn.discard()
        except pydgraph.AbortedError:
            pass # Already committed or discarded, ignore error


def main():
    # Project data exported from Liris
    # This data will be dynamically inserted by the script generator
    PROJECT_DATA = {
        "name": "spec_Liris",
        "turing_ontology": {
            "cluster": [
                "first_cluster",
                "node_mutation_app_edit_js.py",
                "recep.txt",
                "second_cluster",
                "Ma musique",
                "Mes images",
                "Mes vidéos",
                "WindowsPowerShell",
                "desktop.ini",
                "liris"
            ],
            "clusters_detailed": [
                {
                    "name": "first_cluster",
                    "id": "92585cf0-21cf-46d0-b7d8-cf9809accabc",
                    "root_labels": [
                        {
                            "name": "global.js",
                            "id": "07523fb0-6aea-46d1-a640-f1a532bd2c7b",
                            "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\first_cluster\\global.js",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": [],
                            "path": "",
                            "parent": [],
                            "child": []
                        },
                        {
                            "name": "src",
                            "id": "2c1a8e40-7c36-49e5-a4dc-9fe9dca24258",
                            "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\first_cluster\\src",
                            "type": "directory",
                            "parent_labels": [
                                {
                                    "name": "app.js",
                                    "id": "82bf0ae7-17bd-413d-a1bd-02bc6c877847",
                                    "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\first_cluster\\src\\app.js",
                                    "type": "file",
                                    "category": [],
                                    "parent_labels": [],
                                    "child_labels": [
                                        {
                                            "name": "connectDb",
                                            "type": "directory",
                                            "id": "7207ea59-8e99-4907-a1dd-16bd66f75ad0",
                                            "full_path": "",
                                            "parent_labels": [],
                                            "child_labels": []
                                        }
                                    ]
                                },
                                {
                                    "name": "index.js",
                                    "id": "05f9ed6b-170f-442f-a43a-2ffb21a614b9",
                                    "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\first_cluster\\src\\index.js",
                                    "type": "file",
                                    "category": [],
                                    "parent_labels": [],
                                    "child_labels": []
                                },
                                {
                                    "name": "routes.js",
                                    "type": "directory",
                                    "id": "f807d87c-b2e2-4b4c-913f-6834078301fa",
                                    "full_path": "",
                                    "child_labels": [],
                                    "parent_labels": []
                                }
                            ],
                            "child_labels": [],
                            "path": "",
                            "parent": [],
                            "child": []
                        },
                        {
                            "name": "target",
                            "id": "b0b4d91a-a574-4720-a170-659d25e5facd",
                            "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\first_cluster\\target",
                            "type": "directory",
                            "parent_labels": [],
                            "child_labels": [],
                            "path": "",
                            "parent": [],
                            "child": []
                        }
                    ]
                },
                {
                    "name": "node_mutation_app_edit_js.py",
                    "id": "14994a0b-7f8f-4a22-ae19-a1601f797e0f",
                    "root_labels": []
                },
                {
                    "name": "recep.txt",
                    "id": "2cf9b56d-adbb-4277-90f3-f7c279081548",
                    "root_labels": []
                },
                {
                    "name": "second_cluster",
                    "id": "2f602438-74ff-45ae-a744-4c6a85d344d7",
                    "root_labels": [
                        {
                            "name": "cluster_promt.js",
                            "id": "bad451e5-f248-4dc7-9f09-ae6cada894e9",
                            "full_path": "C:/Users/Ditrakely/Desktop/spec_Liris\\second_cluster\\cluster_promt.js",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": [],
                            "path": "",
                            "parent": [],
                            "child": []
                        }
                    ]
                },
                {
                    "name": "Ma musique",
                    "id": "f8ce8407-0006-484f-9b1f-2a45219ce817",
                    "root_labels": []
                },
                {
                    "name": "Mes images",
                    "id": "1e6df047-aa71-48ee-be45-a6c3c2d09ca5",
                    "root_labels": []
                },
                {
                    "name": "Mes vidéos",
                    "id": "0c05f349-513c-4b35-a31e-4e69d3b0ec4f",
                    "root_labels": []
                },
                {
                    "name": "WindowsPowerShell",
                    "id": "e94234cf-ec4e-43d3-8c3c-9e7df167f8b5",
                    "root_labels": []
                },
                {
                    "name": "desktop.ini",
                    "id": "393132f0-0c73-4b2a-b26c-16faacc81b0c",
                    "root_labels": []
                },
                {
                    "name": "liris",
                    "id": "a022dfcb-6c12-4486-95cd-3e017350e6ff",
                    "root_labels": [
                        {
                            "name": ".git",
                            "id": "9b62ed4c-99a1-4f1c-bdfc-bdeeab1b6bd9",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "COMMIT_EDITMSG",
                                    "id": "322b1a47-ad6d-4192-ab69-80a9fa0a14a1",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\COMMIT_EDITMSG",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "FETCH_HEAD",
                                    "id": "08e8423c-035c-4143-bb04-fbfcb53630bb",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\FETCH_HEAD",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "HEAD",
                                    "id": "0d20668e-09c9-46dc-bcfa-fb8d0a8f0a47",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\HEAD",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "ORIG_HEAD",
                                    "id": "6c3693d6-09b0-4be1-a09f-e5e127358302",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\ORIG_HEAD",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "config",
                                    "id": "72bd5c17-8a12-4a89-b76b-3f8e3036326b",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\config",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "description",
                                    "id": "7ab2f193-1c35-443c-9cb9-755e241aa058",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\description",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "hooks",
                                    "id": "af191c78-00c9-42c6-8b8c-72175e5b38ff",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "applypatch-msg.sample",
                                            "id": "b96ede4c-bddf-4f79-b96c-35703842a2a3",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\applypatch-msg.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "commit-msg.sample",
                                            "id": "99e9a0d1-228a-4b7c-a9ca-1356d89a0f6b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\commit-msg.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "fsmonitor-watchman.sample",
                                            "id": "47cc341d-d5f4-4b86-97de-51423607d161",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\fsmonitor-watchman.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "post-update.sample",
                                            "id": "00dbc13b-6e08-4284-9d68-e5e6fc83cab5",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\post-update.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-applypatch.sample",
                                            "id": "63b538b3-82a2-4b53-9293-6d943a16191a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-applypatch.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-commit.sample",
                                            "id": "e6328c15-49dd-4e43-8cad-5aefa8443749",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-commit.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-merge-commit.sample",
                                            "id": "d7e7082c-e09a-4394-b687-2d4eb3a56c4c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-merge-commit.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-push.sample",
                                            "id": "41a84cab-346b-4898-a190-5d88e49ad076",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-push.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-rebase.sample",
                                            "id": "0c9a2c11-4499-47ea-a3d1-e44c0a414972",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-rebase.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pre-receive.sample",
                                            "id": "c0894491-86ae-42dc-87dc-9a7e81e4406c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\pre-receive.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "prepare-commit-msg.sample",
                                            "id": "a36274c6-170f-4f46-a5c1-79771ed34d23",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\prepare-commit-msg.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "push-to-checkout.sample",
                                            "id": "9bbfbc1f-ad5d-407b-9d4a-f9d12c671766",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\push-to-checkout.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "sendemail-validate.sample",
                                            "id": "31b618f8-9a7c-4099-ad36-74b5219b3598",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\sendemail-validate.sample",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "update.sample",
                                            "id": "a83f8abd-6f6e-44ef-9355-f7ab734f0b27",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\hooks\\update.sample",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "index",
                                    "id": "45430481-3831-4ec0-84cc-be9018b55b37",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\index",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "info",
                                    "id": "247ebc94-6eef-4158-94e0-a60cc797014d",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\info",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "exclude",
                                            "id": "4bcc0737-586d-4c10-99d4-af9f2150495d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\info\\exclude",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "logs",
                                    "id": "ad750209-fb08-4103-aad9-57602f85e18f",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\logs",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "HEAD",
                                            "id": "97c96e37-6fc0-402c-80bd-c4d90cca7bc5",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\logs\\HEAD",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "refs",
                                            "id": "814e376e-ffbe-4c50-aca7-720823eeaf05",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\logs\\refs",
                                            "type": "directory"
                                        }
                                    ]
                                },
                                {
                                    "name": "objects",
                                    "id": "97b781a1-0188-4b6c-b4aa-83f454da1959",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "09",
                                            "id": "939be6a8-d371-45d4-b469-bd326ba1d0ed",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\09",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "0c",
                                            "id": "e5af5ef2-4e97-47ab-ac3c-fb15b825b398",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\0c",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "11",
                                            "id": "4a97b2ec-ec33-4bcf-b154-32b705ae7752",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\11",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "15",
                                            "id": "289500b5-d759-4898-9718-bc2864381f12",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\15",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "1f",
                                            "id": "afed389b-135f-482b-ad08-98a6963221b9",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\1f",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "21",
                                            "id": "a9c595ed-3dd1-4df6-a9ec-cc32cc719e88",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\21",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "22",
                                            "id": "28b59f4a-6d3e-4fc3-988e-956b4f2089b7",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\22",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "23",
                                            "id": "b7bb660a-7931-4676-804d-fc5a72a6821b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\23",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "24",
                                            "id": "50ebb14b-b6fb-41ad-ba1f-ffe4c5baf883",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\24",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "27",
                                            "id": "242376a1-23a7-4560-bcf9-cbc4ca26eeb1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\27",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "28",
                                            "id": "660c55e0-6ac0-4764-a15f-bff695772cdf",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\28",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "31",
                                            "id": "7ddceb90-05a5-4dd5-bba7-af944b9fbb70",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\31",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "32",
                                            "id": "9b86c0d3-8edd-4851-a575-7328ad3a8c92",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\32",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "38",
                                            "id": "031cf91d-85dd-418d-a75e-3ca44c3fff73",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\38",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "42",
                                            "id": "200c6b86-476c-40fa-ad1e-73eab9933121",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\42",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "4e",
                                            "id": "efe2afb2-aff2-4606-9f24-577a7d3ce812",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\4e",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "53",
                                            "id": "c61ff8b3-54ff-4da1-a9eb-1481776bf641",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\53",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "54",
                                            "id": "1bb8f357-2556-41ef-827a-e24f446448a8",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\54",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "56",
                                            "id": "a5a1a507-4868-4e11-ae9f-0ffd8080562c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\56",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "5c",
                                            "id": "aad3b16a-f2e1-4691-8c7c-258aab2ca854",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\5c",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "60",
                                            "id": "e593f7a8-a688-4897-8fb6-0d7688acc156",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\60",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "62",
                                            "id": "24a54e45-0cd4-4e02-be39-def38aab6635",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\62",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "67",
                                            "id": "2290f6f6-969b-4d7f-afcc-ac328a7efa90",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\67",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "69",
                                            "id": "8da85c1e-d29a-4f02-9c32-a5ffcb0e9a17",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\69",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "6f",
                                            "id": "17a4fca0-9208-4b41-9cc2-e5b17349aa45",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\6f",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "75",
                                            "id": "5f761c00-04a9-4879-93e8-7a3c9846312d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\75",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "77",
                                            "id": "f858f816-7cf3-459d-aebb-f9734e5d0450",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\77",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "78",
                                            "id": "1c862b13-6ae5-42f1-a6f8-95301790d77f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\78",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "7d",
                                            "id": "b66e482b-2325-42b6-b0a5-722f3af59a25",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\7d",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "84",
                                            "id": "9d379a50-7723-463f-bcac-eb9f7323d91b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\84",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "88",
                                            "id": "3f9237a4-1d46-4279-af5a-361ba5a1efa9",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\88",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "95",
                                            "id": "9ac2a922-d3b3-4325-9aba-118531084952",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\95",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "96",
                                            "id": "c4bcb6f5-b0ad-45f1-bbd4-42596d58e92a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\96",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "9c",
                                            "id": "644b9765-4b6a-4abc-a832-6c3b7b5b5d10",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\9c",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "a5",
                                            "id": "3e4cf950-1f9f-47e8-a183-3aab10ce8355",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\a5",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "a8",
                                            "id": "b679284f-45ee-4eab-82c2-64e344335917",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\a8",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "b1",
                                            "id": "45259d27-0979-48e2-8313-b968c1027e40",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\b1",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "b7",
                                            "id": "6185dd50-eae5-4692-840b-30632bdcd003",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\b7",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "c3",
                                            "id": "1cd1ccfb-af56-4c01-94ce-1a736aded8ea",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\c3",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "c7",
                                            "id": "354da25d-3da8-4c0d-bf5a-16e9138385df",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\c7",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "c8",
                                            "id": "47622086-1f8b-45c4-a284-5df628ca4b9f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\c8",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "cd",
                                            "id": "85fe5007-2656-4bdb-b990-acc5c209ed37",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\cd",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "ce",
                                            "id": "afe01208-f4fd-46f2-9a15-ebf1797a331f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\ce",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "cf",
                                            "id": "2800bcc5-8ff9-42f7-bc9c-289e6cd1e678",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\cf",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "d3",
                                            "id": "df89943e-b0ed-492a-bb94-2e4455d6b82b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\d3",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "d4",
                                            "id": "96a344fe-7a06-4d7d-b28d-afa376ab0da6",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\d4",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "dd",
                                            "id": "3b5374bb-c0dd-41f4-893d-32dda03888e3",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\dd",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "e1",
                                            "id": "6cc256b6-836d-47d6-84b7-6e72a390ed86",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\e1",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "ed",
                                            "id": "1e8f55d0-6ec0-4c4c-bc83-942748f65e92",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\ed",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "ef",
                                            "id": "01f55651-1432-4eaa-9475-90f5c32d92ef",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\ef",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "f1",
                                            "id": "04dc0fb3-a839-4a00-a39e-9abe88fae2fd",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\f1",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "f3",
                                            "id": "992f21f0-69bc-4a50-98db-d74de0f3eb6a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\f3",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "f4",
                                            "id": "1915dfb1-8846-4138-bafa-9db9971cf507",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\f4",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "ff",
                                            "id": "6973a13c-94fa-4da2-b78a-0ef128e4aa43",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\ff",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "info",
                                            "id": "5a55f5d6-03ed-4083-9313-93744482fdfa",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\info",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "pack",
                                            "id": "08abd7a2-804f-497f-99ea-fbab1fc4beef",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\objects\\pack",
                                            "type": "directory"
                                        }
                                    ]
                                },
                                {
                                    "name": "packed-refs",
                                    "id": "83600660-a743-455d-8950-825b13617b0f",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\packed-refs",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "refs",
                                    "id": "3b3de8c9-5c46-46c0-b747-8fa1d910da66",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\refs",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "heads",
                                            "id": "a0a0bcb3-baf9-43fc-b030-ac76a5955dec",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\refs\\heads",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "remotes",
                                            "id": "a633225e-4514-4f46-a2c6-2bc81f7ff72e",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\refs\\remotes",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "tags",
                                            "id": "4a92bf96-9380-40df-b668-81814568affc",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.git\\refs\\tags",
                                            "type": "directory"
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": ".gitignore",
                            "id": "41f9a48f-3c9f-4184-a533-9ba22ed757e1",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\.gitignore",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": ".idea",
                            "id": "167978d9-be52-4cd9-98f7-392b3dc3003d",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\.idea",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": ".gitignore",
                                    "id": "63a3625b-8d04-4780-a4a5-6822c79733d8",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\.gitignore",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": ".name",
                                    "id": "2eb2c147-af9d-476e-b4ab-46824d566241",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\.name",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "inspectionProfiles",
                                    "id": "00df546d-dfff-4b11-b92a-32507a1a9665",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\inspectionProfiles",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "profiles_settings.xml",
                                            "id": "c9464976-a10f-4ef0-a839-1c22ca531975",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\inspectionProfiles\\profiles_settings.xml",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "liris.iml",
                                    "id": "4fd3acf4-87d0-4ade-b7d3-b583595a6330",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\liris.iml",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "misc.xml",
                                    "id": "20bf311c-90f4-46d6-8d81-93735debba16",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\misc.xml",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "modules.xml",
                                    "id": "4e2ff618-4a42-4a5e-9d35-efce1b8e3582",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\modules.xml",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "vcs.xml",
                                    "id": "b499781e-dd96-451d-b2b3-46f556f3c6e0",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\vcs.xml",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "workspace.xml",
                                    "id": "b2feb924-2557-430c-8d21-32d78bb52c09",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.idea\\workspace.xml",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": ".venv",
                            "id": "53b8b7bb-5ef1-4ac8-bffa-6b101bd62072",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": ".gitignore",
                                    "id": "eaedd48c-97d4-41bc-987c-d7042eb6d170",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\.gitignore",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "CACHEDIR.TAG",
                                    "id": "42cef92b-7eac-48d3-8a7e-afd05b2cf7d4",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\CACHEDIR.TAG",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "Lib",
                                    "id": "3c6fc5e3-ee59-41cc-820d-7c8e9e394c77",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Lib",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "site-packages",
                                            "id": "2180653e-135f-49a7-9bae-7cd0c09aab16",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Lib\\site-packages",
                                            "type": "directory"
                                        }
                                    ]
                                },
                                {
                                    "name": "Scripts",
                                    "id": "fba6ef44-e016-4571-807a-07fdf36eb231",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__pycache__",
                                            "id": "6f24b93d-7901-46d2-8f78-83c20ecc4b12",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "activate",
                                            "id": "76e68eb7-5b73-4e8b-a1d1-62a87544e0a3",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "activate.bat",
                                            "id": "6575d526-b721-4bca-a880-440da641523c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate.bat",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "activate.fish",
                                            "id": "e3ae011f-962a-4f5e-8ded-8dab7c6c0150",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate.fish",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "activate.nu",
                                            "id": "93a18f9e-50d8-4099-9b37-daac764c7531",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate.nu",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "activate.ps1",
                                            "id": "48e1e228-a784-434c-9052-db1dee8bc9a2",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate.ps1",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "activate_this.py",
                                            "id": "282c6a27-0fa4-46f9-a4e8-32a3e1865b97",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\activate_this.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "deactivate.bat",
                                            "id": "6b1576ed-0553-46c2-b638-6c01e0a9920d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\deactivate.bat",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "f2py.exe",
                                            "id": "19cce279-67c7-4ab1-8960-698c66bb82be",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\f2py.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "fonttools.exe",
                                            "id": "9bad8009-7d7f-4baf-86f2-c920cd23299c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\fonttools.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "normalizer.exe",
                                            "id": "ffdf0115-2d4d-437b-aefe-92d1f00f6c20",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\normalizer.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "numpy-config.exe",
                                            "id": "08f772d1-f542-464b-9bd2-3015837a17b1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\numpy-config.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pip-3.13.exe",
                                            "id": "331394a6-c13f-4977-8c03-a80023b883b1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pip-3.13.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pip.exe",
                                            "id": "7b5cb131-dafe-4813-8582-0f99d9afbe76",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pip.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pip3.13.exe",
                                            "id": "19cab293-8c89-4c70-9449-a18090e8f68d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pip3.13.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pip3.exe",
                                            "id": "202852fb-91ad-411b-a97c-f75383f813e4",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pip3.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pydoc.bat",
                                            "id": "970264b4-9766-4ca6-bc30-44069257af3f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pydoc.bat",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pyftmerge.exe",
                                            "id": "6269d8ab-1099-47ef-8b1e-c5af52618d77",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pyftmerge.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pyftsubset.exe",
                                            "id": "55c12adb-7b31-4e9c-bbcf-22511a9cb8c5",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pyftsubset.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pylupdate5.exe",
                                            "id": "cee36391-175a-41e5-96da-734a6bfc21f6",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pylupdate5.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pyrcc5.exe",
                                            "id": "6741b966-036d-458f-8e14-05adbff4912c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pyrcc5.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pytesseract.exe",
                                            "id": "a1c642f7-41ec-4094-a0a2-8245c545d52f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pytesseract.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "python.exe",
                                            "id": "39bb12fa-7064-4a83-becf-e75b2fb00c4d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\python.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "python3.dll",
                                            "id": "5cba9114-a16e-41e6-b7aa-7ab92f2597a0",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\python3.dll",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "python313.dll",
                                            "id": "ec8d20e4-30c6-4106-afbc-8aaff6949fb6",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\python313.dll",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pythonw.exe",
                                            "id": "f78e8ff6-948c-4a31-896e-f551d6d1c2fb",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pythonw.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "pyuic5.exe",
                                            "id": "7d7c0c8b-485f-4aca-a5df-d94fc3a5d266",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\pyuic5.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "runxlrd.py",
                                            "id": "3c366a5c-ce0b-44e6-b08b-859bcfd5c05f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\runxlrd.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "tabulate.exe",
                                            "id": "0d0e75dd-d530-451f-a4d0-d559d43f4a38",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\tabulate.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "ttx.exe",
                                            "id": "5490f596-a7a8-4131-85a8-829db1625a10",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\ttx.exe",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "vcruntime140.dll",
                                            "id": "0f13e54d-5e78-4501-ad91-983ee727bda8",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\vcruntime140.dll",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "vcruntime140_1.dll",
                                            "id": "9fa2695a-37b0-49b2-acc9-2fbb86a02d5a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\Scripts\\vcruntime140_1.dll",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "pyvenv.cfg",
                                    "id": "ebf410cb-054a-4995-96f0-a69f1cb617fb",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\pyvenv.cfg",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "share",
                                    "id": "50607889-75c5-4a2c-a6d5-3a625171eba7",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\share",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "man",
                                            "id": "d5ce73b0-231c-49ee-a512-4585cb80858c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\.venv\\share\\man",
                                            "type": "directory"
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "Liris.spec",
                            "id": "279eb85c-764b-442e-b34c-d88abe1ed2af",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\Liris.spec",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "README.md",
                            "id": "ef31f72e-5170-4377-aa69-d19930b47871",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\README.md",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "check_settings.py",
                            "id": "06bd43b1-0555-494d-88d3-a3078c4a95a6",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\check_settings.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "config",
                            "id": "31c4d4b5-1301-4aaf-b82b-50b055f25a95",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\config",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "__init__.py",
                                    "id": "7eff1cf5-c4b0-4c9c-bf03-431f4365197e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "780f768c-dd0f-4a8f-9a37-f541d69a02e1",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "3827c83f-4b6d-42ad-81e8-2aa54a1bbdc0",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "console_shortcuts.cpython-313.pyc",
                                            "id": "191e8095-ad39-4ed6-b6ec-007622447d63",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__pycache__\\console_shortcuts.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "detect_clic_user.cpython-313.pyc",
                                            "id": "dc84a1d0-b32d-425a-8aaf-a5470fa96944",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__pycache__\\detect_clic_user.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "settings.cpython-313.pyc",
                                            "id": "0abdc352-cd9c-4c08-853c-9ebf966765a9",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\__pycache__\\settings.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "console_shortcuts.py",
                                    "id": "c71caae6-8e99-41b1-b609-bf490ad386b2",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\console_shortcuts.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "detect_clic_user.py",
                                    "id": "c540c762-0fd1-41d1-97fd-2c6b48835040",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\detect_clic_user.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "profiles",
                                    "id": "f190a112-f12c-4177-8a56-403ca729e118",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": ".Custom AI Platform.deleted",
                                            "id": "633efe2a-06b1-4dba-aff4-7242f09f7d27",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\.Custom AI Platform.deleted",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": ".keyboard_config.deleted",
                                            "id": "fbc68b42-bc6b-4b2b-9161-650a901dc413",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\.keyboard_config.deleted",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "Gemini.json",
                                            "id": "60150cb5-27e4-4890-831c-f9972e8c3c8e",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\Gemini.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "Genius 27 Turing.json",
                                            "id": "402ba45d-ec27-4b2c-bab8-6edc4f010de9",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\Genius 27 Turing.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "Genius Turing.json",
                                            "id": "50087e49-8755-497d-a0ae-0ef700966c86",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\Genius Turing.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__init__.py",
                                            "id": "bc3b7e87-8df3-4668-9456-9be28d7b4cf1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "browsers",
                                            "id": "61de90fe-2c38-4b56-8cc0-1d5d040aef5b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\browsers",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "chatgpt.json",
                                            "id": "b708e3ec-a159-4ec0-a5e4-6ae4977722a0",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\chatgpt.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "claude.json",
                                            "id": "f5c24036-86c4-4589-8c98-70323d4d3619",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\claude.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "custom.json",
                                            "id": "a5a3367c-bafd-4f13-b705-ed7d10a719cb",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\custom.json",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "keyboard_config.json",
                                            "id": "874526c2-2f67-47a1-9218-8a272e08811f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\config\\profiles\\keyboard_config.json",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "settings.py",
                                    "id": "93ab45bb-4fcd-4d4d-a4f6-789b0ca2ca7f",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\config\\settings.py",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "core",
                            "id": "aca0f634-027c-4d01-8c33-09c4fe41b084",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\core",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "__init__.py",
                                    "id": "c7602469-a331-41a2-9b04-face96514170",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "e1bad2b2-f274-46ed-be91-e91bfc246e8a",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "9bd4cac7-b823-464a-9132-da157dcbd89c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "data",
                                    "id": "24507472-0e81-4645-b26a-a246dda2dbe9",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "4c674cb3-b220-426c-8690-c369e3209681",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "72d22834-30ce-41ab-bb7d-069e4a11e3aa",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "database.py",
                                            "id": "6eb2bf30-3d01-4988-b7ed-3432ba666244",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\database.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "exporter.py",
                                            "id": "73ca987d-eb43-4521-8658-754dff00619e",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\exporter.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "migrations.py",
                                            "id": "8dbd8d27-9ae8-44e2-8c69-4c499bff97e7",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\migrations.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "parser.py",
                                            "id": "0f870b86-21b4-4b13-9795-e7b08b12d2a7",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\data\\parser.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "interaction",
                                    "id": "24ece1c8-078f-47a6-a56f-20568d4ea679",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "60d48f8e-72ee-4c07-b541-37035200b20a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "ce0d368b-daee-4813-87a0-f031c8fb24fd",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "keyboard.py",
                                            "id": "7054de3a-5dc0-42db-a4cd-8e99b45c06da",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction\\keyboard.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "mouse.py",
                                            "id": "c2c0d96d-d0e4-4c4e-95ce-187cb4e1a747",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction\\mouse.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "screen.py",
                                            "id": "259a1947-8114-4dea-b792-831bd8513707",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\interaction\\screen.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "orchestration",
                                    "id": "1b1425c3-1b2a-4857-9460-89fb61b97a23",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\orchestration",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "44a874aa-5c1d-407e-9a33-47504fb3724d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\orchestration\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "f56d4d53-68a5-4620-93e5-781bd4c09e60",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\orchestration\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "conductor.py",
                                            "id": "d6768fd0-8eed-42d6-8030-bb904e5a49b1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\orchestration\\conductor.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "state_automation.py",
                                            "id": "e6751c68-d3d4-4b82-b7f3-1521c9bd4d92",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\orchestration\\state_automation.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "scheduling",
                                    "id": "a1ff3d67-b6ae-4b02-8d1f-1eff5041f123",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\scheduling",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "7cc2f5f7-8d77-4d7f-801d-5db3bfd647d1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\scheduling\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "3d45fc41-5767-4e6f-a718-9d63ab8777fc",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\scheduling\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "queue.py",
                                            "id": "406b6ee2-50b4-4598-b830-7f89c4d8cae7",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\scheduling\\queue.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "scheduler.py",
                                            "id": "2d23d5b5-047d-41b0-a49c-147a4b6e7016",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\scheduling\\scheduler.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "vision",
                                    "id": "8e3fb950-2192-45c1-8621-a94eeeeb5f0e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "1d97215a-e918-46b3-ae7e-d935378823bb",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "color_extractor.py",
                                            "id": "426a6f55-9a05-48b6-b2a8-d062bbb4a3df",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision\\color_extractor.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "detector.py",
                                            "id": "f828d34d-d56d-41d6-9aee-edede80dda9a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision\\detector.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "recognizer.py",
                                            "id": "dccd13c2-038e-406c-8ab1-9a391b25e46d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision\\recognizer.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "utils.py",
                                            "id": "ecfa9324-57dd-42d3-af55-96d00f73cc75",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\core\\vision\\utils.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "data",
                            "id": "aa8bbd3e-ab73-47a8-8845-2732ef8bded6",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\data",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "liris.db",
                                    "id": "31e6e85b-a0a5-48a3-8007-d60a1cedba1e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\data\\liris.db",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "dataset_json_20250710_155057",
                            "id": "370e2dba-a645-4b93-a30d-a048faaaf4c6",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\dataset_json_20250710_155057",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "dgraph_import_Liris_project.py",
                            "id": "8a03116b-351b-449c-8704-9b8b5d48096d",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\dgraph_import_Liris_project.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "dgraph_import_project_mutate.py",
                            "id": "7efab96b-da27-4657-a25e-ae2d4b9217e3",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\dgraph_import_project_mutate.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "dgraph_import_spec_Liris.py",
                            "id": "8b3e88e3-6123-40f0-8d25-c50411648796",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\dgraph_import_spec_Liris.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "dgraph_mutation_project_ontologie.py",
                            "id": "b64fe529-82de-4cd3-bf8d-6d59495480d0",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\dgraph_mutation_project_ontologie.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "exports",
                            "id": "88af6427-33e8-48a6-a710-1a50958427c7",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\exports",
                            "type": "directory",
                            "parents": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "force_reset.py",
                            "id": "aa66d5f8-2b3a-4a51-9bea-0545e061f584",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\force_reset.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "logs",
                            "id": "a6d1c3ee-17e6-4498-bfde-d4b5415e562a",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\logs",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "ai_automation_20250923.log",
                                    "id": "bd66419e-3f2f-4963-a26e-1f34d1d4f1d3",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\logs\\ai_automation_20250923.log",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "ai_automation_20250924.log",
                                    "id": "e6f45d9f-32db-4039-aa01-ccad96f51c14",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\logs\\ai_automation_20250924.log",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "main.py",
                            "id": "6fcae9c6-22e4-4f86-be31-76cdd23788f1",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\main.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "modules",
                            "id": "6c4dc5ad-e2a7-4ba0-ab81-2e9f3274923c",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "__init__.py",
                                    "id": "fceb9f63-79b5-4cec-948a-ee7d4437f55d",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "02649e5e-f0ad-4d23-9488-fcb127405e0f",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "4267ca22-1310-4dc1-a178-b50f52a41621",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "brainstorming",
                                    "id": "402e7b7f-4757-4e83-a9d6-7c86eff9a6d0",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "944f4add-c213-4d42-8218-a46ad4dd6eaf",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "3e4bfdbd-e85c-4a25-8e27-6d25775b8f32",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "competition_prompts.py",
                                            "id": "06c999f0-a2e0-40eb-9232-f9c0ef0856e2",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\competition_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "evaluation_prompts.py",
                                            "id": "fed4227d-cd98-423f-a911-25e823aa7536",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\evaluation_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "orchestrator.py",
                                            "id": "9d15ce5f-1b3d-491f-bab8-463c7d735caa",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\orchestrator.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "scoring_prompts.py",
                                            "id": "6dd324c2-575e-4798-8c8c-00bbefe6a053",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\scoring_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "templates.py",
                                            "id": "5c5f9382-0dcf-4638-a62b-360af8e2dbe2",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\brainstorming\\templates.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "content_analysis",
                                    "id": "afd3557d-9b85-4a68-95c7-c915199bd973",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\content_analysis",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "d0dbced7-a6e8-40bf-9e42-51232466234c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\content_analysis\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "analyzer.py",
                                            "id": "f716058f-29c3-46f0-a16b-a81d196cb97d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\content_analysis\\analyzer.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "templates.py",
                                            "id": "1c97448a-60fc-4ddc-94b9-6cf764a31afe",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\content_analysis\\templates.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "dataset_annotation",
                                    "id": "f646a35d-59ee-42ea-8074-6239d2227c4a",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_annotation",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "2bc11a31-3746-4fc0-8bc4-597147d1e44d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_annotation\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "8c37b7f5-ae11-4448-9799-247cf3e460df",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_annotation\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "annotator.py",
                                            "id": "d3f00607-7221-45bb-a2c7-9a8fc520d3b4",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_annotation\\annotator.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "templates.py",
                                            "id": "5b06baf6-e148-49dd-8dff-486703df54b8",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_annotation\\templates.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "dataset_generation",
                                    "id": "6f7fb7ae-7bb8-4dc1-ba97-92e2f87ae6e7",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_generation",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "b7b9e7fa-bf56-4e10-a3e9-1f72b4b39836",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_generation\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "generator.py",
                                            "id": "1041d657-8b94-4b3c-852d-dde645019306",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_generation\\generator.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "templates.py",
                                            "id": "8636b0c1-1951-4726-884a-3d83c37bc492",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\modules\\dataset_generation\\templates.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "objectif_data_science.md",
                            "id": "ec48923f-1521-42b5-ae0c-644778472b47",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\objectif_data_science.md",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "refresh_table.md",
                            "id": "4aa033ce-ff73-47a2-8f65-80c9b00390b7",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\refresh_table.md",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "requirements.txt",
                            "id": "726528f1-5d2a-4e7f-8cbd-a0ee56a7dba1",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\requirements.txt",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "schema.txt",
                            "id": "e1e6838f-5c11-4863-b174-1258a9bc51bd",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\schema.txt",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "scripts",
                            "id": "b445bdb4-ce74-48b1-b05b-d42f60355e59",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\scripts",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": ".ui_patch_applied",
                                    "id": "8889e384-9257-47e1-9ece-1a39714d1027",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\.ui_patch_applied",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__init__.py",
                                    "id": "13891acf-5164-4c40-8d13-4bf143dd2ad3",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "auto_test_language_selector.py",
                                    "id": "02a494b3-f087-4ef5-9053-4e65c3ba9d43",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\auto_test_language_selector.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "check_dependencies.py",
                                    "id": "f63bdd22-c99c-4237-a8d0-b2b04395afc9",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\check_dependencies.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "check_json_content.py",
                                    "id": "a7d04a1e-91bd-4ff6-9af7-065e67caecd9",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\check_json_content.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "clean_backgrounds.ps1",
                                    "id": "682b072d-dc09-4617-be4e-67a32b059531",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\clean_backgrounds.ps1",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "debug_translation.py",
                                    "id": "6ee920c1-1b38-4331-b40b-606491c93f52",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\debug_translation.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "diagnostic_db.py",
                                    "id": "4a3b95ec-7401-4e04-b2f7-a5ebf514774b",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\diagnostic_db.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "fix_scheduler.py",
                                    "id": "3cf7896e-c32a-44af-bf8e-5f4e5cdd2100",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\fix_scheduler.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "fix_ui_detection.py",
                                    "id": "93fe3820-6251-46ea-b310-c0faed9e06dd",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\fix_ui_detection.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "initialize_defaults.py",
                                    "id": "f843ca64-d32c-4015-8a61-5310e1b534a1",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\initialize_defaults.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "reset_platforms_database.py",
                                    "id": "eb661fe3-f906-43b0-8e0b-f70dd1f0f9fa",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\reset_platforms_database.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "unblock_ui.py",
                                    "id": "bcef1463-6c06-430b-be46-5506b3b5c655",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\scripts\\unblock_ui.py",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "templates",
                            "id": "c14a35a8-b5f8-4361-9a04-2f8dd2d3b892",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "__init__.py",
                                    "id": "cdf35d21-0ce0-47cf-8c67-da1dc34e91cc",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "6257e131-f000-4cd5-90ba-a0741970afc2",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "606ec0eb-00b9-4026-8098-6db150570465",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "brainstorming",
                                    "id": "d9cd90df-ce4d-402c-81d8-0b37f4fc8d4e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\brainstorming",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__pycache__",
                                            "id": "cb59daac-41a9-4177-8092-ae3807a6c520",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\brainstorming\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "competition_prompts.py",
                                            "id": "05735f87-4cdd-4ed7-93fc-bbec8520e649",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\brainstorming\\competition_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "evaluation_prompts.py",
                                            "id": "f9a1bc20-678e-43cd-8e9d-0f0fb547d10a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\brainstorming\\evaluation_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "scoring_prompts.py",
                                            "id": "9f8e3bb4-29fd-4504-8151-931ef971b90a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\brainstorming\\scoring_prompts.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "content_analysis",
                                    "id": "760f541d-d92d-48d8-8dab-a7a8ad8f0be9",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\content_analysis",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "structured_prompts.py",
                                            "id": "6ce1172e-5897-4868-88cb-c9f460f2b1b5",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\content_analysis\\structured_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "text_prompts.py",
                                            "id": "2e3786ef-be46-4809-b3bb-572700f0e924",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\content_analysis\\text_prompts.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "dataset_annotation",
                                    "id": "2669b7b2-6129-483b-a2be-88670d29fb6a",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\dataset_annotation",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "annotation_prompts.py",
                                            "id": "133abc64-5b8f-4c01-92e5-a7deffab30e1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\dataset_annotation\\annotation_prompts.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "dataset_generation",
                                    "id": "6410af2e-4164-4ce2-bdd8-4c5129dd4af4",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\dataset_generation",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "csv_prompts.py",
                                            "id": "fee0726f-82ab-4b49-aec6-a7c7938e9e68",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\dataset_generation\\csv_prompts.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "json_prompts.py",
                                            "id": "5436c42b-e53d-4fad-ae71-88043e6c6e45",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\templates\\dataset_generation\\json_prompts.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "ui",
                            "id": "02be3d0f-4800-4e89-96bd-278a0ac591fb",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": ".platforms_initialized",
                                    "id": "ec74fd78-d24b-4737-9f06-41ca20eed959",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\.platforms_initialized",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__init__.py",
                                    "id": "d71f3bc4-2530-4dfb-93e9-d91c804343d9",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "c0348ace-12f4-49bd-87cd-bcee0bb161e1",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "8b5a5f14-12d3-4db5-9b95-bc30a229ab9b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "main_window.cpython-313.pyc",
                                            "id": "d3e2ac2f-1729-4b40-ac02-f594b46ddc25",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\__pycache__\\main_window.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "dialogs",
                                    "id": "dd038fc0-b398-4a4c-8ccc-ed7f5d2b4425",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\dialogs",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "d2b1d2e2-3903-4ecf-b690-d4a26a1cf289",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\dialogs\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "results_viewer.py",
                                            "id": "13d7176d-d06c-40f8-a993-905c9122ac9d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\dialogs\\results_viewer.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "settings_dialog.py",
                                            "id": "dfad18ab-3b85-446b-a15d-5a38e0d653b8",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\dialogs\\settings_dialog.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "localization",
                                    "id": "7d9177f0-930c-46b2-823c-f3c0e653ba72",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\localization",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "e7abacf7-5d0a-4e2c-b7df-299f1f5d068e",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\localization\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "fe9e1baf-fd31-4f97-8544-25a7f659463a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\localization\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "translations",
                                            "id": "a7dca127-c885-4791-9aa0-72b85bf03a32",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\localization\\translations",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "translator.py",
                                            "id": "865d88ba-596a-4a15-8db0-a6658231340a",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\localization\\translator.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "main_window.py",
                                    "id": "a6f01ea6-b012-4d3f-8891-94215543be0b",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\main_window.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "resources",
                                    "id": "dc09786d-6c2a-4861-b575-b668ecd5cd97",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "compile_resources.py",
                                            "id": "f5d50e0a-25f9-43ee-8db3-051ae65bfd13",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources\\compile_resources.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "flags",
                                            "id": "ab4eab3d-284a-44b6-87c8-ff5a36a2e794",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources\\flags",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "generate_resources.py",
                                            "id": "2246e564-8a00-406b-a351-2f8d1db90ddf",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources\\generate_resources.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "icons",
                                            "id": "a3f04784-bc38-40db-9f14-9b4b63c8baab",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources\\icons",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "resources.qrc",
                                            "id": "17135c12-3270-4853-8c7a-0a4d88ea29e9",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\resources\\resources.qrc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "styles",
                                    "id": "29006ebf-248d-4aec-ba95-f2b2b960b4f4",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\styles",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "37915500-4e8e-4a07-92c7-26987242a98f",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\styles\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "eac64930-3215-497b-b2c4-d1c2698e6c65",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\styles\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "platform_config_style.py",
                                            "id": "24cca0eb-5bed-4a25-9a63-eec5f4b0b6a6",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\styles\\platform_config_style.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "theme.py",
                                            "id": "6ffbd0ae-6927-44fb-be10-4a610cace552",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\styles\\theme.py",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "widgets",
                                    "id": "dc9a25bc-5c83-4b88-82d4-51c1a54ada4e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.py",
                                            "id": "9943d558-856e-46c9-b6d0-635d3376a093",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\__init__.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "__pycache__",
                                            "id": "66d35edf-ae37-486f-98f1-2cda1927305c",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\__pycache__",
                                            "type": "directory"
                                        },
                                        {
                                            "name": "annotation_form.py",
                                            "id": "711076ea-f3d7-41df-98c5-6578402ca627",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\annotation_form.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "base_widget.py",
                                            "id": "44a755e7-ceab-427b-b2d1-7d78a95122c4",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\base_widget.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "brainstorming_panel.py",
                                            "id": "1723afbb-222f-438c-b5ff-92b26551b767",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\brainstorming_panel.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "coding_panel.py",
                                            "id": "e88232e8-aea9-4401-b397-37f43cf1b983",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\coding_panel.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "dataset_generation.py",
                                            "id": "820fdfdd-379b-496e-aaf6-fe7bac397cfd",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\dataset_generation.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "dataset_generator_widget.py",
                                            "id": "bb91283d-227c-4707-96e7-f9f0e844cfd3",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\dataset_generator_widget.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "dataset_table.py",
                                            "id": "4017a4da-732d-499f-b2fc-858b22260f5d",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\dataset_table.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "emergency_stop_overlay.py",
                                            "id": "700b6df8-1ab4-4b32-ba37-40f3099430c2",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\emergency_stop_overlay.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "language_selector.py",
                                            "id": "1f42f61b-a439-4b97-9d2d-023dc3da2ce1",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\language_selector.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "platform_config_widget.py",
                                            "id": "ee1a336e-7389-40ea-a59a-b17f2bfa686b",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\platform_config_widget.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "project_config_only_widget.py",
                                            "id": "dcd0308a-db26-464b-a30d-e018dc1ab6fd",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\project_config_only_widget.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "prompt_list.py",
                                            "id": "93294b1f-9d2e-45b6-b515-c2e99a727195",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\prompt_list.py",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "tabs",
                                            "id": "e8bb5bec-9a22-4bd5-9019-ed5f30fcdc08",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\ui\\widgets\\tabs",
                                            "type": "directory"
                                        }
                                    ]
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "utils",
                            "id": "3df30625-28f2-46bc-8e54-7e5257dcd62c",
                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils",
                            "type": "directory",
                            "parents": [
                                {
                                    "name": "__init__.py",
                                    "id": "ce7f8f98-f55f-40c4-971f-dc6479e43123",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__init__.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "__pycache__",
                                    "id": "945371ed-3314-4bf2-9ffa-2bf8fcfcb02e",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__",
                                    "type": "directory",
                                    "children": [
                                        {
                                            "name": "__init__.cpython-313.pyc",
                                            "id": "af64f0b3-c081-4630-8a8e-36fbb4c21e87",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__\\__init__.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "exceptions.cpython-313.pyc",
                                            "id": "c33d54e3-91b8-4c28-a3aa-881790d46e94",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__\\exceptions.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "logger.cpython-313.pyc",
                                            "id": "d8178756-26fe-45b3-b252-7ed2d5637fe6",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__\\logger.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "selector_generator.cpython-313.pyc",
                                            "id": "4e85c3f5-aa56-4330-aef0-f1a63a46fcd4",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__\\selector_generator.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        },
                                        {
                                            "name": "tab_refresh_helper.cpython-313.pyc",
                                            "id": "6a596c0e-684c-4ddb-b47f-a071d9c8c2f0",
                                            "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\__pycache__\\tab_refresh_helper.cpython-313.pyc",
                                            "type": "file",
                                            "category": []
                                        }
                                    ]
                                },
                                {
                                    "name": "clear_icon_cache.py",
                                    "id": "0ffd4772-ed31-42c9-8af3-2d3120513594",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\clear_icon_cache.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "exceptions.py",
                                    "id": "0a33ed12-cadd-4607-8938-2a0be8b2cc8b",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\exceptions.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "logger.py",
                                    "id": "9104bfde-e687-4b1d-bb86-ff85b941ee77",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\logger.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "selector_generator.py",
                                    "id": "90358a22-788f-48a5-8928-1650faabc59b",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\selector_generator.py",
                                    "type": "file",
                                    "category": []
                                },
                                {
                                    "name": "tab_refresh_helper.py",
                                    "id": "3bff4d18-80aa-4ae1-af4f-cbc0c1d57fbf",
                                    "full_path": "C:/Users/Oracle/Documents\\liris\\utils\\tab_refresh_helper.py",
                                    "type": "file",
                                    "category": []
                                }
                            ],
                            "parent_labels": [],
                            "child_labels": []
                        }
                    ]
                }
            ]
        }
    }

    
    client_stub = pydgraph.DgraphClientStub(DGRAPH_ADDR)
    client = pydgraph.DgraphClient(client_stub)

    logger.info(f"Attempting to connect to Dgraph at {DGRAPH_ADDR}")
    
    # Step 1: Insert the ontology hierarchy
    insert_hierarchy(client, PROJECT_DATA)

if __name__ == '__main__':
    main()
