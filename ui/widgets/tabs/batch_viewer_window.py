#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
import qtawesome as qta
from ui.styles.theme import Theme


class BatchViewerWindow(QtWidgets.QDialog):
    """
    Fenêtre modale moderne pour visualiser les éléments du batch
    avec panneau de détails rétractable
    """
    
    def __init__(self, batch_data, parent=None):
        super().__init__(parent)
        self.batch_data = batch_data
        self.combinations = batch_data.get('combinations', [])
        self.selected_combination = None
        self.details_visible = False
        
        self.primary_color = Theme.PRIMARY_COLOR
        self.secondary_color = Theme.SECONDARY_COLOR
        
        self._init_ui()
        self._load_combinations()
        
    def _init_ui(self):
        """Interface avec panneau de détails rétractable"""
        self.setWindowTitle(f"Batch: {self.batch_data.get('batch_name', 'Sans nom')}")
        self.setModal(True)
        
        # Dimensions responsives
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        width = min(1000, int(screen_size.width() * 0.65))
        height = min(700, int(screen_size.height() * 0.7))
        self.resize(width, height)
        
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # ===== EN-TÊTE =====
        header = self._create_header()
        main_layout.addWidget(header)
        
        # ===== CONTENU PRINCIPAL =====
        content_container = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_container)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(15, 15, 15, 15)
        
        # Liste des combinaisons
        self.combinations_widget = self._create_combinations_list()
        content_layout.addWidget(self.combinations_widget, 1)
        
        # ===== PANNEAU DE DÉTAILS (superposé, caché par défaut) =====
        self.details_panel = self._create_details_panel()
        self.details_panel.setParent(content_container)
        self.details_panel.setFixedWidth(0)
        self.details_panel.hide()
        
        # ===== BOUTON TOGGLE DÉTAILS =====
        self.toggle_details_button = self._create_toggle_button()
        self.toggle_details_button.setParent(content_container)
        
        main_layout.addWidget(content_container)
        
        # ===== PIED DE PAGE =====
        footer = self._create_footer()
        main_layout.addWidget(footer)
        
        # Style global
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #f5f6f8;
            }}
        """)
        
    def _create_header(self):
        """En-tête avec informations du batch - version compacte"""
        header = QtWidgets.QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                border-bottom: 2px solid #D0D0D0;
            }}
        """)
        header.setFixedHeight(85)
        
        layout = QtWidgets.QVBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(6)
        
        # Titre + Badge
        title_layout = QtWidgets.QHBoxLayout()
        
        title = QtWidgets.QLabel(self.batch_data.get('batch_name', 'Batch sans nom'))
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: white;
            background: transparent;
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # Badge compteur
        count_badge = QtWidgets.QLabel(f"{len(self.combinations)}")
        count_badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.25);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.3);
        """)
        title_layout.addWidget(count_badge)
        
        layout.addLayout(title_layout)
        
        # Informations secondaires
        info_layout = QtWidgets.QHBoxLayout()
        
        project = self.batch_data.get('project_name', 'N/A')
        project_label = QtWidgets.QLabel(f"Projet: {project}")
        project_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9);
            font-size: 11px;
            background: transparent;
        """)
        info_layout.addWidget(project_label)
        
        family = self.batch_data.get('batch_family', '').strip()
        if family:
            info_layout.addSpacing(20)
            family_label = QtWidgets.QLabel(f"• {family}")
            family_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.9);
                font-size: 11px;
                background: transparent;
            """)
            info_layout.addWidget(family_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # Description (si présente)
        description = self.batch_data.get('description', '').strip()
        if description:
            desc_label = QtWidgets.QLabel(description[:70] + "..." if len(description) > 70 else description)
            desc_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.85);
                font-size: 10px;
                font-style: italic;
                background: transparent;
            """)
            layout.addWidget(desc_label)
        
        return header
        
    def _create_combinations_list(self):
        """Widget principal avec la liste des combinaisons"""
        group = QtWidgets.QGroupBox("Combinaisons générées")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 13px;
                color: {self.primary_color};
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: white;
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        
        # Barre de recherche - simple et compacte
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher dans les combinaisons...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: #fafafa;
                font-size: 11px;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 1px solid #2c3e50;
                background-color: white;
            }
        """)
        self.search_edit.setFixedHeight(28)
        self.search_edit.textChanged.connect(self._filter_combinations)
        layout.addWidget(self.search_edit)
        
        # Liste des combinaisons - plus compacte
        self.combinations_list = QtWidgets.QListWidget()
        self.combinations_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                background-color: #fafbfc;
                padding: 4px;
                font-size: 11px;
                color: #2c3e50;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin: 2px 0;
                background-color: white;
                border: 1px solid #e8eaed;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
                border: 1px solid #1976d2;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
            }
        """)
        self.combinations_list.itemClicked.connect(self._on_combination_selected)
        self.combinations_list.itemDoubleClicked.connect(self._on_combination_double_clicked)
        
        layout.addWidget(self.combinations_list)
        
        # Info tooltip - plus discrète
        info_label = QtWidgets.QLabel("Double-clic pour voir les détails")
        info_label.setStyleSheet("""
            color: #95a5a6;
            font-size: 9px;
            font-style: italic;
            padding: 3px 5px;
            background: transparent;
        """)
        layout.addWidget(info_label)
        
        return group
        
    def _create_details_panel(self):
        """Panneau de détails rétractable - version compacte"""
        panel = QtWidgets.QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.98);
                border-left: 2px solid #D0D0D0;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # En-tête du panneau
        header_title = QtWidgets.QLabel("Détails de la combinaison")
        header_title.setStyleSheet("""
            font-size: 13px;
            font-weight: 600;
            color: #333;
            background-color: transparent;
        """)
        layout.addWidget(header_title)
        
        # Zone scrollable pour les détails
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.details_content = QtWidgets.QWidget()
        self.details_layout = QtWidgets.QVBoxLayout(self.details_content)
        self.details_layout.setSpacing(10)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area.setWidget(self.details_content)
        layout.addWidget(scroll_area)
        
        return panel
        
    def _create_toggle_button(self):
        """Bouton compact pour afficher/masquer le panneau de détails"""
        button = QtWidgets.QWidget()
        button.setMinimumSize(32, 80)
        button.setMaximumSize(32, 120)
        button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        button.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                border: none;
                border-radius: 6px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QWidget:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """)
        
        button_layout = QtWidgets.QVBoxLayout(button)
        button_layout.setContentsMargins(0, 10, 0, 10)
        button_layout.setSpacing(6)
        button_layout.setAlignment(Qt.AlignCenter)
        
        # Icône chevron
        self.chevron_icon = QtWidgets.QLabel()
        self.chevron_icon.setAlignment(Qt.AlignCenter)
        self.chevron_icon.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(14, 14))
        button_layout.addWidget(self.chevron_icon)
        
        # Texte vertical compact
        text = QtWidgets.QLabel("I\nN\nF\nO")
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 8px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
            }
        """)
        button_layout.addWidget(text)
        
        button.mousePressEvent = lambda event: self._toggle_details_panel()
        button.hide()
        
        return button
        
    def _create_footer(self):
        """Pied de page avec boutons d'action - version compacte"""
        footer = QtWidgets.QWidget()
        footer.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 1px solid #e1e4e8;
            }
        """)
        footer.setFixedHeight(60)
        
        layout = QtWidgets.QHBoxLayout(footer)
        layout.setContentsMargins(20, 12, 20, 12)
        
        # Statistiques
        stats_label = QtWidgets.QLabel(f"Total: {len(self.combinations)} combinaison(s)")
        stats_label.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #555;
        """)
        layout.addWidget(stats_label)
        
        layout.addStretch()
        
        # Bouton Export
        export_btn = QtWidgets.QPushButton("Exporter")
        export_btn.setIcon(qta.icon('fa5s.file-export', color='white'))
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.primary_color}, 
                    stop:1 {self.secondary_color});
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 11px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.secondary_color}, 
                    stop:1 {self.primary_color});
            }}
        """)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export_batch)
        layout.addWidget(export_btn)
        
        # Bouton Fermer
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.setIcon(qta.icon('fa5s.times', color='#666'))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border: 1px solid #b0b0b0;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        return footer
        
    def _load_combinations(self):
        """Charger les combinaisons dans la liste"""
        self.combinations_list.clear()
        
        for idx, combo in enumerate(self.combinations):
            display = combo.get('display', f"Combinaison {idx + 1}")
            item = QtWidgets.QListWidgetItem(f"#{idx + 1} • {display}")
            item.setData(Qt.UserRole, combo)
            self.combinations_list.addItem(item)
            
    def _filter_combinations(self, text):
        """Filtrer les combinaisons selon le texte de recherche"""
        search_text = text.lower().strip()
        
        for i in range(self.combinations_list.count()):
            item = self.combinations_list.item(i)
            item_text = item.text().lower()
            item.setHidden(search_text not in item_text)
            
    def _on_combination_selected(self, item):
        """Sélection simple d'une combinaison"""
        self.selected_combination = item.data(Qt.UserRole)
        self.toggle_details_button.show()
        
    def _on_combination_double_clicked(self, item):
        """Double-clic pour afficher les détails"""
        self.selected_combination = item.data(Qt.UserRole)
        self.toggle_details_button.show()
        
        if not self.details_visible:
            self._toggle_details_panel()
        else:
            self._update_details_content()
            
    def _toggle_details_panel(self):
        """Afficher/masquer le panneau de détails avec animation"""
        if not self.selected_combination:
            return
            
        target_width = 350 if not self.details_visible else 0
        
        # Animation
        self.animation = QtCore.QPropertyAnimation(self.details_panel, b"minimumWidth")
        self.animation.setDuration(250)
        self.animation.setStartValue(self.details_panel.width())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        
        if not self.details_visible:
            self.details_panel.show()
            self._update_details_content()
            self.chevron_icon.setPixmap(qta.icon('fa5s.chevron-right', color='white').pixmap(14, 14))
        else:
            self.animation.finished.connect(self.details_panel.hide)
            self.chevron_icon.setPixmap(qta.icon('fa5s.chevron-left', color='white').pixmap(14, 14))
            
        self.animation.start()
        self.details_visible = not self.details_visible
        
    def _update_details_content(self):
        """Mettre à jour le contenu des détails"""
        # Nettoyer le layout
        while self.details_layout.count():
            child = self.details_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if not self.selected_combination:
            return
            
        # Master
        master_data = self.selected_combination.get('master', {})
        master_card = self._create_detail_card(
            "Typologie Master",
            master_data.get('name', 'N/A'),
            "#e8f5e9"
        )
        self.details_layout.addWidget(master_card)
        
        # Context
        context = self.selected_combination.get('context', {})
        
        context_info = []
        if context.get('typologie'):
            context_info.append(f"Typologie: {context['typologie']}")
        if context.get('taxonomy'):
            context_info.append(f"Cluster: {context['taxonomy']}")
        if context.get('root'):
            context_info.append(f"Root: {context['root']}")
        if context.get('parent'):
            context_info.append(f"Parent: {context['parent']}")
        if context.get('child'):
            context_info.append(f"Child: {context['child']}")
            
        context_card = self._create_detail_card(
            "Contexte Combiné",
            "\n".join(context_info),
            "#e3f2fd"
        )
        self.details_layout.addWidget(context_card)
        
        # Niveau
        level_map = {
            'typologie': 'Typologie complète',
            'taxonomy': 'Cluster',
            'root': 'Label Racine',
            'parent': 'Label Parent',
            'child': 'Label Enfant'
        }
        level_card = self._create_detail_card(
            "Niveau",
            level_map.get(context.get('level', ''), 'N/A'),
            "#fff3e0"
        )
        self.details_layout.addWidget(level_card)
        
        self.details_layout.addStretch()
        
    def _create_detail_card(self, title, content, bg_color):
        """Créer une carte de détail compacte"""
        card = QtWidgets.QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 11px;
                color: #2c3e50;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: {bg_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: {bg_color};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        
        content_label = QtWidgets.QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet(f"""
            font-size: 10px;
            color: #2c3e50;
            background-color: transparent;
            padding: 6px;
            line-height: 1.4;
        """)
        layout.addWidget(content_label)
        
        return card
        
    def _export_batch(self):
        """Exporter le batch"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exporter le batch",
            f"{self.batch_data.get('batch_name', 'batch')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            import json
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.batch_data, f, indent=2, ensure_ascii=False)
                QtWidgets.QMessageBox.information(
                    self,
                    "Succès",
                    f"Batch exporté avec succès dans:\n{file_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de l'export:\n{str(e)}"
                )
                
    def resizeEvent(self, event):
        """Repositionner le bouton toggle lors du redimensionnement"""
        super().resizeEvent(event)
        if hasattr(self, 'toggle_details_button'):
            # Positionner le bouton à droite de la liste
            parent_width = self.combinations_widget.width()
            parent_x = self.combinations_widget.geometry().x()
            
            self.toggle_details_button.move(
                parent_x + parent_width - 32,
                70
            )
            
            # Positionner le panneau de détails
            if self.details_visible:
                self.details_panel.setGeometry(
                    parent_x + parent_width - 350,
                    0,
                    350,
                    self.combinations_widget.height()
                )