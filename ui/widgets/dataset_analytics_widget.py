#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/dataset_analytics_widget.py
Widget d'analyse et de visualisation des datasets
"""

import os
import json
import numpy as np
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QPushButton, QScrollArea,
                             QFrame, QGridLayout, QSizePolicy, QSpacerItem)
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush
#from PyQt5.QtChart import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PyQt5.QtCore import Qt

from core.data.database import Database
from utils.logger import logger


class AnalyticsPieChart(QWidget):
    """Diagramme circulaire interactif pour l'analyse des typologies"""
    
    # Signal émis lorsque le diagramme est mis à jour
    chart_updated = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.current_level = "cluster"  # "cluster" ou "typologie"
        self.selected_cluster = None
        self.back_button_rect = None
        self.setMinimumSize(600, 400)
        
    def set_data(self, data):
        """Définit les données à afficher"""
        self.data = data
        self.current_level = "cluster"
        self.selected_cluster = None
        self.update()
        self.chart_updated.emit()
        
    def paintEvent(self, event):
        """Dessine le diagramme circulaire"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fond
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        if not self.data:
            self._draw_no_data(painter)
            return
            
        if self.current_level == "cluster":
            self._draw_cluster_level(painter)
        else:
            self._draw_typology_level(painter)
            
    def _draw_no_data(self, painter):
        """Affiche un message lorsqu'il n'y a pas de données"""
        painter.setFont(QFont("Arial", 14))
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(self.rect(), Qt.AlignCenter, "Aucune donnée disponible\nGénérez d'abord un dataset")
        
    def _draw_cluster_level(self, painter):
        """Dessine le niveau cluster"""
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 3
        
        # Calcul des totaux
        total = sum(cluster["total"] for cluster in self.data.values())
        if total == 0:
            self._draw_no_data(painter)
            return
            
        # Couleurs pour les clusters
        colors = [
            QColor(65, 105, 225),   # Royal Blue
            QColor(220, 20, 60),    # Crimson
            QColor(46, 139, 87),    # Sea Green
            QColor(255, 140, 0),    # Dark Orange
            QColor(148, 0, 211),    # Dark Violet
            QColor(255, 69, 0),     # Red Orange
            QColor(30, 144, 255),   # Dodger Blue
            QColor(50, 205, 50),    # Lime Green
        ]
        
        # Dessin du diagramme circulaire
        start_angle = 0
        color_index = 0
        
        for cluster_name, cluster_data in self.data.items():
            percentage = (cluster_data["total"] / total) * 100
            angle = (percentage * 360) // 100
            
            # Sélection de la couleur
            color = colors[color_index % len(colors)]
            if self.selected_cluster == cluster_name:
                color = color.darker(120)  # Plus foncé pour la sélection
                
            # Dessin de la section
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawPie(center_x - radius, center_y - radius, 
                           radius * 2, radius * 2, start_angle * 16, angle * 16)
            
            # Étiquette
            label_angle = start_angle + angle / 2
            label_x = center_x + (radius + 30) * np.cos(np.radians(label_angle))
            label_y = center_y - (radius + 30) * np.sin(np.radians(label_angle))
            
            painter.setPen(QPen(Qt.black))
            painter.drawText(int(label_x) - 50, int(label_y) - 10, 100, 20, 
                           Qt.AlignCenter, f"{cluster_name}\n{percentage:.1f}%")
            
            start_angle += angle
            color_index += 1
            
        # Légende
        self._draw_legend(painter, colors)
        
    def _draw_typology_level(self, painter):
        """Dessine le niveau typologie détaillé"""
        if not self.selected_cluster or self.selected_cluster not in self.data:
            return
            
        cluster_data = self.data[self.selected_cluster]
        typologies = cluster_data.get("typologies", {})
        
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 3
        
        total = cluster_data["total"]
        if total == 0:
            return
            
        # Couleurs pour les typologies (nuances de la couleur du cluster)
        base_color = QColor(65, 105, 225)  # Couleur de base
        colors = []
        for i in range(len(typologies)):
            factor = 0.7 + (i * 0.3) / len(typologies)
            colors.append(QColor(
                min(255, int(base_color.red() * factor)),
                min(255, int(base_color.green() * factor)),
                min(255, int(base_color.blue() * factor))
            ))
        
        # Dessin du diagramme
        start_angle = 0
        color_index = 0
        
        for typology_name, count in typologies.items():
            percentage = (count / total) * 100
            angle = (percentage * 360) // 100
            
            color = colors[color_index % len(colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawPie(center_x - radius, center_y - radius, 
                           radius * 2, radius * 2, start_angle * 16, angle * 16)
            
            # Étiquette
            if angle > 10:  # N'afficher que les sections significatives
                label_angle = start_angle + angle / 2
                label_x = center_x + (radius + 40) * np.cos(np.radians(label_angle))
                label_y = center_y - (radius + 40) * np.sin(np.radians(label_angle))
                
                painter.setPen(QPen(Qt.black))
                painter.drawText(int(label_x) - 60, int(label_y) - 15, 120, 30, 
                               Qt.AlignCenter, f"{typology_name}\n{count} ({percentage:.1f}%)")
            
            start_angle += angle
            color_index += 1
            
        # Titre
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.setPen(QPen(QColor(50, 50, 50)))
        painter.drawText(10, 30, width - 20, 40, Qt.AlignCenter, 
                        f"Typologies - {self.selected_cluster}")
                        
        # Bouton retour
        self._draw_back_button(painter)
        
    def _draw_legend(self, painter, colors):
        """Dessine la légende"""
        painter.setFont(QFont("Arial", 10))
        x = 20
        y = self.height() - 150
        box_size = 15
        
        color_index = 0
        for cluster_name, cluster_data in self.data.items():
            if color_index >= len(colors):
                break
                
            color = colors[color_index]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawRect(x, y, box_size, box_size)
            
            total_all = sum(c["total"] for c in self.data.values())
            percentage = (cluster_data["total"] / total_all) * 100 if total_all > 0 else 0
            painter.setPen(QPen(Qt.black))
            painter.drawText(x + box_size + 10, y + box_size - 2, 
                           f"{cluster_name}: {cluster_data['total']} échantillons ({percentage:.1f}%)")
            
            y += 25
            color_index += 1
            
    def _draw_back_button(self, painter):
        """Dessine le bouton retour"""
        button_rect = QtCore.QRect(20, 20, 100, 30)
        
        # Fond du bouton
        painter.setBrush(QBrush(QColor(200, 200, 200)))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(button_rect)
        
        # Texte
        painter.setPen(QPen(QColor(50, 50, 50)))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(button_rect, Qt.AlignCenter, "← Retour")
        
        self.back_button_rect = button_rect
        
    def mousePressEvent(self, event):
        """Gère les clics sur le diagramme"""
        if not self.data:
            return
            
        if self.current_level == "cluster":
            # Vérifier si un cluster a été cliqué
            width = self.width()
            height = self.height()
            center_x = width // 2
            center_y = height // 2
            radius = min(width, height) // 3
            
            # Calcul de la position relative
            click_x = event.pos().x() - center_x
            click_y = center_y - event.pos().y()  # Inversion Y pour les coordonnées polaires
            
            # Conversion en coordonnées polaires
            distance = np.sqrt(click_x**2 + click_y**2)
            angle = np.degrees(np.arctan2(click_y, click_x))
            if angle < 0:
                angle += 360
                
            if distance <= radius:
                # Trouver le cluster correspondant à cet angle
                total = sum(cluster["total"] for cluster in self.data.values())
                current_angle = 0
                
                for cluster_name, cluster_data in self.data.items():
                    percentage = (cluster_data["total"] / total) * 100
                    cluster_angle = (percentage * 360) / 100
                    
                    if current_angle <= angle < current_angle + cluster_angle:
                        self.selected_cluster = cluster_name
                        self.current_level = "typologie"
                        self.update()
                        self.chart_updated.emit()
                        return
                        
                    current_angle += cluster_angle
                    
        else:  # Niveau typologie
            # Vérifier le bouton retour
            if self.back_button_rect and self.back_button_rect.contains(event.pos()):
                self.current_level = "cluster"
                self.selected_cluster = None
                self.update()
                self.chart_updated.emit()
                
    def get_current_level(self):
        """Retourne le niveau actuel d'affichage"""
        return self.current_level, self.selected_cluster


