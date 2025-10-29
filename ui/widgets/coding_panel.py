# coding_panel.py - Version avec panneau de snippets rétractable
import os
import time
import pyperclip
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.Qsci import (
    QsciScintilla,
    QsciLexerPython,
    QsciLexerCPP,
    QsciLexerJavaScript,
    QsciLexerHTML,
)

import qtawesome as qta

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

        self.is_browser_mode = False
        # État du panneau de snippets
        self.snippets_panel_visible = False

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"
        self.accent_color = "#E8E0DF"

        self._init_style()
        self._init_ui()
        self._update_ui_texts()
        self._load_projects_list()
        self.setObjectName("CodingPanel")

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
        """

        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Interface avec panneau de snippets rétractable"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(15, 15, 15, 15)

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
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        self.title_label.setAlignment(Qt.AlignVCenter)
        title_container.addWidget(self.title_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        # ===== BOUTON SWITCH MODE =====
        self.mode_switch_container = QtWidgets.QWidget()
        self.mode_switch_container.setFixedSize(280, 40)

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

        # Bouton Mode API
        self.api_mode_button = QtWidgets.QPushButton("Mode API")
        self.api_mode_button.setFixedSize(135, 34)
        self.api_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.api_mode_button.clicked.connect(lambda: self._switch_mode(False))

        # Bouton Navigation Auto
        self.browser_mode_button = QtWidgets.QPushButton("Navigation Auto")
        self.browser_mode_button.setFixedSize(135, 34)
        self.browser_mode_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.browser_mode_button.clicked.connect(lambda: self._switch_mode(True))

        switch_layout.addWidget(self.api_mode_button)
        switch_layout.addWidget(self.browser_mode_button)

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

        project_label = QtWidgets.QLabel("📁 Projet")
        project_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setMinimumWidth(180)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)

        platform_label = QtWidgets.QLabel("Plateforme IA")
        platform_label.setStyleSheet("font-weight: 600; font-size: 12px; margin-left: 20px;")
        self.platforms_combo = QtWidgets.QComboBox()
        self.platforms_combo.setMinimumWidth(180)

        proj_platform_layout.addWidget(project_label)
        proj_platform_layout.addWidget(self.project_combo)
        proj_platform_layout.addWidget(platform_label)
        proj_platform_layout.addWidget(self.platforms_combo)
        proj_platform_layout.addStretch()
        session_layout.addLayout(proj_platform_layout)

        # Contexte
        context_label = QtWidgets.QLabel("💡 Contexte (Fonctionnalité souhaitée)")
        context_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        session_layout.addWidget(context_label)

        self.context_edit = QtWidgets.QTextEdit()
        self.context_edit.setPlaceholderText("Décrivez la fonctionnalité à implémenter...")
        self.context_edit.setMinimumHeight(250)
        session_layout.addWidget(self.context_edit)

        # Périmètre
        perimeter_container = QtWidgets.QVBoxLayout()
        perimeter_container.setSpacing(10)

        perimeter_header = QtWidgets.QHBoxLayout()
        perimeter_label_title = QtWidgets.QLabel("🎯 Périmètre d'implémentation")
        perimeter_label_title.setStyleSheet("font-weight: 600; font-size: 12px;")
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
        self.perimeter_status_label.setStyleSheet("font-size: 13px; color: #888888; font-style: italic;")
        perimeter_display_layout.addWidget(self.perimeter_status_label)

        self.perimeter_details_label = QtWidgets.QLabel()
        self.perimeter_details_label.setWordWrap(True)
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
        self.status_label.setStyleSheet("color: #333; font-weight: bold; font-size: 11px;")
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

        content_layout.addLayout(left_column, 3)

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
        self.toggle_snippets_button.setFixedSize(36, 140)
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

        # En-tête du panneau
        snippets_header = QtWidgets.QHBoxLayout()
        snippets_title = QtWidgets.QLabel("💻 Code Généré")
        snippets_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        snippets_header.addWidget(snippets_title)
        snippets_header.addStretch()

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
        self.no_snippets_label = QtWidgets.QLabel("Aucun code généré pour le moment")
        self.no_snippets_label.setAlignment(Qt.AlignCenter)
        self.no_snippets_label.setStyleSheet("""
            font-size: 13px;
            color: #999;
            font-style: italic;
            padding: 60px 20px;
        """)
        self.snippets_layout.insertWidget(0, self.no_snippets_label)

        # Positionner le panneau snippets par-dessus le graphe
        self.snippets_panel.setParent(graph_container)
        self.snippets_panel.raise_()

        content_layout.addWidget(graph_container, 7)
        main_layout.addWidget(main_content)

        # Connecter le resize
        graph_container.resizeEvent = self._on_graph_container_resize


    def _switch_mode(self, is_browser_mode):
        """Change le mode de génération (API ou Browser)"""
        if self.is_browser_mode == is_browser_mode:
            return  # Déjà dans ce mode

        self.is_browser_mode = is_browser_mode
        self._update_switch_style()

        mode_name = "Navigation Automatique" if is_browser_mode else "Mode API"
        logger.info(f"Mode changé vers: {mode_name}")

        # Message de confirmation visuel
        self.update_status(f"✓ Basculé vers {mode_name}", None)

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
            # Mode Browser actif
            self.api_mode_button.setStyleSheet(inactive_style)
            self.browser_mode_button.setStyleSheet(active_style)
        else:
            # Mode API actif (par défaut)
            self.api_mode_button.setStyleSheet(active_style)
            self.browser_mode_button.setStyleSheet(inactive_style)

    def _on_start_session(self):
        """Lance une session de coding avec affichage de snippets"""
        
        # Vérifier le mode sélectionné
        if self.is_browser_mode:
            # Mode Navigation Automatique
            QtWidgets.QMessageBox.information(
                self,
                "Mode Navigation Automatique",
                "⚠️ Mode Navigation Automatique sélectionné.\n\n"
                "Cette fonctionnalité est en cours d'implémentation.\n"
                "Le système prendra le contrôle de votre navigateur."
            )
            # TODO: Implémenter la logique de navigation automatique
            return
        
        # Mode API (code existant)
        selected_platform_name = self.platforms_combo.currentData()

    def _toggle_snippets_panel(self):
            """Affiche/Cache le panneau de snippets avec animation (40% de l'écran)"""
            container = self.snippets_panel.parent()
            if not container:
                return
            
            container_width = container.width()
            container_height = container.height()
            target_width = int(container_width * 0.4) if not self.snippets_panel_visible else 0
            
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
            
            logger.info(f"Panneau snippets: {'ouvert (40%)' if self.snippets_panel_visible else 'fermé'}")

    def _update_snippets_count(self):
        """Met à jour le badge compteur de snippets"""
        count = len(self.current_snippets)
        self.snippets_count_badge.setText(str(count))

        # Changer la couleur selon le nombre
        if count == 0:
            self.snippets_count_badge.setStyleSheet("""
                background-color: #999;
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
        snippet_card.ide_requested.connect(self._on_ide_integration_requested)

        insert_position = self.snippets_layout.count() - 1
        if insert_position < 0:
            insert_position = 0

        self.snippets_layout.insertWidget(insert_position, snippet_card)
        self.current_snippets.append(snippet_data)
        self._update_snippets_count()

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

    def _on_start_session(self):
        """Lance une session de coding avec affichage de snippets"""
        selected_platform_name = self.platforms_combo.currentData()

        if not selected_platform_name:
            self.update_status("Erreur: Sélectionnez une plateforme IA", 0)
            QtWidgets.QMessageBox.warning(
                self, "Plateforme non sélectionnée",
                "Veuillez sélectionner une plateforme IA."
            )
            return

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

        test_message = self.context_edit.toPlainText().strip()
        if not test_message:
            self.update_status("Erreur: Décrivez le contexte", 0)
            QtWidgets.QMessageBox.warning(
                self, "Contexte vide",
                "Veuillez décrire la fonctionnalité à implémenter."
            )
            return

        perimeter_data = self._build_perimeter_data()

        self._clear_snippets()
        
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
            logger.info("Signal snippet_generated connecté")
        
        self.current_worker.finished.connect(self._on_worker_finished_generic)

        logger.info(f"Démarrage de {platform.name} avec {len(perimeter_data)} éléments")
        self.current_worker.start()
        self.session_started.emit(1)

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
                    f"✅ {snippet_count} snippets générés par {platform_name} en {duration:.2f}s",
                    100
                )
                
                logger.info(f"✅ {snippet_count} snippets affichés pour {platform_name}")
            else:
                self.update_status(
                    f"✅ Code généré avec succès par {platform_name} en {duration:.2f}s",
                    100
                )

            self.progress_bar.setValue(100)
            self.export_button.setEnabled(True)

        else:
            self.update_status(f"❌ Erreur {platform_name}: {message}", 0)
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
            "Sélectionnez un projet...",
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
        """Met à jour l'affichage du périmètre défini"""
        if not self.selected_taxonomy:
            self.perimeter_status_label.setText("⚪ Aucun périmètre défini")
            self.perimeter_details_label.setVisible(False)
            self.graph_widget._clear_graph()
            return

        count = len(self.selected_taxonomy)
        level = self.selected_taxonomy[0]['search_depth'] if self.selected_taxonomy else 1

        self.perimeter_status_label.setText(f"✅ {count} élément(s) sélectionné(s) • Niveau {level}")
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #2E7D32;
            font-weight: bold;
        """)

        details_html = f"<div style='line-height: 1.8;'><p style='margin: 0 0 12px 0;'>"
        details_html += "<span style='color: #A23B2D; font-weight: bold;'>📋 Éléments sélectionnés:</span></p>"

        for tax in self.selected_taxonomy:
            node_name = tax['name']
            node_type = tax.get('type', 'unknown')
            icon = self._get_icon_for_type(node_type)
            details_html += f"<p style='margin: 2px 0 2px 8px; font-size: 11px;'>"
            details_html += f"{icon} <span style='color: #333;'>{node_name}</span> "
            details_html += f"<span style='color: #888;'>({node_type})</span></p>"

        details_html += "</div>"
        self.perimeter_details_label.setTextFormat(Qt.RichText)
        self.perimeter_details_label.setText(details_html)
        self.perimeter_details_label.setVisible(True)

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
        """Construit les données du périmètre"""
        perimeter_list = []

        if not self.selected_taxonomy:
            return perimeter_list

        for tax_item in self.selected_taxonomy:
            item_data = {
                'name': tax_item.get('name', 'N/A'),
                'type': tax_item.get('type', 'unknown'),
                'level': tax_item.get('level', 0),
                'search_depth': tax_item.get('search_depth', 1),
                'data': {
                    'description': '',
                    'path': '',
                    'uid': '',
                    'fileContents': '',
                    'codeContent': ''
                },
                'relations': [],
                'related': []
            }

            file_data = tax_item.get('data', {})
            if file_data:
                item_data['data']['description'] = file_data.get('description', '')
                item_data['data']['path'] = file_data.get('path', '')
                item_data['data']['uid'] = file_data.get('uid', '')
                item_data['data']['fileContents'] = file_data.get('fileContents', '')
                item_data['data']['codeContent'] = file_data.get('codeContent', '')

            if not item_data['data']['uid']:
                uid = self._get_uid_by_name(item_data['name'])
                if uid:
                    item_data['data']['uid'] = uid

            relations = tax_item.get('relations', [])
            for rel in relations:
                relation_obj = {
                    'source': rel.get('source', ''),
                    'target': rel.get('target', ''),
                    'relation_type': rel.get('relation_type', 'unknown')
                }
                item_data['relations'].append(relation_obj)

            related = tax_item.get('related', [])
            for rel_item in related:
                related_data = rel_item.get('data', {})
                related_obj = {
                    'name': rel_item.get('name', ''),
                    'type': rel_item.get('type', 'unknown'),
                    'data': {
                        'description': related_data.get('description', ''),
                        'path': related_data.get('path', ''),
                        'uid': related_data.get('uid', ''),
                        'fileContents': related_data.get('fileContents', ''),
                        'codeContent': related_data.get('codeContent', '')
                    }
                }

                if not related_obj['data']['uid']:
                    uid = self._get_uid_by_name(related_obj['name'])
                    if uid:
                        related_obj['data']['uid'] = uid

                item_data['related'].append(related_obj)

            perimeter_list.append(item_data)

        return perimeter_list
    
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
        """Définit la liste des plateformes"""
        self.platforms_combo.clear()

        self.platforms_combo.addItem(
            qta.icon('fa5s.robot', color='#999999'),
            "Sélectionnez une plateforme IA",
            None
        )

        platform_data = self.platform_manager.get_platform_for_combo()

        for display_name, internal_name, color, icon in platform_data:
            self.platforms_combo.addItem(
                qta.icon(icon, color=color),
                display_name,
                internal_name
            )

        logger.info(f"Loaded {len(platform_data)} AI platforms")

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

    def _update_ui_texts(self):
        """Met à jour les textes de l'interface"""
        pass

    def closeEvent(self, event):
        """Fermeture propre du panneau"""
        if hasattr(self, 'current_worker') and self.current_worker:
            self.current_worker.quit()
            self.current_worker.wait()

        if self.dgraph_connector:
            self.dgraph_connector.close()
        if self.graph_widget:
            self.graph_widget.close()
        super().closeEvent(event)