import pyperclip
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt
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


class CodePopupDialog(QtWidgets.QDialog):
    """Popup professionnelle pour afficher le code"""
    
    def __init__(self, snippet_data, parent=None):
        super().__init__(parent)
        self.snippet_data = snippet_data
        self.setWindowTitle(snippet_data.get('title', 'Code'))
        self.setMinimumSize(900, 600)
        self._init_ui()
        
    def _get_action_label(self, action):
        """Retourne le texte descriptif selon l'action"""
        action_map = {
            'AJOUTER': 'Code à ajouter',
            'MODIFIER': 'Code à modifier',
            'REMPLACER': 'Code à remplacer'
        }
        return action_map.get(action, 'Code')
        
    def _init_ui(self):
        """Initialise l'interface de la popup"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ===== EN-TÊTE =====
        header_container = QtWidgets.QWidget()
        header_container.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 12px;
        """)
        header_layout = QtWidgets.QVBoxLayout(header_container)
        header_layout.setSpacing(8)
        
        # Titre
        title_label = QtWidgets.QLabel(self.snippet_data.get('title', 'Sans titre'))
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #212529;
        """)
        header_layout.addWidget(title_label)
        
        # Métadonnées (fichier, action, langage)
        meta_layout = QtWidgets.QHBoxLayout()
        meta_layout.setSpacing(16)
        
        # Fichier
        file_path = self.snippet_data.get('file', 'Non spécifié')
        file_label = QtWidgets.QLabel(f"📄 {file_path}")
        file_label.setStyleSheet("font-size: 12px; color: #6c757d;")
        meta_layout.addWidget(file_label)
        
        # Séparateur
        sep1 = QtWidgets.QLabel("•")
        sep1.setStyleSheet("color: #dee2e6; font-size: 12px;")
        meta_layout.addWidget(sep1)
        
        # Action (sans style de bouton, juste du texte informatif)
        action = self.snippet_data.get('action', 'MODIFIER')
        action_text = self._get_action_label(action)
        action_label = QtWidgets.QLabel(action_text)
        action_label.setStyleSheet("font-size: 12px; color: #495057; font-weight: 500;")
        meta_layout.addWidget(action_label)
        
        # Séparateur
        sep2 = QtWidgets.QLabel("•")
        sep2.setStyleSheet("color: #dee2e6; font-size: 12px;")
        meta_layout.addWidget(sep2)
        
        # Langage
        language = self.snippet_data.get('language', 'python')
        lang_label = QtWidgets.QLabel(language.upper())
        lang_label.setStyleSheet("""
            font-size: 11px;
            color: #6c757d;
            background-color: #e9ecef;
            padding: 2px 8px;
            border-radius: 3px;
        """)
        meta_layout.addWidget(lang_label)
        
        # Cible (si présente)
        target = self.snippet_data.get('target')
        if target:
            sep3 = QtWidgets.QLabel("•")
            sep3.setStyleSheet("color: #dee2e6; font-size: 12px;")
            meta_layout.addWidget(sep3)
            
            target_label = QtWidgets.QLabel(f"🎯 {target}")
            target_label.setStyleSheet("font-size: 12px; color: #6c757d;")
            meta_layout.addWidget(target_label)
        
        meta_layout.addStretch()
        header_layout.addLayout(meta_layout)
        
        layout.addWidget(header_container)
        
        # ===== DESCRIPTION =====
        description = self.snippet_data.get('description', '').strip()
        if description:
            desc_container = QtWidgets.QWidget()
            desc_container.setStyleSheet("""
                background-color: #fff8e1;
                border-left: 3px solid #ffc107;
                border-radius: 3px;
                padding: 10px 12px;
            """)
            desc_layout = QtWidgets.QHBoxLayout(desc_container)
            desc_layout.setSpacing(8)
            desc_layout.setContentsMargins(0, 0, 0, 0)
            
            desc_label = QtWidgets.QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("""
                font-size: 12px;
                color: #5f4c00;
                line-height: 1.5;
            """)
            desc_layout.addWidget(desc_label)
            
            layout.addWidget(desc_container)
        
        # ===== ZONE DE CODE =====
        self.code_viewer = QsciScintilla()
        self.code_viewer.setUtf8(True)
        self.code_viewer.setReadOnly(True)
        
        code_text = self.snippet_data.get('code', '')
        self.code_viewer.setText(code_text)
        
        # Configuration du lexer
        language = self.snippet_data.get('language', 'python')
        lexer = self._get_lexer(language)
        code_font = QtGui.QFont("Consolas", 10)
        
        if lexer:
            lexer.setDefaultFont(code_font)
            self.code_viewer.setLexer(lexer)
        
        # Marges et numéros de ligne
        fontmetrics = QtGui.QFontMetrics(code_font)
        self.code_viewer.setMarginWidth(0, fontmetrics.width("0000") + 6)
        self.code_viewer.setMarginLineNumbers(0, True)
        self.code_viewer.setMarginsBackgroundColor(QtGui.QColor("#f8f9fa"))
        self.code_viewer.setMarginsForegroundColor(QtGui.QColor("#6c757d"))
        
        # Bordure subtile
        self.code_viewer.setStyleSheet("""
            QsciScintilla {
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        
        layout.addWidget(self.code_viewer)
        
        # ===== BOUTONS =====
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        
        copy_button = QtWidgets.QPushButton("Copier le code")
        copy_button.setIcon(qta.icon('fa5s.copy', color='#495057'))
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #495057;
                border: 1px solid #ced4da;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        copy_button.clicked.connect(lambda: self._copy_code(code_text))
        buttons_layout.addWidget(copy_button)
        
        close_button = QtWidgets.QPushButton("Fermer")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #4e555b;
            }
        """)
        close_button.clicked.connect(self.close)
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        
        # Style général
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
        """)
    
    def _get_lexer(self, language):
        """Retourne le lexer approprié"""
        lexers = {
            'python': QsciLexerPython,
            'cpp': QsciLexerCPP,
            'c++': QsciLexerCPP,
            'javascript': QsciLexerJavaScript,
            'js': QsciLexerJavaScript,
            'html': QsciLexerHTML
        }
        lexer_class = lexers.get(language.lower(), QsciLexerPython)
        return lexer_class()
    
    def _copy_code(self, text):
        """Copie le code dans le presse-papier"""
        try:
            pyperclip.copy(text)
            QtWidgets.QMessageBox.information(
                self,
                "Copié",
                "Le code a été copié dans le presse-papier !"
            )
        except Exception as e:
            logger.error(f"Erreur lors de la copie: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de copier: {str(e)}"
            )   