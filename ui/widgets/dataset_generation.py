#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Generation Panel - Improved 3-column layout
Left: Project & Config | Center: Prompt Editor | Right: Combinations Visualizer
"""

import json
import os
from datetime import datetime
from typing import Dict
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QComboBox, QProgressBar, QScrollArea,
    QFrame, QGroupBox, QCheckBox, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush
import sys
from pathlib import Path
from typing import Dict, Any
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager
import qtawesome as qta  # Nécessaire pour les icônes du snippet
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice
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
        self.header.setStyleSheet(f"""
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
        """)
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
    """Widget de visualisation avec Camembert et Liste"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.combinations = []
        self.completed = []
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # === 1. CAMEMBERT (QChart) ===
        self.chart_view = self._create_pie_chart()
        self.chart_view.setMinimumHeight(200)
        self.chart_view.setMaximumHeight(250)
        layout.addWidget(self.chart_view)

        # === 2. LISTE DÉFILANTE ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        self.combinations_widget = QWidget()
        self.combinations_layout = QVBoxLayout(self.combinations_widget)
        self.combinations_layout.setSpacing(8)
        scroll.setWidget(self.combinations_widget)
        
        layout.addWidget(scroll)

    def _create_pie_chart(self):
        """Crée le graphique camembert"""
        self.series = QPieSeries()
        self.series.setHoleSize(0.40) # Style "Donut" moderne
        
        # Données initiales vides
        self.slice_todo = self.series.append("À faire", 1)
        self.slice_done = self.series.append("Terminé", 0)
        
        # Couleurs
        self.slice_todo.setColor(QColor("#E0E0E0"))
        self.slice_todo.setBorderColor(QColor("#E0E0E0"))
        self.slice_done.setColor(QColor(Theme.PRIMARY_COLOR))
        self.slice_done.setBorderColor(QColor(Theme.PRIMARY_COLOR))

        chart = QChart()
        chart.addSeries(self.series)
        chart.setTitle("Progression du Batch")
        chart.setTitleFont(QFont("Segoe UI", 10, QFont.Bold))
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setBackgroundRoundness(0)
        chart.setMargins(QtCore.QMargins(0, 0, 0, 0))
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        
        return chart_view

    def update_chart_data(self):
        """Met à jour les données du camembert"""
        total = len(self.combinations)
        done_count = sum(1 for c in self.completed if c)
        todo_count = total - done_count
        
        if total == 0:
            self.slice_todo.setValue(1)
            self.slice_done.setValue(0)
            self.chart_view.chart().setTitle("Aucune donnée")
        else:
            self.slice_todo.setValue(todo_count)
            self.slice_done.setValue(done_count)
            percentage = int((done_count / total) * 100)
            self.chart_view.chart().setTitle(f"Progression: {percentage}%")

    def set_combinations(self, combinations):
        """Définit les combinaisons à afficher et met à jour le graph"""
        self.combinations = combinations
        self.completed = [False] * len(combinations)
        self.update_chart_data() # Update chart
        self._update_display()
        
    def mark_completed(self, index):
        """Marque une combinaison comme complétée et met à jour le graph"""
        if 0 <= index < len(self.completed):
            self.completed[index] = True
            self.update_chart_data() # Update chart
            self._update_display()
            
    def _update_display(self):
        """Met à jour l'affichage - VERSION AVEC MASTER"""
        while self.combinations_layout.count():
            item = self.combinations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for i, combo in enumerate(self.combinations):
            combo_frame = QFrame()
            combo_frame.setFrameShape(QFrame.StyledPanel)
            
            is_completed = self.completed[i] if i < len(self.completed) else False
            
            if is_completed:
                combo_frame.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                        border-radius: 6px;
                        padding: 10px;
                    }}
                """)
                text_color = "white"
            else:
                combo_frame.setStyleSheet("""
                    QFrame {
                        background: #F5F5F5;
                        border-radius: 6px;
                        padding: 10px;
                    }
                """)
                text_color = "#333333"
            
            combo_layout = QVBoxLayout(combo_frame)
            
            # En-tête : Numéro + Master + Samples
            header_layout = QHBoxLayout()
            
            num_label = QLabel(f"#{i+1}")
            num_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            num_label.setStyleSheet(f"color: {text_color};")
            num_label.setFixedWidth(40)
            header_layout.addWidget(num_label)
            
            # ✅ AFFICHAGE DU MASTER
            master_name = combo.get('master', 'N/A')
            master_label = QLabel(f"Master: {master_name}")
            master_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            master_label.setStyleSheet(f"color: {text_color}; text-decoration: underline;")
            header_layout.addWidget(master_label)
            
            header_layout.addStretch()
            
            # Nombre de contextes et samples
            nb_contexts = len(combo.get('contexts', []))
            nb_samples = combo.get('nb_samples', 1)
            
            info_label = QLabel(f"{nb_contexts} contexte(s) • {nb_samples} sample(s)")
            info_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
            info_label.setStyleSheet(f"color: {text_color};")
            header_layout.addWidget(info_label)
            
            # Icône de statut
            status_label = QLabel("✓" if is_completed else "○")
            status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            status_label.setStyleSheet(f"color: {text_color};")
            header_layout.addWidget(status_label)
            
            combo_layout.addLayout(header_layout)
            
            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet(f"background-color: {text_color}; max-height: 1px;")
            combo_layout.addWidget(separator)
            
            # Liste des contextes
            contexts = combo.get('contexts', [])
            for ctx_idx, ctx in enumerate(contexts):
                ctx_label = QLabel(f"  {ctx_idx + 1}. {ctx.get('display', 'N/A')}")
                ctx_label.setFont(QFont("Segoe UI", 8))
                ctx_label.setStyleSheet(f"color: {text_color}; padding-left: 20px;")
                ctx_label.setWordWrap(True)
                combo_layout.addWidget(ctx_label)
            
            self.combinations_layout.addWidget(combo_frame)
        
        self.combinations_layout.addStretch()

class BatchRepresentativityChart(QWidget):
    """
    Widget de visualisation de la représentativité des batches
    Style et logique alignés avec ContextClusterAnalysisTab
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.combinations_data = []  # Liste des combinaisons du batch
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # === TITRE ===
        title = QLabel("Distribution des Typologies de Contexte")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # === CAMEMBERT (QChart) - Style moderne ===
        self.chart_view = self._create_pie_chart()
        layout.addWidget(self.chart_view, 1)  # stretch = 1 pour occuper tout l'espace
        
    def _create_pie_chart(self):
        """Crée le graphique camembert avec style moderne épuré"""
        self.series = QPieSeries()
        # PAS de trou pour un style plein comme l'image 2
        self.series.setHoleSize(0.0)
        
        # Données initiales vides
        self.slice_default = self.series.append("Aucune donnée", 1)
        self.slice_default.setColor(QColor("#E0E0E0"))
        self.slice_default.setBorderColor(Qt.transparent)  # Pas de bordure
        self.slice_default.setLabelVisible(False)

        chart = QChart()
        chart.addSeries(self.series)
        chart.setTitle("Sélectionnez un batch")
        chart.setTitleFont(QFont("Segoe UI", 13, QFont.Bold))
        chart.setTitleBrush(QBrush(QColor("#1e293b")))
        
        # Légende moderne en bas
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setFont(QFont("Segoe UI", 10))
        chart.legend().setLabelColor(QColor("#1e293b"))
        chart.legend().setBackgroundVisible(False)
        chart.legend().setBorderColor(Qt.transparent)
        
        # Fond transparent et sans bordure
        chart.setBackgroundVisible(False)
        chart.setBackgroundRoundness(0)
        chart.setMargins(QtCore.QMargins(20, 20, 20, 20))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setStyleSheet("background: transparent; border: none;")
        
        return chart_view

    def set_batch_combinations(self, combinations):
        """
        Définit les combinaisons d'un batch pour analyser les typologies
        combinations: liste de dict avec 'contexts' contenant les typologies
        Format: [
            {
                'contexts': [
                    {'level': 'typologie', 'display': 'UX/UI 4', 'data': {...}},
                    ...
                ],
                'nb_samples': 3
            },
            ...
        ]
        """
        self.combinations_data = combinations
        self._update_chart()
    
    def set_batch_family_data(self, data):
        """Alias pour compatibilité - redirige vers set_batch_combinations"""
        # Pour la compatibilité avec l'ancien code
        # data peut être [] pour vider ou une liste de combinaisons
        self.set_batch_combinations(data if data else [])
        
    def _update_chart(self):
        """Analyse et affiche la distribution des typologies de contexte"""
        # Effacer les données précédentes
        self.series.clear()

        # ✅ DEBUG : Afficher ce qu'on reçoit
        logger.info(f"\n📊 DEBUG _update_chart")
        logger.info(f"   Combinations reçues: {len(self.combinations_data)}")

        if self.combinations_data:
            logger.info(f"   Premier combo keys: {self.combinations_data[0].keys()}")
            if 'contexts' in self.combinations_data[0]:
                logger.info(f"   Nombre de contextes: {len(self.combinations_data[0]['contexts'])}")
            if 'master' in self.combinations_data[0]:
                logger.info(f"   Master: {self.combinations_data[0].get('master')}")

        if not self.combinations_data or len(self.combinations_data) == 0:
            # Aucune donnée
            self.slice_default = self.series.append("Aucune donnée", 1)
            self.slice_default.setColor(QColor("#E0E0E0"))
            self.slice_default.setBorderColor(Qt.transparent)
            self.slice_default.setLabelVisible(False)
            self.chart_view.chart().setTitle("Aucune donnée disponible")
            return

        # 📊 ANALYSER LES TYPOLOGIES (MASTER + TOUS LES CONTEXTES)
        typologie_counts = {}
        total_contexts = 0

        for combo_idx, combo in enumerate(self.combinations_data):
            logger.info(f"\n   Combo {combo_idx + 1}:")

            # ✅ 1. COMPTER LE MASTER (toujours présent dans chaque combo)
            master_name = combo.get('master', 'N/A')
            if master_name and master_name != 'N/A':
                logger.info(f"      ⭐ Master: {master_name}")

                if master_name not in typologie_counts:
                    typologie_counts[master_name] = {
                        'count': 0,
                        'level': 'master',
                        'data': combo.get('master_data', {})
                    }

                typologie_counts[master_name]['count'] += 1
                total_contexts += 1

            # ✅ 2. COMPTER TOUS LES CONTEXTES (sans filtre de level)
            contexts = combo.get('contexts', [])
            logger.info(f"      Contextes: {len(contexts)}")

            for ctx_idx, ctx in enumerate(contexts):
                level = ctx.get('level', 'unknown')
                display = ctx.get('display', 'Inconnu')

                logger.info(f"         • Contexte {ctx_idx + 1}: level='{level}', display='{display}'")

                # ⭐ ACCEPTER TOUS LES CONTEXTES (pas de filtre sur level)
                if display and display != 'Inconnu' and display != 'N/A':
                    if display not in typologie_counts:
                        typologie_counts[display] = {
                            'count': 0,
                            'level': level,
                            'data': ctx.get('data', {})
                        }

                    typologie_counts[display]['count'] += 1
                    total_contexts += 1
                else:
                    logger.warning(f"            ⚠️ Contexte ignoré: display invalide")

        logger.info(f"\n   ✅ Total typologies comptées: {total_contexts}")
        logger.info(f"   ✅ Typologies uniques: {list(typologie_counts.keys())}")
        for typo_name, info in typologie_counts.items():
            logger.info(f"      • {typo_name}: {info['count']} occurrence(s) (level: {info['level']})")

        if total_contexts == 0 or not typologie_counts:
            self.slice_default = self.series.append("Aucune typologie trouvée", 1)
            self.slice_default.setColor(QColor("#E0E0E0"))
            self.slice_default.setBorderColor(Qt.transparent)
            self.slice_default.setLabelVisible(False)
            self.chart_view.chart().setTitle("Aucune typologie trouvée")
            return

        # Palette moderne et éclatante
        colors = [
            "#FF6B6B",  # Rouge corail clair
            "#4ECDC4",  # Turquoise clair
            "#45B7D1",  # Bleu ciel
            "#96CEB4",  # Vert menthe
            "#FFEAA7",  # Jaune pastel
            "#DFE6E9",  # Gris très clair
            "#74B9FF",  # Bleu pervenche
            "#A29BFE",  # Lavande
            "#FD79A8",  # Rose bonbon
            "#FDCB6E",  # Orange pastel
            "#6C5CE7",  # Violet doux
            "#00B894",  # Vert émeraude clair
            "#55EFC4",  # Vert menthe vif
            "#81ECEC",  # Cyan clair
            "#FAB1A0",  # Pêche clair
            "#FF7675"   # Rouge saumon
        ]

        # Trier par count décroissant
        sorted_typologies = sorted(
            typologie_counts.items(), 
            key=lambda x: x[1]['count'], 
            reverse=True
        )

        # Ajouter une slice par typologie
        for i, (typologie_name, info) in enumerate(sorted_typologies):
            count = info['count']
            level = info['level']

            # Calculer le pourcentage
            percentage = (count / total_contexts) * 100 if total_contexts > 0 else 0

            slice_obj = self.series.append(typologie_name, count)

            # Couleur unie, SANS bordure visible
            color = QColor(colors[i % len(colors)])
            slice_obj.setColor(color)
            slice_obj.setBorderColor(Qt.transparent)
            slice_obj.setBorderWidth(0)

            # Labels directement sur le camembert
            slice_obj.setLabelVisible(True)
            slice_obj.setLabelPosition(QPieSlice.LabelOutside)
            slice_obj.setLabelArmLengthFactor(0.15)
            slice_obj.setLabelColor(QColor("#1e293b"))
            slice_obj.setLabelFont(QFont("Segoe UI", 10, QFont.Bold))

            # Format du label : ajouter un badge si c'est le master
            if level == 'master':
                slice_obj.setLabel(f"⭐ {typologie_name} ({percentage:.1f}%)")
            else:
                slice_obj.setLabel(f"{typologie_name} ({percentage:.1f}%)")

            # Explosion légère pour le master
            if level == 'master':
                slice_obj.setExploded(True)
                slice_obj.setExplodeDistanceFactor(0.05)
            else:
                slice_obj.setExploded(False)
                slice_obj.setExplodeDistanceFactor(0.03)

            # Stocker les données
            slice_obj.setProperty("typologie_data", {
                'name': typologie_name,
                'level': level,
                'count': count,
                'percentage': percentage,
                'data': info['data']
            })

            # Événements
            slice_obj.hovered.connect(lambda state, s=slice_obj: self._on_slice_hovered(s, state))
            slice_obj.clicked.connect(lambda s=slice_obj: self._on_slice_clicked(s))

        # Titre avec stats
        self.chart_view.chart().setTitle(
            f"Distribution: {len(typologie_counts)} typologie(s) • {total_contexts} occurrence(s) • {len(self.combinations_data)} combo(s)"
        )
    
    def _on_slice_hovered(self, slice_obj, state):
        """Effet hover subtil sur les slices"""
        if state:
            # Légère explosion au survol
            slice_obj.setExploded(True)
        else:
            slice_obj.setExploded(False)
    
    def _on_slice_clicked(self, slice_obj):
        """Affiche une popup avec les détails de la typologie cliquée"""
        typologie_data = slice_obj.property("typologie_data")
        if not typologie_data:
            return
        
        self._show_typologie_details_popup(typologie_data)
    
    def _show_typologie_details_popup(self, typologie_data):
        """Affiche une popup stylée moderne et compacte avec les détails d'une typologie"""
        dialog = QtWidgets.QDialog(self)

        # ✅ SUPPRIMER LE CADRE DE LA FENÊTRE
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)

        dialog.setMinimumWidth(500)
        dialog.setMaximumWidth(600)

        # Container principal avec ombre
        main_container = QWidget()
        main_container.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8fafc);
                border-radius: 12px;
                border: 2px solid #e2e8f0;
            }}
        """)

        # Effet d'ombre sur le container
        try:
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(30)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 8)
            main_container.setGraphicsEffect(shadow)
        except:
            pass
        
        # Layout du dialog
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_container)

        layout = QVBoxLayout(main_container)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # === BARRE DE TITRE CUSTOM ===
        title_bar = QWidget()
        title_bar.setStyleSheet("background: transparent;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(0)

        title_bar_layout.addStretch()

        # Bouton X pour fermer
        close_x_btn = QPushButton("✕")
        close_x_btn.setFixedSize(32, 32)
        close_x_btn.setCursor(Qt.PointingHandCursor)
        close_x_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 16px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #fee2e2;
                color: #dc2626;
            }}
        """)
        close_x_btn.clicked.connect(dialog.reject)
        title_bar_layout.addWidget(close_x_btn)

        layout.addWidget(title_bar)

        # === EN-TÊTE AVEC ICÔNE ET TITRE ===
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(15)

        # Icône
        icon_label = QLabel("📊")
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        header_layout.addWidget(icon_label)

        # Titre et level
        title_widget = QWidget()
        title_widget.setStyleSheet("background: transparent;")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)

        name = typologie_data.get('name', 'Inconnu')
        level = typologie_data.get('level', 'unknown')
        count = typologie_data.get('count', 0)
        percentage = typologie_data.get('percentage', 0.0)
        data = typologie_data.get('data', {})

        title_label = QLabel(f"<b>{name}</b>")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setStyleSheet("color: #1e293b; background: transparent;")
        title_layout.addWidget(title_label)

        # Badge du level
        level_badge = QLabel(f"🏷️ {level.upper()}")
        level_badge.setStyleSheet(f"""
            background: {Theme.PRIMARY_COLOR if level == 'master' else '#e2e8f0'};
            color: {'white' if level == 'master' else '#475569'};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
        """)
        title_layout.addWidget(level_badge)

        header_layout.addWidget(title_widget)
        header_layout.addStretch()

        layout.addWidget(header)

        # === STATISTIQUES ===
        stats_container = QWidget()
        stats_container.setStyleSheet("background: transparent;")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setSpacing(15)

        # Carte Occurrences
        occ_card = QFrame()
        occ_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f9ff);
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        occ_layout = QVBoxLayout(occ_card)
        occ_layout.setSpacing(5)

        occ_value = QLabel(str(count))
        occ_value.setFont(QFont("Segoe UI", 28, QFont.Bold))
        occ_value.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; background: transparent;")
        occ_value.setAlignment(Qt.AlignCenter)
        occ_layout.addWidget(occ_value)

        occ_label = QLabel("Occurrences")
        occ_label.setFont(QFont("Segoe UI", 10))
        occ_label.setStyleSheet("color: #64748b; background: transparent;")
        occ_label.setAlignment(Qt.AlignCenter)
        occ_layout.addWidget(occ_label)

        stats_layout.addWidget(occ_card)

        # Carte Pourcentage
        pct_card = QFrame()
        pct_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #fef3f2);
                border: 2px solid {Theme.SECONDARY_COLOR};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        pct_layout = QVBoxLayout(pct_card)
        pct_layout.setSpacing(5)

        pct_value = QLabel(f"{percentage:.1f}%")
        pct_value.setFont(QFont("Segoe UI", 28, QFont.Bold))
        pct_value.setStyleSheet(f"color: {Theme.SECONDARY_COLOR}; background: transparent;")
        pct_value.setAlignment(Qt.AlignCenter)
        pct_layout.addWidget(pct_value)

        pct_label = QLabel("Du total")
        pct_label.setFont(QFont("Segoe UI", 10))
        pct_label.setStyleSheet("color: #64748b; background: transparent;")
        pct_label.setAlignment(Qt.AlignCenter)
        pct_layout.addWidget(pct_label)

        stats_layout.addWidget(pct_card)

        layout.addWidget(stats_container)

        # === INFORMATIONS SUPPLÉMENTAIRES ===
        if data:
            clusters = data.get('taxonomy_clusters', [])
            if clusters:
                info_container = QFrame()
                info_container.setStyleSheet("""
                    QFrame {
                        background: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                        padding: 12px;
                    }
                """)
                info_layout = QHBoxLayout(info_container)
                info_layout.setSpacing(10)

                cluster_icon = QLabel("🗂️")
                cluster_icon.setStyleSheet("font-size: 20px; background: transparent;")
                info_layout.addWidget(cluster_icon)

                cluster_text = QLabel(f"<b>{len(clusters)}</b> cluster(s) taxonomique(s)")
                cluster_text.setFont(QFont("Segoe UI", 10))
                cluster_text.setStyleSheet("color: #475569; background: transparent;")
                info_layout.addWidget(cluster_text)
                info_layout.addStretch()

                layout.addWidget(info_container)

        # === BOUTON FERMER MODERNE ===
        layout.addSpacing(10)

        close_btn = QPushButton("Fermer")
        close_btn.setMinimumHeight(45)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:pressed {{
                background: {Theme.PRIMARY_COLOR};
                padding: 13px 23px 11px 25px;
            }}
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()
    
    def clear(self):
        """Efface le chart et réinitialise"""
        self.combinations_data = []
        self._update_chart()

