#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
import logging
import json
import math
from ui.styles.theme import Theme
import csv
import pandas as pd
from xml.etree.ElementTree import Element, tostring
from ui.widgets.tabs.final_test_widget import SimpleTestWorker
from utils.selector_generator import UniversalSelectorGenerator
from datetime import datetime
from ui.styles.platform_config_style import PlatformConfigStyle

logger = logging.getLogger(__name__)

class DatasetGenerationWidget(QtWidgets.QWidget):
    """
    Widget amélioré pour la gestion de la génération de datasets avec une structure hiérarchique
    """

    def __init__(self, conductor=None, parent=None):
        super().__init__(parent)
        logger.info("=== DÉBUT INITIALISATION DatasetGenerationWidget ===")
        self.data = {'categories': []}
        self.current_category_index = -1
        self.current_subcategory_index = -1
        self.current_theme_index = -1
        self.conductor = conductor
        self.running_workers = []
        self.current_worker_index = -1
        self.results = []
        self.selector_generator = UniversalSelectorGenerator()
        self.current_platform = None
        self.current_profile = None
        self.profiles = {}
        self.dataset_generator_widget = None
        self.loaded_project_data = None

        if self.conductor:
            logger.info("Conducteur initialisé dans le constructeur")
        else:
            logger.warning("Aucun conducteur fourni lors de l'initialisation")

        self._init_ui()
        logger.info("Interface initialisée via _init_ui")
        self._initialize_default_project()
        logger.info("Projet par défaut initialisé")
        self._update_summary()
        logger.info("Résumé mis à jour")
        logger.info("=== FIN INITIALISATION DatasetGenerationWidget ===")

    def _create_projet_tab(self, parent):
        """Crée l'onglet Projet avec aperçu de structure hiérarchique, bouton pour afficher la liste des projets et tableau"""
        layout = QtWidgets.QHBoxLayout(parent)
        layout.setSpacing(20)

        # ======= COLONNE GAUCHE : Aperçu de la structure =======
        chart_group = QtWidgets.QGroupBox("📊 Aperçu de la structure")
        chart_group.setStyleSheet(self._get_group_style())
        chart_layout = QtWidgets.QVBoxLayout(chart_group)

        # Bouton pour afficher/masquer la liste des projets
        self.toggle_projects_btn = QtWidgets.QPushButton("📋 Afficher la liste des projets")
        self.toggle_projects_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        self.toggle_projects_btn.setCheckable(True)
        self.toggle_projects_btn.toggled.connect(self._toggle_project_list)
        chart_layout.addWidget(self.toggle_projects_btn)

        # Tableau pour afficher la liste des projets (initialement caché)
        self.project_table = QtWidgets.QTableWidget()
        self.project_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #fafafa;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: %s;
                color: white;
            }
        """ % Theme.SECONDARY_COLOR)
        self.project_table.setColumnCount(3)
        self.project_table.setHorizontalHeaderLabels(["Nom du projet", "Description", "Date de création"])
        self.project_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.project_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.project_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.project_table.itemDoubleClicked.connect(self._load_project_from_table)
        self.project_table.setVisible(False)  # Caché par défaut
        chart_layout.addWidget(self.project_table)

        # QTextBrowser pour l'aperçu de la structure
        self.apercu_view = QtWidgets.QTextBrowser()
        self.apercu_view.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        chart_layout.addWidget(self.apercu_view)

        # Bouton pour actualiser la vue
        refresh_btn = QtWidgets.QPushButton("🔄 Actualiser la structure")
        refresh_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        refresh_btn.clicked.connect(self._display_project_structure_in_overview)
        chart_layout.addWidget(refresh_btn)

        # ======= COLONNE DROITE : Configuration =======
        config_group = QtWidgets.QGroupBox("🛠️ Configuration")
        config_group.setStyleSheet(self._get_group_style())
        config_layout = QtWidgets.QVBoxLayout(config_group)

        # Ajouter le sélecteur de projet au début
        self._add_project_loader_to_dataset_tab(config_layout)

        self.selection_label = QtWidgets.QLabel("Sélectionnez un thème à configurer")
        self.selection_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #34495e;
            padding: 10px;
            background-color: #ecf0f1;
            border-radius: 6px;
        """)
        config_layout.addWidget(self.selection_label)

        form_layout = QtWidgets.QFormLayout()

        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        self.platform_status = QtWidgets.QLabel("Sélectionnez une plateforme...")
        self.platform_status.setWordWrap(True)
        platform_layout.addWidget(self.platform_status)

        prompt_label = QtWidgets.QLabel("📝 Description:")
        prompt_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.prompt_edit = QtWidgets.QTextEdit()
        self.prompt_edit.setMinimumHeight(100)
        self.prompt_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                background-color: white;
            }
            QTextEdit:focus {
                border-color: %s;
            }
        """ % Theme.SECONDARY_COLOR)
        self.prompt_edit.setPlaceholderText("Entrez la description pour la génération du dataset...")
        self.prompt_edit.textChanged.connect(self._on_prompt_changed)

        #output_format_label = QtWidgets.QLabel("📋 Format de sortie:")
        #output_format_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.output_format_combo = QtWidgets.QComboBox()
        self.output_format_combo.addItems(["JSON", "CSV", "XML", "JSONL", "Parquet"])
        self.output_format_combo.setStyleSheet(self._get_combo_style())
        self.output_format_combo.currentTextChanged.connect(self._on_output_format_changed)

        sample_label = QtWidgets.QLabel("📊 Nombre d'échantillons:")
        sample_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.sample_count_spin = QtWidgets.QSpinBox()
        self.sample_count_spin.setRange(1, 100000)
        self.sample_count_spin.setValue(100)
        self.sample_count_spin.setStyleSheet(self._get_combo_style())
        self.sample_count_spin.valueChanged.connect(self._on_sample_count_changed)

        training_tech_label = QtWidgets.QLabel("🧠 Technique d'entraînement:")
        training_tech_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.training_tech_combo = QtWidgets.QComboBox()
        self.training_tech_combo.addItems([
            "Full SFT",
            "DPO"
        ])
        self.training_tech_combo.setStyleSheet(self._get_combo_style())
        self.training_tech_combo.currentTextChanged.connect(self._on_training_tech_changed)

        form_layout.addRow(platform_group)
        form_layout.addRow(prompt_label, self.prompt_edit)
        form_layout.addRow(output_format_label, self.output_format_combo)
        form_layout.addRow(sample_label, self.sample_count_spin)
        form_layout.addRow(training_tech_label, self.training_tech_combo)

        config_layout.addLayout(form_layout)

        self.generate_button = QtWidgets.QPushButton("🚀 Génération")
        self.generate_button.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        self.generate_button.clicked.connect(self._generate_dataset)
        config_layout.addWidget(self.generate_button)

        layout.addWidget(chart_group, 2)
        layout.addWidget(config_group, 1)

        # Afficher la structure au chargement
        self._display_project_structure_in_overview()
        # Charger la liste des projets dans le tableau
        self._populate_project_table()

    def _toggle_project_list(self, checked):
        """Affiche ou masque la liste des projets dans le tableau"""
        logger.info(f"Toggle project list: {'Afficher' if checked else 'Masquer'}")
        self.project_table.setVisible(checked)
        self.apercu_view.setVisible(not checked)
        self.toggle_projects_btn.setText("📊 Afficher l'aperçu de la structure" if checked else "📋 Afficher la liste des projets")
        if checked:
            self._populate_project_table()

    def _populate_project_table(self):
        """Remplit le tableau avec la liste des projets depuis la base de données"""
        logger.info("=== DÉBUT _populate_project_table ===")

        self.project_table.setRowCount(0)  # Réinitialiser le tableau

        projects = self._load_projects_from_database()
        if not projects:
            logger.warning("Aucun projet trouvé pour remplir le tableau")
            self.project_table.setRowCount(1)
            item = QtWidgets.QTableWidgetItem("Aucun projet disponible")
            item.setFlags(Qt.ItemIsEnabled)
            self.project_table.setItem(0, 0, item)
            self.project_table.setSpan(0, 0, 1, 3)  # Étendre sur toutes les colonnes
            return

        self.project_table.setRowCount(len(projects))
        for row, project in enumerate(projects):
            project_name = project.get('name', 'Projet sans nom')
            description = project.get('description', 'Aucune description')
            created_at = project.get('created_at', 'Inconnue')

            # Nom du projet
            name_item = QtWidgets.QTableWidgetItem(project_name)
            name_item.setData(Qt.UserRole, project)  # Stocker les données complètes
            self.project_table.setItem(row, 0, name_item)

            # Description
            desc_item = QtWidgets.QTableWidgetItem(description)
            self.project_table.setItem(row, 1, desc_item)

            # Date de création
            date_item = QtWidgets.QTableWidgetItem(created_at)
            self.project_table.setItem(row, 2, date_item)

        # Ajuster la taille des colonnes
        self.project_table.resizeColumnsToContents()
        self.project_table.setColumnWidth(1, max(200, self.project_table.columnWidth(1)))  # Description plus large
        logger.info(f"Tableau rempli avec {len(projects)} projets")

    def _load_project_from_table(self, item):
        """Charge un projet lorsque l'utilisateur double-clique sur une ligne du tableau"""
        row = item.row()
        project_item = self.project_table.item(row, 0)
        if not project_item:
            return

        project_data = project_item.data(Qt.UserRole)
        project_name = project_data.get('name', 'Projet sans nom')
        logger.info(f"Chargement du projet depuis le tableau: {project_name}")

        try:
            if self.conductor and hasattr(self.conductor, 'database'):
                project_data = self.conductor.database.get_dataset_projet(project_name)
                if project_data:
                    self.loaded_project_data = project_data
                    self._convert_and_load_project_structure(project_data)
                    self._display_project_structure_in_overview()
                    self.project_selector_combo.setCurrentText(project_name)
                    QtWidgets.QMessageBox.information(
                        self, "Projet chargé",
                        f"Le projet '{project_name}' a été chargé avec succès."
                    )
                    logger.info(f"Projet '{project_name}' chargé avec succès depuis le tableau")
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Erreur",
                        f"Impossible de charger les détails du projet '{project_name}'."
                    )
                    logger.warning(f"Projet '{project_name}' non trouvé dans la base de données")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Erreur",
                f"Erreur lors du chargement du projet: {str(e)}"
            )
            logger.error(f"Erreur lors du chargement du projet {project_name}: {e}")

    # Le reste des méthodes reste inchangé, sauf pour _display_project_structure_in_overview
    def _display_project_structure_in_overview(self):
        """
        Affiche la structure hiérarchique du projet chargé depuis la base de données
        """
        logger.info("=== DÉBUT _display_project_structure_in_overview ===")

        if not hasattr(self, 'apercu_view'):
            logger.error("Widget apercu_view non trouvé")
            return

        try:
            # Obtenir les données du projet depuis la base de données
            project_data = self._get_current_project_structure()
            logger.info(f"Données récupérées: {project_data is not None}")

            if project_data:
                # Générer et afficher l'HTML avec les données réelles
                html_content = self._generate_structure_html(project_data)
            else:
                # Afficher un message pour charger un projet depuis la base de données
                html_content = self._generate_no_project_html()

            # Mettre à jour l'aperçu uniquement si le tableau n'est pas visible
            if not self.project_table.isVisible():
                self.apercu_view.setHtml(html_content)
                self.apercu_view.update()
                logger.info("Contenu HTML affiché dans apercu_view")
            else:
                logger.info("Tableau des projets visible, aperçu non mis à jour")

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage de la structure: {str(e)}")
            error_html = f"""
                <div style='padding: 20px; text-align: center; color: #856404;'>
                    <h3>⚠️ Erreur lors du chargement de la structure</h3>
                    <p>Une erreur s'est produite : {str(e)}</p>
                    <p>Veuillez vérifier la base de données ou contacter le support.</p>
                </div>
            """
            self.apercu_view.setHtml(error_html)

        logger.info("=== FIN _display_project_structure_in_overview ===")

    # Les autres méthodes restent inchangées...

