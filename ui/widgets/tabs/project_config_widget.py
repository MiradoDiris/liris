import copy
import os
import sys
import time
import qtawesome as qta
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from PyQt5 import QtWidgets, QtCore, QtGui
import uuid
from datetime import datetime
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QListWidgetItem, QHBoxLayout, QLabel, QPushButton, QInputDialog, QListWidget
from collections import defaultdict
from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.code_elements_popup import CodeElementsPopup
from utils.progress_dialog import ModernProgressDialog
from utils.multi_language_parser import (
    MultiLanguageDependencyParser, 
    ProjectStructureScanner,
    normalize_node_name,
)
from ui.widgets.tabs.relations_graph_widget import RelationsGraphWidget
from ui.widgets.tabs.add_editItem_dialog import AddEditItemDialog
from ui.widgets.tabs.relations_config import RelationsConfig
from utils.project_storage_manager import ProjectStorageManager
from utils.dgraph_project_manager import DgraphProjectManager
from ui.widgets.dialogs.code_dialogs import CodeDialogs
from utils.complete_call_resolver import CompleteCallResolver
from utils.resource_path import (
    get_database_path,
    is_frozen
)

def log_initialization_info():
    """Log les informations d'initialisation pour le débogage"""
    logger.info("=" * 60)
    logger.info("ProjectConfigWidget - Initialisation")
    logger.info("=" * 60)
    logger.info(f"Mode frozen: {is_frozen()}")
    logger.info(f"sys.executable: {sys.executable}")
    logger.info(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    logger.info(f"Database path: {get_database_path()}")
    logger.info("=" * 60)

class BackButton(QtWidgets.QPushButton):
    """
    🎨 Bouton retour personnalisé avec rendu garanti (VERSION COMPACTE)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)  # ✅ Taille réduite de 40x32 → 28x28
        self.setToolTip("Retour au niveau précédent")
        self.setCursor(Qt.PointingHandCursor)
        
        # Style direct
        self.setStyleSheet("""
            BackButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            BackButton:hover {
                background-color: #e5f3ff;
                border-color: #0078d4;
            }
            BackButton:pressed {
                background-color: #cce8ff;
            }
            BackButton:disabled {
                background-color: #f3f3f3;
                color: #cccccc;
            }
        """)
    
    def paintEvent(self, event):
        """Dessine la flèche directement avec QPainter"""
        super().paintEvent(event)
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Définir la couleur selon l'état
        if not self.isEnabled():
            painter.setPen(QtGui.QPen(QtGui.QColor("#cccccc"), 2.5))
        elif self.underMouse():
            painter.setPen(QtGui.QPen(QtGui.QColor("#0078d4"), 2.5))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor("#2c3e50"), 2.5))
        
        # Dessiner la flèche (chevron gauche) - AJUSTÉE POUR TAILLE 28x28
        path = QtGui.QPainterPath()
        
        # Centre du bouton
        cx = self.width() / 2
        cy = self.height() / 2
        
        # Taille de la flèche réduite
        arrow_size = 6  # ✅ Réduit de 8 → 6
        
        # Dessiner le chevron : >
        path.moveTo(cx + 2, cy - arrow_size)  # Haut
        path.lineTo(cx - 2, cy)                # Milieu
        path.lineTo(cx + 2, cy + arrow_size)  # Bas
        
        painter.drawPath(path)
        painter.end()

class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.conductor = conductor
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.db_path = os.path.join("data", "liris.db")
        self.project_storage_manager = ProjectStorageManager(
            parent_widget=self,
            db_path=self.db_path,
            dgraph_connector=self.dgraph_connector
        )

        log_initialization_info()
        
        self.config_provider = config_provider
        self.dgraph_manager = DgraphProjectManager(self.dgraph_connector)
        self.project_storage_manager._init_sqlite_db()

        self.local_to_dgraph = {}
        self.dgraph_to_local = {}

        self.dependency_parser = MultiLanguageDependencyParser()
        self.project_scanner = ProjectStructureScanner(self.dependency_parser)
        self.call_resolver = None
        

        self.project_profiles = {}

        self.structure_scanner = self.project_scanner
        
        self.parsed_relations_cache = {}
        self.file_content_cache = {}

        
        self.current_project_name = None
        self.current_project_profile_data = None

        self.current_cluster_index = -1
        self.current_cluster_data = None

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None

        self.current_level1_label_index = -1
        self.current_level1_is_file = False
        self.current_level1_filename = None

        self.current_level2_label_index = -1
        self.current_level2_is_file = False
        self.current_level2_filename = None

        # Pour les relations
        self.pending_relations = defaultdict(list)
        self.label_uid_to_info = {}
        self.name_to_uid = {}
        self.current_selected_label_uid = None
        self.child_navigation_stack = []

        self.current_child_parent = None

        self.global_relations_config = RelationsConfig(self, "global")
        self.relations_graph = RelationsGraphWidget(self)  # Nouveau widget graphe
        self.code_dialogs = CodeDialogs(self)

        self.setMinimumSize(1400, 900)

        self._init_ui()
        self._setup_child_list_connections()
        self._setup_minimum_window_size()
        self._init_responsive_design()
        self._optimize_for_high_dpi()
        self._enable_scroll_areas_for_small_screens()

        try:
            if self.dgraph_connector.client:
                self.dgraph_manager._load_project_profiles()
                schema = self.dgraph_connector.get_current_schema()

                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse...")
 
            self.project_storage_manager._load_projects_from_sqlite()
            
            # ← NOUVELLE LIGNE :
            #self._update_project_combo()
            logger.debug(f"Initialisation : {len(self.project_profiles)} projets affichés")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._delayed_combo_update)

    def _init_responsive_design(self):
        # Installer le filtre d'événements
        self.installEventFilter(self)

        # État initial
        self.last_size = self.size()
        self.current_scale = 1.0

        # Ajuster immédiatement
        QtCore.QTimer.singleShot(200, self._adjust_layout_for_resolution)

    def _delayed_combo_update(self, force_reload: bool = False):
        """
        ✅ VERSION AVEC DIAGNOSTIC : Permet de forcer le rechargement si nécessaire

        Args:
            force_reload: Si True, recharge depuis les sources mĂȘme si des donnĂ©es existent
        """
        try:
            logger.info("🔄 Démarrage mise à jour différée du combo...")
            logger.info(f"📊 État initial: {len(self.project_profiles)} projet(s) en mémoire")

            # ✅ DIAGNOSTIC : Vérifier contenu AVANT reload
            if self.project_profiles:
                logger.info("📋 Projets existants AVANT reload:")
                for name, profile in self.project_profiles.items():
                    clusters = profile.get('turing_ontology', {}).get('clusters_detailed', [])
                    logger.info(f"   • {name}: {len(clusters)} clusters")

            # ✅ Déterminer si rechargement nécessaire
            needs_reload = force_reload or len(self.project_profiles) == 0

            if needs_reload:
                reload_reason = "forcé" if force_reload else "profils vides"
                logger.info(f"📩 Rechargement ({reload_reason})...")

                # Sauvegarder les projets existants pour merge intelligent
                existing_projects = set(self.project_profiles.keys())
                loaded_count = 0

                # 1. Dgraph
                if self.dgraph_connector.client:
                    try:
                        logger.info("   📡 Chargement depuis Dgraph...")
                        dgraph_profiles = self.dgraph_manager._load_project_profiles()

                        if dgraph_profiles:
                            for name, profile in dgraph_profiles.items():
                                clusters = profile.get('turing_ontology', {}).get('clusters_detailed', [])

                                # ✅ DIAGNOSTIC : Vérifier contenu
                                logger.info(f"      ✅ Dgraph: '{name}' = {len(clusters)} clusters")

                                # ✅ Merge : ajouter ou mettre à jour
                                if force_reload or name not in self.project_profiles:
                                    self.project_profiles[name] = profile
                                    loaded_count += 1
                                else:
                                    logger.debug(f"      ⭐ '{name}' déjà en mémoire, skip")

                            logger.info(f"   ✅ Dgraph: {len(dgraph_profiles)} profil(s) trouvé(s), {loaded_count} ajouté(s)")
                        else:
                            logger.warning("   ⚠ Dgraph: Aucun profil récupéré")
                    except Exception as e:
                        logger.error(f"   ❌ Erreur Dgraph: {e}")

                # 2. SQLite
                try:
                    logger.info("   💟 Chargement depuis SQLite...")
                    before_count = len(self.project_profiles)
                    sqlite_loaded = self.project_storage_manager._load_projects_from_sqlite()
                    after_count = len(self.project_profiles)

                    if sqlite_loaded:
                        added = after_count - before_count
                        logger.info(f"   ✅ SQLite: {added} profil(s) ajouté(s)")
                    else:
                        logger.warning("   ⚠ SQLite: Aucun profil récupéré")
                except Exception as e:
                    logger.error(f"   ❌ Erreur SQLite: {e}")

                # Afficher les nouveaux projets
                new_projects = set(self.project_profiles.keys()) - existing_projects
                if new_projects:
                    logger.info(f"   📄 Nouveaux projets: {', '.join(sorted(new_projects))}")
            else:
                logger.info("✓ Profils déjà en mémoire, pas de rechargement")

            # 3. Statistiques finales
            total_projects = len(self.project_profiles)
            logger.info(f"📊 Total final: {total_projects} projet(s)")

            if total_projects > 0:
                logger.info("📋 Projets en mémoire APRÈs reload:")
                for name in sorted(self.project_profiles.keys()):
                    clusters = self.project_profiles[name].get('turing_ontology', {}).get('clusters_detailed', [])
                    total_labels = sum(len(c.get('root_labels', [])) for c in clusters)
                    logger.info(f"   • {name}: {len(clusters)} clusters, {total_labels} labels")

            # 4. Mettre à jour le combo
            self._update_project_combo()
            logger.info(f"✅ Combo mis à jour avec {total_projects} projet(s)")

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour différée : {e}")
            import traceback
            traceback.print_exc()

    def eventFilter(self, obj, event):
        """
        Filtre les événements de redimensionnement avec seuil plus petit.
        """
        if obj == self and event.type() == QtCore.QEvent.Resize:
            new_size = event.size()
            # Seuil réduit à 100px pour une meilleure réactivité
            if (abs(new_size.width() - self.last_size.width()) > 100 or 
                abs(new_size.height() - self.last_size.height()) > 100):
                self.last_size = new_size
                # Utiliser un timer pour éviter trop d'appels pendant le resize
                if not hasattr(self, '_resize_timer'):
                    self._resize_timer = QtCore.QTimer()
                    self._resize_timer.setSingleShot(True)
                    self._resize_timer.timeout.connect(self._adjust_layout_for_resolution)
                self._resize_timer.start(150)  # Délai de 150ms

        return super().eventFilter(obj, event)
    
    def _adjust_layout_for_resolution(self):
        # Utiliser la taille réelle de la fenêtre au lieu de l'écran complet
        window_width = self.width()
        window_height = self.height()

        # Déterminer le facteur d'échelle basé sur la taille de la fenêtre
        if window_width >= 3840:  # 4K
            scale = 1.2
            layout_mode = "4K"
        elif window_width >= 2560:  # QHD
            scale = 1.1
            layout_mode = "QHD"
        elif window_width >= 1920:  # Full HD
            scale = 1.0
            layout_mode = "FullHD"
        elif window_width >= 1600:  # HD+
            scale = 0.95
            layout_mode = "HD+"
        elif window_width >= 1366:  # HD
            scale = 0.85
            layout_mode = "HD"
        elif window_width >= 1024:  # Tablette
            scale = 0.75
            layout_mode = "Tablette"
        else:  # Très petit
            scale = 0.65
            layout_mode = "Mobile"

        self.current_scale = scale

        print(f"🖥️ Mode {layout_mode} - Scale: {scale} (Largeur: {window_width}px)")

        # Appliquer les ajustements
        self._apply_responsive_scale(scale, layout_mode)

    def _apply_responsive_scale(self, scale, mode):
        # 1. Ajuster les listes
        self._adjust_list_widgets_size(scale)

        # 2. Ajuster les colonnes
        self._adjust_columns_layout(mode)

        # 3. Ajuster les boutons
        self._adjust_buttons_size(scale)

        # 4. Ajuster les polices
        self._adjust_fonts(scale)

        # 5. Ajuster les spacings
        self._adjust_spacings(scale)

    def _adjust_list_widgets_size(self, scale):
        # Hauteurs minimales et maximales plus flexibles
        base_heights = {
            'cluster': (60, 220),
            'root': (150, 350), 
            'level1': (150, 350),   
            'child': (150, 350) 
        }

        # Ajuster en fonction de la largeur de fenêtre pour éviter les coupures
        window_height = self.height()
        max_list_height = max(100, int(window_height * 0.15))  # Max 15% de la hauteur

        # Cluster list
        if hasattr(self, 'cluster_list_widget'):
            min_h, max_h = base_heights['cluster']
            self.cluster_list_widget.setMinimumHeight(int(min_h * scale))
            self.cluster_list_widget.setMaximumHeight(min(int(max_h * scale), max_list_height))

        # Root list
        if hasattr(self, 'root_list_widget'):
            min_h, max_h = base_heights['root']
            self.root_list_widget.setMinimumHeight(int(min_h * scale))
            self.root_list_widget.setMaximumHeight(min(int(max_h * scale), max_list_height))

        # Level1 list
        if hasattr(self, 'level1_list_widget'):
            min_h, max_h = base_heights['level1']
            self.level1_list_widget.setMinimumHeight(int(min_h * scale))
            self.level1_list_widget.setMaximumHeight(min(int(max_h * scale), max_list_height))

        # Child list
        if hasattr(self, 'child_list_widget'):
            min_h, max_h = base_heights['child']
            self.child_list_widget.setMinimumHeight(int(min_h * scale))
            self.child_list_widget.setMaximumHeight(min(int(max_h * scale), max_list_height))

        # Details text - hauteur adaptative
        if hasattr(self, 'details_text'):
            details_max = min(400, int(window_height * 0.25))
            self.details_text.setMaximumHeight(int(details_max * scale))

    def _adjust_columns_layout(self, mode):
        # Définir les ratios de colonnes selon le mode avec scroll si nécessaire
        if mode in ["4K", "QHD", "FullHD"]:
            # Grands écrans : affichage normal
            ratios = [4, 4, 5]  # Gauche, Milieu, Droite
        elif mode in ["HD+", "HD"]:
            # Écrans moyens : réduire légèrement la colonne droite
            ratios = [4, 5, 4]
        elif mode == "Tablette":
            # Petits écrans : réduire les colonnes latérales
            ratios = [3, 5, 3]
        else:
            # Très petits écrans : privilégier la colonne centrale
            ratios = [2, 6, 3]

        # Activer le scroll pour les petits écrans
        if mode in ["Tablette", "Mobile"]:
            self._enable_scroll_areas_for_small_screens()

    def _adjust_buttons_size(self, scale):
        base_button_height = 32
        base_button_width = 120

        buttons = []

        # Collecter tous les boutons
        if hasattr(self, 'add_project_button'):
            buttons.append(self.add_project_button)
        if hasattr(self, 'delete_project_button'):
            buttons.append(self.delete_project_button)
        if hasattr(self, 'upload_local_button'):
            buttons.append(self.upload_local_button)
        if hasattr(self, 'browse_button'):
            buttons.append(self.browse_button)
        if hasattr(self, 'save_button'):
            buttons.append(self.save_button)
        if hasattr(self, 'export_profile_button'):
            buttons.append(self.export_profile_button)

        # Ajuster la taille
        for button in buttons:
            if button:
                button.setMinimumHeight(int(base_button_height * scale))
                if button.maximumWidth() < 16777215:  # Si une largeur max est définie
                    button.setMaximumWidth(int(base_button_width * scale))

    def _adjust_fonts(self, scale):
        base_font_size = 13
        scaled_font_size = max(10, int(base_font_size * scale))

        # Liste des widgets à ajuster
        widgets_to_adjust = []

        # Ajouter tous les QListWidget
        for attr_name in dir(self):
            if attr_name.endswith('_list_widget'):
                widget = getattr(self, attr_name, None)
                if isinstance(widget, QtWidgets.QListWidget):
                    widgets_to_adjust.append(widget)

        # Ajouter les champs de texte
        if hasattr(self, 'project_name_edit'):
            widgets_to_adjust.append(self.project_name_edit)
        if hasattr(self, 'project_description_edit'):
            widgets_to_adjust.append(self.project_description_edit)
        if hasattr(self, 'details_text'):
            widgets_to_adjust.append(self.details_text)

        # Appliquer la police
        for widget in widgets_to_adjust:
            if widget:
                font = widget.font()
                font.setPointSize(scaled_font_size)
                widget.setFont(font)

    def _adjust_spacings(self, scale):
        base_spacing = 8
        base_margin = 15

        scaled_spacing = int(base_spacing * scale)
        scaled_margin = int(base_margin * scale)

        # Ajuster le layout principal si accessible
        main_layout = self.layout()
        if main_layout:
            main_layout.setSpacing(scaled_spacing)
            main_layout.setContentsMargins(
                scaled_margin, 
                5,  # Top reste petit
                scaled_margin, 
                scaled_margin
            )

    def _enable_scroll_areas_for_small_screens(self):
        """Active les scrollbars pour les petits écrans"""
        if self.current_scale < 0.95:
            # Activer scroll horizontal et vertical pour la colonne du milieu
            if hasattr(self, 'middle_scroll'):
                self.middle_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
                self.middle_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

            # Forcer le word wrap et l'ellipsis pour les listes
            for list_widget in [self.cluster_list_widget, self.root_list_widget, 
                               self.level1_list_widget, self.child_list_widget]:
                if list_widget:
                    list_widget.setWordWrap(True)
                    list_widget.setTextElideMode(QtCore.Qt.ElideRight)

    def _adjust_combo_box_size(self, scale):
        if hasattr(self, 'project_combo'):
            base_min_width = 200
            base_max_width = 350

            self.project_combo.setMinimumWidth(int(base_min_width * scale))
            self.project_combo.setMaximumWidth(int(base_max_width * scale))

    def _optimize_for_high_dpi(self):
        screen = QtWidgets.QApplication.primaryScreen()
        dpi = screen.physicalDotsPerInch()

        # Si DPI > 150, c'est un écran haute résolution
        if dpi > 150:
            # Activer le rendu haute qualité
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

            # Ajuster le style des icônes pour qu'elles restent nettes
            if hasattr(self, 'cluster_list_widget'):
                self.cluster_list_widget.setIconSize(QtCore.QSize(20, 20))
            if hasattr(self, 'root_list_widget'):
                self.root_list_widget.setIconSize(QtCore.QSize(20, 20))

            print(f"🎨 Mode Haute Résolution activé (DPI: {dpi})")

    def _setup_minimum_window_size(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_width = screen.geometry().width()
        screen_height = screen.geometry().height()

        # Taille minimale plus flexible
        min_width = max(800, min(1400, int(screen_width * 0.6)))
        min_height = max(600, min(900, int(screen_height * 0.6)))

        self.setMinimumSize(min_width, min_height)

        print(f"📐 Taille minimale: {min_width}x{min_height}")

        # Permettre le redimensionnement libre
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )

    def _on_insert_dgraph_clicked(self):
        """
        ✅ CORRECTION: Prépare et lance l'insertion avec synchronisation correcte
        """
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné pour l'insertion.")
            logger.error("❌ Aucun projet sélectionné pour l'insertion.")
            return

        self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
        self.dgraph_manager.project_storage_manager = self.project_storage_manager
        self.dgraph_manager.project_profiles = self.project_profiles
        self.dgraph_manager.current_project_name = self.current_project_name
        self.dgraph_manager.label_uid_to_info = self.label_uid_to_info
        self.dgraph_manager.pending_relations = self.pending_relations 
        self.dgraph_manager.local_to_dgraph = self.local_to_dgraph 
        self.dgraph_manager.dgraph_to_local = self.dgraph_to_local

        logger.info(f"🔍 Insertion Dgraph demandée pour le projet : {self.current_project_name}")

        self.dgraph_manager._on_insert_dgraph(self)

    def showEvent(self, event):
        """Maximiser la fenêtre lors de l'affichage"""
        super().showEvent(event)
        if self.window():
            self.window().showMaximized()

    def _get_improved_list_style(self):
        return """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 8px 8px 32px;  /* Espace pour l'icône à gauche */
                border-radius: 3px;
                margin: 2px 0px;
                color: #000000;
                min-height: 24px;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            QListWidget::item:selected:hover {
                background-color: #d5d5d5;
                color: #000000;
            }
        """

    def _init_ui(self):
        # ==================== LAYOUT PRINCIPAL ====================
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(8)
        main_vertical_layout.setContentsMargins(15, 5, 15, 15)
    
        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)
    
        # Initialisation des structures de données
        self.label_uid_to_info = {}
        self.pending_relations = defaultdict(list)
        self.current_selected_label_uid = None
    
        # ==================== COLONNE DE GAUCHE ====================
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)
    
        # --- Groupe sélection projet ---
        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)
    
        # ComboBox projet
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.setMinimumWidth(200)
        self.project_combo.setMaximumWidth(350)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)
    
        # Bouton "Ajouter" / "Add"
        self.add_project_button = QtWidgets.QPushButton(tr("project_config.button_add"))
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)
    
        # Bouton "Supprimer" / "Delete"
        self.delete_project_button = QtWidgets.QPushButton(tr("project_config.button_delete"))
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)
    
        # Bouton "📂 Uploader" / "📂 Upload"
        self.upload_local_button = QtWidgets.QPushButton(tr("project_config.button_upload"))
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)
    
        project_selection_layout.addStretch()
        left_column_layout.addWidget(project_selection_group)
    
        # --- Groupe détails ---
        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    
        # Layout horizontal pour le nom du projet avec bouton Parcourir
        project_name_widget = QtWidgets.QWidget()
        project_name_layout = QtWidgets.QHBoxLayout(project_name_widget)
        project_name_layout.setContentsMargins(0, 0, 0, 0)
        project_name_layout.setSpacing(8)
    
        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setMinimumWidth(200)
        self.project_name_edit.setMaximumWidth(350)
        project_name_layout.addWidget(self.project_name_edit)
    
        # Bouton "Scanner les noeuds" / "Scan Nodes"
        self.browse_button = QtWidgets.QPushButton(tr("project_config.button_scan_nodes"))
        self.browse_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.browse_button.setMaximumWidth(120)
        if hasattr(self, '_on_browse_project'):
            self.browse_button.clicked.connect(self._on_browse_project)
        project_name_layout.addWidget(self.browse_button)
    
        project_name_layout.addStretch()
        details_form_layout.addRow("", project_name_widget)
    
        # Description du projet / Project Description
        self.project_description_edit = QtWidgets.QTextEdit()
        self.project_description_edit.setPlaceholderText(tr("project_config.description_placeholder"))
        self.project_description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.project_description_edit.setMaximumHeight(80)
        details_form_layout.addRow(tr("project_config.description_label"), self.project_description_edit)
    
        # --- Liste des clusters ---
        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)
    
        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(self._get_improved_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        self.cluster_list_widget.currentItemChanged.connect(self._on_cluster_selected)
        cluster_list_layout.addWidget(self.cluster_list_widget)
    
        # ✅ ESPACEMENT AVANT LES BOUTONS
        cluster_list_layout.addSpacing(8)
    
        # Boutons cluster
        cluster_buttons_layout = QtWidgets.QHBoxLayout()
        cluster_buttons_layout.setSpacing(5)
        cluster_buttons_layout.setContentsMargins(0, 0, 0, 0)
    
        self.add_cluster_button = QtWidgets.QPushButton(tr("project_config.button_add"))
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)
    
        self.edit_cluster_button = QtWidgets.QPushButton(tr("project_config.button_edit"))
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)
    
        self.remove_cluster_button = QtWidgets.QPushButton(tr("project_config.button_delete"))
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)
    
        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
        cluster_buttons_layout.addStretch()
        cluster_list_layout.addLayout(cluster_buttons_layout)
    
        details_form_layout.addRow(cluster_list_layout)
        left_column_layout.addWidget(details_group)
    
        # --- Groupe détails sélectionné / Selected Details Group ---
        details_selected_group = QtWidgets.QGroupBox(tr("project_config.selected_details_group"))
        details_selected_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_selected_layout = QtWidgets.QVBoxLayout(details_selected_group)
    
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.details_text.setMaximumHeight(400)
        details_selected_layout.addWidget(self.details_text)
        left_column_layout.addWidget(details_selected_group)
    
        left_column_layout.addStretch()
        top_columns_layout.addLayout(left_column_layout, 4)
    
        # ==================== COLONNE DU MILIEU: HIÉRARCHIE ====================
        middle_scroll = QtWidgets.QScrollArea()
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setStyleSheet("border: none;")
    
        middle_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(middle_content)
        hierarchy_layout.setSpacing(8)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)
    
        hierarchy_group = QtWidgets.QGroupBox(tr("project_config.hierarchy_group"))
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(8)
    
        # --- 1. Labels Racines / Root Labels ---
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(root_label_title)
    
        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(self._get_improved_list_style())
        self.root_list_widget.setMinimumHeight(150)
        self.root_list_widget.setMaximumHeight(350)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)
    
        # ✅ ESPACEMENT AVANT LES BOUTONS
        hierarchy_group_layout.addSpacing(8)
    
        # Boutons root
        root_buttons_layout = QtWidgets.QHBoxLayout()
        root_buttons_layout.setSpacing(5)
        root_buttons_layout.setContentsMargins(0, 0, 0, 0)
    
        self.add_root_button = QtWidgets.QPushButton(tr("project_config.button_add"))
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)
    
        self.edit_root_button = QtWidgets.QPushButton(tr("project_config.button_edit"))
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)
    
        self.remove_root_button = QtWidgets.QPushButton(tr("project_config.button_delete"))
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)
    
        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        root_buttons_layout.addStretch()
        hierarchy_group_layout.addLayout(root_buttons_layout)
    
        # ✅ ESPACEMENT APRÈS LES BOUTONS
        hierarchy_group_layout.addSpacing(12)
    
        # --- 2. Labels Niveau 1 / Level 1 Labels ---
        level1_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        level1_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(level1_label_title)
    
        self.level1_list_widget = QtWidgets.QListWidget()
        self.level1_list_widget.setStyleSheet(self._get_improved_list_style())
        self.level1_list_widget.setMinimumHeight(150)
        self.level1_list_widget.setMaximumHeight(350)
        self.level1_list_widget.currentItemChanged.connect(self._on_level1_label_selected)
        hierarchy_group_layout.addWidget(self.level1_list_widget)
    
        # ✅ ESPACEMENT AVANT LES BOUTONS
        hierarchy_group_layout.addSpacing(8)
    
        # Boutons level1
        level1_buttons_layout = QtWidgets.QHBoxLayout()
        level1_buttons_layout.setSpacing(5)
        level1_buttons_layout.setContentsMargins(0, 0, 0, 0)
    
        self.add_level1_button = QtWidgets.QPushButton(tr("project_config.button_add"))
        self.add_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_level1_button.clicked.connect(self._add_level1_label)
    
        self.edit_level1_button = QtWidgets.QPushButton(tr("project_config.button_edit"))
        self.edit_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_level1_button.clicked.connect(self._edit_level1_label)
    
        self.remove_level1_button = QtWidgets.QPushButton(tr("project_config.button_delete"))
        self.remove_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_level1_button.clicked.connect(self._remove_level1_label)
    
        level1_buttons_layout.addWidget(self.add_level1_button)
        level1_buttons_layout.addWidget(self.edit_level1_button)
        level1_buttons_layout.addWidget(self.remove_level1_button)
        level1_buttons_layout.addStretch()
        hierarchy_group_layout.addLayout(level1_buttons_layout)
    
        # ✅ ESPACEMENT APRÈS LES BOUTONS
        hierarchy_group_layout.addSpacing(12)
    
        # --- 3. Labels Enfants avec Bouton Retour / Child Labels with Back Button ---
        child_header_layout = self._create_back_button_section()
        hierarchy_group_layout.addLayout(child_header_layout)
    
        # Liste des enfants / Children list
        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(150)
        self.child_list_widget.setMaximumHeight(400)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)
    
        # ✅ ESPACEMENT AVANT LES BOUTONS
        hierarchy_group_layout.addSpacing(8)
    
        # Boutons child
        child_buttons_layout = QtWidgets.QHBoxLayout()
        child_buttons_layout.setSpacing(5)
        child_buttons_layout.setContentsMargins(0, 0, 0, 0)
    
        self.add_child_button = QtWidgets.QPushButton(tr("project_config.button_add"))
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)
    
        self.edit_child_button = QtWidgets.QPushButton(tr("project_config.button_edit"))
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)
    
        self.remove_child_button = QtWidgets.QPushButton(tr("project_config.button_delete"))
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)
    
        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)
        child_buttons_layout.addStretch()
        hierarchy_group_layout.addLayout(child_buttons_layout)
    
        hierarchy_layout.addWidget(hierarchy_group)
        hierarchy_layout.addStretch()  # ✅ IMPORTANT: Permet au contenu de ne pas s'étirer
        middle_scroll.setWidget(middle_content)
        top_columns_layout.addWidget(middle_scroll, 4)
    
        # ==================== COLONNE DE DROITE: RELATIONS ====================
        right_column_layout = QtWidgets.QVBoxLayout()
    
        # Configuration des Relations en haut / Relations Configuration (top)
        relations_group = QtWidgets.QGroupBox(tr("project_config.relations_config_group"))
        relations_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        relations_layout.addWidget(self.global_relations_config)
        right_column_layout.addWidget(relations_group)
    
        # Section graphe des relations / Relations Graph Section
        graph_group = QtWidgets.QGroupBox(tr("project_config.relations_graph_group"))
        graph_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        graph_layout = QtWidgets.QVBoxLayout(graph_group)
        graph_layout.addWidget(self.relations_graph)
        graph_group.setMinimumHeight(350)
        right_column_layout.addWidget(graph_group)
    
        # Boutons de sauvegarde/export/insert en bas / Save/Export/Insert buttons (bottom)
        save_layout = QtWidgets.QHBoxLayout()
    
        self.save_button = QtWidgets.QPushButton(tr("project_config.button_save_profile"))
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False)
        self.save_button.setMaximumWidth(120)
        save_layout.addWidget(self.save_button)
    
        self.export_profile_button = QtWidgets.QPushButton(tr("project_config.button_export_profile"))
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(False)
        self.export_profile_button.setMaximumWidth(120)
        save_layout.addWidget(self.export_profile_button)
    
        save_layout.addStretch()
    
        right_column_layout.addLayout(save_layout)
        right_column_layout.addStretch()
        top_columns_layout.addLayout(right_column_layout, 5)
    
        self.level1_list_widget.itemDoubleClicked.connect(self._on_double_click_item)
        self.child_list_widget.itemDoubleClicked.connect(self._on_double_click_item)

    def _create_back_button_section(self):
        """Crée la section avec bouton retour et titre des labels enfants"""
        child_header_layout = QtWidgets.QHBoxLayout()
        child_header_layout.setSpacing(15)
        child_header_layout.setContentsMargins(0, 0, 0, 5)

        # ✅ BOUTON RETOUR AVEC FALLBACK ROBUSTE
        self.back_navigation_btn = QtWidgets.QPushButton()
        self.back_navigation_btn.setToolTip("Retour au niveau précédent")

        # 🔹 TENTATIVE 1 : Charger depuis resources/icons
        icon_loaded = False
        icon_path = self._ensure_icon_exists()

        if os.path.exists(icon_path):
            try:
                icon = QtGui.QIcon(icon_path)
                if not icon.isNull():
                    pixmap = icon.pixmap(20, 20)
                    if not pixmap.isNull():
                        self.back_navigation_btn.setIcon(icon)
                        self.back_navigation_btn.setIconSize(QSize(20, 20))
                        icon_loaded = True
                        logger.debug(f"✅ Icône chargée depuis : {icon_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement icône : {e}")

        # 🔹 TENTATIVE 2 : Utiliser QStyle (icône système)
        if not icon_loaded:
            try:
                style = self.style()
                if style:
                    system_icon = style.standardIcon(QtWidgets.QStyle.SP_ArrowBack)
                    if not system_icon.isNull():
                        self.back_navigation_btn.setIcon(system_icon)
                        self.back_navigation_btn.setIconSize(QSize(20, 20))
                        icon_loaded = True
                        logger.debug("✅ Icône système chargée (SP_ArrowBack)")
            except Exception as e:
                logger.warning(f"⚠️ Erreur icône système : {e}")

        # 🔹 FALLBACK FINAL : Texte Unicode
        if not icon_loaded:
            self.back_navigation_btn.setText("←")
            logger.info("ℹ️ Fallback texte Unicode activé")

        # ✅ STYLE UNIFIÉ (LARGEUR RÉDUITE)
        self.back_navigation_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 6px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #e5f3ff;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #cce8ff;
                border-color: #005499;
            }
            QPushButton:disabled {
                background-color: #f3f3f3;
                border-color: #d9d9d9;
                color: #cccccc;
            }
        """)

        self.back_navigation_btn.clicked.connect(self._on_child_navigation_back)
        self.back_navigation_btn.setEnabled(False)
        self.back_navigation_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        child_header_layout.addWidget(self.back_navigation_btn)

        # Titre "Labels enfants" avec numéro de niveau centré
        self.child_label_title = QtWidgets.QLabel("Labels enfants")
        self.child_label_title.setStyleSheet("""
            font-weight: bold; 
            color: #2c3e50; 
            font-size: 12px;
            padding: 4px 8px;
        """)
        self.child_label_title.setAlignment(Qt.AlignCenter)
        child_header_layout.addWidget(self.child_label_title)

        # Label indicateur de profondeur (chemin)
        self.depth_indicator_label = QtWidgets.QLabel("")
        self.depth_indicator_label.setStyleSheet("""
            color: #7f8c8d; 
            font-size: 10px; 
            font-style: italic;
            padding: 4px 8px;
        """)
        self.depth_indicator_label.setAlignment(Qt.AlignCenter)
        child_header_layout.addWidget(self.depth_indicator_label)

        child_header_layout.addStretch()
        return child_header_layout

    def _ensure_icon_exists(self):
        """
        ✅ VERSION AMÉLIORÉE : Crée l'icône SVG optimisée
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(base_dir, '..', 'resources', 'icons')
        icons_dir = os.path.normpath(icons_dir)

        # Créer le dossier si nécessaire
        try:
            os.makedirs(icons_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ Impossible de créer le dossier icons : {e}")
            return ""

        icon_path = os.path.join(icons_dir, 'retour.svg')

        # Créer l'icône si elle n'existe pas
        if not os.path.exists(icon_path):
            # ✅ SVG OPTIMISÉ avec viewBox correct
            svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Flèche gauche simple et visible -->
      <path d="M15 18L9 12L15 6" 
            stroke="#2c3e50" 
            stroke-width="2.5" 
            stroke-linecap="round" 
            stroke-linejoin="round"
            fill="none"/>
    </svg>'''
            try:
                with open(icon_path, 'w', encoding='utf-8') as f:
                    f.write(svg_content)
                logger.info(f"✅ Icône créée : {icon_path}")
            except Exception as e:
                logger.error(f"❌ Erreur création icône : {e}")
                return ""

        return icon_path

    def _update_child_navigation_ui(self):
        current_depth = len(self.child_navigation_stack)

        if current_depth == 0:
            level_text = "Labels enfants - Niveau 1"
        else:
            child_level = current_depth + 1
            level_text = f"Labels enfants - Niveau {child_level}"

        self.child_label_title.setText(level_text)

        self.back_navigation_btn.setEnabled(current_depth > 0)

        if current_depth > 0:
            path_parts = []
            for state in self.child_navigation_stack:
                parent = state.get('parent')
                if parent:
                    path_parts.append(parent.get('label', parent.get('name', '?')))

            if self.current_child_parent:
                path_parts.append(self.current_child_parent.get('label', self.current_child_parent.get('name', '?')))

            path_text = " > ".join(path_parts[-3:])
            if len(self.child_navigation_stack) > 3:
                path_text = "... > " + path_text

            self.depth_indicator_label.setText(f"📂 {path_text}")
        else:
            self.depth_indicator_label.setText("")

    def _get_file_content(self, file_path: str) -> str:
        """
        Récupère le contenu d'un fichier depuis la structure en mémoire ou le disque.
        """
        if not file_path:
            return ""

        # Essayer depuis current_root_data (pour les fichiers ouverts)
        if self.current_root_data:
            content = self.current_root_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Essayer depuis project_profile_data global
        if self.current_project_profile_data:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Fallback : lecture directe du disque
        return self._read_file_content(file_path)  # Méthode existante
    #Interface a ameliorer

    def _on_double_click_item(self, item):
        """
        Gère le double-clic sur un item de liste.
        - Pour classes/fonctions/variables : Affiche un snippet du fichier centré sur la ligne.
        - Pour fichiers/labels : Réutilise l'affichage existant (_on_double_click_label).
        """
        if not item:
            return

        item_type = item.data(Qt.UserRole + 1)
        if item_type in ['class', 'function', 'variable', 'method']:
            file_path = item.data(Qt.UserRole + 2)
            line_num = item.data(Qt.UserRole + 3) or 1

            content = self._get_file_content(file_path)
            if not content:
                QtWidgets.QMessageBox.warning(self, "Erreur", f"Impossible de charger le fichier {file_path}.")
                return

            # Extraire et afficher le snippet
            self.code_dialogs._show_code_snippet_dialog(file_path, content, item_type, line_num, item.text())

        elif item_type in ['file', 'root_file', 'level1_file']:
            # Fallback : affichage complet du fichier (comme existant)
            uid = item.data(Qt.UserRole)
            label = self._find_label_by_uid(uid)
            if label:
                self._on_double_click_label(item)
            else:
                content = self._get_file_content(file_path)
                if content:
                    self.code_dialogs._show_file_content_dialog(file_path, content, {'label': item.text()})

        else:
            self._on_double_click_label(item)

    def _update_project_combo(self):
        """
        CORRECTION: Mise à jour robuste avec gestion d'erreurs
        """
        try:
            logger.info(f"🔄 Mise à jour combo: {len(self.project_profiles)} projet(s)")

            if not hasattr(self, 'project_combo') or self.project_combo is None:
                logger.error("❌ project_combo n'existe pas ou est None!")
                return

            self.project_combo.blockSignals(True)
            current_text = self.project_combo.currentText()
            self.project_combo.clear()

            if not self.project_profiles:
                logger.warning("⚠️ Aucun projet à afficher")
                self.project_combo.addItem("(Aucun projet)")
                self.project_combo.blockSignals(False)
                return

            count = 0
            for name in sorted(self.project_profiles.keys()):
                self.project_combo.addItem(name)
                count += 1
                logger.debug(f"   ✅ Ajouté: {name}")

            self.project_combo.blockSignals(False)
            self.project_combo.update()
            self.project_combo.repaint()

            logger.info(f"✅ Combo mis à jour: {count} projet(s) affiché(s)")

            # Restaurer sélection précédente si possible
            if current_text and current_text != "(Aucun projet)":
                index = self.project_combo.findText(current_text)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                elif count > 0:
                    self.project_combo.setCurrentIndex(0)
                    self._on_project_selected(0)
            elif count > 0 and not self.current_project_name:
                self.project_combo.setCurrentIndex(0)
                self._on_project_selected(0)

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour combo: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_selected(self, index):
        """
        ✅ VERSION AMÉLIORÉE : Détection .exe + copie adaptative + diagnostic complet
        """
        start_time = time.time()
    
        if index < 0:
            logger.debug("Index < 0, sélection annulée")
            return
    
        project_name = self.project_combo.currentText()
        
        # ✅ DÉTECTION ENVIRONNEMENT
        is_frozen = getattr(sys, 'frozen', False)
        env_mode = "🔧 .EXE" if is_frozen else "🐍 DEV"
        
        logger.info("=" * 80)
        logger.info(f"📂 SÉLECTION PROJET : {project_name} [{env_mode}]")
        logger.info("=" * 80)
        logger.info(f"⏱ [T+0.000s] Début du processus")
    
        # ✅ ÉTAPE 1 : Vérifier que le projet existe
        if project_name not in self.project_profiles:
            logger.error(f"❌ Projet '{project_name}' introuvable!")
            logger.error(f"   Projets disponibles : {list(self.project_profiles.keys())}")
            return
    
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ Projet trouvé dans project_profiles")
    
        # ✅ ÉTAPE 2 : Récupérer les données originales
        original_data = self.project_profiles[project_name]
    
        # ✅ ÉTAPE 3 : Analyser la structure AVANT copie
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 📊 Analyse des données originales...")
    
        original_ontology = original_data.get('turing_ontology', {})
        original_clusters = original_ontology.get('clusters_detailed', [])
        original_files = original_data.get('files', [])
        original_file_contents = original_data.get('file_contents', {})
    
        logger.info(f"   📩 Clusters : {len(original_clusters)}")
        logger.info(f"   📄 Fichiers : {len(original_files)}")
        logger.info(f"   💟 File contents : {len(original_file_contents)} entrées")
    
        # Détails par cluster
        total_labels = 0
        for i, cluster in enumerate(original_clusters):
            c_name = cluster.get('name', f'Cluster_{i}')
            root_labels = cluster.get('root_labels', [])
            c_files = cluster.get('files', [])
    
            logger.info(f"      [{i}] {c_name}")
            logger.info(f"          Root labels : {len(root_labels)}")
            logger.info(f"          Fichiers : {len(c_files)}")
    
            # Vérifier le type des labels
            if root_labels:
                first_label = root_labels[0]
                if isinstance(first_label, dict):
                    logger.info(f"          ✅ Premier label est un dict")
                else:
                    logger.warning(f"          ⚠ Premier label n'est PAS un dict : {type(first_label)}")
    
            total_labels += len(root_labels)
    
        logger.info(f"   📊 Total labels : {total_labels}")
    
        # ✅ ÉTAPE 4 : Calculer la taille des données
        def get_size(obj, seen=None):
            """Calcule la taille récursive d'un objet"""
            size = sys.getsizeof(obj)
            if seen is None:
                seen = set()
    
            obj_id = id(obj)
            if obj_id in seen:
                return 0
    
            seen.add(obj_id)
    
            if isinstance(obj, dict):
                size += sum([get_size(v, seen) for v in obj.values()])
                size += sum([get_size(k, seen) for k in obj.keys()])
            elif hasattr(obj, '__dict__'):
                size += get_size(obj.__dict__, seen)
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                try:
                    size += sum([get_size(i, seen) for i in obj])
                except:
                    pass
                
            return size
    
        try:
            total_size = get_size(original_data)
            logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 💟 Taille des données : {total_size / (1024*1024):.2f} MB")
    
            if total_size > 100 * 1024 * 1024:
                logger.warning(f"⚠ DONNÉES VOLUMINEUSES : {total_size / (1024*1024):.2f} MB")
                logger.warning("   La copie peut être lente")
        except Exception as e:
            logger.warning(f"⚠ Impossible de calculer la taille : {e}")
    
        # ✅ ÉTAPE 5 : Copie profonde ADAPTATIVE selon l'environnement
        self.current_project_name = project_name
        copy_method = "unknown"
    
        # 🔧 STRATÉGIE .EXE vs DEV
        if is_frozen:
            # ==================== MODE .EXE ====================
            logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🔧 MODE .EXE DÉTECTÉ")
            logger.info("   → Utilisation deepcopy (plus fiable que JSON dans PyInstaller)")
            
            try:
                self.current_project_profile_data = copy.deepcopy(original_data)
                copy_method = "deepcopy_exe"
                logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ deepcopy réussi")
    
            except Exception as e:
                logger.error(f"❌ deepcopy échoué : {e}")
                
                # FALLBACK : Copie manuelle sécurisée
                logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🔄 Tentative copie manuelle sécurisée...")
                try:
                    self.current_project_profile_data = self._manual_copy_secure(original_data)
                    copy_method = "manual_secure"
                    logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ Copie manuelle réussie")
                
                except Exception as e2:
                    logger.error(f"❌ Copie manuelle échouée : {e2}")
                    logger.error("❌ ÉCHEC COMPLET - Utilisation référence directe (DANGEREUX)")
                    self.current_project_profile_data = original_data
                    copy_method = "reference"
    
        else:
            # ==================== MODE DEV ====================
            logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🐍 MODE DEV")
            logger.info("   → Tentative JSON (rapide et propre)")
            
            try:
                json_str = json.dumps(original_data, ensure_ascii=False, indent=None)
                logger.info(f"   JSON string : {len(json_str):,} caractÚres ({len(json_str)/(1024*1024):.2f} MB)")
    
                self.current_project_profile_data = json.loads(json_str)
                copy_method = "json"
                logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ JSON serialization réussie")
    
            except Exception as e:
                logger.error(f"❌ JSON échoué : {e}")
                
                # FALLBACK : deepcopy
                try:
                    logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🔄 Fallback deepcopy...")
                    self.current_project_profile_data = copy.deepcopy(original_data)
                    copy_method = "deepcopy"
                    logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ deepcopy réussi")
    
                except Exception as e2:
                    logger.error(f"❌ deepcopy échoué : {e2}")
                    
                    # DERNIER RECOURS : Copie manuelle
                    logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🔄 Dernier recours : copie manuelle...")
                    try:
                        self.current_project_profile_data = self._manual_copy_secure(original_data)
                        copy_method = "manual_secure"
                    except Exception as e3:
                        logger.error(f"❌ Toutes méthodes échouées : {e3}")
                        self.current_project_profile_data = original_data
                        copy_method = "reference"
    
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 📋 Méthode de copie : {copy_method}")
    
        # ✅ ÉTAPE 6 : Vérifier l'intégrité APRÈs copie
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🔍 Vérification de l'intégrité...")
    
        copied_ontology = self.current_project_profile_data.get('turing_ontology', {})
        copied_clusters = copied_ontology.get('clusters_detailed', [])
        copied_files = self.current_project_profile_data.get('files', [])
    
        logger.info(f"   APRÈs copie :")
        logger.info(f"   📩 Clusters : {len(copied_clusters)} (original: {len(original_clusters)})")
        logger.info(f"   📄 Fichiers : {len(copied_files)} (original: {len(original_files)})")
    
        # Comparer cluster par cluster
        integrity_ok = True
        for i, copied_cluster in enumerate(copied_clusters):
            c_name = copied_cluster.get('name', f'Cluster_{i}')
            copied_labels = copied_cluster.get('root_labels', [])
    
            original_cluster = original_clusters[i] if i < len(original_clusters) else {}
            original_labels = original_cluster.get('root_labels', [])
    
            match = "✅" if len(copied_labels) == len(original_labels) else "❌"
            logger.info(f"      [{i}] {c_name}: {len(copied_labels)} labels (original: {len(original_labels)}) {match}")
    
            if len(copied_labels) != len(original_labels):
                integrity_ok = False
                logger.error(f"         ❌ PERTE DE DONNÉES : {len(original_labels) - len(copied_labels)} labels manquants")
    
                # Détails sur les labels perdus
                if original_labels and not copied_labels:
                    logger.error(f"         Labels originaux existaient mais copie vide!")
                    logger.error(f"         Premiers labels originaux : {[l.get('label', l.get('name', '?')) for l in original_labels[:3]]}")
    
        # 🚹 Si perte de données détectée
        if not integrity_ok:
            logger.error(f"⏱ [T+{time.time()-start_time:.3f}s] ❌ PERTE DE DONNÉES DÉTECTÉE")
            logger.error(f"   Méthode de copie utilisée : {copy_method}")
    
            # 🔧 TENTATIVE DE RÉCUPÉRATION
            logger.warning("   🔧 Tentative de récupération via re-load...")
            try:
                if hasattr(self, 'dgraph_manager') and self.dgraph_connector and self.dgraph_connector.client:
                    logger.info("   📡 Re-chargement depuis Dgraph...")
                    fresh_profiles = self.dgraph_manager._load_project_profiles()
    
                    if project_name in fresh_profiles:
                        # Remplacer les données
                        self.current_project_profile_data = fresh_profiles[project_name]
    
                        # Re-vérifier
                        recovered_clusters = self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])
                        logger.info(f"   ✅ Récupéré {len(recovered_clusters)} clusters depuis Dgraph")
    
                        if len(recovered_clusters) == len(original_clusters):
                            integrity_ok = True
                            copy_method = "dgraph_recovery"
                            logger.info(f"   ✅ Récupération réussie!")
                        else:
                            logger.error(f"   ❌ Récupération partielle : {len(recovered_clusters)}/{len(original_clusters)} clusters")
                    else:
                        logger.error(f"   ❌ Projet '{project_name}' introuvable dans Dgraph")
                else:
                    logger.error(f"   ❌ Dgraph non disponible pour récupération")
    
            except Exception as e:
                logger.error(f"   ❌ Échec récupération : {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ Intégrité des données vérifiée")
    
        # ✅ ÉTAPE 7 : Charger les pending_relations
        pending_relations_data = self.current_project_profile_data.get("pending_relations", {})
        self.pending_relations = defaultdict(list, pending_relations_data)
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 📊 Pending relations : {len(self.pending_relations)} entrées")
    
        # ✅ ÉTAPE 8 : Synchroniser avec les autres composants
        self.global_relations_config.current_project_profile_data = self.current_project_profile_data
        self.relations_graph.current_project_profile_data = self.current_project_profile_data
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] ✅ Composants synchronisés")
    
        # ✅ ÉTAPE 9 : Charger dans l'UI
        logger.info(f"⏱ [T+{time.time()-start_time:.3f}s] 🎹 Chargement dans l'UI...")
        self._load_project_data_into_ui()
    
        # ✅ ÉTAPE 10 : Mettre à jour les détails et boutons
        self._update_project_details()
        self._update_button_states()
    
        # ✅ ÉTAPE 11 : Test des relations
        self.dgraph_manager._test_relations_loading()
    
        # ✅ RÉSUMÉ FINAL
        total_time = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"✅ SÉLECTION TERMINÉE en {total_time:.3f}s")
        logger.info(f"   Environnement : {env_mode}")
        logger.info(f"   Projet : {project_name}")
        logger.info(f"   Méthode copie : {copy_method}")
        logger.info(f"   Intégrité : {'✅ OK' if integrity_ok else '❌ ERREUR'}")
        logger.info(f"   Clusters : {len(copied_clusters)}")
        logger.info(f"   Total labels : {sum(len(c.get('root_labels', [])) for c in copied_clusters)}")
        logger.info("=" * 80)
    
    def _load_project_data_into_ui(self):
        """Charge les données du projet dans l'UI avec réinitialisation complète."""
        if not self.current_project_profile_data:
            return

        # Réinitialiser toute la hiérarchie
        self.current_cluster_data = None
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_cluster_index = -1
        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        # Vider toutes les listes
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Charger les informations de base
        self.project_name_edit.setText(self.current_project_profile_data.get('name', ''))
        self.project_description_edit.setPlainText(self.current_project_profile_data.get('description', ''))

        # Charger uniquement la liste des clusters
        self._refresh_cluster_list()

        # Collecter tous les labels pour les relations
        self._collect_all_labels()

        # Réinitialiser les relations et graphe
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

    def _update_project_details(self):
        """Met à jour les détails du projet sélectionné."""
        if self.current_project_name:
            details = f"Projet: {self.current_project_name}\n"
            details += f"Clusters: {len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []))}\n"
            details += f"Fichiers: {len(self.current_project_profile_data.get('files', []))}"
            self.details_text.setPlainText(details)

    def _get_icon_for_item(self, item_data: Dict[str, Any], default_color: str = '#2c3e50') -> QtGui.QIcon:
        item_type = item_data.get('type', 'folder')
        label = item_data.get('label', item_data.get('name', ''))

        # Logique pour déterminer si c'est un fichier
        is_file = (
            item_type == 'file' or
            label.lower().endswith((
                '.ts', '.py', '.js', '.java', '.cpp', '.json', '.c', '.h', '.tsx', 
                '.jsx', '.cs', '.php', '.rb', '.go', '.html', '.css', '.xml', 
                '.txt', '.md', '.yaml', '.yml', '.net'
            ))
        )

        if is_file:
            return qta.icon('fa5s.file-code', color='#666666')  # Noir pour les fichiers
        else:
            return qta.icon('fa5s.folder', color=default_color)

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters sans charger les niveaux inférieurs."""
        self.cluster_list_widget.clear()
        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        folder_color = "#FFD700"  # Couleur orange pour les dossiers/clusters
        for cluster in clusters:
            cluster_item = QListWidgetItem(cluster["name"])
            # Utiliser la méthode helper pour l'icône (clusters sont des dossiers)
            icon = self._get_icon_for_item(cluster, folder_color)
            cluster_item.setIcon(icon)
            cluster_item.setData(Qt.UserRole, cluster.get('uid', ''))
            cluster_item.setData(Qt.UserRole + 1, 'cluster')
            cluster_item.setForeground(QtGui.QColor(folder_color))
            self.cluster_list_widget.addItem(cluster_item)

    def _on_cluster_selected(self, current):
        if not current:
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_index = self.cluster_list_widget.row(current)

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        if self.current_cluster_index < 0 or self.current_cluster_index >= len(clusters):
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_data = clusters[self.current_cluster_index]

        # Réinitialiser niveaux inférieurs
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        # ❌ ANCIEN CODE (affiche juste les noms)
        # self._populate_root_list_with_cluster_files()

        # ✅ NOUVEAU CODE (affiche fichiers ET dossiers)
        self._populate_root_list()

        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Afficher détails
        details = f"Cluster: {self.current_cluster_data.get('name', '')}\n"
        details += f"Description: {self.current_cluster_data.get('description', '')}\n"
        details += f"Root Labels: {len(self.current_cluster_data.get('root_labels', []))}\n"
        details += f"Fichiers: {len(self.current_cluster_data.get('files', []))}\n"
        self.details_text.setPlainText(details)

        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """
        Gère la sélection dans level1_list (fichiers, children OU éléments de code).
        """
        if not current:
            self.current_level1_data = None
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)

        # === CAS 1 : Fichier sélectionné → afficher ses éléments dans child_list ===
        if item_type == 'root_file':
            file_path = current.data(Qt.UserRole + 2)
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            classes = self.dependency_parser.extract_classes(content, file_path)
            functions = self.dependency_parser.extract_functions(content, file_path)
            variables = self.dependency_parser.extract_variables(content, file_path)

            self._display_code_elements_in_list(
                self.child_list_widget,
                classes,
                functions,
                variables,
                file_path
            )

            details = f"📄 Fichier: {os.path.basename(file_path)}\n\n"
            details += f"Classes: {len(classes)}\n"
            details += f"Fonctions: {len(functions)}\n"
            details += f"Variables: {len(variables)}\n"
            self.details_text.setPlainText(details)

            self.current_selected_label_uid = None
            self.current_level1_data = None

        # === CAS 2 : Child sélectionné → afficher ses fichiers + children + éléments ===
        elif item_type in ['folder', 'file', 'child']:
            item_uid = current.data(Qt.UserRole)
            self.current_selected_label_uid = item_uid

            child_data = self._find_child_by_uid(self.current_root_data, item_uid)

            if child_data:
                self.current_level1_data = child_data
                self._update_selected_details("Niveau 1", child_data)

                self._populate_child_list_with_parent_files()

                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)

        # === CAS 3 : Élément de code sélectionné ===
        elif item_type in ['class', 'function', 'variable']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            details = f"Type: {item_type.upper()}\n"
            details += f"Fichier: {os.path.basename(file_path)}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

            self.child_list_widget.clear()

        self._update_button_states()
    
    def _add_child_to_list(self, child: Dict, list_widget, indent: str = ""):
        child_type = child.get('type', 'folder')
        child_label = child.get('label', child.get('name', 'Sans nom'))

        display = f"{indent}{child_label}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Récursion pour dossiers
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_list(grandchild, list_widget, indent + "  ")

    def _show_code_elements_popup(self, file_name, classes, functions, variables, file_path):
        """
        Affiche une popup avec les classes/fonctions/variables d'un fichier.
        Utilisé pour les fichiers des labels enfants (plus de place dans l'UI).

        Args:
            file_name: Nom du fichier
            classes: Liste des classes
            functions: Liste des fonctions
            variables: Liste des variables
            file_path: Chemin complet du fichier
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Éléments de code : {file_name}")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"<b>Fichier :</b> {file_name}<br><b>Chemin :</b> {file_path}")
        header.setWordWrap(True)
        layout.addWidget(header)

        # Stats
        stats = QLabel(
            f"<b>Classes :</b> {len(classes)} | "
            f"<b>Fonctions :</b> {len(functions)} | "
            f"<b>Variables :</b> {len(variables)}"
        )
        stats.setStyleSheet("color: #34495e; font-size: 11pt; padding: 5px;")
        layout.addWidget(stats)

        # Liste
        list_widget = QListWidget()
        list_widget.setStyleSheet(self._get_improved_list_style())
        self._display_code_elements_in_list(list_widget, classes, functions, variables, file_path)
        layout.addWidget(list_widget)

        # Boutons
        button_layout = QHBoxLayout()

        view_file_button = QPushButton("📄 Voir le fichier")
        view_file_button.clicked.connect(
            lambda: self.code_dialogs._show_file_content_dialog(
                file_name,
                self.current_project_profile_data.get('file_contents', {}).get(file_path, ''),
                {'label': file_name, 'uid': str(uuid.uuid4())}
            )
        )
        button_layout.addWidget(view_file_button)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.exec_()

    def _populate_level1_list(self):
        self.level1_list_widget.clear()

        if not self.current_root_data:
            return

        # Couleurs
        primary = '#A23B2D'
        dark_gray = '#424242'
        medium_gray = '#666666'
        strong_gray = '#555555'

        def modulate_color(base_color: str, lvl: int = 1):
            if lvl > 1:
                if base_color == primary:
                    return '#D35A4A'
                elif base_color == dark_gray:
                    return '#5A5A5A'
                elif base_color == medium_gray:
                    return '#888888'
            return base_color

        modulated_primary = modulate_color(primary)
        modulated_dark = modulate_color(dark_gray)

        has_items = False

        # === NOUVEAU : Afficher TOUS les children (fichiers + éléments de code) ===
        for child in self.current_root_data.get("children", []):
            has_items = True

            child_type = child.get('type', 'folder')
            label = child.get('label', child.get('name', 'Sans nom'))
            child_uid = child.get('uid', str(uuid.uuid4()))
            if 'uid' not in child:
                child['uid'] = child_uid

            line_num = child.get('line', 0)
            file_path = child.get('file', '')

            # === TRAITEMENT PAR TYPE ===
            icon = None
            color = QtGui.QColor("#000000")
            display = label

            if child_type == 'class':
                icon = qta.icon('fa5s.cube', color=strong_gray)
                color = QtGui.QColor(strong_gray)
                display = f"[CLASS] {label} (ligne {line_num})"

            elif child_type in ['function', 'method']:
                icon = qta.icon('fa5s.cog', color=modulated_primary)
                color = QtGui.QColor(modulated_primary)
                prefix = "[METH]" if child_type == 'method' else "[FUNC]"
                display = f"{prefix} {label} (ligne {line_num})"

            elif child_type == 'variable':
                icon = qta.icon('fa5s.tag', color=medium_gray)
                color = QtGui.QColor(medium_gray)
                display = f"[VAR] {label} (ligne {line_num})"

            elif label.endswith((
                '.ts', '.py', '.js', '.java', '.cpp', '.json', '.net',
                '.c', '.h', '.tsx', '.jsx', '.cs', '.php', '.rb', '.go',
                '.html', '.css', '.xml', '.txt', '.md', '.yaml', '.yml'
            )):
                icon = qta.icon('fa5s.file-code', color=medium_gray)
                color = QtGui.QColor(medium_gray)
                display = label

            elif child_type in ['folder', 'directory']:
                icon = qta.icon('fa5s.folder', color=modulated_dark)
                color = QtGui.QColor(modulated_dark)
                display = label

            else:
                icon = qta.icon('fa5s.question-circle', color="#16a085")
                color = QtGui.QColor("#16a085")
                display = f"[UNKNOWN] {label}"

            # === CRÉER L'ITEM ===
            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, child_uid)
            item.setData(Qt.UserRole + 1, child_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, line_num)
            item.setForeground(color)

            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)

            self.level1_list_widget.addItem(item)

        # === Message vide ===
        if not has_items:
            empty_item = QListWidgetItem("(Aucun élément trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            font = QtGui.QFont()
            font.setPointSize(7)
            empty_item.setFont(font)
            self.level1_list_widget.addItem(empty_item)

        self._update_button_states()

    def _on_child_label_selected(self, current):
        if not current:
            self.current_level2_data = None
            return

        item_type = current.data(Qt.UserRole + 1)
        item_uid = current.data(Qt.UserRole)

        # Skip les items de navigation
        if item_type == 'navigation':
            return

        # ✅ CAS 1 : Dossier (navigation hiérarchique)
        if item_type in ['folder', 'directory', 'child']:
            # ✅ PROTECTION : Vérifier que current_level1_data existe
            if not self.current_level1_data:
                logger.warning("⚠️ current_level1_data est None, impossible de naviguer")
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Erreur", 
                    "Aucun label parent sélectionné. Veuillez d'abord sélectionner un élément dans la liste niveau 1."
                )
                return

            folder_data = self._find_child_by_uid(self.current_level1_data, item_uid)

            if folder_data:
                # Sauvegarder l'état actuel pour retour arrière
                self.child_navigation_stack.append({
                    'parent': self.current_child_parent,
                    'list_items': self._save_list_state(self.child_list_widget)
                })

                self.current_child_parent = folder_data
                self.current_level2_data = folder_data
                self.current_selected_label_uid = item_uid

                self._populate_child_list_for_folder(folder_data)
                self._update_child_navigation_ui()

                self._update_selected_details("Dossier", folder_data)

                self.global_relations_config.update_current(item_uid)
                self.relations_graph.update_graph(item_uid)
            else:
                logger.warning(f"⚠️ Dossier introuvable pour UID: {item_uid}")

        elif item_type == 'level1_file':
            file_path = current.data(Qt.UserRole + 2)

            if not file_path:
                logger.warning("⚠️ Chemin de fichier manquant")
                return

            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            if content:
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)

                # Sauvegarder l'état pour retour
                self.child_navigation_stack.append({
                    'parent': self.current_child_parent,
                    'list_items': self._save_list_state(self.child_list_widget)
                })

                file_parent = {
                    'label': os.path.basename(file_path),
                    'uid': f"file_{file_path}",
                    'type': 'file',
                    'path': file_path,
                    'classes': classes,
                    'functions': functions,
                    'variables': variables
                }

                self.current_child_parent = file_parent

                self._populate_child_list_for_file(file_path, classes, functions, variables)
                self._update_child_navigation_ui()

                details = f"📄 Fichier: {os.path.basename(file_path)}\n\n"
                details += f"Classes: {len(classes)}\n"
                details += f"Fonctions: {len(functions)}\n"
                details += f"Variables: {len(variables)}\n"
                self.details_text.setPlainText(details)

        # ✅ CAS 3 : Élément de code (classe, fonction, variable, méthode)
        elif item_type in ['class', 'function', 'variable', 'method']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            # ✅ Extraire le nom proprement
            text = current.text()

            # Retirer l'icône et le préfixe [CLASS], [FUNC], etc.
            if '[' in text:
                name_part = text.split(']', 1)[1].strip()
            else:
                name_part = text.strip()

            # Retirer la partie "(ligne X)"
            if '(' in name_part:
                element_name = name_part.split('(')[0].strip()
            else:
                element_name = name_part

            details = f"Type: {item_type.upper()}\n"
            details += f"Nom: {element_name}\n"
            details += f"Fichier: {os.path.basename(file_path) if file_path else 'N/A'}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

            self.current_selected_label_uid = item_uid
            self.global_relations_config.update_current(item_uid)
            self.relations_graph.update_graph(item_uid)

        self._update_button_states()

    def _populate_child_list_for_file(self, file_path: str, classes: List, functions: List, variables: List):
        """Affiche éléments de code d'un fichier SANS bouton retour (maintenant externe)."""
        self.child_list_widget.clear()

        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément de code trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            self.child_list_widget.addItem(empty_item)
            return

        # === CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#e74c3c"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

            # Méthodes indentées
            for method in cls.get('methods', []):
                method_item = QListWidgetItem(f"  ↳ {method.get('name', 'method')} (ligne {method.get('line', '?')})")
                method_item.setData(Qt.UserRole, method.get('uid', str(uuid.uuid4())))
                method_item.setData(Qt.UserRole + 1, 'method')
                method_item.setData(Qt.UserRole + 2, file_path)
                method_item.setData(Qt.UserRole + 3, method.get('line', 0))
                method_item.setForeground(QtGui.QColor("#c0392b"))
                self.child_list_widget.addItem(method_item)

        # === FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, func.get('line', 0))
            item.setForeground(QtGui.QColor("#3498db"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

        # === VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'local')

            item = QListWidgetItem(f"[VAR] {var['name']} ({var_type}, ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, var.get('line', 0))
            item.setForeground(QtGui.QColor("#2ecc71"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            self.child_list_widget.addItem(item)

    def _on_child_navigation_back(self):
        """Retour en arrière dans la navigation des enfants."""
        if not self.child_navigation_stack:
            # Retour au niveau 1
            if self.current_level1_data:
                self._populate_child_list_with_parent_files()
            self.current_child_parent = None
            self._update_child_navigation_ui()
            return

        previous_state = self.child_navigation_stack.pop()
        self.current_child_parent = previous_state['parent']

        self._restore_list_state(self.child_list_widget, previous_state['list_items'])
        self._update_child_navigation_ui()

    def _update_navigation_buttons(self):
        is_navigating = bool(self.child_navigation_stack)

        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(not is_navigating and has_level1)
        self.edit_child_button.setEnabled(not is_navigating and self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(not is_navigating and self.child_list_widget.currentRow() != -1)

    def _restore_list_state(self, list_widget, items):
        list_widget.clear()
        for item_data in items:
            item = QListWidgetItem(item_data['text'])
            item.setData(Qt.UserRole, item_data['uid'])
            item.setData(Qt.UserRole + 1, item_data['type'])
            item.setData(Qt.UserRole + 2, item_data['data2'])
            item.setData(Qt.UserRole + 3, item_data['data3'])
            item.setForeground(QtGui.QColor(item_data['color']))
            list_widget.addItem(item)

    def _setup_child_list_connections(self):
        if hasattr(self, 'child_list_widget') and self.child_list_widget:
            self.child_list_widget.itemClicked.connect(self._on_child_item_clicked)
            self.child_list_widget.itemDoubleClicked.connect(self._on_double_click_item)
            logger.debug("✅ Signaux child_list_widget connectés")
        else:
            logger.error("❌ child_list_widget n'existe pas!")


    def _on_child_item_clicked(self, item):
        if not item:
            return

        item_type = item.data(Qt.UserRole + 1)

        if item_type == 'navigation':
            uid = item.data(Qt.UserRole)
            if uid == 'back_navigation':
                self._on_child_navigation_back()
                return

        self._on_child_label_selected(item)

    def _populate_child_list_for_folder(self, folder_data: Dict, level: int = 1):
        self.child_list_widget.clear()

        if not folder_data:
            return

        has_items = False

        primary = '#A23B2D'
        dark_gray = '#424242'
        medium_gray = '#666666'
        strong_gray = '#555555'

        def modulate_color(base_color: str, lvl: int):
            """Renvoie une teinte légèrement modifiée selon le niveau hiérarchique"""
            if lvl > 1:
                if base_color == primary:
                    return '#D35A4A'  # Rouge plus clair
                elif base_color == dark_gray:
                    return '#5A5A5A'  # Gris plus clair
                elif base_color == medium_gray:
                    return '#888888'
            return base_color

        # Couleurs modulées selon le niveau
        modulated_primary = modulate_color(primary, level)
        modulated_dark = modulate_color(dark_gray, level)

        for child in folder_data.get('children', []):
            has_items = True

            child_label = child.get('label', child.get('name', 'Sans nom'))
            label_lower = child_label.lower()
            child_uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = child_uid

            file_path = child.get('file', '')
            line_num = child.get('line', 0)
            display_type = "unknown"
            icon = None
            color = QtGui.QColor("#000000")

            # === Détection par préfixe ===
            if label_lower.startswith(("class", "[class", "classe")):
                display_type = "class"
                icon = qta.icon('fa5s.cube', color=strong_gray)
                color = QtGui.QColor(strong_gray)

            elif label_lower.startswith(("function", "[func", "fonction")):
                display_type = "function"
                icon = qta.icon('fa5s.cog', color=modulated_primary)
                color = QtGui.QColor(modulated_primary)

            elif label_lower.startswith(("method", "[meth", "methode")):
                display_type = "function"  # méthode assimilée à fonction
                icon = qta.icon('fa5s.cog', color=modulated_primary)
                color = QtGui.QColor(modulated_primary)

            elif label_lower.startswith(("variable", "[var", "var_")):
                display_type = "variable"
                icon = qta.icon('fa5s.tag', color=medium_gray)
                color = QtGui.QColor(medium_gray)

            elif label_lower.endswith((
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
                '.php', '.rb', '.cs', '.go', '.html', '.css', '.xml', '.json',
                '.yml', '.yaml', '.md', '.txt', '.vue', '.svelte', '.sql', '.bat', '.sh'
            )):
                display_type = "file"
                icon = qta.icon('fa5s.file-code', color=medium_gray)
                color = QtGui.QColor(medium_gray)

            elif label_lower.startswith(("folder", "dir", "📁")):
                display_type = "folder"
                icon = qta.icon('fa5s.folder', color=modulated_dark)
                color = QtGui.QColor(modulated_dark)

            elif label_lower.startswith(("dependency", "dependance")):
                display_type = "dependency"
                icon = qta.icon('fa5s.cubes', color=modulated_dark)
                color = QtGui.QColor(modulated_dark)

            else:
                display_type = "unknown"
                icon = qta.icon('fa5s.question-circle', color="#16a085")
                color = QtGui.QColor("#16a085")

            # === Création de l’élément ===
            item = QListWidgetItem(child_label)
            item.setIcon(icon)
            item.setData(Qt.UserRole, child_uid)
            item.setData(Qt.UserRole + 1, display_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, line_num)
            item.setForeground(color)

            # Police sobre et petite
            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)

            self.child_list_widget.addItem(item)

        # === Dossier vide ===
        if not has_items:
            empty_item = QListWidgetItem("(Dossier vide)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            font = QtGui.QFont()
            font.setPointSize(7)
            empty_item.setFont(font)
            self.child_list_widget.addItem(empty_item)


    def _setup_navigation_button_style(self):
        self.back_navigation_btn.installEventFilter(self)
    
    def _save_list_state(self, list_widget):
        items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            items.append({
                'text': item.text(),
                'uid': item.data(Qt.UserRole),
                'type': item.data(Qt.UserRole + 1),
                'data2': item.data(Qt.UserRole + 2),
                'data3': item.data(Qt.UserRole + 3),
                'color': item.foreground().color().name()
            })
        return items

    def _display_code_elements_in_list(self, list_widget, classes, functions, variables, file_path):
        list_widget.clear()

        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            list_widget.addItem(empty_item)
            return

        # === CLASSES avec icône ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            icon = self._get_element_icon('class')
            item = QListWidgetItem(f"{icon} [CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#e74c3c"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

            # Méthodes indentées avec icône
            for method in cls.get('methods', []):
                method_icon = self._get_element_icon('method')
                method_item = QListWidgetItem(f"  {method_icon} {method.get('name', 'method')} (ligne {method.get('line', '?')})")
                method_item.setData(Qt.UserRole, str(uuid.uuid4()))
                method_item.setData(Qt.UserRole + 1, 'method')
                method_item.setData(Qt.UserRole + 2, method.get('line', 0))
                method_item.setForeground(QtGui.QColor("#c0392b"))
                list_widget.addItem(method_item)

        # === FONCTIONS avec icône ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            icon = self._get_element_icon(func_type)
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{icon} {prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#3498db"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        # === VARIABLES avec icône ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'local')
            icon = self._get_element_icon('variable')

            item = QListWidgetItem(f"{icon} [VAR] {var['name']} ({var_type}, ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#2ecc71"))
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        logger.info(f"Affiché {len(classes)} classes, {len(functions)} fonctions, {len(variables)} variables avec icônes")

    def _on_any_label_selected(self, current):
        """
        Handles selection of ANY label (root, level1, level2, child).
        Updates relations config and graph for the selected node.

        This is a unified handler to avoid code duplication across different
        list widgets.
        """
        if current:
            # Get UID from the selected item
            uid = current.data(Qt.UserRole)

            if not uid:
                logger.warning("Selected item has no UID")
                self.current_selected_label_uid = None
                self.global_relations_config.update_current(None)
                self.relations_graph.update_graph(None)
                return

            self.current_selected_label_uid = uid

            # Update relations config and graph
            self.global_relations_config.update_current(uid)
            self.relations_graph.update_graph(uid)

            logger.debug(f"Label sélectionné: {uid}")
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _on_any_label_selected(self, current):
        """Gère la sélection de n'importe quel label pour relations et graphe."""
        if current:
            self.current_selected_label_uid = current.data(Qt.UserRole)
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _update_selected_details(self, title, data):
        """Met à jour les détails de l'élément sélectionné. Amélioration pour clusters-fichiers."""
        if not data:
            self.details_text.clear()
            return

        is_file_cluster = data.get('is_file_cluster', False)
        if is_file_cluster:
            details = f"=== {title} ===\n\n"
            details += f"Nom: {data.get('name', '')}\n"
            details += f"Description: {data.get('description', '')}\n\n"
            files = data.get('files', [])
            if files:
                details += f"Fichier: {files[0]}\n"  # Un seul fichier pour file-cluster
                content = data.get('file_contents', {}).get(files[0], '')
                details += f"Contenu (résumé): {content[:200]}..." if len(content) > 200 else f"Contenu: {content}"
            else:
                details += "Aucun fichier associé\n"
            # Pas de hiérarchie/relations pour file-cluster
            details += "\nNote: Pas de hiérarchie ni relations pour un cluster-fichier."
            self.details_text.setPlainText(details)
            return

        # Comportement normal pour labels (inchangé)
        details = f"=== {title} ===\n\n"
        details += f"Nom: {data.get('label', '')}\n"
        details += f"ID: {data.get('id', '')}\n"
        details += f"UID: {data.get('uid', '')}\n"
        details += f"Description: {data.get('description', '')}\n\n"

        categories = data.get('category', [])
        if categories:
            details += f"Catégories: {', '.join(categories)}\n\n"

        files = data.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:10]:  # Limiter à 10 fichiers pour l'affichage
                details += f"  - {f}\n"
            if len(files) > 10:
                details += f"  ... et {len(files) - 10} autres\n"
        else:
            details += "Aucun fichier associé\n"

        # Relations sortantes
        outgoing = data.get('outgoing_relations', [])
        if outgoing:
            details += f"\nRelations sortantes ({len(outgoing)}):\n"
            for r in outgoing:
                target_name = self.label_uid_to_info.get(r['target_uid'], {}).get('name', 'Inconnu')
                details += f"  {r['relation_type'].upper()} -> {target_name}\n"

        # Relations entrantes
        incoming = data.get('incoming_relations', [])
        if incoming:
            details += f"\nRelations entrantes ({len(incoming)}):\n"
            for r in incoming:
                source_name = self.label_uid_to_info.get(r['source_uid'], {}).get('name', 'Inconnu')
                details += f"  {source_name} {r['relation_type'].upper()} -> \n"

        # Ajouter info sur la hiérarchie
        if title == "Label Racine":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"
        elif title == "Label Niveau 1":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"

        self.details_text.setPlainText(details)

    def _reset_hierarchy_ui(self):
        """Réinitialise complètement l'interface hiérarchique."""
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

        self.details_text.clear()

    def _collect_all_labels(self):
        """
        CORRECTION: Collecte avec génération systématique d'UIDs
        """
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()

        if not self.current_project_profile_data:
            return

        ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = ontology.get("clusters_detailed", [])

        for cluster in clusters_detailed:
            cluster_name = cluster.get('name', '')
            root_labels = cluster.get("root_labels", [])

            for root in root_labels:
                # ✅ Assurer qu'un UID existe
                if 'uid' not in root or not root['uid']:
                    root['uid'] = root.get('id') or str(uuid.uuid4())

                uid = root['uid']

                info = {
                    'name': root.get('label', ''),
                    'cluster': cluster_name,
                    'type': 'label'
                }
                self.label_uid_to_info[uid] = info
                self.name_to_uid[root.get('label', '')] = uid

                # Collecter récursivement
                self._collect_labels_recursive(root, cluster_name)

    def _collect_labels_recursive(self, node, cluster_name=''):
        """
         CORRECTION: Collecte récursive avec génération d'UIDs
        """
        children = node.get('children', [])

        for child in children:
            # Assurer qu'un UID existe
            if 'uid' not in child or not child['uid']:
                child['uid'] = child.get('id') or str(uuid.uuid4())

            uid = child['uid']

            # Récupérer cluster du parent
            parent_uid = node.get('uid')
            parent_cluster = self.label_uid_to_info.get(parent_uid, {}).get('cluster', cluster_name)

            info = {
                'name': child.get('label', child.get('name', '')),
                'cluster': parent_cluster,
                'type': child.get('type', 'label')
            }
            self.label_uid_to_info[uid] = info

            label_name = child.get('label', child.get('name', ''))
            if label_name:
                self.name_to_uid[label_name] = uid

            # Appel récursif
            self._collect_labels_recursive(child, parent_cluster)

        # Collecter les classes
        for cls in node.get('classes', []):
            if 'uid' not in cls or not cls['uid']:
                cls['uid'] = f"cls_{cls.get('name', '')}_{str(uuid.uuid4())[:8]}"

            cls_uid = cls['uid']

            info = {
                'name': cls.get('name', ''),
                'label': cls.get('name', ''),
                'cluster': cluster_name,
                'type': 'class',
                'parent_label': node.get('label', ''),
                'file': cls.get('file', '')
            }
            self.label_uid_to_info[cls_uid] = info

            cls_name = cls.get('name', '')
            if cls_name:
                self.name_to_uid[cls_name] = cls_uid

        # Collecter les fonctions
        for func in node.get('functions', []):
            if 'uid' not in func or not func['uid']:
                func['uid'] = f"func_{func.get('name', '')}_{str(uuid.uuid4())[:8]}"

            func_uid = func['uid']

            info = {
                'name': func.get('name', ''),
                'label': func.get('name', ''),
                'cluster': cluster_name,
                'type': func.get('type', 'function'),
                'parent_label': node.get('label', ''),
                'file': func.get('file', '')
            }
            self.label_uid_to_info[func_uid] = info

            func_name = func.get('name', '')
            if func_name:
                self.name_to_uid[func_name] = func_uid

        # Collecter les variables
        for var in node.get('variables', []):
            if 'uid' not in var or not var['uid']:
                var['uid'] = f"var_{var.get('name', '')}_{str(uuid.uuid4())[:8]}"

            var_uid = var['uid']

            info = {
                'name': var.get('name', ''),
                'label': var.get('name', ''),
                'cluster': cluster_name,
                'type': 'variable',
                'parent_label': node.get('label', ''),
                'file': var.get('file', '')
            }
            self.label_uid_to_info[var_uid] = info

            var_name = var.get('name', '')
            if var_name:
                self.name_to_uid[var_name] = var_uid

    def _add_cluster(self):
        dialog = AddEditItemDialog("Ajouter Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "files": [],
                    "file_contents": {},
                    "root_labels": []
                }
                self.current_project_profile_data["turing_ontology"]["clusters_detailed"].append(new_cluster)
                self._refresh_cluster_list()
                self._collect_all_labels()
                self.cluster_list_widget.setCurrentRow(self.cluster_list_widget.count() - 1)
                self._update_button_states()
                logger.info(f"Cluster ajouté: {data['name']}")

    def _edit_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
        dialog = AddEditItemDialog("Modifier Cluster", cluster["name"], cluster["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                cluster["name"] = data["name"]
                cluster["description"] = data["description"]
                self._refresh_cluster_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Cluster modifié: {data['name']}")

    def _remove_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster_name = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]["name"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le cluster '{cluster_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
            self._refresh_cluster_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Cluster supprimé: {cluster_name}")

    def _add_root_label(self):
        """Ajoute un label racine avec vérification des fichiers."""
        if not self.current_cluster_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Racine", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_root = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_cluster_data["root_labels"].append(new_root)
                self._populate_root_list()
                self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine ajouté: {data['name']}")

    def _edit_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root = self.current_cluster_data["root_labels"][index]
        dialog = AddEditItemDialog("Modifier Label Racine", root["label"], root["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                root["label"] = data["name"]
                root["description"] = data["description"]
                self._populate_root_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine modifié: {data['name']}")

    def _remove_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root_name = self.current_cluster_data["root_labels"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label racine '{root_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data["root_labels"][index]
            self._populate_root_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label racine supprimé: {root_name}")

    def _add_level1_label(self):
        """Ajoute un label niveau 1 avec vérification des fichiers."""
        if not self.current_root_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 1", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_level1 = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_root_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_root_data["children"].append(new_level1)
                self._populate_level1_list()
                self.level1_list_widget.setCurrentRow(self.level1_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 ajouté: {data['name']}")

    def _edit_level1_label(self):
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1 = self.current_root_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 1", level1["label"], level1["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                level1["label"] = data["name"]
                level1["description"] = data["description"]
                self._populate_level1_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 modifié: {data['name']}")

    def _remove_level1_label(self): 
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1_name = self.current_root_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 1 '{level1_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_root_data["children"][index]
            self._populate_level1_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 1 supprimé: {level1_name}")

    def _add_child_label(self):
        """Ajoute un label enfant avec vérification des fichiers."""
        if not self.current_level1_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 2", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_child = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_level1_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_level1_data["children"].append(new_child)
                self._populate_child_list()
                self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 ajouté: {data['name']}")

    def _edit_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child = self.current_level1_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 2", child["label"], child["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                child["label"] = data["name"]
                child["description"] = data["description"]
                self._populate_child_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 modifié: {data['name']}")

    def _remove_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child_name = self.current_level1_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 2 '{child_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_level1_data["children"][index]
            self._populate_child_list()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 2 supprimé: {child_name}")

    def _add_all_files_from_dir(self, dir_path, base_dir, label, profile):
        """Ajoute récursivement tous les fichiers d'un dossier à un label."""
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                content = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                label['files'].append(rel_path)
                label['file_contents'][rel_path] = content

    def _build_sub_hierarchy(self, dir_path, base_dir, parent_label, is_parents=True, profile=None):
        """Construit la hiérarchie récursivement à partir d'un dossier."""
        level_key = 'children' if is_parents else 'children'
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
            if os.path.isfile(item_path):
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                if profile:
                    profile['files'].append(rel_path)
                    profile['file_contents'][rel_path] = content
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
            elif os.path.isdir(item_path):
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'files': [],
                    'file_contents': {},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
                if is_parents:
                    self._build_sub_hierarchy(item_path, base_dir, new_label, False, profile)
                else:
                    # Pour le niveau children, ajouter les fichiers profonds au label
                    self._add_all_files_from_dir(item_path, base_dir, new_label, profile)

    def _scan_project_directory(self, directory):
        """
        ✅ VERSION CORRIGÉE : Merge avec clusters existants au lieu de dupliquer
        """
        project_name = os.path.basename(directory)

        # ✅ RÉCUPÉRER LE PROFIL EXISTANT (si présent)
        if project_name in self.project_profiles:
            profile = self.project_profiles[project_name]
            logger.info(f"🔄 Mise à jour du projet existant : {project_name}")
        else:
            profile = {
                'name': project_name,
                'description': f"Projet importé depuis {directory}",
                'files': [],
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': {}
            }
            logger.info(f"✅ Création nouveau projet : {project_name}")

        # ✅ CRÉER UN INDEX DES CLUSTERS EXISTANTS
        existing_clusters = {
            cluster['name']: cluster 
            for cluster in profile['turing_ontology']['clusters_detailed']
        }

        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            cluster_name = item

            # ✅ MERGE AU LIEU DE CRÉER UN DOUBLON
            if cluster_name in existing_clusters:
                cluster = existing_clusters[cluster_name]
                logger.info(f"🔄 Mise à jour cluster existant : {cluster_name}")
            else:
                cluster = {
                    'name': cluster_name,
                    'uid': str(uuid.uuid4()),
                    'description': f"{'Fichier' if os.path.isfile(item_path) else 'Dossier'}: {item}",
                    'files': [],
                    'file_contents': {},
                    'root_labels': [],
                    'is_file_cluster': False
                }
                profile['turing_ontology']['clusters_detailed'].append(cluster)
                existing_clusters[cluster_name] = cluster
                logger.info(f"✅ Nouveau cluster : {cluster_name}")

            # === CAS 1 : FICHIER DIRECT ===
            if os.path.isfile(item_path):
                rel_path = item
                content = self._read_file_safe(item_path)

                if rel_path not in profile['files']:
                    profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content

                if rel_path not in cluster['files']:
                    cluster['files'].append(rel_path)
                cluster['file_contents'][rel_path] = content
                cluster['is_file_cluster'] = True

            # === CAS 2 : DOSSIER ===
            elif os.path.isdir(item_path):
                cluster['is_file_cluster'] = False

                # ✅ SCANNER RÉCURSIF (sans dupliquer les labels)
                self._scan_directory_recursive(
                    item_path,
                    directory,
                    cluster,
                    profile,
                    parent_label=None,
                    level=0
                )

        logger.info(f"✅ Scanné {len(profile['files'])} fichiers depuis {directory}")
        return profile
    
    def _scan_directory_recursive(self, dir_path, base_dir, cluster, profile, 
                          parent_label=None, level=0):
        """
        ✅ CORRIGÉ : Évite les doublons de labels dans les scans successifs
        """
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
    
            # === FICHIER ===
            if os.path.isfile(item_path):
                content = self._read_file_safe(item_path)
    
                # ✅ VÉRIFIER SI DÉJÀ EXISTANT (éviter doublon)
                existing_label = None
                search_list = cluster['root_labels'] if parent_label is None else parent_label['children']
                
                for existing in search_list:
                    if existing.get('label') == item or rel_path in existing.get('files', []):
                        existing_label = existing
                        logger.debug(f"🔄 Label existant trouvé : {item}")
                        break
                    
                if existing_label:
                    # ✅ MISE À JOUR DU LABEL EXISTANT
                    if rel_path not in existing_label['files']:
                        existing_label['files'].append(rel_path)
                    existing_label['file_contents'][rel_path] = content
                    continue  # ⚠️ NE PAS CRÉER DE DOUBLON
                
                # Créer le label fichier (nouveau)
                file_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'type': 'file',
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
    
                # Ajouter au profile global
                if rel_path not in profile['files']:
                    profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
    
                # ✅ AJOUT SELON LE NIVEAU (sans doublon)
                if parent_label is None:
                    cluster['root_labels'].append(file_label)
                else:
                    parent_label['children'].append(file_label)
                    file_label['parents'] = [parent_label['uid']]
    
            # === DOSSIER ===
            elif os.path.isdir(item_path):
                # ✅ MÊME LOGIQUE : Vérifier existence avant création
                existing_folder = None
                search_list = cluster['root_labels'] if parent_label is None else parent_label['children']
                
                for existing in search_list:
                    if existing.get('label') == item:
                        existing_folder = existing
                        logger.debug(f"🔄 Dossier existant trouvé : {item}")
                        break
                    
                if existing_folder:
                    # ✅ SCANNER RÉCURSIF DANS LE DOSSIER EXISTANT
                    self._scan_directory_recursive(
                        item_path,
                        base_dir,
                        cluster,
                        profile,
                        parent_label=existing_folder,
                        level=level + 1
                    )
                    continue  # ⚠️ NE PAS CRÉER DE DOUBLON
                
                # Créer le label dossier (nouveau)
                folder_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'type': 'folder',
                    'files': [],
                    'file_contents': {},
                    'parents': [],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
    
                if parent_label is None:
                    cluster['root_labels'].append(folder_label)
                else:
                    parent_label['children'].append(folder_label)
                    folder_label['parents'] = [parent_label['uid']]
    
                # ✅ RÉCURSION
                self._scan_directory_recursive(
                    item_path,
                    base_dir,
                    cluster,
                    profile,
                    parent_label=folder_label,
                    level=level + 1
                )

    def _read_file_safe(self, file_path):
        """
        ✅ Lit un fichier de manière sécurisée avec gestion d'erreurs
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _on_upload_local_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet local")
        if directory:
            scanned_data = self._scan_project_directory(directory)
            project_name = scanned_data['name']
            self.project_profiles[project_name] = json.loads(json.dumps(scanned_data))
            self._update_project_combo()
            self.project_combo.setCurrentText(project_name)
            self._on_project_selected(self.project_combo.currentIndex())
            logger.info(f"Upload local complété pour: {directory}")

    def _on_add_new_project(self):
        """Crée un nouveau projet vide."""
        dialog = AddEditItemDialog("Nouveau Projet", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                project_name = data["name"]
                self.project_profiles[project_name] = {
                    'name': project_name,
                    'description': data["description"],
                    'files': [],
                    'file_contents': {},
                    'turing_ontology': {
                        'clusters_detailed': []
                    },
                    'pending_relations': {}
                }
                self._update_project_combo()
                self.project_combo.setCurrentText(project_name)
                self._on_project_selected(self.project_combo.currentIndex())
                logger.info(f"Nouveau projet créé : {project_name}")

    def _on_delete_project(self):
        """Suppression complète d'un projet depuis l'UI, Dgraph et SQLite."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        project_name = self.project_combo.currentText()
        uid = self.current_project_profile_data.get('uid') if self.current_project_profile_data else None

        if not uid:
            logger.warning(f"Aucun UID trouvé pour le projet {project_name}")
            QtWidgets.QMessageBox.warning(self, "Erreur", f"UID manquant pour '{project_name}'.")
            return

        # Confirmation utilisateur
        reply = QtWidgets.QMessageBox.question(
            self,
            "Suppression du projet",
            f"Voulez-vous vraiment supprimer le projet '{project_name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            uids_to_delete = self._collect_uids_to_delete(uid)
            if not uids_to_delete:
                logger.warning("Aucun UID à supprimer.")
                return

            # Supprimer de Dgraph si disponible
            dgraph_deleted = True
            if self.dgraph_connector.client:
                dgraph_deleted = self._collect_and_delete_uids(uids_to_delete, project_name)

            # Supprimer de SQLite via CRUD
            sqlite_deleted = self.project_storage_manager._delete_project_from_sqlite(uid)

            if dgraph_deleted and sqlite_deleted:
                logger.info(f"Supprimé de Dgraph et SQLite : {project_name}")

                # Supprimer du cache local
                if project_name in self.project_profiles:
                    del self.project_profiles[project_name]
                self._update_project_combo()  # Refresh la combo

                # Reset UI
                self._reset_ui()
                self.current_project_name = None

                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé.")
            else:
                QtWidgets.QMessageBox.warning(self, "Partiel", f"Supprimé de {'Dgraph et ' if dgraph_deleted else ''}SQLite, mais échec sur {'Dgraph' if not dgraph_deleted else 'SQLite'}.")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression : {e}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur : {str(e)}")

    def _collect_uids_to_delete(self, uid):
        """
        ✅ Collecte récursivement tous les UIDs à supprimer liés à un workspace.
        VERSION CORRIGÉE : Sans @recurse
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph client non initialisé.")
            return []
    
        uids_to_delete = set()
    
        # Requête EXPLICITE sans @recurse
        gc_query = f"""
        {{
          workspace(func: uid({uid})) {{
            uid
            clusterManagement {{
              uid
              clusters {{
                uid
                
                # Labels niveau 0
                root_labels: ~clusters @filter(eq(level, 0)) {{
                  uid
                  
                  # Classes
                  classes {{
                    uid
                    methods {{
                      uid
                    }}
                  }}
                  
                  # Fonctions
                  functions {{
                    uid
                  }}
                  
                  # Variables
                  variables {{
                    uid
                  }}
                  
                  # Relations sortantes
                  relations {{
                    uid
                  }}
                  
                  # Relations entrantes
                  ~target {{
                    uid
                  }}
                  
                  # Enfants niveau 1
                  children: ~parents @filter(eq(level, 1)) {{
                    uid
                    
                    classes {{
                      uid
                      methods {{
                        uid
                      }}
                    }}
                    
                    functions {{
                      uid
                    }}
                    
                    variables {{
                      uid
                    }}
                    
                    relations {{
                      uid
                    }}
                    
                    ~target {{
                      uid
                    }}
                    
                    # Enfants niveau 2
                    children: ~parents @filter(eq(level, 2)) {{
                      uid
                      
                      classes {{
                        uid
                      }}
                      
                      functions {{
                        uid
                      }}
                      
                      variables {{
                        uid
                      }}
                      
                      relations {{
                        uid
                      }}
                      
                      ~target {{
                        uid
                      }}
                      
                      # Enfants niveau 3
                      children: ~parents @filter(eq(level, 3)) {{
                        uid
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
    
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp_gc = txn.query(gc_query)
            txn.discard()
    
            data_gc = self.dgraph_connector._parse_response(resp_gc)
            
            def collect_recursive(node):
                """Collecte récursivement les UIDs"""
                if 'uid' in node:
                    uids_to_delete.add(node['uid'])
                
                # Parcourir tous les champs possibles
                for key, value in node.items():
                    if key == 'uid':
                        continue
                    
                    if isinstance(value, dict):
                        collect_recursive(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                collect_recursive(item)
            
            # Collecter depuis la racine
            for ws in data_gc.get('workspace', []):
                collect_recursive(ws)
    
            logger.info(f"✅ {len(uids_to_delete)} UID(s) collecté(s) pour suppression.")
            return list(uids_to_delete)
    
        except Exception as e:
            logger.error(f"❌ Erreur lors de la collecte des UID à supprimer : {e}")
            import traceback
            traceback.print_exc()
            return []

    def _collect_and_delete_uids(self, uids, project_name=None):
        """Supprime les UIDs collectés via mutation DELETE + vérif post-suppression dynamique (non-bloquante)."""
        if not uids or not self.dgraph_connector.client:
            return False

        txn = self.dgraph_connector.client.txn()
        committed = False
        try:
            del_objs = [{"uid": uid} for uid in uids]
            assigned = txn.mutate(del_obj=del_objs)
            txn.commit()
            committed = True
            logger.info(f"Supprimés {len(uids)} nœuds avec succès.")

            # Vérification optionnelle : Dynamique sur le nom du projet
            if project_name:
                try:
                    # Échappement basique pour le regexp (ajustez si noms complexes)
                    escaped_name = project_name.replace('/', '\\/').replace('\\', '\\\\')
                    verify_query = f"""
                    {{
                      q(func: has(name)) @filter(regexp(name, /.*{escaped_name}.*/i)) {{
                        uid
                      }}
                    }}
                    """
                    txn_verify = self.dgraph_connector.client.txn(read_only=True)
                    resp_verify = txn_verify.query(verify_query)
                    txn_verify.discard()
                    data_verify = self.dgraph_connector._parse_response(resp_verify)
                    remaining = len(data_verify.get('q', []))
                    if remaining > 0:
                        logger.warning(f"ATTENTION : {remaining} résidus pour '{project_name}' encore présents après suppression. Relance manuelle recommandée.")
                    else:
                        logger.info(f"Vérification OK : Aucune résidu pour '{project_name}' trouvé.")
                except Exception as ve:
                    logger.warning(f"Vérification post-suppression pour '{project_name}' échouée (non critique) : {ve}. La suppression principale a réussi.")

            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression principale : {e}")
            return False
        finally:
            if not committed:
                txn.discard()

    def _reset_ui(self):
        """Reset l'UI."""
        self.current_project_name = None

        # Appel AVANT le reset des données pour éviter AttributeError
        self._refresh_cluster_list()

        # Maintenant safe de set à None
        self.current_project_profile_data = None
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self._reset_hierarchy_ui()
        self.pending_relations.clear()
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)
        self._update_button_states()

        # Log pour debug
        logger.info("UI reset complété.")

    def _on_save_project(self):
        """Sauvegarde le profil local."""
        if not self.current_project_name:
            return
        self.current_project_profile_data['name'] = self.project_name_edit.text().strip()
        self.current_project_profile_data['description'] = self.project_description_edit.toPlainText().strip()
        self.current_project_profile_data['pending_relations'] = dict(self.pending_relations)
        self.project_profiles[self.current_project_name] = json.loads(json.dumps(self.current_project_profile_data))
        self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
        logger.info(f"Profil sauvegardé : {self.current_project_name}")

    def _on_export_profile(self):
        """Exporte le profil en JSON."""
        if not self.current_project_name:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Profil", f"{self.current_project_name}.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.current_project_profile_data, f, indent=4)
            logger.info(f"Profil exporté : {file_path}")

    def is_configured(self):
        """Vérifie si la config est complète."""
        return (self.current_project_profile_data and
                self.project_name_edit.text().strip() and
                len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])) > 0)

    def _process_hierarchy_recursive(self, node_data, parent_mutation, cluster_uid, 
                                 mutations, label_uids, level):
        """
        Traite récursivement la hiérarchie en créant les mutations.
        Utilise le prédicat 'parents' sur l'enfant pour lier au parent (reverse ~parents).
        """
        children_list = node_data.get('children', [])

        if not children_list:
            return

        parent_uid = parent_mutation["uid"]

        for child_data in children_list:
            # Créer la mutation pour cet enfant
            child_mutation = self.dgraph_manager._create_label_mutation(
                child_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
            mutations.append(child_mutation)

            # Enregistrer l'UID
            label_uids[child_data['uid']] = child_mutation["uid"]

            # Lier au parent via 'parents' sur l'enfant
            if "parents" not in child_mutation:
                child_mutation["parents"] = []
            child_mutation["parents"].append({"uid": parent_uid})

            # Définir le parentId (string)
            child_mutation["parentId"] = node_data.get('uid', '')

            # Traiter récursivement les enfants de cet enfant
            self._process_hierarchy_recursive(
                child_data,
                child_mutation,
                cluster_uid,
                mutations,
                label_uids,
                level + 1
            )

    def _update_button_states(self):
        """Met à jour l'état des boutons en fonction de la sélection."""
        has_project = bool(self.current_project_name)
        self.delete_project_button.setEnabled(has_project)
        self.save_button.setEnabled(has_project)
        self.export_profile_button.setEnabled(has_project)
    
        has_cluster = bool(self.current_cluster_data)
        self.add_root_button.setEnabled(has_cluster)
        self.edit_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
        self.remove_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
    
        has_root = bool(self.current_root_data)
        self.add_level1_button.setEnabled(has_root)
        self.edit_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.remove_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
    
        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(has_level1)
        self.edit_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(self.child_list_widget.currentRow() != -1)

        # Boutons relations
        has_source = bool(self.current_selected_label_uid)
        self.global_relations_config.add_button.setEnabled(has_source and len(self.label_uid_to_info) > 1)
        has_rel_selected = self.global_relations_config.relations_list.currentRow() != -1
        self.global_relations_config.edit_button.setEnabled(has_rel_selected)
        self.global_relations_config.remove_button.setEnabled(has_rel_selected)

    def _on_browse_project(self):
        """Version avec résolution complète des appels."""
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné")
            return

        project_name = self.current_project_profile_data.get("name", "Projet inconnu")
        files = self.current_project_profile_data.get("files", [])
        file_contents = self.current_project_profile_data.get("file_contents", {})

        if not files:
            QtWidgets.QMessageBox.warning(
                self, 
                "Aucun fichier trouvé", 
                f"Aucun fichier enregistré pour le projet '{project_name}'."
            )
            return

        logger.info(f"🔍 Analyse du projet '{project_name}'...")

        # Créer dialogue de progression
        progress = ModernProgressDialog(
            title=f"Analyse du projet : {project_name}",
            parent=self,
            show_log=True,
            cancelable=True
        )
        progress.set_title(f"📊 Scan du projet {project_name}")
        progress.set_status(f"Analyse de {len(files)} fichiers...")
        progress.set_progress(0, len(files))
        progress.show()

        self.parsed_relations_cache = {}
        files_processed = 0

        try:
            # ✅ ÉTAPE 1 : Extraction classique (classes, fonctions, variables)
            for i, file_path in enumerate(files, 1):
                progress.set_progress(i, len(files))
                progress.set_status(f"Traitement du fichier {i}/{len(files)}")
                progress.set_details(f"📄 {os.path.basename(file_path)}")
                progress.add_log(f"[{i}/{len(files)}] Traitement: {file_path}")

                QtWidgets.QApplication.processEvents()

                if progress.is_cancelled:
                    progress.add_log("❌ Opération annulée par l'utilisateur")
                    logger.warning("Scan annulé par l'utilisateur")
                    progress.reject()
                    return

                content = file_contents.get(file_path, "")

                if not content:
                    progress.add_log(f"   ⚠️ Contenu vide, skip")
                    continue
                
                # Parser les relations
                parsed_rels = self.dependency_parser.parse_content(content, file_path)

                if parsed_rels:
                    total_rels = sum(len(v) for v in parsed_rels.values())
                    progress.add_log(f"   ✅ {total_rels} relations détectées")
                    self.parsed_relations_cache[file_path] = parsed_rels

                # Extraire classes/fonctions/variables avec code source
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)

                # ✅ Extraire le code source
                for cls in classes:
                    cls['codeContent'] = self._extract_class_code(content, cls)
                    for method in cls.get('methods', []):
                        method['codeContent'] = self._extract_method_code(content, method)

                for func in functions:
                    func['codeContent'] = self._extract_function_code(content, func)

                progress.add_log(
                    f"   📦 Extraits: {len(classes)} classes, "
                    f"{len(functions)} fonctions, {len(variables)} variables"
                )

                # Trouver le label correspondant
                target_label = self._find_label_by_file_path(file_path)

                if target_label:
                    # Stocker le dict relations
                    target_label['relations'] = parsed_rels

                    # Intégrer dans outgoing_relations
                    if parsed_rels:
                        self._integrate_parsed_relations_to_label(target_label, parsed_rels, file_path)

                    # Stocker les éléments
                    target_label['classes'] = classes
                    target_label['functions'] = functions
                    target_label['variables'] = variables

                    # Créer les enfants
                    for cls in classes:
                        cls['file'] = file_path
                        if 'uid' not in cls:
                            cls['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(cls, 'class')
                        target_label.setdefault('children', []).append(child)

                    for func in functions:
                        func['file'] = file_path
                        if 'uid' not in func:
                            func['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(func, 'function')
                        target_label.setdefault('children', []).append(child)

                    for var in variables:
                        var['file'] = file_path
                        if 'uid' not in var:
                            var['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(var, 'variable')
                        target_label.setdefault('children', []).append(child)

                    files_processed += 1

            # ✅ ÉTAPE 2 : RÉSOLUTION COMPLÈTE DES APPELS (NOUVEAU)
            progress.set_indeterminate(True)
            progress.set_status("🔗 Résolution complète des appels...")
            progress.add_log("\n🔗 Initialisation CompleteCallResolver...")
            QtWidgets.QApplication.processEvents()

            # Initialiser le resolver avec la structure du projet
            self.call_resolver = CompleteCallResolver(self.current_project_profile_data)

            # Résoudre TOUS les appels
            progress.add_log("📞 Résolution de tous les appels du projet...")
            resolved_calls = self.call_resolver.resolve_all_calls()

            # Intégrer les appels résolus
            calls_integrated = self._integrate_resolved_calls_to_structure(resolved_calls)
            progress.add_log(f"   ✅ {calls_integrated} appels résolus et intégrés")

            progress.set_indeterminate(False)

            # Construction du graphe
            progress.set_status("🔗 Construction du graphe de relations...")
            progress.add_log("\n🔗 Construction du graphe de relations...")
            QtWidgets.QApplication.processEvents()

            self._build_complete_relations_graph()

            # Validation
            progress.set_status("🔍 Validation des relations...")
            progress.add_log("🔍 Validation des relations parsées...")
            validation_stats = self._validate_parsed_relations()

            # Rafraîchir l'UI
            progress.set_status("♻️ Rafraîchissement de l'interface...")
            progress.add_log("♻️ Rafraîchissement de l'interface...")
            self._collect_all_labels()
            self._refresh_cluster_list()

            # Sauvegarde
            progress.set_status("💾 Sauvegarde dans SQLite et Dgraph...")
            progress.add_log("\n💾 Démarrage de la sauvegarde...")

            save_success = self._save_scan_results_to_storage()

            if save_success:
                progress.finish(
                    success=True,
                    message=f"✅ {files_processed} fichiers traités, "
                            f"{validation_stats['total_parsed_in_dict']} relations détectées, "
                            f"{calls_integrated} appels résolus"
                )
                progress.add_log("\n✅ Sauvegarde complète réussie!")
            else:
                progress.finish(
                    success=False,
                    message="Le scan a réussi mais la sauvegarde a échoué"
                )
                progress.add_log("\n❌ Échec de la sauvegarde")

        except Exception as e:
            logger.error(f"Erreur lors du scan: {str(e)}")
            import traceback
            traceback.print_exc()

            progress.finish(
                success=False,
                message=f"Erreur : {str(e)}"
            )
            progress.add_log(f"\n❌ ERREUR: {str(e)}")

    def _integrate_resolved_calls_to_structure(self, resolved_calls: Dict[str, List[Dict]]) -> int:
        count = 0

        if not resolved_calls:
            logger.warning("⚠️ Aucun appel résolu à intégrer")
            return 0

        # Index pour recherche rapide
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)
        node_by_uid = {n['uid']: n for n in all_nodes if 'uid' in n}

        # Index par nom + fichier
        node_by_name_file = {}
        for node in all_nodes:
            if node.get('type') in ['function', 'method', 'class']:
                key = (node.get('name'), node.get('file') or self._get_parent_file_path_simple(node))
                node_by_name_file[key] = node

        for file_path, calls in resolved_calls.items():
            for call in calls:
                # Skip non résolus
                if not call.get('resolved'):
                    continue
                
                source_uid = call.get('source_uid')
                target_uid = call.get('target_uid')
                target_file = call.get('target_file')
                target_name = call.get('target_name')
                call_type = call.get('call_type')
                line = call.get('line', 0)
                scope = call.get('scope', 'unknown')

                # Trouver le nœud source
                source_node = node_by_uid.get(source_uid)
                if not source_node:
                    source_key = (call.get('source_func'), file_path)
                    source_node = node_by_name_file.get(source_key)

                # Trouver le nœud cible
                target_node = node_by_uid.get(target_uid)
                if not target_node and target_file:
                    target_key = (target_name, target_file)
                    target_node = node_by_name_file.get(target_key)

                if source_node and target_node:
                    # Déterminer le type de relation
                    relation_type = self._map_call_type_to_relation(call_type)

                    # Ajouter la relation sortante
                    outgoing = {
                        'target_uid': target_node['uid'],
                        'target_name': target_name,
                        'relation_type': relation_type,
                        'category': 'parsed',
                        'line': line,
                        'scope': scope,
                        'call_type': call_type,
                        'full_call': call.get('full_call', ''),
                        'intra_file': call.get('scope') in ['same_file', 'same_class']
                    }

                    if outgoing not in source_node.setdefault('outgoing_relations', []):
                        source_node['outgoing_relations'].append(outgoing)
                        count += 1

                    # Ajouter la relation entrante
                    incoming = {
                        'source_uid': source_node['uid'],
                        'source_name': source_node.get('label', source_node.get('name', 'Unknown')),
                        'relation_type': relation_type,
                        'category': 'parsed',
                        'line': line,
                        'scope': scope
                    }

                    if incoming not in target_node.setdefault('incoming_relations', []):
                        target_node['incoming_relations'].append(incoming)
                else:
                    logger.debug(
                        f"Appel non lié : {call.get('source_func')} -> {target_name} "
                        f"(source={source_node is not None}, target={target_node is not None})"
                    )

        logger.info(f"✅ {count} appels intégrés dans la structure")
        return count
    
    def _map_call_type_to_relation(self, call_type: str) -> str:
        # Mapping des types d'appels vers relations
        mapping = {
            'function_call': 'calls',
            'method_call': 'calls',
            'constructor': 'instantiates',
            'super_call': 'calls_super',
            'static_call': 'calls_static',
            'async_call': 'calls_async',
            'callback': 'uses_callback',
            'decorator': 'decorated_by',
            'generator': 'yields_from',
            'comprehension': 'uses_in_comprehension',

            # Fallback pour types non reconnus
            'call': 'calls',
            'invoke': 'calls',
            'execute': 'calls'
        }

        # Retourner le type mappé ou 'calls' par défaut
        return mapping.get(call_type, 'calls')
    
    def _get_parent_file_path_simple(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Remonte la hiérarchie pour trouver le fichier parent d'un nœud.
        Version simplifiée pour éviter les dépendances circulaires.

        Args:
            node: Nœud dont on cherche le fichier parent

        Returns:
            Chemin du fichier parent ou None
        """
        # Vérifier si le nœud a déjà un fichier
        if node.get('file'):
            return node['file']

        # Vérifier dans les fichiers du nœud
        files = node.get('files', [])
        if files:
            return files[0]

        # Chercher dans label_uid_to_info
        node_uid = node.get('uid')
        if node_uid and node_uid in self.label_uid_to_info:
            info = self.label_uid_to_info[node_uid]
            if info.get('file'):
                return info['file']

        return None

    def _extract_class_code(self, content: str, cls: Dict) -> str:
        """
        ✅ Extrait le code source complet d'une classe
        """
        try:
            lines = content.split('\n')
            start_line = cls.get('line', 1) - 1  # Index 0
            
            if start_line >= len(lines):
                return ""
            
            # Trouver la fin de la classe (indentation)
            base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            end_line = start_line + 1
            
            while end_line < len(lines):
                line = lines[end_line]
                
                # Ligne vide ou commentaire : continuer
                if not line.strip() or line.strip().startswith('#'):
                    end_line += 1
                    continue
                
                # Si indentation <= base, c'est la fin de la classe
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent:
                    break
                
                end_line += 1
            
            # Extraire le code
            code_lines = lines[start_line:end_line]
            return '\n'.join(code_lines)
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction code classe {cls.get('name')}: {e}")
            return ""

    def _extract_method_code(self, content: str, method: Dict) -> str:
        """
        ✅ Extrait le code source d'une méthode
        """
        try:
            lines = content.split('\n')
            start_line = method.get('line', 1) - 1

            if start_line >= len(lines):
                return ""

            # Trouver la fin de la méthode
            base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            end_line = start_line + 1

            while end_line < len(lines):
                line = lines[end_line]

                if not line.strip() or line.strip().startswith('#'):
                    end_line += 1
                    continue
                
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent:
                    break
                
                end_line += 1

            code_lines = lines[start_line:end_line]
            return '\n'.join(code_lines)

        except Exception as e:
            logger.error(f"❌ Erreur extraction code méthode {method.get('name')}: {e}")
            return ""

    def _extract_function_code(self, content: str, func: Dict) -> str:
        """
        ✅ Extrait le code source d'une fonction
        """
        try:
            lines = content.split('\n')
            start_line = func.get('line', 1) - 1

            if start_line >= len(lines):
                return ""

            # Trouver la fin de la fonction
            base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            end_line = start_line + 1

            while end_line < len(lines):
                line = lines[end_line]

                if not line.strip() or line.strip().startswith('#'):
                    end_line += 1
                    continue
                
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent:
                    break
                
                end_line += 1

            code_lines = lines[start_line:end_line]
            return '\n'.join(code_lines)

        except Exception as e:
            logger.error(f"❌ Erreur extraction code fonction {func.get('name')}: {e}")
            return ""

    def _create_child_node_from_item(self, item: Dict, item_type: str) -> Dict[str, Any]:
        """
        Crée un nœud enfant à partir d'un élément extrait (classe, fonction, variable).
        
        Args:
            item: Dict de l'élément extrait
            item_type: Type ('class', 'function', 'variable')
        
        Returns:
            Dict du nœud enfant
        """
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'parents': []  # Sera mis à jour si nécessaire
        }
        
        # Ajouter à label_uid_to_info
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_name if hasattr(self, 'current_cluster_name') else 'unknown',
            'file': os.path.basename(item.get('file', ''))
        }
        
        return child

    def _get_local_to_dgraph_mapping(self):
        """Retourne {local_uuid: dgraph_hex}"""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
            self._collect_all_labels()  # Rafraîchir si besoin
        return self.local_to_dgraph

    def _get_dgraph_to_local_mapping(self):
        """Retourne {dgraph_hex: local_uuid}"""
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
            self._collect_all_labels()
        return self.dgraph_to_local

    def _load_mappings_from_dgraph(self):
        """Charge les mappings depuis Dgraph pour sync."""
        query = """
        {
          q(func: type(Node)) {
            uid
            local_id
          }
        }
        """
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self.dgraph_connector._parse_response(resp)
            for node in data.get("q", []):
                local_id = node.get('local_id')
                dgraph_uid = node['uid']
                if local_id:
                    self.local_to_dgraph[local_id] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = local_id
        except Exception as e:
            logger.error(f"Erreur chargement mappings Dgraph: {e}")

    def _load_existing_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Charge la structure existante du projet.
        """
        structure_file = os.path.join(project_path, "turing_ontology.json")
        if os.path.exists(structure_file):
            try:
                with open(structure_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement structure: {e}")
        return {"clusters_detailed": []}    
    
    def _integrate_scanned_structure(self, scanned_structure: Dict[str, Any], base_dir: str):
            """
            Intègre la structure scannée dans le projet, en calculant relations_map à l'intérieur.

            Args:
                scanned_structure: Structure scannée par le scanner
                base_dir: Répertoire de base du projet
            """
            # Calculer relations_map ici pour matcher l'appel (3 args)
            relations_map = self.project_scanner.get_relations_map(scanned_structure)

            clusters_detailed = []
            for cluster in scanned_structure.get('clusters', []):
                new_cluster = {
                    'name': cluster.get('name', 'Unknown'),
                    'path': cluster.get('path', ''),
                    'type': 'cluster',
                    'root_labels': []
                }

                # Traiter chaque fichier avec force
                all_files_in_cluster = self.project_scanner.get_all_files({'clusters': [cluster]})
                for file_info in all_files_in_cluster:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    rel_path = os.path.relpath(file_path, base_dir) if base_dir and file_path else file_path

                    # Contenu déjà lu dans _scan_file, fallback si absent
                    content = file_info.get('file_contents', {}).get(rel_path, '')
                    if not content and file_path:
                        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                        for encoding in encodings:
                            try:
                                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                                    content = f.read()
                                break
                            except (UnicodeDecodeError, IOError):
                                continue
                        else:
                            try:
                                with open(file_path, 'rb') as f:
                                    raw = f.read()
                                    content = raw.decode('utf-8', errors='replace')
                            except Exception:
                                content = ''

                    new_label = {
                        'label': file_name,
                        'id': str(uuid.uuid4()),
                        'uid': file_info.get('uid', str(uuid.uuid4())),
                        'type': 'file',
                        'description': f"Fichier: {rel_path}",
                        'category': ['file'],
                        'files': [rel_path],
                        'file_contents': {rel_path: content},
                        'children': [],
                        'parents': [],
                        'outgoing_relations': [],
                        'incoming_relations': [],
                        'classes': file_info.get('classes', []),  # Forcé depuis scan
                        'functions': file_info.get('functions', []),  # Forcé depuis scan
                        'variables': file_info.get('variables', [])  # Forcé depuis scan
                    }

                    # Ajouter le fichier au projet global
                    files_list = self.current_project_profile_data.get('files', [])
                    if rel_path not in files_list:
                        files_list.append(rel_path)
                        self.current_project_profile_data['files'] = files_list
                    file_contents = self.current_project_profile_data.get('file_contents', {})
                    file_contents[rel_path] = content
                    self.current_project_profile_data['file_contents'] = file_contents

                    # Mapper relations
                    relations = relations_map.get(file_path, {})
                    if relations:
                        for rel_type, rel_list in relations.items():
                            for rel in rel_list:
                                target = rel.get('target', '')
                                normalized_target = normalize_node_name(target)

                                if normalized_target:
                                    target_uid = self._find_label_uid_by_name(normalized_target)

                                    if target_uid:
                                        relation_entry = {
                                            'target_uid': target_uid,
                                            'relation_type': rel_type,
                                            'line': rel.get('line', 0)
                                        }
                                        new_label['outgoing_relations'].append(relation_entry)

                                        pending_rels = self.pending_relations.get(new_label['uid'], [])
                                        pending_rels.append({
                                            'target_uid': target_uid,
                                            'relation_type': rel_type
                                        })
                                        self.pending_relations[new_label['uid']] = pending_rels

                    # Ajouter enfants depuis scan (classes, functions, variables)
                    for child in file_info.get('children', []):
                        if 'uid' not in child:
                            child['uid'] = str(uuid.uuid4())
                        new_label['children'].append(child)

                    new_cluster['root_labels'].append(new_label)

                clusters_detailed.append(new_cluster)

            logger.info(f"{len(clusters_detailed)} clusters intégrés avec classes/fonctions/variables")
            turing_ontology = self.current_project_profile_data.get('turing_ontology', {})
            turing_ontology['clusters_detailed'] = clusters_detailed
            self.current_project_profile_data['turing_ontology'] = turing_ontology

    def _find_label_uid_by_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        
        normalized_search = name.lower().strip()
        
        for uid, info in self.label_uid_to_info.items():
            label_name = info.get('name', '')
            normalized_label = normalize_node_name(label_name)
            
            if normalized_label and normalized_label.lower() == normalized_search:
                return uid
        
        return None

    def _on_root_label_selected(self, current):
        if not current:
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)
        self.current_root_label_index = self.root_list_widget.row(current)

        root_labels = self.current_cluster_data.get("root_labels", [])

        if self.current_root_label_index < 0 or self.current_root_label_index >= len(root_labels):
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        self.current_root_data = root_labels[self.current_root_label_index]
        self.current_selected_label_uid = current.data(Qt.UserRole)

        # 📊 LOG: Vérifier les relations du fichier sélectionné
        file_name = self.current_root_data.get('label', 'Unknown')
        logger.info(f"📂 Sélectionné: {file_name} (type: {item_type}, UID: {self.current_selected_label_uid})")

        # Réinitialiser niveaux inférieurs
        self.current_level1_data = None
        self.current_level2_data = None
        self.child_list_widget.clear()

        # ✅ TRAITEMENT UNIFIÉ pour fichiers ET dossiers
        self._update_selected_details("Label Racine", self.current_root_data)

        # ✅ Si c'est un FICHIER : créer les children à partir des éléments de code
        if item_type == 'file':
            files = self.current_root_data.get('files', [])
            if files:
                file_path = files[0]
                content = self.current_root_data.get('file_contents', {}).get(file_path, '')

                if not content:
                    content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

                if content:
                    logger.info(f"   📄 Extraction depuis: {file_path} ({len(content)} chars)")

                    # Extraire les éléments de code
                    classes = self.dependency_parser.extract_classes(content, file_path)
                    functions = self.dependency_parser.extract_functions(content, file_path)
                    variables = self.dependency_parser.extract_variables(content, file_path)

                    logger.info(f"   ✅ Trouvés: {len(classes)} classes, {len(functions)} fonctions, {len(variables)} variables")

                    # ✅ CRÉER LES CHILDREN à partir des éléments extraits
                    children = []

                    # Ajouter les classes
                    for cls in classes:
                        if 'uid' not in cls:
                            cls['uid'] = str(uuid.uuid4())

                        child_node = {
                            'label': cls['name'],
                            'name': cls['name'],
                            'uid': cls['uid'],
                            'type': 'class',
                            'line': cls.get('line', 0),
                            'file': file_path,
                            'description': f"Class {cls['name']} at line {cls.get('line', 0)}",
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        children.append(child_node)

                    # Ajouter les fonctions
                    for func in functions:
                        if 'uid' not in func:
                            func['uid'] = str(uuid.uuid4())

                        child_node = {
                            'label': func['name'],
                            'name': func['name'],
                            'uid': func['uid'],
                            'type': func.get('type', 'function'),
                            'line': func.get('line', 0),
                            'file': file_path,
                            'description': f"Function {func['name']} at line {func.get('line', 0)}",
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        children.append(child_node)

                    # Ajouter les variables
                    for var in variables:
                        if 'uid' not in var:
                            var['uid'] = str(uuid.uuid4())

                        child_node = {
                            'label': var['name'],
                            'name': var['name'],
                            'uid': var['uid'],
                            'type': 'variable',
                            'line': var.get('line', 0),
                            'file': file_path,
                            'description': f"Variable {var['name']} at line {var.get('line', 0)}",
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        children.append(child_node)

                    # ✅ INJECTER dans current_root_data
                    self.current_root_data['children'] = children
                    self.current_root_data['classes'] = classes
                    self.current_root_data['functions'] = functions
                    self.current_root_data['variables'] = variables

                    logger.info(f"   ✅ {len(children)} children créés pour {file_name}")

                    # ✅ Afficher dans level1_list
                    self._populate_level1_list()
                else:
                    # Fichier vide
                    logger.warning(f"   ⚠️ Fichier vide: {file_path}")
                    self.level1_list_widget.clear()
                    empty_item = QListWidgetItem("(Fichier vide)")
                    empty_item.setForeground(QtGui.QColor("#95a5a6"))
                    self.level1_list_widget.addItem(empty_item)
            else:
                logger.warning(f"   ⚠️ Aucun fichier associé")
                self.level1_list_widget.clear()

        # ✅ Si c'est un DOSSIER : afficher sa hiérarchie normale
        else:
            logger.info(f"   📁 Dossier - affichage hiérarchie normale")
            self._populate_level1_list_with_root_files()

        # Mettre à jour relations
        self.global_relations_config.update_current(self.current_selected_label_uid)
        self.relations_graph.update_graph(self.current_selected_label_uid)

        self._update_button_states()

    def _populate_children_list(self, parent_data: Dict, list_widget=None):
        if list_widget is None:
            list_widget = (
                self.level1_list_widget
                if hasattr(self, 'current_root_data')
                else self.child_list_widget
            )

        list_widget.clear()
        if not parent_data:
            return

        primary_orange = '#FFD700'  # pour dossiers
        orange = '#FFD700'           # pour classes
        blue_light = '#3498db'       # methodes
        blue = '#2196F3'             # fonctions
        green = '#4CAF50'            # variables
        gray = '#7f8c8d'             # fichiers
        turquoise = '#16a085'        # autres

        for child in parent_data.get('children', []):
            child_type = child.get('type', 'child')
            label = child.get('label', child.get('name', 'Sans nom'))
            uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = uid

            # ✅ CLASSE avec icône cube (orange)
            if child_type == 'class':
                display = f"[CLASS] {label} (ligne {child.get('line', '?')})"
                item = QListWidgetItem(display)
                icon = qta.icon('fa5s.cube', color=orange)
                item.setIcon(icon)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'class')
                item.setData(Qt.UserRole + 2, child.get('file', ''))
                item.setData(Qt.UserRole + 3, child.get('line', 0))
                item.setForeground(QtGui.QColor(orange))
                item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                list_widget.addItem(item)
                continue

            # ✅ MÉTHODE avec icône cog (bleu clair)
            if child_type == 'method':
                display = f"[METH] {label} (ligne {child.get('line', '?')})"
                item = QListWidgetItem(display)
                icon = qta.icon('fa5s.cog', color=blue_light)
                item.setIcon(icon)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'method')
                item.setData(Qt.UserRole + 2, child.get('file', ''))
                item.setData(Qt.UserRole + 3, child.get('line', 0))
                item.setForeground(QtGui.QColor(blue_light))
                item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                list_widget.addItem(item)
                continue

            # ✅ FONCTION avec icône bolt (bleu)
            if child_type == 'function':
                display = f"[FUNC] {label} (ligne {child.get('line', '?')})"
                item = QListWidgetItem(display)
                icon = qta.icon('fa5s.bolt', color=blue)
                item.setIcon(icon)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'function')
                item.setData(Qt.UserRole + 2, child.get('file', ''))
                item.setData(Qt.UserRole + 3, child.get('line', 0))
                item.setForeground(QtGui.QColor(blue))
                item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                list_widget.addItem(item)
                continue

            # ✅ VARIABLE avec icône tag (vert)
            if child_type == 'variable':
                display = f"[VAR] {label} (ligne {child.get('line', '?')})"
                item = QListWidgetItem(display)
                icon = qta.icon('fa5s.tag', color=green)
                item.setIcon(icon)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'variable')
                item.setData(Qt.UserRole + 2, child.get('file', ''))
                item.setData(Qt.UserRole + 3, child.get('line', 0))
                item.setForeground(QtGui.QColor(green))
                item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                list_widget.addItem(item)
                continue

            # ✅ FICHIERS ET DOSSIERS (détection par extension)
            is_file = (
                child_type == 'file' or 
                label.endswith((
                    '.ts', '.py', '.js', '.java', '.cpp', '.json', '.net',
                    '.c', '.h', '.tsx', '.jsx', '.cs', '.php', '.rb', '.go',
                    '.html', '.css', '.xml', '.txt', '.md', '.yaml', '.yml'
                ))
            )

            if is_file:
                icon = qta.icon('fa5s.file-code', color=gray)
                display = label
                display_type = 'file'
                color = QtGui.QColor(gray)
            elif child_type in ['folder', 'directory']:
                icon = qta.icon('fa5s.folder', color=primary_orange)
                display = label
                display_type = 'folder'
                color = QtGui.QColor(primary_orange)
            else:
                icon = qta.icon('fa5s.question-circle', color=turquoise)
                display = label
                display_type = child_type
                color = QtGui.QColor(turquoise)

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, uid)
            item.setData(Qt.UserRole + 1, display_type)
            item.setForeground(color)
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        self._update_button_states()

    def _populate_level1_with_file_elements(self, file_data: Dict):
        self.level1_list_widget.clear()

        if not file_data:
            return

        # Récupérer le contenu du fichier
        files = file_data.get('files', [])
        if not files:
            self.level1_list_widget.addItem(QListWidgetItem("(Aucun contenu)"))
            return

        file_path = files[0]  # Fichier principal
        content = file_data.get('file_contents', {}).get(file_path, '')

        if not content:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

        if not content:
            self.level1_list_widget.addItem(QListWidgetItem("(Contenu vide)"))
            return

        # Extraire les éléments de code
        classes = self.dependency_parser.extract_classes(content, file_path)
        functions = self.dependency_parser.extract_functions(content, file_path)
        variables = self.dependency_parser.extract_variables(content, file_path)

        # Couleurs (identiques à celles du style précédent)
        primary = '#A23B2D'
        dark_gray = '#424242'
        medium_gray = '#666666'
        strong_gray = '#555555'

        def modulate_color(base_color: str, lvl: int = 1):
            if lvl > 1:
                if base_color == primary:
                    return '#D35A4A'
                elif base_color == dark_gray:
                    return '#5A5A5A'
                elif base_color == medium_gray:
                    return '#888888'
            return base_color

        # On suppose un niveau 1 ici (pas d'indication différente)
        modulated_primary = modulate_color(primary, 1)

        # === Afficher les CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            icon = qta.icon('fa5s.cube', color=strong_gray)
            display = f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})"

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, cls.get('line', 0))
            item.setForeground(QtGui.QColor(strong_gray))
            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)
            self.level1_list_widget.addItem(item)

        # === Afficher les FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            icon = qta.icon('fa5s.cog', color=modulated_primary)
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"
            display = f"{prefix} {func['name']} (ligne {func.get('line', '?')})"

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, func.get('line', 0))
            item.setForeground(QtGui.QColor(modulated_primary))
            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)
            self.level1_list_widget.addItem(item)

        # === Afficher les VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            icon = qta.icon('fa5s.tag', color=medium_gray)
            display = f"[VAR] {var['name']} (ligne {var.get('line', '?')})"

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, var.get('line', 0))
            item.setForeground(QtGui.QColor(medium_gray))
            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)
            self.level1_list_widget.addItem(item)

        # Message si aucun élément trouvé
        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément de code trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            font = QtGui.QFont()
            font.setPointSize(7)
            empty_item.setFont(font)
            self.level1_list_widget.addItem(empty_item)

        self._update_button_states()

    def _populate_root_list(self):
        """Affiche les root labels - icône dossier uniquement."""
        self.root_list_widget.clear()

        if not self.current_cluster_data:
            return

        folder_color = '#FFD700'  # Bleu pour TOUS les dossiers
        file_color = '#7f8c8d'    # Gris pour TOUS les fichiers

        for root in self.current_cluster_data.get("root_labels", []):
            root_type = root.get('type', 'folder')
            root_label = root.get('label', root.get('name', 'Sans nom'))

            # Détection fichier vs dossier
            is_file = (
                root_type == 'file' or 
                root_label.endswith((
                    '.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h'
                ))
            )

            if is_file:
                icon = qta.icon('fa5s.file-code', color=file_color)
                display = root_label
                item_type = 'file'
                color = QtGui.QColor(file_color)
            else:
                # ✅ COULEUR HOMOGÈNE pour les dossiers
                icon = qta.icon('fa5s.folder', color=folder_color)
                display = root_label
                item_type = 'root_label'
                color = QtGui.QColor(folder_color)

            root_item = QListWidgetItem(display)
            root_item.setIcon(icon)
            root_item.setData(Qt.UserRole, root.get("uid"))
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)

        self._update_button_states()

    def _get_node_icon(self, node_type: str) -> str:
        if node_type in ['folder', 'directory']:
            return '📁'
        # Pour file, class, function, variable, method : pas d'icône
        return ''

    def _get_relation_icon(self, rel_type: str) -> str:
        """
        Retourne une icône selon le type de relation.
        
        Args:
            rel_type: Type de relation
        
        Returns:
            Icône Unicode
        """
        icons = {
            'import': '📦',
            'from_import': '📦',
            'require': '📦',
            'include': '📦',
            'heritage': '🔗',
            'extends': '🔗',
            'implements': '🔗',
            'call': '📞',
            'function_call': '📞',
            'method_call': '📞',
            'uses': '🔹',  # NOUVEAU pour variables
            'variable_use': '🔹'
        }
        
        return icons.get(rel_type, '🔸')

    def _format_child_details(self, child: Dict[str, Any]) -> str:
        """
        Formate les détails d'un enfant (classe, fonction, variable) pour affichage.
        """
        child_type = child.get('type', 'unknown')
        details = ""

        if child_type == 'class':
            details = f"=== CLASSE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            bases = child.get('bases', [])
            if bases:
                details += f"\nHérite de:\n"
                for base in bases:
                    details += f"  - {base}\n"

            methods = child.get('children', [])
            if methods:
                details += f"\nMéthodes ({len(methods)}):\n"
                for method in methods[:10]:
                    details += f"  - {method.get('name', 'N/A')} (ligne {method.get('line', '?')})\n"
                if len(methods) > 10:
                    details += f"  ... et {len(methods) - 10} autres\n"

        elif child_type in ['function', 'method']:
            details = f"=== {'MÉTHODE' if child_type == 'method' else 'FONCTION'} ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('type', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            params = child.get('params', [])
            if params:
                details += f"\nParamètres ({len(params)}):\n"
                for param in params:
                    param_name = param.get('name', 'param')
                    param_type = param.get('type', 'unknown')
                    details += f"  - {param_name}: {param_type}\n"

            returns = child.get('returns', {})
            if returns:
                details += f"\nRetour: {returns.get('type', 'N/A')}\n"

            calls = child.get('outgoing_relations', [])
            if calls:
                details += f"\nAppelle ({len(calls)}):\n"
                for call in calls[:5]:
                    details += f"  - {call}\n"
                if len(calls) > 5:
                    details += f"  ... et {len(calls) - 5} autres\n"

        elif child_type == 'variable':
            details = f"=== VARIABLE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('var_type', 'N/A')}\n"
            details += f"Scope: {child.get('scope', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

        return details

    def _get_child_index_by_uid(self, uid: str) -> int:
        """
        Trouve l'index d'un enfant par son UID.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Index ou -1
        """
        if not self.current_root_data:
            return -1
        
        for i, child in enumerate(self.current_root_data.get('children', [])):
            if child.get('uid') == uid:
                return i
        
        return -1

    def _find_label_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un label par son UID dans toute la hiérarchie.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Dictionnaire du label ou None
        """
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)

        return next((n for n in all_nodes if n.get('uid') == uid), None)

    def _find_child_by_uid(self, parent: Dict, uid: str) -> Optional[Dict]:
        if not parent or not isinstance(parent, dict):
            logger.warning(f"⚠️ Parent invalide dans _find_child_by_uid: {type(parent)}")
            return None

        # Chercher dans les enfants directs
        for child in parent.get("children", []):
            if child.get('uid') == uid or child.get('id') == uid:
                return child

            # Chercher récursivement dans les sous-dossiers
            result = self._find_child_by_uid(child, uid)
            if result:
                return result

        return None

    def _format_label_details(self, label: Dict[str, Any]) -> str:
        """
        Formate les détails d'un label pour affichage, incluant classes, fonctions et variables.
        
        Args:
            label: Dictionnaire du label
        
        Returns:
            String formaté
        """
        details = f"Nom: {label.get('label', 'N/A')}\n"
        details += f"UID: {label.get('uid', 'N/A')}\n"
        details += f"Type: {label.get('type', 'N/A')}\n"  # NOUVEAU
        details += f"Description: {label.get('description', 'N/A')}\n\n"
        
        files = label.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:5]:
                details += f"  - {f}\n"
            if len(files) > 5:
                details += f"  ... et {len(files) - 5} autres\n"
        
        # Ajouter classes si présentes
        classes = label.get('classes', [])
        if classes:
            details += f"\nClasses ({len(classes)}):\n"
            for cls in classes[:5]:
                details += f"  - {cls['name']} (ligne {cls['line']})\n"
            if len(classes) > 5:
                details += f"  ... et {len(classes) - 5} autres\n"
        
        # Ajouter fonctions si présentes
        functions = label.get('functions', [])
        if functions:
            details += f"\nFonctions/Méthodes ({len(functions)}):\n"
            for func in functions[:5]:
                details += f"  - {func['name']} ({func['type']}, ligne {func['line']})\n"
            if len(functions) > 5:
                details += f"  ... et {len(functions) - 5} autres\n"

        # NOUVEAU : Ajouter variables si présentes
        variables = label.get('variables', [])
        if variables:
            details += f"\nVariables ({len(variables)}):\n"
            for var in variables[:5]:
                details += f"  - {var['name']} ({var['type']}, ligne {var['line']})\n"
            if len(variables) > 5:
                details += f"  ... et {len(variables) - 5} autres\n"
        
        return details

    def _on_double_click_label(self, item):
        """
        Double-clic sur un label - Affiche le contenu du fichier avec snippet highlighté.
        MODIFIÉ: Centré sur ligne pour classes/foncs/vars.
        """
        if not item:
            return
        
        uid = item.data(Qt.UserRole)
        label = self._find_label_by_uid(uid)
        
        if not label:
            return
        
        files = label.get('files', [])
        if not files:
            QtWidgets.QMessageBox.information(
                self,
                "Aucun fichier",
                "Ce label n'a pas de fichier associé."
            )
            return
        
        # Si plusieurs fichiers, demander lequel afficher
        file_to_show = files[0]
        if len(files) > 1:
            file_to_show, ok = QInputDialog.getItem(
                self,
                "Sélectionner un fichier",
                "Fichier à afficher:",
                files,
                0,
                False
            )
            if not ok:
                return
        
        # Récupérer le contenu
        content = label.get('file_contents', {}).get(file_to_show, '')
        
        if not content:
            QtWidgets.QMessageBox.warning(
                self,
                "Contenu vide",
                f"Le fichier {file_to_show} est vide."
            )
            return
        
        # Afficher dans une fenêtre de dialogue avec highlight
        self.code_dialogs._show_file_content_dialog(file_to_show, content, label)

    def _read_file_content(self, file_path: str) -> str:
        """Lit un fichier en UTF-8 avec gestion d’erreur."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _add_child_to_level1_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste niveau 1, récursivement pour les sous-dossiers.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant SANS icône
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_level1_list(grandchild, list_widget, indent + "  ")

    def _populate_cluster_list(self):
        """
        CORRIGÉ : Affiche UNIQUEMENT les clusters (pas leurs fichiers).
        """
        self.cluster_list_widget.clear()

        if not self.current_project_profile_data:
            return

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])

        for cluster in clusters:
            cluster_item = QListWidgetItem(f"📁 {cluster['name']}")
            cluster_item.setData(Qt.UserRole, cluster['uid'])
            cluster_item.setData(Qt.UserRole + 1, 'cluster')
            cluster_item.setForeground(QtGui.QColor("#2c3e50"))
            self.cluster_list_widget.addItem(cluster_item)

    def _populate_root_list_with_cluster_files(self):   
        """Affiche dans root_list : icône dossiers et fichiers avec icônes et couleurs précédentes."""
        self.root_list_widget.clear()

        if not self.current_cluster_data:
            return

        folder_color = '#FFD700'  # orange comme avant
        file_color = '#7f8c8d'    # gris comme avant

        for root in self.current_cluster_data.get("root_labels", []):
            root_label = root.get('label', root.get('name', 'Sans nom'))
            root_uid = root.get("uid")

            root_type = root.get('type', 'folder')
            is_file = (
                root_type == 'file' or 
                root_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h', '.tsx', '.jsx'))
            )

            if is_file:
                icon = qta.icon('fa5s.file-code', color=file_color)
                display = root_label
                item_type = 'file'
                color = QtGui.QColor(file_color)
            else:
                icon = qta.icon('fa5s.folder', color=folder_color)
                display = root_label
                item_type = 'root_label'
                color = QtGui.QColor(folder_color)

            root_item = QListWidgetItem(display)
            root_item.setIcon(icon)
            root_item.setData(Qt.UserRole, root_uid)
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)

        self._update_button_states()

    def _populate_level1_list_with_root_files(self):
        """Affiche fichiers (avec icône) et dossiers (avec icône)."""
        self.level1_list_widget.clear()

        if not self.current_root_data:
            return

        # ✅ COULEURS HOMOGÈNES
        folder_color = '#FFD700'   # Bleu uniforme pour dossiers
        file_color = '#7f8c8d'     # Gris uniforme pour fichiers

        # 1. Fichiers : AVEC icône fichier
        for file_path in self.current_root_data.get('files', []):
            file_name = os.path.basename(file_path)
            item = QListWidgetItem(file_name)
            icon = qta.icon('fa5s.file-code', color=file_color)
            item.setIcon(icon)
            item.setData(Qt.UserRole, f"root_file_{file_path}")
            item.setData(Qt.UserRole + 1, 'root_file')
            item.setData(Qt.UserRole + 2, file_path)
            item.setForeground(QtGui.QColor(file_color))
            self.level1_list_widget.addItem(item)

        # 2. Children (fichiers et dossiers)
        for child in self.current_root_data.get("children", []):
            child_type = child.get('type', 'folder')

            # Skip éléments de code
            if child_type in ['class', 'function', 'variable', 'method']:
                continue
            
            label = child.get('label', child.get('name', 'Sans nom'))

            is_file = (
                child_type == 'file' or 
                label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net'))
            )

            if is_file:
                icon = qta.icon('fa5s.file-code', color=file_color)
                display = label
                color = QtGui.QColor(file_color)
            elif child_type in ['folder', 'directory']:
                # ✅ COULEUR HOMOGÈNE
                icon = qta.icon('fa5s.folder', color=folder_color)
                display = label
                color = QtGui.QColor(folder_color)
            else:
                icon = qta.icon('fa5s.question-circle', color="#16a085")
                display = label
                color = QtGui.QColor("#16a085")

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, child.get("uid"))
            item.setData(Qt.UserRole + 1, child_type)
            item.setForeground(color)
            self.level1_list_widget.addItem(item)

        self._update_button_states()    

    def _populate_child_list_with_parent_files(self):
        """Affiche les fichiers parents et leurs enfants avec un style unifié."""
        self.child_list_widget.clear()

        if not self.current_level1_data:
            return

        has_items = False

        primary = '#A23B2D'
        dark_gray = '#424242'
        medium_gray = '#666666'
        strong_gray = '#555555'

        def modulate_color(base_color: str, lvl: int = 1):
            if lvl > 1:
                if base_color == primary:
                    return '#D35A4A'
                elif base_color == dark_gray:
                    return '#5A5A5A'
                elif base_color == medium_gray:
                    return '#888888'
            return base_color

        modulated_primary = modulate_color(primary)
        modulated_dark = modulate_color(dark_gray)

        # === Fichiers parents ===
        for file_path in self.current_level1_data.get('files', []):
            has_items = True
            file_name = os.path.basename(file_path)
            item = QListWidgetItem(file_name)
            item.setIcon(qta.icon('fa5s.file-code', color=medium_gray))
            item.setData(Qt.UserRole, f"level1_file_{file_path}")
            item.setData(Qt.UserRole + 1, 'level1_file')
            item.setData(Qt.UserRole + 2, file_path)
            item.setForeground(QtGui.QColor(medium_gray))

            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)
            self.child_list_widget.addItem(item)

        # === Enfants ===
        for child in self.current_level1_data.get("children", []):
            has_items = True
            child_type = child.get('type', 'folder')
            label = child.get('label', child.get('name', 'Sans nom'))
            child_uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = child_uid
            line_num = child.get('line', 0)
            file_path = child.get('file', '')

            # --- AJOUT: détection du type selon préfixe label ---
            label_lower = label.lower()
            if child_type == 'folder' or not child_type:
                if label_lower.startswith(('function', 'func', 'fonction')):
                    child_type = 'function'
                elif label_lower.startswith(('method', 'meth', 'methode')):
                    child_type = 'method'
                elif label_lower.startswith(('class', 'classe')):
                    child_type = 'class'
                elif label_lower.startswith(('variable', 'var')):
                    child_type = 'variable'
            # --- FIN ajout ---

            icon = None
            color = QtGui.QColor("#000000")

            # === Typage et icônes cohérents ===
            if child_type == 'class':
                icon = qta.icon('fa5s.cube', color=strong_gray)
                color = QtGui.QColor(strong_gray)
                display = f"[CLASS] {label} (ligne {line_num})"

            elif child_type in ['function', 'method']:
                icon = qta.icon('fa5s.cog', color=modulated_primary)
                color = QtGui.QColor(modulated_primary)
                prefix = "[METH]" if child_type == 'method' else "[FUNC]"
                display = f"{prefix} {label} (ligne {line_num})"

            elif child_type == 'variable':
                icon = qta.icon('fa5s.tag', color=medium_gray)
                color = QtGui.QColor(medium_gray)
                display = f"[VAR] {label} (ligne {line_num})"

            elif label.endswith((
                '.ts', '.py', '.js', '.java', '.cpp', '.json', '.net',
                '.c', '.h', '.tsx', '.jsx', '.cs', '.php', '.rb', '.go',
                '.html', '.css', '.xml', '.txt', '.md', '.yaml', '.yml'
            )):
                icon = qta.icon('fa5s.file-code', color=medium_gray)
                color = QtGui.QColor(medium_gray)
                display = label

            elif child_type in ['folder', 'directory']:
                icon = qta.icon('fa5s.folder', color=modulated_dark)
                color = QtGui.QColor(modulated_dark)
                display = label

            else:
                icon = qta.icon('fa5s.question-circle', color="#16a085")
                color = QtGui.QColor("#16a085")
                display = f"[UNKNOWN] {label}"

            item = QListWidgetItem(display)
            item.setIcon(icon)
            item.setData(Qt.UserRole, child_uid)
            item.setData(Qt.UserRole + 1, child_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, line_num)
            item.setForeground(color)

            font = QtGui.QFont()
            font.setPointSize(7)
            font.setBold(False)
            item.setFont(font)

            self.child_list_widget.addItem(item)

        # === Aucun élément trouvé ===
        if not has_items:
            empty_item = QListWidgetItem("(Aucun élément trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            font = QtGui.QFont()
            font.setPointSize(7)
            empty_item.setFont(font)
            self.child_list_widget.addItem(empty_item)

        self._update_button_states()

    def _integrate_parsed_relations_to_node(self, node: Dict, parsed_relations: Dict, node_type: str):
        """
        Intègre les relations parsées (import, extends, calls, uses) au nœud.

        Args:
            node: Nœud cible (classe, fonction, variable)
            parsed_relations: Dict avec clés 'import', 'heritage', 'call', 'uses'
            node_type: Type du nœud ('class', 'function', 'variable')
        """
        if not parsed_relations:
            return

        # Pour les CLASSES : les héritages (extends)
        if node_type == 'class':
            for base_rel in parsed_relations.get('heritage', []):
                target_name = base_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'extends',
                            'category': 'parsed',
                            'line': base_rel.get('line', 0)
                        })

            # Usages de variables par la classe
            for use_rel in parsed_relations.get('uses', []):
                target_name = use_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'uses',
                            'category': 'parsed',
                            'line': use_rel.get('line', 0)
                        })

        # Pour les FONCTIONS : les appels (calls)
        elif node_type == 'function':
            for call_rel in parsed_relations.get('call', []):
                target_name = call_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'calls',
                            'category': 'parsed',
                            'line': call_rel.get('line', 0)
                        })

        # Pour les FICHIERS (root_labels) : imports
        if 'import' in parsed_relations:
            for import_rel in parsed_relations['import']:
                target_name = import_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'import',
                            'category': 'parsed',
                            'line': import_rel.get('line', 0)
                        })

    def _validate_parsed_relations(self):
        """
        Méthode de debug pour vérifier que les relations parsées sont bien présentes.
        """
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)

        stats = {
            'nodes_with_relations_dict': 0,
            'nodes_with_outgoing': 0,
            'total_parsed_in_dict': 0,
            'total_parsed_in_outgoing': 0
        }

        for node in all_nodes:
            node_name = node.get('label', node.get('name', 'Unknown'))

            # Vérifier dict 'relations'
            relations_dict = node.get('relations', {})
            if relations_dict:
                stats['nodes_with_relations_dict'] += 1
                for rel_type, rel_list in relations_dict.items():
                    stats['total_parsed_in_dict'] += len(rel_list)
                    logger.debug(f"  {node_name} - relations['{rel_type}']: {len(rel_list)} items")

            # Vérifier outgoing_relations
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                stats['nodes_with_outgoing'] += 1
                parsed_out = [r for r in outgoing if r.get('category') == 'parsed']
                stats['total_parsed_in_outgoing'] += len(parsed_out)
                if parsed_out:
                    logger.debug(f"  {node_name} - outgoing_relations (parsed): {len(parsed_out)}")

        logger.info(f"\n📊 VALIDATION RELATIONS PARSÉES:")
        logger.info(f"  Nœuds avec 'relations' dict: {stats['nodes_with_relations_dict']}")
        logger.info(f"  Nœuds avec outgoing_relations: {stats['nodes_with_outgoing']}")
        logger.info(f"  Total relations dans dict: {stats['total_parsed_in_dict']}")
        logger.info(f"  Total relations parsées dans outgoing: {stats['total_parsed_in_outgoing']}")

        return stats

    def _find_label_by_file_path(self, file_path: str) -> Optional[Dict]:
        """
        Trouve le label correspondant à un fichier dans la structure.
        """
        if not self.current_project_profile_data:
            return None

        file_name = os.path.basename(file_path)

        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            for root_label in cluster.get('root_labels', []):
                # Vérifier si c'est le bon label
                if root_label.get('label') == file_name:
                    return root_label

                # Chercher dans les fichiers du label
                if file_path in root_label.get('files', []):
                    return root_label

                # Chercher récursivement dans les enfants
                result = self._find_label_in_children(root_label, file_path, file_name)
                if result:
                    return result

        return None
    
    def _find_label_in_children(self, parent: Dict, file_path: str, file_name: str) -> Optional[Dict]:
        """Cherche récursivement un label par fichier."""
        for child in parent.get('children', []):
            if child.get('label') == file_name or file_path in child.get('files', []):
                return child

            result = self._find_label_in_children(child, file_path, file_name)
            if result:
                return result

        return None

    def _integrate_parsed_relations_to_label(self, label: Dict, parsed_relations: Dict, file_path: str):

        label_uid = label.get('uid')
        if not label_uid:
            return

        # Récupérer les infos complètes du label source
        source_info = {
            'uid': label_uid,
            'name': label.get('label', label.get('name', '')),
            'description': label.get('description', ''),
            'path': label.get('path', file_path),
            'type': label.get('type', 'file')
        }

        for rel_type, rel_list in parsed_relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                if not target_name:
                    continue
                
                # Normaliser le nom de la cible
                normalized_target = normalize_node_name(target_name)
                if not normalized_target:
                    continue
                
                # Essayer de trouver l'UID de la cible
                target_uid = self._find_label_uid_by_name(normalized_target)

                # ✅ RÉCUPÉRER LES INFOS COMPLÈTES DE LA CIBLE
                if target_uid and target_uid in self.label_uid_to_info:
                    target_info = self.label_uid_to_info[target_uid]
                    target_data = {
                        'uid': target_uid,
                        'name': target_info.get('name', target_name),
                        'description': target_info.get('label', ''),
                        'path': target_info.get('file', ''),
                        'type': target_info.get('type', 'unknown')
                    }
                else:
                    # Si pas trouvé, créer un UID temporaire avec infos minimales
                    target_uid = f"temp_{normalized_target}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': target_uid,
                        'name': target_name,
                        'description': f"Unresolved: {target_name}",
                        'path': '',
                        'type': 'unresolved'
                    }
                    logger.debug(f"UID temporaire créé pour {normalized_target}: {target_uid}")

                # ✅ CRÉER L'ENTRÉE DE RELATION ENRICHIE
                relation_entry = {
                    # Target info
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],

                    # Source info
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],

                    # Relation metadata
                    'relation_type': rel_type,
                    'category': 'parsed',
                    'line': rel.get('line', 0),
                    'intra_file': rel.get('intra_file', False)
                }

                # Ajouter à outgoing_relations si pas déjà présent
                outgoing = label.setdefault('outgoing_relations', [])
                if not any(r['target_uid'] == target_data['uid'] and r['relation_type'] == rel_type for r in outgoing):
                    outgoing.append(relation_entry)
                    logger.debug(f"Relation enrichie ajoutée: {source_info['name']} --{rel_type}--> {target_data['name']}")

                # Ajouter aussi aux pending_relations pour synchronisation Dgraph
                pending = self.pending_relations.get(label_uid, [])
                pending_entry = {
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'relation_type': rel_type
                }
                if pending_entry not in pending:
                    pending.append(pending_entry)
                    self.pending_relations[label_uid] = pending

    def _create_child_node_from_extracted(self, item: Dict, item_type: str) -> Dict:
        """
        ✅ CORRIGÉ : Crée un nœud enfant avec relations enrichies
        """
        uid = item.get('uid', str(uuid.uuid4()))
        
        # Récupérer infos du fichier parent
        file_path = item.get('file', '')
        
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'path': file_path,
            'description': item.get('description', f"{item_type} {item['name']} at line {item.get('line', 0)}"),
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': [],
            'parents': []
        }
    
        # ✅ Infos source complètes
        source_info = {
            'uid': uid,
            'name': item['name'],
            'description': child['description'],
            'path': file_path,
            'type': item_type
        }
    
        if item_type == 'class':
            # Héritage (bases)
            for base_name in item.get('bases', []):
                base_uid = self._find_label_uid_by_name(normalize_node_name(base_name))
                
                # ✅ Récupérer infos complètes de la base
                if base_uid and base_uid in self.label_uid_to_info:
                    base_info = self.label_uid_to_info[base_uid]
                    target_data = {
                        'uid': base_uid,
                        'name': base_info.get('name', base_name),
                        'description': base_info.get('label', ''),
                        'path': base_info.get('file', ''),
                        'type': base_info.get('type', 'class')
                    }
                else:
                    base_uid = f"temp_class_{base_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': base_uid,
                        'name': base_name,
                        'description': f"Base class: {base_name}",
                        'path': '',
                        'type': 'class'
                    }
    
                child['outgoing_relations'].append({
                    # Target
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    
                    # Source
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    
                    # Metadata
                    'relation_type': 'extends',
                    'category': 'parsed'
                })
    
            # Usages de variables (même pattern)
            for var_name in item.get('uses_vars', []):
                var_uid = self._find_label_uid_by_name(normalize_node_name(var_name))
                
                if var_uid and var_uid in self.label_uid_to_info:
                    var_info = self.label_uid_to_info[var_uid]
                    target_data = {
                        'uid': var_uid,
                        'name': var_info.get('name', var_name),
                        'description': var_info.get('label', ''),
                        'path': var_info.get('file', ''),
                        'type': var_info.get('type', 'variable')
                    }
                else:
                    var_uid = f"temp_var_{var_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': var_uid,
                        'name': var_name,
                        'description': f"Variable: {var_name}",
                        'path': '',
                        'type': 'variable'
                    }
    
                child['outgoing_relations'].append({
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    'relation_type': 'uses',
                    'category': 'parsed'
                })
    
        elif item_type == 'function':
            # Appels de fonction (même pattern)
            for call_name in item.get('calls', []):
                call_uid = self._find_label_uid_by_name(normalize_node_name(call_name))
                
                if call_uid and call_uid in self.label_uid_to_info:
                    call_info = self.label_uid_to_info[call_uid]
                    target_data = {
                        'uid': call_uid,
                        'name': call_info.get('name', call_name),
                        'description': call_info.get('label', ''),
                        'path': call_info.get('file', ''),
                        'type': call_info.get('type', 'function')
                    }
                else:
                    call_uid = f"temp_func_{call_name}_{str(uuid.uuid4())[:8]}"
                    target_data = {
                        'uid': call_uid,
                        'name': call_name,
                        'description': f"Function: {call_name}",
                        'path': '',
                        'type': 'function'
                    }
    
                child['outgoing_relations'].append({
                    'target_uid': target_data['uid'],
                    'target_name': target_data['name'],
                    'target_description': target_data['description'],
                    'target_path': target_data['path'],
                    'target_type': target_data['type'],
                    'source_uid': source_info['uid'],
                    'source_name': source_info['name'],
                    'source_description': source_info['description'],
                    'source_path': source_info['path'],
                    'source_type': source_info['type'],
                    'relation_type': 'calls',
                    'category': 'parsed'
                })
    
        # Ajouter aux infos globales
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_data.get('name', 'unknown') if self.current_cluster_data else 'unknown',
            'file': file_path,
            'path': file_path,
            'description': child['description']
        }
    
        return child

    def _build_complete_relations_graph(self):
        """
        ✅ VERSION CORRIGÉE : Résout les UIDs avec recherche améliorée
        """
        logger.info("🔗 Construction du graphe de relations...")
    
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)
        resolved_count = 0
        inverse_count = 0
    
        # Étape 0 : Créer des index pour recherche rapide
        logger.info("📊 Création des index de recherche...")
        
        # Index par UID
        node_by_uid = {n['uid']: n for n in all_nodes if 'uid' in n}
        
        # Index par nom (pour résolution)
        node_by_name = {}
        for node in all_nodes:
            name = node.get('name') or node.get('label', '')
            if name:
                normalized = name.lower().strip()
                if normalized not in node_by_name:
                    node_by_name[normalized] = []
                node_by_name[normalized].append(node)
        
        logger.info(f"  ✅ {len(node_by_uid)} nœuds indexés par UID")
        logger.info(f"  ✅ {len(node_by_name)} noms indexés")
    
        # Étape 1 : Résoudre les UIDs temporaires
        logger.info("📝 Résolution des UIDs temporaires...")
        
        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid', '')
                
                # Si c'est un UID temporaire, essayer de le résoudre
                if target_uid.startswith('temp_'):
                    target_name = rel.get('target_name', '')
                    
                    # ✅ AMÉLIORATION : Essayer plusieurs stratégies de résolution
                    real_uid = None
                    
                    # Stratégie 1 : Recherche par nom exact
                    if target_name:
                        normalized_target = target_name.lower().strip()
                        
                        # Essayer avec le nom complet
                        candidates = node_by_name.get(normalized_target, [])
                        
                        # Si pas trouvé, essayer sans extension
                        if not candidates and '.' in target_name:
                            base_name = target_name.rsplit('.', 1)[0].lower()
                            candidates = node_by_name.get(base_name, [])
                        
                        # Si trouvé, choisir le premier candidat du bon type
                        if candidates:
                            target_type = rel.get('target_type', '')
                            
                            # Filtrer par type si spécifié
                            if target_type:
                                typed_candidates = [c for c in candidates if c.get('type') == target_type]
                                if typed_candidates:
                                    real_uid = typed_candidates[0]['uid']
                                else:
                                    real_uid = candidates[0]['uid']
                            else:
                                real_uid = candidates[0]['uid']
                    
                    # Stratégie 2 : Recherche via label_uid_to_info
                    if not real_uid and target_name:
                        real_uid = self._find_label_uid_by_name(target_name)
                    
                    # Si résolu, mettre à jour
                    if real_uid:
                        rel['target_uid'] = real_uid
                        resolved_count += 1
                        
                        # Mettre à jour aussi les infos de target
                        target_node = node_by_uid.get(real_uid)
                        if target_node:
                            rel['target_name'] = target_node.get('label') or target_node.get('name', target_name)
                            rel['target_type'] = target_node.get('type', 'unknown')
                    else:
                        logger.debug(f"⚠️ UID temporaire non résolu: {target_name} ({target_uid})")
    
        logger.info(f"✅ {resolved_count} UIDs temporaires résolus")
    
        # Étape 2 : Créer les relations inverses
        logger.info("🔄 Création des relations inverses...")
        
        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')
                
                # Skip si c'est toujours un UID temporaire
                if not target_uid or target_uid.startswith('temp_'):
                    continue
                
                target_node = node_by_uid.get(target_uid)
                if not target_node:
                    continue
                
                # Créer la relation inverse
                inverse = {
                    'source_uid': node_uid,
                    'relation_type': rel['relation_type'],
                    'category': rel.get('category', 'parsed'),
                    'source_name': node.get('label', node.get('name', 'Unknown')),
                    'source_type': node.get('type', 'unknown'),
                    'source_path': node.get('path', ''),
                    'line': rel.get('line', 0)
                }
                
                incoming = target_node.setdefault('incoming_relations', [])
                
                # Vérifier si déjà présent
                is_duplicate = any(
                    r['source_uid'] == node_uid and 
                    r['relation_type'] == rel['relation_type']
                    for r in incoming
                )
                
                if not is_duplicate:
                    incoming.append(inverse)
                    inverse_count += 1
    
        logger.info(f"✅ {inverse_count} relations inverses créées")
    
        # Étape 3 : Statistiques finales
        total_relations = sum(len(n.get('outgoing_relations', [])) for n in all_nodes)
        resolved_relations = sum(
            1 for n in all_nodes 
            for r in n.get('outgoing_relations', []) 
            if not r.get('target_uid', '').startswith('temp_')
        )
        
        logger.info(f"📊 Graphe complet: {len(all_nodes)} nœuds, {total_relations} relations")
        logger.info(f"  ✅ {resolved_relations}/{total_relations} relations résolues ({resolved_relations*100//total_relations if total_relations > 0 else 0}%)")
        logger.info(f"  ⚠️ {total_relations - resolved_relations} relations non résolues")

    def _save_scan_results_to_storage(self):
        """
         CORRECTION: Sauvegarde avec passage explicite de profile_data
        """
        if not self.current_project_name or not self.current_project_profile_data:
            logger.error("Aucun projet sélectionné pour la sauvegarde.")
            return False

        logger.info("=" * 80)
        logger.info("💾 SAUVEGARDE DES RÉSULTATS DE SCAN")
        logger.info("=" * 80)

        try:
            # ÉTAPE 1: Finaliser les données
            logger.info("\n🔄 Étape 1: Mise à jour des structures en mémoire...")
            self._finalize_project_data_after_scan()

            # ÉTAPE 2: SQLite
            logger.info("\n💾 Étape 2: Sauvegarde dans SQLite...")
            sqlite_success = self.project_storage_manager._save_project_to_sqlite(
                self.current_project_profile_data
            )
            if not sqlite_success:
                logger.error("❌ Échec sauvegarde SQLite")
                return False
            logger.info("✅ Sauvegarde SQLite réussie")

            # ÉTAPE 3: Dgraph
            logger.info("\n🔄 Étape 3: Insertion dans Dgraph...")

            # ✅ CORRECTION: Synchroniser avant transformation
            self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
            self.dgraph_manager.label_uid_to_info = self.label_uid_to_info
            self.dgraph_manager.pending_relations = self.pending_relations

            # ✅ CORRECTION: Passer explicitement profile_data
            mutations = self.dgraph_manager._transform_profile_to_dgraph_mutations(
                profile_data=self.current_project_profile_data
            )

            if not mutations:
                logger.error("❌ Aucune mutation générée")
                return False

            logger.info(f"📊 {len(mutations)} mutations à insérer")

            dgraph_success = self.dgraph_connector.insert_mutations(mutations)
            if not dgraph_success:
                logger.error("❌ Échec insertion Dgraph")
                return False

            logger.info("✅ Insertion Dgraph réussie")
            self.dgraph_manager.clean_duplicate_files()

            # ÉTAPE 4: Rafraîchir
            logger.info("\n🔄 Étape 4: Rafraîchissement des données...")

            # Recharger depuis Dgraph
            loaded_profiles = self.dgraph_manager._load_project_profiles()
            if loaded_profiles:
                self.project_profiles.update(loaded_profiles)
                logger.info(f"✅ {len(loaded_profiles)} profil(s) rechargé(s)")

            # Recharger depuis SQLite
            self.project_storage_manager._load_projects_from_sqlite()

            # Réafficher dans l'UI
            if self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())

            logger.info("\n" + "=" * 80)
            logger.info("✅ SAUVEGARDE COMPLÈTE: Scan enregistré dans SQLite ET Dgraph")
            logger.info("=" * 80 + "\n")

            QtWidgets.QMessageBox.information(
                self,
                "Succès",
                "Résultats du scan sauvegardés dans SQLite et Dgraph avec succès!"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            import traceback
            traceback.print_exc()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la sauvegarde: {str(e)}"
            )
            return False

    def _finalize_project_data_after_scan(self):
        """
         CORRECTION: Finalise avec passage explicite de profile_data
        """
        logger.info("Finalisation des données du projet...")

        if not self.current_project_profile_data:
            return

        all_nodes = self.dgraph_manager._get_all_nodes(
            self.current_project_profile_data
        )

        # 1. Résolution des UIDs temporaires
        logger.info("✓ Résolution des UIDs temporaires...")
        uid_mapping = {}

        for node in all_nodes:
            uid = node.get('uid')
            if not uid or uid.startswith('temp_') or uid.startswith('unresolved_'):
                new_uid = str(uuid.uuid4())
                if uid:
                    uid_mapping[uid] = new_uid
                node['uid'] = new_uid

        # 2. Mettre à jour les références
        logger.info("✓ Mise à jour des références aux UIDs...")
        for node in all_nodes:
            for rel in node.get('outgoing_relations', []):
                old_target = rel.get('target_uid')
                if old_target in uid_mapping:
                    rel['target_uid'] = uid_mapping[old_target]

        # 3. Synchroniser pending_relations
        logger.info("✓ Synchronisation pending_relations...")
        self.pending_relations.clear()

        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            relations_list = []
            for rel in node.get('outgoing_relations', []):
                relations_list.append({
                    'target_uid': rel.get('target_uid'),
                    'relation_type': rel.get('relation_type', 'relation')
                })

            if relations_list:
                self.pending_relations[node_uid] = relations_list

        # 4. Validation
        logger.info("✓ Validation de la cohérence...")
        validation_stats = self._validate_parsed_relations()
        logger.info(f"  Validation: {validation_stats['total_parsed_in_outgoing']} relations validées")

        # 5. Construction du graphe complet
        logger.info("✓ Construction du graphe complet...")
        self._build_complete_relations_graph()

        # 6. Batch insertion Dgraph
        logger.info("✓ Insertion batchée dans Dgraph...")

        #  CORRECTION: Synchroniser avant batch save
        self.dgraph_manager.current_project_profile_data = self.current_project_profile_data
        self.dgraph_manager.label_uid_to_info = self.label_uid_to_info
        self.dgraph_manager.pending_relations = self.pending_relations

        # CORRECTION: Passer explicitement profile_data
        if self.dgraph_manager._batch_save_to_dgraph(
            profile_data=self.current_project_profile_data
        ):
            logger.info(" Batch Dgraph réussi")
        else:
            logger.warning("⚠️ Échec batch Dgraph, retry manuel requis")

        logger.info("Finalisation terminée ✓")

    def _get_element_icon(self, element_type: str) -> str:
        icons = {
            # Éléments de code
            'class': '🏛️',      # Temple/bâtiment pour représenter une structure de classe
            'function': '⚡',    # Éclair pour fonction autonome (rapide, indépendante)
            'method': '⚙️',     # Engrenage pour méthode (partie d'un mécanisme de classe)
            'variable': '💠',    # Losange pour variable

            # Fichiers et dossiers
            'file': '📄',
            'folder': '📁',
            'directory': '📁',

            # Types spéciaux
            'root_file': '📄',
            'level1_file': '📄',
            'root_label': '📁',
            'child': '📁',

            # Relations
            'import': '📦',
            'extends': '🔗',
            'calls': '📞',
            'uses': '🔸'
        }
        return icons.get(element_type, '📌')
    
    def _extract_and_save_inter_element_relations(self, file_path: str, content: str):
        """
        ✅ NOUVEAU : Extrait et sauvegarde les relations inter-éléments

        Args:
            file_path: Chemin du fichier
            content: Contenu du fichier
        """
        if not content:
            return

        # Extraire classes et fonctions
        classes = self.dependency_parser.extract_classes(content, file_path)
        functions = self.dependency_parser.extract_functions(content, file_path)

        if not classes and not functions:
            return

        # Extraire les relations détaillées
        detailed_relations = self.dependency_parser.extract_detailed_relations(
            content, file_path, classes, functions
        )

        # Enregistrer dans la structure
        self._register_inter_element_relations(detailed_relations, file_path)

        # Log
        total_rels = sum(len(v) for v in detailed_relations.values())
        if total_rels > 0:
            logger.info(f"  📊 {total_rels} relations inter-éléments détectées:")
            for rel_type, rel_list in detailed_relations.items():
                if rel_list:
                    logger.info(f"    • {rel_type}: {len(rel_list)}")

    def _register_inter_element_relations(self, detailed_relations: Dict, file_path: str):
        """
        ✅ Enregistre les relations dans la structure du projet

        Args:
            detailed_relations: Dict avec les relations extraites
            file_path: Chemin du fichier source
        """
        # Classe → Classe
        for rel in detailed_relations.get('class_to_class', []):
            source_uid = rel['source_uid']

            # Ajouter à outgoing_relations
            source_node = self._find_label_by_uid(source_uid)
            if source_node:
                source_node.setdefault('outgoing_relations', []).append({
                    'target_uid': rel['target_uid'],
                    'target_name': rel['target_name'],
                    'relation_type': rel['relation_type'],
                    'category': 'parsed',
                    'line': rel['line'],
                    'source_name': rel['source_name'],
                    'source_uid': source_uid,
                    'intra_file': True
                })

            # Ajouter aux pending_relations
            self.pending_relations[source_uid].append({
                'target_uid': rel['target_uid'],
                'target_name': rel['target_name'],
                'relation_type': rel['relation_type']
            })

        # Classe → Fonction
        for rel in detailed_relations.get('class_to_function', []):
            source_uid = rel['source_uid']

            source_node = self._find_label_by_uid(source_uid)
            if source_node:
                source_node.setdefault('outgoing_relations', []).append({
                    'target_uid': rel['target_uid'],
                    'target_name': rel['target_name'],
                    'relation_type': rel['relation_type'],
                    'category': 'parsed',
                    'line': rel['line'],
                    'source_name': rel['source_name'],
                    'source_uid': source_uid,
                    'intra_file': True
                })

            self.pending_relations[source_uid].append({
                'target_uid': rel['target_uid'],
                'target_name': rel['target_name'],
                'relation_type': rel['relation_type']
            })

        # Fonction → Fonction
        for rel in detailed_relations.get('function_to_function', []):
            source_uid = rel['source_uid']

            source_node = self._find_label_by_uid(source_uid)
            if source_node:
                source_node.setdefault('outgoing_relations', []).append({
                    'target_uid': rel['target_uid'],
                    'target_name': rel['target_name'],
                    'relation_type': rel['relation_type'],
                    'category': 'parsed',
                    'line': rel['line'],
                    'source_name': rel['source_name'],
                    'source_uid': source_uid,
                    'intra_file': True
                })

            self.pending_relations[source_uid].append({
                'target_uid': rel['target_uid'],
                'target_name': rel['target_name'],
                'relation_type': rel['relation_type']
            })

        # Fonction → Classe
        for rel in detailed_relations.get('function_to_class', []):
            source_uid = rel['source_uid']

            source_node = self._find_label_by_uid(source_uid)
            if source_node:
                source_node.setdefault('outgoing_relations', []).append({
                    'target_uid': rel['target_uid'],
                    'target_name': rel['target_name'],
                    'relation_type': rel['relation_type'],
                    'category': 'parsed',
                    'line': rel['line'],
                    'source_name': rel['source_name'],
                    'source_uid': source_uid,
                    'intra_file': True
                })

            self.pending_relations[source_uid].append({
                'target_uid': rel['target_uid'],
                'target_name': rel['target_name'],
                'relation_type': rel['relation_type']
            })

    def _save_label_and_children_recursive(self, cursor, label_data, cluster_uid, parent_uid, level):
        """
        ✅ CORRIGÉ : Sauvegarde SANS troncature avec commit optimisé
        """
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid

        # ✅ DIRECT - Pas de truncate_json()
        files = label_data.get('files', [])
        file_contents = label_data.get('file_contents', {})

        # Log taille pour monitoring
        try:
            file_contents_json = json.dumps(file_contents, ensure_ascii=False)
            size_mb = len(file_contents_json.encode('utf-8')) / (1024 * 1024)

            if size_mb > 10:
                logger.warning(f"⚠️ Gros fileContents: {label_data.get('label')} ({size_mb:.2f} MB)")
        except Exception as e:
            logger.error(f"❌ Erreur calcul taille: {e}")
            file_contents_json = "{}"
            size_mb = 0

        # Sauvegarder le label
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label_uid,
                cluster_uid,
                parent_uid,
                label_data.get('label', ''),
                label_data.get('id', label_uid),
                level,
                label_data.get('path', ''),
                parent_uid,
                label_data.get('type', 'label'),
                json.dumps(label_data.get('category', []), ensure_ascii=False),
                label_data.get('description', ''),
                '',
                json.dumps(files, ensure_ascii=False),
                file_contents_json,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
        except Exception as e:
            logger.error(f"❌ Erreur insertion label {label_data.get('label')}: {e}")
            return

        # ✅ Commit après CHAQUE root label
        if level == 0:
            try:
                cursor.connection.commit()
                logger.info(f"✅ Commit: {label_data.get('label')} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.error(f"❌ Erreur commit: {e}")

        # Sauvegarder les classes du label
        for cls in label_data.get('classes', []):
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            cls['uid'] = cls_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cls_uid,
                    cluster_uid,
                    label_uid,
                    cls.get('name', ''),
                    cls.get('uid', cls_uid),
                    level + 1,
                    '',
                    label_uid,
                    'class',
                    json.dumps(['code_element', 'class']),
                    cls.get('description', ''),
                    '',
                    json.dumps(cls.get('files', []), ensure_ascii=False),
                    json.dumps(cls.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Relations de la classe
                for rel in cls.get('outgoing_relations', []):
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        cls_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            except Exception as e:
                logger.error(f"❌ Erreur classe {cls.get('name')}: {e}")
                continue

        # Sauvegarder les fonctions
        for func in label_data.get('functions', []):
            func_uid = func.get('uid', str(uuid.uuid4()))
            func['uid'] = func_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    func_uid,
                    cluster_uid,
                    label_uid,
                    func.get('name', ''),
                    func.get('uid', func_uid),
                    level + 1,
                    '',
                    label_uid,
                    func.get('type', 'function'),
                    json.dumps(['code_element', 'function']),
                    func.get('description', ''),
                    '',
                    json.dumps(func.get('files', []), ensure_ascii=False),
                    json.dumps(func.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Relations
                for rel in func.get('outgoing_relations', []):
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        func_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            except Exception as e:
                logger.error(f"❌ Erreur fonction {func.get('name')}: {e}")
                continue

        # Sauvegarder les variables
        for var in label_data.get('variables', []):
            var_uid = var.get('uid', str(uuid.uuid4()))
            var['uid'] = var_uid

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO labels 
                    (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                     nodeType, category, description, codeContent, files, fileContents, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    var_uid,
                    cluster_uid,
                    label_uid,
                    var.get('name', ''),
                    var.get('uid', var_uid),
                    level + 1,
                    '',
                    label_uid,
                    'variable',
                    json.dumps(['code_element', 'variable']),
                    var.get('description', ''),
                    '',
                    json.dumps(var.get('files', []), ensure_ascii=False),
                    json.dumps(var.get('file_contents', {}), ensure_ascii=False),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.error(f"❌ Erreur variable {var.get('name')}: {e}")
                continue

        # Traiter récursivement les enfants hiérarchiques
        for child in label_data.get('children', []):
            if child.get('type') not in ['class', 'function', 'variable']:
                self._save_label_and_children_recursive(
                    cursor, child, cluster_uid, label_uid, level + 1
                )

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector: 
            self.dgraph_connector.close()
        super().closeEvent(event)