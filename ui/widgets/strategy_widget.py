import numpy as np
import matplotlib.pyplot as plt
import json
from datetime import datetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, 
                             QTextEdit, QGroupBox, QSplitter, QMessageBox, QInputDialog, QFileDialog,
                             QDialog, QDialogButtonBox, QCheckBox, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from PyQt5.QtWidgets import QTabWidget

class TypologyDialog(QDialog):
    """Dialogue pour la gestion des typologies"""
    def __init__(self, parent=None, name="", description="", is_hierarchical=False):
        super().__init__(parent)
        self.setWindowTitle("Gestion des Typologies")
        self.setModal(True)
        self.setup_ui(name, description, is_hierarchical)
        
    def setup_ui(self, name, description, is_hierarchical):
        layout = QVBoxLayout(self)
        
        # Nom
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.name_edit = QLineEdit(name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.desc_edit = QTextEdit(description)
        self.desc_edit.setMaximumHeight(100)
        desc_layout.addWidget(self.desc_edit)
        layout.addLayout(desc_layout)
        
        # Hiérarchique
        self.hierarchical_cb = QCheckBox("Structure hiérarchique (taxonomique)")
        self.hierarchical_cb.setChecked(is_hierarchical)
        layout.addWidget(self.hierarchical_cb)
        
        # Boutons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.desc_edit.toPlainText().strip(),
            self.hierarchical_cb.isChecked()
        )

