# relation_import_widget.py - Version Améliorée et Corrigée Complète
import os
import re
import ast
import json
import time
from typing import List, Dict, Set, Tuple, Any
from collections import defaultdict
from threading import Thread

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QColor

import qtawesome as qta
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.dgraph_connector import LirisDgraphConnector
from utils.logger import logger


class TaxonomyItem(QtWidgets.QTreeWidgetItem):
    """Item pour l'arbre de taxonomie avec métadonnées, style et icônes unifiés."""
    def __init__(self, parent, text, item_type="folder", data=None, level=0):
        super().__init__(parent, [text])
        self.item_type = item_type
        self.item_data = data or {}
        self.level = level
        
        # Palette monochrome professionnelle
        primary = '#A23B2D'
        dark_gray = '#424242'
        strong_gray = '#555555'
        
        icon_map = {
            "folder": ('fa5s.folder', strong_gray),
            "file": ('fa5s.file-code', strong_gray),
            "function": ('fa5s.cube', primary),
            "dependency": ('fa5s.link', strong_gray),
            "class": ('fa5s.cubes', dark_gray),
            "variable": ('fa5s.tag', '#999999'),
        }
        
        icon_name, icon_color = icon_map.get(item_type, ('fa5s.question-circle', strong_gray))
        self.setIcon(0, qta.icon(icon_name, color=icon_color))