class CombinationsPopup(QtWidgets.QDialog):
    """Popup pour afficher les combinaisons à générer"""
    
    def __init__(self, combinations, parent=None):
        super().__init__(parent)
        self.combinations = combinations
        self.completed = [False] * len(combinations)
        self._init_ui()
        
    def _init_ui(self):
        self.setWindowTitle("📋 Combinaisons à Générer")
        self.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Titre
        title = QLabel(f"<h2>🎯 {len(self.combinations)} Combinaison(s) à Générer</h2>")
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        layout.addWidget(title)
        
        # Zone scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(10)
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        # Bouton Fermer
        close_btn = GradientButton("Fermer")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Remplir avec les combinaisons
        self._populate_combinations()
        
    def _populate_combinations(self):
        """Remplit la liste des combinaisons"""
        for i, combo in enumerate(self.combinations):
            combo_frame = QFrame()
            combo_frame.setFrameShape(QFrame.StyledPanel)
            combo_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 2px solid #E0E0E0;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
            
            combo_layout = QVBoxLayout(combo_frame)
            
            # En-tête : Numéro + Master + Samples
            header_layout = QHBoxLayout()
            
            num_label = QLabel(f"<b>#{i+1}</b>")
            num_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            num_label.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
            header_layout.addWidget(num_label)
            
            # Master
            master_name = combo.get('master', 'N/A')
            master_label = QLabel(f"Master: <b>{master_name}</b>")
            master_label.setStyleSheet("font-size: 11pt;")
            header_layout.addWidget(master_label)
            
            header_layout.addStretch()
            
            # Infos
            nb_contexts = len(combo.get('contexts', []))
            nb_samples = combo.get('nb_samples', 1)
            
            info_label = QLabel(f"<b>{nb_contexts}</b> contexte(s) • <b>{nb_samples}</b> sample(s)")
            info_label.setStyleSheet(f"color: {Theme.SECONDARY_COLOR}; font-size: 10pt;")
            header_layout.addWidget(info_label)
            
            combo_layout.addLayout(header_layout)
            
            # Séparateur
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #E0E0E0; max-height: 1px;")
            combo_layout.addWidget(separator)
            
            # Liste des contextes
            contexts = combo.get('contexts', [])
            for ctx_idx, ctx in enumerate(contexts):
                ctx_layout = QHBoxLayout()
                
                # Niveau
                level_label = QLabel(f"<b>{ctx.get('level', 'unknown').upper()}</b>")
                level_label.setStyleSheet("color: #666; font-size: 9pt;")
                level_label.setFixedWidth(80)
                ctx_layout.addWidget(level_label)
                
                # Display
                display_label = QLabel(ctx.get('display', 'N/A'))
                display_label.setStyleSheet("font-size: 10pt;")
                display_label.setWordWrap(True)
                ctx_layout.addWidget(display_label)
                
                combo_layout.addLayout(ctx_layout)
            
            self.content_layout.addWidget(combo_frame)
        
        self.content_layout.addStretch()
    
    def mark_completed(self, index):
        """Marque une combinaison comme complétée (appelé pendant la génération)"""
        if 0 <= index < len(self.completed):
            self.completed[index] = True


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
        self.dropdown_svg = get_dropdown_svg_path()

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

        # ✅ CORRECTION ICI : D'abord l'UI, ENSUITE le bouton overlay
        self._init_ui()            # Crée self.snippets_container
        self._init_overlay_button() # Utilise self.snippets_container
        
        print("✅ UI initialisée")
        logger.info("✅ UI initialisée")
        
        # Charger les projets si la database est disponible
        if self.database:
            self._load_projects()
        
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
        left_scroll.setMinimumWidth(250)
        center_scroll.setMinimumWidth(300)
        right_scroll.setMinimumWidth(350)

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
        """Crée la colonne gauche - Projet, Configuration RESPONSIVE + Progress Bar"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # ✅ Padding uniforme

        # Section Projet
        project_section = self._create_project_section()
        layout.addWidget(project_section)

        # Section Configuration
        config_section = self._create_config_section()
        layout.addWidget(config_section)

        # INFO: Affichage des infos du batch sélectionné
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

        # ✅ BARRE DE PROGRESSION EN BAS DE LA COLONNE 1
        self.progress_bar = GradientProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(self.progress_bar)

        return column
        
    def _create_center_column(self):
        """Crée la colonne centrale - Éditeur de Prompt RESPONSIVE + Bouton Combinaisons"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # ✅ Padding uniforme

        # === CONTEXTE GLOBAL (Collapsible) ===
        self.global_section = CollapsibleSection("Contexte Global du Projet")

        global_info = QLabel("ℹ️ Contexte partagé pour tous les batches du projet")
        global_info.setFont(QFont("Segoe UI", 8))
        global_info.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        global_info.setWordWrap(True)  # ✅ Responsive text
        self.global_section.add_widget(global_info)

        # ✅ Éditeur contexte global - Hauteur adaptative
        self.global_context_editor = QTextEdit()
        self.global_context_editor.setPlaceholderText(
            "Définissez ici le contexte général du projet...\n\n"
            "Exemple:\n"
            "- Objectif du dataset\n"
            "- Domaine d'application\n"
            "- Contraintes générales\n"
            "- Style de sortie attendu"
        )
        self.global_context_editor.setMinimumHeight(100)  # ✅ Min height
        self.global_context_editor.setMaximumHeight(200)  # ✅ Max height
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

        local_title = QLabel("✏️ Prompt Local (Batch)")
        local_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        local_title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        local_header_layout.addWidget(local_title)

        local_info = QLabel("Instructions spécifiques pour ce batch")
        local_info.setFont(QFont("Segoe UI", 8))
        local_info.setStyleSheet("color: #666; font-style: italic;")
        local_info.setWordWrap(True)  # ✅ Responsive text
        local_header_layout.addWidget(local_info)
        local_header_layout.addStretch()

        layout.addWidget(local_header)

        # ✅ Éditeur contexte local - Hauteur adaptative et responsive
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText(
            "Exemple:\n\n"
            "Générez des exemples d'entraînement basés sur les typologies suivantes:\n"
            "{typologie}\n\n"
            "Format attendu: {'input': '...', 'output': '...'}"
        )
        self.prompt_editor.setMinimumHeight(200)  # ✅ Min height
        self.prompt_editor.setMaximumHeight(500)  # ✅ Max height augmentée
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
        layout.addWidget(self.prompt_editor, 1)  # ✅ Stretch pour utiliser l'espace

        # ✅ BOUTON "VOIR LES COMBINAISONS" EN BAS DE LA COLONNE 2
        self.view_combinations_btn = GradientButton("📋 Voir les Combinaisons")
        self.view_combinations_btn.clicked.connect(self._show_combinations_popup)
        self.view_combinations_btn.setEnabled(False)  # Désactivé par défaut
        self.view_combinations_btn.setMinimumHeight(45)  # Hauteur fixe
        layout.addWidget(self.view_combinations_btn)

        return column
        
    def _create_right_column(self):
        """Crée la colonne droite - Chart UNIQUEMENT (bouton déplacé en colonne 2)"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)  # ✅ Padding uniforme

        # Visualiseur de représentativité (Camembert)
        self.batch_chart = BatchRepresentativityChart()

        viz_container = QFrame()
        viz_container.setFrameShape(QFrame.StyledPanel)
        viz_container.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
        """)

        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(15, 15, 15, 15)

        # ✅ Chart avec hauteur min/max
        self.batch_chart.setMinimumHeight(300)
        self.batch_chart.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        viz_layout.addWidget(self.batch_chart)

        layout.addWidget(viz_container, 1)  # ✅ Stretch pour utiliser l'espace

        # ❌ BOUTON SUPPRIMÉ D'ICI - Maintenant dans la colonne 2

        return column

    def _create_project_section(self):
        """Crée la section de sélection du projet - RESPONSIVE"""
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

        # ✅ 1. COMBO PROJET - RESPONSIVE
        project_label = QLabel("Projet:")
        project_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        project_label.setWordWrap(True)
        group_layout.addWidget(project_label)

        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(40)
        self.project_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self._apply_combo_style(self.project_combo)
        group_layout.addWidget(self.project_combo)

        # ✅ 2. COMBO FAMILLE DE BATCH - RESPONSIVE
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

        # ✅ 3. COMBO BATCH - RESPONSIVE
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
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.SECONDARY_COLOR};
                background: #FAFAFA;
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
                border: 2px solid {Theme.PRIMARY_COLOR};
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
            self.project_combo.addItem("-- Sélectionner un projet --", None)
            
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
        if project_name == "-- Sélectionner un projet --" or not project_name:
            self.current_project = None
            self.current_project_name = None
            self.current_batch_number = None
            self.current_batch_data = None
            self.combinations = []
            self.batch_family_combo.clear()
            self.batch_family_combo.addItem("-- Aucun projet sélectionné --", None)
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Aucun projet sélectionné --", None)
            self.batch_info_label.setVisible(False)
            logger.info("Reset de la sélection")
            return

        try:
            self.current_project_name = project_name
            project_data = self.database.get_dataset_projet(project_name)

            if not project_data:
                logger.error(f"❌ Projet '{project_name}' non trouvé")
                QMessageBox.warning(
                    self, 
                    "Projet introuvable", 
                    f"Le projet '{project_name}' n'a pas pu être chargé."
                )
                return

            self.current_project = project_data
            logger.info(f"✅ Projet chargé: {project_name}")

            # ✅ CHARGER LES FAMILLES DE BATCH
            self._load_batch_families()

        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    #def _load_batches(self):
    #    """Charge les batches du projet actuel"""
    #    self.batch_combo.clear()
    #    self.batch_combo.addItem("-- Sélectionner un batch --", None)
