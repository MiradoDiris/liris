from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHBoxLayout, QLabel
# ==============================================================================
# 1. STYLES RESPONSIFS POUR RelationsConfig
# ==============================================================================

class ResponsiveRelationsConfigStyles:
    """Styles responsifs pour le widget de configuration des relations"""
    
    @staticmethod
    def get_responsive_stylesheet():
        """Retourne le stylesheet responsive complet"""
        return """
            /* === CONTENEUR PRINCIPAL === */
            QWidget {
                min-width: 300px;
            }
            
            /* === TITRE RESPONSIVE === */
            QLabel[objectName="title"] {
                font-weight: bold;
                font-size: clamp(11px, 2vw, 14px);
                color: black;
                padding: 5px;
            }
            
            /* === SECTION FILTRES RESPONSIVE === */
            QLabel[objectName="filter_label"] {
                color: black;
                font-weight: bold;
                font-size: clamp(10px, 1.8vw, 12px);
                padding: 3px;
            }
            
            /* === BOUTONS DE FILTRAGE RESPONSIVE === */
            QPushButton[objectName="filter_btn"] {
                background-color: #e8e8e8;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: clamp(4px, 1vw, 8px) clamp(8px, 2vw, 12px);
                font-size: clamp(9px, 1.5vw, 11px);
                font-weight: normal;
                min-height: 28px;
                max-height: 40px;
            }
            
            QPushButton[objectName="filter_btn"]:checked {
                background-color: #b3d9ff;
                color: black;
                border: 1px solid #0066cc;
                font-weight: bold;
            }
            
            QPushButton[objectName="filter_btn"]:hover:!pressed {
                background-color: #ffffff;
                color: black;
                border: 1px solid #666;
            }
            
            /* === LABELS SOURCE/TARGET RESPONSIVE === */
            QLabel[objectName="source_header"],
            QLabel[objectName="target_header"] {
                font-weight: bold;
                font-size: clamp(10px, 1.8vw, 12px);
                color: #333;
                padding: 2px 5px;
            }
            
            QLabel[objectName="source_label"] {
                color: #2196F3;
                font-weight: bold;
                font-size: clamp(10px, 1.8vw, 12px);
                padding: 2px 8px;
                word-wrap: break-word;
            }
            
            QLabel[objectName="target_label"] {
                color: #4CAF50;
                font-weight: bold;
                font-size: clamp(10px, 1.8vw, 12px);
                padding: 2px 8px;
                word-wrap: break-word;
            }
            
            /* === LISTE DES RELATIONS RESPONSIVE === */
            QListWidget {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                min-height: 120px;
                max-height: 200px;
                font-size: clamp(9px, 1.6vw, 11px);
            }
            
            QListWidget::item {
                padding: clamp(4px, 1vw, 8px);
                border-radius: 3px;
                margin: 2px 0px;
                color: black;
                word-wrap: break-word;
                min-height: 25px;
            }
            
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: black;
                border: 1px solid #999;
            }
            
            QListWidget::item:hover {
                background-color: #ffffff;
                color: black;
            }
            
            /* === BOUTONS D'ACTION RESPONSIVE === */
            QPushButton[objectName="action_btn"] {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: clamp(5px, 1.2vw, 10px) clamp(10px, 2vw, 15px);
                font-size: clamp(9px, 1.6vw, 11px);
                font-weight: bold;
                min-height: 30px;
                min-width: 80px;
            }
            
            QPushButton[objectName="action_btn"]:hover {
                background-color: #1976D2;
            }
            
            QPushButton[objectName="action_btn"]:pressed {
                background-color: #0D47A1;
            }
            
            QPushButton[objectName="action_btn"]:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
            
            /* === SÉPARATEUR RESPONSIVE === */
            QFrame[frameShape="4"] {
                background-color: #ccc;
                max-height: 1px;
                margin: 5px 0;
            }
            
            /* === MEDIA QUERIES SIMULÉES === */
            /* Pour petits écrans (< 600px simulé via taille de widget) */
            QWidget[minimumWidth="0"] QWidget[maximumWidth="600"] {
                QPushButton[objectName="action_btn"] {
                    min-width: 100%;
                    margin: 3px 0;
                }
            }
        """
    
    @staticmethod
    def get_container_style():
        """Style pour le conteneur principal avec flexibilité"""
        return """
            QWidget {
                background-color: white;
                border-radius: 6px;
                padding: clamp(5px, 1vw, 10px);
            }
        """


# ==============================================================================
# 2. MODIFICATIONS POUR RelationsConfig.__init__
# ==============================================================================

