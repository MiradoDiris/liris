from typing import Dict, List, Any
from PyQt5.QtWidgets import QMessageBox
from utils.dataset_dgraph_manager import DgraphDatasetManager
from utils.logger import logger


class DatasetProjectManager:

    def __init__(self, database):
        self.database = database
        self.db = database
        self.dgraph_manager = DgraphDatasetManager
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
        """Sauvegarde le projet actuel dans la base de données - VERSION AVEC LOGGING"""
        logger.info("┌" + "─" * 78 + "┐")
        logger.info("│ PROJECT_MANAGER: save_project()                                              │")
        logger.info("└" + "─" * 78 + "┘")
        
        if not self.current_project_name or not self.current_project_data:
            logger.error("❌ PROJECT_MANAGER: Aucun projet à sauvegarder")
            logger.error(f"  - current_project_name: {self.current_project_name}")
            logger.error(f"  - current_project_data: {self.current_project_data is not None}")
            return False
        
        project_name = self.current_project_data.get('nom', self.current_project_name)
        logger.info(f"📝 PROJECT_MANAGER: Préparation de la sauvegarde")
        logger.info(f"  - Nom du projet: '{project_name}'")
        logger.info(f"  - Nombre de typologies: {len(self.current_project_data.get('typologies', []))}")
        
        # Statistiques sur le contenu
        typologies = self.current_project_data.get('typologies', [])
        total_clusters = sum(len(t.get('taxonomy_clusters', [])) for t in typologies)
        total_roots = sum(
            len(c.get('root_labels', []))
            for t in typologies
            for c in t.get('taxonomy_clusters', [])
        )
        total_parents = sum(
            len(r.get('parent_labels', []))
            for t in typologies
            for c in t.get('taxonomy_clusters', [])
            for r in c.get('root_labels', [])
        )
        
        logger.info(f"📊 PROJECT_MANAGER: Statistiques du contenu")
        logger.info(f"  - {len(typologies)} typologie(s)")
        logger.info(f"  - {total_clusters} cluster(s) de taxonomie")
        logger.info(f"  - {total_roots} root label(s)")
        logger.info(f"  - {total_parents} parent label(s)")
        
        logger.info(f"➡️  PROJECT_MANAGER: Appel de database.save_dataset_projet()")
        
        success = self.database.save_dataset_projet(project_name, self.current_project_data)
        
        if success:
            logger.info(f"✅ PROJECT_MANAGER: Sauvegarde réussie pour '{project_name}'")
        else:
            logger.error(f"❌ PROJECT_MANAGER: Échec de la sauvegarde pour '{project_name}'")
        
        return success
    
    def sync_project_to_dgraph(self, create_if_missing=True) -> bool:
        if not self.dgraph_manager:
            logger.warning("⚠️ Dgraph non configuré")
            return False

        if not self.current_project_data:
            logger.error("❌ Aucun projet chargé")
            return False

        try:
            logger.info(f"🔄 Début sync '{self.current_project_name}' → Dgraph")

            # 1️⃣ Vérifier si le projet existe dans Dgraph
            dgraph_project = self.dgraph_manager.get_project_by_name(self.current_project_name)

            if not dgraph_project and create_if_missing:
                # Créer le projet dans Dgraph
                project_uid = self.dgraph_manager.create_project(
                    self.current_project_name,
                    self.current_project_data.get('description', '')
                )

                if not project_uid:
                    logger.error("❌ Échec création projet Dgraph")
                    return False

                logger.info(f"✅ Projet créé dans Dgraph: {project_uid}")

            elif not dgraph_project:
                logger.error("❌ Projet n'existe pas dans Dgraph")
                return False

            # 2️⃣ Synchroniser la structure hiérarchique
            success = self._sync_hierarchy_to_dgraph()

            # 3️⃣ Synchroniser les prérequis
            if success:
                prereq_stats = self.dgraph_manager.sync_all_prerequisites_from_sqlite_to_dgraph(
                    self.current_project_name
                )
                logger.info(f"📊 Prérequis synchronisés: {prereq_stats}")

            logger.info(f"✅ Synchronisation terminée")
            return success

        except Exception as e:
            logger.error(f"❌ Erreur sync vers Dgraph: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    def sync_project_from_dgraph(self) -> bool:
        if not self.dgraph_manager:
            logger.warning("⚠️ Dgraph non configuré")
            return False

        if not self.current_project_name:
            logger.error("❌ Aucun projet actuel")
            return False

        try:
            logger.info(f"🔄 Début sync Dgraph → '{self.current_project_name}'")

            # 1️⃣ Récupérer le projet depuis Dgraph
            dgraph_project = self.dgraph_manager.get_project_by_name(self.current_project_name)

            if not dgraph_project:
                logger.error(f"❌ Projet '{self.current_project_name}' non trouvé dans Dgraph")
                return False

            # 2️⃣ Convertir la structure Dgraph en structure SQLite
            self.current_project_data = self._convert_dgraph_to_sqlite_structure(dgraph_project)

            # 3️⃣ Sauvegarder dans SQLite
            success = self.save_project()

            # 4️⃣ Synchroniser les prérequis
            if success:
                prereq_stats = self.dgraph_manager.sync_all_prerequisites_from_dgraph_to_sqlite(
                    self.current_project_name
                )
                logger.info(f"📊 Prérequis synchronisés: {prereq_stats}")

            logger.info(f"✅ Synchronisation depuis Dgraph terminée")
            return success

        except Exception as e:
            logger.error(f"❌ Erreur sync depuis Dgraph: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    def verify_sync_status(self) -> Dict[str, Any]:
        if not self.dgraph_manager:
            return {'status': 'error', 'message': 'Dgraph non configuré'}

        if not self.current_project_name:
            return {'status': 'error', 'message': 'Aucun projet actuel'}

        try:
            report = self.dgraph_manager.verify_sync_integrity(self.current_project_name)

            # Ajouter des statistiques SQLite
            sqlite_stats = self.database.get_sync_statistics()
            report['sqlite_stats'] = sqlite_stats

            logger.info(f"📊 Vérification sync: {report['status']}")
            return report

        except Exception as e:
            logger.error(f"❌ Erreur vérification: {e}")
            return {'status': 'error', 'message': str(e)}
        
    def add_prerequisite_to_label(self, level: str, source_name: str,
                              target_names: List[str], mandatory: bool = True,
                              explanation: str = "") -> bool:
        if not self.dgraph_manager:
            logger.warning("⚠️ Dgraph non configuré, prérequis SQLite seulement")
            return self._add_prerequisite_sqlite_only(level, source_name, target_names, mandatory, explanation)
        
        try:
            # 1️⃣ Récupérer les UIDs Dgraph
            source_uid = self._get_dgraph_uid_for_label(level, source_name)
            if not source_uid:
                logger.error(f"❌ UID source non trouvé pour '{source_name}'")
                return False
            
            target_uids = []
            for target_name in target_names:
                target_uid = self._get_dgraph_uid_for_label(level, target_name)
                if target_uid:
                    target_uids.append(target_uid)
                else:
                    logger.warning(f"⚠️ UID cible non trouvé pour '{target_name}'")
            
            if not target_uids:
                logger.error("❌ Aucun UID cible trouvé")
                return False
            
            # 2️⃣ Récupérer les IDs SQLite
            source_id = self._get_sqlite_id_for_label(level, source_name)
            target_ids = [self._get_sqlite_id_for_label(level, name) for name in target_names]
            
            # 3️⃣ Créer les prérequis avec sync automatique
            success = self.dgraph_manager.create_prerequisites_with_sync(
                source_uid=source_uid,
                target_uids=target_uids,
                mandatory=mandatory,
                explanation=explanation,
                source_type=level,
                source_id=source_id,
                target_type=level,
                target_ids=target_ids
            )
            
            if success:
                logger.info(f"✅ Prérequis ajouté: {source_name} → {target_names}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Erreur ajout prérequis: {e}")
            return False
    
    
    def remove_prerequisite_from_label(self, level: str, source_name: str,
                                       target_name: str) -> bool:
        """
        ✅ NOUVEAU: Supprime un prérequis (synchronisé SQLite + Dgraph)
        
        Args:
            level: 'root', 'parent', ou 'child'
            source_name: Nom du label source
            target_name: Nom du label cible
        
        Returns:
            True si succès
        """
        if not self.dgraph_manager:
            logger.warning("⚠️ Dgraph non configuré")
            return False
        
        try:
            # Récupérer les UIDs et IDs
            source_uid = self._get_dgraph_uid_for_label(level, source_name)
            target_uid = self._get_dgraph_uid_for_label(level, target_name)
            
            source_id = self._get_sqlite_id_for_label(level, source_name)
            target_id = self._get_sqlite_id_for_label(level, target_name)
            
            if not all([source_uid, target_uid, source_id, target_id]):
                logger.error("❌ UIDs/IDs manquants")
                return False
            
            # Supprimer avec sync
            success = self.dgraph_manager.remove_prerequisite_with_sync(
                source_uid, target_uid,
                level, source_id,
                level, target_id
            )
            
            # Suppression SQLite explicite
            if success and self.database:
                self.database.delete_single_prerequisite(level, source_id, level, target_id)
            
            if success:
                logger.info(f"✅ Prérequis supprimé: {source_name} -/-> {target_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression prérequis: {e}")
            return False
    
    
    def get_prerequisites_for_label(self, level: str, label_name: str) -> List[Dict]:
        """
        ✅ NOUVEAU: Récupère les prérequis d'un label
        
        Args:
            level: 'root', 'parent', ou 'child'
            label_name: Nom du label
        
        Returns:
            Liste des prérequis
        """
        if not self.dgraph_manager:
            # Fallback SQLite
            label_id = self._get_sqlite_id_for_label(level, label_name)
            if label_id:
                return self.database.get_prerequisites(level, label_id)
            return []
        
        try:
            # Récupérer depuis Dgraph
            label_uid = self._get_dgraph_uid_for_label(level, label_name)
            if not label_uid:
                return []
            
            prereqs = self.dgraph_manager.get_node_prerequisites(label_uid)
            
            # Enrichir avec les noms
            enriched = []
            for prereq in prereqs:
                enriched.append({
                    'uid': prereq.get('uid'),
                    'name': prereq.get('name'),
                    'type': prereq.get('dgraph.type'),
                    'mandatory': prereq.get('prerequisite|mandatory', True)
                })
            
            return enriched
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération prérequis: {e}")
            return []
    
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

    def permanent_delete_batches_and_combinations(self, confirm_callback=None):
        logger.info("=" * 80)
        logger.info("🗑️  SUPPRESSION DÉFINITIVE DES BATCHES")
        logger.info("=" * 80)
        
        if not self.current_project_name:
            logger.error("❌ Aucun projet actuel")
            return False
        
        logger.info(f"Projet: {self.current_project_name}")
        
        # Double confirmation si callback fourni
        if confirm_callback and not confirm_callback():
            logger.info("⚠️  Suppression annulée par l'utilisateur")
            return False
        
        try:
            # Compter d'abord pour information
            batches = self.database.get_all_batches(self.current_project_name)
            count = len(batches)
            
            logger.info(f"📊 {count} batch(es) à supprimer")
            
            if count == 0:
                logger.info("ℹ️  Aucun batch à supprimer")
                return True
            
            # Afficher le détail
            for batch in batches:
                data = batch.get('data', {})
                batch_name = data.get('batch_name', 'Sans nom')
                combo_count = data.get('count', 0)
                logger.info(f"  - Batch #{batch['batch_number']}: {batch_name} ({combo_count} combinaisons)")
            
            # Suppression définitive
            logger.info("\n🗑️  Suppression en cours...")
            success = self.database.delete_all_batches(self.current_project_name)
            
            if success:
                logger.info(f"✅ {count} batch(es) supprimé(s) définitivement")
                logger.info("=" * 80 + "\n")
                return True
            else:
                logger.error("❌ Échec de la suppression")
                logger.info("=" * 80 + "\n")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la suppression: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

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