#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
✅ CORRIGÉ: TaxonomyProjector - Phase 1 Build avec validation structurelle
"""

import datetime
import logging
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict, deque

from context_weaver.taxonomy.taxonomy_models import TaxonDoc, PrereqSnapshot

logger = logging.getLogger(__name__)


class TaxonomyProjector:
    """
    ✅ CORRIGÉ: Projette la taxonomie avec validation structurelle
    
    Nouvelles fonctionnalités:
    - ✅ Validation hiérarchique offline (cycles, orphelins, chemins)
    - ✅ Construction de PrereqSnapshot (cache KV)
    - ✅ index_text enrichi (breadcrumbs + prereq_hint + children)
    - ✅ Fermeture transitive des prereqs hard
    """
    
    def __init__(self, graph_client, vector_store, embedder):
        self.graph = graph_client
        self.vector_store = vector_store
        self.embedder = embedder
    
    
    def project_taxonomy(self, taxonomy_version: str) -> Dict[str, Any]:
        """
        ✅ CORRIGÉ: Phase 1 Build complète avec validation
        
        1. Extract hiérarchie depuis graph (SoT)
        2. ✅ NOUVEAU: Validate structure offline (cycles, chemins, cohérence)
        3. ✅ NOUVEAU: Build PrereqSnapshot (cache KV)
        4. Create TaxonDoc enrichis avec:
           - index_text contextualisé (breadcrumbs + prereq_hint + children)
           - metadata structurée (parent_ids, path_ids, prereqs)
           - embedding
        5. Store dans vector store
        """
        
        logger.info("="*80)
        logger.info("🏗️ TAXONOMY PROJECTION - PHASE 1 BUILD")
        logger.info("="*80)
        
        # === 1. EXTRACT ===
        logger.info("\n📊 Étape 1: Extraction depuis graph...")
        hierarchy = self._extract_hierarchy()
        logger.info(f"   ✅ {len(hierarchy['nodes'])} nœuds extraits")
        
        # === 2. VALIDATE STRUCTURE (✅ NOUVEAU) ===
        logger.info("\n🔍 Étape 2: Validation structurelle...")
        validation_result = self._validate_hierarchy_structure(hierarchy)
        
        if not validation_result['valid']:
            logger.error("❌ Validation échouée - Ne peut pas publier la version")
            for error in validation_result['errors']:
                logger.error(f"   • {error}")
            raise ValueError("Hiérarchie invalide")
        
        logger.info(f"   ✅ Hiérarchie valide")
        
        # === 3. BUILD PREREQ SNAPSHOT (✅ NOUVEAU) ===
        logger.info("\n💾 Étape 3: Construction PrereqSnapshot...")
        prereq_snapshot = self._build_prereq_snapshot(hierarchy, taxonomy_version)
        logger.info(f"   ✅ {len(prereq_snapshot.prereq_hard)} prereqs hard")
        logger.info(f"   ✅ {len(prereq_snapshot.closure_hard)} fermetures transitives")
        
        # Sauvegarder snapshot
        snapshot_path = f"./data/prereq_snapshot_{taxonomy_version}.json"
        prereq_snapshot.save_to_json(snapshot_path)
        logger.info(f"   ✅ Snapshot sauvegardé: {snapshot_path}")
        
        # === 4. CREATE TAXON DOCS ===
        logger.info("\n📝 Étape 4: Création TaxonDocs enrichis...")
        taxon_docs = []
        
        for node in hierarchy['nodes']:
            doc = self._create_taxon_doc(node, hierarchy, prereq_snapshot)
            taxon_docs.append(doc)
        
        logger.info(f"   ✅ {len(taxon_docs)} TaxonDocs créés")
        
        # === 5. STORE ===
        logger.info("\n💾 Étape 5: Store dans vector store...")
        self.vector_store.bulk_insert(taxon_docs)
        logger.info(f"   ✅ Stockés dans vector store")
        
        logger.info("\n" + "="*80)
        logger.info("✅ PROJECTION TERMINÉE")
        logger.info("="*80 + "\n")
        
        return {
            'version': taxonomy_version,
            'taxons_count': len(taxon_docs),
            'validation': validation_result,
            'prereq_snapshot_path': snapshot_path,
            'timestamp': datetime.datetime.now()
        }
    
    
    # ========================================================================
    # VALIDATION STRUCTURELLE (✅ NOUVEAU)
    # ========================================================================
    
    def _validate_hierarchy_structure(self, hierarchy: Dict) -> Dict[str, Any]:
        """
        ✅ NOUVEAU: Validation structurelle offline
        
        Checks:
        - Cycles
        - Orphelins
        - Cohérence des chemins (path_ids)
        - Unicité des IDs
        - Profondeur cohérente
        """
        
        errors = []
        warnings = []
        
        nodes = hierarchy['nodes']
        edges = hierarchy.get('edges', [])
        
        # Build adjacency lists
        children_map = defaultdict(list)  # parent_id → [child_ids]
        parent_map = {}  # child_id → parent_id
        
        for edge in edges:
            parent_id = edge.get('from')
            child_id = edge.get('to')
            if parent_id and child_id:
                children_map[parent_id].append(child_id)
                parent_map[child_id] = parent_id
        
        node_ids = {node['uid'] for node in nodes}
        
        # === CHECK 1: Cycles ===
        cycles = self._detect_cycles(children_map, node_ids)
        if cycles:
            errors.append(f"Cycles détectés: {cycles}")
        
        # === CHECK 2: Orphelins ===
        roots = {nid for nid in node_ids if nid not in parent_map}
        orphans = {nid for nid in node_ids if nid not in roots and nid not in children_map and nid not in parent_map}
        
        if len(roots) == 0:
            errors.append("Aucune racine trouvée")
        elif len(roots) > 5:
            warnings.append(f"{len(roots)} racines (multi-root autorisé mais vérifier)")
        
        if orphans:
            errors.append(f"{len(orphans)} nœuds orphelins: {list(orphans)[:5]}")
        
        # === CHECK 3: Unicité des IDs ===
        if len(node_ids) != len(nodes):
            errors.append("IDs dupliqués détectés")
        
        # === CHECK 4: Cohérence path_ids ===
        for node in nodes:
            path_ids = node.get('path_ids', [])
            node_id = node['uid']
            
            # Vérifier que path_ids contient les ancêtres
            if path_ids:
                # Le dernier élément devrait être le nœud lui-même ou son parent
                if node_id not in path_ids and parent_map.get(node_id) not in path_ids:
                    warnings.append(f"Nœud {node_id}: path_ids incohérent")
        
        # === CHECK 5: Profondeur cohérente ===
        for node in nodes:
            depth = node.get('depth', 0)
            path_ids = node.get('path_ids', [])
            
            # Depth devrait correspondre à len(path_ids) - 1 (ou len(path_ids))
            if len(path_ids) > 0 and abs(depth - len(path_ids)) > 1:
                warnings.append(f"Nœud {node['uid']}: depth={depth} vs path_ids={len(path_ids)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'stats': {
                'nodes_count': len(nodes),
                'edges_count': len(edges),
                'roots_count': len(roots),
                'orphans_count': len(orphans),
                'cycles_count': len(cycles)
            }
        }
    
    
    def _detect_cycles(self, children_map: Dict, node_ids: Set[str]) -> List[List[str]]:
        """Détecte les cycles dans le graphe"""
        
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            if node in rec_stack:
                # Cycle détecté
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for child in children_map.get(node, []):
                dfs(child, path[:])
            
            rec_stack.remove(node)
        
        for node_id in node_ids:
            if node_id not in visited:
                dfs(node_id, [])
        
        return cycles
    
    
    # ========================================================================
    # PREREQ SNAPSHOT (✅ NOUVEAU)
    # ========================================================================
    
    def _build_prereq_snapshot(
        self,
        hierarchy: Dict,
        taxonomy_version: str
    ) -> PrereqSnapshot:
        """
        ✅ NOUVEAU: Construit le cache KV des prereqs
        
        Inclut:
        - prereq_hard[label_id] → set(prereq_ids)
        - prereq_soft[label_id] → set(prereq_ids)
        - closure_hard[label_id] → set(prereq_ids transitifs)
        - incompatible[label_id] → set(incompatible_ids)
        """
        
        snapshot = PrereqSnapshot(
            taxonomy_version=taxonomy_version,
            created_at=datetime.datetime.now().isoformat()
        )
        
        # Extraire prereqs depuis nodes
        for node in hierarchy['nodes']:
            node_id = node['uid']
            
            prereq_hard = set(node.get('prereq_hard_ids', []))
            prereq_soft = set(node.get('prereq_soft_ids', []))
            incompatible = set(node.get('incompatible_ids', []))
            
            if prereq_hard:
                snapshot.prereq_hard[node_id] = prereq_hard
            
            if prereq_soft:
                snapshot.prereq_soft[node_id] = prereq_soft
            
            if incompatible:
                snapshot.incompatible[node_id] = incompatible
        
        # ✅ Fermeture transitive des prereqs hard
        logger.info("   📊 Calcul fermeture transitive...")
        snapshot.closure_hard = self._compute_transitive_closure(snapshot.prereq_hard)
        logger.info(f"      ✅ {len(snapshot.closure_hard)} fermetures calculées")
        
        return snapshot
    
    
    def _compute_transitive_closure(
        self,
        prereq_map: Dict[str, Set[str]]
    ) -> Dict[str, Set[str]]:
        """
        Calcule la fermeture transitive des prereqs hard
        
        Exemple:
        - A requires B
        - B requires C
        → closure[A] = {B, C}
        """
        
        closure = {}
        
        for node_id in prereq_map:
            visited = set()
            queue = deque(list(prereq_map[node_id]))
            
            while queue:
                prereq_id = queue.popleft()
                
                if prereq_id in visited:
                    continue
                
                visited.add(prereq_id)
                
                # Ajouter les prereqs transitifs
                if prereq_id in prereq_map:
                    for transitive_prereq in prereq_map[prereq_id]:
                        if transitive_prereq not in visited:
                            queue.append(transitive_prereq)
            
            closure[node_id] = visited
        
        return closure
    
    
    # ========================================================================
    # TAXON DOC ENRICHI (✅ CORRIGÉ)
    # ========================================================================
    
    def _create_taxon_doc(
        self,
        node: Dict,
        hierarchy: Dict,
        prereq_snapshot: PrereqSnapshot
    ) -> TaxonDoc:
        """
        ✅ CORRIGÉ: Créer TaxonDoc enrichi
        
        Changements:
        - index_text enrichi (breadcrumb + prereq_hint + children)
        - prereq_hint_text pour retrieval
        - children_names pour contexte
        """
        
        # === A. TEXTE INDEXÉ ===
        breadcrumb = self._build_breadcrumb(node, hierarchy)
        examples = self._get_examples(node)
        
        # ✅ NOUVEAU: prereq_hint_text
        prereq_hint = self._build_prereq_hint(node, prereq_snapshot)
        
        # ✅ NOUVEAU: children_names
        children_names = self._get_children_names(node, hierarchy)
        
        # Créer TaxonDoc
        doc = TaxonDoc(
            title=node.get('name', ''),
            definition=node.get('definition', node.get('description', '')),
            synonyms=node.get('synonyms', []),
            examples=examples,
            breadcrumb=breadcrumb,
            prereq_hint_text=prereq_hint,  # ✅ NOUVEAU
            children_names=children_names,  # ✅ NOUVEAU
            
            # Metadata
            taxon_id=node['uid'],
            taxonomy_version=prereq_snapshot.taxonomy_version,
            taxon_type=node.get('dgraph.type', ['Unknown'])[0] if isinstance(node.get('dgraph.type'), list) else node.get('dgraph.type', 'Unknown'),
            
            parent_ids=self._get_parent_ids(node),
            child_ids=self._get_child_ids(node, hierarchy),
            path_ids=node.get('path_ids', []),
            depth=self._calculate_depth(node),
            
            prereq_hard_ids=list(prereq_snapshot.prereq_hard.get(node['uid'], set())),
            prereq_soft_ids=list(prereq_snapshot.prereq_soft.get(node['uid'], set())),
            incompatible_ids=list(prereq_snapshot.incompatible.get(node['uid'], set())),
            required_slots=node.get('required_slots', []),
            
            domain=node.get('domain', ''),
            category=node.get('category', 'default'),
            
            embedder_id=self.embedder.model_name if hasattr(self.embedder, 'model_name') else 'default'
        )
        
        # Build index_text
        doc.build_index_text()
        
        # Generate embedding
        doc.embedding = self.embedder.embed(doc.index_text)
        
        return doc
    
    
    def _build_prereq_hint(
        self,
        node: Dict,
        prereq_snapshot: PrereqSnapshot
    ) -> str:
        """
        ✅ NOUVEAU: Construit prereq_hint_text pour retrieval
        
        Exemple: "Souvent requis: Dataset labellisé, Features sélectionnées"
        """
        
        node_id = node['uid']
        
        hard_prereqs = prereq_snapshot.prereq_hard.get(node_id, set())
        soft_prereqs = prereq_snapshot.prereq_soft.get(node_id, set())
        
        hints = []
        
        if hard_prereqs:
            # Chercher noms des prereqs (si disponibles)
            prereq_names = [self._get_node_name(pid) for pid in list(hard_prereqs)[:3]]
            prereq_names = [n for n in prereq_names if n]
            
            if prereq_names:
                hints.append(f"Requis: {', '.join(prereq_names)}")
        
        if soft_prereqs and not hard_prereqs:
            prereq_names = [self._get_node_name(pid) for pid in list(soft_prereqs)[:2]]
            prereq_names = [n for n in prereq_names if n]
            
            if prereq_names:
                hints.append(f"Recommandé: {', '.join(prereq_names)}")
        
        return " ; ".join(hints) if hints else ""
    
    
    def _get_children_names(self, node: Dict, hierarchy: Dict) -> str:
        """
        ✅ NOUVEAU: Récupère noms des enfants directs
        
        Exemple: "Regression, Classification, Clustering"
        """
        
        child_ids = self._get_child_ids(node, hierarchy)
        
        if not child_ids:
            return ""
        
        children_names = []
        for child_id in child_ids[:5]:  # Max 5 enfants
            child_name = self._get_node_name(child_id)
            if child_name:
                children_names.append(child_name)
        
        return ", ".join(children_names) if children_names else ""
    
    
    # ========================================================================
    # HELPERS (inchangés majoritairement)
    # ========================================================================
    
    def _extract_hierarchy(self) -> Dict:
        """Extrait hiérarchie depuis graph"""
        # Votre implémentation actuelle
        # (query Dgraph, etc.)
        pass
    
    
    def _build_breadcrumb(self, node: Dict, hierarchy: Dict) -> str:
        """Construit breadcrumb (ancêtres)"""
        # Votre implémentation actuelle
        pass
    
    
    def _get_examples(self, node: Dict) -> List[str]:
        """Récupère exemples du node"""
        return node.get('examples', node.get('examplePrompts', []))
    
    
    def _get_parent_ids(self, node: Dict) -> List[str]:
        """Récupère parent IDs"""
        # Votre implémentation actuelle
        pass
    
    
    def _get_child_ids(self, node: Dict, hierarchy: Dict) -> List[str]:
        """Récupère child IDs"""
        # Votre implémentation actuelle
        pass
    
    
    def _calculate_depth(self, node: Dict) -> int:
        """Calcule profondeur"""
        return node.get('depth', len(node.get('path_ids', [])))
    
    
    def _get_node_name(self, node_id: str) -> str:
        """Récupère nom d'un node par ID (via cache ou graph)"""
        # Implémentation selon votre setup
        # (peut nécessiter un cache node_id → name)
        pass