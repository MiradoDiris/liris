# test_dgraph_direct.py
# Testez ce script pour voir ce que Dgraph retourne vraiment

import json
from utils.dgraph_connector import LirisDgraphConnector

def test_dgraph_queries():
    """Test toutes les méthodes possibles de récupération"""
    
    connector = LirisDgraphConnector()
    
    if not connector.client:
        print("❌ Pas de connexion Dgraph")
        return
    
    print("\n" + "="*80)
    print("🔍 TEST 1 : Query workspaces via query_workspaces()")
    print("="*80)
    
    # Méthode 1 : Via query_workspaces du connector
    result1 = connector.query_workspaces()
    
    if result1 and 'q' in result1:
        workspaces = result1['q']
        print(f"✅ {len(workspaces)} workspace(s) trouvé(s)")
        
        for ws in workspaces:
            ws_name = ws.get('name')
            cm = ws.get('clusterManagement', {})
            clusters = cm.get('clusters', [])
            
            print(f"\n📦 Workspace: {ws_name}")
            print(f"   Clusters: {len(clusters)}")
            
            # Compter les labels
            total_labels = 0
            clusters_with_labels = 0
            
            for cluster in clusters:
                cluster_name = cluster.get('name')
                
                # Vérifier les 2 méthodes
                labels_direct = cluster.get('labels', [])
                labels_reverse = cluster.get('root_labels', [])  # ~clusters devient root_labels
                
                has_labels = len(labels_direct) > 0 or len(labels_reverse) > 0
                
                if has_labels:
                    clusters_with_labels += 1
                    total_labels += len(labels_direct) + len(labels_reverse)
                
                print(f"   - {cluster_name}: "
                      f"labels_direct={len(labels_direct)}, "
                      f"labels_reverse={len(labels_reverse)}")
            
            print(f"\n📊 Statistiques:")
            print(f"   Total clusters: {len(clusters)}")
            print(f"   Clusters avec labels: {clusters_with_labels}")
            print(f"   Total labels: {total_labels}")
    
    print("\n" + "="*80)
    print("🔍 TEST 2 : Query clusters directs (sans workspace)")
    print("="*80)
    
    query2 = """
    {
      q(func: type(Cluster)) {
        uid
        name
        id
        nodeType
        
        # Essayer les 2 méthodes
        labels_method1: labels @filter(eq(level, 0)) {
          uid
          name
        }
        
        labels_method2: ~clusters @filter(eq(level, 0)) {
          uid
          name
        }
      }
    }
    """
    
    txn = connector.client.txn(read_only=True)
    resp = txn.query(query2)
    txn.discard()
    
    result2 = connector._parse_response(resp)
    clusters = result2.get('q', [])
    
    print(f"✅ {len(clusters)} clusters trouvés directement")
    
    with_method1 = 0
    with_method2 = 0
    
    for cluster in clusters[:10]:  # Afficher les 10 premiers
        name = cluster.get('name')
        m1 = len(cluster.get('labels_method1', []))
        m2 = len(cluster.get('labels_method2', []))
        
        if m1 > 0:
            with_method1 += 1
        if m2 > 0:
            with_method2 += 1
        
        print(f"   - {name}: method1={m1}, method2={m2}")
    
    print(f"\n📊 Statistiques:")
    print(f"   Clusters avec labels (method1 'labels'): {with_method1}")
    print(f"   Clusters avec labels (method2 '~clusters'): {with_method2}")
    
    print("\n" + "="*80)
    print("🔍 TEST 3 : Compter tous les labels niveau 0")
    print("="*80)
    
    query3 = """
    {
      q(func: type(Label)) @filter(eq(level, 0)) {
        uid
        name
        label
        level
        
        # Cluster parent
        parent_cluster: clusters {
          uid
          name
        }
      }
    }
    """
    
    txn = connector.client.txn(read_only=True)
    resp = txn.query(query3)
    txn.discard()
    
    result3 = connector._parse_response(resp)
    labels = result3.get('q', [])
    
    print(f"✅ {len(labels)} labels niveau 0 trouvés")
    
    # Grouper par cluster parent
    by_cluster = {}
    for label in labels:
        parent = label.get('parent_cluster')
        if parent:
            cluster_name = parent[0].get('name') if isinstance(parent, list) else parent.get('name')
            if cluster_name not in by_cluster:
                by_cluster[cluster_name] = []
            by_cluster[cluster_name].append(label.get('name'))
    
    print(f"\n📦 Répartition par cluster:")
    for cluster_name, label_names in list(by_cluster.items())[:10]:
        print(f"   {cluster_name}: {len(label_names)} labels")
    
    print("\n" + "="*80)
    print("🔍 RÉSUMÉ ET RECOMMANDATIONS")
    print("="*80)
    
    print("\n💡 Pour corriger taxonomy_dialog.py :")
    
    if with_method1 > with_method2:
        print("   → Utiliser : labels @filter(eq(level, 0))")
    elif with_method2 > with_method1:
        print("   → Utiliser : ~clusters @filter(eq(level, 0))")
    else:
        print("   → Les deux méthodes retournent le même nombre")
    
    print(f"\n📊 Données disponibles:")
    print(f"   Total clusters: {len(clusters)}")
    print(f"   Total labels niveau 0: {len(labels)}")
    
    if len(labels) < len(clusters):
        print(f"\n⚠️ ATTENTION: {len(clusters) - len(labels)} clusters SANS labels!")
        print("   → Il faut gérer les clusters sans labels séparément")
    
    connector.close()

if __name__ == '__main__':
    test_dgraph_queries()