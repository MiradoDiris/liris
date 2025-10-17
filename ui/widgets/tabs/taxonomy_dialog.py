# taxonomy_dialog.py - Version intégrée avec GraphWidget et Loader Professionnel
from datetime import datetime, timedelta
import os
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from typing import List, Dict, Optional
from utils.dgraph_connector import LirisDgraphConnector 

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

        # Timer pour l'animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate)

        # État
        self.current_message = "Chargement..."
        self.current_progress = 0
        self.current_detail = ""

        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container compact
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

        # Message de statut
        self.message_label = QtWidgets.QLabel(self.current_message)
        self.message_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #A23B2D;
        """)
        self.message_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.message_label)

        # Barre de progression
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

        # Pourcentage
        self.percentage_label = QtWidgets.QLabel("0%")
        self.percentage_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #A23B2D;
        """)
        self.percentage_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.percentage_label)

        # Détail (nombre d'éléments)
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
    
    progress_update = pyqtSignal(int, str, str)  # value, message, detail
    loading_complete = pyqtSignal(dict)  # résultats
    loading_error = pyqtSignal(str)  # message d'erreur
    
    def __init__(self, dialog, uid, level):
        super().__init__()
        self.dialog = dialog
        self.uid = uid
        self.level = level
        self.is_cancelled = False
    
    def run(self):
        """Exécute le chargement des données."""
        try:
            # Étape 1: Chargement des mappings UID (10%)
            if self.is_cancelled:
                return
            self.progress_update.emit(10, "Initialisation...", "Chargement des mappings UID")
            self.dialog._load_uid_mappings()
            
            # Étape 2: Récupération des détails du nœud (30%)
            if self.is_cancelled:
                return
            self.progress_update.emit(30, "Analyse du nœud...", f"Récupération des détails pour {self.dialog.current_central_name}")
            node_details = self.dialog._get_node_details(self.uid)
            
            # Étape 3: Chargement des relations selon le niveau (40-90%)
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
                
            elif self.level == 3:
                if self.is_cancelled:
                    return
                self.progress_update.emit(50, "Chargement...", "Récupération des relations de niveau 1")
                
                if self.is_cancelled:
                    return
                self.progress_update.emit(60, "Chargement...", "Récupération des relations de niveau 2")
                
                if self.is_cancelled:
                    return
                self.progress_update.emit(80, "Chargement...", "Récupération des relations de niveau 3 (peut prendre du temps)")
                relations_list = self.dialog._get_level_3_relations(self.uid)
                self.progress_update.emit(90, "Chargement...", f"{len(relations_list)} relations trouvées")
            
            # Étape 4: Construction des related_items (95%)
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
            
            # Étape 5: Terminé (100%)
            if self.is_cancelled:
                return
            self.progress_update.emit(100, "Terminé !", f"{len(relations_list)} relations chargées")
            
            # Émettre les résultats
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

