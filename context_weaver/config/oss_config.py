#!/usr/bin/env python
# -*- coding: utf-8 -*-
#config/oss_config.py
"""
Configuration pour l'API OSS 20B (Classification sémantique)
"""

import os
from typing import Dict, Any

class OSSConfig:
    """Configuration pour l'appel à l'API OSS 20B"""
    
    # URL fictive de l'API OSS 20B
    API_URL = os.getenv("OSS_API_URL", "https://api.oss-20b.example.com/v1/classify")
    
    # Clé API (à remplacer par vraie clé en production)
    API_KEY = os.getenv("OSS_API_KEY", "oss_demo_key_12345")
    
    # Timeout en secondes
    TIMEOUT = 30
    
    # Retry config
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # secondes
    
    # Paramètres du modèle
    MODEL_NAME = "oss-20b-classifier"
    TEMPERATURE = 0.0  # Zéro variabilité pour classification
    MAX_TOKENS = 500   # Output JSON court
    
    # Prompt système pour classification
    SYSTEM_PROMPT = """Tu es un classificateur sémantique expert.
Analyse le contexte utilisateur et retourne UNIQUEMENT un JSON strict.
Format obligatoire:
{
  "domain": "string",
  "task": "string",
  "decision_type": "string",
  "variables": ["string"],
  "risk_axis": ["string"],
  "constraints": ["string"]
}
Pas de commentaire, pas de markdown, UNIQUEMENT le JSON."""

    # Domaines connus
    KNOWN_DOMAINS = [
        "fraude_bancaire",
        "credit_scoring",
        "detection_anomalies",
        "risque_operational",
        "compliance"
    ]
    
    # Types de tâches
    KNOWN_TASKS = [
        "dataset_generation",
        "rule_creation",
        "model_training",
        "decision_automation"
    ]
    
    # Types de décision
    KNOWN_DECISION_TYPES = [
        "decision_tree",
        "scoring_model",
        "rule_based",
        "ml_model"
    ]
    
    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Retourne les headers HTTP pour l'API"""
        return {
            "Authorization": f"Bearer {OSSConfig.API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @staticmethod
    def get_request_payload(user_context: str) -> Dict[str, Any]:
        """Construit le payload de requête pour OSS"""
        return {
            "model": OSSConfig.MODEL_NAME,
            "messages": [
                {"role": "system", "content": OSSConfig.SYSTEM_PROMPT},
                {"role": "user", "content": user_context}
            ],
            "temperature": OSSConfig.TEMPERATURE,
            "max_tokens": OSSConfig.MAX_TOKENS,
            "response_format": {"type": "json_object"}  # Force JSON
        }
    
    @staticmethod
    def validate_classification(classification: Dict[str, Any]) -> bool:
        """Valide la structure de la classification"""
        required_fields = ["domain", "task", "decision_type", "variables"]
        return all(field in classification for field in required_fields)