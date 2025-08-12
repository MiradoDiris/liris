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
        
        self.data = {'categories': []}  # Structure de données interne
        self.current_category_index = -1
        self.current_subcategory_index = -1
        self.current_theme_index = -1
        self.conductor = conductor
        self.running_workers = []
        self.current_worker_index = -1
        self.results = []
        self.selector_generator = UniversalSelectorGenerator()
        self.current_platform = None  # Store selected platform
        self.current_profile = None  # Store platform profile
        self.profiles = {}  # Store platform profiles
        
        if self.conductor:
            logger.info("Conducteur initialisé dans le constructeur de DatasetGenerationWidget")
        else:
            logger.warning("Aucun conducteur fourni lors de l'initialisation")
        
        self._init_ui()
        self._update_summary()

    def set_conductor(self, conductor):
        """Définir le conducteur pour le contrôle du navigateur et des entrées."""
        self.conductor = conductor
        logger.info("Conducteur défini pour DatasetGenerationWidget")

    def set_platforms(self, profiles):
        """
        Définit la liste des profils de plateformes disponibles
        Args:
            profiles (dict): Dictionnaire des profils de plateformes {name: profile_data}
        """
        self.profiles = profiles
        self.platforms = self.conductor.database.get_all_platforms()
         
        for name in self.profiles:
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked)
             
        logger.info(f"Chargé {len(profiles)} profils de plateformes.")
    def _on_platform_changed(self, platform_name):
        """
        Handle platform selection and detect the selected platform.
        Args:
            platform_name (str): Name of the selected platform.
        """
        try:
            if platform_name and platform_name != "-- Sélectionner --":
                self.current_platform = platform_name
                self.current_profile = self.profiles.get(platform_name, {})
                logger.info(f"Platform detected: {self.current_platform}")
                logger.debug(f"Profile loaded for {platform_name}: {json.dumps(self.current_profile, indent=2)}")
                self._update_platform_status()
                self._load_and_sync_configuration()
            else:
                self.current_platform = None
                self.current_profile = None
                logger.info("No platform selected, resetting interface.")
                self._reset_interface()

            self._update_test_button_state()
        except Exception as e:
            logger.error(f"Error handling platform change: {e}")
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()
    def _init_ui(self):
        """Configure l'interface utilisateur améliorée"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: %s;
                color: white;
            }
        """ % Theme.SECONDARY_COLOR)
        
        ajouter_tab = QtWidgets.QWidget()
        self._create_ajouter_tab(ajouter_tab)
        self.tab_widget.addTab(ajouter_tab, "➕ Ajouter")
        
        projet_tab = QtWidgets.QWidget()
        self._create_projet_tab(projet_tab)
        self.tab_widget.addTab(projet_tab, "📊 Projet")
        
        main_layout.addWidget(self.tab_widget)

        save_btn = QtWidgets.QPushButton("💾 Sauvegarder Projet")
        save_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        save_btn.clicked.connect(self._save_configuration)
        main_layout.addWidget(save_btn)

    def _create_ajouter_tab(self, parent):
        """Crée l'onglet Ajouter avec une disposition verticale"""
        layout = QtWidgets.QVBoxLayout(parent)
        layout.setSpacing(20)
        
        new_project_btn = QtWidgets.QPushButton("📋 Nouveau Projet")
        new_project_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        new_project_btn.clicked.connect(self._new_project)
        layout.addWidget(new_project_btn)
        
        cat_group = QtWidgets.QGroupBox("📁 Catégories")
        cat_group.setStyleSheet(self._get_group_style())
        cat_layout = QtWidgets.QVBoxLayout(cat_group)
        
        self.category_list_widget = QtWidgets.QListWidget()
        self.category_list_widget.setStyleSheet(self._get_list_style())
        self.category_list_widget.setItemDelegate(CategoryItemDelegate(self._delete_category))
        self.category_list_widget.currentItemChanged.connect(self._on_category_selected)
        cat_layout.addWidget(self.category_list_widget)
        
        cat_btn_layout = QtWidgets.QHBoxLayout()
        add_cat_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_cat_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_cat_btn.clicked.connect(self._add_category)
        edit_cat_btn = QtWidgets.QPushButton("✏️ Éditer")
        edit_cat_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_cat_btn.clicked.connect(self._edit_category)
        cat_btn_layout.addWidget(add_cat_btn)
        cat_btn_layout.addWidget(edit_cat_btn)
        cat_layout.addLayout(cat_btn_layout)
        
        subcat_group = QtWidgets.QGroupBox("📂 Sous-catégories")
        subcat_group.setStyleSheet(self._get_group_style())
        subcat_layout = QtWidgets.QVBoxLayout(subcat_group)
        
        self.subcategory_list_widget = QtWidgets.QListWidget()
        self.subcategory_list_widget.setStyleSheet(self._get_list_style())
        self.subcategory_list_widget.setItemDelegate(CategoryItemDelegate(self._delete_subcategory))
        self.subcategory_list_widget.currentItemChanged.connect(self._on_subcategory_selected)
        subcat_layout.addWidget(self.subcategory_list_widget)
        
        subcat_btn_layout = QtWidgets.QHBoxLayout()
        add_subcat_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_subcat_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_subcat_btn.clicked.connect(self._add_subcategory)
        edit_subcat_btn = QtWidgets.QPushButton("✏️ Éditer")
        edit_subcat_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_subcat_btn.clicked.connect(self._edit_subcategory)
        subcat_btn_layout.addWidget(add_subcat_btn)
        subcat_btn_layout.addWidget(edit_subcat_btn)
        subcat_layout.addLayout(subcat_btn_layout)
        
        theme_group = QtWidgets.QGroupBox("🎨 Thèmes")
        theme_group.setStyleSheet(self._get_group_style())
        theme_layout = QtWidgets.QVBoxLayout(theme_group)
        
        self.theme_list_widget = QtWidgets.QListWidget()
        self.theme_list_widget.setStyleSheet(self._get_list_style())
        self.theme_list_widget.setItemDelegate(CategoryItemDelegate(self._delete_theme))
        self.theme_list_widget.currentItemChanged.connect(self._on_theme_selected)
        theme_layout.addWidget(self.theme_list_widget)
        
        theme_btn_layout = QtWidgets.QHBoxLayout()
        add_theme_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_theme_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_theme_btn.clicked.connect(self._add_theme)
        edit_theme_btn = QtWidgets.QPushButton("✏️ Éditer")
        edit_theme_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_theme_btn.clicked.connect(self._edit_theme)
        theme_btn_layout.addWidget(add_theme_btn)
        theme_btn_layout.addWidget(edit_theme_btn)
        theme_layout.addLayout(theme_btn_layout)

        layout.addWidget(cat_group)
        layout.addWidget(subcat_group)
        layout.addWidget(theme_group)

    def _create_projet_tab(self, parent):
        """Crée l'onglet Projet avec un graphique en anneau et une configuration"""
        layout = QtWidgets.QHBoxLayout(parent)
        layout.setSpacing(20)
        
        chart_group = QtWidgets.QGroupBox("📊 Aperçu de la structure")
        chart_group.setStyleSheet(self._get_group_style())
        chart_layout = QtWidgets.QVBoxLayout(chart_group)
        
        self.chart_widget = PieChartWidget(self.data, self)
        chart_layout.addWidget(self.chart_widget)
        
        config_group = QtWidgets.QGroupBox("🛠️ Configuration")
        config_group.setStyleSheet(self._get_group_style())
        config_layout = QtWidgets.QVBoxLayout(config_group)
         
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
        
        output_format_label = QtWidgets.QLabel("📋 Format de sortie:")
        output_format_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
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
        #config_layout.addWidget(platforms_group)
        
        self.generate_button = QtWidgets.QPushButton("🚀 Génération")
        self.generate_button.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        self.generate_button.clicked.connect(self._generate_dataset)
        config_layout.addWidget(self.generate_button)
        
        layout.addWidget(chart_group, 2)
        layout.addWidget(config_group, 1)

    def _get_group_style(self):
        """Obtenir un style cohérent pour les groupes"""
        return """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
        """

    def _get_list_style(self):
        """Obtenir un style cohérent pour les widgets de liste"""
        return """
            QListWidget {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: %s;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """ % Theme.SECONDARY_COLOR

    def _get_button_style(self, color):
        """Obtenir un style cohérent pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.2)};
            }}
        """

    def _get_combo_style(self):
        """Obtenir un style cohérent pour les boîtes de sélection"""
        return """
            QComboBox, QSpinBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                min-width: 150px;
            }
            QComboBox:focus, QSpinBox:focus {
                border-color: %s;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7f8c8d;
            }
        """ % Theme.SECONDARY_COLOR

    def _darken_color(self, color, factor=0.1):
        """Assombrir une couleur hexadécimale par un facteur"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return '#%02x%02x%02x' % darkened

    def _update_summary(self):
        """Mettre à jour le graphique en anneau"""
        if hasattr(self, 'chart_widget'):
            self.chart_widget.update_data(self.data, 
                                       self.current_category_index,
                                       self.current_subcategory_index,
                                       self.current_theme_index)

    def _update_selection_label(self):
        """Mettre à jour l'indicateur de sélection"""
        if not hasattr(self, 'selection_label'):
            return
            
        if self.current_theme_index != -1:
            theme_data = self._get_current_theme_data()
            if theme_data:
                cat_name = self.data['categories'][self.current_category_index]['name']
                subcat_name = self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['name']
                theme_name = theme_data['name']
                self.selection_label.setText(f"🎨 Configuration : {cat_name} → {subcat_name} → {theme_name}")
        else:
            self.selection_label.setText("Sélectionnez un thème à configurer")

    def _load_categories(self):
        """Charger les catégories depuis les données internes"""
        self.category_list_widget.clear()
        self.subcategory_list_widget.clear()
        self.theme_list_widget.clear()
        self.current_category_index = -1
        self.current_subcategory_index = -1
        self.current_theme_index = -1

        categories = self.data.get('categories', [])
        for category_data in categories:
            item_text = category_data.get('name')
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(Qt.UserRole, category_data)
            self.category_list_widget.addItem(item)
        if categories:
            self.category_list_widget.setCurrentRow(0)
        self._update_summary()
        self._update_selection_label()

    def _new_project(self):
        """Créer un nouveau projet avec des données pré-remplies"""
        reply = QtWidgets.QMessageBox.question(self, "Nouveau Projet", 
                                             "Voulez-vous créer un nouveau projet ? Cela effacera la configuration actuelle.",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.data = {
                'categories': [
                    {
                        'name': 'Catégorie par défaut',
                        'subcategories': [
                            {
                                'name': 'Sous-catégorie par défaut',
                                'themes': [
                                    {
                                        'name': 'Thème par défaut',
                                        'platform': 'Grok',
                                        'description': '',
                                        'output_format': 'JSON',
                                        'sample_count': 100,
                                        'training_technique': 'Supervised Learning'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            self._load_categories()
            self._update_summary()
            logger.info("Nouveau projet créé avec des données par défaut")

    def _add_category(self):
        """Ajouter une nouvelle catégorie"""
        category_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        "Ajouter Catégorie",
                                                        "Entrez le nom de la catégorie :")
        if ok and category_name:
            category_name = category_name.strip()
            if not category_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom de la catégorie ne peut pas être vide.")
                return
            
            existing_categories = [c.get('name') for c in self.data.get('categories', [])]
            if category_name in existing_categories:
                QtWidgets.QMessageBox.warning(self, "Duplicata", f"La catégorie '{category_name}' existe déjà.")
                return
            
            new_category_data = {"name": category_name, "subcategories": []}
            self.data.setdefault('categories', []).append(new_category_data)
            
            item = QtWidgets.QListWidgetItem(category_name)
            item.setData(Qt.UserRole, new_category_data)
            self.category_list_widget.addItem(item)
            self.category_list_widget.setCurrentRow(self.category_list_widget.count() - 1)
            self._update_summary()
            logger.info(f"Ajout de la catégorie '{category_name}'")

    def _edit_category(self):
        """Éditer la catégorie sélectionnée"""
        if self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune catégorie sélectionnée.")
            return
        
        current_name = self.data['categories'][self.current_category_index]['name']
        new_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                    "Éditer Catégorie",
                                                    "Entrez le nouveau nom de la catégorie :",
                                                    text=current_name)
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom de la catégorie ne peut pas être vide.")
                return
                
            existing_categories = [c.get('name') for c in self.data.get('categories', [])]
            if new_name in existing_categories and new_name != current_name:
                QtWidgets.QMessageBox.warning(self, "Duplicata", f"La catégorie '{new_name}' existe déjà.")
                return
                
            self.data['categories'][self.current_category_index]['name'] = new_name
            self._load_categories()
            logger.info(f"Catégorie '{current_name}' renommée en '{new_name}'")

    def _delete_category(self, index):
        """Supprimer la catégorie sélectionnée"""
        if index < 0:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune catégorie sélectionnée.")
            return
        
        cat_name = self.data['categories'][index]['name']
        reply = QtWidgets.QMessageBox.question(self, "Supprimer Catégorie", 
                                             f"Êtes-vous sûr de vouloir supprimer '{cat_name}' et toutes ses sous-catégories ?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.data['categories'][index]
            self._load_categories()

    def _add_subcategory(self):
        """Ajouter une nouvelle sous-catégorie"""
        if self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune catégorie sélectionnée pour la sous-catégorie.")
            return

        category_data = self.data['categories'][self.current_category_index]
        subcategory_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        "Ajouter Sous-catégorie",
                                                        "Entrez le nom de la sous-catégorie :")
        if ok and subcategory_name:
            subcategory_name = subcategory_name.strip()
            if not subcategory_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom de la sous-catégorie ne peut pas être vide.")
                return
            
            existing_subcategories = [s.get('name') for s in category_data.get('subcategories', [])]
            if subcategory_name in existing_subcategories:
                QtWidgets.QMessageBox.warning(self, "Duplicata", f"La sous-catégorie '{subcategory_name}' existe déjà.")
                return
            
            new_subcategory_data = {"name": subcategory_name, "themes": []}
            category_data.setdefault('subcategories', []).append(new_subcategory_data)

            item = QtWidgets.QListWidgetItem(subcategory_name)
            item.setData(Qt.UserRole, new_subcategory_data)
            self.subcategory_list_widget.addItem(item)
            self.subcategory_list_widget.setCurrentRow(self.subcategory_list_widget.count() - 1)
            self._update_summary()
            logger.info(f"Ajout de la sous-catégorie '{subcategory_name}'")

    def _edit_subcategory(self):
        """Éditer la sous-catégorie sélectionnée"""
        if self.current_subcategory_index == -1 or self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune sous-catégorie sélectionnée.")
            return
        
        current_name = self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['name']
        new_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                    "Éditer Sous-catégorie",
                                                    "Entrez le nouveau nom de la sous-catégorie :",
                                                    text=current_name)
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom de la sous-catégorie ne peut pas être vide.")
                return
                
            existing_subcategories = [s.get('name') for s in self.data['categories'][self.current_category_index]['subcategories']]
            if new_name in existing_subcategories and new_name != current_name:
                QtWidgets.QMessageBox.warning(self, "Duplicata", f"La sous-catégorie '{new_name}' existe déjà.")
                return
                
            self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['name'] = new_name
            self._on_category_selected(None, None)
            logger.info(f"Sous-catégorie '{current_name}' renommée en '{new_name}'")

    def _delete_subcategory(self, index):
        """Supprimer la sous-catégorie sélectionnée"""
        if index < 0 or self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune sous-catégorie sélectionnée.")
            return
        
        subcat_name = self.data['categories'][self.current_category_index]['subcategories'][index]['name']
        reply = QtWidgets.QMessageBox.question(self, "Supprimer Sous-catégorie", 
                                             f"Êtes-vous sûr de vouloir supprimer '{subcat_name}' et tous ses thèmes ?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.data['categories'][self.current_category_index]['subcategories'][index]
            self._on_category_selected(None, None)
            self._update_summary()

    def _add_theme(self):
        """Ajouter un nouveau thème"""
        if self.current_subcategory_index == -1 or self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune sous-catégorie sélectionnée pour le thème.")
            return

        categories = self.data.get('categories', [])
        if 0 <= self.current_category_index < len(categories):
            category_data = categories[self.current_category_index]
            subcategories = category_data.get('subcategories', [])
            if 0 <= self.current_subcategory_index < len(subcategories):
                subcategory_data = subcategories[self.current_subcategory_index]
                theme_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                        "Ajouter Thème",
                                                        "Entrez le nom du thème :")
                if ok and theme_name:
                    theme_name = theme_name.strip()
                    if not theme_name:
                        QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom du thème ne peut pas être vide.")
                        return
                    
                    existing_themes = [t.get('name') for t in subcategory_data.get('themes', [])]
                    if theme_name in existing_themes:
                        QtWidgets.QMessageBox.warning(self, "Duplicata", f"Le thème '{theme_name}' existe déjà.")
                        return
                    
                    new_theme_data = {
                        "name": theme_name,
                        "platform": "Grok",
                        "description": "",
                        "output_format": "JSON",
                        "sample_count": 100,
                        "training_technique": "Supervised Learning"
                    }
                    subcategory_data.setdefault('themes', []).append(new_theme_data)

                    item = QtWidgets.QListWidgetItem(theme_name)
                    item.setData(Qt.UserRole, new_theme_data)
                    self.theme_list_widget.addItem(item)
                    self.theme_list_widget.setCurrentRow(self.theme_list_widget.count() - 1)
                    self._update_summary()
                    self._update_selection_label()
                    logger.info(f"Ajout du thème '{theme_name}'")

    def _edit_theme(self):
        """Éditer le thème sélectionné"""
        if self.current_theme_index == -1 or self.current_subcategory_index == -1 or self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun thème sélectionné.")
            return
        
        current_name = self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['themes'][self.current_theme_index]['name']
        new_name, ok = QtWidgets.QInputDialog.getText(self, 
                                                    "Éditer Thème",
                                                    "Entrez le nouveau nom du thème :",
                                                    text=current_name)
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Le nom du thème ne peut pas être vide.")
                return
                
            existing_themes = [t.get('name') for t in self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['themes']]
            if new_name in existing_themes and new_name != current_name:
                QtWidgets.QMessageBox.warning(self, "Duplicata", f"Le thème '{new_name}' existe déjà.")
                return
                
            self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['themes'][self.current_theme_index]['name'] = new_name
            self._on_subcategory_selected(None, None)
            logger.info(f"Thème '{current_name}' renommé en '{new_name}'")

    def _delete_theme(self, index):
        """Supprimer le thème sélectionné"""
        if index < 0 or self.current_subcategory_index == -1 or self.current_category_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun thème sélectionné.")
            return
        
        theme_name = self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['themes'][index]['name']
        reply = QtWidgets.QMessageBox.question(self, "Supprimer Thème", 
                                             f"Êtes-vous sûr de vouloir supprimer '{theme_name}' ?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.data['categories'][self.current_category_index]['subcategories'][self.current_subcategory_index]['themes'][index]
            self._on_subcategory_selected(None, None)
            self._update_summary()

    def _on_category_selected(self, current, previous):
        """Gérer la sélection de catégorie"""
        self.current_category_index = self.category_list_widget.currentRow()
        self.subcategory_list_widget.clear()
        self.theme_list_widget.clear()
        self.current_subcategory_index = -1
        self.current_theme_index = -1

        if self.current_category_index != -1:
            categories = self.data.get('categories', [])
            if 0 <= self.current_category_index < len(categories):
                category_data = categories[self.current_category_index]
                subcategories = category_data.get('subcategories', [])
                for subcategory_data in subcategories:
                    item_text = subcategory_data.get('name')
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, subcategory_data)
                    self.subcategory_list_widget.addItem(item)
                if subcategories:
                    self.subcategory_list_widget.setCurrentRow(0)
                self._update_summary()
                self._update_selection_label()
                logger.debug(f"Chargé {len(subcategories)} sous-catégories")

    def _on_subcategory_selected(self, current, previous):
        """Gérer la sélection de sous-catégorie"""
        self.current_subcategory_index = self.subcategory_list_widget.currentRow()
        self.theme_list_widget.clear()
        self.current_theme_index = -1

        if self.current_subcategory_index != -1 and self.current_category_index != -1:
            categories = self.data.get('categories', [])
            if 0 <= self.current_category_index < len(categories):
                category_data = categories[self.current_category_index]
                subcategories = category_data.get('subcategories', [])
                if 0 <= self.current_subcategory_index < len(subcategories):
                    subcategory_data = subcategories[self.current_subcategory_index]
                    themes = subcategory_data.get('themes', [])
                    for theme_data in themes:
                        item_text = theme_data.get('name')
                        item = QtWidgets.QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, theme_data)
                        self.theme_list_widget.addItem(item)
                    if themes:
                        self.theme_list_widget.setCurrentRow(0)
                    self._update_summary()
                    self._update_selection_label()
                    logger.debug(f"Chargé {len(themes)} thèmes")

    def _on_theme_selected(self, current, previous):
        """Gérer la sélection de thème"""
        self.current_theme_index = self.theme_list_widget.currentRow()
        
        if self.current_theme_index != -1 and self.current_subcategory_index != -1 and self.current_category_index != -1:
            theme_data = self._get_current_theme_data()
            if theme_data:
                self.platform_combo.blockSignals(True)
                self.prompt_edit.blockSignals(True)
                self.output_format_combo.blockSignals(True)
                self.sample_count_spin.blockSignals(True)
                self.training_tech_combo.blockSignals(True)
                
                self.platform_combo.setCurrentText(theme_data.get('platform', 'Grok'))
                self.prompt_edit.setText(theme_data.get('description', ''))
                self.output_format_combo.setCurrentText(theme_data.get('output_format', 'JSON'))
                self.sample_count_spin.setValue(theme_data.get('sample_count', 100))
                self.training_tech_combo.setCurrentText(theme_data.get('training_technique', 'Supervised Learning'))
                
                self.platform_combo.blockSignals(False)
                self.prompt_edit.blockSignals(False)
                self.output_format_combo.blockSignals(False)
                self.sample_count_spin.blockSignals(False)
                self.training_tech_combo.blockSignals(False)
                self._update_summary()
                self._update_selection_label()

    def _on_platform_changed(self, text):
        """Gérer le changement de plateforme"""
        theme_data = self._get_current_theme_data()
        if theme_data:
            theme_data['platform'] = text
            self._update_summary()

    def _on_prompt_changed(self):
        """Gérer le changement de description"""
        theme_data = self._get_current_theme_data()
        if theme_data:
            theme_data['description'] = self.prompt_edit.toPlainText()
            self._update_summary()

    def _on_output_format_changed(self, text):
        """Gérer le changement de format de sortie"""
        theme_data = self._get_current_theme_data()
        if theme_data:
            theme_data['output_format'] = text
            self._update_summary()

    def _on_sample_count_changed(self, value):
        """Gérer le changement du nombre d'échantillons"""
        theme_data = self._get_current_theme_data()
        if theme_data:
            theme_data['sample_count'] = value
            self._update_summary()

    def _on_training_tech_changed(self, text):
        """Gérer le changement de technique d'entraînement"""
        theme_data = self._get_current_theme_data()
        if theme_data:
            theme_data['training_technique'] = text
            self._update_summary()

    def _get_current_theme_data(self):
        """Obtenir les données du thème actuellement sélectionné"""
        if (self.current_theme_index != -1 and 
            self.current_subcategory_index != -1 and 
            self.current_category_index != -1):
            categories = self.data.get('categories', [])
            if 0 <= self.current_category_index < len(categories):
                category_data = categories[self.current_category_index]
                subcategories = category_data.get('subcategories', [])
                if 0 <= self.current_subcategory_index < len(subcategories):
                    subcategory_data = subcategories[self.current_subcategory_index]
                    themes = subcategory_data.get('themes', [])
                    if 0 <= self.current_theme_index < len(themes):
                        return themes[self.current_theme_index]
        return None

    def _save_configuration(self):
        """Sauvegarder la configuration actuelle"""
        self._update_summary()
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Sauvegarder Projet", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=4)
                QtWidgets.QMessageBox.information(self, "Succès", "Projet sauvegardé avec succès.")
                logger.info(f"Projet sauvegardé à {file_name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {str(e)}")
                logger.error(f"Échec de la sauvegarde : {str(e)}")

    def _construct_enhanced_prompt(self, theme, category_name, subcategory_name):
        """Construire un prompt complet incluant catégorie, sous-catégorie, thème, format, nombre d'échantillons et technique d'entraînement."""
        description = theme.get('description', '')
        output_format = theme.get('output_format', 'JSON')
        sample_count = theme.get('sample_count', 100)
        theme_name = theme.get('name', 'Thème sans nom')
        training_technique = theme.get('training_technique', 'Supervised Learning')

        format_instruction = ""
        if training_technique == "Autre":
            format_instruction = "Les données doivent être structurées au format Question-Réponse, avec chaque échantillon contenant un champ 'question' et un champ 'réponse'."
        elif training_technique == "DPO":
            format_instruction = "Les données doivent être structurées pour l'optimisation de préférence directe (DPO), avec chaque échantillon contenant les champs 'input', 'chosen' (réponse préférée) et 'rejected' (réponse rejetée)."

        enhanced_prompt = (
            f"Générez un dataset pour le contexte suivant :\n"
            f"- Catégorie : {category_name}\n"
            f"- Sous-catégorie : {subcategory_name}\n"
            f"- Thème : {theme_name}\n"
            f"- Description : {description if description else 'Aucune description fournie.'}\n"
            f"- Format de sortie souhaité : {output_format}\n"
            f"- Nombre d'échantillons : {sample_count}\n"
            f"- Technique d'entraînement : {training_technique}\n\n"
            f"Veuillez créer {sample_count} échantillons de données alignés avec le thème '{theme_name}' "
            f"sous la sous-catégorie '{subcategory_name}' et la catégorie '{category_name}'. "
            f"Les données doivent respecter la structure et les exigences décrites dans '{description}'. "
            f"{format_instruction} Assurez-vous que la sortie est valide et cohérente avec le format spécifié ({output_format})."
        )

        return enhanced_prompt

    def _generate_dataset(self):
        """Generate the dataset for ChatGPT using Chrome, with hardcoded settings for detection and extraction."""
        if not self.conductor:
            QtWidgets.QMessageBox.critical(self, "Error", "Conductor not defined. Please configure the conductor before generating the dataset.")
            logger.error("Conductor not defined. Cannot start dataset generation.")
            return

        categories = self.data.get('categories', [])
        if not categories:
            QtWidgets.QMessageBox.warning(self, "Error", "No categories defined for dataset generation.")
            logger.error("No categories defined for dataset generation.")
            return

        # Fetch ChatGPT platform profile
        platform_name = "ChatGPT"
        try:
            platform_profile = self.conductor.database.get_all_platforms().get(platform_name)
            if not platform_profile:
                QtWidgets.QMessageBox.critical(self, "Error", "ChatGPT platform profile not found in conductor database.")
                logger.error("ChatGPT platform profile not found.")
                self._cleanup_progress_bar()
                return
        except AttributeError:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to access platform database. Please check conductor configuration.")
            logger.error("Failed to access platform database.")
            self._cleanup_progress_bar()
            return

        # Calculate total tasks for progress bar (ChatGPT only)
        total_tasks = sum(
            len(subcat.get('themes', [])) for cat in categories for subcat in cat.get('subcategories', [])
        )

        # Reuse or create progress bar
        if hasattr(self, 'progress_bar') and self.progress_bar:
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar = QtWidgets.QProgressBar()
            self.layout().addWidget(self.progress_bar)
        self.progress_bar.setMaximum(total_tasks * 100)
        self.progress_bar.setValue(0)

        self.running_workers = []
        self.current_worker_index = -1
        self.results = []

        for cat_idx, category in enumerate(categories):
            category_name = category.get('name', 'Unnamed Category')
            for subcat_idx, subcategory in enumerate(category.get('subcategories', [])):
                subcategory_name = subcategory.get('name', 'Unnamed Subcategory')
                for theme_idx, theme in enumerate(subcategory.get('themes', [])):
                    # Skip themes not designated for ChatGPT
                    if theme.get('platform', 'ChatGPT') != platform_name:
                        logger.debug(f"Skipping theme {theme.get('name', 'Unnamed')} (platform: {theme.get('platform', 'ChatGPT')}) as it is not for ChatGPT.")
                        self.progress_bar.setValue(self.progress_bar.value() + 100)
                        continue

                    enhanced_prompt = self._construct_enhanced_prompt(theme, category_name, subcategory_name)
                    if not enhanced_prompt:
                        logger.warning(f"Skipping theme {theme.get('name', 'Unnamed')} due to empty prompt.")
                        self.progress_bar.setValue(self.progress_bar.value() + 100)
                        continue

                    try:
                        # Hardcode ChatGPT-specific settings
                        platform_profile['extraction_config'] = {
                            'response_area': {
                                'primary_selector': 'div[class*="message"]',
                                'fallback_selectors': ['div[class*="conversation"]', 'main'],
                                'text_cleaning': 'preserve_markdown_structure'
                            }
                        }
                        platform_profile['detection_config'] = {
                            'platform_type': platform_name.lower(),
                            'primary_selector': 'div[class*="message"]',
                            'fallback_selectors': ['div[class*="conversation"]', 'main']
                        }

                        detected_browser_type = 'chromium'  # Hardcoded to Chrome
                        worker = SimpleTestWorker(self.conductor, platform_profile, enhanced_prompt, detected_browser_type)
                        worker.platform_name = platform_name
                        worker.platform_index = len(self.running_workers)
                        worker.theme_info = {
                            'category': category_name,
                            'subcategory': subcategory_name,
                            'theme': theme.get('name', 'Unnamed Theme'),
                            'output_format': theme.get('output_format', 'JSON'),
                            'sample_count': theme.get('sample_count', 100),
                            'training_technique': theme.get('training_technique', 'Supervised Learning')
                        }

                        worker.test_completed.connect(self._on_test_completed)
                        worker.step_update.connect(self._on_step_update)
                        worker.debug_info.connect(self._on_debug_info)
                        worker.finished.connect(self._on_worker_finished)

                        self.running_workers.append(worker)
                    except Exception as e:
                        logger.error(f"Failed to create worker for ChatGPT: {str(e)}")
                        self.progress_bar.setValue(self.progress_bar.value() + 100)
                        continue

        if not self.running_workers:
            QtWidgets.QMessageBox.warning(self, "Error", "No valid tasks to execute for ChatGPT.")
            self._cleanup_progress_bar()
            return

        self._start_next_worker()
        QtWidgets.QMessageBox.information(self, "Success", "Dataset generation for ChatGPT started...")
        logger.info("Dataset generation for ChatGPT started")

    def _start_next_worker(self):
        """Démarrer le worker suivant dans la file d'attente."""
        self.current_worker_index += 1
        if self.current_worker_index < len(self.running_workers):
            worker = self.running_workers[self.current_worker_index]
            logger.info(f"Démarrage du worker pour la plateforme : {worker.platform_name}, "
                        f"Thème : {worker.theme_info['theme']}")
            try:
                worker.start()
            except Exception as e:
                logger.error(f"Échec du démarrage du worker pour {worker.platform_name} : {str(e)}")
                self._start_next_worker()
        else:
            self._finalize_dataset()
            logger.info("Tous les workers de génération de dataset sont terminés.")

    def _on_worker_finished(self):
        """Gérer la fin d'un worker."""
        sender_worker = self.sender()
        if sender_worker:
            logger.info(f"Worker pour la plateforme {sender_worker.platform_name} (Thème : {sender_worker.theme_info.get('theme', 'Inconnu')}) terminé.")
            self._start_next_worker()

    def _on_test_completed(self, success, message, duration, response):
        """Gérer la fin d'un test pour une plateforme et un thème."""
        sender_worker = self.sender()
        if not sender_worker:
            return
        
        platform_name = getattr(sender_worker, 'platform_name', 'Plateforme inconnue')
        theme_info = getattr(sender_worker, 'theme_info', {})
        
        logger.info(f"Test terminé pour {platform_name} (Thème : {theme_info.get('theme', 'Inconnu')}). "
                    f"Succès : {success}, Durée : {duration:.2f}s, Message : {message}")

        self.results.append({
            'category': theme_info.get('category'),
            'subcategory': theme_info.get('subcategory'),
            'theme': theme_info.get('theme'),
            'platform': platform_name,
            'success': success,
            'message': message,
            'duration': duration,
            'response': response,
            'output_format': theme_info.get('output_format', 'JSON'),
            'sample_count': theme_info.get('sample_count', 100),
            'training_technique': theme_info.get('training_technique', 'Supervised Learning')
        })

        current_progress = (self.current_worker_index + 1) * 100
        self.progress_bar.setValue(current_progress)

    def _on_step_update(self, step_name, message):
        """Gérer les mises à jour des étapes des workers."""
        sender_worker = self.sender()
        if not sender_worker:
            return
        
        platform_name = getattr(sender_worker, 'platform_name', 'Plateforme inconnue')
        theme = getattr(sender_worker, 'theme_info', {}).get('theme', 'Thème inconnu')
        logger.debug(f"[{platform_name}][{theme}] : {message}")
        self.selection_label.setText(f"Traitement : {platform_name} → {theme} ({message})")

    def _on_debug_info(self, message):
        """Gérer les informations de débogage des workers."""
        sender_worker = self.sender()
        if not sender_worker:
            return
            
        platform_name = getattr(sender_worker, 'platform_name', 'Plateforme inconnue')
        theme = getattr(sender_worker, 'theme_info', {}).get('theme', 'Thème inconnu')
        logger.debug(f"[{platform_name}][{theme} DEBUG] : {message}")

    def _finalize_dataset(self):
        """Finaliser la génération du dataset en sauvegardant les résultats dans le format spécifié."""
        if not self.results:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune donnée générée à sauvegarder.")
            self.progress_bar.setVisible(False)
            return

        results_by_format = {}
        for result in self.results:
            output_format = result['output_format']
            if output_format not in results_by_format:
                results_by_format[output_format] = []
            results_by_format[output_format].append(result)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for output_format, results in results_by_format.items():
            file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Sauvegarder Dataset", f"dataset_{output_format.lower()}_{timestamp}",
                f"{output_format} Files (*.{output_format.lower()})"
            )
            if file_name:
                try:
                    if output_format == 'JSON':
                        with open(file_name, 'w', encoding='utf-8') as f:
                            json.dump(results, f, indent=4)
                    elif output_format == 'CSV':
                        with open(file_name, 'w', encoding='utf-8', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=[
                                'category', 'subcategory', 'theme', 'platform',
                                'success', 'message', 'duration', 'response',
                                'sample_count', 'training_technique'
                            ])
                            writer.writeheader()
                            writer.writerows(results)
                    elif output_format == 'JSONL':
                        with open(file_name, 'w', encoding='utf-8') as f:
                            for result in results:
                                f.write(json.dumps(result) + '\n')
                    elif output_format == 'XML':
                        root = Element('dataset')
                        for result in results:
                            item = Element('item')
                            for key, value in result.items():
                                child = Element(key)
                                child.text = str(value)
                                item.append(child)
                            root.append(item)
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(tostring(root, encoding='unicode'))
                    elif output_format == 'Parquet':
                        df = pd.DataFrame(results)
                        df.to_parquet(file_name)
                    
                    QtWidgets.QMessageBox.information(
                        self, "Succès", f"Dataset sauvegardé avec succès en tant que {file_name}"
                    )
                    logger.info(f"Dataset sauvegardé à {file_name}")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self, "Erreur", f"Échec de la sauvegarde : {str(e)}"
                    )
                    logger.error(f"Échec de la sauvegarde du dataset : {str(e)}")

        self.progress_bar.setVisible(False)
        self.selection_label.setText("Génération du dataset terminée")

    def get_data(self):
        """
        Obtenir les données actuelles
        Returns:
            Dictionnaire des données actuelles
        """
        return self.data

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

import math
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt

class PieChartWidget(QtWidgets.QWidget):
    """Widget personnalisé pour afficher un graphique en anneau avec affichage hiérarchique"""
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.current_category_index = -1
        self.current_subcategory_index = -1
        self.current_theme_index = -1
        self.setMinimumSize(300, 300)
        self.pie_segments = []  # Store segment information for click detection

    def update_data(self, data, cat_index=-1, subcat_index=-1, theme_index=-1):
        """Mettre à jour les données du graphique et les indices de sélection"""
        self.data = data
        self.current_category_index = cat_index
        self.current_subcategory_index = subcat_index
        self.current_theme_index = theme_index
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse clicks to navigate through the hierarchy"""
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()
            clicked_segment = self.get_clicked_segment(click_pos)
            
            if clicked_segment is not None:
                # Navigate based on current level
                if self.current_category_index == -1:
                    # Currently showing categories, drill down to subcategories
                    self.current_category_index = clicked_segment
                    self.current_subcategory_index = -1
                    self.current_theme_index = -1
                elif self.current_subcategory_index == -1:
                    # Currently showing subcategories, drill down to themes
                    self.current_subcategory_index = clicked_segment
                    self.current_theme_index = -1
                elif self.current_theme_index == -1:
                    # Currently showing themes, select specific theme
                    self.current_theme_index = clicked_segment
                
                self.update()
        elif event.button() == Qt.RightButton:
            # Right click to go back up in hierarchy
            if self.current_theme_index != -1:
                self.current_theme_index = -1
            elif self.current_subcategory_index != -1:
                self.current_subcategory_index = -1
            elif self.current_category_index != -1:
                self.current_category_index = -1
            
            self.update()

    def get_clicked_segment(self, click_pos):
        """Determine which segment was clicked based on mouse position"""
        rect = self.rect().adjusted(20, 20, -20, -20)
        center = rect.center()
        
        # Calculate distance from center
        dx = click_pos.x() - center.x()
        dy = click_pos.y() - center.y()
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Check if click is within the pie chart area
        outer_radius = rect.width() / 2
        inner_radius = outer_radius * 0.3  # Assuming donut chart with inner radius
        
        if distance < inner_radius or distance > outer_radius:
            return None
        
        # Calculate angle of click
        angle = math.atan2(-dy, dx)  # Negative dy because Qt coordinates are inverted
        if angle < 0:
            angle += 2 * math.pi
        
        # Convert to degrees and adjust for Qt's angle system (starts from 3 o'clock, goes clockwise)
        angle_degrees = math.degrees(angle)
        qt_angle = (90 - angle_degrees) % 360  # Convert to Qt's angle system
        
        # Find which segment contains this angle
        for i, segment in enumerate(self.pie_segments):
            start_angle = segment['start_angle'] / 16  # Convert from Qt's 1/16 degree units
            span_angle = segment['span_angle'] / 16
            end_angle = (start_angle + span_angle) % 360
            
            if start_angle <= end_angle:
                if start_angle <= qt_angle <= end_angle:
                    return i
            else:  # Segment crosses 0 degrees
                if qt_angle >= start_angle or qt_angle <= end_angle:
                    return i
        
        return None

    def paintEvent(self, event):
        """Peindre le graphique en anneau"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        categories = self.data.get('categories', [])
        self.pie_segments = []  # Reset segments for click detection
        
        # Par défaut : afficher seulement les catégories
        if self.current_category_index == -1:
            if not categories:
                return
            total = len(categories)
            rect = self.rect().adjusted(20, 20, -20, -20)
            start_angle = 0
            colors = [QtGui.QColor("#4CAF50")]  # Vert pour les catégories
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#f5f5f5")))
            painter.drawEllipse(rect)
            
            for i, category in enumerate(categories):
                angle = int((1 / total) * 5760) if total > 0 else 0
                
                # Store segment info for click detection
                self.pie_segments.append({
                    'start_angle': start_angle,
                    'span_angle': angle,
                    'index': i
                })
                
                painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
                painter.setBrush(QtGui.QBrush(colors[0]))
                painter.drawPie(rect, start_angle, angle)
                
                mid_angle = start_angle + angle / 2
                angle_rad = math.radians(mid_angle / 16)
                radius = rect.width() / 2
                label_radius = radius * 1.2
                label_pos = QtCore.QPointF(
                    rect.center().x() + math.cos(angle_rad) * label_radius,
                    rect.center().y() - math.sin(angle_rad) * label_radius
                )
                line_end = QtCore.QPointF(
                    rect.center().x() + math.cos(angle_rad) * radius,
                    rect.center().y() - math.sin(angle_rad) * radius
                )
                painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 1))
                painter.drawLine(line_end, label_pos)
                
                text = f"{category['name']}: 1 ({(1/total*100):.1f}%)"
                fm = QtGui.QFontMetrics(painter.font())
                text_rect = fm.boundingRect(text).adjusted(-5, -3, 5, 3)
                text_rect.moveCenter(label_pos.toPoint())
                
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 200)))
                painter.setPen(QtGui.QPen(QtGui.QColor("#333333")))
                painter.drawRoundedRect(text_rect, 4, 4)
                
                painter.setPen(QtGui.QColor("#333333"))
                painter.drawText(text_rect, Qt.AlignCenter, text)
                
                start_angle += angle

        # Afficher les sous-catégories si une catégorie est sélectionnée
        elif self.current_category_index != -1 and self.current_subcategory_index == -1:
            if 0 <= self.current_category_index < len(categories):
                subcategories = categories[self.current_category_index].get('subcategories', [])
                if not subcategories:
                    return
                total = len(subcategories)
                rect = self.rect().adjusted(20, 20, -20, -20)
                start_angle = 0
                colors = [QtGui.QColor("#2196F3")]  # Bleu pour les sous-catégories
                painter.setBrush(QtGui.QBrush(QtGui.QColor("#f5f5f5")))
                painter.drawEllipse(rect)
                
                for i, subcategory in enumerate(subcategories):
                    angle = int((1 / total) * 5760) if total > 0 else 0
                    
                    # Store segment info for click detection
                    self.pie_segments.append({
                        'start_angle': start_angle,
                        'span_angle': angle,
                        'index': i
                    })
                    
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
                    painter.setBrush(QtGui.QBrush(colors[0]))
                    painter.drawPie(rect, start_angle, angle)
                    
                    mid_angle = start_angle + angle / 2
                    angle_rad = math.radians(mid_angle / 16)
                    radius = rect.width() / 2
                    label_radius = radius * 1.2
                    label_pos = QtCore.QPointF(
                        rect.center().x() + math.cos(angle_rad) * label_radius,
                        rect.center().y() - math.sin(angle_rad) * label_radius
                    )
                    line_end = QtCore.QPointF(
                        rect.center().x() + math.cos(angle_rad) * radius,
                        rect.center().y() - math.sin(angle_rad) * radius
                    )
                    painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 1))
                    painter.drawLine(line_end, label_pos)
                    
                    text = f"{subcategory['name']}: 1 ({(1/total*100):.1f}%)"
                    fm = QtGui.QFontMetrics(painter.font())
                    text_rect = fm.boundingRect(text).adjusted(-5, -3, 5, 3)
                    text_rect.moveCenter(label_pos.toPoint())
                    
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 200)))
                    painter.setPen(QtGui.QPen(QtGui.QColor("#333333")))
                    painter.drawRoundedRect(text_rect, 4, 4)
                    
                    painter.setPen(QtGui.QColor("#333333"))
                    painter.drawText(text_rect, Qt.AlignCenter, text)
                    
                    start_angle += angle

        # Afficher les thèmes si une sous-catégorie est sélectionnée
        elif self.current_category_index != -1 and self.current_subcategory_index != -1:
            if 0 <= self.current_category_index < len(categories):
                subcategories = categories[self.current_category_index].get('subcategories', [])
                if 0 <= self.current_subcategory_index < len(subcategories):
                    themes = subcategories[self.current_subcategory_index].get('themes', [])
                    if not themes:
                        return
                    total = len(themes)
                    rect = self.rect().adjusted(20, 20, -20, -20)
                    start_angle = 0
                    colors = [QtGui.QColor("#FFC107")]  # Ambre pour les thèmes
                    painter.setBrush(QtGui.QBrush(QtGui.QColor("#f5f5f5")))
                    painter.drawEllipse(rect)
                    
                    for i, theme in enumerate(themes):
                        angle = int((1 / total) * 5760) if total > 0 else 0
                        
                        # Store segment info for click detection
                        self.pie_segments.append({
                            'start_angle': start_angle,
                            'span_angle': angle,
                            'index': i
                        })
                        
                        # Highlight selected theme
                        if self.current_theme_index == i:
                            painter.setBrush(QtGui.QBrush(QtGui.QColor("#FF9800")))  # Darker orange for selected
                        else:
                            painter.setBrush(QtGui.QBrush(colors[0]))
                        
                        painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
                        painter.drawPie(rect, start_angle, angle)
                        
                        mid_angle = start_angle + angle / 2
                        angle_rad = math.radians(mid_angle / 16)
                        radius = rect.width() / 2
                        label_radius = radius * 1.2
                        label_pos = QtCore.QPointF(
                            rect.center().x() + math.cos(angle_rad) * label_radius,
                            rect.center().y() - math.sin(angle_rad) * label_radius
                        )
                        line_end = QtCore.QPointF(
                            rect.center().x() + math.cos(angle_rad) * radius,
                            rect.center().y() - math.sin(angle_rad) * radius
                        )
                        painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 1))
                        painter.drawLine(line_end, label_pos)
                        
                        text = f"{theme['name']}: 1 ({(1/total*100):.1f}%)"
                        fm = QtGui.QFontMetrics(painter.font())
                        text_rect = fm.boundingRect(text).adjusted(-5, -3, 5, 3)
                        text_rect.moveCenter(label_pos.toPoint())
                        
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 200)))
                        painter.setPen(QtGui.QPen(QtGui.QColor("#333333")))
                        painter.drawRoundedRect(text_rect, 4, 4)
                        
                        painter.setPen(QtGui.QColor("#333333"))
                        painter.drawText(text_rect, Qt.AlignCenter, text)
                        
                        start_angle += angle

        # Add navigation instructions
        painter.setPen(QtGui.QColor("#666666"))
        painter.setFont(QtGui.QFont("Arial", 8))
        nav_text = "Left click: drill down | Right click: go back"
        painter.drawText(10, self.height() - 10, nav_text)
class DatasetCreationWidget(DatasetGenerationWidget):
    """
    Alias pour gérer la génération de datasets avec compatibilité ascendante
    """
    pass