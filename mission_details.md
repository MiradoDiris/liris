# Détail de la Mission pour le Projet Liris Dev

## La Vision : L'Objectif Final

L'objectif est de transformer Liris en un **agent de développement logiciel**. Il doit être capable de construire une base de connaissances structurée (le graphe "Turing") à partir d'un projet de code existant. Ensuite, il utilisera cette connaissance pour enrichir les prompts des utilisateurs et générer du code plus pertinent et mieux adapté au contexte du projet.

Votre rôle est de construire les fondations techniques essentielles pour que cette vision devienne réalité.

---

## Vos Tâches Détaillées

### 1. Ajuster l'Interface Utilisateur (UI) pour le Code

L'interface actuelle doit être optimisée pour la manipulation et l'affichage de code source.

- **Attente :** Modifier l'onglet "Coding" pour offrir une expérience de développement minimale mais fonctionnelle.
- **Actions Concrètes :**
    - Intégrer un éditeur de code ou un visualiseur qui supporte la **coloration syntaxique** (pour Python initialement).
    - Afficher les **numéros de ligne**.
    - Ajouter un bouton "Copier le code" pour une utilisation facile du résultat.
- **Fichiers Concernés :** Principalement dans `ui/widgets/`. Il faudra identifier et modifier le fichier qui gère l'onglet "Coding".

### 2. Construire la Base de Connaissances "Turing" (Votre Mission Principale)

C'est votre tâche la plus importante. Elle consiste à peupler la base de données graphe Dgraph avec la structure et le contenu d'un projet logiciel.

- **Attente :** Mettre en place le workflow complet qui analyse un projet local et le traduit en une structure de graphe dans Dgraph, en utilisant l'interface `Turing > Configuration de projets`.
- **Actions Concrètes (en séquence) :**
    1.  **Extraire l'Arborescence du Projet :**
        - Implémenter la logique qui scanne un dossier et en extrait la structure hiérarchique (`Cluster > Label Racine > Label Parent > ...`).
    2.  **Générer la Structure du Graphe via l'IA :**
        - Fournir l'arborescence extraite (ex: en JSON) à une IA.
        - Demander à l'IA de **générer le script de mutation `pydgraph`** nécessaire pour créer cette structure dans Dgraph.
    3.  **Extraire les Fonctions du Code via l'IA :**
        - Pour chaque fichier de code (`.py`), lire son contenu.
        - Envoyer ce contenu à une IA pour qu'elle détecte et liste toutes les fonctions présentes.
    4.  **Insérer les Fonctions dans le Graphe via l'IA :**
        - Fournir la liste de fonctions à l'IA.
        - Demander à l'IA de **générer un nouveau script de mutation `pydgraph`** pour insérer ces fonctions comme des nœuds dans le graphe, rattachés à leur fichier parent.

### 3. Mettre en Place l'Automatisation du Prompt

Cette tâche consiste à connecter l'interface utilisateur au moteur d'automatisation principal.

- **Attente :** Assurer que le prompt de l'utilisateur, saisi dans le nouvel onglet "Coding", soit envoyé à l'IA choisie et que la réponse (le code généré) soit récupérée et affichée.
- **Actions Concrètes :**
    - **Utiliser l'existant :** S'appuyer sur les fonctions déjà présentes dans `core/interaction`, `core/vision` et `core/orchestration/conductor.py`. Il n'est pas nécessaire de réécrire la logique d'automatisation.
    - **Brancher les fils :** L'action du bouton "Lancer" de votre nouvelle interface doit appeler le `conductor` avec les bons paramètres (prompt, plateforme, etc.).
    - **Prévoir l'enrichissement du Prompt :** La fonction d'envoi doit être conçue pour accepter non seulement le prompt de l'utilisateur, mais aussi des données de contexte supplémentaires (qui viendront plus tard de Turing), afin de les fusionner avant l'envoi à l'IA.

---

## Synthèse

Votre mission est de construire le **système de peuplement de la base de connaissances "Turing"**. Vous allez créer l'outil qui permet à Liris d'apprendre et de modéliser la structure d'un projet de code. Ce travail est la fondation indispensable pour la future fonctionnalité de "retrieval" qui s'appuiera sur votre travail.
