#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Widget de Génération Amélioré pour Liris
Intègre toutes les fonctionnalités manquantes :
- Sélection de typologies de contexte
- Configuration des batches
- Visualisations PyQtGraph (camembert, statistiques)
- Enrichissement automatique des prompts
- Gestion par lots
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QSpinBox, QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QSplitter, QTabWidget, QProgressBar, QCheckBox,
    QMessageBox, QInputDialog, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QFrame, QGridLayout, QSlider, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette

import pyqtgraph as pg
import numpy as np

# Import de la classe Database existante
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from data.database import Database
except ImportError:
    # Fallback si le module n'est pas trouvé
    class Database:
        def __init__(self, db_path=None):
            self.db_path = db_path or "/tmp/liris_fallback.db"
            self.conn = sqlite3.connect(self.db_path)
            self._init_fallback_tables()
        
        def _init_fallback_tables(self):
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clusters (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS labels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    cluster_id TEXT,
                    parent_id TEXT,
                    level INTEGER,
                    created_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS generation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_base TEXT,
                    context_ids TEXT,
                    batch_count INTEGER,
                    created_at TEXT,
                    status TEXT
                )
            ''')
            self.conn.commit()


class ContextStatistics:
    """Classe pour gérer les statistiques d'utilisation des contextes"""
    
    def __init__(self, database: Database):
        self.db = database
        
    def get_context_usage_stats(self) -> Dict[str, int]:
        """Récupère les statistiques d'utilisation des contextes"""
        try:
            cursor = self.db.conn.cursor()
            
            # Compter l'utilisation de chaque contexte dans l'historique
            cursor.execute('''
                SELECT context_ids, COUNT(*) as usage_count
                FROM generation_history 
                WHERE status = 'completed'
                GROUP BY context_ids
            ''')
            
            results = cursor.fetchall()
            stats = {}
            
            for context_ids_str, count in results:
                if context_ids_str:
                    context_ids = json.loads(context_ids_str)
                    for context_id in context_ids:
                        stats[context_id] = stats.get(context_id, 0) + count
            
            return stats
            
        except Exception as e:
            print(f"Erreur lors de la récupération des statistiques: {e}")
            return {}
    
    def get_context_names(self, context_ids: List[str]) -> Dict[str, str]:
        """Récupère les noms des contextes à partir de leurs IDs"""
        try:
            cursor = self.db.conn.cursor()
            names = {}
            
            for context_id in context_ids:
                # Essayer d'abord dans les clusters
                cursor.execute('SELECT name FROM clusters WHERE id = ?', (context_id,))
                result = cursor.fetchone()
                if result:
                    names[context_id] = result[0]
                    continue
                
                # Puis dans les labels
                cursor.execute('SELECT name FROM labels WHERE id = ?', (context_id,))
                result = cursor.fetchone()
                if result:
                    names[context_id] = result[0]
            
            return names
            
        except Exception as e:
            print(f"Erreur lors de la récupération des noms: {e}")
            return {}


class GenerationWorkerEnhanced(QThread):
    """Worker thread amélioré pour la génération par lots"""
    
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    batch_completed = pyqtSignal(int, dict)
    generation_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, database: Database, config: Dict):
        super().__init__()
        self.db = database
        self.config = config
        self.is_running = True
        
    def run(self):
        """Exécute la génération par lots"""
        try:
            total_batches = self.config.get('batch_count', 1)
            base_prompt = self.config.get('base_prompt', '')
            selected_contexts = self.config.get('selected_contexts', [])
            
            results = {
                'total_batches': total_batches,
                'completed_batches': 0,
                'failed_batches': 0,
                'generated_datasets': [],
                'start_time': datetime.now().isoformat()
            }
            
            for batch_num in range(total_batches):
                if not self.is_running:
                    break
                
                self.status_updated.emit(f"Génération du lot {batch_num + 1}/{total_batches}")
                
                # Enrichir le prompt avec les contextes
                enriched_prompt = self._enrich_prompt(base_prompt, selected_contexts, batch_num)
                
                # Simuler la génération (à remplacer par l'appel réel à l'IA)
                batch_result = self._generate_batch(enriched_prompt, batch_num)
                
                if batch_result['success']:
                    results['completed_batches'] += 1
                    results['generated_datasets'].append(batch_result['data'])
                    self.batch_completed.emit(batch_num, batch_result)
                else:
                    results['failed_batches'] += 1
                    self.error_occurred.emit(f"Erreur lot {batch_num + 1}: {batch_result['error']}")
                
                # Mettre à jour la progression
                progress = int((batch_num + 1) / total_batches * 100)
                self.progress_updated.emit(progress)
                
                # Pause entre les lots
                time.sleep(0.5)
            
            results['end_time'] = datetime.now().isoformat()
            self._save_generation_history(results)
            self.generation_finished.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(f"Erreur générale: {str(e)}")
    
    def _enrich_prompt(self, base_prompt: str, contexts: List[Dict], batch_num: int) -> str:
        """Enrichit le prompt de base avec les contextes sélectionnés"""
        enriched = f"PROMPT DE BASE:\n{base_prompt}\n\n"
        enriched += f"CONTEXTES SÉLECTIONNÉS (Lot {batch_num + 1}):\n"
        
        for i, context in enumerate(contexts):
            enriched += f"{i+1}. {context.get('name', 'Contexte inconnu')}\n"
            if context.get('description'):
                enriched += f"   Description: {context['description']}\n"
            if context.get('hierarchy'):
                enriched += f"   Hiérarchie: {' > '.join(context['hierarchy'])}\n"
        
        enriched += f"\nINSTRUCTIONS:\nGénérez un dataset en utilisant le prompt de base enrichi avec les contextes ci-dessus. Lot {batch_num + 1}.\n"
        
        return enriched
    
    def _generate_batch(self, prompt: str, batch_num: int) -> Dict:
        """Génère un lot de données (simulation)"""
        try:
            # Simulation de génération - à remplacer par l'appel réel
            time.sleep(1)  # Simuler le temps de traitement
            
            return {
                'success': True,
                'data': {
                    'batch_id': batch_num,
                    'prompt': prompt,
                    'generated_content': f"Dataset généré pour le lot {batch_num + 1}",
                    'timestamp': datetime.now().isoformat(),
                    'token_count': np.random.randint(100, 500)
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_generation_history(self, results: Dict):
        """Sauvegarde l'historique de génération"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                INSERT INTO generation_history 
                (prompt_base, context_ids, batch_count, created_at, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                self.config.get('base_prompt', ''),
                json.dumps([ctx.get('id', '') for ctx in self.config.get('selected_contexts', [])]),
                results['total_batches'],
                results['start_time'],
                'completed' if results['failed_batches'] == 0 else 'partial'
            ))
            self.db.conn.commit()
        except Exception as e:
            print(f"Erreur sauvegarde historique: {e}")
    
    def stop(self):
        """Arrête la génération"""
        self.is_running = False


class GenerationWidget(QWidget):
    """Widget de génération amélioré avec toutes les fonctionnalités"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.statistics = None
        self.generation_worker = None
        
        # Configuration des couleurs (respectant le thème existant)
        self.colors = {
            'primary': '#A23B2D',
            'secondary': '#A23B2D', 
            'accent': '#A23B2D',
            'danger': '#A23B2D',
            'success': '#A23B2D',
            'background': '#A23B2D',
            'text': '#333333'
        }
        
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre principal
        title_label = QLabel("Génération de Datasets")
        title_label.setStyleSheet(f"""
            font-size: 18px; 
            font-weight: bold; 
            color: {self.colors['primary']};
            margin: 10px;
            padding: 10px;
        """)
        layout.addWidget(title_label)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Panneau de configuration (gauche)
        config_widget = self._create_configuration_panel()
        main_splitter.addWidget(config_widget)
        
        # Panneau de visualisation (droite)
        viz_widget = self._create_visualization_panel()
        main_splitter.addWidget(viz_widget)
        
        # Définir les proportions
        main_splitter.setSizes([500, 700])
        
        # Barre de contrôle en bas
        control_layout = self._create_control_bar()
        layout.addLayout(control_layout)
        
    def _create_configuration_panel(self) -> QWidget:
        """Crée le panneau de configuration"""
        widget = QGroupBox("Configuration de Génération")
        widget.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {self.colors['primary']};
                border-radius: 8px;
                margin: 5px;
                padding-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        
        # 1. Sélection de typologies de contexte
        typology_group = self._create_typology_selection()
        layout.addWidget(typology_group)
        
        # 2. Prompt de base
        prompt_group = self._create_base_prompt_section()
        layout.addWidget(prompt_group)
        
        # 3. Configuration des batches
        batch_group = self._create_batch_configuration()
        layout.addWidget(batch_group)
        
        return widget
    
    def _create_typology_selection(self) -> QGroupBox:
        """Crée la section de sélection des typologies"""
        group = QGroupBox("Sélection de Typologies de Contexte")
        layout = QVBoxLayout(group)
        
        # Arbre des typologies
        self.typology_tree = QTreeWidget()
        self.typology_tree.setHeaderLabels(["Nom", "Type", "Utilisation"])
        layout.addWidget(self.typology_tree)
        
        # Boutons de gestion
        button_layout = QHBoxLayout()
        
        self.refresh_typologies_btn = QPushButton("Actualiser")
        self.refresh_typologies_btn.setStyleSheet(self._get_button_style(self.colors['secondary']))
        
        self.select_all_btn = QPushButton("Tout sélectionner")
        self.select_all_btn.setStyleSheet(self._get_button_style(self.colors['accent']))
        
        self.clear_selection_btn = QPushButton("Tout désélectionner")
        self.clear_selection_btn.setStyleSheet(self._get_button_style(self.colors['danger']))
        
        button_layout.addWidget(self.refresh_typologies_btn)
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.clear_selection_btn)
        
        layout.addLayout(button_layout)
        
        return group
    
    def _create_base_prompt_section(self) -> QGroupBox:
        """Crée la section du prompt de base"""
        group = QGroupBox("Prompt de Base")
        layout = QVBoxLayout(group)
        
        # Zone de texte pour le prompt
        self.base_prompt_edit = QTextEdit()
        self.base_prompt_edit.setPlaceholderText(
            "Entrez votre prompt de base ici...\n\n"
            "Ce prompt sera automatiquement enrichi avec les contextes sélectionnés "
            "pour chaque lot de génération."
        )
        self.base_prompt_edit.setMaximumHeight(120)
        layout.addWidget(self.base_prompt_edit)
        
        # Compteur de caractères
        self.char_count_label = QLabel("Caractères: 0")
        self.char_count_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.char_count_label)
        
        return group
    
    def _create_batch_configuration(self) -> QGroupBox:
        """Crée la section de configuration des batches"""
        group = QGroupBox("Configuration des Lots")
        layout = QGridLayout(group)
        
        # Nombre de lots
        layout.addWidget(QLabel("Nombre de lots:"), 0, 0)
        self.batch_count_spin = QSpinBox()
        self.batch_count_spin.setRange(1, 100)
        self.batch_count_spin.setValue(5)
        layout.addWidget(self.batch_count_spin, 0, 1)
        
        # Délai entre lots
        layout.addWidget(QLabel("Délai entre lots (s):"), 1, 0)
        self.batch_delay_spin = QDoubleSpinBox()
        self.batch_delay_spin.setRange(0.1, 60.0)
        self.batch_delay_spin.setValue(1.0)
        self.batch_delay_spin.setSingleStep(0.1)
        layout.addWidget(self.batch_delay_spin, 1, 1)
        
        # Options avancées
        self.auto_enrich_checkbox = QCheckBox("Enrichissement automatique des prompts")
        self.auto_enrich_checkbox.setChecked(True)
        layout.addWidget(self.auto_enrich_checkbox, 2, 0, 1, 2)
        
        self.save_intermediate_checkbox = QCheckBox("Sauvegarder les résultats intermédiaires")
        self.save_intermediate_checkbox.setChecked(True)
        layout.addWidget(self.save_intermediate_checkbox, 3, 0, 1, 2)
        
        return group
    
    def _create_visualization_panel(self) -> QWidget:
        """Crée le panneau de visualisation"""
        widget = QGroupBox("Visualisations et Statistiques")
        widget.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {self.colors['accent']};
                border-radius: 8px;
                margin: 5px;
                padding-top: 15px;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        
        # Onglets de visualisation
        self.viz_tabs = QTabWidget()
        layout.addWidget(self.viz_tabs)
        
        # Onglet 1: Diagramme circulaire
        pie_widget = self._create_pie_chart_tab()
        self.viz_tabs.addTab(pie_widget, "Utilisation Contextes")
        
        # Onglet 2: Historique des générations
        history_widget = self._create_history_tab()
        self.viz_tabs.addTab(history_widget, "Historique")
        
        # Onglet 3: Progression en temps réel
        progress_widget = self._create_progress_tab()
        self.viz_tabs.addTab(progress_widget, "Progression")
        
        return widget
    
    def _create_pie_chart_tab(self) -> QWidget:
        """Crée l'onglet avec le diagramme circulaire"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Widget PyQtGraph pour le diagramme circulaire
        self.pie_chart_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.pie_chart_widget)
        
        # Légende et statistiques
        stats_layout = QHBoxLayout()
        
        self.stats_label = QLabel("Statistiques d'utilisation des contextes")
        self.stats_label.setStyleSheet("font-weight: bold; margin: 10px;")
        stats_layout.addWidget(self.stats_label)
        
        self.refresh_stats_btn = QPushButton("Actualiser")
        self.refresh_stats_btn.setStyleSheet(self._get_button_style(self.colors['secondary']))
        stats_layout.addWidget(self.refresh_stats_btn)
        
        layout.addLayout(stats_layout)
        
        # Initialiser le graphique
        self._init_pie_chart()
        
        return widget
    
    def _create_history_tab(self) -> QWidget:
        """Crée l'onglet d'historique des générations"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Liste des générations passées
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        
        # Boutons de gestion de l'historique
        history_buttons = QHBoxLayout()
        
        self.load_history_btn = QPushButton("Charger Historique")
        self.load_history_btn.setStyleSheet(self._get_button_style(self.colors['primary']))
        
        self.clear_history_btn = QPushButton("Vider Historique")
        self.clear_history_btn.setStyleSheet(self._get_button_style(self.colors['danger']))
        
        self.export_history_btn = QPushButton("Exporter")
        self.export_history_btn.setStyleSheet(self._get_button_style(self.colors['accent']))
        
        history_buttons.addWidget(self.load_history_btn)
        history_buttons.addWidget(self.clear_history_btn)
        history_buttons.addWidget(self.export_history_btn)
        
        layout.addLayout(history_buttons)
        
        return widget
    
    def _create_progress_tab(self) -> QWidget:
        """Crée l'onglet de progression en temps réel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Barre de progression principale
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self.colors['primary']};
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {self.colors['success']};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.main_progress_bar)
        
        # Statut actuel
        self.status_label = QLabel("Prêt à générer")
        self.status_label.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Journal des opérations
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        return widget
    
    def _create_control_bar(self) -> QHBoxLayout:
        """Crée la barre de contrôle en bas"""
        layout = QHBoxLayout()
        
        # Bouton de génération principal
        self.start_generation_btn = QPushButton("Démarrer la Génération")
        self.start_generation_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['success']};
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
            }}
        """)
        
        # Bouton d'arrêt
        self.stop_generation_btn = QPushButton("Arrêter")
        self.stop_generation_btn.setStyleSheet(self._get_button_style(self.colors['danger']))
        self.stop_generation_btn.setEnabled(False)
        
        # Bouton d'aperçu
        self.preview_btn = QPushButton("Aperçu")
        self.preview_btn.setStyleSheet(self._get_button_style(self.colors['accent']))
        
        layout.addWidget(self.start_generation_btn)
        layout.addWidget(self.stop_generation_btn)
        layout.addWidget(self.preview_btn)
        layout.addStretch()
        
        return layout
    
    def _get_button_style(self, color: str) -> str:
        """Retourne le style CSS pour un bouton avec la couleur spécifiée"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
            }}
        """
    
    def _init_pie_chart(self):
        """Initialise le diagramme circulaire"""
        # Créer un graphique circulaire simple avec PyQtGraph
        self.pie_plot = self.pie_chart_widget.addPlot(title="Utilisation des Contextes")
        self.pie_plot.hideAxis('left')
        self.pie_plot.hideAxis('bottom')
        
        # Données d'exemple (sera remplacé par les vraies données)
        self._update_pie_chart_with_sample_data()
    
    def _update_pie_chart_with_sample_data(self):
        """Met à jour le diagramme avec des données d'exemple"""
        # Données d'exemple
        labels = ['Cluster A', 'Cluster B', 'Cluster C', 'Cluster D']
        values = [30, 25, 20, 25]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        
        # Créer un diagramme circulaire simple
        angles = np.linspace(0, 2*np.pi, len(values)+1)
        
        for i, (label, value, color) in enumerate(zip(labels, values, colors)):
            # Calculer les coordonnées pour chaque secteur
            start_angle = angles[i]
            end_angle = angles[i+1]
            
            # Créer les points du secteur
            theta = np.linspace(start_angle, end_angle, 50)
            x = np.concatenate([[0], np.cos(theta), [0]])
            y = np.concatenate([[0], np.sin(theta), [0]])
            
            # Ajouter le secteur au graphique
            brush = pg.mkBrush(color)
            self.pie_plot.plot(x, y, fillLevel=0, brush=brush, pen=pg.mkPen('white', width=2))
    
    def setup_connections(self):
        """Configure les connexions des signaux"""
        # Connexions des boutons
        self.refresh_typologies_btn.clicked.connect(self.load_typologies)
        self.select_all_btn.clicked.connect(self.select_all_typologies)
        self.clear_selection_btn.clicked.connect(self.clear_typology_selection)
        
        self.start_generation_btn.clicked.connect(self.start_generation)
        self.stop_generation_btn.clicked.connect(self.stop_generation)
        self.preview_btn.clicked.connect(self.show_preview)
        
        self.refresh_stats_btn.clicked.connect(self.refresh_statistics)
        self.load_history_btn.clicked.connect(self.load_generation_history)
        self.clear_history_btn.clicked.connect(self.clear_generation_history)
        self.export_history_btn.clicked.connect(self.export_generation_history)
        
        # Connexion du compteur de caractères
        self.base_prompt_edit.textChanged.connect(self.update_char_count)
    
    def set_database(self, database: Database):
        """Configure la base de données"""
        self.database = database
        self.statistics = ContextStatistics(database)
        self.load_typologies()
        self.refresh_statistics()
        self.load_generation_history()
    
    def set_conductor(self, conductor):
        """Définit le chef d'orchestre"""
        self.conductor = conductor
    
    def load_typologies(self):
        """Charge les typologies depuis la base de données"""
        if not self.database:
            return
        
        self.typology_tree.clear()
        
        try:
            cursor = self.database.conn.cursor()
            
            # Charger les clusters
            cursor.execute('SELECT id, name, description FROM clusters ORDER BY name')
            clusters = cursor.fetchall()
            
            for cluster_id, cluster_name, cluster_desc in clusters:
                cluster_item = QTreeWidgetItem(self.typology_tree)
                cluster_item.setText(0, cluster_name)
                cluster_item.setText(1, "Cluster")
                cluster_item.setData(0, Qt.UserRole, {
                    'id': cluster_id,
                    'type': 'cluster',
                    'name': cluster_name,
                    'description': cluster_desc
                })
                cluster_item.setCheckState(0, Qt.Unchecked)
                
                # Charger les labels de ce cluster
                cursor.execute('''
                    SELECT id, name, parent_id, level 
                    FROM labels 
                    WHERE cluster_id = ? 
                    ORDER BY level, name
                ''', (cluster_id,))
                
                labels = cursor.fetchall()
                label_items = {}
                
                # Créer les éléments de label en respectant la hiérarchie
                for label_id, label_name, parent_id, level in labels:
                    label_item = QTreeWidgetItem()
                    label_item.setText(0, label_name)
                    label_item.setText(1, f"Label (Niveau {level})")
                    label_item.setData(0, Qt.UserRole, {
                        'id': label_id,
                        'type': 'label',
                        'name': label_name,
                        'cluster_id': cluster_id,
                        'parent_id': parent_id,
                        'level': level
                    })
                    label_item.setCheckState(0, Qt.Unchecked)
                    
                    if parent_id and parent_id in label_items:
                        label_items[parent_id].addChild(label_item)
                    else:
                        cluster_item.addChild(label_item)
                    
                    label_items[label_id] = label_item
                
                cluster_item.setExpanded(True)
        
        except Exception as e:
            self.log_message(f"Erreur lors du chargement des typologies: {e}")
    
    def select_all_typologies(self):
        """Sélectionne toutes les typologies"""
        self._set_all_items_check_state(Qt.Checked)
    
    def clear_typology_selection(self):
        """Désélectionne toutes les typologies"""
        self._set_all_items_check_state(Qt.Unchecked)
    
    def _set_all_items_check_state(self, state):
        """Définit l'état de sélection de tous les éléments"""
        def set_item_state(item):
            item.setCheckState(0, state)
            for i in range(item.childCount()):
                set_item_state(item.child(i))
        
        for i in range(self.typology_tree.topLevelItemCount()):
            set_item_state(self.typology_tree.topLevelItem(i))
    
    def get_selected_contexts(self) -> List[Dict]:
        """Récupère les contextes sélectionnés"""
        selected = []
        
        def check_item(item):
            if item.checkState(0) == Qt.Checked:
                data = item.data(0, Qt.UserRole)
                if data:
                    selected.append(data)
            
            for i in range(item.childCount()):
                check_item(item.child(i))
        
        for i in range(self.typology_tree.topLevelItemCount()):
            check_item(self.typology_tree.topLevelItem(i))
        
        return selected
    
    def start_generation(self):
        """Démarre la génération par lots"""
        # Validation
        base_prompt = self.base_prompt_edit.toPlainText().strip()
        if not base_prompt:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un prompt de base")
            return
        
        selected_contexts = self.get_selected_contexts()
        if not selected_contexts:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner au moins un contexte")
            return
        
        # Configuration
        config = {
            'base_prompt': base_prompt,
            'selected_contexts': selected_contexts,
            'batch_count': self.batch_count_spin.value(),
            'batch_delay': self.batch_delay_spin.value(),
            'auto_enrich': self.auto_enrich_checkbox.isChecked(),
            'save_intermediate': self.save_intermediate_checkbox.isChecked()
        }
        
        # Créer et démarrer le worker
        self.generation_worker = GenerationWorkerEnhanced(self.database, config)
        self.generation_worker.progress_updated.connect(self.update_progress)
        self.generation_worker.status_updated.connect(self.update_status)
        self.generation_worker.batch_completed.connect(self.on_batch_completed)
        self.generation_worker.generation_finished.connect(self.on_generation_finished)
        self.generation_worker.error_occurred.connect(self.on_generation_error)
        
        self.generation_worker.start()
        
        # Mettre à jour l'interface
        self.start_generation_btn.setEnabled(False)
        self.stop_generation_btn.setEnabled(True)
        self.main_progress_bar.setValue(0)
        self.log_message("Génération démarrée...")
        
        # Basculer vers l'onglet de progression
        self.viz_tabs.setCurrentIndex(2)
    
    def stop_generation(self):
        """Arrête la génération en cours"""
        if self.generation_worker:
            self.generation_worker.stop()
            self.generation_worker.wait()
        
        self.start_generation_btn.setEnabled(True)
        self.stop_generation_btn.setEnabled(False)
        self.log_message("Génération arrêtée par l'utilisateur")
    
    def show_preview(self):
        """Affiche un aperçu de la génération"""
        base_prompt = self.base_prompt_edit.toPlainText().strip()
        selected_contexts = self.get_selected_contexts()
        
        if not base_prompt or not selected_contexts:
            QMessageBox.warning(self, "Erreur", "Veuillez configurer le prompt et sélectionner des contextes")
            return
        
        # Créer un aperçu du prompt enrichi
        preview_text = f"APERÇU DE LA GÉNÉRATION\n{'='*50}\n\n"
        preview_text += f"PROMPT DE BASE:\n{base_prompt}\n\n"
        preview_text += f"CONTEXTES SÉLECTIONNÉS ({len(selected_contexts)}):\n"
        
        for i, context in enumerate(selected_contexts):
            preview_text += f"{i+1}. [{context['type']}] {context['name']}\n"
        
        preview_text += f"\nNOMBRE DE LOTS: {self.batch_count_spin.value()}\n"
        preview_text += f"DÉLAI ENTRE LOTS: {self.batch_delay_spin.value()}s\n"
        
        # Afficher dans une boîte de dialogue
        msg = QMessageBox(self)
        msg.setWindowTitle("Aperçu de la Génération")
        msg.setText(preview_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
    
    def refresh_statistics(self):
        """Actualise les statistiques d'utilisation"""
        if not self.statistics:
            return
        
        try:
            # Récupérer les statistiques
            usage_stats = self.statistics.get_context_usage_stats()
            context_names = self.statistics.get_context_names(list(usage_stats.keys()))
            
            # Mettre à jour le diagramme circulaire
            self._update_pie_chart(usage_stats, context_names)
            
            # Mettre à jour le label des statistiques
            total_usage = sum(usage_stats.values())
            self.stats_label.setText(f"Total d'utilisations: {total_usage}")
            
        except Exception as e:
            self.log_message(f"Erreur lors de l'actualisation des statistiques: {e}")
    
    def _update_pie_chart(self, usage_stats: Dict[str, int], context_names: Dict[str, str]):
        """Met à jour le diagramme circulaire avec les vraies données"""
        if not usage_stats:
            return
        
        # Effacer le graphique existant
        self.pie_chart_widget.clear()
        self.pie_plot = self.pie_chart_widget.addPlot(title="Utilisation des Contextes")
        self.pie_plot.hideAxis('left')
        self.pie_plot.hideAxis('bottom')
        
        # Préparer les données
        labels = []
        values = []
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
        
        for context_id, usage_count in usage_stats.items():
            name = context_names.get(context_id, f"Contexte {context_id}")
            labels.append(name)
            values.append(usage_count)
        
        if not values:
            return
        
        # Calculer les angles
        total = sum(values)
        angles = [0]
        for value in values:
            angles.append(angles[-1] + (value / total) * 2 * np.pi)
        
        # Dessiner les secteurs
        for i, (label, value, color) in enumerate(zip(labels, values, colors[:len(labels)])):
            start_angle = angles[i]
            end_angle = angles[i+1]
            
            # Créer les points du secteur
            theta = np.linspace(start_angle, end_angle, 50)
            x = np.concatenate([[0], np.cos(theta), [0]])
            y = np.concatenate([[0], np.sin(theta), [0]])
            
            # Ajouter le secteur
            brush = pg.mkBrush(color)
            self.pie_plot.plot(x, y, fillLevel=0, brush=brush, pen=pg.mkPen('white', width=2))
    
    def load_generation_history(self):
        """Charge l'historique des générations"""
        if not self.database:
            return
        
        self.history_list.clear()
        
        try:
            cursor = self.database.conn.cursor()
            cursor.execute('''
                SELECT prompt_base, context_ids, batch_count, created_at, status
                FROM generation_history
                ORDER BY created_at DESC
                LIMIT 50
            ''')
            
            results = cursor.fetchall()
            
            for prompt_base, context_ids_str, batch_count, created_at, status in results:
                # Créer l'élément de liste
                item_text = f"[{status}] {created_at} - {batch_count} lots"
                if prompt_base:
                    item_text += f" - {prompt_base[:50]}..."
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {
                    'prompt_base': prompt_base,
                    'context_ids': context_ids_str,
                    'batch_count': batch_count,
                    'created_at': created_at,
                    'status': status
                })
                
                # Couleur selon le statut
                if status == 'completed':
                    item.setBackground(QColor('#d4edda'))
                elif status == 'partial':
                    item.setBackground(QColor('#fff3cd'))
                else:
                    item.setBackground(QColor('#f8d7da'))
                
                self.history_list.addItem(item)
        
        except Exception as e:
            self.log_message(f"Erreur lors du chargement de l'historique: {e}")
    
    def clear_generation_history(self):
        """Vide l'historique des générations"""
        reply = QMessageBox.question(
            self, 'Confirmer', 
            'Êtes-vous sûr de vouloir vider l\'historique des générations ?'
        )
        
        if reply == QMessageBox.Yes and self.database:
            try:
                cursor = self.database.conn.cursor()
                cursor.execute('DELETE FROM generation_history')
                self.database.conn.commit()
                self.load_generation_history()
                self.log_message("Historique vidé avec succès")
            except Exception as e:
                self.log_message(f"Erreur lors du vidage de l'historique: {e}")
    
    def export_generation_history(self):
        """Exporte l'historique des générations"""
        # TODO: Implémenter l'export (CSV, JSON, etc.)
        QMessageBox.information(self, "Info", "Fonctionnalité d'export à implémenter")
    
    def update_char_count(self):
        """Met à jour le compteur de caractères"""
        text = self.base_prompt_edit.toPlainText()
        char_count = len(text)
        self.char_count_label.setText(f"Caractères: {char_count}")
    
    @pyqtSlot(int)
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.main_progress_bar.setValue(value)
    
    @pyqtSlot(str)
    def update_status(self, status):
        """Met à jour le statut"""
        self.status_label.setText(status)
        self.log_message(status)
    
    @pyqtSlot(int, dict)
    def on_batch_completed(self, batch_num, result):
        """Gère la completion d'un lot"""
        self.log_message(f"Lot {batch_num + 1} terminé avec succès")
    
    @pyqtSlot(dict)
    def on_generation_finished(self, results):
        """Gère la fin de la génération"""
        self.start_generation_btn.setEnabled(True)
        self.stop_generation_btn.setEnabled(False)
        
        completed = results['completed_batches']
        failed = results['failed_batches']
        total = results['total_batches']
        
        self.log_message(f"🎉 Génération terminée: {completed}/{total} lots réussis")
        
        if failed > 0:
            self.log_message(f"⚠️ {failed} lots ont échoué")
        
        # Actualiser les statistiques
        self.refresh_statistics()
        self.load_generation_history()
    
    @pyqtSlot(str)
    def on_generation_error(self, error):
        """Gère les erreurs de génération"""
        self.log_message(f"❌ Erreur: {error}")
    
    def log_message(self, message: str):
        """Ajoute un message au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Faire défiler vers le bas
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# Test du widget
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Créer une base de données de test
    db = Database("/tmp/test_enhanced_generation.db")
    
    # Créer le widget
    widget = GenerationWidget()
    widget.set_database(db)
    widget.show()
    
    sys.exit(app.exec_())
