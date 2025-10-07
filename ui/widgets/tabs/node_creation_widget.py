#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/node_creation_widget.py
Widget amélioré pour la création de nœuds avec navigation type système de fichiers
"""

import os
import uuid
import time
import pyperclip
import json
import traceback
from datetime import datetime

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QPushButton, QHBoxLayout, QInputDialog, QMessageBox, 
                             QDialog, QFormLayout, QLineEdit, QTextEdit, 
                             QDialogButtonBox, QVBoxLayout, QPlainTextEdit)

from utils.selector_generator import UniversalSelectorGenerator
from utils.logger import logger
from utils.dgraph_connector import LirisDgraphConnector


# Palette de couleurs sans bleu (blanc et noir)
class ColorPalette:
    PRIMARY = "#2c3e50"      # Noir doux
    SECONDARY = "#34495e"    # Gris anthracite
    ACCENT = "#555555"       # Gris moyen
    SUCCESS = "#27ae60"      # Vert
    WARNING = "#f39c12"      # Orange
    DANGER = "#e74c3c"       # Rouge
    LIGHT = "#ecf0f1"        # Gris très clair
    LIGHTER = "#f8f9fa"      # Presque blanc
    BORDER = "#dfe6e9"       # Bordure gris clair
    TEXT = "#2c3e50"         # Texte principal
    TEXT_LIGHT = "#7f8c8d"   # Texte secondaire
    BACKGROUND = "#ffffff"   # Fond blanc
    DARK = "#1a1a1a"         # Noir pour console
    SELECTED = "#d5dbdb"     # Gris clair pour sélection
    
    # Couleurs pour les labels/tags
    TAG_COLORS = [
        {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#66bb6a"},  # Vert
        {"bg": "#fce4ec", "text": "#c2185b", "border": "#f06292"},  # Rose
        {"bg": "#e3f2fd", "text": "#1565c0", "border": "#42a5f5"},  # Bleu
        {"bg": "#fff3e0", "text": "#e65100", "border": "#ff9800"},  # Orange
        {"bg": "#f3e5f5", "text": "#6a1b9a", "border": "#ba68c8"},  # Violet
        {"bg": "#e0f2f1", "text": "#00695c", "border": "#26a69a"},  # Cyan
        {"bg": "#fff9c4", "text": "#f57f17", "border": "#fdd835"},  # Jaune
        {"bg": "#d7ccc8", "text": "#4e342e", "border": "#8d6e63"},  # Marron
    ]


class AddEditItemDialog(QDialog):
    """
    Dialogue générique pour ajouter/éditer un item avec nom et description.
    """
    def __init__(self, title, current_name="", current_description="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 200)

        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Nom de l'item...")
        self.name_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ColorPalette.BACKGROUND};
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {ColorPalette.PRIMARY};
            }}
        """)

        self.description_edit = QTextEdit(current_description)
        self.description_edit.setPlaceholderText("Description de l'item...")
        self.description_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ColorPalette.BACKGROUND};
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 2px solid {ColorPalette.PRIMARY};
            }}
        """)
        self.description_edit.setMaximumHeight(100)

        layout = QFormLayout(self)
        layout.addRow("Nom:", self.name_edit)
        layout.addRow("Description:", self.description_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip()
        }


class CodeEditDialog(QDialog):
    """
    Dialogue pour éditer le contenu code d'un fichier (cluster ou label).
    """
    def __init__(self, title, current_code="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        # Utiliser QPlainTextEdit pour une meilleure préservation de la structure de code
        self.code_edit = QPlainTextEdit(current_code)
        self.code_edit.setPlaceholderText("Contenu du fichier...")
        self.code_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {ColorPalette.BACKGROUND};
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }}
            QPlainTextEdit:focus {{
                border: 2px solid {ColorPalette.PRIMARY};
            }}
        """)
        # Configuration pour préserver la structure (indentation, retours à la ligne, tabs)
        self.code_edit.setLineWrapMode(QPlainTextEdit.NoWrap)  # Pas de retour automatique à la ligne
        self.code_edit.setTabStopWidth(4 * self.code_edit.fontMetrics().width(' '))  # Largeur de tabulation (4 espaces)
        # Sauvegarder l'événement original et redéfinir pour gérer Tab
        self.original_key_press = self.code_edit.keyPressEvent
        self.code_edit.keyPressEvent = self._handle_key_press

        layout.addWidget(self.code_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _handle_key_press(self, event):
        """Gère la touche Tab pour insérer une tabulation au lieu de changer de focus."""
        if event.key() == Qt.Key_Tab:
            cursor = self.code_edit.textCursor()
            cursor.insertText('\t')
            event.accept()
        else:
            self.original_key_press(event)

    def get_code(self):
        return self.code_edit.toPlainText()  # Préserve tabs, newlines, espaces, etc.


class TagWidget(QtWidgets.QWidget):
    """Widget pour afficher un tag/label avec bouton de fermeture"""
    
    removed = pyqtSignal(object)  # Signal émis quand le tag est retiré
    
    def __init__(self, text, color_scheme=None, removable=True, parent=None):
        super().__init__(parent)
        self.text = text
        self.removable = removable
        
        # Choisir un schéma de couleur
        if color_scheme is None:
            color_scheme = ColorPalette.TAG_COLORS[hash(text) % len(ColorPalette.TAG_COLORS)]
        self.color_scheme = color_scheme
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(6)
        
        # Label du texte
        self.label = QtWidgets.QLabel(self.text)
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {self.color_scheme['text']};
                font-size: 12px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.label)
        
        # Bouton de fermeture (si removable)
        if self.removable:
            self.close_btn = QtWidgets.QPushButton("×")
            self.close_btn.setFixedSize(16, 16)
            self.close_btn.setCursor(Qt.PointingHandCursor)
            self.close_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {self.color_scheme['text']};
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background: rgba(0, 0, 0, 0.1);
                }}
            """)
            self.close_btn.clicked.connect(self._on_remove)
            layout.addWidget(self.close_btn)
        
        # Style du widget principal
        self.setStyleSheet(f"""
            TagWidget {{
                background-color: {self.color_scheme['bg']};
                border: 1.5px solid {self.color_scheme['border']};
                border-radius: 14px;
            }}
        """)
    
    def _on_remove(self):
        """Émet le signal de suppression"""
        self.removed.emit(self)


class TagContainer(QtWidgets.QWidget):
    """Conteneur pour afficher plusieurs tags avec wrapping automatique"""
    
    def __init__(self, title="Labels", parent=None):
        super().__init__(parent)
        self.title = title
        self.tags = []
        self._init_ui()
    
    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # En-tête avec titre et bouton collapse
        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Icône et titre
        title_layout = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel("🏷️")
        title_icon.setStyleSheet("font-size: 14px;")
        title_layout.addWidget(title_icon)
        
        title_label = QtWidgets.QLabel(self.title)
        title_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {ColorPalette.TEXT};
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        
        # Bouton collapse
        self.collapse_btn = QtWidgets.QPushButton("Collapse")
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {ColorPalette.PRIMARY};
                border: none;
                font-size: 11px;
                padding: 2px 8px;
                text-decoration: underline;
            }}
            QPushButton:hover {{
                color: {ColorPalette.ACCENT};
            }}
        """)
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self.collapse_btn)
        
        main_layout.addWidget(header)
        
        # Conteneur scrollable pour les tags
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)
        
        # Widget pour le flow layout
        self.tags_widget = QtWidgets.QWidget()
        self.flow_layout = FlowLayout(self.tags_widget)
        self.flow_layout.setSpacing(8)
        
        scroll.setWidget(self.tags_widget)
        main_layout.addWidget(scroll)
        
        self.is_collapsed = False
    
    def add_tag(self, text, color_scheme=None, removable=True):
        """Ajoute un nouveau tag"""
        tag = TagWidget(text, color_scheme, removable)
        tag.removed.connect(self._on_tag_removed)
        self.flow_layout.addWidget(tag)
        self.tags.append(tag)
        return tag
    
    def clear_tags(self):
        """Supprime tous les tags"""
        for tag in self.tags[:]:
            self.flow_layout.removeWidget(tag)
            tag.deleteLater()
        self.tags.clear()
    
    def _on_tag_removed(self, tag):
        """Gère la suppression d'un tag"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.flow_layout.removeWidget(tag)
            tag.deleteLater()
    
    def _toggle_collapse(self):
        """Toggle l'état collapse/expand"""
        self.is_collapsed = not self.is_collapsed
        self.tags_widget.setVisible(not self.is_collapsed)
        self.collapse_btn.setText("Expand" if self.is_collapsed else "Collapse")
    
    def get_tags_text(self):
        """Retourne la liste des textes des tags"""
        return [tag.text for tag in self.tags]


