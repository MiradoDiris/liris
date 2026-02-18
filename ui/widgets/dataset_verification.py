#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dataset Verification Panel - AMÉLIORÉ avec API + Feedback Utilisateur
- Intégration API de vérification (RL + RLHF)
- Interface de feedback humain
- Validation en temps réel
- Export des résultats
"""

import json
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QProgressBar, QGroupBox, QMessageBox, 
    QFileDialog, QFrame, QTabWidget, QScrollArea, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QCheckBox, QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QFont, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui.styles.theme import Theme
from utils.logger import logger
from utils.dataset_database import DatasetDatabase


# ============================================================================
# CONFIGURATION API
# ============================================================================

API_BASE_URL = "http://localhost:8086"

class ValidationLevel:
    QUICK = "quick"
    STANDARD = "standard"
    STRICT = "strict"


# ============================================================================
# WORKER DE VÉRIFICATION VIA API
# ============================================================================

class APIVerificationWorker(QThread):
    """Worker pour vérification via API"""
    
    progress_updated = pyqtSignal(int, int, str)
    verification_completed = pyqtSignal(dict)
    verification_failed = pyqtSignal(str)
    
    def __init__(self, file_path, file_format, validation_level, rlhf_enabled):
        super().__init__()
        self.file_path = file_path
        self.file_format = file_format
        self.validation_level = validation_level
        self.rlhf_enabled = rlhf_enabled
        
    def run(self):
        """Execute la vérification via API"""
        try:
            logger.info(f"Début vérification API: {self.file_path}")
            
            # Charger les données
            self.progress_updated.emit(1, 4, "Chargement du fichier...")
            data = self._load_data()
            
            if not data:
                raise ValueError("Impossible de charger les données")
            
            # Vérifier connexion API
            self.progress_updated.emit(2, 4, "Connexion à l'API...")
            if not self._check_api_health():
                raise ConnectionError("API de vérification non disponible")
            
            # Envoyer à l'API
            self.progress_updated.emit(3, 4, "Vérification en cours...")
            api_result = self._verify_via_api(data)
            
            # Finalisation
            self.progress_updated.emit(4, 4, "Finalisation...")
            
            result = {
                'file_path': self.file_path,
                'file_format': self.file_format,
                'validation_level': self.validation_level,
                'rlhf_enabled': self.rlhf_enabled,
                'api_result': api_result,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            
            self.verification_completed.emit(result)
            logger.info("Vérification API terminée")
            
        except Exception as e:
            error_msg = f"Erreur lors de la vérification API: {str(e)}"
            logger.error(f"{error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            self.verification_failed.emit(error_msg)
    
    def _check_api_health(self) -> bool:
        """Vérifie la santé de l'API"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _verify_via_api(self, data: List[Dict]) -> Dict:
        """Envoie les données à l'API"""
        payload = {
            "samples": data,
            "validation_level": self.validation_level,
            "rlhf_validation": self.rlhf_enabled,
            "auto_fix": False
        }
        
        response = requests.post(
            f"{API_BASE_URL}/verify",
            json=payload,
            timeout=1200  # 5 minutes max
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
        
        return response.json()
    
    def _load_data(self) -> List[Dict]:
        """Charge les données selon le format"""
        if self.file_format == 'JSON':
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
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


# ============================================================================
# DIALOGUE DE FEEDBACK UTILISATEUR
# ============================================================================

class FeedbackDialog(QDialog):
    """Dialogue pour le feedback utilisateur sur un sample"""
    
    def __init__(self, sample_result: Dict, parent=None):
        super().__init__(parent)
        self.sample_result = sample_result
        self.feedback_data = {}
        
        self.setWindowTitle("Feedback Utilisateur")
        self.setMinimumSize(700, 600)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Titre
        title = QLabel("Validation du Sample")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #000000;")
        layout.addWidget(title)
        
        # Infos sample
        info_group = QGroupBox("Informations")
        info_layout = QVBoxLayout(info_group)
        
        sample_id = self.sample_result.get('sample_id', 'N/A')
        status = self.sample_result.get('status', 'unknown')
        score = self.sample_result.get('quality_score', 0)
        
        info_text = f"Sample ID: {sample_id}\n"
        info_text += f"Statut actuel: {status}\n"
        info_text += f"Score qualité: {score:.1f}/100"
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet("padding: 10px; background: #F5F5F5; border-radius: 4px;")
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        
        # Textes
        text_group = QGroupBox("Contenu")
        text_layout = QVBoxLayout(text_group)
        
        input_label = QLabel("Input:")
        input_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        input_label.setStyleSheet("color: #000000;")
        text_layout.addWidget(input_label)
        
        input_text = QTextEdit()
        input_text.setReadOnly(True)
        input_text.setMinimumHeight(60)
        input_text.setMaximumHeight(80)
        input_text.setPlainText(self.sample_result.get('input_text', ''))
        input_text.setStyleSheet("background: #FAFAFA; border: 1px solid #DDD;")
        text_layout.addWidget(input_text)
        
        output_label = QLabel("Output:")
        output_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        output_label.setStyleSheet("color: #000000;")
        text_layout.addWidget(output_label)
        
        self.output_text = QTextEdit()
        self.output_text.setMinimumHeight(80)
        self.output_text.setMaximumHeight(120)
        self.output_text.setPlainText(self.sample_result.get('output_text', ''))
        self.output_text.setStyleSheet("background: white; border: 2px solid #4CAF50;")
        text_layout.addWidget(self.output_text)
        
        hint = QLabel("Vous pouvez modifier l'output directement ci-dessus")
        hint.setStyleSheet("color: #666; font-size: 8pt; font-style: italic;")
        text_layout.addWidget(hint)
        
        layout.addWidget(text_group)
        
        # Issues détectées
        issues = self.sample_result.get('issues', [])
        if issues:
            issues_group = QGroupBox(f"Problèmes détectés ({len(issues)})")
            issues_layout = QVBoxLayout(issues_group)
            
            issues_text = ""
            for issue in issues[:5]:  # Max 5
                severity = issue.get('severity', 'info')
                issues_text += f"{issue.get('message', '')}\n"
            
            issues_label = QLabel(issues_text)
            issues_label.setWordWrap(True)
            issues_label.setStyleSheet("padding: 10px; background: #FFF3E0; border-radius: 4px;")
            issues_layout.addWidget(issues_label)
            
            layout.addWidget(issues_group)
        
        # Décision utilisateur
        decision_group = QGroupBox("Votre Décision")
        decision_layout = QVBoxLayout(decision_group)
        
        self.decision_group = QButtonGroup(self)
        
        self.valid_radio = QRadioButton("Valider ce sample")
        self.invalid_radio = QRadioButton("Rejeter ce sample")
        self.review_radio = QRadioButton("Nécessite une révision")
        
        self.decision_group.addButton(self.valid_radio, 1)
        self.decision_group.addButton(self.invalid_radio, 2)
        self.decision_group.addButton(self.review_radio, 3)
        
        # Pré-sélectionner selon le statut
        if status == "valid":
            self.valid_radio.setChecked(True)
        elif status == "invalid":
            self.invalid_radio.setChecked(True)
        else:
            self.review_radio.setChecked(True)
        
        decision_layout.addWidget(self.valid_radio)
        decision_layout.addWidget(self.invalid_radio)
        decision_layout.addWidget(self.review_radio)
        
        layout.addWidget(decision_group)
        
        # Commentaires
        comment_group = QGroupBox("Commentaires (optionnel)")
        comment_layout = QVBoxLayout(comment_group)
        
        self.comment_text = QTextEdit()
        self.comment_text.setMinimumHeight(50)
        self.comment_text.setMaximumHeight(80)
        self.comment_text.setPlaceholderText("Ajoutez vos commentaires ici...")
        comment_layout.addWidget(self.comment_text)
        
        layout.addWidget(comment_group)
        
        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _on_submit(self):
        """Soumission du feedback"""
        # Récupérer la décision
        if self.valid_radio.isChecked():
            decision = "valid"
        elif self.invalid_radio.isChecked():
            decision = "invalid"
        else:
            decision = "needs_review"
        
        # Construire le feedback
        self.feedback_data = {
            'sample_id': self.sample_result.get('sample_id'),
            'user_decision': decision,
            'user_comments': self.comment_text.toPlainText(),
            'corrected_output': self.output_text.toPlainText(),
            'timestamp': datetime.now().isoformat()
        }
        
        self.accept()
    
    def get_feedback(self) -> Dict:
        """Retourne le feedback"""
        return self.feedback_data


# ============================================================================
# WIDGET DE RÉSULTATS DÉTAILLÉS
# ============================================================================

class DetailedResultsWidget(QWidget):
    """Widget pour afficher les résultats détaillés avec feedback"""
    
    feedback_submitted = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_results = []
        self.feedbacks = []
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Barre d'outils
        toolbar = QHBoxLayout()
        
        toolbar_label = QLabel("Résultats Détaillés")
        toolbar_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        toolbar_label.setStyleSheet("color: #000000;")
        toolbar.addWidget(toolbar_label)
        
        toolbar.addStretch()
        
        # Filtres
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Tous", "Valides", "Warnings", "Invalides"
        ])
        self.filter_combo.setMinimumHeight(28)
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Filtre:"))
        toolbar.addWidget(self.filter_combo)
        
        # Export
        export_btn = QPushButton("Exporter")
        export_btn.setMinimumHeight(28)
        export_btn.clicked.connect(self._export_results)
        toolbar.addWidget(export_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Statut", "Score", "Input", "Output", "Issues", "Actions"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        
        # Réduire au maximum les colonnes fixes pour donner plus d'espace aux Input/Output
        self.table.setColumnWidth(0, 35)   # ID - minimum
        self.table.setColumnWidth(1, 70)   # Statut
        self.table.setColumnWidth(2, 45)   # Score
        self.table.setColumnWidth(5, 45)   # Issues
        self.table.setColumnWidth(6, 90)   # Actions
        
        # Définir une largeur minimale pour les colonnes Stretch
        self.table.horizontalHeader().setMinimumSectionSize(200)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)  # Masquer les numéros de lignes
        self.table.verticalHeader().setDefaultSectionSize(32)  # Hauteur de ligne réduite
        self.table.setWordWrap(True)  # Activer le retour à la ligne
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #E0E0E0;
                border: 1px solid #CCCCCC;
            }
            QTableWidget::item {
                padding: 2px 4px;
                color: #000000;
            }
            QTableWidget::item:alternate {
                background-color: #FAFAFA;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                padding: 4px;
                border: none;
                border-bottom: 2px solid #DDDDDD;
                font-weight: bold;
                color: #333333;
                font-size: 9pt;
            }
        """)
        
        layout.addWidget(self.table)
    
    def load_results(self, results: List[Dict]):
        """Charge les résultats"""
        self.current_results = results
        self._populate_table(results)
    
    def _populate_table(self, results: List[Dict]):
        """Remplit la table"""
        self.table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # ID
            id_item = QTableWidgetItem(str(result.get('sample_id', row)))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setForeground(QColor("#000000"))
            self.table.setItem(row, 0, id_item)
            
            # Statut
            status = result.get('status', 'unknown')
            status_item = QTableWidgetItem(status.upper())
            status_item.setTextAlignment(Qt.AlignCenter)
            
            # Couleurs avec fond subtil + texte coloré pour meilleure distinction
            if status == 'valid':
                status_item.setBackground(QColor("#E8F5E9"))  # Vert très clair
                status_item.setForeground(QColor("#2E7D32"))  # Vert foncé
                status_item.setData(Qt.ForegroundRole, QColor("#2E7D32"))
            elif status == 'warning':
                status_item.setBackground(QColor("#FFF8E1"))  # Jaune très clair
                status_item.setForeground(QColor("#F57C00"))  # Orange foncé
                status_item.setData(Qt.ForegroundRole, QColor("#F57C00"))
            else:
                status_item.setBackground(QColor("#FFEBEE"))  # Rouge très clair
                status_item.setForeground(QColor("#C62828"))  # Rouge foncé
                status_item.setData(Qt.ForegroundRole, QColor("#C62828"))
            
            self.table.setItem(row, 1, status_item)
            
            # Score
            score = result.get('quality_score', 0)
            score_item = QTableWidgetItem(f"{score:.1f}")
            score_item.setTextAlignment(Qt.AlignCenter)
            score_item.setForeground(QColor("#000000"))
            self.table.setItem(row, 2, score_item)
            
            # Input
            input_text = result.get('input_text', '')[:100]  # Augmenter à 100 caractères
            if len(result.get('input_text', '')) > 100:
                input_text += "..."
            input_item = QTableWidgetItem(input_text)
            input_item.setForeground(QColor("#000000"))
            self.table.setItem(row, 3, input_item)
            
            # Output
            output_text = result.get('output_text', '')[:100]  # Augmenter à 100 caractères
            if len(result.get('output_text', '')) > 100:
                output_text += "..."
            output_item = QTableWidgetItem(output_text)
            output_item.setForeground(QColor("#000000"))
            self.table.setItem(row, 4, output_item)
            
            # Issues
            issues_count = len(result.get('issues', []))
            issues_item = QTableWidgetItem(str(issues_count))
            issues_item.setTextAlignment(Qt.AlignCenter)
            issues_item.setForeground(QColor("#000000"))
            self.table.setItem(row, 5, issues_item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 0, 4, 0)
            actions_layout.setSpacing(0)
            
            feedback_btn = QPushButton("Feedback")
            feedback_btn.setToolTip("Donner un feedback sur ce sample")
            feedback_btn.setFixedHeight(22)
            feedback_btn.setFixedWidth(78)
            feedback_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F5F5F5;
                    color: #333333;
                    border: 1px solid #CCCCCC;
                    border-radius: 3px;
                    padding: 2px 4px;
                    font-size: 8pt;
                }
                QPushButton:hover {
                    background-color: #E0E0E0;
                    border-color: #999999;
                }
                QPushButton:pressed {
                    background-color: #D0D0D0;
                }
            """)
            feedback_btn.clicked.connect(lambda checked, r=result: self._show_feedback_dialog(r))
            
            actions_layout.addWidget(feedback_btn)
            
            self.table.setCellWidget(row, 6, actions_widget)
        
        self.table.resizeRowsToContents()
    
    def _apply_filter(self, filter_text: str):
        """Applique un filtre"""
        if filter_text == "Tous":
            filtered = self.current_results
        elif filter_text == "Valides":
            filtered = [r for r in self.current_results if r.get('status') == 'valid']
        elif filter_text == "Warnings":
            filtered = [r for r in self.current_results if r.get('status') == 'warning']
        else:  # Invalides
            filtered = [r for r in self.current_results if r.get('status') == 'invalid']
        
        self._populate_table(filtered)
    
    def _show_feedback_dialog(self, result: Dict):
        """Affiche le dialogue de feedback"""
        dialog = FeedbackDialog(result, self)
        
        if dialog.exec_() == QDialog.Accepted:
            feedback = dialog.get_feedback()
            self.feedbacks.append(feedback)
            self.feedback_submitted.emit(feedback)
            
            QMessageBox.information(
                self,
                "Feedback Enregistré",
                "Votre feedback a été enregistré avec succès."
            )
    
    def _export_results(self):
        """Exporte les résultats"""
        if not self.current_results:
            QMessageBox.warning(self, "Attention", "Aucun résultat à exporter")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les résultats",
            f"verification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            export_data = {
                'results': self.current_results,
                'feedbacks': self.feedbacks,
                'export_date': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(
                self,
                "Export Réussi",
                f"Résultats exportés vers:\n{file_path}"
            )


