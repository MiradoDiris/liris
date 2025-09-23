#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Widget de génération de datasets avec système de templates et visualisation avancée de l'avancement
"""

import os
import json
import time
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QTextEdit, QPushButton, 
                             QScrollArea, QFrame, QMessageBox, QSplitter,
                             QTabWidget, QFormLayout, QSpinBox, QCheckBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QProgressBar, QTreeWidget, QTreeWidgetItem,
                             QToolTip, QApplication, QStyleFactory)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QFont, QTextOption, QColor, QBrush, QLinearGradient

from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.template_manager import template_manager

# Import pour la visualisation
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class HeatmapWidget(QWidget):
    """Widget de carte thermique pour visualiser l'avancement des combinaisons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_matrix = None
        self.labels_x = []
        self.labels_y = []
        self.init_ui()
        
    def init_ui(self):
        """Initialise l'interface de la carte thermique"""
        layout = QVBoxLayout(self)
        
        # Titre
        title = QLabel("Carte Thermique des Combinaisons de Stratégies")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Zone de visualisation
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 6), dpi=80)
            self.canvas = FigureCanvas(self.figure)
            layout.addWidget(self.canvas)
        else:
            self.fallback_label = QLabel(
                "Matplotlib non disponible. Installation recommandée pour la visualisation avancée."
            )
            self.fallback_label.setWordWrap(True)
            layout.addWidget(self.fallback_label)
        
        # Légende
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("Légende:"))
        
        colors = [
            ("Non-traité", QColor(240, 240, 240)),
            ("En cours", QColor(255, 255, 0)),
            ("Terminé", QColor(0, 255, 0)),
            ("Erreur", QColor(255, 0, 0))
        ]
        
        for status, color in colors:
            color_label = QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
            legend_layout.addWidget(color_label)
            legend_layout.addWidget(QLabel(status))
            legend_layout.addSpacing(10)
        
        legend_layout.addStretch()
        layout.addLayout(legend_layout)
        
        # Données d'exemple par défaut
        self.set_sample_data()
    
    def set_sample_data(self):
        """Définit des données d'exemple pour la démonstration"""
        # Matrice 5x5 avec différents états
        self.data_matrix = np.array([
            [0, 0, 1, 2, 0],
            [1, 2, 2, 3, 1],
            [2, 3, 1, 2, 0],
            [0, 1, 2, 3, 2],
            [3, 2, 1, 0, 1]
        ])
        
        self.labels_x = [f"Stratégie {i+1}" for i in range(5)]
        self.labels_y = [f"Batch {i+1}" for i in range(5)]
        
        self.update_heatmap()
    
    def update_heatmap(self):
        """Met à jour la carte thermique"""
        if not MATPLOTLIB_AVAILABLE or self.data_matrix is None:
            return
            
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Créer la heatmap
        im = ax.imshow(self.data_matrix, cmap='RdYlGn', interpolation='nearest', vmin=0, vmax=3)
        
        # Configurer les axes
        ax.set_xticks(np.arange(len(self.labels_x)))
        ax.set_yticks(np.arange(len(self.labels_y)))
        ax.set_xticklabels(self.labels_x, rotation=45, ha='right')
        ax.set_yticklabels(self.labels_y)
        
        # Ajouter les valeurs dans les cellules
        for i in range(len(self.labels_y)):
            for j in range(len(self.labels_x)):
                text = ax.text(j, i, self.data_matrix[i, j],
                             ha="center", va="center", color="black" if self.data_matrix[i, j] < 2 else "white")
        
        ax.set_title("Avancement des Combinaisons de Stratégies")
        self.figure.tight_layout()
        self.canvas.draw()
    
    def update_data(self, matrix, x_labels, y_labels):
        """Met à jour les données de la heatmap"""
        self.data_matrix = matrix
        self.labels_x = x_labels
        self.labels_y = y_labels
        self.update_heatmap()


