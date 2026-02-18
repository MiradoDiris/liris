#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Generation Panel - Improved 3-column layout
Left: Project & Config | Center: Prompt Editor | Right: Combinations Visualizer
"""

from email.mime import message
import json
from operator import index
import os

from datetime import datetime
from typing import Dict
from unittest import result
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QComboBox, QProgressBar, QScrollArea,
    QFrame, QGroupBox, QMessageBox, QFileDialog, QDialog
)
from PyQt5.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush
import sys
from pathlib import Path
from typing import Dict, Any
from PyQt5.QtCore import QThread
from self import self
from utils.enhanced_logging import ResultTracer

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager
import qtawesome as qta
from PyQt5.QtGui import QPainter

def get_dropdown_svg_path():
    """Retourne le chemin vers l'icône dropdown SVG"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.dirname(current_dir)
    svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
    svg_path = os.path.normpath(svg_path)
    return svg_path.replace('\\', '/')

class CollapsibleSection(QWidget):
    """Section collapsible avec chevron - VERSION RESPONSIVE"""
    
    def __init__(self, title="Section", parent=None):
        super().__init__(parent)
        self.is_collapsed = True
        self.section_title = title
        
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header avec chevron
        self.header = QPushButton()
        self.header.setMinimumHeight(40)  # ✅ Hauteur minimum
        self.header.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        # Style par défaut (gradient bleu)
        self.default_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
        """
        
        # Style alternatif (gris clair pour section d'ajout)
        self.light_style = """
            QPushButton {
                background: #F5F5F5;
                color: #333333;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """
        
        self.header.setStyleSheet(self.default_style)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        self.update_header_text(title)
        
        layout.addWidget(self.header)
        
        # Content
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content.setVisible(False)
        self.content.setMaximumHeight(0)
        self.content.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Maximum
        )
        self.content.setStyleSheet("""
            QWidget {
                background: #F8F9FA;
                border: 2px solid #E0E0E0;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)
        
        layout.addWidget(self.content)
        
    def update_header_text(self, title):
        """Met à jour le texte du header avec chevron"""
        chevron = "▲" if not self.is_collapsed else "▼"
        self.header.setText(f"{chevron}  {title}")
        self.section_title = title  # Mettre à jour le titre stocké
        
    def toggle(self):
        """Bascule l'état collapsed/expanded"""
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self.update_header_text(self.section_title)  # Utiliser le titre stocké
        
        # Animation
        if hasattr(self, 'animation'):
            self.animation.stop()
        
        self.animation = QPropertyAnimation(self.content, b"maximumHeight")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        if self.is_collapsed:
            # Fermeture
            self.animation.setStartValue(self.content.sizeHint().height())
            self.animation.setEndValue(0)
        else:
            # Ouverture
            self.animation.setStartValue(0)
            # Calculer la hauteur nécessaire
            target_height = self.content.sizeHint().height()
            if target_height < 100:  # Hauteur minimum raisonnable
                target_height = 200
            self.animation.setEndValue(target_height)
        
        self.animation.start()
        
    def add_widget(self, widget):
        """Ajoute un widget au contenu"""
        self.content_layout.addWidget(widget)
        
    def set_title(self, title):
        """Définit le titre"""
        self.section_title = title
        self.update_header_text(title)
    
    def set_light_style(self):
        """Applique le style gris clair au lieu du gradient bleu"""
        self.header.setStyleSheet(self.light_style)


class GradientProgressBar(QProgressBar):
    """Barre de progression avec dégradé personnalisé"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(30)
        
    def paintEvent(self, event):
        """Dessine la barre avec le dégradé PRIMARY -> SECONDARY"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fond
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 245, 245))
        painter.drawRoundedRect(self.rect(), 4, 4)
        
        # Calcul de la largeur remplie
        if self.maximum() > 0:
            progress = self.value() / self.maximum()
            filled_width = int(self.width() * progress)
            
            if filled_width > 0:
                # Dégradé vertical PRIMARY -> SECONDARY
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0, QColor(Theme.PRIMARY_COLOR))
                gradient.setColorAt(1, QColor(Theme.SECONDARY_COLOR))
                
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(0, 0, filled_width, self.height(), 4, 4)
        
        # Texte
        painter.setPen(QColor(255, 255, 255) if self.value() > self.maximum() / 2 else QColor(100, 100, 100))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class GradientButton(QPushButton):
    """Bouton avec dégradé personnalisé"""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        # Style avec dégradé
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:pressed {{
                background: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)


class CombinationVisualizer(QWidget):
    """Widget de visualisation - LISTE UNIQUEMENT (sans camembert)"""

    combination_deleted = pyqtSignal(int)
    combination_modified = pyqtSignal(int, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.combinations = []
        self.completed = []
        self.all_project_typologies = []  # ✅ Ajout pour la recherche
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # === LISTE DÉFILANTE UNIQUEMENT (PAS DE CAMEMBERT) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.combinations_widget = QWidget()
        self.combinations_layout = QVBoxLayout(self.combinations_widget)
        self.combinations_layout.setSpacing(8)
        self.combinations_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.combinations_widget)

        layout.addWidget(scroll)

    def set_combinations(self, combinations):
        """Définit les combinaisons à afficher"""
        self.combinations = combinations
        self.completed = [False] * len(combinations)
        self._update_display()
        
    def mark_completed(self, index):
        """Marque une combinaison comme complétée"""
        if 0 <= index < len(self.completed):
            self.completed[index] = True
            self._update_display()
            
    def _update_display(self):
        """
        ✅ Met à jour l'affichage avec les chemins taxonomiques complets
        """
        # Vider le layout
        while self.combinations_layout.count():
            item = self.combinations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.combinations:
            empty_label = QLabel("Aucune combinaison à afficher.\nSélectionnez un batch pour commencer.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; font-style: italic; padding: 30px; font-size: 9pt;")
            self.combinations_layout.addWidget(empty_label)
            return

        # Afficher chaque combinaison
        for i, combo in enumerate(self.combinations):
            combo_frame = QFrame()
            combo_frame.setFrameShape(QFrame.StyledPanel)
            combo_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

            is_completed = self.completed[i] if i < len(self.completed) else False

            if is_completed:
                combo_frame.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        border-radius: 4px;
                        padding: 6px;
                    }}
                """)
                text_color = "white"
            else:
                combo_frame.setStyleSheet("""
                    QFrame {
                        background: white;
                        border: 1px solid #E0E0E0;
                        border-radius: 4px;
                        padding: 6px;
                    }
                """)
                text_color = "#333333"

            combo_layout = QVBoxLayout(combo_frame)
            combo_layout.setSpacing(4)
            combo_layout.setContentsMargins(4, 4, 4, 4)

            # En-tête
            header_layout = QHBoxLayout()
            header_layout.setSpacing(4)
            header_layout.setContentsMargins(0, 0, 0, 0)

            num_label = QLabel(f"#{i+1}")
            num_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            num_label.setStyleSheet(f"color: {text_color}; min-width: 30px;")
            header_layout.addWidget(num_label)

            master_name = combo.get('master', 'N/A')
            master_label = QLabel(f"{master_name}")
            master_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            master_label.setStyleSheet(f"color: {text_color};")
            master_label.setWordWrap(True)
            header_layout.addWidget(master_label, 1)

            # Info compacte
            nb_contexts = len(combo.get('contexts', []))
            nb_samples = combo.get('nb_samples', 1)

            info_label = QLabel(f"{nb_contexts}ctx • {nb_samples}spl")
            info_label.setFont(QFont("Segoe UI", 8))
            info_label.setStyleSheet(f"color: {text_color}; padding: 0 5px;")
            header_layout.addWidget(info_label)

            # Boutons d'action (code existant)
            if not is_completed:
                edit_samples_btn = QPushButton("Modifier")
                edit_samples_btn.setToolTip("Modifier le nombre de samples")
                edit_samples_btn.setMinimumSize(40, 22)
                edit_samples_btn.setMaximumHeight(22)
                edit_samples_btn.setCursor(Qt.PointingHandCursor)
                edit_samples_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: white;
                        border: 1px solid {Theme.PRIMARY_COLOR};
                        border-radius: 3px;
                        font-size: 8pt;
                        font-weight: bold;
                        color: {Theme.PRIMARY_COLOR};
                        padding: 2px 4px;
                    }}
                    QPushButton:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        color: white;
                        border: none;
                    }}
                """)
                edit_samples_btn.clicked.connect(lambda checked, idx=i: self._edit_samples(idx))
                header_layout.addWidget(edit_samples_btn)

                delete_btn = QPushButton("Suppr")
                delete_btn.setToolTip("Supprimer la combinaison")
                delete_btn.setMinimumSize(45, 22)
                delete_btn.setMaximumHeight(22)
                delete_btn.setCursor(Qt.PointingHandCursor)
                delete_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: white;
                        border: 1px solid {Theme.PRIMARY_COLOR};
                        border-radius: 3px;
                        font-size: 8pt;
                        font-weight: bold;
                        color: {Theme.PRIMARY_COLOR};
                        padding: 2px 4px;
                    }}
                    QPushButton:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        color: white;
                        border: none;
                    }}
                """)
                delete_btn.clicked.connect(lambda checked, idx=i: self.combination_deleted.emit(idx))
                header_layout.addWidget(delete_btn)

            status_label = QLabel("✓" if is_completed else "○")
            status_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
            status_label.setStyleSheet(f"color: {text_color};")
            header_layout.addWidget(status_label)

            combo_layout.addLayout(header_layout)

            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet(f"background-color: {text_color}; max-height: 1px; opacity: 0.3;")
            combo_layout.addWidget(separator)

            # ✅ AFFICHAGE DES CONTEXTES AVEC CHEMINS COMPLETS
            contexts = combo.get('contexts', [])
            for ctx_idx, ctx in enumerate(contexts):
                ctx_layout = QHBoxLayout()
                ctx_layout.setSpacing(4)
                ctx_layout.setContentsMargins(0, 2, 0, 2)

                # ✅ Utiliser 'display' qui contient maintenant le breadcrumb complet
                display_text = ctx.get('display', 'N/A')
                
                # ✅ Afficher avec numéro et chemin complet
                ctx_label = QLabel(f"{ctx_idx + 1}. {display_text}")
                ctx_label.setFont(QFont("Segoe UI", 8))
                ctx_label.setStyleSheet(f"color: {text_color}; padding-left: 15px;")
                ctx_label.setWordWrap(True)
                ctx_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
                
                # ✅ Tooltip enrichi avec les détails
                ctx_data = ctx.get('data', {})
                tooltip_parts = []
                if 'breadcrumb' in ctx_data and ctx_data['breadcrumb']:
                    tooltip_parts.append(f"📍 {ctx_data['breadcrumb']}")
                if 'description' in ctx_data and ctx_data['description']:
                    tooltip_parts.append(f"📝 {ctx_data['description']}")
                if 'score' in ctx_data:
                    tooltip_parts.append(f"⭐ Score: {ctx_data['score']:.3f}")
                if 'depth' in ctx_data:
                    tooltip_parts.append(f"🔢 Profondeur: {ctx_data['depth']}")
                    
                if tooltip_parts:
                    ctx_label.setToolTip("\n".join(tooltip_parts))
                
                ctx_layout.addWidget(ctx_label, 1)

                # Bouton supprimer contexte (DESIGN ORIGINAL)
                if not is_completed:
                    delete_ctx_btn = QPushButton("X")
                    delete_ctx_btn.setToolTip("Supprimer ce contexte")
                    delete_ctx_btn.setFixedSize(20, 20)
                    delete_ctx_btn.setCursor(Qt.PointingHandCursor)
                    delete_ctx_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent;
                            border: 1px solid transparent;
                            border-radius: 3px;
                            font-size: 8pt;
                            font-weight: bold;
                            color: {Theme.PRIMARY_COLOR};
                            padding: 0px;
                            margin: 0px;
                            min-width: 20px;
                            max-width: 20px;
                            min-height: 20px;
                            max-height: 20px;
                        }}
                        QPushButton:hover {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                            color: white;
                            border: 1px solid {Theme.PRIMARY_COLOR};
                            border-radius: 3px;
                            min-width: 20px;
                            max-width: 20px;
                            min-height: 20px;
                            max-height: 20px;
                        }}
                    """)
                    delete_ctx_btn.clicked.connect(lambda checked, combo_idx=i, ctx_i=ctx_idx: self._delete_context(combo_idx, ctx_i))
                    ctx_layout.addWidget(delete_ctx_btn)

                combo_layout.addLayout(ctx_layout)

            # Bouton ajouter contexte
            if not is_completed:
                add_ctx_btn = QPushButton("+ Contexte")
                add_ctx_btn.setMinimumHeight(30)
                add_ctx_btn.setMaximumHeight(30)
                add_ctx_btn.setMaximumWidth(120)
                add_ctx_btn.setCursor(Qt.PointingHandCursor)
                add_ctx_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: white;
                        border: 1px solid {Theme.PRIMARY_COLOR};
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 9pt;
                        font-weight: bold;
                        color: {Theme.PRIMARY_COLOR};
                        margin-top: 6px;
                    }}
                    QPushButton:hover {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        color: white;
                        border: none;
                    }}
                """)
                add_ctx_btn.clicked.connect(lambda checked, idx=i: self._add_context_to_combo(idx))
                combo_layout.addWidget(add_ctx_btn)

            self.combinations_layout.addWidget(combo_frame)

        self.combinations_layout.addStretch()

    def _delete_context(self, combo_idx, ctx_idx):
        """Supprime un contexte d'une combinaison"""
        if combo_idx < 0 or combo_idx >= len(self.combinations):
            return

        combo = self.combinations[combo_idx]
        contexts = combo.get('contexts', [])

        if ctx_idx < 0 or ctx_idx >= len(contexts):
            return

        # Vérifier qu'il reste au moins 1 contexte
        if len(contexts) <= 1:
            QMessageBox.warning(
                self,
                "Impossible de supprimer",
                "Une combinaison doit avoir au moins 1 contexte.\n"
                "Supprimez plutôt toute la combinaison si nécessaire."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer le contexte:\n\n{contexts[ctx_idx].get('display', 'N/A')} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            contexts.pop(ctx_idx)
            combo['contexts'] = contexts
            self.combination_modified.emit(combo_idx, combo)
            self._update_display()

    def _add_context_to_combo(self, combo_idx):
        """Ouvre l'interface pour ajouter un contexte à une combinaison existante"""
        if combo_idx < 0 or combo_idx >= len(self.combinations):
            return

        # Récupérer le panel parent
        parent_panel = self.parent()
        while parent_panel and not isinstance(parent_panel, DatasetGenerationPanel):
            parent_panel = parent_panel.parent()

        if parent_panel and isinstance(parent_panel, DatasetGenerationPanel):
            # Appeler la méthode qui existe dans le panel
            parent_panel._open_add_context_dialog(combo_idx)

    def _edit_samples(self, combo_idx):
        """Modifie le nombre de samples d'une combinaison"""
        if combo_idx < 0 or combo_idx >= len(self.combinations):
            return

        combo = self.combinations[combo_idx]
        current_samples = combo.get('nb_samples', 1)

        new_samples, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Modifier le nombre de samples",
            f"Nombre de samples pour la combinaison #{combo_idx + 1}:",
            current_samples, 1, 10000
        )

        if ok and new_samples != current_samples:
            combo['nb_samples'] = new_samples
            self.combination_modified.emit(combo_idx, combo)
            self._update_display()

    def _search_in_children(self, children, text_lower, results, typologie, cluster, root, parent, path, full_typologie):
        """Recherche récursive dans les enfants"""
        for child in children:
            child_name = child.get('name', '')
            current_path = path + [child_name]

            if text_lower in child_name.lower():
                # Déterminer le niveau de l'enfant (enfant 1, enfant 2, etc.)
                child_level = len(current_path)
                results.append({
                    'display': f"Label enfant {child_level}: {child_name}",
                    'path': f"{typologie} → {cluster} → {root} → {parent} → {' → '.join(current_path)}",
                    'level': 'child',
                    'typologie': typologie,
                    'taxonomy': cluster,
                    'root': root,
                    'parent': parent,
                    'child_path': current_path,
                    'data': child,
                    'full_typologie': full_typologie
                })

            # Récursion
            self._search_in_children(
                child.get('children', []), text_lower, results,
                typologie, cluster, root, parent, current_path, full_typologie
            )

class AISelectionDialog(QDialog):
    """Dialog pour sélectionner l'IA à utiliser en mode API"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_ai = None
        self._init_ui()
        
    def _init_ui(self):
        """Interface de sélection d'IA"""
        self.setWindowTitle("Sélection de l'IA")
        self.setMinimumSize(450, 300)
        self.setMaximumSize(450, 300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Titre
        title = QLabel("Choisissez l'IA à utiliser")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; padding: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Sélectionnez le modèle d'IA pour la génération du dataset")
        desc.setFont(QFont("Segoe UI", 9))
        desc.setStyleSheet("color: #666; padding: 5px;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Boutons de sélection
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(15)
        
        # Option Gemini
        self.gemini_button = self._create_ai_button(
            "Gemini",
            "Google Gemini - Modèle par défaut\nPerformant et fiable",
            "gemini"
        )
        buttons_layout.addWidget(self.gemini_button)
        
        # Option OSS
        self.oss_button = self._create_ai_button(
            "Modèle Open Source",
            "Llama, Mistral ou autre modèle OSS\nFlexible et personnalisable",
            "oss"
        )
        buttons_layout.addWidget(self.oss_button)
        
        layout.addLayout(buttons_layout)
        layout.addStretch()
        
        # Bouton Annuler
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-size: 10pt;
                font-weight: bold;
                color: #666;
            }
            QPushButton:hover {
                background: #EEEEEE;
                border-color: #CCCCCC;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
    def _create_ai_button(self, title, description, ai_type):
        """Crée un bouton de sélection d'IA"""
        button = QPushButton()
        button.setMinimumHeight(80)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
                text-align: left;
            }}
            QPushButton:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                background: #F8FBFF;
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                border: none;
            }}
        """)
        
        # Layout interne du bouton
        btn_layout = QVBoxLayout(button)
        btn_layout.setSpacing(5)
        
        # Titre
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; background: transparent; border: none;")
        btn_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 8))
        desc_label.setStyleSheet("color: #666; background: transparent; border: none;")
        desc_label.setWordWrap(True)
        btn_layout.addWidget(desc_label)
        
        # Connexion
        button.clicked.connect(lambda: self._select_ai(ai_type))
        
        return button
    
    def _select_ai(self, ai_type):
        """Confirme la sélection et ferme le dialog"""
        self.selected_ai = ai_type
        self.accept()
    
    def get_selected_ai(self):
        """Retourne l'IA sélectionnée"""
        return self.selected_ai

