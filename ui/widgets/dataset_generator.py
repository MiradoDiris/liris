import json
import logging
import os
import sqlite3
import sys
import random
from collections import defaultdict
from datetime import datetime
import time
import itertools

import google.generativeai as genai
import pandas as pd
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

TEMPLATES = {
    'simple': {
        'prompt_suffix': "Génère un échantillon de données simple avec des champs : question, réponse, contexte.",
        'output_structure': {'question': '', 'réponse': '', 'contexte': ''}
    },
    'complex': {
        'prompt_suffix': "Génère un échantillon de données complexe avec des champs : instruction, input, output, metadata (incluant batch_path et typologie_combination).",
        'output_structure': {'instruction': '', 'input': '', 'output': '', 'metadata': {}}
    }
}

GEMINI_API_KEY = "AIzaSyDSKsAtCIsE5UVYLwA4a5PTyIpPVUBV3pc"


class DatasetGenerator:
    def __init__(self, strategy_widget, generator_widget, api_key=GEMINI_API_KEY):
        self.strategy_widget = strategy_widget
        self.generator_widget = generator_widget
        self.db_connection = None
        self.api_key = api_key
        self._init_database()
        self.model = self._init_gemini_api()

    def _init_database(self):
        """Initialise ou réinitialise la connexion à la base de données."""
        try:
            db_path = os.path.join("data", "liris.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.db_connection = sqlite3.connect(db_path)
            self.db_connection.row_factory = sqlite3.Row
            logger.info(f"Base de données connectée : {db_path}")
        except Exception as e:
            logger.error(f"Erreur initialisation DB : {str(e)}")
            self.db_connection = None
            raise

    def _init_gemini_api(self):
        """Initialise l'API Gemini."""
        if not self.api_key:
            raise ValueError("Clé API Gemini manquante. Fournissez une clé valide.")
        os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = ""
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("API Gemini initialisée avec succès")
        return model

    def _ensure_db_connection(self):
        """Vérifie si la connexion est ouverte, sinon la rouvre."""
        if self.db_connection is None:
            self._init_database()
        try:
            self.db_connection.execute("SELECT 1")
        except (sqlite3.ProgrammingError, AttributeError):
            logger.warning("Connexion DB fermée ou invalide, réinitialisation.")
            self._init_database()

    def load_project_data(self, project_name):
        """Charge les données du projet depuis la base de données."""
        self._ensure_db_connection()
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Projet '{project_name}' non trouvé dans la DB.")

            project_data = {'nom': row['name'], 'description': row['description'] or ''}
            if row['data']:
                try:
                    json_data = json.loads(row['data'])
                    project_data.update(json_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur JSON pour '{project_name}': {e}")

            # Charger les batches depuis dataset_batches
            cursor.execute("SELECT * FROM dataset_batches WHERE project_name = ?", (project_name,))
            batch_rows = cursor.fetchall()

            project_data['batches'] = {}
            for row in batch_rows:
                project_data['batches'][row['batch_name']] = {
                    'count': row['sample_count'],
                    'percentage': row['percentage'],
                    'typologie_combination': row['typologie_combination']
                }

            logger.info(f"Chargé {len(project_data['batches'])} batches pour le projet '{project_name}'")
            return project_data

        except Exception as e:
            logger.error(f"Erreur lors du chargement des données du projet '{project_name}': {str(e)}")
            raise

    def generate_all_combinations(self, project_data):
        """
        Génère TOUTES les combinaisons possibles entre TOUTES les typologies.
        Chaque combinaison croise les éléments de différentes typologies.
        """
        typologies = project_data.get('typologies', [])

        if not typologies:
            raise ValueError("Aucune typologie définie dans le projet")

        # Pour chaque typologie, récupérer tous ses chemins jusqu'au niveau parent
        typologie_paths = {}

        for typologie in typologies:
            typologie_name = typologie.get('name', 'Unknown')
            paths = []

            # Récupérer tous les chemins root et root/parent
            root_labels = typologie.get('root_labels', [])
            for root in root_labels:
                root_name = root.get('name', 'Root')
                # Ajouter le root seul
                paths.append({
                    'path': f"{typologie_name}/{root_name}",
                    'level': 'root',
                    'typologie': typologie_name
                })

                # Ajouter root/parent
                parent_labels = root.get('parent_labels', [])
                for parent in parent_labels:
                    parent_name = parent.get('name', 'Parent')
                    paths.append({
                        'path': f"{typologie_name}/{root_name}/{parent_name}",
                        'level': 'parent',
                        'typologie': typologie_name
                    })

            if paths:
                typologie_paths[typologie_name] = paths

        if not typologie_paths:
            raise ValueError("Aucun chemin généré depuis les typologies")

        # Générer toutes les combinaisons entre typologies
        all_combinations = []
        typologie_names = list(typologie_paths.keys())

        # Si une seule typologie, retourner ses chemins
        if len(typologie_names) == 1:
            for path_info in typologie_paths[typologie_names[0]]:
                all_combinations.append({
                    'path': path_info['path'],
                    'typologie_combination': typologie_names[0],
                    'categories': self._parse_path_to_categories(path_info['path'])
                })
        else:
            # Combiner toutes les typologies entre elles
            for combo in itertools.product(*[typologie_paths[typ] for typ in typologie_names]):
                # combo est un tuple de path_info
                combined_path = ' + '.join([p['path'] for p in combo])
                typologie_combo = ' + '.join([p['typologie'] for p in combo])

                all_combinations.append({
                    'path': combined_path,
                    'typologie_combination': typologie_combo,
                    'categories': {
                        f'typologie_{i + 1}': p['path']
                        for i, p in enumerate(combo)
                    }
                })

        logger.info(f"Généré {len(all_combinations)} combinaisons multi-typologies")
        return all_combinations

    def _parse_path_to_categories(self, path):
        """Parse un chemin en structure de catégories"""
        parts = path.split('/')
        categories = {}

        if len(parts) >= 1:
            categories['typologie'] = parts[0]
        if len(parts) >= 2:
            categories['root'] = parts[1]
        if len(parts) >= 3:
            categories['parent'] = parts[2]
        if len(parts) >= 4:
            categories['child'] = parts[3]

        return categories

    def build_prompt(self, combo, template, sample_count, augment=False):
        """Construit le prompt pour l'API Gemini avec le contexte complet de la combinaison."""
        config = self.generator_widget.config_data
        platform = config['platform'] if config['platform'] != 'Personnalisée' else config['custom_platform']

        # Extraire les informations de la combinaison
        typologie_combo = combo.get('typologie_combination', 'Unknown')
        path = combo.get('path', '')

        base_prompt = (
            f"Génère exactement {sample_count} échantillons de dataset pour la combinaison de contextes suivante:\n\n"
            f"COMBINAISON DE TYPOLOGIES: {typologie_combo}\n"
            f"CHEMIN COMPLET: {path}\n"
            f"CATÉGORIES: {combo.get('categories', {})}\n\n"
            f"Description du projet: {config['description']}\n"
            f"Plateforme: {platform}\n"
            f"Technique d'entraînement: {config['training_technique']}\n\n"
            f"IMPORTANT: Chaque échantillon doit refléter la COMBINAISON COMPLÈTE des typologies.\n"
            f"Par exemple, si la combinaison est 'Language utilisé + Domaine', chaque échantillon doit "
            f"traiter à la fois du langage de programmation ET du domaine d'application spécifiés.\n\n"
            f"Format de sortie attendu: JSON valide avec les champs instruction, input, output, metadata.\n"
            f"Les metadata doivent contenir:\n"
            f"  - batch_path: '{path}'\n"
            f"  - typologie_combination: '{typologie_combo}'\n"
            f"  - categories détaillées\n\n"
            f"Assure-toi que la réponse est un JSON valide contenant exactement {sample_count} échantillons."
        )

        base_prompt += TEMPLATES[template]['prompt_suffix']

        if augment:
            base_prompt += "\n\nApplique des variations aléatoires (paraphrases, synonymes, modifications contextuelles) pour l'augmentation des données."

        return base_prompt

    def generate_data_with_gemini(self, prompt, expected_count):
        """Génère des données via l'API Gemini."""
        all_data = []
        remaining = expected_count
        max_attempts = 5
        max_samples_per_request = 2  # Réduit encore pour la fiabilité
        attempts = 0

        while remaining > 0 and attempts < max_attempts:
            current_request_count = min(remaining, max_samples_per_request)
            adjusted_prompt = prompt.replace(f"exactement {expected_count}", f"exactement {current_request_count}")

            try:
                logger.debug(
                    f"Tentative {attempts + 1}/{max_attempts} pour générer {current_request_count} échantillons")
                response = self.model.generate_content(adjusted_prompt)
                data_text = response.text.strip('```json').strip('```').strip()
                logger.debug(f"Réponse reçue ({len(data_text)} caractères)")

                data_text = data_text.replace('\n', '').replace('\r', '')

                try:
                    samples = json.loads(data_text)
                    if not isinstance(samples, list):
                        samples = [samples]

                    all_data.extend(samples)
                    remaining -= len(samples)
                    logger.info(f"Généré {len(samples)} échantillons, reste {remaining}")
                    attempts = 0  # Reset attempts on success
                    time.sleep(1)  # Pause entre requêtes

                except json.JSONDecodeError as e:
                    logger.error(f"Erreur JSON : {str(e)}")
                    attempts += 1
                    time.sleep(2)

            except Exception as e:
                logger.error(f"Erreur Gemini : {str(e)}")
                attempts += 1
                time.sleep(2)

        if not all_data:
            logger.warning(f"Aucun échantillon généré après {max_attempts} tentatives")
            # Retourner au moins un échantillon vide pour éviter l'erreur totale
            return [{
                'instruction': f'Échantillon généré par défaut',
                'input': '',
                'output': '',
                'metadata': {}
            }] * min(expected_count, 1)

        return all_data[:expected_count]

    def save_dataset(self, data, output_file, output_format, project_data, batch_statistics):
        """Sauvegarde le dataset dans le format spécifié avec statistiques complètes."""
        output_path = f"{output_file}.{output_format.lower()}"
        export_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        if 'nom' not in project_data:
            project_data['nom'] = self.generator_widget.current_project_name or 'Projet sans nom'

        if 'description' not in project_data:
            project_data['description'] = ''

        # Regrouper les samples par batch
        batches_output = defaultdict(list)
        for sample in data:
            batch_path = sample.get('metadata', {}).get('batch_path', 'unknown')
            batches_output[batch_path].append(sample)

        # Structurer la sortie selon les spécifications
        output_data = {
            'project_info': {
                'nom': project_data['nom'],
                'description': project_data['description'],
                'typologies': project_data.get('typologies', [])
            },
            'dataset_statistics': batch_statistics,
            'batches': [
                {
                    'batch_id': idx + 1,
                    'batch_name': batch_name,
                    'typologie_combination': batches_output[batch_name][0].get('metadata', {}).get(
                        'typologie_combination', 'Unknown') if batches_output[batch_name] else 'Unknown',
                    'context_path': batch_name,
                    'sample_count': len(batches_output[batch_name]),
                    'samples': batches_output[batch_name]
                }
                for idx, batch_name in enumerate(sorted(batches_output.keys()))
            ],
            'export_timestamp': export_timestamp
        }

        if output_format.lower() == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
        elif output_format.lower() == 'csv':
            df = pd.DataFrame(data)
            df.to_csv(output_path, index=False, encoding='utf-8')
        elif output_format.lower() == 'parquet':
            df = pd.DataFrame(data)
            df.to_parquet(output_path, index=False)
        else:
            raise ValueError(f"Format de sortie non supporté : {output_format}")

        logger.info(f"Dataset sauvegardé : {output_path}")

    def generate(self, lots=1, samples_per_lot=100, template='complex', augment=False, output_file="dataset_output",
                 existing_file=None):
        """Génère un dataset avec la structure de batches combinés demandée."""
        if not self.generator_widget.current_project_name:
            QtWidgets.QMessageBox.warning(self.generator_widget, "Aucun Projet",
                                          "Veuillez sélectionner un projet avant de lancer la génération.")
            return

        config = self.generator_widget.config_data
        output_format = config['output_format']
        total_samples = config['sample_count']

        logger.info(f"Démarrage génération: {total_samples} échantillons demandés")

        project_data = self.load_project_data(self.generator_widget.current_project_name)
        if not project_data:
            QtWidgets.QMessageBox.warning(self.generator_widget, "Aucune Donnée", "Aucune donnée de projet disponible.")
            return

        batches = project_data.get('batches', {})

        # SI AUCUN BATCH CONFIGURÉ, générer les combinaisons automatiquement
        if not batches:
            logger.info("Aucun batch configuré, génération automatique des combinaisons")
            all_combinations = self.generate_all_combinations(project_data)

            # Distribution uniforme
            samples_per_combo = total_samples // len(all_combinations)
            remainder = total_samples % len(all_combinations)

            batch_distribution = {}
            for i, combo in enumerate(all_combinations):
                extra = 1 if i < remainder else 0
                batch_distribution[combo['path']] = {
                    'count': samples_per_combo + extra,
                    'typologie_combination': combo['typologie_combination']
                }
        else:
            # UTILISER LES BATCHES CONFIGURÉS
            logger.info(f"Utilisation de {len(batches)} batches configurés")
            all_combinations = self.generate_all_combinations(project_data)

            # Mapper les batches configurés aux combinaisons
            batch_distribution = {}
            total_configured = sum(b['count'] for b in batches.values())

            # Si total configuré != total demandé, ajuster proportionnellement
            if total_configured != total_samples:
                logger.warning(f"Total configuré ({total_configured}) != demandé ({total_samples}), ajustement...")
                adjustment_factor = total_samples / total_configured if total_configured > 0 else 1
            else:
                adjustment_factor = 1.0

            for combo in all_combinations:
                # Trouver le batch correspondant
                matching_batch = None
                for batch_name, batch_info in batches.items():
                    if combo['path'] == batch_name or (combo['path'] in batch_name) or (batch_name in combo['path']):
                        matching_batch = batch_info
                        break

                if matching_batch:
                    adjusted_count = int(matching_batch['count'] * adjustment_factor)
                else:
                    # Distribution minimale pour les non-configurés
                    adjusted_count = max(1, total_samples // (len(all_combinations) * 10))

                if adjusted_count > 0:
                    batch_distribution[combo['path']] = {
                        'count': adjusted_count,
                        'typologie_combination': combo['typologie_combination']
                    }

        # Vérifier et ajuster le total
        actual_total = sum(b['count'] for b in batch_distribution.values())
        logger.info(f"Distribution calculée: {actual_total} échantillons sur {len(batch_distribution)} batches")

        if actual_total != total_samples:
            # Ajuster le premier batch pour atteindre le total exact
            diff = total_samples - actual_total
            first_batch = list(batch_distribution.keys())[0]
            batch_distribution[first_batch]['count'] = max(1, batch_distribution[first_batch]['count'] + diff)
            logger.info(f"Ajustement: +{diff} échantillons au batch '{first_batch}'")

        progress_dialog = QtWidgets.QProgressDialog("Génération du dataset en cours...", "Annuler", 0, total_samples,
                                                    self.generator_widget)
        progress_dialog.setWindowTitle("Génération du Dataset")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        all_data = []
        progress = 0

        try:
            # Calculer les statistiques finales
            batch_statistics = {
                'total_batches': len(batch_distribution),
                'total_samples': sum(b['count'] for b in batch_distribution.values()),
                'samples_per_batch': total_samples // len(batch_distribution) if batch_distribution else 0,
                'batch_distribution': {
                    batch_name: info['count']
                    for batch_name, info in batch_distribution.items()
                }
            }

            # Génération pour chaque combinaison
            for combo_path, info in tqdm(batch_distribution.items(), desc="Génération des batches"):
                if progress_dialog.wasCanceled():
                    logger.info("Génération annulée par l'utilisateur.")
                    return

                current_samples = info['count']

                if current_samples <= 0:
                    continue

                logger.info(f"Génération batch: {combo_path} ({current_samples} échantillons)")

                # Trouver la combinaison complète
                matching_combo = None
                for combo in all_combinations:
                    if combo['path'] == combo_path:
                        matching_combo = combo
                        break

                if not matching_combo:
                    logger.warning(f"Combinaison non trouvée pour {combo_path}, skip")
                    continue

                try:
                    prompt = self.build_prompt(matching_combo, template, current_samples, augment=augment)
                    samples = self.generate_data_with_gemini(prompt, current_samples)

                    # Enrichir les metadata
                    for sample in samples:
                        sample['metadata'] = sample.get('metadata', {})
                        sample['metadata']['batch_path'] = combo_path
                        sample['metadata']['typologie_combination'] = info['typologie_combination']
                        sample['metadata'].update(matching_combo.get('categories', {}))

                    all_data.extend(samples)
                    progress += len(samples)
                    progress_dialog.setValue(min(progress, total_samples))
                    QtWidgets.QApplication.processEvents()

                    logger.info(f"✓ Généré {len(samples)} échantillons pour {combo_path}")

                except Exception as e:
                    logger.error(f"Erreur batch {combo_path}: {str(e)}")
                    continue

            logger.info(f"Génération terminée: {len(all_data)} échantillons générés")

            self.save_dataset(all_data, output_file, output_format, project_data, batch_statistics)

            QtWidgets.QMessageBox.information(
                self.generator_widget,
                "Génération Terminée",
                f"Dataset généré avec succès :\n"
                f"• Fichier: {output_file}.{output_format.lower()}\n"
                f"• {len(all_data)} échantillons générés\n"
                f"• {len(batch_distribution)} batches (combinaisons)\n"
                f"• Typologies combinées: {len(project_data.get('typologies', []))}"
            )

        except Exception as e:
            logger.error(f"Erreur génération : {str(e)}", exc_info=True)
            QtWidgets.QMessageBox.critical(self.generator_widget, "Erreur Génération",
                                           f"Une erreur est survenue : {str(e)}")
        finally:
            progress_dialog.close()

    def __del__(self):
        """Ferme la connexion à la base de données lors de la destruction de l'objet."""
        if self.db_connection:
            self.db_connection.close()
            logger.info("Connexion à la base de données fermée")


def integrate_generation_button(generator_widget, strategy_widget):
    generator = DatasetGenerator(strategy_widget, generator_widget)

    def on_generation_clicked():
        try:
            template = 'complex' if generator_widget.config_data['training_technique'] == 'RLHF' else 'simple'

            generator.generate(
                lots=1,
                samples_per_lot=generator_widget.config_data['sample_count'],
                template=template,
                augment=False,
                output_file=f"exports/{generator_widget.current_project_name}_dataset"
            )
        except Exception as e:
            logger.error(f"Erreur : {str(e)}")
            QtWidgets.QMessageBox.critical(generator_widget, "Erreur", f"Erreur : {str(e)}")

    for child in generator_widget.findChildren(QtWidgets.QPushButton):
        if child.text() == "🚀 Génération":
            child.clicked.connect(on_generation_clicked)
            break