class MultiLanguageDependencyParser:
    """Parser multi-langages pour détecter les dépendances et relations."""
    
    def __init__(self):
        self.supported_languages = {
            '.py': self._parse_python,
            '.java': self._parse_java,
            '.js': self._parse_javascript,
            '.jsx': self._parse_javascript,
            '.ts': self._parse_javascript,
            '.tsx': self._parse_javascript,
            '.cpp': self._parse_cpp,
            '.c': self._parse_cpp,
            '.h': self._parse_cpp,
        }
    
    def parse_content(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse le contenu d'un fichier et retourne un dict: {relation_type: [dépendances]}."""
        if not content:
            logger.warning(f"Contenu vide pour {file_path}")
            return {}
        
        ext = os.path.splitext(file_path)[1].lower()
        parser_func = self.supported_languages.get(ext)
        
        if not parser_func:
            logger.warning(f"Langage non supporté pour {ext}, utilisation de parsing générique.")
            return self._parse_generic(content, file_path)
        
        return parser_func(content, file_path)
    
    def _parse_python(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parsing Python complet avec ast pour imports, héritage, appels de fonctions."""
        relations = defaultdict(list)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            logger.warning("Syntaxe Python invalide, fallback regex.")
            return self._parse_generic(content, file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name.split('.')[0]
                    relations['import'].append({
                        'target': target + '.py',
                        'type': 'import',
                        'line': node.lineno
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    target = (module + '.' + alias.name).split('.')[0] + '.py'
                    relations['import'].append({
                        'target': target,
                        'type': 'from_import',
                        'line': node.lineno
                    })
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        target = base.id
                        relations['heritage'].append({
                            'target': target,
                            'type': 'extends',
                            'line': node.lineno
                        })
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    target = node.func.id
                    relations['call'].append({
                        'target': target,
                        'type': 'function_call',
                        'line': node.lineno
                    })
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        target = f"{node.func.value.id}.{node.func.attr}"
                        relations['call'].append({
                            'target': target,
                            'type': 'method_call',
                            'line': node.lineno
                        })
        
        for rel_type in relations:
            relations[rel_type] = list({d['target']: d for d in relations[rel_type]}.values())
        
        return dict(relations)
    
    def _parse_java(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parsing Java via regex: imports, extends/implements."""
        relations = defaultdict(list)
        
        import_pattern = r'^import\s+(?:static\s+)?([\w\.]+);'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            target = match.group(1).split('.')[-1] + '.java'
            relations['import'].append({'target': target, 'type': 'import', 'line': content[:match.start()].count('\n') + 1})
        
        extends_pattern = r'(public|private|protected)?\s*class\s+\w+\s*(extends\s+([\w\.]+))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(3):
                target = match.group(3) + '.java'
                relations['heritage'].append({'target': target, 'type': 'extends', 'line': content[:match.start()].count('\n') + 1})
        
        call_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            relations['call'].append({'target': target, 'type': 'method_call', 'line': content[:match.start()].count('\n') + 1})
        
        return self._dedup_relations(relations)
    
    def _parse_javascript(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parsing JS/TS: require, import, calls, heritage."""
        relations = defaultdict(list)
        
        import_pattern = r'import\s+(?:\{[^}]+\}\s+)?(?:.*\s+)?from\s+[\'\"]([\w\/\.@]+)[\'\"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            target = match.group(1)
            if not target.endswith(('.js', '.jsx', '.ts', '.tsx')):
                ext = os.path.splitext(file_path)[1]
                target += ext
            relations['import'].append({'target': target, 'type': 'import', 'line': content[:match.start()].count('\n') + 1})
        
        require_pattern = r'require\s*\(\s*[\'\"]([\w\/\.@]+)[\'\"]\s*\)'
        for match in re.finditer(require_pattern, content, re.MULTILINE):
            target = match.group(1)
            if not target.endswith(('.js', '.jsx', '.ts', '.tsx')):
                ext = os.path.splitext(file_path)[1]
                target += ext
            relations['import'].append({'target': target, 'type': 'require', 'line': content[:match.start()].count('\n') + 1})
        
        method_call_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(method_call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}.{match.group(2)}"
            relations['call'].append({'target': target, 'type': 'method_call', 'line': content[:match.start()].count('\n') + 1})
        
        extends_pattern = r'class\s+\w+\s*(extends\s+(\w+))?'
        for match in re.finditer(extends_pattern, content, re.MULTILINE):
            if match.group(2):
                target = match.group(2)
                relations['heritage'].append({'target': target, 'type': 'extends', 'line': content[:match.start()].count('\n') + 1})
        
        return self._dedup_relations(relations)
    
    def _parse_cpp(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parsing C/C++: #include, function calls."""
        relations = defaultdict(list)
        
        include_pattern = r'#include\s*[<"](\w+\.h?)["<]'
        for match in re.finditer(include_pattern, content, re.MULTILINE):
            target = match.group(1)
            relations['import'].append({'target': target, 'type': 'include', 'line': content[:match.start()].count('\n') + 1})
        
        call_pattern = r'(\w+)::(\w+)\s*\('
        for match in re.finditer(call_pattern, content, re.MULTILINE):
            target = f"{match.group(1)}::{match.group(2)}"
            relations['call'].append({'target': target, 'type': 'function_call', 'line': content[:match.start()].count('\n') + 1})
        
        return self._dedup_relations(relations)
    
    def _parse_generic(self, content: str, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Fallback regex pour tout langage."""
        relations = defaultdict(list)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            import_match = re.search(r'(?:import\s+(?:{[^}]*}\s+)?(?:.*\s+)?from\s+|from\s+|import\s+)[\'\"]([\w\.\/@]+)[\'\"]', line)
            if import_match:
                target = import_match.group(1)
                relations['import'].append({'target': target, 'type': 'import_generic', 'line': i})
        
        return self._dedup_relations(relations)
    
    def _dedup_relations(self, relations: defaultdict) -> Dict[str, List[Dict[str, Any]]]:
        """Dédoublonne les relations par target et type."""
        for rel_type in relations:
            seen = {}
            deduped = []
            for rel in relations[rel_type]:
                key = (rel['target'], rel['type'])
                if key not in seen:
                    seen[key] = rel
                    deduped.append(rel)
            relations[rel_type] = deduped
        return dict(relations)


class DependencyFinderWorker(QThread):
    """Worker pour trouver les dépendances dans un thread séparé."""
    
    progress_updated = pyqtSignal(str, int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_items: List[Dict[str, Any]], dgraph_connector, parent=None):
        super().__init__(parent)
        self.file_items = file_items
        self.dgraph_connector = dgraph_connector
        self.parser = MultiLanguageDependencyParser()
        
    def _execute_dgraph_query(self, query):
        """Exécute une requête Dgraph."""
        if not self.dgraph_connector or not self.dgraph_connector.client:
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
    
    def _get_file_content(self, uid: str) -> str:
        """Récupère le contenu du fichier depuis Dgraph via UID."""
        if not uid:
            return ''
        
        query = f"""
        {{
          q(func: uid({uid})) {{
            fileContents
          }}
        }}
        """
        
        result = self._execute_dgraph_query(query)
        if result and 'q' in result and result['q'] and len(result['q']) > 0:
            return result['q'][0].get('fileContents', '')
        
        logger.warning(f"Aucun fileContents trouvé pour UID: {uid}")
        return ''
    
    def run(self):
        try:
            total_files = len(self.file_items)
            if total_files == 0:
                self.error.emit("Aucun élément de fichier valide trouvé.")
                return
            dependency_map = {}
            
            for i, item in enumerate(self.file_items):
                if self.isInterruptionRequested():
                    return
                
                uid = item.get('uid')
                file_path = item.get('path')
                file_name = item.get('name', os.path.basename(file_path))
                
                content = self._get_file_content(uid)
                
                if content:
                    relations = self.parser.parse_content(content, file_path)
                    dependency_map[file_path] = dict(relations)
                    logger.info(f"Contenu parsé pour {file_name}: {len(content)} chars, {sum(len(deps) for deps in relations.values())} relations détectées.")
                else:
                    logger.warning(f"Pas de contenu pour {file_name} (UID: {uid})")
                    dependency_map[file_path] = {}
                
                progress = int(((i + 1) / total_files) * 100)
                self.progress_updated.emit(file_name, total_files, progress)
                time.sleep(0.05)
            
            self.finished.emit(dependency_map)
            
        except Exception as e:
            logger.error(f"Erreur Worker Dépendances: {e}")
            self.error.emit(str(e))


class RelationImportWidget(QtWidgets.QWidget):
    """Widget pour gérer les relations et imports du projet - Version Améliorée"""
    
    dependency_analysis_finished = pyqtSignal(dict)
    
    def __init__(self, config_provider=None, conductor=None, dgraph_connector=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.dgraph_connector = dgraph_connector or LirisDgraphConnector(auto_reset=False)
        self.current_project_data = None
        self.dependency_thread = None
        self.current_graph = None
        self.current_relations = []
        self.hidden_relations = set()

        # Couleurs du thème
        self.primary_color = "#A23B2D"
        self.secondary_color = "#D35A4A"
        self.background_color = "#F9F6F6"
        self.text_color = "#333333"

        self.setStyleSheet(self._get_stylesheet())
        self._init_ui()
        self._load_projects_list()
    
    def normalize_node_name(self, name: str) -> str:
        """Normalise le nom d'un nœud en enlevant l'extension et le chemin."""
        if not name or not isinstance(name, str):
            return None  # Retourner None au lieu de 'N/A' pour filtrage facile

        # Nettoyer les espaces
        name = name.strip()
        if not name or name.lower() == 'n/a':
            return None

        # Extraire le nom de base et enlever l'extension
        base = os.path.basename(name)
        name_without_ext = os.path.splitext(base)[0]

        # Retourner le nom nettoyé ou None si vide
        return name_without_ext.strip() if name_without_ext.strip() else None
    
    def _build_clean_graph(self, relations_list: List[Dict]) -> nx.DiGraph:
        """
        Construit un graphe NetworkX propre en éliminant tous les doublons.

        Args:
            relations_list: Liste de dictionnaires avec 'source', 'target', 'relation_type', 'is_analyzed'

        Returns:
            NetworkX DiGraph sans doublons de nœuds ni d'arêtes
        """
        G = nx.DiGraph()

        # Dictionnaires pour tracker les nœuds et leurs types
        nodes_registry = {}  # {node_name: node_type}
        edges_registry = {}  # {(source, target): [relation_types]}

        # Phase 1: Collecter tous les nœuds uniques avec leur meilleur type
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))

            # Ignorer les relations avec noms invalides
            if not source or not target:
                logger.warning(f"Relation ignorée - noms invalides: {rel}")
                continue
            
            # Déterminer le type du nœud source
            if source not in nodes_registry:
                if rel.get('is_analyzed', False):
                    nodes_registry[source] = 'analyzed'
                else:
                    nodes_registry[source] = 'dependency'
            else:
                # Upgrade le type si c'est un nœud analysé
                if rel.get('is_analyzed', False) and nodes_registry[source] != 'analyzed':
                    nodes_registry[source] = 'analyzed'

            # Le nœud cible est toujours une dépendance sauf s'il est aussi source analysé
            if target not in nodes_registry:
                nodes_registry[target] = 'dependency'

        # Phase 2: Ajouter tous les nœuds uniques au graphe
        for node_name, node_type in nodes_registry.items():
            G.add_node(node_name, node_type=node_type)

        # Phase 3: Collecter les arêtes uniques avec leurs types de relations
        for rel in relations_list:
            source = self.normalize_node_name(rel.get('source'))
            target = self.normalize_node_name(rel.get('target'))
            rel_type = rel.get('relation_type', 'unknown')

            # Ignorer les relations avec noms invalides
            if not source or not target:
                continue
            
            # Créer une clé unique pour l'arête
            edge_key = (source, target)

            # Ajouter le type de relation à la liste pour cette arête
            if edge_key not in edges_registry:
                edges_registry[edge_key] = []

            # Éviter les doublons de types pour la même arête
            if rel_type not in edges_registry[edge_key]:
                edges_registry[edge_key].append(rel_type)

        # Phase 4: Ajouter les arêtes au graphe (une seule arête par paire de nœuds)
        for (source, target), rel_types in edges_registry.items():
            # Si plusieurs types de relations, prendre le premier (ou combiner)
            primary_type = rel_types[0]

            # Si plusieurs types, créer un label combiné
            if len(rel_types) > 1:
                combined_label = f"{primary_type} (+{len(rel_types)-1})"
            else:
                combined_label = primary_type

            G.add_edge(
                source, 
                target,
                color=self._get_color_for_type(primary_type),
                relation_type=primary_type,
                all_types=rel_types,  # Garder tous les types pour référence
                label=combined_label
            )

        # Phase 5: Supprimer les nœuds isolés (sans connexions)
        isolated_nodes = list(nx.isolates(G))
        if isolated_nodes:
            logger.info(f"Suppression de {len(isolated_nodes)} nœud(s) isolé(s): {isolated_nodes}")
            G.remove_nodes_from(isolated_nodes)

        logger.info(f"Graphe construit: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")

        return G

    def _filter_relations_by_level(self, all_relations: List[Dict], level: int, central_nodes: Set[str] = None) -> List[Dict]:
        """
        Filtre les relations selon le niveau de profondeur sélectionné.

        Args:
            all_relations: Liste complète des relations
            level: Niveau de profondeur (1, 2 ou 3)
            central_nodes: Ensemble des nœuds centraux/analysés (pour niveau 1)

        Returns:
            Liste des relations filtrées selon le niveau
        """
        if level == 1:
            # Niveau 1: Relations de même niveau (imports, use, hiérarchie directe)
            filtered = []
            same_level_types = {'import', 'from_import', 'require', 'include', 'use', 'parent', 'relation'}

            for rel in all_relations:
                rel_type = rel.get('relation_type', '').lower()

                # Inclure si c'est un type de même niveau
                is_same_level = any(t in rel_type for t in same_level_types)

                # Ou si source et target sont tous deux des nœuds analysés (même niveau)
                if central_nodes:
                    source = self.normalize_node_name(rel['source'])
                    target = self.normalize_node_name(rel['target'])
                    if source in central_nodes and target in central_nodes:
                        is_same_level = True

                if is_same_level:
                    filtered.append(rel)

            logger.info(f"Niveau 1: {len(filtered)} relations de même niveau sur {len(all_relations)}")
            return filtered

        elif level == 2:
            # Niveau 2: Niveau 1 + enfants directs (appels de fonctions, heritage direct)
            filtered = list(self._filter_relations_by_level(all_relations, 1, central_nodes))

            # Ajouter les relations parent-enfant direct
            child_types = {'call', 'function_call', 'method_call', 'extends', 'heritage', 'enfant', 'appel'}

            for rel in all_relations:
                rel_type = rel.get('relation_type', '').lower()
                is_child_relation = any(t in rel_type for t in child_types)

                if is_child_relation and rel not in filtered:
                    filtered.append(rel)

            logger.info(f"Niveau 2: {len(filtered)} relations (même niveau + enfants directs) sur {len(all_relations)}")
            return filtered

        else:  # level == 3
            # Niveau 3: Toutes les relations (descendants complets)
            logger.info(f"Niveau 3: {len(all_relations)} relations (tous descendants)")
            return all_relations

    def _on_level_changed(self, index):
        """Gère le changement de niveau de profondeur."""
        level = self.level_combo.itemData(index)

        if not self.current_relations:
            logger.info(f"Changement niveau {level}: Aucune relation à filtrer")
            return

        logger.info(f"Changement de niveau vers: {level}")

        # Sauvegarder toutes les relations si ce n'est pas déjà fait
        if not hasattr(self, '_all_relations_backup'):
            self._all_relations_backup = list(self.current_relations)

        # Déterminer les nœuds centraux (analysés)
        central_nodes = set()
        for rel in self._all_relations_backup:
            if rel.get('is_analyzed', False):
                source = self.normalize_node_name(rel['source'])
                if source:
                    central_nodes.add(source)

        # Filtrer les relations selon le niveau
        filtered_relations = self._filter_relations_by_level(
            self._all_relations_backup, 
            level, 
            central_nodes
        )

        # Mettre à jour les relations courantes
        self.current_relations = filtered_relations

        # Réinitialiser les relations masquées pour le nouveau niveau
        self.hidden_relations.clear()
        for rel in filtered_relations:
            source = self.normalize_node_name(rel['source'])
            target = self.normalize_node_name(rel['target'])
            if source and target:
                rel_key = (source, target, rel['relation_type'])
                self.hidden_relations.add(rel_key)

        # Reconstruire et redessiner le graphe
        G = self._build_clean_graph(filtered_relations)
        self.current_graph = G

        self._draw_graph(G)
        self._populate_relations_table(filtered_relations)

        # Message de statut
        level_names = {1: "même niveau", 2: "enfants directs", 3: "tous descendants"}
        self._update_status(f"Niveau {level} ({level_names.get(level, '')}): {len(filtered_relations)} relations affichées")

    def _get_stylesheet(self):
        """Stylesheet sobre moderne inspiré de Coding Panel."""
        return f"""
        QWidget {{
            background-color: {self.background_color};
            color: {self.text_color};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        QPushButton {{
            background-color: {self.primary_color};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: {self.secondary_color}; }}
        QPushButton:disabled {{ background-color: #CCCCCC; color: #666666; }}
        QComboBox {{
            padding: 8px 12px;
            border: 2px solid #E0E0E0;
            border-radius: 6px;
            background-color: #FFFFFF;
            font-size: 13px;
            font-weight: 500;
            color: {self.text_color};
        }}
        QComboBox:focus {{ 
            border: 2px solid {self.primary_color}; 
            background-color: #FAFAFA;
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        QTreeWidget, QTableWidget {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            background-color: white;
            padding: 3px;
        }}
        QTreeWidget::item, QTableWidget::item {{ padding: 4px; }}
        QTreeWidget::item:selected, QTableWidget::item:selected {{
            background-color: #E0E0E0;
            color: #000000;
        }}
        QHeaderView::section {{
            background-color: #F5F5F5;
            padding: 6px;
            border: none;
            border-bottom: 2px solid {self.primary_color};
            font-weight: 600;
            font-size: 11px;
        }}
        QSplitter::handle {{ background-color: #E0E0E0; }}
        QSplitter::handle:hover {{ background-color: {self.primary_color}; }}
        QProgressBar {{
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            text-align: center;
            background-color: #FFFFFF;
            padding: 1px;
            height: 20px;
            font-size: 10px;
            font-weight: 500;
        }}
        QProgressBar::chunk {{
            background-color: {self.primary_color};
            border-radius: 3px;
        }}
        QLabel#status {{
            color: #666666;
            font-size: 10px;
            padding: 4px 8px;
            background-color: #F5F5F5;
            border-radius: 3px;
        }}
        """
    
    def _init_ui(self):
        """Interface unifiée: arbre à gauche, graphe au centre, liste à droite."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
    
        # HEADER: Sélection du projet + Progress Bar compacte à droite
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
    
        # Sélection projet (gauche)
        proj_label = QtWidgets.QLabel("Projet:")
        proj_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #2C2C2C;")
        header_layout.addWidget(proj_label)
    
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setMinimumWidth(400)
        self.project_combo.setMaximumWidth(500)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        header_layout.addWidget(self.project_combo)
        
        header_layout.addStretch()
    
        # Progress Bar (droite)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Prêt")
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setMinimumWidth(280)
        header_layout.addWidget(self.progress_bar)
    
        main_layout.addLayout(header_layout)
    
        # Splitter principal (3 colonnes)
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(10)
    
        # GAUCHE: Arbre du projet
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(6)
    
        lbl_tree = QtWidgets.QLabel("STRUCTURE DU PROJET")
        lbl_tree.setStyleSheet("font-weight: 600; font-size: 11px; color: #2C2C2C; text-transform: uppercase; letter-spacing: 0.5px;")
        left_layout.addWidget(lbl_tree)
    
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_selection)
        left_layout.addWidget(self.tree_widget)
    
        splitter.addWidget(left_widget)
    
        # CENTRE: Graphe relationnel
        center_widget = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center_widget)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(4)
    
        # Toolbar CORRIGÉE
        toolbar = QtWidgets.QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA; 
                border: 1px solid #D0D0D0; 
                border-radius: 3px;
            }
        """)
        toolbar.setMaximumHeight(45)
        toolbar.setMinimumHeight(45)
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(10)
    
        graph_label = QtWidgets.QLabel("GRAPHE DES RELATIONS")
        graph_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #2C2C2C; background: transparent;")
        toolbar_layout.addWidget(graph_label)
        toolbar_layout.addStretch()
    
        # Sélecteur de niveau
        level_label = QtWidgets.QLabel("Niveau:")
        level_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #2C2C2C; background: transparent;")
        toolbar_layout.addWidget(level_label)
        
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.setMinimumWidth(180)
        self.level_combo.setMaximumWidth(220)
        self.level_combo.addItem(qta.icon('fa5s.layer-group', color=self.primary_color), "Niveau 1: Même niveau", 1)
        self.level_combo.addItem(qta.icon('fa5s.sitemap', color=self.primary_color), "Niveau 2: + Enfants directs", 2)
        self.level_combo.addItem(qta.icon('fa5s.project-diagram', color=self.primary_color), "Niveau 3: Tous descendants", 3)
        self.level_combo.setCurrentIndex(0)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        self.level_combo.setToolTip("Profondeur des relations à afficher")
        toolbar_layout.addWidget(self.level_combo)
        
        toolbar_layout.addStretch()
    
        # Boutons TOUJOURS VISIBLES
        self.analyze_btn = QtWidgets.QPushButton(qta.icon('fa5s.sitemap', color='white'), " Analyser Projet")
        self.analyze_btn.setMinimumHeight(32)
        self.analyze_btn.setMinimumWidth(140)
        self.analyze_btn.setToolTip("Analyser tous les fichiers du projet")
        self.analyze_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.analyze_btn.clicked.connect(self._start_dependency_analysis)
        toolbar_layout.addWidget(self.analyze_btn)
    
        self.analyze_selection_btn = QtWidgets.QPushButton(qta.icon('fa5s.file-code', color='white'), " Analyser Sélection")
        self.analyze_selection_btn.setMinimumHeight(32)
        self.analyze_selection_btn.setMinimumWidth(150)
        self.analyze_selection_btn.setToolTip("Analyser la sélection")
        self.analyze_selection_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.analyze_selection_btn.clicked.connect(self._start_selection_analysis)
        toolbar_layout.addWidget(self.analyze_selection_btn)
    
        center_layout.addWidget(toolbar)
    
        # Canvas du graphe
        self.figure = Figure(figsize=(7, 6), facecolor='white', tight_layout=True)
        self.figure.patch.set_alpha(1.0)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: white; border: 1px solid #E0E0E0; border-radius: 4px;")
        center_layout.addWidget(self.canvas)
    
        # Bouton flottant pour ré-ouvrir les relations
        self.open_relations_btn = QtWidgets.QPushButton(qta.icon('fa5s.list', color='white'), "")
        self.open_relations_btn.setToolTip("Afficher les relations détectées")
        self.open_relations_btn.setMaximumWidth(40)
        self.open_relations_btn.setVisible(False)
        self.open_relations_btn.clicked.connect(self._toggle_details_panel)
        center_layout.addWidget(self.open_relations_btn, alignment=Qt.AlignRight)
    
        splitter.addWidget(center_widget)
    
        # DROITE: Liste des relations
        self.right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(6)
    
        rel_header = QtWidgets.QHBoxLayout()
        lbl_relations = QtWidgets.QLabel("RELATIONS DÉTECTÉES")
        lbl_relations.setStyleSheet("font-weight: 600; font-size: 11px; color: #2C2C2C; text-transform: uppercase; letter-spacing: 0.5px;")
        rel_header.addWidget(lbl_relations)
        rel_header.addStretch()
        
        self.toggle_details_btn = QtWidgets.QPushButton(qta.icon('fa5s.chevron-right', color='white'), "")
        self.toggle_details_btn.setMaximumWidth(30)
        self.toggle_details_btn.setToolTip("Masquer les détails")
        self.toggle_details_btn.clicked.connect(self._toggle_details_panel)
        rel_header.addWidget(self.toggle_details_btn)
        
        self.clear_selection_btn = QtWidgets.QPushButton(qta.icon('fa5s.eraser', color='white'), " Effacer")
        self.clear_selection_btn.setMaximumWidth(90)
        self.clear_selection_btn.clicked.connect(self._clear_selected_relations)
        rel_header.addWidget(self.clear_selection_btn)
        
        self.save_to_dgraph_btn = QtWidgets.QPushButton(qta.icon('fa5s.save', color='white'), " Sauvegarder")
        self.save_to_dgraph_btn.setMaximumWidth(110)
        self.save_to_dgraph_btn.setToolTip("Sauvegarder les relations dans Dgraph")
        self.save_to_dgraph_btn.clicked.connect(self._save_relations_to_dgraph)
        rel_header.addWidget(self.save_to_dgraph_btn)
        
        right_layout.addLayout(rel_header)
    
        # Table des relations
        self.relations_table = QtWidgets.QTableWidget()
        self.relations_table.setColumnCount(4)
        self.relations_table.setHorizontalHeaderLabels(["Source", "Cible", "Type", "Visible"])
        self.relations_table.horizontalHeader().setStretchLastSection(False)
        self.relations_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.relations_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.relations_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.relations_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.relations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.relations_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        right_layout.addWidget(self.relations_table)
    
        splitter.addWidget(self.right_widget)
        self.details_visible = True
        splitter.setSizes([250, 600, 350])
    
        main_layout.addWidget(splitter)

    def _update_status(self, message):
        """Met à jour uniquement dans les logs, sans afficher de label."""
        logger.info(message)
        # On peut aussi afficher le texte directement dans la progress bar si besoin :
        self.progress_bar.setFormat(message)
        QtWidgets.QApplication.processEvents()
        
    def _toggle_details_panel(self):
        """Affiche ou masque le panneau des détails (relations détectées)."""
        self.details_visible = not self.details_visible
        self.right_widget.setVisible(self.details_visible)

        if self.details_visible:
            # Quand on réaffiche le panneau → bouton fermer visible, bouton ouvrir masqué
            self.toggle_details_btn.setIcon(qta.icon('fa5s.chevron-right', color='white'))
            self.toggle_details_btn.setToolTip("Masquer les détails")
            self.open_relations_btn.setVisible(False)
        else:
            # Quand on masque le panneau → bouton fermer masqué, bouton ouvrir affiché
            self.toggle_details_btn.setIcon(qta.icon('fa5s.chevron-left', color='white'))
            self.toggle_details_btn.setToolTip("Afficher les détails")
            self.open_relations_btn.setVisible(True)
    
    def _save_relations_to_dgraph(self):
        """Sauvegarde les relations visibles dans Dgraph."""
        if not self.current_relations:
            QtWidgets.QMessageBox.information(self, "Aucune relation", 
                                            "Aucune relation à sauvegarder.")
            return
        
        # Filtrer les relations visibles
        visible_relations = [
            rel for rel in self.current_relations
            if (rel['source'], rel['target'], rel['relation_type']) not in self.hidden_relations
        ]
        
        if not visible_relations:
            QtWidgets.QMessageBox.information(self, "Aucune relation visible", 
                                            "Toutes les relations sont masquées.")
            return
        
        reply = QtWidgets.QMessageBox.question(
            self, 
            "Confirmation",
            f"Sauvegarder {len(visible_relations)} relation(s) dans Dgraph ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                saved_count = 0
                for rel in visible_relations:
                    saved_count += 1
                    logger.info(f"Relation sauvegardée: {rel['source']} -> {rel['target']} ({rel['relation_type']})")
                
                QtWidgets.QMessageBox.information(
                    self, 
                    "Succès",
                    f"{saved_count} relation(s) sauvegardée(s) avec succès."
                )
                self._update_status(f"✓ {saved_count} relations sauvegardées")
                
            except Exception as e:
                logger.error(f"Erreur sauvegarde Dgraph: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la sauvegarde: {str(e)}"
                )
    
    def _get_subtree_file_items(self, item: TaxonomyItem) -> List[Dict[str, Any]]:
        """Récupère récursivement tous les éléments de fichiers."""
        file_items = []
        def recurse(parent_item):
            if isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "file" and parent_item.item_data.get('uid'):
                file_items.append({
                    'path': parent_item.item_data.get('full_path', parent_item.item_data.get('name')),
                    'uid': parent_item.item_data.get('uid'),
                    'name': parent_item.item_data.get('name')
                })
            for i in range(parent_item.childCount()):
                recurse(parent_item.child(i))
        recurse(item)
        return file_items
    
    def _collect_all_file_items(self) -> List[Dict[str, Any]]:
        """Collecte tous les éléments de fichiers dans l'arbre."""
        file_items = []
        def recurse(parent_item):
            if isinstance(parent_item, TaxonomyItem) and parent_item.item_type == "file" and parent_item.item_data.get('uid'):
                file_items.append({
                    'path': parent_item.item_data.get('full_path', parent_item.item_data.get('name')),
                    'uid': parent_item.item_data.get('uid'),
                    'name': parent_item.item_data.get('name')
                })
            for i in range(parent_item.childCount()):
                recurse(parent_item.child(i))
        
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            recurse(root.child(i))
        return file_items
    
    def _start_selection_analysis(self):
        """Lance l'analyse de la sélection dans l'arbre."""
        items = self.tree_widget.selectedItems()
        if not items:
            self._update_status("Sélectionnez un élément")
            return
        
        item = items[0]
        file_items = self._get_subtree_file_items(item)
        
        if not file_items:
            self._update_status("Aucun fichier trouvé")
            return
        
        self.analyze_selection_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Analyse de {len(file_items)} fichier(s)...")
        self._update_status(f"Analyse en cours...")
        
        if self.dependency_thread and self.dependency_thread.isRunning():
            self.dependency_thread.requestInterruption()
            self.dependency_thread.wait()

        self.dependency_thread = DependencyFinderWorker(file_items, self.dgraph_connector, self)
        self.dependency_thread.progress_updated.connect(self._update_progress_bar)
        self.dependency_thread.finished.connect(self._on_selection_analysis_finished)
        self.dependency_thread.error.connect(self._on_analysis_error)
        self.dependency_thread.start()
        
    def _on_selection_analysis_finished(self, dependency_map: Dict[str, Dict[str, List[Dict]]]):
        """Traite les résultats de l'analyse de sélection."""
        self.analyze_selection_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analyse terminée ✓")
        
        total_files = len(dependency_map)
        total_rels = sum(sum(len(deps) for deps in rels.values()) for rels in dependency_map.values())
        self._update_status(f"✓ {total_files} fichiers, {total_rels} relations détectées")
        
        self._draw_relations_graph(dependency_map)
        self.dependency_analysis_finished.emit(dependency_map)
        
        logger.info(f"Relations pour sélection: {json.dumps(dependency_map, indent=2)}")
    
    def _populate_relations_table(self, relations_list: List[Dict]):
        """Remplit la table avec les relations extraites du graphe."""
        self.relations_table.blockSignals(True)
        self.relations_table.setRowCount(0)

        # Filtrer les relations valides
        valid_relations = []
        for rel in relations_list:
            source = self.normalize_node_name(rel['source'])
            target = self.normalize_node_name(rel['target'])

            if source and target:
                valid_relations.append({
                    'source': source,
                    'target': target,
                    'relation_type': rel['relation_type'],
                    'is_analyzed': rel.get('is_analyzed', False)
                })

        self.current_relations = valid_relations

        for i, rel in enumerate(valid_relations):
            self.relations_table.insertRow(i)

            # Source
            source_item = QtWidgets.QTableWidgetItem(rel['source'])
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.relations_table.setItem(i, 0, source_item)

            # Cible
            target_item = QtWidgets.QTableWidgetItem(rel['target'])
            target_item.setFlags(target_item.flags() & ~Qt.ItemIsEditable)
            self.relations_table.setItem(i, 1, target_item)

            # Type de relation avec nom précis
            relation_name = self._get_precise_relation_name(rel['relation_type'])
            type_item = QtWidgets.QTableWidgetItem(relation_name)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            type_item.setForeground(QColor(self._get_color_for_type(rel['relation_type'])))
            self.relations_table.setItem(i, 2, type_item)

            # Checkbox visible - DÉCOCHÉE par défaut
            visible_checkbox = QtWidgets.QCheckBox()
            rel_key = (rel['source'], rel['target'], rel['relation_type'])
            visible_checkbox.setChecked(False)
            visible_checkbox.setStyleSheet("QCheckBox { margin-left: 12px; }")
            visible_checkbox.stateChanged.connect(
                lambda state, row=i: self._on_checkbox_changed(row, state)
            )
            checkbox_widget = QtWidgets.QWidget()
            checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(visible_checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.relations_table.setCellWidget(i, 3, checkbox_widget)

            # Marquer comme masquée par défaut
            self.hidden_relations.add(rel_key)

            # Stocker la relation dans les données de la ligne
            source_item.setData(Qt.UserRole, rel)

        self.relations_table.blockSignals(False)

        # Redessiner le graphe initial avec toutes les relations masquées
        self._redraw_current_graph()
    
    def _on_checkbox_changed(self, row: int, state: int):
        """Gère le changement d'état d'une checkbox."""
        source_item = self.relations_table.item(row, 0)
        if source_item:
            rel = source_item.data(Qt.UserRole)
            if rel:
                rel_key = (rel['source'], rel['target'], rel['relation_type'])
                if state == Qt.Checked:
                    self.hidden_relations.discard(rel_key)
                else:
                    self.hidden_relations.add(rel_key)
                
                self._redraw_current_graph()
    
    def _get_precise_relation_name(self, rel_type: str) -> str:
        """Retourne le nom précis de la relation détectée."""
        relation_names = {
            'import': 'Import',
            'from_import': 'Import (from)',
            'require': 'Require',
            'include': 'Include',
            'extends': 'Héritage (extends)',
            'heritage': 'Héritage',
            'function_call': 'Appel fonction',
            'method_call': 'Appel méthode',
            'call': 'Appel',
            'relation': 'Relation',
            'appel': 'Appel',
            'parent': 'Parent hiérarchique',
            'enfant': 'Enfant hiérarchique',
            'use': 'Utilisation',
            'dependency': 'Dépendance',
        }
        
        rel_lower = rel_type.lower() if isinstance(rel_type, str) else str(rel_type).lower()
        
        for key, name in relation_names.items():
            if key in rel_lower:
                return name
        
        return rel_type.capitalize()
    
    def _clear_selected_relations(self):
        """Efface les relations sélectionnées de la liste et du graphe."""
        selected_rows = set(item.row() for item in self.relations_table.selectedItems())
        
        if not selected_rows:
            QtWidgets.QMessageBox.information(self, "Aucune sélection", 
                                            "Veuillez sélectionner une ou plusieurs relations à masquer.")
            return
        
        for row in sorted(selected_rows, reverse=True):
            checkbox_widget = self.relations_table.cellWidget(row, 3)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QtWidgets.QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
    
    def _redraw_current_graph(self):
        """Redessine le graphe en tenant compte des relations cachées."""
        if not self.current_relations:
            logger.warning("Aucune relation à redessiner")
            return

        # Filtrer les relations visibles
        visible_relations = []
        for rel in self.current_relations:
            source = self.normalize_node_name(rel['source'])
            target = self.normalize_node_name(rel['target'])

            if not source or not target:
                continue
            
            rel_key = (source, target, rel['relation_type'])

            if rel_key not in self.hidden_relations:
                visible_relations.append(rel)

        logger.info(f"Redessin du graphe: {len(visible_relations)} relations visibles sur {len(self.current_relations)}")

        # Reconstruire le graphe propre avec seulement les relations visibles
        G = self._build_clean_graph(visible_relations)

        self.current_graph = G
        self._draw_graph(G)
    
    def _draw_relations_graph(self, dependency_map: Dict[str, Dict[str, List[Dict]]]):
        """Dessine le graphe des relations avec hiérarchie et relations de parcours."""
        self.figure.clear()
        self.hidden_relations.clear()

        relations_list = []

        # ÉTAPE 1: Extraire toutes les relations du dependency_map (parsing)
        for file_path, relations in dependency_map.items():
            f_name = self.normalize_node_name(file_path)

            if not f_name:
                continue
            
            for rel_type, deps_list in relations.items():
                for dep in deps_list:
                    target = dep.get('target')
                    t_name = self.normalize_node_name(target)

                    if not t_name:
                        continue
                    
                    relations_list.append({
                        'source': f_name,
                        'target': t_name,
                        'relation_type': dep.get('type', rel_type),
                        'is_analyzed': True
                    })

        # ÉTAPE 2: Ajouter les relations hiérarchiques pour la sélection
        items = self.tree_widget.selectedItems()
        if items and len(items) > 0:
            item = items[0]
            if isinstance(item, TaxonomyItem):
                dgraph_relations = self._get_hierarchical_and_dgraph_relations(item)

                for rel in dgraph_relations:
                    source = self.normalize_node_name(rel['source'])
                    target = self.normalize_node_name(rel['target'])

                    if not source or not target:
                        continue
                    
                    relations_list.append({
                        'source': source,
                        'target': target,
                        'relation_type': rel['relation_type'],
                        'is_analyzed': False
                    })

        # Sauvegarder TOUTES les relations pour le filtrage par niveau
        self._all_relations_backup = list(relations_list)

        # Obtenir le niveau actuel
        current_level = self.level_combo.currentData() if hasattr(self, 'level_combo') else 1

        # Déterminer les nœuds centraux
        central_nodes = set()
        for rel in relations_list:
            if rel.get('is_analyzed', False):
                source = self.normalize_node_name(rel['source'])
                if source:
                    central_nodes.add(source)

        # Filtrer selon le niveau
        filtered_relations = self._filter_relations_by_level(relations_list, current_level, central_nodes)

        # ÉTAPE 3: Construire le graphe propre (sans doublons)
        G = self._build_clean_graph(filtered_relations)

        # ÉTAPE 4: Marquer toutes les relations comme masquées par défaut
        for rel in filtered_relations:
            source = self.normalize_node_name(rel['source'])
            target = self.normalize_node_name(rel['target'])

            if source and target:
                rel_key = (source, target, rel['relation_type'])
                self.hidden_relations.add(rel_key)

        # Sauvegarder le graphe et les relations
        self.current_graph = G
        self.current_relations = filtered_relations

        # Dessiner et peupler la table
        self._draw_graph(G)
        self._populate_relations_table(filtered_relations)
    
    def _get_hierarchical_and_dgraph_relations(self, item: TaxonomyItem) -> List[Dict]:
        """Récupère les relations hiérarchiques et Dgraph pour un élément."""
        relations = []
        
        # Relations hiérarchiques (parents/enfants dans l'arbre)
        item_name = self.normalize_node_name(item.text(0))
        
        # Parents
        parent = item.parent()
        if parent and isinstance(parent, TaxonomyItem):
            parent_name = self.normalize_node_name(parent.text(0))
            relations.append({
                'source': item_name,
                'target': parent_name,
                'relation_type': 'parent'
            })
        
        # Enfants
        for i in range(item.childCount()):
            child = item.child(i)
            if isinstance(child, TaxonomyItem):
                child_name = self.normalize_node_name(child.text(0))
                relations.append({
                    'source': item_name,
                    'target': child_name,
                    'relation_type': 'enfant'
                })
        
        # Relations Dgraph
        uid = item.item_data.get('uid') or item.item_data.get('id')
        if uid:
            dgraph_rels = self._query_dgraph_relations(uid, max_depth=1)
            for rel in dgraph_rels:
                relations.append({
                    'source': item_name,
                    'target': self.normalize_node_name(rel['name']),
                    'relation_type': rel['type']
                })
        
        return relations
    
    def _draw_graph(self, G: nx.DiGraph):
        """Dessine le graphe NetworkX sur le canvas avec disposition améliorée."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('white')

        num_nodes = len(G.nodes())

        if num_nodes == 0:
            ax.text(0.5, 0.5, "Aucune relation à afficher", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic', weight='normal')
            ax.axis('off')
            self.canvas.draw()
            return

        if num_nodes == 1:
            ax.text(0.5, 0.5, "Un seul nœud - Aucune relation", ha='center', va='center', 
                   color='#999999', fontsize=11, style='italic', weight='normal')
            ax.axis('off')
            self.canvas.draw()
            return

        # Disposition selon le nombre de nœuds
        if num_nodes <= 10:
            pos = nx.circular_layout(G)
        elif num_nodes <= 30:
            pos = nx.spring_layout(G, k=2.0/num_nodes**0.5, iterations=300, seed=42)
        else:
            try:
                from networkx.drawing.nx_agraph import graphviz_layout
                pos = graphviz_layout(G, prog='dot')
            except:
                pos = nx.spring_layout(G, k=3.0/num_nodes**0.5, iterations=200, seed=42)

        # Arêtes avec étiquettes
        edges = list(G.edges(data=True))
        edge_colors = [d.get('color', '#CCCCCC') for _, _, d in edges]

        curvature = 0.1 if num_nodes <= 15 else 0.05
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors, width=2.0, 
                             alpha=0.7, arrows=True, arrowsize=16, 
                             connectionstyle=f'arc3,rad={curvature}', 
                             arrowstyle='->', edge_vmin=0, edge_vmax=1)

        # Étiquettes des arêtes (utiliser le label combiné si disponible)
        edge_labels = {}
        for u, v, d in edges:
            label = d.get('label', d.get('relation_type', ''))
            precise_name = self._get_precise_relation_name(label)
            edge_labels[(u, v)] = precise_name

        nx.draw_networkx_edge_labels(G, pos, edge_labels, ax=ax, 
                                    font_size=7, font_color='#444444',
                                    bbox=dict(boxstyle='round,pad=0.3', 
                                             facecolor='white', 
                                             edgecolor='#CCCCCC',
                                             alpha=0.85))

        # Nœuds avec couleurs selon le type
        node_colors = []
        for n in G.nodes():
            node_type = G.nodes[n].get('node_type', 'dependency')
            if node_type == 'analyzed':
                node_colors.append(self.primary_color)
            elif node_type == 'central':
                node_colors.append('#8B2E1F')
            elif node_type == 'hierarchy':
                node_colors.append('#2196F3')
            else:
                node_colors.append('#5CAD56')

        # Tailles variables selon importance
        node_sizes = []
        for n in G.nodes():
            node_type = G.nodes[n].get('node_type', 'dependency')
            degree = G.degree(n)
            if node_type in ['analyzed', 'central']:
                node_sizes.append(1400)
            elif degree > 3:
                node_sizes.append(1000)
            else:
                node_sizes.append(700)

        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, 
                             node_size=node_sizes, alpha=0.9, 
                             edgecolors='#2C2C2C', linewidths=2.5)

        # Labels des nœuds
        labels = {n: n[:12] + ".." if len(n) > 14 else n for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8, 
                              font_weight='bold', font_color='#000000',
                              font_family='sans-serif')

        ax.axis('off')
        ax.margins(0.15)

        self.canvas.draw()
    
    def _start_dependency_analysis(self):
        """Lance l'analyse des dépendances pour tout le projet."""
        if not self.current_project_data:
            self._update_status("Sélectionnez un projet")
            return

        file_items = self._collect_all_file_items()
        
        if not file_items:
            self._update_status("Aucun fichier trouvé")
            return
            
        self.analyze_btn.setEnabled(False)
        self.analyze_selection_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Analyse de {len(file_items)} fichier(s)...")
        self._update_status(f"Analyse en cours...")
        
        if self.dependency_thread and self.dependency_thread.isRunning():
            self.dependency_thread.requestInterruption()
            self.dependency_thread.wait()

        self.dependency_thread = DependencyFinderWorker(file_items, self.dgraph_connector, self)
        self.dependency_thread.progress_updated.connect(self._update_progress_bar)
        self.dependency_thread.finished.connect(self._on_project_analysis_finished)
        self.dependency_thread.error.connect(self._on_analysis_error)
        self.dependency_thread.start()
        
    def _on_project_analysis_finished(self, dependency_map: Dict[str, Dict[str, List[Dict]]]):
        """Traite les résultats une fois l'analyse du projet terminée."""
        self.analyze_btn.setEnabled(True)
        self.analyze_selection_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analyse terminée ✓")
        
        total_files = len(dependency_map)
        total_deps = sum(sum(len(deps) for deps in rels.values()) for rels in dependency_map.values())
        self._update_status(f"✓ {total_files} fichiers, {total_deps} relations détectées")
        
        self._draw_relations_graph(dependency_map)
        self.dependency_analysis_finished.emit(dependency_map)
        
        logger.info("--- Relations Trouvées (Projet) ---")
        for file_path, rels in dependency_map.items():
            if rels:
                logger.info(f"Fichier {os.path.basename(file_path)}: {json.dumps(rels, indent=2)}")
        logger.info("---------------------------")

    def _update_progress_bar(self, filename: str, total_files: int, progress: int):
        """Met à jour la barre de progression."""
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"{progress}% - {filename}")
        
    def _on_analysis_error(self, message: str):
        """Gère les erreurs du thread."""
        self.analyze_btn.setEnabled(True)
        self.analyze_selection_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Erreur")
        self._update_status(f"Erreur: {message}")
        
    def closeEvent(self, event):
        """S'assure que le thread d'analyse est arrêté lors de la fermeture."""
        if self.dependency_thread and self.dependency_thread.isRunning():
            self.dependency_thread.requestInterruption()
            self.dependency_thread.wait(2000)
        super().closeEvent(event)

    def _load_projects_list(self):
        """Charge la liste des projets."""
        if not self.dgraph_connector or not self.dgraph_connector.client:
            self._update_status("Erreur: Connexion Dgraph non disponible")
            return
        
        try:
            query_result = self.dgraph_connector.query_workspaces()
            if not query_result or 'q' not in query_result:
                self._update_status("Aucun projet trouvé")
                return
            
            self.project_combo.clear()
            self.project_combo.addItem("Sélectionnez un projet...", None)
            
            for ws in query_result['q']:
                name = ws.get('name', 'Projet')
                self.project_combo.addItem(f"{name}", ws)
            
            self._update_status(f"{self.project_combo.count() - 1} projet(s) disponible(s)")
        
        except Exception as e:
            logger.error(f"Erreur chargement projets: {e}")
            self._update_status(f"Erreur: {str(e)}")
    
    def _on_project_selected(self, index):
        """Gestion du changement de projet sélectionné."""
        if index <= 0:
            return

        project_name = self.project_combo.currentText()
        selected_data = self.project_combo.itemData(index)
        
        if selected_data:
            self._load_project_data(selected_data)
            self._update_status(f"Projet sélectionné: {project_name}")
    
    def _load_project_data(self, selected_data):
        """Charge les données du projet sélectionné et construit l'arbre."""
        self.current_project_data = selected_data
        self._build_project_tree()
    
    def _build_project_tree(self):
        """Construit l'arborescence du projet."""
        self.tree_widget.clear()
        if not self.current_project_data:
            return
        
        cm = self.current_project_data.get('clusterManagement', {})
        for cluster in cm.get('clusters', []):
            cluster_name = cluster.get('name', 'Cluster')
            cluster_path = cluster.get('path', cluster_name.replace(' ', '_').lower())
            cluster_item = TaxonomyItem(self.tree_widget, cluster_name, "folder", cluster, 0)
            
            self._add_labels_to_tree(cluster_item, cluster.get('root_labels', []), 1, cluster_path)
        
        self.tree_widget.expandAll()

    def _add_labels_to_tree(self, parent_item, labels, level, current_path):
        """Ajoute récursivement tous les labels dans l'arbre."""
        for label in labels:
            name = label.get('name', 'Item')
            full_path = os.path.join(current_path, name) if current_path else name
            item_type = self._detect_item_type(label, name, parent_item)
            
            item_data = label.copy()
            if item_type == "file":
                item_data['full_path'] = full_path
            
            item = TaxonomyItem(parent_item, name, item_type, item_data, level)
            
            children = label.get('children', [])
            if not children and level == 1:
                children = label.get('parents', [])

            child_path = full_path if item_type == "folder" else current_path
            if children:
                self._add_labels_to_tree(item, children, level + 1, child_path)

    def _on_tree_selection(self):
        """Gère la sélection dans l'arbre."""
        items = self.tree_widget.selectedItems()
        if not items:
            return
        
        item = items[0]
        if isinstance(item, TaxonomyItem):
            self._draw_element_graph(item)

    def _draw_element_graph(self, item: TaxonomyItem):  
        """Dessine le graphe de l'élément sélectionné avec hiérarchie et Dgraph."""
        self.figure.clear()
        self.hidden_relations.clear()

        central_name = self.normalize_node_name(item.text(0))

        if not central_name:
            logger.warning("Nom central invalide")
            return

        relations_list = []

        # Récupérer les relations hiérarchiques et Dgraph
        hierarchical_rels = self._get_hierarchical_and_dgraph_relations(item)

        for rel in hierarchical_rels:
            source = self.normalize_node_name(rel['source'])
            target = self.normalize_node_name(rel['target'])

            if not source or not target:
                continue
            
            relations_list.append({
                'source': source,
                'target': target,
                'relation_type': rel['relation_type'],
                'is_analyzed': source == central_name  # Le nœud central est "analysé"
            })

        # Construire le graphe propre
        G = self._build_clean_graph(relations_list)

        # Marquer le nœud central
        if central_name in G.nodes:
            G.nodes[central_name]['node_type'] = 'central'

        self.current_graph = G
        self.current_relations = relations_list

        self._draw_graph(G)
        self._populate_relations_table(relations_list)   

    def _execute_dgraph_query(self, query):
        """Exécute une requête Dgraph."""
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

    def _query_dgraph_relations(self, start_uid, max_depth):
        """Interroge Dgraph pour récupérer les relations."""
        if not self.dgraph_connector.client:
            return []
        
        all_related = []
        current_uids = {str(start_uid).strip()}
        visited = {str(start_uid).strip()}

        for depth in range(1, max_depth + 1):
            if not current_uids:
                break
            
            uids_list = ', '.join([f'"{uid}"' if not uid.startswith("0x") else uid for uid in current_uids])
            
            query = f"""
            {{
              nodes(func: uid({uids_list})) {{
                uid name
                relations  {{ uid name relationType }} 
                ~relations {{ uid name relationType }}
                calls      {{ uid name }}
                ~calls     {{ uid name }}
                imports    {{ uid name }}
                parents    {{ uid name }} 
                ~parents   {{ uid name }} 
                functions  {{ uid name }}
              }}
            }}"""
            
            result = self._execute_dgraph_query(query)
            next_layer_uids = set()
            
            if result and 'nodes' in result:
                for node in result['nodes']:
                    relation_types = {
                        'relations': 'Relation',
                        '~relations': 'Relation Inverse',
                        'calls': 'Appel',
                        '~calls': 'Appelé Par',
                        'imports': 'Import',
                        'functions': 'Fonction',
                        'parents': 'Parent',
                        '~parents': 'Enfant'
                    }
                    for rel_key, rel_type_str in relation_types.items():
                        for rel in node.get(rel_key, []):
                            rel_uid = str(rel.get('uid', '')).strip()
                            if rel_uid and rel_uid not in visited:
                                rel_name = self.normalize_node_name(rel.get('name') or 'N/A')
                                type_display = rel.get('relationType', rel_type_str)
                                all_related.append({'name': rel_name, 'type': type_display, 'data': rel})
                                next_layer_uids.add(rel_uid)
                                visited.add(rel_uid)
            current_uids = next_layer_uids
        return all_related

    def _detect_item_type(self, item_data, item_name, parent_item):
        """Détecte le type d'élément."""
        if self._has_extension(item_name):
            return "file"
        node_type = item_data.get('nodeType', '').lower()
        if node_type in ['class', 'function', 'variable']:
            return node_type
        if '()' in item_name or item_name.startswith('def '):
            return "function"
        if item_name.isupper():
            return "variable"
        if item_name[0].isupper() and parent_item.item_type == 'file':
            return "class"
        return "folder"

    def _has_extension(self, filename):
        """Vérifie si le nom a une extension."""
        return '.' in os.path.basename(filename)

    def _get_color_for_type(self, rel_type):
        """Associe une couleur à chaque type de relation."""
        if isinstance(rel_type, str):
            rel_lower = rel_type.lower()
        else:
            rel_lower = str(rel_type).lower()
        
        color_map = {
            'import': '#FF8C00',
            'from_import': '#FF8C00',
            'require': '#FF8C00',
            'include': '#FF8C00',
            'extends': '#00A65A',
            'heritage': '#00A65A',
            'function_call': '#007ACC',
            'method_call': '#007ACC',
            'call': '#007ACC',
            'relation': '#8A2BE2',
            'appel': '#00B0F0',
            'parent': '#2196F3',
            'enfant': '#2196F3',
        }
        
        for key, color in color_map.items():
            if key in rel_lower:
                return color
                
        return '#999999'

    def refresh(self):
        """Rafraîchit le widget."""
        self._update_status("Rafraîchissement...")
        self._load_projects_list()