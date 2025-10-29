from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QLabel, QMessageBox, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal

from utils.license_manager import license_manager # Importe l'instance du LicenseManager

class ActivationDialog(QDialog):
    """
    Fenêtre de dialogue permettant à l'utilisateur d'entrer une clé d'activation.
    """
    activation_successful = pyqtSignal() # Signal émis lors d'une activation réussie

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Activation de l'application")
        self.setMinimumWidth(400)
        self.setModal(True) # Rend la fenêtre bloquante

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # Message d'introduction
        intro_label = QLabel(
            "La limite d'utilisation gratuite a été atteinte. "
            "Veuillez entrer votre clé d'activation pour déverrouiller l'application."
        )
        intro_label.setWordWrap(True)
        main_layout.addWidget(intro_label)

        # Champ de saisie de la clé
        key_layout = QHBoxLayout()
        key_label = QLabel("Clé d'activation:")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Ex: XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setEchoMode(QLineEdit.Normal) # Normal ou Password si vous voulez cacher
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        main_layout.addLayout(key_layout)

        # Boutons
        button_layout = QHBoxLayout()
        self.activate_button = QPushButton("Activer")
        self.activate_button.clicked.connect(self._on_activate_clicked)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject) # Rejette le dialogue
        
        button_layout.addStretch() # Pousse les boutons à droite
        button_layout.addWidget(self.activate_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        # État de la vérification
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: blue;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def _on_activate_clicked(self):
        """Gère le clic sur le bouton 'Activer'."""
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer une clé d'activation.")
            return

        self.status_label.setText("Vérification de la clé en cours...")
        self.status_label.setStyleSheet("color: blue;")
        self.activate_button.setEnabled(False)
        self.key_input.setEnabled(False)
        
        # Effectue la vérification via le LicenseManager
        if license_manager.verify_license_online(key):
            self.status_label.setText("Activation réussie !")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Succès", "L'application a été activée avec succès !")
            self.activation_successful.emit() # Émet le signal
            self.accept() # Accepte et ferme le dialogue
        else:
            self.status_label.setText("Clé d'activation invalide ou erreur réseau.")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Échec de l'activation", 
                                 "La clé d'activation est invalide ou une erreur réseau est survenue. Veuillez réessayer.")
            self.activate_button.setEnabled(True)
            self.key_input.setEnabled(True)