class BatchProgressWidget(QWidget):
    """Widget pour afficher la progression par batch"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.batches = {}
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        """Initialise l'interface de progression par batch"""
        layout = QVBoxLayout(self)
        
        # Titre
        title = QLabel("Progression par Batch")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Tableau des batches
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Batch ID", "Statut", "Progression", "Temps écoulé", 
            "Temps restant", "Détails"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
    
    def load_sample_data(self):
        """Charge des données d'exemple"""
        sample_batches = {
            "Batch-001": {"status": "En cours", "progress": 65, "elapsed": "00:15:30", "remaining": "00:08:15"},
            "Batch-002": {"status": "Terminé", "progress": 100, "elapsed": "00:25:10", "remaining": "00:00:00"},
            "Batch-003": {"status": "En attente", "progress": 0, "elapsed": "00:00:00", "remaining": "00:30:00"},
            "Batch-004": {"status": "Erreur", "progress": 45, "elapsed": "00:12:45", "remaining": "N/A"},
        }
        
        for batch_id, data in sample_batches.items():
            self.add_batch(batch_id, data)
    
    def add_batch(self, batch_id, data):
        """Ajoute ou met à jour un batch"""
        if batch_id in self.batches:
            row = self.batches[batch_id]
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.batches[batch_id] = row
        
        # Batch ID
        self.table.setItem(row, 0, QTableWidgetItem(batch_id))
        
        # Statut avec couleur
        status_item = QTableWidgetItem(data["status"])
        if data["status"] == "Terminé":
            status_item.setBackground(QColor(0, 255, 0, 100))
        elif data["status"] == "En cours":
            status_item.setBackground(QColor(255, 255, 0, 100))
        elif data["status"] == "Erreur":
            status_item.setBackground(QColor(255, 0, 0, 100))
        self.table.setItem(row, 1, status_item)
        
        # Barre de progression
        progress_widget = QWidget()
        progress_layout = QHBoxLayout(progress_widget)
        progress_bar = QProgressBar()
        progress_bar.setValue(data["progress"])
        progress_layout.addWidget(progress_bar)
        progress_layout.setContentsMargins(2, 2, 2, 2)
        self.table.setCellWidget(row, 2, progress_widget)
        
        # Temps écoulé
        self.table.setItem(row, 3, QTableWidgetItem(data["elapsed"]))
        
        # Temps restant
        self.table.setItem(row, 4, QTableWidgetItem(data["remaining"]))
        
        # Détails
        details_btn = QPushButton("📊")
        details_btn.setFixedSize(30, 25)
        details_btn.clicked.connect(lambda: self.show_batch_details(batch_id))
        details_widget = QWidget()
        details_layout = QHBoxLayout(details_widget)
        details_layout.addWidget(details_btn)
        details_layout.setAlignment(Qt.AlignCenter)
        details_layout.setContentsMargins(2, 2, 2, 2)
        self.table.setCellWidget(row, 5, details_widget)
    
    def show_batch_details(self, batch_id):
        """Affiche les détails d'un batch"""
        QMessageBox.information(self, f"Détails du batch {batch_id}", 
                              f"Informations détaillées pour le batch {batch_id}")


