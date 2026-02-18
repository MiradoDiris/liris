#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/rl_panel.py - Panel Reinforcement Learning
Interface pour la configuration et l'entraînement RL
"""
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox, QComboBox, QSpinBox
)
from PyQt5.QtGui import QFont
import qtawesome as qta

from grpo_worker.grpo_worker import GRPOWorker
from rl_grpo.config import GRPOConfig
from ui.styles.theme import Theme
from utils.logger import logger


class GradientButton(QPushButton):
    """Bouton avec dégradé personnalisé"""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 {Theme.PRIMARY_COLOR});
            }}
            QPushButton:pressed {{
                background: {Theme.PRIMARY_COLOR};
            }}
            QPushButton:disabled {{
                background: #CCCCCC;
                color: #888888;
            }}
        """)


class RLPanel(QWidget):
    """Panel principal pour le Reinforcement Learning"""
    
    training_started = pyqtSignal(str)  # project_name
    training_completed = pyqtSignal(str, dict)  # project_name, results
    training_failed = pyqtSignal(str, str)  # project_name, error
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.database = None
        self.current_project = None
        self.current_project_name = None
        self.current_batch_number = None
        self.current_batch_data = None
        
        logger.info("🤖 Initialisation RLPanel")
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialise l'interface utilisateur - Layout 3 colonnes RESPONSIVE"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # ✅ UTILISER UN QSPLITTER POUR LES 3 COLONNES RESPONSIVE
        from PyQt5.QtWidgets import QSplitter
        
        self.columns_splitter = QSplitter(Qt.Horizontal)
        self.columns_splitter.setHandleWidth(1)
        self.columns_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E0E0E0;
            }
            QSplitter::handle:hover {
                background: #4A90E2;
            }
        """)
        
        # === COLONNE GAUCHE (Configuration) ===
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        left_column = self._create_left_column()
        left_scroll.setWidget(left_column)
        self.columns_splitter.addWidget(left_scroll)
        
        # === COLONNE CENTRALE (Environnement & Agent) ===
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QFrame.NoFrame)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        center_column = self._create_center_column()
        center_scroll.setWidget(center_column)
        self.columns_splitter.addWidget(center_scroll)
        
        # === COLONNE DROITE (Résultats & Visualisation) ===
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        right_column = self._create_right_column()
        right_scroll.setWidget(right_column)
        self.columns_splitter.addWidget(right_column)
        
        # ✅ DÉFINIR LES PROPORTIONS INITIALES (25% - 35% - 40%)
        total_width = 1200
        self.columns_splitter.setSizes([
            int(total_width * 0.25),
            int(total_width * 0.35),
            int(total_width * 0.40)
        ])
        
        # ✅ DÉFINIR LES LARGEURS MINIMALES
        left_scroll.setMinimumWidth(200)
        center_scroll.setMinimumWidth(250)
        right_scroll.setMinimumWidth(280)
        
        main_layout.addWidget(self.columns_splitter)
        
        # === BARRE D'ACTIONS EN BAS ===
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(20, 10, 20, 20)
        
        actions = self._create_actions()
        bottom_layout.addWidget(actions)
        
        main_layout.addWidget(bottom_widget)
        
    def _create_left_column(self):
        """Crée la colonne gauche - Configuration du projet RL"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === EN-TÊTE ===
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)
        
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.robot', color='#666').pixmap(20, 20))
        title_layout.addWidget(title_icon)
        
        title_label = QLabel("Configuration RL")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # === SECTION SÉLECTION BATCH ===
        batch_group = QGroupBox("Sélection du Batch")
        batch_group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        batch_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)
        
        batch_layout = QVBoxLayout(batch_group)
        
        # 1. Combo Projet
        project_label = QLabel("Projet:")
        project_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_layout.addWidget(project_label)
        
        self.project_combo = QComboBox()
        self.project_combo.addItem("Sélectionner un projet", None)
        self.project_combo.setMinimumHeight(40)
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        self._apply_combo_style(self.project_combo)
        batch_layout.addWidget(self.project_combo)
        
        # 2. Combo Famille de Batch
        family_label = QLabel("Famille de batch:")
        family_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_layout.addWidget(family_label)
        
        self.batch_family_combo = QComboBox()
        self.batch_family_combo.addItem("Sélectionner une famille", None)
        self.batch_family_combo.setMinimumHeight(40)
        self.batch_family_combo.currentTextChanged.connect(self._on_batch_family_changed)
        self._apply_combo_style(self.batch_family_combo)
        batch_layout.addWidget(self.batch_family_combo)
        
        # 3. Combo Batch
        batch_label = QLabel("Batch:")
        batch_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_layout.addWidget(batch_label)
        
        self.batch_combo = QComboBox()
        self.batch_combo.addItem("Sélectionner un batch", None)
        self.batch_combo.setMinimumHeight(40)
        self.batch_combo.currentIndexChanged.connect(self._on_batch_changed)
        self._apply_combo_style(self.batch_combo)
        batch_layout.addWidget(self.batch_combo)
        
        # 4. Upload Batch personnalisé
        batch_layout.addSpacing(10)
        upload_label = QLabel("Ou uploader un batch:")
        upload_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        batch_layout.addWidget(upload_label)
        
        upload_container = QHBoxLayout()
        upload_container.setSpacing(10)
        
        self.batch_file_input = QtWidgets.QLineEdit()
        self.batch_file_input.setPlaceholderText("Aucun fichier sélectionné")
        self.batch_file_input.setReadOnly(True)
        self.batch_file_input.setMinimumHeight(40)
        upload_container.addWidget(self.batch_file_input, 1)
        
        self.browse_btn = QPushButton("Parcourir...")
        self.browse_btn.setMinimumHeight(40)
        self.browse_btn.setMaximumWidth(120)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._on_browse_batch)
        upload_container.addWidget(self.browse_btn)
        
        self.clear_batch_btn = QPushButton("Effacer")
        self.clear_batch_btn.setMinimumHeight(40)
        self.clear_batch_btn.setMaximumWidth(100)
        self.clear_batch_btn.setCursor(Qt.PointingHandCursor)
        self.clear_batch_btn.setEnabled(False)
        
        self.clear_batch_btn.clicked.connect(self._on_clear_batch)
        upload_container.addWidget(self.clear_batch_btn)
        
        batch_layout.addLayout(upload_container)
        
        layout.addWidget(batch_group)
        
        # === SECTION ALGORITHME ===
        algo_group = QGroupBox("Algorithme RL")
        algo_group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        algo_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)
        
        algo_layout = QVBoxLayout(algo_group)
        
        # Info GRPO
        grpo_info = QLabel(
            "🎯 <b>GRPO</b> (Group Relative Policy Optimization)<br>"
            "<small>Algorithme de fine-tuning pour LLMs avec reward model</small>"
        )
        grpo_info.setWordWrap(True)
        grpo_info.setStyleSheet(
            "padding: 10px; background: #F0F8FF; border-radius: 4px; "
            "font-size: 9pt; color: #333;"
        )
        algo_layout.addWidget(grpo_info)
        
        layout.addWidget(algo_group)
        
        # === SECTION HYPERPARAMÈTRES ===
        params_group = QGroupBox("Hyperparamètres")
        params_group.setFont(QFont("Segoe UI", 10, QFont.Bold))
        params_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
        """)
        
        params_layout = QVBoxLayout(params_group)
        
        # Episodes
        episodes_label = QLabel("Nombre d'épisodes:")
        episodes_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        params_layout.addWidget(episodes_label)
        
        self.episodes_spin = QSpinBox()
        self.episodes_spin.setRange(100, 100000)
        self.episodes_spin.setValue(1000)
        self.episodes_spin.setMinimumHeight(40)
        self._apply_spinbox_style(self.episodes_spin)
        params_layout.addWidget(self.episodes_spin)
        
        # Learning Rate
        lr_label = QLabel("Learning Rate:")
        lr_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        params_layout.addWidget(lr_label)
        
        self.lr_combo = QComboBox()
        self.lr_combo.addItems(["0.0001", "0.0003", "0.001", "0.003", "0.01"])
        self.lr_combo.setCurrentText("0.0003")
        self.lr_combo.setMinimumHeight(40)
        self._apply_combo_style(self.lr_combo)
        params_layout.addWidget(self.lr_combo)
        
        # Batch Size
        batch_size_label = QLabel("Batch Size:")
        batch_size_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        params_layout.addWidget(batch_size_label)
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 512)
        self.batch_size_spin.setValue(32)
        self.batch_size_spin.setMinimumHeight(40)
        self._apply_spinbox_style(self.batch_size_spin)
        params_layout.addWidget(self.batch_size_spin)
        
        layout.addWidget(params_group)
        
        layout.addStretch()
        
        return column
        
    def _on_project_changed(self, project_name):
        """Gère le changement de projet"""
        logger.info(f"🔄 Changement de projet RL: {project_name}")
        
        if project_name == "Sélectionner un projet" or not project_name:
            self.current_project_name = None
            self.batch_family_combo.clear()
            self.batch_family_combo.addItem("Aucun projet", None)
            self.batch_combo.clear()
            self.batch_combo.addItem("Aucun projet", None)
            return
        
        try:
            self.current_project_name = project_name
            self._load_batch_families()
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
    
    def _load_batch_families(self):
        """Charge les familles de batch du projet actuel"""
        self.batch_family_combo.clear()
        self.batch_family_combo.addItem("Sélectionner une famille", None)
        
        if not self.current_project_name or not self.database:
            return
        
        try:
            logger.info(f"🔍 Recherche des familles pour: {self.current_project_name}")
            batches = self.database.get_all_batches(self.current_project_name)
            
            if not batches:
                self.batch_family_combo.addItem("Aucune famille", None)
                return
            
            families = set()
            for batch in batches:
                batch_data = batch.get('data', {})
                family = batch_data.get('batch_family', '')
                if family:
                    families.add(family)
            
            if not families:
                self.batch_family_combo.addItem("Aucune famille", None)
                return
            
            families_sorted = sorted(list(families))
            for family in families_sorted:
                count = sum(1 for b in batches if b.get('data', {}).get('batch_family', '') == family)
                display_name = f"{family} ({count} batch{'es' if count > 1 else ''})"
                self.batch_family_combo.addItem(display_name, family)
            
            logger.info(f"✅ {len(families_sorted)} famille(s) chargée(s)")
        
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
    
    def _on_batch_family_changed(self, family_name):
        """Gère le changement de famille de batch"""
        family = self.batch_family_combo.currentData()
        logger.info(f"🔄 Changement de famille RL: {family_name}")
        
        if family is None:
            self.batch_combo.clear()
            self.batch_combo.addItem("Sélectionner une famille", None)
            return
        
        self._load_batches_by_family(family)
    
    def _load_batches_by_family(self, family):
        """Charge les batches d'une famille spécifique"""
        self.batch_combo.clear()
        self.batch_combo.addItem("Sélectionner un batch", None)
        
        if not self.current_project_name or not family or not self.database:
            return
        
        try:
            all_batches = self.database.get_all_batches(self.current_project_name)
            
            if not all_batches:
                self.batch_combo.addItem("Aucun batch", None)
                return
            
            batches = [b for b in all_batches if b.get('data', {}).get('batch_family', '') == family]
            
            if not batches:
                self.batch_combo.addItem("Aucun batch", None)
                return
            
            batches_sorted = sorted(batches, key=lambda x: x.get('batch_number', 0))
            
            for batch in batches_sorted:
                batch_num = batch.get('batch_number', 0)
                total_batches = batch.get('total_batches', 0)
                batch_data_content = batch.get('data', {})
                batch_name = batch_data_content.get('batch_name', f'Batch {batch_num}')
                combinations = batch_data_content.get('combinations', [])
                total_samples = sum(c.get('nb_samples', 0) for c in combinations)
                
                if total_batches > 0:
                    display_name = f"Batch {batch_num}/{total_batches} - {batch_name} ({total_samples} samples)"
                else:
                    display_name = f"Batch {batch_num} - {batch_name} ({total_samples} samples)"
                
                self.batch_combo.addItem(display_name, batch_num)
            
            logger.info(f"✅ {len(batches)} batch(es) chargé(s)")
        
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
    
    def _on_batch_changed(self, index):
        """Gère le changement de batch"""
        batch_number = self.batch_combo.currentData()
        logger.info(f"🔄 Batch RL sélectionné: {batch_number}")
        
        if batch_number is None:
            self.current_batch_number = None
            self.train_btn.setEnabled(False)
            return
        
        try:
            self.current_batch_number = batch_number
            batch_result = self.database.get_batch(self.current_project_name, batch_number)
            
            if batch_result:
                self.current_batch_data = batch_result
                batch_data = batch_result.get('data', {})
                combinations = batch_data.get('combinations', [])
                total_samples = sum(c.get('nb_samples', 0) for c in combinations)
                
                logger.info(f"✅ Batch chargé: {total_samples} samples disponibles")
                self.train_btn.setEnabled(True)
                
                # Afficher info dans les logs
                self.logs_text.append(f"✅ Batch sélectionné: {batch_data.get('batch_name', 'N/A')}")
                self.logs_text.append(f"📊 {len(combinations)} combinaisons, {total_samples} samples total")
        
        except Exception as e:
            logger.error(f"❌ Erreur chargement batch: {str(e)}")
            self.train_btn.setEnabled(False)
        

    def _on_browse_batch(self):
        """Ouvre un dialogue pour sélectionner un fichier de batch"""
        from PyQt5.QtWidgets import QFileDialog
        import json
        import os
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier de batch",
            "",
            "Fichiers Batch (*.json *.jsonl);;Fichiers JSON (*.json);;Fichiers JSONL (*.jsonl);;Tous les fichiers (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # Déterminer le type de fichier
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            if ext == '.jsonl':
                # Lire fichier JSONL (une ligne = un objet JSON)
                batch_data = {'combinations': []}
                total_samples = 0
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            # Chaque ligne du JSONL peut être une combinaison ou un sample
                            if isinstance(entry, dict):
                                # Si c'est déjà une combinaison avec samples
                                if 'samples' in entry:
                                    batch_data['combinations'].append(entry)
                                    total_samples += len(entry.get('samples', []))
                                else:
                                    # Sinon, traiter comme un sample individuel
                                    if not batch_data['combinations']:
                                        batch_data['combinations'].append({
                                            'samples': [],
                                            'nb_samples': 0
                                        })
                                    batch_data['combinations'][0]['samples'].append(entry)
                                    total_samples += 1
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️  Ligne {line_num} ignorée (JSON invalide): {str(e)}")
                
                # Mettre à jour le compteur de samples si nécessaire
                if batch_data['combinations']:
                    for combo in batch_data['combinations']:
                        combo['nb_samples'] = len(combo.get('samples', []))
                
                if total_samples == 0:
                    raise ValueError("Aucun sample valide trouvé dans le fichier JSONL")
                    
            else:
                # Lire fichier JSON classique
                with open(file_path, 'r', encoding='utf-8') as f:
                    batch_data = json.load(f)
                
                # Vérifier la structure du batch
                if not isinstance(batch_data, dict):
                    raise ValueError("Le fichier doit contenir un objet JSON valide")
            
            # Afficher le nom du fichier
            filename = os.path.basename(file_path)
            self.batch_file_input.setText(file_path)
            self.batch_file_input.setStyleSheet("""
                QLineEdit {
                    background-color: #E8F5E9;
                    border: 2px solid #4CAF50;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 11px;
                    color: #2E7D32;
                }
            """)
            
            # Désactiver les combos de sélection de batch
            self.batch_family_combo.setEnabled(False)
            self.batch_combo.setEnabled(False)
            
            # Charger le batch uploadé
            self.current_batch_data = {'data': batch_data}
            self.current_batch_number = -1  # Valeur spéciale pour batch uploadé
            
            # Compter les samples
            combinations = batch_data.get('combinations', [])
            total_samples = sum(c.get('nb_samples', 0) for c in combinations)
            
            # Activer le bouton d'entraînement
            self.train_btn.setEnabled(True)
            
            # Activer le bouton effacer
            self.clear_batch_btn.setEnabled(True)
            
            # Log dans l'interface
            self.logs_text.append(f"\n✅ Batch uploadé: {filename}")
            self.logs_text.append(f"📊 {len(combinations)} combinaisons, {total_samples} samples total")
            
            logger.info(f"✅ Batch uploadé: {filename} ({total_samples} samples)")
            
            # Message de confirmation
            QtWidgets.QMessageBox.information(
                self,
                "✅ Batch chargé",
                f"Le fichier '{filename}' a été chargé avec succès!\n\n"
                f"Combinaisons: {len(combinations)}\n"
                f"Samples: {total_samples}"
            )
            
        except json.JSONDecodeError as e:
            QtWidgets.QMessageBox.critical(
                self,
                "❌ Erreur",
                f"Le fichier n'est pas un JSON valide:\n{str(e)}"
            )
            logger.error(f"❌ Erreur lecture JSON: {str(e)}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "❌ Erreur",
                f"Impossible de charger le fichier:\n{str(e)}"
            )
            logger.error(f"❌ Erreur chargement batch: {str(e)}")

    def _on_clear_batch(self):
        """Efface le batch uploadé et réactive la sélection normale"""
        # Réinitialiser le champ de fichier
        self.batch_file_input.clear()
        self.batch_file_input.setPlaceholderText("Aucun fichier sélectionné")
        self.batch_file_input.setStyleSheet("""
            QLineEdit {
                background-color: #F5F5F5;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                color: #666;
            }
        """)
        
        # Réactiver les combos de sélection
        self.batch_family_combo.setEnabled(True)
        self.batch_combo.setEnabled(True)
        
        # Désactiver le bouton effacer
        self.clear_batch_btn.setEnabled(False)
        
        # Réinitialiser les données
        self.current_batch_data = None
        self.current_batch_number = None
        
        # Désactiver le bouton d'entraînement
        self.train_btn.setEnabled(False)
        
        # Log
        self.logs_text.append("\n🗑️  Batch uploadé effacé")
        logger.info("🗑️  Batch uploadé effacé")
    def _create_center_column(self):
        """Crée la colonne centrale - Environnement & Agent"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === TITRE ===
        title = QLabel("Environnement & Agent")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        layout.addWidget(title)
        
        # === SECTION ENVIRONNEMENT ===
        env_group = QGroupBox("Configuration Environnement")
        env_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        
        env_layout = QVBoxLayout(env_group)
        
        env_info = QLabel(
            "🌍 <b>Environnement d'entraînement</b><br><br>"
            "Définissez les paramètres de l'environnement dans lequel "
            "l'agent RL évoluera pendant l'entraînement."
        )
        env_info.setWordWrap(True)
        env_info.setStyleSheet("padding: 10px; background: #F0F8FF; border-radius: 4px;")
        env_layout.addWidget(env_info)
        
        # Placeholder pour configuration environnement
        env_placeholder = QLabel("⚙️ Configuration à venir...")
        env_placeholder.setAlignment(Qt.AlignCenter)
        env_placeholder.setStyleSheet(
            "color: #999; font-style: italic; padding: 30px; "
            "background: #FAFAFA; border: 2px dashed #E0E0E0; border-radius: 6px;"
        )
        env_layout.addWidget(env_placeholder)
        
        layout.addWidget(env_group)
        
        # === SECTION ARCHITECTURE AGENT ===
        agent_group = QGroupBox("Architecture de l'Agent")
        agent_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        
        agent_layout = QVBoxLayout(agent_group)
        
        agent_info = QLabel(
            "🤖 <b>Réseau de neurones</b><br><br>"
            "Configurez l'architecture du réseau de neurones "
            "qui servira de policy pour l'agent."
        )
        agent_info.setWordWrap(True)
        agent_info.setStyleSheet("padding: 10px; background: #F0F8FF; border-radius: 4px;")
        agent_layout.addWidget(agent_info)
        
        # Placeholder pour architecture
        agent_placeholder = QLabel("🧠 Configuration réseau à venir...")
        agent_placeholder.setAlignment(Qt.AlignCenter)
        agent_placeholder.setStyleSheet(
            "color: #999; font-style: italic; padding: 30px; "
            "background: #FAFAFA; border: 2px dashed #E0E0E0; border-radius: 6px;"
        )
        agent_layout.addWidget(agent_placeholder)
        
        layout.addWidget(agent_group)
        
        layout.addStretch()
        
        return column
        
    def _create_right_column(self):
        """Crée la colonne droite - Résultats & Visualisation"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === TITRE ===
        title_layout = QHBoxLayout()
        title = QLabel("Résultats d'Entraînement")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.PRIMARY_COLOR};")
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # === SECTION MÉTRIQUES ===
        metrics_group = QGroupBox("Métriques en Temps Réel")
        metrics_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        
        metrics_layout = QVBoxLayout(metrics_group)
        
        # Placeholder pour graphiques
        metrics_placeholder = QLabel(
            "📊 Graphiques de progression\n\n"
            "• Reward moyen par épisode\n"
            "• Loss de la policy\n"
            "• Taux d'exploration vs exploitation"
        )
        metrics_placeholder.setAlignment(Qt.AlignCenter)
        metrics_placeholder.setWordWrap(True)
        metrics_placeholder.setStyleSheet(
            "color: #666; padding: 40px; "
            "background: #FAFAFA; border: 2px dashed #E0E0E0; border-radius: 6px;"
        )
        metrics_layout.addWidget(metrics_placeholder)
        
        layout.addWidget(metrics_group)
        
        # === SECTION LOGS ===
        logs_group = QGroupBox("Logs d'Entraînement")
        logs_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            }}
        """)
        
        logs_layout = QVBoxLayout(logs_group)
        
        self.logs_text = QtWidgets.QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setPlaceholderText("Les logs d'entraînement apparaîtront ici...")
        self.logs_text.setMinimumHeight(150)
        self.logs_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background: #FAFAFA;
            }
        """)
        logs_layout.addWidget(self.logs_text)
        
        layout.addWidget(logs_group)
        
        layout.addStretch()
        
        return column
        
    def _create_actions(self):
        """Crée la barre d'actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        
        layout.addStretch()
        
        # Bouton Entraîner
        self.train_btn = GradientButton("🚀 Lancer l'Entraînement")
        self.train_btn.clicked.connect(self._on_train)
        self.train_btn.setMinimumWidth(200)
        layout.addWidget(self.train_btn)
        
        # Bouton Évaluer
        self.eval_btn = GradientButton("📊 Évaluer le Modèle")
        self.eval_btn.clicked.connect(self._on_evaluate)
        self.eval_btn.setEnabled(False)
        layout.addWidget(self.eval_btn)
        
        # Bouton Exporter
        self.export_btn = GradientButton("💾 Exporter")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
        return widget
        
    def _apply_combo_style(self, combo):
        """Applique le style aux combobox (identique à dataset_generation)"""
        # Importer le chemin SVG
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(current_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        svg_path = os.path.normpath(svg_path).replace('\\', '/')
        
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 35px;
                background: white;
                font-size: 10pt;
            }}
            QComboBox:hover {{
                border: 2px solid #E0E0E0;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #E0E0E0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 18px;
                height: 18px;
            }}
            QComboBox QAbstractItemView {{
                border: 2px solid {Theme.PRIMARY_COLOR};
                border-radius: 6px;
                background: white;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
                selection-color: white;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border: none;
                margin: 2px 4px;
                border-radius: 4px;
            }}
        """)
        
    def _apply_spinbox_style(self, spinbox):
        """Applique le style aux spinbox"""
        spinbox.setStyleSheet(f"""
            QSpinBox {{
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                font-size: 10pt;
            }}
            QSpinBox:hover {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
            QSpinBox:focus {{
                border: 2px solid {Theme.PRIMARY_COLOR};
            }}
        """)
        
    def _on_train(self):
        """Lance l'entraînement GRPO"""
        if not self.current_batch_number:
            QtWidgets.QMessageBox.warning(
                self,
                "⚠️ Batch requis",
                "Veuillez d'abord sélectionner un batch pour l'entraînement GRPO."
            )
            return
        
        # Récupérer les paramètres
        episodes = self.episodes_spin.value()
        lr = float(self.lr_combo.currentText())
        batch_size = self.batch_size_spin.value()
        
        # Récupérer les infos du batch
        batch_data = self.current_batch_data.get('data', {})
        batch_name = batch_data.get('batch_name', 'N/A')
        combinations = batch_data.get('combinations', [])
        
        # Calculer nombre total de samples
        total_samples = 0
        for combo in combinations:
            samples = combo.get('samples', [])
            total_samples += len(samples)
        
        if total_samples == 0:
            QtWidgets.QMessageBox.warning(
                self,
                "⚠️ Dataset vide",
                "Aucun sample trouvé dans ce batch."
            )
            return
        
        # Configuration GRPO
        config = GRPOConfig(
            model_name="openai/gpt-oss-20b",  # Modèle OSS 20B
            vllm_url="http://localhost:8000/v1",
            reward_api_url="http://localhost:8086",
            group_size=8,  # 8 réponses par prompt
            num_episodes=episodes,
            batch_size=batch_size,
            learning_rate=lr,
            temperature=0.8,
            domain="comptabilité"
        )
        
        # Message de confirmation
        msg = f"<b>🚀 Lancer l'entraînement GRPO ?</b><br><br>"
        msg += f"<b>Configuration :</b><br>"
        msg += f"• Projet : {self.current_project_name}<br>"
        msg += f"• Batch : {batch_name}<br>"
        msg += f"• Samples disponibles : {total_samples}<br>"
        msg += f"• Group size (G) : {config.group_size} réponses/prompt<br>"
        msg += f"• Episodes : {episodes}<br>"
        msg += f"• Learning Rate : {lr}<br>"
        msg += f"• Batch Size : {batch_size}<br><br>"
        msg += f"<b>Formule GRPO :</b><br>"
        msg += f"<code>A_g = (R_g - mean(R)) / std(R)</code><br><br>"
        msg += f"<small><i>L'entraînement peut prendre plusieurs minutes...<br>"
        msg += f"Génération de {total_samples * config.group_size} samples attendue</i></small>"
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "🤖 Entraînement GRPO",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Désactiver boutons
            self.train_btn.setEnabled(False)
            self.eval_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            
            # Clear logs
            self.logs_text.clear()
            
            # Créer et lancer le worker GRPO
            # Si batch uploadé (batch_number == -1), passer les données directement
            worker_batch_data = None
            if self.current_batch_number == -1:
                worker_batch_data = self.current_batch_data
            
            self.grpo_worker = GRPOWorker(
                project_name=self.current_project_name or "Projet Uploadé",
                batch_number=self.current_batch_number,
                config=config,
                database=self.database,
                batch_data=worker_batch_data,  # Passer les données si batch uploadé
                parent=self
            )
            
            # Connecter signaux
            self.grpo_worker.progress.connect(self._on_grpo_progress)
            self.grpo_worker.finished.connect(self._on_grpo_finished)
            self.grpo_worker.error.connect(self._on_grpo_error)
            self.grpo_worker.log.connect(self._on_grpo_log)
            self.grpo_worker.episode_complete.connect(self._on_grpo_episode_complete)
            self.grpo_worker.group_complete.connect(self._on_grpo_group_complete)
            
            # Démarrer
            self.grpo_worker.start()
            
            self.logs_text.append("="*60)
            self.logs_text.append("🚀 DÉMARRAGE ENTRAÎNEMENT GRPO")
            self.logs_text.append("="*60)
            self.logs_text.append(f"Modèle: {config.model_name}")
            self.logs_text.append(f"Formule: A_g = (R_g - mean(R)) / std(R)")
            self.logs_text.append("")
            
            # Émettre signal
            self.training_started.emit(self.current_project_name)

    def _on_grpo_progress(self, data: dict):
        """Callback progression GRPO"""
        progress_type = data.get("type")
        progress_data = data.get("data", {})

        if progress_type == "episode":
            episode = progress_data.get("episode", 0)
            mean_reward = progress_data.get("mean_reward", 0.0)
            self.logs_text.append(
                f"\n📊 Episode {episode}: Mean Reward = {mean_reward:.2f}"
            )

        elif progress_type == "group":
            group_id = progress_data.get("group_id", 0)
            mean_reward = progress_data.get("mean_reward", 0.0)
            diversity = progress_data.get("diversity", 0.0)
            self.logs_text.append(
                f"  Groupe {group_id}: Reward={mean_reward:.2f}, "
                f"Diversity={diversity:.2f}"
            )

    def _on_grpo_episode_complete(self, metrics: dict):
        """Callback fin d'épisode GRPO"""
        episode = metrics.get("episode", 0)
        mean_reward = metrics.get("mean_reward", 0.0)
        num_positive = metrics.get("num_positive_advantages", 0)
        num_negative = metrics.get("num_negative_advantages", 0)

        self.logs_text.append("")
        self.logs_text.append(f"✅ Episode {episode} terminé:")
        self.logs_text.append(f"   Mean Reward: {mean_reward:.2f}")
        self.logs_text.append(f"   Advantages: +{num_positive} / -{num_negative}")
    
    def _on_grpo_group_complete(self, metrics: dict):
        """Callback fin de groupe GRPO"""
        # Optionnel: mettre à jour une barre de progression
        pass

    def _on_grpo_finished(self, summary: dict):
        """Callback fin GRPO"""
        training = summary.get("training", {})
        metrics = summary.get("metrics", {})
        cache = summary.get("cache", {})

        self.logs_text.append("")
        self.logs_text.append("="*60)
        self.logs_text.append("🎉 ENTRAÎNEMENT GRPO TERMINÉ")
        self.logs_text.append("="*60)
        self.logs_text.append(f"Episodes: {training.get('episode', 0)}")
        self.logs_text.append(f"Groupes traités: {training.get('total_groups', 0)}")
        self.logs_text.append(f"Samples générés: {training.get('total_samples', 0)}")
        self.logs_text.append("")
        self.logs_text.append(f"📊 MÉTRIQUES FINALES:")
        self.logs_text.append(f"Mean Reward: {metrics.get('mean_reward', 0):.2f}")
        self.logs_text.append(f"Std Reward: {metrics.get('std_reward', 0):.2f}")
        self.logs_text.append(f"Min Reward: {metrics.get('min_reward', 0):.2f}")
        self.logs_text.append(f"Max Reward: {metrics.get('max_reward', 0):.2f}")

        if cache:
            self.logs_text.append("")
            self.logs_text.append(f"💾 Cache: {cache.get('cache_size', 0)} entrées")
            self.logs_text.append(f"Hit Rate: {cache.get('hit_rate', 0)*100:.1f}%")

        # Réactiver boutons
        self.train_btn.setEnabled(True)
        self.eval_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Notification
        QtWidgets.QMessageBox.information(
            self,
            "✅ Entraînement terminé",
            f"GRPO terminé avec succès !\n\n"
            f"Episodes: {training.get('episode', 0)}\n"
            f"Mean Reward: {metrics.get('mean_reward', 0):.2f}\n"
            f"Best Reward: {metrics.get('max_reward', 0):.2f}"
        )

        # Émettre signal
        self.training_completed.emit(self.current_project_name, summary)

    def _on_grpo_error(self, error: str):
        """Callback erreur GRPO"""
        self.logs_text.append("")
        self.logs_text.append("="*60)
        self.logs_text.append("❌ ERREUR")
        self.logs_text.append("="*60)
        self.logs_text.append(error)

        # Réactiver boutons
        self.train_btn.setEnabled(True)
        self.eval_btn.setEnabled(False)
        self.export_btn.setEnabled(False)

        QtWidgets.QMessageBox.critical(
            self,
            "❌ Erreur",
            f"Erreur durant l'entraînement GRPO:\n\n{error}"
        )

        # Émettre signal
        self.training_failed.emit(self.current_project_name, error)

    def _on_grpo_log(self, log_message: str):
        """Callback log GRPO"""
        self.logs_text.append(log_message)

        # Auto-scroll vers le bas
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_stop_training(self):
        """Arrête l'entraînement en cours"""
        if hasattr(self, 'grpo_worker') and self.grpo_worker.isRunning():
            reply = QtWidgets.QMessageBox.question(
                self,
                "⚠️ Arrêter l'entraînement ?",
                "Voulez-vous vraiment arrêter l'entraînement en cours ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self.grpo_worker.stop()
                self.logs_text.append("\n⚠️  Arrêt de l'entraînement demandé...")

    def _on_evaluate(self):
        """Évalue le modèle entraîné"""
        QtWidgets.QMessageBox.information(
            self,
            "📊 Évaluation",
            "Fonctionnalité à venir..."
        )
        
    def _on_export(self):
        """Exporte le modèle"""
        QtWidgets.QMessageBox.information(
            self,
            "💾 Export",
            "Fonctionnalité à venir..."
        )
        
    def set_conductor(self, conductor):
        """Définit le conductor"""
        self.conductor = conductor
        logger.info(f"🎼 Conductor défini pour RLPanel")
        
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        logger.info(f"💾 Database définie pour RLPanel")
        
        # Charger les projets
        if database:
            self._load_projects()
    
    def _load_projects(self):
        """Charge les projets disponibles"""
        if not self.database:
            return
        
        try:
            projects = self.database.get_all_projects()
            logger.info(f"📦 {len(projects) if projects else 0} projet(s) trouvé(s) pour RL")
            
            self.project_combo.clear()
            self.project_combo.addItem("Sélectionner un projet", None)
            
            for project in projects:
                if isinstance(project, dict):
                    project_name = project.get('name', project.get('nom', 'Sans nom'))
                    self.project_combo.addItem(project_name, project_name)
            
            logger.info(f"✅ {self.project_combo.count() - 1} projet(s) chargé(s) dans RLPanel")
        
        except Exception as e:
            logger.error(f"❌ Erreur chargement projets RL: {str(e)}")
        
    def refresh(self):
        """Rafraîchit les données"""
        logger.info("🔄 Refresh RLPanel")
        
    def update_language(self):
        """Met à jour la langue"""
        pass