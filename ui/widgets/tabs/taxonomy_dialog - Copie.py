# taxonomy_dialog.py - Version intégrée avec GraphWidget et Loader Professionnel
from datetime import datetime, timedelta
import os
import json
import uuid
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from typing import List, Dict, Optional

import self
from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.graph_widget import GraphWidget

from utils.logger import logger
from ui.localization.translator import tr
from .taxonomy_item import TaxonomyItem


from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QTimer

class LoadingOverlay(QtWidgets.QWidget):
    """Overlay de chargement compact avec QFrame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate)

        self.current_message = "Chargement..."
        self.current_progress = 0
        self.current_detail = ""

        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)

        container = QtWidgets.QFrame()
        container.setObjectName("loadingContainer")
        container.setStyleSheet("""
            QFrame#loadingContainer {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
                border: 2px solid rgba(162, 59, 45, 0.3);
            }
        """)

        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(20, 15, 20, 15)

        self.message_label = QtWidgets.QLabel(self.current_message)
        self.message_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #A23B2D;
        """)
        self.message_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.message_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedWidth(250)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background-color: rgba(162, 59, 45, 0.1);
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #A23B2D,
                    stop:0.5 #D35A4A,
                    stop:1 #A23B2D);
            }
        """)
        container_layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)

        self.percentage_label = QtWidgets.QLabel("0%")
        self.percentage_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #A23B2D;
        """)
        self.percentage_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.percentage_label)

        self.detail_label = QtWidgets.QLabel(self.current_detail)
        self.detail_label.setStyleSheet("""
            font-size: 11px;
            color: #666;
            font-style: italic;
        """)
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setFixedWidth(250)
        container_layout.addWidget(self.detail_label)

        layout.addWidget(container)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))

    def _animate(self):
        self.update()

    def show_loading(self, message="Chargement...", detail=""):
        self.current_message = message
        self.current_detail = detail
        self.message_label.setText(message)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")

        if self.parent():
            self.setGeometry(self.parent().rect())

        self.show()
        self.raise_()
        self.animation_timer.start(30)
        QtWidgets.QApplication.processEvents()

    def update_progress(self, value, message=None, detail=None):
        self.current_progress = value
        self.progress_bar.setValue(value)
        self.percentage_label.setText(f"{value}%")

        if message:
            self.current_message = message
            self.message_label.setText(message)

        if detail is not None:
            self.current_detail = detail
            self.detail_label.setText(detail)
            self.detail_label.setVisible(bool(detail))

        QtWidgets.QApplication.processEvents()

    def hide_loading(self):
        self.animation_timer.stop()
        self.hide()
        QtWidgets.QApplication.processEvents()

class DataLoaderThread(QThread):
    """Thread pour charger les données en arrière-plan."""
    
    progress_update = pyqtSignal(int, str, str)
    loading_complete = pyqtSignal(dict)
    loading_error = pyqtSignal(str)
    
    def __init__(self, dialog, uid, level):
        super().__init__()
        self.dialog = dialog
        self.uid = uid
        self.level = level
        self.is_cancelled = False
    
    def run(self):
        """Exécute le chargement des données."""
        try:
            if self.is_cancelled:
                return
            self.progress_update.emit(10, "Initialisation...", "Chargement des mappings UID")
            self.dialog._load_uid_mappings()
            
            if self.is_cancelled:
                return
            self.progress_update.emit(30, "Analyse du nœud...", f"Récupération des détails pour {self.dialog.current_central_name}")
            node_details = self.dialog._get_node_details(self.uid)
            
            relations_list = []
            if self.level == 1:
                if self.is_cancelled:
                    return
                self.progress_update.emit(50, "Chargement...", "Récupération des relations directes (Niveau 1)")
                relations_list = self.dialog._get_level_1_relations(self.uid)
                self.progress_update.emit(90, "Chargement...", f"{len(relations_list)} relations trouvées")
                
            elif self.level == 2:
                if self.is_cancelled:
                    return
                self.progress_update.emit(50, "Chargement...", "Récupération des relations de niveau 1")
                relations_list = self.dialog._get_level_1_relations(self.uid)
                
                if self.is_cancelled:
                    return
                self.progress_update.emit(70, "Chargement...", "Récupération des relations de niveau 2")
                relations_list = self.dialog._get_level_2_relations(self.uid)
                self.progress_update.emit(90, "Chargement...", f"{len(relations_list)} relations trouvées")
            
            if self.is_cancelled:
                return
            self.progress_update.emit(95, "Finalisation...", "Construction de la structure des données")
            
            related_items = []
            seen_nodes = set([self.dialog.current_central_name])
            
            for rel in relations_list:
                source_name = rel.get('source', '')
                if source_name and source_name not in seen_nodes:
                    seen_nodes.add(source_name)
                    source_uid = self.dialog._get_node_uid_by_name(source_name)
                    related_items.append({
                        'name': source_name,
                        'uid': source_uid,
                        'type': rel.get('source_type', 'dependency'),
                        'taxonomy_level': 0
                    })
                
                target_name = rel.get('target', '')
                if target_name and target_name not in seen_nodes:
                    seen_nodes.add(target_name)
                    target_uid = self.dialog._get_node_uid_by_name(target_name)
                    related_items.append({
                        'name': target_name,
                        'uid': target_uid,
                        'type': rel.get('target_type', 'dependency'),
                        'taxonomy_level': 0
                    })
            
            if self.is_cancelled:
                return
            self.progress_update.emit(100, "Terminé !", f"{len(relations_list)} relations chargées")
            
            self.loading_complete.emit({
                'relations': relations_list,
                'related_items': related_items,
                'node_details': node_details
            })
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des données: {e}")
            self.loading_error.emit(f"Erreur: {str(e)}")
    
    def cancel(self):
        """Annule le chargement."""
        self.is_cancelled = True