#
    #    if not self.current_project_name:
    #        logger.warning("Aucun projet actuel")
    #        return
#
    #    try:
    #        logger.info(f"🔍 Recherche des batches pour: {self.current_project_name}")
    #        batches = self.database.get_all_batches(self.current_project_name)
#
    #        if not batches or len(batches) == 0:
    #            logger.info(f"⚠️ Aucun batch trouvé")
    #            self.batch_combo.addItem("-- Aucun batch disponible --", None)
    #            return
#
    #        logger.info(f"📦 {len(batches)} batch(es) trouvé(s)")
#
    #        # Trier par numéro
    #        try:
    #            batches_sorted = sorted(batches, key=lambda x: x.get('batch_number', 0))
    #        except:
    #            batches_sorted = batches
#
    #        # Ajouter chaque batch
    #        for batch in batches_sorted:
    #            batch_num = batch.get('batch_number', 0)
    #            total_batches = batch.get('total_batches', 0)
    #            batch_data_content = batch.get('data', {})
    #            
    #            batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
    #            combinations = batch_data_content.get('combinations', [])
    #            combinations_count = len(combinations)
#
    #            if total_batches > 0:
    #                display_name = f"Batch {batch_num}/{total_batches} - {batch_name} ({combinations_count} combos)"
    #            else:
    #                display_name = f"Batch {batch_num} - {batch_name} ({combinations_count} combos)"
