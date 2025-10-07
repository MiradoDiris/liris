#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
audit_panel.py - Panel d'audit de code généré (version simplifiée sans score global)
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QComboBox, QLabel, QSplitter, QTreeWidget,
    QTreeWidgetItem, QGroupBox, QProgressBar, QMessageBox, QApplication
)
import sys


class AuditPanel(QWidget):
    """
    Panel pour l'audit de code généré par l'IA.
    Analyse le code selon plusieurs critères : qualité, sécurité, performance, maintenabilité.
    """

    # Signaux
    audit_started = pyqtSignal(str)  # audit_id
    audit_completed = pyqtSignal(str)  # audit_id
    audit_failed = pyqtSignal(str, str)  # audit_id, error
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conductor = None
        self.platforms = []
        self.current_audit_id = None

        # Couleurs du thème (harmonisées avec MainWindow et CodingPanel)
        self.primary_color = "#A23B2D"  # Rouge brique
        self.secondary_color = "#D35A4A"  # Rouge brique clair
        self.background_color = "#F9F6F6"  # Beige très clair
        self.text_color = "#333333"  # Gris foncé
        self.accent_color = "#E8E0DF"  # Gris clair pour les accents

        self._init_style()
        self._init_ui()

    def _init_style(self):
        """Configure le style global du widget"""
        stylesheet = f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QGroupBox {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            margin-top: 1em;
            padding: 10px;
            background-color: white;
            font-weight: bold;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            min-height: 28px;
        }}

        QPushButton:hover {{
            background-color: {self.secondary_color};
        }}

        QPushButton:pressed {{
            background-color: #8B1A1A;
        }}

        QPushButton:disabled {{
            background-color: #CCCCCC;
        }}

        QComboBox {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            padding: 6px;
            background-color: white;
            min-width: 120px;
        }}

        QComboBox:focus {{
            border: 2px solid {self.primary_color};
        }}

        QComboBox::drop-down {{
            border: none;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {self.text_color};
        }}

        QComboBox QAbstractItemView {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            background-color: white;
            selection-background-color: {self.primary_color};
            outline: none;
        }}

        QTextEdit {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            padding: 8px;
            background-color: white;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
        }}

        QTextEdit:focus {{
            border: 2px solid {self.primary_color};
        }}

        QTreeWidget {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            background-color: white;
            alternate-background-color: #f9f9f9;
        }}

        QTreeWidget::item {{
            padding: 5px;
            border-bottom: 1px solid #eee;
        }}

        QTreeWidget::item:selected {{
            background-color: {self.accent_color};
            color: white;
        }}

        QProgressBar {{
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            text-align: center;
            background-color: #F0F0F0;
        }}

        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 4px;
        }}

        QLabel {{
            color: {self.text_color};
        }}
        """
        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # En-tête
        header = self._create_header()
        main_layout.addWidget(header)

        # Zone principale divisée en deux parties
        splitter = QSplitter(Qt.Horizontal)

        # Partie gauche : Configuration et code à auditer
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Partie droite : Résultats de l'audit
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(100)
        main_layout.addWidget(self.progress_bar)

    def _create_header(self):
        """Crée l'en-tête du panel"""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 10)

        # Titre
        title_label = QLabel("Audit de Code")
        title_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {self.primary_color};
        """)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Sélection de la plateforme IA
        platform_label = QLabel("Plateforme d'audit:")
        header_layout.addWidget(platform_label)

        self.platform_combo = QComboBox()
        self.platform_combo.setMinimumWidth(180)
        self.platform_combo.setMaximumWidth(200)
        header_layout.addWidget(self.platform_combo)

        return header_widget

    def _create_left_panel(self):
        """Crée le panel gauche avec la configuration"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # Sélection du projet
        project_group = QGroupBox("Projet à auditer")
        project_layout = QVBoxLayout()

        project_selector_layout = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(180)
        self.project_combo.setMaximumWidth(220)
        project_selector_layout.addWidget(QLabel("Projet:"))
        project_selector_layout.addWidget(self.project_combo, 1)

        refresh_btn = QPushButton("Actualiser")
        refresh_btn.setFixedWidth(85)
        refresh_btn.setFixedHeight(28)
        refresh_btn.setToolTip("Actualiser la liste des projets")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: {self.text_color};
                border: 1px solid {self.accent_color};
                border-radius: 4px;
                font-size: 11px;
                font-weight: normal;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {self.secondary_color};
                color: white;
                border: 1px solid {self.secondary_color};
            }}
            QPushButton:pressed {{
                background-color: {self.primary_color};
            }}
        """)
        refresh_btn.clicked.connect(self._refresh_projects)
        project_selector_layout.addWidget(refresh_btn)

        project_layout.addLayout(project_selector_layout)
        project_group.setLayout(project_layout)
        left_layout.addWidget(project_group)

        # Critères d'audit
        criteria_group = QGroupBox("Critères d'audit")
        criteria_layout = QVBoxLayout()

        self.criteria_checkboxes = {}
        criteria = [
            ("quality", "Qualité du code", True),
            ("security", "Sécurité", True),
            ("performance", "Performance", True),
            ("maintainability", "Maintenabilité", True),
            ("best_practices", "Bonnes pratiques", True),
            ("documentation", "Documentation", False),
        ]

        for key, label, checked in criteria:
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setChecked(checked)
            self.criteria_checkboxes[key] = checkbox
            criteria_layout.addWidget(checkbox)

        criteria_group.setLayout(criteria_layout)
        left_layout.addWidget(criteria_group)

        # Zone de code personnalisé
        code_group = QGroupBox("Code à auditer (optionnel)")
        code_layout = QVBoxLayout()

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText(
            "Collez ici le code à auditer, ou laissez vide pour auditer "
            "tout le projet sélectionné..."
        )
        self.code_input.setMaximumHeight(200)
        code_layout.addWidget(self.code_input)

        code_group.setLayout(code_layout)
        left_layout.addWidget(code_group)

        # Boutons d'action
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.start_audit_btn = QPushButton("Lancer l'audit")
        self.start_audit_btn.setMinimumHeight(32)
        self.start_audit_btn.setMaximumWidth(150)
        self.start_audit_btn.clicked.connect(self._start_audit)
        actions_layout.addWidget(self.start_audit_btn)

        self.export_btn = QPushButton("Exporter")
        self.export_btn.setMinimumHeight(32)
        self.export_btn.setMaximumWidth(120)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_results)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addStretch()

        left_layout.addLayout(actions_layout)
        left_layout.addStretch()

        return left_widget

    def _create_right_panel(self):
        """Crée le panel droit avec les résultats"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # Résultats détaillés
        results_group = QGroupBox("Résultats détaillés")
        results_layout = QVBoxLayout()

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Catégorie", "Score", "Statut"])
        self.results_tree.setAlternatingRowColors(True)
        results_layout.addWidget(self.results_tree)

        results_group.setLayout(results_layout)
        right_layout.addWidget(results_group)

        # Recommandations
        recommendations_group = QGroupBox("Recommandations")
        recommendations_layout = QVBoxLayout()

        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMaximumHeight(200)
        self.recommendations_text.setPlaceholderText(
            "Les recommandations d'amélioration apparaîtront ici..."
        )
        recommendations_layout.addWidget(self.recommendations_text)

        recommendations_group.setLayout(recommendations_layout)
        right_layout.addWidget(recommendations_group)

        return right_widget

    def set_conductor(self, conductor):
        """Set the conductor for the audit panel"""
        self.conductor = conductor

    def set_platforms(self, platforms):
        """Set the available platforms for audit"""
        self.platforms = platforms
        self.platform_combo.clear()
        for platform in platforms:
            self.platform_combo.addItem(platform)

    def _refresh_projects(self):
        """Rafraîchit la liste des projets disponibles"""
        self.project_combo.clear()
        self.project_combo.addItem("Projet exemple 1")
        self.project_combo.addItem("Projet exemple 2")
        self.project_combo.addItem("Projet exemple 3")

    def _start_audit(self):
        """Lance l'audit du code"""
        import uuid
        self.current_audit_id = str(uuid.uuid4())

        # Simule un traitement
        self.audit_started.emit(self.current_audit_id)
        self.start_audit_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        QtCore.QTimer.singleShot(2000, self._simulate_audit_results)

    def _simulate_audit_results(self):
        """Simule des résultats d'audit (pour l'exemple)"""
        results = {
            "scores_criteres": {
                "quality": 82,
                "security": 75,
                "performance": 80,
                "maintainability": 76,
                "best_practices": 78,
            },
            "problemes": [
                {
                    "type": "security",
                    "gravite": "elevee",
                    "description": "Injection SQL potentielle détectée",
                    "ligne": 45
                },
                {
                    "type": "performance",
                    "gravite": "moyenne",
                    "description": "Boucle inefficace qui pourrait être optimisée",
                    "ligne": 78
                },
            ],
            "recommandations": [
                "Utiliser des requêtes préparées pour éviter les injections SQL",
                "Remplacer la boucle for par une compréhension de liste",
                "Ajouter des validations d'entrée utilisateur",
                "Améliorer la documentation des fonctions complexes"
            ]
        }

        self._display_results(results)
        self.progress_bar.setValue(100)
        QtCore.QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
        self.start_audit_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.audit_completed.emit(self.current_audit_id)

    def _display_results(self, results):
        """Affiche les résultats de l'audit"""
        self.results_tree.clear()
        scores_criteres = results.get("scores_criteres", {})

        for criterion, score in scores_criteres.items():
            item = QTreeWidgetItem([
                criterion.replace("_", " ").title(),
                f"{score}/100",
                self._get_status_text(score)
            ])

            if score >= 80:
                item.setForeground(2, QtGui.QBrush(QtGui.QColor("#4CAF50")))
            elif score >= 60:
                item.setForeground(2, QtGui.QBrush(QtGui.QColor("#FFC107")))
            else:
                item.setForeground(2, QtGui.QBrush(QtGui.QColor("#F44336")))

            self.results_tree.addTopLevelItem(item)

        problemes_item = QTreeWidgetItem(["Problèmes détectés", "", ""])
        self.results_tree.addTopLevelItem(problemes_item)

        for probleme in results.get("problemes", []):
            prob_item = QTreeWidgetItem([
                probleme.get("description", ""),
                f"Ligne {probleme.get('ligne', '?')}",
                probleme.get("gravite", "").upper()
            ])

            gravite = probleme.get("gravite", "").lower()
            if gravite in ["critique", "elevee"]:
                prob_item.setForeground(2, QtGui.QBrush(QtGui.QColor("#F44336")))
            elif gravite == "moyenne":
                prob_item.setForeground(2, QtGui.QBrush(QtGui.QColor("#FF9800")))
            else:
                prob_item.setForeground(2, QtGui.QBrush(QtGui.QColor("#FFC107")))

            problemes_item.addChild(prob_item)

        self.results_tree.expandAll()

        recommendations = results.get("recommandations", [])
        if recommendations:
            text = "\n".join([f"• {rec}" for rec in recommendations])
            self.recommendations_text.setPlainText(text)
        else:
            self.recommendations_text.setPlainText("Aucune recommandation particulière.")

    def _get_status_text(self, score):
        """Retourne le texte de statut selon le score"""
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Bon"
        elif score >= 40:
            return "Moyen"
        else:
            return "Faible"

    def _export_results(self):
        """Exporte les résultats de l'audit"""
        self.export_requested.emit()
        QMessageBox.information(
            self,
            "Export",
            "Les résultats d'audit ont été exportés avec succès."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuditPanel()
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec_())