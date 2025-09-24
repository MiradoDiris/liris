#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
import logging
import json
import math
from core.data.database import Database
from ui.styles.theme import Theme
from core.data.database import Database
from datetime import datetime
import sqlite3

logger = logging.getLogger(__name__)

class PieChartWidget(QtWidgets.QWidget):
    """
    Widget pour afficher un camembert de la répartition des données
    """
    
    # Déclaration correcte du signal
    segment_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.selected_cluster = None
        self.selected_root = None
        self.selected_parent = None
        
        # Données d'exemple pour la démonstration
        self.sample_data = {
            'total_examples': 1000,
            'batches': [
                {
                    'name': 'Batch 1',
                    'cluster': 'Débutant',
                    'root': 'Compétences de base',
                    'parent': 'Connaissances fondamentales',
                    'examples': 250,
                    'percentage': 25.0
                },
                {
                    'name': 'Batch 2',
                    'cluster': 'Intermédiaire',
                    'root': 'Compétences avancées',
                    'parent': 'Applications pratiques',
                    'examples': 350,
                    'percentage': 35.0
                },
                {
                    'name': 'Batch 3',
                    'cluster': 'Avancé',
                    'root': 'Expertise spécialisée',
                    'parent': 'Optimisation et recherche',
                    'examples': 400,
                    'percentage': 40.0
                }
            ]
        }
        
        self.setMinimumSize(400, 400)
        
    def set_data(self, data):
        """Définir les données à afficher"""
        self.data = data
        self.update()
        
    def set_hierarchy_selection(self, cluster=None, root=None, parent=None):
        """Définir la sélection hiérarchique"""
        self.selected_cluster = cluster
        self.selected_root = root
        self.selected_parent = parent
        self.update()
        
    def paintEvent(self, event):
        """Dessiner le camembert"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Dimensions
        width = self.width()
        height = self.height()
        size = min(width, height) - 40
        x = (width - size) / 2
        y = (height - size) / 2
        
        # Couleurs pour les segments
        colors = [
            QtGui.QColor('#FF6B6B'),  # Rouge
            QtGui.QColor('#4ECDC4'),  # Turquoise
            QtGui.QColor('#45B7D1'),  # Bleu
            QtGui.QColor('#96CEB4'),  # Vert
            QtGui.QColor('#FFEAA7'),  # Jaune
            QtGui.QColor('#DDA0DD'),  # Violet
            QtGui.QColor('#98D8C8'),  # Vert clair
            QtGui.QColor('#F7DC6F'),  # Jaune doré
        ]
        
        # Dessiner le camembert
        if self.sample_data['batches']:
            total_percentage = sum(batch['percentage'] for batch in self.sample_data['batches'])
            start_angle = 0
            
            for i, batch in enumerate(self.sample_data['batches']):
                # Calculer l'angle du segment
                angle = 360 * 16 * (batch['percentage'] / 100)
                
                # Dessiner le segment
                painter.setBrush(colors[i % len(colors)])
                painter.setPen(QtGui.QPen(Qt.black, 2))
                painter.drawPie(int(x), int(y), int(size), int(size), int(start_angle), int(angle))
                
                # Ajouter une légère surbrillance si sélectionné
                if (self.selected_cluster and batch['cluster'] == self.selected_cluster and
                    (not self.selected_root or batch['root'] == self.selected_root) and
                    (not self.selected_parent or batch['parent'] == self.selected_parent)):
                    painter.setBrush(QtGui.QColor(255, 255, 255, 100))
                    painter.drawPie(int(x), int(y), int(size), int(size), int(start_angle), int(angle))
                
                start_angle += angle
        
        # Dessiner le trou au centre (donut chart)
        center_size = size * 0.4
        center_x = x + (size - center_size) / 2
        center_y = y + (size - center_size) / 2
        painter.setBrush(QtGui.QColor(240, 240, 240))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(center_x), int(center_y), int(center_size), int(center_size))
        
        # Ajouter les informations au centre
        painter.setPen(QtGui.QPen(Qt.black))
        painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        total_text = f"{self.sample_data['total_examples']} exemples"
        painter.drawText(int(center_x), int(center_y), int(center_size), int(center_size), 
                        Qt.AlignCenter, total_text)
        
        # Légende
        self._draw_legend(painter, width, height, colors)
        
    def _draw_legend(self, painter, width, height, colors):
        """Dessiner la légende"""
        legend_x = 20
        legend_y = 20
        legend_width = width - 40
        box_size = 15
        spacing = 5
        
        painter.setFont(QtGui.QFont("Arial", 9))
        
        for i, batch in enumerate(self.sample_data['batches']):
            y_pos = legend_y + i * (box_size + spacing + 5)
            
            # Carré de couleur
            painter.setBrush(colors[i % len(colors)])
            painter.setPen(QtGui.QPen(Qt.black, 1))
            painter.drawRect(legend_x, y_pos, box_size, box_size)
            
            # Texte
            text = f"{batch['cluster']} - {batch['root']}: {batch['examples']} exemples ({batch['percentage']}%)"
            painter.setPen(QtGui.QPen(Qt.black))
            painter.drawText(legend_x + box_size + spacing, y_pos + box_size - 3, text)
            
            # Mettre en évidence si sélectionné
            if (self.selected_cluster and batch['cluster'] == self.selected_cluster and
                (not self.selected_root or batch['root'] == self.selected_root) and
                (not self.selected_parent or batch['parent'] == self.selected_parent)):
                painter.setPen(QtGui.QPen(QtGui.QColor(Theme.SECONDARY_COLOR), 2))
                painter.drawRect(legend_x - 2, y_pos - 2, box_size + 4, box_size + 4)
    
    def mousePressEvent(self, event):
        """Gérer les clics sur le camembert"""
        if event.button() == Qt.LeftButton:
            # Calculer la position relative
            width = self.width()
            height = self.height()
            size = min(width, height) - 40
            x_center = width / 2
            y_center = height / 2
            
            # Coordonnées du clic
            click_x = event.x() - x_center
            click_y = event.y() - y_center
            
            # Distance du centre
            distance = math.sqrt(click_x**2 + click_y**2)
            radius = size / 2
            
            # Vérifier si le clic est dans le camembert
            if distance <= radius:
                # Calculer l'angle du clic
                angle = math.degrees(math.atan2(click_y, click_x))
                if angle < 0:
                    angle += 360
                
                # Trouver le segment correspondant
                current_angle = 0
                for i, batch in enumerate(self.sample_data['batches']):
                    segment_angle = 360 * (batch['percentage'] / 100)
                    if current_angle <= angle < current_angle + segment_angle:
                        # Émettre un signal avec les informations du segment
                        self.segment_clicked.emit(batch)
                        break
                    current_angle += segment_angle

class ProjectTypologyTab(QtWidgets.QWidget):
    """
    Onglet pour la gestion du projet et de la typologie
    """
    
    # Déclaration correcte du signal avec des types spécifiques
    hierarchy_selection_changed = pyqtSignal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.strategy_widget = parent
        self._init_ui()
        
    def _init_ui(self):
        """Initialiser l'interface utilisateur"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Section projet
        project_group = QtWidgets.QGroupBox("Gestion du Projet")
        project_group.setStyleSheet(self._get_group_style())
        project_layout = QtWidgets.QVBoxLayout(project_group)
        
        # Informations du projet
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.addWidget(QtWidgets.QLabel("Nom du projet:"))
        self.project_name_label = QtWidgets.QLabel("Aucun projet")
        self.project_name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.project_name_label)
        info_layout.addStretch()
        
        project_layout.addLayout(info_layout)
        
        # Statistiques du projet
        stats_layout = QtWidgets.QGridLayout()
        stats_layout.addWidget(QtWidgets.QLabel("Typologies définies:"), 0, 0)
        self.typologies_count_label = QtWidgets.QLabel("0")
        stats_layout.addWidget(self.typologies_count_label, 0, 1)
        
        stats_layout.addWidget(QtWidgets.QLabel("Clusters total:"), 1, 0)
        self.clusters_count_label = QtWidgets.QLabel("0")
        stats_layout.addWidget(self.clusters_count_label, 1, 1)
        
        stats_layout.addWidget(QtWidgets.QLabel("Exemples total:"), 2, 0)
        self.examples_count_label = QtWidgets.QLabel("0")
        stats_layout.addWidget(self.examples_count_label, 2, 1)
        
        project_layout.addLayout(stats_layout)
        
        layout.addWidget(project_group)
        
        # Section typologie actuelle
        typology_group = QtWidgets.QGroupBox("Typologie Actuelle")
        typology_group.setStyleSheet(self._get_group_style())
        typology_layout = QtWidgets.QVBoxLayout(typology_group)
        
        # Sélection de typologie
        selection_layout = QtWidgets.QHBoxLayout()
        selection_layout.addWidget(QtWidgets.QLabel("Typologie:"))
        self.typology_combo = QtWidgets.QComboBox()
        self.typology_combo.currentTextChanged.connect(self._on_typology_changed)
        selection_layout.addWidget(self.typology_combo, 1)
        
        typology_layout.addLayout(selection_layout)
        
        # Description
        desc_layout = QtWidgets.QVBoxLayout()
        desc_layout.addWidget(QtWidgets.QLabel("Description:"))
        self.typology_desc_text = QtWidgets.QTextEdit()
        self.typology_desc_text.setMaximumHeight(80)
        self.typology_desc_text.textChanged.connect(self._on_typology_desc_changed)
        desc_layout.addWidget(self.typology_desc_text)
        
        typology_layout.addLayout(desc_layout)
        
        # Structure hiérarchique
        structure_layout = QtWidgets.QVBoxLayout()
        structure_layout.addWidget(QtWidgets.QLabel("Structure hiérarchique:"))
        
        # TreeWidget pour afficher la structure
        self.structure_tree = QtWidgets.QTreeWidget()
        self.structure_tree.setHeaderLabels(["Élément", "Type", "Exemples"])
        self.structure_tree.itemClicked.connect(self._on_structure_item_clicked)
        structure_layout.addWidget(self.structure_tree)
        
        typology_layout.addLayout(structure_layout)
        
        layout.addWidget(typology_group)
        
        # Boutons d'action
        button_layout = QtWidgets.QHBoxLayout()
        
        new_typology_btn = QtWidgets.QPushButton("Nouvelle Typologie")
        new_typology_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        new_typology_btn.clicked.connect(self._create_typology)
        
        export_btn = QtWidgets.QPushButton("Exporter Structure")
        export_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        export_btn.clicked.connect(self._export_structure)
        
        button_layout.addWidget(new_typology_btn)
        button_layout.addStretch()
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
    def _get_group_style(self):
        """Obtenir le style pour les groupes"""
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
    
    def _get_button_style(self, color):
        """Obtenir le style pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
        """
    
    def _darken_color(self, color, factor=0.1):
        """Assombrir une couleur"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return '#%02x%02x%02x' % darkened
    
    def refresh(self):
        """Rafraîchir les données affichées depuis la DB"""
        if self.strategy_widget and self.strategy_widget.current_project:
            # Mettre à jour les informations du projet
            project = self.strategy_widget.current_project
            self.project_name_label.setText(project.get('name', 'Aucun projet'))
            
            # Compter les éléments depuis la DB
            if self.strategy_widget.typologies:
                typologies_count = len(self.strategy_widget.typologies)
                
                # Compter les clusters, racines, etc.
                clusters_count = 0
                examples_count = 0
                
                for typology in self.strategy_widget.typologies:
                    if 'clusters' in typology:
                        clusters_count += len(typology['clusters'])
                        # Compter les exemples depuis les statistiques
                        if hasattr(self.strategy_widget, 'statistics'):
                            examples_count = sum(stat['examples_count'] for stat in self.strategy_widget.statistics)
                
                self.typologies_count_label.setText(str(typologies_count))
                self.clusters_count_label.setText(str(clusters_count))
                self.examples_count_label.setText(str(examples_count))
            
            # Mettre à jour la liste des typologies
            self.typology_combo.blockSignals(True)
            self.typology_combo.clear()
            
            if self.strategy_widget.typologies:
                for typology in self.strategy_widget.typologies:
                    self.typology_combo.addItem(typology.get('name', 'Sans nom'))
            
            self.typology_combo.blockSignals(False)
            
            # Mettre à jour l'arbre de structure
            self._refresh_structure_tree()

    def _refresh_structure_tree(self):
        """Rafraîchir l'arbre de structure avec les données de la DB"""
        self.structure_tree.clear()
        
        if (self.strategy_widget.current_typology and 
            'clusters' in self.strategy_widget.current_typology):
            
            typology = self.strategy_widget.current_typology
            
            # Créer l'item racine pour la typologie
            typology_item = QtWidgets.QTreeWidgetItem([
                typology.get('name', 'Sans nom'), 
                'Typologie', 
                ''
            ])
            self.structure_tree.addTopLevelItem(typology_item)
            
            # Ajouter les clusters
            for cluster in typology.get('clusters', []):
                cluster_item = QtWidgets.QTreeWidgetItem([
                    cluster.get('name', 'Sans nom'), 
                    'Cluster', 
                    '0 exemples'  # À adapter avec les vraies statistiques
                ])
                typology_item.addChild(cluster_item)
                
                # Ajouter les racines
                for root in cluster.get('roots', []):
                    root_item = QtWidgets.QTreeWidgetItem([
                        root.get('name', 'Sans nom'), 
                        'Racine', 
                        '0 exemples'
                    ])
                    cluster_item.addChild(root_item)
                    
                    # Ajouter les parents
                    for parent in root.get('parents', []):
                        parent_item = QtWidgets.QTreeWidgetItem([
                            parent.get('name', 'Sans nom'), 
                            'Parent', 
                            '0 exemples'
                        ])
                        root_item.addChild(parent_item)
                        
                        # Ajouter les enfants
                        for child in parent.get('children', []):
                            child_item = QtWidgets.QTreeWidgetItem([
                                child.get('name', 'Sans nom'), 
                                'Enfant', 
                                '0 exemples'
                            ])
                            parent_item.addChild(child_item)
            
            # Développer tout l'arbre
            self.structure_tree.expandAll()
    
    def _refresh_structure_tree(self):
        """Rafraîchir l'arbre de structure"""
        self.structure_tree.clear()
        
        if (self.strategy_widget.current_typology_index != -1 and 
            self.strategy_widget.current_typology_index < len(self.strategy_widget.strategy_data.get('typologies', []))):
            
            typology = self.strategy_widget.strategy_data['typologies'][self.strategy_widget.current_typology_index]
            
            # Créer l'item racine pour la typologie
            typology_item = QtWidgets.QTreeWidgetItem([typology.get('name', 'Sans nom'), 'Typologie', ''])
            self.structure_tree.addTopLevelItem(typology_item)
            
            # Ajouter les clusters
            for cluster in typology.get('clusters', []):
                cluster_item = QtWidgets.QTreeWidgetItem([cluster.get('name', 'Sans nom'), 'Cluster', '250 exemples'])
                typology_item.addChild(cluster_item)
                
                # Ajouter les racines
                for root in cluster.get('roots', []):
                    root_item = QtWidgets.QTreeWidgetItem([root.get('name', 'Sans nom'), 'Racine', '100 exemples'])
                    cluster_item.addChild(root_item)
                    
                    # Ajouter les parents
                    for parent in root.get('parents', []):
                        parent_item = QtWidgets.QTreeWidgetItem([parent.get('name', 'Sans nom'), 'Parent', '50 exemples'])
                        root_item.addChild(parent_item)
                        
                        # Ajouter les enfants
                        for child in parent.get('children', []):
                            child_item = QtWidgets.QTreeWidgetItem([child, 'Enfant', '10 exemples'])
                            parent_item.addChild(child_item)
            
            # Développer tout l'arbre
            self.structure_tree.expandAll()
    
    def _on_typology_changed(self, typology_name):
        """Gérer le changement de typologie"""
        if not typology_name:
            return
            
        # Trouver l'ID de la typologie sélectionnée
        index = self.typology_combo.currentIndex()
        typology_id = self.typology_combo.itemData(index)
        
        if typology_id:
            self.current_typology_id = typology_id
            self._load_typology_data()
            self.refresh_ui()

    def _create_typology(self):
        """Créer une nouvelle typologie"""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un projet")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouvelle typologie", "Nom de la typologie:")
        if ok and name:
            try:
                typology_id = self.db.create_context_typology(self.current_project_id, name)
                self.current_typology_id = typology_id
                self._load_project_data()  # Recharger pour avoir la nouvelle typologie
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Typologie créée avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")
    
    def _on_typology_desc_changed(self):
        """Gérer le changement de description"""
        if self.strategy_widget.current_typology_index != -1:
            typology = self.strategy_widget.strategy_data['typologies'][self.strategy_widget.current_typology_index]
            typology['description'] = self.typology_desc_text.toPlainText()
    
    def _on_structure_item_clicked(self, item, column):
        """Gérer le clic sur un élément de la structure"""
        # Émettre un signal pour mettre à jour le camembert
        element_type = item.text(1)
        element_name = item.text(0)
        
        # Déterminer le niveau hiérarchique
        cluster = None
        root = None
        parent = None
        
        if element_type == 'Cluster':
            cluster = element_name
        elif element_type == 'Racine':
            cluster = item.parent().text(0) if item.parent() else None
            root = element_name
        elif element_type == 'Parent':
            root_item = item.parent()
            if root_item:
                cluster = root_item.parent().text(0) if root_item.parent() else None
                root = root_item.text(0)
            parent = element_name
        
        # Émettre le signal de sélection hiérarchique
        self.hierarchy_selection_changed.emit(cluster, root, parent)
    
    def set_hierarchy_selection(self, cluster, root, parent):
        """Définir la sélection hiérarchique depuis l'extérieur"""
        # Cette méthode peut être utilisée pour synchroniser la sélection
        pass  
    
    def _export_structure(self):
        """Exporter la structure hiérarchique"""
        try:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Exporter la structure", "", "JSON Files (*.json)"
            )
            if filename:
                if not filename.endswith('.json'):
                    filename += '.json'
                
                # Exporter les données de stratégie
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.strategy_widget.strategy_data, f, ensure_ascii=False, indent=2)
                
                QtWidgets.QMessageBox.information(self, "Succès", "Structure exportée avec succès!")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")

