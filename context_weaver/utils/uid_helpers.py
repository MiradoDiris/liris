#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UID Helpers - Extraction et validation des UIDs (ChromaDB + Dgraph)
✅ Compatible avec ChromaDB (IDs simples) ET Dgraph (UIDs 0x...)
✅ Gestion robuste des métadonnées vides
"""

import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)


def extract_uid_from_metadata(metadata: Dict[str, Any]) -> str:
    """
    ✅ CORRIGÉ: Accepte les IDs ChromaDB (strings simples) ET Dgraph (0x...)
    
    Args:
        metadata: Dictionnaire de métadonnées
        
    Returns:
        UID extrait (string)
        
    Raises:
        ValueError: Si aucun UID trouvé ou metadata invalide
    """
    # Cas 1: metadata est directement une string
    if isinstance(metadata, str):
        if metadata.strip():  # ✅ Accepter toute string non-vide
            return metadata.strip()
        raise ValueError(f"String vide comme UID")
    
    # Cas 2: metadata n'est pas un dict
    if not isinstance(metadata, dict):
        raise ValueError(f"Type invalide pour metadata: {type(metadata)}")
    
    # Cas 3: metadata est un dict vide
    if not metadata:
        raise ValueError(
            f"Aucun UID valide trouvé dans metadata. "
            f"Champs disponibles: []"
        )
    
    # Cas 4: Chercher l'UID dans plusieurs champs possibles (ordre de priorité)
    uid_fields = ['id', 'taxon_id', 'uid', 'doc_id', '_id']
    
    for field in uid_fields:
        if field in metadata:
            value = metadata[field]
            
            # ✅ Accepter toute string non-vide (ChromaDB ou Dgraph)
            if isinstance(value, str) and value.strip():
                return value.strip()
            
            # Si c'est un dict imbriqué, extraction récursive
            if isinstance(value, dict):
                try:
                    return extract_uid_from_metadata(value)
                except ValueError:
                    continue
            
            # Si c'est un nombre, le convertir en string
            if isinstance(value, (int, float)):
                return str(value)
    
    # Cas 5: Aucun champ UID standard trouvé
    # Chercher n'importe quelle clé contenant 'id'
    for key, value in metadata.items():
        if 'id' in key.lower() and isinstance(value, str) and value.strip():
            logger.warning(f"⚠️ UID extrait via clé non-standard '{key}': {value}")
            return value.strip()
    
    # Échec final
    raise ValueError(
        f"Aucun UID valide trouvé dans metadata. "
        f"Champs disponibles: {list(metadata.keys())}"
    )


def validate_uid(uid: Union[str, Dict, Any]) -> str:
    """
    ✅ CORRIGÉ: Valide et normalise un UID (ChromaDB ou Dgraph)
    
    Args:
        uid: UID à valider (peut être string, dict, etc.)
        
    Returns:
        UID validé (string)
        
    Raises:
        ValueError: Si l'UID est invalide
    """
    # Cas 1: String directe
    if isinstance(uid, str):
        uid_stripped = uid.strip()
        if uid_stripped:  # ✅ Accepter toute string non-vide
            return uid_stripped
        raise ValueError(f"UID string vide")
    
    # Cas 2: Dict (extraire l'UID)
    if isinstance(uid, dict):
        logger.debug(f"UID au format dict, extraction en cours...")
        return extract_uid_from_metadata(uid)
    
    # Cas 3: Nombre (convertir en string)
    if isinstance(uid, (int, float)):
        logger.warning(f"⚠️ UID numérique converti en string: {uid}")
        return str(uid)
    
    # Cas 4: Type non supporté
    raise ValueError(f"Type invalide pour UID: {type(uid)} = {uid}")


def validate_uid_list(uids: List[Union[str, Dict, Any]]) -> List[str]:
    """
    ✅ CORRIGÉ: Valide une liste d'UIDs (ChromaDB ou Dgraph)
    
    Args:
        uids: Liste d'UIDs à valider
        
    Returns:
        Liste d'UIDs validés (strings)
    """
    validated = []
    errors = []
    
    for i, uid in enumerate(uids):
        try:
            validated_uid = validate_uid(uid)
            validated.append(validated_uid)
        except ValueError as e:
            errors.append((i, uid, str(e)))
            logger.debug(f"UID invalide à l'index {i}: {e}")
    
    if errors:
        logger.warning(
            f"⚠️ {len(errors)} UID(s) invalide(s) ignoré(s), "
            f"{len(validated)} valides"
        )
        
        # Log détaillé des premiers erreurs
        for i, (idx, uid, error) in enumerate(errors[:3]):
            logger.debug(f"   Erreur {i+1}: Index {idx}, UID={uid}, Raison={error}")
    
    return validated


# =============================================================================
# NOUVELLES FONCTIONS DE DIAGNOSTIC
# =============================================================================

def diagnose_metadata_structure(metadata: Dict[str, Any], context: str = "") -> None:
    """
    ✅ NOUVEAU: Diagnostique la structure des métadonnées
    
    Utile pour identifier pourquoi extract_uid_from_metadata() échoue
    """
    logger.info(f"\n🔍 DIAGNOSTIC METADATA {context}")
    logger.info(f"   Type: {type(metadata)}")
    logger.info(f"   Est dict?: {isinstance(metadata, dict)}")
    
    if isinstance(metadata, dict):
        logger.info(f"   Est vide?: {not metadata}")
        logger.info(f"   Nombre de clés: {len(metadata)}")
        
        if metadata:
            logger.info(f"   Clés: {list(metadata.keys())[:10]}")
            
            # Chercher les clés UID
            uid_keys = ['id', 'taxon_id', 'uid', 'doc_id', '_id']
            found_uid_keys = [k for k in uid_keys if k in metadata]
            
            if found_uid_keys:
                logger.info(f"   ✅ Clés UID trouvées: {found_uid_keys}")
                for key in found_uid_keys:
                    value = metadata[key]
                    logger.info(f"      → {key} = {repr(value)} (type: {type(value)})")
            else:
                logger.warning(f"   ⚠️ Aucune clé UID standard trouvée")
                
                # Chercher clés contenant 'id'
                id_like_keys = [k for k in metadata.keys() if 'id' in k.lower()]
                if id_like_keys:
                    logger.info(f"   Clés contenant 'id': {id_like_keys}")
        else:
            logger.error(f"   ❌ Metadata est un dict VIDE!")
    else:
        logger.error(f"   ❌ Metadata n'est PAS un dict!")
        logger.error(f"   Valeur: {repr(metadata)[:100]}")


def safe_extract_uid_from_result(
    result: tuple,
    fallback_prefix: str = "unknown"
) -> str:
    """
    ✅ NOUVEAU: Extraction d'UID ultra-sécurisée avec fallback
    
    Args:
        result: Tuple (taxon_id, score, metadata)
        fallback_prefix: Préfixe pour l'UID de fallback
        
    Returns:
        UID extrait (jamais d'exception)
    """
    if not isinstance(result, tuple) or len(result) < 3:
        fallback_id = f"{fallback_prefix}_invalid_result"
        logger.error(f"❌ Format de résultat invalide, utilisation de fallback: {fallback_id}")
        return fallback_id
    
    taxon_id, score, metadata = result
    
    # Priorité 1: taxon_id direct (si string)
    if isinstance(taxon_id, str) and taxon_id.strip():
        return taxon_id.strip()
    
    # Priorité 2: Extraire depuis metadata
    if isinstance(metadata, dict) and metadata:
        try:
            return extract_uid_from_metadata(metadata)
        except ValueError as e:
            logger.warning(f"⚠️ Échec extraction depuis metadata: {e}")
    
    # Priorité 3: Convertir taxon_id en string
    if taxon_id is not None:
        try:
            uid_str = str(taxon_id).strip()
            if uid_str and uid_str != 'None':
                logger.warning(f"⚠️ UID converti depuis {type(taxon_id)}: {uid_str}")
                return uid_str
        except:
            pass
    
    # Fallback final
    fallback_id = f"{fallback_prefix}_{id(result)}"
    logger.error(f"❌ Impossible d'extraire UID, utilisation de fallback: {fallback_id}")
    return fallback_id


# =============================================================================
# TESTS
# =============================================================================

def test_uid_extraction():
    """Tests unitaires pour vérifier la compatibilité ChromaDB + Dgraph"""
    
    print("\n" + "=" * 80)
    print("🧪 TESTS UID EXTRACTION (ChromaDB + Dgraph)")
    print("=" * 80)
    
    test_cases = [
        # ChromaDB - IDs simples
        ({'id': 'doc_123'}, 'doc_123', "ChromaDB - id simple"),
        ({'taxon_id': 'txn_456'}, 'txn_456', "ChromaDB - taxon_id"),
        
        # Dgraph - UIDs hexadécimaux
        ({'uid': '0x123abc'}, '0x123abc', "Dgraph - uid hex"),
        ({'id': '0xffffff'}, '0xffffff', "Dgraph - id hex"),
        
        # Cas limites
        ({'id': '  doc_789  '}, 'doc_789', "Avec espaces"),
        ({'custom_id': 'my_id'}, 'my_id', "Clé non-standard"),
        
        # Cas d'erreur
        ({}, None, "Dict vide - devrait échouer"),
        ({'name': 'test'}, None, "Sans UID - devrait échouer"),
    ]
    
    passed = 0
    failed = 0
    
    for metadata, expected, description in test_cases:
        try:
            result = extract_uid_from_metadata(metadata)
            
            if expected is None:
                print(f"❌ {description}: devrait échouer mais a retourné '{result}'")
                failed += 1
            elif result == expected:
                print(f"✅ {description}: OK ('{result}')")
                passed += 1
            else:
                print(f"❌ {description}: attendu '{expected}', reçu '{result}'")
                failed += 1
                
        except ValueError as e:
            if expected is None:
                print(f"✅ {description}: Échec attendu ('{str(e)[:50]}...')")
                passed += 1
            else:
                print(f"❌ {description}: erreur inattendue - {e}")
                failed += 1
    
    print("\n" + "-" * 80)
    print(f"Résultats: {passed} réussis, {failed} échoués")
    print("=" * 80 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    # Activer logging
    logging.basicConfig(level=logging.INFO)
    
    # Lancer les tests
    success = test_uid_extraction()
    
    if success:
        print("✅ Tous les tests sont passés!")
    else:
        print("❌ Certains tests ont échoué")