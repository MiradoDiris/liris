import datetime
import csv
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import qtawesome as qta
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from utils.ai_usage_tracker import AIUsageTracker
from utils.logger import logger

MONTHLY_QUOTA_TOKENS = 5000000

class AIUsageWidget(QtWidgets.QWidget):
    usage_updated = pyqtSignal()
    quota_alert = pyqtSignal(int)
    
    def __init__(self, config_provider=None, database=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.database = database
        self.setObjectName("AIUsageWidget")
        
        self.usage_tracker = AIUsageTracker()
        self.current_month = datetime.datetime.now().strftime("%Y-%m")
        self.selected_filter_period = "month"
        
        self._init_style()
        self._init_ui()
        self._load_usage_data()

    def _init_style(self):
        self.setStyleSheet("""
            QWidget#AIUsageWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f5f7fa, stop:1 #e8ecf1);
                color: #333;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            QTableWidget {
                border: none;
                border-radius: 0px;
                background-color: transparent;
                selection-background-color: rgba(217, 83, 79, 0.1);
                selection-color: #333;
                gridline-color: rgba(0, 0, 0, 0.05);
                font-size: 12px;
            }
            
            QTableWidget QHeaderView::section {
                background: transparent;
                color: #666;
                padding: 8px 6px;
                border: none;
                border-bottom: 2px solid rgba(0, 0, 0, 0.1);
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            QTableWidget::item {
                padding: 8px 6px;
                border: none;
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            }
            
            QTableWidget::item:selected {
                background-color: rgba(217, 83, 79, 0.1);
                color: #333;
            }
            
            QProgressBar {
                border: none;
                border-radius: 8px;
                text-align: center;
                background-color: rgba(0, 0, 0, 0.05);
                color: #333;
                font-weight: 600;
                font-size: 11px;
                height: 16px;
            }
            
            QProgressBar::chunk {
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d9534f, stop:1 #e67e73);
            }
            
            QComboBox {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 6px 12px;
                min-width: 100px;
                background-color: white;
                color: #333;
                font-size: 12px;
                font-weight: 500;
            }
            
            QComboBox:hover {
                border-color: #d9534f;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            
            QComboBox QAbstractItemView {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: rgba(217, 83, 79, 0.1);
                selection-color: #333;
                padding: 5px;
            }
            
            QPushButton {
                background: white;
                color: #d9534f;
                border: 2px solid #d9534f;
                padding: 6px 15px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            
            QPushButton:hover {
                background: #d9534f;
                color: white;
            }
            
            QPushButton:pressed {
                background: #c9302c;
                border-color: #c9302c;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 8px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:vertical {
                background: #d9534f;
                border-radius: 4px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #c9302c;
            }
        """)

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header compact
        header_widget = self._create_header()
        layout.addWidget(header_widget)

        # Stats Grid - 3 cartes
        stats_grid = self._create_stats_grid()
        layout.addLayout(stats_grid)

        # Container horizontal: Graphique + Panel droit
        main_container = QtWidgets.QHBoxLayout()
        main_container.setSpacing(15)

        # Graphique (70%)
        graph_widget = self._create_graph_section()
        main_container.addWidget(graph_widget, 7)

        # Panel droit (30%)
        right_panel = self._create_right_panel()
        main_container.addWidget(right_panel, 3)

        layout.addLayout(main_container, 1)

    def _create_header(self):
        """Header compact"""
        header = QtWidgets.QWidget()
        header.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 12px;
                padding: 15px 20px;
            }
        """)
        header.setGraphicsEffect(self._create_shadow(15, 4))
        
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Titre et sous-titre
        title_layout = QtWidgets.QVBoxLayout()
        title_layout.setSpacing(3)
        
        title = QtWidgets.QLabel("Utilisation de l'IA")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 600;
            color: #d9534f;
        """)
        title_layout.addWidget(title)
        
        now = datetime.datetime.now()
        months_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                     'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        subtitle = QtWidgets.QLabel(f"Résumé - {months_fr[now.month-1].capitalize()} {now.year}")
        subtitle.setStyleSheet("font-size: 12px; color: #888;")
        title_layout.addWidget(subtitle)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        return header

    def _create_stats_grid(self):
        """Grid de 3 cartes uniformes"""
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(15)
    
        # Récupérer les vraies données
        stats = self.usage_tracker.get_usage_stats('month')
        total_tokens = stats.get('total_tokens', 0)
        total_calls = stats.get('total_calls', 0)
        total_cost = stats.get('total_cost', 0.0)
        platform_stats = stats.get('platform_stats', [])
    
        # Calcul coût moyen par requête
        avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0
        avg_tokens_per_call = total_tokens // total_calls if total_calls > 0 else 0
    
        # Quota restant
        quota_pct = int((total_tokens / MONTHLY_QUOTA_TOKENS) * 100) if MONTHLY_QUOTA_TOKENS > 0 else 0
        quota_remaining = 100 - quota_pct
    
        # Prévision fin de mois
        now = datetime.datetime.now()
        days_in_month = (datetime.date(now.year, now.month % 12 + 1, 1) - datetime.timedelta(days=1)).day
        if now.day > 0:
            forecast = total_cost + ((total_cost / now.day) * (days_in_month - now.day))
            forecast_tokens = total_tokens + ((total_tokens / now.day) * (days_in_month - now.day))
        else:
            forecast = total_cost
            forecast_tokens = total_tokens
    
        # Cartes - NOUVELLES ICÔNES CORRECTES
        cards_data = [
            ("🤖", "Requêtes IA", f"{total_calls}", "requêtes totales",
             [
                 {'label': 'Tokens/requête', 'value': self._format_number(avg_tokens_per_call)},
                 {'label': 'Coût/requête', 'value': f"{avg_cost_per_call:.4f} €"}
             ], "#667eea", "#764ba2"),
    
            ("database", "Tokens Utilisés", f"{self._format_number(total_tokens)}", f"sur {self._format_number(MONTHLY_QUOTA_TOKENS)}",
             [
                 {'label': 'Utilisé', 'value': f"{quota_pct}%"},
                 {'label': 'Prévision mois', 'value': self._format_number(int(forecast_tokens))}
             ], "#f093fb", "#f5576c"),
    
            ("💰", "Coûts Estimés", f"{total_cost:.2f} €", "ce mois-ci",
             [
                 {'label': 'Aujourd\'hui', 'value': f"{(total_cost / now.day if now.day > 0 else 0):.2f} €"},
                 {'label': 'Prévision mois', 'value': f"{forecast:.2f} €"}
             ], "#4facfe", "#00f2fe")
        ]
    
        for i, (icon, label, value, subtitle, details, color1, color2) in enumerate(cards_data):
            card = self._create_stat_card(icon, label, value, subtitle, details, color1, color2)
            grid.addWidget(card, 0, i)
    
            # Stocker les références pour mise à jour
            if "Requêtes" in label:
                self.calls_value_label = card.findChild(QtWidgets.QLabel, "value_label")
                self.calls_subtitle_label = card.findChild(QtWidgets.QLabel, "subtitle_label")
                self.calls_details_widget = card.findChild(QtWidgets.QWidget, "details_widget")
            elif "Tokens" in label:
                self.tokens_value_label = card.findChild(QtWidgets.QLabel, "value_label")
                self.tokens_subtitle_label = card.findChild(QtWidgets.QLabel, "subtitle_label")
                self.tokens_details_widget = card.findChild(QtWidgets.QWidget, "details_widget")
            elif "Coûts" in label:
                self.cost_value_label = card.findChild(QtWidgets.QLabel, "value_label")
                self.cost_subtitle_label = card.findChild(QtWidgets.QLabel, "subtitle_label")
                self.cost_details_widget = card.findChild(QtWidgets.QWidget, "details_widget")
    
        return grid
    
    def _create_database_icon(self):
        """Crée l'icône SVG de database"""
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtGui import QPixmap, QPainter

        svg_data = """<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
            <path fill="white" d="M256,32c141.4,0,256,40.2,256,89.8v268.4c0,49.6-114.6,89.8-256,89.8S0,439.8,0,390.2V121.8C0,72.2,114.6,32,256,32z M256,64C132.3,64,32,95.5,32,121.8v44.9c37.8,24.5,129.4,41.5,224,41.5s186.2-17,224-41.5v-44.9C480,95.5,379.7,64,256,64z M32,201.3v44.9c37.8,24.5,129.4,41.5,224,41.5s186.2-17,224-41.5v-44.9c-37.8,24.5-129.4,41.5-224,41.5S69.8,225.8,32,201.3z M32,280.9v44.9c37.8,24.5,129.4,41.5,224,41.5s186.2-17,224-41.5v-44.9c-37.8,24.5-129.4,41.5-224,41.5S69.8,305.4,32,280.9z M32,360.4v29.8c0,26.3,100.3,57.8,224,57.8s224-31.5,224-57.8v-29.8c-37.8,24.5-129.4,41.5-224,41.5S69.8,384.9,32,360.4z"/>
        </svg>"""

        renderer = QSvgRenderer(svg_data.encode())
        pixmap = QPixmap(18, 18)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return pixmap

    def _format_number(self, num):
        """Formate les grands nombres (5k, 5M)"""
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}k"
        else:
            return str(int(num))

    def _create_stat_card(self, icon, label, value, subtitle, details, color1, color2):
        """Carte métrique uniforme et épurée"""
        card = QtWidgets.QWidget()
        card.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 12px;
            }
        """)
        card.setGraphicsEffect(self._create_shadow(15, 4))
        card.setFixedHeight(180)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 12, 15, 12)

        # Barre colorée en haut
        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(3)
        top_bar.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color1}, stop:1 {color2}); border-radius: 2px;")
        layout.addWidget(top_bar)

        # En-tête : Icône + Label
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)

        # Gestion de l'icône (emoji ou SVG)
        if icon == "database":
            # Créer un container pour le SVG
            icon_container = QtWidgets.QWidget()
            icon_container.setFixedSize(28, 28)
            icon_container.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {color1}, stop:1 {color2});
                border-radius: 8px;
            """)

            # Créer le label SVG
            svg_label = QtWidgets.QLabel(icon_container)
            svg_label.setPixmap(self._create_database_icon())
            svg_label.setScaledContents(True)
            svg_label.setFixedSize(18, 18)
            svg_label.move(5, 5)

            header_layout.addWidget(icon_container)
        else:
            # Emoji classique
            icon_label = QtWidgets.QLabel(icon)
            icon_label.setStyleSheet(f"""
                font-size: 24px;
                color: transparent;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {color1}, stop:1 {color2});
                -webkit-background-clip: text;
                background-clip: text;
            """)
            header_layout.addWidget(icon_label)

        label_widget = QtWidgets.QLabel(label)
        label_widget.setStyleSheet("""
            font-size: 11px;
            color: #555;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(label_widget)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Valeur principale
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
            line-height: 1.1;
        """)
        layout.addWidget(value_label)

        # Sous-titre
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("subtitle_label")
        subtitle_label.setStyleSheet("""
            font-size: 11px;
            color: #333;
            margin-bottom: 4px;
        """)
        layout.addWidget(subtitle_label)

        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet("background-color: #f0f0f0; max-height: 1px; margin: 4px 0;")
        layout.addWidget(separator)

        # Détails
        details_widget = QtWidgets.QWidget()
        details_widget.setObjectName("details_widget")
        details_layout = QtWidgets.QVBoxLayout(details_widget)
        details_layout.setSpacing(6)
        details_layout.setContentsMargins(0, 0, 0, 0)

        for detail in details:
            if isinstance(detail, dict):
                item_layout = QtWidgets.QHBoxLayout()
                item_layout.setSpacing(5)

                label_text = QtWidgets.QLabel(detail.get('label', ''))
                label_text.setStyleSheet("font-size: 12px; color: #333; font-weight: 500;")
                item_layout.addWidget(label_text)

                item_layout.addStretch()

                value_text = QtWidgets.QLabel(str(detail.get('value', '')))
                value_text.setStyleSheet("font-size: 12px; color: #1a1a1a; font-weight: 700;")
                item_layout.addWidget(value_text)

                item_widget = QtWidgets.QWidget()
                item_widget.setLayout(item_layout)
                details_layout.addWidget(item_widget)

        layout.addWidget(details_widget)
        layout.addStretch()

        return card

    def _create_graph_section(self):
        """Section graphique réduite (70%)"""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        widget.setGraphicsEffect(self._create_shadow(15, 4))

        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header du graphique
        header = QtWidgets.QHBoxLayout()

        title = QtWidgets.QLabel("📈 Consommation de tokens par jour")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1a1a1a;")
        header.addWidget(title)
        header.addStretch()

        # Légende
        legend = QtWidgets.QHBoxLayout()
        legend.setSpacing(20)

        for name, color in [("Claude", "#667eea"), ("Gemini", "#f5576c")]:
            item = QtWidgets.QHBoxLayout()
            item.setSpacing(8)

            color_box = QtWidgets.QLabel()
            color_box.setFixedSize(12, 12)
            color_box.setStyleSheet(f"background: {color}; border-radius: 3px;")
            item.addWidget(color_box)

            label = QtWidgets.QLabel(name)
            label.setStyleSheet("font-size: 12px; color: #333; font-weight: 500;")
            item.addWidget(label)

            item_widget = QtWidgets.QWidget()
            item_widget.setLayout(item)
            legend.addWidget(item_widget)

        header.addLayout(legend)
        layout.addLayout(header)

        # Canvas
        self.fig = Figure(figsize=(10, 4.5), facecolor='white')
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumHeight(320)
        layout.addWidget(self.canvas)

        return widget

    def _create_right_panel(self):
        """Panel droit avec stats par modèle et barres de quota"""
        panel = QtWidgets.QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        panel.setGraphicsEffect(self._create_shadow(15, 4))

        layout = QtWidgets.QVBoxLayout(panel)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre
        title = QtWidgets.QLabel("Statistiques par Modèle")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1a1a1a;")
        layout.addWidget(title)

        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet("background-color: #f0f0f0; max-height: 1px;")
        layout.addWidget(separator)

        # Scroll area pour les stats
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        scroll_content = QtWidgets.QWidget()
        self.models_stats_layout = QtWidgets.QVBoxLayout(scroll_content)
        self.models_stats_layout.setSpacing(12)
        self.models_stats_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        return panel

    def _create_model_stat_item(self, model_name, tokens, calls, percentage, color):
        """Crée un item de statistique pour un modèle"""
        item = QtWidgets.QWidget()
        item.setStyleSheet("""
            QWidget {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(item)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header: Nom + Badge couleur
        header_layout = QtWidgets.QHBoxLayout()
        
        badge = QtWidgets.QLabel()
        badge.setFixedSize(8, 8)
        badge.setStyleSheet(f"background: {color}; border-radius: 4px;")
        header_layout.addWidget(badge)

        name_label = QtWidgets.QLabel(model_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a1a;")
        header_layout.addWidget(name_label, 1)

        layout.addLayout(header_layout)

        # Stats
        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(15)

        # Tokens
        tokens_layout = QtWidgets.QVBoxLayout()
        tokens_layout.setSpacing(2)
        tokens_label = QtWidgets.QLabel("Tokens")
        tokens_label.setStyleSheet("font-size: 11px; color: #555;")
        tokens_layout.addWidget(tokens_label)
        tokens_value = QtWidgets.QLabel(self._format_number(tokens))
        tokens_value.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a1a;")
        tokens_layout.addWidget(tokens_value)
        stats_layout.addLayout(tokens_layout)

        # Requêtes
        calls_layout = QtWidgets.QVBoxLayout()
        calls_layout.setSpacing(2)
        calls_label = QtWidgets.QLabel("Requêtes")
        calls_label.setStyleSheet("font-size: 11px; color: #555;")
        calls_layout.addWidget(calls_label)
        calls_value = QtWidgets.QLabel(str(calls))
        calls_value.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a1a1a;")
        calls_layout.addWidget(calls_value)
        stats_layout.addLayout(calls_layout)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Barre de progression avec quota
        progress_container = QtWidgets.QVBoxLayout()
        progress_container.setSpacing(4)

        progress_header = QtWidgets.QHBoxLayout()
        progress_label = QtWidgets.QLabel("Quota utilisé")
        progress_label.setStyleSheet("font-size: 11px; color: #555;")
        progress_header.addWidget(progress_label)
        progress_header.addStretch()
        progress_pct = QtWidgets.QLabel(f"{percentage:.1f}%")
        progress_pct.setStyleSheet("font-size: 11px; font-weight: 600; color: #1a1a1a;")
        progress_header.addWidget(progress_pct)
        progress_container.addLayout(progress_header)

        progress = QtWidgets.QProgressBar()
        progress.setMaximum(100)
        progress.setValue(int(percentage))
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: rgba(0, 0, 0, 0.05);
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: {color};
            }}
        """)
        progress_container.addWidget(progress)

        layout.addLayout(progress_container)

        return item

    def _create_shadow(self, blur=15, offset=4):
        """Crée un effet d'ombre"""
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setXOffset(0)
        shadow.setYOffset(offset)
        shadow.setColor(QtGui.QColor(0, 0, 0, 25))
        return shadow

    def _load_usage_data(self):
        """Charge les données"""
        try:
            self._update_ui()
            logger.info("✅ Données chargées")
        except Exception as e:
            logger.error(f"Erreur chargement: {e}")

    def record_ai_request(self, platform, inp, out, success=True, duration=0.0, model_name=None):
        """Enregistre une requête"""
        try:
            self.usage_tracker.record_usage(
                platform_name=platform,
                model_name=model_name or platform,
                success=success,
                duration_seconds=duration,
                input_tokens=inp,
                output_tokens=out,
                session_type='coding'
            )
            self._update_ui()
            self.usage_updated.emit()
        except Exception as e:
            logger.error(f"Erreur enregistrement: {e}")

    def _check_quota(self):
        """Vérifie le quota"""
        try:
            stats = self.usage_tracker.get_usage_stats('month')
            total_tokens = stats.get('total_tokens', 0)
            if MONTHLY_QUOTA_TOKENS > 0:
                pct = (total_tokens / MONTHLY_QUOTA_TOKENS) * 100
                if pct >= 80:
                    self.quota_alert.emit(int(pct))
        except Exception as e:
            logger.error(f"Erreur quota: {e}")

    def refresh_data(self):
        """Rafraîchit les données"""
        try:
            self._update_ui()
            logger.info("✅ Rafraîchi")
        except Exception as e:
            logger.error(f"Erreur: {e}")

    def _update_ui(self):
        """Met à jour l'UI"""
        try:
            stats = self.usage_tracker.get_usage_stats('month')
            self._update_stat_cards(stats)
            self._update_graph()
            self._update_models_panel(stats)
        except Exception as e:
            logger.error(f"Erreur UI: {e}")

    def _update_stat_cards(self, stats):
        """Met à jour les cartes de stats"""
        try:
            total_tokens = stats.get('total_tokens', 0)
            total_calls = stats.get('total_calls', 0)
            total_cost = stats.get('total_cost', 0.0)

            # Calculs
            avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0
            avg_tokens_per_call = total_tokens // total_calls if total_calls > 0 else 0
            quota_pct = int((total_tokens / MONTHLY_QUOTA_TOKENS) * 100) if MONTHLY_QUOTA_TOKENS > 0 else 0

            now = datetime.datetime.now()
            days_in_month = (datetime.date(now.year, now.month % 12 + 1, 1) - datetime.timedelta(days=1)).day
            forecast = total_cost + ((total_cost / now.day) * (days_in_month - now.day)) if now.day > 0 else total_cost
            forecast_tokens = total_tokens + ((total_tokens / now.day) * (days_in_month - now.day)) if now.day > 0 else total_tokens

            # Requêtes
            if hasattr(self, 'calls_value_label'):
                self.calls_value_label.setText(f"{total_calls}")
                self.calls_subtitle_label.setText("requêtes totales")
                self._update_details(self.calls_details_widget, [
                    {'label': 'Tokens/requête', 'value': self._format_number(avg_tokens_per_call)},
                    {'label': 'Coût/requête', 'value': f"{avg_cost_per_call:.4f} €"}
                ])

            # Tokens
            if hasattr(self, 'tokens_value_label'):
                self.tokens_value_label.setText(self._format_number(total_tokens))
                self.tokens_subtitle_label.setText(f"sur {self._format_number(MONTHLY_QUOTA_TOKENS)}")
                self._update_details(self.tokens_details_widget, [
                    {'label': 'Utilisé', 'value': f"{quota_pct}%"},
                    {'label': 'Prévision mois', 'value': self._format_number(int(forecast_tokens))}
                ])

            # Coûts
            if hasattr(self, 'cost_value_label'):
                self.cost_value_label.setText(f"{total_cost:.2f} €")
                self.cost_subtitle_label.setText("ce mois-ci")
                self._update_details(self.cost_details_widget, [
                    {'label': 'Aujourd\'hui', 'value': f"{(total_cost / now.day if now.day > 0 else 0):.2f} €"},
                    {'label': 'Prévision mois', 'value': f"{forecast:.2f} €"}
                ])

        except Exception as e:
            logger.error(f"Erreur cartes: {e}")

    def _update_details(self, details_widget, details):
        """Met à jour les détails d'une carte"""
        # Vider les anciens détails
        for i in reversed(range(details_widget.layout().count())): 
            details_widget.layout().itemAt(i).widget().setParent(None)

        # Ajouter les nouveaux
        for detail in details:
            item_layout = QtWidgets.QHBoxLayout()
            item_layout.setSpacing(5)

            label_text = QtWidgets.QLabel(detail.get('label', ''))
            label_text.setStyleSheet("font-size: 12px; color: #333; font-weight: 500;")
            item_layout.addWidget(label_text)

            item_layout.addStretch()

            value_text = QtWidgets.QLabel(str(detail.get('value', '')))
            value_text.setStyleSheet("font-size: 12px; color: #1a1a1a; font-weight: 700;")
            item_layout.addWidget(value_text)

            item_widget = QtWidgets.QWidget()
            item_widget.setLayout(item_layout)
            details_widget.layout().addWidget(item_widget)

    def _update_models_panel(self, stats):
        """Met à jour le panel des modèles"""
        try:
            # Vider le layout
            for i in reversed(range(self.models_stats_layout.count())): 
                widget = self.models_stats_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            platform_stats = stats.get('platform_stats', [])
            
            # Couleurs par modèle
            colors = {
                'Claude': '#667eea',
                'Gemini': '#f5576c',
                'GPT-4': '#4facfe',
                'Grok': '#f093fb'
            }

            # Ajouter chaque modèle
            for ps in platform_stats:
                model_name = ps['name']
                tokens = ps['tokens']
                calls = ps.get('calls', 0)
                
                # Calculer le pourcentage du quota par modèle (5M par modèle)
                percentage = (tokens / MONTHLY_QUOTA_TOKENS) * 100
                
                # Déterminer la couleur
                color = colors.get(model_name, '#999')
                for key in colors:
                    if key in model_name:
                        color = colors[key]
                        break
                
                item = self._create_model_stat_item(model_name, tokens, calls, percentage, color)
                self.models_stats_layout.addWidget(item)

            # Ajouter un stretch à la fin
            self.models_stats_layout.addStretch()

        except Exception as e:
            logger.error(f"Erreur panel modèles: {e}")

    def _update_graph(self):
        """Met à jour le graphique avec courbes lisses partant de (0,0)"""
        try:
            self.fig.clear()
            ax = self.fig.add_subplot(111)

            daily_data = self.usage_tracker.get_daily_consumption(days=30)

            if not daily_data:
                ax.text(0.5, 0.5, 'Aucune donnée disponible', 
                       ha='center', va='center', fontsize=14, color='#999')
                ax.set_facecolor('white')
                self.canvas.draw()
                return

            from collections import defaultdict
            import numpy as np
            from scipy.interpolate import make_interp_spline

            data_by_day = defaultdict(lambda: defaultdict(int))

            for entry in daily_data:
                data_by_day[entry['date']][entry['platform']] += entry['tokens']

            days = sorted(data_by_day.keys())
            platforms = sorted(set(p for day_data in data_by_day.values() for p in day_data.keys()))

            # Extraire les numéros de jour pour l'axe X
            day_nums = [int(d.split('-')[2]) for d in days]

            # LOGIQUE DYNAMIQUE POUR L'ÉTENDUE DE L'AXE
            if day_nums:
                min_day_data = min(day_nums)
                max_day_data = max(day_nums)

                # Calculer la plage de jours avec données
                data_range = max_day_data - min_day_data + 1

                # Déterminer l'étendue optimale
                if data_range <= 7:
                    min_day = 1
                    max_day = max(max_day_data + 2, 7)
                elif data_range <= 15:
                    min_day = 1
                    max_day = max(max_day_data + 3, 15)
                else:
                    min_day = 1
                    max_day = min(max_day_data + 5, 31)

                all_days = list(range(min_day, max_day + 1))
            else:
                all_days = []

            # Couleurs exactes
            colors = {
                'Claude': '#667eea',
                'Gemini': '#f5576c',
                'GPT-4': '#4facfe',
                'Grok': '#f093fb'
            }

            # Stocker les données pour le hover
            self.plot_data = {}

            # Tracer les courbes
            for platform in platforms:
                # Créer les points de données avec (0,0) comme point de départ
                x_points = [0]
                y_points = [0]
                actual_points_x = []
                actual_points_y = []

                for day in all_days:
                    found = False
                    for i, d in enumerate(day_nums):
                        if d == day:
                            token_value = data_by_day[days[i]].get(platform, 0)
                            x_points.append(day)
                            y_points.append(token_value)
                            if token_value > 0:
                                actual_points_x.append(day)
                                actual_points_y.append(token_value)
                            found = True
                            break
                        
                    if not found:
                        x_points.append(day)
                        y_points.append(0)

                color = colors.get(platform, '#999')

                if len(x_points) > 3:
                    try:
                        x_array = np.array(x_points)
                        y_array = np.array(y_points)

                        spl = make_interp_spline(x_array, y_array, k=3)
                        x_smooth = np.linspace(0, max(x_points), 500)
                        y_smooth = spl(x_smooth)
                        y_smooth = np.maximum(y_smooth, 0)

                    except Exception as e:
                        x_smooth = np.array(x_points)
                        y_smooth = np.array(y_points)
                else:
                    x_smooth = np.array(x_points)
                    y_smooth = np.array(y_points)

                # Ligne principale lisse
                ax.plot(x_smooth, y_smooth,
                       color=color,
                       linewidth=3,
                       label=platform,
                       zorder=3,
                       alpha=0.9)

                # Points de données réels (uniquement ceux avec des valeurs > 0)
                if actual_points_x:
                    scatter = ax.plot(actual_points_x, actual_points_y,
                           'o',
                           markersize=10,
                           markerfacecolor=color,
                           markeredgecolor='white',
                           markeredgewidth=3,
                           zorder=5,
                           picker=5)[0]  # picker permet la détection du survol

                    # Stocker les données pour ce scatter
                    self.plot_data[scatter] = {
                        'platform': platform,
                        'x': actual_points_x,
                        'y': actual_points_y,
                        'color': color
                    }

            # Style
            ax.set_facecolor('white')
            self.fig.patch.set_facecolor('white')
            ax.set_xlabel('Jour du mois', fontsize=13, fontweight='bold', color='#666')
            ax.set_ylabel('', fontsize=11, color='#666')

            # Grille horizontale fine et claire
            ax.yaxis.grid(True, linestyle='-', alpha=0.05, color='#000', linewidth=0.5, zorder=0)
            ax.xaxis.grid(False)
            ax.set_axisbelow(True)

            # Supprimer les bordures supérieure et droite
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_linewidth(0.5)
            ax.spines['left'].set_color('#e0e0e0')
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['bottom'].set_color('#e0e0e0')

            # Format des ticks Y avec k/M
            from matplotlib.ticker import FuncFormatter

            def format_func(value, tick_number):
                if value == 0:
                    return '0'
                elif value >= 1000000:
                    val = value / 1000000
                    return f'{int(val)}M' if val == int(val) else f'{val:.1f}M'
                elif value >= 1000:
                    val = value / 1000
                    return f'{int(val)}k' if val == int(val) else f'{val:.1f}k'
                else:
                    return str(int(value))

            ax.yaxis.set_major_formatter(FuncFormatter(format_func))
            ax.tick_params(axis='both', labelsize=12, colors='#666')

            # Limites dynamiques
            ax.set_ylim(bottom=0)
            if all_days:
                ax.set_xlim(-0.5, max_day + 0.5)

                if max_day <= 10:
                    ax.set_xticks(range(0, max_day + 1, 1))
                elif max_day <= 20:
                    ax.set_xticks(range(0, max_day + 1, 2))
                else:
                    ax.set_xticks(range(0, max_day + 1, 5))

            # Créer une annotation invisible pour le hover
            self.annot = ax.annotate("", xy=(0, 0), xytext=(10, 10),
                                     textcoords="offset points",
                                     bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.95),
                                     arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
                                     fontsize=11, fontweight='600', zorder=10)
            self.annot.set_visible(False)

            # Connecter l'événement de mouvement de souris
            self.canvas.mpl_connect('motion_notify_event', self._on_hover)

            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            logger.error(f"Erreur graphique: {e}")

    def _on_hover(self, event):
        """Gère l'affichage des informations au survol des points"""
        if event.inaxes is None:
            self.annot.set_visible(False)
            self.canvas.draw_idle()
            return
        
        # Vérifier si la souris est proche d'un point
        for scatter, data in self.plot_data.items():
            contains, ind = scatter.contains(event)
            if contains:
                # Récupérer les coordonnées du point
                idx = ind['ind'][0]
                x_val = data['x'][idx]
                y_val = data['y'][idx]
                platform = data['platform']
                
                # Mettre à jour l'annotation
                self.annot.xy = (x_val, y_val)
                text = f"{platform}\nJour {x_val}: {self._format_number(int(y_val))} tokens"
                self.annot.set_text(text)
                self.annot.get_bbox_patch().set_facecolor('white')
                self.annot.get_bbox_patch().set_edgecolor(data['color'])
                self.annot.get_bbox_patch().set_linewidth(2)
                self.annot.get_bbox_patch().set_alpha(0.95)
                self.annot.set_color('black')
                self.annot.set_fontsize(9)
                self.annot.set_fontweight('normal')
                self.annot.set_visible(True)
                self.canvas.draw_idle()
                return
        
        # Si aucun point n'est survolé, cacher l'annotation
        self.annot.set_visible(False)
        self.canvas.draw_idle()

    def update_language(self):
        """Mise à jour langue"""
        pass

    def refresh(self):
        """Alias refresh_data"""
        self.refresh_data()