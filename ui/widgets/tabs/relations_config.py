from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QListWidgetItem, QHBoxLayout, QLabel, QPushButton, QInputDialog
from PyQt5.QtCore import Qt
from utils.logger import logger
from utils.multi_language_parser import (
    normalize_node_name
)


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
        self.hierarchy_btn = QPushButton("🔗 Hiérarchie")
        self.hierarchy_btn.setCheckable(True)
        self.hierarchy_btn.setChecked(True)
        self.hierarchy_btn.setStyleSheet(self._get_filter_button_style())
        self.hierarchy_btn.clicked.connect(self._on_filter_hierarchy)
        filter_layout.addWidget(self.hierarchy_btn)

        # Bouton Dépendances
        self.dependencies_btn = QPushButton("📊 Dépendances")
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

        button_style = """
            QPushButton {
                background-color: #e8e8e8;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover:!pressed {
                background-color: #ffffff;
                color: black;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #d5d5d5;
                color: #888888;
                border: 1px solid #bbb;
            }
        """

        self.add_button = QtWidgets.QPushButton("➕ Nouvelle relation")
        self.add_button.setStyleSheet(button_style)
        self.add_button.setMaximumWidth(160)
        self.add_button.clicked.connect(self._on_add_new_relation)
        self.add_button.setEnabled(False)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QtWidgets.QPushButton("✏️ Modifier")
        self.edit_button.setStyleSheet(button_style)
        self.edit_button.setMaximumWidth(110)
        self.edit_button.clicked.connect(self._on_edit)
        self.edit_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QtWidgets.QPushButton("🗑️ Supprimer")
        self.remove_button.setStyleSheet(button_style)
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
        """Gère la sélection d'une relation pour afficher source/target."""
        if not current:
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
        
        source_name = source_info.get('name', source_info.get('label', ''))
        target_name = target_info.get('name', target_info.get('label', ''))
        
        # Mettre à jour l'affichage
        self.source_label.setText(source_name)
        self.target_label.setText(target_name)

        # Activer les boutons de modification et suppression
        rel_category = rel.get('category', 'custom')
        if rel_category == 'hierarchy':
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)

    def _on_relation_selected(self, current):
        """Gère la sélection d'une relation pour afficher source/target."""
        if not current:
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
        
        source_name = source_info.get('name', source_info.get('label', ''))
        target_name = target_info.get('name', target_info.get('label', ''))
        
        # Mettre à jour l'affichage
        self.source_label.setText(source_name)
        self.target_label.setText(target_name)

        # Activer les boutons de modification et suppression
        rel_category = rel.get('category', 'custom')
        if rel_category == 'hierarchy':
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)

    def update_current(self, source_uid):
        """Met à jour l'affichage pour le nœud source sélectionné."""
        self.relations_list.clear()
        self.target_label.clear()
        self.edit_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
        if source_uid:
            source_info = self.parent_widget.label_uid_to_info.get(source_uid, {})
            source_name = source_info.get('name', source_info.get('label', ''))
            self.source_label.setText(source_name)
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
        """
        Met à jour la liste des relations avec TOUTES les sources.
        CORRIGÉ: Les flèches pointent maintenant vers la SOURCE
        """
        self.relations_list.clear()
        if not source_uid:
            return

        dgraph_to_local = self.parent_widget._get_dgraph_to_local_mapping()
        all_nodes = self.parent_widget._get_all_nodes()
        node = next((n for n in all_nodes if n['uid'] == source_uid), None)
        if not node:
            return

        relations_added = {'custom': 0, 'parsed': 0, 'hierarchy': 0}

        # === 1. Relations sortantes CUSTOM ===
        # CHANGEMENT: source ← target (la flèche pointe vers source_uid)
        if self.show_dependencies:
            for r in node.get('outgoing_relations', []):
                target_uid = r['target_uid']

                if target_uid.startswith('temp_'):
                    continue
                
                if target_uid.startswith('0x') and len(target_uid) == 6:
                    target_uid = dgraph_to_local.get(target_uid, target_uid)

                target_name = self._get_node_name(target_uid)
                if not target_name:
                    target_name = r.get('target_name', '')
                    if not target_name:
                        continue

                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')

                source_name = self._get_node_name(source_uid)
                if not source_name:
                    continue

                # CHANGEMENT: Inversion de la flèche
                if category == 'parsed':
                    display = f"{target_name} →({rel_type})→ {source_name} [CODE]"
                else:
                    display = f"{target_name} →({rel_type})→ {source_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": category,
                    "direction": "out",
                    "source": source_uid,  # source_uid EST la vraie source
                    "target": r['target_uid'],  # target est d'où vient la relation
                    "type": rel_type
                })
                item.setForeground(QtGui.QColor("#2196F3"))
                self.relations_list.addItem(item)
                relations_added['custom' if category == 'custom' else 'parsed'] += 1

        # === 2. Relations PARSÉES du dictionnaire 'relations' ===
        if self.show_dependencies:
            parsed_relations = node.get('relations', {})
            if parsed_relations:
                for rel_type, rel_list in parsed_relations.items():
                    for rel in rel_list:
                        target_name = rel.get('target', '')
                        if not target_name:
                            continue
                        
                        normalized = normalize_node_name(target_name)
                        target_uid = None

                        if normalized:
                            target_uid = self.parent_widget._find_label_uid_by_name(normalized)

                        if not target_uid or target_uid.startswith('unresolved_'):
                            continue

                        source_name = self._get_node_name(source_uid) or node.get('label', '')
                        if not source_name:
                            continue

                        line_info = f" (L{rel.get('line', '?')})" if rel.get('line') else ""

                        # CHANGEMENT: Inversion de la flèche
                        display = f"{target_name} →({rel_type})→ {source_name}{line_info} [PARSED]"

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

        # === 3. Relations entrantes CUSTOM ===
        # CHANGEMENT: target ← source (la flèche pointe vers source_uid qui est la cible ici)
        if self.show_dependencies:
            for r in node.get('incoming_relations', []):
                source_uid_rel = r['source_uid']

                if source_uid_rel.startswith('temp_'):
                    continue
                
                if source_uid_rel.startswith('0x') and len(source_uid_rel) == 6:
                    source_uid_rel = dgraph_to_local.get(source_uid_rel, source_uid_rel)

                source_name = self._get_node_name(source_uid_rel)
                if not source_name:
                    source_name = r.get('source_name', '')
                    if not source_name:
                        continue

                rel_type = r.get('relation_type', 'relation')
                category = r.get('category', 'custom')
                target_name = self._get_node_name(source_uid)
                if not target_name:
                    continue

                # CHANGEMENT: Inversion de la flèche
                if category == 'parsed':
                    display = f"{target_name} ←({rel_type})← {source_name} [CODE IN]"
                else:
                    display = f"{target_name} ←({rel_type})← {source_name}"

                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, {
                    "category": category,
                    "direction": "in",
                    "source": r['source_uid'],
                    "target": source_uid,
                    "type": rel_type
                })
                item.setForeground(QtGui.QColor("#4CAF50"))
                self.relations_list.addItem(item)
                relations_added['custom' if category == 'custom' else 'parsed'] += 1

        # === 4. Hiérarchie: Enfants ===
        if self.show_hierarchy:
            children = node.get('children', [])
            if children:
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

                    if not source_name:
                        continue
                    
                    # CHANGEMENT: child pointe vers parent
                    display = f"{child_name} →(child)→ {source_name}"

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
            if parents:
                for p_uid in parents:
                    if not p_uid:
                        continue

                    if p_uid.startswith('0x') and len(p_uid) == 6:
                        p_uid_mapped = dgraph_to_local.get(p_uid, p_uid)
                    else:
                        p_uid_mapped = p_uid

                    parent_name = self._get_node_name(p_uid_mapped)
                    if not parent_name:
                        continue
                    
                    source_name = self._get_node_name(source_uid)
                    if not source_name:
                        source_name = node.get('label', node.get('name', ''))

                    if not source_name:
                        continue
                    
                    # CHANGEMENT: source pointe vers parent
                    display = f"{source_name} →(parent)→ {parent_name}"

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
        logger.info(f"Relations affichées pour {node.get('label', source_uid)}: "
                    f"{relations_added['parsed']} parsées, "
                    f"{relations_added['custom']} custom, "
                    f"{relations_added['hierarchy']} hiérarchie "
                    f"(Total: {total})")

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
