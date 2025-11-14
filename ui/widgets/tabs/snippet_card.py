from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta
import os
from pathlib import Path


class SnippetCard(QtWidgets.QWidget):
    """Widget compact sans scroll horizontal - Adaptatif selon la largeur disponible"""
    
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
        
        # Layout vertical pour empiler les éléments si nécessaire
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(8)
        
        # ===== LIGNE 1 : TITRE + ACTION + BOUTONS =====
        first_row = QtWidgets.QHBoxLayout()
        first_row.setSpacing(12)
        
        # Container titre + action
        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        
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
        
        # Label titre (avec ellipsis si trop long)
        snippet_title = f"{snippet_number}: {title}" if snippet_number else title
        title_label = QtWidgets.QLabel(snippet_title)
        title_label.setStyleSheet("""
            font-weight: 600;
            font-size: 12px;
            color: #1a1a1a;
        """)
        title_label.setWordWrap(False)
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # ✅ IMPORTANT : Activer l'ellipsis pour éviter le débordement
        title_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        title_label.setMaximumWidth(600)  # Largeur max raisonnable
        
        # Créer une version avec elide si trop long
        font_metrics = title_label.fontMetrics()
        elided_text = font_metrics.elidedText(snippet_title, Qt.ElideRight, 600)
        title_label.setText(elided_text)
        title_label.setToolTip(snippet_title)  # Tooltip pour voir le texte complet
        
        title_layout.addWidget(title_label)
        
        # Label action
        action_label = QtWidgets.QLabel(action_text)
        action_label.setStyleSheet("""
            font-size: 10px;
            color: #888;
            font-weight: 500;
        """)
        title_layout.addWidget(action_label)
        
        first_row.addWidget(title_container, 1)  # Stretch = 1
        first_row.addStretch()  # Push buttons à droite
        
        # ===== BOUTONS D'ACTION (toujours visibles) =====
        actions_container = QtWidgets.QWidget()
        actions_container.setStyleSheet("background: transparent; border: none;")
        actions_layout = QtWidgets.QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        
        code_text = self.snippet_data.get('code', '')
        
        # Bouton Copier
        copy_button = QtWidgets.QPushButton()
        copy_button.setIcon(qta.icon('fa5s.copy', color='#666'))
        copy_button.setToolTip("Copier le code")
        copy_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        copy_button.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #ccc;
            }
        """)
        copy_button.setIconSize(QtCore.QSize(14, 14))
        copy_button.clicked.connect(lambda: self.copy_requested.emit(code_text))
        actions_layout.addWidget(copy_button)
        
        # Bouton Étendre
        expand_button = QtWidgets.QPushButton()
        expand_button.setIcon(qta.icon('fa5s.expand-alt', color='#666'))
        expand_button.setToolTip("Voir le code complet")
        expand_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        expand_button.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #ccc;
            }
        """)
        expand_button.setIconSize(QtCore.QSize(14, 14))
        expand_button.clicked.connect(lambda: self.expand_requested.emit(self.snippet_data))
        actions_layout.addWidget(expand_button)
        
        # Bouton VS Code
        vscode_button = QtWidgets.QPushButton()
        vscode_button.setToolTip("Merger dans VS Code")
        vscode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        vscode_button.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #0078d4;
                border-radius: 4px;
                padding: 6px;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background: #e3f2fd;
                border-color: #0078d4;
            }
        """)
        
        # Charger l'icône SVG
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            svg_path = project_root / "ui" / "resources" / "icons" / "vscode.svg"
            
            if svg_path.exists():
                icon = QtGui.QIcon(str(svg_path))
                vscode_button.setIcon(icon)
                vscode_button.setIconSize(QtCore.QSize(16, 16))
            else:
                vscode_button.setIcon(qta.icon('fa5b.microsoft', color='#0078d4'))
                vscode_button.setIconSize(QtCore.QSize(14, 14))
        except:
            vscode_button.setIcon(qta.icon('fa5b.microsoft', color='#0078d4'))
            vscode_button.setIconSize(QtCore.QSize(14, 14))
        
        vscode_button.clicked.connect(lambda: self.vscode_requested.emit(self.snippet_data))
        actions_layout.addWidget(vscode_button)
        
        first_row.addWidget(actions_container)
        content_layout.addLayout(first_row)
        
        # ===== LIGNE 2 : FICHIER + CLASSE/FONCTION (compacts avec ellipsis) =====
        second_row = QtWidgets.QHBoxLayout()
        second_row.setSpacing(12)
        
        # Fichier
        file_name = self.snippet_data.get('file', '')
        if file_name:
            file_container = QtWidgets.QHBoxLayout()
            file_container.setSpacing(4)
            
            file_icon = QtWidgets.QLabel("📄")
            file_icon.setStyleSheet("font-size: 10px;")
            file_container.addWidget(file_icon)
            
            file_label = QtWidgets.QLabel(file_name)
            file_label.setStyleSheet("""
                font-size: 10px;
                color: #666;
            """)
            file_label.setWordWrap(False)
            file_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            
            # Ellipsis si trop long
            font_metrics = file_label.fontMetrics()
            elided_file = font_metrics.elidedText(file_name, Qt.ElideMiddle, 250)
            file_label.setText(elided_file)
            file_label.setToolTip(file_name)
            
            file_container.addWidget(file_label, 1)
            second_row.addLayout(file_container, 1)
        
        # Classe/Fonction
        class_func = self.snippet_data.get('class_function', '')
        if class_func:
            class_container = QtWidgets.QHBoxLayout()
            class_container.setSpacing(4)
            
            class_icon = QtWidgets.QLabel("⚙️")
            class_icon.setStyleSheet("font-size: 10px;")
            class_container.addWidget(class_icon)
            
            class_label = QtWidgets.QLabel(class_func)
            class_label.setStyleSheet("""
                font-size: 10px;
                color: #666;
            """)
            class_label.setWordWrap(False)
            class_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            
            # Ellipsis si trop long
            font_metrics = class_label.fontMetrics()
            elided_class = font_metrics.elidedText(class_func, Qt.ElideRight, 250)
            class_label.setText(elided_class)
            class_label.setToolTip(class_func)
            
            class_container.addWidget(class_label, 1)
            second_row.addLayout(class_container, 1)
        
        if file_name or class_func:
            content_layout.addLayout(second_row)
        
        main_layout.addWidget(content_widget)
    
    def resizeEvent(self, event):
        """Ajuste le contenu lors du redimensionnement"""
        super().resizeEvent(event)
        # Recalculer les ellipsis si nécessaire
        self._update_ellipsis()
    
    def _update_ellipsis(self):
        """Met à jour les ellipsis en fonction de la largeur disponible"""
        width = self.width()
        
        # Trouver les labels à ajuster
        title_label = self.findChild(QtWidgets.QLabel, "title_label")
        if title_label:
            available_width = max(200, width - 200)  # Garder de l'espace pour les boutons
            font_metrics = title_label.fontMetrics()
            original_text = self.snippet_data.get('title', '')
            elided = font_metrics.elidedText(original_text, Qt.ElideRight, available_width)
            title_label.setText(elided)