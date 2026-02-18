#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TypologyGrouper - Regroupement Strict par Typologie
✅ CORRIGÉ: Utilisation correcte des attributs de TaxonCandidate
✅ UN SEUL SLOT PAR TYPOLOGIE
✅ AUCUN ARBITRAGE - TOUS LES CONTEXTES CONSERVÉS
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TypologySlot:
    """
    Représente UN slot de typologie dans la combinaison finale
    Contient TOUS les contextes de cette typologie (aucun filtrage)
    """
    typologie_name: str
    typologie_id: str
    contexts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_context(self, context: Dict[str, Any]):
        """Ajoute un contexte sans condition"""
        self.contexts.append(context)
        self._update_metadata()
    
    def _update_metadata(self):
        """Calcule des statistiques sur les contextes (NON DÉCISIONNEL)"""
        if not self.contexts:
            return
        
        scores = [c.get('final_score', 0) for c in self.contexts]
        depths = [c.get('depth', 0) for c in self.contexts]
        
        self.metadata = {
            'total_contexts': len(self.contexts),
            'score_range': {
                'min': min(scores) if scores else 0,
                'max': max(scores) if scores else 0,
                'avg': sum(scores) / len(scores) if scores else 0
            },
            'depth_range': {
                'min': min(depths) if depths else 0,
                'max': max(depths) if depths else 0
            }
        }


@dataclass
class GroupedCombination:
    """Combinaison finale = UNE liste de slots (1 slot par typologie)"""
    slots: List[TypologySlot] = field(default_factory=list)
    
    def add_slot(self, slot: TypologySlot):
        """Ajoute un slot de typologie"""
        self.slots.append(slot)
    
    def get_total_contexts(self) -> int:
        """Nombre total de contextes (tous slots confondus)"""
        return sum(len(slot.contexts) for slot in self.slots)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export en dict pour JSON/DB"""
        return {
            'total_typologies': len(self.slots),
            'total_contexts': self.get_total_contexts(),
            'slots': [
                {
                    'typologie_name': slot.typologie_name,
                    'typologie_id': slot.typologie_id,
                    'contexts': slot.contexts,
                    'metadata': slot.metadata
                }
                for slot in self.slots
            ]
        }


class TypologyGrouper:
    """
    ✅ REGROUPEMENT STRICT PAR TYPOLOGIE
    
    Règles :
    1. Identifie la typologie de chaque contexte
    2. Crée UN slot par typologie unique
    3. Regroupe TOUS les contextes de même typologie dans leur slot
    4. Aucun filtrage, arbitrage ou élimination
    """
    
    def __init__(self, typologie_key: str = 'typologie_name'):
        """
        Args:
            typologie_key: Clé dans les métadonnées du contexte pour identifier la typologie
        """
        self.typologie_key = typologie_key
    
    def group(self, candidates: List) -> GroupedCombination:
        """
        Regroupe les candidats par typologie
        
        Args:
            candidates: Liste de TaxonCandidate enrichis (objets avec attributs)
            
        Returns:
            GroupedCombination avec UN slot par typologie
        """
        
        logger.info("\n" + "="*80)
        logger.info("🔄 TYPOLOGIE GROUPER - REGROUPEMENT")
        logger.info("="*80)
        logger.info(f"📥 Input: {len(candidates)} candidats")
        
        # ✅ ÉTAPE 1 : Grouper par typologie
        typologie_map = defaultdict(list)
        
        for candidate in candidates:
            # ✅ CORRECTION: Accès aux attributs au lieu de .get()
            typologie_id = self._extract_typologie_id(candidate)
            typologie_name = self._extract_typologie_name(candidate)
            
            if not typologie_id:
                logger.warning(f"⚠️ Candidat sans typologie : {getattr(candidate, 'name', 'Unknown')}")
                typologie_id = "unknown"
                typologie_name = "Typologie Inconnue"
            
            typologie_map[typologie_id].append({
                'typologie_name': typologie_name,
                'candidate': candidate
            })
        
        logger.info(f"\n📊 {len(typologie_map)} typologie(s) unique(s) détectée(s)")
        
        # ✅ ÉTAPE 2 : Créer les slots
        combination = GroupedCombination()
        
        for typologie_id, items in typologie_map.items():
            typologie_name = items[0]['typologie_name']
            
            slot = TypologySlot(
                typologie_name=typologie_name,
                typologie_id=typologie_id
            )
            
            # Ajouter TOUS les contextes (aucun filtrage)
            for item in items:
                candidate = item['candidate']
                
                # ✅ CORRECTION: Accès aux attributs
                context = {
                    'taxon_id': getattr(candidate, 'taxon_id', None),
                    'name': getattr(candidate, 'name', 'N/A'),
                    'breadcrumb': getattr(candidate, 'breadcrumb', ''),
                    'definition': getattr(candidate, 'definition', ''),
                    'depth': getattr(candidate, 'depth', 0),
                    'final_score': getattr(candidate, 'final_score', 0),
                    'rrf_score': getattr(candidate, 'rrf_score', 0),
                    'metadata': getattr(candidate, 'metadata', {})
                }
                
                slot.add_context(context)
            
            combination.add_slot(slot)
            
            logger.info(f"\n✅ Typologie: {typologie_name}")
            logger.info(f"   • ID: {typologie_id}")
            logger.info(f"   • Contextes: {len(slot.contexts)}")
            logger.info(f"   • Score range: {slot.metadata['score_range']['min']:.3f} → {slot.metadata['score_range']['max']:.3f}")
        
        logger.info(f"\n📦 Combinaison finale:")
        logger.info(f"   • Total typologies: {len(combination.slots)}")
        logger.info(f"   • Total contextes: {combination.get_total_contexts()}")
        logger.info("="*80 + "\n")
        
        return combination
    
    def _extract_typologie_id(self, candidate) -> str:
        """✅ CORRECTION: Extrait l'ID de typologie depuis les attributs"""
        
        # 1. Métadonnée explicite
        metadata = getattr(candidate, 'metadata', {})
        if isinstance(metadata, dict) and 'typologie_id' in metadata:
            return metadata['typologie_id']
        
        # 2. Domain
        domain = getattr(candidate, 'domain', None)
        if domain and domain != 'unknown':
            return domain
        
        # 3. Breadcrumb (premier élément)
        breadcrumb = getattr(candidate, 'breadcrumb', '')
        if breadcrumb and '→' in breadcrumb:
            first_element = breadcrumb.split('→')[0].strip()
            if first_element:
                return first_element
        
        # 4. Fallback
        return "unknown"
    
    def _extract_typologie_name(self, candidate) -> str:
        """✅ CORRECTION: Extrait le nom lisible de la typologie depuis les attributs"""
        
        # 1. Nom explicite
        metadata = getattr(candidate, 'metadata', {})
        if isinstance(metadata, dict) and self.typologie_key in metadata:
            return metadata[self.typologie_key]
        
        # 2. Domain comme nom
        if isinstance(metadata, dict) and 'domain' in metadata:
            return metadata['domain']
        
        # 3. Premier élément du breadcrumb
        breadcrumb = getattr(candidate, 'breadcrumb', '')
        if breadcrumb and '→' in breadcrumb:
            return breadcrumb.split('→')[0].strip()
        
        # 4. Fallback
        domain = getattr(candidate, 'domain', 'Typologie Inconnue')
        return domain if domain != 'unknown' else 'Typologie Inconnue'