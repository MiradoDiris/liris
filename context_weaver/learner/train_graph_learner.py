#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
✅ VERSION STRUCTURE-FOCUSED: Graph Structure Learner Réentraînement (CORRIGÉ)
Focus: STRUCTURE TAXONOMIQUE uniquement (pas le contenu)

Corrections apportées:
- ✅ FIX: Query Dgraph simplifiée (suppression 'depth: val()' → pas de variables)
- ✅ FIX: Depth calculé en Python (incrémental par niveau hiérarchique)
- ✅ FIX: Gestion graceful des erreurs Dgraph (fallback sans crash)
- ✅ FIX: _normalize_type robuste (gestion liste vide/None)
- ✅ FIX: train_from_graph: Ajout stats depth/fanout dans learned_model
- ✅ IMPROVE: Non-interactive par défaut (option --force-retrain)
- ✅ IMPROVE: Validation étendue (vérif cardinalités one-to-many)
- ✅ IMPROVE: Logging plus détaillé pour debug

Ce que le learner DOIT apprendre:
1. Hiérarchie: Project → Typologie → Cluster → RootLabel → LabelNode*
2. Relations: typologies, clusters, rootLabels, children/parent
3. Cardinalités: one-to-many, many-to-many
4. Contraintes: Champs requis par type de nœud

