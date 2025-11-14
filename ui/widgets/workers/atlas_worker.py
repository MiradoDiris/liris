# atlas_worker.py - Worker pour GPT Atlas (Navigation automatique)
import time
import json
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import logger


class AtlasWorker(QThread):
    """Worker pour automatiser la navigation web via GPT Atlas"""
    
    # Signaux
    test_completed = pyqtSignal(bool, str, float, dict)
    step_update = pyqtSignal(str, str)
    debug_info = pyqtSignal(str)
    snippet_generated = pyqtSignal(dict)
    session_created = pyqtSignal(str)  # Émet l'ID de session
    action_completed = pyqtSignal(str, dict)  # action_type, result
    
    def __init__(self, context, perimeter_data, api_key, task_description, parent=None):
        super().__init__(parent)
        
        self.context = context
        self.perimeter_data = perimeter_data
        self.api_key = api_key
        self.task_description = task_description
        self.session_id = None
        self.base_url = "https://api.gptatlas.com/v1"
        self.usage_stats = {
            'input_tokens': 0,
            'output_tokens': 0,
            'actions_count': 0
        }
        
        self.platform_name = "GPT Atlas"
        self.project_name = None
        
    def run(self):
        """Exécute le workflow de navigation automatique"""
        start_time = time.time()
        
        try:
            # Étape 1 : Créer une session de navigation
            self.step_update.emit("session_creation", "🌐 Création de la session de navigation...")
            session_result = self._create_session()
            
            if not session_result.get('success'):
                error_msg = session_result.get('error', 'Session creation failed')
                self.test_completed.emit(False, error_msg, time.time() - start_time, {})
                return
            
            self.session_id = session_result.get('session_id')
            self.session_created.emit(self.session_id)
            self.debug_info.emit(f"✅ Session créée: {self.session_id}")
            
            # Étape 2 : Analyser la tâche et générer le plan d'action
            self.step_update.emit("task_analysis", "🧠 Analyse de la tâche...")
            action_plan = self._analyze_task()
            
            if not action_plan:
                self.test_completed.emit(False, "Impossible d'analyser la tâche", time.time() - start_time, {})
                return
            
            self.debug_info.emit(f"📋 Plan d'action: {len(action_plan)} étapes")
            
            # Étape 3 : Exécuter les actions
            snippets = []
            for idx, action in enumerate(action_plan, 1):
                self.step_update.emit(
                    f"action_{idx}", 
                    f"⚡ Exécution action {idx}/{len(action_plan)}: {action['type']}"
                )
                
                result = self._execute_action(action)
                self.action_completed.emit(action['type'], result)
                
                if result.get('success'):
                    # Générer un snippet si l'action produit du code
                    if action['type'] in ['extract_code', 'generate_code']:
                        snippet = self._create_snippet_from_action(action, result)
                        if snippet:
                            snippets.append(snippet)
                            self.snippet_generated.emit(snippet)
                else:
                    logger.warning(f"⚠️ Action {action['type']} échouée: {result.get('error')}")
            
            # Étape 4 : Fermer la session
            self.step_update.emit("cleanup", "🧹 Nettoyage de la session...")
            self._close_session()
            
            # Résultat final
            duration = time.time() - start_time
            response = {
                'snippets': snippets,
                'actions_executed': len(action_plan),
                'session_id': self.session_id
            }
            
            self.test_completed.emit(True, f"Navigation automatique terminée", duration, response)
            
        except Exception as e:
            logger.error(f"❌ Erreur AtlasWorker: {e}")
            import traceback
            traceback.print_exc()
            
            duration = time.time() - start_time
            self.test_completed.emit(False, str(e), duration, {})
        
        finally:
            if self.session_id:
                self._close_session()
    
    def _create_session(self):
        """Crée une session de navigation GPT Atlas"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "browser": "chrome",
                "headless": False,  # Mode visible pour debug
                "viewport": {
                    "width": 1920,
                    "height": 1080
                }
            }
            
            response = requests.post(
                f"{self.base_url}/session/create",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'session_id': data.get('session_id'),
                    'message': 'Session créée avec succès'
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur création session: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_task(self):
        """Analyse la tâche et génère un plan d'action"""
        # TODO: Utiliser une IA (Claude/GPT) pour analyser la tâche
        # et générer un plan d'action structuré
        
        # Exemple de plan d'action simple
        action_plan = [
            {
                'type': 'navigate',
                'url': 'https://example.com',
                'description': 'Navigation vers le site cible'
            },
            {
                'type': 'wait',
                'duration': 2,
                'description': 'Attente du chargement'
            },
            {
                'type': 'extract_code',
                'selector': 'pre code',
                'description': 'Extraction du code depuis la page'
            }
        ]
        
        return action_plan
    
    def _execute_action(self, action):
        """Exécute une action spécifique"""
        action_type = action['type']
        
        if action_type == 'navigate':
            return self._action_navigate(action['url'])
        
        elif action_type == 'click':
            return self._action_click(action['selector'])
        
        elif action_type == 'type':
            return self._action_type(action['selector'], action['text'])
        
        elif action_type == 'extract_code':
            return self._action_extract(action['selector'])
        
        elif action_type == 'wait':
            time.sleep(action.get('duration', 1))
            return {'success': True}
        
        else:
            return {
                'success': False,
                'error': f"Action type '{action_type}' not supported"
            }
    
    def _action_navigate(self, url):
        """Action : Naviguer vers une URL"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "session_id": self.session_id,
                "url": url,
                "wait_until": "networkidle"
            }
            
            response = requests.post(
                f"{self.base_url}/action/navigate",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.usage_stats['actions_count'] += 1
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _action_click(self, selector):
        """Action : Cliquer sur un élément"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "session_id": self.session_id,
                "selector": selector
            }
            
            response = requests.post(
                f"{self.base_url}/action/click",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                self.usage_stats['actions_count'] += 1
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _action_type(self, selector, text):
        """Action : Saisir du texte"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "session_id": self.session_id,
                "selector": selector,
                "text": text
            }
            
            response = requests.post(
                f"{self.base_url}/action/type",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                self.usage_stats['actions_count'] += 1
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _action_extract(self, selector):
        """Action : Extraire du contenu"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "session_id": self.session_id,
                "selector": selector,
                "extract_type": "text"
            }
            
            response = requests.post(
                f"{self.base_url}/action/extract",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                self.usage_stats['actions_count'] += 1
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'extracted_content': data.get('content', '')
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_snippet_from_action(self, action, result):
        """Crée un snippet depuis le résultat d'une action"""
        if not result.get('success'):
            return None
        
        extracted_content = result.get('extracted_content', '')
        
        if not extracted_content:
            return None
        
        snippet = {
            'title': f"Code extrait - {action.get('description', 'N/A')}",
            'action': 'AJOUTER',
            'file': 'extracted_code.py',
            'code': extracted_content,
            'language': 'python',
            'description': f"Code extrait automatiquement via navigation : {action.get('description', '')}",
            'lineNumber': 0,
            'target': None
        }
        
        return snippet
    
    def _close_session(self):
        """Ferme la session de navigation"""
        if not self.session_id:
            return
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "session_id": self.session_id
            }
            
            requests.post(
                f"{self.base_url}/session/close",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            self.debug_info.emit(f"🔒 Session fermée: {self.session_id}")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture session: {e}")