class ContextWeaverComponents:
    """
    Initialise les composants Context Weaver AVANT PyQt5
    ✅ FIXED: Configure ChromaDB pour éviter blocages Windows + PyQt5
    ✅ VectorStore en mode LAZY (pas d'initialisation immédiate)
    """
    
    _instance = None
    
    def __init__(self):
        self.vector_store = None
        self.oss_client = None
        self.dgraph = None
        self.initialized = False
        self._chromadb_configured = False
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _configure_chromadb(self):
        """
        ✅ BLOCAGE POSTHOG ULTRA-COMPLET
        Crée un module Posthog factice qui ne fait RIEN
        """
        if self._chromadb_configured:
            return

        logger.info("🔧 Configuration ChromaDB (blocage Posthog COMPLET)...")

        # ================================================================
        # ÉTAPE 1 : Variables d'environnement
        # ================================================================
        os.environ['ANONYMIZED_TELEMETRY'] = 'False'
        os.environ['CHROMA_TELEMETRY'] = 'False'
        os.environ['POSTHOG_DISABLED'] = '1'

        # ================================================================
        # ÉTAPE 2 : CRÉER UN VRAI MODULE POSTHOG QUI NE FAIT RIEN
        # ================================================================
        import sys

        if 'posthog' not in sys.modules:
            # Créer une vraie classe Posthog
            class PosthogClient:
                """Client Posthog factice"""
                def __init__(self, *args, **kwargs):
                    self.disabled = True
                    self.api_key = None
                    self.host = None
                    self.personal_api_key = None

                def capture(self, *args, **kwargs):
                    pass

                def identify(self, *args, **kwargs):
                    pass

                def alias(self, *args, **kwargs):
                    pass

                def set(self, *args, **kwargs):
                    pass

                def set_once(self, *args, **kwargs):
                    pass

                def group_identify(self, *args, **kwargs):
                    pass

                def feature_enabled(self, *args, **kwargs):
                    return False

                def get_feature_flag(self, *args, **kwargs):
                    return None

                def get_all_flags(self, *args, **kwargs):
                    return {}

                def flush(self):
                    pass

                def shutdown(self):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass
                
            # Créer le module complet
            import types
            posthog_module = types.ModuleType('posthog')

            # Ajouter la classe
            posthog_module.Posthog = PosthogClient

            # Ajouter les fonctions globales
            posthog_module.capture = lambda *args, **kwargs: None
            posthog_module.identify = lambda *args, **kwargs: None
            posthog_module.alias = lambda *args, **kwargs: None
            posthog_module.set = lambda *args, **kwargs: None
            posthog_module.flush = lambda *args, **kwargs: None
            posthog_module.shutdown = lambda *args, **kwargs: None

            # Ajouter les constantes
            posthog_module.disabled = True
            posthog_module.api_key = None
            posthog_module.host = None

            # Injecter dans sys.modules AVANT que ChromaDB l'importe
            sys.modules['posthog'] = posthog_module

            logger.info("   ✅ Module Posthog factice créé et injecté")

        # ================================================================
        # ÉTAPE 3 : Désactiver dans ChromaDB Settings
        # ================================================================
        try:
            import chromadb.config
            chromadb.config.Settings.anonymized_telemetry = False
            logger.info("   ✅ Télémétrie ChromaDB désactivée")
        except Exception as e:
            logger.warning(f"   ⚠️ Impossible de modifier Settings: {e}")

        self._chromadb_configured = True
        logger.info("   ✅ Configuration ChromaDB complète")
    
    def initialize(self):
        """
        ✅ NOUVEAU: VectorStore en mode LAZY
        - Créé mais PAS initialisé
        - Sera initialisé dans le Worker quand nécessaire
        """
        if self.initialized:
            logger.info("✅ Composants déjà initialisés")
            return True
        
        logger.info("=" * 80)
        logger.info("🚀 INITIALISATION COMPOSANTS CONTEXT WEAVER (LAZY MODE)")
        logger.info("=" * 80)
        
        try:
            # ✅ ÉTAPE 0: Configurer ChromaDB
            self._configure_chromadb()
            
            # ================================================================
            # ÉTAPE 1: VectorStore (MODE LAZY - PAS DE CHARGEMENT IMMÉDIAT)
            # ================================================================
            logger.info("\n📦 1/3: Création VectorStore (lazy mode)...")
            from context_weaver.data.vector_store_chroma import VectorStore
            
            chroma_path = Path("./data/indexes/chroma")
            self.vector_store = VectorStore(persist_path=chroma_path)
            
            # ❌ NE PAS APPELER initialize() ICI
            # L'initialisation sera faite dans le Worker
            
            logger.info("   ✅ VectorStore créé (non initialisé - sera fait dans le Worker)")
            
            # ================================================================
            # ÉTAPE 2: OSS Client
            # ================================================================
            logger.info("\n📦 2/3: Initialisation OSS Client...")
            from context_weaver.services.oss_classifier import OSSClassifierClient
            
            self.oss_client = OSSClassifierClient()
            logger.info("   ✅ OSS Client prêt")
            
            # ================================================================
            # ÉTAPE 3: Dgraph (optionnel)
            # ================================================================
            logger.info("\n📦 3/3: Connexion Dgraph...")
            try:
                from utils.dataset_dgraph_connector import TaxonomyDgraphConnector
                self.dgraph = TaxonomyDgraphConnector()
                
                if self.dgraph.client:
                    logger.info("   ✅ Dgraph connecté")
                else:
                    logger.warning("   ⚠️ Dgraph client None")
                    self.dgraph = None
            except Exception as e:
                logger.warning(f"   ⚠️ Dgraph non disponible: {e}")
                self.dgraph = None
            
            # ================================================================
            # Finalisation
            # ================================================================
            self.initialized = True
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ COMPOSANTS CRÉÉS (ChromaDB sera initialisé à la demande)")
            logger.info("=" * 80)
            logger.info(f"   • VectorStore: ✅ (lazy - non initialisé)")
            logger.info(f"   • OSS Client: ✅")
            logger.info(f"   • Dgraph: {'✅' if self.dgraph else '❌'}")
            logger.info("=" * 80 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Erreur initialisation composants: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            self.initialized = False
            self.vector_store = None
            self.oss_client = None
            self.dgraph = None
            
            raise


import time
import logging
from typing import Dict, List, Any, Optional
from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class ContextWeaverWorker(QThread):
    """
    ✅ Worker avec filtrage par SCORE UNIQUEMENT
    VERSION ULTRA-SÉCURISÉE : Aucun crash possible
    ✅ INITIALISE ChromaDB DANS LE THREAD
    """

    # Configuration
    MIN_SCORE_THRESHOLD = 0.10      # ⬇️ Réduit (était 0.20)
    ENABLE_QUALITY_TIERS = True
    HIGH_QUALITY_THRESHOLD = 0.16   # ⬇️ Réduit (était 0.30)
    MEDIUM_QUALITY_THRESHOLD = 0.12 # ⬇️ Réduit (était 0.20)
    
    # Signaux
    progress_updated = pyqtSignal(str)
    generation_completed = pyqtSignal(dict)
    generation_failed = pyqtSignal(str)
    
    def __init__(self, user_context: str, database=None, project_name: str = None, 
                 vector_store=None, oss_client=None, dgraph=None, parent=None):
        super().__init__(parent)
        self.user_context = user_context
        self.database = database
        self.project_name = project_name
        self.pipeline = None
        
        # ✅ Composants pré-initialisés (sauf VectorStore qui sera init ici)
        self.vector_store = vector_store
        self.oss_client = oss_client
        self.dgraph = dgraph
        
        logger.info("=" * 80)
        logger.info("🔧 ContextWeaverWorker INITIALISÉ")
        logger.info("=" * 80)
        logger.info(f"🔍 Context: {len(user_context)} chars")
        logger.info(f"💾 Database: {'✅' if database else '❌'}")
        logger.info(f"📁 Project: {project_name or 'N/A'}")
        logger.info(f"🗄️ VectorStore: {'✅ Pré-créé (sera initialisé dans le thread)' if vector_store else '❌ Sera créé'}")
        logger.info("=" * 80)
    
    def run(self):
        """
        ✅ Exécute le pipeline avec gestion d'erreurs TOTALE
        ✅ UTILISE LE VECTORSTORE PRÉ-INITIALISÉ (pas d'init ici)
        """
        try:
            logger.info("\n" + "=" * 80)
            logger.info("🚀 DÉMARRAGE CONTEXT WEAVER WORKER")
            logger.info("=" * 80)

            self.progress_updated.emit("🔄 Initialisation du Context Weaver...")

            # ================================================================
            # ÉTAPE 1 : VÉRIFIER QUE LE VECTORSTORE EST PRÉ-INITIALISÉ
            # ================================================================
            logger.info("\n📚 ÉTAPE 1/4 : VectorStore")

            if self.vector_store is None:
                error_msg = "❌ VectorStore non fourni au Worker"
                logger.error(error_msg)
                self.generation_failed.emit(error_msg)
                return

            # ✅ VÉRIFIER QUE LA COLLECTION EST ACCESSIBLE (pas d'initialisation)
            try:
                logger.info("   📊 Vérification du VectorStore...")
                self.progress_updated.emit("📚 Vérification du VectorStore...")

                doc_count = self.vector_store.get_document_count()
                logger.info(f"   ✅ VectorStore prêt: {doc_count} documents")

                if doc_count == 0:
                    error_msg = "❌ VectorStore est vide (0 documents)"
                    logger.error(error_msg)
                    self.generation_failed.emit(error_msg)
                    return

            except Exception as e:
                error_msg = f"❌ Erreur accès VectorStore: {str(e)}"
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                self.generation_failed.emit(error_msg)
                return

            # ================================================================
            # ÉTAPE 2 : CRÉER LE PIPELINE OPTIMISÉ
            # ================================================================
            logger.info("\n🧠 ÉTAPE 2/4 : Initialisation du pipeline optimisé")
            self.progress_updated.emit("🧠 Initialisation du pipeline optimisé...")

            try:
                from context_weaver.pipeline.main_pipeline import create_pipeline

                logger.info("🔧 Configuration du pipeline:")
                logger.info(f"   • Project: {self.project_name}")
                logger.info(f"   • VectorStore: PRÉ-INITIALISÉ ({doc_count} docs)")
                logger.info(f"   • Domain filter: ACTIVÉ (Macompta.fr)")
                logger.info(f"   • Query strategy: full_prompt")

                # ✅ CRÉER LE PIPELINE AVEC LE VECTORSTORE PRÉ-INITIALISÉ
                self.pipeline = create_pipeline(
                    project_name=self.project_name,
                    vector_store=self.vector_store,      # ✅ Maintenant accepté
                    oss_client=self.oss_client,          # ✅ Maintenant accepté
                    dgraph_connector=self.dgraph,        # ✅ Maintenant accepté
                    use_domain_filter=True,
                    default_domain="Macompta.fr",
                    query_strategy="full_prompt"
                )

                # Optimisations supplémentaires
                logger.info("🔧 Application des optimisations...")
                self.pipeline.taxonomy_pipeline.retriever.config.enable_query_expansion = False
                self.pipeline.taxonomy_pipeline.retriever.config.enable_bm25_exact_boost = True
                self.pipeline.taxonomy_pipeline.retriever.config.bm25_exact_boost_factor = 2.0

                logger.info("✅ Pipeline configuré avec succès")

            except ImportError as e:
                error_msg = f"❌ Module manquant: {str(e)}\n\nVérifiez que context_weaver est bien installé."
                logger.error(error_msg)
                self.generation_failed.emit(error_msg)
                return

            except Exception as e:
                error_msg = f"❌ Erreur création pipeline: {str(e)}"
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                self.generation_failed.emit(error_msg)
                return

            # ================================================================
            # ÉTAPE 3 : EXÉCUTER LE PIPELINE
            # ================================================================
            logger.info("\n🔍 ÉTAPE 3/4 : Classification sémantique")
            self.progress_updated.emit("🔍 Classification sémantique en cours...")

            try:
                logger.info(f"📝 Contexte utilisateur ({len(self.user_context)} chars):")
                logger.info(f"   {self.user_context[:200]}...")

                result = self.pipeline.run(
                    user_context=self.user_context,
                    top_k=100,
                    domain="Macompta.fr"
                )

                logger.info("✅ Pipeline exécuté avec succès")

            except Exception as e:
                error_msg = f"❌ Erreur exécution pipeline: {str(e)}"
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                self.generation_failed.emit(error_msg)
                return

            # ================================================================
            # ÉTAPE 4 : VÉRIFIER LES RÉSULTATS
            # ================================================================
            logger.info("\n✅ ÉTAPE 4/4 : Vérification des résultats")
            self.progress_updated.emit("✅ Traitement des résultats...")

            try:
                # ✅ VÉRIFICATIONS ROBUSTES
                if not result:
                    raise ValueError("Pipeline n'a retourné aucun résultat (result is None)")

                if not hasattr(result, 'search_results'):
                    raise ValueError("Pipeline result n'a pas d'attribut 'search_results'")

                if not result.search_results:
                    raise ValueError("search_results est None")

                if not hasattr(result.search_results, 'results'):
                    raise ValueError("search_results n'a pas d'attribut 'results'")

                if not result.search_results.results:
                    raise ValueError("Aucun taxon trouvé dans les résultats")

                logger.info(f"✅ {len(result.search_results.results)} résultats trouvés")

            except Exception as e:
                error_msg = f"❌ Résultats pipeline invalides: {str(e)}"
                logger.error(error_msg)
                self.generation_failed.emit(error_msg)
                return

            # ================================================================
            # ÉTAPE 5 : CONVERTIR EN COMBINAISONS
            # ================================================================
            logger.info("\n🔄 Conversion en combinaisons...")
            self.progress_updated.emit("🔄 Génération des combinaisons...")

            try:
                combinations_data = self._convert_to_combinations(result)

                # ✅ VÉRIFICATION FINALE
                if not combinations_data:
                    raise ValueError("Aucune combinaison générée (data is None)")

                if 'error' in combinations_data.get('metadata', {}):
                    error = combinations_data['metadata']['error']
                    raise ValueError(f"Erreur dans conversion: {error}")

                if 'combinations' not in combinations_data:
                    raise ValueError("Format de données invalide (pas de clé 'combinations')")

                if not combinations_data['combinations']:
                    raise ValueError("Liste de combinaisons vide")

                nb_combos = len(combinations_data['combinations'])
                logger.info(f"✅ {nb_combos} combinaison(s) générée(s)")

                # ✅ ÉMETTRE LE SIGNAL DE SUCCÈS
                self.progress_updated.emit(f"✅ Génération terminée! {nb_combos} combinaisons créées")
                self.generation_completed.emit(combinations_data)

            except Exception as e:
                error_msg = f"❌ Erreur conversion résultats: {str(e)}"
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                self.generation_failed.emit(error_msg)
                return

        except Exception as e:
            # ✅ CATCH GLOBAL : CAPTURE TOUT
            error_msg = f"❌ Erreur globale Context Weaver: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            self.generation_failed.emit(error_msg)

        finally:
            # ✅ TOUJOURS FERMER LE PIPELINE
            logger.info("\n🔒 Fermeture du pipeline...")
            if self.pipeline:
                try:
                    self.pipeline.close()
                    logger.info("✅ Pipeline fermé proprement")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur fermeture pipeline: {e}")

            logger.info("=" * 80)
            logger.info("🏁 CONTEXT WEAVER WORKER TERMINÉ")
            logger.info("=" * 80)
    
    def _convert_to_combinations(self, pipeline_output):
        """
        ✅ ULTRA-SÉCURISÉ : Convertit avec filtrage par SCORE UNIQUEMENT
        Ne lève JAMAIS d'exception, retourne toujours un dict valide
        """
        combinations = []
        master_typologie = None

        stats = {
            'pipeline_results': 0,
            'above_threshold': 0,
            'below_threshold': 0,
            'quality_breakdown': {
                'high': 0,
                'medium': 0,
                'low': 0
            },
            'combinations_generated': 0,
            'total_contexts': 0
        }

        try:
            # ✅ VÉRIFICATION : search_results existe
            if not hasattr(pipeline_output, 'search_results'):
                logger.error("❌ pipeline_output n'a pas d'attribut 'search_results'")
                return self._empty_combinations_response("Aucun search_results dans le résultat")
            
            search_results = pipeline_output.search_results.results
            
            if not search_results:
                logger.warning("⚠️ Aucun résultat dans search_results")
                return self._empty_combinations_response("Aucun résultat trouvé")
            
            stats['pipeline_results'] = len(search_results)

            logger.info(f"\n{'='*80}")
            logger.info(f"📊 FILTRAGE PAR SCORE (pas de limite de nombre)")
            logger.info(f"{'='*80}")
            logger.info(f"Résultats bruts: {len(search_results)}")

            # ✅ FILTRAGE PAR SCORE UNIQUEMENT
            pertinent_results = []
            
            for result in search_results:
                try:
                    # ✅ VÉRIFICATION : result a un score
                    if not hasattr(result, 'score'):
                        logger.warning(f"⚠️ Résultat sans score: {result}")
                        continue
                    
                    if result.score >= self.MIN_SCORE_THRESHOLD:
                        pertinent_results.append(result)
                        stats['above_threshold'] += 1
                        
                        # Classifier par qualité
                        if self.ENABLE_QUALITY_TIERS:
                            if result.score >= self.HIGH_QUALITY_THRESHOLD:
                                stats['quality_breakdown']['high'] += 1
                            elif result.score >= self.MEDIUM_QUALITY_THRESHOLD:
                                stats['quality_breakdown']['medium'] += 1
                            else:
                                stats['quality_breakdown']['low'] += 1
                    else:
                        stats['below_threshold'] += 1
                
                except Exception as e:
                    logger.warning(f"⚠️ Erreur traitement résultat: {e}")
                    continue

            logger.info(f"✅ Résultats au-dessus du seuil ({self.MIN_SCORE_THRESHOLD}): {len(pertinent_results)}")
            logger.info(f"❌ Résultats en-dessous du seuil: {stats['below_threshold']}")
            
            if self.ENABLE_QUALITY_TIERS:
                logger.info(f"\n📊 Répartition par qualité:")
                logger.info(f"   • High (≥{self.HIGH_QUALITY_THRESHOLD}): {stats['quality_breakdown']['high']}")
                logger.info(f"   • Medium (≥{self.MEDIUM_QUALITY_THRESHOLD}): {stats['quality_breakdown']['medium']}")
                logger.info(f"   • Low (≥{self.MIN_SCORE_THRESHOLD}): {stats['quality_breakdown']['low']}")

            # ✅ VÉRIFICATION : Il y a des résultats pertinents
            if not pertinent_results:
                logger.warning("⚠️ Aucun résultat au-dessus du seuil")
                return self._empty_combinations_response(
                    f"Aucun résultat avec score ≥ {self.MIN_SCORE_THRESHOLD}"
                )

            # Trier par score décroissant
            pertinent_results.sort(key=lambda x: x.score, reverse=True)
            
            # ✅ OPTION 1 : UNE SEULE COMBINAISON AVEC TOUS LES RÉSULTATS
            if not self.ENABLE_QUALITY_TIERS:
                contexts = self._build_contexts_from_results(pertinent_results)
                
                if contexts:
                    avg_score = sum(c['data']['score'] for c in contexts) / len(contexts)
                    combination = {
                        'contexts': contexts,
                        'nb_samples': 10,
                        'quality_tier': 'all',
                        'avg_score': avg_score,
                        'min_score': min(c['data']['score'] for c in contexts),
                        'max_score': max(c['data']['score'] for c in contexts)
                    }
                    combinations.append(combination)
                    stats['combinations_generated'] = 1
                    stats['total_contexts'] = len(contexts)
                    
                    logger.info(f"\n✅ Combinaison unique créée:")
                    logger.info(f"   • Contextes: {len(contexts)}")
                    logger.info(f"   • Score moyen: {avg_score:.3f}")
                    logger.info(f"   • Score min: {combination['min_score']:.3f}")
                    logger.info(f"   • Score max: {combination['max_score']:.3f}")
            
            # ✅ OPTION 2 : GROUPER PAR QUALITÉ
            else:
                high_quality = [r for r in pertinent_results if r.score >= self.HIGH_QUALITY_THRESHOLD]
                medium_quality = [r for r in pertinent_results if self.MEDIUM_QUALITY_THRESHOLD <= r.score < self.HIGH_QUALITY_THRESHOLD]
                low_quality = [r for r in pertinent_results if self.MIN_SCORE_THRESHOLD <= r.score < self.MEDIUM_QUALITY_THRESHOLD]
                
                for tier_name, tier_results, samples in [
                    ('high', high_quality, 15),
                    ('medium', medium_quality, 10),
                    ('low', low_quality, 5)
                ]:
                    if tier_results:
                        contexts = self._build_contexts_from_results(tier_results)
                        
                        if contexts:
                            avg_score = sum(c['data']['score'] for c in contexts) / len(contexts)
                            combination = {
                                'contexts': contexts,
                                'nb_samples': samples,
                                'quality_tier': tier_name,
                                'avg_score': avg_score,
                                'min_score': min(c['data']['score'] for c in contexts),
                                'max_score': max(c['data']['score'] for c in contexts)
                            }
                            combinations.append(combination)
                            
                            logger.info(f"\n✅ Combinaison '{tier_name}' créée:")
                            logger.info(f"   • Contextes: {len(contexts)}")
                            logger.info(f"   • Samples: {samples}")
                            logger.info(f"   • Score moyen: {avg_score:.3f}")
                            logger.info(f"   • Score range: [{combination['min_score']:.3f}, {combination['max_score']:.3f}]")

            # ✅ Créer la typologie master
            if hasattr(pipeline_output, 'classification'):
                classification = pipeline_output.classification
                master_typologie = {
                    'name': f"Taxonomie {classification.domain}",
                    'taxonomy_clusters': [{
                        'name': classification.domain,
                        'root_labels': []
                    }]
                }

        except Exception as e:
            logger.error(f"❌ Erreur conversion : {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._empty_combinations_response(str(e))

        # ✅ VÉRIFICATION FINALE : Au moins une combinaison
        if not combinations:
            logger.error("❌ Aucune combinaison créée après conversion")
            return self._empty_combinations_response(
                "Impossible de créer des combinaisons à partir des résultats"
            )

        stats['combinations_generated'] = len(combinations)
        stats['total_contexts'] = sum(len(c['contexts']) for c in combinations)

        # ✅ RÉSUMÉ DÉTAILLÉ
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 RÉSUMÉ DE LA CONVERSION (SCORE-BASED)")
        logger.info(f"{'='*80}")
        logger.info(f"   • Résultats pipeline: {stats['pipeline_results']}")
        logger.info(f"   • Au-dessus seuil ({self.MIN_SCORE_THRESHOLD}): {stats['above_threshold']}")
        logger.info(f"   • En-dessous seuil: {stats['below_threshold']}")
        logger.info(f"   • Combinaisons: {stats['combinations_generated']}")
        logger.info(f"   • Total contextes: {stats['total_contexts']}")
        
        if self.ENABLE_QUALITY_TIERS:
            logger.info(f"\n   📊 Qualité:")
            logger.info(f"      • High: {stats['quality_breakdown']['high']}")
            logger.info(f"      • Medium: {stats['quality_breakdown']['medium']}")
            logger.info(f"      • Low: {stats['quality_breakdown']['low']}")
        
        # Log détaillé par combinaison
        for i, combo in enumerate(combinations, 1):
            tier = combo.get('quality_tier', 'unknown')
            avg = combo.get('avg_score', 0.0)
            min_s = combo.get('min_score', 0.0)
            max_s = combo.get('max_score', 0.0)
            logger.info(f"\n   • Combo {i} ({tier}):")
            logger.info(f"      - Contextes: {len(combo['contexts'])}")
            logger.info(f"      - Samples: {combo['nb_samples']}")
            logger.info(f"      - Avg score: {avg:.3f}")
            logger.info(f"      - Range: [{min_s:.3f}, {max_s:.3f}]")
        
        logger.info(f"{'='*80}\n")

        return {
            'master_typologie': master_typologie,
            'combinations': combinations,
            'metadata': {
                'source': 'context_weaver_db',
                'confidence': (
                    getattr(pipeline_output.context_weaver, 'confidence_score', 0.0) 
                    if hasattr(pipeline_output, 'context_weaver') 
                    else 0.0
                ),
                'execution_time_ms': (
                    pipeline_output.execution_time_ms 
                    if hasattr(pipeline_output, 'execution_time_ms') 
                    else 0.0
                ),
                'indexed_from_database': self.database is not None and self.project_name is not None,
                'conversion_stats': stats,
                'configuration': {
                    'min_score_threshold': self.MIN_SCORE_THRESHOLD,
                    'filtering_method': 'score_only',
                    'enable_quality_tiers': self.ENABLE_QUALITY_TIERS,
                    'high_quality_threshold': self.HIGH_QUALITY_THRESHOLD if self.ENABLE_QUALITY_TIERS else None,
                    'medium_quality_threshold': self.MEDIUM_QUALITY_THRESHOLD if self.ENABLE_QUALITY_TIERS else None
                }
            }
        }
    
    def _build_contexts_from_results(self, results: List) -> List[Dict]:
        """
        ✅ ULTRA-SÉCURISÉ : Construit la liste des contextes
        Ne lève jamais d'exception, skip les résultats invalides
        """
        contexts = []
        
        if not results:
            logger.warning("⚠️ Aucun résultat à convertir")
            return contexts
        
        for result in results:
            try:
                # ✅ VÉRIFICATIONS : Tous les attributs nécessaires existent
                if not hasattr(result, 'name'):
                    logger.warning(f"⚠️ Résultat sans 'name': {result}")
                    continue
                
                if not hasattr(result, 'content'):
                    logger.warning(f"⚠️ Résultat sans 'content': {result.name}")
                    continue
                
                if not isinstance(result.content, dict):
                    logger.warning(f"⚠️ content n'est pas un dict: {result.name}")
                    continue
                
                if not hasattr(result, 'score'):
                    logger.warning(f"⚠️ Résultat sans 'score': {result.name}")
                    continue
                
                # ✅ EXTRACTION SÉCURISÉE
                breadcrumb = result.content.get('breadcrumb', result.name)
                display_text = breadcrumb if breadcrumb != result.name else result.name
                
                context = {
                    'level': result.type if hasattr(result, 'type') else 'taxon',
                    'display': display_text,
                    'data': {
                        'name': result.name,
                        'domain': result.domain if hasattr(result, 'domain') else 'Macompta.fr',
                        'type': result.type if hasattr(result, 'type') else 'taxon',
                        'description': result.content.get('description', ''),
                        'breadcrumb': breadcrumb,
                        'score': result.score,
                        'depth': result.content.get('depth', 0)
                    }
                }
                contexts.append(context)
                
            except Exception as e:
                logger.error(f"❌ Erreur conversion résultat '{getattr(result, 'name', 'Unknown')}': {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"✅ {len(contexts)} contextes construits sur {len(results)} résultats")
        
        return contexts
    
    def _empty_combinations_response(self, reason: str) -> Dict:
        """
        ✅ Retourne une réponse vide en cas d'erreur
        Permet de retourner gracieusement au lieu de crasher
        """
        logger.warning(f"⚠️ Génération de réponse vide: {reason}")
        
        return {
            'master_typologie': None,
            'combinations': [],
            'metadata': {
                'error': reason,
                'source': 'context_weaver_error',
                'confidence': 0.0,
                'execution_time_ms': 0.0,
                'indexed_from_database': False,
                'conversion_stats': {
                    'pipeline_results': 0,
                    'above_threshold': 0,
                    'below_threshold': 0,
                    'quality_breakdown': {'high': 0, 'medium': 0, 'low': 0},
                    'combinations_generated': 0,
                    'total_contexts': 0
                },
                'configuration': {
                    'min_score_threshold': self.MIN_SCORE_THRESHOLD,
                    'filtering_method': 'score_only',
                    'enable_quality_tiers': self.ENABLE_QUALITY_TIERS
                }
            }
        }
    
class DatasetGenerationPanel(QWidget):
    """Panel principal de génération de datasets - Layout 3 colonnes"""
    
    generation_started = pyqtSignal(str)  # project_name
    generation_completed = pyqtSignal(str, str)  # project_name, output_path
    generation_failed = pyqtSignal(str, str)  # project_name, error
    
    def __init__(self, parent=None, database=None, project_manager=None):
        super().__init__(parent)
        
        # ⚠️ INITIALISATION DE LA DATABASE ET DU MANAGER
        self.conductor = None
        
        # Initialize database and project_manager
        if database is not None:
            self.database = database
            self.db = database
        else:
            self.db = DatasetDatabase()
            self.database = self.db
            
        if project_manager is not None:
            self.project_manager = project_manager
        else:
            self.project_manager = DatasetProjectManager(self.db)
        
        self.current_project = None
        self.current_project_name = None
        self.current_batch_number = None
        self.current_batch_data = None
        self.combinations = []
        self.current_master_typologie = None
        self.all_project_typologies = []  # ✅ Toutes les typologies du projet
        self.dropdown_svg = get_dropdown_svg_path()
        self.global_vector_store = None

        self.is_browser_mode = True
        self.selected_ai_model = 'gemini'

        self.generation_results = []
        self.generation_metadata = {}
        self.worker = None
        
        # Log d'initialisation
        print("=" * 60)
        print("🚀 INITIALISATION DatasetGenerationPanel")
        print("=" * 60)
        logger.info("🚀 DatasetGenerationPanel initialisé")

        self.primary_color = Theme.PRIMARY_COLOR
        self.secondary_color = Theme.SECONDARY_COLOR
        self.base_height = 800

        self._init_ui()
        self._init_overlay_button()
        self.visualizer.combination_deleted.connect(self._delete_combination)
        self.visualizer.combination_modified.connect(self._handle_combination_modified)
        
        print("✅ UI initialisée")
        logger.info("✅ UI initialisée")
        
        # Charger les projets si la database est disponible
        if self.database:
            self._load_projects()
        logger.info("🔧 Pré-initialisation des composants Context Weaver...")
        try:
            components = ContextWeaverComponents.get_instance()
            components.initialize()
            logger.info("✅ Composants Context Weaver prêts")
        except Exception as e:
            logger.error(f"❌ Erreur pré-initialisation: {e}")

    def set_global_vector_store(self, vector_store):
        """
        ✅ REÇOIT LE VECTORSTORE PRÉ-INITIALISÉ
        """
        self.global_vector_store = vector_store
        
        if vector_store:
            doc_count = vector_store.get_document_count()
            logger.info(f"✅ DatasetGenerationPanel - VectorStore set: {doc_count} docs")
        else:
            logger.warning("⚠️  DatasetGenerationPanel - VectorStore is None")
        
    def _init_ui(self):
        """Initialise l'interface utilisateur - 3 colonnes RESPONSIVE + Panel Latéral"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Container principal (Scroll + Panel)
        h_container = QWidget()
        h_layout = QHBoxLayout(h_container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ✅ UTILISER UN QSPLITTER POUR LES 3 COLONNES RESPONSIVE
        from PyQt5.QtWidgets import QSplitter

        self.columns_splitter = QSplitter(Qt.Horizontal)
        self.columns_splitter.setHandleWidth(1)
        self.columns_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E0E0E0;
            }
            QSplitter::handle:hover {
                background: #4A90E2;
            }
        """)

        # Zone scrollable pour chaque colonne
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === COLONNE GAUCHE (Responsive) ===
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_column = self._create_left_column()
        left_scroll.setWidget(left_column)
        self.columns_splitter.addWidget(left_scroll)

        # === COLONNE CENTRALE (Responsive) ===
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QFrame.NoFrame)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        center_column = self._create_center_column()
        center_scroll.setWidget(center_column)
        self.columns_splitter.addWidget(center_scroll)

        # === COLONNE DROITE (Responsive) ===
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_column = self._create_right_column()
        right_scroll.setWidget(right_column)
        self.columns_splitter.addWidget(right_scroll)

        # ✅ DÉFINIR LES PROPORTIONS INITIALES (25% - 35% - 40%)
        total_width = 1200  # Largeur de référence
        self.columns_splitter.setSizes([
            int(total_width * 0.25),  # Gauche: 25%
            int(total_width * 0.35),  # Centre: 35%
            int(total_width * 0.40)   # Droite: 40%
        ])

        # ✅ DÉFINIR LES LARGEURS MINIMALES POUR ÉVITER L'ÉCRASEMENT
        left_scroll.setMinimumWidth(200)
        center_scroll.setMinimumWidth(250)
        right_scroll.setMinimumWidth(280)

        h_layout.addWidget(self.columns_splitter)

        # === PANNEAU DE SNIPPETS ===
        self.snippets_container = QWidget()
        self.snippets_container.setFixedWidth(0)
        h_layout.addWidget(self.snippets_container)

        main_layout.addWidget(h_container)

        # ✅ BARRE D'ACTIONS EN BAS (sans progress bar)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(20, 10, 20, 20)

        # ❌ PROGRESS BAR SUPPRIMÉE D'ICI - Maintenant dans la colonne 1

        actions = self._create_actions()
        bottom_layout.addWidget(actions)

        main_layout.addWidget(bottom_widget)

    def _create_left_column(self):
        """Crée la colonne gauche - Projet, Configuration RESPONSIVE + Switch Mode + Progress Bar"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # ===== ✅ EN-TÊTE AVEC SWITCH MODE - VERSION ULTRA RESPONSIVE =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        # Titre + Icône (plus compact)
        title_container = QHBoxLayout()
        title_container.setSpacing(6)

        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.database', color='#666').pixmap(20, 20))
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setFixedSize(20, 20)
        title_container.addWidget(title_icon)

        title_label = QLabel("Dataset")
        title_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            color: #333; 
            background-color: transparent;
        """)
        title_label.setAlignment(Qt.AlignVCenter)
        title_container.addWidget(title_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()  # ✅ STRETCH POUR POUSSER LE SWITCH À DROITE

        # ===== BOUTON SWITCH MODE (RESPONSIVE DYNAMIQUE) =====
        self.mode_switch_container = QtWidgets.QWidget()
        # ✅ UNIQUEMENT MIN WIDTH, PAS DE MAX POUR PERMETTRE LA CONTRACTION
        self.mode_switch_container.setMinimumWidth(140)
        self.mode_switch_container.setFixedHeight(36)
        # ✅ POLICY POUR PERMETTRE LE SHRINK
        self.mode_switch_container.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed
        )

        switch_layout = QHBoxLayout(self.mode_switch_container)
        switch_layout.setContentsMargins(3, 3, 3, 3)
        switch_layout.setSpacing(3)

        self.mode_switch_container.setStyleSheet("""
            QWidget {
                background-color: #E8E8E8;
                border-radius: 18px;
            }
        """)

        # Boutons - ✅ TAILLES DYNAMIQUES AVEC MINIMUM
        self.browser_mode_button = QPushButton("Nav. Auto")
        self.api_mode_button = QPushButton("API")

        # ✅ MINIMUM WIDTH AU LIEU DE FIXED SIZE
        self.browser_mode_button.setMinimumWidth(60)
        self.browser_mode_button.setMaximumWidth(100)
        self.browser_mode_button.setFixedHeight(30)

        self.api_mode_button.setMinimumWidth(40)
        self.api_mode_button.setMaximumWidth(60)
        self.api_mode_button.setFixedHeight(30)

        # ✅ POLICY POUR PERMETTRE LE SHRINK
        self.browser_mode_button.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed
        )
        self.api_mode_button.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed
        )

        self.browser_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.api_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.browser_mode_button.clicked.connect(lambda: self._switch_mode(True))
        self.api_mode_button.clicked.connect(lambda: self._switch_mode(False))

        switch_layout.addWidget(self.browser_mode_button)
        switch_layout.addWidget(self.api_mode_button)

        # Appliquer le style initial
        self._update_switch_style()

        header_layout.addWidget(self.mode_switch_container)

        layout.addLayout(header_layout)
        # ===== FIN EN-TÊTE =====

        # Section Projet (code existant inchangé)
        project_section = self._create_project_section()
        layout.addWidget(project_section)

        # Section Configuration (code existant inchangé)
        config_section = self._create_config_section()
        layout.addWidget(config_section)

        # INFO: Affichage des infos du batch sélectionné (code existant inchangé)
        self.batch_info_label = QLabel()
        self.batch_info_label.setWordWrap(True)
        self.batch_info_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        self.batch_info_label.setStyleSheet("""
            QLabel {
                background: #F0F8FF;
                border: 2px solid #4A90E2;
                border-radius: 6px;
                padding: 10px;
                font-size: 9pt;
                color: #333;
            }
        """)
        self.batch_info_label.setVisible(False)
        layout.addWidget(self.batch_info_label)

        layout.addStretch()

        # ✅ BARRE DE PROGRESSION EN BAS DE LA COLONNE 1 (code existant inchangé)
        self.progress_bar = GradientProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(self.progress_bar)

        return column

    def _switch_mode(self, is_browser_mode):
        """Change le mode entre Navigation Auto et Mode API avec sélection d'IA"""
        if self.is_browser_mode == is_browser_mode:
            return

        # Si on passe en mode API, afficher le dialog de sélection
        if not is_browser_mode:
            dialog = AISelectionDialog(self)
            result = dialog.exec_()

            if result == QDialog.Accepted:
                selected_ai = dialog.get_selected_ai()

                if selected_ai:
                    self.is_browser_mode = False
                    self.selected_ai_model = selected_ai  # Stocker le choix
                    self._update_switch_style()

                    # Message de confirmation
                    ai_names = {
                        'gemini': 'Google Gemini',
                        'oss': 'Modèle Open Source'
                    }

                    QMessageBox.information(
                        self,
                        "✅ Mode API activé",
                        f"Mode API activé avec {ai_names.get(selected_ai, selected_ai)}.\n\n"
                        f"Les générations utiliseront ce modèle."
                    )

                    logger.info(f"🔑 Mode API activé avec {selected_ai}")
                else:
                    # Pas de sélection, annuler le changement
                    return
            else:
                # Dialog annulé, rester en mode Navigation Auto
                return
        else:
            # Retour au mode Navigation Auto
            self.is_browser_mode = True
            self.selected_ai_model = None
            self._update_switch_style()

            QMessageBox.information(
                self,
                "Mode changé",
                "✅ Mode Navigation Automatique activé\n\n"
                "Cette fonctionnalité sera implémentée prochainement."
            )

            logger.info("🌐 Mode Navigation Auto activé")

    def _update_switch_style(self):
        """Met à jour le style visuel du switch selon le mode actif"""

        # Style actif : Gradient avec border-radius pour arrondir
        active_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 4px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, 
                    stop:1 {Theme.PRIMARY_COLOR});
            }}
        """

        # Style inactif : Transparent avec arrondi
        inactive_style = """
            QPushButton {
                background-color: transparent;
                color: #333333;
                border: none;
                border-radius: 15px;
                font-weight: 600;
                font-size: 12px;
                padding: 5px 8px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: rgba(200, 200, 200, 0.3);
            }
        """

        if self.is_browser_mode:
            # Navigation Auto actif (par défaut)
            self.browser_mode_button.setStyleSheet(active_style)
            self.api_mode_button.setStyleSheet(inactive_style)
        else:
            # Mode API actif
            self.browser_mode_button.setStyleSheet(inactive_style)
            self.api_mode_button.setStyleSheet(active_style)
        
    def _create_center_column(self):
        """Crée la colonne centrale - Éditeur de Prompt RESPONSIVE + Bouton Combinaisons"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
    
        # === EXPLICATION DE STRUCTURE (Collapsible) - MAINTENANT EN HAUT AVEC DÉGRADÉ ===
        self.structure_section = CollapsibleSection("Explication de Structure")
        self.structure_section.set_light_style()
        self.structure_section.is_collapsed = True
        self.structure_section.content.setVisible(False)
        self.structure_section.content.setMaximumHeight(0)
    
        structure_info = QLabel("ℹ️ Description du contexte et de la structure taxonomique")
        structure_info.setFont(QFont("Segoe UI", 8))
        structure_info.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        structure_info.setWordWrap(True)
        self.structure_section.add_widget(structure_info)
    
        # Éditeur explication structure
        self.structure_explanation_editor = QTextEdit()
        self.structure_explanation_editor.setPlaceholderText(
            "Décrivez la structure taxonomique utilisée...\n\n"
            "Cette explication sera ajoutée au prompt envoyé à l'IA."
        )
    
        # Texte par défaut (non pré-rempli, juste stocké)
        default_structure_text = """Voici la description de contexte:
    Nous avons créé un environnement basé sur des arbres taxonomiques de clusters et de labels,
    comprenant plusieurs niveaux hiérarchiques correspondant à la classification des données.
    Chaque label représente une structure taxonomique, utilisée pour classifier les inputs des utilisateurs et produire les outputs associés.
    Ta tâche est de générer un dataset complet comme si tu étais à la place de l'utilisateur :
    Crée des inputs réalistes correspondant aux différents labels que tu reçois.
    Fournis pour chaque input le label complet (tous les niveaux de la hiérarchie).
    Fournis également l'output correspondant à cet input selon la classification.
    Le résultat doit permettre de relier de manière cohérente chaque input utilisateur à son label et à l'output associé,
    en respectant la structure hiérarchique des labels.
    Classification de donnée d'un environnement de logiciel SaaS comptable. Le but est de déterminer toutes les typologies de contexte,
    de les trier et de les structurer correctement. Le dataset est pour fine tuner un agent qui s'appelle Emma et qui connaît parfaitement la comptabilité et le logiciel comptable."""
    
        # ✅ INSÉRER LE TEXTE PAR DÉFAUT
        self.structure_explanation_editor.setPlainText(default_structure_text)
    
        self.structure_explanation_editor.setMinimumHeight(150)
        self.structure_explanation_editor.setMaximumHeight(300)
        self.structure_explanation_editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        self.structure_explanation_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid
            }}
            QTextEdit:disabled {{
                background: #F5F5F5;
                color: #666666;
                border: 2px solid #CCCCCC;
            }}
        """)
    
        self.structure_section.add_widget(self.structure_explanation_editor)
    
        # ✅ LAYOUT HORIZONTAL POUR LES BOUTONS
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.addStretch()
    
        # Bouton Modifier (caché par défaut)
        self.edit_structure_btn = QPushButton("Modifier")
        self.edit_structure_btn.setVisible(False)
        self.edit_structure_btn.setMinimumHeight(32)
        self.edit_structure_btn.setMaximumWidth(120)
        self.edit_structure_btn.setCursor(Qt.PointingHandCursor)
        self.edit_structure_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {Theme.PRIMARY_COLOR};
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 9pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #F0F8FF;
            }}
        """)
        self.edit_structure_btn.clicked.connect(self._edit_structure_explanation)
        buttons_layout.addWidget(self.edit_structure_btn)
    
        # Bouton Enregistrer (visible par défaut)
        self.save_structure_btn = QPushButton("Enregistrer")
        self.save_structure_btn.setMinimumHeight(32)
        self.save_structure_btn.setMaximumWidth(150)
        self.save_structure_btn.setCursor(Qt.PointingHandCursor)
        self.save_structure_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 9pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
        """)
        self.save_structure_btn.clicked.connect(self._save_structure_explanation)
        buttons_layout.addWidget(self.save_structure_btn)
    
        self.structure_section.add_widget(self._create_widget_from_layout(buttons_layout))
    
        # Stocker le texte sauvegardé
        self.saved_structure_text = default_structure_text
        self.structure_is_locked = False
    
        layout.addWidget(self.structure_section)
    
        # === CONTEXTE GLOBAL (Collapsible) - MAINTENANT EN BAS AVEC STYLE GRIS ===
        self.global_section = CollapsibleSection("Contexte Global du Projet")
        self.global_section.set_light_style()  # ✅ Appliquer le style gris clair
    
        global_info = QLabel("ℹ️ Contexte partagé pour tous les batches du projet")
        global_info.setFont(QFont("Segoe UI", 8))
        global_info.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        global_info.setWordWrap(True)
        self.global_section.add_widget(global_info)
    
        self.global_context_editor = QTextEdit()
        self.global_context_editor.setPlaceholderText(
            "Définissez ici le contexte général du projet...\n\n"
            "Exemple:\n"
            "- Objectif du dataset\n"
            "- Domaine d'application\n"
            "- Contraintes générales\n"
            "- Style de sortie attendu"
        )
        self.global_context_editor.setMinimumHeight(100)
        self.global_context_editor.setMaximumHeight(200)
        self.global_context_editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        self.global_context_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        self.global_section.add_widget(self.global_context_editor)
    
        layout.addWidget(self.global_section)
    
        # === CONTEXTE LOCAL ===
        local_header = QWidget()
        local_header_layout = QHBoxLayout(local_header)
        local_header_layout.setContentsMargins(0, 0, 0, 0)
    
        local_title = QLabel("Prompt Local (Batch)")
        local_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        local_title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        local_header_layout.addWidget(local_title)
    
        local_info = QLabel("Instructions spécifiques pour ce batch")
        local_info.setFont(QFont("Segoe UI", 8))
        local_info.setStyleSheet("color: #666; font-style: italic;")
        local_info.setWordWrap(True)
        local_header_layout.addWidget(local_info)
        local_header_layout.addStretch()
    
        layout.addWidget(local_header)
    
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText(
            "Exemple:\n\n"
            "Génère des exemples d'entraînement basés sur les typologies suivantes:\n"
            "{typologie}\n\n"
            "Format attendu: {'input': '...', 'output': '...'}"
        )
        self.prompt_editor.setMinimumHeight(200)
        self.prompt_editor.setMaximumHeight(500)
        self.prompt_editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.prompt_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        layout.addWidget(self.prompt_editor, 1)

        self.context_weaver_section = CollapsibleSection("Génération Automatique")
        self.context_weaver_section.set_light_style()

        cw_info = QLabel(
            "Utilisez Context Weaver pour générer automatiquement des combinaisons "
            "basées sur votre contexte global et local."
        )
        cw_info.setWordWrap(True)
        cw_info.setFont(QFont("Segoe UI", 9))
        cw_info.setStyleSheet("color: #666; padding: 10px; background: #F0F8FF; border-radius: 4px;")
        self.context_weaver_section.add_widget(cw_info)

        # Bouton de génération
        self.generate_combinations_btn = GradientButton("Générer avec Context Weaver")
        self.generate_combinations_btn.setMinimumHeight(50)
        self.generate_combinations_btn.setEnabled(False)  # Désactivé par défaut
        self.generate_combinations_btn.clicked.connect(self._on_generate_with_context_weaver)
        self.context_weaver_section.add_widget(self.generate_combinations_btn)

        # Barre de progression Context Weaver
        self.cw_progress_bar = GradientProgressBar()
        self.cw_progress_bar.setVisible(False)
        self.cw_progress_bar.setMinimumHeight(30)
        self.context_weaver_section.add_widget(self.cw_progress_bar)

        layout.addWidget(self.context_weaver_section)

        self.global_context_editor.textChanged.connect(self._check_context_weaver_ready)
        self.prompt_editor.textChanged.connect(self._check_context_weaver_ready)
    
        return column
    
    def _check_context_weaver_ready(self):
        """
        Active le bouton Context Weaver si:
        - Contexte global OU local rempli
        (Peut générer même s'il y a déjà des combinaisons)
        """
        has_global_context = bool(self.global_context_editor.toPlainText().strip())
        has_local_context = bool(self.prompt_editor.toPlainText().strip())

        # ✅ Activer dès qu'il y a au moins un contexte rempli
        can_generate = has_global_context or has_local_context

        self.generate_combinations_btn.setEnabled(can_generate)

        # Mettre à jour le texte du bouton
        if not can_generate:
            self.generate_combinations_btn.setText("🔍 Contexte requis")
            self.generate_combinations_btn.setToolTip(
                "Remplissez le contexte global ou local pour générer"
            )
        else:
            self.generate_combinations_btn.setText("🧠 Générer avec Context Weaver")
            self.generate_combinations_btn.setToolTip(
                "Cliquez pour générer automatiquement des combinaisons"
            )
    

    def _on_generate_with_context_weaver(self):
        """Lance la génération automatique via Context Weaver"""

        # Vérifications
        if not self.current_project_name or not self.current_batch_number:
            QMessageBox.warning(
                self,
                "Projet requis",
                "Veuillez d'abord sélectionner un projet et un batch."
            )
            return

        # ✅ VÉRIFIER QUE LE VECTORSTORE EST DISPONIBLE
        if not self.global_vector_store:
            QMessageBox.critical(
                self,
                "❌ VectorStore non disponible",
                "Le VectorStore n'a pas été initialisé.\n\n"
                "Veuillez redémarrer l'application pour corriger ce problème."
            )
            return

        # ✅ VÉRIFIER QUE LE VECTORSTORE EST ACCESSIBLE
        try:
            doc_count = self.global_vector_store.get_document_count()

            if doc_count == 0:
                QMessageBox.warning(
                    self,
                    "⚠️ VectorStore vide",
                    "Le VectorStore ne contient aucun document.\n\n"
                    "Veuillez charger des données avant de générer."
                )
                return

            logger.info(f"✅ VectorStore prêt: {doc_count} documents")

        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Erreur VectorStore",
                f"Impossible d'accéder au VectorStore:\n\n{str(e)}"
            )
            return

        # ✅ DEMANDER CONFIRMATION SI DES COMBINAISONS EXISTENT
        if len(self.combinations) > 0:
            reply = QMessageBox.question(
                self,
                "Combinaisons existantes",
                f"<b>⚠️ Attention</b><br><br>"
                f"Il y a déjà {len(self.combinations)} combinaison(s) dans ce batch.<br><br>"
                f"<b>Voulez-vous :</b><br>"
                f"• <b>Remplacer</b> toutes les combinaisons existantes par celles générées par Context Weaver ?<br>"
                f"• Ou <b>Annuler</b> et garder les combinaisons actuelles ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                logger.info("❌ Génération Context Weaver annulée par l'utilisateur")
                return

        # ✅ LANCER LE PIPELINE CONTEXT WEAVER
        try:
            # Récupérer le contexte combiné
            global_context = self.global_context_editor.toPlainText().strip()
            local_prompt = self.prompt_editor.toPlainText().strip()

            # Combiner les contextes
            combined_context = ""
            if global_context:
                combined_context += global_context + "\n\n"
            combined_context += local_prompt

            logger.info("🚀 Lancement du Context Weaver Worker...")
            logger.info(f"📝 Contexte: {combined_context[:100]}...")
            logger.info(f"📊 VectorStore: {doc_count} documents disponibles")

            # Désactiver le bouton pendant le traitement
            self.generate_combinations_btn.setEnabled(False)
            self.generate_combinations_btn.setText("⏳ Génération en cours...")

            # Afficher la barre de progression
            self.cw_progress_bar.setVisible(True)
            self.cw_progress_bar.setValue(0)
            self.cw_progress_bar.setFormat("🔄 Initialisation...")

            # ✅ CRÉER ET LANCER LE WORKER AVEC LE VECTORSTORE PRÉ-INITIALISÉ
            components = ContextWeaverComponents.get_instance()

            self.cw_worker = ContextWeaverWorker(
                user_context=combined_context,
                database=self.database,
                project_name=self.current_project_name,
                vector_store=self.global_vector_store,  # ✅ PRÉ-INITIALISÉ
                oss_client=components.oss_client,
                dgraph=components.dgraph
            )

            # Connecter les signaux
            self.cw_worker.progress_updated.connect(self._on_cw_progress)
            self.cw_worker.generation_completed.connect(self._on_cw_completed)
            self.cw_worker.generation_failed.connect(self._on_cw_failed)

            # Démarrer
            self.cw_worker.start()

            logger.info("✅ Context Weaver Worker démarré")

        except Exception as e:
            logger.error(f"❌ Erreur lancement Context Weaver: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de lancer Context Weaver:\n\n{str(e)}"
            )

            # Réactiver le bouton
            self.generate_combinations_btn.setEnabled(True)
            self.generate_combinations_btn.setText("🧠 Générer avec Context Weaver")
            self.cw_progress_bar.setVisible(False)

    def _on_cw_progress(self, message: str):
        """Met à jour la progression Context Weaver"""
        self.cw_progress_bar.setFormat(message)
        logger.info(f"Context Weaver: {message}")
    
    def _on_cw_completed(self, result: dict):
        """Traite les résultats du Context Weaver"""
        try:
            self.cw_progress_bar.setVisible(False)
            self.generate_combinations_btn.setEnabled(True)
            self.generate_combinations_btn.setText("🧠 Générer avec Context Weaver")

            # Extraire les données
            master_typologie = result.get('master_typologie')
            combinations = result.get('combinations', [])
            metadata = result.get('metadata', {})

            if not combinations:
                QMessageBox.warning(
                    self,
                    "Aucun résultat",
                    "Context Weaver n'a pas pu générer de combinaisons pertinentes.\n\n"
                    "Essayez de fournir plus de contexte."
                )
                return

            # Sauvegarder dans la base de données
            batch_result = self.database.get_batch(self.current_project_name, self.current_batch_number)
            batch_data = batch_result.get('data', {})

            # Remplacer ou ajouter les combinaisons
            batch_data['combinations'] = combinations
            batch_data['count'] = len(combinations)

            # Ajouter la typologie master si elle n'existe pas
            if not batch_data.get('master_typologie') and master_typologie:
                batch_data['master_typologie'] = master_typologie

            # Ajouter les métadonnées Context Weaver
            batch_data['context_weaver_metadata'] = metadata

            # Sauvegarder
            cursor = self.database.connection.cursor()
            cursor.execute("""
                UPDATE batches 
                SET data = ?
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
                AND batch_number = ?
            """, (json.dumps(batch_data), self.current_project_name, self.current_batch_number))
            self.database.connection.commit()

            logger.info(f"✅ {len(combinations)} combinaisons générées et sauvegardées")

            # Recharger l'affichage
            self._on_batch_changed(self.batch_combo.currentIndex())

            # Message de succès
            QMessageBox.information(
                self,
                "✅ Génération réussie",
                f"<b>Context Weaver a généré {len(combinations)} combinaison(s)</b><br><br>"
                f"Confiance: {metadata.get('confidence', 0):.1%}<br>"
                f"Temps: {metadata.get('execution_time_ms', 0):.0f} ms<br><br>"
                f"Vous pouvez maintenant les modifier ou générer le dataset."
            )

        except Exception as e:
            logger.error(f"❌ Erreur traitement résultats: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de traiter les résultats:\n\n{str(e)}"
            )

    def _on_cw_failed(self, error: str):
        """Gère les erreurs du Context Weaver"""
        self.cw_progress_bar.setVisible(False)
        self.generate_combinations_btn.setEnabled(True)
        self.generate_combinations_btn.setText("🧠 Générer avec Context Weaver")

        logger.error(f"❌ Context Weaver échoué: {error}")

        QMessageBox.critical(
            self,
            "❌ Erreur Context Weaver",
            f"La génération automatique a échoué:\n\n{error}\n\n"
            f"Vérifiez les logs pour plus de détails."
        )
        
    def _handle_combination_modified(self, combo_idx: int, modified_combo: dict):
        """Gère la sauvegarde d'une combinaison modifiée (logique extraite de visualizer)"""
        if not self.current_project_name or not self.current_batch_number:
            logger.warning("⚠️ Pas de projet/batch courant pour la modification")
            return

        try:
            # Récupérer les données actuelles du batch
            batch_result = self.database.get_batch(self.current_project_name, self.current_batch_number)
            if not batch_result:
                raise ValueError("Batch non trouvé en BDD")

            batch_data = batch_result.get('data', {})
            combinations = batch_data.get('combinations', [])

            if combo_idx < 0 or combo_idx >= len(combinations):
                raise IndexError(f"Index de combinaison invalide: {combo_idx}")

            # Mettre à jour la combinaison
            combinations[combo_idx] = {
                'contexts': modified_combo.get('contexts', []),
                'nb_samples': modified_combo.get('nb_samples', 1)
            }

            # Sauvegarder en BDD
            cursor = self.database.connection.cursor()
            cursor.execute("""
                UPDATE batches 
                SET data = ?
                WHERE project_id = (SELECT id FROM projects WHERE name = ?) 
                AND batch_number = ?
            """, (json.dumps(batch_data), self.current_project_name, self.current_batch_number))
            self.database.connection.commit()

            logger.info(f"✅ Combinaison {combo_idx + 1} modifiée et sauvegardée en BDD")

            # Recharger l'affichage (via le batch courant)
            current_index = self.batch_combo.currentIndex()
            self._on_batch_changed(current_index)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la modification de combinaison: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Erreur de Modification", f"Impossible de sauvegarder la modification:\n\n{str(e)}")
    
    def _open_add_context_dialog(self, combo_idx):
        """Ouvre le dialogue pour ajouter un contexte à une combinaison existante"""
        if combo_idx < 0 or combo_idx >= len(self.combinations):
            return
    
        # Créer un dialog pour sélectionner un nouveau contexte
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Ajouter un contexte à la combinaison #{combo_idx + 1}")
        dialog.setMinimumSize(600, 500)
    
        layout = QVBoxLayout(dialog)
    
        # Info
        combo = self.combinations[combo_idx]
        nb_contexts = len(combo.get('contexts', []))
        info = QLabel(
            f"<b>Combinaison #{combo_idx + 1}</b><br>"
            f"Contextes actuels: {nb_contexts}<br>"
            f"Ajoutez un nouveau contexte à cette combinaison"
        )
        info.setStyleSheet("padding: 10px; background: #F0F8FF; border-radius: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)
    
        # Champ de recherche
        search_label = QLabel("Rechercher une taxonomie:")
        search_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(search_label)
    
        search_input = QtWidgets.QLineEdit()
        search_input.setPlaceholderText("Tapez pour rechercher...")
        search_input.setMinimumHeight(32)
        layout.addWidget(search_input)
    
        # Liste des résultats
        results_list = QtWidgets.QListWidget()
        results_list.setMinimumHeight(250)
        layout.addWidget(results_list)
    
        # Fil d'ariane
        breadcrumb = QLabel("Aucune sélection")
        breadcrumb.setStyleSheet(
            "background: #F8F9FA; border: 1px solid #E0E0E0; "
            "border-radius: 4px; padding: 8px; font-size: 8pt;"
        )
        breadcrumb.setWordWrap(True)
        layout.addWidget(breadcrumb)
    
        # Boutons
        buttons = QHBoxLayout()
        buttons.addStretch()
    
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(cancel_btn)
    
        add_btn = QPushButton("Ajouter")
        add_btn.setEnabled(False)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)
        buttons.addWidget(add_btn)
    
        layout.addLayout(buttons)
    
        # Variable pour stocker la sélection
        selected_taxonomy = None
    
        def on_search(text):
            results_list.clear()
            if not text or len(text) < 2:
                return
    
            if not self.all_project_typologies:
                results_list.addItem("⚠️ Aucune typologie disponible")
                return
    
            text_lower = text.lower()
            results = []
    
            # Recherche dans toutes les typologies
            for typologie in self.all_project_typologies:
                if not isinstance(typologie, dict):
                    continue
                
                typologie_name = typologie.get('name', '')
                clusters = typologie.get('taxonomy_clusters', [])
    
                for cluster in clusters:
                    cluster_name = cluster.get('name', '')
    
                    if text_lower in cluster_name.lower():
                        results.append({
                            'display': f"Cluster: {cluster_name}",
                            'path': f"{typologie_name} → {cluster_name}",
                            'level': 'taxonomy',
                            'typologie': typologie_name,
                            'taxonomy': cluster_name,
                            'data': cluster,
                            'full_typologie': typologie
                        })
    
                    # Recherche dans root, parent, children...
                    for root in cluster.get('root_labels', []):
                        root_name = root.get('name', '')
    
                        if text_lower in root_name.lower():
                            results.append({
                                'display': f"Label root: {root_name}",
                                'path': f"{typologie_name} → {cluster_name} → {root_name}",
                                'level': 'root',
                                'typologie': typologie_name,
                                'taxonomy': cluster_name,
                                'root': root_name,
                                'data': root,
                                'full_typologie': typologie
                            })
    
                        for parent in root.get('parent_labels', []):
                            parent_name = parent.get('name', '')
    
                            if text_lower in parent_name.lower():
                                results.append({
                                    'display': f"Label parent: {parent_name}",
                                    'path': f"{typologie_name} → {cluster_name} → {root_name} → {parent_name}",
                                    'level': 'parent',
                                    'typologie': typologie_name,
                                    'taxonomy': cluster_name,
                                    'root': root_name,
                                    'parent': parent_name,
                                    'data': parent,
                                    'full_typologie': typologie
                                })
    
                            # Recherche dans children (récursif)
                            self._search_in_children(
                                parent.get('children', []), text_lower, results,
                                typologie_name, cluster_name, root_name, parent_name, [], typologie
                            )
    
            # Afficher les résultats
            if results:
                for result in results[:15]:
                    item = QtWidgets.QListWidgetItem(result['display'])
                    item.setData(Qt.UserRole, result)
                    item.setToolTip(result['path'])
                    results_list.addItem(item)
            else:
                results_list.addItem("❌ Aucun résultat")
    
        def on_select(item):
            nonlocal selected_taxonomy
            result = item.data(Qt.UserRole)
    
            if not result or isinstance(result, str):
                return
    
            selected_taxonomy = result
            breadcrumb.setText(f"✅ {result['path']}")
            add_btn.setEnabled(True)
    
        def on_add():
            if not selected_taxonomy:
                return

            # Construire le nouveau contexte
            new_context = {
                'level': selected_taxonomy['level'],
                'display': selected_taxonomy['path'],
                'data': self._build_context_data_from_selection(selected_taxonomy)
            }

            # Ajouter à la combinaison
            combo = self.combinations[combo_idx]
            combo['contexts'].append(new_context)

            # ✅ CHANGÉ : Émettre le signal au lieu d'appeler la méthode
            self.visualizer.combination_modified.emit(combo_idx, combo)

            dialog.accept()
    
        # Connexions
        search_input.textChanged.connect(on_search)
        results_list.itemDoubleClicked.connect(on_select)
        add_btn.clicked.connect(on_add)
    
        dialog.exec_()
        
    def _create_right_column(self):
        """Crée la colonne droite - Visualiseur + Gestion des Combinaisons"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # === EN-TÊTE AVEC TITRE ET COMPTEUR ===
        title_layout = QHBoxLayout()
        title = QLabel("Combinaisons à Générer")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        title_layout.addWidget(title)

        self.combo_count_label = QLabel("(0)")
        self.combo_count_label.setFont(QFont("Segoe UI", 10))
        self.combo_count_label.setStyleSheet("color: #666;")
        title_layout.addWidget(self.combo_count_label)
        title_layout.addStretch()

        layout.addLayout(title_layout)

        # === SECTION AJOUT DE COMBINAISON ===
        add_combo_section = self._create_add_combination_section()
        layout.addWidget(add_combo_section)

        # === VISUALISEUR (LISTE DES COMBINAISONS) ===
        self.visualizer = CombinationVisualizer()
        viz_container = QFrame()
        viz_container.setFrameShape(QFrame.StyledPanel)
        viz_container.setStyleSheet("""
            QFrame {
                background: white;
                border: none;
                border-radius: 0px;
            }
        """)
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(0, 0, 0, 0)
        viz_layout.addWidget(self.visualizer)

        layout.addWidget(viz_container, 1)

        return column
    
    def _create_add_combination_section(self):
        """Section pour ajouter une nouvelle combinaison - Design compact et uniforme"""
        section = CollapsibleSection("Ajouter une Combinaison")
        section.set_light_style()  # ✅ Appliquer le style gris clair

        # Formulaire d'ajout
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(5, 5, 5, 5)

        # === CHAMP DE RECHERCHE ===
        search_label = QLabel("Rechercher une taxonomie")
        search_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        search_label.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        form_layout.addWidget(search_label)

        self.taxonomy_search = QtWidgets.QLineEdit()
        self.taxonomy_search.setPlaceholderText("Tapez pour rechercher...")
        self.taxonomy_search.setMinimumHeight(32)
        self.taxonomy_search.textChanged.connect(self._on_taxonomy_search)
        self.taxonomy_search.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 6px 10px;
                background: white;
                font-size: 9pt;
            }}
            QLineEdit:hover {{
                border: 1px solid {Theme.PRIMARY_COLOR};
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                background: #FAFAFA;
            }}
        """)
        form_layout.addWidget(self.taxonomy_search)

        # === LISTE DES RÉSULTATS ===
        self.search_results_list = QtWidgets.QListWidget()
        self.search_results_list.setMaximumHeight(120)
        self.search_results_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background: white;
                font-size: 9pt;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid #F5F5F5;
            }}
            QListWidget::item:hover {{
                background: #F8F9FA;
            }}
            QListWidget::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
        """)
        self.search_results_list.itemDoubleClicked.connect(self._on_taxonomy_selected)
        form_layout.addWidget(self.search_results_list)

        # === FIL D'ARIANE (SÉLECTION ACTUELLE) ===
        breadcrumb_label = QLabel("Sélection actuelle")
        breadcrumb_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        breadcrumb_label.setStyleSheet("color: #666;")
        form_layout.addWidget(breadcrumb_label)

        self.breadcrumb_display = QLabel("Aucune sélection")
        self.breadcrumb_display.setWordWrap(True)
        self.breadcrumb_display.setMinimumHeight(35)
        self.breadcrumb_display.setStyleSheet(f"""
            QLabel {{
                background: #F8F9FA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 8pt;
                color: #666;
            }}
        """)
        form_layout.addWidget(self.breadcrumb_display)

        # === CONTEXTES AJOUTÉS (LISTE TEMPORAIRE) ===
        contexts_label = QLabel("Contextes ajoutés à cette combinaison")
        contexts_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        contexts_label.setStyleSheet("color: #666;")
        form_layout.addWidget(contexts_label)
        
        self.temp_contexts_list = QtWidgets.QListWidget()
        self.temp_contexts_list.setMaximumHeight(80)
        self.temp_contexts_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background: #FAFAFA;
                font-size: 8pt;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #F0F0F0;
            }
        """)
        form_layout.addWidget(self.temp_contexts_list)

        # === BOUTONS D'ACTION CONTEXTES ===
        ctx_buttons_layout = QHBoxLayout()
        
        # Bouton "Ajouter contexte"
        self.add_context_btn = QPushButton("+ Contexte")
        self.add_context_btn.setEnabled(False)
        self.add_context_btn.setFixedHeight(28)
        self.add_context_btn.setMaximumWidth(100)
        self.add_context_btn.setCursor(Qt.PointingHandCursor)
        self.add_context_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)
        self.add_context_btn.clicked.connect(self._add_context_to_temp_list)
        ctx_buttons_layout.addWidget(self.add_context_btn)
        
        # Bouton "Effacer contextes"
        self.clear_contexts_btn = QPushButton("Effacer")
        self.clear_contexts_btn.setEnabled(False)
        self.clear_contexts_btn.setFixedHeight(28)
        self.clear_contexts_btn.setMaximumWidth(80)
        self.clear_contexts_btn.setCursor(Qt.PointingHandCursor)
        self.clear_contexts_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8pt;
                font-weight: bold;
            }
            QPushButton:disabled {
                background: #CCCCCC;
                color: #888888;
            }
        """)
        self.clear_contexts_btn.clicked.connect(self._clear_temp_contexts)
        ctx_buttons_layout.addWidget(self.clear_contexts_btn)
        
        ctx_buttons_layout.addStretch()
        form_layout.addLayout(ctx_buttons_layout)

        # === BOUTON AJOUTER - Layout horizontal pour alignement à droite ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Pousse le bouton à droite
        
        self.add_combo_btn = QPushButton("Sauvegarder")
        self.add_combo_btn.setEnabled(False)
        self.add_combo_btn.setFixedHeight(28)  # Compact
        self.add_combo_btn.setMaximumWidth(180)  # Limite la largeur
        self.add_combo_btn.setCursor(Qt.PointingHandCursor)
        self.add_combo_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 9pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)
        self.add_combo_btn.clicked.connect(self._add_new_combination)
        button_layout.addWidget(self.add_combo_btn)
        
        form_layout.addLayout(button_layout)

        # Info
        info = QLabel("Double-cliquez pour sélectionner, puis '+ Contexte' pour ajouter")
        info.setFont(QFont("Segoe UI", 8))
        info.setStyleSheet("color: #999; font-style: italic;")
        info.setWordWrap(True)
        form_layout.addWidget(info)

        section.add_widget(form_widget)

        # Initialiser les variables de sélection
        self.current_selected_taxonomy = None
        self.temp_contexts = []  # ✅ Liste temporaire des contextes

        return section
    
    def _on_taxonomy_search(self, text):
        """Recherche dans TOUTES les typologies du projet"""
        self.search_results_list.clear()

        if not text or len(text) < 2:
            return

        if not self.current_project_name:
            self.search_results_list.addItem("⚠️ Sélectionnez d'abord un projet")
            return

        if not self.all_project_typologies:
            self.search_results_list.addItem("⚠️ Aucune typologie disponible dans le projet")
            return

        text_lower = text.lower()
        results = []

        # ✅ RECHERCHE DANS TOUTES LES TYPOLOGIES DU PROJET
        for typologie in self.all_project_typologies:
            if not isinstance(typologie, dict):
                continue
                
            typologie_name = typologie.get('name', '')
            clusters = typologie.get('taxonomy_clusters', [])

            for cluster in clusters:
                cluster_name = cluster.get('name', '')

                # Cluster match
                if text_lower in cluster_name.lower():
                    results.append({
                        'display': f"Cluster: {cluster_name}",
                        'path': f"{typologie_name} → {cluster_name}",
                        'level': 'taxonomy',
                        'typologie': typologie_name,
                        'taxonomy': cluster_name,
                        'data': cluster,
                        'full_typologie': typologie
                    })

                # Root labels
                for root in cluster.get('root_labels', []):
                    root_name = root.get('name', '')

                    if text_lower in root_name.lower():
                        results.append({
                            'display': f"Label root: {root_name}",
                            'path': f"{typologie_name} → {cluster_name} → {root_name}",
                            'level': 'root',
                            'typologie': typologie_name,
                            'taxonomy': cluster_name,
                            'root': root_name,
                            'data': root,
                            'full_typologie': typologie
                        })

                    # Parent labels
                    for parent in root.get('parent_labels', []):
                        parent_name = parent.get('name', '')

                        if text_lower in parent_name.lower():
                            results.append({
                                'display': f"Label parent: {parent_name}",
                                'path': f"{typologie_name} → {cluster_name} → {root_name} → {parent_name}",
                                'level': 'parent',
                                'typologie': typologie_name,
                                'taxonomy': cluster_name,
                                'root': root_name,
                                'parent': parent_name,
                                'data': parent,
                                'full_typologie': typologie
                            })

                        # Children
                        children = parent.get('children', [])
                        self._search_in_children(
                            children, text_lower, results,
                            typologie_name, cluster_name, root_name, parent_name, [], typologie
                        )

        # Afficher les résultats (max 15)
        if results:
            for result in results[:15]:
                item = QtWidgets.QListWidgetItem(result['display'])
                item.setData(Qt.UserRole, result)
                
                # Construire le tooltip avec les informations structurées
                tooltip_lines = [f"Typologie de contexte: {result['typologie']}"]
                tooltip_lines.append(f"Cluster: {result['taxonomy']}")
                
                if 'root' in result:
                    tooltip_lines.append(f"Label root: {result['root']}")
                if 'parent' in result:
                    tooltip_lines.append(f"Label parent: {result['parent']}")
                if 'child_path' in result and result['child_path']:
                    for i, child in enumerate(result['child_path'], 1):
                        tooltip_lines.append(f"Label enfant {i}: {child}")
                
                item.setToolTip("\n".join(tooltip_lines))
                self.search_results_list.addItem(item)
        else:
            self.search_results_list.addItem("❌ Aucun résultat")

    def _search_in_children(self, children, text_lower, results, typologie, cluster, root, parent, path, full_typologie):
        """Recherche récursive dans les enfants"""
        for child in children:
            child_name = child.get('name', '')
            current_path = path + [child_name]

            if text_lower in child_name.lower():
                # Déterminer le niveau de l'enfant (enfant 1, enfant 2, etc.)
                child_level = len(current_path)
                results.append({
                    'display': f"Label enfant {child_level}: {child_name}",
                    'path': f"{typologie} → {cluster} → {root} → {parent} → {' → '.join(current_path)}",
                    'level': 'child',
                    'typologie': typologie,
                    'taxonomy': cluster,
                    'root': root,
                    'parent': parent,
                    'child_path': current_path,
                    'data': child,
                    'full_typologie': full_typologie
                })

            # Récursion
            self._search_in_children(
                child.get('children', []), text_lower, results,
                typologie, cluster, root, parent, current_path, full_typologie
            )

    def _create_widget_from_layout(self, layout):
        """Helper pour convertir un layout en widget"""
        widget = QWidget()
        widget.setLayout(layout)
        return widget
    
    def _save_structure_explanation(self):
        """Enregistre et verrouille l'explication de structure"""
        current_text = self.structure_explanation_editor.toPlainText().strip()

        if not current_text:
            QMessageBox.warning(
                self,
                "⚠️ Champ vide",
                "Veuillez saisir une explication de structure avant d'enregistrer."
            )
            return

        self.saved_structure_text = current_text
        self.structure_is_locked = True

        # ✅ VERROUILLER LE CHAMP
        self.structure_explanation_editor.setReadOnly(True)
        self.structure_explanation_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: #F5F5F5;
                color: #666666;
            }}
        """)

        # ✅ INVERSER LES BOUTONS
        self.save_structure_btn.setVisible(False)
        self.edit_structure_btn.setVisible(True)

        QMessageBox.information(
            self,
            "✅ Enregistré",
            "L'explication de structure a été enregistrée et verrouillée.\n"
            "Elle sera incluse dans les prochaines générations.\n\n"
            "Cliquez sur 'Modifier' pour déverrouiller."
        )
        logger.info("✅ Explication de structure enregistrée et verrouillée")

    def _edit_structure_explanation(self):
        """Déverrouille l'explication de structure pour modification"""
        self.structure_is_locked = False

        # ✅ DÉVERROUILLER LE CHAMP
        self.structure_explanation_editor.setReadOnly(False)
        self.structure_explanation_editor.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: white;
            }}
            QTextEdit:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)

        # ✅ INVERSER LES BOUTONS
        self.save_structure_btn.setVisible(True)
        self.edit_structure_btn.setVisible(False)

        # Focus sur le champ pour faciliter l'édition
        self.structure_explanation_editor.setFocus()

        logger.info("✏️ Explication de structure déverrouillée pour modification")

    def _delete_combination(self, index):
        """Supprime une combinaison de la base de données"""
        if index < 0 or index >= len(self.combinations):
            return

        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer la combinaison #{index + 1} ?\n\n"
            "Cette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Récupérer les données actuelles
            batch_result = self.database.get_batch(self.current_project_name, self.current_batch_number)
            batch_data = batch_result.get('data', {})
            combinations = batch_data.get('combinations', [])

            # Supprimer la combinaison
            if index < len(combinations):
                deleted = combinations.pop(index)

                # Mettre à jour le count
                batch_data['count'] = len(combinations)

                # Sauvegarder
                cursor = self.database.connection.cursor()
                cursor.execute("""
                    UPDATE batches 
                    SET data = ?
                    WHERE project_id = (SELECT id FROM projects WHERE name = ?)
                    AND batch_number = ?
                """, (json.dumps(batch_data), self.current_project_name, self.current_batch_number))

                self.database.connection.commit()

                logger.info(f"✅ Combinaison {index + 1} supprimée")

                # Recharger
                self._on_batch_changed(self.batch_combo.currentIndex())

                QMessageBox.information(self, "✅ Suppression", "Combinaison supprimée avec succès!")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            QMessageBox.critical(self, "Erreur", f"Impossible de supprimer:\n\n{str(e)}")

    def _on_taxonomy_selected(self, item):
        """Double-clic sur un résultat"""
        result = item.data(Qt.UserRole)

        if not result or isinstance(result, str):
            return

        # Stocker la sélection
        self.current_selected_taxonomy = result

        # Afficher le fil d'ariane
        self.breadcrumb_display.setText(f"✅ {result['path']}")

        # Activer le bouton "+ Contexte"
        self.add_context_btn.setEnabled(True)

        logger.info(f"✅ Taxonomie sélectionnée: {result['display']}")
    
    def _add_context_to_temp_list(self):
        """Ajoute le contexte sélectionné à la liste temporaire"""
        if not self.current_selected_taxonomy:
            return
        
        # Ajouter à la liste temporaire
        self.temp_contexts.append(self.current_selected_taxonomy)
        
        # Afficher dans la liste
        display_text = f"{len(self.temp_contexts)}. {self.current_selected_taxonomy['path']}"
        self.temp_contexts_list.addItem(display_text)
        
        # Activer les boutons
        self.clear_contexts_btn.setEnabled(True)
        self.add_combo_btn.setEnabled(True)
        
        # Réinitialiser la sélection
        self.current_selected_taxonomy = None
        self.breadcrumb_display.setText("Aucune sélection")
        self.add_context_btn.setEnabled(False)
        self.taxonomy_search.clear()
        
        logger.info(f"✅ Contexte ajouté à la liste temporaire (total: {len(self.temp_contexts)})")
    
    def _clear_temp_contexts(self):
        """Efface la liste temporaire des contextes"""
        self.temp_contexts.clear()
        self.temp_contexts_list.clear()
        self.clear_contexts_btn.setEnabled(False)
        self.add_combo_btn.setEnabled(False)
        logger.info("🗑️ Liste temporaire des contextes effacée")


    def _add_new_combination(self):
        """Ajoute une nouvelle combinaison avec TOUS les contextes de la liste temporaire"""
        if not self.temp_contexts:
            QMessageBox.warning(self, "Attention", "Aucun contexte ajouté")
            return

        if not self.current_batch_number:
            QMessageBox.warning(self, "Attention", "Aucun batch sélectionné")
            return

        try:
            # Récupérer les données actuelles du batch
            batch_result = self.database.get_batch(self.current_project_name, self.current_batch_number)

            if not batch_result:
                QMessageBox.critical(self, "Erreur", "Impossible de charger le batch")
                return

            batch_data = batch_result.get('data', {})
            combinations = batch_data.get('combinations', [])

            # Demander le nombre de samples
            nb_samples, ok = QtWidgets.QInputDialog.getInt(
                self,
                "Nombre de samples",
                f"Combien de samples pour cette combinaison ({len(self.temp_contexts)} contexte(s)) ?",
                1, 1, 1000
            )

            if not ok:
                return

            # ✅ CONSTRUIRE LA NOUVELLE COMBINAISON AVEC TOUS LES CONTEXTES
            contexts_list = []
            for ctx in self.temp_contexts:
                new_context = {
                    'level': ctx['level'],
                    'display': ctx['path'],
                    'data': self._build_context_data_from_selection(ctx)
                }
                contexts_list.append(new_context)

            new_combination = {
                'contexts': contexts_list,
                'nb_samples': nb_samples
            }

            # Ajouter à la liste
            combinations.append(new_combination)

            # Mettre à jour le count
            batch_data['count'] = len(combinations)

            # Sauvegarder dans la base
            batch_result['data'] = batch_data

            cursor = self.database.connection.cursor()
            cursor.execute("""
                UPDATE batches 
                SET data = ?
                WHERE project_id = (SELECT id FROM projects WHERE name = ?)
                AND batch_number = ?
            """, (json.dumps(batch_data), self.current_project_name, self.current_batch_number))

            self.database.connection.commit()

            logger.info(f"✅ Nouvelle combinaison avec {len(contexts_list)} contexte(s) ajoutée au batch {self.current_batch_number}")

            # Recharger le batch pour mettre à jour l'affichage
            self._on_batch_changed(self.batch_combo.currentIndex())

            # Réinitialiser le formulaire
            self._clear_temp_contexts()
            self.taxonomy_search.clear()
            self.breadcrumb_display.setText("Aucune sélection")
            self.current_selected_taxonomy = None

            QMessageBox.information(
                self,
                "✅ Succès",
                f"Combinaison ajoutée avec succès!\n\n"
                f"Contextes: {len(contexts_list)}\n"
                f"Samples: {nb_samples}"
            )

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter la combinaison:\n\n{str(e)}")

    def _build_context_data_from_selection(self, selected):
        """Construit les données du contexte depuis la sélection - UTILISE LA TYPOLOGIE COMPLÈTE"""
        level = selected['level']
        typologie_name = selected['typologie']
        
        # ✅ UTILISER LA TYPOLOGIE COMPLÈTE DE LA SÉLECTION
        typologie = selected.get('full_typologie', {})
        
        if not typologie:
            logger.error("❌ Pas de typologie complète dans la sélection")
            return {}

        if level == 'taxonomy':
            # Retourner le cluster complet
            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == selected['taxonomy']:
                    return {
                        'name': typologie_name,
                        'taxonomy_clusters': [cluster]
                    }

        elif level == 'root':
            # Retourner root + sa hiérarchie
            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == selected['taxonomy']:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == selected['root']:
                            return {
                                'name': typologie_name,
                                'taxonomy_clusters': [{
                                    'name': selected['taxonomy'],
                                    'root_labels': [root]
                                }]
                            }

        elif level == 'parent':
            # Retourner parent + sa hiérarchie
            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == selected['taxonomy']:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == selected['root']:
                            for parent in root.get('parent_labels', []):
                                if parent.get('name') == selected['parent']:
                                    return {
                                        'name': typologie_name,
                                        'taxonomy_clusters': [{
                                            'name': selected['taxonomy'],
                                            'root_labels': [{
                                                'name': selected['root'],
                                                'parent_labels': [parent]
                                            }]
                                        }]
                                    }

        elif level == 'child':
            # Retourner le chemin complet vers l'enfant
            child_path = selected.get('child_path', [])

            for cluster in typologie.get('taxonomy_clusters', []):
                if cluster.get('name') == selected['taxonomy']:
                    for root in cluster.get('root_labels', []):
                        if root.get('name') == selected['root']:
                            for parent in root.get('parent_labels', []):
                                if parent.get('name') == selected['parent']:
                                    # Extraire la hiérarchie enfant
                                    child_hierarchy = self._extract_child_from_path(
                                        parent.get('children', []),
                                        child_path
                                    )

                                    return {
                                        'name': typologie_name,
                                        'taxonomy_clusters': [{
                                            'name': selected['taxonomy'],
                                            'root_labels': [{
                                                'name': selected['root'],
                                                'parent_labels': [{
                                                    'name': selected['parent'],
                                                    'children': child_hierarchy
                                                }]
                                            }]
                                        }]
                                    }

        return {}
    
    def _extract_child_from_path(self, children, target_path):
        """Extrait un enfant spécifique depuis un chemin"""
        if not target_path:
            return children

        target_name = target_path[0]
        remaining_path = target_path[1:]

        for child in children:
            if child.get('name') == target_name:
                if not remaining_path:
                    return [child]
                else:
                    sub_children = self._extract_child_from_path(
                        child.get('children', []),
                        remaining_path
                    )
                    return [{
                        'name': child.get('name'),
                        'description': child.get('description', ''),
                        'category': child.get('category', 'default'),
                        'children': sub_children
                    }]

        return []

    def _create_project_section(self):
        """Crée la section de sélection du projet - RESPONSIVE + REFRESH"""
        widget = QWidget()
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Groupe encadré
        group = QGroupBox("Sélection du Projet")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)

        group_layout = QVBoxLayout(group)

        # ✅ EN-TÊTE AVEC BOUTON REFRESH (UNIQUE)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        header_title = QLabel("Projet:")
        header_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        # ✅ BOUTON REFRESH UNIQUE
        self.refresh_btn = QPushButton()
        try:
            import qtawesome as qta
            self.refresh_btn.setIcon(qta.icon('fa5s.sync-alt', color=Theme.PRIMARY_COLOR))
        except:
            self.refresh_btn.setText("🔄")

        self.refresh_btn.setToolTip("Rafraîchir les données depuis la base")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 16px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                border: none;
            }}
            QPushButton:pressed {{
                background: {Theme.SECONDARY_COLOR};
            }}
        """)
        self.refresh_btn.clicked.connect(self._on_refresh_data)
        header_layout.addWidget(self.refresh_btn)

        group_layout.addLayout(header_layout)

        # ✅ 1. COMBO PROJET
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(40)
        self.project_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self._apply_combo_style(self.project_combo)
        group_layout.addWidget(self.project_combo)

        # ✅ 2. COMBO FAMILLE DE BATCH
        family_label = QLabel("Famille de batch:")
        family_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        family_label.setWordWrap(True)
        group_layout.addWidget(family_label)

        self.batch_family_combo = QComboBox()
        self.batch_family_combo.setMinimumHeight(40)
        self.batch_family_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batch_family_combo.currentTextChanged.connect(self._on_batch_family_changed)
        self._apply_combo_style(self.batch_family_combo)
        group_layout.addWidget(self.batch_family_combo)

        # ✅ 3. COMBO BATCH
        batch_label = QLabel("Batch:")
        batch_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_label.setWordWrap(True)
        group_layout.addWidget(batch_label)

        self.batch_combo = QComboBox()
        self.batch_combo.setMinimumHeight(40)
        self.batch_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self._apply_combo_style(self.batch_combo)
        group_layout.addWidget(self.batch_combo)

        layout.addWidget(group)

        return widget
    
    def _on_refresh_data(self):
        """
        Rafraîchit toutes les données depuis la base de données
        Réinitialise les combos et recharge les projets
        """
        try:
            logger.info("\n" + "="*60)
            logger.info("🔄 RAFRAÎCHISSEMENT DES DONNÉES")
            logger.info("="*60)
            
            # ✅ ANIMATION DU BOUTON
            self.refresh_btn.setEnabled(False)
            
            # Effet de rotation
            try:
                import qtawesome as qta
                self.refresh_btn.setIcon(qta.icon('fa5s.spinner', color=Theme.SECONDARY_COLOR, animation=qta.Spin(self.refresh_btn)))
            except:
                self.refresh_btn.setText("⏳")
            
            # ✅ SAUVEGARDER LES SÉLECTIONS ACTUELLES
            current_project = self.project_combo.currentData()
            current_family = self.batch_family_combo.currentData()
            current_batch = self.batch_combo.currentData()
            
            logger.info(f"   📌 Sélections actuelles:")
            logger.info(f"      • Projet: {current_project}")
            logger.info(f"      • Famille: {current_family}")
            logger.info(f"      • Batch: {current_batch}")
            
            # ✅ RÉINITIALISER TOUS LES COMBOS
            self.project_combo.blockSignals(True)
            self.batch_family_combo.blockSignals(True)
            self.batch_combo.blockSignals(True)
            
            self.project_combo.clear()
            self.batch_family_combo.clear()
            self.batch_combo.clear()
            
            # ✅ RECHARGER LES PROJETS
            if not self.database:
                logger.error("   ❌ Database non initialisée")
                QMessageBox.warning(
                    self,
                    "Erreur",
                    "La base de données n'est pas accessible.\nImpossible de rafraîchir."
                )
                return
            
            logger.info("   📂 Rechargement des projets...")
            projects = self.database.get_all_projects()
            
            if not projects:
                logger.warning("   ⚠️ Aucun projet trouvé")
                self.project_combo.addItem("Aucune", None)
            else:
                logger.info(f"   ✅ {len(projects)} projet(s) trouvé(s)")
                
                self.project_combo.addItem("Projet", None)
                
                for project in projects:
                    if isinstance(project, dict):
                        project_name = project.get('name', project.get('nom', 'Sans nom'))
                        self.project_combo.addItem(project_name, project_name)
                        logger.debug(f"      ✓ {project_name}")
            
            # ✅ RESTAURER LES SÉLECTIONS SI POSSIBLE
            restore_success = False
            
            if current_project:
                index = self.project_combo.findData(current_project)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                    logger.info(f"   ✅ Projet restauré: {current_project}")
                    restore_success = True
                    
                    # Recharger les familles pour ce projet
                    self._load_batch_families()
                    
                    # Restaurer la famille
                    if current_family:
                        family_index = self.batch_family_combo.findData(current_family)
                        if family_index >= 0:
                            self.batch_family_combo.setCurrentIndex(family_index)
                            logger.info(f"   ✅ Famille restaurée: {current_family}")
                            
                            # Recharger les batches
                            self._load_batches_by_family(current_family)
                            
                            # Restaurer le batch
                            if current_batch:
                                batch_index = self.batch_combo.findData(current_batch)
                                if batch_index >= 0:
                                    self.batch_combo.setCurrentIndex(batch_index)
                                    logger.info(f"   ✅ Batch restauré: {current_batch}")
            
            # ✅ RÉACTIVER LES SIGNAUX
            self.project_combo.blockSignals(False)
            self.batch_family_combo.blockSignals(False)
            self.batch_combo.blockSignals(False)
            
            # ✅ MESSAGE DE SUCCÈS (QMESSAGEBOX UNIQUEMENT)
            if restore_success:
                msg = f"✅ Données rafraîchies avec succès!\n\n"
                msg += f"Sélections restaurées:\n"
                msg += f"• Projet: {current_project}\n"
                if current_family:
                    msg += f"• Famille: {current_family}\n"
                if current_batch:
                    msg += f"• Batch: {current_batch}"
            else:
                msg = f"✅ Données rafraîchies avec succès!\n\n"
                msg += f"{len(projects) if projects else 0} projet(s) disponible(s)"
            
            QMessageBox.information(
                self,
                "Rafraîchissement réussi",
                msg
            )
            
            logger.info("="*60)
            logger.info("✅ Rafraîchissement terminé")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du rafraîchissement: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            QMessageBox.critical(
                self,
                "Erreur de rafraîchissement",
                f"Impossible de rafraîchir les données:\n\n{str(e)}"
            )
        
        finally:
            # ✅ RÉACTIVER LE BOUTON
            self.refresh_btn.setEnabled(True)
            try:
                import qtawesome as qta
                self.refresh_btn.setIcon(qta.icon('fa5s.sync-alt', color=Theme.PRIMARY_COLOR))
            except:
                self.refresh_btn.setText("🔄")
        
    def _create_config_section(self):
        """Crée la section de configuration - RESPONSIVE"""
        widget = QWidget()
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Groupe encadré
        group = QGroupBox("Configuration")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)

        group_layout = QVBoxLayout(group)

        # ✅ LINEEDIT NOMBRE DE BATCHES - RESPONSIVE
        batches_label = QLabel("Nombre de batches à traiter:")
        batches_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batches_label.setWordWrap(True)
        group_layout.addWidget(batches_label)

        self.batches_input = QtWidgets.QLineEdit()
        self.batches_input.setPlaceholderText("Nombre de batches...")
        self.batches_input.setText("1")
        self.batches_input.setMinimumHeight(40)
        self.batches_input.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.batches_input.setValidator(QtGui.QIntValidator(1, 100))
        self.batches_input.setAlignment(Qt.AlignCenter)
        self._apply_lineedit_style(self.batches_input)
        group_layout.addWidget(self.batches_input)

        # Info
        info_label = QLabel("ℹ️ Le nombre de samples par combinaison\nest défini dans le batch")
        info_label.setFont(QFont("Segoe UI", 8))
        info_label.setStyleSheet("color: #666; font-style: italic;")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setWordWrap(True)
        group_layout.addWidget(info_label)

        # ✅ COMBO FORMAT - RESPONSIVE
        format_label = QLabel("Format de sortie:")
        format_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        format_label.setWordWrap(True)
        group_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "JSONL", "Parquet"])
        self.format_combo.setMinimumHeight(40)
        self.format_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self._apply_combo_style(self.format_combo)
        group_layout.addWidget(self.format_combo)

        layout.addWidget(group)

        return widget
    
    def _apply_lineedit_style(self, lineedit):
        """Applique le style aux champs de texte"""
        lineedit.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px 15px;
                background: white;
                font-size: 11pt;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QLineEdit:hover {{
                border: 2px solid #E0E0E0;
            }}
            QLineEdit:focus {{
                border: 2px solid #E0E0E0;
                background: white;
            }}
            QLineEdit::placeholder {{
                color: #AAAAAA;
                font-weight: normal;
                font-style: italic;
            }}
        """)
        
    def _create_actions(self):
        """Crée la barre d'actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)

        layout.addStretch()

        # Bouton Générer
        self.generate_btn = GradientButton("Générer le Dataset")
        self.generate_btn.clicked.connect(self._on_generate)
        self.generate_btn.setMinimumWidth(200)
        layout.addWidget(self.generate_btn)

        # Bouton Exporter
        self.export_btn = GradientButton("Exporter")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)

        return widget
        
    def _apply_combo_style(self, combo):
        """Applique le style aux combobox"""
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 35px;
                background: white;
                font-size: 10pt;
            }}
            QComboBox:hover {{
                border: 2px solid #E0E0E0;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #E0E0E0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
            }}
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 18px;
                height: 18px;
            }}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border: none;
                margin: 2px 4px;
                border-radius: 4px;
            }}
        """)
        
    def set_conductor(self, conductor):
        """Définit le conductor"""
        self.conductor = conductor
        logger.info(f"🎼 Conductor défini: {conductor}")
        
    def set_database(self, database):
        """Définit la base de données"""
        logger.info(f"💾 set_database appelé avec: {database}")
        self.database = database
        
        if database is None:
            logger.warning("⚠️ Database est None!")
            return
            
        self._load_projects()
        logger.info("✅ set_database terminé")
        
    def set_project_manager(self, project_manager):
        """Définit le project manager"""
        self.project_manager = project_manager
        logger.info(f"📋 Project Manager défini: {project_manager}")
        
    def _load_projects(self):
        """Charge les projets disponibles"""
        logger.info("📋 _load_projects démarré")
        
        if not self.database:
            logger.error("❌ Database non initialisée")
            return
            
        try:
            projects = self.database.get_all_projects()
            logger.info(f"📦 {len(projects) if projects else 0} projet(s) trouvé(s)")
            
            self.project_combo.clear()
            self.project_combo.addItem("Projet", None)
            
            for project in projects:
                if isinstance(project, dict):
                    project_name = project.get('name', project.get('nom', 'Sans nom'))
                    self.project_combo.addItem(project_name, project_name)
                    logger.debug(f"✓ Projet ajouté: {project_name}")
            
            logger.info(f"✅ {self.project_combo.count() - 1} projet(s) chargé(s)")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des projets: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
    def _on_project_changed(self, project_name):
        """Gère le changement de projet"""
        logger.info(f"🔄 Changement de projet: {project_name}")

        # Reset si sélection vide
        if project_name == "Sélectionner" or not project_name:
            self.current_project = None
            self.current_project_name = None
            self.current_batch_number = None
            self.current_batch_data = None
            self.combinations = []
            self.batch_family_combo.clear()
            self.batch_family_combo.addItem("Aucun projet", None)
            self.batch_combo.clear()
            self.batch_combo.addItem("Aucun projet", None)
            self.batch_info_label.setVisible(False)
            logger.info("Reset de la sélection")
            return

        try:
            self.current_project_name = project_name
            project_data = self.database.get_dataset_projet(project_name)

            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé")
                return

            self.current_project = project_data
            logger.info(f"✅ Projet chargé: {project_name}")

            # ✅ CHARGER LES FAMILLES DE BATCH
            self._load_batch_families()

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _on_batch_changed(self, index):
        """Gère le changement de batch - VERSION AVEC RÉCUPÉRATION SAMPLES"""
        batch_number = self.batch_combo.currentData()
        logger.info(f"🔄 Changement de batch: index={index}, batch_number={batch_number}")

        if batch_number is None:
            self.current_batch_number = None
            self.current_batch_data = None
            self.current_master_typologie = None
            self.combinations = []
            self.batch_info_label.setVisible(False)
            logger.info("Reset des combinaisons")
            return

        try:
            logger.info(f"📂 Chargement du batch {batch_number}")
            batch_result = self.database.get_batch(self.current_project_name, batch_number)

            if not batch_result:
                logger.error(f"❌ Batch {batch_number} non trouvé")
                QMessageBox.warning(
                    self,
                    "Batch introuvable",
                    f"Le batch {batch_number} n'a pas pu être chargé."
                )
                return

            logger.info(f"✅ Batch récupéré")

            # Stocker les données du batch
            self.current_batch_number = batch_number
            self.current_batch_data = batch_result

            # Extraire les données depuis le champ 'data'
            batch_data = batch_result.get('data', {})

            if not batch_data:
                logger.error(f"❌ Le champ 'data' est vide")
                self.combinations = []
                return

            # ✅ EXTRACTION DE LA TYPOLOGIE MASTER COMPLÈTE
            logger.info(f"\n📊 EXTRACTION TYPOLOGIE MASTER")
            master_typologie = batch_data.get('master_typologie', {})

            if master_typologie:
                master_name = master_typologie.get('name', 'N/A')
                clusters = master_typologie.get('taxonomy_clusters', [])

                logger.info(f"  Master: {master_name}")
                logger.info(f"  Clusters: {len(clusters)}")

                # Compter tous les éléments
                total_roots = sum(len(c.get('root_labels', [])) for c in clusters)
                total_parents = sum(
                    len(r.get('parent_labels', []))
                    for c in clusters
                    for r in c.get('root_labels', [])
                )
                total_children = sum(
                    self._count_children_recursive(p.get('children', []))
                    for c in clusters
                    for r in c.get('root_labels', [])
                    for p in r.get('parent_labels', [])
                )

                logger.info(f"  Structure complète:")
                logger.info(f"    • Roots: {total_roots}")
                logger.info(f"    • Parents: {total_parents}")
                logger.info(f"    • Children: {total_children}")

                # Stocker la typologie master complète
                self.current_master_typologie = master_typologie
                logger.info(f"✅ Typologie master complète chargée")
            else:
                logger.warning(f"⚠️ Pas de typologie master dans le batch")
                self.current_master_typologie = None

            # ✅ CHARGER TOUTES LES TYPOLOGIES DU PROJET
            self._load_all_project_typologies()

            # Extraire les informations du batch
            batch_name = batch_data.get('batch_name', 'Sans nom')
            batch_family = batch_data.get('batch_family', '')
            total_batches = batch_result.get('total_batches', 0)
            combinations = batch_data.get('combinations', [])

            if not combinations:
                logger.warning(f"⚠️ Aucune combinaison")
                self.combinations = []
                return

            logger.info(f"\n📊 {len(combinations)} combinaison(s) trouvée(s)")

            # ⭐ CALCUL DU TOTAL DE SAMPLES DEPUIS LA BDD
            total_samples_in_batch = sum(combo.get('nb_samples', 0) for combo in combinations)
            logger.info(f"⭐ Total samples définis dans le batch: {total_samples_in_batch}")

            # Afficher les infos du batch avec samples
            info_text = f"<b>Batch:</b> {batch_name}<br>"
            if batch_family:
                info_text += f"<b>Famille:</b> {batch_family}<br>"
            info_text += f"<b>Numéro:</b> {batch_number}/{total_batches}<br>"
            if master_typologie:
                info_text += f"<b>Master:</b> {master_typologie.get('name', 'N/A')}<br>"
            info_text += f"<b>Combinaisons:</b> {len(combinations)}<br>"
            info_text += f"<b>⭐ Total samples:</b> {total_samples_in_batch}"
            self.batch_info_label.setText(info_text)
            self.batch_info_label.setVisible(True)

            # ✅ Construire l'affichage avec MASTER + CONTEXTES + SAMPLES
            display_combos = []

            for i, combo in enumerate(combinations):
                try:
                    logger.info(f"\n=== Combinaison {i + 1} ===")

                    # Nouveau format : {contexts: [...], nb_samples: N}
                    contexts = combo.get('contexts', [])
                    nb_samples = combo.get('nb_samples', 1)  # ⭐ DEPUIS LA BDD

                    logger.info(f"  Contextes: {len(contexts)}")
                    logger.info(f"  ⭐ Samples (BDD): {nb_samples}")

                    # Créer l'objet d'affichage avec MASTER + SAMPLES
                    display_combo = {
                        'master': master_name if master_typologie else 'N/A',
                        'contexts': [],
                        'nb_samples': nb_samples,  # ⭐ CONSERVÉ DEPUIS LA BDD
                        'master_data': master_typologie
                    }

                    # Extraire chaque contexte
                    for ctx_idx, ctx in enumerate(contexts):
                        level = ctx.get('level', 'unknown')
                        display = ctx.get('display', 'N/A')
                        ctx_data = ctx.get('data', {})

                        logger.debug(f"    Contexte {ctx_idx + 1}: {level} - {display}")

                        display_combo['contexts'].append({
                            'level': level,
                            'display': display,
                            'data': ctx_data
                        })

                    display_combos.append(display_combo)
                    logger.info(f"  ✅ Combinaison {i + 1} traitée")

                except Exception as combo_error:
                    logger.error(f"Erreur combo {i}: {combo_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    display_combos.append({
                        'master': 'Error',
                        'contexts': [{'level': 'error', 'display': 'Erreur de chargement'}],
                        'nb_samples': 1,
                        'master_data': None
                    })

            # Mettre à jour l'affichage
            self.combinations = combinations
            self.visualizer.set_combinations(display_combos)
            self.combo_count_label.setText(f"({len(display_combos)})")

            # ✅ METTRE À JOUR LE CHART AVEC LES VRAIES DONNÉES
            logger.info(f"\n📊 Mise à jour du chart de représentativité")
            logger.info(f"✅ Chart mis à jour avec {len(display_combos)} combinaisons")

            logger.info(f"\n✅ Batch {batch_number} chargé:")
            logger.info(f"  • Master: {master_name if master_typologie else 'N/A'}")
            logger.info(f"  • Combinaisons: {len(combinations)}")
            logger.info(f"  • ⭐ Total samples (BDD): {total_samples_in_batch}")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de charger le batch:\n\n{str(e)}"
            )

    def _count_children_recursive(self, children):
        """Compte récursivement tous les enfants"""
        if not children:
            return 0
        count = len(children)
        for child in children:
            count += self._count_children_recursive(child.get('children', []))
        return count

    def _load_all_project_typologies(self):
        """Charge toutes les typologies du projet depuis la base de données"""
        self.all_project_typologies = []
        
        if not self.current_project_name:
            logger.warning("⚠️ Pas de projet sélectionné")
            return
        
        try:
            # ✅ CHARGER DEPUIS LA BASE DE DONNÉES DIRECTEMENT
            project_data = self.database.get_dataset_projet(self.current_project_name)
            
            if project_data:
                typologies = project_data.get('typologies', [])
                self.all_project_typologies = typologies if isinstance(typologies, list) else []
                logger.info(f"✅ {len(self.all_project_typologies)} typologies chargées du projet")
                
                # Debug : Afficher les noms des typologies
                for typ in self.all_project_typologies:
                    if isinstance(typ, dict):
                        typ_name = typ.get('name', 'Sans nom')
                        clusters_count = len(typ.get('taxonomy_clusters', []))
                        logger.debug(f"  - {typ_name} ({clusters_count} clusters)")
            else:
                logger.warning("⚠️ Pas de données projet")
        except Exception as e:
            logger.error(f"❌ Erreur chargement typologies: {e}")
            import traceback
            logger.error(traceback.format_exc())


    def _on_generate(self):
        """Lance la génération du dataset - VERSION AVEC SÉLECTION API"""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 GÉNÉRATION DATASET - DÉMARRAGE")
        logger.info("=" * 80)
    
        if not self.current_project or not self.combinations:
            QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez d'abord sélectionner un projet et un batch"
            )
            return
    
        # ✅ VÉRIFICATION TYPOLOGIE MASTER
        if not self.current_master_typologie:
            logger.error("❌ Pas de typologie master chargée!")
            QMessageBox.warning(
                self,
                "Attention",
                "La typologie master n'est pas chargée.\n"
                "Impossible de générer le dataset."
            )
            return
    
        # ✅ RÉCUPÉRATION DU NOMBRE DE BATCHES À TRAITER
        try:
            num_batches_to_process = int(self.batches_input.text())
            if num_batches_to_process < 1:
                raise ValueError("Le nombre de batches doit être >= 1")
        except (ValueError, AttributeError) as e:
            logger.error(f"❌ Nombre de batches invalide: {self.batches_input.text()}")
            QMessageBox.warning(
                self,
                "Nombre de batches invalide",
                "Veuillez entrer un nombre entier valide (minimum 1)"
            )
            return
    
        # ⭐ CALCUL DU TOTAL DE SAMPLES
        total_samples_per_batch = sum(combo.get('nb_samples', 0) for combo in self.combinations)
        total_samples_all_batches = total_samples_per_batch * num_batches_to_process
    
        # ✅ RÉCUPÉRATION DES PROMPTS
        global_context = self.global_context_editor.toPlainText().strip()
        structure_explanation = self.saved_structure_text.strip()
        local_prompt = self.prompt_editor.toPlainText().strip()
    
        if not local_prompt:
            QMessageBox.warning(
                self,
                "Prompt manquant",
                "Veuillez définir au moins un prompt local de génération"
            )
            return
    
        # Combiner les contextes avec l'explication de structure
        combined_prompt = ""
        if global_context:
            combined_prompt += f"{global_context}\n\n---\n\n"
            logger.info("✅ Contexte global ajouté")
    
        if structure_explanation:
            combined_prompt += f"{structure_explanation}\n\n---\n\n"
            logger.info("✅ Explication de structure ajoutée")
    
        combined_prompt += local_prompt
        logger.info("✅ Prompt local ajouté")
    
        # 📦 PRÉPARER LA CONFIGURATION POUR LE WORKER
        batch_data = self.current_batch_data.get('data', {})
    
        generation_config = {
            "metadata": {
                "project_name": self.current_project_name,
                "batch_number": self.current_batch_number,
                "batch_name": batch_data.get('batch_name', 'Sans nom'),
                "batch_family": batch_data.get('batch_family', ''),
                "num_batches_to_process": num_batches_to_process,
                "total_samples_per_batch": total_samples_per_batch,
                "total_samples_all_batches": total_samples_all_batches,
                "output_format": self.format_combo.currentText()
            },
            "prompts": {
                "global_context": global_context or None,
                "structure_explanation": structure_explanation or None,
                "local_prompt": local_prompt,
                "combined_prompt": combined_prompt
            },
            "prompt": combined_prompt,
            "master_typologie": {
                "name": self.current_master_typologie.get('name', 'N/A'),
                "full_data": self.current_master_typologie
            },
            "combinations": [],
            "debug_mode": True
        }
    
        # 📋 CONSTRUIRE LES COMBINAISONS COMPLÈTES
        for i, combo in enumerate(self.combinations):
            contexts = combo.get('contexts', [])
            nb_samples = combo.get('nb_samples', 1)
    
            combo_export = {
                "combination_index": i + 1,
                "nb_samples": nb_samples,
                "master": {
                    "name": self.current_master_typologie.get('name', 'N/A'),
                    "full_data": self.current_master_typologie
                },
                "contexts": []
            }
    
            for ctx_idx, ctx in enumerate(contexts):
                ctx_data = ctx.get('data', {})
                context_export = {
                    "level": ctx.get('level', 'unknown'),
                    "display": ctx.get('display', 'N/A'),
                    "full_data": ctx_data
                }
                combo_export["contexts"].append(context_export)
    
            generation_config["combinations"].append(combo_export)
    
        # 📝 EXPORTER LA CONFIGURATION COMPLÈTE
        #config_filepath = self._export_generation_config_to_file(generation_config)
        config_filepath = None
        generation_id = self.database.save_generation_start(generation_config)
    
        if not generation_id:
            logger.error("❌ Impossible d'enregistrer la génération dans l'historique")
            QMessageBox.warning(
                self,
                "Erreur",
                "Impossible d'enregistrer la génération dans l'historique"
            )
            return
    
        logger.info(f"📝 Génération #{generation_id} enregistrée dans l'historique")
        self.current_generation_id = generation_id
    
        # ⭐ DÉTERMINER QUEL MODÈLE UTILISER
        if self.is_browser_mode:
            # Mode Navigation Auto (non implémenté)
            QMessageBox.information(
                self,
                "Mode non disponible",
                "Le mode Navigation Automatique n'est pas encore implémenté.\n\n"
                "Veuillez utiliser le Mode API."
            )
            return
        
        # Mode API : déterminer Gemini ou OSS
        ai_model_name = "Unknown"
        if self.selected_ai_model == 'gemini':
            ai_model_name = "Google Gemini"
            worker_class_name = "GeminiDatasetWorker"
        elif self.selected_ai_model == 'oss':
            ai_model_name = "Modèle Open Source"
            worker_class_name = "OSSDatasetWorker"
        else:
            QMessageBox.warning(
                self,
                "Modèle non sélectionné",
                "Veuillez sélectionner un modèle d'IA via le Mode API"
            )
            return
    
        # ✅ CONFIRMATION
        msg = f"<b>🚀 Prêt à générer le dataset</b><br><br>"
        msg += f"<b>Configuration :</b><br>"
        msg += f"• Projet : {self.current_project_name}<br>"
        msg += f"• Batch : {batch_data.get('batch_name', 'Sans nom')}<br>"
        msg += f"• Master : {self.current_master_typologie.get('name', 'N/A')}<br>"
        msg += f"• Combinaisons : {len(self.combinations)}<br>"
        msg += f"• Batches à traiter : {num_batches_to_process}<br>"
        msg += f"• Samples par batch : {total_samples_per_batch}<br>"
        msg += f"• <b>Total samples : {total_samples_all_batches}</b><br>"
        msg += f"• Format : {self.format_combo.currentText()}<br>"
        msg += f"• <b>🤖 Modèle IA : {ai_model_name}</b><br>"
        #if config_filepath:
        #    msg += f"<br>📝 <b>Config exportée :</b><br><small>{config_filepath}</small><br>"
        msg += f"<br><b>Lancer la génération ?</b>"
    
        reply = QMessageBox.question(
            self,
            "🚀 Confirmer la génération",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
    
        if reply != QMessageBox.Yes:
            logger.info("❌ Génération annulée par l'utilisateur")
            return
    
        # 🎬 LANCER LE WORKER APPROPRIÉ
        try:
            if self.selected_ai_model == 'gemini':
                # 🟢 WORKER GEMINI
                logger.info("🟢 Chargement de GeminiDatasetWorker...")
                from ui.widgets.workers.gemini_dataset_worker import GeminiDatasetWorker
                self.worker = GeminiDatasetWorker(generation_config)
                logger.info("✅ GeminiDatasetWorker initialisé")
                
            elif self.selected_ai_model == 'oss':
                # 🔵 WORKER OSS
                logger.info("🔵 Chargement de OSSDatasetWorker...")
                from ui.widgets.workers.oss_dataset_worker import OSSDatasetWorker
                self.worker = OSSDatasetWorker(generation_config)
                logger.info("✅ OSSDatasetWorker initialisé")
            
            else:
                raise ValueError(f"Modèle IA non reconnu: {self.selected_ai_model}")
    
            # Connecter les signaux (identiques pour les deux workers)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.combination_completed.connect(self._on_combination_completed)
            self.worker.batch_completed.connect(self._on_batch_completed)
            self.worker.generation_completed.connect(self._on_generation_completed)
            self.worker.generation_failed.connect(self._on_generation_failed)
            self.worker.log_message.connect(self._on_log_message)
    
            # Démarrer
            self.worker.start()
    
            # UI : mode génération
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText(f"⏳ Génération en cours ({ai_model_name})...")
            self.export_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(total_samples_all_batches)
    
            logger.info(f"✅ Worker lancé avec succès ({worker_class_name})")
            logger.info(f"🤖 Modèle : {ai_model_name}")
    
        except ImportError as e:
            error_msg = f"❌ Impossible de charger le worker {worker_class_name}\n\n{str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(
                self,
                "Erreur de chargement",
                f"Le module du worker n'a pas pu être chargé:\n\n{str(e)}\n\n"
                f"Vérifiez que le fichier existe:\n"
                f"ui/widgets/workers/{worker_class_name.lower()}.py"
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du lancement: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de lancer la génération:\n\n{str(e)}"
            )
    
    def _load_batch_families(self):
        """Charge les familles de batch du projet actuel"""
        self.batch_family_combo.clear()
        self.batch_family_combo.addItem("famille", None)

        if not self.current_project_name:
            logger.warning("Aucun projet actuel")
            return

        try:
            logger.info(f"🔍 Recherche des familles de batch pour: {self.current_project_name}")
            batches = self.database.get_all_batches(self.current_project_name)

            if not batches or len(batches) == 0:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_family_combo.addItem("Aucune famille", None)
                return

            # Extraire les familles uniques
            families = set()
            for batch in batches:
                batch_data = batch.get('data', {})
                family = batch_data.get('batch_family', '')
                if family:
                    families.add(family)

            if not families:
                logger.info(f"⚠️ Aucune famille définie")
                self.batch_family_combo.addItem("Aucune famille", None)
                return

            # Trier et ajouter les familles
            families_sorted = sorted(list(families))
            logger.info(f"📦 {len(families_sorted)} famille(s) trouvée(s)")

            for family in families_sorted:
                # Compter les batches dans cette famille
                count = sum(1 for b in batches if b.get('data', {}).get('batch_family', '') == family)
                display_name = f"{family} ({count} batch{'es' if count > 1 else ''})"
                self.batch_family_combo.addItem(display_name, family)
                logger.debug(f"  ✓ Famille ajoutée: {display_name}")

            logger.info(f"✅ {len(families_sorted)} famille(s) chargée(s)")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.batch_family_combo.addItem("-- Erreur de chargement --", None)

    def _on_batch_family_changed(self, family_name):
        """Gère le changement de famille de batch - VERSION AVEC CHART UPDATE"""
        family = self.batch_family_combo.currentData()
        logger.info(f"🔄 Changement de famille: {family_name} (data: {family})")

        # Reset des combinaisons
        self.current_batch_number = None
        self.current_batch_data = None
        self.combinations = []
        self.batch_info_label.setVisible(False)

        if family is None:
            self.batch_combo.clear()
            self.batch_combo.addItem("famille", None)
            logger.info("Reset des batches")
            return

        # Charger les batches de cette famille
        self._load_batches_by_family(family)

        # ✅ METTRE À JOUR LE CHART DE REPRÉSENTATIVITÉ
        try:
            all_batches = self.database.get_all_batches(self.current_project_name)
            batches_in_family = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]

            # Préparer les données pour le chart
            chart_data = []
            for batch in batches_in_family:
                batch_num = batch.get('batch_number', 0)
                batch_data_content = batch.get('data', {})
                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                total_samples = sum(c.get('nb_samples', 0) for c in combinations)

                chart_data.append({
                    'batch_number': batch_num,
                    'batch_name': batch_name,
                    'batch_family': family,
                    'combinations_count': len(combinations),
                    'total_samples': total_samples
                })

            logger.info(f"✅ Chart mis à jour avec {len(chart_data)} batches")

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour chart: {str(e)}")

    def _load_batches_by_family(self, family):
        """Charge les batches d'une famille spécifique"""
        self.batch_combo.clear()
        self.batch_combo.addItem("batch", None)

        if not self.current_project_name or not family:
            logger.warning("Projet ou famille manquant")
            return

        try:
            logger.info(f"🔍 Recherche des batches pour famille: {family}")
            all_batches = self.database.get_all_batches(self.current_project_name)

            if not all_batches:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_combo.addItem("Aucun batch", None)
                return

            # Filtrer par famille
            batches = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]

            if not batches:
                logger.info(f"⚠️ Aucun batch dans cette famille")
                self.batch_combo.addItem("Aucun batch", None)
                return

            logger.info(f"📦 {len(batches)} batch(es) trouvé(s) dans {family}")

            # Trier par numéro
            try:
                batches_sorted = sorted(batches, key=lambda x: x.get('batch_number', 0))
            except:
                batches_sorted = batches

            # Ajouter chaque batch
            for batch in batches_sorted:
                batch_num = batch.get('batch_number', 0)
                total_batches = batch.get('total_batches', 0)
                batch_data_content = batch.get('data', {})

                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                combinations_count = len(combinations)

                if total_batches > 0:
                    display_name = f"Batch {batch_num}/{total_batches} - {batch_name} ({combinations_count} combos)"
                else:
                    display_name = f"Batch {batch_num} - {batch_name} ({combinations_count} combos)"

                self.batch_combo.addItem(display_name, batch_num)
                logger.debug(f"  ✓ Batch ajouté: {display_name}")

            logger.info(f"✅ {len(batches)} batch(es) chargé(s)")

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.batch_combo.addItem("-- Erreur de chargement --", None)

    def _on_progress_updated(self, current: int, total: int, message: str):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{message} - {current}/{total} samples ({current*100//total if total > 0 else 0}%)")
        logger.debug(f"📊 Progression: {current}/{total} - {message}")

    def _on_combination_completed(self, combo_idx: int, info: dict):
        """Marque une combinaison comme complétée"""
        samples_generated = info.get('samples_generated', 0)
        logger.info(f"✅ Combinaison {combo_idx + 1} complétée: {samples_generated} samples")

    def _on_batch_completed(self, batch_number: int, results: list):
        """Appelé quand un batch est terminé"""
        logger.info(f"✅ Batch {batch_number} terminé: {len(results)} samples")

    def _on_generation_completed(self, results: list, metadata: dict):
        """Appelé quand toute la génération est terminée"""
        logger.info(f"\n{'=' * 80}")
        logger.info(f"🎉 GÉNÉRATION TERMINÉE")
        logger.info(f"   • Total samples: {len(results)}")
        logger.info(f"{'=' * 80}")

        # Stocker les résultats
        self.generation_results = results
        self.generation_metadata = metadata

        # ✅ METTRE À JOUR L'HISTORIQUE
        if hasattr(self, 'current_generation_id'):
            duration = metadata.get('duration_seconds')
            self.database.update_generation_completion(
                self.current_generation_id,
                output_file_path=None,  # Sera défini lors de l'export
                duration_seconds=duration
            )

        # ✅ AJOUTER AU PANNEAU DATASET
        if self.current_project_name and self.current_batch_number:
            batch_name = metadata.get('batch_name', f'Batch {self.current_batch_number}')
            self._add_to_history(
                project=self.current_project_name,
                batch=batch_name,
                count=len(results)
            )
            
            # Ouvrir automatiquement le panneau si fermé
            if self.snippets_panel.width() == 0:
                self._toggle_snippets_panel()

        # UI : réactiver les boutons
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Générer le Dataset")
        self.export_btn.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())

        # Message de succès
        QMessageBox.information(
            self,
            "✅ Génération terminée",
            f"<b>Dataset généré avec succès !</b><br><br>"
            f"• Total samples: {len(results)}<br>"
            f"• Format: {metadata.get('output_format', 'JSON')}<br><br>"
            f"Utilisez le bouton 'Exporter' pour sauvegarder."
        )

    def _on_generation_failed(self, error: str):
        """Appelé en cas d'erreur"""
        logger.error(f"❌ Génération échouée: {error}")

        # ✅ METTRE À JOUR L'HISTORIQUE AVEC L'ERREUR
        if hasattr(self, 'current_generation_id'):
            self.database.update_generation_completion(
                self.current_generation_id,
                error_message=error
            )

        # UI : réactiver les boutons
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Générer le Dataset")
        self.progress_bar.setVisible(False)

        QMessageBox.critical(
            self,
            "❌ Erreur de génération",
            f"La génération a échoué:\n\n{error}"
        )

    def _on_log_message(self, level: str, message: str):
        """Reçoit les logs du worker"""
        # Optionnel : afficher dans une console de logs dans l'UI
        pass

    def _on_export(self):
        """Exporte le dataset généré avec données nettoyées"""
        if not self.generation_results:
            QMessageBox.warning(
                self,
                "Aucune donnée",
                "Aucun dataset à exporter.\nVeuillez d'abord générer un dataset."
            )
            return

        output_format = self.format_combo.currentText()

        # Extensions
        format_ext = {
            "JSON": ".json",
            "CSV": ".csv",
            "JSONL": ".jsonl",
            "Parquet": ".parquet"
        }

        ext = format_ext.get(output_format, ".json")
        default_filename = f"dataset_{self.current_project_name}_batch{self.current_batch_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "💾 Exporter le dataset",
            default_filename,
            f"Fichiers {output_format} (*{ext})"
        )

        if not filepath:
            logger.info("❌ Export annulé")
            return

        try:
            # Export selon le format
            if output_format == "JSON":
                self._export_json(filepath)
            elif output_format == "JSONL":
                self._export_jsonl(filepath)
            elif output_format == "CSV":
                self._export_csv(filepath)
            elif output_format == "Parquet":
                self._export_parquet(filepath)

            # ✅ METTRE À JOUR L'HISTORIQUE AVEC LE CHEMIN (POUR TOUS LES FORMATS)
            if hasattr(self, 'current_generation_id') and self.current_generation_id:
                cursor = self.database.connection.cursor()
                cursor.execute("""
                    UPDATE dataset_generations 
                    SET output_file_path = ?
                    WHERE id = ?
                """, (filepath, self.current_generation_id))
                self.database.connection.commit()
                logger.info(f"📝 Chemin d'export enregistré dans l'historique: {filepath}")

            logger.info(f"✅ Dataset exporté: {filepath}")

            QMessageBox.information(
                self,
                "✅ Export réussi",
                f"Dataset exporté avec succès vers:\n\n{filepath}\n\n"
                f"Format: {output_format}\n"
                f"Samples: {len(self.generation_results)}"
            )

        except Exception as e:
            logger.error(f"❌ Erreur export: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Erreur d'export",
                f"Impossible d'exporter le dataset:\n\n{str(e)}"
            )

    def _export_json(self, filepath: str):
        """Exporte en JSON avec samples nettoyés"""
        # ✅ Nettoyer les samples
        cleaned_samples = [self._clean_sample_for_export(s) for s in self.generation_results]

        output = {
            "metadata": self.generation_metadata,
            "samples": cleaned_samples
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON exporté: {filepath}")


    def _export_jsonl(self, filepath: str):
        """Exporte en JSONL (une ligne par sample) avec données nettoyées"""
        with open(filepath, 'w', encoding='utf-8') as f:
            for sample in self.generation_results:
                # ✅ Nettoyer chaque sample
                cleaned = self._clean_sample_for_export(sample)
                f.write(json.dumps(cleaned, ensure_ascii=False) + '\n')

        logger.info(f"✅ JSONL exporté: {filepath}")

    def _export_csv(self, filepath: str):
        """
        Exporte en CSV avec données nettoyées
        Format simplifié : sample_id, input, output uniquement
        """
        import csv

        if not self.generation_results:
            return

        fieldnames = ['sample_id', 'input', 'output']

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sample in self.generation_results:
                row = {
                    'sample_id': sample.get('sample_id'),
                    'input': sample.get('input', ''),
                    'output': sample.get('output', '')
                }
                writer.writerow(row)

        logger.info(f"✅ CSV exporté: {filepath}")

    def _clean_sample_for_export(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Nettoie un sample en ne gardant que les champs essentiels
        FORMAT : sample_id, input, output uniquement
        """
        return {
            'sample_id': sample.get('sample_id'),
            'input': sample.get('input', ''),
            'output': sample.get('output', '')
        }

    def _export_parquet(self, filepath: str):
        """
        Exporte en Parquet avec données nettoyées
        Format simplifié : input, output uniquement
        """
        try:
            import pandas as pd
    
            # Aplatir les données
            rows = []
            for sample in self.generation_results:
                row = {
                    'sample_id': sample.get('sample_id'),
                    'input': sample.get('input', ''),
                    'output': sample.get('output', '')
                }
                rows.append(row)
    
            df = pd.DataFrame(rows)
            df.to_parquet(filepath, index=False)
    
            logger.info(f"✅ Parquet exporté: {filepath}")
    
        except ImportError:
            raise Exception(
                "Le module 'pandas' est requis pour exporter en Parquet.\n"
                "Installez-le avec: pip install pandas pyarrow"
            )
        
    def resizeEvent(self, event):
        """Repositionne le bouton toggle et gère le responsive"""
        super().resizeEvent(event)

        # ✅ Repositionner le bouton toggle snippets (code existant)
        if hasattr(self, 'toggle_snippets_button'):
            self.update_button_position()

        # ✅ Ajuster la hauteur du bouton toggle selon la fenêtre (code existant)
        if hasattr(self, 'toggle_snippets_button'):
            button_height = min(200, int(self.height() * 0.20))
            self.toggle_snippets_button.setMaximumHeight(button_height)

        # ✅ Gérer les colonnes splitter (code existant inchangé)
        window_width = self.width()

        if window_width < 800:
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.30),
                    int(window_width * 0.35),
                    int(window_width * 0.35)
                ])
        elif window_width < 1200:
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.27),
                    int(window_width * 0.35),
                    int(window_width * 0.38)
                ])
        else:
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.25),
                    int(window_width * 0.35),
                    int(window_width * 0.40)
                ])

    def _init_overlay_button(self):
        """Initialise le bouton chevron et le panneau latéral (Style Snippet)"""
        
        # Pour simuler la fonction tr() si elle n'existe pas
        def tr(text): return {"generated_code": "Dataset"}.get(text, text)
        
        graph_container = self

        self.toggle_snippets_button = QtWidgets.QWidget(self)
        button_height = min(200, int(self.height() * 0.20))
        self.toggle_snippets_button.setMinimumSize(36, 150)
        self.toggle_snippets_button.setMaximumSize(36, button_height)
        self.toggle_snippets_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_snippets_button.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                border: none;
                border-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QWidget:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """)

        # Layout interne du bouton
        button_layout = QtWidgets.QVBoxLayout(self.toggle_snippets_button)
        button_layout.setContentsMargins(0, 15, 0, 15)
        button_layout.setSpacing(10)
        button_layout.setAlignment(Qt.AlignCenter)

        # Icône chevron
        self.chevron_icon_label = QtWidgets.QLabel()
        self.chevron_icon_label.setAlignment(Qt.AlignCenter)
        try:
            self.chevron_icon_label.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(18, 18))
        except:
            self.chevron_icon_label.setText("<") # Fallback si qtawesome manque

        button_layout.addWidget(self.chevron_icon_label)

        # Texte vertical "DATASET"
        self.toggle_button_text = QtWidgets.QLabel("D\nA\nT\nA\nS\nE\nT")
        self.toggle_button_text.setAlignment(Qt.AlignCenter)
        self.toggle_button_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }
        """)
        button_layout.addWidget(self.toggle_button_text)

        # Rendre le widget cliquable
        self.toggle_snippets_button.mousePressEvent = lambda event: self._toggle_snippets_panel()

        # Position initiale (sera mis à jour par resizeEvent)
        self.toggle_snippets_button.move(self.width() - 40, 80)
        self.toggle_snippets_button.show()

        # ===== PANNEAU DE SNIPPETS =====
        # On utilise self.snippets_container créé dans _init_ui comme hôte
        self.snippets_panel = self.snippets_container
        self.snippets_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.97);
                border-left: 3px solid #D0D0D0;
                border-radius: 0px;
            }
        """)

        snippets_panel_layout = QtWidgets.QVBoxLayout(self.snippets_panel)
        snippets_panel_layout.setContentsMargins(15, 15, 15, 15)
        snippets_panel_layout.setSpacing(10)

        # En-tête du panneau
        snippets_header = QtWidgets.QHBoxLayout()
        snippets_title = QtWidgets.QLabel(f"💻 Dataset généré")
        snippets_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; background-color: transparent; border: none;")
        snippets_header.addWidget(snippets_title)
        snippets_header.addStretch()

        # Bouton Dataset Global
        self.global_history_button = QtWidgets.QPushButton()
        try:
            self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))
        except:
            self.global_history_button.setText("H")
            
        self.global_history_button.setToolTip("Voir le dataset")
        self.global_history_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.global_history_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 6px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        
        # Menu Dataset
        history_menu = QtWidgets.QMenu(self)
        view_current_action = QtWidgets.QAction("📜 Dataset de la session", self)
        view_current_action.triggered.connect(self._toggle_global_history)
        history_menu.addAction(view_current_action)
        self.global_history_button.setMenu(history_menu)
        
        snippets_header.addWidget(self.global_history_button)

        # Badge compteur
        self.snippets_count_badge = QtWidgets.QLabel("0")
        self.snippets_count_badge.setStyleSheet(f"""
            background-color: {self.primary_color};
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        snippets_header.addWidget(self.snippets_count_badge)

        snippets_panel_layout.addLayout(snippets_header)

        # Accordéon Dataset Global (Contenu)
        self.global_history_accordion = QtWidgets.QWidget()
        self.global_history_accordion.setVisible(True) # Toujours visible par défaut pour voir les résultats
        
        global_history_layout = QtWidgets.QVBoxLayout(self.global_history_accordion)
        global_history_layout.setContentsMargins(0, 0, 0, 0)
        
        # Zone scrollable pour la liste des générations passées
        self.history_scroll_area = QScrollArea()
        self.history_scroll_area.setWidgetResizable(True)
        self.history_scroll_area.setFrameShape(QFrame.NoFrame)
        self.history_scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.history_content_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_content_widget)
        self.history_layout.setAlignment(Qt.AlignTop)
        self.history_layout.setSpacing(10)
        
        self.history_scroll_area.setWidget(self.history_content_widget)
        global_history_layout.addWidget(self.history_scroll_area)
        
        snippets_panel_layout.addWidget(self.global_history_accordion)

    def _toggle_snippets_panel(self):
        """Animation d'ouverture/fermeture du panneau latéral"""
        width = self.snippets_panel.width()
        target_width = 350 if width == 0 else 0
        
        # Changer l'icône du chevron
        try:
            icon_name = 'fa5s.chevron-right' if width == 0 else 'fa5s.chevron-left'
            self.chevron_icon_label.setPixmap(qta.icon(icon_name, color='white').pixmap(18, 18))
        except:
            self.chevron_icon_label.setText(">" if width == 0 else "<")

        # Animation du Panel
        self.anim_panel = QPropertyAnimation(self.snippets_panel, b"minimumWidth")
        self.anim_panel.setDuration(300)
        self.anim_panel.setStartValue(width)
        self.anim_panel.setEndValue(target_width)
        self.anim_panel.setEasingCurve(QEasingCurve.InOutQuart)
        
        # Mettre à jour maximumWidth aussi pour forcer le layout
        self.anim_panel.valueChanged.connect(lambda v: self.snippets_panel.setMaximumWidth(v))
        
        # Repositionner le bouton pendant l'animation
        self.anim_panel.valueChanged.connect(lambda: self.update_button_position())
        
        self.anim_panel.start()

    def update_button_position(self):
        """Helper pour resizeEvent et animation"""
        panel_width = self.snippets_panel.width()
        x_pos = self.width() - panel_width - self.toggle_snippets_button.width()
        self.toggle_snippets_button.move(x_pos, 80)

    def _open_sessions_history(self):
        pass # Placeholder

    def _toggle_global_history(self):
        """Affiche/Masque le dataset"""
        # Dans cette implémentation simple, on peut juste s'assurer que le panneau est ouvert
        if self.snippets_panel.width() == 0:
            self._toggle_snippets_panel()

    def _export_generation_config_to_file(self, generation_config: Dict[str, Any]) -> str:
        """
        Exporte la configuration complète de génération dans un fichier JSON
        Retourne le chemin du fichier créé
        """
        try:
            # Créer le dossier de logs s'il n'existe pas
            logs_dir = Path("generation_logs")
            logs_dir.mkdir(exist_ok=True)

            # Nom du fichier avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = generation_config['metadata']['project_name']
            batch_number = generation_config['metadata']['batch_number']
            filename = f"generation_config_{project_name}_batch{batch_number}_{timestamp}.json"
            filepath = logs_dir / filename

            # Préparer les données à exporter (format lisible)
            export_data = {
                "export_info": {
                    "exported_at": datetime.now().isoformat(),
                    "purpose": "Vérification de la configuration de génération avant envoi à Gemini"
                },
                "metadata": generation_config['metadata'],
                "prompts": generation_config['prompts'],
                "master_typologie": {
                    "name": generation_config['master_typologie']['name'],
                    "full_structure": generation_config['master_typologie']['full_data']
                },
                "combinations_details": []
            }

            # Détailler chaque combinaison
            for combo in generation_config['combinations']:
                combo_detail = {
                    "combination_index": combo['combination_index'],
                    "nb_samples": combo['nb_samples'],
                    "master": {
                        "name": combo['master']['name'],
                        "taxonomy_clusters": combo['master']['full_data'].get('taxonomy_clusters', [])
                    },
                    "contexts": []
                }

                for ctx in combo['contexts']:
                    ctx_detail = {
                        "level": ctx['level'],
                        "display": ctx['display'],
                        "taxonomy_clusters": ctx['full_data'].get('taxonomy_clusters', [])
                    }
                    combo_detail['contexts'].append(ctx_detail)

                export_data['combinations_details'].append(combo_detail)

            # Sauvegarder le fichier
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Configuration exportée : {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"❌ Erreur export config : {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return ""

    def _add_to_history(self, project, batch, count):
        """Ajoute une entrée dans le dataset après génération"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #4A90E2;
                background: #F8FBFF;
            }
        """)
        layout = QVBoxLayout(card)
        
        time_str = datetime.now().strftime("%H:%M")
        
        title = QLabel(f"<b>{project}</b>")
        layout.addWidget(title)
        
        info = QLabel(f"Batch {batch} • {count} samples\n🕒 {time_str}")
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)
        
        # Insérer en haut
        self.history_layout.insertWidget(0, card)
        
        # Mettre à jour le badge
        current_count = int(self.snippets_count_badge.text())
        self.snippets_count_badge.setText(str(current_count + 1))