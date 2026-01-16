#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de nettoyage du modèle Graph Learner
Supprime les patterns Unknown accumulés
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_graph_learner_model(model_path: Path, backup: bool = True):
    """
    Nettoie le modèle en supprimant les patterns Unknown
    
    Args:
        model_path: Chemin du modèle
        backup: Créer une sauvegarde avant nettoyage
    """
    
    if not model_path.exists():
        logger.error(f"❌ Modèle introuvable: {model_path}")
        return False
    
    logger.info("="*80)
    logger.info("🧹 NETTOYAGE DU MODÈLE GRAPH LEARNER")
    logger.info("="*80)
    
    # Charger le modèle actuel
    with open(model_path, 'r', encoding='utf-8') as f:
        model = json.load(f)
    
    logger.info(f"\n📂 Modèle chargé: {model_path}")
    
    # Stats avant nettoyage
    edge_patterns_before = model.get('edge_patterns', {})
    unknown_before = sum(1 for sig in edge_patterns_before if 'Unknown' in sig)
    
    logger.info(f"\n📊 État actuel:")
    logger.info(f"  • Total patterns d'arêtes: {len(edge_patterns_before)}")
    logger.info(f"  • Patterns Unknown: {unknown_before}")
    logger.info(f"  • Graphes vus: {model.get('learning_metrics', {}).get('total_graphs_seen', 0)}")
    
    if unknown_before == 0:
        logger.info("\n✅ Aucun pattern Unknown, modèle déjà propre!")
        return True
    
    # Backup si demandé
    if backup:
        backup_path = model_path.parent / f"{model_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        logger.info(f"\n💾 Backup créé: {backup_path}")
    
    # Nettoyage
    logger.info("\n🧹 Nettoyage en cours...")
    
    # Supprimer patterns Unknown des edge_patterns
    cleaned_edge_patterns = {
        sig: pattern 
        for sig, pattern in edge_patterns_before.items() 
        if 'Unknown' not in sig
    }
    
    model['edge_patterns'] = cleaned_edge_patterns
    
    # Optionnel: Nettoyer aussi les node_patterns Unknown (si présents)
    node_patterns_before = model.get('node_patterns', {})
    cleaned_node_patterns = {
        node_type: pattern 
        for node_type, pattern in node_patterns_before.items() 
        if node_type != 'Unknown'
    }
    
    model['node_patterns'] = cleaned_node_patterns
    
    # Mettre à jour les métriques
    if 'learning_metrics' in model:
        model['learning_metrics']['edge_patterns_count'] = len(cleaned_edge_patterns)
        model['learning_metrics']['node_patterns_count'] = len(cleaned_node_patterns)
        model['learning_metrics']['last_training_date'] = datetime.now().isoformat()
    
    # Sauvegarder le modèle nettoyé
    with open(model_path, 'w', encoding='utf-8') as f:
        json.dump(model, f, indent=2, ensure_ascii=False)
    
    # Stats après nettoyage
    logger.info(f"\n✅ Nettoyage terminé!")
    logger.info(f"  • Patterns Unknown supprimés: {unknown_before}")
    logger.info(f"  • Patterns restants: {len(cleaned_edge_patterns)}")
    logger.info(f"  • Modèle sauvegardé: {model_path}")
    
    logger.info("\n" + "="*80)
    logger.info("✅ MODÈLE NETTOYÉ")
    logger.info("="*80 + "\n")
    
    return True


def reset_graph_learner_model(model_path: Path):
    """
    Réinitialise complètement le modèle (supprime le fichier)
    
    Args:
        model_path: Chemin du modèle
    """
    
    if not model_path.exists():
        logger.info(f"✅ Modèle n'existe pas, rien à réinitialiser")
        return True
    
    logger.info("="*80)
    logger.info("🔄 RÉINITIALISATION COMPLÈTE DU MODÈLE")
    logger.info("="*80)
    
    # Backup avant suppression
    backup_path = model_path.parent / f"{model_path.stem}_before_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        # Copier le fichier
        import shutil
        shutil.copy2(model_path, backup_path)
        logger.info(f"\n💾 Backup créé: {backup_path}")
        
        # Supprimer le modèle
        model_path.unlink()
        logger.info(f"🗑️  Modèle supprimé: {model_path}")
        
        logger.info("\n✅ Réinitialisation terminée!")
        logger.info("💡 Le prochain entraînement créera un nouveau modèle propre")
        
        logger.info("\n" + "="*80)
        logger.info("✅ RÉINITIALISATION COMPLÈTE")
        logger.info("="*80 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Erreur: {e}")
        return False


def main():
    """Point d'entrée principal"""
    
    print("\n" + "="*80)
    print("🧹 NETTOYAGE MODÈLE GRAPH LEARNER")
    print("="*80 + "\n")
    
    model_path = Path("./data/graph_structure_model.json")
    
    if not model_path.exists():
        print(f"❌ Modèle introuvable: {model_path}")
        print("💡 Le modèle sera créé au prochain entraînement")
        return 0
    
    print("Options:")
    print("  1. Nettoyer les patterns Unknown (recommandé)")
    print("  2. Réinitialiser complètement (supprimer le modèle)")
    print("  3. Annuler")
    
    choice = input("\nVotre choix (1/2/3): ").strip()
    
    if choice == "1":
        success = clean_graph_learner_model(model_path, backup=True)
        if success:
            print("\n✅ Nettoyage réussi!")
            print("💡 Relancez l'entraînement pour recalculer les patterns propres")
        else:
            print("\n❌ Échec du nettoyage")
        return 0 if success else 1
    
    elif choice == "2":
        confirm = input("\n⚠️  Supprimer complètement le modèle ? (oui/non): ").strip().lower()
        if confirm in ['oui', 'yes', 'y', 'o']:
            success = reset_graph_learner_model(model_path)
            if success:
                print("\n✅ Réinitialisation réussie!")
                print("💡 Relancez l'entraînement pour créer un nouveau modèle")
            else:
                print("\n❌ Échec de la réinitialisation")
            return 0 if success else 1
        else:
            print("\n❌ Annulé")
            return 0
    
    elif choice == "3":
        print("\n❌ Annulé")
        return 0
    
    else:
        print("\n❌ Choix invalide")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())