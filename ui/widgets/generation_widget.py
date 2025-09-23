from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QTextEdit, QGroupBox, 
                             QSpinBox, QProgressBar, QTabWidget, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QSplitter,
                             QFrame, QCheckBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont, QColor
import sqlite3
import json
import random
from datetime import datetime
import os


class GenerationWorker(QThread):
    """Thread pour la génération de datasets en arrière-plan"""
    
    progress_updated = pyqtSignal(int)
    generation_completed = pyqtSignal(dict)
    generation_failed = pyqtSignal(str)
    
    def __init__(self, config, conductor):
        super().__init__()
        self.config = config
        self.conductor = conductor
        self.is_running = True
        
    def run(self):
        try:
            total_batches = self.config.get('batches', 1)
            results = []
            
            for i in range(total_batches):
                if not self.is_running:
                    break
                    
                # Simuler la génération (à remplacer par l'appel IA réel)
                progress = int((i + 1) / total_batches * 100)
                self.progress_updated.emit(progress)
                
                # Générer un dataset exemple
                dataset = self.generate_dataset(self.config)
                results.append(dataset)
                
                # Pause pour simulation
                self.msleep(500)
                
            if self.is_running:
                self.generation_completed.emit({
                    'datasets': results,
                    'total_batches': total_batches,
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.generation_failed.emit(str(e))
            
    def stop(self):
        self.is_running = False
        
    def generate_dataset(self, config):
        """Génère un dataset basé sur la configuration"""
        # Cette méthode sera remplacée par l'appel IA réel
        return {
            'id': random.randint(1000, 9999),
            'name': f"Dataset_{datetime.now().strftime('%H%M%S')}",
            'content': f"Contenu généré pour {config.get('typology', 'N/A')}",
            'context': config.get('selected_contexts', []),
            'prompt': config.get('prompt', ''),
            'timestamp': datetime.now().isoformat()
        }


class GenerationWidget(QWidget):
    """
    Widget pour l'onglet Génération - Création de datasets avec contexte
    """
    
    # Signaux
    dataset_generated = pyqtSignal(dict)
    generation_started = pyqtSignal()
    generation_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_path = None
        self.conductor = None
        self.generation_worker = None
        self.current_datasets = []
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Génération de Datasets avec Contexte")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Configuration principale
        config_group = QGroupBox("Configuration de Génération")
        config_layout = QVBoxLayout(config_group)
        
        # Ligne 1: Typologies et Contexte
        row1_layout = QHBoxLayout()
        
        # Typologies
        typology_layout = QVBoxLayout()
        typology_layout.addWidget(QLabel("Typologies de Contexte:"))
        self.typology_combo = QComboBox()
        self.typology_combo.setMinimumWidth(200)
        typology_layout.addWidget(self.typology_combo)
        row1_layout.addLayout(typology_layout)
        
        # Contextes disponibles
        context_layout = QVBoxLayout()
        context_layout.addWidget(QLabel("Contextes Disponibles:"))
        self.contexts_list = QComboBox()
        self.contexts_list.setMinimumWidth(200)
        context_layout.addWidget(self.contexts_list)
        row1_layout.addLayout(context_layout)
        
        # Contextes sélectionnés
        selected_layout = QVBoxLayout()
        selected_layout.addWidget(QLabel("Contextes Sélectionnés:"))
        self.selected_contexts_list = QComboBox()
        self.selected_contexts_list.setMinimumWidth(200)
        selected_layout.addWidget(self.selected_contexts_list)
        row1_layout.addLayout(selected_layout)
        
        # Boutons de gestion des contextes
        context_buttons_layout = QVBoxLayout()
        context_buttons_layout.addStretch()
        self.add_context_btn = QPushButton("➡ Ajouter")
        self.remove_context_btn = QPushButton("⬅ Retirer")
        context_buttons_layout.addWidget(self.add_context_btn)
        context_buttons_layout.addWidget(self.remove_context_btn)
        context_buttons_layout.addStretch()
        row1_layout.addLayout(context_buttons_layout)
        
        config_layout.addLayout(row1_layout)
        
        # Ligne 2: Prompt et configuration
        row2_layout = QHBoxLayout()
        
        # Prompt
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("Prompt de Base:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(100)
        self.prompt_edit.setPlaceholderText("Entrez votre prompt principal ici...")
        prompt_layout.addWidget(self.prompt_edit)
        row2_layout.addLayout(prompt_layout)
        
        # Paramètres de génération
        params_layout = QVBoxLayout()
        params_layout.addWidget(QLabel("Paramètres de Génération:"))
        
        # Plateforme IA
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QLabel("Plateforme:"))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["OpenAI GPT-4", "Claude", "LLaMA", "Custom"])
        platform_layout.addWidget(self.platform_combo)
        params_layout.addLayout(platform_layout)
        
        # Nombre de batches
        batches_layout = QHBoxLayout()
        batches_layout.addWidget(QLabel("Nombre de Batches:"))
        self.batches_spin = QSpinBox()
        self.batches_spin.setRange(1, 100)
        self.batches_spin.setValue(5)
        batches_layout.addWidget(self.batches_spin)
        params_layout.addLayout(batches_layout)
        
        # Format de sortie
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "XML", "Texte"])
        format_layout.addWidget(self.format_combo)
        params_layout.addLayout(format_layout)
        
        row2_layout.addLayout(params_layout)
        config_layout.addLayout(row2_layout)
        
        layout.addWidget(config_group)
        
        # Contrôles de génération
        controls_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("🚀 Générer")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.stop_btn = QPushButton("🛑 Arrêter")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.stop_btn.setEnabled(False)
        
        self.preview_btn = QPushButton("👁 Aperçu")
        self.preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        
        controls_layout.addWidget(self.generate_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.preview_btn)
        controls_layout.addStretch()
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        controls_layout.addWidget(self.progress_bar)
        
        layout.addLayout(controls_layout)
        
        # Zone des résultats
        self.results_tabs = QTabWidget()
        
        # Onglet Progression
        self.progress_tab = self.create_progress_tab()
        self.results_tabs.addTab(self.progress_tab, "📊 Progression")
        
        # Onglet Datasets
        self.datasets_tab = self.create_datasets_tab()
        self.results_tabs.addTab(self.datasets_tab, "💾 Datasets")
        
        # Onglet Aperçu
        self.preview_tab = self.create_preview_tab()
        self.results_tabs.addTab(self.preview_tab, "👁 Aperçu")
        
        layout.addWidget(self.results_tabs)
        
    def create_progress_tab(self):
        """Crée l'onglet de progression"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Statistiques en temps réel
        stats_group = QGroupBox("Statistiques de Génération")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Aucune génération en cours")
        self.stats_label.setStyleSheet("font-size: 12px; color: #666;")
        stats_layout.addWidget(self.stats_label)
        
        # Camembert des contextes (placeholder)
        chart_label = QLabel("📊 Diagramme d'utilisation des contextes")
        chart_label.setAlignment(Qt.AlignCenter)
        chart_label.setStyleSheet("""
            background-color: #f0f0f0;
            border: 1px dashed #ccc;
            padding: 40px;
            color: #666;
        """)
        stats_layout.addWidget(chart_label)
        
        layout.addWidget(stats_group)
        
        # Journal des opérations
        log_group = QGroupBox("Journal des Opérations")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return widget
        
    def create_datasets_tab(self):
        """Crée l'onglet des datasets générés"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Table des datasets
        self.datasets_table = QTableWidget()
        self.datasets_table.setColumnCount(5)
        self.datasets_table.setHorizontalHeaderLabels([
            "ID", "Nom", "Typologie", "Date", "Actions"
        ])
        self.datasets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.datasets_table)
        
        # Boutons de gestion des datasets
        dataset_buttons_layout = QHBoxLayout()
        
        self.export_all_btn = QPushButton("📤 Exporter Tout")
        self.export_selected_btn = QPushButton("📤 Exporter Sélection")
        self.delete_selected_btn = QPushButton("🗑 Supprimer Sélection")
        
        dataset_buttons_layout.addWidget(self.export_all_btn)
        dataset_buttons_layout.addWidget(self.export_selected_btn)
        dataset_buttons_layout.addWidget(self.delete_selected_btn)
        dataset_buttons_layout.addStretch()
        
        layout.addLayout(dataset_buttons_layout)
        
        return widget
        
    def create_preview_tab(self):
        """Crée l'onglet d'aperçu"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Aperçu du prompt enrichi
        prompt_group = QGroupBox("Aperçu du Prompt Enrichi")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.enriched_prompt_text = QTextEdit()
        self.enriched_prompt_text.setReadOnly(True)
        prompt_layout.addWidget(self.enriched_prompt_text)
        
        layout.addWidget(prompt_group)
        
        # Aperçu du dataset
        dataset_group = QGroupBox("Aperçu du Dataset")
        dataset_layout = QVBoxLayout(dataset_group)
        
        self.dataset_preview_text = QTextEdit()
        self.dataset_preview_text.setReadOnly(True)
        dataset_layout.addWidget(self.dataset_preview_text)
        
        layout.addWidget(dataset_group)
        
        return widget
        
    def setup_connections(self):
        """Configure les connexions des signaux"""
        # Connexions des boutons
        self.generate_btn.clicked.connect(self.start_generation)
        self.stop_btn.clicked.connect(self.stop_generation)
        self.preview_btn.clicked.connect(self.show_preview)
        self.add_context_btn.clicked.connect(self.add_context)
        self.remove_context_btn.clicked.connect(self.remove_context)
        
        # Connexions des datasets
        self.export_all_btn.clicked.connect(self.export_all_datasets)
        self.export_selected_btn.clicked.connect(self.export_selected_datasets)
        self.delete_selected_btn.clicked.connect(self.delete_selected_datasets)
        
        # Connexions des combobox
        self.typology_combo.currentIndexChanged.connect(self.on_typology_changed)
        
    def set_database(self, db_path):
        """Définit le chemin de la base de données"""
        self.db_path = db_path
        self.load_typologies()
        self.load_datasets()
        
    def set_conductor(self, conductor):
        """Définit le conducteur IA"""
        self.conductor = conductor
        self.update_platforms()
        
    def load_typologies(self):
        """Charge la liste des typologies"""
        if not self.db_path:
            return
            
        self.typology_combo.clear()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM context_typologies ORDER BY name")
            typologies = cursor.fetchall()
            conn.close()
            
            self.typology_combo.addItem("-- Sélectionnez une typologie --", None)
            for typology_id, name in typologies:
                self.typology_combo.addItem(name, typology_id)
                
        except Exception as e:
            print(f"Erreur lors du chargement des typologies: {str(e)}")
            
    def on_typology_changed(self):
        """Gère le changement de typologie"""
        typology_id = self.typology_combo.currentData()
        if typology_id:
            self.load_contexts_for_typology(typology_id)
            
    def load_contexts_for_typology(self, typology_id):
        """Charge les contextes pour une typologie donnée"""
        if not self.db_path:
            return
            
        self.contexts_list.clear()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, type FROM strategy_items 
                WHERE typology_id = ? 
                ORDER BY type, name
            ''', (typology_id,))
            contexts = cursor.fetchall()
            conn.close()
            
            for name, context_type in contexts:
                display_text = f"{name} ({context_type})"
                self.contexts_list.addItem(display_text, name)
                
        except Exception as e:
            print(f"Erreur lors du chargement des contextes: {str(e)}")
            
    def add_context(self):
        """Ajoute un contexte à la sélection"""
        current_index = self.contexts_list.currentIndex()
        if current_index >= 0:
            text = self.contexts_list.currentText()
            data = self.contexts_list.currentData()
            self.selected_contexts_list.addItem(text, data)
            self.contexts_list.removeItem(current_index)
            self.update_preview()
            
    def remove_context(self):
        """Retire un contexte de la sélection"""
        current_index = self.selected_contexts_list.currentIndex()
        if current_index >= 0:
            text = self.selected_contexts_list.currentText()
            data = self.selected_contexts_list.currentData()
            self.contexts_list.addItem(text, data)
            self.selected_contexts_list.removeItem(current_index)
            self.update_preview()
            
    def update_preview(self):
        """Met à jour l'aperçu du prompt enrichi"""
        base_prompt = self.prompt_edit.toPlainText()
        selected_contexts = []
        
        for i in range(self.selected_contexts_list.count()):
            context_data = self.selected_contexts_list.itemData(i)
            selected_contexts.append(context_data)
            
        # Construire le prompt enrichi
        enriched_prompt = base_prompt
        if selected_contexts:
            contexts_text = "\n".join([f"- {ctx}" for ctx in selected_contexts])
            enriched_prompt = f"{base_prompt}\n\nContextes appliqués:\n{contexts_text}"
            
        self.enriched_prompt_text.setPlainText(enriched_prompt)
        
    def show_preview(self):
        """Affiche l'aperçu de la génération"""
        self.update_preview()
        self.results_tabs.setCurrentIndex(2)  # Onglet Aperçu
        
    def start_generation(self):
        """Démarre la génération des datasets"""
        if not self.validate_configuration():
            return
            
        # Préparer la configuration
        config = {
            'prompt': self.prompt_edit.toPlainText(),
            'typology': self.typology_combo.currentText(),
            'selected_contexts': self.get_selected_contexts(),
            'platform': self.platform_combo.currentText(),
            'batches': self.batches_spin.value(),
            'format': self.format_combo.currentText()
        }
        
        # Démarrer le worker
        self.generation_worker = GenerationWorker(config, self.conductor)
        self.generation_worker.progress_updated.connect(self.update_progress)
        self.generation_worker.generation_completed.connect(self.generation_complete)
        self.generation_worker.generation_failed.connect(self.generation_failed)
        
        # Mettre à jour l'interface
        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.log_message("🚀 Démarrage de la génération...")
        self.generation_started.emit()
        
        self.generation_worker.start()
        
    def stop_generation(self):
        """Arrête la génération en cours"""
        if self.generation_worker:
            self.generation_worker.stop()
            self.generation_worker.wait()
            
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log_message("🛑 Génération arrêtée")
        self.generation_stopped.emit()
        
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
        self.stats_label.setText(f"Progression: {value}%")
        
    def generation_complete(self, results):
        """Gère la fin de la génération"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Sauvegarder les résultats
        self.current_datasets.extend(results['datasets'])
        self.save_datasets_to_db(results['datasets'])
        
        self.log_message("✅ Génération terminée avec succès!")
        self.update_datasets_table()
        self.results_tabs.setCurrentIndex(1)  # Onglet Datasets
        
        self.dataset_generated.emit(results)
        
    def generation_failed(self, error_message):
        """Gère l'échec de la génération"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self.log_message(f"❌ Erreur lors de la génération: {error_message}")
        QMessageBox.critical(self, "Erreur", f"La génération a échoué:\n{error_message}")
        
    def validate_configuration(self):
        """Valide la configuration avant génération"""
        if not self.prompt_edit.toPlainText().strip():
            QMessageBox.warning(self, "Validation", "Veuillez saisir un prompt de base")
            return False
            
        if self.selected_contexts_list.count() == 0:
            QMessageBox.warning(self, "Validation", "Veuillez sélectionner au moins un contexte")
            return False
            
        return True
        
    def get_selected_contexts(self):
        """Retourne la liste des contextes sélectionnés"""
        contexts = []
        for i in range(self.selected_contexts_list.count()):
            contexts.append(self.selected_contexts_list.itemData(i))
        return contexts
        
    def log_message(self, message):
        """Ajoute un message au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
    def save_datasets_to_db(self, datasets):
        """Sauvegarde les datasets dans la base de données"""
        if not self.db_path:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for dataset in datasets:
                cursor.execute('''
                    INSERT INTO generated_datasets 
                    (name, content, config, context_data, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    dataset['name'],
                    json.dumps(dataset['content']),
                    json.dumps(dataset.get('config', {})),
                    json.dumps(dataset.get('context', [])),
                    dataset['timestamp']
                ))
                
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des datasets: {str(e)}")
            
    def load_datasets(self):
        """Charge les datasets depuis la base de données"""
        if not self.db_path:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Créer la table si elle n'existe pas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS generated_datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    config TEXT,
                    context_data TEXT,
                    created_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                SELECT id, name, content, config, context_data, created_at 
                FROM generated_datasets 
                ORDER BY created_at DESC
            ''')
            datasets = cursor.fetchall()
            conn.close()
            
            self.current_datasets = []
            for dataset in datasets:
                self.current_datasets.append({
                    'id': dataset[0],
                    'name': dataset[1],
                    'content': json.loads(dataset[2]),
                    'config': json.loads(dataset[3]) if dataset[3] else {},
                    'context': json.loads(dataset[4]) if dataset[4] else [],
                    'timestamp': dataset[5]
                })
                
            self.update_datasets_table()
            
        except Exception as e:
            print(f"Erreur lors du chargement des datasets: {str(e)}")
            
    def update_datasets_table(self):
        """Met à jour la table des datasets"""
        self.datasets_table.setRowCount(len(self.current_datasets))
        
        for row, dataset in enumerate(self.current_datasets):
            self.datasets_table.setItem(row, 0, QTableWidgetItem(str(dataset['id'])))
            self.datasets_table.setItem(row, 1, QTableWidgetItem(dataset['name']))
            self.datasets_table.setItem(row, 2, QTableWidgetItem(dataset.get('typology', 'N/A')))
            self.datasets_table.setItem(row, 3, QTableWidgetItem(
                datetime.fromisoformat(dataset['timestamp']).strftime("%Y-%m-%d %H:%M")
            ))
            
            # Bouton d'action
            action_btn = QPushButton("📤 Exporter")
            action_btn.clicked.connect(lambda checked, d=dataset: self.export_dataset(d))
            self.datasets_table.setCellWidget(row, 4, action_btn)
            
    def export_dataset(self, dataset):
        """Exporte un dataset spécifique"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter le dataset",
            f"{dataset['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(dataset, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Succès", f"Dataset exporté vers {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")
                
    def export_all_datasets(self):
        """Exporte tous les datasets"""
        if not self.current_datasets:
            QMessageBox.information(self, "Information", "Aucun dataset à exporter")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter tous les datasets",
            f"datasets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.current_datasets, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Succès", f"Tous les datasets exportés vers {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")
                
    def export_selected_datasets(self):
        """Exporte les datasets sélectionnés"""
        selected_rows = set(index.row() for index in self.datasets_table.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "Information", "Aucun dataset sélectionné")
            return
            
        selected_datasets = [self.current_datasets[row] for row in selected_rows]
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter les datasets sélectionnés",
            f"datasets_selected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(selected_datasets, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Succès", f"Datasets sélectionnés exportés vers {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")
                
    def delete_selected_datasets(self):
        """Supprime les datasets sélectionnés"""
        selected_rows = set(index.row() for index in self.datasets_table.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "Information", "Aucun dataset sélectionné")
            return
            
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer {len(selected_rows)} dataset(s) ?"
        )
        
        if reply == QMessageBox.Yes:
            # Supprimer de la base de données
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for row in selected_rows:
                    dataset_id = self.current_datasets[row]['id']
                    cursor.execute("DELETE FROM generated_datasets WHERE id = ?", (dataset_id,))
                    
                conn.commit()
                conn.close()
                
                # Mettre à jour l'interface
                self.load_datasets()
                QMessageBox.information(self, "Succès", "Datasets supprimés avec succès")
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")
                
    def update_platforms(self):
        """Met à jour la liste des plateformes IA disponibles"""
        if self.conductor:
            platforms = self.conductor.get_available_platforms()
            self.platform_combo.clear()
            self.platform_combo.addItems(platforms)