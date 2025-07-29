Liris Dev est en fait un outil qui à terme permettra d'automatiser la production de code adapté aux besoins spécifiques d'un projet.
Le but est donc d'utiliser l'automatisation de l'interaction avec les plateformes IA (déjà en place) pour générer des codes.
Il y a 2 parties à traiter pour que ça puisse bien fonctionner :
1- Automatiser de l'envoi du prompt et de la récupération/extraction de la réponse de l'IA : utiliser les codes existants
2- Relier le programme à une base de données graphe (Dgraph) qu'on appelle Turing qui sera utilisée pour stocker de manière structurée toutes les données concernant un projet.

En environnement réel, voici comment ça devrait se passer :

- L'utilisateur entre son prompt dans le champ, sélectionne l'IA à utiliser et le projet sur lequel il est en train de travailler.
- Lorsqu'il valide sa requête, Liris va effectuer un retrieval dans Turing pour récupérer toutes les informations liées a ce prompt (par exemple des fonctions qui pourraient être utilisées) pour servir de contexte à envoyer à l'IA
- Une fois ces informations recueillies, ça va les injecter dans le prompt pour enrichir le contexte, puis procéder à son envoi dans la plateforme IA
- Une fois l'attente de la réponse terminée le programme va automatiquement extraire le résultat (le code) et l'afficher dans l'interface

Vos tâches principales sont donc:

- Ajuster l'interface de l'onglet coding (il y en a déjà une mais pas encore bien adapté au code)
- Assurer la mise en place de la structure d'un projet dans Turing : sur le menu en haut il y a déjà la partie Turing, qui permet de configurer les projets à utiliser dans Liris.
  - En premier lieu il faudra extraire toute l'arborescence du projet (onglet Configuration de projet) pour déterminer les clusters et labels à ajouter dans le graph : les enfants directs du dossier racine du projet seront les clusters, puis les enfants directs des clusters seront les labels racines, et ainsi de suite. Voici l'hiérarchie : cluster > label racine > label parent > label enfant
  - Une fois l'arborescence extraite, générer à l'aide de l'IA un script de mutation pydgraph pour créer la structure dans Dgraph
  - Ensuite il faudra récupérer tous les labels qui sont des fichiers de code (scripts), et les envoyer à l'IA aussi pour détecter toutes les fonctions dans le code, et générer de nouveaux codes de mutation pydgraph pour insérer ces fonctions dans le graphe en tant que nodes, enfants respectifs des labels qui représentent les scripts auxquels ils sont rattachés
  - À terme le but sera donc de pouvoir faire du retrieval d'informations dans ce graph qui a été construit pour améliorer le prompt de l'utilisateur, mais il faut d'abord s'assurer que le graph est crée et structuré correctement
- Mettre en place l'automatisation de l'envoi du prompt de l'utilisateur à l'IA choisie et la récupération de la réponse : utiliser juste le code déjà existant. Faire en sorte aussi qu'on puisse bien injecter plus d'informations dans le prompt, pour faciliter l'intégration des informations récupérées depuis Turing

Pour la structure hiérarchique du code, les codes que vous utiliserez la plupart du temps se trouvent dans core et ui.
Dans core vous trouverez les scripts utilisés pour les automatisations (contrôle souris, clavier, ...), et le script principal qui gère les actions est le conductor (dans orchestration).
Et c'est dans l'ui que vous trouverez tous les codes pour les éléments de l'interface du programme, avec leurs logiqies respectifs.

Pour l'interface, à part l'écran principal, les fenêtres que vous utiliserez le plus souvent aussi se trouvent dans les menus IA et Turing.
IA > Plateformes : c'est là que vous pourrez configurer les valeurs pour l'automatisation des intéractions avec les plateformes IA : configuration du clavier, du navigateur à utiliser pour chaque plateforme, les coordonnées des positions a cliquer pour sélectionner le navigateur ou aussi pour sélectionner le champ de saisoe de la plateforme, les sélecteurs à utiliser pour attendre et extraire la réponse (on utilise les sélecteurs CSS pour déterminer les éléments HTML à vérifier), ... Normalement les valeurs par défaut devraient déjà permettre le bon fonctionnement de l'automatisation.
Turing > Configuration de projets : permet l'extraction des clusters et labels (arborescence du projet), et des nodes (fonctions), et ensuite l'ajout dans Turing
