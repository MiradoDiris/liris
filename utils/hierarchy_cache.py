#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Système de cache hiérarchique unifié pour DatasetConfigTab
Structure: Projet -> Typologie -> Cluster -> Racine -> Parent -> Enfants (récursif infini)
"""

import logging
from os import path
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
    
    def insert_parent_above(self, path: List[str], element_name: str, new_parent_name: str) -> bool:
        """
        Insère un nouveau parent AU-DESSUS d'un élément existant
        L'élément existant devient enfant du nouveau parent

        Exemple:
            Avant: typologie → cluster → root → parent1 → child1
            Appel: insert_parent_above([typ, cluster, root], "parent1", "new_parent")
            Après: typologie → cluster → root → new_parent → parent1 → child1

        Args:
            path: Chemin jusqu'au niveau PARENT de l'élément
            element_name: Nom de l'élément qui aura un nouveau parent
            new_parent_name: Nom du nouveau parent à créer

        Returns:
            True si l'insertion réussit, False sinon
        """
        # Validation
        if not path or not element_name or not new_parent_name:
            logger.error("Chemin, élément ou nouveau parent vide")
            return False

        # Vérifier que l'élément existe
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        element_node = parent_node.get_child(element_name)
        if not element_node:
            logger.error(f"Élément '{element_name}' non trouvé dans {' > '.join(path)}")
            return False

        # Vérifier que le nouveau parent n'existe pas déjà
        if parent_node.get_child(new_parent_name):
            logger.error(f"Le nouveau parent '{new_parent_name}' existe déjà")
            return False

        # ÉTAPE 1: Créer le nouveau parent
        new_parent_node = parent_node.add_child(new_parent_name, element_node.category)

        # ÉTAPE 2: Déplacer l'élément existant sous le nouveau parent
        # Copier toute la structure de l'élément
        new_parent_node.children[element_name] = element_node

        # ÉTAPE 3: Supprimer l'élément de son emplacement original
        del parent_node.children[element_name]

        self._dirty = True
        logger.info(f"✅ Parent '{new_parent_name}' inséré au-dessus de '{element_name}' dans {' > '.join(path)}")
        logger.info(f"   Structure: {' > '.join(path)} → {new_parent_name} → {element_name}")

        return True
    
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
    
    def insert_child_between(self, path: List[str], new_child_name: str, 
                        move_existing_children: bool = True) -> bool:
        """
        Insère un nouveau niveau d'enfant ENTRE un parent et ses enfants existants

        Exemple:
            Avant: typologie → cluster → root → parent1 → [child1, child2, child3]
            Appel: insert_child_between([typ, cluster, root, parent1], "intermediate")
            Après: typologie → cluster → root → parent1 → intermediate → [child1, child2, child3]

        Args:
            path: Chemin jusqu'au parent qui recevra le nouvel enfant intermédiaire
            new_child_name: Nom du nouvel enfant intermédiaire
            move_existing_children: Si True, déplace tous les enfants existants sous le nouveau

        Returns:
            True si l'insertion réussit, False sinon
        """
        # Validation
        if not path or not new_child_name:
            logger.error("Chemin ou nom d'enfant vide")
            return False

        # Obtenir le nœud parent
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        # Vérifier que le nouvel enfant n'existe pas déjà
        if parent_node.get_child(new_child_name):
            logger.error(f"L'enfant '{new_child_name}' existe déjà")
            return False

        # Sauvegarder les enfants existants
        existing_children = dict(parent_node.children) if move_existing_children else {}

        # ÉTAPE 1: Créer le nouvel enfant intermédiaire
        new_child_node = parent_node.add_child(new_child_name, parent_node.category)

        if move_existing_children and existing_children:
            # ÉTAPE 2: Déplacer tous les enfants existants sous le nouveau
            for child_name, child_node in existing_children.items():
                if child_name != new_child_name:  # Ne pas déplacer le nouveau nœud lui-même
                    new_child_node.children[child_name] = child_node
                    # Supprimer de l'emplacement original
                    if child_name in parent_node.children:
                        del parent_node.children[child_name]

            logger.info(f"✅ Enfant intermédiaire '{new_child_name}' inséré avec {len(existing_children)-1} enfants déplacés")
        else:
            logger.info(f"✅ Enfant intermédiaire '{new_child_name}' créé sans déplacement")

        self._dirty = True
        logger.info(f"   Structure: {' > '.join(path)} → {new_child_name} → [{', '.join(new_child_node.get_children_names())}]")

        return True
    
    def insert_sibling_and_move(self, path: List[str], element_name: str, 
                           new_sibling_name: str, elements_to_move: List[str]) -> bool:
        """
        Crée un nouveau frère/sœur et y déplace des éléments spécifiques
        Utile pour réorganiser la taxonomie

        Exemple:
            Avant: parent → [child1, child2, child3, child4]
            Appel: insert_sibling_and_move([parent], "child1", "new_group", ["child2", "child3"])
            Après: parent → [child1, new_group → [child2, child3], child4]

        Args:
            path: Chemin jusqu'au niveau parent
            element_name: Élément de référence (pour la catégorie)
            new_sibling_name: Nom du nouveau frère/sœur
            elements_to_move: Liste des noms d'éléments à déplacer

        Returns:
            True si l'insertion réussit, False sinon
        """
        # Validation
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        ref_element = parent_node.get_child(element_name)
        if not ref_element:
            logger.error(f"Élément de référence '{element_name}' non trouvé")
            return False

        # Vérifier que le nouveau sibling n'existe pas
        if parent_node.get_child(new_sibling_name):
            logger.error(f"Le sibling '{new_sibling_name}' existe déjà")
            return False

        # ÉTAPE 1: Créer le nouveau sibling
        new_sibling = parent_node.add_child(new_sibling_name, ref_element.category)

        # ÉTAPE 2: Déplacer les éléments spécifiés
        moved_count = 0
        for elem_name in elements_to_move:
            elem_node = parent_node.get_child(elem_name)
            if elem_node:
                # Déplacer sous le nouveau sibling
                new_sibling.children[elem_name] = elem_node
                del parent_node.children[elem_name]
                moved_count += 1
            else:
                logger.warning(f"Élément '{elem_name}' non trouvé, ignoré")

        self._dirty = True
        logger.info(f"✅ Sibling '{new_sibling_name}' créé avec {moved_count} éléments déplacés")

        return True
    
    def promote_to_higher_level(self, path: List[str], element_name: str) -> bool:
        if len(path) < 1:
            logger.error("Impossible de promouvoir depuis la racine")
            return False

        # Obtenir le nœud parent actuel
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        # Obtenir l'élément à promouvoir
        element_node = parent_node.get_child(element_name)
        if not element_node:
            logger.error(f"Élément '{element_name}' non trouvé")
            return False

        # Obtenir le grand-parent (niveau au-dessus)
        grandparent_path = path[:-1]
        grandparent_node = self.get_node_at_path(grandparent_path) if grandparent_path else None

        if not grandparent_node and len(path) > 1:
            logger.error("Grand-parent non trouvé")
            return False

        # ÉTAPE 1: Copier l'élément au niveau supérieur
        if grandparent_node:
            grandparent_node.children[element_name] = element_node
        else:
            # Cas spécial: promotion au niveau typologie
            if len(path) == 1:
                self.typologies[element_name] = element_node

        # ÉTAPE 2: Supprimer de l'emplacement original
        del parent_node.children[element_name]

        self._dirty = True
        logger.info(f"✅ Élément '{element_name}' promu de {' > '.join(path)} vers {' > '.join(grandparent_path)}")

        return True
    
    def demote_to_child_of_sibling(self, path: List[str], element_name: str, 
                               target_sibling_name: str) -> bool:
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        element_node = parent_node.get_child(element_name)
        target_node = parent_node.get_child(target_sibling_name)

        if not element_node or not target_node:
            logger.error(f"Élément ou sibling cible non trouvé")
            return False

        # ÉTAPE 1: Déplacer l'élément sous le sibling cible
        target_node.children[element_name] = element_node

        # ÉTAPE 2: Supprimer de l'emplacement original
        del parent_node.children[element_name]

        self._dirty = True
        logger.info(f"✅ Élément '{element_name}' déplacé sous '{target_sibling_name}'")

        return True

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
    
    def shift_level_down(self, path: List[str], element_name: str, new_parent_name: str) -> bool:
        """
        Décale un élément d'un niveau vers le bas en insérant un nouveau parent au-dessus

        Exemple:
            Avant: A(root) → B(parent) → C(child)
            Appel: shift_level_down([typologie, cluster], "A", "X")
            Après: X(root) → A(parent) → B(child) → C(child-child)

        Args:
            path: Chemin jusqu'au niveau CONTENANT l'élément
            element_name: Nom de l'élément à décaler vers le bas
            new_parent_name: Nom du nouveau parent à insérer au-dessus

        Returns:
            True si le décalage réussit
        """
        parent_node = self.get_node_at_path(path)
        if not parent_node:
            logger.error(f"Nœud parent non trouvé: {' > '.join(path)}")
            return False

        element_node = parent_node.get_child(element_name)
        if not element_node:
            logger.error(f"Élément '{element_name}' non trouvé")
            return False

        # Vérifier que le nouveau parent n'existe pas déjà
        if parent_node.get_child(new_parent_name):
            logger.error(f"Le nouveau parent '{new_parent_name}' existe déjà")
            return False

        # ÉTAPE 1: Créer le nouveau parent au niveau actuel
        new_parent_node = parent_node.add_child(new_parent_name, element_node.category)

        # ÉTAPE 2: Déplacer l'élément existant (avec toute sa descendance) sous le nouveau parent
        new_parent_node.children[element_name] = element_node

        # ÉTAPE 3: Supprimer l'élément de son emplacement original
        del parent_node.children[element_name]

        self._dirty = True
        logger.info(f"✅ '{element_name}' décalé vers le bas, nouveau parent '{new_parent_name}' créé")
        logger.info(f"   Structure: {' > '.join(path)} → {new_parent_name} → {element_name}")

        return True
    
    def shift_level_up(self, path: List[str], parent_name: str, new_child_name: str) -> bool:
        # Construire le chemin complet vers le parent
        full_path = path + [parent_name]
        parent_node = self.get_node_at_path(full_path)
        
        if not parent_node:
            logger.error(f"Parent '{parent_name}' non trouvé au chemin {' > '.join(path)}")
            return False
        
        # Vérifier que le nouvel enfant n'existe pas déjà
        if parent_node.get_child(new_child_name):
            logger.error(f"L'enfant '{new_child_name}' existe déjà")
            return False
        
        # Sauvegarder tous les enfants existants
        existing_children = dict(parent_node.children)
        
        if not existing_children:
            logger.warning(f"Aucun enfant à décaler pour '{parent_name}'")
            # On peut quand même créer le nouvel enfant
            parent_node.add_child(new_child_name, parent_node.category)
            self._dirty = True
            return True
        
        # ÉTAPE 1: Créer le nouvel enfant intermédiaire
        new_child_node = parent_node.add_child(new_child_name, parent_node.category)
        
        # ÉTAPE 2: Déplacer tous les enfants existants sous le nouvel enfant
        for child_name, child_node in existing_children.items():
            new_child_node.children[child_name] = child_node
            # Supprimer de l'emplacement original
            if child_name in parent_node.children and child_name != new_child_name:
                del parent_node.children[child_name]
        
        self._dirty = True
        logger.info(f"✅ Nouvel enfant '{new_child_name}' créé, {len(existing_children)} enfants décalés")
        logger.info(f"   Structure: {' > '.join(full_path)} → {new_child_name} → [{', '.join(existing_children.keys())}]")
        
        return True

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