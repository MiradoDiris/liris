from PyQt5 import QtWidgets, QtCore, QtGui
import qtawesome as qta

class KeyRecoveryDialog(QtWidgets.QDialog):
    """Interface de récupération de clé de licence"""
    
    def __init__(self, email, parent=None):
        super().__init__(parent)
        self.email = email
        self.setWindowTitle("Récupérer votre clé")
        self.setModal(True)
        self.setFixedSize(500, 400)
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
        
        # En-tête
        header = QtWidgets.QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {self.primary}, stop:1 {self.secondary});
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        """)
        
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        header_layout.setSpacing(12)
        
        icon = QtWidgets.QLabel()
        icon.setPixmap(qta.icon('fa5s.key', color="#EDEBDC").pixmap(28, 28))
        header_layout.addWidget(icon)
        
        title = QtWidgets.QLabel("Récupérer votre clé")
        title.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        main_layout.addWidget(header)
        
        # Contenu
        content = QtWidgets.QWidget()
        content.setStyleSheet(f"background-color: {self.bg};")
        
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(40, 40, 40, 35)
        content_layout.setSpacing(25)
        
        # Message d'information
        info_label = QtWidgets.QLabel(
            f"Entrez la clé de licence envoyée à :<br>"
            f"<b style='color: {self.primary};'>{self.email}</b>"
        )
        info_label.setStyleSheet(f"color: {self.dark}; font-size: 14px; line-height: 1.6;")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)
        
        # Champ de clé
        self.key_input = self._create_key_input()
        content_layout.addWidget(self.key_input['container'])
        
        # Note
        note = QtWidgets.QLabel("💡 La clé contient des lettres et des chiffres (XXXX-XXXX-XXXX)")
        note.setStyleSheet(f"color: {self.light}; font-size: 12px;")
        note.setWordWrap(True)
        content_layout.addWidget(note)
        
        content_layout.addStretch()
        
        main_layout.addWidget(content)
        
        # Footer
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
        
        # Bouton Valider
        self.validate_btn = QtWidgets.QPushButton("  Valider la clé")
        self.validate_btn.setIcon(qta.icon('fa5s.check', color='white'))
        self.validate_btn.setFixedSize(170, 42)
        self.validate_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.validate_btn.setStyleSheet(f"""
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
        self.validate_btn.clicked.connect(self._on_validate)
        
        footer_layout.addStretch()
        footer_layout.addWidget(self.cancel_btn)
        footer_layout.addWidget(self.validate_btn)
        
        main_layout.addWidget(footer)
    
    def _create_key_input(self):
        """Créé le champ de saisie de clé"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QtWidgets.QLabel("Clé de licence")
        label.setStyleSheet(f"color: {self.dark}; font-weight: 600; font-size: 14px;")
        layout.addWidget(label)
        
        # Input container
        input_widget = QtWidgets.QWidget()
        input_widget.setFixedHeight(60)
        input_widget.setStyleSheet(f"""
            QWidget {{
                background-color: white;
                border: 2px solid #E8EAED;
                border-radius: 10px;
            }}
            QWidget:hover {{
                border-color: {self.secondary};
            }}
        """)
        
        input_layout = QtWidgets.QHBoxLayout(input_widget)
        input_layout.setContentsMargins(18, 18, 18, 18)
        input_layout.setSpacing(14)
        
        # Icône
        icon = QtWidgets.QLabel()
        icon.setPixmap(qta.icon('fa5s.key', color=self.light).pixmap(20, 20))
        input_layout.addWidget(icon)
        
        # Champ texte
        field = QtWidgets.QLineEdit()
        field.setFrame(False)
        field.setPlaceholderText("Entrez votre clé...")
        field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 500;
                color: {self.dark};
                padding: 0;
                min-height: 24px;
                letter-spacing: 1px;
            }}
        """)
        
        font = field.font()
        font.setFamily("Consolas, Monaco, monospace")
        font.setPointSize(11)
        font.setWeight(QtGui.QFont.Medium)
        field.setFont(font)
        
        # Animation focus
        def on_focus_in(e):
            input_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: #FFF5F3;
                    border: 2px solid {self.primary};
                    border-radius: 10px;
                }}
            """)
            QtWidgets.QLineEdit.focusInEvent(field, e)
        
        def on_focus_out(e):
            input_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: white;
                    border: 2px solid #E8EAED;
                    border-radius: 10px;
                }}
                QWidget:hover {{
                    border-color: {self.secondary};
                }}
            """)
            QtWidgets.QLineEdit.focusOutEvent(field, e)
        
        field.focusInEvent = on_focus_in
        field.focusOutEvent = on_focus_out
        
        input_layout.addWidget(field, 1)
        layout.addWidget(input_widget)
        
        return {'container': container, 'field': field}
    
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
    
    def _on_validate(self):
        """Validation de la clé"""
        key = self.key_input['field'].text().strip()
        
        if not key:
            self._show_error("Veuillez entrer une clé de licence")
            self.key_input['field'].setFocus()
            return
        
        if len(key) < 10:
            self._show_error("La clé semble trop courte")
            self.key_input['field'].setFocus()
            return
        
        # Simuler la validation
        self._show_loading()
        QtCore.QTimer.singleShot(1500, lambda: self._validate_key(key))
    
    def _show_loading(self):
        """État de chargement"""
        self.validate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.validate_btn.setText("  Validation...")
        
        self.load_timer = QtCore.QTimer()
        self.angle = 0
        
        def rotate():
            self.angle = (self.angle + 30) % 360
            self.validate_btn.setIcon(
                qta.icon('fa5s.circle-notch', color='white', 
                        options=[{'rotate': self.angle}])
            )
        
        self.load_timer.timeout.connect(rotate)
        self.load_timer.start(50)
    
    def _validate_key(self, key):
        """Valide la clé (à adapter selon votre logique)"""
        if hasattr(self, 'load_timer'):
            self.load_timer.stop()
        
        # Exemple de validation simple - à remplacer par votre logique
        if len(key) >= 10:  # Critère basique
            self._show_success(key)
        else:
            self.validate_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.validate_btn.setText("  Valider la clé")
            self.validate_btn.setIcon(qta.icon('fa5s.check', color='white'))
            self._show_error("Clé invalide")
    
    def _show_success(self, key):
        """Message de succès"""
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Activation réussie")
        msg.setIconPixmap(qta.icon('fa5s.check-circle', color='#10B981').pixmap(48, 48))
        msg.setText("<b style='font-size: 15px;'>Licence activée !</b>")
        msg.setInformativeText(
            f"Votre licence Premium est maintenant active.<br>"
            f"<span style='color: #666;'>Profitez de toutes les fonctionnalités !</span>"
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


class PremiumDialog(QtWidgets.QDialog):
    """Formulaire simplifié et moderne pour la demande de licence Premium"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Passer à Premium")
        self.setModal(True)
        self.setFixedSize(550, 600)
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
        
        # En-tête avec gradient
        header = QtWidgets.QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {self.primary}, stop:1 {self.secondary});
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        """)
        
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        header_layout.setSpacing(12)
        header_layout.setAlignment(QtCore.Qt.AlignVCenter)
        
        # Icône couronne
        icon = QtWidgets.QLabel()
        icon.setPixmap(qta.icon('fa5s.crown', color="#EDEBDC").pixmap(28, 28))
        header_layout.addWidget(icon)
        
        # Titre
        title = QtWidgets.QLabel("Passez à Premium")
        title.setStyleSheet("""
            color: white;
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
        
        # Bouton Envoyer
        self.submit_btn = QtWidgets.QPushButton("  Obtenir ma licence")
        self.submit_btn.setIcon(qta.icon('fa5s.paper-plane', color='white'))
        self.submit_btn.setFixedSize(190, 42)
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
    
    def _create_input(self, label_text, placeholder, icon_name):
        """Créé un champ de saisie moderne"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet(f"color: {self.dark}; font-weight: 600; font-size: 14px;")
        layout.addWidget(label)
        
        # Input container
        input_widget = QtWidgets.QWidget()
        input_widget.setFixedHeight(60)
        input_widget.setStyleSheet(f"""
            QWidget {{
                background-color: white;
                border: 2px solid #E8EAED;
                border-radius: 10px;
            }}
            QWidget:hover {{
                border-color: {self.secondary};
            }}
        """)
        
        input_layout = QtWidgets.QHBoxLayout(input_widget)
        input_layout.setContentsMargins(18, 18, 18, 18)
        input_layout.setSpacing(14)
        
        # Icône
        icon = QtWidgets.QLabel()
        icon.setPixmap(qta.icon(icon_name, color=self.light).pixmap(20, 20))
        input_layout.addWidget(icon)
        
        # Champ texte
        field = QtWidgets.QLineEdit()
        field.setFrame(False)
        field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 500;
                color: {self.dark};
                padding: 0;
                min-height: 24px;
                letter-spacing: 0.3px;
            }}
        """)
        
        font = field.font()
        font.setFamily("Segoe UI, Arial, sans-serif")
        font.setPointSize(11)
        font.setWeight(QtGui.QFont.Medium)
        field.setFont(font)
        
        # Animation focus
        def on_focus_in(e):
            input_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: #FFF5F3;
                    border: 2px solid {self.primary};
                    border-radius: 10px;
                }}
            """)
            QtWidgets.QLineEdit.focusInEvent(field, e)
        
        def on_focus_out(e):
            input_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: white;
                    border: 2px solid #E8EAED;
                    border-radius: 10px;
                }}
                QWidget:hover {{
                    border-color: {self.secondary};
                }}
            """)
            QtWidgets.QLineEdit.focusOutEvent(field, e)
        
        field.focusInEvent = on_focus_in
        field.focusOutEvent = on_focus_out
        
        input_layout.addWidget(field, 1)
        layout.addWidget(input_widget)
        
        return {'container': container, 'field': field}
    
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
        """Validation et envoi - redirige vers l'interface de récupération"""
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
        
        # Simuler l'envoi puis ouvrir l'interface de récupération
        self._show_loading()
        QtCore.QTimer.singleShot(1500, lambda: self._open_key_recovery(email))
    
    def _show_loading(self):
        """État de chargement"""
        self.submit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.submit_btn.setText("  Envoi en cours...")
        
        self.load_timer = QtCore.QTimer()
        self.angle = 0
        
        def rotate():
            self.angle = (self.angle + 30) % 360
            self.submit_btn.setIcon(
                qta.icon('fa5s.circle-notch', color='white', 
                        options=[{'rotate': self.angle}])
            )
        
        self.load_timer.timeout.connect(rotate)
        self.load_timer.start(50)
    
    def _open_key_recovery(self, email):
        """Ouvre l'interface de récupération de clé"""
        if hasattr(self, 'load_timer'):
            self.load_timer.stop()
        
        # Fermer le dialogue actuel
        self.accept()
        
        # Ouvrir l'interface de récupération
        recovery_dialog = KeyRecoveryDialog(email, self.parent())
        recovery_dialog.exec_()
    
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
