import os
import time
import re
import keyring
import json
try:
    from anthropic import Anthropic
except ImportError:
    from utils.logger import logger
    logger.error("Package 'anthropic' non installé. Installez-le avec: pip install anthropic")
    raise

from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import logger


class ClaudeWorker(QThread):
    """Worker pour effectuer des requêtes à l'API Claude avec génération de snippets ciblés"""

    # Signaux
    test_completed = pyqtSignal(bool, str, float, object)
    step_update = pyqtSignal(str, str)
    debug_info = pyqtSignal(str)
    snippet_generated = pyqtSignal(dict)

    def __init__(self, context, perimeter_data, api_key=None, dgraph_connector=None, use_opus=False, conversation_history=None):
        super().__init__()
        self.context = context
        self.perimeter_data = perimeter_data
        self.api_key = api_key
        self.dgraph_connector = dgraph_connector
        self.use_opus = use_opus
        self.platform_name = "Claude"
        self.platform_index = 1
        self.usage_stats = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }

        self.conversation_history = conversation_history

        if not api_key:
            try:
                from utils.keyring_helper import KeyringHelper
                config = KeyringHelper.get_platform_config("Claude")
                self.api_key = config.get('api_key', '')

                # Déterminer use_opus depuis le modèle stocké si non spécifié
                stored_model = config.get('model', '')
                if stored_model and not use_opus:
                    self.use_opus = 'opus' in stored_model.lower()
                    logger.info(f"📝 Modèle détecté depuis keyring: {stored_model} (use_opus={self.use_opus})")
                else:
                    self.use_opus = use_opus

                if self.api_key:
                    logger.info("✅ Clé API Claude chargée depuis keyring")
                else:
                    logger.warning("⚠️ Aucune clé API Claude trouvée dans keyring")
            except ImportError as e:
                logger.error(f"❌ Erreur import KeyringHelper: {e}")
                self.api_key = None
            except Exception as e:
                logger.error(f"❌ Erreur chargement config depuis keyring: {e}")
                self.api_key = None
            else:
                self.api_key = api_key
                self.use_opus = use_opus
                logger.info("✅ Clé API Claude fournie en paramètre")

            if not self.api_key:
                logger.warning("⚠️ Aucune clé API Claude configurée")

    def run(self):
        """Exécute la requête Claude avec historique de conversation"""
        start_time = time.time()
        usage_tracker = None

        try:
            from utils.ai_usage_tracker import AIUsageTracker
            usage_tracker = AIUsageTracker()

            self.step_update.emit("config", "Configuration de l'API Claude...")

            if not self.api_key:
                raise ValueError("Clé API Claude non configurée")

            client = Anthropic(api_key=self.api_key)

            self.step_update.emit("data", "Enrichissement des données avec le contenu complet...")
            enriched_perimeter = self._enrich_perimeter_with_content()

            self.step_update.emit("prompt", "Construction du prompt complet...")

            # 🆕 MODIFICATION: Construire les messages avec historique
            messages = self._build_messages_with_history(enriched_perimeter)

            # Choisir le modèle et max_tokens
            try:
                from utils.keyring_helper import KeyringHelper
                stored_model = KeyringHelper.get_model("Claude")
                stored_max_tokens = KeyringHelper.get_max_tokens("Claude")
                
                if stored_model:
                    model = stored_model
                    is_opus = 'opus' in stored_model.lower()
                    max_tokens = 8192
                    model_name = "Claude Opus 4" if is_opus else "Claude Sonnet 4"
                    logger.info(f"📝 Configuration depuis keyring: {model} ({max_tokens} tokens)")
                else:
                    # Fallback sur les valeurs par défaut
                    if self.use_opus:
                        model = "claude-opus-4-20250514"
                        max_tokens = 16384
                        model_name = "Claude Opus 4"
                    else:
                        model = "claude-sonnet-4-20250514"
                        max_tokens = 8192
                        model_name = "Claude Sonnet 4"
                    logger.info(f"📝 Utilisation du modèle par défaut: {model}")
            except ImportError as e:
                logger.warning(f"⚠️ KeyringHelper non disponible, utilisation des valeurs par défaut: {e}")
                # Fallback complet
                if self.use_opus:
                    model = "claude-opus-4-20250514"
                    max_tokens = 16384
                    model_name = "Claude Opus 4"
                else:
                    model = "claude-sonnet-4-20250514"
                    max_tokens = 8192
                    model_name = "Claude Sonnet 4"
                logger.info(f"📝 Modèle par défaut: {model}")
            except Exception as e:
                logger.error(f"❌ Erreur récupération config keyring: {e}")
                # Fallback complet
                if self.use_opus:
                    model = "claude-opus-4-20250514"
                    max_tokens = 16384
                    model_name = "Claude Opus 4"
                else:
                    model = "claude-sonnet-4-20250514"
                    max_tokens = 8192
                    model_name = "Claude Sonnet 4"
                logger.info(f"📝 Modèle par défaut (après erreur): {model}")

            self.step_update.emit("request", f"Envoi à {model_name}...")

            # 🆕 AFFICHAGE: Montrer le contexte conversationnel
            if self.conversation_history:
                history_summary = self.conversation_history.get_summary()
                self.debug_info.emit(
                    f"💬 Historique: {history_summary['message_count']} messages "
                    f"({history_summary['user_messages']} utilisateur, "
                    f"{history_summary['assistant_messages']} assistant)"
                )

            # 🆕 MODIFICATION: Envoyer avec l'historique
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.7,
                messages=messages  # ✅ Utilise les messages avec historique
            )

            if not response or not response.content:
                raise ValueError("Réponse vide de Claude")

            self.step_update.emit("processing", "Traitement de la réponse...")
            duration = time.time() - start_time

            # Extraire le texte complet
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text += block.text

            if not response_text:
                raise ValueError("Aucun contenu texte dans la réponse de Claude")

            # 🆕 NOUVEAU: Enregistrer la réponse dans l'historique
            if self.conversation_history:
                self.conversation_history.add_assistant_message(
                    response_text,
                    metadata={
                        'model': model_name,
                        'duration': duration,
                        'tokens': response.usage.output_tokens if response.usage else 0
                    }
                )
                logger.info("✅ Réponse ajoutée à l'historique de conversation")

            # Vérifier si la réponse a été tronquée
            stop_reason = response.stop_reason
            if stop_reason == "max_tokens":
                warning = f"⚠️ Réponse tronquée - Limite de {max_tokens} tokens atteinte"
                self.debug_info.emit(warning)
                logger.warning(warning)

                response_text += f"\n\n{'='*80}\n"
                response_text += f"⚠️ AVERTISSEMENT: La réponse a été tronquée car la limite de {max_tokens} tokens a été atteinte.\n"
                if not self.use_opus:
                    response_text += "💡 Conseil: Activez 'use_opus=True' pour obtenir jusqu'à 16K tokens (2x plus).\n"
                response_text += "Ou divisez votre demande en plusieurs parties plus petites.\n"
                response_text += f"{'='*80}"

            # Récupérer les vraies données d'utilisation
            usage = response.usage
            input_tokens = usage.input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0

            if usage:
                tokens_info = f"Tokens: {usage.input_tokens} entrée + {usage.output_tokens} sortie = {usage.input_tokens + usage.output_tokens} total"
                self.debug_info.emit(tokens_info)
                logger.info(f"📊 {tokens_info}")

            # Enregistrer l'usage dans la base de données
            if usage_tracker:
                usage_tracker.record_usage(
                    platform_name="Claude",
                    model_name=model_name,
                    success=True,
                    duration_seconds=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    context_length=sum(len(m['content']) for m in messages),
                    project_name=getattr(self, 'project_name', None),
                    session_type='coding'
                )

            # 🆕 Parser les snippets
            snippets = self._parse_snippets(response_text)
            
            # 🆕 Émettre chaque snippet individuellement
            for snippet in snippets:
                self.snippet_generated.emit(snippet)

            self.debug_info.emit(f"Réponse reçue: {len(response_text)} caractères, {len(snippets)} snippets")
            
            # 🆕 Retourner un dictionnaire avec snippets
            result = {
                'text': response_text,
                'snippets': snippets
            }
            
            self.test_completed.emit(True, "Code généré avec succès", duration, result)
            logger.info(f"✅ Claude request complétée ({duration:.2f}s, {usage.output_tokens if usage else '?'} tokens générés)")

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Erreur Claude: {str(e)}"
            logger.error(error_msg)

            if usage_tracker:
                usage_tracker.record_usage(
                    platform_name="Claude",
                    model_name="Claude Sonnet 4" if not getattr(self, 'use_opus', False) else "Claude Opus 4",
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
        """Parse la réponse pour extraire les snippets - VERSION CORRIGÉE"""
        snippets = []
    
        snippet_pattern = r'###\s*SNIPPET\s+\[([^\]]+)\]:\s*(.+?)(?:\n|$)'
        snippet_matches = list(re.finditer(snippet_pattern, response_text, re.IGNORECASE))
    
        for i, match in enumerate(snippet_matches):
            action = match.group(1).strip().upper()
            title = match.group(2).strip()
    
            start_pos = match.end()
            end_pos = snippet_matches[i + 1].start() if i + 1 < len(snippet_matches) else len(response_text)
            snippet_content = response_text[start_pos:end_pos]
    
            # 🔧 AMÉLIORATION: Extraction du fichier avec plusieurs patterns
            file_match = None
            
            # Pattern 1: **Fichier**: `path/to/file.py`
            file_match = re.search(r'\*\*Fichier\*\*:\s*`([^`]+)`', snippet_content)
            
            # Pattern 2: Fichier: path/to/file.py (sans backticks)
            if not file_match:
                file_match = re.search(r'\*\*Fichier\*\*:\s*([^\n]+?)(?:\n|\*\*)', snippet_content)
            
            # Pattern 3: Dans le titre ou la description
            if not file_match:
                file_match = re.search(
                    r'(?:dans|fichier|file)\s+[`"]?([a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css|json|txt))[`"]?',
                    snippet_content,
                    re.IGNORECASE
                )
    
            # Extraction de la cible
            target_match = re.search(r'\*\*(?:Classe/Fonction|Cible)\*\*:\s*`([^`]+)`', snippet_content)
            
            # Si pas trouvé, chercher sans backticks
            if not target_match:
                target_match = re.search(r'\*\*(?:Classe/Fonction|Cible)\*\*:\s*([^\n]+?)(?:\n|\*\*)', snippet_content)
    
            # Extraction de l'action
            action_match = re.search(r'\*\*Action\*\*:\s*(\w+)', snippet_content)
    
            # 🔧 AMÉLIORATION: Extraction de la description SANS les métadonnées
            desc_match = re.search(
                r'\*\*Description\*\*:\s*(.+?)(?=\n\n```|\n```|\*\*Fichier\*\*|\*\*Action\*\*|$)', 
                snippet_content, 
                re.DOTALL
            )
    
            code_match = re.search(r'```(\w+)?\n(.*?)```', snippet_content, re.DOTALL)
    
            # 🔧 NETTOYAGE: Description sans les métadonnées de fichier
            description = ""
            if desc_match:
                raw_desc = desc_match.group(1).strip()
                desc_lines = []
                for line in raw_desc.split('\n'):
                    line = line.strip()
                    # 🔧 IGNORER les lignes contenant des infos de fichier
                    if line and not any(marker in line.lower() for marker in [
                        '**fichier**', '**action**', '**cible**', '**classe',
                        'fichier:', 'file:', 'dans le fichier', 'in file'
                    ]):
                        # 🔧 NETTOYER les chemins de fichier dans la description
                        clean_line = re.sub(r'[a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css)', '', line)
                        clean_line = clean_line.strip()
                        if clean_line and not clean_line.startswith('**'):
                            desc_lines.append(clean_line)
                
                description = ' '.join(desc_lines)
    
            # 🔧 EXTRACTION: Nom de fichier propre
            file_name = "Non spécifié"
            if file_match:
                raw_file = file_match.group(1).strip()
                # Nettoyer les backticks, guillemets, etc.
                file_name = raw_file.strip('`\'"').strip()
    
            snippet = {
                'action': action_match.group(1).strip().upper() if action_match else action,
                'title': title,
                'file': file_name,  # 🔧 CORRECTION: Nom de fichier nettoyé
                'target': target_match.group(1).strip() if target_match else None,
                'description': description,  # 🔧 CORRECTION: Description sans métadonnées
                'code': code_match.group(2).strip() if code_match else "",
                'language': code_match.group(1).strip() if code_match and code_match.group(1) else "python",
                'order': i + 1
            }
    
            snippets.append(snippet)
            logger.debug(f"Snippet parsé: {snippet['action']} - {snippet['title']} ({snippet['file']})")
    
        if not snippets:
            logger.warning("Aucun snippet formaté trouvé, tentative de parsing alternatif")
            snippets = self._parse_legacy_format(response_text)
    
        return snippets

    def _build_messages_with_history(self, enriched_perimeter):
        """
        Construit les messages pour l'API avec l'historique de conversation

        Returns:
            Liste de messages formatés pour Claude
        """
        messages = []

        # 1️⃣ Si on a un historique, l'inclure d'abord
        if self.conversation_history and self.conversation_history.messages:
            # Récupérer les messages formatés pour Claude
            history_messages = self.conversation_history.get_messages_for_api('claude')
            messages.extend(history_messages)
            logger.info(f"📚 {len(history_messages)} messages d'historique chargés")

        # 2️⃣ Ajouter le nouveau message utilisateur avec le contexte actuel
        current_prompt = self._build_snippets_prompt(enriched_perimeter)

        # 🆕 Ajouter un préfixe si c'est une continuation
        if messages:
            continuation_prefix = (
                "📌 SUITE DE LA CONVERSATION\n\n"
                "Voici ma nouvelle demande qui fait suite à notre discussion précédente:\n\n"
            )
            current_prompt = continuation_prefix + current_prompt

        messages.append({
            'role': 'user',
            'content': current_prompt
        })

        # Enregistrer ce nouveau message dans l'historique
        if self.conversation_history:
            self.conversation_history.add_user_message(
                current_prompt,
                metadata={
                    'perimeter_items': len(enriched_perimeter),
                    'context_length': len(self.context)
                }
            )

        logger.info(f"💬 Messages construits: {len(messages)} total")
        return messages

    def _parse_legacy_format(self, response_text):
        """Parse l'ancien format de réponse - VERSION CORRIGÉE"""
        snippets = []
        code_blocks = re.finditer(r'```(\w+)?\n(.*?)```', response_text, re.DOTALL)

        for i, match in enumerate(code_blocks):
            language = match.group(1) or "python"
            code = match.group(2).strip()

            # Chercher le contexte AVANT le bloc de code
            context_start = max(0, match.start() - 500)  # 🔧 Augmenté à 500 chars
            context = response_text[context_start:match.start()]

            # 🔧 AMÉLIORATION: Patterns multiples pour détecter le fichier
            file_match = None

            # Pattern 1: Fichier avec extension claire
            file_match = re.search(
                r'(?:fichier|file|dans|in|modifier|update|ajouter|add)\s*[:`]?\s*([a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css|json|txt|md))',
                context,
                re.IGNORECASE
            )

            # Pattern 2: Chemin complet
            if not file_match:
                file_match = re.search(
                    r'([a-zA-Z0-9_\-]+/[a-zA-Z0-9_/\-\.]+\.(?:py|js|cpp|java|html|css))',
                    context,
                    re.IGNORECASE
                )

            # Pattern 3: Nom de fichier simple
            if not file_match:
                file_match = re.search(
                    r'\b([a-zA-Z0-9_\-]+\.(?:py|js|cpp|java|html|css))\b',
                    context,
                    re.IGNORECASE
                )

            # 🔧 EXTRACTION: Nom de fichier nettoyé
            file_name = "Non spécifié"
            if file_match:
                file_name = file_match.group(1).strip('`\'"').strip()

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
                
            # 🔧 AMÉLIORATION: Description nettoyée SANS le nom de fichier
            context_lines = [line.strip() for line in context.split('\n') if line.strip()]
            clean_desc_lines = []

            for line in context_lines[-3:]:
                # 🔧 IGNORER les lignes avec métadonnées ou noms de fichiers
                if not any(marker in line.lower() for marker in [
                    '**fichier**', '**action**', '```', 'snippet',
                    '.py', '.js', '.cpp', '.java', '.html', '.css'
                ]):
                    clean_desc_lines.append(line)

            description = ' '.join(clean_desc_lines) if clean_desc_lines else ""

            snippet = {
                'action': detected_action,
                'title': f"Snippet {i + 1}",
                'file': file_name,  # 🔧 CORRECTION: Nom de fichier extrait
                'target': None,
                'description': description[:200],  # 🔧 Description sans nom de fichier
                'code': code,
                'language': language,
                'order': i + 1
            }

            snippets.append(snippet)

        return snippets


    def _parse_legacy_format(self, response_text):
        """Parse l'ancien format de réponse - VERSION CORRIGÉE"""
        snippets = []
        code_blocks = re.finditer(r'```(\w+)?\n(.*?)```', response_text, re.DOTALL)
        
        for i, match in enumerate(code_blocks):
            language = match.group(1) or "python"
            code = match.group(2).strip()
            
            # Chercher le contexte AVANT le bloc de code (pas trop loin)
            context_start = max(0, match.start() - 300)
            context = response_text[context_start:match.start()]
            
            # 🔧 CORRECTION: Extraction propre du fichier
            file_match = re.search(
                r'(?:fichier|file|dans)\s*[:`]?\s*([^\s`\n]+\.(?:py|js|cpp|java|html|css))', 
                context, 
                re.IGNORECASE
            )
            
            # 🔧 CORRECTION: Détection de l'action sans pollution
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
                
            # 🔧 CORRECTION: Description nettoyée
            # Prendre seulement les 2-3 dernières lignes significatives
            context_lines = [line.strip() for line in context.split('\n') if line.strip()]
            clean_desc_lines = []
            
            for line in context_lines[-3:]:  # Seulement les 3 dernières lignes
                # Ignorer les lignes qui sont des métadonnées ou du bruit
                if not any(marker in line.lower() for marker in ['**fichier**', '**action**', '```', 'snippet']):
                    clean_desc_lines.append(line)
            
            description = ' '.join(clean_desc_lines) if clean_desc_lines else ""
            
            snippet = {
                'action': detected_action,
                'title': f"Snippet {i + 1}",
                'file': file_match.group(1) if file_match else "Non spécifié",
                'target': None,
                'description': description[:200],  # Limiter à 200 caractères
                'code': code,
                'language': language,
                'order': i + 1
            }
            
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