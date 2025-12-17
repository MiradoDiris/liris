#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gemini Dataset Worker - Générateur STRICT aux combinaisons définies
❌ INTERDIT : Générer du contenu hors des combinaisons master + contextes
✅ OBLIGATOIRE : Respecter UNIQUEMENT les éléments de la taxonomie fournie
VERSION CORRIGÉE : Inclut TOUTE la structure master dans le prompt
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
        
        # ✅ NOUVEAU : Mode debug
        self.debug_mode = generation_config.get('debug_mode', True)  # Activé par défaut
        
        logger.info("🤖 GeminiDatasetWorker initialisé (MODE STRICT + DEBUG)")
    
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

            self._log("info", "🔍 Validation des structures taxonomiques...")
            for combo_idx, combo in enumerate(self.combinations):
                master_data = combo['master']['full_data']
                if not master_data.get('taxonomy_clusters'):
                    self.generation_failed.emit(f"❌ Combinaison {combo_idx+1}: master sans 'taxonomy_clusters'")
                    return
                sample_cluster = master_data['taxonomy_clusters'][0]
                if not (sample_cluster.get('name') or sample_cluster.get('cluster_name')):
                    self.generation_failed.emit(f"❌ Combinaison {combo_idx+1}: Noms manquants dans master_typologie")
                    return
                self._log("debug", f"   Combinaison {combo_idx+1} OK: '{combo['master']['name']}'")
            
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
        ✅ CORRIGÉ : sample_id utilise TOUJOURS le compteur global
        """
        samples = []
        nb_samples = combination.get('nb_samples', 1)
    
        self._log("info", f"   🎯 Génération de {nb_samples} sample(s)...")
    
        # Construire le contexte EXACT de cette combinaison
        context = self._build_context(combination)
    
        # Construire le prompt
        final_prompt = self._build_flexible_prompt(context, nb_samples)
    
        # 📝 LOGGER LE PROMPT DANS UN FICHIER
        self._log_prompt_to_file(final_prompt, combination, combo_idx, batch_number)
    
        try:
            generated_data = self._call_gemini_api(final_prompt, nb_samples)
    
            if generated_data:
                for idx, sample in enumerate(generated_data):
                    self.global_sample_counter += 1  # ✅ Incrémentation AVANT utilisation
    
                    if 'combinaisons' in sample and sample['combinaisons']:
                        combinaisons = sample['combinaisons']
                        self._log("debug", f"      ✅ Sample #{self.global_sample_counter}: format 'combinaisons' détecté")
                    else:
                        self._log("debug", f"      ⚠️ Sample #{self.global_sample_counter}: format legacy, reconstruction...")
                        combinaisons = self._build_combinaisons_from_sample(sample, combination)
    
                    enriched_sample = {
                        'sample_id': self.global_sample_counter,  # ✅ TOUJOURS le compteur global, jamais celui de Gemini
                        'input': sample.get('input', ''),
                        'combinaisons': combinaisons,
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
        """Construit la liste des combinaisons à partir du sample généré (FORMAT LEGACY)"""
        combinaisons = []

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

        combo = {
            'typologie_de_contexte': typologie.strip(),
            'cluster': cluster.strip()
        }

        separators = [' > ', ' / ', ' - ']
        parts = [label]

        for sep in separators:
            if sep in label:
                parts = [p.strip() for p in label.split(sep)]
                break
            
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

        return combinaisons

    def _build_flexible_prompt(self, context: Dict[str, Any], nb_samples: int) -> str:
        """
        ⭐ PROMPT FLEXIBLE : Génération libre basée sur la taxonomie fournie
        CORRECTION : Inclure TOUTE la structure master (clusters, labels, hiérarchie)
        """
        master_name = context['master_name']
        master_data = context['master_typologie']
        contexts = context['contexts']

        self._log("debug", f"\n🔍 _build_flexible_prompt - Vérification master_data")
        self._log("debug", f"   master_data keys : {list(master_data.keys())}")

        if not master_data.get('taxonomy_clusters'):
            self._log("error", f"❌ taxonomy_clusters MANQUANT dans master_data !")
            self._log("error", f"   Keys disponibles : {list(master_data.keys())}")
            raise ValueError("taxonomy_clusters manquant dans master_data")

        clusters = master_data['taxonomy_clusters']
        self._log("debug", f"   ✅ {len(clusters)} clusters à formater")

        prompts = self.generation_config.get('prompts', {})
        global_context = prompts.get('global_context', '')
        local_prompt = prompts.get('local_prompt', '')

        # ✅ VÉRIFICATION : La typologie master contient-elle bien les clusters ?
        if not master_data or not master_data.get('taxonomy_clusters'):
            self._log("error", f"⚠️ ATTENTION : Typologie master '{master_name}' VIDE ou SANS clusters !")
            self._log("error", f"   master_data keys: {master_data.keys() if master_data else 'NONE'}")

            # FALLBACK : essayer de récupérer depuis generation_config
            if 'master_typologie' in self.generation_config:
                fallback_master = self.generation_config['master_typologie'].get('full_data', {})
                if fallback_master and fallback_master.get('taxonomy_clusters'):
                    self._log("warning", "   🔄 Utilisation des données master depuis generation_config")
                    master_data = fallback_master
                else:
                    self._log("error", "   ❌ Impossible de récupérer la structure master !")
                    ### CORRECTION : Blocage si fallback échoue
                    raise ValueError(f"Structure master invalide pour '{master_name}' - Génération impossible.")
        else:
            clusters_count = len(master_data.get('taxonomy_clusters', []))
            self._log("info", f"   ✅ Typologie master '{master_name}' : {clusters_count} cluster(s)")

            ### CORRECTION : Log détaillé des premiers noms pour debug
            if clusters_count > 0:
                first_cluster = master_data['taxonomy_clusters'][0]
                cluster_name = first_cluster.get('cluster_name') or first_cluster.get('name', 'MISSING')
                if cluster_name == 'MISSING':
                    self._log("error", f"   ❌ Premier cluster sans 'name' dans master: {first_cluster.keys()}")
                else:
                    self._log("debug", f"   Premier cluster: '{cluster_name}'")

        # ✅ FORMATER LA TYPOLOGIE MASTER COMPLÈTE
        master_section = self._format_typologie_detailed(master_data, f"TYPOLOGIE MASTER : {master_name}")

        # ✅ VÉRIFICATION : Le master_section contient-il vraiment les clusters ?
        if "📦 CLUSTER" not in master_section:
            self._log("error", f"❌ master_section ne contient AUCUN cluster !")
            self._log("error", f"   Longueur : {len(master_section)} caractères")
            self._log("error", f"   Extrait : {master_section[:500]}")
            raise ValueError("master_section invalide - aucun cluster formaté")

        # Compter les clusters dans le texte
        cluster_count = master_section.count("📦 CLUSTER")
        self._log("debug", f"   ✅ master_section contient {cluster_count} cluster(s) formatés")

        # Formater les contextes
        context_sections = []
        for idx, ctx in enumerate(contexts):
            ctx_section = f"\n### CONTEXTE {idx + 1} ({ctx['level']}): {ctx['display']}\n"
            ctx_data = ctx.get('full_data', {})

            if not ctx_data or not ctx_data.get('taxonomy_clusters'):
                self._log("warning", f"   ⚠️ Contexte {idx+1} '{ctx['display']}' VIDE ou SANS clusters")
            else:
                ctx_clusters = len(ctx_data.get('taxonomy_clusters', []))
                self._log("debug", f"   ✅ Contexte {idx+1} '{ctx['display']}' : {ctx_clusters} cluster(s)")

            ctx_section += self._format_typologie_detailed(ctx_data, "Typologie du contexte")
            context_sections.append(ctx_section)

        # ✅ EXTRAIRE DES EXEMPLES CONCRETS
        exemple_structure = self._extract_structure_examples(master_data, contexts)

        prompt = f"""# 🤖 GÉNÉRATION DE DATASET POUR IA CONVERSATIONNELLE

    Voici le description de contexte:
    Nous avons créé un environnement basé sur des arbres taxonomiques de clusters et de labels,
    comprenant plusieurs niveaux hiérarchiques correspondant à la classification des données.
    Chaque label représente une structure taxonomique, utilisée pour classifier les inputs des utilisateurs et produire les outputs associés.
    Ta tâche est de générer un dataset complet comme si tu étais à la place de l’utilisateur :
    Crée des inputs réalistes correspondant aux différents labels que tu reçois.
    Fournis pour chaque input le label complet (tous les niveaux de la hiérarchie).
    Fournis également l’output correspondant à cet input selon la classification.
    Le résultat doit permettre de relier de manière cohérente chaque input utilisateur à son label et à l’output associé,
    en respectant la structure hiérarchique des labels.
    Classification de donnée d’un environnement de logiciel SaaS comptable. Le but est de déterminer toutes les typologies de contexte,
    de les trier et de les structurer correctement Le detaset est pour fine tuner un agent qui s’appelle Emma et qui connaît parfaitement la comptabilité et le logiciel comptable 
    
    
    NB: La combinaison doit etre entre de typologie de contexte minimum, 1 master avec 1 ou plusieurs autre contextes
    
    ## 📚 TAXONOMIE DE RÉFÉRENCE

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
    🔍 COMPRENDRE LA STRUCTURE HIÉRARCHIQUE
    ⚠️ RÈGLE CRITIQUE : Dans votre taxonomie, la hiérarchie est :

    typologie_de_contexte : Le nom de la typologie (ex: "UX/UI", "Intention")
    cluster : Le PREMIER niveau sous la typologie (ex: "Paramètres", "Modules", "Explications")
    label : La hiérarchie COMPLÈTE en dessous du cluster (ex: "Affichage > Thème > Mode sombre")

    {exemple_structure}
    📊 RÈGLES POUR REMPLIR LES CHAMPS

    typologie_de_contexte :
    Utilisez le NOM de la typologie (visible en haut de chaque section)

    cluster :
    Utilisez le nom du 📦 CLUSTER (premier niveau sous la typologie)
    ⚠️ NE PAS écrire "Cluster" comme valeur !

    label :
    La hiérarchie COMPLÈTE en dessous du cluster
    Utilisez " > " (espace-chevron-espace) pour séparer les niveaux
    ⚠️ N'incluez PAS le cluster dans le label !


    📋 INSTRUCTIONS UTILISATEUR
    Contexte Global du Projet :
    {global_context if global_context else "(Aucun contexte global défini)"}
    Instructions Spécifiques pour ce Batch :
    {local_prompt}
    🎯 GÉNÉRATION
    ⚠️ CONTRAINTE CRITIQUE : Générez EXACTEMENT {nb_samples} échantillon(s), ni plus ni moins.
    Retournez UNIQUEMENT un array JSON contenant EXACTEMENT {nb_samples} objet(s) :
    JSON[
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
    ⚠️ RÈGLES STRICTES :

    Générez EXACTEMENT {nb_samples} échantillon(s)
    cluster doit être le nom du 📦 CLUSTER, PAS "Cluster" !
    label ne doit PAS contenir le cluster
    NE PAS écrire de texte explicatif avant le JSON
    NE PAS utiliser de balises markdown ```json
    Retournez DIRECTEMENT l'array JSON commençant par [

    COMMENCEZ MAINTENANT.
    """
        return prompt
    
    def _format_typologie_detailed(self, typologie_data: Dict[str, Any], title: str) -> str:
        """
        Formate une typologie en texte ULTRA-DÉTAILLÉ avec TOUTE la structure
        VERSION ENRICHIE : affiche TOUS les niveaux hiérarchiques
        """
        if not typologie_data:
            return f"\n### {title}\n(Vide)\n"

        ### CORRECTION : Ajout de logs debug pour tracer la structure brute
        self._log("debug", f"🔍 DEBUG {title} - Keys globales: {list(typologie_data.keys())}")
        clusters = typologie_data.get('taxonomy_clusters', [])
        self._log("debug", f"   Nombre de clusters: {len(clusters)}")
        if clusters:
            first_cluster = clusters[0]
            self._log("debug", f"   Premier cluster keys: {list(first_cluster.keys())}")
            cluster_name_raw = first_cluster.get('cluster_name') or first_cluster.get('name', 'MISSING')
            self._log("debug", f"   Premier cluster 'name': '{cluster_name_raw}'")

        output = [f"\n### {title}"]
        typo_name = typologie_data.get('name', 'Sans nom')
        output.append(f"**Nom de la typologie:** {typo_name}")
        output.append(f"**⚠️ UTILISEZ CE NOM comme 'typologie_de_contexte' dans vos échantillons**\n")

        clusters = typologie_data.get('taxonomy_clusters', [])

        if not clusters:
            output.append("\n⚠️ **ATTENTION:** Aucun cluster défini dans cette typologie!")
            output.append("Cette typologie est VIDE - impossible de générer des échantillons valides.\n")
            return '\n'.join(output)

        output.append(f"**Structure ({len(clusters)} cluster(s) disponibles):**\n")

        # ✅ AFFICHER CHAQUE CLUSTER EN DÉTAIL
        for cluster_idx, cluster in enumerate(clusters):
            # ✅ SUPPORT DES DEUX FORMATS : "cluster_name" OU "name"
            cluster_name = cluster.get('cluster_name') or cluster.get('name', f'Cluster{cluster_idx+1}')

            ### CORRECTION : Warning si fallback activé
            if cluster_name == f'Cluster{cluster_idx+1}':
                self._log("warning", f"⚠️ Fallback cluster name pour {title}: '{cluster_name}' - Vérifiez 'name' dans full_data !")

            output.append(f"\n#### 📦 CLUSTER {cluster_idx+1}: **{cluster_name}**")
            output.append(f"   **⚠️ Utilisez '{cluster_name}' comme valeur de 'cluster'**\n")

            roots = cluster.get('root_labels', [])

            if not roots:
                output.append(f"   ⚠️ Cluster '{cluster_name}' VIDE (aucun root)\n")
                continue
            
            # ✅ AFFICHER CHAQUE ROOT
            for root_idx, root in enumerate(roots):
                # ✅ SUPPORT DES DEUX FORMATS : "root_name" OU "name"
                root_name = root.get('root_name') or root.get('name', f'Root{root_idx+1}')

                ### CORRECTION : Warning si fallback pour root
                if root_name == f'Root{root_idx+1}':
                    self._log("warning", f"⚠️ Fallback root name dans {title}: '{root_name}' - Vérifiez structure root_labels")

                output.append(f"   ├─ 🔹 ROOT: **{root_name}**")

                parents = root.get('parent_labels', [])

                if not parents:
                    output.append(f"   │  └─ ⚠️ Root '{root_name}' sans parents")
                    output.append(f"   │     💡 **Exemple de label:** \"{root_name}\"")
                    continue
                
                # ✅ AFFICHER CHAQUE PARENT
                for parent_idx, parent in enumerate(parents):
                    # ✅ SUPPORT DES DEUX FORMATS : "parent_name" OU "name"
                    parent_name = parent.get('parent_name') or parent.get('name', f'Parent{parent_idx+1}')

                    ### CORRECTION : Warning si fallback pour parent
                    if parent_name == f'Parent{parent_idx+1}':
                        self._log("warning", f"⚠️ Fallback parent name dans {title}: '{parent_name}'")

                    is_last_parent = (parent_idx == len(parents) - 1)
                    prefix = "   │  └─" if is_last_parent else "   │  ├─"

                    output.append(f"{prefix} PARENT: **{parent_name}**")

                    children = parent.get('children', [])

                    if not children:
                        example_label = f"{root_name} > {parent_name}"
                        child_prefix = "   │  │  " if not is_last_parent else "   │     "
                        output.append(f"{child_prefix}💡 **Exemple de label:** \"{example_label}\"")
                    else:
                        child_prefix = "   │  │  " if not is_last_parent else "   │     "
                        output.append(f"{child_prefix}└─ ENFANTS:")
                        self._format_children_recursive(children, output, child_prefix + "   ", root_name, parent_name)

                output.append("")

        # ✅ STATISTIQUES GLOBALES
        total_clusters = len(clusters)
        total_roots = sum(len(c.get('root_labels', [])) for c in clusters)
        total_parents = sum(
            len(r.get('parent_labels', []))
            for c in clusters
            for r in c.get('root_labels', [])
        )
        total_children = sum(
            self._count_children_recursive(p.get('children', []))
            for c in clusters
            for r in c.get('root_labels', [])
            for p in r.get('parent_labels', [])
        )

        output.append(f"\n📊 **STATISTIQUES DE CETTE TYPOLOGIE:**")
        output.append(f"   • Clusters: {total_clusters}")
        output.append(f"   • Roots: {total_roots}")
        output.append(f"   • Parents: {total_parents}")
        output.append(f"   • Children (tous niveaux): {total_children}")
        output.append("")

        return '\n'.join(output)
    
    def _format_children_recursive(self, children: List[Dict], output: list, indent: str, root_name: str, parent_name: str):
        """Formate récursivement TOUS les enfants et sous-enfants"""
        for child_idx, child in enumerate(children):
            # ✅ SUPPORT DES DEUX FORMATS : "child_name" OU "name"
            child_name = child.get('child_name') or child.get('name', f'Child{child_idx+1}')
            is_last = (child_idx == len(children) - 1)
            
            symbol = "└─" if is_last else "├─"
            output.append(f"{indent}{symbol} {child_name}")
            
            example_label = f"{root_name} > {parent_name} > {child_name}"
            next_indent = indent + ("   " if is_last else "│  ")
            output.append(f"{next_indent}💡 **Exemple de label:** \"{example_label}\"")
            
            sub_children = child.get('children', [])
            if sub_children:
                output.append(f"{next_indent}└─ SOUS-ENFANTS:")
                self._format_children_recursive(
                    sub_children, 
                    output, 
                    next_indent + "   ", 
                    root_name, 
                    f"{parent_name} > {child_name}"
                )
    
    def _count_children_recursive(self, children: List[Dict]) -> int:
        """Compte récursivement tous les enfants"""
        if not children:
            return 0
        count = len(children)
        for child in children:
            count += self._count_children_recursive(child.get('children', []))
        return count
    
    def _extract_structure_examples(self, master_data: Dict[str, Any], contexts: list) -> str:
        """Extrait des exemples CONCRETS de la structure cluster/label"""
        examples = []
        
        def extract_from_typologie(typo_data: Dict[str, Any], typo_name: str):
            local_examples = []
            clusters = typo_data.get('taxonomy_clusters', [])
            
            for cluster in clusters[:2]:
                # ✅ SUPPORT DES DEUX FORMATS
                cluster_name = cluster.get('cluster_name') or cluster.get('name', '')
                if not cluster_name:
                    continue
                
                roots = cluster.get('root_labels', [])
                for root in roots[:1]:
                    # ✅ SUPPORT DES DEUX FORMATS
                    root_name = root.get('root_name') or root.get('name', '')
                    if not root_name:
                        continue
                    
                    parents = root.get('parent_labels', [])
                    for parent in parents[:1]:
                        # ✅ SUPPORT DES DEUX FORMATS
                        parent_name = parent.get('parent_name') or parent.get('name', '')
                        if not parent_name:
                            continue
                        
                        children = parent.get('children', [])
                        if children:
                            # ✅ SUPPORT DES DEUX FORMATS
                            child_name = children[0].get('child_name') or children[0].get('name', '')
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
        
        typo_name = master_data.get('name', 'Typologie')
        examples.extend(extract_from_typologie(master_data, typo_name))
        
        for ctx in contexts[:1]:
            ctx_data = ctx.get('full_data', {})
            if ctx_data:
                ctx_typo_name = ctx_data.get('name', 'Contexte')
                examples.extend(extract_from_typologie(ctx_data, ctx_typo_name))
        
        if examples:
            result = "\n### 💡 EXEMPLES DE VOTRE TAXONOMIE\n"
            result += "Ces exemples montrent comment SÉPARER correctement cluster et label :\n"
            result += '\n'.join(examples[:3])
            return result
        
        return ""

    def _log_prompt_to_file(self, prompt: str, combination: Dict[str, Any], combo_idx: int, batch_number: int):
        """Exporte chaque prompt envoyé à Gemini dans un fichier"""
        try:
            from pathlib import Path

            logs_dir = Path("generation_logs") / "prompts"
            logs_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"prompt_batch{batch_number}_combo{combo_idx + 1}_{timestamp}.json"
            filepath = logs_dir / filename

            # ✅ CORRECTION : Inclure TOUTE la structure master
            master_full_data = combination['master'].get('full_data', {})

            export_data = {
                "timestamp": datetime.now().isoformat(),
                "batch_number": batch_number,
                "combination_index": combo_idx + 1,
                "nb_samples_requested": combination.get('nb_samples', 1),
                "combination_details": {
                    "master": {
                        "name": combination['master']['name'],
                        "taxonomy_clusters": master_full_data.get('taxonomy_clusters', [])  # ✅ Structure complète
                    },
                    "contexts": [
                        {
                            "level": ctx['level'],
                            "display": ctx['display'],
                            "taxonomy_clusters": ctx.get('full_data', {}).get('taxonomy_clusters', [])
                        }
                        for ctx in combination['contexts']
                    ]
                },
                "prompt_sent_to_gemini": prompt,
                "model": self.model_name,
                "generation_config": {
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": self.max_tokens
                }
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"   📝 Prompt loggé : {filepath}")

        except Exception as e:
            logger.error(f"   ❌ Erreur log prompt : {str(e)}")
    
    def _build_context(self, combination: Dict[str, Any]) -> Dict[str, Any]:
        """Construit le contexte complet de la combinaison"""

        # ✅ LOG DÉTAILLÉ
        self._log("debug", f"\n{'='*60}")
        self._log("debug", f"🔍 _build_context - Combo {combination.get('combination_index', '?')}")

        master_obj = combination.get('master', {})
        master_name = master_obj.get('name', 'N/A')
        master_full_data = master_obj.get('full_data', {})

        self._log("debug", f"📦 Master name : {master_name}")
        self._log("debug", f"📦 master_full_data keys : {list(master_full_data.keys())}")

        # ✅ VÉRIFICATION CRITIQUE
        if not master_full_data:
            raise ValueError(f"❌ master_full_data est VIDE pour master '{master_name}'")

        if 'taxonomy_clusters' not in master_full_data:
            self._log("error", f"❌ taxonomy_clusters MANQUANT dans master_full_data")
            self._log("error", f"   Keys disponibles : {list(master_full_data.keys())}")
            raise ValueError(f"taxonomy_clusters MANQUANT pour master '{master_name}'")

        clusters = master_full_data.get('taxonomy_clusters', [])
        self._log("debug", f"✅ {len(clusters)} cluster(s) trouvés")

        if len(clusters) == 0:
            raise ValueError(f"❌ taxonomy_clusters est VIDE pour master '{master_name}'")

        # Vérifier le premier cluster
        first_cluster = clusters[0]
        cluster_name = first_cluster.get('name') or first_cluster.get('cluster_name', 'MISSING')
        self._log("debug", f"   Premier cluster : '{cluster_name}'")

        context = {
            'master_typologie': master_full_data,
            'master_name': master_name,
            'contexts': []
        }

        # Traiter les contextes
        for ctx in combination.get('contexts', []):
            ctx_full = ctx.get('full_data', {})

            self._log("debug", f"   Context '{ctx.get('display', 'N/A')}' : {len(ctx_full.get('taxonomy_clusters', []))} clusters")

            context['contexts'].append({
                'level': ctx.get('level', 'unknown'),
                'display': ctx.get('display', 'N/A'),
                'structure': ctx.get('structure_summary', {}),
                'full_data': ctx_full
            })

        self._log("debug", f"✅ Context construit : master + {len(context['contexts'])} contextes")
        self._log("debug", f"{'='*60}\n")

        return context

    def _call_gemini_api(self, prompt: str, nb_samples: int) -> Optional[List[Dict[str, Any]]]:
        """
        ✅ VERSION CORRIGÉE avec diagnostics complets
        """
        try:
            self._log("info", "   🌐 Appel API Gemini...")
            
            # ✅ LOG DU PROMPT (premiers 500 chars)
            if self.debug_mode:
                self._log("debug", f"\n{'='*60}")
                self._log("debug", f"PROMPT ENVOYÉ (premiers 500 chars):")
                self._log("debug", prompt[:500] + "...")
                self._log("debug", f"{'='*60}")
            
            # Configuration de génération
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": self.max_tokens,
            }
            
            # ✅ APPEL API AVEC GESTION D'ERREURS
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # ✅ VÉRIFIER LES BLOQUAGES DE SÉCURITÉ
            if hasattr(response, 'prompt_feedback'):
                feedback = response.prompt_feedback
                if hasattr(feedback, 'block_reason') and feedback.block_reason:
                    reason = feedback.block_reason
                    self._log("error", f"   ❌ PROMPT BLOQUÉ par Gemini!")
                    self._log("error", f"   Raison: {reason}")
                    if hasattr(feedback, 'safety_ratings'):
                        self._log("error", f"   Safety ratings: {feedback.safety_ratings}")
                    return None
            
            # ✅ VÉRIFIER LA PRÉSENCE DE CANDIDATS
            if not hasattr(response, 'candidates') or not response.candidates:
                self._log("error", "   ❌ Aucun candidat retourné par Gemini")
                self._log("error", f"   Response type: {type(response)}")
                self._log("error", f"   Response attributes: {dir(response)}")
                return None
            
            # ✅ VÉRIFIER LE STATUT DU PREMIER CANDIDAT
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                finish_reason_name = finish_reason.name if hasattr(finish_reason, 'name') else str(finish_reason)
                
                self._log("debug", f"   Finish reason: {finish_reason_name}")
                
                if finish_reason_name != "STOP":
                    self._log("warning", f"   ⚠️ Génération incomplète: {finish_reason_name}")
                    
                    if finish_reason_name == "SAFETY":
                        self._log("error", "   ❌ Contenu bloqué par les filtres de sécurité Gemini")
                        if hasattr(candidate, 'safety_ratings'):
                            self._log("error", f"   Safety ratings: {candidate.safety_ratings}")
                        return None
                    
                    elif finish_reason_name == "MAX_TOKENS":
                        self._log("warning", "   ⚠️ Limite de tokens atteinte, résultat peut être tronqué")
                    
                    elif finish_reason_name == "RECITATION":
                        self._log("error", "   ❌ Contenu bloqué (récitation détectée)")
                        return None
            
            # ✅ EXTRAIRE LE TEXTE
            if not hasattr(response, 'text') or not response.text:
                self._log("error", "   ❌ Réponse vide de Gemini")
                self._log("error", f"   Candidate content: {candidate}")
                if hasattr(candidate, 'content'):
                    self._log("error", f"   Content parts: {candidate.content.parts if hasattr(candidate.content, 'parts') else 'N/A'}")
                return None
            
            response_text = response.text.strip()
            
            # ✅ LOG DE LA RÉPONSE BRUTE (ESSENTIEL POUR DEBUG)
            self._log("debug", f"\n{'='*60}")
            self._log("debug", f"RÉPONSE BRUTE DE GEMINI:")
            self._log("debug", f"Longueur: {len(response_text)} caractères")
            self._log("debug", f"Premiers 1000 chars:\n{response_text[:1000]}")
            if len(response_text) > 1000:
                self._log("debug", f"... [tronqué] ...")
                self._log("debug", f"Derniers 500 chars:\n{response_text[-500:]}")
            self._log("debug", f"{'='*60}\n")
            
            # ✅ PARSER LE JSON
            samples = self._parse_json_response(response_text)
            
            if not samples:
                self._log("error", "   ❌ PARSING JSON ÉCHOUÉ")
                self._log("error", "   💡 La réponse de Gemini n'est pas au format JSON attendu")
                
                # Sauvegarder la réponse pour analyse
                self._save_failed_response(response_text, prompt)
                return None
            
            # ✅ VALIDER LE NOMBRE DE SAMPLES
            if len(samples) != nb_samples:
                self._log("warning", f"   ⚠️ Attendu {nb_samples} samples, reçu {len(samples)}")
            
            self._log("info", f"   ✅ {len(samples)} sample(s) généré(s) et parsé(s)")
            return samples
            
        except Exception as e:
            error_type = type(e).__name__
            self._log("error", f"   ❌ EXCEPTION dans _call_gemini_api ({error_type}): {str(e)}")
            
            # ✅ DIAGNOSTICS SPÉCIFIQUES
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate" in error_msg:
                self._log("error", "   💡 CAUSE PROBABLE: Quota API dépassé")
                self._log("error", "   → Vérifiez votre quota sur https://makersuite.google.com/")
            elif "timeout" in error_msg:
                self._log("error", "   💡 CAUSE PROBABLE: Timeout réseau")
            elif "invalid" in error_msg or "authentication" in error_msg:
                self._log("error", "   💡 CAUSE PROBABLE: Clé API invalide")
            elif "safety" in error_msg or "blocked" in error_msg:
                self._log("error", "   💡 CAUSE PROBABLE: Contenu bloqué par les filtres")
            
            import traceback
            self._log("debug", f"Traceback complet:\n{traceback.format_exc()}")
            return None
        
    def _save_failed_response(self, response_text: str, prompt: str):
        """Sauvegarde une réponse qui a échoué pour analyse"""
        try:
            from pathlib import Path
            
            failed_dir = Path("generation_logs") / "failed_responses"
            failed_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = failed_dir / f"failed_response_{timestamp}.json"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "project": self.project_name,
                    "batch": self.batch_number,
                    "model": self.model_name,
                    "prompt_length": len(prompt),
                    "prompt_preview": prompt[:500],
                    "response_length": len(response_text),
                    "response_full": response_text
                }, f, ensure_ascii=False, indent=2)
            
            self._log("info", f"   💾 Réponse échouée sauvegardée: {filepath}")
            
        except Exception as e:
            self._log("error", f"   Erreur sauvegarde: {str(e)}")
    
    def _parse_json_response(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        ✅ VERSION CORRIGÉE avec diagnostics détaillés
        """
        if not text:
            self._log("error", "   ❌ Texte vide à parser")
            return None
        
        try:
            # ✅ NETTOYAGE ROBUSTE
            cleaned = text.strip()
            
            self._log("debug", f"   Parsing: longueur = {len(cleaned)} chars")
            
            # Retirer les balises markdown
            if cleaned.startswith('```json'):
                self._log("debug", "   → Retrait de ```json")
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                self._log("debug", "   → Retrait de ```")
                cleaned = cleaned[3:]
            
            if cleaned.endswith('```'):
                self._log("debug", "   → Retrait de ``` final")
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            
            # ✅ VÉRIFIER QUE ÇA COMMENCE PAR [ OU {
            if not cleaned:
                self._log("error", "   ❌ Texte vide après nettoyage")
                return None
            
            first_char = cleaned[0]
            self._log("debug", f"   Premier caractère: '{first_char}'")
            
            if first_char not in ('[', '{'):
                self._log("error", f"   ❌ Ne commence pas par [ ou {{ (caractère: '{first_char}')")
                self._log("error", f"   Premiers 200 chars: {cleaned[:200]}")
                
                # TENTATIVE DE RÉCUPÉRATION
                json_start_bracket = cleaned.find('[')
                json_start_brace = cleaned.find('{')
                
                if json_start_bracket > 0 or json_start_brace > 0:
                    if json_start_bracket > 0 and (json_start_brace < 0 or json_start_bracket < json_start_brace):
                        json_start = json_start_bracket
                    else:
                        json_start = json_start_brace
                    
                    self._log("warning", f"   🔧 Tentative récupération à partir du char {json_start}")
                    self._log("debug", f"   Texte avant JSON: '{cleaned[:json_start]}'")
                    cleaned = cleaned[json_start:]
                else:
                    self._log("error", "   ❌ Aucun caractère JSON trouvé dans toute la réponse")
                    return None
            
            # ✅ PARSE JSON
            try:
                self._log("debug", "   Tentative de parsing JSON...")
                data = json.loads(cleaned)
                self._log("debug", f"   ✅ JSON parsé avec succès (type: {type(data)})")
                
            except json.JSONDecodeError as e:
                self._log("error", f"   ❌ Erreur JSON: {str(e)}")
                self._log("error", f"   Position: ligne {e.lineno}, col {e.colno}")
                
                # Afficher le contexte de l'erreur
                error_pos = e.pos
                context_start = max(0, error_pos - 100)
                context_end = min(len(cleaned), error_pos + 100)
                context = cleaned[context_start:context_end]
                
                self._log("error", f"   Contexte de l'erreur:")
                self._log("error", f"   ...{context}...")
                
                # TENTATIVE DE RÉPARATION
                self._log("warning", "   🔧 Tentative de réparation du JSON...")
                
                # Retirer les virgules traînantes
                cleaned_v2 = cleaned.replace(',]', ']').replace(',}', '}')
                
                # Retirer les commentaires JavaScript
                import re
                cleaned_v2 = re.sub(r'//.*?\n', '\n', cleaned_v2)
                cleaned_v2 = re.sub(r'/\*.*?\*/', '', cleaned_v2, flags=re.DOTALL)
                
                try:
                    data = json.loads(cleaned_v2)
                    self._log("info", "   ✅ JSON réparé avec succès!")
                except Exception as repair_error:
                    self._log("error", f"   ❌ Réparation échouée: {repair_error}")
                    return None
            
            # ✅ CONVERTIR EN LISTE SI NÉCESSAIRE
            if isinstance(data, dict):
                self._log("debug", "   ℹ️ Objet JSON reçu, conversion en liste")
                data = [data]
            elif not isinstance(data, list):
                self._log("error", f"   ❌ Type inattendu: {type(data)}")
                self._log("error", f"   Valeur: {data}")
                return None
            
            # ✅ VALIDER LA STRUCTURE
            self._log("debug", f"   Validation de {len(data)} sample(s)...")
            
            valid_samples = []
            for idx, sample in enumerate(data):
                if not isinstance(sample, dict):
                    self._log("error", f"   ❌ Sample {idx} n'est pas un objet JSON (type: {type(sample)})")
                    continue
                
                # Vérifier les champs obligatoires
                required_fields = ['input', 'output']
                missing = [f for f in required_fields if f not in sample]
                
                if missing:
                    self._log("warning", f"   ⚠️ Sample {idx}: champs manquants {missing}")
                    self._log("debug", f"   Champs présents: {list(sample.keys())}")
                
                # Même avec des champs manquants, on garde le sample
                valid_samples.append(sample)
            
            if not valid_samples:
                self._log("error", "   ❌ Aucun sample valide après validation")
                return None
            
            self._log("info", f"   ✅ {len(valid_samples)} sample(s) valide(s)")
            return valid_samples
            
        except Exception as e:
            self._log("error", f"   ❌ Exception dans _parse_json_response: {str(e)}")
            import traceback
            self._log("debug", traceback.format_exc())
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
        elif level == "debug":
            logger.debug(message)
        else:
            logger.info(message)
    
    def pause(self):
        self.is_paused = True
    
    def resume(self):
        self.is_paused = False
    
    def stop(self):
        self.should_stop = True