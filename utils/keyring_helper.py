import keyring
import json
from utils.logger import logger


class KeyringHelper:
    """Helper centralisé pour gérer l'accès sécurisé aux configurations via keyring"""
    
    KEYRING_SERVICE = "AI_Conductor"
    
    @staticmethod
    def get_platform_config(platform_name):
        """
        Récupère la configuration complète d'une plateforme depuis keyring
        
        Args:
            platform_name: Nom de la plateforme (ChatGPT, Claude, Gemini, etc.)
        
        Returns:
            dict: Configuration complète avec api_key, model, max_tokens, etc.
        """
        try:
            # Essayer le nouveau format (config complète en JSON)
            config_key = f"{platform_name}_config"
            config_json = keyring.get_password(KeyringHelper.KEYRING_SERVICE, config_key)
            
            if config_json:
                config = json.loads(config_json)
                logger.debug(f"✅ Config complète chargée pour {platform_name}")
                return config
            
            # Fallback: ancien format (clé API seule)
            api_key = keyring.get_password(KeyringHelper.KEYRING_SERVICE, platform_name)
            
            if api_key:
                logger.warning(f"⚠️ Migration nécessaire: ancien format détecté pour {platform_name}")
                return {'api_key': api_key}
            
            logger.warning(f"⚠️ Aucune configuration trouvée pour {platform_name}")
            return {}
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON invalide dans keyring pour {platform_name}: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"❌ Erreur keyring pour {platform_name}: {str(e)}")
            return {}
    
    @staticmethod
    def has_api_key(platform_name):
        """Vérifie si une clé API existe pour une plateforme"""
        config = KeyringHelper.get_platform_config(platform_name)
        return bool(config.get('api_key'))
    
    @staticmethod
    def get_api_key(platform_name):
        """Récupère uniquement la clé API d'une plateforme"""
        config = KeyringHelper.get_platform_config(platform_name)
        api_key = config.get('api_key', '')
        if api_key:
            logger.debug(f"✅ Clé API trouvée pour {platform_name}")
        else:
            logger.warning(f"⚠️ Aucune clé API pour {platform_name}")
        return api_key
    
    @staticmethod
    def get_model(platform_name, default=None):
        """Récupère le modèle configuré pour une plateforme"""
        config = KeyringHelper.get_platform_config(platform_name)
        model = config.get('model', default)
        if model:
            logger.debug(f"✅ Modèle trouvé pour {platform_name}: {model}")
        return model
    
    @staticmethod
    def get_max_tokens(platform_name, default=8192):
        """Récupère la limite de tokens pour une plateforme"""
        config = KeyringHelper.get_platform_config(platform_name)
        return config.get('max_tokens', default)