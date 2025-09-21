from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QComboBox, QSpinBox, 
                             QProgressBar, QGroupBox, QSplitter, QListWidget,
                             QMessageBox, QFileDialog, QCheckBox, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
import json
import sqlite3
from datetime import datetime


class GenerationWorker(QThread):
    """Worker thread pour la génération de datasets"""
    
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    dataset_generated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, conductor, context_data, prompt, config):
        super().__init__()
        self.conductor = conductor
        self.context_data = context_data
        self.prompt = prompt
        self.config = config
        self.is_running = False
        
    def run(self):
        """Exécute la génération de datasets"""
        self.is_running = True
        try:
            total_batches = self.config.get('batch_count', 1)
            
            for batch_num in range(total_batches):
                if not self.is_running:
                    break
                    
                self.status_updated.emit(f"Génération du lot {batch_num + 1}/{total_batches}")
                
                # Préparer le prompt avec le contexte
                full_prompt = self._prepare_prompt()
                
                # Appel à ChatGPT via le conductor
                response = self._call_chatgpt(full_prompt)
                
                # Traitement de la réponse
                dataset = self._process_response(response, batch_num)
                
                self.dataset_generated.emit(dataset)
                
                # Mise à jour du progrès
                progress = int((batch_num + 1) / total_batches * 100)
                self.progress_updated.emit(progress)
                
            self.status_updated.emit("Génération terminée avec succès")
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def _prepare_prompt(self):
        """Prépare le prompt avec le contexte sélectionné"""
        # Construire une représentation structurée du contexte
        context_info = []
        
        # Informations de base du contexte
        if 'name' in self.context_data:
            context_info.append(f"Nom du contexte: {self.context_data['name']}")
        if 'type' in self.context_data:
            context_info.append(f"Type: {self.context_data['type']}")
        if 'description' in self.context_data and self.context_data['description']:
            context_info.append(f"Description: {self.context_data['description']}")
        
        # Hiérarchie du contexte
        if 'hierarchy' in self.context_data and self.context_data['hierarchy']:
            hierarchy_str = " > ".join([f"{level['type']}: {level['name']}" for level in self.context_data['hierarchy']])
            context_info.append(f"Hiérarchie: {hierarchy_str}")
        
        # Propriétés spécifiques
        if 'properties' in self.context_data and self.context_data['properties']:
            context_info.append(f"Propriétés spécifiques: {json.dumps(self.context_data['properties'], ensure_ascii=False)}")
        
        context_str = "\n".join(context_info)
        
        # Configuration détaillée
        config_details = []
        config_details.append(f"Format de sortie: {self.config.get('output_format', 'JSON')}")
        config_details.append(f"Type de dataset: {self.config.get('dataset_type', 'Standard')}")
        config_details.append(f"Nombre d'exemples à générer: {self.config.get('examples_per_batch', 10)}")
        
        if self.config.get('output_format') == 'JSON':
            config_details.append("Structure JSON attendue: Utilisez des clés descriptives et une structure cohérente")
        elif self.config.get('output_format') == 'CSV':
            config_details.append("Format CSV: Incluez les en-têtes de colonnes et séparez les valeurs par des virgules")
        
        config_str = "\n".join(config_details)
        
        full_prompt = f"""
CONTEXTE DE GÉNÉRATION:
{context_str}

INSTRUCTIONS UTILISATEUR:
{self.prompt}

CONFIGURATION TECHNIQUE:
{config_str}

CONSIGNES IMPORTANTES:
1. Respectez strictement le format de sortie demandé ({self.config.get('output_format', 'JSON')})
2. Générez exactement {self.config.get('examples_per_batch', 10)} exemples
3. Assurez-vous que chaque exemple est cohérent avec le contexte fourni
4. Variez les exemples pour couvrir différents aspects du contexte
5. Maintenez une qualité élevée et une pertinence maximale

Générez maintenant le dataset selon ces spécifications.
"""
        return full_prompt
        
    def _call_chatgpt(self, prompt):
        """Appelle ChatGPT via le conductor"""
        if self.conductor:
            return self.conductor.generate_response(prompt)
        else:
            # Simulation pour les tests
            return {
                "content": "Dataset simulé généré avec succès",
                "usage": {"tokens": 150}
            }
            
    def _process_response(self, response, batch_num):
        """Traite la réponse de ChatGPT"""
        return {
            "batch_id": batch_num,
            "content": response.get("content", ""),
            "usage": response.get("usage", {}),
            "timestamp": datetime.now().isoformat(),
            "config": self.config
        }
        
    def stop(self):
        """Arrête la génération"""
        self.is_running = False


