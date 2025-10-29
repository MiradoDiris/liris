from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.Qsci import (
    QsciScintilla,
    QsciLexerPython,
    QsciLexerCPP,
    QsciLexerJavaScript,
    QsciLexerHTML,
)

import qtawesome as qta

from utils.logger import logger
from ui.localization.translator import tr


class SnippetCard(QtWidgets.QWidget):
    """Widget pour afficher un snippet de code avec métadonnées - style monochrome gris"""
    
    copy_requested = pyqtSignal(str)
    expand_requested = pyqtSignal(dict)
    ide_requested = pyqtSignal(dict)
    
    def __init__(self, snippet_data, parent=None):
        super().__init__(parent)
        self.snippet_data = snippet_data
        self._init_ui()
    
    def _get_action_icon_and_color(self, action):
        """Retourne l'icône selon l'action, couleur grise uniforme"""
        action_map = {
            'AJOUTER': ('fa5s.plus-circle', '#666666'),
            'MODIFIER': ('fa5s.edit', '#666666'),
            'REMPLACER': ('fa5s.sync-alt', '#666666'),
        }
        return action_map.get(action.upper(), ('fa5s.code', '#666666'))
    
    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Fond et bordures - design épuré
        self.setStyleSheet("""
            SnippetCard {
                background-color: #ffffff;
                border: none;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        
        # ===== CONTENEUR PRINCIPAL =====
        content_widget = QtWidgets.QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: none;
            }
            QWidget:hover {
                background-color: #fafafa;
            }
        """)
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)
        
        # ===== EN-TÊTE SIMPLIFIÉ =====
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)
        
        # Badge numéro (gardé)
        order_label = QtWidgets.QLabel(f"#{self.snippet_data.get('order', 0)}")
        order_label.setStyleSheet("""
            font-size: 11px;
            color: #666;
            padding: 3px 9px;
            background-color: #f0f0f0;
            border-radius: 10px;
            font-weight: 700;
        """)
        header_layout.addWidget(order_label)
        
        action = self.snippet_data.get('action', 'MODIFIER')
        icon_name, color = self._get_action_icon_and_color(action)
        
        action_icon = QtWidgets.QLabel()
        action_icon.setPixmap(qta.icon(icon_name, color=color).pixmap(18, 18))
        header_layout.addWidget(action_icon)
        
        action_label = QtWidgets.QLabel(action.capitalize())
        action_label.setStyleSheet(f"""
            font-weight: 700;
            font-size: 13px;
            color: {color};
        """)
        header_layout.addWidget(action_label)
        
        # Titre (sans "Snippet 1", "Snippet 2" - juste le vrai titre)
        title = self.snippet_data.get('title', 'Sans titre')
        # Enlever le préfixe "Snippet N: " s'il existe
        if title.lower().startswith('snippet') and ':' in title:
            title = title.split(':', 1)[1].strip()
        
        if title and title != 'Sans titre':
            separator = QtWidgets.QLabel("•")
            separator.setStyleSheet("color: #ccc; font-weight: bold; font-size: 12px;")
            header_layout.addWidget(separator)
            
            title_label = QtWidgets.QLabel(title)
            title_label.setWordWrap(True)
            title_label.setStyleSheet("""
                font-weight: 600;
                font-size: 13px;
                color: #333;
            """)
            header_layout.addWidget(title_label, 1)
        
        header_layout.addStretch()
        content_layout.addLayout(header_layout)
        
        # ===== MÉTADONNÉES MINIMALISTES =====
        meta_layout = QtWidgets.QVBoxLayout()
        meta_layout.setSpacing(4)
        
        file_layout = QtWidgets.QHBoxLayout()
        file_icon = QtWidgets.QLabel()
        file_icon.setPixmap(qta.icon('fa5s.file-code', color='#888').pixmap(12, 12))
        file_layout.addWidget(file_icon)
        
        file_path = self.snippet_data.get('file', 'Non spécifié')
        file_label = QtWidgets.QLabel(f"<span style='color: #666;'>Fichier:</span> <b>{file_path}</b>")
        file_label.setTextFormat(Qt.RichText)
        file_label.setStyleSheet("font-size: 11px; color: #333;")
        file_layout.addWidget(file_label, 1)
        file_layout.addStretch()
        meta_layout.addLayout(file_layout)
        
        target = self.snippet_data.get('target')
        if target:
            target_layout = QtWidgets.QHBoxLayout()
            target_icon = QtWidgets.QLabel()
            target_icon.setPixmap(qta.icon('fa5s.bullseye', color='#888').pixmap(12, 12))
            target_layout.addWidget(target_icon)
            
            target_label = QtWidgets.QLabel(f"<span style='color: #666;'>Cible:</span> <b>{target}</b>")
            target_label.setTextFormat(Qt.RichText)
            target_label.setStyleSheet("font-size: 11px; color: #333;")
            target_layout.addWidget(target_label, 1)
            target_layout.addStretch()
            meta_layout.addLayout(target_layout)
        
        content_layout.addLayout(meta_layout)
        
        # ===== DESCRIPTION =====
        description = self.snippet_data.get('description', '').strip()
        if description:
            desc_label = QtWidgets.QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("""
                font-size: 12px;
                color: #666;
                padding: 8px 0;
                line-height: 1.4;
            """)
            content_layout.addWidget(desc_label)
        
        # ===== BARRE D'ACTIONS =====
        actions_bar = QtWidgets.QWidget()
        actions_bar.setStyleSheet("""
            background-color: transparent;
            border: none;
        """)
        actions_layout = QtWidgets.QHBoxLayout(actions_bar)
        actions_layout.setContentsMargins(0, 8, 0, 0)
        actions_layout.setSpacing(6)
        
        # Bouton toggle
        self.toggle_button = QtWidgets.QPushButton()
        self.toggle_button.setIcon(qta.icon('fa5s.code', color='#666'))
        self.toggle_button.setText(" Code")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #555;
            }
            QPushButton:hover {
                background: #eeeeee;
                border-color: #ccc;
                color: #333;
            }
        """)
        self.toggle_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_button.clicked.connect(self._toggle_code)
        actions_layout.addWidget(self.toggle_button)
        
        actions_layout.addStretch()
        
        code_text = self.snippet_data.get('code', '')
        
        # Boutons d'action groupés
        button_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #ccc;
            }
        """
        
        # Bouton Copier
        copy_button = QtWidgets.QPushButton()
        copy_button.setIcon(qta.icon('fa5s.copy', color='#666'))
        copy_button.setToolTip("Copier le code")
        copy_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        copy_button.setStyleSheet(button_style)
        copy_button.setIconSize(QtCore.QSize(14, 14))
        copy_button.clicked.connect(lambda: self.copy_requested.emit(code_text))
        actions_layout.addWidget(copy_button)
    
        # Bouton Étendre
        expand_button = QtWidgets.QPushButton()
        expand_button.setIcon(qta.icon('fa5s.expand', color='#666'))
        expand_button.setToolTip("Ouvrir en plein écran")
        expand_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        expand_button.setStyleSheet(button_style)
        expand_button.setIconSize(QtCore.QSize(14, 14))
        expand_button.clicked.connect(lambda: self.expand_requested.emit(self.snippet_data))
        actions_layout.addWidget(expand_button)
    
        # Bouton IDE
        ide_button = QtWidgets.QPushButton()
        ide_button.setIcon(qta.icon('fa5s.code-branch', color='#4CAF50'))
        ide_button.setToolTip("Intégrer dans l'IDE")
        ide_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        ide_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background: #e8f5e9;
                border-color: #4CAF50;
            }
        """)
        ide_button.setIconSize(QtCore.QSize(14, 14))
        ide_button.clicked.connect(lambda: self.ide_requested.emit(self.snippet_data))
        actions_layout.addWidget(ide_button)
        
        content_layout.addWidget(actions_bar)
        
        # ===== ZONE DE CODE =====
        self.code_viewer = QsciScintilla()
        self.code_viewer.setUtf8(True)
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setVisible(False)
        self.code_viewer.setText(code_text)
        
        language = self.snippet_data.get('language', 'python')
        lexer = self._get_lexer(language)
        code_font = QtGui.QFont("Consolas", 10)
        if lexer:
            lexer.setDefaultFont(code_font)
            self.code_viewer.setLexer(lexer)
        
        self.code_viewer.setMarginsBackgroundColor(QtGui.QColor("#fafafa"))
        self.code_viewer.setMarginsForegroundColor(QtGui.QColor("#999"))
        self.code_viewer.setMarginLineNumbers(0, True)
        self.code_viewer.setMarginWidth(0, QtGui.QFontMetrics(code_font).width("000") + 8)
        
        # Style épuré pour l'éditeur
        self.code_viewer.setStyleSheet("""
            QsciScintilla {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        
        line_count = code_text.count('\n') + 1
        self.code_viewer.setMinimumHeight(min(line_count * 18 + 40, 250))
        self.code_viewer.setMaximumHeight(400)
        
        content_layout.addWidget(self.code_viewer)
        
        main_layout.addWidget(content_widget)
    
    def _toggle_code(self):
        is_visible = self.code_viewer.isVisible()
        self.code_viewer.setVisible(not is_visible)
        icon = 'fa5s.chevron-up' if not is_visible else 'fa5s.chevron-down'
        self.toggle_button.setIcon(qta.icon(icon, color='#666'))
        self.toggle_button.setText("  Masquer le code" if not is_visible else "  Afficher le code")
    
    def _get_lexer(self, language):
        lexers = {
            'python': QsciLexerPython,
            'cpp': QsciLexerCPP,
            'c++': QsciLexerCPP,
            'javascript': QsciLexerJavaScript,
            'js': QsciLexerJavaScript,
            'html': QsciLexerHTML
        }
        return lexers.get(language.lower(), QsciLexerPython)()  
