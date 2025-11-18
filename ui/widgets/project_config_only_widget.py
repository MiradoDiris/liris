import traceback
from PyQt5 import QtWidgets, QtCore

from ui.localization.translator import tr
from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.tabs.project_config_widget import ProjectConfigWidget
from ui.widgets.tabs.relation_import_widget import RelationImportWidget
from utils.tab_refresh_helper import add_refresh_to_existing_tabs
from PyQt5.QtCore import pyqtSignal


class ProjectConfigOnlyWidget(QtWidgets.QWidget):
    """
    Widget de configuration des projets et de leur ontologie,
    avec uniquement l'onglet "Configuration de Projet" et "Relations des Importations".
    """
    project_selected = pyqtSignal(bool)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)
        print("ProjectConfigOnlyWidget: Initialisation (sans NodeCreationWidget)...")

        self.setMinimumSize(1400, 900)

        self.config_provider = config_provider
        self.conductor = conductor
        self.project_config_widget_instance = None
        self.relation_import_widget_instance = None

        # Initialize step containers to None
        self.step1_container = None
        self.step2_container = None

        try:
            self._init_ui()

            self.config_timer = QtCore.QTimer()
            self.config_timer.timeout.connect(self._maintain_config_active)
            self.config_timer.start(100)

            print("ProjectConfigOnlyWidget: Initialisation terminée avec succès.")
        except Exception as e:
            logger.error(
                f"Erreur lors de l'initialisation de ProjectConfigOnlyWidget: {str(e)}"
            )
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_responsive_ui(self):
        self.installEventFilter(self)

        # État initial de la taille
        self.last_size = self.size()

        # Ajuster immédiatement selon la résolution d'écran
        QtCore.QTimer.singleShot(100, self._adjust_for_screen_resolution)

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QtCore.QEvent.Resize:
            self._on_window_resized(event.size())
        return super().eventFilter(obj, event)
    
    def _on_window_resized(self, new_size):
        # Éviter les appels répétés inutiles (seuil de 100px)
        if (abs(new_size.width() - self.last_size.width()) > 100 or 
            abs(new_size.height() - self.last_size.height()) > 100):
            self.last_size = new_size
            self._adjust_for_screen_resolution()

    def _adjust_for_screen_resolution(self):
        """
        Ajuste la mise en page selon la résolution d'écran actuelle.
        """
        # Obtenir les dimensions de l'écran principal
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Obtenir les dimensions de la fenêtre
        window_width = self.width()
        window_height = self.height()

        # Déterminer le niveau de résolution
        if screen_width >= 3840:  # 4K et plus
            scale_factor = 1.3
            print("🖥️ Résolution 4K détectée")
        elif screen_width >= 2560:  # QHD
            scale_factor = 1.15
            print("🖥️ Résolution QHD détectée")
        elif screen_width >= 1920:  # Full HD
            scale_factor = 1.0
            print("🖥️ Résolution Full HD détectée")
        elif screen_width >= 1366:  # HD
            scale_factor = 0.9
            print("🖥️ Résolution HD détectée")
        else:  # Petits écrans
            scale_factor = 0.8
            print("🖥️ Petite résolution détectée")

        # Appliquer le facteur d'échelle
        self._apply_scale_factor(scale_factor)

    def _apply_scale_factor(self, scale):
        # Calcul des tailles basées sur le scale
        base_tab_width = 260
        base_circle_size = 32
        base_font_size = 13
        base_tab_height = 40

        scaled_tab_width = int(base_tab_width * scale)
        scaled_circle_size = int(base_circle_size * scale)
        scaled_font_size = int(base_font_size * scale)
        scaled_tab_height = int(base_tab_height * scale)

        # Mettre à jour les widgets d'onglets
        self._update_tab_widget_sizes(
            scaled_tab_width, 
            scaled_circle_size, 
            scaled_font_size
        )

        # Mettre à jour le style des onglets
        self._update_tabs_style_with_scale(scaled_tab_height, scaled_font_size)

    def _add_maximize_button(self):
        # Obtenir la fenêtre principale
        main_window = self.window()

        if not main_window:
            print("⚠️ Impossible de trouver la fenêtre principale")
            return

        # Activer le bouton Maximize dans les flags de la fenêtre
        main_window.setWindowFlags(
            main_window.windowFlags() | 
            QtCore.Qt.WindowMaximizeButtonHint
        )

        # S'assurer que le bouton est visible
        main_window.show()

        print("✅ Bouton Agrandir/Réduire ajouté à la barre de titre")

    def _update_tabs_style_with_scale(self, tab_height, font_size):
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        # Récupérer l'état actuel pour Tab 2
        tab2_enabled = self.tabs.isTabEnabled(1)
        has_project = (self.project_config_widget_instance and 
                       self.project_config_widget_instance.current_project_name)

        # Styles pour Tab 2
        if tab2_enabled and has_project:
            tab2_bg = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_color}, stop:1 {secondary_color})"
            tab2_color = "white"
        else:
            tab2_bg = "#F5F5F5"
            tab2_color = "#BDC3C7"

        stylesheet = f"""
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
                border: none;
                border-radius: 6px;
                padding: {int(tab_height * 0.25)}px {int(tab_height * 0.6)}px;
                margin-right: 8px;
                margin-top: 8px;
                margin-bottom: 4px;
                font-weight: 600;
                font-size: {font_size}px;
                min-height: {tab_height}px;
            }}

            QTabBar::tab:first {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 {primary_color}, stop:1 {secondary_color});
                color: white;
                margin-left: 15px;
            }}

            QTabBar::tab:last {{
                background: {tab2_bg};
                color: {tab2_color};
            }}

            QTabBar::tab:disabled {{
                background: #F5F5F5;
                color: #BDC3C7;
            }}
        """

        self.tabs.setStyleSheet(stylesheet)

    def _update_tab_widget_sizes(self, width, circle_size, font_size):
        for tab_widget in [self.config_tab_widget, self.relations_tab_widget]:
            if not tab_widget:
                continue
            
            # Ajuster le container
            tab_widget.setFixedWidth(width)

            # Ajuster le cercle
            tab_widget.circle_label.setFixedSize(circle_size, circle_size)

            # Ajuster le style du cercle
            border_radius = circle_size // 2

            is_active = hasattr(tab_widget, 'is_active') and tab_widget.is_active

            if is_active:
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

            tab_widget.circle_label.setStyleSheet(circle_style)

            # Ajuster le texte
            text_color = 'white' if is_active else '#7F8C8D'
            text_style = f"""
                font-size: {font_size}px;
                font-weight: 600;
                color: {text_color};
                background: transparent;
                padding: 0px;
                margin-left: 5px;
            """
            tab_widget.text_label.setStyleSheet(text_style)

    def _adjust_responsive_layout(self):
        current_width = self.width()

        # Breakpoints
        MOBILE_BREAKPOINT = 768
        TABLET_BREAKPOINT = 1024

        if current_width < MOBILE_BREAKPOINT:
            self._apply_mobile_layout()
        elif current_width < TABLET_BREAKPOINT:
            self._apply_tablet_layout()
        else:
            self._apply_desktop_layout()

    def _apply_mobile_layout(self):
        if self.is_mobile_mode:
            return

        self.is_mobile_mode = True

        # Adapter les onglets
        self.tabs.setTabPosition(QtWidgets.QTabWidget.West)

        # Réduire la taille des widgets d'onglets
        self._update_tab_widget_size(180, 24, 11)

        # Style mobile pour les onglets
        self._apply_mobile_tab_style()

        print("📱 Mode mobile activé")

    def _apply_tablet_layout(self):
        self.is_mobile_mode = False

        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)

        # Taille intermédiaire
        self._update_tab_widget_size(220, 28, 12)

        # Style tablette
        self._apply_tablet_tab_style()

        print("📱 Mode tablette activé")

    def _apply_desktop_layout(self):
        """
        Mode desktop (> 1024px)
        - Onglets en taille normale
        """
        self.is_mobile_mode = False

        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)

        # Taille normale
        self._update_tab_widget_size(260, 32, 13)

        # Réappliquer le style personnalisé normal
        self._apply_custom_tab_style()

        # Mettre à jour l'état des onglets
        current_tab = self.tabs.currentIndex()
        self._on_tab_changed(current_tab)

        print("🖥️ Mode desktop activé")

    def _update_tab_widget_size(self, width, circle_size, font_size):
        for tab_widget in [self.config_tab_widget, self.relations_tab_widget]:
            if not tab_widget:
                continue
            
            # Ajuster le container
            tab_widget.setFixedWidth(width)

            # Ajuster le cercle
            tab_widget.circle_label.setFixedSize(circle_size, circle_size)

            # Ajuster le style du cercle
            is_active = tab_widget.is_active
            border_radius = circle_size // 2

            if is_active:
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

            tab_widget.circle_label.setStyleSheet(circle_style)

            # Ajuster le texte
            text_style = f"""
                font-size: {font_size - 1}px;
                font-weight: 600;
                color: {'white' if is_active else '#7F8C8D'};
                background: transparent;
            """
            tab_widget.text_label.setStyleSheet(text_style)

    def _apply_mobile_tab_style(self):
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        stylesheet = f"""
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
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                margin-right: 4px;
                margin-top: 4px;
                margin-bottom: 2px;
                font-weight: 600;
                font-size: 11px;
                min-width: 160px;
                min-height: 32px;
            }}

            QTabBar::tab:first {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 {primary_color}, stop:1 {secondary_color});
                color: white;
                margin-left: 8px;
            }}

            QTabBar::tab:disabled {{
                background: #F5F5F5;
                color: #BDC3C7;
            }}
        """

        self.tabs.setStyleSheet(stylesheet)

    def _apply_tablet_tab_style(self):
        """
        Style pour tablette avec onglets moyens.
        """
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        stylesheet = f"""
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
                border: none;
                border-radius: 5px;
                padding: 9px 18px;
                margin-right: 6px;
                margin-top: 6px;
                margin-bottom: 3px;
                font-weight: 600;
                font-size: 12px;
                min-width: 200px;
                min-height: 36px;
            }}

            QTabBar::tab:first {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 {primary_color}, stop:1 {secondary_color});
                color: white;
                margin-left: 12px;
            }}

            QTabBar::tab:disabled {{
                background: #F5F5F5;
                color: #BDC3C7;
            }}
        """

        self.tabs.setStyleSheet(stylesheet)

    def _add_responsive_animations(self):
        """
        Ajoute des animations fluides lors des transitions responsive.
        """
        # Animation de transition pour les onglets
        self.tab_animation = QtCore.QPropertyAnimation(self.tabs, b"geometry")
        self.tab_animation.setDuration(300)
        self.tab_animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

    def _get_optimal_sizes_for_screen(self):
        """
        Calcule les tailles optimales selon la résolution d'écran.

        Returns:
            dict: Dictionnaire avec les tailles optimales
        """
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        screen_width = screen_size.width()

        if screen_width < 1366:
            return {
                'tab_width': 220,
                'circle_size': 28,
                'font_size': 12,
                'padding': '8px 16px',
                'margin': 6
            }
        elif screen_width < 1920:
            return {
                'tab_width': 260,
                'circle_size': 32,
                'font_size': 13,
                'padding': '10px 24px',
                'margin': 8
            }
        else:
            # 4K et plus
            return {
                'tab_width': 300,
                'circle_size': 36,
                'font_size': 14,
                'padding': '12px 28px',
                'margin': 10
            }

    def mousePressEvent(self, event):
        print(f"DEBUG: Clic dans ProjectConfigOnlyWidget à {event.pos()}")
        super().mousePressEvent(event)

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(PlatformConfigStyle.SPACING)
        main_layout.setContentsMargins(
            PlatformConfigStyle.MARGIN,
            PlatformConfigStyle.MARGIN,
            PlatformConfigStyle.MARGIN,
            PlatformConfigStyle.MARGIN,
        )
    
        # Titre principal / Main title
        title_label = QtWidgets.QLabel(tr("project_config_only.main_title"))
        title_label.setStyleSheet(PlatformConfigStyle.get_title_style())
        main_layout.addWidget(title_label)
    
        # Onglets avec style personnalisé / Tabs with custom style
        self.tabs = QtWidgets.QTabWidget()
        self._apply_custom_tab_style()
        
        # Onglet ProjectConfigWidget / ProjectConfigWidget Tab
        self.project_config_widget_instance = ProjectConfigWidget(
            config_provider=self.config_provider, conductor=self.conductor, parent=self
        )
    
        self.project_config_widget_instance.project_selected_signal = self._on_project_selection_changed
        
        # Créer un widget personnalisé pour l'onglet Config / Create custom widget for Config tab
        config_tab_widget = self._create_tab_label(
            tr("project_config_only.tab_config_number"), 
            tr("project_config_only.tab_config_label"), 
            True
        )
        tab_index_0 = self.tabs.addTab(self.project_config_widget_instance, "")
        self.tabs.tabBar().setTabButton(tab_index_0, QtWidgets.QTabBar.LeftSide, config_tab_widget)
    
        # Onglet RelationImportWidget / RelationImportWidget Tab
        self.relation_import_widget_instance = RelationImportWidget(
            config_provider=self.config_provider, conductor=self.conductor, parent=self
        )
        
        relations_tab_widget = self._create_tab_label(
            tr("project_config_only.tab_relations_number"), 
            tr("project_config_only.tab_relations_label"), 
            False
        )
        tab_index_1 = self.tabs.addTab(self.relation_import_widget_instance, "")
        self.tabs.tabBar().setTabButton(tab_index_1, QtWidgets.QTabBar.LeftSide, relations_tab_widget)
    
        self.tabs.setTabEnabled(1, False)
        self.tabs.tabBar().setVisible(True)
    
        self.config_tab_widget = config_tab_widget
        self.relations_tab_widget = relations_tab_widget
    
        self.tabs.currentChanged.connect(self._on_tab_changed)
    
        main_layout.addWidget(self.tabs)
    
        self.setLayout(main_layout)
        self._init_responsive_ui()
        self._add_maximize_button()
        self._add_responsive_animations()

    def _on_tab_changed(self, index):
        """Gère le changement d'onglet et met à jour l'état visuel."""
        print(f"DEBUG: Changement d'onglet vers index {index}")
    
        has_project = bool(
            self.project_config_widget_instance and
            self.project_config_widget_instance.current_project_name and 
            self.project_config_widget_instance.current_project_profile_data
        )
    
        # ✅ Tab 1 Config widgets TOUJOURS actifs
        self._update_tab_style(self.config_tab_widget, True)
    
        if index == 0:
            # Sur Tab 1 Config : Tab 1 dégradé, Tab 2 grisé
            self._update_tabs_stylesheet(tab1_active=True, tab2_active=False)
            self._update_tab_style(self.relations_tab_widget, False)
        elif index == 1:
            # Sur Tab 2 Relations : Tab 1 ET Tab 2 avec dégradé
            self._update_tabs_stylesheet(tab1_active=True, tab2_active=has_project)
            self._update_tab_style(self.relations_tab_widget, has_project)

    def _force_tab1_active_style(self):
        """Force le Tab 1 à toujours avoir le style actif (dégradé)."""
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        # Forcer le style du Tab 1 avec le dégradé
        tab_bar = self.tabs.tabBar()
        for i in range(tab_bar.count()):
            if i == 0:  # Tab 1 Config
                tab_bar.setTabTextColor(i, QtCore.Qt.white)
                # Appliquer un style spécifique pour le Tab 1
                existing_style = self.tabs.styleSheet()
                if "QTabBar::tab:first" not in existing_style or "stop:0" not in existing_style.split("QTabBar::tab:first")[1].split("}")[0]:
                    self.tabs.setStyleSheet(existing_style + f"""
                        QTabBar::tab:first {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                         stop:0 {primary_color}, stop:1 {secondary_color}) !important;
                            color: white !important;
                        }}
                    """)

    def _create_tab_label(self, number, text, is_active):
        """Crée un widget d'onglet personnalisé avec cercle numéroté et texte centré."""
        container = QtWidgets.QWidget()
        container.setFixedWidth(260)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        # Cercle numéroté
        circle = QtWidgets.QLabel(number)
        circle.setFixedSize(32, 32)
        circle.setAlignment(QtCore.Qt.AlignCenter)

        # ✅ CORRIGÉ: Même style pour tous les onglets inactifs
        if is_active:
            circle.setStyleSheet("""
                QLabel {
                    background-color: #2C3E50;
                    color: white;
                    border-radius: 16px;
                    font-size: 15px;
                    font-weight: 600;
                    border: 2px solid #2C3E50;
                }
            """)
        else:
            circle.setStyleSheet("""
                QLabel {
                    background-color: #E0E0E0;
                    color: #7F8C8D;
                    border-radius: 16px;
                    font-size: 15px;
                    font-weight: 600;
                    border: 2px solid #BDC3C7;
                }
            """)

        # Texte du menu
        text_label = QtWidgets.QLabel(text)
        text_label.setAlignment(QtCore.Qt.AlignCenter)

        # ✅ CORRIGÉ: Couleur grise pour tous les onglets inactifs
        text_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {'white' if is_active else '#7F8C8D'};
            background: transparent;
        """)

        # Centrage parfait horizontalement
        layout.addStretch()
        layout.addWidget(circle, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(text_label, alignment=QtCore.Qt.AlignCenter)
        layout.addStretch()

        container.setLayout(layout)
        container.circle_label = circle
        container.text_label = text_label
        container.is_active = is_active
        return container

    def _update_tab_style(self, tab_widget, is_active):
        """Met à jour le style d'un onglet selon son état actif/inactif."""
        if not tab_widget:
            return

        if is_active:
            # 🟥 Style ACTIF (blanc sur fond sombre)
            tab_widget.circle_label.setStyleSheet("""
                QLabel {
                    background-color: #2C3E50;
                    color: white;
                    border-radius: 16px;
                    font-size: 15px;
                    font-weight: 600;
                    border: 2px solid #2C3E50;
                }
            """)
            tab_widget.text_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 600;
                color: white;
                background: transparent;
                padding: 0px;
                margin-left: 5px;
            """)

        else:
            # 🟦 Style INACTIF (gris pour TOUS les onglets non actifs)
            tab_widget.circle_label.setStyleSheet("""
                QLabel {
                    background-color: #E0E0E0;
                    color: #7F8C8D;
                    border-radius: 16px;
                    font-size: 15px;
                    font-weight: 600;
                    border: 2px solid #BDC3C7;
                }
            """)
            tab_widget.text_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 600;
                color: #7F8C8D;
                background: transparent;
                padding: 0px;
                margin-left: 5px;
            """)

    def _apply_custom_tab_style(self):
        """Applique un style personnalisé avec dégradé aux onglets."""
        # Récupérer les couleurs du thème
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        # ✅ Style de base sans les états selected
        base_style = f"""
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
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                margin-right: 8px;
                margin-top: 8px;
                margin-bottom: 4px;
                font-weight: 600;
                font-size: 13px;
                min-width: 220px;
                min-height: 40px;
            }}

            QTabBar::tab:disabled {{
                background: #F5F5F5;
                color: #BDC3C7;
            }}
        """

        self.tabs.setStyleSheet(base_style)
        self.tabs.tabBar().setLayoutDirection(QtCore.Qt.LeftToRight)

        # Stocker les couleurs pour usage ultérieur
        self.primary_color = primary_color
        self.secondary_color = secondary_color

    def _update_tabs_stylesheet(self, tab1_active=True, tab2_active=False):
        """Met à jour dynamiquement le stylesheet des onglets."""
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        # Styles pour Tab 1 (toujours actif)
        tab1_bg = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_color}, stop:1 {secondary_color})"
        tab1_color = "white"

        # Styles pour Tab 2 (actif ou inactif)
        if tab2_active:
            tab2_bg = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_color}, stop:1 {secondary_color})"
            tab2_color = "white"
        else:
            tab2_bg = "#F5F5F5"
            tab2_color = "#BDC3C7"

        stylesheet = f"""
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
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                margin-right: 8px;
                margin-top: 8px;
                margin-bottom: 4px;
                font-weight: 600;
                font-size: 13px;
                min-width: 220px;
                min-height: 40px;
            }}

            QTabBar::tab:first {{
                background: {tab1_bg};
                color: {tab1_color};
                margin-left: 15px;
            }}

            QTabBar::tab:last {{
                background: {tab2_bg};
                color: {tab2_color};
            }}

            QTabBar::tab:disabled {{
                background: #F5F5F5;
                color: #BDC3C7;
            }}
        """

        self.tabs.setStyleSheet(stylesheet)

    def _set_tab_background(self, tab_index, active):
        """Applique directement le style de fond à un onglet spécifique."""
        try:
            from ui.styles.theme import Theme
            primary_color = Theme.PRIMARY_COLOR
            secondary_color = Theme.SECONDARY_COLOR
        except:
            primary_color = "#A23B2D"
            secondary_color = "#8B2F22"

        tab_bar = self.tabs.tabBar()

        if active:
            # Dégradé actif
            style = f"""
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 {primary_color}, stop:1 {secondary_color});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 13px;
            """
        else:
            # Fond gris inactif
            style = """
                background: #F5F5F5;
                color: #BDC3C7;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 13px;
            """

        # Appliquer le style directement au bouton de l'onglet
        tab_button = tab_bar.tabButton(tab_index, QtWidgets.QTabBar.LeftSide)
        if tab_button and hasattr(tab_button, 'parent'):
            # Forcer le style sur le tab lui-même via une feuille de style inline
            tab_bar.setTabTextColor(tab_index, QtCore.Qt.white if active else QtCore.Qt.gray)

    def _maintain_config_active(self):
        """Force le style actif du menu Configuration en permanence."""
        if hasattr(self, 'config_tab_widget') and self.config_tab_widget:
            self._update_tab_style(self.config_tab_widget, True)

    def _on_project_selection_changed(self, has_project):
        """Gère le changement d'état de sélection d'un projet."""
        print(f"DEBUG: Projet sélectionné = {has_project}")

        self.tabs.setTabEnabled(1, has_project)

        self._update_tab_style(self.config_tab_widget, True)

        current_tab = self.tabs.currentIndex()

        if current_tab == 0:
            # Sur Config: Relations inactif
            self._update_tab_style(self.relations_tab_widget, False)
        elif current_tab == 1 and has_project:
            # Sur Relations: Relations actif
            self._update_tab_style(self.relations_tab_widget, True)

        # Émettre le signal
        self.project_selected.emit(has_project)
        
    def showEvent(self, event):
        """Gère l'affichage initial du widget."""
        super().showEvent(event)

        if hasattr(self, 'project_config_widget_instance') and self.project_config_widget_instance:
            has_project = bool(
                self.project_config_widget_instance.current_project_name and 
                self.project_config_widget_instance.current_project_profile_data
            )

            if has_project:
                print(f"DEBUG: Projet existant détecté au démarrage: {self.project_config_widget_instance.current_project_name}")
                self.tabs.setTabEnabled(1, True)
            else:
                self.tabs.setTabEnabled(1, False)

            # ✅ Configuration TOUJOURS actif
            self._update_tab_style(self.config_tab_widget, True)

            # ✅ Mettre à jour Relations selon l'onglet actuel
            current_tab = self.tabs.currentIndex()
            if current_tab == 0:
                # Sur Config au démarrage
                self._update_tab_style(self.relations_tab_widget, False)
            elif current_tab == 1 and has_project:
                # Sur Relations au démarrage
                self._update_tab_style(self.relations_tab_widget, True)

    def _force_enable_all_widgets(self):
        """Force l'activation de tous les widgets enfants."""
        if self.project_config_widget_instance:
            self.project_config_widget_instance.setEnabled(True)
            print("DEBUG: ProjectConfigWidget instance activée")
            for child in self.project_config_widget_instance.findChildren(
                QtWidgets.QWidget
            ):
                child.setEnabled(True)

        if self.relation_import_widget_instance:
            self.relation_import_widget_instance.setEnabled(True)
            print("DEBUG: RelationImportWidget instance activée")
            for child in self.relation_import_widget_instance.findChildren(
                QtWidgets.QWidget
            ):
                child.setEnabled(True)

        self.raise_()
        self.tabs.raise_()

    def refresh(self):
        """Rafraîchit l'état du widget."""
        print("ProjectConfigOnlyWidget: Refresh appelé.")

        if self.project_config_widget_instance and hasattr(
            self.project_config_widget_instance, "refresh"
        ):
            self.project_config_widget_instance.refresh()

        if self.relation_import_widget_instance and hasattr(
            self.relation_import_widget_instance, "refresh"
        ):
            self.relation_import_widget_instance.refresh()

        self._force_enable_all_widgets()

        self._check_project_state()

        current_tab = self.tabs.currentIndex()
        self._on_tab_changed(current_tab)

    def _check_project_state(self):
        """Vérifie et synchronise l'état du projet avec l'indicateur."""
        if not self.project_config_widget_instance:
            return

        has_project = bool(
            self.project_config_widget_instance.current_project_name and 
            self.project_config_widget_instance.current_project_profile_data
        )

        print(f"DEBUG: État projet au refresh = {has_project}")

        self.tabs.setTabEnabled(1, has_project)

        self._update_tab_style(self.config_tab_widget, True)

        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self._update_tab_style(self.relations_tab_widget, False)
        elif current_tab == 1 and has_project:
            self._update_tab_style(self.relations_tab_widget, True)