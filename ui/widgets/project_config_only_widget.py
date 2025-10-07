#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/project_config_only_widget.py
Widget dédié à la configuration des projets et de leur ontologie,
séparé des configurations de plateformes IA.
Contient uniquement l'onglet ProjectConfigWidget.
"""

import traceback
from PyQt5 import QtWidgets

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.widgets.tabs.project_config_widget import ProjectConfigWidget
from ui.widgets.tabs.node_creation_widget import NodeCreationWidget  # <-- NOUVEL IMPORT
from ui.widgets.tabs.relation_import_widget import RelationImportWidget # <-- Import pour l'onglet RelationImportWidget, si nécessaire
from utils.tab_refresh_helper import add_refresh_to_existing_tabs


class ProjectConfigOnlyWidget(QtWidgets.QWidget):
    """
    Widget de configuration des projets et de leur ontologie,
    avec uniquement l'onglet "Configuration de Projet".
    """

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)
        print(
            "ProjectConfigOnlyWidget: Initialisation (onglet ProjectConfigWidget et NodeCreationWidget)..."
        )

        self.setMinimumSize(1400, 900)

        self.config_provider = config_provider
        self.conductor = conductor
        self.project_config_widget_instance = None
        self.node_creation_widget_instance = (
            None  # <-- Nouvelle instance pour le nouvel onglet
        )
        self.relation_import_widget_instance = (
            None  # <-- Instance pour l'onglet RelationImportWidget, si nécessaire
        )

        try:
            self._init_ui()
            print("ProjectConfigOnlyWidget: Initialisation terminée avec succès.")
        except Exception as e:
            logger.error(
                f"Erreur lors de l'initialisation de ProjectConfigOnlyWidget: {str(e)}"
            )
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

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

        title_label = QtWidgets.QLabel("Configuration de Projet et Ontologie")
        title_label.setStyleSheet(PlatformConfigStyle.get_title_style())
        main_layout.addWidget(title_label)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(PlatformConfigStyle.get_tabs_style())
        main_layout.addWidget(self.tabs)

        # Ajout de l'onglet ProjectConfigWidget
        self.project_config_widget_instance = ProjectConfigWidget(
            config_provider=self.config_provider, conductor=self.conductor, parent=self
        )
        self.tabs.addTab(self.project_config_widget_instance, "Configuration de Projet")

        # NOUVEAU: Ajout de l'onglet NodeCreationWidget
        self.node_creation_widget_instance = NodeCreationWidget(
            config_provider=self.config_provider, conductor=self.conductor, parent=self
        )

        self.tabs.addTab(
            self.node_creation_widget_instance, "Création de Nœuds"
        )  # <-- NOUVEL ONGLET

        # Ajout de l'onglet CreationImportWidget
        self.relation_import_widget_instance = RelationImportWidget(
            config_provider=self.config_provider, conductor=self.conductor, parent=self
        )
        self.tabs.addTab(
            self.relation_import_widget_instance, "Relations des Importations"
        )  # <-- Onglet RelationImportWidget

        # La barre d'onglets doit être visible car il y a maintenant deux onglets
        self.tabs.tabBar().setVisible(True)  # <-- MODIFIÉ ICI

        self.setLayout(main_layout)

    def _force_enable_all_widgets(self):
        if self.project_config_widget_instance:
            self.project_config_widget_instance.setEnabled(True)
            print("DEBUG: ProjectConfigWidget instance activée")
            for child in self.project_config_widget_instance.findChildren(
                QtWidgets.QWidget
            ):
                child.setEnabled(True)

        # NOUVEAU: Activer le NodeCreationWidget
        if self.node_creation_widget_instance:
            self.node_creation_widget_instance.setEnabled(True)
            print("DEBUG: NodeCreationWidget instance activée")
            for child in self.node_creation_widget_instance.findChildren(
                QtWidgets.QWidget
            ):
                child.setEnabled(True)

        # NOUVEAU: Activer le RelationImportWidget
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
        print("ProjectConfigOnlyWidget: Refresh appelé.")
        if self.project_config_widget_instance and hasattr(
            self.project_config_widget_instance, "refresh"
        ):
            self.project_config_widget_instance.refresh()
        # NOUVEAU: Rafraîchir le NodeCreationWidget
        if self.node_creation_widget_instance and hasattr(
            self.node_creation_widget_instance, "refresh"
        ):
            self.node_creation_widget_instance.refresh()
        # NOUVEAU: Rafraîchir le RelationImportWidget
        if self.relation_import_widget_instance and hasattr(
            self.relation_import_widget_instance, "refresh"
        ):
            self.relation_import_widget_instance.refresh()

        self._force_enable_all_widgets()
