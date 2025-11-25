import logging
from PyQt5.QtWidgets import QMessageBox
import traceback

from ui.localization.translator import tr

from utils.logger import logger


class DatasetProjectManager:
    """
    Gestionnaire de la logique métier pour les projets de datasets.
    Gère une structure hiérarchique dynamique et illimitée de labels.
    
    Structure:
    - Typologies (niveau fixe)
      └── Taxonomy Clusters (niveau fixe)
          └── Root Labels (niveau fixe)
              └── Parent Labels (niveau fixe)
                  └── Children (NIVEAU DYNAMIQUE INFINI)
                      └── Children
                          └── Children...
    """

    def __init__(self, database):
        self.database = database
        self.db = database
        self.current_project_name = None
        self.current_project_data = None
        
        # Navigation
        self.current_typologie_index = -1
        self.current_taxonomy_index = -1
        self.current_root_index = -1
        self.current_parent_index = -1
        # Chemin dans la hiérarchie des enfants (dynamique)
        self.children_path = []  # Liste des noms des enfants dans le chemin

    # ======== GESTION DES PROJETS ========
    
    def load_project(self, project_name):
        """Charge un projet existant depuis la base de données"""
        project_data = self.database.get_dataset_projet(project_name)
        if not project_data:
            return False

        self.current_project_name = project_name
        self.current_project_data = project_data
        self._reset_navigation()
        
        logger.info(f"Projet '{project_name}' chargé avec succès")
        return True

    def create_new_project(self, project_name, description=""):
        """Crée une nouvelle structure de projet"""
        if self.database.get_dataset_projet(project_name):
            logger.warning(f"Projet '{project_name}' existe déjà")
            return False

        self.current_project_name = project_name
        self.current_project_data = {
            "nom": project_name,
            "description": description,
            "typologies": []
        }
        self._reset_navigation()
        
        success = self.save_project()
        if success:
            logger.info(f"Nouveau projet '{project_name}' créé")
        return success

    def save_project(self):
        """Sauvegarde le projet actuel dans la base de données"""
        if not self.current_project_name or not self.current_project_data:
            logger.error("Aucun projet à sauvegarder")
            return False

        project_name = self.current_project_data.get('nom', self.current_project_name)
        success = self.database.save_dataset_projet(project_name, self.current_project_data)
        
        if success:
            logger.info(f"Projet '{project_name}' sauvegardé")
        else:
            logger.error(f"Échec sauvegarde projet '{project_name}'")
        
        return success

    def delete_project(self, project_name):
        """Supprime un projet"""
        success = self.database.delete_dataset_projet(project_name)
        if success and project_name == self.current_project_name:
            self.current_project_name = None
            self.current_project_data = None
            self._reset_navigation()
            logger.info(f"Projet '{project_name}' supprimé")
        return success

    def get_all_projects(self):
        """Récupère tous les projets"""
        return self.database.get_all_projects()

    def get_current_project_data(self):
        """Retourne les données du projet actuel"""
        return self.current_project_data

    def set_project_description(self, description):
        """Met à jour la description du projet"""
        if self.current_project_data:
            self.current_project_data['description'] = description

    # ======== NAVIGATION ========
    
    def _reset_navigation(self):
        """Réinitialise uniquement les indices de navigation du manager

        Note: Cette méthode ne gère que la logique métier.
        La réinitialisation de l'UI doit être faite dans le widget correspondant.
        """
        self.current_typologie_index = -1
        self.current_taxonomy_index = -1
        self.current_root_index = -1
        self.current_parent_index = -1
        self.children_path = []
        logger.debug("Navigation du project manager réinitialisée")

    def set_current_typologie_index(self, index):
        """Définit l'index de la typologie courante"""
        self.current_typologie_index = index
        self.current_taxonomy_index = -1
        self.current_root_index = -1
        self.current_parent_index = -1
        self.children_path = []

    def set_current_taxonomy_cluster(self, taxonomy_name):
        """Définit le cluster de taxonomie courant par son nom"""
        typologie = self.get_current_typologie()
        if not typologie:
            return False
        
        clusters = typologie.get('taxonomy_clusters', [])
        for idx, cluster in enumerate(clusters):
            if cluster.get('name') == taxonomy_name:
                self.current_taxonomy_index = idx
                self.current_root_index = -1
                self.current_parent_index = -1
                self.children_path = []
                return True
        return False

    def set_current_root_index(self, index):
        """Définit l'index du root label courant"""
        self.current_root_index = index
        self.current_parent_index = -1
        self.children_path = []

    def set_current_parent_index(self, index):
        """Définit l'index du parent label courant"""
        self.current_parent_index = index
        self.children_path = []

    def navigate_into_child(self, child_name):
        """Navigue dans un enfant spécifique"""
        self.children_path.append(child_name)
        logger.debug(f"Navigation dans enfant '{child_name}', profondeur: {len(self.children_path)}")

    def navigate_up(self):
        """Remonte d'un niveau dans la hiérarchie des enfants"""
        if self.children_path:
            removed = self.children_path.pop()
            logger.debug(f"Remonté depuis '{removed}', profondeur: {len(self.children_path)}")
            return True
        return False

    def reset_children_navigation(self):
        """Réinitialise la navigation dans les enfants"""
        self.children_path = []

    def get_current_depth(self):
        """Retourne la profondeur actuelle dans la hiérarchie des enfants"""
        return len(self.children_path)

    def get_current_hierarchy_path(self):
        """Retourne le chemin complet des enfants"""
        return self.children_path.copy()
    
    def save_batch(self, batch_number, total_batches, batch_data):
        """Sauvegarde un batch pour le projet actuel"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return False

        return self.database.save_batch(
            self.current_project_name,
            batch_number,
            total_batches,
            batch_data
        )
    
    def get_batch(self, batch_number):
        """Récupère un batch du projet actuel"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return None

        return self.database.get_batch(self.current_project_name, batch_number)
    
    def get_all_batches(self):
        """Récupère tous les batches du projet actuel"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return []

        return self.database.get_all_batches(self.current_project_name)
    
    def update_batch_status(self, batch_number, status):
        """Met à jour le statut d'un batch"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return False

        return self.database.update_batch_status(
            self.current_project_name,
            batch_number,
            status
        )
    
    def clear_all_batches(self):
        """Supprime tous les batches du projet actuel"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return False
        
        return self.database.delete_all_batches(self.current_project_name)
    
    def delete_batch(self, batch_number):
        """Supprime un batch"""
        if not self.current_project_name:
            logger.error("Aucun projet actuel")
            return False

        return self.database.delete_batch(self.current_project_name, batch_number)

    def get_breadcrumb_path(self):
        """Retourne le chemin complet pour l'affichage breadcrumb"""
        path_names = []
        
        typologie = self.get_current_typologie()
        if typologie:
            path_names.append(typologie.get('name', ''))
        
        taxonomy = self.get_current_taxonomy()
        if taxonomy:
            path_names.append(taxonomy.get('name', ''))
        
        root = self.get_current_root()
        if root:
            path_names.append(root.get('name', ''))
        
        parent = self.get_current_parent()
        if parent:
            path_names.append(parent.get('name', ''))
        
        # Ajouter le chemin des enfants
        path_names.extend(self.children_path)
        
        return ' > '.join(path_names) if path_names else 'Root'

    # ======== GESTION DES TYPOLOGIES ========
    
    def add_typologie(self, typologie_name, parent_widget=None):
        """Ajoute une nouvelle typologie"""
        if not typologie_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom de la typologie ne peut pas être vide")
            return False

        if not self.current_project_data:
            self.current_project_data = {"typologies": []}

        typologies = self.current_project_data.setdefault('typologies', [])
        existing_names = [t.get('name') for t in typologies]
        
        if typologie_name in existing_names:
            if parent_widget:
                QMessageBox.warning(parent_widget, "Doublon",
                                    f"La typologie '{typologie_name}' existe déjà")
            return False

        new_typologie = {
            'name': typologie_name,
            'description': '',
            'taxonomy_clusters': []
        }
        typologies.append(new_typologie)
        logger.info(f"Typologie '{typologie_name}' ajoutée")
        return True

    def edit_typologie(self, old_name, new_name, parent_widget=None):
        """Édite le nom d'une typologie"""
        if not new_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        typologies = self.current_project_data.get('typologies', [])
        for typologie in typologies:
            if typologie.get('name') == old_name:
                existing_names = [t.get('name') for t in typologies if t != typologie]
                if new_name in existing_names:
                    if parent_widget:
                        QMessageBox.warning(parent_widget, "Doublon",
                                            f"La typologie '{new_name}' existe déjà")
                    return False
                typologie['name'] = new_name
                logger.info(f"Typologie renommée: '{old_name}' -> '{new_name}'")
                return True
        return False

    def remove_typologie(self, typologie_name):
        """Supprime une typologie"""
        typologies = self.current_project_data.get('typologies', [])
        for i, typologie in enumerate(typologies):
            if typologie.get('name') == typologie_name:
                del typologies[i]
                if self.current_typologie_index == i:
                    self._reset_navigation()
                logger.info(f"Typologie '{typologie_name}' supprimée")
                return True
        return False

    def get_typologies(self):
        """Retourne la liste des typologies"""
        return self.current_project_data.get('typologies', []) if self.current_project_data else []

    def get_current_typologie(self):
        """Retourne la typologie actuellement sélectionnée"""
        typologies = self.get_typologies()
        if 0 <= self.current_typologie_index < len(typologies):
            return typologies[self.current_typologie_index]
        return None

    # ======== GESTION DES TAXONOMY CLUSTERS ========
    
    def get_current_taxonomy(self):
        """Retourne le cluster de taxonomie actuellement sélectionné"""
        typologie = self.get_current_typologie()
        if not typologie:
            return None
        
        clusters = typologie.get('taxonomy_clusters', [])
        if 0 <= self.current_taxonomy_index < len(clusters):
            return clusters[self.current_taxonomy_index]
        return None

    # ======== GESTION DES ROOT LABELS ========
    
    def add_root_label(self, label_name, parent_widget=None):
        """Ajoute un root label"""
        if not label_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        taxonomy = self.get_current_taxonomy()
        if not taxonomy:
            logger.warning("Aucun cluster de taxonomie sélectionné")
            return False

        root_labels = taxonomy.setdefault('root_labels', [])
        existing_names = [l.get('name') for l in root_labels]
        
        if label_name in existing_names:
            if parent_widget:
                QMessageBox.warning(parent_widget, "Doublon",
                                    f"Le label '{label_name}' existe déjà")
            return False

        new_label = {
            'name': label_name,
            'description': '',
            'category': 'default',
            'parent_labels': []
        }
        root_labels.append(new_label)
        logger.info(f"Root label '{label_name}' ajouté")
        return True

    def edit_root_label(self, old_name, new_name, parent_widget=None):
        """Édite un root label"""
        if not new_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        root_labels = self.get_root_labels()
        for label in root_labels:
            if label.get('name') == old_name:
                existing_names = [l.get('name') for l in root_labels if l != label]
                if new_name in existing_names:
                    if parent_widget:
                        QMessageBox.warning(parent_widget, "Doublon",
                                            f"Le label '{new_name}' existe déjà")
                    return False
                label['name'] = new_name
                logger.info(f"Root label renommé: '{old_name}' -> '{new_name}'")
                return True
        return False

    def remove_root_label(self, label_name):
        """Supprime un root label"""
        taxonomy = self.get_current_taxonomy()
        if not taxonomy:
            return False

        root_labels = taxonomy.get('root_labels', [])
        for i, label in enumerate(root_labels):
            if label.get('name') == label_name:
                del root_labels[i]
                if self.current_root_index == i:
                    self.current_root_index = -1
                    self.current_parent_index = -1
                    self.children_path = []
                logger.info(f"Root label '{label_name}' supprimé")
                return True
        return False

    def get_root_labels(self):
        """Retourne les root labels du cluster de taxonomie actuel"""
        taxonomy = self.get_current_taxonomy()
        return taxonomy.get('root_labels', []) if taxonomy else []

    def get_current_root(self):
        """Retourne le root label actuellement sélectionné"""
        root_labels = self.get_root_labels()
        if 0 <= self.current_root_index < len(root_labels):
            return root_labels[self.current_root_index]
        return None

    # ======== GESTION DES PARENT LABELS ========
    
    def add_parent_label(self, label_name, parent_widget=None):
        """Ajoute un parent label"""
        if not label_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        root = self.get_current_root()
        if not root:
            return False

        parent_labels = root.setdefault('parent_labels', [])
        existing_names = [l.get('name') for l in parent_labels]
        
        if label_name in existing_names:
            if parent_widget:
                QMessageBox.warning(parent_widget, "Doublon",
                                    f"Le label '{label_name}' existe déjà")
            return False

        new_label = {
            'name': label_name,
            'description': '',
            'category': 'default',
            'children': []
        }
        parent_labels.append(new_label)
        logger.info(f"Parent label '{label_name}' ajouté")
        return True

    def edit_parent_label(self, old_name, new_name, parent_widget=None):
        """Édite un parent label"""
        if not new_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        parent_labels = self.get_parent_labels()
        for label in parent_labels:
            if label.get('name') == old_name:
                existing_names = [l.get('name') for l in parent_labels if l != label]
                if new_name in existing_names:
                    if parent_widget:
                        QMessageBox.warning(parent_widget, "Doublon",
                                            f"Le label '{new_name}' existe déjà")
                    return False
                label['name'] = new_name
                logger.info(f"Parent label renommé: '{old_name}' -> '{new_name}'")
                return True
        return False

    def remove_parent_label(self, label_name):
        """Supprime un parent label"""
        root = self.get_current_root()
        if not root:
            return False

        parent_labels = root.get('parent_labels', [])
        for i, label in enumerate(parent_labels):
            if label.get('name') == label_name:
                del parent_labels[i]
                if self.current_parent_index == i:
                    self.current_parent_index = -1
                    self.children_path = []
                logger.info(f"Parent label '{label_name}' supprimé")
                return True
        return False

    def get_parent_labels(self):
        """Retourne les parent labels du root actuel"""
        root = self.get_current_root()
        return root.get('parent_labels', []) if root else []

    def get_current_parent(self):
        """Retourne le parent label actuellement sélectionné"""
        parent_labels = self.get_parent_labels()
        if 0 <= self.current_parent_index < len(parent_labels):
            return parent_labels[self.current_parent_index]
        return None

    # ======== GESTION DYNAMIQUE DES CHILDREN (HIÉRARCHIE INFINIE) ========
    
    def _get_current_children_container(self):
        """
        Récupère le conteneur des enfants au niveau actuel
        Retourne: (children_list, parent_dict)
        """
        parent = self.get_current_parent()
        if not parent:
            return None, None

        # Si pas de chemin, on est au premier niveau d'enfants
        if not self.children_path:
            return parent.get('children', []), parent

        # Naviguer dans la hiérarchie des enfants par nom
        current_children = parent.get('children', [])
        current_container = parent
        
        for child_name in self.children_path:
            # Chercher l'enfant par nom
            found = False
            for child in current_children:
                if child.get('name') == child_name:
                    current_container = child
                    current_children = child.get('children', [])
                    found = True
                    break
            
            if not found:
                logger.error(f"Enfant '{child_name}' non trouvé dans le chemin")
                return None, None
        
        return current_children, current_container

    def add_child_label(self, label_name, parent_widget=None):
        """Ajoute un enfant au niveau actuel de la hiérarchie"""
        if not label_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        children_list, container = self._get_current_children_container()
        if children_list is None:
            return False

        existing_names = [l.get('name') for l in children_list]
        
        if label_name in existing_names:
            if parent_widget:
                QMessageBox.warning(parent_widget, "Doublon",
                                    f"Le label '{label_name}' existe déjà")
            return False

        new_child = {
            'name': label_name,
            'description': '',
            'category': 'default',
            'children': []
        }
        
        if 'children' not in container:
            container['children'] = []
        
        container['children'].append(new_child)
        depth = len(self.children_path)
        logger.info(f"Child label '{label_name}' ajouté au niveau {depth}")
        return True

    def edit_child_label(self, old_name, new_name, parent_widget=None):
        """Édite un enfant au niveau actuel"""
        if not new_name.strip():
            if parent_widget:
                QMessageBox.warning(parent_widget, "Nom invalide",
                                    "Le nom ne peut pas être vide")
            return False

        children_list, _ = self._get_current_children_container()
        if not children_list:
            return False

        for child in children_list:
            if child.get('name') == old_name:
                existing_names = [l.get('name') for l in children_list if l != child]
                if new_name in existing_names:
                    if parent_widget:
                        QMessageBox.warning(parent_widget, "Doublon",
                                            f"Le label '{new_name}' existe déjà")
                    return False
                child['name'] = new_name
                depth = len(self.children_path)
                logger.info(f"Child label renommé au niveau {depth}: '{old_name}' -> '{new_name}'")
                return True
        return False

    def remove_child_label(self, label_name):
        """Supprime un enfant au niveau actuel"""
        children_list, container = self._get_current_children_container()
        if not children_list:
            return False

        for i, child in enumerate(children_list):
            if child.get('name') == label_name:
                del container['children'][i]
                depth = len(self.children_path)
                logger.info(f"Child label '{label_name}' supprimé au niveau {depth}")
                return True
        return False

    def get_children_at_current_level(self):
        """Retourne les enfants au niveau actuel"""
        children_list, _ = self._get_current_children_container()
        return children_list if children_list else []

    def has_children(self):
        """Vérifie si le niveau actuel a des enfants"""
        children = self.get_children_at_current_level()
        return len(children) > 0

    # ======== MODIFICATION DE CATÉGORIE ========
    
    def modify_label_category(self, level, new_category):
        """Modifie la catégorie d'un label"""
        if level == "root":
            label = self.get_current_root()
        elif level == "parent":
            label = self.get_current_parent()
        elif level == "child":
            # Trouver l'enfant actuel dans le chemin
            if not self.children_path:
                return False
            children_list, _ = self._get_current_children_container()
            # On modifie le dernier dans le chemin? Cela dépend de votre logique
            # Pour l'instant, on ne supporte pas cette modification
            logger.warning("Modification de catégorie pour child non implémentée")
            return False
        else:
            return False

        if label:
            label['category'] = new_category
            logger.info(f"Catégorie du {level} mise à jour: {new_category}")
            return True
        return False

    # ======== SYNCHRONISATION AVEC LE CACHE ========
    
    def update_from_hierarchy_cache(self, cache_data):
        """
        Met à jour le projet depuis les données du cache hiérarchique
        cache_data est le dictionnaire retourné par HierarchyCache.to_dict()
        """
        if not self.current_project_data:
            logger.error("Aucun projet actuel pour la mise à jour")
            return False
        
        # Le cache_data devrait avoir une structure comme:
        # {typologie_name: {taxonomy_name: [root1, root2, ...], ...}, ...}
        
        typologies = []
        for typ_name, taxonomy_dict in cache_data.items():
            typologie = {
                'name': typ_name,
                'description': '',
                'taxonomy_clusters': []
            }
            
            for tax_name, roots in taxonomy_dict.items():
                cluster = {
                    'name': tax_name,
                    'description': '',
                    'root_labels': self._build_hierarchy_from_cache(roots)
                }
                typologie['taxonomy_clusters'].append(cluster)
            
            typologies.append(typologie)
        
        self.current_project_data['typologies'] = typologies
        logger.info("Projet mis à jour depuis le cache hiérarchique")
        return True

    def _build_hierarchy_from_cache(self, cache_structure):
        """Construit récursivement la hiérarchie depuis le cache"""
        # À adapter selon la structure exacte de votre cache
        # Cette méthode devrait transformer les données du cache en structure de projet
        return []
    

    # ======== EXPORT ========
    
    def export_strategy(self, export_dir="exports"):
        """Exporte la stratégie du projet"""
        import json
        import os
        from datetime import datetime

        if not self.current_project_data or not self.current_project_name:
            return False

        os.makedirs(export_dir, exist_ok=True)
        filename = os.path.join(export_dir, f"{self.current_project_name}_strategy.json")
        
        export_data = {
            'project_info': self.current_project_data,
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Stratégie exportée vers : {filename}")
        return True