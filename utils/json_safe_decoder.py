# json_safe_decoder.py - Décodeur JSON robuste avec récupération d'erreurs
"""
Utilitaires pour décoder JSON défaillant/tronqué sans crash
"""

import json
import re
from typing import Any, Dict, Union
from utils.logger import logger


class JSONSafeDecoder:
    """Décodeur JSON qui gère les chaînes malformées ou tronquées."""
    
    @staticmethod
    def safe_loads(data: str, default=None) -> Any:
        """
        Charge du JSON en tolérant les erreurs.
        
        Args:
            data: Chaîne JSON potentiellement malformée
            default: Valeur par défaut en cas d'erreur
        
        Returns:
            Objet Python ou valeur par défaut
        """
        if not data or not isinstance(data, str):
            return default if default is not None else {}
        
        data = data.strip()
        
        if not data:
            return default if default is not None else {}
        
        # Tentative 1: JSON normal
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.debug(f"Erreur JSON standard: {e}")
        
        # Tentative 2: Réparer le JSON tronqué
        repaired = JSONSafeDecoder._repair_truncated_json(data)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.debug(f"Erreur après réparation: {e}")
        
        # Tentative 3: Extraire les parties valides
        valid_data = JSONSafeDecoder._extract_valid_json_parts(data)
        if valid_data:
            try:
                return json.loads(valid_data)
            except json.JSONDecodeError:
                pass
        
        # Fallback: retourner la valeur par défaut
        logger.warning(f"Impossible de décoder JSON, retour à la valeur par défaut. Données: {data[:100]}...")
        return default if default is not None else {}
    
    @staticmethod
    def _repair_truncated_json(data: str) -> str:
        """
        Répare un JSON tronqué en le fermant correctement.
        
        Args:
            data: JSON tronqué
        
        Returns:
            JSON réparé et valide
        """
        data = data.rstrip()
        
        # Compter les accolades et crochets ouverts
        open_braces = data.count('{') - data.count('}')
        open_brackets = data.count('[') - data.count(']')
        open_quotes = 0
        escaped = False
        
        # Compter les guillemets non échappés
        for char in data:
            if char == '\\' and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                open_quotes += 1
            escaped = False
        
        # Si le nombre de guillemets est impair, fermer la dernière chaîne
        if open_quotes % 2 != 0:
            data += '"'
        
        # Fermer les structures ouvertes
        data += '}' * open_braces
        data += ']' * open_brackets
        
        return data
    
    @staticmethod
    def _extract_valid_json_parts(data: str) -> str:
        """
        Extrait les parties valides d'une chaîne JSON malformée.
        
        Args:
            data: JSON malformé
        
        Returns:
            JSON valide extrait
        """
        # Trouver le dernier objet/tableau complet
        for i in range(len(data) - 1, 0, -1):
            try:
                test_str = data[:i]
                # Compter les structures
                open_braces = test_str.count('{') - test_str.count('}')
                open_brackets = test_str.count('[') - test_str.count(']')
                
                # Fermer les structures
                repaired = test_str + '}' * open_braces + ']' * open_brackets
                
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                continue
        
        return '{}'
    
    @staticmethod
    def safe_loads_dict(data: str, default=None) -> Dict:
        """Charge du JSON en assurant un dictionnaire."""
        result = JSONSafeDecoder.safe_loads(data, default or {})
        if not isinstance(result, dict):
            logger.warning(f"Retour attendu dict, obtenu {type(result)}")
            return default or {}
        return result
    
    @staticmethod
    def safe_stringify(obj: Any, default=None) -> str:
        """Convertit un objet en JSON sûrement."""
        try:
            return json.dumps(obj, ensure_ascii=True, default=str)
        except Exception as e:
            logger.error(f"Erreur sérialisation JSON: {e}")
            return json.dumps(default or {})


def safe_json_parse_workspace_field(ws: Dict, field: str, default=None) -> Any:
    """
    Parse un champ JSON d'un workspace Dgraph en tolérant les erreurs.
    
    Args:
        ws: Workspace dict depuis Dgraph
        field: Nom du champ JSON (ex: 'fileContents', 'description')
        default: Valeur par défaut
    
    Returns:
        Objet parsé ou valeur par défaut
    """
    raw_value = ws.get(field, default or {})
    
    if isinstance(raw_value, str):
        return JSONSafeDecoder.safe_loads(raw_value, default)
    elif isinstance(raw_value, dict):
        return raw_value
    elif isinstance(raw_value, list):
        return raw_value
    else:
        return default or {}


def repair_workspace_data(ws: Dict) -> Dict:
    """
    Répare tous les champs JSON d'un workspace Dgraph.
    
    Args:
        ws: Workspace dict potentiellement malformé
    
    Returns:
        Workspace dict avec champs JSON réparés
    """
    repaired = ws.copy()
    
    json_fields = ['fileContents', 'description', 'codeContent', 'functions', 'imports', 'relations']
    
    for field in json_fields:
        if field in repaired:
            raw_value = repaired[field]
            
            if isinstance(raw_value, str):
                try:
                    # Essayer de parser
                    repaired[field] = json.loads(raw_value)
                except json.JSONDecodeError:
                    # Réparer et parser
                    repaired[field] = JSONSafeDecoder.safe_loads(raw_value, {})
                    logger.info(f"Champ {field} réparé")
            elif not isinstance(raw_value, (dict, list)):
                repaired[field] = {}
    
    return repaired


# Exemple d'utilisation dans project_config_widget.py
def _workspace_to_profile_safe(ws):
    """
    Conversion workspace -> profile avec gestion JSON sûre.
    Remplace _workspace_to_profile original.
    """
    # Réparer d'abord tous les champs JSON
    ws = repair_workspace_data(ws)
    
    return {
        'workspace_name': ws.get('name', 'Unnamed'),
        'workspace_id': ws.get('id', ws.get('uid', 'unknown')),
        'owner_id': ws.get('ownerId', 'unknown'),
        'updated_at': ws.get('updatedAt', ''),
        'description': ws.get('description', ''),
        'file_contents': ws.get('fileContents', {}),  # Maintenant dict ou {}
        'clusters': ws.get('clusterManagement', {}).get('clusters', []),
    }