class StrategyWidget(QtWidgets.QWidget):
    """
    Widget pour la gestion des stratégies de typologies de contexte avec structure hiérarchique
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialiser la connexion à la base de données
        self.db = Database()
        
        # Initialiser les mappings
        self.cluster_list_map = {}
        self.root_list_map = {}
        self.parent_list_map = {}
        self.child_list_map = {}
        
        # Structure de données pour les typologies (maintenant stockée en DB)
        self.current_project_id = None
        self.current_typology_id = None
        self.current_cluster_id = None
        self.current_root_id = None
        self.current_parent_id = None
        
        # Structure de données pour les typologies
        self.strategy_data = {
            'project_name': '',
            'typologies': []
        }
        
         # AJOUTER CES ATTRIBUTS MANQUANTS :
        self.current_project = None
        self.typologies = []
        self.current_typology = None
        self.statistics = []
        
        # Indices de sélection (pour la compatibilité avec le code existant)
        self.current_typology_index = -1
        self.current_cluster_index = -1
        self.current_root_index = -1
        self.current_parent_index = -1
        self.current_child_index = -1
        
        self._init_ui()
        self._load_projects_from_db()
            

    def _init_ui(self):
        """Initialiser l'interface utilisateur"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Conteneur gauche pour les sections 1, 2 et 3
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Section 1: Sélection du profil de projet
        project_section = self._create_project_section()
        left_layout.addWidget(project_section)

        # Section 2: Détails du projet
        project_details_section = self._create_project_details_section()
        left_layout.addWidget(project_details_section)

        # Section 3: Typologie
        typology_section = self._create_typology_section()
        left_layout.addWidget(typology_section)

        # Espace flexible pour pousser les sections vers le haut
        left_layout.addStretch(1)

        # Conteneur droit pour la section 4 (plus large)
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Section 4: Gestion des typologies de contexte avec onglets
        context_typology_section = self._create_context_typology_section()
        right_layout.addWidget(context_typology_section)

        # Ajouter les conteneurs gauche et droit au layout principal
        main_layout.addWidget(left_container, 1)  # 1/3 de l'espace
        main_layout.addWidget(right_container, 2)  # 2/3 de l'espace
        
    def _load_projects_from_db(self):
        """Charger les projets depuis la base de données"""
        try:
            projects = self.db.get_typology_projects()
            if not projects:
                # Créer un projet par défaut si aucun n'existe
                self._create_default_project()
            else:
                # Charger le premier projet
                self.current_project_id = projects[0]['id']
                self._load_project_data()
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement des projets: {str(e)}")
            self._create_default_project()
            
    def _create_default_project(self):
        """Créer un projet par défaut"""
        try:
            project_id = self.db.create_typology_project(
                "Projet de démonstration", 
                "Projet de démonstration pour les typologies de contexte"
            )
            self.current_project_id = project_id
            
            # Créer une typologie par défaut
            typology_id = self.db.create_context_typology(
                project_id,
                "Typologie principale",
                "Typologie principale pour le projet de démonstration"
            )
            
            # Créer la structure hiérarchique par défaut
            self._create_default_typology_structure(typology_id)
            self._load_project_data()
            
        except Exception as e:
            logger.error(f"Erreur création projet par défaut: {str(e)}")

    def _create_default_typology_structure(self, typology_id):
        """Créer la structure hiérarchique par défaut"""
        # Cluster Débutant
        cluster1_id = self.db.create_typology_cluster(typology_id, "Débutant")
        root1_id = self.db.create_typology_root(cluster1_id, "Compétences de base")
        parent1_id = self.db.create_typology_parent(root1_id, "Connaissances fondamentales")
        self.db.create_typology_child(parent1_id, "Théorie")
        self.db.create_typology_child(parent1_id, "Définitions")
        self.db.create_typology_child(parent1_id, "Concepts de base")

        # Cluster Intermédiaire
        cluster2_id = self.db.create_typology_cluster(typology_id, "Intermédiaire")
        root2_id = self.db.create_typology_root(cluster2_id, "Compétences avancées")
        parent2_id = self.db.create_typology_parent(root2_id, "Applications pratiques")
        self.db.create_typology_child(parent2_id, "Exercices")
        self.db.create_typology_child(parent2_id, "Cas pratiques")
        self.db.create_typology_child(parent2_id, "Projets simples")

        # Cluster Avancé
        cluster3_id = self.db.create_typology_cluster(typology_id, "Avancé")
        root3_id = self.db.create_typology_root(cluster3_id, "Expertise spécialisée")
        parent3_id = self.db.create_typology_parent(root3_id, "Optimisation et recherche")
        self.db.create_typology_child(parent3_id, "Recherche avancée")
        self.db.create_typology_child(parent3_id, "Optimisation")
        self.db.create_typology_child(parent3_id, "Innovation")

        # Sauvegarder des statistiques d'exemple
        statistics = [
            {'cluster': 'Débutant', 'root': 'Compétences de base', 'parent': 'Connaissances fondamentales', 
             'name': 'Batch 1', 'examples': 250, 'percentage': 25.0},
            {'cluster': 'Intermédiaire', 'root': 'Compétences avancées', 'parent': 'Applications pratiques', 
             'name': 'Batch 2', 'examples': 350, 'percentage': 35.0},
            {'cluster': 'Avancé', 'root': 'Expertise spécialisée', 'parent': 'Optimisation et recherche', 
             'name': 'Batch 3', 'examples': 400, 'percentage': 40.0}
        ]
        self.db.save_typology_statistics(typology_id, statistics)
        
    def _load_project_data(self):
        """Charger les données du projet actuel depuis la DB"""
        if not self.current_project_id:
            return
            
        try:
            # Charger le projet
            self.current_project = self.db.get_typology_project(self.current_project_id)
            
            # Charger les typologies du projet
            self.typologies = self.db.get_typologies_by_project(self.current_project_id)
            
            if self.typologies:
                self.current_typology_id = self.typologies[0]['id']
                self._load_typology_data()
                
        except Exception as e:
            logger.error(f"Erreur chargement données projet: {str(e)}")

    def _load_typology_data(self):
        """Charger les données de la typologie actuelle depuis la DB"""
        if not self.current_typology_id:
            return
            
        try:
            # Charger la structure complète
            self.current_typology = self.db.get_complete_typology_structure(self.current_typology_id)
            
            # Charger les statistiques
            self.statistics = self.db.get_typology_statistics(self.current_typology_id)
            
        except Exception as e:
            logger.error(f"Erreur chargement données typologie: {str(e)}")

    def refresh_ui(self):
        """Rafraîchir l'interface utilisateur avec les données de la DB"""
        # Mettre à jour la liste des projets
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        
        projects = self.db.get_typology_projects()
        for project in projects:
            self.project_combo.addItem(project['name'], project['id'])
        
        # Sélectionner le projet courant
        if self.current_project_id:
            index = self.project_combo.findData(self.current_project_id)
            if index >= 0:
                self.project_combo.setCurrentIndex(index)
        
        self.project_combo.blockSignals(False)
        
        # Mettre à jour le nom du projet
        if self.current_project:
            self.project_name_label.setText(self.current_project['name'])
        else:
            self.project_name_label.setText("Aucun projet sélectionné")
        
        # Mettre à jour la liste des typologies
        self.typology_combo.blockSignals(True)
        self.typology_combo.clear()
        
        if self.typologies:
            for typology in self.typologies:
                self.typology_combo.addItem(typology['name'], typology['id'])
            
            # Sélectionner la typologie courante
            if self.current_typology_id:
                index = self.typology_combo.findData(self.current_typology_id)
                if index >= 0:
                    self.typology_combo.setCurrentIndex(index)
        
        self.typology_combo.blockSignals(False)
        
        # Mettre à jour les onglets
        self._refresh_cluster_tab()
        self._refresh_root_tab()
        self._refresh_parent_tab()
        self._refresh_child_tab()
        
        # Rafraîchir l'onglet projet et typologie
        self.project_typology_tab.refresh()
        
        # Mettre à jour le camembert avec les statistiques
        self._update_pie_chart()

    def _update_pie_chart(self):
        """Mettre à jour le camembert avec les données de la DB"""
        if hasattr(self, 'statistics') and self.statistics:
            # Convertir les statistiques en format compatible avec le camembert
            pie_data = {
                'total_examples': sum(stat['examples_count'] for stat in self.statistics),
                'batches': []
            }
            
            for stat in self.statistics:
                pie_data['batches'].append({
                    'name': stat['batch_name'],
                    'cluster': stat['cluster_name'],
                    'root': stat['root_name'],
                    'parent': stat['parent_name'],
                    'examples': stat['examples_count'],
                    'percentage': stat['percentage']
                })
            
            self.pie_chart.set_data(pie_data)
        else:
            # Données par défaut si pas de statistiques
            self.pie_chart.set_data(self.pie_chart.sample_data)
        
    def _get_group_style(self):
        """Obtenir le style pour les groupes"""
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

    def _get_combo_style(self):
        """Obtenir le style pour les combobox"""
        return """
            QComboBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
        """

    def _get_list_style(self):
        """Obtenir le style pour les listes"""
        return """
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """

    def _get_button_style(self, color):
        """Obtenir le style pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
        """

    def _darken_color(self, color, factor=0.1):
        """Assombrir une couleur"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return '#%02x%02x%02x' % darkened

    def _create_project_section(self):
        """Créer la section de sélection du projet"""
        group = QtWidgets.QGroupBox("Section 1: Sélection du profil de projet")
        group.setStyleSheet(self._get_group_style())
        layout = QtWidgets.QHBoxLayout(group)
        
        # Liste déroulante des projets
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(self._get_combo_style())
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        
        # Bouton créer un projet
        create_project_btn = QtWidgets.QPushButton("➕ Créer un projet")
        create_project_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        create_project_btn.clicked.connect(self._create_project)
        
        layout.addWidget(QtWidgets.QLabel("Projet:"))
        layout.addWidget(self.project_combo, 1)
        layout.addWidget(create_project_btn)
        
        return group

    def _create_project_details_section(self):
        """Créer la section des détails du projet"""
        group = QtWidgets.QGroupBox("Section 2: Détails du projet")
        group.setStyleSheet(self._get_group_style())
        layout = QtWidgets.QHBoxLayout(group)
        
        # Nom du projet
        self.project_name_label = QtWidgets.QLabel("Aucun projet sélectionné")
        self.project_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # Boutons d'action
        edit_project_btn = QtWidgets.QPushButton("✏️ Modifier")
        edit_project_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_project_btn.clicked.connect(self._edit_project)
        
        delete_project_btn = QtWidgets.QPushButton("🗑️ Supprimer")
        delete_project_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        delete_project_btn.clicked.connect(self._delete_project)
        
        layout.addWidget(self.project_name_label, 1)
        layout.addWidget(edit_project_btn)
        layout.addWidget(delete_project_btn)
        
        return group

    def _create_typology_section(self):
        """Créer la section de typologie"""
        group = QtWidgets.QGroupBox("Section 3: Typologie")
        group.setStyleSheet(self._get_group_style())
        layout = QtWidgets.QHBoxLayout(group)
        
        # Liste déroulante des typologies
        self.typology_combo = QtWidgets.QComboBox()
        self.typology_combo.setStyleSheet(self._get_combo_style())
        self.typology_combo.currentTextChanged.connect(self._on_typology_changed)
        
        # Bouton créer une typologie
        create_typology_btn = QtWidgets.QPushButton("➕ Créer une typologie")
        create_typology_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        create_typology_btn.clicked.connect(self._create_typology)
        
        layout.addWidget(QtWidgets.QLabel("Typologie:"))
        layout.addWidget(self.typology_combo, 1)
        layout.addWidget(create_typology_btn)
        
        return group

    def _create_context_typology_section(self):
        """Créer la section de gestion des typologies de contexte avec onglets"""
        group = QtWidgets.QGroupBox("Section 4: Gestion des typologies de contexte")
        group.setStyleSheet(self._get_group_style())
        
        main_layout = QtWidgets.QVBoxLayout(group)
        
        # Widget à onglets
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
        
        # Nouvel onglet: Projet et Typologie
        self.project_typology_tab = ProjectTypologyTab(self)
        self.tab_widget.addTab(self.project_typology_tab, "📋 Projet & Typologie")
        
        # Nouvel onglet: Camembert de répartition
        self.pie_chart_tab = self._create_pie_chart_tab()
        self.tab_widget.addTab(self.pie_chart_tab, "📊 Répartition Dataset")
        
        # Sous-section 1: Clusters
        cluster_tab = self._create_cluster_tab()
        self.tab_widget.addTab(cluster_tab, "📊 Clusters")
        
        # Sous-section 2: Racines
        root_tab = self._create_root_tab()
        self.tab_widget.addTab(root_tab, "🌳 Racines")
        
        # Sous-section 3: Parents
        parent_tab = self._create_parent_tab()
        self.tab_widget.addTab(parent_tab, "👨‍👩‍👧 Parents")
        
        # Sous-section 4: Enfants
        child_tab = self._create_child_tab()
        self.tab_widget.addTab(child_tab, "👶 Enfants")
        
        main_layout.addWidget(self.tab_widget)
        
        # Bouton de sauvegarde dans la section 4
        save_btn = QtWidgets.QPushButton("💾 Sauvegarder la stratégie")
        save_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        save_btn.clicked.connect(self._save_strategy)
        main_layout.addWidget(save_btn)
        
        return group

    def _create_pie_chart_tab(self):
        """Créer l'onglet avec le camembert de répartition (version originale)"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Titre et description
        header_layout = QtWidgets.QVBoxLayout()
        title_label = QtWidgets.QLabel("Répartition du Dataset par Typologie de Contexte")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        desc_label = QtWidgets.QLabel(
            "Le camembert montre la répartition des exemples par batch selon la typologie de contexte. "
            "Cliquez sur les éléments de la hiérarchie pour filtrer l'affichage."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        header_layout.addWidget(desc_label)
        
        layout.addLayout(header_layout)
        
        # Conteneur pour le camembert et les contrôles (côte à côte)
        content_layout = QtWidgets.QHBoxLayout()
        
        # Camembert à GAUCHE
        self.pie_chart = PieChartWidget()
        content_layout.addWidget(self.pie_chart, 2)  # 2/3 de l'espace à gauche
        
        # Contrôles à DROITE
        controls_layout = QtWidgets.QVBoxLayout()
        
        # Informations de sélection
        info_group = QtWidgets.QGroupBox("Sélection Actuelle")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        self.selection_info = QtWidgets.QLabel("Aucune sélection")
        self.selection_info.setWordWrap(True)
        info_layout.addWidget(self.selection_info)
        
        controls_layout.addWidget(info_group)
        
        # Statistiques
        stats_group = QtWidgets.QGroupBox("Statistiques")
        stats_layout = QtWidgets.QGridLayout(stats_group)
        
        stats_layout.addWidget(QtWidgets.QLabel("Total dataset:"), 0, 0)
        self.total_dataset_label = QtWidgets.QLabel("1000 exemples")
        stats_layout.addWidget(self.total_dataset_label, 0, 1)
        
        stats_layout.addWidget(QtWidgets.QLabel("Batches:"), 1, 0)
        self.batches_count_label = QtWidgets.QLabel("3 batches")
        stats_layout.addWidget(self.batches_count_label, 1, 1)
        
        stats_layout.addWidget(QtWidgets.QLabel("Typologies:"), 2, 0)
        self.typologies_stats_label = QtWidgets.QLabel("1 typologie")
        stats_layout.addWidget(self.typologies_stats_label, 2, 1)
        
        controls_layout.addWidget(stats_group)
        
        # Boutons de contrôle
        buttons_layout = QtWidgets.QVBoxLayout()
        
        reset_btn = QtWidgets.QPushButton("Réinitialiser la vue")
        reset_btn.clicked.connect(self._reset_pie_chart_view)
        buttons_layout.addWidget(reset_btn)
        
        export_chart_btn = QtWidgets.QPushButton("Exporter le graphique")
        export_chart_btn.clicked.connect(self._export_pie_chart)
        buttons_layout.addWidget(export_chart_btn)
        
        controls_layout.addLayout(buttons_layout)
        controls_layout.addStretch()
        
        content_layout.addLayout(controls_layout, 1)  # 1/3 de l'espace à droite
        layout.addLayout(content_layout)
        
        # Connexions des signaux
        self.project_typology_tab.hierarchy_selection_changed.connect(self._on_hierarchy_selection_changed)
        self.pie_chart.segment_clicked.connect(self._on_pie_segment_clicked)
        
        return widget

    def _create_cluster_tab(self):
        """Créer l'onglet Clusters"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Liste des clusters
        self.cluster_list = QtWidgets.QListWidget()
        self.cluster_list.setStyleSheet(self._get_list_style())
        self.cluster_list.currentRowChanged.connect(self._on_cluster_selected)
        layout.addWidget(self.cluster_list)
        
        # Boutons d'action
        btn_layout = QtWidgets.QHBoxLayout()
        add_cluster_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_cluster_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_cluster_btn.clicked.connect(self._add_cluster)
        
        edit_cluster_btn = QtWidgets.QPushButton("✏️ Modifier")
        edit_cluster_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_cluster_btn.clicked.connect(self._edit_cluster)
        
        delete_cluster_btn = QtWidgets.QPushButton("🗑️ Supprimer")
        delete_cluster_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        delete_cluster_btn.clicked.connect(self._delete_cluster)
        
        btn_layout.addWidget(add_cluster_btn)
        btn_layout.addWidget(edit_cluster_btn)
        btn_layout.addWidget(delete_cluster_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def _create_root_tab(self):
        """Créer l'onglet Racines"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Sélection du cluster
        cluster_layout = QtWidgets.QHBoxLayout()
        cluster_layout.addWidget(QtWidgets.QLabel("Cluster:"))
        self.root_cluster_combo = QtWidgets.QComboBox()
        self.root_cluster_combo.currentTextChanged.connect(self._on_root_cluster_changed)
        cluster_layout.addWidget(self.root_cluster_combo, 1)
        layout.addLayout(cluster_layout)
        
        # Liste des racines
        self.root_list = QtWidgets.QListWidget()
        self.root_list.setStyleSheet(self._get_list_style())
        self.root_list.currentRowChanged.connect(self._on_root_selected)
        layout.addWidget(self.root_list)
        
        # Boutons d'action
        btn_layout = QtWidgets.QHBoxLayout()
        add_root_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_root_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_root_btn.clicked.connect(self._add_root)
        
        edit_root_btn = QtWidgets.QPushButton("✏️ Modifier")
        edit_root_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_root_btn.clicked.connect(self._edit_root)
        
        delete_root_btn = QtWidgets.QPushButton("🗑️ Supprimer")
        delete_root_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        delete_root_btn.clicked.connect(self._delete_root)
        
        btn_layout.addWidget(add_root_btn)
        btn_layout.addWidget(edit_root_btn)
        btn_layout.addWidget(delete_root_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def _create_parent_tab(self):
        """Créer l'onglet Parents"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Sélection du cluster et racine
        selection_layout = QtWidgets.QGridLayout()
        selection_layout.addWidget(QtWidgets.QLabel("Cluster:"), 0, 0)
        self.parent_cluster_combo = QtWidgets.QComboBox()
        self.parent_cluster_combo.currentTextChanged.connect(self._on_parent_cluster_changed)
        selection_layout.addWidget(self.parent_cluster_combo, 0, 1)
        
        selection_layout.addWidget(QtWidgets.QLabel("Racine:"), 1, 0)
        self.parent_root_combo = QtWidgets.QComboBox()
        self.parent_root_combo.currentTextChanged.connect(self._on_parent_root_changed)
        selection_layout.addWidget(self.parent_root_combo, 1, 1)
        layout.addLayout(selection_layout)
        
        # Liste des parents
        self.parent_list = QtWidgets.QListWidget()
        self.parent_list.setStyleSheet(self._get_list_style())
        self.parent_list.currentRowChanged.connect(self._on_parent_selected)
        layout.addWidget(self.parent_list)
        
        # Boutons d'action
        btn_layout = QtWidgets.QHBoxLayout()
        add_parent_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_parent_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_parent_btn.clicked.connect(self._add_parent)
        
        edit_parent_btn = QtWidgets.QPushButton("✏️ Modifier")
        edit_parent_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_parent_btn.clicked.connect(self._edit_parent)
        
        delete_parent_btn = QtWidgets.QPushButton("🗑️ Supprimer")
        delete_parent_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        delete_parent_btn.clicked.connect(self._delete_parent)
        
        btn_layout.addWidget(add_parent_btn)
        btn_layout.addWidget(edit_parent_btn)
        btn_layout.addWidget(delete_parent_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def _create_child_tab(self):
        """Créer l'onglet Enfants"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Sélection hiérarchique
        selection_layout = QtWidgets.QGridLayout()
        selection_layout.addWidget(QtWidgets.QLabel("Cluster:"), 0, 0)
        self.child_cluster_combo = QtWidgets.QComboBox()
        self.child_cluster_combo.currentTextChanged.connect(self._on_child_cluster_changed)
        selection_layout.addWidget(self.child_cluster_combo, 0, 1)
        
        selection_layout.addWidget(QtWidgets.QLabel("Racine:"), 1, 0)
        self.child_root_combo = QtWidgets.QComboBox()
        self.child_root_combo.currentTextChanged.connect(self._on_child_root_changed)
        selection_layout.addWidget(self.child_root_combo, 1, 1)
        
        selection_layout.addWidget(QtWidgets.QLabel("Parent:"), 2, 0)
        self.child_parent_combo = QtWidgets.QComboBox()
        self.child_parent_combo.currentTextChanged.connect(self._on_child_parent_changed)
        selection_layout.addWidget(self.child_parent_combo, 2, 1)
        layout.addLayout(selection_layout)
        
        # Liste des enfants
        self.child_list = QtWidgets.QListWidget()
        self.child_list.setStyleSheet(self._get_list_style())
        self.child_list.currentRowChanged.connect(self._on_child_selected)
        layout.addWidget(self.child_list)
        
        # Boutons d'action
        btn_layout = QtWidgets.QHBoxLayout()
        add_child_btn = QtWidgets.QPushButton("➕ Ajouter")
        add_child_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        add_child_btn.clicked.connect(self._add_child)
        
        edit_child_btn = QtWidgets.QPushButton("✏️ Modifier")
        edit_child_btn.setStyleSheet(self._get_button_style(Theme.SECONDARY_COLOR))
        edit_child_btn.clicked.connect(self._edit_child)
        
        delete_child_btn = QtWidgets.QPushButton("🗑️ Supprimer")
        delete_child_btn.setStyleSheet(self._get_button_style("#e74c3c"))
        delete_child_btn.clicked.connect(self._delete_child)
        
        btn_layout.addWidget(add_child_btn)
        btn_layout.addWidget(edit_child_btn)
        btn_layout.addWidget(delete_child_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def _get_group_style(self):
        """Style pour les groupes"""
        return """
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #333333;
            }
        """

    def _get_button_style(self, color):
        """Style pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
        """

    def _darken_color(self, color, factor=0.1):
        """Assombrir une couleur"""
        try:
            color = color.lstrip('#')
            rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            darkened = tuple(int(c * (1 - factor)) for c in rgb)
            return '#%02x%02x%02x' % darkened
        except:
            return color

    def _get_combo_style(self):
        """Obtenir le style pour les combobox"""
        return """
            QComboBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
        """

    def _get_list_style(self):
        """Obtenir le style pour les listes"""
        return """
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """

    def _get_button_style(self, color):
        """Obtenir le style pour les boutons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
        """

    def _darken_color(self, color, factor=0.1):
        """Assombrir une couleur"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return '#%02x%02x%02x' % darkened

    def _load_default_data(self):
        """Charger les données depuis la base de données"""
        self._load_projects_from_db()

    def refresh_ui(self):
        """Rafraîchir l'interface utilisateur"""
        # Mettre à jour la liste des projets
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem(self.strategy_data['project_name'])
        self.project_combo.blockSignals(False)
        
        # Mettre à jour le nom du projet
        self.project_name_label.setText(self.strategy_data['project_name'])
        
        # Mettre à jour la liste des typologies
        self.typology_combo.blockSignals(True)
        self.typology_combo.clear()
        for typology in self.strategy_data['typologies']:
            self.typology_combo.addItem(typology['name'])
        self.typology_combo.blockSignals(True)
        
        # Mettre à jour les onglets
        self._refresh_cluster_tab()
        self._refresh_root_tab()
        self._refresh_parent_tab()
        self._refresh_child_tab()
        
        # Rafraîchir l'onglet projet et typologie
        self.project_typology_tab.refresh()
        
        # Mettre à jour le camembert
        self.pie_chart.update()

    def _refresh_cluster_tab(self):
        """Rafraîchir l'onglet Clusters avec les données de la DB"""
        self.cluster_list.clear()
        self.cluster_list_map = {}
        
        if self.current_typology and 'clusters' in self.current_typology:
            for i, cluster in enumerate(self.current_typology['clusters']):
                self.cluster_list.addItem(cluster['name'])
                self.cluster_list_map[cluster['name']] = cluster['id']
                
                # Mettre à jour l'index si c'est le cluster actuel
                if self.current_cluster_id == cluster['id']:
                    self.current_cluster_index = i

    def _refresh_root_tab(self):
        """Rafraîchir l'onglet Racines avec les données de la DB"""
        self.root_cluster_combo.blockSignals(True)
        self.root_cluster_combo.clear()
        self.root_list.clear()
        self.root_list_map = {}
        
        if self.current_typology and 'clusters' in self.current_typology:
            for cluster in self.current_typology['clusters']:
                self.root_cluster_combo.addItem(cluster['name'], cluster['id'])
        
        self.root_cluster_combo.blockSignals(False)
        self._on_root_cluster_changed(self.root_cluster_combo.currentText())

    def _refresh_parent_tab(self):
        """Rafraîchir l'onglet Parents avec les données de la DB"""
        self.parent_cluster_combo.blockSignals(True)
        self.parent_cluster_combo.clear()
        self.parent_root_combo.clear()
        self.parent_list.clear()
        self.parent_list_map = {}
        
        if self.current_typology and 'clusters' in self.current_typology:
            for cluster in self.current_typology['clusters']:
                self.parent_cluster_combo.addItem(cluster['name'], cluster['id'])
        
        self.parent_cluster_combo.blockSignals(False)
        self._on_parent_cluster_changed(self.parent_cluster_combo.currentText())

    def _refresh_child_tab(self):
        """Rafraîchir l'onglet Enfants avec les données de la DB"""
        self.child_cluster_combo.blockSignals(True)
        self.child_cluster_combo.clear()
        self.child_root_combo.clear()
        self.child_parent_combo.clear()
        self.child_list.clear()
        self.child_list_map = {}
        
        if self.current_typology and 'clusters' in self.current_typology:
            for cluster in self.current_typology['clusters']:
                self.child_cluster_combo.addItem(cluster['name'], cluster['id'])
        
        self.child_cluster_combo.blockSignals(False)
        self._on_child_cluster_changed(self.child_cluster_combo.currentText())
        
        # Gestionnaires d'événements pour les onglets
    def _on_project_changed(self, project_name):
        """Gérer le changement de projet"""
        if not project_name:
            return
        
        
        
        # Trouver l'ID du projet sélectionné
        index = self.project_combo.currentIndex()
        project_id = self.project_combo.itemData(index)
        
        if project_id:
            self.current_project_id = project_id
            self._load_project_data()
            self.refresh_ui()

    def _on_typology_changed(self, typology_name):
        """Gérer le changement de typologie"""
        if not typology_name:
            return
            
        # Trouver l'ID de la typologie sélectionnée
        index = self.typology_combo.currentIndex()
        typology_id = self.typology_combo.itemData(index)
        
        if typology_id:
            self.current_typology_id = typology_id
            self._load_typology_data()
            self.refresh_ui()
            
            # Mettre à jour l'index pour la compatibilité
            for i, typology in enumerate(self.typologies):
                if typology['id'] == typology_id:
                    self.current_typology_index = i
                    break
            
    def _on_cluster_selected(self, row):
        """Gérer la sélection d'un cluster"""
        self.current_cluster_index = row
        if row >= 0:
                item = self.cluster_list.item(row)
                cluster_name = item.text()
                self.current_cluster_id = self.cluster_list_map.get(cluster_name)

    def _on_root_cluster_changed(self, cluster_name):
        """Gérer le changement de cluster dans l'onglet Racines"""
        self.root_list.clear()
        self.root_list_map = {}
        
        if not cluster_name:
            return
            
        # Trouver l'ID du cluster sélectionné
        cluster_id = None
        for i in range(self.root_cluster_combo.count()):
            if self.root_cluster_combo.itemText(i) == cluster_name:
                cluster_id = self.root_cluster_combo.itemData(i)
                break
        
        if cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        self.root_list.addItem(root['name'])
                        self.root_list_map[root['name']] = root['id']
                    break

    def _on_root_selected(self, row):
        """Gérer la sélection d'une racine"""
        self.current_root_index = row
        if row >= 0:
            item = self.root_list.item(row)
            root_name = item.text()
            self.current_root_id = self.root_list_map.get(root_name)

    def _on_parent_cluster_changed(self, cluster_name):
        """Gérer le changement de cluster dans l'onglet Parents"""
        self.parent_root_combo.blockSignals(True)
        self.parent_root_combo.clear()
        self.parent_list.clear()
        self.parent_list_map = {}
        
        if not cluster_name:
            return
            
        # Trouver l'ID du cluster sélectionné
        cluster_id = None
        for i in range(self.parent_cluster_combo.count()):
            if self.parent_cluster_combo.itemText(i) == cluster_name:
                cluster_id = self.parent_cluster_combo.itemData(i)
                break
        
        if cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        self.parent_root_combo.addItem(root['name'], root['id'])
                    break
        
        self.parent_root_combo.blockSignals(False)
        self._on_parent_root_changed(self.parent_root_combo.currentText())

    def _on_parent_root_changed(self, root_name):
        """Gérer le changement de racine dans l'onglet Parents"""
        self.parent_list.clear()
        self.parent_list_map = {}
        
        if not root_name:
            return
            
        # Trouver l'ID de la racine sélectionnée
        root_id = None
        for i in range(self.parent_root_combo.count()):
            if self.parent_root_combo.itemText(i) == root_name:
                root_id = self.parent_root_combo.itemData(i)
                break
        
        cluster_id = self.parent_cluster_combo.currentData()
        
        if root_id and cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                self.parent_list.addItem(parent['name'])
                                self.parent_list_map[parent['name']] = parent['id']
                            break
                    break

    def _on_parent_selected(self, row):
        """Gérer la sélection d'un parent"""
        self.current_parent_index = row
        if row >= 0:
            item = self.parent_list.item(row)
            parent_name = item.text()
            self.current_parent_id = self.parent_list_map.get(parent_name)

    def _add_parent(self):
        """Ajouter un parent"""
        root_id = self.parent_root_combo.currentData()
        if not root_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner une racine")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau parent", "Nom du parent:")
        if ok and name:
            try:
                parent_id = self.db.create_typology_parent(root_id, name)
                self._load_typology_data()
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Parent créé avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    def _on_parent_selected(self, row):
        """Gérer la sélection d'un parent"""
        self.current_parent_index = row

    def _on_child_cluster_changed(self, cluster_name):
        """Gérer le changement de cluster dans l'onglet Enfants"""
        self.child_root_combo.blockSignals(True)
        self.child_root_combo.clear()
        self.child_parent_combo.clear()
        self.child_list.clear()
        self.child_list_map = {}
        
        if not cluster_name:
            return
            
        # Trouver l'ID du cluster sélectionné
        cluster_id = None
        for i in range(self.child_cluster_combo.count()):
            if self.child_cluster_combo.itemText(i) == cluster_name:
                cluster_id = self.child_cluster_combo.itemData(i)
                break
        
        if cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        self.child_root_combo.addItem(root['name'], root['id'])
                    break
        
        self.child_root_combo.blockSignals(False)
        self._on_child_root_changed(self.child_root_combo.currentText())

    def _on_child_root_changed(self, root_name):
        """Gérer le changement de racine dans l'onglet Enfants"""
        self.child_parent_combo.blockSignals(True)
        self.child_parent_combo.clear()
        self.child_list.clear()
        self.child_list_map = {}
        
        if not root_name:
            return
            
        # Trouver l'ID de la racine sélectionnée
        root_id = None
        for i in range(self.child_root_combo.count()):
            if self.child_root_combo.itemText(i) == root_name:
                root_id = self.child_root_combo.itemData(i)
                break
        
        cluster_id = self.child_cluster_combo.currentData()
        
        if root_id and cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                self.child_parent_combo.addItem(parent['name'], parent['id'])
                            break
                    break
        
        self.child_parent_combo.blockSignals(False)
        self._on_child_parent_changed(self.child_parent_combo.currentText())


    def _on_child_root_changed(self, root_name):
        """Gérer le changement de racine dans l'onglet Enfants"""
        self.child_parent_combo.blockSignals(True)
        self.child_parent_combo.clear()
        self.child_list.clear()
        
        if (self.current_typology_index != -1 and 
            self.child_cluster_combo.currentText() and root_name):
            
            typology = self.strategy_data['typologies'][self.current_typology_index]
            for cluster in typology['clusters']:
                if cluster['name'] == self.child_cluster_combo.currentText():
                    for root in cluster['roots']:
                        if root['name'] == root_name:
                            for parent in root['parents']:
                                self.child_parent_combo.addItem(parent['name'])
                            break
                    break
        
        self.child_parent_combo.blockSignals(False)
        self._on_child_parent_changed(self.child_parent_combo.currentText())

    def _on_child_parent_changed(self, parent_name):
        """Gérer le changement de parent dans l'onglet Enfants"""
        self.child_list.clear()
        self.child_list_map = {}
        
        if not parent_name:
            return
            
        # Trouver l'ID du parent sélectionné
        parent_id = None
        for i in range(self.child_parent_combo.count()):
            if self.child_parent_combo.itemText(i) == parent_name:
                parent_id = self.child_parent_combo.itemData(i)
                break
        
        root_id = self.child_root_combo.currentData()
        cluster_id = self.child_cluster_combo.currentData()
        
        if parent_id and root_id and cluster_id and self.current_typology:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                if parent['id'] == parent_id:
                                    for child in parent.get('children', []):
                                        self.child_list.addItem(child['name'])
                                        self.child_list_map[child['name']] = child['id']
                                    break
                            break
                    break

    def _on_child_selected(self, row):
        """Gérer la sélection d'un enfant"""
        self.current_child_index = row
        if row >= 0:
            item = self.child_list.item(row)
            child_name = item.text()
            self.current_child_id = self.child_list_map.get(child_name)

    def _create_project(self):
        """Créer un nouveau projet"""
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau projet", "Nom du projet:")
        if ok and name:
            try:
                project_id = self.db.create_typology_project(name)
                self.current_project_id = project_id
                self._load_project_data()
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Projet créé avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création du projet: {str(e)}")

    def _edit_project(self):
        """Modifier le projet actuel"""
        if not self.current_project:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier le projet", "Nom du projet:", 
            text=self.current_project['name']
        )
        
        if ok and name:
            try:
                success = self.db.update_typology_project(self.current_project_id, name=name)
                if success:
                    self._load_project_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Projet modifié avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la modification du projet")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")

    def _delete_project(self):
        """Supprimer le projet actuel"""
        if not self.current_project:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné")
            return
            
        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer le projet", 
            f"Êtes-vous sûr de vouloir supprimer le projet '{self.current_project['name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.db.delete_typology_project(self.current_project_id)
                if success:
                    # Recharger les projets
                    projects = self.db.get_typology_projects()
                    if projects:
                        self.current_project_id = projects[0]['id']
                        self._load_project_data()
                    else:
                        self.current_project_id = None
                        self.current_project = None
                        self.typologies = []
                    
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Projet supprimé avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression du projet")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")

    def _create_typology(self):
        """Créer une nouvelle typologie"""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un projet")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouvelle typologie", "Nom de la typologie:")
        if ok and name:
            try:
                typology_id = self.db.create_context_typology(self.current_project_id, name)
                self.current_typology_id = typology_id
                self._load_project_data()  # Recharger pour avoir la nouvelle typologie
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Typologie créée avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    def _add_cluster(self):
        """Ajouter un cluster"""
        if not self.current_typology_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner une typologie")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau cluster", "Nom du cluster:")
        if ok and name:
            try:
                cluster_id = self.db.create_typology_cluster(self.current_typology_id, name)
                self._load_typology_data()
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Cluster créé avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    def _edit_cluster(self):
        """Modifier un cluster"""
        if not self.current_cluster_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un cluster")
            return
            
        # Trouver le cluster actuel
        current_cluster = None
        for cluster in self.current_typology.get('clusters', []):
            if cluster['id'] == self.current_cluster_id:
                current_cluster = cluster
                break
        
        if not current_cluster:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Cluster non trouvé")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier le cluster", "Nom du cluster:", 
            text=current_cluster['name']
        )
        
        if ok and name:
            try:
                # Mettre à jour dans la base de données
                success = self.db.update_typology_cluster(self.current_cluster_id, name=name)
                if success:
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Cluster modifié avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la modification")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")
    
    def _edit_cluster(self):
        """Modifier un cluster"""
        if self.current_cluster_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un cluster")
            return
            
        typology = self.strategy_data['typologies'][self.current_typology_index]
        cluster = typology['clusters'][self.current_cluster_index]
        
        name, ok = QtWidgets.QInputDialog.getText(self, "Modifier le cluster", "Nom du cluster:", 
                                                 text=cluster['name'])
        if ok and name:
            cluster['name'] = name
            self.refresh_ui()

    def _delete_cluster(self):
        """Supprimer un cluster"""
        if not self.current_cluster_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un cluster")
            return
            
        # Trouver le nom du cluster
        cluster_name = ""
        for cluster in self.current_typology.get('clusters', []):
            if cluster['id'] == self.current_cluster_id:
                cluster_name = cluster['name']
                break
        
        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer le cluster", 
            f"Êtes-vous sûr de vouloir supprimer le cluster '{cluster_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.db.delete_typology_cluster(self.current_cluster_id)
                if success:
                    self.current_cluster_id = None
                    self.current_cluster_index = -1
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Cluster supprimé avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")


    def _add_root(self):
        """Ajouter une racine"""
        cluster_id = self.root_cluster_combo.currentData()
        if not cluster_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un cluster")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouvelle racine", "Nom de la racine:")
        if ok and name:
            try:
                root_id = self.db.create_typology_root(cluster_id, name)
                self._load_typology_data()
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Racine créée avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    def _edit_root(self):
        """Modifier une racine"""
        if not self.current_root_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner une racine")
            return
            
        # Trouver la racine actuelle
        current_root = None
        cluster_id = self.root_cluster_combo.currentData()
        
        if self.current_typology and cluster_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == self.current_root_id:
                            current_root = root
                            break
                    break
        
        if not current_root:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Racine non trouvée")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier la racine", "Nom de la racine:", 
            text=current_root['name']
        )
        
        if ok and name:
            try:
                success = self.db.update_typology_root(self.current_root_id, name=name)
                if success:
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Racine modifiée avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la modification")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")


    def _delete_root(self):
        """Supprimer une racine"""
        if not self.current_root_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner une racine")
            return
            
        # Trouver le nom de la racine
        root_name = ""
        cluster_id = self.root_cluster_combo.currentData()
        
        if self.current_typology and cluster_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == self.current_root_id:
                            root_name = root['name']
                            break
                    break
        
        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer la racine", 
            f"Êtes-vous sûr de vouloir supprimer la racine '{root_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.db.delete_typology_root(self.current_root_id)
                if success:
                    self.current_root_id = None
                    self.current_root_index = -1
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Racine supprimée avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")

    def _add_parent(self):
        """Ajouter un parent"""
        if (self.parent_cluster_combo.currentText() == '' or 
            self.parent_root_combo.currentText() == ''):
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un cluster et une racine")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau parent", "Nom du parent:")
        if ok and name:
            typology = self.strategy_data['typologies'][self.current_typology_index]
            for cluster in typology['clusters']:
                if cluster['name'] == self.parent_cluster_combo.currentText():
                    for root in cluster['roots']:
                        if root['name'] == self.parent_root_combo.currentText():
                            new_parent = {
                                'name': name,
                                'children': []
                            }
                            root['parents'].append(new_parent)
                            break
                    break
            self.refresh_ui()

    def _edit_parent(self):
        """Modifier un parent"""
        if not self.current_parent_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un parent")
            return
            
        # Trouver le parent actuel
        current_parent = None
        root_id = self.parent_root_combo.currentData()
        cluster_id = self.parent_cluster_combo.currentData()
        
        if self.current_typology and cluster_id and root_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                if parent['id'] == self.current_parent_id:
                                    current_parent = parent
                                    break
                            break
                    break
        
        if not current_parent:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Parent non trouvé")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier le parent", "Nom du parent:", 
            text=current_parent['name']
        )
        
        if ok and name:
            try:
                success = self.db.update_typology_parent(self.current_parent_id, name=name)
                if success:
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Parent modifié avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la modification")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")

    def _delete_parent(self):
        """Supprimer un parent"""
        if not self.current_parent_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un parent")
            return
            
        # Trouver le nom du parent
        parent_name = ""
        root_id = self.parent_root_combo.currentData()
        cluster_id = self.parent_cluster_combo.currentData()
        
        if self.current_typology and cluster_id and root_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                if parent['id'] == self.current_parent_id:
                                    parent_name = parent['name']
                                    break
                            break
                    break
        
        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer le parent", 
            f"Êtes-vous sûr de vouloir supprimer le parent '{parent_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.db.delete_typology_parent(self.current_parent_id)
                if success:
                    self.current_parent_id = None
                    self.current_parent_index = -1
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Parent supprimé avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")

    def _add_child(self):
        """Ajouter un enfant"""
        parent_id = self.child_parent_combo.currentData()
        if not parent_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un parent")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouvel enfant", "Nom de l'enfant:")
        if ok and name:
            try:
                child_id = self.db.create_typology_child(parent_id, name)
                self._load_typology_data()
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, "Succès", "Enfant créé avec succès!")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")

    def _edit_child(self):
        """Modifier un enfant"""
        if not self.current_child_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un enfant")
            return
            
        # Trouver l'enfant actuel
        current_child = None
        parent_id = self.child_parent_combo.currentData()
        root_id = self.child_root_combo.currentData()
        cluster_id = self.child_cluster_combo.currentData()
        
        if self.current_typology and cluster_id and root_id and parent_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                if parent['id'] == parent_id:
                                    for child in parent.get('children', []):
                                        if child['id'] == self.current_child_id:
                                            current_child = child
                                            break
                                    break
                            break
                    break
        
        if not current_child:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Enfant non trouvé")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Modifier l'enfant", "Nom de l'enfant:", 
            text=current_child['name']
        )
        
        if ok and name:
            try:
                success = self.db.update_typology_child(self.current_child_id, name=name)
                if success:
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Enfant modifié avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la modification")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")


    def _edit_child(self):
        """Modifier un enfant"""
        if self.current_child_index == -1:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un enfant")
            return
            
        typology = self.strategy_data['typologies'][self.current_typology_index]
        for cluster in typology['clusters']:
            if cluster['name'] == self.child_cluster_combo.currentText():
                for root in cluster['roots']:
                    if root['name'] == self.child_root_combo.currentText():
                        for parent in root['parents']:
                            if parent['name'] == self.child_parent_combo.currentText():
                                old_name = parent['children'][self.current_child_index]
                                name, ok = QtWidgets.QInputDialog.getText(self, "Modifier l'enfant", "Nom de l'enfant:", 
                                                                         text=old_name)
                                if ok and name:
                                    parent['children'][self.current_child_index] = name
                                    self.refresh_ui()
                                break
                        break
                break

    def _delete_child(self):
        """Supprimer un enfant"""
        if not self.current_child_id:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un enfant")
            return
            
        # Trouver le nom de l'enfant
        child_name = ""
        parent_id = self.child_parent_combo.currentData()
        root_id = self.child_root_combo.currentData()
        cluster_id = self.child_cluster_combo.currentData()
        
        if self.current_typology and cluster_id and root_id and parent_id:
            for cluster in self.current_typology.get('clusters', []):
                if cluster['id'] == cluster_id:
                    for root in cluster.get('roots', []):
                        if root['id'] == root_id:
                            for parent in root.get('parents', []):
                                if parent['id'] == parent_id:
                                    for child in parent.get('children', []):
                                        if child['id'] == self.current_child_id:
                                            child_name = child['name']
                                            break
                                    break
                            break
                    break
        
        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer l'enfant", 
            f"Êtes-vous sûr de vouloir supprimer l'enfant '{child_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                success = self.db.delete_typology_child(self.current_child_id)
                if success:
                    self.current_child_id = None
                    self.current_child_index = -1
                    self._load_typology_data()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(self, "Succès", "Enfant supprimé avec succès!")
                else:
                    QtWidgets.QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")


    def _save_strategy(self):
        """Sauvegarder la stratégie"""
        try:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Sauvegarder la stratégie", "", "JSON Files (*.json)"
            )
            if filename:
                if not filename.endswith('.json'):
                    filename += '.json'
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.strategy_data, f, ensure_ascii=False, indent=2)
                
                QtWidgets.QMessageBox.information(self, "Succès", "Stratégie sauvegardée avec succès!")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")

    # Méthodes pour le camembert
    def _on_hierarchy_selection_changed(self, cluster, root, parent):
        """Gérer le changement de sélection hiérarchique"""
        # Mettre à jour le camembert
        self.pie_chart.set_hierarchy_selection(cluster, root, parent)
        
        # Mettre à jour les informations de sélection
        selection_text = ""
        if cluster:
            selection_text += f"<b>Cluster:</b> {cluster}<br>"
        if root:
            selection_text += f"<b>Racine:</b> {root}<br>"
        if parent:
            selection_text += f"<b>Parent:</b> {parent}"
        
        if not selection_text:
            selection_text = "Aucune sélection (vue globale)"
            
        self.selection_info.setText(selection_text)

    def _on_pie_segment_clicked(self, batch_data):
        """Gérer le clic sur un segment du camembert"""
        # Mettre à jour la sélection hiérarchique
        self._on_hierarchy_selection_changed(
            batch_data.get('cluster'), 
            batch_data.get('root'), 
            batch_data.get('parent')
        )
        
        # Mettre à jour l'arbre de structure dans l'onglet projet
        self.project_typology_tab.set_hierarchy_selection(
            batch_data.get('cluster'), 
            batch_data.get('root'), 
            batch_data.get('parent')
        )

    def _reset_pie_chart_view(self):
        """Réinitialiser la vue du camembert"""
        self._on_hierarchy_selection_changed(None, None, None)

    def _export_pie_chart(self):
        """Exporter le graphique en image"""
        try:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Exporter le graphique", "", "PNG Files (*.png);;JPEG Files (*.jpg)"
            )
            if filename:
                # Capturer le widget en tant qu'image
                pixmap = self.pie_chart.grab()
                pixmap.save(filename)
                QtWidgets.QMessageBox.information(self, "Succès", "Graphique exporté avec succès!")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = StrategyWidget()
    widget.show()
    sys.exit(app.exec_())