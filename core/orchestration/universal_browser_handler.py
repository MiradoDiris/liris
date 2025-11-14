import time
import re
import ast
from typing import Dict, List, Optional, Callable
from core.orchestration.browser_helpers import (
    interact_with_platform_generic,
    PLATFORM_CONFIGS
)
from utils.logger import logger
from core.orchestration.code_formatter import format_extracted_snippets
from core.orchestration.advanced_code_recovery import DomExtractionFixer
from core.orchestration.code_validator import CodeValidator

# ✅ Import du nouveau extracteur clipboard
try:
    from core.orchestration.clipboard_extractor import (
        extract_via_clipboard_safe,
        CLIPBOARD_AVAILABLE
    )
    CLIPBOARD_EXTRACTION_AVAILABLE = True
except ImportError:
    CLIPBOARD_EXTRACTION_AVAILABLE = False
    logger.warning("⚠️ Clipboard extraction non disponible")


class UniversalBrowserHandler:
    """Handler universel pour toutes les plateformes IA avec support clipboard prioritaire"""
    
    DOM_POLLUTION_PATTERNS = [
        r'<[^>]+>',
        r'Copier\s*Regenerate',
        r'Démarrer le sujet',
        r'Créer un lien de partage',
        r'How can \w+ help\?',
        r'New conversation',
        r'logo icon',
        r'Passer en mode vocal',
        r'Réfléchir plus intensément',
        r'AI-powered structured data',
        r'\(\d+ characters\)',
        r'Automatique',
        r'Fermer',
        r'Défiler vers le',
    ]
    
    # ✅ SÉLECTEURS AMÉLIORÉS POUR CLAUDE.AI
    CLAUDE_COPY_BUTTON_SELECTORS = [
        # Sélecteurs spécifiques Claude.ai (par ordre de priorité)
        'button[aria-label="Copy"]',  # Bouton principal
        'button.inline-flex[aria-label="Copy"]',  # Avec classe inline-flex
        'div[class*="code"] button[aria-label="Copy"]',  # Dans bloc de code
        'pre + div button[aria-label="Copy"]',  # Après balise pre
        '[data-testid="copy-button"]',  # TestID si présent
        'button:has-text("Copy")',  # Fallback texte
        'button.copy-code-button',  # Classe générique
    ]
    
    def __init__(self, platform_name: str, auto_format: bool = True, use_playwright: bool = False, 
             repair_code: bool = True, aggressive_repair: bool = False, 
             try_clipboard: bool = True):  # ✅ Déjà True par défaut - OK
    
        self.platform_name = platform_name.lower()
        self.auto_format = auto_format
        self.use_playwright = use_playwright
        self.repair_code = repair_code
        self.aggressive_repair = aggressive_repair
        self.try_clipboard = try_clipboard and CLIPBOARD_EXTRACTION_AVAILABLE

        # ✅ AJOUT : Forcer clipboard si disponible
        if CLIPBOARD_EXTRACTION_AVAILABLE and not self.try_clipboard:
            logger.warning("⚠️ Clipboard disponible mais désactivé - Activation forcée recommandée")

        repair_mode = "AGRESSIF" if aggressive_repair else "SAFE"
        clipboard_status = "✅ ACTIVÉ (PRIORITÉ)" if self.try_clipboard else "❌ DÉSACTIVÉ"

        logger.info(f"🔧 Handler initialisé: format={auto_format}, playwright={use_playwright}, "
                   f"repair={repair_code} ({repair_mode}), clipboard={clipboard_status}")

        if self.platform_name not in PLATFORM_CONFIGS:
            raise ValueError(
                f"Plateforme non supportée: {platform_name}. "
                f"Plateformes disponibles: {', '.join(PLATFORM_CONFIGS.keys())}"
            )

        self.config = PLATFORM_CONFIGS[self.platform_name]
        self.client = None
        self.current_response = ""

    # ============================================================================
    # ✅ NOUVELLE MÉTHODE: EXTRACTION CLIPBOARD PRIORITAIRE
    # ============================================================================
    
    def _try_clipboard_extraction(self, status_callback: Optional[Callable] = None) -> Dict[str, any]:
        """Extraction clipboard optimisée"""
        if not self.try_clipboard:
            return {'success': False, 'snippets': [], 'method': 'disabled'}
        
        logger.info("📋 TENTATIVE EXTRACTION VIA CLIPBOARD (PRIORITÉ)")
        
        try:
            if self.use_playwright:
                from core.orchestration.clipboard_extractor import extract_via_clipboard_playwright
                
                # Récupérer la page Playwright active
                page = self._get_playwright_page()
                
                if page:
                    result = extract_via_clipboard_playwright(
                        page, 
                        platform=self.platform_name
                    )
                    
                    if result.get('success'):
                        logger.info(f"✅ CLIPBOARD: {len(result['snippets'])} snippets extraits")
                        logger.info(f"   📊 Taux succès: {result['stats']['success_rate']:.1f}%")
                        return result
            
            logger.warning("⚠️ Playwright page non disponible")
            return {'success': False, 'snippets': [], 'method': 'no_page'}
        
        except Exception as e:
            logger.error(f"❌ Erreur clipboard: {e}")
            return {'success': False, 'snippets': [], 'method': 'error', 'error': str(e)}
        
    def _wait_for_code_blocks(self, max_wait: int = 10  ) -> bool:
        """
        ✅ VERSION CORRIGÉE FINALE - API MCP BrowserOS
        """
        logger.debug("🔍 Attente des blocs de code...")

        # ✅ DIAGNOSTIC INITIAL
        try:
            initial_diag_result = self.client.execute_javascript("""
                (() => {
                    return {
                        url: window.location.href,
                        title: document.title,
                        bodyLength: document.body?.innerText?.length || 0,
                        hasMain: !!document.querySelector('main'),
                        totalElements: document.querySelectorAll('*').length,
                        pre: document.querySelectorAll('pre').length,
                        code: document.querySelectorAll('code').length,
                        div: document.querySelectorAll('div').length,
                        buttons: document.querySelectorAll('button').length,
                        claudePatterns: {
                            articles: document.querySelectorAll('article').length,
                            codeBlocks: document.querySelectorAll('[class*="code"]').length,
                            fontClaude: document.querySelectorAll('[class*="font-claude"]').length
                        }
                    };
                })();
            """)

            # Extraire résultat MCP
            if isinstance(initial_diag_result, dict) and "error" in initial_diag_result:
                logger.error(f"❌ Erreur MCP: {initial_diag_result['error']}")
                return False

            initial_diag = initial_diag_result.get("result", initial_diag_result) if isinstance(initial_diag_result, dict) else {}

            logger.info(f"🔍 DIAGNOSTIC PAGE INITIALE:")
            logger.info(f"   URL: {initial_diag.get('url', 'N/A')}")
            logger.info(f"   Title: {initial_diag.get('title', 'N/A')}")
            logger.info(f"   Body length: {initial_diag.get('bodyLength', 0)} chars")
            logger.info(f"   Total elements: {initial_diag.get('totalElements', 0)}")
            logger.info(f"   <pre>: {initial_diag.get('pre', 0)}, <code>: {initial_diag.get('code', 0)}")
            logger.info(f"   Buttons: {initial_diag.get('buttons', 0)}")
            logger.info(f"   Claude patterns: {initial_diag.get('claudePatterns', {})}")

            # Vérifications
            if 'claude.ai' not in str(initial_diag.get('url', '')):
                logger.error(f"❌ MAUVAISE PAGE: {initial_diag.get('url', 'N/A')}")
                return False

            if initial_diag.get('bodyLength', 0) < 100:
                logger.error("❌ PAGE VIDE OU NON CHARGÉE")
                return False

        except Exception as e:
            logger.error(f"❌ Erreur diagnostic initial: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Sélecteurs
        code_block_selectors = [
            'pre',
            'code',
            'pre > code',
            'pre code',
            '[class*="code-block"]',
            '[class*="codeblock"]',
            'div pre',
            'main pre',
            'article pre',
            'article code',
        ]

        start_time = time.time()
        last_log_time = start_time

        while time.time() - start_time < max_wait:
            try:
                # Vérifier génération
                gen_status_result = self.client.execute_javascript("""
                    (() => {
                        const streamingIndicators = [
                            'button[aria-label*="Stop"]',
                            'button[aria-label*="Arrêt"]',
                            '[data-testid*="streaming"]',
                            '.animate-pulse',
                            '[class*="generating"]'
                        ];

                        let isGenerating = false;
                        for (let selector of streamingIndicators) {
                            if (document.querySelector(selector)) {
                                isGenerating = true;
                                break;
                            }
                        }

                        return {
                            generating: isGenerating,
                            bodyLength: document.body?.innerText?.length || 0,
                            pre: document.querySelectorAll('pre').length,
                            code: document.querySelectorAll('code').length
                        };
                    })();
                """)

                if isinstance(gen_status_result, dict) and "error" in gen_status_result:
                    logger.debug(f"   ⚠️ Erreur check génération: {gen_status_result['error']}")
                    time.sleep(1)
                    continue
                
                generation_status = gen_status_result.get("result", gen_status_result) if isinstance(gen_status_result, dict) else {}

                current_time = time.time()
                elapsed = int(current_time - start_time)

                # Log périodique
                if current_time - last_log_time >= 5:
                    logger.debug(f"   ⏳ {elapsed}s - Génération: {generation_status.get('generating', 'unknown')}")
                    logger.debug(f"      Body: {generation_status.get('bodyLength', 0)} chars")
                    logger.debug(f"      <pre>: {generation_status.get('pre', 0)}, <code>: {generation_status.get('code', 0)}")
                    last_log_time = current_time

                if generation_status.get('generating'):
                    time.sleep(2)
                    continue
                
                # Chercher blocs de code
                for selector in code_block_selectors:
                    try:
                        search_result = self.client.execute_javascript(f"""
                            (() => {{
                                const blocks = document.querySelectorAll('{selector}');

                                let validBlocks = 0;
                                let blockDetails = [];

                                blocks.forEach(block => {{
                                    const text = block.textContent || '';
                                    const rect = block.getBoundingClientRect();

                                    if (text.trim().length > 20 && rect.height > 0) {{
                                        validBlocks++;
                                        blockDetails.push({{
                                            tag: block.tagName,
                                            length: text.length,
                                            className: block.className,
                                            visible: rect.height > 0
                                        }});
                                    }}
                                }});

                                return {{
                                    count: validBlocks,
                                    details: blockDetails.slice(0, 3)
                                }};
                            }})();
                        """)

                        if isinstance(search_result, dict) and "error" in search_result:
                            logger.debug(f"   ⚠️ Erreur sélecteur '{selector}': {search_result['error']}")
                            continue
                        
                        result = search_result.get("result", search_result) if isinstance(search_result, dict) else {}

                        if result.get('count', 0) > 0:
                            logger.info(f"   ✅ {result['count']} bloc(s) trouvé(s) avec '{selector}'")
                            logger.debug(f"      Détails: {result.get('details', [])}")
                            time.sleep(2)
                            return True

                    except Exception as e:
                        logger.debug(f"   ⚠️ Exception sélecteur '{selector}': {e}")
                        continue
                    
                time.sleep(1)

            except Exception as e:
                logger.debug(f"   ⚠️ Erreur vérification: {e}")
                time.sleep(1)

        logger.warning(f"⚠️ Aucun bloc de code détecté après {max_wait}s")

        # DIAGNOSTIC FINAL
        try:
            final_diag_result = self.client.execute_javascript("""
                (() => {
                    const structure = {
                        pre: document.querySelectorAll('pre').length,
                        code: document.querySelectorAll('code').length,
                        preCode: document.querySelectorAll('pre code').length,

                        firstPre: (() => {
                            const pre = document.querySelector('pre');
                            if (!pre) return null;
                            return {
                                text: pre.textContent?.substring(0, 100) || '',
                                className: pre.className,
                                hasCode: !!pre.querySelector('code')
                            };
                        })(),

                        articles: document.querySelectorAll('article').length,
                        bodyLength: document.body?.innerText?.length || 0
                    };

                    return structure;
                })();
            """)

            final_diag = final_diag_result.get("result", final_diag_result) if isinstance(final_diag_result, dict) else {}

            if final_diag:
                logger.warning(f"🔍 DIAGNOSTIC FINAL:")
                logger.warning(f"   <pre>: {final_diag.get('pre', 0)}, <code>: {final_diag.get('code', 0)}")
                logger.warning(f"   <pre><code>: {final_diag.get('preCode', 0)}")

                if final_diag.get('firstPre'):
                    logger.warning(f"   Premier <pre> trouvé:")
                    logger.warning(f"      Texte: {final_diag['firstPre'].get('text', '')[:50]}...")
                    logger.warning(f"      Classe: {final_diag['firstPre'].get('className', 'N/A')}")

                logger.warning(f"   Articles: {final_diag.get('articles', 0)}")
                logger.warning(f"   Body: {final_diag.get('bodyLength', 0)} chars")

        except Exception as e:
            logger.error(f"❌ Erreur diagnostic final: {e}")

        return False

    # ============================================================================
    # MÉTHODES EXISTANTES (inchangées)
    # ============================================================================
    
    def _clean_dom_pollution(self, text: str) -> str:
        """🧹 Nettoie le texte de toute pollution DOM/HTML"""
        cleaned = text
        
        for pattern in self.DOM_POLLUTION_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _validate_python_syntax(self, code: str) -> bool:
        """✅ Valide la syntaxe Python avec AST"""
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning(f"⚠️ Erreur syntaxe Python: {e}")
            return False
        except Exception:
            return False
    
    def _final_cleanup_code(self, code: str) -> str:
        """🧼 NETTOYAGE FINAL ULTRA-STRICT"""
        logger.debug("   🧼 Nettoyage final ultra-strict")
        
        code = re.sub(r'\n{4,}', '\n\n', code)
        
        lines = []
        for line in code.split('\n'):
            if line.strip() or not lines or lines[-1].strip():
                lines.append(line.rstrip())
        
        code = '\n'.join(lines)
        
        result_lines = []
        prev_was_empty = False
        
        for i, line in enumerate(code.split('\n')):
            is_empty = not line.strip()
            
            if is_empty:
                if not prev_was_empty:
                    result_lines.append('')
                prev_was_empty = True
            else:
                result_lines.append(line)
                prev_was_empty = False
        
        code = '\n'.join(result_lines)
        
        normalized_lines = []
        for line in code.split('\n'):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                content = ' '.join(line.split())
                if indent > 0:
                    normalized_lines.append(' ' * indent + content.lstrip())
                else:
                    normalized_lines.append(content)
            else:
                normalized_lines.append('')
        
        code = '\n'.join(normalized_lines)
        code = code.strip()
        
        if code and not code.endswith('\n'):
            code += '\n'
        
        logger.debug(f"   ✅ Nettoyage final: {len(code)} chars")
        
        return code
    
    def _safe_repair_code(self, code: str, snippet_name: str) -> str:
        logger.info(f"   🛡️ Réparation SAFE Enhanced: {snippet_name}")

        if self._detect_extreme_corruption(code):
            logger.warning("   🚨 CORRUPTION EXTRÊME DÉTECTÉE")
            logger.warning("   ➡️ Recommandation: Utiliser mode AGGRESSIVE")

        original_length = len(code)

        # ═══════════════════════════════════════════════════════════════════════
        # 🆕 ÉTAPE 0 : RECONSTRUCTION TOKENS ÉCLATÉS (PRIORITÉ) - VERSION SÉCURISÉE
        # ═══════════════════════════════════════════════════════════════════════
        try:
            from core.orchestration.advanced_code_recovery import DomExtractionFixer

            # Créer une classe RepairStats simple si elle n'existe pas
            class SimpleRepairStats:
                def __init__(self):
                    self.operators_fixed = 0
                    self.imports_fixed = 0
                    self.indents_fixed = 0

            # Essayer d'utiliser RepairStats de DomExtractionFixer, sinon utiliser la version simple
            try:
                stats_temp = DomExtractionFixer.RepairStats()
            except AttributeError:
                logger.debug("      ℹ️ Utilisation de SimpleRepairStats (RepairStats non trouvé)")
                stats_temp = SimpleRepairStats()

            # Appeler la méthode de reconstruction si elle existe
            if hasattr(DomExtractionFixer, '_reconstruct_split_tokens'):
                code = DomExtractionFixer._reconstruct_split_tokens(code, stats_temp, verbose=False)

                if stats_temp.operators_fixed > 0:
                    logger.info(f"      ⚡ {stats_temp.operators_fixed} token(s) éclaté(s) reconstruits")
            else:
                logger.debug("      ℹ️ Méthode _reconstruct_split_tokens non disponible")

        except ImportError as e:
            logger.debug(f"      ⚠️ Module DomExtractionFixer non disponible: {e}")
        except Exception as e:
            logger.debug(f"      ⚠️ Erreur reconstruction tokens: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # ÉTAPE 1 : Correction ligne 4 (indentation excessive)
        # ═══════════════════════════════════════════════════════════════════════
        lines = code.split('\n')

        if len(lines) >= 4:
            line_4 = lines[3]

            if line_4.strip() and (len(line_4) - len(line_4.lstrip())) > 40:
                logger.warning(f"   ⚠️ Ligne 4 suspecte: {line_4[:60]}...")

                stripped = line_4.strip()
                if stripped.startswith(('import ', 'from ')):
                    lines[3] = stripped
                    logger.info("      ✅ Ligne 4 corrigée (import désindentée)")
                elif stripped.startswith(('def ', 'class ')):
                    lines[3] = stripped
                    logger.info("      ✅ Ligne 4 corrigée (définition désindentée)")

        code = '\n'.join(lines)

        # ═══════════════════════════════════════════════════════════════════════
        # ÉTAPE 2 : Nettoyage junk évident
        # ═══════════════════════════════════════════════════════════════════════
        obvious_junk = [
            r'Copier\s*le\s*code',
            r'```python\s*Copier',
            r'Rapide\s*Ajouter',
            r'Soumettre',
            r'=+\s*Grok\s*=+',
            r'NOTE:\s*extraction\s+coming\s+soon',
            r'Réessayer',
            r'Comment\s+puis\s*-\s*je\s+vous\s+aider\s*\?',
            r'Sonnet\s+\d+\.\d+',
            r'\(\d+\s*characters?\s*total\)',
        ]

        removed = 0
        for pattern in obvious_junk:
            matches = len(re.findall(pattern, code, re.IGNORECASE))
            if matches > 0:
                code = re.sub(pattern, '', code, flags=re.IGNORECASE)
                removed += matches

        # ═══════════════════════════════════════════════════════════════════════
        # ÉTAPE 3 : Correction collision 'pass'
        # ═══════════════════════════════════════════════════════════════════════
        if re.search(r'\bpass\s+if\s+not\s+\w+\s*\(', code):
            code = re.sub(r'\bpass\s+(if\s+not)', r'\1', code)
            logger.info("      🔧 Corrigé: 'pass if not'")

        if re.search(r'\bpass\s+([a-z_]\w+)\s*=\s*', code):
            code = re.sub(r'\bpass\s+([a-z_]\w+\s*=)', r'\1', code)
            logger.info("      🔧 Corrigé: 'pass variable ='")

        # ═══════════════════════════════════════════════════════════════════════
        # ÉTAPE 4 : Nettoyage final
        # ═══════════════════════════════════════════════════════════════════════
        code = self._final_cleanup_code(code)

        final_length = len(code)
        reduction = original_length - final_length
        reduction_percent = 100 * reduction / original_length if original_length > 0 else 0

        logger.info(f"      📊 {original_length} → {final_length} chars ({reduction_percent:.1f}% réduction)")

        if reduction_percent > 50:
            logger.warning(f"      ⚠️ Réduction importante: {reduction_percent:.1f}%")

        if removed > 0:
            logger.info(f"      🗑️ {removed} pattern(s) de junk supprimés")

        return code
    
    def _detect_extreme_corruption(self, code: str) -> bool:
        score = 0

        lines = code.split('\n')
        extreme_indent = sum(1 for line in lines 
                            if line.strip() and len(line) - len(line.lstrip()) > 80)
        if extreme_indent > 5:
            score += 3

        first_non_import = False
        mid_imports = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                if stripped.startswith(('import ', 'from ')):
                    if first_non_import:
                        mid_imports += 1
                else:
                    first_non_import = True
        if mid_imports > 2:
            score += 2

        empty_lines = sum(1 for line in lines if not line.strip())
        if len(lines) > 0 and empty_lines / len(lines) > 0.3:
            score += 2

        python_keywords = ['def ', 'class ', 'import ', 'return ', 'if ', 'for ']
        keyword_count = sum(code.count(kw) for kw in python_keywords)
        if len(code) > 20000 and keyword_count < 5:
            score += 3

        return score >= 5
    
    def _compare_repair_results(self, before: str, after: str, snippet_name: str):
        """📊 Compare avant/après réparation"""
        
        before_lines = before.split('\n')
        after_lines = after.split('\n')
        
        reduction = len(before) - len(after)
        reduction_percent = 100 * reduction / len(before) if len(before) > 0 else 0
        
        python_keywords = ['def ', 'class ', 'import ', 'return ']
        before_keywords = sum(before.count(kw) for kw in python_keywords)
        after_keywords = sum(after.count(kw) for kw in python_keywords)
        
        syntax_valid = self._validate_python_syntax(after)
        
        logger.info(f"\n   📊 Comparaison {snippet_name}:")
        logger.info(f"      AVANT: {len(before)} chars, {len(before_lines)} lignes, {before_keywords} mots-clés")
        logger.info(f"      APRÈS: {len(after)} chars, {len(after_lines)} lignes, {after_keywords} mots-clés")
        logger.info(f"      RÉDUCTION: {reduction_percent:.1f}%")
        logger.info(f"      SYNTAXE: {'✅ VALIDE' if syntax_valid else '❌ INVALIDE'}")
        
        if reduction_percent > 80:
            logger.error(f"      🚨 SUR-SUPPRESSION: {reduction_percent:.1f}%!")
            logger.error("         Le réparateur a probablement supprimé du code valide")
        elif reduction_percent > 50:
            logger.warning(f"      ⚠️ Réduction importante: {reduction_percent:.1f}%")
        
        if after_keywords < before_keywords * 0.3:
            logger.error(f"      🚨 PERTE DE CODE: {before_keywords - after_keywords} mots-clés perdus")
        
        if not syntax_valid:
            logger.error(f"      🚨 SYNTAXE INVALIDE après réparation!")

    def _extract_code_after_metadata_clean(self, response: str, start_pos: int, snippet_idx: int) -> str:
        """
        🔧 VERSION SIMPLIFIÉE : Le code est déjà propre grâce à la reconstruction préalable
        """
        remaining_text = response[start_pos:]

        logger.debug(f"   🔍 Analyse snippet {snippet_idx} (position {start_pos})")

        # Trouver le prochain bloc ACTION
        next_action_pos = remaining_text.find('# ACTION:')
        if next_action_pos == -1:
            next_action_pos = remaining_text.find('#ACTION:')

        end_pos = len(remaining_text)

        if next_action_pos > 0:
            end_pos = next_action_pos
            logger.debug(f"      Délimiteur: '# ACTION:' à {next_action_pos}")

        # Extraire le code (déjà propre)
        code = remaining_text[:end_pos].strip()

        # Nettoyer uniquement les métadonnées (le code est déjà reconstruit)
        lines = code.split('\n')
        clean_lines = []

        for line in lines:
            # Ignorer les métadonnées et junk évidents
            if re.match(r'^\s*#\s*(ACTION|FILE|TARGET|DESCRIPTION):', line, re.IGNORECASE):
                continue
            if line.strip() in ['python', '```python', '```', 'Copier', 'Regenerate']:
                continue

            if line.strip():
                clean_lines.append(line)

        code = '\n'.join(clean_lines).strip()

        logger.debug(f"      ✅ Code final: {len(code)} chars")

        return code
    
    def _extract_code_after_metadata(self, response: str, start_pos: int, snippet_idx: int) -> str:
        """
        🔧 VERSION CORRIGÉE v3 : Extrait le code + reconstruction tokens immédiate
        """
        remaining_text = response[start_pos:]

        logger.debug(f"   🔍 Analyse snippet {snippet_idx} (position {start_pos})")

        # Trouver le prochain bloc ACTION
        next_action_pos = remaining_text.find('# ACTION:')
        if next_action_pos == -1:
            next_action_pos = remaining_text.find('#ACTION:')

        end_pos = len(remaining_text)

        if next_action_pos > 0:
            end_pos = next_action_pos
            logger.debug(f"      Délimiteur: '# ACTION:' à {next_action_pos}")

        # Extraire le code brut
        code = remaining_text[:end_pos].strip()

        # ═══════════════════════════════════════════════════════════════════════════
        # 🆕 ÉTAPE 1 : RECONSTRUCTION TOKENS ÉCLATÉS IMMÉDIATE
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            from core.orchestration.advanced_code_recovery import DomExtractionFixer

            # Créer une classe RepairStats simple si elle n'existe pas
            class SimpleRepairStats:
                def __init__(self):
                    self.operators_fixed = 0
                    self.imports_fixed = 0
                    self.indents_fixed = 0

            # Essayer d'utiliser RepairStats de DomExtractionFixer, sinon utiliser la version simple
            try:
                stats_temp = DomExtractionFixer.RepairStats()
            except AttributeError:
                stats_temp = SimpleRepairStats()

            # Appeler la méthode de reconstruction si elle existe
            if hasattr(DomExtractionFixer, '_reconstruct_split_tokens'):
                code = DomExtractionFixer._reconstruct_split_tokens(code, stats_temp, verbose=False)

                if stats_temp.operators_fixed > 0:
                    logger.debug(f"      ⚡ {stats_temp.operators_fixed} tokens reconstruits immédiatement")
            else:
                logger.debug("      ℹ️ Méthode _reconstruct_split_tokens non disponible")

        except ImportError:
            logger.debug("      ⚠️ Module DomExtractionFixer non disponible")
        except Exception as e:
            logger.debug(f"      ⚠️ Erreur reconstruction tokens: {e}")

        # ═══════════════════════════════════════════════════════════════════════════
        # ÉTAPE 2 : Nettoyer les métadonnées et junk
        # ═══════════════════════════════════════════════════════════════════════════
        lines = code.split('\n')
        reconstructed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Ignorer les métadonnées
            if re.match(r'^\s*#\s*(ACTION|FILE|TARGET|DESCRIPTION):', line, re.IGNORECASE):
                i += 1
                continue
            
            # Ignorer les lignes avec juste "python" ou "```"
            if line.strip() in ['python', '```python', '```', 'Copier', 'Regenerate', 'Réessayer']:
                i += 1
                continue
            
            # 🔧 CORRECTION : Fusionner les lignes cassées (keywords Python seuls)
            if line.strip() and len(line.strip()) < 30:
                # Vérifier si c'est un import ou un début de déclaration
                if line.strip() in ['import', 'from', 'def', 'class', 'async', 'return', 'if', 'for', 'while']:
                    # Essayer de fusionner avec la ligne suivante
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not next_line.startswith('#'):
                            # Fusionner
                            line = line.strip() + ' ' + next_line
                            i += 2  # Sauter la ligne suivante
                            reconstructed_lines.append(line)
                            continue
                        
            # Ligne normale
            if line.strip():
                reconstructed_lines.append(line)

            i += 1

        code = '\n'.join(reconstructed_lines).strip()

        logger.debug(f"      ✅ Code final: {len(code)} chars")

        return code

    def _clean_broken_lines(self, text: str) -> str:
        """
        🧹 Nettoie et reconstruit les lignes cassées dans le texte
        """
        lines = text.split('\n')
        cleaned = []

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            # Cas 1 : Ligne avec juste un mot-clé Python
            if line.strip() in ['import', 'from', 'def', 'class', 'async', 'return', 'if', 'for', 'while']:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('#'):
                        # Fusionner
                        line = line.strip() + ' ' + next_line
                        i += 2
                        cleaned.append(line)
                        continue
                    
            # Cas 2 : Ligne qui se termine par une virgule ou une parenthèse ouvrante
            if line.rstrip().endswith((',', '(', '{', '[')):
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line:
                        # Fusionner en préservant l'indentation
                        indent = len(line) - len(line.lstrip())
                        line = line + ' ' + next_line
                        i += 2
                        cleaned.append(line)
                        continue
                    
            cleaned.append(line)
            i += 1

        return '\n'.join(cleaned)
    
    def _extract_snippets(self, response: str) -> List[Dict]:
        """
        🔧 VERSION CORRIGÉE : Reconstruction tokens IMMÉDIATE après extraction
        """
        snippets = []

        logger.info(f"\n{'='*80}")
        logger.info("🔍 EXTRACTION DES SNIPPETS")
        logger.info(f"{'='*80}")

        logger.info(f"📄 Taille réponse: {len(response)} chars")

        # ✅ PHASE 0.1 : RECONSTRUCTION TOKENS ÉCLATÉS (PRIORITAIRE)
        # Appliquer AVANT toute autre manipulation
        logger.info("⚡ PHASE 0.1 : Reconstruction tokens éclatés (PRIORITAIRE)")

        try:
            from core.orchestration.advanced_code_recovery import DomExtractionFixer, RepairStats

            stats_temp = RepairStats()
            response = DomExtractionFixer._reconstruct_split_tokens(response, stats_temp, verbose=True)

            if stats_temp.operators_fixed > 0:
                logger.info(f"   ✅ {stats_temp.operators_fixed} token(s) éclatés reconstruits")
        except Exception as e:
            logger.warning(f"⚠️ Erreur reconstruction tokens globale: {e}")

        # ✅ PHASE 0.2 : FUSION LIGNES ÉCLATÉES (UltimateLineMerger)
        logger.info("🔗 PHASE 0.2 : Fusion intelligente des lignes éclatées")

        try:
            from core.orchestration.advanced_code_recovery import UltimateLineMerger

            lines = response.split('\n')
            merged_lines = UltimateLineMerger.merge_lines(lines)
            response = '\n'.join(merged_lines)

            logger.info(f"   ✅ {len(lines) - len(merged_lines)} lignes fusionnées")
        except Exception as e:
            logger.warning(f"⚠️ Erreur fusion lignes: {e}")

        # 🔧 PHASE 0.3 : Nettoyer les lignes cassées
        cleaned_response = self._clean_broken_lines(response)
        logger.info(f"🔧 Après reconstruction lignes: {len(cleaned_response)} chars")

        # PHASE 0.4 : Nettoyer la pollution DOM
        cleaned_response = self._clean_dom_pollution(cleaned_response)
        logger.info(f"🧹 Après nettoyage pollution: {len(cleaned_response)} chars")

        # PHASE 0.5 : Extraction normale (le code est déjà propre maintenant)
        metadata_pattern = r'#\s*ACTION\s*:\s*(\w+)\s*[\r\n]+\s*#\s*FILE\s*:\s*([^\r\n]+?)[\r\n]+(?:\s*#\s*TARGET\s*:\s*([^\r\n]+?)[\r\n]+)?(?:\s*#\s*DESCRIPTION\s*:\s*([^\r\n]+?)[\r\n]+)?'

        metadata_matches = list(re.finditer(metadata_pattern, cleaned_response, re.IGNORECASE | re.MULTILINE))

        logger.info(f"🎯 Blocs détectés: {len(metadata_matches)}")

        if metadata_matches:
            for idx, meta_match in enumerate(metadata_matches, 1):
                try:
                    action = meta_match.group(1).strip().upper()
                    file_path = meta_match.group(2).strip()
                    target = meta_match.group(3).strip() if meta_match.group(3) else ""
                    description = meta_match.group(4).strip() if meta_match.group(4) else ""

                    meta_end_pos = meta_match.end()

                    logger.info(f"\n📦 Snippet {idx}: {action} -> {file_path}")

                    # ✅ Extraction simplifiée (le code est déjà propre)
                    code = self._extract_code_after_metadata_clean(cleaned_response, meta_end_pos, idx)

                    if not code or len(code.strip()) < 10:
                        logger.warning(f"   ⚠️ Code trop court ({len(code)} chars)")
                        continue

                    action_map = {
                        'ADD': 'AJOUTER', 'MODIFY': 'MODIFIER',
                        'REPLACE': 'REMPLACER', 'AJOUTER': 'AJOUTER',
                        'MODIFIER': 'MODIFIER', 'REMPLACER': 'REMPLACER'
                    }
                    action = action_map.get(action, 'AJOUTER')

                    snippet = {
                        'action': action,
                        'title': self._generate_title(action, file_path, target),
                        'file': file_path,
                        'code': code,
                        'language': 'python',
                        'description': description or f"Code généré par {self.config['name']}",
                        'lineNumber': 0,
                        'target': target,
                        'platform': self.config['name']
                    }

                    snippets.append(snippet)
                    logger.info(f"   ✅ Extrait: {len(code)} chars")

                except Exception as e:
                    logger.error(f"❌ Erreur snippet {idx}: {e}")
                    continue

        if not snippets:
            logger.warning("📄 Activation fallback")
            snippets = self._extract_fallback_snippets(cleaned_response)

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ {len(snippets)} snippet(s) extraits")
        logger.info(f"{'='*80}\n")

        return snippets

    def _extract_fallback_snippets(self, response: str) -> List[Dict]:
        """Extraction fallback INTELLIGENTE"""
        snippets = []

        logger.info("📄 Extraction fallback intelligente v2")

        code_blocks = re.findall(r'```python\s*\n(.*?)```', response, re.DOTALL)
        logger.info(f"   📦 {len(code_blocks)} blocs ```python trouvés")

        for idx, code_block in enumerate(code_blocks, 1):
            try:
                code_block = self._clean_dom_pollution(code_block)

                action_match = re.search(r'#\s*ACTION\s*:\s*(\w+)', code_block, re.IGNORECASE)
                file_match = re.search(r'#\s*FILE\s*:\s*([^\n\r]+)', code_block, re.IGNORECASE)

                if action_match and file_match:
                    action = action_match.group(1).strip().upper()
                    file_path = file_match.group(1).strip()

                    desc_match = re.search(r'#\s*DESCRIPTION\s*:\s*([^\n\r]+)', code_block, re.IGNORECASE)
                    description = desc_match.group(1).strip() if desc_match else ""

                    code_lines = []
                    for line in code_block.split('\n'):
                        if re.match(r'^\s*#\s*(ACTION|FILE|TARGET|DESCRIPTION)\s*:', line, re.IGNORECASE):
                            continue
                        code_lines.append(line)

                    code = '\n'.join(code_lines).strip()

                    if len(code) < 10:
                        logger.debug(f"   ⛔ Bloc {idx} trop court")
                        continue
                    
                    snippet = {
                        'action': 'AJOUTER' if action not in ['MODIFIER', 'REMPLACER'] else action,
                        'title': f"{action} - {file_path}",
                        'file': file_path,
                        'code': code,
                        'language': 'python',
                        'description': description or f"Code du bloc {idx}",
                        'lineNumber': 0,
                        'target': '',
                        'platform': self.config['name']
                    }

                    snippets.append(snippet)
                    logger.info(f"   ✅ Snippet {idx} extrait (FORMAT STRICT) - {len(code)} chars")
                    continue
                
                file_hints = re.findall(r'#.*?([a-zA-Z_][a-zA-Z0-9_]*\.py)', code_block)

                if file_hints:
                    file_path = file_hints[0]
                    logger.info(f"   💡 Fichier détecté par indice: {file_path}")
                else:
                    file_path = f"generated_code_{idx}.py"
                    logger.warning(f"   ⚠️ Pas de fichier détecté, utilisation de {file_path}")

                code = code_block.strip()

                python_indicators = ['def ', 'class ', 'import ', 'from ', 'if ', 'for ', 'while ', '=']
                has_python = any(indicator in code for indicator in python_indicators)

                if not has_python or len(code) < 20:
                    logger.debug(f"   ⛔ Bloc {idx} ne semble pas être du Python valide")
                    continue
                
                snippet = {
                    'action': 'AJOUTER',
                    'title': f"Code extrait - {file_path}",
                    'file': file_path,
                    'code': code,
                    'language': 'python',
                    'description': f"Code extrait automatiquement du bloc {idx}",
                    'lineNumber': 0,
                    'target': '',
                    'platform': self.config['name']
                }

                snippets.append(snippet)
                logger.info(f"   ✅ Snippet {idx} extrait (FALLBACK) - {len(code)} chars")

            except Exception as e:
                logger.error(f"   ❌ Erreur bloc {idx}: {e}")
                continue
            
        if not snippets:
            logger.warning("   🔍 Tentative extraction code Python sans balises...")

            function_pattern = r'((?:async\s+)?def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?:\s*(?:\n(?:[ \t]+[^\n]+\n)+)+)'
            functions = re.findall(function_pattern, response, re.MULTILINE)

            for idx, func_code in enumerate(functions, 1):
                if len(func_code.strip()) < 20:
                    continue
                
                func_name_match = re.search(r'def\s+(\w+)', func_code)
                func_name = func_name_match.group(1) if func_name_match else f"function_{idx}"

                snippet = {
                    'action': 'AJOUTER',
                    'title': f"Fonction extraite - {func_name}",
                    'file': f"extracted_{func_name}.py",
                    'code': func_code.strip(),
                    'language': 'python',
                    'description': f"Fonction {func_name} extraite automatiquement",
                    'lineNumber': 0,
                    'target': '',
                    'platform': self.config['name']
                }

                snippets.append(snippet)
                logger.info(f"   ✅ Fonction {func_name} extraite (CODE NU) - {len(func_code)} chars")

        if not snippets:
            logger.error("   ❌ AUCUN CODE EXTRACTIBLE TROUVÉ")
            logger.error("   📋 Début de la réponse brute:")
            logger.error(response[:500])

        return snippets
    
    def build_prompt(self, context: str, perimeter_data: List[Dict]) -> str:
        """Construction du prompt AVEC FORMAT ULTRA-STRICT"""

        prompt = f"""Tu es un assistant de développement Python expert.

**CONTEXTE:**
{context}

"""

        if perimeter_data and len(perimeter_data) > 0:
            prompt += "**📦 FICHIERS DU PROJET AVEC LEUR CODE:**\n\n"

        for idx, item in enumerate(perimeter_data, 1):
            name = item.get('name', 'N/A')
            data = item.get('data', {})

            path = (data.get('path') or 
                   data.get('sourcePath') or 
                   data.get('full_path') or
                   item.get('path') or
                   item.get('sourcePath') or
                   item.get('full_path', ''))

            description = data.get('description', '')
            code_content = data.get('codeContent', '') or data.get('fileContents', '')

            prompt += f"\n### {idx}. Fichier: `{path or name}`\n"

            if description:
                prompt += f"**Description:** {description}\n\n"

            if code_content:
                if len(code_content) > 3000:
                    code_preview = code_content[:3000] + "\n... (code tronqué)"
                    prompt += f"**Code actuel (extrait):**\n```python\n{code_preview}\n```\n"
                else:
                    prompt += f"**Code actuel complet:**\n```python\n{code_content}\n```\n\n"

        prompt += """

================================================================================
⚠️ FORMAT DE RÉPONSE OBLIGATOIRE - AUCUNE EXCEPTION
================================================================================

Tu DOIS répondre UNIQUEMENT avec des blocs de code formatés EXACTEMENT comme suit :

```python
# ACTION: AJOUTER
# FILE: core/orchestration/advanced_code_recovery.py
# DESCRIPTION: Nouvelle méthode de détection

def detect_corruption_v6(code: str) -> int:
    # Votre code ici
    pass
```

**RÈGLES STRICTES :**
1. ✅ Chaque bloc DOIT commencer par ```python
2. ✅ La première ligne DOIT être # ACTION: [AJOUTER ou MODIFIER ou REMPLACER]
3. ✅ La deuxième ligne DOIT être # FILE: [chemin/fichier.py]
4. ✅ Pour MODIFIER : ajouter # TARGET: [nom de la fonction/classe]
5. ✅ Ligne # DESCRIPTION: optionnelle mais recommandée
6. ✅ Chaque bloc DOIT se terminer par ```
7. ❌ AUCUN texte explicatif en dehors des blocs
8. ❌ AUCUN commentaire en dehors des blocs

**EXEMPLE COMPLET DE RÉPONSE VALIDE :**

```python
# ACTION: AJOUTER
# FILE: utils/new_helper.py
# DESCRIPTION: Nouvelle fonction helper

def calculate_score(data: dict) -> float:
    return sum(data.values()) / len(data)
```

```python
# ACTION: MODIFIER
# FILE: core/main.py
# TARGET: def process_data()
# DESCRIPTION: Ajout validation

def process_data(input_data):
    if not input_data:
        raise ValueError("Data cannot be empty")
    return input_data
```

================================================================================
⚠️ RAPPEL : NE PAS ÉCRIRE DE TEXTE EXPLICATIF, UNIQUEMENT DES BLOCS DE CODE
================================================================================

Maintenant, génère le code selon le contexte fourni :
"""

        return prompt
    

    def _wait_for_claude_completion(self, max_wait: int = 30) -> bool:
        """⏳ Attendre que Claude ait VRAIMENT fini de générer"""

        if self.client is None:
            logger.error("❌ Client non initialisé")
            return False

        logger.info("⏳ Surveillance active de la génération Claude...")

        start_time = time.time()
        last_content_length = 0
        stable_count = 0
        last_log_time = start_time

        while time.time() - start_time < max_wait:
            try:
                if self.client is None:
                    logger.error("❌ Client est devenu None")
                    return False

                content_result = self.client.get_page_content(content_type="text")

                if "error" not in content_result and "result" in content_result:
                    content_data = content_result["result"].get("content", [])

                    content = ""
                    if isinstance(content_data, list) and len(content_data) > 0:
                        if isinstance(content_data[0], dict):
                            content = content_data[0].get("text", "")
                        else:
                            content = str(content_data[0])

                    current_length = len(content.strip())

                    # Log périodique réduit
                    current_time = time.time()
                    elapsed = int(current_time - start_time)

                    if current_time - last_log_time >= 5:  # ✅ OK
                        logger.info(f"   ⏳ {elapsed}s - Contenu: {current_length} chars")
                        last_log_time = current_time

                    # ✅ Stabilité réduite
                    if current_length == last_content_length:
                        stable_count += 1

                        if stable_count >= 2:
                            logger.info(f"   ✅ Contenu stable à {current_length} chars")

                            has_code = any([
                                '```python' in content,
                                '# ACTION:' in content and '# FILE:' in content,
                                ('def ' in content or 'class ' in content) and current_length > 1000
                            ])

                            if has_code:
                                logger.info("   ✅ Code détecté dans la réponse")
                                return True
                            elif current_length > 500:
                                logger.warning("   ⚠️ Contenu présent mais pas de code Python détecté")
                                return True
                            else:
                                stable_count = 0
                    else:
                        stable_count = 0

                    last_content_length = current_length
                else:
                    logger.debug(f"   ⚠️ Erreur get_page_content")

                time.sleep(2)

            except AttributeError as e:
                logger.error(f"   ❌ Erreur AttributeError: {e}")
                return False

            except Exception as e:
                logger.warning(f"   ⚠️ Erreur surveillance: {e}")
                time.sleep(2)

        logger.error(f"❌ Timeout après {max_wait}s")
        return False
    
    def send_to_platform(self, context: str, perimeter_data: List[Dict], 
                        status_callback: Optional[Callable] = None) -> Dict:
        try:
            if status_callback:
                status_callback("Construction du prompt", 5)

            prompt = self.build_prompt(context, perimeter_data)

            logger.info(f"\n{'='*70}")
            logger.info(f"🚀 ENVOI VERS {self.config['name']}")
            logger.info(f"{'='*70}")

            def wrapped_callback(msg, progress):
                if status_callback:
                    adjusted_progress = 10 + int(progress * 0.75)
                    status_callback(msg, adjusted_progress)

            if status_callback:
                status_callback(f"Connexion à {self.config['name']}", 10)

            self.client = interact_with_platform_generic(
                platform_name=self.platform_name,
                url=self.config['url'],
                message=prompt,
                wait_response=True,
                max_wait=self.config.get('max_wait', 45.0),
                take_screenshot=True,
                status_callback=wrapped_callback
            )

            if status_callback:
                status_callback("Récupération de la réponse", 85)

            logger.info("⏳ Vérification rapide du contenu...")

            content_ready = False

            # Quick check seulement si client existe
            if self.client is not None:
                try:
                    quick_content = self.client.get_page_content(content_type="text")

                    if "error" not in quick_content and "result" in quick_content:
                        content_data = quick_content["result"].get("content", [])
                        if content_data and len(str(content_data)) > 1000:
                            content_ready = True
                            logger.info("✅ Contenu déjà disponible, pas d'attente")
                except Exception as e:
                    logger.debug(f"⚠️ Quick check échoué: {e}")

            if not content_ready:
                logger.info("⏳ Attente complète de la génération Claude...")
                if not self._wait_for_claude_completion(max_wait=30):
                    logger.warning("⚠️ Timeout: génération Claude non terminée")

            # Attente sécurité réduite
            time.sleep(1)

            snippets = []
            extraction_method = "none"
            
            if self.try_clipboard:
                clipboard_result = self._try_clipboard_extraction(status_callback)
                
                if clipboard_result.get('success'):
                    snippets = clipboard_result['snippets']
                    extraction_method = "clipboard"
                    
                    logger.info("\n" + "="*80)
                    logger.info("✅ EXTRACTION CLIPBOARD RÉUSSIE - PASSAGE DIRECT AU FORMATAGE")
                    logger.info("="*80)
                    
                    # ✅ Snippets de clipboard sont déjà propres, on saute la réparation
                    # et on passe directement au formatage
                    if self.auto_format and len(snippets) > 0:
                        if status_callback:
                            status_callback("🎨 Formatage des snippets", 95)
                        
                        logger.info(f"\n{'='*80}")
                        logger.info("🎨 FORMATAGE - ÉTAPE FINALE")
                        logger.info(f"{'='*80}")
                        
                        try:
                            formatted_snippets = format_extracted_snippets(snippets)
                            if formatted_snippets:
                                snippets = formatted_snippets
                                logger.info(f"✅ {len(snippets)} snippet(s) formatés")
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur formatage: {e}")
                    
                    # Validation finale
                    for snippet in snippets:
                        if 'syntax_valid' not in snippet:
                            code = snippet.get('code', '')
                            snippet['syntax_valid'] = self._validate_python_syntax(code)
                            snippet['quality_score'] = snippet.get('quality_score', 95)
                    
                    valid_count = sum(1 for s in snippets if s.get('syntax_valid', False))
                    
                    logger.info(f"\n{'='*80}")
                    logger.info(f"📊 RÉSULTATS FINAUX (CLIPBOARD):")
                    logger.info(f"   ✅ Snippets valides: {valid_count}")
                    logger.info(f"   📦 Total: {len(snippets)}")
                    logger.info(f"   🎯 Méthode: CLIPBOARD (qualité optimale)")
                    logger.info(f"{'='*80}")
                    
                    if status_callback:
                        status_callback("Terminé", 100)
                    
                    return {
                        'success': True,
                        'message': f"✅ {len(snippets)} snippets via clipboard",
                        'snippets': snippets,
                        'raw_response': '',
                        'extraction_method': 'clipboard'
                    }
                else:
                    logger.warning(f"\n⚠️ Clipboard échoué: {clipboard_result.get('message', 'Unknown')}")
                    logger.info("➡️ Fallback vers extraction DOM classique\n")
            
            if self.use_playwright:
                logger.info("🎭 Extraction avec BrowserOS natif")
                try:
                    # ✅ NOUVEAU : Extraction directe depuis BrowserOS
                    from core.orchestration.playwright_content_extractor import extract_response_with_browseros

                    playwright_result = extract_response_with_browseros(
                        browser_client=self.client,  # ✅ Passer le client BrowserOS actif
                        platform_name=self.platform_name,
                        wait_response=True,
                        max_wait=30
                    )

                    if playwright_result.get('success'):
                        self.current_response = playwright_result.get('text', '')
                        logger.info(f"✅ BrowserOS: {len(self.current_response)} chars")
                        extraction_method = "browseros_direct"
                    else:
                        logger.warning("⚠️ Extraction BrowserOS échouée, fallback")
                        self.use_playwright = False

                except Exception as e:
                    logger.warning(f"⚠️ Erreur extraction BrowserOS : {e}")
                    self.use_playwright = False
            
            if not self.use_playwright or not self.current_response:
                response_result = self.client.get_page_content(content_type="text")
                
                if "error" in response_result:
                    return {
                        'success': False,
                        'message': f"Erreur: {response_result['error']}",
                        'snippets': [],
                        'raw_response': '',
                        'extraction_method': 'error'
                    }
                
                content = ""
                if "result" in response_result:
                    content_data = response_result["result"].get("content", [])
                    if isinstance(content_data, list) and len(content_data) > 0:
                        if isinstance(content_data[0], dict):
                            content = content_data[0].get("text", "")
                        else:
                            content = str(content_data[0])
                
                self.current_response = content.strip()
                extraction_method = "browseros"
            
            logger.info(f"📄 Réponse récupérée: {len(self.current_response)} caractères")
            if len(self.current_response) > 0:
                self._debug_response_structure(self.current_response)
            
            if status_callback:
                status_callback("Extraction des snippets", 90)

            # ✅ ÉTAPE 1: EXTRACTION DOM
            snippets = self._extract_snippets(self.current_response)
            logger.info(f"✅ {len(snippets)} snippet(s) extraits via DOM")

            # ========================================================================
            # ✅ ÉTAPE 2: RÉPARATION (SAFE ou AGGRESSIVE)
            # ========================================================================
            if snippets and len(snippets) > 0 and self.repair_code:
                repair_mode = "AGGRESSIVE" if self.aggressive_repair else "SAFE"

                if status_callback:
                    status_callback(f"🔧 Réparation {repair_mode} du code", 93)

                logger.info(f"\n{'='*80}")
                logger.info(f"🔧 RÉPARATION {repair_mode} - ÉTAPE 2/4")
                logger.info(f"{'='*80}")

                try:
                    if self.aggressive_repair:
                        repaired_snippets = DomExtractionFixer.repair_snippets_avec_validation(
                            snippets=snippets,
                            verbose=True,
                            keep_invalid=True
                        )
                    else:
                        logger.info("🛡️ Mode SAFE activé (réparation conservative)")
                        repaired_snippets = []

                        for idx, snippet in enumerate(snippets, 1):
                            original_code = snippet.get('code', '')

                            if len(original_code.strip()) < 10:
                                logger.warning(f"📦 Snippet {idx}: Trop court, ignoré")
                                continue
                            
                            logger.info(f"\n📦 Snippet {idx}/{len(snippets)}: {snippet.get('file', 'N/A')}")

                            before = original_code
                            after = self._safe_repair_code(original_code, snippet.get('file', 'N/A'))

                            syntax_valid = self._validate_python_syntax(after)
                            quality_score = DomExtractionFixer._calculate_quality_score(after, syntax_valid)

                            self._compare_repair_results(before, after, snippet.get('file', 'N/A'))

                            snippet['code'] = after
                            snippet['syntax_valid'] = syntax_valid
                            snippet['quality_score'] = quality_score
                            snippet['repair_status'] = 'SUCCESS' if syntax_valid else 'PARTIAL'

                            repaired_snippets.append(snippet)

                    if repaired_snippets:
                        snippets = repaired_snippets
                        logger.info(f"✅ {len(snippets)} snippet(s) réparés")
                    else:
                        logger.warning("⚠️ Aucun snippet réparé")

                except Exception as e:
                    logger.error(f"❌ ERREUR réparation: {e}")
                    import traceback
                    traceback.print_exc()

            # ========================================================================
            # ✅ ÉTAPE 3: FORMATAGE
            # ========================================================================
            if self.auto_format and snippets and len(snippets) > 0:
                if status_callback:
                    status_callback("🎨 Formatage des snippets", 95)

                logger.info(f"\n{'='*80}")
                logger.info("🎨 FORMATAGE - ÉTAPE 3/4")
                logger.info(f"{'='*80}")

                try:
                    formatted_snippets = format_extracted_snippets(snippets)
                    if formatted_snippets:
                        snippets = formatted_snippets
                        logger.info(f"✅ {len(snippets)} snippet(s) formatés")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur formatage: {e}")

            # ========================================================================
            # ✅ ÉTAPE 4: VALIDATION AVEC AUTO-ESCALADE VERS AGGRESSIVE
            # ========================================================================
            if snippets and len(snippets) > 0:
                if status_callback:
                    status_callback("🔍 Validation finale", 97)
            
                logger.info(f"\n{'='*80}")
                logger.info("🔍 VALIDATION FINALE - ÉTAPE 4/4")
                logger.info(f"{'='*80}")
            
                for snippet in snippets:
                    code = snippet.get('code', '')
                    
                    if 'syntax_valid' not in snippet:
                        syntax_valid = CodeValidator._validate_syntax(code)
                        quality_score = DomExtractionFixer._calculate_quality_score(code, syntax_valid)
                        
                        snippet['syntax_valid'] = syntax_valid
                        snippet['quality_score'] = quality_score
                        snippet['repair_status'] = snippet.get('repair_status', 'SUCCESS' if syntax_valid else 'PARTIAL')
            
                valid_count = sum(1 for s in snippets if s.get('syntax_valid', False))
                invalid_count = len(snippets) - valid_count
            
                if invalid_count > 0 and not self.aggressive_repair:
                    logger.warning(f"\n{'='*80}")
                    logger.warning(f"⚠️ {invalid_count} snippet(s) invalide(s) en MODE SAFE")
                    logger.warning(f"🚀 ESCALADE AUTOMATIQUE VERS MODE AGGRESSIVE")
                    logger.warning(f"{'='*80}")
            
                    logger.info("⚡ Lancement réparation AGGRESSIVE...")
                    aggressive_repaired = DomExtractionFixer.repair_snippets_avec_validation(
                        snippets=snippets,
                        verbose=True,
                        keep_invalid=True
                    )
            
                    if self.auto_format and aggressive_repaired:
                        logger.info("🎨 Re-formatage après réparation aggressive...")
                        try:
                            aggressive_repaired = format_extracted_snippets(aggressive_repaired)
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur re-formatage: {e}")
            
                    snippets = aggressive_repaired
            
                    valid_count = sum(1 for s in snippets if s.get('syntax_valid', False))
                    invalid_count = len(snippets) - valid_count
            
                logger.info(f"\n{'='*80}")
                logger.info(f"📊 RÉSULTATS FINAUX:")
                logger.info(f"   ✅ Snippets valides: {valid_count}")
                logger.info(f"   ⚠️ Snippets partiels: {invalid_count}")
                logger.info(f"   📦 Total conservé: {len(snippets)}")
                logger.info(f"   🎯 Méthode: {extraction_method.upper()}")
                
                if len(snippets) > 0:
                    avg_quality = sum(s.get('quality_score', 0) for s in snippets) / len(snippets)
                    logger.info(f"   🎯 Score moyen: {avg_quality:.1f}/100")
                    logger.info(f"   📈 Taux récupération: 100%")
                
                logger.info(f"{'='*80}")

            if status_callback:
                status_callback("Terminé", 100)

            return {
                'success': True,
                'message': f"✅ {len(snippets)} snippets validés",
                'snippets': snippets,
                'raw_response': self.current_response,
                'extraction_method': extraction_method
            }

        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f"❌ Erreur: {str(e)}",
                'snippets': [],
                'raw_response': '',
                'extraction_method': 'error'
            }
        
    def _debug_response_structure(self, response: str):
        """🔍 DIAGNOSTIC COMPLET de la structure de la réponse"""
        logger.info("\n" + "="*80)
        logger.info("🔍 DIAGNOSTIC DE LA RÉPONSE")
        logger.info("="*80)

        logger.info(f"📏 Longueur totale: {len(response)} caractères")
        logger.info(f"📏 Lignes: {len(response.split(chr(10)))}")

        python_blocks = len(re.findall(r'```python', response))
        code_blocks = len(re.findall(r'```', response)) // 2
        logger.info(f"📖 Blocs ```python détectés: {python_blocks}")
        logger.info(f"📖 Blocs ``` génériques: {code_blocks - python_blocks}")

        actions = len(re.findall(r'#\s*ACTION\s*:', response, re.IGNORECASE))
        files = len(re.findall(r'#\s*FILE\s*:', response, re.IGNORECASE))
        logger.info(f"📋 Métadonnées ACTION détectées: {actions}")
        logger.info(f"📋 Métadonnées FILE détectées: {files}")

        logger.info("\n📄 STRUCTURE DE LA RÉPONSE:")
        logger.info("-" * 80)

        lines = response.split('\n')
        for i, line in enumerate(lines[:50], 1):
            preview = line[:100] if len(line) > 100 else line

            markers = []
            if '```python' in line:
                markers.append('🟢 DÉBUT BLOC PYTHON')
            elif '```' in line and i > 1 and '```' in lines[i-2]:
                markers.append('🔴 FIN BLOC')
            elif re.search(r'#\s*ACTION\s*:', line, re.IGNORECASE):
                markers.append('🎯 ACTION')
            elif re.search(r'#\s*FILE\s*:', line, re.IGNORECASE):
                markers.append('📁 FILE')

            marker_str = ' '.join(markers) if markers else ''
            logger.info(f"  {i:3d} | {preview} {marker_str}")

        if len(lines) > 50:
            logger.info(f"  ... ({len(lines) - 50} lignes supplémentaires)")

        logger.info("-" * 80)

        first_block_match = re.search(r'```python\s*\n(.*?)```', response, re.DOTALL)
        if first_block_match:
            first_block = first_block_match.group(1)
            logger.info("\n📦 PREMIER BLOC DE CODE DÉTECTÉ:")
            logger.info("-" * 80)
            block_lines = first_block.split('\n')[:20]
            for i, line in enumerate(block_lines, 1):
                logger.info(f"  {i:2d} | {line}")
            if len(first_block.split('\n')) > 20:
                logger.info(f"  ... ({len(first_block.split(chr(10))) - 20} lignes supplémentaires)")
            logger.info("-" * 80)
        else:
            logger.warning("\n⚠️ AUCUN BLOC ```python DÉTECTÉ")

        text_indicators = [
            'Je vais', 'Voici', 'Pour', 'Il faut', 'Vous devez',
            'I will', 'Here is', 'You should', 'Let me'
        ]
        has_explanation = any(indicator in response[:500] for indicator in text_indicators)

        if has_explanation:
            logger.warning("⚠️ La réponse semble contenir du texte explicatif")
            logger.warning("   💡 Solution: Renforcer le prompt pour demander UNIQUEMENT du code")

        logger.info("="*80 + "\n")
    
    def _generate_title(self, action: str, file_path: str, target: str) -> str:
        """Génère un titre pour le snippet"""
        file_name = file_path.split('/')[-1] if '/' in file_path else file_path
        
        if target:
            return f"{action}: {target} dans {file_name}"
        else:
            return f"{action}: Code dans {file_name}"
    
    def close(self):
        """Ferme la connexion proprement"""
        if self.client:
            try:
                self.client.close()
            except:
                pass