class CombinationChartWidget(QWidget):
    """Widget pour le diagramme de représentativité des combinaisons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.init_ui()
        
    def set_database(self, database):
        """Définit l'objet Database"""
        self.database = database
        self.update_combination_chart()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Contrôles
        controls_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Actualiser")
        self.refresh_btn.clicked.connect(self.update_combination_chart)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        controls_layout.addWidget(self.refresh_btn)
        
        controls_layout.addStretch()
        
        self.auto_refresh_cb = QCheckBox("Actualisation automatique")
        self.auto_refresh_cb.setChecked(True)
        controls_layout.addWidget(self.auto_refresh_cb)
        
        layout.addLayout(controls_layout)
        
        # Figure matplotlib
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Légende interactive
        self.legend_label = QLabel("💡 Cliquez sur une légende pour filtrer (fonctionnalité à venir)")
        self.legend_label.setStyleSheet("font-style: italic; color: #666; padding: 5px;")
        layout.addWidget(self.legend_label)
        
        # Message si aucune donnée
        self.no_data_label = QLabel("📊 Aucune donnée disponible - Effectuez des générations dans l'onglet 'Génération' d'abord")
        self.no_data_label.setStyleSheet("color: #999; font-size: 12px; background-color: #f5f5f5; padding: 20px;")
        self.no_data_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.no_data_label)
        self.no_data_label.hide()
        
    def calculate_combinations_metrics(self):
        """Calcule les métriques des combinaisons depuis l'historique"""
        if not self.database:
            return None
            
        try:
            # Récupérer l'historique des générations
            history = self.database.get_generation_history()
            
            if not history:
                return None
                
            # Compter les occurrences de chaque combinaison
            combination_counts = {}
            total_generations = 0
            
            for generation in history:
                # Extraire la combinaison de contextes
                context_combination = self.extract_combination_from_generation(generation)
                if context_combination:
                    combination_key = str(sorted(context_combination))
                    combination_counts[combination_key] = combination_counts.get(combination_key, 0) + 1
                    total_generations += 1
            
            # Calculer les pourcentages
            combinations_data = []
            for combination_key, count in combination_counts.items():
                percentage = (count / total_generations) * 100 if total_generations > 0 else 0
                combinations_data.append({
                    'combination': eval(combination_key),
                    'count': count,
                    'percentage': percentage,
                    'label': self.format_combination_label(eval(combination_key))
                })
            
            # Trier par pourcentage décroissant
            combinations_data.sort(key=lambda x: x['percentage'], reverse=True)
            
            return {
                'combinations': combinations_data,
                'total_generations': total_generations,
                'unique_combinations': len(combinations_data)
            }
            
        except Exception as e:
            print(f"Erreur calcul métriques: {str(e)}")
            return None
    
    def extract_combination_from_generation(self, generation):
        """Extrait la combinaison de contextes d'une génération"""
        # À adapter selon votre structure de données
        if 'context_combination' in generation:
            return generation['context_combination']
        elif 'contexts' in generation:
            return generation['contexts']
        elif 'combination' in generation:
            return generation['combination']
        else:
            return []
    
    def format_combination_label(self, combination):
        """Formate l'étiquette pour une combinaison"""
        if not combination:
            return "Aucun contexte"
        return " + ".join(str(ctx) for ctx in combination)
    
    def update_combination_chart(self):
        """Met à jour le diagramme avec les données actuelles"""
        metrics = self.calculate_combinations_metrics()
        
        # Masquer/afficher le message "aucune donnée"
        if not metrics or not metrics['combinations']:
            self.no_data_label.show()
            self.canvas.hide()
            self.legend_label.hide()
            return
        else:
            self.no_data_label.hide()
            self.canvas.show()
            self.legend_label.show()
        
        # Préparer les données pour le graphique
        labels = [item['label'] for item in metrics['combinations']]
        percentages = [item['percentage'] for item in metrics['combinations']]
        counts = [item['count'] for item in metrics['combinations']]
        
        # Créer le diagramme
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Couleurs pour le diagramme
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        
        # Diagramme en barres
        bars = ax.bar(labels, percentages, color=colors, alpha=0.7)
        
        # Ajouter les valeurs sur les barres
        for i, (bar, percentage, count) in enumerate(zip(bars, percentages, counts)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{percentage:.1f}% ({count})', ha='center', va='bottom', fontsize=9)
        
        # Configuration de l'axe
        ax.set_ylabel('Pourcentage d\'utilisation (%)')
        ax.set_title(f'Répartition des Combinaisons de Contextes\n'
                    f'Total: {metrics["total_generations"]} générations | '
                    f'Combinaisons uniques: {metrics["unique_combinations"]}')
        
        # Rotation des labels
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Ajuster les marges
        self.figure.tight_layout()
        
        # Légende
        legend_elements = [Patch(color=colors[i], label=labels[i]) 
                          for i in range(len(labels))]
        ax.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Actualiser le canvas
        self.canvas.draw()
    
    def on_new_generation(self):
        """Appelé quand une nouvelle génération est effectuée"""
        if self.auto_refresh_cb.isChecked():
            self.update_combination_chart()

class StrategyAnalysisTab(QWidget):
    """
    Deuxième onglet : Diagramme de représentativité des combinaisons
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.init_ui()
        
    def set_database(self, database):
        """Définit l'objet Database"""
        self.database = database
        self.combination_chart.set_database(database)
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Analyse de Représentativité des Combinaisons de Contextes")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Diagramme montrant la répartition des combinaisons de contextes utilisées dans l'historique des générations")
        desc_label.setStyleSheet("color: #666; margin: 5px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Widget du diagramme
        self.combination_chart = CombinationChartWidget()
        layout.addWidget(self.combination_chart)
        
    def on_generation_performed(self):
        """Notifie qu'une nouvelle génération a été effectuée"""
        self.combination_chart.on_new_generation()

class TypologyManagementTab(QWidget):
    """
    Premier onglet : Gestion des typologies
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Gestion des Stratégies et Typologies de Contexte")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Barre de gestion des typologies
        typology_layout = QHBoxLayout()
        typology_layout.addWidget(QLabel("Typologie:"))
        
        self.typology_combo = QComboBox()
        self.typology_combo.setMinimumWidth(200)
        typology_layout.addWidget(self.typology_combo)
        
        self.add_typology_btn = QPushButton("Nouvelle")
        self.edit_typology_btn = QPushButton("Modifier")
        self.delete_typology_btn = QPushButton("Supprimer")
        
        typology_layout.addWidget(self.add_typology_btn)
        typology_layout.addWidget(self.edit_typology_btn)
        typology_layout.addWidget(self.delete_typology_btn)
        typology_layout.addStretch()
        
        layout.addLayout(typology_layout)
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Partie gauche - Arbre des typologies
        left_widget = self._create_tree_section()
        main_splitter.addWidget(left_widget)
        
        # Partie droite - Détails et édition
        right_widget = self._create_details_section()
        main_splitter.addWidget(right_widget)
        
        # Définir les proportions
        main_splitter.setSizes([400, 600])
        
        # Barre de boutons en bas
        button_layout = self._create_button_bar()
        layout.addLayout(button_layout)
     
    def set_database(self, database):
        """Définit l'objet Database et initialise"""
        print(f"TypologyManagementTab: Database set to {database}")  # Debug
        self.database = database
        if database:
            self.load_typologies()
        else:
            print("Warning: Database is None in TypologyManagementTab")
            
    def add_typology(self):
        """Ajoute une nouvelle typologie"""
        # VÉRIFICATION CRITIQUE ICI
        if not self.database:
            QMessageBox.critical(self, "Erreur", "Base de données non initialisée")
            print("Error: Database is None in add_typology")
            return
            
        dialog = TypologyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, description, is_hierarchical = dialog.get_data()
            if not name:
                QMessageBox.warning(self, "Erreur", "Le nom de la typologie est obligatoire")
                return
                
            try:
                # Ajouter un log pour debug
                print(f"Attempting to add typology: {name}")
                self.database.add_typology(name, description, is_hierarchical)
                self.load_typologies()
                QMessageBox.information(self, "Succès", f"Typologie '{name}' créée avec succès")
                
            except ValueError as e:
                QMessageBox.warning(self, "Erreur", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")
                print(f"Detailed error: {e}")

        
    def _create_tree_section(self):
        """Crée la section avec l'arbre des typologies"""
        widget = QGroupBox("Structure Hiérarchique")
        layout = QVBoxLayout(widget)
        
        # Boutons de gestion de l'arbre
        tree_buttons = QHBoxLayout()
        
        self.add_cluster_btn = QPushButton("Cluster")
        self.add_cluster_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_root_btn = QPushButton("Racine")
        self.add_root_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_parent_btn = QPushButton("Parent")
        self.add_parent_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.add_child_btn = QPushButton("Enfant")
        self.add_child_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        self.delete_item_btn = QPushButton("Supprimer")
        self.delete_item_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        
        tree_buttons.addWidget(self.add_cluster_btn)
        tree_buttons.addWidget(self.add_root_btn)
        tree_buttons.addWidget(self.add_parent_btn)
        tree_buttons.addWidget(self.add_child_btn)
        tree_buttons.addWidget(self.delete_item_btn)
        
        layout.addLayout(tree_buttons)
        
        # Arbre des typologies
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Nom", "Type", "ID"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setColumnWidth(1, 100)
        layout.addWidget(self.tree_widget)
        
        return widget
        
    def _create_details_section(self):
        """Crée la section des détails et de l'édition"""
        widget = QGroupBox("Détails et Édition")
        layout = QVBoxLayout(widget)
        
        # Informations de base
        info_layout = QVBoxLayout()
        
        # Nom
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        info_layout.addLayout(name_layout)
        
        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_label = QLabel("Aucun élément sélectionné")
        type_layout.addWidget(self.type_label)
        info_layout.addLayout(type_layout)
        
        # Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        desc_layout.addWidget(self.description_edit)
        info_layout.addLayout(desc_layout)
        
        layout.addLayout(info_layout)
        
        # Propriétés spécifiques
        properties_group = QGroupBox("Propriétés Spécifiques")
        properties_layout = QVBoxLayout(properties_group)
        
        self.properties_edit = QTextEdit()
        self.properties_edit.setPlaceholderText("Propriétés JSON spécifiques à ce type d'élément...")
        properties_layout.addWidget(self.properties_edit)
        
        layout.addWidget(properties_group)
        
        # Boutons de sauvegarde
        save_layout = QHBoxLayout()
        self.save_item_btn = QPushButton("Sauvegarder l'élément")
        self.reset_item_btn = QPushButton("Réinitialiser")
        save_layout.addWidget(self.save_item_btn)
        save_layout.addWidget(self.reset_item_btn)
        layout.addLayout(save_layout)
        
        return widget
        
    def _create_button_bar(self):
        """Crée la barre de boutons en bas"""
        layout = QHBoxLayout()
        
        self.load_strategy_btn = QPushButton("Charger Stratégie")
        self.load_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.save_strategy_btn = QPushButton("Sauvegarder Stratégie")
        self.save_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.export_strategy_btn = QPushButton("Exporter")
        self.export_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        self.import_strategy_btn = QPushButton("Importer")
        self.import_strategy_btn.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        layout.addWidget(self.load_strategy_btn)
        layout.addWidget(self.save_strategy_btn)
        layout.addWidget(self.export_strategy_btn)
        layout.addWidget(self.import_strategy_btn)
        layout.addStretch()
        
        return layout
        
    def setup_connections(self):
        """Configure les connexions des signaux"""
        # Connexions des boutons de l'arbre
        self.add_cluster_btn.clicked.connect(self.add_cluster)
        self.add_root_btn.clicked.connect(self.add_root_label)
        self.add_parent_btn.clicked.connect(self.add_parent)
        self.add_child_btn.clicked.connect(self.add_child)
        self.delete_item_btn.clicked.connect(self.delete_item)
        
        # Connexions de l'édition
        self.save_item_btn.clicked.connect(self.save_current_item)
        self.reset_item_btn.clicked.connect(self.reset_current_item)
        
        # Connexions de la stratégie
        self.load_strategy_btn.clicked.connect(self.load_strategy)
        self.save_strategy_btn.clicked.connect(self.save_strategy)
        self.export_strategy_btn.clicked.connect(self.export_strategy)
        self.import_strategy_btn.clicked.connect(self.import_strategy)
        
        # Connexions des typologies
        self.add_typology_btn.clicked.connect(self.add_typology)
        self.edit_typology_btn.clicked.connect(self.edit_typology)
        self.delete_typology_btn.clicked.connect(self.delete_typology)
        self.typology_combo.currentIndexChanged.connect(self.on_typology_changed)
        
        # Sélection dans l'arbre
        self.tree_widget.itemSelectionChanged.connect(self.on_item_selected)
        
    def load_typologies(self):
        """Charge la liste des typologies depuis la base de données"""
        if not self.database:
            return
            
        self.typology_combo.clear()
        
        try:
            # Use the database object correctly
            typologies = self.database.get_typologies()
            
            self.typology_combo.addItem("-- Sélectionnez une typologie --", None)
            
            for typology in typologies:
                # Handle both tuple and sqlite3.Row objects
                if isinstance(typology, (tuple, list)) and len(typology) >= 3:
                    name = typology[1]
                    is_hierarchical = bool(typology[2])
                    typology_id = typology[0]
                elif hasattr(typology, '__getitem__'):
                    # For sqlite3.Row objects, access by index or column name
                    try:
                        # Try to access by column name first
                        name = typology['name']
                        is_hierarchical = bool(typology['is_hierarchical'])
                        typology_id = typology['id']
                    except (KeyError, IndexError):
                        # Fall back to index access
                        name = typology[0] if len(typology) > 0 else 'Unknown'
                        is_hierarchical = bool(typology[1]) if len(typology) > 1 else False
                        typology_id = typology[0] if len(typology) > 0 else None
                else:
                    continue
                    
                display_text = f"{name} {'(Hiérarchique)' if is_hierarchical else ''}"
                self.typology_combo.addItem(display_text, typology_id)
                
        except Exception as e:
            print(f"Erreur lors du chargement des typologies: {str(e)}")
            self.typology_combo.addItem("-- Erreur de chargement --", None)

            
    def on_typology_changed(self):
        """Gère le changement de typologie sélectionnée"""
        current_typology_id = self.typology_combo.currentData()
        if current_typology_id:
            self.load_strategy()
            
    def add_typology(self):
        """Ajoute une nouvelle typologie"""
        dialog = TypologyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, description, is_hierarchical = dialog.get_data()
            if not name:
                QMessageBox.warning(self, "Erreur", "Le nom de la typologie est obligatoire")
                return
                
            try:
                self.database.add_typology(name, description, is_hierarchical)
                self.load_typologies()
                QMessageBox.information(self, "Succès", f"Typologie '{name}' créée avec succès")
                
            except ValueError as e:
                QMessageBox.warning(self, "Erreur", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")      
                
    def edit_typology(self):
        """Modifie une typologie existante"""
        current_id = self.typology_combo.currentData()
        if not current_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée")
            return

        try:
            result = self.database.get_typology_details(current_id)

            if result:
                # Gestion de plusieurs formats de retour
                if isinstance(result, (tuple, list)) and len(result) >= 3:
                    name = result[0]
                    description = result[1]
                    is_hierarchical = bool(result[2])
                elif hasattr(result, '__getitem__'):
                    # For sqlite3.Row objects
                    try:
                        name = result['name']
                        description = result['description']
                        is_hierarchical = bool(result['is_hierarchical'])
                    except (KeyError, IndexError):
                        # Fall back to index access
                        name = result[0] if len(result) > 0 else ''
                        description = result[1] if len(result) > 1 else ''
                        is_hierarchical = bool(result[2]) if len(result) > 2 else False
                else:
                    name = ''
                    description = ''
                    is_hierarchical = False

                dialog = TypologyDialog(self, name, description, is_hierarchical)
                if dialog.exec_() == QDialog.Accepted:
                    name, description, is_hierarchical = dialog.get_data()
                    if not name:
                        QMessageBox.warning(self, "Erreur", "Le nom de la typologie est obligatoire")
                        return

                    self.database.update_typology(current_id, name, description, is_hierarchical)
                    self.load_typologies()
                    QMessageBox.information(self, "Succès", f"Typologie '{name}' modifiée avec succès")

        except ValueError as e:
            QMessageBox.warning(self, "Erreur", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")
            
    def delete_typology(self):
        """Supprime une typologie"""
        current_id = self.typology_combo.currentData()
        if not current_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée")
            return
            
        try:
            typology_name = self.typology_combo.currentText()
            reply = QMessageBox.question(
                self, "Confirmation", 
                f"Êtes-vous sûr de vouloir supprimer la typologie '{typology_name}' ?"
            )
            
            if reply == QMessageBox.Yes:
                self.database.delete_typology(current_id)
                self.load_typologies()
                QMessageBox.information(self, "Succès", "Typologie supprimée avec succès")
                
        except ValueError as e:
            QMessageBox.warning(self, "Erreur", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")   
            
    def add_cluster(self):
        """Ajoute un nouveau cluster"""
        name, ok = QInputDialog.getText(self, 'Nouveau Cluster', 'Nom du cluster:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), None):
                QMessageBox.warning(self, "Erreur", f"Un cluster nommé '{name.strip()}' existe déjà")
                return
                
            item = QTreeWidgetItem(self.tree_widget)
            item.setText(0, name.strip())
            item.setText(1, "Cluster")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "cluster", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Cluster '{name.strip()}' créé avec succès")
            
    def add_root_label(self):
        """Ajoute un libellé racine"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Cluster":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un cluster")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Libellé Racine', 'Nom du libellé:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un libellé racine nommé '{name.strip()}' existe déjà dans ce cluster")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Racine")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "root", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Libellé racine '{name.strip()}' créé avec succès")
            
    def add_parent(self):
        """Ajoute un élément parent"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) not in ["Racine", "Parent"]:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une racine ou un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouveau Parent', 'Nom du parent:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un parent nommé '{name.strip()}' existe déjà sous cet élément")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Parent")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "parent", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Parent '{name.strip()}' créé avec succès")
            
    def add_child(self):
        """Ajoute un élément enfant"""
        current = self.tree_widget.currentItem()
        if not current or current.text(1) != "Parent":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un parent")
            return
            
        name, ok = QInputDialog.getText(self, 'Nouvel Enfant', 'Nom de l\'enfant:')
        if ok and name.strip():
            if self._name_exists_at_level(name.strip(), current):
                QMessageBox.warning(self, "Erreur", f"Un enfant nommé '{name.strip()}' existe déjà sous ce parent")
                return
                
            item = QTreeWidgetItem(current)
            item.setText(0, name.strip())
            item.setText(1, "Enfant")
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": "child", 
                "name": name.strip(),
                "description": "",
                "properties": {}
            })
            current.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
            QMessageBox.information(self, "Succès", f"Enfant '{name.strip()}' créé avec succès")
            
    def delete_item(self):
        """Supprime l'élément sélectionné"""
        current = self.tree_widget.currentItem()
        if not current:
            return
            
        child_count = current.childCount()
        if child_count > 0:
            reply = QMessageBox.question(
                self, 'Confirmer la suppression', 
                f'L\'élément "{current.text(0)}" contient {child_count} enfant(s). ' 
                f'Voulez-vous vraiment le supprimer avec tous ses enfants ?'
            )
        else:
            reply = QMessageBox.question(
                self, 'Confirmer la suppression', 
                f'Êtes-vous sûr de vouloir supprimer "{current.text(0)}" ?'
            )
            
        if reply == QMessageBox.Yes:
            parent = current.parent()
            if parent:
                parent.removeChild(current)
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(current))
            QMessageBox.information(self, "Succès", "Élément supprimé avec succès")
                
    def on_item_selected(self):
        """Gère la sélection d'un élément dans l'arbre"""
        current = self.tree_widget.currentItem()
        if not current:
            self._clear_details()
            return
            
        data = current.data(0, Qt.UserRole)
        if data:
            self.name_edit.setText(data.get("name", ""))
            self.type_label.setText(data.get("type", ""))
            self.description_edit.setText(data.get("description", ""))
            self.properties_edit.setText(json.dumps(data.get("properties", {}), indent=2))
            
    def _clear_details(self):
        """Vide les champs de détails"""
        self.name_edit.clear()
        self.type_label.setText("Aucun élément sélectionné")
        self.description_edit.clear()
        self.properties_edit.clear()
        
    def save_current_item(self):
        """Sauvegarde l'élément actuellement sélectionné"""
        current = self.tree_widget.currentItem()
        if not current:
            return
            
        data = current.data(0, Qt.UserRole) or {}
        new_name = self.name_edit.text().strip()
        
        if new_name != data.get("name", "") and new_name:
            parent = current.parent()
            if self._name_exists_at_level(new_name, parent, exclude_item=current):
                QMessageBox.warning(self, "Erreur", f"Le nom '{new_name}' existe déjà à ce niveau")
                return
        
        data["name"] = new_name
        data["description"] = self.description_edit.toPlainText()
        
        try:
            properties_text = self.properties_edit.toPlainText()
            if properties_text.strip():
                data["properties"] = json.loads(properties_text)
            else:
                data["properties"] = {}
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Erreur", "Format JSON invalide dans les propriétés")
            return
            
        current.setData(0, Qt.UserRole, data)
        current.setText(0, data["name"])
        
        QMessageBox.information(self, "Succès", "Élément sauvegardé avec succès")
        
    def reset_current_item(self):
        """Réinitialise les champs de l'élément actuel"""
        self.on_item_selected()
        
    def save_strategy(self):
        """Sauvegarde la stratégie complète dans la base de données"""
        if not self.database:
            QMessageBox.warning(self, "Erreur", "Aucune base de données configurée")
            return
        
        current_typology_id = self.typology_combo.currentData()
        if not current_typology_id:
            QMessageBox.warning(self, "Erreur", "Aucune typologie sélectionnée pour la sauvegarde")
            return

        try:
            self.database.clear_strategy_items(current_typology_id)
            self._save_tree_items(None, self.tree_widget.invisibleRootItem(), current_typology_id)
            
            QMessageBox.information(self, "Succès", "Stratégie sauvegardée avec succès")
            self.strategy_saved.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
            
    def _save_tree_items(self, parent_id, parent_item, typology_id):
        """Sauvegarde récursivement les éléments de l'arbre"""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            data = item.data(0, Qt.UserRole) or {}
            
            item_id = self.database.add_strategy_item(
                data.get("name", ""),
                data.get("type", ""),
                parent_id,
                data.get("description", ""),
                json.dumps(data.get("properties", {})),
                typology_id
            )
            
            item.setText(2, str(item_id))
            
            self._save_tree_items(item_id, item, typology_id)
            
    def load_strategy(self):
        """Charge une stratégie depuis la base de données"""
        if not self.database:
            QMessageBox.warning(self, "Erreur", "Aucune base de données configurée")
            return
            
        current_typology_id = self.typology_combo.currentData()
        if not current_typology_id:
            self.tree_widget.clear()
            return

        try:
            self.tree_widget.clear()
            items = self.database.get_strategy_items(current_typology_id)
            
            if not items:
                return
                
            item_map = {}
            root_items = []
            
            for item_data in items:
                # Handle sqlite3.Row objects
                try:
                    item_id = item_data['id']
                    parent_id = item_data['parent_id']
                    name = item_data['name']
                    item_type = item_data['type']
                    description = item_data['description']
                    properties = item_data['properties']
                except (KeyError, TypeError):
                    # Fall back to index access if it's a tuple
                    if isinstance(item_data, (tuple, list)) and len(item_data) >= 6:
                        item_id = item_data[0]
                        name = item_data[1]
                        item_type = item_data[2]
                        parent_id = item_data[3]
                        description = item_data[4]
                        properties = item_data[5]
                    else:
                        continue
                
                item = QTreeWidgetItem()
                item.setText(0, name)
                item.setText(1, item_type)
                item.setText(2, str(item_id))
                item.setData(0, Qt.UserRole, {
                    "type": item_type,
                    "name": name,
                    "description": description,
                    "properties": json.loads(properties) if properties else {}
                })
                
                item_map[item_id] = item
                
                if parent_id is None:
                    root_items.append(item)
                else:
                    parent_item = item_map.get(parent_id)
                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        root_items.append(item)
            
            self.tree_widget.addTopLevelItems(root_items)
            self.tree_widget.expandAll()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement: {str(e)}")
                
    def export_strategy(self):
        """Exporte la stratégie vers un fichier JSON"""
        if self.tree_widget.topLevelItemCount() == 0:
            QMessageBox.warning(self, "Erreur", "Aucune stratégie à exporter")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter la stratégie", "", "JSON Files (*.json)"
        )
        
        if filename:
            try:
                strategy_data = self._export_tree_to_json(self.tree_widget.invisibleRootItem())
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(strategy_data, f, indent=2, ensure_ascii=False)
                    
                QMessageBox.information(self, "Succès", "Stratégie exportée avec succès")
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")
                
    def _export_tree_to_json(self, root_item):
        """Exporte récursivement l'arbre en JSON"""
        items = []
        
        for i in range(root_item.childCount()):
            item = root_item.child(i)
            data = item.data(0, Qt.UserRole) or {}
            
            item_data = {
                "name": data.get("name", ""),
                "type": data.get("type", ""),
                "description": data.get("description", ""),
                "properties": data.get("properties", {}),
                "children": self._export_tree_to_json(item)
            }
            
            items.append(item_data)
            
        return items
        
    def import_strategy(self):
        """Importe une stratégie depuis un fichier JSON"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importer une stratégie", "", "JSON Files (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)
                    
                self.tree_widget.clear()
                self._import_tree_from_json(strategy_data, self.tree_widget.invisibleRootItem())
                self.tree_widget.expandAll()
                
                QMessageBox.information(self, "Succès", "Stratégie importée avec succès")
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'import: {str(e)}")
                
    def _import_tree_from_json(self, items_data, parent_item):
        """Importe récursivement l'arbre depuis JSON"""
        for item_data in items_data:
            item = QTreeWidgetItem(parent_item)
            item.setText(0, item_data.get("name", ""))
            item.setText(1, item_data.get("type", ""))
            item.setText(2, str(self._get_next_id()))
            item.setData(0, Qt.UserRole, {
                "type": item_data.get("type", ""),
                "name": item_data.get("name", ""),
                "description": item_data.get("description", ""),
                "properties": item_data.get("properties", {})
            })
            
            children = item_data.get("children", [])
            if children:
                self._import_tree_from_json(children, item)
                
    def _name_exists_at_level(self, name, parent_item, exclude_item=None):
        """Vérifie si un nom existe déjà au même niveau"""
        if parent_item is None:
            items = [self.tree_widget.topLevelItem(i) for i in range(self.tree_widget.topLevelItemCount())]
        else:
            items = [parent_item.child(i) for i in range(parent_item.childCount())]
            
        for item in items:
            if item == exclude_item:
                continue
            if item.text(0) == name:
                return True
        return False
        
    def _get_next_id(self):
        """Génère un ID temporaire pour les nouveaux éléments"""
        max_id = 0
        all_items = self._get_all_items(self.tree_widget.invisibleRootItem())
        for item in all_items:
            try:
                item_id = int(item.text(2))
                max_id = max(max_id, item_id)
            except ValueError:
                pass
        return max_id + 1
        
    def _get_all_items(self, parent_item):
        """Récupère tous les éléments de l'arbre"""
        items = []
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            items.append(item)
            items.extend(self._get_all_items(item))
        return items

class StrategyWidget(QWidget):
    """
    Widget principal pour la gestion des stratégies et typologies
    """
    
    strategy_saved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = None
        self.init_ui()
        
    def set_database(self, database):
        """Définit l'objet Database pour tous les onglets"""
        self.database = database
        if self.typology_tab:
            self.typology_tab.set_database(database)
        if self.analysis_tab:
            self.analysis_tab.set_database(database)
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Onglets
        self.tab_widget = QTabWidget()
        
        # Premier onglet - Gestion des typologies
        self.typology_tab = TypologyManagementTab()
        self.tab_widget.addTab(self.typology_tab, "Gestion des Typologies")
        
        # Deuxième onglet - Analyse de représentativité
        self.analysis_tab = StrategyAnalysisTab()
        self.tab_widget.addTab(self.analysis_tab, "Analyse de Représentativité")
        
        layout.addWidget(self.tab_widget)
        
    def on_generation_performed(self):
        """Notifie qu'une nouvelle génération a été effectuée"""
        self.analysis_tab.on_generation_performed()