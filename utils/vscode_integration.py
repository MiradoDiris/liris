import requests
from PyQt5.QtCore import QObject, pyqtSignal
from utils.logger import logger

class VSCodeIntegration(QObject):
    """Intégration avec VS Code via l'extension Liris"""
    
    code_sent = pyqtSignal(bool, str)  # (success, message)
    connection_changed = pyqtSignal(bool)  # (connected)
    
    def __init__(self, host='127.0.0.1', port=9000):
        super().__init__()
        self.host = host
        self.port = port
        self.base_url = f'http://{host}:{port}'
        logger.info(f"🔌 VSCodeIntegration initialisé: {self.base_url}")
    
    def check_connection(self):
        """Vérifie si le serveur VS Code est accessible"""
        try:
            logger.info(f"🔍 Vérification connexion VS Code: {self.base_url}/ping")
            response = requests.get(f'{self.base_url}/ping', timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ VS Code connecté - Version: {data.get('version', 'N/A')}")
                self.connection_changed.emit(True)
                return True
            else:
                logger.warning(f"⚠️ VS Code ping failed: {response.status_code}")
                self.connection_changed.emit(False)
                return False
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"❌ VS Code non accessible: {e}")
            self.connection_changed.emit(False)
            return False
    
    def send_code_to_vscode(self, file_path, code, action='insert', 
                           target=None, line_number=None, 
                           class_name=None, method_name=None):
        """Envoie du code à VS Code"""
        
        logger.info(f"📤 Envoi vers VS Code:")
        logger.info(f"   - Fichier: {file_path}")
        logger.info(f"   - Action: {action}")
        logger.info(f"   - Code length: {len(code)} chars")
        
        if not self.check_connection():
            error_msg = "VS Code n'est pas accessible"
            logger.error(f"❌ {error_msg}")
            self.code_sent.emit(False, error_msg)
            return False, error_msg
        
        # Construire la requête
        payload = {
            'action': action,
            'filePath': file_path,
            'code': code
        }
        
        if target:
            payload['target'] = target
            logger.info(f"   - Target: {target[:50]}...")
        
        if line_number is not None:
            payload['lineNumber'] = line_number
            logger.info(f"   - Line: {line_number}")
        
        if class_name:
            payload['className'] = class_name
            logger.info(f"   - Class: {class_name}")
        
        if method_name:
            payload['methodName'] = method_name
            logger.info(f"   - Method: {method_name}")
        
        try:
            logger.info(f"🌐 Envoi POST à {self.base_url}/update")
            
            response = requests.post(
                f'{self.base_url}/update',
                json=payload,
                timeout=10
            )
            
            logger.info(f"📥 Réponse VS Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success', False)
                message = result.get('message', 'Code envoyé')
                
                logger.info(f"✅ Succès VS Code: {message}")
                self.code_sent.emit(True, message)
                return True, message
            else:
                error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                error_msg = error_data.get('error', f'Erreur HTTP {response.status_code}')
                
                logger.error(f"❌ Échec VS Code: {error_msg}")
                self.code_sent.emit(False, error_msg)
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout: VS Code ne répond pas"
            logger.error(f"⏱️ {error_msg}")
            self.code_sent.emit(False, error_msg)
            return False, error_msg
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Erreur réseau: {str(e)}"
            logger.error(f"🌐 {error_msg}")
            self.code_sent.emit(False, error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            logger.error(f"💥 {error_msg}")
            import traceback
            traceback.print_exc()
            self.code_sent.emit(False, error_msg)
            return False, error_msg