#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OSS Dataset Worker - Version alignée sur GeminiDatasetWorker
✅ Génère le MÊME prompt que Gemini
✅ Utilise l'endpoint http://localhost:8084/v1/generate-dataset
✅ Données d'entrée et sortie identiques
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import logger


class OSSDatasetWorker(QThread):
    """Worker thread pour générer des datasets via l'endpoint OSS local"""
    
    # Signaux (identiques à GeminiDatasetWorker)
    progress_updated = pyqtSignal(int, int, str)
    combination_completed = pyqtSignal(int, dict)
    batch_completed = pyqtSignal(int, list)
    generation_completed = pyqtSignal(list, dict)
    generation_failed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    API_BASE_URL = "http://localhost:8084"
    
    def __init__(self, generation_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.generation_config = generation_config
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        
        # Configuration (IDENTIQUE GEMINI)
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
        
        self.all_results = []
        self.global_sample_counter = 0
        self.debug_mode = generation_config.get('debug_mode', True)
        
        logger.info("🤖 OSSDatasetWorker initialisé (prompt identique Gemini)")
    
    def run(self):
        """Point d'entrée du thread"""
        self.is_running = True
        self.should_stop = False
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 GÉNÉRATION DATASET (ENDPOINT OSS LOCAL)")
        logger.info("=" * 80)
        
        try:
            if not self._check_service_health():
                self.generation_failed.emit(
                    "❌ Service OSS non accessible sur localhost:8084\n"
                    "Démarrez-le avec: ./dataset_generator_service.sh start"
                )
                return
            
            self._log_generation_summary()
            self._validate_taxonomies()
            
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
                self._finalize_generation()
            
        except Exception as e:
            self._log("error", f"❌ Erreur critique: {str(e)}")
            import traceback
            self._log("debug", traceback.format_exc())
            self.generation_failed.emit(str(e))
        finally:
            self.is_running = False
    
    def _check_service_health(self) -> bool:
        """Vérifie que le service OSS est accessible"""
        try:
            response = requests.get(f"{self.API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self._log("info", "✅ Service OSS accessible")
                if data.get('vllm_available'):
                    self._log("info", "✅ vLLM disponible")
                else:
                    self._log("warning", "⚠️ vLLM non disponible")
                return True
            return False
        except Exception as e:
            self._log("error", f"❌ Connexion refusée: {str(e)}")
            return False
    
    def _validate_taxonomies(self):
        """Valide les structures taxonomiques (IDENTIQUE GEMINI)"""
        self._log("info", "🔍 Validation des structures taxonomiques...")
        for combo_idx, combo in enumerate(self.combinations):
            master_data = combo['master']['full_data']
            if not master_data.get('taxonomy_clusters'):
                raise ValueError(f"❌ Combinaison {combo_idx+1}: master sans 'taxonomy_clusters'")
            sample_cluster = master_data['taxonomy_clusters'][0]
            if not (sample_cluster.get('name') or sample_cluster.get('cluster_name')):
                raise ValueError(f"❌ Combinaison {combo_idx+1}: Noms manquants")
            self._log("debug", f"   Combinaison {combo_idx+1} OK: '{combo['master']['name']}'")
    
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
    
    def _generate_combination(self, combination: Dict[str, Any], combo_idx: int, batch_number: int) -> List[Dict[str, Any]]:
        """Génère les échantillons pour UNE combinaison"""
        samples = []
        nb_samples = combination.get('nb_samples', 1)
        self._log("info", f"   🎯 Génération de {nb_samples} sample(s)...")
        
        # Construire contexte et prompt (IDENTIQUE GEMINI)
        context = self._build_context(combination)
        final_prompt = self._build_flexible_prompt(context, nb_samples)
        self._log_prompt_to_file(final_prompt, combination, combo_idx, batch_number)
        
        try:
            # ⚡ APPEL À L'ENDPOINT OSS
            generated_data = self._call_oss_api(final_prompt, nb_samples)
            
            if generated_data:
                for idx, sample in enumerate(generated_data):
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
                            'local_sample_index': idx + 1,
                            'generated_at': datetime.now().isoformat(),
                            'model': 'OSS Local Model',
                            'master': combination['master']['name'],
                            'contexts': [ctx['display'] for ctx in combination['contexts']],
                            'purpose': 'conversational_ai_training',
                            'output_format': self.output_format
                        }
                    }
                    samples.append(enriched_sample)
                
                self._log("info", f"   ✅ {len(samples)} sample(s) générés")
        except Exception as e:
            self._log("error", f"   ❌ Erreur: {str(e)}")
        
        # Mise à jour progression
        current = (combo_idx * nb_samples) + len(samples)
        self.progress_updated.emit(current, self.total_samples_per_batch, 
                                   f"Combinaison {combo_idx + 1}/{len(self.combinations)}")
        return samples
    
    def _call_oss_api(self, prompt: str, nb_samples: int) -> Optional[List[Dict[str, Any]]]:
        """Appelle l'endpoint OSS pour générer les samples"""
        try:
            self._log("info", "   🌐 Appel API OSS...")
            
            request_data = {
                "prompt": prompt,
                "nb_samples": nb_samples,
                "temperature": 0.7,
                "max_tokens": 8192
            }
            
            if self.debug_mode:
                self._log("debug", f"  URL: {self.API_BASE_URL}/v1/generate-dataset")
                self._log("debug", f"  nb_samples: {nb_samples}")
            
            response = requests.post(
                f"{self.API_BASE_URL}/v1/generate-dataset",
                json=request_data,
                timeout=300
            )
            
            if response.status_code != 200:
                self._log("error", f"   ❌ HTTP {response.status_code}: {response.text}")
                return None
            
            result = response.json()
            if result.get('status') == 'error':
                self._log("error", f"   ❌ Erreur: {result.get('error')}")
                return None
            
            samples = result.get('samples', [])
            if not samples:
                return None
            
            # Valider les samples
            valid = [s for s in samples if isinstance(s, dict) and 'input' in s and 'output' in s]
            self._log("info", f"   ✅ {len(valid)} sample(s) valides")
            return valid
            
        except Exception as e:
            self._log("error", f"   ❌ Exception: {str(e)}")
            return None
    
    # MÉTHODES UTILITAIRES (importées depuis GeminiDatasetWorker)
    from ui.widgets.workers.gemini_dataset_worker import GeminiDatasetWorker
    _build_context = GeminiDatasetWorker._build_context
    _build_flexible_prompt = GeminiDatasetWorker._build_flexible_prompt
    _format_typologie_detailed = GeminiDatasetWorker._format_typologie_detailed
    _format_children_recursive = GeminiDatasetWorker._format_children_recursive
    _count_children_recursive = GeminiDatasetWorker._count_children_recursive
    _extract_structure_examples = GeminiDatasetWorker._extract_structure_examples
    _build_combinaisons_from_sample = GeminiDatasetWorker._build_combinaisons_from_sample
    
    def _log_prompt_to_file(self, prompt: str, combination: Dict[str, Any], combo_idx: int, batch_number: int):
        """Exporte le prompt dans un fichier"""
        try:
            from pathlib import Path
            logs_dir = Path("generation_logs") / "prompts"
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = logs_dir / f"prompt_oss_batch{batch_number}_combo{combo_idx + 1}_{timestamp}.json"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "batch_number": batch_number,
                    "combination_index": combo_idx + 1,
                    "nb_samples_requested": combination.get('nb_samples', 1),
                    "prompt_sent": prompt,
                    "model": "OSS Local",
                    "endpoint": f"{self.API_BASE_URL}/v1/generate-dataset"
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log("error", f"   ❌ Erreur log: {str(e)}")
    
    def _log_generation_summary(self):
        """Affiche le récapitulatif"""
        self._log("info", "\n📊 RÉCAPITULATIF")
        self._log("info", f"   • Projet: {self.project_name}")
        self._log("info", f"   • Batch: {self.batch_name} (#{self.batch_number})")
        self._log("info", f"   • Combinaisons: {len(self.combinations)}")
        self._log("info", f"   • Total samples: {self.total_samples_all_batches}")
    
    def _finalize_generation(self):
        """Finalise la génération"""
        self._log("info", f"\n{'=' * 80}")
        self._log("info", f"🎉 GÉNÉRATION TERMINÉE")
        self._log("info", f"   • Total: {len(self.all_results)} samples")
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
            'model_used': 'OSS Local Model',
            'purpose': 'Conversational AI Training Dataset'
        }
        self.generation_completed.emit(self.all_results, final_metadata)
    
    def _log(self, level: str, message: str):
        """Log vers interface et logger"""
        self.log_message.emit(level, message)
        getattr(logger, level if level in ['error', 'warning', 'debug'] else 'info')(message)
    
    def pause(self):
        self._log("warning", "⚠️ Pause non supportée en mode endpoint")
    
    def resume(self):
        self._log("warning", "⚠️ Resume non supporté en mode endpoint")
    
    def stop(self):
        self._log("warning", "⚠️ Arrêt de la surveillance")
        self.should_stop = True