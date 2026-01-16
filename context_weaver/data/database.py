#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestionnaire de base de données SQLite
Stocke l'historique des requêtes et résultats
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Database:
    """Gestionnaire SQLite pour historique"""
    
    def __init__(self, db_path: str = "./data/context_weaver.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Établit la connexion à la base"""
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        logger.info(f"✅ Connexion DB: {self.db_path}")
    
    def _create_tables(self):
        """Crée les tables nécessaires"""
        cursor = self.connection.cursor()
        
        # Table des requêtes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_context TEXT NOT NULL,
                domain TEXT,
                task TEXT,
                decision_type TEXT,
                variables TEXT,
                execution_time_ms REAL,
                confidence_score REAL,
                result_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des résultats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER,
                result_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_id) REFERENCES queries(id)
            )
        """)
        
        self.connection.commit()
        logger.info("✅ Tables créées/vérifiées")
    
    def save_query(
        self,
        user_context: str,
        domain: str,
        task: str,
        decision_type: str,
        variables: List[str],
        execution_time_ms: float,
        confidence_score: float,
        result_count: int
    ) -> int:
        """Sauvegarde une requête"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO queries (
                user_context, domain, task, decision_type,
                variables, execution_time_ms, confidence_score, result_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_context,
            domain,
            task,
            decision_type,
            json.dumps(variables),
            execution_time_ms,
            confidence_score,
            result_count
        ))
        
        self.connection.commit()
        query_id = cursor.lastrowid
        logger.info(f"✅ Requête sauvegardée (ID: {query_id})")
        return query_id
    
    def save_result(self, query_id: int, result_data: Dict[str, Any]):
        """Sauvegarde un résultat"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO results (query_id, result_data)
            VALUES (?, ?)
        """, (query_id, json.dumps(result_data)))
        
        self.connection.commit()
        logger.info(f"✅ Résultat sauvegardé pour query {query_id}")
    
    def get_recent_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les requêtes récentes"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT * FROM queries
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        queries = []
        for row in rows:
            queries.append({
                "id": row["id"],
                "user_context": row["user_context"],
                "domain": row["domain"],
                "task": row["task"],
                "variables": json.loads(row["variables"]),
                "execution_time_ms": row["execution_time_ms"],
                "confidence_score": row["confidence_score"],
                "created_at": row["created_at"]
            })
        
        return queries
    
    def get_stats(self) -> Dict[str, int]:
        """Retourne les statistiques"""
        cursor = self.connection.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM queries")
        query_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM results")
        result_count = cursor.fetchone()["count"]
        
        return {
            "total_queries": query_count,
            "total_results": result_count
        }
    
    def close(self):
        """Ferme la connexion"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Connexion DB fermée")