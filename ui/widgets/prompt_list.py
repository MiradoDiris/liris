#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.localization.translator import tr


class PromptList(QtWidgets.QWidget):
    """
    Widget pour l'historique des prompts
    """

    # Signaux
    prompt_selected = pyqtSignal(int)
    prompt_deleted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.database = None
        self.current_prompt_id = None

        # Couleurs du thème
        self.primary_color = "#A23B2D"  # Rouge brique
        self.secondary_color = "#D35A4A"  # Rouge brique clair
        self.background_color = "#F5F0EF"  # Beige clair
        self.text_color = "#333333"  # Gris foncé
        self.accent_color = "#E38272"  # Rose pâle

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

        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: bold;
            min-width: 120px;
        }}

        QPushButton:hover {{
            background-color: {self.secondary_color};
        }}

        QPushButton:pressed {{
            background-color: #922E23;
        }}

        QPushButton:disabled {{
            background-color: #CCCCCC;
        }}

        QComboBox {{
            padding: 8px;
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            background-color: white;
            min-width: 120px;
        }}

        QComboBox:hover {{
            border: 2px solid {self.primary_color};
        }}

        QComboBox::drop-down {{
            border: none;
        }}

        QLineEdit {{
            padding: 8px;
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            background-color: white;
        }}

        QLineEdit:focus {{
            border: 2px solid {self.primary_color};
        }}

        QTableWidget {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            background-color: white;
            gridline-color: #E0E0E0;
            alternate-background-color: #FAF7F6;
        }}

        QTableWidget::item {{
            padding: 5px;
        }}

        QTableWidget::item:selected {{
            background-color: {self.accent_color};
            color: white;
        }}

        QTableWidget::item:hover {{
            background-color: #F2E3E1;
        }}

        QHeaderView::section {{
            background-color: {self.primary_color};
            color: white;
            padding: 8px;
            border: none;
            font-weight: bold;
        }}

        QTextEdit {{
            border: 2px solid {self.accent_color};
            border-radius: 6px;
            padding: 8px;
            background-color: white;
        }}

        QTextEdit:focus {{
            border: 2px solid {self.primary_color};
        }}

        QTabWidget::pane {{
            border: 2px solid {self.accent_color};
            top: -1px;
            border-radius: 6px;
            background-color: white;
        }}

        QTabBar::tab {{
            background: #E8E0DF;
            border: 1px solid {self.accent_color};
            padding: 8px 20px;
            margin-right: 4px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}

        QTabBar::tab:selected {{
            background: {self.primary_color};
            color: white;
            border-bottom-color: {self.primary_color};
        }}

        QTabBar::tab:hover {{
            background: {self.secondary_color};
            color: white;
        }}

        QLabel {{
            color: {self.text_color};
        }}

        QFrame[frameShape="4"] {{
            color: {self.accent_color};
        }}

        QSplitter::handle {{
            background: {self.accent_color};
        }}
        """
        self.setStyleSheet(stylesheet)

    def _init_ui(self):
        """Configure l'interface utilisateur"""
        # Disposition principale
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # En-tête avec logo
        header_layout = QtWidgets.QHBoxLayout()

        # Logo
        logo_label = QtWidgets.QLabel()
        logo_path = os.path.join("ui", "resources", "icons", "logo")
        if os.path.exists(logo_path):
            pixmap = QtGui.QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        header_layout.addWidget(logo_label)

        # Titre
        self.title_label = QtWidgets.QLabel(tr("history.title"))
        self.title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {self.primary_color};
            margin-left: 10px;
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Barre d'outils
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setSpacing(10)

        self.refresh_button = QtWidgets.QPushButton(tr("history.refresh"))
        self.refresh_button.clicked.connect(self.refresh_list)
        toolbar_layout.addWidget(self.refresh_button)

        self.delete_button = QtWidgets.QPushButton(tr("history.delete"))
        self.delete_button.clicked.connect(self._on_delete)
        self.delete_button.setEnabled(False)
        toolbar_layout.addWidget(self.delete_button)

        self.export_button = QtWidgets.QPushButton(tr("history.export"))
        self.export_button.clicked.connect(self._on_export)
        self.export_button.setEnabled(False)
        toolbar_layout.addWidget(self.export_button)

        # Filtre par plateforme
        self.platform_label = QtWidgets.QLabel(tr("history.platform"))
        self.platform_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.platform_label)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.addItem(tr("history.all"), "")
        self.platform_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.platform_combo)

        # Filtre par type
        self.type_label = QtWidgets.QLabel(tr("history.type"))
        self.type_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.type_label)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem(tr("history.all"), "")
        self.type_combo.addItem(tr("history.standard"), "standard")
        self.type_combo.addItem(tr("history.analyze"), "analyze")
        self.type_combo.addItem(tr("history.generate"), "generate")
        self.type_combo.addItem(tr("history.brainstorm"), "brainstorm")
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.type_combo)

        # Recherche
        self.search_label = QtWidgets.QLabel(tr("history.search"))
        self.search_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.search_label)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(tr("history.search_placeholder"))
        self.search_edit.textChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.search_edit)

        # Ajouter la barre d'outils
        main_layout.addLayout(toolbar_layout)

        # Séparateur
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(line)

        # Splitter principal
        splitter = QtWidgets.QSplitter(Qt.Vertical)
        splitter.setHandleWidth(3)
        main_layout.addWidget(splitter)

        # Liste des prompts
        list_widget = QtWidgets.QWidget()
        list_widget.setStyleSheet("background-color: transparent;")
        list_layout = QtWidgets.QVBoxLayout(list_widget)
        list_layout.setSpacing(10)

        # Tableau des prompts
        self.prompts_table = QtWidgets.QTableWidget()
        self.prompts_table.setColumnCount(5)
        self.prompts_table.setHorizontalHeaderLabels([
            tr("history.id"),
            tr("history.date"),
            tr("history.platform"),
            tr("history.type"),
            tr("history.content")
        ])
        self.prompts_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.prompts_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.prompts_table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.prompts_table.verticalHeader().setVisible(False)
        self.prompts_table.setAlternatingRowColors(True)

        # Connexion de la sélection
        self.prompts_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.prompts_table.cellDoubleClicked.connect(self._on_prompt_double_clicked)

        list_layout.addWidget(self.prompts_table)

        # Détail du prompt
        detail_widget = QtWidgets.QWidget()
        detail_widget.setStyleSheet("background-color: transparent;")
        detail_layout = QtWidgets.QVBoxLayout(detail_widget)
        detail_layout.setSpacing(10)

        # Tabs pour prompt et réponse
        self.detail_tabs = QtWidgets.QTabWidget()

        # Onglet prompt
        prompt_tab = QtWidgets.QWidget()
        prompt_layout = QtWidgets.QVBoxLayout(prompt_tab)

        self.prompt_edit = QtWidgets.QTextEdit()
        self.prompt_edit.setReadOnly(True)
        prompt_layout.addWidget(self.prompt_edit)

        self.detail_tabs.addTab(prompt_tab, tr("history.prompt"))

        # Onglet réponse
        response_tab = QtWidgets.QWidget()
        response_layout = QtWidgets.QVBoxLayout(response_tab)

        self.response_edit = QtWidgets.QTextEdit()
        self.response_edit.setReadOnly(True)
        response_layout.addWidget(self.response_edit)

        self.detail_tabs.addTab(response_tab, tr("history.response"))

        # Onglet métadonnées
        metadata_tab = QtWidgets.QWidget()
        metadata_layout = QtWidgets.QVBoxLayout(metadata_tab)

        self.metadata_table = QtWidgets.QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels([
            tr("history.property"),
            tr("history.value")
        ])
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.metadata_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.metadata_table.verticalHeader().setVisible(False)
        metadata_layout.addWidget(self.metadata_table)

        self.detail_tabs.addTab(metadata_tab, tr("history.metadata"))

        detail_layout.addWidget(self.detail_tabs)

        # Ajouter les widgets au splitter
        splitter.addWidget(list_widget)
        splitter.addWidget(detail_widget)

        # Définir les tailles initiales
        splitter.setSizes([400, 300])

        # Statut
        status_layout = QtWidgets.QHBoxLayout()

        self.status_label = QtWidgets.QLabel(tr("history.status_ready"))
        self.status_label.setStyleSheet(f"color: {self.primary_color}; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        self.count_label = QtWidgets.QLabel(tr("history.count", count=0))
        self.count_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.count_label)

        main_layout.addLayout(status_layout)

    def set_database(self, database):
        """
        Définit la connexion à la base de données

        Args:
            database: Instance de la base de données
        """
        self.database = database

    def update_status(self, message):
        """
        Met à jour le statut

        Args:
            message (str): Message de statut
        """
        self.status_label.setText(message)

    def refresh_list(self):
        """Actualise la liste des prompts"""
        # Vérifier la disponibilité de la base de données
        if not self.database:
            self.update_status(tr("history.database_unavailable"))
            return

        try:
            # Effacer la sélection actuelle
            self.current_prompt_id = None
            self.prompts_table.clearSelection()
            self.prompt_edit.clear()
            self.response_edit.clear()
            self.metadata_table.setRowCount(0)

            # Effacer le tableau
            self.prompts_table.setRowCount(0)

            # Récupérer les filtres
            platform = self.platform_combo.currentData()
            prompt_type = self.type_combo.currentData()
            search_text = self.search_edit.text()

            # Récupérer la liste des prompts
            prompts = None
            # prompts = self.database.get_prompts(
            #     platform=platform if platform else None,
            #     operation_type=prompt_type if prompt_type else None,
            #     search=search_text if search_text else None,
            #     limit=1000  # Limiter le nombre de résultats
            # )

            if not prompts:
                self.update_status(tr("history.no_prompts_found"))
                self.count_label.setText(tr("history.count", count=0))
                return

            # Mettre à jour les plateformes disponibles
            self._update_platforms(prompts)

            # Remplir le tableau
            for prompt in prompts:
                # Ajouter une ligne
                row = self.prompts_table.rowCount()
                self.prompts_table.insertRow(row)

                # ID
                id_item = QtWidgets.QTableWidgetItem(str(prompt.get('id', '')))
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                self.prompts_table.setItem(row, 0, id_item)

                # Date
                timestamp = prompt.get('timestamp', '')
                date_str = ""

                if timestamp:
                    try:
                        date = datetime.fromisoformat(timestamp)
                        date_str = date.strftime('%d/%m/%Y %H:%M')
                    except:
                        date_str = timestamp

                date_item = QtWidgets.QTableWidgetItem(date_str)
                date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
                self.prompts_table.setItem(row, 1, date_item)

                # Plateforme
                platform_item = QtWidgets.QTableWidgetItem(prompt.get('platform', ''))
                platform_item.setFlags(platform_item.flags() & ~Qt.ItemIsEditable)
                self.prompts_table.setItem(row, 2, platform_item)

                # Type
                type_item = QtWidgets.QTableWidgetItem(prompt.get('operation_type', ''))
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                self.prompts_table.setItem(row, 3, type_item)

                # Contenu (aperçu)
                content = prompt.get('content', '')
                preview = content[:50].replace('\n', ' ')
                if len(content) > 50:
                    preview += "..."

                content_item = QtWidgets.QTableWidgetItem(preview)
                content_item.setFlags(content_item.flags() & ~Qt.ItemIsEditable)
                content_item.setToolTip(content[:200] + "..." if len(content) > 200 else content)
                self.prompts_table.setItem(row, 4, content_item)

            # Mettre à jour le statut
            count = self.prompts_table.rowCount()
            self.update_status(tr("history.prompts_displayed", count=count))
            self.count_label.setText(tr("history.count", count=count))

        except Exception as e:
            logger.error(f"Erreur lors de l'actualisation de la liste: {str(e)}")
            self.update_status(tr("history.error", error=str(e)))

    def _update_platforms(self, prompts):
        """
        Met à jour la liste des plateformes disponibles

        Args:
            prompts (list): Liste des prompts
        """
        # Sauvegarder la sélection actuelle
        current_platform = self.platform_combo.currentData()

        # Récupérer toutes les plateformes uniques
        platforms = set()

        for prompt in prompts:
            platform = prompt.get('platform', '')
            if platform:
                platforms.add(platform)

        # Mettre à jour le combo
        self.platform_combo.clear()
        self.platform_combo.addItem(tr("history.all"), "")

        for platform in sorted(platforms):
            self.platform_combo.addItem(platform, platform)

        # Restaurer la sélection si possible
        if current_platform:
            index = self.platform_combo.findData(current_platform)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_filter_changed(self):
        """Gère le changement des filtres"""
        self.refresh_list()

    def _on_selection_changed(self):
        """Gère le changement de sélection"""
        # Récupérer les indices sélectionnés
        selected_rows = self.prompts_table.selectionModel().selectedRows()

        if not selected_rows:
            # Aucune sélection
            self.current_prompt_id = None
            self.prompt_edit.clear()
            self.response_edit.clear()
            self.metadata_table.setRowCount(0)
            self.delete_button.setEnabled(False)
            self.export_button.setEnabled(False)
            return

        # Récupérer l'ID du prompt sélectionné
        row = selected_rows[0].row()
        id_item = self.prompts_table.item(row, 0)

        if not id_item:
            return

        prompt_id = int(id_item.text())
        self.current_prompt_id = prompt_id

        # Activer les boutons
        self.delete_button.setEnabled(True)
        self.export_button.setEnabled(True)

        # Charger les détails
        self._load_prompt_details(prompt_id)

        # Émettre le signal
        self.prompt_selected.emit(prompt_id)

    def _load_prompt_details(self, prompt_id):
        """
        Charge les détails d'un prompt

        Args:
            prompt_id (int): ID du prompt
        """
        # Vérifier la disponibilité de la base de données
        if not self.database:
            return

        try:
            # Récupérer les informations
            prompt = self.database.get_prompt(prompt_id)

            if not prompt:
                return

            # Mettre à jour les onglets
            self.prompt_edit.setPlainText(prompt.get('content', ''))
            self.response_edit.setPlainText(prompt.get('response', ''))

            # Mettre à jour les métadonnées
            self.metadata_table.setRowCount(0)

            # Ajouter les métadonnées
            metadata = [
                (tr("history.id"), prompt.get('id', '')),
                (tr("history.session"), prompt.get('session_id', '')),
                (tr("history.platform"), prompt.get('platform', '')),
                (tr("history.type"), prompt.get('operation_type', '')),
                (tr("history.tokens"), prompt.get('token_count', '')),
                (tr("history.date"), prompt.get('timestamp', '')),
                (tr("history.status"), prompt.get('status', ''))
            ]

            # Ajouter des métadonnées supplémentaires
            for key, value in prompt.items():
                if key not in ['id', 'session_id', 'platform', 'operation_type',
                               'token_count', 'timestamp', 'status', 'content', 'response']:
                    metadata.append((key, value))

            # Remplir le tableau
            for key, value in metadata:
                row = self.metadata_table.rowCount()
                self.metadata_table.insertRow(row)

                # Clé
                key_item = QtWidgets.QTableWidgetItem(str(key))
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                self.metadata_table.setItem(row, 0, key_item)

                # Valeur
                value_item = QtWidgets.QTableWidgetItem(str(value))
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                self.metadata_table.setItem(row, 1, value_item)

            # Ajuster les lignes
            self.metadata_table.resizeRowsToContents()

        except Exception as e:
            logger.error(f"Erreur lors du chargement des détails: {str(e)}")

    def _on_prompt_double_clicked(self, row, column):
        """
        Gère le double-clic sur un prompt

        Args:
            row (int): Index de ligne
            column (int): Index de colonne
        """
        # Vérifier si un prompt est sélectionné
        if not self.current_prompt_id:
            return

        # Afficher une boîte de dialogue avec les détails
        try:
            # Récupérer les informations
            prompt = self.database.get_prompt(self.current_prompt_id)

            if not prompt:
                return

            # Créer une boîte de dialogue
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(tr("history.dialog_title", id=self.current_prompt_id))
            dialog.resize(900, 700)

            # Style pour la dialog
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {self.background_color};
                }}
                QLabel {{
                    color: {self.text_color};
                }}
                QPushButton {{
                    background-color: {self.primary_color};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background-color: {self.secondary_color};
                }}
            """)

            # Disposition
            layout = QtWidgets.QVBoxLayout(dialog)

            # Titre
            title_label = QtWidgets.QLabel(tr("history.dialog_header",
                                              id=self.current_prompt_id,
                                              platform=prompt.get('platform')))
            title_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 16px;
                color: {self.primary_color};
                margin-bottom: 10px;
            """)
            layout.addWidget(title_label)

            # Info
            info_layout = QtWidgets.QHBoxLayout()

            info_label = QtWidgets.QLabel(tr("history.info_line",
                                             type=prompt.get('operation_type', ''),
                                             date=prompt.get('timestamp', ''),
                                             tokens=prompt.get('token_count', '')
                                             ))
            info_layout.addWidget(info_label)

            layout.addLayout(info_layout)

            # Séparateur
            line = QtWidgets.QFrame()
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            layout.addWidget(line)

            # Contenu et réponse dans un splitter
            splitter = QtWidgets.QSplitter(Qt.Vertical)
            splitter.setHandleWidth(3)
            layout.addWidget(splitter)

            # Contenu
            content_widget = QtWidgets.QWidget()
            content_layout = QtWidgets.QVBoxLayout(content_widget)

            content_label = QtWidgets.QLabel(tr("history.content_label"))
            content_label.setStyleSheet(f"font-weight: bold; color: {self.primary_color};")
            content_layout.addWidget(content_label)

            content_edit = QtWidgets.QTextEdit()
            content_edit.setPlainText(prompt.get('content', ''))
            content_edit.setReadOnly(True)
            content_layout.addWidget(content_edit)

            splitter.addWidget(content_widget)

            # Réponse
            response_widget = QtWidgets.QWidget()
            response_layout = QtWidgets.QVBoxLayout(response_widget)

            response_label = QtWidgets.QLabel(tr("history.response_label"))
            response_label.setStyleSheet(f"font-weight: bold; color: {self.primary_color};")
            response_layout.addWidget(response_label)

            response_edit = QtWidgets.QTextEdit()
            response_edit.setPlainText(prompt.get('response', ''))
            response_edit.setReadOnly(True)
            response_layout.addWidget(response_edit)

            splitter.addWidget(response_widget)

            # Définir les tailles initiales
            splitter.setSizes([300, 400])

            # Boutons
            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Close
            )
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            # Afficher la boîte de dialogue
            dialog.exec_()

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage des détails: {str(e)}")

    def _on_delete(self):
        """Gère l'action de suppression"""
        # Vérifier si un prompt est sélectionné
        if not self.current_prompt_id:
            return

        # Confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            tr("history.confirm_delete"),
            tr("history.confirm_delete_message", id=self.current_prompt_id),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Supprimer le prompt
            success = self.database.delete_prompt(self.current_prompt_id)

            if not success:
                raise Exception(tr("history.deletion_failed", id=self.current_prompt_id))

            # Émettre le signal
            prompt_id = self.current_prompt_id
            self.prompt_deleted.emit(prompt_id)

            # Mettre à jour la liste
            self.refresh_list()

            # Mettre à jour le statut
            self.update_status(tr("history.prompt_deleted", id=prompt_id))

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du prompt: {str(e)}")

            # Message d'erreur
            QtWidgets.QMessageBox.critical(
                self,
                tr("history.deletion_error"),
                tr("history.deletion_error_message", error=str(e))
            )

    def _on_export(self):
        """Gère l'action d'exportation"""
        # Vérifier si un prompt est sélectionné
        if not self.current_prompt_id:
            return

        try:
            # Récupérer les informations
            prompt = self.database.get_prompt(self.current_prompt_id)

            if not prompt:
                raise Exception(tr("history.prompt_not_found", id=self.current_prompt_id))

            # Ouvrir un sélecteur de fichier
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                tr("history.export_prompt"),
                os.path.expanduser(f"~/prompt_{self.current_prompt_id}.json"),
                tr("history.export_file_filter")
            )

            if not file_path:
                return

            # Déterminer le format
            is_json = file_path.lower().endswith('.json')

            if is_json:
                # Export JSON
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(prompt, f, ensure_ascii=False, indent=2)
            else:
                # Export texte
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(tr("history.export_prompt_header", id=prompt.get('id', '')) + "\n")
                    f.write(f"{'=' * 80}\n")
                    f.write(tr("history.export_platform", platform=prompt.get('platform', '')) + "\n")
                    f.write(tr("history.export_type", type=prompt.get('operation_type', '')) + "\n")
                    f.write(tr("history.export_date", date=prompt.get('timestamp', '')) + "\n")
                    f.write(f"{'=' * 80}\n\n")

                    f.write(tr("history.export_content") + "\n")
                    f.write(f"{'-' * 80}\n")
                    f.write(prompt.get('content', '') + "\n\n")

                    f.write(tr("history.export_response") + "\n")
                    f.write(f"{'-' * 80}\n")
                    f.write(prompt.get('response', ''))

            # Mettre à jour le statut
            self.update_status(tr("history.prompt_exported",
                                  id=self.current_prompt_id,
                                  file=os.path.basename(file_path)))

        except Exception as e:
            logger.error(f"Erreur lors de l'exportation du prompt: {str(e)}")

            # Message d'erreur
            QtWidgets.QMessageBox.critical(
                self,
                tr("history.export_error"),
                tr("history.export_error_message", error=str(e))
            )

    def export_history(self):
        """Exporte l'historique complet des prompts"""
        # Vérifier la disponibilité de la base de données
        if not self.database:
            QtWidgets.QMessageBox.warning(
                self,
                tr("history.database_unavailable"),
                tr("history.database_unavailable_message")
            )
            return

        try:
            # Récupérer les filtres actuels
            platform = self.platform_combo.currentData()
            prompt_type = self.type_combo.currentData()
            search_text = self.search_edit.text()

            # Récupérer les prompts (avec les filtres actuels)
            prompts = None
            # prompts = self.database.get_prompts(
            #     platform=platform if platform else None,
            #     operation_type=prompt_type if prompt_type else None,
            #     search=search_text if search_text else None
            # )

            if not prompts:
                QtWidgets.QMessageBox.information(
                    self,
                    tr("history.no_prompt"),
                    tr("history.no_prompt_message")
                )
                return

            # Ouvrir un sélecteur de fichier
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                tr("history.export_history"),
                os.path.expanduser(f"~/historique_prompts_{datetime.now().strftime('%Y%m%d')}.json"),
                tr("history.export_history_filter")
            )

            if not file_path:
                return

            # Déterminer le format
            if file_path.lower().endswith('.json'):
                # Export JSON
                import json

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(prompts, f, ensure_ascii=False, indent=2)

            elif file_path.lower().endswith('.csv'):
                # Export CSV
                import csv

                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)

                    # En-têtes
                    writer.writerow([
                        tr("history.id"),
                        tr("history.session"),
                        tr("history.platform"),
                        tr("history.type"),
                        tr("history.date"),
                        tr("history.tokens"),
                        tr("history.status"),
                        tr("history.content"),
                        tr("history.response")
                    ])

                    # Données
                    for prompt in prompts:
                        writer.writerow([
                            prompt.get('id', ''),
                            prompt.get('session_id', ''),
                            prompt.get('platform', ''),
                            prompt.get('operation_type', ''),
                            prompt.get('timestamp', ''),
                            prompt.get('token_count', ''),
                            prompt.get('status', ''),
                            prompt.get('content', '')[:1000],  # Limiter la taille
                            prompt.get('response', '')[:1000]  # Limiter la taille
                        ])

            else:
                # Export texte
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(tr("history.history_header") + "\n")
                    f.write(tr("history.export_date_line", date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n\n")

                    # Filtres appliqués
                    f.write(tr("history.applied_filters") + "\n")
                    if platform:
                        f.write(tr("history.filter_platform", platform=platform) + "\n")
                    if prompt_type:
                        f.write(tr("history.filter_type", type=prompt_type) + "\n")
                    if search_text:
                        f.write(tr("history.filter_search", search=search_text) + "\n")
                    f.write(tr("history.total_count", count=len(prompts)) + "\n\n")

                    # Prompts
                    for prompt in prompts:
                        f.write(tr("history.export_prompt_header", id=prompt.get('id', '')) + "\n")
                        f.write(f"{'=' * 80}\n")
                        f.write(tr("history.export_platform", platform=prompt.get('platform', '')) + "\n")
                        f.write(tr("history.export_type", type=prompt.get('operation_type', '')) + "\n")
                        f.write(tr("history.export_date", date=prompt.get('timestamp', '')) + "\n")
                        f.write(f"{'=' * 80}\n\n")

                        f.write(tr("history.export_content") + "\n")
                        f.write(f"{'-' * 80}\n")
                        f.write(prompt.get('content', '') + "\n\n")

                        f.write(tr("history.export_response") + "\n")
                        f.write(f"{'-' * 80}\n")
                        f.write(prompt.get('response', '') + "\n\n")
                        f.write(f"{'=' * 80}\n\n")

            # Mettre à jour le statut
            self.update_status(tr("history.history_exported",
                                  count=len(prompts),
                                  file=os.path.basename(file_path)))

            # Message de confirmation
            QtWidgets.QMessageBox.information(
                self,
                tr("history.export_success"),
                tr("history.export_success_message", file=file_path)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'exportation de l'historique: {str(e)}")

            # Message d'erreur
            QtWidgets.QMessageBox.critical(
                self,
                tr("history.export_error"),
                tr("history.export_error_message", error=str(e))
            )

    def update_language(self):
        """Met à jour tous les textes après un changement de langue"""
        # Mettre à jour le titre
        self.title_label.setText(tr("history.title"))

        # Mettre à jour les boutons
        self.refresh_button.setText(tr("history.refresh"))
        self.delete_button.setText(tr("history.delete"))
        self.export_button.setText(tr("history.export"))

        # Mettre à jour les labels
        self.platform_label.setText(tr("history.platform"))
        self.type_label.setText(tr("history.type"))
        self.search_label.setText(tr("history.search"))
        self.search_edit.setPlaceholderText(tr("history.search_placeholder"))

        # Mettre à jour les en-têtes du tableau
        self.prompts_table.setHorizontalHeaderLabels([
            tr("history.id"),
            tr("history.date"),
            tr("history.platform"),
            tr("history.type"),
            tr("history.content")
        ])

        # Mettre à jour les onglets
        self.detail_tabs.setTabText(0, tr("history.prompt"))
        self.detail_tabs.setTabText(1, tr("history.response"))
        self.detail_tabs.setTabText(2, tr("history.metadata"))

        # Mettre à jour les en-têtes du tableau de métadonnées
        self.metadata_table.setHorizontalHeaderLabels([
            tr("history.property"),
            tr("history.value")
        ])

        # Mettre à jour le statut
        self.status_label.setText(tr("history.status_ready"))
        self.count_label.setText(tr("history.count", count=0))

        # Mettre à jour le combo des types
        current_type_index = self.type_combo.currentIndex()
        self.type_combo.setItemText(0, tr("history.all"))
        self.type_combo.setItemText(1, tr("history.standard"))
        self.type_combo.setItemText(2, tr("history.analyze"))
        self.type_combo.setItemText(3, tr("history.generate"))
        self.type_combo.setItemText(4, tr("history.brainstorm"))

        # Mettre à jour le combo des plateformes
        current_platform_index = self.platform_combo.currentIndex()
        if self.platform_combo.count() > 0:
            self.platform_combo.setItemText(0, tr("history.all"))