class FlowLayout(QtWidgets.QLayout):
    """Layout qui arrange les widgets en flow (wrapping automatique)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.item_list = []
        self._spacing = 5
    
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
    
    def addItem(self, item):
        self.item_list.append(item)
    
    def count(self):
        return len(self.item_list)
    
    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None
    
    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None
    
    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        height = self._do_layout(QtCore.QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)
    
    def sizeHint(self):
        return self.minimumSize()
    
    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QtCore.QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size
    
    def setSpacing(self, spacing):
        self._spacing = spacing
    
    def spacing(self):
        return self._spacing
    
    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        
        for item in self.item_list:
            widget = item.widget()
            space_x = spacing
            space_y = spacing
            
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        
        return y + line_height - rect.y()


class NodeInfoPanel(QtWidgets.QWidget):
    """Panneau d'affichage des détails d'un nœud sélectionné"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(400)
        self._init_ui()
    
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(15)
        
        # Titre
        title = QtWidgets.QLabel("Détails du Nœud")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {ColorPalette.PRIMARY};")
        layout.addWidget(title)
        
        # Zone de détails avec scroll
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 6px;
                background-color: {ColorPalette.BACKGROUND};
            }}
        """)
        
        self.details_widget = QtWidgets.QWidget()
        self.details_layout = QtWidgets.QVBoxLayout(self.details_widget)
        self.details_layout.setAlignment(Qt.AlignTop)
        self.details_layout.setSpacing(12)
        
        scroll.setWidget(self.details_widget)
        layout.addWidget(scroll)
        
        # Message par défaut
        self.show_empty_state()
    
    def show_empty_state(self):
        """Affiche un message quand aucun nœud n'est sélectionné"""
        self._clear_details()
        
        empty_label = QtWidgets.QLabel("Sélectionnez un nœud pour voir ses détails")
        empty_label.setStyleSheet(f"""
            color: {ColorPalette.TEXT_LIGHT};
            font-size: 12px;
            padding: 30px 10px;
        """)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setWordWrap(True)
        self.details_layout.addWidget(empty_label)
    
    def display_node(self, node_data):
        """Affiche les détails d'un nœud avec tags pour les catégories"""
        self._clear_details()
        
        # Nom du nœud
        node_name = node_data.get('label', node_data.get('name', 'N/A'))
        name_label = self._create_field("Nom", node_name)
        self.details_layout.addWidget(name_label)
        
        # ID
        if 'id' in node_data or 'uid' in node_data:
            node_id = node_data.get('id') or node_data.get('uid')
            id_label = self._create_field("ID", node_id, monospace=True)
            self.details_layout.addWidget(id_label)
        
        # Chemin
        if 'path' in node_data:
            path_label = self._create_field("Chemin", node_data['path'], monospace=True)
            self.details_layout.addWidget(path_label)
        
        # Catégories avec TagContainer
        if 'category' in node_data:
            categories = node_data['category']
            if categories:
                cat_container = TagContainer(title="Catégories")
                cat_list = categories if isinstance(categories, list) else [str(categories)]
                
                for i, cat in enumerate(cat_list):
                    color_scheme = ColorPalette.TAG_COLORS[i % len(ColorPalette.TAG_COLORS)]
                    cat_container.add_tag(cat, color_scheme, removable=False)
                
                self.details_layout.addWidget(cat_container)
        
        # Niveau
        if 'level' in node_data:
            level_label = self._create_field("Niveau", str(node_data['level']))
            self.details_layout.addWidget(level_label)
        
        # Dates
        if 'createdAt' in node_data:
            created_label = self._create_field("Créé le", node_data['createdAt'])
            self.details_layout.addWidget(created_label)
        
        if 'updatedAt' in node_data:
            updated_label = self._create_field("Modifié le", node_data['updatedAt'])
            self.details_layout.addWidget(updated_label)
        
        # Type de nœud avec tag
        node_path = node_data.get('path', '')
        is_file = node_path and os.path.splitext(node_path)[1]
        node_type = "Fichier" if is_file else "Dossier"
        type_container = TagContainer(title="Type")
        color = ColorPalette.TAG_COLORS[0] if node_type == "Fichier" else ColorPalette.TAG_COLORS[5]
        type_container.add_tag(node_type, color, removable=False)
        self.details_layout.addWidget(type_container)
        
        self.details_layout.addStretch()
    
    def _create_field(self, label, value, monospace=False):
        """Crée un widget de champ avec label et valeur"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(3)
        
        # Label
        label_widget = QtWidgets.QLabel(label)
        label_widget.setStyleSheet(f"font-weight: bold; color: {ColorPalette.SECONDARY}; font-size: 11px;")
        layout.addWidget(label_widget)
        
        # Valeur
        value_widget = QtWidgets.QLabel(str(value))
        font_style = "font-family: 'Courier New', monospace;" if monospace else ""
        value_widget.setStyleSheet(f"""
            color: {ColorPalette.TEXT};
            font-size: 11px;
            padding: 6px;
            background-color: {ColorPalette.LIGHTER};
            border-radius: 4px;
            {font_style}
        """)
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(value_widget)
        
        return container
    
    def _clear_details(self):
        """Efface tous les widgets de détails"""
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class FileTreeWidget(QtWidgets.QTreeWidget):
    """Widget d'arbre pour naviguer dans la hiérarchie des nœuds"""
    
    itemDoubleClicked = pyqtSignal(object)  # Signal pour double-clic sur item
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setColumnCount(1)
        self.setAlternatingRowColors(True)
        self.setMaximumWidth(450)
        self.setStyleSheet(f"""
            QTreeWidget {{
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 6px;
                background-color: {ColorPalette.BACKGROUND};
                font-size: 12px;
            }}
            QTreeWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {ColorPalette.LIGHT};
            }}
            QTreeWidget::item:selected {{
                background-color: {ColorPalette.SELECTED};
                color: {ColorPalette.TEXT};
            }}
            QTreeWidget::item:hover {{
                background-color: {ColorPalette.LIGHT};
            }}
        """)
        self.itemDoubleClicked.connect(self._on_double_click)
    
    def _on_double_click(self, item):
        """Gère le double-clic pour éditer le code si fichier"""
        self.itemDoubleClicked.emit(item)


