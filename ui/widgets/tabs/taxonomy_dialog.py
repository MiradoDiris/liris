# taxonomy_dialog.py - Version intégrée avec GraphWidget et Loader Professionnel
import os
import json
import uuid
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, QThread, pyqtSlot
from typing import List, Dict, Optional
from ui.widgets.tabs.graph_widget import GraphWidget
from PyQt5.QtGui import QColor, QBrush

from utils.logger import logger
from ui.localization.translator import tr
from .taxonomy_item import TaxonomyItem


from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QTimer

class LoadingOverlay(QtWidgets.QWidget):
    """Overlay de chargement compact avec QFrame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.animation_timer = QTimer()

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
        #self.animation_timer.start(30)
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
        #self.animation_timer.stop()
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

            self.progress_update.emit(10, "Initialisation...", "Chargement mappings UID")
            self.dialog._load_uid_mappings()

            if self.is_cancelled:
                return

            self.progress_update.emit(30, "Analyse du nœud...", f"UID {self.uid}")
            node_details = self.dialog._get_node_details(self.uid)

            # ✅ AJOUT : Estimation du nombre de relations
            estimated_relations = len(node_details.get('outgoing_relations', [])) + \
                                 len(node_details.get('incoming_relations', []))

            relations_list = []
            if self.level == 1:
                if self.is_cancelled:
                    return
                self.progress_update.emit(
                    50, 
                    "Niveau 1...", 
                    f"~{estimated_relations} relations estimées"
                )
                relations_list = self.dialog._get_level_1_relations(self.uid)
                self.progress_update.emit(90, "Finalisation...", f"{len(relations_list)} trouvées")

            elif self.level == 2:
                if self.is_cancelled:
                    return
                self.progress_update.emit(50, "Niveau 1...", "Relations directes")
                level1_rels = self.dialog._get_level_1_relations(self.uid)

                if self.is_cancelled:
                    return
                self.progress_update.emit(70, "Niveau 2...", "Relations indirectes")
                relations_list = self.dialog._get_level_2_relations(self.uid)
                self.progress_update.emit(90, "Finalisation...", f"{len(relations_list)} trouvées")
            
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
        self.resize(1200, 800)
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
            empty.setForeground(0, QBrush(QColor("#999999")))
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
        logger.info(f"🔒 UIDs uniques: {len(self._uid_set)}")

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
            orphan_item.loaded = True
            orphan_item.is_expandable = False

            # Ajouter éléments de code
            self._add_all_code_elements(orphan_item, orphan, 1)

            # Cache
            if orphan_uid:
                self._node_cache[orphan_uid] = orphan_item
                self._uid_set.add(orphan_uid)

    def _build_cluster_tree(self, cluster, cluster_idx, total_clusters):
        """
        Construction récursive COMPLÈTE d'un cluster (une seule définition !)
        """
        cluster_name = cluster.get('name') or cluster.get('id') or "Cluster sans nom"
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

        # Cache
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
                'level1': []
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

                # Forcer type correct si extension détectée
                if self._has_extension(label_name):
                    root_label['nodeType'] = 'file'

                self._build_label_tree_recursive(
                    parent_item=cluster_item,
                    label_data=root_label,
                    level=1
                )

    def _build_label_tree_recursive(self, parent_item, label_data, level):
        """
        ✅ Construction récursive des labels (fichiers / sous-dossiers)
        """
        label_name = label_data.get("name") or label_data.get("label") or f"Label_{level}"
        label_uid = label_data.get("uid", f"label_{uuid.uuid4()}")

        # ✅ S'assurer que path est présent dans item_data
        if 'path' not in label_data and 'sourcePath' not in label_data:
            # Essayer de construire un path depuis le parent
            if hasattr(parent_item, 'item_data'):
                parent_path = parent_item.item_data.get('path') or parent_item.item_data.get('sourcePath', '')
                if parent_path:
                    label_data['path'] = os.path.join(parent_path, label_name)

        # Déterminer le type de nœud
        node_type = label_data.get("nodeType", "folder")
        if label_name.endswith((".py", ".js", ".java", ".cpp")):
            node_type = "file"

        label_item = TaxonomyItem(
            parent_item,
            label_name,
            node_type,
            label_data,
            level
        )
        label_item.loaded = True
        label_item.is_expandable = False

        if label_uid:
            self._node_cache[label_uid] = label_item
            self._uid_set.add(label_uid)

        # Ajouter les éléments internes (classes, fonctions, variables)
        for cls in label_data.get("classes", []):
            cls_item = TaxonomyItem(label_item, cls.get("name", "Classe"), "class", cls, level + 1)
            cls_item.loaded = True

        for func in label_data.get("functions", []):
            func_item = TaxonomyItem(label_item, func.get("name", "Fonction"), "function", func, level + 1)
            func_item.loaded = True

        for var in label_data.get("variables", []):
            var_item = TaxonomyItem(label_item, var.get("name", "Variable"), "variable", var, level + 1)
            var_item.loaded = True

        # Charger récursivement les sous-niveaux
        for child_level in [f"level{level}", "children", "level1", "level2", "level3"]:
            children = label_data.get(child_level, [])
            for child in children:
                self._build_label_tree_recursive(label_item, child, level + 1)

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
        ✅ VERSION FINALE CORRIGÉE
        Affiche TOUS les éléments avec noms RÉELS (classes, fonctions, variables)
        """
        stats = {
            'classes': 0,
            'functions': 0,
            'variables': 0,
            'total': 0
        }

        # ========== CLASSES ==========
        classes = data.get('classes', [])
        for cls in classes:
            cls_uid = cls.get('uid', '')

            # Vérifier doublon
            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
            cls_name = TaxonomyDialog.safe_get_name(cls, 'class', cls_uid)

            logger.debug(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

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

            # ========== MÉTHODES ==========
            methods = cls.get('methods', [])
            for method in methods:
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
                method_name = TaxonomyDialog.safe_get_name(method, 'method', method_uid)

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

            # ========== VARIABLES DE CLASSE ==========
            cls_vars = cls.get('variables', [])
            for var in cls_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
                var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

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

        # ========== FONCTIONS GLOBALES ==========
        functions = data.get('functions', [])
        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
            func_name = TaxonomyDialog.safe_get_name(func, 'function', func_uid)

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

            # ========== VARIABLES DE FONCTION ==========
            func_vars = func.get('variables', [])
            for var in func_vars:
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
                var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

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

        # ========== VARIABLES GLOBALES ==========
        variables = data.get('variables', [])
        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
            var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

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
        """
        ✅ VERSION CORRIGÉE COMPLÈTE
        Ajoute les classes d'un nœud à l'arbre avec leurs méthodes et variables
        """

        classes = data_node.get('classes', [])

        for cls in classes:
            cls_uid = cls.get('uid', '')

            # Vérifier doublon
            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
            cls_name = TaxonomyDialog.safe_get_name(cls, 'class', cls_uid)

            logger.debug(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

            # ✅ Créer l'item classe
            cls_item = TaxonomyItem(parent_item, cls_name, 'class', cls, parent_item.level + 1)
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            # ========== MÉTHODES ==========
            for method in cls.get('methods', []):
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
                method_name = TaxonomyDialog.safe_get_name(method, 'method', method_uid)

                logger.debug(f"      ⚙️ Méthode: '{method_name}' (uid={method_uid})")

                # ✅ Créer l'item méthode
                method_item = TaxonomyItem(cls_item, method_name, 'function', method, cls_item.level + 1)
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

            # ========== VARIABLES DE LA CLASSE ==========
            for var in cls.get('variables', []):
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ CORRECTION : Utiliser TaxonomyDialog.safe_get_name
                var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                # ✅ Créer l'item variable
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
        if self._has_extension(item_name):
            return "file"

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

        item_type = item_data.get('type', '').lower()
        if item_type in ['file', 'folder', 'directory', 'function', 'class', 'variable']:
            return item_type if item_type != 'directory' else 'folder'

        categories = item_data.get('category', [])
        if 'file' in categories:
            return "file"
        if 'folder' in categories or 'directory' in categories:
            return "folder"

        if item_data.get('files') or item_data.get('fileContents'):
            return "file"

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
        """
        ✅ VERSION CORRIGÉE COMPLÈTE
        Ajoute les fonctions d'un nœud à l'arbre avec leurs variables
        """

        functions = data_node.get('functions', [])

        for func in functions:
            func_uid = func.get('uid', '')

            # Vérifier doublon
            if func_uid and func_uid in self._uid_set:
                continue
            
            # ✅ Récupérer le nom de la FONCTION (pas de la classe !)
            func_name = TaxonomyDialog.safe_get_name(func, 'function', func_uid)

            logger.debug(f"   ⚙️ Fonction: '{func_name}' (uid={func_uid})")

            # ✅ Créer l'item fonction
            func_item = TaxonomyItem(parent_item, func_name, 'function', func, parent_item.level + 1)
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

            # ========== VARIABLES DE LA FONCTION ==========
            for var in func.get('variables', []):
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                # ✅ Récupérer le nom de la VARIABLE (pas de la classe !)
                var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

                logger.debug(f"      📦 Variable: '{var_name}' (uid={var_uid})")

                # ✅ Créer l'item variable
                var_item = TaxonomyItem(func_item, var_name, 'variable', var, func_item.level + 1)
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)


    def _add_variables_to_tree(self, parent_item, data_node):
        """
        ✅ VERSION CORRIGÉE COMPLÈTE
        Ajoute les variables d'un nœud à l'arbre
        """

        variables = data_node.get('variables', [])

        for var in variables:
            var_uid = var.get('uid', '')

            # Vérifier doublon
            if var_uid and var_uid in self._uid_set:
                continue
            
            # ✅ Récupérer le nom de la VARIABLE (pas de la classe !)
            var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

            logger.debug(f"   📦 Variable: '{var_name}' (uid={var_uid})")

            # ✅ Créer l'item variable
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

        # ✅ CORRECTION : Vérifier loaded APRÈS avoir identifié le type
        # Si déjà chargé ET a des enfants réels, rien à faire
        if item.loaded and item.childCount() > 0:
            # Vérifier que ce n'est pas juste un placeholder
            first_child = item.child(0)
            if first_child and first_child.text(0) != "⏳ Chargement...":
                return

        # Marquer comme chargé
        item.loaded = True

        # Retirer le placeholder s'il existe
        self._remove_placeholder(item)

        try:
            item_type = getattr(item, 'item_type', None)
            item_name = item.text(0)

            # ✅ CORRECTION : Forcer la détection du type
            if item_type is None:
                item_type = 'file' if self._has_extension(item_name) else 'folder'

            logger.info(f"📂 Expansion: {item_name} (type={item_type}, level={item.level})")

            # Si c'est un cluster racine (level == 0)
            if getattr(item, 'level', None) == 0 and item.item_data:
                logger.info(f"  → Chargement cluster")
                self._load_cluster_content(item)
                return

            # Si c'est un fichier : charger classes/fonctions/variables
            if item_type == 'file':
                logger.info(f"  → Chargement contenu fichier")
                self._load_file_content(item)
                return

            # Si c'est un dossier : charger ses enfants
            if item_type == 'folder':
                logger.info(f"  → Chargement enfants dossier")
                self._load_folder_children(item)
                return

            # Fallback par UID
            uid = item.item_data.get('uid') if getattr(item, 'item_data', None) else None
            if uid:
                logger.info(f"  → Chargement par UID: {uid}")
                self._load_item_detailed_content(item, uid)

        except Exception as e:
            logger.error(f"❌ Erreur expansion {item.text(0)}: {e}")
            import traceback
            traceback.print_exc()


    def _load_file_content(self, file_item):
        """
        ✅ VERSION CORRIGÉE : Recharge TOUJOURS depuis Dgraph + Noms JAMAIS génériques
        """
        file_data = file_item.item_data
        file_name = file_data.get('name') or file_data.get('label', 'Unknown')
        file_uid = file_data.get('uid')

        logger.info(f"📄 Chargement fichier: {file_name} (uid={file_uid})")

        # ✅ TOUJOURS RECHARGER depuis Dgraph
        if file_uid and self.dgraph_connector:
            detailed_data = self._fetch_file_complete_data(file_uid)
            if detailed_data:
                file_data = detailed_data
                file_item.item_data = detailed_data
                logger.info(f"   ✅ Données rechargées depuis Dgraph")
            else:
                logger.warning(f"   ⚠️ Impossible de recharger depuis Dgraph")

        # Récupérer éléments de code
        classes = file_data.get('classes', [])
        functions = file_data.get('functions', [])
        variables = file_data.get('variables', [])

        # ========== CLASSES ==========
        for cls in classes:
            cls_uid = cls.get('uid', '')

            # Vérifier doublon
            if cls_uid and cls_uid in self._uid_set:
                continue
            
            # ✅ UTILISER safe_get_name au lieu de validation stricte
            cls_name = TaxonomyDialog.safe_get_name(cls, 'class', cls_uid)

            logger.info(f"   🗂️ Classe: '{cls_name}' (uid={cls_uid})")

            cls_item = TaxonomyItem(
                file_item,
                cls_name,  # ✅ Toujours un nom RÉEL
                'class',
                cls,
                file_item.level + 1
            )
            cls_item.loaded = True

            if cls_uid:
                self._node_cache[cls_uid] = cls_item
                self._uid_set.add(cls_uid)

            # ✅ MÉTHODES
            for method in cls.get('methods', []):
                method_uid = method.get('uid', '')

                if method_uid and method_uid in self._uid_set:
                    continue
                
                # ✅ UTILISER safe_get_name
                method_name = TaxonomyDialog.safe_get_name(method, 'method', method_uid)

                logger.info(f"      ⚙️ Méthode: '{method_name}' (uid={method_uid})")

                method_item = TaxonomyItem(
                    cls_item,
                    method_name,  # ✅ Toujours un nom RÉEL
                    'function',
                    method,
                    cls_item.level + 1
                )
                method_item.loaded = True

                if method_uid:
                    self._node_cache[method_uid] = method_item
                    self._uid_set.add(method_uid)

                # Variables de la méthode
                for var in method.get('variables', []):
                    var_uid = var.get('uid', '')

                    if var_uid and var_uid in self._uid_set:
                        continue
                    
                    var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

                    var_item = TaxonomyItem(
                        method_item,
                        var_name,
                        'variable',
                        var,
                        method_item.level + 1
                    )
                    var_item.loaded = True

                    if var_uid:
                        self._node_cache[var_uid] = var_item
                        self._uid_set.add(var_uid)

        # ========== FONCTIONS ==========
        for func in functions:
            func_uid = func.get('uid', '')

            if func_uid and func_uid in self._uid_set:
                continue
            
            # ✅ UTILISER safe_get_name
            func_name = TaxonomyDialog.safe_get_name(func, 'function', func_uid)

            logger.info(f"   ⚙️ Fonction: '{func_name}' (uid={func_uid})")

            func_item = TaxonomyItem(
                file_item,
                func_name,  # ✅ Toujours un nom RÉEL
                'function',
                func,
                file_item.level + 1
            )
            func_item.loaded = True

            if func_uid:
                self._node_cache[func_uid] = func_item
                self._uid_set.add(func_uid)

            # Variables de la fonction
            for var in func.get('variables', []):
                var_uid = var.get('uid', '')

                if var_uid and var_uid in self._uid_set:
                    continue
                
                var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

                var_item = TaxonomyItem(
                    func_item,
                    var_name,
                    'variable',
                    var,
                    func_item.level + 1
                )
                var_item.loaded = True

                if var_uid:
                    self._node_cache[var_uid] = var_item
                    self._uid_set.add(var_uid)

        # ========== VARIABLES GLOBALES ==========
        for var in variables:
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue
            
            var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)

            logger.info(f"   📦 Variable: '{var_name}' (uid={var_uid})")

            var_item = TaxonomyItem(
                file_item,
                var_name,  # ✅ Toujours un nom RÉEL
                'variable',
                var,
                file_item.level + 1
            )
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

        logger.info(f"   ✅ {file_item.childCount()} éléments ajoutés")

    @staticmethod
    def safe_get_name(item_data: dict, item_type: str, uid: str = None) -> str:
        """
        ✅ Retourne TOUJOURS un nom valide pour un élément de code.

        Args:
            item_data: Dictionnaire contenant les données de l'élément
            item_type: Type d'élément ('class', 'function', 'variable', 'method')
            uid: UID de l'élément (optionnel)

        Returns:
            Nom valide (jamais générique comme "Classe" ou "Fonction")
        """
        # 1️⃣ Essayer TOUS les champs de nom possibles
        name_fields = ['name', 'label', 'id', 'functionName', 'className', 'variableName']
        for field in name_fields:
            name = item_data.get(field, '').strip()
            if name and not name.startswith(('Unnamed', 'class-', 'func-', 'var-', 'method-', 'N/A', 'Element')):
                # Nettoyer les préfixes de type
                name = name.replace('Function: ', '').replace('Method: ', '').replace('Class: ', '').replace('Variable: ', '').strip()
                if name:  # Vérifier qu'il reste quelque chose après nettoyage
                    return name

        # 2️⃣ Essayer description courte
        description = item_data.get('description', '').strip()
        if description and len(description) < 50 and '\n' not in description:
            return description

        # 3️⃣ Utiliser ligne + type (ex: "Func_L42")
        line = item_data.get('line')
        if line:
            type_prefix = {
                'class': 'Class',
                'function': 'Func',
                'method': 'Method',
                'variable': 'Var'
            }.get(item_type, 'Element')
            return f"{type_prefix}_L{line}"

        # 4️⃣ Utiliser UID court
        if not uid:
            uid = item_data.get('uid', '')

        if uid and len(uid) > 8:
            suffix = uid[-8:]
            type_map = {
                'class': 'Classe',
                'function': 'Fonction',
                'method': 'Méthode',
                'variable': 'Variable'
            }
            prefix = type_map.get(item_type, 'Element')
            return f"{prefix}_{suffix}"

        # 5️⃣ DERNIER RECOURS : Hash de l'objet
        suffix = f"{id(item_data) & 0xFFFFFF:06x}"
        type_map = {
            'class': 'Classe',
            'function': 'Fonction',
            'method': 'Méthode',
            'variable': 'Variable'
        }
        prefix = type_map.get(item_type, 'Element')
        return f"{prefix}_{suffix}"

    def _fetch_file_complete_data(self, file_uid: str) -> Optional[Dict]:
        """
        🆕 RECHARGE TOUTES LES DONNÉES D'UN NŒUD AVEC LE CODE COMPLET
        """
        if not file_uid or not self.dgraph_connector:
            return None
    
        query = f"""
        {{
          node(func: uid({file_uid})) {{
            uid
            name
            label
            nodeType
            path
            description
            fileContents
            codeContent
            docstring
            line
            
            # ✅ CLASSES COMPLÈTES avec code
            classes {{
              uid
              name
              description
              line
              codeContent
              bases
              uses_vars
              
              # ✅ MÉTHODES avec code
              methods {{
                uid
                name
                description
                line
                codeContent  # ✅ CRITIQUE
                params
                returns
                docstring
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
            
            # ✅ FONCTIONS COMPLÈTES avec code
            functions {{
              uid
              name
              description
              line
              codeContent  # ✅ CRITIQUE
              params
              returns
              docstring
              
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
          }}
        }}
        """
    
        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
    
            result = self.dgraph_connector._parse_response(resp)
            
            if result and 'node' in result and result['node']:
                node_data = result['node'][0]
                
                # 📊 DIAGNOSTIC DÉTAILLÉ
                code = node_data.get('codeContent', '') or node_data.get('fileContents', '')
                classes = node_data.get('classes', [])
                functions = node_data.get('functions', [])
                
                logger.info(f"   📥 Nœud rechargé: {node_data.get('name', 'N/A')}")
                logger.info(f"      - Code fichier: {len(code)} chars")
                logger.info(f"      - Classes: {len(classes)}")
                logger.info(f"      - Fonctions: {len(functions)}")
                
                # ✅ VÉRIFIER CODE DES CLASSES/FONCTIONS
                for cls in classes:
                    cls_code = cls.get('codeContent', '')
                    methods = cls.get('methods', [])
                    logger.info(f"         🗂️ Classe '{cls.get('name')}': {len(cls_code)} chars")
                    
                    for method in methods:
                        method_code = method.get('codeContent', '')
                        if method_code:
                            logger.info(f"            ✓ Méthode '{method.get('name')}': {len(method_code)} chars")
                        else:
                            logger.warning(f"            ⚠️ Méthode '{method.get('name')}': AUCUN code")
                
                for func in functions:
                    func_code = func.get('codeContent', '')
                    if func_code:
                        logger.info(f"         ✓ Fonction '{func.get('name')}': {len(func_code)} chars")
                    else:
                        logger.warning(f"         ⚠️ Fonction '{func.get('name')}': AUCUN code")
                
                return node_data
            else:
                logger.warning(f"⚠️ Aucun nœud trouvé pour UID {file_uid}")
                return None
    
        except Exception as e:
            logger.error(f"❌ Erreur rechargement nœud {file_uid}: {e}")
            import traceback
            traceback.print_exc()
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

        for ch in codes:
            name = ch.get('name') or 'Code'
            ch_uid = ch.get('uid', '')

            # ✅ NOUVEAU : RECHARGER LE CODE si c'est une classe/fonction/méthode
            if ch_uid and self.dgraph_connector:
                complete_ch_data = self._fetch_complete_node_data(ch_uid)
                if complete_ch_data:
                    ch.update(complete_ch_data)
                    logger.info(f"      ✅ Code rechargé pour {name}")

                    code = ch.get('codeContent', '')
                    if code:
                        logger.info(f"         📦 {len(code)} chars")
                    else:
                        logger.warning(f"         ⚠️ AUCUN code")

            code_item = TaxonomyItem(
                folder_item, 
                name, 
                ch.get('nodeType', 'function'), 
                ch,  # ✅ Contient maintenant codeContent
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
        ✅ VERSION CORRIGÉE : Charge ET recharge le code complet
        """
        # ✅ TOUJOURS RECHARGER depuis Dgraph
        complete_data = self._fetch_complete_node_data(uid)

        if complete_data:
            # ✅ REMPLACER les données existantes
            item.item_data.update(complete_data)
            logger.info(f"✅ Données rechargées pour UID {uid}")

            # 📊 DIAGNOSTIC
            code = complete_data.get('codeContent', '') or complete_data.get('fileContents', '')
            classes = complete_data.get('classes', [])
            functions = complete_data.get('functions', [])

            logger.info(f"   📦 Code: {len(code)} chars")
            logger.info(f"   🗂️ {len(classes)} classes, {len(functions)} fonctions")

            # Vérifier code des classes/fonctions
            for cls in classes:
                cls_code = cls.get('codeContent', '')
                if cls_code:
                    logger.info(f"      ✓ Classe '{cls.get('name')}': {len(cls_code)} chars")
                else:
                    logger.warning(f"      ⚠️ Classe '{cls.get('name')}': AUCUN code")

            for func in functions:
                func_code = func.get('codeContent', '')
                if func_code:
                    logger.info(f"      ✓ Fonction '{func.get('name')}': {len(func_code)} chars")
                else:
                    logger.warning(f"      ⚠️ Fonction '{func.get('name')}': AUCUN code")

        else:
            logger.warning(f"⚠️ Impossible de recharger les données pour UID {uid}")
            # Fallback : utiliser les données locales
            complete_data = item.item_data

        # ✅ CONSTRUCTION DE L'ARBRE avec données rechargées
        def has_valid_name(element):
            """Validation simple : vérifie juste qu'il y a un nom"""
            name = element.get('name')
            return bool(name and name.strip())

        # ✅ CLASSES
        classes = [cls for cls in complete_data.get('classes', []) if has_valid_name(cls)]
        if classes:
            logger.info(f"   🗂️ {len(classes)} classes valides")
            for cls in classes:
                cls_name = TaxonomyDialog.safe_get_name(cls, 'class', cls_uid)
                cls_uid = cls.get('uid', '')

                if cls_uid and cls_uid in self._uid_set:
                    continue

                cls_item = TaxonomyItem(
                    item,
                    cls_name,
                    'class',
                    cls,  # ✅ Contient maintenant codeContent
                    item.level + 1
                )
                cls_item.loaded = True
                cls_item.is_expandable = False

                if cls_uid:
                    self._node_cache[cls_uid] = cls_item
                    self._uid_set.add(cls_uid)

                # ✅ MÉTHODES
                methods = [m for m in cls.get('methods', []) if has_valid_name(m)]
                for method in methods:
                    method_name = TaxonomyDialog.safe_get_name(method, 'method', method_uid)
                    method_uid = method.get('uid', '')

                    if method_uid and method_uid in self._uid_set:
                        continue

                    method_item = TaxonomyItem(
                        cls_item,
                        method_name,
                        'function',
                        method,  # ✅ Contient maintenant codeContent
                        cls_item.level + 1
                    )
                    method_item.loaded = True

                    if method_uid:
                        self._node_cache[method_uid] = method_item
                        self._uid_set.add(method_uid)

        # ✅ FONCTIONS
        functions = [f for f in complete_data.get('functions', []) if has_valid_name(f)]
        if functions:
            logger.info(f"   ⚙️ {len(functions)} fonctions valides")
            for func in functions:
                func_name = TaxonomyDialog.safe_get_name(func, 'function', func_uid)
                func_uid = func.get('uid', '')

                if func_uid and func_uid in self._uid_set:
                    continue

                func_item = TaxonomyItem(
                    item,
                    func_name,
                    'function',
                    func,  # ✅ Contient maintenant codeContent
                    item.level + 1
                )
                func_item.loaded = True

                if func_uid:
                    self._node_cache[func_uid] = func_item
                    self._uid_set.add(func_uid)

        # ✅ VARIABLES
        variables = [v for v in complete_data.get('variables', []) if has_valid_name(v)]
        for var in variables:
            var_name = TaxonomyDialog.safe_get_name(var, 'variable', var_uid)
            var_uid = var.get('uid', '')

            if var_uid and var_uid in self._uid_set:
                continue

            var_item = TaxonomyItem(
                item,
                var_name,
                'variable',
                var,
                item.level + 1
            )
            var_item.loaded = True

            if var_uid:
                self._node_cache[var_uid] = var_item
                self._uid_set.add(var_uid)

        # ✅ ENFANTS HIÉRARCHIQUES
        children = complete_data.get('children', [])
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
        """
        ✅ VERSION ALIGNÉE : Récupère détails complets avec enfants récursifs
        """
        if not uid:
            return {}

        cache_key = f"node_details_{uid}"
        if hasattr(self, 'query_cache'):
            cached_data = self.query_cache.get(cache_key)
            if cached_data:
                return cached_data

        logger.info(f"🔎 Récupération des détails complets pour UID: {uid}")

        # ✅ Requête étendue : inclut path, sourcePath, full_path
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            level
            nodeType
            category
            description
            path
            sourcePath
            full_path

            outgoing_relations {{
              target_uid
              target_name
              relation_type
              category
              line
            }}

            incoming_relations {{
              source_uid
              source_name
              relation_type
              category
            }}

            relations

            parents {{
              uid
              name
              label
              nodeType
              level
              category
              path
              sourcePath
            }}

            # ✅ Enfants récursifs jusqu'à 3 niveaux
            children: ~parents {{
              uid
              name
              label
              nodeType
              level
              category
              path
              sourcePath

              children: ~parents {{
                uid
                name
                label
                nodeType
                level
                category
                path
                sourcePath

                children: ~parents {{
                  uid
                  name
                  label
                  nodeType
                  level
                  category
                  path
                  sourcePath
                }}
              }}
            }}

            clusters {{
              uid
              name
              path
            }}
          }}
        }}
        """

        try:
            result = self._execute_dgraph_query(query)
            if result and 'node' in result and result['node']:
                node = result['node'][0]

                # ✅ Nettoyage : filtrer les enfants sans nom
                def _clean_children(data):
                    if not data or not isinstance(data, list):
                        return []
                    cleaned = []
                    for c in data:
                        name = c.get('name') or c.get('label', '')
                        if not name or name.strip() == "":
                            continue
                        c['name'] = name.strip()
                        if 'children' in c:
                            c['children'] = _clean_children(c['children'])
                        cleaned.append(c)
                    return cleaned

                node['children'] = _clean_children(node.get('children', []))

                # ✅ Cache résultat
                if hasattr(self, 'query_cache'):
                    self.query_cache.set(cache_key, node)

                logger.info(
                    f"✅ Nœud trouvé: {node.get('name', 'N/A')} "
                    f"avec {len(node.get('children', []))} enfants "
                    f"et {len(node.get('outgoing_relations', []))} relations sortantes"
                )
                return node

            logger.warning(f"⚠️  Aucun nœud trouvé pour UID: {uid}")
            return {}

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du nœud {uid}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # taxonomy_dialog.py - Méthode corrigée
    def _get_level_1_relations(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION ALIGNÉE avec relation_import_widget.py
        Récupère les relations niveau 1 avec tri hiérarchiques/externes
        """
        if not uid or not self.current_central_name:
            return []

        cache_key = f"level1_{uid}"
        cached_data = self.query_cache.get(cache_key) if hasattr(self, 'query_cache') else None

        if cached_data:
            return cached_data

        relations = []
        dgraph_to_local = self._get_dgraph_to_local_mapping()

        self._show_progress(f"Chargement relations niveau 1...", 10)

        # ✅ 1. Récupérer détails du nœud avec relations complètes
        node_details = self._get_node_details(uid)

        if not node_details:
            self._hide_progress()
            return []

        central_name = self.current_central_name

        # ========== RELATIONS SORTANTES ==========
        self._update_progress(30, "Relations sortantes...")
        try:
            for rel in node_details.get('outgoing_relations', []):
                target_uid = rel.get('target_uid', '')

                if target_uid.startswith('0x'):
                    target_uid = dgraph_to_local.get(target_uid, target_uid)

                if target_uid.startswith('temp_'):
                    continue
                
                target_name = rel.get('target_name', '')
                if not target_name or target_name.strip() == '':
                    target_name = self._get_node_name_by_uid(target_uid)

                target_name = self.normalize_node_name(target_name)

                if target_name:
                    relations.append({
                        'source': central_name,
                        'target': target_name,
                        'relation_type': rel.get('relation_type', 'relation'),
                        'category': rel.get('category', 'custom'),
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement outgoing_relations: {e}")

        # ========== RELATIONS PARSÉES (JSON) ==========
        self._update_progress(50, "Relations parsées...")
        try:
            relations_json = node_details.get('relations', '{}')
            if isinstance(relations_json, str):
                parsed_relations = json.loads(relations_json) if relations_json else {}
            else:
                parsed_relations = relations_json or {}

            for rel_type, rel_list in parsed_relations.items():
                if not isinstance(rel_list, list):
                    continue

                for rel in rel_list:
                    target_name = self.normalize_node_name(rel.get('target', ''))
                    if target_name:
                        relations.append({
                            'source': central_name,
                            'target': target_name,
                            'relation_type': rel_type,
                            'category': 'parsed',
                            'is_analyzed': True,
                            'line': rel.get('line', 0)
                        })
        except Exception as e:
            logger.warning(f"Erreur parsing relations JSON: {e}")

        # ========== RELATIONS ENTRANTES ==========
        self._update_progress(70, "Relations entrantes...")
        try:
            for rel in node_details.get('incoming_relations', []):
                source_uid = rel.get('source_uid', '')

                if source_uid.startswith('0x'):
                    source_uid = dgraph_to_local.get(source_uid, source_uid)

                if source_uid.startswith('temp_'):
                    continue
                
                source_name = rel.get('source_name', '')
                if not source_name or source_name.strip() == '':
                    source_name = self._get_node_name_by_uid(source_uid)

                source_name = self.normalize_node_name(source_name)

                if source_name:
                    relations.append({
                        'source': source_name,
                        'target': central_name,
                        'relation_type': rel.get('relation_type', 'relation'),
                        'category': rel.get('category', 'custom'),
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement incoming_relations: {e}")

        # ========== HIÉRARCHIE (PARENTS) ==========
        self._update_progress(80, "Hiérarchie...")
        try:
            for parent in node_details.get('parents', []):
                parent_name = self.normalize_node_name(parent.get('name') or parent.get('label', ''))
                if parent_name:
                    relations.append({
                        'source': parent_name,
                        'target': central_name,
                        'relation_type': 'parent',
                        'category': 'hierarchy',
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement parents: {e}")

        # ========== HIÉRARCHIE (CHILDREN) ==========
        try:
            for child in node_details.get('children', []):
                child_name = self.normalize_node_name(child.get('name') or child.get('label', ''))
                if child_name:
                    relations.append({
                        'source': central_name,
                        'target': child_name,
                        'relation_type': 'child',
                        'category': 'hierarchy',
                        'is_analyzed': True
                    })
        except Exception as e:
            logger.error(f"Erreur traitement children: {e}")

        # ========== RELATIONS TYPE RELATION ==========
        self._update_progress(90, "Relations additionnelles...")
        try:
            relation_type_relations = self._get_relation_type_relations(uid)

            # Fusionner en évitant les doublons
            existing_keys = set()
            for rel in relations:
                key = (
                    rel.get('source'),
                    rel.get('target'),
                    rel.get('relation_type')
                )
                existing_keys.add(key)

            added_count = 0
            for rel in relation_type_relations:
                key = (
                    rel.get('source'),
                    rel.get('target'),
                    rel.get('relation_type')
                )

                if key not in existing_keys:
                    relations.append(rel)
                    existing_keys.add(key)
                    added_count += 1

            logger.info(f"  🔗 Relations type Relation: {len(relation_type_relations)} récupérées, {added_count} ajoutées")

        except Exception as e:
            logger.error(f"❌ Erreur récupération relations type Relation: {e}")
            import traceback
            traceback.print_exc()

        # ✅ TRI : hiérarchiques d'abord, puis externes
        def sort_relations(relations_list):
            hierarchical = []
            external = []

            for rel in relations_list:
                rel_type = rel.get('relation_type', '').lower()
                category = rel.get('category', '').lower()

                is_hierarchical = (
                    rel_type in ['parent', 'child', 'contains', 'belongs_to'] or
                    category in ['hierarchy', 'internal']
                )

                if is_hierarchical:
                    hierarchical.append(rel)
                else:
                    external.append(rel)

            return hierarchical + external

        relations = sort_relations(relations)

        # Sauvegarder dans le cache
        if hasattr(self, 'query_cache'):
            self.query_cache.set(cache_key, relations)

        self._hide_progress()

        # Log du résultat
        hierarchical_count = sum(1 for r in relations if r.get('category') in ['hierarchy', 'internal'])
        external_count = len(relations) - hierarchical_count

        logger.info(f"Niveau 1: {len(relations)} relations trouvées pour {central_name}")
        logger.info(f"  📊 {hierarchical_count} hiérarchiques (à gauche), {external_count} externes (à droite)")

        return relations
    
    def _get_dgraph_to_local_mapping(self):
        """Retourne le mapping Dgraph UID -> Local UID."""
        if not hasattr(self, 'dgraph_to_local') or not self.dgraph_to_local:
            self._load_uid_mappings()
        return getattr(self, 'dgraph_to_local', {})
    
    def _hide_progress(self):
        """Cache la progression."""
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.hide_loading()
        QtWidgets.QApplication.processEvents()
    
    def _show_progress(self, message: str, value: int):
        """Affiche la progression."""
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.update_progress(value, message)
        QtWidgets.QApplication.processEvents()

    def _update_progress(self, value: int, message: str = ""):
        """Met à jour la progression."""
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.update_progress(value, message)
        QtWidgets.QApplication.processEvents()
    
    def _get_relation_type_relations(self, uid: str) -> List[Dict]:
        """
        ✅ VERSION COMPLÈTE — corrige les appels manquants inter-fichiers.
        Récupère toutes les relations (calls/call) où le nœud est source ou cible,
        peu importe le fichier. Compatible avec le checkbox 1 (inter-fonctions globales).
        """
        if not uid or not self.dgraph_connector:
            logger.error("❌ Pas d'UID ou pas de connecteur")
            return []
    
        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 RÉCUPÉRATION RELATIONS TYPE RELATION")
        logger.info(f"  UID central: {uid}")
        logger.info(f"{'='*70}")
    
        # 1️⃣ — Récupérer les infos du nœud (nom et chemin)
        node_query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            path
            label
            id
          }}
        }}
        """
    
        node_result = self._execute_dgraph_query(node_query)
        if not node_result or 'node' not in node_result or not node_result['node']:
            logger.error(f"❌ Nœud {uid} introuvable")
            return []
    
        node_data = node_result['node'][0]
        node_name = node_data.get('name', '')
        node_path = node_data.get('path', '')
    
        # 2️⃣ — Construire les variantes de recherche
        search_variants = set()
        if node_name:
            search_variants.add(node_name)
            search_variants.add(os.path.basename(node_name))
            name_no_ext = os.path.splitext(node_name)[0]
            search_variants.add(name_no_ext)
            search_variants.add(os.path.basename(name_no_ext))
        if node_path:
            search_variants.add(node_path)
            search_variants.add(os.path.basename(node_path))
        search_variants = {v for v in search_variants if v and v.strip()}
    
        logger.info("🔍 Identifiants à rechercher:")
        for variant in sorted(search_variants):
            logger.info(f"   • {variant}")
    
        if not search_variants:
            logger.error("❌ Aucun identifiant valide")
            return []
    
        # 3️⃣ — Nouvelle requête UID : relations entrantes + sortantes globales
        query_by_uid = f"""
        {{
          related_calls(func: type(Relation)) @filter(
            (eq(relationType, "calls") OR eq(relationType, "call")) AND
            (uid_in(source, {uid}) OR uid_in(target, {uid}))
          ) {{
            uid
            relationType
            category
            line
            intraFile
            source {{
              uid
              name
              nodeType
              path
              sourcePath
            }}
            target {{
              uid
              name
              nodeType
              path
              targetPath
            }}
            sourceName
            sourceType
            sourcePath
            sourceDescription
            targetName
            targetType
            targetPath
            targetDescription
          }}
        }}
        """
    
        result_uid = self._execute_dgraph_query(query_by_uid)
        relations_by_uid = result_uid.get('related_calls', []) if result_uid else []
        logger.info(f"🎯 Mode UID: {len(relations_by_uid)} relations trouvées")
    
        # 4️⃣ — Recherche additionnelle par nom / path
        relations_by_name = []
        for variant in search_variants:
            escaped = variant.replace('"', '\\"')
            query_by_name = f"""
            {{
              related_calls(func: type(Relation)) @filter(
                (eq(relationType, "calls") OR eq(relationType, "call")) AND
                (regexp(sourcePath, /{escaped}/i) OR regexp(targetPath, /{escaped}/i))
              ) {{
                uid
                relationType
                category
                line
                intraFile
                source {{
                  uid
                  name
                  nodeType
                  path
                }}
                target {{
                  uid
                  name
                  nodeType
                  path
                }}
                sourceName
                sourceType
                sourcePath
                sourceDescription
                targetName
                targetType
                targetPath
                targetDescription
              }}
            }}
            """
            result_name = self._execute_dgraph_query(query_by_name)
            if result_name:
                relations_by_name.extend(result_name.get('related_calls', []))
    
        logger.info(f"🎯 Mode Nom/Path: {len(relations_by_name)} relations trouvées")
    
        # 5️⃣ — Fusion et dé-duplication
        all_raw_relations = relations_by_uid + relations_by_name
        seen_uids = set()
        unique_raw_relations = []
        for rel in all_raw_relations:
            rel_uid = rel.get('uid')
            if rel_uid and rel_uid not in seen_uids:
                seen_uids.add(rel_uid)
                unique_raw_relations.append(rel)
        logger.info(f"📦 {len(unique_raw_relations)} relations uniques après déduplication")
    
        # 6️⃣ — Traitement et validation
        relations_list = []
        seen_keys = set()
        for rel in unique_raw_relations:
            source_node = rel.get('source', {}) or {}
            target_node = rel.get('target', {}) or {}
    
            source_uid_rel = source_node.get('uid')
            target_uid_rel = target_node.get('uid')
    
            source_name = (
                source_node.get('name') or rel.get('sourceName') or rel.get('sourcePath', '')
            )
            target_name = (
                target_node.get('name') or rel.get('targetName') or rel.get('targetPath', '')
            )
    
            if not source_name or not target_name:
                continue
            
            source_name_norm = os.path.basename(source_name).strip()
            target_name_norm = os.path.basename(target_name).strip()
            if not source_name_norm or not target_name_norm or source_name_norm == target_name_norm:
                continue
            
            relation_type = rel.get('relationType', 'relation')
            unique_key = (
                source_uid_rel or source_name_norm,
                target_uid_rel or target_name_norm,
                relation_type
            )
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)
    
            relations_list.append({
                'source': source_name_norm,
                'source_uid': source_uid_rel or uid,
                'source_type': rel.get('sourceType', 'function'),
                'target': target_name_norm,
                'target_uid': target_uid_rel or uid,
                'target_type': rel.get('targetType', 'function'),
                'relation_type': relation_type,
                'category': rel.get('category', 'external'),
                'line': rel.get('line'),
                'intraFile': rel.get('intraFile', False)
            })
    
        logger.info(f"✅ {len(relations_list)} relations finales validées")
        logger.info(f"{'='*70}\n")
    
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

        # === PANNEAU ARBRE ===
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

        # === PANNEAU DESCRIPTION + SÉLECTION ===
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
        self.description_text.setMinimumHeight(200)
        # ✅ MODIFIÉ : Stretch factor 1 (égal à selected_list)
        desc_layout.addWidget(self.description_text, stretch=1)

        # Header avec bouton "Vider"
        selected_header_layout = QtWidgets.QHBoxLayout()
        selected_header_layout.setSpacing(8)

        selected_label = QtWidgets.QLabel("Éléments sélectionnés:")
        selected_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; background-color: white;"
        )
        selected_header_layout.addWidget(selected_label)

        selected_header_layout.addStretch()

        self.clear_selection_button = QtWidgets.QPushButton("🗑️ Vider")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.clear_selection_button.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                color: #666666;
                border: 1px solid #BDBDBD;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #BDBDBD;
                border-color: #9E9E9E;
            }
        """)
        self.clear_selection_button.setMaximumWidth(80)
        selected_header_layout.addWidget(self.clear_selection_button)

        desc_layout.addLayout(selected_header_layout)

        self.selected_list = QtWidgets.QListWidget()
        # ✅ MODIFIÉ : Hauteur minimum ajustée
        self.selected_list.setMinimumHeight(150)
        self.selected_list.setMaximumHeight(9999)  # ✅ Pas de limite haute
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
        # ✅ MODIFIÉ : Stretch factor 1 (égal à description_text)
        desc_layout.addWidget(self.selected_list, stretch=1)

        main_splitter.addWidget(desc_container)

        main_splitter.setSizes([400, 800])
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        layout.addWidget(main_splitter, stretch=1)

        # === BOUTONS VALIDATION ===
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
        """✅ VERSION AVEC LOADER : Validation avec affichage du chargement"""
        try:
            logger.info(f"=== ACCEPT appelé ===")
            logger.info(f"Nombre d'items dans selected_items: {len(self.selected_items)}")

            # ✅ AFFICHER LE LOADER IMMÉDIATEMENT
            self.loading_overlay.show_loading(
                "Validation en cours...",
                "Préparation des données sélectionnées"
            )

            # ✅ FORCER LE TRAITEMENT DES ÉVÉNEMENTS POUR AFFICHER LE LOADER
            QtWidgets.QApplication.processEvents()

            # ✅ Petit délai pour que le loader soit visible
            QTimer.singleShot(100, self._process_validation)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            self.loading_overlay.hide_loading()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur s'est produite lors de la validation:\n\n{str(e)}"
            )

    def _process_validation(self):
        """✅ NOUVEAU : Traite la validation en affichant la progression"""
        try:
            # ✅ ÉTAPE 1 : Vérifier la sélection
            self.loading_overlay.update_progress(
                10, 
                "Vérification de la sélection...",
                f"{len(self.selected_items)} élément(s) sélectionné(s)"
            )
            QtWidgets.QApplication.processEvents()

            if not self.selected_items:
                self.loading_overlay.hide_loading()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune sélection",
                    "Veuillez sélectionner au moins un élément avant de valider."
                )
                return

            # ✅ ÉTAPE 2 : Récupérer les taxonomies (fonction qui prend du temps)
            self.loading_overlay.update_progress(
                30,
                "Récupération des données...",
                "Chargement du code et des relations"
            )
            QtWidgets.QApplication.processEvents()

            taxonomy_data = self.get_selected_taxonomy()

            # ✅ ÉTAPE 3 : Validation des données
            self.loading_overlay.update_progress(
                80,
                "Validation des données...",
                f"{len(taxonomy_data)} taxonomies récupérées"
            )
            QtWidgets.QApplication.processEvents()

            logger.info(f"Taxonomies récupérées: {len(taxonomy_data)}")

            if not taxonomy_data:
                self.loading_overlay.hide_loading()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune donnée",
                    "Impossible de récupérer les données des éléments sélectionnés.\n"
                    "Veuillez réessayer."
                )
                return

            # ✅ ÉTAPE 4 : Émettre le signal
            self.loading_overlay.update_progress(
                95,
                "Finalisation...",
                "Émission du signal de validation"
            )
            QtWidgets.QApplication.processEvents()

            self.selection_validated.emit(taxonomy_data)

            logger.info(f"✅ Validation du dialogue: {len(taxonomy_data)} taxonomies sélectionnées")

            # ✅ ÉTAPE 5 : Masquer le loader et fermer
            self.loading_overlay.update_progress(
                100,
                "Terminé !",
                "Validation réussie"
            )

            # Petit délai avant de fermer pour que l'utilisateur voit "Terminé !"
            QTimer.singleShot(500, self._complete_validation)

        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de la validation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            self.loading_overlay.hide_loading()

            QtWidgets.QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur s'est produite lors de la validation:\n\n{str(e)}"
            )

    def _complete_validation(self):
        """✅ NOUVEAU : Finalise la validation et ferme le dialogue"""
        try:
            self.loading_overlay.hide_loading()

            # Appeler la méthode accept() du parent (QDialog)
            super(TaxonomyDialog, self).accept()

        except Exception as e:
            logger.error(f"❌ Erreur lors de la finalisation: {e}")
            self.loading_overlay.hide_loading()

    def resizeEvent(self, event):
        """Redimensionne l'overlay lors du redimensionnement du dialogue."""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(self.rect())

    def _add_item_to_selected_list(self, item: TaxonomyItem):
        """✅ CORRIGÉ : Ajoute un item à la liste avec espacement et bouton X"""
        if not isinstance(item, TaxonomyItem):
            return

        item_name = item.text(0)
        item_type = item.item_type

        # Vérifier si déjà présent
        for i in range(self.selected_list.count()):
            list_item = self.selected_list.item(i)
            if list_item and list_item.data(Qt.UserRole) == item_name:
                return

        icon_map = {
            'file': '📄', 'folder': '📁', 'function': '⚙️',
            'class': '🔷', 'variable': '🏷️', 'dependency': '🔗',
            'unknown': '❓'
        }
        icon = icon_map.get(item_type, '•')

        list_item = QtWidgets.QListWidgetItem()
        list_item.setData(Qt.UserRole, item_name)
        list_item.setData(Qt.UserRole + 1, item_type)
        list_item.setData(Qt.UserRole + 2, item)

        item_widget = QtWidgets.QWidget()
        item_layout = QtWidgets.QHBoxLayout(item_widget)
        item_layout.setContentsMargins(8, 6, 8, 6)
        item_layout.setSpacing(8)

        label = QtWidgets.QLabel(f"{icon} {item_name}")
        label.setStyleSheet("color: #333333; font-size: 12px;")
        item_layout.addWidget(label)
        item_layout.addStretch()

        remove_btn = QtWidgets.QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #999999;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #FFCDD2;
                color: #C62828;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_item_from_list(item))
        item_layout.addWidget(remove_btn)

        # ✅ MODIFIÉ : Hauteur fixe pour espacement vertical
        item_widget.setMinimumHeight(32)
        list_item.setSizeHint(QSize(item_widget.sizeHint().width(), 32))

        self.selected_list.addItem(list_item)
        self.selected_list.setItemWidget(list_item, item_widget)

        logger.info(f"✅ '{item_name}' ajouté à la liste ({len(self.selected_items)} total)")

    def _remove_item_from_list(self, item: TaxonomyItem):
        """✅ NOUVEAU : Retire un item de la liste et de la sélection"""
        if not isinstance(item, TaxonomyItem):
            return

        item_name = item.text(0)
        logger.info(f"🗑️ Retrait de '{item_name}' via bouton X")

        # Retirer de selected_items
        if item in self.selected_items:
            self.selected_items.remove(item)
            logger.info(f"  ✓ Retiré de selected_items ({len(self.selected_items)} restants)")

        # Retirer de la liste d'affichage
        for i in range(self.selected_list.count()):
            list_item = self.selected_list.item(i)
            if list_item and list_item.data(Qt.UserRole) == item_name:
                self.selected_list.takeItem(i)
                logger.info(f"  ✓ Retiré de selected_list")
                break

        item.setSelected(False)
        logger.info(f"  ✓ Désélectionné dans l'arbre")

        if len(self.selected_items) > 0:
            self._update_description_only()
        else:
            self.description_text.clear()
            self.description_text.setPlaceholderText("Sélectionnez un élément dans l'arbre")
            self.graph_update_signal.emit("", "", [], {})

        logger.info(f"✅ '{item_name}' complètement retiré")


    def _update_description_only(self):
        """✅ NOUVEAU : Met à jour uniquement la description"""
        if not self.selected_items:
            self.description_text.clear()
            return

        if len(self.selected_items) == 1:
            item = self.selected_items[0]
            self._display_single_item_summary(item)
        else:
            self._display_multiple_selection_summary()

        def _update_description_only(self):
            if not self.selected_items:
                self.description_text.clear()
                return

            if len(self.selected_items) == 1:
                item = self.selected_items[0]
                self._display_single_item_summary(item)
            else:
                self._display_multiple_selection_summary()

    def _display_single_item_summary(self, item: TaxonomyItem):
        """✅ NOUVEAU : Affiche un résumé rapide d'un item"""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D;'>📋 {item.text(0)}</h3>"
        details_html += f"<p><b>Type:</b> {item.item_type}</p>"
        details_html += f"<p><b>Niveau:</b> {item.level}</p>"
        details_html += "<p style='color: #666; font-style: italic; margin-top: 15px;'>"
        details_html += "Chargement des relations en cours..."
        details_html += "</p>"
        details_html += "</div>"
        self.description_text.setHtml(details_html)
    
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

    def _fetch_function_with_fallback(self, function_uid: str, function_name: str) -> Optional[Dict]:
        if not function_uid or not self.dgraph_connector:
            logger.error(f"❌ UID ou connecteur manquant pour {function_name}")
            return None
    
        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 RÉCUPÉRATION FONCTION : {function_name}")
        logger.info(f"   UID: {function_uid}")
        logger.info(f"{'='*70}")
    
        # ✅ Normaliser le nom
        normalized_name = self.normalize_node_name(function_name)
        search_name = normalized_name.split(':', 1)[-1].strip() if ':' in normalized_name else normalized_name
    
        # ✅ ÉTAPE 1 : Essayer avec l'UID direct
        query_by_uid = f"""
        {{
          by_uid(func: uid({function_uid})) {{
            uid
            name
            description
            line
            params
            returns
            path
            sourcePath
            codeContent
            nodeType
    
            # Parent fichier (si fonction globale)
            ~functions {{
              uid
              name
              path
              fileContents
              codeContent
            }}
    
            # Parent classe (si méthode)
            ~methods {{
              uid
              name
              description
    
              # Fichier de la classe
              ~classes {{
                uid
                name
                path
                fileContents
                codeContent
              }}
            }}
          }}
        }}
        """
    
        result = self._execute_dgraph_query(query_by_uid)
    
        if result and 'by_uid' in result and result['by_uid']:
            node_data = result['by_uid'][0]
    
            # Vérifier si on a plus que juste l'UID
            if len(node_data) > 1:
                code = node_data.get('codeContent', '').strip()
    
                if code:
                    logger.info(f"✅ Code récupéré avec UID direct ({len(code)} chars)")
                    return node_data
    
        # ✅ ÉTAPE 2 : FALLBACK - Recherche par nom
        logger.warning(f"🔄 UID {function_uid} vide, recherche par nom '{search_name}'...")
    
        query_by_name = f"""
        {{
          by_name(func: eq(name, "{search_name}")) {{
            uid
            name
            description
            line
            params
            returns
            path
            sourcePath
            codeContent
            nodeType
    
            ~functions {{
              uid
              name
              path
              fileContents
              codeContent
            }}
    
            ~methods {{
              uid
              name
    
              ~classes {{
                uid
                name
                path
                fileContents
                codeContent
              }}
            }}
          }}
        }}
        """
    
        result = self._execute_dgraph_query(query_by_name)
    
        if not result or 'by_name' not in result:
            logger.error("❌ Aucun résultat par nom")
            return None
    
        candidates = result['by_name']
    
        if not candidates:
            logger.error("❌ Aucune fonction trouvée")
            return None
    
        logger.info(f"📊 {len(candidates)} candidat(s) trouvé(s)")
    
        # ✅ Prendre le premier candidat avec du code
        for i, candidate in enumerate(candidates):
            code = candidate.get('codeContent', '').strip()
            candidate_uid = candidate.get('uid')
    
            logger.info(f"  Candidat {i+1}: UID={candidate_uid}, code={len(code) if code else 0} chars")
    
            if code:
                logger.info(f"✅ BON nœud trouvé ! UID correct: {candidate_uid} (au lieu de {function_uid})")
    
                # ✅ MISE À JOUR CACHE
                if hasattr(self, '_node_cache') and function_uid in self._node_cache:
                    old_item = self._node_cache[function_uid]
                    self._node_cache[candidate_uid] = old_item
                    old_item.item_data['uid'] = candidate_uid
                    logger.info(f"🔄 Cache mis à jour : {function_uid} → {candidate_uid}")
    
                return candidate
    
        logger.error(f"❌ {len(candidates)} nœud(s) trouvé(s) mais tous vides")
        return None
    
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
        """✅ VERSION CORRIGÉE : Force TOUJOURS la recherche de relations externes"""

        # Vider le cache
        if hasattr(self.graph_helper, 'query_cache'):
            self.graph_helper.query_cache.clear()
        logger.info("🗑️ Cache vidé avant nouvelle sélection")

        selected_items_tree = self.tree_widget.selectedItems()

        if not selected_items_tree:
            self.description_text.clear()
            self.selected_list.clear()
            self.selected_items.clear()
            self.graph_update_signal.emit("", "", [], {})
            return

        # ✅ ÉTAPE 1 : Afficher immédiatement tous les éléments sélectionnés
        newly_selected = []

        for item in selected_items_tree:
            if isinstance(item, TaxonomyItem):
                # Ajouter à la liste d'affichage si pas déjà présent
                self._add_item_to_selected_list(item)

                # Identifier les nouveaux éléments
                if item not in self.selected_items:
                    newly_selected.append(item)
                    self.selected_items.append(item)

        # ✅ ÉTAPE 2 : Mettre à jour la description (résumé rapide)
        if len(self.selected_items) == 1:
            self._display_single_item_summary(self.selected_items[0])
        else:
            self._display_multiple_selection_summary()

        # ✅ ÉTAPE 3 : Si nouveaux éléments, charger leurs relations en arrière-plan
        if not newly_selected:
            return

        last_item = newly_selected[-1]

        if not isinstance(last_item, TaxonomyItem):
            return

        data = last_item.item_data or {}
        item_type = last_item.item_type or "unknown"

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 CHARGEMENT RELATIONS : {last_item.text(0)}")
        logger.info(f"  Type: {item_type}")
        logger.info(f"{'='*70}")

        # ✅ MODE SÉLECTION MULTIPLE
        if len(self.selected_items) > 1:
            logger.info(f"\n{'='*70}")
            logger.info(f"🎯 MODE SÉLECTION MULTIPLE : {len(self.selected_items)} éléments")
            logger.info(f"{'='*70}")

            selected_data = []
            selected_uids = []

            for item in self.selected_items:
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

            # ✅ AFFICHER LE LOADER
            self.loading_overlay.show_loading(
                f"Recherche des relations multiples...",
                f"Analyse de {len(selected_uids)} éléments"
            )

            relations = self._get_multi_selection_relations(selected_uids)

            related_items = []
            for item_data in selected_data:
                related_items.append({
                    'name': item_data['name'],
                    'uid': item_data['uid'],
                    'type': item_data['type'],
                    'taxonomy_level': item_data['level'],
                    'search_depth': 1,
                    'relations': relations
                })

            QTimer.singleShot(300, self.loading_overlay.hide_loading)

            # ✅ SUPPRIMÉ : import local redondant
            QTimer.singleShot(100, lambda: self.graph_update_signal.emit(
                "Relations Multiples",
                "",
                related_items,
                self.project_data
            ))

            return

        # ✅ MODE SÉLECTION SIMPLE
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

        # ✅ AFFICHER LE LOADER
        self.loading_overlay.show_loading(
            f"Recherche des relations...",
            f"Analyse de {self.current_central_name}"
        )

        # ✅ LANCER LE THREAD DE CHARGEMENT
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()

        self.loader_thread = DataLoaderThread(self, self.current_central_uid, selected_level)

        # ✅ DÉCONNECTER les anciens signaux si existants (pour éviter les doublons)
        try:
            self.loader_thread.progress_update.disconnect()
        except:
            pass
        try:
            self.loader_thread.loading_complete.disconnect()
        except:
            pass
        try:
            self.loader_thread.loading_error.disconnect()
        except:
            pass
        
        # ✅ CONNECTER les signaux
        self.loader_thread.progress_update.connect(self._on_loading_progress)
        self.loader_thread.loading_complete.connect(self._on_loading_complete)
        self.loader_thread.loading_error.connect(self._on_loading_error)

        self.loader_thread.start()

    def _display_multiple_selection_summary(self):
        """✅ NOUVEAU : Affiche un résumé de la sélection multiple"""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D;'>🕸️ Sélection Multiple</h3>"
        details_html += f"<p><b>{len(self.selected_items)} éléments sélectionnés :</b></p>"
        details_html += "<ul style='margin: 10px 0; padding-left: 20px;'>"

        for item in self.selected_items:
            if isinstance(item, TaxonomyItem):
                icon = self._get_icon_for_type(item.item_type)
                details_html += f"<li>{icon} {item.text(0)} <i>({item.item_type})</i></li>"

        details_html += "</ul>"
        details_html += "<p style='color: #666; font-style: italic; margin-top: 15px;'>"
        details_html += "Chargement des relations entre ces éléments..."
        details_html += "</p>"
        details_html += "</div>"
        self.description_text.setHtml(details_html)

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

    def clear_selection(self):
        """✅ MODIFIÉ : Vide complètement la sélection"""
        self.tree_widget.clearSelection()
        self.selected_items.clear()
        self.selected_list.clear()
        self.description_text.clear()
        self.description_text.setPlaceholderText("Sélectionnez un élément dans l'arbre")
        self.current_central_uid = None
        self.current_central_name = None
        self.graph_update_signal.emit("", "", [], {})

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
    
    def remove_selected_item(self, item_to_remove):
        if not isinstance(item_to_remove, TaxonomyItem):
            return

        item_name = item_to_remove.text(0)
        logger.info(f"🗑️ Retrait de '{item_name}' de la sélection")

        # Retirer de selected_items
        if item_to_remove in self.selected_items:
            self.selected_items.remove(item_to_remove)

        # Retirer de la liste d'affichage
        for i in range(self.selected_list.count()):
            list_item = self.selected_list.item(i)
            if list_item and list_item.data(Qt.UserRole) == item_name:
                self.selected_list.takeItem(i)
                break
            
        # Déselectionner dans l'arbre
        item_to_remove.setSelected(False)

        # Mettre à jour le graphe si nécessaire
        if len(self.selected_items) > 0:
            self._on_selection_changed()
        else:
            self.clear_selection()

        logger.info(f"'{item_name}' retiré, {len(self.selected_items)} éléments restants")


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
        """✅ MODIFIÉ : Met à jour la progression du chargement."""
        self.loading_overlay.update_progress(value, message, detail)


    @pyqtSlot(dict)
    def _on_loading_complete(self, results):
        """✅ MODIFIÉ : Appelé quand le chargement est terminé."""
        relations_list = results.get('relations', [])
        related_items = results.get('related_items', [])

        logger.info(f"✅ Chargement terminé: {len(relations_list)} relations")

        # ✅ Masquer le loader avec un petit délai pour fluidité
        QTimer.singleShot(300, self.loading_overlay.hide_loading)

        # ✅ Mettre à jour l'affichage des détails
        selected_items_tree = self.tree_widget.selectedItems()
        if selected_items_tree:
            last_item = selected_items_tree[-1]
            if isinstance(last_item, TaxonomyItem):
                self._display_tree_item_details(last_item, relations_list)

        # ✅ Émettre le signal pour mettre à jour le graphe
        self.graph_update_signal.emit(
            self.current_central_name,
            self.current_central_uid,
            related_items,
            self.project_data
        )

    @pyqtSlot(str)
    def _on_loading_error(self, error_message):
        """✅ MODIFIÉ : Appelé en cas d'erreur pendant le chargement."""
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

    def _build_project_tree(self):
        """
        ✅ CORRIGÉ : Construit l'arbre du projet avec tous les clusters
        """
        self.tree_widget.clear()
        if not self.current_project_data:
            return

        cm = self.current_project_data.get('clusterManagement', {})

        self._node_cache.clear()
        self._name_cache.clear()
        self._uid_set.clear()

        seen_uids = set()
        clusters = cm.get('clusters', [])
        total_clusters = len(clusters)

        logger.info(f"🗂️ Construction de l'arbre avec {total_clusters} clusters")

        for cluster_idx, cluster in enumerate(clusters):
            cluster_uid = cluster.get('uid')
            if cluster_uid in seen_uids:
                continue
            seen_uids.add(cluster_uid)

            self._build_cluster_tree(cluster, cluster_idx, total_clusters)

        self.tree_widget.expandAll()
        self._load_taxonomy_structure()
        logger.info(f"✅ Arbre construit: {len(self._uid_set)} éléments uniques")

    def     get_selected_taxonomy(self):
        """
        ✅ VERSION FINALE : Retourne les taxonomies avec CODE COMPLET + PATH
        """
        logger.info(f"=== get_selected_taxonomy appelé ===")
    
        taxonomy_data = []
        selected_level = self.level_combo.currentData()
        total_items = len(self.selected_items)
    
        if total_items == 0:
            logger.warning("⚠️ selected_items est vide !")
            return taxonomy_data
    
        # ✅ AFFICHER OVERLAY
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
                f"Récupération du code pour {item.text(0)}"
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
            
            # ✅ RECHARGEMENT DONNÉES COMPLÈTES
            complete_data = self._fetch_complete_node_data(temp_uid)
    
            if complete_data:
                # ✅ FUSIONNER les données rechargées avec les données existantes
                data.update(complete_data)
                logger.info(f"✅ Code rechargé pour {temp_name}")
                
                # ✅ NOUVEAU : Récupérer et ajouter le path si manquant
                if not data.get('path') and not data.get('sourcePath') and not data.get('full_path'):
                    function_path = self._get_function_path(temp_uid, temp_name)
                    if function_path:
                        data['path'] = function_path
                        data['sourcePath'] = function_path
                        data['full_path'] = function_path
                        logger.info(f"   📂 Path ajouté: {function_path}")
                    else:
                        logger.warning(f"   ⚠️ Path non trouvé pour {temp_name}")
                
                # 📊 DIAGNOSTIC DÉTAILLÉ
                code = data.get('codeContent', '') or data.get('fileContents', '')
                classes = data.get('classes', [])
                functions = data.get('functions', [])
                path = data.get('path') or data.get('sourcePath') or data.get('full_path', 'N/A')
    
                logger.info(f"   📦 Taille code FICHIER: {len(code)} chars")
                logger.info(f"   📊 {len(classes)} classes, {len(functions)} fonctions")
                logger.info(f"   📂 Path: {path}")
    
                # ✅ VÉRIFIER CODE DES CLASSES
                for cls in classes:
                    cls_code = cls.get('codeContent', '')
                    methods = cls.get('methods', [])
    
                    if cls_code:
                        logger.info(f"      ✓ Classe '{cls.get('name')}': {len(cls_code)} chars")
                    else:
                        logger.warning(f"      ⚠️ Classe '{cls.get('name')}': AUCUN code classe")
    
                    # ✅ VÉRIFIER CODE DES MÉTHODES
                    for method in methods:
                        method_code = method.get('codeContent', '')
                        if method_code:
                            logger.info(f"         ✓ Méthode '{method.get('name')}': {len(method_code)} chars")
                        else:
                            logger.warning(f"         ⚠️ Méthode '{method.get('name')}': AUCUN code méthode")
    
                # ✅ VÉRIFIER CODE DES FONCTIONS
                for func in functions:
                    func_code = func.get('codeContent', '')
                    if func_code:
                        logger.info(f"      ✓ Fonction '{func.get('name')}': {len(func_code)} chars")
                    else:
                        logger.warning(f"      ⚠️ Fonction '{func.get('name')}': AUCUN code fonction")
    
            else:
                logger.error(f"❌ ÉCHEC rechargement pour {temp_name}")
                # ✅ FALLBACK : Essayer de récupérer au moins le path
                if not data.get('path') and not data.get('sourcePath') and not data.get('full_path'):
                    function_path = self._get_function_path(temp_uid, temp_name)
                    if function_path:
                        data['path'] = function_path
                        data['sourcePath'] = function_path
                        data['full_path'] = function_path
                        logger.info(f"   📂 Path ajouté (fallback): {function_path}")
    
            # ✅ RÉCUPÉRATION RELATIONS
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
    
                        # ✅ NOUVEAU : Récupérer le path pour les éléments liés aussi
                        node_path = None
                        if node_uid:
                            # Essayer depuis le cache d'abord
                            if hasattr(self, '_node_cache') and node_uid in self._node_cache:
                                cached_item = self._node_cache[node_uid]
                                node_path = (cached_item.item_data.get('path') or 
                                           cached_item.item_data.get('sourcePath') or 
                                           cached_item.item_data.get('full_path'))
                            
                            # Si pas dans le cache, récupérer via _get_function_path
                            if not node_path:
                                node_path = self._get_function_path(node_uid, node_name)
    
                        related_items.append({
                            'name': node_name,
                            'uid': node_uid,
                            'type': rel.get(f'{key}_type', 'dependency'),
                            'taxonomy_level': item_level,
                            'path': node_path,  # ✅ NOUVEAU
                            'sourcePath': node_path,  # ✅ NOUVEAU
                            'full_path': node_path  # ✅ NOUVEAU
                        })
    
            # ✅ AJOUTER À taxonomy_data
            taxonomy_entry = {
                'name': temp_name,
                'uid': temp_uid,
                'type': item.item_type,
                'level': item_level,
                'search_depth': selected_level,
                'data': data,  # ✅ Contient maintenant le code complet + path
                'related': related_items,
                'relations': relations_list,
                # ✅ NOUVEAU : Ajouter le path au niveau racine pour accès facile
                'path': data.get('path') or data.get('sourcePath') or data.get('full_path'),
                'sourcePath': data.get('sourcePath') or data.get('path') or data.get('full_path'),
                'full_path': data.get('full_path') or data.get('path') or data.get('sourcePath')
            }
            
            taxonomy_data.append(taxonomy_entry)
    
        # ✅ FINALISATION
        self.loading_overlay.update_progress(
            100, 
            "Terminé !", 
            f"{len(taxonomy_data)} taxonomies préparées"
        )
    
        QTimer.singleShot(500, self.loading_overlay.hide_loading)
    
        # 📊 STATISTIQUES FINALES
        total_code = 0
        items_with_code = 0
        items_with_path = 0
    
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 STATISTIQUES FINALES")
        logger.info(f"{'='*70}")
    
        for tax in taxonomy_data:
            item_name = tax['name']
            item_type = tax['type']
            code = tax['data'].get('codeContent', '') or tax['data'].get('fileContents', '')
            path = tax.get('path') or tax.get('sourcePath') or tax.get('full_path', 'N/A')
            
            if code:
                total_code += len(code)
                items_with_code += 1
            
            if path and path != 'N/A':
                items_with_path += 1
            
            if item_type in ['function', 'method', 'class']:
                if code:
                    logger.info(f"✅ {item_name}: {len(code)} chars de code | Path: {path}")
                else:
                    logger.error(f"❌ {item_name}: AUCUN code (problème) | Path: {path}")
    
        logger.info(f"\n📊 RÉSUMÉ :")
        logger.info(f"   • {len(taxonomy_data)} taxonomies retournées")
        logger.info(f"   • {items_with_code}/{len(taxonomy_data)} avec code")
        logger.info(f"   • {items_with_path}/{len(taxonomy_data)} avec path")
        logger.info(f"   • Code total: {total_code:,} caractères")
        logger.info(f"{'='*70}\n")
    
        return taxonomy_data
    
    def _get_function_path(self, function_uid: str, function_name: str) -> Optional[str]:
        """
        ✅ NOUVEAU : Récupère le path complet d'une fonction/méthode
        Retourne le chemin du fichier source de la fonction
        """
        if not function_uid or not self.dgraph_connector:
            logger.warning(f"⚠️ UID ou connecteur manquant pour {function_name}")
            return None
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📂 RÉCUPÉRATION PATH : {function_name}")
        logger.info(f"   UID: {function_uid}")
        logger.info(f"{'='*70}")
        
        # ✅ STRATÉGIE 1 : Chercher dans le cache local
        if hasattr(self, '_node_cache') and function_uid in self._node_cache:
            cached_item = self._node_cache[function_uid]
            path = (cached_item.item_data.get('path') or 
                   cached_item.item_data.get('sourcePath') or 
                   cached_item.item_data.get('full_path', ''))
            
            if path:
                logger.info(f"   ✅ Cache local: {path}")
                return self._normalize_path(path)
        
        # ✅ STRATÉGIE 2 : Requête Dgraph avec fallback
        normalized_name = self.normalize_node_name(function_name)
        search_name = normalized_name.split(':', 1)[-1].strip() if ':' in normalized_name else normalized_name
        
        # 2.1 : Essayer avec l'UID direct
        query_by_uid = f"""
        {{
          by_uid(func: uid({function_uid})) {{
            uid
            name
            path
            sourcePath
            full_path
            
            # Si c'est une fonction globale
            ~functions {{
              uid
              name
              path
              sourcePath
              full_path
            }}
            
            # Si c'est une méthode de classe
            ~methods {{
              uid
              name
              path
              
              # Remonter au fichier parent
              ~classes {{
                uid
                name
                path
                sourcePath
                full_path
              }}
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query_by_uid)
        
        if result and 'by_uid' in result and result['by_uid']:
            node_data = result['by_uid'][0]
            
            # Vérifier path direct
            path = (node_data.get('path') or 
                   node_data.get('sourcePath') or 
                   node_data.get('full_path', ''))
            
            if path:
                logger.info(f"   ✅ Dgraph (UID direct): {path}")
                return self._normalize_path(path)
            
            # Vérifier fichier parent (pour fonction globale)
            parent_files = node_data.get('~functions', [])
            if parent_files:
                parent_path = (parent_files[0].get('path') or 
                              parent_files[0].get('sourcePath') or 
                              parent_files[0].get('full_path', ''))
                if parent_path:
                    logger.info(f"   ✅ Dgraph (parent fichier): {parent_path}")
                    return self._normalize_path(parent_path)
            
            # Vérifier fichier parent (pour méthode de classe)
            parent_classes = node_data.get('~methods', [])
            if parent_classes:
                parent_class = parent_classes[0]
                class_files = parent_class.get('~classes', [])
                if class_files:
                    file_path = (class_files[0].get('path') or 
                                class_files[0].get('sourcePath') or 
                                class_files[0].get('full_path', ''))
                    if file_path:
                        logger.info(f"   ✅ Dgraph (parent classe): {file_path}")
                        return self._normalize_path(file_path)
        
        # 2.2 : Fallback par nom
        logger.warning(f"🔄 UID {function_uid} n'a pas donné de path, recherche par nom '{search_name}'...")
        
        query_by_name = f"""
        {{
          by_name(func: eq(name, "{search_name}")) {{
            uid
            name
            path
            sourcePath
            full_path
            
            ~functions {{
              uid
              name
              path
              sourcePath
              full_path
            }}
            
            ~methods {{
              uid
              name
              path
              
              ~classes {{
                uid
                name
                path
                sourcePath
                full_path
              }}
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query_by_name)
        
        if result and 'by_name' in result:
            candidates = result['by_name']
            
            for candidate in candidates:
                # Essayer path direct
                path = (candidate.get('path') or 
                       candidate.get('sourcePath') or 
                       candidate.get('full_path', ''))
                
                if path:
                    logger.info(f"   ✅ Dgraph (nom - direct): {path}")
                    return self._normalize_path(path)
                
                # Essayer parent fichier
                parent_files = candidate.get('~functions', [])
                if parent_files:
                    parent_path = (parent_files[0].get('path') or 
                                  parent_files[0].get('sourcePath') or 
                                  parent_files[0].get('full_path', ''))
                    if parent_path:
                        logger.info(f"   ✅ Dgraph (nom - parent fichier): {parent_path}")
                        return self._normalize_path(parent_path)
                
                # Essayer parent classe
                parent_classes = candidate.get('~methods', [])
                if parent_classes:
                    parent_class = parent_classes[0]
                    class_files = parent_class.get('~classes', [])
                    if class_files:
                        file_path = (class_files[0].get('path') or 
                                    class_files[0].get('sourcePath') or 
                                    class_files[0].get('full_path', ''))
                        if file_path:
                            logger.info(f"   ✅ Dgraph (nom - parent classe): {file_path}")
                            return self._normalize_path(file_path)
        
        # ✅ STRATÉGIE 3 : Relations Dgraph
        logger.warning(f"🔄 Dernière tentative via relations...")
        
        escaped = search_name.replace('"', '\\"')
        query_relations = f"""
        {{
          by_source(func: type(Relation)) @filter(regexp(sourceName, /{escaped}/i)) {{
            sourceName
            sourcePath
          }}
          
          by_target(func: type(Relation)) @filter(regexp(targetName, /{escaped}/i)) {{
            targetName
            targetPath
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query_relations)
        
        if result:
            # Vérifier sourcePath
            for rel in result.get('by_source', []):
                source_name = rel.get('sourceName', '')
                source_path = rel.get('sourcePath', '')
                
                if source_name and source_path:
                    clean_source = source_name.replace('Function: ', '').replace('Method: ', '').strip()
                    if clean_source == search_name or search_name in clean_source:
                        path = self._extract_file_path_from_relation(source_path)
                        if path:
                            logger.info(f"   ✅ Relations (source): {path}")
                            return self._normalize_path(path)
            
            # Vérifier targetPath
            for rel in result.get('by_target', []):
                target_name = rel.get('targetName', '')
                target_path = rel.get('targetPath', '')
                
                if target_name and target_path:
                    clean_target = target_name.replace('Function: ', '').replace('Method: ', '').strip()
                    if clean_target == search_name or search_name in clean_target:
                        path = self._extract_file_path_from_relation(target_path)
                        if path:
                            logger.info(f"   ✅ Relations (target): {path}")
                            return self._normalize_path(path)
        
        logger.error(f"❌ Impossible de trouver le path pour {function_name}")
        return None
    
    def _normalize_path(self, path: str) -> str:
        """
        ✅ Normalise un path (enlève les suffixes de type, uniformise les séparateurs)
        """
        if not path:
            return ""
        
        # Enlever les suffixes de type comme "/Function:xxx"
        if '/Function:' in path:
            path = path.split('/Function:')[0]
        if '/Method:' in path:
            path = path.split('/Method:')[0]
        if '/Class:' in path:
            path = path.split('/Class:')[0]
        if '/Variable:' in path:
            path = path.split('/Variable:')[0]
        
        # Uniformiser les séparateurs
        path = path.replace('\\', '/')
        
        # Enlever les slashes en début/fin
        path = path.strip('/')
        
        return path
    
    def _extract_file_path_from_relation(self, relation_path: str) -> Optional[str]:
        """
        ✅ Extrait le path du fichier depuis un path de relation
        Ex: "src/ui/widgets/graph.py/Function:draw" -> "src/ui/widgets/graph.py"
        """
        if not relation_path:
            return None
        
        # Supprimer les éléments après Function:, Method:, etc.
        clean_path = relation_path
        for marker in ['/Function:', '/Method:', '/Class:', '/Variable:']:
            if marker in clean_path:
                clean_path = clean_path.split(marker)[0]
                break
        
        # Si c'est un fichier valide
        if clean_path and ('.' in os.path.basename(clean_path)):
            return clean_path
        
        return None
    
    def _extract_filename_from_relation_path(self, source_path: str) -> Optional[str]:
        """
        ✅ Extrait le nom du fichier depuis un path de relation
        """
        file_path = self._extract_file_path_from_relation(source_path)
        if file_path:
            return os.path.basename(file_path)
        return None

    def _fetch_file_complete_data(self, file_uid: str) -> Optional[Dict]:
        """
        🆕 RECHARGE TOUTES LES DONNÉES D'UN NŒUD AVEC LE CODE COMPLET
        """
        if not file_uid or not self.dgraph_connector:
            return None
    
    def _fetch_complete_node_data(self, uid: str) -> Optional[Dict]:
        """
        ✅ VERSION AMÉLIORÉE : Utilise le fallback pour les fonctions/méthodes
        """
        if not uid or not self.dgraph_connector:
            return None

        logger.info(f"🔍 Récupération données complètes pour UID: {uid}")

        # ✅ D'abord, identifier le type de nœud
        type_query = f"""
        {{
          check(func: uid({uid})) {{
            uid
            name
            nodeType
            dgraph.type
          }}
        }}
        """

        type_result = self._execute_dgraph_query(type_query)

        if not type_result or 'check' not in type_result or not type_result['check']:
            logger.warning(f"⚠️ Nœud {uid} introuvable")
            return None

        node_info = type_result['check'][0]
        node_name = node_info.get('name', '')
        node_type = node_info.get('nodeType', '')
        dgraph_types = node_info.get('dgraph.type', [])

        logger.info(f"   Type: {node_type}")
        logger.info(f"   Dgraph.type: {dgraph_types}")

        # ✅ SI C'EST UNE FONCTION/MÉTHODE → Utiliser le fallback robuste
        is_function = (
            node_type in ['function', 'method'] or
            'Function' in dgraph_types or
            'Method' in dgraph_types
        )

        if is_function:
            logger.info(f"🎯 Fonction/Méthode détectée, utilisation du fallback robuste...")
            return self._fetch_function_with_fallback(uid, node_name)

        # ✅ SINON → Utiliser la requête standard (pour fichiers/classes)
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            nodeType
            path
            description
            fileContents
            codeContent
            docstring
            line
        
            # Classes (directes + inverses)
            classes {{
              uid
              name
              description
              line
              codeContent
        
              methods {{
                uid
                name
                description
                line
                codeContent
                
                # 🆕 AJOUT : Variables de méthode
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
            }}
        
            ~classes {{
              uid
              name
              description
              line
              codeContent
        
              methods {{
                uid
                name
                description
                line
                codeContent
                
                # 🆕 AJOUT : Variables de méthode
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
            }}
        
            # Fonctions (directes + inverses)
            functions {{
              uid
              name
              description
              line
              codeContent
              
              # 🆕 AJOUT : Variables de fonction
              variables {{
                uid
                name
                description
                line
                var_type
                scope
              }}
            }}
        
            ~functions {{
              uid
              name
              description
              line
              codeContent
              
              # 🆕 AJOUT : Variables de fonction
              variables {{
                uid
                name
                description
                line
                var_type
                scope
              }}
            }}
        
            # Variables
            variables {{
              uid
              name
              description
              line
            }}
        
            ~variables {{
              uid
              name
              description
              line
            }}
          }}
        }}
        """

        try:
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()

            result = self.dgraph_connector._parse_response(resp)

            if result and 'node' in result and result['node']:
                node_data = result['node'][0]

                # Fusionner classes
                direct_classes = node_data.get('classes', [])
                inverse_classes = node_data.get('~classes', [])
                all_classes = direct_classes + inverse_classes

                if all_classes:
                    node_data['classes'] = all_classes
                    node_data.pop('~classes', None)

                # Fusionner fonctions
                direct_functions = node_data.get('functions', [])
                inverse_functions = node_data.get('~functions', [])
                all_functions = direct_functions + inverse_functions

                if all_functions:
                    node_data['functions'] = all_functions
                    node_data.pop('~functions', None)

                # Fusionner variables
                direct_variables = node_data.get('variables', [])
                inverse_variables = node_data.get('~variables', [])
                all_variables = direct_variables + inverse_variables

                if all_variables:
                    node_data['variables'] = all_variables
                    node_data.pop('~variables', None)

                # Diagnostic
                code = node_data.get('codeContent', '') or node_data.get('fileContents', '')
                classes = node_data.get('classes', [])
                functions = node_data.get('functions', [])

                logger.info(f"   📦 Code: {len(code)} chars")
                logger.info(f"   🗂️ {len(classes)} classes, {len(functions)} fonctions")

                return node_data

            return None

        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return None

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