class DatasetAnalyticsWidget(QWidget):
    """Widget complet d'analyse des datasets"""
    
    dataset_loaded = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.current_dataset = None
        self.analytics_data = {}
        
        self._init_ui()
        self._init_connections()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # En-tête
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Analyse des Datasets")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #A23B2D;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Sélecteur de dataset
        header_layout.addWidget(QLabel("Dataset:"))
        self.dataset_combo = QComboBox()
        self.dataset_combo.setMinimumWidth(200)
        header_layout.addWidget(self.dataset_combo)
        
        self.load_btn = QPushButton("Charger")
        self.load_btn.setStyleSheet("background-color: #A23B2D; color: white; padding: 5px 15px;")
        header_layout.addWidget(self.load_btn)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setToolTip("Rafraîchir la liste")
        self.refresh_btn.setStyleSheet("padding: 5px 10px;")
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Zone de diagramme
        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("background-color: white; border: 1px solid #cccccc;")
        chart_layout = QVBoxLayout(chart_frame)
        
        self.analytics_chart = AnalyticsPieChart()
        chart_layout.addWidget(self.analytics_chart)
        
        main_layout.addWidget(chart_frame)
        
        # Statistiques détaillées
        stats_group = QGroupBox("Statistiques Détaillées")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {}
        metrics = ["total_echantillons", "clusters", "typologies", "date_creation", "derniere_maj"]
        
        for i, metric in enumerate(metrics):
            stats_layout.addWidget(QLabel(metric.replace("_", " ").title() + ":"), i, 0)
            value_label = QLabel("N/A")
            value_label.setStyleSheet("font-weight: bold;")
            stats_layout.addWidget(value_label, i, 1)
            self.stats_labels[metric] = value_label
        
        main_layout.addWidget(stats_group)
        
        # Informations sur la sélection
        self.selection_info = QLabel("Sélectionnez un dataset pour voir l'analyse")
        self.selection_info.setStyleSheet("font-style: italic; color: #666666; padding: 10px;")
        self.selection_info.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.selection_info)
        
    def _init_connections(self):
        """Initialise les connexions"""
        self.load_btn.clicked.connect(self._on_load_dataset)
        self.refresh_btn.clicked.connect(self.refresh_datasets)
        # Correction : utilisation du signal personnalisé chart_updated au lieu de update
        self.analytics_chart.chart_updated.connect(self._on_chart_update)
        
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        self.refresh_datasets()
        
    def refresh_datasets(self):
        """Rafraîchit la liste des datasets"""
        self.dataset_combo.clear()
        
        if not self.database:
            return
            
        try:
            # Récupérer la liste des datasets depuis la base de données
            # Pour l'instant, on utilise des données simulées
            datasets = self._get_sample_datasets()
            
            for dataset in datasets:
                self.dataset_combo.addItem(dataset["name"], dataset["id"])
                
            if datasets:
                self.selection_info.setText(f"{len(datasets)} datasets disponibles")
            else:
                self.selection_info.setText("Aucun dataset disponible")
                
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement des datasets: {str(e)}")
            self.selection_info.setText("Erreur de chargement")
            
    def _get_sample_datasets(self):
        """Retourne des datasets d'exemple (à remplacer par les vraies données)"""
        return [
            {"id": 1, "name": "Dataset Principal", "samples": 1500},
            {"id": 2, "name": "Dataset de Test", "samples": 450},
            {"id": 3, "name": "Dataset Validation", "samples": 300}
        ]
        
    def _generate_sample_analytics(self, dataset_id):
        """Génère des données analytiques d'exemple"""
        # Données simulées pour la démonstration
        clusters_data = {
            "Analyse de Texte": {
                "total": 650,
                "typologies": {
                    "Analyse de sentiment": 250,
                    "Classification": 200,
                    "Résumé automatique": 150,
                    "Extraction d'information": 50
                }
            },
            "Génération": {
                "total": 450,
                "typologies": {
                    "Génération créative": 200,
                    "Question-Réponse": 150,
                    "Traduction": 100
                }
            },
            "Code": {
                "total": 300,
                "typologies": {
                    "Génération de code": 150,
                    "Debugging": 100,
                    "Documentation": 50
                }
            },
            "Données": {
                "total": 250,
                "typologies": {
                    "Analyse de données": 120,
                    "Visualisation": 80,
                    "Nettoyage": 50
                }
            }
        }
        
        return clusters_data
        
    def _on_load_dataset(self):
        """Charge le dataset sélectionné"""
        current_index = self.dataset_combo.currentIndex()
        if current_index < 0:
            return
            
        dataset_id = self.dataset_combo.itemData(current_index)
        dataset_name = self.dataset_combo.currentText()
        
        try:
            # Charger les données analytiques (simulées pour l'instant)
            self.analytics_data = self._generate_sample_analytics(dataset_id)
            
            # Mettre à jour le diagramme
            self.analytics_chart.set_data(self.analytics_data)
            
            # Mettre à jour les statistiques
            self._update_statistics(dataset_name)
            
            # Mettre à jour les informations
            total_samples = sum(cluster["total"] for cluster in self.analytics_data.values())
            self.selection_info.setText(
                f"Dataset: {dataset_name} | {total_samples} échantillons | "
                f"{len(self.analytics_data)} clusters | "
                f"{sum(len(cluster['typologies']) for cluster in self.analytics_data.values())} typologies"
            )
            
            logger.info(f"Dataset chargé: {dataset_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du dataset: {str(e)}")
            self.selection_info.setText(f"Erreur: {str(e)}")
            
    def _update_statistics(self, dataset_name):
        """Met à jour les statistiques affichées"""
        if not self.analytics_data:
            return
            
        total_samples = sum(cluster["total"] for cluster in self.analytics_data.values())
        num_clusters = len(self.analytics_data)
        num_typologies = sum(len(cluster["typologies"]) for cluster in self.analytics_data.values())
        
        self.stats_labels["total_echantillons"].setText(f"{total_samples:,}")
        self.stats_labels["clusters"].setText(str(num_clusters))
        self.stats_labels["typologies"].setText(str(num_typologies))
        self.stats_labels["date_creation"].setText(datetime.now().strftime("%d/%m/%Y"))
        self.stats_labels["derniere_maj"].setText(datetime.now().strftime("%d/%m/%Y %H:%M"))
        
    def _on_chart_update(self):
        """Met à jour l'interface lors des changements du diagramme"""
        level, cluster = self.analytics_chart.get_current_level()
        
        if level == "typologie" and cluster:
            cluster_data = self.analytics_data.get(cluster, {})
            typologies = cluster_data.get("typologies", {})
            
            typology_text = " | ".join([f"{k}: {v}" for k, v in typologies.items()])
            self.selection_info.setText(
                f"Cluster: {cluster} | {cluster_data.get('total', 0)} échantillons | {typology_text}"
            )
        else:
            # Réinitialiser l'info si on est au niveau cluster
            current_index = self.dataset_combo.currentIndex()
            if current_index >= 0:
                dataset_name = self.dataset_combo.currentText()
                total_samples = sum(cluster["total"] for cluster in self.analytics_data.values())
                self.selection_info.setText(
                    f"Dataset: {dataset_name} | {total_samples} échantillons | "
                    f"{len(self.analytics_data)} clusters | "
                    f"{sum(len(cluster['typologies']) for cluster in self.analytics_data.values())} typologies"
                )
            
    def update_language(self):
        """Met à jour les textes selon la langue"""
        # Implémenter les traductions si nécessaire
        pass