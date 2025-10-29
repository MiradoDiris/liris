import json
import os
import requests
import uuid
import hashlib
import hmac
import platform
import base64
from utils.logger import logger

# --- Configuration ---
LICENSE_FILE = "app_license.json"
MAX_FREE_PROMPTS = 30
BACKEND_BASE_URL = "https://your-backend-url.com"  # TODO: REMPLACEZ PAR VOTRE URL
VERIFY_LICENSE_ENDPOINT = f"{BACKEND_BASE_URL}/api/verify_license"

# --- Paramètres de chiffrement ---
XOR_KEY = b"YourSuperSecretXORKeyForLicenseFile1234567890"
HMAC_SECRET = b"AnotherSuperSecretHMACKeyForLicenseIntegrity"


class LicenseManager:
    """
    Gère la logique de licence pour l'application, y compris le suivi d'utilisation,
    la vérification des clés d'activation et le stockage local sécurisé.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._license_data = self._load_license_data()
        self._initialized = True

    def _get_machine_id(self) -> str:
        """
        Génère une empreinte unique de la machine basée sur l'adresse MAC.
        """
        try:
            mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) 
                                   for i in range(0, 8*6, 8)][::-1])
            
            if mac_address == "00:00:00:00:00:00" and platform.system() == "Windows":
                import subprocess
                output = subprocess.check_output("getmac").decode().splitlines()
                for line in output:
                    if "Media disconnected" not in line and "Local Area Connection" in line:
                        mac_address = line.split()[0].replace('-', ':')
                        break
            
            if mac_address == "00:00:00:00:00:00":
                mac_address = hashlib.sha256(str(uuid.getnode()).encode('utf-8')).hexdigest()
            
            return mac_address
        except Exception as e:
            logger.error(f"Erreur récupération ID machine: {e}")
            return hashlib.sha256(
                platform.node().encode('utf-8') + 
                platform.system().encode('utf-8')
            ).hexdigest()

    def _xor_cipher(self, data: bytes, key: bytes) -> bytes:
        """Applique un chiffrement XOR simple."""
        return bytes(data_byte ^ key[i % len(key)] for i, data_byte in enumerate(data))

    def _generate_hmac(self, data: bytes, secret: bytes) -> str:
        """Génère un HMAC pour l'intégrité des données."""
        return hmac.new(secret, data, hashlib.sha256).hexdigest()

    def _get_default_license_data(self) -> dict:
        """Retourne la structure de données de licence par défaut."""
        return {
            "usage_count": 0,
            "is_activated": False,
            "machine_id": self._get_machine_id(),
            "last_verified_key": None,
        }

    def _load_license_data(self) -> dict:
        """
        Charge les données de licence depuis le fichier local.
        Déchiffre et vérifie l'intégrité.
        """
        if not os.path.exists(LICENSE_FILE):
            logger.info(f"Fichier de licence '{LICENSE_FILE}' non trouvé. Création.")
            data = self._get_default_license_data()
            self._save_license_data(data)
            return data

        try:
            with open(LICENSE_FILE, "rb") as f:
                encoded_content = f.read()

            parts = encoded_content.split(b":", 1)
            if len(parts) != 2:
                logger.warning("Fichier de licence malformé. Réinitialisation.")
                return self._reset_license_data()

            received_hmac_hex, encoded_data_b64 = parts
            encoded_data = base64.b64decode(encoded_data_b64)
            decrypted_data_bytes = self._xor_cipher(encoded_data, XOR_KEY)

            # Vérifier l'HMAC
            expected_hmac = self._generate_hmac(decrypted_data_bytes, HMAC_SECRET)
            if expected_hmac != received_hmac_hex.decode('utf-8'):
                logger.warning("Erreur d'intégrité HMAC. Le fichier a été altéré.")
                return self._reset_license_data()

            data = json.loads(decrypted_data_bytes.decode('utf-8'))

            # Vérifier l'ID machine
            if data.get("machine_id") != self._get_machine_id():
                logger.warning("ID machine ne correspond pas. Réinitialisation.")
                return self._reset_license_data()

            return data

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Erreur lecture licence: {e}. Réinitialisation.")
            return self._reset_license_data()
        except Exception as e:
            logger.error(f"Erreur inattendue chargement licence: {e}")
            return self._reset_license_data()

    def _save_license_data(self, data: dict):
        """
        Sauvegarde les données de licence dans le fichier local.
        Chiffre et ajoute un HMAC pour la sécurité.
        """
        try:
            data["machine_id"] = self._get_machine_id()
            plain_data_bytes = json.dumps(data, indent=4).encode('utf-8')

            encrypted_data_bytes = self._xor_cipher(plain_data_bytes, XOR_KEY)
            encrypted_data_b64 = base64.b64encode(encrypted_data_bytes)
            hmac_hex = self._generate_hmac(plain_data_bytes, HMAC_SECRET)

            content_to_write = f"{hmac_hex}:".encode('utf-8') + encrypted_data_b64

            with open(LICENSE_FILE, "wb") as f:
                f.write(content_to_write)
            self._license_data = data
            logger.info("Données de licence sauvegardées avec succès")
        except Exception as e:
            logger.error(f"Erreur sauvegarde licence: {e}")

    def _reset_license_data(self) -> dict:
        """Réinitialise les données de licence à leur état par défaut."""
        new_data = self._get_default_license_data()
        self._save_license_data(new_data)
        return new_data

    def is_activated(self) -> bool:
        """Vérifie si l'application est activée."""
        return self._license_data.get("is_activated", False)

    def get_usage_count(self) -> int:
        """Retourne le nombre d'utilisations enregistrées."""
        return self._license_data.get("usage_count", 0)

    def get_remaining_prompts(self) -> int:
        """Retourne le nombre de prompts restants."""
        if self.is_activated():
            return -1  # Illimité
        return max(0, MAX_FREE_PROMPTS - self.get_usage_count())

    def increment_usage(self):
        """Incrémente le compteur d'utilisation et sauvegarde."""
        if not self.is_activated():
            self._license_data["usage_count"] = self.get_usage_count() + 1
            self._save_license_data(self._license_data)
            remaining = self.get_remaining_prompts()
            logger.info(f"Compteur: {self.get_usage_count()}/{MAX_FREE_PROMPTS} - Restant: {remaining}")

    def can_use_app(self) -> bool:
        """
        Détermine si l'utilisateur peut utiliser l'application.
        """
        if self.is_activated():
            return True
        return self.get_usage_count() < MAX_FREE_PROMPTS

    def verify_license_online(self, license_key: str) -> bool:
        """
        Envoie la clé de licence au backend pour vérification.
        Si valide, active l'application localement.
        """
        logger.info(f"Vérification de la clé de licence en ligne...")
        try:
            payload = {
                "license_key": license_key,
                "machine_id": self._get_machine_id()
            }
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(
                VERIFY_LICENSE_ENDPOINT, 
                json=payload, 
                headers=headers, 
                timeout=10
            )
            response.raise_for_status()

            result = response.json()

            if result.get("status") == "success":
                self._license_data["is_activated"] = True
                self._license_data["last_verified_key"] = license_key
                self._save_license_data(self._license_data)
                logger.info("✅ Clé validée. Application activée définitivement.")
                return True
            else:
                logger.warning(f"Clé invalide: {result.get('message', 'Aucun message')}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Erreur: Timeout du serveur backend.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Erreur: Impossible de se connecter au backend.")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur réseau: {e}")
            return False
        except json.JSONDecodeError:
            logger.error("Erreur: Réponse backend invalide (pas de JSON).")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue vérification licence: {e}")
            return False


# Instance singleton
license_manager = LicenseManager()