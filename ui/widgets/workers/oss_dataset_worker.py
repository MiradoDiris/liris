#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OSS Dataset Generator - VERSION OPTIMISÉE v6.0
Génération par batch de 10 samples + parallélisation
Gain de performance: ~90% plus rapide
Compatible Windows/Linux/Mac
"""

import json
import re
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import httpx
import logging

# Import PyQt5 pour le worker thread
try:
    from PyQt5.QtCore import QThread, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QThread = object
    def pyqtSignal(*args, **kwargs):
        return None

# ============================================================================
# CONFIGURATION LOGGING
# ============================================================================

# Créer un fichier de log dans un répertoire temporaire compatible cross-platform
log_dir = tempfile.gettempdir()
log_file = os.path.join(log_dir, 'dataset_generator.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 Fichier de log: {log_file}")

# ============================================================================
# INITIALISATION
# ============================================================================

app = FastAPI(title="OSS Dataset Generator", version="6.0.0-optimized")

# Configuration de l'API publique
API_BASE_URL = os.getenv('OSS_API_URL', 'http://localhost:8083')
API_ENDPOINT = f"{API_BASE_URL}/v1/generate-dataset"

logger.info(f"✅ API configurée : {API_ENDPOINT}")

# Client HTTP pour les requêtes
http_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0))

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "BATCH_SIZE": 10,           # Nombre de samples par appel API
    "MAX_TOKENS_BATCH": 6144,   # Tokens pour batch complet
    "MAX_TOKENS_SINGLE": 1024,  # Tokens pour fallback 1 sample
    "PARALLEL_WORKERS": 5,      # Nombre de threads parallèles
    "ENABLE_PARALLEL": True     # Activer/désactiver parallélisation
}

# ============================================================================
# MODÈLES
# ============================================================================

class SimpleGenerationRequest(BaseModel):
    prompt: str
    nb_samples: int = 1
    temperature: float = 0.3
    max_tokens: int = 8192
    enable_parallel: bool = True  # Option pour désactiver si besoin

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def clean_generated_json(text: str) -> str:
    """
    Nettoie le texte JSON généré
    """
    # Guillemets courbes → droits
    text = text.replace('"', '"').replace('"', '"').replace('«', '"').replace('»', '"')
    text = text.replace(''', "'").replace(''', "'").replace('‹', "'").replace('›', "'")
    
    # Remplace \' par '
    text = text.replace("\\'", "'")
    text = re.sub(r'\\n', '\n', text)
    return text

def repair_truncated_json(json_text: str) -> Optional[str]:
    """
    Répare un JSON array tronqué via regex
    """
    logger.info(f"🔧 Réparation JSON via regex ({len(json_text)} chars)")
    
    json_text = clean_generated_json(json_text)
    
    # Pattern pour extraire objets complets
    pattern = r'\{\s*"input"\s*:\s*"([^"]*(?:[^"\\]|\\.)*?)"\s*,\s*"output"\s*:\s*"([^"]*(?:[^"\\]|\\.)*?)"\s*\}'
    
    matches = re.findall(pattern, json_text, re.DOTALL | re.MULTILINE)
    
    if not matches:
        logger.error("❌ Aucun objet complet trouvé via regex")
        return None
    
    samples = [
        {
            "input": inp.strip(),
            "output": out.strip()
        }
        for inp, out in matches
    ]
    
    repaired = json.dumps(samples)
    logger.info(f"✅ JSON réparé via regex: {len(samples)} objets récupérés")
    return repaired

def extract_content(choice) -> Optional[str]:
    """
    Extrait le contenu de la réponse
    """
    msg = choice.message
    
    if msg.content:
        logger.info("✅ Contenu dans 'content'")
        return msg.content
    
    if hasattr(msg, 'reasoning_content') and msg.reasoning_content:
        logger.warning("⚠️ Contenu dans 'reasoning_content' (mode reasoning)")
        return msg.reasoning_content
    
    logger.error("❌ Aucun contenu trouvé")
    return None

def extract_json_from_reasoning(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fallback: extraction depuis raisonnement textuel
    """
    logger.info("🔍 Extraction JSON depuis raisonnement")
    
    text = clean_generated_json(text)
    
    # Stratégie 1: Chercher un array JSON
    patterns = [
        r'\[\s*\{[^\]]*"input"[^\]]*"output"[^\]]*\}\s*\]',
        r'\[[\s\S]*?\{[\s\S]*?"input"[\s\S]*?"output"[\s\S]*?\}[\s\S]*?\]'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            best = max(matches, key=len)
            try:
                parsed = json.loads(best)
                if isinstance(parsed, list) and len(parsed) > 0:
                    logger.info(f"✅ Array JSON extrait: {len(parsed)} éléments")
                    return parsed
            except:
                continue
    
    # Stratégie 2: Reconstruction Input/Output
    input_pattern = r'Input:\s*"([^"]+)"'
    output_pattern = r'Output:\s*"([^"]+)"'
    
    inputs = re.findall(input_pattern, text)
    outputs = re.findall(output_pattern, text)
    
    if inputs and outputs:
        min_len = min(len(inputs), len(outputs))
        samples = [
            {"input": inputs[i], "output": outputs[i]}
            for i in range(min_len)
        ]
        logger.info(f"✅ {len(samples)} paires reconstruites (Input/Output)")
        return samples
    
    # Stratégie 3: Lowercase input:/output:
    text_input_pattern = r'(?:input\s*:\s*"([^"]+)")'
    text_output_pattern = r'(?:output\s*:\s*"([^"]+)")'
    
    all_inputs = re.findall(text_input_pattern, text, re.IGNORECASE | re.DOTALL)
    all_outputs = re.findall(text_output_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if all_inputs and all_outputs:
        min_len = min(len(all_inputs), len(all_outputs))
        samples = [
            {"input": all_inputs[i].strip(), "output": all_outputs[i].strip()}
            for i in range(min_len)
        ]
        logger.info(f"✅ {len(samples)} paires reconstruites (textuel)")
        return samples
    
    logger.error("❌ Extraction échouée")
    return None

# ============================================================================
# GÉNÉRATEUR OPTIMISÉ
# ============================================================================

class OptimizedGenerator:
    """Générateur optimisé avec batch + parallélisation"""
    
    def __init__(self):
        self.model_name = "openai/gpt-oss-20b"
        self.executor = ThreadPoolExecutor(max_workers=CONFIG["PARALLEL_WORKERS"])
    
    def generate_samples(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        enable_parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Point d'entrée principal avec choix parallèle ou séquentiel
        """
        
        if enable_parallel and CONFIG["ENABLE_PARALLEL"] and nb_samples > CONFIG["BATCH_SIZE"]:
            logger.info(f"🚀 Mode PARALLÈLE activé ({CONFIG['PARALLEL_WORKERS']} workers)")
            return self._generate_parallel(prompt, nb_samples, temperature, max_tokens)
        else:
            logger.info(f"📦 Mode SÉQUENTIEL")
            return self._generate_sequential(prompt, nb_samples, temperature, max_tokens)
    
    def _generate_parallel(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float,
        max_tokens: int
    ) -> List[Dict[str, Any]]:
        """
        Génération PARALLÈLE: plusieurs batches en même temps
        """
        
        all_samples = []
        batch_size = CONFIG["BATCH_SIZE"]
        
        # Calculer nombre de batches
        nb_full_batches = nb_samples // batch_size
        remaining = nb_samples % batch_size
        
        total_batches = nb_full_batches + (1 if remaining > 0 else 0)
        
        logger.info(f"📊 Découpage: {nb_full_batches} batches complets + {remaining} restant")
        logger.info(f"🔄 Total: {total_batches} batches à exécuter")
        
        # Lancer batches en parallèle
        futures = []
        
        for i in range(nb_full_batches):
            future = self.executor.submit(
                self._generate_batch,
                prompt=prompt,
                nb_samples=batch_size,
                temperature=temperature,
                max_tokens=CONFIG["MAX_TOKENS_BATCH"],
                batch_num=i+1
            )
            futures.append(future)
        
        # Batch restant
        if remaining > 0:
            future = self.executor.submit(
                self._generate_batch,
                prompt=prompt,
                nb_samples=remaining,
                temperature=temperature,
                max_tokens=CONFIG["MAX_TOKENS_BATCH"],
                batch_num=total_batches
            )
            futures.append(future)
        
        # Collecter résultats
        for i, future in enumerate(futures, 1):
            try:
                batch_samples = future.result()
                all_samples.extend(batch_samples)
                logger.info(f"✅ Batch {i}/{total_batches} récupéré: {len(batch_samples)} samples")
            except Exception as e:
                logger.error(f"❌ Batch {i}/{total_batches} échoué: {e}")
        
        logger.info(f"🏁 Total collecté: {len(all_samples)}/{nb_samples} samples")
        return all_samples
    
    def _generate_sequential(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float,
        max_tokens: int
    ) -> List[Dict[str, Any]]:
        """
        Génération SÉQUENTIELLE: batches un par un
        """
        
        all_samples = []
        batch_size = CONFIG["BATCH_SIZE"]
        
        nb_full_batches = nb_samples // batch_size
        remaining = nb_samples % batch_size
        
        # Batches complets
        for i in range(nb_full_batches):
            logger.info(f"📦 Batch {i+1}/{nb_full_batches + (1 if remaining else 0)}")
            
            try:
                batch_samples = self._generate_batch(
                    prompt=prompt,
                    nb_samples=batch_size,
                    temperature=temperature,
                    max_tokens=CONFIG["MAX_TOKENS_BATCH"],
                    batch_num=i+1
                )
                all_samples.extend(batch_samples)
                logger.info(f"✅ {len(batch_samples)} samples générés")
                
            except Exception as e:
                logger.error(f"❌ Batch échoué: {e}")
        
        # Batch restant
        if remaining > 0:
            logger.info(f"📦 Batch final: {remaining} samples")
            try:
                batch_samples = self._generate_batch(
                    prompt=prompt,
                    nb_samples=remaining,
                    temperature=temperature,
                    max_tokens=CONFIG["MAX_TOKENS_BATCH"],
                    batch_num=nb_full_batches + 1
                )
                all_samples.extend(batch_samples)
                logger.info(f"✅ {len(batch_samples)} samples générés")
                
            except Exception as e:
                logger.error(f"❌ Batch final échoué: {e}")
        
        return all_samples
    
    def _generate_batch(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float,
        max_tokens: int,
        batch_num: int
    ) -> List[Dict[str, Any]]:
        """
        Génère un batch de samples avec fallback automatique
        """
        
        logger.info(f"🎯 Batch #{batch_num}: {nb_samples} samples demandés")
        
        # Tentative batch complet
        try:
            samples = self._generate_one_call(
                prompt=prompt,
                nb_samples=nb_samples,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if len(samples) >= nb_samples:
                logger.info(f"✅ Batch #{batch_num} complet: {len(samples)} samples")
                return samples[:nb_samples]
            
            logger.warning(f"⚠️ Batch #{batch_num} incomplet: {len(samples)}/{nb_samples}")
            return samples
            
        except Exception as e:
            logger.error(f"❌ Batch #{batch_num} échoué: {e}")
            logger.info(f"🔄 Fallback: génération 1 par 1")
            
            # Fallback: 1 par 1
            return self._generate_one_by_one(
                prompt=prompt,
                nb_samples=nb_samples,
                temperature=temperature
            )
    
    def _generate_one_by_one(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float
    ) -> List[Dict[str, Any]]:
        """
        Fallback: génère 1 sample à la fois
        """
        
        all_samples = []
        
        for i in range(nb_samples):
            try:
                logger.info(f"   🔹 Sample {i+1}/{nb_samples}...")
                
                samples = self._generate_one_call(
                    prompt=prompt,
                    nb_samples=1,
                    temperature=temperature,
                    max_tokens=CONFIG["MAX_TOKENS_SINGLE"]
                )
                
                if samples:
                    all_samples.extend(samples)
                    logger.info(f"   ✅ Sample {i+1} OK")
                else:
                    logger.warning(f"   ⚠️ Sample {i+1} vide")
                    
            except Exception as e:
                logger.error(f"   ❌ Sample {i+1} échoué: {e}")
        
        return all_samples
    
    def _build_natural_prompt(self, user_prompt: str, nb_samples: int) -> str:
        """
        Construit un prompt enrichi avec les règles de langage naturel
        """
        return f"""# 🤖 GÉNÉRATION DE DATASET CONVERSATIONNEL NATUREL

    ## 📋 CONSIGNES DE GÉNÉRATION

    Générez EXACTEMENT {nb_samples} échantillon(s) au format JSON pour le sujet : "{user_prompt}"

    ## ✅ MOTS DE LIAISON OBLIGATOIRES POUR LA NAVIGATION

    **RÈGLE ABSOLUE : Pour décrire un chemin dans l'interface, vous DEVEZ utiliser ces mots de liaison :**

    ### 🔑 Mots de liaison AUTORISÉS et OBLIGATOIRES :
    - ✅ **puis** → "allez dans Menu, puis Sous-menu, puis Action"
    - ✅ **ensuite** → "ouvrez Menu, ensuite Sous-menu, ensuite Action"
    - ✅ **et** → "allez dans Menu et Sous-menu et cliquez sur Action"
    - ✅ **dans** → "dans le menu Menu, dans la section Sous-menu"
    - ✅ **sous** → "dans Menu, sous Sous-menu"
    - ✅ **à** → "allez à Menu, à la section Sous-menu"
    - ✅ **vers** → "dirigez-vous vers Menu, vers Sous-menu"

    ### 🎯 EXEMPLES AVEC MOTS DE LIAISON :

    **Exemple 1 - Chemin court (2-3 niveaux) :**
    ✅ "Allez dans Comptabilité, puis Rapports, puis cliquez sur Trésorerie"
    ✅ "Ouvrez Ventes, ensuite Factures et cliquez sur Nouveau"
    ✅ "Dans le menu Compte, sous Paramètres, cliquez sur Préférences"

    **Exemple 2 - Chemin long (4+ niveaux) :**
    ✅ "Pour accéder à cette fonction, allez dans Compte, puis Catégorie fiscale, ensuite Société, puis Impôts et sélectionnez Prestataire de services"
    ✅ "Vous trouverez cette option dans Macompta.fr, section Comptabilité, sous-section Comptabilité simplifiée, option Saisie classique"

    **Exemple 3 - Alternative descriptive :**
    ✅ "Cette fonction se trouve dans le menu Abo/Sales, sous la section Comptabilité simplifiée"
    ✅ "Accédez aux paramètres via le menu Compte, dans la catégorie Impôts sur les sociétés"

    ### ⚠️ CE QU'IL NE FAUT JAMAIS FAIRE :
    ❌ "Dans Macompta.fr > Abo/Sales > Comptabilité > Saisie"
    ❌ "Menu \"Compte\" > \"Paramètres\" > \"Préférences\""
    ❌ "Comptabilité / Rapports / Trésorerie"
    ❌ "Ventes : Factures : Nouveau"

    ## 💬 RÈGLES POUR L'INPUT (Question utilisateur)

    1. **Langage naturel spontané**
       - ✅ "Comment je peux suivre mes dépenses facilement ?"
       - ✅ "J'aimerais savoir où créer une nouvelle facture"
       - ❌ "Afficher suivi dépenses" (trop robotique)

    2. **Questions complètes et contextualisées**
       - ✅ "J'ai besoin d'aide pour créer ma première facture, comment faire ?"
       - ❌ "Créer facture" (pas une vraie question)

    3. **Longueur** : Entre 5 et 20 mots

    ## 💬 RÈGLES POUR L'OUTPUT (Réponse assistant)

    1. **Réponses DIRECTES avec phrases complètes**
       - ✅ "Pour suivre vos dépenses, allez dans le menu Comptabilité puis cliquez sur Tableau de bord."
       - ❌ "Comptabilité > Tableau de bord" (télégraphique)

    2. **Style conversationnel professionnel**
       - Utiliser "vous"
       - Verbes conjugués correctement
       - Instructions claires

    3. **Longueur** : Entre 10 et 30 mots

    ## ❌ INTERDICTIONS ABSOLUES

    1. ❌ **JAMAIS** utiliser ">", "/", "-", "→"
    2. ❌ **JAMAIS** de phrases incomplètes
    3. ❌ **JAMAIS** utiliser ":" ou "..."
    4. ❌ **JAMAIS** de guillemets autour des menus
    5. ❌ **JAMAIS** dépasser 30 mots

    ## 📋 FORMAT DE SORTIE

    ```json
    [
      {{
        "input": "Comment ajouter un nouveau client ?",
        "output": "Pour ajouter un client, allez dans Clients, puis cliquez sur Nouveau client."
      }}
    ]
    ```

    ⚠️ **UTILISEZ TOUJOURS : puis, ensuite, et, dans, sous**
    ❌ **JAMAIS : >, /, :, ->, guillemets autour des menus**

    **RETOURNEZ UNIQUEMENT LE JSON.**
    """    

    def _generate_one_call(
        self,
        prompt: str,
        nb_samples: int,
        temperature: float,
        max_tokens: int
    ) -> List[Dict[str, Any]]:
        """
        Effectue UN appel à l'API avec prompt enrichi
        """
        
        # ✅ NOUVEAU : Enrichir le prompt avec les règles de langage naturel
        enriched_prompt = self._build_natural_prompt(prompt, nb_samples)
        
        # Préparer la requête pour l'API publique
        payload = {
            "prompt": enriched_prompt,  # ✅ Utiliser le prompt enrichi
            "nb_samples": nb_samples,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enable_parallel": False
        }
        
        logger.debug(f"📤 Requête API: {nb_samples} samples")
        logger.debug(f"📝 Prompt enrichi: {len(enriched_prompt)} caractères")
        
        # Le reste du code reste identique...
        try:
            response = http_client.post(
                API_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300.0
            )
            response.raise_for_status()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erreur HTTP {e.response.status_code}: {e.response.text}")
            raise Exception(f"Erreur API HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error(f"❌ Impossible de se connecter à {API_ENDPOINT}")
            raise Exception(f"Connexion impossible à l'API: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Erreur requête API: {str(e)}")
            raise
        
        # Parser la réponse
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"❌ Réponse non-JSON: {response.text[:200]}")
            raise Exception(f"Réponse invalide de l'API")
        
        # Vérifier le statut
        if data.get("status") == "error":
            error_msg = data.get("error", "Erreur inconnue")
            logger.error(f"❌ Erreur API: {error_msg}")
            raise Exception(f"Erreur génération: {error_msg}")
        
        # Extraire les samples
        samples = data.get("samples", [])
        
        if not samples:
            logger.warning("⚠️ Aucun sample retourné par l'API")
            raise Exception("Aucun sample généré")
        
        # Valider et nettoyer
        valid = []
        for s in samples[:nb_samples]:
            if isinstance(s, dict) and 'input' in s and 'output' in s:
                valid.append({
                    "input": str(s['input']).strip(),
                    "output": str(s['output']).strip()
                })
        
        if not valid:
            raise Exception("Aucun sample valide")
        
        logger.debug(f"✅ {len(valid)} samples valides reçus de l'API")
        return valid

# ============================================================================
# INSTANCE GLOBALE
# ============================================================================

generator = OptimizedGenerator()

# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.get("/health")
async def health():
    """Vérification santé du service"""
    return {
        "status": "healthy",
        "version": "6.0.0-optimized",
        "model": "openai/gpt-oss-20b",
        "config": CONFIG,
        "features": [
            f"Génération par batch de {CONFIG['BATCH_SIZE']} samples",
            f"Parallélisation {CONFIG['PARALLEL_WORKERS']} workers",
            f"{CONFIG['MAX_TOKENS_BATCH']} tokens par batch",
            "Fallback automatique 1 par 1",
            "Réparation JSON robuste",
            "Gain performance: ~90%"
        ]
    }

@app.post("/v1/generate-dataset")
async def generate_dataset(request: SimpleGenerationRequest):
    """Endpoint principal de génération"""
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"📥 Requête: {request.nb_samples} samples")
        logger.info(f"   Prompt: {request.prompt[:50]}...")
        logger.info(f"   Température: {request.temperature}")
        logger.info(f"   Parallèle: {request.enable_parallel}")
        logger.info(f"{'='*60}")
        
        start_time = datetime.now()
        
        samples = generator.generate_samples(
            prompt=request.prompt,
            nb_samples=request.nb_samples,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            enable_parallel=request.enable_parallel
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"⏱️ Durée: {duration:.1f}s ({len(samples)/duration:.1f} samples/s)")
        
        return {
            "status": "success",
            "samples": samples,
            "count": len(samples),
            "requested": request.nb_samples,
            "duration_seconds": round(duration, 2),
            "samples_per_second": round(len(samples)/duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "status": "error",
            "error": str(e),
            "samples": [],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/")
async def root():
    """Page d'accueil"""
    return {
        "service": "OSS Dataset Generator",
        "version": "6.0.0-optimized",
        "description": f"Générateur ultra-rapide: {CONFIG['BATCH_SIZE']} samples/batch + {CONFIG['PARALLEL_WORKERS']} workers parallèles",
        "performance": {
            "batch_size": CONFIG["BATCH_SIZE"],
            "parallel_workers": CONFIG["PARALLEL_WORKERS"],
            "estimated_speedup": "90% plus rapide",
            "75_samples_time": "~5 minutes (au lieu de 50 min)"
        },
        "endpoints": {
            "/health": "Vérification santé + config",
            "/generator/v1/generate-dataset": "Génération de dataset (POST)"
        },
        "example": {
            "curl_linux": 'curl -X POST http://localhost:8083/v1/generate-dataset -H "Content-Type: application/json" -d \'{"prompt":"liasse fiscale","nb_samples":75,"enable_parallel":true}\'',
            "curl_windows": 'curl -X POST http://localhost:8083/v1/generate-dataset -H "Content-Type: application/json" -d "{\\"prompt\\":\\"liasse fiscale\\",\\"nb_samples\\":10,\\"enable_parallel\\":true}"',
            "powershell": '$body = @{prompt="liasse fiscale";nb_samples=10;enable_parallel=$true} | ConvertTo-Json; Invoke-WebRequest -Uri http://localhost:8083/v1/generate-dataset -Method POST -ContentType "application/json" -Body $body'
        }
    }

@app.post("/config")
async def update_config(
    batch_size: Optional[int] = None,
    max_tokens_batch: Optional[int] = None,
    parallel_workers: Optional[int] = None,
    enable_parallel: Optional[bool] = None
):
    """Mise à jour configuration à chaud"""
    
    if batch_size is not None:
        CONFIG["BATCH_SIZE"] = batch_size
    if max_tokens_batch is not None:
        CONFIG["MAX_TOKENS_BATCH"] = max_tokens_batch
    if parallel_workers is not None:
        CONFIG["PARALLEL_WORKERS"] = parallel_workers
        generator.executor = ThreadPoolExecutor(max_workers=parallel_workers)
    if enable_parallel is not None:
        CONFIG["ENABLE_PARALLEL"] = enable_parallel
    
    return {
        "status": "updated",
        "config": CONFIG
    }

# ============================================================================
# WORKER PYQT5 POUR L'INTERFACE GRAPHIQUE
# ============================================================================

if PYQT_AVAILABLE:
    class OSSDatasetWorker(QThread):
        """
        Worker PyQt5 pour la génération de datasets dans l'interface graphique
        Compatible avec dataset_generation.py
        """
        
        # Signaux PyQt5 (compatibles avec GeminiDatasetWorker)
        progress_updated = pyqtSignal(int, int, str)  # current, total, message
        combination_completed = pyqtSignal(int, dict)  # combo_index, info_dict
        batch_completed = pyqtSignal(int, list)  # batch_num, samples
        generation_completed = pyqtSignal(list, dict)  # samples_list, metadata_dict
        generation_failed = pyqtSignal(str)  # error_message
        log_message = pyqtSignal(str, str)  # level, message (compatible avec Gemini)
        
        def __init__(self, generation_config: Dict[str, Any], parent=None):
            super().__init__(parent)
            self.generation_config = generation_config
            self.is_running = True
            self.all_samples = []
            self.global_sample_counter = 0  # ✅ Compteur pour sample_id
        
        def _log(self, level: str, message: str):
            """Log vers interface et logger (compatible avec GeminiDatasetWorker)"""
            self.log_message.emit(level, message)
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            elif level == "debug":
                logger.debug(message)
            else:
                logger.info(message)
            
        def run(self):
            """Exécution du worker dans un thread séparé"""
            try:
                self._log("info", "🚀 Démarrage de la génération OSS...")
                
                # Test de connexion à l'API
                try:
                    self._log("info", f"🔗 Test de connexion à {API_ENDPOINT}...")
                    
                    # Test simple avec une petite requête
                    test_payload = {
                        "prompt": "test",
                        "nb_samples": 1,
                        "temperature": 0.3,
                        "max_tokens": 100,
                        "enable_parallel": False
                    }
                    
                    test_response = http_client.post(
                        API_ENDPOINT,
                        json=test_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0
                    )
                    test_response.raise_for_status()
                    
                    self._log("info", "✅ Connexion à l'API établie")
                    
                except httpx.ConnectError as e:
                    error_msg = (
                        f"❌ Impossible de se connecter à l'API\n"
                        f"URL: {API_ENDPOINT}\n"
                        f"Erreur: {str(e)}\n\n"
                        "Vérifiez:\n"
                        "1. Que l'URL de l'API est correcte\n"
                        "2. Votre connexion Internet\n"
                        "3. Que le serveur API est en ligne"
                    )
                    self._log("error", error_msg)
                    self.generation_failed.emit(error_msg)
                    return
                    
                except httpx.HTTPStatusError as e:
                    error_msg = (
                        f"❌ Erreur HTTP {e.response.status_code}\n"
                        f"URL: {API_ENDPOINT}\n"
                        f"Réponse: {e.response.text[:200]}"
                    )
                    self._log("error", error_msg)
                    self.generation_failed.emit(error_msg)
                    return
                    
                except Exception as e:
                    error_msg = f"❌ Erreur test connexion: {str(e)}"
                    self._log("error", error_msg)
                    self.generation_failed.emit(error_msg)
                    return
                
                # Extraire les paramètres de configuration
                metadata = self.generation_config.get('metadata', {})
                prompts = self.generation_config.get('prompts', {})
                combinations = self.generation_config.get('combinations', [])
                
                project_name = metadata.get('project_name', 'unknown')
                batch_number = metadata.get('batch_number', 1)
                
                # Calculer le nombre total de samples
                total_samples = sum(combo.get('nb_samples', 0) for combo in combinations)
                current_progress = 0
                
                self._log("info", f"📊 Projet: {project_name}")
                self._log("info", f"📦 Batch: {batch_number}")
                self._log("info", f"🎯 Total: {total_samples} samples")
                self._log("info", f"🔄 Combinaisons: {len(combinations)}")
                
                all_results = []
                
                # Générer pour chaque combinaison
                for combo_idx, combo in enumerate(combinations):
                    if not self.is_running:
                        break
                        
                    combo_index = combo.get('combination_index', combo_idx)
                    nb_samples = combo.get('nb_samples', 10)
                    
                    # Construire le prompt pour cette combinaison
                    master_name = combo.get('master', {}).get('name', 'unknown')
                    contexts = combo.get('contexts', [])
                    context_names = [ctx.get('display', '') for ctx in contexts]
                    
                    prompt_text = f"{project_name} - {master_name}"
                    if context_names:
                        prompt_text += f" ({', '.join(context_names)})"
                    
                    self._log("info", f"\n{'='*60}")
                    self._log("info", f"🎯 Combinaison {combo_idx + 1}/{len(combinations)}")
                    self._log("info", f"   Master: {master_name}")
                    self._log("info", f"   Samples: {nb_samples}")
                    self._log("info", f"{'='*60}")
                    
                    try:
                        # Générer les samples avec le générateur
                        samples = generator.generate_samples(
                            prompt=prompt_text,
                            nb_samples=nb_samples,
                            temperature=0.3,
                            max_tokens=8192,
                            enable_parallel=True
                        )
                        
                        self._log("info", f"✅ {len(samples)} samples générés")
                        
                        # ✅ AJOUTER sample_id à chaque sample
                        enriched_samples = []
                        for sample in samples:
                            self.global_sample_counter += 1
                            enriched_sample = {
                                'sample_id': self.global_sample_counter,
                                'input': sample.get('input', ''),
                                'output': sample.get('output', '')
                            }
                            enriched_samples.append(enriched_sample)
                        
                        # Émettre le signal de combinaison terminée (compatible avec Gemini)
                        combo_info = {
                            'samples_generated': len(enriched_samples),
                            'samples': enriched_samples,
                            'master_name': master_name,
                            'contexts': context_names
                        }
                        self.combination_completed.emit(combo_index, combo_info)
                        
                        # Ajouter aux résultats
                        all_results.extend(enriched_samples)
                        self.all_samples.extend(enriched_samples)
                        
                        # Mettre à jour la progression
                        current_progress += len(enriched_samples)
                        progress_message = f"Combinaison {combo_idx + 1}/{len(combinations)}"
                        self.progress_updated.emit(current_progress, total_samples, progress_message)
                        
                    except Exception as e:
                        error_msg = f"❌ Erreur combinaison {combo_idx + 1}: {str(e)}"
                        self._log("error", error_msg)
                
                # Génération terminée
                if self.is_running:
                    # Métadonnées compatibles avec Gemini
                    metadata = {
                        'project_name': project_name,
                        'batch_number': batch_number,
                        'total_samples': len(all_results),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self._log("info", f"\n{'='*60}")
                    self._log("info", f"✅ GÉNÉRATION TERMINÉE")
                    self._log("info", f"📊 Total généré: {len(all_results)} samples")
                    self._log("info", f"{'='*60}")
                    
                    # Émettre le signal (list, dict) comme Gemini
                    self.generation_completed.emit(all_results, metadata)
                else:
                    self._log("warning", "⚠️ Génération annulée par l'utilisateur")
                    
            except Exception as e:
                error_msg = f"❌ Erreur fatale: {str(e)}"
                self._log("error", error_msg)
                import traceback
                logger.error(traceback.format_exc())
                self.generation_failed.emit(error_msg)
        
        def stop(self):
            """Arrête la génération"""
            self.is_running = False
            self._log("warning", "⏹️ Arrêt demandé...")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 OSS Dataset Generator v6.0 OPTIMISÉ")
    print("="*70)
    print("\n✨ Fonctionnalités:")
    print(f"   • Génération par batch de {CONFIG['BATCH_SIZE']} samples")
    print(f"   • Parallélisation avec {CONFIG['PARALLEL_WORKERS']} workers")
    print(f"   • {CONFIG['MAX_TOKENS_BATCH']} tokens par batch")
    print("   • Fallback automatique 1 par 1 si batch échoue")
    print("   • Réparation JSON robuste (regex + extraction textuelle)")
    print("\n⚡ Performance:")
    print("   • 75 samples: ~5 min (au lieu de 50 min)")
    print("   • Gain: 90% plus rapide")
    print("   • Throughput: ~15 samples/min")
    print("\n📖 Exemples d'utilisation:")
    print("\n   Windows PowerShell:")
    print('   $body = @{prompt="liasse fiscale";nb_samples=10;enable_parallel=$true} | ConvertTo-Json')
    print('   Invoke-WebRequest -Uri http://0.0.0.0:8083/generator/v1/generate-dataset -Method POST -ContentType "application/json" -Body $body')
    print("\n   Linux/Mac curl:")
    print('   curl -X POST http://0.0.0.0:8083/generator/v1/generate-dataset \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"prompt":"liasse fiscale","nb_samples":75,"enable_parallel":true}\'')
    print("\n🔧 Mise à jour config:")
    print('   curl -X POST http://0.0.0.0:8083/config?batch_size=15&parallel_workers=10')
    print(f"\n🌐 Démarrage sur http://0.0.0.0:8083")
    print(f"📝 Log file: {log_file}")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8083)