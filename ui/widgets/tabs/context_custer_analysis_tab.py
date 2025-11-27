from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QFont
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

import logging

from ui.styles.theme import Theme

logger = logging.getLogger(__name__)


class ContextClusterAnalysisTab(QtWidgets.QWidget):
    """Dashboard d'analyse globale du dataset avec navigation séquentielle et visualisations"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis_data = None
        self.selected_typologie = None
        self.selected_cluster = None
        # NOUVEAU: Stocker la correspondance slice -> typologie pour éviter les erreurs de parsing
        self.slice_to_typologie_map = {}
        self._init_ui()

    def _init_ui(self):
        """Initialise l'interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === LIGNE DU HAUT : CARD GROUPÉE ===
        top_row_layout = QtWidgets.QHBoxLayout()

        # Spacer pour pousser la card à droite
        top_row_layout.addStretch()

        # Card groupée : Toggle + Stats
        grouped_card = self._create_grouped_header_card()
        top_row_layout.addWidget(grouped_card)

        layout.addLayout(top_row_layout)

        # === GRAPHIQUE PRINCIPAL PLEIN ÉCRAN ===
        self.chart_container = self._create_chart_container()
        layout.addWidget(self.chart_container, 1)

        # === BREADCRUMB NAVIGATION ===
        self.breadcrumb_widget = self._create_breadcrumb()
        layout.addWidget(self.breadcrumb_widget)

    def _create_grouped_header_card(self):
        """Crée une card groupée compacte avec Toggle + Stats"""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
            }
        """)

        # Layout horizontal unique pour tout mettre sur une ligne
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(20)

        # === SECTION TOGGLE (sans label) ===
        # Radio buttons
        self.radio_all = QtWidgets.QRadioButton("Toutes")
        self.radio_master = QtWidgets.QRadioButton("Master")
        self.radio_context = QtWidgets.QRadioButton("Context")

        self.radio_all.setChecked(True)

        button_style = """
            QRadioButton {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                color: white;
                spacing: 5px;
                background-color: transparent;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 2px solid rgba(255, 255, 255, 0.7);
                background-color: transparent;
            }
            QRadioButton::indicator:hover {
                border-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: white;
                border-color: white;
            }
        """
        self.radio_all.setStyleSheet(button_style)
        self.radio_master.setStyleSheet(button_style)
        self.radio_context.setStyleSheet(button_style)

        # Connexion des signaux
        self.radio_all.toggled.connect(self._on_toggle_changed)
        self.radio_master.toggled.connect(self._on_toggle_changed)
        self.radio_context.toggled.connect(self._on_toggle_changed)

        layout.addWidget(self.radio_all)
        layout.addWidget(self.radio_master)
        layout.addWidget(self.radio_context)

        # Separator vertical
        separator0 = QtWidgets.QFrame()
        separator0.setFrameShape(QtWidgets.QFrame.VLine)
        separator0.setStyleSheet("background-color: rgba(255, 255, 255, 0.3);")
        separator0.setMaximumHeight(30)
        layout.addWidget(separator0)

        # === SECTION STATS ===
        # Total samples
        self.total_label = self._create_stat_label("0", "Total Samples")
        layout.addWidget(self.total_label)

        # Separator vertical
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.VLine)
        separator1.setStyleSheet("background-color: rgba(255, 255, 255, 0.3);")
        separator1.setMaximumHeight(30)
        layout.addWidget(separator1)

        # Stats dynamiques 1
        self.dynamic_stat_1 = self._create_stat_label("0", "Typologies")
        layout.addWidget(self.dynamic_stat_1)

        # Separator vertical
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.VLine)
        separator2.setStyleSheet("background-color: rgba(255, 255, 255, 0.3);")
        separator2.setMaximumHeight(30)
        layout.addWidget(separator2)

        # Stats dynamiques 2
        self.dynamic_stat_2 = self._create_stat_label("0%", "Proportion")
        layout.addWidget(self.dynamic_stat_2)

        return widget
    
    def _create_stat_label(self, value, description):
        """Crée un widget de statistique compact pour la card groupée"""
        container = QtWidgets.QWidget()
        container.setStyleSheet("background: transparent;")
        stat_layout = QtWidgets.QVBoxLayout(container)
        stat_layout.setSpacing(1)
        stat_layout.setContentsMargins(0, 0, 0, 0)

        value_label = QtWidgets.QLabel(value)
        value_label.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        value_label.setAlignment(Qt.AlignCenter)
        stat_layout.addWidget(value_label)

        desc_label = QtWidgets.QLabel(description)
        desc_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.85);
            font-size: 9px;
            font-weight: 500;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        desc_label.setAlignment(Qt.AlignCenter)
        stat_layout.addWidget(desc_label)

        # Stocker les labels pour mise à jour
        container.value_label = value_label
        container.desc_label = desc_label
        return container
    
    def _create_level_drill_down_chart(self):
        """
        Crée un graphique permettant de naviguer dans les niveaux taxonomiques
        ROOT → PARENT → CHILD
        """
        if not self.selected_cluster or not self.selected_typologie:
            return

        typ_name, typ_type = self.selected_typologie

        # Récupérer les données
        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)

        if not typo_data:
            return

        cluster_data = typo_data['clusters'].get(self.selected_cluster)
        if not cluster_data:
            return

        # Déterminer quel niveau afficher
        level_details = cluster_data.get('level_details', {})

        # Créer le pie chart par niveau
        series = QPieSeries()

        colors = {
            'root': '#4CAF50',
            'parent': '#2196F3',
            'child': '#FF9800'
        }

        # Réinitialiser la map pour les clics
        self.slice_to_typologie_map = {}

        total_by_level = {}
        for level in ['root', 'parent', 'child']:
            details = level_details.get(level, {})

            if level == 'root':
                labels = details.get('root_labels', {})
            elif level == 'parent':
                labels = details.get('parent_labels', {})
            else:
                labels = details.get('child_labels', {})

            total = sum(labels.values())
            if total > 0:
                total_by_level[level] = {
                    'total': total,
                    'labels': labels,
                    'color': colors[level]
                }

        if not total_by_level:
            # Fallback vers la vue agrégée
            self._create_aggregated_labels_chart()
            return

        # Créer le graphique par niveau
        for level, data in total_by_level.items():
            slice_ = series.append(level.upper(), data['total'])
            slice_.setLabelVisible(True)
            pct = (data['total'] / cluster_data['sample_count'] * 100) if cluster_data['sample_count'] > 0 else 0
            slice_.setLabel(f"{level.upper()}\n{data['total']} ({pct:.1f}%)")
            slice_.setLabelColor(QColor("#212529"))
            slice_.setLabelFont(self._get_slice_label_font())
            slice_.setColor(QColor(data['color']))

            # Stocker le niveau dans la map
            self.slice_to_typologie_map[slice_] = level

        # Connecter le signal de clic
        series.clicked.connect(self._on_level_slice_clicked)

        chart = QChart()
        chart.addSeries(series)

        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        chart.setTitle(f"Niveaux Taxonomiques - {typ_name} > {self.selected_cluster} [{type_label}]")
        chart.setTitleFont(self._get_chart_title_font())
        chart.setTitleBrush(QColor("#212529"))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor("#ffffff"))

        self.main_chart_view.setChart(chart)

    def _on_level_slice_clicked(self, slice_):
        """Gestion du clic sur un niveau taxonomique"""
        level_name = self.slice_to_typologie_map.get(slice_)

        if not level_name:
            logger.warning(f"Niveau non trouvé dans la map: {slice_.label()}")
            return

        logger.info(f"Niveau cliqué: {level_name}")
        self._show_level_labels(level_name)

    def _show_level_labels(self, level_name: str):
        if not self.selected_cluster or not self.selected_typologie:
            return

        typ_name, typ_type = self.selected_typologie

        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)

        if not typo_data:
            return

        cluster_data = typo_data['clusters'].get(self.selected_cluster)
        if not cluster_data:
            return

        # Récupérer les détails du niveau
        from utils.context_cluster_analyzer import ContextClusterAnalyzer
        level_labels = ContextClusterAnalyzer.get_level_details_for_cluster(
            cluster_data, 
            level_name
        )

        if not level_labels:
            QtWidgets.QMessageBox.information(
                self, 
                "Aucune donnée",
                f"Aucun label trouvé au niveau '{level_name.upper()}'"
            )
            # Retourner à la vue par niveaux
            self._create_level_drill_down_chart()
            return

        # Trier les labels par count
        sorted_labels = sorted(
            level_labels.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:15]

        # Créer le bar chart
        series = QBarSeries()
        bar_set = QBarSet(f"{level_name.upper()} Labels")

        colors = {
            'root': '#4CAF50',
            'parent': '#2196F3',
            'child': '#FF9800'
        }
        bar_set.setColor(QColor(colors.get(level_name, '#667eea')))

        self.bar_index_to_label_map = {}
        categories = []
        for idx, (label, count) in enumerate(sorted_labels):
            bar_set.append(count)
            display_label = label if len(label) <= 25 else label[:22] + "..."
            categories.append(display_label)
            # Stocker le label complet pour récupération ultérieure
            self.bar_index_to_label_map[idx] = label

        chart = QChart()
        chart.addSeries(series)

        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        chart.setTitle(
            f"{level_name.upper()} Labels - {typ_name} > {self.selected_cluster} [{type_label}]"
        )
        chart.setTitleFont(self._get_chart_title_font())
        chart.setTitleBrush(QColor("#212529"))
        chart.setAnimationOptions(QChart.SeriesAnimations)

        # Axes
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setTitleText("Nombre de samples")
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor("#ffffff"))

        self.main_chart_view.setChart(chart)

    def _create_chart_container(self):
        """Crée le conteneur du graphique principal avec boutons de navigation"""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)

        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Boutons de navigation en haut à droite
        top_bar = QtWidgets.QHBoxLayout()

        # Spacer pour pousser les boutons à droite
        top_bar.addStretch()

        # Bouton pour basculer entre vues
        self.toggle_view_button = QtWidgets.QPushButton("Vue Agrégée")
        self.toggle_view_button.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #5568d3;
            }
            QPushButton:pressed {
                background-color: #4451b8;
            }
        """)
        self.toggle_view_button.clicked.connect(self._toggle_view_mode)
        self.toggle_view_button.hide()
        top_bar.addWidget(self.toggle_view_button)

        # Bouton retour
        self.back_to_levels_button = QtWidgets.QPushButton("⬅ Retour Niveaux")
        self.back_to_levels_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        self.back_to_levels_button.clicked.connect(self._back_to_level_view)
        self.back_to_levels_button.hide()
        top_bar.addWidget(self.back_to_levels_button)

        # Bouton reset
        self.reset_button = QtWidgets.QPushButton("Réinitialiser")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #764ba2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #653a8a;
            }
            QPushButton:pressed {
                background-color: #543272;
            }
        """)
        self.reset_button.clicked.connect(self._reset_selection)
        self.reset_button.hide()
        top_bar.addWidget(self.reset_button)

        layout.addLayout(top_bar)

        # Graphique
        self.main_chart_view = QChartView()
        self.main_chart_view.setRenderHint(QPainter.Antialiasing)
        self.main_chart_view.setMinimumHeight(600)
        self.main_chart_view.setStyleSheet("""
            QChartView {
                background-color: white;
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.main_chart_view, 1)

        return widget
    
    def _toggle_view_mode(self):
        """Bascule entre vue par niveaux et vue agrégée"""
        if not hasattr(self, '_current_view_mode'):
            self._current_view_mode = 'levels'

        if self._current_view_mode == 'levels':
            self._current_view_mode = 'aggregated'
            self.toggle_view_button.setText("Vue Niveaux")
            self._create_aggregated_labels_chart()
        else:
            self._current_view_mode = 'levels'
            self.toggle_view_button.setText("Vue Agrégée")
            self._create_level_drill_down_chart()

    def _back_to_level_view(self):
        """Retourne à la vue par niveaux"""
        self._current_view_mode = 'levels'
        self.back_to_levels_button.hide()
        self.toggle_view_button.show()
        self._create_level_drill_down_chart()

    def _create_breadcrumb(self):
        """Crée le fil d'Ariane"""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 10px 15px;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        self.breadcrumb_label = QtWidgets.QLabel("Dataset Global")
        self.breadcrumb_label.setStyleSheet("""
            font-size: 12px;
            color: #495057;
            font-weight: 500;
        """)
        layout.addWidget(self.breadcrumb_label)
        layout.addStretch()

        widget.hide()
        return widget
    
    def _create_combos_widget(self):
        """Crée le widget contenant les combos Projet et Batch"""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
    
        # Combo Projet
        projet_label = QtWidgets.QLabel("Projet:")
        projet_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: 600;
            font-size: 11px;
            color: white;
        """)
        layout.addWidget(projet_label)
    
        self.projet_combo = QtWidgets.QComboBox()
        self.projet_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 5px;
                padding: 5px 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                min-width: 150px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #212529;
                selection-background-color: #667eea;
                selection-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.projet_combo)
    
        # Separator vertical
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.3);")
        separator.setMaximumHeight(30)
        layout.addWidget(separator)
    
        # Combo Batch
        batch_label = QtWidgets.QLabel("Batch:")
        batch_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: 600;
            font-size: 11px;
            color: white;
        """)
        layout.addWidget(batch_label)
    
        self.batch_combo = QtWidgets.QComboBox()
        self.batch_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 5px;
                padding: 5px 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                min-width: 150px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #212529;
                selection-background-color: #667eea;
                selection-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.batch_combo)
    
        return widget
    
    def update_analysis(self, analysis_data):
        """
        Met à jour l'affichage avec les nouvelles données d'analyse
        
        Args:
            analysis_data: Données retournées par ContextClusterAnalyzer
        """
        self.analysis_data = analysis_data

        if not analysis_data:
            self._clear_all()
            return

        # Reset la sélection
        self._reset_selection()

        # === MISE À JOUR DES STATS GLOBALES ===
        total = analysis_data.get('total_samples', 0)
        self.total_label.value_label.setText(str(total))

        # Mise à jour des stats initiales
        filter_type = self._get_current_filter()
        from utils.context_cluster_analyzer import ContextClusterAnalyzer
        sorted_typologies = ContextClusterAnalyzer.get_sorted_typologies(analysis_data, filter_type)
        
        self.dynamic_stat_1.value_label.setText(str(len(sorted_typologies)))
        self.dynamic_stat_1.desc_label.setText("Typologies")
        
        self.dynamic_stat_2.value_label.setText("100%")
        self.dynamic_stat_2.desc_label.setText("Proportion")

        # === CRÉER LE GRAPHIQUE PRINCIPAL ===
        self._create_main_chart()

        logger.info(f"Dashboard d'analyse globale mis à jour - Total: {total} samples, {len(sorted_typologies)} typologies")

    def _on_toggle_changed(self):
        """Gestion du changement de filtre Master/Context/All"""
        if self.analysis_data:
            self._reset_selection()
            self._create_main_chart()

    def _get_current_filter(self):
        """Retourne le filtre actuel ('all', 'master', ou 'context')"""
        if self.radio_master.isChecked():
            return 'master'
        elif self.radio_context.isChecked():
            return 'context'
        else:
            return 'all'

    def _create_main_chart(self):
        """Crée le graphique principal en camembert"""
        if not self.analysis_data:
            return

        # Si un cluster est sélectionné, afficher les labels en histogramme
        if self.selected_cluster:
            self._create_labels_histogram()
            return

        # Si une typologie est sélectionnée, afficher ses clusters
        if self.selected_typologie:
            self._create_cluster_chart()
            return

        # Sinon, afficher les typologies
        self._create_typologie_chart()

    def _create_typologie_chart(self):
        """Crée le graphique des typologies"""
        series = QPieSeries()

        from utils.context_cluster_analyzer import ContextClusterAnalyzer
        
        filter_type = self._get_current_filter()
        sorted_typologies = ContextClusterAnalyzer.get_sorted_typologies(self.analysis_data, filter_type)

        # Palette de couleurs
        colors = [
            "#e63946", "#f77f00", "#fcbf49", "#06d6a0", "#118ab2",
            "#073b4c", "#d62828", "#f77f00", "#3a86ff", "#8338ec",
            "#ff6b6b", "#ee5a6f", "#fca311", "#e85d04", "#4ecdc4"
        ]

        total_samples = self.analysis_data.get('total_samples', 1)

        # NOUVEAU: Réinitialiser la map
        self.slice_to_typologie_map = {}

        for idx, (typologie_name, typo_data) in enumerate(sorted_typologies):
            samples = typo_data['total_samples']
            pct = (samples / total_samples * 100)
            typ_type = typo_data['type']

            type_label = "M" if typ_type == 'master' else "C"

            slice_ = series.append(f"[{type_label}] {typologie_name}", samples)
            slice_.setLabelVisible(True)
            slice_.setLabel(f"{typologie_name}\n{samples} ({pct:.1f}%)")
            slice_.setLabelColor(QColor("#212529"))
            slice_.setLabelFont(self._get_slice_label_font())
            slice_.setColor(QColor(colors[idx % len(colors)]))

            # NOUVEAU: Stocker la correspondance slice -> (typologie_name, type)
            self.slice_to_typologie_map[slice_] = (typologie_name, typ_type)

        # Connecter le signal de clic sur le series
        series.clicked.connect(self._on_pie_slice_clicked)

        chart = QChart()
        chart.addSeries(series)
        
        if filter_type == 'master':
            title = "Distribution des Typologies MASTER"
        elif filter_type == 'context':
            title = "Distribution des Typologies CONTEXT"
        else:
            title = "Distribution Globale des Typologies"
        
        chart.setTitle(title)
        chart.setTitleFont(self._get_chart_title_font())
        chart.setTitleBrush(QColor("#212529"))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor("#ffffff"))

        self.main_chart_view.setChart(chart)

    def _create_cluster_chart(self):
        """Crée le graphique des clusters pour la typologie sélectionnée"""
        if not self.selected_typologie:
            return

        typ_name, typ_type = self.selected_typologie

        # Récupérer les données
        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)
        
        if not typo_data:
            return

        series = QPieSeries()

        from utils.context_cluster_analyzer import ContextClusterAnalyzer
        sorted_clusters = ContextClusterAnalyzer.get_sorted_clusters_for_typologie(typo_data)

        # Palette orangée pour les clusters
        colors = [
            "#ff6b6b", "#ee5a6f", "#f77f00", "#fcbf49", "#ffd60a",
            "#fca311", "#e85d04", "#dc2f02", "#d00000", "#9d0208",
            "#ff9800", "#ff5722", "#ff7043", "#ffab91", "#ffccbc"
        ]

        # NOUVEAU: Réinitialiser la map pour les clusters
        self.slice_to_typologie_map = {}

        for idx, (cluster_name, cluster_data) in enumerate(sorted_clusters):
            sample_count = cluster_data['sample_count']
            pct = (sample_count / typo_data['total_samples'] * 100)

            slice_ = series.append(cluster_name, sample_count)
            slice_.setLabelVisible(True)
            slice_.setLabel(f"{cluster_name}\n{sample_count} ({pct:.1f}%)")
            slice_.setLabelColor(QColor("#212529"))
            slice_.setLabelFont(self._get_slice_label_font())
            slice_.setColor(QColor(colors[idx % len(colors)]))

            # NOUVEAU: Stocker le nom du cluster
            self.slice_to_typologie_map[slice_] = cluster_name

        # Connecter le signal de clic
        series.clicked.connect(self._on_cluster_pie_clicked)

        chart = QChart()
        chart.addSeries(series)
        
        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        chart.setTitle(f"Clusters - {typ_name} [{type_label}]")
        chart.setTitleFont(self._get_chart_title_font())
        chart.setTitleBrush(QColor("#212529"))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor("#ffffff"))

        self.main_chart_view.setChart(chart)
        

    def _create_labels_histogram(self):
        if not self.selected_cluster or not self.selected_typologie:
            return

        typ_name, typ_type = self.selected_typologie

        # Récupérer les données
        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)

        if not typo_data:
            return

        cluster_data = typo_data['clusters'].get(self.selected_cluster)
        if not cluster_data:
            return

        # Vérifier si on a des détails de niveaux
        level_details = cluster_data.get('level_details', {})
        has_level_details = any(
            level_details.get(level, {}).get(f'{level}_labels', {})
            for level in ['root', 'parent', 'child']
        )

        # Si on a des détails de niveaux, proposer la vue par niveaux
        if has_level_details and not hasattr(self, '_current_view_mode'):
            self._current_view_mode = 'levels'  # Par défaut, vue par niveaux

        # Afficher selon le mode
        if hasattr(self, '_current_view_mode') and self._current_view_mode == 'levels':
            self._create_level_drill_down_chart()
        else:
            self._create_aggregated_labels_chart()

    def _create_aggregated_labels_chart(self):
        """Crée un histogramme des labels agrégés (ancienne vue)"""
        if not self.selected_cluster or not self.selected_typologie:
            return

        typ_name, typ_type = self.selected_typologie

        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)

        if not typo_data:
            return

        cluster_data = typo_data['clusters'].get(self.selected_cluster)
        if not cluster_data:
            return

        from utils.context_cluster_analyzer import ContextClusterAnalyzer
        sorted_labels = ContextClusterAnalyzer.get_sorted_labels_for_cluster(cluster_data)

        # Limiter à top 15
        top_labels = sorted_labels[:15]

        # Créer le bar chart
        series = QBarSeries()
        bar_set = QBarSet("Samples")
        bar_set.setColor(QColor("#667eea"))

        categories = []
        for label, count in top_labels:
            bar_set.append(count)
            display_label = label if len(label) <= 20 else label[:17] + "..."
            categories.append(display_label)

        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)

        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        chart.setTitle(f"Labels (Agrégés) - {typ_name} > {self.selected_cluster} [{type_label}]")
        chart.setTitleFont(self._get_chart_title_font())
        chart.setTitleBrush(QColor("#212529"))
        chart.setAnimationOptions(QChart.SeriesAnimations)

        # Axes
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setTitleText("Nombre de samples")
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor("#ffffff"))

        self.main_chart_view.setChart(chart)    

    def _on_pie_slice_clicked(self, slice_):
        """Gestion du clic sur une tranche de typologie"""
        # NOUVEAU: Utiliser la map au lieu de parser le label
        typologie_info = self.slice_to_typologie_map.get(slice_)
        
        if not typologie_info:
            logger.warning(f"Slice non trouvée dans la map: {slice_.label()}")
            return
        
        typologie_name, typ_type = typologie_info
        self._on_typologie_clicked(typologie_name, typ_type)

    def _on_cluster_pie_clicked(self, slice_):
        """Gestion du clic sur une tranche de cluster"""
        # NOUVEAU: Utiliser la map au lieu de parser le label
        cluster_name = self.slice_to_typologie_map.get(slice_)
        
        if not cluster_name:
            logger.warning(f"Cluster slice non trouvé dans la map: {slice_.label()}")
            return
        
        self._on_cluster_clicked(cluster_name)

    def _on_typologie_clicked(self, typologie_name, typ_type):
        """Gestion du clic sur une typologie"""
        logger.info(f"Typologie cliquée: {typologie_name} [{typ_type}]")
        
        self.selected_typologie = (typologie_name, typ_type)
        self.selected_cluster = None

        # Récupérer les données
        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typologie_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typologie_name)
        
        if not typo_data:
            return

        # === MISE À JOUR DES STATS DYNAMIQUES ===
        total_samples = self.analysis_data.get('total_samples', 1)
        typo_samples = typo_data['total_samples']
        typo_pct = (typo_samples / total_samples * 100)
        
        # Stat 1: Nombre de clusters dans cette typologie
        num_clusters = len(typo_data['clusters'])
        self.dynamic_stat_1.value_label.setText(str(num_clusters))
        self.dynamic_stat_1.desc_label.setText("Clusters")
        
        # Stat 2: Proportionnalité de cette typologie
        self.dynamic_stat_2.value_label.setText(f"{typo_pct:.1f}%")
        self.dynamic_stat_2.desc_label.setText("Proportion")

        # Breadcrumb
        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        self.breadcrumb_label.setText(f"Dataset Global > {typologie_name} [{type_label}]")
        self.breadcrumb_widget.show()

        # Bouton reset
        self.reset_button.show()

        # Recréer le graphique avec les clusters
        self._create_cluster_chart()

    def _on_cluster_clicked(self, cluster_name):
        """Gestion du clic sur un cluster - VERSION AMÉLIORÉE"""
        if not self.selected_typologie:
            return

        logger.info(f"Cluster cliqué: {cluster_name}")

        self.selected_cluster = cluster_name

        typ_name, typ_type = self.selected_typologie

        # Récupérer les données
        if typ_type == 'master':
            typo_data = self.analysis_data['master_typologies'].get(typ_name)
        else:
            typo_data = self.analysis_data['context_typologies'].get(typ_name)

        if not typo_data:
            return

        cluster_data = typo_data['clusters'].get(cluster_name)
        if not cluster_data:
            return

        # === MISE À JOUR DES STATS DYNAMIQUES ===
        total_samples = self.analysis_data.get('total_samples', 1)
        cluster_samples = cluster_data['sample_count']
        cluster_pct = (cluster_samples / total_samples * 100)

        # Stat 1: Nombre de labels dans ce cluster
        num_labels = len(cluster_data['labels'])
        self.dynamic_stat_1.value_label.setText(str(num_labels))
        self.dynamic_stat_1.desc_label.setText("Labels")

        # Stat 2: Proportionnalité de ce cluster
        self.dynamic_stat_2.value_label.setText(f"{cluster_pct:.1f}%")
        self.dynamic_stat_2.desc_label.setText("Proportion")

        # Breadcrumb
        type_label = "MASTER" if typ_type == 'master' else "CONTEXT"
        self.breadcrumb_label.setText(f"Dataset Global > {typ_name} [{type_label}] > {cluster_name}")

        # NOUVEAU: Afficher les boutons de navigation
        self.toggle_view_button.show()
        self.back_to_levels_button.hide()  # Caché au début

        # Initialiser le mode de vue
        if not hasattr(self, '_current_view_mode'):
            self._current_view_mode = 'levels'

        # Afficher le graphique approprié
        self._create_labels_histogram()

    def _reset_selection(self):
        """Réinitialise la sélection - VERSION AMÉLIORÉE"""
        self.selected_typologie = None
        self.selected_cluster = None

        self.reset_button.hide()
        self.breadcrumb_widget.hide()
        self.breadcrumb_label.setText("Dataset Global")

        # NOUVEAU: Cacher les boutons de navigation
        if hasattr(self, 'toggle_view_button'):
            self.toggle_view_button.hide()
        if hasattr(self, 'back_to_levels_button'):
            self.back_to_levels_button.hide()

        # Réinitialiser le mode de vue
        if hasattr(self, '_current_view_mode'):
            delattr(self, '_current_view_mode')

        # Réinitialiser les stats dynamiques
        if self.analysis_data:
            filter_type = self._get_current_filter()
            from utils.context_cluster_analyzer import ContextClusterAnalyzer
            sorted_typologies = ContextClusterAnalyzer.get_sorted_typologies(self.analysis_data, filter_type)

            self.dynamic_stat_1.value_label.setText(str(len(sorted_typologies)))
            self.dynamic_stat_1.desc_label.setText("Typologies")

            self.dynamic_stat_2.value_label.setText("100%")
            self.dynamic_stat_2.desc_label.setText("Proportion")

        # Recréer le graphique des typologies
        if self.analysis_data:
            self._create_typologie_chart()

    def _clear_all(self):
        """Vide tous les affichages"""
        self.total_label.value_label.setText("0")
        self.dynamic_stat_1.value_label.setText("0")
        self.dynamic_stat_2.value_label.setText("0%")
        
        self._reset_selection()

    def _get_legend_font(self):
        """Police pour les légendes"""
        font = QFont()
        font.setPointSize(9)
        font.setFamily("Segoe UI")
        return font

    def _get_chart_title_font(self):
        """Police pour les titres de graphiques"""
        font = QFont()
        font.setPointSize(14)
        font.setFamily("Segoe UI")
        font.setBold(True)
        return font

    def _get_slice_label_font(self):
        """Police pour les labels des parts de camembert"""
        font = QFont()
        font.setPointSize(10)
        font.setFamily("Segoe UI")
        font.setBold(True)
        return font