"""
Module de test des clés API pour différentes plateformes d'IA
"""
import requests
from utils.logger import logger


class ApiTester:
    """Classe pour tester les clés API des différentes plateformes"""
    
    @staticmethod
    def test_api_key(platform_name, api_config):
        """
        Teste la validité de la clé API selon la plateforme
        
        Args:
            platform_name (str): Nom de la plateforme (Claude, Gemini, ChatGPT, etc.)
            api_config (dict): Configuration API contenant api_key, model, etc.
            
        Returns:
            dict: {success: bool, error: str, details: dict}
        """
        try:
            if platform_name == "Claude":
                return ApiTester._test_claude(api_config)
            elif platform_name == "Gemini":
                return ApiTester._test_gemini(api_config)
            elif platform_name == "ChatGPT":
                return ApiTester._test_openai(api_config)
            elif platform_name == "Grok":
                return ApiTester._test_grok(api_config)
            elif platform_name == "DeepSeek":
                return ApiTester._test_deepseek(api_config)
            else:
                return {
                    "success": False,
                    "error": f"Plateforme '{platform_name}' non supportée par le testeur"
                }
        except Exception as e:
            logger.error(f"Erreur test API {platform_name}: {str(e)}")
            return {"success": False, "error": f"Erreur inattendue: {str(e)}"}

    @staticmethod
    def _test_claude(api_config):
        """Test de l'API Anthropic Claude"""
        try:
            base_url = api_config.get("base_url", "https://api.anthropic.com/v1/messages")
            
            # S'assurer que l'URL se termine par /messages
            if not base_url.endswith('/messages'):
                base_url = base_url.rstrip('/') + '/messages'
            
            headers = {
                "x-api-key": api_config["api_key"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            # Ajouter les headers personnalisés si présents
            custom_headers = api_config.get('custom_headers', {})
            if custom_headers:
                headers.update(custom_headers)
            
            payload = {
                "model": api_config.get("model", "claude-3-opus-20240229"),
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Réponds juste: OK"}]
            }
            
            logger.info(f"Test Claude API: {base_url}")
            
            response = requests.post(
                base_url,
                headers=headers,
                json=payload,
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "details": {
                        "status": 200,
                        "model": data.get("model", "N/A"),
                        "usage": data.get("usage", {}),
                        "message": "✅ Clé API Claude valide et fonctionnelle"
                    }
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "🔑 Clé API invalide ou non autorisée (401 Unauthorized)"
                }
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error": "⏱️ Limite de requêtes dépassée (429 Too Many Requests)"
                }
            elif response.status_code == 400:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)
                return {
                    "success": False,
                    "error": f"❌ Requête invalide (400): {error_msg[:200]}"
                }
            else:
                return {
                    "success": False,
                    "error": f"❌ HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "⏱️ Timeout - L'API ne répond pas dans le délai imparti"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "🌐 Erreur de connexion - Vérifiez votre connexion internet"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"🌐 Erreur réseau: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"❌ Erreur: {str(e)}"
            }

    @staticmethod
    def _test_gemini(api_config):
        """Test de l'API Google Gemini"""
        try:
            api_key = api_config.get("api_key")
            model = api_config.get("model", "gemini-pro")
            
            # Construction de l'URL
            base_url = api_config.get("base_url")
            if not base_url:
                base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            
            # Ajouter la clé API à l'URL
            url = f"{base_url}?key={api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": "Réponds juste: OK"}]
                }]
            }
            
            logger.info(f"Test Gemini API: {base_url}")
            
            response = requests.post(
                url,
                json=payload,
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "details": {
                        "status": 200,
                        "model": model,
                        "message": "✅ Clé API Gemini valide et fonctionnelle"
                    }
                }
            elif response.status_code == 400:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)
                return {
                    "success": False,
                    "error": f"🔑 Clé API invalide ou modèle incorrect: {error_msg[:200]}"
                }
            else:
                return {
                    "success": False,
                    "error": f"❌ HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "⏱️ Timeout - L'API ne répond pas"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "🌐 Erreur de connexion"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"❌ Erreur: {str(e)}"
            }

    @staticmethod
    def _test_openai(api_config):
        """Test de l'API OpenAI (ChatGPT)"""
        try:
            base_url = api_config.get("base_url", "https://api.openai.com/v1/chat/completions")
            
            headers = {
                "Authorization": f"Bearer {api_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            # Ajouter les headers personnalisés
            custom_headers = api_config.get('custom_headers', {})
            if custom_headers:
                headers.update(custom_headers)
            
            payload = {
                "model": api_config.get("model", "gpt-3.5-turbo"),
                "messages": [{"role": "user", "content": "Réponds juste: OK"}],
                "max_tokens": 10
            }
            
            logger.info(f"Test OpenAI API: {base_url}")
            
            response = requests.post(
                base_url,
                headers=headers,
                json=payload,
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "details": {
                        "status": 200,
                        "model": data.get("model", "N/A"),
                        "usage": data.get("usage", {}),
                        "message": "✅ Clé API OpenAI valide et fonctionnelle"
                    }
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "🔑 Clé API invalide (401 Unauthorized)"
                }
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error": "⏱️ Limite de requêtes dépassée (429)"
                }
            else:
                return {
                    "success": False,
                    "error": f"❌ HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "⏱️ Timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "🌐 Erreur de connexion"}
        except Exception as e:
            return {"success": False, "error": f"❌ Erreur: {str(e)}"}

    @staticmethod
    def _test_grok(api_config):
        """Test de l'API Grok (xAI)"""
        try:
            base_url = api_config.get("base_url", "https://api.x.ai/v1/chat/completions")
            
            headers = {
                "Authorization": f"Bearer {api_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            custom_headers = api_config.get('custom_headers', {})
            if custom_headers:
                headers.update(custom_headers)
            
            payload = {
                "model": api_config.get("model", "grok-beta"),
                "messages": [{"role": "user", "content": "Réponds juste: OK"}],
                "max_tokens": 10
            }
            
            logger.info(f"Test Grok API: {base_url}")
            
            response = requests.post(
                base_url,
                headers=headers,
                json=payload,
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "details": {
                        "status": 200,
                        "model": data.get("model", "N/A"),
                        "message": "✅ Clé API Grok valide et fonctionnelle"
                    }
                }
            elif response.status_code == 401:
                return {"success": False, "error": "🔑 Clé API invalide"}
            else:
                return {
                    "success": False,
                    "error": f"❌ HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {"success": False, "error": f"❌ Erreur: {str(e)}"}

    @staticmethod
    def _test_deepseek(api_config):
        """Test de l'API DeepSeek"""
        try:
            base_url = api_config.get("base_url", "https://api.deepseek.com/v1/chat/completions")
            
            headers = {
                "Authorization": f"Bearer {api_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            custom_headers = api_config.get('custom_headers', {})
            if custom_headers:
                headers.update(custom_headers)
            
            payload = {
                "model": api_config.get("model", "deepseek-chat"),
                "messages": [{"role": "user", "content": "Réponds juste: OK"}],
                "max_tokens": 10
            }
            
            logger.info(f"Test DeepSeek API: {base_url}")
            
            response = requests.post(
                base_url,
                headers=headers,
                json=payload,
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "details": {
                        "status": 200,
                        "model": data.get("model", "N/A"),
                        "message": "✅ Clé API DeepSeek valide et fonctionnelle"
                    }
                }
            elif response.status_code == 401:
                return {"success": False, "error": "🔑 Clé API invalide"}
            else:
                return {
                    "success": False,
                    "error": f"❌ HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {"success": False, "error": f"❌ Erreur: {str(e)}"}