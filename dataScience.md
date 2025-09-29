1. Objectif global

Le projet permet de générer automatiquement des datasets personnalisés pour l’entraînement de modèles IA.
Il s’appuie sur une interface utilisateur (PyQt5), une base de données SQLite, et l’API Gemini de Google pour générer et augmenter des échantillons de données structurés.

2. Structure des fichiers
a) dataset_generator.py

Rôle : cœur du système de génération de datasets.

Fonctionnalités principales :

Initialisation de la base SQLite (liris.db) et gestion des projets.

Connexion à l’API Gemini pour générer des échantillons de données (questions/réponses, instructions, inputs/outputs).

Construction dynamique des prompts selon la configuration (plateforme, technique d’entraînement, typologies choisies).

Augmentation de données : création de variantes (paraphrases, synonymes, modifications légères).

Sauvegarde des résultats en JSON, CSV, ou Parquet.

Chargement d’un dataset existant pour l’enrichir.

b) dataset_generator_widget.py

Rôle : interface utilisateur (UI) pour gérer les projets et lancer la génération.

Fonctionnalités principales :

Gestion des projets de dataset (création, édition, suppression, sauvegarde).

Interface pour définir :

Le nom et la description du projet.

Les typologies de contexte (hiérarchiques : racines → parents → enfants).

Le format de sortie (JSON, CSV, Parquet).

La taille du dataset à générer.

Connexion directe à la base SQLite pour stocker la configuration.

Gestion multi-projets avec un sélecteur et sauvegarde automatique.

Interface en onglets :

➕ Créer projet

📊 Dataset (gestion, édition, typologies, export).

c) dataset_strategy.py

Rôle : définir la stratégie de création des datasets.

Fonctionnalités principales :

Gestion des typologies de contexte (ajout, édition, suppression).

Navigation hiérarchique avec arborescence (TreeView) pour visualiser :

Typologies

Labels racines

Labels parents

Labels enfants

Génération et gestion des batches (combinaisons de typologies utilisées pour la génération de données).

Visualisation des batches via un camembert (pie chart) avec Matplotlib :

Permet de voir la répartition des échantillons par typologie.

Sauvegarde et export des stratégies.

3. Base de données

SQLite (fichier : data/liris.db)

Tables principales :

projects → stocke les projets (nom, description, données JSON).

dataset_batches → stocke les combinaisons générées avec leur pourcentage et typologie.

platforms → stocke les configurations de plateformes.

4. Flux de travail utilisateur

Créer un projet (nom + description).

Définir la stratégie dans l’onglet stratégie :

Ajouter des typologies de contexte et leurs labels (racines/parents/enfants).

Générer les batches.

Vérifier leur représentativité avec le graphique.

Lancer la génération dans l’onglet dataset :

Sélectionner le projet.

Définir les paramètres (format, nombre d’échantillons, technique d’entraînement).

Générer les données via Gemini.

Sauvegarder en JSON/CSV/Parquet.

Optionnel : importer un dataset existant et l’augmenter.

5. Points clés à retenir pour l’entretien

Technologies :

Python (PyQt5 pour l’UI, SQLite pour la BD, Pandas pour manipulation, Matplotlib pour visualisation).

API Gemini pour la génération intelligente.

Architecture :

Séparation claire entre :

UI (dataset_generator_widget, dataset_strategy)

Logique métier (dataset_generator)

Stockage (SQLite)

Valeur ajoutée :

Génération automatisée et personnalisée de datasets.

Gestion hiérarchique des contextes (typologies).

Outil flexible et modulable pour différents projets IA.