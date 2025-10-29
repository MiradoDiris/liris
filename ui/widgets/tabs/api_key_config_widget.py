import os
import json
import keyring
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from utils.api_tester import ApiTester

from utils.logger import logger


class ApiTestThread(QThread):
    """Thread pour tester la clé API sans bloquer l'interface"""
    
    test_complete = pyqtSignal(dict)  # {success, message, details}
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(self, platform_name, api_config, conductor):
        super().__init__()
        self.platform_name = platform_name
        self.api_config = api_config
        self.conductor = conductor
    
    def run(self):
        """Exécute le test de la clé API"""
        try:
            self.log_message.emit(f"🔍 Démarrage du test pour {self.platform_name}...", "info")
            
            # Vérification 1: Présence de la clé API
            api_key = self.api_config.get('api_key', '')
            if not api_key:
                self.log_message.emit("❌ Aucune clé API fournie", "error")
                self.test_complete.emit({
                    'success': False,
                    'message': 'Clé API manquante',
                    'details': 'Veuillez saisir une clé API avant de tester'
                })
                return
            
            self.log_message.emit(f"✅ Clé API présente ({len(api_key)} caractères)", "info")
            
            # Vérification 2: Format de la clé
            if len(api_key) < 10:
                self.log_message.emit("⚠️ Clé API trop courte", "warning")
            
            # Vérification 3: Présence du modèle
            model = self.api_config.get('model', '')
            if model:
                self.log_message.emit(f"✅ Modèle configuré: {model}", "info")
            else:
                self.log_message.emit("⚠️ Aucun modèle spécifié", "warning")
            
            # Vérification 4: Configuration complète
            config_summary = {
                'base_url': self.api_config.get('base_url', 'Par défaut'),
                'max_tokens': self.api_config.get('max_tokens', 2000),
                'timeout': self.api_config.get('timeout', 60)
            }
            self.log_message.emit(f"📋 Config: {json.dumps(config_summary, indent=2)}", "debug")
            
            # Vérification 5: Test keyring (lecture/écriture)
            self.log_message.emit("🔐 Vérification du trousseau système...", "info")
            try:
                test_key = f"{self.platform_name}_test_temp"
                keyring.set_password("AI_Conductor_TEST", test_key, "test_value")
                stored = keyring.get_password("AI_Conductor_TEST", test_key)
                keyring.delete_password("AI_Conductor_TEST", test_key)
                
                if stored == "test_value":
                    self.log_message.emit("✅ Trousseau système fonctionnel", "info")
                else:
                    self.log_message.emit("⚠️ Problème avec le trousseau système", "warning")
            except Exception as e:
                self.log_message.emit(f"❌ Erreur trousseau: {str(e)}", "error")
            
            # Vérification 6: Test API réel avec ApiTester
            self.log_message.emit("🌐 Test de connexion à l'API...", "info")
            
            # UTILISATION DU NOUVEAU ApiTester
            result = ApiTester.test_api_key(self.platform_name, self.api_config)
            
            if result.get('success'):
                self.log_message.emit("✅ Connexion API réussie", "success")
                details = result.get('details', {})
                
                # Afficher les détails de la réponse
                if details:
                    self.log_message.emit(f"📊 Détails: {json.dumps(details, indent=2, ensure_ascii=False)}", "debug")
                
                self.test_complete.emit({
                    'success': True,
                    'message': 'Test réussi',
                    'details': details.get('message', 'API fonctionnelle')
                })
            else:
                error_msg = result.get('error', 'Erreur inconnue')
                self.log_message.emit(f"❌ Échec API: {error_msg}", "error")
                
                # Diagnostics supplémentaires
                if 'authentication' in error_msg.lower() or 'unauthorized' in error_msg.lower() or '401' in error_msg:
                    self.log_message.emit("💡 Conseil: Vérifiez que votre clé API est valide", "info")
                elif 'network' in error_msg.lower() or 'timeout' in error_msg.lower() or 'connexion' in error_msg.lower():
                    self.log_message.emit("💡 Conseil: Vérifiez votre connexion internet", "info")
                elif '429' in error_msg:
                    self.log_message.emit("💡 Conseil: Attendez quelques instants avant de réessayer", "info")
                
                self.test_complete.emit({
                    'success': False,
                    'message': 'Test échoué',
                    'details': error_msg
                })
        
        except Exception as e:
            self.log_message.emit(f"❌ Erreur inattendue: {str(e)}", "error")
            import traceback
            self.log_message.emit(f"🔍 Traceback:\n{traceback.format_exc()}", "debug")
            
            self.test_complete.emit({
                'success': False,
                'message': 'Erreur de test',
                'details': str(e)
            })


