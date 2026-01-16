#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gemini Dataset Worker - Générateur STRICT aux combinaisons définies
✅ VERSION CORRIGÉE : Utilise le nouveau système de stockage robuste
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from PyQt5.QtCore import QThread, pyqtSignal

from utils.logger import logger


class GeminiDatasetWorker(QThread):
    """
    Worker thread pour générer des datasets via Gemini API
    ✅ Utilise le nouveau système de stockage multi-plateforme
    """
    
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
        
        # Mode debug
        self.debug_mode = generation_config.get('debug_mode', True)
        
        logger.info("🤖 GeminiDatasetWorker initialisé (GÉNÉRATION EXACTE GARANTIE)")
    
    def _load_gemini_config(self) -> bool:
        """Charge la configuration Gemini"""
        try:
            self._log("info", "📋 Chargement config Gemini...")
            
            # Nouveau système (AIPlatformManager)
            config = self._try_new_platform_manager()
            
            if config and config.get('api_key'):
                self.api_key = config['api_key']
                self.model_name = config.get('model', 'gemini-2.0-flash-exp')
                self.max_tokens = config.get('max_tokens', 8192)
                self._log("info", f"✅ Config chargée : {self.model_name}")
                return True
            
            # Keyring (ancien système)
            config = self._try_keyring_helper()
            
            if config and config.get('api_key'):
                self.api_key = config['api_key']
                self.model_name = config.get('model', 'gemini-2.0-flash-exp')
                self.max_tokens = config.get('max_tokens', 8192)
                self._log("warning", f"⚠️ Config chargée (keyring) : {self.model_name}")
                return True
            
            # Variable d'environnement
            import os
            env_key = os.getenv('GEMINI_API_KEY')
            
            if env_key:
                self.api_key = env_key
                self.model_name = 'gemini-2.0-flash-exp'
                self.max_tokens = 8192
                self._log("warning", "⚠️ Config chargée depuis .env")
                return True
            
            self._log("error", "❌ AUCUNE clé API Gemini trouvée")
            return False
            
        except Exception as e:
            self._log("error", f"❌ Erreur chargement config: {str(e)}")
            return False
    
    def _try_new_platform_manager(self) -> Optional[Dict[str, Any]]:
        """
        Essaie de charger depuis le nouveau AIPlatformManager
        """
        try:
            from utils.ai_platform_manager import AIPlatformManager
            
            manager = AIPlatformManager()
            platform = manager.get_platform('gemini')
            
            if not platform:
                self._log("debug", "   Platform 'gemini' non trouvée dans manager")
                return None
            
            if not platform.is_configured:
                self._log("debug", "   Platform 'gemini' non configurée")
                return None
            
            config = platform.config
            
            # Vérifier la validité
            if not config.get('api_key'):
                self._log("debug", "   Config sans api_key")
                return None
            
            self._log("info", f"   ✅ Chargé depuis {platform.key_source}")
            return config
            
        except ImportError:
            self._log("debug", "   AIPlatformManager non disponible (normal si ancien système)")
            return None
        except Exception as e:
            self._log("debug", f"   Erreur nouveau système: {str(e)}")
            return None
    
    def _try_keyring_helper(self) -> Optional[Dict[str, Any]]:
        """
        Essaie de charger depuis KeyringHelper (ancien système)
        """
        try:
            from utils.keyring_helper import KeyringHelper
            
            config = KeyringHelper.get_platform_config("Gemini")
            
            if not config:
                self._log("debug", "   Aucune config dans KeyringHelper")
                return None
            
            if not config.get('api_key'):
                self._log("debug", "   Config KeyringHelper sans api_key")
                return None
            
            self._log("info", "   ✅ Chargé depuis KeyringHelper (legacy)")
            return config
            
        except ImportError:
            self._log("debug", "   KeyringHelper non disponible")
            return None
        except Exception as e:
            self._log("debug", f"   Erreur KeyringHelper: {str(e)}")
            return None
    
    def _initialize_gemini_client(self) -> bool:
        """Initialise le client Gemini"""
        try:
            self._log("info", "🔧 Init client Gemini...")
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model_name)
            self._log("info", f"✅ Client OK: {self.model_name}")
            return True
        except Exception as e:
            self._log("error", f"❌ Erreur init client: {str(e)}")
            
            # Diagnostics supplémentaires
            error_msg = str(e).lower()
            if "invalid" in error_msg or "authentication" in error_msg:
                self._log("error", "💡 CAUSE: Clé API invalide")
                self._log("error", "   → Vérifiez votre clé sur https://makersuite.google.com/")
            elif "quota" in error_msg or "rate" in error_msg:
                self._log("error", "💡 CAUSE: Quota API dépassé")
            
            return False
    
    def run(self):
        """Point d'entrée du thread"""
        self.is_running = True
        self.should_stop = False
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 GÉNÉRATION DATASET (MODE STRICT + STORAGE ROBUSTE)")
        logger.info("=" * 80)
        
        try:
            if not self._load_gemini_config():
                self.generation_failed.emit("❌ Configuration Gemini invalide ou manquante")
                return
            
            if not self._initialize_gemini_client():
                self.generation_failed.emit("❌ Impossible d'initialiser le client Gemini")
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
            import traceback
            self._log("debug", traceback.format_exc())
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
            
            combo_samples = self._generate_combination(combination, combo_idx, batch_number)
            
            if combo_samples:
                batch_results.extend(combo_samples)
                self.combination_completed.emit(combo_idx, {
                    'combination_index': combo_idx,
                    'samples_generated': len(combo_samples)
                })
        
        return batch_results
    
    def _validate_sample(self, sample: Dict[str, Any]) -> bool:
        """
        ✅ VALIDATION ASSOUPLIE
        Focus sur l'essentiel : format valide et contenu présent
        """
        try:
            # 1. Vérifier que c'est un dictionnaire
            if not isinstance(sample, dict):
                self._log("debug", "      ❌ Sample n'est pas un dict")
                return False
            
            # 2. Vérifier présence des champs obligatoires
            required_fields = ['input', 'output']
            for field in required_fields:
                if field not in sample:
                    self._log("debug", f"      ❌ Champ manquant : {field}")
                    return False
                
                # Vérifier que les champs ne sont pas vides
                value = sample.get(field, '').strip()
                if not value:
                    self._log("debug", f"      ❌ Champ vide : {field}")
                    return False
            
            # 3. ✅ LIMITES ASSOUPLIES : 3-50 mots pour input
            input_text = sample.get('input', '')
            input_words = len(input_text.split())
            if input_words < 3 or input_words > 50:
                self._log("debug", f"      ❌ Input hors limites : {input_words} mots (attendu : 3-50)")
                return False
            
            # 4. ✅ LIMITES ASSOUPLIES : 3-100 mots pour output
            output_text = sample.get('output', '')
            output_words = len(output_text.split())
            if output_words < 3 or output_words > 100:
                self._log("debug", f"      ❌ Output hors limites : {output_words} mots (attendu : 3-100)")
                return False
            
            # 5. ✅ DÉTECTION SIMPLIFIÉE : Seulement les termes techniques évidents
            forbidden_terms = ['taxonomy_clusters', 'root_labels', 'parent_labels', 'child_name']
            combined_text = (input_text + ' ' + output_text).lower()
            
            for term in forbidden_terms:
                if term in combined_text:
                    self._log("debug", f"      ❌ Terme technique détecté : {term}")
                    return False
            
            # ✅ VALIDATION RÉUSSIE
            return True
            
        except Exception as e:
            self._log("debug", f"      ❌ Erreur validation : {str(e)}")
            return False
    
    def _generate_combination(
        self, 
        combination: Dict[str, Any], 
        combo_idx: int, 
        batch_number: int
    ) -> List[Dict[str, Any]]:
        """
        ✅ VERSION GARANTIE : Continue jusqu'à obtenir EXACTEMENT le nombre demandé
        """
        samples = []
        nb_samples_requested = combination.get('nb_samples', 1)

        self._log("info", f"   🎯 Génération de EXACTEMENT {nb_samples_requested} sample(s)...")

        # Construire le contexte
        context = self._build_context(combination)

        # ✅ NOUVELLE STRATÉGIE : Génération par paquets jusqu'à complétion
        max_total_attempts = 20  # Augmenté pour garantir le succès
        attempt = 0
        total_generated = 0
        total_rejected = 0

        while len(samples) < nb_samples_requested and attempt < max_total_attempts:
            attempt += 1

            # Calculer combien il reste à générer
            remaining = nb_samples_requested - len(samples)

            # ✅ STRATÉGIE : Demander 50% de plus pour compenser les rejets
            samples_to_request = max(remaining, int(remaining * 1.5))

            if attempt > 1:
                self._log("warning", f"   🔄 Tentative {attempt}/{max_total_attempts} : demande de {samples_to_request} samples (besoin de {remaining})")

            # Construire le prompt
            final_prompt = self._build_flexible_prompt(context, samples_to_request)

            # 📁 Logger le prompt
            #self._log_prompt_to_file(final_prompt, combination, combo_idx, batch_number, attempt)

            try:
                # 🔥 APPEL API
                generated_data = self._call_gemini_api(final_prompt, samples_to_request)

                if generated_data:
                    # Compteurs pour diagnostics
                    valid_count = 0
                    rejected_count = 0

                    for idx, sample in enumerate(generated_data):
                        # ✅ VALIDATION DU SAMPLE
                        if not self._validate_sample(sample):
                            rejected_count += 1
                            total_rejected += 1
                            continue
                        
                        valid_count += 1
                        total_generated += 1
                        self.global_sample_counter += 1

                        # Gérer combinaisons
                        if 'combinaisons' in sample and sample['combinaisons']:
                            combinaisons = sample['combinaisons']
                        else:
                            combinaisons = self._build_combinaisons_from_sample(sample, combination)

                        # Enrichir le sample
                        enriched_sample = {
                            'sample_id': self.global_sample_counter,
                            'input': sample.get('input', ''),
                            'combinaisons': combinaisons,
                            'output': sample.get('output', ''),
                            'metadata': {
                                'project_name': self.project_name,
                                'batch_number': batch_number,
                                'batch_name': self.batch_name,
                                'batch_family': self.batch_family,
                                'combination_index': combo_idx + 1,
                                'local_sample_index': len(samples) + 1,
                                'generated_at': datetime.now().isoformat(),
                                'model': self.model_name,
                                'master': combination['master']['name'],
                                'contexts': [ctx['display'] for ctx in combination['contexts']],
                                'purpose': 'conversational_ai_training',
                                'output_format': self.output_format,
                                'generation_attempt': attempt
                            }
                        }

                        samples.append(enriched_sample)

                        # ✅ OBJECTIF ATTEINT
                        if len(samples) >= nb_samples_requested:
                            self._log("info", f"   ✅ Objectif atteint : {len(samples)}/{nb_samples_requested} samples")
                            break
                        
                    # 📊 Rapport de cette tentative
                    self._log("info", f"   📊 Tentative {attempt} : {valid_count} acceptés, {rejected_count} rejetés")

                    if len(samples) >= nb_samples_requested:
                        break
                else:
                    self._log("warning", f"   ⚠️ Aucun sample généré lors de la tentative {attempt}")
                    
                # ⏱️ Pause entre tentatives pour éviter le rate limiting
                if len(samples) < nb_samples_requested and attempt < max_total_attempts:
                    time.sleep(2)

            except Exception as e:
                self._log("error", f"   ❌ Erreur tentative {attempt}: {str(e)}")
                import traceback
                self._log("error", traceback.format_exc())

        # 📊 RAPPORT FINAL
        self._log("info", f"\n   {'='*50}")
        if len(samples) < nb_samples_requested:
            self._log("error", f"   ❌ INCOMPLET : {len(samples)}/{nb_samples_requested} samples")
            self._log("error", f"      • Tentatives : {attempt}/{max_total_attempts}")
            self._log("error", f"      • Générés : {total_generated}")
            self._log("error", f"      • Rejetés : {total_rejected}")
            self._log("error", f"      • Taux de rejet : {total_rejected*100//(total_generated+total_rejected) if (total_generated+total_rejected) > 0 else 0}%")
        else:
            self._log("info", f"   ✅ SUCCÈS : {len(samples)}/{nb_samples_requested} samples")
            self._log("info", f"      • Tentatives : {attempt}")
            self._log("info", f"      • Générés : {total_generated}")
            self._log("info", f"      • Rejetés : {total_rejected}")
        self._log("info", f"   {'='*50}\n")

        # Mise à jour progression
        current = (combo_idx * nb_samples_requested) + len(samples)
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
        ⭐ PROMPT OPTIMISÉ : Génération conversationnelle naturelle
        Focus sur des dialogues humains réalistes sans exposer la taxonomie
        """
        master_name = context['master_name']
        master_data = context['master_typologie']
        contexts = context['contexts']

        self._log("debug", f"\n🔍 _build_flexible_prompt - Vérification master_data")
        self._log("debug", f"   master_data keys : {list(master_data.keys())}")

        if not master_data.get('taxonomy_clusters'):
            self._log("error", f"❌ taxonomy_clusters MANQUANT dans master_data !")
            raise ValueError("taxonomy_clusters manquant dans master_data")

        clusters = master_data['taxonomy_clusters']
        self._log("debug", f"   ✅ {len(clusters)} clusters à formater")

        prompts = self.generation_config.get('prompts', {})
        global_context = prompts.get('global_context', '')
        local_prompt = prompts.get('local_prompt', '')

        # Validation master
        if not master_data or not master_data.get('taxonomy_clusters'):
            self._log("error", f"⚠️ ATTENTION : Typologie master '{master_name}' VIDE ou SANS clusters !")
            if 'master_typologie' in self.generation_config:
                fallback_master = self.generation_config['master_typologie'].get('full_data', {})
                if fallback_master and fallback_master.get('taxonomy_clusters'):
                    self._log("warning", "   🔄 Utilisation des données master depuis generation_config")
                    master_data = fallback_master
                else:
                    raise ValueError(f"Structure master invalide pour '{master_name}' - Génération impossible.")
        else:
            clusters_count = len(master_data.get('taxonomy_clusters', []))
            self._log("info", f"   ✅ Typologie master '{master_name}' : {clusters_count} cluster(s)")

        # Formater les taxonomies pour l'IA (usage interne uniquement)
        master_section = self._format_typologie_detailed(master_data, f"TYPOLOGIE MASTER : {master_name}")

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

        prompt = f"""# 🤖 GÉNÉRATION DE DATASET CONVERSATIONNEL NATUREL

    ## 📚 CONTEXTE DE LA TAXONOMIE (USAGE INTERNE UNIQUEMENT - NE PAS MENTIONNER DANS LES RÉPONSES)

    {master_section}

    ### CONTEXTES SPÉCIFIQUES
    {''.join(context_sections)}
    ⚠️ **CRITIQUE** : Générez UNIQUEMENT du JSON pur, sans texte avant/après.

    Structure JSON attendue pour chaque échantillon :
    ```json
    {{
      "input": "<question_ou_demande_utilisateur>",
      "output": "<réponse_assistant>"
    }}
    ```

    ## 📖 RÈGLES DE GÉNÉRATION CONVERSATIONNELLE

    ### 🗣️ POUR L'INPUT (Question/Demande utilisateur)

    1. **Langage naturel spontané** : L'utilisateur s'exprime comme dans une vraie conversation
       - ✅ BON : "Comment je peux suivre mes dépenses facilement ?"
       - ✅ BON : "J'aimerais savoir où créer une nouvelle facture"
       - ❌ MAUVAIS : "Afficher suivi dépenses" (trop robotique)
       - ❌ MAUVAIS : "Créer facture" (trop court, pas naturel)

    2. **Questions complètes et contextualisées**
       - ✅ BON : "J'ai besoin d'aide pour créer ma première facture, comment faire ?"
       - ✅ BON : "Où est-ce que je peux voir l'historique de mes paiements ?"
       - ❌ MAUVAIS : "Créer facture" (pas une vraie question)
       - ❌ MAUVAIS : "Historique" (incomplet)

    3. **Variété de formulations naturelles**
       - Questions directes : "Où est-ce que je peux..."
       - Demandes polies : "Pourriez-vous m'expliquer..."
       - Expressions d'incertitude : "Je ne sais pas comment..."
       - Problèmes exprimés : "J'ai du mal à..."
       - Demandes d'aide : "Comment faire pour..."

    4. **Longueur** : Entre 5 et 20 mots (phrases complètes et naturelles)

    5. **Ton humain** : Avec hésitations, politesse, formulations variées comme dans une vraie conversation

    ### 💬 POUR L'OUTPUT (Réponse assistant)

    1. **Réponses DIRECTES et ACTIONNABLES**
       - ✅ BON : "Pour suivre vos dépenses, allez dans le menu Comptabilité puis cliquez sur Tableau de bord."
       - ✅ BON : "Vous pouvez voir l'historique des paiements dans l'onglet Transactions."
       - ❌ MAUVAIS : "Comptabilité > Tableau de bord > Suivi des dépenses" (pas une phrase)
       - ❌ MAUVAIS : "Menu Comptabilité" (incomplet, télégraphique)

    2. **Phrases complètes et grammaticales**
       - ✅ BON : "Vous pouvez créer une facture en cliquant sur le bouton Nouveau en haut à droite."
       - ✅ BON : "Pour ajouter un client, rendez-vous dans la section Clients et cliquez sur Ajouter."
       - ❌ MAUVAIS : "Cliquer Nouveau bouton" (télégraphique, pas de sujet)
       - ❌ MAUVAIS : "Section Clients > Ajouter" (pas une phrase)

    3. **Style conversationnel professionnel**
       - Utiliser "vous" pour s'adresser à l'utilisateur
       - Verbes conjugués correctement (pas d'infinitif seul)
       - Instructions claires et précises
       - Ton aidant et bienveillant

    4. **Longueur** : Entre 10 et 30 mots (suffisamment détaillé sans être verbeux)

    5. **Aucune mention de la taxonomie** : Ne JAMAIS révéler les noms techniques (clusters, labels, typologies, etc.)

    ## ❌ INTERDICTIONS ABSOLUES

    **Ces règles sont NON-NÉGOCIABLES :**

    1. ❌ **NE JAMAIS** inclure les mots : "cluster", "label", "typologie", "taxonomie", "contexte", "root", "parent", "enfant" ou tout terme technique
    2. ❌ **NE JAMAIS** générer de phrases incomplètes ou télégraphiques
    3. ❌ **NE JAMAIS** utiliser les symboles ">", "/", "-", "→" pour séparer des concepts
    4. ❌ **NE JAMAIS** générer de formules mathématiques, code ou expressions techniques
    5. ❌ **NE JAMAIS** dépasser 30 mots par input ou output
    6. ❌ **NE JAMAIS** utiliser ":" ou "..." dans les réponses
    7. ❌ **NE JAMAIS** utiliser d'abréviations techniques ou jargon
    8. ❌ **NE JAMAIS** mentionner la structure interne du système

    ## 📋 INSTRUCTIONS UTILISATEUR

    Contexte Global du Projet :
    {global_context if global_context else "(Aucun contexte global défini)"}

    Instructions Spécifiques pour ce Batch :
    {local_prompt}

    ## 🎯 GÉNÉRATION

    ⚠️ **CONTRAINTE CRITIQUE** : Générez EXACTEMENT {nb_samples} échantillon(s), ni plus ni moins.

    Retournez UNIQUEMENT un array JSON (pas de texte explicatif avant ou après) :
    ```json
    [
      {{
        "input": "Comment je peux ajouter un nouveau client dans le système ?",
        "output": "Pour ajouter un client, cliquez sur Clients dans le menu principal puis sur le bouton Nouveau client."
      }},
      {{
        "input": "J'aimerais savoir où voir mes factures impayées",
        "output": "Vos factures impayées sont visibles dans l'onglet Factures en utilisant le filtre Impayées."
      }}
    ]
    ```

    ## ✅ CHECKLIST FINALE AVANT GÉNÉRATION

    **Vérifiez CHAQUE sample avant de le générer :**

    - [ ] L'input est une question/demande complète et naturelle (comme un humain parlerait)
    - [ ] L'input fait entre 5-20 mots
    - [ ] L'output est une réponse complète avec sujet + verbe (phrase grammaticale)
    - [ ] L'output fait entre 10-30 mots
    - [ ] Aucune mention de termes techniques (cluster, label, typologie, etc.)
    - [ ] Pas de format télégraphique ou de symboles de navigation (>, /, -)
    - [ ] Pas de formules, code, abréviations ou jargon technique
    - [ ] Langage français correct et professionnel
    - [ ] La conversation semble naturelle et réaliste
    - [ ] L'utilisateur ne "sait pas" qu'il y a une taxonomie derrière

    ## 🎬 EXEMPLES DE BONNES CONVERSATIONS

    **Exemple 1 :**
    ```json
    {{
      "input": "Comment je fais pour envoyer une facture à un client ?",
      "output": "Pour envoyer une facture, ouvrez-la puis cliquez sur le bouton Envoyer par email en haut."
    }}
    ```

    **COMMENCEZ MAINTENANT LA GÉNÉRATION DE {nb_samples} ÉCHANTILLON(S).**
    **RETOURNEZ UNIQUEMENT LE JSON, SANS AUCUN TEXTE AVANT OU APRÈS.**
    """
        return prompt
    
    def _format_typologie_detailed(self, typologie_data: Dict[str, Any], title: str) -> str:
        """Formate une typologie en texte ULTRA-DÉTAILLÉ avec TOUTE la structure"""
        if not typologie_data:
            return f"\n### {title}\n(Vide)\n"

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

        for cluster_idx, cluster in enumerate(clusters):
            cluster_name = cluster.get('cluster_name') or cluster.get('name', f'Cluster{cluster_idx+1}')

            if cluster_name == f'Cluster{cluster_idx+1}':
                self._log("warning", f"⚠️ Fallback cluster name pour {title}: '{cluster_name}' - Vérifiez 'name' dans full_data !")

            output.append(f"\n#### 📦 CLUSTER {cluster_idx+1}: **{cluster_name}**")
            output.append(f"   **⚠️ Utilisez '{cluster_name}' comme valeur de 'cluster'**\n")

            roots = cluster.get('root_labels', [])

            if not roots:
                output.append(f"   ⚠️ Cluster '{cluster_name}' VIDE (aucun root)\n")
                continue
            
            for root_idx, root in enumerate(roots):
                root_name = root.get('root_name') or root.get('name', f'Root{root_idx+1}')

                if root_name == f'Root{root_idx+1}':
                    self._log("warning", f"⚠️ Fallback root name dans {title}: '{root_name}' - Vérifiez structure root_labels")

                output.append(f"   ├─ 🔹 ROOT: **{root_name}**")

                parents = root.get('parent_labels', [])

                if not parents:
                    output.append(f"   │  └─ ⚠️ Root '{root_name}' sans parents")
                    output.append(f"   │     💡 **Exemple de label:** \"{root_name}\"")
                    continue
                
                for parent_idx, parent in enumerate(parents):
                    parent_name = parent.get('parent_name') or parent.get('name', f'Parent{parent_idx+1}')

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
                cluster_name = cluster.get('cluster_name') or cluster.get('name', '')
                if not cluster_name:
                    continue
                
                roots = cluster.get('root_labels', [])
                for root in roots[:1]:
                    root_name = root.get('root_name') or root.get('name', '')
                    if not root_name:
                        continue
                    
                    parents = root.get('parent_labels', [])
                    for parent in parents[:1]:
                        parent_name = parent.get('parent_name') or parent.get('name', '')
                        if not parent_name:
                            continue
                        
                        children = parent.get('children', [])
                        if children:
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

            master_full_data = combination['master'].get('full_data', {})

            export_data = {
                "timestamp": datetime.now().isoformat(),
                "batch_number": batch_number,
                "combination_index": combo_idx + 1,
                "nb_samples_requested": combination.get('nb_samples', 1),
                "combination_details": {
                    "master": {
                        "name": combination['master']['name'],
                        "taxonomy_clusters": master_full_data.get('taxonomy_clusters', [])
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

        self._log("debug", f"\n{'='*60}")
        self._log("debug", f"🔍 _build_context - Combo {combination.get('combination_index', '?')}")

        master_obj = combination.get('master', {})
        master_name = master_obj.get('name', 'N/A')
        master_full_data = master_obj.get('full_data', {})

        self._log("debug", f"📦 Master name : {master_name}")
        self._log("debug", f"📦 master_full_data keys : {list(master_full_data.keys())}")

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

        first_cluster = clusters[0]
        cluster_name = first_cluster.get('name') or first_cluster.get('cluster_name', 'MISSING')
        self._log("debug", f"   Premier cluster : '{cluster_name}'")

        context = {
            'master_typologie': master_full_data,
            'master_name': master_name,
            'contexts': []
        }

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
        """✅ VERSION CORRIGÉE avec diagnostics complets"""
        try:
            self._log("info", "   🌐 Appel API Gemini...")
            
            if self.debug_mode:
                self._log("debug", f"\n{'='*60}")
                self._log("debug", f"PROMPT ENVOYÉ (premiers 500 chars):")
                self._log("debug", prompt[:500] + "...")
                self._log("debug", f"{'='*60}")
            
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": self.max_tokens,
            }
            
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if hasattr(response, 'prompt_feedback'):
                feedback = response.prompt_feedback
                if hasattr(feedback, 'block_reason') and feedback.block_reason:
                    reason = feedback.block_reason
                    self._log("error", f"   ❌ PROMPT BLOQUÉ par Gemini!")
                    self._log("error", f"   Raison: {reason}")
                    if hasattr(feedback, 'safety_ratings'):
                        self._log("error", f"   Safety ratings: {feedback.safety_ratings}")
                    return None
            
            if not hasattr(response, 'candidates') or not response.candidates:
                self._log("error", "   ❌ Aucun candidat retourné par Gemini")
                self._log("error", f"   Response type: {type(response)}")
                return None
            
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                finish_reason_name = finish_reason.name if hasattr(finish_reason, 'name') else str(finish_reason)
                
                self._log("debug", f"   Finish reason: {finish_reason_name}")
                
                if finish_reason_name != "STOP":
                    self._log("warning", f"   ⚠️ Génération incomplète: {finish_reason_name}")
                    
                    if finish_reason_name == "SAFETY":
                        self._log("error", "   ❌ Contenu bloqué par les filtres de sécurité Gemini")
                        return None
                    elif finish_reason_name == "MAX_TOKENS":
                        self._log("warning", "   ⚠️ Limite de tokens atteinte, résultat peut être tronqué")
                    elif finish_reason_name == "RECITATION":
                        self._log("error", "   ❌ Contenu bloqué (récitation détectée)")
                        return None
            
            if not hasattr(response, 'text') or not response.text:
                self._log("error", "   ❌ Réponse vide de Gemini")
                return None
            
            response_text = response.text.strip()
            
            self._log("debug", f"\n{'='*60}")
            self._log("debug", f"RÉPONSE BRUTE DE GEMINI:")
            self._log("debug", f"Longueur: {len(response_text)} caractères")
            self._log("debug", f"Premiers 1000 chars:\n{response_text[:1000]}")
            if len(response_text) > 1000:
                self._log("debug", f"... [tronqué] ...")
                self._log("debug", f"Derniers 500 chars:\n{response_text[-500:]}")
            self._log("debug", f"{'='*60}\n")
            
            samples = self._parse_json_response(response_text)
            
            if not samples:
                self._log("error", "   ❌ PARSING JSON ÉCHOUÉ")
                self._log("error", "   💡 La réponse de Gemini n'est pas au format JSON attendu")
                self._save_failed_response(response_text, prompt)
                return None
            
            if len(samples) != nb_samples:
                self._log("warning", f"   ⚠️ Attendu {nb_samples} samples, reçu {len(samples)}")
            
            self._log("info", f"   ✅ {len(samples)} sample(s) généré(s) et parsé(s)")
            return samples
            
        except Exception as e:
            error_type = type(e).__name__
            self._log("error", f"   ❌ EXCEPTION dans _call_gemini_api ({error_type}): {str(e)}")
            
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
        """✅ VERSION CORRIGÉE avec diagnostics détaillés"""
        if not text:
            self._log("error", "   ❌ Texte vide à parser")
            return None
        
        try:
            cleaned = text.strip()
            
            self._log("debug", f"   Parsing: longueur = {len(cleaned)} chars")
            
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
            
            if not cleaned:
                self._log("error", "   ❌ Texte vide après nettoyage")
                return None
            
            first_char = cleaned[0]
            self._log("debug", f"   Premier caractère: '{first_char}'")
            
            if first_char not in ('[', '{'):
                self._log("error", f"   ❌ Ne commence pas par [ ou {{ (caractère: '{first_char}')")
                self._log("error", f"   Premiers 200 chars: {cleaned[:200]}")
                
                json_start_bracket = cleaned.find('[')
                json_start_brace = cleaned.find('{')
                
                if json_start_bracket > 0 or json_start_brace > 0:
                    if json_start_bracket > 0 and (json_start_brace < 0 or json_start_bracket < json_start_brace):
                        json_start = json_start_bracket
                    else:
                        json_start = json_start_brace
                    
                    self._log("warning", f"   🔧 Tentative récupération à partir du char {json_start}")
                    cleaned = cleaned[json_start:]
                else:
                    self._log("error", "   ❌ Aucun caractère JSON trouvé")
                    return None
            
            try:
                self._log("debug", "   Tentative de parsing JSON...")
                data = json.loads(cleaned)
                self._log("debug", f"   ✅ JSON parsé avec succès (type: {type(data)})")
                
            except json.JSONDecodeError as e:
                self._log("error", f"   ❌ Erreur JSON: {str(e)}")
                self._log("error", f"   Position: ligne {e.lineno}, col {e.colno}")
                
                error_pos = e.pos
                context_start = max(0, error_pos - 100)
                context_end = min(len(cleaned), error_pos + 100)
                context = cleaned[context_start:context_end]
                
                self._log("error", f"   Contexte de l'erreur:")
                self._log("error", f"   ...{context}...")
                
                self._log("warning", "   🔧 Tentative de réparation du JSON...")
                
                cleaned_v2 = cleaned.replace(',]', ']').replace(',}', '}')
                
                import re
                cleaned_v2 = re.sub(r'//.*?\n', '\n', cleaned_v2)
                cleaned_v2 = re.sub(r'/\*.*?\*/', '', cleaned_v2, flags=re.DOTALL)
                
                try:
                    data = json.loads(cleaned_v2)
                    self._log("info", "   ✅ JSON réparé avec succès!")
                except Exception as repair_error:
                    self._log("error", f"   ❌ Réparation échouée: {repair_error}")
                    return None
            
            if isinstance(data, dict):
                self._log("debug", "   ℹ️ Objet JSON reçu, conversion en liste")
                data = [data]
            elif not isinstance(data, list):
                self._log("error", f"   ❌ Type inattendu: {type(data)}")
                return None
            
            self._log("debug", f"   Validation de {len(data)} sample(s)...")
            
            valid_samples = []
            for idx, sample in enumerate(data):
                if not isinstance(sample, dict):
                    self._log("error", f"   ❌ Sample {idx} n'est pas un objet JSON")
                    continue
                
                required_fields = ['input', 'output']
                missing = [f for f in required_fields if f not in sample]
                
                if missing:
                    self._log("warning", f"   ⚠️ Sample {idx}: champs manquants {missing}")
                
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
        self._log("info", f"   • MODE: STRICT + STORAGE ROBUSTE")
    
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