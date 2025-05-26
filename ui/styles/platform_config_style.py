@staticmethod
def get_tabs_style():
    """Style pour les onglets"""
    return f"""
            QTabWidget::pane {{
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
            }}
            QTabBar::tab {{
                background-color: {PlatformConfigStyle.BACKGROUND_COLOR};
                color: {PlatformConfigStyle.PRIMARY_COLOR};
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background-color: {PlatformConfigStyle.PRIMARY_COLOR};
                color: white;
                border-bottom: 1px solid white;
            }}
            QTabBar::tab:hover {{
                background-color: #F8E6E3;
            }}
        """  # !/usr/bin/env python


# -*- coding: utf-8 -*-

"""
Liris/ui/styles/platform_config_style.py
"""


class PlatformConfigStyle:
    """Styles pour les widgets de configuration des plateformes"""

    # Constantes de layout
    SPACING = 10
    MARGIN = 15

    # Couleurs principales - MÊME COULEUR QUE THEME.PY
    PRIMARY_COLOR = "#A23B2D"  # Rouge brique (comme Theme.PRIMARY_COLOR)
    SECONDARY_COLOR = "#D35A4A"  # Rouge brique clair (comme Theme.SECONDARY_COLOR)
    SUCCESS_COLOR = "#4CAF50"
    WARNING_COLOR = "#FF9800"
    ERROR_COLOR = "#F44336"
    BACKGROUND_COLOR = "#F9F6F6"  # Beige très clair (comme Theme.BACKGROUND_COLOR)

    @staticmethod
    def get_title_style():
        """Style pour les titres principaux"""
        return f"""
            font-size: 18px;
            font-weight: bold;
            color: {PlatformConfigStyle.PRIMARY_COLOR};
            padding: 10px;
            margin-bottom: 10px;
            background-color: {PlatformConfigStyle.BACKGROUND_COLOR};
            border-radius: 4px;
        """

    @staticmethod
    def get_explanation_style():
        """Style pour les textes d'explication"""
        return f"""
            font-size: 12px;
            color: #black;
            padding: 8px;
            background-color: #B3D9FF;
            border-left: 3px solid #66CCFF;
            border-radius: 4px;
            margin-bottom: 10px;
        """

    @staticmethod
    def get_group_box_style():
        """Style pour les groupes de widgets"""
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12px;
                color: {PlatformConfigStyle.PRIMARY_COLOR};
                border: 2px solid #DDDDDD;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }}
        """

    @staticmethod
    def get_input_style():
        """Style pour les champs de saisie"""
        return f"""
            border: 1px solid #CCCCCC;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 11px;
            background-color: white;
            selection-background-color: {PlatformConfigStyle.SECONDARY_COLOR};
        """

    @staticmethod
    def get_button_style():
        """Style pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {PlatformConfigStyle.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {PlatformConfigStyle.SECONDARY_COLOR};
            }}
            QPushButton:pressed {{
                background-color: #922E23;
            }}
            QPushButton:disabled {{
                background-color: #CCCCCC;
                color: #888888;
            }}
        """

    @staticmethod
    def get_list_style():
        """Style pour les listes principales"""
        return f"""
            QListWidget {{
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: {PlatformConfigStyle.BACKGROUND_COLOR};
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid #EEEEEE;
            }}
            QListWidget::item:selected {{
                background-color: {PlatformConfigStyle.PRIMARY_COLOR};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: #A23B2D;
            }}
        """

    @staticmethod
    def get_small_list_style():
        """Style pour les petites listes"""
        return f"""
            QListWidget {{
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                background-color: white;
                font-size: 10px;
                max-height: 120px;
            }}
            QListWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid #EEEEEE;
            }}
            QListWidget::item:selected {{
                background-color: {PlatformConfigStyle.PRIMARY_COLOR};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: #F8E6E3;
            }}
        """

    @staticmethod
    def get_tabs_style():
        """Style pour les onglets"""
        return f"""
            QTabWidget::pane {{
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
            }}
            QTabBar::tab {{
                background-color: {PlatformConfigStyle.BACKGROUND_COLOR};
                color: {PlatformConfigStyle.PRIMARY_COLOR};
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background-color: {PlatformConfigStyle.SECONDARY_COLOR};
                color: white;
                border-bottom: 1px solid white;
            }}
            QTabBar::tab:hover {{
                background-color: #757575;
                color: white;
            }}
        """

    @staticmethod
    def get_status_normal_style():
        """Style pour les statuts normaux"""
        return f"""
            color: {PlatformConfigStyle.PRIMARY_COLOR};
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            background-color: {PlatformConfigStyle.BACKGROUND_COLOR};
            border-radius: 4px;
            border: 1px solid #DDDDDD;
        """

    @staticmethod
    def get_status_success_style():
        """Style pour les statuts de succès"""
        return f"""
            color: {PlatformConfigStyle.SUCCESS_COLOR};
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            background-color: #E8F5E8;
            border-radius: 4px;
            border: 1px solid {PlatformConfigStyle.SUCCESS_COLOR};
        """

    @staticmethod
    def get_status_error_style():
        """Style pour les statuts d'erreur"""
        return f"""
            color: {PlatformConfigStyle.ERROR_COLOR};
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            background-color: #FFEBEE;
            border-radius: 4px;
            border: 1px solid {PlatformConfigStyle.ERROR_COLOR};
        """

    @staticmethod
    def get_status_warning_style():
        """Style pour les statuts d'avertissement"""
        return f"""
            color: {PlatformConfigStyle.WARNING_COLOR};
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            background-color: #FFF3E0;
            border-radius: 4px;
            border: 1px solid {PlatformConfigStyle.WARNING_COLOR};
        """