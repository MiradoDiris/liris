#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Verification Panel
Vérification et validation des datasets générés avec analyse de qualité
Design cohérent avec dataset_generation.py et prompt_list.py
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QProgressBar, QScrollArea,
    QFrame, QGroupBox, QMessageBox, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase


def get_dropdown_svg_path():
    """Retourne le chemin vers l'icône dropdown SVG"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.dirname(current_dir)
    svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
    return os.path.normpath(svg_path).replace('\\', '/')


class DatasetVerificationWorker(QThread):
    """Worker pour la vérification asynchrone des datasets"""
    
    progress_updated = pyqtSignal(int, int, str)
    verification_completed = pyqtSignal(dict)
    verification_failed = pyqtSignal(str)
    
    def __init__(self, file_path, file_format):
        super().__init__()
        self.file_path = file_path
        self.file_format = file_format
        
    def run(self):
        """Execute la vérification du dataset"""
        try:
            logger.info(f"🔍 Début vérification: {self.file_path}")
            
            # Charger les données
            self.progress_updated.emit(1, 5, "Chargement du fichier...")
            data = self._load_data()
            
            if not data:
                raise ValueError("Impossible de charger les données")
            
            # Analyser la structure
            self.progress_updated.emit(2, 5, "Analyse de la structure...")
            structure_analysis = self._analyze_structure(data)
            
            # Vérifier la qualité
            self.progress_updated.emit(3, 5, "Vérification de la qualité...")
            quality_analysis = self._analyze_quality(data)
            
            # Vérifier les doublons
            self.progress_updated.emit(4, 5, "Détection des doublons...")
            duplicates_analysis = self._check_duplicates(data)
            
            # Statistiques globales
            self.progress_updated.emit(5, 5, "Calcul des statistiques...")
            statistics = self._compute_statistics(data)
            
            # Résultat complet
            result = {
                'file_path': self.file_path,
                'file_format': self.file_format,
                'structure': structure_analysis,
                'quality': quality_analysis,
                'duplicates': duplicates_analysis,
                'statistics': statistics,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            
            self.verification_completed.emit(result)
            logger.info("✅ Vérification terminée avec succès")
            
        except Exception as e:
            error_msg = f"Erreur lors de la vérification: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            self.verification_failed.emit(error_msg)
    
    def _load_data(self) -> List[Dict]:
        """Charge les données selon le format"""
        if self.file_format == 'JSON':
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                # Gérer le cas où le JSON contient {samples: [...]}
                if isinstance(content, dict) and 'samples' in content:
                    return content['samples']
                elif isinstance(content, list):
                    return content
                else:
                    return [content]
                    
        elif self.file_format == 'JSONL':
            data = []
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            return data
            
        elif self.file_format == 'CSV':
            import csv
            data = []
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            return data
            
        elif self.file_format == 'Parquet':
            import pandas as pd
            df = pd.read_parquet(self.file_path)
            return df.to_dict('records')
        
        return []
    
    def _analyze_structure(self, data: List[Dict]) -> Dict:
        """Analyse la structure du dataset"""
        if not data:
            return {'valid': False, 'error': 'Dataset vide'}
        
        # Vérifier les champs communs
        first_keys = set(data[0].keys())
        required_fields = {'sample_id', 'input', 'output'}
        
        missing_fields = required_fields - first_keys
        extra_fields = first_keys - required_fields
        
        # Vérifier la cohérence des clés
        inconsistent_samples = []
        for i, sample in enumerate(data[1:], start=1):
            if set(sample.keys()) != first_keys:
                inconsistent_samples.append(i)
        
        return {
            'valid': len(missing_fields) == 0 and len(inconsistent_samples) == 0,
            'total_samples': len(data),
            'fields': list(first_keys),
            'required_fields': list(required_fields),
            'missing_fields': list(missing_fields),
            'extra_fields': list(extra_fields),
            'inconsistent_samples': inconsistent_samples[:10]  # Max 10 exemples
        }
    
    def _analyze_quality(self, data: List[Dict]) -> Dict:
        """Analyse la qualité des données"""
        issues = []
        empty_inputs = 0
        empty_outputs = 0
        short_inputs = 0
        short_outputs = 0
        
        for i, sample in enumerate(data):
            sample_id = sample.get('sample_id', f'sample_{i}')
            
            # Vérifier les champs vides
            if not sample.get('input', '').strip():
                empty_inputs += 1
                issues.append({
                    'sample_id': sample_id,
                    'type': 'empty_input',
                    'message': 'Input vide'
                })
            
            if not sample.get('output', '').strip():
                empty_outputs += 1
                issues.append({
                    'sample_id': sample_id,
                    'type': 'empty_output',
                    'message': 'Output vide'
                })
            
            # Vérifier les longueurs suspectes
            input_text = sample.get('input', '')
            output_text = sample.get('output', '')
            
            if len(input_text.strip()) < 10:
                short_inputs += 1
                if len(issues) < 100:  # Limiter les issues
                    issues.append({
                        'sample_id': sample_id,
                        'type': 'short_input',
                        'message': f'Input court ({len(input_text)} caractères)'
                    })
            
            if len(output_text.strip()) < 10:
                short_outputs += 1
                if len(issues) < 100:
                    issues.append({
                        'sample_id': sample_id,
                        'type': 'short_output',
                        'message': f'Output court ({len(output_text)} caractères)'
                    })
        
        total_samples = len(data)
        quality_score = 100 - (
            (empty_inputs / total_samples * 30) +
            (empty_outputs / total_samples * 30) +
            (short_inputs / total_samples * 20) +
            (short_outputs / total_samples * 20)
        )
        
        return {
            'quality_score': max(0, quality_score),
            'empty_inputs': empty_inputs,
            'empty_outputs': empty_outputs,
            'short_inputs': short_inputs,
            'short_outputs': short_outputs,
            'issues': issues[:50],  # Max 50 issues affichées
            'total_issues': len(issues)
        }
    
    def _check_duplicates(self, data: List[Dict]) -> Dict:
        """Détecte les doublons"""
        seen_inputs = {}
        seen_outputs = {}
        exact_duplicates = []
        similar_inputs = []
        
        for i, sample in enumerate(data):
            sample_id = sample.get('sample_id', f'sample_{i}')
            input_text = sample.get('input', '').strip().lower()
            output_text = sample.get('output', '').strip().lower()
            
            # Doublons exacts d'input
            if input_text in seen_inputs:
                similar_inputs.append({
                    'sample_id': sample_id,
                    'duplicate_of': seen_inputs[input_text],
                    'text': sample.get('input', '')[:100]
                })
            else:
                seen_inputs[input_text] = sample_id
            
            # Doublons exacts (input + output)
            key = (input_text, output_text)
            if key in exact_duplicates:
                continue
            
            for j in range(i + 1, len(data)):
                other_input = data[j].get('input', '').strip().lower()
                other_output = data[j].get('output', '').strip().lower()
                
                if input_text == other_input and output_text == other_output:
                    exact_duplicates.append({
                        'sample_1': sample_id,
                        'sample_2': data[j].get('sample_id', f'sample_{j}')
                    })
                    break
        
        return {
            'exact_duplicates': len(exact_duplicates),
            'similar_inputs': len(similar_inputs),
            'duplicate_examples': exact_duplicates[:20],
            'similar_examples': similar_inputs[:20]
        }
    
    def _compute_statistics(self, data: List[Dict]) -> Dict:
        """Calcule les statistiques globales"""
        total = len(data)
        
        input_lengths = []
        output_lengths = []
        
        for sample in data:
            input_text = sample.get('input', '')
            output_text = sample.get('output', '')
            
            input_lengths.append(len(input_text))
            output_lengths.append(len(output_text))
        
        return {
            'total_samples': total,
            'input_stats': {
                'min': min(input_lengths) if input_lengths else 0,
                'max': max(input_lengths) if input_lengths else 0,
                'avg': sum(input_lengths) / len(input_lengths) if input_lengths else 0,
                'median': sorted(input_lengths)[len(input_lengths) // 2] if input_lengths else 0
            },
            'output_stats': {
                'min': min(output_lengths) if output_lengths else 0,
                'max': max(output_lengths) if output_lengths else 0,
                'avg': sum(output_lengths) / len(output_lengths) if output_lengths else 0,
                'median': sorted(output_lengths)[len(output_lengths) // 2] if output_lengths else 0
            }
        }


class DatasetVerificationPanel(QWidget):
    """Panel de vérification de datasets générés"""
    
    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        
        self.database = database or DatasetDatabase()
        self.current_verification = None
        self.worker = None
        self.dropdown_svg = get_dropdown_svg_path()
        
        logger.info("🔍 Initialisation DatasetVerificationPanel")
        
        self._init_ui()
        self._load_generations()
    
    def _init_ui(self):
        """Initialise l'interface - 3 colonnes comme dataset_generation.py"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Colonne gauche - Sélection
        left_column = self._create_left_column()
        main_layout.addWidget(left_column, 23)

        # Colonne centrale - Résultats (plus d'espace)
        center_column = self._create_center_column()
        main_layout.addWidget(center_column, 38)

        # Colonne droite - Statistiques
        right_column = self._create_right_column()
        main_layout.addWidget(right_column, 39)

    def _create_left_column(self):
        """Crée la colonne gauche - Sélection du dataset"""
        column = QWidget()
        column.setStyleSheet("background: white; border-right: 2px solid #E0E0E0;")
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Titre
        title = QLabel("Vérification de Dataset")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        layout.addWidget(title)
        
        # Section: Charger un fichier
        file_section = self._create_file_section()
        layout.addWidget(file_section)
        
        layout.addStretch()
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                text-align: center;
                background: #F5F5F5;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)
        
        return column
    
    def _create_file_section(self):
        """Section de sélection unifiée - Historique en haut"""
        group = QGroupBox("Sélection du Dataset")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        layout = QVBoxLayout(group)

        # === HISTORIQUE EN HAUT ===
        history_label = QLabel("Depuis l'historique:")
        history_label.setStyleSheet("font-weight: bold; font-size: 9pt; border: none;")
        layout.addWidget(history_label)

        self.generation_combo = QComboBox()
        self.generation_combo.setMinimumHeight(32)
        self.generation_combo.currentIndexChanged.connect(self._on_generation_selected)
        self._apply_combo_style(self.generation_combo)
        layout.addWidget(self.generation_combo)

        # Info génération - Améliorée
        self.gen_info_label = QLabel("📂 Sélectionnez une génération dans la liste")
        self.gen_info_label.setWordWrap(True)
        self.gen_info_label.setMinimumHeight(40)
        self.gen_info_label.setStyleSheet("""
            color: #555;
            font-size: 9pt;
            padding: 8px 10px;
            background: #F0F4F8;
            border: 1px solid #D0E0F0;
            border-radius: 6px;
        """)
        layout.addWidget(self.gen_info_label)

        # Séparateur
        separator = QLabel("─── ou ───")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("color: #999; font-size: 9pt; border: none; padding: 8px;")
        layout.addWidget(separator)

        # === FICHIER LOCAL ===
        file_label = QLabel("Charger un fichier:")
        file_label.setStyleSheet("font-weight: bold; font-size: 9pt; border: none;")
        layout.addWidget(file_label)

        # Format sur une ligne
        format_row = QHBoxLayout()
        format_row.setSpacing(8)

        format_sublabel = QLabel("Format:")
        format_sublabel.setStyleSheet("font-size: 8pt; color: #666; border: none;")
        format_sublabel.setFixedWidth(50)
        format_row.addWidget(format_sublabel)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "JSONL", "CSV", "Parquet"])
        self.format_combo.setMinimumHeight(32)
        self._apply_combo_style(self.format_combo)
        format_row.addWidget(self.format_combo, 1)

        layout.addLayout(format_row)

        # Fichier sélectionné + Bouton Parcourir côte à côte - Amélioré
        browse_row = QHBoxLayout()
        browse_row.setSpacing(8)

        self.file_label = QLabel("Aucun fichier sélectionné")
        self.file_label.setWordWrap(True)
        self.file_label.setMinimumHeight(40)
        self.file_label.setStyleSheet("""
            color: #555;
            font-size: 9pt;
            padding: 8px 10px;
            background: #F0F4F8;
            border: 1px solid #D0E0F0;
            border-radius: 6px;
        """)
        browse_row.addWidget(self.file_label, 1)

        # Bouton parcourir
        self.browse_btn = QPushButton("📁 Parcourir...")
        self.browse_btn.setMinimumHeight(40)
        self.browse_btn.setMaximumHeight(40)
        self.browse_btn.setMinimumWidth(110)
        self.browse_btn.setMaximumWidth(110)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_file)
        self._apply_button_style(self.browse_btn)
        browse_row.addWidget(self.browse_btn)

        layout.addLayout(browse_row)

        # === BOUTON VÉRIFIER UNIQUE - COMPACT À DROITE ===
        layout.addSpacing(15)

        verify_layout = QHBoxLayout()
        verify_layout.addStretch()

        self.verify_btn = QPushButton("Vérifier")
        self.verify_btn.setMinimumHeight(38)
        self.verify_btn.setMaximumHeight(38)
        self.verify_btn.setMinimumWidth(130)
        self.verify_btn.setMaximumWidth(160)
        self.verify_btn.setCursor(Qt.PointingHandCursor)
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self._verify_dataset)
        self._apply_button_style(self.verify_btn)
        verify_layout.addWidget(self.verify_btn)

        layout.addLayout(verify_layout)

        return group
    
    def _create_history_section(self):
        """Section supprimée - tout est dans file_section maintenant"""
        return None
    
    def _create_quality_widget(self):
        """Widget d'affichage du score de qualité - VERSION COMPACTE LISIBLE"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8F9FA, stop:1 #FFFFFF);
                border: 2px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        widget.setMinimumHeight(90)
        widget.setMaximumHeight(110)
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 12, 10, 12)

        # Score principal
        self.quality_score_label = QLabel("Score: --")
        self.quality_score_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.quality_score_label.setAlignment(Qt.AlignCenter)
        self.quality_score_label.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        self.quality_score_label.setMinimumHeight(25)
        layout.addWidget(self.quality_score_label)

        # Détails
        self.quality_details_label = QLabel("En attente de vérification")
        self.quality_details_label.setAlignment(Qt.AlignCenter)
        self.quality_details_label.setWordWrap(True)
        self.quality_details_label.setMinimumHeight(30)
        self.quality_details_label.setStyleSheet("""
            color: #666; 
            font-size: 9pt; 
            border: none;
        """)
        layout.addWidget(self.quality_details_label)

        return widget
    
    def _create_chart_group(self):
        """Groupe contenant le graphique de distribution - DESIGN AMÉLIORÉ"""
        group = QGroupBox("Distribution des Longueurs")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
                background: white;
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 20, 10, 10)

        # Matplotlib figure avec meilleure résolution
        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: white; border-radius: 6px;")
        layout.addWidget(self.canvas)

        return group
    
    def _create_right_column(self):
        """Crée la colonne droite - Statistiques et visualisations"""
        column = QWidget()
        column.setStyleSheet("background: white; border: none;")
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Titre
        title = QLabel("Statistiques")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        layout.addWidget(title)

        # Graphique de distribution
        chart_group = self._create_chart_group()
        layout.addWidget(chart_group, 1)

        return column
    
    def _create_center_column(self):
        """Crée la colonne centrale - Résultats de vérification"""
        column = QWidget()
        column.setStyleSheet("background: white; border: none;")
        layout = QVBoxLayout(column)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # Titre
        title = QLabel("Résultats")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR}; border: none;")
        layout.addWidget(title)

        # Score de qualité
        self.quality_widget = self._create_quality_widget()
        layout.addWidget(self.quality_widget)

        # Onglets de résultats
        self.results_tabs = QtWidgets.QTabWidget()
        self.results_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background: white;
                margin-top: 2px;
            }}
            QTabBar::tab {{
                background: #F5F5F5;
                color: #666;
                padding: 10px 16px;
                border: 1px solid #E0E0E0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 9pt;
                min-width: 80px;
                min-height: 28px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                font-weight: bold;
                padding-bottom: 12px;
            }}
            QTabBar::tab:hover:!selected {{
                background: #E8E8E8;
            }}
        """)

        # Tab Structure
        self.structure_tab = QTextEdit()
        self.structure_tab.setReadOnly(True)
        self._apply_textedit_style(self.structure_tab)
        self.results_tabs.addTab(self.structure_tab, "Structure")

        # Tab Qualité
        self.quality_tab = QTextEdit()
        self.quality_tab.setReadOnly(True)
        self._apply_textedit_style(self.quality_tab)
        self.results_tabs.addTab(self.quality_tab, "Qualité")

        # Tab Doublons
        self.duplicates_tab = QTextEdit()
        self.duplicates_tab.setReadOnly(True)
        self._apply_textedit_style(self.duplicates_tab)
        self.results_tabs.addTab(self.duplicates_tab, "Doublons")

        layout.addWidget(self.results_tabs, 1)

        # Boutons d'action
        actions = self._create_actions()
        layout.addWidget(actions)

        return column
    
    def _create_actions(self):
        """Crée les boutons d'action - Version compacte"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addStretch()
        
        # Bouton Exporter rapport
        self.export_report_btn = QPushButton("Exporter Rapport")
        self.export_report_btn.setMinimumHeight(32)
        self.export_report_btn.setMaximumHeight(32)
        self.export_report_btn.setCursor(Qt.PointingHandCursor)
        self.export_report_btn.setEnabled(False)
        self.export_report_btn.clicked.connect(self._export_report)
        self._apply_button_style(self.export_report_btn)
        layout.addWidget(self.export_report_btn)
        
        # Bouton Corriger
        self.fix_btn = QPushButton("Corriger les Problèmes")
        self.fix_btn.setMinimumHeight(32)
        self.fix_btn.setMaximumHeight(32)
        self.fix_btn.setCursor(Qt.PointingHandCursor)
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self._fix_issues)
        self._apply_button_style(self.fix_btn)
        layout.addWidget(self.fix_btn)
        
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
                border: none;
                border-left: 1px solid #E0E0E0;
                width: 32px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: #FAFAFA;
            }}
            QComboBox::down-arrow {{
                image: url({self.dropdown_svg});
                width: 16px;
                height: 16px;
            }}
        """)
    
    def _apply_button_style(self, button):
        """Applique le style aux boutons - Version compacte"""
        button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 9pt;
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
    
    def _apply_textedit_style(self, textedit):
        """Applique le style aux QTextEdit - LISIBLE"""
        textedit.setStyleSheet("""
            QTextEdit {
                border: none;
                background: transparent;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                padding: 10px;
                line-height: 1.4;
            }
        """)
    
    def _load_generations(self):
        """Charge les générations depuis la base"""
        self.generation_combo.clear()
        self.generation_combo.addItem("Sélectionner une génération", None)
        
        try:
            generations = self.database.get_all_generations(limit=50)
            
            for gen in generations:
                if gen.get('status') == 'completed' and gen.get('output_file_path'):
                    project = gen.get('project_name', 'N/A')
                    batch = gen.get('batch_name', f"Batch {gen.get('batch_number', '?')}")
                    date = gen.get('started_at', '')
                    
                    if date:
                        try:
                            date_obj = datetime.fromisoformat(date)
                            date_str = date_obj.strftime("%d/%m/%Y")
                        except:
                            date_str = date[:10]
                    else:
                        date_str = "N/A"
                    
                    display = f"{project} - {batch} - {date_str}"
                    self.generation_combo.addItem(display, gen)
            
            logger.info(f"✅ {len(generations)} génération(s) chargée(s)")
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement générations: {e}")
    
    def _browse_file(self):
        """Ouvre le dialogue de sélection de fichier"""
        file_format = self.format_combo.currentText()
        
        extensions = {
            'JSON': 'JSON (*.json)',
            'JSONL': 'JSONL (*.jsonl)',
            'CSV': 'CSV (*.csv)',
            'Parquet': 'Parquet (*.parquet)'
        }
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un Dataset",
            "",
            extensions.get(file_format, "Tous les fichiers (*.*)")
        )
        
        if file_path:
            self.file_label.setText(os.path.basename(file_path))
            self.current_file_path = file_path
            
            # Réinitialiser la sélection historique
            self.generation_combo.setCurrentIndex(0)
            self.current_history_path = None
            
            self._check_verify_button_state()
            logger.info(f"Fichier sélectionné: {file_path}")
    
    def _on_generation_selected(self, index):
        """Gère la sélection d'une génération"""
        gen_data = self.generation_combo.currentData()
        
        if not gen_data:
            self.gen_info_label.setText("Sélectionnez une génération")
            self._check_verify_button_state()
            return
        
        # Afficher les infos
        samples = gen_data.get('total_samples', 0)
        format_type = gen_data.get('output_format', 'N/A')
        file_path = gen_data.get('output_file_path', '')
        
        info = f"{samples} samples • {format_type}"
        
        if file_path and os.path.exists(file_path):
            info += " • Disponible"
            self.current_history_path = file_path
            self.current_history_format = format_type
        else:
            info += " • Fichier introuvable"
            self.current_history_path = None
            self.current_history_format = None
        
        self.gen_info_label.setText(info)
        self._check_verify_button_state()
    
    def _check_verify_button_state(self):
        """Vérifie si le bouton Vérifier doit être activé"""
        has_file = hasattr(self, 'current_file_path') and bool(self.current_file_path)
        has_history = hasattr(self, 'current_history_path') and bool(self.current_history_path)
        
        self.verify_btn.setEnabled(bool(has_file or has_history))
    
    def _verify_dataset(self):
        """Lance la vérification (fichier ou historique)"""
        # Priorité au fichier local si les deux sont sélectionnés
        if hasattr(self, 'current_file_path') and self.current_file_path:
            file_path = self.current_file_path
            file_format = self.format_combo.currentText()
        elif hasattr(self, 'current_history_path') and self.current_history_path:
            file_path = self.current_history_path
            file_format = self.current_history_format
        else:
            QMessageBox.warning(self, "Attention", "Aucun dataset sélectionné")
            return
        
        self._start_verification(file_path, file_format)
    
    def _start_verification(self, file_path, file_format):
        """Démarre le worker de vérification"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 DÉMARRAGE VÉRIFICATION")
        logger.info(f"{'='*80}")
        logger.info(f"  Fichier: {file_path}")
        logger.info(f"  Format: {file_format}")
        
        # Désactiver les contrôles
        self.browse_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        self.generation_combo.setEnabled(False)
        
        # Afficher la progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(5)
        
        # Créer et démarrer le worker
        self.worker = DatasetVerificationWorker(file_path, file_format)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.verification_completed.connect(self._on_verification_completed)
        self.worker.verification_failed.connect(self._on_verification_failed)
        self.worker.start()
    
    def _on_progress_updated(self, current, total, message):
        """Met à jour la progression"""
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{message} ({current}/{total})")
    
    def _on_verification_completed(self, result):
        """Gère la fin de vérification"""
        logger.info("✅ Vérification terminée")
        
        self.current_verification = result
        
        # Réactiver les contrôles
        self.browse_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)
        self.generation_combo.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # Afficher les résultats
        self._display_results(result)
        
        # Activer les boutons d'export
        self.export_report_btn.setEnabled(True)
        
        # Activer le bouton de correction si nécessaire
        quality = result.get('quality', {})
        duplicates = result.get('duplicates', {})
        
        has_issues = (
            quality.get('total_issues', 0) > 0 or
            duplicates.get('exact_duplicates', 0) > 0
        )
        
        self.fix_btn.setEnabled(has_issues)
        
        QMessageBox.information(
            self,
            "Vérification Terminée",
            f"Le dataset a été vérifié avec succès.\n\n"
            f"Score de qualité: {quality.get('quality_score', 0):.1f}/100"
        )
    
    def _on_verification_failed(self, error):
        """Gère l'échec de vérification"""
        logger.error(f"❌ Vérification échouée: {error}")
        
        # Réactiver les contrôles
        self.browse_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)
        self.generation_combo.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(
            self,
            "Erreur de Vérification",
            f"La vérification a échoué:\n\n{error}"
        )
    
    def _display_results(self, result):
        """Affiche les résultats de vérification"""
        # Score de qualité
        quality = result.get('quality', {})
        score = quality.get('quality_score', 0)

        self.quality_score_label.setText(f"Score: {score:.1f}/100")

        # Couleur selon le score
        if score >= 90:
            color = "#4CAF50"  # Vert
            status = "Excellent ✓"
        elif score >= 75:
            color = "#8BC34A"  # Vert clair
            status = "Bon"
        elif score >= 50:
            color = "#FFC107"  # Orange
            status = "Moyen"
        else:
            color = "#F44336"  # Rouge
            status = "Faible"

        self.quality_score_label.setStyleSheet(f"""
            color: {color}; 
            border: none; 
            font-size: 14pt; 
            font-weight: bold;
        """)

        # Détails plus compacts
        total_issues = quality.get('total_issues', 0)
        if total_issues == 0:
            detail_text = f"{status} • Aucun problème"
        elif total_issues == 1:
            detail_text = f"{status} • 1 problème"
        else:
            detail_text = f"{status} • {total_issues} problèmes"

        self.quality_details_label.setText(detail_text)

        # Tab Structure
        self._display_structure_tab(result.get('structure', {}))

        # Tab Qualité
        self._display_quality_tab(quality)

        # Tab Doublons
        self._display_duplicates_tab(result.get('duplicates', {}))

        # Graphique
        self._display_chart(result.get('statistics', {}))
    
    def _display_structure_tab(self, structure):
        """Affiche l'onglet structure"""
        text = "=== STRUCTURE DU DATASET ===\n\n"
        
        if structure.get('valid'):
            text += "✅ Structure valide\n\n"
        else:
            text += "❌ Structure invalide\n\n"
        
        text += f"Total samples: {structure.get('total_samples', 0)}\n\n"
        
        text += "Champs présents:\n"
        for field in structure.get('fields', []):
            text += f"  • {field}\n"
        
        text += "\nChamps requis:\n"
        for field in structure.get('required_fields', []):
            text += f"  • {field}\n"
        
        if structure.get('missing_fields'):
            text += "\n⚠️ Champs manquants:\n"
            for field in structure['missing_fields']:
                text += f"  ❌ {field}\n"
        
        if structure.get('extra_fields'):
            text += "\nℹ️ Champs supplémentaires:\n"
            for field in structure['extra_fields']:
                text += f"  • {field}\n"
        
        if structure.get('inconsistent_samples'):
            text += f"\n⚠️ {len(structure['inconsistent_samples'])} sample(s) avec structure incohérente\n"
            text += "Exemples:\n"
            for idx in structure['inconsistent_samples'][:5]:
                text += f"  • Sample #{idx}\n"
        
        self.structure_tab.setPlainText(text)
    
    def _display_quality_tab(self, quality):
        """Affiche l'onglet qualité"""
        text = "=== ANALYSE DE QUALITÉ ===\n\n"
        
        score = quality.get('quality_score', 0)
        text += f"Score global: {score:.1f}/100\n\n"
        
        text += "Problèmes détectés:\n"
        text += f"  • Inputs vides: {quality.get('empty_inputs', 0)}\n"
        text += f"  • Outputs vides: {quality.get('empty_outputs', 0)}\n"
        text += f"  • Inputs courts (<10 car): {quality.get('short_inputs', 0)}\n"
        text += f"  • Outputs courts (<10 car): {quality.get('short_outputs', 0)}\n"
        
        issues = quality.get('issues', [])
        if issues:
            text += f"\n📋 Détails des problèmes (max 50):\n\n"
            
            for issue in issues[:50]:
                text += f"Sample: {issue['sample_id']}\n"
                text += f"  Type: {issue['type']}\n"
                text += f"  Message: {issue['message']}\n\n"
        
        total = quality.get('total_issues', 0)
        if total > 50:
            text += f"\n... et {total - 50} autre(s) problème(s)\n"
        
        self.quality_tab.setPlainText(text)
    
    def _display_duplicates_tab(self, duplicates):
        """Affiche l'onglet doublons"""
        text = "=== DÉTECTION DES DOUBLONS ===\n\n"
        
        exact = duplicates.get('exact_duplicates', 0)
        similar = duplicates.get('similar_inputs', 0)
        
        text += f"🔄 Doublons exacts (input + output): {exact}\n"
        text += f"🔄 Inputs similaires: {similar}\n\n"
        
        if exact > 0:
            text += "Exemples de doublons exacts:\n\n"
            for dup in duplicates.get('duplicate_examples', [])[:20]:
                text += f"  • {dup['sample_1']} ↔ {dup['sample_2']}\n"
        
        if similar > 0:
            text += "\nExemples d'inputs similaires:\n\n"
            for sim in duplicates.get('similar_examples', [])[:20]:
                text += f"Sample: {sim['sample_id']}\n"
                text += f"  Doublon de: {sim['duplicate_of']}\n"
                text += f"  Texte: {sim['text']}\n\n"
        
        if exact == 0 and similar == 0:
            text += "✅ Aucun doublon détecté"
        
        self.duplicates_tab.setPlainText(text)

    def _display_chart(self, stats):
        """Affiche le graphique de distribution - DESIGN MODERNE"""
        self.figure.clear()

        input_stats = stats.get('input_stats', {})
        output_stats = stats.get('output_stats', {})

        # Créer le subplot avec fond transparent
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#FAFAFA')
        self.figure.patch.set_facecolor('white')

        categories = ['Min', 'Médiane', 'Moyenne', 'Max']
        input_values = [
            input_stats.get('min', 0),
            input_stats.get('median', 0),
            input_stats.get('avg', 0),
            input_stats.get('max', 0)
        ]
        output_values = [
            output_stats.get('min', 0),
            output_stats.get('median', 0),
            output_stats.get('avg', 0),
            output_stats.get('max', 0)
        ]

        x = range(len(categories))
        width = 0.38

        # Barres avec dégradé et bordures
        bars1 = ax.bar([i - width/2 for i in x], input_values, width, 
                        label='Input', 
                        color=Theme.PRIMARY_COLOR,
                        edgecolor='white',
                        linewidth=1.5,
                        alpha=0.9)

        bars2 = ax.bar([i + width/2 for i in x], output_values, width, 
                        label='Output', 
                        color=Theme.SECONDARY_COLOR,
                        edgecolor='white',
                        linewidth=1.5,
                        alpha=0.9)

        # Ajouter les valeurs sur les barres
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}',
                           ha='center', va='bottom',
                           fontsize=8, fontweight='bold',
                           color='#333333')

        # Style des axes
        ax.set_xlabel('Statistique', fontsize=10, fontweight='bold', color='#555555')
        ax.set_ylabel('Longueur (caractères)', fontsize=10, fontweight='bold', color='#555555')
        ax.set_title('Distribution des Longueurs Input/Output', 
                     fontsize=11, fontweight='bold', 
                     color=Theme.PRIMARY_COLOR, pad=15)

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9, color='#555555')
        ax.tick_params(axis='y', labelsize=9, colors='#555555')

        # Légende stylée
        legend = ax.legend(loc='upper left', frameon=True, fontsize=9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('#E0E0E0')
        legend.get_frame().set_linewidth(1.5)
        legend.get_frame().set_alpha(0.95)

        # Grille améliorée
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.8, color='#CCCCCC')
        ax.set_axisbelow(True)

        # Bordure du graphique
        for spine in ax.spines.values():
            spine.set_edgecolor('#D0D0D0')
            spine.set_linewidth(1.2)

        self.figure.tight_layout(pad=1.5)
        self.canvas.draw()
    
    def _export_report(self):
        """Exporte le rapport de vérification"""
        if not self.current_verification:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le Rapport",
            f"rapport_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json);;Texte (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                # Export JSON
                export_data = {
                    'verification_date': self.current_verification['timestamp'],
                    'file': self.current_verification['file_path'],
                    'format': self.current_verification['file_format'],
                    'results': {
                        'structure': self.current_verification['structure'],
                        'quality': self.current_verification['quality'],
                        'duplicates': self.current_verification['duplicates'],
                        'statistics': self.current_verification['statistics']
                    }
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            else:
                # Export TXT
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("="*80 + "\n")
                    f.write("RAPPORT DE VÉRIFICATION DE DATASET\n")
                    f.write("="*80 + "\n\n")
                    
                    f.write(f"Date: {self.current_verification['timestamp']}\n")
                    f.write(f"Fichier: {self.current_verification['file_path']}\n")
                    f.write(f"Format: {self.current_verification['file_format']}\n\n")
                    
                    f.write(self.structure_tab.toPlainText() + "\n\n")
                    f.write(self.quality_tab.toPlainText() + "\n\n")
                    f.write(self.duplicates_tab.toPlainText() + "\n\n")
            
            QMessageBox.information(
                self,
                "✅ Export Réussi",
                f"Rapport exporté vers:\n{file_path}"
            )
            
            logger.info(f"✅ Rapport exporté: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Erreur export: {e}")
            QMessageBox.critical(
                self,
                "❌ Erreur d'Export",
                f"Impossible d'exporter le rapport:\n\n{str(e)}"
            )
    
    def _fix_issues(self):
        """Ouvre le dialogue de correction des problèmes"""
        if not self.current_verification:
            return
        
        quality = self.current_verification.get('quality', {})
        duplicates = self.current_verification.get('duplicates', {})
        
        msg = "Problèmes détectés:\n\n"
        
        if quality.get('empty_inputs', 0) > 0:
            msg += f"• {quality['empty_inputs']} input(s) vide(s)\n"
        if quality.get('empty_outputs', 0) > 0:
            msg += f"• {quality['empty_outputs']} output(s) vide(s)\n"
        if duplicates.get('exact_duplicates', 0) > 0:
            msg += f"• {duplicates['exact_duplicates']} doublon(s) exact(s)\n"
        
        msg += "\nActions possibles:\n"
        msg += "• Supprimer les samples avec problèmes\n"
        msg += "• Supprimer les doublons\n"
        msg += "• Exporter un dataset nettoyé\n\n"
        msg += "Souhaitez-vous nettoyer le dataset ?"
        
        reply = QMessageBox.question(
            self,
            "🔧 Corriger les Problèmes",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._clean_dataset()
    
    def _clean_dataset(self):
        """Nettoie le dataset en supprimant les problèmes"""
        try:
            data = self.current_verification.get('data', [])
            original_count = len(data)
            
            # Supprimer les samples avec inputs/outputs vides
            cleaned_data = []
            seen = set()
            
            for sample in data:
                input_text = sample.get('input', '').strip()
                output_text = sample.get('output', '').strip()
                
                # Ignorer les vides
                if not input_text or not output_text:
                    continue
                
                # Ignorer les doublons exacts
                key = (input_text.lower(), output_text.lower())
                if key in seen:
                    continue
                
                seen.add(key)
                cleaned_data.append(sample)
            
            removed_count = original_count - len(cleaned_data)
            
            # Demander où sauvegarder
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Enregistrer le Dataset Nettoyé",
                f"dataset_cleaned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON (*.json);;JSONL (*.jsonl)"
            )
            
            if not file_path:
                return
            
            # Sauvegarder
            if file_path.endswith('.jsonl'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    for sample in cleaned_data:
                        f.write(json.dumps(sample, ensure_ascii=False) + '\n')
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(
                self,
                "✅ Nettoyage Terminé",
                f"Dataset nettoyé avec succès!\n\n"
                f"Original: {original_count} samples\n"
                f"Nettoyé: {len(cleaned_data)} samples\n"
                f"Supprimés: {removed_count} samples\n\n"
                f"Sauvegardé vers:\n{file_path}"
            )
            
            logger.info(f"✅ Dataset nettoyé: {removed_count} samples supprimés")
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage: {e}")
            QMessageBox.critical(
                self,
                "❌ Erreur",
                f"Impossible de nettoyer le dataset:\n\n{str(e)}"
            )
    
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        self._load_generations()