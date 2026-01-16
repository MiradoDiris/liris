#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Client pour le service OSS Classifier (port 8085)
AJOUT: Génération d'embeddings par OSS 20B
"""

import logging
import requests
import numpy as np
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class OSSClassification:
    """
    Résultat de la classification sémantique OSS 20B
    Compatible avec le schéma Context Weaver existant
    """
    domain: str
    task: str
    decision_type: str
    variables: list[str]
    risk_axis: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self):
        """Convertit en dictionnaire"""
        return {
            "domain": self.domain,
            "task": self.task,
            "decision_type": self.decision_type,
            "variables": self.variables,
            "risk_axis": self.risk_axis,
            "constraints": self.constraints,
            "confidence": self.confidence
        }

class OSSClassifierClient:
    """
    Client pour le service OSS Classifier standalone (port 8085)
    
    NOUVEAU: Génération d'embeddings par OSS 20B pour Vector Store matching
    """
    
    def __init__(self, base_url: str = "http://localhost:8085"):
        self.base_url = base_url
        self.timeout = 60
        logger.info(f"✅ OSS Classifier Client initialisé: {base_url}")
        
        # Vérifier que le service est accessible
        try:
            self._check_health()
        except Exception as e:
            logger.warning(f"⚠️ Service OSS Classifier non accessible: {e}")
            logger.warning("   Le service doit être démarré sur le port 8085")
    
    def classify(
        self,
        user_context: str,
        domain_hint: Optional[str] = None
    ) -> OSSClassification:
        """
        Classifie le contexte utilisateur via l'API
        
        Args:
            user_context: Texte libre décrivant le besoin
            domain_hint: Indice de domaine optionnel
            
        Returns:
            OSSClassification: Classification structurée
        """
        logger.info("🤖 Classification OSS 20B via API...")
        logger.info(f"   Contexte: {user_context[:100]}...")
        
        try:
            # Appel API
            response = requests.post(
                f"{self.base_url}/v1/classify",
                json={
                    "user_context": user_context,
                    "domain_hint": domain_hint
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur API: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return self._get_fallback_classification()
            
            # Parser la réponse
            data = response.json()
            
            if data["status"] != "success":
                logger.error("❌ Classification échouée")
                return self._get_fallback_classification()
            
            # Extraire la classification
            classification_data = data["classification"]
            
            # Convertir en OSSClassification (dataclass)
            classification = OSSClassification(
                domain=classification_data["domain"],
                task=classification_data["task"],
                decision_type=classification_data["decision_type"],
                variables=classification_data["variables"],
                risk_axis=classification_data.get("risk_axis", []),
                constraints=classification_data.get("constraints", []),
                confidence=classification_data.get("confidence", 0.0)
            )
            
            logger.info("✅ Classification terminée")
            logger.info(f"   • Domain: {classification.domain}")
            logger.info(f"   • Task: {classification.task}")
            logger.info(f"   • Decision Type: {classification.decision_type}")
            logger.info(f"   • Variables: {', '.join(classification.variables[:3])}...")
            logger.info(f"   • Confidence: {classification.confidence:.2%}")
            
            return classification
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout lors de l'appel API")
            return self._get_fallback_classification()
            
        except requests.exceptions.ConnectionError:
            logger.error("❌ Impossible de se connecter au service OSS Classifier")
            logger.error("   Vérifiez que le service tourne sur le port 8085")
            return self._get_fallback_classification()
            
        except Exception as e:
            logger.error(f"❌ Erreur classification: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._get_fallback_classification()
    
    def generate_embeddings(self, text: str) -> np.ndarray:
        """
        NOUVEAU: Génère les embeddings du texte via OSS 20B
        
        Args:
            text: Texte à encoder
            
        Returns:
            np.ndarray: Vecteur d'embeddings (dimension dépend du modèle)
        """
        logger.info("🧮 Génération embeddings OSS 20B...")
        
        try:
            response = requests.post(
                f"{self.base_url}/v1/embeddings",
                json={"text": text},
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur API embeddings: {response.status_code}")
                return self._get_fallback_embeddings()
            
            data = response.json()
            
            if data["status"] != "success":
                logger.error("❌ Génération embeddings échouée")
                return self._get_fallback_embeddings()
            
            # Extraire le vecteur
            embeddings = np.array(data["embeddings"])
            
            logger.info(f"✅ Embeddings générés (dim={len(embeddings)})")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Erreur génération embeddings: {e}")
            return self._get_fallback_embeddings()
    
    def _check_health(self):
        """Vérifie que le service est accessible"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Service OSS Classifier opérationnel")
                logger.info(f"   Modèle: {data.get('model', 'unknown')}")
            else:
                raise Exception(f"Health check failed: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Service non accessible: {e}")
    
    def _get_fallback_classification(self) -> OSSClassification:
        """Classification par défaut en cas d'erreur"""
        logger.warning("⚠️ Utilisation de la classification de secours")
        
        return OSSClassification(
            domain="unknown",
            task="unknown",
            decision_type="decision_tree",
            variables=["feature_1", "feature_2"],
            risk_axis=["risk_factor_1"],
            constraints=[],
            confidence=0.0
        )
    
    def _get_fallback_embeddings(self) -> np.ndarray:
        """Embeddings par défaut en cas d'erreur"""
        logger.warning("⚠️ Utilisation embeddings de secours (vecteur aléatoire)")
        # Retourner un vecteur aléatoire normalisé
        # Dimension standard: 768 (mpnet-base)
        vector = np.random.randn(768)
        return vector / np.linalg.norm(vector)
    
    def validate_classification(self, classification: OSSClassification) -> dict:
        """
        Valide une classification via l'API
        
        Args:
            classification: Classification à valider
            
        Returns:
            dict: Résultat de la validation
        """
        try:
            response = requests.post(
                f"{self.base_url}/v1/validate",
                json=classification.to_dict(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Erreur validation: {response.status_code}")
                return {"status": "error", "message": response.text}
                
        except Exception as e:
            logger.error(f"❌ Erreur validation: {e}")
            return {"status": "error", "message": str(e)}
    
    def close(self):
        """Fermeture propre (compatibilité avec l'ancien code)"""
        logger.info("✅ OSS Classifier Client fermé")

# Alias pour compatibilité avec l'ancien code
OSSClassifier = OSSClassifierClient

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Créer le client
    classifier = OSSClassifierClient()
    
    # Test 1: Classification + Embeddings
    print("\n" + "="*70)
    print("Test 1: Classification + Embeddings")
    print("="*70)
    
    context = "Je veux créer un arbre de décision pour détecter les fraudes bancaires"
    
    # Classification
    classification = classifier.classify(context)
    print(f"\nClassification:")
    print(f"  Domain: {classification.domain}")
    print(f"  Variables: {classification.variables}")
    
    # Embeddings
    embeddings = classifier.generate_embeddings(context)
    print(f"\nEmbeddings:")
    print(f"  Dimension: {len(embeddings)}")
    print(f"  Norme: {np.linalg.norm(embeddings):.3f}")
    print(f"  Extrait: [{embeddings[0]:.3f}, {embeddings[1]:.3f}, ...]")
    
    classifier.close()