class ApiKeyConfigWidget(QtWidgets.QWidget):
    """Widget de configuration des clés API pour les plateformes d'IA"""

    # Signaux
    api_key_saved = pyqtSignal(str, dict)
    api_key_deleted = pyqtSignal(str)
    api_key_tested = pyqtSignal(str, bool, str)

    # Nom du service pour keyring
    KEYRING_SERVICE = "AI_Conductor"

    # Plateformes disponibles
    PLATFORMS = ["ChatGPT", "Claude", "Gemini", "Grok", "DeepSeek"]

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.key_visible = False
        self.test_thread = None

        self._init_ui()
        self._populate_platforms()
        logger.info("Widget de configuration des clés API initialisé avec console de diagnostic")

    def _load_icon(self, icon_path):
        """Charge une icône SVG"""
        if os.path.exists(icon_path):
            return QtGui.QIcon(icon_path)
        return QtGui.QIcon()

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Titre et description
        title_label = QtWidgets.QLabel("Configuration des Clés API")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title_label)

        description = QtWidgets.QLabel(
            "Configurez les clés API pour accéder aux plateformes d'IA via leurs API officielles. "
            "Toutes les informations sont stockées de manière sécurisée dans le trousseau système."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        main_layout.addWidget(description)

        # Section: Sélection de plateforme
        platform_layout = QtWidgets.QHBoxLayout()
        platform_layout.setSpacing(15)
        platform_label = QtWidgets.QLabel("Plateforme:")
        platform_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 80px;")
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setMinimumWidth(200)
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        self._set_combo_style(self.platform_combo)
        platform_layout.addWidget(platform_label)
        platform_layout.addWidget(self.platform_combo)
        platform_layout.addStretch()
        main_layout.addLayout(platform_layout)

        # Section principale: Champs à gauche, Headers à droite
        main_content_layout = QtWidgets.QHBoxLayout()
        main_content_layout.setSpacing(20)
        
        # Colonne de gauche
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)
        
        # Clé API
        api_key_label = QtWidgets.QLabel("Clé API:")
        api_key_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        left_column.addWidget(api_key_label)

        self.api_key_edit = QtWidgets.QLineEdit()
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Entrez votre clé API")
        self.api_key_edit.setMinimumWidth(400)
        self.api_key_edit.setMaximumWidth(500)
        self._set_lineedit_style(self.api_key_edit)

        self.eye_action = QtWidgets.QAction(self._load_icon("ui/resources/icons/eyeouvert.svg"), "Afficher", self)
        self.eye_action.setCheckable(True)
        self.eye_action.toggled.connect(self._toggle_key_visibility)
        self.api_key_edit.addAction(self.eye_action, QtWidgets.QLineEdit.TrailingPosition)

        left_column.addWidget(self.api_key_edit)

        # Modèle
        model_label = QtWidgets.QLabel("Modèle:")
        model_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        left_column.addWidget(model_label)

        self.model_edit = QtWidgets.QLineEdit()
        self.model_edit.setPlaceholderText("gpt-4, claude-3-opus, etc.")
        self.model_edit.setMinimumWidth(400)
        self.model_edit.setMaximumWidth(500)
        self._set_lineedit_style(self.model_edit)
        left_column.addWidget(self.model_edit)

        # URL
        url_label = QtWidgets.QLabel("URL:")
        url_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        left_column.addWidget(url_label)

        self.base_url_edit = QtWidgets.QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.example.com/v1")
        self.base_url_edit.setMinimumWidth(400)
        self.base_url_edit.setMaximumWidth(500)
        self._set_lineedit_style(self.base_url_edit)
        left_column.addWidget(self.base_url_edit)
        left_column.addStretch()
        
        # Colonne de droite: Headers
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)
        
        headers_label = QtWidgets.QLabel("Headers JSON (avancé):")
        headers_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        right_column.addWidget(headers_label)

        self.custom_headers_edit = QtWidgets.QTextEdit()
        self.custom_headers_edit.setPlaceholderText('{"Authorization": "Bearer YOUR_TOKEN"}')
        self.custom_headers_edit.setMinimumHeight(100)
        self.custom_headers_edit.setMaximumHeight(120)
        self.custom_headers_edit.setMinimumWidth(400)
        self._set_textedit_style(self.custom_headers_edit)
        right_column.addWidget(self.custom_headers_edit)
        right_column.addStretch()
        
        main_content_layout.addLayout(left_column, 1)
        main_content_layout.addLayout(right_column, 1)
        main_content_layout.addStretch()
        
        main_layout.addLayout(main_content_layout)

        # Paramètres
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.setSpacing(15)
        params_layout.setContentsMargins(0, 5, 0, 0)

        tokens_label = QtWidgets.QLabel("Tokens max:")
        tokens_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 90px;")
        self.max_tokens_spin = QtWidgets.QSpinBox()
        self.max_tokens_spin.setRange(1, 100000)
        self.max_tokens_spin.setValue(2000)
        self.max_tokens_spin.setMaximumWidth(110)
        self._set_spinbox_style(self.max_tokens_spin)
        params_layout.addWidget(tokens_label)
        params_layout.addWidget(self.max_tokens_spin)

        timeout_label = QtWidgets.QLabel("Timeout:")
        timeout_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 70px;")
        self.timeout_spin = QtWidgets.QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(60)
        self.timeout_spin.setSuffix(" sec")
        self.timeout_spin.setMaximumWidth(100)
        self._set_spinbox_style(self.timeout_spin)
        params_layout.addWidget(timeout_label)
        params_layout.addWidget(self.timeout_spin)
        params_layout.addStretch()

        main_layout.addLayout(params_layout)
        
        # Boutons d'action
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 20, 0, 0)

        self.test_button = QtWidgets.QPushButton("Tester la clé")
        self.test_button.setIcon(QtGui.QIcon.fromTheme("system-run"))
        self.test_button.clicked.connect(self._on_test_api_key)

        self.save_button = QtWidgets.QPushButton("Enregistrer")
        self.save_button.setIcon(QtGui.QIcon.fromTheme("document-save"))
        self.save_button.clicked.connect(self._on_save_api_key)

        self.delete_button = QtWidgets.QPushButton("Supprimer")
        self.delete_button.setIcon(QtGui.QIcon.fromTheme("edit-delete"))
        self.delete_button.clicked.connect(self._on_delete_api_key)

        buttons_layout.addWidget(self.test_button)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)

        # Console de diagnostic
        console_label = QtWidgets.QLabel("Console de diagnostic:")
        console_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 10px;")
        main_layout.addWidget(console_label)

        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumHeight(200)
        self.console_output.setPlaceholderText("Les messages de diagnostic s'afficheront ici...")
        self._set_console_style(self.console_output)
        main_layout.addWidget(self.console_output)

        # Bouton pour effacer la console (aligné à droite)
        clear_console_layout = QtWidgets.QHBoxLayout()
        clear_console_layout.addStretch()  # Pousse le bouton vers la droite
        
        clear_console_btn = QtWidgets.QPushButton("Effacer la console")
        clear_console_btn.setIcon(QtGui.QIcon.fromTheme("edit-clear"))
        clear_console_btn.clicked.connect(self.console_output.clear)
        clear_console_btn.setMaximumWidth(150)
        clear_console_btn.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px 15px;
                color: #2c3e50;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
                color: white;
                border: 1px solid #c0392b;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        
        clear_console_layout.addWidget(clear_console_btn)
        main_layout.addLayout(clear_console_layout)

        main_layout.addStretch()

    def _set_combo_style(self, combo):
        combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 11px;
            }
            QComboBox:focus {
                border: 2px solid #3498db;
            }
        """)

    def _set_lineedit_style(self, lineedit):
        lineedit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)

    def _set_spinbox_style(self, spinbox):
        spinbox.setStyleSheet("""
            QSpinBox {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 11px;
            }
            QSpinBox:focus {
                border: 2px solid #3498db;
            }
        """)

    def _set_textedit_style(self, textedit):
        textedit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                background-color: #ffffff;
                color: #2c3e50;
                font-family: 'Courier New';
                font-size: 10px;
            }
            QTextEdit:focus {
                border: 2px solid #3498db;
            }
        """)

    def _set_console_style(self, console):
        """Style pour la console de diagnostic - version claire"""
        console.setStyleSheet("""
            QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                background-color: #f8f9fa;
                color: #2c3e50;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """)

    def _log_to_console(self, message, level="info"):
        """Ajoute un message à la console avec couleur selon le niveau"""
        colors = {
            'info': '#3498db',      # Bleu
            'success': '#27ae60',   # Vert
            'warning': '#f39c12',   # Orange
            'error': '#e74c3c',     # Rouge
            'debug': '#7f8c8d'      # Gris
        }
        
        color = colors.get(level, '#2c3e50')
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        
        # Style adapté pour fond clair
        html = f'<span style="color: {color}; font-weight: bold;">[{timestamp}]</span> <span style="color: #2c3e50;">{message}</span>'
        self.console_output.append(html)
        
        # Auto-scroll vers le bas
        scrollbar = self.console_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _populate_platforms(self):
        self.platform_combo.clear()
        self.platform_combo.addItems(self.PLATFORMS)

    def _toggle_key_visibility(self, checked):
        if checked:
            self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.eye_action.setIcon(self._load_icon("ui/resources/icons/eyeslash.svg"))
        else:
            self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.eye_action.setIcon(self._load_icon("ui/resources/icons/eyeouvert.svg"))

    def _on_platform_changed(self, platform_name):
        if not platform_name:
            return
        self.current_platform = platform_name
        self._load_api_config(platform_name)
        self._log_to_console(f"Plateforme sélectionnée: {platform_name}", "info")

    def _get_keyring_key(self, platform_name, key_type="config"):
        return f"{platform_name}_{key_type}"

    def _load_config_from_keyring(self, platform_name):
        try:
            config_json = keyring.get_password(
                self.KEYRING_SERVICE, 
                self._get_keyring_key(platform_name, "config")
            )
            
            if config_json:
                config = json.loads(config_json)
                logger.info(f"Configuration chargée depuis keyring pour {platform_name}")
                return config
            
            api_key = keyring.get_password(self.KEYRING_SERVICE, platform_name)
            if api_key:
                logger.info(f"Migration: clé API trouvée dans l'ancien format pour {platform_name}")
                return {'api_key': api_key}
            
            return {}
            
        except Exception as e:
            logger.error(f"Erreur lecture keyring pour {platform_name}: {str(e)}")
            return {}

    def _save_config_to_keyring(self, platform_name, config):
        try:
            if not config:
                return False
            
            config_json = json.dumps(config, ensure_ascii=False)
            config_key = self._get_keyring_key(platform_name, "config")
            
            keyring.set_password(self.KEYRING_SERVICE, config_key, config_json)
            
            verification = keyring.get_password(self.KEYRING_SERVICE, config_key)
            if not verification:
                return False
            
            try:
                keyring.delete_password(self.KEYRING_SERVICE, platform_name)
            except:
                pass
            
            logger.info(f"Configuration sauvegardée dans keyring pour {platform_name}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde keyring: {str(e)}")
            return False

    def _delete_config_from_keyring(self, platform_name):
        try:
            try:
                keyring.delete_password(
                    self.KEYRING_SERVICE, 
                    self._get_keyring_key(platform_name, "config")
                )
            except:
                pass
            
            try:
                keyring.delete_password(self.KEYRING_SERVICE, platform_name)
            except:
                pass
            
            return True
        except Exception as e:
            logger.error(f"Erreur suppression keyring: {str(e)}")
            return False

    @staticmethod
    def get_platform_config(platform_name):
        try:
            config_key = f"{platform_name}_config"
            config_json = keyring.get_password("AI_Conductor", config_key)

            if config_json:
                return json.loads(config_json)

            api_key = keyring.get_password("AI_Conductor", platform_name)
            if api_key:
                return {'api_key': api_key}

            return {}
        except Exception as e:
            logger.error(f"Erreur lecture keyring: {str(e)}")
            return {}

    def _load_api_config(self, platform_name):
        try:
            config = self._load_config_from_keyring(platform_name)

            if config:
                self.api_key_edit.setText(config.get('api_key', ''))
                self.base_url_edit.setText(config.get('base_url', ''))
                self.model_edit.setText(config.get('model', ''))
                self.max_tokens_spin.setValue(config.get('max_tokens', 2000))
                self.timeout_spin.setValue(config.get('timeout', 60))
                
                custom_headers = config.get('custom_headers', {})
                if custom_headers:
                    self.custom_headers_edit.setPlainText(json.dumps(custom_headers, indent=2))
                else:
                    self.custom_headers_edit.clear()
                
                self._log_to_console(f"Configuration chargée pour {platform_name}", "success")
            else:
                self._reset_fields()
                self._log_to_console(f"Aucune configuration trouvée pour {platform_name}", "warning")

        except Exception as e:
            logger.error(f"Erreur chargement config: {str(e)}")
            self._log_to_console(f"Erreur: {str(e)}", "error")

    def _reset_fields(self):
        self.api_key_edit.clear()
        self.base_url_edit.clear()
        self.model_edit.clear()
        self.max_tokens_spin.setValue(2000)
        self.timeout_spin.setValue(60)
        self.custom_headers_edit.clear()
        self.key_visible = False

    def _show_temporary_message(self, message, duration=1500):
        msg_label = QtWidgets.QLabel(message, self)
        msg_label.setStyleSheet("""
            QLabel {
                background-color: rgba(46, 204, 113, 230);
                color: white;
                padding: 15px 30px;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.adjustSize()
        
        msg_label.move(
            (self.width() - msg_label.width()) // 2,
            (self.height() - msg_label.height()) // 2
        )
        
        msg_label.show()
        msg_label.raise_()
        
        QtCore.QTimer.singleShot(duration, msg_label.deleteLater)

    def _on_test_api_key(self):
        """Lance le test de la clé API dans un thread séparé"""
        if not self.current_platform:
            self._log_to_console("❌ Aucune plateforme sélectionnée", "error")
            return

        api_key = self.api_key_edit.text().strip()
        if not api_key:
            self._log_to_console("❌ Aucune clé API saisie", "error")
            return

        # Désactiver le bouton pendant le test
        self.test_button.setEnabled(False)
        self.test_button.setText("Test en cours...")
        
        self.console_output.clear()
        self._log_to_console("=" * 60, "info")
        self._log_to_console(f"🧪 TEST DE LA CLÉ API - {self.current_platform}", "info")
        self._log_to_console("=" * 60, "info")

        try:
            api_config = self._get_current_config()

            # Créer et démarrer le thread de test
            self.test_thread = ApiTestThread(self.current_platform, api_config, self.conductor)
            self.test_thread.log_message.connect(self._log_to_console)
            self.test_thread.test_complete.connect(self._on_test_complete)
            self.test_thread.start()

        except Exception as e:
            self._log_to_console(f"❌ Erreur lors du démarrage du test: {str(e)}", "error")
            self.test_button.setEnabled(True)
            self.test_button.setText("Tester la clé")

    def _on_test_complete(self, result):
        """Appelé quand le test est terminé"""
        self._log_to_console("=" * 60, "info")
        
        if result['success']:
            self._log_to_console(f"✅ RÉSULTAT: {result['message']}", "success")
            self._log_to_console(f"📝 {result['details']}", "info")
            self.api_key_tested.emit(self.current_platform, True, result['message'])
            self._show_temporary_message("✓ Test réussi")
        else:
            self._log_to_console(f"❌ RÉSULTAT: {result['message']}", "error")
            self._log_to_console(f"📝 {result['details']}", "error")
            self.api_key_tested.emit(self.current_platform, False, result['message'])
        
        self._log_to_console("=" * 60, "info")
        
        # Réactiver le bouton
        self.test_button.setEnabled(True)
        self.test_button.setText("Tester la clé")

    def _get_current_config(self):
        config = {
            'type': 'OpenAI',
            'api_key': self.api_key_edit.text().strip(),
            'base_url': self.base_url_edit.text().strip(),
            'model': self.model_edit.text().strip(),
            'max_tokens': self.max_tokens_spin.value(),
            'timeout': self.timeout_spin.value()
        }

        headers_text = self.custom_headers_edit.toPlainText().strip()
        if headers_text:
            try:
                config['custom_headers'] = json.loads(headers_text)
            except json.JSONDecodeError:
                logger.warning("Headers JSON invalides, ignorés")
                config['custom_headers'] = {}
        else:
            config['custom_headers'] = {}

        return config

    def _on_save_api_key(self):
        """Sauvegarde la configuration API"""
        if not self.current_platform:
            self._log_to_console("❌ Aucune plateforme sélectionnée", "error")
            return

        api_key = self.api_key_edit.text().strip()
        if not api_key:
            self._log_to_console("❌ Aucune clé API saisie", "error")
            return

        try:
            api_config = self._get_current_config()
            
            self._log_to_console(f"💾 Sauvegarde de la configuration pour {self.current_platform}...", "info")
            
            keyring_success = self._save_config_to_keyring(self.current_platform, api_config)

            if keyring_success:
                self._log_to_console(f"✅ Configuration enregistrée avec succès", "success")
                self._log_to_console(f"   - Clé API: {'configurée' if api_config.get('api_key') else 'manquante'}", "info")
                self._log_to_console(f"   - Modèle: {api_config.get('model', 'non défini')}", "info")
                self._log_to_console(f"   - Max tokens: {api_config.get('max_tokens', 'défaut')}", "info")
                
                self.api_key_saved.emit(self.current_platform, api_config)
                self._show_temporary_message("✓ Enregistrement avec succès")
                
                QtCore.QTimer.singleShot(1500, lambda: self._load_api_config(self.current_platform))
            else:
                self._log_to_console(f"❌ Échec de la sauvegarde", "error")
                self._show_temporary_message("✗ Erreur de sauvegarde")

        except Exception as e:
            self._log_to_console(f"❌ Erreur: {str(e)}", "error")
            self._show_temporary_message(f"✗ Erreur: {str(e)}")

    def _on_delete_api_key(self):
        """Supprime la configuration API"""
        if not self.current_platform:
            self._log_to_console("❌ Aucune plateforme sélectionnée", "error")
            return

        try:
            self._log_to_console(f"🗑️ Suppression de la configuration pour {self.current_platform}...", "info")
            
            keyring_success = self._delete_config_from_keyring(self.current_platform)

            if keyring_success:
                self._reset_fields()
                self._log_to_console(f"✅ Configuration supprimée avec succès", "success")
                self.api_key_deleted.emit(self.current_platform)
                self._show_temporary_message("✓ Configuration supprimée")
            else:
                self._log_to_console(f"❌ Échec de la suppression", "error")
                self._show_temporary_message("✗ Erreur de suppression")

        except Exception as e:
            self._log_to_console(f"❌ Erreur: {str(e)}", "error")
            self._show_temporary_message(f"✗ Erreur: {str(e)}")

    def set_profiles(self, profiles):
        """Définit les profils disponibles (pour compatibilité)"""
        self.profiles = profiles
        
        if self.current_platform:
            self._load_api_config(self.current_platform)

    def select_platform(self, platform_name):
        """Sélectionne une plateforme"""
        if platform_name in self.PLATFORMS:
            self.platform_combo.setCurrentText(platform_name)

    def refresh(self):
        """Actualise le widget"""
        if self.current_platform:
            self._load_api_config(self.current_platform)

    def is_configured(self):
        """Vérifie si une API est configurée pour la plateforme courante"""
        if not self.current_platform:
            return False
        
        config = self._load_config_from_keyring(self.current_platform)
        return bool(config.get('api_key'))