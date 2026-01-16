# ==================== services/normalizer.py ====================
"""
Normalisation taxonomique des variables
Mappe les variables user vers la taxonomie standard
"""

import logging
from typing import Dict, List
import difflib

from context_weaver.models.schemas import NormalizedVariables, OSSClassification


logger = logging.getLogger(__name__)

class Normalizer:
    """
    Normalisation taxonomique
    
    Mappe les variables identifiées par OSS vers la taxonomie
    standard de l'entreprise pour garantir la cohérence
    """
    
    def __init__(self):
        logger.info("✅ Normalizer initialisé")
    
    def normalize(self, classification: OSSClassification) -> NormalizedVariables:
        """
        Normalise les variables selon la taxonomie
        
        Args:
            classification: Classification OSS avec variables brutes
            
        Returns:
            NormalizedVariables: Variables mappées à la taxonomie
        """
        logger.info("🔄 Normalisation taxonomique...")
        logger.info(f"   Variables brutes: {classification.variables}")
        
        # Récupérer la taxonomie pour le domaine
        domain_taxonomy = self.taxonomy.get_taxonomy_for_domain(classification.domain)
        
        if not domain_taxonomy:
            logger.warning(f"⚠️ Taxonomie non trouvée pour domain: {classification.domain}")
            # Retourner les variables telles quelles
            return NormalizedVariables(
                variables={v: v for v in classification.variables},
                domain_taxonomy=[]
            )
        
        # Mapper chaque variable
        normalized_mapping = {}
        for user_var in classification.variables:
            normalized_var = self._map_variable(
                user_var,
                domain_taxonomy,
                classification.domain
            )
            normalized_mapping[user_var] = normalized_var
        
        logger.info("✅ Normalisation terminée")
        logger.info(f"   Variables normalisées: {list(normalized_mapping.values())}")
        
        return NormalizedVariables(
            variables=normalized_mapping,
            domain_taxonomy=domain_taxonomy
        )
    
    def _map_variable(
        self,
        user_var: str,
        taxonomy: List[str],
        domain: str
    ) -> str:
        """
        Mappe une variable utilisateur vers la taxonomie
        
        Stratégies:
        1. Correspondance exacte
        2. Correspondance partielle (contient)
        3. Similarité de chaîne (fuzzy matching)
        4. Synonymes du domaine
        5. Fallback: retourner la variable telle quelle
        """
        user_var_lower = user_var.lower()
        
        # 1. Correspondance exacte
        for tax_var in taxonomy:
            if user_var_lower == tax_var.lower():
                logger.debug(f"   ✓ Exact match: {user_var} → {tax_var}")
                return tax_var
        
        # 2. Correspondance partielle (contient)
        for tax_var in taxonomy:
            if user_var_lower in tax_var.lower() or tax_var.lower() in user_var_lower:
                logger.debug(f"   ✓ Partial match: {user_var} → {tax_var}")
                return tax_var
        
        # 3. Synonymes spécifiques au domaine
        synonym_map = self._get_domain_synonyms(domain)
        for synonym, canonical in synonym_map.items():
            if synonym.lower() in user_var_lower:
                # Vérifier que le canonical existe dans la taxonomie
                for tax_var in taxonomy:
                    if canonical.lower() in tax_var.lower():
                        logger.debug(f"   ✓ Synonym match: {user_var} → {tax_var}")
                        return tax_var
        
        # 4. Fuzzy matching (similarité de chaîne)
        best_match = None
        best_score = 0.0
        for tax_var in taxonomy:
            score = difflib.SequenceMatcher(
                None,
                user_var_lower,
                tax_var.lower()
            ).ratio()
            
            if score > best_score and score >= 0.6:  # Seuil de 60%
                best_score = score
                best_match = tax_var
        
        if best_match:
            logger.debug(f"   ✓ Fuzzy match ({best_score:.2f}): {user_var} → {best_match}")
            return best_match
        
        # 5. Fallback: garder la variable telle quelle
        logger.warning(f"   ⚠️ No match found for: {user_var}, keeping as-is")
        return user_var
    
    def _get_domain_synonyms(self, domain: str) -> Dict[str, str]:
        """
        Retourne un mapping de synonymes pour un domaine
        
        Permet de mapper des termes métier courants vers la taxonomie
        """
        synonyms = {
            # Synonymes généraux
            "amount": "montant",
            "country": "pays",
            "frequency": "frequence",
            "time": "temps",
            "age": "age",
            "income": "revenu",
            "status": "statut",
        }
        
        # Synonymes spécifiques par domaine
        if domain == "fraude_bancaire":
            synonyms.update({
                "txn_amount": "transaction_amount",
                "transaction_amt": "transaction_amount",
                "tx_amount": "transaction_amount",
                "country_code": "country_code",
                "country_origin": "country_code",
                "tx_freq": "transaction_frequency",
                "frequency": "transaction_frequency",
                "merchant": "merchant_category",
                "merchant_type": "merchant_category",
            })
        
        elif domain == "credit_scoring":
            synonyms.update({
                "client_age": "customer_age",
                "user_age": "customer_age",
                "borrower_age": "customer_age",
                "salary": "customer_income",
                "revenue": "customer_income",
                "credit_hist": "credit_history",
                "credit_record": "credit_history",
                "job": "employment_status",
                "work": "employment_status",
            })
        
        elif domain == "detection_anomalies":
            synonyms.update({
                "pattern": "transaction_pattern",
                "behavior": "transaction_pattern",
                "freq": "transaction_frequency",
                "amount": "transaction_amount",
            })
        
        return synonyms
    
    def get_variable_metadata(self, normalized_var: str, domain: str) -> Dict:
        """
        Retourne les métadonnées d'une variable normalisée
        
        Utile pour comprendre le type, les valeurs possibles, etc.
        """
        # Dans un vrai système, cela viendrait d'une base de métadonnées
        metadata = {
            "name": normalized_var,
            "domain": domain,
            "type": "unknown",
            "possible_values": [],
            "description": ""
        }
        
        # Heuristiques simples pour déterminer le type
        if "amount" in normalized_var.lower() or "montant" in normalized_var.lower():
            metadata["type"] = "numeric"
            metadata["description"] = "Valeur monétaire"
        
        elif "code" in normalized_var.lower() or "pays" in normalized_var.lower():
            metadata["type"] = "categorical"
            metadata["possible_values"] = ["local", "regional", "international", "high_risk"]
            metadata["description"] = "Code géographique"
        
        elif "frequency" in normalized_var.lower() or "frequence" in normalized_var.lower():
            metadata["type"] = "categorical"
            metadata["possible_values"] = ["low", "medium", "high", "very_high"]
            metadata["description"] = "Fréquence d'occurrence"
        
        elif "age" in normalized_var.lower():
            metadata["type"] = "numeric"
            metadata["description"] = "Âge en années"
        
        elif "score" in normalized_var.lower():
            metadata["type"] = "numeric"
            metadata["description"] = "Score (0-100)"
        
        return metadata