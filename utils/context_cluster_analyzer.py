#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enhanced Dataset Analyzer - CORRECTION COMPLÈTE
Analyse basée sur le NOMBRE DE SAMPLES avec support complet des typologies Master et Context
"""

import logging
from typing import Dict, List, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class ContextClusterAnalyzer:
    """Analyseur spécialisé pour les typologies de contexte basé sur les SAMPLES"""

    @staticmethod
    def extract_typologie_info(typologie_data: Any, typologie_type: str = 'context') -> Dict[str, Any]:
        """
        Extrait les informations d'une typologie de manière robuste
        Gère les cas où typologie_data est une string ou un dict
        
        Args:
            typologie_data: Données de la typologie (string ou dict)
            typologie_type: 'master' ou 'context'
            
        Returns:
            Dict avec toutes les informations structurées
        """
        # Cas 1: typologie_data est une simple string (nom de typologie)
        if isinstance(typologie_data, str):
            return {
                'name': typologie_data,
                'taxonomy': 'Default Cluster',
                'label': typologie_data,
                'full_label': typologie_data,
                'level': 'typologie',
                'root_label': '',
                'parent_label': '',
                'child_path': []
            }
        
        # Cas 2: typologie_data est un dict
        if not isinstance(typologie_data, dict):
            logger.warning(f"Type inattendu pour typologie: {type(typologie_data)}")
            return {
                'name': 'Unknown',
                'taxonomy': 'No Cluster',
                'label': 'Unknown',
                'full_label': 'Unknown',
                'level': 'unknown',
                'root_label': '',
                'parent_label': '',
                'child_path': []
            }
        
        # Extraction des champs selon le type
        if typologie_type == 'master':
            name = typologie_data.get('name', 'Unknown Master')
            taxonomy = typologie_data.get('taxonomy', 'No Cluster')
            label = typologie_data.get('label', name)
        else:  # context
            name = typologie_data.get('typologie', typologie_data.get('name', 'Unknown'))
            taxonomy = typologie_data.get('taxonomy', typologie_data.get('cluster', 'No Cluster'))
            label = typologie_data.get('label', 'No Label')
        
        level = typologie_data.get('level', 'typologie')
        root_label = typologie_data.get('root_label', '')
        parent_label = typologie_data.get('parent_label', '')
        child_path = typologie_data.get('child_path', [])
        
        # Construction du label complet selon le niveau
        if level == 'typologie':
            full_label = name
        elif level == 'root':
            full_label = root_label or label
        elif level == 'parent':
            if root_label and parent_label:
                full_label = f"{root_label} > {parent_label}"
            else:
                full_label = label
        elif level == 'child':
            if child_path:
                path_str = " > ".join(child_path)
                if root_label and parent_label:
                    full_label = f"{root_label} > {parent_label} > {path_str}"
                else:
                    full_label = path_str
            else:
                full_label = label
        else:
            full_label = label
        
        return {
            'name': name,
            'taxonomy': taxonomy,
            'label': label,
            'full_label': full_label,
            'level': level,
            'root_label': root_label,
            'parent_label': parent_label,
            'child_path': child_path
        }

    @staticmethod
    def analyze_context_typologies_with_clusters(combinations: List[Dict]) -> Dict[str, Any]:
        """
        Analyse complète basée sur le NOMBRE DE SAMPLES
        VERSION CORRIGÉE avec support complet Master + Context
        
        Args:
            combinations: Liste des combinaisons du batch
            
        Returns:
            Dictionnaire avec analyse complète par samples
        """
        analysis = {
            'context_typologies': defaultdict(lambda: {
                'total_samples': 0,
                'type': 'context',
                'clusters': defaultdict(lambda: {
                    'sample_count': 0,
                    'labels': defaultdict(int),
                    'levels': defaultdict(int),
                    'level_details': defaultdict(lambda: {
                        'root_labels': defaultdict(int),
                        'parent_labels': defaultdict(int),
                        'child_labels': defaultdict(int)
                    })
                }),
                'percentage': 0.0
            }),
            'master_typologies': defaultdict(lambda: {
                'total_samples': 0,
                'type': 'master',
                'clusters': defaultdict(lambda: {
                    'sample_count': 0,
                    'labels': defaultdict(int),
                    'levels': defaultdict(int),
                    'level_details': defaultdict(lambda: {
                        'root_labels': defaultdict(int),
                        'parent_labels': defaultdict(int),
                        'child_labels': defaultdict(int)
                    })
                }),
                'percentage': 0.0
            }),
            'total_samples': 0,
            'global_clusters': defaultdict(int),
            'global_labels': defaultdict(int),
            'level_distribution': {
                'context': defaultdict(int),
                'master': defaultdict(int)
            }
        }

        # === COMPTAGE DES SAMPLES TOTAUX ===
        for combo in combinations:
            sample_count = combo.get('sample_count', 1)
            analysis['total_samples'] += sample_count

        # === PARCOURS DES COMBINAISONS ===
        for combo in combinations:
            sample_count = combo.get('sample_count', 1)
            
            # === TRAITEMENT MASTER ===
            master_raw = combo.get('master', {})
            master_info = ContextClusterAnalyzer.extract_typologie_info(master_raw, 'master')
            
            master_data = analysis['master_typologies'][master_info['name']]
            master_data['total_samples'] += sample_count
            
            master_cluster_data = master_data['clusters'][master_info['taxonomy']]
            master_cluster_data['sample_count'] += sample_count
            master_cluster_data['labels'][master_info['full_label']] += sample_count
            master_cluster_data['levels'][master_info['level']] += sample_count
            
            # Détails par niveau
            level_detail = master_cluster_data['level_details'][master_info['level']]
            if master_info['level'] == 'root' and master_info['root_label']:
                level_detail['root_labels'][master_info['root_label']] += sample_count
            elif master_info['level'] == 'parent' and master_info['parent_label']:
                level_detail['parent_labels'][master_info['parent_label']] += sample_count
            elif master_info['level'] == 'child' and master_info['child_path']:
                level_detail['child_labels'][master_info['child_path'][-1]] += sample_count
            
            analysis['global_clusters'][master_info['taxonomy']] += sample_count
            analysis['global_labels'][master_info['full_label']] += sample_count
            analysis['level_distribution']['master'][master_info['level']] += sample_count
            
            # === TRAITEMENT CONTEXT ===
            context_raw = combo.get('context', {})
            context_info = ContextClusterAnalyzer.extract_typologie_info(context_raw, 'context')
            
            typo_data = analysis['context_typologies'][context_info['name']]
            typo_data['total_samples'] += sample_count
            
            cluster_data = typo_data['clusters'][context_info['taxonomy']]
            cluster_data['sample_count'] += sample_count
            cluster_data['labels'][context_info['full_label']] += sample_count
            cluster_data['levels'][context_info['level']] += sample_count
            
            # Détails par niveau
            level_detail = cluster_data['level_details'][context_info['level']]
            if context_info['level'] == 'root' and context_info['root_label']:
                level_detail['root_labels'][context_info['root_label']] += sample_count
            elif context_info['level'] == 'parent' and context_info['parent_label']:
                level_detail['parent_labels'][context_info['parent_label']] += sample_count
            elif context_info['level'] == 'child' and context_info['child_path']:
                level_detail['child_labels'][context_info['child_path'][-1]] += sample_count
            
            analysis['global_clusters'][context_info['taxonomy']] += sample_count
            analysis['global_labels'][context_info['full_label']] += sample_count
            analysis['level_distribution']['context'][context_info['level']] += sample_count

        # === CALCUL DES POURCENTAGES ===
        total_samples = analysis['total_samples']
        
        for typologie_name, typo_data in analysis['context_typologies'].items():
            typo_data['percentage'] = (typo_data['total_samples'] / total_samples * 100) if total_samples > 0 else 0
        
        for typologie_name, typo_data in analysis['master_typologies'].items():
            typo_data['percentage'] = (typo_data['total_samples'] / total_samples * 100) if total_samples > 0 else 0

        # === IDENTIFICATION DES TOPS ===
        all_typologies = {}
        for typ_name, typ_data in analysis['context_typologies'].items():
            all_typologies[('context', typ_name)] = typ_data
        for typ_name, typ_data in analysis['master_typologies'].items():
            all_typologies[('master', typ_name)] = typ_data
        
        if all_typologies:
            top_typo_key, top_typo_data = max(
                all_typologies.items(),
                key=lambda x: x[1]['total_samples']
            )
            analysis['top_typologie'] = {
                'type': top_typo_key[0],
                'name': top_typo_key[1],
                'samples': top_typo_data['total_samples'],
                'percentage': top_typo_data['percentage']
            }
        
        if analysis['context_typologies']:
            top_context = max(
                analysis['context_typologies'].items(),
                key=lambda x: x[1]['total_samples']
            )
            analysis['top_context_typologie'] = {
                'name': top_context[0],
                'samples': top_context[1]['total_samples'],
                'percentage': top_context[1]['percentage']
            }
        
        if analysis['master_typologies']:
            top_master = max(
                analysis['master_typologies'].items(),
                key=lambda x: x[1]['total_samples']
            )
            analysis['top_master_typologie'] = {
                'name': top_master[0],
                'samples': top_master[1]['total_samples'],
                'percentage': top_master[1]['percentage']
            }

        if analysis['global_clusters']:
            top_cluster = max(
                analysis['global_clusters'].items(),
                key=lambda x: x[1]
            )
            analysis['top_cluster'] = {
                'name': top_cluster[0],
                'samples': top_cluster[1],
                'percentage': (top_cluster[1] / total_samples * 100) if total_samples > 0 else 0
            }

        # Conversion en dict normaux
        ContextClusterAnalyzer._convert_defaultdicts_to_dicts(analysis)

        logger.info(f"📊 Analyse par SAMPLES (MASTER + CONTEXT):")
        logger.info(f"   Total SAMPLES: {total_samples}")
        logger.info(f"   Typologies CONTEXT: {len(analysis['context_typologies'])}")
        logger.info(f"   Typologies MASTER: {len(analysis['master_typologies'])}")
        logger.info(f"   Distribution niveaux CONTEXT: {dict(analysis['level_distribution']['context'])}")
        logger.info(f"   Distribution niveaux MASTER: {dict(analysis['level_distribution']['master'])}")

        return analysis

    @staticmethod
    def _convert_defaultdicts_to_dicts(analysis: Dict):
        """Convertit tous les defaultdicts en dicts normaux"""
        analysis['context_typologies'] = dict(analysis['context_typologies'])
        for typologie_name in analysis['context_typologies']:
            typo_data = analysis['context_typologies'][typologie_name]
            typo_data['clusters'] = dict(typo_data['clusters'])
            for cluster_name in typo_data['clusters']:
                cluster_data = typo_data['clusters'][cluster_name]
                cluster_data['labels'] = dict(cluster_data['labels'])
                cluster_data['levels'] = dict(cluster_data['levels'])
                cluster_data['level_details'] = dict(cluster_data['level_details'])
                for level in cluster_data['level_details']:
                    details = cluster_data['level_details'][level]
                    details['root_labels'] = dict(details['root_labels'])
                    details['parent_labels'] = dict(details['parent_labels'])
                    details['child_labels'] = dict(details['child_labels'])
        
        analysis['master_typologies'] = dict(analysis['master_typologies'])
        for typologie_name in analysis['master_typologies']:
            typo_data = analysis['master_typologies'][typologie_name]
            typo_data['clusters'] = dict(typo_data['clusters'])
            for cluster_name in typo_data['clusters']:
                cluster_data = typo_data['clusters'][cluster_name]
                cluster_data['labels'] = dict(cluster_data['labels'])
                cluster_data['levels'] = dict(cluster_data['levels'])
                cluster_data['level_details'] = dict(cluster_data['level_details'])
                for level in cluster_data['level_details']:
                    details = cluster_data['level_details'][level]
                    details['root_labels'] = dict(details['root_labels'])
                    details['parent_labels'] = dict(details['parent_labels'])
                    details['child_labels'] = dict(details['child_labels'])

        analysis['global_clusters'] = dict(analysis['global_clusters'])
        analysis['global_labels'] = dict(analysis['global_labels'])
        analysis['level_distribution']['context'] = dict(analysis['level_distribution']['context'])
        analysis['level_distribution']['master'] = dict(analysis['level_distribution']['master'])

    @staticmethod
    def get_sorted_typologies(analysis: Dict, typologie_type: str = 'all') -> List[Tuple[str, Dict]]:
        """Retourne les typologies triées par nombre de SAMPLES"""
        if typologie_type == 'context':
            typologies = analysis.get('context_typologies', {})
        elif typologie_type == 'master':
            typologies = analysis.get('master_typologies', {})
        else:  # 'all'
            typologies = {}
            typologies.update(analysis.get('context_typologies', {}))
            typologies.update(analysis.get('master_typologies', {}))
        
        return sorted(
            typologies.items(),
            key=lambda x: x[1]['total_samples'],
            reverse=True
        )

    @staticmethod
    def get_sorted_clusters_for_typologie(typologie_data: Dict) -> List[Tuple[str, Dict]]:
        """Retourne les clusters d'une typologie triés par nombre de SAMPLES"""
        clusters = typologie_data.get('clusters', {})
        return sorted(
            clusters.items(),
            key=lambda x: x[1]['sample_count'],
            reverse=True
        )

    @staticmethod
    def get_sorted_labels_for_cluster(cluster_data: Dict) -> List[Tuple[str, int]]:
        """Retourne les labels d'un cluster triés par nombre de SAMPLES"""
        labels = cluster_data.get('labels', {})
        return sorted(
            labels.items(),
            key=lambda x: x[1],
            reverse=True
        )
    
    @staticmethod
    def get_level_details_for_cluster(cluster_data: Dict, level: str) -> Dict[str, int]:
        """
        Récupère les détails d'un niveau spécifique dans un cluster
        
        Args:
            cluster_data: Données du cluster
            level: 'root', 'parent', ou 'child'
            
        Returns:
            Dict avec les labels du niveau et leurs counts
        """
        level_details = cluster_data.get('level_details', {}).get(level, {})
        
        if level == 'root':
            return dict(level_details.get('root_labels', {}))
        elif level == 'parent':
            return dict(level_details.get('parent_labels', {}))
        elif level == 'child':
            return dict(level_details.get('child_labels', {}))
        
        return {}

    @staticmethod
    def format_context_summary(analysis: Dict) -> str:
        """Formate un résumé textuel de l'analyse par SAMPLES"""
        lines = []
        lines.append("=" * 60)
        lines.append("ANALYSE PAR SAMPLES - TYPOLOGIES ET CLUSTERS")
        lines.append("=" * 60)
        lines.append(f"\n📦 Total SAMPLES dans la batch: {analysis['total_samples']}")
        
        if analysis.get('top_typologie'):
            top_typo = analysis['top_typologie']
            type_icon = "🎯" if top_typo['type'] == 'master' else "🔗"
            lines.append(f"\n{type_icon} Typologie la plus représentée (globale):")
            lines.append(f"   • {top_typo['name']} [{top_typo['type'].upper()}]")
            lines.append(f"   • {top_typo['samples']} samples ({top_typo['percentage']:.1f}%)")
        
        # Distribution par niveaux
        lines.append(f"\n📊 DISTRIBUTION PAR NIVEAUX:")
        lines.append("-" * 60)
        lines.append("CONTEXT:")
        for level, count in sorted(analysis['level_distribution']['context'].items(), 
                                   key=lambda x: x[1], reverse=True):
            pct = (count / analysis['total_samples'] * 100) if analysis['total_samples'] > 0 else 0
            lines.append(f"   • {level}: {count} samples ({pct:.1f}%)")
        
        lines.append("\nMASTER:")
        for level, count in sorted(analysis['level_distribution']['master'].items(), 
                                   key=lambda x: x[1], reverse=True):
            pct = (count / analysis['total_samples'] * 100) if analysis['total_samples'] > 0 else 0
            lines.append(f"   • {level}: {count} samples ({pct:.1f}%)")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    @staticmethod
    def export_to_csv_data(analysis: Dict) -> List[List[str]]:
        """Exporte les données au format CSV (basé sur samples)"""
        csv_data = []
        
        csv_data.append([
            "Type",
            "Typologie",
            "Total_Samples",
            "Pourcentage",
            "Cluster",
            "Cluster_Samples",
            "Cluster_Pct",
            "Level",
            "Label",
            "Label_Samples"
        ])
        
        # Export MASTER
        sorted_masters = ContextClusterAnalyzer.get_sorted_typologies(analysis, 'master')
        for typologie_name, typo_data in sorted_masters:
            sorted_clusters = ContextClusterAnalyzer.get_sorted_clusters_for_typologie(typo_data)
            for cluster_name, cluster_data in sorted_clusters:
                cluster_pct = (cluster_data['sample_count'] / typo_data['total_samples'] * 100)
                sorted_labels = ContextClusterAnalyzer.get_sorted_labels_for_cluster(cluster_data)
                for label, label_count in sorted_labels:
                    # Déterminer le niveau du label
                    level = 'unknown'
                    for lvl, lvl_count in cluster_data['levels'].items():
                        if lvl_count > 0:
                            level = lvl
                            break
                    
                    csv_data.append([
                        "MASTER",
                        typologie_name,
                        str(typo_data['total_samples']),
                        f"{typo_data['percentage']:.2f}",
                        cluster_name,
                        str(cluster_data['sample_count']),
                        f"{cluster_pct:.2f}",
                        level,
                        label,
                        str(label_count)
                    ])
        
        # Export CONTEXT
        sorted_contexts = ContextClusterAnalyzer.get_sorted_typologies(analysis, 'context')
        for typologie_name, typo_data in sorted_contexts:
            sorted_clusters = ContextClusterAnalyzer.get_sorted_clusters_for_typologie(typo_data)
            for cluster_name, cluster_data in sorted_clusters:
                cluster_pct = (cluster_data['sample_count'] / typo_data['total_samples'] * 100)
                sorted_labels = ContextClusterAnalyzer.get_sorted_labels_for_cluster(cluster_data)
                for label, label_count in sorted_labels:
                    level = 'unknown'
                    for lvl, lvl_count in cluster_data['levels'].items():
                        if lvl_count > 0:
                            level = lvl
                            break
                    
                    csv_data.append([
                        "CONTEXT",
                        typologie_name,
                        str(typo_data['total_samples']),
                        f"{typo_data['percentage']:.2f}",
                        cluster_name,
                        str(cluster_data['sample_count']),
                        f"{cluster_pct:.2f}",
                        level,
                        label,
                        str(label_count)
                    ])
        
        return csv_data