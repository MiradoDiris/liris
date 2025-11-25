#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from ui.localization.translator import tr
from ui.styles.theme import Theme
from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager
from ui.widgets.tabs.dataset_config_tab import DatasetConfigTab
from ui.widgets.tabs.dataset_preview_tab import DatasetPreviewTab
from ui.widgets.tabs.dataset_relation_tab import DatasetRelationTab
from utils.logger import logger


class CustomTabBar(QtWidgets.QTabBar):
    """TabBar personnalisée qui contrôle complètement le rendu des onglets"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tab_states = {}  # {index: True/False pour actif}
    
    def set_tab_active_state(self, index, is_active):
        """Force l'état visuel d'un onglet"""
        self._tab_states[index] = is_active
        self.update()
    
    def paintEvent(self, event):
        """Override du rendu pour forcer les couleurs"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        try:
            from ui.styles.theme import Theme
            primary_color = QtGui.QColor(Theme.PRIMARY_COLOR)
            secondary_color = QtGui.QColor(Theme.SECONDARY_COLOR)
        except:
            primary_color = QtGui.QColor("#A23B2D")
            secondary_color = QtGui.QColor("#8B2F22")
        
        inactive_color = QtGui.QColor("#F5F5F5")
        inactive_border = QtGui.QColor("#BDC3C7")
        
        for i in range(self.count()):
            rect = self.tabRect(i)
            
            # Déterminer si l'onglet doit être actif visuellement
            is_visually_active = self._tab_states.get(i, i == 0)
            
            # Dessiner le fond
            if is_visually_active:
                # Créer un gradient
                gradient = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
                gradient.setColorAt(0, primary_color)
                gradient.setColorAt(1, secondary_color)
                painter.setBrush(gradient)
                painter.setPen(Qt.NoPen)
            else:
                painter.setBrush(inactive_color)
                painter.setPen(Qt.NoPen)
            
            # Dessiner le rectangle arrondi
            painter.drawRoundedRect(rect.adjusted(6, 6, -6, -3), 6, 6)
        
        # Laisser Qt dessiner le reste (texte, etc.) par dessus
        painter.end()
        super().paintEvent(event)


