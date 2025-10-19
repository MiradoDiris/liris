import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import sqlite3
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout, QPlainTextEdit, QListWidgetItem, QHBoxLayout, QLabel, QComboBox, QPushButton, QInputDialog, QMessageBox
from collections import defaultdict
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from ui.localization.translator import tr
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.code_elements_popup import CodeElementsPopup
from utils.progress_dialog import ModernProgressDialog, SpinnerDialog
from utils.multi_language_parser import (
    MultiLanguageDependencyParser, 
    ProjectStructureScanner,
    normalize_node_name,
    is_supported_file
)


class AddEditItemDialog(QDialog):
    """
    Dialogue générique pour ajouter/éditer un item avec nom et description.
    """
    def __init__(self, title, current_name="", current_description="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 200)

        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Nom de l'item...")
        self.name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())

        self.description_edit = QTextEdit(current_description)
        self.description_edit.setPlaceholderText("Description de l'item...")
        self.description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.description_edit.setMaximumHeight(100)

        layout = QFormLayout(self)
        layout.addRow("Nom:", self.name_edit)
        layout.addRow("Description:", self.description_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip()
        }

class RelationsConfig(QtWidgets.QWidget):
    """
    Widget pour configurer les relations d'import pour un niveau de hiérarchie spécifique.
    Version corrigée avec logique source/target cohérente et affichage tableau.
    """
    def __init__(self, parent_widget, level="global"):
        super().__init__()
        self.parent_widget = parent_widget
        self.level = level
        self.show_hierarchy = True
        self.show_dependencies = True
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QtWidgets.QLabel(f"Relations {self.level.capitalize()}")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: black;
        """)
        layout.addWidget(title)

        # === SECTION FILTRAGE ===
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        relations_label = QtWidgets.QLabel("Filtres :")
        relations_label.setStyleSheet("color: black; font-weight: bold; font-size: 11px;")
        filter_layout.addWidget(relations_label)

        # Bouton Hiérarchie
        self.hierarchy_btn = QPushButton("Hiérarchie")
        self.hierarchy_btn.setCheckable(True)
        self.hierarchy_btn.setChecked(True)
        self.hierarchy_btn.setStyleSheet(self._get_filter_button_style())
        self.hierarchy_btn.clicked.connect(self._on_filter_hierarchy)
        filter_layout.addWidget(self.hierarchy_btn)

        # Bouton Dépendances
        self.dependencies_btn = QPushButton("Dépendances")
        self.dependencies_btn.setCheckable(True)
        self.dependencies_btn.setChecked(True)
        self.dependencies_btn.setStyleSheet(self._get_filter_button_style())
        self.dependencies_btn.clicked.connect(self._on_filter_dependencies)
        filter_layout.addWidget(self.dependencies_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # === AFFICHAGE SOURCE / TARGET ===
        info_layout = QHBoxLayout()
        info_layout.setSpacing(0)

        source_header = QLabel("Source: ")
        source_header.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #333;
        """)
        info_layout.addWidget(source_header)

        self.source_label = QLabel("")
        self.source_label.setStyleSheet("""
            color: #2196F3;
            font-weight: bold;
            font-size: 11px;
        """)
        info_layout.addWidget(self.source_label)

        info_layout.addStretch()

        target_header = QLabel("Target: ")
        target_header.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #333;
        """)
        info_layout.addWidget(target_header)

        self.target_label = QLabel("")
        self.target_label.setStyleSheet("""
            color: #4CAF50;
            font-weight: bold;
            font-size: 11px;
        """)
        info_layout.addWidget(self.target_label)

        layout.addLayout(info_layout)

        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet("background-color: #ccc; max-height: 1px;")
        layout.addWidget(separator)

        # === LISTE DES RELATIONS ===
        self.relations_list = QtWidgets.QListWidget()
        self.relations_list.setMaximumHeight(200)
        self.relations_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.relations_list.currentItemChanged.connect(self._on_relation_selected)
        self.relations_list.setStyleSheet("""
            QListWidget {
                background-color: #fafafa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 2px 0px;
                color: black;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: black;
                border: 1px solid #999;
            }
            QListWidget::item:hover {
                background-color: #ffffff;
                color: black;
            }
        """)
        layout.addWidget(self.relations_list)

        # === BOUTONS D'ACTION ===
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.add_button = QtWidgets.QPushButton("Nouvelle relation")
        self.add_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_button.setMaximumWidth(160)
        self.add_button.clicked.connect(self._on_add_new_relation)
        self.add_button.setEnabled(False)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QtWidgets.QPushButton(" Modifier")
        self.edit_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_button.setMaximumWidth(110)
        self.edit_button.clicked.connect(self._on_edit)
        self.edit_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QtWidgets.QPushButton("Supprimer")
        self.remove_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_button.setMaximumWidth(110)
        self.remove_button.clicked.connect(self._on_remove)
        self.remove_button.setEnabled(False)
        buttons_layout.addWidget(self.remove_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        layout.addStretch()

    def _get_filter_button_style(self):
        """Style pour les boutons de filtrage - gris clair avec texte noir."""
        return """
            QPushButton {
                background-color: #e8e8e8;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: normal;
            }
            QPushButton:checked {
                background-color: #b3d9ff;
                color: black;
                border: 1px solid #0066cc;
                font-weight: bold;
            }
            QPushButton:hover:!pressed {
                background-color: #ffffff;
                color: black;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """

    def _on_filter_hierarchy(self):
        """Toggle affichage relations hiérarchiques."""
        self.show_hierarchy = self.hierarchy_btn.isChecked()
        self._refresh_relations_list()

    def _on_filter_dependencies(self):
        """Toggle affichage relations de dépendances."""
        self.show_dependencies = self.dependencies_btn.isChecked()
        self._refresh_relations_list()

    def _refresh_relations_list(self):
        """Rafraîchit la liste avec les filtres appliqués."""
        if hasattr(self.parent_widget, 'current_selected_label_uid') and self.parent_widget.current_selected_label_uid:
            self._update_relations_list(self.parent_widget.current_selected_label_uid)

    def _on_relation_selected(self, current):
        """Gùre la sélection d'une relation pour afficher source/target."""
        if not current:
            self.source_label.clear()
            self.target_label.clear()
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return

        rel = current.data(Qt.UserRole)
        if not rel:
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return

        # Récupérer les infos source et target
        source_uid = rel.get('source')
        target_uid = rel.get('target')

        source_info = self.parent_widget.label_uid_to_info.get(source_uid, {})
        target_info = self.parent_widget.label_uid_to_info.get(target_uid, {})

        source_name = source_info.get('name', source_info.get('label', 'Inconnu'))
        target_name = target_info.get('name', target_info.get('label', 'Inconnu'))

        # Mettre à jour l'affichage
        self.source_label.setText(source_name)
        self.target_label.setText(target_name)

        # Activer boutons selon catégorie
        rel_category = rel.get('category', 'custom')
        if rel_category == 'hierarchy':
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)

    def update_current(self, source_uid):
        self.relations_list.clear()
        self.target_label.clear()
        self.edit_button.setEnabled(False)
        self.remove_button.setEnabled(False)

        if source_uid:
            source_info = self.parent_widget.label_uid_to_info.get(source_uid, {})
            source_name = source_info.get('name', source_info.get('label', ''))
            self.source_label.setText(source_name)

            # ✅ AJOUTER : Diagnostic
            self._diagnose_relations_display(source_uid)

            self._update_relations_list(source_uid)

            # Activer le bouton "Nouvelle relation" si au moins 2 nœuds existent
            if len(self.parent_widget.label_uid_to_info) > 1:
                self.add_button.setEnabled(True)
        else:
            self.source_label.clear()
            self.add_button.setEnabled(False)

    def _get_node_name(self, uid):
        """Récupère le nom d'un nœud par son UID avec fallback robuste."""
        if not uid:
            return ""
        
        # Chercher dans label_uid_to_info
        info = self.parent_widget.label_uid_to_info.get(uid)
        if info:
            name = info.get('name') or info.get('label')
            return name if name else ""
        
        # Fallback: chercher directement dans les nœuds
        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n.get('uid') == uid), None)
        if node:
            name = node.get('label') or node.get('name')
            return name if name else ""
        
        return ""

    def _on_edit(self):
        """Modifie une relation existante (change la target)."""
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        rel_category = rel.get('category', 'custom')
        
        # Ne pas permettre modification des relations hiérarchiques
        if rel_category == 'hierarchy':
            QtWidgets.QMessageBox.information(
                self, 
                "Info", 
                "Les relations hiérarchiques (parent/child) ne peuvent pas être modifiées."
            )
            return

        src_uid = rel['source']
        old_target_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        # Boîte de dialogue pour choisir une nouvelle cible
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == src_uid:
                continue
            name = info.get('name') or info.get('label', 'N/A')
            cluster = info.get('cluster', 'N/A')
            target_uids.append(uid)
            target_names.append(f"{name} ({cluster})")

        if not target_names:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune cible",
                "Aucun nœud disponible comme nouvelle cible."
            )
            return

        new_target_name, ok = QInputDialog.getItem(
            self, 
            "Modifier la relation",
            "Nouvelle cible:", 
            target_names, 
            0, 
            False
        )
        
        if ok and new_target_name:
            new_index = target_names.index(new_target_name)
            new_target_uid = target_uids[new_index]

            # Supprimer ancienne relation
            self.parent_widget._update_local_relations_remove(src_uid, old_target_uid, rel_type)
            old_rel = {"target_uid": old_target_uid, "relation_type": rel_type}
            if old_rel in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(old_rel)

            # Ajouter nouvelle relation
            new_rel = {"target_uid": new_target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[src_uid].append(new_rel)
            self.parent_widget._update_local_relations(src_uid, new_target_uid, rel_type)

            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation modifiée: {src_uid} → {new_target_uid}")

    def _on_remove(self):
        """Supprime une relation."""
        current_item = self.relations_list.currentItem()
        if not current_item:
            return

        rel = current_item.data(Qt.UserRole)
        rel_category = rel.get('category', 'custom')
        
        # Ne pas permettre suppression des relations hiérarchiques
        if rel_category == 'hierarchy':
            QtWidgets.QMessageBox.information(
                self,
                "Info",
                "Les relations hiérarchiques (parent/child) ne peuvent pas être supprimées."
            )
            return

        src_uid = rel['source']
        tgt_uid = rel['target']
        rel_type = rel.get('type', 'relation')

        reply = QtWidgets.QMessageBox.question(
            self, 
            "Supprimer", 
            "Voulez-vous vraiment supprimer cette relation?"
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.parent_widget._update_local_relations_remove(src_uid, tgt_uid, rel_type)
            rel_obj = {"target_uid": tgt_uid, "relation_type": rel_type}
            if rel_obj in self.parent_widget.pending_relations[src_uid]:
                self.parent_widget.pending_relations[src_uid].remove(rel_obj)
            
            self._update_relations_list(self.parent_widget.current_selected_label_uid)
            logger.info(f"Relation supprimée: {src_uid} → {tgt_uid}")

    def _update_relations_list(self, source_uid):
        self.relations_list.clear()
        if not source_uid:
            return

        # Initialiser mapping si nécessaire
        if not hasattr(self.parent_widget, 'dgraph_to_local'):
            self.parent_widget.dgraph_to_local = {}

        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()
        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n['uid'] == source_uid), None)

        if not node:
            logger.warning(f"Noeud {source_uid} non trouvé")
            return

        relations_added = {'custom': 0, 'parsed': 0, 'hierarchy': 0}
        seen_relations = set()  # Pour éviter les doublons

        # === 1. Relations sortantes CUSTOM + PARSED (depuis outgoing_relations) ===
        if self.show_dependencies:
            for r in node.get('outgoing_relations', []):
                target_uid = r.get('target_uid')

                if not target_uid or target_uid.startswith('temp_'):
                    continue
                
                # Mapper Dgraph UID si nécessaire
                if target_uid.startswith('0x') and len(target_uid) <= 10:
                    target_uid = dgraph_to_local.get(target_uid, target_uid)

                # ✅ CORRECTION : Gérer les UIDs non résolus
                if target_uid.startswith('unresolved_'):
                    target_name = r.get('target_name', 'Inconnu')
                    rel_type = r.get('relation_type', 'relation')
                    category = r.get('category', 'parsed')
                    line_info = f" (L{r.get('line', '?')})" if r.get('line') else ""

                    source_name = self._get_node_name(source_uid)
                    if not source_name:
                        continue
                    
                    display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} [NON RÉSOLU]"

                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, {
                        "category": "parsed_unresolved",
                        "direction": "out",
                        "source": source_uid,
                        "target": target_uid,
                        "target_name": target_name,
                        "type": rel_type,
                        "line": r.get('line', 0)
                    })
                    item.setForeground(QtGui.QColor("#95a5a6"))  # Gris pour non résolu
                    self.relations_list.addItem(item)
                    continue

                target_name = self._get_node_name(target_uid)
                if not target_name:
                    target_name = r.get('target_name', 'Inconnu')
                    if not target_name or target_name == 'Inconnu':
                        continue
                    
                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')

                # Créer clé unique pour détecter doublons
                rel_key = f"{source_uid}->{target_uid}:{rel_type}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                source_name = self._get_node_name(source_uid)
                if not source_name:
                    continue
                
                # Affichage selon catégorie
                line_info = f" (L{r.get('line', '?')})" if r.get('line') else ""
                if category == 'parsed':
                    display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} [CODE]"
                    color = "#FF9800"  # Orange pour parsé
                else:
                    display = f"{source_name} →[{rel_type}]→ {target_name}"
                    color = "#2196F3"  # Bleu pour custom

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": category,
                    "direction": "out",
                    "source": source_uid,
                    "target": target_uid,
                    "type": rel_type,
                    "line": r.get('line', 0)
                })

                item.setForeground(QtGui.QColor(color))
                self.relations_list.addItem(item)
                relations_added['custom' if category == 'custom' else 'parsed'] += 1

        # === 2. Relations PARSÉES depuis dict 'relations' (CORRIGÉ) ===
        if self.show_dependencies:
            parsed_relations = node.get('relations', {})
            if parsed_relations:
                logger.debug(f"📋 Relations dict trouvé pour {node.get('label')}: {list(parsed_relations.keys())}")

                for rel_type, rel_list in parsed_relations.items():
                    logger.debug(f"   Type '{rel_type}': {len(rel_list)} relation(s)")

                    for rel in rel_list:
                        target_name = rel.get('target', '')
                        if not target_name:
                            continue
                        
                        # Trouver l'UID de la cible
                        from utils.multi_language_parser import normalize_node_name
                        normalized = normalize_node_name(target_name)
                        target_uid = None

                        if normalized:
                            target_uid = self.parent_widget._find_label_uid_by_name(normalized)

                        # ✅ CORRECTION : Vérifier si déjà ajoutée depuis outgoing_relations
                        if target_uid:
                            rel_key = f"{source_uid}->{target_uid}:{rel_type}"
                            if rel_key in seen_relations:
                                logger.debug(f"      ⏭️  Skip doublon: {target_name}")
                                continue
                            seen_relations.add(rel_key)

                        # Si pas trouvé, afficher comme non résolu
                        if not target_uid or target_uid.startswith('unresolved_'):
                            rel_key = f"{source_uid}->unresolved:{target_name}:{rel_type}"
                            if rel_key in seen_relations:
                                continue
                            seen_relations.add(rel_key)

                            source_name = self._get_node_name(source_uid)
                            line_info = f" (L{rel.get('line', '?')})" if rel.get('line') else ""
                            display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} [NON RÉSOLU]"

                            item = QListWidgetItem(display)
                            item.setData(Qt.UserRole, {
                                "category": "parsed_raw",
                                "direction": "out",
                                "source": source_uid,
                                "target": f"unresolved_{target_name}",
                                "target_name": target_name,
                                "type": rel_type,
                                "line": rel.get('line', 0)
                            })
                            item.setForeground(QtGui.QColor("#95a5a6"))  # Gris pour non résolu
                            self.relations_list.addItem(item)
                            logger.debug(f"      ➕ Ajouté (non résolu): {target_name}")
                            continue
                        
                        # ✅ Afficher la relation résolue
                        source_name = self._get_node_name(source_uid) or node.get('label', '')
                        line_info = f" (L{rel.get('line', '?')})" if rel.get('line') else ""

                        display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} [PARSED]"

                        item = QListWidgetItem(display)
                        item.setData(Qt.UserRole, {
                            "category": "parsed_raw",
                            "direction": "out",
                            "source": source_uid,
                            "target": target_uid,
                            "target_name": target_name,
                            "type": rel_type,
                            "line": rel.get('line', 0)
                        })
                        item.setForeground(QtGui.QColor("#FF9800"))
                        self.relations_list.addItem(item)
                        relations_added['parsed'] += 1
                        logger.debug(f"      ✅ Ajouté: {source_name} → {target_name}")

        # === 3. Relations entrantes ===
        if self.show_dependencies:
            for r in node.get('incoming_relations', []):
                source_uid_rel = r.get('source_uid')

                if not source_uid_rel or source_uid_rel.startswith('temp_'):
                    continue
                
                if source_uid_rel.startswith('0x') and len(source_uid_rel) <= 10:
                    source_uid_rel = dgraph_to_local.get(source_uid_rel, source_uid_rel)

                source_name = self._get_node_name(source_uid_rel)
                if not source_name:
                    source_name = r.get('source_name', 'Inconnu')
                    if not source_name or source_name == 'Inconnu':
                        continue
                    
                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')
                target_name = self._get_node_name(source_uid)

                if not target_name:
                    continue
                
                rel_key = f"{source_uid_rel}->{source_uid}:{rel_type}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                # Affichage selon catégorie
                if category == 'parsed':
                    display = f"{source_name} →[{rel_type}]→ {target_name} [CODE IN]"
                else:
                    display = f"{source_name} →[{rel_type}]→ {target_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": category,
                    "direction": "in",
                    "source": source_uid_rel,
                    "target": source_uid,
                    "type": rel_type
                })
                item.setForeground(QtGui.QColor("#4CAF50"))
                self.relations_list.addItem(item)
                relations_added['custom' if category == 'custom' else 'parsed'] += 1

        # === 4. Hiérarchie: Enfants ===
        if self.show_hierarchy:
            children = node.get('children', [])
            for child in children:
                child_uid = child.get('uid')
                if not child_uid:
                    continue
                
                child_name = child.get('label') or child.get('name')
                if not child_name:
                    continue
                
                source_name = self._get_node_name(source_uid)
                if not source_name:
                    source_name = node.get('label', node.get('name', ''))

                rel_key = f"{source_uid}->child:{child_uid}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                display = f"{source_name} →[child]→ {child_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": "hierarchy",
                    "direction": "out",
                    "source": source_uid,
                    "target": child_uid,
                    "type": "child"
                })
                item.setForeground(QtGui.QColor("#9C27B0"))
                self.relations_list.addItem(item)
                relations_added['hierarchy'] += 1

        # === 5. Hiérarchie: Parents ===
        if self.show_hierarchy:
            parents = node.get('parents', [])
            for p_uid in parents:
                if not p_uid:
                    continue
                
                if p_uid.startswith('0x') and len(p_uid) <= 10:
                    p_uid_mapped = dgraph_to_local.get(p_uid, p_uid)
                else:
                    p_uid_mapped = p_uid

                parent_name = self._get_node_name(p_uid_mapped)
                if not parent_name:
                    continue
                
                source_name = self._get_node_name(source_uid)
                if not source_name:
                    source_name = node.get('label', node.get('name', ''))

                rel_key = f"{source_uid}->parent:{p_uid_mapped}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                display = f"{source_name} →[parent]→ {parent_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": "hierarchy",
                    "direction": "in",
                    "source": p_uid,
                    "target": source_uid,
                    "type": "parent"
                })
                item.setForeground(QtGui.QColor("#9C27B0"))
                self.relations_list.addItem(item)
                relations_added['hierarchy'] += 1

        # Log pour debug
        total = sum(relations_added.values())
        logger.info(f"✅ Relations affichées pour {node.get('label', source_uid)}: "
                    f"{relations_added['parsed']} parsées, "
                    f"{relations_added['custom']} custom, "
                    f"{relations_added['hierarchy']} hiérarchie "
                    f"(Total: {total}, Uniques: {len(seen_relations)})")

        if total == 0:
            no_rel_item = QListWidgetItem("(Aucune relation)")
            no_rel_item.setForeground(QtGui.QColor("#999"))
            self.relations_list.addItem(no_rel_item)

    def _on_add_new_relation(self):
        """Ajoute une nouvelle relation custom."""
        source_uid = self.parent_widget.current_selected_label_uid
        if not source_uid:
            QtWidgets.QMessageBox.warning(
                self, 
                "Erreur", 
                "Sélectionnez un nœud source."
            )
            return

        # Créer une liste de toutes les cibles possibles
        target_uids = []
        target_names = []
        for uid, info in self.parent_widget.label_uid_to_info.items():
            if uid == source_uid:
                continue
            name = info.get('name') or info.get('label', 'N/A')
            cluster = info.get('cluster', 'N/A')
            target_uids.append(uid)
            target_names.append(f"{name} ({cluster})")

        if not target_names:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune cible",
                "Aucun nœud disponible comme cible."
            )
            return

        # Boîte de sélection de la cible
        target_name, ok = QInputDialog.getItem(
            self, 
            "Nouvelle relation",
            "Choisissez une cible:", 
            target_names, 
            0, 
            False
        )
        
        if ok and target_name:
            target_index = target_names.index(target_name)
            target_uid = target_uids[target_index]

            # Boîte pour le type de relation
            rel_types = [
                "import", 
                "extends", 
                "implements", 
                "uses", 
                "calls", 
                "depends_on",
                "relation"
            ]
            
            rel_type, ok2 = QInputDialog.getItem(
                self,
                "Type de relation",
                "Type de relation:",
                rel_types,
                0,
                True
            )
            
            if not ok2 or not rel_type:
                rel_type = "relation"

            # Enregistrer relation
            relation = {"target_uid": target_uid, "relation_type": rel_type}
            self.parent_widget.pending_relations[source_uid].append(relation)
            self.parent_widget._update_local_relations(source_uid, target_uid, rel_type)

            self._update_relations_list(source_uid)
            logger.info(f"Nouvelle relation ajoutée: {source_uid} →({rel_type})→ {target_uid}")

    def _diagnose_relations_display(self, node_uid):
        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n['uid'] == node_uid), None)

        if not node:
            print(f"❌ Nœud {node_uid} non trouvé")
            return

        node_name = node.get('label', node.get('name', 'Unknown'))
        print(f"\n{'='*60}")
        print(f"🔍 DIAGNOSTIC RELATIONS pour : {node_name}")
        print(f"{'='*60}\n")

        # 1. Vérifier outgoing_relations
        outgoing = node.get('outgoing_relations', [])
        print(f"📤 Outgoing relations: {len(outgoing)}")
        for i, rel in enumerate(outgoing[:5], 1):
            print(f"   {i}. Type: {rel.get('relation_type')}, "
                  f"Target: {rel.get('target_uid')[:8]}..., "
                  f"Category: {rel.get('category', 'N/A')}")
        if len(outgoing) > 5:
            print(f"   ... et {len(outgoing) - 5} autres")

        # 2. Vérifier dict 'relations'
        relations_dict = node.get('relations', {})
        print(f"\n📋 Dict 'relations': {len(relations_dict)} types")
        for rel_type, rel_list in relations_dict.items():
            print(f"   - {rel_type}: {len(rel_list)} relation(s)")
            for i, rel in enumerate(rel_list[:3], 1):
                print(f"      {i}. target: {rel.get('target', 'N/A')}, "
                      f"line: {rel.get('line', 'N/A')}")
            if len(rel_list) > 3:
                print(f"      ... et {len(rel_list) - 3} autres")

        # 3. Vérifier incoming_relations
        incoming = node.get('incoming_relations', [])
        print(f"\n📥 Incoming relations: {len(incoming)}")
        for i, rel in enumerate(incoming[:5], 1):
            print(f"   {i}. Type: {rel.get('relation_type')}, "
                  f"Source: {rel.get('source_uid')[:8]}...")
        if len(incoming) > 5:
            print(f"   ... et {len(incoming) - 5} autres")

        # 4. Vérifier les filtres actifs
        print(f"\n🔘 Filtres actifs:")
        print(f"   - Hiérarchie: {self.show_hierarchy}")
        print(f"   - Dépendances: {self.show_dependencies}")

        # 5. Vérifier label_uid_to_info
        print(f"\n📚 label_uid_to_info:")
        print(f"   Total entrées: {len(self.parent_widget.label_uid_to_info)}")

        print(f"\n{'='*60}\n")

