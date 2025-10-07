# relation_import_widget.py (Version Complète Corrigée - Enregistrement Relations dans Dgraph)
import os
import re
import ast
import time
import json
from typing import List, Dict
from collections import defaultdict
import uuid

from utils.dgraph_connector import LirisDgraphConnector

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from utils.logger import logger


class ResultsDialog(QtWidgets.QDialog):
    """
    Dialogue pour afficher et exécuter les mutations de relations d'import.
    """

    def __init__(self, generated_mutations, dgraph_connector, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Résultats - Relations d'Import")
        self.setMinimumSize(700, 500)
        self.generated_mutations = generated_mutations
        self.dgraph_connector = dgraph_connector
        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        title_label = QtWidgets.QLabel("Mutations de Relations d'Import Générées")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QtWidgets.QWidget()
        self.results_layout = QtWidgets.QVBoxLayout(scroll_content_widget)
        self.results_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_content_widget)
        main_layout.addWidget(scroll_area)

        self._populate_results()

        execute_all_button = QtWidgets.QPushButton("Exécuter toutes les mutations")
        execute_all_button.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0c0c0;
            }
            QPushButton:pressed {
                background-color: #a0a0a0;
            }
        """)
        execute_all_button.clicked.connect(self._on_execute_all)
        main_layout.addWidget(execute_all_button, alignment=Qt.AlignCenter)

    def _populate_results(self):
        for result in self.generated_mutations:
            file_name = result.get("file_name", "Fichier inconnu")
            mutations = result.get("mutations", [])

            file_row_layout = QtWidgets.QHBoxLayout()
            file_row_layout.setSpacing(10)

            file_label = QtWidgets.QLabel(f"<b>Fichier:</b> {file_name} ({len(mutations)} mutations)")
            file_label.setMinimumWidth(200)
            file_row_layout.addWidget(file_label)
            file_row_layout.addStretch()

            view_button = QtWidgets.QPushButton("Voir détails")
            view_button.clicked.connect(lambda checked, m=mutations, n=file_name: self._show_mutations_dialog(m, n))
            view_button.setStyleSheet("""
                QPushButton {
                    background-color: #17a2b8;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #138496;
                }
            """)
            file_row_layout.addWidget(view_button)

            execute_button = QtWidgets.QPushButton("Exécuter")
            execute_button.clicked.connect(lambda checked, m=mutations, n=file_name: self._on_execute_mutations(m, n))
            execute_button.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """)
            file_row_layout.addWidget(execute_button)

            self.results_layout.addLayout(file_row_layout)

    def _show_mutations_dialog(self, mutations, file_name):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Mutations pour {file_name}")
        dialog.setMinimumSize(600, 400)

        layout = QtWidgets.QVBoxLayout(dialog)
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)

        mutations_text = f"Nombre de mutations : {len(mutations)}\n\n"
        for i, mutation in enumerate(mutations, 1):
            mutations_text += f"=== Mutation {i} ===\n{json.dumps(mutation, indent=2, ensure_ascii=False)}\n\n"

        text_edit.setPlainText(mutations_text)
        layout.addWidget(text_edit)

        close_button = QtWidgets.QPushButton("Fermer")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)
        dialog.exec_()

    def _on_execute_mutations(self, mutations, file_name):
        """Exécute mutations avec validation préalable et gestion d'erreurs détaillée."""
        if not mutations:
            QtWidgets.QMessageBox.information(self, "Exécution", "Aucune mutation à exécuter.")
            return
        
        # Validation avant insertion
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, '_log'):
            parent_widget._log(f"Validation de {len(mutations)} mutations pour '{file_name}'...")
        
        valid_mutations = []
        for mutation in mutations:
            if parent_widget and hasattr(parent_widget, '_validate_mutation_structure'):
                if parent_widget._validate_mutation_structure(mutation):
                    valid_mutations.append(mutation)
            else:
                valid_mutations.append(mutation)
        
        if not valid_mutations:
            QtWidgets.QMessageBox.warning(self, "Validation", f"Aucune mutation valide pour '{file_name}'.")
            return
        
        try:
            success = self.dgraph_connector.insert_mutations(valid_mutations)
            if success:
                QtWidgets.QMessageBox.information(
                    self, "Succès", 
                    f"{len(valid_mutations)} mutations pour '{file_name}' exécutées avec succès !"
                )
                logger.info(f"Mutations pour {file_name} exécutées : {len(valid_mutations)} mutations")
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Erreur", 
                    f"Échec de l'exécution des mutations pour '{file_name}'.\nVoir logs pour détails."
                )
        except Exception as e:
            logger.error(f"Erreur exécution mutations: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Erreur", 
                f"Erreur lors de l'exécution: {str(e)}\n\nVoir logs pour détails complets."
            )

    def _on_execute_all(self):
        """Exécute toutes les mutations avec suivi détaillé."""
        if not self.generated_mutations:
            QtWidgets.QMessageBox.information(self, "Exécution", "Aucune mutation à exécuter.")
            return
        
        total_mutations = 0
        successful_files = []
        failed_files = []
        
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, '_log'):
            parent_widget._log(f"Début exécution globale : {len(self.generated_mutations)} fichiers")
        
        for result in self.generated_mutations:
            file_name = result.get("file_name")
            mutations = result.get("mutations", [])
            
            # Validation
            valid_mutations = mutations
            if parent_widget and hasattr(parent_widget, '_validate_mutation_structure'):
                valid_mutations = [m for m in mutations if parent_widget._validate_mutation_structure(m)]
            
            if not valid_mutations:
                failed_files.append(f"{file_name} (validation échouée)")
                continue
            
            try:
                success = self.dgraph_connector.insert_mutations(valid_mutations)
                if success:
                    total_mutations += len(valid_mutations)
                    successful_files.append(file_name)
                else:
                    failed_files.append(f"{file_name} (insertion échouée)")
            except Exception as e:
                failed_files.append(f"{file_name} ({str(e)[:50]})")
                logger.error(f"Erreur pour {file_name}: {e}", exc_info=True)
        
        # Rapport final détaillé
        report = f"Mutations réussies: {total_mutations}\n"
        report += f"Fichiers traités: {len(successful_files)}/{len(self.generated_mutations)}\n\n"
        
        if successful_files:
            report += "Succès:\n" + "\n".join([f"  - {f}" for f in successful_files[:5]])
            if len(successful_files) > 5:
                report += f"\n  ... et {len(successful_files) - 5} autres"
        
        if failed_files:
            report += f"\n\nErreurs ({len(failed_files)}):\n"
            report += "\n".join([f"  - {f}" for f in failed_files[:5]])
            if len(failed_files) > 5:
                report += f"\n  ... et {len(failed_files) - 5} autres"
            
            QtWidgets.QMessageBox.warning(self, "Exécution partielle", report)
        else:
            QtWidgets.QMessageBox.information(self, "Succès complet", report)


