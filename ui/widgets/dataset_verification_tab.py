# ui/widgets/dataset_verification_tab.py

import os
import json

from datetime import datetime
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QThread, QUrl
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QTextEdit, QSpinBox, 
                             QPushButton, QProgressBar, QMessageBox,
                             QFileDialog, QCheckBox, QListWidget, QListWidgetItem,
                             QSplitter, QTabWidget, QFrame)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPainter, QColor, QFont

from core.data.database import Database
from utils.logger import logger
from ui.widgets.visualization import DatasetVisualization, generate_verification_pie_chart, generate_comparison_visualization

class VerificationWorker(QThread):
    """Thread pour la vérification de dataset en arrière-plan"""
    
    progress_updated = pyqtSignal(int)
    verification_completed = pyqtSignal(dict)
    verification_failed = pyqtSignal(str)
    
    def __init__(self, conductor, platform, dataset_path, verification_criteria):
        super().__init__()
        self.conductor = conductor
        self.platform = platform
        self.dataset_path = dataset_path
        self.verification_criteria = verification_criteria
        self.is_running = True
        
    def run(self):
        """Exécute la vérification du dataset"""
        try:
            # Charger le dataset
            self.progress_updated.emit(10)
            dataset = self._load_dataset()
            if not dataset:
                self.verification_failed.emit("Impossible de charger le dataset")
                return
                
            self.progress_updated.emit(30)
            
            # Préparer le prompt de vérification
            verification_prompt = self._prepare_verification_prompt(dataset)
            
            self.progress_updated.emit(50)
            
            # Envoyer le prompt via l'API
            response = self.conductor.send_prompt(
                self.platform, 
                verification_prompt, 
                mode="standard", 
                sync=True, 
                timeout=120
            )
            
            self.progress_updated.emit(80)
            
            # Analyser la réponse
            results = self._parse_verification_response(response, dataset)
            
            self.progress_updated.emit(100)
            self.verification_completed.emit(results)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification: {str(e)}")
            self.verification_failed.emit(f"Erreur: {str(e)}")
    
    def _load_dataset(self):
        """Charge le dataset depuis le fichier"""
        try:
            if self.dataset_path.endswith('.json'):
                with open(self.dataset_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif self.dataset_path.endswith('.csv'):
                # Implémenter le chargement CSV si nécessaire
                import pandas as pd
                return pd.read_csv(self.dataset_path).to_dict('records')
            else:
                # Pour les fichiers texte, traiter comme un dataset simple
                with open(self.dataset_path, 'r', encoding='utf-8') as f:
                    return {"content": f.read()}
        except Exception as e:
            logger.error(f"Erreur lors du chargement du dataset: {str(e)}")
            return None
    
    def _prepare_verification_prompt(self, dataset):
        """Prépare le prompt pour la vérification"""
        prompt = f"""
        Vérification de qualité de dataset - Analyse complète

        CONTEXTE:
        Je souhaite vérifier la qualité d'un dataset destiné à l'entraînement de modèles d'IA.

        CRITÈRES DE VÉRIFICATION:
        {self.verification_criteria}

        DONNÉES À ANALYSER:
        {json.dumps(dataset, ensure_ascii=False, indent=2)[:2000]}...

        FORMAT DE RÉPONSE ATTENDU:
        Retournez un objet JSON avec cette structure:
        {{
            "quality_score": 0-100,
            "issues_found": [
                {{
                    "type": "type_d_erreur",
                    "description": "description détaillée",
                    "severity": "low/medium/high",
                    "count": nombre_d_occurrences
                }}
            ],
            "statistics": {{
                "total_items": nombre_total,
                "valid_items": nombre_valide,
                "invalid_items": nombre_invalide
            }},
            "recommendations": [
                "recommandation 1",
                "recommandation 2"
            ]
        }}

        Analysez soigneusement et fournissez une évaluation objective.
        """
        return prompt
    
    def _parse_verification_response(self, response, dataset):
        """Analyse la réponse de vérification"""
        try:
            if response and "result" in response and "response" in response["result"]:
                response_text = response["result"]["response"]
                
                # Essayer d'extraire le JSON de la réponse
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                
                if json_match:
                    results = json.loads(json_match.group())
                else:
                    # Si pas de JSON, créer un résultat par défaut
                    results = {
                        "quality_score": 50,
                        "issues_found": [
                            {
                                "type": "format_error",
                                "description": "Impossible de parser la réponse de l'IA",
                                "severity": "medium",
                                "count": 1
                            }
                        ],
                        "statistics": {
                            "total_items": len(dataset) if isinstance(dataset, list) else 1,
                            "valid_items": 0,
                            "invalid_items": len(dataset) if isinstance(dataset, list) else 1
                        },
                        "recommendations": [
                            "Vérifier manuellement le dataset",
                            "Réessayer avec un autre modèle d'IA"
                        ]
                    }
            else:
                results = {
                    "quality_score": 0,
                    "issues_found": [
                        {
                            "type": "api_error",
                            "description": "Erreur de communication avec l'API",
                            "severity": "high",
                            "count": 1
                        }
                    ],
                    "statistics": {
                        "total_items": 0,
                        "valid_items": 0,
                        "invalid_items": 0
                    },
                    "recommendations": [
                        "Vérifier la connexion à l'API",
                        "Réessayer plus tard"
                    ]
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de la réponse: {str(e)}")
            return {
                "quality_score": 0,
                "issues_found": [
                    {
                        "type": "parsing_error",
                        "description": f"Erreur d'analyse: {str(e)}",
                        "severity": "high",
                        "count": 1
                    }
                ],
                "statistics": {
                    "total_items": 0,
                    "valid_items": 0,
                    "invalid_items": 0
                },
                "recommendations": [
                    "Vérifier le format de la réponse",
                    "Contacter le support"
                ]
            }


class VisualizationTab(QWidget):
    """Onglet de visualisation des résultats de vérification"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.verification_data = None
        self.current_viz_paths = {}
        self.viz_manager = DatasetVisualization()
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # En-tête
        header_label = QLabel("📊 Visualisations des Résultats")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #A23B2D;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header_label)
        
        # Contrôles de visualisation
        controls_group = QGroupBox("Contrôles de Visualisation")
        controls_group.setStyleSheet(self._get_group_box_style())
        controls_layout = QHBoxLayout(controls_group)
        
        self.generate_pie_btn = QPushButton("Générer Camembert")
        self.generate_pie_btn.setStyleSheet(self._get_button_style())
        self.generate_pie_btn.clicked.connect(self._generate_pie_chart)
        
        self.generate_detailed_btn = QPushButton("Analyse Détaillée")
        self.generate_detailed_btn.setStyleSheet(self._get_button_style())
        self.generate_detailed_btn.clicked.connect(self._generate_detailed_analysis)
        
        self.refresh_btn = QPushButton("🔄 Actualiser")
        self.refresh_btn.setStyleSheet(self._get_secondary_button_style())
        self.refresh_btn.clicked.connect(self._refresh_visualizations)
        
        controls_layout.addWidget(self.generate_pie_btn)
        controls_layout.addWidget(self.generate_detailed_btn)
        controls_layout.addWidget(self.refresh_btn)
        controls_layout.addStretch()
        
        layout.addWidget(controls_group)
        
        # Zone d'affichage des visualisations
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #A23B2D;
                color: white;
            }
        """)
        
        # Onglet Camembert
        self.pie_tab = QWidget()
        pie_layout = QVBoxLayout(self.pie_tab)
        self.pie_webview = QWebEngineView()
        self.pie_webview.setMinimumHeight(400)
        pie_layout.addWidget(self.pie_webview)
        self.tab_widget.addTab(self.pie_tab, "📈 Score de Qualité")
        
        # Onglet Analyse Détaillée
        self.detailed_tab = QWidget()
        detailed_layout = QVBoxLayout(self.detailed_tab)
        self.detailed_webview = QWebEngineView()
        self.detailed_webview.setMinimumHeight(400)
        detailed_layout.addWidget(self.detailed_webview)
        self.tab_widget.addTab(self.detailed_tab, "📊 Analyse Détaillée")
        
        # Onglet Comparaison (pour usage futur)
        self.comparison_tab = QWidget()
        comparison_layout = QVBoxLayout(self.comparison_tab)
        self.comparison_webview = QWebEngineView()
        self.comparison_webview.setMinimumHeight(400)
        comparison_layout.addWidget(self.comparison_webview)
        self.tab_widget.addTab(self.comparison_tab, "🔍 Comparaison")
        
        layout.addWidget(self.tab_widget)
        
        # Message d'état
        self.status_label = QLabel("Aucune donnée de vérification disponible. Veuillez d'abord effectuer une vérification.")
        self.status_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self._set_visualization_state(False)
        
    def _get_group_box_style(self):
        """Retourne le style pour les group boxes"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #A23B2D;
                border: 2px solid #DDDDDD;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }
        """
    
    def _get_button_style(self):
        """Retourne le style pour les boutons standards"""
        return """
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C24A3A;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """
    
    def _get_secondary_button_style(self):
        """Retourne le style pour le bouton secondaire"""
        return """
            QPushButton {
                background-color: #2D8A23;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3D9A33;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """
    
    def set_verification_data(self, verification_data):
        """Définit les données de vérification à visualiser"""
        self.verification_data = verification_data
        has_data = verification_data is not None
        
        self._set_visualization_state(has_data)
        
        if has_data:
            self.status_label.setText("Données de vérification chargées. Cliquez sur les boutons pour générer les visualisations.")
            # Générer automatiquement le camembert
            self._generate_pie_chart()
    
    def _set_visualization_state(self, enabled):
        """Active ou désactive les contrôles de visualisation"""
        self.generate_pie_btn.setEnabled(enabled)
        self.generate_detailed_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        
        if not enabled:
            self.pie_webview.setHtml("<html><body style='background-color: #F5F5F5; display: flex; justify-content: center; align-items: center;'><p style='color: #666; font-style: italic;'>Aucune visualisation disponible</p></body></html>")
            self.detailed_webview.setHtml("<html><body style='background-color: #F5F5F5; display: flex; justify-content: center; align-items: center;'><p style='color: #666; font-style: italic;'>Aucune visualisation disponible</p></body></html>")
            self.comparison_webview.setHtml("<html><body style='background-color: #F5F5F5; display: flex; justify-content: center; align-items: center;'><p style='color: #666; font-style: italic;'>Aucune visualisation disponible</p></body></html>")
    
    def _generate_pie_chart(self):
        """Génère et affiche le camembert de qualité"""
        if not self.verification_data:
            return
            
        try:
            viz_path = generate_verification_pie_chart(
                self.verification_data, 
                "Score de Qualité du Dataset"
            )
            
            if viz_path and os.path.exists(viz_path):
                self.current_viz_paths['pie'] = viz_path
                self.pie_webview.load(QUrl.fromLocalFile(viz_path))
                self.status_label.setText("Camembert généré avec succès.")
            else:
                self.status_label.setText("Erreur lors de la génération du camembert.")
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération du camembert: {str(e)}")
            self.status_label.setText(f"Erreur: {str(e)}")
    
    def _generate_detailed_analysis(self):
        """Génère et affiche l'analyse détaillée"""
        if not self.verification_data:
            return
            
        try:
            viz_path = self.viz_manager.generate_detailed_analysis_chart(self.verification_data)
            
            if viz_path and os.path.exists(viz_path):
                self.current_viz_paths['detailed'] = viz_path
                self.detailed_webview.load(QUrl.fromLocalFile(viz_path))
                self.status_label.setText("Analyse détaillée générée avec succès.")
            else:
                self.status_label.setText("Erreur lors de la génération de l'analyse détaillée.")
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération de l'analyse détaillée: {str(e)}")
            self.status_label.setText(f"Erreur: {str(e)}")
    
    def _refresh_visualizations(self):
        """Rafraîchit toutes les visualisations"""
        if self.verification_data:
            self._generate_pie_chart()
            self._generate_detailed_analysis()


class DatasetVerificationTab(QWidget):
    """Onglet de vérification de dataset avec visualisation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.database = None
        self.platforms = []
        self.verification_worker = None
        self.current_results = None
        self.current_dataset_path = None
        
        self._init_ui()
        self._init_connections()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # === EN-TÊTE ===
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #A23B2D;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        title_label = QLabel("🔍 Vérification de Dataset")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }
        """)
        
        subtitle_label = QLabel("Analysez la qualité de vos datasets avec l'IA")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #F0F0F0;
                font-size: 12px;
            }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        main_layout.addWidget(header_frame)
        
        # === ONGLETS PRINCIPAUX ===
        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #A23B2D;
                color: white;
            }
        """)
        
        # Onglet Vérification
        self.verification_tab = QWidget()
        self._init_verification_tab()
        self.main_tab_widget.addTab(self.verification_tab, "⚙️ Vérification")
        
        # Onglet Visualisation
        self.visualization_tab = VisualizationTab()
        self.main_tab_widget.addTab(self.visualization_tab, "📊 Visualisation")
        
        main_layout.addWidget(self.main_tab_widget, 1)
        
    def _init_verification_tab(self):
        """Initialise l'onglet de vérification"""
        layout = QVBoxLayout(self.verification_tab)
        layout.setSpacing(15)
        
        # === CONTENU PRINCIPAL ===
        content_splitter = QSplitter(QtCore.Qt.Horizontal)
        
        # === PARTIE GAUCHE - CONFIGURATION ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        
        # Section Sélection du dataset
        dataset_group = QGroupBox("📁 Sélection du Dataset")
        dataset_group.setStyleSheet(self._get_group_box_style())
        dataset_layout = QVBoxLayout(dataset_group)
        
        # Sélection de fichier
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("Aucun fichier sélectionné")
        self.file_path_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #F5F5F5;
                border: 1px solid #DDDDDD;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        
        self.browse_btn = QPushButton("Parcourir...")
        self.browse_btn.setStyleSheet(self._get_button_style())
        
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.browse_btn)
        dataset_layout.addLayout(file_layout)
        
        # Info fichier
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("font-size: 10px; color: #666;")
        dataset_layout.addWidget(self.file_info_label)
        
        left_layout.addWidget(dataset_group)
        
        # Section Configuration vérification
        config_group = QGroupBox("⚙️ Configuration de la Vérification")
        config_group.setStyleSheet(self._get_group_box_style())
        config_layout = QVBoxLayout(config_group)
        
        # Plateforme IA
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QLabel("Plateforme IA:"))
        self.platform_combo = QComboBox()
        self.platform_combo.setStyleSheet(self._get_combo_box_style())
        platform_layout.addWidget(self.platform_combo, 1)
        config_layout.addLayout(platform_layout)
        
        # Critères de vérification
        criteria_layout = QVBoxLayout()
        criteria_layout.addWidget(QLabel("Critères de vérification:"))
        
        self.criteria_edit = QTextEdit()
        self.criteria_edit.setPlaceholderText("""Exemples de critères:
- Cohérence des formats de données
- Complétude des informations
- Qualité linguistique
- Absence de doublons
- Respect des contraintes métier""")
        self.criteria_edit.setMaximumHeight(120)
        self.criteria_edit.setStyleSheet(self._get_text_edit_style())
        
        criteria_layout.addWidget(self.criteria_edit)
        config_layout.addLayout(criteria_layout)
        
        left_layout.addWidget(config_group)
        
        # Section Contrôles
        controls_group = QGroupBox("🎛️ Contrôles")
        controls_group.setStyleSheet(self._get_group_box_style())
        controls_layout = QVBoxLayout(controls_group)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        
        self.verify_btn = QPushButton("🔍 Lancer la vérification")
        self.verify_btn.setStyleSheet(self._get_primary_button_style())
        
        self.save_btn = QPushButton("💾 Sauvegarder le dataset")
        self.save_btn.setStyleSheet(self._get_secondary_button_style())
        self.save_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.verify_btn)
        buttons_layout.addWidget(self.save_btn)
        controls_layout.addLayout(buttons_layout)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p% - Vérification en cours...")
        controls_layout.addWidget(self.progress_bar)
        
        left_layout.addWidget(controls_group)
        
        # === PARTIE DROITE - RÉSULTATS ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)
        
        # Section Score de qualité
        score_group = QGroupBox("📊 Score de Qualité")
        score_group.setStyleSheet(self._get_group_box_style())
        score_layout = QVBoxLayout(score_group)
        
        self.score_label = QLabel("N/A")
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #A23B2D;
                padding: 20px;
            }
        """)
        
        self.score_description = QLabel("En attente de vérification...")
        self.score_description.setAlignment(QtCore.Qt.AlignCenter)
        self.score_description.setStyleSheet("font-size: 11px; color: #666;")
        
        score_layout.addWidget(self.score_label)
        score_layout.addWidget(self.score_description)
        
        right_layout.addWidget(score_group)
        
        # Section Visualisation (remplacée par une liste textuelle)
        viz_group = QGroupBox("📈 Problèmes Identifiés")
        viz_group.setStyleSheet(self._get_group_box_style())
        viz_layout = QVBoxLayout(viz_group)
        
        # Liste textuelle au lieu du graphique
        self.issues_list = QTextEdit()
        self.issues_list.setReadOnly(True)
        self.issues_list.setMaximumHeight(150)
        self.issues_list.setStyleSheet(self._get_text_edit_style())
        self.issues_list.setPlaceholderText("Aucun problème identifié pour le moment...")
        
        viz_layout.addWidget(self.issues_list)
        
        right_layout.addWidget(viz_group)
        
        # Section Détails
        details_group = QGroupBox("📋 Détails de l'Analyse")
        details_group.setStyleSheet(self._get_group_box_style())
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet(self._get_text_edit_style())
        details_layout.addWidget(self.details_text)
        
        right_layout.addWidget(details_group)
        
        # Ajouter les widgets au splitter
        content_splitter.addWidget(left_widget)
        content_splitter.addWidget(right_widget)
        content_splitter.setSizes([400, 500])
        
        layout.addWidget(content_splitter, 1)
        
    def _init_connections(self):
        """Initialise les connexions signal-slot"""
        self.browse_btn.clicked.connect(self._on_browse_dataset)
        self.verify_btn.clicked.connect(self._on_verify_dataset)
        self.save_btn.clicked.connect(self._on_save_dataset)
        
    def _get_group_box_style(self):
        """Retourne le style pour les group boxes"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #A23B2D;
                border: 2px solid #DDDDDD;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }
        """
    
    def _get_button_style(self):
        """Retourne le style pour les boutons standards"""
        return """
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C24A3A;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """
    
    def _get_primary_button_style(self):
        """Retourne le style pour le bouton principal"""
        return """
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C24A3A;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """
    
    def _get_secondary_button_style(self):
        """Retourne le style pour le bouton secondaire"""
        return """
            QPushButton {
                background-color: #2D8A23;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3D9A33;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """
    
    def _get_combo_box_style(self):
        """Retourne le style pour les combobox"""
        return """
            QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                background-color: white;
            }
        """
    
    def _get_text_edit_style(self):
        """Retourne le style pour les zones de texte"""
        return """
            QTextEdit {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                background-color: white;
            }
        """
    
    def set_conductor(self, conductor):
        """Définit le conducteur pour les appels API"""
        self.conductor = conductor
    
    def set_platforms(self, platforms):
        """Définit les plateformes disponibles"""
        self.platforms = platforms
        self.platform_combo.clear()
        self.platform_combo.addItems(platforms)
        
        # Prioriser Gemini s'il est disponible
        gemini_platforms = [p for p in platforms if "gemini" in p.lower()]
        if gemini_platforms:
            self.platform_combo.setCurrentText(gemini_platforms[0])
    
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
    
    def _on_browse_dataset(self):
        """Ouvre la boîte de dialogue pour sélectionner un dataset"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un dataset", 
            "",
            "Dataset Files (*.json *.csv *.txt);;All Files (*)", 
            options=options
        )
        
        if file_path:
            self.current_dataset_path = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            
            # Afficher les informations du fichier
            file_size = os.path.getsize(file_path) / 1024  # Taille en KB
            self.file_info_label.setText(f"Taille: {file_size:.1f} KB | Chemin: {file_path}")
            
            # Activer le bouton de vérification
            self.verify_btn.setEnabled(True)
    
    def _on_verify_dataset(self):
        """Lance la vérification du dataset"""
        if not self.conductor:
            QMessageBox.warning(self, "Erreur", "Conducteur non initialisé")
            return
        
        if not self.platforms:
            QMessageBox.warning(self, "Erreur", "Aucune plateforme disponible")
            return
        
        if not self.current_dataset_path:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un dataset")
            return
        
        # Récupérer les critères de vérification
        criteria = self.criteria_edit.toPlainText().strip()
        if not criteria:
            criteria = "Vérification standard de la qualité du dataset"
        
        # Désactiver le bouton pendant la vérification
        self.verify_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Réinitialiser l'affichage des résultats
        self.score_label.setText("N/A")
        self.score_description.setText("Vérification en cours...")
        self.details_text.clear()
        self.issues_list.clear()
        
        # Lancer le worker de vérification
        self.verification_worker = VerificationWorker(
            self.conductor, 
            self.platform_combo.currentText(),
            self.current_dataset_path,
            criteria
        )
        
        self.verification_worker.progress_updated.connect(self._on_progress_updated)
        self.verification_worker.verification_completed.connect(self._on_verification_completed)
        self.verification_worker.verification_failed.connect(self._on_verification_failed)
        
        self.verification_worker.start()
    
    def _on_save_dataset(self):
        """Sauvegarde le dataset vérifié"""
        if not self.current_dataset_path:
            QMessageBox.warning(self, "Erreur", "Aucun dataset à sauvegarder")
            return
        
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le dataset", 
            f"verified_{os.path.basename(self.current_dataset_path)}",
            "JSON Files (*.json);;CSV Files (*.csv);;Text Files (*.txt)", 
            options=options
        )
        
        if file_path:
            try:
                # Copier le fichier avec un préfixe "verified_"
                import shutil
                shutil.copy2(self.current_dataset_path, file_path)
                
                # Ajouter les métadonnées de vérification si JSON
                if file_path.endswith('.json') and self.current_results:
                    with open(file_path, 'r+', encoding='utf-8') as f:
                        data = json.load(f)
                        data['_verification_metadata'] = {
                            'verified_at': datetime.now().isoformat(),
                            'quality_score': self.current_results.get('quality_score', 0),
                            'verification_criteria': self.criteria_edit.toPlainText().strip()
                        }
                        f.seek(0)
                        json.dump(data, f, ensure_ascii=False, indent=2)
                        f.truncate()
                
                QMessageBox.information(self, "Succès", f"Dataset sauvegardé sous: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
    
    def _on_progress_updated(self, progress):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(progress)
    
    def _on_verification_completed(self, results):
        """Gère la fin de la vérification"""
        self.verify_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.save_btn.setEnabled(True)
        
        self.current_results = results
        self._display_results(results)
        
        # Mettre à jour l'onglet de visualisation
        self.visualization_tab.set_verification_data(results)
        
        # Basculer automatiquement sur l'onglet visualisation
        self.main_tab_widget.setCurrentIndex(1)
    
    def _on_verification_failed(self, error_message):
        """Gère l'échec de la vérification"""
        self.verify_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(self, "Erreur de vérification", error_message)
        
        # Réinitialiser l'affichage
        self.score_label.setText("N/A")
        self.score_description.setText("Échec de la vérification")
        self.details_text.setText(f"Erreur: {error_message}")
    
    def _display_results(self, results):
        """Affiche les résultats de la vérification"""
        # Score de qualité
        quality_score = results.get('quality_score', 0)
        self.score_label.setText(f"{quality_score}/100")
        
        # Description du score
        if quality_score >= 90:
            description = "Excellent - Dataset de haute qualité"
            color = "#2D8A23"
        elif quality_score >= 70:
            description = "Bon - Quelques améliorations possibles"
            color = "#A23B2D"
        elif quality_score >= 50:
            description = "Moyen - Améliorations recommandées"
            color = "#D4A017"
        else:
            description = "Faible - Améliorations nécessaires"
            color = "#C41E3A"
        
        self.score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 32px;
                font-weight: bold;
                color: {color};
                padding: 20px;
            }}
        """)
        self.score_description.setText(description)
        
        # Problèmes identifiés
        issues = results.get('issues_found', [])
        if issues:
            issues_text = ""
            for issue in issues:
                severity_icon = {
                    "high": "🔴",
                    "medium": "🟡", 
                    "low": "🟢"
                }.get(issue.get('severity', 'low'), "⚪")
                
                issues_text += f"{severity_icon} {issue.get('type', 'Unknown')}: {issue.get('description', '')}\n"
                if issue.get('count', 0) > 1:
                    issues_text += f"   Occurrences: {issue.get('count', 0)}\n"
                issues_text += "\n"
            
            self.issues_list.setText(issues_text)
        else:
            self.issues_list.setText("✅ Aucun problème identifié")
        
        # Détails complets
        details = f"=== RAPPORT DE VÉRIFICATION ===\n\n"
        details += f"Score de qualité: {quality_score}/100\n"
        details += f"Statut: {description}\n\n"
        
        stats = results.get('statistics', {})
        details += f"STATISTIQUES:\n"
        details += f"- Total des éléments: {stats.get('total_items', 0)}\n"
        details += f"- Éléments valides: {stats.get('valid_items', 0)}\n"
        details += f"- Éléments invalides: {stats.get('invalid_items', 0)}\n\n"
        
        details += f"PROBLÈMES IDENTIFIÉS ({len(issues)}):\n"
        for i, issue in enumerate(issues, 1):
            details += f"{i}. [{issue.get('severity', 'unknown').upper()}] {issue.get('type', 'Unknown')}\n"
            details += f"   Description: {issue.get('description', '')}\n"
            details += f"   Occurrences: {issue.get('count', 0)}\n\n"
        
        recommendations = results.get('recommendations', [])
        if recommendations:
            details += f"RECOMMANDATIONS:\n"
            for i, rec in enumerate(recommendations, 1):
                details += f"{i}. {rec}\n"
        
        self.details_text.setText(details)