# ============================================================================
# PANEL PRINCIPAL DE VÉRIFICATION
# ============================================================================

class DatasetVerificationPanel(QWidget):
    """Panel de vérification AMÉLIORÉ avec API + Feedback"""
    
    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        
        self.database = database or DatasetDatabase()
        self.current_verification = None
        self.worker = None
        
        logger.info("Initialisation DatasetVerificationPanel - Version API + Feedback")
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Onglets
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: white;
            }}
            QTabBar::tab {{
                background: #F5F5F5;
                color: #666;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: white;
                color: {Theme.PRIMARY_COLOR};
                border-bottom: 3px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        
        # Onglet Configuration
        config_tab = self._create_config_tab()
        self.tabs.addTab(config_tab, "Configuration")
        
        # Onglet Résultats
        self.results_widget = DetailedResultsWidget()
        self.results_widget.feedback_submitted.connect(self._on_feedback_submitted)
        self.tabs.addTab(self.results_widget, "Résultats Détaillés")
        
        # Onglet Visualisation
        viz_tab = self._create_visualization_tab()
        self.tabs.addTab(viz_tab, "Visualisations")
        
        main_layout.addWidget(self.tabs)
    
    def _create_config_tab(self):
        """Crée l'onglet de configuration"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Colonne gauche - Configuration
        left_col = self._create_config_column()
        layout.addWidget(left_col, 40)
        
        # Colonne droite - Aperçu
        right_col = self._create_preview_column()
        layout.addWidget(right_col, 60)
        
        return widget
    
    def _create_config_column(self):
        """Colonne de configuration"""
        widget = QWidget()
        widget.setStyleSheet("background: white; border-right: 2px solid #E0E0E0;")
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Titre
        title = QLabel("Configuration de la Vérification")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #000000;")
        layout.addWidget(title)
        
        # Source de données
        source_group = self._create_data_source_section()
        layout.addWidget(source_group)
        
        # Options de validation
        options_group = self._create_validation_options()
        layout.addWidget(options_group)
        
        layout.addStretch()
        
        # Bouton de lancement
        self.verify_btn = QPushButton("Lancer la Vérification")
        self.verify_btn.setMinimumHeight(50)
        self.verify_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self._verify_dataset)
        self.verify_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 8px;
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
        layout.addWidget(self.verify_btn)
        
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
        
        return widget
    
    def _create_data_source_section(self):
        """Section de sélection de la source"""
        group = QGroupBox("Source de Données")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setStyleSheet("QGroupBox { color: #000000; }")
        layout = QVBoxLayout(group)
        
        # Format et Fichier en horizontal
        format_file_layout = QHBoxLayout()
        
        # Format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "JSONL", "CSV", "Parquet"])
        self.format_combo.setMinimumHeight(32)
        format_file_layout.addWidget(self.format_combo)
        
        # Fichier
        self.file_label = QLabel("Aucun fichier sélectionné")
        self.file_label.setStyleSheet("padding: 8px; background: #F0F4F8; border-radius: 4px;")
        format_file_layout.addWidget(self.file_label, 1)
        
        # Bouton Parcourir
        browse_btn = QPushButton("Parcourir")
        browse_btn.setMinimumHeight(32)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
        """)
        browse_btn.clicked.connect(self._browse_file)
        format_file_layout.addWidget(browse_btn)
        
        layout.addLayout(format_file_layout)
        
        return group
    
    def _create_validation_options(self):
        """Options de validation"""
        group = QGroupBox("Options de Validation")
        group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        group.setStyleSheet("QGroupBox { color: #000000; }")
        layout = QVBoxLayout(group)
        
        # Niveau de validation
        level_label = QLabel("Niveau de validation:")
        layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "Quick - Rapide (RL uniquement)",
            "Standard - Recommandé (RL + RLHF basique)",
            "Strict - Complet (RL + RLHF avancé)"
        ])
        self.level_combo.setCurrentIndex(1)
        self.level_combo.setMinimumHeight(32)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        layout.addWidget(self.level_combo)
        
        # RLHF
        self.rlhf_check = QCheckBox("Activer la validation RLHF intelligente")
        self.rlhf_check.setChecked(True)
        self.rlhf_check.toggled.connect(self._on_rlhf_toggled)
        layout.addWidget(self.rlhf_check)
        
        # Description
        self.level_desc = QLabel()
        self.level_desc.setWordWrap(True)
        self.level_desc.setStyleSheet("padding: 10px; background: #E3F2FD; border-radius: 4px; color: #1976D2;")
        self._update_level_description()
        layout.addWidget(self.level_desc)
        
        return group
    
    def _create_preview_column(self):
        """Colonne d'aperçu et résumé"""
        widget = QWidget()
        widget.setStyleSheet("background: white;")
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Titre
        title = QLabel("Aperçu de la Vérification")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #000000;")
        layout.addWidget(title)
        
        # Résumé
        summary_group = QGroupBox("Résumé")
        summary_group.setStyleSheet("QGroupBox { color: #000000; }")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setPlainText("En attente de vérification...")
        self.summary_text.setStyleSheet("""
            QTextEdit {
                border: none;
                background: #FAFAFA;
                font-family: 'Segoe UI';
                font-size: 9pt;
                padding: 10px;
            }
        """)
        summary_layout.addWidget(self.summary_text)
        
        layout.addWidget(summary_group)
        
        # Graphique de distribution
        chart_group = QGroupBox("Distribution des Scores")
        chart_group.setStyleSheet("QGroupBox { color: #000000; }")
        chart_layout = QVBoxLayout(chart_group)
        
        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: white;")
        chart_layout.addWidget(self.canvas)
        
        layout.addWidget(chart_group, 1)
        
        return widget
    
    def _create_visualization_tab(self):
        """Onglet de visualisation"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Graphiques multiples
        charts_layout = QHBoxLayout()
        
        # Distribution par statut
        status_group = QGroupBox("Distribution par Statut")
        status_group.setStyleSheet("QGroupBox { color: #000000; }")
        status_layout = QVBoxLayout(status_group)
        
        self.status_figure = Figure(figsize=(4, 4), dpi=100)
        self.status_canvas = FigureCanvas(self.status_figure)
        status_layout.addWidget(self.status_canvas)
        
        charts_layout.addWidget(status_group)
        
        # Distribution des scores
        score_group = QGroupBox("Distribution des Scores")
        score_group.setStyleSheet("QGroupBox { color: #000000; }")
        score_layout = QVBoxLayout(score_group)
        
        self.score_figure = Figure(figsize=(4, 4), dpi=100)
        self.score_canvas = FigureCanvas(self.score_figure)
        score_layout.addWidget(self.score_canvas)
        
        charts_layout.addWidget(score_group)
        
        layout.addLayout(charts_layout)
        
        # Statistiques
        stats_group = QGroupBox("Statistiques Détaillées")
        stats_group.setStyleSheet("QGroupBox { color: #000000; }")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setPlainText("Aucune statistique disponible")
        stats_layout.addWidget(self.stats_text)
        
        layout.addWidget(stats_group)
        
        return widget
    
    def _browse_file(self):
        """Parcourir un fichier"""
        file_filter = "All Files (*.json *.jsonl *.csv *.parquet);;JSON (*.json);;JSONL (*.jsonl);;CSV (*.csv);;Parquet (*.parquet)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier de dataset",
            "",
            file_filter
        )
        
        if file_path:
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setProperty('file_path', file_path)
            
            # Détecter automatiquement le format basé sur l'extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.json':
                self.format_combo.setCurrentText('JSON')
            elif ext == '.jsonl':
                self.format_combo.setCurrentText('JSONL')
            elif ext == '.csv':
                self.format_combo.setCurrentText('CSV')
            elif ext == '.parquet':
                self.format_combo.setCurrentText('Parquet')
            
            self.verify_btn.setEnabled(True)
    
    def _on_level_changed(self):
        """Changement de niveau"""
        self._update_level_description()
    
    def _on_rlhf_toggled(self):
        """Toggle RLHF"""
        self._update_level_description()
    
    def _update_level_description(self):
        """Met à jour la description du niveau"""
        level_idx = self.level_combo.currentIndex()
        rlhf = self.rlhf_check.isChecked()
        
        descriptions = [
            "Vérification rapide des règles de base (format, longueur, etc.)",
            "Vérification standard avec analyse de qualité basique",
            "Vérification complète avec analyse approfondie de qualité"
        ]
        
        desc = descriptions[level_idx]
        if rlhf:
            desc += "\n\nValidation RLHF activée pour une analyse intelligente."
        
        self.level_desc.setText(desc)
    
    def _verify_dataset(self):
        """Lance la vérification"""
        # Récupérer le fichier sélectionné
        file_path = self.file_label.property('file_path')
        
        if not file_path:
            QMessageBox.warning(
                self,
                "Attention",
                "Veuillez sélectionner un fichier de dataset"
            )
            return
        
        # Format du fichier
        file_format = self.format_combo.currentText()
        
        # Niveau de validation
        level_map = {
            0: ValidationLevel.QUICK,
            1: ValidationLevel.STANDARD,
            2: ValidationLevel.STRICT
        }
        validation_level = level_map[self.level_combo.currentIndex()]
        
        # RLHF
        rlhf_enabled = self.rlhf_check.isChecked()
        
        self._start_verification(file_path, file_format, validation_level, rlhf_enabled)
    
    def _start_verification(self, file_path, file_format, validation_level, rlhf_enabled):
        """Démarre la vérification"""
        logger.info(f"Début vérification: {file_path}")
        
        self.verify_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(4)
        
        self.worker = APIVerificationWorker(file_path, file_format, validation_level, rlhf_enabled)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.verification_completed.connect(self._on_verification_completed)
        self.worker.verification_failed.connect(self._on_verification_failed)
        self.worker.start()
    
    def _on_progress_updated(self, current, total, message):
        """Mise à jour progression"""
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{message} ({current}/{total})")
    
    def _on_verification_completed(self, result):
        """Fin de vérification"""
        logger.info("Vérification terminée")
        
        self.current_verification = result
        
        self.verify_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        self._display_results(result)
        
        # Passer à l'onglet résultats
        self.tabs.setCurrentIndex(1)
        
        api_result = result.get('api_result', {})
        valid = api_result.get('valid_samples', 0)
        total = api_result.get('total_samples', 0)
        score = api_result.get('overall_quality_score', 0)
        
        QMessageBox.information(
            self,
            "Vérification Terminée",
            f"Vérification effectuée avec succès!\n\n"
            f"Valides: {valid}/{total}\n"
            f"Score global: {score:.1f}/100"
        )
    
    def _on_verification_failed(self, error):
        """Échec de vérification"""
        logger.error(f"Vérification échouée: {error}")
        
        self.verify_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(self, "Erreur", f"La vérification a échoué:\n\n{error}")
    
    def _display_results(self, result):
        """Affiche les résultats"""
        api_result = result.get('api_result', {})
        
        # Charger dans le widget de résultats
        results_list = api_result.get('results', [])
        self.results_widget.load_results(results_list)
        
        # Mise à jour du résumé
        self._update_summary(api_result)
        
        # Mise à jour des graphiques
        self._update_charts(api_result)
        
        # Statistiques
        self._update_statistics(api_result)
    
    def _update_summary(self, api_result):
        """Met à jour le résumé"""
        total = api_result.get('total_samples', 0)
        valid = api_result.get('valid_samples', 0)
        warning = api_result.get('warning_samples', 0)
        invalid = api_result.get('invalid_samples', 0)
        score = api_result.get('overall_quality_score', 0)
        
        summary = f"""=== RÉSUMÉ DE LA VÉRIFICATION ===