class PlatformSelector(QtWidgets.QWidget):
    """Widget de sélection des plateformes IA avec tags"""
    
    FALLBACK_PLATFORMS = [
        {'name': 'ChatGPT', 'type': 'chatgpt', 'icon': '💬'},
        {'name': 'Claude AI', 'type': 'claude', 'icon': '🤖'},
        {'name': 'Grok', 'type': 'grok', 'icon': '🚀'},
        {'name': 'Gemini', 'type': 'gemini', 'icon': '✨'}
    ]
    
    def __init__(self, selector_generator, parent=None):
        super().__init__(parent)
        self.selector_generator = selector_generator
        self.platforms_data = []
        self.setMaximumWidth(400)
        self._init_ui()
    
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # En-tête
        header = QtWidgets.QLabel("Plateformes IA Disponibles")
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {ColorPalette.PRIMARY};")
        layout.addWidget(header)
        
        # Conteneur de tags pour les plateformes sélectionnées
        self.selected_container = TagContainer(title="Plateformes Sélectionnées")
        layout.addWidget(self.selected_container)
        
        # Liste des plateformes
        self.platforms_list = QtWidgets.QListWidget()
        self.platforms_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.platforms_list.setMinimumHeight(180)
        self.platforms_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 6px;
                background-color: {ColorPalette.BACKGROUND};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {ColorPalette.LIGHT};
            }}
            QListWidget::item:selected {{
                background-color: {ColorPalette.SELECTED};
                color: {ColorPalette.TEXT};
            }}
            QListWidget::item:hover {{
                background-color: {ColorPalette.LIGHT};
            }}
        """)
        self.platforms_list.itemSelectionChanged.connect(self._update_selected_tags)
        layout.addWidget(self.platforms_list)
    
    def _update_selected_tags(self):
        """Met à jour l'affichage des tags des plateformes sélectionnées"""
        self.selected_container.clear_tags()
        
        for item in self.platforms_list.selectedItems():
            config = item.data(Qt.UserRole)
            if config:
                name = config.get('name', 'Plateforme')
                color_idx = hash(name) % len(ColorPalette.TAG_COLORS)
                self.selected_container.add_tag(name, ColorPalette.TAG_COLORS[color_idx], removable=False)
    
    def load_platforms(self, conductor):
        """Charge les plateformes depuis le conductor"""
        self.platforms_list.clear()
        self.platforms_data = []
        
        platforms_loaded = False
        
        if conductor:
            try:
                platforms = conductor.database.get_all_platforms()
                
                if platforms:
                    for name, config in sorted(platforms.items()):
                        icon_map = {
                            'claude': '🤖',
                            'chatgpt': '💬',
                            'gemini': '✨',
                            'grok': '🚀',
                            'deepseek': '🔍'
                        }
                        
                        platform_type = name.lower()
                        icon = next((v for k, v in icon_map.items() if k in platform_type), '🔧')
                        
                        item = QtWidgets.QListWidgetItem(f"{icon} {name}")
                        item.setData(Qt.UserRole, config)
                        self.platforms_list.addItem(item)
                        self.platforms_data.append(config)
                    
                    platforms_loaded = True
                    self._log_platform(f"{len(platforms)} plateforme(s) chargée(s)")
                    
            except Exception as e:
                self._log_platform(f"Erreur chargement plateformes: {e}")
                logger.error(f"Erreur chargement plateformes: {e}")
        
        if not platforms_loaded:
            self._log_platform("Chargement des plateformes par défaut")
            for platform in self.FALLBACK_PLATFORMS:
                item = QtWidgets.QListWidgetItem(f"{platform['icon']} {platform['name']}")
                item.setData(Qt.UserRole, platform)
                self.platforms_list.addItem(item)
                self.platforms_data.append(platform)
            
            self._log_platform(f"{len(self.FALLBACK_PLATFORMS)} plateforme(s) par défaut chargée(s)")
    
    def _log_platform(self, message):
        """Log pour le chargement des plateformes"""
        print(f"[PlatformSelector] {message}")
    
    def get_selected_platforms(self):
        """Retourne les plateformes sélectionnées"""
        selected = []
        for item in self.platforms_list.selectedItems():
            config = item.data(Qt.UserRole)
            if config:
                selected.append(config)
        return selected


