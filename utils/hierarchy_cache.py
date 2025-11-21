#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Système de cache hiérarchique unifié pour DatasetConfigTab
Structure: Projet -> Typologie -> Cluster -> Racine -> Parent -> Enfants (récursif infini)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HierarchyNode:
    """Nœud dans l'arbre hiérarchique"""
    name: str
    category: str = "default"
    children: Dict[str, 'HierarchyNode'] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_child(self, name: str, category: str = "default") -> 'HierarchyNode':
        """Ajouter un enfant et retourner le nœud créé"""
        if name not in self.children:
            self.children[name] = HierarchyNode(name=name, category=category)
        return self.children[name]
    
    def remove_child(self, name: str) -> bool:
        """Supprimer un enfant"""
        if name in self.children:
            del self.children[name]
            return True
        return False
    
    def rename_child(self, old_name: str, new_name: str) -> bool:
        """Renommer un enfant"""
        if old_name in self.children and new_name not in self.children:
            node = self.children.pop(old_name)
            node.name = new_name
            self.children[new_name] = node
            return True
        return False
    
    def get_child(self, name: str) -> Optional['HierarchyNode']:
        """Obtenir un enfant par nom"""
        return self.children.get(name)
    
    def get_children_names(self) -> List[str]:
        """Liste des noms des enfants"""
        return list(self.children.keys())
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour sérialisation"""
        return {
            'name': self.name,
            'category': self.category,
            'metadata': self.metadata,
            'children': {k: v.to_dict() for k, v in self.children.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'HierarchyNode':
        """Créer depuis un dictionnaire"""
        node = cls(
            name=data.get('name', ''),
            category=data.get('category', 'default'),
            metadata=data.get('metadata', {})
        )
        for child_name, child_data in data.get('children', {}).items():
            node.children[child_name] = cls.from_dict(child_data)
        return node


class HierarchyCache:
    """
    Cache hiérarchique unifié pour la navigation dans l'arbre de dataset
    
    Structure:
    cache_root
    └── typologies
        └── {typologie_name}: HierarchyNode
            └── clusters (children)
                └── {cluster_name}: HierarchyNode
                    └── roots (children)
                        └── {root_name}: HierarchyNode
                            └── parents (children)
                                └── {parent_name}: HierarchyNode
                                    └── children (récursif infini)
    """
    
    def __init__(self):
        self.typologies: Dict[str, HierarchyNode] = {}
        self._current_path: List[str] = []  # Chemin de navigation actuel
        self._dirty: bool = False  # Indique si le cache a été modifié
        
    def clear(self):
        """Réinitialiser le cache"""
        self.typologies.clear()
        self._current_path.clear()
        self._dirty = False
        logger.debug("Cache hiérarchique vidé")
    
    @property
    def is_dirty(self) -> bool:
        return self._dirty
    
    def mark_clean(self):
        self._dirty = False
    
    # ==================== GESTION DES TYPOLOGIES ====================
    
    def add_typologie(self, name: str) -> bool:
        """Ajouter une typologie"""
        if name not in self.typologies:
            self.typologies[name] = HierarchyNode(name=name)
            self._dirty = True
            logger.debug(f"Typologie '{name}' ajoutée au cache")
            return True
        return False
    
    def remove_typologie(self, name: str) -> bool:
        """Supprimer une typologie et toute sa hiérarchie"""
        if name in self.typologies:
            del self.typologies[name]
            self._dirty = True
            logger.debug(f"Typologie '{name}' supprimée du cache")
            return True
        return False
    
    def rename_typologie(self, old_name: str, new_name: str) -> bool:
        """Renommer une typologie"""
        if old_name in self.typologies and new_name not in self.typologies:
            node = self.typologies.pop(old_name)
            node.name = new_name
            self.typologies[new_name] = node
            self._dirty = True
            logger.debug(f"Typologie renommée: '{old_name}' -> '{new_name}'")
            return True
        return False
    
    def get_typologies(self) -> List[str]:
        """Liste des typologies"""
        return list(self.typologies.keys())
    
    # ==================== NAVIGATION PAR CHEMIN ====================
    
    def get_node_at_path(self, path: List[str]) -> Optional[HierarchyNode]:
        """
        Obtenir le nœud à un chemin donné
        path: [typologie, cluster, root, parent, child1, child2, ...]
        """
        if not path:
            return None
        
        typologie_name = path[0]
        if typologie_name not in self.typologies:
            return None
        
        current = self.typologies[typologie_name]
        
        for i, name in enumerate(path[1:], 1):
            child = current.get_child(name)
            if child is None:
                logger.debug(f"Nœud non trouvé au niveau {i}: '{name}'")
                return None
            current = child
        
        return current
    
    def get_children_at_path(self, path: List[str]) -> List[str]:
        """Obtenir les noms des enfants à un chemin donné"""
        if not path:
            return self.get_typologies()
        
        node = self.get_node_at_path(path)
        if node:
            return node.get_children_names()
        return []
    
    def add_child_at_path(self, path: List[str], child_name: str, 
                          category: str = "default") -> bool:
        """
        Ajouter un enfant à un chemin donné
        Si path est vide, ajoute une typologie
        """
        if not path:
            return self.add_typologie(child_name)
        
        node = self.get_node_at_path(path)
        if node:
            if child_name not in node.children:
                node.add_child(child_name, category)
                self._dirty = True
                logger.debug(f"Enfant '{child_name}' ajouté à {' > '.join(path)}")
                return True
        return False
    
    def remove_child_at_path(self, path: List[str], child_name: str) -> bool:
        """Supprimer un enfant à un chemin donné"""
        if not path:
            return self.remove_typologie(child_name)
        
        node = self.get_node_at_path(path)
        if node and node.remove_child(child_name):
            self._dirty = True
            logger.debug(f"Enfant '{child_name}' supprimé de {' > '.join(path)}")
            return True
        return False
    
    def rename_child_at_path(self, path: List[str], old_name: str, 
                             new_name: str) -> bool:
        """Renommer un enfant à un chemin donné"""
        if not path:
            return self.rename_typologie(old_name, new_name)
        
        node = self.get_node_at_path(path)
        if node and node.rename_child(old_name, new_name):
            self._dirty = True
            logger.debug(f"Enfant renommé à {' > '.join(path)}: '{old_name}' -> '{new_name}'")
            return True
        return False
    
    # ==================== GESTION DU CONTEXTE DE NAVIGATION ====================
    
    def set_current_path(self, path: List[str]):
        """Définir le chemin de navigation actuel"""
        self._current_path = list(path)
    
    def get_current_path(self) -> List[str]:
        """Obtenir le chemin de navigation actuel"""
        return list(self._current_path)
    
    def navigate_into(self, child_name: str) -> bool:
        """Naviguer dans un enfant"""
        test_path = self._current_path + [child_name]
        if self.get_node_at_path(test_path):
            self._current_path.append(child_name)
            return True
        return False
    
    def navigate_up(self) -> bool:
        """Remonter d'un niveau"""
        if self._current_path:
            self._current_path.pop()
            return True
        return False
    
    def navigate_to_root(self):
        """Retourner à la racine"""
        self._current_path.clear()
    
    def get_current_children(self) -> List[str]:
        """Obtenir les enfants du niveau actuel"""
        return self.get_children_at_path(self._current_path)
    
    def add_current_child(self, name: str, category: str = "default") -> bool:
        """Ajouter un enfant au niveau actuel"""
        return self.add_child_at_path(self._current_path, name, category)
    
    def remove_current_child(self, name: str) -> bool:
        """Supprimer un enfant au niveau actuel"""
        return self.remove_child_at_path(self._current_path, name)
    
    def rename_current_child(self, old_name: str, new_name: str) -> bool:
        """Renommer un enfant au niveau actuel"""
        return self.rename_child_at_path(self._current_path, old_name, new_name)
    
    # ==================== NIVEAUX SÉMANTIQUES ====================
    
    def get_clusters(self, typologie: str) -> List[str]:
        """Obtenir les clusters d'une typologie"""
        return self.get_children_at_path([typologie])
    
    def get_roots(self, typologie: str, cluster: str) -> List[str]:
        """Obtenir les racines d'un cluster"""
        return self.get_children_at_path([typologie, cluster])
    
    def get_parents(self, typologie: str, cluster: str, root: str) -> List[str]:
        """Obtenir les parents d'une racine"""
        return self.get_children_at_path([typologie, cluster, root])
    
    def get_children(self, typologie: str, cluster: str, root: str, 
                     parent: str, sub_path: List[str] = None) -> List[str]:
        """Obtenir les enfants avec sous-chemin optionnel"""
        path = [typologie, cluster, root, parent]
        if sub_path:
            path.extend(sub_path)
        return self.get_children_at_path(path)
    
    # ==================== SÉRIALISATION ====================
    
    def to_dict(self) -> dict:
        """Exporter le cache complet"""
        return {
            'typologies': {k: v.to_dict() for k, v in self.typologies.items()},
            'current_path': self._current_path
        }
    
    def from_dict(self, data: dict):
        """Importer depuis un dictionnaire"""
        self.clear()
        for name, typ_data in data.get('typologies', {}).items():
            self.typologies[name] = HierarchyNode.from_dict(typ_data)
        self._current_path = data.get('current_path', [])
    
    def get_breadcrumb(self, max_display: int = 3) -> str:
        """Générer le fil d'Ariane pour l'affichage"""
        if not self._current_path:
            return "Racine"
        
        if len(self._current_path) <= max_display:
            return " > ".join(self._current_path)
        
        # Afficher seulement les derniers niveaux
        return "... > " + " > ".join(self._current_path[-max_display:])
    
    def get_depth(self) -> int:
        """Profondeur actuelle dans la hiérarchie"""
        return len(self._current_path)
    
    def get_level_name(self) -> str:
        """Nom du niveau actuel"""
        depth = self.get_depth()
        level_names = ["Typologies", "Clusters", "Racines", "Parents", "Enfants"]
        if depth < len(level_names):
            return level_names[depth]
        return f"Niveau {depth - 3}"  # Enfants niveau N