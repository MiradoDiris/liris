#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module d'amélioration du logging pour Context Weaver Pipeline

À intégrer dans le pipeline pour résoudre les problèmes de traçabilité
"""

import time
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# 1. RESULT TRACER - Tracer les résultats à travers le pipeline
# ============================================================================

@dataclass
class StageTrace:
    """Trace d'une étape du pipeline"""
    name: str
    timestamp: datetime
    count: int
    duration_ms: float
    sample_ids: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class ResultTracer:
    """
    Tracer pour suivre les résultats du pipeline de bout en bout
    
    Usage:
        tracer = ResultTracer()
        tracer.log_stage("vector_search", vector_results)
        tracer.log_stage("validation", validated)
        tracer.print_summary()
    """
    
    def __init__(self):
        self.trace_id = str(uuid.uuid4())[:8]
        self.stages: List[StageTrace] = []
        self.start_time = time.time()
        
        logger.info(f"🔍 Nouveau trace: {self.trace_id}")
    
    def log_stage(
        self,
        stage_name: str,
        data: Any,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Logger une étape avec ses données
        
        Args:
            stage_name: Nom de l'étape
            data: Données (liste, dict, ou objet avec __len__)
            details: Informations complémentaires
        """
        # Calculer le count
        if isinstance(data, (list, tuple)):
            count = len(data)
            sample_ids = [
                d.get('id', d.get('name', str(i)))
                for i, d in enumerate(data[:5])
                if isinstance(d, dict)
            ]
        elif isinstance(data, dict):
            count = len(data)
            sample_ids = list(data.keys())[:5]
        elif hasattr(data, '__len__'):
            count = len(data)
            sample_ids = []
        else:
            count = 1
            sample_ids = []
        
        # Temps écoulé
        duration_ms = (time.time() - self.start_time) * 1000
        
        # Créer le trace
        trace = StageTrace(
            name=stage_name,
            timestamp=datetime.now(),
            count=count,
            duration_ms=duration_ms,
            sample_ids=sample_ids,
            details=details or {}
        )
        
        self.stages.append(trace)
        
        # Logger
        logger.info(
            f"[{self.trace_id}] {stage_name}: {count} items "
            f"({duration_ms:.0f}ms total)"
        )
        
        if sample_ids:
            logger.debug(f"  Sample IDs: {', '.join(sample_ids)}")
    
    def print_summary(self):
        """Affiche un résumé du traçage"""
        print("\n" + "=" * 100)
        print(f"📊 TRACE SUMMARY [{self.trace_id}]")
        print("=" * 100)
        
        if not self.stages:
            print("⚠️  Aucune étape tracée")
            return
        
        total_duration = self.stages[-1].duration_ms
        
        print(f"\n⏱️  Durée totale: {total_duration:.0f}ms")
        print(f"📈 Nombre d'étapes: {len(self.stages)}\n")
        
        # Table
        print(f"{'#':<3} {'Étape':<35} {'Count':<10} {'Durée':<12} {'Samples'}")
        print("-" * 100)
        
        for i, stage in enumerate(self.stages, 1):
            samples_preview = ', '.join(stage.sample_ids[:3])
            if len(stage.sample_ids) > 3:
                samples_preview += "..."
            
            print(
                f"{i:<3} {stage.name:<35} "
                f"{stage.count:<10} {stage.duration_ms:<12.0f} "
                f"{samples_preview}"
            )
        
        print("=" * 100 + "\n")
    
    def get_stage_summary(self) -> Dict[str, Any]:
        """Retourne un résumé structuré"""
        return {
            'trace_id': self.trace_id,
            'total_duration_ms': self.stages[-1].duration_ms if self.stages else 0,
            'num_stages': len(self.stages),
            'stages': [
                {
                    'name': s.name,
                    'count': s.count,
                    'duration_ms': s.duration_ms
                }
                for s in self.stages
            ]
        }


# ============================================================================
# 2. PIPELINE MONITOR - Monitoring temps réel
# ============================================================================

class PipelineMonitor:
    """
    Monitor temps réel du pipeline avec affichage progressif
    
    Usage:
        monitor = PipelineMonitor()
        
        monitor.start_stage("Vector Search")
        # ... code ...
        monitor.end_stage(len(results), "Top 50 results")
        
        monitor.print_summary()
    """
    
    def __init__(self):
        self.stages = []
        self.current_stage = None
    
    def start_stage(self, name: str):
        """Démarre une étape"""
        self.current_stage = {
            'name': name,
            'start_time': time.time(),
            'status': 'running'
        }
        print(f"\n┌─ {name}")
        logger.info(f"▶️  Début: {name}")
    
    def end_stage(
        self,
        count: int,
        details: str = "",
        metadata: Optional[Dict] = None
    ):
        """
        Termine une étape
        
        Args:
            count: Nombre d'items traités
            details: Description optionnelle
            metadata: Métadonnées supplémentaires
        """
        if self.current_stage:
            self.current_stage['end_time'] = time.time()
            self.current_stage['duration'] = (
                self.current_stage['end_time'] - self.current_stage['start_time']
            ) * 1000
            self.current_stage['count'] = count
            self.current_stage['status'] = 'done'
            self.current_stage['metadata'] = metadata or {}
            
            print(f"│   ✅ {count} items ({self.current_stage['duration']:.0f}ms)")
            
            if details:
                print(f"│   {details}")
            
            if metadata:
                for key, value in metadata.items():
                    print(f"│   • {key}: {value}")
            
            print(f"└─\n")
            
            logger.info(
                f"✅ Fin: {self.current_stage['name']} - "
                f"{count} items - {self.current_stage['duration']:.0f}ms"
            )
            
            self.stages.append(self.current_stage)
            self.current_stage = None
    
    def print_summary(self):
        """Affiche un résumé visuel"""
        print("\n" + "=" * 100)
        print("📊 PIPELINE SUMMARY")
        print("=" * 100)
        
        if not self.stages:
            print("⚠️  Aucune étape complétée")
            return
        
        total_time = sum(s['duration'] for s in self.stages)
        
        print(f"\n⏱️  Temps total: {total_time:.0f}ms")
        print(f"📊 Nombre d'étapes: {len(self.stages)}\n")
        
        # Graphique en barres
        print(f"{'#':<3} {'Étape':<30} {'Count':<8} {'Durée':<10} {'%':<6} {'Graphique'}")
        print("-" * 100)
        
        for i, stage in enumerate(self.stages, 1):
            pct = (stage['duration'] / total_time * 100) if total_time > 0 else 0
            bar_length = int(pct / 2)
            bar = "█" * bar_length
            
            print(
                f"{i:<3} {stage['name']:<30} "
                f"{stage['count']:<8} {stage['duration']:<10.0f} "
                f"{pct:<6.1f} {bar}"
            )
        
        print("\n" + "=" * 100 + "\n")


# ============================================================================
# 3. RESULT MAPPER - Mapper les transformations
# ============================================================================

def log_result_mapping(
    vector_results: List[Dict],
    validated: List[Dict],
    skeleton_nodes: List[Any],
    templates: Optional[List[Dict]] = None,
    samples: Optional[List[Dict]] = None
):
    """
    Logger le mapping complet des résultats à travers le pipeline
    
    Args:
        vector_results: Résultats du Vector Store
        validated: Structures validées
        skeleton_nodes: Nœuds du decision tree
        templates: Templates de génération (optionnel)
        samples: Samples générés (optionnel)
    """
    print("\n" + "=" * 100)
    print("🗺️  MAPPING COMPLET DES RÉSULTATS")
    print("=" * 100)
    
    # 1. Vue d'ensemble
    print("\n📊 VUE D'ENSEMBLE\n")
    print(f"1️⃣  Vector Store Search:   {len(vector_results):>5} résultats")
    print(f"2️⃣  Après validation:      {len(validated):>5} structures")
    print(f"3️⃣  Skeleton nodes:        {len(skeleton_nodes):>5} nœuds")
    
    if templates is not None:
        print(f"4️⃣  Templates générés:     {len(templates):>5} templates")
    
    if samples is not None:
        print(f"5️⃣  Samples finaux:        {len(samples):>5} samples")
    
    # 2. Taux de conservation
    print("\n📉 TAUX DE CONSERVATION\n")
    
    if vector_results:
        val_rate = len(validated) / len(vector_results) * 100
        print(f"Vector → Validated:   {val_rate:>5.1f}% conservés")
    
    if validated:
        node_rate = len(skeleton_nodes) / len(validated) * 100
        print(f"Validated → Nodes:    {node_rate:>5.1f}% convertis en nœuds")
    
    # 3. Détail des structures validées
    if validated:
        print(f"\n📋 DÉTAIL DES {len(validated)} STRUCTURES VALIDÉES\n")
        
        # Grouper par score
        high_score = [s for s in validated if s.get('score', 0) >= 0.7]
        mid_score = [s for s in validated if 0.4 <= s.get('score', 0) < 0.7]
        low_score = [s for s in validated if s.get('score', 0) < 0.4]
        
        print(f"  🟢 Score élevé (≥0.7):     {len(high_score):>3}")
        print(f"  🟡 Score moyen (0.4-0.7):  {len(mid_score):>3}")
        print(f"  🔴 Score faible (<0.4):    {len(low_score):>3}")
        
        # Top 10
        print(f"\n  Top 10 structures:")
        for i, struct in enumerate(sorted(validated, key=lambda x: x.get('score', 0), reverse=True)[:10], 1):
            name = struct.get('name', 'Unknown')[:50]
            score = struct.get('score', 0)
            struct_type = struct.get('type', 'unknown')
            print(f"    {i:>2}. {name:<50} (score: {score:.3f}, type: {struct_type})")
    
    # 4. Mapping vers les nodes
    if skeleton_nodes:
        print(f"\n🌳 {len(skeleton_nodes)} NŒUDS DANS LE SKELETON\n")
        
        for i, node in enumerate(skeleton_nodes, 1):
            field = getattr(node, 'field', str(node))
            print(f"  [{i}] {field}")
            
            # Chercher quelle structure a généré ce node
            source_structs = [
                s.get('name', '') for s in validated
                if field.lower() in s.get('name', '').lower()
            ]
            
            if source_structs:
                print(f"      ← Sources potentielles: {', '.join(source_structs[:3])}")
            
            # Afficher les propriétés du node
            if hasattr(node, 'ranges') and node.ranges:
                print(f"      • Ranges: {node.ranges}")
            if hasattr(node, 'groups') and node.groups:
                print(f"      • Groups: {node.groups}")
            if hasattr(node, 'levels') and node.levels:
                print(f"      • Levels: {node.levels}")
    
    # 5. Templates (si fournis)
    if templates:
        print(f"\n📝 {len(templates)} TEMPLATES DE GÉNÉRATION\n")
        
        for i, template in enumerate(templates, 1):
            name = template.get('name', f'Template {i}')
            print(f"  [{i}] {name}")
            
            if 'source_structures' in template:
                count = len(template['source_structures'])
                print(f"      • Utilise {count} structures sources")
            
            if 'variables' in template:
                print(f"      • Variables: {', '.join(template['variables'][:5])}")
    
    # 6. Samples (si fournis)
    if samples:
        print(f"\n✨ {len(samples)} SAMPLES GÉNÉRÉS\n")
        
        for i, sample in enumerate(samples, 1):
            desc = sample.get('description', f'Sample {i}')[:60]
            print(f"  [{i}] {desc}")
            
            if 'template_id' in sample:
                print(f"      ← Template: {sample['template_id']}")
            
            if 'variables_used' in sample:
                print(f"      • Variables: {', '.join(sample['variables_used'][:3])}")
    
    print("\n" + "=" * 100 + "\n")


# ============================================================================
# 4. CONSISTENCY VALIDATOR - Validation de cohérence
# ============================================================================

def validate_pipeline_consistency(
    vector_results: int,
    validated: int,
    skeleton_nodes: int,
    templates: Optional[int] = None,
    samples: Optional[int] = None
) -> List[str]:
    """
    Valide la cohérence du pipeline et retourne les warnings
    
    Args:
        vector_results: Nombre de résultats Vector Store
        validated: Nombre de structures validées
        skeleton_nodes: Nombre de nœuds dans le skeleton
        templates: Nombre de templates générés (optionnel)
        samples: Nombre de samples générés (optionnel)
        
    Returns:
        Liste des warnings (vide si tout OK)
    """
    warnings = []
    
    # Check 1: Résultats initiaux
    if vector_results < 10:
        warnings.append(
            f"⚠️  Peu de résultats trouvés dans Vector Store: {vector_results} "
            f"(recommandé: ≥10)"
        )
    
    # Check 2: Taux de validation
    if validated < vector_results * 0.5:
        rate = validated / vector_results * 100 if vector_results > 0 else 0
        warnings.append(
            f"⚠️  Beaucoup de résultats éliminés par la validation: "
            f"{vector_results} → {validated} ({rate:.1f}% conservés)"
        )
    
    # Check 3: Nodes dans le skeleton
    if skeleton_nodes < 3:
        warnings.append(
            f"⚠️  Peu de nœuds dans le skeleton: {skeleton_nodes} "
            f"(recommandé: ≥3)"
        )
    
    if skeleton_nodes > 20:
        warnings.append(
            f"⚠️  Beaucoup de nœuds dans le skeleton: {skeleton_nodes} "
            f"(peut indiquer un sur-apprentissage)"
        )
    
    # Check 4: Templates
    if templates is not None:
        if templates == 0:
            warnings.append("❌ Aucun template de génération créé!")
        elif templates < 2:
            warnings.append(
                f"⚠️  Peu de templates générés: {templates} "
                f"(recommandé: ≥2 pour plus de diversité)"
            )
    
    # Check 5: Samples
    if samples is not None:
        if samples == 0:
            warnings.append("❌ Aucun sample généré!")
        elif samples < 5:
            warnings.append(
                f"⚠️  Peu de samples générés: {samples} "
                f"(recommandé: ≥5)"
            )
    
    # Afficher les warnings
    if warnings:
        print("\n" + "=" * 100)
        print("⚠️  VÉRIFICATIONS DE COHÉRENCE")
        print("=" * 100 + "\n")
        
        for warning in warnings:
            print(warning)
            logger.warning(warning)
        
        print("\n" + "=" * 100 + "\n")
    else:
        print("\n✅ Toutes les vérifications de cohérence sont OK\n")
        logger.info("✅ Pipeline cohérent")
    
    return warnings


# ============================================================================
# 5. INTEGRATION HELPER - Aide à l'intégration dans le pipeline existant
# ============================================================================

class EnhancedPipelineLogger:
    """
    Logger amélioré à intégrer dans ContextWeaverPipeline
    
    Usage dans main_pipeline.py:
    
        # Dans __init__
        self.enhanced_logger = EnhancedPipelineLogger()
        
        # Dans run()
        self.enhanced_logger.start_pipeline(user_context)
        
        # À chaque étape
        self.enhanced_logger.log_stage("embeddings", embeddings)
        self.enhanced_logger.log_stage("vector_search", vector_results)
        # ... etc
        
        # À la fin
        self.enhanced_logger.end_pipeline(output)
    """
    
    def __init__(self):
        self.tracer = None
        self.monitor = None
    
    def start_pipeline(self, user_context: str):
        """Démarre le logging amélioré"""
        self.tracer = ResultTracer()
        self.monitor = PipelineMonitor()
        
        logger.info("=" * 80)
        logger.info("🚀 PIPELINE START (Enhanced Logging)")
        logger.info("=" * 80)
        logger.info(f"Context: {user_context[:100]}...")
        logger.info(f"Trace ID: {self.tracer.trace_id}")
        logger.info("=" * 80)
    
    def log_stage(self, stage_name: str, data: Any, **kwargs):
        """Logger une étape"""
        if self.tracer:
            self.tracer.log_stage(stage_name, data, details=kwargs)
    
    def start_monitor_stage(self, name: str):
        """Démarre le monitoring d'une étape"""
        if self.monitor:
            self.monitor.start_stage(name)
    
    def end_monitor_stage(self, count: int, details: str = "", **metadata):
        """Termine le monitoring d'une étape"""
        if self.monitor:
            self.monitor.end_stage(count, details, metadata)
    
    def end_pipeline(self, output: Any):
        """Termine le pipeline et affiche les résumés"""
        if self.tracer:
            self.tracer.print_summary()
        
        if self.monitor:
            self.monitor.print_summary()
        
        logger.info("=" * 80)
        logger.info("✅ PIPELINE COMPLETE")
        logger.info("=" * 80)


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 100)
    print("🧪 TEST DES MODULES DE LOGGING AMÉLIORÉ")
    print("=" * 100)
    
    # Simuler des données
    vector_results = [{'id': f'v{i}', 'name': f'Result {i}', 'score': 0.8 - i*0.05} for i in range(50)]
    validated = vector_results[:40]  # Garde 40/50
    
    class FakeNode:
        def __init__(self, field, ranges=None):
            self.field = field
            self.ranges = ranges or []
    
    skeleton_nodes = [
        FakeNode('montant', ['<1000', '1000-5000', '>5000']),
        FakeNode('pays', ['FR', 'UE', 'INT']),
        FakeNode('frequency', ['low', 'medium', 'high'])
    ]
    
    # Test 1: Result Tracer
    print("\n" + "-" * 100)
    print("TEST 1: Result Tracer")
    print("-" * 100)
    
    tracer = ResultTracer()
    tracer.log_stage("vector_search", vector_results)
    tracer.log_stage("validation", validated)
    tracer.log_stage("skeleton_build", skeleton_nodes)
    tracer.print_summary()
    
    # Test 2: Pipeline Monitor
    print("\n" + "-" * 100)
    print("TEST 2: Pipeline Monitor")
    print("-" * 100)
    
    monitor = PipelineMonitor()
    
    monitor.start_stage("Vector Search")
    time.sleep(0.1)
    monitor.end_stage(len(vector_results), "Top 50 results")
    
    monitor.start_stage("Validation")
    time.sleep(0.05)
    monitor.end_stage(len(validated), "Filtered by score")
    
    monitor.start_stage("Skeleton Building")
    time.sleep(0.03)
    monitor.end_stage(len(skeleton_nodes), "3 nodes created")
    
    monitor.print_summary()
    
    # Test 3: Result Mapper
    print("\n" + "-" * 100)
    print("TEST 3: Result Mapper")
    print("-" * 100)
    
    log_result_mapping(
        vector_results,
        validated,
        skeleton_nodes
    )
    
    # Test 4: Consistency Validator
    print("\n" + "-" * 100)
    print("TEST 4: Consistency Validator")
    print("-" * 100)
    
    warnings = validate_pipeline_consistency(
        vector_results=len(vector_results),
        validated=len(validated),
        skeleton_nodes=len(skeleton_nodes),
        templates=3,
        samples=10
    )
    
    print(f"\n✅ Tests terminés - {len(warnings)} warnings détectés\n")