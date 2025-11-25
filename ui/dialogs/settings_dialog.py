from PyQt5 import QtWidgets, QtCore, QtGui
from utils.logger import logger
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox, QLabel, QLineEdit
from PyQt5.QtWidgets import QPushButton, QComboBox, QSpinBox, QTimeEdit, QCheckBox, QListWidget, QMessageBox
import os
import json


class SettingsDialog(QDialog):
    """
    Dialogue des paramètres de l'application
    """

    def __init__(self, config_provider, parent=None):
        super().__init__(parent)

        self.config_provider = config_provider
        self.setWindowTitle("Paramètres - Liris")
        self.setMinimumSize(800, 600)

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        layout = QVBoxLayout(self)

        # Onglets
        self.tab_widget = QTabWidget()

        # Onglet Plateformes IA
        self.platforms_tab = self._create_platforms_tab()
        self.tab_widget.addTab(self.platforms_tab, "Plateformes IA")

        # Onglet Paramètres généraux
        self.general_tab = self._create_general_tab()
        self.tab_widget.addTab(self.general_tab, "Général")

        # Onglet Export/Import
        self.import_export_tab = self._create_import_export_tab()
        self.tab_widget.addTab(self.import_export_tab, "Import/Export")

        # Onglet À propos
        self.about_tab = self._create_about_tab()
        self.tab_widget.addTab(self.about_tab, "À propos")

        layout.addWidget(self.tab_widget)

        # Boutons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Appliquer")
        self.apply_button.clicked.connect(self._on_apply)
        button_layout.addWidget(self.apply_button)

        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self._on_ok)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_platforms_tab(self):
        """Crée l'onglet des plateformes IA"""
        tab = QtWidgets.QWidget()
        layout = QVBoxLayout(tab)

        # Liste des plateformes
        platform_layout = QHBoxLayout()

        # Liste à gauche
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Plateformes disponibles:"))

        self.platform_list = QListWidget()
        self.platform_list.itemClicked.connect(self._on_platform_selected)
        left_layout.addWidget(self.platform_list)

        # Boutons d'ajout/suppression
        platform_buttons = QHBoxLayout()
        self.add_platform_button = QPushButton("Ajouter")
        self.add_platform_button.clicked.connect(self._on_add_platform)
        platform_buttons.addWidget(self.add_platform_button)

        self.remove_platform_button = QPushButton("Supprimer")
        self.remove_platform_button.clicked.connect(self._on_remove_platform)
        platform_buttons.addWidget(self.remove_platform_button)
        platform_buttons.addStretch()

        left_layout.addLayout(platform_buttons)
        platform_layout.addLayout(left_layout)

        # Configuration à droite
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Configuration de la plateforme:"))

        # Groupe de configuration
        config_group = QGroupBox()
        config_layout = QVBoxLayout()

        # Nom
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.platform_name_input = QLineEdit()
        name_layout.addWidget(self.platform_name_input)
        config_layout.addLayout(name_layout)

        # Limites
        limits_group = QGroupBox("Limites d'utilisation")
        limits_layout = QVBoxLayout()

        # Prompts par jour
        prompts_layout = QHBoxLayout()
        prompts_layout.addWidget(QLabel("Prompts par jour:"))
        self.prompts_limit = QSpinBox()
        self.prompts_limit.setRange(1, 10000)
        self.prompts_limit.setValue(100)
        prompts_layout.addWidget(self.prompts_limit)
        limits_layout.addLayout(prompts_layout)

        # Heure de réinitialisation
        reset_layout = QHBoxLayout()
        reset_layout.addWidget(QLabel("Heure de réinitialisation:"))
        self.reset_time = QTimeEdit()
        self.reset_time.setTime(QtCore.QTime(0, 0))
        self.reset_time.setDisplayFormat("HH:mm:ss")
        reset_layout.addWidget(self.reset_time)
        limits_layout.addLayout(reset_layout)

        # Cooldown
        cooldown_layout = QHBoxLayout()
        cooldown_layout.addWidget(QLabel("Cooldown (secondes):"))
        self.cooldown_value = QSpinBox()
        self.cooldown_value.setRange(0, 300)
        self.cooldown_value.setValue(60)
        cooldown_layout.addWidget(self.cooldown_value)
        limits_layout.addLayout(cooldown_layout)

        limits_group.setLayout(limits_layout)
        config_layout.addWidget(limits_group)

        config_group.setLayout(config_layout)
        right_layout.addWidget(config_group)

        platform_layout.addLayout(right_layout)
        layout.addLayout(platform_layout)

        return tab

    def _create_general_tab(self):
        """Crée l'onglet des paramètres généraux"""
        tab = QtWidgets.QWidget()
        layout = QVBoxLayout(tab)

        # Langue
        lang_group = QGroupBox("Langue")
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Langue:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Français", "English"])
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        # Logging
        log_group = QGroupBox("Journalisation")
        log_layout = QVBoxLayout()

        # Niveau de log
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("Niveau de log:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        log_level_layout.addWidget(self.log_level_combo)
        log_level_layout.addStretch()
        log_layout.addLayout(log_level_layout)

        # Répertoire des logs
        log_dir_layout = QHBoxLayout()
        log_dir_layout.addWidget(QLabel("Répertoire des logs:"))
        self.log_dir_input = QLineEdit()
        self.log_dir_input.setReadOnly(True)
        log_dir_layout.addWidget(self.log_dir_input)

        browse_log_button = QPushButton("Parcourir")
        browse_log_button.clicked.connect(self._on_browse_log_dir)
        log_dir_layout.addWidget(browse_log_button)

        log_layout.addLayout(log_dir_layout)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Base de données
        db_group = QGroupBox("Base de données")
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Fichier DB:"))
        self.db_file_input = QLineEdit()
        self.db_file_input.setReadOnly(True)
        db_layout.addWidget(self.db_file_input)

        browse_db_button = QPushButton("Parcourir")
        browse_db_button.clicked.connect(self._on_browse_db_file)
        db_layout.addWidget(browse_db_button)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        layout.addStretch()
        return tab

    def _create_import_export_tab(self):
        """Crée l'onglet Import/Export"""
        tab = QtWidgets.QWidget()
        layout = QVBoxLayout(tab)

        # Export des paramètres
        export_group = QGroupBox("Exporter les paramètres")
        export_layout = QVBoxLayout()

        export_button = QPushButton("Exporter la configuration")
        export_button.clicked.connect(self._on_export_config)
        export_layout.addWidget(export_button)

        export_all_button = QPushButton("Exporter tout (avec profils)")
        export_all_button.clicked.connect(self._on_export_all)
        export_layout.addWidget(export_all_button)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Import des paramètres
        import_group = QGroupBox("Importer les paramètres")
        import_layout = QVBoxLayout()

        import_button = QPushButton("Importer la configuration")
        import_button.clicked.connect(self._on_import_config)
        import_layout.addWidget(import_button)

        import_group.setLayout(import_layout)
        layout.addWidget(import_group)

        layout.addStretch()
        return tab

    def _create_about_tab(self):
        """Crée l'onglet À propos"""
        tab = QtWidgets.QWidget()
        layout = QVBoxLayout(tab)

        # Logo et titre
        logo_label = QLabel()
        logo_label.setText("<h1>Liris</h1>")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # Description
        desc_text = """
        <p>Liris est une plateforme collaborative d'IA permettant de travailler
        avec plusieurs modèles d'intelligence artificielle de manière comparative
        et efficace.</p>

        <p>Développé avec PyQt5 et Python.</p>

        <p>© 2023 - Tous droits réservés</p>
        """
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)

        layout.addStretch()
        return tab

    def _load_settings(self):
        """Charge les paramètres actuels"""
        try:
            # Charger les profils
            self._load_platforms()

            # Charger les paramètres généraux
            db_config = self.config_provider.get_database_config()
            if db_config and 'path' in db_config:
                self.db_file_input.setText(db_config['path'])

            # Charger le répertoire des logs
            log_dir = os.path.join(os.path.dirname(self.config_provider.config_dir), "logs")
            self.log_dir_input.setText(log_dir)

        except Exception as e:
            logger.error(f"Erreur lors du chargement des données du projet: {str(e)}")

    def _load_platforms(self):
        """Charge la liste des plateformes"""
        self.platform_list.clear()
        profiles = self.config_provider.get_profiles()

        for name in profiles.keys():
            self.platform_list.addItem(name)

        if self.platform_list.count() > 0:
            self.platform_list.setCurrentRow(0)
            self._on_platform_selected()

    def _on_platform_selected(self):
        """Gère la sélection d'une plateforme"""
        current_item = self.platform_list.currentItem()
        if current_item:
            platform_name = current_item.text()
            profiles = self.config_provider.get_profiles()
            platform = profiles.get(platform_name)

            if platform:
                # Charger la configuration
                self.platform_name_input.setText(platform.get('name', ''))

                limits = platform.get('limits', {})
                self.prompts_limit.setValue(limits.get('prompts_per_day', 100))

                reset_time = limits.get('reset_time', '00:00:00')
                time_parts = reset_time.split(':')
                if len(time_parts) == 3:
                    hour, minute, second = map(int, time_parts)
                    self.reset_time.setTime(QtCore.QTime(hour, minute, second))

                self.cooldown_value.setValue(limits.get('cooldown_period', 60))

    def _on_add_platform(self):
        """Ajoute une nouvelle plateforme"""
        dialog = AddPlatformDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name = dialog.get_platform_name()
            if name:
                # Créer un profil basique
                profile = {
                    'name': name,
                    'interface': {},
                    'limits': {
                        'prompts_per_day': 100,
                        'reset_time': '00:00:00',
                        'cooldown_period': 60
                    },
                    'error_detection': {
                        'patterns': []
                    }
                }

                # Sauvegarder le profil
                self.config_provider.save_profile(name, profile)

                # Recharger la liste
                self._load_platforms()

    def _on_remove_platform(self):
        """Supprime une plateforme"""
        current_item = self.platform_list.currentItem()
        if current_item:
            platform_name = current_item.text()

            reply = QMessageBox.question(
                self,
                "Confirmation",
                f"Êtes-vous sûr de vouloir supprimer la plateforme '{platform_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # Supprimer le fichier de profil
                profile_path = os.path.join(self.config_provider.profiles_dir, f"{platform_name}.json")
                if os.path.exists(profile_path):
                    os.remove(profile_path)

                # Recharger la liste
                self._load_platforms()

    def _on_browse_log_dir(self):
        """Ouvre un dialogue pour choisir le répertoire des logs"""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choisir le répertoire des logs",
            self.log_dir_input.text()
        )

        if dir_path:
            self.log_dir_input.setText(dir_path)

    def _on_browse_db_file(self):
        """Ouvre un dialogue pour choisir le fichier de base de données"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Choisir le fichier de base de données",
            self.db_file_input.text(),
            "Database Files (*.db);;All Files (*)"
        )

        if file_path:
            self.db_file_input.setText(file_path)

    def _on_export_config(self):
        """Exporte la configuration"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter la configuration",
            "liris_config.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                config = {
                    'database': {'path': self.db_file_input.text()},
                    'logging': {
                        'level': self.log_level_combo.currentText(),
                        'directory': self.log_dir_input.text()
                    },
                    'language': self.language_combo.currentText()
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                QMessageBox.information(self, "Export", "Configuration exportée avec succès")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'exportation: {str(e)}")

    def _on_export_all(self):
        """Exporte toute la configuration incluant les profils"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter toute la configuration",
            "liris_full_config.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                config = {
                    'database': {'path': self.db_file_input.text()},
                    'logging': {
                        'level': self.log_level_combo.currentText(),
                        'directory': self.log_dir_input.text()
                    },
                    'language': self.language_combo.currentText(),
                    'profiles': self.config_provider.get_profiles()
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                QMessageBox.information(self, "Export", "Configuration complète exportée avec succès")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'exportation: {str(e)}")

    def _on_import_config(self):
        """Importe une configuration"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Importer une configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Appliquer la configuration
                if 'database' in config and 'path' in config['database']:
                    self.db_file_input.setText(config['database']['path'])

                if 'logging' in config:
                    if 'level' in config['logging']:
                        self.log_level_combo.setCurrentText(config['logging']['level'])
                    if 'directory' in config['logging']:
                        self.log_dir_input.setText(config['logging']['directory'])

                if 'language' in config:
                    self.language_combo.setCurrentText(config['language'])

                # Importer les profils si présents
                if 'profiles' in config:
                    for name, profile in config['profiles'].items():
                        self.config_provider.save_profile(name, profile)
                    self._load_platforms()

                QMessageBox.information(self, "Import", "Configuration importée avec succès")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'importation: {str(e)}")

    def _on_apply(self):
        """Applique les changements"""
        self._save_settings()

    def _on_ok(self):
        """Applique et ferme"""
        self._save_settings()
        self.accept()

    def _save_settings(self):
        """Sauvegarde les paramètres"""
        try:
            # Sauvegarder la plateforme sélectionnée
            current_item = self.platform_list.currentItem()
            if current_item:
                platform_name = current_item.text()
                profiles = self.config_provider.get_profiles()

                if platform_name in profiles:
                    platform = profiles[platform_name]

                    # Mettre à jour les limites
                    platform['limits'] = {
                        'prompts_per_day': self.prompts_limit.value(),
                        'reset_time': self.reset_time.time().toString("HH:mm:ss"),
                        'cooldown_period': self.cooldown_value.value()
                    }

                    # Sauvegarder
                    self.config_provider.save_profile(platform_name, platform)

            QMessageBox.information(self, "Paramètres", "Paramètres sauvegardés avec succès")

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")


class AddPlatformDialog(QDialog):
    """
    Dialogue pour ajouter une nouvelle plateforme
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Ajouter une plateforme")
        self.setMinimumWidth(300)

        self._init_ui()

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        layout = QVBoxLayout(self)

        # Nom de la plateforme
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.name_input = QLineEdit()
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Boutons
        button_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_platform_name(self):
        """Retourne le nom de la plateforme"""
        return self.name_input.text().strip()