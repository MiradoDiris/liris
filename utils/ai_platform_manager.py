# ai_platform_manager.py - Gestionnaire des plateformes IA
import os
from typing import Dict, List, Optional, Tuple
from utils.logger import logger
from utils.api_config import APIConfigManager
from utils.keyring_helper import KeyringHelper


class AIPlatform:
    """Représente une plateforme IA avec sa configuration"""
    
    def __init__(
        self,
        name: str,
        internal_name: str,
        api_key_env: str,
        color: str = '#999999',
        icon: str = 'fa5s.robot',
        enabled: bool = True
    ):
        self.name = name
        self.internal_name = internal_name
        self.api_key_env = api_key_env
        self.color = color
        self.icon = icon
        self.enabled = enabled
        self._api_key = None
    
    @property
    def api_key(self) -> Optional[str]:
        """Récupère la clé API depuis Keyring ou la config"""
        if not self._api_key:
            # 🔐 Essayer de récupérer la clé depuis keyring
            key = KeyringHelper.get_api_key(self.name)
            if key:
                self._api_key = key
            else:
                # 🔁 Fallback: ancienne méthode (variable d'environnement)
                env_key = os.getenv(self.api_key_env)
                if env_key:
                    self._api_key = env_key
                    logger.warning(f"⚠️ {self.name}: chargée depuis .env (non sécurisé)")
        return self._api_key
    
    @api_key.setter
    def api_key(self, value: str):
        """Définit la clé API"""
        self._api_key = value
    
    @property
    def is_configured(self) -> bool:
        """Vérifie si la plateforme est configurée avec une clé API"""
        return bool(self.api_key)
    
    def __repr__(self):
        return f"AIPlatform({self.name}, configured={self.is_configured})"


class AIPlatformManager:
    """Gestionnaire centralisé des plateformes IA"""
    
    PLATFORMS_CONFIG = [
        {
            'name': 'Gemini',
            'internal_name': 'gemini',
            'api_key_env': 'GEMINI_API_KEY',
            'color': '#4285F4',
            'icon': 'fa5s.gem'
        },
        {
            'name': 'Claude',
            'internal_name': 'claude',
            'api_key_env': 'CLAUDE_API_KEY',
            'color': '#CC9B7A',
            'icon': 'fa5s.brain'
        },
        {
            'name': 'ChatGPT',
            'internal_name': 'chatgpt',
            'api_key_env': 'OPENAI_API_KEY',
            'color': '#10A37F',
            'icon': 'fa5s.comment-dots'
        },
        {
            'name': 'Grok',
            'internal_name': 'grok',
            'api_key_env': 'GROK_API_KEY',
            'color': '#000000',
            'icon': 'fa5s.bolt'
        }
    ]
    
    def __init__(self, api_config_manager: Optional[APIConfigManager] = None):
        self.api_config = api_config_manager or APIConfigManager()
        self.platforms: Dict[str, AIPlatform] = {}
        self._initialize_platforms()
    
    def _initialize_platforms(self):
        """Initialise toutes les plateformes disponibles"""
        for config in self.PLATFORMS_CONFIG:
            platform = AIPlatform(**config)
            self.platforms[platform.internal_name] = platform
            
            # 🔐 PRIORITÉ 1 : keyring sécurisé
            key = KeyringHelper.get_api_key(platform.name)
            if key:
                platform.api_key = key
                logger.info(f"🔐 {platform.name}: clé chargée depuis keyring")
                continue

            # 🔁 PRIORITÉ 2 : configuration persistante
            stored_key = self.api_config.get_api_key(platform.internal_name)
            if stored_key:
                platform.api_key = stored_key
                logger.info(f"✅ {platform.name}: chargée depuis config persistante")
                continue

            # ⚙️ PRIORITÉ 3 : variable d'environnement (.env)
            if platform.api_key:
                logger.warning(f"⚠️ {platform.name}: chargée depuis .env (non sécurisé)")
            else:
                logger.warning(f"🚫 {platform.name}: aucune clé trouvée")
        
        configured = len(self.get_configured_platforms())
        logger.info(f"Initialized {len(self.platforms)} platforms ({configured} configurées)")
    
    def get_platform(self, internal_name: str) -> Optional[AIPlatform]:
        return self.platforms.get(internal_name)
    
    def get_all_platforms(self) -> List[AIPlatform]:
        return list(self.platforms.values())
    
    def get_configured_platforms(self) -> List[AIPlatform]:
        return [p for p in self.platforms.values() if p.is_configured]
    
    def get_enabled_platforms(self) -> List[AIPlatform]:
        return [p for p in self.platforms.values() if p.enabled]
    
    def set_api_key(self, internal_name: str, api_key: str, save: bool = True):
        """Définit et sauvegarde la clé API dans keyring"""
        platform = self.get_platform(internal_name)
        if not platform:
            logger.warning(f"Plateforme {internal_name} introuvable")
            return False
        
        platform.api_key = api_key
        
        if save:
            # 🔐 Sauvegarde dans keyring sécurisé
            try:
                import keyring, json
                config_json = json.dumps({'api_key': api_key})
                keyring.set_password(KeyringHelper.KEYRING_SERVICE, f"{platform.name}_config", config_json)
                logger.info(f"🔐 Clé API enregistrée dans keyring pour {platform.name}")
            except Exception as e:
                logger.error(f"Erreur sauvegarde keyring ({platform.name}): {e}")
        
        return True
    
    def remove_api_key(self, internal_name: str):
        """Supprime la clé API du keyring"""
        platform = self.get_platform(internal_name)
        if platform:
            try:
                import keyring
                keyring.delete_password(KeyringHelper.KEYRING_SERVICE, f"{platform.name}_config")
                platform.api_key = None
                logger.info(f"🗑️ Clé supprimée pour {platform.name}")
            except Exception as e:
                logger.error(f"Erreur suppression keyring ({platform.name}): {e}")
    
    def validate_api_key(self, internal_name: str) -> Tuple[bool, str]:
        """Valide la présence d'une clé API"""
        platform = self.get_platform(internal_name)
        if not platform:
            return False, f"Plateforme '{internal_name}' non trouvée"
        
        if not platform.is_configured:
            return False, f"Clé API non configurée pour {platform.name}"
        
        api_key = platform.api_key
        if len(api_key) < 10:
            return False, f"Clé API invalide pour {platform.name} (trop courte)"
        
        return True, f"Clé API valide pour {platform.name}"
    
    def get_platform_for_combo(self) -> List[Tuple[str, str, str, str]]:
        combo_data = []
        for platform in self.get_enabled_platforms():
            status_icon = "✓" if platform.is_configured else "○"
            display_name = f"{status_icon} {platform.name}"
            combo_data.append((display_name, platform.internal_name, platform.color, platform.icon))
        return combo_data
    
    def get_statistics(self) -> Dict[str, int]:
        return {
            'total': len(self.platforms),
            'configured': len(self.get_configured_platforms()),
            'enabled': len(self.get_enabled_platforms())
        }
    
    def __repr__(self):
        stats = self.get_statistics()
        return f"AIPlatformManager(total={stats['total']}, configured={stats['configured']}, enabled={stats['enabled']})"