#
    #            self.batch_combo.addItem(display_name, batch_num)
    #            logger.debug(f"  ✓ Batch ajouté: {display_name}")
#
    #        logger.info(f"✅ {len(batches)} batch(es) chargé(s)")
#
    #    except Exception as e:
    #        logger.error(f"❌ Erreur: {str(e)}")
    #        import traceback
    #        logger.error(traceback.format_exc())
    #        self.batch_combo.addItem("-- Erreur de chargement --", None)

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
            self.batch_chart.clear()
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
            self.view_combinations_btn.setEnabled(len(self.combinations) > 0)

            # ✅ METTRE À JOUR LE CHART AVEC LES VRAIES DONNÉES
            logger.info(f"\n📊 Mise à jour du chart de représentativité")
            self.batch_chart.set_batch_combinations(display_combos)
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

    def _on_generate(self):
        """Lance la génération du dataset - VERSION AVEC WORKER + LOGGING"""
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
        local_prompt = self.prompt_editor.toPlainText().strip()
    
        if not local_prompt:
            QMessageBox.warning(
                self,
                "Prompt manquant",
                "Veuillez définir au moins un prompt local de génération"
            )
            return
    
        # Combiner les contextes
        if global_context:
            combined_prompt = f"{global_context}\n\n---\n\n{local_prompt}"
            logger.info("✅ Contexte global et local combinés")
        else:
            combined_prompt = local_prompt
            logger.info("ℹ️ Utilisation du contexte local uniquement")
    
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
                "local_prompt": local_prompt,
                "combined_prompt": combined_prompt
            },
            "prompt": combined_prompt,  # Pour le worker
            "master_typologie": {
                "name": self.current_master_typologie.get('name', 'N/A'),
                "full_data": self.current_master_typologie
            },
            "combinations": []
        }
    
        # 📋 CONSTRUIRE LES COMBINAISONS COMPLÈTES
        for i, combo in enumerate(self.combinations):
            contexts = combo.get('contexts', [])
            nb_samples = combo.get('nb_samples', 1)
    
            # ✅ DEBUG : Vérifier ce qu'on envoie
            logger.debug(f"\n🔍 DEBUG Combination {i+1} preparation:")
            logger.debug(f"   Master typologie keys: {self.current_master_typologie.keys()}")
            logger.debug(f"   Master has taxonomy_clusters: {bool(self.current_master_typologie.get('taxonomy_clusters'))}")
    
            if self.current_master_typologie.get('taxonomy_clusters'):
                clusters = self.current_master_typologie['taxonomy_clusters']
                logger.debug(f"   Master clusters count: {len(clusters)}")
                if clusters:
                    logger.debug(f"   First cluster keys: {clusters[0].keys()}")
                    logger.debug(f"   First cluster name: {clusters[0].get('cluster_name', 'NO NAME')}")
    
            combo_export = {
                "combination_index": i + 1,
                "nb_samples": nb_samples,
                "master": {
                    "name": self.current_master_typologie.get('name', 'N/A'),
                    "full_data": self.current_master_typologie  # ✅ Doit contenir taxonomy_clusters
                },
                "contexts": []
            }
    
            for ctx_idx, ctx in enumerate(contexts):
                ctx_data = ctx.get('data', {})
    
                # ✅ DEBUG : Vérifier chaque contexte
                logger.debug(f"   Context {ctx_idx+1} data keys: {ctx_data.keys() if ctx_data else 'EMPTY'}")
                logger.debug(f"   Context {ctx_idx+1} has taxonomy_clusters: {bool(ctx_data.get('taxonomy_clusters'))}")
    
                context_export = {
                    "level": ctx.get('level', 'unknown'),
                    "display": ctx.get('display', 'N/A'),
                    "full_data": ctx_data  # ✅ Doit contenir taxonomy_clusters
                }
                combo_export["contexts"].append(context_export)
    
            generation_config["combinations"].append(combo_export)
    
        # 📝 EXPORTER LA CONFIGURATION COMPLÈTE DANS UN FICHIER DE LOG
        config_filepath = self._export_generation_config_to_file(generation_config)
    
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
        if config_filepath:
            msg += f"<br>📝 <b>Config exportée :</b><br><small>{config_filepath}</small><br>"
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
    
        # 🎬 LANCER LE WORKER
        try:
            from ui.widgets.workers.gemini_dataset_worker import GeminiDatasetWorker
    
            self.worker = GeminiDatasetWorker(generation_config)
    
            # Connecter les signaux
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
            self.generate_btn.setText("⏳ Génération en cours...")
            self.export_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(total_samples_all_batches)
    
            logger.info("✅ Worker lancé avec succès")
    
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
        self.batch_family_combo.addItem("-- Sélectionner une famille --", None)

        if not self.current_project_name:
            logger.warning("Aucun projet actuel")
            return

        try:
            logger.info(f"🔍 Recherche des familles de batch pour: {self.current_project_name}")
            batches = self.database.get_all_batches(self.current_project_name)

            if not batches or len(batches) == 0:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_family_combo.addItem("-- Aucune famille disponible --", None)
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
                self.batch_family_combo.addItem("-- Aucune famille définie --", None)
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
        self.view_combinations_btn.setEnabled(False)
        self.batch_info_label.setVisible(False)

        if family is None:
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Sélectionner une famille --", None)
            self.batch_chart.set_batch_family_data([])  # ✅ Vider le chart
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

            self.batch_chart.set_batch_family_data(chart_data)
            logger.info(f"✅ Chart mis à jour avec {len(chart_data)} batches")

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour chart: {str(e)}")

    def _show_combinations_popup(self):
        """Affiche la popup avec les combinaisons à générer"""
        if not self.combinations:
            QMessageBox.warning(
                self,
                "Aucune combinaison",
                "Aucune combinaison à afficher.\nVeuillez d'abord sélectionner un batch."
            )
            return
        
        # Construire les données d'affichage
        display_combos = []
        batch_data = self.current_batch_data.get('data', {})
        master_typologie = batch_data.get('master_typologie', {})
        master_name = master_typologie.get('name', 'N/A') if master_typologie else 'N/A'
        
        for i, combo in enumerate(self.combinations):
            contexts = combo.get('contexts', [])
            nb_samples = combo.get('nb_samples', 1)
            
            display_combo = {
                'master': master_name,
                'contexts': [],
                'nb_samples': nb_samples
            }
            
            for ctx in contexts:
                display_combo['contexts'].append({
                    'level': ctx.get('level', 'unknown'),
                    'display': ctx.get('display', 'N/A')
                })
            
            display_combos.append(display_combo)
        
        # Créer et afficher la popup
        popup = CombinationsPopup(display_combos, self)
        
        # Si on a un worker en cours, connecter les signaux pour mettre à jour
        if hasattr(self, 'worker') and self.worker:
            self.worker.combination_completed.connect(popup.mark_completed)
        
        popup.exec_()

    def _load_batches_by_family(self, family):
        """Charge les batches d'une famille spécifique"""
        self.batch_combo.clear()
        self.batch_combo.addItem("-- Sélectionner un batch --", None)

        if not self.current_project_name or not family:
            logger.warning("Projet ou famille manquant")
            return

        try:
            logger.info(f"🔍 Recherche des batches pour famille: {family}")
            all_batches = self.database.get_all_batches(self.current_project_name)

            if not all_batches:
                logger.info(f"⚠️ Aucun batch trouvé")
                self.batch_combo.addItem("-- Aucun batch disponible --", None)
                return

            # Filtrer par famille
            batches = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]

            if not batches:
                logger.info(f"⚠️ Aucun batch dans cette famille")
                self.batch_combo.addItem("-- Aucun batch dans cette famille --", None)
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

        # UI : réactiver les boutons
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Générer le Dataset")
        self.export_btn.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())

        self._add_to_history(
            self.current_project_name, 
            self.current_batch_number, 
            len(results)
        )

        if self.snippets_panel.width() == 0:
            self._toggle_snippets_panel()

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

    def _export_jsonl(self, filepath: str):
        """Exporte en JSONL (une ligne par sample) avec données nettoyées"""
        with open(filepath, 'w', encoding='utf-8') as f:
            for sample in self.generation_results:
                # ✅ Nettoyer chaque sample
                cleaned = self._clean_sample_for_export(sample)
                f.write(json.dumps(cleaned, ensure_ascii=False) + '\n')

    def _export_csv(self, filepath: str):
        """
        Exporte en CSV avec données nettoyées
        Format aplati pour CSV : une ligne par combinaison
        Gère la hiérarchie complète : label_root, label_parent, label_enfant, label_enfant_1, label_enfant_2, ...
        """
        import csv

        if not self.generation_results:
            return

        # ✅ DÉTERMINER LE NOMBRE MAXIMUM DE NIVEAUX D'ENFANTS
        max_enfant_levels = 0
        for sample in self.generation_results:
            combinaisons = sample.get('combinaisons', [])
            for combo in combinaisons:
                # Chercher les clés label_enfant_N
                enfant_keys = [k for k in combo.keys() if k.startswith('label_enfant_') and k != 'label_enfant']
                if enfant_keys:
                    # Extraire le niveau max (label_enfant_1 -> 1, label_enfant_2 -> 2, etc.)
                    levels = [int(k.split('_')[-1]) for k in enfant_keys if k.split('_')[-1].isdigit()]
                    if levels:
                        max_enfant_levels = max(max_enfant_levels, max(levels))

        # Construire les colonnes dynamiquement avec la hiérarchie complète
        fieldnames = [
            'sample_id', 'input', 'output',
            'typologie_de_contexte', 'cluster', 
            'label',           # Label simple (si pas de hiérarchie)
            'label_root',      # Niveau 1 : ROOT
            'label_parent',    # Niveau 2 : PARENT
            'label_enfant'     # Niveau 3 : ENFANT/CHILD
        ]

        # Ajouter label_enfant_1, label_enfant_2, ... selon le max trouvé (Niveau 4+)
        for i in range(1, max_enfant_levels + 1):
            fieldnames.append(f'label_enfant_{i}')

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sample in self.generation_results:
                sample_id = sample.get('sample_id')
                input_text = sample.get('input', '')
                output_text = sample.get('output', '')
                combinaisons = sample.get('combinaisons', [])

                # ✅ Une ligne par combinaison
                if not combinaisons:
                    # Si pas de combinaisons, écrire une ligne vide
                    row = {
                        'sample_id': sample_id,
                        'input': input_text,
                        'output': output_text
                    }
                    # Remplir les colonnes manquantes avec vide
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    writer.writerow(row)
                else:
                    for combo in combinaisons:
                        row = {
                            'sample_id': sample_id,
                            'input': input_text,
                            'output': output_text,
                            'typologie_de_contexte': combo.get('typologie_de_contexte', ''),
                            'cluster': combo.get('cluster', ''),
                            'label': combo.get('label', ''),           # Label simple
                            'label_root': combo.get('label_root', ''),     # ROOT
                            'label_parent': combo.get('label_parent', ''), # PARENT
                            'label_enfant': combo.get('label_enfant', '')  # ENFANT
                        }

                        # Ajouter les label_enfant_N dynamiquement (sous-enfants)
                        for i in range(1, max_enfant_levels + 1):
                            row[f'label_enfant_{i}'] = combo.get(f'label_enfant_{i}', '')

                        writer.writerow(row)

    def _clean_sample_for_export(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Nettoie un sample en ne gardant que les champs essentiels
        FORMAT : sample_id, input, combinaisons[], output
        """
        return {
            'sample_id': sample.get('sample_id'),
            'input': sample.get('input', ''),
            'combinaisons': sample.get('combinaisons', []),
            'output': sample.get('output', '')
        }

    def _export_parquet(self, filepath: str):
        """
        Exporte en Parquet avec données nettoyées
        Format aplati avec hiérarchie complète : label_root, label_parent, label_enfant, label_enfant_1, ...
        """
        try:
            import pandas as pd
    
            # ✅ DÉTERMINER LE NOMBRE MAXIMUM DE NIVEAUX D'ENFANTS
            max_enfant_levels = 0
            for sample in self.generation_results:
                combinaisons = sample.get('combinaisons', [])
                for combo in combinaisons:
                    enfant_keys = [k for k in combo.keys() if k.startswith('label_enfant_') and k != 'label_enfant']
                    if enfant_keys:
                        levels = [int(k.split('_')[-1]) for k in enfant_keys if k.split('_')[-1].isdigit()]
                        if levels:
                            max_enfant_levels = max(max_enfant_levels, max(levels))
    
            # Aplatir les données
            rows = []
            for sample in self.generation_results:
                sample_id = sample.get('sample_id')
                input_text = sample.get('input', '')
                output_text = sample.get('output', '')
                combinaisons = sample.get('combinaisons', [])
    
                if not combinaisons:
                    row = {
                        'sample_id': sample_id,
                        'input': input_text,
                        'output': output_text,
                        'typologie_de_contexte': '',
                        'cluster': '',
                        'label': '',
                        'label_root': '',
                        'label_parent': '',
                        'label_enfant': ''
                    }
                    # Ajouter colonnes label_enfant_N vides
                    for i in range(1, max_enfant_levels + 1):
                        row[f'label_enfant_{i}'] = ''
                    rows.append(row)
                else:
                    for combo in combinaisons:
                        row = {
                            'sample_id': sample_id,
                            'input': input_text,
                            'output': output_text,
                            'typologie_de_contexte': combo.get('typologie_de_contexte', ''),
                            'cluster': combo.get('cluster', ''),
                            'label': combo.get('label', ''),
                            'label_root': combo.get('label_root', ''),
                            'label_parent': combo.get('label_parent', ''),
                            'label_enfant': combo.get('label_enfant', '')
                        }
                        # Ajouter label_enfant_N dynamiquement
                        for i in range(1, max_enfant_levels + 1):
                            row[f'label_enfant_{i}'] = combo.get(f'label_enfant_{i}', '')
                        rows.append(row)
    
            df = pd.DataFrame(rows)
            df.to_parquet(filepath, index=False)
    
        except ImportError:
            raise Exception(
                "Le module 'pandas' est requis pour exporter en Parquet.\n"
                "Installez-le avec: pip install pandas pyarrow"
            )
        
    def resizeEvent(self, event):
        """Repositionne le bouton toggle et gère le responsive"""
        super().resizeEvent(event)

        # ✅ Repositionner le bouton toggle snippets
        if hasattr(self, 'toggle_snippets_button'):
            self.update_button_position()

        # ✅ Ajuster la hauteur du bouton toggle selon la fenêtre
        if hasattr(self, 'toggle_snippets_button'):
            button_height = min(140, int(self.height() * 0.15))
            self.toggle_snippets_button.setMaximumHeight(button_height)

        # ✅ Gérer les petites largeurs (mobile-like)
        window_width = self.width()

        if window_width < 800:
            # Mode compact: ajuster les proportions
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.30),  # Gauche: 30%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.35)   # Droite: 35%
                ])
        elif window_width < 1200:
            # Mode moyen
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.27),  # Gauche: 27%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.38)   # Droite: 38%
                ])
        else:
            # Mode large: proportions par défaut
            if hasattr(self, 'columns_splitter'):
                self.columns_splitter.setSizes([
                    int(window_width * 0.25),  # Gauche: 25%
                    int(window_width * 0.35),  # Centre: 35%
                    int(window_width * 0.40)   # Droite: 40%
                ])

    def _init_overlay_button(self):
        """Initialise le bouton chevron et le panneau latéral (Style Snippet)"""
        
        # Pour simuler la fonction tr() si elle n'existe pas
        def tr(text): return {"generated_code": "Historique"}.get(text, text)
        
        graph_container = self

        self.toggle_snippets_button = QtWidgets.QWidget(self)
        button_height = min(140, int(self.height() * 0.15))
        self.toggle_snippets_button.setMinimumSize(36, 100)
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
        button_layout.setContentsMargins(0, 12, 0, 12)
        button_layout.setSpacing(8)
        button_layout.setAlignment(Qt.AlignCenter)

        # Icône chevron
        self.chevron_icon_label = QtWidgets.QLabel()
        self.chevron_icon_label.setAlignment(Qt.AlignCenter)
        try:
            self.chevron_icon_label.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(18, 18))
        except:
            self.chevron_icon_label.setText("<") # Fallback si qtawesome manque

        button_layout.addWidget(self.chevron_icon_label)

        # Texte vertical "HISTORIQUE"
        self.toggle_button_text = QtWidgets.QLabel("H\nI\nS\nT\nO\nR\nI\nQ\nU\nE")
        self.toggle_button_text.setAlignment(Qt.AlignCenter)
        self.toggle_button_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 9px;
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
        snippets_title = QtWidgets.QLabel(f"💻 Historique")
        snippets_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; background-color: transparent; border: none;")
        snippets_header.addWidget(snippets_title)
        snippets_header.addStretch()

        # Bouton Historique Global
        self.global_history_button = QtWidgets.QPushButton()
        try:
            self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))
        except:
            self.global_history_button.setText("H")
            
        self.global_history_button.setToolTip("Voir l'historique")
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
        
        # Menu Historique
        history_menu = QtWidgets.QMenu(self)
        view_current_action = QtWidgets.QAction("📜 Historique de la session", self)
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

        # Accordéon Historique Global (Contenu)
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
        """Affiche/Masque l'historique"""
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
        """Ajoute une entrée dans l'historique après génération"""
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