class RelationsGraphWidget(QtWidgets.QWidget):
    """Widget optimisé pour afficher le graphe des relations du nœud sélectionné"""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget
        self.figure = None
        self.canvas = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Titre dynamique
        self.title_label = QLabel("Graphe des Relations")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50;")
        layout.addWidget(self.title_label)

        # Canvas pour le graphe
        self.figure = Figure(figsize=(5, 3), facecolor='white', dpi=100)  # Taille optimisée pour le panneau
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        layout.addWidget(self.canvas)

        # Légende simplifiée
        self.legend_label = QLabel("Aucun nœud sélectionné")
        self.legend_label.setStyleSheet("font-size: 10px; color: #666; font-style: italic;")
        layout.addWidget(self.legend_label)

        # Message initial
        self._draw_empty_graph()

    def _init_uid_mappings(self):
        """Initialize UID mapping dictionaries."""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
        logger.debug("UID mappings initialized")

    def update_graph(self, central_uid=None):
        """
        Met à jour le graphe pour le nœud central sélectionné.
        Version corrigée : affiche toujours le NOM du nœud central au lieu de l'UID.
        """
        if not central_uid:
            self._draw_empty_graph()
            self.title_label.setText("Graphe des Relations")
            self.legend_label.setText("Aucun nœud sélectionné")
            return

        # 🔸 1. Récupérer les infos du nœud central
        central_info = self.parent_widget.label_uid_to_info.get(central_uid)

        if not central_info:
            # Fallback : essayer via Dgraph
            central_info = self._query_node_info_from_dgraph(central_uid)

            if central_info:
                # Mettre en cache local pour réutilisation
                self.parent_widget.label_uid_to_info[central_uid] = central_info
            else:
                # Si toujours rien, utiliser fallback minimal
                logger.warning(f"Nœud {central_uid} introuvable, utilisation de fallback")
                central_info = {
                    'name': f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid,
                    'label': f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid,
                    'cluster': 'inconnu',
                    'type': 'unknown'
                }

        # 🔸 2. Déterminer le nom à afficher
        central_name = (
            central_info.get('name') 
            or central_info.get('label') 
            or self.parent_widget.name_to_uid.get(central_uid) 
            or f"Nœud {central_uid[:10]}..." if len(central_uid) > 10 else central_uid
        )

        related_items = self._collect_related_items(central_uid, max_depth=1, max_nodes=50)

        if not related_items:
            self.title_label.setText(f"Graphe des relations : {central_name}")
            self.legend_label.setText("Aucune relation trouvée")
            self._draw_empty_graph_with_message(
                f"Le nœud « {central_name} » n'a aucune relation"
            )
            logger.info(f"Aucune relation pour {central_name}")
            return

        # 🔸 4. Affichage du graphe
        logger.info(f"Affichage du graphe pour {central_name}: {len(related_items)} relations")
        self.title_label.setText(f"Graphe des relations : {central_name}")
        self._draw_graph(central_uid, central_name, related_items)

    def _query_node_info_from_dgraph(self, central_uid):
        """
        Query Dgraph for node information with improved error handling.
        Returns node info or None if not found.
        """
        if not self.parent_widget.dgraph_connector or not self.parent_widget.dgraph_connector.client:
            logger.debug("No Dgraph client available.")
            return None

        # Check if it's already a hex Dgraph UID (format: 0x...)
        is_hex_uid = isinstance(central_uid, str) and central_uid.startswith('0x')

        if is_hex_uid:
            # Direct Dgraph query with hex UID
            query = f"""
            {{
              q(func: uid({central_uid})) {{
                uid
                name
                id
                local_id
                label
                description
              }}
            }}
            """
        else:
            # Try local UUID first via local_id field
            query = f"""
            {{
              q(func: eq(local_id, "{central_uid}")) {{
                uid
                name
                id
                local_id
                label
                description
              }}
            }}
            """

        try:
            txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            data = self.parent_widget.dgraph_connector._parse_response(resp)
            nodes = data.get("q", [])

            if nodes:
                node = nodes[0]
                node_uid = node.get('uid', central_uid)

                # Map the Dgraph UID to local UID if not already mapped
                if is_hex_uid and node.get('local_id'):
                    self.parent_widget.local_to_dgraph[node['local_id']] = central_uid
                    self.parent_widget.dgraph_to_local[central_uid] = node['local_id']

                return {
                    'uid': node_uid,
                    'name': node.get('name') or node.get('label', 'Unknown'),
                    'label': node.get('label', node.get('name', 'Unknown')),
                    'description': node.get('description', ''),
                    'id': node.get('id', central_uid)
                }

            # No node found in Dgraph
            logger.warning(f"Nœud {central_uid} non trouvé dans Dgraph")
            return None

        except Exception as e:
            logger.error(f"Erreur query Dgraph pour {central_uid}: {e}")
            return None

    def _draw_empty_graph_with_message(self, message):
        """
        Dessine un graphe vide avec un message personnalisé
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5, 0.5, 
            message, 
            ha='center', 
            va='center', 
            transform=ax.transAxes, 
            fontsize=11, 
            color='#666',
            style='italic'
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.figure.tight_layout()
        self.canvas.draw()

    def _query_relations_for_node(self, central_uid):
        """
        Query Dgraph pour les relations impliquant le nœud central.
        Corrigée pour supporter les identifiants non numériques (UUID string) et mapper.
        """
        if not self.parent_widget.dgraph_connector.client:
            logger.warning("Aucun client Dgraph connecté.")
            return []

        # Mapping pour query : local -> Dgraph UID
        local_to_dgraph = self.parent_widget._get_local_to_dgraph_mapping()
        dgraph_uid = local_to_dgraph.get(central_uid)
        if not dgraph_uid:
            # Fallback : query par 'local_id' si stocké comme champ
            query = f"""
            {{
              q(func: eq(local_id, "{central_uid}")) {{
                uid
                name
                id
                local_id
              }}
            }}
            """
            try:
                txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
                resp = txn.query(query)
                txn.discard()
                data = self.parent_widget.dgraph_connector._parse_response(resp)
                nodes = data.get("q", [])
                if nodes:
                    dgraph_uid = nodes[0]['uid']
                else:
                    logger.warning(f"Pas de Dgraph UID pour local {central_uid}")
                    return []
            except Exception as e:
                logger.error(f"Erreur fallback query pour {central_uid}: {e}")
                return []

        # Query principale avec Dgraph UID (hex)
        query = f"""
        {{
          q(func: uid({dgraph_uid})) {{
            uid
            name
            relationType
            source {{
              uid
              name
              id
              local_id
              level
            }}
            target {{
              uid
              name
              id
              local_id
              level
            }}
          }}
          incoming(func: type(Relation)) @filter(eq(target.uid, {dgraph_uid})) {{
            uid
            name
            relationType
            source {{
              uid
              name
              id
              local_id
              level
            }}
            target {{
              uid
              name
              id
              local_id
              level
            }}
          }}
        }}
        """

        try:
            logger.debug(f"Envoi de la requête Dgraph pour le nœud dgraph_uid={dgraph_uid} (local={central_uid})")
            txn = self.parent_widget.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            data = self.parent_widget.dgraph_connector._parse_response(resp)
            relations = data.get("q", []) + data.get("incoming", [])

            logger.info(f"{len(relations)} relations récupérées depuis Dgraph pour {central_uid}")
            return relations

        except Exception as e:
            logger.error(f"Erreur lors de la query des relations (dgraph={dgraph_uid}): {e}")
            return []

    def _collect_related_items(self, central_uid, max_depth=1, max_nodes=50):
        """
        Version enrichie qui collecte TOUTES les relations (hiérarchiques + parsées + dict relations).
        """
        if not self.parent_widget.current_project_profile_data:
            return []

        all_nodes = self.parent_widget._get_all_nodes()
        central_node = next((n for n in all_nodes if n['uid'] == central_uid), None)
        if not central_node:
            return []

        related = []
        visited = set([central_uid])
        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()

        # === 1. RELATIONS SORTANTES (CUSTOM + PARSÉES depuis outgoing_relations) ===
        for rel in central_node.get('outgoing_relations', []):
            target_uid = rel.get('target_uid', rel.get('target_id', ''))

            # Skip temporaires
            if target_uid.startswith('temp_'):
                continue

            # Mapper si hex Dgraph
            if target_uid.startswith('0x') and len(target_uid) == 6:
                target_uid = dgraph_to_local.get(target_uid, target_uid)

            if target_uid in visited:
                continue

            target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
            if target_node:
                rel_type = rel['relation_type']
                category = rel.get('category', 'custom')

                display_type = f"{rel_type} [{'code' if category == 'parsed' else 'custom'}]"

                related.append({
                    'name': target_node.get('label', target_node.get('name', 'Unknown')),
                    'type': display_type,
                    'uid': target_uid,
                    'direction': 'out',
                    'category': category
                })
                visited.add(target_uid)

        # === 2. RELATIONS PARSÉES depuis le dict 'relations' ===
        parsed_relations = central_node.get('relations', {})
        for rel_type, rel_list in parsed_relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                if not target_name:
                    continue
                
                # Essayer de trouver le nœud cible
                normalized = normalize_node_name(target_name)
                target_node = None

                if normalized:
                    target_node = next(
                        (n for n in all_nodes 
                         if normalize_node_name(n.get('name', '')) == normalized or 
                            normalize_node_name(n.get('label', '')) == normalized),
                        None
                    )

                if target_node:
                    target_uid = target_node['uid']
                    if target_uid not in visited:
                        related.append({
                            'name': target_node.get('label', target_node.get('name', target_name)),
                            'type': f"{rel_type} [parsed]",
                            'uid': target_uid,
                            'direction': 'out',
                            'category': 'parsed',
                            'line': rel.get('line', 0)
                        })
                        visited.add(target_uid)
                else:
                    # Si non trouvé, ajouter quand même pour visualisation
                    related.append({
                        'name': target_name,
                        'type': f"{rel_type} [unresolved]",
                        'uid': f"unresolved_{target_name}",
                        'direction': 'out',
                        'category': 'parsed',
                        'line': rel.get('line', 0)
                    })

        # === 3. RELATIONS ENTRANTES ===
        for rel in central_node.get('incoming_relations', []):
            source_uid = rel.get('source_uid', rel.get('source_id', ''))

            if source_uid.startswith('0x') and len(source_uid) == 6:
                source_uid = dgraph_to_local.get(source_uid, source_uid)

            if source_uid in visited or source_uid.startswith('temp_'):
                continue

            source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
            if source_node:
                rel_type = rel.get('relation_type', 'relation')
                category = rel.get('category', 'custom')
                display_type = f"{rel_type} (in) [{'code' if category == 'parsed' else 'custom'}]"

                related.append({
                    'name': source_node.get('label', source_node.get('name', 'Unknown')),
                    'type': display_type,
                    'uid': source_uid,
                    'direction': 'in',
                    'category': category
                })
                visited.add(source_uid)

        # === 4. HIÉRARCHIE : ENFANTS ===
        for child in central_node.get('children', []):
            child_uid = child['uid']
            if child_uid in visited:
                continue

            related.append({
                'name': child.get('label', child.get('name', 'Child')),
                'type': 'child [hierarchy]',
                'uid': child_uid,
                'direction': 'out',
                'category': 'hierarchy'
            })
            visited.add(child_uid)

        # === 5. HIÉRARCHIE : PARENTS ===
        for parent_uid in central_node.get('parents', []):
            if parent_uid.startswith('0x') and len(parent_uid) == 6:
                parent_uid = dgraph_to_local.get(parent_uid, parent_uid)

            if parent_uid in visited:
                continue

            parent_info = self.parent_widget.label_uid_to_info.get(parent_uid)
            if parent_info:
                related.append({
                    'name': parent_info['name'],
                    'type': 'parent [hierarchy]',
                    'uid': parent_uid,
                    'direction': 'in',
                    'category': 'hierarchy'
                })
                visited.add(parent_uid)

        related = related[:max_nodes]
        logger.info(f"Collecté {len(related)} relations pour {central_node.get('label', central_uid)}")

        return related

    def _draw_empty_graph(self):
        """Dessine un graphe vide avec message"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, 'Sélectionnez un nœud pour voir ses relations', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12, color='#666')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.figure.tight_layout()
        self.canvas.draw()

    def _draw_graph(self, central_uid, central_name, related_items):
        """
        Dessine le graphe avec NetworkX - Version corrigée avec flèches pointant vers la source
        """
        self.figure.clear()
        G = nx.DiGraph()

        # Nœud central
        G.add_node(central_uid, node_type='central', label=central_name)

        if not related_items:
            self._draw_empty_graph()
            return

        # Grouper par type pour statistiques
        relation_types = {}
        seen_nodes = set([central_uid])
        edge_colors = []
        edge_labels = {}

        for item in related_items:
            rel_uid = item['uid']
            rel_name = item['name']
            rel_type = item['type']
            direction = item.get('direction', 'out')

            # Éviter doublons
            if rel_uid in seen_nodes:
                continue
            
            # Ajouter nœud
            G.add_node(rel_uid, node_type='related', label=rel_name)
            seen_nodes.add(rel_uid)

            # CHANGEMENT CRITIQUE: Inverser le sens des arêtes
            if direction == 'in':
                # Relation entrante : central ← rel_uid devient rel_uid → central
                G.add_edge(rel_uid, central_uid, type=rel_type)
                edge_labels[(rel_uid, central_uid)] = rel_type[:6]
            else:
                # Relation sortante : central → rel_uid devient rel_uid → central
                # CHANGEMENT: Inverser pour que la flèche pointe vers central
                G.add_edge(rel_uid, central_uid, type=rel_type)
                edge_labels[(rel_uid, central_uid)] = rel_type[:6]

            # Couleur selon type
            edge_colors.append(self._get_color_for_type(rel_type))

            # Comptage
            base_type = rel_type.replace(' (inverse)', '')
            relation_types[base_type] = relation_types.get(base_type, 0) + 1

        if len(G.nodes()) == 1:
            self._draw_empty_graph()
            return

        # Layout optimisé selon taille
        num_nodes = len(G.nodes())

        if num_nodes <= 10:
            pos = nx.spring_layout(G, k=2.5, iterations=100, seed=42)
        elif num_nodes <= 30:
            pos = nx.kamada_kawai_layout(G)
        else:
            # Layout circulaire pour grands graphes
            pos = nx.circular_layout(G)
            pos[central_uid] = (0, 0)

        # Dessiner
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        # Arêtes avec couleurs
        if G.edges():
            edges_list = list(G.edges())
            nx.draw_networkx_edges(
                G, pos, 
                edgelist=edges_list,
                edge_color=edge_colors,
                ax=ax,
                width=2.0 if num_nodes <= 20 else 1.5,
                alpha=0.7,
                arrows=True,
                arrowsize=15 if num_nodes <= 20 else 12,
                arrowstyle='->',
                connectionstyle='arc3,rad=0.1'
            )

        # Nœuds avec couleurs distinctes
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if node == central_uid:
                node_colors.append('#A23B2D')  # Rouge pour central
                node_sizes.append(800)
            else:
                node_colors.append('#4CAF50')  # Vert pour liés
                node_sizes.append(500)

        nx.draw_networkx_nodes(
            G, pos, 
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.85,
            linewidths=2,
            edgecolors='white'
        )

        # Labels des nœuds
        labels = {}
        for node in G.nodes():
            node_label = G.nodes[node].get('label', node)
            # Tronquer les noms longs
            label = node_label if len(node_label) <= 15 else node_label[:12] + "..."
            labels[node] = label

        label_opts = {
            'ax': ax,
            'font_size': 9 if num_nodes > 20 else 10,
            'font_weight': 'bold',
        }

        if num_nodes <= 30:
            label_opts.update({
                'font_color': 'white',
                'bbox': dict(
                    boxstyle='round,pad=0.3', 
                    facecolor='black', 
                    alpha=0.7, 
                    edgecolor='none'
                )
            })
        else:
            label_opts['font_color'] = 'black'

        nx.draw_networkx_labels(G, pos, labels, **label_opts)

        # Labels des arêtes pour petits graphes
        if num_nodes <= 15 and edge_labels:
            nx.draw_networkx_edge_labels(
                G, pos, 
                edge_labels,
                ax=ax,
                font_size=7,
                font_color='#333',
                bbox=dict(
                    boxstyle='round,pad=0.2', 
                    facecolor='white', 
                    alpha=0.9
                )
            )

        # Titre informatif
        title_text = (
            f"Réseau de relations\n"
            f"Nœud central: {central_name}\n"
            f"({num_nodes} nœuds, {len(G.edges())} relations)"
        )
        ax.set_title(title_text, fontsize=11, fontweight='bold', pad=15)

        ax.axis('off')
        ax.margins(0.15)

        self.figure.tight_layout()
        self.canvas.draw()

        # Mettre à jour la légende avec tous les types
        self._update_legend_with_types(relation_types)

    def _get_color_for_type(self, rel_type):
        """
        Retourne une couleur selon le type de relation.
        Ajoute support pour les types parsés.
        """
        rel_lower = rel_type.lower().replace(' (inverse)', '').replace('[code]', '').replace('[custom]', '').replace('[hierarchy]', '').strip()

        colors = {
            'import': '#FF9800',           # Orange pour imports
            'heritage': '#2196F3',         # Bleu pour héritage
            'extends': '#4CAF50',          # Vert pour extends
            'implement': '#9C27B0',        # Violet pour implement
            'depends_on': '#FF5722',       # Rouge pour dépendances
            'calls': '#00BCD4',            # Cyan pour appels
            'uses': '#795548',             # Marron pour usages
            'references': '#607D8B',       # Gris-bleu pour références
            'child': '#00BCD4',            # Cyan pour hiérarchie
            'parent': '#3F51B5',           # Bleu foncé pour parents
            'relation': '#E91E63',         # Rose pour relations génériques
        }

        # Recherche exacte puis partielle
        if rel_lower in colors:
            return colors[rel_lower]

        for key, color in colors.items():
            if key in rel_lower:
                return color

        return '#999999'

    def _update_legend_with_types(self, relation_types):
        """
        Met à jour la légende avec tous les types de relations
        """
        if not relation_types:
            self.legend_label.setText("Aucune relation")
            return

        # Construire texte de légende avec compteurs
        legend_parts = []
        for rel_type, count in sorted(relation_types.items()):
            color = self._get_color_for_type(rel_type)
            legend_parts.append(f"{rel_type}: {count}")

        legend_text = " | ".join(legend_parts)

        # Tronquer si trop long
        if len(legend_text) > 80:
            legend_text = legend_text[:77] + "..."

        self.legend_label.setText(legend_text)

    def _update_legend(self, related_items):
        """
        Version alternative : légende simple avec comptage
        """
        if not related_items:
            self.legend_label.setText("Aucune relation")
            return
    
        # Grouper par type
        types = {}
        for item in related_items:
            rel_type = item['type'].replace(' (inverse)', '')
            types[rel_type] = types.get(rel_type, 0) + 1
    
        # Construire texte
        legend_text = " | ".join([f"{k}: {v}" for k, v in sorted(types.items())])
        
        if len(legend_text) > 80:
            legend_text = legend_text[:77] + "..."
        
        self.legend_label.setText(legend_text)

