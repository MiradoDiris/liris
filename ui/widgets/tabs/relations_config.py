from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QListWidgetItem, QHBoxLayout, QLabel, QPushButton, QInputDialog
from PyQt5.QtCore import Qt
from utils.dgraph_connector import LirisDgraphConnector
from ui.styles.platform_config_style import PlatformConfigStyle
from utils.logger import logger
from utils.multi_language_parser import (
    normalize_node_name
)
from utils.dgraph_project_manager import DgraphProjectManager


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
        self.current_project_profile_data = None
        self._init_ui()

        self.dgraph_connector = LirisDgraphConnector(auto_reset=False)
        self.dgraph_manager = DgraphProjectManager(self.dgraph_connector)

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 5, 10, 10)

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
        self.relations_list.setMaximumHeight(150)
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
        if hasattr(self.parent_widget, 'current_selected_label_uid') and self.parent_widget.current_selected_label_uid:
            logger.info(f"DEBUG: Refresh relations pour {self.parent_widget.current_selected_label_uid}")
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
            if name:
                return name

        # ✅ CORRECTION : Utiliser current_project_profile_data local
        if not self.current_project_profile_data:
            # Fallback : récupérer depuis parent_widget
            self.current_project_profile_data = getattr(
                self.parent_widget, 
                'current_project_profile_data', 
                None
            )

        if not self.current_project_profile_data:
            return ""

        # Fallback: chercher directement dans les nœuds
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)
        node = next((n for n in all_nodes if n.get('uid') == uid), None)
        if node:
            name = node.get('label') or node.get('name')
            if name:
                return name

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
        """Affiche TOUTES les relations : hiérarchiques + parsées + custom + non résolues"""
        self.relations_list.clear()
        if not source_uid:
            return

        # ✅ Synchroniser les données si nécessaire
        if not self.current_project_profile_data:
            self.current_project_profile_data = getattr(
                self.parent_widget, 
                'current_project_profile_data', 
                None
            )

        if not self.current_project_profile_data:
            logger.warning("❌ Aucune donnée de projet disponible")
            return

        if not hasattr(self.parent_widget, 'dgraph_to_local'):
            self.parent_widget.dgraph_to_local = {}

        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()
        all_nodes = self.dgraph_manager._get_all_nodes(self.current_project_profile_data)
        node = next((n for n in all_nodes if n['uid'] == source_uid), None)

        if not node:
            logger.warning(f"Noeud {source_uid} non trouvé")
            return

        relations_added = {'custom': 0, 'parsed': 0, 'hierarchy': 0, 'unresolved': 0}
        seen_relations = set()

        # === 1. RELATIONS SORTANTES (outgoing_relations) ===
        if self.show_dependencies:
            logger.debug(f"DEBUG: Traitement outgoing_relations pour {node.get('label')}")
            logger.debug(f"DEBUG: Nombre d'outgoing_relations: {len(node.get('outgoing_relations', []))}")

            for r in node.get('outgoing_relations', []):
                target_uid = r.get('target_uid')

                # ✅ CORRECTION : Ne plus ignorer tous les UIDs temporaires
                if not target_uid:
                    continue
                
                # Gérer les UIDs temporaires/non résolus avec affichage spécial
                if target_uid.startswith('temp_') or target_uid.startswith('unresolved_'):
                    target_name = r.get('target_name', 'Inconnu')
                    rel_type = r.get('relation_type', 'relation')
                    line_info = f" (L{r.get('line', '?')})" if r.get('line') else ""

                    source_name = self._get_node_name(source_uid)
                    if not source_name:
                        source_name = node.get('label', node.get('name', 'Unknown'))

                    display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} ⚠️ [NON RÉSOLU]"

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
                    item.setForeground(QtGui.QColor("#95a5a6"))  # Gris
                    self.relations_list.addItem(item)
                    relations_added['unresolved'] += 1
                    logger.debug(f"DEBUG: Relation non résolue ajoutée: {target_name}")
                    continue
                
                # Mapper Dgraph UID si nécessaire
                if target_uid.startswith('0x') and len(target_uid) <= 10:
                    target_uid = dgraph_to_local.get(target_uid, target_uid)

                target_name = self._get_node_name(target_uid)
                if not target_name:
                    target_name = r.get('target_name', 'Inconnu')
                    if not target_name or target_name == 'Inconnu':
                        # ✅ Afficher quand même avec marqueur
                        target_name = f"[{target_uid[:8]}...]"

                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')

                # Créer clé unique
                rel_key = f"{source_uid}->{target_uid}:{rel_type}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                source_name = self._get_node_name(source_uid)
                if not source_name:
                    source_name = node.get('label', node.get('name', 'Unknown'))

                # Affichage selon catégorie
                line_info = f" (L{r.get('line', '?')})" if r.get('line') else ""
                if category == 'parsed':
                    display = f"{source_name} →[{rel_type}]→ {target_name}{line_info} 📝 [CODE]"
                    color = "#FF9800"
                else:
                    display = f"{source_name} →[{rel_type}]→ {target_name}"
                    color = "#2196F3"

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

                logger.debug(f"DEBUG: Relation sortante ajoutée: {source_name} --{rel_type}--> {target_name} [{category}]")

        # === 2. RELATIONS ENTRANTES (incoming_relations) ===
        if self.show_dependencies:
            logger.debug(f"DEBUG: Traitement incoming_relations pour {node.get('label')}")
            logger.debug(f"DEBUG: Nombre d'incoming_relations: {len(node.get('incoming_relations', []))}")

            for r in node.get('incoming_relations', []):
                source_uid_rel = r.get('source_uid')

                if not source_uid_rel:
                    continue
                
                # ✅ Gérer les temporaires en incoming aussi
                if source_uid_rel.startswith('temp_') or source_uid_rel.startswith('unresolved_'):
                    source_name = r.get('source_name', 'Inconnu')
                    rel_type = r.get('relation_type', 'relation')
                    target_name = self._get_node_name(source_uid)

                    if not target_name:
                        target_name = node.get('label', node.get('name', 'Unknown'))

                    display = f"{source_name} →[{rel_type}]→ {target_name} ⚠️ [NON RÉSOLU IN]"

                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, {
                        "category": "parsed_unresolved",
                        "direction": "in",
                        "source": source_uid_rel,
                        "target": source_uid,
                        "source_name": source_name,
                        "type": rel_type
                    })
                    item.setForeground(QtGui.QColor("#95a5a6"))
                    self.relations_list.addItem(item)
                    relations_added['unresolved'] += 1
                    continue
                
                if source_uid_rel.startswith('0x') and len(source_uid_rel) <= 10:
                    source_uid_rel = dgraph_to_local.get(source_uid_rel, source_uid_rel)

                source_name = self._get_node_name(source_uid_rel)
                if not source_name:
                    source_name = r.get('source_name', 'Inconnu')
                    if not source_name or source_name == 'Inconnu':
                        source_name = f"[{source_uid_rel[:8]}...]"

                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')
                target_name = self._get_node_name(source_uid)

                if not target_name:
                    target_name = node.get('label', node.get('name', 'Unknown'))

                rel_key = f"{source_uid_rel}->{source_uid}:{rel_type}"
                if rel_key in seen_relations:
                    continue
                seen_relations.add(rel_key)

                # Affichage selon catégorie
                if category == 'parsed':
                    display = f"{source_name} →[{rel_type}]→ {target_name} 📝 [CODE IN]"
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

                logger.debug(f"DEBUG: Relation entrante ajoutée: {source_name} --{rel_type}--> {target_name} [{category}]")

        # === 3. HIÉRARCHIE: Enfants ===
        if self.show_hierarchy:
            logger.debug(f"DEBUG: Traitement children pour {node.get('label')}")
            children = node.get('children', [])
            logger.debug(f"DEBUG: Nombre d'enfants: {len(children)}")

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

                logger.debug(f"DEBUG: Relation hiérarchique (child) ajoutée: {source_name} --child--> {child_name}")

        # === 4. HIÉRARCHIE: Parents ===
        if self.show_hierarchy:
            logger.debug(f"DEBUG: Traitement parents pour {node.get('label')}")
            parents = node.get('parents', [])
            logger.debug(f"DEBUG: Nombre de parents: {len(parents)}")

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

                logger.debug(f"DEBUG: Relation hiérarchique (parent) ajoutée: {source_name} --parent--> {parent_name}")

        # Log pour debug
        total = sum(relations_added.values())
        logger.info(f"✅ Relations affichées pour {node.get('label', source_uid)}: "
                    f"{relations_added['parsed']} parsées, "
                    f"{relations_added['custom']} custom, "
                    f"{relations_added['hierarchy']} hiérarchie, "
                    f"{relations_added['unresolved']} non résolues "
                    f"(Total: {total}, Uniques: {len(seen_relations)})")

        if total == 0:
            no_rel_item = QListWidgetItem("(Aucune relation)")
            no_rel_item.setForeground(QtGui.QColor("#999"))
            self.relations_list.addItem(no_rel_item)
            logger.warning(f"⚠️ Aucune relation trouvée pour {node.get('label', source_uid)}")
    
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
        """
        Méthode de diagnostic pour vérifier l'affichage des relations.
        Affiche des logs détaillés sur les nœuds et relations pour debug.
        """
        # Récupérer les données du projet via parent (ou local)
        profile_data = self.current_project_profile_data
        if not profile_data and self.parent_widget:
            profile_data = getattr(self.parent_widget, 'current_project_profile_data', None)

        if not profile_data:
            logger.warning("❌ Aucune donnée de projet disponible pour le diagnostic des relations.")
            return

        logger.info(f"📦 Projet détecté pour diagnostic: {profile_data.get('name', 'Unknown')}")

        # Récupérer tous les nœuds via le manager avec données passées
        all_nodes = self.dgraph_manager._get_all_nodes(profile_data)
        node = next((n for n in all_nodes if n['uid'] == node_uid), None)

        if not node:
            logger.error(f"❌ Nœud {node_uid} non trouvé dans {len(all_nodes)} nœuds")
            return

        node_name = node.get('label', node.get('name', 'Unknown'))
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 DIAGNOSTIC RELATIONS pour : {node_name} (UID: {node_uid[:8]}...)")
        logger.info(f"{'='*60}\n")

            # 1. Vérifier outgoing_relations
        outgoing = node.get('outgoing_relations', [])
        logger.info(f"📤 Outgoing relations: {len(outgoing)}")
        for i, rel in enumerate(outgoing[:5], 1):
            logger.info(f"   {i}. Type: {rel.get('relation_type')}, "
                        f"Target: {rel.get('target_uid')[:8]}..., "
                        f"Category: {rel.get('category', 'N/A')}")
        if len(outgoing) > 5:
            logger.info(f"   ... et {len(outgoing) - 5} autres")

        # 2. Vérifier dict 'relations'
        relations_dict = node.get('relations', {})
        logger.info(f"\n📋 Dict 'relations': {len(relations_dict)} types")
        for rel_type, rel_list in relations_dict.items():
            logger.info(f"   - {rel_type}: {len(rel_list)} relation(s)")
            for i, rel in enumerate(rel_list[:3], 1):
                logger.info(f"      {i}. target: {rel.get('target', 'N/A')}, "
                            f"line: {rel.get('line', 'N/A')}")
            if len(rel_list) > 3:
                logger.info(f"      ... et {len(rel_list) - 3} autres")

        # 3. Vérifier incoming_relations
        incoming = node.get('incoming_relations', [])
        logger.info(f"\n📥 Incoming relations: {len(incoming)}")
        for i, rel in enumerate(incoming[:5], 1):
            logger.info(f"   {i}. Type: {rel.get('relation_type')}, "
                        f"Source: {rel.get('source_uid')[:8]}...")
        if len(incoming) > 5:
            logger.info(f"   ... et {len(incoming) - 5} autres")

        # 4. Vérifier les filtres actifs
        logger.info(f"\n🔘 Filtres actifs:")
        logger.info(f"   - Hiérarchie: {self.show_hierarchy}")
        logger.info(f"   - Dépendances: {self.show_dependencies}")

        # 5. Vérifier label_uid_to_info
        logger.info(f"\n📚 label_uid_to_info:")
        logger.info(f"   Total entrées: {len(self.parent_widget.label_uid_to_info)}")

        logger.info(f"\n{'='*60}\n")