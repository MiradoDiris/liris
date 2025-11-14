# gemini_worker.py - VERSION CORRIGÉE
import time
import re
try:
    from google import genai
    from google.genai import types
except ImportError:
    from utils.logger import logger
    logger.error("Package 'google-genai' non installé. Installez-le avec: pip install google-genai")
    raise

from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import logger
from utils.conversation_history import ConversationHistory


class GeminiWorker(QThread):
    """Worker pour effectuer des requêtes à l'API Gemini avec génération de snippets ciblés"""
    
    test_completed = pyqtSignal(bool, str, float, object)
    step_update = pyqtSignal(str, str)
    debug_info = pyqtSignal(str)
    snippet_generated = pyqtSignal(dict)
    
    def __init__(self, context, perimeter_data, api_key=None, dgraph_connector=None, conversation_history=None):
        super().__init__()
        self.context = context
        self.perimeter_data = perimeter_data
        self.api_key = api_key
        self.dgraph_connector = dgraph_connector
        self.platform_name = "Gemini"
        self.platform_index = 0
        self.usage_stats = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }
        self.conversation_history = conversation_history

        if not api_key:
                try:
                    from utils.keyring_helper import KeyringHelper
                    self.api_key = KeyringHelper.get_api_key("Gemini")

                    if self.api_key:
                        logger.info("✅ Clé API Gemini chargée depuis keyring")
                    else:
                        logger.warning("⚠️ Aucune clé API Gemini trouvée dans keyring")
                except ImportError as e:
                    logger.error(f"❌ Erreur import KeyringHelper: {e}")
                    self.api_key = None
                except Exception as e:
                    logger.error(f"❌ Erreur chargement config depuis keyring: {e}")
                    self.api_key = None
                else:
                    self.api_key = api_key
                    logger.info("✅ Clé API Gemini fournie en paramètre")
                
                if not self.api_key:
                    logger.warning("⚠️ Aucune clé API Gemini configurée")

        
    def run(self):
        """Exécute la requête Gemini avec historique de conversation"""
        start_time = time.time()
        usage_tracker = None

        try:
            from utils.ai_usage_tracker import AIUsageTracker
            usage_tracker = AIUsageTracker()

            self.step_update.emit("config", "Configuration de l'API Gemini...")

            if not self.api_key:
                raise ValueError("Clé API Gemini non configurée")

            client = genai.Client(api_key=self.api_key)

            self.step_update.emit("data", "Enrichissement des données avec le contenu complet...")
            enriched_perimeter = self._enrich_perimeter_with_content()

            self.step_update.emit("prompt", "Construction du prompt avec historique...")

            # 💬 AFFICHAGE: Montrer le contexte conversationnel
            if self.conversation_history:
                history_summary = self.conversation_history.get_summary()
                self.debug_info.emit(
                    f"💬 Historique: {history_summary['message_count']} messages "
                    f"({history_summary['user_messages']} utilisateur, "
                    f"{history_summary['assistant_messages']} assistant)"
                )

            # Construire le prompt actuel
            current_prompt = self._build_snippets_prompt(enriched_perimeter)

            # 🆕 Ajouter préfixe si continuation
            if self.conversation_history and self.conversation_history.messages:
                continuation_prefix = (
                    "📌 SUITE DE LA CONVERSATION\n\n"
                    "Voici ma nouvelle demande qui fait suite à notre discussion précédente:\n\n"
                )
                current_prompt = continuation_prefix + current_prompt

            # Enregistrer le message utilisateur AVANT l'envoi
            if self.conversation_history:
                self.conversation_history.add_user_message(
                    current_prompt,
                    metadata={
                        'perimeter_items': len(enriched_perimeter),
                        'context_length': len(self.context)
                    }
                )

            # ✅ CORRECTION: Préparer le contenu avec historique
            contents = []
            
            # Ajouter l'historique (sauf le dernier message qu'on vient d'ajouter)
            if self.conversation_history and len(self.conversation_history.messages) > 1:
                for msg in self.conversation_history.messages[:-1]:
                    role = 'model' if msg['role'] == 'assistant' else 'user'
                    # ✅ FIX: Part.from_text() ne prend qu'un argument (text=...)
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part(text=msg['content'])]  # ✅ Correction ici
                    ))

            # Ajouter le message actuel
            contents.append(types.Content(
                role='user',
                parts=[types.Part(text=current_prompt)]  # ✅ Correction ici aussi
            ))

            logger.info(f"📚 Envoi avec {len(contents)} messages (dont historique)")

            # Estimation des tokens d'entrée
            total_input_length = sum(len(c.parts[0].text) for c in contents if c.parts)
            input_tokens_estimate = total_input_length // 4

            self.step_update.emit("request", "Envoi de la requête à Gemini...")

            try:
                from utils.keyring_helper import KeyringHelper
                model = KeyringHelper.get_model("Gemini", "gemini-2.5-flash")
                max_output_tokens = 8192
                logger.info(f"📝 Configuration Gemini depuis keyring: {model} ({max_output_tokens} tokens)")
            except ImportError as e:
                logger.warning(f"⚠️ KeyringHelper non disponible, utilisation des valeurs par défaut: {e}")
                model = "gemini-2.5-flash"
                max_output_tokens = 8192
            except Exception as e:
                logger.error(f"❌ Erreur récupération config keyring: {e}")
                model = "gemini-2.5-flash"
                max_output_tokens = 8192

            logger.info(f"📝 Modèle Gemini: {model} ({max_output_tokens} tokens)")

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=max_output_tokens,
                )
            )

            if not response or not response.text:
                raise ValueError("Réponse vide de Gemini")

            self.step_update.emit("processing", "Traitement de la réponse...")
            duration = time.time() - start_time
            response_text = response.text

            # 🆕 NOUVEAU: Enregistrer la réponse dans l'historique
            if self.conversation_history:
                self.conversation_history.add_assistant_message(
                    response_text,
                    metadata={
                        'model': 'gemini-2.5-flash',    
                        'duration': duration,
                        'tokens_estimate': len(response_text) // 4
                    }
                )
                logger.info("✅ Réponse ajoutée à l'historique de conversation")

            # Estimation des tokens de sortie
            output_tokens_estimate = len(response_text) // 4

            # 🆕 Parser les snippets
            snippets = self._parse_snippets(response_text)
            
            # 🆕 Émettre chaque snippet individuellement
            for snippet in snippets:
                self.snippet_generated.emit(snippet)

            # Enregistrer l'usage dans la base de données
            if usage_tracker:
                usage_tracker.record_usage(
                    platform_name="Gemini",
                    model_name="gemini-2.5-flash",
                    success=True,
                    duration_seconds=duration,
                    input_tokens=input_tokens_estimate,
                    output_tokens=output_tokens_estimate,
                    context_length=total_input_length,
                    project_name=getattr(self, 'project_name', None),
                    session_type='coding'
                )

            # 🆕 Retourner un dictionnaire avec snippets
            result = {
                'text': response_text,
                'snippets': snippets
            }

            self.test_completed.emit(True, "Code généré avec succès", duration, result)
            logger.info(f"✅ Gemini request complétée avec succès ({duration:.2f}s, ~{output_tokens_estimate} tokens, {len(snippets)} snippets)")

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Erreur Gemini: {str(e)}"
            logger.error(error_msg)

            if usage_tracker:
                usage_tracker.record_usage(
                    platform_name="Gemini",
                    model_name="gemini-2.5-flash",
                    success=False,
                    duration_seconds=duration,
                    input_tokens=0,
                    output_tokens=0,
                    error_message=str(e),
                    project_name=getattr(self, 'project_name', None),
                    session_type='coding'
                )

            self.test_completed.emit(False, error_msg, duration, f"Erreur: {str(e)}")

    def _parse_snippets(self, response_text):
        """Parse la réponse pour extraire les snippets - VERSION AMÉLIORÉE"""
        snippets = []

        snippet_pattern = r'###\s*SNIPPET\s+\[([^\]]+)\]:\s*(.+?)(?:\n|$)'
        snippet_matches = list(re.finditer(snippet_pattern, response_text, re.IGNORECASE))

        for i, match in enumerate(snippet_matches):
            action = match.group(1).strip().upper()
            title = match.group(2).strip()

            start_pos = match.end()
            end_pos = snippet_matches[i + 1].start() if i + 1 < len(snippet_matches) else len(response_text)
            snippet_content = response_text[start_pos:end_pos]

            # 🔧 AMÉLIORATION 1: Extraction du fichier avec patterns multiples
            file_match = None

            # Pattern 1: **Fichier**: `path/to/file.py`
            file_match = re.search(r'\*\*Fichier\*\*:\s*`([^`]+)`', snippet_content, re.IGNORECASE)

            # Pattern 2: Fichier: path/to/file.py (sans backticks)
            if not file_match:
                file_match = re.search(r'\*\*Fichier\*\*:\s*([^\n]+?)(?:\n|\*\*)', snippet_content, re.IGNORECASE)

            # Pattern 3: File: (anglais)
            if not file_match:
                file_match = re.search(r'\*\*File\*\*:\s*`?([^`\n]+)`?', snippet_content, re.IGNORECASE)

            # 🔧 AMÉLIORATION 2: Extraction de la cible avec patterns multiples
            target_match = None

            # Pattern 1: **Classe/Fonction**: `ClassName.method()`
            target_match = re.search(
                r'\*\*(?:Classe/Fonction|Cible|Target|Classe|Function)\*\*:\s*`([^`]+)`', 
                snippet_content, 
                re.IGNORECASE
            )

            # Pattern 2: Sans backticks
            if not target_match:
                target_match = re.search(
                    r'\*\*(?:Classe/Fonction|Cible|Target|Classe|Function)\*\*:\s*([^\n]+?)(?:\n|\*\*)', 
                    snippet_content,
                    re.IGNORECASE
                )

            # Pattern 3: Détecter "dans la méthode X" ou "in method X"
            if not target_match:
                target_match = re.search(
                    r'(?:dans|in)\s+(?:la\s+)?(?:méthode|method|fonction|function|classe|class)\s+[`"]?([a-zA-Z0-9_\.]+)[`"]?',
                    snippet_content,
                    re.IGNORECASE
                )

            # Pattern 4: Chercher dans le titre si action == REMPLACER
            if not target_match and action in ['REMPLACER', 'REPLACE', 'MODIFIER', 'MODIFY']:
                # Ex: "Remplacer la méthode _build_prompt"
                target_match = re.search(
                    r'(?:remplacer|replace|modifier|modify|update)\s+(?:la\s+)?(?:méthode|method|fonction|function|classe|class)?\s*[`"]?([a-zA-Z0-9_\.]+)[`"]?',
                    title,
                    re.IGNORECASE
                )

            # 🔧 AMÉLIORATION 3: Extraction de l'action avec synonymes
            action_match = re.search(r'\*\*Action\*\*:\s*(\w+)', snippet_content, re.IGNORECASE)

            detected_action = action
            if action_match:
                raw_action = action_match.group(1).strip().upper()
                # Normaliser les actions
                action_mapping = {
                    'ADD': 'AJOUTER',
                    'CREATE': 'AJOUTER',
                    'INSERT': 'AJOUTER',
                    'MODIFY': 'MODIFIER',
                    'UPDATE': 'MODIFIER',
                    'CHANGE': 'MODIFIER',
                    'REPLACE': 'REMPLACER'
                }
                detected_action = action_mapping.get(raw_action, raw_action)

            # 🔧 AMÉLIORATION 4: Description nettoyée
            desc_match = re.search(
                r'\*\*Description\*\*:\s*(.+?)(?=\n\n```|\n```|\*\*Fichier\*\*|\*\*Action\*\*|$)', 
                snippet_content, 
                re.DOTALL
            )

            description = ""
            if desc_match:
                raw_desc = desc_match.group(1).strip()
                desc_lines = []
                for line in raw_desc.split('\n'):
                    line = line.strip()
                    if line and not any(marker in line.lower() for marker in [
                        '**fichier**', '**action**', '**cible**', '**classe',
                        'fichier:', 'file:', '```'
                    ]):
                        clean_line = re.sub(r'[a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css)', '', line)
                        clean_line = clean_line.strip()
                        if clean_line and not clean_line.startswith('**'):
                            desc_lines.append(clean_line)
                description = ' '.join(desc_lines)

            # 🔧 AMÉLIORATION 5: Extraction du code
            code_match = re.search(r'```(\w+)?\n(.*?)```', snippet_content, re.DOTALL)

            # 🔧 AMÉLIORATION 6: Si target manquant et action=REMPLACER, tenter extraction du code
            target_value = None
            if target_match:
                target_value = target_match.group(1).strip()
            elif detected_action in ['REMPLACER', 'MODIFIER'] and code_match:
                # Tenter d'extraire le nom de la fonction/classe du code
                code_text = code_match.group(2).strip()

                # Pattern Python: def function_name( ou class ClassName
                func_match = re.search(r'(?:def|class)\s+([a-zA-Z0-9_]+)', code_text)
                if func_match:
                    target_value = func_match.group(1)
                    logger.info(f"🎯 Target extrait automatiquement du code: {target_value}")

            # 🔧 Nom de fichier nettoyé
            file_name = "Non spécifié"
            if file_match:
                raw_file = file_match.group(1).strip()
                file_name = raw_file.strip('`\'"').strip()

            snippet = {
                'action': detected_action,
                'title': title,
                'file': file_name,
                'target': target_value,  # 🔧 PEUT ÊTRE None si non trouvé
                'description': description,
                'code': code_match.group(2).strip() if code_match else "",
                'language': code_match.group(1).strip() if code_match and code_match.group(1) else "python",
                'order': i + 1
            }

            # 🔧 AMÉLIORATION 7: Logging détaillé
            if detected_action in ['REMPLACER', 'MODIFIER'] and not target_value:
                logger.warning(
                    f"⚠️ Snippet {i+1} ({detected_action}): Target manquant!\n"
                    f"   Titre: {title}\n"
                    f"   Fichier: {file_name}\n"
                    f"   Extrait: {snippet_content[:200]}..."
                )
            else:
                logger.info(
                    f"✅ Snippet {i+1} parsé: {detected_action} - {title}\n"
                    f"   Fichier: {file_name}\n"
                    f"   Target: {target_value or 'N/A'}"
                )

            snippets.append(snippet)

        if not snippets:
            logger.warning("Aucun snippet formaté trouvé, tentative de parsing alternatif")
            snippets = self._parse_legacy_format(response_text)

        return snippets

    def _parse_legacy_format(self, response_text):
        """Parse l'ancien format - VERSION AMÉLIORÉE"""
        snippets = []
        code_blocks = re.finditer(r'```(\w+)?\n(.*?)```', response_text, re.DOTALL)
        
        for i, match in enumerate(code_blocks):
            language = match.group(1) or "python"
            code = match.group(2).strip()
            
            # Contexte AVANT le bloc
            context_start = max(0, match.start() - 500)
            context = response_text[context_start:match.start()]
            
            # 🔧 AMÉLIORATION: Extraction du fichier
            file_match = re.search(
                r'(?:fichier|file|dans|in|path)\s*[:`]?\s*([a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css|json|txt|md))',
                context,
                re.IGNORECASE
            )
            
            file_name = file_match.group(1).strip('`\'"').strip() if file_match else "Non spécifié"
            
            # 🔧 AMÉLIORATION: Extraction du target
            target_match = None
            
            # Pattern 1: "remplacer la méthode X"
            target_match = re.search(
                r'(?:remplacer|replace|modifier|modify)\s+(?:la\s+)?(?:méthode|method|fonction|function|classe|class)?\s*[`"]?([a-zA-Z0-9_\.]+)[`"]?',
                context,
                re.IGNORECASE
            )
            
            # Pattern 2: Extraire du code lui-même
            if not target_match:
                func_match = re.search(r'(?:def|class)\s+([a-zA-Z0-9_]+)', code)
                if func_match:
                    target_match = type('obj', (object,), {'group': lambda self, x: func_match.group(x)})()
            
            target_value = target_match.group(1) if target_match else None
            
            # 🔧 Détection de l'action
            detected_action = "MODIFIER"
            action_keywords = {
                'AJOUTER': ['ajouter', 'créer', 'nouveau', 'add', 'create', 'new'],
                'MODIFIER': ['modifier', 'mettre à jour', 'changer', 'modify', 'update', 'change'],
                'REMPLACER': ['remplacer', 'replace']
            }
            
            for action, keywords in action_keywords.items():
                if any(kw in context.lower() for kw in keywords):
                    detected_action = action
                    break
                
            # Description nettoyée
            context_lines = [line.strip() for line in context.split('\n') if line.strip()]
            clean_desc_lines = [
                line for line in context_lines[-3:]
                if not any(marker in line.lower() for marker in ['**fichier**', '**action**', '```', 'snippet'])
            ]
            description = ' '.join(clean_desc_lines) if clean_desc_lines else ""
            
            snippet = {
                'action': detected_action,
                'title': f"Snippet {i + 1}",
                'file': file_name,
                'target': target_value,  # 🔧 Maintenant extrait
                'description': description[:200],
                'code': code,
                'language': language,
                'order': i + 1
            }
            
            logger.info(
                f"✅ Legacy snippet {i+1}: {detected_action} - {file_name}\n"
                f"   Target: {target_value or 'Non trouvé'}"
            )
            
            snippets.append(snippet)
        
        return snippets
    
    def _enrich_perimeter_with_content(self):
        """Enrichit le périmètre avec le contenu complet des fichiers"""
        if not self.perimeter_data:
            return []

        enriched = []
        
        for item in self.perimeter_data:
            enriched_item = item.copy()
            uid = item.get('data', {}).get('uid', '')
            
            if uid and self.dgraph_connector:
                node_data = self._fetch_node_complete_data(uid)
                
                if node_data:
                    enriched_item['data']['fileContents'] = node_data.get('fileContents', '')
                    enriched_item['data']['codeContent'] = node_data.get('codeContent', '')
                    
                    enriched_related = []
                    for rel_item in enriched_item.get('related', []):
                        rel_uid = rel_item.get('data', {}).get('uid', '')
                        if rel_uid:
                            rel_data = self._fetch_node_complete_data(rel_uid)
                            if rel_data:
                                rel_item['data']['fileContents'] = rel_data.get('fileContents', '')
                                rel_item['data']['codeContent'] = rel_data.get('codeContent', '')
                        enriched_related.append(rel_item)
                    
                    enriched_item['related'] = enriched_related
            
            enriched.append(enriched_item)
        
        logger.info(f"✅ Périmètre enrichi: {len(enriched)} éléments avec contenu complet")
        return enriched

    def _fetch_node_complete_data(self, uid):
        """Requête Dgraph complète pour récupérer le contenu d'un nœud"""
        if not self.dgraph_connector or not uid:
            return None
        
        try:
            query = f"""
            {{
              node(func: uid({uid})) {{
                uid
                name
                nodeType
                description
                path
                fileContents
                codeContent
                relations @filter(type(Relation)) {{
                  uid
                  relationType
                  name
                  target {{
                    uid
                    name
                    nodeType
                    fileContents
                    codeContent
                    description
                  }}
                }}
                ~target @filter(type(Relation)) {{
                  uid
                  relationType
                  name
                  source {{
                    uid
                    name
                    nodeType
                    fileContents
                    codeContent
                    description
                  }}
                }}
                imports {{
                  uid
                  name
                  description
                  fileContents
                  codeContent
                }}
                functions {{
                  uid
                  name
                  description
                  calls {{
                    uid
                    name
                    fileContents
                    codeContent
                  }}
                }}
              }}
            }}
            """
            
            txn = self.dgraph_connector.client.txn(read_only=True)
            resp = txn.query(query)
            txn.discard()
            
            data = self.dgraph_connector._parse_response(resp)
            nodes = data.get('node', [])
            
            if nodes:
                node = nodes[0]
                logger.debug(f"✅ Contenu récupéré pour {node.get('name', 'N/A')}: {len(node.get('fileContents', ''))} chars")
                return node
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur fetch node {uid}: {e}")
            return None

    def _build_snippets_prompt(self, enriched_perimeter):
        """Construit un prompt optimisé pour la génération de snippets ciblés"""
        prompt_parts = []
        prompt_parts.append("# GÉNÉRATION DE SNIPPETS DE CODE - MODIFICATIONS CIBLÉES\n" + "=" * 80)
        prompt_parts.append("\n## CONTEXTE DE LA FONCTIONNALITÉ\n" + self.context.strip())
        prompt_parts.append("\n" + "-" * 80 + "\n")

        if enriched_perimeter:
            prompt_parts.append("## PÉRIMÈTRE D'IMPLÉMENTATION (code existant)\n")

            for idx, item in enumerate(enriched_perimeter, 1):
                name = item.get('name', 'N/A')
                node_type = item.get('type', 'unknown')
                prompt_parts.append(f"\n### {idx}. 📁 FICHIER: {name} ({node_type})")

                data = item.get('data', {})
                description = data.get('description', '')
                file_path = data.get('path', '')
                file_content = data.get('fileContents', '') or data.get('codeContent', '')

                if description:
                    prompt_parts.append(f"- 📝 Description: {description}")
                if file_path:
                    prompt_parts.append(f"- 📂 Chemin: {file_path}")

                if file_content:
                    prompt_parts.append(f"\n#### 📄 CODE EXISTANT ({len(file_content)} caractères):")
                    prompt_parts.append("```code\n" + file_content.strip() + "\n```\n")

                related = item.get('related', [])
                if related:
                    prompt_parts.append(f"\n#### 🔗 FICHIERS LIÉS ({len(related)}):")
                    for rel_idx, rel_item in enumerate(related, 1):
                        rel_name = rel_item.get('name', 'N/A')
                        rel_data = rel_item.get('data', {})
                        rel_content = rel_data.get('fileContents', '') or rel_data.get('codeContent', '')
                        if rel_content:
                            prompt_parts.append(f"\n##### {rel_idx}. {rel_name}")
                            prompt_parts.append("```code\n" + rel_content.strip() + "\n```\n")

        prompt_parts.append("\n" + "=" * 80)
        prompt_parts.append("""
## INSTRUCTIONS DE GÉNÉRATION - SNIPPETS CIBLÉS

⚠️ RÈGLES CRITIQUES:
1. **GÉNÈRE DES SNIPPETS DISTINCTS** - Un snippet par modification/ajout
2. **FORMAT OBLIGATOIRE** - Utilise le format ci-dessous pour CHAQUE snippet
3. **SOIS PRÉCIS** - Indique exactement où placer le code (fichier, classe, fonction)
4. **CODE COMPLET** - Chaque snippet doit être fonctionnel et complet
5. **ORDRE LOGIQUE** - Numéote les snippets dans l'ordre d'implémentation

📋 FORMAT OBLIGATOIRE POUR CHAQUE SNIPPET:

### SNIPPET [ACTION]: [TITRE DESCRIPTIF]
**Fichier**: `chemin/vers/fichier.py`
**Classe/Fonction**: `NomClasse.methode()` ou `nom_fonction()` (optionnel si nouveau fichier)
**Action**: AJOUTER | MODIFIER | REMPLACER
**Description**: Explication claire de ce que fait ce snippet et pourquoi

```python
# Code complet et fonctionnel ici
# Avec commentaires explicatifs
def exemple():
    pass
```

---

🎯 TYPES D'ACTIONS:
- **AJOUTER**: Nouveau code à insérer (nouvelle fonction, classe, méthode, fichier)
- **MODIFIER**: Code existant à mettre à jour (garder la structure, changer le contenu)
- **REMPLACER**: Code existant à remplacer complètement

🎯 OBJECTIF: Génère des snippets clairs, précis et directement applicables.
Chaque snippet doit pouvoir être copié-collé à l'emplacement indiqué.
""")

        full_prompt = "\n".join(prompt_parts)
        logger.info(f"📊 Taille totale du prompt: {len(full_prompt)} caractères ({len(full_prompt) // 4} tokens estimés)")
        return full_prompt