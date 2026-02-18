#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'entraînement du Neural Graph Learner

✅ Pipeline complet:
1. Extraction des données depuis Dgraph
2. Enrichissement avec parent_uid
3. Construction des vocabulaires
4. Création du dataset avec augmentation
5. Entraînement avec validation
6. Sauvegarde du modèle
"""

import logging
import torch
from pathlib import Path
from typing import Dict, Any

# Imports locaux
from context_weaver.learner.neural import (
    NeuralConfig,
    GraphFeatureExtractor,
    GraphStructureDataset,
    NeuralGraphLearnerTrainer
)
from context_weaver.learner.neural.feature_extractor import enrich_nodes_with_parent_info

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_graph_from_dgraph(connector) -> Dict[str, Any]:
    """
    Extrait le graphe complet depuis Dgraph
    
    Returns:
        {
            'nodes': [...],
            'edges': [...]
        }
    """
    logger.info("📥 Extraction du graphe depuis Dgraph...")
    
    # Query pour récupérer nœuds avec profondeur
    query = """
    {
        nodes(func: has(dgraph.type)) @cascade {
            uid
            dgraph.type
            name
            definition
            expand(_all_) {
                uid
            }
        }
    }
    """
    
    result = connector.query(query)
    nodes = result.get('nodes', [])
    
    logger.info(f"   • Nœuds extraits: {len(nodes)}")
    
    # Calculer profondeurs (BFS depuis racines)
    nodes_with_depth = _compute_depths(nodes)
    
    # Extraire arêtes
    edges = _extract_edges(nodes_with_depth)
    
    logger.info(f"   • Arêtes extraites: {len(edges)}")
    
    return {
        'nodes': nodes_with_depth,
        'edges': edges
    }


def _compute_depths(nodes):
    """Calcule la profondeur de chaque nœud (BFS)"""
    from collections import deque
    
    # Construire adjacency
    uid_to_node = {n['uid']: n for n in nodes}
    parent_to_children = {}
    
    for node in nodes:
        for key, value in node.items():
            if isinstance(value, list) and key not in ['dgraph.type', 'name']:
                for child in value:
                    if isinstance(child, dict) and 'uid' in child:
                        child_uid = child['uid']
                        if node['uid'] not in parent_to_children:
                            parent_to_children[node['uid']] = []
                        parent_to_children[node['uid']].append(child_uid)
    
    # BFS pour calculer depth
    depths = {}
    queue = deque()
    
    # Trouver racines (pas de parent)
    all_children = set()
    for children in parent_to_children.values():
        all_children.update(children)
    
    roots = [uid for uid in uid_to_node.keys() if uid not in all_children]
    
    for root in roots:
        queue.append((root, 0))
        depths[root] = 0
    
    while queue:
        uid, depth = queue.popleft()
        
        for child_uid in parent_to_children.get(uid, []):
            if child_uid not in depths:
                depths[child_uid] = depth + 1
                queue.append((child_uid, depth + 1))
    
    # Ajouter depth aux nœuds
    for node in nodes:
        node['depth'] = depths.get(node['uid'], 0)
    
    return nodes


def _extract_edges(nodes):
    """Extrait les arêtes parent-enfant"""
    edges = []
    
    for node in nodes:
        parent_uid = node['uid']
        
        for key, value in node.items():
            if isinstance(value, list) and key not in ['dgraph.type', 'name']:
                for child in value:
                    if isinstance(child, dict) and 'uid' in child:
                        edges.append({
                            'from': parent_uid,
                            'to': child['uid'],
                            'predicate': key,
                            'edge_type': 'parent_child'
                        })
    
    return edges


def train_neural_learner(
    graph_data: Dict[str, Any],
    config: NeuralConfig = None,
    save_path: Path = None
):
    """
    🎓 Entraîne le Neural Graph Learner
    
    Args:
        graph_data: Données du graphe
        config: Configuration (par défaut: NeuralConfig())
        save_path: Chemin de sauvegarde (par défaut: ./data/neural_graph_model.pt)
    """
    logger.info("=" * 80)
    logger.info("🎓 ENTRAÎNEMENT NEURAL GRAPH LEARNER")
    logger.info("=" * 80)
    
    # Configuration
    config = config or NeuralConfig.small()
    save_path = save_path or Path("./data/neural_graph_model.pt")
    
    logger.info(f"📋 Configuration:")
    logger.info(f"   • Embed dim: {config.node_embed_dim}")
    logger.info(f"   • Transformer layers: {config.num_transformer_layers}")
    logger.info(f"   • Attention heads: {config.num_attention_heads}")
    logger.info(f"   • Batch size: {config.batch_size}")
    logger.info(f"   • Max epochs: {config.max_epochs}")
    
    # 1. Enrichir avec parent_uid
    logger.info("\n🔧 Enrichissement des nœuds...")
    enriched_nodes = enrich_nodes_with_parent_info(
        graph_data['nodes'],
        graph_data['edges']
    )
    graph_data['nodes'] = enriched_nodes
    
    # 2. Feature extractor
    logger.info("\n🔨 Construction des vocabulaires...")
    feature_extractor = GraphFeatureExtractor(
        max_depth=config.max_depth,
        max_fanout=config.max_fanout
    )
    feature_extractor.build_vocabularies(graph_data)
    
    # Sauvegarder vocabulaires
    vocab_path = save_path.parent / "neural_vocabularies.json"
    vocab_path.parent.mkdir(parents=True, exist_ok=True)
    feature_extractor.save_vocabularies(str(vocab_path))
    
    # 3. Créer dataset
    logger.info("\n📦 Création du dataset...")
    dataset = GraphStructureDataset(
        graph_data,
        feature_extractor,
        max_nodes=config.max_nodes_per_structure,
        include_negative_samples=True,
        negative_ratio=0.3,
        augmentation_factor=2  # Double le dataset
    )
    
    if len(dataset) == 0:
        logger.error("❌ Dataset vide !")
        return
    
    # 4. Split train/val
    logger.info("\n✂️ Split train/val...")
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    
    if val_size == 0:
        val_size = 1
        train_size = len(dataset) - 1
    
    train_ds, val_ds = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )
    
    logger.info(f"   • Train: {train_size} samples")
    logger.info(f"   • Val: {val_size} samples")
    
    # 5. Créer trainer
    logger.info("\n🏗️ Création du trainer...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"   • Device: {device}")
    
    trainer = NeuralGraphLearnerTrainer(
        config,
        feature_extractor,
        device
    )
    
    # 6. Entraîner
    logger.info("\n🎓 Début entraînement...")
    history = trainer.train(train_ds, val_ds, verbose=True)
    
    # 7. Sauvegarder
    logger.info("\n💾 Sauvegarde du modèle...")
    trainer.save_model(save_path)
    
    # 8. Résumé
    logger.info("\n" + "=" * 80)
    logger.info("✅ ENTRAÎNEMENT TERMINÉ")
    logger.info("=" * 80)
    logger.info(f"📊 Résultats finaux:")
    if history['train_loss']:
        logger.info(f"   • Train loss: {history['train_loss'][-1]:.4f}")
    if history['val_loss']:
        logger.info(f"   • Val loss: {history['val_loss'][-1]:.4f}")
        logger.info(f"   • Val accuracy: {history['val_acc'][-1]:.2%}")
    logger.info(f"💾 Modèle sauvegardé: {save_path}")
    logger.info(f"💾 Vocabulaires: {vocab_path}")
    logger.info("=" * 80 + "\n")


def main():
    """Point d'entrée principal"""
    
    # 1. Connecter à Dgraph
    logger.info("🔌 Connexion à Dgraph...")
    from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
    
    connector = TaxonomyDgraphConnector()
    
    try:
        # 2. Extraire graphe
        graph_data = extract_graph_from_dgraph(connector)
        
        # 3. Entraîner
        config = NeuralConfig.small()  # Ou NeuralConfig() pour défaut
        
        train_neural_learner(
            graph_data,
            config=config,
            save_path=Path("./data/neural_graph_model.pt")
        )
        
    finally:
        # 4. Fermer connexion
        connector.close()
        logger.info("🔌 Connexion fermée")


if __name__ == "__main__":
    main()