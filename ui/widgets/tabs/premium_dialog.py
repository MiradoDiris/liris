from PyQt5 import QtWidgets, QtCore, QtGui
import qtawesome as qta
from ui.widgets.create_account_dialog import AccountCreationDialog
from ui.widgets.stripe_payment_dialog import StripePaymentDialog
import requests
import asyncio


class PremiumDialog(QtWidgets.QDialog):
    """Formulaire simplifié et moderne pour la demande de licence Premium"""
    
    def __init__(self, parent=None, license_price=99.99, currency="EUR", api_url="http://localhost:8080"):
        super().__init__(parent)
        self.license_price = license_price
        self.currency = currency
        self.api_url = api_url
        self.setWindowTitle("Passer à Premium")
        self.setModal(True)
        self.setFixedSize(550, 650)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        # Couleurs
        self.primary = "#A23B2D"    
        self.secondary = "#C85442"
        self.bg = "#FAFBFC"
        self.dark = "#1A1A1A"
        self.light = "#666666"
        
        self._init_ui()
        self._apply_fade_in()
        
    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # En-tête avec gradient blanc
        header = QtWidgets.QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #FFFFFF, stop:1 #F5F5F5);
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 2px solid #E8EAED;
        """)

        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        header_layout.setSpacing(12)
        header_layout.setAlignment(QtCore.Qt.AlignVCenter)

        # Icône couronne
        icon = QtWidgets.QLabel()
        icon.setPixmap(qta.icon('fa5s.crown', color=self.primary).pixmap(28, 28))
        header_layout.addWidget(icon)

        # Titre
        title = QtWidgets.QLabel("Passez à Premium")
        title.setStyleSheet(f"""
            color: {self.primary};
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        main_layout.addWidget(header)
        
        # Contenu principal
        content = QtWidgets.QWidget()
        content.setStyleSheet(f"background-color: {self.bg};")
        
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(40, 40, 40, 35)
        content_layout.setSpacing(28)
        
        # Titre du formulaire
        form_title = QtWidgets.QLabel("Obtenez votre licence")
        form_title.setStyleSheet(f"""
            color: {self.dark};
            font-size: 17px;
            font-weight: bold;
        """)
        content_layout.addWidget(form_title)
        
        # Champ Nom
        self.name_input = self._create_input("Nom complet", "", "fa5s.user")
        content_layout.addWidget(self.name_input['container'])
        
        # Champ Email
        self.email_input = self._create_input("Email", "", "fa5s.envelope")
        content_layout.addWidget(self.email_input['container'])
        
        # Message de vérification email
        self.email_status = QtWidgets.QLabel()
        self.email_status.setStyleSheet(f"color: {self.light}; font-size: 12px;")
        self.email_status.setWordWrap(True)
        self.email_status.setVisible(False)
        content_layout.addWidget(self.email_status)
        
        # Note sécurité
        security = QtWidgets.QWidget()
        security.setStyleSheet(f"background-color: transparent;")
        
        security_layout = QtWidgets.QHBoxLayout(security)
        security_layout.setSpacing(12)
        security_layout.setContentsMargins(0, 0, 0, 0)
        
        lock = QtWidgets.QLabel()
        lock.setPixmap(qta.icon('fa5s.shield-alt', color=self.primary).pixmap(20, 20))
        security_layout.addWidget(lock)
        
        security_text = QtWidgets.QLabel("Vos données sont protégées")
        security_text.setStyleSheet(f"""
            color: {self.light}; 
            font-size: 13px;
            font-weight: 500;
        """)
        security_layout.addWidget(security_text)
        security_layout.addStretch()
        
        content_layout.addWidget(security)
        
        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet(f"background-color: #E8EAED; max-height: 1px;")
        content_layout.addWidget(separator)
        
        # Section "Vous n'avez pas de compte"
        account_section = QtWidgets.QWidget()
        account_section.setStyleSheet("background-color: transparent;")
        
        account_layout = QtWidgets.QVBoxLayout(account_section)
        account_layout.setSpacing(12)
        account_layout.setContentsMargins(0, 0, 0, 0)
        
        # Texte "Vous n'avez pas de compte ?"
        no_account_label = QtWidgets.QLabel("Vous n'avez pas de compte ?")
        no_account_label.setStyleSheet(f"""
            color: {self.dark};
            font-size: 14px;
            font-weight: 600;
        """)
        no_account_label.setAlignment(QtCore.Qt.AlignCenter)
        account_layout.addWidget(no_account_label)
        
        # Bouton Créer un compte (plus petit)
        btn_container = QtWidgets.QHBoxLayout()
        btn_container.addStretch()
        
        self.create_account_btn = QtWidgets.QPushButton("  Créer un compte")
        self.create_account_btn.setIcon(qta.icon('fa5s.user-plus', color='white'))
        self.create_account_btn.setFixedSize(180, 36)
        self.create_account_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.create_account_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.primary}, stop:1 {self.secondary});
                color: white;
                border: none;
                border-radius: 18px;
                font-weight: bold;
                font-size: 12px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.secondary}, stop:1 {self.primary});
            }}
            QPushButton:pressed {{
                background-color: #8B2F23;
            }}
        """)
        self.create_account_btn.clicked.connect(self._on_create_account)
        
        btn_container.addWidget(self.create_account_btn)
        btn_container.addStretch()
        account_layout.addLayout(btn_container)
        
        content_layout.addWidget(account_section)
        content_layout.addStretch()
        
        main_layout.addWidget(content)
        
        # Footer avec boutons
        footer = QtWidgets.QWidget()
        footer.setFixedHeight(75)
        footer.setStyleSheet("background-color: white; border-top: 1px solid #E8EAED;")
        
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(40, 15, 40, 15)
        footer_layout.setSpacing(12)
        
        # Bouton Annuler
        self.cancel_btn = QtWidgets.QPushButton("Annuler")
        self.cancel_btn.setFixedSize(110, 42)
        self.cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self.light};
                border: 2px solid #D1D5DB;
                border-radius: 21px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #F9FAFB;
                border-color: {self.light};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Bouton Obtenir ma licence (ouvre le paiement)
        self.submit_btn = QtWidgets.QPushButton(f"  Obtenir ma licence")
        self.submit_btn.setIcon(qta.icon('fa5s.credit-card', color='white'))
        self.submit_btn.setFixedSize(260, 42)
        self.submit_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.primary}, stop:1 {self.secondary});
                color: white;
                border: none;
                border-radius: 21px;
                font-weight: bold;
                font-size: 13px;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.secondary}, stop:1 {self.primary});
            }}
            QPushButton:pressed {{
                background-color: #8B2F23;
            }}
        """)
        self.submit_btn.clicked.connect(self._on_submit)
        
        footer_layout.addStretch()
        footer_layout.addWidget(self.cancel_btn)
        footer_layout.addWidget(self.submit_btn)
        
        main_layout.addWidget(footer)
        
        # Connecter le changement d'email pour vérifier en temps réel
        self.email_input['field'].textChanged.connect(self._on_email_changed)
    
    def _create_input(self, label_text, placeholder, icon_name):
        """Crée un champ de saisie stylisé"""
        container = QtWidgets.QWidget()
        container.setStyleSheet("background-color: transparent;")

        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet(f"""
            color: {self.dark};
            font-size: 13px;
            font-weight: 600;
        """)
        layout.addWidget(label)

        # Input avec icône
        input_container = QtWidgets.QWidget()
        input_container.setFixedHeight(44)
        input_container.setStyleSheet(f"""
            background-color: white;
            border: 2px solid #E8EAED;
            border-radius: 8px;
        """)

        input_layout = QtWidgets.QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 0, 12, 0)
        input_layout.setSpacing(10)

        # Icône (sans bordure)
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color=self.light).pixmap(18, 18))
        icon_label.setStyleSheet("border: none; background: transparent;")
        input_layout.addWidget(icon_label)

        # Champ de texte
        line_edit = QtWidgets.QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {self.dark};
                font-size: 14px;
            }}
        """)
        input_layout.addWidget(line_edit)

        layout.addWidget(input_container)

        # Animation focus
        def on_focus_in(e):
            input_container.setStyleSheet(f"""
                QWidget {{
                    background-color: #FFF5F3;
                    border: 2px solid {self.primary};
                    border-radius: 8px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            QtWidgets.QLineEdit.focusInEvent(line_edit, e)

        def on_focus_out(e):
            input_container.setStyleSheet(f"""
                QWidget {{
                    background-color: white;
                    border: 2px solid #E8EAED;
                    border-radius: 8px;
                }}
                QWidget:hover {{
                    border-color: {self.secondary};
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            QtWidgets.QLineEdit.focusOutEvent(line_edit, e)

        line_edit.focusInEvent = on_focus_in
        line_edit.focusOutEvent = on_focus_out

        return {'container': container, 'field': line_edit}
    
    def _on_email_changed(self, email):
        """Vérifie l'email en temps réel lors du changement"""
        email = email.strip()
        
        if not email:
            self.email_status.setVisible(False)
            return
        
        # Valider format email basique
        if '@' not in email or '.' not in email.split('@')[-1]:
            self.email_status.setText("❌ Format email invalide")
            self.email_status.setStyleSheet(f"color: #EF4444; font-size: 12px;")
            self.email_status.setVisible(True)
            return
        
        # Vérifier si l'utilisateur existe via l'API
        self._check_email_exists(email)
    
    def _check_email_exists(self, email):
        """Vérifie si l'email existe via l'API"""
        try:
            response = requests.get(
                f"{self.api_url}/api/payment/user/{email}/check",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("account_exists"):
                    # Compte trouvé
                    self.email_status.setText("✅ Compte trouvé - Prêt pour le paiement")
                    self.email_status.setStyleSheet(f"color: #10B981; font-size: 12px;")
                    self.email_status.setVisible(True)
                else:
                    # Compte non trouvé
                    self.email_status.setText("⚠️ Aucun compte trouvé avec cet email")
                    self.email_status.setStyleSheet(f"color: #F59E0B; font-size: 12px;")
                    self.email_status.setVisible(True)
            else:
                self.email_status.setText("⚠️ Erreur lors de la vérification")
                self.email_status.setStyleSheet(f"color: #F59E0B; font-size: 12px;")
                self.email_status.setVisible(True)
                
        except requests.exceptions.Timeout:
            self.email_status.setText("⚠️ Vérification en cours...")
            self.email_status.setStyleSheet(f"color: {self.light}; font-size: 12px;")
            self.email_status.setVisible(True)
        except Exception as e:
            self.email_status.setText("⚠️ Impossible de vérifier l'email")
            self.email_status.setStyleSheet(f"color: #F59E0B; font-size: 12px;")
            self.email_status.setVisible(True)
    
    def _apply_fade_in(self):
        """Animation d'apparition"""
        self.opacity = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        
        self.anim = QtCore.QPropertyAnimation(self.opacity, b"opacity")
        self.anim.setDuration(350)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.anim.start()
        
    def _on_submit(self):
        """Validation et ouverture du dialogue de paiement"""
        name = self.name_input['field'].text().strip()
        email = self.email_input['field'].text().strip()
        
        if not name:
            self._show_error("Veuillez entrer votre nom complet")
            self.name_input['field'].setFocus()
            return
            
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            self._show_error("Veuillez entrer une adresse email valide")
            self.email_input['field'].setFocus()
            return
        
        # Vérifier que le compte existe avant d'ouvrir le paiement
        self._verify_and_open_payment(name, email)
    
    def _verify_and_open_payment(self, name, email):
        """Vérifie le compte et ouvre le dialogue de paiement"""
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("  Vérification...")
        QtWidgets.QApplication.processEvents()
        
        try:
            response = requests.post(
                f"{self.api_url}/api/payment/authorize",
                params={"email": email},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("authorized"):
                    # L'utilisateur est autorisé à payer
                    self._open_payment_dialog(name, email)
                else:
                    # Afficher le message d'erreur spécifique de l'API
                    message = data.get("message", "Compte non autorisé à effectuer un paiement")
                    self._show_error(message)
                    self.submit_btn.setEnabled(True)
                    self.submit_btn.setText("  Obtenir ma licence")
            else:
                # Gérer les erreurs HTTP
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", "Erreur lors de la vérification")
                except:
                    error_msg = f"Erreur HTTP {response.status_code}"
                
                self._show_error(f"❌ {error_msg}")
                self.submit_btn.setEnabled(True)
                self.submit_btn.setText("  Obtenir ma licence")
                
        except requests.exceptions.Timeout:
            self._show_error("❌ La vérification a pris trop de temps. Veuillez réessayer.")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("  Obtenir ma licence")
        except requests.exceptions.ConnectionError:
            self._show_error("❌ Impossible de se connecter au serveur. Vérifiez votre connexion.")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("  Obtenir ma licence")
        except Exception as e:
            self._show_error(f"❌ Erreur lors de la vérification: {str(e)[:100]}")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("  Obtenir ma licence")
    
    def _open_payment_dialog(self, name, email):
        """Ouvre le dialogue de paiement Stripe"""
        payment_dialog = StripePaymentDialog(
            parent=self,
            amount=self.license_price,
            currency=self.currency,
            api_url=f"{self.api_url}/api/payment/stripe"
        )
        
        # Connecter le signal de paiement réussi
        payment_dialog.payment_completed.connect(
            lambda data: self._on_payment_success(name, email, data)
        )
        
        # Afficher le dialogue de paiement
        payment_dialog.exec_()
        
        # Réactiver le bouton après fermeture
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("  Obtenir ma licence")
    
    def _on_payment_success(self, name, email, payment_data):
        """Appelé quand le paiement est réussi"""
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Paiement réussi")
        msg.setIconPixmap(qta.icon('fa5s.check-circle', color='#10B981').pixmap(48, 48))
        msg.setText("<b style='font-size: 15px;'>Paiement effectué avec succès !</b>")
        msg.setInformativeText(
            f"Merci {name} !<br>"
            f"Votre licence Premium sera envoyée à :<br>"
            f"<b style='color: {self.primary};'>{email}</b>"
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox { background-color: white; }
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                padding: 8px 25px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        msg.exec_()
        
        self.accept()

    def _on_create_account(self):
        """Gestionnaire pour le bouton Créer un compte"""
        dialog = AccountCreationDialog(self)
        if hasattr(dialog, 'account_created'):
            dialog.account_created.connect(self._on_account_created)
        dialog.exec_()
    
    def _on_account_created(self, account_data):
        """Appelé quand un compte est créé avec succès"""
        if 'email' in account_data:
            self.email_input['field'].setText(account_data['email'])
        if 'nom_complet' in account_data:
            self.name_input['field'].setText(account_data['nom_complet'])
        elif 'prenom' in account_data and 'nom' in account_data:
            self.name_input['field'].setText(f"{account_data['prenom']} {account_data['nom']}")
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Compte créé")
        msg.setIconPixmap(qta.icon('fa5s.check-circle', color='#10B981').pixmap(48, 48))
        msg.setText("<b>Compte créé avec succès !</b>")
        msg.setInformativeText("Vous pouvez maintenant obtenir votre licence Premium.")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox { background-color: white; }
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                padding: 8px 25px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        msg.exec_()
    
    def _show_error(self, message):
        """Message d'erreur"""
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Erreur")
        msg.setIconPixmap(qta.icon('fa5s.exclamation-triangle', color='#EF4444').pixmap(48, 48))
        msg.setText(f"<b>{message}</b>")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                padding: 8px 25px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        msg.exec_()