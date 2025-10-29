# ide_panel.py - Panneau IDE pour intégration VS Code
import os
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QThread
import qtawesome as qta

from utils.logger import logger


class CodeIntegrationWorker(QThread):
    """Worker pour l'intégration du code dans le projet"""
    
    progress_update = pyqtSignal(str, int)
    integration_completed = pyqtSignal(bool, str, dict)
    
    def __init__(self, config, snippet_data):
        super().__init__()
        self.config = config
        self.snippet_data = snippet_data
        self.backup_path = None
        
    def run(self):
        """Exécute l'intégration du code"""
        try:
            self.progress_update.emit("📁 Analyse du projet source...", 10)
            
            # Validation du projet
            if not self._validate_project():
                self.integration_completed.emit(
                    False, 
                    "Le chemin du projet source est invalide", 
                    {}
                )
                return
            
            self.progress_update.emit("🔍 Identification du fichier cible...", 30)
            
            # Identification du fichier cible
            target_file = self._identify_target_file()
            if not target_file:
                self.integration_completed.emit(
                    False, 
                    "Impossible d'identifier le fichier cible", 
                    {}
                )
                return
            
            self.progress_update.emit("💾 Création de la sauvegarde...", 50)
            
            # Sauvegarde
            if not self._create_backup(target_file):
                self.integration_completed.emit(
                    False, 
                    "Échec de la création de la sauvegarde", 
                    {}
                )
                return
            
            self.progress_update.emit("✏️ Intégration du code...", 70)
            
            # Intégration selon le mode
            success, message = self._integrate_code(target_file)
            
            if not success:
                self._restore_backup(target_file)
                self.integration_completed.emit(False, message, {})
                return
            
            self.progress_update.emit("🎨 Application du formatage...", 85)
            
            # Formatage si activé
            if self.config.get('auto_format', False):
                self._apply_formatting(target_file)
            
            self.progress_update.emit("✅ Intégration terminée", 100)
            
            # Rapport
            report = {
                'file': str(target_file),
                'action': self.config['integration_mode'],
                'status': 'success',
                'backup': str(self.backup_path),
                'timestamp': datetime.now().isoformat()
            }
            
            self.integration_completed.emit(True, "Code intégré avec succès", report)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'intégration: {e}")
            self.integration_completed.emit(
                False, 
                f"Erreur: {str(e)}", 
                {}
            )
    
    def _validate_project(self):
        """Valide le chemin du projet"""
        project_path = Path(self.config['project_path'])
        return project_path.exists() and project_path.is_dir()
    
    def _identify_target_file(self):
        """Identifie le fichier cible dans le projet"""
        project_path = Path(self.config['project_path'])
        target_name = self.snippet_data.get('file', '')
        
        # Recherche du fichier
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if file == target_name or file.endswith(target_name):
                    return Path(root) / file
        
        # Si mode création, retourner le chemin du nouveau fichier
        if self.config['integration_mode'] == 'creation':
            return project_path / target_name
        
        return None
    
    def _create_backup(self, target_file):
        """Crée une sauvegarde du fichier"""
        if not target_file.exists():
            return True
        
        backup_dir = Path(self.config['project_path']) / '.liris_backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{target_file.name}.{timestamp}.bak"
        self.backup_path = backup_dir / backup_name
        
        try:
            shutil.copy2(target_file, self.backup_path)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    def _integrate_code(self, target_file):
        """Intègre le code selon le mode choisi"""
        mode = self.config['integration_mode']
        code = self.snippet_data.get('code', '')
        
        if mode == 'creation':
            return self._create_new_file(target_file, code)
        elif mode == 'ajout':
            return self._append_code(target_file, code)
        elif mode == 'remplacement':
            return self._replace_code(target_file, code)
        else:
            return False, f"Mode '{mode}' non supporté"
    
    def _create_new_file(self, target_file, code):
        """Crée un nouveau fichier"""
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(code)
            return True, "Fichier créé avec succès"
        except Exception as e:
            return False, f"Erreur lors de la création: {str(e)}"
    
    def _append_code(self, target_file, code):
        """Ajoute du code à un fichier existant"""
        try:
            if not target_file.exists():
                return self._create_new_file(target_file, code)
            
            with open(target_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # Ajouter le code à la fin avec séparation
            new_content = existing_content.rstrip() + "\n\n\n" + code
            
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True, "Code ajouté avec succès"
        except Exception as e:
            return False, f"Erreur lors de l'ajout: {str(e)}"
    
    def _replace_code(self, target_file, code):
        """Remplace du code dans un fichier"""
        try:
            target = self.snippet_data.get('target', '')
            
            if not target_file.exists():
                return self._create_new_file(target_file, code)
            
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Si pas de cible spécifique, remplacer tout le fichier
            if not target:
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                return True, "Fichier remplacé avec succès"
            
            # Rechercher et remplacer la section cible
            if target in content:
                # Logique simplifiée: remplacer la première occurrence
                new_content = content.replace(target, code, 1)
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                return True, "Code remplacé avec succès"
            else:
                return False, f"Cible '{target}' non trouvée dans le fichier"
            
        except Exception as e:
            return False, f"Erreur lors du remplacement: {str(e)}"
    
    def _apply_formatting(self, target_file):
        """Applique le formatage automatique"""
        language = self.config.get('language', '').lower()
        
        formatters = {
            'python': ['black', str(target_file)],
            'javascript': ['prettier', '--write', str(target_file)],
            'typescript': ['prettier', '--write', str(target_file)],
        }
        
        formatter_cmd = formatters.get(language)
        
        if formatter_cmd:
            try:
                subprocess.run(formatter_cmd, check=False, capture_output=True)
            except Exception as e:
                logger.warning(f"Formatage échoué: {e}")
    
    def _restore_backup(self, target_file):
        """Restaure le fichier depuis la sauvegarde"""
        if self.backup_path and self.backup_path.exists():
            try:
                shutil.copy2(self.backup_path, target_file)
                logger.info("Sauvegarde restaurée après erreur")
            except Exception as e:
                logger.error(f"Erreur lors de la restauration: {e}")


class IDEPanel(QtWidgets.QWidget):
    """Panneau IDE pour l'intégration de code dans VS Code"""
    
    integration_started = pyqtSignal()
    integration_completed = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_snippets = []
        self.integration_worker = None
        
        # Configuration par défaut
        self.config = {
            'project_path': '',
            'ide_path': 'code',  # Commande VS Code par défaut
            'language': 'python',
            'integration_mode': 'ajout',
            'auto_format': False,
            'open_mode': 'ouvrir_fichier'
        }
        
        self._init_ui()
        self._load_config()
        
    def _init_ui(self):
        """Initialise l'interface"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # En-tête
        header_layout = QtWidgets.QHBoxLayout()
        
        title_icon = QtWidgets.QLabel()
        title_icon.setPixmap(qta.icon('fa5s.code', color='#666').pixmap(24, 24))
        header_layout.addWidget(title_icon)
        
        title_label = QtWidgets.QLabel("Intégration IDE")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; padding: 0 8px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # Zone de configuration (gauche) et prévisualisation (droite)
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(15)
        
        # === COLONNE GAUCHE: Configuration ===
        config_group = QtWidgets.QGroupBox("⚙️ Configuration")
        config_group.setStyleSheet(self._get_groupbox_style())
        config_layout = QtWidgets.QVBoxLayout(config_group)
        config_layout.setSpacing(15)
        
        # Projet source
        project_label = QtWidgets.QLabel("📁 Chemin du projet source")
        project_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(project_label)
        
        project_row = QtWidgets.QHBoxLayout()
        self.project_path_edit = QtWidgets.QLineEdit()
        self.project_path_edit.setPlaceholderText("C:/Users/mon_projet/...")
        project_row.addWidget(self.project_path_edit)
        
        browse_btn = QtWidgets.QPushButton()
        browse_btn.setIcon(qta.icon('fa5s.folder-open', color='white'))
        browse_btn.setToolTip("Parcourir")
        browse_btn.clicked.connect(self._browse_project)
        browse_btn.setFixedWidth(40)
        project_row.addWidget(browse_btn)
        config_layout.addLayout(project_row)
        
        # IDE
        ide_label = QtWidgets.QLabel("💻 Chemin de l'IDE (VS Code)")
        ide_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(ide_label)
        
        self.ide_path_edit = QtWidgets.QLineEdit()
        self.ide_path_edit.setPlaceholderText("code (ou chemin complet)")
        self.ide_path_edit.setText("code")
        config_layout.addWidget(self.ide_path_edit)
        
        # Langage
        language_label = QtWidgets.QLabel("🔤 Langage / Framework")
        language_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(language_label)
        
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItems(['Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'HTML', 'CSS'])
        config_layout.addWidget(self.language_combo)
        
        # Mode d'intégration
        mode_label = QtWidgets.QLabel("🔧 Mode d'intégration")
        mode_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(mode_label)
        
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("➕ Ajout", "ajout")
        self.mode_combo.addItem("🔄 Remplacement", "remplacement")
        self.mode_combo.addItem("📄 Création de fichier", "creation")
        config_layout.addWidget(self.mode_combo)
        
        # Options
        options_label = QtWidgets.QLabel("⚡ Options")
        options_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(options_label)
        
        self.format_checkbox = QtWidgets.QCheckBox("Formatage automatique")
        config_layout.addWidget(self.format_checkbox)
        
        # Mode d'ouverture
        open_label = QtWidgets.QLabel("🚀 Après export")
        open_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        config_layout.addWidget(open_label)
        
        self.open_combo = QtWidgets.QComboBox()
        self.open_combo.addItem("📂 Ouvrir le fichier", "ouvrir_fichier")
        self.open_combo.addItem("📁 Ouvrir le projet", "ouvrir_projet")
        self.open_combo.addItem("❌ Ne rien ouvrir", "ne_rien_ouvrir")
        config_layout.addWidget(self.open_combo)
        
        config_layout.addStretch()
        
        # Bouton d'intégration
        self.integrate_btn = QtWidgets.QPushButton()
        self.integrate_btn.setIcon(qta.icon('fa5s.rocket', color='white'))
        self.integrate_btn.setText("  Intégrer le code")
        self.integrate_btn.clicked.connect(self._integrate_code)
        self.integrate_btn.setEnabled(False)
        self.integrate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #D35A4A;
            }}
            QPushButton:disabled {{
                background-color: #e0e0e0;
                color: #424242;
            }}
        """)
        config_layout.addWidget(self.integrate_btn)
        
        content_layout.addWidget(config_group, 4)
        
        # === COLONNE DROITE: Prévisualisation ===
        preview_group = QtWidgets.QGroupBox("👁️ Prévisualisation")
        preview_group.setStyleSheet(self._get_groupbox_style())
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        
        self.preview_text = QtWidgets.QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Sélectionnez un snippet dans le panneau Coding pour le prévisualiser ici...")
        self.preview_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        content_layout.addWidget(preview_group, 6)
        
        main_layout.addLayout(content_layout)
        
        # Zone de statut et progression
        status_layout = QtWidgets.QVBoxLayout()
        
        status_header = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel()
        status_icon.setPixmap(qta.icon('fa5s.info-circle', color='#666').pixmap(16, 16))
        status_header.addWidget(status_icon)
        
        self.status_label = QtWidgets.QLabel("Prêt")
        self.status_label.setStyleSheet("color: #333; font-weight: bold; font-size: 11px;")
        status_header.addWidget(self.status_label)
        status_header.addStretch()
        status_layout.addLayout(status_header)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(18)
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(status_layout)
        
        # Historique des intégrations
        history_group = QtWidgets.QGroupBox("📜 Historique des intégrations")
        history_group.setStyleSheet(self._get_groupbox_style())
        history_layout = QtWidgets.QVBoxLayout(history_group)
        
        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(['Horodatage', 'Fichier', 'Action', 'Statut', 'Sauvegarde'])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        history_layout.addWidget(self.history_table)
        
        main_layout.addWidget(history_group)
    
    def _get_groupbox_style(self):
        """Retourne le style des groupbox"""
        return """
            QGroupBox {
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                margin-top: 1.2em;
                padding: 15px;
                background-color: #FFFFFF;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #333333;
            }
        """
    
    def _browse_project(self):
        """Ouvre un dialogue pour sélectionner le projet"""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier du projet",
            self.project_path_edit.text() or os.path.expanduser("~")
        )
        
        if directory:
            self.project_path_edit.setText(directory)
            self._save_config()
    
    def set_snippet(self, snippet_data):
        """Définit le snippet à intégrer"""
        self.current_snippets = [snippet_data]
        
        # Prévisualisation
        code = snippet_data.get('code', '')
        self.preview_text.setPlainText(code)
        
        # Activer le bouton
        self.integrate_btn.setEnabled(True)
        
        self.update_status("Snippet chargé, prêt à intégrer")
    
    def _integrate_code(self):
        """Lance l'intégration du code"""
        if not self.current_snippets:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun snippet",
                "Aucun snippet sélectionné pour l'intégration."
            )
            return
        
        # Mise à jour de la config
        self.config['project_path'] = self.project_path_edit.text()
        self.config['ide_path'] = self.ide_path_edit.text()
        self.config['language'] = self.language_combo.currentText().lower()
        self.config['integration_mode'] = self.mode_combo.currentData()
        self.config['auto_format'] = self.format_checkbox.isChecked()
        self.config['open_mode'] = self.open_combo.currentData()
        
        # Validation
        if not self.config['project_path']:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration incomplète",
                "Veuillez spécifier le chemin du projet source."
            )
            return
        
        self._save_config()
        
        # Désactiver les contrôles
        self.integrate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Lancer le worker
        self.integration_worker = CodeIntegrationWorker(
            self.config,
            self.current_snippets[0]
        )
        
        self.integration_worker.progress_update.connect(self._on_progress_update)
        self.integration_worker.integration_completed.connect(self._on_integration_completed)
        
        self.integration_started.emit()
        self.integration_worker.start()
    
    def _on_progress_update(self, message, progress):
        """Mise à jour de la progression"""
        self.update_status(message)
        self.progress_bar.setValue(progress)
    
    def _on_integration_completed(self, success, message, report):
        """Intégration terminée"""
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.integrate_btn.setEnabled(True)
        
        if success:
            self.update_status(f"✅ {message}")
            self._add_to_history(report)
            
            QtWidgets.QMessageBox.information(
                self,
                "Intégration réussie",
                f"{message}\n\nFichier: {report['file']}"
            )
            
            # Ouvrir dans VS Code si demandé
            self._open_in_vscode(report['file'])
            
        else:
            self.update_status(f"❌ {message}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'intégration",
                f"L'intégration a échoué:\n\n{message}"
            )
        
        self.integration_completed.emit(success, message)
    
    def _open_in_vscode(self, file_path):
        """Ouvre le fichier ou projet dans VS Code"""
        open_mode = self.config.get('open_mode', 'ne_rien_ouvrir')
        
        if open_mode == 'ne_rien_ouvrir':
            return
        
        ide_cmd = self.config.get('ide_path', 'code')
        
        try:
            if open_mode == 'ouvrir_fichier':
                subprocess.Popen([ide_cmd, file_path])
            elif open_mode == 'ouvrir_projet':
                subprocess.Popen([ide_cmd, self.config['project_path']])
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture de VS Code: {e}")
    
    def _add_to_history(self, report):
        """Ajoute une entrée à l'historique"""
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        timestamp = datetime.fromisoformat(report['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        self.history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(timestamp))
        self.history_table.setItem(row, 1, QtWidgets.QTableWidgetItem(os.path.basename(report['file'])))
        self.history_table.setItem(row, 2, QtWidgets.QTableWidgetItem(report['action']))
        self.history_table.setItem(row, 3, QtWidgets.QTableWidgetItem('✅ ' + report['status']))
        self.history_table.setItem(row, 4, QtWidgets.QTableWidgetItem(report.get('backup', 'N/A')))
    
    def update_status(self, message):
        """Met à jour le statut"""
        self.status_label.setText(message)
        logger.info(f"IDE Panel: {message}")
    
    def _load_config(self):
        """Charge la configuration depuis un fichier"""
        config_file = Path.home() / '.liris' / 'ide_config.json'
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                
                # Appliquer à l'interface
                self.project_path_edit.setText(self.config.get('project_path', ''))
                self.ide_path_edit.setText(self.config.get('ide_path', 'code'))
                
                lang = self.config.get('language', 'python')
                index = self.language_combo.findText(lang.capitalize())
                if index >= 0:
                    self.language_combo.setCurrentIndex(index)
                
                mode = self.config.get('integration_mode', 'ajout')
                for i in range(self.mode_combo.count()):
                    if self.mode_combo.itemData(i) == mode:
                        self.mode_combo.setCurrentIndex(i)
                        break
                
                self.format_checkbox.setChecked(self.config.get('auto_format', False))
                
                open_mode = self.config.get('open_mode', 'ouvrir_fichier')
                for i in range(self.open_combo.count()):
                    if self.open_combo.itemData(i) == open_mode:
                        self.open_combo.setCurrentIndex(i)
                        break
                
                logger.info("Configuration IDE chargée")
            except Exception as e:
                logger.error(f"Erreur lors du chargement de la config: {e}")
    
    def _save_config(self):
        """Sauvegarde la configuration"""
        config_dir = Path.home() / '.liris'
        config_dir.mkdir(exist_ok=True)
        
        config_file = config_dir / 'ide_config.json'
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration IDE sauvegardée")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la config: {e}")
    
    def refresh(self):
        """Rafraîchit le panneau"""
        self._load_config()