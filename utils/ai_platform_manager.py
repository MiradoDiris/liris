"""
Gestionnaire de plateformes IA robuste avec système de stockage adaptatif
"""
from typing import Dict, List, Optional, Tuple
from utils.logger import logger
from utils.secure_storage import SecureStorage


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
        self._config = {}
    
    @property
    def api_key(self) -> Optional[str]:
        """Récupère la clé API"""
        return self._config.get('api_key')
    
    @api_key.setter
    def api_key(self, value: str):
        """Définit la clé API"""
        self._config['api_key'] = value
    
    @property
    def model(self) -> Optional[str]:
        """Récupère le modèle configuré"""
        return self._config.get('model')
    
    @model.setter
    def model(self, value: str):
        """Définit le modèle"""
        self._config['model'] = value
    
    @property
    def config(self) -> dict:
        """Retourne toute la configuration"""
        return self._config.copy()
    
    def update_config(self, config_dict: dict):
        """Met à jour la configuration complète"""
        self._config.update(config_dict)
    
    @property
    def is_configured(self) -> bool:
        """Vérifie si la plateforme est configurée"""
        return bool(self.api_key and len(self.api_key) > 10)
    
    def __repr__(self):
        return f"AIPlatform({self.name}, configured={self.is_configured})"


class AIPlatformManager:
    """
    Gestionnaire de plateformes IA avec stockage robuste
    Utilise SecureStorage pour garantir la compatibilité multi-plateforme
    """
    
    PLATFORMS_CONFIG = [
        {
            'name': 'Gemini',
            'internal_name': 'gemini',
            'api_key_env': 'GEMINI_API_KEY',
            'color': '#4285F4',
            'icon': 'fa5s.gem',
            'default_model': 'gemini-2.0-flash-exp'
        },
        {
            'name': 'Claude',
            'internal_name': 'claude',
            'api_key_env': 'CLAUDE_API_KEY',
            'color': '#CC9B7A',
            'icon': 'fa5s.brain',
            'default_model': 'claude-3-5-sonnet-20241022'
        },
        {
            'name': 'ChatGPT',
            'internal_name': 'chatgpt',
            'api_key_env': 'OPENAI_API_KEY',
            'color': '#10A37F',
            'icon': 'fa5s.comment-dots',
            'default_model': 'gpt-4o'
        },
        {
            'name': 'Grok',
            'internal_name': 'grok',
            'api_key_env': 'GROK_API_KEY',
            'color': '#000000',
            'icon': 'fa5s.bolt',
            'default_model': 'grok-beta'
        },
        {
            'name': 'DeepSeek',
            'internal_name': 'deepseek',
            'api_key_env': 'DEEPSEEK_API_KEY',
            'color': '#FF6B6B',
            'icon': 'fa5s.brain',
            'default_model': 'deepseek-chat'
        }
    ]
    
    def __init__(self, storage: Optional[SecureStorage] = None):
        """
        Initialise le gestionnaire
        
        Args:
            storage: Instance SecureStorage personnalisée (optionnel)
        """
        self.storage = storage or SecureStorage(app_name="AI_Conductor")
        self.platforms: Dict[str, AIPlatform] = {}
        self._initialize_platforms()
        
        # Log des infos de stockage
        info = self.storage.get_storage_info()
        logger.info(f"🔐 Stockage: mode={info['mode']}, dir={info['config_dir']}")
    
    def _initialize_platforms(self):
        """Initialise toutes les plateformes et charge leurs configurations"""
        for config in self.PLATFORMS_CONFIG:
            platform = AIPlatform(**{k: v for k, v in config.items() if k != 'default_model'})
            self.platforms[platform.internal_name] = platform
            
            # Charger la configuration stockée
            stored_config = self.storage.load(
                key=platform.internal_name,
                category="platforms",
                default={}
            )
            
            if stored_config:
                platform.update_config(stored_config)
                logger.info(f"✅ {platform.name}: configuration chargée")
            else:
                # Tenter de charger depuis l'env (migration)
                import os
                env_key = os.getenv(platform.api_key_env)
                if env_key:
                    platform.api_key = env_key
                    platform.model = config.get('default_model')
                    logger.info(f"⚠️ {platform.name}: chargée depuis .env (migration recommandée)")
        
        configured = len(self.get_configured_platforms())
        logger.info(f"Plateformes: {len(self.platforms)} total, {configured} configurées")
    
    def get_platform(self, internal_name: str) -> Optional[AIPlatform]:
        """Récupère une plateforme par son nom interne"""
        return self.platforms.get(internal_name)
    
    def get_all_platforms(self) -> List[AIPlatform]:
        """Retourne toutes les plateformes"""
        return list(self.platforms.values())
    
    def get_configured_platforms(self) -> List[AIPlatform]:
        """Retourne les plateformes configurées"""
        return [p for p in self.platforms.values() if p.is_configured]
    
    def get_enabled_platforms(self) -> List[AIPlatform]:
        """Retourne les plateformes activées"""
        return [p for p in self.platforms.values() if p.enabled]
    
    def set_platform_config(
        self,
        internal_name: str,
        api_key: str,
        model: Optional[str] = None,
        additional_config: Optional[dict] = None
    ) -> bool:
        """
        Configure une plateforme complète
        
        Args:
            internal_name: Nom interne de la plateforme
            api_key: Clé API
            model: Modèle à utiliser (optionnel)
            additional_config: Configuration additionnelle (optionnel)
        
        Returns:
            bool: True si succès
        """
        platform = self.get_platform(internal_name)
        if not platform:
            logger.error(f"❌ Plateforme '{internal_name}' introuvable")
            return False
        
        # Construction de la configuration complète
        config = {
            'api_key': api_key,
            'model': model or self._get_default_model(internal_name),
        }
        
        if additional_config:
            config.update(additional_config)
        
        # Mise à jour de la plateforme
        platform.update_config(config)
        
        # Sauvegarde sécurisée
        success = self.storage.save(
            key=internal_name,
            value=config,
            category="platforms"
        )
        
        if success:
            logger.info(f"✅ Configuration sauvegardée pour {platform.name}")
        else:
            logger.error(f"❌ Échec sauvegarde pour {platform.name}")
        
        return success
    
    def _get_default_model(self, internal_name: str) -> str:
        """Récupère le modèle par défaut d'une plateforme"""
        for config in self.PLATFORMS_CONFIG:
            if config['internal_name'] == internal_name:
                return config.get('default_model', 'default')
        return 'default'
    
    def remove_platform_config(self, internal_name: str) -> bool:
        """
        Supprime la configuration d'une plateforme
        
        Args:
            internal_name: Nom interne de la plateforme
        
        Returns:
            bool: True si succès
        """
        platform = self.get_platform(internal_name)
        if not platform:
            return False
        
        # Supprimer du stockage
        success = self.storage.delete(
            key=internal_name,
            category="platforms"
        )
        
        # Réinitialiser la plateforme
        if success:
            platform._config = {}
            logger.info(f"🗑️ Configuration supprimée pour {platform.name}")
        
        return success
    
    def validate_api_key(self, internal_name: str) -> Tuple[bool, str]:
        """
        Valide la configuration d'une plateforme
        
        Args:
            internal_name: Nom interne de la plateforme
        
        Returns:
            Tuple[bool, str]: (valide, message)
        """
        platform = self.get_platform(internal_name)
        
        if not platform:
            return False, f"Plateforme '{internal_name}' non trouvée"
        
        if not platform.is_configured:
            return False, f"Clé API non configurée pour {platform.name}"
        
        api_key = platform.api_key
        
        # Validations basiques
        if len(api_key) < 10:
            return False, f"Clé API trop courte pour {platform.name}"
        
        if not platform.model:
            return False, f"Modèle non configuré pour {platform.name}"
        
        return True, f"✅ {platform.name} configuré correctement"
    
    def get_platform_for_combo(self) -> List[Tuple[str, str, str, str]]:
        """
        Prépare les données pour un ComboBox
        
        Returns:
            List[Tuple]: (display_name, internal_name, color, icon)
        """
        combo_data = []
        for platform in self.get_enabled_platforms():
            status_icon = "✓" if platform.is_configured else "○"
            display_name = f"{status_icon} {platform.name}"
            combo_data.append((
                display_name,
                platform.internal_name,
                platform.color,
                platform.icon
            ))
        return combo_data
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques du gestionnaire"""
        storage_info = self.storage.get_storage_info()
        
        return {
            'total_platforms': len(self.platforms),
            'configured': len(self.get_configured_platforms()),
            'enabled': len(self.get_enabled_platforms()),
            'storage_mode': storage_info['mode'],
            'storage_available': True,
            'config_dir': storage_info['config_dir']
        }
    
    def export_config(self) -> dict:
        """
        Exporte toutes les configurations (sans les clés API)
        Utile pour le backup ou le transfert de configuration
        
        Returns:
            dict: Configuration exportable
        """
        export = {}
        for platform in self.get_all_platforms():
            if platform.is_configured:
                config = platform.config.copy()
                # Masquer la clé API pour la sécurité
                if 'api_key' in config:
                    config['api_key'] = "***MASKED***"
                export[platform.internal_name] = config
        return export
    
    def import_config(self, config_dict: dict, overwrite: bool = False) -> int:
        """
        Importe des configurations (ne remplace pas les clés API)
        
        Args:
            config_dict: Dictionnaire de configurations
            overwrite: Si True, écrase les configs existantes
        
        Returns:
            int: Nombre de plateformes importées
        """
        imported = 0
        for internal_name, config in config_dict.items():
            platform = self.get_platform(internal_name)
            if not platform:
                logger.warning(f"⚠️ Plateforme '{internal_name}' ignorée (inconnue)")
                continue
            
            if not overwrite and platform.is_configured:
                logger.info(f"ℹ️ {platform.name} déjà configuré (skip)")
                continue
            
            # Ne pas importer les clés masquées
            if config.get('api_key') == "***MASKED***":
                config.pop('api_key', None)
            
            # Mettre à jour uniquement si il y a une vraie clé ou si overwrite
            if config.get('api_key') or overwrite:
                platform.update_config(config)
                self.storage.save(internal_name, config, category="platforms")
                imported += 1
                logger.info(f"✅ Importé: {platform.name}")
        
        return imported
    
    def migrate_from_old_system(self):
        """
        Migre automatiquement depuis l'ancien système
        (APIConfigManager ou keyring ancien format)
        """
        try:
            from utils.api_config import APIConfigManager
            
            old_manager = APIConfigManager()
            providers = old_manager.list_providers()
            
            migrated = 0
            for provider_key in providers:
                # Trouver la plateforme correspondante
                platform = None
                for p in self.get_all_platforms():
                    if p.internal_name.lower() == provider_key.lower():
                        platform = p
                        break
                
                if not platform:
                    logger.warning(f"⚠️ Provider '{provider_key}' non mappé")
                    continue
                
                # Récupérer l'ancienne clé
                old_key = old_manager.get_api_key(provider_key)
                if old_key and not platform.is_configured:
                    self.set_platform_config(
                        platform.internal_name,
                        old_key,
                        model=self._get_default_model(platform.internal_name)
                    )
                    migrated += 1
                    logger.info(f"✅ Migré: {platform.name}")
            
            if migrated > 0:
                logger.info(f"🔄 Migration terminée: {migrated} plateformes")
            else:
                logger.info("ℹ️ Aucune migration nécessaire")
            
            return migrated
            
        except Exception as e:
            logger.error(f"❌ Erreur migration: {e}")
            return 0
    
    def get_debug_info(self) -> str:
        """Génère un rapport de diagnostic"""
        storage_info = self.storage.get_storage_info()
        
        lines = [
            "=" * 60,
            "AI PLATFORM MANAGER - DIAGNOSTIC",
            "=" * 60,
            "",
            "📊 STATISTIQUES:",
            f"  Total plateformes: {len(self.platforms)}",
            f"  Configurées: {len(self.get_configured_platforms())}",
            f"  Activées: {len(self.get_enabled_platforms())}",
            "",
            "🔐 SYSTÈME DE STOCKAGE:",
            f"  Mode: {storage_info['mode']}",
            f"  Keyring disponible: {storage_info['keyring_available']}",
            f"  Répertoire: {storage_info['config_dir']}",
            f"  Fichier chiffré: {'✓' if storage_info['encrypted_file_exists'] else '✗'}",
            f"  Base SQLite: {'✓' if storage_info['db_file_exists'] else '✗'}",
            "",
            "🤖 PLATEFORMES:",
        ]
        
        for platform in self.get_all_platforms():
            status = "✅ Configurée" if platform.is_configured else "❌ Non configurée"
            model = platform.model or "N/A"
            lines.append(f"  • {platform.name}: {status} | Modèle: {model}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def __repr__(self):
        stats = self.get_statistics()
        return (f"AIPlatformManager("
                f"platforms={stats['total_platforms']}, "
                f"configured={stats['configured']}, "
                f"storage={stats['storage_mode']})")


# ==================== UTILITAIRES ====================

def quick_setup_wizard():
    """
    Assistant de configuration rapide en ligne de commande
    Utile pour le premier démarrage
    """
    print("\n" + "="*60)
    print("🚀 ASSISTANT DE CONFIGURATION - AI CONDUCTOR")
    print("="*60 + "\n")
    
    manager = AIPlatformManager()
    
    # Afficher l'état actuel
    print("📊 État actuel:")
    for platform in manager.get_all_platforms():
        status = "✅" if platform.is_configured else "❌"
        print(f"  {status} {platform.name}")
    
    print("\n" + "-"*60)
    
    # Configuration interactive
    for platform in manager.get_all_platforms():
        if platform.is_configured:
            print(f"\n✓ {platform.name} déjà configuré (skip)")
            continue
        
        print(f"\n🔧 Configuration de {platform.name}")
        response = input(f"  Voulez-vous configurer {platform.name}? (o/N): ").strip().lower()
        
        if response == 'o':
            api_key = input(f"  Entrez votre clé API {platform.name}: ").strip()
            if api_key:
                manager.set_platform_config(
                    platform.internal_name,
                    api_key,
                    model=manager._get_default_model(platform.internal_name)
                )
                print(f"  ✅ {platform.name} configuré!")
    
    print("\n" + "="*60)
    print("✅ Configuration terminée!")
    print("="*60 + "\n")
    
    return manager