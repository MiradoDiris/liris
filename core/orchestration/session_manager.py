from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta
import re
import os
from pathlib import Path


class SnippetCard(QtWidgets.QWidget):
    """Widget compact avec accordéon pour l'historique conversationnel"""
    
    copy_requested = pyqtSignal(str)
    expand_requested = pyqtSignal(dict)
    vscode_requested = pyqtSignal(dict)
    
    def __init__(self, snippet_data, parent=None):
        super().__init__(parent)
        self.snippet_data = snippet_data
        self.is_expanded = False
        
        # 🧪 DEBUG: Afficher les infos
        print("\n" + "="*60)
        print("🔍 DEBUG SnippetCard")
        print("="*60)
        print(f"📦 Titre: {snippet_data.get('title', 'N/A')}")
        print(f"📊 session_info présent: {'session_info' in snippet_data}")
        if 'session_info' in snippet_data:
            session_info = snippet_data['session_info']
            print(f"   - session_id: {session_info.get('session_id', 'N/A')}")
            print(f"   - total_messages: {session_info.get('total_messages', 0)}")
            print(f"   - has_context: {session_info.get('has_context', False)}")
        print(f"✅ _has_conversation_history(): {self._has_conversation_history()}")
        print("="*60 + "\n")
        
        self._init_ui()
    
    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Fond et bordures
        self.setStyleSheet("""
            SnippetCard {
                background-color: #ffffff;
                border: none;
                border-bottom: 1px solid #e8e8e8;
            }
        """)
        
        # ===== CONTENEUR PRINCIPAL =====
        content_widget = QtWidgets.QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: none;
            }
        """)
        
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(8)
        
        # ===== LIGNE 1 : ICÔNE HISTORIQUE + TITRE + ACTION =====
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)
        
        # ✨ ICÔNE HISTORIQUE (à gauche du titre)
        # 🧪 DEBUG: FORCER L'AFFICHAGE pour tester
        has_history = self._has_conversation_history()
        print(f"🎯 Création icône historique: has_history={has_history}")
        
        # TEMPORAIRE: Toujours afficher l'icône pour tester
        if True:  # Remplacer par: if has_history:
            print("   ✅ Création du bouton accordéon...")
            self.accordion_button = QtWidgets.QPushButton("☰")  # TEXTE au lieu d'icône pour test
            # Commenté temporairement: self.accordion_button.setIcon(qta.icon('fa5s.bars', color='#666'))
            self.accordion_button.setToolTip(f"Afficher l'historique conversationnel (DEBUG: has_history={has_history})")
            self.accordion_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            self.accordion_button.setStyleSheet("""
                QPushButton {
                    background: #f0f7ff;
                    border: 2px solid #2563eb;
                    border-radius: 3px;
                    padding: 4px 8px;
                    min-width: 30px;
                    max-width: 30px;
                    min-height: 30px;
                    max-height: 30px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #dbeafe;
                    border-color: #1d4ed8;
                }
            """)
            # Commenté temporairement: self.accordion_button.setIconSize(QtCore.QSize(12, 12))
            self.accordion_button.clicked.connect(self._toggle_history)
            
            # FORCER la visibilité
            self.accordion_button.setVisible(True)
            self.accordion_button.show()
            self.accordion_button.raise_()
            
            title_row.addWidget(self.accordion_button)
            print(f"   ✅ Bouton accordéon ajouté au layout")
            print(f"   📏 Taille bouton: {self.accordion_button.sizeHint()}")
            print(f"   👁️  Visible: {self.accordion_button.isVisible()}")
        else:
            print(f"   ❌ Pas d'historique, bouton non créé")
        
        # Container vertical pour titre + action
        title_info_layout = QtWidgets.QVBoxLayout()
        title_info_layout.setSpacing(2)
        
        # Extraire le titre (supprimer le numéro de snippet)
        title = self.snippet_data.get('title', 'Sans titre')
        action = self.snippet_data.get('action', 'MODIFIER').upper()
        
        # Supprimer TOUS les patterns de numéro de snippet possibles
        # Pattern 1: "Snippet 1:" ou "snippet 1:"
        title = re.sub(r'^snippet\s*\d+\s*:\s*', '', title, flags=re.IGNORECASE)
        
        # Pattern 2: Juste le numéro au début "1:" ou "1 -"
        title = re.sub(r'^\d+\s*[:-]\s*', '', title)
        
        # Pattern 3: Format "[1]" au début
        title = re.sub(r'^\[\d+\]\s*', '', title)
        
        # Nettoyer les espaces
        title = title.strip()
        
        # Formater l'action
        action_text = "[A remplacer]" if action in ["MODIFIER", "REPLACE", "REMPLACER"] else "[A ajouter]"
        
        # Label titre avec ellipsis
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("""
            font-weight: 600;
            font-size: 12px;
            color: #1a1a1a;
        """)
        title_label.setWordWrap(False)
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        
        # Ellipsis automatique
        font_metrics = title_label.fontMetrics()
        max_width = self.parent().width() - 150 if self.parent() else 400
        elided_text = font_metrics.elidedText(title, Qt.ElideRight, max_width)
        title_label.setText(elided_text)
        title_label.setToolTip(title)
        
        title_info_layout.addWidget(title_label)
        
        # Label action
        action_label = QtWidgets.QLabel(action_text)
        action_label.setStyleSheet("""
            font-size: 10px;
            color: #888;
            font-weight: 500;
        """)
        title_info_layout.addWidget(action_label)
        
        # Ajouter le container titre/action
        title_row.addLayout(title_info_layout, 1)
        title_row.addStretch()
        
        content_layout.addLayout(title_row)
        
        # ===== LIGNE 2 : FICHIER + CLASSE/FONCTION + BOUTONS (même niveau) =====
        info_row = QtWidgets.QHBoxLayout()
        info_row.setSpacing(8)
        
        # Container pour fichier + classe (avec ellipsis)
        info_container = QtWidgets.QHBoxLayout()
        info_container.setSpacing(12)
        
        # Fichier
        file_name = self.snippet_data.get('file', '')
        if file_name:
            file_container = QtWidgets.QHBoxLayout()
            file_container.setSpacing(4)
            
            file_icon = QtWidgets.QLabel("📄")
            file_icon.setStyleSheet("font-size: 10px;")
            file_icon.setFixedWidth(12)
            file_container.addWidget(file_icon)
            
            file_label = QtWidgets.QLabel(file_name)
            file_label.setStyleSheet("""
                font-size: 10px;
                color: #666;
            """)
            file_label.setWordWrap(False)
            file_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            
            # Ellipsis
            font_metrics = file_label.fontMetrics()
            elided_file = font_metrics.elidedText(file_name, Qt.ElideMiddle, 200)
            file_label.setText(elided_file)
            file_label.setToolTip(file_name)
            
            file_container.addWidget(file_label)
            info_container.addLayout(file_container)
        
        # Classe/Fonction
        class_func = self.snippet_data.get('class_function', '')
        if class_func:
            class_container = QtWidgets.QHBoxLayout()
            class_container.setSpacing(4)
            
            class_icon = QtWidgets.QLabel("⚙️")
            class_icon.setStyleSheet("font-size: 10px;")
            class_icon.setFixedWidth(12)
            class_container.addWidget(class_icon)
            
            class_label = QtWidgets.QLabel(class_func)
            class_label.setStyleSheet("""
                font-size: 10px;
                color: #666;
            """)
            class_label.setWordWrap(False)
            class_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            
            # Ellipsis
            font_metrics = class_label.fontMetrics()
            elided_class = font_metrics.elidedText(class_func, Qt.ElideRight, 200)
            class_label.setText(elided_class)
            class_label.setToolTip(class_func)
            
            class_container.addWidget(class_label)
            info_container.addLayout(class_container)
        
        info_row.addLayout(info_container, 1)
        info_row.addStretch()
        
        # ===== BOUTONS MINIATURES =====
        actions_container = QtWidgets.QWidget()
        actions_container.setStyleSheet("background: transparent; border: none;")
        actions_layout = QtWidgets.QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)
        
        code_text = self.snippet_data.get('code', '')
        
        # Style pour mini-boutons
        mini_button_style = """
            QPushButton {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 4px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #ccc;
            }
        """
        
        vscode_button_style = """
            QPushButton {
                background: white;
                border: 1px solid #0078d4;
                border-radius: 3px;
                padding: 4px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QPushButton:hover {
                background: #e3f2fd;
                border-color: #0078d4;
            }
        """
        
        # Bouton Copier
        copy_button = QtWidgets.QPushButton()
        copy_button.setIcon(qta.icon('fa5s.copy', color='#666'))
        copy_button.setToolTip("Copier le code")
        copy_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        copy_button.setStyleSheet(mini_button_style)
        copy_button.setIconSize(QtCore.QSize(12, 12))
        copy_button.clicked.connect(lambda: self.copy_requested.emit(code_text))
        actions_layout.addWidget(copy_button)
        
        # Bouton Étendre
        expand_button = QtWidgets.QPushButton()
        expand_button.setIcon(qta.icon('fa5s.expand-alt', color='#666'))
        expand_button.setToolTip("Voir le code complet")
        expand_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        expand_button.setStyleSheet(mini_button_style)
        expand_button.setIconSize(QtCore.QSize(12, 12))
        expand_button.clicked.connect(lambda: self.expand_requested.emit(self.snippet_data))
        actions_layout.addWidget(expand_button)
        
        # Bouton VS Code
        vscode_button = QtWidgets.QPushButton()
        vscode_button.setToolTip("Merger dans VS Code")
        vscode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        vscode_button.setStyleSheet(vscode_button_style)
        
        # Charger l'icône SVG
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            svg_path = project_root / "ui" / "resources" / "icons" / "vscode.svg"
            
            if svg_path.exists():
                icon = QtGui.QIcon(str(svg_path))
                vscode_button.setIcon(icon)
                vscode_button.setIconSize(QtCore.QSize(14, 14))
            else:
                vscode_button.setIcon(qta.icon('fa5b.microsoft', color='#0078d4'))
                vscode_button.setIconSize(QtCore.QSize(12, 12))
        except:
            vscode_button.setIcon(qta.icon('fa5b.microsoft', color='#0078d4'))
            vscode_button.setIconSize(QtCore.QSize(12, 12))
        
        vscode_button.clicked.connect(lambda: self.vscode_requested.emit(self.snippet_data))
        actions_layout.addWidget(vscode_button)
        
        info_row.addWidget(actions_container)
        
        content_layout.addLayout(info_row)
        
        # ===== NOUVEAU: PANNEAU HISTORIQUE (masqué par défaut) =====
        self.history_panel = QtWidgets.QWidget()
        self.history_panel.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        self.history_panel.setVisible(False)
        
        history_layout = QtWidgets.QVBoxLayout(self.history_panel)
        history_layout.setContentsMargins(12, 8, 12, 8)
        history_layout.setSpacing(6)
        
        # Titre de la section
        history_title = QtWidgets.QLabel("💬 Historique conversationnel")
        history_title.setStyleSheet("""
            font-weight: 600;
            font-size: 11px;
            color: #2563eb;
            margin-bottom: 4px;
        """)
        history_layout.addWidget(history_title)
        
        # Afficher l'historique
        self._build_history_content(history_layout)
        
        content_layout.addWidget(self.history_panel)
        
        main_layout.addWidget(content_widget)
        
        # ===== CONFIGURATION =====
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    
    def _has_conversation_history(self) -> bool:
        """Vérifie si le snippet contient un historique conversationnel"""
        session_info = self.snippet_data.get('session_info', {})
        has_context = session_info.get('has_context', False)
        total_messages = session_info.get('total_messages', 0)
        
        result = has_context and total_messages > 1
        
        # 🧪 DEBUG
        print(f"   📊 _has_conversation_history():")
        print(f"      - session_info: {bool(session_info)}")
        print(f"      - has_context: {has_context}")
        print(f"      - total_messages: {total_messages}")
        print(f"      - result: {result}")
        
        return result
    
    def _toggle_history(self):
        """Toggle l'affichage de l'historique"""
        self.is_expanded = not self.is_expanded
        self.history_panel.setVisible(self.is_expanded)
        
        # Changer l'icône et le style
        if hasattr(self, 'accordion_button'):
            if self.is_expanded:
                self.accordion_button.setIcon(qta.icon('fa5s.times', color='#dc2626'))
                self.accordion_button.setToolTip("Masquer l'historique conversationnel")
                self.accordion_button.setStyleSheet("""
                    QPushButton {
                        background: #fee2e2;
                        border: 1px solid #fca5a5;
                        border-radius: 3px;
                        padding: 4px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                    }
                    QPushButton:hover {
                        background: #fecaca;
                        border-color: #f87171;
                    }
                """)
            else:
                self.accordion_button.setIcon(qta.icon('fa5s.bars', color='#666'))
                self.accordion_button.setToolTip("Afficher l'historique conversationnel")
                self.accordion_button.setStyleSheet("""
                    QPushButton {
                        background: #f0f7ff;
                        border: 1px solid #b3d9ff;
                        border-radius: 3px;
                        padding: 4px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                    }
                    QPushButton:hover {
                        background: #e0f0ff;
                        border-color: #66b3ff;
                    }
                """)
        
        # Ajuster la taille du widget
        self.adjustSize()
        self.updateGeometry()
    
    def _build_history_content(self, layout: QtWidgets.QVBoxLayout):
        """Construit le contenu de l'historique"""
        session_info = self.snippet_data.get('session_info', {})
        
        if not session_info:
            no_history_label = QtWidgets.QLabel("Aucun historique disponible")
            no_history_label.setStyleSheet("color: #999; font-size: 10px; font-style: italic;")
            layout.addWidget(no_history_label)
            return
        
        # Informations de session
        info_text = []
        
        session_id = session_info.get('session_id', 'N/A')
        total_messages = session_info.get('total_messages', 0)
        conversation_turns = session_info.get('conversation_turns', 0)
        
        info_text.append(f"🆔 Session: {session_id[:12]}...")
        info_text.append(f"📊 Messages: {total_messages} ({conversation_turns} tours)")
        
        info_label = QtWidgets.QLabel(" | ".join(info_text))
        info_label.setStyleSheet("""
            font-size: 10px;
            color: #666;
            padding: 4px 0;
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Récupérer l'historique complet si disponible
        conversation_history = self.snippet_data.get('conversation_history', [])
        
        if conversation_history and len(conversation_history) > 0:
            # Ligne de séparation
            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.HLine)
            separator.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
            layout.addWidget(separator)
            
            # Scroll area pour l'historique
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMaximumHeight(200)
            scroll_area.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
            """)
            
            scroll_content = QtWidgets.QWidget()
            scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
            scroll_layout.setContentsMargins(0, 4, 0, 4)
            scroll_layout.setSpacing(8)
            
            # Afficher les messages (limiter à 5 derniers)
            messages_to_show = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            
            for msg in messages_to_show:
                msg_widget = self._create_message_widget(msg)
                scroll_layout.addWidget(msg_widget)
            
            scroll_layout.addStretch()
            scroll_area.setWidget(scroll_content)
            layout.addWidget(scroll_area)
        else:
            hint_label = QtWidgets.QLabel("💡 L'historique complet est disponible dans le gestionnaire de sessions")
            hint_label.setStyleSheet("""
                font-size: 10px;
                color: #666;
                font-style: italic;
                padding: 4px;
            """)
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
    
    def _create_message_widget(self, message: dict) -> QtWidgets.QWidget:
        """Crée un widget pour un message de l'historique"""
        msg_widget = QtWidgets.QWidget()
        msg_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e8e8e8;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        
        msg_layout = QtWidgets.QVBoxLayout(msg_widget)
        msg_layout.setContentsMargins(6, 6, 6, 6)
        msg_layout.setSpacing(4)
        
        # Rôle
        role = message.get('role', 'unknown')
        role_icon = "👤" if role == 'user' else "🤖"
        role_label = QtWidgets.QLabel(f"{role_icon} {role.upper()}")
        role_label.setStyleSheet("""
            font-weight: 600;
            font-size: 10px;
            color: #2563eb;
        """)
        msg_layout.addWidget(role_label)
        
        # Contenu (tronqué)
        content = message.get('content', '')
        content_preview = content[:150] + "..." if len(content) > 150 else content
        
        content_label = QtWidgets.QLabel(content_preview)
        content_label.setStyleSheet("""
            font-size: 10px;
            color: #333;
            padding: 2px;
        """)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg_layout.addWidget(content_label)
        
        return msg_widget
    
    def resizeEvent(self, event):
        """Ajuste le contenu lors du redimensionnement"""
        super().resizeEvent(event)
        self._update_ellipsis()
    
    def _update_ellipsis(self):
        """Met à jour les ellipsis en fonction de la largeur disponible"""
        width = self.width()
        
        for label in self.findChildren(QtWidgets.QLabel):
            if label.toolTip():
                original_text = label.toolTip()
                font_metrics = label.fontMetrics()
                available_width = max(100, width // 3)
                
                elided = font_metrics.elidedText(original_text, Qt.ElideMiddle, available_width)
                label.setText(elided)