class TaxonomyDialog(QtWidgets.QDialog):
    """Dialogue pour sélectionner les taxonomies (fichiers/fonctions) avec niveaux"""
    
    graph_update_signal = pyqtSignal(str, str, list, dict)
    selection_validated = pyqtSignal(list)
    
    def __init__(self, project_data, dgraph_connector, parent=None):
        super().__init__(parent)
        self.project_data = project_data
        self.dgraph_connector = dgraph_connector
        self.selected_items = []
        
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}
        self.current_central_uid = None
        self.current_central_name = None
        self.loader_thread = None
        
        # ✅ Caches uniques
        self._node_cache = {}      # uid -> TaxonomyItem
        self._name_cache = {}      # (name, level) -> TaxonomyItem
        self._uid_set = set()      # UIDs déjà affichés
        
        self.setWindowTitle("Définir les Bornes - Taxonomies")
        self.resize(900, 600)
        self.setModal(True)
        
        self._init_ui()
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.hide()
        
        self.tree_widget.itemExpanded.connect(self._on_item_expanded)
        
        if not self.project_data:
            QtWidgets.QMessageBox.critical(
                self, "Erreur", "Données du projet invalides"
            )
            return
        
        self._load_taxonomy_structure()
        self._load_uid_mappings()
        self.graph_helper = GraphWidget(
            dgraph_connector=dgraph_connector,
            parent=None
        )


    def _load_complete_structure_from_dgraph(self):
        """
        ✅ VERSION FINALE — Charge la structure complète avec les relations inverses (~)
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("❌ Pas de connexion Dgraph.")
            return []

        query = """
        {
          q(func: type(Cluster)) {
            uid
            name
            id
            description
            nodeType
            files
            fileContents
            createdAt

            root_labels: ~clusters @filter(eq(level, 0)) {
              uid
              name
              label
              level
              nodeType
              path
              description
              files
              fileContents

              # ✅ Les éléments de code via les liens inverses (~)
              ~classes {
                uid
                name
                description
                line
                bases
                uses_vars
                methods { uid name description line params returns }
                variables { uid name description line var_type scope }
              }

              ~functions {
                uid
                name
                description
                line
                params
                returns
                variables { uid name description line var_type scope }
              }

              ~variables {
                uid
                name
                description
                line
                var_type
                scope
              }

              children: ~parents @filter(eq(level, 1)) {
                uid
                name
                label
                nodeType
                level
                path
                ~classes { uid name description line }
                ~functions { uid name description line }
                ~variables { uid name description line }
              }
            }
          }
        }
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            result = self.dgraph_connector._parse_response(resp)
            clusters = result.get("q", []) if result else []

            logger.info(f"✅ {len(clusters)} clusters chargés (avec ~classes/~functions/~variables)")
            return clusters

        except Exception as e:
            logger.error(f"❌ Erreur Dgraph: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_taxonomy_structure(self):
        """
        ✅ VERSION CORRIGÉE : Charge TOUS les éléments (clusters + orphelins)
        """
        logger.info("\n" + "="*70)
        logger.info("📂 CHARGEMENT STRUCTURE TAXONOMY HIÉRARCHIQUE")
        logger.info("="*70)

        self.tree_widget.clear()

        # ✅ Réinitialiser les caches
        self._node_cache.clear()
        self._name_cache.clear()
        self._uid_set.clear()

        # Récupérer clusters
        clusters = self._get_clusters_data()

        logger.info(f"📦 {len(clusters)} clusters récupérés")

        if not clusters:
            empty = QtWidgets.QTreeWidgetItem(self.tree_widget)
            empty.setText(0, "(Aucune donnée disponible)")
            empty.setForeground(0, QtGui.QBrush(QtGui.QColor("#999999")))
            return

        # ✅ Tracer tous les UIDs déjà affichés dans les clusters
        displayed_in_clusters = set()

        # Construire l'arbre des clusters
        for cluster_idx, cluster in enumerate(clusters):
            self._build_cluster_tree(cluster, cluster_idx, len(clusters))

            # ✅ Enregistrer tous les root_labels de ce cluster
            for root_label in cluster.get('root_labels', []):
                label_uid = root_label.get('uid')
                if label_uid:
                    displayed_in_clusters.add(label_uid)

        # ✅ NOUVEAU : Charger les labels orphelins (pas dans les clusters)
        self._load_orphan_labels(displayed_in_clusters)

        logger.info(f"\n✅ Structure complète affichée")
        logger.info(f"📊 Total items: {len(self._node_cache)}")
        logger.info(f"🔑 UIDs uniques: {len(self._uid_set)}")

    def _load_orphan_labels(self, displayed_uids: set):
        """
        ✅ NOUVEAU : Charge les labels niveau 0 NON affichés dans les clusters
        """
        if not self.dgraph_connector:
            return

        query = """
        {
          orphans(func: type(Label)) @filter(eq(level, 0)) {
            uid
            name
            label
            nodeType
            path
            files
            fileContents
            description

            classes {
              uid
              name
              description
              line
            }

            functions {
              uid
              name
              description
              line
            }

            variables {
              uid
              name
              description
              line
            }

            children: ~parents {
              uid
              name
              label
              nodeType
              level
            }
          }
        }
        """

        result = self._execute_dgraph_query(query)

        if not result or 'orphans' not in result:
            logger.info("ℹ️  Aucun label orphelin trouvé")
            return

        orphans = result['orphans']

        # ✅ Filtrer ceux déjà affichés
        true_orphans = [
            label for label in orphans 
            if label.get('uid') and label.get('uid') not in displayed_uids
        ]

        if not true_orphans:
            logger.info("ℹ️  Tous les labels sont dans des clusters")
            return

        logger.info(f"\n📌 {len(true_orphans)} LABELS ORPHELINS DÉTECTÉS")

        # ✅ Créer un groupe "Fichiers isolés"
        orphan_group = TaxonomyItem(
            self.tree_widget,
            f"📦 Fichiers isolés ({len(true_orphans)})",
            "folder",
            {'uid': 'orphan_group', 'name': 'Orphans'},
            0
        )
        orphan_group.loaded = True
        orphan_group.is_expandable = False

        # ✅ Ajouter chaque orphelin
        for orphan in true_orphans:
            orphan_name = orphan.get('name') or orphan.get('label', 'Fichier sans nom')
            orphan_uid = orphan.get('uid')

            # Détection type
            orphan_type = 'file' if self._has_extension(orphan_name) else 'folder'

            logger.info(f"  ➕ {orphan_name} (type={orphan_type}, uid={orphan_uid})")

            orphan_item = TaxonomyItem(
                orphan_group,
                orphan_name,
                orphan_type,
                orphan,
                1
            )
            orphan_item.loaded = False
            orphan_item.is_expandable = True

            # Cache
            if orphan_uid:
                self._node_cache[orphan_uid] = orphan_item
                self._uid_set.add(orphan_uid)

            self._add_loading_placeholder(orphan_item)

    def _build_cluster_tree(self, cluster, cluster_idx, total_clusters):
        """
        ✅ CORRIGÉ : Construction récursive COMPLÈTE
        """
        cluster_name = cluster.get('name', f'Cluster {cluster_idx + 1}')
        cluster_uid = cluster.get('uid', '')

        logger.info(f"\n[{cluster_idx + 1}/{total_clusters}] 📦 Cluster: {cluster_name}")

        # Vérification doublon
        if cluster_uid and cluster_uid in self._uid_set:
            logger.debug(f"  ⏭️ Cluster déjà affiché (uid={cluster_uid})")
            return

        cache_key = (cluster_name, 0)
        if cache_key in self._name_cache:
            logger.debug(f"  ⏭️ Cluster déjà affiché (nom={cluster_name})")
            return

        # Créer l'item cluster
        cluster_item = TaxonomyItem(
            self.tree_widget,
            cluster_name,
            'folder',
            cluster,
            0
        )
        cluster_item.is_expandable = False
        cluster_item.loaded = True

        if cluster_uid:
            self._node_cache[cluster_uid] = cluster_item
            self._uid_set.add(cluster_uid)
        self._name_cache[cache_key] = cluster_item

        # Traiter les root_labels
        root_labels = cluster.get('root_labels', [])

        if not root_labels:
            logger.info(f"  ⚠️ Aucun root_label → Création label virtuel")
            virtual_label = {
                'uid': cluster_uid,
                'name': cluster_name,
                'label': cluster_name,
                'level': 1,
                'nodeType': cluster.get('nodeType', 'file'),
                'path': '',
                'description': cluster.get('description', ''),
                'files': cluster.get('files', []),
                'fileContents': cluster.get('fileContents', ''),
                'classes': [],
                'functions': [],
                'variables': [],
                'level1': []  # ✅ Ajout
            }

            self._build_label_tree_recursive(
                parent_item=cluster_item,
                label_data=virtual_label,
                level=1
            )
        else:
            logger.info(f"  📄 {len(root_labels)} root_labels")

            for root_label in root_labels:
                label_name = root_label.get('name') or root_label.get('label', '')

                # ✅ Forcer type correct
                if self._has_extension(label_name):
                    root_label['nodeType'] = 'file'

                self._build_label_tree_recursive(
                    parent_item=cluster_item,
                    label_data=root_label,
                    level=1
                )

    def _build_label_tree_recursive(self, parent_item, label_data, level):
        """
        ✅ NOUVELLE MÉTHODE : Construction récursive COMPLÈTE de la hiérarchie
        """
        label_name = label_data.get('name') or label_data.get('label', f"Item_level_{level}")
        label_uid = label_data.get('uid', '')

        indent = "  " * level

        # Vérification doublon
        if label_uid and label_uid in self._uid_set:
            logger.debug(f"{indent}⏭️ '{label_name}' déjà affiché")
            return None

        # Détection type
        label_type = self._detect_item_type_improved(label_data, label_name)

        if self._has_extension(label_name) and label_type != 'file':
            logger.info(f"{indent}🔧 Correction: {label_name} -> file")
            label_type = 'file'

        logger.info(f"{indent}📄 {label_name} (type={label_type}, level={level})")

        # Créer l'item
        label_item = TaxonomyItem(
            parent_item,
            label_name,
            label_type,
            label_data,
            level
        )
        label_item.loaded = True
        label_item.is_expandable = False

        # Cache
        if label_uid:
            self._node_cache[label_uid] = label_item
            self._uid_set.add(label_uid)

        cache_key = (label_name, level)
        self._name_cache[cache_key] = label_item

        # ✅ AJOUTER ÉLÉMENTS DE CODE
        code_stats = self._add_all_code_elements(label_item, label_data, level)

        if code_stats['total'] > 0:
            logger.info(f"{indent}  📊 Classes: {code_stats['classes']}, "
                       f"Functions: {code_stats['functions']}, "
                       f"Variables: {code_stats['variables']}")

        # ✅ TRAITER TOUS LES NIVEAUX ENFANTS
        # Niveau suivant direct
        next_level_key = f'level{level}'
        children = label_data.get(next_level_key, [])

        if children:
            logger.info(f"{indent}  👶 {len(children)} enfants niveau {level}")
            for child in children:
                self._build_label_tree_recursive(
                    parent_item=label_item,
                    label_data=child,
                    level=level + 1
                )

        # ✅ FALLBACK : Vérifier 'children' générique
        if not children:
            generic_children = label_data.get('children', [])
            if generic_children:
                logger.info(f"{indent}  👶 {len(generic_children)} enfants génériques")
                for child in generic_children:
                    self._build_label_tree_recursive(
                        parent_item=label_item,
                        label_data=child,
                        level=level + 1
                    )

        return label_item

    def _build_label_tree(self, parent_item, label_data, level, idx, total):
        """
        ✅ CORRIGÉ : Construction complète avec gestion récursive
        """
        label_name = label_data.get('name') or label_data.get('label', f"Label {idx + 1}")
        label_uid = label_data.get('uid', '')

        indent = "  " * level

        # ✅ Vérification doublon STRICTE
        if label_uid and label_uid in self._uid_set:
            logger.debug(f"{indent}⏭️ '{label_name}' déjà affiché (uid={label_uid})")
            return None

        # ✅ Détection type AMÉLIORÉE
        label_type = self._detect_item_type_improved(label_data, label_name)

        # ✅ FORCER 'file' si extension détectée
        if self._has_extension(label_name) and label_type != 'file':
            logger.info(f"{indent}🔧 Correction type: {label_name} -> file (était {label_type})")
            label_type = 'file'

        logger.info(f"{indent}[{idx + 1}/{total}] {label_name} (type={label_type}, level={level})")

        # ✅ Créer l'item
        label_item = TaxonomyItem(
            parent_item,
            label_name,
            label_type,
            label_data,
            level
        )
        label_item.loaded = False  # ✅ CHANGÉ : lazy loading
        label_item.is_expandable = True

        # ✅ Enregistrer dans les caches IMMÉDIATEMENT
        if label_uid:
            self._node_cache[label_uid] = label_item
            self._uid_set.add(label_uid)

        cache_key = (label_name, level)
        self._name_cache[cache_key] = label_item

        # ✅ AJOUTER PLACEHOLDER au lieu de charger tout
        self._add_loading_placeholder(label_item)

        return label_item
    
    def _add_all_code_elements(self, parent_item, data, level):
        """
        ✅ VERSION SANS FALLBACK : Affiche uniquement les éléments avec noms valides
        """
        stats = {
            'classes': 0,
            'functions': 0,
            'variables': 0,
            'total': 0
        }

        def has_valid_name(element):
            """Vérifie si un élément a un nom RÉEL (non vide, non None)"""
            name = element.get('name')
            if not name:
                return False

            name = name.strip()
            if not name:
                return False

            # Rejeter les noms génériques/générés
            if name.startswith(('Unnamed', 'class-', 'func-', 'var-', 'method-')):
                return False

            return True

        # ✅ 1. CLASSES
        classes = data.get('classes', [])
        for cls in classes:
            cls_uid = cls.get('uid', '')

            # Vérifier doublon
            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ STRICT : Ignorer si pas de nom valide
            if not has_valid_name(cls):
                logger.debug(f"   ⏭️ Classe ignorée : pas de nom valide (uid={cls_uid})")
                continue
            
            cls_name = cls.get('name').strip()

            logger.debug(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

            # Créer l'item classe
            cls_item = TaxonomyItem(
                parent_item,
                cls_name,
                'class',
                cls,
                level + 1
            )
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            stats['classes'] += 1
            stats['total'] += 1

            # ✅ 1.1 MÉTHODES
            methods = cls.get('methods', [])
            for method in methods:
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                # ✅ STRICT : Ignorer si pas de nom valide
                if not has_valid_name(method):
                    logger.debug(f"      ⏭️ Méthode ignorée : pas de nom valide")
                    continue
                
                method_name = method.get('name').strip()

                logger.debug(f"      ⚙️ Méthode: '{method_name}' (uid={method_uid})")

                method_item = TaxonomyItem(
                    cls_item,
                    method_name,
                    'function',
                    method,
                    level + 2
                )
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

            # ✅ 1.2 VARIABLES de la classe
            cls_vars = cls.get('variables', [])
            for var in cls_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ STRICT : Ignorer si pas de nom valide
                if not has_valid_name(var):
                    logger.debug(f"      ⏭️ Variable ignorée : pas de nom valide")
                    continue
                
                var_name = var.get('name').strip()

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                var_item = TaxonomyItem(
                    cls_item,
                    var_name,
                    'variable',
                    var,
                    level + 2
                )
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        # ✅ 2. FONCTIONS
        functions = data.get('functions', [])
        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            # ✅ STRICT : Ignorer si pas de nom valide
            if not has_valid_name(func):
                logger.debug(f"   ⏭️ Fonction ignorée : pas de nom valide (uid={func_uid})")
                continue
            
            func_name = func.get('name').strip()

            logger.debug(f"   ⚙️ Fonction: '{func_name}' (uid={func_uid})")

            func_item = TaxonomyItem(
                parent_item,
                func_name,
                'function',
                func,
                level + 1
            )
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

            stats['functions'] += 1
            stats['total'] += 1

            # Variables de la fonction
            func_vars = func.get('variables', [])
            for var in func_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ STRICT : Ignorer si pas de nom valide
                if not has_valid_name(var):
                    continue
                
                var_name = var.get('name').strip()

                var_item = TaxonomyItem(
                    func_item,
                    var_name,
                    'variable',
                    var,
                    level + 2
                )
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        # ✅ 3. VARIABLES GLOBALES
        variables = data.get('variables', [])
        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            # ✅ STRICT : Ignorer si pas de nom valide
            if not has_valid_name(var):
                logger.debug(f"   ⏭️ Variable globale ignorée : pas de nom valide")
                continue
            
            var_name = var.get('name').strip()

            logger.debug(f"   📦 Variable globale: '{var_name}' (uid={var_uid})")

            var_item = TaxonomyItem(
                parent_item,
                var_name,
                'variable',
                var,
                level + 1
            )
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

            stats['variables'] += 1
            stats['total'] += 1

        return stats
    
    def _add_classes_to_tree(self, parent_item, data_node):
        """✅ VERSION SANS FALLBACK"""

        def has_valid_name(element):
            """Vérifie si un élément a un nom RÉEL"""
            name = element.get('name')
            if not name:
                return False

            name = name.strip()
            if not name or name.startswith(('Unnamed', 'class-', 'func-', 'var-')):
                return False

            return True

        classes = data_node.get('classes', [])

        for cls in classes:
            cls_uid = cls.get('uid', '')

            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ Ignorer si pas de nom valide
            if not has_valid_name(cls):
                logger.debug(f"   ⏭️ Classe ignorée (pas de nom)")
                continue
            
            cls_name = cls.get('name').strip()

            logger.debug(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

            cls_item = TaxonomyItem(parent_item, cls_name, 'class', cls, parent_item.level + 1)
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            # ✅ MÉTHODES
            for method in cls.get('methods', []):
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                if not has_valid_name(method):
                    continue
                
                method_name = method.get('name').strip()

                logger.debug(f"      ⚙️ Méthode: '{method_name}' (uid={method_uid})")

                method_item = TaxonomyItem(cls_item, method_name, 'function', method, cls_item.level + 1)
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

            # ✅ VARIABLES DE LA CLASSE
            for var in cls.get('variables', []):
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                if not has_valid_name(var):
                    continue
                
                var_name = var.get('name').strip()

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                var_item = TaxonomyItem(cls_item, var_name, 'variable', var, cls_item.level + 1)
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

    def _get_clusters_data(self):
        """
        ✅ VERSION CORRIGÉE : Récupère TOUTE la hiérarchie récursivement
        """
        clusters = []

        if self.dgraph_connector and self.dgraph_connector.client:
            logger.info("📡 Chargement depuis Dgraph (avec hiérarchie complète)...")

            # ✅ CORRECTION : Requête récursive sur TOUS les niveaux
            query_labels = """
            {
              all_labels(func: type(Label)) @filter(eq(level, 0)) {
                uid
                name
                id
                level
                path
                nodeType
                category
                description
                files
                fileContents

                parent_clusters: clusters {
                  uid
                  name
                  id
                  description
                  nodeType
                  files
                  fileContents
                  createdAt
                  updatedAt
                }

                # ✅ Éléments de code du niveau 0
                classes {
                  uid
                  name
                  description
                  line
                  bases
                  uses_vars
                  methods { uid name description line params returns }
                  variables { uid name description line var_type scope }
                }

                functions {
                  uid
                  name
                  description
                  line
                  params
                  returns
                  variables { uid name description line var_type scope }
                }

                variables {
                  uid
                  name
                  description
                  line
                  var_type
                  scope
                }

                # ✅ NIVEAU 1 (enfants directs)
                level1: ~parents @filter(eq(level, 1)) {
                  uid
                  name
                  id
                  level
                  nodeType
                  path
                  description
                  files
                  fileContents

                  classes {
                    uid
                    name
                    description
                    line
                    methods { uid name description line }
                    variables { uid name description line }
                  }

                  functions {
                    uid
                    name
                    description
                    line
                    variables { uid name description line }
                  }

                  variables {
                    uid
                    name
                    description
                    line
                  }

                  # ✅ NIVEAU 2
                  level2: ~parents @filter(eq(level, 2)) {
                    uid
                    name
                    id
                    level
                    nodeType
                    path
                    description
                    files
                    fileContents

                    classes {
                      uid
                      name
                      description
                      line
                      methods { uid name description line }
                    }

                    functions {
                      uid
                      name
                      description
                      line
                    }

                    variables {
                      uid
                      name
                      description
                      line
                    }

                    # ✅ NIVEAU 3
                    level3: ~parents @filter(eq(level, 3)) {
                      uid
                      name
                      id
                      level
                      nodeType
                      path
                      description
                      files
                      fileContents

                      classes { uid name description line }
                      functions { uid name description line }
                      variables { uid name description line }

                      # ✅ NIVEAU 4
                      level4: ~parents @filter(eq(level, 4)) {
                        uid
                        name
                        id
                        level
                        nodeType
                        path
                        description
                        files
                        fileContents

                        classes { uid name description line }
                        functions { uid name description line }
                        variables { uid name description line }
                      }
                    }
                  }
                }
              }
            }
            """

            try:
                txn = self.dgraph_connector.client.txn(read_only=True)
                resp = txn.query(query_labels)
                txn.discard()

                result = self.dgraph_connector._parse_response(resp)
                all_labels = result.get('all_labels', [])

                logger.info(f"📥 Récupéré {len(all_labels)} labels niveau 0 depuis Dgraph")

                clusters_dict = {}

                # Regrouper par cluster parent
                for label in all_labels:
                    parent_clusters = label.get('parent_clusters', [])

                    if not parent_clusters:
                        # Label orphelin → créer un cluster virtuel
                        uid = label.get('uid', f"generated_{uuid.uuid4()}")
                        clusters_dict[uid] = {
                            'uid': uid,
                            'name': label.get('name', 'Label isolé'),
                            'id': uid,
                            'nodeType': label.get('nodeType', 'file'),
                            'root_labels': [label]
                        }
                        continue

                    for cluster_data in parent_clusters:
                        cluster_uid = cluster_data.get('uid')
                        if not cluster_uid:
                            continue
                        
                        if cluster_uid not in clusters_dict:
                            clusters_dict[cluster_uid] = {
                                'uid': cluster_uid,
                                'name': cluster_data.get('name', 'Cluster sans nom'),
                                'description': cluster_data.get('description', ''),
                                'nodeType': cluster_data.get('nodeType', 'cluster'),
                                'files': cluster_data.get('files', []),
                                'fileContents': cluster_data.get('fileContents', ''),
                                'root_labels': []
                            }

                        clusters_dict[cluster_uid]['root_labels'].append(label)

                clusters = list(clusters_dict.values())
                logger.info(f"📦 {len(clusters)} clusters chargés avec hiérarchie complète.")

                # ✅ DEBUG : Afficher structure
                for cluster in clusters[:3]:  # Premiers 3 clusters
                    logger.info(f"\n📦 Cluster: {cluster.get('name')}")
                    for root in cluster.get('root_labels', [])[:5]:
                        logger.info(f"  📄 Root: {root.get('name')}")
                        level1 = root.get('level1', [])
                        logger.info(f"    └─ {len(level1)} enfants niveau 1")
                        for l1 in level1[:3]:
                            logger.info(f"      📁 {l1.get('name')}")
                            level2 = l1.get('level2', [])
                            logger.info(f"        └─ {len(level2)} enfants niveau 2")

                return clusters

            except Exception as e:
                logger.error(f"❌ Erreur Dgraph lors du chargement : {e}")
                import traceback
                traceback.print_exc()

        logger.warning("⚠️ Aucune source Dgraph active, fallback local.")
        return []


    def _process_label_recursive(self, label_data, cluster_uid, mutations, 
                         label_uids, seen_uids, level=0, parent_uid=None, parent_path=""):
        """
        ✅ CORRIGÉ : Génère des blank nodes valides
        """
        if not label_data:
            logger.warning("⚠️ label_data vide")
            return

        label_name = label_data.get('label') or label_data.get('name', f"Label_level_{level}")
        current_path = f"{parent_path}/{label_name}" if parent_path else label_name
        label_data['path'] = current_path

        # 1️⃣ Créer mutation avec blank node
        try:
            label_mutation = self._create_label_mutation(
                label_data, 
                level=level, 
                cluster_uid=cluster_uid
            )
        except Exception as e:
            logger.error(f"❌ Erreur création mutation pour '{label_name}': {e}")
            return

        label_uid = label_mutation["uid"]
        
        # ✅ VALIDATION
        if not self._validate_uid_format(label_uid):
            logger.error(f"❌ UID label invalide: {label_uid}")
            return

        if label_uid in seen_uids:
            logger.debug(f"⏭️ Label '{label_name}' déjà traité")
            return

        seen_uids.add(label_uid)
        mutations.append(label_mutation)

        # ✅ Enregistrer mapping (local_uid → dgraph_uid)
        local_uid = label_data.get('uid') or label_data.get('id')
        if local_uid:
            label_uids[local_uid] = label_uid

        # 2️⃣ Lier au parent
        if parent_uid:
            if "parents" not in label_mutation:
                label_mutation["parents"] = []
            label_mutation["parents"].append({"uid": parent_uid})
            label_mutation["parentId"] = parent_uid

        # 3️⃣ Traiter éléments de code
        classes = label_data.get('classes', [])
        functions = label_data.get('functions', [])
        variables = label_data.get('variables', [])

        if classes or functions or variables:
            # ✅ Générer blank nodes pour code elements
            for cls in classes:
                local_cls_uid = cls.get('uid', str(uuid.uuid4()))
                dgraph_cls_uid = self._sanitize_uid("", 'class')
                label_uids[local_cls_uid] = dgraph_cls_uid
                cls['dgraph_uid'] = dgraph_cls_uid  # Nouveau champ
            
            for func in functions:
                local_func_uid = func.get('uid', str(uuid.uuid4()))
                dgraph_func_uid = self._sanitize_uid("", 'func')
                label_uids[local_func_uid] = dgraph_func_uid
                func['dgraph_uid'] = dgraph_func_uid
            
            for var in variables:
                local_var_uid = var.get('uid', str(uuid.uuid4()))
                dgraph_var_uid = self._sanitize_uid("", 'var')
                label_uids[local_var_uid] = dgraph_var_uid
                var['dgraph_uid'] = dgraph_var_uid
            
            try:
                self._process_code_elements(
                    label_data, 
                    label_uid, 
                    mutations, 
                    label_uids, 
                    seen_uids
                )
            except Exception as e:
                logger.error(f"❌ Erreur traitement code elements: {e}")

        # 4️⃣ Récursion enfants
        for idx, child in enumerate(label_data.get('children', [])):
            try:
                self._process_label_recursive(
                    child,
                    cluster_uid,
                    mutations,
                    label_uids,
                    seen_uids,
                    level + 1,
                    label_uid,
                    current_path
                )
            except Exception as e:
                child_name = child.get('label') or child.get('name', f'child_{idx}')
                logger.error(f"❌ Erreur enfant '{child_name}': {e}")
                continue

    def _diagnose_missing_relations_detailed(self, selected_uids: List[str]):
        """
        ✅ DIAGNOSTIC APPROFONDI : Analyse pourquoi les relations ne sont pas trouvées
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔬 DIAGNOSTIC APPROFONDI - Relations manquantes")
        logger.info(f"{'='*70}")

        for idx, uid in enumerate(selected_uids[:3]):  # Limiter à 3 pour éviter trop de logs
            logger.info(f"\n🔍 Analyse UID {idx+1}/{min(3, len(selected_uids))}: {uid}")

            # ✅ UTILISER la méthode de diagnostic de graph_widget
            if hasattr(self.graph_helper, '_diagnose_relation_issues'):
                diagnostic = self.graph_helper._diagnose_relation_issues(uid)

                if diagnostic.get('node_exists'):
                    node_details = diagnostic.get('node_details', {})
                    logger.info(f"  ✅ Nœud trouvé: {node_details.get('name', 'N/A')}")
                    logger.info(f"     Type: {node_details.get('nodeType', 'unknown')}")

                    # Afficher les relations par prédicat
                    rel_counts = diagnostic.get('relation_counts', {})
                    if rel_counts:
                        logger.info(f"\n  📊 Relations par prédicat:")
                        for pred, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
                            if count > 0:
                                logger.info(f"     • {pred}: {count}")
                    else:
                        logger.warning(f"  ⚠️ Aucune relation trouvée pour ce nœud")

                    # Afficher les problèmes identifiés
                    if diagnostic.get('issues'):
                        logger.warning(f"\n  ⚠️ Problèmes identifiés:")
                        for issue in diagnostic['issues']:
                            logger.warning(f"     • {issue}")
                else:
                    logger.error(f"  ❌ Nœud {uid} n'existe pas dans Dgraph")
            else:
                # Fallback si la méthode n'existe pas dans graph_widget
                logger.warning(f"  ⚠️ Méthode de diagnostic non disponible")
                self._diagnose_missing_relations_fallback(uid)

        # ✅ VÉRIFIER RELATIONS CROISÉES entre les UIDs sélectionnés
        if len(selected_uids) > 1:
            logger.info(f"\n🔗 ANALYSE RELATIONS CROISÉES")
            self._diagnose_cross_relations(selected_uids)

        logger.info(f"{'='*70}\n")

    def _diagnose_missing_relations_fallback(self, uid: str):
        """
        ✅ FALLBACK : Diagnostic simple si graph_widget indisponible
        """
        if not uid or not self.dgraph_connector:
            return

        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            nodeType

            # Compter relations
            parents {{ uid }}
            children: ~parents {{ uid }}
            imports {{ uid }}
            ~imports {{ uid }}
            calls {{ uid }}
            ~calls {{ uid }}
          }}

          # Relations type Relation
          relations_out(func: type(Relation)) @filter(uid_in(source, {uid})) {{
            uid
          }}

          relations_in(func: type(Relation)) @filter(uid_in(target, {uid})) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            node = result['node'][0]

            rel_counts = {
                'parents': len(node.get('parents', [])),
                'children': len(node.get('children', [])),
                'imports': len(node.get('imports', [])),
                '~imports': len(node.get('~imports', [])),
                'calls': len(node.get('calls', [])),
                '~calls': len(node.get('~calls', [])),
                'relations_out': len(result.get('relations_out', [])),
                'relations_in': len(result.get('relations_in', []))
            }

            total = sum(rel_counts.values())

            logger.info(f"  📊 Relations trouvées: {total}")
            for rel_type, count in rel_counts.items():
                if count > 0:
                    logger.info(f"     • {rel_type}: {count}")

    def _diagnose_cross_relations(self, selected_uids: List[str]):
        """
        ✅ CORRIGÉ : Vérifie les relations entre les UIDs sélectionnés
        """
        if len(selected_uids) < 2:
            return

        logger.info(f"\n  Vérification des connexions entre {len(selected_uids)} nœuds...")

        # Matrice de connexions
        connections = {}

        for uid1 in selected_uids[:3]:  # Limiter pour performance
            for uid2 in selected_uids[:3]:
                if uid1 == uid2:
                    continue
                
                # Vérifier si uid1 -> uid2
                query = f"""
                {{
                  # Relations directes
                  direct(func: uid({uid1})) {{
                    imports @filter(uid({uid2})) {{ uid }}
                    calls @filter(uid({uid2})) {{ uid }}
                    uses @filter(uid({uid2})) {{ uid }}
                  }}

                  # Relations type Relation
                  relations(func: type(Relation)) @filter(
                    uid_in(source, {uid1}) AND uid_in(target, {uid2})
                  ) {{
                    uid
                    relationType
                  }}
                }}
                """

                result = self._execute_dgraph_query(query)

                if result:
                    # ✅ CORRECTION : Vérification sécurisée avec valeur par défaut
                    direct_list = result.get('direct', [])
                    direct_node = direct_list[0] if direct_list else {}

                    relations = result.get('relations', [])

                    has_direct = any([
                        direct_node.get('imports'),
                        direct_node.get('calls'),
                        direct_node.get('uses')
                    ])

                    if has_direct or relations:
                        pair = f"{uid1[-8:]} -> {uid2[-8:]}"
                        connections[pair] = {
                            'direct': has_direct,
                            'relations': len(relations)
                        }

        if connections:
            logger.info(f"\n  ✅ Connexions trouvées:")
            for pair, info in connections.items():
                types = []
                if info['direct']:
                    types.append("directe")
                if info['relations'] > 0:
                    types.append(f"{info['relations']} Relation(s)")
                logger.info(f"     • {pair}: {', '.join(types)}")
        else:
            logger.warning(f"\n  ⚠️ AUCUNE connexion directe entre ces nœuds")
            logger.info(f"\n  💡 Suggestions:")
            logger.info(f"     • Ces éléments sont peut-être isolés")
            logger.info(f"     • Essayez de sélectionner des fichiers qui s'importent mutuellement")
            logger.info(f"     • Vérifiez que les relations ont bien été analysées")

    def _get_all_children(self, node_data, current_level):
        """
        ✅ NOUVEAU : Récupère TOUS les enfants selon le niveau actuel
        """
        children = []
        
        # Niveaux explicites
        if current_level == 0:  # Root
            children = node_data.get('level1', [])
        elif current_level == 1:
            children = node_data.get('level2', [])
        elif current_level == 2:
            children = node_data.get('level3', [])
        elif current_level == 3:
            children = node_data.get('level4', [])
        
        # Fallback sur 'children' générique
        if not children:
            children = node_data.get('children', [])
        
        return children
    
    def _detect_item_type_improved(self, item_data, item_name):
        """✅ Détection robuste du type d'élément avec priorité aux fichiers"""

        # 1. PRIORITÉ : Vérifier extension de fichier EN PREMIER
        if self._has_extension(item_name):
            return "file"

        # 2. Vérifier nodeType explicite
        node_type = item_data.get('nodeType', '').lower()
        if node_type:
            type_mapping = {
                'file': 'file',
                'folder': 'folder',
                'directory': 'folder',
                'function': 'function',
                'class': 'class',
                'method': 'function',
                'variable': 'variable',
                'module': 'folder',
                'label': 'folder'
            }
            if node_type in type_mapping:
                return type_mapping[node_type]

        # 3. Vérifier type explicite
        item_type = item_data.get('type', '').lower()
        if item_type in ['file', 'folder', 'directory', 'function', 'class', 'variable']:
            return item_type if item_type != 'directory' else 'folder'

        # 4. Vérifier category
        categories = item_data.get('category', [])
        if 'file' in categories:
            return "file"
        if 'folder' in categories or 'directory' in categories:
            return "folder"

        # 5. Vérifier présence de 'files' ou 'fileContents' (indique un fichier)
        if item_data.get('files') or item_data.get('fileContents'):
            return "file"

        # 6. Défaut selon présence d'enfants ou code
        has_children = (
            len(item_data.get('children', [])) > 0 or
            len(item_data.get('classes', [])) > 0 or
            len(item_data.get('functions', [])) > 0 or
            len(item_data.get('variables', [])) > 0
        )

        return "folder" if has_children else "file"
    
    def _add_code_elements_no_duplicates(self, parent_item, data_node, level):
        """
        ✅ CORRECTION : Ajout sans doublons aligné sur project_config_widget ligne 532-629
        """
        # Classes
        for cls in data_node.get('classes', []):
            cls_uid = cls.get('uid', '')
            cls_name = cls.get('name', 'UnnamedClass')

            if cls_uid and cls_uid in self._uid_set:
                continue
            
            if not cls_name or cls_name == 'N/A':
                cls_name = f"Class_{cls_uid[-6:]}" if cls_uid else "UnnamedClass"

            cls_item = TaxonomyItem(parent_item, cls_name, 'class', cls, level + 1)
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            # Méthodes
            for method in cls.get('methods', []):
                method_uid = method.get('uid', '')
                method_name = method.get('name', 'UnnamedMethod')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                if not method_name or method_name == 'N/A':
                    method_name = f"method_{method_uid[-6:]}" if method_uid else "UnnamedMethod"

                method_item = TaxonomyItem(cls_item, method_name, 'function', method, level + 2)
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

            # Variables de la classe
            for var in cls.get('variables', []):
                var_uid = var.get('uid', '')
                var_name = var.get('name', 'UnnamedVar')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                if not var_name or var_name == 'N/A':
                    var_name = f"var_{var_uid[-6:]}" if var_uid else "UnnamedVar"

                var_item = TaxonomyItem(cls_item, var_name, 'variable', var, level + 2)
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        # Fonctions
        for func in data_node.get('functions', []):
            func_uid = func.get('uid', '')
            func_name = func.get('name', 'UnnamedFunction')

            if func_uid and func_uid in self._uid_set:
                continue
            
            if not func_name or func_name == 'N/A':
                func_name = f"func_{func_uid[-6:]}" if func_uid else "UnnamedFunction"

            func_item = TaxonomyItem(parent_item, func_name, 'function', func, level + 1)
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

        # Variables
        for var in data_node.get('variables', []):
            var_uid = var.get('uid', '')
            var_name = var.get('name', 'UnnamedVariable')

            if var_uid and var_uid in self._uid_set:
                continue
            
            var_item = TaxonomyItem(parent_item, var_name, 'variable', var, level + 1)
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

    def _process_child_recursive(self, parent_item, child_data, level):
        """
        ✅ NOUVELLE MÉTHODE : Traite récursivement un enfant avec tous ses éléments
        """
        child_uid = child_data.get('uid', '')
        child_name = child_data.get('name') or child_data.get('label', 'Child')

        # Vérifier doublon
        if child_uid and child_uid in self._node_cache:
            logger.debug(f"{'  ' * level}⏭️ Child '{child_name}' déjà affiché")
            return

        # Détection type
        child_type = self._detect_item_type(child_data, child_name, parent_item)

        logger.debug(f"{'  ' * level}📄 Child: {child_name} (type={child_type}, level={level})")

        # Créer l'item
        child_item = TaxonomyItem(
            parent_item,
            child_name,
            child_type,
            child_data,
            level
        )
        child_item.loaded = True
        child_item.is_expandable = False

        # Enregistrer dans le cache
        if child_uid:
            self._node_cache[child_uid] = child_item
        self._name_cache[child_name] = child_item

        # ✅ AJOUTER LES ÉLÉMENTS DE CODE
        classes = child_data.get('classes', [])
        functions = child_data.get('functions', [])
        variables = child_data.get('variables', [])
        grandchildren = child_data.get('children', [])

        if classes or functions or variables or grandchildren:
            logger.debug(f"{'  ' * level}  - Classes: {len(classes)}, Functions: {len(functions)}, Variables: {len(variables)}, Children: {len(grandchildren)}")

        self._add_classes_to_tree(child_item, child_data)
        self._add_functions_to_tree(child_item, child_data)
        self._add_variables_to_tree(child_item, child_data)

        # ✅ TRAITER LES PETITS-ENFANTS RÉCURSIVEMENT
        for grandchild in grandchildren:
            self._process_child_recursive(child_item, grandchild, level + 1)
    
    def _build_complete_tree(self, parent_item, data_node):
            """
            ✅ CONSTRUIT L'ARBRE COMPLET de manière récursive SANS DOUBLONS
            Gère : Fichiers, Dossiers, Classes, Fonctions, Variables
            """
            # ✅ ROOT LABELS (si présents)
            root_labels = data_node.get('root_labels', [])

            # Si data_node EST un root_label (pas un cluster), traiter différemment
            if not root_labels and data_node.get('level') is not None:
                # C'est un label individuel, pas un cluster
                root_uid = data_node.get('uid', '')
                root_name = data_node.get('name') or data_node.get('label', 'Label')

                # Vérifier doublon
                if root_uid and root_uid in self._node_cache:
                    logger.debug(f"  ⏭️ Label '{root_name}' déjà affiché")
                    return

                # Créer l'item (déjà créé par l'appelant, donc on enrichit juste)
                # Ajouter les éléments de code
                self._add_classes_to_tree(parent_item, data_node)
                self._add_functions_to_tree(parent_item, data_node)
                self._add_variables_to_tree(parent_item, data_node)

                # Traiter les enfants hiérarchiques
                children = data_node.get('children', [])
                for child in children:
                    child_uid = child.get('uid', '')
                    child_name = child.get('name') or child.get('label', 'Child')

                    # Vérifier doublon
                    if child_uid and child_uid in self._node_cache:
                        logger.debug(f"  ⏭️ Child '{child_name}' déjà affiché")
                        continue
                    
                    # Détecter le type
                    child_type = self._detect_item_type(child, child_name, parent_item)

                    child_item = TaxonomyItem(
                        parent_item,
                        child_name,
                        child_type,
                        child,
                        parent_item.level + 1
                    )

                    # Enregistrer dans le cache
                    if child_uid:
                        self._node_cache[child_uid] = child_item
                    self._name_cache[child_name] = child_item

                    child_item.loaded = False
                    child_item.is_expandable = (
                        len(child.get('children', [])) > 0 or
                        len(child.get('classes', [])) > 0 or
                        len(child.get('functions', [])) > 0 or
                        len(child.get('variables', [])) > 0
                    )

                    if child_item.is_expandable:
                        self._add_loading_placeholder(child_item)

                return

            # ✅ TRAITER LES ROOT LABELS (cas cluster)
            for root_label in root_labels:
                root_uid = root_label.get('uid', '')
                root_name = root_label.get('name') or root_label.get('label', 'Label')

                # Vérifier doublon
                if root_uid and root_uid in self._node_cache:
                    logger.debug(f"  ⏭️ Root label '{root_name}' déjà affiché")
                    continue
                
                # Détecter le type
                is_file = self._has_extension(root_name)
                item_type = 'file' if is_file else 'folder'

                root_item = TaxonomyItem(
                    parent_item,
                    root_name,
                    item_type,
                    root_label,
                    parent_item.level + 1 if hasattr(parent_item, 'level') else 1
                )
                root_item.loaded = True
                root_item.is_expandable = False

                # Enregistrer dans le cache
                if root_uid:
                    self._node_cache[root_uid] = root_item
                self._name_cache[root_name] = root_item

                # ✅ AJOUTER CLASSES
                self._add_classes_to_tree(root_item, root_label)

                # ✅ AJOUTER FONCTIONS
                self._add_functions_to_tree(root_item, root_label)

                # ✅ AJOUTER VARIABLES
                self._add_variables_to_tree(root_item, root_label)

                # ✅ ENFANTS HIÉRARCHIQUES (récursif)
                children = root_label.get('children', [])
                for child in children:
                    # Appel récursif pour chaque enfant
                    self._build_complete_tree(root_item, {'root_labels': [child]})

    def _add_functions_to_tree(self, parent_item, data_node):
        """✅ VERSION SANS FALLBACK"""

        def has_valid_name(element):
            name = element.get('name')
            if not name:
                return False
            name = name.strip()
            return bool(name) and not name.startswith(('Unnamed', 'func-', 'method-'))

        functions = data_node.get('functions', [])

        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            if not has_valid_name(func):
                logger.debug(f"   ⏭️ Fonction ignorée (pas de nom)")
                continue
            
            func_name = func.get('name').strip()

            logger.debug(f"   ⚙️ Fonction: '{func_name}' (uid={func_uid})")

            func_item = TaxonomyItem(parent_item, func_name, 'function', func, parent_item.level + 1)
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

            # ✅ Variables de la fonction
            for var in func.get('variables', []):
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                if not has_valid_name(var):
                    continue
                
                var_name = var.get('name').strip()

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                var_item = TaxonomyItem(func_item, var_name, 'variable', var, func_item.level + 1)
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)


    def _add_variables_to_tree(self, parent_item, data_node):
        """✅ VERSION SANS FALLBACK"""

        def has_valid_name(element):
            name = element.get('name')
            if not name:
                return False
            name = name.strip()
            return bool(name) and not name.startswith(('Unnamed', 'var-'))

        variables = data_node.get('variables', [])

        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            if not has_valid_name(var):
                logger.debug(f"   ⏭️ Variable ignorée (pas de nom)")
                continue
            
            var_name = var.get('name').strip()

            logger.debug(f"   📦 Variable: '{var_name}' (uid={var_uid})")

            var_item = TaxonomyItem(parent_item, var_name, 'variable', var, parent_item.level + 1)
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

    def _load_clusters_from_dgraph(self):
        """
         VERSION OPTIMISÉE — Charge tous les clusters avec leur structure complète
        """
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("❌ Pas de connexion Dgraph.")
            return []

        query = """
        {
          q(func: type(Cluster)) {
            uid
            name
            id
            description
            nodeType
            createdAt
            files
            fileContents

            root_labels: ~clusters @filter(eq(level, 0)) {
              uid
              name
              label
              level
              nodeType
              path

              children: ~parents {
                uid
                name
                label
                nodeType
                level
                path

                children: ~parents {
                  uid
                  name
                  label
                  nodeType
                  level
                  path

                  children: ~parents {
                    uid
                    name
                    label
                    nodeType
                    level
                    path
                  }
                }
              }

              classes {
                uid
                name
                line
                methods {
                  uid
                  name
                  line
                }
              }

              functions {
                uid
                name
                line
              }

              variables {
                uid
                name
                line
              }
            }
          }
        }
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            result = self.dgraph_connector._parse_response(resp)
            clusters = result.get("q", []) if result else []

            logger.info(f"✅ {len(clusters)} clusters chargés avec structure complète.")
            return clusters

        except Exception as e:
            logger.error(f"❌ Erreur Dgraph: {e}")
            return []
        
    

    def _load_cluster_content(self, cluster_item):
        """
        ✅ VERSION CORRIGÉE : Charge TOUTE la hiérarchie du cluster
        Affiche TOUS les root_labels (fichiers ET dossiers)
        """
        cluster_data = cluster_item.item_data
        cluster_name = cluster_data.get('name', 'Unknown')

        logger.info(f"\n📂 CHARGEMENT CLUSTER: {cluster_name}")

        # ✅ RÉCUPÉRER root_labels
        root_labels = cluster_data.get('root_labels', [])

        # ✅ SI VIDE : Créer depuis fichiers du cluster
        if not root_labels:
            files = cluster_data.get('files', [])
            file_contents = cluster_data.get('file_contents') or cluster_data.get('fileContents', {})

            if files or file_contents:
                logger.info("   📄 Création root_labels depuis fichiers")
                root_labels = []

                for file_path in files:
                    file_name = os.path.basename(file_path)
                    content = file_contents.get(file_path, '') if isinstance(file_contents, dict) else ''

                    root_label = {
                        'name': file_name,
                        'label': file_name,
                        'uid': f"generated_{file_name}_{str(uuid.uuid4())[:8]}",
                        'type': 'file',
                        'nodeType': 'file',
                        'files': [file_path],
                        'file_contents': {file_path: content},
                        'classes': [],
                        'functions': [],
                        'variables': [],
                        'children': []
                    }
                    root_labels.append(root_label)

                cluster_data['root_labels'] = root_labels

        # ✅ AFFICHER TOUS LES ROOT_LABELS
        if not root_labels:
            empty_item = QtWidgets.QTreeWidgetItem(cluster_item)
            empty_item.setText(0, "(Cluster vide)")
            empty_item.setForeground(0, QtGui.QBrush(QtGui.QColor("#999999")))
            return

        logger.info(f"   📄 {len(root_labels)} root labels trouvés")

        # ✅ AFFICHER CHAQUE ROOT_LABEL (sans filtrer)
        for idx, root_label in enumerate(root_labels):
            root_name = root_label.get('name') or root_label.get('label', f"Item {idx + 1}")
            root_uid = root_label.get('uid', '')

            # ✅ VÉRIFIER DOUBLON
            if root_uid and root_uid in self._node_cache:
                logger.debug(f"  ⏭️ Root label '{root_name}' déjà affiché (uid={root_uid})")
                continue

            # ✅ DÉTECTION TYPE
            root_type = root_label.get('type') or root_label.get('nodeType', 'folder')

            is_file = (
                root_type == 'file' or 
                root_name.endswith(('.ts', '.py', '.js', '.java', '.cpp', '.json', '.net', '.c', '.h', '.tsx', '.jsx'))
            )

            item_type = 'file' if is_file else 'folder'

            # ✅ VÉRIFIER S'IL A DES ENFANTS OU DU CODE
            has_children = len(root_label.get('children', [])) > 0
            has_code_elements = (
                len(root_label.get('classes', [])) > 0 or 
                len(root_label.get('functions', [])) > 0 or 
                len(root_label.get('variables', [])) > 0
            )

            logger.info(f"   [{idx+1}] {root_name} (type={item_type}, children={has_children}, code={has_code_elements})")

            root_item = TaxonomyItem(
                cluster_item,
                root_name,
                item_type,
                root_label,
                1  # Niveau 1 (enfant direct du cluster)
            )

            # ✅ Enregistrer dans le cache
            if root_uid:
                self._node_cache[root_uid] = root_item
            self._name_cache[root_name] = root_item

            root_item.is_expandable = (
                item_type == 'folder' or 
                has_code_elements or 
                has_children
            )

            root_item.loaded = False

            if root_item.is_expandable:
                self._add_loading_placeholder(root_item)

        logger.info(f"✅ Cluster '{cluster_name}' chargé avec {len(root_labels)} root_labels")

    def _load_autonomous_labels_structure(self):
        """
        ✅ NOUVELLE MÉTHODE : Charge les labels autonomes SANS leur contenu détaillé
        """
        if not self.dgraph_connector:
            return
        
        # Requête SIMPLIFIÉE : seulement uid, name, level
        query = """
        {
          q(func: has(name)) @filter(type(Label) AND eq(level, 0)) {
            uid
            name
            label
            path
            nodeType
            level
          }
        }
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result:
            labels = result['q']
            logger.info(f"📥 Récupéré {len(labels)} labels niveau 0")
            
            python_files = []
            other_files = []
            
            for label in labels:
                label_name = label.get('name', label.get('label', 'N/A'))
                
                # Vérifier si déjà affiché dans un cluster
                if self._label_exists_in_tree_root(label_name):
                    continue
                
                if label_name.endswith('.py'):
                    python_files.append(label)
                else:
                    other_files.append(label)
            
            # Créer le groupe Python si nécessaire
            if python_files:
                python_group = TaxonomyItem(
                    self.tree_widget,
                    f"📁 Fichiers Python ({len(python_files)})",
                    "folder",
                    {},
                    0
                )
                python_group.loaded = False
                python_group.is_expandable = True
                self._add_loading_placeholder(python_group)
            
            # Ajouter les autres fichiers
            for label in other_files:
                label_name = label.get('name', label.get('label', 'N/A'))
                item_type = self._detect_item_type(label, label_name, None)
                
                label_item = TaxonomyItem(
                    self.tree_widget,
                    label_name,
                    item_type,
                    label,
                    0
                )
                label_item.loaded = False
                label_item.is_expandable = True
                self._add_loading_placeholder(label_item)

    def _label_exists_in_tree_root(self, label_name):
        """Vérifie si un label existe au niveau racine de l'arbre (comparaison normalisée)."""
        if not label_name:
            return False

        def normalize(n):
            # garder que le nom de fichier (basename), minuscules, sans espaces superflus
            try:
                n = str(n)
            except Exception:
                n = ""
            n = n.strip().lower()
            # si c'est un chemin, garder basename
            if '/' in n or '\\' in n:
                n = os.path.basename(n)
            return n

        target = normalize(label_name)

        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if not item:
                continue
            try:
                item_text = item.text(0)
            except Exception:
                item_text = ""
            if normalize(item_text) == target:
                return True

            if item.childCount() > 0:
                for j in range(item.childCount()):
                    child = item.child(j)
                    if normalize(child.text(0)) == target:
                        return True
        return False
    
    def _add_loading_placeholder(self, parent_item):
        """Ajoute un item placeholder '⏳ Chargement...'"""
        placeholder = QtWidgets.QTreeWidgetItem(parent_item)
        placeholder.setText(0, "⏳ Chargement...")
        placeholder.setForeground(0, QtGui.QBrush(QtGui.QColor("#999999")))
        placeholder.setFlags(Qt.ItemIsEnabled)

    def _add_file_structure_only(self, parent_item, labels):
        """
        ✅ Ajoute des labels/fichiers sans filtrer par extension
        """
        for label in labels:
            name = label.get('name') or label.get('label') or label.get('id') or 'unknown'
            item_type = 'file' if self._has_extension(name) else 'folder'

            item = TaxonomyItem(parent_item, name, item_type, label, parent_item.level + 1)
            item.is_expandable = bool(
                label.get('children') or
                label.get('uid') or
                label.get('classes') or
                label.get('functions')
            )
            item.loaded = False
            if item.is_expandable:
                self._add_loading_placeholder(item)

            logger.debug(f"  ➕ {name} (expandable={item.is_expandable})")

    def _remove_placeholder(self, parent_item):
        """Supprime le placeholder 'Chargement...' d'un item"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child and child.text(0) == "⏳ Chargement...":
                parent_item.removeChild(child)
                break

    def _on_item_expanded(self, item):
        """Gère l'expansion d'un item (lazy loading si nécessaire)."""
        if not isinstance(item, TaxonomyItem):
            return

        # Si déjà chargé, rien à faire
        if item.loaded:
            return

        # Marquer comme chargé pour éviter réentrance
        item.loaded = True

        # Retirer le placeholder s'il existe
        self._remove_placeholder(item)

        try:
            # Si c'est un cluster racine (level == 0) : charger tout le contenu du cluster
            if getattr(item, 'level', None) == 0 and item.item_data:
                logger.info(f"Expansion cluster: {item.text(0)} -> chargement complet")
                self._load_cluster_content(item)
                return

            # Si c'est un dossier (folder) : charger ses enfants (récursif)
            typ = getattr(item, 'item_type', None) or getattr(item, 'type', None) or item.data if hasattr(item, 'data') else None
            # On se base plutôt sur l'item_type stocké dans TaxonomyItem (si impl.).
            item_type = getattr(item, 'item_type', None)
            if item_type is None:
                # fallback : détecter via nom
                item_type = 'file' if self._has_extension(item.text(0)) else 'folder'

            if item_type == 'folder':
                logger.info(f"Expansion dossier: {item.text(0)} -> _load_folder_children")
                self._load_folder_children(item)
                return

            # Si c'est un fichier : charger son contenu (classes/fonctions/variables)
            if item_type == 'file':
                logger.info(f"Expansion fichier: {item.text(0)} -> _load_file_content")
                self._load_file_content(item)
                return

            # Par défaut, tenter un chargement détaillé si l'item possède un uid
            uid = item.item_data.get('uid') if getattr(item, 'item_data', None) else None
            if uid:
                logger.info(f"Expansion par UID: {item.text(0)} uid={uid}")
                self._load_item_detailed_content(item, uid)
        except Exception as e:
            logger.warning(f"Erreur lors de l'expansion de {item.text(0)}: {e}")


    def _load_file_content(self, file_item):
        """
        ✅ VERSION SANS FALLBACK : Chargement strict des noms réels
        """
        file_data = file_item.item_data
        file_name = file_data.get('name') or file_data.get('label', 'Unknown')
        file_uid = file_data.get('uid')

        logger.info(f"📄 Chargement fichier: {file_name} (uid={file_uid})")

        # ✅ Si l'UID existe, recharger depuis Dgraph
        if file_uid and self.dgraph_connector:
            detailed_data = self._fetch_file_complete_data(file_uid)
            if detailed_data:
                file_data = detailed_data
                file_item.item_data = detailed_data

        def has_valid_name(element):
            """Validation stricte du nom"""
            name = element.get('name')
            if not name:
                return False
            name = name.strip()
            if not name or name.startswith(('Unnamed', 'class-', 'func-', 'var-', 'method-')):
                return False
            return True

        # ✅ Récupérer éléments de code
        classes = file_data.get('classes', [])
        functions = file_data.get('functions', [])
        variables = file_data.get('variables', [])

        # Compter uniquement les éléments avec noms valides
        valid_count = sum([
            1 for cls in classes if has_valid_name(cls)
        ]) + sum([
            1 for func in functions if has_valid_name(func)
        ]) + sum([
            1 for var in variables if has_valid_name(var)
        ])

        logger.info(f"   📊 {valid_count} éléments valides trouvés")

        # ✅ CLASSES avec méthodes
        for cls in classes:
            cls_uid = cls.get('uid', '')

            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ STRICT : Ignorer si pas de nom valide
            if not has_valid_name(cls):
                logger.debug(f"   ⏭️ Classe sans nom ignorée")
                continue
            
            cls_name = cls.get('name').strip()

            cls_item = TaxonomyItem(
                file_item,
                cls_name,
                'class',
                cls,
                file_item.level + 1
            )
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            # Méthodes
            for method in cls.get('methods', []):
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                if not has_valid_name(method):
                    continue
                
                method_name = method.get('name').strip()

                method_item = TaxonomyItem(
                    cls_item,
                    method_name,
                    'function',
                    method,
                    cls_item.level + 1
                )
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

        # ✅ FONCTIONS
        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            if not has_valid_name(func):
                logger.debug(f"   ⏭️ Fonction sans nom ignorée")
                continue
            
            func_name = func.get('name').strip()

            func_item = TaxonomyItem(
                file_item,
                func_name,
                'function',
                func,
                file_item.level + 1
            )
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

        # ✅ VARIABLES
        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            if not has_valid_name(var):
                logger.debug(f"   ⏭️ Variable sans nom ignorée")
                continue
            
            var_name = var.get('name').strip()

            var_item = TaxonomyItem(
                file_item,
                var_name,
                'variable',
                var,
                file_item.level + 1
            )
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

        logger.info(f"   ✅ {file_item.childCount()} éléments ajoutés")

    def _fetch_file_complete_data(self, file_uid: str) -> Optional[Dict]:
        """
        ✅ NOUVEAU : Recharge les données complètes d'un fichier depuis Dgraph
        """
        query = f"""
        {{
          file(func: uid({file_uid})) {{
            uid
            name
            label
            nodeType
            path
            files
            fileContents
            description

            classes {{
              uid
              name
              description
              line
              bases

              methods {{
                uid
                name
                description
                line
                params
                returns
              }}

              variables {{
                uid
                name
                description
                line
                var_type
                scope
              }}
            }}

            functions {{
              uid
              name
              description
              line
              params
              returns

              variables {{
                uid
                name
                description
                line
                var_type
                scope
              }}
            }}

            variables {{
              uid
              name
              description
              line
              var_type
              scope
            }}

            children: ~parents {{
              uid
              name
              label
              nodeType
              level
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'file' in result and result['file']:
            return result['file'][0]

        return None

    def _load_folder_children(self, folder_item):
        """
        ✅ CORRIGÉ : Charge TOUS les enfants avec la bonne clé de niveau
        """
        folder_data = folder_item.item_data or {}
        folder_name = folder_data.get('name') or folder_data.get('label', 'Unknown')
        folder_level = folder_item.level

        logger.info(f"\n📁 CHARGEMENT DOSSIER: {folder_name} (niveau {folder_level})")

        # ✅ Récupérer enfants selon le niveau actuel
        next_level = folder_level + 1
        level_key = f'level{next_level}'

        children = folder_data.get(level_key, [])

        # Fallback
        if not children:
            children = folder_data.get('children', [])

        logger.info(f"   🔍 Clé utilisée: '{level_key}' → {len(children)} enfants")

        # Si toujours vide ET a un uid → recharger
        if not children and folder_data.get('uid'):
            try:
                uid = folder_data['uid']
                logger.info(f"   🔄 Rechargement depuis Dgraph (uid={uid})")
                detailed_data = self._load_item_detailed_content_sync(folder_item, uid)

                if detailed_data:
                    folder_data = detailed_data
                    folder_item.item_data = detailed_data
                    children = detailed_data.get(level_key, []) or detailed_data.get('children', [])
                    logger.info(f"   ✅ {len(children)} enfants après rechargement")
            except Exception as e:
                logger.warning(f"   ⚠️ Erreur rechargement: {e}")

        if not children:
            empty = QtWidgets.QTreeWidgetItem(folder_item)
            empty.setText(0, "(Dossier vide)")
            empty.setForeground(0, QtGui.QBrush(QtGui.QColor("#999999")))
            return

        # ✅ Trier : dossiers, puis fichiers, puis code
        folders, files, codes = [], [], []

        for ch in children:
            ch_uid = ch.get('uid', '')

            # Éviter doublons
            if ch_uid and ch_uid in self._uid_set:
                logger.debug(f"   ⏭️ Enfant {ch.get('name')} déjà affiché")
                continue
            
            ctype = ch.get('nodeType') or ch.get('type') or 'folder'
            cname = ch.get('name') or ch.get('label') or ch.get('id') or 'N/A'

            if ctype in ['class', 'function', 'variable', 'method']:
                codes.append(ch)
            elif ctype == 'file' or self._has_extension(cname):
                files.append(ch)
            else:
                folders.append(ch)

        logger.info(f"   📊 Répartition: {len(folders)} dossiers, {len(files)} fichiers, {len(codes)} codes")

        # ✅ Ajouter dossiers
        for ch in folders:
            name = ch.get('name') or ch.get('label') or 'Folder'
            ch_uid = ch.get('uid', '')

            it = TaxonomyItem(folder_item, name, 'folder', ch, next_level)
            it.is_expandable = True
            it.loaded = False

            if ch_uid:
                self._node_cache[ch_uid] = it
                self._uid_set.add(ch_uid)

            self._add_loading_placeholder(it)

        # ✅ Ajouter fichiers
        for ch in files:
            name = ch.get('name') or ch.get('label') or 'File'
            ch_uid = ch.get('uid', '')

            it = TaxonomyItem(folder_item, name, 'file', ch, next_level)
            it.is_expandable = True
            it.loaded = False

            if ch_uid:
                self._node_cache[ch_uid] = it
                self._uid_set.add(ch_uid)

            self._add_loading_placeholder(it)

        # ✅ Ajouter codes
        for ch in codes:
            name = ch.get('name') or 'Code'
            ch_uid = ch.get('uid', '')

            code_item = TaxonomyItem(
                folder_item, 
                name, 
                ch.get('nodeType', 'function'), 
                ch, 
                next_level
            )
            code_item.loaded = True
            code_item.is_expandable = False

            if ch_uid:
                self._node_cache[ch_uid] = code_item
                self._uid_set.add(ch_uid)

        logger.info(f"   ✅ {folder_item.childCount()} éléments affichés")

    def _load_item_detailed_content_sync(self, item, uid):
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            id
            label
            path
            category
            nodeType
            level
            files
            fileContents
    
            classes {{
              uid
              name
              description
              line
              methods {{ uid name description line }}
              variables {{ uid name description line }}
            }}
    
            functions {{
              uid
              name
              description
              line
              variables {{ uid name description line }}
            }}
    
            variables {{
              uid
              name
              description
              line
            }}
    
            level1: ~parents @filter(eq(level, 1)) {{
              uid
              name
              nodeType
              level
            }}
            
            level2: ~parents @filter(eq(level, 2)) {{
              uid
              name
              nodeType
              level
            }}
            
            level3: ~parents @filter(eq(level, 3)) {{
              uid
              name
              nodeType
              level
            }}
          }}
        }}
        """
    
        result = self._execute_dgraph_query(query)
    
        if result and 'node' in result and result['node']:
            return result['node'][0]
    
        return None

    def _load_item_detailed_content(self, item, uid):
        """
        ✅ VERSION SANS FALLBACK : Charge uniquement les éléments avec noms valides
        """
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            id
            label
            path
            category
            nodeType
            codeContent
            description
            level
            files
            fileContents

            classes {{
              uid
              name 
              description
              line
              bases
              uses_vars

              methods {{
                uid
                name   
                description
                line
                params
                returns
              }}

              variables {{
                uid
                name
                description
                line
                var_type
                scope
              }}
            }}

            functions {{
              uid
              name       
              description
              line
              params
              returns

              variables {{
                uid
                name 
                description
                line
                var_type
                scope
              }}
            }}

            variables {{
              uid
              name     
              description
              line
              var_type
              scope
            }}

            children: ~parents {{
              uid
              name 
              id
              label
              nodeType
              level
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            node_data = result['node'][0]
            item.item_data.update(node_data)

            def has_valid_name(element):
                """Validation stricte"""
                name = element.get('name')
                if not name:
                    return False
                name = name.strip()
                if not name or name.startswith(('Unnamed', 'class-', 'func-', 'var-', 'method-')):
                    return False
                return True

            # ✅ CLASSES
            classes = [cls for cls in node_data.get('classes', []) if has_valid_name(cls)]
            if classes:
                logger.info(f"   🗂️ {len(classes)} classes valides")
                for cls in classes:
                    cls_name = cls.get('name').strip()

                    cls_item = TaxonomyItem(
                        item,
                        cls_name,
                        'class',
                        cls,
                        item.level + 1
                    )
                    cls_item.loaded = True
                    cls_item.is_expandable = False

                    if cls.get('uid'):
                        self._node_cache[cls['uid']] = cls_item
                        self._uid_set.add(cls['uid'])

                    # ✅ MÉTHODES
                    methods = [m for m in cls.get('methods', []) if has_valid_name(m)]
                    for method in methods:
                        method_name = method.get('name').strip()

                        method_item = TaxonomyItem(
                            cls_item,
                            method_name,
                            'function',
                            method,
                            cls_item.level + 1
                        )
                        method_item.loaded = True

                        if method.get('uid'):
                            self._node_cache[method['uid']] = method_item
                            self._uid_set.add(method['uid'])

            # ✅ FONCTIONS
            functions = [f for f in node_data.get('functions', []) if has_valid_name(f)]
            if functions:
                logger.info(f"   ⚙️ {len(functions)} fonctions valides")
                for func in functions:
                    func_name = func.get('name').strip()

                    func_item = TaxonomyItem(
                        item,
                        func_name,
                        'function',
                        func,
                        item.level + 1
                    )
                    func_item.loaded = True

                    if func.get('uid'):
                        self._node_cache[func['uid']] = func_item
                        self._uid_set.add(func['uid'])

            # ✅ VARIABLES
            variables = [v for v in node_data.get('variables', []) if has_valid_name(v)]
            for var in variables:
                var_name = var.get('name').strip()

                var_item = TaxonomyItem(
                    item,
                    var_name,
                    'variable',
                    var,
                    item.level + 1
                )
                var_item.loaded = True

                if var.get('uid'):
                    self._node_cache[var['uid']] = var_item
                    self._uid_set.add(var['uid'])

            # ✅ ENFANTS HIÉRARCHIQUES
            children = node_data.get('children', [])
            if children:
                logger.info(f"   📁 {len(children)} enfants hiérarchiques")
                for child in children:
                    child_name = child.get('name') or child.get('label') or child.get('id', 'Item')

                    if not child_name or child_name.startswith('Unnamed'):
                        continue

                    child_type = self._detect_item_type(child, child_name, item)

                    child_item = TaxonomyItem(
                        item,
                        child_name,
                        child_type,
                        child,
                        item.level + 1
                    )
                    child_item.loaded = False
                    child_item.is_expandable = True
                    self._add_loading_placeholder(child_item)

    def _debug_item_structure(self, item):
        """
        ✅ NOUVELLE MÉTHODE : Debug de la structure d'un item
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 DEBUG ITEM: {item.text(0)}")
        logger.info(f"{'='*60}")

        data = item.item_data

        logger.info(f"Type: {item.item_type}")
        logger.info(f"Level: {item.level}")
        logger.info(f"UID: {data.get('uid', 'MISSING')}")
        logger.info(f"Name: {data.get('name', 'MISSING')}")
        logger.info(f"Label: {data.get('label', 'N/A')}")
        logger.info(f"NodeType: {data.get('nodeType', 'N/A')}")

        logger.info(f"\n📊 Contenu:")
        logger.info(f"  Classes: {len(data.get('classes', []))}")
        logger.info(f"  Functions: {len(data.get('functions', []))}")
        logger.info(f"  Variables: {len(data.get('variables', []))}")
        logger.info(f"  Children: {len(data.get('children', []))}")

        # Afficher les premiers éléments
        for cls in data.get('classes', [])[:3]:
            logger.info(f"    🏗️ Class: {cls.get('name', 'NO NAME')} (uid={cls.get('uid', 'NO UID')})")

        for func in data.get('functions', [])[:3]:
            logger.info(f"    ⚙️ Function: {func.get('name', 'NO NAME')} (uid={func.get('uid', 'NO UID')})")

        logger.info(f"{'='*60}\n")

    def _load_item_local_content(self, item):
        """
        ✅ Charge depuis les données locales (si déjà en mémoire)
        """
        item_data = item.item_data

        # Classes
        classes = item_data.get('classes', [])
        if classes:
            for cls in classes:
                cls_name = cls.get('name', 'class')
                cls_item = TaxonomyItem(
                    item,
                    cls_name,
                    'class',
                    cls,
                    item.level + 1
                )
                cls_item.loaded = True

                # Méthodes
                methods = cls.get('methods', [])
                if methods:
                    for method in methods:
                        method_name = method.get('name', 'method')
                        method_item = TaxonomyItem(
                            cls_item,
                            method_name,
                            'function',
                            method,
                            cls_item.level + 1
                        )
                        method_item.loaded = True

        # Fonctions
        functions = item_data.get('functions', [])
        if functions:
            for func in functions:
                func_name = func.get('name', 'function')
                func_item = TaxonomyItem(
                    item,
                    func_name,
                    'function',
                    func,
                    item.level + 1
                )
                func_item.loaded = True

        # Variables
        variables = item_data.get('variables', [])
        if variables:
            for var in variables:
                var_name = var.get('name', 'variable')
                var_item = TaxonomyItem(
                    item,
                    var_name,
                    'variable',
                    var,
                    item.level + 1
                )
                var_item.loaded = True

        # Enfants
        children = item_data.get('children', [])
        if children:
            for child in children:
                child_name = child.get('name', child.get('label', 'Item'))
                child_type = self._detect_item_type(child, child_name, item)

                child_item = TaxonomyItem(
                    item,
                    child_name,
                    child_type,
                    child,
                    item.level + 1
                )
                child_item.loaded = False
                child_item.is_expandable = True
                self._add_loading_placeholder(child_item)

    def _label_exists_in_tree(self, parent_item, label_name):
        """Vérifie si un label existe déjà dans l'arbre"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if isinstance(child, TaxonomyItem) and child.text(0) == label_name:
                return True
        return False

    def _fetch_cluster_name_from_dgraph(self, cluster_uid):
        """Récupère le name d'un cluster depuis Dgraph"""
        if not cluster_uid or not self.dgraph_connector:
            return None

        query = f"""
        {{
          q(func: uid({cluster_uid})) {{
            name
            id
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'q' in result and result['q']:
            node = result['q'][0]
            return node.get('name') or node.get('id')

        return None

    def _fetch_root_labels_from_dgraph(self, cluster_uid):
        """Récupère les root_labels d'un cluster depuis Dgraph"""
        if not cluster_uid or not self.dgraph_connector:
            return []

        query = f"""
        {{
          q(func: uid({cluster_uid})) {{
            uid
            name

            root_labels: ~clusters {{
              uid
              name
              id
              label
              path
              category
              nodeType
              codeContent
              description
              level
              files
              fileContents

              functions {{
                uid
                name
                description
                line
              }}

              classes {{
                uid
                name
                description
                line

                methods {{
                  uid
                  name
                  description
                }}
              }}

              variables {{
                uid
                name
                description
                line
              }}

              children: ~parents {{
                uid
                name
                nodeType
                level
              }}
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'q' in result and result['q']:
            node = result['q'][0]
            root_labels = node.get('root_labels', [])
            return root_labels

        return []

    def _fetch_node_details_from_dgraph(self, node_uid):
        """
        🆕 NOUVELLE MÉTHODE : Récupère les détails d'un nœud par son UID
        """
        if not node_uid or not self.dgraph_connector:
            return None

        query = f"""
        {{
          q(func: uid({node_uid})) {{
            uid
            name
            description
            line
            params
            returns
            var_type
            scope
            bases
            uses_vars
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'q' in result and result['q']:
            return result['q'][0]

        return None

    def _fetch_children_from_dgraph(self, parent_uid):
        """
        ✅ CORRIGÉ : Récupère les enfants d'un nœud depuis Dgraph
        (fonctions, classes, variables, sous-fichiers, etc.)
        """
        if not parent_uid or not self.dgraph_connector:
            return []
        
        query = f"""
        {{
          q(func: uid({parent_uid})) {{
            uid
            name
            
            # Récupérer tous les enfants directs via la relation ~parents
            children: ~parents {{
              uid
              name
              label
              nodeType
              level
              category
              path
              codeContent
              description
              
              # Fonctions de ces enfants
              functions {{
                uid
                name
                description
                
                # ✅ NOUVEAU : Variables et classes sous les fonctions
                variables {{
                  uid
                  name
                  description
                  var_type
                  scope
                }}
                classes {{
                  uid
                  name
                  description
                  
                  # Méthodes des classes
                  methods {{
                    uid
                    name
                    description
                    params
                    returns
                  }}
                  
                  # Variables des classes
                  variables {{
                    uid
                    name
                    description
                    var_type
                    scope
                  }}
                }}
              }}
              
              # ✅ NOUVEAU : Classes du label/enfant
              classes {{
                uid
                name
                description
                
                methods {{
                  uid
                  name
                  description
                  params
                  returns
                }}
                
                variables {{
                  uid
                  name
                  description
                  var_type
                  scope
                }}
              }}
              
              # ✅ NOUVEAU : Variables du label/enfant
              variables {{
                uid
                name
                description
                var_type
                scope
              }}
            }}
            
            # Récupérer les fonctions directement rattachées
            functions {{
              uid
              name
              description
              
              # ✅ NOUVEAU : Variables et classes sous les fonctions directes
              variables {{
                uid
                name
                description
                var_type
                scope
              }}
              classes {{
                uid
                name
                description
                methods {{
                  uid
                  name
                  description
                }}
                variables {{
                  uid
                  name
                  description
                }}
              }}
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result and result['q']:
            node = result['q'][0]
            children_list = []
            
            # Ajouter les children
            for child in node.get('children', []):
                children_list.append(child)
            
            # Ajouter les fonctions comme children aussi
            for func in node.get('functions', []):
                func['nodeType'] = 'function'  # Marquer explicitement comme fonction
                children_list.append(func)
            
            # ✅ NOUVEAU : Ajouter classes et variables comme children
            for cls in node.get('classes', []):
                cls['nodeType'] = 'class'
                children_list.append(cls)
            
            for var in node.get('variables', []):
                var['nodeType'] = 'variable'
                children_list.append(var)
                
            return children_list
        
        return []

    def _load_uid_mappings(self):
        """Charge les mappings UID depuis Dgraph."""
        query = """
        {
          q(func: has(local_id)) {
            uid
            local_id
          }
        }
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result:
            for node in result['q']:
                dgraph_uid = node.get('uid')
                local_id = node.get('local_id')
                
                if dgraph_uid and local_id:
                    self.dgraph_to_local[dgraph_uid] = local_id
                    self.local_to_dgraph[local_id] = dgraph_uid
        logger.info(f"Mappings UID chargés: {len(self.dgraph_to_local)} entrées")

    def _detect_item_type(self, item_data, item_name, parent_item):
        """
        ✅ VERSION FINALE : Détection robuste
        """
        # 1. Vérifier nodeType explicite
        explicit_type = item_data.get('nodeType', '')
        if explicit_type:
            type_mapping = {
                'file': 'file',
                'folder': 'folder',
                'function': 'function',
                'class': 'class',
                'method': 'function',
                'variable': 'variable',
                'module': 'folder',
                'label': 'folder'
            }
            mapped_type = type_mapping.get(explicit_type.lower())
            if mapped_type:
                return mapped_type

        # 2. Vérifier type explicite
        item_type = item_data.get('type', '')
        if item_type:
            if item_type == 'file':
                return 'file'
            elif item_type in ['folder', 'directory']:
                return 'folder'

        # 3. Vérifier extension
        if self._has_extension(item_name):
            return "file"

        # 4. Vérifier category
        categories = item_data.get('category', [])
        if categories:
            if 'file' in categories:
                return "file"
            if 'folder' in categories or 'directory' in categories:
                return "folder"

        # 5. Défaut : folder
        return "folder"

    def _validate_item_data(self, item_data, item_type):
        """
        ✅ NOUVELLE MÉTHODE : Valide et corrige les données d'un item
        """
        # Vérifier que 'name' existe
        if 'name' not in item_data or not item_data['name']:
            item_data['name'] = item_data.get('label') or item_data.get('id', 'Unknown')
            logger.warning(f"⚠️ 'name' manquant, utilisation fallback: {item_data['name']}")

        if 'uid' not in item_data or not item_data['uid']:
            import uuid
            item_data['uid'] = str(uuid.uuid4())
            logger.warning(f"⚠️ 'uid' manquant, génération: {item_data['uid']}")

        if 'nodeType' not in item_data:
            item_data['nodeType'] = item_type

        return item_data

    def _execute_dgraph_query(self, query: str) -> Optional[Dict]:
        """Exécute une requête Dgraph"""
        if not self.dgraph_connector or not self.dgraph_connector.client:
            logger.error("Dgraph connector non disponible")
            return None
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            try:
                resp = txn.query(query)
                return self.dgraph_connector._parse_response(resp)
            finally:    
                txn.discard()
        except Exception as e:
            logger.error(f"Erreur requête Dgraph: {e}")
            return None

    def _get_node_details(self, uid: str) -> Dict:
        """Récupère les détails complets d'un nœud."""
        if not uid:
            return {}

        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            level
            nodeType

            parents {{
              uid
              name
            }}

            children: ~parents {{
              uid
              name
            }}
          }}

          outgoing_relations(func: type(Relation)) @filter(uid_in(source, {uid})) {{
            uid
            relationType
            target {{
              uid
              name
            }}
          }}

          incoming_relations(func: type(Relation)) @filter(uid_in(target, {uid})) {{
            uid
            relationType
            source {{
              uid
              name
            }}
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        if result and 'node' in result and result['node']:
            node = result['node'][0]
            node['outgoing_relations'] = result.get('outgoing_relations', [])
            node['incoming_relations'] = result.get('incoming_relations', [])
            return node

        return {}

    # taxonomy_dialog.py - Méthode corrigée
    def _get_level_1_relations(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION FINALE : Force le rechargement
        """
        if not uid:
            logger.warning("⚠️ UID manquant")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"📊 NIVEAU 1 via graph_widget : {uid}")
        logger.info(f"{'='*70}")

        # ✅ VALIDATION
        if not self._validate_uid_exists(uid):
            logger.error(f"❌ UID {uid} introuvable dans Dgraph")
            return []

        # ✅ FORCER LE RECHARGEMENT (pas de cache)
        relations_list = self.graph_helper._get_complete_relations(
            uid, 
            level=1,
            use_cache=False  # ← NOUVEAU
        )

        # Statistiques
        self._log_relation_stats(relations_list, "NIVEAU 1")

        return relations_list


    def _get_node_name_by_uid(self, uid: str) -> str:
        """Récupère le nom d'un nœud à partir du cache (TaxonomyItem/dict)."""
        item = self._node_cache.get(uid)
        if item:
            # Essayer d'accéder au nom via l'attribut (TaxonomyItem) ou clé (dict)
            return getattr(item, 'name', None) or item.get('name', None) or item.get('label', None) or f"Node_{uid}"
        return f"Node_{uid}"
    
    def _get_node_type_by_uid(self, uid: str) -> str:
        """Récupère le type d'un nœud à partir du cache (TaxonomyItem/dict)."""
        item = self._node_cache.get(uid)
        if item:
            return getattr(item, 'item_type', None) or getattr(item, 'item_data', {}).get('nodeType', None) or "unknown"
        return "unknown"

    def _get_level_2_relations(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION FINALE : Force le rechargement
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🕸️ NIVEAU 2 via graph_widget : {uid}")
        logger.info(f"{'='*70}")

        if not self._validate_uid_exists(uid):
            logger.error(f"❌ UID {uid} introuvable")
            return []

        # ✅ FORCER LE RECHARGEMENT
        relations_list = self.graph_helper._get_complete_relations(
            uid, 
            level=2,
            use_cache=False  # ← NOUVEAU
        )

        self._log_relation_stats(relations_list, "NIVEAU 2")

        return relations_list
    
    def _get_multi_selection_relations(self, selected_uids: List[str]) -> List[Dict]:
        """
        ✅ VERSION FINALE : Utilise graph_widget pour multi-sélection
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 SÉLECTION MULTIPLE via graph_widget : {len(selected_uids)} éléments")
        logger.info(f"{'='*70}")

        # ✅ VALIDATION des UIDs
        valid_uids = [uid for uid in selected_uids if self._validate_uid_exists(uid)]

        if not valid_uids:
            logger.error("❌ Aucun UID valide dans la sélection")
            return []

        logger.info(f"✅ {len(valid_uids)}/{len(selected_uids)} UIDs valides")

        all_relations = []
        selected_uid_set = set(valid_uids)

        # ✅ Pour chaque UID, récupérer ses relations complètes
        for uid in valid_uids:
            node_relations = self.graph_helper._get_complete_relations(uid, level=1)
            all_relations.extend(node_relations)

        logger.info(f"📊 {len(all_relations)} relations totales récupérées")

        # ✅ FILTRER : Garder UNIQUEMENT les relations entre éléments sélectionnés
        filtered_relations = []

        for rel in all_relations:
            source_uid = rel.get('source_uid')
            target_uid = rel.get('target_uid')

            # Les DEUX doivent être dans la sélection
            if source_uid in selected_uid_set and target_uid in selected_uid_set:
                filtered_relations.append(rel)

        # ✅ DÉDOUBLONNER
        unique_relations = self._deduplicate_relations(filtered_relations)

        # ✅ STATISTIQUES
        self._log_relation_stats(unique_relations, "MULTI-SÉLECTION")

        if not unique_relations:
            logger.warning("⚠️ AUCUNE relation réelle entre ces éléments")
            # ✅ Lancer diagnostic approfondi
            self._diagnose_missing_relations_detailed(valid_uids)

        return unique_relations
    
    def _validate_uid_exists(self, uid: str) -> bool:
        """
        ✅ NOUVEAU : Vérifie qu'un UID existe dans Dgraph
        """
        if not uid or not self.dgraph_connector:
            return False

        query = f"""
        {{
          check(func: uid({uid})) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)

        exists = result and 'check' in result and result['check']

        if not exists:
            logger.warning(f"⚠️ UID {uid} n'existe pas dans Dgraph")

        return exists
    
    def _log_relation_stats(self, relations: List[Dict], context: str):
        """
        ✅ NOUVEAU : Log unifié des statistiques de relations
        """
        rel_types = {}
        categories = {}

        for rel in relations:
            rel_type = rel.get('relation_type', 'unknown')
            category = rel.get('category', 'unknown')

            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
            categories[category] = categories.get(category, 0) + 1

        logger.info(f"\n📊 STATISTIQUES {context} :")
        logger.info(f"  Total relations : {len(relations)}")

        if rel_types:
            logger.info(f"\n📈 PAR TYPE :")
            for rel_type, count in sorted(rel_types.items(), key=lambda x: -x[1])[:10]:
                logger.info(f"  • {rel_type} : {count}")

        if categories:
            logger.info(f"\n📂 PAR CATÉGORIE :")
            for category, count in sorted(categories.items(), key=lambda x: -x[1]):
                logger.info(f"  • {category} : {count}")

        logger.info(f"{'='*70}\n")

    def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """
        ✅ NOUVEAU : Dédoublonnage unifié
        """
        unique_relations = []
        seen_keys = set()

        for rel in relations:
            key = (
                rel.get('source_uid', ''),
                rel.get('target_uid', ''),
                rel.get('relation_type', '')
            )

            if key not in seen_keys and key[0] and key[1]:
                seen_keys.add(key)
                unique_relations.append(rel)

        logger.info(f"🔄 Déduplication : {len(relations)} → {len(unique_relations)} relations")

        return unique_relations

    def _get_node_uid_by_name(self, node_name: str) -> str:
        """Récupère l'UID d'un nœud par son nom."""
        if not node_name:
            return None

        query = f"""
        {{
          q(func: has(name)) @filter(eq(name, "{node_name}")) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            return result['q'][0].get('uid')

        return None

    def normalize_node_name(self, name: str) -> str:
        """Normalise le nom d'un nœud."""
        if not name or not isinstance(name, str):
            return f"unnamed_{id(name)}"

        name = name.strip()
        if not name or name.lower() == 'n/a':
            return f"unnamed_{id(name)}"

        base = os.path.basename(name)
        name_without_ext = os.path.splitext(base)[0]
        normalized = name_without_ext.strip()
        
        if not normalized:
            return f"unnamed_{id(name)}"
        
        return normalized

    def _init_ui(self):
        """Initialise l'interface du dialogue"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("background-color: white;")

        header = QtWidgets.QLabel("Sélectionnez les fichiers/fonctions à implémenter")
        header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #A23B2D;
            padding: 10px;
            background-color: white;
        """)
        layout.addWidget(header)

        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel("Niveau de profondeur:")
        level_label.setStyleSheet("font-weight: 600; font-size: 12px;")

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItem("Niveau 1: Relations directes uniquement", 1)
        self.level_combo.addItem("Niveau 2: Relations + enfants (récursif)", 2)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        self.level_combo.setStyleSheet("background-color: white;")

        level_layout.addWidget(level_label)
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        main_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("background-color: white;")

        tree_container = QtWidgets.QWidget()
        tree_container.setStyleSheet("background-color: white;")
        tree_layout = QtWidgets.QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        tree_label = QtWidgets.QLabel("Structure du projet:")
        tree_label.setStyleSheet("font-weight: bold; font-size: 13px; background-color: white;")
        tree_layout.addWidget(tree_label)

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.tree_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 8px;
                background-color: white;
            }
            QTreeWidget::item:selected {
                background-color: #E0E0E0;
                color: #333333;
            }
            QTreeWidget::item:hover {
                background-color: #F5F5F5;
            }
        """)
        tree_layout.addWidget(self.tree_widget)
        main_splitter.addWidget(tree_container)

        desc_container = QtWidgets.QWidget()
        desc_container.setStyleSheet("background-color: white;")
        desc_layout = QtWidgets.QVBoxLayout(desc_container)
        desc_layout.setContentsMargins(0, 0, 0, 0)

        desc_label = QtWidgets.QLabel("Description:")
        desc_label.setStyleSheet("font-weight: bold; font-size: 13px; background-color: white;")
        desc_layout.addWidget(desc_label)

        self.description_text = QtWidgets.QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText(
            "Sélectionnez un élément dans l'arbre"
        )
        self.description_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: white;
                padding: 10px;
                color: #333333;
            }
        """)
        desc_layout.addWidget(self.description_text)

        selected_label = QtWidgets.QLabel("Éléments sélectionnés:")
        selected_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; margin-top: 10px; background-color: white;"
        )
        desc_layout.addWidget(selected_label)

        self.selected_list = QtWidgets.QListWidget()
        self.selected_list.setMaximumHeight(120)
        self.selected_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #E8E0DF;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
                background-color: white;
                color: #333333;
            }
            QListWidget::item:selected {
                background-color: #E0E0E0;
                color: #333333;
            }
        """)
        desc_layout.addWidget(self.selected_list)

        main_splitter.addWidget(desc_container)
        main_splitter.setSizes([300, 400, 300])

        layout.addWidget(main_splitter)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.validate_button = QtWidgets.QPushButton("Valider la sélection")
        self.validate_button.clicked.connect(self.accept)
        self.validate_button.setStyleSheet("""
            QPushButton {
                background-color: #A23B2D;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35A4A;
            }
        """)

        cancel_button = QtWidgets.QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                color: #333333;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
        """)

        button_layout.addWidget(self.validate_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def accept(self):
        """Surcharge de accept() pour émettre le signal avec les données complètes."""
        try:
            logger.info(f"=== ACCEPT appelé ===")
            logger.info(f"Nombre d'items dans selected_items: {len(self.selected_items)}")
            
            taxonomy_data = self.get_selected_taxonomy()
            
            logger.info(f"Taxonomies récupérées: {len(taxonomy_data)}")
            
            if not taxonomy_data:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune sélection",
                    "Veuillez sélectionner au moins un élément avant de valider."
                )
                return
            
            self.selection_validated.emit(taxonomy_data)
            
            logger.info(f"✅ Validation du dialogue: {len(taxonomy_data)} taxonomies sélectionnées")
            
            super().accept()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur s'est produite lors de la validation:\n\n{str(e)}"
            )

    def resizeEvent(self, event):
        """Redimensionne l'overlay lors du redimensionnement du dialogue."""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(self.rect())
    
    def _on_node_selected_in_graph(self, node_name: str, node_details: dict):
        """Gère la sélection d'un nœud dans le graphe et affiche ses détails."""
        logger.info(f"Nœud sélectionné dans le graphe du dialogue: {node_name}")

        # Construire le HTML des détails
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D; margin: 0 0 10px 0;'>📋 {node_name}</h3>"

        # Type et niveau
        node_type = node_details.get('type', 'unknown')
        level = node_details.get('level', 0)
        details_html += f"<p style='margin: 4px 0;'>"
        details_html += f"<b>Type:</b> <span style='color: #555;'>{node_type}</span> | "
        details_html += f"<b>Niveau:</b> <span style='color: #555;'>{level}</span>"
        details_html += f"</p>"

        # Relations sortantes
        outgoing = node_details.get('outgoing', [])
        details_html += f"<p style='margin: 12px 0 6px 0;'>"
        details_html += f"<b style='color: #A23B2D;'>→ Relations sortantes ({len(outgoing)}):</b>"
        details_html += f"</p>"

        if outgoing:
            details_html += "<ul style='margin: 0; padding-left: 20px;'>"
            for i, (source, target, rel_type) in enumerate(outgoing[:8]):
                target_short = target[:35] + '...' if len(target) > 35 else target
                rel_short = rel_type[:20] + '...' if len(rel_type) > 20 else rel_type
                details_html += f"<li style='margin: 3px 0; font-size: 11px;'>"
                details_html += f"<span style='color: #333;'>{target_short}</span> "
                details_html += f"<span style='color: #888; font-style: italic;'>[{rel_short}]</span>"
                details_html += f"</li>"
            details_html += "</ul>"
            if len(outgoing) > 8:
                details_html += f"<p style='margin: 4px 0 0 20px; font-size: 11px; color: #888;'>"
                details_html += f"... et {len(outgoing) - 8} autre(s)"
                details_html += f"</p>"
        else:
            details_html += "<p style='margin: 0 0 0 20px; font-size: 11px; color: #888;'>Aucune</p>"

        # Relations entrantes
        incoming = node_details.get('incoming', [])
        details_html += f"<p style='margin: 12px 0 6px 0;'>"
        details_html += f"<b style='color: #2196F3;'>← Relations entrantes ({len(incoming)}):</b>"
        details_html += f"</p>"

        if incoming:
            details_html += "<ul style='margin: 0; padding-left: 20px;'>"
            for i, (source, target, rel_type) in enumerate(incoming[:8]):
                source_short = source[:35] + '...' if len(source) > 35 else source
                rel_short = rel_type[:20] + '...' if len(rel_type) > 20 else rel_type
                details_html += f"<li style='margin: 3px 0; font-size: 11px;'>"
                details_html += f"<span style='color: #333;'>{source_short}</span> "
                details_html += f"<span style='color: #888; font-style: italic;'>[{rel_short}]</span>"
                details_html += f"</li>"
            details_html += "</ul>"
            if len(incoming) > 8:
                details_html += f"<p style='margin: 4px 0 0 20px; font-size: 11px; color: #888;'>"
                details_html += f"... et {len(incoming) - 8} autre(s)"
                details_html += f"</p>"
        else:
            details_html += "<p style='margin: 0 0 0 20px; font-size: 11px; color: #888;'>Aucune</p>"

        details_html += "</div>"

        # Afficher dans la zone de description
        self.description_text.setHtml(details_html)

        # Ajouter à la liste des éléments sélectionnés si pas déjà présent
        self._add_to_selected_list(node_name, node_type)

    def _add_to_selected_list(self, node_name: str, node_type: str):
        """Ajoute un nœud à la liste des éléments sélectionnés."""
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            if item and item.data(Qt.UserRole) == node_name:
                self.selected_list.setCurrentItem(item)
                return

        icon_map = {
            'file': '📄', 'folder': '📁', 'function': '⚙️',
            'class': '🔷', 'variable': '🏷️', 'dependency': '🔗',
            'unknown': '❓'
        }
        icon = icon_map.get(node_type, '•')

        list_item = QtWidgets.QListWidgetItem(f"{icon} {node_name}")
        list_item.setData(Qt.UserRole, node_name)
        list_item.setData(Qt.UserRole + 1, node_type)
        self.selected_list.addItem(list_item)
        self.selected_list.setCurrentItem(list_item)

        taxonomy_item = self._find_taxonomy_item_by_name(node_name)
        
        if taxonomy_item:
            if taxonomy_item not in self.selected_items:
                self.selected_items.append(taxonomy_item)
                logger.info(f"✅ TaxonomyItem '{node_name}' ajouté à selected_items")
        else:
            logger.warning(f"⚠️ TaxonomyItem non trouvé pour '{node_name}', création temporaire")
            temp_item = TaxonomyItem(None, node_name, node_type, {'name': node_name, 'uid': None}, 0)
            if temp_item not in self.selected_items:
                self.selected_items.append(temp_item)
    
    def _has_extension(self, filename):
        """✅ Vérifie si le nom a une extension de fichier (amélioré)"""
        if not filename or not isinstance(filename, str):
            return False

        filename = filename.strip()

        known_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', 
            '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg',
            '.html', '.css', '.scss', '.sass', '.less',
            '.md', '.txt', '.log', '.csv',
            '.sh', '.bat', '.ps1'
        }

        filename_lower = filename.lower()
        for ext in known_extensions:    
            if filename_lower.endswith(ext):
                return True

        if '.' in filename:
            ext = filename.split('.')[-1]
            if 2 <= len(ext) <= 5 and ext.isalnum():
                return True

        return False
    
    def _on_level_changed(self, index):
        """Gère le changement de niveau"""
        selected_level = self.level_combo.currentData()
        logger.info(f"Niveau {selected_level} sélectionné")
        self._on_selection_changed()
    
    @pyqtSlot()
    def _on_selection_changed(self):
        selected_items = self.tree_widget.selectedItems()
        if hasattr(self.graph_helper, 'query_cache'):
            self.graph_helper.query_cache.clear()
        logger.info("🗑️ Cache vidé avant nouvelle sélection")
    
        selected_items = self.tree_widget.selectedItems()

        if not selected_items:
            self.description_text.clear()
            self.selected_list.clear()
            self.graph_update_signal.emit("", "", [], {})
            return

        last_item = selected_items[-1]

        if not isinstance(last_item, TaxonomyItem):
            logger.warning("⚠️ Élément sélectionné non reconnu comme TaxonomyItem.")
            return

        if len(selected_items) > 1:
            logger.info(f"\n{'='*70}")
            logger.info(f"🎯 MODE SÉLECTION MULTIPLE : {len(selected_items)} éléments")
            logger.info(f"{'='*70}")

            selected_data = []
            selected_uids = []

            for item in selected_items:
                if isinstance(item, TaxonomyItem):
                    item_uid = item.item_data.get('uid')
                    item_name = self.normalize_node_name(
                        item.item_data.get('name') or item.item_data.get('label', 'N/A')
                    )

                    if not item_uid:
                        item_uid = self._get_node_uid_by_name(item_name)

                    if item_uid:
                        selected_uids.append(item_uid)
                        selected_data.append({
                            'uid': item_uid,
                            'name': item_name,
                            'type': item.item_type,
                            'level': item.level,
                            'data': item.item_data
                        })
                        logger.info(f"  ✓ {item_name} ({item.item_type})")

            if not selected_uids:
                logger.warning("⚠️ Aucun UID valide dans la sélection")
                return

            self._display_multiple_selection_details(selected_items)

            relations = self._get_multi_selection_relations(selected_uids)

            related_items = []
            for item_data in selected_data:
                related_items.append({
                    'name': item_data['name'],
                    'uid': item_data['uid'],
                    'type': item_data['type'],
                    'taxonomy_level': item_data['level'],
                    'search_depth': 1,  # Multi-sélection = niveau 1
                    'relations': relations
                })

            # Émettre signal
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.graph_update_signal.emit(
                "Relations Multiples",
                "",
                related_items,
                self.project_data
            ))

            for item in selected_items:
                if isinstance(item, TaxonomyItem) and item not in self.selected_items:
                    self.selected_items.append(item)

            return

        data = last_item.item_data or {}
        item_type = last_item.item_type or "unknown"

        has_internal_structure = (
            item_type == 'file' and (
                len(data.get('classes', [])) > 0 or
                len(data.get('functions', [])) > 0 or
                len(data.get('variables', [])) > 0
            )
        )

        if has_internal_structure:
            logger.info(f"\n{'='*70}")
            logger.info(f"📂 MODE STRUCTURE INTERNE : {last_item.text(0)}")
            logger.info(f"{'='*70}")

            self._display_internal_structure_details(last_item, data)

            self.current_central_uid = data.get('uid')
            self.current_central_name = self.normalize_node_name(
                data.get('name') or data.get('label', 'N/A')
            )

            self.graph_update_signal.emit(
                self.current_central_name,
                self.current_central_uid,
                [{'mode': 'internal_structure', 'data': data}],
                self.project_data
            )

            if last_item not in self.selected_items:
                self.selected_items.append(last_item)

            return

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 MODE RELATIONS EXTERNES : {last_item.text(0)}")
        logger.info(f"{'='*70}")

        selected_level = self.level_combo.currentData()

        self.current_central_uid = data.get('uid')
        self.current_central_name = self.normalize_node_name(
            data.get('name') or data.get('label', 'N/A')
        )

        if not self.current_central_uid:
            if self.current_central_name:
                self.current_central_uid = self._get_node_uid_by_name(self.current_central_name)

            if not self.current_central_uid:
                self.description_text.setHtml(
                    "<b style='color: #D32F2F;'>⚠️ Erreur :</b> UID du nœud introuvable"
                )
                return

        logger.info(f"  UID: {self.current_central_uid}")
        logger.info(f"  Niveau: {selected_level}")

        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()

        self.loader_thread = DataLoaderThread(self, self.current_central_uid, selected_level)
        self.loader_thread.progress_update.connect(self._on_loading_progress)
        self.loader_thread.loading_complete.connect(self._on_loading_complete)
        self.loader_thread.loading_error.connect(self._on_loading_error)
        self.loader_thread.start()

        if last_item not in self.selected_items:
            self.selected_items.append(last_item)

    def _display_multiple_selection_details(self, selected_items):
        """✅ NOUVELLE MÉTHODE : Affiche les détails de la sélection multiple"""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D;'>🕸️ Sélection Multiple</h3>"

        details_html += f"<p><b>{len(selected_items)} éléments sélectionnés :</b></p>"
        details_html += "<ul style='margin: 10px 0; padding-left: 20px;'>"

        for item in selected_items:
            if isinstance(item, TaxonomyItem):
                icon = self._get_icon_for_type(item.item_type)
                details_html += f"<li>{icon} {item.text(0)} <i>({item.item_type})</i></li>"

        details_html += "</ul>"

        details_html += "<p style='color: #666; font-style: italic; margin-top: 15px;'>"
        details_html += "Le graphe affichera les relations de code (imports, appels, etc.) entre ces éléments."
        details_html += "</p>"

        details_html += "</div>"
        self.description_text.setHtml(details_html)

    def _get_icon_for_type(self, item_type: str) -> str:
        """✅ Helper pour icônes par type"""
        icon_map = {
            'file': '📄',
            'folder': '📁',
            'function': '⚙️',
            'class': '🔷',
            'variable': '🏷️',
            'dependency': '🔗',
            'unknown': '❓'
        }
        return icon_map.get(item_type, '•')


    def _display_internal_structure_details(self, item: TaxonomyItem, data: Dict):
        """Affiche les détails de la structure interne"""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D;'>📄 {item.text(0)}</h3>"

        # Classes
        classes = data.get('classes', [])
        details_html += f"<p><b style='color: #9C27B0;'>🏗️ Classes ({len(classes)}):</b></p>"
        if classes:
            details_html += "<ul>"
            for cls in classes[:5]:
                cls_name = cls.get('name', 'UnnamedClass')
                methods = len(cls.get('methods', []))
                details_html += f"<li>{cls_name} <i>({methods} méthodes)</i></li>"
            details_html += "</ul>"

        # Fonctions
        functions = data.get('functions', [])
        details_html += f"<p><b style='color: #FF9800;'>⚙️ Fonctions ({len(functions)}):</b></p>"
        if functions:
            details_html += "<ul>"
            for func in functions[:5]:
                details_html += f"<li>{func.get('name', 'UnnamedFunction')}</li>"
            details_html += "</ul>"

        # Variables
        variables = data.get('variables', [])
        details_html += f"<p><b style='color: #4CAF50;'>📊 Variables ({len(variables)}):</b></p>"
        if variables:
            details_html += "<ul>"
            for var in variables[:5]:
                details_html += f"<li>{var.get('name', 'UnnamedVariable')}</li>"
            details_html += "</ul>"

        details_html += "</div>"
        self.description_text.setHtml(details_html)
    
    @pyqtSlot(int, str, str)
    def _on_loading_progress(self, value, message, detail):
        """Met à jour la progression du chargement."""
        #self.loading_overlay.update_progress(value, message, detail)
        pass

    @pyqtSlot(dict)
    def _on_loading_complete(self, results):
        """Appelé quand le chargement est terminé."""
        relations_list = results.get('relations', [])
        related_items = results.get('related_items', [])
        
        logger.info(f"Chargement terminé: {len(relations_list)} relations")
        
        #QTimer.singleShot(500, self.loading_overlay.hide_loading)
        
        selected_items_tree = self.tree_widget.selectedItems()
        if selected_items_tree:
            last_item = selected_items_tree[-1]
            if isinstance(last_item, TaxonomyItem):
                self._display_tree_item_details(last_item, relations_list)
                
                if last_item not in self.selected_items:
                    self.selected_items.append(last_item)
        
        self.graph_update_signal.emit(
            self.current_central_name,
            self.current_central_uid,
            related_items,
            self.project_data
        )
        
        if selected_items_tree:
            last_item = selected_items_tree[-1]
            if isinstance(last_item, TaxonomyItem):
                self._add_to_selected_list(self.current_central_name, last_item.item_type)
    
    @pyqtSlot(str)
    def _on_loading_error(self, error_message):
        """Appelé en cas d'erreur pendant le chargement."""
        logger.error(f"Erreur de chargement: {error_message}")
        self.loading_overlay.hide_loading()
        
        QtWidgets.QMessageBox.critical(
            self,
            "Erreur de chargement",
            f"Une erreur s'est produite lors du chargement des données:\n\n{error_message}"
        )
    
    def _find_taxonomy_item_by_name(self, node_name: str):
        """Parcourt récursivement l'arbre pour trouver un TaxonomyItem par son nom."""
        def search_item(parent):
            child_count = parent.childCount() if hasattr(parent, 'childCount') else parent.topLevelItemCount()
            
            for i in range(child_count):
                child = parent.child(i) if hasattr(parent, 'child') else parent.topLevelItem(i)
                
                if isinstance(child, TaxonomyItem):
                    child_name = child.text(0)
                    if child_name == node_name or self.normalize_node_name(child_name) == node_name:
                        return child
                    
                    if child.childCount() > 0:
                        result = search_item(child)
                        if result:
                            return result
            
            return None
        
        return search_item(self.tree_widget)

    def _display_tree_item_details(self, item: TaxonomyItem, relations_list: List[Dict]):
        """Affiche les détails d'un item de l'arbre."""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D; margin: 0 0 10px 0;'>{item.text(0)}</h3>"

        details_html += f"<p style='margin: 4px 0;'>"
        details_html += f"<b>Type:</b> <span style='color: #555;'>{item.item_type}</span> | "
        details_html += f"<b>Niveau:</b> <span style='color: #555;'>{item.level}</span>"
        details_html += f"</p>"

        outgoing = [r for r in relations_list if r.get('source') == self.current_central_name]
        incoming = [r for r in relations_list if r.get('target') == self.current_central_name]

        details_html += f"<p style='margin: 12px 0 6px 0;'>"
        details_html += f"<b>Statistiques des relations:</b>"
        details_html += f"</p>"
        details_html += f"<ul style='margin: 0; padding-left: 20px;'>"
        details_html += f"<li><b>{len(relations_list)}</b> relations au total</li>"
        details_html += f"<li><b>{len(outgoing)}</b> relations sortantes</li>"
        details_html += f"<li><b>{len(incoming)}</b> relations entrantes</li>"
        details_html += f"</ul>"

        if outgoing:
            details_html += f"<p style='margin: 12px 0 6px 0;'>"
            details_html += f"<b style='color: #A23B2D;'>→ Exemples de relations sortantes:</b>"
            details_html += f"</p>"
            details_html += "<ul style='margin: 0; padding-left: 20px;'>"
            for rel in outgoing[:5]:
                target = rel.get('target', '')[:30] + '...' if len(rel.get('target', '')) > 30 else rel.get('target', '')
                rel_type = rel.get('relation_type', 'unknown')
                details_html += f"<li style='font-size: 11px;'>{target} <i>[{rel_type}]</i></li>"
            details_html += "</ul>"
            if len(outgoing) > 5:
                details_html += f"<p style='margin: 4px 0 0 20px; font-size: 11px; color: #888;'>"
                details_html += f"... et {len(outgoing) - 5} autre(s)"
                details_html += f"</p>"

        details_html += "</div>"
        self.description_text.setHtml(details_html)

    def get_selected_taxonomy(self):
        """
        ✅ VERSION FINALE : Retourne les taxonomies avec relations complètes
        """
        logger.info(f"=== get_selected_taxonomy appelé ===")

        taxonomy_data = []
        selected_level = self.level_combo.currentData()

        total_items = len(self.selected_items)

        if total_items == 0:
            logger.warning("⚠️ selected_items est vide !")

            # Fallback : récupérer depuis la liste d'affichage
            for i in range(self.selected_list.count()):
                list_item = self.selected_list.item(i)
                node_name = list_item.data(Qt.UserRole)

                taxonomy_item = self._find_taxonomy_item_by_name(node_name)

                if taxonomy_item:
                    self.selected_items.append(taxonomy_item)

            total_items = len(self.selected_items)

            if total_items == 0:
                return taxonomy_data

        # ✅ AFFICHER OVERLAY DE CHARGEMENT
        self.loading_overlay.show_loading(
            "Préparation des données...",
            f"Traitement de {total_items} élément(s)"
        )

        for idx, item in enumerate(self.selected_items):
            if not isinstance(item, TaxonomyItem):
                continue
            
            data = item.item_data
            item_level = item.level

            # ✅ MISE À JOUR PROGRESSION
            progress = int((idx / total_items) * 100)
            self.loading_overlay.update_progress(
                progress,
                f"Traitement {idx + 1}/{total_items}",
                f"Analyse de {item.text(0)}"
            )

            # ✅ RÉCUPÉRATION UID
            temp_uid = data.get('uid')
            temp_name = self.normalize_node_name(data.get('name', data.get('label', '')))

            if not temp_uid:
                temp_uid = self._get_node_uid_by_name(temp_name)

                if not temp_uid:
                    logger.warning(f"⚠️ UID manquant pour {temp_name}, ignoré")
                    continue
                
            # ✅ VALIDATION UID
            if not self._validate_uid_exists(temp_uid):
                logger.warning(f"⚠️ UID {temp_uid} invalide, ignoré")
                continue
            
            # ✅ RÉCUPÉRATION RELATIONS VIA MÉTHODES UNIFIÉES
            relations_list = []

            if selected_level == 1:
                relations_list = self._get_level_1_relations(temp_uid)
            elif selected_level == 2:
                relations_list = self._get_level_2_relations(temp_uid)

            # ✅ CONSTRUIRE RELATED_ITEMS
            related_items = []
            seen_nodes = set([temp_name])

            for rel in relations_list:
                for key in ['source', 'target']:
                    node_name = rel.get(key, '')
                    node_uid = rel.get(f'{key}_uid', '')

                    if node_name and node_name not in seen_nodes:
                        seen_nodes.add(node_name)

                        if not node_uid:
                            node_uid = self._get_node_uid_by_name(node_name)

                        related_items.append({
                            'name': node_name,
                            'uid': node_uid,
                            'type': rel.get(f'{key}_type', 'dependency'),
                            'taxonomy_level': item_level
                        })

            # ✅ AJOUTER À taxonomy_data
            taxonomy_data.append({
                'name': temp_name,
                'uid': temp_uid,
                'type': item.item_type,
                'level': item_level,
                'search_depth': selected_level,
                'data': data,
                'related': related_items,
                'relations': relations_list
            })

        # ✅ FINALISATION
        self.loading_overlay.update_progress(
            100, 
            "Terminé !", 
            f"{len(taxonomy_data)} taxonomies préparées"
        )

        QTimer.singleShot(500, self.loading_overlay.hide_loading)

        logger.info(f"✅ {len(taxonomy_data)} taxonomies retournées")

        return taxonomy_data

    def _is_class_name(self, name):
        """Détecte si un nom correspond à une classe"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Mots-clés de définition de classe
        class_keywords = [
            'public class', 'private class', 'protected class',
            'abstract class', 'static class', 'final class',
            'sealed class', 'internal class',
            'class ', 'interface ', 'trait ', 'struct ',
            'enum '
        ]

        for keyword in class_keywords:
            if name_lower.startswith(keyword):
                return True

        # Convention : commence par une majuscule (CamelCase)
        if (name_stripped and 
            name_stripped[0].isupper() and 
            '(' not in name_stripped and 
            '=' not in name_stripped and
            not name_stripped.isupper() and
            not '.' in name_stripped):  # Pas un chemin de fichier
            return True

        return False

    def _is_function_name(self, name):
        """Détecte si un nom correspond à une fonction"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Mots-clés de définition de fonction
        function_keywords = [
            'def ', 'function ', 'fn ', 'func ', 
            'async def ', 'async function ',
            'public ', 'private ', 'protected ',
            'static ', 'void ', 'async '
        ]
        
        for keyword in function_keywords:
            if name_lower.startswith(keyword):
                return True

        # Présence de parenthèses (signature de fonction)
        if '(' in name_stripped and ')' in name_stripped:
            # Vérifier que ce n'est pas une déclaration de variable
            if not self._is_variable_declaration(name_stripped):
                return True

        # Convention : commence par une minuscule et contient des underscores
        if (name_stripped and 
            name_stripped[0].islower() and 
            '_' in name_stripped and
            '=' not in name_stripped.split('(')[0]):
            return True

        return False

    def _is_variable_name(self, name):
        """Détecte si un nom correspond à une variable"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        # Mots-clés de déclaration de variable
        variable_keywords = [
            'var ', 'let ', 'const ', 'val ', 'final ',
            'static ', 'public static ', 'private static ',
            'protected static ', 'readonly '
        ]

        for keyword in variable_keywords:
            if name_lower.startswith(keyword):
                # S'assurer que ce n'est pas une fonction
                if '(' not in name_stripped or '=' in name_stripped:
                    return True

        # Déclaration typée (ex: "variable: Type = value")
        if self._is_variable_declaration(name_stripped):
            return True

        # Constantes en MAJUSCULES avec underscores
        if name_stripped.isupper() and '_' in name_stripped:
            return True

        return False

    def _is_variable_declaration(self, name):
        """Détecte une déclaration de variable typée"""
        if not name:
            return False

        name_stripped = name.strip()

        # Pattern : "name: Type" ou "name: Type = value"
        if ':' in name_stripped and '(' not in name_stripped.split(':')[0]:
            parts = name_stripped.split(':')
            if len(parts) >= 2:
                type_part = parts[1].strip().split('=')[0].strip()

                if type_part:
                    # Types primitifs courants
                    primitive_types = [
                        'int', 'str', 'float', 'bool', 'double', 'long',
                        'string', 'boolean', 'number', 'any', 'void',
                        'list', 'dict', 'tuple', 'set', 'array', 'object',
                        'List', 'Dict', 'Tuple', 'Set', 'Array', 'Object',
                        'Optional', 'Union'
                    ]

                    type_name = type_part.split('[')[0].split('<')[0].strip()
                    if type_name in primitive_types or (type_name and type_name[0].isupper()):
                        return True

        # Pattern : "name = value" (sans mot-clé function)
        if '=' in name_stripped:
            before_equal = name_stripped.split('=')[0].strip().lower()
            if ('def' not in before_equal and 
                'function' not in before_equal and 
                'fn' not in before_equal and
                '(' not in before_equal):
                return True

        return False
    
    def closeEvent(self, event):
        """Fermeture propre."""
        try:
            if self.loader_thread and self.loader_thread.isRunning():
                self.loader_thread.cancel()
                self.loader_thread.wait()
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture du dialogue: {e}")
        finally:
            super().closeEvent(event)