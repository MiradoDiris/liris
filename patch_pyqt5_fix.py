#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PATCH RAPIDE POUR PYQT5
Remplace filter_fn par where dans taxonomy_retriever.py
"""

def patch_taxonomy_retriever():
    """
    Patch automatique du fichier taxonomy_retriever.py
    Remplace filter_fn par where pour compatibilité PyQt5
    """
    
    import fileinput
    import sys
    from pathlib import Path
    
    # Trouver le fichier
    retriever_path = Path("context_weaver/taxonomy/taxonomy_retriever.py")
    
    if not retriever_path.exists():
        print(f"❌ Fichier non trouvé: {retriever_path}")
        print("   Assurez-vous d'être dans le bon répertoire")
        return False
    
    print(f"📝 Patching: {retriever_path}")
    
    # Backup
    backup_path = retriever_path.with_suffix('.py.backup')
    import shutil
    shutil.copy(retriever_path, backup_path)
    print(f"✅ Backup créé: {backup_path}")
    
    # Lire le fichier
    with open(retriever_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patch 1: Ajouter la méthode _create_chroma_where_filter
    if '_create_chroma_where_filter' not in content:
        # Trouver où insérer (après _create_filter_function)
        insert_marker = "return filter_fn\n"
        
        new_method = '''
    
    def _create_chroma_where_filter(self, context):
        """
        ✅ Crée un filtre WHERE pour ChromaDB (PyQt5-safe)
        Remplace filter_fn pour meilleure performance et compatibilité
        """
        if not context or 'domain' not in context:
            logger.warning("⚠️ No domain in context - NO FILTER")
            return None

        target_domain = context['domain']

        if target_domain.lower() in ['unknown', 'none', '']:
            logger.warning(f"⚠️ Domain '{target_domain}' is invalid, NO FILTER")
            return None

        logger.info(f"🔒 Creating WHERE filter for domain: '{target_domain}'")
        return {"domain": target_domain}
'''
        
        content = content.replace(insert_marker, insert_marker + new_method)
        print("✅ Patch 1: Méthode _create_chroma_where_filter ajoutée")
    
    # Patch 2: Remplacer filter_fn par where_filter dans _dense_retrieval
    content = content.replace(
        "filter_fn = self._create_filter_function(context)",
        "where_filter = self._create_chroma_where_filter(context)  # ✅ PYQT5 FIX"
    )
    
    content = content.replace(
        "if filter_fn is not None and self.search_params.get('has_filter_fn'):",
        "if where_filter is not None and self.search_params.get('has_where'):"
    )
    
    content = content.replace(
        "search_kwargs['filter_fn'] = filter_fn",
        "search_kwargs['where'] = where_filter"
    )
    
    content = content.replace(
        'logger.info("ℹ️ Filter function will be applied")',
        'logger.info(f"ℹ️ WHERE clause: {where_filter}")'
    )
    
    print("✅ Patch 2: filter_fn remplacé par where_filter")
    
    # Écrire le fichier patché
    with open(retriever_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fichier patché avec succès!")
    print("\n📋 Changements:")
    print("   1. Ajout de _create_chroma_where_filter()")
    print("   2. Remplacement de filter_fn par where dans _dense_retrieval()")
    print("   3. Utilisation de WHERE clause ChromaDB (plus rapide)")
    
    print(f"\n💾 Backup disponible: {backup_path}")
    print("\n🎯 Testez maintenant votre interface PyQt5!")
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("🔧 PATCH PYQT5 - Taxonomy Retriever")
    print("=" * 80)
    print()
    print("Ce patch corrige le crash de l'interface PyQt5 en:")
    print("  • Remplaçant filter_fn par WHERE clause ChromaDB")
    print("  • Éliminant les problèmes de thread-safety")
    print("  • Améliorant les performances")
    print()
    
    success = patch_taxonomy_retriever()
    
    if success:
        print("\n" + "=" * 80)
        print("✅ PATCH APPLIQUÉ AVEC SUCCÈS")
        print("=" * 80)
        print()
        print("Prochaines étapes:")
        print("  1. Relancez votre interface PyQt5")
        print("  2. Testez la génération de dataset")
        print("  3. Si problème, restaurez: mv taxonomy_retriever.py.backup taxonomy_retriever.py")
        print()
    else:
        print("\n❌ Patch échoué")
        print("Vérifiez que vous êtes dans le bon répertoire")