class RelationImportWidget(QtWidgets.QWidget):
    def __init__(self, config_provider=None, conductor=None, dgraph_connector=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor
        self.dgraph_connector = dgraph_connector or LirisDgraphConnector(auto_reset=False)
        self.current_workspace = None
        self.current_clusters = []
        self.current_labels = {}
        self.name_to_uid = {}
        self.pending_relations = []
        self._init_ui()
        
        if self.dgraph_connector and self.dgraph_connector.client:
            self._load_workspaces()
        else:
            self._log("Connecteur Dgraph non disponible.")

    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Message d'information en haut
        info_label = QtWidgets.QLabel(
            "Gestion des Relations d'Import - Récupération depuis Dgraph"
        )
        info_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                color: #333;
            }
        """)
        main_layout.addWidget(info_label)

        # Label guide
        guide_label = QtWidgets.QLabel("Sélectionnez un workspace, puis un cluster ou label à configurer pour les relations.")
        guide_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-style: italic;
                padding: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #007bff;
            }
        """)
        main_layout.addWidget(guide_label)

        # Workspace et Cluster sur la même ligne
        selection_group = QtWidgets.QGroupBox("Sélection Workspace/Cluster")
        selection_layout = QtWidgets.QHBoxLayout(selection_group)
        
        # Workspace
        selection_layout.addWidget(QtWidgets.QLabel("Workspace:"))
        self.workspace_combo = QtWidgets.QComboBox()
        self.workspace_combo.setMinimumWidth(200)
        self.workspace_combo.currentIndexChanged.connect(self._on_workspace_selected)
        selection_layout.addWidget(self.workspace_combo)
        
        # Cluster
        selection_layout.addWidget(QtWidgets.QLabel("Cluster:"))
        self.cluster_combo = QtWidgets.QComboBox()
        self.cluster_combo.setMinimumWidth(200)
        self.cluster_combo.currentIndexChanged.connect(self._on_cluster_selected)
        selection_layout.addWidget(self.cluster_combo)
        
        # Bouton de rafraîchissement
        refresh_button = QtWidgets.QPushButton("Rafraîchir")
        refresh_button.setMaximumWidth(100)
        refresh_button.setToolTip("Rafraîchir les données depuis Dgraph")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #d0d0d0;
                color: #333;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #b0b0d0;
            }
        """)
        refresh_button.clicked.connect(self._load_workspaces)
        selection_layout.addWidget(refresh_button)
        
        # Bouton diagnostic
        diag_button = QtWidgets.QPushButton("Test Connexion")
        diag_button.setMaximumWidth(120)
        diag_button.setToolTip("Tester la connexion et diagnostiquer les problèmes")
        diag_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        diag_button.clicked.connect(self._run_diagnostics)
        selection_layout.addWidget(diag_button)
        
        main_layout.addWidget(selection_group)

        # Liste des fichiers/labels et Logs côte à côte
        content_splitter = QtWidgets.QHBoxLayout()
        
        # Colonne gauche: Liste des clusters/labels à configurer
        files_group = QtWidgets.QGroupBox("Clusters/Labels à Configurer")
        files_layout = QtWidgets.QVBoxLayout(files_group)
        self.file_list_widget = QtWidgets.QListWidget()
        self.file_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list_widget.itemSelectionChanged.connect(self._on_file_selection_changed)
        files_layout.addWidget(self.file_list_widget)
        content_splitter.addWidget(files_group, 1)
        
        # Colonne droite: Logs
        log_group = QtWidgets.QGroupBox("Logs d'Activité")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        content_splitter.addWidget(log_group, 1)
        
        main_layout.addLayout(content_splitter)

        # Section de configuration des relations
        relations_group = QtWidgets.QGroupBox("Configuration des Relations")
        relations_layout = QtWidgets.QVBoxLayout(relations_group)
        
        # Ligne 1: Type de relation + Fichier source
        config_line1 = QtWidgets.QHBoxLayout()
        config_line1.addWidget(QtWidgets.QLabel("Type:"))
        self.relation_type_combo = QtWidgets.QComboBox()
        self.relation_type_combo.addItems([
            "import", "heritage", "extend", "implement", 
            "depends_on", "calls", "uses", "references"
        ])
        self.relation_type_combo.setMinimumWidth(120)
        config_line1.addWidget(self.relation_type_combo)
        
        config_line1.addWidget(QtWidgets.QLabel("Source:"))
        self.source_file_label = QtWidgets.QLabel("Sélectionner 1 cluster/label source")
        self.source_file_label.setStyleSheet("color: #666; font-style: italic;")
        self.source_file_label.setMinimumWidth(250)
        config_line1.addWidget(self.source_file_label, 1)
        relations_layout.addLayout(config_line1)
        
        # Ligne 2: Fichier cible + Bouton ajouter
        config_line2 = QtWidgets.QHBoxLayout()
        config_line2.addWidget(QtWidgets.QLabel("Cible:"))
        self.target_file_combo = QtWidgets.QComboBox()
        self.target_file_combo.setMinimumWidth(300)
        config_line2.addWidget(self.target_file_combo, 1)
        
        add_relation_button = QtWidgets.QPushButton("Ajouter Relation")
        add_relation_button.setMaximumWidth(150)
        add_relation_button.setToolTip("Ajouter cette relation")
        add_relation_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        add_relation_button.clicked.connect(self._on_add_relation)
        config_line2.addWidget(add_relation_button)
        relations_layout.addLayout(config_line2)
        
        # Liste des relations
        relations_header = QtWidgets.QHBoxLayout()
        relations_header.addWidget(QtWidgets.QLabel("Relations à Créer:"))
        remove_relation_button = QtWidgets.QPushButton("Supprimer")
        remove_relation_button.setMaximumWidth(100)
        remove_relation_button.setToolTip("Supprimer la relation sélectionnée")
        remove_relation_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        remove_relation_button.clicked.connect(self._on_remove_relation)
        relations_header.addWidget(remove_relation_button)
        relations_layout.addLayout(relations_header)
        
        self.relations_list_widget = QtWidgets.QListWidget()
        self.relations_list_widget.setMaximumHeight(100)
        relations_layout.addWidget(self.relations_list_widget)
        
        main_layout.addWidget(relations_group)
        
        # Bouton de génération
        self.generate_button = QtWidgets.QPushButton("Générer et Appliquer Relations")
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #fff;
            }
        """)
        self.generate_button.clicked.connect(self._on_generate_relations)
        self.generate_button.setEnabled(False)
        main_layout.addWidget(self.generate_button, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)

    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"
        logger.info(message)
        self.log_area.append(log_message)
        QtWidgets.QApplication.processEvents()

    def _show_error(self, title, message):
        """Affiche une boîte de dialogue d'erreur et log"""
        self._log(f"ERREUR: {message}")
        QtWidgets.QMessageBox.critical(self, title, message)
    
    def _show_info(self, title, message):
        """Affiche une boîte d'info et log"""
        self._log(f"INFO: {message}")
        QtWidgets.QMessageBox.information(self, title, message)

    def _run_diagnostics(self):
        """Exécute des tests de diagnostic complets sur la connexion Dgraph."""
        self._log("=== DIAGNOSTIC CONNEXION DGRAPH ===")
        
        diag_results = []
        all_ok = True
        
        # 1. Test du connecteur
        if not self.dgraph_connector:
            diag_results.append("Connecteur Dgraph non initialisé")
            all_ok = False
        else:
            diag_results.append("Connecteur Dgraph initialisé")
            
            # 2. Test du client
            if not self.dgraph_connector.client:
                diag_results.append("Client Dgraph non connecté")
                all_ok = False
            else:
                diag_results.append("Client Dgraph connecté")
                
                # 3. Test de query simple
                try:
                    test_query = """
                    {
                      q(func: has(dgraph.type)) {
                        count(uid)
                      }
                    }
                    """
                    txn = self.dgraph_connector.client.txn(read_only=True)
                    resp = txn.query(test_query)
                    txn.discard()
                    data = json.loads(resp.json if isinstance(resp.json, str) else resp.json.decode('utf-8'))
                    diag_results.append(f"Query test réussie: {data}")
                except Exception as e:
                    diag_results.append(f"Query test échouée: {str(e)}")
                    logger.error(f"Erreur query test: {e}", exc_info=True)
                    all_ok = False
                
                # 4. Test du schéma
                try:
                    schema = self.dgraph_connector.get_current_schema()
                    if schema:
                        diag_results.append("Schéma récupéré")
                        # Vérifier les predicates essentiels
                        required_preds = ['imports', 'relations', 'functions', 'calls', 'name', 'clusterManagement']
                        for pred in required_preds:
                            if pred in schema:
                                diag_results.append(f"  Predicate '{pred}' présent")
                            else:
                                diag_results.append(f"  ATTENTION: Predicate '{pred}' manquant")
                    else:
                        diag_results.append("Schéma vide ou non récupéré")
                except Exception as e:
                    diag_results.append(f"Erreur récupération schéma: {str(e)}")
                    logger.error(f"Erreur schéma: {e}", exc_info=True)
                    all_ok = False
                
                # 5. Test des workspaces (avec détails)
                try:
                    self._log("\n--- Test query workspaces détaillé ---")
                    ws_data = self.dgraph_connector.query_workspaces()
                    
                    diag_results.append(f"\nRéponse raw type: {type(ws_data)}")
                    
                    if ws_data:
                        diag_results.append(f"Clés réponse: {list(ws_data.keys()) if isinstance(ws_data, dict) else 'N/A'}")
                        
                        if isinstance(ws_data, dict) and 'q' in ws_data:
                            ws_list = ws_data['q']
                            ws_count = len(ws_list) if isinstance(ws_list, list) else 0
                            diag_results.append(f"{ws_count} workspace(s) trouvé(s)")
                            
                            # Détails du premier workspace
                            if ws_count > 0 and isinstance(ws_list, list):
                                first_ws = ws_list[0]
                                diag_results.append(f"\nPremier workspace:")
                                diag_results.append(f"  Type: {type(first_ws)}")
                                if isinstance(first_ws, dict):
                                    diag_results.append(f"  Clés: {list(first_ws.keys())}")
                                    diag_results.append(f"  Name: {first_ws.get('name', 'N/A')}")
                                    diag_results.append(f"  UID: {first_ws.get('uid', 'N/A')}")
                                    
                                    cm = first_ws.get('clusterManagement')
                                    diag_results.append(f"  clusterManagement type: {type(cm)}")
                                    if isinstance(cm, dict):
                                        diag_results.append(f"  clusterManagement clés: {list(cm.keys())}")
                                        clusters = cm.get('clusters', [])
                                        diag_results.append(f"  Nombre clusters: {len(clusters) if isinstance(clusters, list) else 'N/A'}")
                        else:
                            diag_results.append("Clé 'q' absente ou ws_data non-dict")
                    else:
                        diag_results.append("Aucune donnée workspace (None ou vide)")
                        
                except Exception as e:
                    diag_results.append(f"Erreur query workspaces: {str(e)}")
                    logger.error(f"Erreur workspaces: {e}", exc_info=True)
                    all_ok = False
        
        # 6. État du widget
        diag_results.append(f"\nÉtat du widget:")
        diag_results.append(f"  Labels chargés: {len(self.current_labels)}")
        diag_results.append(f"  Relations en attente: {len(self.pending_relations)}")
        diag_results.append(f"  Workspace actuel: {self.current_workspace.get('name', 'Aucun') if self.current_workspace else 'Aucun'}")
        
        # Affichage
        report = "\n".join(diag_results)
        self._log(report)
        
        if all_ok:
            QtWidgets.QMessageBox.information(
                self, "Diagnostic", 
                f"Tous les tests ont réussi !\n\n{report}"
            )
        else:
            QtWidgets.QMessageBox.warning(
                self, "Diagnostic", 
                f"Problèmes détectés\n\n{report}\n\nVérifiez que Dgraph est démarré (docker-compose up)"
            )

    def _validate_uid_exists(self, uid):
        """Vérifie qu'un UID existe dans les labels chargés ou dans Dgraph."""
        # Vérification rapide dans les labels chargés
        if uid in self.current_labels:
            return True
        
        # Vérification dans Dgraph si disponible
        if not self.dgraph_connector or not self.dgraph_connector.client:
            self._log(f"Impossible de valider UID {uid[:8]}... (pas de connexion)")
            return False
        
        try:
            query = f"""
            {{
              q(func: uid({uid})) {{
                uid
                dgraph.type
              }}
            }}
            """
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = json.loads(resp.json if isinstance(resp.json, str) else resp.json.decode('utf-8'))
            exists = len(data.get('q', [])) > 0
            
            if not exists:
                self._log(f"UID {uid[:8]}... n'existe pas dans Dgraph")
            
            return exists
        except Exception as e:
            logger.error(f"Erreur validation UID {uid}: {e}")
            return False

    def _validate_mutation_structure(self, mutation):
        """Valide la structure d'une mutation avant insertion."""
        if not isinstance(mutation, dict):
            self._log("Mutation non-dict rejetée")
            return False
        
        if 'uid' not in mutation:
            self._log("Mutation sans UID rejetée")
            return False
        
        # Vérifier qu'il y a au moins un predicate autre que 'uid'
        predicates = [k for k in mutation.keys() if k != 'uid']
        if not predicates:
            self._log(f"Mutation {mutation.get('uid')} sans predicates rejetée")
            return False
        
        return True

    def _on_file_selection_changed(self):
        """Met à jour la section relations quand un cluster/label est sélectionné"""
        selected_items = self.file_list_widget.selectedItems()
        
        if len(selected_items) == 1:
            uid = selected_items[0].data(Qt.UserRole)
            label_info = self.current_labels.get(uid)
            if label_info:
                ws_name = self.current_workspace.get('name', 'N/A') if self.current_workspace else 'N/A'
                display = f"{label_info['name']} - {label_info['cluster']} ({ws_name})"
                self.source_file_label.setText(display)
                self.source_file_label.setStyleSheet("color: #28a745; font-weight: bold;")
                self._populate_target_files(uid)
                self._log(f"Source sélectionné: {display}")
        else:
            self.source_file_label.setText("Sélectionnez 1 cluster/label source")
            self.source_file_label.setStyleSheet("color: #dc3545; font-style: italic;")
            self.target_file_combo.clear()
    
    def _populate_target_files(self, exclude_uid):
        """Affiche les cibles uniques avec workspace"""
        self.target_file_combo.clear()
        self.target_file_combo.addItem("-- Sélectionner une cible --", None)
        ws_name = self.current_workspace.get('name', 'N/A') if self.current_workspace else 'N/A'
        seen_names = set()
        for uid, label_info in self.current_labels.items():
            if uid != exclude_uid:
                name = label_info['name']
                display = f"{name} ({label_info['cluster']}, {ws_name})"
                if name in seen_names:
                    display += f" ({uid[:8]})"
                else:
                    seen_names.add(name)
                self.target_file_combo.addItem(display, uid)
        self._log(f"{self.target_file_combo.count() - 1} cibles disponibles")
    
    def _on_add_relation(self):
        """Ajoute une relation à la liste"""
        selected_items = self.file_list_widget.selectedItems()
        if len(selected_items) != 1:
            self._show_error("Sélection Source", "Sélectionnez exactement 1 source.")
            return
        
        source_uid = selected_items[0].data(Qt.UserRole)
        source_info = self.current_labels.get(source_uid)
        
        target_uid = self.target_file_combo.currentData()
        if not target_uid:
            self._show_error("Sélection Cible", "Sélectionnez une cible.")
            return
        
        target_info = self.current_labels.get(target_uid)
        relation_type = self.relation_type_combo.currentText()
        
        relation = {
            'source_uid': source_uid,
            'source_name': source_info['name'],
            'target_uid': target_uid,
            'target_name': target_info['name'],
            'relation_type': relation_type
        }
        
        # Vérif doublon par UID et nom
        if any(r['source_uid'] == source_uid and r['target_uid'] == target_uid and r['relation_type'] == relation_type for r in self.pending_relations):
            self._show_info("Doublon", "Relation déjà ajoutée.")
            return
        
        if any(r['source_name'] == relation['source_name'] and r['target_name'] == relation['target_name'] and r['relation_type'] == relation_type for r in self.pending_relations):
            self._show_info("Doublon", "Relation avec ces noms déjà ajoutée.")
            return
        
        self.pending_relations.append(relation)
        
        display_text = f"{relation_type.upper()}: {source_info['name']} ({source_info['cluster']}) -> {target_info['name']} ({target_info['cluster']})"
        item = QtWidgets.QListWidgetItem(display_text)
        item.setData(Qt.UserRole, relation)
        self.relations_list_widget.addItem(item)
        
        self._log(f"Relation ajoutée: {display_text}")
    
    def _on_remove_relation(self):
        """Supprime relation sélectionnée"""
        current_item = self.relations_list_widget.currentItem()
        if not current_item:
            self._show_error("Suppression", "Sélectionnez une relation à supprimer.")
            return
        
        relation = current_item.data(Qt.UserRole)
        self.pending_relations.remove(relation)
        self.relations_list_widget.takeItem(self.relations_list_widget.currentRow())
        self._log(f"Relation supprimée: {relation['source_name']} -> {relation['target_name']}")

    def _load_workspaces(self):
        """Charge les workspaces depuis Dgraph avec gestion d'erreurs améliorée"""
        self._log("Chargement des workspaces depuis Dgraph...")
        self.workspace_combo.clear()
        self.workspace_combo.addItem("Chargement en cours...")
        
        if not self.dgraph_connector:
            self._log("ERREUR: Connecteur Dgraph manquant")
            self.workspace_combo.clear()
            self.workspace_combo.addItem("Erreur: Pas de connecteur")
            return
        
        if not self.dgraph_connector.client:
            self._log("ERREUR: Client Dgraph non connecté")
            self.workspace_combo.clear()
            self.workspace_combo.addItem("Erreur: Connexion Dgraph")
            return
        
        try:
            # Appel avec gestion d'exception
            data = self.dgraph_connector.query_workspaces()
            
            # Log raw data pour debug
            logger.info(f"RAW DATA query_workspaces: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if not data:
                self._log("Réponse Dgraph vide ou None")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Aucun workspace trouvé")
                self.generate_button.setEnabled(False)
                return
            
            # Vérification structure de réponse
            if not isinstance(data, dict):
                self._log(f"ERREUR: Réponse non-dict, type: {type(data)}")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Erreur: Format réponse invalide")
                self.generate_button.setEnabled(False)
                return
            
            self._log(f"Données reçues: clés = {list(data.keys())}")
            
            if 'q' not in data:
                self._log("ERREUR: Clé 'q' absente de la réponse")
                self._log(f"Clés disponibles: {list(data.keys())}")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Erreur: Structure réponse incorrecte")
                self.generate_button.setEnabled(False)
                return
            
            workspaces = data['q']
            
            if not workspaces:
                self._log("Aucun workspace dans la réponse Dgraph (liste vide)")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Aucun workspace disponible")
                self.generate_button.setEnabled(False)
                return
            
            if not isinstance(workspaces, list):
                self._log(f"ERREUR: 'q' n'est pas une liste, type: {type(workspaces)}")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Erreur: Format données invalide")
                self.generate_button.setEnabled(False)
                return
            
            self._log(f"Traitement de {len(workspaces)} workspace(s)")
            
            self.workspace_combo.clear()
            self.workspace_combo.addItem("-- Sélectionner un workspace --")
            
            total_clusters = 0
            total_labels = 0
            valid_workspaces = 0
            
            for i, ws in enumerate(workspaces):
                try:
                    if not isinstance(ws, dict):
                        self._log(f"Workspace {i} invalide (non-dict), type: {type(ws)}")
                        continue
                    
                    ws_name = ws.get('name', f'Sans nom {i}')
                    ws_desc = ws.get('description', '')
                    
                    # Vérification clusterManagement
                    cm = ws.get('clusterManagement')
                    if not cm:
                        self._log(f"Workspace '{ws_name}': pas de clusterManagement")
                        clusters = []
                    elif isinstance(cm, dict):
                        clusters = cm.get('clusters', [])
                    else:
                        self._log(f"Workspace '{ws_name}': clusterManagement invalide, type: {type(cm)}")
                        clusters = []

                    if ws_desc and ws_desc.strip():
                        display_text = f"{ws_name} - {ws_desc[:40]}"
                    else:
                        display_text = ws_name

                    self.workspace_combo.addItem(display_text, ws)
                    valid_workspaces += 1

                    num_clusters = len(clusters) if isinstance(clusters, list) else 0
                    num_labels = 0
                    
                    if isinstance(clusters, list):
                        for cluster in clusters:
                            if isinstance(cluster, dict):
                                root_labels = cluster.get('root_labels', [])
                                if isinstance(root_labels, list):
                                    labels = self._count_labels_recursively(root_labels)
                                    num_labels += labels
                    
                    total_clusters += num_clusters
                    total_labels += num_labels

                    if ws_desc and ws_desc.strip():
                        self._log(f"  -> {ws_name} ({ws_desc[:30]}): {num_clusters} clusters, {num_labels} labels")
                    else:
                        self._log(f"  -> {ws_name}: {num_clusters} clusters, {num_labels} labels")
                
                except Exception as e:
                    self._log(f"Erreur traitement workspace {i}: {str(e)}")
                    logger.error(f"Erreur workspace {i}: {e}", exc_info=True)
                    continue
            
            if valid_workspaces == 0:
                self._log("ERREUR: Aucun workspace valide trouvé")
                self.workspace_combo.clear()
                self.workspace_combo.addItem("Aucun workspace valide")
                self.generate_button.setEnabled(False)
            else:
                self._log(f"Chargement réussi: {valid_workspaces} workspaces, {total_clusters} clusters, {total_labels} labels")
                self.generate_button.setEnabled(False)
                                  
        except Exception as e:
            self._log(f"ERREUR CRITIQUE chargement workspaces: {str(e)}")
            logger.error(f"Détails erreur complète: {e}", exc_info=True)
            self.workspace_combo.clear()
            self.workspace_combo.addItem("Erreur de chargement")
            self.generate_button.setEnabled(False)

    def _count_labels_recursively(self, labels, count=0):
        """Compte tous les labels/fichiers récursivement"""
        for label in labels or []:
            count += 1
            level = label.get('level', 0)
            if level == 0:
                subs = label.get('parents', [])
            else:
                subs = label.get('children', [])
            count += self._count_labels_recursively(subs)
        return count

    def _on_workspace_selected(self, index):
        """Gère sélection workspace"""
        self._log(f"Sélection workspace index {index}")
        self.file_list_widget.clear()
        self.cluster_combo.clear()
        self.cluster_combo.addItem("Tous les clusters")
        self.current_labels = {}
        self.name_to_uid = {}
        self.generate_button.setEnabled(False)

        if index <= 0:
            return

        self.current_workspace = self.workspace_combo.itemData(index)
        if self.current_workspace is None:
            self._log(f"Erreur: Données workspace manquantes pour index {index}")
            return

        if not isinstance(self.current_workspace, dict):
            self._log("Erreur: Données workspace invalides (non-dict)")
            return

        ws_name = self.current_workspace.get('name', 'Sans nom')
        ws_desc = self.current_workspace.get('description', '')

        if ws_desc:
            self._log(f"Workspace sélectionné: {ws_name} - {ws_desc}")
        else:
            self._log(f"Workspace sélectionné: {ws_name}")

        cm = self.current_workspace.get('clusterManagement', {})
        clusters = cm.get('clusters', [])
        self.current_clusters = clusters

        if not clusters:
            self._log("Aucun cluster dans ce workspace")
            return

        for cluster in clusters:
            cluster_name = cluster.get('name', 'Sans nom')
            display = f"{cluster_name} ({len(self._get_all_labels_from_cluster(cluster))} labels)"
            self.cluster_combo.addItem(display, cluster)

        self._log(f"{len(clusters)} clusters disponibles")
        self._on_cluster_selected(0)
    
    def _get_all_labels_from_cluster(self, cluster):
        """Helper: Récup tous labels d'un cluster"""
        return self._extract_labels_recursively(cluster.get('root_labels', []))

    def _extract_labels_recursively(self, labels):
        """Extrait tous labels récursivement"""
        all_labels = []
        for label in labels:
            all_labels.append(label)
            level = label.get('level', 0)
            if level == 0:
                subs = label.get('parents', [])
            else:
                subs = label.get('children', [])
            all_labels.extend(self._extract_labels_recursively(subs))
        return all_labels

    def _on_cluster_selected(self, index):
        """Gère sélection cluster"""
        self.file_list_widget.clear()
        self.current_labels = {}
        self.name_to_uid = {}
        self._log(f"Sélection cluster index {index}")
        
        if index == 0:
            self._load_all_files()
        else:
            cluster = self.cluster_combo.itemData(index)
            if cluster:
                self._load_files_from_cluster(cluster)
        
        num_loaded = len(self.current_labels)
        self.generate_button.setEnabled(num_loaded > 0)
        self._log(f"{num_loaded} clusters/labels chargés")

    def _load_all_files(self):
        """Charge tous clusters/labels du workspace"""
        total_loaded = 0
        for cluster in self.current_clusters:
            loaded = self._load_files_from_cluster(cluster)
            total_loaded += loaded
        self._log(f"Total chargé: {total_loaded} éléments")

    def _load_files_from_cluster(self, cluster):
        """Charge labels d'un cluster"""
        cluster_name = cluster.get('name', 'Sans nom')
        root_labels = cluster.get('root_labels', [])
        loaded_count = 0
        
        self._log(f"Chargement de '{cluster_name}': {len(root_labels)} root labels")
        
        for label in root_labels:
            loaded = self._process_label(label, cluster_name)
            loaded_count += loaded
        
        if loaded_count == 0:
            self._log(f"Aucun élément dans '{cluster_name}'")
        return loaded_count

    def _process_label(self, label, cluster_name, level=0):
        """Traite un label"""
        actual_level = label.get('level', level)
        node_type = label.get('nodeType', 'unknown')
        uid = label.get('uid')

        if not uid:
            self._log(f"Label sans UID ignoré (level {actual_level})")
            return 0

        if uid in self.current_labels:
            return 0

        name = label.get('name', f"Label L{actual_level}")
        path = label.get('path', '')
        description = label.get('description', '')

        file_contents_str = label.get('fileContents', '{}')
        try:
            file_contents = json.loads(file_contents_str) if file_contents_str else {}
        except Exception as e:
            logger.warning(f"Erreur parse fileContents pour {name}: {e}")
            file_contents = {}

        code = ''
        if isinstance(file_contents, dict):
            code = file_contents.get('content', file_contents.get('code', ''))
        else:
            code = str(file_contents)

        code = label.get('codeContent', code) or code

        if name in self.name_to_uid:
            return 0

        self.name_to_uid[name] = uid

        self.current_labels[uid] = {
            'uid': uid,
            'name': name,
            'path': path,
            'cluster': cluster_name,
            'codeContent': code,
            'description': description,
            'nodeType': node_type,
            'level': actual_level
        }

        ws_name = self.current_workspace.get('name', 'N/A') if self.current_workspace else 'N/A'

        display_parts = [name, f"[{node_type.upper()}]", cluster_name, f"({ws_name})"]

        if description and description.strip():
            display_parts.insert(1, f"- {description[:30]}...")

        indent = "  " * actual_level
        display_text = indent + " ".join(display_parts)

        item = QtWidgets.QListWidgetItem(display_text)
        item.setData(Qt.UserRole, uid)
        self.file_list_widget.addItem(item)

        loaded_count = 1

        if actual_level < 10:
            if actual_level == 0:
                subs = label.get('parents', [])
            else:
                subs = label.get('children', [])
            for sub in subs:
                loaded = self._process_label(sub, cluster_name, actual_level + 1)
                loaded_count += loaded

        return loaded_count

    def _on_generate_relations(self):
        """Génère mutations"""
        selected_items = self.file_list_widget.selectedItems()
        
        if not selected_items:
            self._show_error("Génération", "Sélectionnez au moins 1 cluster/label.")
            return
        
        if self.pending_relations:
            recap = "\n".join([f"  {r['relation_type'].upper()}: {r['source_name']} -> {r['target_name']}" for r in self.pending_relations])
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmer Relations",
                f"Récap relations:\n{recap}\n\nTotal: {len(self.pending_relations)}\nContinuer génération?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
        
        self._log(f"Génération pour {len(selected_items)} éléments sélectionnés")
        
        generated_mutations = []
        ws_name = self.current_workspace.get('name', 'N/A') if self.current_workspace else 'N/A'
        for item in selected_items:
            uid = item.data(Qt.UserRole)
            label_info = self.current_labels.get(uid)
            if label_info:
                mutations = self._generate_mutations_for_file(label_info)
                if mutations:
                    file_name = f"{label_info['name']} ({label_info['cluster']}, {ws_name})"
                    generated_mutations.append({
                        'file_name': file_name,
                        'mutations': mutations
                    })
                    self._log(f"  -> {len(mutations)} mutations générées pour {file_name}")
        
        if generated_mutations:
            dialog = ResultsDialog(generated_mutations, self.dgraph_connector, self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.pending_relations.clear()
                self.relations_list_widget.clear()
                self._log("Génération terminée - Relations réinitialisées")
        else:
            self._show_info("Génération Vide", "Aucune mutation générée.")

    def _generate_mutations_for_file(self, label_info):
        """Génère mutations avec structure correcte pour Dgraph"""
        code_content = label_info.get('codeContent', '')
        uid = label_info['uid']
        source_name = label_info['name']
        
        mutation = {'uid': uid}
        has_changes = False
    
        # 1. Extraction fonctions
        functions = self._extract_functions_detailed(code_content)
        if functions:
            func_nodes = [
                {
                    'uid': f"_:func_{uid}_{f['name']}", 
                    'dgraph.type': 'Function', 
                    'name': f['name'], 
                    'description': f['docstring']
                } 
                for f in functions
            ]
            mutation['functions'] = func_nodes
            has_changes = True
            self._log(f"  -> {len(functions)} functions extraites pour {source_name}")
    
        # 2. Collecte des targets par type
        relations_by_type = defaultdict(set)
    
        # Auto-imports
        auto_imports = self._extract_imports(code_content)
        for imp in auto_imports:
            target_name = imp['module']
            base_name = target_name.split('.')[-1].lower()
            target_uid = next(
                (u for n, u in self.name_to_uid.items() if n.lower() == base_name),
                None
            )
            if target_uid and self._validate_uid_exists(target_uid):
                relations_by_type['imports'].add(target_uid)
                self._log(f"  -> Auto-import: {source_name} -> {target_name}")
    
        # Relations manuelles
        for r in self.pending_relations:
            if r['source_uid'] == uid:
                if self._validate_uid_exists(r['target_uid']):
                    pred_name = r['relation_type']
                    if pred_name == 'import':
                        pred_name = 'imports'
                    relations_by_type[pred_name].add(r['target_uid'])
                    self._log(f"  -> Relation manuelle: {source_name} ({pred_name}) -> {r['target_name']}")
                else:
                    self._log(f"  UID cible invalide: {r['target_uid']}")
    
        # 3. Ajout des relations
        for rel_type, target_uids in relations_by_type.items():
            if target_uids:
                mutation[rel_type] = [{'uid': t} for t in target_uids]
                has_changes = True
                self._log(f"  -> {len(target_uids)} cibles pour '{rel_type}'")
    
        if has_changes:
            logger.info(f"Mutation pour {source_name}: {json.dumps(mutation, indent=2)}")
            return [mutation]
        else:
            return None
    
    def _extract_imports(self, content: str) -> List[Dict]:
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({'module': alias.name})
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    if module:
                        imports.append({'module': module})
        except SyntaxError as e:
            self._log(f"Erreur syntaxe imports: {e}")
        return imports
    
    def _extract_functions_detailed(self, content: str) -> List[Dict]:
        functions = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    docstring = ast.get_docstring(node) or ""
                    functions.append({'name': node.name, 'docstring': docstring})
        except SyntaxError as e:
            self._log(f"Erreur syntaxe functions: {e}")
        return functions

    def refresh(self):
        """Rafraîchit tout"""
        self._log("Rafraîchissement complet...")
        self._load_workspaces()