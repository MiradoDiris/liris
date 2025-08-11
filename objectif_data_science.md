Voici les instructions pour Liris Data Science

Objectif

Développement d’un système piloté par intelligence artificielle, destiné à la génération de datasets configurables. Le système devra permettre la génération automatique des datasets en envoyant des prompts vers une plateforme d’IA (Claude, Gemini, etc) et en extrayant automatiquement les résultats.
Ce système doit permettre :
une personnalisation des paramètres de contexte,
un formatage structuré des données,
une visualisation statistique des combinaisons utilisées par projet.

L'application sera disponible sous forme de client desktop, compatible avec différents systèmes d’exploitation.

1. Stratégie de génération de dataset

Le système autorise l’injection de multiples paires clé-valeur dans le dataset, en complément des champs obligatoires tels que input et output

Chaque clé peut être liée à une taxonomie hiérarchisée comportant trois niveaux :
catégorie
sous-catégorie
thème
Cette architecture permet une contextualisation riche et adaptable, assurant une granularité dans l’organisation des données.
Un champ de saisie dédié permettra l’ajout de prompts dynamiques, lesquels seront transmis à l’IA générative dans le cadre de la production des données.

2. Composants de visualisation
   Analyses thématiques (Camemberts)

Des visualisations en diagrammes circulaires permettront d’analyser la répartition des thèmes générés. Ces vues présenteront, en pourcentage, la distribution des éléments selon leur thème, avec une agrégation par projet.
Navigation hiérarchique interactive

Le camembert offrira une navigation contextuelle dans la taxonomie :
un clic sur une catégorie déclenchera une mise à jour dynamique, révélant la répartition des sous-catégories correspondantes,
à chaque niveau, les pourcentages de génération seront mis à jour et affichés en temps réel.

3. Vérification des datasets

Le système intègre un mécanisme d’identification et de traçabilité des éléments vérifiés.

Chaque élément généré sera associé explicitement au modèle d’IA ayant produit la donnée, assurant une transparence totale sur l’origine des contenus.

Un camembert spécifique permettra de visualiser :
le taux global de complétion de la vérification par dataset,
le pourcentage de données vérifiées versus non vérifiées,

4. Ranking par décomposition

Le système implémente une stratégie d’évaluation croisée via plusieurs modèles d’IA.

Chaque IA évalue les réponses de manière autonome, en fonction de critères internes propres.

Les classements fournis par chaque modèle sont comparés.

Les scores des différentes IA sont ensuite fusionnés , produisant un classement final consolidé, représentatif d’un consensus multi-modèles.
Le processus suit les étapes suivantes :
génération initiale des réponses par plusieurs IA,
évaluation croisée indépendante,
comparaison et alignement des classements,
calcul d’un score final par fusion des évaluations.

Si vous avez des questions ou besoin de précisions, n’hésitez pas à les poser

Voici des instructions supplémentaires :
Mettre en place une première interface avec des champs permettant d’ajouter des typologies de contexte, chacune accompagnée d’une description.
L’interface devra inclure un bouton pour enregistrer chaque typologie de contexte, ainsi qu’un bouton pour en ajouter un nouveau.
Chaque typologie de contexte pourra contenir plusieurs clusters, chacun composé de labels roots organisés hiérarchiquement comme suit : Cluster > label root > label parent > label enfant.

Par exemple :
Typologie de contexte : "Niveau", avec la description suivante : Structuration des compétences selon le niveau d’expertise.
L'utilisateur ajoute trois clusters représentant les niveaux suivants :
Cluster : Débutant
Cluster : Intermédiaire
Cluster : Avancé

L'objectif est de constituer du contexte enrichi composé des typologies de contexte