def apply_responsive_to_relations_config(widget_instance):
    """
    Fonction à appeler dans __init__ pour appliquer le design responsive
    
    Usage dans RelationsConfig.__init__:
        self._init_ui()
        apply_responsive_to_relations_config(self)
    """
    
    # Appliquer les object names pour le CSS
    if hasattr(widget_instance, 'hierarchy_btn'):
        widget_instance.hierarchy_btn.setObjectName("filter_btn")
    
    if hasattr(widget_instance, 'dependencies_btn'):
        widget_instance.dependencies_btn.setObjectName("filter_btn")
    
    if hasattr(widget_instance, 'source_label'):
        widget_instance.source_label.setObjectName("source_label")
    
    if hasattr(widget_instance, 'target_label'):
        widget_instance.target_label.setObjectName("target_label")
    
    if hasattr(widget_instance, 'add_button'):
        widget_instance.add_button.setObjectName("action_btn")
    
    if hasattr(widget_instance, 'edit_button'):
        widget_instance.edit_button.setObjectName("action_btn")
    
    if hasattr(widget_instance, 'remove_button'):
        widget_instance.remove_button.setObjectName("action_btn")
    
    # Appliquer le stylesheet responsive
    widget_instance.setStyleSheet(ResponsiveRelationsConfigStyles.get_responsive_stylesheet())
    
    # Rendre le widget redimensionnable
    widget_instance.setMinimumWidth(300)
    widget_instance.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Expanding
    )


# ==============================================================================
# 3. STYLES RESPONSIFS POUR RelationsGraphWidget
# ==============================================================================

class ResponsiveGraphStyles:
    """Styles responsifs pour le widget de graphe"""
    
    @staticmethod
    def get_responsive_stylesheet():
        return """
            /* === CONTENEUR GRAPHE === */
            QWidget {
                background-color: white;
                border-radius: 6px;
                min-width: 300px;
            }
            
            /* === TITRE RESPONSIVE === */
            QLabel[objectName="graph_title"] {
                font-weight: bold;
                font-size: clamp(11px, 2vw, 14px);
                color: #2c3e50;
                padding: clamp(3px, 0.8vw, 8px);
            }
            
            /* === LÉGENDE RESPONSIVE === */
            QLabel[objectName="graph_legend"] {
                font-size: clamp(9px, 1.5vw, 11px);
                color: #666;
                font-style: italic;
                padding: clamp(3px, 0.8vw, 6px);
                word-wrap: break-word;
            }
            
            /* === CANVAS RESPONSIVE === */
            QWidget[objectName="graph_canvas"] {
                min-height: 200px;
                background-color: white;
            }
        """


def apply_responsive_to_graph_widget(widget_instance):
    """
    Fonction à appeler dans RelationsGraphWidget.__init__
    
    Usage:
        self._init_ui()
        apply_responsive_to_graph_widget(self)
    """
    
    # Appliquer les object names
    if hasattr(widget_instance, 'title_label'):
        widget_instance.title_label.setObjectName("graph_title")
    
    if hasattr(widget_instance, 'legend_label'):
        widget_instance.legend_label.setObjectName("graph_legend")
    
    if hasattr(widget_instance, 'canvas'):
        widget_instance.canvas.setObjectName("graph_canvas")
        # Rendre le canvas responsive
        widget_instance.canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
    
    # Appliquer le stylesheet
    widget_instance.setStyleSheet(ResponsiveGraphStyles.get_responsive_stylesheet())
    
    # Politique de taille
    widget_instance.setMinimumWidth(300)
    widget_instance.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Expanding
    )


# ==============================================================================
# 4. GESTIONNAIRE D'ÉVÉNEMENTS RESIZE
# ==============================================================================

class ResponsiveLayoutManager:
    """Gestionnaire pour adapter le layout selon la taille de la fenêtre"""
    
    @staticmethod
    def handle_resize_relations_config(widget_instance, event):
        """
        Gère le redimensionnement pour RelationsConfig
        
        À ajouter dans RelationsConfig:
            def resizeEvent(self, event):
                super().resizeEvent(event)
                ResponsiveLayoutManager.handle_resize_relations_config(self, event)
        """
        width = event.size().width()
        
        # Adapter la hauteur de la liste selon la largeur
        if hasattr(widget_instance, 'relations_list'):
            if width < 400:
                widget_instance.relations_list.setMaximumHeight(120)
            elif width < 600:
                widget_instance.relations_list.setMaximumHeight(150)
            else:
                widget_instance.relations_list.setMaximumHeight(200)
        
        # Adapter la disposition des boutons
        if width < 500:
            # Mode compact: boutons en colonne
            if hasattr(widget_instance, 'add_button'):
                widget_instance.add_button.setMaximumWidth(16777215)  # Enlever la limite
            if hasattr(widget_instance, 'edit_button'):
                widget_instance.edit_button.setMaximumWidth(16777215)
            if hasattr(widget_instance, 'remove_button'):
                widget_instance.remove_button.setMaximumWidth(16777215)
        else:
            # Mode normal: boutons en ligne
            if hasattr(widget_instance, 'add_button'):
                widget_instance.add_button.setMaximumWidth(160)
            if hasattr(widget_instance, 'edit_button'):
                widget_instance.edit_button.setMaximumWidth(110)
            if hasattr(widget_instance, 'remove_button'):
                widget_instance.remove_button.setMaximumWidth(110)
    
    @staticmethod
    def handle_resize_graph_widget(widget_instance, event):
        """
        Gère le redimensionnement pour RelationsGraphWidget
        
        À ajouter dans RelationsGraphWidget:
            def resizeEvent(self, event):
                super().resizeEvent(event)
                ResponsiveLayoutManager.handle_resize_graph_widget(self, event)
        """
        width = event.size().width()
        height = event.size().height()
        
        # Adapter la taille du graphe
        if hasattr(widget_instance, 'figure') and widget_instance.figure:
            # Ajuster DPI selon la taille
            if width < 400:
                dpi = 80
            elif width < 600:
                dpi = 90
            else:
                dpi = 100
            
            widget_instance.figure.set_dpi(dpi)
            
            # Redessiner si nécessaire
            if hasattr(widget_instance, 'canvas'):
                widget_instance.canvas.draw_idle()
        
        # Adapter la hauteur minimale du canvas
        if hasattr(widget_instance, 'canvas'):
            if height < 300:
                widget_instance.canvas.setMinimumHeight(150)
            elif height < 500:
                widget_instance.canvas.setMinimumHeight(200)
            else:
                widget_instance.canvas.setMinimumHeight(250)


