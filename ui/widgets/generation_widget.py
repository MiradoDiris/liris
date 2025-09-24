# ui/widgets/generation_widget.py

import os
import json
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QTextEdit, QSpinBox, 
                             QPushButton, QProgressBar, QMessageBox,
                             QFileDialog, QCheckBox, QListWidget, QListWidgetItem,
                             QSplitter)

from core.data.database import Database
from utils.logger import logger

class GenerationWorker(QThread):
    """Thread pour la génération de dataset en arrière-plan"""
    
    progress_updated = pyqtSignal(int)
    batch_completed = pyqtSignal(int, str)
    generation_finished = pyqtSignal(bool, str)
    
    def __init__(self, conductor, platform, base_prompt, contexts, num_batches, output_format):
        super().__init__()
        self.conductor = conductor
        self.platform = platform
        self.base_prompt = base_prompt
        self.contexts = contexts
        self.num_batches = num_batches
        self.output_format = output_format
        self.is_running = True
        
    def run(self):
        """Exécute la génération du dataset"""
        try:
            results = []
            
            for i in range(self.num_batches):
                if not self.is_running:
                    break
                    
                # Mettre à jour la progression
                progress = int((i / self.num_batches) * 100)
                self.progress_updated.emit(progress)
                
                # Enrichir le prompt avec les contextes sélectionnés
                enriched_prompt = self._enrich_prompt()
                
                # Envoyer le prompt via l'API
                try:
                    response = self.conductor.send_prompt(
                        self.platform, 
                        enriched_prompt, 
                        mode="standard", 
                        sync=True, 
                        timeout=60
                    )
                    
                    if response and "result" in response and "response" in response["result"]:
                        result_text = response["result"]["response"]
                        results.append({
                            "batch": i + 1,
                            "prompt": enriched_prompt,
                            "response": result_text,
                            "timestamp": datetime.now().isoformat(),
                            "contexts": self.contexts
                        })
                        
                        self.batch_completed.emit(i + 1, f"Batch {i+1} terminé avec succès")
                    else:
                        self.batch_completed.emit(i + 1, f"Erreur dans le batch {i+1}")
                        
                except Exception as e:
                    logger.error(f"Erreur lors de la génération du batch {i+1}: {str(e)}")
                    self.batch_completed.emit(i + 1, f"Erreur dans le batch {i+1}: {str(e)}")
            
            # Sauvegarder les résultats
            if results:
                success, message = self._save_results(results)
                self.generation_finished.emit(success, message)
            else:
                self.generation_finished.emit(False, "Aucun résultat généré")
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération: {str(e)}")
            self.generation_finished.emit(False, f"Erreur: {str(e)}")
    
    def _enrich_prompt(self):
        """Enrichit le prompt de base avec les contextes sélectionnés"""
        enriched = self.base_prompt
        
        if self.contexts:
            contexts_text = "\n\nContexte(s) à considérer:\n"
            for context in self.contexts:
                contexts_text += f"- {context}\n"
            enriched += contexts_text
            
        return enriched
    
    def _save_results(self, results):
        """Sauvegarde les résultats dans le format sélectionné"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dataset_generation_{timestamp}"
            
            if self.output_format == "JSON":
                filename += ".json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
            elif self.output_format == "CSV":
                filename += ".csv"
                # Implémenter la conversion CSV si nécessaire
                pass
            elif self.output_format == "TXT":
                filename += ".txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    for result in results:
                        f.write(f"=== Batch {result['batch']} ===\n")
                        f.write(f"Prompt: {result['prompt']}\n")
                        f.write(f"Réponse: {result['response']}\n")
                        f.write(f"Timestamp: {result['timestamp']}\n")
                        f.write("="*50 + "\n\n")
            
            return True, f"Dataset sauvegardé sous: {filename}"
            
        except Exception as e:
            return False, f"Erreur lors de la sauvegarde: {str(e)}"
    
    def stop(self):
        """Arrête la génération"""
        self.is_running = False


class GenerationWidget(QWidget):
    """Widget de génération de dataset avec disposition divisée"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.database = None
        self.platforms = []
        self.generation_worker = None
        
        self._init_ui()
        self._init_connections()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur avec disposition divisée"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Créer un séparateur pour redimensionner les colonnes
        splitter = QSplitter(QtCore.Qt.Horizontal)
        
        # === PARTIE GAUCHE ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        # Section Typologies de contexte (en haut à gauche)
        context_group = QGroupBox("Typologies de contexte")
        context_layout = QVBoxLayout(context_group)
        
        # Liste des typologies disponibles
        self.context_list = QListWidget()
        self.context_list.setSelectionMode(QListWidget.MultiSelection)
        
        # Typologies prédéfinies
        predefined_contexts = [
            "Analyse de sentiment",
            "Classification de texte", 
            "Résumé automatique",
            "Traduction",
            "Génération de code",
            "Question-Réponse",
            "Reconnaissance d'entités",
            "Correction grammaticale",
            "Analyse syntaxique",
            "Détection de spam",
            "Génération créative",
            "Analyse de données",
            "Extraction d'information",
            "Synthèse de texte",
            "Évaluation de qualité"
        ]
        
        for context in predefined_contexts:
            item = QListWidgetItem(context)
            self.context_list.addItem(item)
        
        context_layout.addWidget(QLabel("Sélectionnez une ou plusieurs typologies:"))
        context_layout.addWidget(self.context_list)
        
        left_layout.addWidget(context_group)
        
        # Section Prompt de base (en bas à gauche)
        prompt_group = QGroupBox("Prompt de base")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Rédigez votre prompt de base ici...\n\nCe prompt sera automatiquement enrichi avec les contextes sélectionnés.")
        self.prompt_edit.setMinimumHeight(200)
        
        prompt_layout.addWidget(QLabel("Prompt de base (sera enrichi par les contextes sélectionnés):"))
        prompt_layout.addWidget(self.prompt_edit)
        
        left_layout.addWidget(prompt_group)
        
        # Ajuster les proportions de la partie gauche
        left_layout.setStretchFactor(context_group, 1)
        left_layout.setStretchFactor(prompt_group, 1)
        
        # === PARTIE DROITE ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        
        # Section Configuration de génération (en haut à droite)
        config_group = QGroupBox("Configuration de génération")
        config_layout = QVBoxLayout(config_group)
        
        # Plateforme IA
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QLabel("Plateforme d'IA:"))
        self.platform_combo = QComboBox()
        platform_layout.addWidget(self.platform_combo)
        platform_layout.addStretch()
        
        # Nombre de batches
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("Nombre de batches:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 100)
        self.batch_spin.setValue(5)
        self.batch_spin.setSuffix(" batches")
        batch_layout.addWidget(self.batch_spin)
        batch_layout.addStretch()
        
        # Format de sortie
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format de sortie:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "TXT"])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        
        config_layout.addLayout(platform_layout)
        config_layout.addLayout(batch_layout)
        config_layout.addLayout(format_layout)
        
        right_layout.addWidget(config_group)
        
        # Section Lots de génération (en bas à droite)
        generation_group = QGroupBox("Lots de génération")
        generation_layout = QVBoxLayout(generation_group)
        
        # Boutons de contrôle
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("🚀 Générer")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D; 
                color: white; 
                padding: 12px 25px;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #C24A3A;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
        """)
        
        self.stop_btn = QPushButton("⏹️ Arrêter")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #666; 
                color: white; 
                padding: 12px 25px;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #777;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
        """)
        self.stop_btn.setEnabled(False)
        
        self.export_btn = QPushButton("📤 Exporter")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D8A23; 
                color: white; 
                padding: 12px 25px;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3D9A33;
            }
        """)
        
        button_layout.addWidget(self.generate_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p% - Génération en cours...")
        
        # Logs de génération
        log_label = QLabel("Logs de génération:")
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(120)
        self.log_edit.setStyleSheet("background-color: #f5f5f5; font-family: 'Courier New'; font-size: 11px;")
        
        generation_layout.addLayout(button_layout)
        generation_layout.addWidget(self.progress_bar)
        generation_layout.addWidget(log_label)
        generation_layout.addWidget(self.log_edit)
        
        right_layout.addWidget(generation_group)
        
        # Ajuster les proportions de la partie droite
        right_layout.setStretchFactor(config_group, 1)
        right_layout.setStretchFactor(generation_group, 2)
        
        # Ajouter les widgets au séparateur
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Définir les proportions initiales (50%-50%)
        splitter.setSizes([400, 400])
        
        # Ajouter le séparateur au layout principal
        main_layout.addWidget(splitter)
    
    def _init_connections(self):
        """Initialise les connexions signal-slot"""
        self.generate_btn.clicked.connect(self._on_generate)
        self.stop_btn.clicked.connect(self._on_stop)
        self.export_btn.clicked.connect(self._on_export)
        
        # Connexion pour mettre à jour le statut en temps réel
        self.context_list.itemSelectionChanged.connect(self._update_selection_status)
    
    def _update_selection_status(self):
        """Met à jour le statut de sélection des typologies"""
        selected_count = len(self.context_list.selectedItems())
        self.context_list.setToolTip(f"{selected_count} typologie(s) sélectionnée(s)")
    
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
            logger.info("Gemini sélectionné par défaut")
        elif platforms:
            self.platform_combo.setCurrentIndex(0)
    
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
    
    def _on_generate(self):
        """Lance la génération du dataset"""
        if not self.conductor:
            QMessageBox.warning(self, "Erreur", "Conducteur non initialisé")
            return
        
        if not self.platforms:
            QMessageBox.warning(self, "Erreur", "Aucune plateforme disponible")
            return
        
        # Vérifier le prompt
        base_prompt = self.prompt_edit.toPlainText().strip()
        if not base_prompt:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir un prompt de base")
            return
        
        # Récupérer les contextes sélectionnés
        selected_contexts = [item.text() for item in self.context_list.selectedItems()]
        if not selected_contexts:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner au moins une typologie de contexte")
            return
        
        # Récupérer les paramètres
        platform = self.platform_combo.currentText()
        num_batches = self.batch_spin.value()
        output_format = self.format_combo.currentText()
        
        # Désactiver le bouton de génération
        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Effacer les logs précédents
        self.log_edit.clear()
        self._add_log("=== DÉBUT DE LA GÉNÉRATION ===")
        self._add_log(f"Plateforme: {platform}")
        self._add_log(f"Typologies: {', '.join(selected_contexts)}")
        self._add_log(f"Nombre de batches: {num_batches}")
        self._add_log("")
        
        # Lancer le worker de génération
        self.generation_worker = GenerationWorker(
            self.conductor, platform, base_prompt, selected_contexts, 
            num_batches, output_format
        )
        
        self.generation_worker.progress_updated.connect(self._on_progress_updated)
        self.generation_worker.batch_completed.connect(self._on_batch_completed)
        self.generation_worker.generation_finished.connect(self._on_generation_finished)
        
        self.generation_worker.start()
    
    def _on_stop(self):
        """Arrête la génération en cours"""
        if self.generation_worker and self.generation_worker.isRunning():
            self.generation_worker.stop()
            self.generation_worker.wait()
            self._add_log("=== GÉNÉRATION ARRÊTÉE PAR L'UTILISATEUR ===")
            
            # Réactiver le bouton de génération
            self.generate_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
    
    def _on_export(self):
        """Exporte le dataset généré"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le dataset", 
            f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "JSON Files (*.json);;CSV Files (*.csv);;Text Files (*.txt)", 
            options=options
        )
        
        if file_path:
            # Implémenter l'exportation selon le format
            QMessageBox.information(self, "Export", f"Dataset exporté vers: {file_path}")
            self._add_log(f"Dataset exporté: {file_path}")
    
    def _on_progress_updated(self, progress):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(progress)
    
    def _on_batch_completed(self, batch_num, message):
        """Ajoute un log lors de la completion d'un batch"""
        self._add_log(f"✅ Batch {batch_num}: {message}")
    
    def _on_generation_finished(self, success, message):
        """Gère la fin de la génération"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if success:
            self._add_log(f"🎉 {message}")
            self._add_log("=== GÉNÉRATION TERMINÉE AVEC SUCCÈS ===")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", message)
        else:
            self._add_log(f"❌ {message}")
            self._add_log("=== GÉNÉRATION ÉCHOUÉE ===")
            QMessageBox.warning(self, "Erreur", message)
        
        # Cacher la barre de progression après un délai
        QtCore.QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))
    
    def _add_log(self, message):
        """Ajoute un message aux logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_edit.append(f"[{timestamp}] {message}")
        # Auto-scroll vers le bas
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )
    
    def refresh(self):
        """Rafraîchit le widget"""
        if self.platform_combo.count() == 0 and self.platforms:
            self.set_platforms(self.platforms)
    
    def update_language(self):
        """Met à jour les textes selon la langue"""
        # Implémenter la traduction si nécessaire
        pass