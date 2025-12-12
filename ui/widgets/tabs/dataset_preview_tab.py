#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ui.localization.translator import tr
from ui.styles.theme import Theme

from utils.logger import logger

import logging
from ui.widgets.tabs.context_custer_analysis_tab import ContextClusterAnalysisTab
from utils.context_cluster_analyzer import ContextClusterAnalyzer


class DatasetPreviewTab(QtWidgets.QWidget):
    """Dataset preview tab - Affichage direct de l'analyse Context & Clusters"""

    def __init__(self, project_manager, config_data=None, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data or {}
        self.current_batch_data = None
        self.current_project_data = None
        self._init_ui()

    def _init_ui(self):
        """Create dataset preview tab with direct context cluster view"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header avec sélection de projet et batch
        header_layout = self._create_header()
        layout.addLayout(header_layout)

        # Affichage direct de l'onglet Context & Clusters
        self.context_cluster_tab = ContextClusterAnalysisTab()
        layout.addWidget(self.context_cluster_tab, 1)

    def _create_header(self):
        """Create header with project and batch selection"""
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(16)

        # Sélection du projet
        select_label = QtWidgets.QLabel("Projet")
        select_label.setStyleSheet("""
            QLabel {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-weight: 500;
                font-size: 13px;
                color: #64748b;
                letter-spacing: 0.3px;
            }
        """)
        layout.addWidget(select_label)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_modern_input_style())
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.project_combo.setMinimumWidth(300)
        self.project_combo.setMaximumWidth(380)
        layout.addWidget(self.project_combo)

        layout.addSpacing(24)

        # Sélection du batch (avec option "Tous les batches")
        batch_label = QtWidgets.QLabel("Batch")
        batch_label.setStyleSheet("""
            QLabel {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-weight: 500;
                font-size: 13px;
                color: #64748b;
                letter-spacing: 0.3px;
            }
        """)
        layout.addWidget(batch_label)

        self.batch_combo = QtWidgets.QComboBox()
        self.batch_combo.setStyleSheet(self._get_modern_input_style())
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self.batch_combo.setMinimumWidth(300)
        self.batch_combo.setMaximumWidth(380)
        layout.addWidget(self.batch_combo)

        layout.addSpacing(24)

        # Bouton refresh
        refresh_btn = QtWidgets.QPushButton("↻")
        refresh_btn.setStyleSheet(self._get_button_style())
        refresh_btn.clicked.connect(self.refresh_projects)
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.setToolTip("Actualiser les projets")
        layout.addWidget(refresh_btn)

        layout.addStretch()

        return layout

    def _on_project_changed(self, index):
        """Handle project selection change"""
        if index <= 0:
            self.current_project_data = None
            self.batch_combo.clear()
            self.batch_combo.addItem("-- Sélectionner un batch --")
            self._clear_all_data()
            return

        project_name = self.project_combo.currentText()

        # Charger le projet complet
        if self.project_manager:
            if self.project_manager.load_project(project_name):
                self.current_project_data = self.project_manager.current_project_data

                # Charger les batches dans le combo
                self._load_batches_for_project(project_name)
            else:
                logger.error(f"Impossible de charger le projet: {project_name}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Erreur",
                    f"Impossible de charger le projet '{project_name}'"
                )

    def _on_batch_changed(self, index):
        """Handle batch selection change"""
        if index <= 0:
            self.current_batch_data = None
            self._clear_all_data()
            return

        # Vérifier si c'est l'option "Tous les batches"
        if index == 1:  # Premier élément après "-- Sélectionner --"
            self._update_global_analysis()
        else:
            batch_data = self.batch_combo.itemData(index, Qt.UserRole)
            if batch_data:
                self.current_batch_data = batch_data
                logger.info(f"Batch selected: {batch_data.get('batch_name', 'N/A')}")

                # Mettre à jour l'analyse Context & Clusters pour ce batch
                self._update_context_cluster_analysis(batch_data)

    def _get_full_project_structure_from_db(self):
        """
        Récupère la structure COMPLÈTE du projet depuis la base de données
        pour avoir TOUS les contextes définis, même ceux non utilisés dans les batches
        """
        if not self.project_manager or not self.project_manager.current_project_name:
            logger.warning("⚠️  No project loaded")
            return None

        try:
            project_name = self.project_manager.current_project_name
            
            logger.info("=" * 80)
            logger.info("🗄️  RÉCUPÉRATION STRUCTURE COMPLÈTE DEPUIS DB")
            logger.info("=" * 80)
            logger.info(f"📂 Projet: {project_name}")
            
            # Récupérer la structure complète depuis la DB
            project_data = self.project_manager.database.get_dataset_projet(project_name)
            
            if not project_data:
                logger.warning(f"❌ No project data found for: {project_name}")
                return None
            
            logger.info(f"✅ Données du projet récupérées")
            
            # Extraire tous les contextes définis dans la structure
            all_contexts = {}
            
            typologies = project_data.get('typologies', [])
            logger.info(f"📊 {len(typologies)} typologie(s) trouvée(s)")
            
            for typ_idx, typologie in enumerate(typologies):
                typ_name = typologie.get('name', '')
                logger.info(f"\n  [{typ_idx+1}] Typologie: '{typ_name}'")
                
                clusters = typologie.get('taxonomy_clusters', [])
                logger.info(f"      └─ {len(clusters)} cluster(s)")
                
                for cluster_idx, cluster in enumerate(clusters):
                    cluster_name = cluster.get('name', '')
                    context_key = f"{typ_name} > {cluster_name}"
                    
                    # Compter tous les root_labels définis
                    root_labels = cluster.get('root_labels', [])
                    
                    logger.info(f"         [{cluster_idx+1}] Cluster: '{cluster_name}'")
                    logger.info(f"             └─ {len(root_labels)} root_label(s) défini(s)")
                    
                    if context_key not in all_contexts:
                        all_contexts[context_key] = {
                            'typologie': typ_name,
                            'cluster': cluster_name,
                            'total_defined': len(root_labels),
                            'count_in_batches': 0  # Sera mis à jour après
                        }
            
            logger.info(f"\n{'=' * 80}")
            logger.info(f"✅ {len(all_contexts)} contextes trouvés dans la structure DB")
            logger.info(f"{'=' * 80}\n")
            
            return all_contexts
            
        except Exception as e:
            logger.error(f"❌ Error getting project structure from DB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _update_global_analysis(self):
        """
        Met à jour l'analyse globale de TOUS les batches du projet
        EN UTILISANT la structure complète de la DB comme référence
        """
        if not self.project_manager or not self.project_manager.current_project_name:
            logger.warning("⚠️  No project loaded for global analysis")
            return

        try:
            project_name = self.project_manager.current_project_name
            
            logger.info("\n" + "=" * 80)
            logger.info("🌍 MISE À JOUR ANALYSE GLOBALE")
            logger.info("=" * 80)
            logger.info(f"📂 Projet: {project_name}")
            
            # 1. Récupérer la structure COMPLÈTE depuis la DB
            logger.info("\n🔍 ÉTAPE 1: Récupération structure DB...")
            full_structure = self._get_full_project_structure_from_db()
            
            if not full_structure:
                logger.warning("❌ Unable to get full project structure")
                if hasattr(self, 'context_cluster_tab'):
                    self.context_cluster_tab.update_analysis(None)
                return
            
            # 2. Récupérer tous les batches
            logger.info("\n🔍 ÉTAPE 2: Récupération des batches...")
            all_batches = self.project_manager.get_all_batches()
            
            logger.info(f"📦 {len(all_batches)} batch(es) trouvé(s)")
            
            if not all_batches:
                logger.warning(f"⚠️  No batches found for project: {project_name}")
                logger.info("   → Affichage de la structure sans occurrences")
                # Afficher quand même la structure complète avec 0 occurrences
                analysis = self._create_analysis_from_structure(full_structure)
                if hasattr(self, 'context_cluster_tab'):
                    logger.info("📊 Envoi de l'analyse au tab...")
                    self.context_cluster_tab.update_analysis(analysis)
                return

            # 3. Agréger toutes les combinaisons de tous les batches
            logger.info("\n🔍 ÉTAPE 3: Agrégation des combinaisons...")
            all_combinations = []
            total_batches = len(all_batches)
            
            for batch_idx, batch in enumerate(all_batches):
                batch_data = batch.get('data', {})
                batch_name = batch_data.get('batch_name', f"Batch #{batch.get('batch_number')}")
                combinations = batch_data.get('combinations', [])
                
                logger.info(f"  [{batch_idx+1}/{total_batches}] {batch_name}: {len(combinations)} combinaisons")
                all_combinations.extend(combinations)
            
            logger.info(f"\n✅ Total: {len(all_combinations)} combinaisons agrégées")
            
            # 4. Compter les occurrences dans les batches
            logger.info("\n🔍 ÉTAPE 4: Comptage des occurrences...")
            for combo_idx, combination in enumerate(all_combinations):
                typologie = combination.get('typologie', combination.get('context', {}).get('typologie', ''))
                taxonomy = combination.get('taxonomy_cluster', combination.get('context', {}).get('taxonomy', ''))
                context_key = f"{typologie} > {taxonomy}"
                
                if context_key in full_structure:
                    full_structure[context_key]['count_in_batches'] += 1
                else:
                    logger.warning(f"   ⚠️  Contexte non trouvé dans structure: {context_key}")
            
            # Log résumé des occurrences
            logger.info("\n📊 RÉSUMÉ DES OCCURRENCES:")
            for context_key, context_data in full_structure.items():
                count = context_data['count_in_batches']
                total_def = context_data['total_defined']
                logger.info(f"  • {context_key}")
                logger.info(f"      → {count} occurrences, {total_def} labels définis")
            
            # 5. Créer l'analyse complète
            logger.info("\n🔍 ÉTAPE 5: Création de l'analyse...")
            analysis = self._create_analysis_from_structure(full_structure)

            # 6. Mise à jour de l'onglet
            if hasattr(self, 'context_cluster_tab'):
                logger.info("\n📊 ÉTAPE 6: Envoi de l'analyse au tab...")
                self.context_cluster_tab.update_analysis(analysis)
                logger.info("✅ Analyse envoyée au tab")

            logger.info("\n" + "=" * 80)
            logger.info(f"✅ ANALYSE GLOBALE TERMINÉE")
            logger.info(f"   • Projet: {project_name}")
            logger.info(f"   • {len(all_combinations)} combinaisons")
            logger.info(f"   • {total_batches} batches")
            logger.info(f"   • {len(full_structure)} contextes")
            logger.info("=" * 80 + "\n")

        except Exception as e:
            logger.error(f"\n❌ Error updating global analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _create_analysis_from_structure(self, full_structure):
        """
        Crée une analyse complète basée sur la structure complète du projet
        Compatible avec ContextClusterAnalyzer
        VERSION CORRIGÉE: Ne crée PAS de master vide
        """
        try:
            logger.info("=" * 80)
            logger.info("📊 CRÉATION DE L'ANALYSE DEPUIS LA STRUCTURE DB")
            logger.info("=" * 80)
            
            # Créer des combinaisons virtuelles pour chaque contexte
            virtual_combinations = []
            
            for context_key, context_data in full_structure.items():
                typologie = context_data['typologie']
                cluster = context_data['cluster']
                count = context_data['count_in_batches']
                total_defined = context_data['total_defined']
                
                logger.info(f"  📍 Contexte: {context_key}")
                logger.info(f"     - Typologie: {typologie}")
                logger.info(f"     - Cluster: {cluster}")
                logger.info(f"     - Occurrences dans batches: {count}")
                logger.info(f"     - Labels définis dans DB: {total_defined}")
                
                # Créer une combinaison virtuelle pour ce contexte
                # IMPORTANT: NE PAS inclure 'master' du tout (pas même vide)
                if count > 0:
                    virtual_combinations.append({
                        'context': {
                            'typologie': typologie,
                            'taxonomy': cluster,
                            'label': f"{typologie} > {cluster}",
                            'level': 'typologie'
                        },
                        'sample_count': count
                        # PAS DE 'master' ici !
                    })
                else:
                    # Ajouter quand même avec 1 sample pour le visualiser
                    logger.info(f"     ⚠️  Aucune occurrence, ajout avec 1 sample virtuel")
                    virtual_combinations.append({
                        'context': {
                            'typologie': typologie,
                            'taxonomy': cluster,
                            'label': f"{typologie} > {cluster}",
                            'level': 'typologie'
                        },
                        'sample_count': 1
                        # PAS DE 'master' ici non plus !
                    })
            
            logger.info(f"\n✅ {len(virtual_combinations)} combinaisons virtuelles créées")
            logger.info("=" * 80 + "\n")
            
            # Utiliser ContextClusterAnalyzer pour créer l'analyse
            from utils.context_cluster_analyzer import ContextClusterAnalyzer
            analysis = ContextClusterAnalyzer.analyze_context_typologies_with_clusters(
                virtual_combinations
            )
            
            logger.info("✅ Analyse créée par ContextClusterAnalyzer")
            logger.info(f"   - Total samples: {analysis.get('total_samples', 0)}")
            logger.info(f"   - Context typologies: {len(analysis.get('context_typologies', {}))}")
            logger.info(f"   - Master typologies: {len(analysis.get('master_typologies', {}))}")
            
            # ⚠️ VÉRIFICATION: S'assurer qu'il n'y a pas de master généré
            if analysis.get('master_typologies'):
                logger.warning("⚠️  Des master typologies ont été générées alors qu'elles ne devraient pas exister!")
                for master_name in analysis['master_typologies'].keys():
                    logger.warning(f"    → {master_name}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error creating analysis from structure: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _update_context_cluster_analysis(self, batch_data):
        """
        Met à jour l'analyse des typologies de contexte et clusters pour UN batch
        EN UTILISANT la structure complète de la DB comme référence
        """
        if not batch_data:
            if hasattr(self, 'context_cluster_tab'):
                self.context_cluster_tab.update_analysis(None)
            return

        try:
            # 1. Récupérer la structure complète depuis la DB
            full_structure = self._get_full_project_structure_from_db()
            
            if not full_structure:
                logger.warning("Unable to get full project structure")
                if hasattr(self, 'context_cluster_tab'):
                    self.context_cluster_tab.update_analysis(None)
                return
            
            # 2. Récupérer les combinaisons du batch
            combinations = batch_data.get('combinations', [])
            
            if not combinations:
                logger.warning("No combinations found for context/cluster analysis")
                # Afficher quand même la structure complète avec 0 occurrences
                analysis = self._create_analysis_from_structure(full_structure)
                if hasattr(self, 'context_cluster_tab'):
                    self.context_cluster_tab.update_analysis(analysis)
                return

            # 3. Compter les occurrences dans ce batch
            for combination in combinations:
                typologie = combination.get('typologie', '')
                taxonomy = combination.get('taxonomy_cluster', '')
                context_key = f"{typologie} > {taxonomy}"
                
                if context_key in full_structure:
                    full_structure[context_key]['count_in_batches'] += 1

            # 4. Créer l'analyse complète
            analysis = self._create_analysis_from_structure(full_structure)

            # 5. Mise à jour de l'onglet
            if hasattr(self, 'context_cluster_tab'):
                self.context_cluster_tab.update_analysis(analysis)

            logger.info(f"✅ Context/Cluster analysis updated for batch: "
                       f"{batch_data.get('batch_name', 'N/A')}, "
                       f"{len(combinations)} combinations, {len(full_structure)} contexts in structure")

        except Exception as e:
            logger.error(f"Error updating context/cluster analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _load_batches_for_project(self, project_name):
        """Load batches for the selected project"""
        self.batch_combo.blockSignals(True)
        self.batch_combo.clear()
        self.batch_combo.addItem("-- Sélectionner un batch --")
        
        # Ajouter l'option "Tous les batches" avec icône
        self.batch_combo.addItem("📊 Tous les batches (Dataset global)", None)

        if not self.project_manager:
            self.batch_combo.blockSignals(False)
            return

        try:
            batches = self.project_manager.get_all_batches()

            for batch in batches:
                batch_number = batch.get('batch_number', 0)
                batch_data = batch.get('data', {})
                batch_name = batch_data.get('batch_name', f'Batch #{batch_number}')
                count = batch_data.get('count', 0)
                status = batch.get('status', 'pending')

                display_text = f"#{batch_number} - {batch_name} ({count} combinaisons) [{status}]"
                self.batch_combo.addItem(display_text, batch_data)

            logger.info(f"Loaded {len(batches)} batches for project: {project_name}")

        except Exception as e:
            logger.error(f"Error loading batches: {e}")

        finally:
            self.batch_combo.blockSignals(False)
            
            # IMPORTANT : Déclencher l'analyse globale APRÈS le déblocage des signaux
            if len(batches) > 0:
                self.batch_combo.setCurrentIndex(1)  # Index 1 = "Tous les batches"
                # Déclencher manuellement l'analyse car les signaux étaient bloqués
                self._update_global_analysis()

    def _clear_all_data(self):
        """Clear all displayed data"""
        if hasattr(self, 'context_cluster_tab'):
            self.context_cluster_tab.update_analysis(None)

        self.current_batch_data = None

        logger.debug("All data cleared")

    def _get_modern_input_style(self):
        """Modern minimalist input field style"""
        svg_path = self._get_dropdown_svg_path()

        return f"""
            QComboBox {{
                border: 1.5px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 14px;
                padding-right: 36px;
                background-color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                font-weight: 400;
                color: #0f172a;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: #cbd5e1;
                background-color: #f8fafc;
            }}
            QComboBox:focus {{
                border: 1.5px solid #3b82f6;
                background-color: #ffffff;
                outline: none;
            }}
            QComboBox:disabled {{
                background-color: #f1f5f9;
                color: #94a3b8;
                border-color: #e2e8f0;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 32px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QComboBox::drop-down:hover {{
                background-color: rgba(59, 130, 246, 0.04);
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 14px;
                height: 14px;
            }}
            QComboBox QAbstractItemView {{
                border: 1.5px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                selection-background-color: #3b82f6;
                selection-color: white;
                padding: 6px;
                outline: none;
                margin-top: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 10px 14px;
                border-radius: 6px;
                min-height: 20px;
                color: #0f172a;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #f1f5f9;
                color: #0f172a;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #3b82f6;
                color: white;
            }}
        """

    def _get_button_style(self):
        """Get modern minimalist button style"""
        return """
            QPushButton {
                background-color: #ffffff;
                border: 1.5px solid #e2e8f0;
                color: #64748b;
                font-weight: 500;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #3b82f6;
                color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #eff6ff;
                border-color: #2563eb;
                color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #f1f5f9;
                border-color: #e2e8f0;
                color: #cbd5e1;
            }
        """
    
    def _get_dropdown_svg_path(self):
        """Get absolute path to dropdown SVG icon"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(current_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        return os.path.normpath(svg_path).replace('\\', '/')

    def refresh_projects(self):
        """Refresh project list"""
        if not self.project_manager:
            return
        
        projects = self.project_manager.get_all_projects()
        project_names = sorted([p['name'] for p in projects])

        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- Sélectionner un projet --")
        self.project_combo.addItems(project_names)
        
        if self.project_manager.current_project_name in project_names:
            index = project_names.index(self.project_manager.current_project_name) + 1
            self.project_combo.setCurrentIndex(index)
        
        self.project_combo.blockSignals(False)
        
        if self.project_combo.currentIndex() > 0:
            self._on_project_changed(self.project_combo.currentIndex())

    def update_preview(self, project_data):
        """Update preview with project data - Compatibility method"""
        if not project_data:
            return

        try:
            self.current_project_data = project_data
            logger.info("Preview updated successfully")

        except Exception as e:
            logger.error(f"Error in update_preview: {e}")
            import traceback
            logger.error(traceback.format_exc())