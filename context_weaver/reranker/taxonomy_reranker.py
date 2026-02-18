#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Taxonomy Reranker
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from pyparsing import Union

from context_weaver.taxonomy.taxonomy_models import TaxonCandidate

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class RerankingConfig:
    """Configuration des poids du reranking"""
    
    # Poids des composants (simplifié - pas de validation)
    rrf_weight: float = 0.7           # Base RRF
    metadata_boost_weight: float = 0.3  # Boost selon metadata enrichie
    
    # Bonus pour signaux forts
    bonus_has_description: float = 0.05
    bonus_has_prereqs: float = 0.03
    bonus_high_depth: float = 0.02  # Profondeur ≥ 3
    
    # Seuils
    min_final_score: float = 0.0
    max_final_score: float = 1.0


@dataclass
class ScoreAdjustment:
    """Détail d'un ajustement de score"""
    adjustment_type: str
    amount: float
    reason: str
    related_entity: Optional[str] = None


@dataclass
class RerankingResult:
    """Résultat détaillé du reranking pour un candidat"""
    taxon_id: str
    original_rrf_score: float
    original_rank: int
    final_score: float
    new_rank: int
    adjustments: List[ScoreAdjustment] = field(default_factory=list)
    total_adjustment: float = 0.0
    rrf_component: float = 0.0
    metadata_component: float = 0.0


# ============================================================================
# TAXONOMY RERANKER
# ============================================================================

