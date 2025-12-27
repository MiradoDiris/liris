# api_config.py - Gestionnaire de configuration des API (Cross-platform)
import os
import sys
import json
from pathlib import Path
from cryptography.fernet import Fernet
from utils.logger import logger

class APIConfigManager:
    """Gestionnaire sécurisé des clés API - Compatible Windows/Linux/macOS"""
    
    def __init__(self):
        # Configuration des chemins selon l'OS
        self.config_dir = self._get_config_directory()
        self.config_file = self.config_dir / "api_config.enc"
        self.key_file = self.config_dir / ".encryption_key"
        
        # Créer le répertoire si nécessaire
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Charger ou créer la clé de chiffrement
        self._init_encryption()
    
    def _get_config_directory(self) -> Path:
        """Retourne le répertoire de configuration selon l'OS"""
        if sys.platform == "win32":
            # Windows: utilise APPDATA
            base_dir = Path(os.getenv('APPDATA', Path.home()))
            return base_dir / "LirisCoding"
        elif sys.platform == "darwin":
            # macOS: utilise ~/Library/Application Support
            return Path.home() / "Library" / "Application Support" / "LirisCoding"
        else:
            # Linux/Unix: utilise ~/.config ou XDG_CONFIG_HOME
            xdg_config = os.getenv('XDG_CONFIG_HOME')
            if xdg_config:
                return Path(xdg_config) / "liris_coding"
            return Path.home() / ".config" / "liris_coding"
    
    def _init_encryption(self):
        """Initialise le système de chiffrement"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.key)
            
            # Sécuriser le fichier selon l'OS
            self._secure_file(self.key_file)
        
        self.cipher = Fernet(self.key)
    
    def _secure_file(self, filepath: Path):
        """Sécurise un fichier selon l'OS"""
        try:
            if sys.platform == "win32":
                # Windows: utilise icacls pour restreindre l'accès
                import subprocess
                username = os.getenv('USERNAME')
                cmd = [
                    'icacls', str(filepath),
                    '/inheritance:r',  # Supprimer l'héritage
                    '/grant:r', f'{username}:F'  # Accès complet pour l'utilisateur
                ]
                subprocess.run(cmd, capture_output=True, check=False)
                logger.debug(f"Fichier sécurisé (Windows): {filepath}")
            else:
                # Unix/Linux/macOS: chmod classique
                os.chmod(filepath, 0o600)
                logger.debug(f"Fichier sécurisé (Unix): {filepath}")
        except Exception as e:
            logger.warning(f"Impossible de sécuriser {filepath}: {e}")
    
    def save_api_key(self, provider: str, api_key: str):
        """Sauvegarde une clé API de manière sécurisée"""
        try:
            # Charger la config existante
            config = self._load_config()
            
            # Ajouter/Mettre à jour la clé
            config[provider] = api_key
            
            # Sauvegarder
            encrypted_data = self.cipher.encrypt(json.dumps(config).encode())
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
            
            self._secure_file(self.config_file)
            logger.info(f"API key for {provider} saved securely")
            return True
            
        except Exception as e:
            logger.error(f"Error saving API key: {e}")
            return False
    
    def get_api_key(self, provider: str) -> str:
        """Récupère une clé API"""
        try:
            config = self._load_config()
            return config.get(provider, "")
        except Exception as e:
            logger.error(f"Error loading API key: {e}")
            return ""
    
    def delete_api_key(self, provider: str):
        """Supprime une clé API"""
        try:
            config = self._load_config()
            if provider in config:
                del config[provider]
                encrypted_data = self.cipher.encrypt(json.dumps(config).encode())
                with open(self.config_file, 'wb') as f:
                    f.write(encrypted_data)
                logger.info(f"API key for {provider} deleted")
                return True
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return False
    
    def list_providers(self) -> list:
        """Liste les fournisseurs configurés"""
        try:
            config = self._load_config()
            return list(config.keys())
        except:
            return []
    
    def _load_config(self) -> dict:
        """Charge la configuration chiffrée"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.warning(f"Could not load config: {e}")
            return {}
    
    def export_to_env(self):
        """Exporte les clés vers les variables d'environnement"""
        config = self._load_config()
        for provider, key in config.items():
            env_var = f"{provider.upper()}_API_KEY"
            os.environ[env_var] = key
            logger.debug(f"Exported {env_var} to environment")
    
    def get_config_info(self) -> dict:
        """Retourne les informations de configuration"""
        return {
            "config_dir": str(self.config_dir),
            "platform": sys.platform,
            "config_exists": self.config_file.exists(),
            "key_exists": self.key_file.exists()
        }