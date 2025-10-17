Suite à votre demande, je vais générer le code pour une formulaire de création de compte avec intégration Stripe, en tenant compte du contexte d'un "coding panel" et du fichier `ui\widgets\coding_panel.py`.

Pour une intégration Stripe sécurisée et conforme aux normes PCI, il est impératif que les opérations de paiement impliquant vos clés API secrètes se fassent côté serveur. L'approche la plus courante pour une application de bureau (comme le suggère `ui\widgets\coding_panel.py` avec PyQt) est de :

1.  Collecter les informations de base (nom, email) dans l'application de bureau.
2.  Envoyer ces informations à un **serveur backend** (distinct de l'application de bureau).
3.  Le backend interagit avec l'API Stripe pour créer une session de paiement (par exemple, Stripe Checkout).
4.  Le backend renvoie une URL de paiement sécurisée à l'application de bureau.
5.  L'application de bureau ouvre cette URL dans le navigateur web par défaut de l'utilisateur.
6.  L'utilisateur complète le paiement sur la page sécurisée de Stripe.
7.  Stripe informe votre backend (via un **webhook**) du statut du paiement, permettant ainsi d'activer le compte de l'utilisateur.

Je vais donc structurer ma réponse en trois parties principales :

1.  **`ui\widgets\account_creation_form.py`**: Le nouveau widget PyQt pour le formulaire de création de compte.
2.  **`ui\widgets\coding_panel.py`**: Une modification conceptuelle du fichier existant pour intégrer ce nouveau formulaire (par exemple, dans un nouvel onglet).
3.  **`backend\app.py` (CONCEPTUEL)**: Un exemple de serveur Flask backend qui gère les appels à l'API Stripe et les webhooks. C'est une composante *essentielle* pour la fonctionnalité Stripe mais elle est séparée de l'application client.

---

### 1. `ui\widgets\account_creation_form.py`

Ce fichier contiendra le code du widget PyQt pour le formulaire de création de compte.

```python
# ==============================================================================
# FICHIER: ui\widgets\account_creation_form.py
# DESCRIPTION: Nouveau widget pour la création de compte utilisateur,
#              incluant les champs nom, email et l'initiation de paiement Stripe.
# ==============================================================================

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QMessageBox, QProgressDialog
)
from PyQt5.QtCore import pyqtSignal, Qt
import requests  # Pour les appels HTTP vers le backend
import json
import logging

# Configuration du logger pour ce module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class AccountCreationForm(QWidget):
    """
    Widget PyQt pour la création de compte utilisateur.
    Contient des champs pour le nom et l'email, et un bouton pour initier un paiement Stripe.
    Interagit avec un backend pour gérer la logique Stripe.
    """
    # Signal émis lorsque le formulaire est soumis et que le paiement Stripe est initié avec succès.
    # Fournit le nom, l'email de l'utilisateur et l'URL de redirection Stripe Checkout.
    payment_initiated = pyqtSignal(str, str, str)  # (name, email, stripe_checkout_url)

    # Signal émis en cas d'erreur lors de la soumission du formulaire ou de la communication avec le backend.
    error_occurred = pyqtSignal(str)  # (message d'erreur)

    def __init__(self, backend_url="http://127.0.0.1:5000/api", parent=None):
        """
        Initialise le formulaire de création de compte.

        Args:
            backend_url (str): L'URL de base de l'API backend pour les interactions Stripe.
                               Doit pointer vers votre service Flask/Django/FastAPI.
            parent (QWidget): Le widget parent de ce formulaire.
        """
        super().__init__(parent)
        self.backend_url = backend_url
        self.init_ui()

    def init_ui(self):
        """
        Configure l'interface utilisateur (UI) du formulaire avec les champs et boutons nécessaires.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)  # Aligner le contenu en haut
        main_layout.setSpacing(15)  # Espacement entre les widgets

        # Titre du formulaire
        title_label = QLabel("Créer votre compte Coding Panel")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 15px; color: #333;")
        main_layout.addWidget(title_label)

        # Champ pour le nom complet
        name_layout = QHBoxLayout()
        name_label = QLabel("Nom complet:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Entrez votre nom et prénom")
        self.name_input.setMinimumWidth(250)
        name_layout.addWidget(name_label)
        name_layout.addStretch() # Pousser le label vers la gauche
        name_layout.addWidget(self.name_input)
        main_layout.addLayout(name_layout)

        # Champ pour l'adresse email
        email_layout = QHBoxLayout()
        email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Entrez une adresse email valide")
        self.email_input.setMinimumWidth(250)
        email_layout.addWidget(email_label)
        email_layout.addStretch() # Pousser le label vers la gauche
        email_layout.addWidget(self.email_input)
        main_layout.addLayout(email_layout)

        # Informations sur le paiement Stripe
        stripe_info_label = QLabel(
            "En cliquant sur 'Créer le compte et S'abonner', "
            "vous serez redirigé vers une page sécurisée de Stripe dans votre navigateur "
            "pour finaliser le processus d'abonnement et de paiement."
        )
        stripe_info_label.setStyleSheet("font-style: italic; color: #666; margin-top: 10px; margin-bottom: 20px;")
        stripe_info_label.setWordWrap(True)  # Permet au texte de passer à la ligne
        main_layout.addWidget(stripe_info_label)

        # Bouton de soumission
        self.submit_button = QPushButton("Créer le compte et S'abonner")
        self.submit_button.setStyleSheet(
            "QPushButton { "
                "background-color: #4CAF50; color: white; "
                "padding: 12px 25px; border-radius: 6px; font-size: 16px; font-weight: bold;"
            "}"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:pressed { background-color: #3e8e41; }"
            "QPushButton:disabled { background-color: #cccccc; color: #666666; }"
        )
        self.submit_button.clicked.connect(self._on_submit)
        main_layout.addWidget(self.submit_button)

        # Ajoute un espace flexible pour pousser les éléments vers le haut du layout
        main_layout.addStretch()

        self.setLayout(main_layout)
        self.setWindowTitle("Création de Compte")

        # Appliquer des styles de base aux QLineEdit
        self.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                min-width: 200px;
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
        """)

    def _on_submit(self):
        """
        Méthode appelée lorsque le bouton de soumission est cliqué.
        Elle valide les entrées utilisateur et initie la communication avec le backend.
        """
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        # Validation basique des entrées
        if not name:
            QMessageBox.warning(self, "Erreur de validation", "Veuillez entrer votre nom complet.")
            return

        if not email or "@" not in email or "." not in email:
            QMessageBox.warning(self, "Erreur de validation", "Veuillez entrer une adresse email valide.")
            return

        # Désactiver le bouton pour éviter les soumissions multiples
        self.submit_button.setEnabled(False)

        # Afficher une boîte de dialogue de progression pour informer l'utilisateur
        self.progress_dialog = QProgressDialog("Préparation de votre abonnement...", "Annuler", 0, 0, self)
        self.progress_dialog.setWindowTitle("Chargement")
        self.progress_dialog.setWindowModality(Qt.WindowModal)  # Rend la boîte de dialogue bloquante
        self.progress_dialog.setCancelButton(None)  # Pas de bouton Annuler pour ce processus critique
        self.progress_dialog.setMinimumDuration(0)  # Afficher immédiatement
        self.progress_dialog.show()

        try:
            logger.info(f"Tentative d'initiation de paiement pour {email} via {self.backend_url}/create-checkout-session")
            # Appel HTTP POST vers le backend pour créer une session Stripe Checkout
            response = requests.post(
                f"{self.backend_url}/create-checkout-session",
                json={"name": name, "email": email},
                timeout=10  # Timeout de 10 secondes pour la requête
            )
            response.raise_for_status()  # Lève une exception pour les codes d'état HTTP d'erreur (4xx ou 5xx)

            data = response.json()
            checkout_url = data.get("checkout_url")

            if checkout_url:
                self.progress_dialog.close()
                logger.info(f"URL de paiement Stripe reçue pour {email}. Émission du signal.")
                # Émet le signal avec les informations nécessaires pour la redirection
                self.payment_initiated.emit(name, email, checkout_url)
            else:
                self.progress_dialog.close()
                error_msg = data.get("error", "URL de paiement Stripe non reçue du backend.")
                logger.error(f"Erreur backend: {error_msg}")
                QMessageBox.critical(self, "Erreur de Paiement", error_msg)
                self.error_occurred.emit(error_msg)

        except requests.exceptions.ConnectionError as e:
            self.progress_dialog.close()
            msg = f"Impossible de se connecter au serveur backend à {self.backend_url}. Veuillez vérifier qu'il est en cours d'exécution. Erreur: {e}"
            logger.error(msg)
            QMessageBox.critical(self, "Erreur de Connexion", msg)
            self.error_occurred.emit(msg)
        except requests.exceptions.Timeout:
            self.progress_dialog.close()
            msg = "Le serveur backend n'a pas répondu à temps. Veuillez réessayer."
            logger.error(msg)
            QMessageBox.critical(self, "Timeout de la Requête", msg)
            self.error_occurred.emit(msg)
        except requests.exceptions.RequestException as e:
            self.progress_dialog.close()
            msg = f"Une erreur HTTP est survenue lors de la communication avec le backend : {e}"
            logger.error(msg)
            QMessageBox.critical(self, "Erreur de Requête", msg)
            self.error_occurred.emit(msg)
        except json.JSONDecodeError:
            self.progress_dialog.close()
            msg = "Réponse invalide reçue du serveur backend (non-JSON)."
            logger.error(msg)
            QMessageBox.critical(self, "Erreur de Données", msg)
            self.error_occurred.emit(msg)
        except Exception as e:
            self.progress_dialog.close()
            msg = f"Une erreur inattendue est survenue : {e}"
            logger.error(msg)
            QMessageBox.critical(self, "Erreur Inattendue", msg)
            self.error_occurred.emit(msg)
        finally:
            self.submit_button.setEnabled(True) # Réactiver le bouton après traitement
```

---

### 2. `ui\widgets\coding_panel.py` (Modification)

Ce bloc montre comment intégrer le `AccountCreationForm` dans votre `coding_panel.py`. Étant donné que le `coding_panel` a une dépendance sur `tabs`, l'ajout d'un nouvel onglet pour la création de compte est une option logique et non intrusive.

```python
# ==============================================================================
# FICHIER: ui\widgets\coding_panel.py
# DESCRIPTION: Modification pour intégrer le formulaire de création de compte.
#              (Exemple d'intégration dans un QTabWidget).
#              Ceci est une version simplifiée du fichier existant pour montrer l'intégration.
# ==============================================================================

import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QApplication, QLabel, QMessageBox
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl, Qt
import logging

# Import du nouveau formulaire de création de compte
from ui.widgets.account_creation_form import AccountCreationForm

# Configuration du logger pour ce module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Simulateurs d'autres widgets existants ---
# (Ces classes sont ici pour que l'exemple soit complet et puisse être exécuté.
#  Dans votre projet réel, ce seraient les imports de vos vrais widgets.)
class ProjectConfigOnlyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Section: Configuration du Projet")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setStyleSheet("background-color: #e0f2f7; border: 1px solid #b3e5fc;")

class PlatformConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Section: Configuration de la Plateforme")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setStyleSheet("background-color: #e8f5e9; border: 1px solid #c8e6c9;")

class PromptList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Section: Liste des Prompts")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setStyleSheet("background-color: #fffde7; border: 1px solid #fff9c4;")

# (Ajoutez ici les simulateurs pour les 15 autres widgets liés si vous souhaitez un exemple complet)
# ----------------------------------------------------------------------


class CodingPanel(QMainWindow):
    """
    Fenêtre principale du Coding Panel.
    Gère l'organisation des différents widgets et intègre le formulaire de création de compte.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coding Panel - Gestion de Projet & Compte")
        self.setGeometry(100, 100, 1000, 700) # x, y, width, height

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self._add_existing_tabs()       # Ajoute les onglets déjà présents
        self._add_account_creation_tab() # Ajoute le nouvel onglet pour la création de compte

        self.set_default_styles()       # Applique des styles visuels à l'application

        logger.info("CodingPanel initialisé et formulaire de création de compte intégré.")

    def _add_existing_tabs(self):
        """
        Ajoute les onglets existants au QTabWidget du panel de codage.
        Basé sur les éléments listés dans le périmètre.
        """
        self.tab_widget.addTab(ProjectConfigOnlyWidget(self), "Configuration Projet")
        self.tab_widget.addTab(PlatformConfigWidget(self), "Configuration Plateforme")
        self.tab_widget.addTab(PromptList(self), "Prompts")
        # Ajoutez ici les instances des autres widgets enfants mentionnés dans le périmètre
        # Ex: self.tab_widget.addTab(DatasetGenerator(self), "Générateur Dataset")
        # Ex: self.tab_widget.addTab(WorkersWidget(self), "Workers")
        # Ex: self.tab_widget.addTab(DatasetTable(self), "Table Dataset")
        logger.info("Onglets existants ajoutés.")

    def _add_account_creation_tab(self):
        """
        Crée une instance du AccountCreationForm et l'ajoute comme un nouvel onglet.
        Connecte également les signaux du formulaire aux slots de ce panel.
        """
        # Il est crucial que l'URL du backend corresponde à l'adresse de votre serveur Flask (ou autre).
        # Par défaut, nous utilisons localhost:5000 comme dans l'exemple Flask.
        self.account_form = AccountCreationForm(backend_url="http://127.0.0.1:5000/api", parent=self)
        self.tab_widget.addTab(self.account_form, "Créer un Compte")
        self.tab_widget.setTabIcon(self.tab_widget.indexOf(self.account_form), self.style().standardIcon(QStyle.SP_MessageBoxQuestion)) # Exemple d'icône

        # Connexion des signaux du formulaire
        self.account_form.payment_initiated.connect(self._handle_payment_redirection)
        self.account_form.error_occurred.connect(self._handle_form_error)
        logger.info("Onglet 'Créer un Compte' ajouté et signaux connectés.")

    def _handle_payment_redirection(self, name, email, stripe_checkout_url):
        """
        Slot appelé lorsque le signal `payment_initiated` est émis par AccountCreationForm.
        Ouvre l'URL de paiement Stripe dans le navigateur web par défaut de l'utilisateur.
        """
        logger.info(f"Redirection initiée pour {email} vers Stripe Checkout.")
        # Ouvre l'URL de Stripe Checkout dans le navigateur par défaut
        success = QDesktopServices.openUrl(QUrl(stripe_checkout_url))
        if success:
            QMessageBox.information(
                self, "Action Requise: Compléter l'Abonnement",
                f"Vous avez été redirigé vers une page sécurisée de Stripe dans votre navigateur web."
                f"\n\nVeuillez y compléter les informations de paiement pour activer votre compte '{email}'."
                f"\n\nAprès le paiement, vous pouvez fermer l'onglet du navigateur."
            )
            # Optionnel: On pourrait désactiver le formulaire ou naviguer vers un autre onglet
            # une fois la redirection effectuée pour éviter des soumissions répétées.
            # self.account_form.setEnabled(False)
            # self.tab_widget.setCurrentIndex(0) # Revenir au premier onglet par exemple
        else:
            logger.error(f"Impossible d'ouvrir l'URL Stripe Checkout: {stripe_checkout_url}")
            QMessageBox.critical(
                self, "Erreur de Redirection",
                "Impossible d'ouvrir la page de paiement Stripe dans votre navigateur. "
                "Veuillez copier l'URL suivante et l'ouvrir manuellement:\n"
                f"{stripe_checkout_url}"
            )

    def _handle_form_error(self, message):
        """
        Slot appelé lorsque le signal `error_occurred` est émis par AccountCreationForm.
        Affiche le message d'erreur à l'utilisateur.
        """
        logger.warning(f"Erreur dans le formulaire de création de compte: {message}")
        QMessageBox.critical(self, "Erreur du Formulaire", message)

    def set_default_styles(self):
        """
        Applique des styles CSS par défaut à la fenêtre principale et à ses widgets enfants
        pour une apparence plus cohérente et agréable.
        """
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f8f8;
            }
            QTabWidget::pane { /* Le cadre autour des onglets */
                border-top: 2px solid #a7d9f7; /* Couleur de la ligne du dessus des onglets */
                background: #ffffff; /* Fond du contenu de l'onglet */
                border-radius: 5px;
            }
            QTabWidget::tab-bar {
                left: 5px; /* Décalage de la barre d'onglets par rapport au bord gauche */
            }
            QTabBar::tab {
                background: #e0e0e0; /* Fond des onglets non sélectionnés */
                border: 1px solid #c0c0c0; /* Bordure des onglets */
                border-bottom-color: #c0c0c0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 10ex; /* Largeur minimale des onglets */
                padding: 8px 15px; /* Remplissage interne */
                margin-right: 2px; /* Espacement entre les onglets */
                font-size: 14px;
                color: #444;
            }
            QTabBar::tab:selected {
                background: #ffffff; /* Fond de l'onglet sélectionné */
                border-color: #a7d9f7; /* Couleur de bordure de l'onglet sélectionné */
                border-bottom-color: #ffffff; /* Cache la bordure inférieure de l'onglet sélectionné */
                font-weight: bold;
                color: #000;
            }
            QTabBar::tab:hover:!selected {
                background: #f0f0f0; /* Effet au survol des onglets non sélectionnés */
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
                background-color: #007bff;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)

# --- Exemple d'exécution de l'application PyQt ---
# Ceci est utile pour tester le CodingPanel et le formulaire.
# Dans un projet réel, vous auriez un script 'main.py' ou similaire à la racine.
if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = CodingPanel()
    panel.show()
    sys.exit(app.exec_())

```

---

### 3. `backend\app.py` (CONCEPTUEL - Exemple de Backend Flask)

Ce fichier représente la partie serveur de votre application. **Il doit être exécuté séparément de votre application PyQt.** Il gérera les interactions directes avec l'API Stripe en utilisant vos clés secrètes.

**Installation des dépendances pour le backend :**

```bash
pip install Flask stripe python-dotenv
```

**Fichier `.env` (à créer dans le dossier `backend`) :**

Ce fichier contiendra vos clés API Stripe et l'ID de votre produit/prix Stripe. **Ne partagez jamais vos clés secrètes !**

```dotenv
# .env
STRIPE_SECRET_KEY=sk_test_****************************************
STRIPE_WEBHOOK_SECRET=whsec_****************************************
# Cet ID doit correspondre à un 'Prix' que vous avez configuré dans votre tableau de bord Stripe.
# Ex: price_1HcE022eZvKYlo2Cc18c5D1b pour un abonnement mensuel de 10 EUR.
STRIPE_PRICE_ID=price_****************************************
```

```python
# ==============================================================================
# FICHIER: backend\app.py (CONCEPTUEL - Exemple de Backend Flask)
# DESCRIPTION: Serveur Flask pour gérer les appels à l'API Stripe et les webhooks.
#              Ceci ne fait PAS partie de l'application cliente (coding_panel.py).
#              C'est un serveur distinct qui doit être déployé et accessible
#              par l'application client.
# ==============================================================================

import os
from flask import Flask, request, jsonify, redirect, url_for, render_template_string
import stripe
from dotenv import load_dotenv
import logging

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

# Configuration du logger pour le backend
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurer Stripe avec votre clé secrète.
# Cette clé doit être gardée secrète et ne jamais être exposée côté client.
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Le secret du webhook Stripe est utilisé pour vérifier l'authenticité des événements
# reçus de Stripe.
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Assurez-vous d'avoir un "produit" (Product) et un "plan de tarification" (Price)
# configurés dans votre tableau de bord Stripe pour l'abonnement.
# Remplacez ceci par l'ID de votre Price Stripe (ex: "price_1234567890abcdefghijkl").
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
if not STRIPE_PRICE_ID:
    logger.error("STRIPE_PRICE_ID n'est pas configuré dans les variables d'environnement. Le paiement ne fonctionnera pas.")
    exit(1) # Arrêter si l'ID du prix n'est pas fourni.

@app.route("/api/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """
    Endpoint pour créer une session Stripe Checkout pour un nouvel abonnement.
    Reçoit le nom et l'email de l'utilisateur de l'application client.
    """
    data = request.json
    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        logger.warning(f"Tentative de création de session sans nom/email: {data}")
        return jsonify({"error": "Nom et email sont requis."}), 400

    try:
        # 1. Créer un client Stripe ou récupérer un existant.
        # Dans un système réel, vous pourriez vouloir associer cet email à un utilisateur
        # existant dans votre propre base de données.
        customers = stripe.Customer.list(email=email, limit=1).data
        if customers:
            customer = customers[0]
            logger.info(f"Client Stripe existant trouvé pour {email}: {customer.id}")
        else:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'app_user_name': name} # Stocke le nom dans les métadonnées du client Stripe
            )
            logger.info(f"Nouveau client Stripe créé pour {email}: {customer.id}")

        # 2. Créer une session Checkout pour un abonnement
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            line_items=[
                {
                    "price": STRIPE_PRICE_ID, # Utilisation de l'ID de prix configuré
                    "quantity": 1,
                },
            ],
            mode="subscription", # Mode pour un abonnement récurrent
            success_url="http://127.0.0.1:5000/success?session_id={CHECKOUT_SESSION_ID}", # URL de redirection après succès
            cancel_url="http://127.0.0.1:5000/cancel", # URL de redirection après annulation
            metadata={
                'user_email': email,
                'user_name': name,
                # Ajoutez d'autres métadonnées utiles pour votre système interne
            }
        )
        logger.info(f"Session Checkout créée pour {email}: {checkout_session.id}")
        return jsonify({"checkout_url": checkout_session.url})

    except stripe.error.StripeError as e:
        logger.error(f"Erreur Stripe lors de la création de la session de paiement: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Erreur interne lors de la création de la session de paiement: {e}", exc_info=True)
        return jsonify({"error": "Erreur interne du serveur."}), 500

@app.route("/success")
def success():
    """
    Page de succès affichée à l'utilisateur après un paiement réussi sur Stripe.
    Cette page est affichée dans le navigateur web de l'utilisateur.
    """
    session_id = request.args.get("session_id")
    logger.info(f"Redirection vers la page de succès pour la session Stripe: {session_id}")
    # En production, vous pourriez vouloir récupérer la session pour afficher des détails
    # de manière plus robuste, bien que l'activation du compte se fasse via le webhook.
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Paiement réussi !</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #f0f0f0; }
                .container { background-color: #ffffff; margin: auto; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; }
                h1 { color: #28a745; }
                p { color: #333; }
                a { color: #007bff; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 Paiement réussi !</h1>
                <p>Merci pour votre abonnement au Coding Panel.</p>
                <p>Votre compte sera activé sous peu. Vous pouvez maintenant fermer cette fenêtre.</p>
                <p><small>Session ID: {{ session_id }}</small></p>
                <p><a href="javascript:window.close();">Fermer cette fenêtre</a></p>
            </div>
        </body>
        </html>
    """, session_id=session_id)

@app.route("/cancel")
def cancel():
    """
    Page d'annulation affichée à l'utilisateur après l'annulation du paiement sur Stripe.
    Cette page est affichée dans le navigateur web de l'utilisateur.
    """
    logger.info("Redirection vers la page d'annulation du paiement Stripe.")
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Paiement annulé</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #f0f0f0; }
                .container { background-color: #ffffff; margin: auto; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; }
                h1 { color: #dc3545; }
                p { color: #333; }
                a { color: #007bff; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Paiement annulé.</h1>
                <p>Votre abonnement n'a pas été finalisé.</p>
                <p>Vous pouvez retourner à l'application Coding Panel pour réessayer si vous le souhaitez.</p>
                <p><a href="javascript:window.close();">Fermer cette fenêtre</a></p>
            </div>
        </body>
        </html>
    """)

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """
    Gère les événements webhook de Stripe. C'est ici que l'état de l'utilisateur
    dans votre système est mis à jour suite aux événements de paiement Stripe.
    """
    payload = request.get_data()
    sig_header = request.headers.get("stripe-signature")
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        # Payload invalide
        logger.error(f"Erreur Webhook (payload invalide): {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Signature invalide
        logger.error(f"Erreur Webhook (signature invalide): {e}")
        return jsonify({"error": "Invalid signature"}), 400

    # Gérer l'événement Stripe
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email")
        subscription_id = session.get("subscription")
        customer_id = session.get("customer")
        user_name = session.get("metadata", {}).get("user_name") # Récupéré des metadata

        logger.info(f"Webhook: Checkout Session Completed ({session.id})")
        logger.info(f"User Email: {customer_email}, Name: {user_name}")
        logger.info(f"Customer ID: {customer_id}, Subscription ID: {subscription_id}")

        # --- LOGIQUE D'ACTIVATION DU COMPTE ---
        # Ici, vous devriez :
        # 1. **Vérifier** si un utilisateur existe déjà avec cet email dans votre base de données.
        # 2. Si non, **créer un nouvel utilisateur** dans votre système.
        # 3. **Lier** l'ID du client Stripe (`customer_id`) et l'ID de l'abonnement (`subscription_id`)
        #    à votre utilisateur interne. Ces IDs sont cruciaux pour gérer les abonnements futurs.
        # 4. **Mettre à jour le statut** de l'utilisateur à "actif", "abonné" ou "payant".
        # 5. Potentiellement **envoyer un email de bienvenue** à `customer_email`.
        print(f"ACTION REQUISE: Activation du compte pour {customer_email} - Abonnement: {subscription_id}")
        # --------------------------------------

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        logger.info(f"Webhook: Subscription deleted for customer {customer_id} (ID: {subscription.id})")
        # --- LOGIQUE DE DÉSACTIVATION / GESTION ABONNEMENT ---
        # Ici, vous devriez:
        # 1. Retrouver l'utilisateur lié à ce `customer_id` ou `subscription.id`.
        # 2. Mettre à jour le statut de l'utilisateur à "désactivé", "abonnement annulé", etc.
        # 3. Révoquer l'accès aux fonctionnalités payantes du Coding Panel.
        print(f"ACTION REQUISE: Désactivation/Gestion de l'abonnement pour le client Stripe {customer_id}")
        # -----------------------------------------------------

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        logger.warning(f"Webhook: Payment failed for customer {customer_id}, invoice {invoice.id}")
        # --- LOGIQUE DE GESTION DES ÉCHECS DE PAIEMENT ---
        # Ici, vous devriez:
        # 1. Notifier l'utilisateur de l'échec de son paiement (email).
        # 2. Potentiellement suspendre temporairement l'accès aux fonctionnalités payantes.
        # 3. Informer l'utilisateur des étapes pour mettre à jour ses informations de paiement.
        print(f"ACTION REQUISE: Gestion de l'échec de paiement pour le client Stripe {customer_id}")
        # --------------------------------------------------

    else:
        logger.info(f"Webhook: Type d'événement non géré: {event['type']}")

    return jsonify(success=True)

if __name__ == "__main__":
    # Pour exécuter le backend, assurez-vous que votre fichier .env est configuré.
    # Dans un environnement de production, utilisez un serveur WSGI (Gunicorn, uWSGI)
    # et n'utilisez pas `debug=True`.
    logger.info("Démarrage du serveur Flask pour le backend Stripe...")
    app.run(debug=True, port=5000)

```

---

### Instructions pour l'Implémentation et les Tests

**1. Structure de votre projet :**

Assurez-vous d'avoir une structure de fichiers similaire à celle-ci :

```
your_project_root/
├── ui/
│   └── widgets/
│       ├── coding_panel.py           # Le fichier existant, à modifier
│       ├── account_creation_form.py  # Le nouveau fichier
│       └── __init__.py               # Créez ce fichier s'il n'existe pas (peut être vide)
│       └── ... (vos autres fichiers de widgets)
├── backend/
│   ├── app.py                        # Le nouveau fichier backend Flask
│   └── .env                          # Le fichier de configuration des clés Stripe
└── main_app.py                     # Script pour lancer votre application PyQt (si vous en avez un)
```

**2. Configuration Stripe (très important) :**

*   **Compte Stripe** : Créez un compte sur [Stripe](https://stripe.com/) si vous n'en avez pas.
*   **Clés API** : Récupérez votre "Clé secrète de test" (commençant par `sk_test_...`) depuis le Tableau de bord des développeurs Stripe.
*   **Produit et Prix** :
    *   Dans votre tableau de bord Stripe, allez dans `Produits` > `Ajouter un produit`. Donnez-lui un nom (ex: "Abonnement Coding Panel").
    *   Sous ce produit, cliquez sur `Ajouter un prix`. Choisissez un montant (ex: 10 EUR), une devise, et une récurrence (ex: "Mensuel"). **Notez l'ID du prix** (commence par `price_...`).
*   **Webhook** :
    *   Dans votre tableau de bord Stripe, allez dans `Développeurs` > `Webhooks`.
    *   Cliquez sur `Ajouter un point de terminaison`.
    *   Pour le développement local, vous devrez exposer votre backend à Internet. Utilisez un outil comme [ngrok](https://ngrok.com/). Lancez `ngrok http 5000` et copiez l'URL HTTPS qu'il vous donne (ex: `https://abcd.ngrok.io`).
    *   Collez cette URL suivie de `/stripe-webhook` dans le champ "URL du point de terminaison" (ex: `https://abcd.ngrok.io/stripe-webhook`).
    *   Sélectionnez les événements suivants : `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`.
    *   Cliquez sur `Ajouter un point de terminaison`.
    *   Après sa création, cliquez sur le point de terminaison pour révéler le "Secret de signature" (commence par `whsec_...`).

**3. Remplir le fichier `.env` :**

Ouvrez le fichier `backend/.env` et remplissez-le avec les informations que vous avez obtenues de Stripe :

```dotenv
STRIPE_SECRET_KEY=sk_test_votre_cle_secrete_stripe
STRIPE_WEBHOOK_SECRET=whsec_votre_secret_webhook_stripe
STRIPE_PRICE_ID=price_votre_id_de_prix_stripe
```

**4. Lancement de l'application :**

*   **Lancez le Backend (Terminal 1)** :
    *   Ouvrez un terminal.
    *   Naviguez jusqu'au dossier `backend` (`cd your_project_root/backend`).
    *   Exécutez : `python app.py`
    *   Si vous utilisez ngrok, assurez-vous qu'il est également en cours d'exécution.
*   **Lancez l'Application Client (Terminal 2)** :
    *   Ouvrez un *deuxième* terminal.
    *   Naviguez jusqu'à la racine de votre projet (`cd your_project_root`).
    *   Exécutez : `python main_app.py` (ou le script qui lance votre `CodingPanel`).

**5. Cas de Test suggérés :**

1.  **Affichage du formulaire** : Le `CodingPanel` devrait s'ouvrir et un nouvel onglet "Créer un Compte" devrait être visible et contenir le formulaire.
2.  **Validation des champs** :
    *   Essayez de soumettre le formulaire avec un nom vide. Attendez un `QMessageBox.warning`.
    *   Essayez avec un email invalide (ex: `test`, `test@exemple`). Attendez un `QMessageBox.warning`.
3.  **Flux de paiement réussi** :
    *   Entrez un nom et un email valides.
    *   Cliquez sur "Créer le compte et S'abonner".
    *   Vérifiez l'affichage de la `QProgressDialog`, puis le `QMessageBox.information` de redirection.
    *   Votre navigateur web par défaut devrait s'ouvrir sur la page Stripe Checkout.
    *   Utilisez les cartes de test fournies par Stripe (ex: `4242...4242` pour une carte valide, `4000...0000` pour un échec) pour compléter le paiement.
    *   Vous devriez être redirigé vers la page `/success` de votre backend dans le navigateur.
    *   Dans le terminal du backend, observez les logs pour les messages `Checkout Session Completed` et l'action d'activation du compte.
4.  **Flux de paiement annulé** :
    *   Répétez les étapes 1-3 jusqu'à la page Stripe Checkout.
    *   Annulez la transaction sur la page Stripe (via le bouton d'annulation si disponible ou en fermant l'onglet).
    *   Vous devriez être redirigé vers la page `/cancel` de votre backend.
5.  **Erreur de connexion Backend** :
    *   Arrêtez le serveur `backend/app.py`.
    *   Tentez de soumettre le formulaire dans l'application PyQt.
    *   Attendez un `QMessageBox.critical` indiquant une erreur de connexion.
6.  **Erreur Stripe côté Backend** :
    *   Modifiez temporairement `STRIPE_PRICE_ID` dans `.env` ou `app.py` pour un ID non valide.
    *   Redémarrez le backend et soumettez le formulaire.
    *   Attendez un `QMessageBox.critical` avec l'erreur Stripe (ex: "No such price...").
7.  **Webhook** : Après un paiement réussi, assurez-vous que les logs du terminal du backend affichent bien que le webhook a été reçu et traité, ce qui simule l'activation de l'abonnement dans votre système.

Ce code fournit une base solide et sécurisée pour la fonctionnalité demandée, en respectant les bonnes pratiques d'intégration Stripe et les conventions PyQt.