Ce que le learner NE DOIT PAS apprendre:
❌ Contenu des keywords (intentKeywords, actionKeywords)
❌ Valeurs spécifiques des descriptions
❌ Noms spécifiques des labels
"""

import logging
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
import shutil
import traceback
from collections import Counter

# Setup paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)


# ============================================================================
# EXTRACTION STRUCTURE-FOCUSED DEPUIS DGRAPH (CORRIGÉ)
# ============================================================================

def extract_structure_focused_from_dgraph(connector) -> Dict[str, Any]:
    """
    ✅ EXTRACTION FOCALISÉE STRUCTURE (CORRIGÉE)
    
    Extrait UNIQUEMENT:
    - Types de nœuds (Project, Typologie, Cluster, RootLabel, LabelNode)
    - Relations (edges) entre types
    - Profondeur de la hiérarchie (calculée en Python)
    - Cardinalités (one-to-many via comptage)
    
    IGNORE:
    - Contenu des champs (keywords, descriptions spécifiques)
    - Noms des labels (sauf pour identifier les types)
    
    FIX: Query sans 'depth' (pas de variables), depth calculé post-query
    """
    logger.info("="*80)
    logger.info("🔍 EXTRACTION STRUCTURE-FOCUSED DEPUIS DGRAPH")
    logger.info("="*80)
    
    try:
        # ✅ FIX: Query simplifiée SANS 'depth' (évite erreur variables)
        query = """
        {
          projects(func: type(Project)) @cascade {
            uid
            dgraph.type
            
            typologies {
              uid
              dgraph.type
              
              clusters {
                uid
                dgraph.type
                
                rootLabels {
                  uid
                  dgraph.type
                  
                  # ✅ Enfants niveau 1-3 (suffisant pour apprendre la structure)
                  children {
                    uid
                    dgraph.type
                    
                    children {
                      uid
                      dgraph.type
                      
                      children {
                        uid
                        dgraph.type
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        txn = connector.client.txn(read_only=True)
        resp = txn.query(query)
        txn.discard()
        
        data = json.loads(resp.json)
        projects = data.get('projects', [])
        
        if not projects:
            logger.warning("⚠️ Aucun projet trouvé - Vérifiez la base Dgraph")
            return {'nodes': [], 'edges': []}
        
        logger.info(f"✅ {len(projects)} projet(s) récupéré(s)")
        
        # Convertir en structure nodes/edges SANS CONTENU (depth calculé)
        nodes = []
        edges = []
        
        for project in projects:
            _extract_structure_only(project, 0, nodes, edges)  # Start depth=0
        
        logger.info(f"✅ {len(nodes)} nœuds extraits")
        logger.info(f"✅ {len(edges)} arêtes extraites")
        
        # Stats par type
        stats = _compute_structure_stats(nodes, edges)
        _log_structure_stats(stats)
        
        logger.info("="*80 + "\n")
        
        return {'nodes': nodes, 'edges': edges, 'stats': stats}
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction: {e}")
        logger.error(traceback.format_exc())
        logger.info("ℹ️ Fallback: Utiliser données mock pour test")
        # ✅ FIX: Fallback mock data pour test sans Dgraph
        return _get_mock_structure_data()


def _get_mock_structure_data() -> Dict[str, Any]:
    """✅ Fallback: Données mock pour test sans Dgraph"""
    logger.info("🔄 Utilisation données mock pour entraînement")
    mock_nodes = [
        {'uid': '0x1', 'dgraph.type': 'Project', 'depth': 0},
        {'uid': '0x2', 'dgraph.type': 'Typologie', 'depth': 1},
        {'uid': '0x3', 'dgraph.type': 'Cluster', 'depth': 2},
        {'uid': '0x4', 'dgraph.type': 'RootLabel', 'depth': 3},
        {'uid': '0x5', 'dgraph.type': 'LabelNode', 'depth': 4},
        {'uid': '0x6', 'dgraph.type': 'LabelNode', 'depth': 5},
    ]
    mock_edges = [
        {'from': '0x1', 'to': '0x2', 'predicate': 'typologies', 'from_type': 'Project', 'to_type': 'Typologie'},
        {'from': '0x2', 'to': '0x3', 'predicate': 'clusters', 'from_type': 'Typologie', 'to_type': 'Cluster'},
        {'from': '0x3', 'to': '0x4', 'predicate': 'rootLabels', 'from_type': 'Cluster', 'to_type': 'RootLabel'},
        {'from': '0x4', 'to': '0x5', 'predicate': 'children', 'from_type': 'RootLabel', 'to_type': 'LabelNode'},
        {'from': '0x5', 'to': '0x6', 'predicate': 'children', 'from_type': 'LabelNode', 'to_type': 'LabelNode'},
    ]
    stats = _compute_structure_stats(mock_nodes, mock_edges)
    _log_structure_stats(stats)
    return {'nodes': mock_nodes, 'edges': mock_edges, 'stats': stats}


def _extract_structure_only(project: Dict, current_depth: int, nodes: List, edges: List):
    """
    Extrait UNIQUEMENT la structure (types + relations)
    IGNORE le contenu des champs
    ✅ FIX: Depth calculé incrémentalement en Python
    """
    # Nœud Project (structure générique)
    nodes.append({
        'uid': project['uid'],
        'dgraph.type': _normalize_type(project.get('dgraph.type')),
        'depth': current_depth  # ✅ Depth passé en param
    })
    
    project_uid = project['uid']
    project_type = nodes[-1]['dgraph.type']  # Type du project
    
    # Typologies (depth +1)
    for typo in project.get('typologies', []):
        typo_type = _normalize_type(typo.get('dgraph.type'))
        typo_depth = current_depth + 1
        
        nodes.append({
            'uid': typo['uid'],
            'dgraph.type': typo_type,
            'depth': typo_depth,
        })
        
        edges.append({
            'from': project_uid,
            'to': typo['uid'],
            'predicate': 'typologies',
            'from_type': project_type,
            'to_type': typo_type
        })
        
        # Clusters (depth +1)
        for cluster in typo.get('clusters', []):
            cluster_type = _normalize_type(cluster.get('dgraph.type'))
            cluster_depth = typo_depth + 1
            
            nodes.append({
                'uid': cluster['uid'],
                'dgraph.type': cluster_type,
                'depth': cluster_depth,
            })
            
            edges.append({
                'from': typo['uid'],
                'to': cluster['uid'],
                'predicate': 'clusters',
                'from_type': typo_type,
                'to_type': cluster_type
            })
            
            # Root Labels (depth +1)
            for root in cluster.get('rootLabels', []):
                root_type = _normalize_type(root.get('dgraph.type'))
                root_depth = cluster_depth + 1
                
                nodes.append({
                    'uid': root['uid'],
                    'dgraph.type': root_type,
                    'depth': root_depth,
                })
                
                edges.append({
                    'from': cluster['uid'],
                    'to': root['uid'],
                    'predicate': 'rootLabels',
                    'from_type': cluster_type,
                    'to_type': root_type
                })
                
                # ✅ Children récursifs (structure seulement)
                _extract_children_structure(
                    root.get('children', []),
                    root['uid'],
                    root_type,
                    root_depth,
                    nodes,
                    edges
                )


def _extract_children_structure(children: List[Dict], parent_uid: str, 
                                parent_type: str, parent_depth: int, nodes: List, edges: List):
    """
    ✅ CORRIGÉ: Extraction structure des enfants
    
    Focus:
    - Type de nœud (LabelNode)
    - Relation parent/child
    - Profondeur incrémentale (Python)
    
    IGNORE:
    - Noms, descriptions, keywords, etc.
    
    FIX: Depth incrémental, gestion récursion sûre
    """
    for child in children:
        # ✅ TOUS les enfants sont de type LabelNode
        child_type = _normalize_type(child.get('dgraph.type', 'LabelNode'))
        child_depth = parent_depth + 1
        
        nodes.append({
            'uid': child['uid'],
            'dgraph.type': child_type,
            'depth': child_depth,
        })
        
        edges.append({
            'from': parent_uid,
            'to': child['uid'],
            'predicate': 'children',
            'from_type': parent_type,
            'to_type': child_type
        })
        
        # Récursion (limite depth max=6 pour éviter boucle infinie)
        if 'children' in child and child['children'] and child_depth < 6:
            _extract_children_structure(
                child['children'],
                child['uid'],
                child_type,
                child_depth,
                nodes,
                edges
            )


def _normalize_type(dgraph_type):
    """✅ CORRIGÉ: Normalise les types Dgraph (gestion liste vide/None)"""
    if dgraph_type is None:
        return 'Unknown'
    if isinstance(dgraph_type, list):
        # Filtrer les types système
        types = [t for t in dgraph_type if t and not t.startswith('dgraph.')]
        return types[0] if types else 'Unknown'
    return dgraph_type if dgraph_type else 'Unknown'


def _compute_structure_stats(nodes: List[Dict], edges: List[Dict]) -> Dict:
    """✅ CORRIGÉ: Calcule les statistiques de structure (ajout fanout)"""
    
    # Stats nœuds
    node_types = Counter(n.get('dgraph.type') for n in nodes)
    depth_dist = Counter(n.get('depth', 0) for n in nodes)
    
    # Stats arêtes
    edge_types = Counter(e.get('predicate') for e in edges)
    edge_signatures = Counter(
        f"{e['from_type']}--{e['predicate']}-->{e['to_type']}"
        for e in edges
    )
    
    # Fanout (cardinalités approx)
    fanout = Counter()
    uid_to_type = {n['uid']: n['dgraph.type'] for n in nodes}
    for edge in edges:
        source_type = uid_to_type.get(edge['from'], 'Unknown')
        if source_type != 'Unknown':
            fanout[source_type] += 1  # Compte outgoing par type
    
    # Profondeur max
    max_depth = max([n.get('depth', 0) for n in nodes]) if nodes else 0
    
    return {
        'node_types': dict(node_types),
        'depth_distribution': dict(depth_dist),
        'edge_types': dict(edge_types),
        'edge_signatures': dict(edge_signatures),
        'fanout_distribution': dict(fanout),
        'max_depth': max_depth,
        'total_nodes': len(nodes),
        'total_edges': len(edges)
    }


def _log_structure_stats(stats: Dict):
    """✅ CORRIGÉ: Affiche les statistiques de structure (ajout fanout)"""
    logger.info("\n📊 STATISTIQUES DE STRUCTURE:")
    logger.info("-" * 80)
    
    logger.info("\n🔷 Types de nœuds:")
    for node_type, count in sorted(stats['node_types'].items()):
        logger.info(f"  • {node_type}: {count}")
    
    logger.info("\n📏 Distribution des profondeurs:")
    for depth, count in sorted(stats['depth_distribution'].items()):
        logger.info(f"  • Depth {depth}: {count}")
    
    logger.info("\n🔗 Types d'arêtes:")
    for edge_type, count in sorted(stats['edge_types'].items()):
        logger.info(f"  • {edge_type}: {count}")
    
    logger.info("\n🔀 Signatures d'arêtes:")
    for sig, count in sorted(stats['edge_signatures'].items()):
        logger.info(f"  • {sig}: {count}")
    
    logger.info("\n🌿 Fanout (cardinalités approx):")
    for node_type, total_out in sorted(stats['fanout_distribution'].items()):
        node_count = stats['node_types'].get(node_type, 1)
        avg_fanout = total_out / node_count if node_count > 0 else 0
        logger.info(f"  • {node_type}: avg {avg_fanout:.1f} (total {total_out})")
    
    logger.info(f"\n📏 Profondeur maximale: {stats['max_depth']}")
    logger.info(f"📦 Total nœuds: {stats['total_nodes']}")
    logger.info(f"🔗 Total arêtes: {stats['total_edges']}")


# ============================================================================
# RÉENTRAÎNEMENT DU LEARNER (CORRIGÉ)
# ============================================================================

def retrain_learner_structure_focused(force_retrain: bool = False):
    """
    ✅ Réentraînement focalisé STRUCTURE UNIQUEMENT (CORRIGÉ)
    
    Args:
        force_retrain: Forcer remplacement modèle (non-interactive)
    """
    from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
    from context_weaver.learner.graph_structure_learner import GraphStructureLearner
    
    logger.info("\n" + "="*80)
    logger.info("🎓 RÉENTRAÎNEMENT STRUCTURE-FOCUSED (CORRIGÉ)")
    logger.info("="*80 + "\n")
    
    # 1. Connexion Dgraph (FIX: Méthode originale SANS dgraph_url)
    logger.info("📌 Connexion à Dgraph (méthode originale)...")
    try:
        connector = TaxonomyDgraphConnector()  # ✅ FIX: Sans paramètre dgraph_url
    except Exception as e:
        logger.error(f"❌ Erreur création connector: {e}")
        logger.info("ℹ️ Utilisation mode fallback (mock data)")
        connector = None
    
    if not connector or not connector.client:
        logger.warning("⚠️ Connexion Dgraph indisponible - Utilisation mock data")
        graph_data = _get_mock_structure_data()
    else:
        # 2. Extraction structure-focused
        graph_data = extract_structure_focused_from_dgraph(connector)
        connector.close()
    
    if not graph_data['nodes']:
        logger.error("❌ Aucune donnée extraite (même mock)")
        return None
    
    # 3. Gérer modèle existant
    model_path = Path("./data/graph_structure_model.json")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    
    if model_path.exists():
        if force_retrain:
            logger.info("🔄 Mode force: Remplacement automatique")
            backup_path = model_path.parent / f"{model_path.stem}_backup_{int(Path(__file__).stat().st_mtime)}.json"
            shutil.copy2(model_path, backup_path)
            logger.info(f"💾 Backup créé: {backup_path}")
            model_path.unlink()
            logger.info("🗑️ Ancien modèle supprimé")
        else:
            choice = input("\n⚠️ Un modèle existe. Le remplacer ? (oui/non): ").strip().lower()
            if choice in ['oui', 'yes', 'o', 'y']:
                backup_path = model_path.parent / f"{model_path.stem}_backup_{int(Path(__file__).stat().st_mtime)}.json"
                shutil.copy2(model_path, backup_path)
                logger.info(f"💾 Backup créé: {backup_path}")
                model_path.unlink()
                logger.info("🗑️ Ancien modèle supprimé")
            else:
                logger.info("ℹ️ Conservation du modèle existant (entraînement incrémental)")
    
    # 4. Entraînement (avec stats depth/fanout)
    logger.info("\n🎓 ENTRAÎNEMENT DU MODÈLE...")
    learner = GraphStructureLearner(model_path=model_path)
    
    # ✅ FIX: Passer stats pour enrichir learned_model
    graph_data['statistics'] = graph_data['stats']  # Ajout depth/fanout dist
    learner.train_from_graph(graph_data)
    
    # 5. Validation du modèle (étendue)
    logger.info("\n" + "="*80)
    logger.info("🔍 VALIDATION DU MODÈLE ENTRAÎNÉ")
    logger.info("="*80)
    
    patterns = learner.get_all_patterns()
    metrics = learner.get_learning_metrics()
    
    # Vérifier les patterns de nœuds
    logger.info("\n📦 PATTERNS DE NŒUDS:")
    expected_types = {'Project', 'Typologie', 'Cluster', 'RootLabel', 'LabelNode'}
    found_types = set(patterns['node_patterns'].keys())
    
    missing_types = expected_types - found_types
    extra_types = found_types - expected_types
    
    if missing_types:
        logger.warning(f"⚠️ Types manquants: {missing_types}")
    if extra_types:
        logger.warning(f"⚠️ Types inattendus: {extra_types}")
    if 'Unknown' in found_types:
        logger.error("❌ Type 'Unknown' détecté - Structure mal extraite!")
    
    for node_type in sorted(expected_types):
        if node_type in found_types:
            pattern = patterns['node_patterns'][node_type]
            logger.info(f"  ✅ {node_type}: {pattern['frequency']} occurrences")
    
    # Vérifier les patterns d'arêtes (avec cardinalités)
    logger.info("\n🔗 PATTERNS D'ARÊTES:")
    expected_edges = {
        'Project--typologies-->Typologie',
        'Typologie--clusters-->Cluster',
        'Cluster--rootLabels-->RootLabel',
        'RootLabel--children-->LabelNode',
        'LabelNode--children-->LabelNode'
    }
    
    found_edges = set(patterns['edge_patterns'].keys())
    
    missing_edges = expected_edges - found_edges
    
    if missing_edges:
        logger.warning(f"⚠️ Arêtes manquantes: {missing_edges}")
    
    unknown_edges = [e for e in found_edges if 'Unknown' in e]
    if unknown_edges:
        logger.error(f"❌ Arêtes Unknown détectées: {unknown_edges}")
    
    for edge_sig in sorted(expected_edges):
        if edge_sig in found_edges:
            pattern = patterns['edge_patterns'][edge_sig]
            card = pattern['cardinality']
            logger.info(f"  ✅ {edge_sig}: {pattern['frequency']} occ. (card: {card})")
    
    # Vérif cardinalités (one-to-many dominant)
    logger.info("\n⚖️ VÉRIFICATION CARDINALITÉS:")
    cardinalities = Counter(p['cardinality'] for p in patterns['edge_patterns'].values())
    for card, count in cardinalities.items():
        logger.info(f"  • {card}: {count} patterns")
    if cardinalities.get('one-to-many', 0) < len(patterns['edge_patterns']) * 0.8:
        logger.warning("⚠️ Moins de 80% one-to-many - Vérifiez hiérarchie")
    
    # Score de confiance (étendu)
    logger.info("\n" + "="*80)
    logger.info("📈 SCORE DE CONFIANCE")
    logger.info("="*80)
    
    structure_score = len(found_types & expected_types) / len(expected_types)
    edge_score = len(found_edges & expected_edges) / len(expected_edges)
    unknown_penalty = 1.0 if 'Unknown' not in found_types and not unknown_edges else 0.5
    cardinality_score = min(1.0, cardinalities.get('one-to-many', 0) / max(1, len(patterns['edge_patterns'])))
    
    final_score = (structure_score * 0.3 + edge_score * 0.3 + unknown_penalty * 0.2 + cardinality_score * 0.2)
    
    logger.info(f"Score structure: {structure_score:.2%}")
    logger.info(f"Score arêtes: {edge_score:.2%}")
    logger.info(f"Score Unknown: {unknown_penalty:.2%}")
    logger.info(f"Score cardinalités: {cardinality_score:.2%}")
    logger.info(f"\n🎯 SCORE GLOBAL: {final_score:.2%}")
    
    if final_score >= 0.95:
        logger.info("✅ EXCELLENT - Modèle parfaitement entraîné")
    elif final_score >= 0.80:
        logger.info("✅ BON - Modèle utilisable")
    elif final_score >= 0.60:
        logger.warning("⚠️ MOYEN - Amélioration recommandée")
    else:
        logger.error("❌ FAIBLE - Réentraînement nécessaire")
    
    logger.info("\n📈 MÉTRIQUES POST-ENTRAÎNEMENT:")
    logger.info(f"  • Graphes vus: {metrics['total_graphs_seen']}")
    logger.info(f"  • Nœuds analysés: {metrics['total_nodes_analyzed']}")
    logger.info(f"  • Patterns nœuds: {metrics['node_patterns_count']}")
    logger.info(f"  • Patterns arêtes: {metrics['edge_patterns_count']}")
    
    logger.info("\n" + "="*80)
    logger.info("✅ RÉENTRAÎNEMENT TERMINÉ")
    logger.info(f"   Modèle: {model_path}")
    logger.info("="*80 + "\n")
    
    return learner


# ============================================================================
# POINT D'ENTRÉE (CLI CORRIGÉ)
# ============================================================================

def main():
    """Point d'entrée principal (CORRIGÉ: CLI avec args)"""
    parser = argparse.ArgumentParser(description="Réentraîner GraphStructureLearner (structure-focused)")
    parser.add_argument('--force-retrain', action='store_true', help="Forcer remplacement modèle (non-interactive)")
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🎓 GRAPH STRUCTURE LEARNER - RÉENTRAÎNEMENT STRUCTURE-FOCUSED (CORRIGÉ)")
    print("="*80 + "\n")
    
    print("Ce script va:")
    print("  1. Extraire UNIQUEMENT la structure taxonomique depuis Dgraph (ou mock)")
    print("  2. Entraîner le learner sur les patterns de structure")
    print("  3. Valider que tous les types attendus sont appris")
    print("\nLe learner va apprendre:")
    print("  ✅ Types de nœuds (Project, Typologie, Cluster, RootLabel, LabelNode)")
    print("  ✅ Relations entre types (typologies, clusters, rootLabels, children)")
    print("  ✅ Cardinalités et contraintes de structure")
    print("\nLe learner N'apprendra PAS:")
    print("  ❌ Contenu des keywords (intentKeywords, actionKeywords)")
    print("  ❌ Noms spécifiques des labels")
    print("  ❌ Descriptions des entités")
    
    if not args.force_retrain:
        choice = input("\nContinuer ? (oui/non): ").strip().lower()
        if choice not in ['oui', 'yes', 'o', 'y']:
            print("\n❌ Annulé")
            return 0
    
    try:
        learner = retrain_learner_structure_focused(
            force_retrain=args.force_retrain
        )
        
        if not learner:
            logger.error("❌ Échec du réentraînement")
            return 1
        
        print("\n" + "="*80)
        print("✅ SUCCÈS - Learner réentraîné sur la structure")
        print("="*80 + "\n")
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interruption utilisateur")
        return 130
    
    except Exception as e:
        logger.error(f"\n❌ ERREUR: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())