class DatasetGeneratorWidget(QtWidgets.QWidget):
    """
    Modern widget for dataset generation management with hierarchical structure.
    Relies entirely on DatasetProjectManager for business logic.
    """

    def __init__(self, conductor=None, parent=None):
        super().__init__(parent)
        self.conductor = conductor
        self.platforms = []

        # Default configuration
        self.config_data = {
            'platform': 'ChatGPT',
            'description': '',
            'output_format': 'JSON',
            'sample_count': 100,
            'training_technique': 'Full SFT'
        }

        # Initialize managers (complete delegation)
        self.db = DatasetDatabase()
        self.project_manager = DatasetProjectManager(self.db)

        # Variables pour le responsive
        self.is_mobile_mode = False
        self.last_size = QtCore.QSize(800, 600)

        self._init_ui()

    def _init_ui(self):
        """Configure user interface"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QtWidgets.QTabWidget()
        
        # ✅ Utiliser notre TabBar personnalisée
        self.custom_tab_bar = CustomTabBar()
        self.tab_widget.setTabBar(self.custom_tab_bar)

        # Configuration tab avec indicateur numéroté
        self.config_tab = DatasetConfigTab(
            self.project_manager,
            self.config_data,
            parent=self
        )
        config_tab_widget = self._create_tab_label("1", tr("dataset.tab_config"), True)
        tab_index_0 = self.tab_widget.addTab(self.config_tab, "")
        self.tab_widget.tabBar().setTabButton(
            tab_index_0, QtWidgets.QTabBar.LeftSide, config_tab_widget
        )

        # Relation tab avec indicateur numéroté
        self.relation_tab = DatasetRelationTab(
            self.project_manager,
            self.config_data,
            parent=self
        )
        relation_tab_widget = self._create_tab_label("2", tr("dataset.tab_relation"), False)
        tab_index_1 = self.tab_widget.addTab(self.relation_tab, "")
        self.tab_widget.tabBar().setTabButton(
            tab_index_1, QtWidgets.QTabBar.LeftSide, relation_tab_widget
        )

        # Dataset preview tab avec indicateur numéroté
        self.preview_tab = DatasetPreviewTab(
            self.project_manager,
            self.config_data,
            parent=self
        )
        preview_tab_widget = self._create_tab_label("3", tr("dataset.tab_preview"), False)
        tab_index_2 = self.tab_widget.addTab(self.preview_tab, "")
        self.tab_widget.tabBar().setTabButton(
            tab_index_2, QtWidgets.QTabBar.LeftSide, preview_tab_widget
        )

        # Stocker les références aux widgets d'onglets
        self.config_tab_widget = config_tab_widget
        self.relation_tab_widget = relation_tab_widget
        self.preview_tab_widget = preview_tab_widget

        # Connect signals
        self.config_tab.project_saved.connect(self._on_project_saved)
        self.config_tab.preview_updated.connect(self.preview_tab.update_preview)
        self.config_tab.preview_updated.connect(self.relation_tab.update_relation)

        # Connecter le changement d'onglet
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # ✅ Appliquer le style transparent pour laisser notre paint prendre le dessus
        self._apply_custom_tab_style()

        main_layout.addWidget(self.tab_widget)

        # ✅ Initialiser le système responsive
        self._init_responsive_ui()
        self._add_maximize_button()
        self._add_responsive_animations()

    def _init_responsive_ui(self):
        """Initialise le système de détection de redimensionnement"""
        self.installEventFilter(self)
        self.last_size = self.size()
        QtCore.QTimer.singleShot(100, self._adjust_for_screen_resolution)

    def eventFilter(self, obj, event):
        """Filtre les événements pour détecter le redimensionnement"""
        if obj == self and event.type() == QtCore.QEvent.Resize:
            self._on_window_resized(event.size())
        return super().eventFilter(obj, event)

    def _on_window_resized(self, new_size):
        """Gère le redimensionnement de la fenêtre"""
        if (abs(new_size.width() - self.last_size.width()) > 100 or
                abs(new_size.height() - self.last_size.height()) > 100):
            self.last_size = new_size
            self._adjust_for_screen_resolution()

    def _adjust_for_screen_resolution(self):
        """Ajuste la mise en page selon la résolution d'écran actuelle"""
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()

        if screen_width >= 3840:
            scale_factor = 1.3
        elif screen_width >= 2560:
            scale_factor = 1.15
        elif screen_width >= 1920:
            scale_factor = 1.0
        elif screen_width >= 1366:
            scale_factor = 0.9
        else:
            scale_factor = 0.8

        self._apply_scale_factor(scale_factor)

    def _apply_scale_factor(self, scale):
        """Applique le facteur d'échelle aux éléments de l'interface"""
        base_tab_width = 200
        base_circle_size = 28
        base_font_size = 12

        scaled_tab_width = int(base_tab_width * scale)
        scaled_circle_size = int(base_circle_size * scale)
        scaled_font_size = int(base_font_size * scale)

        self._update_tab_widget_sizes(
            scaled_tab_width, scaled_circle_size, scaled_font_size
        )

    def _update_tab_widget_sizes(self, width, circle_size, font_size):
        """Met à jour les tailles des widgets d'onglets"""
        current_index = self.tab_widget.currentIndex()
        
        for idx, tab_widget in enumerate([self.config_tab_widget, self.relation_tab_widget, self.preview_tab_widget]):
            if not tab_widget:
                continue

            tab_widget.setFixedWidth(width)
            tab_widget.circle_label.setFixedSize(circle_size, circle_size)

            border_radius = circle_size // 2
            
            # ✅ Déterminer si l'onglet doit être actif
            should_be_active = False
            if current_index == 0:
                should_be_active = (idx == 0)
            elif current_index == 1:
                should_be_active = (idx <= 1)
            elif current_index == 2:
                should_be_active = True  # TOUS actifs

            if should_be_active:
                circle_style = f"""
                    QLabel {{
                        background-color: #2C3E50;
                        color: white;
                        border-radius: {border_radius}px;
                        font-size: {font_size}px;
                        font-weight: 600;
                        border: 2px solid #2C3E50;
                    }}
                """
                text_color = 'white'
            else:
                circle_style = f"""
                    QLabel {{
                        background-color: #E0E0E0;
                        color: #7F8C8D;
                        border-radius: {border_radius}px;
                        font-size: {font_size}px;
                        font-weight: 600;
                        border: 2px solid #BDC3C7;
                    }}
                """
                text_color = '#7F8C8D'

            tab_widget.circle_label.setStyleSheet(circle_style)
            text_style = f"""
                font-size: {font_size}px;
                font-weight: 600;
                color: {text_color};
                background: transparent;
                padding: 0px;
                margin-left: 4px;
            """
            tab_widget.text_label.setStyleSheet(text_style)

    def _add_maximize_button(self):
        """Ajoute le bouton Agrandir/Réduire à la fenêtre"""
        main_window = self.window()
        if not main_window:
            return

        main_window.setWindowFlags(
            main_window.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint
        )
        main_window.show()

    def _add_responsive_animations(self):
        """Ajoute des animations fluides lors des transitions responsive"""
        self.tab_animation = QtCore.QPropertyAnimation(self.tab_widget, b"geometry")
        self.tab_animation.setDuration(300)
        self.tab_animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

    def showEvent(self, event):
        """Gère l'affichage initial du widget."""
        super().showEvent(event)
        current_index = self.tab_widget.currentIndex()
        self._on_tab_changed(current_index)

    def _create_tab_label(self, number, text, is_active):
        """Crée un widget d'onglet personnalisé avec cercle numéroté"""
        container = QtWidgets.QWidget()
        container.setFixedWidth(200)

        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        circle = QtWidgets.QLabel(number)
        circle.setFixedSize(28, 28)
        circle.setAlignment(QtCore.Qt.AlignCenter)

        if is_active:
            circle.setStyleSheet("""
                QLabel {
                    background-color: #2C3E50;
                    color: white;
                    border-radius: 14px;
                    font-size: 13px;
                    font-weight: 600;
                    border: 2px solid #2C3E50;
                }
            """)
        else:
            circle.setStyleSheet("""
                QLabel {
                    background-color: #E0E0E0;
                    color: #7F8C8D;
                    border-radius: 14px;
                    font-size: 13px;
                    font-weight: 600;
                    border: 2px solid #BDC3C7;
                }
            """)

        text_label = QtWidgets.QLabel(text)
        text_label.setAlignment(QtCore.Qt.AlignCenter)
        text_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {'white' if is_active else '#7F8C8D'};
            background: transparent;
        """)

        layout.addStretch()
        layout.addWidget(circle, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(text_label, alignment=QtCore.Qt.AlignCenter)
        layout.addStretch()

        container.setLayout(layout)
        container.circle_label = circle
        container.text_label = text_label
        container.is_active = is_active

        return container

    def _apply_custom_tab_style(self):
        """Applique un style personnalisé minimal pour laisser le paint custom fonctionner"""
        stylesheet = f"""
            QTabWidget::pane {{
                border: none;
                background: white;
                margin-top: 0px;
            }}
            QTabBar {{
                background: transparent;
                border: none;
            }}
            QTabBar::tab {{
                border: none;
                padding: 8px 16px;
                margin-right: 6px;
                margin-top: 6px;
                margin-bottom: 3px;
                font-weight: 600;
                font-size: 12px;
                min-width: 170px;
                min-height: 36px;
                background: transparent;
            }}
        """
        self.tab_widget.setStyleSheet(stylesheet)

    def _on_tab_changed(self, index):
        """Gère le changement d'onglet avec activation en cascade."""
        logger.debug(f"📍 Changement d'onglet vers index {index}")

        # ✅ Définir les états visuels dans la CustomTabBar
        if index == 0:
            self.custom_tab_bar.set_tab_active_state(0, True)
            self.custom_tab_bar.set_tab_active_state(1, False)
            self.custom_tab_bar.set_tab_active_state(2, False)
            states = [True, False, False]
        elif index == 1:
            self.custom_tab_bar.set_tab_active_state(0, True)
            self.custom_tab_bar.set_tab_active_state(1, True)
            self.custom_tab_bar.set_tab_active_state(2, False)
            states = [True, True, False]
        else:  # index == 2
            self.custom_tab_bar.set_tab_active_state(0, True)
            self.custom_tab_bar.set_tab_active_state(1, True)
            self.custom_tab_bar.set_tab_active_state(2, True)
            states = [True, True, True]
            logger.debug("🔒 Sur Aperçu : TOUS les onglets visuellement actifs")

        # ✅ Mettre à jour les labels (cercles et texte)
        for idx, (tab_widget, should_be_active) in enumerate(zip(
            [self.config_tab_widget, self.relation_tab_widget, self.preview_tab_widget],
            states
        )):
            if not tab_widget:
                continue

            if should_be_active:
                tab_widget.circle_label.setStyleSheet("""
                    QLabel {
                        background-color: #2C3E50;
                        color: white;
                        border-radius: 14px;
                        font-size: 13px;
                        font-weight: 600;
                        border: 2px solid #2C3E50;
                    }
                """)
                tab_widget.text_label.setStyleSheet("""
                    font-size: 12px;
                    font-weight: 600;
                    color: white;
                    background: transparent;
                    padding: 0px;
                    margin-left: 4px;
                """)
            else:
                tab_widget.circle_label.setStyleSheet("""
                    QLabel {
                        background-color: #E0E0E0;
                        color: #7F8C8D;
                        border-radius: 14px;
                        font-size: 13px;
                        font-weight: 600;
                        border: 2px solid #BDC3C7;
                    }
                """)
                tab_widget.text_label.setStyleSheet("""
                    font-size: 12px;
                    font-weight: 600;
                    color: #7F8C8D;
                    background: transparent;
                    padding: 0px;
                    margin-left: 4px;
                """)

    def _on_project_saved(self):
        """Handle project saved event"""
        self.relation_tab.refresh_data()
        self.preview_tab.refresh_projects()
        self.tab_widget.setCurrentIndex(2)

        QtWidgets.QMessageBox.information(
            self,
            tr("dataset.success"),
            f"{tr('dataset.project_saved')}: '{self.project_manager.current_project_name}'"
        )

    def set_conductor(self, conductor):
        """Set conductor for browser control"""
        self.conductor = conductor

    def set_platforms(self, platforms):
        """Set available platforms"""
        self.platforms = platforms if platforms else []

    def set_database(self, database):
        """Set database connection"""
        pass

    def refresh(self):
        """Refresh widget data"""
        self.config_tab.refresh()
        self.relation_tab.refresh_data()
        self.preview_tab.refresh_projects()
        current_index = self.tab_widget.currentIndex()
        self._on_tab_changed(current_index)

    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'db'):
            self.db.close()