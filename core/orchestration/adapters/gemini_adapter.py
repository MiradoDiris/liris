# core/orchestration/adapters/gemini_adapter.py

import requests
import json
from typing import Dict, Any, Optional
from utils.logger import logger

class GeminiAdapter:
    """Adapteur pour l'API Google Gemini"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gemini-pro")
        self.base_url = config.get("base_url", "https://generativelanguage.googleapis.com/v1beta/models/")
        self.timeout = config.get("timeout", 60)
        
    def send_prompt(self, prompt: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Envoie un prompt à l'API Gemini"""
        try:
            url = f"{self.base_url}{self.model}:generateContent?key={self.api_key}"
            
            headers = {
                "Content-Type": "application/json",
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "maxOutputTokens": kwargs.get("max_tokens", 8192),
                    "topP": 0.8,
                    "topK": 40
                }
            }
            
            logger.info(f"Envoi du prompt à Gemini: {prompt[:100]}...")
            response = requests.post(
                url, 
                headers=headers, 
                json=data, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("Réponse reçue de Gemini avec succès")
                return self._parse_response(result)
            else:
                logger.error(f"Erreur Gemini API: {response.status_code} - {response.text}")
                return {
                    "status": "error",
                    "error": f"Erreur API: {response.status_code} - {response.text}",
                    "result": None
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à Gemini: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "result": None
            }
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse la réponse de l'API Gemini"""
        try:
            if "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = candidate["content"]["parts"][0].get("text", "")
                    
                    return {
                        "status": "completed",
                        "result": {
                            "response": text,
                            "raw_response": response
                        },
                        "error": None
                    }
            
            return {
                "status": "error",
                "result": None,
                "error": "Réponse invalide de l'API Gemini"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "result": None,
                "error": f"Erreur parsing réponse: {str(e)}"
            }
    
    def test_connection(self) -> bool:
        """Teste la connexion à l'API Gemini"""
        try:
            test_prompt = "Réponds simplement par 'OK' pour confirmer la connexion."
            result = self.send_prompt(test_prompt)
            return result is not None and result.get("status") == "completed"
        except Exception as e:
            logger.error(f"Erreur test connexion Gemini: {str(e)}")
            return False