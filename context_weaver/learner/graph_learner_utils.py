#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilitaires pour analyser et visualiser les patterns du Graph Learner
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


# ============================================================================
# ANALYSE DES PATTERNS
# ============================================================================

def analyze_node_patterns(learner) -> Dict[str, Any]:
    """
    Analyse détaillée des patterns de nœuds
    
    Returns:
        Statistiques sur les patterns appris
    """
    patterns = learner.get_all_patterns()['node_patterns']
    
    analysis = {
        'total_types': len(patterns),
        'types_by_frequency': {},
        'avg_predicates_per_type': 0.0,
        'most_common_predicates': [],
        'required_fields_distribution': {}
    }
    
    # Trier par fréquence
    sorted_patterns = sorted(
        patterns.items(),
        key=lambda x: x[1]['frequency'],
        reverse=True
    )
    
    analysis['types_by_frequency'] = {
        k: v['frequency'] for k, v in sorted_patterns
    }
    
    # Prédicats moyens
    total_predicates = sum(len(p['predicates']) for p in patterns.values())
    analysis['avg_predicates_per_type'] = total_predicates / len(patterns) if patterns else 0
    
    # Prédicats les plus communs
    all_predicates = []
    for pattern in patterns.values():
        all_predicates.extend(pattern['predicates'])
    
    predicate_counts = Counter(all_predicates)
    analysis['most_common_predicates'] = predicate_counts.most_common(10)
    
    # Distribution des champs requis
    for node_type, pattern in patterns.items():
        analysis['required_fields_distribution'][node_type] = len(pattern['required_fields'])
    
    return analysis


def analyze_edge_patterns(learner) -> Dict[str, Any]:
    """Analyse des patterns d'arêtes"""
    patterns = learner.get_all_patterns()['edge_patterns']
    
    analysis = {
        'total_edge_types': len(patterns),
        'cardinality_distribution': Counter(),
        'most_frequent_edges': [],
        'source_target_pairs': []
    }
    
    # Distribution des cardinalités
    for pattern in patterns.values():
        analysis['cardinality_distribution'][pattern['cardinality']] += 1
    
    # Arêtes les plus fréquentes
    sorted_edges = sorted(
        patterns.items(),
        key=lambda x: x[1]['frequency'],
        reverse=True
    )
    
    analysis['most_frequent_edges'] = [
        (k, v['frequency']) for k, v in sorted_edges[:10]
    ]
    
    # Paires source-target
    for edge_sig, pattern in patterns.items():
        analysis['source_target_pairs'].append({
            'source': pattern['source_type'],
            'edge': pattern['edge_type'],
            'target': pattern['target_type'],
            'cardinality': pattern['cardinality']
        })
    
    return analysis


def analyze_constraints(learner) -> Dict[str, Any]:
    """Analyse des contraintes"""
    patterns = learner.get_all_patterns()
    constraints = patterns['constraints']
    
    analysis = {
        'total_constraints': len(constraints),
        'by_type': Counter(),
        'by_node_type': {}
    }
    
    for constraint in constraints:
        analysis['by_type'][constraint['constraint_type']] += 1
        
        node_type = constraint['applies_to']
        if node_type not in analysis['by_node_type']:
            analysis['by_node_type'][node_type] = []
        
        analysis['by_node_type'][node_type].append({
            'type': constraint['constraint_type'],
            'field': constraint['field']
        })
    
    return analysis


# ============================================================================
# RAPPORTS
# ============================================================================

