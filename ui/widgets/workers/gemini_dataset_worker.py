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
        VERSION SANS CONTRAINTES - Accepte toutes les données générées
        """
        samples = []
        nb_samples = combination.get('nb_samples', 1)

        self._log("info", f"   🎯 Génération de {nb_samples} sample(s)...")

        # Construire le contexte EXACT de cette combinaison
        context = self._build_context(combination)

        # ✅ SUPPRESSION DE LA VALIDATION - On génère directement
        self._log("info", f"   ℹ️ Mode sans contraintes activé - Acceptation de toutes les données")

        # Construire le prompt (version simplifiée sans liste restrictive)
        final_prompt = self._build_flexible_prompt(context, nb_samples)

        try:
            generated_data = self._call_gemini_api(final_prompt, nb_samples)

            if generated_data:
                for idx, sample in enumerate(generated_data):
                    self.global_sample_counter += 1

                    # ✅ PAS DE VALIDATION - On accepte tout
                    enriched_sample = {
                        'sample_id': sample.get('sample_id', self.global_sample_counter),
                        'typologie_de_contexte': sample.get('typologie_de_contexte', sample.get('typologie de contexte', '')),
                        'cluster': sample.get('cluster', ''),
                        'label': sample.get('label', ''),
                        'input': sample.get('input', ''),
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
                    samples.append(enriched_sample)

                self._log("info", f"   ✅ {len(samples)} sample(s) générés et acceptés")
            else:
                self._log("warning", f"   ⚠️ Aucun sample généré")

        except Exception as e:
            self._log("error", f"   ❌ Erreur: {str(e)}")

        # Mise à jour progression
        current = (combo_idx * nb_samples) + len(samples)
        self.progress_updated.emit(
            current,
            self.total_samples_per_batch,
            f"Combinaison {combo_idx + 1}/{len(self.combinations)}"
        )

        return samples
    
    def _build_flexible_prompt(
        self, 
        context: Dict[str, Any], 
        nb_samples: int
    ) -> str:
        """
        ⭐ PROMPT FLEXIBLE : Génération libre basée sur la taxonomie fournie
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

        prompt = f"""# 🤖 GÉNÉRATION DE DATASET POUR IA CONVERSATIONNELLE

    ## 📚 TAXONOMIE DE RÉFÉRENCE

    ### TYPOLOGIE MASTER : {master_name}
    {master_section}

    ### CONTEXTES SPÉCIFIQUES
    {''.join(context_sections)}

    ## 📋 FORMAT DE SORTIE OBLIGATOIRE

    Chaque échantillon doit suivre cette structure JSON **EXACTEMENT** :

    ```json
    {{
      "sample_id": <numéro>,
      "typologie_de_contexte": "<typologie_depuis_taxonomie>",
      "cluster": "<cluster_depuis_taxonomie>",
      "label": "<label_depuis_taxonomie>",
      "input": "<question_utilisateur_naturelle>",
      "output": "<réponse_chatbot_actionnable>"
    }}
    ```

    ### 🔍 CONTRAINTES SUR LES CHAMPS
    1. **typologie_de_contexte** : Doit être une typologie de la taxonomie ci-dessus
    2. **cluster** : Doit être un cluster de la taxonomie ci-dessus
    3. **label** : Doit être un label de la taxonomie ci-dessus
    4. **input** : Question naturelle en lien avec le cluster/label
    5. **output** : Réponse précise avec chemins de navigation

    ## ✅ RÈGLES DE GÉNÉRATION

    ### 🎯 COHÉRENCE
    - ✅ Utilisez les éléments de la taxonomie fournie
    - ✅ Créez des exemples réalistes et variés
    - ✅ Assurez la cohérence entre cluster, label et contenu

    ### 🗣️ STYLE CONVERSATIONNEL (IA de support)
    - Questions naturelles : "Comment...", "Où trouver...", "J'arrive pas à ..."
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
      "typologie_de_contexte": "Application MaCompta",
      "cluster": "Tableau de bord",
      "label": "Vue générale",
      "input": "Comment je vois mon tableau de bord ?",
      "output": "Pour accéder au tableau de bord, cliquez sur l'onglet 'Tableau de bord' dans le menu principal."
    }}
    ```

    ### Exemple 2 : Avec problème
    ```json
    {{
      "sample_id": 2,
      "typologie_de_contexte": "Application MaCompta",
      "cluster": "Paramètres",
      "label": "Configuration",
      "input": "je trouve plus les parametres ça bug",
      "output": "Pour accéder aux paramètres : cliquez sur l'icône ⚙️ en haut à droite, puis 'Paramètres'. Si le problème persiste, rechargez la page (F5)."
    }}
    ```

    ## 📋 INSTRUCTIONS UTILISATEUR

    ### Contexte Global du Projet :
    {global_context if global_context else "(Aucun contexte global défini)"}

    ### Instructions Spécifiques pour ce Batch :
    {local_prompt}

    ## 🎯 GÉNÉRATION

    Générez EXACTEMENT **{nb_samples} échantillon(s)** :
    - Inspirez-vous de la taxonomie fournie
    - Format JSON strict
    - Ton conversationnel naturel
    - Réponses actionnables

    Retournez UNIQUEMENT un array JSON :

    ```json
    [
      {{
        "sample_id": 1,
        "typologie_de_contexte": "...",
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
        """Formate une typologie en texte lisible"""
        if not typologie_data:
            return f"\n### {title}\n(Vide)\n"
        
        output = [f"\n### {title}"]
        typo_name = typologie_data.get('name', 'Sans nom')
        output.append(f"**Nom:** {typo_name}")
        
        clusters = typologie_data.get('taxonomy_clusters', [])
        if clusters:
            output.append(f"\n**Structure ({len(clusters)} cluster(s)):**\n")
            
            for cluster in clusters:
                cluster_name = cluster.get('cluster_name', 'Cluster')
                output.append(f"\n#### {cluster_name}")
                
                for root in cluster.get('root_labels', []):
                    root_name = root.get('root_name', 'Root')
                    output.append(f"\n- **{root_name}** (ROOT)")
                    
                    for parent in root.get('parent_labels', []):
                        parent_name = parent.get('parent_name', 'Parent')
                        output.append(f"  - {parent_name} (PARENT)")
                        
                        children = parent.get('children', [])
                        if children:
                            child_names = [c.get('child_name', 'Child') for c in children]
                            output.append(f"    - Enfants: {', '.join(child_names)}")
        
        return '\n'.join(output)
    
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