class GenerationWidget(QWidget):
    """
    Widget pour l'onglet Génération - Génération de datasets avec ChatGPT
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_path = None
        self.conductor = None
        self.generation_worker = None
        self.generated_datasets = []
        
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Génération de Datasets avec IA")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Partie gauche - Configuration
        left_widget = self._create_config_section()
        main_splitter.addWidget(left_widget)
        
        # Partie droite - Résultats et suivi
        right_widget = self._create_results_section()
        main_splitter.addWidget(right_widget)
        
        # Définir les proportions
        main_splitter.setSizes([500, 700])
        
        # Barre de contrôle en bas
        control_layout = self._create_control_bar()
        layout.addLayout(control_layout)
        
    def _create_config_section(self):
        """Crée la section de configuration"""
        widget = QGroupBox("Configuration de Génération")
        layout = QVBoxLayout(widget)
        
        # Sélection du contexte
        context_group = QGroupBox("Contexte de Stratégie")
        context_layout = QVBoxLayout(context_group)
        
        self.context_list = QListWidget()
        self.context_list.setMaximumHeight(150)
        context_layout.addWidget(QLabel("Contextes disponibles:"))
        context_layout.addWidget(self.context_list)
        
        refresh_context_btn = QPushButton("Actualiser les contextes")
        refresh_context_btn.clicked.connect(self.load_available_contexts)
        context_layout.addWidget(refresh_context_btn)
        
        layout.addWidget(context_group)
        
        # Prompt de génération
        prompt_group = QGroupBox("Instructions de Génération")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Entrez vos instructions pour ChatGPT...\n\n"
            "Exemple:\n"
            "Générez un dataset de 10 exemples de conversations client-service "
            "en utilisant le contexte fourni. Chaque exemple doit contenir "
            "une question client et une réponse appropriée."
        )
        self.prompt_edit.setMaximumHeight(120)
        prompt_layout.addWidget(self.prompt_edit)
        
        layout.addWidget(prompt_group)
        
        # Configuration de sortie
        output_group = QGroupBox("Configuration de Sortie")
        output_layout = QVBoxLayout(output_group)
        
        # Format de sortie
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "XML", "Texte libre"])
        format_layout.addWidget(self.format_combo)
        output_layout.addLayout(format_layout)
        
        # Type de dataset
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Standard", "Conversationnel", "Q&A", "Classification", "Personnalisé"])
        type_layout.addWidget(self.type_combo)
        output_layout.addLayout(type_layout)
        
        # Nombre d'exemples par lot
        examples_layout = QHBoxLayout()
        examples_layout.addWidget(QLabel("Exemples par lot:"))
        self.examples_spin = QSpinBox()
        self.examples_spin.setRange(1, 100)
        self.examples_spin.setValue(10)
        examples_layout.addWidget(self.examples_spin)
        output_layout.addLayout(examples_layout)
        
        # Nombre de lots
        batches_layout = QHBoxLayout()
        batches_layout.addWidget(QLabel("Nombre de lots:"))
        self.batches_spin = QSpinBox()
        self.batches_spin.setRange(1, 50)
        self.batches_spin.setValue(1)
        batches_layout.addWidget(self.batches_spin)
        output_layout.addLayout(batches_layout)
        
        # Options avancées
        self.preview_checkbox = QCheckBox("Générer un aperçu d'abord")
        self.save_intermediate_checkbox = QCheckBox("Sauvegarder les résultats intermédiaires")
        output_layout.addWidget(self.preview_checkbox)
        output_layout.addWidget(self.save_intermediate_checkbox)
        
        layout.addWidget(output_group)
        
        return widget
        
    def _create_results_section(self):
        """Crée la section des résultats"""
        widget = QGroupBox("Résultats et Suivi")
        layout = QVBoxLayout(widget)
        
        # Onglets pour les résultats
        self.results_tabs = QTabWidget()
        
        # Onglet Progression
        progress_widget = self._create_progress_tab()
        self.results_tabs.addTab(progress_widget, "Progression")
        
        # Onglet Datasets générés
        datasets_widget = self._create_datasets_tab()
        self.results_tabs.addTab(datasets_widget, "Datasets")
        
        # Onglet Aperçu
        preview_widget = self._create_preview_tab()
        self.results_tabs.addTab(preview_widget, "Aperçu")
        
        layout.addWidget(self.results_tabs)
        
        return widget
        
    def _create_progress_tab(self):
        """Crée l'onglet de progression"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(QLabel("Progression globale:"))
        layout.addWidget(self.progress_bar)
        
        # Statut actuel
        layout.addWidget(QLabel("Statut:"))
        self.status_label = QLabel("Prêt à générer")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        layout.addWidget(self.status_label)
        
        # Log des opérations
        layout.addWidget(QLabel("Journal des opérations:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
        
        layout.addStretch()
        return widget
        
    def _create_datasets_tab(self):
        """Crée l'onglet des datasets"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Liste des datasets générés
        layout.addWidget(QLabel("Datasets générés:"))
        self.datasets_list = QListWidget()
        layout.addWidget(self.datasets_list)
        
        # Boutons de gestion
        buttons_layout = QHBoxLayout()
        self.view_dataset_btn = QPushButton("Voir le contenu")
        self.export_dataset_btn = QPushButton("Exporter")
        self.delete_dataset_btn = QPushButton("Supprimer")
        
        buttons_layout.addWidget(self.view_dataset_btn)
        buttons_layout.addWidget(self.export_dataset_btn)
        buttons_layout.addWidget(self.delete_dataset_btn)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        return widget
        
    def _create_preview_tab(self):
        """Crée l'onglet d'aperçu"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Aperçu du dataset:"))
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)
        
        # Boutons d'aperçu
        preview_buttons = QHBoxLayout()
        self.generate_preview_btn = QPushButton("Générer un aperçu")
        self.approve_preview_btn = QPushButton("Approuver et continuer")
        
        preview_buttons.addWidget(self.generate_preview_btn)
        preview_buttons.addWidget(self.approve_preview_btn)
        preview_buttons.addStretch()
        
        layout.addLayout(preview_buttons)
        
        return widget
        
    def _create_control_bar(self):
        """Crée la barre de contrôle"""
        layout = QHBoxLayout()
        
        self.start_generation_btn = QPushButton("Démarrer la Génération")
        self.start_generation_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.stop_generation_btn = QPushButton("Arrêter")
        self.stop_generation_btn.setEnabled(False)
        self.stop_generation_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        self.save_all_btn = QPushButton("Sauvegarder Tout")
        self.clear_results_btn = QPushButton("Effacer les Résultats")
        
        layout.addWidget(self.start_generation_btn)
        layout.addWidget(self.stop_generation_btn)
        layout.addWidget(self.save_all_btn)
        layout.addWidget(self.clear_results_btn)
        layout.addStretch()
        
        return layout
        
    def setup_connections(self):
        """Configure les connexions des signaux"""
        # Boutons principaux
        self.start_generation_btn.clicked.connect(self.start_generation)
        self.stop_generation_btn.clicked.connect(self.stop_generation)
        self.save_all_btn.clicked.connect(self.save_all_datasets)
        self.clear_results_btn.clicked.connect(self.clear_results)
        
        # Boutons des datasets
        self.view_dataset_btn.clicked.connect(self.view_selected_dataset)
        self.export_dataset_btn.clicked.connect(self.export_selected_dataset)
        self.delete_dataset_btn.clicked.connect(self.delete_selected_dataset)
        
        # Boutons d'aperçu
        self.generate_preview_btn.clicked.connect(self.generate_preview)
        self.approve_preview_btn.clicked.connect(self.approve_and_continue)
        
        # Sélection dans les listes
        self.datasets_list.itemSelectionChanged.connect(self.on_dataset_selected)
        
    def set_database(self, db_path):
        """Définit le chemin de la base de données"""
        self.db_path = db_path
        self.init_database()
        self.load_available_contexts()
        
    def set_conductor(self, conductor):
        """Définit le conductor pour les appels à l'IA"""
        self.conductor = conductor
        
    def init_database(self):
        """Initialise les tables de la base de données"""
        if not self.db_path:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table pour les datasets générés
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generated_datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                config TEXT,
                context_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def load_available_contexts(self):
        """Charge les contextes disponibles depuis la stratégie avec organisation améliorée"""
        self.context_list.clear()
        
        if not self.db_path:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Récupérer tous les éléments avec leur hiérarchie
            cursor.execute("""
                SELECT s1.id, s1.name, s1.type, s1.description,
                       s2.name as parent_name, s2.type as parent_type
                FROM strategy_items s1
                LEFT JOIN strategy_items s2 ON s1.parent_id = s2.id
                ORDER BY s1.type, s1.name
            """)
            
            items = cursor.fetchall()
            conn.close()
            
            # Grouper par type pour une meilleure organisation
            grouped_items = {}
            for item in items:
                item_id, name, item_type, description, parent_name, parent_type = item
                
                if item_type not in grouped_items:
                    grouped_items[item_type] = []
                
                display_text = f"[{item_type}] {name}"
                if parent_name:
                    display_text += f" (sous {parent_name})"
                if description:
                    display_text += f" - {description[:50]}..."
                
                grouped_items[item_type].append({
                    "id": item_id,
                    "display": display_text,
                    "name": name,
                    "type": item_type
                })
            
            # Ajouter les éléments groupés à la liste
            for item_type in ["Cluster", "Racine", "Parent", "Enfant"]:
                if item_type in grouped_items:
                    for item in grouped_items[item_type]:
                        self.context_list.addItem(item["display"])
                        
        except Exception as e:
            self.log_message(f"Erreur lors du chargement des contextes: {str(e)}")
            
    def start_generation(self):
        """Démarre la génération de datasets"""
        # Validation des entrées
        if not self.prompt_edit.toPlainText().strip():
            QMessageBox.warning(self, "Erreur", "Veuillez entrer des instructions de génération")
            return
            
        if self.context_list.currentRow() == -1:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un contexte")
            return
            
        # Préparer la configuration
        config = {
            'output_format': self.format_combo.currentText(),
            'dataset_type': self.type_combo.currentText(),
            'examples_per_batch': self.examples_spin.value(),
            'batch_count': self.batches_spin.value(),
            'generate_preview': self.preview_checkbox.isChecked(),
            'save_intermediate': self.save_intermediate_checkbox.isChecked()
        }
        
        # Récupérer le contexte sélectionné
        context_data = self._get_selected_context_data()
        
        # Créer et démarrer le worker
        self.generation_worker = GenerationWorker(
            self.conductor,
            context_data,
            self.prompt_edit.toPlainText(),
            config
        )
        
        # Connecter les signaux
        self.generation_worker.progress_updated.connect(self.update_progress)
        self.generation_worker.status_updated.connect(self.update_status)
        self.generation_worker.dataset_generated.connect(self.on_dataset_generated)
        self.generation_worker.error_occurred.connect(self.on_generation_error)
        
        # Démarrer la génération
        self.generation_worker.start()
        
        # Mettre à jour l'interface
        self.start_generation_btn.setEnabled(False)
        self.stop_generation_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_message("Génération démarrée...")
        
    def stop_generation(self):
        """Arrête la génération en cours"""
        if self.generation_worker:
            self.generation_worker.stop()
            self.generation_worker.wait()
            
        self.start_generation_btn.setEnabled(True)
        self.stop_generation_btn.setEnabled(False)
        self.log_message("Génération arrêtée par l'utilisateur")
        
    def _get_selected_context_data(self):
        """Récupère les données du contexte sélectionné"""
        if not self.context_list.currentItem() or not self.db_path:
            return {
                "selected_context": "",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            # Extraire le nom du contexte depuis le texte affiché
            display_text = self.context_list.currentItem().text()
            # Format: "[Type] Nom - Description..."
            if "] " in display_text:
                context_name = display_text.split("] ")[1].split(" - ")[0]
            else:
                context_name = display_text
            
            # Récupérer les données complètes depuis la base de données
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, type, description, properties, parent_id 
                FROM strategy_items 
                WHERE name = ?
            """, (context_name,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                item_id, name, item_type, description, properties, parent_id = result
                
                # Récupérer la hiérarchie complète
                hierarchy = self._get_context_hierarchy(item_id)
                
                return {
                    "id": item_id,
                    "name": name,
                    "type": item_type,
                    "description": description or "",
                    "properties": json.loads(properties) if properties else {},
                    "parent_id": parent_id,
                    "hierarchy": hierarchy,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "selected_context": display_text,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.log_message(f"Erreur lors de la récupération du contexte: {str(e)}")
            return {
                "selected_context": display_text if self.context_list.currentItem() else "",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        
    @pyqtSlot(int)
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
        
    @pyqtSlot(str)
    def update_status(self, status):
        """Met à jour le statut"""
        self.status_label.setText(status)
        self.log_message(status)
        
    @pyqtSlot(dict)
    def on_dataset_generated(self, dataset):
        """Gère la réception d'un nouveau dataset"""
        self.generated_datasets.append(dataset)
        
        # Ajouter à la liste
        display_name = f"Lot {dataset['batch_id'] + 1} - {dataset['timestamp']}"
        self.datasets_list.addItem(display_name)
        
        # Sauvegarder si demandé
        if dataset['config'].get('save_intermediate', False):
            self.save_dataset_to_db(dataset)
            
        self.log_message(f"Dataset généré: {display_name}")
        
    @pyqtSlot(str)
    def on_generation_error(self, error):
        """Gère les erreurs de génération"""
        QMessageBox.critical(self, "Erreur de génération", error)
        self.log_message(f"ERREUR: {error}")
        self.stop_generation()
        
    def generate_preview(self):
        """Génère un aperçu du dataset"""
        # Validation des entrées
        if not self.prompt_edit.toPlainText().strip():
            QMessageBox.warning(self, "Erreur", "Veuillez entrer des instructions de génération")
            return
            
        if self.context_list.currentRow() == -1:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un contexte")
            return
        
        try:
            # Récupérer les paramètres actuels
            output_format = self.format_combo.currentText()
            dataset_type = self.type_combo.currentText()
            examples_count = self.examples_spin.value()
            context_data = self._get_selected_context_data()
            
            # Générer l'aperçu basé sur le modèle prédéfini
            template_example = self._apply_template(dataset_type, output_format)
            
            # Construire l'aperçu détaillé
            preview_text = f"""
📋 APERÇU DU DATASET À GÉNÉRER

🎯 Configuration:
• Format de sortie: {output_format}
• Type de dataset: {dataset_type}
• Exemples par lot: {examples_count}
• Nombre de lots: {self.batches_spin.value()}
• Total d'exemples: {examples_count * self.batches_spin.value()}

🏷️ Contexte sélectionné:
• Nom: {context_data.get('name', 'Non défini')}
• Type: {context_data.get('type', 'Non défini')}
• Description: {context_data.get('description', 'Aucune description')}

📝 Instructions de génération:
{self.prompt_edit.toPlainText()[:200]}{'...' if len(self.prompt_edit.toPlainText()) > 200 else ''}

📊 Exemple de structure attendue:
{template_example}

⚙️ Hiérarchie du contexte:
"""
            
            # Ajouter la hiérarchie si disponible
            hierarchy = context_data.get('hierarchy', [])
            if hierarchy:
                for i, level in enumerate(hierarchy):
                    indent = "  " * i
                    preview_text += f"\n{indent}• {level['type']}: {level['name']}"
            else:
                preview_text += "\nAucune hiérarchie disponible"
            
            # Ajouter les propriétés du contexte si disponibles
            properties = context_data.get('properties', {})
            if properties:
                preview_text += f"\n\n🔧 Propriétés du contexte:\n{json.dumps(properties, indent=2, ensure_ascii=False)}"
            
            self.preview_text.setText(preview_text)
            self.log_message("Aperçu détaillé généré avec succès")
            
            # Activer le bouton d'approbation
            self.approve_preview_btn.setEnabled(True)
            
        except Exception as e:
            error_msg = f"Erreur lors de la génération de l'aperçu: {str(e)}"
            self.preview_text.setText(error_msg)
            self.log_message(error_msg)
        
    def approve_and_continue(self):
        """Approuve l'aperçu et continue la génération complète"""
        reply = QMessageBox.question(
            self, 'Confirmer la génération', 
            'Êtes-vous satisfait de cet aperçu et souhaitez-vous lancer la génération complète ?'
        )
        
        if reply == QMessageBox.Yes:
            self.log_message("Aperçu approuvé, lancement de la génération complète...")
            # Désactiver la case "Générer un aperçu d'abord" pour éviter la redondance
            self.preview_checkbox.setChecked(False)
            # Lancer la génération
            self.start_generation()
        else:
            self.log_message("Génération annulée par l'utilisateur")
        
    def view_selected_dataset(self):
        """Affiche le contenu du dataset sélectionné"""
        current_row = self.datasets_list.currentRow()
        if current_row >= 0 and current_row < len(self.generated_datasets):
            dataset = self.generated_datasets[current_row]
            self.preview_text.setText(json.dumps(dataset, indent=2, ensure_ascii=False))
            self.results_tabs.setCurrentIndex(2)  # Onglet aperçu
            
    def export_selected_dataset(self):
        """Exporte le dataset sélectionné"""
        current_row = self.datasets_list.currentRow()
        if current_row >= 0 and current_row < len(self.generated_datasets):
            dataset = self.generated_datasets[current_row]
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "Exporter le dataset", 
                f"dataset_{dataset['batch_id']}.json",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(dataset, f, indent=2, ensure_ascii=False)
                    QMessageBox.information(self, "Succès", f"Dataset exporté vers {filename}")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")
                    
    def delete_selected_dataset(self):
        """Supprime le dataset sélectionné"""
        current_row = self.datasets_list.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(self, 'Confirmer la suppression', 
                                       'Êtes-vous sûr de vouloir supprimer ce dataset ?')
            if reply == QMessageBox.Yes:
                del self.generated_datasets[current_row]
                self.datasets_list.takeItem(current_row)
                
    def on_dataset_selected(self):
        """Gère la sélection d'un dataset"""
        has_selection = self.datasets_list.currentRow() >= 0
        self.view_dataset_btn.setEnabled(has_selection)
        self.export_dataset_btn.setEnabled(has_selection)
        self.delete_dataset_btn.setEnabled(has_selection)
        
    def save_all_datasets(self):
        """Sauvegarde tous les datasets dans la base de données"""
        if not self.generated_datasets:
            QMessageBox.information(self, "Info", "Aucun dataset à sauvegarder")
            return
            
        saved_count = 0
        for dataset in self.generated_datasets:
            if self.save_dataset_to_db(dataset):
                saved_count += 1
                
        QMessageBox.information(self, "Succès", f"{saved_count} datasets sauvegardés")
        
    def save_dataset_to_db(self, dataset):
        """Sauvegarde un dataset dans la base de données"""
        if not self.db_path:
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO generated_datasets (name, content, config, context_data)
                VALUES (?, ?, ?, ?)
            ''', (
                f"Dataset_Lot_{dataset['batch_id']}",
                json.dumps(dataset['content']),
                json.dumps(dataset['config']),
                json.dumps(dataset.get('context_data', {}))
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            self.log_message(f"Erreur lors de la sauvegarde: {str(e)}")
            return False
            
    def clear_results(self):
        """Efface tous les résultats"""
        reply = QMessageBox.question(self, 'Confirmer l\'effacement', 
                                   'Êtes-vous sûr de vouloir effacer tous les résultats ?')
        if reply == QMessageBox.Yes:
            self.generated_datasets.clear()
            self.datasets_list.clear()
            self.preview_text.clear()
            self.log_text.clear()
            self.progress_bar.setValue(0)
            self.status_label.setText("Prêt à générer")
            
    def log_message(self, message):
        """Ajoute un message au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Faire défiler vers le bas
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_context_hierarchy(self, item_id):
        """Récupère la hiérarchie complète d'un élément de contexte"""
        if not self.db_path:
            return []
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            hierarchy = []
            current_id = item_id
            
            while current_id is not None:
                cursor.execute("""
                    SELECT id, name, type, parent_id 
                    FROM strategy_items 
                    WHERE id = ?
                """, (current_id,))
                
                result = cursor.fetchone()
                if result:
                    item_id, name, item_type, parent_id = result
                    hierarchy.insert(0, {
                        "id": item_id,
                        "name": name,
                        "type": item_type
                    })
                    current_id = parent_id
                else:
                    break
            
            conn.close()
            return hierarchy
            
        except Exception as e:
            self.log_message(f"Erreur lors de la récupération de la hiérarchie: {str(e)}")
            return []
    
    def _get_predefined_templates(self):
        """Retourne les modèles prédéfinis pour les formats de sortie"""
        templates = {
            "JSON": {
                "Conversationnel": {
                    "structure": {
                        "conversations": [
                            {
                                "id": "int",
                                "question": "string",
                                "response": "string",
                                "context": "string",
                                "metadata": "object"
                            }
                        ]
                    },
                    "example": {
                        "conversations": [
                            {
                                "id": 1,
                                "question": "Comment puis-je retourner un produit?",
                                "response": "Vous pouvez retourner votre produit dans les 30 jours...",
                                "context": "Service client - Retours",
                                "metadata": {"category": "support", "priority": "normal"}
                            }
                        ]
                    }
                },
                "Q&A": {
                    "structure": {
                        "qa_pairs": [
                            {
                                "id": "int",
                                "question": "string",
                                "answer": "string",
                                "category": "string",
                                "difficulty": "string"
                            }
                        ]
                    },
                    "example": {
                        "qa_pairs": [
                            {
                                "id": 1,
                                "question": "Qu'est-ce que l'intelligence artificielle?",
                                "answer": "L'intelligence artificielle est...",
                                "category": "Technologie",
                                "difficulty": "Débutant"
                            }
                        ]
                    }
                },
                "Classification": {
                    "structure": {
                        "data": [
                            {
                                "id": "int",
                                "text": "string",
                                "label": "string",
                                "confidence": "float"
                            }
                        ]
                    },
                    "example": {
                        "data": [
                            {
                                "id": 1,
                                "text": "Ce produit est fantastique!",
                                "label": "positif",
                                "confidence": 0.95
                            }
                        ]
                    }
                }
            },
            "CSV": {
                "Standard": {
                    "headers": ["id", "input", "output", "category"],
                    "example": "id,input,output,category\n1,\"Question exemple\",\"Réponse exemple\",\"Catégorie\""
                }
            }
        }
        return templates
    
    def _apply_template(self, dataset_type, output_format):
        """Applique un modèle prédéfini selon le type et format"""
        templates = self._get_predefined_templates()
        
        if output_format in templates and dataset_type in templates[output_format]:
            template = templates[output_format][dataset_type]
            
            if output_format == "JSON":
                return json.dumps(template["example"], indent=2, ensure_ascii=False)
            elif output_format == "CSV":
                return template["example"]
        
        return f"Modèle pour {dataset_type} en format {output_format}"
    
    def _enhance_load_available_contexts(self):
        """Version améliorée du chargement des contextes avec filtrage"""
        self.context_list.clear()
        
        if not self.db_path:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Récupérer tous les éléments avec leur hiérarchie
            cursor.execute("""
                SELECT s1.id, s1.name, s1.type, s1.description,
                       s2.name as parent_name, s2.type as parent_type
                FROM strategy_items s1
                LEFT JOIN strategy_items s2 ON s1.parent_id = s2.id
                ORDER BY s1.type, s1.name
            """)
            
            items = cursor.fetchall()
            conn.close()
            
            # Grouper par type pour une meilleure organisation
            grouped_items = {}
            for item in items:
                item_id, name, item_type, description, parent_name, parent_type = item
                
                if item_type not in grouped_items:
                    grouped_items[item_type] = []
                
                display_text = f"[{item_type}] {name}"
                if parent_name:
                    display_text += f" (sous {parent_name})"
                if description:
                    display_text += f" - {description[:50]}..."
                
                grouped_items[item_type].append({
                    "id": item_id,
                    "display": display_text,
                    "name": name,
                    "type": item_type
                })
            
            # Ajouter les éléments groupés à la liste
            for item_type in ["Cluster", "Racine", "Parent", "Enfant"]:
                if item_type in grouped_items:
                    for item in grouped_items[item_type]:
                        self.context_list.addItem(item["display"])
                        
        except Exception as e:
            self.log_message(f"Erreur lors du chargement des contextes: {str(e)}")
    
    def get_generation_statistics(self):
        """Retourne les statistiques de génération"""
        total_datasets = len(self.generated_datasets)
        total_tokens = sum(
            dataset.get('usage', {}).get('tokens', 0) 
            for dataset in self.generated_datasets
        )
        
        return {
            "total_datasets": total_datasets,
            "total_tokens": total_tokens,
            "average_tokens_per_dataset": total_tokens / total_datasets if total_datasets > 0 else 0,
            "generation_time": datetime.now().isoformat()
        }