def generate_text_report(learner, output_path: Path = None):
    """
    Génère un rapport texte complet
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sortie (optionnel)
    """
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("GRAPH STRUCTURE LEARNER - RAPPORT D'ANALYSE")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Métriques générales
    metrics = learner.get_learning_metrics()
    report_lines.append("📊 MÉTRIQUES GÉNÉRALES")
    report_lines.append("-" * 80)
    report_lines.append(f"Graphes vus: {metrics['total_graphs_seen']}")
    report_lines.append(f"Nœuds analysés: {metrics['total_nodes_analyzed']:,}")
    report_lines.append(f"Arêtes analysées: {metrics['total_edges_analyzed']:,}")
    report_lines.append(f"Dernière mise à jour: {metrics['last_training_date']}")
    report_lines.append(f"Itérations d'entraînement: {metrics['training_iterations']}")
    report_lines.append(f"Taux de succès: {metrics['success_rate']:.2%}")
    report_lines.append("")
    
    # Patterns de nœuds
    node_analysis = analyze_node_patterns(learner)
    report_lines.append("📦 PATTERNS DE NŒUDS")
    report_lines.append("-" * 80)
    report_lines.append(f"Types de nœuds: {node_analysis['total_types']}")
    report_lines.append(f"Prédicats moyens par type: {node_analysis['avg_predicates_per_type']:.1f}")
    report_lines.append("")
    
    report_lines.append("Types par fréquence:")
    for node_type, freq in list(node_analysis['types_by_frequency'].items())[:10]:
        report_lines.append(f"  • {node_type}: {freq}")
    report_lines.append("")
    
    report_lines.append("Prédicats les plus communs:")
    for pred, count in node_analysis['most_common_predicates']:
        report_lines.append(f"  • {pred}: {count}")
    report_lines.append("")
    
    # Patterns d'arêtes
    edge_analysis = analyze_edge_patterns(learner)
    report_lines.append("🔗 PATTERNS D'ARÊTES")
    report_lines.append("-" * 80)
    report_lines.append(f"Types d'arêtes: {edge_analysis['total_edge_types']}")
    report_lines.append("")
    
    report_lines.append("Distribution des cardinalités:")
    for card, count in edge_analysis['cardinality_distribution'].items():
        report_lines.append(f"  • {card}: {count}")
    report_lines.append("")
    
    report_lines.append("Arêtes les plus fréquentes:")
    for edge_sig, freq in edge_analysis['most_frequent_edges']:
        report_lines.append(f"  • {edge_sig}: {freq}")
    report_lines.append("")
    
    # Contraintes
    constraint_analysis = analyze_constraints(learner)
    report_lines.append("⚖️ CONTRAINTES")
    report_lines.append("-" * 80)
    report_lines.append(f"Total: {constraint_analysis['total_constraints']}")
    report_lines.append("")
    
    report_lines.append("Par type:")
    for constraint_type, count in constraint_analysis['by_type'].items():
        report_lines.append(f"  • {constraint_type}: {count}")
    report_lines.append("")
    
    # Footer
    report_lines.append("=" * 80)
    report_lines.append("FIN DU RAPPORT")
    report_lines.append("=" * 80)
    
    # Générer le texte
    report_text = "\n".join(report_lines)
    
    # Sauvegarder si chemin fourni
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"📄 Rapport sauvegardé: {output_path}")
    
    return report_text


def generate_json_report(learner, output_path: Path):
    """
    Génère un rapport JSON complet
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sortie
    """
    report = {
        'metrics': learner.get_learning_metrics(),
        'patterns': learner.get_all_patterns(),
        'analysis': {
            'nodes': analyze_node_patterns(learner),
            'edges': analyze_edge_patterns(learner),
            'constraints': analyze_constraints(learner)
        }
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Rapport JSON sauvegardé: {output_path}")


# ============================================================================
# VISUALISATIONS
# ============================================================================

def plot_node_type_distribution(learner, output_path: Path = None):
    """
    Graphique de distribution des types de nœuds
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sauvegarde (optionnel)
    """
    try:
        analysis = analyze_node_patterns(learner)
        
        # Prendre top 15
        types = list(analysis['types_by_frequency'].keys())[:15]
        frequencies = [analysis['types_by_frequency'][t] for t in types]
        
        # Plot
        plt.figure(figsize=(12, 6))
        plt.bar(range(len(types)), frequencies)
        plt.xticks(range(len(types)), types, rotation=45, ha='right')
        plt.xlabel('Type de nœud')
        plt.ylabel('Fréquence')
        plt.title('Distribution des types de nœuds')
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Graphique sauvegardé: {output_path}")
        else:
            plt.show()
        
        plt.close()
        
    except Exception as e:
        logger.error(f"Erreur génération graphique: {e}")


def plot_edge_cardinality(learner, output_path: Path = None):
    """
    Graphique des cardinalités d'arêtes
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sauvegarde (optionnel)
    """
    try:
        analysis = analyze_edge_patterns(learner)
        
        cardinalities = list(analysis['cardinality_distribution'].keys())
        counts = list(analysis['cardinality_distribution'].values())
        
        # Plot
        plt.figure(figsize=(8, 6))
        plt.pie(counts, labels=cardinalities, autopct='%1.1f%%', startangle=90)
        plt.title('Distribution des cardinalités d\'arêtes')
        plt.axis('equal')
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Graphique sauvegardé: {output_path}")
        else:
            plt.show()
        
        plt.close()
        
    except Exception as e:
        logger.error(f"Erreur génération graphique: {e}")


def plot_validation_history(learner, output_path: Path = None):
    """
    Graphique de l'historique de validation
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sauvegarde (optionnel)
    """
    try:
        history = learner.learned_model['validation_history']
        
        successes = len(history['successes'])
        failures = len(history['failures'])
        
        # Plot
        plt.figure(figsize=(8, 6))
        plt.bar(['Succès', 'Échecs'], [successes, failures], color=['green', 'red'])
        plt.ylabel('Nombre de validations')
        plt.title('Historique de validation')
        plt.grid(axis='y', alpha=0.3)
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Graphique sauvegardé: {output_path}")
        else:
            plt.show()
        
        plt.close()
        
    except Exception as e:
        logger.error(f"Erreur génération graphique: {e}")


# ============================================================================
# COMPARAISONS
# ============================================================================

def compare_patterns_over_time(learner_v1_path: Path, learner_v2_path: Path):
    """
    Compare deux versions du modèle pour voir l'évolution
    
    Args:
        learner_v1_path: Chemin du modèle version 1
        learner_v2_path: Chemin du modèle version 2
    """
    from graph_structure_learner import GraphStructureLearner
    
    learner_v1 = GraphStructureLearner(model_path=learner_v1_path)
    learner_v2 = GraphStructureLearner(model_path=learner_v2_path)
    
    metrics_v1 = learner_v1.get_learning_metrics()
    metrics_v2 = learner_v2.get_learning_metrics()
    
    print("=" * 80)
    print("COMPARAISON DES MODÈLES")
    print("=" * 80)
    
    print("\nMÉTRIQUES:")
    for key in metrics_v1.keys():
        v1_val = metrics_v1.get(key, 0)
        v2_val = metrics_v2.get(key, 0)
        
        if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)):
            diff = v2_val - v1_val
            print(f"  {key}:")
            print(f"    V1: {v1_val}")
            print(f"    V2: {v2_val}")
            print(f"    Δ:  {diff:+}")
    
    print("\nPATTERNS:")
    print(f"  Node patterns:")
    print(f"    V1: {metrics_v1['node_patterns_count']}")
    print(f"    V2: {metrics_v2['node_patterns_count']}")
    print(f"    Δ:  {metrics_v2['node_patterns_count'] - metrics_v1['node_patterns_count']:+}")
    
    print(f"  Edge patterns:")
    print(f"    V1: {metrics_v1['edge_patterns_count']}")
    print(f"    V2: {metrics_v2['edge_patterns_count']}")
    print(f"    Δ:  {metrics_v2['edge_patterns_count'] - metrics_v1['edge_patterns_count']:+}")


