import os
import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta

# Importation des widgets internes du Dashboard
from ui.widgets.ai_usage_widget import AIUsageWidget
from ui.widgets.tabs.api_key_config_widget import ApiKeyConfigWidget

class DashboardPanel(QtWidgets.QWidget):
    """
    Widget principal du Dashboard IA.
    Contient un menu latéral pour naviguer entre les sections
    "Utilisation de l'IA" et "Configuration de l'API".
    """

    def __init__(self, config_provider, conductor, database, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.database = database
        self.setObjectName("DashboardPanel")

        self._init_style()
        self._init_ui()
        self.update_language()
        
        # S'assurer que les composants système sont passés aux sous-widgets
        self.set_system_components(config_provider, conductor, database)
        
        # Par défaut, afficher le panneau d'utilisation de l'IA
        self.ai_usage_button.click()
        self.refresh_data()

    def _init_style(self):
        """Initialise le style CSS du DashboardPanel en cohérence avec le thème principal."""
        self.setStyleSheet("""
            QWidget#DashboardPanel {
                background-color: #FFFFFF;
                color: #333333;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            /* Style pour le conteneur du menu latéral */
            QWidget#Sidebar {
                background-color: #F5F5F5;
                border-right: 1px solid #E0E0E0;
            }
            /* Style pour les boutons du menu latéral */
            QPushButton.SidebarButton {
                background-color: transparent;
                border: none;
                color: #333333;
                padding: 12px 15px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
                border-radius: 6px;
                margin: 4px 8px;
            }
            QPushButton.SidebarButton:hover {
                background-color: rgba(162, 59, 45, 0.1);
                color: #333333;
            }
            QPushButton.SidebarButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #A23B2D, stop:1 #D35A4A);
                color: white;
                font-weight: bold;
            }
            QLabel#DashboardHeaderLabel {
                font-size: 20px;
                font-weight: bold;
                color: #333333;
                padding: 10px 0;
            }
            QLabel#DashboardPeriodLabel {
                font-size: 14px;
                color: #666666;
                font-style: italic;
            }
        """)

    def _init_ui(self):
        """Configure l'interface utilisateur du Dashboard."""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Menu latéral gauche ---
        sidebar_widget = QtWidgets.QWidget()
        sidebar_widget.setObjectName("Sidebar")
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        sidebar_layout.setSpacing(5)

        # En-tête du Dashboard dans le panneau de gauche
        header_container = QtWidgets.QVBoxLayout()
        header_container.setContentsMargins(15, 0, 15, 20)
        
        # Logo/Titre simple
        app_name_label = QtWidgets.QLabel("Liris IA Dashboard")
        app_name_label.setObjectName("DashboardHeaderLabel")
        app_name_label.setAlignment(Qt.AlignCenter)
        header_container.addWidget(app_name_label)
        
        # Période affichée
        self.period_label = QtWidgets.QLabel("")
        self.period_label.setObjectName("DashboardPeriodLabel")
        self.period_label.setAlignment(Qt.AlignCenter)
        header_container.addWidget(self.period_label)
        
        sidebar_layout.addLayout(header_container)
        
        # Bouton "Utilisation de l'IA"
        self.ai_usage_button = QtWidgets.QPushButton(qta.icon('fa5s.chart-line', color='#e0e0e0'), "Utilisation de l'IA")
        self.ai_usage_button.setCheckable(True)
        self.ai_usage_button.setChecked(True)
        self.ai_usage_button.setProperty("class", "SidebarButton")
        self.ai_usage_button.setIconSize(QtCore.QSize(20, 20))
        
        # Bouton "Configuration de l'API"
        self.api_config_button = QtWidgets.QPushButton(qta.icon('fa5s.cogs', color='#e0e0e0'), "Configuration API")
        self.api_config_button.setCheckable(True)
        self.api_config_button.setProperty("class", "SidebarButton")
        self.api_config_button.setIconSize(QtCore.QSize(20, 20))

        # Groupe de boutons exclusifs
        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.addButton(self.ai_usage_button)
        self.button_group.addButton(self.api_config_button)
        self.button_group.setExclusive(True)

        sidebar_layout.addWidget(self.ai_usage_button)
        sidebar_layout.addWidget(self.api_config_button)
        sidebar_layout.addStretch()

        sidebar_widget.setFixedWidth(250)
        main_layout.addWidget(sidebar_widget)

        # --- Zone de contenu principale (Stacked Widget) ---
        self.content_stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.content_stack)

        # Instanciation des widgets de contenu
        self.ai_usage_widget = AIUsageWidget(self.config_provider, self.database)
        self.api_key_config_widget = ApiKeyConfigWidget(self.config_provider, self.conductor)

        self.content_stack.addWidget(self.ai_usage_widget) # Index 0
        self.content_stack.addWidget(self.api_key_config_widget) # Index 1

        # Connexions des boutons au Stacked Widget
        self.ai_usage_button.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.api_config_button.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        
        # Connexion pour rafraîchir le widget actif quand il est affiché
        self.content_stack.currentChanged.connect(self._on_stack_page_changed)

    def set_system_components(self, config_provider, conductor, database):
        """Passe les composants système aux widgets enfants."""
        self.config_provider = config_provider
        self.conductor = conductor
        self.database = database

        if self.ai_usage_widget:
            # AIUsageWidget peut avoir besoin de la base de données pour de vraies données
            self.ai_usage_widget.database = database
            self.ai_usage_widget.config_provider = config_provider

        if self.api_key_config_widget:
            self.api_key_config_widget.config_provider = config_provider
            self.api_key_config_widget.conductor = conductor
            # Rafraîchir les profils une fois le conducteur initialisé
            if self.conductor and hasattr(self.conductor, 'get_all_profiles'):
                profiles = self.conductor.get_all_profiles()
                self.api_key_config_widget.set_profiles(profiles)
            else:
                self.api_key_config_widget.set_profiles({})

    def refresh_data(self):
        """Rafraîchit les données du widget actuellement visible."""
        current_widget = self.content_stack.currentWidget()
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()
        
        # Mise à jour de la période affichée
        now = datetime.datetime.now()
        mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        self.period_label.setText(f"{mois[now.month - 1]} {now.year}")
        
        if self.ai_usage_widget:
            self.ai_usage_widget.refresh_data()

    def _on_stack_page_changed(self, index):
        """Appelé lors du changement de page dans le QStackedWidget."""
        current_widget = self.content_stack.widget(index)
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()
        
        # S'assurer que le bouton correspondant est coché
        if index == 0:
            self.ai_usage_button.setChecked(True)
        elif index == 1:
            self.api_config_button.setChecked(True)

    def update_language(self):
        """Met à jour les textes de l'interface lors d'un changement de langue."""
        self.ai_usage_button.setText("Utilisation de l'IA")
        self.api_config_button.setText("Configuration API")
        
        now = datetime.datetime.now()
        mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        self.period_label.setText(f"{mois[now.month - 1]} {now.year}")
        
        if self.ai_usage_widget and hasattr(self.ai_usage_widget, 'update_language'):
            self.ai_usage_widget.update_language()
        if self.api_key_config_widget and hasattr(self.api_key_config_widget, 'update_language'):
            self.api_key_config_widget.update_language()