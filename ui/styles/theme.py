#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/styles/theme.py
"""

from PyQt5 import QtGui


class Theme:
    """Thème global de l'application"""

    # Couleurs
    PRIMARY_COLOR = "#A23B2D"  # Rouge brique
    SECONDARY_COLOR = "#D35A4A"  # Rouge brique clair
    BACKGROUND_COLOR = "#FFFFFF"  # Blanc très clair
    LIGHT_BACKGROUND = "#FFFFFF"  # Blanc pour la fenêtre principale
    TEXT_COLOR = "#333333"  # Gris foncé
    ACCENT_COLOR = "#E8E0DF"  # Gris clair pour les accents

    # Tailles de police
    FONT_SIZE_TITLE = 28
    FONT_SIZE_SUBTITLE = 20
    FONT_SIZE_HEADER = 16
    FONT_SIZE_NORMAL = 14

    # Espacements
    PADDING_NORMAL = 10
    PADDING_LARGE = 20
    PADDING_SMALL = 5
    SPACING_NORMAL = 10
    SPACING_LARGE = 20
    SPACING_SMALL = 5

    # Bordures
    BORDER_RADIUS = 4
    BORDER_WIDTH = 1
    BORDER_WIDTH_FOCUS = 2

    # Dimensions
    BUTTON_MIN_WIDTH = 120
    BUTTON_PADDING = "8px 20px"

    @staticmethod
    def get_global_stylesheet():
        """Retourne le stylesheet global de l'application"""
        return f"""
        /* Application globale */
        QMainWindow {{
            background-color: {Theme.LIGHT_BACKGROUND};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QWidget {{
            background-color: {Theme.BACKGROUND_COLOR};
            color: {Theme.TEXT_COLOR};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        /* Menu Bar */
        QMenuBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            color: white;
            padding: {Theme.PADDING_SMALL}px;
            border: none;
        }}

        QMenuBar::item {{
            background-color: transparent;
            padding: {Theme.PADDING_SMALL}px 15px;
            color: white;
        }}

        QMenuBar::item:selected {{
            background-color: {Theme.SECONDARY_COLOR};
        }}

        QMenu {{
            background-color: white;
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            color: {Theme.TEXT_COLOR};
        }}

        QMenu::item {{
            padding: 8px 30px;
        }}

        QMenu::item:selected {{
            background-color: {Theme.ACCENT_COLOR};
            color: {Theme.TEXT_COLOR};
        }}

        QMenu::separator {{
            height: {Theme.BORDER_WIDTH}px;
            background: {Theme.ACCENT_COLOR};
            margin: {Theme.PADDING_SMALL}px 0;
        }}

        /* Tabs */
        QTabWidget::pane {{
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            background: white;
            margin-top: 0px;
            padding: 10px;
        }}

        QTabBar {{
            background: transparent;
        }}

        QTabBar::tab {{
            background: #F5F5F5;
            color: {Theme.TEXT_COLOR};
            border: none;
            border-radius: 6px;
            padding: 10px 24px;
            margin-right: 8px;
            margin-top: 8px;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 13px;
            min-width: 90px;
            min-height: 36px;
            max-height: 36px;
        }}

        QTabBar::tab:selected {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                         stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            color: white;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}

        QTabBar::tab:hover:!selected {{
            background: #EBEBEB;
            color: {Theme.PRIMARY_COLOR};
        }}

        QTabBar::tab:first {{
            margin-left: 15px;
        }}

        /* Group Box */
        QGroupBox {{
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            margin-top: 1em;
            padding-top: {Theme.PADDING_NORMAL}px;
            font-weight: bold;
            background-color: white;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {Theme.PADDING_NORMAL}px;
            padding: 0 {Theme.PADDING_SMALL}px 0 {Theme.PADDING_SMALL}px;
        }}

        /* Buttons */
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            color: white;
            border: none;
            padding: {Theme.BUTTON_PADDING};
            border-radius: {Theme.BORDER_RADIUS}px;
            font-weight: bold;
            min-width: {Theme.BUTTON_MIN_WIDTH}px;
        }}

        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.SECONDARY_COLOR}, stop:1 #C84F3F);
        }}

        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #922E23, stop:1 #7A2519);
        }}

        QPushButton:disabled {{
            background-color: #CCCCCC;
        }}

        /* Input Fields */
        QLineEdit, QTextEdit, QComboBox {{
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            padding: 8px;
            background-color: white;
            selection-background-color: {Theme.PRIMARY_COLOR};
            selection-color: white;
        }}

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: {Theme.BORDER_WIDTH_FOCUS}px solid {Theme.PRIMARY_COLOR};
        }}

        /* Lists and Tables */
        QListWidget {{
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            background-color: white;
            selection-background-color: {Theme.PRIMARY_COLOR};
            outline: none;
        }}

        QListWidget::item {{
            padding: {Theme.PADDING_SMALL}px;
        }}

        QListWidget::item:selected {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            color: white;
        }}

        QListWidget::item:hover {{
            background-color: {Theme.SECONDARY_COLOR};
            color: white;
        }}

        QTableWidget {{
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            background-color: white;
            gridline-color: #E0E0E0;
        }}

        QHeaderView::section {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            color: white;
            padding: 8px;
            border: none;
            font-weight: bold;
        }}

        /* Progress Bar */
        QProgressBar {{
            border: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            border-radius: {Theme.BORDER_RADIUS}px;
            text-align: center;
            background-color: #F0F0F0;
            font-weight: bold;
        }}

        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {Theme.PRIMARY_COLOR}, stop:1 {Theme.SECONDARY_COLOR});
            border-radius: {Theme.BORDER_RADIUS}px;
        }}

        /* Status Bar */
        QStatusBar {{
            background-color: {Theme.BACKGROUND_COLOR};
            border-top: {Theme.BORDER_WIDTH}px solid {Theme.ACCENT_COLOR};
            color: {Theme.TEXT_COLOR};
        }}

        QStatusBar QLabel {{
            color: {Theme.TEXT_COLOR};
            font-weight: bold;
            padding: 0 {Theme.PADDING_NORMAL}px;
        }}
        """

    @staticmethod
    def get_button_style(color=None):
        """Retourne un style spécifique pour les boutons"""
        color = color or Theme.PRIMARY_COLOR
        secondary = Theme.SECONDARY_COLOR
        return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {color}, stop:1 {secondary});
            color: white;
            border: none;
            padding: {Theme.BUTTON_PADDING};
            border-radius: {Theme.BORDER_RADIUS}px;
            font-weight: bold;
            min-width: {Theme.BUTTON_MIN_WIDTH}px;
        }}
        """