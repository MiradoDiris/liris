#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/generation_widget.py - Widget pour la génération de contenu via ChatGPT
"""

import json
import sqlite3
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMessageBox

from ui.localization.translator import tr
from utils.logger import logger


class GenerationWorker(QThread):
    """Thread worker pour la génération asynchrone"""
    
    generation_completed = pyqtSignal(dict)
    generation_failed = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, conductor, platform, context, prompt):
        super().__init__()
        self.conductor = conductor
        self.platform = platform
        self.context = context
        self.prompt = prompt
        self.is_cancelled = False
    
    def run(self):
        try:
            self.progress_updated.emit(10)
            
            # Construire le prompt complet avec contexte
            full_prompt = f"Contexte: {self.context}\n\nDemande: {self.prompt}"
            
            self.progress_updated.emit(30)
            
            # Envoyer vers ChatGPT
            result = self.conductor.send_prompt(
                self.platform,
                full_prompt,
                mode="standard",
                sync=True,
                timeout=120
            )
            
            self.progress_updated.emit(80)
            
            if self.is_cancelled:
                return
                
            self.progress_updated.emit(100)
            self.generation_completed.emit(result)
            
        except Exception as e:
            logger.error(f"Erreur dans GenerationWorker: {str(e)}")
            self.generation_failed.emit(str(e))
    
    def cancel(self):
        self.is_cancelled = True


class GenerationWidget(QWidget):
    """Widget pour la génération de contenu avec ChatGPT"""
    
    # Signaux
    generation_started = pyqtSignal(str)
    generation_completed = pyqtSignal(str)
    generation_failed = pyqtSignal(str, str)
    dataset_created = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.platforms = []
        self.database = None
        self.current_worker = None

        # Nouveau : paramètres de sortie
        self.selected_template = "JSON"
        self.num_batches = 1
        
        # Couleurs du thème (même style que prompt_list.py)
        self.primary_color = "#A23B2D"  # Rouge brique
        self.secondary_color = "#D35A4A"  # Rouge brique clair
        self.background_color = "#F5F0EF"  # Beige clair
        self.text_color = "#333333"  # Gris foncé
        self.accent_color = "#E38272"  # Rose pâle
        
        self._init_style()
        self._init_ui()
        self._init_connections()
    
    def _init_style(self):
        """Configure le style global du widget (cohérent avec prompt_list.py)"""
        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: bold;
            min-width: 120px;
        }}

        QPushButton:hover {{
            background-color: {self.secondary_color};
        }}

        QPushButton:pressed {{
            background-color: #922E23;
        }}

        QPushButton:disabled {{
            background-color: #CCCCCC;
            color: #666666;
        }}

        QComboBox {{
            padding: 8px;
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            background-color: white;
            min-width: 120px;
        }}

        QComboBox:hover {{
            border: 2px solid {self.primary_color};
        }}

        QComboBox::drop-down {{
            border: none;
        }}

        QTextEdit {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            padding: 8px;
            background-color: white;
        }}

        QTextEdit:focus {{
            border: 2px solid {self.primary_color};
        }}

        QGroupBox {{
            font-weight: bold;
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: transparent;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {self.primary_color};
        }}

        QProgressBar {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            text-align: center;
            background-color: white;
        }}

        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 4px;
        }}

        QLabel {{
            color: {self.text_color};
        }}
        """
        self.setStyleSheet(stylesheet)
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Titre
        title_label = QtWidgets.QLabel("Génération de contenu")
        title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {self.primary_color};
            margin: 10px 0;
        """)
        layout.addWidget(title_label)
        
        # Configuration
        config_group = QtWidgets.QGroupBox("Configuration de la génération")
        config_layout = QVBoxLayout(config_group)
        
        # Sélection de plateforme
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QtWidgets.QLabel("Plateforme IA:"))
        
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setMinimumWidth(200)
        platform_layout.addWidget(self.platform_combo)
        platform_layout.addStretch()
        config_layout.addLayout(platform_layout)
        
        # Sélection du type de contexte avec boutons
        context_layout = QVBoxLayout()
        context_layout.addWidget(QtWidgets.QLabel("Type de contexte:"))
        
        # Boutons de typologies de contexte
        context_buttons_layout = QHBoxLayout()
        
        self.context_buttons = {
            "Créatif": "Contexte créatif pour la génération d'idées innovantes, de solutions originales et de contenu artistique. Favorise la pensée divergente et l'exploration de nouvelles possibilités.",
            "Analytique": "Contexte analytique pour l'analyse approfondie, la résolution de problèmes complexes et l'évaluation critique. Met l'accent sur la logique et la méthode.",
            "Technique": "Contexte technique pour les aspects spécialisés, les détails d'implémentation et les solutions pratiques. Orienté vers la précision et l'expertise.",
            "Commercial": "Contexte commercial pour les stratégies business, l'analyse de marché et les recommandations commerciales. Axé sur la valeur et les résultats.",
            "Éducatif": "Contexte éducatif pour l'apprentissage, la pédagogie et la transmission de connaissances. Privilégie la clarté et la progression."
        }
        
        for context_type, description in self.context_buttons.items():
            btn = QtWidgets.QPushButton(context_type)
            btn.setToolTip(description)
            # Bouton avec style cohérent (pas de style inline)
            context_buttons_layout.addWidget(btn)
        
        context_layout.addLayout(context_buttons_layout)
        
        # Zone de texte pour le contexte
        self.context_text = QtWidgets.QTextEdit()
        self.context_text.setPlaceholderText("Décrivez le contexte de génération ou utilisez les boutons ci-dessus...")
        self.context_text.setMaximumHeight(120)
        context_layout.addWidget(self.context_text)
        
        config_layout.addLayout(context_layout)
        layout.addWidget(config_group)
        
        # Prompt de génération
        prompt_group = QtWidgets.QGroupBox("Prompt de génération")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.prompt_text = QtWidgets.QTextEdit()
        self.prompt_text.setPlaceholderText("Entrez votre demande de génération ici...")
        self.prompt_text.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_text)
        
        layout.addWidget(prompt_group)

        output_group = QtWidgets.QGroupBox("Configuration de la sortie")
        output_layout = QVBoxLayout(output_group)
        
         # Template de dataset
        template_layout = QHBoxLayout()
        template_layout.addWidget(QtWidgets.QLabel("Template de dataset :"))
        self.template_combo = QtWidgets.QComboBox()
        self.template_combo.addItems(["JSON", "CSV", "Texte brut"])
        self.template_combo.setCurrentText("JSON")
        template_layout.addWidget(self.template_combo)
        template_layout.addStretch()
        output_layout.addLayout(template_layout)

        # Exemple / aperçu
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QtWidgets.QLabel("Aperçu du jeu de données :"))
        self.preview_btn = QtWidgets.QPushButton("Générer un aperçu")
        preview_layout.addWidget(self.preview_btn)
        preview_layout.addStretch()
        output_layout.addLayout(preview_layout)

        # Nombre de lots
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QtWidgets.QLabel("Nombre de lots :"))
        self.batch_spin = QtWidgets.QSpinBox()
        self.batch_spin.setMinimum(1)
        self.batch_spin.setMaximum(100)
        self.batch_spin.setValue(1)
        batch_layout.addWidget(self.batch_spin)
        batch_layout.addStretch()
        output_layout.addLayout(batch_layout)

        layout.addWidget(output_group)

        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.generate_btn = QtWidgets.QPushButton("Générer le contenu")
        # Style géré par le CSS global
        action_layout.addWidget(self.generate_btn)
        
        self.cancel_btn = QtWidgets.QPushButton("Annuler")
        self.cancel_btn.setEnabled(False)
        # Style géré par le CSS global
        action_layout.addWidget(self.cancel_btn)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)
        
        # Barre de progression
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Résultats
        results_group = QtWidgets.QGroupBox("Résultats générés")
        results_layout = QVBoxLayout(results_group)
        
        # Informations sur la génération
        info_layout = QHBoxLayout()
        self.info_label = QtWidgets.QLabel("Aucune génération en cours")
        self.info_label.setStyleSheet(f"color: {self.text_color}; font-style: italic;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        results_layout.addLayout(info_layout)
        
        # Zone des résultats
        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setPlaceholderText("Les résultats de génération apparaîtront ici...")
        self.results_text.setReadOnly(True)
        results_layout.addWidget(self.results_text)
        
        # Boutons pour les résultats
        results_actions_layout = QHBoxLayout()
        
        self.save_dataset_btn = QtWidgets.QPushButton("Sauvegarder comme Dataset")
        self.save_dataset_btn.setEnabled(False)
        # Style géré par le CSS global
        results_actions_layout.addWidget(self.save_dataset_btn)
        
        self.copy_btn = QtWidgets.QPushButton("Copier")
        self.copy_btn.setEnabled(False)
        results_actions_layout.addWidget(self.copy_btn)
        
        self.clear_btn = QtWidgets.QPushButton("Effacer")
        self.clear_btn.setEnabled(False)
        results_actions_layout.addWidget(self.clear_btn)
        
        results_actions_layout.addStretch()
        results_layout.addLayout(results_actions_layout)
        
        layout.addWidget(results_group)
        layout.addStretch()
    
    def _init_connections(self):
        """Initialise les connexions signal-slot"""
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.save_dataset_btn.clicked.connect(self._on_save_dataset)
        self.copy_btn.clicked.connect(self._on_copy_results)
        self.clear_btn.clicked.connect(self._on_clear_results)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
    
    def _set_context_template(self, template):
        """Définit le template de contexte sélectionné"""
        self.context_text.setPlainText(template)
    
    def set_conductor(self, conductor):
        """Définit le conducteur d'IA"""
        self.conductor = conductor
        
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
    
    def set_platforms(self, platforms):
        """Met à jour la liste des plateformes disponibles"""
        self.platforms = platforms
        self.platform_combo.clear()
        
        if platforms:
            for platform in platforms:
                self.platform_combo.addItem(platform)
            self.generate_btn.setEnabled(True)
        else:
            self.platform_combo.addItem("Aucune plateforme disponible")
            self.generate_btn.setEnabled(False)
    
    def _on_generate_clicked(self):
        """Lance la génération"""
        if not self.conductor:
            QMessageBox.warning(self, "Erreur", "Système non initialisé")
            return
        
        context = self.context_text.toPlainText().strip()
        prompt = self.prompt_text.toPlainText().strip()
        platform = self.platform_combo.currentText()
        
        if not context:
            QMessageBox.warning(self, "Erreur", "Veuillez définir un contexte")
            return
        
        if not prompt:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un prompt")
            return
        
        # Récupérer config sortie
        self.selected_template = self.template_combo.currentText()
        self.num_batches = self.batch_spin.value()
        
        # Démarrer la génération
        self._start_generation(platform, context, prompt)
    
    def _start_generation(self, platform, context, prompt):
        """Démarre la génération dans un thread séparé"""
        # Interface en mode génération
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Informations
        self.info_label.setText(f"Génération en cours sur {platform}...")
        self.info_label.setStyleSheet(f"color: {self.primary_color}; font-weight: bold;")
        
        # Créer et démarrer le worker
        self.current_worker = GenerationWorker(self.conductor, platform, context, prompt)
        self.current_worker.generation_completed.connect(self._on_generation_completed)
        self.current_worker.generation_failed.connect(self._on_generation_failed)
        self.current_worker.progress_updated.connect(self._on_progress_updated)
        self.current_worker.start()
        
        # Émettre le signal de début
        self.generation_started.emit(platform)

    def _on_preview_clicked(self):
        """Génère un aperçu de dataset (1 lot)"""
        context = self.context_text.toPlainText().strip()
        prompt = self.prompt_text.toPlainText().strip()
        if not context or not prompt:
            QMessageBox.warning(self, "Erreur", "Veuillez remplir le contexte et le prompt avant l’aperçu")
            return

        # Pour l’aperçu : simuler une mini-génération
        sample_text = f"[APERÇU] Template: {self.template_combo.currentText()} • 1 lot\nContexte: {context[:50]}...\nPrompt: {prompt[:50]}..."
        self.results_text.setPlainText(sample_text)
        self.info_label.setText("Aperçu généré")
        self.info_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.copy_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
    
    def _on_progress_updated(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
    
    def _on_generation_completed(self, result):
        """Traite la fin de génération"""
        # Interface normale
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Extraire la réponse
        if result and 'result' in result and 'response' in result['result']:
            response = result['result']['response']
            
            # Afficher les résultats
            self.results_text.setPlainText(response)
            
            # Activer les boutons de résultats
            self.save_dataset_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            
            # Informations
            platform = self.platform_combo.currentText()
            duration = result.get('duration', 0)
            tokens = result.get('token_count', 0)
            
            self.info_label.setText(f"Génération terminée • {platform} • {duration:.1f}s • {tokens} tokens")
            self.info_label.setStyleSheet(f"color: #4CAF50; font-weight: bold;")
            
            # Sauvegarder automatiquement dans la base
            if self.database:
                self._save_generation_to_db(result)
            
            # Émettre le signal de fin
            self.generation_completed.emit(platform)
            
        else:
            error_msg = result.get('error', 'Réponse invalide') if result else 'Aucun résultat'
            self._on_generation_failed(error_msg)
    
    def _on_generation_failed(self, error):
        """Traite l'échec de génération"""
        # Interface normale
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Afficher l'erreur
        self.info_label.setText(f"Erreur de génération: {error}")
        self.info_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        # Message d'erreur
        QMessageBox.critical(self, "Erreur de génération", f"La génération a échoué:\n\n{error}")
        
        # Émettre le signal d'échec
        platform = self.platform_combo.currentText()
        self.generation_failed.emit(platform, error)
    
    def _on_cancel_clicked(self):
        """Annule la génération en cours"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(3000)  # Attendre max 3 secondes
            
        # Remettre l'interface normale
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self.info_label.setText("Génération annulée")
        self.info_label.setStyleSheet("color: #FF9800; font-weight: bold;")
    
    def _save_generation_to_db(self, result):
        """Sauvegarde la génération dans la base de données"""
        if not self.database:
            return
        
        try:
            context = self.context_text.toPlainText()
            prompt = self.prompt_text.toPlainText()
            platform = self.platform_combo.currentText()
            response = result['result']['response']
            
            # Données à sauvegarder
            generation_data = {
                'timestamp': datetime.now().isoformat(),
                'platform': platform,
                'context': context,
                'prompt': prompt,
                'response': response,
                'duration': result.get('duration', 0),
                'token_count': result.get('token_count', 0)
            }
            
            # Insérer dans la base (adapter selon votre schéma)
            cursor = self.database.connection.cursor()
            cursor.execute("""
                INSERT INTO generations (timestamp, platform, context, prompt, response, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                generation_data['timestamp'],
                generation_data['platform'],
                generation_data['context'],
                generation_data['prompt'],
                generation_data['response'],
                json.dumps({
                    'duration': generation_data['duration'],
                    'token_count': generation_data['token_count']
                })
            ))
            
            self.database.connection.commit()
            logger.info("Génération sauvegardée dans la base de données")
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde en base: {str(e)}")
    
    def _on_save_dataset(self):
        """Sauvegarde les résultats comme dataset"""
        if not self.database:
            QMessageBox.warning(self, "Erreur", "Base de données non disponible")
            return
        
        response = self.results_text.toPlainText()
        if not response:
            return
        
        # Demander le nom du dataset
        name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "Nouveau Dataset", 
            "Nom du dataset:",
            text=f"Generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        if not ok or not name:
            return
        
        try:
            # Créer le dataset
            cursor = self.database.connection.cursor()
            cursor.execute("""
                INSERT INTO datasets (name, description, data, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                f"Dataset généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                json.dumps({
                    'context': self.context_text.toPlainText(),
                    'prompt': self.prompt_text.toPlainText(),
                    'response': response,
                    'platform': self.platform_combo.currentText()
                }),
                datetime.now().isoformat()
            ))
            
            dataset_id = cursor.lastrowid
            self.database.connection.commit()
            
            QMessageBox.information(self, "Succès", f"Dataset '{name}' créé avec succès")
            
            # Émettre le signal
            self.dataset_created.emit(dataset_id)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du dataset: {str(e)}")
            QMessageBox.critical(self, "Erreur", f"Impossible de créer le dataset:\n\n{str(e)}")
    
    def _on_copy_results(self):
        """Copie les résultats dans le presse-papier"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.results_text.toPlainText())
        
        self.info_label.setText("Résultats copiés dans le presse-papier")
        self.info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
    
    def _on_clear_results(self):
        """Efface les résultats"""
        self.results_text.clear()
        self.save_dataset_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        self.info_label.setText("Résultats effacés")
        self.info_label.setStyleSheet(f"color: {self.text_color}; font-style: italic;")
    
    def update_language(self):
        """Met à jour les textes selon la langue sélectionnée"""
        # À implémenter selon votre système de traduction
        pass
    
    def refresh(self):
        """Actualise le widget"""
        # Actualiser la liste des plateformes si nécessaire
        if self.conductor:
            platforms = self.conductor.get_available_platforms()
            self.set_platforms(platforms)