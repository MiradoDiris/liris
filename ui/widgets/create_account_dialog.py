from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import qtawesome as qta
from utils.logger import logger
import re
import requests
import json


class AccountCreationDialog(QtWidgets.QDialog):
    """Dialogue élégant pour la création de compte avec intégration API"""
    
    account_created = QtCore.pyqtSignal(dict)  # Signal émis lors de la création
    
    def __init__(self, parent=None, api_url="http://localhost:8080/api/user/register"):
        super().__init__(parent)
        
        self.api_url = api_url
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        self.setWindowTitle("Créer un compte")
        self.setModal(True)
        self.setFixedSize(500, 550)
        
        # Style du dialogue avec dégradé blanc
        self.setStyleSheet(f"""
            QDialog {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF,
                    stop:0.3 #FAFAFA,
                    stop:1 {self.background_color}
                );
            }}
            
            QLabel {{
                background: transparent;
                color: #333333;
            }}
            
            QLineEdit {{
                padding: 12px 16px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                background-color: #FFFFFF;
                font-size: 14px;
                color: #333333;
            }}
            
            QLineEdit:focus {{
                border: 2px solid {self.primary_color};
                background-color: #FFFBFA;
                outline: none;
            }}
            
            QLineEdit:hover {{
                border: 2px solid #C0C0C0;
            }}
            
            QPushButton {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            
            QPushButton#createButton {{
                background-color: {self.primary_color};
                color: white;
            }}
            
            QPushButton#createButton:hover {{
                background-color: {self.secondary_color};
            }}
            
            QPushButton#createButton:disabled {{
                background-color: #CCCCCC;
                color: #888888;
            }}
            
            QPushButton#cancelButton {{
                background-color: #F5F5F5;
                color: #666666;
                border: 2px solid #E0E0E0;
            }}
            
            QPushButton#cancelButton:hover {{
                background-color: #EEEEEE;
                border-color: #C0C0C0;
            }}
        """)
        
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # ===== EN-TÊTE =====
        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(10)
        
        # Icône + Titre
        title_container = QtWidgets.QHBoxLayout()
        title_container.addStretch()
        
        icon_label = QtWidgets.QLabel()
        icon_pixmap = qta.icon('fa5s.user-plus', color=self.primary_color).pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)
        title_container.addWidget(icon_label)
        
        title_label = QtWidgets.QLabel("Créer un compte")
        title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {self.primary_color};
            padding-left: 15px;
        """)
        title_container.addWidget(title_label)
        title_container.addStretch()
        
        header_layout.addLayout(title_container)
        
        # Sous-titre
        subtitle_label = QtWidgets.QLabel("Remplissez les informations ci-dessous")
        subtitle_label.setStyleSheet("""
            font-size: 13px;
            color: #666666;
            font-style: italic;
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        main_layout.addLayout(header_layout)
        
        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet(f"""
            background-color: {self.primary_color};
            max-height: 2px;
            margin: 10px 0;
        """)
        main_layout.addWidget(separator)
        
        # ===== FORMULAIRE =====
        form_layout = QtWidgets.QVBoxLayout()
        form_layout.setSpacing(20)
        
        # Champ Nom
        nom_container = self._create_field_container(
            "👤 Nom",
            "Entrez votre nom de famille"
        )
        self.nom_input = nom_container['input']
        form_layout.addLayout(nom_container['layout'])
        
        # Champ Prénom
        prenom_container = self._create_field_container(
            "👤 Prénom",
            "Entrez votre prénom"
        )
        self.prenom_input = prenom_container['input']
        form_layout.addLayout(prenom_container['layout'])
        
        # Champ Email
        email_container = self._create_field_container(
            "📧 Email",
            "exemple@email.com"
        )
        self.email_input = email_container['input']
        form_layout.addLayout(email_container['layout'])
        
        main_layout.addLayout(form_layout)
        
        # Message d'erreur (caché par défaut)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("""
            color: #D32F2F;
            font-size: 12px;
            font-weight: bold;
            padding: 8px;
            background-color: #FFEBEE;
            border-radius: 6px;
            border-left: 3px solid #D32F2F;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)
        
        # Message de succès (caché par défaut)
        self.success_label = QtWidgets.QLabel()
        self.success_label.setStyleSheet("""
            color: #388E3C;
            font-size: 12px;
            font-weight: bold;
            padding: 8px;
            background-color: #E8F5E9;
            border-radius: 6px;
            border-left: 3px solid #388E3C;
        """)
        self.success_label.setWordWrap(True)
        self.success_label.setVisible(False)
        main_layout.addWidget(self.success_label)
        
        main_layout.addStretch()
        
        # ===== BOUTONS D'ACTION =====
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # Bouton Annuler
        self.cancel_button = QtWidgets.QPushButton("Annuler")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setFixedHeight(45)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        
        # Bouton Créer
        self.create_button = QtWidgets.QPushButton("  Créer le compte")
        self.create_button.setObjectName("createButton")
        self.create_button.setIcon(qta.icon('fa5s.check', color='white'))
        self.create_button.setCursor(Qt.PointingHandCursor)
        self.create_button.setFixedHeight(45)
        self.create_button.clicked.connect(self._on_create_account)
        buttons_layout.addWidget(self.create_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Connecter les champs pour validation en temps réel
        self.nom_input.textChanged.connect(self._validate_form)
        self.prenom_input.textChanged.connect(self._validate_form)
        self.email_input.textChanged.connect(self._validate_form)
        
        # Validation initiale
        self._validate_form()
        
    def _create_field_container(self, label_text, placeholder):
        """Crée un conteneur de champ avec label et input"""
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setSpacing(8)
        
        # Label
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet("""
            font-weight: 600;
            font-size: 13px;
            color: #333333;
        """)
        container_layout.addWidget(label)
        
        # Input
        input_field = QtWidgets.QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(45)
        container_layout.addWidget(input_field)
        
        return {
            'layout': container_layout,
            'input': input_field
        }
    
    def _validate_form(self):
        """Valide le formulaire et active/désactive le bouton Créer"""
        nom = self.nom_input.text().strip()
        prenom = self.prenom_input.text().strip()
        email = self.email_input.text().strip()
        
        # Validation basique
        is_valid = bool(nom and prenom and email and '@' in email and '.' in email)
        
        self.create_button.setEnabled(is_valid)
        self.error_label.setVisible(False)
        self.success_label.setVisible(False)
    
    def _on_create_account(self):
        """Gère la création du compte via l'API"""
        nom = self.nom_input.text().strip()
        prenom = self.prenom_input.text().strip()
        email = self.email_input.text().strip()
        
        # Validation avancée de l'email
        if not self._is_valid_email(email):
            self._show_error("❌ Veuillez entrer une adresse email valide.")
            return
        
        # Validation des noms (pas de caractères spéciaux)
        if not nom.replace('-', '').replace(' ', '').isalpha():
            self._show_error("❌ Le nom ne doit contenir que des lettres.")
            return
            
        if not prenom.replace('-', '').replace(' ', '').isalpha():
            self._show_error("❌ Le prénom ne doit contenir que des lettres.")
            return
        
        # Désactiver le bouton pendant la requête
        self.create_button.setEnabled(False)
        self.create_button.setText("  Création en cours...")
        QtWidgets.QApplication.processEvents()
        
        # Préparer les données pour l'API
        api_data = {
            'nom': nom,
            'prenom': prenom,
            'email': email.lower()
        }
        
        try:
            # Envoyer la requête POST à l'API
            response = requests.post(
                self.api_url,
                json=api_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            # Vérifier la réponse
            if response.status_code == 200 or response.status_code == 201:
                # Succès
                response_data = response.json()
                
                account_data = {
                    'nom': nom,
                    'prenom': prenom,
                    'email': email.lower(),
                    'nom_complet': f"{prenom} {nom}",
                    'api_response': response_data
                }
                
                logger.info(f"Compte créé avec succès: {account_data['nom_complet']} ({email})")
                
                # Afficher message de succès
                self._show_success("✅ Compte créé avec succès!")
                
                # Émettre le signal
                self.account_created.emit(account_data)
                
                # Fermer le dialogue après un court délai
                QtCore.QTimer.singleShot(1500, self.accept)
                
            else:
                # Erreur serveur
                error_message = "❌ Erreur lors de la création du compte."
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_message = f"❌ {error_data['message']}"
                    elif 'detail' in error_data:
                        error_message = f"❌ {error_data['detail']}"
                except:
                    error_message = f"❌ Erreur {response.status_code}: {response.text[:100]}"
                
                logger.error(f"Erreur API: {response.status_code} - {response.text}")
                self._show_error(error_message)
                self._reset_button()
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Impossible de se connecter à l'API: {self.api_url}")
            self._show_error("❌ Impossible de se connecter au serveur. Vérifiez que l'API est démarrée.")
            self._reset_button()
            
        except requests.exceptions.Timeout:
            logger.error("Timeout lors de la requête API")
            self._show_error("❌ La requête a pris trop de temps. Réessayez.")
            self._reset_button()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la requête API: {str(e)}")
            self._show_error(f"❌ Erreur réseau: {str(e)[:100]}")
            self._reset_button()
            
        except Exception as e:
            logger.error(f"Erreur inattendue: {str(e)}")
            self._show_error(f"❌ Erreur inattendue: {str(e)[:100]}")
            self._reset_button()
    
    def _reset_button(self):
        """Réinitialise le bouton de création"""
        self.create_button.setText("  Créer le compte")
        self.create_button.setEnabled(True)
    
    def _is_valid_email(self, email):
        """Validation simple d'email"""
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _show_error(self, message):
        """Affiche un message d'erreur"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.success_label.setVisible(False)
        
        # Animation de secousse pour attirer l'attention
        self._shake_animation()
    
    def _show_success(self, message):
        """Affiche un message de succès"""
        self.success_label.setText(message)
        self.success_label.setVisible(True)
        self.error_label.setVisible(False)
    
    def _shake_animation(self):
        """Animation de secousse pour le dialogue"""
        animation = QtCore.QPropertyAnimation(self, b"pos")
        animation.setDuration(400)
        animation.setLoopCount(1)
        
        pos = self.pos()
        animation.setStartValue(pos)
        animation.setKeyValueAt(0.25, QtCore.QPoint(pos.x() + 10, pos.y()))
        animation.setKeyValueAt(0.5, QtCore.QPoint(pos.x() - 10, pos.y()))
        animation.setKeyValueAt(0.75, QtCore.QPoint(pos.x() + 10, pos.y()))
        animation.setEndValue(pos)
        
        animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)