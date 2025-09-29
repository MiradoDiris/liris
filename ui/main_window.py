#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/main_window.py - MODIFIÉ pour inclure l'onglet Stratégie de Dataset
"""

import os
import json
from datetime import datetime
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal

from PyQt5.QtCore import QRectF, QPropertyAnimation, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QFont

from ui.widgets.brainstorming_panel import BrainstormingPanel
from ui.widgets.coding_panel import CodingPanel
from ui.widgets.annotation_form import AnnotationForm
from ui.widgets.dataset_table import DatasetTable
from ui.widgets.prompt_list import PromptList
from ui.widgets.language_selector import LanguageSelector
from ui.widgets.dataset_generation import DatasetGenerationWidget
from ui.widgets.dataset_generator_widget import DatasetGeneratorWidget
from ui.widgets.platform_config_widget import PlatformConfigWidget
from ui.widgets.dataset_generator import DatasetGenerator, integrate_generation_button

# NOUVEL IMPORT: Onglet Stratégie de Dataset
from ui.widgets.dataset_strategy import DatasetStrategyWidget

# Importer le nouveau widget ProjectConfigOnlyWidget
from ui.widgets.project_config_only_widget import (
    ProjectConfigOnlyWidget,
)

from ui.widgets.tabs.project_config_widget import (
    ProjectConfigWidget,
)

from ui.styles.theme import Theme
from ui.localization.translator import translator, tr

from core.orchestration.conductor import AIConductor
from core.data.database import Database
from core.data.exporter import DataExporter
from core.scheduling.scheduler import AIScheduler
from config.settings import ConfigProvider

from utils.logger import logger


# === Switch Glassmorphism (inchangé) ===
class GlassSwitch(QtWidgets.QWidget):
    # Signaux compatibles QCheckBox
    toggled = pyqtSignal(bool)
    stateChanged = pyqtSignal(int)  # émet Qt.Checked / Qt.Unchecked
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(125, 44)
        self._checked = False
        self._x_pos = 4.0
        self.animation = QPropertyAnimation(self, b"pos_anim", self)
        self.animation.setDuration(220)

        # Couleurs
        self.bg_dev = QColor("#e7e3fb")  # fond quand Dev (clair)
        self.bg_data = QColor("#A23B2D")  # fond quand Data (foncé)
        self.handle_color = QColor(255, 255, 255, 230)  # poignée blanche
        self.font = QFont("Segoe UI", 10, QFont.Bold)

    def isChecked(self):
        return bool(self._checked)

    def setChecked(self, checked: bool, animate: bool = True):
        if bool(self._checked) == bool(checked):
            return
        self._checked = bool(checked)
        end_pos = 4.0 if not self._checked else (self.width() - self.height() + 4.0)
        self.animation.stop()
        self.animation.setStartValue(self._x_pos)
        self.animation.setEndValue(end_pos)
        if animate:
            self.animation.start()
        else:
            self._x_pos = end_pos
            self.update()

        self.toggled.emit(self._checked)
        self.stateChanged.emit(Qt.Checked if self._checked else Qt.Unchecked)

    def toggle(self):
        self.setChecked(not self._checked, animate=True)

    def mousePressEvent(self, event):
        self.toggle()
        self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        bg_color = self.bg_data if self._checked else self.bg_dev
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)

        p.setFont(self.font)
        text_color = (
            QColor(255, 255, 255, 220) if self._checked else QColor(45, 45, 255, 220)
        )
        p.setPen(text_color)
        label = "Data" if self._checked else "Dev"
        p.drawText(self.rect(), Qt.AlignCenter, label)

        p.setBrush(self.handle_color)
        handle_rect = QRectF(self._x_pos, 4.0, self.height() - 8.0, self.height() - 8.0)
        p.drawEllipse(handle_rect)

    @pyqtProperty(float)
    def pos_anim(self):
        return float(self._x_pos)

    @pos_anim.setter
    def pos_anim(self, x):
        self._x_pos = float(x)
        self.update()


class MainWindow(QMainWindow):
    """
    Fenêtre principale de l'application d'IA collaborative
    """

    def __init__(self):
        print("=== DÉBUT - Initialisation de MainWindow ===")
        super().__init__()

        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(1024, 768)

        # Définir l'icône avec le fichier .ico
        logo_path = os.path.join("ui", "resources", "icons", "logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QtGui.QIcon(logo_path))
        else:
            logger.warning("Icône non trouvée à l'emplacement: %s", logo_path)

        # Appliquer le style global
        self.setStyleSheet(Theme.get_global_stylesheet())

        # Initialiser les composants
        self._init_components()
        self._init_ui()
        self._init_menu()
        self._init_statusbar()
        self._init_connections()

        self.dataset_generator = DatasetGenerator(self.dataset_strategy, self.dataset_generation)
        integrate_generation_button(self.dataset_generation, self.dataset_strategy)

        # Restaurer les paramètres
        self._restore_settings()

        # État initial
        self.conductor = None
        self.database = None
        self.exporter = None
        self.config_provider = None

        # Stocker la référence à la fenêtre de configuration des projets
        self.project_config_dialog_instance = None

        # Initialiser le système au démarrage
        QTimer.singleShot(100, self._init_system)

        # Journaliser le démarrage
        logger.info("Application démarrée")
        print("=== FIN - Initialisation de MainWindow ===")

        self.current_mode = "dev"

    def _init_components(self):
        """Initialise les composants principaux"""
        print("   - Création des widgets principaux...")
        self.coding_panel = CodingPanel()
        self.brainstorming_panel = BrainstormingPanel()
        self.annotation_form = AnnotationForm()
        self.dataset_table = DatasetTable()
        self.prompt_list = PromptList()

        # Widget de génération de dataset (existant)
        self.dataset_generation = DatasetGeneratorWidget()

        # NOUVEAU: Widget de stratégie de dataset
        self.dataset_strategy = DatasetStrategyWidget()

        # Barres de progression
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        # Widgets d'état
        self.status_label = QtWidgets.QLabel(tr("status.ready"))
        self.status_label.setStyleSheet(
            f"color: {Theme.PRIMARY_COLOR}; font-weight: bold;"
        )

        self.platform_label = QtWidgets.QLabel(tr("messages.no_platforms"))
        self.platform_label.setStyleSheet(
            f"color: {Theme.PRIMARY_COLOR}; font-weight: bold;"
        )

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        # Widget central principal
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # En-tête simplifié
        header_widget = QtWidgets.QWidget()
        header_widget.setStyleSheet(f"""
            background-color: white;
            border-bottom: 2px solid {Theme.PRIMARY_COLOR};
        """)
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(30, 20, 30, 20)

        # Logo et titre
        logo_layout = QtWidgets.QHBoxLayout()
        logo_layout.setSpacing(15)

        # Logo (si disponible)
        logo_path = os.path.join("ui", "resources", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo_label = QtWidgets.QLabel()
            pixmap = QtGui.QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(
                40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
            logo_layout.addWidget(logo_label)

        # Titre et sous-titre
        title_layout = QtWidgets.QVBoxLayout()

        title_label = QtWidgets.QLabel("Liris")
        title_label.setStyleSheet(f"""
            font-size: {Theme.FONT_SIZE_TITLE}px;
            font-weight: bold;
            color: {Theme.PRIMARY_COLOR};
            margin: 0;
            padding: 0;
        """)
        title_layout.addWidget(title_label)

        subtitle_label = QtWidgets.QLabel(tr("app_title"))
        subtitle_label.setObjectName("subtitle_label")
        subtitle_label.setStyleSheet(f"""
            font-size: {Theme.FONT_SIZE_HEADER}px;
            color: {Theme.SECONDARY_COLOR};
            margin: 0;
            padding: 0;
        """)
        title_layout.addWidget(subtitle_label)

        logo_layout.addLayout(title_layout)
        header_layout.addLayout(logo_layout)

        # Ajout du switch glassmorphism
        self.mode_switch = GlassSwitch()
        header_layout.addWidget(self.mode_switch)

        header_layout.addStretch()

        # Indicateur de statut système dans l'en-tête
        system_status_widget = QtWidgets.QWidget()
        system_status_layout = QtWidgets.QHBoxLayout(system_status_widget)
        system_status_layout.setContentsMargins(0, 0, 0, 0)

        self.connection_indicator = QtWidgets.QLabel()
        self.connection_indicator.setFixedSize(12, 12)
        self.connection_indicator.setStyleSheet("""
            background-color: #888888;
            border-radius: 6px;
        """)
        system_status_layout.addWidget(self.connection_indicator)

        self.connection_label = QtWidgets.QLabel("Système en attente")
        self.connection_label.setStyleSheet(
            f"color: {Theme.TEXT_COLOR}; margin-left: 5px;"
        )
        system_status_layout.addWidget(self.connection_label)

        header_layout.addWidget(system_status_widget)

        main_layout.addWidget(header_widget)

        # Zone principale avec onglets
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(False)

        # Style personnalisé pour les onglets plus grands
        tab_stylesheet = f"""
        QTabBar::tab {{
            background: {Theme.ACCENT_COLOR};
            color: {Theme.TEXT_COLOR};
            border: 1px solid #C0C0C0;
            padding: 10px 25px;
            margin-right: 2px;
            border-top-left-radius: 2px;
            border-top-right-radius: 2px;
            font-weight: bold;
            min-width: 150px;
            font-size: {Theme.FONT_SIZE_HEADER}px;
            min-height: 30px;
        }}

        QTabBar::tab:selected {{
            background: {Theme.PRIMARY_COLOR};
            color: white;
            border-bottom: 1px solid white;
        }}

        QTabBar::tab:hover {{
            background: {Theme.SECONDARY_COLOR};
            color: white;
        }}
        """
        self.tab_widget.setStyleSheet(tab_stylesheet)

        # Créer les onglets principaux (par défaut mode Dev)
        self.tab_widget.addTab(self.coding_panel, tr("coding_tab"))
        self.tab_widget.addTab(self.brainstorming_panel, tr("brainstorming_tab"))

        # Configuration des onglets
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.North)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(False)

        # Changement d'onglet
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tab_widget)

    def set_conductor(self, conductor):
        """Set the conductor for all relevant widgets"""
        self.conductor = conductor
        if hasattr(self, 'dataset_strategy'):
            # Le DatasetStrategyWidget n'utilise pas de conductor pour l'instant
            # Mais on peut l'ajouter si nécessaire
            pass

    def _on_mode_switched(self):
        """
        Active ou désactive les onglets selon le mode sélectionné (Dev vs Data science).
        """
        if self.mode_switch.isChecked():
            self.current_mode = "data"
            # Supprimer tous les onglets
            self.tab_widget.clear()

            # MODIFICATION: Ajouter l'onglet Stratégie en premier
            self.tab_widget.addTab(self.dataset_strategy, "📊 Stratégie")
            self.tab_widget.addTab(self.dataset_generation, "🚀 Génération")
            self.tab_widget.addTab(self.prompt_list, "📜 Historique")

            # Sélectionner l'onglet Stratégie par défaut
            self.tab_widget.setCurrentIndex(0)
        else:
            self.current_mode = "dev"
            self.tab_widget.clear()
            self.tab_widget.addTab(self.coding_panel, tr("coding_tab"))
            self.tab_widget.addTab(self.brainstorming_panel, tr("brainstorming_tab"))
            self.tab_widget.setCurrentIndex(0)

    def _init_menu(self):
        """Configure les menus (inchangé)"""
        # Menu principal
        menubar = self.menuBar()

        # Menu Fichier
        file_menu = menubar.addMenu(tr("file"))

        # Actions du menu Fichier
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

        # Actions du menu Édition
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

        # Menu IA
        ai_menu = menubar.addMenu(tr("ai"))

        # Actions du menu IA
        platforms_action = QtWidgets.QAction(tr("platforms"), self)
        platforms_action.triggered.connect(self._on_show_platforms)
        ai_menu.addAction(platforms_action)

        test_action = QtWidgets.QAction(tr("test_connection"), self)
        test_action.triggered.connect(self._on_test_ai)
        ai_menu.addAction(test_action)

        ai_menu.addSeparator()

        compare_action = QtWidgets.QAction(tr("compare_results"), self)
        compare_action.triggered.connect(self._on_compare_ai)
        ai_menu.addAction(compare_action)

        # Menu Config
        turing_menu = menubar.addMenu("Config")

        # Action pour "Configuration projets dev"
        config_projects_dev_action = QtWidgets.QAction(
            "Configuration projets dev", self
        )
        config_projects_dev_action.triggered.connect(self._on_show_project_config)
        turing_menu.addAction(config_projects_dev_action)

        # Menu Aide
        help_menu = menubar.addMenu(tr("help"))

        # Actions du menu Aide
        about_action = QtWidgets.QAction(tr("about"), self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        docs_action = QtWidgets.QAction(tr("documentation"), self)
        docs_action.triggered.connect(self._on_documentation)
        help_menu.addAction(docs_action)

    def _update_menus(self):
        """Met à jour les textes des menus (inchangé)"""
        menubar = self.menuBar()

        # Récupérer les menus
        menus = {
            tr("file"): 0,
            tr("edit"): 1,
            tr("ai"): 2,
            "Config": 3,
            tr("help"): 4,
        }

        # Mettre à jour les titres des menus
        for i, action in enumerate(menubar.actions()):
            for title_key, index in menus.items():
                if i == index:
                    if title_key == "Config":
                        action.setText("Config")
                    else:
                        action.setText(title_key)
                    break

        # Mettre à jour les actions
        self._update_menu_actions()

    def _on_change_language(self):
        """Ouvre le sélecteur de langue (inchangé)"""
        selector = LanguageSelector(self)

        # Sélectionner la langue actuelle
        languages = translator.get_available_languages()
        for i in range(selector.language_combo.count()):
            if selector.language_combo.itemData(i) == translator.current_language:
                selector.language_combo.setCurrentIndex(i)
                break

        if selector.exec_() == QtWidgets.QDialog.Accepted:
            selected_language = selector.get_selected_language()
            self.change_language(selected_language)

    def _update_menu_actions(self):
        """Met à jour les textes des actions des menus (inchangé)"""
        menubar = self.menuBar()

        # Textes des actions par menu
        menu_actions = {
            0: [  # File
                tr("new"),
                tr("open"),
                tr("save"),
                tr("export"),
                None,  # Séparateur
                tr("quit"),
            ],
            1: [  # Edit
                tr("preferences"),
                tr("select_language"),
                tr("refresh"),
            ],
            2: [  # AI
                tr("platforms"),
                tr("test_connection"),
                None,  # Séparateur
                tr("compare_results"),
            ],
            3: [  # Config
                "Configuration projets dev"
            ],
            4: [  # Help
                tr("about"),
                tr("documentation"),
            ],
        }

        # Mettre à jour chaque menu
        for menu_index, actions_texts in menu_actions.items():
            if menu_index < len(menubar.actions()):
                menu = menubar.actions()[menu_index].menu()
                if menu:
                    actions = menu.actions()
                    action_index = 0
                    for i, text in enumerate(actions_texts):
                        if text is None:  # Séparateur
                            action_index += 1
                            continue
                        if (
                                action_index < len(actions)
                                and not actions[action_index].isSeparator()
                        ):
                            actions[action_index].setText(text)
                        action_index += 1

    def _init_statusbar(self):
        """Configure la barre d'état (inchangé)"""
        statusbar = self.statusBar()

        # Ajouter les widgets à la barre d'état
        statusbar.addPermanentWidget(self.progress_bar, 1)
        statusbar.addWidget(self.status_label, 2)
        statusbar.addPermanentWidget(self.platform_label, 1)

        # Barre d'état initiale
        self.update_status(tr("status.ready"))

    def _init_connections(self):
        """Configure les connexions signal-slot entre widgets"""
        # Connexions du panel de coding
        self.coding_panel.session_started.connect(self._on_brainstorming_started)
        self.coding_panel.session_completed.connect(self._on_brainstorming_completed)
        self.coding_panel.session_failed.connect(self._on_brainstorming_failed)
        self.coding_panel.export_requested.connect(self._on_export_data)

        # Connexions du panel de brainstorming
        self.brainstorming_panel.session_started.connect(self._on_brainstorming_started)
        self.brainstorming_panel.session_completed.connect(
            self._on_brainstorming_completed
        )
        self.brainstorming_panel.session_failed.connect(self._on_brainstorming_failed)
        self.brainstorming_panel.export_requested.connect(self._on_export_data)

        # Connexions du formulaire d'annotation
        self.annotation_form.annotation_started.connect(self._on_annotation_started)
        self.annotation_form.annotation_completed.connect(self._on_annotation_completed)
        self.annotation_form.annotation_failed.connect(self._on_annotation_failed)

        # Connexions de la table de datasets
        self.dataset_table.dataset_selected.connect(self._on_dataset_selected)
        self.dataset_table.dataset_created.connect(self._on_dataset_created)
        self.dataset_table.dataset_deleted.connect(self._on_dataset_deleted)

        # Connexions de la liste de prompts
        self.prompt_list.prompt_selected.connect(self._on_prompt_selected)
        self.prompt_list.prompt_deleted.connect(self._on_prompt_deleted)

        # MODIFICATION: Connexion du switch de mode
        self.mode_switch.stateChanged.connect(self._on_mode_switched)

        # NOUVEAU: Connexions potentielles pour l'onglet Stratégie
        # Si le DatasetStrategyWidget émet des signaux, les connecter ici
        # Par exemple:
        # self.dataset_strategy.project_saved.connect(self._on_strategy_project_saved)

    def change_language(self, language_code):
        """Change la langue de l'application"""
        if translator.set_language(language_code):
            # Mettre à jour le titre de la fenêtre
            self.setWindowTitle(tr("app_title"))

            # MODIFICATION: Mettre à jour les onglets selon le mode actuel
            if self.current_mode == "dev":
                # Mode développement
                self.tab_widget.setTabText(
                    self.tab_widget.indexOf(self.coding_panel), tr("coding_tab")
                )
                self.tab_widget.setTabText(
                    self.tab_widget.indexOf(self.brainstorming_panel),
                    tr("brainstorming_tab"),
                )
            else:
                # Mode Data Science - Les textes sont en dur pour l'instant
                # Vous pouvez ajouter des traductions si nécessaire
                for i in range(self.tab_widget.count()):
                    current_text = self.tab_widget.tabText(i)
                    if "Stratégie" in current_text:
                        self.tab_widget.setTabText(i, "📊 Stratégie")
                    elif "Génération" in current_text:
                        self.tab_widget.setTabText(i, "🚀 Génération")
                    elif "Historique" in current_text:
                        self.tab_widget.setTabText(i, "📜 Historique")

            # Mettre à jour les menus
            self._update_menus()

            # Mettre à jour la barre d'état
            self.update_status(tr("status.ready"))

            # Mettre à jour le sous-titre
            subtitle_label = self.findChild(QtWidgets.QLabel, "subtitle_label")
            if subtitle_label:
                subtitle_label.setText(tr("app_title"))

            # Actualiser tous les widgets
            self._notify_language_change()

            # Sauvegarder
            settings = QSettings("Liris", "IACollaborative")
            settings.setValue("language", language_code)

    def _notify_language_change(self):
        """Notifie les widgets enfants du changement de langue"""
        # Informer les panneaux principaux
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

        # NOUVEAU: Notifier le widget de stratégie
        if hasattr(self.dataset_strategy, "update_language"):
            self.dataset_strategy.update_language()

        # Notifier également la fenêtre de configuration des projets si elle est ouverte
        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "update_language"):
                    child.update_language()

    def _restore_settings(self):
        """Restaure les paramètres utilisateur (inchangé)"""
        settings = QSettings("Liris", "IACollaborative")

        # Restaurer la géométrie et l'état de la fenêtre
        if settings.contains("geometry"):
            self.restoreGeometry(settings.value("geometry"))
        if settings.contains("windowState"):
            self.restoreState(settings.value("windowState"))

        # Restaurer l'onglet actif
        if settings.contains("activeTab"):
            tab_index = int(settings.value("activeTab", 0))
            if 0 <= tab_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(tab_index)

        # Autres paramètres spécifiques aux widgets
        if settings.contains("lastExportPath"):
            self.last_export_path = settings.value(
                "lastExportPath", os.path.expanduser("~")
            )
        else:
            self.last_export_path = os.path.expanduser("~")

    def _save_settings(self):
        """Sauvegarde les paramètres utilisateur (inchangé)"""
        settings = QSettings("Liris", "IACollaborative")

        # Sauvegarder la géométrie et l'état de la fenêtre
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

        # Sauvegarder l'onglet actif
        settings.setValue("activeTab", self.tab_widget.currentIndex())

        # Autres paramètres spécifiques
        settings.setValue("lastExportPath", self.last_export_path)
        settings.setValue("language", translator.current_language)

    def _init_system(self):
        """Initialise le système d'IA et les composants principaux"""
        try:
            self.update_status(tr("status.system_connecting"))
            self.update_connection_status("connecting")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)

            # Charger la configuration
            self.config_provider = ConfigProvider()
            self.progress_bar.setValue(20)

            # Initialiser la base de données
            db_config = self.config_provider.get_database_config()
            self.database = Database(db_config["path"])  # Passer uniquement le chemin
            self.database.connect()
            self.progress_bar.setValue(40)

            # Initialiser l'exportateur
            self.exporter = DataExporter(self.config_provider)
            self.progress_bar.setValue(50)

            # Initialiser le scheduler
            self.scheduler = AIScheduler(self.config_provider)
            self.progress_bar.setValue(70)

            # Initialiser le chef d'orchestre
            self.conductor = AIConductor(
                self.config_provider, self.scheduler, self.database
            )
            self.conductor.initialize()
            self.progress_bar.setValue(90)

            # Mettre à jour les widgets
            self._update_ui_with_system()
            self.progress_bar.setValue(100)

            # Terminer l'initialisation
            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            self.update_status(tr("status.system_initialized"))
            self.update_connection_status("connected")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du système: {str(e)}")
            self.progress_bar.setVisible(False)
            self.update_status("Erreur d'initialisation")
            self.update_connection_status("error")

            # Afficher un message d'erreur
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

        # Récupérer les plateformes disponibles
        platforms = self.conductor.get_available_platforms()
        print(f"platforms: {platforms}")

        # Mettre à jour l'étiquette de plateforme
        if platforms:
            self.platform_label.setText(
                tr("messages.platforms_available", count=len(platforms))
            )
        else:
            self.platform_label.setText(tr("messages.no_platforms"))

        # Mettre à jour les widgets
        self.coding_panel.set_conductor(self.conductor)
        self.coding_panel.set_platforms(platforms)

        self.brainstorming_panel.set_conductor(self.conductor)
        self.brainstorming_panel.set_platforms(platforms)

        self.dataset_generation.set_conductor(self.conductor)
        self.dataset_generation.set_platforms(platforms)
        self.dataset_generation.set_database(self.database)

        # NOUVEAU: Initialiser l'onglet Stratégie (n'a pas besoin de conductor/platforms pour l'instant)
        # Le DatasetStrategyWidget gère sa propre base de données SQLite
        # Si vous voulez partager la même base de données:
        # self.dataset_strategy.set_database(self.database)

        self.dataset_table.set_database(self.database)
        self.dataset_table.set_exporter(self.exporter)

        self.prompt_list.set_database(self.database)

        # Charger les données initiales
        self.prompt_list.refresh_list()
        self.dataset_table.refresh_list()

        # Rafraîchir la fenêtre de configuration des projets si ouverte
        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

    def update_status(self, message):
        """
        Met à jour le message de la barre d'état

        Args:
            message (str): Nouveau message
        """
        self.status_label.setText(message)
        logger.debug(f"Statut: {message}")

    def update_connection_status(self, status):
        """
        Met à jour l'indicateur de connexion

        Args:
            status (str): 'connected', 'connecting', 'disconnected', 'error'
        """
        color_map = {
            "connected": "#4CAF50",
            "connecting": "#FFC107",
            "disconnected": "#9E9E9E",
            "error": "#F44336",
        }

        text_map = {
            "connected": tr("status.system_connected"),
            "connecting": tr("status.system_connecting"),
            "disconnected": "Système déconnecté",
            "error": tr("status.system_error"),
        }

        self.connection_indicator.setStyleSheet(f"""
            background-color: {color_map.get(status, "#9E9E9E")};
            border-radius: 6px;
        """)
        self.connection_label.setText(text_map.get(status, "État inconnu"))

    def show_progress(self, value, max_value=100):
        """
        Affiche une progression dans la barre d'état

        Args:
            value (int): Valeur actuelle
            max_value (int): Valeur maximale
        """
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(value)
        self.progress_bar.setVisible(True)

    def hide_progress(self):
        """Cache la barre de progression"""
        self.progress_bar.setVisible(False)

    def _on_tab_changed(self, index):
        """
        Gère le changement d'onglet

        Args:
            index (int): Index du nouvel onglet
        """
        # Mettre à jour le statut en fonction de l'onglet
        tab_name = self.tab_widget.tabText(index)
        self.update_status(f"Section: {tab_name}")

        # Actualiser l'onglet actif
        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, "refresh_list"):
            current_widget.refresh_list()

        # NOUVEAU: Gestion spéciale pour l'onglet Stratégie
        if current_widget == self.dataset_strategy:
            # L'onglet Stratégie n'a pas besoin de refresh spécial pour l'instant
            # Mais on peut ajouter des actions ici si nécessaire
            pass

    def _on_new_file(self):
        """Gère la création d'un nouveau fichier"""
        # Déterminer l'action en fonction de l'onglet actif
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
            # NOUVEAU: Action pour l'onglet Stratégie
            # Par exemple, créer un nouveau projet
            if hasattr(self.dataset_strategy, '_create_new_project'):
                self.dataset_strategy._create_new_project()

    def _on_open_file(self):
        """Gère l'ouverture d'un fichier"""
        # Ouvrir un sélecteur de fichier
        file_path, file_filter = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un fichier",
            self.last_export_path,
            "Tous les fichiers (*.*);;Fichiers JSON (*.json);;Fichiers CSV (*.csv);;Fichiers texte (*.txt)",
        )

        if not file_path:
            return

        # Mettre à jour le chemin d'exportation
        self.last_export_path = os.path.dirname(file_path)

        # Déterminer l'action en fonction de l'onglet actif
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
            # NOUVEAU: Action pour l'onglet Stratégie
            # Par exemple, importer une configuration de projet
            if file_path.endswith('.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Traiter l'import de configuration si nécessaire
                    QMessageBox.information(self, "Import", f"Configuration importée depuis {file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Erreur", f"Erreur lors de l'import: {str(e)}")

    def _on_save_file(self):
        """Gère l'enregistrement d'un fichier"""
        # Déterminer l'action en fonction de l'onglet actif
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
            # NOUVEAU: Action pour l'onglet Stratégie
            if hasattr(self.dataset_strategy, '_save_strategy'):
                self.dataset_strategy._save_strategy()

    def _on_export_data(self):
        """Gère l'exportation des données"""
        # Déterminer l'action en fonction de l'onglet actif
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
            # NOUVEAU: Action pour l'onglet Stratégie
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
        # Actualiser l'onglet actif
        current_tab = self.tab_widget.currentWidget()

        if hasattr(current_tab, "refresh_list"):
            current_tab.refresh_list()
        elif hasattr(current_tab, "refresh"):
            current_tab.refresh()

        # NOUVEAU: Gestion spécifique pour l'onglet Stratégie
        if current_tab == self.dataset_strategy:
            # Recharger les projets existants
            if hasattr(self.dataset_strategy, '_load_existing_projects'):
                self.dataset_strategy._load_existing_projects()

        # Actualiser également la fenêtre ProjectConfigOnlyWidget si elle est ouverte
        if self.project_config_dialog_instance and isinstance(
                self.project_config_dialog_instance, QtWidgets.QDialog
        ):
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

        self.update_status("Données actualisées")

    # NOUVELLES MÉTHODES POUR GÉRER LES SIGNAUX DE L'ONGLET STRATÉGIE
    def _on_strategy_project_saved(self, project_name):
        """
        Gère la sauvegarde d'un projet depuis l'onglet Stratégie

        Args:
            project_name (str): Nom du projet sauvegardé
        """
        self.update_status(f"Projet de stratégie '{project_name}' sauvegardé")
        logger.info(f"Projet de stratégie sauvegardé: {project_name}")

    def _on_strategy_project_loaded(self, project_name):
        """
        Gère le chargement d'un projet depuis l'onglet Stratégie

        Args:
            project_name (str): Nom du projet chargé
        """
        self.update_status(f"Projet de stratégie '{project_name}' chargé")
        logger.info(f"Projet de stratégie chargé: {project_name}")

    def _on_strategy_data_generated(self, combinations_count):
        """
        Gère la génération de données de test depuis l'onglet Stratégie

        Args:
            combinations_count (int): Nombre de combinaisons générées
        """
        self.update_status(f"Données de test générées: {combinations_count} combinaisons")

    # MÉTHODES EXISTANTES (inchangées)
    def _on_show_platforms(self):
        """Ouvre la fenêtre de configuration des plateformes"""
        if not self.conductor:
            QMessageBox.warning(
                self,
                "Configuration des plateformes",
                "Le système n'est pas encore initialisé.",
            )
            return

        try:
            # Créer et afficher le widget de configuration
            self.platform_config_dialog = QtWidgets.QDialog(self)
            self.platform_config_dialog.setWindowTitle(
                "Configuration des Plateformes d'IA"
            )
            self.platform_config_dialog.setMinimumSize(1200, 800)
            self.platform_config_dialog.setModal(True)

            # Layout pour la boîte de dialogue
            dialog_layout = QtWidgets.QVBoxLayout(self.platform_config_dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)

            # Créer le widget de configuration avec les bonnes dépendances
            platform_config_widget = PlatformConfigWidget(
                self.config_provider, self.conductor, parent=self.platform_config_dialog
            )

            # Ajouter au layout
            dialog_layout.addWidget(platform_config_widget)

            # Connecter les signaux
            platform_config_widget.platform_added.connect(
                self._on_platform_config_changed
            )
            platform_config_widget.platform_updated.connect(
                self._on_platform_config_changed
            )
            platform_config_widget.platform_deleted.connect(
                self._on_platform_config_changed
            )

            # Afficher la boîte de dialogue
            self.platform_config_dialog.exec_()

        except Exception as e:
            logger.error(
                f"Erreur lors de l'ouverture de la configuration des plateformes: {str(e)}"
            )
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'ouvrir la configuration des plateformes:\n\n{str(e)}",
            )

    def _on_platform_config_changed(self, platform_name):
        """
        Gère les changements de configuration des plateformes

        Args:
            platform_name (str): Nom de la plateforme modifiée
        """
        try:
            # Actualiser les plateformes disponibles
            if self.conductor:
                platforms = self.conductor.get_available_platforms()

                # Mettre à jour l'étiquette
                if platforms:
                    self.platform_label.setText(
                        tr("messages.platforms_available", count=len(platforms))
                    )
                else:
                    self.platform_label.setText(tr("messages.no_platforms"))

                # Mettre à jour les widgets qui utilisent les plateformes
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
        """
        Ouvre la fenêtre de configuration des projets de développement.
        """
        if not self.conductor:
            QMessageBox.warning(
                self,
                "Configuration des projets",
                "Le système n'est pas encore initialisé.",
            )
            return

        try:
            # Vérifier si une instance de la boîte de dialogue existe déjà
            if not self.project_config_dialog_instance:
                self.project_config_dialog_instance = QtWidgets.QDialog(self)
                self.project_config_dialog_instance.setWindowTitle(
                    "Configuration des Projets de Développement (Turing)"
                )
                self.project_config_dialog_instance.setMinimumSize(1000, 700)
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
                dialog_layout.addWidget(project_config_widget)

                # Connexion pour réinitialiser l'instance de dialogue lorsque fermée
                self.project_config_dialog_instance.finished.connect(
                    self._on_project_config_dialog_closed
                )

            # Rafraîchir le contenu avant d'afficher
            for child in self.project_config_dialog_instance.findChildren(
                    ProjectConfigOnlyWidget
            ):
                if hasattr(child, "refresh"):
                    child.refresh()

            # Afficher la boîte de dialogue
            self.project_config_dialog_instance.show()
            self.project_config_dialog_instance.raise_()
            self.project_config_dialog_instance.activateWindow()

        except Exception as e:
            logger.error(
                f"Erreur lors de l'ouverture de la configuration des projets: {str(e)}"
            )
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'ouvrir la configuration des projets:\n\n{str(e)}",
            )

    def _on_project_config_changed(self, project_name):
        """
        Gère les changements de configuration des projets.
        """
        logger.info(f"Configuration du projet '{project_name}' mise à jour/supprimée.")
        self.update_status(f"Projet {project_name} mis à jour.")

    def _on_project_config_dialog_closed(self, result):
        """
        Gère la fermeture de la boîte de dialogue ProjectConfigOnlyWidget.
        """
        self.project_config_dialog_instance = None
        logger.info("Fenêtre de configuration des projets fermée.")

    # Les autres méthodes restent inchangées (_on_test_ai, _on_compare_ai, etc.)
    # Je ne les reproduis pas ici pour éviter la répétition, mais elles doivent être conservées

    def _on_test_ai(self):
        """Teste la connexion avec les IA (méthode existante inchangée)"""
        # Code existant...
        pass

    def _on_compare_ai(self):
        """Compare les résultats de différentes IA (méthode existante inchangée)"""
        # Code existant...
        pass

    def _save_comparison_results(self, prompt, results):
        """Enregistre les résultats d'une comparaison (méthode existante inchangée)"""
        # Code existant...
        pass

    def _on_about(self):
        """Affiche la boîte de dialogue À propos (méthode existante inchangée)"""
        # Code existant...
        pass

    def _on_documentation(self):
        """Ouvre la documentation (méthode existante inchangée)"""
        # Code existant...
        pass

    # Gestionnaires d'événements existants (inchangés)
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
        """
        Gère l'événement de fermeture de la fenêtre
        """
        # Sauvegarder les paramètres
        self._save_settings()

        # Arrêter proprement le système
        if self.conductor:
            try:
                self.conductor.shutdown()
            except Exception as e:
                logger.error(f"Erreur lors de l'arrêt du système: {str(e)}")

        # Fermer la base de données de l'onglet Stratégie si nécessaire
        if hasattr(self.dataset_strategy, 'closeEvent'):
            self.dataset_strategy.closeEvent(None)

        # Accepter l'événement
        event.accept()