class NodeCreationWidget(QtWidgets.QWidget):
    """Widget principal amélioré pour la création de nœuds"""
    
    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.selector_generator = UniversalSelectorGenerator()
        self.current_node_data = None
        self.dgraph_connector = None
        self.tree_data = {}  # Pour stocker la hiérarchie locale
        
        self._init_ui()
        self._load_data()
        
        if self.platform_selector:
            self.platform_selector.load_platforms(self.conductor)
    
    def _transform_root_labels(self, dgraph_root_labels):
        """Transforme les root_labels depuis le format Dgraph vers le format Liris."""
        transformed = []

        for root in dgraph_root_labels:
            root_obj = {
                "label": root.get('name', ''),
                "id": root.get('id', str(uuid.uuid4())),
                "description": root.get('description', ''),
                "category": root.get('category', []),
                "parents": [],
                "codeContent": root.get('codeContent', '')  # Charger codeContent
            }

            for parent in root.get('parents', []):
                parent_obj = {
                    "label": parent.get('name', ''),
                    "id": parent.get('id', str(uuid.uuid4())),
                    "description": parent.get('description', ''),
                    "category": parent.get('category', []),
                    "children": [],
                    "codeContent": parent.get('codeContent', '')  # Charger codeContent
                }

                for child in parent.get('children', []):
                    child_obj = {
                        "label": child.get('name', ''),
                        "id": child.get('id', str(uuid.uuid4())),
                        "description": child.get('description', ''),
                        "category": child.get('category', []),
                        "codeContent": child.get('codeContent', '')  # Charger codeContent
                    }
                    parent_obj['children'].append(child_obj)

                root_obj['parents'].append(parent_obj)

            transformed.append(root_obj)

        return transformed

    def _has_extension(self, filename):
        """Vérifie si le nom a une extension de fichier"""
        return bool(os.path.splitext(filename)[1])

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Titre
        title = QtWidgets.QLabel("🔨 Création de Nœuds de Fonction")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {ColorPalette.PRIMARY};
            padding: 10px;
            background-color: {ColorPalette.BACKGROUND};
            border: 2px solid {ColorPalette.BORDER};
            border-radius: 8px;
        """)
        main_layout.addWidget(title)
        
        # Layout principal en splitter
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # Panneau gauche: Navigation
        left_panel = self._create_navigation_panel()
        left_panel.setMaximumWidth(500)
        splitter.addWidget(left_panel)
        
        # Panneau droite: Détails et actions
        right_panel = self._create_details_panel()
        right_panel.setMaximumWidth(450)
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter, 1)
        
        # Bouton de création
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        self.create_button = QtWidgets.QPushButton("🚀 Procéder à la Création")
        self.create_button.setFixedHeight(45)
        self.create_button.setMinimumWidth(250)
        self.create_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ColorPalette.SUCCESS};
                color: white;
                border-radius: 8px;
                padding: 0px 30px;
                font-size: 15px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #229954;
            }}
            QPushButton:pressed {{
                background-color: #1e8449;
            }}
            QPushButton:disabled {{
                background-color: {ColorPalette.BORDER};
                color: {ColorPalette.TEXT_LIGHT};
            }}
        """)
        self.create_button.clicked.connect(self._on_create_nodes)
        self.create_button.setEnabled(False)
        button_layout.addStretch()
        button_layout.addWidget(self.create_button)
        button_layout.addStretch()
        main_layout.addWidget(button_container)
    
    def _create_navigation_panel(self):
        """Crée le panneau de navigation"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Workspace selector
        workspace_label = QtWidgets.QLabel("📁 Workspace")
        workspace_label.setStyleSheet(f"font-weight: bold; color: {ColorPalette.PRIMARY}; font-size: 13px;")
        layout.addWidget(workspace_label)
        
        self.workspace_combo = QtWidgets.QComboBox()
        self.workspace_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px;
                border: 2px solid {ColorPalette.BORDER};
                border-radius: 6px;
                font-size: 12px;
                background-color: {ColorPalette.BACKGROUND};
            }}
            QComboBox:hover {{
                border-color: {ColorPalette.SECONDARY};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        self.workspace_combo.currentIndexChanged.connect(self._on_workspace_changed)
        layout.addWidget(self.workspace_combo)
        
        # Arbre de fichiers
        tree_label = QtWidgets.QLabel("📂 Structure des Nœuds")
        tree_label.setStyleSheet(f"font-weight: bold; color: {ColorPalette.PRIMARY}; font-size: 13px; margin-top: 5px;")
        layout.addWidget(tree_label)
        
        self.file_tree = FileTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemClicked.connect(self._on_node_selected)
        self.file_tree.itemDoubleClicked.connect(self.file_tree._on_double_click)
        layout.addWidget(self.file_tree, 1)
        
        # Boutons de gestion
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.add_node_button = QPushButton("+ Ajouter")
        self.add_node_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ColorPalette.SUCCESS};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #229954;
            }}
        """)
        self.add_node_button.clicked.connect(self._add_node)
        self.add_node_button.setEnabled(False)
        buttons_layout.addWidget(self.add_node_button)
        
        self.edit_node_button = QPushButton("✏️ Éditer")
        self.edit_node_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ColorPalette.WARNING};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #e67e22;
            }}
        """)
        self.edit_node_button.clicked.connect(self._edit_node)
        self.edit_node_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_node_button)
        
        self.delete_node_button = QPushButton("🗑️ Supprimer")
        self.delete_node_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ColorPalette.DANGER};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #c0392b;
            }}
        """)
        self.delete_node_button.clicked.connect(self._delete_node)
        self.delete_node_button.setEnabled(False)
        buttons_layout.addWidget(self.delete_node_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_details_panel(self):
        """Crée le panneau de détails"""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(15)
        
        # Détails du nœud
        self.node_info = NodeInfoPanel()
        layout.addWidget(self.node_info, 1)
        
        # Sélecteur de plateformes
        self.platform_selector = PlatformSelector(self.selector_generator)
        layout.addWidget(self.platform_selector, 1)
        
        return panel
    
    def _load_data(self):
        """Charge les données depuis Dgraph"""
        self._log("🔄 Chargement des workspaces depuis Dgraph...")
        
        if not self.conductor or not hasattr(self.conductor, 'dgraph_connector'):
            self._log("❌ Dgraph connector non disponible")
            try:
                self.dgraph_connector = LirisDgraphConnector()
                if self.dgraph_connector.client:
                    self._log("✅ Connexion directe à Dgraph établie")
                    self._load_workspaces_from_dgraph()
                else:
                    self._log("❌ Impossible de se connecter à Dgraph")
            except Exception as e:
                self._log(f"❌ Erreur de connexion: {e}")
            return
        
        self._load_workspaces_from_dgraph()
    
    def _load_workspaces_from_dgraph(self):
        """Charge les workspaces depuis Dgraph via le connector"""
        try:
            connector = getattr(self.conductor, 'dgraph_connector', self.dgraph_connector)
            
            if not connector or not connector.client:
                self._log("❌ Connector Dgraph invalide")
                return
            
            result = connector.query_workspaces()
            
            if not result or 'q' not in result or not result['q']:
                self._log("⚠️ Aucun workspace trouvé dans Dgraph")
                self.workspace_combo.addItem("Aucun workspace disponible", None)
                return
            
            self.workspace_combo.clear()
            self.workspace_combo.addItem("Sélectionner...", None)
            
            for workspace in result['q']:
                name = workspace.get('name', workspace.get('id', 'Sans nom'))
                self.workspace_combo.addItem(name, workspace)
            
            self._log(f"✅ {len(result['q'])} workspace(s) chargé(s)")
            
        except Exception as e:
            self._log(f"❌ Erreur lors du chargement: {e}")
            traceback.print_exc()
    
    def _on_workspace_changed(self, index):
        """Gère le changement de workspace"""
        self.file_tree.clear()
        self.node_info.show_empty_state()
        self.current_node_data = None
        self.create_button.setEnabled(False)
        self.add_node_button.setEnabled(False)
        self.edit_node_button.setEnabled(False)
        self.delete_node_button.setEnabled(False)
        
        if index <= 0:
            return
        
        workspace_data = self.workspace_combo.itemData(index)
        if not workspace_data:
            return
        
        self._log(f"📂 Chargement du workspace: {workspace_data.get('name')}")
        self._build_tree(workspace_data)
    
    def _build_tree(self, workspace_data):
        """Construit l'arbre de navigation avec transformation des données"""
        self.tree_data = {}  # Reset tree data
        cluster_mgmt = workspace_data.get('clusterManagement', {})
        clusters = cluster_mgmt.get('clusters', [])
        
        clusters_detailed = []
        for cluster in clusters:
            cluster_data = {
                "name": cluster.get('name', ''),
                "id": cluster.get('id', str(uuid.uuid4())),
                "description": cluster.get('description', ''),
                "codeContent": cluster.get('codeContent', ''),
                "root_labels": self._transform_root_labels(cluster.get('root_labels', []))
            }
            clusters_detailed.append(cluster_data)
            self.tree_data[cluster_data['id']] = cluster_data
        
        for cluster_data in clusters_detailed:
            cluster_name = cluster_data.get('name', 'Cluster')
            cluster_item = QtWidgets.QTreeWidgetItem([f"📦 {cluster_name}"])
            cluster_item.setData(0, Qt.UserRole, cluster_data)
            self.file_tree.addTopLevelItem(cluster_item)
            
            # Ajouter le fichier du cluster s'il a une extension
            if self._has_extension(cluster_data.get('name', '')):
                file_item = QtWidgets.QTreeWidgetItem([f"📄 {cluster_data['name']}"])
                full_data = cluster_data.copy()
                full_data['is_cluster_file'] = True
                file_item.setData(0, Qt.UserRole, full_data)
                cluster_item.addChild(file_item)
            
            root_labels = cluster_data.get("root_labels", [])
            
            processed_ids = set()
            self._add_nodes_to_tree(cluster_item, root_labels, cluster_data, processed_ids)
            
            cluster_item.setExpanded(True)
    
    def _add_nodes_to_tree(self, parent_item, nodes, cluster_data, processed_ids):
        """Ajoute récursivement les nœuds à l'arbre sans doublons"""
        if not nodes:
            return
        
        for node in nodes:
            node_id = node.get('id')
            if not node_id or node_id in processed_ids:
                continue
            processed_ids.add(node_id)
            
            node_name = node.get('label', node.get('name', 'Sans nom'))
            is_file = self._has_extension(node_name)
            icon = "📄" if is_file else "📁"
            
            item = QtWidgets.QTreeWidgetItem([f"{icon} {node_name}"])
            
            full_data = node.copy()
            full_data['cluster_id'] = cluster_data.get('id')
            item.setData(0, Qt.UserRole, full_data)
            
            parent_item.addChild(item)
            
            if not is_file:
                # Recurse seulement si pas un fichier
                if 'parents' in node and node['parents']:
                    self._add_nodes_to_tree(item, node['parents'], cluster_data, processed_ids)
                if 'children' in node and node['children']:
                    self._add_nodes_to_tree(item, node['children'], cluster_data, processed_ids)
    
    def _on_node_selected(self, item, column):
        """Gère la sélection d'un nœud"""
        node_data = item.data(0, Qt.UserRole)
        if not node_data:
            return
        
        self.current_node_data = node_data
        self.node_info.display_node(node_data)
        
        path = node_data.get('path')
        is_file = bool(path and self._has_extension(path))
        
        self.create_button.setEnabled(is_file)
        self.add_node_button.setEnabled(True)
        self.edit_node_button.setEnabled(True)
        self.delete_node_button.setEnabled(True)
        
        if is_file:
            self._log(f"Fichier sélectionné: {node_data.get('label', node_data.get('name'))}")
        else:
            self._log(f"Dossier sélectionné: {node_data.get('label', node_data.get('name'))}")
    
    def _add_node(self):
        """Ajoute un nouveau nœud"""
        if not self.current_node_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un nœud parent")
            return
        
        dialog = AddEditItemDialog("Ajouter un Nœud", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_node = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "codeContent": "",
                    "createdAt": datetime.now().isoformat() + "Z",
                    "updatedAt": datetime.now().isoformat() + "Z"
                }
                
                # Ajouter comme enfant du courant
                current_item = self.file_tree.currentItem()
                if current_item:
                    new_item = QtWidgets.QTreeWidgetItem([f"📁 {new_node['label']}"])
                    new_item.setData(0, Qt.UserRole, new_node)
                    current_item.addChild(new_item)
                    current_item.setExpanded(True)
                    self._log(f"Nœud ajouté: {new_node['label']}")
    
    def _edit_node(self):
        """Édite le nœud sélectionné"""
        if not self.current_node_data:
            return
        
        current_name = self.current_node_data.get('label', self.current_node_data.get('name', ''))
        dialog = AddEditItemDialog("Éditer le Nœud", current_name, self.current_node_data.get('description', ''), self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                self.current_node_data['label'] = data["name"]
                self.current_node_data['description'] = data["description"]
                self.current_node_data['updatedAt'] = datetime.now().isoformat() + "Z"
                
                current_item = self.file_tree.currentItem()
                if current_item:
                    current_item.setText(0, f"📁 {data['name']}")
                    self.node_info.display_node(self.current_node_data)
                    self._log(f"Nœud modifié: {data['name']}")
    
    def _delete_node(self):
        """Supprime le nœud sélectionné"""
        if not self.current_node_data:
            return
        
        reply = QMessageBox.question(self, "Confirmer", f"Supprimer le nœud '{self.current_node_data.get('label', self.current_node_data.get('name'))}' ?", 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            current_item = self.file_tree.currentItem()
            if current_item:
                parent = current_item.parent()
                if parent:
                    parent.removeChild(current_item)
                else:
                    self.file_tree.takeTopLevelItem(self.file_tree.indexOfTopLevelItem(current_item))
                self._log("Nœud supprimé")
                self.node_info.show_empty_state()
                self.current_node_data = None
                self.create_button.setEnabled(False)
    
    def _on_create_nodes(self):
        """Lance le processus de création de nœuds"""
        if not self.current_node_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un fichier")
            return
        
        selected_platforms = self.platform_selector.get_selected_platforms()
        if not selected_platforms:
            QMessageBox.warning(self, "Plateformes", "Veuillez sélectionner au moins une plateforme IA")
            return
        
        self._log("🚀 Démarrage du processus de création...")
        self.create_button.setEnabled(False)
        
        # TODO: Implémenter la logique de création de fonctions sous le nœud sélectionné
        
        self._log("✅ Processus terminé")
        self.create_button.setEnabled(True)
    
    def _log(self, message):
        """Log dans la console"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def refresh(self):
        """Rafraîchit le widget"""
        self._load_data()
        self.platform_selector.load_platforms(self.conductor)