# ============================================================================
# EXPORT
# ============================================================================

def export_patterns_to_schema(learner, output_path: Path):
    """
    Exporte les patterns en format schema Dgraph
    
    Args:
        learner: Instance du GraphStructureLearner
        output_path: Chemin de sortie
    """
    patterns = learner.get_all_patterns()
    
    schema_lines = []
    schema_lines.append("# Schema généré depuis Graph Structure Learner")
    schema_lines.append("# Date: " + str(Path(__file__).stat().st_mtime))
    schema_lines.append("")
    
    # Types
    for node_type, pattern in patterns['node_patterns'].items():
        schema_lines.append(f"type {node_type} {{")
        
        for field in pattern['required_fields']:
            schema_lines.append(f"  {field}")
        
        schema_lines.append("}")
        schema_lines.append("")
    
    # Prédicats
    all_predicates = set()
    for pattern in patterns['node_patterns'].values():
        all_predicates.update(pattern['predicates'])
    
    for predicate in sorted(all_predicates):
        schema_lines.append(f"{predicate}: string .")
    
    schema_text = "\n".join(schema_lines)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(schema_text)
    
    logger.info(f"📄 Schema exporté: {output_path}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python graph_learner_utils.py <command> [args]")
        print("\nCommandes disponibles:")
        print("  report <model_path>           - Génère un rapport texte")
        print("  json <model_path> <output>    - Génère un rapport JSON")
        print("  plot <model_path> <output>    - Génère des graphiques")
        print("  compare <model1> <model2>     - Compare deux modèles")
        print("  schema <model_path> <output>  - Exporte en schema Dgraph")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "report":
        from graph_structure_learner import GraphStructureLearner
        
        model_path = Path(sys.argv[2])
        learner = GraphStructureLearner(model_path=model_path)
        
        report = generate_text_report(learner)
        print(report)
    
    elif command == "json":
        from graph_structure_learner import GraphStructureLearner
        
        model_path = Path(sys.argv[2])
        output_path = Path(sys.argv[3])
        
        learner = GraphStructureLearner(model_path=model_path)
        generate_json_report(learner, output_path)
    
    elif command == "plot":
        from graph_structure_learner import GraphStructureLearner
        
        model_path = Path(sys.argv[2])
        output_dir = Path(sys.argv[3])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        learner = GraphStructureLearner(model_path=model_path)
        
        plot_node_type_distribution(learner, output_dir / "node_distribution.png")
        plot_edge_cardinality(learner, output_dir / "edge_cardinality.png")
        plot_validation_history(learner, output_dir / "validation_history.png")
    
    elif command == "compare":
        model1_path = Path(sys.argv[2])
        model2_path = Path(sys.argv[3])
        
        compare_patterns_over_time(model1_path, model2_path)
    
    elif command == "schema":
        from graph_structure_learner import GraphStructureLearner
        
        model_path = Path(sys.argv[2])
        output_path = Path(sys.argv[3])
        
        learner = GraphStructureLearner(model_path=model_path)
        export_patterns_to_schema(learner, output_path)
    
    else:
        print(f"Commande inconnue: {command}")
        sys.exit(1)