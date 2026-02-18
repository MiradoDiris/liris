#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reranked Result Store - Stockage des résultats après reranking
Architecture hybride: SQLite + Redis (optionnel) + JSON (debug)
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from context_weaver.taxonomy.taxonomy_models import (
    TaxonCandidate,
    ValidationResult
)
from context_weaver.reranker.taxonomy_reranker import (
    RerankingResult
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class StoreConfig:
    """Configuration du stockage"""
    
    # Paths
    DB_PATH = Path("data/context_weaver.db")
    JSON_DEBUG_PATH = Path("data/reranking_results")
    
    # Options
    ENABLE_JSON_DEBUG = True  # Sauvegarder les dumps JSON détaillés
    ENABLE_REDIS = False       # Utiliser Redis pour le cache
    
    # Limits
    MAX_CANDIDATES_IN_DB = 10  # Top N à sauvegarder en DB
    REDIS_TTL = 3600           # TTL Redis en secondes (1h)


# ============================================================================
# RERANKED RESULT STORE
# ============================================================================

class RerankedResultStore:
    """
    Store pour les résultats après reranking
    
    Architecture:
    1. SQLite: Persistence long terme (top N candidats par requête)
    2. Redis: Cache haute performance (optionnel)
    3. JSON: Dumps détaillés pour debug/analysis
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        enable_redis: bool = False,
        enable_json_debug: bool = True
    ):
        self.db_path = db_path or StoreConfig.DB_PATH
        self.enable_redis = enable_redis
        self.enable_json_debug = enable_json_debug
        
        # Connexion DB
        self.connection = None
        self._connect_db()
        self._create_tables()
        
        # Redis (optionnel)
        self.redis_client = None
        if self.enable_redis:
            self._init_redis()
        
        logger.info("✅ RerankedResultStore initialisé")
        logger.info(f"   • DB: {self.db_path}")
        logger.info(f"   • Redis: {self.enable_redis}")
        logger.info(f"   • JSON debug: {self.enable_json_debug}")
    
    
    def _connect_db(self):
        """Établit la connexion SQLite"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        logger.info(f"✅ Connexion DB: {self.db_path}")
    
    
    def _create_tables(self):
        """Crée les tables pour stocker les résultats reranked"""
        
        cursor = self.connection.cursor()
        
        # Table principale: résultats reranked
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reranked_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER NOT NULL,
                taxon_id TEXT NOT NULL,
                taxon_name TEXT,
                
                -- Scores
                dense_score REAL,
                bm25_score REAL,
                rrf_score REAL,
                final_score REAL,
                
                -- Composants du final_score
                rrf_component REAL,
                validation_component REAL,
                context_component REAL,
                
                -- Validation
                validation_status TEXT,
                validation_confidence REAL,
                
                -- Reranking
                score_adjustment REAL,
                rank_before INTEGER,
                rank_after INTEGER,
                
                -- Metadata
                breadcrumb TEXT,
                depth INTEGER,
                domain TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (query_id) REFERENCES queries(id)
            )
        """)
        
        # Table des ajustements de score (détails)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS score_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                adjustment_type TEXT NOT NULL,  -- 'penalty' ou 'bonus'
                amount REAL NOT NULL,
                reason TEXT,
                related_entity TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (result_id) REFERENCES reranked_results(id)
            )
        """)
        
        # Table des violations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                violation_type TEXT NOT NULL,
                details TEXT,
                affected_entity TEXT,
                severity TEXT,
                resolution_hint TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (result_id) REFERENCES reranked_results(id)
            )
        """)
        
        # Index pour performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reranked_query_id 
            ON reranked_results(query_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reranked_final_score 
            ON reranked_results(final_score DESC)
        """)
        
        self.connection.commit()
        logger.info("✅ Tables créées/vérifiées")
    
    
    def _init_redis(self):
        """Initialise la connexion Redis"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            # Test connexion
            self.redis_client.ping()
            logger.info("✅ Redis connecté")
        
        except ImportError:
            logger.warning("⚠️ redis-py non installé, cache Redis désactivé")
            self.enable_redis = False
        
        except Exception as e:
            logger.warning(f"⚠️ Redis non disponible: {e}")
            self.enable_redis = False
    
    
    def save_reranked_results(
        self,
        query_id: int,
        candidates: List[TaxonCandidate],
        reranking_results: List[RerankingResult],
        validation_results: Dict[str, ValidationResult],
        execution_time_ms: float = 0.0
    ) -> bool:
        """
        Sauvegarde les résultats après reranking
        
        Args:
            query_id: ID de la requête (de la table queries)
            candidates: Candidats reranked avec final_score
            reranking_results: Détails du reranking
            validation_results: Résultats de validation par taxon_id
            execution_time_ms: Temps d'exécution du reranking
            
        Returns:
            True si succès
        """
        
        logger.info(f"💾 Sauvegarde résultats reranked pour query {query_id}...")
        
        try:
            # 1. SQLite - Top N candidats
            saved_count = self._save_to_sqlite(
                query_id,
                candidates,
                reranking_results,
                validation_results
            )
            
            logger.info(f"   ✅ SQLite: {saved_count} candidats sauvegardés")
            
            # 2. Redis - Cache (optionnel)
            if self.enable_redis:
                self._save_to_redis(
                    query_id,
                    candidates,
                    reranking_results
                )
                logger.info(f"   ✅ Redis: Cache mis à jour")
            
            # 3. JSON - Debug dump (optionnel)
            if self.enable_json_debug:
                self._save_to_json(
                    query_id,
                    candidates,
                    reranking_results,
                    validation_results,
                    execution_time_ms
                )
                logger.info(f"   ✅ JSON: Dump debug créé")
            
            logger.info(f"✅ Résultats sauvegardés avec succès")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    
    def _save_to_sqlite(
        self,
        query_id: int,
        candidates: List[TaxonCandidate],
        reranking_results: List[RerankingResult],
        validation_results: Dict[str, ValidationResult]
    ) -> int:
        """Sauvegarde dans SQLite (top N candidats)"""
        
        cursor = self.connection.cursor()
        saved_count = 0
        
        # Limiter aux top N
        top_candidates = candidates[:StoreConfig.MAX_CANDIDATES_IN_DB]
        
        for candidate in top_candidates:
            # Trouver le RerankingResult correspondant
            rerank_result = next(
                (r for r in reranking_results if r.taxon_id == candidate.taxon_id),
                None
            )
            
            if not rerank_result:
                logger.warning(f"⚠️ Pas de RerankingResult pour {candidate.taxon_id}")
                continue
            
            # Validation
            validation = validation_results.get(candidate.taxon_id)
            
            # Insérer dans reranked_results
            cursor.execute("""
                INSERT INTO reranked_results (
                    query_id, taxon_id, taxon_name,
                    dense_score, bm25_score, rrf_score, final_score,
                    rrf_component, validation_component, context_component,
                    validation_status, validation_confidence,
                    score_adjustment, rank_before, rank_after,
                    breadcrumb, depth, domain
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                query_id,
                candidate.taxon_id,
                candidate.name,
                candidate.dense_score,
                candidate.bm25_score,
                candidate.rrf_score,
                candidate.final_score,
                rerank_result.rrf_component,
                rerank_result.validation_component,
                rerank_result.context_component,
                str(validation.status) if validation else None,
                validation.confidence if validation else None,
                rerank_result.total_adjustment,
                rerank_result.original_rank,
                rerank_result.new_rank,
                candidate.breadcrumb,
                candidate.depth,
                candidate.metadata.get('domain', '')
            ))
            
            result_id = cursor.lastrowid
            
            # Sauvegarder les ajustements
            for adjustment in rerank_result.adjustments:
                cursor.execute("""
                    INSERT INTO score_adjustments (
                        result_id, adjustment_type, amount, reason, related_entity
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    result_id,
                    adjustment.adjustment_type,
                    adjustment.amount,
                    adjustment.reason,
                    adjustment.related_entity
                ))
            
            # Sauvegarder les violations
            if validation and validation.violations:
                for violation in validation.violations:
                    cursor.execute("""
                        INSERT INTO validation_violations (
                            result_id, violation_type, details, 
                            affected_entity, severity, resolution_hint
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        result_id,
                        str(violation.type),
                        violation.details,
                        violation.affected_entity,
                        violation.severity,
                        violation.resolution_hint
                    ))
            
            saved_count += 1
        
        self.connection.commit()
        
        return saved_count
    
    
    def _save_to_redis(
        self,
        query_id: int,
        candidates: List[TaxonCandidate],
        reranking_results: List[RerankingResult]
    ):
        """Sauvegarde dans Redis (cache)"""
        
        if not self.redis_client:
            return
        
        try:
            # Construire le payload
            cache_data = {
                'query_id': query_id,
                'timestamp': datetime.now().isoformat(),
                'candidates': [
                    {
                        'taxon_id': c.taxon_id,
                        'name': c.name,
                        'final_score': c.final_score,
                        'rank': c.metadata.get('new_rank', 0),
                        'breadcrumb': c.breadcrumb
                    }
                    for c in candidates[:20]  # Top 20 pour cache
                ]
            }
            
            # Clé Redis
            redis_key = f"reranked:query:{query_id}"
            
            # Sauvegarder avec TTL
            self.redis_client.setex(
                redis_key,
                StoreConfig.REDIS_TTL,
                json.dumps(cache_data)
            )
        
        except Exception as e:
            logger.warning(f"⚠️ Erreur cache Redis: {e}")
    
    
    def _save_to_json(
        self,
        query_id: int,
        candidates: List[TaxonCandidate],
        reranking_results: List[RerankingResult],
        validation_results: Dict[str, ValidationResult],
        execution_time_ms: float
    ):
        """Sauvegarde dump JSON pour debug/analysis"""
        
        try:
            # Créer le dossier
            output_dir = StoreConfig.JSON_DEBUG_PATH
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Nom du fichier
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reranking_{query_id}_{timestamp}.json"
            filepath = output_dir / filename
            
            # Construire le JSON détaillé
            dump_data = {
                'query_id': query_id,
                'timestamp': datetime.now().isoformat(),
                'execution_time_ms': execution_time_ms,
                
                'summary': {
                    'total_candidates': len(candidates),
                    'top_candidate': {
                        'taxon_id': candidates[0].taxon_id,
                        'name': candidates[0].name,
                        'final_score': candidates[0].final_score
                    } if candidates else None,
                    'significant_changes': sum(
                        1 for r in reranking_results 
                        if abs(r.new_rank - r.original_rank) >= 3
                    )
                },
                
                'candidates': [
                    {
                        'taxon_id': c.taxon_id,
                        'name': c.name,
                        'breadcrumb': c.breadcrumb,
                        'scores': {
                            'dense': c.dense_score,
                            'bm25': c.bm25_score,
                            'rrf': c.rrf_score,
                            'final': c.final_score
                        },
                        'ranks': {
                            'before': c.metadata.get('original_rank', 0),
                            'after': c.metadata.get('new_rank', 0),
                            'change': c.metadata.get('new_rank', 0) - c.metadata.get('original_rank', 0)
                        }
                    }
                    for c in candidates
                ],
                
                'reranking_details': [
                    {
                        'taxon_id': r.taxon_id,
                        'score_adjustment': r.total_adjustment,
                        'components': {
                            'rrf': r.rrf_component,
                            'validation': r.validation_component,
                            'context': r.context_component
                        },
                        'adjustments': [
                            {
                                'type': a.adjustment_type,
                                'amount': a.amount,
                                'reason': a.reason
                            }
                            for a in r.adjustments
                        ]
                    }
                    for r in reranking_results
                ],
                
                'validation_summary': {
                    taxon_id: {
                        'status': str(v.status),
                        'confidence': v.confidence,
                        'violations_count': len(v.violations)
                    }
                    for taxon_id, v in validation_results.items()
                }
            }
            
            # Sauvegarder
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"   Debug dump: {filepath}")
        
        except Exception as e:
            logger.warning(f"⚠️ Erreur JSON dump: {e}")
    
    
    def get_reranked_results(
        self,
        query_id: int,
        from_cache: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Récupère les résultats reranked d'une requête
        
        Args:
            query_id: ID de la requête
            from_cache: Essayer Redis d'abord
            
        Returns:
            Liste des résultats ou None
        """
        
        # 1. Essayer Redis si activé
        if from_cache and self.enable_redis:
            cached = self._get_from_redis(query_id)
            if cached:
                logger.info(f"✅ Résultats trouvés en cache Redis")
                return cached
        
        # 2. Sinon, aller en DB
        return self._get_from_sqlite(query_id)
    
    
    def _get_from_redis(self, query_id: int) -> Optional[List[Dict[str, Any]]]:
        """Récupère depuis Redis"""
        
        if not self.redis_client:
            return None
        
        try:
            redis_key = f"reranked:query:{query_id}"
            cached_data = self.redis_client.get(redis_key)
            
            if cached_data:
                data = json.loads(cached_data)
                return data.get('candidates', [])
        
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture Redis: {e}")
        
        return None
    
    
    def _get_from_sqlite(self, query_id: int) -> Optional[List[Dict[str, Any]]]:
        """Récupère depuis SQLite"""
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT * FROM reranked_results
            WHERE query_id = ?
            ORDER BY final_score DESC
        """, (query_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        results = []
        for row in rows:
            results.append({
                'taxon_id': row['taxon_id'],
                'taxon_name': row['taxon_name'],
                'final_score': row['final_score'],
                'rank': row['rank_after'],
                'breadcrumb': row['breadcrumb'],
                'validation_status': row['validation_status'],
                'score_adjustment': row['score_adjustment']
            })
        
        return results
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du store"""
        
        cursor = self.connection.cursor()
        
        # Total résultats
        cursor.execute("SELECT COUNT(*) as count FROM reranked_results")
        total_results = cursor.fetchone()['count']
        
        # Total ajustements
        cursor.execute("SELECT COUNT(*) as count FROM score_adjustments")
        total_adjustments = cursor.fetchone()['count']
        
        # Total violations
        cursor.execute("SELECT COUNT(*) as count FROM validation_violations")
        total_violations = cursor.fetchone()['count']
        
        # Stats par type d'ajustement
        cursor.execute("""
            SELECT adjustment_type, COUNT(*) as count
            FROM score_adjustments
            GROUP BY adjustment_type
        """)
        adjustments_by_type = {row['adjustment_type']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_results': total_results,
            'total_adjustments': total_adjustments,
            'total_violations': total_violations,
            'adjustments_by_type': adjustments_by_type,
            'redis_enabled': self.enable_redis,
            'json_debug_enabled': self.enable_json_debug
        }
    
    
    def close(self):
        """Ferme les connexions"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Connexion DB fermée")
        
        if self.redis_client:
            self.redis_client.close()
            logger.info("✅ Redis fermé")


# ============================================================================
# FACTORY
# ============================================================================

def create_reranked_store(
    enable_redis: bool = False,
    enable_json_debug: bool = True
) -> RerankedResultStore:
    """
    Factory pour créer un RerankedResultStore
    
    Args:
        enable_redis: Activer le cache Redis
        enable_json_debug: Activer les dumps JSON
        
    Returns:
        RerankedResultStore configuré
    """
    
    return RerankedResultStore(
        enable_redis=enable_redis,
        enable_json_debug=enable_json_debug
    )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Créer le store
    store = create_reranked_store(
        enable_redis=False,
        enable_json_debug=True
    )
    
    # Stats
    stats = store.get_stats()
    print("\n📊 Statistiques du store:")
    print(f"   • Total résultats: {stats['total_results']}")
    print(f"   • Total ajustements: {stats['total_adjustments']}")
    print(f"   • Total violations: {stats['total_violations']}")
    
    store.close()
    
    print("\n✅ Test terminé!")