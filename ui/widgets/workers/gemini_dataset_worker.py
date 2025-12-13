#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gemini Dataset Worker - Générateur STRICT aux combinaisons définies
❌ INTERDIT : Générer du contenu hors des combinaisons master + contextes
✅ OBLIGATOIRE : Respecter UNIQUEMENT les éléments de la taxonomie fournie
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from PyQt5.QtCore import QThread, pyqtSignal

from utils.logger import logger
from utils.keyring_helper import KeyringHelper


class GeminiDatasetWorker(QThread):
    """
    Worker thread pour générer des datasets via Gemini API
    GÉNÉRATION STRICTE : Uniquement les combinaisons définies
    """
    
    # Signaux
    progress_updated = pyqtSignal(int, int, str)
    combination_completed = pyqtSignal(int, dict)
    batch_completed = pyqtSignal(int, list)
    generation_completed = pyqtSignal(list, dict)
    generation_failed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    def __init__(self, generation_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.generation_config = generation_config
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        
        # Configuration
        self.metadata = generation_config.get('metadata', {})
        self.user_prompt = generation_config.get('prompt', '')
        self.master_typologie = generation_config.get('master_typologie', {})
        self.combinations = generation_config.get('combinations', [])
        
        # Métadonnées
        self.project_name = self.metadata.get('project_name', 'Unknown')
        self.batch_number = self.metadata.get('batch_number', 0)
        self.batch_name = self.metadata.get('batch_name', 'Sans nom')
        self.batch_family = self.metadata.get('batch_family', '')
        self.output_format = self.metadata.get('output_format', 'JSON')
        self.num_batches = self.metadata.get('num_batches_to_process', 1)
        self.total_samples_per_batch = self.metadata.get('total_samples_per_batch', 0)
        self.total_samples_all_batches = self.metadata.get('total_samples_all_batches', 0)
        
        # Résultats
        self.all_results = []
        self.global_sample_counter = 0
        
        # Gemini
        self.api_key = None
        self.model_name = None
        self.max_tokens = None
        self.client = None
        
        logger.info("🤖 GeminiDatasetWorker initialisé (MODE STRICT)")
    
    def _load_gemini_config(self) -> bool:
        """Charge la configuration Gemini"""
        try:
            self._log("info", "📋 Chargement config Gemini...")
            config = KeyringHelper.get_platform_config("Gemini")
            
            if not config:
                self._log("error", "❌ Config Gemini introuvable")
                return False
            
            self.api_key = config.get('api_key')
            self.model_name = config.get('model', 'gemini-2.0-flash-exp')
            self.max_tokens = config.get('max_tokens', 8192)
            
            if not self.api_key:
                self._log("error", "❌ Clé API manquante")
                return False
            
            self._log("info", f"✅ Config OK: {self.model_name}")
            return True
            
        except Exception as e:
            self._log("error", f"❌ Erreur config: {str(e)}")
            return False
    
    def _initialize_gemini_client(self) -> bool:
        """Initialise le client Gemini"""
        try:
            self._log("info", "🔧 Init client Gemini...")
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model_name)
            self._log("info", f"✅ Client OK: {self.model_name}")
            return True
        except Exception as e:
            self._log("error", f"❌ Erreur init: {str(e)}")
            return False
    
    def run(self):
        """Point d'entrée du thread"""
        self.is_running = True
        self.should_stop = False
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 GÉNÉRATION DATASET (MODE STRICT)")
        logger.info("=" * 80)
        
        try:
            if not self._load_gemini_config():
                self.generation_failed.emit("Config Gemini invalide")
                return
            
            if not self._initialize_gemini_client():
                self.generation_failed.emit("Init client impossible")
                return
            
            self._log_generation_summary()
            
            # Générer chaque batch
            for batch_idx in range(self.num_batches):
                if self.should_stop:
                    break
                
                self._log("info", f"\n{'=' * 60}")
                self._log("info", f"📦 BATCH {batch_idx + 1}/{self.num_batches}")
                self._log("info", f"{'=' * 60}")
                
                batch_results = self._generate_batch(batch_idx + 1)
                
                if batch_results:
                    self.all_results.extend(batch_results)
                    self.batch_completed.emit(batch_idx + 1, batch_results)
                    self._log("info", f"✅ Batch {batch_idx + 1}: {len(batch_results)} samples")
            
            # Finaliser
            if not self.should_stop:
                self._log("info", f"\n{'=' * 80}")
                self._log("info", f"🎉 GÉNÉRATION TERMINÉE")
                self._log("info", f"   • Total: {len(self.all_results)} samples")
                self._log("info", f"   • Format: {self.output_format}")
                self._log("info", f"{'=' * 80}")
                
                final_metadata = {
                    'project_name': self.project_name,
                    'batch_number': self.batch_number,
                    'batch_name': self.batch_name,
                    'batch_family': self.batch_family,
                    'output_format': self.output_format,
                    'num_batches_processed': self.num_batches,
                    'total_samples': len(self.all_results),
                    'generation_date': datetime.now().isoformat(),
                    'model_used': self.model_name,
                    'purpose': 'Conversational AI Training Dataset'
                }
                
                self.generation_completed.emit(self.all_results, final_metadata)
            
        except Exception as e:
            self._log("error", f"❌ Erreur critique: {str(e)}")
            self.generation_failed.emit(str(e))
        finally:
            self.is_running = False
    
    def _generate_batch(self, batch_number: int) -> List[Dict[str, Any]]:
        """Génère un batch complet"""
        batch_results = []
        
        for combo_idx, combination in enumerate(self.combinations):
            if self.should_stop:
                break
            
            self._log("info", f"\n--- Combinaison {combo_idx + 1}/{len(self.combinations)} ---")
            
            combo_samples = self._generate_combination(
                combination, 
                combo_idx, 
                batch_number
            )
            
            if combo_samples:
                batch_results.extend(combo_samples)
                self.combination_completed.emit(combo_idx, {
                    'combination_index': combo_idx,
                    'samples_generated': len(combo_samples)
                })
        
        return batch_results
    
    def _generate_combination(
        self, 
        combination: Dict[str, Any], 
        combo_idx: int, 
        batch_number: int
    ) -> List[Dict[str, Any]]:
        """
        Génère les échantillons pour UNE combinaison spécifique
        VERSION CORRIGÉE : Le modèle génère déjà le bon format avec "combinaisons"
        """
        samples = []
        nb_samples = combination.get('nb_samples', 1)

        self._log("info", f"   🎯 Génération de {nb_samples} sample(s)...")

        # Construire le contexte EXACT de cette combinaison
        context = self._build_context(combination)

        # Construire le prompt
        final_prompt = self._build_flexible_prompt(context, nb_samples)

        try:
            generated_data = self._call_gemini_api(final_prompt, nb_samples)

            if generated_data:
                for idx, sample in enumerate(generated_data):
                    self.global_sample_counter += 1

                    # ✅ LE MODÈLE GÉNÈRE DÉJÀ LE BON FORMAT
                    # Si le sample contient déjà un champ "combinaisons", on le garde
                    # Sinon, on le construit à partir des champs à la racine

                    if 'combinaisons' in sample and sample['combinaisons']:
                        # ✅ CAS 1 : Le modèle a généré le bon format avec "combinaisons"
                        combinaisons = sample['combinaisons']
                        self._log("debug", f"      ✅ Sample #{self.global_sample_counter}: format 'combinaisons' détecté")
                    else:
                        # ✅ CAS 2 : Format legacy, construire depuis les champs racine
                        self._log("debug", f"      ⚠️ Sample #{self.global_sample_counter}: format legacy, reconstruction...")
                        combinaisons = self._build_combinaisons_from_sample(sample, combination)

                    enriched_sample = {
                        'sample_id': sample.get('sample_id', self.global_sample_counter),
                        'input': sample.get('input', ''),
                        'combinaisons': combinaisons,  # ✅ Utiliser directement ce que le modèle a généré
                        'output': sample.get('output', ''),
                        'metadata': {
                            'project_name': self.project_name,
                            'batch_number': batch_number,
                            'batch_name': self.batch_name,
                            'batch_family': self.batch_family,
                            'combination_index': combo_idx + 1,
                            'local_sample_index': idx + 1,
                            'generated_at': datetime.now().isoformat(),
                            'model': self.model_name,
                            'master': combination['master']['name'],
                            'contexts': [ctx['display'] for ctx in combination['contexts']],
                            'purpose': 'conversational_ai_training',
                            'output_format': self.output_format
                        }
                    }

                    # ✅ LOG DE DEBUG : Afficher ce qui a été extrait
                    self._log("debug", f"      Sample #{self.global_sample_counter}:")
                    for combo in combinaisons:
                        typo = combo.get('typologie_de_contexte', '')
                        cluster = combo.get('cluster', '')
                        label = combo.get('label', combo.get('label_root', ''))
                        self._log("debug", f"         • typo='{typo}', cluster='{cluster}', label='{label}'")

                    samples.append(enriched_sample)

                self._log("info", f"   ✅ {len(samples)} sample(s) générés et acceptés")
            else:
                self._log("warning", f"   ⚠️ Aucun sample généré")

        except Exception as e:
            self._log("error", f"   ❌ Erreur: {str(e)}")
            import traceback
            self._log("error", traceback.format_exc())

        # Mise à jour progression
        current = (combo_idx * nb_samples) + len(samples)
        self.progress_updated.emit(
            current,
            self.total_samples_per_batch,
            f"Combinaison {combo_idx + 1}/{len(self.combinations)}"
        )

        return samples
    
    def _build_combinaisons_from_sample(
        self, 
        sample: Dict[str, Any], 
        combination: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Construit la liste des combinaisons à partir du sample généré (FORMAT LEGACY)
        Cette méthode n'est utilisée QUE si le modèle n'a pas généré le bon format
        """
        combinaisons = []

        # ✅ EXTRACTION ROBUSTE avec plusieurs variantes de clés
        typologie = (
            sample.get('typologie_de_contexte') or 
            sample.get('typologie de contexte') or 
            sample.get('typologie') or 
            ''
        )

        cluster = (
            sample.get('cluster') or 
            sample.get('Cluster') or 
            ''
        )

        label = (
            sample.get('label') or 
            sample.get('Label') or 
            ''
        )

        # ✅ LOG pour debug
        logger.debug(f"   📋 Extraction legacy sample #{sample.get('sample_id', '?')}")
        logger.debug(f"      typologie: '{typologie}'")
        logger.debug(f"      cluster: '{cluster}'")
        logger.debug(f"      label: '{label}'")

        # ✅ CRÉER LA COMBINAISON PRINCIPALE
        combo = {
            'typologie_de_contexte': typologie.strip(),
            'cluster': cluster.strip()
        }

        # ✅ GÉRER LA HIÉRARCHIE COMPLÈTE : ROOT > PARENT > ENFANT > ENFANT_1 > ...
        separators = [' > ', ' / ', ' - ']
        parts = [label]

        # Trouver le séparateur utilisé et split
        for sep in separators:
            if sep in label:
                parts = [p.strip() for p in label.split(sep)]
                break
            
        # Construire la hiérarchie selon le nombre de niveaux
        num_levels = len(parts)

        if num_levels == 1:
            combo['label'] = parts[0]
        elif num_levels == 2:
            combo['label_root'] = parts[0]
            combo['label_parent'] = parts[1]
        elif num_levels == 3:
            combo['label_root'] = parts[0]
            combo['label_parent'] = parts[1]
            combo['label_enfant'] = parts[2]
        elif num_levels >= 4:
            combo['label_root'] = parts[0]
            combo['label_parent'] = parts[1]
            combo['label_enfant'] = parts[2]
            for i, part in enumerate(parts[3:], start=1):
                combo[f'label_enfant_{i}'] = part

        combinaisons.append(combo)

        # 🔄 AJOUTER LES CONTEXTES ADDITIONNELS si présents dans le sample
        if 'additional_contexts' in sample:
            for ctx in sample['additional_contexts']:
                extra_combo = {
                    'typologie_de_contexte': ctx.get('typologie_de_contexte', ''),
                    'cluster': ctx.get('cluster', ''),
                }

                extra_label = ctx.get('label', '')
                extra_parts = [extra_label]

                for sep in separators:
                    if sep in extra_label:
                        extra_parts = [p.strip() for p in extra_label.split(sep)]
                        break
                    
                extra_num_levels = len(extra_parts)

                if extra_num_levels == 1:
                    extra_combo['label'] = extra_parts[0]
                elif extra_num_levels == 2:
                    extra_combo['label_root'] = extra_parts[0]
                    extra_combo['label_parent'] = extra_parts[1]
                elif extra_num_levels == 3:
                    extra_combo['label_root'] = extra_parts[0]
                    extra_combo['label_parent'] = extra_parts[1]
                    extra_combo['label_enfant'] = extra_parts[2]
                elif extra_num_levels >= 4:
                    extra_combo['label_root'] = extra_parts[0]
                    extra_combo['label_parent'] = extra_parts[1]
                    extra_combo['label_enfant'] = extra_parts[2]
                    for i, part in enumerate(extra_parts[3:], start=1):
                        extra_combo[f'label_enfant_{i}'] = part

                combinaisons.append(extra_combo)

        logger.debug(f"      ✅ {len(combinaisons)} combinaison(s) créée(s)")

        return combinaisons

    def _build_flexible_prompt(
        self, 
        context: Dict[str, Any], 
        nb_samples: int
    ) -> str:
        """
        ⭐ PROMPT FLEXIBLE : Génération libre basée sur la taxonomie fournie
        CORRECTION : Clarifier la différence entre cluster et label
        """
        master_name = context['master_name']
        master_data = context['master_typologie']
        contexts = context['contexts']

        prompts = self.generation_config.get('prompts', {})
        global_context = prompts.get('global_context', '')
        local_prompt = prompts.get('local_prompt', '')

        # Formater la typologie master
        master_section = self._format_typologie(master_data, "TYPOLOGIE MASTER")

        # Formater les contextes
        context_sections = []
        for idx, ctx in enumerate(contexts):
            ctx_section = f"\n### CONTEXTE {idx + 1} ({ctx['level']}): {ctx['display']}\n"
            ctx_section += self._format_typologie(ctx['full_data'], "Typologie du contexte")
            context_sections.append(ctx_section)

        # ✅ EXTRAIRE DES EXEMPLES CONCRETS pour montrer la structure
        exemple_structure = self._extract_structure_examples(master_data, contexts)

        prompt = f"""# 🤖 GÉNÉRATION DE DATASET POUR IA CONVERSATIONNELLE

    ## 📚 TAXONOMIE DE RÉFÉRENCE

    ### TYPOLOGIE MASTER : {master_name}
    {master_section}

    ### CONTEXTES SPÉCIFIQUES
    {''.join(context_sections)}

    ## 📋 FORMAT DE SORTIE OBLIGATOIRE

    ⚠️ **IMPORTANT** : Vous DEVEZ générer UNIQUEMENT du JSON pur, sans texte avant/après.

    Chaque échantillon doit suivre cette structure JSON **EXACTEMENT** :

    ```json
    {{
      "sample_id": <numéro>,
      "input": "<question_utilisateur_naturelle>",
      "combinaisons": [
        {{
          "typologie_de_contexte": "<typologie_depuis_taxonomie>",
          "cluster": "<cluster_depuis_taxonomie>",
          "label": "<label_hiérarchique_SANS_le_cluster>"
        }}
      ],
      "output": "<réponse_chatbot_actionnable>"
    }}
    ```

    ### 🔍 COMPRENDRE LA STRUCTURE HIÉRARCHIQUE

    **⚠️ RÈGLE CRITIQUE** : Dans votre taxonomie, la hiérarchie est :

    1. **typologie_de_contexte** : Le nom de la typologie (ex: "UX/UI", "Intention")
    2. **cluster** : Le PREMIER niveau sous la typologie (ex: "Paramètres", "Modules", "Explications")
    3. **label** : La hiérarchie COMPLÈTE en dessous du cluster (ex: "Affichage > Thème > Mode sombre")

    {exemple_structure}

    ### 📐 EXEMPLES DE STRUCTURE CORRECTE vs INCORRECTE

    #### ❌ INCORRECT (tout dans le label) :
    ```json
    {{
      "typologie_de_contexte": "UX/UI",
      "cluster": "Cluster",
      "label": "Paramètres > Affichage > Thème > Mode sombre"
    }}
    ```

    #### ✅ CORRECT (cluster séparé du label) :
    ```json
    {{
      "typologie_de_contexte": "UX/UI",
      "cluster": "Paramètres",
      "label": "Affichage > Thème > Mode sombre"
    }}
    ```

    #### ❌ INCORRECT (cluster dans le label) :
    ```json
    {{
      "typologie_de_contexte": "Intention",
      "cluster": "Cluster",
      "label": "Explications > Fonctionnement du système"
    }}
    ```

    #### ✅ CORRECT (cluster extrait) :
    ```json
    {{
      "typologie_de_contexte": "Intention",
      "cluster": "Explications",
      "label": "Fonctionnement du système"
    }}
    ```

    ### 📊 RÈGLES POUR REMPLIR LES CHAMPS

    1. **typologie_de_contexte** : 
       - Utilisez le NOM de la typologie (visible en haut de chaque section)
       - Exemples valides : "UX/UI", "Intention", "Level Scorer"

    2. **cluster** : 
       - Utilisez le nom du 📦 CLUSTER (premier niveau sous la typologie)
       - C'est le texte après "📦 CLUSTER:" dans la taxonomie
       - Exemples : "Paramètres", "Modules", "Tableau de board", "Explications", "Action"
       - ⚠️ NE PAS écrire "Cluster" comme valeur !

    3. **label** : 
       - La hiérarchie COMPLÈTE en dessous du cluster
       - Utilisez " > " (espace-chevron-espace) pour séparer les niveaux
       - Peut avoir plusieurs niveaux : "Parent", "Parent > Enfant", "Parent > Enfant > Sous-enfant"
       - ⚠️ N'incluez PAS le cluster dans le label !

    ## 🎨 EXEMPLES RÉELS BASÉS SUR VOTRE TAXONOMIE

    ### Exemple 1 : Simple (2 niveaux sous cluster)
    ```json
    {{
      "sample_id": 1,
      "input": "Comment je change la langue de l'interface ?",
      "combinaisons": [
        {{
          "typologie_de_contexte": "UX/UI",
          "cluster": "Paramètres",
          "label": "Langue > Interface"
        }}
      ],
      "output": "Pour changer la langue, allez dans 'Paramètres' > 'Langue' > 'Interface' et sélectionnez votre langue préférée."
    }}
    ```

    ### Exemple 2 : Hiérarchie profonde (4 niveaux sous cluster)
    ```json
    {{
      "sample_id": 2,
      "input": "Où je trouve les options d'export des rapports en PDF ?",
      "combinaisons": [
        {{
          "typologie_de_contexte": "UX/UI",
          "cluster": "Modules",
          "label": "Rapports > Export > Formats > PDF"
        }}
      ],
      "output": "Naviguez vers 'Modules' > 'Rapports' > 'Export' > 'Formats' et choisissez 'PDF' comme format d'export."
    }}
    ```

    ### Exemple 3 : Combinaisons multiples
    ```json
    {{
      "sample_id": 3,
      "input": "Comment ça marche les dotations aux amortissements ?",
      "combinaisons": [
        {{
          "typologie_de_contexte": "Intention",
          "cluster": "Explications",
          "label": "Concepts comptables > Amortissements"
        }},
        {{
          "typologie_de_contexte": "UX/UI",
          "cluster": "Modules",
          "label": "Comptabilité > Opérations diverses > Dotations"
        }}
      ],
      "output": "Les dotations aux amortissements permettent de répartir le coût d'un bien sur sa durée d'utilisation. Dans Macompta, accédez à 'Modules' > 'Comptabilité' > 'Opérations diverses' > 'Dotations' pour les saisir."
    }}
    ```

    ## 📋 INSTRUCTIONS UTILISATEUR

    ### Contexte Global du Projet :
    {global_context if global_context else "(Aucun contexte global défini)"}

    ### Instructions Spécifiques pour ce Batch :
    {local_prompt}

    ## 🎯 GÉNÉRATION

    ⚠️ **CONTRAINTE CRITIQUE** : Générez EXACTEMENT **{nb_samples} échantillon(s)**, ni plus ni moins.

    Exigences :
    - Inspirez-vous de la taxonomie fournie
    - Format JSON strict avec le champ "combinaisons"
    - **cluster** = Premier niveau sous la typologie (📦 CLUSTER)
    - **label** = Hiérarchie complète SOUS le cluster (séparée par " > ")
    - Ton conversationnel naturel
    - Réponses actionnables
    - Sample IDs séquentiels (1, 2, 3, ..., {nb_samples})

    Retournez UNIQUEMENT un array JSON contenant EXACTEMENT {nb_samples} objet(s) :

    ```json
    [
      {{
        "sample_id": 1,
        "input": "...",
        "combinaisons": [
          {{
            "typologie_de_contexte": "...",
            "cluster": "...",
            "label": "..."
          }}
        ],
        "output": "..."
      }}
    ]
    ```

    **⚠️ RÈGLES STRICTES :**
    1. Générez EXACTEMENT {nb_samples} échantillon(s) - c'est OBLIGATOIRE
    2. **cluster** doit être le nom du 📦 CLUSTER, PAS "Cluster" !
    3. **label** ne doit PAS contenir le cluster, seulement ce qui vient après
    4. Utilisez " > " pour séparer les niveaux de hiérarchie dans le label
    5. NE PAS écrire de texte explicatif avant le JSON
    6. NE PAS utiliser de balises markdown ```json
    7. Retournez DIRECTEMENT l'array JSON commençant par [

    **COMMENCEZ MAINTENANT.**
    """

        return prompt
    
    def _extract_structure_examples(self, master_data: Dict[str, Any], contexts: list) -> str:
        """
        Extrait des exemples CONCRETS de la structure cluster/label depuis la taxonomie réelle
        Pour montrer au modèle comment séparer correctement cluster et label
        """
        examples = []
        
        # Fonction helper pour extraire des exemples d'une typologie
        def extract_from_typologie(typo_data: Dict[str, Any], typo_name: str):
            local_examples = []
            clusters = typo_data.get('taxonomy_clusters', [])
            
            for cluster in clusters[:2]:  # Max 2 clusters par typologie
                cluster_name = cluster.get('cluster_name', '')
                if not cluster_name:
                    continue
                
                roots = cluster.get('root_labels', [])
                for root in roots[:1]:  # 1 root par cluster
                    root_name = root.get('root_name', '')
                    if not root_name:
                        continue
                    
                    parents = root.get('parent_labels', [])
                    for parent in parents[:1]:  # 1 parent par root
                        parent_name = parent.get('parent_name', '')
                        if not parent_name:
                            continue
                        
                        # Construire l'exemple avec la structure correcte
                        children = parent.get('children', [])
                        if children:
                            child_name = children[0].get('child_name', '')
                            label_hierarchy = f"{root_name} > {parent_name} > {child_name}"
                        else:
                            label_hierarchy = f"{root_name} > {parent_name}"
                        
                        local_examples.append(f"""
    **Exemple : {typo_name} > {cluster_name}**
    ```json
    {{
      "typologie_de_contexte": "{typo_name}",
      "cluster": "{cluster_name}",
      "label": "{label_hierarchy}"
    }}
    ```
    ⚠️ Notez bien : le cluster "{cluster_name}" n'apparaît PAS dans le label !
    """)
                        
                        if len(local_examples) >= 2:
                            break
                    if len(local_examples) >= 2:
                        break
                if len(local_examples) >= 2:
                    break
                
            return local_examples
        
        # Extraire du master
        typo_name = master_data.get('name', 'Typologie')
        examples.extend(extract_from_typologie(master_data, typo_name))
        
        # Extraire des contextes
        for ctx in contexts[:1]:  # Max 1 contexte
            ctx_data = ctx.get('full_data', {})
            if ctx_data:
                ctx_typo_name = ctx_data.get('name', 'Contexte')
                examples.extend(extract_from_typologie(ctx_data, ctx_typo_name))
        
        if examples:
            result = "\n### 💡 EXEMPLES DE VOTRE TAXONOMIE\n"
            result += "Ces exemples montrent comment SÉPARER correctement cluster et label :\n"
            result += '\n'.join(examples[:3])  # Max 3 exemples
            return result
        
        return ""


    def _extract_real_examples(self, master_data: Dict[str, Any], contexts: list) -> str:
        """
        Extrait des exemples concrets depuis la taxonomie réelle
        """
        examples = []
        example_count = 0

        # Nom de la typologie master
        typo_name = master_data.get('name', 'Typologie')

        # Extraire des exemples du master
        clusters = master_data.get('taxonomy_clusters', [])

        for cluster in clusters[:2]:  # Max 2 clusters
            cluster_name = cluster.get('cluster_name', '')
            if not cluster_name:
                continue

            roots = cluster.get('root_labels', [])
            for root in roots[:1]:  # 1 root par cluster
                root_name = root.get('root_name', '')
                if not root_name:
                    continue

                parents = root.get('parent_labels', [])
                for parent in parents[:1]:  # 1 parent par root
                    parent_name = parent.get('parent_name', '')
                    if not parent_name:
                        continue
                    
                    example_count += 1

                    # Construire le label hiérarchique
                    children = parent.get('children', [])
                    if children:
                        child_name = children[0].get('child_name', '')
                        label_hierarchy = f"{root_name} > {parent_name} > {child_name}"
                    else:
                        label_hierarchy = f"{root_name} > {parent_name}"

                    example = f"""
    ### Exemple {example_count} - Basé sur votre taxonomie
    ```json
    {{
      "sample_id": {example_count},
      "input": "Comment accéder à {parent_name.lower()} ?",
      "combinaisons": [
        {{
          "typologie_de_contexte": "{typo_name}",
          "cluster": "{cluster_name}",
          "label": "{label_hierarchy}"
        }}
      ],
      "output": "Pour accéder à {parent_name}, naviguez vers {root_name} puis sélectionnez {parent_name} dans le menu."
    }}
    ```
    """
                    examples.append(example)

                    if example_count >= 3:
                        break
                if example_count >= 3:
                    break
            if example_count >= 3:
                break
            
        if not examples:
            # Si aucun exemple extrait, utiliser un générique
            return f"""
    ### Exemple 1
    ```json
    {{
      "sample_id": 1,
      "input": "Comment faire X ?",
      "combinaisons": [
        {{
          "typologie_de_contexte": "{typo_name}",
          "cluster": "<utilisez un cluster de la taxonomie ci-dessus>",
          "label": "<utilisez un label de la taxonomie ci-dessus>"
        }}
      ],
      "output": "Pour faire X, suivez ces étapes..."
    }}
    ```

    ⚠️ **IMPORTANT**: Remplacez les valeurs entre <> par des valeurs RÉELLES de la taxonomie ci-dessus.
    """

        return '\n'.join(examples)

    #def _extract_allowed_elements(self, context: Dict[str, Any]) -> Dict[str, Any]:
    #    """
    #    ⭐ EXTRACTION des éléments AUTORISÉS pour cette combinaison
    #    """
    #    allowed = {
    #        'clusters': set(),
    #        'labels': set(),
    #        'root_labels': set(),
    #        'parent_labels': set(),
    #        'child_labels': set()
    #    }
#
    #    logger.debug(f"\n   🔎 DEBUG _extract_allowed_elements:")
#
    #    # ✅ FIX: master_typologie EST DÉJÀ full_data (pas besoin de unnest)
    #    master_data = context.get('master_typologie', {})
#
    #    logger.debug(f"      Master data type: {type(master_data)}")
    #    logger.debug(f"      Master data keys: {master_data.keys() if isinstance(master_data, dict) else 'NOT A DICT'}")
#
    #    if master_data and isinstance(master_data, dict):
    #        master_clusters = master_data.get('taxonomy_clusters', [])
    #        logger.debug(f"      Master clusters count: {len(master_clusters)}")
#
    #        if master_clusters:
    #            logger.debug(f"      First cluster keys: {master_clusters[0].keys() if master_clusters else 'EMPTY'}")
#
    #        for cluster_idx, cluster in enumerate(master_clusters):
    #            cluster_name = cluster.get('cluster_name', '')
    #            logger.debug(f"        Cluster {cluster_idx}: '{cluster_name}'")
#
    #            if cluster_name:
    #                allowed['clusters'].add(cluster_name)
#
    #                # Extraire les labels
    #                for root in cluster.get('root_labels', []):
    #                    root_name = root.get('root_name', '')
    #                    if root_name:
    #                        allowed['labels'].add(root_name)
    #                        allowed['root_labels'].add(root_name)
    #                        logger.debug(f"          Root: '{root_name}'")
#
    #                    for parent in root.get('parent_labels', []):
    #                        parent_name = parent.get('parent_name', '')
    #                        if parent_name:
    #                            allowed['labels'].add(parent_name)
    #                            allowed['parent_labels'].add(parent_name)
    #                            logger.debug(f"            Parent: '{parent_name}'")
#
    #                        # Récursif pour les enfants
    #                        children = parent.get('children', [])
    #                        if children:
    #                            self._extract_children_labels_recursive(
    #                                children,
    #                                allowed['labels'],
    #                                allowed['child_labels']
    #                            )
#
    #    # ✅ FIX: Extraire des contextes (full_data est déjà la bonne structure)
    #    contexts = context.get('contexts', [])
    #    logger.debug(f"      Contexts count: {len(contexts)}")
#
    #    for ctx_idx, ctx in enumerate(contexts):
    #        # ✅ FIX: full_data EST DÉJÀ la bonne structure
    #        ctx_data = ctx.get('full_data', {})
#
    #        logger.debug(f"        Context {ctx_idx} data type: {type(ctx_data)}")
    #        logger.debug(f"        Context {ctx_idx} data keys: {ctx_data.keys() if isinstance(ctx_data, dict) else 'NOT A DICT'}")
#
    #        if ctx_data and isinstance(ctx_data, dict):
    #            ctx_clusters = ctx_data.get('taxonomy_clusters', [])
    #            logger.debug(f"        Context {ctx_idx} clusters count: {len(ctx_clusters)}")
#
    #            for cluster in ctx_clusters:
    #                cluster_name = cluster.get('cluster_name', '')
    #                if cluster_name:
    #                    allowed['clusters'].add(cluster_name)
#
    #                    # Même extraction que pour le master
    #                    for root in cluster.get('root_labels', []):
    #                        root_name = root.get('root_name', '')
    #                        if root_name:
    #                            allowed['labels'].add(root_name)
    #                            allowed['root_labels'].add(root_name)
#
    #                        for parent in root.get('parent_labels', []):
    #                            parent_name = parent.get('parent_name', '')
    #                            if parent_name:
    #                                allowed['labels'].add(parent_name)
    #                                allowed['parent_labels'].add(parent_name)
#
    #                            self._extract_children_labels_recursive(
    #                                parent.get('children', []),
    #                                allowed['labels'],
    #                                allowed['child_labels']
    #                            )
#
    #    logger.info(f"   ℹ️ Éléments autorisés:")
    #    logger.info(f"      Clusters: {sorted(allowed['clusters'])}")
    #    logger.info(f"      Labels totaux: {len(allowed['labels'])}")
    #    logger.info(f"        - Roots: {len(allowed['root_labels'])}")
    #    logger.info(f"        - Parents: {len(allowed['parent_labels'])}")
    #    logger.info(f"        - Children: {len(allowed['child_labels'])}")
#
    #    return allowed
    
    def _extract_children_labels_recursive(self, children: List[Dict], all_labels: set, child_labels: set):
        """Extrait récursivement tous les labels enfants"""
        for child in children:
            child_name = child.get('child_name', '')
            if child_name:
                all_labels.add(child_name)
                child_labels.add(child_name)
            # Récursif si sous-enfants
            self._extract_children_labels_recursive(
                child.get('children', []), 
                all_labels,
                child_labels
            )
    
    def _extract_children_labels(self, children: List[Dict], labels_set: set):
        """Extrait récursivement tous les labels enfants"""
        for child in children:
            child_name = child.get('child_name', '')
            if child_name:
                labels_set.add(child_name)
            # Récursif si sous-enfants
            self._extract_children_labels(child.get('children', []), labels_set)
    
    #def _validate_sample(self, sample: Dict[str, Any], allowed: Dict[str, Any]) -> bool:
    #    """
    #    ⭐ VALIDATION : Vérifie que le sample respecte les éléments autorisés
    #    """
    #    cluster = sample.get('cluster', '').strip()
    #    label = sample.get('label', '').strip()
    #    
    #    # Vérifier cluster
    #    if cluster and cluster not in allowed['clusters']:
    #        logger.warning(f"      ❌ Cluster '{cluster}' non autorisé")
    #        return False
    #    
    #    # Vérifier label
    #    if label and label not in allowed['labels']:
    #        logger.warning(f"      ❌ Label '{label}' non autorisé")
    #        return False
    #    
    #    return True
    
    def _build_context(self, combination: Dict[str, Any]) -> Dict[str, Any]:
        """Construit le contexte complet de la combinaison"""
        context = {
            'master_typologie': combination['master']['full_data'],
            'master_name': combination['master']['name'],
            'contexts': []
        }

        for ctx in combination['contexts']:
            context['contexts'].append({
                'level': ctx.get('level', 'unknown'),
                'display': ctx.get('display', 'N/A'),
                'structure': ctx.get('structure_summary', {}),
                'full_data': ctx.get('full_data', {})
            })

        # ✅ DEBUG : Vérifier ce qui est passé
        logger.debug(f"\n   🔍 DEBUG _build_context:")
        logger.debug(f"      Master name: {context['master_name']}")
        logger.debug(f"      Master has clusters: {bool(context['master_typologie'].get('taxonomy_clusters'))}")
        logger.debug(f"      Contexts count: {len(context['contexts'])}")
        for idx, ctx in enumerate(context['contexts']):
            has_clusters = bool(ctx['full_data'].get('taxonomy_clusters'))
            logger.debug(f"      Context {idx+1} has clusters: {has_clusters}")

        return context
    
    def _build_strict_prompt(
        self, 
        context: Dict[str, Any], 
        nb_samples: int,
        allowed_elements: Dict[str, Any]
    ) -> str:
        """
        ⭐ PROMPT STRICT : Force l'IA à rester dans les limites de la combinaison
        """
        master_name = context['master_name']
        master_data = context['master_typologie']
        contexts = context['contexts']

        prompts = self.generation_config.get('prompts', {})
        global_context = prompts.get('global_context', '')
        local_prompt = prompts.get('local_prompt', '')
        
        # Formater la typologie master
        master_section = self._format_typologie(master_data, "TYPOLOGIE MASTER")
        
        # Formater les contextes
        context_sections = []
        for idx, ctx in enumerate(contexts):
            ctx_section = f"\n### CONTEXTE {idx + 1} ({ctx['level']}): {ctx['display']}\n"
            ctx_section += self._format_typologie(ctx['full_data'], "Typologie du contexte")
            context_sections.append(ctx_section)
        
        # ⭐ LISTE EXPLICITE des éléments autorisés
        allowed_clusters_str = ", ".join(sorted(allowed_elements['clusters']))
        allowed_labels_str = ", ".join(sorted(allowed_elements['labels']))
        
        prompt = f"""# 🤖 GÉNÉRATION STRICTE DE DATASET POUR IA CONVERSATIONNELLE

## ⚠️ RÈGLE ABSOLUE : RESTER DANS LA COMBINAISON

Vous générez un dataset d'entraînement pour un **chatbot conversationnel**.
Vous DEVEZ générer des exemples UNIQUEMENT basés sur la combinaison taxonomique fournie ci-dessous.

❌ **INTERDIT** : Inventer des catégories, clusters ou labels non présents dans la taxonomie
✅ **OBLIGATOIRE** : Utiliser UNIQUEMENT les éléments listés dans "ÉLÉMENTS AUTORISÉS"

## 📊 ÉLÉMENTS AUTORISÉS POUR CETTE COMBINAISON

### Clusters autorisés :
{allowed_clusters_str or "Tous les clusters du master"}

### Labels autorisés :
{allowed_labels_str or "Tous les labels du master"}

⚠️ **ATTENTION** : Si vous utilisez un cluster ou label NON présent dans cette liste, 
le sample sera REJETÉ automatiquement.

## 📚 TAXONOMIE DE RÉFÉRENCE

### TYPOLOGIE MASTER : {master_name}
{master_section}

### CONTEXTES SPÉCIFIQUES (SCOPE DE CETTE COMBINAISON)
{''.join(context_sections)}

## 📋 FORMAT DE SORTIE OBLIGATOIRE

Chaque échantillon doit suivre cette structure JSON **EXACTEMENT** :

```json
{{
  "sample_id": <numéro>,
  "typologie de contexte": "<typologie_de_contexte_depuis_liste_autorisée>",
  "cluster": "<cluster_depuis_liste_autorisée>",
  "label": "<label_depuis_liste_autorisée>",
  "input": "<question_utilisateur_naturelle>",
  "output": "<réponse_chatbot_actionnable>"
}}
```

### 🔍 CONTRAINTES SUR LES CHAMPS
1.**typologie de context** : DOIT être un cluster de la liste autorisée ci-dessus
2. **cluster** : DOIT être un cluster de la liste autorisée ci-dessus
3. **label** : DOIT être un label de la liste autorisée ci-dessus
4. **input** : Question naturelle en lien avec le cluster/label
5. **output** : Réponse précise avec chemins de navigation

## ✅ RÈGLES DE GÉNÉRATION

### 🎯 COHÉRENCE STRICTE
- ✅ Utilisez UNIQUEMENT les éléments de la liste "ÉLÉMENTS AUTORISÉS"
- ✅ Vérifiez que chaque cluster/label existe dans la taxonomie fournie
- ❌ N'inventez JAMAIS de nouvelles catégories
- ❌ Ne vous écartez JAMAIS des contextes spécifiques fournis

### 🗣️ STYLE CONVERSATIONNEL (IA de support)
- Questions naturelles : "Comment...", "Où trouver...", "J'arrive pas à..."
- Ton accessible et professionnel
- Variations de formulation
- Fautes occasionnelles (réalisme)

### 💬 RÉPONSES ACTIONNABLES
- Instructions claires avec étapes numérotées
- Chemins de navigation précis (onglets, menus, boutons)
- Ton encourageant et utile

## 🎨 EXEMPLES DE RÉFÉRENCE

### Exemple 1 : Simple
```json
{{
  "sample_id": 1,
  "cluster": "{list(allowed_elements['clusters'])[0] if allowed_elements['clusters'] else 'Tableau de bord'}",
  "label": "{list(allowed_elements['labels'])[0] if allowed_elements['labels'] else 'Vue générale'}",
  "input": "Comment je vois mon tableau de bord ?",
  "output": "Pour accéder au tableau de bord, cliquez sur l'onglet 'Tableau de bord' dans le menu principal."
}}
```

### Exemple 2 : Avec problème
```json
{{
  "sample_id": 2,
  "cluster": "{list(allowed_elements['clusters'])[0] if allowed_elements['clusters'] else 'Paramètres'}",
  "label": "{list(allowed_elements['labels'])[1] if len(allowed_elements['labels']) > 1 else 'Configuration'}",
  "input": "je trouve plus les parametres ça bug",
  "output": "Pour accéder aux paramètres : cliquez sur l'icône ⚙️ en haut à droite, puis 'Paramètres'. Si le problème persiste, rechargez la page (F5)."
}}
```

## 🚨 VALIDATION AUTOMATIQUE

Chaque sample sera automatiquement vérifié :
- ✅ Le cluster est dans la liste autorisée
- ✅ Le label est dans la liste autorisée
- ❌ Si NON conforme → Sample REJETÉ

## 📋 INSTRUCTIONS UTILISATEUR

### Contexte Global du Projet :
{global_context if global_context else "(Aucun contexte global défini)"}

### Instructions Spécifiques pour ce Batch :
{local_prompt}

## 🎯 GÉNÉRATION

Générez EXACTEMENT **{nb_samples} échantillon(s)** :
- Respectez les éléments autorisés ci-dessus
- Format JSON strict
- Ton conversationnel naturel
- Réponses actionnables

Retournez UNIQUEMENT un array JSON :

```json
[
  {{
    "sample_id": 1,
    "typologie de context": "...",
    "cluster": "...",
    "label": "...",
    "input": "...",
    "output": "..."
  }}
]
```

**PAS de texte avant/après le JSON.**
**COMMENCEZ MAINTENANT.**
"""
        
        return prompt
    
    def _format_typologie(self, typologie_data: Dict[str, Any], title: str) -> str:
        """
        Formate une typologie en texte lisible AVEC EXEMPLES EXPLICITES
        """
        if not typologie_data:
            return f"\n### {title}\n(Vide)\n"

        output = [f"\n### {title}"]
        typo_name = typologie_data.get('name', 'Sans nom')
        output.append(f"**Nom de la typologie:** {typo_name}")
        output.append(f"**⚠️ UTILISEZ CE NOM comme 'typologie_de_contexte' dans vos échantillons**\n")

        clusters = typologie_data.get('taxonomy_clusters', [])
        if clusters:
            output.append(f"**Structure ({len(clusters)} cluster(s) disponibles):**\n")

            for cluster in clusters:
                cluster_name = cluster.get('cluster_name', 'Cluster')
                output.append(f"\n#### 📦 CLUSTER: **{cluster_name}**")
                output.append(f"   **⚠️ Utilisez '{cluster_name}' comme valeur de 'cluster'**\n")

                for root in cluster.get('root_labels', []):
                    root_name = root.get('root_name', 'Root')
                    output.append(f"   ├─ 🔹 ROOT: **{root_name}**")

                    for parent in root.get('parent_labels', []):
                        parent_name = parent.get('parent_name', 'Parent')
                        output.append(f"   │  ├─ PARENT: **{parent_name}**")

                        children = parent.get('children', [])
                        if children:
                            output.append(f"   │  │  └─ ENFANTS:")
                            for child in children:
                                child_name = child.get('child_name', 'Child')
                                output.append(f"   │  │     • {child_name}")
                                # Afficher les sous-enfants s'ils existent
                                self._format_sub_children(child, output, "   │  │        ")

                        # Exemple de label hiérarchique complet
                        if children:
                            example_label = f"{root_name} > {parent_name} > {children[0].get('child_name', 'Enfant')}"
                            output.append(f"   │  │")
                            output.append(f"   │  │  **💡 Exemple de label:** \"{example_label}\"")
        else:
            output.append("\n⚠️ **ATTENTION:** Aucun cluster défini dans cette typologie!")

        return '\n'.join(output)
    
    def _format_sub_children(self, child: Dict[str, Any], output: list, indent: str):
        """Formate récursivement les sous-enfants"""
        sub_children = child.get('children', [])
        if sub_children:
            for sub_child in sub_children:
                sub_name = sub_child.get('child_name', 'SubChild')
                output.append(f"{indent}  ◦ {sub_name}")
                # Récursif pour les niveaux plus profonds
                self._format_sub_children(sub_child, output, indent + "  ")

    def _call_gemini_api(self, prompt: str, nb_samples: int) -> Optional[List[Dict[str, Any]]]:
        """Appelle l'API Gemini"""
        try:
            self._log("info", "   🌐 Appel API Gemini...")
            
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": self.max_tokens,
                }
            )
            
            if not response or not response.text:
                return None
            
            samples = self._parse_json_response(response.text.strip())
            
            if samples and len(samples) != nb_samples:
                self._log("warning", f"   ⚠️ {len(samples)}/{nb_samples} samples générés")
            
            return samples
            
        except Exception as e:
            self._log("error", f"   ❌ Erreur API: {str(e)}")
            return None
    
    def _parse_json_response(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Parse la réponse JSON"""
        try:
            cleaned = text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            return data if isinstance(data, list) else [data]
        except:
            return None
    
    def _log_generation_summary(self):
        """Affiche le récapitulatif"""
        self._log("info", "\n📊 RÉCAPITULATIF")
        self._log("info", f"   • Projet: {self.project_name}")
        self._log("info", f"   • Batch: {self.batch_name} (#{self.batch_number})")
        self._log("info", f"   • Famille: {self.batch_family}")
        self._log("info", f"   • Format: {self.output_format}")
        self._log("info", f"   • Combinaisons: {len(self.combinations)}")
        self._log("info", f"   • Total samples: {self.total_samples_all_batches}")
        self._log("info", f"   • MODE: STRICT (validation auto)")
    
    def _log(self, level: str, message: str):
        """Log vers interface et logger"""
        self.log_message.emit(level, message)
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
    
    def pause(self):
        self.is_paused = True
    
    def resume(self):
        self.is_paused = False
    
    def stop(self):
        self.should_stop = True