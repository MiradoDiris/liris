# session_history_manager.py
"""
Gestionnaire d'historique de sessions pour CodingPanel
Réutilise l'infrastructure existante de conversation_history
"""
import json
from pathlib import Path
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta

from utils.logger import logger


def load_session_into_history(coding_panel, session_file_path: str):
    """
    Charge une session JSON dans l'historique existant du CodingPanel
    
    Args:
        coding_panel: Instance de CodingPanel
        session_file_path: Chemin vers le fichier JSON de session
    """
    try:
        with open(session_file_path, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        messages = session_data.get('messages', [])
        
        if not messages:
            QtWidgets.QMessageBox.warning(
                coding_panel,
                "Session vide",
                "Cette session ne contient aucun message."
            )
            return False
        
        # Réinitialiser l'historique actuel
        if coding_panel.conversation_history:
            coding_panel.conversation_history.clear()
            
            # Charger tous les messages
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content', '')
                
                # Ajouter le message à l'historique
                coding_panel.conversation_history.add_message(
                    role=role,
                    content=content
                )
            
            logger.info(f"Session chargée: {len(messages)} messages")
            
            # Mettre à jour l'interface
            coding_panel._update_history_button_state()
            
            # Si l'accordéon est ouvert, rafraîchir l'affichage
            if coding_panel.global_history_accordion.isVisible():
                coding_panel._populate_global_history()
            
            # Ouvrir automatiquement l'historique pour montrer les messages chargés
            if not coding_panel.global_history_accordion.isVisible():
                coding_panel._toggle_global_history()
            
            session_id = session_data.get('session_id', 'N/A')
            platform = session_data.get('metadata', {}).get('platform', 'N/A')
            
            QtWidgets.QMessageBox.information(
                coding_panel,
                "Session chargée",
                f"{len(messages)} messages chargés\n\n"
                f"Session: {session_id}\n"
                f"Plateforme: {platform.upper()}"
            )
            
            return True
        
        return False
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur JSON: {e}")
        QtWidgets.QMessageBox.critical(
            coding_panel,
            "Erreur de format",
            f"Le fichier de session est corrompu:\n{str(e)}"
        )
        return False
        
    except Exception as e:
        logger.error(f"Erreur chargement session: {e}")
        QtWidgets.QMessageBox.critical(
            coding_panel,
            "Erreur",
            f"Impossible de charger la session:\n{str(e)}"
        )
        return False


class SessionHistoryDialog(QtWidgets.QDialog):
    """
    Dialogue léger pour sélectionner une session à charger
    Utilise la fonctionnalité d'historique existante du CodingPanel
    """
    
    session_selected = pyqtSignal(str)  # Émet le chemin du fichier sélectionné
    
    def __init__(self, sessions_folder: str = "sessions", parent=None):
        super().__init__(parent)
        self.sessions_folder = Path(sessions_folder)
        self.sessions_folder.mkdir(exist_ok=True)
        
        self.setWindowTitle("Charger une session")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        self._init_ui()
        self._load_sessions()
    
    def _init_ui(self):
        """Interface simple de sélection"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # En-tête
        header_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("Sessions sauvegardées")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #333;
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Bouton rafraîchir
        refresh_button = QtWidgets.QPushButton()
        refresh_button.setIcon(qta.icon('fa5s.sync-alt', color='#666'))
        refresh_button.setToolTip("Rafraîchir")
        refresh_button.clicked.connect(self._load_sessions)
        refresh_button.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                min-width: 36px;
                max-width: 36px;
            }
            QPushButton:hover {
                background: #f5f5f5;
            }
        """)
        header_layout.addWidget(refresh_button)
        
        layout.addLayout(header_layout)
        
        # Recherche
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.textChanged.connect(self._filter_sessions)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #A23B2D;
            }
        """)
        layout.addWidget(self.search_input)
        
        # Liste des sessions
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #f9f9f9;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        
        self.sessions_container = QtWidgets.QWidget()
        self.sessions_layout = QtWidgets.QVBoxLayout(self.sessions_container)
        self.sessions_layout.setSpacing(10)
        self.sessions_layout.setContentsMargins(10, 10, 10, 10)
        self.sessions_layout.addStretch()
        
        scroll_area.setWidget(self.sessions_container)
        layout.addWidget(scroll_area)
        
        # Bouton fermer
        close_button = QtWidgets.QPushButton("Annuler")
        close_button.clicked.connect(self.reject)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                padding: 10px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
    
    def _load_sessions(self):
        """Charge les sessions disponibles"""
        while self.sessions_layout.count() > 1:
            item = self.sessions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        session_files = sorted(
            self.sessions_folder.glob("session_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not session_files:
            no_sessions_label = QtWidgets.QLabel("Aucune session trouvée")
            no_sessions_label.setAlignment(Qt.AlignCenter)
            no_sessions_label.setStyleSheet("""
                font-size: 14px;
                color: #999;
                padding: 40px;
            """)
            self.sessions_layout.insertWidget(0, no_sessions_label)
            return
        
        logger.info(f"{len(session_files)} session(s) trouvée(s)")
        
        for session_file in session_files:
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                card = SessionCard(session_data, session_file, self)
                card.load_requested.connect(self._on_load_session)
                
                self.sessions_layout.insertWidget(
                    self.sessions_layout.count() - 1,
                    card
                )
            
            except Exception as e:
                logger.error(f"Erreur: {e}")
    
    def _filter_sessions(self, search_text: str):
        """Filtre les sessions"""
        search_text = search_text.lower()
        
        for i in range(self.sessions_layout.count() - 1):
            item = self.sessions_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if isinstance(card, SessionCard):
                    should_show = (
                        search_text in card.session_data.get('session_id', '').lower() or
                        search_text in card.session_data.get('metadata', {}).get('platform', '').lower() or
                        any(search_text in msg.get('content', '').lower() 
                            for msg in card.session_data.get('messages', []))
                    )
                    card.setVisible(should_show)
    
    def _on_load_session(self, session_file_path: str):
        """Émet le signal avec le chemin du fichier"""
        self.session_selected.emit(str(session_file_path))
        self.accept()


class SessionCard(QtWidgets.QWidget):
    """Carte compacte pour une session"""
    
    load_requested = pyqtSignal(str)  # Émet le chemin du fichier
    
    def __init__(self, session_data: dict, file_path: Path, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.file_path = file_path
        self._init_ui()
    
    def _init_ui(self):
        """Interface de la carte"""
        self.setStyleSheet("""
            SessionCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            SessionCard:hover {
                border: 1px solid #A23B2D;
                background-color: #fffbfa;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)
        
        # Ligne 1: ID + Plateforme + Date
        header_layout = QtWidgets.QHBoxLayout()
        
        session_id = self.session_data.get('session_id', 'Unknown')
        platform = self.session_data.get('metadata', {}).get('platform', 'N/A')
        created_at = self.session_data.get('created_at', 0)
        
        # Formater la date
        if created_at:
            date_str = datetime.fromtimestamp(created_at).strftime("%d/%m/%Y %H:%M")
        else:
            date_str = "Date inconnue"
        
        # ID Session
        id_label = QtWidgets.QLabel(session_id)
        id_label.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #333;
        """)
        header_layout.addWidget(id_label)
        
        header_layout.addStretch()
        
        # Plateforme
        platform_label = QtWidgets.QLabel(platform.upper())
        platform_label.setStyleSheet("""
            font-size: 11px;
            color: #666;
            background-color: #f0f0f0;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 500;
        """)
        header_layout.addWidget(platform_label)
        
        # Date
        date_label = QtWidgets.QLabel(date_str)
        date_label.setStyleSheet("""
            font-size: 11px;
            color: #888;
        """)
        header_layout.addWidget(date_label)
        
        layout.addLayout(header_layout)
        
        # Ligne 2: Statistiques
        stats_layout = QtWidgets.QHBoxLayout()
        
        messages = self.session_data.get('messages', [])
        total_messages = len(messages)
        
        # Compter les snippets
        total_snippets = sum(
            msg.get('metadata', {}).get('snippets_count', 0)
            for msg in messages
            if msg.get('role') == 'assistant'
        )
        
        stats_label = QtWidgets.QLabel(
            f"{total_messages} messages · {total_snippets} snippets"
        )
        stats_label.setStyleSheet("""
            font-size: 11px;
            color: #666;
        """)
        stats_layout.addWidget(stats_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Ligne 3: Aperçu du premier message utilisateur
        first_user_msg = next(
            (msg for msg in messages if msg.get('role') == 'user'),
            None
        )
        
        if first_user_msg:
            preview_text = first_user_msg.get('content', '')[:100]
            if len(first_user_msg.get('content', '')) > 100:
                preview_text += "..."
            
            preview_label = QtWidgets.QLabel(preview_text)
            preview_label.setWordWrap(True)
            preview_label.setStyleSheet("""
                font-size: 11px;
                color: #555;
                font-style: italic;
                background-color: #f9f9f9;
                padding: 8px 10px;
                border-radius: 4px;
                border-left: 3px solid #A23B2D;
            """)
            layout.addWidget(preview_label)
        
        # Ligne 4: Bouton de chargement
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.addStretch()
        
        # Bouton Charger
        load_button = QtWidgets.QPushButton("Charger")
        load_button.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35A4A;
            }
        """)
        load_button.clicked.connect(lambda: self.load_requested.emit(str(self.file_path)))
        actions_layout.addWidget(load_button)
        
        layout.addLayout(actions_layout)