"""
Système de stockage sécurisé multi-plateforme avec fallback intelligent
Combine plusieurs approches pour garantir la compatibilité
"""
import os
import json
import hashlib
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from utils.logger import logger


class SecureStorage:
    """
    Gestionnaire de stockage sécurisé avec cascade de solutions :
    1. Keyring système (si disponible)
    2. Fichier chiffré avec dérivation de clé
    3. SQLite chiffré (fallback ultime)
    """
    
    def __init__(self, app_name: str = "AI_Conductor"):
        self.app_name = app_name
        self.system_info = self._get_system_info()
        
        # Chemins de configuration
        self.config_dir = self._get_safe_config_dir()
        self.encrypted_file = self.config_dir / "secure_config.dat"
        self.salt_file = self.config_dir / ".salt"
        self.db_file = self.config_dir / "secure_storage.db"
        
        # Détection des capacités du système
        self.keyring_available = self._check_keyring()
        self.storage_mode = self._determine_storage_mode()
        
        # Initialisation
        self._init_storage()
        
        logger.info(f"🔐 SecureStorage initialisé : mode={self.storage_mode}, système={self.system_info['os']}")
    
    def _get_system_info(self) -> Dict[str, str]:
        """Collecte des informations système pour adaptation"""
        return {
            'os': platform.system(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python': platform.python_version(),
            'node': platform.node()
        }
    
    def _get_safe_config_dir(self) -> Path:
        """
        Trouve le meilleur emplacement pour la configuration
        Gère les cas problématiques (réseaux, permissions, etc.)
        """
        # Liste des emplacements par ordre de préférence
        candidates = []
        
        # 1. Répertoire utilisateur standard
        try:
            home = Path.home()
            if home.exists() and os.access(home, os.W_OK):
                candidates.append(home / f".{self.app_name.lower()}")
        except Exception as e:
            logger.warning(f"Path.home() inaccessible: {e}")
        
        # 2. APPDATA sur Windows
        if platform.system() == "Windows":
            appdata = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
            if appdata:
                candidates.append(Path(appdata) / self.app_name)
        
        # 3. XDG_CONFIG_HOME sur Linux
        if platform.system() == "Linux":
            xdg_config = os.getenv("XDG_CONFIG_HOME")
            if xdg_config:
                candidates.append(Path(xdg_config) / self.app_name)
        
        # 4. Répertoire temporaire (dernier recours)
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / f".{self.app_name.lower()}"
        candidates.append(temp_dir)
        
        # Tester chaque candidat
        for path in candidates:
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Test d'écriture
                test_file = path / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                
                logger.info(f"✅ Répertoire config: {path}")
                return path
            except Exception as e:
                logger.debug(f"❌ {path} inaccessible: {e}")
                continue
        
        # Si rien ne marche, utiliser le répertoire courant
        fallback = Path("./config")
        fallback.mkdir(exist_ok=True)
        logger.warning(f"⚠️ Utilisation répertoire local: {fallback}")
        return fallback
    
    def _check_keyring(self) -> bool:
        """Vérifie la disponibilité réelle de keyring"""
        try:
            import keyring
            
            # Test d'écriture/lecture
            test_service = f"{self.app_name}_test"
            test_key = "_availability_check_"
            test_value = "test123"
            
            keyring.set_password(test_service, test_key, test_value)
            result = keyring.get_password(test_service, test_key)
            keyring.delete_password(test_service, test_key)
            
            if result == test_value:
                logger.info("✅ Keyring système disponible")
                return True
            else:
                logger.warning("⚠️ Keyring disponible mais incohérent")
                return False
                
        except ImportError:
            logger.warning("⚠️ Module keyring non installé")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Keyring indisponible: {str(e)[:100]}")
            return False
    
    def _determine_storage_mode(self) -> str:
        """Détermine le meilleur mode de stockage"""
        if self.keyring_available:
            return "keyring"
        elif self._is_sqlite_available():
            return "sqlite_encrypted"
        else:
            return "file_encrypted"
    
    def _is_sqlite_available(self) -> bool:
        """Vérifie si SQLite est disponible"""
        try:
            import sqlite3
            return True
        except ImportError:
            return False
    
    def _init_storage(self):
        """Initialise le système de stockage selon le mode"""
        if self.storage_mode == "keyring":
            self._init_keyring()
        elif self.storage_mode == "sqlite_encrypted":
            self._init_sqlite()
        else:
            self._init_file_encryption()
    
    def _init_keyring(self):
        """Initialisation keyring (rien à faire)"""
        pass
    
    def _init_sqlite(self):
        """Initialise la base SQLite chiffrée"""
        import sqlite3
        
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Table des configurations chiffrées
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS secure_config (
                        key TEXT PRIMARY KEY,
                        encrypted_value BLOB NOT NULL,
                        salt BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("✅ SQLite chiffré initialisé")
                
        except Exception as e:
            logger.error(f"❌ Erreur init SQLite: {e}")
            # Fallback vers fichier
            self.storage_mode = "file_encrypted"
            self._init_file_encryption()
    
    def _init_file_encryption(self):
        """Initialise le chiffrement par fichier"""
        if not self.salt_file.exists():
            # Générer un salt unique par machine
            import secrets
            salt = secrets.token_bytes(32)
            self.salt_file.write_bytes(salt)
            os.chmod(self.salt_file, 0o600)
            logger.info("🔑 Salt généré pour chiffrement")
    
    def _get_encryption_key(self) -> bytes:
        """
        Génère une clé de chiffrement dérivée de l'identité machine
        Plus sécurisé qu'une clé statique
        """
        # Charger ou créer le salt
        if self.salt_file.exists():
            salt = self.salt_file.read_bytes()
        else:
            import secrets
            salt = secrets.token_bytes(32)
            self.salt_file.write_bytes(salt)
            os.chmod(self.salt_file, 0o600)
        
        # Créer un identifiant machine unique
        machine_id = f"{self.system_info['node']}_{self.system_info['machine']}"
        
        # Dérivation de clé avec PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(machine_id.encode())
        
        # Encoder en base64 pour Fernet
        import base64
        return base64.urlsafe_b64encode(key)
    
    # ==================== API PUBLIQUE ====================
    
    def save(self, key: str, value: Any, category: str = "default") -> bool:
        """
        Sauvegarde une valeur de manière sécurisée
        
        Args:
            key: Identifiant de la donnée
            value: Valeur à stocker (str, dict, list, etc.)
            category: Catégorie optionnelle (ex: "api_keys", "settings")
        
        Returns:
            bool: True si succès
        """
        full_key = f"{category}:{key}"
        
        try:
            # Conversion en JSON si nécessaire
            if not isinstance(value, str):
                value = json.dumps(value)
            
            if self.storage_mode == "keyring":
                return self._save_keyring(full_key, value)
            elif self.storage_mode == "sqlite_encrypted":
                return self._save_sqlite(full_key, value)
            else:
                return self._save_file(full_key, value)
                
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde '{key}': {e}")
            return False
    
    def load(self, key: str, category: str = "default", default=None) -> Any:
        """
        Charge une valeur stockée
        
        Args:
            key: Identifiant de la donnée
            category: Catégorie
            default: Valeur par défaut si non trouvé
        
        Returns:
            La valeur stockée ou default
        """
        full_key = f"{category}:{key}"
        
        try:
            if self.storage_mode == "keyring":
                value = self._load_keyring(full_key)
            elif self.storage_mode == "sqlite_encrypted":
                value = self._load_sqlite(full_key)
            else:
                value = self._load_file(full_key)
            
            if value is None:
                return default
            
            # Tenter de parser le JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error(f"❌ Erreur chargement '{key}': {e}")
            return default
    
    def delete(self, key: str, category: str = "default") -> bool:
        """Supprime une valeur stockée"""
        full_key = f"{category}:{key}"
        
        try:
            if self.storage_mode == "keyring":
                return self._delete_keyring(full_key)
            elif self.storage_mode == "sqlite_encrypted":
                return self._delete_sqlite(full_key)
            else:
                return self._delete_file(full_key)
        except Exception as e:
            logger.error(f"❌ Erreur suppression '{key}': {e}")
            return False
    
    def list_keys(self, category: str = "default") -> list:
        """Liste toutes les clés d'une catégorie"""
        try:
            if self.storage_mode == "keyring":
                return self._list_keyring(category)
            elif self.storage_mode == "sqlite_encrypted":
                return self._list_sqlite(category)
            else:
                return self._list_file(category)
        except Exception as e:
            logger.error(f"❌ Erreur listage catégorie '{category}': {e}")
            return []
    
    # ==================== IMPLÉMENTATIONS KEYRING ====================
    
    def _save_keyring(self, key: str, value: str) -> bool:
        import keyring
        keyring.set_password(self.app_name, key, value)
        logger.debug(f"💾 Keyring: sauvegardé '{key}'")
        return True
    
    def _load_keyring(self, key: str) -> Optional[str]:
        import keyring
        value = keyring.get_password(self.app_name, key)
        logger.debug(f"📂 Keyring: chargé '{key}' = {bool(value)}")
        return value
    
    def _delete_keyring(self, key: str) -> bool:
        import keyring
        try:
            keyring.delete_password(self.app_name, key)
            logger.debug(f"🗑️ Keyring: supprimé '{key}'")
            return True
        except keyring.errors.PasswordDeleteError:
            return False
    
    def _list_keyring(self, category: str) -> list:
        # Keyring ne permet pas de lister facilement
        # On utilise un index stocké
        index_key = f"_index_{category}"
        index = self._load_keyring(index_key)
        if index:
            try:
                return json.loads(index)
            except:
                return []
        return []
    
    # ==================== IMPLÉMENTATIONS SQLITE ====================
    
    def _save_sqlite(self, key: str, value: str) -> bool:
        import sqlite3
        
        # Chiffrement de la valeur
        cipher = Fernet(self._get_encryption_key())
        encrypted = cipher.encrypt(value.encode())
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO secure_config (key, encrypted_value, salt, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, encrypted, self.salt_file.read_bytes()))
            conn.commit()
        
        logger.debug(f"💾 SQLite: sauvegardé '{key}'")
        return True
    
    def _load_sqlite(self, key: str) -> Optional[str]:
        import sqlite3
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT encrypted_value FROM secure_config WHERE key = ?", (key,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        # Déchiffrement
        cipher = Fernet(self._get_encryption_key())
        decrypted = cipher.decrypt(row[0]).decode()
        
        logger.debug(f"📂 SQLite: chargé '{key}'")
        return decrypted
    
    def _delete_sqlite(self, key: str) -> bool:
        import sqlite3
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM secure_config WHERE key = ?", (key,))
            conn.commit()
        
        logger.debug(f"🗑️ SQLite: supprimé '{key}'")
        return True
    
    def _list_sqlite(self, category: str) -> list:
        import sqlite3
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key FROM secure_config WHERE key LIKE ?", (f"{category}:%",))
            rows = cursor.fetchall()
        
        return [row[0].split(":", 1)[1] for row in rows]
    
    # ==================== IMPLÉMENTATIONS FICHIER ====================
    
    def _save_file(self, key: str, value: str) -> bool:
        # Charger la config existante
        config = self._load_file_config()
        config[key] = value
        
        # Chiffrement
        cipher = Fernet(self._get_encryption_key())
        encrypted = cipher.encrypt(json.dumps(config).encode())
        
        # Sauvegarde atomique
        temp_file = self.encrypted_file.with_suffix(".tmp")
        temp_file.write_bytes(encrypted)
        temp_file.replace(self.encrypted_file)
        
        os.chmod(self.encrypted_file, 0o600)
        logger.debug(f"💾 Fichier: sauvegardé '{key}'")
        return True
    
    def _load_file(self, key: str) -> Optional[str]:
        config = self._load_file_config()
        value = config.get(key)
        logger.debug(f"📂 Fichier: chargé '{key}' = {bool(value)}")
        return value
    
    def _delete_file(self, key: str) -> bool:
        config = self._load_file_config()
        if key in config:
            del config[key]
            # Re-sauvegarder
            cipher = Fernet(self._get_encryption_key())
            encrypted = cipher.encrypt(json.dumps(config).encode())
            self.encrypted_file.write_bytes(encrypted)
            logger.debug(f"🗑️ Fichier: supprimé '{key}'")
            return True
        return False
    
    def _list_file(self, category: str) -> list:
        config = self._load_file_config()
        prefix = f"{category}:"
        return [k.split(":", 1)[1] for k in config.keys() if k.startswith(prefix)]
    
    def _load_file_config(self) -> dict:
        """Charge la configuration chiffrée depuis le fichier"""
        if not self.encrypted_file.exists():
            return {}
        
        try:
            cipher = Fernet(self._get_encryption_key())
            encrypted = self.encrypted_file.read_bytes()
            decrypted = cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"❌ Erreur déchiffrement config: {e}")
            return {}
    
    # ==================== UTILITAIRES ====================
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le système de stockage"""
        return {
            'mode': self.storage_mode,
            'keyring_available': self.keyring_available,
            'config_dir': str(self.config_dir),
            'system': self.system_info,
            'encrypted_file_exists': self.encrypted_file.exists(),
            'db_file_exists': self.db_file.exists()
        }
    
    def migrate_from_old_storage(self, old_api_config_manager):
        """
        Migre les données depuis l'ancien système
        
        Args:
            old_api_config_manager: Instance de APIConfigManager
        """
        try:
            providers = old_api_config_manager.list_providers()
            for provider in providers:
                api_key = old_api_config_manager.get_api_key(provider)
                if api_key:
                    self.save(provider, api_key, category="api_keys")
                    logger.info(f"✅ Migré: {provider}")
            
            logger.info(f"🔄 Migration terminée: {len(providers)} clés")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur migration: {e}")
            return False