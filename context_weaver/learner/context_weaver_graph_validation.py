#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Intégration du Graph Structure Learner dans Context Weaver
✅ REFACTORISÉ: Utilise TaxonomyPipeline au lieu de BM25/Embedding/Fusion séparés
"""

import logging
from pathlib import Path
from typing import Dict, List, Any
from graph_structure_learner import GraphStructureLearner

logger = logging.getLogger(__name__)


class ContextWeaverWithGraphValidation:
    """
    Context Weaver étendu avec validation par Graph Structure Learner
    
    ✅ REFACTORISÉ: Pipeline simplifié
    1. Classification OSS
    2. Normalisation
    3. **TaxonomyPipeline (Retrieval + Validation intégrés)**
    4. Context Weaver final
    """
    
    def __init__(
        self,
        oss_classifier,
        normalizer,
        taxonomy_pipeline,  # ✅ NOUVEAU: Remplace BM25/Embedding/Fusion
        context_weaver,
        graph_learner_model_path: Path = None
    ):
        """
        Initialise le pipeline avec Graph Learner
        
        Args:
            oss_classifier: Classifier OSS 20B
            normalizer: Normalizer taxonomique
            taxonomy_pipeline: Pipeline taxonomy complet (Retrieval + Validation)
            context_weaver: Assembleur de contexte
            graph_learner_model_path: Chemin du modèle Graph Learner
        """
        self.oss_classifier = oss_classifier
        self.normalizer = normalizer
        self.taxonomy_pipeline = taxonomy_pipeline  # ✅ REFACTORISÉ
        self.context_weaver = context_weaver
        
        # === Graph Structure Learner ===
        self.graph_learner = GraphStructureLearner(model_path=graph_learner_model_path)
        
        logger.info("✅ Context Weaver avec Graph Validation initialisé")
    
    
    def process(
        self, 
        user_context: str,
        conversation_id: str = "default",
        session_state: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Pipeline complet avec validation des structures
        
        Args:
            user_context: Contexte utilisateur
            conversation_id: ID de conversation
            session_state: État de session
            
        Returns:
            Résultat complet incluant scores de validation
        """
        logger.info("=" * 80)
        logger.info("🔄 CONTEXT WEAVER AVEC GRAPH VALIDATION")
        logger.info("=" * 80)
        
        # === ÉTAPE 1: Classification OSS ===
        logger.info("\n1️⃣ Classification OSS...")
        classification = self.oss_classifier.classify(user_context)
        
        logger.info(f"   • Domain: {classification.domain}")
        logger.info(f"   • Task: {classification.task}")
        logger.info(f"   • Variables: {len(classification.variables)}")
        
        # === ÉTAPE 2: Normalisation ===
        logger.info("\n2️⃣ Normalisation taxonomique...")
        normalized = self.normalizer.normalize(classification)
        
        # === ÉTAPE 3: TAXONOMY PIPELINE (Retrieval + Validation intégrés) ===
        logger.info("\n3️⃣ Taxonomy Pipeline (Retrieval + Validation)...")
        
        # Préparer contexte enrichi
        enriched_context = {
            'domain': classification.domain,
            'task': classification.task,
            'variables': classification.variables,
            'key_variables': list(normalized.variables.values())[:10]
        }
        
        # Ajouter structure hint du learner
        if self.graph_learner:
            try:
                structure_hypothesis = self.graph_learner.predict_structure(
                    context={
                        'domain': classification.domain,
                        'variables': enriched_context['key_variables'],
                        'task': classification.task
                    },
                    candidates=[],
                    prereq_cache=None  # Ou passer PrereqSnapshot si disponible
                )
                
                enriched_context['structure_hint'] = {
                    'primary_label_id': structure_hypothesis.primary_label_id,
                    'expected_prereqs': list(structure_hypothesis.expected_prereq_hard_ids),
                    'confidence': structure_hypothesis.confidence
                }
                
                logger.info(f"   • Structure hint: {structure_hypothesis.primary_label_id}")
                logger.info(f"   • Confidence: {structure_hypothesis.confidence:.3f}")
                
            except Exception as e:
                logger.warning(f"   ⚠️ Learner prediction failed: {e}")
        
        # ✅ REFACTORISÉ: Appeler TaxonomyPipeline au lieu de BM25/Embedding/Fusion
        from context_weaver.taxonomy.taxonomy_models import ConversationState
        
        conv_state = ConversationState(conversation_id=conversation_id)
        if session_state:
            if 'confirmed_taxons' in session_state:
                conv_state.confirmed_taxons = session_state['confirmed_taxons']
            if 'filled_slots' in session_state:
                conv_state.filled_slots = session_state['filled_slots']
        
        taxonomy_output = self.taxonomy_pipeline.process(
            user_query=user_context,
            user_context=enriched_context,
            conversation_state=conv_state
        )
        
        logger.info(f"   • Status: {taxonomy_output.status}")
        logger.info(f"   • Can access graph: {taxonomy_output.can_access_graph}")
        
        # === ÉTAPE 4: Validation Graph Learner (optionnelle) ===
        logger.info("\n4️⃣ Validation Graph Learner...")
        
        validated_results = []
        
        if taxonomy_output.retrieval_result:
            validated_results = self._validate_candidates(
                taxonomy_output.retrieval_result.candidates,
                classification,
                normalized
            )
        
        # === ÉTAPE 5: Context Weaver final ===
        logger.info("\n5️⃣ Assemblage du contexte...")
        
        # Convertir taxonomy output en hybrid results
        from context_weaver.models.schemas import HybridSearchResults, SearchResult
        
        search_results_list = []
        
        if taxonomy_output.retrieval_result:
            for candidate in taxonomy_output.retrieval_result.candidates[:10]:
                result = SearchResult(
                    id=candidate.taxon_id,
                    name=candidate.name,
                    domain=candidate.metadata.get('domain', ''),
                    type="taxon",
                    score=candidate.final_score,
                    method="taxonomy_rrf",
                    content={
                        'definition': candidate.definition,
                        'breadcrumb': candidate.breadcrumb,
                        'depth': candidate.depth
                    },
                    metadata=candidate.metadata
                )
                search_results_list.append(result)
        
        hybrid_results = HybridSearchResults(
            results=search_results_list,
            bm25_count=taxonomy_output.retrieval_result.bm25_count if taxonomy_output.retrieval_result else 0,
            embedding_count=taxonomy_output.retrieval_result.dense_count if taxonomy_output.retrieval_result else 0,
            final_count=len(search_results_list),
            fusion_method="taxonomy_rrf"
        )
        
        context_output = self.context_weaver.weave(
            classification,
            normalized,
            hybrid_results
        )
        
        # === RÉSULTAT FINAL ===
        logger.info("\n✅ Pipeline terminé")
        
        return {
            'classification': classification,
            'normalized': normalized,
            'taxonomy_output': taxonomy_output,
            'search_results': hybrid_results,
            'context_output': context_output,
            'validation_summary': self._get_validation_summary(validated_results)
        }
    
    
    def _validate_candidates(
        self,
        candidates: List,
        classification,
        normalized
    ) -> List:
        """
        Valide et score les candidats avec Graph Learner
        
        Args:
            candidates: Candidats du retrieval
            classification: Classification OSS
            normalized: Variables normalisées
            
        Returns:
            Candidats enrichis avec validation
        """
        logger.info(f"   🔍 Validation de {len(candidates)} structures...")
        
        validated_candidates = []
        
        context = {
            'domain': classification.domain,
            'variables': list(normalized.variables.values()),
            'task': classification.task
        }
        
        for candidate in candidates:
            # Convertir TaxonCandidate en structure pour validation
            structure = {
                'id': candidate.taxon_id,
                'name': candidate.name,
                'domain': candidate.metadata.get('domain', ''),
                'type': 'taxon',
                'dgraph.type': 'TaxonomyNode',
                'definition': candidate.definition,
                'breadcrumb': candidate.breadcrumb
            }
            
            # Valider avec Graph Learner
            try:
                validation = self.graph_learner.validate_structure(structure, context)
                
                # Enrichir metadata
                if not hasattr(candidate, 'metadata') or candidate.metadata is None:
                    candidate.metadata = {}
                
                candidate.metadata['graph_validation'] = {
                    'score': validation['quality_score'],
                    'confidence': validation['confidence'],
                    'category': validation['quality_category'],
                    'issues': validation.get('issues', [])
                }
                
                # Ajuster score final (optionnel)
                # candidate.final_score *= (1.0 + validation['quality_score'] * 0.1)
                
            except Exception as e:
                logger.warning(f"   ⚠️ Validation failed for {candidate.name}: {e}")
                candidate.metadata['graph_validation'] = {
                    'score': 0.5,
                    'confidence': 0.0,
                    'category': 'MEDIUM',
                    'issues': ['validation_error']
                }
            
            validated_candidates.append(candidate)
        
        # Stats
        if validated_candidates:
            high = sum(1 for c in validated_candidates if c.metadata['graph_validation']['category'] == 'HIGH')
            medium = sum(1 for c in validated_candidates if c.metadata['graph_validation']['category'] == 'MEDIUM')
            low = sum(1 for c in validated_candidates if c.metadata['graph_validation']['category'] == 'LOW')
            
            logger.info(f"   ✅ HIGH: {high} | MEDIUM: {medium} | LOW: {low}")
        
        return validated_candidates
    
    
    def _get_validation_summary(self, validated_candidates: List) -> Dict[str, Any]:
        """Génère un résumé des validations"""
        
        if not validated_candidates:
            return {
                'total_structures': 0,
                'high_quality': 0,
                'medium_quality': 0,
                'low_quality': 0,
                'avg_validation_score': 0.0,
                'avg_confidence': 0.0
            }
        
        categories = [
            c.metadata.get('graph_validation', {}).get('category', 'MEDIUM')
            for c in validated_candidates
        ]
        
        scores = [
            c.metadata.get('graph_validation', {}).get('score', 0.5)
            for c in validated_candidates
        ]
        
        confidences = [
            c.metadata.get('graph_validation', {}).get('confidence', 0.0)
            for c in validated_candidates
        ]
        
        return {
            'total_structures': len(validated_candidates),
            'high_quality': categories.count('HIGH'),
            'medium_quality': categories.count('MEDIUM'),
            'low_quality': categories.count('LOW'),
            'avg_validation_score': sum(scores) / len(scores) if scores else 0.0,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0
        }
    
    
    def train_graph_learner(self, graph_data: Dict[str, Any]):
        """
        Entraîne le Graph Learner avec de nouvelles données
        
        Args:
            graph_data: Structure du graphe {nodes: [...], edges: [...]}
        """
        logger.info("🎓 Entraînement du Graph Learner...")
        self.graph_learner.train_from_graph(graph_data)
        logger.info("✅ Entraînement terminé")
    
    
    def get_learner_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du Graph Learner"""
        return self.graph_learner.get_learning_metrics()


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

def example_usage():
    """Exemple complet d'utilisation"""
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 80)
    print("📘 EXEMPLE: Context Weaver avec Graph Validation")
    print("=" * 80 + "\n")
    
    # === SETUP ===
    from context_weaver.services.oss_classifier import OSSClassifierClient
    from context_weaver.services.normalizer import Normalizer
    from context_weaver.services.context_weaver import ContextWeaver
    from context_weaver.data.vector_store import VectorStore
    from context_weaver.pipeline.taxonomy_pipeline import TaxonomyPipeline
    from context_weaver.taxonomy.taxonomy_retriever import RetrievalConfig
    
    # Initialiser les services
    oss_classifier = OSSClassifierClient()
    normalizer = Normalizer()
    context_weaver = ContextWeaver()
    
    # ✅ REFACTORISÉ: Créer TaxonomyPipeline au lieu de BM25/Embedding/Fusion
    vector_store = VectorStore()
    vector_store.initialize()
    
    # Embedder wrapper
    from context_weaver.services.embedder_wrapper import EmbedderWrapper
    embedder = EmbedderWrapper(oss_client=oss_classifier)
    
    retrieval_config = RetrievalConfig(
        dense_top_k=100,
        bm25_top_k=100,
        rrf_k=60,
        final_top_n=30,
        boost_by_depth=True
    )
    
    taxonomy_pipeline = TaxonomyPipeline(
        vector_store=vector_store,
        embedder=embedder,
        retrieval_config=retrieval_config,
        taxonomy_metadata={}
    )
    
    # === CRÉER LE PIPELINE AVEC GRAPH VALIDATION ===
    pipeline = ContextWeaverWithGraphValidation(
        oss_classifier=oss_classifier,
        normalizer=normalizer,
        taxonomy_pipeline=taxonomy_pipeline,  # ✅ REFACTORISÉ
        context_weaver=context_weaver,
        graph_learner_model_path=Path("./data/graph_structure_model.json")
    )
    
    # === ENTRAÎNER LE GRAPH LEARNER (une fois) ===
    print("🎓 Phase d'entraînement...")
    
    from train_graph_learner import extract_from_database
    from utils.dataset_database import DatasetDatabase
    
    database = DatasetDatabase()
    graph_data = extract_from_database(database)
    
    pipeline.train_graph_learner(graph_data)
    
    print("\n" + "-" * 80)
    
    # === UTILISER LE PIPELINE ===
    print("\n🔄 Traitement d'une requête...")
    
    user_context = "Je veux créer une facture de vente avec TVA"
    
    result = pipeline.process(
        user_context,
        conversation_id="example_001"
    )
    
    # === AFFICHER LES RÉSULTATS ===
    print("\n" + "=" * 80)
    print("📊 RÉSULTATS")
    print("=" * 80)
    
    print("\n🎯 Classification:")
    print(f"  • Domain: {result['classification'].domain}")
    print(f"  • Task: {result['classification'].task}")
    print(f"  • Variables: {', '.join(result['classification'].variables[:3])}...")
    
    print("\n🔍 Taxonomy Pipeline:")
    taxonomy = result['taxonomy_output']
    print(f"  • Status: {taxonomy.status}")
    print(f"  • Can access graph: {taxonomy.can_access_graph}")
    
    if taxonomy.validated_taxon_name:
        print(f"  • Validated: {taxonomy.validated_taxon_name}")
    
    print("\n✅ Validation Graph:")
    validation = result['validation_summary']
    print(f"  • HIGH quality: {validation['high_quality']}")
    print(f"  • MEDIUM quality: {validation['medium_quality']}")
    print(f"  • LOW quality: {validation['low_quality']}")
    print(f"  • Score moyen: {validation['avg_validation_score']:.3f}")
    print(f"  • Confiance: {validation['avg_confidence']:.3f}")
    
    print("\n🎯 Top 3 résultats:")
    for i, result_item in enumerate(result['search_results'].results[:3], 1):
        print(f"\n  {i}. {result_item.name}")
        print(f"     Score: {result_item.score:.3f}")
        if 'graph_validation' in result_item.metadata:
            val = result_item.metadata['graph_validation']
            print(f"     Validation: {val['category']} (score={val['score']:.3f})")
    
    # === MÉTRIQUES DU LEARNER ===
    print("\n" + "=" * 80)
    print("📈 MÉTRIQUES DU GRAPH LEARNER")
    print("=" * 80)
    
    metrics = pipeline.get_learner_metrics()
    print(f"  • Graphes vus: {metrics['total_graphs_seen']}")
    print(f"  • Nœuds analysés: {metrics['total_nodes_analyzed']}")
    print(f"  • Patterns de nœuds: {metrics['node_patterns_count']}")
    print(f"  • Taux de succès: {metrics['success_rate']:.2%}")
    
    print("\n" + "=" * 80)
    print("✅ TERMINÉ")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    example_usage()