Total de samples: {total}

Valides: {valid} ({valid/total*100:.1f}%)
Warnings: {warning} ({warning/total*100:.1f}%)
Invalides: {invalid} ({invalid/total*100:.1f}%)

Score global: {score:.1f}/100

{self._get_verdict(score)}
"""
        
        self.summary_text.setPlainText(summary)
    
    def _get_verdict(self, score):
        """Verdict selon le score"""
        if score >= 80:
            return "Excellent - Dataset de haute qualité"
        elif score >= 60:
            return "Bon - Quelques améliorations possibles"
        elif score >= 40:
            return "Moyen - Nécessite des corrections"
        else:
            return "Faible - Révision majeure requise"
    
    def _update_charts(self, api_result):
        """Met à jour les graphiques"""
        results = api_result.get('results', [])
        if not results:
            return
        
        # Distribution des scores (aperçu)
        scores = [r.get('quality_score', 0) for r in results]
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.hist(scores, bins=20, color=Theme.PRIMARY_COLOR, alpha=0.7, edgecolor='white')
        ax.set_xlabel('Score de qualité')
        ax.set_ylabel('Nombre de samples')
        ax.set_title('Distribution des Scores')
        ax.grid(axis='y', alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()
        
        # Distribution par statut (viz tab)
        statuses = [r.get('status', 'unknown') for r in results]
        status_counts = {
            'valid': statuses.count('valid'),
            'warning': statuses.count('warning'),
            'invalid': statuses.count('invalid')
        }
        
        self.status_figure.clear()
        ax2 = self.status_figure.add_subplot(111)
        colors = ['#4CAF50', '#FFC107', '#F44336']
        ax2.pie(
            status_counts.values(),
            labels=[f"{k}\n({v})" for k, v in status_counts.items()],
            colors=colors,
            autopct='%1.1f%%',
            startangle=90
        )
        ax2.set_title('Distribution par Statut')
        self.status_figure.tight_layout()
        self.status_canvas.draw()
        
        # Distribution scores (viz tab)
        self.score_figure.clear()
        ax3 = self.score_figure.add_subplot(111)
        ax3.hist(scores, bins=20, color=Theme.SECONDARY_COLOR, alpha=0.7, edgecolor='white')
        ax3.set_xlabel('Score')
        ax3.set_ylabel('Fréquence')
        ax3.set_title('Distribution Détaillée des Scores')
        ax3.grid(axis='y', alpha=0.3)
        self.score_figure.tight_layout()
        self.score_canvas.draw()
    
    def _update_statistics(self, api_result):
        """Met à jour les statistiques"""
        summary = api_result.get('summary', {})
        results = api_result.get('results', [])
        
        # Analyser les issues
        all_issues = []
        for r in results:
            all_issues.extend(r.get('issues', []))
        
        issue_types = {}
        for issue in all_issues:
            issue_type = issue.get('type', 'unknown')
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
        
        # Top erreurs
        top_errors = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:10]
        
        stats_text = "=== STATISTIQUES DÉTAILLÉES ===\n\n"
        
        stats_text += f"Niveau de validation: {summary.get('validation_level', 'N/A')}\n\n"
        
        stats_text += "Top 10 des erreurs:\n"
        for error_type, count in top_errors:
            stats_text += f"  {error_type}: {count}\n"
        
        stats_text += f"\n\nRecommandations:\n"
        for rec in summary.get('recommendations', []):
            stats_text += f"  {rec}\n"
        
        self.stats_text.setPlainText(stats_text)
    
    def _on_feedback_submitted(self, feedback):
        """Feedback soumis"""
        logger.info(f"Feedback reçu pour sample {feedback.get('sample_id')}")
        
        # Ici on pourrait envoyer le feedback à l'API
        # pour l'enregistrement et l'amélioration future
        try:
            logger.info("Feedback enregistré localement")
        except Exception as e:
            logger.error(f"Erreur enregistrement feedback: {e}")
    
    def _load_generations(self):
        """Charge les générations disponibles (méthode conservée pour compatibilité API)"""
        pass
    
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        self._load_generations()