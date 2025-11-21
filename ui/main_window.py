#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/main_window.py - CORRIGÉ pour afficher DashboardPanel via menu IA
"""

import os
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal

from PyQt5.QtCore import QRectF, QPropertyAnimation, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QFont, QLinearGradient

from ui.widgets.brainstorming_panel import BrainstormingPanel
from ui.widgets.coding_panel import CodingPanel
from ui.widgets.annotation_form import AnnotationForm
from ui.widgets.dataset_table import DatasetTable
from ui.widgets.prompt_list import PromptList
from ui.widgets.language_selector import LanguageSelector
from ui.widgets.dataset_generator_widget import DatasetGeneratorWidget
from ui.widgets.audit_panel import AuditPanel
from ui.widgets.platform_config_widget import PlatformConfigWidget
from ui.widgets.dataset_generator import DatasetGenerator, integrate_generation_button
from ui.widgets.dashboard_panel import DashboardPanel

from ui.widgets.dataset_strategy import DatasetStrategyWidget
import qtawesome as qta

from ui.widgets.project_config_only_widget import (
    ProjectConfigOnlyWidget,
)

from ui.widgets.tabs.premium_dialog import PremiumDialog

from ui.styles.theme import Theme
from ui.localization.translator import translator, tr

from core.orchestration.conductor import AIConductor
from core.data.database import Database
from core.data.exporter import DataExporter
from core.scheduling.scheduler import AIScheduler
from config.settings import ConfigProvider
from ui.widgets.ide_panel import IDEPanel

from utils.logger import logger


# === Switch Glassmorphism pour deux états (Dev/Data) ===
class GlassSwitch(QtWidgets.QWidget):
    """
    Switch glassmorphism avec dégradé identique aux onglets de menu
    Version responsive avec gestion dynamique de la taille
    """
    stateChanged = pyqtSignal(int)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Dimensions min/max
        self.setMinimumSize(180, 40)
        self.setMaximumSize(250, 50)
        
        # État et animation
        self._state = 0
        self._pill_x = 0.0
        self.animation = QPropertyAnimation(self, b"pill_x", self)
        self.animation.setDuration(220)

        # Importer Theme pour les couleurs
        from ui.styles.theme import Theme
        self.pill_primary_color = QColor(Theme.PRIMARY_COLOR)
        self.pill_secondary_color = QColor(Theme.SECONDARY_COLOR)
        self.font = QFont("Segoe UI", 9, QFont.Bold)
        
        # Largeur de section (sera recalculée dans resizeEvent)
        self._section_width = 100.0

    def resizeEvent(self, event):
        """Gère le redimensionnement"""
        super().resizeEvent(event)
        # Recalculer la largeur de section
        self._section_width = self.width() / 2.0
        # Recalculer la position de la pilule
        self._pill_x = self._state * self._section_width
        self.update()

    def sizeHint(self):
        """Taille suggérée"""
        return QtCore.QSize(200, 44)

    def getState(self):
        """Retourne l'état actuel (0 pour Dev, 1 pour Data)"""
        return self._state

    def setState(self, state: int, animate: bool = True):
        """
        Définit l'état du switch
        
        Args:
            state: 0 pour Dev, 1 pour Data
            animate: Si True, anime la transition
        """
        if state < 0 or state > 1:
            return
        if state == self._state:
            return
            
        self._state = state
        end_x = state * self._section_width
        
        self.animation.stop()
        self.animation.setStartValue(self._pill_x)
        self.animation.setEndValue(end_x)
        
        if animate:
            self.animation.start()
        else:
            self._pill_x = end_x
            self.update()

        self.stateChanged.emit(self._state)

    def mousePressEvent(self, event):
        """Gère le clic sur le switch"""
        if event.button() == Qt.LeftButton:
            x = event.pos().x()
            section = min(int(x / self._section_width), 1)
            self.setState(section)
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Dessine le switch avec dégradé identique aux onglets"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Fond du switch (gris clair comme les onglets non sélectionnés)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(245, 245, 245))  # #F5F5F5
        radius = min(self.height() / 2, 22)
        p.drawRoundedRect(self.rect(), radius, radius)

        # Pilule mobile avec dégradé vertical
        pill_rect = QRectF(
            self._pill_x, 
            2.0, 
            self._section_width - 4.0, 
            self.height() - 4.0
        )
        
        # Créer le dégradé vertical (PRIMARY_COLOR -> SECONDARY_COLOR)
        # Identique à: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 PRIMARY, stop:1 SECONDARY)
        gradient = QLinearGradient(
            pill_rect.center().x(),  # x1: centre horizontal
            pill_rect.top(),         # y1: haut (0)
            pill_rect.center().x(),  # x2: centre horizontal
            pill_rect.bottom()       # y2: bas (1)
        )
        gradient.setColorAt(0, self.pill_primary_color)    # stop:0 PRIMARY_COLOR
        gradient.setColorAt(1, self.pill_secondary_color)  # stop:1 SECONDARY_COLOR
        
        p.setBrush(gradient)
        pill_radius = (self.height() - 4.0) / 2
        p.drawRoundedRect(pill_rect, pill_radius, pill_radius)

        # Labels
        p.setFont(self.font)
        labels = ["Dev", "Data"]
        for i in range(2):
            text_rect = QRectF(
                i * self._section_width, 
                0, 
                self._section_width, 
                self.height()
            )
            if i == self._state:
                # Blanc pour le texte sélectionné (comme QTabBar::tab:selected)
                p.setPen(QColor(255, 255, 255))
            else:
                # Gris pour le texte non sélectionné
                p.setPen(QColor(100, 100, 100))
            p.drawText(text_rect, Qt.AlignCenter, labels[i])

    @pyqtProperty(float)
    def pill_x(self):
        """Getter pour la propriété pill_x (position de la pilule)"""
        return float(self._pill_x)

    @pill_x.setter
    def pill_x(self, x):
        """Setter pour la propriété pill_x (utilisé par l'animation)"""
        self._pill_x = float(x)
        self.update()


