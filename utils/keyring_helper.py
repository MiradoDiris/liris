import json
import sys
from utils.logger import logger

class KeyringHelper:
    """Helper centralisé pour gérer l'accès sécurisé aux configurations via keyring"""
    
    KEYRING_SERVICE = "AI_Conductor"
    _keyring_available = None
    
    @staticmethod
    def _check_keyring_availability():
        """Vérifie si keyring est disponible sur ce système"""
        if KeyringHelper._keyring_available is not None:
            return KeyringHelper._keyring_available
        
        try:
            import keyring
            # Tester l'accès au backend
            keyring.get_keyring()
            KeyringHelper._keyring_available = True
            logger.info(f"✅ Keyring disponible: {keyring.get_keyring()}")
        except Exception as e:
            KeyringHelper._keyring_available = False
            logger.warning(f"⚠️ Keyring non disponible: {e}")
            
            if sys.platform.startswith('linux'):
                logger.info("💡 Sur Linux, installer: sudo apt-get install python3-secretstorage")
        
        return KeyringHelper._keyring_available
    
    @staticmethod
    def get_platform_config(platform_name):
        """
        Récupère la configuration complète d'une plateforme depuis keyring
        
        Args:
            platform_name: Nom de la plateforme (ChatGPT, Claude, Gemini, etc.)
        
        Returns:
            dict: Configuration complète avec api_key, model, max_tokens, etc.
        """
        # Vérifier la disponibilité de keyring
        if not KeyringHelper._check_keyring_availability():
            logger.debug(f"Keyring non disponible, retour config vide pour {platform_name}")
            return {}
        
        try:
            import keyring
            
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
            
            logger.debug(f"ℹ️ Aucune configuration trouvée pour {platform_name}")
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
            logger.debug(f"ℹ️ Aucune clé API pour {platform_name}")
        return api_key
    
    @staticmethod
    def set_api_key(platform_name, api_key, additional_config=None):
        """
        Enregistre une clé API dans keyring
        
        Args:
            platform_name: Nom de la plateforme
            api_key: Clé API à enregistrer
            additional_config: Configuration supplémentaire (model, max_tokens, etc.)
        
        Returns:
            bool: True si succès, False sinon
        """
        if not KeyringHelper._check_keyring_availability():
            logger.error("❌ Impossible d'enregistrer: keyring non disponible")
            return False
        
        try:
            import keyring
            
            # Préparer la configuration complète
            config = {'api_key': api_key}
            if additional_config:
                config.update(additional_config)
            
            # Enregistrer
            config_key = f"{platform_name}_config"
            config_json = json.dumps(config)
            keyring.set_password(KeyringHelper.KEYRING_SERVICE, config_key, config_json)
            
            logger.info(f"✅ Configuration enregistrée pour {platform_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement keyring pour {platform_name}: {e}")
            return False
    
    @staticmethod
    def delete_api_key(platform_name):
        """Supprime une clé API du keyring"""
        if not KeyringHelper._check_keyring_availability():
            logger.warning("⚠️ Keyring non disponible")
            return False
        
        try:
            import keyring
            
            config_key = f"{platform_name}_config"
            keyring.delete_password(KeyringHelper.KEYRING_SERVICE, config_key)
            
            # Essayer aussi l'ancien format
            try:
                keyring.delete_password(KeyringHelper.KEYRING_SERVICE, platform_name)
            except:
                pass
            
            logger.info(f"🗑️ Clé supprimée pour {platform_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression keyring pour {platform_name}: {e}")
            return False
    
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
    
    @staticmethod
    def get_system_info():
        """Retourne les informations sur la disponibilité de keyring"""
        is_available = KeyringHelper._check_keyring_availability()
        
        info = {
            "available": is_available,
            "platform": sys.platform
        }
        
        if is_available:
            try:
                import keyring
                info["backend"] = str(keyring.get_keyring())
            except:
                pass
        
        return info