class TaxonomyReranker:
    """
    ✅ SIMPLIFIÉ: Enrichissement Dgraph + Scoring
    
    Workflow:
    1. Batch retrieval Dgraph → enrichit metadata
    2. Calcule final_score = f(rrf, metadata_quality)
    3. Retourne candidats réordonnés
    
    ❌ Plus de:
    - Validation
    - Conversation state
    - Prereqs checking
    """
    
    def __init__(
        self, 
        dgraph_connector,
        config: Optional[RerankingConfig] = None
    ):
        """
        Args:
            dgraph_connector: Connector Dgraph pour enrichissement (peut être None)
            config: Configuration reranking
        """
        self.dgraph = dgraph_connector
        self.config = config or RerankingConfig()
        
        # ✅ AJOUTÉ: Flag pour savoir si Dgraph est disponible
        self.dgraph_available = dgraph_connector is not None
        
        logger.info("✅ TaxonomyReranker initialisé (mode simplifié)")
        logger.info(f"   • RRF weight: {self.config.rrf_weight}")
        logger.info(f"   • Metadata boost weight: {self.config.metadata_boost_weight}")
        
        # ✅ AJOUTÉ: Warning si Dgraph non disponible
        if not self.dgraph_available:
            logger.warning("⚠️ Dgraph non initialisé - enrichissement désactivé")
    
    
    def rerank(
        self,
        candidates: List[TaxonCandidate]
    ) -> Tuple[List[TaxonCandidate], List[RerankingResult]]:
        """
        ✅ SIMPLIFIÉ: Enrichit puis réordonne les candidats
        
        Args:
            candidates: Candidats post-RRF (metadata minimale)
            
        Returns:
            Tuple[List[TaxonCandidate], List[RerankingResult]]:
                - Candidats enrichis + réordonnés
                - Détails du reranking
        """
        
        logger.info("🔄 RERANKING (mode simplifié)")
        logger.info(f"   • Candidats: {len(candidates)}")
        
        if not candidates:
            logger.warning("⚠️ Aucun candidat à reranker")
            return [], []
        
        # === ÉTAPE 1: ENRICHISSEMENT DGRAPH ===
        # ✅ MODIFIÉ: Enrichissement conditionnel selon disponibilité Dgraph
        if self.dgraph_available:
            logger.info("📥 Enrichissement metadata Dgraph...")
            enriched_candidates = self._enrich_candidates_from_dgraph(candidates)
            logger.info(f"✅ {len(enriched_candidates)} candidats enrichis")
        else:
            logger.info("⏭️ Enrichissement Dgraph ignoré (non disponible)")
            enriched_candidates = candidates
        
        # === ÉTAPE 2: SCORING ===
        for rank, candidate in enumerate(enriched_candidates, 1):
            candidate.metadata['original_rank'] = rank
        
        reranking_results = []
        
        for candidate in enriched_candidates:
            # Calculer le final_score
            result = self._compute_final_score(candidate)
            
            candidate.final_score = result.final_score
            reranking_results.append(result)
        
        # Réordonner
        reranked_candidates = sorted(
            enriched_candidates,
            key=lambda c: c.final_score,
            reverse=True
        )
        
        # Mettre à jour les nouveaux rangs
        for new_rank, candidate in enumerate(reranked_candidates, 1):
            candidate.metadata['new_rank'] = new_rank
            
            for result in reranking_results:
                if result.taxon_id == candidate.taxon_id:
                    result.new_rank = new_rank
                    break
        
        self._log_reranking_changes(reranking_results)
        
        logger.info(f"✅ Reranking terminé: {len(reranked_candidates)} candidats")
        
        return reranked_candidates, reranking_results
    
    
    # ========================================================================
    # ENRICHISSEMENT DGRAPH
    # ========================================================================
    
    def _enrich_candidates_from_dgraph(
        self, 
        candidates: List[TaxonCandidate]
    ) -> List[TaxonCandidate]:
        """
        ✅ Batch retrieval Dgraph pour enrichir tous les candidats
        
        Enrichit:
        - description complète
        - prereq_hard_ids, prereq_soft_ids
        - incompatible_ids
        - required_slots
        - parent_ids, child_ids, path_ids
        - category, keywords, etc.
        
        Returns:
            Liste des candidats avec metadata.* enrichie
        """
        
        if not candidates:
            return candidates
        
        # ✅ AJOUTÉ: Vérification Dgraph disponible
        if not self.dgraph_available:
            logger.warning("⚠️ Dgraph non disponible - enrichissement ignoré")
            return candidates
        
        # Extraire tous les UIDs
        taxon_uids = [c.taxon_id for c in candidates]
        
        # Batch query Dgraph
        enrichment_data = self._batch_fetch_metadata(taxon_uids)
        
        # Enrichir chaque candidat
        for candidate in candidates:
            uid = candidate.taxon_id
            
            if uid not in enrichment_data:
                logger.warning(f"⚠️ Pas de metadata Dgraph pour {uid}")
                continue
            
            data = enrichment_data[uid]
            
            # Enrichir candidate.metadata avec TOUTES les données Dgraph
            candidate.metadata.update({
                # Description
                'description': data.get('description', ''),
                'definition': data.get('description', ''),
                
                # Prérequis
                'prereq_hard_ids': data.get('prereq_hard', []),
                'prereq_soft_ids': data.get('prereq_soft', []),
                'incompatible_ids': data.get('incompatible', []),
                'required_slots': data.get('required_slots', []),
                
                # Hiérarchie
                'parent_ids': data.get('parent_ids', []),
                'child_ids': data.get('child_ids', []),
                'path_ids': data.get('path_ids', []),
                
                # Autres
                'category': data.get('category', 'default'),
                'intentKeywords': data.get('intentKeywords', []),
                'actionKeywords': data.get('actionKeywords', []),
                'dgraph_type': data.get('dgraph.type', []),
            })
            
            # Enrichir candidate.definition (champ direct)
            if not candidate.definition and data.get('description'):
                candidate.definition = data['description']
            
            # Enrichir candidate.prereq_hint
            prereq_hard = data.get('prereq_hard', [])
            if prereq_hard:
                prereq_names = self._get_prereq_names(prereq_hard, enrichment_data)
                candidate.prereq_hint = f"Prérequis: {', '.join(prereq_names)}"
        
        return candidates
    
    
    def _batch_fetch_metadata(
        self, 
        taxon_uids: List[Union[str, Dict]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        ✅ CORRIGÉ: Batch retrieval Dgraph avec validation des UIDs
        
        Args:
            taxon_uids: Liste d'UIDs (peut contenir des dicts par erreur)
            
        Returns:
            Dict[uid → metadata]
        """
        
        # ✅ AJOUTÉ: Vérification early exit si Dgraph non disponible
        if not self.dgraph_available:
            logger.warning("⚠️ Dgraph non initialisé - enrichissement ignoré")
            return {}
        
        if not taxon_uids:
            return {}
        
        # ✅ VALIDATION DES UIDS
        from context_weaver.utils.uid_helpers import validate_uid_list
        
        validated_uids = validate_uid_list(taxon_uids)
        
        if not validated_uids:
            logger.error("❌ Aucun UID valide après validation")
            return {}
        
        if len(validated_uids) < len(taxon_uids):
            logger.warning(
                f"⚠️ {len(taxon_uids) - len(validated_uids)} UID(s) invalide(s) ignoré(s)"
            )
        
        # Construire la query Dgraph avec UIDs VALIDÉS
        uids_str = ", ".join(validated_uids)
        
        query = f"""
        {{
          nodes(func: uid({uids_str})) {{
            uid
            name
            description
            category
            depth
            position
            dgraph.type
    
            # Prérequis
            prereq_hard {{ uid name }}
            prereq_soft {{ uid name }}
            incompatible {{ uid name }}
            required_slots
    
            # Hiérarchie
            ~children {{ uid name }}  # parent
            children {{ uid name }}
    
            # Keywords (pour RootLabel)
            intentKeywords
            actionKeywords
          }}
        }}
        """
    
        try:
            # ✅ AJOUTÉ: Vérification supplémentaire avant accès
            if not self.dgraph or not hasattr(self.dgraph, 'client'):
                logger.error("❌ Dgraph client non disponible")
                return {}
            
            txn = self.dgraph.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
    
            data = json.loads(resp.json)
            nodes = data.get('nodes', [])
    
            # Parser les résultats
            enrichment_data = {}
    
            for node in nodes:
                uid = node.get('uid')
                if not uid:
                    continue
                
                enrichment_data[uid] = {
                    'name': node.get('name', ''),
                    'description': node.get('description', ''),
                    'category': node.get('category', 'default'),
                    'depth': node.get('depth', 0),
                    'position': node.get('position', 0),
                    'dgraph.type': node.get('dgraph.type', []),
    
                    # Prérequis (extraire UIDs)
                    'prereq_hard': [p['uid'] for p in node.get('prereq_hard', []) if 'uid' in p],
                    'prereq_soft': [p['uid'] for p in node.get('prereq_soft', []) if 'uid' in p],
                    'incompatible': [i['uid'] for i in node.get('incompatible', []) if 'uid' in i],
                    'required_slots': node.get('required_slots', []),
    
                    # Hiérarchie
                    'parent_ids': [p['uid'] for p in node.get('~children', []) if 'uid' in p],
                    'child_ids': [c['uid'] for c in node.get('children', []) if 'uid' in c],
                    'path_ids': [],  # TODO: calculer si nécessaire
    
                    # Keywords
                    'intentKeywords': node.get('intentKeywords', []),
                    'actionKeywords': node.get('actionKeywords', []),
                }
    
            logger.info(f"📊 Dgraph batch fetch: {len(enrichment_data)}/{len(validated_uids)} nodes enrichis")
    
            return enrichment_data
    
        except Exception as e:
            logger.error(f"❌ Erreur batch fetch Dgraph: {e}")
            logger.error(f"   Query tentée: {query[:200]}...")
            import traceback
            logger.error(traceback.format_exc())
            return {}   
    
    def _get_prereq_names(
        self, 
        prereq_uids: List[str], 
        enrichment_data: Dict[str, Dict]
    ) -> List[str]:
        """Récupère les noms des prérequis depuis enrichment_data"""
        names = []
        for uid in prereq_uids[:3]:  # Max 3 pour le hint
            if uid in enrichment_data:
                names.append(enrichment_data[uid].get('name', uid))
            else:
                names.append(uid)
        
        if len(prereq_uids) > 3:
            names.append(f"+ {len(prereq_uids) - 3} autres")
        
        return names
    
    
    # ========================================================================
    # CALCUL FINAL SCORE (SIMPLIFIÉ)
    # ========================================================================
    
    def _compute_final_score(
        self,
        candidate: TaxonCandidate
    ) -> RerankingResult:
        """
        ✅ SIMPLIFIÉ: Calcule final_score = f(rrf, metadata_quality)
        
        Pas de validation, juste boost selon qualité metadata
        """
        
        original_rank = candidate.metadata.get('original_rank', 0)
        
        result = RerankingResult(
            taxon_id=candidate.taxon_id,
            original_rrf_score=candidate.rrf_score,
            original_rank=original_rank,
            final_score=0.0,
            new_rank=0
        )
        
        # 1. Composant RRF (base)
        result.rrf_component = candidate.rrf_score * self.config.rrf_weight
        
        # 2. Composant metadata quality
        metadata_score, adjustments = self._compute_metadata_score(candidate)
        result.metadata_component = metadata_score * self.config.metadata_boost_weight
        result.adjustments.extend(adjustments)
        
        # Final score
        result.final_score = (
            result.rrf_component +
            result.metadata_component
        )
        
        # Clamp
        #result.final_score = max(
        #    self.config.min_final_score,
        #    min(self.config.max_final_score, result.final_score)
        #)
        
        # Total adjustment
        #result.total_adjustment = result.final_score - candidate.rrf_score
        
        return result
    
    
    def _compute_metadata_score(
        self,
        candidate: TaxonCandidate
    ) -> Tuple[float, List[ScoreAdjustment]]:
        """
        Calcule un score basé sur la qualité/richesse de la metadata
        
        Bonus pour:
        - Description présente
        - Prereqs définis
        - Profondeur élevée
        """
        
        adjustments = []
        base_score = 0.5  # Neutre
        
        # Bonus si description enrichie
        if candidate.metadata.get('description'):
            adjustments.append(ScoreAdjustment(
                adjustment_type="bonus",
                amount=self.config.bonus_has_description,
                reason="Has complete description"
            ))
            base_score += self.config.bonus_has_description
        
        # Bonus si prereqs définis
        prereq_hard = candidate.metadata.get('prereq_hard_ids', [])
        if prereq_hard:
            adjustments.append(ScoreAdjustment(
                adjustment_type="bonus",
                amount=self.config.bonus_has_prereqs,
                reason=f"Has {len(prereq_hard)} hard prerequisites"
            ))
            base_score += self.config.bonus_has_prereqs
        
        # Bonus si profondeur élevée (nœud spécifique)
        if candidate.depth >= 3:
            adjustments.append(ScoreAdjustment(
                adjustment_type="bonus",
                amount=self.config.bonus_high_depth,
                reason=f"High specificity (depth={candidate.depth})"
            ))
            base_score += self.config.bonus_high_depth
        
        metadata_score = max(0.0, min(1.0, base_score))
        
        return metadata_score, adjustments
    
    
    def _log_reranking_changes(self, results: List[RerankingResult]):
        """Log les changements significatifs de rang"""
        
        significant_changes = [
            r for r in results 
            if abs(r.new_rank - r.original_rank) >= 3
        ]
        
        if significant_changes:
            logger.info(f"\n📊 Changements significatifs de rang (≥3 positions):")
            for result in significant_changes[:5]:
                direction = "⬆️" if result.new_rank < result.original_rank else "⬇️"
                logger.info(
                    f"   {direction} {result.taxon_id}: "
                    f"Rank {result.original_rank} → {result.new_rank} "
                    f"(Δscore: {result.total_adjustment:+.3f})"
                )
        
        top_adjusted = sorted(results, key=lambda r: abs(r.total_adjustment), reverse=True)[:3]
        
        if top_adjusted:
            logger.info(f"\n🎯 Top 3 ajustements:")
            for result in top_adjusted:
                logger.info(
                    f"   • {result.taxon_id}: "
                    f"RRF={result.original_rrf_score:.3f} → Final={result.final_score:.3f} "
                    f"(Δ={result.total_adjustment:+.3f})"
                )
                
                if result.adjustments:
                    main_adjustment = max(result.adjustments, key=lambda a: abs(a.amount))
                    logger.info(f"     Raison: {main_adjustment.reason}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_reranker(
    dgraph_connector,
    rrf_weight: float = 0.7,
    metadata_boost_weight: float = 0.3
) -> TaxonomyReranker:
    """Factory pour créer un reranker avec configuration custom"""
    
    config = RerankingConfig(
        rrf_weight=rrf_weight,
        metadata_boost_weight=metadata_boost_weight
    )
    
    return TaxonomyReranker(dgraph_connector, config)