class MainWindow(QMainWindow):
    """
    Fenêtre principale de l'application d'IA collaborative
    """

    def __init__(self):
        print("=== DÉBUT - Initialisation de MainWindow ===")
        super().__init__()

        self.setWindowTitle(tr("app_title"))

        screen = QtWidgets.QApplication.desktop().screenGeometry()
        min_width = max(1024, int(screen.width() * 0.6))
        min_height = max(768, int(screen.height() * 0.6))
        self.setMinimumSize(min_width, min_height)

        initial_width = int(screen.width() * 0.8)
        initial_height = int(screen.height() * 0.8)
        self.resize(initial_width, initial_height)

        self.center_window()

        logo_path = os.path.join("ui", "resources", "icons", "logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QtGui.QIcon(logo_path))
        else:
            logger.warning("Icône non trouvée à l'emplacement: %s", logo_path)

        self.setStyleSheet(Theme.get_global_stylesheet())

        self._init_components()
        self._init_ui()
        self._init_menu()
        self._init_statusbar()
        self._init_connections()

        self.dataset_generator = DatasetGenerator(self.dataset_strategy, self.dataset_generation)
        integrate_generation_button(self.dataset_generation, self.dataset_strategy)

        self._restore_settings()

        self.conductor = None
        self.database = None
        self.exporter = None
        self.config_provider = None

        self.project_config_dialog_instance = None
        self.dashboard_dialog_instance = None

        QTimer.singleShot(100, self._init_system)

        logger.info("Application démarrée")
        print("=== FIN - Initialisation de MainWindow ===")

        self.current_mode = "dev"

    def _init_components(self):
        """Initialise les composants principaux"""
        print("   - Création des widgets principaux...")
        self.coding_panel = CodingPanel()
        self.brainstorming_panel = BrainstormingPanel()
        self.audit_panel = AuditPanel()
        self.annotation_form = AnnotationForm()
        self.dataset_table = DatasetTable()
        self.prompt_list = PromptList()

        self.dataset_generation = DatasetGeneratorWidget()
        self.dataset_strategy = DatasetStrategyWidget()
        self.ide_panel = IDEPanel()
        self.ide_dialog_instance = None
        self.dashboard_panel = None

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.status_label = QtWidgets.QLabel(tr("status.ready"))
        self.status_label.setStyleSheet(
            f"color: {Theme.PRIMARY_COLOR}; font-weight: bold;"
        )

        self.platform_label = QtWidgets.QLabel(tr("messages.no_platforms"))
        self.platform_label.setStyleSheet(
            f"color: {Theme.PRIMARY_COLOR}; font-weight: bold;"
        )

    def resizeEvent(self, event):
        """Gère le redimensionnement de la fenêtre principale"""
        super().resizeEvent(event)

        # Ajuster les éléments si nécessaire
        if hasattr(self, 'mode_switch') and self.mode_switch:
            self.mode_switch.updateGeometry()

        # Sauvegarder la géométrie
        if hasattr(self, 'config_provider'):
            self._save_window_geometry()

    def _save_window_geometry(self):
        """Sauvegarde la géométrie actuelle de la fenêtre"""
        settings = QSettings("Liris", "IACollaborative")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def center_window(self):
        """Centre la fenêtre sur l'écran"""
        frame_geometry = self.frameGeometry()
        screen_center = QtWidgets.QApplication.desktop().screenGeometry().center()
        frame_geometry.moveCenter(screen_center)
        self.move(frame_geometry.topLeft())

    def _init_ui(self):
        """Configure l'interface utilisateur avec responsivité"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(False)

        # Ajuster la taille des tabs selon la largeur de la fenêtre
        self.tab_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )

        # Stylesheet responsive avec calculs dynamiques
        tab_stylesheet = f"""
            QTabWidget::pane {{
                border: none;
                background: white;
                margin-top: 0px;
            }}

            QTabBar {{
                background: white;
                border: none;
            }}

            QTabBar::tab {{
                background: #F5F5F5;
                color: {Theme.TEXT_COLOR};
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                margin-right: 6px;
                margin-top: 8px;
                margin-bottom: 4px;
                font-weight: 500;
                font-size: 13px;
                min-width: 80px;
                min-height: 36px;
            }}

            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 {Theme.PRIMARY_COLOR}, 
                                             stop:1 {Theme.SECONDARY_COLOR});
                color: white;
                font-weight: 600;
            }}

            QTabBar::tab:hover:!selected {{
                background: #EBEBEB;
                color: {Theme.PRIMARY_COLOR};
            }}

            QTabBar::tab:first {{
                margin-left: 10px;
            }}
        """
        self.tab_widget.setStyleSheet(tab_stylesheet)

        # Container responsive pour le switch
        tab_bar_container = QtWidgets.QWidget()
        tab_bar_layout = QtWidgets.QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(0, 10, 15, 0)
        tab_bar_layout.setSpacing(0)

        tab_bar_layout.addStretch()
        self.mode_switch = GlassSwitch()
        self.mode_switch.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed
        )
        tab_bar_layout.addWidget(self.mode_switch)

        self.tab_widget.setCornerWidget(tab_bar_container, Qt.TopRightCorner)

        # Ajouter les tabs
        self.tab_widget.addTab(self.coding_panel, tr("coding_tab"))
        self.tab_widget.addTab(self.audit_panel, "Audit")
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.North)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(False)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tab_widget)

    def _update_tab_texts(self):
        """Met à jour les textes des onglets"""
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget == self.coding_panel:
                self.tab_widget.setTabText(i, tr("coding_tab"))
            elif widget == self.brainstorming_panel:
                self.tab_widget.setTabText(i, tr("brainstorming_tab"))
            elif widget == self.audit_panel:
                self.tab_widget.setTabText(i, "Audit")
            elif widget == self.dataset_strategy:
                self.tab_widget.setTabText(i, "Stratégie")
            elif widget == self.dataset_generation:
                self.tab_widget.setTabText(i, "Génération")
            elif widget == self.prompt_list:
                self.tab_widget.setTabText(i, "Historique")

    def set_conductor(self, conductor):
        """Set the conductor for all relevant widgets"""
        self.conductor = conductor
        if hasattr(self, 'dataset_strategy'):
            pass

    def _on_mode_switched(self, state):
        """
        Gère le changement entre Dev (0) et Data (1)
        """
        modes = {0: "dev", 1: "data"}
        self.current_mode = modes.get(state, "dev")
        self.tab_widget.clear()

        if state == 0:
            self.tab_widget.addTab(self.coding_panel, tr("coding_tab"))
            self.tab_widget.addTab(self.audit_panel, "Audit")
            self.tab_widget.setCurrentIndex(0)

        elif state == 1:
            self.tab_widget.addTab(self.dataset_strategy, "📊 Stratégie")
            self.tab_widget.addTab(self.dataset_generation, "🚀 Génération")
            self.tab_widget.addTab(self.prompt_list, "📜 Historique")
            self.tab_widget.setCurrentIndex(0)

        self._update_tab_texts()

    def _init_menu(self):
        """Configure les menus"""
        menubar = self.menuBar()

        # Menu Fichier
        file_menu = menubar.addMenu(tr("file"))

        new_action = QtWidgets.QAction(tr("new"), self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_file)
        file_menu.addAction(new_action)

        open_action = QtWidgets.QAction(tr("open"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        save_action = QtWidgets.QAction(tr("save"), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)

        export_action = QtWidgets.QAction(tr("export"), self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export_data)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction(tr("quit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Menu Édition
        edit_menu = menubar.addMenu(tr("edit"))

        settings_action = QtWidgets.QAction(tr("preferences"), self)
        settings_action.triggered.connect(self._on_settings)
        edit_menu.addAction(settings_action)

        language_action = QtWidgets.QAction(tr("select_language"), self)
        language_action.triggered.connect(self._on_change_language)
        edit_menu.addAction(language_action)

        refresh_action = QtWidgets.QAction(tr("refresh"), self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh)
        edit_menu.addAction(refresh_action)

        # Menu IA (avec Clé API déplacé ici)
        ai_menu = menubar.addMenu(tr("ai"))

        platforms_action = QtWidgets.QAction(tr("platforms"), self)
        platforms_action.triggered.connect(self._on_show_platforms)
        ai_menu.addAction(platforms_action)

        # DÉPLACÉ: Gestion des clés API dans le menu IA
        manage_api_keys_action = QtWidgets.QAction(tr("manage_api_keys"), self)
        manage_api_keys_action.setShortcut("Ctrl+K")
        manage_api_keys_action.triggered.connect(self._on_manage_api_keys)
        ai_menu.addAction(manage_api_keys_action)

        test_action = QtWidgets.QAction(tr("test_connection"), self)
        test_action.triggered.connect(self._on_test_ai)
        ai_menu.addAction(test_action)

        ai_menu.addSeparator()

        compare_action = QtWidgets.QAction(tr("compare_results"), self)
        compare_action.triggered.connect(self._on_compare_ai)
        ai_menu.addAction(compare_action)

        # NOUVEAU: Menu IDE (remplace l'ancien menu Clé API)
        ide_menu = menubar.addMenu("IDE")

        code_editor_action = QtWidgets.QAction("Éditeur de code", self)
        code_editor_action.triggered.connect(self._on_open_code_editor)
        ide_menu.addAction(code_editor_action)

        terminal_action = QtWidgets.QAction("Terminal", self)
        terminal_action.triggered.connect(self._on_open_terminal)
        ide_menu.addAction(terminal_action)

        ide_menu.addSeparator()

        project_explorer_action = QtWidgets.QAction("Explorateur de projet", self)
        project_explorer_action.triggered.connect(self._on_open_project_explorer)
        ide_menu.addAction(project_explorer_action)

        # Menu Brainstorming
        brainstorming_menu = menubar.addMenu("Brainstorming")
        open_brainstorming_action = QtWidgets.QAction("Ouvrir Brainstorming", self)
        open_brainstorming_action.triggered.connect(self._on_open_brainstorming)
        brainstorming_menu.addAction(open_brainstorming_action)

        # Menu Config
        turing_menu = menubar.addMenu("Config")

        config_projects_dev_action = QtWidgets.QAction(
            "Configuration projets dev", self
        )
        config_projects_dev_action.triggered.connect(self._on_show_project_config)
        turing_menu.addAction(config_projects_dev_action)

        # Menu Update avec icône couronne
        premium_action = QtWidgets.QAction(
            qta.icon('fa5s.crown', color="#FBF8F8"),
            "",
            self
        )
        premium_action.setShortcut("Ctrl+U")
        premium_action.triggered.connect(self._on_premium_update)
        menubar.addAction(premium_action)

        # Menu Aide
        help_menu = menubar.addMenu(tr("help"))

        about_action = QtWidgets.QAction(tr("about"), self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        docs_action = QtWidgets.QAction(tr("documentation"), self)
        docs_action.triggered.connect(self._on_documentation)
        help_menu.addAction(docs_action)

    def _on_manage_api_keys(self):
        """Ouvre le DashboardPanel avec dimensions responsives"""
        try:
            if not self.conductor or not self.config_provider or not self.database:
                QMessageBox.warning(
                    self,
                    tr("manage_api_keys"),
                    tr("system_not_initialized")
                )
                return
    
            if not self.dashboard_dialog_instance:
                self.dashboard_dialog_instance = QtWidgets.QDialog(self)
                self.dashboard_dialog_instance.setWindowTitle(tr("dashboard_window_title"))
                
                # Dimensions responsives
                screen = QtWidgets.QApplication.desktop().screenGeometry()
                dialog_width = min(1400, int(screen.width() * 0.85))
                dialog_height = min(900, int(screen.height() * 0.85))
                self.dashboard_dialog_instance.setMinimumSize(
                    max(1000, int(screen.width() * 0.6)),
                    max(700, int(screen.height() * 0.6))
                )
                self.dashboard_dialog_instance.resize(dialog_width, dialog_height)
                self.dashboard_dialog_instance.setModal(False)
    
                dialog_layout = QtWidgets.QVBoxLayout(self.dashboard_dialog_instance)
                dialog_layout.setContentsMargins(0, 0, 0, 0)
    
                if not self.dashboard_panel:
                    self.dashboard_panel = DashboardPanel(
                        self.config_provider,
                        self.conductor,
                        self.database
                    )
                    # Assurer que le panel s'adapte
                    self.dashboard_panel.setSizePolicy(
                        QtWidgets.QSizePolicy.Expanding,
                        QtWidgets.QSizePolicy.Expanding
                    )
    
                dialog_layout.addWidget(self.dashboard_panel)
    
                self.dashboard_dialog_instance.finished.connect(
                    self._on_dashboard_dialog_closed
                )
                
                # Centrer le dialogue
                self._center_dialog(self.dashboard_dialog_instance)
    
            if hasattr(self.dashboard_panel, 'refresh'):
                self.dashboard_panel.refresh()
    
            self.dashboard_dialog_instance.show()
            self.dashboard_dialog_instance.raise_()
            self.dashboard_dialog_instance.activateWindow()
    
            logger.info("Dashboard de gestion des clés API ouvert")
            self.update_status(tr("dashboard_opened"))
    
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture du Dashboard: {str(e)}")
            QMessageBox.critical(
                self,
                tr("error"),
                tr("dashboard_open_error", error=str(e))
            )

    def _on_dashboard_dialog_closed(self, result):
        """Gère la fermeture de la boîte de dialogue Dashboard"""
        self.dashboard_dialog_instance = None
        logger.info("Fenêtre Dashboard fermée.")

    def _on_ide_dialog_closed(self, result):
        """Gère la fermeture de la boîte de dialogue IDE"""
        self.ide_dialog_instance = None
        logger.info("Fenêtre IDE fermée.")

    # NOUVEAU: Méthodes pour le menu IDE
    def _on_open_code_editor(self):
        """Ouvre la fenêtre IDE avec dimensions responsives"""
        try:
            if not self.ide_dialog_instance:
                self.ide_dialog_instance = QtWidgets.QDialog(self)
                self.ide_dialog_instance.setWindowTitle(tr("ide_window_title"))

                # Dimensions responsives
                screen = QtWidgets.QApplication.desktop().screenGeometry()
                dialog_width = min(1600, int(screen.width() * 0.9))
                dialog_height = min(1000, int(screen.height() * 0.9))
                self.ide_dialog_instance.setMinimumSize(
                    max(1200, int(screen.width() * 0.7)),
                    max(800, int(screen.height() * 0.7))
                )
                self.ide_dialog_instance.resize(dialog_width, dialog_height)
                self.ide_dialog_instance.setModal(False)

                dialog_layout = QtWidgets.QVBoxLayout(self.ide_dialog_instance)
                dialog_layout.setContentsMargins(0, 0, 0, 0)

                if not self.ide_panel:
                    self.ide_panel = IDEPanel()
                    self.ide_panel.setSizePolicy(
                        QtWidgets.QSizePolicy.Expanding,
                        QtWidgets.QSizePolicy.Expanding
                    )

                    self.ide_panel.integration_started.connect(self._on_ide_integration_started)
                    self.ide_panel.integration_completed.connect(self._on_ide_integration_completed)

                    if hasattr(self.coding_panel, 'snippet_selected'):
                        self.coding_panel.snippet_selected.connect(self.ide_panel.set_snippet)

                dialog_layout.addWidget(self.ide_panel)
                self.ide_dialog_instance.finished.connect(self._on_ide_dialog_closed)

                # Centrer le dialogue
                self._center_dialog(self.ide_dialog_instance)

            if hasattr(self.ide_panel, 'refresh'):
                self.ide_panel.refresh()

            self.ide_dialog_instance.show()
            self.ide_dialog_instance.raise_()
            self.ide_dialog_instance.activateWindow()

            logger.info("Fenêtre IDE ouverte")
            self.update_status(tr("ide_window_opened"))

        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture de l'IDE: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                tr("error"),
                tr("ide_open_error", error=str(e))
            )

    def _on_open_terminal(self):
        """Ouvre le terminal intégré"""
        QMessageBox.information(
            self,
            "Terminal",
            "Le terminal intégré sera implémenté dans une prochaine version."
        )

    def _on_open_project_explorer(self):
        """Ouvre l'explorateur de projet"""
        QMessageBox.information(
            self,
            "Explorateur de projet",
            "L'explorateur de projet sera implémenté dans une prochaine version."
        )

    def _on_ide_integration_started(self):
        """Gère le démarrage de l'intégration IDE"""
        self.update_status("🚀 Intégration du code dans le projet...")
        self.show_progress(0, 100)
        logger.info("Intégration IDE démarrée")

    def _on_ide_integration_completed(self, success, message):
        """Gère la fin de l'intégration IDE"""
        self.hide_progress()

        if success:
            self.update_status(f"✅ {message}")
            logger.info(f"Intégration IDE réussie: {message}")
        else:
            self.update_status(f"❌ {message}")
            logger.error(f"Intégration IDE échouée: {message}")

    def _on_premium_update(self):
        """
        Ouvre directement le dialogue Premium Update.
        """
        try:
            dialog = PremiumDialog(self)
            result = dialog.exec_()
            
            if result == QtWidgets.QDialog.Accepted:
                logger.info("Premium Update: Dialogue accepté")
                self.update_status("Contexte mis à jour avec succès")
            else:
                logger.info("Premium Update: Dialogue annulé")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture du dialogue Premium: {str(e)}")
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'ouvrir le dialogue Premium:\n\n{str(e)}"
            )

    def _update_menus(self):
        """Met à jour les textes des menus"""
        menubar = self.menuBar()

        menus = {
            tr("file"): 0,
            tr("edit"): 1,
            tr("ai"): 2,
            "IDE": 3,
            "Brainstorming": 4,
            "Config": 5,
            tr("help"): 6,
        }

        for i, action in enumerate(menubar.actions()):
            for title_key, index in menus.items():
                if i == index:
                    action.setText(title_key)
                    break

        self._update_menu_actions()

    def _update_menu_actions(self):
        """Met à jour les textes des actions des menus"""
        menubar = self.menuBar()

        menu_actions = {
            0: [
                tr("new"),
                tr("open"),
                tr("save"),
                tr("export"),
                None,
                tr("quit"),
            ],
            1: [
                tr("preferences"),
                tr("select_language"),
                tr("refresh"),
            ],
            2: [
                tr("platforms"),
                tr("manage_api_keys"),
                tr("test_connection"),
                None,
                tr("compare_results"),
            ],
            3: [
                "Éditeur de code",
                "Terminal",
                None,
                "Explorateur de projet",
            ],
            4: [
                "Ouvrir Brainstorming"
            ],
            5: [
                "Configuration projets dev"
            ],
            6: [
                tr("about"),
                tr("documentation"),
            ],
        }

        for menu_index, actions_texts in menu_actions.items():
            if menu_index < len(menubar.actions()):
                menu = menubar.actions()[menu_index].menu()
                if menu:
                    actions = menu.actions()
                    action_index = 0
                    for i, text in enumerate(actions_texts):
                        if text is None:
                            action_index += 1
                            continue
                        if (
                                action_index < len(actions)
                                and not actions[action_index].isSeparator()
                        ):
                            actions[action_index].setText(text)
                        action_index += 1

    def _on_change_language(self):
        """Ouvre le sélecteur de langue"""
        selector = LanguageSelector(self)

        languages = translator.get_available_languages()
        for i in range(selector.language_combo.count()):
            if selector.language_combo.itemData(i) == translator.current_language:
                selector.language_combo.setCurrentIndex(i)
                break

        if selector.exec_() == QtWidgets.QDialog.Accepted:
            selected_language = selector.get_selected_language()
            self.change_language(selected_language)

    def _init_statusbar(self):
        """Configure la barre d'état"""
        statusbar = self.statusBar()

        statusbar.addPermanentWidget(self.progress_bar, 1)
        statusbar.addWidget(self.status_label, 2)
        statusbar.addPermanentWidget(self.platform_label, 1)

        self.update_status(tr("status.ready"))

    def _init_connections(self):
        """Configure les connexions signal-slot entre widgets"""
        self.coding_panel.session_started.connect(self._on_brainstorming_started)
        self.coding_panel.session_completed.connect(self._on_brainstorming_completed)
        self.coding_panel.session_failed.connect(self._on_brainstorming_failed)
        self.coding_panel.export_requested.connect(self._on_export_data)

        self.brainstorming_panel.session_started.connect(self._on_brainstorming_started)
        self.brainstorming_panel.session_completed.connect(
            self._on_brainstorming_completed
        )
        self.brainstorming_panel.session_failed.connect(self._on_brainstorming_failed)
        self.brainstorming_panel.export_requested.connect(self._on_export_data)

        self.annotation_form.annotation_started.connect(self._on_annotation_started)
        self.annotation_form.annotation_completed.connect(self._on_annotation_completed)
        self.annotation_form.annotation_failed.connect(self._on_annotation_failed)

        self.dataset_table.dataset_selected.connect(self._on_dataset_selected)
        self.dataset_table.dataset_created.connect(self._on_dataset_created)
        self.dataset_table.dataset_deleted.connect(self._on_dataset_deleted)

        self.prompt_list.prompt_selected.connect(self._on_prompt_selected)
        self.prompt_list.prompt_deleted.connect(self._on_prompt_deleted)

        self.mode_switch.stateChanged.connect(self._on_mode_switched)

        self.audit_panel.audit_started.connect(self._on_audit_started)
        self.audit_panel.audit_completed.connect(self._on_audit_completed)
        self.audit_panel.audit_failed.connect(self._on_audit_failed)
        self.audit_panel.export_requested.connect(self._on_export_data)

    def change_language(self, language_code):
        """Change la langue de l'application"""
        if translator.set_language(language_code):
            self.setWindowTitle(tr("app_title"))
            self._update_tab_texts()
            self._update_menus()
            self.update_status(tr("status.ready"))

            self._notify_language_change()

            settings = QSettings("Liris", "IACollaborative")
            settings.setValue("language", language_code)

    def _notify_language_change(self):
        """Notifie les widgets enfants du changement de langue"""
        for panel in [
            self.coding_panel,
            self.brainstorming_panel,
            self.annotation_form,
            self.dataset_table,
            self.dataset_generation,
            self.prompt_list,
        ]:
            if hasattr(panel, "update_language"):
                panel.update_language()

        if hasattr(self.dataset_strategy, "update_language"):
            self.dataset_strategy.update_language()

        if self.dashboard_panel and hasattr(self.dashboard_panel, "update_language"):
            self.dashboard_panel.update_language()

        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "update_language"):
                    child.update_language()

    def _restore_settings(self):
        """Restaure les paramètres utilisateur"""
        settings = QSettings("Liris", "IACollaborative")

        if settings.contains("geometry"):
            self.restoreGeometry(settings.value("geometry"))
        if settings.contains("windowState"):
            self.restoreState(settings.value("windowState"))

        last_mode = int(settings.value("last_mode", 0))
        last_index = int(settings.value("last_index", 0))
        self.mode_switch.setState(last_mode)
        QTimer.singleShot(300, lambda: self.tab_widget.setCurrentIndex(last_index) if last_index < self.tab_widget.count() else None)

        if settings.contains("lastExportPath"):
            self.last_export_path = settings.value(
                "lastExportPath", os.path.expanduser("~")
            )
        else:
            self.last_export_path = os.path.expanduser("~")

    def _save_settings(self):
        """Sauvegarde les paramètres utilisateur"""
        settings = QSettings("Liris", "IACollaborative")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

        settings.setValue("last_mode", self.mode_switch.getState())
        settings.setValue("last_index", self.tab_widget.currentIndex())

        settings.setValue("lastExportPath", self.last_export_path)
        settings.setValue("language", translator.current_language)

    def _init_system(self):
        """Initialise le système d'IA et les composants principaux"""
        try:
            self.update_status(tr("status.system_connecting"))
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)

            self.config_provider = ConfigProvider()
            self.progress_bar.setValue(20)

            db_config = self.config_provider.get_database_config()
            self.database = Database(db_config["path"])
            self.database.connect()
            self.progress_bar.setValue(40)

            self.exporter = DataExporter(self.config_provider)
            self.progress_bar.setValue(50)

            self.scheduler = AIScheduler(self.config_provider)
            self.progress_bar.setValue(70)

            self.conductor = AIConductor(
                self.config_provider, self.scheduler, self.database
            )
            self.conductor.initialize()
            self.progress_bar.setValue(90)

            self._update_ui_with_system()
            self.progress_bar.setValue(100)

            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            self.update_status(tr("status.system_initialized"))

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du système: {str(e)}")
            self.progress_bar.setVisible(False)
            self.update_status("Erreur d'initialisation")

            QMessageBox.critical(
                self,
                "Erreur d'initialisation",
                f"Le système n'a pas pu être initialisé correctement.\n\n"
                f"Erreur: {str(e)}\n\n"
                f"Certaines fonctionnalités pourraient ne pas être disponibles.",
            )

    def _update_ui_with_system(self):
        """Met à jour l'interface avec les informations du système"""
        if not self.conductor:
            return

        platforms = self.conductor.get_available_platforms()
        print(f"platforms: {platforms}")

        if platforms:
            self.platform_label.setText(
                tr("messages.platforms_available", count=len(platforms))
            )
        else:
            self.platform_label.setText(tr("messages.no_platforms"))

        self.coding_panel.set_conductor(self.conductor)
        self.coding_panel.set_platforms(platforms)

        self.brainstorming_panel.set_conductor(self.conductor)
        self.brainstorming_panel.set_platforms(platforms)

        self.dataset_generation.set_conductor(self.conductor)
        self.dataset_generation.set_platforms(platforms)
        self.dataset_generation.set_database(self.database)
        
        self.audit_panel.set_conductor(self.conductor)
        self.audit_panel.set_platforms(platforms)

        self.dataset_table.set_database(self.database)
        self.dataset_table.set_exporter(self.exporter)

        self.prompt_list.set_database(self.database)

        if not self.dashboard_panel:
            self.dashboard_panel = DashboardPanel(
                self.config_provider,
                self.conductor,
                self.database
            )

        self.prompt_list.refresh_list()
        self.dataset_table.refresh_list()

        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

    def update_status(self, message):
        """Met à jour le message de la barre d'état"""
        self.status_label.setText(message)
        logger.debug(f"Statut: {message}")

    def show_progress(self, value, max_value=100):
        """Affiche une progression dans la barre d'état"""
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(value)
        self.progress_bar.setVisible(True)

    def hide_progress(self):
        """Cache la barre de progression"""
        self.progress_bar.setVisible(False)

    def _on_tab_changed(self, index):
        """Gère le changement d'onglet"""
        tab_name = self.tab_widget.tabText(index)
        self.update_status(f"Section: {tab_name}")

        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, "refresh_list"):
            current_widget.refresh_list()

        if current_widget == self.dataset_strategy:
            pass

    def _on_new_file(self):
        """Gère la création d'un nouveau fichier"""
        current_tab = self.tab_widget.currentWidget()

        if current_tab == self.coding_panel:
            self.coding_panel.new_session()
        elif current_tab == self.brainstorming_panel:
            self.brainstorming_panel.new_session()
        elif current_tab == self.annotation_form:
            self.annotation_form.new_annotation_task()
        elif current_tab == self.dataset_table:
            self.dataset_table.new_dataset()
        elif current_tab == self.dataset_strategy:
            if hasattr(self.dataset_strategy, '_create_new_project'):
                self.dataset_strategy._create_new_project()

        if self.ide_panel and self.ide_dialog_instance and self.ide_dialog_instance.isVisible():
            self.ide_panel.preview_text.clear()
            self.ide_panel.current_snippets = []
            self.ide_panel.integrate_btn.setEnabled(False)
            self.update_status("Configuration IDE réinitialisée")

    def _on_open_file(self):
        """Gère l'ouverture d'un fichier"""
        file_path, file_filter = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un fichier",
            self.last_export_path,
            "Tous les fichiers (*.*);;Fichiers JSON (*.json);;Fichiers CSV (*.csv);;Fichiers texte (*.txt)",
        )

        if not file_path:
            return

        self.last_export_path = os.path.dirname(file_path)

        current_tab = self.tab_widget.currentWidget()

        if current_tab == self.coding_panel:
            self.coding_panel.load_file(file_path)
        elif current_tab == self.brainstorming_panel:
            self.brainstorming_panel.load_file(file_path)
        elif current_tab == self.annotation_form:
            self.annotation_form.load_file(file_path)
        elif current_tab == self.dataset_table:
            self.dataset_table.import_dataset(file_path)
        elif current_tab == self.dataset_strategy:
            if file_path.endswith('.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    QMessageBox.information(self, "Import", f"Configuration importée depuis {file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Erreur", f"Erreur lors de l'import: {str(e)}")

    def _on_save_file(self):
        """Gère l'enregistrement d'un fichier"""
        current_tab = self.tab_widget.currentWidget()

        if current_tab == self.coding_panel:
            self.coding_panel.save_session()
        elif current_tab == self.brainstorming_panel:
            self.brainstorming_panel.save_session()
        elif current_tab == self.annotation_form:
            self.annotation_form.save_annotations()
        elif current_tab == self.dataset_table:
            self.dataset_table.export_current()
        elif current_tab == self.dataset_strategy:
            if hasattr(self.dataset_strategy, '_save_strategy'):
                self.dataset_strategy._save_strategy()

    def _on_export_data(self):
        """Gère l'exportation des données"""
        current_tab = self.tab_widget.currentWidget()

        if current_tab == self.coding_panel:
            if hasattr(self.coding_panel, "export_session"):
                self.coding_panel.export_session()
        elif current_tab == self.brainstorming_panel:
            if hasattr(self.brainstorming_panel, "export_session"):
                self.brainstorming_panel.export_session()
        elif current_tab == self.annotation_form:
            if hasattr(self.annotation_form, "export_annotations"):
                self.annotation_form.export_annotations()
        elif current_tab == self.dataset_table:
            if hasattr(self.dataset_table, "export_dataset"):
                self.dataset_table.export_dataset()
        elif current_tab == self.prompt_list:
            if hasattr(self.prompt_list, "export_history"):
                self.prompt_list.export_history()
        elif current_tab == self.dataset_strategy:
            if hasattr(self.dataset_strategy, '_export_configuration'):
                self.dataset_strategy._export_configuration()

    def _on_settings(self):
        """Ouvre la boîte de dialogue des préférences"""
        QMessageBox.information(
            self,
            "Préférences",
            "La boîte de dialogue des préférences sera implémentée dans une prochaine version.",
        )

    def _on_refresh(self):
        """Actualise les données"""
        current_tab = self.tab_widget.currentWidget()

        if hasattr(current_tab, "refresh_list"):
            current_tab.refresh_list()
        elif hasattr(current_tab, "refresh"):
            current_tab.refresh()

        if current_tab == self.dataset_strategy:
            if hasattr(self.dataset_strategy, '_load_existing_projects'):
                self.dataset_strategy._load_existing_projects()

        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

        self.update_status("Données actualisées")

    def _on_strategy_project_saved(self, project_name):
        """Gère la sauvegarde d'un projet depuis l'onglet Stratégie"""
        self.update_status(f"Projet de stratégie '{project_name}' sauvegardé")
        logger.info(f"Projet de stratégie sauvegardé: {project_name}")

    def _on_strategy_project_loaded(self, project_name):
        """Gère le chargement d'un projet depuis l'onglet Stratégie"""
        self.update_status(f"Projet de stratégie '{project_name}' chargé")
        logger.info(f"Projet de stratégie chargé: {project_name}")

    def _on_strategy_data_generated(self, combinations_count):
        """Gère la génération de données de test depuis l'onglet Stratégie"""
        self.update_status(f"Données de test générées: {combinations_count} combinaisons")

    def _on_show_platforms(self):
        """Ouvre la configuration des plateformes avec dimensions responsives"""
        if not self.conductor:
            QMessageBox.warning(
                self,
                tr("platforms"),
                tr("system_not_initialized")
            )
            return

        try:
            self.platform_config_dialog = QtWidgets.QDialog(self)
            self.platform_config_dialog.setWindowTitle(tr("platform_config_window_title"))

            # Dimensions responsives
            screen = QtWidgets.QApplication.desktop().screenGeometry()
            dialog_width = min(1400, int(screen.width() * 0.85))
            dialog_height = min(900, int(screen.height() * 0.85))
            self.platform_config_dialog.setMinimumSize(
                max(1000, int(screen.width() * 0.6)),
                max(700, int(screen.height() * 0.6))
            )
            self.platform_config_dialog.resize(dialog_width, dialog_height)
            self.platform_config_dialog.setModal(True)

            dialog_layout = QtWidgets.QVBoxLayout(self.platform_config_dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)

            platform_config_widget = PlatformConfigWidget(
                self.config_provider, self.conductor, parent=self.platform_config_dialog
            )
            platform_config_widget.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding
            )

            dialog_layout.addWidget(platform_config_widget)

            platform_config_widget.platform_added.connect(
                self._on_platform_config_changed
            )
            platform_config_widget.platform_updated.connect(
                self._on_platform_config_changed
            )
            platform_config_widget.platform_deleted.connect(
                self._on_platform_config_changed
            )

            # Centrer le dialogue
            self._center_dialog(self.platform_config_dialog)

            self.platform_config_dialog.exec_()

        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture des plateformes: {str(e)}")
            QMessageBox.critical(
                self,
                tr("error"),
                tr("platforms_open_error", error=str(e))
            )

    def _on_platform_config_changed(self, platform_name):
        """Gère les changements de configuration des plateformes"""
        try:
            if self.conductor:
                platforms = self.conductor.get_available_platforms()

                if platforms:
                    self.platform_label.setText(
                        tr("messages.platforms_available", count=len(platforms))
                    )
                else:
                    self.platform_label.setText(tr("messages.no_platforms"))

                self.coding_panel.set_conductor(self.conductor)
                self.coding_panel.set_platforms(platforms)

                self.brainstorming_panel.set_conductor(self.conductor)
                self.brainstorming_panel.set_platforms(platforms)

                self.dataset_generation.set_conductor(self.conductor)
                self.dataset_generation.set_platforms(platforms)

            logger.info(f"Configuration des plateformes mise à jour: {platform_name}")
            self.update_status(f"Plateforme {platform_name} mise à jour")

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des plateformes: {str(e)}")

    def _on_show_project_config(self):
        """Ouvre la fenêtre de configuration avec dimensions responsives"""
        if not self.conductor:
            QMessageBox.warning(
                self,
                tr("config_projects_dev"),
                tr("system_not_initialized")
            )
            return

        try:
            if not self.project_config_dialog_instance:
                self.project_config_dialog_instance = QtWidgets.QDialog(self)
                self.project_config_dialog_instance.setWindowTitle(
                    tr("project_config_window_title")
                )

                # Dimensions responsives
                screen = QtWidgets.QApplication.desktop().screenGeometry()
                dialog_width = min(1200, int(screen.width() * 0.8))
                dialog_height = min(800, int(screen.height() * 0.8))
                self.project_config_dialog_instance.setMinimumSize(
                    max(900, int(screen.width() * 0.55)),
                    max(650, int(screen.height() * 0.6))
                )
                self.project_config_dialog_instance.resize(dialog_width, dialog_height)
                self.project_config_dialog_instance.setModal(False)

                dialog_layout = QtWidgets.QVBoxLayout(
                    self.project_config_dialog_instance
                )
                dialog_layout.setContentsMargins(0, 0, 0, 0)

                project_config_widget = ProjectConfigOnlyWidget(
                    self.config_provider,
                    self.conductor,
                    parent=self.project_config_dialog_instance,
                )
                project_config_widget.setSizePolicy(
                    QtWidgets.QSizePolicy.Expanding,
                    QtWidgets.QSizePolicy.Expanding
                )
                dialog_layout.addWidget(project_config_widget)

                self.project_config_dialog_instance.finished.connect(
                    self._on_project_config_dialog_closed
                )

                # Centrer le dialogue
                self._center_dialog(self.project_config_dialog_instance)

                project_config_widget.project_created.connect(
                self._on_global_project_refresh
                )
                project_config_widget.project_updated.connect(
                    self._on_global_project_refresh
                )
                project_config_widget.project_deleted.connect(
                    self._on_global_project_refresh
                )
                project_config_widget.project_loaded.connect(
                    self._on_global_project_refresh
                )

                # Stocker la référence
                self.project_config_widget_ref = project_config_widget

            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

            self.project_config_dialog_instance.show()
            self.project_config_dialog_instance.raise_()
            self.project_config_dialog_instance.activateWindow()

        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture de la configuration: {str(e)}")
            QMessageBox.critical(
                self,
                tr("error"),
                tr("config_open_error", error=str(e))
            )

    def _on_global_project_refresh(self, project_name):
        logger.info(f"🔄 Rafraîchissement global suite à une action sur le projet: {project_name}")

        try:
            self.update_status(f"Projet '{project_name}' mis à jour - Actualisation...")
            self.show_progress(0, 100)

            if self.conductor:
                self.show_progress(20)
                if hasattr(self.conductor, 'refresh_configurations'):
                    self.conductor.refresh_configurations()
                self.show_progress(40)

            widgets_to_refresh = [
                self.coding_panel,
                self.brainstorming_panel,
                self.audit_panel,
                self.dataset_strategy,
                self.dataset_generation,
                self.prompt_list,
                self.dataset_table
            ]

            progress_step = 40 / len(widgets_to_refresh)
            current_progress = 40

            for widget in widgets_to_refresh:
                if widget:
                    if hasattr(widget, 'refresh'):
                        widget.refresh()
                    elif hasattr(widget, 'refresh_list'):
                        widget.refresh_list()
                current_progress += progress_step
                self.show_progress(int(current_progress))

            if self.dashboard_panel and self.dashboard_dialog_instance:
                if hasattr(self.dashboard_panel, 'refresh'):
                    self.dashboard_panel.refresh()
            self.show_progress(90)

            if self.ide_panel and self.ide_dialog_instance:
                if hasattr(self.ide_panel, 'refresh'):
                    self.ide_panel.refresh()

            if self.conductor:
                platforms = self.conductor.get_available_platforms()
                self._update_platform_info(platforms)

            self.show_progress(100)

            QTimer.singleShot(500, self.hide_progress)
            self.update_status(f"✅ Application actualisée - Projet: {project_name}")

            logger.info(f"✅ Rafraîchissement global terminé pour le projet: {project_name}")

        except Exception as e:
            logger.error(f"❌ Erreur lors du rafraîchissement global: {str(e)}")
            self.hide_progress()
            self.update_status("❌ Erreur lors de l'actualisation")
            QMessageBox.warning(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'actualisation:\n\n{str(e)}"
            )

    def _update_platform_info(self, platforms):
        if platforms:
            self.platform_label.setText(
                tr("messages.platforms_available", count=len(platforms))
            )
        else:
            self.platform_label.setText(tr("messages.no_platforms"))

        for panel in [self.coding_panel, self.brainstorming_panel, 
                      self.dataset_generation, self.audit_panel]:
            if panel and hasattr(panel, 'set_platforms'):
                panel.set_platforms(platforms)

    def _on_project_config_changed(self, project_name):
        """Gère les changements de configuration des projets"""
        logger.info(f"Configuration du projet '{project_name}' mise à jour/supprimée.")
        self.update_status(f"Projet {project_name} mis à jour.")

    def _on_project_config_dialog_closed(self, result):
        """Gère la fermeture de la boîte de dialogue ProjectConfigOnlyWidget"""
        self.project_config_dialog_instance = None
        logger.info("Fenêtre de configuration des projets fermée.")

    def _on_test_ai(self):
        """Teste la connexion avec les IA"""
        pass

    def _on_compare_ai(self):
        """Compare les résultats de différentes IA"""
        pass

    def _save_comparison_results(self, prompt, results):
        """Enregistre les résultats d'une comparaison"""
        pass

    def _on_about(self):
        """Affiche la boîte de dialogue À propos"""
        pass

    def _on_documentation(self):
        """Ouvre la documentation"""
        pass

    def _on_brainstorming_started(self, session_id):
        """Gère le démarrage d'une session"""
        self.update_status(f"Session {session_id} démarrée")
        self.show_progress(0, 100)

    def _on_brainstorming_completed(self, session_id):
        """Gère la fin d'une session"""
        self.update_status(f"Session {session_id} terminée")
        self.hide_progress()

    def _on_brainstorming_failed(self, session_id, error):
        """Gère l'échec d'une session"""
        self.update_status(f"Échec de la session {session_id}")
        self.hide_progress()
        QMessageBox.critical(
            self, "Échec", f"La session {session_id} a échoué.\n\nErreur: {error}"
        )

    def _on_annotation_started(self, task_id):
        """Gère le démarrage d'une tâche d'annotation"""
        self.update_status(f"Tâche d'annotation {task_id} démarrée")
        self.show_progress(0, 100)

    def _on_annotation_completed(self, task_id):
        """Gère la fin d'une tâche d'annotation"""
        self.update_status(f"Tâche d'annotation {task_id} terminée")
        self.hide_progress()

    def _on_annotation_failed(self, task_id, error):
        """Gère l'échec d'une tâche d'annotation"""
        self.update_status(f"Échec de la tâche d'annotation {task_id}")
        self.hide_progress()
        QMessageBox.critical(
            self, "Échec", f"La tâche d'annotation {task_id} a échoué.\n\nErreur: {error}"
        )

    def _on_dataset_selected(self, dataset_id):
        """Gère la sélection d'un jeu de données"""
        self.update_status(f"Jeu de données {dataset_id} sélectionné")

    def _on_dataset_created(self, dataset_id):
        """Gère la création d'un jeu de données"""
        self.update_status(f"Jeu de données {dataset_id} créé")

    def _on_dataset_deleted(self, dataset_id):
        """Gère la suppression d'un jeu de données"""
        self.update_status(f"Jeu de données {dataset_id} supprimé")

    def _on_prompt_selected(self, prompt_id):
        """Gère la sélection d'un prompt"""
        self.update_status(f"Prompt {prompt_id} sélectionné")

    def _on_prompt_deleted(self, prompt_id):
        """Gère la suppression d'un prompt"""
        self.update_status(f"Prompt {prompt_id} supprimé")

    def closeEvent(self, event):
        """Gère l'événement de fermeture de la fenêtre"""
        self._save_settings()

        if self.conductor:
            try:
                self.conductor.shutdown()
            except Exception as e:
                logger.error(f"Erreur lors de l'arrêt du système: {str(e)}")

        if hasattr(self.dataset_strategy, 'closeEvent'):
            self.dataset_strategy.closeEvent(None)
        
        if self.ide_dialog_instance:
            self.ide_dialog_instance.close()

        event.accept()

    def _on_audit_started(self, audit_id):
        """Gère le démarrage d'un audit"""
        self.update_status(f"Audit {audit_id} démarré")
        self.show_progress(0, 100)

    def _on_audit_completed(self, audit_id):
        """Gère la fin d'un audit"""
        self.update_status(f"Audit {audit_id} terminé")
        self.hide_progress()

    def _on_audit_failed(self, audit_id, error):
        """Gère l'échec d'un audit"""
        self.update_status(f"Échec de l'audit {audit_id}")
        self.hide_progress()
        QMessageBox.critical(
            self, "Échec", f"L'audit {audit_id} a échoué.\n\nErreur: {error}"
        )
    
    def _on_open_brainstorming(self):
        """Ouvre la fenêtre Brainstorming avec dimensions responsives"""
        try:
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(tr("brainstorming_session_window"))

            # Dimensions responsives
            screen = QtWidgets.QApplication.desktop().screenGeometry()
            dialog_width = min(1200, int(screen.width() * 0.8))
            dialog_height = min(800, int(screen.height() * 0.8))
            dialog.setMinimumSize(
                max(900, int(screen.width() * 0.55)),
                max(650, int(screen.height() * 0.6))
            )
            dialog.resize(dialog_width, dialog_height)

            layout = QtWidgets.QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)

            self.brainstorming_panel.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding
            )
            layout.addWidget(self.brainstorming_panel)

            dialog.setModal(False)

            # Centrer le dialogue
            self._center_dialog(dialog)

            dialog.show()

        except Exception as e:
            QMessageBox.critical(
                self, 
                tr("error"), 
                tr("brainstorming_open_error", error=str(e))
            )

    def _center_dialog(self, dialog):
        """Centre un dialogue par rapport à la fenêtre principale"""
        if dialog and self:
            parent_geometry = self.frameGeometry()
            dialog_geometry = dialog.frameGeometry()
            center_point = parent_geometry.center()
            dialog_geometry.moveCenter(center_point)
            dialog.move(dialog_geometry.topLeft())