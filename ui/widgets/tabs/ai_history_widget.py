import datetime
import csv
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
import qtawesome as qta
from utils.ai_usage_tracker import AIUsageTracker
from utils.logger import logger


class AIHistoryWidget(QtWidgets.QWidget):
    """Widget séparé pour l'historique des requêtes IA."""

    def __init__(self, config_provider=None, database=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.database = database
        self.usage_tracker = AIUsageTracker()
        self.selected_filter_period = "month"
        self._init_style()
        self._init_ui()
        self._update_table()

    def _init_style(self):
        self.setStyleSheet("""
            QWidget#AIHistoryWidget { background-color: #f8f9fb; }
            QTableWidget {
                border: none; border-radius: 8px; background-color: white;
                selection-background-color: #d9534f; selection-color: white;
                gridline-color: #f0f0f0;
            }
            QTableWidget QHeaderView::section {
                background: #d9534f; color: white; font-weight: 600;
                padding: 8px; border: none;
            }
            QPushButton {
                background: #d9534f; color: white; border: none;
                padding: 8px 16px; border-radius: 6px;
            }
            QPushButton:hover { background: #e67e73; }
            QComboBox {
                border: 2px solid #e8ecf1; border-radius: 6px;
                padding: 6px 10px; background-color: white;
            }
        """)

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # En-tête
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("📋 Historique des Requêtes IA")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #d9534f;")
        header.addWidget(title)
        header.addStretch()

        self.export_button = QtWidgets.QPushButton("Exporter CSV")
        self.export_button.setIcon(qta.icon('fa5s.file-export', color='white'))
        self.export_button.clicked.connect(self._export_csv)
        header.addWidget(self.export_button)
        layout.addLayout(header)

        # Filtres
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("🔍 Filtrer par période :"))
        self.period_filter_combo = QtWidgets.QComboBox()
        self.period_filter_combo.addItems(["Aujourd'hui", "Cette semaine", "Ce mois"])
        self.period_filter_combo.setCurrentIndex(2)
        self.period_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.period_filter_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["📅 Date", "🤖 Modèle", "📥 Tokens In", "📤 Tokens Out", "💰 Coût", "✓ Statut"]
        )
        header = self.history_table.horizontalHeader()
        for i in range(6):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.history_table)

    def _on_filter_changed(self, idx):
        self.selected_filter_period = ["day", "week", "month"][idx]
        self._update_table()

    def _update_table(self):
        try:
            history = self.usage_tracker.get_usage_history(limit=200, filter_period=self.selected_filter_period)
            self.history_table.setRowCount(len(history))
            for i, record in enumerate(history):
                dt = datetime.datetime.fromisoformat(record['date'])
                vals = [
                    dt.strftime("%d/%m/%Y %H:%M"),
                    record['model'],
                    f"{record['tokens']//2:,}",
                    f"{record['tokens']//2:,}",
                    f"{record['cost']:.4f} €",
                    "✅ Succès" if record['success'] else "❌ Échec"
                ]
                for j, val in enumerate(vals):
                    item = QtWidgets.QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.history_table.setItem(i, j, item)
        except Exception as e:
            logger.error(f"Erreur chargement historique: {e}")

    def _export_csv(self):
        try:
            history = self.usage_tracker.get_usage_history(limit=1000)
            if not history:
                QtWidgets.QMessageBox.information(self, "Aucune donnée", "Aucune donnée à exporter.")
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Exporter l'historique", "ai_history.csv", "CSV Files (*.csv)")
            if path:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Date', 'Modèle', 'Tokens', 'Coût (€)', 'Statut'])
                    for r in history:
                        writer.writerow([r['date'], r['model'], r['tokens'],
                                         f"{r['cost']:.4f}",
                                         'Succès' if r['success'] else 'Échec'])
                QtWidgets.QMessageBox.information(self, "Export réussi", f"Données exportées vers :\n{path}")
        except Exception as e:
            logger.error(f"Erreur export CSV: {e}")
