import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QUrl # QUrl pour potentiellement ouvrir un lien Stripe dans un navigateur
# from PyQt5.QtGui import QDesktopServices # Nécessaire si vous voulez ouvrir un navigateur externe

class CodingPanel(QWidget):
    """
    Widget pour la création de compte dans le Coding Panel.
    Comprend les champs pour le nom, l'email et un bouton d'intégration Stripe (interface).
    """
    def __init__(self, parent=None):
        """
        Initialise le widget CodingPanel.
        :param parent: Le widget parent (optionnel).
        """
        super().__init__(parent)
        self.setWindowTitle("Créer un Compte - Coding Panel")
        self.setGeometry(100, 100, 500, 350) # x, y, largeur, hauteur

        self._setup_ui() # Configure l'interface utilisateur

    def _setup_ui(self):
        """
        Configure tous les éléments de l'interface utilisateur du formulaire.
        """
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # --- Titre du formulaire ---
        title_label = QLabel("<h2>Créer votre compte Coding Panel</h2>")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        main_layout.addSpacing(20)

        # --- Formulaire pour le Nom et l'Email ---
        form_layout = QFormLayout()
        form_layout.setContentsMargins(40, 10, 40, 10) # Marges pour centrer un peu le formulaire

        # Champ Nom
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Votre nom complet")
        self.name_input.setMinimumHeight(30) # Augmente la hauteur du champ
        form_layout.addRow("Nom:", self.name_input)

        # Champ Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("votre.email@example.com")
        self.email_input.setMinimumHeight(30) # Augmente la hauteur du champ
        form_layout.addRow("Email:", self.email_input)

        main_layout.addLayout(form_layout)
        main_layout.addSpacing(30)

        # --- Intégration de l'interface Stripe ---
        stripe_layout = QHBoxLayout()
        stripe_layout.addStretch() # Pousse le bouton vers le centre/droite

        self.stripe_button = QPushButton("Payer avec Stripe")
        self.stripe_button.setMinimumHeight(40) # Rend le bouton plus grand
        self.stripe_button.setFixedWidth(200) # Largeur fixe pour le bouton Stripe
        self.stripe_button.setStyleSheet(
            """
            QPushButton {
                background-color: #6772E5; /* Couleur bleue de Stripe */
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5764d2;
            }
            QPushButton:pressed {
                background-color: #4b55be;
            }
            """
        )
        # Connecte le bouton à la fonction de simulation de paiement
        self.stripe_button.clicked.connect(self._initiate_stripe_payment)
        stripe_layout.addWidget(self.stripe_button)
        stripe_layout.addStretch() # Pousse le bouton vers le centre/droite

        main_layout.addLayout(stripe_layout)
        main_layout.addSpacing(30) # Espacement avant le bouton de création de compte

        # --- Bouton de création de compte ---
        self.create_account_button = QPushButton("Créer le compte")
        self.create_account_button.setMinimumHeight(40) # Rend le bouton plus grand
        self.create_account_button.setFixedWidth(250) # Largeur fixe pour le bouton
        self.create_account_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50; /* Vert */
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
            """
        )
        # Connecte le bouton à la fonction de simulation de création de compte
        self.create_account_button.clicked.connect(self._create_account)

        # Ajoute le bouton au centre en utilisant un QHBoxLayout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.create_account_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        main_layout.addStretch() # Pousse tout le contenu vers le haut

    def _initiate_stripe_payment(self):
        """
        Fonction de remplacement pour l'initialisation d'un paiement Stripe.
        Ceci est l'interface. La logique réelle impliquerait :
        1. La validation des données requises (ex: l'email).
        2. Un appel à votre backend pour créer une session de paiement Stripe (Checkout Session, Payment Intent).
        3. L'ouverture d'une page de paiement Stripe dans un navigateur web (ex: QDesktopServices.openUrl)
           ou l'intégration d'un widget Stripe Elements dans une QWebEngineView.
        4. La gestion du résultat du paiement (succès/échec) via un webhook de Stripe
           et la mise à jour de l'état du compte utilisateur.
        """
        email = self.email_input.text().strip()

        if not email:
            QMessageBox.warning(self, "Erreur de paiement", "Veuillez entrer votre adresse email pour procéder au paiement Stripe.")
            return

        # Simulation de l'action Stripe
        QMessageBox.information(
            self,
            "Paiement Stripe (Interface)",
            f"Le processus de paiement Stripe serait lancé pour l'email: <b>{email}</b>.<br>"
            "Ceci est une interface utilisateur. L'intégration API de Stripe et le backend "
            "doivent être implémentés ici pour un fonctionnement réel."
        )
        print(f"DEBUG: Tentative d'initier le paiement Stripe pour l'email: {email}")

        # Exemple d'ouverture d'un lien Stripe (nécessite QDesktopServices et QUrl)
        # Assurez-vous d'importer from PyQt5.QtGui import QDesktopServices
        # et from PyQt5.QtCore import QUrl
        # Si vous aviez un URL de session Checkout de Stripe:
        # stripe_checkout_url = "https://checkout.stripe.com/pay/YOUR_SESSION_ID"
        # QDesktopServices.openUrl(QUrl(stripe_checkout_url))


    def _create_account(self):
        """
        Fonction de remplacement pour la création du compte utilisateur.
        Ceci est l'interface. La logique réelle impliquerait :
        1. La validation complète des entrées (nom, email, et potentiellement statut de paiement).
        2. L'envoi des données à un service backend/API pour l'enregistrement de l'utilisateur.
        3. La gestion des réponses du backend (succès, erreur, email déjà utilisé, etc.).
        4. Si le paiement est requis avant la création du compte, cette fonction pourrait
           vérifier si le paiement Stripe a déjà été effectué ou rediriger l'utilisateur.
        """
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        # --- Validation basique des entrées ---
        if not name:
            QMessageBox.warning(self, "Erreur de saisie", "Veuillez entrer votre nom.")
            return

        if not email:
            QMessageBox.warning(self, "Erreur de saisie", "Veuillez entrer votre adresse email.")
            return

        if "@" not in email or "." not in email or " " in email:
            QMessageBox.warning(self, "Email invalide", "Veuillez entrer une adresse email valide.")
            return

        # --- Simulation de la création de compte ---
        # Dans une application réelle, vous feriez un appel API à votre backend ici.
        # Exemple:
        # try:
        #     response = requests.post("YOUR_BACKEND_API/register", json={"name": name, "email": email})
        #     if response.status_code == 200:
        #         QMessageBox.information(self, "Succès", "Compte créé avec succès !")
        #         # Réinitialiser le formulaire
        #         self.name_input.clear()
        #         self.email_input.clear()
        #     else:
        #         error_message = response.json().get("message", "Erreur inconnue lors de la création du compte.")
        #         QMessageBox.critical(self, "Erreur", f"Échec de la création du compte: {error_message}")
        # except Exception as e:
        #     QMessageBox.critical(self, "Erreur Réseau", f"Impossible de contacter le serveur: {e}")

        # Pour cet exemple, nous affichons simplement un message de succès simulé.
        QMessageBox.information(
            self,
            "Compte Créé (Interface)",
            f"Compte pour '<b>{name}</b>' avec l'email '<b>{email}</b>' a été simulé.<br>"
            "La logique de création de compte réelle, incluant la validation backend et "
            "la gestion de la liaison avec le paiement Stripe, devrait être implémentée ici."
        )
        print(f"DEBUG: Tentative de créer un compte pour Nom: {name}, Email: {email}")

        # Réinitialiser le formulaire après une "création" réussie
        self.name_input.clear()
        self.email_input.clear()


# --- Section de test (pour exécuter ce widget seul) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = CodingPanel()
    panel.show()
    sys.exit(app.exec_())