class ProjectConfigWidget(QtWidgets.QWidget):
    """Widget pour configurer les profils de projet et l'ontologie de Turing avec liaison hiérarchique."""

    project_profile_saved = pyqtSignal(str, dict)
    project_profile_deleted = pyqtSignal(str)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.conductor = conductor
        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.db_path = os.path.join("data", "liris.db")
        self._init_sqlite_db()

        self.local_to_dgraph = {}
        self.dgraph_to_local = {}

        self.dependency_parser = MultiLanguageDependencyParser()
        self.project_scanner = ProjectStructureScanner(self.dependency_parser)

        self.project_profiles = {}

        self.structure_scanner = self.project_scanner
        
        self.parsed_relations_cache = {}
        self.file_content_cache = {}

        
        self.current_project_name = None
        self.current_project_profile_data = None

        self.current_cluster_index = -1
        self.current_cluster_data = None

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_top_level_is_file = False
        self.current_top_level_filename = None

        self.current_root_label_index = -1
        self.current_root_is_file = False
        self.current_root_filename = None

        self.current_level1_label_index = -1
        self.current_level1_is_file = False
        self.current_level1_filename = None

        self.current_level2_label_index = -1
        self.current_level2_is_file = False
        self.current_level2_filename = None

        # Pour les relations
        self.pending_relations = defaultdict(list)
        self.label_uid_to_info = {}
        self.name_to_uid = {}
        self.current_selected_label_uid = None

        self.global_relations_config = RelationsConfig(self, "global")
        self.relations_graph = RelationsGraphWidget(self)  # Nouveau widget graphe

        # Définir une taille minimale pour le widget et maximiser
        self.setMinimumSize(1400, 900)

        self._init_ui()

        try:
            if self.dgraph_connector.client:
                self._load_project_profiles()
                schema = self.dgraph_connector.get_current_schema()

                if schema and '@reverse' not in schema:
                    logger.warning("Le schéma ne contient pas de @reverse...")
 
            self._load_projects_from_sqlite()
            
            # ← NOUVELLE LIGNE :
            self._update_project_combo()
            logger.debug(f"Initialisation : {len(self.project_profiles)} projets affichés")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation : {str(e)}")

    def _init_sqlite_db(self):
        """Initialise ou met à jour la base SQLite avec schéma aligné à Dgraph."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # === 1️⃣ Vérifier si la table relations existe déjà ===
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='relations';
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                cursor.execute("PRAGMA table_info(relations);")
                existing_cols = [row[1] for row in cursor.fetchall()]

                # Si l'ancienne structure est détectée (pas de colonne 'uid' ou noms différents)
                if 'uid' not in existing_cols or 'relationType' not in existing_cols:
                    logger.warning("Structure obsolète détectée pour la table 'relations'. Reconstruction en cours...")

                    # Sauvegarde des anciennes données minimales (si possible)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS relations_backup AS
                        SELECT * FROM relations;
                    """)

                    # Supprimer l'ancienne table
                    cursor.execute("DROP TABLE relations;")

            # === 2️⃣ Création / recréation des tables ===

            # Table des Workspaces
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT UNIQUE,
                    ownerId TEXT,
                    description TEXT,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table ClusterManagement
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cluster_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    workspace_uid TEXT NOT NULL,
                    lastUpdated TIMESTAMP,
                    version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_uid) REFERENCES workspaces(uid)
                )
            """)

            # Table Clusters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_management_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    userId TEXT,
                    nodeType TEXT DEFAULT 'cluster',
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    is_file_cluster BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_management_uid) REFERENCES cluster_management(uid)
                )
            """)

            # Table Labels
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    cluster_uid TEXT NOT NULL,
                    parent_uid TEXT,
                    name TEXT NOT NULL,
                    id_field TEXT,
                    level INTEGER,
                    path TEXT,
                    parentId TEXT,
                    nodeType TEXT DEFAULT 'label',
                    category TEXT,
                    description TEXT,
                    codeContent TEXT,
                    createdAt TIMESTAMP,
                    updatedAt TIMESTAMP,
                    files TEXT,
                    fileContents TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_uid) REFERENCES clusters(uid),
                    FOREIGN KEY (parent_uid) REFERENCES labels(uid)
                )
            """)

            # 🧩 Table Relations corrigée (structure alignée)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    name TEXT,
                    relationType TEXT NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)

            # Table Functions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    label_uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (label_uid) REFERENCES labels(uid)
                )
            """)

            # Table Imports
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    source_uid TEXT NOT NULL,
                    target_uid TEXT NOT NULL,
                    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_uid) REFERENCES labels(uid),
                    FOREIGN KEY (target_uid) REFERENCES labels(uid)
                )
            """)

            # === 3️⃣ Création d’index ===
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_cm ON clusters(cluster_management_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_cluster ON labels(cluster_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels_parent ON labels(parent_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_uid)")

            conn.commit()
            conn.close()

            logger.info(f"Base de données SQLite initialisée et synchronisée : {self.db_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation ou mise à jour SQLite : {e}")

    def _create_workspace_in_sqlite(self, project_data):
        """CRUD Create: Crée un nouveau workspace en évitant les doublons via uid unique."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid
            
            # Vérifier si existe déjà (bien que uid unique)
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if cursor.fetchone():
                logger.warning(f"Workspace {project_uid} existe déjà.")
                conn.close()
                return False
            
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace créé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du workspace SQLite : {e}")
            return False

    def _read_workspace_from_sqlite(self, workspace_uid):
        """CRUD Read: Lit un workspace spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM workspaces WHERE uid = ?", (workspace_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du workspace SQLite : {e}")
            return None

    def _update_workspace_in_sqlite(self, project_data):
        """CRUD Update: Met à jour un workspace existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid')
            if not project_uid:
                logger.error("UID manquant pour update.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (project_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {project_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE workspaces SET
                name = ?, description = ?, files = ?, fileContents = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                project_data.get('name', ''),
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat(),
                project_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace mis à jour dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du workspace SQLite : {e}")
            return False

    def _delete_workspace_in_sqlite(self, workspace_uid):
        """CRUD Delete: Supprime un workspace et ses dépendances en cascade."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM workspaces WHERE uid = ?", (workspace_uid,))
            if not cursor.fetchone():
                logger.warning(f"Workspace {workspace_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade (ordre inverse des FK)
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid IN (
                        SELECT uid FROM clusters 
                        WHERE cluster_management_uid IN (
                            SELECT uid FROM cluster_management 
                            WHERE workspace_uid = ?
                        )
                    )
                )
            """, (workspace_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))  # Remplacer ... par la sous-requête ci-dessus
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (...) OR target_uid IN (...)
            """, (workspace_uid, workspace_uid))
            
            # Labels
            cursor.execute("""
                DELETE FROM labels 
                WHERE cluster_uid IN (
                    SELECT uid FROM clusters 
                    WHERE cluster_management_uid IN (
                        SELECT uid FROM cluster_management 
                        WHERE workspace_uid = ?
                    )
                )
            """, (workspace_uid,))
            
            # Clusters
            cursor.execute("""
                DELETE FROM clusters 
                WHERE cluster_management_uid IN (
                    SELECT uid FROM cluster_management 
                    WHERE workspace_uid = ?
                )
            """, (workspace_uid,))
            
            # Cluster Management
            cursor.execute("""
                DELETE FROM cluster_management 
                WHERE workspace_uid = ?
            """, (workspace_uid,))
            
            # Workspace
            cursor.execute("DELETE FROM workspaces WHERE uid = ?", (workspace_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Workspace supprimé de SQLite : {workspace_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du workspace SQLite : {e}")
            return False

    def _create_cluster_in_sqlite(self, cluster_data, workspace_uid):
        """CRUD Create: Crée un cluster en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
            cluster_data['uid'] = cluster_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} existe déjà.")
                conn.close()
                return False
            
            # Assurer cluster_management existe
            cm_uid = f"cm_{workspace_uid}"
            cursor.execute("""
                INSERT OR IGNORE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (cm_uid, workspace_uid, datetime.now().isoformat(), '1.0'))
            
            cursor.execute("""
                INSERT INTO clusters 
                (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                 description, codeContent, files, fileContents, is_file_cluster, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cluster_uid,
                cm_uid,
                cluster_data.get('name', ''),
                cluster_data.get('uid', str(uuid.uuid4())),
                'user1',
                'cluster',
                cluster_data.get('description', ''),
                '',
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster créé dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création cluster SQLite : {e}")
            return False

    def _update_cluster_in_sqlite(self, cluster_data):
        """CRUD Update: Met à jour un cluster existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cluster_uid = cluster_data.get('uid')
            if not cluster_uid:
                logger.error("UID manquant pour update cluster.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour update.")
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE clusters SET
                name = ?, description = ?, files = ?, fileContents = ?, is_file_cluster = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                cluster_data.get('name', ''),
                cluster_data.get('description', ''),
                json.dumps(cluster_data.get('files', [])),
                json.dumps(cluster_data.get('file_contents', {})),
                1 if cluster_data.get('is_file_cluster') else 0,
                datetime.now().isoformat(),
                cluster_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster mis à jour dans SQLite : {cluster_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour cluster SQLite : {e}")
            return False

    def _delete_cluster_in_sqlite(self, cluster_uid):
        """CRUD Delete: Supprime un cluster et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM clusters WHERE uid = ?", (cluster_uid,))
            if not cursor.fetchone():
                logger.warning(f"Cluster {cluster_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("""
                DELETE FROM functions 
                WHERE label_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid,))
            
            # Imports
            cursor.execute("""
                DELETE FROM imports 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Relations
            cursor.execute("""
                DELETE FROM relations 
                WHERE source_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                ) OR target_uid IN (
                    SELECT uid FROM labels 
                    WHERE cluster_uid = ?
                )
            """, (cluster_uid, cluster_uid))
            
            # Labels
            cursor.execute("DELETE FROM labels WHERE cluster_uid = ?", (cluster_uid,))
            
            # Cluster
            cursor.execute("DELETE FROM clusters WHERE uid = ?", (cluster_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Cluster supprimé de SQLite : {cluster_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression cluster SQLite : {e}")
            return False

    def _create_label_in_sqlite(self, label_data, cluster_uid, parent_uid=None, level=0):
        """CRUD Create: Crée un label en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid', str(uuid.uuid4()))
            label_data['uid'] = label_uid
            
            # Vérifier doublon
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if cursor.fetchone():
                logger.warning(f"Label {label_uid} existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label_uid,
                cluster_uid,
                parent_uid,
                label_data.get('label', ''),
                label_data.get('id', label_uid),
                level,
                '',  # path
                parent_uid,  # parentId
                'label',
                json.dumps(label_data.get('category', [])),
                label_data.get('description', ''),
                '',  # codeContent
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label créé dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création label SQLite : {e}")
            return False

    def _read_label_from_sqlite(self, label_uid):
        """CRUD Read: Lit un label spécifique et ses enfants récursivement."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM labels WHERE uid = ?", (label_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            data['category'] = json.loads(data['category'])
            data['files'] = json.loads(data['files'])
            data['fileContents'] = json.loads(data['fileContents'])
            data['children'] = []
            data['parents'] = [data['parent_uid']] if data['parent_uid'] else []
            
            # Charger enfants récursivement
            cursor.execute("SELECT uid FROM labels WHERE parent_uid = ?", (label_uid,))
            for child_row in cursor.fetchall():
                child_data = self._read_label_from_sqlite(child_row['uid'])
                if child_data:
                    data['children'].append(child_data)
            
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture label SQLite : {e}")
            return None

    def _test_relations_loading(self):
        """
        Méthode de diagnostic pour vérifier le chargement des relations depuis Dgraph.
        Affiche des statistiques détaillées sur les relations parsées et custom.
        """
        logger.info("\n" + "="*80)
        logger.info("🧪 TEST CHARGEMENT RELATIONS")
        logger.info("="*80)

        if not self.current_project_profile_data:
            logger.warning("❌ Aucun projet chargé")
            return

        project_name = self.current_project_profile_data.get('name', 'Unknown')
        logger.info(f"📦 Projet: {project_name}")

        # === 1️⃣ STATISTIQUES GLOBALES ===
        all_nodes = self._get_all_nodes()

        stats = {
            'total_nodes': len(all_nodes),
            'nodes_with_outgoing': 0,
            'nodes_with_incoming': 0,
            'nodes_with_relations_dict': 0,
            'total_outgoing_relations': 0,
            'total_incoming_relations': 0,
            'total_parsed_in_dict': 0,
            'parsed_relations_count': 0,
            'custom_relations_count': 0,
            'hierarchy_relations_count': 0,
            'unresolved_relations': 0,
            'relations_by_type': defaultdict(int)
        }

        logger.info(f"\n📊 ANALYSE DE {stats['total_nodes']} NŒUDS\n")

        # === 2️⃣ PARCOURIR TOUS LES NŒUDS ===
        for node in all_nodes:
            node_name = node.get('label', node.get('name', 'Unknown'))
            node_uid = node.get('uid', 'N/A')

            # Vérifier outgoing_relations
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                stats['nodes_with_outgoing'] += 1
                stats['total_outgoing_relations'] += len(outgoing)

                for rel in outgoing:
                    rel_type = rel.get('relation_type', 'unknown')
                    rel_category = rel.get('category', 'custom')

                    stats['relations_by_type'][rel_type] += 1

                    if rel_category == 'parsed':
                        stats['parsed_relations_count'] += 1
                    elif rel_category == 'hierarchy':
                        stats['hierarchy_relations_count'] += 1
                    else:
                        stats['custom_relations_count'] += 1

                    # Détecter relations non résolues
                    target_uid = rel.get('target_uid', '')
                    if target_uid.startswith('temp_') or target_uid.startswith('unresolved_'):
                        stats['unresolved_relations'] += 1

            # Vérifier incoming_relations
            incoming = node.get('incoming_relations', [])
            if incoming:
                stats['nodes_with_incoming'] += 1
                stats['total_incoming_relations'] += len(incoming)

            # Vérifier dict 'relations' (relations parsées brutes)
            relations_dict = node.get('relations', {})
            if relations_dict:
                stats['nodes_with_relations_dict'] += 1
                for rel_type, rel_list in relations_dict.items():
                    stats['total_parsed_in_dict'] += len(rel_list)
                    logger.debug(f"  📄 {node_name} - relations['{rel_type}']: {len(rel_list)} items")

        # === 3️⃣ AFFICHER LES STATISTIQUES ===
        logger.info("📈 RÉSULTATS:")
        logger.info(f"  • Total nœuds: {stats['total_nodes']}")
        logger.info(f"  • Nœuds avec relations sortantes: {stats['nodes_with_outgoing']}")
        logger.info(f"  • Nœuds avec relations entrantes: {stats['nodes_with_incoming']}")
        logger.info(f"  • Nœuds avec dict 'relations': {stats['nodes_with_relations_dict']}")
        logger.info(f"\n🔗 RELATIONS:")
        logger.info(f"  • Total sortantes: {stats['total_outgoing_relations']}")
        logger.info(f"  • Total entrantes: {stats['total_incoming_relations']}")
        logger.info(f"  • Parsées (code): {stats['parsed_relations_count']}")
        logger.info(f"  • Custom (manuelles): {stats['custom_relations_count']}")
        logger.info(f"  • Hiérarchie (parent/child): {stats['hierarchy_relations_count']}")
        logger.info(f"  • Non résolues: {stats['unresolved_relations']}")
        logger.info(f"  • Dans dict 'relations': {stats['total_parsed_in_dict']}")

        # === 4️⃣ TYPES DE RELATIONS ===
        if stats['relations_by_type']:
            logger.info(f"\n📋 TYPES DE RELATIONS:")
            for rel_type, count in sorted(stats['relations_by_type'].items(), key=lambda x: -x[1]):
                logger.info(f"  • {rel_type}: {count}")

        # === 5️⃣ VÉRIFICATION PENDING_RELATIONS ===
        pending_count = sum(len(rels) for rels in self.pending_relations.values())
        logger.info(f"\n⏳ PENDING_RELATIONS:")
        logger.info(f"  • Nœuds sources: {len(self.pending_relations)}")
        logger.info(f"  • Total relations: {pending_count}")

        # === 6️⃣ EXEMPLES DE RELATIONS ===
        logger.info(f"\n🔍 EXEMPLES DE RELATIONS (premiers 5 nœuds):")

        sample_nodes = [n for n in all_nodes if n.get('outgoing_relations') or n.get('incoming_relations')][:5]

        for node in sample_nodes:
            node_name = node.get('label', node.get('name', 'Unknown'))
            logger.info(f"\n  📦 {node_name} (UID: {node.get('uid', 'N/A')[:8]}...)")

            # Sortantes
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                logger.info(f"    ↗ Sortantes ({len(outgoing)}):")
                for rel in outgoing[:3]:  # Limiter à 3
                    target_uid = rel.get('target_uid', 'N/A')
                    target_name = self.label_uid_to_info.get(target_uid, {}).get('name', 'Unknown')
                    rel_type = rel.get('relation_type', 'N/A')
                    category = rel.get('category', 'custom')
                    logger.info(f"      • {rel_type} [{category}] → {target_name}")

            # Entrantes
            incoming = node.get('incoming_relations', [])
            if incoming:
                logger.info(f"    ↙ Entrantes ({len(incoming)}):")
                for rel in incoming[:3]:  # Limiter à 3
                    source_uid = rel.get('source_uid', 'N/A')
                    source_name = self.label_uid_to_info.get(source_uid, {}).get('name', 'Unknown')
                    rel_type = rel.get('relation_type', 'N/A')
                    category = rel.get('category', 'custom')
                    logger.info(f"      • {source_name} {rel_type} [{category}] →")

        # === 7️⃣ VÉRIFICATION COHÉRENCE ===
        logger.info(f"\n🔍 VÉRIFICATION COHÉRENCE:")

        # Vérifier que les relations sortantes ont leurs inverses
        missing_inverses = 0
        for node in all_nodes:
            node_uid = node.get('uid')
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')
                if target_uid.startswith('temp_') or target_uid.startswith('unresolved_'):
                    continue
                
                target_node = next((n for n in all_nodes if n.get('uid') == target_uid), None)
                if target_node:
                    # Vérifier si relation inverse existe
                    has_inverse = any(
                        r.get('source_uid') == node_uid 
                        for r in target_node.get('incoming_relations', [])
                    )
                    if not has_inverse:
                        missing_inverses += 1

        logger.info(f"  • Relations sortantes sans inverse: {missing_inverses}")

        # === 8️⃣ TEST AFFICHAGE UI ===
        if all_nodes and hasattr(self, 'global_relations_config'):
            test_node = all_nodes[0]
            test_uid = test_node.get('uid')

            logger.info(f"\n🎯 TEST AFFICHAGE UI:")
            logger.info(f"  • Nœud test: {test_node.get('label', 'Unknown')}")
            logger.info(f"  • UID: {test_uid}")

            try:
                self.global_relations_config.update_current(test_uid)
                ui_count = self.global_relations_config.relations_list.count()
                logger.info(f"  • Items affichés dans UI: {ui_count}")

                if ui_count == 0:
                    logger.warning("  ⚠️ ATTENTION: Aucune relation affichée dans l'UI!")
            except Exception as e:
                logger.error(f"  ❌ Erreur test UI: {e}")

        # === 9️⃣ RECOMMANDATIONS ===
        logger.info(f"\n💡 RECOMMANDATIONS:")

        if stats['unresolved_relations'] > 0:
            logger.warning(f"  ⚠️ {stats['unresolved_relations']} relations non résolues à traiter")

        if missing_inverses > 0:
            logger.warning(f"  ⚠️ {missing_inverses} relations inverses manquantes")

        if stats['parsed_relations_count'] == 0 and stats['total_parsed_in_dict'] > 0:
            logger.warning("  ⚠️ Relations parsées présentes dans dict mais pas dans outgoing_relations")
            logger.info("  → Exécuter _build_complete_relations_graph()")

        if stats['total_outgoing_relations'] == 0:
            logger.warning("  ⚠️ AUCUNE relation trouvée!")
            logger.info("  → Vérifier le parsing ou lancer un scan avec _on_browse_project()")

        logger.info("="*80 + "\n")

        # === 🔟 RETOURNER LES STATS POUR USAGE EXTERNE ===
        return stats

    def _update_label_in_sqlite(self, label_data):
        """CRUD Update: Met à jour un label existant."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            label_uid = label_data.get('uid')
            if not label_uid:
                logger.error("UID manquant pour update label.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour update.")
                conn.close()
                return False
            
            parent_uid = label_data.get('parents', [None])[0] if label_data.get('parents') else None
            
            cursor.execute("""
                UPDATE labels SET
                name = ?, description = ?, category = ?, files = ?, fileContents = ?, parent_uid = ?, updatedAt = ?
                WHERE uid = ?
            """, (
                label_data.get('label', ''),
                label_data.get('description', ''),
                json.dumps(label_data.get('category', [])),
                json.dumps(label_data.get('files', [])),
                json.dumps(label_data.get('file_contents', {})),
                parent_uid,
                datetime.now().isoformat(),
                label_uid
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Label mis à jour dans SQLite : {label_data.get('label')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour label SQLite : {e}")
            return False

    def _delete_label_in_sqlite(self, label_uid):
        """CRUD Delete: Supprime un label et ses dépendances."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM labels WHERE uid = ?", (label_uid,))
            if not cursor.fetchone():
                logger.warning(f"Label {label_uid} non trouvé pour suppression.")
                conn.close()
                return False
            
            # Supprimer en cascade
            # Functions
            cursor.execute("DELETE FROM functions WHERE label_uid = ?", (label_uid,))
            
            # Imports
            cursor.execute("DELETE FROM imports WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Relations
            cursor.execute("DELETE FROM relations WHERE source_uid = ? OR target_uid = ?", (label_uid, label_uid))
            
            # Enfants récursifs
            cursor.execute("""
                WITH RECURSIVE label_tree AS (
                    SELECT uid FROM labels WHERE uid = ?
                    UNION ALL
                    SELECT l.uid FROM labels l
                    JOIN label_tree lt ON l.parent_uid = lt.uid
                )
                DELETE FROM labels WHERE uid IN (SELECT uid FROM label_tree)
            """, (label_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Label supprimé de SQLite : {label_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression label SQLite : {e}")
            return False

    def _create_relation_in_sqlite(self, source_uid, target_uid, relation_type='relation'):
        """CRUD Create: Crée une relation en évitant doublons."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            rel_uid = f"rel_{str(uuid.uuid4())}"
            
            # Vérifier doublon (même source, target, type)
            cursor.execute("""
                SELECT uid FROM relations 
                WHERE source_uid = ? AND target_uid = ? AND relationType = ?
            """, (source_uid, target_uid, relation_type))
            if cursor.fetchone():
                logger.warning(f"Relation {source_uid} -> {target_uid} ({relation_type}) existe déjà.")
                conn.close()
                return False
            
            cursor.execute("""
                INSERT INTO relations 
                (uid, name, relationType, source_uid, target_uid, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rel_uid,
                f"{relation_type}_relation",
                relation_type,
                source_uid,
                target_uid,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation créée dans SQLite : {source_uid} -> {target_uid} ({relation_type})")
            return True
            
        except Exception as e:
            logger.error(f"Erreur création relation SQLite : {e}")
            return False

    def _read_relation_from_sqlite(self, rel_uid):
        """CRUD Read: Lit une relation spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM relations WHERE uid = ?", (rel_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            data = dict(row)
            conn.close()
            return data
            
        except Exception as e:
            logger.error(f"Erreur lecture relation SQLite : {e}")
            return None

    def _update_relation_in_sqlite(self, rel_uid, new_target_uid=None, new_relation_type=None):
        """CRUD Update: Met à jour une relation existante."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if not rel_uid:
                logger.error("UID manquant pour update relation.")
                conn.close()
                return False
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour update.")
                conn.close()
                return False
            
            updates = []
            params = []
            if new_target_uid is not None:
                updates.append("target_uid = ?")
                params.append(new_target_uid)
            if new_relation_type is not None:
                updates.append("relationType = ?")
                params.append(new_relation_type)
            updates.append("updatedAt = ?")  # Toujours updater la date
            params.append(datetime.now().isoformat())
            params.append(rel_uid)
            
            if updates:
                query = f"UPDATE relations SET {', '.join(updates)} WHERE uid = ?"
                cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            logger.info(f"Relation mise à jour dans SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour relation SQLite : {e}")
            return False

    def _delete_relation_in_sqlite(self, rel_uid):
        """CRUD Delete: Supprime une relation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vérifier existence
            cursor.execute("SELECT uid FROM relations WHERE uid = ?", (rel_uid,))
            if not cursor.fetchone():
                logger.warning(f"Relation {rel_uid} non trouvée pour suppression.")
                conn.close()
                return False
            
            cursor.execute("DELETE FROM relations WHERE uid = ?", (rel_uid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Relation supprimée de SQLite : {rel_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression relation SQLite : {e}")
            return False

    def _save_project_to_sqlite(self, project_data):
        """Sauvegarde le projet complet dans SQLite avec schéma aligné à Dgraph (Upsert)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid  # Ensure uid is set
            
            # Upsert Workspace
            workspace_id = project_data.get('name', str(uuid.uuid4()))
            cursor.execute("""
                INSERT OR REPLACE INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                workspace_id,
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))
            
            # Upsert ClusterManagement
            cluster_management_uid = f"cm_{project_uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (
                cluster_management_uid,
                project_uid,
                datetime.now().isoformat(),
                '1.0'
            ))
            
            # Upsert clusters et labels
            for cluster_data in project_data.get('turing_ontology', {}).get('clusters_detailed', []):
                cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
                cluster_data['uid'] = cluster_uid
                
                cursor.execute("""
                    INSERT OR REPLACE INTO clusters 
                    (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                     description, codeContent, files, fileContents, is_file_cluster, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster_uid,
                    cluster_management_uid,
                    cluster_data.get('name', ''),
                    cluster_data.get('uid', str(uuid.uuid4())),
                    'user1',
                    'cluster',
                    cluster_data.get('description', ''),
                    '',
                    json.dumps(cluster_data.get('files', [])),
                    json.dumps(cluster_data.get('file_contents', {})),
                    1 if cluster_data.get('is_file_cluster') else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                # Upsert labels hiérarchiquement
                for root_label in cluster_data.get('root_labels', []):
                    self._save_label_recursive_sqlite(
                        cursor, root_label, cluster_uid, None, 0
                    )
            
            # Upsert relations
            for source_uid, relations in self.pending_relations.items():
                for rel in relations:
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    relation_type = rel.get('relation_type', 'relation')
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{relation_type}_relation",
                        relation_type,
                        source_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Projet sauvegardé dans SQLite : {project_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde SQLite : {e}")
            return False

    def _delete_project_from_sqlite(self, workspace_uid):
        """Supprime un projet entier de SQLite (CRUD Delete pour projet)."""
        return self._delete_workspace_in_sqlite(workspace_uid)

    def _save_label_recursive_sqlite(self, cursor, label_data, cluster_uid, parent_uid, level):
        """Sauvegarde récursivement les labels dans SQLite (Upsert)."""
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid
        
        cursor.execute("""
            INSERT OR REPLACE INTO labels 
            (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
             nodeType, category, description, codeContent, files, fileContents, 
             createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label_uid,
            cluster_uid,
            parent_uid,
            label_data.get('label', ''),
            label_data.get('id', label_uid),
            level,
            '',  # path
            parent_uid,  # parentId
            'label',
            json.dumps(label_data.get('category', [])),
            label_data.get('description', ''),
            '',  # codeContent
            json.dumps(label_data.get('files', [])),
            json.dumps(label_data.get('file_contents', {})),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        # Traiter les enfants récursivement
        for child in label_data.get('children', []):
            self._save_label_recursive_sqlite(cursor, child, cluster_uid, label_uid, level + 1)

    def _load_projects_from_sqlite(self):
        """Charge les projets depuis SQLite au démarrage, en évitant les doublons avec Dgraph."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM workspaces")
            workspaces = cursor.fetchall()

            loaded_count = 0
            skipped_count = 0

            for ws_row in workspaces:
                workspace_uid = ws_row['uid']
                project_name = ws_row['name']

                # ✅ ÉVITER DOUBLON : skip si déjà chargé (de Dgraph)
                if project_name in self.project_profiles:
                    logger.debug(f"   ⏭️ Projet déjà chargé (Dgraph), skip SQLite: {project_name}")
                    skipped_count += 1
                    continue
                
                # ✅ CHARGER VIA CRUD READ
                ws_data = self._read_workspace_from_sqlite(workspace_uid)
                if not ws_data:
                    continue
                
                project_data = {
                    'uid': ws_data['uid'],
                    'name': ws_data['name'],
                    'description': ws_data['description'],
                    'files': ws_data['files'],
                    'file_contents': ws_data['fileContents'],
                    'turing_ontology': {'clusters_detailed': []},
                    'pending_relations': {}
                }

                # Charger clusters via Read
                cursor.execute("""
                    SELECT c.* FROM clusters c 
                    JOIN cluster_management cm ON c.cluster_management_uid = cm.uid 
                    WHERE cm.workspace_uid = ?
                """, (workspace_uid,))

                for cluster_row in cursor.fetchall():
                    cluster_uid = cluster_row['uid']
                    cluster_data = self._read_cluster_from_sqlite(cluster_uid)
                    if not cluster_data:
                        continue
                    cluster_data['root_labels'] = []

                    # Charger labels racines
                    cursor.execute("""
                        SELECT * FROM labels 
                        WHERE cluster_uid = ? AND parent_uid IS NULL
                    """, (cluster_uid,))

                    for label_row in cursor.fetchall():
                        root_label = self._read_label_from_sqlite(label_row['uid'])
                        if root_label:
                            cluster_data['root_labels'].append(root_label)

                    project_data['turing_ontology']['clusters_detailed'].append(cluster_data)

                # Charger relations
                cursor.execute("""
                    SELECT * FROM relations WHERE source_uid IN (
                        SELECT uid FROM labels WHERE cluster_uid IN (
                            SELECT uid FROM clusters WHERE cluster_management_uid IN (
                                SELECT uid FROM cluster_management WHERE workspace_uid = ?
                            )
                        )
                    )
                """, (workspace_uid,))

                relations_by_source = {}
                for rel_row in cursor.fetchall():
                    source_uid = rel_row['source_uid']
                    if source_uid not in relations_by_source:
                        relations_by_source[source_uid] = []
                    relations_by_source[source_uid].append({
                        'target_uid': rel_row['target_uid'],
                        'relation_type': rel_row['relationType']
                    })

                project_data['pending_relations'] = relations_by_source

                # ✅ STOCKER
                self.project_profiles[project_name] = project_data
                loaded_count += 1
                logger.debug(f"   ✅ Chargé depuis SQLite: {project_name}")

            conn.close()
            logger.info(f"✅ Chargé depuis SQLite: {loaded_count} projet(s) (ignoré {skipped_count} doublon(s))")

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement SQLite : {e}")
            import traceback
            traceback.print_exc()
    
    def _read_cluster_from_sqlite(self, cluster_uid):
        """CRUD Read: Lit un cluster spécifique."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM clusters WHERE uid = ?", (cluster_uid,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None

            data = dict(row)
            data['files'] = json.loads(data['files'])
            data['file_contents'] = json.loads(data['fileContents'])
            data['root_labels'] = []  # Sera rempli par l'appelant

            conn.close()
            return data

        except Exception as e:
            logger.error(f"Erreur lecture cluster SQLite : {e}")
            return None

    def _load_label_from_sqlite(self, cursor, label_row):
        """Charge un label et ses enfants depuis SQLite."""
        label_uid = label_row['uid']
        label_data = {
            'uid': label_uid,
            'label': label_row['name'],
            'id': label_row['id_field'],
            'description': label_row['description'],
            'category': json.loads(label_row['category']),
            'files': json.loads(label_row['files']),
            'file_contents': json.loads(label_row['fileContents']),
            'parents': [label_row['parent_uid']] if label_row['parent_uid'] else [],
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': []
        }
        
        # Charger les enfants
        cursor.execute("""
            SELECT * FROM labels WHERE parent_uid = ?
        """, (label_uid,))
        
        for child_row in cursor.fetchall():
            child_label = self._load_label_from_sqlite(cursor, child_row)
            label_data['children'].append(child_label)
        
        return label_data

    def _get_all_nodes(self):
        """Récupère tous les nœuds de labels dans la hiérarchie."""
        if not self.current_project_profile_data:
            return []
        all_nodes = []
        def collect_nodes(node_list):
            for node in node_list:
                all_nodes.append(node)
                collect_nodes(node.get('children', []))
        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            collect_nodes(cluster.get('root_labels', []))
        return all_nodes

    def _update_local_relations(self, source_uid, target_uid, rel_type):
        """Met à jour les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if source_node:
            source_node.setdefault('outgoing_relations', []).append({'target_uid': target_uid, 'relation_type': rel_type})
        target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
        if target_node:
            target_node.setdefault('incoming_relations', []).append({'source_uid': source_uid, 'relation_type': rel_type})

    def _update_local_relations_remove(self, source_uid, target_uid, rel_type):
        """Supprime les relations locales dans les données des nœuds."""
        all_nodes = self._get_all_nodes()
        source_node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if source_node:
            to_remove = next((r for r in source_node.get('outgoing_relations', []) if r['target_uid'] == target_uid and (rel_type is None or r['relation_type'] == rel_type)), None)
            if to_remove:
                source_node['outgoing_relations'].remove(to_remove)
        target_node = next((n for n in all_nodes if n['uid'] == target_uid), None)
        if target_node:
            to_remove = next((r for r in target_node.get('incoming_relations', []) if r['source_uid'] == source_uid and (rel_type is None or r['relation_type'] == rel_type)), None)
            if to_remove:
                target_node['incoming_relations'].remove(to_remove)

    def showEvent(self, event):
        """Maximiser la fenêtre lors de l'affichage"""
        super().showEvent(event)
        if self.window():
            self.window().showMaximized()

    def _get_improved_list_style(self):
        """Style amélioré pour les listes avec sélection gris clair"""
        return """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
                margin: 2px 0px;
                color: #000000;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            QListWidget::item:selected:hover {
                background-color: #d5d5d5;
                color: #000000;
            }
        """

    def _on_insert_dgraph(self):
        """Insère le profil dans Dgraph après sauvegarde SQLite."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        
        # Étape 1 : Sauvegarder d'abord dans SQLite
        if not self._save_project_to_sqlite(self.current_project_profile_data):
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                "Échec de la sauvegarde dans SQLite. Insertion Dgraph annulée."
            )
            return
        
        QtWidgets.QMessageBox.information(
            self,
            "Succès partiel",
            "Projet sauvegardé dans SQLite. Insertion dans Dgraph en cours..."
        )
        
        # Étape 2 : Insérer dans Dgraph
        mutations = self._transform_profile_to_dgraph_mutations()
        
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                "Inséré dans SQLite et Dgraph avec succès. Ratel ouvert pour vérification."
            )
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.warning(
                self, 
                "Avertissement", 
                "Sauvegardé dans SQLite mais échec insertion Dgraph.\n"
                "Les données sont disponibles dans SQLite."
            )

    def _init_ui(self):
        """Initialise l'interface utilisateur pour la configuration du projet (layout 3 colonnes)."""
        main_vertical_layout = QtWidgets.QVBoxLayout(self)
        main_vertical_layout.setSpacing(15)
        main_vertical_layout.setContentsMargins(15, 15, 15, 15)

        top_columns_layout = QtWidgets.QHBoxLayout()
        top_columns_layout.setSpacing(15)
        main_vertical_layout.addLayout(top_columns_layout)

        self.label_uid_to_info = {}
        self.pending_relations = defaultdict(list)
        self.current_selected_label_uid = None

        # --- Colonne de gauche ---
        left_column_layout = QtWidgets.QVBoxLayout()
        left_column_layout.setSpacing(12)

        # Groupe sélection projet
        project_selection_group = QtWidgets.QGroupBox(
            tr("project_config.select_profile_group")
        )
        project_selection_group.setObjectName("project_selection_group")
        project_selection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        project_selection_layout = QtWidgets.QHBoxLayout(project_selection_group)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_combo.setMinimumWidth(200)
        self.project_combo.setMaximumWidth(350)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        project_selection_layout.addWidget(self.project_combo)

        # Bouton "Ajouter"
        self.add_project_button = QtWidgets.QPushButton("Ajouter")
        self.add_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_project_button.clicked.connect(self._on_add_new_project)
        project_selection_layout.addWidget(self.add_project_button)

        # Bouton "Supprimer"
        self.delete_project_button = QtWidgets.QPushButton("Supprimer")
        self.delete_project_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.delete_project_button.clicked.connect(self._on_delete_project)
        self.delete_project_button.setEnabled(False)
        project_selection_layout.addWidget(self.delete_project_button)

        # Bouton "Uploader"
        self.upload_local_button = QtWidgets.QPushButton("📁 Uploader")
        self.upload_local_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.upload_local_button.clicked.connect(self._on_upload_local_project)
        project_selection_layout.addWidget(self.upload_local_button)

        project_selection_layout.addStretch()

        left_column_layout.addWidget(project_selection_group)

        # Groupe détails
        details_group = QtWidgets.QGroupBox(tr("project_config.details_group"))
        details_group.setObjectName("details_group")
        details_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_form_layout = QtWidgets.QFormLayout(details_group)
        details_form_layout.setSpacing(12)
        details_form_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # Layout horizontal pour le nom du projet avec bouton Parcourir
        project_name_widget = QtWidgets.QWidget()
        project_name_layout = QtWidgets.QHBoxLayout(project_name_widget)
        project_name_layout.setContentsMargins(0, 0, 0, 0)
        project_name_layout.setSpacing(8)

        self.project_name_edit = QtWidgets.QLineEdit()
        self.project_name_edit.setPlaceholderText(
            tr("project_config.project_name_placeholder")
        )
        self.project_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.project_name_edit.setMinimumWidth(200)
        self.project_name_edit.setMaximumWidth(350)
        project_name_layout.addWidget(self.project_name_edit)

        # Bouton Parcourir
        self.browse_button = QtWidgets.QPushButton("Scanner les noeuds")
        self.browse_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.browse_button.setMaximumWidth(120)
        if hasattr(self, '_on_browse_project'):
            self.browse_button.clicked.connect(self._on_browse_project)
        project_name_layout.addWidget(self.browse_button)

        project_name_layout.addStretch()

        details_form_layout.addRow("", project_name_widget)

        self.project_description_edit = QtWidgets.QTextEdit()
        self.project_description_edit.setPlaceholderText("Description du projet...")
        self.project_description_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #888888;
            }
        """)
        self.project_description_edit.setMaximumHeight(80)
        details_form_layout.addRow("Description:", self.project_description_edit)

        cluster_list_layout = QtWidgets.QVBoxLayout()
        cluster_list_title = QtWidgets.QLabel(tr("project_config.cluster_label"))
        cluster_list_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cluster_list_layout.addWidget(cluster_list_title)

        self.cluster_list_widget = QtWidgets.QListWidget()
        self.cluster_list_widget.setStyleSheet(self._get_improved_list_style())
        self.cluster_list_widget.setMinimumHeight(60)
        self.cluster_list_widget.currentItemChanged.connect(self._on_cluster_selected)
        cluster_list_layout.addWidget(self.cluster_list_widget)

        cluster_buttons_layout = QtWidgets.QHBoxLayout()
        cluster_buttons_layout.setSpacing(5)

        self.add_cluster_button = QtWidgets.QPushButton("Ajouter")
        self.add_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_cluster_button.clicked.connect(self._add_cluster)

        self.edit_cluster_button = QtWidgets.QPushButton("Modifier")
        self.edit_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_cluster_button.clicked.connect(self._edit_cluster)

        self.remove_cluster_button = QtWidgets.QPushButton("Supprimer")
        self.remove_cluster_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_cluster_button.clicked.connect(self._remove_cluster)

        cluster_buttons_layout.addWidget(self.add_cluster_button)
        cluster_buttons_layout.addWidget(self.edit_cluster_button)
        cluster_buttons_layout.addWidget(self.remove_cluster_button)
        cluster_buttons_layout.addStretch()
        cluster_list_layout.addLayout(cluster_buttons_layout)

        details_form_layout.addRow(cluster_list_layout)

        left_column_layout.addWidget(details_group)

        details_selected_group = QtWidgets.QGroupBox("Détails sélectionné")
        details_selected_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        details_selected_layout = QtWidgets.QVBoxLayout(details_selected_group)
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.details_text.setMaximumHeight(400)
        details_selected_layout.addWidget(self.details_text)
        left_column_layout.addWidget(details_selected_group)

        left_column_layout.addStretch()

        top_columns_layout.addLayout(left_column_layout, 4)

        # --- Colonne du milieu: Hiérarchie (largeur augmentée) ---
        middle_scroll = QtWidgets.QScrollArea()
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setStyleSheet("border: none;")

        middle_content = QtWidgets.QWidget()
        hierarchy_layout = QtWidgets.QVBoxLayout(middle_content)
        hierarchy_layout.setSpacing(8)
        hierarchy_layout.setContentsMargins(0, 0, 0, 0)

        hierarchy_group = QtWidgets.QGroupBox(tr("project_config.hierarchy_group"))
        hierarchy_group.setObjectName("hierarchy_group")
        hierarchy_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        hierarchy_group_layout = QtWidgets.QVBoxLayout(hierarchy_group)
        hierarchy_group_layout.setSpacing(8)

        # 1. Labels Racines
        root_label_title = QtWidgets.QLabel(tr("project_config.root_labels_list_label"))
        root_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(root_label_title)

        self.root_list_widget = QtWidgets.QListWidget()
        self.root_list_widget.setStyleSheet(self._get_improved_list_style())
        self.root_list_widget.setMinimumHeight(80)
        self.root_list_widget.currentItemChanged.connect(self._on_root_label_selected)
        hierarchy_group_layout.addWidget(self.root_list_widget)

        root_buttons_layout = QtWidgets.QHBoxLayout()
        root_buttons_layout.setSpacing(5)

        self.add_root_button = QtWidgets.QPushButton("Ajouter")
        self.add_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_root_button.clicked.connect(self._add_root_label)

        self.edit_root_button = QtWidgets.QPushButton("Modifier")
        self.edit_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_root_button.clicked.connect(self._edit_root_label)

        self.remove_root_button = QtWidgets.QPushButton("Supprimer")
        self.remove_root_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_root_button.clicked.connect(self._remove_root_label)

        root_buttons_layout.addWidget(self.add_root_button)
        root_buttons_layout.addWidget(self.edit_root_button)
        root_buttons_layout.addWidget(self.remove_root_button)
        root_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(root_buttons_layout)

        # 2. Labels Niveau 1 (anciennement Parents)
        level1_label_title = QtWidgets.QLabel(
            tr("project_config.parent_labels_list_for_root_label")
        )
        level1_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(level1_label_title)

        self.level1_list_widget = QtWidgets.QListWidget()
        self.level1_list_widget.setStyleSheet(self._get_improved_list_style())
        self.level1_list_widget.setMinimumHeight(80)
        self.level1_list_widget.currentItemChanged.connect(self._on_level1_label_selected)
        hierarchy_group_layout.addWidget(self.level1_list_widget)

        level1_buttons_layout = QtWidgets.QHBoxLayout()
        level1_buttons_layout.setSpacing(5)

        self.add_level1_button = QtWidgets.QPushButton("Ajouter")
        self.add_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_level1_button.clicked.connect(self._add_level1_label)

        self.edit_level1_button = QtWidgets.QPushButton("Modifier")
        self.edit_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_level1_button.clicked.connect(self._edit_level1_label)

        self.remove_level1_button = QtWidgets.QPushButton("Supprimer")
        self.remove_level1_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_level1_button.clicked.connect(self._remove_level1_label)

        level1_buttons_layout.addWidget(self.add_level1_button)
        level1_buttons_layout.addWidget(self.edit_level1_button)
        level1_buttons_layout.addWidget(self.remove_level1_button)
        level1_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(level1_buttons_layout)

        # 3. Labels Enfants (Niveau 2)
        child_label_title = QtWidgets.QLabel("Labels enfants")
        child_label_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 11px;")
        hierarchy_group_layout.addWidget(child_label_title)

        self.child_list_widget = QtWidgets.QListWidget()
        self.child_list_widget.setStyleSheet(self._get_improved_list_style())
        self.child_list_widget.setMinimumHeight(80)
        self.child_list_widget.currentItemChanged.connect(self._on_child_label_selected)
        hierarchy_group_layout.addWidget(self.child_list_widget)

        child_buttons_layout = QtWidgets.QHBoxLayout()
        child_buttons_layout.setSpacing(5)

        self.add_child_button = QtWidgets.QPushButton("Ajouter")
        self.add_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.add_child_button.clicked.connect(self._add_child_label)

        self.edit_child_button = QtWidgets.QPushButton("Modifier")
        self.edit_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.edit_child_button.clicked.connect(self._edit_child_label)

        self.remove_child_button = QtWidgets.QPushButton("Supprimer")
        self.remove_child_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.remove_child_button.clicked.connect(self._remove_child_label)

        child_buttons_layout.addWidget(self.add_child_button)
        child_buttons_layout.addWidget(self.edit_child_button)
        child_buttons_layout.addWidget(self.remove_child_button)
        child_buttons_layout.addStretch()

        hierarchy_group_layout.addLayout(child_buttons_layout)

        hierarchy_layout.addWidget(hierarchy_group)
        middle_scroll.setWidget(middle_content)
        top_columns_layout.addWidget(middle_scroll, 4)

        # --- Colonne de droite: Relations ---
        right_column_layout = QtWidgets.QVBoxLayout()

        # Configuration des Relations en haut
        relations_group = QtWidgets.QGroupBox("Configuration des Relations")
        relations_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        relations_layout.addWidget(self.global_relations_config)
        right_column_layout.addWidget(relations_group)

        # Section graphe des relations
        graph_group = QtWidgets.QGroupBox("Graphe des Relations")
        graph_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        graph_layout = QtWidgets.QVBoxLayout(graph_group)
        graph_layout.addWidget(self.relations_graph)
        graph_group.setMinimumHeight(400)
        right_column_layout.addWidget(graph_group)

        # Boutons de sauvegarde/export/insert en bas
        save_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("💾 Sauvegarder Profil")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._on_save_project)
        self.save_button.setEnabled(False)
        save_layout.addWidget(self.save_button)

        self.export_profile_button = QtWidgets.QPushButton("📤 Exporter Profil")
        self.export_profile_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.export_profile_button.clicked.connect(self._on_export_profile)
        self.export_profile_button.setEnabled(False)
        save_layout.addWidget(self.export_profile_button)

        self.insert_dgraph_button = QtWidgets.QPushButton("🔄 Insérer dans Dgraph")
        self.insert_dgraph_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.insert_dgraph_button.clicked.connect(self._on_insert_dgraph)
        self.insert_dgraph_button.setEnabled(False)
        save_layout.addWidget(self.insert_dgraph_button)

        right_column_layout.addLayout(save_layout)
        right_column_layout.addStretch()

        top_columns_layout.addLayout(right_column_layout, 5)

        self.level1_list_widget.itemDoubleClicked.connect(self._on_double_click_item)
        self.child_list_widget.itemDoubleClicked.connect(self._on_double_click_item)

    def _load_project_profiles(self):
        """Charge les profils depuis Dgraph avec gestion d'erreur robuste."""
        try:
            logger.info("📡 Chargement des profils depuis Dgraph...")

            if not self.dgraph_connector or not self.dgraph_connector.client:
                logger.warning("⚠️ Dgraph client non disponible")
                return

            query_result = self.dgraph_connector.query_workspaces()

            if not query_result or 'q' not in query_result:
                logger.warning("⚠️ Aucun résultat depuis Dgraph")
                return

            workspaces = query_result['q']
            logger.info(f"📦 {len(workspaces)} workspace(s) récupéré(s) depuis Dgraph")

            loaded_count = 0
            for ws in workspaces:
                profile = self._workspace_to_profile(ws)
                if profile and profile.get('name'):
                    project_name = profile['name']

                    # ✅ ÉVITER LES DOUBLONS
                    if project_name not in self.project_profiles:
                        self.project_profiles[project_name] = profile
                        loaded_count += 1
                        logger.debug(f"   ✅ Chargé: {project_name}")
                    else:
                        logger.debug(f"   ⏭️ Doublon ignoré: {project_name}")

            logger.info(f"✅ Chargement Dgraph terminé: {loaded_count} profil(s) unique(s)")

        except Exception as e:
            logger.error(f"❌ ERREUR CRITIQUE dans _load_project_profiles: {e}")
            import traceback
            traceback.print_exc()

    def _get_file_content(self, file_path: str) -> str:
        """
        Récupère le contenu d'un fichier depuis la structure en mémoire ou le disque.
        """
        if not file_path:
            return ""

        # Essayer depuis current_root_data (pour les fichiers ouverts)
        if self.current_root_data:
            content = self.current_root_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Essayer depuis project_profile_data global
        if self.current_project_profile_data:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')
            if content:
                return content

        # Fallback : lecture directe du disque
        return self._read_file_content(file_path)  # Méthode existante
    #Interface a ameliorer
    def _show_code_snippet_dialog(self, filename: str, full_content: str, item_type: str, line_num: int, item_text: str):
        """
        Affiche une fenêtre moderne et élégante contenant un extrait de code centré sur une ligne donnée.
        """
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Snippet — {item_text}")
        dialog.setMinimumSize(1000, 600)
        dialog.setMaximumSize(1400, 900)

        # --- Palette de couleurs gris/blanc ---
        stylesheet = """
            QDialog {
                background-color: #f8f8f8;
                color: #1a1a1a;
            }
            QLabel {
                color: #1a1a1a;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #d0d0d0;
                color: #1a1a1a;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #b0b0b0;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
            QPlainTextEdit {
                font-family: 'Fira Code', 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 12px;
                line-height: 1.5;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #b0b0b0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #888888;
            }
        """
        dialog.setStyleSheet(stylesheet)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # --- En-tête avec titre et informations ---
        title_label = QLabel(f"<b style='font-size: 13pt; color: #1a1a1a'>{item_text}</b>")
        title_label.setStyleSheet("margin-bottom: 8px;")
        layout.addWidget(title_label)

        # --- Information détaillée ---
        info_parts = [
            f"<span style='color: #333333'><b>Type :</b></span> <span style='color: #555555'>{item_type.capitalize()}</span>",
            f"<span style='color: #333333'><b>Fichier :</b></span> <span style='color: #555555; font-family: monospace'>{os.path.basename(filename)}</span>",
            f"<span style='color: #333333'><b>Ligne :</b></span> <span style='color: #555555'>{line_num}</span>"
        ]
        info_label = QLabel(" • ".join(info_parts))
        info_label.setStyleSheet("""
            QLabel {
                background-color: #e8e8e8;
                border-left: 3px solid #2a2a2a;
                border-radius: 4px;
                padding: 10px 12px;
                color: #333333;
                font-size: 9pt;
            }
        """)
        layout.addWidget(info_label)

        # --- Zone de code avec numérotation ---
        code_editor = QPlainTextEdit()
        code_editor.setReadOnly(True)

        # Extraire le snippet
        lines = full_content.splitlines()
        snippet_start = max(0, line_num - 11)
        snippet_end = min(len(lines), line_num + 10)
        snippet_lines = lines[snippet_start:snippet_end]

        # Construire le snippet avec numérotation
        numbered_lines = []
        for i, line_content in enumerate(snippet_lines):
            actual_line_num = snippet_start + i + 1
            numbered_lines.append(f"{actual_line_num:4d} │ {line_content}")

        snippet = "\n".join(numbered_lines)
        if snippet_start > 0:
            snippet = f"     │ ... (lignes omises avant)\n{snippet}"
        if snippet_end < len(lines):
            snippet += f"\n     │ ... (lignes omises après)"

        code_editor.setPlainText(snippet)
        layout.addWidget(code_editor)

        # --- Surlignage de la ligne ciblée ---
        cursor = code_editor.textCursor()
        target_line = line_num - snippet_start
        if snippet_start > 0:
            target_line += 1

        for _ in range(target_line):
            cursor.movePosition(QTextCursor.Down)
        cursor.select(QTextCursor.LineUnderCursor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#f0f0f0"))
        fmt.setForeground(QColor("#1a1a1a"))
        cursor.mergeCharFormat(fmt)
        code_editor.setTextCursor(cursor)
        code_editor.ensureCursorVisible()

        # --- Boutons avec icônes textelles ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 8, 0, 0)

        copy_button = QPushButton("📋 Copier le code")
        copy_button.setMinimumHeight(36)
        copy_button.clicked.connect(lambda: self._copy_to_clipboard(snippet))
        button_layout.addWidget(copy_button)

        full_button = QPushButton("📄 Fichier complet")
        full_button.setMinimumHeight(36)
        full_button.clicked.connect(lambda: self._show_file_content_dialog(filename, full_content, {'label': item_text, 'type': item_type, 'line': line_num}))
        button_layout.addWidget(full_button)

        button_layout.addStretch()

        close_button = QPushButton("✕ Fermer")
        close_button.setMinimumHeight(36)
        close_button.setMaximumWidth(120)
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        dialog.exec_()

    def _show_file_content_dialog(self, filename: str, content: str, label: dict):
        """
        Affiche le contenu complet du fichier dans une fenêtre moderne et élégante.

        Args:
            filename: Nom du fichier
            content: Contenu du fichier
            label: Dictionnaire contenant 'label', 'type' et 'line'
        """
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout
        import os

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Fichier complet — {os.path.basename(filename)}")
        dialog.setMinimumSize(1200, 700)

        stylesheet = """
            QDialog {
                background-color: #f8f8f8;
                color: #1a1a1a;
            }
            QLabel {
                color: #1a1a1a;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #d0d0d0;
                color: #1a1a1a;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #b0b0b0;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
            QPlainTextEdit {
                font-family: 'Fira Code', 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 12px;
                line-height: 1.5;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #b0b0b0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #888888;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #b0b0b0;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #888888;
            }
        """
        dialog.setStyleSheet(stylesheet)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # --- En-tête ---
        title_label = QLabel(f"<b style='font-size: 13pt; color: #1a1a1a'>{label.get('label', 'Fichier')}</b>")
        layout.addWidget(title_label)

        # --- Information fichier ---
        info_parts = [
            f"<span style='color: #333333'><b>Fichier :</b></span> <span style='color: #555555; font-family: monospace'>{os.path.basename(filename)}</span>",
            f"<span style='color: #333333'><b>Type :</b></span> <span style='color: #555555'>{label.get('type', 'N/A').capitalize()}</span>",
            f"<span style='color: #333333'><b>Lignes totales :</b></span> <span style='color: #555555'>{len(content.splitlines())}</span>"
        ]
        file_info = QLabel(" • ".join(info_parts))
        file_info.setStyleSheet("""
            QLabel {
                background-color: #e8e8e8;
                border-left: 3px solid #888888;
                border-radius: 4px;
                padding: 10px 12px;
                color: #333333;
                font-size: 9pt;
            }
        """)
        layout.addWidget(file_info)

        # --- Zone de code avec numérotation complète ---
        code_editor = QPlainTextEdit()
        code_editor.setReadOnly(True)

        lines = content.splitlines()
        numbered_lines = []
        for i, line_content in enumerate(lines):
            line_num = i + 1
            numbered_lines.append(f"{line_num:5d} │ {line_content}")

        full_snippet = "\n".join(numbered_lines)
        code_editor.setPlainText(full_snippet)
        layout.addWidget(code_editor)

        # --- Surlignage de la ligne ciblée (si type spécifique) ---
        if label.get('type') in ['class', 'function', 'variable']:
            target_line_num = label.get('line', 1)
            cursor = code_editor.textCursor()

            for _ in range(target_line_num):
                cursor.movePosition(QTextCursor.Down)
            cursor.select(QTextCursor.LineUnderCursor)

            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#fff9c4"))
            fmt.setForeground(QColor("#1a1a1a"))
            cursor.mergeCharFormat(fmt)
            code_editor.setTextCursor(cursor)
            code_editor.ensureCursorVisible()

        # --- Boutons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 8, 0, 0)

        copy_all_button = QPushButton("📋 Copier tout")
        copy_all_button.setMinimumHeight(36)
        copy_all_button.clicked.connect(lambda: self._copy_to_clipboard(content))
        button_layout.addWidget(copy_all_button)

        button_layout.addStretch()

        close_button = QPushButton("✕ Fermer")
        close_button.setMinimumHeight(36)
        close_button.setMaximumWidth(120)
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        dialog.exec_()

    def _on_double_click_item(self, item):
        """
        Gère le double-clic sur un item de liste.
        - Pour classes/fonctions/variables : Affiche un snippet du fichier centré sur la ligne.
        - Pour fichiers/labels : Réutilise l'affichage existant (_on_double_click_label).
        """
        if not item:
            return

        item_type = item.data(Qt.UserRole + 1)  # Type stocké (ex. 'class', 'function', 'variable', 'file')

        if item_type in ['class', 'function', 'variable', 'method']:
            # Cas spécifique : snippet pour élément de code
            file_path = item.data(Qt.UserRole + 2)  # Chemin du fichier stocké
            line_num = item.data(Qt.UserRole + 3) or 1  # Numéro de ligne (int)

            # Récupérer le contenu du fichier (depuis current_root_data ou project_profile_data)
            content = self._get_file_content(file_path)
            if not content:
                QtWidgets.QMessageBox.warning(self, "Erreur", f"Impossible de charger le fichier {file_path}.")
                return

            # Extraire et afficher le snippet
            self._show_code_snippet_dialog(file_path, content, item_type, line_num, item.text())

        elif item_type in ['file', 'root_file', 'level1_file']:
            # Fallback : affichage complet du fichier (comme existant)
            uid = item.data(Qt.UserRole)
            label = self._find_label_by_uid(uid)
            if label:
                self._on_double_click_label(item)  # Réutilise la méthode existante si applicable
            else:
                # Ou directement afficher le fichier
                content = self._get_file_content(file_path)
                if content:
                    self._show_file_content_dialog(file_path, content, {'label': item.text()})

        else:
            # Pour les dossiers/labels généraux : affichage existant
            self._on_double_click_label(item)

    def _label_to_data(self, label):
        """Convertit un label Dgraph en data local avec parsing robuste des relations."""
        try:
            data = {
                'label': label.get('name', ''),
                'id': label.get('id', ''),
                'uid': label.get('uid', ''),
                'description': label.get('description', ''),
                'category': label.get('category', []),
                'files': label.get('files', []),
                'file_contents': {},
                'parents': [],
                'children': [],
                'outgoing_relations': [],
                'incoming_relations': []
            }

            # Parser fileContents
            label_file_contents_raw = label.get('fileContents', '{}')
            try:
                if isinstance(label_file_contents_raw, dict):
                    data['file_contents'] = label_file_contents_raw
                elif isinstance(label_file_contents_raw, str):
                    data['file_contents'] = json.loads(label_file_contents_raw.strip() or '{}')
                else:
                    data['file_contents'] = {}
            except json.JSONDecodeError:
                logger.warning(f"Erreur parsing fileContents pour label '{label.get('name')}'")
                data['file_contents'] = {}

            # ✅ RELATIONS SORTANTES (avec gestion d'erreur)
            try:
                for rel in label.get('relations', []):
                    source_node = rel.get('source', {})
                    target_node = rel.get('target', {})

                    # Vérifier que les données sont valides
                    if not source_node or not target_node:
                        continue
                    
                    source_uid = source_node.get('uid')
                    target_uid = target_node.get('uid')

                    # Vérifier que ce label est bien la source
                    if source_uid == label.get('uid') and target_uid:
                        data['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'target_id': target_node.get('id', ''),
                            'target_name': target_node.get('name', ''),
                            'relation_type': rel.get('relationType', 'relation'),
                            'category': 'custom'
                        })
            except Exception as e:
                logger.warning(f"Erreur parsing outgoing_relations pour '{label.get('name')}': {e}")

            # ✅ RELATIONS ENTRANTES (avec gestion d'erreur)
            try:
                for rel in label.get('~target', []):
                    source_node = rel.get('source', {})
                    target_node = rel.get('target', {})

                    # Vérifier que les données sont valides
                    if not source_node or not target_node:
                        continue
                    
                    source_uid = source_node.get('uid')
                    target_uid = target_node.get('uid')

                    # Vérifier que ce label est bien la cible
                    if target_uid == label.get('uid') and source_uid:
                        data['incoming_relations'].append({
                            'source_uid': source_uid,
                            'source_id': source_node.get('id', ''),
                            'source_name': source_node.get('name', ''),
                            'relation_type': rel.get('relationType', 'relation'),
                            'category': 'custom'
                        })
            except Exception as e:
                logger.warning(f"Erreur parsing incoming_relations pour '{label.get('name')}': {e}")

            # Log uniquement si des relations ont été trouvées
            total_relations = len(data['outgoing_relations']) + len(data['incoming_relations'])
            if total_relations > 0:
                logger.debug(f"✅ Label '{label.get('name')}': "
                             f"{len(data['outgoing_relations'])} sortantes, "
                             f"{len(data['incoming_relations'])} entrantes")

            return data

        except Exception as e:
            logger.error(f"❌ Erreur critique dans _label_to_data pour '{label.get('name', 'unknown')}': {e}")
            # Retourner une structure minimale valide
            return {
                'label': label.get('name', 'Unknown'),
                'id': label.get('id', ''),
                'uid': label.get('uid', ''),
                'description': '',
                'category': [],
                'files': [],
                'file_contents': {},
                'parents': [],
                'children': [],
                'outgoing_relations': [],
                'incoming_relations': []
            }

    def _fill_hierarchy(self, data, label_node):
        """Remplit récursivement les enfants et set les parents comme uids."""
        # Gérer l'inconsistance dans les clés de la requête Dgraph
        children_key = 'children' if 'children' in label_node else 'parents'
        children = label_node.get(children_key, [])

        for child in children:
            # ✅ Appeler _label_to_data pour parser les relations
            child_data = self._label_to_data(child)
            child_data['parents'] = [data['uid']]  # Set parent uid
            data['children'].append(child_data)

            # Récursif
            self._fill_hierarchy(child_data, child)

    def _workspace_to_profile(self, ws):
        """Convertit un workspace Dgraph en profil local avec mapping UID."""
        try:
            profile_name = ws.get('name', '')
            logger.info(f"🔍 Conversion workspace : {profile_name}")

            profile = {
                'uid': ws.get('uid', ''),
                'name': profile_name,
                'description': ws.get('description', ''),
                'files': ws.get('files', []),
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': defaultdict(list)
            }

            # 📋 PARSING ROBUSTE DE fileContents
            file_contents_raw = ws.get('fileContents', '{}')

            try:
                if isinstance(file_contents_raw, dict):
                    profile['file_contents'] = file_contents_raw
                elif isinstance(file_contents_raw, str):
                    file_contents_raw = file_contents_raw.strip()
                    if not file_contents_raw or file_contents_raw == '{}':
                        profile['file_contents'] = {}
                    else:
                        profile['file_contents'] = json.loads(file_contents_raw)
                elif isinstance(file_contents_raw, bytes):
                    file_contents_str = file_contents_raw.decode('utf-8').strip()
                    profile['file_contents'] = json.loads(file_contents_str) if file_contents_str else {}
                else:
                    logger.warning(f"Type inattendu pour fileContents: {type(file_contents_raw)}")
                    profile['file_contents'] = {}

            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur parsing fileContents pour workspace '{ws.get('name')}': {e}")
                profile['file_contents'] = {}

            # Parser clusters et labels
            cm = ws.get('clusterManagement', {})
            if not cm:
                logger.warning(f"Aucun clusterManagement pour workspace '{ws.get('name')}'")
                return profile

            for cluster in cm.get('clusters', []):
                cluster_data = {
                    'name': cluster.get('name', ''),
                    'uid': cluster.get('uid', ''),
                    'description': cluster.get('description', ''),
                    'files': cluster.get('files', []),
                    'file_contents': {},
                    'root_labels': []
                }

                # Parser fileContents du cluster
                cluster_file_contents_raw = cluster.get('fileContents', '{}')
                try:
                    if isinstance(cluster_file_contents_raw, dict):
                        cluster_data['file_contents'] = cluster_file_contents_raw
                    elif isinstance(cluster_file_contents_raw, str):
                        cluster_data['file_contents'] = json.loads(cluster_file_contents_raw.strip() or '{}')
                    elif isinstance(cluster_file_contents_raw, bytes):
                        cluster_data['file_contents'] = json.loads(cluster_file_contents_raw.decode('utf-8').strip() or '{}')
                    else:
                        cluster_data['file_contents'] = {}
                except json.JSONDecodeError:
                    logger.warning(f"Erreur parsing fileContents pour cluster '{cluster.get('name')}'")
                    cluster_data['file_contents'] = {}

                # Parser root labels
                for root_label in cluster.get('root_labels', []):
                    try:
                        root_data = self._label_to_data(root_label)
                        cluster_data['root_labels'].append(root_data)
                        # Remplir enfants récursivement
                        self._fill_hierarchy(root_data, root_label)
                    except Exception as e:
                        logger.error(f"❌ Erreur traitement root_label '{root_label.get('name')}': {e}")
                        continue

                profile['turing_ontology']['clusters_detailed'].append(cluster_data)

            return profile

        except Exception as e:
            logger.error(f"❌ ERREUR CRITIQUE dans _workspace_to_profile: {e}")
            import traceback
            traceback.print_exc()

            # Retourner un profil minimal valide pour ne pas bloquer l'UI
            return {
                'uid': ws.get('uid', ''),
                'name': ws.get('name', 'Projet Erreur'),
                'description': f"Erreur de chargement: {str(e)}",
                'files': [],
                'file_contents': {},
                'turing_ontology': {'clusters_detailed': []},
                'pending_relations': {}
            }

    def _update_project_combo(self):
        """Met à jour le combo des projets avec logging détaillé."""
        try:
            logger.info(f"🔄 Mise à jour combo: {len(self.project_profiles)} projet(s)")

            if not hasattr(self, 'project_combo'):
                logger.error("❌ project_combo n'existe pas encore!")
                return

            if self.project_combo is None:
                logger.error("❌ project_combo est None!")
                return

            self.project_combo.blockSignals(True)
            self.project_combo.clear()

            if not self.project_profiles:
                logger.warning("⚠️ Aucun projet à afficher")
                self.project_combo.addItem("(Aucun projet)")
                self.project_combo.blockSignals(False)
                return

            count = 0
            for name in sorted(self.project_profiles.keys()):
                self.project_combo.addItem(name)
                count += 1
                logger.debug(f"   ✅ Ajouté: {name}")

            self.project_combo.blockSignals(False)

            self.project_combo.update()
            self.project_combo.repaint()

            logger.info(f"✅ Combo mis à jour: {count} projet(s) affiché(s)")

            if count > 0 and not self.current_project_name:
                self.project_combo.setCurrentIndex(0)
                self._on_project_selected(0)

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour combo: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_selected(self, index):
        """Gère la sélection d'un projet dans la combo."""
        if index < 0:
            return
        project_name = self.project_combo.currentText()
        self.current_project_name = project_name
        self.current_project_profile_data = json.loads(json.dumps(self.project_profiles[project_name]))
        # Restore relations
        pending_relations_data = self.current_project_profile_data.get("pending_relations", {})
        self.pending_relations = defaultdict(list, pending_relations_data)
        self._load_project_data_into_ui()
        self._update_project_details()
        self._update_button_states()
        self._test_relations_loading()

    def _load_project_data_into_ui(self):
        """Charge les données du projet dans l'UI avec réinitialisation complète."""
        if not self.current_project_profile_data:
            return

        # Réinitialiser toute la hiérarchie
        self.current_cluster_data = None
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_cluster_index = -1
        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        # Vider toutes les listes
        self.cluster_list_widget.clear()
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Charger les informations de base
        self.project_name_edit.setText(self.current_project_profile_data.get('name', ''))
        self.project_description_edit.setPlainText(self.current_project_profile_data.get('description', ''))

        # Charger uniquement la liste des clusters
        self._refresh_cluster_list()

        # Collecter tous les labels pour les relations
        self._collect_all_labels()

        # Réinitialiser les relations et graphe
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

    def _update_project_details(self):
        """Met à jour les détails du projet sélectionné."""
        if self.current_project_name:
            details = f"Projet: {self.current_project_name}\n"
            details += f"Clusters: {len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []))}\n"
            details += f"Fichiers: {len(self.current_project_profile_data.get('files', []))}"
            self.details_text.setPlainText(details)

    def _refresh_cluster_list(self):
        """Rafraîchit la liste des clusters sans charger les niveaux inférieurs."""
        self.cluster_list_widget.clear()
        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        for cluster in clusters:
            self.cluster_list_widget.addItem(cluster["name"])

    def _on_cluster_selected(self, current):
        """
        Gère la sélection d'un cluster.
        Affiche les root labels + classes/fonctions/variables des fichiers du cluster.
        """
        if not current:
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_index = self.cluster_list_widget.row(current)

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])
        if self.current_cluster_index < 0 or self.current_cluster_index >= len(clusters):
            self.current_cluster_data = None
            self._reset_hierarchy_ui()
            return

        self.current_cluster_data = clusters[self.current_cluster_index]

        # Réinitialiser niveaux inférieurs
        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        # Afficher root labels + éléments de code des fichiers du cluster
        self._populate_root_list_with_cluster_files()

        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        # Afficher détails
        details = f"Cluster: {self.current_cluster_data.get('name', '')}\n"
        details += f"Description: {self.current_cluster_data.get('description', '')}\n"
        details += f"Root Labels: {len(self.current_cluster_data.get('root_labels', []))}\n"
        details += f"Fichiers: {len(self.current_cluster_data.get('files', []))}\n"
        self.details_text.setPlainText(details)

        self._update_button_states()

    def _on_level1_label_selected(self, current):
        """
        Gère la sélection dans level1_list (fichiers, children OU éléments de code).
        """
        if not current:
            self.current_level1_data = None
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)

        # === CAS 1 : Fichier sélectionné → afficher ses éléments dans child_list ===
        if item_type == 'root_file':
            file_path = current.data(Qt.UserRole + 2)
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            classes = self.dependency_parser.extract_classes(content, file_path)
            functions = self.dependency_parser.extract_functions(content, file_path)
            variables = self.dependency_parser.extract_variables(content, file_path)

            self._display_code_elements_in_list(
                self.child_list_widget,
                classes,
                functions,
                variables,
                file_path
            )

            details = f"📄 Fichier: {os.path.basename(file_path)}\n\n"
            details += f"Classes: {len(classes)}\n"
            details += f"Fonctions: {len(functions)}\n"
            details += f"Variables: {len(variables)}\n"
            self.details_text.setPlainText(details)

            self.current_selected_label_uid = None
            self.current_level1_data = None

        # === CAS 2 : Child sélectionné → afficher ses fichiers + children + éléments ===
        elif item_type in ['folder', 'file', 'child']:
            item_uid = current.data(Qt.UserRole)
            self.current_selected_label_uid = item_uid

            child_data = self._find_child_by_uid(self.current_root_data, item_uid)

            if child_data:
                self.current_level1_data = child_data
                self._update_selected_details("Niveau 1", child_data)

                self._populate_child_list_with_parent_files()

                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)

        # === CAS 3 : Élément de code sélectionné ===
        elif item_type in ['class', 'function', 'variable']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            details = f"Type: {item_type.upper()}\n"
            details += f"Fichier: {os.path.basename(file_path)}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

            self.child_list_widget.clear()

        self._update_button_states()

    def _populate_level1_list(self):
        """
        Peuple TOUS les enfants du root label : 
        - Hiérarchiques (fichiers/dossiers)
        - Extraits (classes/fonctions/variables du fichier racine)
        """
        self.level1_list_widget.clear()
    
        if not self.current_root_data:
            return
    
        # 1. Afficher les enfants hiérarchiques
        for level1 in self.current_root_data.get("children", []):
            child_type = level1.get('type', 'folder')
            icon = self._get_node_icon(child_type)
            display = f"{icon} {level1.get('label', level1.get('name', 'Sans nom'))}"
    
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, level1.get("uid", level1.get("id", "")))
            item.setData(Qt.UserRole + 1, child_type)
            item.setData(Qt.UserRole + 2, None)  # Pas de ligne
            self.level1_list_widget.addItem(item)
    
        # 2. Afficher les classes du root label lui-même
        classes = self.current_root_data.get('classes', [])
        for cls in classes:
            display = f"🛑 {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)
            
            cls_uid = cls.get('uid', f"cls_{str(uuid.uuid4())}")
            if 'uid' not in cls:
                cls['uid'] = cls_uid
            
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            self.level1_list_widget.addItem(item)
    
        # 3. Afficher les fonctions du root label lui-même
        functions = self.current_root_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "⚙️" if func_type == "method" else "🔧"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)
            
            func_uid = func.get('uid', f"func_{str(uuid.uuid4())}")
            if 'uid' not in func:
                func['uid'] = func_uid
            
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            self.level1_list_widget.addItem(item)
    
        # 4. Afficher les variables du root label
        variables = self.current_root_data.get('variables', [])
        for var in variables:
            display = f"📦 {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)
            
            var_uid = var.get('uid', f"var_{str(uuid.uuid4())}")
            if 'uid' not in var:
                var['uid'] = var_uid
            
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            self.level1_list_widget.addItem(item)
    
        self._update_button_states()

    def _add_child_to_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste, récursivement pour les sous-dossiers.
        SANS icônes.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_list(grandchild, list_widget, indent + "  ")

    def _show_code_elements_popup(self, file_name, classes, functions, variables, file_path):
        """
        Affiche une popup avec les classes/fonctions/variables d'un fichier.
        Utilisé pour les fichiers des labels enfants (plus de place dans l'UI).

        Args:
            file_name: Nom du fichier
            classes: Liste des classes
            functions: Liste des fonctions
            variables: Liste des variables
            file_path: Chemin complet du fichier
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Éléments de code : {file_name}")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"<b>Fichier :</b> {file_name}<br><b>Chemin :</b> {file_path}")
        header.setWordWrap(True)
        layout.addWidget(header)

        # Stats
        stats = QLabel(
            f"<b>Classes :</b> {len(classes)} | "
            f"<b>Fonctions :</b> {len(functions)} | "
            f"<b>Variables :</b> {len(variables)}"
        )
        stats.setStyleSheet("color: #34495e; font-size: 11pt; padding: 5px;")
        layout.addWidget(stats)

        # Liste
        list_widget = QListWidget()
        list_widget.setStyleSheet(self._get_improved_list_style())
        self._display_code_elements_in_list(list_widget, classes, functions, variables, file_path)
        layout.addWidget(list_widget)

        # Boutons
        button_layout = QHBoxLayout()

        view_file_button = QPushButton("📄 Voir le fichier")
        view_file_button.clicked.connect(
            lambda: self._show_file_content_dialog(
                file_name,
                self.current_project_profile_data.get('file_contents', {}).get(file_path, ''),
                {'label': file_name, 'uid': str(uuid.uuid4())}
            )
        )
        button_layout.addWidget(view_file_button)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.exec_()

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        Peuple la liste enfant avec la hiérarchie correcte:
        - Classes (avec sous-items méthodes)
        - Fonctions
        - Variables

        Chaque élément peut être sélectionné pour voir ses relations et détails.
        """
        list_widget.clear()
        if not file_data:
            return

        children = file_data.get('children', [])

        if not children:
            list_widget.addItem(QListWidgetItem("(Aucun élément trouvé)"))
            return

        # Afficher les enfants organisés par type
        for child in children:
            child_type = child.get('type', 'unknown')
            child_uid = child.get('uid')

            if not child_uid:
                child_uid = child.get('id', str(uuid.uuid4()))
                child['uid'] = child_uid

            # === CLASSE ===
            if child_type == 'class':
                icon = '[CLS]'
                class_name = child.get('name', 'Class')
                line_num = child.get('line', '?')
                methods_count = len(child.get('children', []))

                # Format: [CLS] ClassName (3 methods) - line 42
                display = f"{icon} {class_name}"
                if methods_count > 0:
                    display += f" ({methods_count} methods)"
                display += f" - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'class')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#FF9800"))  # Orange
                list_widget.addItem(item)

                # Ajouter les méthodes comme sous-items indentés
                for method in child.get('children', []):
                    method_uid = method.get('uid')
                    if not method_uid:
                        method_uid = str(uuid.uuid4())
                        method['uid'] = method_uid

                    method_name = method.get('name', 'method')
                    method_line = method.get('line', '?')

                    # Indentation pour sous-item
                    method_display = f"  ├─ {method_name} (ligne {method_line})"
                    method_item = QListWidgetItem(method_display)
                    method_item.setData(Qt.UserRole, method_uid)
                    method_item.setData(Qt.UserRole + 1, 'method')
                    method_item.setData(Qt.UserRole + 2, method_line)
                    method_item.setForeground(QtGui.QColor("#FFA500"))  # Orange clair
                    list_widget.addItem(method_item)

            # === FONCTION ===
            elif child_type in ['function', 'method']:
                icon = '[FNC]'
                func_name = child.get('name', 'Function')
                line_num = child.get('line', '?')
                func_type = child.get('type', 'function')

                display = f"{icon} {func_name} - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, func_type)
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#2196F3"))  # Bleu
                list_widget.addItem(item)

            # === VARIABLE ===
            elif child_type == 'variable':
                icon = '[VAR]'
                var_name = child.get('name', 'Variable')
                var_type = child.get('var_type', 'local')
                line_num = child.get('line', '?')

                display = f"{icon} {var_name} ({var_type}) - ligne {line_num}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, 'variable')
                item.setData(Qt.UserRole + 2, line_num)
                item.setForeground(QtGui.QColor("#4CAF50"))  # Vert
                list_widget.addItem(item)

            # === AUTRES (fichiers, dossiers, etc.) ===
            else:
                icon = self._get_node_icon(child_type)
                child_name = child.get('label', child.get('name', 'unknown'))

                display = f"{icon} {child_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _on_child_label_selected(self, current):
        """
        Gère la sélection dans child_list.
        Si fichier → POPUP avec éléments de code
        Si child → met à jour les détails
        Si élément de code → affiche détails
        """
        if not current:
            self.current_level2_data = None
            return

        item_type = current.data(Qt.UserRole + 1)

        # === CAS 1 : Fichier sélectionné → POPUP ===
        if item_type == 'level1_file':
            file_path = current.data(Qt.UserRole + 2)
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            # Pré-extraire les éléments pour passer à la popup (optionnel ; la popup peut extraire elle-même)
            classes = self.dependency_parser.extract_classes(content, file_path)
            functions = self.dependency_parser.extract_functions(content, file_path)
            variables = self.dependency_parser.extract_variables(content, file_path)

            # Créer parent_data avec les éléments extraits
            parent_data = {
                'classes': classes,
                'functions': functions,
                'variables': variables,
                'children': self.current_level1_data.get('children', []) if self.current_level1_data else []
            }

            # Instancier la popup (remplace l'appel à _show_code_elements_popup)
            popup = CodeElementsPopup(
                os.path.basename(file_path),
                file_path,
                content,  # file_content
                parent_data,
                self  # parent widget pour accès aux méthodes comme _show_code_snippet_dialog
            )
            popup.exec_()  # Ouvre la popup modale

        # === CAS 2 : Child sélectionné ===
        elif item_type in ['folder', 'file', 'child']:
            item_uid = current.data(Qt.UserRole)
            self.current_selected_label_uid = item_uid

            child_data = self._find_child_by_uid(self.current_level1_data, item_uid)

            if child_data:
                self.current_level2_data = child_data
                self._update_selected_details("Niveau 2", child_data)

                self.global_relations_config.update_current(self.current_selected_label_uid)
                self.relations_graph.update_graph(self.current_selected_label_uid)

        # === CAS 3 : Élément de code sélectionné ===
        elif item_type in ['class', 'function', 'variable']:
            file_path = current.data(Qt.UserRole + 2)
            line = current.data(Qt.UserRole + 3)

            details = f"Type: {item_type.upper()}\n"
            details += f"Fichier: {os.path.basename(file_path)}\n"
            details += f"Ligne: {line}\n"
            self.details_text.setPlainText(details)

        self._update_button_states()

    def _display_code_elements_in_list(self, list_widget, classes, functions, variables, file_path):
        """
        Affiche classes/fonctions/variables dans une liste avec préfixes distinctifs.

        Args:
            list_widget: QListWidget cible
            classes: Liste des classes
            functions: Liste des fonctions
            variables: Liste des variables
            file_path: Chemin du fichier source
        """
        list_widget.clear()

        if not classes and not functions and not variables:
            empty_item = QListWidgetItem("(Aucun élément trouvé)")
            empty_item.setForeground(QtGui.QColor("#95a5a6"))
            list_widget.addItem(empty_item)
            return

        # === CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#e74c3c"))  # Rouge
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

            # Méthodes indentées
            for method in cls.get('methods', []):
                method_item = QListWidgetItem(f"  ↳ {method.get('name', 'method')} (ligne {method.get('line', '?')})")
                method_item.setData(Qt.UserRole, str(uuid.uuid4()))
                method_item.setData(Qt.UserRole + 1, 'method')
                method_item.setData(Qt.UserRole + 2, method.get('line', 0))
                method_item.setForeground(QtGui.QColor("#c0392b"))
                list_widget.addItem(method_item)

        # === FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#3498db"))  # Bleu
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        # === VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'local')

            item = QListWidgetItem(f"[VAR] {var['name']} ({var_type}, ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setData(Qt.UserRole + 3, file_path)
            item.setForeground(QtGui.QColor("#2ecc71"))  # Vert
            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            list_widget.addItem(item)

        logger.info(f"Affiché {len(classes)} classes, {len(functions)} fonctions, {len(variables)} variables")

    def _on_any_label_selected(self, current):
        """
        Handles selection of ANY label (root, level1, level2, child).
        Updates relations config and graph for the selected node.

        This is a unified handler to avoid code duplication across different
        list widgets.
        """
        if current:
            # Get UID from the selected item
            uid = current.data(Qt.UserRole)

            if not uid:
                logger.warning("Selected item has no UID")
                self.current_selected_label_uid = None
                self.global_relations_config.update_current(None)
                self.relations_graph.update_graph(None)
                return

            self.current_selected_label_uid = uid

            # Update relations config and graph
            self.global_relations_config.update_current(uid)
            self.relations_graph.update_graph(uid)

            logger.debug(f"Label sélectionné: {uid}")
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _on_any_label_selected(self, current):
        """Gère la sélection de n'importe quel label pour relations et graphe."""
        if current:
            self.current_selected_label_uid = current.data(Qt.UserRole)
            self.global_relations_config.update_current(self.current_selected_label_uid)
            self.relations_graph.update_graph(self.current_selected_label_uid)
        else:
            self.current_selected_label_uid = None
            self.global_relations_config.update_current(None)
            self.relations_graph.update_graph(None)

    def _update_selected_details(self, title, data):
        """Met à jour les détails de l'élément sélectionné. Amélioration pour clusters-fichiers."""
        if not data:
            self.details_text.clear()
            return

        is_file_cluster = data.get('is_file_cluster', False)
        if is_file_cluster:
            details = f"=== {title} ===\n\n"
            details += f"Nom: {data.get('name', '')}\n"
            details += f"Description: {data.get('description', '')}\n\n"
            files = data.get('files', [])
            if files:
                details += f"Fichier: {files[0]}\n"  # Un seul fichier pour file-cluster
                content = data.get('file_contents', {}).get(files[0], '')
                details += f"Contenu (résumé): {content[:200]}..." if len(content) > 200 else f"Contenu: {content}"
            else:
                details += "Aucun fichier associé\n"
            # Pas de hiérarchie/relations pour file-cluster
            details += "\nNote: Pas de hiérarchie ni relations pour un cluster-fichier."
            self.details_text.setPlainText(details)
            return

        # Comportement normal pour labels (inchangé)
        details = f"=== {title} ===\n\n"
        details += f"Nom: {data.get('label', '')}\n"
        details += f"ID: {data.get('id', '')}\n"
        details += f"UID: {data.get('uid', '')}\n"
        details += f"Description: {data.get('description', '')}\n\n"

        categories = data.get('category', [])
        if categories:
            details += f"Catégories: {', '.join(categories)}\n\n"

        files = data.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:10]:  # Limiter à 10 fichiers pour l'affichage
                details += f"  - {f}\n"
            if len(files) > 10:
                details += f"  ... et {len(files) - 10} autres\n"
        else:
            details += "Aucun fichier associé\n"

        # Relations sortantes
        outgoing = data.get('outgoing_relations', [])
        if outgoing:
            details += f"\nRelations sortantes ({len(outgoing)}):\n"
            for r in outgoing:
                target_name = self.label_uid_to_info.get(r['target_uid'], {}).get('name', 'Inconnu')
                details += f"  {r['relation_type'].upper()} -> {target_name}\n"

        # Relations entrantes
        incoming = data.get('incoming_relations', [])
        if incoming:
            details += f"\nRelations entrantes ({len(incoming)}):\n"
            for r in incoming:
                source_name = self.label_uid_to_info.get(r['source_uid'], {}).get('name', 'Inconnu')
                details += f"  {source_name} {r['relation_type'].upper()} -> \n"

        # Ajouter info sur la hiérarchie
        if title == "Label Racine":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"
        elif title == "Label Niveau 1":
            nb_children = len(data.get('children', []))
            details += f"\nNombre d'enfants: {nb_children}"

        self.details_text.setPlainText(details)

    def _reset_hierarchy_ui(self):
        """Réinitialise complètement l'interface hiérarchique."""
        self.root_list_widget.clear()
        self.level1_list_widget.clear()
        self.child_list_widget.clear()

        self.current_root_data = None
        self.current_level1_data = None
        self.current_level2_data = None

        self.current_root_label_index = -1
        self.current_level1_label_index = -1
        self.current_level2_label_index = -1

        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)

        self.details_text.clear()

    def _collect_all_labels(self):
        """
        MODIFIÉE: Collecte tous les labels ET les classes, fonctions, variables
        pour les ajouter à label_uid_to_info.
        """
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()

        if not self.current_project_profile_data:
            return

        ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = ontology.get("clusters_detailed", [])

        for cluster in clusters_detailed:
            cluster_name = cluster.get('name', '')
            root_labels = cluster.get("root_labels", [])

            for root in root_labels:
                uid = root.get('uid') or root.get('id') or str(uuid.uuid4())

                # S'assurer que uid est défini
                if 'uid' not in root:
                    root['uid'] = uid

                info = {'name': root.get('label', ''), 'cluster': cluster_name, 'type': 'label'}
                self.label_uid_to_info[uid] = info
                self.name_to_uid[root.get('label', '')] = uid

                # Collecter récursivement les enfants et les classes/fonctions/variables
                self._collect_labels_recursive(root, cluster_name)

    def _collect_labels_recursive(self, node, cluster_name=''):
        """
        MODIFIÉE: Collecte récursivement labels, classes, fonctions et variables
        dans label_uid_to_info.
        """
        children = node.get('children', [])

        for child in children:
            # Safe fallback: priorité uid > id > générer nouveau
            uid = child.get('uid')
            if not uid:
                uid = child.get('id')
            if not uid:
                uid = str(uuid.uuid4())

            # S'assurer que uid est défini sur le nœud
            if 'uid' not in child:
                child['uid'] = uid

            # Récupérer le cluster du parent
            parent_uid = node.get('uid')
            parent_cluster = self.label_uid_to_info.get(parent_uid, {}).get('cluster', cluster_name)

            info = {
                'name': child.get('label', ''),
                'cluster': parent_cluster,
                'type': child.get('type', 'label')
            }
            self.label_uid_to_info[uid] = info

            label_name = child.get('label', '')
            if label_name:
                self.name_to_uid[label_name] = uid

            # Appel récursif pour les enfants
            self._collect_labels_recursive(child, parent_cluster)

        # NOUVEAU: Collecter les classes du nœud courant
        classes = node.get('classes', [])
        for cls in classes:
            cls_uid = cls.get('uid', f"cls_{cls.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            info = {
                'name': cls.get('name', ''),
                'cluster': cluster_name,
                'type': 'class',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[cls_uid] = info

        # NOUVEAU: Collecter les fonctions du nœud courant
        functions = node.get('functions', [])
        for func in functions:
            func_uid = func.get('uid', f"func_{func.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in func:
                func['uid'] = func_uid

            info = {
                'name': func.get('name', ''),
                'cluster': cluster_name,
                'type': 'function',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[func_uid] = info

        # NOUVEAU: Collecter les variables du nœud courant
        variables = node.get('variables', [])
        for var in variables:
            var_uid = var.get('uid', f"var_{var.get('name', '')}_{str(uuid.uuid4())}")
            if 'uid' not in var:
                var['uid'] = var_uid

            info = {
                'name': var.get('name', ''),
                'cluster': cluster_name,
                'type': 'variable',
                'parent_label': node.get('label', '')
            }
            self.label_uid_to_info[var_uid] = info

    def _add_cluster(self):
        dialog = AddEditItemDialog("Ajouter Cluster", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_cluster = {
                    "name": data["name"],
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "files": [],
                    "file_contents": {},
                    "root_labels": []
                }
                self.current_project_profile_data["turing_ontology"]["clusters_detailed"].append(new_cluster)
                self._refresh_cluster_list()
                self._collect_all_labels()
                self.cluster_list_widget.setCurrentRow(self.cluster_list_widget.count() - 1)
                self._update_button_states()
                logger.info(f"Cluster ajouté: {data['name']}")

    def _edit_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
        dialog = AddEditItemDialog("Modifier Cluster", cluster["name"], cluster["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                cluster["name"] = data["name"]
                cluster["description"] = data["description"]
                self._refresh_cluster_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Cluster modifié: {data['name']}")

    def _remove_cluster(self):
        current = self.cluster_list_widget.currentItem()
        if not current:
            return
        index = self.cluster_list_widget.row(current)
        cluster_name = self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]["name"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le cluster '{cluster_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_project_profile_data["turing_ontology"]["clusters_detailed"][index]
            self._refresh_cluster_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Cluster supprimé: {cluster_name}")

    def _add_root_label(self):
        """Ajoute un label racine avec vérification des fichiers."""
        if not self.current_cluster_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Racine", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_root = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_cluster_data["root_labels"].append(new_root)
                self._populate_root_list()
                self.root_list_widget.setCurrentRow(self.root_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine ajouté: {data['name']}")

    def _edit_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root = self.current_cluster_data["root_labels"][index]
        dialog = AddEditItemDialog("Modifier Label Racine", root["label"], root["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                root["label"] = data["name"]
                root["description"] = data["description"]
                self._populate_root_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label racine modifié: {data['name']}")

    def _remove_root_label(self):
        current = self.root_list_widget.currentItem()
        if not current:
            return
        index = self.root_list_widget.row(current)
        root_name = self.current_cluster_data["root_labels"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label racine '{root_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_cluster_data["root_labels"][index]
            self._populate_root_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label racine supprimé: {root_name}")

    def _add_level1_label(self):
        """Ajoute un label niveau 1 avec vérification des fichiers."""
        if not self.current_root_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 1", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_level1 = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_root_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_root_data["children"].append(new_level1)
                self._populate_level1_list()
                self.level1_list_widget.setCurrentRow(self.level1_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 ajouté: {data['name']}")

    def _edit_level1_label(self):
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1 = self.current_root_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 1", level1["label"], level1["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                level1["label"] = data["name"]
                level1["description"] = data["description"]
                self._populate_level1_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 1 modifié: {data['name']}")

    def _remove_level1_label(self): 
        current = self.level1_list_widget.currentItem()
        if not current:
            return
        index = self.level1_list_widget.row(current)
        level1_name = self.current_root_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 1 '{level1_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_root_data["children"][index]
            self._populate_level1_list()
            self._reset_hierarchy_ui()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 1 supprimé: {level1_name}")

    def _add_child_label(self):
        """Ajoute un label enfant avec vérification des fichiers."""
        if not self.current_level1_data:
            return
        dialog = AddEditItemDialog("Ajouter Label Niveau 2", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                new_child = {
                    "label": data["name"],
                    "id": str(uuid.uuid4()),
                    "uid": str(uuid.uuid4()),
                    "description": data["description"],
                    "category": [],
                    "files": [],
                    "file_contents": {},
                    "parents": [self.current_level1_data['uid']],
                    "children": [],
                    "outgoing_relations": [],
                    "incoming_relations": []
                }
                self.current_level1_data["children"].append(new_child)
                self._populate_child_list()
                self.child_list_widget.setCurrentRow(self.child_list_widget.count() - 1)
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 ajouté: {data['name']}")

    def _edit_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child = self.current_level1_data["children"][index]
        dialog = AddEditItemDialog("Modifier Label Niveau 2", child["label"], child["description"], self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                child["label"] = data["name"]
                child["description"] = data["description"]
                self._populate_child_list()
                self._collect_all_labels()
                self._update_button_states()
                logger.info(f"Label niveau 2 modifié: {data['name']}")

    def _remove_child_label(self):
        current = self.child_list_widget.currentItem()
        if not current:
            return
        index = self.child_list_widget.row(current)
        child_name = self.current_level1_data["children"][index]["label"]
        reply = QtWidgets.QMessageBox.question(self, "Confirmer", f"Supprimer le label niveau 2 '{child_name}'?")
        if reply == QtWidgets.QMessageBox.Yes:
            del self.current_level1_data["children"][index]
            self._populate_child_list()
            self._collect_all_labels()
            self._update_button_states()
            logger.info(f"Label niveau 2 supprimé: {child_name}")

    def _add_all_files_from_dir(self, dir_path, base_dir, label, profile):
        """Ajoute récursivement tous les fichiers d'un dossier à un label."""
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                content = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                label['files'].append(rel_path)
                label['file_contents'][rel_path] = content

    def _build_sub_hierarchy(self, dir_path, base_dir, parent_label, is_parents=True, profile=None):
        """Construit la hiérarchie récursivement à partir d'un dossier."""
        level_key = 'children' if is_parents else 'children'
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            rel_path = os.path.relpath(item_path, base_dir)
            if os.path.isfile(item_path):
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                if profile:
                    profile['files'].append(rel_path)
                    profile['file_contents'][rel_path] = content
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Fichier: {rel_path}",
                    'category': ['file'],
                    'files': [rel_path],
                    'file_contents': {rel_path: content},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
            elif os.path.isdir(item_path):
                new_label = {
                    'label': item,
                    'id': str(uuid.uuid4()),
                    'uid': str(uuid.uuid4()),
                    'description': f"Dossier: {rel_path}",
                    'category': ['folder'],
                    'files': [],
                    'file_contents': {},
                    'parents': [parent_label['uid']],
                    'children': [],
                    'outgoing_relations': [],
                    'incoming_relations': []
                }
                parent_label[level_key].append(new_label)
                if is_parents:
                    self._build_sub_hierarchy(item_path, base_dir, new_label, False, profile)
                else:
                    # Pour le niveau children, ajouter les fichiers profonds au label
                    self._add_all_files_from_dir(item_path, base_dir, new_label, profile)

    def _scan_project_directory(self, directory):
        """Scanne un dossier et crée une structure hiérarchique avec un cluster par élément de niveau supérieur."""
        profile = {
            'name': os.path.basename(directory),
            'description': f"Projet importé depuis {directory}",
            'files': [],
            'file_contents': {},
            'turing_ontology': {
                'clusters_detailed': []
            },
            'pending_relations': {}
        }
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            cluster = {
                'name': item,
                'uid': str(uuid.uuid4()),
                'description': f"{'Fichier' if os.path.isfile(item_path) else 'Dossier'}: {item}",
                'files': [],
                'file_contents': {},
                'root_labels': [],
                'is_file_cluster': False  # Nouveau flag
            }
            if os.path.isfile(item_path):
                # Traitement pour fichier : associer directement au cluster, sans root_labels
                rel_path = item
                content = ''
                try:
                    with open(item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {item_path}: {e}")
                profile['files'].append(rel_path)
                profile['file_contents'][rel_path] = content
                cluster['files'].append(rel_path)
                cluster['file_contents'][rel_path] = content
                cluster['is_file_cluster'] = True  # Flag pour indiquer cluster-fichier
                cluster['description'] += f"\nContenu résumé: {content[:100]}..." if len(content) > 100 else f"\nContenu: {content}"
            elif os.path.isdir(item_path):
                # Comportement inchangé pour dossiers : créer root_labels
                cluster['is_file_cluster'] = False
                # Ajouter les contenus directs comme root_labels
                for subitem in sorted(os.listdir(item_path)):
                    subitem_path = os.path.join(item_path, subitem)
                    sub_rel_path = os.path.relpath(subitem_path, directory)
                    if os.path.isfile(subitem_path):
                        content = ''
                        try:
                            with open(subitem_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read {subitem_path}: {e}")
                        profile['files'].append(sub_rel_path)
                        profile['file_contents'][sub_rel_path] = content
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'uid': str(uuid.uuid4()),
                            'description': f"Fichier: {sub_rel_path}",
                            'category': ['file'],
                            'files': [sub_rel_path],
                            'file_contents': {sub_rel_path: content},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                    elif os.path.isdir(subitem_path):
                        new_root = {
                            'label': subitem,
                            'id': str(uuid.uuid4()),
                            'uid': str(uuid.uuid4()),
                            'description': f"Dossier: {sub_rel_path}",
                            'category': ['folder'],
                            'files': [],
                            'file_contents': {},
                            'parents': [],
                            'children': [],
                            'outgoing_relations': [],
                            'incoming_relations': []
                        }
                        cluster['root_labels'].append(new_root)
                        # Construire la hiérarchie pour ce sous-dossier
                        self._build_sub_hierarchy(subitem_path, directory, new_root, True, profile)
            profile['turing_ontology']['clusters_detailed'].append(cluster)
        logger.info(f"Scanné {len(profile['files'])} fichiers depuis {directory}")
        return profile

    def _on_upload_local_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet local")
        if directory:
            scanned_data = self._scan_project_directory(directory)
            project_name = scanned_data['name']
            self.project_profiles[project_name] = json.loads(json.dumps(scanned_data))
            self._update_project_combo()
            self.project_combo.setCurrentText(project_name)
            self._on_project_selected(self.project_combo.currentIndex())
            logger.info(f"Upload local complété pour: {directory}")

    def _on_add_new_project(self):
        """Crée un nouveau projet vide."""
        dialog = AddEditItemDialog("Nouveau Projet", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"]:
                project_name = data["name"]
                self.project_profiles[project_name] = {
                    'name': project_name,
                    'description': data["description"],
                    'files': [],
                    'file_contents': {},
                    'turing_ontology': {
                        'clusters_detailed': []
                    },
                    'pending_relations': {}
                }
                self._update_project_combo()
                self.project_combo.setCurrentText(project_name)
                self._on_project_selected(self.project_combo.currentIndex())
                logger.info(f"Nouveau projet créé : {project_name}")

    def _on_delete_project(self):
        """Suppression complète d'un projet depuis l'UI, Dgraph et SQLite."""
        if not self.current_project_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        project_name = self.project_combo.currentText()
        uid = self.current_project_profile_data.get('uid') if self.current_project_profile_data else None

        if not uid:
            logger.warning(f"Aucun UID trouvé pour le projet {project_name}")
            QtWidgets.QMessageBox.warning(self, "Erreur", f"UID manquant pour '{project_name}'.")
            return

        # Confirmation utilisateur
        reply = QtWidgets.QMessageBox.question(
            self,
            "Suppression du projet",
            f"Voulez-vous vraiment supprimer le projet '{project_name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            uids_to_delete = self._collect_uids_to_delete(uid)
            if not uids_to_delete:
                logger.warning("Aucun UID à supprimer.")
                return

            # Supprimer de Dgraph si disponible
            dgraph_deleted = True
            if self.dgraph_connector.client:
                dgraph_deleted = self._collect_and_delete_uids(uids_to_delete, project_name)

            # Supprimer de SQLite via CRUD
            sqlite_deleted = self._delete_project_from_sqlite(uid)

            if dgraph_deleted and sqlite_deleted:
                logger.info(f"Supprimé de Dgraph et SQLite : {project_name}")

                # Supprimer du cache local
                if project_name in self.project_profiles:
                    del self.project_profiles[project_name]
                self._update_project_combo()  # Refresh la combo

                # Reset UI
                self._reset_ui()
                self.current_project_name = None

                QtWidgets.QMessageBox.information(self, "Succès", f"Projet '{project_name}' supprimé.")
            else:
                QtWidgets.QMessageBox.warning(self, "Partiel", f"Supprimé de {'Dgraph et ' if dgraph_deleted else ''}SQLite, mais échec sur {'Dgraph' if not dgraph_deleted else 'SQLite'}.")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression : {e}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur : {str(e)}")

    def _collect_uids_to_delete(self, uid):
        """
        Collecte récursivement tous les UIDs à supprimer liés à un workspace.
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph client non initialisé.")
            return []

        uids_to_delete = set()

        # Requête récursive pour collecter tous les noeuds liés
        gc_query = f"""
        {{
          nodes(func: uid({uid})) @recurse(loop: false) {{
            uid
            children
            parents
            clusters
            relations
            imports
          }}
        }}
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp_gc = txn.query(gc_query)
            txn.discard()

            data_gc = self.dgraph_connector._parse_response(resp_gc)
            for node in data_gc.get('nodes', []):
                if 'uid' in node:
                    uids_to_delete.add(node['uid'])

            logger.info(f"{len(uids_to_delete)} UID(s) collecté(s) pour suppression.")
            return list(uids_to_delete)

        except Exception as e:
            logger.error(f"Erreur lors de la collecte des UID à supprimer : {e}")
            return []

    def _collect_and_delete_uids(self, uids, project_name=None):
        """Supprime les UIDs collectés via mutation DELETE + vérif post-suppression dynamique (non-bloquante)."""
        if not uids or not self.dgraph_connector.client:
            return False

        txn = self.dgraph_connector.client.txn()
        committed = False
        try:
            del_objs = [{"uid": uid} for uid in uids]
            assigned = txn.mutate(del_obj=del_objs)
            txn.commit()
            committed = True
            logger.info(f"Supprimés {len(uids)} nœuds avec succès.")

            # Vérification optionnelle : Dynamique sur le nom du projet
            if project_name:
                try:
                    # Échappement basique pour le regexp (ajustez si noms complexes)
                    escaped_name = project_name.replace('/', '\\/').replace('\\', '\\\\')
                    verify_query = f"""
                    {{
                      q(func: has(name)) @filter(regexp(name, /.*{escaped_name}.*/i)) {{
                        uid
                      }}
                    }}
                    """
                    txn_verify = self.dgraph_connector.client.txn(read_only=True)
                    resp_verify = txn_verify.query(verify_query)
                    txn_verify.discard()
                    data_verify = self.dgraph_connector._parse_response(resp_verify)
                    remaining = len(data_verify.get('q', []))
                    if remaining > 0:
                        logger.warning(f"ATTENTION : {remaining} résidus pour '{project_name}' encore présents après suppression. Relance manuelle recommandée.")
                    else:
                        logger.info(f"Vérification OK : Aucune résidu pour '{project_name}' trouvé.")
                except Exception as ve:
                    logger.warning(f"Vérification post-suppression pour '{project_name}' échouée (non critique) : {ve}. La suppression principale a réussi.")

            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression principale : {e}")
            return False
        finally:
            if not committed:
                txn.discard()

    def _reset_ui(self):
        """Reset l'UI."""
        self.current_project_name = None

        # Appel AVANT le reset des données pour éviter AttributeError
        self._refresh_cluster_list()

        # Maintenant safe de set à None
        self.current_project_profile_data = None
        self.project_name_edit.clear()
        self.project_description_edit.clear()
        self._reset_hierarchy_ui()
        self.pending_relations.clear()
        self.label_uid_to_info.clear()
        self.name_to_uid.clear()
        self.current_selected_label_uid = None
        self.global_relations_config.update_current(None)
        self.relations_graph.update_graph(None)
        self._update_button_states()

        # Log pour debug
        logger.info("UI reset complété.")

    def _on_save_project(self):
        """Sauvegarde le profil local."""
        if not self.current_project_name:
            return
        self.current_project_profile_data['name'] = self.project_name_edit.text().strip()
        self.current_project_profile_data['description'] = self.project_description_edit.toPlainText().strip()
        self.current_project_profile_data['pending_relations'] = dict(self.pending_relations)
        self.project_profiles[self.current_project_name] = json.loads(json.dumps(self.current_project_profile_data))
        self.project_profile_saved.emit(self.current_project_name, self.current_project_profile_data)
        logger.info(f"Profil sauvegardé : {self.current_project_name}")

    def _on_export_profile(self):
        """Exporte le profil en JSON."""
        if not self.current_project_name:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Profil", f"{self.current_project_name}.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.current_project_profile_data, f, indent=4)
            logger.info(f"Profil exporté : {file_path}")

    def _on_insert_dgraph(self):
        """Insère le profil dans Dgraph après sauvegarde SQLite."""
        if not self.is_configured():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète.")
            return
        
        # Étape 1 : Sauvegarder d'abord dans SQLite (via CRUD)
        if not self._save_project_to_sqlite(self.current_project_profile_data):
            QtWidgets.QMessageBox.critical(
                self, 
                "Erreur", 
                "Échec de la sauvegarde dans SQLite. Insertion Dgraph annulée."
            )
            return
        
        QtWidgets.QMessageBox.information(
            self,
            "Succès partiel",
            "Projet sauvegardé dans SQLite. Insertion dans Dgraph en cours..."
        )
        
        # Étape 2 : Insérer dans Dgraph
        mutations = self._transform_profile_to_dgraph_mutations()
        
        if self.dgraph_connector.insert_mutations(mutations):
            logger.info("Insertion réussie dans Dgraph, y compris les relations.")
            QtWidgets.QMessageBox.information(
                self, 
                "Succès", 
                "Inséré dans SQLite et Dgraph avec succès. Ratel ouvert pour vérification."
            )
            self.dgraph_connector.open_ratel()
            self._load_project_profiles()  # Refresh Dgraph
            self._load_projects_from_sqlite()  # Refresh SQLite
            if self.current_project_name and self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())
        else:
            QtWidgets.QMessageBox.warning(
                self, 
                "Avertissement", 
                "Sauvegardé dans SQLite mais échec insertion Dgraph.\n"
                "Les données sont disponibles dans SQLite."
            )

    def is_configured(self):
        """Vérifie si la config est complète."""
        return (self.current_project_profile_data and
                self.project_name_edit.text().strip() and
                len(self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', [])) > 0)

    def _create_label_mutation(self, label_data, level, cluster_uid):
        """Crée une mutation pour un label avec ses fichiers."""
        uid = f"_:label_{label_data.get('uid', str(uuid.uuid4()))}"

        # S'assurer que les fichiers sont bien présents
        files = label_data.get('files', [])
        file_contents = label_data.get('file_contents', {})

        label = {
            "uid": uid,
            "dgraph.type": "Label",
            "name": label_data.get("label", label_data.get("name", "")),
            "id": label_data.get("id", str(uuid.uuid4())),
            "level": level,
            "path": "",
            "category": label_data.get("category", []),
            "createdAt": datetime.now().isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z",
            "parentId": "",
            "nodeType": "label",
            "description": label_data.get("description", ""),
            "codeContent": "",
            "files": files,
            "fileContents": json.dumps(file_contents),
            "clusters": [{"uid": cluster_uid}],
            "children": [],        # AJOUTER
            "relations": []        # AJOUTER
        }
        return label

    def _transform_profile_to_dgraph_mutations(self):
        """Transforme le profil actuel en mutations Dgraph avec gestion complète de la hiérarchie et relations liées."""
        if not self.current_project_profile_data:
            return []

        mutations = []

        # Créer Workspace
        workspace = {
            "uid": "_:workspace_uid",
            "dgraph.type": "Workspace",
            "name": self.current_project_profile_data.get("name", ""),
            "id": self.current_project_profile_data.get("name", str(uuid.uuid4())),
            "ownerId": "user1",
            "description": self.current_project_profile_data.get("description", ""),
            "updatedAt": datetime.now().isoformat() + "Z",
            "files": self.current_project_profile_data.get("files", []),
            "fileContents": json.dumps(self.current_project_profile_data.get("file_contents", {}))
        }
        mutations.append(workspace)

        # Créer ClusterManagement
        cluster_management = {
            "uid": "_:cm_uid",
            "dgraph.type": "ClusterManagement",
            "lastUpdated": datetime.now().isoformat() + "Z",
            "version": "1.0",
            "clusters": []
        }
        mutations.append(cluster_management)

        # Lier ClusterManagement au Workspace
        workspace["clusterManagement"] = {"uid": "_:cm_uid"}

        turing_ontology = self.current_project_profile_data.get("turing_ontology", {})
        clusters_detailed = turing_ontology.get("clusters_detailed", [])

        label_uids = {}  # Map label uid to dgraph uid

        for cluster_data in clusters_detailed:
            cluster_uid = f"_:cluster_{cluster_data.get('uid', str(uuid.uuid4()))}"
            cluster = {
                "uid": cluster_uid,
                "dgraph.type": "Cluster",
                "name": cluster_data.get("name", ""),
                "id": cluster_data.get("uid", str(uuid.uuid4())),
                "userId": "user1",
                "nodeType": "cluster",
                "description": cluster_data.get("description", ""),
                "codeContent": "",
                "createdAt": datetime.now().isoformat() + "Z",
                "updatedAt": datetime.now().isoformat() + "Z",
                "files": cluster_data.get("files", []),
                "fileContents": json.dumps(cluster_data.get("file_contents", {})),
                "root_labels": []
            }
            mutations.append(cluster)
            cluster_management["clusters"].append({"uid": cluster_uid})

            # Créer root_labels avec leurs hiérarchies complètes
            root_labels = cluster_data.get("root_labels", [])
            for root in root_labels:
                # Créer le root label
                root_label = self._create_label_mutation(root, level=0, cluster_uid=cluster_uid)
                mutations.append(root_label)
                cluster["root_labels"].append({"uid": root_label["uid"]})
                label_uids[root['uid']] = root_label["uid"]

                # Traiter récursivement la hiérarchie complète
                self._map_all_children_uids(
                    root, 
                    root_label["uid"], 
                    mutations, 
                    label_uids, 
                    cluster_uid, 
                    level=1
                )

        # NOUVEAU: Créer les relations et les lier aux sources
        relations_by_source = {}  # {source_dgraph_uid: [relation_uids]}

        for source_uid, rels in self.pending_relations.items():
            source_dgraph_uid = label_uids.get(source_uid)

            if not source_dgraph_uid:
                logger.warning(f"Source UID non trouvé: {source_uid}")
                continue
            
            relations_for_this_source = []

            for rel in rels:
                target_dgraph_uid = label_uids.get(rel['target_uid'])

                if not target_dgraph_uid:
                    logger.warning(f"Target UID non trouvé: {rel['target_uid']}")
                    continue
                
                relation_uid = f"_:rel_{uuid.uuid4()}"
                relation = {
                    "uid": relation_uid,
                    "dgraph.type": "Relation",
                    "name": f"Relation {rel['relation_type']}",
                    "relationType": rel['relation_type'],
                    "source": {"uid": source_dgraph_uid},
                    "target": {"uid": target_dgraph_uid}
                }
                mutations.append(relation)
                relations_for_this_source.append({"uid": relation_uid})

            # Stocker pour associer au label plus tard
            if relations_for_this_source:
                relations_by_source[source_dgraph_uid] = relations_for_this_source
                logger.debug(f"Créé {len(relations_for_this_source)} relations pour {source_uid}")

        # Associer les relations aux labels sources
        relations_associated = 0
        for mutation in mutations:
            mutation_uid = mutation.get("uid")
            if mutation_uid in relations_by_source:
                mutation["relations"] = relations_by_source[mutation_uid]
                relations_associated += len(relations_by_source[mutation_uid])
                logger.debug(f"Associé {len(relations_by_source[mutation_uid])} relations à {mutation.get('name')}")

        logger.info(f"Total mutations créées: {len(mutations)}")
        logger.info(f"Total relations associées aux sources: {relations_associated}")

        return mutations
    
    def _process_hierarchy_recursive(self, node_data, parent_mutation, cluster_uid, 
                                 mutations, label_uids, level):
        """
        Traite récursivement la hiérarchie en créant les mutations.
        Utilise le prédicat 'parents' sur l'enfant pour lier au parent (reverse ~parents).
        """
        children_list = node_data.get('children', [])

        if not children_list:
            return

        parent_uid = parent_mutation["uid"]

        for child_data in children_list:
            # Créer la mutation pour cet enfant
            child_mutation = self._create_label_mutation(
                child_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
            mutations.append(child_mutation)

            # Enregistrer l'UID
            label_uids[child_data['uid']] = child_mutation["uid"]

            # Lier au parent via 'parents' sur l'enfant
            if "parents" not in child_mutation:
                child_mutation["parents"] = []
            child_mutation["parents"].append({"uid": parent_uid})

            # Définir le parentId (string)
            child_mutation["parentId"] = node_data.get('uid', '')

            # Traiter récursivement les enfants de cet enfant
            self._process_hierarchy_recursive(
                child_data,
                child_mutation,
                cluster_uid,
                mutations,
                label_uids,
                level + 1
            )

    def _update_button_states(self):
        """Met à jour l'état des boutons en fonction de la sélection."""
        has_project = bool(self.current_project_name)
        self.delete_project_button.setEnabled(has_project)
        self.save_button.setEnabled(has_project)
        self.export_profile_button.setEnabled(has_project)
        self.insert_dgraph_button.setEnabled(has_project and self.is_configured())
    
        has_cluster = bool(self.current_cluster_data)
        self.add_root_button.setEnabled(has_cluster)
        self.edit_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
        self.remove_root_button.setEnabled(self.root_list_widget.currentRow() != -1)
    
        has_root = bool(self.current_root_data)
        self.add_level1_button.setEnabled(has_root)
        self.edit_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
        self.remove_level1_button.setEnabled(self.level1_list_widget.currentRow() != -1)
    
        has_level1 = bool(self.current_level1_data)
        self.add_child_button.setEnabled(has_level1)
        self.edit_child_button.setEnabled(self.child_list_widget.currentRow() != -1)
        self.remove_child_button.setEnabled(self.child_list_widget.currentRow() != -1)

        # Boutons relations
        has_source = bool(self.current_selected_label_uid)
        self.global_relations_config.add_button.setEnabled(has_source and len(self.label_uid_to_info) > 1)
        has_rel_selected = self.global_relations_config.relations_list.currentRow() != -1
        self.global_relations_config.edit_button.setEnabled(has_rel_selected)
        self.global_relations_config.remove_button.setEnabled(has_rel_selected)

    def _on_browse_project(self):
        """Version avec barre de progression moderne."""
        if not self.current_project_profile_data:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné")
            return
    
        project_name = self.current_project_profile_data.get("name", "Projet inconnu")
        files = self.current_project_profile_data.get("files", [])
        file_contents = self.current_project_profile_data.get("file_contents", {})
    
        if not files:
            QtWidgets.QMessageBox.warning(
                self, 
                "Aucun fichier trouvé", 
                f"Aucun fichier enregistré pour le projet '{project_name}'."
            )
            return
    
        logger.info(f"🔍 Analyse du projet '{project_name}'...")
    
        # 🎨 CRÉER LE DIALOGUE DE PROGRESSION
        progress = ModernProgressDialog(
            title=f"Analyse du projet : {project_name}",
            parent=self,
            show_log=True,  # Activer le log détaillé
            cancelable=True
        )
        progress.set_title(f"📊 Scan du projet {project_name}")
        progress.set_status(f"Analyse de {len(files)} fichiers...")
        progress.set_progress(0, len(files))
        progress.show()
    
        self.parsed_relations_cache = {}
        files_processed = 0
        files_with_content = 0
        files_with_relations = 0
    
        try:
            for i, file_path in enumerate(files, 1):
                # 🔄 MISE À JOUR DE LA PROGRESSION
                progress.set_progress(i, len(files))
                progress.set_status(f"Traitement du fichier {i}/{len(files)}")
                progress.set_details(f"📄 {os.path.basename(file_path)}")
                progress.add_log(f"[{i}/{len(files)}] Traitement: {file_path}")
                
                QtWidgets.QApplication.processEvents()
    
                # Vérifier annulation
                if progress.is_cancelled:
                    progress.add_log("❌ Opération annulée par l'utilisateur")
                    logger.warning("Scan annulé par l'utilisateur")
                    progress.reject()
                    return
    
                # Récupérer le contenu
                content = file_contents.get(file_path, "")
                
                if content:
                    files_with_content += 1
                    progress.add_log(f"   ✅ Contenu récupéré ({len(content)} chars)")
                else:
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            files_with_content += 1
                            progress.add_log(f"   ✅ Contenu lu depuis disque ({len(content)} chars)")
                        except Exception as e:
                            progress.add_log(f"   ⚠️ Erreur lecture: {e}")
                            logger.warning(f"Impossible de lire {file_path}: {e}")
                            continue
                    else:
                        progress.add_log(f"   ❌ Fichier introuvable sur disque")
                        continue
                    
                if not content:
                    progress.add_log(f"   ⚠️ Contenu vide, skip")
                    continue
                
                # Parser les relations
                parsed_rels = self.dependency_parser.parse_content(content, file_path)
                
                if parsed_rels:
                    total_rels = sum(len(v) for v in parsed_rels.values())
                    progress.add_log(f"   ✅ {total_rels} relations détectées")
                    files_with_relations += 1
                    self.parsed_relations_cache[file_path] = parsed_rels
                else:
                    progress.add_log(f"   ℹ️ Aucune relation détectée")
                
                # Extraire classes/fonctions/variables
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)
                
                progress.add_log(
                    f"   📦 Extraits: {len(classes)} classes, "
                    f"{len(functions)} fonctions, {len(variables)} variables"
                )
    
                # Trouver le label correspondant
                target_label = self._find_label_by_file_path(file_path)
                
                if target_label:
                    # Stocker le dict relations
                    target_label['relations'] = parsed_rels
                    
                    # Intégrer dans outgoing_relations
                    if parsed_rels:
                        self._integrate_parsed_relations_to_label(target_label, parsed_rels, file_path)
                    
                    # Stocker les éléments
                    target_label['classes'] = classes
                    target_label['functions'] = functions
                    target_label['variables'] = variables
                    
                    # Créer les enfants
                    for cls in classes:
                        cls['file'] = file_path
                        if 'uid' not in cls:
                            cls['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(cls, 'class')
                        target_label.setdefault('children', []).append(child)
    
                    for func in functions:
                        func['file'] = file_path
                        if 'uid' not in func:
                            func['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(func, 'function')
                        target_label.setdefault('children', []).append(child)
    
                    for var in variables:
                        var['file'] = file_path
                        if 'uid' not in var:
                            var['uid'] = str(uuid.uuid4())
                        child = self._create_child_node_from_extracted(var, 'variable')
                        target_label.setdefault('children', []).append(child)
                    
                    files_processed += 1
                else:
                    progress.add_log(f"   ⚠️ Aucun label trouvé pour ce fichier")
    
            # Construction du graphe
            progress.set_indeterminate(True)
            progress.set_status("🔗 Construction du graphe de relations...")
            progress.add_log("\n🔗 Construction du graphe de relations...")
            QtWidgets.QApplication.processEvents()
            
            self._build_complete_relations_graph()
            
            progress.set_indeterminate(False)
    
            # Validation
            progress.set_status("🔍 Validation des relations...")
            progress.add_log("🔍 Validation des relations parsées...")
            validation_stats = self._validate_parsed_relations()
    
            # Rafraîchir l'UI
            progress.set_status("♻️ Rafraîchissement de l'interface...")
            progress.add_log("♻️ Rafraîchissement de l'interface...")
            self._collect_all_labels()
            self._refresh_cluster_list()
            
            # Sauvegarde
            progress.set_status("💾 Sauvegarde dans SQLite et Dgraph...")
            progress.add_log("\n💾 Démarrage de la sauvegarde...")
            
            save_success = self._save_scan_results_to_storage()
            
            if save_success:
                progress.finish(
                    success=True,
                    message=f"✅ {files_processed} fichiers traités, "
                            f"{validation_stats['total_parsed_in_dict']} relations détectées"
                )
                progress.add_log("\n✅ Sauvegarde complète réussie!")
            else:
                progress.finish(
                    success=False,
                    message="Le scan a réussi mais la sauvegarde a échoué"
                )
                progress.add_log("\n❌ Échec de la sauvegarde")
    
        except Exception as e:
            logger.error(f"Erreur lors du scan: {str(e)}")
            import traceback
            traceback.print_exc()
            
            progress.finish(
                success=False,
                message=f"Erreur : {str(e)}"
            )
            progress.add_log(f"\n❌ ERREUR: {str(e)}")

    def _create_child_node_from_item(self, item: Dict, item_type: str) -> Dict[str, Any]:
        """
        Crée un nœud enfant à partir d'un élément extrait (classe, fonction, variable).
        
        Args:
            item: Dict de l'élément extrait
            item_type: Type ('class', 'function', 'variable')
        
        Returns:
            Dict du nœud enfant
        """
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': item.get('calls', []) if item_type == 'function' else item.get('uses_vars', []) if item_type == 'class' else [],
            'incoming_relations': [],
            'parents': []  # Sera mis à jour si nécessaire
        }
        
        # Ajouter à label_uid_to_info
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_name if hasattr(self, 'current_cluster_name') else 'unknown',
            'file': os.path.basename(item.get('file', ''))
        }
        
        return child

    def _collect_all_labels(self):
        """
        Collecte tous les labels et met à jour label_uid_to_info avec mapping Dgraph.
        À appeler après scan pour rafraîchir.
        """
        self.label_uid_to_info = {}
        if not self.current_project_profile_data:
            return

        def recurse(node, cluster_name=''):
            if 'uid' in node:
                uid = node['uid']
                # Stocker mapping local -> Dgraph si présent
                dgraph_uid = node.get('dgraph_uid', None)
                if dgraph_uid:
                    self.local_to_dgraph[uid] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = uid
                self.label_uid_to_info[uid] = {
                    'name': node.get('name', node.get('label', 'N/A')),
                    'label': node.get('label', 'N/A'),
                    'type': node.get('type', 'unknown'),
                    'cluster': cluster_name,
                    'file': node.get('file', 'N/A')
                }

            for child in node.get('children', []):
                recurse(child, cluster_name)

        for cluster in self.current_project_profile_data.get('clusters_detailed', []):
            cluster_name = cluster.get('name', 'unknown')
            for root_label in cluster.get('root_labels', []):
                recurse(root_label, cluster_name)

        # Charger mappings persistés depuis Dgraph si connector actif
        if self.dgraph_connector:
            self._load_mappings_from_dgraph()

        logger.info(f"label_uid_to_info mis à jour: {len(self.label_uid_to_info)} entrées")

    def _get_local_to_dgraph_mapping(self):
        """Retourne {local_uuid: dgraph_hex}"""
        if not hasattr(self, 'local_to_dgraph'):
            self.local_to_dgraph = {}
            self._collect_all_labels()  # Rafraîchir si besoin
        return self.local_to_dgraph

    def _get_dgraph_to_local_mapping(self):
        """Retourne {dgraph_hex: local_uuid}"""
        if not hasattr(self, 'dgraph_to_local'):
            self.dgraph_to_local = {}
            self._collect_all_labels()
        return self.dgraph_to_local

    def _load_mappings_from_dgraph(self):
        """Charge les mappings depuis Dgraph pour sync."""
        query = """
        {
          q(func: type(Node)) {
            uid
            local_id
          }
        }
        """
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            data = self.dgraph_connector._parse_response(resp)
            for node in data.get("q", []):
                local_id = node.get('local_id')
                dgraph_uid = node['uid']
                if local_id:
                    self.local_to_dgraph[local_id] = dgraph_uid
                    self.dgraph_to_local[dgraph_uid] = local_id
        except Exception as e:
            logger.error(f"Erreur chargement mappings Dgraph: {e}")

    def _load_existing_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Charge la structure existante du projet.
        """
        structure_file = os.path.join(project_path, "turing_ontology.json")
        if os.path.exists(structure_file):
            try:
                with open(structure_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement structure: {e}")
        return {"clusters_detailed": []}    
    
    def _integrate_scanned_structure(self, scanned_structure: Dict[str, Any], base_dir: str):
            """
            Intègre la structure scannée dans le projet, en calculant relations_map à l'intérieur.

            Args:
                scanned_structure: Structure scannée par le scanner
                base_dir: Répertoire de base du projet
            """
            # Calculer relations_map ici pour matcher l'appel (3 args)
            relations_map = self.project_scanner.get_relations_map(scanned_structure)

            clusters_detailed = []
            for cluster in scanned_structure.get('clusters', []):
                new_cluster = {
                    'name': cluster.get('name', 'Unknown'),
                    'path': cluster.get('path', ''),
                    'type': 'cluster',
                    'root_labels': []
                }

                # Traiter chaque fichier avec force
                all_files_in_cluster = self.project_scanner.get_all_files({'clusters': [cluster]})
                for file_info in all_files_in_cluster:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    rel_path = os.path.relpath(file_path, base_dir) if base_dir and file_path else file_path

                    # Contenu déjà lu dans _scan_file, fallback si absent
                    content = file_info.get('file_contents', {}).get(rel_path, '')
                    if not content and file_path:
                        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                        for encoding in encodings:
                            try:
                                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                                    content = f.read()
                                break
                            except (UnicodeDecodeError, IOError):
                                continue
                        else:
                            try:
                                with open(file_path, 'rb') as f:
                                    raw = f.read()
                                    content = raw.decode('utf-8', errors='replace')
                            except Exception:
                                content = ''

                    new_label = {
                        'label': file_name,
                        'id': str(uuid.uuid4()),
                        'uid': file_info.get('uid', str(uuid.uuid4())),
                        'type': 'file',
                        'description': f"Fichier: {rel_path}",
                        'category': ['file'],
                        'files': [rel_path],
                        'file_contents': {rel_path: content},
                        'children': [],
                        'parents': [],
                        'outgoing_relations': [],
                        'incoming_relations': [],
                        'classes': file_info.get('classes', []),  # Forcé depuis scan
                        'functions': file_info.get('functions', []),  # Forcé depuis scan
                        'variables': file_info.get('variables', [])  # Forcé depuis scan
                    }

                    # Ajouter le fichier au projet global
                    files_list = self.current_project_profile_data.get('files', [])
                    if rel_path not in files_list:
                        files_list.append(rel_path)
                        self.current_project_profile_data['files'] = files_list
                    file_contents = self.current_project_profile_data.get('file_contents', {})
                    file_contents[rel_path] = content
                    self.current_project_profile_data['file_contents'] = file_contents

                    # Mapper relations
                    relations = relations_map.get(file_path, {})
                    if relations:
                        for rel_type, rel_list in relations.items():
                            for rel in rel_list:
                                target = rel.get('target', '')
                                normalized_target = normalize_node_name(target)

                                if normalized_target:
                                    target_uid = self._find_label_uid_by_name(normalized_target)

                                    if target_uid:
                                        relation_entry = {
                                            'target_uid': target_uid,
                                            'relation_type': rel_type,
                                            'line': rel.get('line', 0)
                                        }
                                        new_label['outgoing_relations'].append(relation_entry)

                                        pending_rels = self.pending_relations.get(new_label['uid'], [])
                                        pending_rels.append({
                                            'target_uid': target_uid,
                                            'relation_type': rel_type
                                        })
                                        self.pending_relations[new_label['uid']] = pending_rels

                    # Ajouter enfants depuis scan (classes, functions, variables)
                    for child in file_info.get('children', []):
                        if 'uid' not in child:
                            child['uid'] = str(uuid.uuid4())
                        new_label['children'].append(child)

                    new_cluster['root_labels'].append(new_label)

                clusters_detailed.append(new_cluster)

            logger.info(f"{len(clusters_detailed)} clusters intégrés avec classes/fonctions/variables")
            turing_ontology = self.current_project_profile_data.get('turing_ontology', {})
            turing_ontology['clusters_detailed'] = clusters_detailed
            self.current_project_profile_data['turing_ontology'] = turing_ontology

    def _find_label_uid_by_name(self, name: str) -> Optional[str]:
        """
        Trouve l'UID d'un label par son nom (sans extension).
        
        Args:
            name: Nom du label à chercher
        
        Returns:
            UID du label ou None
        """
        if not name:
            return None
        
        normalized_search = name.lower().strip()
        
        for uid, info in self.label_uid_to_info.items():
            label_name = info.get('name', '')
            normalized_label = normalize_node_name(label_name)
            
            if normalized_label and normalized_label.lower() == normalized_search:
                return uid
        
        return None

    def _on_root_label_selected(self, current):
        """
        Gère la sélection dans root_list.
        - Si FICHIER → affiche directement classes/fonctions/variables dans level1_list
        - Si DOSSIER → affiche fichiers + children dans level1_list
        """
        if not current:
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        item_type = current.data(Qt.UserRole + 1)
        self.current_root_label_index = self.root_list_widget.row(current)

        root_labels = self.current_cluster_data.get("root_labels", [])

        if self.current_root_label_index < 0 or self.current_root_label_index >= len(root_labels):
            self.current_root_data = None
            self.level1_list_widget.clear()
            self.child_list_widget.clear()
            return

        self.current_root_data = root_labels[self.current_root_label_index]
        self.current_selected_label_uid = current.data(Qt.UserRole)

        # 🔍 LOG: Vérifier les relations du fichier sélectionné
        file_name = self.current_root_data.get('label', 'Unknown')
        logger.info(f"📂 Fichier sélectionné: {file_name} (UID: {self.current_selected_label_uid})")
        
        # Log des relations sortantes
        outgoing = self.current_root_data.get('outgoing_relations', [])
        logger.info(f"   → Relations sortantes: {len(outgoing)}")
        for rel in outgoing:
            target_uid = rel.get('target_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            category = rel.get('category', 'unknown')
            target_name = self.label_uid_to_info.get(target_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {rel_type} [{category}] → {target_name} (UID: {target_uid})")
        
        # Log des relations entrantes
        incoming = self.current_root_data.get('incoming_relations', [])
        logger.info(f"   ← Relations entrantes: {len(incoming)}")
        for rel in incoming:
            source_uid = rel.get('source_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            category = rel.get('category', 'unknown')
            source_name = self.label_uid_to_info.get(source_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {source_name} (UID: {source_uid}) {rel_type} [{category}] →")
        
        # Log des relations en attente (pending_relations)
        pending = self.pending_relations.get(self.current_selected_label_uid, [])
        logger.info(f"   ⏳ Relations en attente: {len(pending)}")
        for rel in pending:
            target_uid = rel.get('target_uid', 'N/A')
            rel_type = rel.get('relation_type', 'N/A')
            target_name = self.label_uid_to_info.get(target_uid, {}).get('name', 'Unknown')
            logger.debug(f"      • {rel_type} → {target_name} (UID: {target_uid})")

        # Réinitialiser niveaux inférieurs
        self.current_level1_data = None
        self.current_level2_data = None
        self.child_list_widget.clear()

        # Logique selon le type
        if item_type == 'file':
            # FICHIER : afficher détails + éléments de code directement
            self._update_selected_details("Fichier", self.current_root_data)
            self._populate_level1_with_file_elements(self.current_root_data)
        else:
            # DOSSIER : afficher détails + hiérarchie
            self._update_selected_details("Label Racine", self.current_root_data)
            self._populate_level1_list_with_root_files()

        # Mettre à jour relations
        self.global_relations_config.update_current(self.current_selected_label_uid)
        self.relations_graph.update_graph(self.current_selected_label_uid)

        self._update_button_states()

    def _populate_children_list(self, parent_data: Dict, list_widget=None):
        """
        Corrigée : 
        - Les fichiers .ts/.py/... s'affichent directement avec icône 📄
        - Seuls les sous-dossiers apparaissent comme 📁
        - Plus de double affichage du fichier lors du clic
        """
        if list_widget is None:
            list_widget = (
                self.level1_list_widget
                if hasattr(self, 'current_root_data')
                else self.child_list_widget
            )

        list_widget.clear()
        if not parent_data:
            return

        for child in parent_data.get('children', []):
            child_type = child.get('type', 'child')
            label = child.get('label', child.get('name', 'Sans nom'))
            uid = child.get('uid', str(uuid.uuid4()))
            child['uid'] = uid

            # === CAS 1 : Sous-dossier ===
            if child_type in ['folder', 'directory']:
                icon = self._get_node_icon('folder')
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'folder')
                list_widget.addItem(item)

            # === CAS 2 : Fichier ===
            elif child_type == 'file' or label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net')):
                icon = self._get_node_icon('file')
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, 'file')
                list_widget.addItem(item)

            # === CAS 3 : Éléments de code internes (classe, fonction, variable) ===
            elif child_type in ['class', 'function', 'variable']:
                # Ces éléments ne sont pas affichés ici : ils seront dans la partie inférieure
                continue

            # === Autres types (fallback générique) ===
            else:
                icon = self._get_node_icon(child_type)
                display = f"{icon} {label}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, uid)
                item.setData(Qt.UserRole + 1, child_type)
                list_widget.addItem(item)

        self._update_button_states()

    def _populate_level1_with_file_elements(self, file_data: Dict):
        """
        Affiche UNIQUEMENT les classes/fonctions/variables d'un fichier dans level1_list.
        PAS de réaffichage du fichier lui-même.

        Args:
            file_data: Dictionnaire du fichier (root_data)
        """
        self.level1_list_widget.clear()

        if not file_data:
            return

        # Récupérer le contenu du fichier
        files = file_data.get('files', [])
        if not files:
            self.level1_list_widget.addItem(QListWidgetItem("(Aucun contenu)"))
            return

        file_path = files[0]  # Fichier principal
        content = file_data.get('file_contents', {}).get(file_path, '')

        if not content:
            content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

        if not content:
            self.level1_list_widget.addItem(QListWidgetItem("(Contenu vide)"))
            return

        # Extraire les éléments de code
        classes = self.dependency_parser.extract_classes(content, file_path)
        functions = self.dependency_parser.extract_functions(content, file_path)
        variables = self.dependency_parser.extract_variables(content, file_path)

        # === Afficher les CLASSES ===
        for cls in classes:
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            if 'uid' not in cls:
                cls['uid'] = cls_uid

            item = QListWidgetItem(f"[CLASS] {cls['name']} (ligne {cls.get('line', '?')})")
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, 'class')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#e74c3c"))  # Rouge
            self.level1_list_widget.addItem(item)

        # === Afficher les FONCTIONS ===
        for func in functions:
            func_uid = func.get('uid', str(uuid.uuid4()))
            if 'uid' not in func:
                func['uid'] = func_uid

            func_type = func.get('type', 'function')
            prefix = "[METH]" if func_type == 'method' else "[FUNC]"

            item = QListWidgetItem(f"{prefix} {func['name']} (ligne {func.get('line', '?')})")
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, func.get('line', 0))
            item.setForeground(QtGui.QColor("#3498db"))  # Bleu
            self.level1_list_widget.addItem(item)

        # === Afficher les VARIABLES ===
        for var in variables:
            var_uid = var.get('uid', str(uuid.uuid4()))
            if 'uid' not in var:
                var['uid'] = var_uid

            var_type = var.get('type', 'variable')

            item = QListWidgetItem(f"[VAR] {var['name']} (ligne {var.get('line', '?')})")
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, 'variable')
            item.setData(Qt.UserRole + 2, file_path)
            item.setData(Qt.UserRole + 3, var.get('line', 0))
            item.setForeground(QtGui.QColor("#2ecc71"))  # Vert
            self.level1_list_widget.addItem(item)

        # Message si aucun élément trouvé
        if not classes and not functions and not variables:
            self.level1_list_widget.addItem(QListWidgetItem("(Aucun élément de code trouvé)"))

        self._update_button_states()

    def _populate_root_list(self):
        """
        Affiche la liste des root labels avec détection automatique fichier/dossier.
        """
        self.root_list_widget.clear()

        if not self.current_cluster_data:
            return

        for root in self.current_cluster_data.get("root_labels", []):
            root_type = root.get('type', 'folder')
            root_label = root.get('label', root.get('name', 'Sans nom'))

            # Détection automatique : si le label se termine par une extension, c'est un fichier
            is_file = root_type == 'file' or root_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h'))

            if is_file:
                icon = "📄"
                item_type = 'file'
                color = QtGui.QColor("#7f8c8d")
            else:
                icon = "📂"
                item_type = 'root_label'
                color = QtGui.QColor("#2980b9")

            display = f"{icon} {root_label}"
            root_item = QListWidgetItem(display)
            root_item.setData(Qt.UserRole, root.get("uid"))
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)

        self._update_button_states()

    def _get_node_icon(self, node_type: str) -> str:
        """
        Retourne une icône selon le type de nœud.
        ÉTENDU pour supporter class, function, variable.
        """
        icons = {
            'folder': '📁',
            'file': '📄',
            'class': '[CLASS]',
            'function': '[FUNC]',
            'method': '[METH]',
            'variable': '[VAR]',
            'child': '📂'
        }
        return icons.get(node_type, '📦')

    def _get_relation_icon(self, rel_type: str) -> str:
        """
        Retourne une icône selon le type de relation.
        
        Args:
            rel_type: Type de relation
        
        Returns:
            Icône Unicode
        """
        icons = {
            'import': '📦',
            'from_import': '📦',
            'require': '📦',
            'include': '📦',
            'heritage': '🔗',
            'extends': '🔗',
            'implements': '🔗',
            'call': '📞',
            'function_call': '📞',
            'method_call': '📞',
            'uses': '🔹',  # NOUVEAU pour variables
            'variable_use': '🔹'
        }
        
        return icons.get(rel_type, '🔸')

    def _populate_children_for_file(self, file_data: Dict, list_widget):
        """
        MODIFIÉE: Peuple la liste enfant avec les classes, fonctions et variables
        DU FICHIER SÉLECTIONNÉ. Les UIDs sont stockés correctement dans Qt.UserRole.
        """
        list_widget.clear()
        if not file_data:
            return

        # Afficher d'abord les classes du fichier
        classes = file_data.get('classes', [])
        for cls in classes:
            icon = '[CLS]'
            display = f"{icon} {cls.get('name', 'Classe')} (ligne {cls.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            cls_uid = cls.get('uid')
            if not cls_uid:
                cls_uid = f"cls_{cls.get('name', '')}_{str(uuid.uuid4())}"
                cls['uid'] = cls_uid

            # Stocker le UID STRING, pas l'ID mémoire
            item.setData(Qt.UserRole, cls_uid)
            item.setData(Qt.UserRole + 1, "class")
            item.setData(Qt.UserRole + 2, cls.get('line', 0))
            item.setForeground(QtGui.QColor("#FF9800"))
            list_widget.addItem(item)

        # Afficher les fonctions du fichier
        functions = file_data.get('functions', [])
        for func in functions:
            func_type = func.get('type', 'function')
            icon = "[MTH]" if func_type == "method" else "[FNC]"
            display = f"{icon} {func.get('name', 'Fonction')} (ligne {func.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            func_uid = func.get('uid')
            if not func_uid:
                func_uid = f"func_{func.get('name', '')}_{str(uuid.uuid4())}"
                func['uid'] = func_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, func_uid)
            item.setData(Qt.UserRole + 1, func_type)
            item.setData(Qt.UserRole + 2, func.get('line', 0))
            item.setForeground(QtGui.QColor("#2196F3"))
            list_widget.addItem(item)

        # Afficher les variables du fichier
        variables = file_data.get('variables', [])
        for var in variables:
            display = f"[VAR] {var.get('name', 'Variable')} (ligne {var.get('line', '?')})"
            item = QListWidgetItem(display)

            # S'assurer que le UID est généré
            var_uid = var.get('uid')
            if not var_uid:
                var_uid = f"var_{var.get('name', '')}_{str(uuid.uuid4())}"
                var['uid'] = var_uid

            # Stocker le UID STRING
            item.setData(Qt.UserRole, var_uid)
            item.setData(Qt.UserRole + 1, "variable")
            item.setData(Qt.UserRole + 2, var.get('line', 0))
            item.setForeground(QtGui.QColor("#4CAF50"))
            list_widget.addItem(item)

        # Afficher les enfants hiérarchiques (sous-dossiers/fichiers) APRÈS les classes/foncs/vars
        for child in file_data.get('children', []):
            if child.get('type') in ['folder', 'file', 'child']:
                icon = self._get_node_icon(child.get('type', 'child'))
                display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"
                item = QListWidgetItem(display)

                # Stocker le UID STRING de l'enfant
                child_uid = child.get('uid')
                if not child_uid:
                    child_uid = child.get('id', str(uuid.uuid4()))
                    child['uid'] = child_uid

                item.setData(Qt.UserRole, child_uid)
                item.setData(Qt.UserRole + 1, child.get('type', 'child'))
                list_widget.addItem(item)

        self._update_button_states()

    def _format_child_details(self, child: Dict[str, Any]) -> str:
        """
        Formate les détails d'un enfant (classe, fonction, variable) pour affichage.
        """
        child_type = child.get('type', 'unknown')
        details = ""

        if child_type == 'class':
            details = f"=== CLASSE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            bases = child.get('bases', [])
            if bases:
                details += f"\nHérite de:\n"
                for base in bases:
                    details += f"  - {base}\n"

            methods = child.get('children', [])
            if methods:
                details += f"\nMéthodes ({len(methods)}):\n"
                for method in methods[:10]:
                    details += f"  - {method.get('name', 'N/A')} (ligne {method.get('line', '?')})\n"
                if len(methods) > 10:
                    details += f"  ... et {len(methods) - 10} autres\n"

        elif child_type in ['function', 'method']:
            details = f"=== {'MÉTHODE' if child_type == 'method' else 'FONCTION'} ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('type', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

            params = child.get('params', [])
            if params:
                details += f"\nParamètres ({len(params)}):\n"
                for param in params:
                    param_name = param.get('name', 'param')
                    param_type = param.get('type', 'unknown')
                    details += f"  - {param_name}: {param_type}\n"

            returns = child.get('returns', {})
            if returns:
                details += f"\nRetour: {returns.get('type', 'N/A')}\n"

            calls = child.get('outgoing_relations', [])
            if calls:
                details += f"\nAppelle ({len(calls)}):\n"
                for call in calls[:5]:
                    details += f"  - {call}\n"
                if len(calls) > 5:
                    details += f"  ... et {len(calls) - 5} autres\n"

        elif child_type == 'variable':
            details = f"=== VARIABLE ===\n\n"
            details += f"Nom: {child.get('name', 'N/A')}\n"
            details += f"UID: {child.get('uid', 'N/A')}\n"
            details += f"Type: {child.get('var_type', 'N/A')}\n"
            details += f"Scope: {child.get('scope', 'N/A')}\n"
            details += f"Ligne: {child.get('line', 'N/A')}\n"
            details += f"Description: {child.get('description', 'N/A')}\n"

        return details

    def _get_child_index_by_uid(self, uid: str) -> int:
        """
        Trouve l'index d'un enfant par son UID.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Index ou -1
        """
        if not self.current_root_data:
            return -1
        
        for i, child in enumerate(self.current_root_data.get('children', [])):
            if child.get('uid') == uid:
                return i
        
        return -1

    def _find_label_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un label par son UID dans toute la hiérarchie.
        
        Args:
            uid: UID à chercher
        
        Returns:
            Dictionnaire du label ou None
        """
        all_nodes = self._get_all_nodes()
        return next((n for n in all_nodes if n.get('uid') == uid), None)

    def _find_child_by_uid(self, parent: Dict, uid: str) -> Optional[Dict]:
        """
        Cherche récursivement un enfant par son UID dans la structure.
        """
        for child in parent.get("children", []):
            if child.get('uid') == uid or child.get('id') == uid:
                return child

            # Chercher récursivement dans les sous-dossiers
            result = self._find_child_by_uid(child, uid)
            if result:
                return result

        return None

    def _format_label_details(self, label: Dict[str, Any]) -> str:
        """
        Formate les détails d'un label pour affichage, incluant classes, fonctions et variables.
        
        Args:
            label: Dictionnaire du label
        
        Returns:
            String formaté
        """
        details = f"Nom: {label.get('label', 'N/A')}\n"
        details += f"UID: {label.get('uid', 'N/A')}\n"
        details += f"Type: {label.get('type', 'N/A')}\n"  # NOUVEAU
        details += f"Description: {label.get('description', 'N/A')}\n\n"
        
        files = label.get('files', [])
        if files:
            details += f"Fichiers ({len(files)}):\n"
            for f in files[:5]:
                details += f"  - {f}\n"
            if len(files) > 5:
                details += f"  ... et {len(files) - 5} autres\n"
        
        # Ajouter classes si présentes
        classes = label.get('classes', [])
        if classes:
            details += f"\nClasses ({len(classes)}):\n"
            for cls in classes[:5]:
                details += f"  - {cls['name']} (ligne {cls['line']})\n"
            if len(classes) > 5:
                details += f"  ... et {len(classes) - 5} autres\n"
        
        # Ajouter fonctions si présentes
        functions = label.get('functions', [])
        if functions:
            details += f"\nFonctions/Méthodes ({len(functions)}):\n"
            for func in functions[:5]:
                details += f"  - {func['name']} ({func['type']}, ligne {func['line']})\n"
            if len(functions) > 5:
                details += f"  ... et {len(functions) - 5} autres\n"

        # NOUVEAU : Ajouter variables si présentes
        variables = label.get('variables', [])
        if variables:
            details += f"\nVariables ({len(variables)}):\n"
            for var in variables[:5]:
                details += f"  - {var['name']} ({var['type']}, ligne {var['line']})\n"
            if len(variables) > 5:
                details += f"  ... et {len(variables) - 5} autres\n"
        
        return details

    def _on_double_click_label(self, item):
        """
        Double-clic sur un label - Affiche le contenu du fichier avec snippet highlighté.
        MODIFIÉ: Centré sur ligne pour classes/foncs/vars.
        """
        if not item:
            return
        
        uid = item.data(Qt.UserRole)
        label = self._find_label_by_uid(uid)
        
        if not label:
            return
        
        files = label.get('files', [])
        if not files:
            QtWidgets.QMessageBox.information(
                self,
                "Aucun fichier",
                "Ce label n'a pas de fichier associé."
            )
            return
        
        # Si plusieurs fichiers, demander lequel afficher
        file_to_show = files[0]
        if len(files) > 1:
            file_to_show, ok = QInputDialog.getItem(
                self,
                "Sélectionner un fichier",
                "Fichier à afficher:",
                files,
                0,
                False
            )
            if not ok:
                return
        
        # Récupérer le contenu
        content = label.get('file_contents', {}).get(file_to_show, '')
        
        if not content:
            QtWidgets.QMessageBox.warning(
                self,
                "Contenu vide",
                f"Le fichier {file_to_show} est vide."
            )
            return
        
        # Afficher dans une fenêtre de dialogue avec highlight
        self._show_file_content_dialog(file_to_show, content, label)

    def _copy_to_clipboard(self, text: str):
        """Copie le texte dans le presse-papier."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        
        QtWidgets.QMessageBox.information(
            self,
            "Copié",
            "Contenu copié dans le presse-papier."
        )

    def _copy_snippet(self, text: str, max_lines: int = 50):
        """Copie un snippet (extrait) du texte."""
        lines = text.split('\n')
        snippet = '\n'.join(lines[:max_lines])
        
        if len(lines) > max_lines:
            snippet += f"\n\n... ({len(lines) - max_lines} lignes supplémentaires)"
        
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(snippet)
        
        QtWidgets.QMessageBox.information(
            self,
            "Snippet copié",
            f"Les {min(max_lines, len(lines))} premières lignes ont été copiées."
        )

    def _read_file_content(self, file_path: str) -> str:
        """Lit un fichier en UTF-8 avec gestion d’erreur."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Impossible de lire {file_path}: {e}")
            return ""

    def _add_child_to_level1_list(self, child: Dict, list_widget, indent: str = ""):
        """
        Ajoute un enfant à la liste niveau 1, récursivement pour les sous-dossiers.
        """
        child_type = child.get('type', 'folder')

        # Afficher cet enfant SANS icône
        display = f"{indent}{child.get('label', child.get('name', 'Sans nom'))}"
        item = QListWidgetItem(display)

        child_uid = child.get('uid', child.get('id', str(uuid.uuid4())))
        if 'uid' not in child:
            child['uid'] = child_uid

        item.setData(Qt.UserRole, child_uid)
        item.setData(Qt.UserRole + 1, child_type)
        list_widget.addItem(item)

        # Si c'est un dossier, afficher aussi ses enfants de manière imbriquée
        if child_type in ['folder', 'directory']:
            for grandchild in child.get("children", []):
                self._add_child_to_level1_list(grandchild, list_widget, indent + "  ")

    def _populate_cluster_list(self):
        """
        CORRIGÉ : Affiche UNIQUEMENT les clusters (pas leurs fichiers).
        """
        self.cluster_list_widget.clear()

        if not self.current_project_profile_data:
            return

        clusters = self.current_project_profile_data.get("turing_ontology", {}).get("clusters_detailed", [])

        for cluster in clusters:
            cluster_item = QListWidgetItem(f"📁 {cluster['name']}")
            cluster_item.setData(Qt.UserRole, cluster['uid'])
            cluster_item.setData(Qt.UserRole + 1, 'cluster')
            cluster_item.setForeground(QtGui.QColor("#2c3e50"))
            self.cluster_list_widget.addItem(cluster_item)

    def _populate_root_list_with_cluster_files(self):   
        """
        Affiche dans root_list :
        1. Les root labels du cluster (fichiers ET dossiers détectés automatiquement)
        """
        self.root_list_widget.clear()
    
        if not self.current_cluster_data:
            return
    
        # Afficher tous les root labels avec détection automatique
        for root in self.current_cluster_data.get("root_labels", []):
            root_label = root.get('label', root.get('name', 'Sans nom'))
            root_uid = root.get("uid")
            
            # Détection automatique par extension OU par type
            root_type = root.get('type', 'folder')
            is_file = (
                root_type == 'file' or 
                root_label.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h', '.tsx', '.jsx'))
            )
            
            if is_file:
                # C'est un fichier
                icon = "📄"
                item_type = 'file'
                color = QtGui.QColor("#7f8c8d")
            else:
                # C'est un dossier
                icon = "📂"
                item_type = 'root_label'
                color = QtGui.QColor("#2980b9")
            
            display = f"{icon} {root_label}"
            root_item = QListWidgetItem(display)
            root_item.setData(Qt.UserRole, root_uid)
            root_item.setData(Qt.UserRole + 1, item_type)
            root_item.setForeground(color)
            self.root_list_widget.addItem(root_item)
    
        self._update_button_states()

    def _populate_level1_list_with_root_files(self):
        """
        Affiche dans level1_list (pour les DOSSIERS uniquement) :
        1. Les fichiers du root label avec icône fichier
        2. Les children (sous-dossiers) du root label

        NE PAS afficher les classes/fonctions/variables ici (réservé aux fichiers directs)
        """
        self.level1_list_widget.clear()

        if not self.current_root_data:
            return

        # 1. Afficher les FICHIERS du root label
        for file_path in self.current_root_data.get('files', []):
            file_name = os.path.basename(file_path)
            file_item = QListWidgetItem(f"📄 {file_name}")
            file_item.setData(Qt.UserRole, f"root_file_{file_path}")
            file_item.setData(Qt.UserRole + 1, 'root_file')
            file_item.setData(Qt.UserRole + 2, file_path)
            file_item.setForeground(QtGui.QColor("#7f8c8d"))
            self.level1_list_widget.addItem(file_item)

        # 2. Afficher les CHILDREN (sous-dossiers/fichiers hiérarchiques)
        for child in self.current_root_data.get("children", []):
            child_type = child.get('type', 'folder')

            # SKIP les éléments de code (ils seront affichés via les fichiers)
            if child_type in ['class', 'function', 'variable', 'method']:
                continue
            
            # Déterminer l'icône selon le type
            if child_type == 'file' or child.get('label', '').endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net')):
                icon = "📄"
                display_type = 'file'
            else:
                icon = self._get_node_icon(child_type)
                display_type = child_type

            display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, child.get("uid"))
            item.setData(Qt.UserRole + 1, display_type)
            item.setForeground(QtGui.QColor("#16a085"))
            self.level1_list_widget.addItem(item)

        self._update_button_states()

    def _populate_child_list_with_parent_files(self):
        """
        Affiche dans child_list :
        1. Les fichiers du parent label
        2. Les children du parent label
        3. Les classes/fonctions/variables des fichiers du parent label
        """
        self.child_list_widget.clear()

        if not self.current_level1_data:
            return

        # 1. Afficher les fichiers
        for file_path in self.current_level1_data.get('files', []):
            file_name = os.path.basename(file_path)
            file_item = QListWidgetItem(f"📄 {file_name}")
            file_item.setData(Qt.UserRole, f"level1_file_{file_path}")
            file_item.setData(Qt.UserRole + 1, 'level1_file')
            file_item.setData(Qt.UserRole + 2, file_path)
            file_item.setForeground(QtGui.QColor("#7f8c8d"))
            self.child_list_widget.addItem(file_item)

        # 2. Afficher les children hiérarchiques
        for child in self.current_level1_data.get("children", []):
            child_type = child.get('type', 'folder')

            if child_type in ['class', 'function', 'variable', 'method']:
                continue
            
            icon = self._get_node_icon(child_type)
            display = f"{icon} {child.get('label', child.get('name', 'Sans nom'))}"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, child.get("uid"))
            item.setData(Qt.UserRole + 1, child_type)
            item.setForeground(QtGui.QColor("#27ae60"))
            self.child_list_widget.addItem(item)

        # 3. Afficher les éléments de code des fichiers du parent label
        parent_files = self.current_level1_data.get('files', [])
        file_contents = self.current_level1_data.get('file_contents', {})

        for file_path in parent_files:
            content = file_contents.get(file_path, '')
            if not content:
                content = self.current_project_profile_data.get('file_contents', {}).get(file_path, '')

            if content:
                classes = self.dependency_parser.extract_classes(content, file_path)
                functions = self.dependency_parser.extract_functions(content, file_path)
                variables = self.dependency_parser.extract_variables(content, file_path)

                # Ajouter classes
                for cls in classes:
                    item = QListWidgetItem(f"[CLASS] {cls['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, cls.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'class')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, cls.get('line', 0))
                    item.setForeground(QtGui.QColor("#e74c3c"))
                    self.child_list_widget.addItem(item)

                # Ajouter fonctions
                for func in functions:
                    item = QListWidgetItem(f"[FUNC] {func['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, func.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'function')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, func.get('line', 0))
                    item.setForeground(QtGui.QColor("#3498db"))
                    self.child_list_widget.addItem(item)

                # Ajouter variables
                for var in variables:
                    item = QListWidgetItem(f"[VAR] {var['name']} (📄 {os.path.basename(file_path)})")
                    item.setData(Qt.UserRole, var.get('uid', str(uuid.uuid4())))
                    item.setData(Qt.UserRole + 1, 'variable')
                    item.setData(Qt.UserRole + 2, file_path)
                    item.setData(Qt.UserRole + 3, var.get('line', 0))
                    item.setForeground(QtGui.QColor("#2ecc71"))
                    self.child_list_widget.addItem(item)

    def _integrate_parsed_relations_to_node(self, node: Dict, parsed_relations: Dict, node_type: str):
        """
        Intègre les relations parsées (import, extends, calls, uses) au nœud.

        Args:
            node: Nœud cible (classe, fonction, variable)
            parsed_relations: Dict avec clés 'import', 'heritage', 'call', 'uses'
            node_type: Type du nœud ('class', 'function', 'variable')
        """
        if not parsed_relations:
            return

        # Pour les CLASSES : les héritages (extends)
        if node_type == 'class':
            for base_rel in parsed_relations.get('heritage', []):
                target_name = base_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'extends',
                            'category': 'parsed',
                            'line': base_rel.get('line', 0)
                        })

            # Usages de variables par la classe
            for use_rel in parsed_relations.get('uses', []):
                target_name = use_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'uses',
                            'category': 'parsed',
                            'line': use_rel.get('line', 0)
                        })

        # Pour les FONCTIONS : les appels (calls)
        elif node_type == 'function':
            for call_rel in parsed_relations.get('call', []):
                target_name = call_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'calls',
                            'category': 'parsed',
                            'line': call_rel.get('line', 0)
                        })

        # Pour les FICHIERS (root_labels) : imports
        if 'import' in parsed_relations:
            for import_rel in parsed_relations['import']:
                target_name = import_rel.get('target', '')
                normalized = normalize_node_name(target_name)
                if normalized:
                    target_uid = self._find_label_uid_by_name(normalized)
                    if target_uid:
                        node['outgoing_relations'].append({
                            'target_uid': target_uid,
                            'relation_type': 'import',
                            'category': 'parsed',
                            'line': import_rel.get('line', 0)
                        })

    def _validate_parsed_relations(self):
        """
        Méthode de debug pour vérifier que les relations parsées sont bien présentes.
        """
        all_nodes = self._get_all_nodes()

        stats = {
            'nodes_with_relations_dict': 0,
            'nodes_with_outgoing': 0,
            'total_parsed_in_dict': 0,
            'total_parsed_in_outgoing': 0
        }

        for node in all_nodes:
            node_name = node.get('label', node.get('name', 'Unknown'))

            # Vérifier dict 'relations'
            relations_dict = node.get('relations', {})
            if relations_dict:
                stats['nodes_with_relations_dict'] += 1
                for rel_type, rel_list in relations_dict.items():
                    stats['total_parsed_in_dict'] += len(rel_list)
                    logger.debug(f"  {node_name} - relations['{rel_type}']: {len(rel_list)} items")

            # Vérifier outgoing_relations
            outgoing = node.get('outgoing_relations', [])
            if outgoing:
                stats['nodes_with_outgoing'] += 1
                parsed_out = [r for r in outgoing if r.get('category') == 'parsed']
                stats['total_parsed_in_outgoing'] += len(parsed_out)
                if parsed_out:
                    logger.debug(f"  {node_name} - outgoing_relations (parsed): {len(parsed_out)}")

        logger.info(f"\n📊 VALIDATION RELATIONS PARSÉES:")
        logger.info(f"  Nœuds avec 'relations' dict: {stats['nodes_with_relations_dict']}")
        logger.info(f"  Nœuds avec outgoing_relations: {stats['nodes_with_outgoing']}")
        logger.info(f"  Total relations dans dict: {stats['total_parsed_in_dict']}")
        logger.info(f"  Total relations parsées dans outgoing: {stats['total_parsed_in_outgoing']}")

        return stats

    def _find_label_by_file_path(self, file_path: str) -> Optional[Dict]:
        """
        Trouve le label correspondant à un fichier dans la structure.
        """
        if not self.current_project_profile_data:
            return None

        file_name = os.path.basename(file_path)

        for cluster in self.current_project_profile_data.get('turing_ontology', {}).get('clusters_detailed', []):
            for root_label in cluster.get('root_labels', []):
                # Vérifier si c'est le bon label
                if root_label.get('label') == file_name:
                    return root_label

                # Chercher dans les fichiers du label
                if file_path in root_label.get('files', []):
                    return root_label

                # Chercher récursivement dans les enfants
                result = self._find_label_in_children(root_label, file_path, file_name)
                if result:
                    return result

        return None
    
    def _find_label_in_children(self, parent: Dict, file_path: str, file_name: str) -> Optional[Dict]:
        """Cherche récursivement un label par fichier."""
        for child in parent.get('children', []):
            if child.get('label') == file_name or file_path in child.get('files', []):
                return child

            result = self._find_label_in_children(child, file_path, file_name)
            if result:
                return result

        return None

    def _integrate_parsed_relations_to_label(self, label: Dict, parsed_relations: Dict, file_path: str):
        """
        Args:
            label: Label cible (fichier)
            parsed_relations: Relations parsées du fichier
            file_path: Chemin du fichier source
        """
        label_uid = label.get('uid')
        if not label_uid:
            return

        for rel_type, rel_list in parsed_relations.items():
            for rel in rel_list:
                target_name = rel.get('target', '')
                if not target_name:
                    continue
                
                # Normaliser le nom de la cible
                normalized_target = normalize_node_name(target_name)
                if not normalized_target:
                    continue
                
                # Essayer de trouver l'UID de la cible
                target_uid = self._find_label_uid_by_name(normalized_target)

                # Si pas trouvé, générer un UID temporaire
                if not target_uid:
                    target_uid = f"temp_{normalized_target}_{str(uuid.uuid4())[:8]}"
                    logger.debug(f"UID temporaire créé pour {normalized_target}: {target_uid}")

                # Créer l'entrée de relation
                relation_entry = {
                    'target_uid': target_uid,
                    'target_name': target_name,  # Garder le nom original
                    'relation_type': rel_type,
                    'category': 'parsed',
                    'line': rel.get('line', 0),
                    'intra_file': rel.get('intra_file', False)
                }

                # Ajouter à outgoing_relations si pas déjà présent
                outgoing = label.setdefault('outgoing_relations', [])
                if not any(r['target_uid'] == target_uid and r['relation_type'] == rel_type for r in outgoing):
                    outgoing.append(relation_entry)
                    logger.debug(f"Relation ajoutée: {label.get('label')} --{rel_type}--> {target_name}")

                # Ajouter aussi aux pending_relations pour synchronisation Dgraph
                pending = self.pending_relations.get(label_uid, [])
                pending_entry = {
                    'target_uid': target_uid,
                    'relation_type': rel_type
                }
                if pending_entry not in pending:
                    pending.append(pending_entry)
                    self.pending_relations[label_uid] = pending

    def _create_child_node_from_extracted(self, item: Dict, item_type: str) -> Dict:
        """
        Crée un nœud enfant à partir d'un élément extrait (classe, fonction, variable).
        VERSION CORRIGÉE : Intègre aussi les relations internes (calls, bases, uses_vars)
        """
        uid = item.get('uid', str(uuid.uuid4()))
        child = {
            'name': item['name'],
            'uid': uid,
            'type': item_type,
            'line': item.get('line', 0),
            'label': f"{item_type.capitalize()}: {item['name']}",
            'children': [],
            'outgoing_relations': [],
            'incoming_relations': [],
            'parents': []
        }

        if item_type == 'class':
            # Héritage (bases)
            for base_name in item.get('bases', []):
                base_uid = self._find_label_uid_by_name(normalize_node_name(base_name))
                if not base_uid:
                    base_uid = f"temp_class_{base_name}_{str(uuid.uuid4())[:8]}"

                child['outgoing_relations'].append({
                    'target_uid': base_uid,
                    'target_name': base_name,
                    'relation_type': 'extends',
                    'category': 'parsed'
                })

            # Usages de variables
            for var_name in item.get('uses_vars', []):
                var_uid = self._find_label_uid_by_name(normalize_node_name(var_name))
                if not var_uid:
                    var_uid = f"temp_var_{var_name}_{str(uuid.uuid4())[:8]}"

                child['outgoing_relations'].append({
                    'target_uid': var_uid,
                    'target_name': var_name,
                    'relation_type': 'uses',
                    'category': 'parsed'
                })

        elif item_type == 'function':
            # Appels de fonction
            for call_name in item.get('calls', []):
                call_uid = self._find_label_uid_by_name(normalize_node_name(call_name))
                if not call_uid:
                    call_uid = f"temp_func_{call_name}_{str(uuid.uuid4())[:8]}"

                child['outgoing_relations'].append({
                    'target_uid': call_uid,
                    'target_name': call_name,
                    'relation_type': 'calls',
                    'category': 'parsed'
                })

        # Ajouter aux infos globales
        self.label_uid_to_info[uid] = {
            'name': child['name'],
            'label': child['label'],
            'type': item_type,
            'cluster': self.current_cluster_data.get('name', 'unknown') if self.current_cluster_data else 'unknown',
            'file': item.get('file', 'N/A')
        }

        return child

    def _build_complete_relations_graph(self):
        """
        - Résout les UIDs temporaires
        - Crée les relations inverses
        - Valide la cohérence
        """
        logger.info("🔗 Construction du graphe de relations...")

        all_nodes = self._get_all_nodes()
        resolved_count = 0
        inverse_count = 0

        # Étape 1 : Résoudre les UIDs temporaires
        logger.info("📝 Résolution des UIDs temporaires...")
        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid', '')

                # Si c'est un UID temporaire, essayer de le résoudre
                if target_uid.startswith('temp_'):
                    target_name = rel.get('target_name', '')
                    normalized = normalize_node_name(target_name)

                    if normalized:
                        real_uid = self._find_label_uid_by_name(normalized)
                        if real_uid:
                            rel['target_uid'] = real_uid
                            resolved_count += 1
                            logger.debug(f"✅ UID résolu: {target_uid} -> {real_uid}")

        logger.info(f"✅ {resolved_count} UIDs temporaires résolus")

        # Étape 2 : Créer les relations inverses
        logger.info("🔄 Création des relations inverses...")
        node_by_uid = {n['uid']: n for n in all_nodes if 'uid' in n}

        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            for rel in node.get('outgoing_relations', []):
                target_uid = rel.get('target_uid')

                # Skip si c'est toujours un UID temporaire
                if not target_uid or target_uid.startswith('temp_'):
                    continue
                
                target_node = node_by_uid.get(target_uid)
                if not target_node:
                    continue
                
                # Créer la relation inverse
                inverse = {
                    'source_uid': node_uid,
                    'relation_type': rel['relation_type'],
                    'category': rel.get('category', 'custom'),
                    'source_name': node.get('label', node.get('name', 'Unknown'))
                }

                incoming = target_node.setdefault('incoming_relations', [])
                if not any(r['source_uid'] == node_uid and r['relation_type'] == rel['relation_type'] for r in incoming):
                    incoming.append(inverse)
                    inverse_count += 1

        logger.info(f"✅ {inverse_count} relations inverses créées")

        # Étape 3 : Log statistiques
        total_relations = sum(len(n.get('outgoing_relations', [])) for n in all_nodes)
        logger.info(f"📊 Graphe complet: {len(all_nodes)} nœuds, {total_relations} relations")

    def _save_scan_results_to_storage(self):
        """
        Sauvegarde les résultats du scan (classes, fonctions, variables, relations)
        dans SQLite ET Dgraph.

        À appeler après _on_browse_project() pour persister les nouveaux nœuds.
        """
        if not self.current_project_name or not self.current_project_profile_data:
            logger.error("Aucun projet sélectionné pour la sauvegarde.")
            return False

        logger.info("=" * 80)
        logger.info("💾 SAUVEGARDE DES RÉSULTATS DE SCAN")
        logger.info("=" * 80)

        try:
            # ÉTAPE 1: Mettre à jour les structures en mémoire
            logger.info("\n📝 Étape 1: Mise à jour des structures en mémoire...")
            self._finalize_project_data_after_scan()

            # ÉTAPE 2: Sauvegarder dans SQLite
            logger.info("\n💾 Étape 2: Sauvegarde dans SQLite...")
            sqlite_success = self._save_project_to_sqlite(self.current_project_profile_data)
            if not sqlite_success:
                logger.error("❌ Échec sauvegarde SQLite")
                return False
            logger.info("✅ Sauvegarde SQLite réussie")

            # ÉTAPE 3: Générer et insérer mutations Dgraph
            logger.info("\n🔄 Étape 3: Insertion dans Dgraph...")
            mutations = self._transform_profile_to_dgraph_mutations()

            if not mutations:
                logger.error("❌ Aucune mutation générée")
                return False

            logger.info(f"📊 {len(mutations)} mutations à insérer")

            dgraph_success = self.dgraph_connector.insert_mutations(mutations)
            if not dgraph_success:
                logger.error("❌ Échec insertion Dgraph")
                return False

            logger.info("✅ Insertion Dgraph réussie")

            # ÉTAPE 4: Rafraîchir les données depuis Dgraph
            logger.info("\n🔄 Étape 4: Rafraîchissement des données...")
            self._load_project_profiles()  # Recharger depuis Dgraph
            self._load_projects_from_sqlite()  # Recharger depuis SQLite

            # ÉTAPE 5: Réafficher le projet dans l'UI
            if self.current_project_name in self.project_profiles:
                self.project_combo.setCurrentText(self.current_project_name)
                self._on_project_selected(self.project_combo.currentIndex())

            logger.info("\n" + "=" * 80)
            logger.info("✅ SAUVEGARDE COMPLÈTE: Scan enregistré dans SQLite ET Dgraph")
            logger.info("=" * 80 + "\n")

            QtWidgets.QMessageBox.information(
                self,
                "Succès",
                "Résultats du scan sauvegardés dans SQLite et Dgraph avec succès!"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            import traceback
            traceback.print_exc()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la sauvegarde: {str(e)}"
            )
            return False

    def _finalize_project_data_after_scan(self):
        """
        Finalise les données du projet après le scan:
        - Résout les UIDs temporaires
        - Synchronise pending_relations
        - Valide la cohérence
        """
        logger.info("Finalisation des données du projet...")

        if not self.current_project_profile_data:
            return

        all_nodes = self._get_all_nodes()

        # 1. Assurer que tous les nœuds ont des UIDs valides (pas temporaires)
        logger.info("✓ Résolution des UIDs temporaires...")
        uid_mapping = {}  # Mapping temp_uid -> real_uid

        for node in all_nodes:
            uid = node.get('uid')
            if not uid or uid.startswith('temp_'):
                # Générer un UID permanent
                new_uid = str(uuid.uuid4())
                if uid:
                    uid_mapping[uid] = new_uid
                node['uid'] = new_uid
                logger.debug(f"  UID généré: {new_uid[:8]}... pour {node.get('label', 'unknown')}")

        # 2. Mettre à jour les références d'UIDs dans les relations
        logger.info("✓ Mise à jour des références aux UIDs...")
        for node in all_nodes:
            for rel in node.get('outgoing_relations', []):
                old_target = rel.get('target_uid')
                if old_target in uid_mapping:
                    rel['target_uid'] = uid_mapping[old_target]
                    logger.debug(f"  Relation mise à jour: {old_target} -> {uid_mapping[old_target]}")

        # 3. Synchroniser pending_relations avec les relations actuelles
        logger.info("✓ Synchronisation pending_relations...")
        self.pending_relations.clear()

        for node in all_nodes:
            node_uid = node.get('uid')
            if not node_uid:
                continue
            
            relations_list = []
            for rel in node.get('outgoing_relations', []):
                relations_list.append({
                    'target_uid': rel.get('target_uid'),
                    'relation_type': rel.get('relation_type', 'relation')
                })

            if relations_list:
                self.pending_relations[node_uid] = relations_list
                logger.debug(f"  {len(relations_list)} relations pour {node.get('label', 'unknown')}")

        # 4. Valider la cohérence
        logger.info("✓ Validation de la cohérence...")
        validation_stats = self._validate_parsed_relations()
        logger.info(f"  Validation: {validation_stats['total_parsed_in_outgoing']} relations validées")

        # 5. Construire le graphe complet
        logger.info("✓ Construction du graphe complet...")
        self._build_complete_relations_graph()

        logger.info("Finalisation terminée ✓")

    def _save_project_to_sqlite_after_scan(self, project_data):
        """
        MODIFIÉ: Sauvegarde complète du projet avec les classes/fonctions/variables
        en tant que nœuds enfants dans SQLite (via CRUD).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            project_uid = project_data.get('uid', str(uuid.uuid4()))
            project_data['uid'] = project_uid

            # 1. Upsert Workspace
            logger.info(f"  📁 Sauvegarde workspace: {project_data.get('name')}")
            cursor.execute("""
                INSERT OR REPLACE INTO workspaces 
                (uid, name, id_field, ownerId, description, files, fileContents, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_uid,
                project_data.get('name', ''),
                project_data.get('name', str(uuid.uuid4())),
                'user1',
                project_data.get('description', ''),
                json.dumps(project_data.get('files', [])),
                json.dumps(project_data.get('file_contents', {})),
                datetime.now().isoformat()
            ))

            # 2. Upsert ClusterManagement
            cluster_management_uid = f"cm_{project_uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_management 
                (uid, workspace_uid, lastUpdated, version)
                VALUES (?, ?, ?, ?)
            """, (
                cluster_management_uid,
                project_uid,
                datetime.now().isoformat(),
                '1.0'
            ))

            # 3. Upsert Clusters et Labels
            ontology = project_data.get('turing_ontology', {})
            clusters = ontology.get('clusters_detailed', [])

            for cluster_data in clusters:
                cluster_uid = cluster_data.get('uid', str(uuid.uuid4()))
                cluster_data['uid'] = cluster_uid

                logger.info(f"    📦 Sauvegarde cluster: {cluster_data.get('name')}")

                # Upsert cluster
                cursor.execute("""
                    INSERT OR REPLACE INTO clusters 
                    (uid, cluster_management_uid, name, id_field, userId, nodeType, 
                     description, codeContent, files, fileContents, is_file_cluster, 
                     createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster_uid,
                    cluster_management_uid,
                    cluster_data.get('name', ''),
                    cluster_data.get('uid', str(uuid.uuid4())),
                    'user1',
                    'cluster',
                    cluster_data.get('description', ''),
                    '',
                    json.dumps(cluster_data.get('files', [])),
                    json.dumps(cluster_data.get('file_contents', {})),
                    1 if cluster_data.get('is_file_cluster') else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Upsert labels et leurs enfants (classes/fonctions/variables)
                root_labels = cluster_data.get('root_labels', [])
                for root_label in root_labels:
                    self._save_label_and_children_recursive(
                        cursor, root_label, cluster_uid, None, 0
                    )

            # 4. Upsert Relations
            logger.info(f"  🔗 Sauvegarde relations")
            for source_uid, relations in self.pending_relations.items():
                for rel in relations:
                    rel_uid = f"rel_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO relations 
                        (uid, name, relationType, source_uid, target_uid, createdAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        rel_uid,
                        f"{rel['relation_type']}_relation",
                        rel['relation_type'],
                        source_uid,
                        rel.get('target_uid', ''),
                        datetime.now().isoformat()
                    ))

            conn.commit()
            conn.close()

            logger.info("✅ Sauvegarde SQLite complète")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde SQLite: {e}")
            return False

    def _save_label_and_children_recursive(self, cursor, label_data, cluster_uid, parent_uid, level):
        """
        MODIFIÉ: Sauvegarde récursive d'un label ET de ses enfants (y compris classes/fonctions/variables).
        """
        label_uid = label_data.get('uid', str(uuid.uuid4()))
        label_data['uid'] = label_uid

        # Sauvegarder le label lui-même
        cursor.execute("""
            INSERT OR REPLACE INTO labels 
            (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
             nodeType, category, description, codeContent, files, fileContents, 
             createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label_uid,
            cluster_uid,
            parent_uid,
            label_data.get('label', ''),
            label_data.get('id', label_uid),
            level,
            '',  # path
            parent_uid,  # parentId
            label_data.get('type', 'label'),
            json.dumps(label_data.get('category', [])),
            label_data.get('description', ''),
            '',  # codeContent
            json.dumps(label_data.get('files', [])),
            json.dumps(label_data.get('file_contents', {})),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        # NOUVEAU: Sauvegarder les classes du label
        for cls in label_data.get('classes', []):
            cls_uid = cls.get('uid', str(uuid.uuid4()))
            cls['uid'] = cls_uid

            cursor.execute("""
                INSERT OR REPLACE INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cls_uid,
                cluster_uid,
                label_uid,
                cls.get('name', ''),
                cls.get('uid', cls_uid),
                level + 1,
                '',
                label_uid,
                'class',
                json.dumps(['code_element', 'class']),
                cls.get('description', ''),
                '',
                json.dumps(cls.get('files', [])),
                json.dumps({}),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

            # Ajouter les relations de la classe
            for rel in cls.get('outgoing_relations', []):
                rel_uid = f"rel_{str(uuid.uuid4())}"
                cursor.execute("""
                    INSERT OR IGNORE INTO relations 
                    (uid, name, relationType, source_uid, target_uid, createdAt)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rel_uid,
                    f"{rel['relation_type']}_relation",
                    rel['relation_type'],
                    cls_uid,
                    rel.get('target_uid', ''),
                    datetime.now().isoformat()
                ))

        # NOUVEAU: Sauvegarder les fonctions du label
        for func in label_data.get('functions', []):
            func_uid = func.get('uid', str(uuid.uuid4()))
            func['uid'] = func_uid

            cursor.execute("""
                INSERT OR REPLACE INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                func_uid,
                cluster_uid,
                label_uid,
                func.get('name', ''),
                func.get('uid', func_uid),
                level + 1,
                '',
                label_uid,
                func.get('type', 'function'),
                json.dumps(['code_element', 'function']),
                func.get('description', ''),
                '',
                json.dumps(func.get('files', [])),
                json.dumps({}),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

            # Ajouter les relations de la fonction
            for rel in func.get('outgoing_relations', []):
                rel_uid = f"rel_{str(uuid.uuid4())}"
                cursor.execute("""
                    INSERT OR IGNORE INTO relations 
                    (uid, name, relationType, source_uid, target_uid, createdAt)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rel_uid,
                    f"{rel['relation_type']}_relation",
                    rel['relation_type'],
                    func_uid,
                    rel.get('target_uid', ''),
                    datetime.now().isoformat()
                ))

        # NOUVEAU: Sauvegarder les variables du label
        for var in label_data.get('variables', []):
            var_uid = var.get('uid', str(uuid.uuid4()))
            var['uid'] = var_uid

            cursor.execute("""
                INSERT OR REPLACE INTO labels 
                (uid, cluster_uid, parent_uid, name, id_field, level, path, parentId, 
                 nodeType, category, description, codeContent, files, fileContents, 
                 createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                var_uid,
                cluster_uid,
                label_uid,
                var.get('name', ''),
                var.get('uid', var_uid),
                level + 1,
                '',
                label_uid,
                'variable',
                json.dumps(['code_element', 'variable']),
                var.get('description', ''),
                '',
                json.dumps(var.get('files', [])),
                json.dumps({}),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

        # Sauvegarder récursivement les enfants hiérarchiques
        for child in label_data.get('children', []):
            if child.get('type') not in ['class', 'function', 'variable']:
                self._save_label_and_children_recursive(
                    cursor, child, cluster_uid, label_uid, level + 1
                )

    def _map_all_children_uids(self, node_data, parent_dgraph_uid, mutations, label_uids, cluster_uid, level):
        """Crée les mutations pour tous les enfants et met à jour label_uids"""

        parent_children = []  # Collecter les UIDs des enfants

        # Mapper les classes
        for cls in node_data.get('classes', []):
            cls_mutation = self._create_label_mutation(cls, level, cluster_uid)
            mutations.append(cls_mutation)
            label_uids[cls['uid']] = cls_mutation["uid"]
            parent_children.append({"uid": cls_mutation["uid"]})

            if "parents" not in cls_mutation:
                cls_mutation["parents"] = []
            cls_mutation["parents"].append({"uid": parent_dgraph_uid})

        # Mapper les fonctions
        for func in node_data.get('functions', []):
            func_mutation = self._create_label_mutation(func, level, cluster_uid)
            mutations.append(func_mutation)
            label_uids[func['uid']] = func_mutation["uid"]
            parent_children.append({"uid": func_mutation["uid"]})

            if "parents" not in func_mutation:
                func_mutation["parents"] = []
            func_mutation["parents"].append({"uid": parent_dgraph_uid})

        # Mapper les variables
        for var in node_data.get('variables', []):
            var_mutation = self._create_label_mutation(var, level, cluster_uid)
            mutations.append(var_mutation)
            label_uids[var['uid']] = var_mutation["uid"]
            parent_children.append({"uid": var_mutation["uid"]})

            if "parents" not in var_mutation:
                var_mutation["parents"] = []
            var_mutation["parents"].append({"uid": parent_dgraph_uid})

        # Mapper les enfants hiérarchiques
        for child in node_data.get('children', []):
            if child.get('type') not in ['class', 'function', 'variable']:
                child_mutation = self._create_label_mutation(child, level, cluster_uid)
                mutations.append(child_mutation)
                label_uids[child['uid']] = child_mutation["uid"]
                parent_children.append({"uid": child_mutation["uid"]})

                if "parents" not in child_mutation:
                    child_mutation["parents"] = []
                child_mutation["parents"].append({"uid": parent_dgraph_uid})

                self._map_all_children_uids(child, child_mutation["uid"], mutations, label_uids, cluster_uid, level + 1)

        # Lier les enfants au parent dans les mutations
        for mutation in mutations:
            if mutation.get("uid") == parent_dgraph_uid:
                mutation["children"] = parent_children
                break

    def closeEvent(self, event):
        """Ferme proprement le connector lors de la fermeture du widget."""
        if self.dgraph_connector: 
            self.dgraph_connector.close()
        super().closeEvent(event)