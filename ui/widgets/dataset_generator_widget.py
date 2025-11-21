#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ui.localization.translator import tr
from ui.styles.theme import Theme

from utils.dataset_database import DatasetDatabase
from utils.dataset_project_manager import DatasetProjectManager

from ui.widgets.tabs.dataset_config_tab import DatasetConfigTab
from ui.widgets.tabs.dataset_preview_tab import DatasetPreviewTab

logger = logging.getLogger(__name__)


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

        self._init_ui()

    def _init_ui(self):
        """Configure user interface"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: #f5f7fa;
            }}
            QTabBar::tab {{
                background-color: #e8ecef;
                padding: 12px 30px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                font-size: 13px;
                min-width: 180px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.PRIMARY_COLOR}, 
                    stop:1 {Theme.SECONDARY_COLOR});
                color: white;
            }}
            QTabBar::tab:hover {{
                background-color: #d0d7de;
            }}
        """)

        # Configuration tab
        self.config_tab = DatasetConfigTab(
            self.project_manager, 
            self.config_data,
            parent=self
        )
        self.tab_widget.addTab(self.config_tab, tr("dataset.tab_config"))

        # Dataset preview tab
        self.preview_tab = DatasetPreviewTab(
            self.project_manager,
            self.config_data,
            parent=self
        )
        self.tab_widget.addTab(self.preview_tab, tr("dataset.tab_preview"))

        # Connect signals
        self.config_tab.project_saved.connect(self._on_project_saved)
        self.config_tab.preview_updated.connect(self.preview_tab.update_preview)

        main_layout.addWidget(self.tab_widget)

    def _on_project_saved(self):
        """Handle project saved event"""
        self.preview_tab.refresh_projects()
        self.tab_widget.setCurrentIndex(1)
        QtWidgets.QMessageBox.information(
            self, 
            tr("dataset.success"), 
            f"{tr('dataset.project_saved')}: '{self.project_manager.current_project_name}'"
        )

    # ========== PUBLIC METHODS ==========

    def set_conductor(self, conductor):
        """Set conductor for browser control"""
        self.conductor = conductor
        logger.info("Conductor set for DatasetGeneratorWidget")

    def set_platforms(self, platforms):
        """Set available platforms"""
        self.platforms = platforms if platforms else []
        logger.info(f"Platforms set for DatasetGeneratorWidget: {len(self.platforms)} platforms")

    def set_database(self, database):
        """Set database connection"""
        pass

    def refresh(self):
        """Refresh widget data"""
        self.config_tab.refresh()
        self.preview_tab.refresh_projects()

    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'db'):
            self.db.close()
            logger.info("DB connection closed")