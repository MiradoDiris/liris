import sqlite3
import datetime
import json
import os
from typing import Dict, List, Optional, Tuple
from utils.logger import logger

class AIUsageTracker:
    """
    Gestionnaire pour tracker et stocker les données d'utilisation de l'IA
    dans la base de données SQLite data/liris.db
    """
    
    def __init__(self, db_path: str = "data/liris.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """S'assure que le répertoire data/ existe"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Répertoire créé: {db_dir}")
    
    def _init_database(self):
        """Initialise les tables de la base de données"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table principale des requêtes IA
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        platform_name TEXT NOT NULL,
                        model_name TEXT,
                        context_length INTEGER DEFAULT 0,
                        input_tokens INTEGER DEFAULT 0,
                        output_tokens INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        estimated_cost REAL DEFAULT 0.0,
                        duration_seconds REAL DEFAULT 0.0,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        project_name TEXT,
                        session_type TEXT DEFAULT 'coding',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table des coûts par modèle
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_costs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT UNIQUE NOT NULL,
                        input_cost_per_1k REAL NOT NULL,
                        output_cost_per_1k REAL NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insérer les coûts par défaut s'ils n'existent pas
                self._insert_default_model_costs(cursor)
                
                conn.commit()
                logger.info("Base de données AI Usage initialisée avec succès")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
    
    def _insert_default_model_costs(self, cursor):
        """Insère les coûts par défaut des modèles IA"""
        default_costs = [
            ("GPT-4", 0.03, 0.06),
            ("GPT-3.5-Turbo", 0.0005, 0.0015),
            ("Claude-3-Opus", 0.075, 0.225),
            ("Claude-3-Sonnet", 0.03, 0.06),
            ("Gemini-1.5-Pro", 0.007, 0.021),
            ("Gemini-2.5-Flash", 0.002, 0.004),
            ("Grok", 0.005, 0.015),
            ("Default", 0.001, 0.002)
        ]
        
        for model_name, input_cost, output_cost in default_costs:
            cursor.execute("""
                INSERT OR IGNORE INTO model_costs (model_name, input_cost_per_1k, output_cost_per_1k)
                VALUES (?, ?, ?)
            """, (model_name, input_cost, output_cost))
    
    def record_usage(self, 
                    platform_name: str,
                    success: bool,
                    duration_seconds: float,
                    input_tokens: int = 0,
                    output_tokens: int = 0,
                    model_name: str = None,
                    context_length: int = 0,
                    error_message: str = None,
                    project_name: str = None,
                    session_type: str = 'coding') -> int:
        """
        Enregistre une utilisation de l'IA
        
        Returns:
            ID de l'enregistrement créé
        """
        try:
            total_tokens = input_tokens + output_tokens
            estimated_cost = self._calculate_cost(model_name or platform_name, input_tokens, output_tokens)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO ai_usage (
                        timestamp, platform_name, model_name, context_length,
                        input_tokens, output_tokens, total_tokens, estimated_cost,
                        duration_seconds, success, error_message, project_name, session_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.datetime.now().isoformat(),
                    platform_name,
                    model_name,
                    context_length,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost,
                    duration_seconds,
                    success,
                    error_message,
                    project_name,
                    session_type
                ))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Usage enregistré: {platform_name} - {total_tokens} tokens - {estimated_cost:.4f}€")
                return record_id
                
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'usage: {e}")
            return -1
    
    def _calculate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Calcule le coût estimé basé sur le modèle"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Essayer de trouver le modèle exact
                cursor.execute("""
                    SELECT input_cost_per_1k, output_cost_per_1k 
                    FROM model_costs 
                    WHERE model_name = ?
                """, (model_name,))
                
                result = cursor.fetchone()
                
                if not result:
                    # Essayer une correspondance partielle
                    cursor.execute("""
                        SELECT input_cost_per_1k, output_cost_per_1k 
                        FROM model_costs 
                        WHERE ? LIKE '%' || model_name || '%'
                        ORDER BY LENGTH(model_name) DESC
                        LIMIT 1
                    """, (model_name.upper(),))
                    
                    result = cursor.fetchone()
                
                if not result:
                    # Utiliser le coût par défaut
                    cursor.execute("""
                        SELECT input_cost_per_1k, output_cost_per_1k 
                        FROM model_costs 
                        WHERE model_name = 'Default'
                    """)
                    result = cursor.fetchone()
                
                if result:
                    input_cost_per_1k, output_cost_per_1k = result
                    cost = (input_tokens / 1000 * input_cost_per_1k) + (output_tokens / 1000 * output_cost_per_1k)
                    return round(cost, 6)
                
        except Exception as e:
            logger.error(f"Erreur calcul coût pour {model_name}: {e}")
        
        return 0.0
    
    def get_usage_stats(self, period: str = 'month') -> Dict:
        """
        Récupère les statistiques d'utilisation pour une période
        
        Args:
            period: 'day', 'week', 'month', 'year'
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculer la date de début selon la période
                now = datetime.datetime.now()
                if period == 'day':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'week':
                    start_date = now - datetime.timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'month':
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                else:  # year
                    start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                
                # Statistiques générales
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_calls,
                        SUM(total_tokens) as total_tokens,
                        SUM(estimated_cost) as total_cost,
                        AVG(duration_seconds) as avg_duration,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls
                    FROM ai_usage 
                    WHERE timestamp >= ?
                """, (start_date.isoformat(),))
                
                stats = cursor.fetchone()
                
                # Statistiques par plateforme
                cursor.execute("""
                    SELECT 
                        platform_name,
                        COUNT(*) as calls,
                        SUM(total_tokens) as tokens,
                        SUM(estimated_cost) as cost
                    FROM ai_usage 
                    WHERE timestamp >= ?
                    GROUP BY platform_name
                    ORDER BY tokens DESC
                """, (start_date.isoformat(),))
                
                platform_stats = cursor.fetchall()
                
                # Dernière activité
                cursor.execute("""
                    SELECT timestamp, platform_name 
                    FROM ai_usage 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                last_activity = cursor.fetchone()
                
                return {
                    'period': period,
                    'start_date': start_date.isoformat(),
                    'total_calls': stats[0] or 0,
                    'total_tokens': stats[1] or 0,
                    'total_cost': stats[2] or 0.0,
                    'avg_duration': stats[3] or 0.0,
                    'successful_calls': stats[4] or 0,
                    'success_rate': (stats[4] / stats[0] * 100) if stats[0] > 0 else 0,
                    'platform_stats': [
                        {
                            'name': row[0],
                            'calls': row[1],
                            'tokens': row[2],
                            'cost': row[3]
                        } for row in platform_stats
                    ],
                    'most_used_platform': platform_stats[0][0] if platform_stats else None,
                    'last_activity': last_activity[0] if last_activity else None
                }
                
        except Exception as e:
            logger.error(f"Erreur récupération stats: {e}")
            return {}
    
    def get_daily_consumption(self, days: int = 30) -> List[Dict]:
        """Récupère la consommation journalière des derniers jours"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                start_date = datetime.datetime.now() - datetime.timedelta(days=days)
                
                cursor.execute("""
                    SELECT 
                        DATE(timestamp) as date,
                        platform_name,
                        SUM(total_tokens) as tokens
                    FROM ai_usage 
                    WHERE timestamp >= ?
                    GROUP BY DATE(timestamp), platform_name
                    ORDER BY date, platform_name
                """, (start_date.isoformat(),))
                
                results = cursor.fetchall()
                
                return [
                    {
                        'date': row[0],
                        'platform': row[1],
                        'tokens': row[2]
                    } for row in results
                ]
                
        except Exception as e:
            logger.error(f"Erreur récupération consommation journalière: {e}")
            return []
    
    def get_usage_history(self, limit: int = 100, filter_period: str = None) -> List[Dict]:
        """Récupère l'historique des utilisations"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        timestamp, platform_name, model_name, total_tokens,
                        estimated_cost, success, error_message, duration_seconds
                    FROM ai_usage 
                """
                params = []
                
                if filter_period:
                    now = datetime.datetime.now()
                    if filter_period == 'day':
                        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif filter_period == 'week':
                        start_date = now - datetime.timedelta(days=now.weekday())
                    elif filter_period == 'month':
                        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    
                    query += " WHERE timestamp >= ?"
                    params.append(start_date.isoformat())
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                return [
                    {
                        'date': row[0],
                        'platform': row[1],
                        'model': row[2] or row[1],
                        'tokens': row[3],
                        'cost': row[4],
                        'success': bool(row[5]),
                        'error': row[6],
                        'duration': row[7]
                    } for row in results
                ]
                
        except Exception as e:
            logger.error(f"Erreur récupération historique: {e}")
            return []