# ==============================================================================
# 5. UTILITAIRES DE LAYOUT RESPONSIVE
# ==============================================================================

class ResponsiveLayoutUtils:
    """Utilitaires pour créer des layouts responsifs"""
    
    @staticmethod
    def create_responsive_button_layout(buttons_list, min_width_threshold=500):
        """
        Crée un layout de boutons qui s'adapte à la largeur
        
        Args:
            buttons_list: Liste des boutons à disposer
            min_width_threshold: Seuil pour passer en mode vertical
        
        Returns:
            QHBoxLayout ou QVBoxLayout selon le contexte
        """
        layout = QHBoxLayout()
        layout.setSpacing(8)
        
        for button in buttons_list:
            layout.addWidget(button)
            # Permettre au bouton de s'étendre
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Fixed
            )
        
        layout.addStretch()
        return layout
    
    @staticmethod
    def make_widget_responsive(widget):
        """
        Applique les propriétés de base pour rendre un widget responsive
        """
        widget.setMinimumWidth(300)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
        # Activer le word wrap pour les labels
        if isinstance(widget, QLabel):
            widget.setWordWrap(True)
            widget.setScaledContents(True)


# ==============================================================================
# 6. EXEMPLE D'INTÉGRATION COMPLÈTE
# ==============================================================================

"""
INTÉGRATION DANS relations_config.py:

1. Ajouter l'import en haut du fichier:
   from ui.responsive_relations import (
       apply_responsive_to_relations_config,
       ResponsiveLayoutManager
   )

2. Dans RelationsConfig.__init__, après self._init_ui():
   apply_responsive_to_relations_config(self)

3. Ajouter la méthode resizeEvent:
   def resizeEvent(self, event):
       super().resizeEvent(event)
       ResponsiveLayoutManager.handle_resize_relations_config(self, event)
"""

"""
INTÉGRATION DANS relations_graph_widget.py:

1. Ajouter l'import:
   from ui.responsive_relations import (
       apply_responsive_to_graph_widget,
       ResponsiveLayoutManager
   )

2. Dans RelationsGraphWidget.__init__, après self._init_ui():
   apply_responsive_to_graph_widget(self)

3. Ajouter la méthode resizeEvent:
   def resizeEvent(self, event):
       super().resizeEvent(event)
       ResponsiveLayoutManager.handle_resize_graph_widget(self, event)
"""


# ==============================================================================
# 7. STYLES POUR DIFFÉRENTES RÉSOLUTIONS
# ==============================================================================

class BreakpointStyles:
    """Styles adaptés selon les points de rupture (breakpoints)"""
    
    # Breakpoints
    MOBILE = 480
    TABLET = 768
    DESKTOP = 1024
    WIDE = 1440
    
    @staticmethod
    def get_style_for_width(width):
        """Retourne le style adapté à la largeur donnée"""
        if width < BreakpointStyles.MOBILE:
            return BreakpointStyles._mobile_style()
        elif width < BreakpointStyles.TABLET:
            return BreakpointStyles._tablet_style()
        elif width < BreakpointStyles.DESKTOP:
            return BreakpointStyles._desktop_style()
        else:
            return BreakpointStyles._wide_style()
    
    @staticmethod
    def _mobile_style():
        return {
            'font_size': 9,
            'padding': 4,
            'button_height': 32,
            'list_height': 100
        }
    
    @staticmethod
    def _tablet_style():
        return {
            'font_size': 10,
            'padding': 6,
            'button_height': 36,
            'list_height': 130
        }
    
    @staticmethod
    def _desktop_style():
        return {
            'font_size': 11,
            'padding': 8,
            'button_height': 40,
            'list_height': 150
        }
    
    @staticmethod
    def _wide_style():
        return {
            'font_size': 12,
            'padding': 10,
            'button_height': 44,
            'list_height': 180
        }