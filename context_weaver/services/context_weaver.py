#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Context Weaver - Assemblage final du contexte
Système déterministe, PAS de LLM
"""

import logging
from typing import List, Dict, Any

from context_weaver.models.schemas import (
    OSSClassification,
    NormalizedVariables,
    HybridSearchResults,
    SearchResult,
    ContextWeaverOutput,
    DecisionTreeSkeleton,
    DecisionTreeNode
)

logger = logging.getLogger(__name__)

class ContextWeaver:
    """
    Context Weaver - Assemblage du contexte final
    
    Système déterministe qui:
    1. Filtre les résultats par score
    2. Déduplique les branches
    3. Prune les nœuds inutiles
    4. Compresse la structure
    5. Assemble un squelette d'arbre exploitable
    """
    
    def __init__(self):
        self.min_confidence = 0.3  # Score minimum pour inclusion
        self.max_nodes = 20        # Nombre max de nœuds dans le squelette
    
    def weave(
        self,
        classification: OSSClassification,
        normalized: NormalizedVariables,
        search_results: HybridSearchResults
    ) -> ContextWeaverOutput:
        """
        Assemble le contexte final
        
        Args:
            classification: Classification OSS
            normalized: Variables normalisées
            search_results: Résultats de recherche fusionnés
            
        Returns:
            ContextWeaverOutput: Contexte assemblé avec squelette d'arbre
        """
        logger.info("🏗️  Context Weaver - Assemblage du contexte...")
        
        # 1. Filtrer par score
        filtered_results = self._filter_by_score(search_results.results)
        logger.info(f"   • {len(filtered_results)} résultats après filtrage")
        
        # 2. Extraire les structures des résultats
        extracted_structures = self._extract_structures(filtered_results)
        logger.info(f"   • {len(extracted_structures)} structures extraites")
        
        # 3. Construire le squelette d'arbre
        tree_skeleton = self._build_tree_skeleton(
            classification,
            normalized,
            extracted_structures
        )
        logger.info(f"   • Squelette: {len(tree_skeleton.nodes)} nœuds")
        
        # 4. Calculer la confiance
        confidence = self._compute_confidence(
            search_results,
            filtered_results,
            tree_skeleton
        )
        logger.info(f"   • Confiance: {confidence:.2%}")
        
        # 5. Extraire les sources
        sources = self._extract_sources(filtered_results)
        
        # 6. Métadonnées
        metadata = {
            "total_search_results": search_results.final_count,
            "filtered_results": len(filtered_results),
            "domain": classification.domain,
            "task": classification.task,
            "decision_type": classification.decision_type,
            "variables_count": len(normalized.variables)
        }
        
        logger.info("✅ Context assemblé")
        
        return ContextWeaverOutput(
            decision_tree_skeleton=tree_skeleton,
            metadata=metadata,
            confidence_score=confidence,
            sources=sources
        )
    
    def _filter_by_score(self, results: List[SearchResult]) -> List[SearchResult]:
        """Filtre les résultats par score minimum"""
        return [r for r in results if r.score >= self.min_confidence]
    
    def _extract_structures(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """
        Extrait les structures exploitables des résultats
        
        Dans un système réel, cela parserait le contenu JSON/XML
        des résultats pour extraire des arbres, règles, templates
        """
        structures = []
        
        for result in results:
            # Simuler l'extraction de structure
            # Dans la vraie version, on parserait result.content
            structure = {
                "id": result.id,
                "name": result.name,
                "type": result.type,
                "score": result.score,
                "domain": result.domain,
                # Ici on extrairait les vrais nœuds/règles du content
                "nodes": self._parse_content_nodes(result.content)
            }
            structures.append(structure)
        
        return structures
    
    def _parse_content_nodes(self, content: Any) -> List[Dict]:
        """
        Parse le contenu pour extraire les nœuds
        Version simplifiée - dans la réalité, parsing complexe
        """
        # Simulé pour l'exemple
        return []
    
    def _build_tree_skeleton(
        self,
        classification: OSSClassification,
        normalized: NormalizedVariables,
        structures: List[Dict[str, Any]]
    ) -> DecisionTreeSkeleton:
        """
        Construit le squelette d'arbre de décision
        
        Stratégie:
        1. Utiliser les variables normalisées comme base
        2. Enrichir avec les structures trouvées
        3. Organiser hiérarchiquement
        """
        logger.info("   • Construction du squelette...")
        
        nodes = []
        
        # Créer un nœud par variable normalisée
        for user_var, normalized_var in normalized.variables.items():
            node = self._create_node_for_variable(
                normalized_var,
                classification.domain
            )
            if node:
                nodes.append(node)
        
        # Limiter le nombre de nœuds
        nodes = nodes[:self.max_nodes]
        
        # Déterminer la racine
        root = self._determine_root(classification, nodes)
        
        return DecisionTreeSkeleton(
            root=root,
            nodes=nodes
        )
    
    def _create_node_for_variable(
        self,
        variable: str,
        domain: str
    ) -> DecisionTreeNode:
        """
        Crée un nœud d'arbre pour une variable
        
        Basé sur des règles métier par domaine et type de variable
        """
        # Mapping type de variable -> type de split
        if "amount" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                ranges=["<1000", "1000-5000", "5000-10000", ">10000"]
            )
        
        elif "country" in variable.lower() or "code" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                groups=["local", "regional", "international", "high_risk"]
            )
        
        elif "frequency" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                levels=["low", "medium", "high", "very_high"]
            )
        
        elif "score" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                ranges=["0-25", "25-50", "50-75", "75-100"]
            )
        
        elif "age" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                ranges=["<25", "25-35", "35-50", "50-65", ">65"]
            )
        
        elif "date" in variable.lower() or "time" in variable.lower():
            return DecisionTreeNode(
                field=variable,
                groups=["morning", "afternoon", "evening", "night"]
            )
        
        # Type par défaut
        return DecisionTreeNode(
            field=variable,
            levels=["low", "medium", "high"]
        )
    
    def _determine_root(
        self,
        classification: OSSClassification,
        nodes: List[DecisionTreeNode]
    ) -> str:
        """
        Détermine le nœud racine de l'arbre
        
        Basé sur le domaine et la tâche
        """
        if classification.domain == "fraude_bancaire":
            return "transaction"
        elif classification.domain == "credit_scoring":
            return "customer"
        elif classification.domain == "detection_anomalies":
            return "event"
        else:
            return "root"
    
    def _compute_confidence(
        self,
        search_results: HybridSearchResults,
        filtered_results: List[SearchResult],
        tree_skeleton: DecisionTreeSkeleton
    ) -> float:
        """
        Calcule un score de confiance global
        
        Basé sur:
        - Nombre de résultats trouvés
        - Qualité des scores
        - Complétude du squelette
        """
        # Facteur 1: Taux de résultats conservés après filtrage
        if search_results.final_count > 0:
            kept_ratio = len(filtered_results) / search_results.final_count
        else:
            kept_ratio = 0.0
        
        # Facteur 2: Score moyen des résultats conservés
        if filtered_results:
            avg_score = sum(r.score for r in filtered_results) / len(filtered_results)
        else:
            avg_score = 0.0
        
        # Facteur 3: Complétude du squelette (nombre de nœuds)
        completeness = min(len(tree_skeleton.nodes) / 5.0, 1.0)  # 5 nœuds = complet
        
        # Combinaison pondérée
        confidence = (
            0.3 * kept_ratio +
            0.5 * avg_score +
            0.2 * completeness
        )
        
        return min(confidence, 1.0)
    
    def _extract_sources(self, results: List[SearchResult]) -> List[str]:
        """Extrait les sources uniques des résultats"""
        sources = set()
        for result in results:
            source = f"{result.domain}:{result.type}:{result.name}"
            sources.add(source)
        return sorted(list(sources))