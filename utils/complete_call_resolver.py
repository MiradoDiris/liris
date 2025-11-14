import ast
import json
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import os
import uuid

from utils.enhanced_python_call_detector import EnhancedPythonCallDetector
from utils.logger import logger

class CompleteCallResolver:
    """
    Résolveur qui trace TOUS les appels avec leur fichier source.
    ✅ VERSION CORRIGÉE : Gère plusieurs formats de structure
    """
    
    def __init__(self, project_structure: Dict[str, Any]):
        self.structure = project_structure
        
        # Index complets
        self.function_index = defaultdict(list)  # func_name → [{file, uid, class, line}]
        self.method_index = defaultdict(list)    # method_name → [{file, uid, class, line}]
        self.class_index = {}                    # class_name → {file, uid}
        self.module_index = {}                   # module_name → file_path
        self.file_imports = {} 
        self.ast_cache = {}
        self.type_context = defaultdict(dict)
        self.variable_index = defaultdict(dict)
        
        self._build_complete_index()
    
    def _get_file_path(self, file_info: Dict) -> Optional[str]:
        """
        ✅ NOUVEAU : Extrait le chemin d'un fichier depuis plusieurs formats possibles
        
        Gère:
        - 'path': '/path/to/file.py'
        - 'files': ['/path/to/file.py']
        - Fallback sur 'label' ou 'name'
        """
        # Format 1 : Clé 'path' directe
        path = file_info.get('path')
        if path:
            return path
        
        # Format 2 : Array 'files'
        files = file_info.get('files', [])
        if files and len(files) > 0:
            return files[0]
        
        # Format 3 : Utiliser label/name comme fallback
        label = file_info.get('label') or file_info.get('name')
        if label:
            logger.debug(f"⚠️ Utilisation de label comme path: {label}")
            return label
        
        return None
    
    def _build_simple_type_context(self, file_path: str, content: str):
        """
        Heuristique simple pour inférer des types:
        - var = ClassName()
        - self.attr = ClassName()
        - var: Type = ...
        Stocke dans self.type_context[file_path]
        """
        if not content:
            return
        # si déjà fait
        if file_path in self.type_context and self.type_context[file_path]:
            return

        ctx = {}
        try:
            tree = self.ast_cache.get(file_path) or ast.parse(content)
            self.ast_cache[file_path] = tree
            for node in ast.walk(tree):
                # var = ClassName()
                if isinstance(node, ast.Assign):
                    # targets may be list
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        class_name = node.value.func.id
                        for tgt in node.targets:
                            if isinstance(tgt, ast.Name):
                                ctx[tgt.id] = class_name
                            elif isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == 'self':
                                # self.attr = ClassName()
                                ctx['self.' + tgt.attr] = class_name

                # var: Type = ...
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        ann = node.annotation
                        if isinstance(ann, ast.Name):
                            ctx[node.target.id] = ann.id
        except Exception:
            # pas bloquant
            pass

        self.type_context[file_path] = ctx
    
    def _build_complete_index(self):
        """✅ CORRIGÉ : Construit l'index avec gestion robuste des chemins"""
        all_files = self._get_all_files()
    
        logger.info(f"🔍 Indexation de {len(all_files)} fichier(s)...")
    
        if not all_files:
            logger.error("❌ Aucun fichier à indexer !")
            logger.error(f"   Structure keys : {list(self.structure.keys())}")
            return
        
        indexed_count = 0
        for file_info in all_files:
            # ✅ Utiliser la méthode robuste pour extraire le chemin
            file_path = self._get_file_path(file_info)
            
            if not file_path:
                logger.warning(f"⚠️ Fichier sans chemin valide, skip: {file_info.get('label', 'unknown')}")
                continue
            
            logger.debug(f"  📄 Indexation : {os.path.basename(file_path)}")
            indexed_count += 1
            
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Index module
            self.module_index[module_name] = file_path
            
            # Index classes
            for cls in file_info.get('classes', []):
                class_name = cls['name']
                self.class_index[class_name] = {
                    'file': file_path,
                    'uid': cls.get('uid', str(uuid.uuid4())),
                    'line': cls.get('line', 0)
                }
                
                # Index méthodes de classe
                for method in cls.get('methods', []):
                    self.method_index[method['name']].append({
                        'file': file_path,
                        'uid': method.get('uid'),
                        'class': class_name,
                        'line': method.get('line', 0),
                        'type': 'method'
                    })
            
            # Index fonctions globales
            for func in file_info.get('functions', []):
                if func.get('type') == 'method':
                    continue  # Déjà indexé avec les classes
                
                self.function_index[func['name']].append({
                    'file': file_path,
                    'uid': func.get('uid', str(uuid.uuid4())),
                    'class': None,
                    'line': func.get('line', 0),
                    'type': 'function'
                })
            
            # Construire contexte d'imports pour ce fichier
            self.file_imports[file_path] = self._build_import_context(file_info)
        
        logger.info(f"✅ Index complet : {indexed_count} fichiers, "
                   f"{len(self.function_index)} fonctions, "
                   f"{len(self.method_index)} méthodes, "
                   f"{len(self.class_index)} classes")
    
    def _build_import_context(self, file_info: Dict) -> Dict[str, str]:
        """
        Construit le contexte d'imports pour un fichier.
        Gère alias, from imports et mappe noms importés -> fichier source.
        """
        context = {}
        relations = file_info.get('relations', {})

        # Si les relations contiennent des entrées plus riches (alias), on les utilise
        for rel_type, rel_list in relations.items():
            if rel_type not in ['import', 'from_import', 'require']:
                continue

            for rel in rel_list:
                target = rel.get('target', '')
                alias = rel.get('alias') or rel.get('as') or None

                # normaliser le module_name (sans extension)
                module_name = os.path.splitext(os.path.basename(target))[0]
                if module_name in self.module_index:
                    target_file = self.module_index[module_name]
                    # mapping module name -> file
                    context[module_name] = target_file

                    # si alias fourni, map alias as well
                    if alias:
                        context[alias] = target_file

                    # ajouter toutes les fonctions/classes de ce module
                    target_info = self._find_file_info(target_file)
                    if target_info:
                        for func in target_info.get('functions', []):
                            context[func['name']] = target_file
                        for cls in target_info.get('classes', []):
                            context[cls['name']] = target_file

        # fallback: si aucune relation mais module_index contient file in same folder name
        return context
    
    def resolve_all_calls(self) -> Dict[str, List[Dict]]:
        """
        Résout TOUS les appels du projet avec leur fichier source.
        ✅ CORRIGÉ : Gestion robuste des chemins
        
        Returns:
            {
                'file_path': [
                    {
                        'source_func': 'main',
                        'source_uid': 'func_xxx',
                        'call_type': 'self_method',
                        'target_name': 'process',
                        'target_file': '/path/to/file.py',
                        'target_uid': 'func_yyy',
                        'line': 42,
                        'resolved': True
                    }
                ]
            }
        """
        all_resolved = defaultdict(list)
        all_files = self._get_all_files()
        
        for file_info in all_files:
            # ✅ Utiliser la méthode robuste
            file_path = self._get_file_path(file_info)
            
            if not file_path:
                continue
            
            # Lire le contenu
            content = self._get_file_content(file_info, file_path)
            if not content:
                continue
            
            # Analyser les appels avec le détecteur amélioré
            detector = EnhancedPythonCallDetector(content, file_path)
            function_calls = detector.extract_all_calls()
            
            # Résoudre chaque appel
            for func_name, calls in function_calls.items():
                # Trouver l'UID de la fonction source
                source_func = self._find_function_in_file(file_info, func_name)
                
                for call in calls:
                    resolved = self._resolve_single_call(
                        call, file_info, source_func
                    )
                    
                    if resolved:
                        all_resolved[file_path].append(resolved)
        
        return dict(all_resolved)
    
    def _get_file_content(self, file_info: Dict, file_path: str) -> str:
        """
        Récupère le contenu d'un fichier depuis plusieurs sources et construit un contexte de types simple.
        """
        if not file_path:
            return ""

        # Source 1 : 'file_contents' dans file_info
        file_contents = file_info.get('file_contents', {})
        content = ""
        if file_contents:
            content = file_contents.get(file_path) or next((c for p, c in file_contents.items() if c), "")
        if not content:
            # Fallback : lecture directe du disque
            content = self._read_file_content(file_path)

        # Construire cache AST & contexte de type si possible
        if content and file_path not in self.ast_cache:
            try:
                self.ast_cache[file_path] = ast.parse(content)
            except Exception:
                # parse failed — on ignore
                pass

        # Construire contexte de types simple
        self._build_simple_type_context(file_path, content)

        return content

    
    def _resolve_single_call(self, call: Dict, file_info: Dict, 
                            source_func: Optional[Dict]) -> Optional[Dict]:
        """
        Résout un appel unique en déterminant le fichier source.
        ✅ CORRIGÉ : Gestion robuste des chemins
        """
        file_path = self._get_file_path(file_info)
        if not file_path:
            return None
        
        call_type = call['call_type']
        target_name = call['target']
        qualifier = call.get('qualifier')
        
        resolved = {
            'source_func': source_func['name'] if source_func else 'unknown',
            'source_uid': source_func['uid'] if source_func else None,
            'call_type': call_type,
            'target_name': target_name,
            'line': call['line'],
            'full_call': call['full_call'],
            'resolved': False
        }
        
        # CAS 1 : self.method() → chercher dans la même classe
        if call_type == 'self_method':
            parent_class = self._find_parent_class(file_info, source_func)
            if parent_class:
                method = self._find_method_in_class(parent_class, target_name)
                if method:
                    resolved.update({
                        'target_file': file_path,
                        'target_uid': method.get('uid'),
                        'target_class': parent_class['name'],
                        'resolved': True,
                        'scope': 'same_class'
                    })
        
        # CAS 2 : super().method() → chercher dans la classe parent
        elif call_type == 'super_method':
            parent_class = self._find_parent_class(file_info, source_func)
            if parent_class:
                for base_name in parent_class.get('bases', []):
                    base_class_info = self.class_index.get(base_name)
                    if base_class_info:
                        resolved.update({
                            'target_file': base_class_info['file'],
                            'target_uid': base_class_info['uid'],
                            'target_class': base_name,
                            'resolved': True,
                            'scope': 'parent_class'
                        })
                        break
        
        # CAS 3 : module.function() ou obj.method() → chercher via imports
        elif call_type == 'qualified':
            import_context = self.file_imports.get(file_path, {}) or {}

            # Si le qualifier est un module importé
            if qualifier in import_context:
                target_file = import_context[qualifier]
                target_func = self._find_function_by_name(target_name, target_file)
                if target_func:
                    resolved.update({
                        'target_file': target_file,
                        'target_uid': target_func.get('uid'),
                        'resolved': True,
                        'scope': 'imported_module'
                    })
                    return resolved

            # Sinon, tenter d'inférer le type de l'objet via type_context
            type_ctx = self.type_context.get(file_path, {})
            inferred = None

            # 1) var = ClassName() -> type_ctx['var'] = 'ClassName'
            if qualifier in type_ctx:
                class_name = type_ctx[qualifier]
                # chercher méthode dans class_index et method_index
                for m in self.method_index.get(target_name, []):
                    if m.get('class') == class_name:
                        resolved.update({
                            'target_file': m['file'],
                            'target_uid': m.get('uid'),
                            'target_class': class_name,
                            'resolved': True,
                            'scope': 'inferred_object'
                        })
                        return resolved

            # 2) self.attr (stocké comme 'self.attr')
            attr_key = f"self.{qualifier}" if qualifier else None
            if attr_key and attr_key in type_ctx:
                class_name = type_ctx[attr_key]
                for m in self.method_index.get(target_name, []):
                    if m.get('class') == class_name:
                        resolved.update({
                            'target_file': m['file'],
                            'target_uid': m.get('uid'),
                            'target_class': class_name,
                            'resolved': True,
                            'scope': 'inferred_self_attribute'
                        })
                        return resolved

            # 3) fallback : essayer de prendre première méthode indexée (heuristique)
            for method_info in self.method_index.get(target_name, []):
                resolved.update({
                    'target_file': method_info['file'],
                    'target_uid': method_info['uid'],
                    'target_class': method_info.get('class'),
                    'resolved': True,
                    'scope': 'object_method_heuristic',
                    'note': f"Appel sur objet '{qualifier}' (heuristique)"
                })
                return resolved
        
        # CAS 4 : function() simple → chercher localement puis dans imports
        elif call_type == 'simple':
            # D'abord dans le même fichier
            local_func = self._find_function_by_name(target_name, file_path)
            if local_func:
                resolved.update({
                    'target_file': file_path,
                    'target_uid': local_func['uid'],
                    'resolved': True,
                    'scope': 'same_file'
                })
            else:
                # Puis dans les imports
                import_context = self.file_imports.get(file_path, {})
                if target_name in import_context:
                    target_file = import_context[target_name]
                    target_func = self._find_function_by_name(target_name, target_file)
                    
                    if target_func:
                        resolved.update({
                            'target_file': target_file,
                            'target_uid': target_func['uid'],
                            'resolved': True,
                            'scope': 'imported_function'
                        })
        
        # CAS 5 : ClassName.method() → méthode statique
        elif call_type == 'static_or_class':
            class_info = self.class_index.get(qualifier)
            if class_info:
                target_file_info = self._find_file_info(class_info['file'])
                target_class = self._find_class_by_name(target_file_info, qualifier)
                
                if target_class:
                    method = self._find_method_in_class(target_class, target_name)
                    if method:
                        resolved.update({
                            'target_file': class_info['file'],
                            'target_uid': method.get('uid'),
                            'target_class': qualifier,
                            'resolved': True,
                            'scope': 'static_method'
                        })
        
        return resolved
    
    # Méthodes utilitaires
    
    def _get_all_files(self) -> List[Dict]:
        """
        ✅ VERSION CORRIGÉE : Récupère tous les fichiers avec support multi-structure.
        """
        files = []
        
        def recurse(node):
            """Parcours récursif d'un nœud."""
            if node.get('type') == 'file':
                files.append(node)
            
            for child in node.get('children', []):
                recurse(child)
        
        # ✅ ÉTAPE 1 : Déterminer où chercher
        ontology = self.structure.get('turing_ontology', {})
        
        # Essayer clusters_detailed dans turing_ontology
        clusters = ontology.get('clusters_detailed', [])
        
        # Fallback : clusters à la racine
        if not clusters:
            clusters = self.structure.get('clusters_detailed', [])
        
        # Fallback ultime : clusters simple
        if not clusters:
            clusters = self.structure.get('clusters', [])
        
        logger.info(f"🔍 Structure détectée : {len(clusters)} cluster(s)")
        
        # ✅ ÉTAPE 2 : Parcourir TOUS les clusters
        for i, cluster in enumerate(clusters):
            logger.debug(f"  📁 Cluster {i+1}: {cluster.get('name', 'N/A')}")
            
            # Parcourir le cluster lui-même (peut contenir des fichiers directs)
            recurse(cluster)
            
            # Parcourir les root_labels (structure hiérarchique)
            for root_label in cluster.get('root_labels', []):
                recurse(root_label)
        
        logger.info(f"✅ {len(files)} fichier(s) indexé(s)")
        
        # ✅ ÉTAPE 3 : Log détaillé si vide
        if not files:
            logger.error("❌ AUCUN FICHIER TROUVÉ !")
            logger.error(f"   Structure reçue : {json.dumps(self.structure, indent=2, default=str)[:500]}...")
        
        return files
    
    def _find_file_info(self, file_path: str) -> Optional[Dict]:
        """✅ CORRIGÉ : Trouve les infos d'un fichier avec normalisation du chemin"""
        all_files = self._get_all_files()

        # Normaliser le chemin recherché
        normalized_search = os.path.normpath(file_path)

        for f in all_files:
            f_path = self._get_file_path(f)
            if not f_path:
                continue
            
            f_path_normalized = os.path.normpath(f_path)

            # Comparaison exacte
            if f_path_normalized == normalized_search:
                return f

            # Comparaison par nom de fichier (fallback)
            if os.path.basename(f_path_normalized) == os.path.basename(normalized_search):
                return f

        logger.debug(f"⚠️ Fichier non trouvé : {file_path}")
        return None
    
    def _read_file_content(self, file_path: str) -> str:
        """Lit le contenu d'un fichier."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""
    
    def _find_function_in_file(self, file_info: Dict, func_name: str) -> Optional[Dict]:
        """Trouve une fonction dans un fichier."""
        for func in file_info.get('functions', []):
            if func['name'] == func_name:
                return func
        
        # Chercher aussi dans les méthodes
        for cls in file_info.get('classes', []):
            for method in cls.get('methods', []):
                if method['name'] == func_name:
                    return method
        
        return None
    
    def _find_function_by_name(self, func_name: str, file_path: str) -> Optional[Dict]:
        """Trouve une fonction par nom dans un fichier spécifique."""
        matches = self.function_index.get(func_name, [])
        for match in matches:
            if match['file'] == file_path:
                return match
        return None
    
    def _find_parent_class(self, file_info: Dict, func: Optional[Dict]) -> Optional[Dict]:
        """Trouve la classe parent d'une méthode."""
        if not func:
            return None
        
        for cls in file_info.get('classes', []):
            for method in cls.get('methods', []):
                if method['name'] == func['name']:
                    return cls
        return None
    
    def _find_method_in_class(self, cls: Dict, method_name: str) -> Optional[Dict]:
        """Trouve une méthode dans une classe."""
        for method in cls.get('methods', []):
            if method['name'] == method_name:
                return method
        return None
    
    def _find_class_by_name(self, file_info: Dict, class_name: str) -> Optional[Dict]:
        """Trouve une classe par nom."""
        for cls in file_info.get('classes', []):
            if cls['name'] == class_name:
                return cls
        return None