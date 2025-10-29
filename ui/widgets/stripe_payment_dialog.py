from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import qtawesome as qta
from utils.logger import logger
import re
import requests
import json


class StripePaymentDialog(QtWidgets.QDialog):
    """Dialogue élégant pour le paiement avec Stripe"""
    
    payment_completed = QtCore.pyqtSignal(dict)  # Signal émis lors du paiement réussi
    
    def __init__(self, parent=None, amount=0.0, currency="EUR", api_url="http://localhost:8080/api/payment/stripe", test_mode=False):
        super().__init__(parent)
        
        self.amount = amount
        self.currency = currency.upper()
        self.api_url = api_url
        self.test_mode = test_mode  # Mode test pour pré-remplir les champs
        self.primary_color = "#635BFF"  # Couleur Stripe
        self.secondary_color = "#0A2540"
        self.success_color = "#00D924"
        self.background_color = "#F6F9FC"
        
        self._init_ui()
        
        # Si mode test, pré-remplir les champs
        if self.test_mode:
            self._fill_test_data()
        
    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        self.setWindowTitle("Paiement sécurisé" + (" - MODE TEST 🧪" if self.test_mode else ""))
        self.setModal(True)
        self.setFixedSize(550, 800 if self.test_mode else 750)
        
        # Style du dialogue
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
                color: #1A1F36;
            }}
            
            QLineEdit {{
                padding: 12px 16px;
                border: 2px solid #E3E8EE;
                border-radius: 8px;
                background-color: #FFFFFF;
                font-size: 14px;
                color: #1A1F36;
            }}
            
            QLineEdit:focus {{
                border: 2px solid {self.primary_color};
                background-color: #FAFAFF;
                outline: none;
            }}
            
            QLineEdit:hover {{
                border: 2px solid #C7D0DD;
            }}
            
            QPushButton {{
                padding: 14px 24px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            
            QPushButton#payButton {{
                background-color: {self.primary_color};
                color: white;
            }}
            
            QPushButton#payButton:hover {{
                background-color: #7A73FF;
            }}
            
            QPushButton#payButton:disabled {{
                background-color: #CCCCCC;
                color: #888888;
            }}
            
            QPushButton#cancelButton {{
                background-color: #F7F9FC;
                color: #697386;
                border: 2px solid #E3E8EE;
            }}
            
            QPushButton#cancelButton:hover {{
                background-color: #EAEEF3;
                border-color: #C7D0DD;
            }}
            
            QPushButton#testButton {{
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                font-size: 12px;
            }}
            
            QPushButton#testButton:hover {{
                background-color: #FB8C00;
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
        icon_pixmap = qta.icon('fa5s.credit-card', color=self.primary_color).pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)
        title_container.addWidget(icon_label)
        
        title_text = "Paiement sécurisé"
        if self.test_mode:
            title_text += " 🧪"
        
        title_label = QtWidgets.QLabel(title_text)
        title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {self.secondary_color};
            padding-left: 15px;
        """)
        title_container.addWidget(title_label)
        title_container.addStretch()
        
        header_layout.addLayout(title_container)
        
        # Sous-titre avec badge Stripe
        subtitle_container = QtWidgets.QHBoxLayout()
        subtitle_container.addStretch()
        
        powered_label = QtWidgets.QLabel("Propulsé par")
        powered_label.setStyleSheet("font-size: 12px; color: #697386;")
        subtitle_container.addWidget(powered_label)
        
        stripe_label = QtWidgets.QLabel("Stripe")
        stripe_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: bold;
            color: {self.primary_color};
            padding: 4px 10px;
            background-color: #F6F9FC;
            border-radius: 4px;
            margin-left: 5px;
        """)
        subtitle_container.addWidget(stripe_label)
        
        lock_icon = QtWidgets.QLabel()
        lock_pixmap = qta.icon('fa5s.lock', color=self.success_color).pixmap(14, 14)
        lock_icon.setPixmap(lock_pixmap)
        subtitle_container.addWidget(lock_icon)
        
        subtitle_container.addStretch()
        header_layout.addLayout(subtitle_container)
        
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
        
        # ===== BANNIÈRE MODE TEST =====
        if self.test_mode:
            test_banner = QtWidgets.QLabel("🧪 MODE TEST - Utilisez les cartes de test Stripe")
            test_banner.setStyleSheet("""
                background-color: #FFF3CD;
                color: #856404;
                padding: 10px;
                border-radius: 6px;
                border-left: 4px solid #FF9800;
                font-size: 12px;
                font-weight: bold;
            """)
            test_banner.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(test_banner)
        
        # ===== MONTANT À PAYER (INPUT ÉDITABLE) =====
        amount_container = self._create_amount_field()
        main_layout.addWidget(amount_container)
        
        # ===== BOUTON REMPLIR DONNÉES TEST =====
        if self.test_mode:
            test_button_layout = QtWidgets.QHBoxLayout()
            test_button_layout.addStretch()
            
            self.fill_test_button = QtWidgets.QPushButton("  Remplir avec données de test")
            self.fill_test_button.setObjectName("testButton")
            self.fill_test_button.setIcon(qta.icon('fa5s.flask', color='white'))
            self.fill_test_button.setCursor(Qt.PointingHandCursor)
            self.fill_test_button.clicked.connect(self._fill_test_data)
            test_button_layout.addWidget(self.fill_test_button)
            
            test_button_layout.addStretch()
            main_layout.addLayout(test_button_layout)
        
        # ===== FORMULAIRE DE PAIEMENT =====
        form_layout = QtWidgets.QVBoxLayout()
        form_layout.setSpacing(22)
        
        # Numéro de carte
        card_container = self._create_field_container(
            "💳 Numéro de carte",
            "1234 5678 9012 3456"
        )
        self.card_input = card_container['input']
        self.card_input.setMaxLength(19)  # 16 digits + 3 spaces
        self.card_input.textChanged.connect(self._format_card_number)
        form_layout.addLayout(card_container['layout'])
        
        # Date d'expiration et CVV sur la même ligne
        expiry_cvv_layout = QtWidgets.QHBoxLayout()
        expiry_cvv_layout.setSpacing(15)
        
        # Date d'expiration
        expiry_container = self._create_field_container(
            "📅 Expiration",
            "MM/AA"
        )
        self.expiry_input = expiry_container['input']
        self.expiry_input.setMaxLength(5)
        self.expiry_input.textChanged.connect(self._format_expiry_date)
        expiry_cvv_layout.addLayout(expiry_container['layout'])
        
        # CVV
        cvv_container = self._create_field_container(
            "🔒 CVV",
            "123"
        )
        self.cvv_input = cvv_container['input']
        self.cvv_input.setMaxLength(4)
        self.cvv_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.cvv_input.textChanged.connect(self._validate_cvv)
        expiry_cvv_layout.addLayout(cvv_container['layout'])
        
        form_layout.addLayout(expiry_cvv_layout)
        
        # Nom sur la carte
        name_container = self._create_field_container(
            "👤 Nom sur la carte",
            "Jean Dupont"
        )
        self.name_input = name_container['input']
        form_layout.addLayout(name_container['layout'])
        
        # Email (optionnel pour le reçu)
        email_container = self._create_field_container(
            "📧 Email (optionnel)",
            "jean.dupont@exemple.com"
        )
        self.email_input = email_container['input']
        form_layout.addLayout(email_container['layout'])
        
        main_layout.addLayout(form_layout)
        
        # Message d'erreur
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("""
            color: #E74C3C;
            font-size: 13px;
            font-weight: bold;
            padding: 12px;
            background-color: #FADBD8;
            border-radius: 6px;
            border-left: 3px solid #E74C3C;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)
        
        # Message de succès
        self.success_label = QtWidgets.QLabel()
        self.success_label.setStyleSheet(f"""
            color: {self.success_color};
            font-size: 13px;
            font-weight: bold;
            padding: 12px;
            background-color: #D4EDDA;
            border-radius: 6px;
            border-left: 3px solid {self.success_color};
        """)
        self.success_label.setWordWrap(True)
        self.success_label.setVisible(False)
        main_layout.addWidget(self.success_label)
        
        # Badge de sécurité
        security_layout = QtWidgets.QHBoxLayout()
        security_layout.addStretch()
        
        security_icon = QtWidgets.QLabel()
        security_pixmap = qta.icon('fa5s.shield-alt', color=self.success_color).pixmap(16, 16)
        security_icon.setPixmap(security_pixmap)
        security_layout.addWidget(security_icon)
        
        security_label = QtWidgets.QLabel("Paiement sécurisé SSL 256-bit")
        security_label.setStyleSheet(f"font-size: 12px; color: #697386; margin-left: 5px;")
        security_layout.addWidget(security_label)
        security_layout.addStretch()
        
        main_layout.addLayout(security_layout)
        
        main_layout.addStretch()
        
        # ===== BOUTONS D'ACTION =====
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # Bouton Annuler
        self.cancel_button = QtWidgets.QPushButton("Annuler")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setFixedHeight(50)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        
        # Bouton Payer
        self.pay_button = QtWidgets.QPushButton(f"  Payer")
        self.pay_button.setObjectName("payButton")
        self.pay_button.setIcon(qta.icon('fa5s.lock', color='white'))
        self.pay_button.setCursor(Qt.PointingHandCursor)
        self.pay_button.setFixedHeight(50)
        self.pay_button.clicked.connect(self._on_process_payment)
        buttons_layout.addWidget(self.pay_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Connecter les champs pour validation
        self.card_input.textChanged.connect(self._validate_form)
        self.expiry_input.textChanged.connect(self._validate_form)
        self.cvv_input.textChanged.connect(self._validate_form)
        self.name_input.textChanged.connect(self._validate_form)
        self.amount_input.textChanged.connect(self._validate_form)
        
        # Validation initiale
        self._validate_form()
    
    def _fill_test_data(self):
        """Remplit les champs avec des données de test Stripe"""
        logger.info("🧪 Remplissage avec données de test Stripe")
        
        # Données de test
        self.card_input.setText("4242 4242 4242 4242")
        self.expiry_input.setText("12/28")
        self.cvv_input.setText("123")
        self.name_input.setText("Test User")
        self.email_input.setText("test@example.com")
        
        # Afficher un message temporaire
        if hasattr(self, 'fill_test_button'):
            original_text = self.fill_test_button.text()
            self.fill_test_button.setText("  ✓ Données chargées")
            self.fill_test_button.setEnabled(False)
            
            # Réactiver après 2 secondes
            QtCore.QTimer.singleShot(2000, lambda: (
                self.fill_test_button.setText(original_text),
                self.fill_test_button.setEnabled(True)
            ))
    
    def _create_field_container(self, label_text, placeholder):
        """Crée un conteneur de champ avec label et input"""
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setSpacing(10)
        
        # Label
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet("""
            font-weight: 600;
            font-size: 13px;
            color: #1A1F36;
        """)
        container_layout.addWidget(label)
        
        # Input
        input_field = QtWidgets.QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(48)
        container_layout.addWidget(input_field)
        
        return {
            'layout': container_layout,
            'input': input_field
        }
    
    def _create_amount_field(self):
        """Crée un champ pour le montant (éditable avec validation)"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QtWidgets.QLabel("💰 Montant à payer")
        label.setStyleSheet("""
            font-weight: 600;
            font-size: 13px;
            color: #1A1F36;
        """)
        layout.addWidget(label)
        
        # Container pour l'input et la devise
        input_container = QtWidgets.QHBoxLayout()
        input_container.setSpacing(10)
        
        # Input montant éditable
        self.amount_input = QtWidgets.QLineEdit()
        self.amount_input.setText(f"{self.amount:.2f}")
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setMinimumHeight(48)
        self.amount_input.setAlignment(Qt.AlignRight)
        self.amount_input.textChanged.connect(self._format_amount)
        
        # Validator pour accepter uniquement des nombres et points
        validator = QtGui.QDoubleValidator(0.0, 999999.99, 2)
        validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
        self.amount_input.setValidator(validator)
        
        input_container.addWidget(self.amount_input)
        
        # Devise (label non-éditable)
        currency_label = QtWidgets.QLabel(self.currency)
        currency_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14px;
            color: {self.secondary_color};
            padding: 0 12px;
        """)
        currency_label.setAlignment(Qt.AlignCenter)
        currency_label.setMinimumWidth(50)
        input_container.addWidget(currency_label)
        
        layout.addLayout(input_container)
        
        # Message d'info montant
        self.amount_error_label = QtWidgets.QLabel()
        self.amount_error_label.setStyleSheet("""
            color: #E74C3C;
            font-size: 11px;
            margin-top: 5px;
        """)
        self.amount_error_label.setVisible(False)
        layout.addWidget(self.amount_error_label)
        
        return container
    
    def _format_amount(self, text):
        """Formate et valide le montant"""
        if not text:
            self.amount_error_label.setVisible(False)
            return
        
        try:
            amount = float(text)
            if amount <= 0:
                self.amount_error_label.setText("Le montant doit être supérieur à 0")
                self.amount_error_label.setVisible(True)
            elif amount > 999999.99:
                self.amount_error_label.setText("Montant trop élevé (max: 999999.99)")
                self.amount_error_label.setVisible(True)
            else:
                self.amount_error_label.setVisible(False)
                self.amount = amount
                self._update_button_text()
        except ValueError:
            self.amount_error_label.setText("Montant invalide")
            self.amount_error_label.setVisible(True)
    
    def _update_button_text(self):
        """Met à jour le texte du bouton avec le montant actuel"""
        try:
            amount = float(self.amount_input.text())
            self.pay_button.setText(f"  Payer {amount:.2f} {self.currency}")
        except:
            self.pay_button.setText("  Payer")
    
    def _format_card_number(self, text):
        """Formate le numéro de carte avec des espaces"""
        # Retirer les espaces
        text = text.replace(" ", "")
        
        # Ne garder que les chiffres
        text = ''.join(filter(str.isdigit, text))
        
        # Ajouter des espaces tous les 4 chiffres
        formatted = ' '.join([text[i:i+4] for i in range(0, len(text), 4)])
        
        # Mettre à jour le champ sans déclencher textChanged
        self.card_input.blockSignals(True)
        self.card_input.setText(formatted)
        self.card_input.blockSignals(False)
    
    def _format_expiry_date(self, text):
        """Formate la date d'expiration MM/AA"""
        # Retirer le slash
        text = text.replace("/", "")
        
        # Ne garder que les chiffres
        text = ''.join(filter(str.isdigit, text))
        
        # Ajouter le slash après 2 chiffres
        if len(text) >= 2:
            formatted = text[:2] + "/" + text[2:4]
        else:
            formatted = text
        
        # Mettre à jour le champ
        self.expiry_input.blockSignals(True)
        self.expiry_input.setText(formatted)
        self.expiry_input.blockSignals(False)
    
    def _validate_cvv(self, text):
        """Valide le CVV (3 ou 4 chiffres)"""
        text = ''.join(filter(str.isdigit, text))
        self.cvv_input.blockSignals(True)
        self.cvv_input.setText(text)
        self.cvv_input.blockSignals(False)
    
    def _validate_form(self):
        """Valide le formulaire et active/désactive le bouton Payer"""
        card = self.card_input.text().replace(" ", "")
        expiry = self.expiry_input.text()
        cvv = self.cvv_input.text()
        name = self.name_input.text().strip()
        
        try:
            amount = float(self.amount_input.text())
            amount_valid = amount > 0
        except:
            amount_valid = False
        
        # Validation basique
        is_valid = (
            len(card) >= 13 and  # Minimum 13 chiffres pour une carte
            len(expiry) == 5 and  # Format MM/AA
            len(cvv) >= 3 and
            len(name) > 0 and
            amount_valid
        )
        
        self.pay_button.setEnabled(is_valid)
        self.error_label.setVisible(False)
        self.success_label.setVisible(False)
    
    def _on_process_payment(self):
        """Traite le paiement via l'API Stripe"""
        card_number = self.card_input.text().replace(" ", "")
        expiry = self.expiry_input.text()
        cvv = self.cvv_input.text()
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        
        try:
            amount = float(self.amount_input.text())
        except:
            self._show_error("❌ Montant invalide.")
            return
        
        # Validation avancée
        if not self._validate_card_number(card_number):
            self._show_error("❌ Numéro de carte invalide.")
            return
        
        if not self._validate_expiry_date(expiry):
            self._show_error("❌ Date d'expiration invalide ou expirée.")
            return
        
        if len(cvv) < 3 or len(cvv) > 4:
            self._show_error("❌ CVV invalide (3 ou 4 chiffres).")
            return
        
        if email and not self._is_valid_email(email):
            self._show_error("❌ Adresse email invalide.")
            return
        
        # Désactiver le bouton pendant la requête
        self.pay_button.setEnabled(False)
        self.pay_button.setText("  Traitement en cours...")
        QtWidgets.QApplication.processEvents()
        
        # Extraire mois et année
        exp_month, exp_year = expiry.split("/")
        
        # Préparer les données pour l'API
        payment_data = {
            'amount': amount,
            'currency': self.currency.lower(),
            'card_number': card_number,
            'exp_month': int(exp_month),
            'exp_year': int("20" + exp_year),
            'cvc': cvv,
            'cardholder_name': name,
            'email': email if email else None
        }
        
        try:
            # Envoyer la requête POST à l'API
            response = requests.post(
                self.api_url,
                json=payment_data,
                headers={'Content-Type': 'application/json'},
                timeout=30  # Timeout plus long pour les paiements
            )
            
            # Vérifier la réponse
            if response.status_code == 200 or response.status_code == 201:
                # Succès
                response_data = response.json()
                
                result_data = {
                    'amount': amount,
                    'currency': self.currency,
                    'cardholder_name': name,
                    'email': email,
                    'api_response': response_data
                }
                
                logger.info(f"✅ Paiement réussi: {amount} {self.currency} - {name}")
                
                # Afficher message de succès
                self._show_success(f"✅ Paiement de {amount:.2f} {self.currency} effectué avec succès!")
                
                # Émettre le signal
                self.payment_completed.emit(result_data)
                
                # Fermer le dialogue après un délai
                QtCore.QTimer.singleShot(2000, self.accept)
                
            else:
                # Erreur serveur
                error_message = "❌ Erreur lors du traitement du paiement."
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_message = f"❌ {error_data['message']}"
                    elif 'error' in error_data:
                        error_message = f"❌ {error_data['error']}"
                    elif 'detail' in error_data:
                        error_message = f"❌ {error_data['detail']}"
                except:
                    error_message = f"❌ Erreur {response.status_code}"
                
                logger.error(f"Erreur paiement: {response.status_code} - {response.text}")
                self._show_error(error_message)
                self._reset_button()
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Impossible de se connecter à l'API: {self.api_url}")
            self._show_error("❌ Impossible de se connecter au serveur de paiement.")
            self._reset_button()
            
        except requests.exceptions.Timeout:
            logger.error("Timeout lors de la requête de paiement")
            self._show_error("❌ La requête a pris trop de temps. Veuillez réessayer.")
            self._reset_button()
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors du paiement: {str(e)}")
            self._show_error(f"❌ Erreur inattendue: {str(e)[:100]}")
            self._reset_button()
    
    def _reset_button(self):
        """Réinitialise le bouton de paiement"""
        self._update_button_text()
        self.pay_button.setEnabled(True)
    
    def _validate_card_number(self, card_number):
        """Valide le numéro de carte avec l'algorithme de Luhn"""
        if not card_number.isdigit() or len(card_number) < 13 or len(card_number) > 19:
            return False
        
        # Algorithme de Luhn
        total = 0
        reverse_digits = card_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        return total % 10 == 0
    
    def _validate_expiry_date(self, expiry):
        """Valide la date d'expiration"""
        if len(expiry) != 5 or "/" not in expiry:
            return False
        
        try:
            month, year = expiry.split("/")
            month = int(month)
            year = int("20" + year)
            
            if month < 1 or month > 12:
                return False
            
            # Vérifier si la carte n'est pas expirée
            from datetime import datetime
            current_date = datetime.now()
            expiry_date = datetime(year, month, 1)
            
            return expiry_date >= datetime(current_date.year, current_date.month, 1)
        except:
            return False
    
    def _is_valid_email(self, email):
        """Validation simple d'email"""
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        return re.match(pattern, email) is not None
    
    def _show_error(self, message):
        """Affiche un message d'erreur"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.success_label.setVisible(False)
        
        # Animation de secousse
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