class QueryCache:
    """Système de cache pour les requêtes Dgraph avec expiration."""
    
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Dict]:
        """Récupère une valeur du cache si elle n'a pas expiré."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                logger.info(f"Cache HIT pour: {key[:50]}...")
                return data
            else:
                logger.info(f"Cache EXPIRED pour: {key[:50]}...")
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        """Stocke une valeur dans le cache."""
        self.cache[key] = (value, datetime.now())
        logger.info(f"Cache SET pour: {key[:50]}...")
    
    def clear(self):
        """Vide le cache."""
        self.cache.clear()
        logger.info("Cache vidé")
    
    def get_stats(self) -> str:
        """Retourne les statistiques du cache."""
        return f"Cache: {len(self.cache)} entrées"

class TaxonomyDialog(QtWidgets.QDialog):
    """Dialogue pour sélectionner les taxonomies (fichiers/fonctions) avec niveaux"""
    
    # Signal pour mettre à jour le graphe dans le panneau principal
    graph_update_signal = pyqtSignal(str, str, list, dict)  # (central_name, central_uid, related_items, project_data)
    selection_validated = pyqtSignal(list)
    
    def __init__(self, project_data, dgraph_connector, parent=None):
        super().__init__(parent)
        self.project_data = project_data
        self.dgraph_connector = dgraph_connector or LirisDgraphConnector(auto_reset=False)
        self.selected_items = []
        
        # Système de cache
        self.query_cache = QueryCache(ttl_seconds=600)
        
        # Cache pour les mappings UID
        self.dgraph_to_local = {}
        self.local_to_dgraph = {}
        
        # Variables pour le nœud central
        self.current_central_uid = None
        self.current_central_name = None
        
        # Thread de chargement
        self.loader_thread = None
        
        self.setWindowTitle("Définir les Bornes - Taxonomies")
        self.resize(900, 600)
        self.setModal(True)
        
        self._init_ui()
        
        # Créer l'overlay de chargement
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.hide()
        
        # Charger la taxonomie avec loader
        self._load_taxonomy_with_loader()

    def _load_taxonomy_with_loader(self):
        """Charge la taxonomie avec affichage du loader."""
        self.loading_overlay.show_loading(
            "Chargement de la taxonomie...",
            "Récupération de la structure du projet"
        )
        
        # Simuler des étapes de progression
        QTimer.singleShot(100, lambda: self.loading_overlay.update_progress(30, detail="Analyse des clusters"))
        QTimer.singleShot(200, lambda: self.loading_overlay.update_progress(60, detail="Construction de l'arbre"))
        QTimer.singleShot(300, lambda: self.loading_overlay.update_progress(90, detail="Finalisation"))
        QTimer.singleShot(400, self._complete_taxonomy_loading)
    
    def _complete_taxonomy_loading(self):
        """Complète le chargement de la taxonomie."""
        self._load_taxonomy()
        self._load_uid_mappings()
        self.loading_overlay.update_progress(100, "Terminé !", "Taxonomie chargée")
        QTimer.singleShot(500, self.loading_overlay.hide_loading)

    def normalize_node_name(self, name: str) -> str:
        """Normalise le nom d'un nœud en enlevant l'extension et le chemin."""
        if not name or not isinstance(name, str):
            logger.warning(f"Invalid name input: {name}")
            return f"unnamed_{id(name)}"

        name = name.strip()
        if not name or name.lower() == 'n/a':
            logger.warning(f"Empty or 'n/a' name: {name}")
            return f"unnamed_{id(name)}"

        base = os.path.basename(name)
        name_without_ext = os.path.splitext(base)[0]
        normalized = name_without_ext.strip()
        
        if not normalized:
            logger.warning(f"Normalized name is empty: {name}")
            return f"unnamed_{id(name)}"
        
        return normalized

    def _load_uid_mappings(self):
        """Charge les mappings UID depuis Dgraph avec cache."""
        cache_key = "uid_mappings"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            self.dgraph_to_local = cached_data.get('dgraph_to_local', {})
            self.local_to_dgraph = cached_data.get('local_to_dgraph', {})
            logger.info(f"Mappings UID chargés depuis cache: {len(self.dgraph_to_local)} entrées")
            return
        
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
            
            self.query_cache.set(cache_key, {
                'dgraph_to_local': self.dgraph_to_local,
                'local_to_dgraph': self.local_to_dgraph
            })
        
        logger.info(f"Mappings UID chargés: {len(self.dgraph_to_local)} entrées")

    def _execute_dgraph_query(self, query: str) -> Optional[Dict]:
        """Exécute une requête Dgraph (identique à relation_import_widget.py)."""
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
        """Récupère les détails complets d'un nœud avec cache."""
        if not uid:
            return {}
        
        cache_key = f"node_details_{uid}"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        logger.info(f"Récupération détails pour UID: {uid}")
        
        query = f"""
        {{
          node(func: uid({uid})) {{
            uid
            name
            label
            level
            nodeType
            
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
            }}
            
            children: ~parents {{
              uid
              name
              label
            }}
            
            clusters {{
              uid
              name
            }}
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'node' in result and result['node']:
            node = result['node'][0]
            self.query_cache.set(cache_key, node)
            logger.info(f"Nœud trouvé: {node.get('name', 'N/A')} avec {len(node.get('outgoing_relations', []))} relations sortantes")
            return node
        
        logger.warning(f"Aucun nœud trouvé pour UID: {uid}")
        return {}

    def _get_level_1_relations(self, uid: str) -> List[Dict]:
        """Récupère toutes les relations directes (Niveau 1) - Identique à relation_import_widget."""
        if not uid or not self.current_central_name:
            return []

        cache_key = f"level1_{uid}"
        cached_data = self.query_cache.get(cache_key)
        
        if cached_data:
            return cached_data

        relations = []
        dgraph_to_local = self.dgraph_to_local

        node_details = self._get_node_details(uid)

        if not node_details:
            return []

        central_name = self.current_central_name

        # 1. Relations sortantes CUSTOM
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

        # 2. Relations PARSÉES
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

        # 3. Relations entrantes CUSTOM
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

        # 4. HIÉRARCHIE - Parents
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

        # 5. HIÉRARCHIE - Enfants
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

        # 6. Relations type(Relation)
        query = f"""
        {{
          relations(func: type(Relation)) @filter(uid_in(source, {uid}) OR uid_in(target, {uid})) {{
            uid
            relationType
            source {{
              uid
              name
              label
            }}
            target {{
              uid
              name
              label
            }}
          }}
        }}
        """
        result = self._execute_dgraph_query(query)
        
        if result and 'relations' in result:
            for rel in result['relations']:
                source_node = rel.get('source', {})
                target_node = rel.get('target', {})
                
                source_name = self.normalize_node_name(
                    source_node.get('name') or source_node.get('label', '')
                )
                target_name = self.normalize_node_name(
                    target_node.get('name') or target_node.get('label', '')
                )
                
                if source_name and target_name:
                    relations.append({
                        'source': source_name,
                        'target': target_name,
                        'relation_type': rel.get('relationType', 'relation'),
                        'category': 'custom',
                        'is_analyzed': True
                    })

        self.query_cache.set(cache_key, relations)
        
        logger.info(f"Niveau 1: {len(relations)} relations trouvées pour {central_name}")
        return relations

    def _get_node_name_by_uid(self, uid: str) -> str:
        """Récupère le nom d'un nœud par son UID avec cache."""
        if not uid:
            return ""
        
        cache_key = f"node_name_{uid}"
        cached_name = self.query_cache.get(cache_key)
        
        if cached_name:
            return cached_name
        
        query = f"""
        {{
          q(func: uid({uid})) {{
            name
            label
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        
        if result and 'q' in result and result['q']:
            node = result['q'][0]
            name = node.get('name') or node.get('label', '')
            self.query_cache.set(cache_key, name)
            return name
        
        return ""

    def _get_level_2_relations(self, uid: str) -> List[Dict]:
        """Niveau 2: Niveau 1 + relations des nœuds connectés."""
        if not uid or not self.current_central_name:
            return []
        
        level1_relations = self._get_level_1_relations(uid)
        
        connected_names = set()
        for rel in level1_relations:
            connected_names.add(rel['source'])
            connected_names.add(rel['target'])
        
        connected_names.discard(self.current_central_name)
        
        connected_uids_names = set()
        for name in connected_names:
            node_uid = self._get_node_uid_by_name(name)
            if node_uid:
                connected_uids_names.add((node_uid, name))
        
        all_relations = list(level1_relations)
        
        original_central_uid = self.current_central_uid
        original_central_name = self.current_central_name
        
        for connected_uid, node_name in connected_uids_names:
            self.current_central_uid = connected_uid
            self.current_central_name = node_name
            connected_rels = self._get_level_1_relations(connected_uid)
            
            for rel in connected_rels:
                rel['is_analyzed'] = False
            all_relations.extend(connected_rels)
        
        self.current_central_uid = original_central_uid
        self.current_central_name = original_central_name
        
        logger.info(f"Niveau 2: {len(all_relations)} relations trouvées")
        return all_relations

    def _get_level_3_relations(self, uid: str) -> List[Dict]:
        """Niveau 3: Niveau 2 + relations des relations."""
        if not uid or not self.current_central_name:
            return []
        
        level_2_relations = self._get_level_2_relations(uid)
        
        all_node_names = set()
        for rel in level_2_relations:
            all_node_names.add(rel['source'])
            all_node_names.add(rel['target'])
        
        level2_uids_names = set()
        for node_name in all_node_names:
            node_uid = self._get_node_uid_by_name(node_name)
            if node_uid:
                level2_uids_names.add((node_uid, node_name))
        
        all_relations = list(level_2_relations)
        
        original_central_uid = self.current_central_uid
        original_central_name = self.current_central_name
        
        for node_uid, node_name in level2_uids_names:
            if node_name == self.current_central_name:
                continue
            
            self.current_central_uid = node_uid
            self.current_central_name = node_name
            connected_rels = self._get_level_1_relations(node_uid)
            
            for rel in connected_rels:
                rel['is_analyzed'] = False
            all_relations.extend(connected_rels)
        
        self.current_central_uid = original_central_uid
        self.current_central_name = original_central_name
        
        logger.info(f"Niveau 3: {len(all_relations)} relations trouvées")
        return all_relations

    def _get_node_uid_by_name(self, node_name: str) -> str:
        """Récupère l'UID d'un nœud par son nom avec cache."""
        if not node_name:
            return None

        cache_key = f"uid_by_name_{node_name}"
        cached_uid = self.query_cache.get(cache_key)
        
        if cached_uid:
            return cached_uid

        query = f"""
        {{
          q(func: has(name)) @filter(eq(name, "{node_name}")) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid

        query = f"""
        {{
          q(func: has(label)) @filter(eq(label, "{node_name}")) {{
            uid
          }}
        }}
        """

        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q']:
            uid = result['q'][0].get('uid')
            self.query_cache.set(cache_key, uid)
            return uid

        logger.warning(f"UID non trouvé pour: {node_name}")
        return None

    def _init_ui(self):
        """Initialise l'interface du dialogue avec graphe intégré"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("background-color: white;")

        # En-tête
        header = QtWidgets.QLabel("Sélectionnez les fichiers/fonctions à implémenter")
        header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #A23B2D;
            padding: 10px;
            background-color: white;
        """)
        layout.addWidget(header)

        # Sélecteur de niveau
        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel("Niveau de profondeur:")
        level_label.setStyleSheet("font-weight: bold; background-color: white;")

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItem("Niveau 1: Relations directes uniquement", 1)
        self.level_combo.addItem("Niveau 2: Relations + enfants (récursif)", 2)
        #self.level_combo.addItem("Niveau 3: Niveau 2 + enfants des enfants", 3)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        self.level_combo.setStyleSheet("background-color: white;")

        level_layout.addWidget(level_label)
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # Zone principale divisée en 3 colonnes
        main_splitter = QtWidgets.QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("background-color: white;")

        # ===== COLONNE GAUCHE: Arbre de taxonomie =====
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

        # ===== COLONNE DROITE: Description et Éléments sélectionnés =====
        desc_container = QtWidgets.QWidget()
        desc_container.setStyleSheet("background-color: white;")
        desc_layout = QtWidgets.QVBoxLayout(desc_container)
        desc_layout.setContentsMargins(0, 0, 0, 0)

        # Section Description (affiche détails du nœud cliqué dans le graphe)
        desc_label = QtWidgets.QLabel("Description:")
        desc_label.setStyleSheet("font-weight: bold; font-size: 13px; background-color: white;")
        desc_layout.addWidget(desc_label)

        self.description_text = QtWidgets.QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlaceholderText(
            "Sélectionnez un élément dans l'arbre ou cliquez sur un nœud dans le graphe"
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

        # Section Éléments sélectionnés
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

        # Boutons d'action
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
            logger.info(f"Nombre d'items dans selected_list: {self.selected_list.count()}")
            
            # DÉBOGAGE : Afficher le contenu de selected_items
            for idx, item in enumerate(self.selected_items):
                if isinstance(item, TaxonomyItem):
                    logger.info(f"  [{idx}] {item.text(0)} (type: {item.item_type})")
            
            # Récupérer les taxonomies sélectionnées avec tous leurs détails
            taxonomy_data = self.get_selected_taxonomy()
            
            logger.info(f"Taxonomies récupérées: {len(taxonomy_data)}")
            
            if not taxonomy_data:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aucune sélection",
                    f"Veuillez sélectionner au moins un élément avant de valider.\n\n"
                    f"Debug: selected_items={len(self.selected_items)}, "
                    f"selected_list={self.selected_list.count()}"
                )
                return
            
            # Émettre le signal avec les données complètes
            self.selection_validated.emit(taxonomy_data)
            
            logger.info(f"✅ Validation du dialogue: {len(taxonomy_data)} taxonomies sélectionnées")
            
            # Appeler le accept() parent pour fermer le dialogue
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
        # Vérifier si déjà dans la liste visuelle
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            if item and item.data(Qt.UserRole) == node_name:
                # Déjà présent, on le met en surbrillance
                self.selected_list.setCurrentItem(item)
                return

        # Ajouter à la liste visuelle avec icône
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

        # CORRECTION CRITIQUE : Chercher le TaxonomyItem correspondant dans l'arbre
        taxonomy_item = self._find_taxonomy_item_by_name(node_name)
        
        if taxonomy_item:
            # Ajouter le vrai TaxonomyItem à selected_items
            if taxonomy_item not in self.selected_items:
                self.selected_items.append(taxonomy_item)
                logger.info(f"✅ TaxonomyItem '{node_name}' ajouté à selected_items")
        else:
            # Si pas trouvé dans l'arbre, créer un TaxonomyItem temporaire
            logger.warning(f"⚠️ TaxonomyItem non trouvé pour '{node_name}', création temporaire")
            temp_item = TaxonomyItem(None, node_name, node_type, {'name': node_name, 'uid': None}, 0)
            if temp_item not in self.selected_items:
                self.selected_items.append(temp_item)

        logger.info(f"Nœud '{node_name}' ajouté à la liste de sélection (total: {len(self.selected_items)})")

    def _load_taxonomy(self):
        """Charge la taxonomie du projet"""
        self.tree_widget.clear()
        
        if not self.project_data:
            return
        
        cm = self.project_data.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_name = f"Cluster: {cluster.get('name', 'Cluster')}"
            cluster_type = "folder" if not self._has_extension(cluster.get('name', '')) else "file"
            cluster_item = TaxonomyItem(
                self.tree_widget,
                cluster_name,
                cluster_type,
                cluster,
                0
            )
            
            self._add_labels_with_relations(cluster_item, cluster.get('root_labels', []))
        
        self.tree_widget.expandAll()
    
    def _add_labels_with_relations(self, parent_item, labels, visited=None):
        """Ajoute les labels avec leurs relations"""
        if visited is None:
            visited = set()
    
        for label in labels:
            label_id = label.get('uid') or label.get('id') or label.get('name')
            if not label_id or label_id in visited:
                continue
            visited.add(label_id)
    
            label_name = label.get('name', label.get('label', 'Item'))
            item_type = self._detect_item_type(label, label_name, parent_item)
    
            label_item = TaxonomyItem(
                parent_item,
                label_name,
                item_type,
                label,
                parent_item.level + 1 if hasattr(parent_item, 'level') else 0
            )
    
            functions = label.get('functions', [])
            for func in functions:
                func_name = func.get('name', 'function')
                func_type = 'function'
                TaxonomyItem(
                    label_item,
                    func_name,
                    func_type,
                    func,
                    label_item.level + 1
                )
    
            if label.get('parents'):
                self._add_labels_with_relations(label_item, label['parents'], visited)
            if label.get('children'):
                self._add_labels_with_relations(label_item, label['children'], visited)
    
    def _has_extension(self, filename):
        """Vérifie si le nom a une extension de fichier"""
        return bool(os.path.splitext(filename)[1])
    
    def _on_level_changed(self, index):
        """Gère le changement de niveau - Recharge les relations"""
        selected_level = self.level_combo.currentData()
        logger.info(f"Niveau {selected_level} sélectionné")
        
        # Recharger les relations pour l'item actuellement sélectionné
        self._on_selection_changed()
    
    @pyqtSlot()
    def _on_selection_changed(self):
        """Gère le changement de sélection dans l'arbre - Charge les données avec loader."""
        selected_items = self.tree_widget.selectedItems()

        if not selected_items:
            self.description_text.clear()
            self.selected_list.clear()
            # Signal pour clear le graphe
            self.graph_update_signal.emit("", "", [], {})
            return

        # Traiter le dernier item sélectionné
        last_item = selected_items[-1]
        if isinstance(last_item, TaxonomyItem):
            data = last_item.item_data
            selected_level = self.level_combo.currentData()

            # Définir le nœud central
            self.current_central_uid = data.get('uid')
            self.current_central_name = self.normalize_node_name(
                data.get('name') or data.get('label', 'N/A')
            )

            if not self.current_central_uid:
                if self.current_central_name:
                    self.current_central_uid = self._get_node_uid_by_name(self.current_central_name)
                if not self.current_central_uid:
                    self.description_text.setHtml(
                        "<b style='color: #D32F2F;'>⚠ Erreur:</b> UID du nœud introuvable"
                    )
                    return

            # Annuler le thread précédent s'il existe
            if self.loader_thread and self.loader_thread.isRunning():
                self.loader_thread.cancel()
                self.loader_thread.wait()

            # Créer et démarrer le thread de chargement
            self.loader_thread = DataLoaderThread(self, self.current_central_uid, selected_level)
            self.loader_thread.progress_update.connect(self._on_loading_progress)
            self.loader_thread.loading_complete.connect(self._on_loading_complete)
            self.loader_thread.loading_error.connect(self._on_loading_error)

            # Afficher le loader
            self.loading_overlay.show_loading(
                f"Chargement des relations...",
                f"Analyse de {self.current_central_name} (Niveau {selected_level})"
            )

            # Démarrer le chargement
            self.loader_thread.start()
    
    @pyqtSlot(int, str, str)
    def _on_loading_progress(self, value, message, detail):
        """Met à jour la progression du chargement."""
        self.loading_overlay.update_progress(value, message, detail)
    
    @pyqtSlot(dict)
    def _on_loading_complete(self, results):
        """Appelé quand le chargement est terminé."""
        relations_list = results.get('relations', [])
        related_items = results.get('related_items', [])
        node_details = results.get('node_details', {})
        
        logger.info(f"Chargement terminé: {len(relations_list)} relations")
        
        # Masquer le loader après un court délai
        QTimer.singleShot(500, self.loading_overlay.hide_loading)
        
        # Afficher les détails
        selected_items_tree = self.tree_widget.selectedItems()
        if selected_items_tree:
            last_item = selected_items_tree[-1]
            if isinstance(last_item, TaxonomyItem):
                self._display_tree_item_details(last_item, relations_list)
                
                # CORRECTION : Ajouter l'item sélectionné dans l'arbre à selected_items
                if last_item not in self.selected_items:
                    self.selected_items.append(last_item)
                    logger.info(f"✅ Item '{last_item.text(0)}' ajouté à selected_items depuis l'arbre")
        
        # Émettre le signal pour mettre à jour le graphe
        self.graph_update_signal.emit(
            self.current_central_name,
            self.current_central_uid,
            related_items,
            self.project_data
        )
        
        # Ajouter à la liste visuelle des sélections
        if selected_items_tree:
            last_item = selected_items_tree[-1]
            if isinstance(last_item, TaxonomyItem):
                self._add_to_selected_list(self.current_central_name, last_item.item_type)
    
    @pyqtSlot(str)
    def _on_loading_error(self, error_message):
        """Appelé en cas d'erreur pendant le chargement."""
        logger.error(f"Erreur de chargement: {error_message}")
        self.loading_overlay.hide_loading()
        
        # Afficher l'erreur
        QtWidgets.QMessageBox.critical(
            self,
            "Erreur de chargement",
            f"Une erreur s'est produite lors du chargement des données:\n\n{error_message}"
        )
    
    def _find_taxonomy_item_by_name(self, node_name: str):
        """
        NOUVELLE MÉTHODE : Parcourt récursivement l'arbre pour trouver un TaxonomyItem par son nom.
        """
        def search_item(parent):
            """Recherche récursive dans l'arbre."""
            child_count = parent.childCount() if hasattr(parent, 'childCount') else parent.topLevelItemCount()
            
            for i in range(child_count):
                child = parent.child(i) if hasattr(parent, 'child') else parent.topLevelItem(i)
                
                if isinstance(child, TaxonomyItem):
                    # Comparer le nom (normaliser pour la comparaison)
                    child_name = child.text(0)
                    if child_name == node_name or self.normalize_node_name(child_name) == node_name:
                        return child
                    
                    # Rechercher dans les enfants
                    if child.childCount() > 0:
                        result = search_item(child)
                        if result:
                            return result
            
            return None
        
        # Commencer la recherche depuis la racine
        return search_item(self.tree_widget)

    def _display_tree_item_details(self, item: TaxonomyItem, relations_list: List[Dict]):
        """Affiche les détails d'un item de l'arbre dans la zone description."""
        details_html = "<div style='line-height: 1.6;'>"
        details_html += f"<h3 style='color: #A23B2D; margin: 0 0 10px 0;'>{item.text(0)}</h3>"

        # Informations de base
        details_html += f"<p style='margin: 4px 0;'>"
        details_html += f"<b>Type:</b> <span style='color: #555;'>{item.item_type}</span> | "
        details_html += f"<b>Niveau:</b> <span style='color: #555;'>{item.level}</span>"
        details_html += f"</p>"

        # Statistiques des relations
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

        # Aperçu des relations sortantes
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
        """Retourne les taxonomies sélectionnées avec leurs relations selon le niveau."""
        logger.info(f"=== get_selected_taxonomy appelé ===")
        logger.info(f"selected_items count: {len(self.selected_items)}")
        
        taxonomy_data = []
        selected_level = self.level_combo.currentData()
        
        total_items = len(self.selected_items)
        
        if total_items == 0:
            logger.warning("⚠️ selected_items est vide !")
            # Essayer de récupérer depuis la liste visuelle
            logger.info("Tentative de récupération depuis selected_list...")
            for i in range(self.selected_list.count()):
                list_item = self.selected_list.item(i)
                node_name = list_item.data(Qt.UserRole)
                node_type = list_item.data(Qt.UserRole + 1)
                
                logger.info(f"  Recherche de '{node_name}' dans l'arbre...")
                taxonomy_item = self._find_taxonomy_item_by_name(node_name)
                
                if taxonomy_item:
                    self.selected_items.append(taxonomy_item)
                    logger.info(f"  ✅ Trouvé et ajouté: {node_name}")
                else:
                    logger.warning(f"  ⚠️ Non trouvé: {node_name}")
            
            total_items = len(self.selected_items)
            
            if total_items == 0:
                logger.error("❌ Impossible de récupérer les items sélectionnés")
                return taxonomy_data
        
        # Afficher le loader pour la récupération finale
        self.loading_overlay.show_loading(
            "Préparation des taxonomies...",
            "Récupération des relations pour les éléments sélectionnés"
        )
        
        for idx, item in enumerate(self.selected_items):
            if isinstance(item, TaxonomyItem):
                data = item.item_data
                item_level = item.level
                
                # Mettre à jour la progression
                progress = int((idx / total_items) * 100)
                self.loading_overlay.update_progress(
                    progress,
                    f"Traitement {idx + 1}/{total_items}",
                    f"Analyse de {item.text(0)}"
                )
                
                # Définir temporairement comme central pour récupérer ses relations
                temp_uid = data.get('uid')
                temp_name = self.normalize_node_name(data.get('name', data.get('label', '')))
                
                if not temp_uid:
                    # Essayer de récupérer l'UID par le nom
                    temp_uid = self._get_node_uid_by_name(temp_name)
                    if not temp_uid:
                        logger.warning(f"⚠️ UID manquant pour {temp_name}, ignoré")
                        continue
                
                # Sauvegarder les valeurs actuelles
                saved_uid = self.current_central_uid
                saved_name = self.current_central_name
                
                # Définir temporairement
                self.current_central_uid = temp_uid
                self.current_central_name = temp_name
                
                # Récupérer les relations
                relations_list = []
                if selected_level == 1:
                    relations_list = self._get_level_1_relations(temp_uid)
                elif selected_level == 2:
                    relations_list = self._get_level_2_relations(temp_uid)
                elif selected_level == 3:
                    relations_list = self._get_level_3_relations(temp_uid)
                
                # Restaurer les valeurs
                self.current_central_uid = saved_uid
                self.current_central_name = saved_name
                
                # Construire related_items
                related_items = []
                seen_nodes = set([temp_name])
                
                for rel in relations_list:
                    source_name = rel.get('source', '')
                    if source_name and source_name not in seen_nodes:
                        seen_nodes.add(source_name)
                        source_uid = self._get_node_uid_by_name(source_name)
                        related_items.append({
                            'name': source_name,
                            'uid': source_uid,
                            'type': 'dependency',
                            'taxonomy_level': item_level
                        })
                    
                    target_name = rel.get('target', '')
                    if target_name and target_name not in seen_nodes:
                        seen_nodes.add(target_name)
                        target_uid = self._get_node_uid_by_name(target_name)
                        related_items.append({
                            'name': target_name,
                            'uid': target_uid,
                            'type': 'dependency',
                            'taxonomy_level': item_level
                        })
                
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
                
                logger.info(f"✅ Taxonomie préparée - {temp_name}: {len(relations_list)} relations, {len(related_items)} items liés")
        
        # Finaliser
        self.loading_overlay.update_progress(100, "Terminé !", f"{len(taxonomy_data)} taxonomies préparées")
        QTimer.singleShot(500, self.loading_overlay.hide_loading)
        
        logger.info(f"=== get_selected_taxonomy terminé: {len(taxonomy_data)} taxonomies ===")
        return taxonomy_data

    def _detect_item_type(self, item_data, item_name, parent_item):
        """Détecte intelligemment le type d'item"""
        if self._has_extension(item_name):
            return "file"

        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "folder":
            return "folder"

        if parent_item and isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "file":
            if item_data.get('type') == 'class' or self._is_class_name(item_name):
                return "class"
            if self._is_function_name(item_name):
                return "function"
            if self._is_variable_name(item_name):
                return "variable"
            return "function"

        return "folder"

    def _is_class_name(self, name):
        """Détecte si un nom correspond à une classe"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        class_keywords = [
            'public class', 'private class', 'protected class',
            'abstract class', 'static class', 'final class',
            'sealed class', 'internal class',
            'public ', 'private ', 'protected ', 'abstract ',
            'class ', 'interface ', 'trait ', 'struct '
        ]

        for keyword in class_keywords:
            if name_lower.startswith(keyword):
                return True

        if (name_stripped and 
            name_stripped[0].isupper() and 
            '(' not in name_stripped and 
            '=' not in name_stripped and
            not name_stripped.isupper()):
            return True

        return False

    def _is_function_name(self, name):
        """Détecte si un nom correspond à une fonction"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        function_keywords = ['def ', 'function ', 'fn ', 'func ', 'async def ', 'async function ']
        for keyword in function_keywords:
            if name_lower.startswith(keyword):
                return True

        if '(' in name_stripped and ')' in name_stripped:
            if not self._is_variable_declaration(name_stripped):
                return True

        if name_stripped and name_stripped[0].islower():
            if not self._is_variable_declaration(name_stripped):
                if '=' not in name_stripped.split('(')[0] and ':' not in name_stripped.split('(')[0]:
                    return True

        return False

    def _is_variable_name(self, name):
        """Détecte si un nom correspond à une variable"""
        if not name:
            return False

        name_lower = name.lower().strip()
        name_stripped = name.strip()

        variable_keywords = [
            'var ', 'let ', 'const ', 'val ', 'final ',
            'static ', 'public static ', 'private static ',
            'protected static ', 'readonly '
        ]

        for keyword in variable_keywords:
            if name_lower.startswith(keyword):
                if '(' not in name_stripped or '=' in name_stripped:
                    return True

        if self._is_variable_declaration(name_stripped):
            return True

        if name_stripped.isupper() and '_' in name_stripped:
            return True

        return False

    def _is_variable_declaration(self, name):
        """Détecte une déclaration de variable typée"""
        if not name:
            return False

        name_stripped = name.strip()

        if ':' in name_stripped and '(' not in name_stripped.split(':')[0]:
            parts = name_stripped.split(':')
            if len(parts) >= 2:
                type_part = parts[1].strip().split('=')[0].strip()

                if type_part:
                    primitive_types = [
                        'int', 'str', 'float', 'bool', 'double', 'long',
                        'string', 'boolean', 'number', 'any', 'void',
                        'list', 'dict', 'tuple', 'set', 'array', 'object',
                        'List', 'Dict', 'Tuple', 'Set', 'Array', 'Object'
                    ]

                    type_name = type_part.split('[')[0].split('<')[0].strip()
                    if type_name in primitive_types or (type_name and type_name[0].isupper()):
                        return True

        if '=' in name_stripped:
            before_equal = name_stripped.split('=')[0].strip().lower()
            if 'def' not in before_equal and 'function' not in before_equal and 'fn' not in before_equal:
                if not name_stripped.replace('=', '').strip().endswith('='):
                    return True

        return False
    
    def closeEvent(self, event):
        """Fermeture propre."""
        # Annuler le thread de chargement s'il existe
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()
        
        if self.dgraph_connector:
            self.dgraph_connector.close()
        
        super().closeEvent(event)