class CategoryItemDelegate(QtWidgets.QStyledItemDelegate):
    """Délégué personnalisé pour les éléments de liste avec une croix de suppression au survol"""
    def __init__(self, delete_callback, parent=None):
        super().__init__(parent)
        self.delete_callback = delete_callback

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if option.state & QtWidgets.QStyle.State_MouseOver:
            rect = option.rect
            cross_rect = QtCore.QRect(rect.right() - 20, rect.top() + 5, 15, 15)

            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtGui.QPen(QtGui.QColor(Theme.SECONDARY_COLOR), 2))
            painter.drawLine(cross_rect.topLeft(), cross_rect.bottomRight())
            painter.drawLine(cross_rect.bottomLeft(), cross_rect.topRight())
            painter.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() == QtCore.QEvent.MouseButtonRelease and
                event.button() == QtCore.Qt.LeftButton):
            rect = option.rect
            cross_rect = QtCore.QRect(rect.right() - 20, rect.top() + 5, 15, 15)
            if cross_rect.contains(event.pos()):
                self.delete_callback(index.row())
                return True
        return super().editorEvent(event, model, option, index)

class DatasetCreationWidget(DatasetGenerationWidget):
    """
    Alias pour gérer la génération de datasets avec compatibilité ascendante
    """
    pass