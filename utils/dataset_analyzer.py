#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Analyzer - Logic layer for analyzing project and batch data
Separates business logic from UI components
"""

import logging
from typing import Dict, List, Any, Set, Tuple

logger = logging.getLogger(__name__)


class DatasetAnalyzer:
    """Handles all data analysis logic for projects and batches"""

    @staticmethod
    def count_children_recursive(children: List[Dict]) -> int:
        """
        Recursively count all children in a hierarchical structure
        
        Args:
            children: List of child dictionaries with potential nested children
            
        Returns:
            Total count of all children at all levels
        """
        if not children:
            return 0
        
        count = len(children)
        
        for child in children:
            if isinstance(child, dict) and 'children' in child:
                count += DatasetAnalyzer.count_children_recursive(
                    child.get('children', [])
                )
        
        return count

    @staticmethod
    def analyze_project_structure(project_data: Dict) -> Dict[str, Any]:
        """
        Analyze overall project structure
        
        Args:
            project_data: Complete project data dictionary
            
        Returns:
            Dictionary with project analysis:
            - name: Project name
            - description: Project description
            - typologies_count: Number of typologies
            - typologies: List of typologie analysis
        """
        if not project_data:
            return {}

        typologies = project_data.get('typologies', [])
        
        typologie_analysis = []
        for typologie in typologies:
            typ_name = typologie.get('name', 'Sans nom')
            taxonomy_clusters = typologie.get('taxonomy_clusters', [])
            
            cluster_details = []
            for cluster in taxonomy_clusters:
                cluster_name = cluster.get('name', 'Sans nom')
                root_labels = cluster.get('root_labels', [])
                
                # Count elements at each level
                total_roots = len(root_labels)
                total_parents = sum(
                    len(root.get('parent_labels', [])) 
                    for root in root_labels
                )
                
                # Count children safely
                total_children = 0
                for root in root_labels:
                    for parent in root.get('parent_labels', []):
                        children = parent.get('children', [])
                        if children:
                            total_children += DatasetAnalyzer.count_children_recursive(children)
                
                cluster_details.append({
                    'name': cluster_name,
                    'roots': total_roots,
                    'parents': total_parents,
                    'children': total_children
                })
            
            typologie_analysis.append({
                'name': typ_name,
                'clusters': cluster_details,
                'clusters_count': len(taxonomy_clusters)
            })

        return {
            'name': project_data.get('nom', 'Sans nom'),
            'description': project_data.get('description', 'Aucune description'),
            'typologies_count': len(typologies),
            'typologies': typologie_analysis
        }

    @staticmethod
    def analyze_batch_combinations(combinations: List[Dict], total_count: int) -> Dict[str, Any]:
        """
        Analyze batch combinations structure
        
        Structure analysis:
        - 1 Master typologie (used N times across combinations)
        - Multiple Context typologies (each used M times)
        - Total uses = Master uses + Context uses = 2 * number of combinations
        
        Args:
            combinations: List of combination dictionaries
            total_count: Total number of combinations
            
        Returns:
            Dictionary with analysis including:
            - typologie_counts: Count per typologie (with emoji prefix)
            - typologie_types: Type of each typologie (master/context)
            - typologie_levels: Hierarchical level of each typologie
            - level_distribution: Distribution by level
            - depth_stats: Statistics by depth
            - master_total_uses: Total master uses
            - context_total_uses: Total context uses
            - unique_masters_count: Number of unique masters
            - unique_contexts_count: Number of unique contexts
            - total_typologies_uses: Total typologie uses
        """
        analysis = {
            'typologie_counts': {},
            'typologie_types': {},
            'typologie_levels': {},
            'level_distribution': {},
            'depth_stats': {},
            'master_total_uses': 0,
            'context_total_uses': 0,
            'unique_masters': set(),
            'unique_contexts': set()
        }

        for combo in combinations:
            # === MASTER TYPOLOGIE ===
            master = combo.get('master', {})
            master_name = master.get('name', 'Unknown Master')

            # Key with prefix for visual distinction
            key_master = f"🎯 {master_name}"

            # Increment count (number of uses)
            analysis['typologie_counts'][key_master] = \
                analysis['typologie_counts'].get(key_master, 0) + 1

            # Store type and level
            analysis['typologie_types'][key_master] = 'master'
            analysis['typologie_levels'][key_master] = 'Master'

            # Global counters
            analysis['master_total_uses'] += 1
            analysis['unique_masters'].add(master_name)

            # === CONTEXT TYPOLOGIE ===
            context = combo.get('context', {})
            context_name = context.get('typologie', 'Unknown Context')
            level = context.get('level', 'unknown')

            # Key with prefix
            key_context = f"🔗 {context_name}"

            # Increment count
            analysis['typologie_counts'][key_context] = \
                analysis['typologie_counts'].get(key_context, 0) + 1

            # Store type
            analysis['typologie_types'][key_context] = 'context'

            # Global counters
            analysis['context_total_uses'] += 1
            analysis['unique_contexts'].add(context_name)

            # === HIERARCHICAL LEVEL ===
            if level == 'child':
                child_path = context.get('child_path', [])
                depth = len(child_path)
                level_display = f"Enfant Niveau {depth}"

                # Depth stats
                analysis['depth_stats'][depth] = \
                    analysis['depth_stats'].get(depth, 0) + 1
            else:
                level_display = {
                    'typologie': 'Typologie',
                    'taxonomy': 'Cluster',
                    'root': 'Root',
                    'parent': 'Parent'
                }.get(level, level.capitalize())

            analysis['typologie_levels'][key_context] = level_display

            # Level distribution
            analysis['level_distribution'][level_display] = \
                analysis['level_distribution'].get(level_display, 0) + 1

        # === TOTAL CALCULATION ===
        # Total = all typologie uses (Master + Context)
        analysis['total_typologies_uses'] = \
            analysis['master_total_uses'] + analysis['context_total_uses']

        # Convert sets to count
        analysis['unique_masters_count'] = len(analysis['unique_masters'])
        analysis['unique_contexts_count'] = len(analysis['unique_contexts'])

        logger.info(f"📊 Batch analysis:")
        logger.info(f"   Combinations: {total_count}")
        logger.info(f"   Total typologie uses: {analysis['total_typologies_uses']}")
        logger.info(f"   Master used: {analysis['master_total_uses']} times "
                   f"({analysis['unique_masters_count']} unique)")
        logger.info(f"   Context used: {analysis['context_total_uses']} times "
                   f"({analysis['unique_contexts_count']} unique)")

        return analysis

    @staticmethod
    def calculate_percentages(analysis: Dict[str, Any]) -> List[Tuple[str, int, float]]:
        """
        Calculate percentages for each typologie based on total uses
        
        Args:
            analysis: Analysis dictionary from analyze_batch_combinations
            
        Returns:
            List of tuples (typologie_key, count, percentage) sorted by count descending
        """
        total_uses = analysis['total_typologies_uses']
        
        results = []
        for typo_key, count in analysis['typologie_counts'].items():
            percentage = (count / total_uses * 100) if total_uses > 0 else 0
            results.append((typo_key, count, percentage))
        
        # Sort by count descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results

    @staticmethod
    def format_batch_info(batch_data: Dict, analysis: Dict[str, Any]) -> str:
        """
        Format batch information string
        
        Args:
            batch_data: Batch data dictionary
            analysis: Analysis dictionary
            
        Returns:
            Formatted info string
        """
        batch_name = batch_data.get('batch_name', 'Sans nom')
        total_count = len(batch_data.get('combinations', []))
        
        return (
            f"📦 Batch: {batch_name} | "
            f"Combinaisons: {total_count} | "
            f"Masters uniques: {analysis['unique_masters_count']} | "
            f"Contextes uniques: {analysis['unique_contexts_count']}"
        )

    @staticmethod
    def get_typologie_display_name(typo_key: str) -> str:
        """
        Get display name without emoji prefix
        
        Args:
            typo_key: Typologie key with emoji prefix
            
        Returns:
            Clean display name
        """
        return typo_key.replace("🎯 ", "").replace("🔗 ", "")

    @staticmethod
    def analyze_combinations_legacy(combinations: List[Dict]) -> Dict[str, Any]:
        """
        Legacy analysis method for backward compatibility
        Analyze combinations and extract statistics
        
        Args:
            combinations: List of combination dictionaries
            
        Returns:
            Dictionary with comprehensive statistics
        """
        analysis = {
            'total': len(combinations),
            'master_typologies': {},
            'context_typologies': {},
            'levels': {},
            'clusters': set(),
            'max_depth': 0,
            'by_depth': {},
            'hierarchy_distribution': {}
        }
        
        for combo in combinations:
            # Master typologie
            master = combo.get('master', {})
            master_name = master.get('name', 'Unknown')
            analysis['master_typologies'][master_name] = \
                analysis['master_typologies'].get(master_name, 0) + 1
            
            # Context
            context = combo.get('context', {})
            level = context.get('level', 'unknown')
            typologie = context.get('typologie', 'Unknown')
            
            # Context typologie
            analysis['context_typologies'][typologie] = \
                analysis['context_typologies'].get(typologie, 0) + 1
            
            # Level
            analysis['levels'][level] = analysis['levels'].get(level, 0) + 1
            
            # Cluster
            taxonomy = context.get('taxonomy', '')
            if taxonomy:
                analysis['clusters'].add(taxonomy)
            
            # Depth calculation
            depth = 0
            if level == 'typologie':
                depth = 1
            elif level == 'taxonomy':
                depth = 2
            elif level == 'root':
                depth = 3
            elif level == 'parent':
                depth = 4
            elif level == 'child':
                child_path = context.get('child_path', [])
                depth = 4 + len(child_path)
            
            analysis['max_depth'] = max(analysis['max_depth'], depth)
            analysis['by_depth'][depth] = analysis['by_depth'].get(depth, 0) + 1
            
            # Hierarchy distribution
            hierarchy_key = f"{level}"
            if level == 'child' and context.get('child_path'):
                hierarchy_key = f"child_level_{len(context.get('child_path', []))}"
            
            analysis['hierarchy_distribution'][hierarchy_key] = \
                analysis['hierarchy_distribution'].get(hierarchy_key, 0) + 1
        
        analysis['clusters'] = len(analysis['clusters'])
        
        return analysis