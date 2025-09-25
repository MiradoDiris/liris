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
                             QSplitter, QTreeWidget, QTreeWidgetItem)

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
        """Enrichit le prompt de base avec la hiérarchie sélectionnée"""
        enriched = self.base_prompt
        
        if self.contexts:
            contexts_text = "\n\n=== STRUCTURE HIÉRARCHIQUE SÉLECTIONNÉE ===\n"
            
            # Grouper par cluster
            clusters_context = {}
            for context in self.contexts:
                cluster_name = context.get('cluster')
                if cluster_name not in clusters_context:
                    clusters_context[cluster_name] = []
                clusters_context[cluster_name].append(context)
            
            for cluster_name, contexts in clusters_context.items():
                contexts_text += f"\n📊 CLUSTER: {cluster_name}\n"
                
                # Organiser les éléments par type
                roots = set()
                parents = set()
                children = set()
                
                for context in contexts:
                    element_type = context.get('type')
                    element_name = context.get('element_name')
                    
                    if element_type == 'cluster':
                        contexts_text += "  • [Cluster entier sélectionné]\n"
                    elif element_type == 'root' and element_name:
                        roots.add(element_name)
                    elif element_type == 'parent' and element_name:
                        parents.add(element_name)
                    elif element_type == 'child' and element_name:
                        children.add(element_name)
                
                if roots:
                    contexts_text += f"  🌳 Racines: {', '.join(roots)}\n"
                
                if parents:
                    contexts_text += f"  👥 Parents: {', '.join(parents)}\n"
                
                if children:
                    contexts_text += f"  👶 Enfants: {', '.join(children)}\n"
                
                contexts_text += "-" * 50 + "\n"
            
            enriched += contexts_text
            
        return enriched
    
    def _format_hierarchical_context(self, context):
        """Formate un contexte hiérarchique pour l'affichage"""
        parts = []
        if context.get('cluster'):
            parts.append(f"Cluster: {context['cluster']}")
        if context.get('root'):
            parts.append(f"Racine: {context['root']}")
        if context.get('parent'):
            parts.append(f"Parent: {context['parent']}")
        if context.get('child'):
            parts.append(f"Enfant: {context['child']}")
        
        return " > ".join(parts)
    
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
        self.strategy_widget = None  # Référence vers le widget de stratégie
        
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
        
        # Section Structure hiérarchique (en haut à gauche)
        hierarchy_group = QGroupBox("Structure hiérarchique des clusters")
        hierarchy_layout = QVBoxLayout(hierarchy_group)
        
        # Arbre pour afficher la structure hiérarchique
        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setHeaderLabels(["Élément", "Type", "Statut"])
        self.hierarchy_tree.setSelectionMode(QTreeWidget.MultiSelection)
        self.hierarchy_tree.itemClicked.connect(self._on_hierarchy_item_clicked)
        
        hierarchy_layout.addWidget(QLabel("Sélectionnez un ou plusieurs éléments hiérarchiques:"))
        hierarchy_layout.addWidget(self.hierarchy_tree)
        
        # Informations de sélection
        self.selection_info = QLabel("Aucun élément sélectionné")
        self.selection_info.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        self.selection_info.setWordWrap(True)
        hierarchy_layout.addWidget(self.selection_info)
        
        left_layout.addWidget(hierarchy_group)
        
        # Section Prompt de base (en bas à gauche)
        prompt_group = QGroupBox("Prompt de base")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Rédigez votre prompt de base ici...\n\n"
            "Ce prompt sera automatiquement enrichi avec les CLUSTERS sélectionnés "
            "et leur structure hiérarchique complète (racines, parents, enfants)."
        )
        self.prompt_edit.setMinimumHeight(200)
        
        prompt_layout.addWidget(QLabel("Prompt de base (sera enrichi par la structure sélectionnée):"))
        prompt_layout.addWidget(self.prompt_edit)
        
        left_layout.addWidget(prompt_group)
        
        # Ajuster les proportions de la partie gauche
        left_layout.setStretchFactor(hierarchy_group, 2)
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
    
    def _refresh_hierarchy_tree(self):
        """Rafraîchit l'arbre hiérarchique avec les clusters ET leur structure complète - VERSION CORRIGÉE"""
        self.hierarchy_tree.clear()
        
        # Vérifier d'abord si strategy_widget existe
        if not self.strategy_widget:
            logger.warning("StrategyWidget non défini")
            no_data_item = QTreeWidgetItem(["StrategyWidget non disponible", "Veuillez configurer une stratégie d'abord", ""])
            self.hierarchy_tree.addTopLevelItem(no_data_item)
            return
            
        # Récupérer les données de typologie via la nouvelle méthode
        typology = self.strategy_widget.get_current_typology_data()
        
        logger.info(f"Typologie reçue: {typology.get('name', 'Inconnue')}")
        logger.info(f"Nombre de clusters dans typologie: {len(typology.get('clusters', []))}")
        
        if not typology or not typology.get('clusters'):
            logger.warning("Aucune typologie disponible ou typologie vide")
            # Afficher un message dans l'arbre
            no_data_item = QTreeWidgetItem(["Aucune typologie chargée", "Veuillez configurer une stratégie d'abord", ""])
            self.hierarchy_tree.addTopLevelItem(no_data_item)
            return
        
        clusters = typology['clusters']
        logger.info(f"Chargement de {len(clusters)} clusters dans l'arbre hiérarchique")
        
        # Afficher les clusters et leur hiérarchie
        for cluster in clusters:
            cluster_name = cluster.get('name', 'Sans nom')
            cluster_item = QTreeWidgetItem([
                cluster_name, 
                'Cluster', 
                '✓'
            ])
            cluster_item.setData(0, QtCore.Qt.UserRole, {
                'type': 'cluster',
                'cluster': cluster_name,
                'cluster_id': cluster.get('id'),
                'full_cluster_data': cluster
            })
            self.hierarchy_tree.addTopLevelItem(cluster_item)
            
            # AJOUTER LA STRUCTURE HIÉRARCHIQUE COMPLÈTE
            roots = cluster.get('roots', [])
            logger.info(f"Cluster '{cluster_name}' a {len(roots)} racines")
            
            for root in roots:
                root_name = root.get('name', 'Sans nom')
                root_item = QTreeWidgetItem([
                    root_name, 
                    'Racine', 
                    '✓'
                ])
                root_item.setData(0, QtCore.Qt.UserRole, {
                    'type': 'root',
                    'cluster': cluster_name,
                    'root': root_name,
                    'root_id': root.get('id')
                })
                cluster_item.addChild(root_item)
                
                # Parents
                parents = root.get('parents', [])
                for parent in parents:
                    parent_name = parent.get('name', 'Sans nom')
                    parent_item = QTreeWidgetItem([
                        parent_name, 
                        'Parent', 
                        '✓'
                    ])
                    parent_item.setData(0, QtCore.Qt.UserRole, {
                        'type': 'parent',
                        'cluster': cluster_name,
                        'root': root_name,
                        'parent': parent_name,
                        'parent_id': parent.get('id')
                    })
                    root_item.addChild(parent_item)
                    
                    # Enfants
                    children = parent.get('children', [])
                    for child in children:
                        child_name = child.get('name', 'Sans nom')
                        child_item = QTreeWidgetItem([
                            child_name, 
                            'Enfant', 
                            '✓'
                        ])
                        child_item.setData(0, QtCore.Qt.UserRole, {
                            'type': 'child',
                            'cluster': cluster_name,
                            'root': root_name,
                            'parent': parent_name,
                            'child': child_name,
                            'child_id': child.get('id')
                        })
                        parent_item.addChild(child_item)
        
        # Développer tout l'arbre pour montrer la structure
        self.hierarchy_tree.expandAll()
        logger.info(f"Arbre hiérarchique rafraîchi avec {len(clusters)} clusters")

    def set_strategy_widget(self, strategy_widget):
        """Définit la référence vers le widget de stratégie"""
        self.strategy_widget = strategy_widget

        # Se connecter au signal de changement de typologie (CORRIGÉ)
        if hasattr(strategy_widget, 'typology_changed_signal'):
            strategy_widget.typology_changed_signal.connect(self._refresh_hierarchy_tree)
        
        self._refresh_hierarchy_tree()
        
    def _on_hierarchy_item_clicked(self, item, column):
        """Gère le clic sur un élément de l'arbre hiérarchique"""
        selected_items = self.hierarchy_tree.selectedItems()
        selected_count = len(selected_items)
        
        if selected_count == 0:
            self.selection_info.setText("Aucun élément sélectionné")
            return
        
        # Filtrer et organiser les sélections par cluster
        cluster_selections = {}
        
        for selected_item in selected_items:
            data = selected_item.data(0, QtCore.Qt.UserRole)
            if data:
                cluster_name = data.get('cluster')
                if cluster_name not in cluster_selections:
                    cluster_selections[cluster_name] = {
                        'cluster_data': None,
                        'roots': set(),
                        'parents': set(),
                        'children': set()
                    }
                
                # Organiser par type
                element_type = data.get('type')
                element_name = data.get(element_type)  # cluster, root, parent, child
                
                if element_type == 'cluster':
                    cluster_selections[cluster_name]['cluster_data'] = data
                elif element_type == 'root':
                    cluster_selections[cluster_name]['roots'].add(element_name)
                elif element_type == 'parent':
                    cluster_selections[cluster_name]['parents'].add(element_name)
                elif element_type == 'child':
                    cluster_selections[cluster_name]['children'].add(element_name)
        
        # Construire le texte d'information
        selection_text = f"{selected_count} élément(s) sélectionné(s):\n\n"
        
        for cluster_name, selections in cluster_selections.items():
            selection_text += f"📊 **Cluster: {cluster_name}**\n"
            
            if selections['cluster_data']:
                selection_text += "  • Cluster sélectionné\n"
            
            if selections['roots']:
                selection_text += f"  🌳 Racines: {', '.join(selections['roots'])}\n"
            
            if selections['parents']:
                selection_text += f"  👥 Parents: {', '.join(selections['parents'])}\n"
            
            if selections['children']:
                selection_text += f"  👶 Enfants: {', '.join(selections['children'])}\n"
            
            selection_text += "\n"
        
        self.selection_info.setText(selection_text)
    
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
        """Lance la génération du dataset basée sur la hiérarchie sélectionnée"""
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
        
        # Récupérer les éléments sélectionnés et les organiser par cluster
        selected_items = self.hierarchy_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner au moins un élément")
            return
        
        # Organiser les sélections par cluster
        hierarchical_contexts = []
        
        for item in selected_items:
            data = item.data(0, QtCore.Qt.UserRole)
            if data:
                # Créer un contexte structuré pour chaque élément sélectionné
                context = {
                    'type': data.get('type'),
                    'cluster': data.get('cluster'),
                    'root': data.get('root'),
                    'parent': data.get('parent'),
                    'child': data.get('child'),
                    'element_name': data.get(data.get('type'))  # Nom de l'élément
                }
                hierarchical_contexts.append(context)
        
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
        self._add_log(f"Éléments sélectionnés: {len(hierarchical_contexts)}")
        self._add_log(f"Nombre de batches: {num_batches}")
        self._add_log("")
        
        # Lancer le worker de génération
        self.generation_worker = GenerationWorker(
            self.conductor, platform, base_prompt, hierarchical_contexts, 
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
        
        # Rafraîchir l'arbre hiérarchique si le widget de stratégie est disponible
        if self.strategy_widget:
            self._refresh_hierarchy_tree()
    
    def update_language(self):
        """Met à jour les textes selon la langue"""
        # Implémenter la traduction si nécessaire
        pass