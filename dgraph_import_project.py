
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
            "id": cluster_unique_id, # Used by @upsert to find/create
            "name": cluster_name,
            "userId": USER_ID, # Corrected to userId
            "createdAt": datetime.now().isoformat() + "Z", # Add creation timestamp
            "updatedAt": datetime.now().isoformat() + "Z", # Add update timestamp
        }
        mutations.append(cluster_mutation)
        
        all_cluster_blank_uids_for_workspace.append({"uid": cluster_blank_uid})
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
            "clusters": all_cluster_blank_uids_for_workspace # Links to all prepared clusters
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
            label_node["clusters"] = [{"uid": containing_cluster_blank_uid}]
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
            children_list_key = "parent_labels" 
        elif level_numeric == 1: # Parent level
            children_list_key = "child_labels"
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

        assigned = txn.mutate(set_json=mutations)
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
        "name": "kakarote",
        "turing_ontology": {
            "cluster": [
                "deuxième_dossier",
                "mutation_example.py",
                "premier_dossier"
            ],
            "clusters_detailed": [
                {
                    "name": "deuxième_dossier",
                    "id": "ef312bf4-bad8-4df7-a8ba-fbd5a032ede6",
                    "root_labels": []
                },
                {
                    "name": "mutation_example.py",
                    "id": "6ea5f9c4-219a-40c8-a5af-18f0da1f5e80",
                    "root_labels": []
                },
                {
                    "name": "premier_dossier",
                    "id": "0342f5ef-07a5-47bf-8b0a-4e5d616f0f9c",
                    "root_labels": [
                        {
                            "name": "AWS_architecture.png",
                            "id": "bce1b80b-b970-4147-a949-dfeef83461b5",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\AWS_architecture.png",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "Attestation_Stage_M1.jpg",
                            "id": "cfd61a1d-5dfb-415d-a219-b3c71e467546",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\Attestation_Stage_M1.jpg",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "hello_world.js",
                            "id": "adeaf476-34ff-41aa-b135-fa50e201d85b",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\hello_world.js",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "premier_label_racine",
                            "id": "044d1c2d-5434-44a5-ac2c-6766238ba583",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\premier_label_racine",
                            "type": "directory",
                            "parent_labels": [
                                {
                                    "name": "Attestation_Stage_M1.jpg",
                                    "id": "7940ed32-273e-4ed6-b4a9-8fd570c0b6c0",
                                    "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\premier_label_racine\\Attestation_Stage_M1.jpg",
                                    "type": "file",
                                    "category": [],
                                    "parent_labels": [],
                                    "child_labels": []
                                },
                                {
                                    "name": "test.py",
                                    "id": "d7b8d88a-0547-4556-8d08-a5a0972fee7f",
                                    "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\premier_label_racine\\test.py",
                                    "type": "file",
                                    "category": [],
                                    "parent_labels": [],
                                    "child_labels": []
                                }
                            ],
                            "child_labels": []
                        },
                        {
                            "name": "premier_script.py",
                            "id": "3c315b4d-46f8-49c0-a924-efeee113e171",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\premier_script.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "premier_script_mutation.py",
                            "id": "eb457d2d-1cd8-4aaf-adf5-69599c733536",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\premier_script_mutation.py",
                            "type": "file",
                            "category": [],
                            "parent_labels": [],
                            "child_labels": []
                        },
                        {
                            "name": "typescript.ts",
                            "id": "2a869f62-3cb4-4174-868d-c405cbb9eac2",
                            "full_path": "C:/Users/Ditrakely/Desktop/kakarote\\premier_dossier\\typescript.ts",
                            "type": "file",
                            "category": [],
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
