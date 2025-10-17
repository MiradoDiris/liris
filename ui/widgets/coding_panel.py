# coding_panel.py - Version corrigée avec intégration complète GraphWidget
import base64
import os
import time
import pyperclip
import traceback
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
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
from ui.widgets.workers.simple_test_worker import SimpleTestWorker
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.premium_dialog import PremiumDialog
from ui.widgets.tabs.taxonomy_dialog import TaxonomyDialog
from ui.widgets.tabs.graph_widget import GraphWidget
from ui.widgets.workers.gemini_worker import GeminiWorker
from utils.api_config import APIConfigManager

class CodingPanel(QtWidgets.QWidget):   
    """Widget pour les sessions du coding multi-IA"""

    # Signaux
    session_started = pyqtSignal(int)
    session_completed = pyqtSignal(int)
    session_failed = pyqtSignal(int, str)
    export_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.conductor = None
        self.profiles = {}
        self.running_workers = []
        self.current_session_id = None
        self.orchestrator = None
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.api_config = APIConfigManager()  # Gestionnaire de configuration API
        self.gemini_api_key = "AIzaSyDkGrbEGhQmThZQAmGS88v_GBQwpqbSoT0"
        self.current_project_data = None
        self.selected_taxonomy = []

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

        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY non trouvée dans les variables d'environnement")


    def _init_style(self):
        """Style global : flèche SVG, pas de bordure grenat, scrollbar cachée dans les listes."""

        def get_dropdown_svg_path():
            """Retourne le chemin absolu vers dropdown.svg"""
            # Obtenir le répertoire du fichier actuel (ui/widgets)
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Remonter au répertoire parent (ui)
            ui_dir = os.path.dirname(current_dir)

            # Construire le chemin vers le SVG
            svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")

            # Normaliser le chemin pour Windows/Linux
            svg_path = os.path.normpath(svg_path)

            return svg_path

        # CORRECTION: Cette ligne doit être au même niveau d'indentation que la fonction
        svg_path = get_dropdown_svg_path()

        # Convertir le chemin Windows en format URL compatible
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
        QLineEdit:hover, QComboBox:hover, QTextEdit:hover {{
            border: 2px solid #C0C0C0;
        }}

        QComboBox {{
            min-height: 38px;
            padding-left: 12px;
            padding-right: 35px;
        }}

        QComboBox QAbstractItemView {{
            border: 2px solid #E0E0E0;
            border-radius: 8px;
            background-color: #FFFFFF;
            selection-background-color: {self.primary_color};
            selection-color: white;
            outline: none;
            padding: 4px;
        }}

        QComboBox QAbstractItemView::item {{
            min-height: 36px;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 2px 4px;
        }}

        QComboBox QAbstractItemView::item:hover {{
            background-color: #FFF3F0;
            color: {self.primary_color};
        }}

        QComboBox QAbstractItemView::item:selected {{
            background-color: {self.primary_color};
            color: white;
        }}

        QComboBox QAbstractItemView QScrollBar:vertical {{
            background: transparent;
            width: 0px;
            margin: 0px;
        }}
        QComboBox QAbstractItemView QScrollBar::handle:vertical {{
            background: transparent;
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

        QComboBox:hover::drop-down {{
            background: linear-gradient(to bottom, #F5F5F5, #F0F0F0);
        }}

        QComboBox::down-arrow {{
            image: url({svg_path});
            width: 18px;
            height: 18px;
        }}

        QComboBox:on {{
            border: 2px solid {self.primary_color};
        }}

        QTableWidget {{
            border: 1px solid #D0D0D0;
            border-radius: 8px;
            background-color: #FFFFFF;
            gridline-color: #E0E0E0;
        }}

        QHeaderView::section {{
            background-color: {self.primary_color};
            color: white;
            padding: 10px;
            border: none;
            font-weight: bold;
            font-size: 12px;
        }}

        QLabel {{ background-color: transparent; }}
        """

        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Interface modifiée : trois colonnes - gauche (param 30%), milieu (graphe 40%), droite (solutions 30%)"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ===== COLONNE GAUCHE : Paramètres (30%) =====
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(12)

        # En-tête avec bouton Premium
        header_layout = QtWidgets.QHBoxLayout()
        
        # Icône et titre à gauche
        title_icon = QtWidgets.QLabel()
        title_icon.setPixmap(qta.icon('fa5s.laptop-code', color='#666').pixmap(24, 24))
        header_layout.addWidget(title_icon)

        self.title_label = QtWidgets.QLabel("Coding")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; padding: 0 8px;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Bouton Premium à droite
        self.premium_button = QtWidgets.QPushButton()
        self.premium_button.setIcon(qta.icon('fa5s.crown', color='white'))
        self.premium_button.setText("  Update ")
        self.premium_button.setFixedHeight(32)
        self.premium_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.secondary_color};
                color: white;
                border: 2px solid {self.primary_color};
                padding: 6px 16px;
                border-radius: 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {self.primary_color};
                border-color: {self.secondary_color};
            }}
            QPushButton:pressed {{
                background-color: {self.primary_color};
                opacity: 0.8;
            }}
        """)
        self.premium_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.premium_button.clicked.connect(self._on_premium_clicked)
        header_layout.addWidget(self.premium_button)
        
        left_column.addLayout(header_layout)

        # Groupe Paramètres
        self.session_group = QtWidgets.QGroupBox("Paramètres de Session")
        session_layout = QtWidgets.QVBoxLayout(self.session_group)
        session_layout.setSpacing(10)
        session_layout.setContentsMargins(10, 18, 10, 10)

        # Projet + Plateforme côte à côte
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

        for combo in (self.project_combo, self.platforms_combo):
            combo.setMaxVisibleItems(10)
            combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

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
        self.context_edit.setMinimumHeight(150)
        session_layout.addWidget(self.context_edit)

        # === SECTION Périmètre amélioré ===
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

        self.taxonomy_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CCCCCC;
                color: #888888;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:enabled {{
                background-color: {self.secondary_color};
                color: white;
            }}
            QPushButton:enabled:hover {{
                background-color: {self.primary_color};
            }}
            QPushButton:disabled {{
                background-color: #e0e0e0;
                color: #424242;
            }}
        """)

        perimeter_header.addWidget(self.taxonomy_button)
        perimeter_container.addLayout(perimeter_header)

        perimeter_display_layout = QtWidgets.QVBoxLayout()
        perimeter_display_layout.setContentsMargins(0, 5, 0, 5)
        perimeter_display_layout.setSpacing(8)

        self.perimeter_status_label = QtWidgets.QLabel("Aucun périmètre défini")
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #888888;
            font-style: italic;
            padding: 8px;
            background-color: transparent;
        """)
        perimeter_display_layout.addWidget(self.perimeter_status_label)

        self.perimeter_details_label = QtWidgets.QLabel()
        self.perimeter_details_label.setStyleSheet("""
            font-size: 12px;
            color: #333333;
            padding: 10px;
            background-color: #F9F9F9;
            border-left: 3px solid #A23B2D;
            line-height: 1.6;
        """)
        self.perimeter_details_label.setWordWrap(True)
        self.perimeter_details_label.setVisible(False)
        perimeter_display_layout.addWidget(self.perimeter_details_label)

        perimeter_container.addLayout(perimeter_display_layout)
        session_layout.addLayout(perimeter_container)

        node_details_group = QtWidgets.QGroupBox("Nœud Sélectionné")
        node_details_layout = QtWidgets.QVBoxLayout(node_details_group)
        node_details_layout.setContentsMargins(10, 18, 10, 10)
        node_details_layout.setSpacing(8)

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
        self.status_label.setStyleSheet("color: #333; font-weight: bold; font-size: 11px; padding: 4px;")
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

        main_layout.addLayout(left_column, 3)  # 30% gauche

        # ===== COLONNE MILIEU : Graphe (40%) =====
        middle_column = QtWidgets.QVBoxLayout()

        self.graph_group = QtWidgets.QGroupBox("Graphe des Relations")
        graph_layout = QtWidgets.QVBoxLayout(self.graph_group)
        graph_layout.setContentsMargins(10, 10, 10, 10)

        # CORRECTION: Passer dgraph_connector au GraphWidget
        self.graph_widget = GraphWidget(
            config_provider=None,
            conductor=self.conductor,
            dgraph_connector=self.dgraph_connector,
            parent=self
        )
        graph_layout.addWidget(self.graph_widget)

        middle_column.addWidget(self.graph_group)
        main_layout.addLayout(middle_column, 4)  # 40% milieu

        # ===== COLONNE DROITE : Résultats (30%) =====
        right_column = QtWidgets.QVBoxLayout()
        self.results_group = QtWidgets.QGroupBox("Résultats")
        results_layout = QtWidgets.QVBoxLayout(self.results_group)
        self.solutions_table = QtWidgets.QTableWidget()
        self.solutions_table.setColumnCount(2)
        self.solutions_table.setHorizontalHeaderLabels(["Plateforme", "Solution"])
        self.solutions_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.solutions_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.solutions_table.verticalHeader().setVisible(False)
        self.solutions_table.cellDoubleClicked.connect(self._on_solution_double_clicked)
        results_layout.addWidget(self.solutions_table)
        right_column.addWidget(self.results_group)

        main_layout.addLayout(right_column, 3)

    def _on_premium_clicked(self):
        dialog = PremiumDialog(self)
        dialog.exec_()# 30% droite

    def _load_projects_list(self):
        """Charge la liste des projets avec icônes"""
        if not self.dgraph_connector.client:
            if not self.dgraph_connector.connect():
                logger.warning("Cannot connect to Dgraph")
                return
        
        query_result = self.dgraph_connector.query_full_context()
        if not query_result or not query_result.get('q'):
            logger.info("No projects found in Dgraph")
            return
        
        self.project_combo.clear()
        
        self.project_combo.addItem(
            qta.icon('fa5s.folder-open', color='#999999'),
            "Sélectionnez un projet...",
            None
        )
        
        seen_projects = set()
        for workspace in query_result['q']:
            project_name = workspace.get('name', '')
            if project_name and project_name not in seen_projects:
                seen_projects.add(project_name)
                self.project_combo.addItem(
                    qta.icon('fa5s.project-diagram', color='#A23B2D'),
                    f"📁 {project_name}",
                    workspace
                )
        
        logger.info(f"Loaded {len(seen_projects)} projects")

    def _on_node_selected_in_graph(self, node_name: str, node_details: dict):
        """Gère la sélection d'un nœud dans le graphe et met à jour l'affichage."""
        logger.info(f"Nœud sélectionné dans le graphe: {node_name}")

        # Mettre à jour le label du nœud sélectionné
        self.selected_node_label.setText(f"📍 {node_name}")

        # Construire le texte des détails
        details_html = "<div style='line-height: 1.6;'>"

        # Type du nœud
        node_type = node_details.get('type', 'unknown')
        level = node_details.get('level', 0)
        details_html += f"<p style='margin: 4px 0;'>"
        details_html += f"<b>Type:</b> <span style='color: #555;'>{node_type}</span> "
        details_html += f"| <b>Niveau:</b> <span style='color: #555;'>{level}</span>"
        details_html += f"</p>"

        # Relations sortantes
        outgoing = node_details.get('outgoing', [])
        details_html += f"<p style='margin: 8px 0 4px 0;'>"
        details_html += f"<b style='color: #A23B2D;'>→ Relations sortantes ({len(outgoing)}):</b>"
        details_html += f"</p>"

        if outgoing:
            details_html += "<ul style='margin: 0; padding-left: 20px;'>"
            for i, (source, target, rel_type) in enumerate(outgoing[:5]):
                target_short = target[:30] + '...' if len(target) > 30 else target
                details_html += f"<li style='margin: 2px 0; font-size: 10px;'>"
                details_html += f"<span style='color: #333;'>{target_short}</span> "
                details_html += f"<span style='color: #888; font-style: italic;'>[{rel_type}]</span>"
                details_html += f"</li>"
            details_html += "</ul>"
            if len(outgoing) > 5:
                details_html += f"<p style='margin: 2px 0 0 20px; font-size: 10px; color: #888;'>"
                details_html += f"... et {len(outgoing) - 5} autre(s)"
                details_html += f"</p>"
        else:
            details_html += "<p style='margin: 0 0 0 20px; font-size: 10px; color: #888;'>Aucune</p>"

        # Relations entrantes
        incoming = node_details.get('incoming', [])
        details_html += f"<p style='margin: 8px 0 4px 0;'>"
        details_html += f"<b style='color: #2196F3;'>← Relations entrantes ({len(incoming)}):</b>"
        details_html += f"</p>"

        if incoming:
            details_html += "<ul style='margin: 0; padding-left: 20px;'>"
            for i, (source, target, rel_type) in enumerate(incoming[:5]):
                source_short = source[:30] + '...' if len(source) > 30 else source
                details_html += f"<li style='margin: 2px 0; font-size: 10px;'>"
                details_html += f"<span style='color: #333;'>{source_short}</span> "
                details_html += f"<span style='color: #888; font-style: italic;'>[{rel_type}]</span>"
                details_html += f"</li>"
            details_html += "</ul>"
            if len(incoming) > 5:
                details_html += f"<p style='margin: 2px 0 0 20px; font-size: 10px; color: #888;'>"
                details_html += f"... et {len(incoming) - 5} autre(s)"
                details_html += f"</p>"
        else:
            details_html += "<p style='margin: 0 0 0 20px; font-size: 10px; color: #888;'>Aucune</p>"

        details_html += "</div>"

        # Mettre à jour le QTextEdit avec le HTML
        self.node_details_text.setHtml(details_html)

        # Ajouter le nœud à la liste des éléments sélectionnés si pas déjà présent
        self._add_to_selected_elements(node_name, node_type)

    def _add_to_selected_elements(self, node_name: str, node_type: str):
        """Ajoute un nœud à la liste des éléments sélectionnés (dans la section périmètre)."""
        # Vérifier si déjà dans la taxonomie sélectionnée
        already_selected = False
        for item in self.selected_taxonomy:
            if item.get('name') == node_name:
                already_selected = True
                break
            
        if not already_selected:
            # Créer un item temporaire pour cet élément
            temp_item = {
                'name': node_name,
                'type': node_type,
                'level': 0,
                'search_depth': 1,
                'data': {'name': node_name, 'uid': None},
                'related': [],
                'relations': []
            }
            self.selected_taxonomy.append(temp_item)

            # Mettre à jour l'affichage du périmètre
            self._update_perimeter_display()

            logger.info(f"Nœud '{node_name}' ajouté aux éléments sélectionnés")

    def _get_icon_for_type(self, node_type: str) -> str:
        """Retourne une icône emoji pour un type de nœud."""
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

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet - Active le bouton périmètre"""
        if index <= 0:
            self.current_project_data = None
            self.taxonomy_button.setEnabled(False)
            self.selected_taxonomy = []
            self._update_perimeter_display()
            self.graph_widget._clear_graph()
            return

        self.current_project_data = self.project_combo.currentData()
        self.taxonomy_button.setEnabled(True)
        # CORRECTION: Mettre à jour le project_data dans graph_widget
        self.graph_widget.current_project_data = self.current_project_data
        logger.info(f"Selected project: {self.current_project_data.get('name')}")

    def _on_define_taxonomy(self):
        """Ouvre le dialogue de définition des taxonomies et connecte le signal graphe"""
        if not self.current_project_data:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucun projet",
                "Veuillez d'abord sélectionner un projet."
            )
            return

        dialog = TaxonomyDialog(self.current_project_data, self.dgraph_connector, self)
        
        # Connecter le signal graph_update_signal pour mise à jour en temps réel
        dialog.graph_update_signal.connect(self._update_graph_from_taxonomy)
        dialog.selection_validated.connect(self._on_taxonomy_validated)
        
        logger.info("Dialogue taxonomie ouvert, signal connecté")
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.selected_taxonomy = dialog.get_selected_taxonomy()
            logger.info(f"Taxonomie acceptée: {len(self.selected_taxonomy)} éléments")
            self._update_perimeter_display()
            
            # Mettre à jour le graphe avec le dernier élément sélectionné
            if self.selected_taxonomy:
                last_item = self.selected_taxonomy[-1]
                central_name = last_item.get('name', 'N/A')
                central_uid = last_item['data'].get('uid', '')
                related = last_item.get('related', [])
                
                logger.info(f"Mise à jour finale du graphe: {central_name}, {len(related)} items")
                
                if central_uid and related:
                    self._update_graph_from_taxonomy(
                        central_name,
                        central_uid,
                        related,
                        self.current_project_data
                    )
                elif central_name:
                    # Même sans relations, afficher le nœud central
                    logger.info(f"Affichage du nœd")

    def _on_taxonomy_validated(self, taxonomy_data):
        """
        Appelée quand l'utilisateur valide sa sélection.
        Reçoit les données complètes et met à jour l'affichage.
        """
        logger.info(f"=== Validation reçue: {len(taxonomy_data)} taxonomies ===")

        # Stocker les taxonomies
        self.selected_taxonomy = taxonomy_data

        # Mettre à jour l'affichage du périmètre
        self._update_perimeter_display()

        # Mettre à jour le graphe avec le dernier élément
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

        logger.info("✅ Périmètre et graphe mis à jour")

    def _update_graph_from_taxonomy(self, central_name, central_uid, related_items, project_data):
        logger.info(f"=== _update_graph_from_taxonomy appelé ===")
        logger.info(f"  Central: {central_name}")
        logger.info(f"  UID: {central_uid}")
        logger.info(f"  Related items: {len(related_items)}")

        if not central_name:
            logger.warning("Nom central manquant, clear du graphe")
            self.graph_widget._clear_graph()
            return

        if not central_uid:
            logger.warning(f"UID manquant pour {central_name}, tentative de récupération")
            if hasattr(self.graph_widget, '_get_node_uid_by_name'):
                central_uid = self.graph_widget._get_node_uid_by_name(central_name)
                logger.info(f"UID récupéré: {central_uid}")

        try:
            self.graph_widget.update_graph(
                central_node=central_name,
                central_uid=central_uid,
                related_items=related_items,
                project_data=project_data
            )
            logger.info("update_graph terminé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du graphe: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _update_perimeter_display(self):
        """Met à jour l'affichage du périmètre défini - VERSION AMÉLIORÉE."""
        if not self.selected_taxonomy:
            self.perimeter_status_label.setText("⚪ Aucun périmètre défini")
            self.perimeter_status_label.setStyleSheet("""
                font-size: 13px;
                color: #888888;
                font-style: italic;
                padding: 8px;
                background-color: transparent;
            """)
            self.perimeter_details_label.setVisible(False)
            self.graph_widget._clear_graph()
            return

        count = len(self.selected_taxonomy)
        level = self.selected_taxonomy[0]['search_depth'] if self.selected_taxonomy else 1

        total_items = count
        total_relations = 0
        for tax in self.selected_taxonomy:
            relations = tax.get('relations', [])
            related = tax.get('related', [])
            total_relations += len(relations)
            total_items += len(related)

        names = [t['name'] for t in self.selected_taxonomy[:3]]
        display_names = ", ".join(names)
        if count > 3:
            display_names += f" et {count - 3} autre(s)"

        self.perimeter_status_label.setText(f"✅ {count} élément(s) sélectionné(s) • Niveau {level}")
        self.perimeter_status_label.setStyleSheet("""
            font-size: 13px;
            color: #2E7D32;
            font-weight: bold;
            padding: 8px;
            background-color: transparent;
        """)

        # Afficher la liste des éléments sélectionnés avec leurs types
        details_html = f"""
        <div style='line-height: 1.8;'>
            <p style='margin: 0 0 12px 0;'>
                <span style='color: #A23B2D; font-weight: bold; font-size: 13px;'>📋 Éléments sélectionnés:</span>
            </p>
        """

        for tax in self.selected_taxonomy:
            node_name = tax['name']
            node_type = tax.get('type', 'unknown')
            icon = self._get_icon_for_type(node_type)
            details_html += f"""
            <p style='margin: 2px 0 2px 8px; font-size: 11px;'>
                {icon} <span style='color: #333; font-weight: 500;'>{node_name}</span>
                <span style='color: #888; font-size: 10px;'>({node_type})</span>
            </p>
            """

        details_html += f"""
            <p style='margin: 12px 0 0 0;'>
                <span style='color: #555; font-weight: bold; font-size: 12px;'>📊 Statistiques du périmètre:</span><br/>
                <span style='color: #333; font-size: 12px;'>
                    • <b>{total_relations}</b> relations incluses<br/>
                    • <b>{total_items}</b> éléments au total<br/>
                    • <b>Niveau {level}</b> de profondeur
                </span>
            </p>
        </div>
        """

        self.perimeter_details_label.setTextFormat(QtCore.Qt.RichText)
        self.perimeter_details_label.setText(details_html)
        self.perimeter_details_label.setVisible(True)

        logger.info(
            f"Perimeter updated: {count} main items, {total_relations} relations, "
            f"{total_items} total elements (Level {level})"
        )

    def _on_start_session(self):
        """Lance une session de coding avec Gemini"""

        # Validations
        if not self.gemini_api_key:
            self.update_status("Erreur: Clé API Gemini non configurée", 0)
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur Configuration",
                "Clé API Gemini non configurée.\nVeuillez configurer votre clé API."
            )
            return

        test_message = self.context_edit.toPlainText().strip()
        if not test_message:
            self.update_status("Erreur: Décrivez le contexte", 0)
            QtWidgets.QMessageBox.warning(
                self,
                "Contexte vide",
                "Veuillez décrire la fonctionnalité à implémenter."
            )
            return

        # Construire les données de périmètre
        perimeter_data = self._build_perimeter_data()

        # Configuration de la session
        self.solutions_table.setRowCount(0)
        self.update_status("Initialisation de Gemini...", 0)
        self.start_button.setEnabled(False)
        self.export_button.setEnabled(False)

        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Créer et configurer le worker Gemini
        self.current_worker = GeminiWorker(
            context=test_message,
            perimeter_data=perimeter_data,
            api_key=self.gemini_api_key
        )

        # Connecter les signaux
        self.current_worker.test_completed.connect(self._on_gemini_completed)
        self.current_worker.step_update.connect(self._on_step_update)
        self.current_worker.debug_info.connect(self._on_debug_info)
        self.current_worker.finished.connect(self._on_gemini_worker_finished)

        # Démarrer le worker
        logger.info(f"Démarrage de Gemini avec {len(perimeter_data)} éléments du périmètre")
        self.current_worker.start()
        self.session_started.emit(1)

    def _on_gemini_completed(self, success, message, duration, response):
        """Gère la complétion de la requête Gemini"""
        
        logger.info(
            f"Gemini completed. Success: {success}, Duration: {duration:.2f}s"
        )
    
        if success:
            self.update_status(f"✅ Code généré avec succès en {duration:.2f}s", 100)
            
            # Ajouter le résultat au tableau
            row_position = self.solutions_table.rowCount()
            self.solutions_table.insertRow(row_position)
    
            # Colonne 1: Plateforme
            platform_item = QtWidgets.QTableWidgetItem("Gemini AI")
            platform_item.setTextAlignment(Qt.AlignCenter)
            self.solutions_table.setItem(row_position, 0, platform_item)
    
            # Colonne 2: Aperçu du code
            preview = response[:100] + "..." if len(response) > 100 else response
            preview_item = QtWidgets.QTableWidgetItem(preview)
            
            # Stocker la réponse complète dans UserRole
            preview_item.setData(Qt.UserRole, response)
            self.solutions_table.setItem(row_position, 1, preview_item)
    
            self.progress_bar.setValue(100)
            self.export_button.setEnabled(True)
            
            logger.info(f"Réponse Gemini: {len(response)} caractères")
        
        else:
            self.update_status(f"❌ Erreur: {message}", 0)
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur Gemini",
                f"Erreur lors de la génération du code:\n{message}"
            )
            self.progress_bar.setValue(0)
    
        self.start_button.setEnabled(True)

    def _on_gemini_worker_finished(self):
        """Appelée quand le worker Gemini est terminé"""
        if self.current_session_id:
            self.session_completed.emit(self.current_session_id)
        logger.info("Gemini worker finished")

    def _build_perimeter_data(self) -> list:
        """
        Construit les données du périmètre à partir de la taxonomie sélectionnée
        Inclut les descriptions des fichiers et relations
        """
        perimeter_list = []

        if not self.selected_taxonomy:
            logger.info("Aucun périmètre défini, utilisant contexte seul")
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
                    'uid': ''
                },
                'relations': [],
                'related': []
            }

            # Extraire les données du fichier (description, path, uid)
            file_data = tax_item.get('data', {})
            if file_data:
                item_data['data']['description'] = file_data.get('description', '')
                item_data['data']['path'] = file_data.get('path', '')
                item_data['data']['uid'] = file_data.get('uid', '')

            # Traiter les relations
            relations = tax_item.get('relations', [])
            for rel in relations:
                relation_obj = {
                    'source': rel.get('source', ''),
                    'target': rel.get('target', ''),
                    'relation_type': rel.get('relation_type', 'unknown')
                }
                item_data['relations'].append(relation_obj)

            # Traiter les éléments liés
            related = tax_item.get('related', [])
            for rel_item in related:
                related_obj = {
                    'name': rel_item.get('name', ''),
                    'type': rel_item.get('type', 'unknown'),
                    'data': {
                        'description': rel_item.get('data', {}).get('description', ''),
                        'path': rel_item.get('data', {}).get('path', '')
                    }
                }
                item_data['related'].append(related_obj)

            perimeter_list.append(item_data)

        logger.info(
            f"Périmètre construit: {len(perimeter_list)} éléments, "
            f"{sum(len(item['relations']) for item in perimeter_list)} relations"
        )

        return perimeter_list

    def _start_next_worker(self):
        """Démarre le worker suivant dans la séquence"""
        self.current_worker_index += 1
        if self.current_worker_index < len(self.running_workers):
            worker = self.running_workers[self.current_worker_index]
            logger.info(
                f"Starting test for platform: {worker.platform_name} "
                f"(Worker {self.current_worker_index + 1}/{len(self.running_workers)})"
            )
            worker.start()
        else:
            logger.info("All test workers have completed.")

    def _on_worker_finished(self):
        """Appelé quand un worker a terminé"""
        sender_worker = self.sender()
        logger.info(f"Worker for platform {sender_worker.platform_name} finished.")
        self._start_next_worker()

    def _on_step_update(self, step_name, message):
        """Mise à jour des étapes du test"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        self.update_status(f"[{platform_name}] {message}")

    def _on_debug_info(self, message):
        """Information de débogage"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        logger.debug(f"[{platform_name} DEBUG] {message}")

    def _on_test_completed(self, success, message, duration, response):
        """Gère la complétion d'un test"""
        sender_worker = self.sender()
        platform_name = getattr(sender_worker, "platform_name", "Unknown Platform")
        platform_index = getattr(sender_worker, "platform_index", 0)

        logger.info(
            f"Test for {platform_name} completed. "
            f"Success: {success}, Duration: {duration:.2f}s"
        )

        row_position = self.solutions_table.rowCount()
        self.solutions_table.insertRow(row_position)

        platform_item = QtWidgets.QTableWidgetItem(platform_name)
        platform_item.setTextAlignment(Qt.AlignCenter)
        self.solutions_table.setItem(row_position, 0, platform_item)

        preview = response[:80] + "..." if len(response) > 80 else response
        self.solutions_table.setItem(
            row_position, 1, QtWidgets.QTableWidgetItem(preview)
        )

        current_progress = (platform_index + 1) * 100
        self.progress_bar.setValue(current_progress)

        self._check_all_workers_finished()

    def _check_all_workers_finished(self):
        """Vérifie si tous les workers ont terminé"""
        if self.current_worker_index >= len(self.running_workers) - 1:
            self.update_status("Session terminée", 100)
            self.start_button.setEnabled(True)
            self.export_button.setEnabled(True)
            if self.current_session_id:
                self.session_completed.emit(self.current_session_id)
            logger.info("All code tests completed.")

    def _on_export_results(self):
        """Exporte les résultats de la session"""
        logger.info("Export results button clicked.")
        
        project_name = ""
        if self.project_combo.currentIndex() > 0:
            project_name = self.current_project_data.get('name', 'project')
        
        session_name = project_name if project_name else "coding_results"
        self.export_requested.emit(session_name)
        
        QtWidgets.QMessageBox.information(
            self, 
            "Export", 
            f"Résultats exportés pour: {session_name}"
        )

    def _on_solution_double_clicked(self, row, column):
        """Affiche le contenu complet de la solution"""
        if column == 1:
            item = self.solutions_table.item(row, column)
            
            # Récupérer la solution complète depuis UserRole
            solution_text = item.data(Qt.UserRole)
            if not solution_text:
                solution_text = item.text() if item else "(aucune solution)"
            
            platform_item = self.solutions_table.item(row, 0)
            platform_name = platform_item.text() if platform_item else "Unknown"

            detail_dialog = QtWidgets.QDialog(self)
            detail_dialog.setWindowTitle(f"Solution de {platform_name}")
            detail_dialog.resize(1000, 700)

            detail_layout = QtWidgets.QVBoxLayout(detail_dialog)
            detail_layout.setContentsMargins(20, 20, 20, 20)
            detail_layout.setSpacing(15)

            # En-tête avec statistiques
            header_layout = QtWidgets.QHBoxLayout()
            
            header_label = QtWidgets.QLabel(f"<b>Solution de {platform_name}</b>")
            header_label.setStyleSheet(f"""
                font-size: 16px;
                color: {self.primary_color};
                padding: 10px;
            """)
            header_layout.addWidget(header_label)
            
            header_layout.addStretch()
            
            # Stats
            lines_count = solution_text.count('\n') + 1
            chars_count = len(solution_text)
            stats_label = QtWidgets.QLabel(f"📊 {lines_count} lignes • {chars_count} caractères")
            stats_label.setStyleSheet("font-size: 11px; color: #666; padding: 10px;")
            header_layout.addWidget(stats_label)
            
            detail_layout.addLayout(header_layout)

            # Zone de code avec coloration syntaxique
            code_viewer = QsciScintilla()
            code_viewer.setUtf8(True)
            code_viewer.setReadOnly(True)
            code_viewer.setText(solution_text)

            # Détection du langage et application du lexer
            lexer = self._get_lexer_for_solution(solution_text)
            code_font = QtGui.QFont("Consolas", 11)

            if lexer:
                lexer.setDefaultFont(code_font)
                code_viewer.setLexer(lexer)

            # Configuration des marges et numéros de ligne
            fontmetrics = QtGui.QFontMetrics(code_font)
            code_viewer.setMarginWidth(0, fontmetrics.width("00000") + 8)
            code_viewer.setMarginLineNumbers(0, True)
            code_viewer.setMarginsBackgroundColor(QtGui.QColor("#f5f5f5"))
            code_viewer.setMarginsForegroundColor(QtGui.QColor("#666666"))
            code_viewer.setMarginsFont(code_font)

            # Mise en surbrillance de la ligne courante
            code_viewer.setCaretLineVisible(True)
            code_viewer.setCaretLineBackgroundColor(QtGui.QColor("#f0f8ff"))
            
            # Pliage de code
            code_viewer.setFolding(QsciScintilla.BoxedTreeFoldStyle)
            code_viewer.setFoldMarginColors(QtGui.QColor("#f5f5f5"), QtGui.QColor("#f5f5f5"))

            detail_layout.addWidget(code_viewer)

            # Boutons d'action
            button_layout = QtWidgets.QHBoxLayout()
            
            # Bouton pour sauvegarder
            save_button = QtWidgets.QPushButton("💾 Sauvegarder")
            save_button.clicked.connect(lambda: self._save_solution_to_file(solution_text))
            save_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.secondary_color};
                    padding: 10px 20px;
                }}
            """)
            button_layout.addWidget(save_button)
            
            button_layout.addStretch()

            # Bouton copier
            copy_button = QtWidgets.QPushButton("📋 Copier")
            copy_button.clicked.connect(lambda: self._copy_to_clipboard(solution_text))
            copy_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.primary_color};
                    padding: 10px 20px;
                }}
            """)
            button_layout.addWidget(copy_button)

            # Bouton fermer
            close_button = QtWidgets.QPushButton("✖ Fermer")
            close_button.clicked.connect(detail_dialog.close)
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: #777;
                    padding: 10px 20px;
                }
            """)
            button_layout.addWidget(close_button)

            detail_layout.addLayout(button_layout)

            detail_dialog.exec_()

    def _save_solution_to_file(self, solution_text):
        """Sauvegarde la solution dans un fichier"""
        try:
            # Détecter l'extension appropriée
            extension = ".txt"
            if "def " in solution_text or "import " in solution_text:
                extension = ".py"
            elif "#include" in solution_text or "std::" in solution_text:
                extension = ".cpp"
            elif "function" in solution_text and "{" in solution_text:
                extension = ".js"
            elif "<!DOCTYPE" in solution_text or "<html" in solution_text:
                extension = ".html"
            
            # Dialogue de sauvegarde
            default_name = f"gemini_solution_{int(time.time())}{extension}"
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Sauvegarder la solution",
                default_name,
                f"Fichiers (*{extension});;Tous les fichiers (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(solution_text)
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Sauvegarde réussie",
                    f"La solution a été sauvegardée dans:\n{file_path}"
                )
                logger.info(f"Solution saved to: {file_path}")
        
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de sauvegarde",
                f"Impossible de sauvegarder le fichier:\n{str(e)}"
            )

    def _copy_to_clipboard(self, text):
        """Copie le texte dans le presse-papier"""
        try:
            pyperclip.copy(text)
            QtWidgets.QMessageBox.information(
                self,
                "Copié",
                "Le code a été copié dans le presse-papier !"
            )
        except Exception as e:
            logger.error(f"Erreur lors de la copie: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de copier: {str(e)}"
            )

    def _get_lexer_for_solution(self, text):
        """Détermine le lexer approprié selon le contenu"""
        text_lower = text.lower()
        
        if "def " in text_lower or "import " in text_lower or "class " in text_lower:
            return QsciLexerPython()
        
        if "#include" in text_lower or "std::" in text_lower or "cout" in text_lower:
            return QsciLexerCPP()
        
        if ("function" in text_lower or "const " in text_lower or "let " in text_lower) and "{" in text_lower:
            return QsciLexerJavaScript()
        
        if "<!doctype" in text_lower or "<html" in text_lower or "<div" in text_lower:
            return QsciLexerHTML()
        
        return QsciLexerPython()

    def set_conductor(self, conductor):
        """Définit le chef d'orchestre"""
        self.conductor = conductor
        # CORRECTION: Mettre à jour le conductor dans graph_widget
        if self.graph_widget:
            self.graph_widget.conductor = conductor
        
        if hasattr(conductor, "modules") and hasattr(
            conductor.modules, "brainstorming_orchestrator"
        ):
            self.orchestrator = conductor.modules.brainstorming_orchestrator
        else:
            try:
                from modules.brainstorming.orchestrator import BrainstormingOrchestrator

                self.orchestrator = BrainstormingOrchestrator(
                    conductor, conductor.database
                )
                logger.info("Orchestrateur de Coding initialisé manuellement")
            except Exception as e:
                logger.error(
                    f"Impossible d'initialiser l'orchestrateur de coding: {str(e)}"
                )

    def set_platforms(self, profiles=None):
        """Définit la liste des profils de plateformes avec icônes"""
        self.platforms_combo.clear()

        default_item = "Sélectionnez une plateforme IA"
        self.platforms_combo.addItem(
            qta.icon('fa5s.robot', color='#999999'),
            default_item,
            ""
        )

        ai_platforms = [
            ("Claude AI", "claud ai", '#999999'),
            ("ChatGPT", "chatgpt", '#999999'),
            ("Grok", "grok", '#999999'),
            ("Gemini", "gemini", '#999999')
        ]

        for display_name, internal_name, color in ai_platforms:
            self.platforms_combo.addItem(
                qta.icon('fa5s.robot', color=color),
                display_name,
                internal_name
            )

        # CORRECTION: Si profiles est fourni, utiliser les profils réels
        if profiles:
            self.profiles = profiles
            logger.info(f"Loaded {len(profiles)} AI platform profiles")

    def update_status(self, message, progress=None):
        """Met à jour le statut de la session"""
        self.status_label.setText(message)
        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)

    def new_session(self):
        """Crée une nouvelle session - Réinitialise le périmètre et graphe"""
        self.project_combo.setCurrentIndex(0)
        self.context_edit.clear()
        self.platforms_combo.setCurrentIndex(0)
        self.selected_taxonomy = []
        self._update_perimeter_display()
        self.graph_widget._clear_graph()
        self.solutions_table.setRowCount(0)
        self.current_session_id = None
        self.current_worker = None  # Réinitialiser le worker
        self.export_button.setEnabled(False)
        self.update_status("Nouvelle session créée")

    def load_file(self, file_path):
        """Charge une session depuis un fichier"""
        try:
            if not file_path.lower().endswith((".json", ".txt", ".py", ".js", ".cpp", ".java")):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Format non supporté",
                    "Le format de fichier n'est pas supporté.",
                )
                return
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.context_edit.setPlainText(content)
            self.update_status(f"Fichier chargé: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Erreur chargement fichier: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de chargement",
                f"Impossible de charger le fichier: {str(e)}",
            )

    def refresh(self):
        """CORRECTION: Rafraîchit le panneau et le graphe"""
        self._load_projects_list()
        if self.graph_widget:
            self.graph_widget.refresh()
        logger.info("Coding panel refreshed")

    def _update_ui_texts(self):
        """Met à jour les textes de l'interface pour la traduction"""
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