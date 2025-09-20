#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/strategy_widget.py - Widget pour la gestion des stratégies et typologies de contexte
"""

import json
import sqlite3
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem
#from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice

try:
    from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice
    QT_CHARTS_AVAILABLE = True
except ImportError:
    QT_CHARTS_AVAILABLE = False
    # Créer des classes factices pour éviter les erreurs
    class QChart:
        pass
    class QChartView(QtWidgets.QWidget):
        pass
    class QPieSeries:
        pass
    class QPieSlice:
        pass

from ui.localization.translator import tr
from utils.logger import logger


class StrategyWidget(QWidget):
    """Widget pour la gestion des stratégies et typologies de contexte"""
    
    # Signaux
    context_hierarchy_changed = pyqtSignal()
    context_typology_saved = pyqtSignal(str)
    strategy_started = pyqtSignal(str)
    strategy_completed = pyqtSignal(str)
    strategy_failed = pyqtSignal(str, str)
    dataset_created = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.current_hierarchy = {}
        
        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F5F0EF"
        self.text_color = "#333333"
        self.accent_color = "#E38272"
        
        self._init_style()
        self._init_ui()
        self._init_connections()
    
    def _init_style(self):
        """Configure le style global du widget"""
        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {self.secondary_color};
        }}
        QPushButton:disabled {{
            background-color: #CCCCCC;
            color: #666666;
        }}
        QTreeWidget {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            background-color: white;
        }}
        QGroupBox {{
            font-weight: bold;
            border: 2px solid {self.accent_color};
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {self.primary_color};
        }}
        """
        self.setStyleSheet(stylesheet)
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Titre
        title_label = QtWidgets.QLabel("Stratégie des Contextes")
        title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {self.primary_color};
            margin: 10px 0;
        """)
        layout.addWidget(title_label)
        
        # Container principal avec splitter
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        
        # Panel gauche - Diagramme circulaire
        left_panel = QtWidgets.QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        chart_group = QtWidgets.QGroupBox("Répartition des Combinaisons de Contextes")
        chart_layout = QVBoxLayout(chart_group)
        
        # Création du diagramme circulaire
        chart_container = QtWidgets.QWidget()
        chart_layout.addWidget(chart_container)
        chart_container_layout = QVBoxLayout(chart_container)
        chart_container_layout.setContentsMargins(0, 0, 0, 0)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_container_layout.addWidget(self.chart_view)
        
        
        left_layout.addWidget(chart_group)
        splitter.addWidget(left_panel)
        
        # Panel droit - Gestion des typologies
        right_panel = QtWidgets.QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        hierarchy_group = QtWidgets.QGroupBox("Gestion des Typologies de Contexte")
        hierarchy_layout = QVBoxLayout(hierarchy_group)
        
        # Arbre hiérarchique
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Typologie", "Type", "ID"])
        self.tree_widget.setColumnHidden(2, True)  # Cacher la colonne ID
        self.tree_widget.setMinimumWidth(400)
        hierarchy_layout.addWidget(self.tree_widget)
        
        # Boutons d'action pour la hiérarchie
        button_layout = QHBoxLayout()
        
        self.add_cluster_btn = QtWidgets.QPushButton("Nouveau Cluster")
        button_layout.addWidget(self.add_cluster_btn)
        
        self.add_root_btn = QtWidgets.QPushButton("Nouveau Libellé Racine")
        button_layout.addWidget(self.add_root_btn)
        
        self.add_parent_btn = QtWidgets.QPushButton("Nouveau Parent")
        button_layout.addWidget(self.add_parent_btn)
        
        self.add_child_btn = QtWidgets.QPushButton("Nouvel Enfant")
        button_layout.addWidget(self.add_child_btn)
        
        hierarchy_layout.addLayout(button_layout)
        
        # Boutons de modification
        edit_layout = QHBoxLayout()
        
        self.edit_btn = QtWidgets.QPushButton("Modifier")
        edit_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QtWidgets.QPushButton("Supprimer")
        edit_layout.addWidget(self.delete_btn)
        
        self.save_btn = QtWidgets.QPushButton("Sauvegarder")
        edit_layout.addWidget(self.save_btn)
        
        hierarchy_layout.addLayout(edit_layout)
        right_layout.addWidget(hierarchy_group)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Prêt")
        self.status_label.setStyleSheet(f"color: {self.text_color}; font-style: italic;")
        layout.addWidget(self.status_label)
    
    def _init_connections(self):
        """Initialise les connexions signal-slot"""
        self.add_cluster_btn.clicked.connect(self._add_cluster)
        self.add_root_btn.clicked.connect(self._add_root_label)
        self.add_parent_btn.clicked.connect(self._add_parent)
        self.add_child_btn.clicked.connect(self._add_child)
        self.edit_btn.clicked.connect(self._edit_item)
        self.delete_btn.clicked.connect(self._delete_item)
        self.save_btn.clicked.connect(self._save_hierarchy)
        self.tree_widget.itemSelectionChanged.connect(self._update_button_states)
    
    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        self._load_context_hierarchy()
        self._update_chart()
    
    def _load_context_hierarchy(self):
        """Charge la hiérarchie des contextes depuis la base de données"""
        if not self.database:
            return
        
        try:
            cursor = self.database.connection.cursor()
            
            # Charger les clusters
            cursor.execute("SELECT * FROM context_clusters ORDER BY name")
            clusters = cursor.fetchall()
            
            self.tree_widget.clear()
            self.current_hierarchy = {}
            
            for cluster in clusters:
                cluster_item = QTreeWidgetItem(self.tree_widget)
                cluster_item.setText(0, cluster['name'])
                cluster_item.setText(1, "Cluster")
                cluster_item.setText(2, str(cluster['id']))
                cluster_item.setData(0, Qt.UserRole, 'cluster')
                
                # Charger les libellés racines pour ce cluster
                cursor.execute(
                    "SELECT * FROM context_root_labels WHERE cluster_id = ? ORDER BY name",
                    (cluster['id'],)
                )
                root_labels = cursor.fetchall()
                
                for root_label in root_labels:
                    root_item = QTreeWidgetItem(cluster_item)
                    root_item.setText(0, root_label['name'])
                    root_item.setText(1, "Libellé Racine")
                    root_item.setText(2, str(root_label['id']))
                    root_item.setData(0, Qt.UserRole, 'root_label')
                    
                    # Charger les parents pour ce libellé racine
                    self._load_parents_and_children(root_item, root_label['id'])
                
                cluster_item.setExpanded(True)
            
            self._update_button_states()
            self.status_label.setText("Hiérarchie chargée")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la hiérarchie: {str(e)}")
            self.status_label.setText("Erreur de chargement")
    
    def _load_parents_and_children(self, parent_item, root_label_id):
        """Charge les parents et enfants récursivement"""
        if not self.database:
            return
        
        try:
            cursor = self.database.connection.cursor()
            
            # Charger les parents
            cursor.execute(
                """SELECT * FROM context_parents 
                   WHERE root_label_id = ? AND parent_id IS NULL 
                   ORDER BY name""",
                (root_label_id,)
            )
            parents = cursor.fetchall()
            
            for parent in parents:
                parent_item_obj = QTreeWidgetItem(parent_item)
                parent_item_obj.setText(0, parent['name'])
                parent_item_obj.setText(1, "Parent")
                parent_item_obj.setText(2, str(parent['id']))
                parent_item_obj.setData(0, Qt.UserRole, 'parent')
                
                # Charger les enfants récursivement
                self._load_children(parent_item_obj, parent['id'])
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des parents/enfants: {str(e)}")
    
    def _load_children(self, parent_item, parent_id):
        """Charge les enfants récursivement"""
        if not self.database:
            return
        
        try:
            cursor = self.database.connection.cursor()
            
            # Charger les enfants directs
            cursor.execute(
                "SELECT * FROM context_parents WHERE parent_id = ? ORDER BY name",
                (parent_id,)
            )
            children = cursor.fetchall()
            
            for child in children:
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, child['name'])
                child_item.setText(1, "Enfant")
                child_item.setText(2, str(child['id']))
                child_item.setData(0, Qt.UserRole, 'child')
                
                # Charger les sous-enfants récursivement
                self._load_children(child_item, child['id'])
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des enfants: {str(e)}")
    
    def _update_chart(self):
        """Met à jour le diagramme circulaire avec les données actuelles"""
        print("[DEBUG] _update_chart called")
        if not self.database:
            print("[DEBUG] No database set for StrategyWidget")
            return

        if not QT_CHARTS_AVAILABLE:
            print("[DEBUG] QtCharts is not available")
            no_chart_label = QtWidgets.QLabel(
                "QtCharts n'est pas disponible.\n\n"
                "Pour installer QtCharts :\n"
                "Sur Windows : pip install PyQtChart\n"
                "Sur Linux : sudo apt-get install python3-pyqt5.qtchart\n"
                "Sur Mac : brew install pyqt@5 --with-qtchart"
            )
            no_chart_label.setAlignment(Qt.AlignCenter)
            no_chart_label.setStyleSheet("color: red; font-weight: bold;")
            if hasattr(self, 'chart_view'):
                layout = self.chart_view.layout()
                if layout:
                    for i in reversed(range(layout.count())):
                        layout.itemAt(i).widget().setParent(None)
                    layout.addWidget(no_chart_label)
            return

        try:
            print("[DEBUG] Fetching context_usage data for chart...")
            cursor = self.database.connection.cursor()
            cursor.execute("""
                SELECT context_combination, COUNT(*) as count 
                FROM context_usage 
                GROUP BY context_combination 
                ORDER BY count DESC
                LIMIT 10
            """)
            data = cursor.fetchall()
            print(f"[DEBUG] Data fetched for chart: {data}")

            if not data:
                print("[DEBUG] No data available for chart.")
                no_data_label = QtWidgets.QLabel("Aucune donnée de contexte disponible")
                no_data_label.setAlignment(Qt.AlignCenter)
                if hasattr(self, 'chart_view'):
                    layout = self.chart_view.layout()
                    if layout:
                        for i in reversed(range(layout.count())):
                            layout.itemAt(i).widget().setParent(None)
                        layout.addWidget(no_data_label)
                return

            series = QPieSeries()
            series.setHoleSize(0.35)
            for row in data:
                print(f"[DEBUG] Adding slice: {row['context_combination']} ({row['count']})")
                slice = QPieSlice(f"{row['context_combination']} ({row['count']})", row['count'])
                series.append(slice)

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("Répartition des Combinaisons de Contextes")
            chart.setAnimationOptions(QChart.SeriesAnimations)
            chart.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(self.background_color)))
            chart.setTitleBrush(QtGui.QBrush(QtGui.QColor(self.primary_color)))
            self.chart_view.setChart(chart)
            print("[DEBUG] Chart set on chart_view")

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du diagramme: {str(e)}")
            print(f"[DEBUG] Exception in _update_chart: {str(e)}")
            error_label = QtWidgets.QLabel(f"Erreur lors du chargement du diagramme:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red;")
            if hasattr(self, 'chart_view'):
                layout = self.chart_view.layout()
                if layout:
                    for i in reversed(range(layout.count())):
                        layout.itemAt(i).widget().setParent(None)
                    layout.addWidget(error_label)

    def _check_database_tables(self):
        """Vérifie que les tables nécessaires existent"""
        if not self.database:
            return False
        
        try:
            cursor = self.database.connection.cursor()
            
            # Vérifier l'existence des tables
            tables_to_check = [
                'context_clusters', 
                'context_root_labels', 
                'context_parents',
                'context_usage'
            ]
            
            for table in tables_to_check:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    logger.warning(f"Table {table} n'existe pas")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des tables: {str(e)}")
            return False       

    def set_database(self, database):
        """Définit la base de données"""
        self.database = database
        
        if self._check_database_tables():
            self._load_context_hierarchy()
            self._update_chart()
        else:
            self.status_label.setText("Tables de contexte manquantes dans la base de données")
            logger.warning("Tables de contexte manquantes")             
    
    def _add_cluster(self):
        """Ajoute un nouveau cluster"""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Cluster", "Nom du cluster:"
        )
        
        if ok and name:
            cluster_item = QTreeWidgetItem(self.tree_widget)
            cluster_item.setText(0, name)
            cluster_item.setText(1, "Cluster")
            cluster_item.setText(2, "new")
            cluster_item.setData(0, Qt.UserRole, 'cluster')
            cluster_item.setExpanded(True)
            
            self.status_label.setText(f"Cluster '{name}' ajouté (non sauvegardé)")
    
    def _add_root_label(self):
        """Ajoute un nouveau libellé racine"""
        selected_item = self.tree_widget.currentItem()
        
        if not selected_item or selected_item.data(0, Qt.UserRole) != 'cluster':
            QtWidgets.QMessageBox.warning(
                self, "Erreur", "Veuillez sélectionner un cluster pour ajouter un libellé racine"
            )
            return
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Libellé Racine", "Nom du libellé racine:"
        )
        
        if ok and name:
            root_item = QTreeWidgetItem(selected_item)
            root_item.setText(0, name)
            root_item.setText(1, "Libellé Racine")
            root_item.setText(2, "new")
            root_item.setData(0, Qt.UserRole, 'root_label')
            
            self.status_label.setText(f"Libellé racine '{name}' ajouté (non sauvegardé)")
    
    def _add_parent(self):
        """Ajoute un nouveau parent"""
        selected_item = self.tree_widget.currentItem()
        valid_types = ['cluster', 'root_label', 'parent']
        
        if not selected_item or selected_item.data(0, Qt.UserRole) not in valid_types:
            QtWidgets.QMessageBox.warning(
                self, "Erreur", 
                "Veuillez sélectionner un cluster, libellé racine ou parent pour ajouter un parent"
            )
            return
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau Parent", "Nom du parent:"
        )
        
        if ok and name:
            parent_item = QTreeWidgetItem(selected_item)
            parent_item.setText(0, name)
            parent_item.setText(1, "Parent")
            parent_item.setText(2, "new")
            parent_item.setData(0, Qt.UserRole, 'parent')
            
            self.status_label.setText(f"Parent '{name}' ajouté (non sauvegardé)")
    
    def _add_child(self):
        """Ajoute un nouvel enfant"""
        selected_item = self.tree_widget.currentItem()
        
        if not selected_item or selected_item.data(0, Qt.UserRole) not in ['parent', 'child']:
            QtWidgets.QMessageBox.warning(
                self, "Erreur", 
                "Veuillez sélectionner un parent ou un enfant pour ajouter un enfant"
            )
            return
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouvel Enfant", "Nom de l'enfant:"
        )
        
        if ok and name:
            child_item = QTreeWidgetItem(selected_item)
            child_item.setText(0, name)
            child_item.setText(1, "Enfant")
            child_item.setText(2, "new")
            child_item.setData(0, Qt.UserRole, 'child')
            
            self.status_label.setText(f"Enfant '{name}' ajouté (non sauvegardé)")
    
    def _edit_item(self):
        """Modifie l'élément sélectionné"""
        selected_item = self.tree_widget.currentItem()
        
        if not selected_item:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un élément à modifier")
            return
        
        current_name = selected_item.text(0)
        item_type = selected_item.data(0, Qt.UserRole)
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Modifier {item_type}", f"Nouveau nom:", text=current_name
        )
        
        if ok and name and name != current_name:
            selected_item.setText(0, name)
            self.status_label.setText(f"{item_type.capitalize()} modifié (non sauvegardé)")
    
    def _delete_item(self):
        """Supprime l'élément sélectionné"""
        selected_item = self.tree_widget.currentItem()
        
        if not selected_item:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un élément à supprimer")
            return
        
        item_type = selected_item.data(0, Qt.UserRole)
        item_name = selected_item.text(0)
        
        reply = QtWidgets.QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer le {item_type} '{item_name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            parent = selected_item.parent()
            if parent:
                parent.removeChild(selected_item)
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(selected_item))
            
            self.status_label.setText(f"{item_type.capitalize()} '{item_name}' supprimé (non sauvegardé)")
    
    def _save_hierarchy(self):
        """Sauvegarde la hiérarchie complète dans la base de données"""
        if not self.database:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Base de données non disponible")
            return
        
        try:
            cursor = self.database.connection.cursor()
            
            # Parcourir tous les clusters
            for i in range(self.tree_widget.topLevelItemCount()):
                cluster_item = self.tree_widget.topLevelItem(i)
                self._save_cluster(cluster_item, cursor)
            
            self.database.connection.commit()
            self.status_label.setText("Hiérarchie sauvegardée avec succès")
            self.context_hierarchy_changed.emit()
            self._update_chart()
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la hiérarchie: {str(e)}")
            self.database.connection.rollback()
            QtWidgets.QMessageBox.critical(
                self, "Erreur", 
                f"Erreur lors de la sauvegarde:\n\n{str(e)}"
            )
    
    def _save_cluster(self, cluster_item, cursor):
        """Sauvegarde un cluster et ses enfants"""
        cluster_id = cluster_item.text(2)
        cluster_name = cluster_item.text(0)
        
        if cluster_id == "new":
            cursor.execute(
                "INSERT INTO context_clusters (name, created_at) VALUES (?, ?)",
                (cluster_name, datetime.now().isoformat())
            )
            cluster_id = cursor.lastrowid
            cluster_item.setText(2, str(cluster_id))
        else:
            cursor.execute(
                "UPDATE context_clusters SET name = ?, updated_at = ? WHERE id = ?",
                (cluster_name, datetime.now().isoformat(), cluster_id)
            )
        
        # Sauvegarder les libellés racines
        for i in range(cluster_item.childCount()):
            root_item = cluster_item.child(i)
            self._save_root_label(root_item, cluster_id, cursor)
    
    def _save_root_label(self, root_item, cluster_id, cursor):
        """Sauvegarde un libellé racine et ses enfants"""
        root_id = root_item.text(2)
        root_name = root_item.text(0)
        
        if root_id == "new":
            cursor.execute(
                "INSERT INTO context_root_labels (cluster_id, name, created_at) VALUES (?, ?, ?)",
                (cluster_id, root_name, datetime.now().isoformat())
            )
            root_id = cursor.lastrowid
            root_item.setText(2, str(root_id))
        else:
            cursor.execute(
                "UPDATE context_root_labels SET name = ?, updated_at = ? WHERE id = ?",
                (root_name, datetime.now().isoformat(), root_id)
            )
        
        # Sauvegarder les parents
        for i in range(root_item.childCount()):
            parent_item = root_item.child(i)
            self._save_parent(parent_item, root_id, None, cursor)
    
    def _save_parent(self, parent_item, root_label_id, parent_id, cursor):
        """Sauvegarde un parent et ses enfants"""
        item_id = parent_item.text(2)
        item_name = parent_item.text(0)
        item_type = parent_item.data(0, Qt.UserRole)
        
        if item_id == "new":
            cursor.execute(
                """INSERT INTO context_parents 
                   (root_label_id, parent_id, name, type, created_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (root_label_id, parent_id, item_name, item_type, datetime.now().isoformat())
            )
            item_id = cursor.lastrowid
            parent_item.setText(2, str(item_id))
        else:
            cursor.execute(
                "UPDATE context_parents SET name = ?, updated_at = ? WHERE id = ?",
                (item_name, datetime.now().isoformat(), item_id)
            )
        
        # Sauvegarder les enfants récursivement
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            self._save_parent(child_item, root_label_id, item_id, cursor)
    
    def _update_button_states(self):
        """Met à jour l'état des boutons en fonction de la sélection"""
        selected_item = self.tree_widget.currentItem()
        
        if selected_item:
            item_type = selected_item.data(0, Qt.UserRole)
            
            # Activer/désactiver les boutons en fonction du type d'élément sélectionné
            self.add_root_btn.setEnabled(item_type == 'cluster')
            self.add_parent_btn.setEnabled(item_type in ['cluster', 'root_label', 'parent'])
            self.add_child_btn.setEnabled(item_type in ['parent', 'child'])
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            # Aucun élément sélectionné
            self.add_root_btn.setEnabled(False)
            self.add_parent_btn.setEnabled(False)
            self.add_child_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def refresh(self):
        """Actualise les données"""
        if self.database:
            self._load_context_hierarchy()
            self._update_chart()
    
    def update_language(self):
        """Met à jour les textes selon la langue sélectionnée"""
        # À implémenter selon votre système de traduction
        pass