class StatisticsWidget(QWidget):
    """Widget pour afficher les statistiques en temps réel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_stats)
        self.update_timer.start(1000)  # Mise à jour chaque seconde
    
    def init_ui(self):
        """Initialise l'interface des statistiques"""
        layout = QVBoxLayout(self)
        
        # Titre
        title = QLabel("Statistiques en Temps Réel")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Grid pour les statistiques
        stats_grid = QHBoxLayout()
        
        # Colonne gauche
        left_col = QVBoxLayout()
        self.combinations_label = QLabel("Combinaisons: 0/0")
        self.success_rate_label = QLabel("Taux de réussite: 0%")
        left_col.addWidget(self.combinations_label)
        left_col.addWidget(self.success_rate_label)
        
        # Colonne droite
        right_col = QVBoxLayout()
        self.throughput_label = QLabel("Débit: 0 datasets/min")
        self.error_count_label = QLabel("Erreurs: 0")
        right_col.addWidget(self.throughput_label)
        right_col.addWidget(self.error_count_label)
        
        stats_grid.addLayout(left_col)
        stats_grid.addLayout(right_col)
        layout.addLayout(stats_grid)
        
        # Graphique de débit (simplifié)
        if PYQTGRAPH_AVAILABLE:
            self.throughput_plot = pg.PlotWidget()
            self.throughput_plot.setBackground('w')
            self.throughput_plot.setTitle("Débit (datasets/minute)")
            self.throughput_plot.setLabel('left', 'Datasets/min')
            self.throughput_plot.setLabel('bottom', 'Temps')
            self.throughput_data = []
            layout.addWidget(self.throughput_plot)
        else:
            self.fallback_plot_label = QLabel("PyQtGraph non disponible pour les graphiques temps réel")
            layout.addWidget(self.fallback_plot_label)
        
        layout.addStretch()
    
    def update_stats(self):
        """Met à jour les statistiques"""
        # Données simulées pour la démonstration
        combinations_total = 100
        combinations_done = np.random.randint(0, combinations_total)
        success_rate = np.random.randint(80, 100) if combinations_done > 0 else 0
        throughput = np.random.randint(1, 10)
        errors = np.random.randint(0, 5)
        
        self.combinations_label.setText(f"Combinaisons: {combinations_done}/{combinations_total}")
        self.success_rate_label.setText(f"Taux de réussite: {success_rate}%")
        self.throughput_label.setText(f"Débit: {throughput} datasets/min")
        self.error_count_label.setText(f"Erreurs: {errors}")
        
        # Mettre à jour le graphique de débit
        if PYQTGRAPH_AVAILABLE:
            self.throughput_data.append(throughput)
            if len(self.throughput_data) > 50:
                self.throughput_data.pop(0)
            self.throughput_plot.plot(self.throughput_data, clear=True, pen='b')


