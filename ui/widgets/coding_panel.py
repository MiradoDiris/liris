# coding_panel.py - Version avec panneau de snippets rétractable
import os
import time
import pyperclip
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
import qtawesome as qta
import requests

from utils.logger import logger
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.taxonomy_dialog import TaxonomyDialog
from ui.widgets.tabs.graph_widget import GraphWidget
from utils.api_config import APIConfigManager
from utils.ai_platform_manager import AIPlatformManager
from utils.conversation_history import ConversationHistory
from ui.widgets.tabs.code_popup_dialog import CodePopupDialog
from ui.widgets.tabs.snippet_card import SnippetCard
from utils.vscode_integration import VSCodeIntegration

class CodingPanel(QtWidgets.QWidget):   
    """Widget pour les sessions du coding multi-IA avec panneau de snippets rétractable"""

    # Signaux
    session_started = pyqtSignal(int)
    session_completed = pyqtSignal(int)
    session_failed = pyqtSignal(int, str)
    export_requested = pyqtSignal(str)
    snippet_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.conductor = None
        self.profiles = {}
        self.running_workers = []
        self.current_session_id = None
        self.orchestrator = None
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.api_config = APIConfigManager()
        self.platform_manager = AIPlatformManager(self.api_config)
        self.conversation_history = ConversationHistory(
            max_messages=10,
            max_age_hours=24
        )
        self.current_project_data = None
        self.ai_usage_widget = None
        self.selected_taxonomy = []
        self.current_snippets = []

        self.is_browser_mode = True
        self.snippets_panel_visible = False

        self.vscode_url = "http://127.0.0.1:9000"

        self.vscode_integration = VSCodeIntegration()
        self.vscode_integration.code_sent.connect(self._on_vscode_response)
        self.vscode_integration.connection_changed.connect(self._on_vscode_connection_changed)
        logger.info("✅ Signaux VS Code connectés")

        QtCore.QTimer.singleShot(1000, self._check_vscode_startup)

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"
        self.accent_color = "#E8E0DF"

        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        self._init_style()
        self._init_ui()
        self._update_ui_texts()
        self._load_projects_list()
        self.setObjectName("CodingPanel")
        QtCore.QTimer.singleShot(0, lambda: self._switch_mode(True))

    def _init_style(self):
        """Style global"""
        def get_dropdown_svg_path():
            current_dir = os.path.dirname(os.path.abspath(__file__))
            ui_dir = os.path.dirname(current_dir)
            svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
            svg_path = os.path.normpath(svg_path)
            return svg_path

        svg_path = get_dropdown_svg_path()
        svg_path = svg_path.replace('\\', '/')

        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QGroupBox {{
            border: 1px solid #D0D0D0;
            border-radius: 8px;
            margin-top: 1.2em;
            padding: 15px;
            background-color: #FFFFFF;
            font-weight: bold;
            font-size: 14px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px;
            color: #333333;
        }}

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {self.secondary_color}; }}
        QPushButton:disabled {{ background-color: #e0e0e0; color: #424242; }}

        QLabel {{
            background-color: transparent;
        }}

        QLineEdit, QComboBox, QTextEdit {{
            padding: 8px 12px;
            border: 2px solid #E0E0E0;
            border-radius: 6px;
            background-color: #FFFFFF;
            font-size: 13px;
        }}
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
            border: 2px solid {self.primary_color};
            background-color: #FFFBFA;
            outline: none;
        }}

        QComboBox {{
            min-height: 38px;
            padding-left: 12px;
            padding-right: 35px;
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 32px;
            border: none;
            border-left: 1px solid #E0E0E0;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: linear-gradient(to bottom, #FAFAFA, #F5F5F5);
        }}

        QComboBox::down-arrow {{
            image: url({svg_path});
            width: 18px;
            height: 18px;
        }}

        /* ✅ NOUVEAUX STYLES POUR ÉLIMINER LES COCHES ET CERCLES */

        QComboBox QAbstractItemView {{
            border: 1px solid #D0D0D0;
            border-radius: 6px;
            background-color: #FFFFFF;
            selection-background-color: {self.accent_color};
            selection-color: {self.text_color};
            padding: 4px;
            outline: none;
        }}

        QComboBox QAbstractItemView::item {{
            padding: 8px 12px;
            border: none;
            margin: 2px 4px;
            border-radius: 4px;
        }}

        QComboBox QAbstractItemView::item:selected {{
            background-color: {self.accent_color};
            color: {self.text_color};
        }}

        QComboBox QAbstractItemView::item:hover {{
            background-color: #F0F0F0;
        }}

        /* ✅ ÉLIMINER LES INDICATEURS (coches, cercles) */
        QComboBox QAbstractItemView::indicator {{
            width: 0px;
            height: 0px;
            border: none;
            background: transparent;
        }}

        QComboBox QAbstractItemView::indicator:checked {{
            image: none;
        }}
        """

        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Interface avec panneau de snippets rétractable"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ✅ NOUVEAU : Calcul des dimensions responsives
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        self.base_width = screen_size.width()
        self.base_height = screen_size.height()

        # ===== CONTENEUR PRINCIPAL (Paramètres + Graphe) =====
        main_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(main_content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ===== COLONNE GAUCHE : Paramètres (30%) =====
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(12)

        # ===== EN-TÊTE AVEC SWITCH MODE =====
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)

        # Icône + Titre alignés
        title_container = QtWidgets.QHBoxLayout()
        title_container.setSpacing(8)

        title_icon = QtWidgets.QLabel()
        title_icon.setPixmap(qta.icon('fa5s.laptop-code', color='#666').pixmap(24, 24))
        title_icon.setAlignment(Qt.AlignCenter)
        title_container.addWidget(title_icon)

        self.title_label = QtWidgets.QLabel("Coding")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; background-color: transparent;")
        self.title_label.setAlignment(Qt.AlignVCenter)
        title_container.addWidget(self.title_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        # ===== BOUTON SWITCH MODE =====
        self.mode_switch_container = QtWidgets.QWidget()
        # ✅ RESPONSIVE : Largeur adaptative avec limites raisonnables
        switch_width = max(180, min(280, int(self.base_width * 0.15)))
        self.mode_switch_container.setMinimumWidth(180)
        self.mode_switch_container.setMaximumWidth(280)
        self.mode_switch_container.setFixedHeight(40)

        switch_layout = QtWidgets.QHBoxLayout(self.mode_switch_container)
        switch_layout.setContentsMargins(3, 3, 3, 3)
        switch_layout.setSpacing(3)

        # Style du container - fond gris clair arrondi
        self.mode_switch_container.setStyleSheet("""
            QWidget {
                background-color: #E8E8E8;
                border-radius: 20px;
            }
        """)

        # ✅ CRÉER LES BOUTONS (Navigation Auto en premier pour être à gauche)
        self.browser_mode_button = QtWidgets.QPushButton("Navigation Auto")
        self.api_mode_button = QtWidgets.QPushButton("Mode API")

        # ✅ RESPONSIVE : Calculer la largeur après création
        button_width = (switch_width - 10) // 2
        self.browser_mode_button.setFixedSize(button_width, 34)
        self.api_mode_button.setFixedSize(button_width, 34)

        self.browser_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.api_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.browser_mode_button.clicked.connect(lambda: self._switch_mode(True))
        self.api_mode_button.clicked.connect(lambda: self._switch_mode(False))

        # ✅ Navigation Auto à GAUCHE, Mode API à DROITE
        switch_layout.addWidget(self.browser_mode_button)
        switch_layout.addWidget(self.api_mode_button)

        self.is_browser_mode = True

        # Appliquer le style initial
        self._update_switch_style()

        # Centrer un peu le switch
        header_layout.addSpacing(20)
        header_layout.addWidget(self.mode_switch_container)
        header_layout.addSpacing(10)

        left_column.addLayout(header_layout)

        # Groupe Paramètres
        self.session_group = QtWidgets.QGroupBox("Paramètres de Session")
        session_layout = QtWidgets.QVBoxLayout(self.session_group)
        session_layout.setSpacing(10)
        session_layout.setContentsMargins(10, 18, 10, 10)

        # Projet + Plateforme
        proj_platform_layout = QtWidgets.QHBoxLayout()

        # 📁 Projet
        project_label = QtWidgets.QLabel(f"📁 {tr('project')}")
        project_label.setStyleSheet("font-weight: 600; font-size: 12px; background-color: transparent;")

        self.project_combo = QtWidgets.QComboBox()
        # ✅ RESPONSIVE : Largeur dynamique selon la taille d'écran
        min_width = 180  # Minimum garanti
        preferred_width = max(200, int(self.base_width * 0.12))  # 12% de la largeur écran
        max_width = 400  # Maximum pour éviter d'être trop large

        self.project_combo.setMinimumWidth(min_width)
        self.project_combo.setMaximumWidth(max_width)
        self.project_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,  # Préféré au lieu d'Expanding
            QtWidgets.QSizePolicy.Fixed
        )
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)

        # 🤖 Plateforme IA
        platform_label = QtWidgets.QLabel(tr('ai_platform'))
        platform_label.setStyleSheet("font-weight: 600; font-size: 12px; margin-left: 20px; background-color: transparent;")

        self.platforms_combo = QtWidgets.QComboBox()
        # ✅ RESPONSIVE : Même logique pour la plateforme
        self.platforms_combo.setMinimumWidth(min_width)
        self.platforms_combo.setMaximumWidth(max_width)
        self.platforms_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed
        )

        proj_platform_layout.addWidget(project_label)
        proj_platform_layout.addWidget(self.project_combo)
        proj_platform_layout.addWidget(platform_label)
        proj_platform_layout.addWidget(self.platforms_combo)
        proj_platform_layout.addStretch()  # ✅ Garder le stretch pour aligner à gauche
        session_layout.addLayout(proj_platform_layout)

        # Contexte
        context_label = QtWidgets.QLabel(f"💡 {tr('context_label')}")
        context_label.setStyleSheet("font-weight: 600; font-size: 12px; background-color: transparent;")
        session_layout.addWidget(context_label)

        self.context_edit = QtWidgets.QTextEdit()
        self.context_edit.setPlaceholderText("Décrivez la fonctionnalité à implémenter...")
        # ✅ RESPONSIVE : Hauteur préférée (pas de minimum strict)
        self.context_edit.setMinimumHeight(80)  # Réduire de 150 à 80
        preferred_height = max(120, int(self.base_height * 0.15))
        self.context_edit.setMaximumHeight(int(self.base_height * 0.35))
        self.context_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, 
            QtWidgets.QSizePolicy.Preferred
        )
        session_layout.addWidget(self.context_edit)

        # Périmètre (CODE ORIGINAL INCHANGÉ)
        perimeter_container = QtWidgets.QVBoxLayout()
        perimeter_container.setSpacing(10)

        perimeter_header = QtWidgets.QHBoxLayout()
        perimeter_label_title = QtWidgets.QLabel(f"🎯 {tr('implementation_perimeter')}")
        perimeter_label_title.setStyleSheet("font-weight: 600; font-size: 12px; background-color: transparent;")
        perimeter_header.addWidget(perimeter_label_title)
        perimeter_header.addStretch()

        self.taxonomy_button = QtWidgets.QPushButton()
        self.taxonomy_button.setIcon(qta.icon('fa5s.sitemap', color='white'))
        self.taxonomy_button.setText("  Définir le Périmètre")
        self.taxonomy_button.clicked.connect(self._on_define_taxonomy)
        self.taxonomy_button.setEnabled(False)
        self.taxonomy_button.setFixedWidth(180)
        self.taxonomy_button.setFixedHeight(32)

        perimeter_header.addWidget(self.taxonomy_button)
        perimeter_container.addLayout(perimeter_header)

        perimeter_display_layout = QtWidgets.QVBoxLayout()
        self.perimeter_status_label = QtWidgets.QLabel("Aucun périmètre défini")
        self.perimeter_status_label.setStyleSheet("font-size: 13px; color: #888888; font-style: italic; background-color: transparent;")
        perimeter_display_layout.addWidget(self.perimeter_status_label)

        self.perimeter_details_label = QtWidgets.QLabel()
        self.perimeter_details_label.setWordWrap(True)
        self.perimeter_details_label.setStyleSheet("background-color: transparent;")
        self.perimeter_details_label.setVisible(False)
        perimeter_display_layout.addWidget(self.perimeter_details_label)

        perimeter_container.addLayout(perimeter_display_layout)
        session_layout.addLayout(perimeter_container)

        # Boutons Action
        buttons_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("  Démarrer")
        self.start_button.setIcon(qta.icon('fa5s.play', color='white'))
        self.start_button.clicked.connect(self._on_start_session)

        self.export_button = QtWidgets.QPushButton("  Export")
        self.export_button.setIcon(qta.icon('fa5s.download', color='white'))
        self.export_button.clicked.connect(self._on_export_results)
        self.export_button.setEnabled(False)

        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.export_button)
        session_layout.addLayout(buttons_layout)
        session_layout.addStretch()
        left_column.addWidget(self.session_group)

        # Statut
        status_container = QtWidgets.QVBoxLayout()
        status_header = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel()
        status_icon.setPixmap(qta.icon('fa5s.info-circle', color='#666').pixmap(16, 16))
        status_header.addWidget(status_icon)

        self.status_label = QtWidgets.QLabel("Prêt")
        self.status_label.setStyleSheet("color: #333; font-weight: bold; font-size: 11px; background-color: transparent;")
        status_header.addWidget(self.status_label)
        status_header.addStretch()
        status_container.addLayout(status_header)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(18)
        status_container.addWidget(self.progress_bar)
        left_column.addLayout(status_container)

        if self.base_width < 1200:
            # Petit écran : 40/60 (inchangé, car déjà adapté)
            content_layout.addLayout(left_column, 4)
        else:
            # Grand écran : 35/65 (augmentation de 30→35)
            content_layout.addLayout(left_column, 7) 

        # ===== COLONNE MILIEU : Graphe (70%) =====
        graph_container = QtWidgets.QWidget()
        graph_container_layout = QtWidgets.QVBoxLayout(graph_container)
        graph_container_layout.setContentsMargins(0, 0, 0, 0)

        self.graph_group = QtWidgets.QGroupBox("Graphe des Relations")
        graph_layout = QtWidgets.QVBoxLayout(self.graph_group)
        graph_layout.setContentsMargins(10, 10, 10, 10)

        self.graph_widget = GraphWidget(
            config_provider=None,
            conductor=self.conductor,
            dgraph_connector=self.dgraph_connector,
            parent=self
        )
        graph_layout.addWidget(self.graph_widget)

        graph_container_layout.addWidget(self.graph_group)

        # ===== BOUTON TOGGLE SNIPPETS MODERNE (Widget personnalisé) =====
        self.toggle_snippets_button = QtWidgets.QWidget()
        # ✅ RESPONSIVE : Hauteur adaptative
        button_height = min(140, int(self.base_height * 0.15))
        self.toggle_snippets_button.setMinimumSize(36, 100)
        self.toggle_snippets_button.setMaximumSize(36, button_height)
        self.toggle_snippets_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_snippets_button.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                border: none;
                border-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QWidget:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """)

        # Layout interne du bouton
        button_layout = QtWidgets.QVBoxLayout(self.toggle_snippets_button)
        button_layout.setContentsMargins(0, 12, 0, 12)
        button_layout.setSpacing(8)
        button_layout.setAlignment(Qt.AlignCenter)

        # Icône chevron
        self.chevron_icon_label = QtWidgets.QLabel()
        self.chevron_icon_label.setAlignment(Qt.AlignCenter)
        self.chevron_icon_label.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(18, 18))
        button_layout.addWidget(self.chevron_icon_label)

        # Texte vertical "RÉSULTATS"
        self.toggle_button_text = QtWidgets.QLabel("R\nÉ\nS\nU\nL\nT\nA\nT\nS")
        self.toggle_button_text.setAlignment(Qt.AlignCenter)
        self.toggle_button_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 9px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }
        """)
        button_layout.addWidget(self.toggle_button_text)

        # Rendre le widget cliquable
        self.toggle_snippets_button.mousePressEvent = lambda event: self._toggle_snippets_panel()

        # Positionner le bouton en absolu sur le graphe
        self.toggle_snippets_button.setParent(graph_container)
        self.toggle_snippets_button.move(10, 80)
        self.toggle_snippets_button.raise_()

        # ===== PANNEAU DE SNIPPETS (Superposé, caché par défaut) =====
        self.snippets_panel = QtWidgets.QWidget()
        self.snippets_panel.setFixedWidth(0)
        self.snippets_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.97);
                border-left: 3px solid #D0D0D0;
                border-radius: 0px;
            }
        """)

        snippets_panel_layout = QtWidgets.QVBoxLayout(self.snippets_panel)
        snippets_panel_layout.setContentsMargins(15, 15, 15, 15)
        snippets_panel_layout.setSpacing(10)

        # En-tête du panneau avec ICÔNE HISTORIQUE
        snippets_header = QtWidgets.QHBoxLayout()
        snippets_title = QtWidgets.QLabel(f"💻 {tr('generated_code')}")
        snippets_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; background-color: transparent;")
        snippets_header.addWidget(snippets_title)
        snippets_header.addStretch()

        # ✅ BOUTON HISTORIQUE GLOBAL (une seule icône pour tous les snippets)
        self.global_history_button = QtWidgets.QPushButton()
        self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))
        self.global_history_button.setToolTip("Voir l'historique conversationnel de la session")
        self.global_history_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.global_history_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 6px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover:enabled {
                background: #f0f0f0;
                border-radius: 4px;
            }
            QPushButton:disabled {
                opacity: 0.3;
            }
        """)
        self.global_history_button.setIconSize(QtCore.QSize(20, 20))
        self.global_history_button.clicked.connect(self._toggle_global_history)
        self.global_history_button.setEnabled(True)  # Désactivé par défaut
        snippets_header.addWidget(self.global_history_button)

        # Badge compteur de snippets
        self.snippets_count_badge = QtWidgets.QLabel("0")
        self.snippets_count_badge.setStyleSheet(f"""
            background-color: {self.primary_color};
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        snippets_header.addWidget(self.snippets_count_badge)

        snippets_panel_layout.addLayout(snippets_header)

        # ===== ACCORDÉON HISTORIQUE GLOBAL (masqué par défaut) =====
        self.global_history_accordion = QtWidgets.QWidget()
        self.global_history_accordion.setVisible(False)
        self.global_history_accordion.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
        """)
        
        global_history_layout = QtWidgets.QVBoxLayout(self.global_history_accordion)
        global_history_layout.setContentsMargins(10, 10, 10, 10)
        global_history_layout.setSpacing(8)
        
        # Titre historique
        history_title = QtWidgets.QLabel("📜 Historique conversationnel")
        history_title.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
            color: #333;
            background: transparent;
        """)
        global_history_layout.addWidget(history_title)
        
        # Zone scrollable pour l'historique
        history_scroll = QtWidgets.QScrollArea()
        history_scroll.setWidgetResizable(True)
        history_scroll.setMaximumHeight(300)
        history_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        history_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)
        
        self.global_history_content = QtWidgets.QWidget()
        self.global_history_layout = QtWidgets.QVBoxLayout(self.global_history_content)
        self.global_history_layout.setSpacing(6)
        self.global_history_layout.setContentsMargins(0, 0, 0, 0)
        
        history_scroll.setWidget(self.global_history_content)
        global_history_layout.addWidget(history_scroll)
        
        snippets_panel_layout.addWidget(self.global_history_accordion)

        # Zone scrollable pour les snippets
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Container pour les snippets
        self.snippets_container = QtWidgets.QWidget()
        self.snippets_layout = QtWidgets.QVBoxLayout(self.snippets_container)
        self.snippets_layout.setSpacing(12)
        self.snippets_layout.setContentsMargins(5, 5, 5, 5)
        self.snippets_layout.addStretch()

        scroll_area.setWidget(self.snippets_container)
        snippets_panel_layout.addWidget(scroll_area)

        # Label initial
        self.no_snippets_label = QtWidgets.QLabel(tr("no_code_generated"))
        self.no_snippets_label.setAlignment(Qt.AlignCenter)
        self.no_snippets_label.setStyleSheet("""
            font-size: 13px;
            color: #999;
            font-style: italic;
            padding: 60px 20px;
            background-color: transparent;
        """)
        self.snippets_layout.insertWidget(0, self.no_snippets_label)

        # Positionner le panneau snippets par-dessus le graphe
        self.snippets_panel.setParent(graph_container)
        self.snippets_panel.raise_()

        if self.base_width < 1200:
            content_layout.addWidget(graph_container, 6)
        else:
            content_layout.addWidget(graph_container, 13)

        main_layout.addWidget(main_content)

        # Connecter le resize
        graph_container.resizeEvent = self._on_graph_container_resize

    def _toggle_global_history(self):
        """Affiche/cache l'accordéon d'historique global"""
        if self.global_history_accordion.isVisible():
            self.global_history_accordion.setVisible(False)
            self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))
        else:
            self._populate_global_history()
            self.global_history_accordion.setVisible(True)
            self.global_history_button.setIcon(qta.icon('fa5s.chevron-up', color='#4CAF50'))

    def _populate_global_history(self):
        """Remplit l'historique global - VERSION TOUJOURS ACCESSIBLE"""
        # Nettoyer le contenu existant
        while self.global_history_layout.count():
            item = self.global_history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # ✅ NOUVEAU : Afficher même si vide
        if not hasattr(self, 'conversation_history') or not self.conversation_history:
            no_history = QtWidgets.QLabel("Aucune session démarrée")
            no_history.setStyleSheet("""
                font-size: 11px;
                color: #999;
                font-style: italic;
                padding: 20px;
                background: transparent;
            """)
            no_history.setAlignment(Qt.AlignCenter)
            self.global_history_layout.addWidget(no_history)
            return

        messages = self.conversation_history.messages

        if not messages:
            no_history = QtWidgets.QLabel("Aucun message dans cette session\n\nLancez une génération pour commencer")
            no_history.setStyleSheet("""
                font-size: 11px;
                color: #999;
                font-style: italic;
                padding: 20px;
                background: transparent;
            """)
            no_history.setAlignment(Qt.AlignCenter)
            self.global_history_layout.addWidget(no_history)
            return

        # ✅ AFFICHER TOUS LES MESSAGES AVEC SNIPPETS INTÉGRÉS
        for idx, message in enumerate(messages, 1):
            role = message.get('role', 'unknown')
            content = message.get('content', '')
            timestamp = message.get('timestamp', '')
            snippets = message.get('snippets', [])  # ✅ NOUVEAU

            # Conteneur message
            message_widget = QtWidgets.QWidget()
            message_widget.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                }
            """)

            message_layout = QtWidgets.QVBoxLayout(message_widget)
            message_layout.setContentsMargins(8, 8, 8, 8)
            message_layout.setSpacing(6)

            # En-tête message
            header_layout = QtWidgets.QHBoxLayout()
            header_layout.setSpacing(6)

            # Icône + rôle
            if role == 'user':
                role_icon = QtWidgets.QLabel("👤")
                role_text = "Utilisateur"
                role_color = "#2196F3"
            else:
                role_icon = QtWidgets.QLabel("🤖")
                role_text = "Assistant IA"
                role_color = "#4CAF50"

            role_icon.setStyleSheet("font-size: 14px; background: transparent;")
            header_layout.addWidget(role_icon)

            role_label = QtWidgets.QLabel(f"{role_text} - Message #{idx}")
            role_label.setStyleSheet(f"""
                font-size: 11px;
                font-weight: bold;
                color: {role_color};
                background: transparent;
            """)
            header_layout.addWidget(role_label)
            header_layout.addStretch()

            # Timestamp
            if timestamp:
                time_label = QtWidgets.QLabel(timestamp)
                time_label.setStyleSheet("""
                    font-size: 9px;
                    color: #999;
                    background: transparent;
                """)
                header_layout.addWidget(time_label)

            message_layout.addLayout(header_layout)

            # Contenu textuel
            if content:
                content_preview = content[:300] + "..." if len(content) > 300 else content

                content_label = QtWidgets.QLabel(content_preview)
                content_label.setStyleSheet("""
                    font-size: 10px;
                    color: #333;
                    background: transparent;
                    padding: 4px;
                """)
                content_label.setWordWrap(True)
                content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                message_layout.addWidget(content_label)

            # ✅ NOUVEAU : Afficher les snippets liés à ce message
            if snippets:
                snippets_header = QtWidgets.QLabel(f"📝 {len(snippets)} snippet(s) généré(s)")
                snippets_header.setStyleSheet("""
                    font-size: 10px;
                    color: #666;
                    font-weight: bold;
                    background: #f5f5f5;
                    padding: 4px 8px;
                    border-radius: 3px;
                    margin-top: 4px;
                """)
                message_layout.addWidget(snippets_header)

                # Afficher chaque snippet
                for snippet_idx, snippet in enumerate(snippets, 1):
                    snippet_title = snippet.get('title', 'Sans titre')
                    snippet_action = snippet.get('action', 'N/A')
                    snippet_file = snippet.get('file', 'N/A')

                    snippet_label = QtWidgets.QLabel(
                        f"  {snippet_idx}. [{snippet_action}] {snippet_title}\n"
                        f"     📄 {snippet_file}"
                    )
                    snippet_label.setStyleSheet("""
                        font-size: 9px;
                        color: #555;
                        background: transparent;
                        padding: 2px 4px;
                    """)
                    snippet_label.setWordWrap(True)
                    message_layout.addWidget(snippet_label)

            self.global_history_layout.addWidget(message_widget)

        # Spacer final
        self.global_history_layout.addStretch()

    def _update_history_button_state(self):
        """✅ TOUJOURS ACTIF maintenant"""
        # Le bouton est maintenant toujours actif
        self.global_history_button.setEnabled(True)

        if hasattr(self, 'conversation_history') and self.conversation_history:
            total = len(self.conversation_history.messages)
            if total > 0:
                self.global_history_button.setToolTip(f"Voir l'historique ({total} messages)")
            else:
                self.global_history_button.setToolTip("Historique (session vide)")
        else:
            self.global_history_button.setToolTip("Historique (aucune session)")

    def _switch_mode(self, is_browser_mode):
        """Change le mode avec messages traduits"""
        if self.is_browser_mode == is_browser_mode:
            return

        self.is_browser_mode = is_browser_mode
        self._update_switch_style()

        if is_browser_mode:
            message = tr("browser_mode_active")
        else:
            message = tr("api_mode_active")

        self.update_status(message, None)

    def _update_switch_style(self):
        """Met à jour le style visuel du switch selon le mode actif"""

        # Style actif : Gradient (comme bouton RÉSULTATS)
        active_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                color: white;
                border: none;
                border-radius: 17px;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """

        # Style inactif : Gris clair + texte noir
        inactive_style = """
            QPushButton {
                background-color: transparent;
                color: #333333;
                border: none;
                border-radius: 17px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: rgba(200, 200, 200, 0.3);
            }
        """
        if self.is_browser_mode:
            # Navigation Auto actif (par défaut)
            self.browser_mode_button.setStyleSheet(active_style)
            self.api_mode_button.setStyleSheet(inactive_style)
        else:
            # Mode API actif
            self.browser_mode_button.setStyleSheet(inactive_style)
            self.api_mode_button.setStyleSheet(active_style)

    def _on_start_session(self):
        """
        Lance une session de coding avec support Navigation Automatique amélioré
        VERSION AVEC EXTRACTION RÉELLE DE SNIPPETS
        """
        selected_platform_name = self.platforms_combo.currentData()

        """Démarrage avec messages traduits"""
        selected_platform_name = self.platforms_combo.currentData()

        if not selected_platform_name:
            self.update_status(tr("no_platform_selected"), 0)
            QtWidgets.QMessageBox.warning(
                self, 
                tr("no_platform_selected"),
                tr("select_platform")
            )
            return

        test_message = self.context_edit.toPlainText().strip()
        if not test_message:
            self.update_status(tr("empty_context"), 0)
            QtWidgets.QMessageBox.warning(
                self,
                tr("empty_context"),
                tr("context_placeholder")
            )
            return

        perimeter_data = self._build_perimeter_data()
        self._clear_snippets()

        if self.is_browser_mode:
            logger.info(f"🌐 Mode Navigation Automatique activé pour {selected_platform_name}")

            self.update_status(f"🌐 Initialisation de la navigation vers {selected_platform_name}...", 0)
            self.start_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

            # Utiliser le nouveau worker amélioré
            try:
                from core.orchestration.browser_navigation_worker import BrowserNavigationWorker

                self.current_worker = BrowserNavigationWorker(
                    platform_name=selected_platform_name,
                    context=test_message,
                    perimeter_data=perimeter_data,
                    parent=self
                )

            except ImportError as e:
                logger.error(f"❌ Worker amélioré introuvable: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Module manquant",
                    "Le module 'improved_browser_navigation_worker.py' est introuvable.\n\n"
                    "Fichiers requis:\n"
                    "• universal_browser_handler.py\n"
                    "• improved_browser_navigation_worker.py\n"
                    "• browser_helpers.py\n"
                    "• browserOs_conductor.py"
                )
                self.start_button.setEnabled(True)
                self.update_status("❌ Modules de navigation manquants", 0)
                return

            # Connecter les signaux
            self.current_worker.test_completed.connect(self._on_worker_completed)
            self.current_worker.step_update.connect(self._on_step_update_enhanced)
            self.current_worker.debug_info.connect(self._on_debug_info)

            if hasattr(self.current_worker, 'snippet_generated'):
                self.current_worker.snippet_generated.connect(self._add_snippet)
                logger.info("✅ Signal snippet_generated connecté")

            self.current_worker.finished.connect(self._on_worker_finished_generic)

            logger.info(f"🚀 Démarrage navigation vers {selected_platform_name}")
            self.current_worker.start()
            self.session_started.emit(1)

        else:
            # Mode API (code existant inchangé)
            logger.info(f"🔑 Mode API activé pour {selected_platform_name}")

            platform = self.platform_manager.get_platform(selected_platform_name)
            if not platform:
                self.update_status(f"Erreur: Plateforme {selected_platform_name} introuvable", 0)
                return

            is_valid, message = self.platform_manager.validate_api_key(selected_platform_name)
            if not is_valid:
                self.update_status(f"Erreur: {message}", 0)
                QtWidgets.QMessageBox.critical(
                    self, "Erreur Configuration",
                    f"{message}\nVeuillez configurer votre clé API."
                )
                return

            self.update_status(f"Initialisation de {platform.name}...", 0)
            self.start_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

            self.current_worker = self._create_worker_for_platform(
                platform, test_message, perimeter_data
            )

            if not self.current_worker:
                self.update_status(f"Erreur: Worker non disponible pour {platform.name}", 0)
                self.start_button.setEnabled(True)
                return

            self.current_worker.test_completed.connect(self._on_worker_completed)
            self.current_worker.step_update.connect(self._on_step_update)
            self.current_worker.debug_info.connect(self._on_debug_info)

            if hasattr(self.current_worker, 'snippet_generated'):
                self.current_worker.snippet_generated.connect(self._add_snippet)
                logger.info("✅ Signal snippet_generated connecté")

            self.current_worker.finished.connect(self._on_worker_finished_generic)

            logger.info(f"🚀 Démarrage de {platform.name} avec {len(perimeter_data)} éléments")
            self.current_worker.start()
            self.session_started.emit(1)

    def _on_step_update_enhanced(self, step_name, message):
        """
        Version améliorée du callback de progression
        Extrait le pourcentage depuis le message
        """
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown")

        # Extraire le pourcentage si présent
        import re
        match = re.search(r'\((\d+)%\)', message)
        if match:
            progress = int(match.group(1))
            self.progress_bar.setValue(progress)
            clean_message = message.replace(f'({progress}%)', '').strip()
            self.update_status(f"[{platform_name}] {clean_message}", progress)
        else:
            self.update_status(f"[{platform_name}] {message}")

    def _toggle_snippets_panel(self):
        """Affiche/Cache le panneau de snippets avec animation RESPONSIVE"""
        container = self.snippets_panel.parent()
        if not container:
            return

        container_width = container.width()
        container_height = container.height()

        # ✅ RESPONSIVE : Largeur adaptative selon la taille d'écran
        if container_width < 1400:
            target_percentage = 0.30  # 30% sur petits écrans
        elif container_width < 1920:
            target_percentage = 0.35  # 35% sur écrans moyens
        else:
            target_percentage = 0.40  # 40% sur grands écrans

        target_width = int(container_width * target_percentage) if not self.snippets_panel_visible else 0

        # Animation de la largeur
        self.animation = QPropertyAnimation(self.snippets_panel, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.snippets_panel.width())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Animation simultanée pour ajuster la géométrie
        def update_geometry(value):
            x_pos = container_width - value
            self.snippets_panel.setGeometry(x_pos, 0, value, container_height)

            # Repositionner le bouton
            if value > 0:
                button_x = x_pos - 36
            else:
                button_x = container_width - 46

            button_y = (container_height - 140) // 2
            self.toggle_snippets_button.move(button_x, max(80, button_y))

        self.animation.valueChanged.connect(update_geometry)

        # Changer l'icône du chevron
        if not self.snippets_panel_visible:
            self.chevron_icon_label.setPixmap(
                qta.icon('fa5s.chevron-right', color='white').pixmap(18, 18)
            )
            self.toggle_snippets_button.setToolTip("Masquer les snippets")
        else:
            self.chevron_icon_label.setPixmap(
                qta.icon('fa5s.chevron-left', color='white').pixmap(18, 18)
            )
            self.toggle_snippets_button.setToolTip("Afficher les snippets de code")

        self.snippets_panel_visible = not self.snippets_panel_visible
        self.animation.start()

        logger.info(f"Panneau snippets: {'ouvert' if self.snippets_panel_visible else 'fermé'} ({int(target_percentage*100)}%)")

    def _update_snippets_count(self):
        """Met à jour le badge compteur de snippets"""
        count = len(self.current_snippets)
        self.snippets_count_badge.setText(str(count))
        
        # ✅ TOUJOURS VISIBLE, juste changer la couleur
        if count == 0:
            self.snippets_count_badge.setStyleSheet("""
                background-color: #bbb;
                color: white;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            """)
        else:
            self.snippets_count_badge.setStyleSheet(f"""
                background-color: {self.primary_color};
                color: white;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            """)
    
    def _clear_snippets(self):
        """Efface tous les snippets affichés"""
        items_to_remove = []

        for i in range(self.snippets_layout.count()):
            item = self.snippets_layout.itemAt(i)
            widget = item.widget()

            if widget and widget != self.no_snippets_label:
                items_to_remove.append(widget)

        for widget in items_to_remove:
            self.snippets_layout.removeWidget(widget)
            widget.deleteLater()

        if hasattr(self, 'no_snippets_label') and self.no_snippets_label:
            try:
                self.no_snippets_label.setVisible(True)
            except RuntimeError:
                self._create_no_snippets_label()

        self.current_snippets = []
        self._update_snippets_count()
        
        # ✅ DÉSACTIVER LE BOUTON HISTORIQUE
        if hasattr(self, 'global_history_accordion'):
            self.global_history_accordion.setVisible(False)
            self.global_history_button.setIcon(qta.icon('fa5s.history', color='#4CAF50'))

        logger.info("Snippets cleared")

    def _on_graph_container_resize(self, event):
        """Repositionne le panneau snippets et le bouton lors du redimensionnement"""
        if hasattr(self, 'snippets_panel') and hasattr(self, 'toggle_snippets_button'):
            container = self.snippets_panel.parent()
            if container:
                panel_width = self.snippets_panel.width()
                container_width = container.width()
                container_height = container.height()

                # Positionner à droite
                x_pos = container_width - panel_width
                self.snippets_panel.setGeometry(x_pos, 0, panel_width, container_height)

                # Repositionner le bouton toggle
                if self.snippets_panel_visible:
                    button_x = x_pos - 36  # Largeur du bouton
                else:
                    button_x = container_width - 46  # 10px de marge

                # Centrer verticalement
                button_y = (container_height - 140) // 2
                self.toggle_snippets_button.move(button_x, max(80, button_y))

        QtWidgets.QWidget.resizeEvent(self.snippets_panel.parent(), event)

    def resizeEvent(self, event):
        """Gestion responsive améliorée"""
        super().resizeEvent(event)

        current_width = self.width()
        current_height = self.height()
        self._detect_screen_mode()

        # 🔄 Ajuster context_edit dynamiquement
        if hasattr(self, 'context_edit'):
            if current_height < 700:
                # Petit écran : réduire la hauteur max
                self.context_edit.setMaximumHeight(int(current_height * 0.25))
            else:
                # Grand écran : hauteur normale
                self.context_edit.setMaximumHeight(int(current_height * 0.35))

        # 🔄 Ajuster les proportions colonnes en live
        if hasattr(self, 'left_column') and hasattr(self, 'graph_container'):
            # Forcer une mise à jour du layout
            self.update()

        # 🔄 Repositionner le panneau snippets
        if hasattr(self, 'snippets_panel') and self.snippets_panel_visible:
            container = self.snippets_panel.parent()
            if container:
                container_width = container.width()

                # Pourcentage adaptatif selon largeur
                if container_width < 1000:
                    target_percentage = 0.40  # 40% sur très petit écran
                elif container_width < 1400:
                    target_percentage = 0.35  # 35% sur petit écran
                elif container_width < 1920:
                    target_percentage = 0.30  # 30% sur écran moyen
                else:
                    target_percentage = 0.25  # 25% sur grand écran

                new_width = int(container_width * target_percentage)
                self.snippets_panel.setMaximumWidth(new_width)
                self.snippets_panel.setGeometry(
                    container_width - new_width,
                    0,
                    new_width,
                    container.height()
                )

        # 🔄 Repositionner le bouton toggle
        if hasattr(self, 'toggle_snippets_button'):
            container = self.snippets_panel.parent() if hasattr(self, 'snippets_panel') else None
            if container:
                panel_width = self.snippets_panel.width() if self.snippets_panel_visible else 0
                container_width = container.width()
                container_height = container.height()

                if self.snippets_panel_visible:
                    button_x = container_width - panel_width - 36
                else:
                    button_x = container_width - 46

                # Centrer verticalement (avec hauteur adaptative du bouton)
                button_height = self.toggle_snippets_button.height()
                button_y = max(80, (container_height - button_height) // 2)

                self.toggle_snippets_button.move(button_x, button_y)

    def _detect_screen_mode(self):
        """Détecte le mode d'affichage selon la taille d'écran"""
        width = self.width()

        if width < 1024:
            # Mode TRÈS compact
            self.session_group.setVisible(True)
            self.graph_group.setVisible(True)
            # Forcer les colonnes en vertical si nécessaire
            logger.info("🖥️ Mode COMPACT activé")

        elif width < 1366:
            # Mode compact
            logger.info("🖥️ Mode NORMAL-COMPACT activé")

        else:
            # Mode normal
            logger.info("🖥️ Mode LARGE activé")

    def _create_no_snippets_label(self):
        """Crée ou recrée le label 'aucun snippet'"""
        if hasattr(self, 'no_snippets_label') and self.no_snippets_label:
            try:
                self.no_snippets_label.deleteLater()
            except RuntimeError:
                pass
            
        self.no_snippets_label = QtWidgets.QLabel("Aucun code généré")
        self.no_snippets_label.setAlignment(Qt.AlignCenter)
        self.no_snippets_label.setStyleSheet("""
            font-size: 13px;
            color: #999;
            font-style: italic;
            padding: 40px;
        """)

        self.snippets_layout.insertWidget(0, self.no_snippets_label)
        logger.debug("no_snippets_label created")

    def _add_snippet(self, snippet_data):
        """Ajoute un snippet à l'affichage"""
        if hasattr(self, 'no_snippets_label') and self.no_snippets_label:
            try:
                self.no_snippets_label.setVisible(False)
            except RuntimeError:
                logger.warning("no_snippets_label was already deleted")
    
        snippet_card = SnippetCard(snippet_data, self)
        snippet_card.copy_requested.connect(self._copy_to_clipboard)
        snippet_card.expand_requested.connect(self._expand_snippet)
        snippet_card.vscode_requested.connect(self._on_vscode_merge)
    
        insert_position = self.snippets_layout.count() - 1
        if insert_position < 0:
            insert_position = 0
    
        self.snippets_layout.insertWidget(insert_position, snippet_card)
        self.current_snippets.append(snippet_data)
        self._update_snippets_count()
        
        # ✅ ACTIVER LE BOUTON HISTORIQUE
        if hasattr(self, 'conversation_history') and self.conversation_history:
        # Ajouter le snippet au dernier message assistant
            if self.conversation_history.messages:
                last_message = self.conversation_history.messages[-1]
                
                # Si le dernier message est de l'assistant, y ajouter le snippet
                if last_message.get('role') == 'assistant':
                    if 'snippets' not in last_message:
                        last_message['snippets'] = []
                    
                    last_message['snippets'].append(snippet_data)
                    logger.info(f"✅ Snippet enregistré dans l'historique (message #{len(self.conversation_history.messages)})")
                else:
                    # Sinon créer un nouveau message assistant avec le snippet
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    
                    assistant_message = {
                        'role': 'assistant',
                        'content': f"Snippet généré : {snippet_data.get('title', 'Sans titre')}",
                        'timestamp': timestamp,
                        'snippets': [snippet_data]
                    }
                    
                    self.conversation_history.add_message(
                        role='assistant',
                        content=assistant_message['content']
                    )
                    
                    # Ajouter les snippets au message créé
                    self.conversation_history.messages[-1]['snippets'] = [snippet_data]
                    logger.info(f"✅ Nouveau message assistant créé avec snippet")
        
        self._update_snippets_count()
        self._update_history_button_state()
    
        # Ouvrir automatiquement le panneau si c'est le premier snippet
        if len(self.current_snippets) == 1 and not self.snippets_panel_visible:
            self._toggle_snippets_panel()
    
        logger.info(f"Snippet ajouté: {snippet_data.get('action')} - {snippet_data.get('title')}")
    
    def _on_ide_integration_requested(self, snippet_data):
        """Gère la demande d'intégration IDE d'un snippet"""
        logger.info(f"Demande d'intégration IDE pour: {snippet_data.get('title')}")
        
        # Émettre le signal pour que main_window puisse le capter
        self.snippet_selected.emit(snippet_data)
        
        # Afficher une notification
        QtWidgets.QMessageBox.information(
            self,
            "Intégration IDE",
            f"Snippet '{snippet_data.get('title')}' prêt pour l'intégration.\n\n"
            f"Allez dans l'onglet 'IDE' pour configurer et lancer l'intégration."
        )
        
        # Optionnel: Basculer automatiquement vers l'onglet IDE
        parent = self.parent()
        while parent and not hasattr(parent, 'tab_widget'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'tab_widget'):
            # Trouver l'index de l'onglet IDE
            for i in range(parent.tab_widget.count()):
                widget = parent.tab_widget.widget(i)
                if hasattr(widget, '__class__') and widget.__class__.__name__ == 'IDEPanel':
                    parent.tab_widget.setCurrentIndex(i)
                    break

    def _expand_snippet(self, snippet_data):
        """Ouvre le snippet dans une popup plein écran"""
        dialog = CodePopupDialog(snippet_data, self)
        dialog.exec_()

    def _on_worker_completed(self, success, message, duration, response):
        """Gère la complétion du worker avec support snippets"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")

        logger.info(f"{platform_name} completed. Success: {success}, Duration: {duration:.2f}s")

        if self.ai_usage_widget and hasattr(sender_worker, 'usage_stats'):
            usage_stats = sender_worker.usage_stats
            self.ai_usage_widget.record_ai_request(
                platform_name=platform_name,
                input_tokens=usage_stats.get('input_tokens', 0),
                output_tokens=usage_stats.get('output_tokens', 0),
                success=success,
                duration=duration
            )
            logger.info(f"📊 Usage recorded: {usage_stats.get('input_tokens', 0) + usage_stats.get('output_tokens', 0)} tokens")

        if success:
            if response and isinstance(response, dict):
                snippets = response.get('snippets', [])
                snippet_count = len(snippets)
                
                self.update_status(
                    tr("snippets_generated").format(snippet_count, platform_name, duration),
                    100
                )
            else:
                self.update_status(
                    tr("code_generated_success").format(platform_name, duration),
                    100
                )
        else:
            self.update_status(tr("error_occurred").format(platform_name, message), 0)
            QtWidgets.QMessageBox.critical(
                self,
                f"Erreur {platform_name}",
                f"Erreur lors de la génération du code:\n{message}"
            )
            self.progress_bar.setValue(0)

        self.start_button.setEnabled(True)

    def _copy_to_clipboard(self, text):
        """Copie le texte dans le presse-papier"""
        try:
            pyperclip.copy(text)
            QtWidgets.QMessageBox.information(
                self,
                "Copié",
                "Le code a été copié dans le presse-papier !"
            )
            logger.info("Code copié dans le presse-papier")
        except Exception as e:
            logger.error(f"Erreur lors de la copie: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de copier: {str(e)}"
            )

    def _on_export_results(self):
        """Exporte tous les snippets générés"""
        logger.info("Export snippets button clicked.")
        
        if not self.current_snippets:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun snippet",
                "Aucun snippet à exporter."
            )
            return
        
        project_name = ""
        if self.project_combo.currentIndex() > 0:
            project_name = self.current_project_data.get('name', 'project')
        
        session_name = project_name if project_name else "coding_snippets"
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter les snippets",
            f"{session_name}_{int(time.time())}.md",
            "Markdown (*.md);;JSON (*.json);;Tous les fichiers (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_snippets, f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Snippets de Code - {session_name}\n\n")
                    f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"**Nombre de snippets:** {len(self.current_snippets)}\n\n")
                    f.write("---\n\n")
                    
                    for i, snippet in enumerate(self.current_snippets, 1):
                        f.write(f"## Snippet {i}: {snippet.get('title', 'Sans titre')}\n\n")
                        f.write(f"**Action:** {snippet.get('action', 'N/A')}\n")
                        f.write(f"**Fichier:** `{snippet.get('file', 'Non spécifié')}`\n")
                        
                        target = snippet.get('target')
                        if target:
                            f.write(f"**Cible:** `{target}`\n")
                        
                        description = snippet.get('description', '')
                        if description:
                            f.write(f"\n**Description:**\n{description}\n")
                        
                        code = snippet.get('code', '')
                        language = snippet.get('language', 'python')
                        if code:
                            f.write(f"\n**Code:**\n```{language}\n{code}\n```\n")
                        
                        f.write("\n---\n\n")
            
            QtWidgets.QMessageBox.information(
                self,
                "Export réussi",
                f"Les snippets ont été exportés dans:\n{file_path}"
            )
            logger.info(f"Snippets exportés: {file_path}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur d'export",
                f"Impossible d'exporter les snippets:\n{str(e)}"
            )

    # ===== MÉTHODES EXISTANTES (inchangées) =====
    
    def _create_worker_for_platform(self, platform, context, perimeter_data):
        """Crée le worker approprié selon la plateforme sélectionnée"""
        api_key = platform.api_key

        project_name = None
        if self.current_project_data:
            project_name = self.current_project_data.get('name', 'Unknown Project')

        if platform.internal_name == 'gemini':
            from ui.widgets.workers.gemini_worker import GeminiWorker
            worker = GeminiWorker(
                context=context,
                perimeter_data=perimeter_data,
                api_key=api_key,
                dgraph_connector=self.dgraph_connector,
                conversation_history=self.conversation_history
            )
            worker.platform_name = platform.name
            worker.project_name = project_name
            return worker

        elif platform.internal_name == 'claude':
            from ui.widgets.workers.claud_worker import ClaudeWorker
            worker = ClaudeWorker(
                context=context,
                perimeter_data=perimeter_data,
                api_key=api_key,
                dgraph_connector=self.dgraph_connector,
                conversation_history=self.conversation_history
            )
            worker.platform_name = platform.name
            worker.project_name = project_name
            return worker

        elif platform.internal_name == 'chatgpt':
            try:
                from ui.widgets.workers.openai_worker import OpenAIWorker
                worker = OpenAIWorker(
                    context=context,
                    perimeter_data=perimeter_data,
                    api_key=api_key,
                    dgraph_connector=self.dgraph_connector,
                    conversation_history=self.conversation_history
                )
                worker.platform_name = platform.name
                worker.project_name = project_name
                return worker
            except ImportError:
                logger.error("ChatGPTWorker non disponible")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Worker non disponible",
                    "Le worker ChatGPT n'est pas encore implémenté."
                )
                return None

        elif platform.internal_name == 'grok':
            try:
                from ui.widgets.workers.grok_worker import GrokWorker
                worker = GrokWorker(
                    context=context,
                    perimeter_data=perimeter_data,
                    api_key=api_key,
                    dgraph_connector=self.dgraph_connector,
                    conversation_history=self.conversation_history
                )
                worker.platform_name = platform.name
                worker.project_name = project_name
                return worker
            except ImportError:
                logger.error("GrokWorker non disponible")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Worker non disponible",
                    "Le worker Grok n'est pas encore implémenté."
                )
                return None

        else:
            logger.error(f"Plateforme non supportée: {platform.internal_name}")
            return None

    def clear_conversation_history(self):
        """Efface l'historique de conversation"""
        if self.conversation_history:
            self.conversation_history.clear()
            logger.info("✅ Historique de conversation effacé")
            QtWidgets.QMessageBox.information(
                self,
                "Historique effacé",
                "L'historique de conversation a été réinitialisé."
            )

    def export_conversation_history(self):
        """Exporte l'historique de conversation"""
        if not self.conversation_history or not self.conversation_history.messages:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun historique",
                "L'historique de conversation est vide."
            )
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter l'historique",
            f"conversation_history_{int(time.time())}.json",
            "JSON (*.json)"
        )

        if file_path:
            try:
                self.conversation_history.export_to_json(file_path)
                QtWidgets.QMessageBox.information(
                    self,
                    "Export réussi",
                    f"Historique exporté vers:\n{file_path}"
                )
            except Exception as e:
                logger.error(f"Erreur export historique: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'exporter l'historique:\n{str(e)}"
                )

    def show_conversation_summary(self):
        """Affiche un résumé de l'historique"""
        if not self.conversation_history:
            return

        summary = self.conversation_history.get_summary()

        message = f"""
📊 Résumé de l'historique de conversation

• Total messages: {summary['message_count']}
• Messages utilisateur: {summary['user_messages']}
• Messages assistant: {summary['assistant_messages']}
• Durée de session: {summary['session_duration_minutes']:.1f} min
• Âge du message le plus ancien: {summary['oldest_message_age_minutes']:.1f} min
"""

        QtWidgets.QMessageBox.information(
            self,
            "Historique de conversation",
            message
        )

    def _load_projects_list(self):
        """
        ✅ VERSION CORRIGÉE : Charge via query_workspaces() avec labels
        """
        if not self.dgraph_connector.client:
            if not self.dgraph_connector.connect():
                logger.warning("Cannot connect to Dgraph")
                return
    
        logger.info("\n" + "="*80)
        logger.info("📂 CHARGEMENT PROJETS")
        logger.info("="*80)
    
        # ✅ UTILISER query_workspaces() qui utilise labels
        result = self.dgraph_connector.query_workspaces()
    
        if not result or 'q' not in result:
            logger.info("⚠️ Aucun workspace trouvé dans Dgraph")
            return
    
        workspaces = result.get('q', [])
        logger.info(f"📦 {len(workspaces)} workspace(s) trouvé(s)")
    
        if not workspaces:
            logger.info("⚠️ Aucun projet valide")
            return
    
        # ✅ Stocker dans self.project_profiles
        if not hasattr(self, 'project_profiles'):
            self.project_profiles = {}
    
        # ✅ Convertir workspaces en profiles
        for workspace in workspaces:
            ws_name = workspace.get('name')
            if not ws_name:
                continue
            
            # ✅ Normaliser la structure
            cm = workspace.get('clusterManagement', {})
            clusters = cm.get('clusters', [])
    
            # Créer turing_ontology depuis clusters
            profile_data = {
                'name': ws_name,
                'uid': workspace.get('uid'),
                'turing_ontology': {
                    'clusters_detailed': clusters
                }
            }
    
            self.project_profiles[ws_name] = profile_data
    
        logger.info(f"✅ {len(self.project_profiles)} profil(s) chargé(s)")
    
        # ✅ Remplir la combo
        self.project_combo.clear()
        self.project_combo.addItem(
            qta.icon('fa5s.folder-open', color='#999999'),
            tr("select_project"),
            None
        )
    
        for project_name, profile_data in self.project_profiles.items():
            logger.info(f"   ✅ Projet: {project_name}")
    
            # 🔍 DIAGNOSTIC : Vérifier la structure
            clusters = profile_data.get('turing_ontology', {}).get('clusters_detailed', [])
            logger.info(f"      - Clusters: {len(clusters)}")
    
            if clusters and len(clusters) > 0:
                first_cluster = clusters[0]
                cluster_name = first_cluster.get('name', 'N/A')
                
                # ✅ CORRECTION : Vérifier labels (relation directe)
                root_labels = first_cluster.get('root_labels', [])
                logger.info(f"      - 1er cluster: '{cluster_name}' ({len(root_labels)} root_labels)")
    
            self.project_combo.addItem(
                qta.icon('fa5s.project-diagram', color='#A23B2D'),
                f"📁 {project_name}",
                project_name
            )
    
        logger.info("="*80 + "\n")

    def _validate_project_data_structure(self, project_data):
        """Valide la structure de project_data - VERSION SIMPLIFIÉE"""
        if not project_data:
            return None

        print(f"\n{'='*60}")
        print(f"🔍 VALIDATION project_data")
        print(f"{'='*60}")

        # Vérifier clusterManagement
        if 'clusterManagement' not in project_data:
            print("❌ ERREUR: Pas de clusterManagement")
            return None

        cm = project_data['clusterManagement']

        if not isinstance(cm, dict):
            print("❌ ERREUR: clusterManagement n'est pas un dict")
            return None

        # Vérifier clusters
        if 'clusters' not in cm:
            print("❌ ERREUR: Pas de clusters dans clusterManagement")
            print(f"Keys disponibles: {list(cm.keys())}")
            return None

        clusters = cm['clusters']

        if not isinstance(clusters, list):
            print("❌ ERREUR: clusters n'est pas une liste")
            return None

        if len(clusters) == 0:
            print("⚠️ WARNING: Liste clusters vide")
            # Peut être valide si le projet n'a pas encore de clusters
            return project_data

        # Validation OK
        print(f"✅ Structure valide: {len(clusters)} clusters")

        for idx, cluster in enumerate(clusters[:2]):  # Vérifier les 2 premiers
            cluster_name = cluster.get('name', 'N/A')
            root_labels = cluster.get('root_labels', [])
            print(f"   Cluster {idx+1}: '{cluster_name}' - {len(root_labels)} root_labels")

        print(f"{'='*60}\n")
        return project_data

    def _on_project_selected(self, index):
        """
        ✅ VERSION CORRIGÉE : Aligne structure sur project_config_widget
        """
        if index <= 0:
            self.current_project_data = None
            self.taxonomy_button.setEnabled(False)
            self.selected_taxonomy = []
            self._update_perimeter_display()
            self.graph_widget._clear_graph()
            return

        project_name = self.project_combo.currentData()

        if not project_name or project_name not in self.project_profiles:
            logger.error(f"❌ Projet '{project_name}' introuvable")
            return

        logger.info(f"\n📊 SÉLECTION PROJET: {project_name}")

        # ✅ COPIE PROFONDE
        import json
        self.current_project_data = json.loads(json.dumps(self.project_profiles[project_name]))

        # ✅ NORMALISER LA STRUCTURE (turing_ontology uniquement)
        if 'turing_ontology' not in self.current_project_data:
            # Créer depuis clusterManagement si présent
            cm = self.current_project_data.get('clusterManagement', {})
            if cm and 'clusters' in cm:
                self.current_project_data['turing_ontology'] = {
                    'clusters_detailed': cm['clusters']
                }
                logger.info("✅ Structure normalisée : clusterManagement → turing_ontology")

        # ✅ VÉRIFIER CLUSTERS
        turing = self.current_project_data.get('turing_ontology', {})
        clusters = turing.get('clusters_detailed', [])

        logger.info(f"   📦 {len(clusters)} cluster(s) trouvé(s)")

        if len(clusters) == 0:
            logger.warning("⚠️ Projet vide")
            QtWidgets.QMessageBox.information(
                self,
                "Projet vide",
                f"Le projet '{project_name}' ne contient aucun cluster.\n\n"
                "Importez des données via l'onglet Configuration."
            )
            self.taxonomy_button.setEnabled(False)
            return

        # ✅ TOUT EST VALIDE
        self.taxonomy_button.setEnabled(True)
        self.graph_widget.current_project_data = self.current_project_data

        logger.info(f"✅ Projet '{project_name}' prêt avec {len(clusters)} clusters")

    def _on_define_taxonomy(self):
        """
        ✅ VERSION CORRIGÉE : Passe les données correctes au dialogue
        """
        if not self.current_project_data:
            QtWidgets.QMessageBox.warning(
                self, "Aucun projet",
                "Veuillez d'abord sélectionner un projet."
            )
            return

        # ✅ Vérifier turing_ontology
        turing = self.current_project_data.get('turing_ontology', {})
        clusters = turing.get('clusters_detailed', [])

        if not clusters:
            QtWidgets.QMessageBox.warning(
                self,
                "Projet vide",
                "Ce projet ne contient aucun cluster.\n\n"
                "Importez d'abord des données via l'onglet Configuration."
            )
            return

        logger.info(f"✅ Ouverture TaxonomyDialog avec {len(clusters)} clusters")

        # ✅ DIAGNOSTIC AVANT PASSAGE
        logger.info("📋 Structure passée au dialogue:")
        logger.info(f"   - Keys: {list(self.current_project_data.keys())}")
        logger.info(f"   - Clusters: {len(clusters)}")
        
        if clusters:
            first_cluster = clusters[0]
            logger.info(f"   - 1er cluster: '{first_cluster.get('name', 'N/A')}'")
            logger.info(f"   - Root labels: {len(first_cluster.get('root_labels', []))}")

        # ✅ Passer current_project_data directement
        dialog = TaxonomyDialog(self.current_project_data, self.dgraph_connector, self)
        dialog.graph_update_signal.connect(self._update_graph_from_taxonomy)
        dialog.selection_validated.connect(self._on_taxonomy_validated)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.selected_taxonomy = dialog.get_selected_taxonomy()
            self._update_perimeter_display()

            if self.selected_taxonomy:
                last_item = self.selected_taxonomy[-1]
                central_name = last_item.get('name', 'N/A')
                central_uid = last_item['data'].get('uid', '')
                related = last_item.get('related', [])

                if central_uid and related:
                    self._update_graph_from_taxonomy(
                        central_name, central_uid, related,
                        self.current_project_data
                    )

    def diagnose_project_data(self):
        """Diagnostic complet de project_data avant chargement."""
        print("\n" + "="*80)
        print("🔍 DIAGNOSTIC PROJECT_DATA")
        print("="*80)

        if not self.project_data:
            print("❌ project_data is None!")
            return False

        print(f"✅ project_data exists: {type(self.project_data)}")
        print(f"Keys: {list(self.project_data.keys())}")

        # Vérifier clusterManagement
        cm = self.project_data.get('clusterManagement')
        if not cm:
            print("❌ clusterManagement is None!")
            return False

        print(f"✅ clusterManagement exists: {type(cm)}")

        if not isinstance(cm, dict):
            print(f"❌ clusterManagement is not dict: {type(cm)}")
            return False

        print(f"clusterManagement keys: {list(cm.keys())}")

        # Vérifier clusters
        clusters = cm.get('clusters')
        if not clusters:
            print("❌ clusters is None or empty!")
            return False

        if not isinstance(clusters, list):
            print(f"❌ clusters is not list: {type(clusters)}")
            return False

        print(f"✅ clusters list: {len(clusters)} clusters")

        # Vérifier premier cluster
        if clusters:
            first_cluster = clusters[0]
            print(f"\n📦 First cluster:")
            print(f"  Name: {first_cluster.get('name', 'N/A')}")
            print(f"  Keys: {list(first_cluster.keys())}")

            root_labels = first_cluster.get('root_labels', [])
            print(f"  Root labels: {len(root_labels)}")

            if root_labels:
                first_label = root_labels[0]
                print(f"\n  📄 First root_label:")
                print(f"    Name: {first_label.get('name', 'N/A')}")
                print(f"    Keys: {list(first_label.keys())}")

                functions = first_label.get('functions', [])
                classes = first_label.get('classes', [])
                variables = first_label.get('variables', [])
                children = first_label.get('children', [])

                print(f"    Functions: {len(functions)}")
                print(f"    Classes: {len(classes)}")
                print(f"    Variables: {len(variables)}")
                print(f"    Children: {len(children)}")

        print("="*80)
        print("✅ DIAGNOSTIC OK - Données valides\n")
        return True

    def _on_taxonomy_validated(self, taxonomy_data):
        """Appelée quand l'utilisateur valide sa sélection"""
        self.selected_taxonomy = taxonomy_data
        self._update_perimeter_display()

        if taxonomy_data:
            last_item = taxonomy_data[-1]
            central_name = last_item.get('name', 'N/A')
            central_uid = last_item.get('uid', '')
            related = last_item.get('related', [])

            if central_uid and related:
                self._update_graph_from_taxonomy(
                    central_name, central_uid, related, 
                    self.current_project_data
                )


    def _update_graph_from_taxonomy(self, central_name, central_uid, related_items, project_data):
        """✅ CORRIGÉ : Route vers le bon mode avec validation"""
        if not central_name and not related_items:
            self.graph_widget._clear_graph()
            return
    
        try:
            # ✅ DÉTECTION MODE 1 : Sélection multiple → Relations de code
            if (related_items and 
                len(related_items) > 1 and
                all(isinstance(item, dict) and 'uid' in item for item in related_items)):
                
                logger.info(f"🕸️ MODE RELATIONS DE CODE : {len(related_items)} éléments")
                
                # ✅ VALIDATION : Vérifier que les UIDs existent
                valid_items = []
                for item in related_items:
                    uid = item.get('uid')
                    if uid:
                        valid_items.append(item)
                    else:
                        logger.warning(f"⚠️ Item sans UID ignoré: {item.get('name', 'N/A')}")
                
                if not valid_items:
                    logger.error("❌ Aucun item valide avec UID")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Erreur de sélection",
                        "Les éléments sélectionnés n'ont pas d'UID valide.\n\n"
                        "Essayez de recharger le projet."
                    )
                    return
                
                # ✅ APPELER avec items validés
                self.graph_widget.update_graph_with_code_relations(
                    selected_items=valid_items,
                    project_data=project_data
                )
                return
            
            # MODE 2 : Structure interne d'un fichier
            if (related_items and 
                len(related_items) == 1 and 
                isinstance(related_items[0], dict) and 
                related_items[0].get('mode') == 'internal_structure'):
                
                node_data = related_items[0].get('data', {})
                logger.info(f"📂 STRUCTURE INTERNE : {central_name}")
                
                self.graph_widget.update_graph_with_internal_structure(
                    central_node=central_name,
                    central_uid=central_uid,
                    node_data=node_data,
                    project_data=project_data
                )
                return
            
            # MODE 3 : Relations externes classiques
            logger.info(f"🔗 RELATIONS EXTERNES : {central_name}")
            
            self.graph_widget.update_graph(
                central_node=central_name,
                central_uid=central_uid,
                related_items=related_items,
                project_data=project_data
            )
    
        except Exception as e:
            logger.error(f"❌ Erreur graphe: {e}")
            import traceback
            traceback.print_exc()

    def _update_perimeter_display(self):
        """Met à jour l'affichage du périmètre défini avec boutons de suppression - INLINE"""
        if not self.selected_taxonomy:
            self.perimeter_status_label.setText(f"⚪ {tr('no_perimeter_defined')}")
            self.perimeter_details_label.setVisible(False)
            return

        count = len(self.selected_taxonomy)
        level = self.selected_taxonomy[0]['search_depth'] if self.selected_taxonomy else 1

        self.perimeter_status_label.setText(
            f"✅ {count} {tr('elements_selected')} • {tr('level')} {level}"
        )
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #2E7D32;
            font-weight: bold;
            background: transparent;
        """)

        # ✅ UTILISER DIRECTEMENT LE HTML DANS perimeter_details_label
        details_html = "<div style='line-height: 1.6;'>"

        # ✅ Créer une ligne HTML pour chaque élément avec bouton ×
        for idx, tax in enumerate(self.selected_taxonomy):
            node_name = tax['name']
            node_type = tax.get('type', 'unknown')
            icon = self._get_icon_for_type(node_type)

            # Ligne avec background hover simulé
            details_html += f"""
            <div style='
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 8px;
                margin: 4px 0;
                display: flex;
                align-items: center;
            '>
                <span style='font-size: 14px; margin-right: 8px;'>{icon}</span>
                <span style='color: #333; font-weight: bold; font-size: 11px;'>{node_name}</span>
                <span style='color: #888; font-size: 10px; margin-left: 8px;'>({node_type})</span>
                <span style='flex: 1;'></span>
                <a href='remove_{idx}' style='
                    color: #d32f2f;
                    text-decoration: none;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 2px 6px;
                    margin-left: 8px;
                ' title='Retirer {node_name}'>×</a>
            </div>
            """

        # ✅ Bouton "Tout effacer" en bas
        if len(self.selected_taxonomy) > 1:
            details_html += f"""
            <div style='text-align: right; margin-top: 8px;'>
                <a href='clear_all' style='
                    color: #d32f2f;
                    text-decoration: none;
                    border: 1px solid #d32f2f;
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: bold;
                    display: inline-block;
                '>🗑️ Tout effacer</a>
            </div>
            """

        details_html += "</div>"

        # Appliquer le HTML
        self.perimeter_details_label.setTextFormat(Qt.RichText)
        self.perimeter_details_label.setText(details_html)
        self.perimeter_details_label.setVisible(True)

        # ✅ Connecter les clics sur les liens
        self.perimeter_details_label.linkActivated.connect(self._handle_perimeter_link_click)

    def _handle_perimeter_link_click(self, link):
        """Gère les clics sur les liens dans l'affichage du périmètre"""
        if link.startswith('remove_'):
            # Extraire l'index
            try:
                index = int(link.replace('remove_', ''))
                self._remove_perimeter_item(index)
            except ValueError:
                logger.error(f"Index invalide: {link}")
        elif link == 'clear_all':
            self._clear_all_perimeter()

    def _clear_all_perimeter(self):
        """Efface tous les éléments du périmètre"""
        if not self.selected_taxonomy:
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            f"Voulez-vous retirer tous les {len(self.selected_taxonomy)} éléments du périmètre ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.selected_taxonomy.clear()
            logger.info("✅ Tous les éléments du périmètre ont été effacés")
            
            self._update_perimeter_display()
            self.graph_widget._clear_graph()
            
            QtWidgets.QMessageBox.information(
                self,
                "Périmètre effacé",
                "Tous les éléments ont été retirés du périmètre."
            )

    def _remove_perimeter_item(self, index):
        """Supprime un élément du périmètre sélectionné"""
        if 0 <= index < len(self.selected_taxonomy):
            removed_item = self.selected_taxonomy[index]
            node_name = removed_item.get('name', 'N/A')

            # Confirmation
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirmation",
                f"Voulez-vous retirer '{node_name}' du périmètre ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                # Supprimer l'élément
                self.selected_taxonomy.pop(index)
                logger.info(f"✅ Élément '{node_name}' retiré du périmètre")

                # Mettre à jour l'affichage
                self._update_perimeter_display()

                # Mettre à jour le graphe
                if self.selected_taxonomy:
                    # Afficher le graphe du dernier élément restant
                    last_item = self.selected_taxonomy[-1]
                    central_name = last_item.get('name', 'N/A')
                    central_uid = last_item['data'].get('uid', '')
                    related = last_item.get('related', [])

                    if central_uid and related:
                        self._update_graph_from_taxonomy(
                            central_name, central_uid, related,
                            self.current_project_data
                        )
                else:
                    # Plus d'éléments, effacer le graphe
                    self.graph_widget._clear_graph()

    def _get_icon_for_type(self, node_type: str) -> str:
        """Retourne une icône pour un type de nœud"""
        icon_map = {
            'file': '📄',
            'folder': '📁',
            'function': '⚙️',
            'class': '🔷',
            'variable': '🏷️',
            'dependency': '🔗',
            'unknown': '❓'
        }
        return icon_map.get(node_type, '•')

    def _build_perimeter_data(self) -> list:
        """
        ✅ VERSION FINALE : Récupération CODE + PATH avec stratégies de fallback multiples
        """
        perimeter_list = []

        if not self.selected_taxonomy:
            logger.warning("⚠️ Aucune taxonomie sélectionnée")
            return perimeter_list

        logger.info(f"\n{'='*80}")
        logger.info(f"📋 CONSTRUCTION DU PÉRIMÈTRE")
        logger.info(f"{'='*80}")
        logger.info(f"Éléments sélectionnés : {len(self.selected_taxonomy)}")

        for idx, tax_item in enumerate(self.selected_taxonomy, 1):
            name = tax_item.get('name', 'N/A')
            item_type = tax_item.get('type', 'unknown')
            uid = tax_item.get('data', {}).get('uid', '')

            logger.info(f"\n🔹 Élément {idx} : {name}")
            logger.info(f"   Type : {item_type}")
            logger.info(f"   UID : {uid}")

            # 🔧 INITIALISATION DES DONNÉES
            code_content = ""
            file_contents = ""
            description = ""
            path = ""
            classes_data = []
            functions_data = []
            variables_data = []

            # ✅ STRATÉGIE 1 : Récupérer path depuis taxonomy_data directement
            path = (tax_item.get('path') or 
                   tax_item.get('sourcePath') or 
                   tax_item.get('full_path') or 
                   tax_item.get('data', {}).get('path') or
                   tax_item.get('data', {}).get('sourcePath') or
                   tax_item.get('data', {}).get('full_path', ''))

            if path:
                logger.info(f"   ✅ Path trouvé dans taxonomy_data: {path}")
            else:
                logger.warning(f"   ⚠️ Path absent de taxonomy_data")

            # ✅ STRATÉGIE 2 : Recharger depuis Dgraph
            if uid and self.dgraph_connector and self.dgraph_connector.client:
                try:
                    # 🆕 REQUÊTE UNIVERSELLE avec relations directes ET inverses + path complet
                    query = f'''
                    {{
                      node(func: uid({uid})) {{
                        uid
                        name
                        nodeType
                        # ✅ TOUS LES CHAMPS PATH POSSIBLES
                        path
                        sourcePath
                        full_path
                        targetPath
                        description
                        fileContents
                        codeContent
                        docstring
                        line
                        params
                        returns
                        var_type
                        scope
                        bases
                        uses_vars

                        # ✅ CLASSES - directes ET inverses
                        classes {{
                          uid
                          name
                          description
                          line
                          codeContent
                          bases
                          uses_vars
                          path
                          sourcePath

                          methods {{
                            uid
                            name
                            description
                            line
                            codeContent
                            params
                            returns
                            docstring
                            path
                            sourcePath
                          }}

                          variables {{
                            uid
                            name
                            description
                            line
                            var_type
                            scope
                          }}
                        }}

                        ~classes {{
                          uid
                          name
                          description
                          line
                          codeContent
                          bases
                          uses_vars
                          path
                          sourcePath

                          methods {{
                            uid
                            name
                            description
                            line
                            codeContent
                            params
                            returns
                            docstring
                            path
                            sourcePath
                          }}

                          variables {{
                            uid
                            name
                            description
                            line
                            var_type
                            scope
                          }}
                        }}

                        # ✅ FUNCTIONS - directes ET inverses
                        functions {{
                          uid
                          name
                          description
                          line
                          codeContent
                          params
                          returns
                          docstring
                          path
                          sourcePath

                          variables {{
                            uid
                            name
                            description
                            line
                            var_type
                            scope
                          }}
                        }}

                        ~functions {{
                          uid
                          name
                          description
                          line
                          codeContent
                          params
                          returns
                          docstring
                          path
                          sourcePath

                          variables {{
                            uid
                            name
                            description
                            line
                            var_type
                            scope
                          }}
                        }}

                        # ✅ VARIABLES - directes ET inverses
                        variables {{
                          uid
                          name
                          description
                          line
                          var_type
                          scope
                        }}

                        ~variables {{
                          uid
                          name
                          description
                          line
                          var_type
                          scope
                        }}

                        # ✅ RÉCUPÉRER LE FICHIER PARENT (pour fonctions/méthodes)
                        ~functions {{
                          uid
                          name
                          path
                          sourcePath
                          full_path
                          fileContents
                          codeContent
                        }}

                        ~methods {{
                          uid
                          name
                          path
                          sourcePath

                          # Remonter au fichier via la classe
                          ~classes {{
                            uid
                            name
                            path
                            sourcePath
                            full_path
                            fileContents
                            codeContent
                          }}
                        }}

                        # ✅ Si c'est un nœud parent (Label/File)
                        ~label @filter(type(Function) OR type(Class) OR type(Variable)) {{
                          uid
                          name
                          nodeType
                          codeContent
                          description
                          line
                          path
                          sourcePath
                        }}
                      }}
                    }}
                    '''

                    txn = self.dgraph_connector.client.txn(read_only=True)
                    resp = txn.query(query)
                    txn.discard()

                    data = self.dgraph_connector._parse_response(resp)
                    nodes = data.get('node', [])

                    if nodes and len(nodes) > 0:
                        node = nodes[0]

                        # ✅ RÉCUPÉRATION UNIVERSELLE DU CODE
                        code_content = node.get('codeContent', '')
                        description = node.get('description', '')

                        # ✅ RÉCUPÉRATION PATH avec toutes les variantes
                        if not path:  # Si pas encore trouvé dans taxonomy_data
                            path = (node.get('path') or 
                                   node.get('sourcePath') or 
                                   node.get('full_path') or 
                                   node.get('targetPath', ''))

                            if path:
                                logger.info(f"   ✅ Path trouvé via Dgraph (nœud direct): {path}")

                        # ✅ FALLBACK 1 : Chercher dans le fichier parent (pour fonctions)
                        if not path:
                            parent_files = node.get('~functions', [])
                            if parent_files:
                                parent_path = (parent_files[0].get('path') or 
                                              parent_files[0].get('sourcePath') or 
                                              parent_files[0].get('full_path', ''))
                                if parent_path:
                                    path = parent_path
                                    logger.info(f"   ✅ Path trouvé via fichier parent (fonction): {path}")

                        # ✅ FALLBACK 2 : Chercher via classe parent (pour méthodes)
                        if not path:
                            parent_methods = node.get('~methods', [])
                            if parent_methods:
                                parent_class = parent_methods[0]
                                parent_files = parent_class.get('~classes', [])
                                if parent_files:
                                    parent_path = (parent_files[0].get('path') or 
                                                  parent_files[0].get('sourcePath') or 
                                                  parent_files[0].get('full_path', ''))
                                    if parent_path:
                                        path = parent_path
                                        logger.info(f"   ✅ Path trouvé via classe parent (méthode): {path}")

                        # 📊 DIAGNOSTIC
                        logger.info(f"   📊 Données Dgraph récupérées:")
                        logger.info(f"      - codeContent: {len(code_content)} chars")
                        logger.info(f"      - path: {path if path else 'MANQUANT'}")
                        logger.info(f"      - nodeType: {node.get('nodeType', 'N/A')}")

                        # 🔧 FUSION des classes directes + inverses
                        direct_classes = node.get('classes', [])
                        inverse_classes = node.get('~classes', [])
                        all_classes = direct_classes + inverse_classes

                        # Dédoublonner par UID
                        seen_uids = set()
                        unique_classes = []
                        for cls in all_classes:
                            cls_uid = cls.get('uid')
                            if cls_uid and cls_uid not in seen_uids:
                                seen_uids.add(cls_uid)
                                unique_classes.append(cls)

                        classes_data = unique_classes

                        # 🔧 FUSION des fonctions directes + inverses
                        direct_functions = node.get('functions', [])
                        inverse_functions = node.get('~functions', [])
                        all_functions = direct_functions + inverse_functions

                        seen_uids = set()
                        unique_functions = []
                        for func in all_functions:
                            func_uid = func.get('uid')
                            if func_uid and func_uid not in seen_uids:
                                seen_uids.add(func_uid)
                                unique_functions.append(func)

                        functions_data = unique_functions

                        # 🔧 FUSION des variables
                        direct_variables = node.get('variables', [])
                        inverse_variables = node.get('~variables', [])
                        all_variables = direct_variables + inverse_variables

                        seen_uids = set()
                        unique_variables = []
                        for var in all_variables:
                            var_uid = var.get('uid')
                            if var_uid and var_uid not in seen_uids:
                                seen_uids.add(var_uid)
                                unique_variables.append(var)

                        variables_data = unique_variables

                        # 📊 STATISTIQUES
                        logger.info(f"      - Classes: {len(classes_data)}")
                        logger.info(f"      - Functions: {len(functions_data)}")
                        logger.info(f"      - Variables: {len(variables_data)}")

                        # 🔧 POUR FONCTIONS/CLASSES : le code est dans le nœud lui-même
                        if item_type in ['function', 'class', 'method']:
                            if code_content:
                                file_contents = code_content
                                logger.info(f"   ✅ Code fonction/classe: {len(code_content)} chars")
                            else:
                                logger.error(f"   ❌ AUCUN codeContent pour {item_type} '{name}'")

                        # 🔧 POUR FICHIERS/LABELS : récupérer fileContents
                        if item_type not in ['function', 'class', 'variable', 'method']:
                            file_contents = node.get('fileContents', '')
                            logger.info(f"   📦 Fichier/Label: {len(file_contents)} chars")

                        # 🚨 VÉRIFICATION CRITIQUE PATH
                        if not path:
                            logger.error(f"   ❌ AUCUN PATH trouvé pour {item_type} '{name}' (UID: {uid})")
                            logger.error(f"      Clés disponibles : {list(node.keys())}")

                            # 🆕 FALLBACK ULTIME : Utiliser _get_function_path
                            logger.info(f"   🔄 Tentative _get_function_path() en dernier recours...")
                            from ui.widgets.tabs.taxonomy_dialog import TaxonomyDialog
                            # Créer une instance temporaire si nécessaire
                            if hasattr(self, 'taxonomy_dialog_instance'):
                                path = self.taxonomy_dialog_instance._get_function_path(uid, name)
                            else:
                                # Appeler directement la méthode si disponible
                                path = self._get_function_path_fallback(uid, name)

                            if path:
                                logger.info(f"   ✅ Path trouvé via fallback ultime: {path}")
                            else:
                                logger.error(f"   ❌ PATH DÉFINITIVEMENT INTROUVABLE")

                    else:
                        logger.warning(f"   ⚠️ Aucun nœud trouvé pour UID {uid}")

                except Exception as e:
                    logger.error(f"   ❌ Erreur récupération Dgraph : {e}")
                    import traceback
                    traceback.print_exc()

                    # Fallback sur données locales
                    code_content = tax_item.get('data', {}).get('codeContent', '')
                    file_contents = tax_item.get('data', {}).get('fileContents', '')
                    description = tax_item.get('data', {}).get('description', '')

                    if code_content or file_contents:
                        logger.info(f"   🔄 Fallback sur données locales réussi")

            else:
                logger.warning(f"   ⚠️ Pas d'UID ou Dgraph non connecté")
                # Utiliser les données locales
                code_content = tax_item.get('data', {}).get('codeContent', '')
                file_contents = tax_item.get('data', {}).get('fileContents', '')
                description = tax_item.get('data', {}).get('description', '')

            # 🗃️ CONSTRUIRE L'OBJET PERIMETER
            item_data = {
                'name': name,
                'type': item_type,
                'level': tax_item.get('level', 0),
                'search_depth': tax_item.get('search_depth', 1),
                'data': {
                    'uid': uid,
                    'path': path,  # ✅ PATH GARANTI
                    'sourcePath': path,  # ✅ Duplication pour compatibilité
                    'full_path': path,  # ✅ Duplication pour compatibilité
                    'description': description or tax_item.get('data', {}).get('description', ''),
                    'fileContents': file_contents,
                    'codeContent': code_content,
                    'classes': classes_data,
                    'functions': functions_data,
                    'variables': variables_data
                },
                'relations': [],
                'related': []
            }

            # 🔍 VÉRIFICATION FINALE
            final_code = item_data['data']['codeContent'] or item_data['data']['fileContents']
            final_path = item_data['data']['path']

            if final_code:
                logger.info(f"   ✅ Code final disponible : {len(final_code)} chars")
            else:
                logger.error(f"   ❌ AUCUN CODE RÉCUPÉRÉ pour {name}")

            if final_path:
                logger.info(f"   ✅ Path final : {final_path}")
            else:
                logger.error(f"   ❌ AUCUN PATH RÉCUPÉRÉ pour {name}")

            # 📊 TRAITER LES RELATIONS
            relations = tax_item.get('relations', [])
            for rel in relations:
                relation_obj = {
                    'source': rel.get('source', ''),
                    'target': rel.get('target', ''),
                    'relation_type': rel.get('relation_type', 'unknown'),
                    'source_uid': rel.get('source_uid', ''),
                    'target_uid': rel.get('target_uid', '')
                }
                item_data['relations'].append(relation_obj)

            perimeter_list.append(item_data)
            logger.info(f"   ✅ Élément ajouté au périmètre")

        # 📊 STATISTIQUES FINALES
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ PÉRIMÈTRE CONSTRUIT : {len(perimeter_list)} élément(s)")

        total_code_size = 0
        items_with_code = 0
        items_without_code = []
        items_with_path = 0
        items_without_path = []

        for item in perimeter_list:
            # Vérifier code
            code = item['data'].get('codeContent', '') or item['data'].get('fileContents', '')
            if code:
                total_code_size += len(code)
                items_with_code += 1
            else:
                items_without_code.append(f"{item['name']} ({item['type']})")

            # Vérifier path
            path = item['data'].get('path', '')
            if path:
                items_with_path += 1
            else:
                items_without_path.append(f"{item['name']} ({item['type']})")

        logger.info(f"   📊 Éléments avec code : {items_with_code}/{len(perimeter_list)}")
        logger.info(f"   📦 Taille totale du code : {total_code_size:,} caractères")
        logger.info(f"   📂 Éléments avec path : {items_with_path}/{len(perimeter_list)}")

        if items_without_code:
            logger.warning(f"   ⚠️ Éléments SANS code :")
            for item_name in items_without_code:
                logger.warning(f"      - {item_name}")

        if items_without_path:
            logger.error(f"   ❌ Éléments SANS path :")
            for item_name in items_without_path:
                logger.error(f"      - {item_name}")

        logger.info(f"{'='*80}\n")

        return perimeter_list
    
    def _get_function_path_fallback(self, uid: str, name: str) -> str:
        """
        ✅ FALLBACK ULTIME : Chercher le path via relations Dgraph
        """
        if not uid or not self.dgraph_connector:
            return ""
        
        logger.info(f"🔍 Fallback ultime pour path de '{name}'...")
        
        normalized_name = name.replace('F: ', '').replace('M: ', '').replace('C: ', '').strip()
        escaped = normalized_name.replace('"', '\\"')
        
        query = f"""
        {{
          by_source(func: type(Relation)) @filter(regexp(sourceName, /{escaped}/i)) {{
            sourceName
            sourcePath
          }}
          
          by_target(func: type(Relation)) @filter(regexp(targetName, /{escaped}/i)) {{
            targetName
            targetPath
          }}
        }}
        """
        
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = self.dgraph_connector._parse_response(resp)
            
            # Vérifier sourcePath
            for rel in data.get('by_source', []):
                source_name = rel.get('sourceName', '')
                source_path = rel.get('sourcePath', '')
                
                if source_name and source_path:
                    clean_source = source_name.replace('Function: ', '').replace('Method: ', '').strip()
                    if clean_source == normalized_name or normalized_name in clean_source:
                        # Nettoyer le path
                        clean_path = source_path
                        for marker in ['/Function:', '/Method:', '/Class:']:
                            if marker in clean_path:
                                clean_path = clean_path.split(marker)[0]
                                break
                            
                        if clean_path:
                            logger.info(f"   ✅ Path trouvé via relations (source): {clean_path}")
                            return clean_path
            
            # Vérifier targetPath
            for rel in data.get('by_target', []):
                target_name = rel.get('targetName', '')
                target_path = rel.get('targetPath', '')
                
                if target_name and target_path:
                    clean_target = target_name.replace('Function: ', '').replace('Method: ', '').strip()
                    if clean_target == normalized_name or normalized_name in clean_target:
                        # Nettoyer le path
                        clean_path = target_path
                        for marker in ['/Function:', '/Method:', '/Class:']:
                            if marker in clean_path:
                                clean_path = clean_path.split(marker)[0]
                                break
                            
                        if clean_path:
                            logger.info(f"   ✅ Path trouvé via relations (target): {clean_path}")
                            return clean_path
            
            logger.warning(f"   ⚠️ Aucun path trouvé via relations pour '{name}'")
            return ""
        
        except Exception as e:
            logger.error(f"   ❌ Erreur fallback path: {e}")
            return ""

    def diagnose_perimeter_data(self):
        if not self.selected_taxonomy:
            print("⚠️ Aucune taxonomie sélectionnée")
            return

        print("\n" + "="*80)
        print("🔍 DIAGNOSTIC DU PÉRIMÈTRE")
        print("="*80)

        perimeter = self._build_perimeter_data()

        print(f"\n📊 Résumé :")
        print(f"   • Éléments sélectionnés : {len(self.selected_taxonomy)}")
        print(f"   • Éléments dans perimeter_data : {len(perimeter)}")

        for idx, item in enumerate(perimeter, 1):
            name = item.get('name', 'N/A')
            code = item['data'].get('codeContent', '') or item['data'].get('fileContents', '')
            path = item['data'].get('path', 'N/A')

            print(f"\n   🔹 Élément {idx} : {name}")
            print(f"      Path : {path}")
            print(f"      Code : {'✅ ' + str(len(code)) + ' chars' if code else '❌ Vide'}")

            if code:
                lines = code.split('\n')[:10]
                print(f"      Aperçu :")
                for line in lines:
                    print(f"         {line[:70]}")
                if len(code.split('\n')) > 10:
                    print(f"         ... ({len(code.split('\n'))} lignes au total)")

        print("\n" + "="*80 + "\n")

    def _get_uid_by_name(self, node_name: str) -> str:
        """Récupère l'UID d'un nœud par son nom"""
        if not self.dgraph_connector or not node_name:
            return ''

        try:
            query = f'''
            {{
              node(func: eq(name, "{node_name}")) {{
                uid
                name
              }}
            }}
            '''

            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            data = self.dgraph_connector._parse_response(resp)
            nodes = data.get('node', [])

            if nodes:
                return nodes[0].get('uid', '')
            return ''

        except Exception as e:
            logger.error(f"Erreur récupération UID pour '{node_name}': {e}")
            return ''

    def _on_step_update(self, step_name, message):
        """Mise à jour des étapes"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown")
        self.update_status(f"[{platform_name}] {message}")

    def _on_debug_info(self, message):
        """Information de débogage"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown")
        logger.debug(f"[{platform_name} DEBUG] {message}")

    def _on_worker_finished_generic(self):
        """Appelée quand un worker est terminé"""
        if self.current_session_id:
            self.session_completed.emit(self.current_session_id)

        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown")
        logger.info(f"{platform_name} worker finished")

    def set_ai_usage_widget(self, ai_usage_widget):
        """Définit le widget d'utilisation IA"""
        self.ai_usage_widget = ai_usage_widget
        logger.info("AI Usage Widget linked to Coding Panel")

    def set_conductor(self, conductor):
        """Définit le chef d'orchestre"""
        self.conductor = conductor
        if self.graph_widget:
            self.graph_widget.conductor = conductor

    def set_platforms(self, profiles=None):
        """Plateformes SANS icônes - Affiche uniquement celles configurées"""
        self.platforms_combo.clear()
    
        # Premier item SANS icône
        self.platforms_combo.addItem(
            tr("select_platform"),
            None
        )
    
        platform_data = self.platform_manager.get_platform_for_combo()
        
        configured_count = 0  # Compteur de plateformes configurées
    
        for display_name, internal_name, color, icon in platform_data:
            # ✅ VÉRIFIER SI LA PLATEFORME EST CONFIGURÉE
            is_valid, _ = self.platform_manager.validate_api_key(internal_name)
            
            if is_valid:
                # Ajouter UNIQUEMENT si configurée
                self.platforms_combo.addItem(
                    display_name,
                    internal_name
                )
                configured_count += 1
                logger.info(f"✅ Plateforme configurée: {display_name}")
            else:
                logger.debug(f"⚠️ Plateforme ignorée (non configurée): {display_name}")
    
        # ✅ DÉSACTIVER LES CHECKBOXES POUR TOUS LES ITEMS
        model = self.platforms_combo.model()
        for i in range(self.platforms_combo.count()):
            index = model.index(i, 0)
            model.setData(index, QtCore.QVariant(), Qt.CheckStateRole)
            
            item = model.itemFromIndex(index)
            if item:
                item.setCheckable(False)
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
    
        # ✅ MESSAGE SI AUCUNE PLATEFORME CONFIGURÉE
        if configured_count == 0:
            logger.warning("⚠️ Aucune plateforme IA configurée")
            # Ajouter un message informatif
            self.platforms_combo.addItem(
                "❌ Aucune plateforme configurée",
                None
            )
            self.platforms_combo.setEnabled(False)
        else:
            logger.info(f"✅ {configured_count} plateforme(s) configurée(s) chargée(s)")
            self.platforms_combo.setEnabled(True)

    def update_status(self, message, progress=None):
        """Met à jour le statut"""
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)

    def new_session(self):
        """Crée une nouvelle session et efface l'historique"""
        self.project_combo.setCurrentIndex(0)
        self.context_edit.clear()
        self.platforms_combo.setCurrentIndex(0)
        self.selected_taxonomy = []
        self._update_perimeter_display()
        self.graph_widget._clear_graph()
        self._clear_snippets()
        
        if self.conversation_history:
            self.conversation_history.clear()
            logger.info("💬 Historique de conversation réinitialisé pour nouvelle session")
        
        self.current_session_id = None
        self.current_worker = None
        self.export_button.setEnabled(False)
        self.update_status("Nouvelle session créée")

    def load_file(self, file_path):
        """Charge une session depuis un fichier"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.context_edit.setPlainText(content)
            self.update_status(f"Fichier chargé: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Erreur chargement fichier: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Erreur de chargement",
                f"Impossible de charger le fichier: {str(e)}"
            )

    def refresh(self):
        """Rafraîchit le panneau"""
        self._load_projects_list()
        if self.graph_widget:
            self.graph_widget.refresh()
        logger.info("Coding panel refreshed")

    def _check_vscode_startup(self):
        """Vérifie la connexion VS Code au démarrage"""
        if self.vscode_integration.check_connection():
            logger.info("✅ VS Code connecté au démarrage")
            self._update_vscode_status_indicator(True)
        else:
            logger.info("ℹ️ VS Code non disponible")
            self._update_vscode_status_indicator(False)

    def _update_vscode_status_indicator(self, connected):
        """Met à jour l'indicateur visuel de connexion VS Code"""
        # Optionnel: Ajouter un petit indicateur dans la barre de statut
        if hasattr(self, 'status_label'):
            if connected:
                # Ne pas surcharger le status_label principal
                pass
            else:
                pass

    def _on_vscode_response(self, success, message):
        """Callback pour les réponses VS Code"""
        if success:
            logger.info(f"✅ VS Code: {message}")
            QtWidgets.QMessageBox.information(
                self,
                "VS Code - Succès",
                f"✅ {message}"
            )
        else:
            logger.error(f"❌ VS Code: {message}")
            QtWidgets.QMessageBox.warning(
                self,
                "VS Code - Erreur",
                f"❌ {message}\n\nVérifiez que l'extension Liris est installée et démarrée dans VS Code."
            )

    def _on_vscode_connection_changed(self, connected):
        """Callback pour les changements de connexion VS Code"""
        if connected:
            logger.info("✅ VS Code connecté")
            self._update_vscode_status_indicator(True)
        else:
            logger.warning("⚠️ VS Code déconnecté")
            self._update_vscode_status_indicator(False)

    def _on_vscode_merge(self, snippet_data):
        """Gère le merge dans VS Code - AVEC VALIDATION"""
        logger.info(f"🔀 Demande de merge VS Code: {snippet_data.get('title', 'N/A')}")
        
        # ✅ VALIDATION STRICTE
        action = snippet_data.get('action', '').upper()
        file_path = snippet_data.get('file', '').strip()
        code = snippet_data.get('code', '').strip()
        target = snippet_data.get('target', '').strip()
        position = snippet_data.get('position', '').strip().lower()
        
        if not file_path:
            logger.error("❌ Aucun chemin de fichier dans snippet_data")
            QtWidgets.QMessageBox.critical(
                self,
                "Données manquantes",
                "Le chemin du fichier n'est pas fourni par l'IA.\n\n"
                "Assurez-vous que l'IA inclut le champ 'file' dans sa réponse."
            )
            return
        
        if not code:
            logger.error("❌ Aucun code dans snippet_data")
            QtWidgets.QMessageBox.critical(
                self,
                "Données manquantes",
                "Le code n'est pas fourni par l'IA."
            )
            return
        
        # ✅ NOUVEAU : Validation TARGET + POSITION pour AJOUTER
        if action == 'AJOUTER':
            if not target:
                # Proposer à l'utilisateur de choisir
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Informations manquantes",
                    f"L'IA n'a pas spécifié où insérer le code dans '{file_path}'.\n\n"
                    "Voulez-vous l'insérer au début du fichier ?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.No:
                    # Demander le target à l'utilisateur
                    target, ok = QtWidgets.QInputDialog.getText(
                        self,
                        "Fonction/Classe de référence",
                        "Entrez le nom de la fonction ou classe de référence:\n"
                        "(Ex: 'def ma_fonction' ou 'class MaClasse')",
                        QtWidgets.QLineEdit.Normal,
                        ""
                    )
                    
                    if not ok or not target.strip():
                        logger.info("❌ Utilisateur a annulé")
                        return
                    
                    # Demander la position
                    positions = ['before', 'after', 'inside']
                    position, ok = QtWidgets.QInputDialog.getItem(
                        self,
                        "Position d'insertion",
                        "Où insérer le code par rapport à la référence ?",
                        positions,
                        1,  # Défaut: 'after'
                        False
                    )
                    
                    if not ok:
                        logger.info("❌ Utilisateur a annulé")
                        return
                    
                    # Mettre à jour snippet_data
                    snippet_data['target'] = target.strip()
                    snippet_data['position'] = position.lower()
                else:
                    # Insertion au début du fichier (lineNumber = 0)
                    snippet_data['target'] = ''
                    snippet_data['position'] = ''
                    snippet_data['lineNumber'] = 0
            
            # Si target fourni mais pas de position
            elif not position:
                positions = ['before', 'after', 'inside']
                position, ok = QtWidgets.QInputDialog.getItem(
                    self,
                    "Position d'insertion",
                    f"Où insérer le code par rapport à '{target}' ?",
                    positions,
                    1,  # Défaut: 'after'
                    False
                )
                
                if ok:
                    snippet_data['position'] = position.lower()
                else:
                    snippet_data['position'] = 'after'  # Défaut
            
            logger.info(f"📋 Action: {action}")
            logger.info(f"📁 File: {file_path}")
            logger.info(f"🎯 Target: {snippet_data.get('target', 'N/A')}")
            logger.info(f"📍 Position: {snippet_data.get('position', 'N/A')}")
            logger.info(f"💻 Code length: {len(code)} chars")
            
            self._vscode_insert(snippet_data)
        
        elif action in ['MODIFIER', 'REMPLACER']:
            # ... code existant pour REPLACE
            if not target:
                logger.error("❌ Action REPLACE sans target")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Données manquantes",
                    f"L'action '{action}' nécessite un champ 'target'."
                )
                return
            
            self._vscode_replace(snippet_data)

    def _prompt_file_path(self, snippet_data):
        """Demande le chemin du fichier à l'utilisateur"""
        # Suggérer un nom basé sur le contexte
        suggested_name = "code.py"

        # Essayer d'extraire depuis la description
        description = snippet_data.get('description', '')
        title = snippet_data.get('title', '')

        if description:
            # Chercher des patterns comme "dans fichier.py" ou "file: fichier.py"
            import re
            match = re.search(r'(?:dans|file:|fichier:)\s+([a-zA-Z0-9_/\\.]+\.py)', description)
            if match:
                suggested_name = match.group(1)

        # Utiliser le projet actuel si disponible
        if self.current_project_data:
            project_name = self.current_project_data.get('name', '')
            if project_name and '/' not in suggested_name:
                suggested_name = f"src/{suggested_name}"

        dialog = QtWidgets.QInputDialog(self)
        dialog.setWindowTitle("Chemin du fichier")
        dialog.setLabelText("Entrez le chemin du fichier (relatif au workspace VS Code):")
        dialog.setTextValue(suggested_name)
        dialog.resize(500, 150)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            file_path = dialog.textValue().strip()
            return file_path if file_path else None

        return None

    def _vscode_insert(self, snippet):
        """Insère du code via VS Code - VERSION CORRIGÉE avec TARGET + POSITION"""
        logger.info(f"📝 _vscode_insert démarré pour: {snippet.get('file', 'N/A')}")

        file_path = snippet.get('file', '').strip()
        code = snippet.get('code', '').strip()

        # ✅ NOUVEAUX CHAMPS
        target = snippet.get('target', '').strip()  # Fonction/classe de référence
        position = snippet.get('position', '').strip().lower()  # before/after/inside
        line_number = snippet.get('lineNumber', 0)

        # ✅ VALIDATION
        if not file_path:
            logger.error("❌ file_path manquant dans snippet")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                "Le chemin du fichier est manquant.\n"
                "L'IA doit fournir le champ 'file' dans sa réponse."
            )
            return

        if not code:
            logger.error("❌ code manquant dans snippet")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                "Le code est manquant.\n"
                "L'IA doit fournir le champ 'code' dans sa réponse."
            )
            return

        # ✅ CONSTRUCTION PAYLOAD ADAPTATIF
        payload = {
            "action": "insert",
            "filePath": file_path,
            "code": code
        }

        # ✅ SI TARGET FOURNI : Ajout contextuel avec position
        if target:
            if not position:
                logger.warning("⚠️ TARGET fourni sans POSITION, utilisation de 'after' par défaut")
                position = "after"

            payload["target"] = target
            payload["position"] = position

            logger.info(f"   📍 Insertion CONTEXTUELLE:")
            logger.info(f"      Target: {target}")
            logger.info(f"      Position: {position}")
        else:
            # ✅ SI PAS DE TARGET : Utiliser lineNumber (défaut début fichier)
            payload["lineNumber"] = line_number
            logger.info(f"   📍 Insertion SIMPLE à la ligne {line_number}")

        logger.info(f"📤 Payload VS Code:")
        logger.info(f"   - Action: {payload['action']}")
        logger.info(f"   - File: {payload['filePath']}")

        try:
            response = requests.post(
                f"{self.vscode_url}/update",
                json=payload,
                timeout=10
            )

            logger.info(f"📥 Réponse VS Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info("✅ Code inséré avec succès dans VS Code")

                    # Message adapté selon le mode
                    if target:
                        msg = f"✅ Code inséré {position} '{target}' dans:\n{file_path}"
                    else:
                        msg = f"✅ Code inséré à la ligne {line_number} dans:\n{file_path}"

                    QtWidgets.QMessageBox.information(self, "Succès", msg)
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"❌ Échec VS Code: {error_msg}")

                    if result.get('userCancelled'):
                        QtWidgets.QMessageBox.information(
                            self,
                            "Annulé",
                            "Opération annulée par l'utilisateur dans VS Code."
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Erreur VS Code",
                            f"Impossible d'insérer le code:\n{error_msg}"
                        )
            else:
                result = response.json() if response.content else {}
                error_msg = result.get('error', f'HTTP {response.status_code}')
                logger.error(f"❌ Erreur HTTP: {error_msg}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur serveur",
                    f"Le serveur VS Code a retourné une erreur:\n{error_msg}"
                )

        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout connexion VS Code")
            QtWidgets.QMessageBox.critical(
                self,
                "Timeout",
                "Le serveur VS Code ne répond pas (timeout)."
            )
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Impossible de se connecter à VS Code")
            QtWidgets.QMessageBox.critical(
                self,
                "Connexion impossible",
                f"Impossible de se connecter au serveur VS Code sur {self.vscode_url}.\n"
                "Vérifiez que l'extension Liris est active dans VS Code."
            )
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur inattendue:\n{str(e)}"
            )

    def _vscode_replace(self, snippet):
        """Remplace du code via VS Code - INCHANGÉ (déjà correct)"""
        logger.info(f"📝 _vscode_replace démarré pour: {snippet.get('file', 'N/A')}")

        file_path = snippet.get('file', '').strip()
        code = snippet.get('code', '').strip()
        target = snippet.get('target', '').strip()

        # ✅ VALIDATION STRICTE
        if not file_path:
            logger.error("❌ file_path manquant")
            QtWidgets.QMessageBox.critical(
                self,
                "Données manquantes",
                "Le chemin du fichier est manquant.\n"
                "L'IA doit fournir le champ 'file' dans sa réponse."
            )
            return

        if not code:
            logger.error("❌ code manquant")
            QtWidgets.QMessageBox.critical(
                self,
                "Données manquantes",
                "Le code de remplacement est manquant.\n"
                "L'IA doit fournir le champ 'code' dans sa réponse."
            )
            return

        if not target:
            logger.error("❌ target manquant pour action REPLACE")
            QtWidgets.QMessageBox.critical(
                self,
                "Données manquantes",
                "Le nom de la fonction/classe à remplacer est manquant.\n\n"
                "L'IA doit fournir le champ 'target' dans sa réponse.\n"
                "Exemple: 'target': 'def old_function():'"
            )
            return

        payload = {
            "action": "replace",
            "filePath": file_path,
            "code": code,
            "target": target
        }

        logger.info(f"📤 Payload VS Code:")
        logger.info(f"   - Action: {payload['action']}")
        logger.info(f"   - File: {payload['filePath']}")
        logger.info(f"   - Target: {payload['target'][:50]}...")

        try:
            response = requests.post(
                f"{self.vscode_url}/update",
                json=payload,
                timeout=10
            )

            logger.info(f"📥 Réponse VS Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info("✅ Code remplacé avec succès dans VS Code")

                    if result.get('created'):
                        QtWidgets.QMessageBox.information(
                            self,
                            "Fichier créé",
                            f"✅ Le fichier {file_path} a été créé avec le nouveau contenu."
                        )
                    else:
                        QtWidgets.QMessageBox.information(
                            self,
                            "Succès",
                            f"✅ Code remplacé avec succès dans:\n{file_path}"
                        )
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"❌ Échec VS Code: {error_msg}")

                    if 'non-existent file' in error_msg.lower():
                        self._handle_missing_file(snippet, payload)
                    elif result.get('userCancelled'):
                        QtWidgets.QMessageBox.information(
                            self,
                            "Annulé",
                            "Opération annulée par l'utilisateur dans VS Code."
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Erreur VS Code",
                            f"Impossible de remplacer le code:\n{error_msg}"
                        )
            else:
                result = response.json() if response.content else {}
                error_msg = result.get('error', f'HTTP {response.status_code}')
                logger.error(f"❌ Erreur HTTP: {error_msg}")

                if 'non-existent file' in error_msg.lower():
                    self._handle_missing_file(snippet, payload)
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Erreur serveur",
                        f"Le serveur VS Code a retourné une erreur:\n{error_msg}"
                    )

        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout connexion VS Code")
            QtWidgets.QMessageBox.critical(
                self,
                "Timeout",
                "Le serveur VS Code ne répond pas (timeout)."
            )
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Impossible de se connecter à VS Code")
            QtWidgets.QMessageBox.critical(
                self,
                "Connexion impossible",
                f"Impossible de se connecter au serveur VS Code sur {self.vscode_url}.\n"
                "Vérifiez que l'extension Liris est active dans VS Code."
            )
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur inattendue:\n{str(e)}"
            )

    def _handle_missing_file(self, snippet, original_payload):
        """Gère le cas où le fichier n'existe pas - SANS DIALOGUE"""
        file_path = snippet.get('file', '')
        
        logger.info(f"📄 Fichier {file_path} introuvable")
        
        # ✅ Proposition automatique de création (avec confirmation simple)
        reply = QtWidgets.QMessageBox.question(
            self,
            "Fichier introuvable",
            f"Le fichier '{file_path}' n'existe pas.\n\n"
            f"Voulez-vous créer le fichier avec ce contenu ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            logger.info(f"📄 Conversion REPLACE → INSERT pour créer {file_path}")
            
            insert_payload = {
                "action": "insert",
                "filePath": file_path,
                "code": snippet.get('code', ''),
                "lineNumber": 0
            }
            
            try:
                response = requests.post(
                    f"{self.vscode_url}/update",
                    json=insert_payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        logger.info(f"✅ Fichier {file_path} créé avec succès")
                        QtWidgets.QMessageBox.information(
                            self,
                            "Fichier créé",
                            f"✅ Le fichier {file_path} a été créé avec succès."
                        )
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        logger.error(f"❌ Échec création: {error_msg}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Erreur",
                            f"Impossible de créer le fichier:\n{error_msg}"
                        )
                else:
                    logger.error(f"❌ Erreur HTTP {response.status_code}")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Erreur",
                        f"Erreur lors de la création du fichier (HTTP {response.status_code})"
                    )
            
            except Exception as e:
                logger.error(f"❌ Erreur lors de la création: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la création du fichier:\n{str(e)}"
                )
        else:
            logger.info("❌ Utilisateur a annulé la création du fichier")

    def _prompt_target_code(self):
        """Demande le code à remplacer à l'utilisateur"""
        dialog = QtWidgets.QInputDialog(self)
        dialog.setWindowTitle("Code à remplacer")
        dialog.setLabelText(
            "Entrez le code à remplacer (doit être unique dans le fichier):\n\n"
            "Exemple: def old_function():"
        )
        dialog.setInputMode(QtWidgets.QInputDialog.InputMode.TextInput)
        dialog.resize(600, 200)

        # Créer un QTextEdit pour multiligne
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlaceholderText("Code à rechercher et remplacer...")
        text_edit.setMinimumHeight(100)

        # Remplacer le widget par défaut
        layout = dialog.layout()
        if layout:
            old_input = dialog.findChild(QtWidgets.QLineEdit)
            if old_input:
                old_input.setParent(None)
                layout.addWidget(text_edit)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            target = text_edit.toPlainText().strip()
            return target if target else None

        return None

    def check_vscode_connection(self):
        """Vérifie manuellement la connexion VS Code"""
        if self.vscode_integration.check_connection():
            QtWidgets.QMessageBox.information(
                self,
                "VS Code",
                "✅ VS Code est connecté et prêt à recevoir du code."
            )
            return True
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "VS Code",
                "❌ VS Code n'est pas accessible.\n\n"
                "Vérifiez que:\n"
                "• VS Code est ouvert\n"
                "• L'extension Liris est installée et activée\n"
                "• Le serveur est démarré (port 9000)"
            )
            return False

    def _update_ui_texts(self):
        """Met à jour les textes de l'interface avec traductions"""
        
        # EN-TÊTE
        self.title_label.setText(tr("coding_panel_title"))
        
        # MODE SWITCH
        self.api_mode_button.setText(tr("mode_api"))
        self.browser_mode_button.setText(tr("mode_browser"))
        
        # GROUPE PARAMÈTRES
        self.session_group.setTitle(tr("session_parameters"))
        
        # BOUTONS
        self.taxonomy_button.setText(f"  {tr('define_perimeter')}")
        self.start_button.setText(f"  {tr('start')}")
        self.export_button.setText(f"  {tr('export')}")
        
        # STATUTS
        self.status_label.setText(tr("ready"))
        self.perimeter_status_label.setText(tr("no_perimeter_defined"))
        
        # GRAPHE
        self.graph_group.setTitle(tr("relationship_graph"))
        
        # SNIPPETS
        self.no_snippets_label.setText(tr("no_code_generated"))
        
        # PLACEHOLDERS
        self.context_edit.setPlaceholderText(tr("context_placeholder"))
        
        # TOOLTIPS
        tooltip = tr("show_snippets") if not self.snippets_panel_visible else tr("hide_snippets")
        self.toggle_snippets_button.setToolTip(tooltip)

    def closeEvent(self, event):
        """Fermeture propre du panneau"""
        if hasattr(self, 'perimeter_items_container'):
            self.perimeter_items_container.deleteLater()

        if hasattr(self, 'current_worker') and self.current_worker:
            self.current_worker.quit()
            self.current_worker.wait()

        if hasattr(self, 'vscode_integration'):
            pass

        if self.dgraph_connector:
            self.dgraph_connector.close()
        if self.graph_widget:
            self.graph_widget.close()
        super().closeEvent(event)