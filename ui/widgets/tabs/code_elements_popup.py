import os
import json
import uuid
from typing import Dict, Any
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
                             QTextEdit, QPushButton, QFrame, QListWidgetItem, QApplication, QMessageBox)
from PyQt5.QtGui import QColor

from utils.logger import logger  # Assumant que c'est importé dans le projet
from ui.styles.platform_config_style import PlatformConfigStyle  # Si disponible, sinon fallback CSS
from utils.multi_language_parser import MultiLanguageDependencyParser  # Pour extraire classes/foncs/vars

class CodeElementsPopup(QDialog):
    """
    Popup modale pour afficher les éléments de code (classes, fonctions, variables) et leurs enfants hiérarchiques.
    Design et fonctionnalités similaires aux sections principales (cluster, root, parent/enfant).
    Supporte la récursivité pour enfants des enfants via sous-popups.
    """
    
    def __init__(self, file_basename: str, file_path: str, file_content: str, parent_data: Dict, parent=None):
        super().__init__(parent)
        self.file_basename = file_basename
        self.file_path = file_path
        self.file_content = file_content
        self.parent_data = parent_data
        self.dependency_parser = MultiLanguageDependencyParser()
        self.setWindowTitle(f"Éléments de {file_basename} - Hiérarchie enfants")
        self.setMinimumSize(800, 600)
        
        # Style global si disponible
        if hasattr(self, 'PlatformConfigStyle'):
            self.setStyleSheet(PlatformConfigStyle.get_input_style())
        
        self._init_ui()
        self._populate_elements_list()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Titre
        title = QLabel(f"📄 {self.file_basename} - Enfants et sous-enfants")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)
        
        # Liste des éléments
        self.elements_list = QListWidget()
        self.elements_list.setStyleSheet(self._get_list_style())
        self.elements_list.itemSelectionChanged.connect(self._update_details)
        self.elements_list.itemDoubleClicked.connect(self._on_double_click_item)
        layout.addWidget(self.elements_list)
        
        # Zone de détails
        self.details_edit = QTextEdit()
        self.details_edit.setReadOnly(True)
        self.details_edit.setMaximumHeight(200)
        self.details_edit.setPlaceholderText("Sélectionnez un élément pour voir les détails...")
        self.details_edit.setStyleSheet(self._get_textedit_style())
        layout.addWidget(self.details_edit)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #ccc; max-height: 1px;")
        layout.addWidget(separator)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        button_style = self._get_button_style()
        
        copy_btn = QPushButton("📋 Copier snippet")
        copy_btn.setStyleSheet(button_style)
        copy_btn.clicked.connect(self._copy_snippet)
        buttons_layout.addWidget(copy_btn)
        
        full_btn = QPushButton("📖 Fichier complet")
        full_btn.setStyleSheet(button_style)
        full_btn.clicked.connect(self._show_full_file)
        buttons_layout.addWidget(full_btn)
        
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet(button_style)
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(close_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
    
    def _get_list_style(self) -> str:
        return """
            QListWidget {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                color: black;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #dcdcdc;
            }
            QListWidget::item:hover {
                background-color: #eaeaea;
            }
        """
    
    def _get_textedit_style(self) -> str:
        return """
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                color: black;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """
    
    def _get_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #f2f2f2;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """
    
    def _populate_elements_list(self):
        """Peuple la liste avec éléments de code et enfants indentés."""
        self.elements_list.clear()
        
        # Extraire si nécessaire
        if not self.parent_data.get('classes'):
            self.parent_data['classes'] = self.dependency_parser.extract_classes(self.file_content, self.file_path)
        if not self.parent_data.get('functions'):
            self.parent_data['functions'] = self.dependency_parser.extract_functions(self.file_content, self.file_path)
        if not self.parent_data.get('variables'):
            self.parent_data['variables'] = self.dependency_parser.extract_variables(self.file_content, self.file_path)
        
        # Ajouter classes + enfants
        for cls in self.parent_data.get('classes', []):
            self._add_element_item(cls, 'class', "")
            for child in cls.get('children', []):
                self._add_indented_child(child, "", 1)  # Niveau 1
        
        # Ajouter fonctions + enfants
        for func in self.parent_data.get('functions', []):
            self._add_element_item(func, func.get('type', 'function'), "")
            for child in func.get('children', []):
                self._add_indented_child(child, "", 1)
        
        # Ajouter variables (généralement sans enfants)
        for var in self.parent_data.get('variables', []):
            self._add_element_item(var, 'variable', "")
    
    def _add_element_item(self, item: Dict, item_type: str, indent: str):
        """Ajoute un item principal à la liste."""
        uid = item.get('uid', str(uuid.uuid4()))
        line = item.get('line', '?')
        display = f"{indent}[{item_type.upper()}] {item['name']} (ligne {line})"
        qitem = QListWidgetItem(display)
        qitem.setData(QtCore.Qt.UserRole, uid)
        qitem.setData(QtCore.Qt.UserRole + 1, item_type)
        qitem.setData(QtCore.Qt.UserRole + 2, self.file_path)
        qitem.setData(QtCore.Qt.UserRole + 3, item.get('line', 0))
        qitem.setData(QtCore.Qt.UserRole + 4, item)  # Objet complet
        qitem.setForeground(QColor("#e74c3c" if item_type == 'class' else "#3498db" if 'function' in item_type else "#2ecc71"))
        self.elements_list.addItem(qitem)
    
    def _add_indented_child(self, child: Dict, parent_indent: str, level: int):
        """Ajoute un enfant indenté (récursif)."""
        if level > 3:  # Limite profondeur pour éviter surcharge
            return
        child_type = child.get('type', 'unknown')
        indent = parent_indent + "  " * (level - 1)
        display = f"{indent}└─ {self._get_node_icon(child_type)} {child.get('name', 'Sans nom')} (ligne {child.get('line', '?')})"
        qitem = QListWidgetItem(display)
        uid = child.get('uid', str(uuid.uuid4()))
        qitem.setData(QtCore.Qt.UserRole, uid)
        qitem.setData(QtCore.Qt.UserRole + 1, child_type)
        qitem.setData(QtCore.Qt.UserRole + 2, self.file_path)
        qitem.setData(QtCore.Qt.UserRole + 3, child.get('line', 0))
        qitem.setData(QtCore.Qt.UserRole + 4, child)
        qitem.setForeground(QColor("#95a5a6"))  # Gris pour sous-niveaux
        self.elements_list.addItem(qitem)
        
        # Récursif
        for subchild in child.get('children', []):
            self._add_indented_child(subchild, parent_indent, level + 1)
    
    def _get_node_icon(self, node_type: str) -> str:
        """Icône par type (réutilisable)."""
        icons = {'method': '⚙️', 'variable': '🔹', 'folder': '📁', 'file': '📄'}
        return icons.get(node_type, '📦')
    
    def _update_details(self):
        """Met à jour les détails sur sélection."""
        current = self.elements_list.currentItem()
        if not current:
            self.details_edit.setPlainText("")
            return
        item_obj = current.data(QtCore.Qt.UserRole + 4)
        if item_obj:
            # Réutilise _format_child_details du parent widget (passé en param ou importé)
            details = self._format_child_details(item_obj)  # Implémentez ci-dessous ou importez
            self.details_edit.setPlainText(details)
    
    def _on_double_click_item(self, item):
        """Double-clic : snippet ou sous-popup."""
        item_type = item.data(QtCore.Qt.UserRole + 1)
        line_num = item.data(QtCore.Qt.UserRole + 3) or 1
        item_text = item.text()
        item_obj = item.data(QtCore.Qt.UserRole + 4)
        
        if item_type in ['class', 'function', 'variable', 'method']:
            # Snippet (réutilise méthode du parent)
            if hasattr(self.parent(), '_show_code_snippet_dialog'):
                self.parent()._show_code_snippet_dialog(self.file_path, self.file_content, item_type, line_num, item_text)
        elif item_obj and item_obj.get('children'):
            # Sous-popup pour enfants des enfants
            sub_popup = CodeElementsPopup(self.file_basename, self.file_path, self.file_content, item_obj, self)
            sub_popup.exec_()
        else:
            # Fallback snippet
            if hasattr(self.parent(), '_show_code_snippet_dialog'):
                self.parent()._show_code_snippet_dialog(self.file_path, self.file_content, item_type, line_num, item_text)
    
    def _copy_snippet(self):
        """Copie un snippet basique (50 lignes)."""
        lines = self.file_content.split('\n')
        snippet = '\n'.join(lines[:50])
        if len(lines) > 50:
            snippet += f"\n\n... ({len(lines) - 50} lignes supplémentaires)"
        clipboard = QApplication.clipboard()
        clipboard.setText(snippet)
        QMessageBox.information(self, "Copié", "Snippet copié dans le presse-papier.")
    
    def _show_full_file(self):
        """Affiche le fichier complet (réutilise méthode du parent)."""
        if hasattr(self.parent(), '_show_file_content_dialog'):
            self.parent()._show_file_content_dialog(self.file_path, self.file_content, {'label': self.file_basename})
    
    def _format_child_details(self, child: Dict) -> str:
        """Formatage des détails (copié/adapté de l'original ; étendez si besoin)."""
        child_type = child.get('type', 'unknown')
        details = f"=== {child_type.upper()} ===\n\n"
        details += f"Nom: {child.get('name', 'N/A')}\n"
        details += f"Ligne: {child.get('line', 'N/A')}\n"
        details += f"Description: {child.get('description', 'N/A')}\n"
        
        # Ajoutez plus (ex. params pour funcs, bases pour classes) selon vos besoins
        children_count = len(child.get('children', []))
        if children_count:
            details += f"\nEnfants ({children_count}):\n"
            for ch in child.get('children', [])[:5]:
                details += f"  - {ch.get('name', 'N/A')}\n"
            if children_count > 5:
                details += f"  ... et {children_count - 5} autres\n"
        
        return details