class LogWidget(QWidget):
    """Widget pour afficher le journal des opérations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_sample_logs()
    
    def init_ui(self):
        """Initialise l'interface du journal"""
        layout = QVBoxLayout(self)
        
        # Barre d'outils
        toolbar = QHBoxLayout()
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tous", "INFO", "WARNING", "ERROR", "DEBUG"])
        self.filter_combo.currentTextChanged.connect(self.filter_logs)
        toolbar.addWidget(QLabel("Filtrer:"))
        toolbar.addWidget(self.filter_combo)
        
        self.export_btn = QPushButton("Exporter les logs")
        self.export_btn.clicked.connect(self.export_logs)
        toolbar.addWidget(self.export_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Zone de logs
        self.log_tree = QTreeWidget()
        self.log_tree.setHeaderLabels(["Timestamp", "Niveau", "Message"])
        self.log_tree.setColumnWidth(0, 150)
        self.log_tree.setColumnWidth(1, 80)
        layout.addWidget(self.log_tree)
    
    def load_sample_logs(self):
        """Charge des logs d'exemple"""
        sample_logs = [
            ("2024-01-15 10:30:15", "INFO", "Démarrage de la génération des datasets"),
            ("2024-01-15 10:30:16", "INFO", "Batch-001: Génération en cours (0/50)"),
            ("2024-01-15 10:31:20", "WARNING", "Batch-001: Retard détecté sur la stratégie A"),
            ("2024-01-15 10:32:45", "ERROR", "Batch-001: Erreur sur la combinaison 25"),
            ("2024-01-15 10:33:10", "INFO", "Batch-001: Reprise après erreur"),
            ("2024-01-15 10:35:00", "INFO", "Batch-001: Terminé avec succès (49/50)"),
        ]
        
        for timestamp, level, message in sample_logs:
            self.add_log(timestamp, level, message)
    
    def add_log(self, timestamp, level, message):
        """Ajoute une entrée de log"""
        item = QTreeWidgetItem([timestamp, level, message])
        
        # Colorer selon le niveau
        if level == "ERROR":
            item.setBackground(1, QBrush(QColor(255, 200, 200)))
        elif level == "WARNING":
            item.setBackground(1, QBrush(QColor(255, 255, 200)))
        elif level == "INFO":
            item.setBackground(1, QBrush(QColor(200, 255, 200)))
        
        self.log_tree.addTopLevelItem(item)
        self.log_tree.scrollToItem(item)
    
    def filter_logs(self, level_filter):
        """Filtre les logs selon le niveau sélectionné"""
        for i in range(self.log_tree.topLevelItemCount()):
            item = self.log_tree.topLevelItem(i)
            if level_filter == "Tous" or item.text(1) == level_filter:
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def export_logs(self):
        """Exporte les logs vers un fichier"""
        QMessageBox.information(self, "Export des logs", 
                              "Fonctionnalité d'export à implémenter")


class GenerationWidget(QWidget):
    """Widget pour la génération de datasets avec templates et visualisation avancée"""
    
    # Signal émis lorsqu'un dataset est généré
    dataset_generated = pyqtSignal(dict, str)  # dataset, format
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataset = None
        self.current_format = "JSON"
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(PlatformConfigStyle.SPACING)
        main_layout.setContentsMargins(PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN, 
                                      PlatformConfigStyle.MARGIN)
        
        # Titre principal
        title_label = QLabel("Génération de Datasets avec Templates")
        title_label.setStyleSheet(PlatformConfigStyle.get_title_style())
        main_layout.addWidget(title_label)
        
        # Zone d'explication
        explanation_label = QLabel(
            "Générez des datasets dans différents formats (JSON, CSV, XML, YAML, Texte) "
            "avec des templates configurables. Configurez les options de formatage et "
            "prévisualisez le résultat avant export. Visualisez l'avancement en temps réel."
        )
        explanation_label.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation_label.setWordWrap(True)
        main_layout.addWidget(explanation_label)
        
        # Onglets principaux
        self.main_tabs = QTabWidget()
        
        # Onglet 1: Génération avec templates
        self.template_tab = self.create_template_tab()
        self.main_tabs.addTab(self.template_tab, "📊 Génération avec Templates")
        
        # Onglet 2: Visualisation de l'avancement
        self.progress_tab = self.create_progress_tab()
        self.main_tabs.addTab(self.progress_tab, "📈 Visualisation Avancée")
        
        main_layout.addWidget(self.main_tabs)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.generate_example_btn = QPushButton("Générer un Exemple")
        self.generate_example_btn.clicked.connect(self.generate_example)
        button_layout.addWidget(self.generate_example_btn)
        
        self.export_btn = QPushButton("Exporter le Dataset")
        self.export_btn.clicked.connect(self.export_dataset)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(button_layout)
        
    def create_template_tab(self):
        """Crée l'onglet de génération avec templates"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Splitter pour une disposition flexible
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel de configuration (gauche)
        config_panel = self.create_config_panel()
        splitter.addWidget(config_panel)
        
        # Panel de prévisualisation (droite)
        preview_panel = self.create_preview_panel()
        splitter.addWidget(preview_panel)
        
        # Définir les proportions initiales
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)
        
        return tab_widget
    
    def create_progress_tab(self):
        """Crée l'onglet de visualisation avancée de l'avancement"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Sous-onglets pour les différentes visualisations
        progress_tabs = QTabWidget()
        
        # Carte thermique
        self.heatmap_widget = HeatmapWidget()
        progress_tabs.addTab(self.heatmap_widget, "🔥 Carte Thermique")
        
        # Progression par batch
        self.batch_progress_widget = BatchProgressWidget()
        progress_tabs.addTab(self.batch_progress_widget, "📦 Progression par Batch")
        
        # Statistiques en temps réel
        self.stats_widget = StatisticsWidget()
        progress_tabs.addTab(self.stats_widget, "📊 Statistiques Temps Réel")
        
        # Journal des opérations
        self.log_widget = LogWidget()
        progress_tabs.addTab(self.log_widget, "📝 Journal des Opérations")
        
        layout.addWidget(progress_tabs)
        
        return tab_widget
    
    def create_config_panel(self):
        """Crée le panel de configuration des templates"""
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        
        # Groupe de sélection du format
        format_group = QGroupBox("Format de Sortie")
        format_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        format_layout = QFormLayout(format_group)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(template_manager.get_supported_formats())
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        format_layout.addRow("Format:", self.format_combo)
        
        layout.addWidget(format_group)
        
        # Options spécifiques au format (dans un QTabWidget)
        self.options_tabs = QTabWidget()
        self.options_tabs.setStyleSheet(PlatformConfigStyle.get_tabs_style())
        self.create_format_options()
        layout.addWidget(self.options_tabs)
        
        # Configuration du template
        template_group = QGroupBox("Configuration du Template")
        template_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        template_layout = QVBoxLayout(template_group)
        
        self.template_config_edit = QTextEdit()
        self.template_config_edit.setPlaceholderText(
            '{\n  "pretty_print": true,\n  "include_metadata": true\n}'
        )
        self.template_config_edit.setMaximumHeight(150)
        template_layout.addWidget(self.template_config_edit)
        
        # Bouton pour réinitialiser la configuration
        reset_btn = QPushButton("Configuration par Défaut")
        reset_btn.clicked.connect(self.reset_template_config)
        template_layout.addWidget(reset_btn)
        
        layout.addWidget(template_group)
        layout.addStretch()
        
        return config_widget
    
    def create_format_options(self):
        """Crée les options spécifiques à chaque format"""
        # Options JSON
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        
        self.json_pretty_print = QCheckBox("Affichage structuré (indentation)")
        self.json_pretty_print.setChecked(True)
        self.json_pretty_print.toggled.connect(self.update_template_config)
        json_layout.addWidget(self.json_pretty_print)
        
        self.json_include_metadata = QCheckBox("Inclure les métadonnées")
        self.json_include_metadata.setChecked(True)
        self.json_include_metadata.toggled.connect(self.update_template_config)
        json_layout.addWidget(self.json_include_metadata)
        
        json_layout.addStretch()
        self.options_tabs.addTab(json_widget, "JSON")
        
        # Options CSV
        csv_widget = QWidget()
        csv_layout = QVBoxLayout(csv_widget)
        
        self.csv_include_headers = QCheckBox("Inclure les en-têtes")
        self.csv_include_headers.setChecked(True)
        self.csv_include_headers.toggled.connect(self.update_template_config)
        csv_layout.addWidget(self.csv_include_headers)
        
        csv_layout.addStretch()
        self.options_tabs.addTab(csv_widget, "CSV")
        
        # Options XML
        xml_widget = QWidget()
        xml_layout = QVBoxLayout(xml_widget)
        
        self.xml_pretty_print = QCheckBox("Affichage structuré (indentation)")
        self.xml_pretty_print.setChecked(True)
        self.xml_pretty_print.toggled.connect(self.update_template_config)
        xml_layout.addWidget(self.xml_pretty_print)
        
        xml_layout.addStretch()
        self.options_tabs.addTab(xml_widget, "XML")
        
        # Options YAML
        yaml_widget = QWidget()
        yaml_layout = QVBoxLayout(yaml_widget)
        
        self.yaml_include_metadata = QCheckBox("Inclure les métadonnées")
        self.yaml_include_metadata.setChecked(True)
        self.yaml_include_metadata.toggled.connect(self.update_template_config)
        yaml_layout.addWidget(self.yaml_include_metadata)
        
        yaml_layout.addStretch()
        self.options_tabs.addTab(yaml_widget, "YAML")
        
        # Options Texte
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        
        self.text_include_timestamp = QCheckBox("Inclure l'horodatage")
        self.text_include_timestamp.setChecked(True)
        self.text_include_timestamp.toggled.connect(self.update_template_config)
        text_layout.addWidget(self.text_include_timestamp)
        
        text_layout.addStretch()
        self.options_tabs.addTab(text_widget, "Texte")
    
    def create_preview_panel(self):
        """Crée le panel de prévisualisation"""
        preview_widget = QWidget()
        layout = QVBoxLayout(preview_widget)
        
        # Titre de prévisualisation
        preview_label = QLabel("Prévisualisation")
        preview_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #A23B2D;
            padding: 8px;
            background-color: #F9F6F6;
            border-radius: 4px;
            margin-bottom: 5px;
        """)
        layout.addWidget(preview_label)
        
        # Éditeur de prévisualisation
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFont(QFont("Courier", 10))
        self.preview_edit.setWordWrapMode(QTextOption.NoWrap)
        
        # Appliquer un style spécifique pour la prévisualisation
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2B2B2B;
                color: #FFFFFF;
                font-family: 'Courier New';
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        
        layout.addWidget(self.preview_edit)
        
        # Statistiques
        stats_group = QGroupBox("Statistiques")
        stats_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        stats_layout = QHBoxLayout(stats_group)
        
        self.stats_label = QLabel("Aucun dataset généré")
        self.stats_label.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        return preview_widget
    
    def apply_styles(self):
        """Applique les styles aux composants"""
        # Styles pour les combobox
        self.format_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        
        # Styles pour les boutons
        button_style = PlatformConfigStyle.get_button_style()
        self.generate_example_btn.setStyleSheet(button_style)
        self.export_btn.setStyleSheet(button_style)
        
        # Style pour l'éditeur de configuration
        self.template_config_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
    
    def on_format_changed(self, format_type):
        """Gère le changement de format"""
        self.current_format = format_type
        self.update_template_config()
        
        # Mettre à jour l'onglet actif
        format_index = template_manager.get_supported_formats().index(format_type)
        self.options_tabs.setCurrentIndex(format_index)
        
        # Régénérer la prévisualisation si un dataset existe
        if self.current_dataset:
            self.update_preview()
    
    def update_template_config(self):
        """Met à jour la configuration du template basée sur les contrôles d'interface"""
        format_type = self.current_format
        config = {}
        
        if format_type == "JSON":
            config = {
                "pretty_print": self.json_pretty_print.isChecked(),
                "include_metadata": self.json_include_metadata.isChecked()
            }
        elif format_type == "CSV":
            config = {
                "include_headers": self.csv_include_headers.isChecked()
            }
        elif format_type == "XML":
            config = {
                "pretty_print": self.xml_pretty_print.isChecked()
            }
        elif format_type == "YAML":
            config = {
                "include_metadata": self.yaml_include_metadata.isChecked()
            }
        elif format_type == "Texte":
            config = {
                "include_timestamp": self.text_include_timestamp.isChecked()
            }
        
        # Mettre à jour l'éditeur de configuration
        self.template_config_edit.setPlainText(json.dumps(config, indent=2))
        
        # Régénérer la prévisualisation si un dataset existe
        if self.current_dataset:
            self.update_preview()
    
    def reset_template_config(self):
        """Réinitialise la configuration du template aux valeurs par défaut"""
        default_config = template_manager.default_templates.get(self.current_format, {})
        self.template_config_edit.setPlainText(json.dumps(default_config, indent=2))
        self.update_ui_from_config()
    
    def update_ui_from_config(self):
        """Met à jour l'interface utilisateur à partir de la configuration JSON"""
        try:
            config_text = self.template_config_edit.toPlainText()
            if config_text.strip():
                config = json.loads(config_text)
                
                # Mettre à jour les contrôles selon le format actuel
                format_type = self.current_format
                if format_type == "JSON":
                    self.json_pretty_print.setChecked(config.get("pretty_print", True))
                    self.json_include_metadata.setChecked(config.get("include_metadata", True))
                elif format_type == "CSV":
                    self.csv_include_headers.setChecked(config.get("include_headers", True))
                elif format_type == "XML":
                    self.xml_pretty_print.setChecked(config.get("pretty_print", True))
                elif format_type == "YAML":
                    self.yaml_include_metadata.setChecked(config.get("include_metadata", True))
                elif format_type == "Texte":
                    self.text_include_timestamp.setChecked(config.get("include_timestamp", True))
                    
        except json.JSONDecodeError:
            # Ignorer les erreurs de parsing pour l'instant
            pass
    
    def generate_example(self):
        """Génère un exemple de dataset"""
        try:
            # Récupérer la configuration du template
            config_text = self.template_config_edit.toPlainText()
            config = json.loads(config_text) if config_text.strip() else {}
            
            # Valider la configuration
            if not template_manager.validate_template_config(self.current_format, config):
                QMessageBox.warning(self, "Configuration invalide", 
                                  "La configuration du template n'est pas valide pour ce format.")
                return
            
            # Générer l'exemple
            example_content = template_manager.generate_example(self.current_format, config)
            self.current_dataset = example_content
            
            # Mettre à jour la prévisualisation
            self.update_preview()
            
            # Activer le bouton d'export
            self.export_btn.setEnabled(True)
            
            # Mettre à jour les statistiques
            self.update_stats(example_content)
            
            # Ajouter une entrée de log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_widget.add_log(timestamp, "INFO", "Exemple de dataset généré avec succès")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur de génération", 
                               f"Erreur lors de la génération de l'exemple:\n{str(e)}")
            
            # Ajouter une entrée de log d'erreur
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_widget.add_log(timestamp, "ERROR", f"Erreur de génération: {str(e)}")
    
    def update_preview(self):
        """Met à jour la prévisualisation"""
        if not self.current_dataset:
            return
            
        try:
            # Formater le dataset selon le format actuel
            config_text = self.template_config_edit.toPlainText()
            config = json.loads(config_text) if config_text.strip() else {}
            
            # Pour l'exemple, on affiche directement le contenu généré
            # Dans une implémentation réelle, on formaterait le dataset actuel
            self.preview_edit.setPlainText(str(self.current_dataset))
            
        except Exception as e:
            self.preview_edit.setPlainText(f"Erreur de formatage: {str(e)}")
    
    def update_stats(self, content):
        """Met à jour les statistiques"""
        if content:
            char_count = len(str(content))
            line_count = str(content).count('\n') + 1
            self.stats_label.setText(
                f"Caractères: {char_count} | Lignes: {line_count} | Format: {self.current_format}"
            )
        else:
            self.stats_label.setText("Aucun dataset généré")
    
    def export_dataset(self):
        """Exporte le dataset généré"""
        if not self.current_dataset:
            QMessageBox.warning(self, "Aucun dataset", "Aucun dataset à exporter.")
            return
        
        try:
            # Dans une implémentation réelle, on sauvegarderait le fichier
            # Pour l'instant, on affiche un message de confirmation
            QMessageBox.information(self, "Export réussi", 
                                  f"Dataset exporté au format {self.current_format} avec succès!")
            
            # Émettre le signal pour d'autres composants
            self.dataset_generated.emit({"content": self.current_dataset}, self.current_format)
            
            # Ajouter une entrée de log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_widget.add_log(timestamp, "INFO", f"Dataset exporté au format {self.current_format}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'export", 
                               f"Erreur lors de l'export:\n{str(e)}")
            
            # Ajouter une entrée de log d'erreur
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_widget.add_log(timestamp, "ERROR", f"Erreur d'export: {str(e)}")
    
    def get_current_config(self):
        """Retourne la configuration actuelle"""
        return {
            "format": self.current_format,
            "template_config": json.loads(self.template_config_edit.toPlainText()) 
                              if self.template_config_edit.toPlainText().strip() else {}
        }


# Test de l'interface
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Appliquer un style global
    app.setStyle(QStyleFactory.create("Fusion"))
    
    widget = GenerationWidget()
    widget.show()
    
    sys.exit(app.exec_())