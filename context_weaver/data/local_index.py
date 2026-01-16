#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestionnaire d'index local Whoosh
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from whoosh import index
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser

from context_weaver.config.bm25_config import BM25Config

logger = logging.getLogger(__name__)

class LocalIndex:
    """Gestionnaire de l'index BM25 local"""
    
    def __init__(self):
        self.index_dir = BM25Config.get_index_path()
        self.index = None
        self._ensure_index()
    
    def _ensure_index(self):
        """Assure que l'index existe"""
        if not index.exists_in(str(self.index_dir)):
            self._create_index()
        else:
            self.index = index.open_dir(str(self.index_dir))
            logger.info(f"✅ Index ouvert: {self.index_dir}")
    
    def _create_index(self):
        """Crée un nouvel index"""
        schema = Schema(
            id=ID(stored=True, unique=True),
            name=TEXT(stored=True),
            domain=ID(stored=True),
            type=ID(stored=True),
            description=TEXT(stored=True),
            variables=TEXT(stored=True),
            content=TEXT(stored=True)
        )
        
        self.index = index.create_in(str(self.index_dir), schema)
        logger.info(f"✅ Nouvel index créé: {self.index_dir}")
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Ajoute des documents à l'index"""
        writer = self.index.writer()
        
        for doc in documents:
            writer.add_document(
                id=str(doc.get("id", "")),
                name=doc.get("name", ""),
                domain=doc.get("domain", ""),
                type=doc.get("type", ""),
                description=doc.get("description", ""),
                variables=doc.get("variables", ""),
                content=doc.get("content", "")
            )
        
        writer.commit()
        logger.info(f"✅ {len(documents)} documents ajoutés")
    
    def get_stats(self) -> Dict[str, int]:
        """Retourne les statistiques de l'index"""
        return {
            "doc_count": self.index.doc_count_all(),
            "schema_fields": len(self.index.schema.names())
        }