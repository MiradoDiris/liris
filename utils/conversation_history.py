import json
import time
from typing import List, Dict, Optional
from utils.logger import logger


class ConversationHistory:
    """Gère l'historique des conversations avec l'IA"""
    
    def __init__(self, max_messages: int = 10, max_age_hours: int = 24):
        """
        Initialise l'historique
        
        Args:
            max_messages: Nombre maximum de messages à conserver
            max_age_hours: Âge maximum des messages en heures
        """
        self.messages: List[Dict] = []
        self.max_messages = max_messages
        self.max_age_seconds = max_age_hours * 3600
        self.session_start = time.time()
        
    def add_user_message(self, content: str, metadata: Optional[Dict] = None):
        """Ajoute un message utilisateur"""
        message = {
            'role': 'user',
            'content': content,
            'timestamp': time.time(),
            'metadata': metadata or {}
        }
        self.messages.append(message)
        self._cleanup_old_messages()
        logger.debug(f"Message utilisateur ajouté. Total: {len(self.messages)}")
        
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None):
        """Ajoute un message assistant"""
        message = {
            'role': 'assistant',
            'content': content,
            'timestamp': time.time(),
            'metadata': metadata or {}
        }
        self.messages.append(message)
        self._cleanup_old_messages()
        logger.debug(f"Message assistant ajouté. Total: {len(self.messages)}")
        
    def get_messages_for_api(self, platform: str = 'generic') -> List[Dict]:
        """
        Retourne les messages formatés pour l'API
        
        Args:
            platform: 'claude', 'gemini', 'openai', 'grok'
            
        Returns:
            Liste de messages formatés
        """
        if platform == 'claude':
            return self._format_for_claude()
        elif platform == 'gemini':
            return self._format_for_gemini()
        elif platform in ['openai', 'grok']:
            return self._format_for_openai()
        else:
            return [{'role': msg['role'], 'content': msg['content']} 
                    for msg in self.messages]
    
    def _format_for_claude(self) -> List[Dict]:
        """Formate pour l'API Claude (Anthropic)"""
        return [{'role': msg['role'], 'content': msg['content']} 
                for msg in self.messages]
    
    def _format_for_gemini(self) -> List[Dict]:
        """Formate pour l'API Gemini"""
        # Gemini utilise 'user' et 'model' au lieu de 'assistant'
        formatted = []
        for msg in self.messages:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            formatted.append({'role': role, 'parts': [msg['content']]})
        return formatted
    
    def _format_for_openai(self) -> List[Dict]:
        """Formate pour OpenAI/Grok (compatible)"""
        return [{'role': msg['role'], 'content': msg['content']} 
                for msg in self.messages]
    
    def _cleanup_old_messages(self):
        """Nettoie les messages trop vieux ou en excès"""
        current_time = time.time()
        
        # Supprimer les messages trop vieux
        self.messages = [
            msg for msg in self.messages 
            if current_time - msg['timestamp'] < self.max_age_seconds
        ]
        
        # Limiter le nombre de messages
        if len(self.messages) > self.max_messages:
            # Garder le premier message (contexte initial) et les plus récents
            if self.messages:
                first_msg = self.messages[0]
                recent_msgs = self.messages[-(self.max_messages-1):]
                self.messages = [first_msg] + recent_msgs
                
    def clear(self):
        """Efface tout l'historique"""
        self.messages.clear()
        self.session_start = time.time()
        logger.info("Historique de conversation effacé")
        
    def get_summary(self) -> Dict:
        """Retourne un résumé de l'historique"""
        return {
            'message_count': len(self.messages),
            'user_messages': sum(1 for m in self.messages if m['role'] == 'user'),
            'assistant_messages': sum(1 for m in self.messages if m['role'] == 'assistant'),
            'session_duration_minutes': (time.time() - self.session_start) / 60,
            'oldest_message_age_minutes': (time.time() - self.messages[0]['timestamp']) / 60 if self.messages else 0
        }
    
    def export_to_json(self, filepath: str):
        """Exporte l'historique en JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'session_start': self.session_start,
                    'messages': self.messages,
                    'summary': self.get_summary()
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Historique exporté vers {filepath}")
        except Exception as e:
            logger.error(f"Erreur export historique: {e}")
            
    def import_from_json(self, filepath: str):
        """Importe un historique depuis JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.session_start = data.get('session_start', time.time())
                self.messages = data.get('messages', [])
            logger.info(f"Historique importé depuis {filepath}")
        except Exception as e:
            logger.error(f"Erreur import historique: {e}")