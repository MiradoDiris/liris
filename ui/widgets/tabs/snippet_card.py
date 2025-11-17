from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta
import os
from pathlib import Path


class SnippetCard(QtWidgets.QWidget):
    """Widget compact sans scroll horizontal - Layout optimisé"""
    
    copy_requested = pyqtSignal(str)
    expand_requested = pyqtSignal(dict)
    vscode_requested = pyqtSignal(dict)
    
    def __init__(self, snippet_data, parent=None):
        super().__init__(parent)
        self.snippet_data = snippet_data
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
        
        # ===== LIGNE 1 : TITRE + ACTION =====
        title_row = QtWidgets.QVBoxLayout()
        title_row.setSpacing(2)
        
        # Extraire le titre
        title = self.snippet_data.get('title', 'Sans titre')
        action = self.snippet_data.get('action', 'MODIFIER').upper()
        
        # Extraire le numéro si présent
        snippet_number = ""
        if title.lower().startswith('snippet') and ':' in title:
            parts = title.split(':', 1)
            snippet_number = parts[0].strip()
            title = parts[1].strip()
        
        # Formater l'action
        action_text = "[A remplacer]" if action in ["MODIFIER", "REPLACE", "REMPLACER"] else "[A ajouter]"
        
        # Label titre avec ellipsis
        snippet_title = f"{snippet_number}: {title}" if snippet_number else title
        title_label = QtWidgets.QLabel(snippet_title)
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
        max_width = self.parent().width() - 100 if self.parent() else 500
        elided_text = font_metrics.elidedText(snippet_title, Qt.ElideRight, max_width)
        title_label.setText(elided_text)
        title_label.setToolTip(snippet_title)
        
        title_row.addWidget(title_label)
        
        # Label action
        action_label = QtWidgets.QLabel(action_text)
        action_label.setStyleSheet("""
            font-size: 10px;
            color: #888;
            font-weight: 500;
        """)
        title_row.addWidget(action_label)
        
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
        
        info_row.addLayout(info_container, 1)  # Stretch pour prendre l'espace disponible
        info_row.addStretch()  # Push les boutons à droite
        
        # ===== BOUTONS MINIATURES (même niveau que les paths) =====
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
        
        main_layout.addWidget(content_widget)
        
        # ===== CONFIGURATION IMPORTANTE =====
        # Empêcher le scroll horizontal
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    
    def resizeEvent(self, event):
        """Ajuste le contenu lors du redimensionnement"""
        super().resizeEvent(event)
        self._update_ellipsis()
    
    def _update_ellipsis(self):
        """Met à jour les ellipsis en fonction de la largeur disponible"""
        width = self.width()
        
        # Ajuster les textes trop longs
        for label in self.findChildren(QtWidgets.QLabel):
            if label.toolTip():  # Seulement les labels avec tooltip (texte complet)
                original_text = label.toolTip()
                font_metrics = label.fontMetrics()
                available_width = max(100, width // 3)  # Largeur adaptative
                
                elided = font_metrics.elidedText(original_text, Qt.ElideMiddle, available_width)
                label.setText(elided)