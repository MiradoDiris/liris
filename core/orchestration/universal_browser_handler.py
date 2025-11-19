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
        
    def _wait_for_code_blocks(self, max_wait: int = 10) -> bool:
        logger.info("⏳ Attente du contenu Claude.ai...")

        start_time = time.time()
        last_length = 0
        stable_count = 0

        while time.time() - start_time < max_wait:
            try:
                # ✅ APPROCHE MINIMALISTE : Juste vérifier la taille du body
                check_result = self.client.execute_javascript("""
                    (() => {
                        const body = document.body;
                        const text = body ? body.innerText : '';

                        // Indicateurs de génération active
                        const stopBtn = document.querySelector('button[aria-label*="Stop"], button[aria-label*="stop"]');
                        const isGenerating = stopBtn && stopBtn.offsetParent !== null;

                        return {
                            length: text.length,
                            generating: isGenerating,
                            hasContent: text.length > 5000
                        };
                    })();
                """)

                if isinstance(check_result, dict) and "error" not in check_result:
                    data = check_result.get("result", check_result)

                    current_length = data.get('length', 0)
                    is_generating = data.get('generating', False)
                    has_content = data.get('hasContent', False)

                    # Si génération en cours, attendre
                    if is_generating:
                        logger.debug(f"   🔄 Génération active... ({current_length} chars)")
                        time.sleep(2)
                        continue
                    
                    # Si contenu substantiel et stable
                    if has_content:
                        if current_length == last_length:
                            stable_count += 1
                            if stable_count >= 2:  # 4 secondes de stabilité
                                logger.info(f"   ✅ Contenu stable détecté ({current_length} chars)")
                                return True
                        else:
                            stable_count = 0

                        last_length = current_length

                    logger.debug(f"   ⏳ {int(time.time() - start_time)}s - {current_length} chars")

                time.sleep(2)

            except Exception as e:
                logger.debug(f"   ⚠️ Erreur vérification: {e}")
                time.sleep(2)

        logger.warning(f"⚠️ Timeout après {max_wait}s")
        return last_length > 5000

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

    def _extract_code_after_metadata(self, response: str, start_pos: int, snippet_idx: int) -> str:
        """
        🆕 Extraction du code après les métadonnées (VERSION FIXÉE)
        """
        remaining_text = response[start_pos:]

        logger.debug(f"   🔍 Extraction snippet {snippet_idx}")

        # Trouver la fin des métadonnées et le code
        lines = remaining_text.split('\n')

        # Phase 1 : Sauter les métadonnées
        code_start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Ligne de métadonnée
            if re.match(r'^#\s*(ACTION|FILE|TARGET|POSITION|DESCRIPTION):', stripped, re.IGNORECASE):
                code_start_idx = i + 1
                continue
            
            # Ligne vide
            if not stripped:
                continue
            
            # Début du code trouvé
            break
        
        # Phase 2 : Extraire le code jusqu'au prochain ACTION ou fin
        code_lines = []
        for i in range(code_start_idx, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # Arrêter au prochain ACTION
            if re.match(r'^#\s*ACTION\s*:', stripped, re.IGNORECASE):
                break
            
            # Ignorer artefacts UI
            if stripped in ['Comment puis-je vous aider ?', 'Sonnet 4.5', 
                           'Copier', 'Regenerate', 'Réessayer', 'python', 
                           '```python', '```']:
                continue
            
            # Arrêter aux caractères de fin
            if 'characters total' in stripped:
                break
            
            # Ajouter la ligne
            code_lines.append(line)

        code = '\n'.join(code_lines).strip()

        # Nettoyer espaces multiples
        code = re.sub(r'\n{3,}', '\n\n', code)

        logger.debug(f"      ✅ Code extrait: {len(code)} chars")

        return code
    
    def _extract_code_after(self, response: str, start_pos: int, snippet_idx: int) -> str:
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
    
    def _extract_content_universal_robust(self) -> str:
        logger.info("📄 Extraction universelle ROBUSTE...")

        # ============================================================
        # ÉTAPE 0 : DIAGNOSTIC DE LA TAILLE
        # ============================================================
        size_check = self.client.execute_javascript("""
            (() => {
                const body = document.body;
                if (!body) return { size: 0, complexity: 'empty' };

                const text = body.innerText || '';
                const codeBlocks = document.querySelectorAll('pre code, pre').length;
                const totalElements = document.querySelectorAll('*').length;

                let complexity = 'small';
                if (text.length > 50000 || totalElements > 5000) {
                    complexity = 'huge';
                } else if (text.length > 20000 || totalElements > 2000) {
                    complexity = 'large';
                } else if (text.length > 5000) {
                    complexity = 'medium';
                }

                return {
                    size: text.length,
                    codeBlocks: codeBlocks,
                    totalElements: totalElements,
                    complexity: complexity
                };
            })();
        """)

        if isinstance(size_check, dict) and "result" in size_check:
            info = size_check["result"]
            logger.info(f"   📊 Taille détectée: {info.get('size')} chars")
            logger.info(f"   🏗️  Complexité: {info.get('complexity')}")
            logger.info(f"   📦 Blocs de code: {info.get('codeBlocks')}")

            complexity = info.get('complexity', 'medium')
        else:
            complexity = 'medium'
            logger.warning("   ⚠️  Impossible de détecter la taille, mode medium")

        # ============================================================
        # ÉTAPE 1 : EXTRACTION ADAPTATIVE
        # ============================================================

        if complexity == 'huge':
            logger.info("   🔄 Mode HUGE : Extraction par chunks...")
            return self._extract_huge_content_by_chunks()

        elif complexity == 'large':
            logger.info("   📦 Mode LARGE : Extraction sélective...")
            return self._extract_large_content_selective()

        else:
            logger.info("   ⚡ Mode STANDARD : Extraction directe...")
            return self._extract_standard_content()
        
    def _extract_large_content_selective(self) -> str:
        logger.info("   📦 Extraction sélective des zones de code...")

        content = self.client.execute_javascript("""
            (() => {
                // Chercher le conteneur principal de conversation
                const mainSelectors = [
                    'main',
                    '[role="main"]',
                    'article',
                    '.conversation',
                    '[class*="conversation"]',
                    '[class*="messages"]'
                ];

                let mainContainer = null;
                for (let selector of mainSelectors) {
                    mainContainer = document.querySelector(selector);
                    if (mainContainer) break;
                }

                if (!mainContainer) {
                    mainContainer = document.body;
                }

                // Stratégie : Extraire SEULEMENT les zones avec code
                let extractedParts = [];

                // 1. Trouver tous les blocs de code
                const codeBlocks = mainContainer.querySelectorAll('pre code, pre, [class*="code-block"]');

                codeBlocks.forEach((codeBlock, idx) => {
                    // Récupérer le contexte autour du code (300 chars avant/après)
                    let parent = codeBlock.closest('div, article, section') || codeBlock.parentElement;

                    if (parent) {
                        let contextText = parent.innerText || parent.textContent || '';

                        // Chercher métadonnées ACTION/FILE autour
                        let beforeText = '';
                        let prev = parent.previousElementSibling;
                        let attempts = 0;

                        while (prev && attempts < 3) {
                            let prevText = prev.innerText || prev.textContent || '';
                            if (prevText.includes('ACTION:') || prevText.includes('FILE:')) {
                                beforeText = prevText + '\\n' + beforeText;
                                break;
                            }
                            if (prevText.length < 200) {
                                beforeText = prevText + '\\n' + beforeText;
                            }
                            prev = prev.previousElementSibling;
                            attempts++;
                        }

                        extractedParts.push(beforeText + contextText);
                    }
                });

                // 2. Si pas de blocs de code, prendre le texte principal
                if (extractedParts.length === 0) {
                    return mainContainer.innerText || mainContainer.textContent || '';
                }

                // Joindre avec séparateurs
                return extractedParts.join('\\n\\n=== BLOC_SUIVANT ===\\n\\n');
            })();
        """)

        if isinstance(content, dict):
            content = content.get("result", "")

        logger.info(f"   ✅ Extraction sélective: {len(content)} chars")

        return content
    
    def _extract_huge_content_by_chunks(self) -> str:
        logger.info("   🔄 Extraction par chunks (contenu énorme)...")

        chunks = []
        chunk_idx = 0
        max_chunks = 20  # Sécurité

        while chunk_idx < max_chunks:
            chunk_content = self.client.execute_javascript(f"""
                (() => {{
                    const chunkSize = 50;  // Nombre d'éléments par chunk
                    const startIdx = {chunk_idx * 50};

                    // Trouver tous les éléments avec du texte
                    const allElements = Array.from(document.querySelectorAll('pre, code, p, div'));

                    // Filtrer ceux avec du contenu substantiel
                    const contentElements = allElements.filter(el => {{
                        const text = el.innerText || el.textContent || '';
                        return text.trim().length > 50;
                    }});

                    // Prendre le chunk actuel
                    const chunk = contentElements.slice(startIdx, startIdx + chunkSize);

                    if (chunk.length === 0) {{
                        return {{ done: true, content: '' }};
                    }}

                    // Extraire le texte du chunk
                    const chunkText = chunk.map(el => el.innerText || el.textContent || '').join('\\n\\n');

                    return {{
                        done: chunk.length < chunkSize,
                        content: chunkText,
                        processed: startIdx + chunk.length
                    }};
                }})();
            """)

            if isinstance(chunk_content, dict):
                result = chunk_content.get("result", {})

                if result.get('done'):
                    if result.get('content'):
                        chunks.append(result['content'])
                    logger.info(f"   ✅ Extraction terminée après {chunk_idx + 1} chunks")
                    break
                
                if result.get('content'):
                    chunks.append(result['content'])
                    logger.info(f"   📦 Chunk {chunk_idx + 1}: {len(result['content'])} chars")

                chunk_idx += 1
            else:
                logger.warning(f"   ⚠️  Erreur chunk {chunk_idx}")
                break
            
            # Petite pause pour éviter surcharge
            time.sleep(0.1)

        full_content = '\n\n'.join(chunks)
        logger.info(f"   ✅ Total extrait: {len(full_content)} chars en {len(chunks)} chunks")

        return full_content
    
    def _extract_content_with_fallback(self) -> str:
        """
        Point d'entrée principal : Extraction avec fallback automatique
        """
        logger.info("📄 Extraction du contenu avec fallback...")

        try:
            # Essayer méthode robuste
            content = self._extract_content_universal_robust()

            if content and len(content) > 100:
                logger.info(f"   ✅ Extraction robuste réussie: {len(content)} chars")
                return content

            logger.warning("   ⚠️  Extraction robuste insuffisante, fallback...")

        except Exception as e:
            logger.error(f"   ❌ Erreur extraction robuste: {e}")

        # Fallback 1 : Méthode standard
        try:
            logger.info("   🔄 Fallback 1: Méthode standard...")
            content = self._extract_content_universal()

            if content and len(content) > 100:
                logger.info(f"   ✅ Fallback 1 réussi: {len(content)} chars")
                return content

        except Exception as e:
            logger.error(f"   ❌ Erreur fallback 1: {e}")

        # Fallback 2 : get_page_content
        try:
            logger.info("   🔄 Fallback 2: get_page_content...")
            response = self.client.get_page_content(content_type="text")

            if "error" not in response:
                content_data = response.get("result", {}).get("content", [])
                if isinstance(content_data, list) and len(content_data) > 0:
                    text = content_data[0].get("text", "") if isinstance(content_data[0], dict) else str(content_data[0])
                    if text and len(text) > 100:
                        logger.info(f"   ✅ Fallback 2 réussi: {len(text)} chars")
                        return text

        except Exception as e:
            logger.error(f"   ❌ Erreur fallback 2: {e}")

        logger.error("❌ Tous les fallbacks ont échoué")
        return ""
        
    def _extract_standard_content(self) -> str:
        """Extraction standard (< 20K chars)"""
        content = self.client.execute_javascript("""
            (() => {
                const body = document.body;
                if (!body) return '';

                const clone = body.cloneNode(true);

                // Supprimer éléments parasites
                const toRemove = clone.querySelectorAll(`
                    script, style, noscript,
                    button, [role="button"],
                    nav, header, footer,
                    [aria-hidden="true"],
                    [style*="display: none"],
                    [style*="visibility: hidden"]
                `);

                toRemove.forEach(el => el.remove());

                return clone.innerText || clone.textContent || '';
            })();
        """)

        if isinstance(content, dict):
            content = content.get("result", "")

        return content

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
        🔍 Extraction des snippets - VERSION CORRIGÉE
        Gère correctement les multiples snippets en découpant par segments
        """
        snippets = []

        logger.info(f"\n{'='*80}")
        logger.info("🔍 EXTRACTION DES SNIPPETS")
        logger.info(f"{'='*80}")
        logger.info(f"📄 Taille réponse: {len(response)} chars")

        # ================================================================
        # PHASE 0 : PRÉPARATION
        # ================================================================
        logger.info("⚡ PHASE 0.1 : Reconstruction tokens éclatés (PRIORITAIRE)")

        try:
            from core.orchestration.advanced_code_recovery import DomExtractionFixer

            class SimpleRepairStats:
                def __init__(self):
                    self.operators_fixed = 0
                    self.imports_fixed = 0
                    self.indents_fixed = 0

            try:
                stats_temp = DomExtractionFixer.RepairStats()
            except AttributeError:
                stats_temp = SimpleRepairStats()

            if hasattr(DomExtractionFixer, '_reconstruct_split_tokens'):
                response = DomExtractionFixer._reconstruct_split_tokens(response, stats_temp, verbose=False)

                if stats_temp.operators_fixed > 0:
                    logger.info(f"   ✅ {stats_temp.operators_fixed} token(s) éclatés reconstruits")

        except Exception as e:
            logger.warning(f"⚠️ Erreur reconstruction tokens: {e}")

        logger.info("🔗 PHASE 0.2 : Fusion intelligente des lignes éclatées")

        try:
            from core.orchestration.advanced_code_recovery import UltimateLineMerger

            lines = response.split('\n')
            merged_lines = UltimateLineMerger.merge_lines(lines)
            response = '\n'.join(merged_lines)

            logger.info(f"   ✅ {len(lines) - len(merged_lines)} lignes fusionnées")
        except Exception as e:
            logger.warning(f"⚠️ Erreur fusion lignes: {e}")

        cleaned_response = self._clean_broken_lines(response)
        logger.info(f"🔧 Après reconstruction lignes: {len(cleaned_response)} chars")

        cleaned_response = self._clean_dom_pollution(cleaned_response)
        logger.info(f"🧹 Après nettoyage pollution: {len(cleaned_response)} chars")

        # ================================================================
        # PHASE 1 : DÉTECTION DE TOUS LES BLOCS ACTION
        # ================================================================
        action_pattern = r'#\s*ACTION\s*:\s*(\w+)'
        action_matches = list(re.finditer(action_pattern, cleaned_response, re.IGNORECASE))

        logger.info(f"🎯 Blocs détectés: {len(action_matches)}")

        if not action_matches:
            logger.warning("📄 Aucun bloc ACTION détecté, activation fallback")
            return self._extract_fallback_snippets(cleaned_response)

        # ================================================================
        # PHASE 2 : EXTRACTION PAR SEGMENTS (CORRECTION PRINCIPALE)
        # ================================================================
        for idx, action_match in enumerate(action_matches, 1):
            try:
                action = action_match.group(1).strip().upper()

                # ✅ CORRECTION : Calculer les limites du segment
                segment_start = action_match.start()

                # Trouver la fin du segment (= début du prochain ACTION ou fin du texte)
                if idx < len(action_matches):
                    segment_end = action_matches[idx].start()  # Prochain ACTION
                else:
                    segment_end = len(cleaned_response)  # Fin du texte

                # Extraire le segment complet
                segment_text = cleaned_response[segment_start:segment_end]

                logger.info(f"\n📦 Snippet {idx}/{len(action_matches)}: {action}")
                logger.info(f"   📏 Segment: {len(segment_text)} chars")

                # ================================================================
                # PHASE 3 : EXTRACTION DES MÉTADONNÉES DU SEGMENT
                # ================================================================
                file_match = re.search(r'#\s*FILE\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                target_match = re.search(r'#\s*TARGET\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                position_match = re.search(r'#\s*POSITION\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                desc_match = re.search(r'#\s*DESCRIPTION\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)

                if not file_match:
                    logger.warning(f"   ⚠️ Pas de FILE détecté, snippet ignoré")
                    continue

                file_path = file_match.group(1).strip()
                target = target_match.group(1).strip() if target_match else ""
                position = position_match.group(1).strip().lower() if position_match else ""
                description = desc_match.group(1).strip() if desc_match else ""

                logger.info(f"   📁 FILE: {file_path}")
                if target:
                    logger.info(f"   🎯 TARGET: {target}")
                if position:
                    logger.info(f"   📍 POSITION: {position}")

                # ================================================================
                # PHASE 4 : EXTRACTION DU CODE DU SEGMENT
                # ================================================================
                code = self._extract_code_from_segment(segment_text, idx)

                if not code or len(code.strip()) < 10:
                    logger.warning(f"   ⚠️ Code trop court ({len(code)} chars)")
                    continue

                # Validation action
                action_map = {
                    'ADD': 'AJOUTER', 'MODIFY': 'MODIFIER',
                    'REPLACE': 'REMPLACER', 'AJOUTER': 'AJOUTER',
                    'MODIFIER': 'MODIFIER', 'REMPLACER': 'REMPLACER'
                }
                action = action_map.get(action, 'AJOUTER')

                # Validation position
                if position and position not in ['before', 'after', 'inside']:
                    logger.warning(f"   ⚠️ Position invalide '{position}', utilisation 'after'")
                    position = 'after'

                # ================================================================
                # PHASE 5 : CRÉATION DU SNIPPET
                # ================================================================
                snippet = {
                    'action': action,
                    'title': self._generate_title(action, file_path, target),
                    'file': file_path,
                    'code': code,
                    'language': 'python',
                    'description': description or f"Code généré par {self.config['name']}",
                    'lineNumber': 0,
                    'target': target,
                    'position': position,
                    'platform': self.config['name']
                }

                snippets.append(snippet)
                logger.info(f"   ✅ Extrait: {len(code)} chars")

            except Exception as e:
                logger.error(f"❌ Erreur snippet {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # ================================================================
        # FALLBACK SI AUCUN SNIPPET EXTRAIT
        # ================================================================
        if not snippets:
            logger.warning("📄 Activation fallback")
            snippets = self._extract_fallback_snippets(cleaned_response)

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ {len(snippets)} snippet(s) extraits")
        logger.info(f"{'='*80}\n")

        return snippets
    
    def _extract_code_from_segment(self, segment_text: str, snippet_idx: int) -> str:
        logger.debug(f"   🔍 Extraction code du segment {snippet_idx}")

        python_block_match = re.search(r'```python\s*\n(.*?)```', segment_text, re.DOTALL | re.IGNORECASE)

        if python_block_match:
            code = python_block_match.group(1).strip()
            logger.debug(f"      ✅ Code extrait via ```python : {len(code)} chars")
            return self._clean_code_artifacts(code)

        # ================================================================
        # MÉTHODE 2 : Extraire tout après les métadonnées
        # ================================================================
        lines = segment_text.split('\n')

        # Trouver la fin des métadonnées
        code_start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Ligne de métadonnée
            if re.match(r'^#\s*(ACTION|FILE|TARGET|POSITION|DESCRIPTION):', stripped, re.IGNORECASE):
                code_start_idx = i + 1
                continue
            
            # Ligne vide après métadonnées
            if not stripped:
                continue
            
            # Début du code trouvé
            break
        
        # Extraire le code
        code_lines = []
        for i in range(code_start_idx, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # Ignorer artefacts UI
            if stripped in ['Comment puis-je vous aider ?', 'Sonnet 4.5', 
                           'Copier', 'Regenerate', 'Réessayer', 'python', 
                           '```python', '```']:
                continue
            
            # Arrêter aux caractères de fin
            if 'characters total' in stripped:
                break
            
            code_lines.append(line)

        code = '\n'.join(code_lines).strip()

        # Nettoyer
        code = self._clean_code_artifacts(code)
        code = re.sub(r'\n{3,}', '\n\n', code)

        logger.debug(f"      ✅ Code extrait après métadonnées: {len(code)} chars")

        return code

    def _extract_content_universal(self) -> str:
        logger.info("📄 Extraction du contenu...")

        content = self.client.execute_javascript("""
            (() => {
                // Stratégie : Ignorer tout avant "# ACTION: AJOUTER"
                const body = document.body;
                if (!body) return '';

                let fullText = body.innerText || body.textContent || '';

                // Chercher le premier # ACTION: (début de la réponse Claude)
                const actionIndex = fullText.indexOf('# ACTION:');

                if (actionIndex > 0) {
                    // Prendre seulement à partir du premier ACTION
                    fullText = fullText.substring(actionIndex);
                    console.log('✅ Prompt utilisateur supprimé');
                }

                // Nettoyer les artefacts UI à la fin
                const endMarkers = [
                    'Comment puis-je vous aider ?',
                    'Sonnet 4.5',
                    '(caractères total)'
                ];

                for (let marker of endMarkers) {
                    const markerIndex = fullText.indexOf(marker);
                    if (markerIndex > 0) {
                        fullText = fullText.substring(0, markerIndex);
                    }
                }

                return fullText.trim();
            })();
        """)

        if isinstance(content, dict):
            content = content.get("result", "")

        if content and len(content) > 100:
            logger.info(f"   ✅ Extraction réussie: {len(content)} chars")
            return content

        # Fallback
        logger.warning("   ⚠️ Extraction JavaScript échouée, fallback...")

        response = self.client.get_page_content(content_type="text")
        if "error" not in response:
            content_data = response.get("result", {}).get("content", [])
            if isinstance(content_data, list) and len(content_data) > 0:
                text = content_data[0].get("text", "") if isinstance(content_data[0], dict) else str(content_data[0])

                # Nettoyer le prompt
                if "# ACTION:" in text:
                    text = text[text.index("# ACTION:"):]

                return text

        logger.error("❌ Échec extraction")
        return ""
    
    def _extract_claude_response_only(self) -> str:
        logger.info("📄 Extraction de la réponse de Claude uniquement...")

        result = self.client.execute_javascript("""
            (() => {
                // ============================================================
                // STRATÉGIE : Trouver les messages de l'ASSISTANT (Claude)
                // ============================================================

                // Sélecteurs pour les messages de Claude (assistant)
                const assistantSelectors = [
                    // Sélecteurs spécifiques Claude.ai
                    '[data-test-render-count]',  // Messages de Claude
                    '[class*="font-claude"]',    // Texte de Claude
                    'div[class*="prose"]',       // Contenu formaté

                    // Sélecteurs génériques assistant
                    '[role="assistant"]',
                    '[data-role="assistant"]',
                    '[class*="assistant"]',
                    '[class*="ai-message"]',
                    '[class*="bot-message"]'
                ];

                let assistantMessages = [];

                // Essayer chaque sélecteur
                for (let selector of assistantSelectors) {
                    const elements = document.querySelectorAll(selector);

                    if (elements.length > 0) {
                        console.log(`✅ Trouvé ${elements.length} éléments avec ${selector}`);

                        elements.forEach(el => {
                            // Vérifier que ce n'est pas un message utilisateur
                            const text = el.innerText || el.textContent || '';

                            // Ignorer si contient le prompt utilisateur
                            if (text.includes('Tu es un assistant de développement Python expert')) {
                                console.log('⏭️ Message utilisateur ignoré');
                                return;
                            }

                            // Ajouter si contient du code ou des mots-clés Python
                            if (text.includes('# ACTION:') || 
                                text.includes('def ') || 
                                text.includes('import ') ||
                                text.includes('```python')) {
                                assistantMessages.push(text);
                            }
                        });

                        // Si trouvé des messages, arrêter
                        if (assistantMessages.length > 0) {
                            break;
                        }
                    }
                }

                // ============================================================
                // FALLBACK 1 : Chercher tous les <pre> et <code>
                // ============================================================
                if (assistantMessages.length === 0) {
                    console.log('🔄 Fallback 1: Extraction <pre> et <code>');

                    const codeBlocks = document.querySelectorAll('pre, code');
                    const codeTexts = [];

                    codeBlocks.forEach(block => {
                        const text = block.innerText || block.textContent || '';
                        if (text.trim().length > 50) {
                            codeTexts.push(text);
                        }
                    });

                    if (codeTexts.length > 0) {
                        return {
                            success: true,
                            content: codeTexts.join('\\n\\n'),
                            method: 'code_blocks',
                            blocks: codeTexts.length
                        };
                    }
                }

                // ============================================================
                // FALLBACK 2 : Chercher le dernier grand bloc de texte
                // ============================================================
                if (assistantMessages.length === 0) {
                    console.log('🔄 Fallback 2: Dernier grand bloc');

                    // Trouver tous les éléments avec beaucoup de texte
                    const allElements = document.querySelectorAll('div, article, section');
                    let largestText = '';
                    let largestLength = 0;

                    allElements.forEach(el => {
                        const text = el.innerText || '';

                        // Ignorer si contient le prompt
                        if (text.includes('Tu es un assistant')) {
                            return;
                        }

                        // Garder le plus grand
                        if (text.length > largestLength && text.length > 1000) {
                            largestLength = text.length;
                            largestText = text;
                        }
                    });

                    if (largestText) {
                        return {
                            success: true,
                            content: largestText,
                            method: 'largest_block',
                            length: largestLength
                        };
                    }
                }

                // ============================================================
                // RETOUR
                // ============================================================
                if (assistantMessages.length > 0) {
                    return {
                        success: true,
                        content: assistantMessages.join('\\n\\n'),
                        method: 'assistant_messages',
                        messages: assistantMessages.length
                    };
                }

                return {
                    success: false,
                    error: 'Aucun message assistant trouvé'
                };
            })();
        """)

        if isinstance(result, dict) and "result" in result:
            data = result["result"]

            if data.get("success"):
                content = data.get("content", "")
                method = data.get("method", 'unknown')

                logger.info(f"   ✅ Extraction réussie via {method}")
                logger.info(f"   📊 Contenu: {len(content)} chars")

                # Vérification que ce n'est pas le prompt
                if "Tu es un assistant de développement Python expert" in content:
                    logger.warning("   ⚠️ Contenu contient le prompt, nettoyage...")

                    # Essayer de séparer
                    parts = content.split("=" * 20)  # Split sur les séparateurs

                    for part in reversed(parts):  # Partir de la fin
                        if "# ACTION:" in part or "def " in part:
                            logger.info("   ✅ Partie réponse détectée")
                            return part.strip()

                return content

            else:
                logger.error(f"   ❌ Erreur: {data.get('error')}")

        logger.error("❌ Échec extraction réponse Claude")
        return ""

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
        """Construction du prompt AVEC FORMAT ULTRA-STRICT + POSITION"""

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

    **🆕 POUR AJOUTER DU NOUVEAU CODE (ACTION: AJOUTER) :**

    ```python
    # ACTION: AJOUTER
    # FILE: core/orchestration/advanced_code_recovery.py
    # TARGET: def detect_corruption_v5()
    # POSITION: after
    # DESCRIPTION: Nouvelle méthode de détection améliorée

    def detect_corruption_v6(code: str) -> int:
        # Votre code ici
        score = 0
        # ... implémentation
        return score
    ```

    **🚨 RÈGLES ABSOLUES POUR ACTION: AJOUTER :**

    1. ✅ Si vous ajoutez du code DANS UN CONTEXTE EXISTANT :
       - Vous DEVEZ fournir # TARGET: (fonction/classe de référence)
       - Vous DEVEZ fournir # POSITION: (before/after/inside)

    2. ✅ Si vous créez un NOUVEAU FICHIER ou ajoutez au DÉBUT :
       - Omettez TARGET et POSITION
       - Le code sera inséré à la ligne 0

    **❌ CAS INVALIDES (seront rejetés) :**
    ```python
    # ACTION: AJOUTER
    # FILE: utils.py
    # ❌ MANQUE TARGET + POSITION

    def new_function():
        pass
    ```

    **✅ CAS VALIDES :**
    ```python
    # ACTION: AJOUTER
    # FILE: utils.py
    # TARGET: def existing_function()
    # POSITION: after

    def new_function():
        pass
    ```

    OU (pour début de fichier) :
    ```python
    # ACTION: AJOUTER
    # FILE: new_module.py
    # DESCRIPTION: Nouveau module

    # Imports
    import os

    **⚡ POUR MODIFIER/REMPLACER DU CODE EXISTANT :**

    ```python
    # ACTION: MODIFIER
    # FILE: core/main.py
    # TARGET: def process_data()
    # DESCRIPTION: Ajout validation des données

    def process_data(input_data):
        # ✅ NOUVEAU CODE COMPLET de la fonction
        if not input_data:
            raise ValueError("Data cannot be empty")

        # Traitement...
        return processed_data
    ```

    **RÈGLES POUR ACTION: MODIFIER :**
    1. ✅ # ACTION: MODIFIER ou REMPLACER
    2. ✅ # FILE: [chemin/fichier.py] (OBLIGATOIRE)
    3. ✅ # TARGET: [signature de la fonction/classe À REMPLACER] (OBLIGATOIRE)
       - Doit être la signature EXACTE : def ma_fonction(arg1, arg2):
    4. ✅ Fournir le code COMPLET de remplacement (pas de "...")

    ================================================================================
    ⚠️ EXEMPLES COMPLETS
    ================================================================================

    **Exemple 1 : AJOUTER une fonction APRÈS une fonction existante**
    ```python
    # ACTION: AJOUTER
    # FILE: utils/helpers.py
    # TARGET: def calculate_score(data)
    # POSITION: after
    # DESCRIPTION: Nouvelle fonction de validation

    def validate_score(score: float) -> bool:
        return 0 <= score <= 100
    ```

    **Exemple 2 : AJOUTER une méthode DANS une classe**
    ```python
    # ACTION: AJOUTER
    # FILE: core/models.py
    # TARGET: class DataProcessor
    # POSITION: inside
    # DESCRIPTION: Nouvelle méthode de nettoyage

    def clean_data(self, data: dict) -> dict:
        cleaned = {k: v for k, v in data.items() if v is not None}
        return cleaned
    ```

    **Exemple 3 : AJOUTER une fonction au DÉBUT du fichier**
    ```python
    # ACTION: AJOUTER
    # FILE: utils/constants.py
    # DESCRIPTION: Nouvelles constantes

    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    ```

    **Exemple 4 : MODIFIER une fonction existante**
    ```python
    # ACTION: MODIFIER
    # FILE: core/processor.py
    # TARGET: def process_data(input_data)
    # DESCRIPTION: Ajout validation et logging

    def process_data(input_data):
        # Validation
        if not input_data:
            raise ValueError("Input cannot be empty")

        # Logging
        logger.info(f"Processing {len(input_data)} items")

        # Traitement
        result = [item.upper() for item in input_data]
        return result
    ```

    ================================================================================
    ⚠️ RAPPELS CRITIQUES
    ================================================================================

    1. ❌ NE PAS écrire de texte explicatif en dehors des blocs de code
    2. ✅ TOUJOURS fournir TARGET + POSITION pour ACTION: AJOUTER (sauf ajout début fichier)
    3. ✅ TOUJOURS fournir TARGET exact pour ACTION: MODIFIER
    4. ✅ Générer le code COMPLET (pas de "..." ou "# reste du code")
    5. ✅ Utiliser des noms de fonctions/classes EXACTS (copier depuis le contexte fourni)
    6. Tous le fonction et methode doit etre separer dans des snippet differente pour faciliter

    ================================================================================
    Maintenant, génère le code selon le contexte fourni :
    """

        return prompt

    def _wait_for_complete_generation(self, max_wait: int = 60, stability_threshold: int = 3) -> bool:
        """
        ✅ FONCTION AMÉLIORÉE : Attente intelligente de la fin complète de génération

        Stratégie multi-niveaux :
        1. Détection indicateurs de streaming actif
        2. Surveillance croissance du contenu
        3. Vérification présence de code complet
        4. Validation stabilité sur plusieurs cycles

        Args:
            max_wait: Temps maximum d'attente en secondes
            stability_threshold: Nombre de vérifications stables requises

        Returns:
            bool: True si génération complète détectée, False si timeout
        """
        if self.client is None:
            logger.error("❌ Client non initialisé")
            return False

        logger.info("🎯 Surveillance intelligente de la génération...")
        logger.info(f"   ⏱️  Timeout: {max_wait}s | Seuil stabilité: {stability_threshold}")

        start_time = time.time()
        last_content_length = 0
        last_code_blocks = 0
        stability_count = 0
        check_interval = 2  # Intervalle entre vérifications
        last_log_time = start_time

        # Compteurs pour diagnostics
        checks_done = 0
        generation_detected = False

        while time.time() - start_time < max_wait:
            try:
                checks_done += 1
                current_time = time.time()
                elapsed = int(current_time - start_time)

                # ============================================================
                # ÉTAPE 1 : Vérifier si génération toujours active
                # ============================================================
                streaming_check_result = self.client.execute_javascript("""
                    (() => {
                        // Indicateurs de génération active
                        const streamingSelectors = [
                            'button[aria-label*="Stop"]',
                            'button[aria-label*="Arrêt"]',
                            'button[aria-label*="stop"]',
                            '[data-testid*="streaming"]',
                            '[data-testid*="stop"]',
                            '.animate-pulse',
                            '[class*="generating"]',
                            '[class*="streaming"]',
                            '[class*="loading"]',
                            'svg.animate-spin'  // Spinner
                        ];

                        let isGenerating = false;
                        let activeIndicator = null;

                        for (let selector of streamingSelectors) {
                            const element = document.querySelector(selector);
                            if (element && element.offsetParent !== null) {  // Visible
                                isGenerating = true;
                                activeIndicator = selector;
                                break;
                            }
                        }

                        // Vérifier aussi les boutons "Stop" spécifiques
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            const text = btn.textContent?.toLowerCase() || '';
                            const label = btn.getAttribute('aria-label')?.toLowerCase() || '';
                            if ((text.includes('stop') || text.includes('arrêt') || 
                                 label.includes('stop') || label.includes('arrêt')) &&
                                btn.offsetParent !== null) {
                                isGenerating = true;
                                activeIndicator = 'button:stop';
                                break;
                            }
                        }

                        return {
                            isGenerating: isGenerating,
                            indicator: activeIndicator,y
                            timestamp: Date.now()
                        };
                    })();
                """)

                if isinstance(streaming_check_result, dict) and "error" not in streaming_check_result:
                    streaming_status = streaming_check_result.get("result", streaming_check_result)
                    is_generating = streaming_status.get('isGenerating', False)

                    if is_generating:
                        indicator = streaming_status.get('indicator', 'unknown')
                        if not generation_detected:
                            logger.info(f"   🔄 Génération active détectée (indicateur: {indicator})")
                            generation_detected = True

                        # Reset stabilité si génération détectée
                        stability_count = 0
                        last_content_length = 0

                        # Log périodique pendant génération
                        if current_time - last_log_time >= 5:
                            logger.info(f"   ⏳ {elapsed}s - Génération en cours...")
                            last_log_time = current_time

                        time.sleep(check_interval)
                        continue
                    
                # ============================================================
                # ÉTAPE 2 : Analyser le contenu actuel
                # ============================================================
                content_analysis_result = self.client.execute_javascript("""
                    (() => {
                        // Récupérer le contenu principal
                        const mainSelectors = [
                            'main',
                            '[role="main"]',
                            'article',
                            '.conversation',
                            '#chat-content'
                        ];

                        let mainContent = null;
                        for (let selector of mainSelectors) {
                            mainContent = document.querySelector(selector);
                            if (mainContent) break;
                        }

                        if (!mainContent) {
                            mainContent = document.body;
                        }

                        const fullText = mainContent.innerText || '';

                        // Compter blocs de code
                        const codeBlockSelectors = [
                            'pre code',
                            'pre',
                            '[class*="code-block"]',
                            '[class*="codeblock"]'
                        ];

                        let totalCodeBlocks = 0;
                        let codeBlocksWithContent = 0;

                        for (let selector of codeBlockSelectors) {
                            const blocks = mainContent.querySelectorAll(selector);
                            blocks.forEach(block => {
                                const text = block.textContent || '';
                                if (text.trim().length > 20) {
                                    totalCodeBlocks++;
                                    if (text.length > 100) {
                                        codeBlocksWithContent++;
                                    }
                                }
                            });
                        }

                        // Rechercher métadonnées de snippets
                        const hasActionMetadata = /# ACTION:/i.test(fullText);
                        const hasFileMetadata = /# FILE:/i.test(fullText);
                        const actionCount = (fullText.match(/# ACTION:/gi) || []).length;

                        // Détecter patterns Python
                        const pythonPatterns = [
                            /\bdef\s+\w+\s*\(/g,
                            /\bclass\s+\w+/g,
                            /\bimport\s+\w+/g,
                            /\bfrom\s+\w+\s+import/g
                        ];

                        let pythonPatternCount = 0;
                        pythonPatterns.forEach(pattern => {
                            const matches = fullText.match(pattern);
                            if (matches) pythonPatternCount += matches.length;
                        });

                        return {
                            contentLength: fullText.length,
                            totalCodeBlocks: totalCodeBlocks,
                            substantialCodeBlocks: codeBlocksWithContent,
                            hasMetadata: hasActionMetadata && hasFileMetadata,
                            actionCount: actionCount,
                            pythonPatternCount: pythonPatternCount,
                            hasSubstantialContent: fullText.length > 1000,
                            timestamp: Date.now()
                        };
                    })();
                """)

                if isinstance(content_analysis_result, dict) and "error" not in content_analysis_result:
                    content_data = content_analysis_result.get("result", content_analysis_result)

                    current_length = content_data.get('contentLength', 0)
                    current_code_blocks = content_data.get('substantialCodeBlocks', 0)
                    has_metadata = content_data.get('hasMetadata', False)
                    action_count = content_data.get('actionCount', 0)
                    python_patterns = content_data.get('pythonPatternCount', 0)

                    # Log périodique détaillé
                    if current_time - last_log_time >= 5:
                        logger.info(f"   📊 {elapsed}s - Contenu: {current_length} chars, "
                                  f"Blocs: {current_code_blocks}, Actions: {action_count}, "
                                  f"Patterns Python: {python_patterns}")
                        last_log_time = current_time

                    # ============================================================
                    # ÉTAPE 3 : Vérifier stabilité du contenu
                    # ============================================================
                    content_stable = (current_length == last_content_length)
                    code_blocks_stable = (current_code_blocks == last_code_blocks)

                    if content_stable and code_blocks_stable:
                        stability_count += 1

                        logger.debug(f"   ✓ Stabilité {stability_count}/{stability_threshold}")

                        # ========================================================
                        # ÉTAPE 4 : Validation complétude si stabilité atteinte
                        # ========================================================
                        if stability_count >= stability_threshold:
                            logger.info(f"   🎯 Contenu stable sur {stability_threshold} vérifications")

                            # Critères de complétude
                            has_content = current_length > 500
                            has_code = current_code_blocks > 0 or python_patterns > 0
                            has_structured_response = has_metadata or action_count > 0

                            logger.info(f"   📋 Validation complétude:")
                            logger.info(f"      - Contenu suffisant: {has_content} ({current_length} chars)")
                            logger.info(f"      - Code présent: {has_code} ({current_code_blocks} blocs, {python_patterns} patterns)")
                            logger.info(f"      - Structure détectée: {has_structured_response} ({action_count} actions)")

                            if has_content and (has_code or has_structured_response):
                                logger.info("   ✅ Génération complète confirmée")
                                return True
                            elif has_content:
                                logger.warning("   ⚠️ Contenu présent mais structure incomplète")
                                logger.warning("      Attente supplémentaire...")
                                stability_count = 0  # Reset pour réessayer
                            else:
                                logger.warning("   ⚠️ Contenu insuffisant, poursuite surveillance")
                                stability_count = 0
                    else:
                        # Contenu en changement
                        stability_count = 0

                        # Détecter croissance significative
                        growth = current_length - last_content_length
                        if growth > 100:
                            logger.debug(f"   📈 Croissance: +{growth} chars")

                    last_content_length = current_length
                    last_code_blocks = current_code_blocks

                time.sleep(check_interval)

            except AttributeError as e:
                logger.error(f"   ❌ Erreur AttributeError: {e}")
                return False
            except Exception as e:
                logger.warning(f"   ⚠️ Erreur vérification: {e}")
                time.sleep(check_interval)

        # ====================================================================
        # TIMEOUT : Diagnostic final
        # ====================================================================
        logger.error(f"❌ Timeout après {max_wait}s ({checks_done} vérifications)")
        logger.error(f"   État final: {last_content_length} chars, {last_code_blocks} blocs")
        logger.error(f"   Stabilité atteinte: {stability_count}/{stability_threshold}")

        # Décider si on peut quand même continuer
        if last_content_length > 1000 and last_code_blocks > 0:
            logger.warning("   ⚠️ Contenu substantiel détecté malgré timeout")
            logger.warning("   ➡️ Poursuite avec extraction partielle")
            return True

        return False
    
    def _verify_generation_readiness(self) -> Dict[str, any]:
        """
        🔍 Vérification ponctuelle de l'état de génération

        Returns:
            dict: État détaillé de la génération
        """
        try:
            result = self.client.execute_javascript("""
                (() => {
                    // État génération
                    const stopBtn = document.querySelector('button[aria-label*="Stop"], button[aria-label*="stop"]');
                    const isGenerating = stopBtn && stopBtn.offsetParent !== null;

                    // Contenu
                    const main = document.querySelector('main') || document.body;
                    const content = main.innerText || '';

                    // Code
                    const codeBlocks = main.querySelectorAll('pre code, pre');
                    let validCodeBlocks = 0;
                    codeBlocks.forEach(block => {
                        if (block.textContent.trim().length > 50) validCodeBlocks++;
                    });

                    // Métadonnées
                    const hasStructure = /# ACTION:/i.test(content) && /# FILE:/i.test(content);

                    return {
                        isGenerating: isGenerating,
                        contentLength: content.length,
                        codeBlocks: validCodeBlocks,
                        hasStructure: hasStructure,
                        ready: !isGenerating && content.length > 500 && (validCodeBlocks > 0 || hasStructure)
                    };
                })();
            """)

            if isinstance(result, dict) and "result" in result:
                return result["result"]

            return {'ready': False, 'error': 'Invalid response'}

        except Exception as e:
            logger.error(f"❌ Erreur vérification état: {e}")
            return {'ready': False, 'error': str(e)}
        
    def _diagnose_html_structure(self) -> Dict:
        """
        🔍 Diagnostic complet de la structure HTML pour debugging
        """
        logger.info("🔍 Diagnostic structure HTML...")
        
        result = self.client.execute_javascript("""
            (() => {
                return {
                    // Structure générale
                    url: window.location.href,
                    title: document.title,
                    
                    // Balises principales
                    hasMain: !!document.querySelector('main'),
                    hasArticle: !!document.querySelector('article'),
                    hasBody: !!document.body,
                    
                    // Dimensions
                    bodyLength: document.body?.innerText?.length || 0,
                    htmlLength: document.documentElement?.innerHTML?.length || 0,
                    
                    // Éléments de contenu
                    divCount: document.querySelectorAll('div').length,
                    pCount: document.querySelectorAll('p').length,
                    preCount: document.querySelectorAll('pre').length,
                    codeCount: document.querySelectorAll('code').length,
                    
                    // Éléments Claude spécifiques
                    claudeClasses: Array.from(document.querySelectorAll('[class*="claude"]')).length,
                    messageClasses: Array.from(document.querySelectorAll('[class*="message"]')).length,
                    
                    // Premier élément avec beaucoup de texte
                    largestElement: (() => {
                        let largest = null;
                        let maxLength = 0;
                        
                        document.querySelectorAll('div, article, section, main').forEach(el => {
                            const text = el.innerText || '';
                            if (text.length > maxLength && text.length > 1000) {
                                maxLength = text.length;
                                largest = {
                                    tag: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    textLength: text.length,
                                    preview: text.substring(0, 200)
                                };
                            }
                        });
                        
                        return largest;
                    })()
                };
            })();
        """)
        
        if isinstance(result, dict) and "result" in result:
            diagnostic = result["result"]
            
            logger.info("📊 DIAGNOSTIC HTML:")
            logger.info(f"   URL: {diagnostic.get('url')}")
            logger.info(f"   Title: {diagnostic.get('title')}")
            logger.info(f"   Body length: {diagnostic.get('bodyLength')} chars")
            logger.info(f"   Has <main>: {diagnostic.get('hasMain')}")
            logger.info(f"   <pre>: {diagnostic.get('preCount')}, <code>: {diagnostic.get('codeCount')}")
            logger.info(f"   Elements Claude: {diagnostic.get('claudeClasses')}")
            
            if diagnostic.get('largestElement'):
                largest = diagnostic['largestElement']
                logger.info(f"   Plus grand élément: <{largest['tag']}> ({largest['textLength']} chars)")
                logger.info(f"      Class: {largest.get('className', 'N/A')}")
                logger.info(f"      Preview: {largest.get('preview', '')[:100]}...")
            
            return diagnostic
        
        return {}
    
    def _force_render_all_content(self) -> bool:
        logger.info("🔄 Forçage du rendu complet...")

        result = self.client.execute_javascript("""
            (async () => {
                try {
                    // 1. Trouver le conteneur scrollable
                    const scrollableSelectors = [
                        'main',
                        '[role="main"]',
                        '.overflow-auto',
                        '.overflow-y-auto',
                        '[class*="scroll"]'
                    ];

                    let scrollContainer = null;
                    for (let selector of scrollableSelectors) {
                        const el = document.querySelector(selector);
                        if (el && (el.scrollHeight > el.clientHeight || el.scrollTop !== undefined)) {
                            scrollContainer = el;
                            break;
                        }
                    }

                    if (!scrollContainer) {
                        scrollContainer = document.documentElement;
                    }

                    // 2. Scroller progressivement jusqu'en bas
                    const scrollStep = 500;  // Scroll de 500px à la fois
                    const scrollDelay = 100; // Attendre 100ms entre chaque scroll

                    let currentScroll = 0;
                    const maxScroll = scrollContainer.scrollHeight;

                    while (currentScroll < maxScroll) {
                        scrollContainer.scrollTo(0, currentScroll);
                        await new Promise(resolve => setTimeout(resolve, scrollDelay));
                        currentScroll += scrollStep;

                        // Sécurité : ne pas boucler infiniment
                        if (currentScroll > maxScroll * 2) break;
                    }

                    // 3. Scroller tout en haut pour repartir
                    scrollContainer.scrollTo(0, 0);
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // 4. Re-scroller jusqu'en bas (au cas où du contenu s'est ajouté)
                    scrollContainer.scrollTo(0, maxScroll);
                    await new Promise(resolve => setTimeout(resolve, 300));

                    return {
                        success: true,
                        scrolledHeight: maxScroll,
                        message: 'Contenu forcé'
                    };

                } catch (error) {
                    return {
                        success: false,
                        error: error.toString()
                    };
                }
            })();
        """)

        if isinstance(result, dict) and result.get("result", {}).get("success"):
            logger.info(f"   ✅ Rendu forcé sur {result['result'].get('scrolledHeight', 0)}px")
            return True
        else:
            logger.warning("   ⚠️ Impossible de forcer le rendu complet")
            return False
        
    def _extract_all_code_blocks_directly(self) -> List[Dict]:
        """
        🆕 MÉTHODE DIRECTE : Extraire TOUS les blocs de code directement du DOM

        Bypasse innerText qui peut tronquer → Extraction élément par élément
        """
        logger.info("📦 Extraction DIRECTE de tous les blocs de code...")

        result = self.client.execute_javascript("""
            (() => {
                const codeBlocks = [];

                // 1. Chercher TOUS les blocs <pre> et <code>
                const preElements = document.querySelectorAll('pre');

                preElements.forEach((pre, index) => {
                    try {
                        // Récupérer le contenu BRUT
                        let code = '';

                        // Vérifier s'il y a un <code> dedans
                        const codeEl = pre.querySelector('code');
                        if (codeEl) {
                            code = codeEl.textContent || codeEl.innerText || '';
                        } else {
                            code = pre.textContent || pre.innerText || '';
                        }

                        if (!code || code.trim().length < 10) return;

                        // Chercher les métadonnées AUTOUR du bloc
                        let metadata = {
                            action: '',
                            file: '',
                            target: '',
                            position: '',
                            description: ''
                        };

                        // Chercher dans le code lui-même
                        const lines = code.split('\\n');
                        const metadataLines = [];
                        const codeLines = [];

                        for (let line of lines) {
                            const trimmed = line.trim();

                            if (trimmed.match(/^#\\s*ACTION\\s*:/i)) {
                                const match = trimmed.match(/^#\\s*ACTION\\s*:\\s*(.+)/i);
                                if (match) metadata.action = match[1].trim();
                                metadataLines.push(line);
                            } else if (trimmed.match(/^#\\s*FILE\\s*:/i)) {
                                const match = trimmed.match(/^#\\s*FILE\\s*:\\s*(.+)/i);
                                if (match) metadata.file = match[1].trim();
                                metadataLines.push(line);
                            } else if (trimmed.match(/^#\\s*TARGET\\s*:/i)) {
                                const match = trimmed.match(/^#\\s*TARGET\\s*:\\s*(.+)/i);
                                if (match) metadata.target = match[1].trim();
                                metadataLines.push(line);
                            } else if (trimmed.match(/^#\\s*POSITION\\s*:/i)) {
                                const match = trimmed.match(/^#\\s*POSITION\\s*:\\s*(.+)/i);
                                if (match) metadata.position = match[1].trim();
                                metadataLines.push(line);
                            } else if (trimmed.match(/^#\\s*DESCRIPTION\\s*:/i)) {
                                const match = trimmed.match(/^#\\s*DESCRIPTION\\s*:\\s*(.+)/i);
                                if (match) metadata.description = match[1].trim();
                                metadataLines.push(line);
                            } else {
                                codeLines.push(line);
                            }
                        }

                        // Si métadonnées trouvées, c'est un snippet valide
                        if (metadata.action && metadata.file) {
                            codeBlocks.push({
                                index: index,
                                metadata: metadata,
                                code: codeLines.join('\\n').trim(),
                                rawCode: code,
                                hasMetadata: true
                            });
                        } else {
                            // Bloc sans métadonnées → garder quand même
                            codeBlocks.push({
                                index: index,
                                metadata: metadata,
                                code: code.trim(),
                                rawCode: code,
                                hasMetadata: false
                            });
                        }

                    } catch (error) {
                        console.error('Erreur extraction bloc', index, error);
                    }
                });

                return {
                    success: true,
                    totalBlocks: codeBlocks.length,
                    withMetadata: codeBlocks.filter(b => b.hasMetadata).length,
                    blocks: codeBlocks
                };
            })();
        """)

        if isinstance(result, dict) and "result" in result:
            data = result["result"]

            if data.get("success"):
                total = data.get("totalBlocks", 0)
                with_meta = data.get("withMetadata", 0)

                logger.info(f"   ✅ {total} blocs extraits ({with_meta} avec métadonnées)")

                return data.get("blocks", [])

        logger.warning("   ⚠️ Extraction directe échouée")
        return []
    
    def _convert_blocks_to_snippets(self, blocks: List[Dict]) -> List[Dict]:
        """
        🆕 Convertir les blocs extraits en snippets formatés
        """
        snippets = []

        for idx, block in enumerate(blocks, 1):
            try:
                metadata = block.get("metadata", {})
                code = block.get("code", "")

                if not code or len(code.strip()) < 10:
                    continue
                
                # Si pas de métadonnées, tenter de les déduire
                if not block.get("hasMetadata"):
                    # Chercher des indices dans le code
                    if "def " in code or "class " in code:
                        action = "AJOUTER"
                        file = f"generated_code_{idx}.py"
                    else:
                        logger.debug(f"   ⏭️  Bloc {idx} sans métadonnées ignoré")
                        continue
                else:
                    action = metadata.get("action", "AJOUTER")
                    file = metadata.get("file", f"code_{idx}.py")

                snippet = {
                    'action': action.upper(),
                    'title': self._generate_title(action, file, metadata.get("target", "")),
                    'file': file,
                    'code': code,
                    'language': 'python',
                    'description': metadata.get("description", f"Code du bloc {idx}"),
                    'lineNumber': 0,
                    'target': metadata.get("target", ""),
                    'position': metadata.get("position", ""),
                    'platform': self.config['name']
                }

                snippets.append(snippet)
                logger.info(f"   ✅ Snippet {idx}: {file}")

            except Exception as e:
                logger.error(f"   ❌ Erreur conversion bloc {idx}: {e}")
                continue
            
        return snippets
    
    def _extract_with_progressive_methods(self) -> Dict:
        """
        🎯 MÉTHODE ULTIME : Extraction avec méthodes progressives

        Essaie 3 méthodes dans l'ordre, garde la meilleure
        """
        logger.info("\n" + "="*80)
        logger.info("🚀 EXTRACTION PROGRESSIVE AVEC 3 MÉTHODES")
        logger.info("="*80)

        results = {
            'method1_direct': None,
            'method2_universal': None,
            'method3_fallback': None,
            'best_method': None,
            'best_content': '',
            'best_snippets': []
        }

        # ============================================================
        # ÉTAPE 0 : FORCER LE RENDU COMPLET
        # ============================================================
        logger.info("\n🔄 ÉTAPE 0/3 : Forçage rendu complet...")
        self._force_render_all_content()
        time.sleep(2)  # Laisser le temps au DOM de se stabiliser

        # ============================================================
        # MÉTHODE 1 : EXTRACTION DIRECTE DES BLOCS (LA PLUS FIABLE)
        # ============================================================
        logger.info("\n📦 MÉTHODE 1/3 : Extraction DIRECTE des blocs de code...")
        try:
            blocks = self._extract_all_code_blocks_directly()

            if blocks and len(blocks) > 0:
                snippets = self._convert_blocks_to_snippets(blocks)

                if snippets and len(snippets) > 0:
                    results['method1_direct'] = {
                        'blocks': len(blocks),
                        'snippets': len(snippets),
                        'success': True
                    }
                    results['best_method'] = 'method1_direct'
                    results['best_snippets'] = snippets

                    # Reconstruire le contenu brut
                    full_code = '\n\n'.join([b.get('rawCode', '') for b in blocks])
                    results['best_content'] = full_code

                    logger.info(f"   ✅ MÉTHODE 1 : {len(snippets)} snippets extraits")
                    logger.info(f"   📊 Contenu total: {len(full_code)} chars")

                    # Si on a des snippets, c'est gagné !
                    return results

        except Exception as e:
            logger.error(f"   ❌ MÉTHODE 1 échouée: {e}")

        # ============================================================
        # MÉTHODE 2 : EXTRACTION UNIVERSELLE ROBUSTE
        # ============================================================
        logger.info("\n📄 MÉTHODE 2/3 : Extraction universelle robuste...")
        try:
            content = self._extract_content_universal_robust()

            if content and len(content) > 1000:
                # Extraire snippets du contenu
                snippets = self._extract_snippets(content)

                if snippets and len(snippets) > 0:
                    results['method2_universal'] = {
                        'content_length': len(content),
                        'snippets': len(snippets),
                        'success': True
                    }

                    # Si pas de meilleure méthode avant
                    if not results['best_method']:
                        results['best_method'] = 'method2_universal'
                        results['best_content'] = content
                        results['best_snippets'] = snippets

                    logger.info(f"   ✅ MÉTHODE 2 : {len(snippets)} snippets extraits")
                    logger.info(f"   📊 Contenu: {len(content)} chars")

        except Exception as e:
            logger.error(f"   ❌ MÉTHODE 2 échouée: {e}")

        # ============================================================
        # MÉTHODE 3 : FALLBACK CLASSIQUE
        # ============================================================
        logger.info("\n🔄 MÉTHODE 3/3 : Fallback classique...")
        try:
            content = self._extract_content_universal()

            if content and len(content) > 500:
                snippets = self._extract_snippets(content)

                results['method3_fallback'] = {
                    'content_length': len(content),
                    'snippets': len(snippets) if snippets else 0,
                    'success': True
                }

                # Si toujours pas de meilleure méthode
                if not results['best_method']:
                    results['best_method'] = 'method3_fallback'
                    results['best_content'] = content
                    results['best_snippets'] = snippets or []

                logger.info(f"   ✅ MÉTHODE 3 : {len(snippets or [])} snippets extraits")

        except Exception as e:
            logger.error(f"   ❌ MÉTHODE 3 échouée: {e}")

        # ============================================================
        # RAPPORT FINAL
        # ============================================================
        logger.info("\n" + "="*80)
        logger.info("📊 RAPPORT D'EXTRACTION")
        logger.info("="*80)
        logger.info(f"Méthode gagnante: {results.get('best_method', 'AUCUNE')}")
        logger.info(f"Snippets extraits: {len(results.get('best_snippets', []))}")
        logger.info(f"Contenu total: {len(results.get('best_content', ''))} chars")
        logger.info("="*80 + "\n")

        return results

    def send_to_platform(self, context: str, perimeter_data: List[Dict], 
                    status_callback: Optional[Callable] = None) -> Dict:
        try:
            # ====================================================================
            # PHASE 1 : CONSTRUCTION DU PROMPT
            # ====================================================================
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

            # ====================================================================
            # PHASE 2 : ENVOI DU MESSAGE
            # ====================================================================
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

            # ====================================================================
            # PHASE 3 : ATTENTE DE LA GÉNÉRATION COMPLÈTE
            # ====================================================================
            if status_callback:
                status_callback("Attente de la génération complète", 85)

            # ✅ CORRECTION 1 : Attente simplifiée
            logger.info("⏳ Attente contenu Claude.ai...")
            time.sleep(10)  # Délai initial pour que la génération commence

            # Attendre que le contenu soit présent et stable
            content_ready = self._wait_for_code_blocks(max_wait=60)

            if not content_ready:
                logger.warning("⚠️ Timeout, tentative extraction malgré tout...")
            else:
                logger.info("✅ Contenu détecté et stable")

            # Attente sécurité finale
            time.sleep(3)

            # ====================================================================
            # PHASE 4 : EXTRACTION DU CONTENU
            # ====================================================================
            if status_callback:
                status_callback("Récupération du contenu", 88)

            logger.info("🎯 Extraction PROGRESSIVE du contenu...")

            # 🆕 NOUVELLE MÉTHODE
            extraction_results = self._extract_with_progressive_methods()

            self.current_response = extraction_results.get('best_content', '')
            snippets = extraction_results.get('best_snippets', [])
            extraction_method = extraction_results.get('best_method', 'unknown')

            if not self.current_response or len(self.current_response) < 100:
                logger.error("❌ Contenu vide ou insuffisant")
                return {
                    'success': False,
                    'message': "❌ Impossible de récupérer le contenu",
                    'snippets': [],
                    'raw_response': '',
                    'extraction_method': 'error'
                }

            logger.info(f"✅ Contenu récupéré: {len(self.current_response)} chars")
            logger.info(f"📦 Méthode utilisée: {extraction_method}")

            # Si pas de snippets de la méthode directe, essayer extraction classique
            if not snippets or len(snippets) == 0:
                logger.info("🔄 Extraction classique des snippets...")
                snippets = self._extract_snippets(self.current_response)

            # ✅ CORRECTION 3 : Debug structure
            if len(self.current_response) > 0:
                self._debug_response_structure(self.current_response)

            # ====================================================================
            # PHASE 5 : EXTRACTION DES SNIPPETS
            # ====================================================================
            if status_callback:
                status_callback("Extraction des snippets", 90)

            snippets = self._extract_snippets(self.current_response)
            logger.info(f"✅ {len(snippets)} snippet(s) extraits via DOM")

            # ====================================================================
            # PHASE 6 : RÉPARATION DU CODE (SAFE ou AGGRESSIVE)
            # ====================================================================
            if snippets and len(snippets) > 0 and self.repair_code:
                repair_mode = "AGGRESSIVE" if self.aggressive_repair else "SAFE"

                if status_callback:
                    status_callback(f"🔧 Réparation {repair_mode} du code", 93)

                logger.info(f"\n{'='*80}")
                logger.info(f"🔧 RÉPARATION {repair_mode} - ÉTAPE 6/8")
                logger.info(f"{'='*80}")

                try:
                    if self.aggressive_repair:
                        # Mode AGGRESSIVE : réparation complète avec validation
                        repaired_snippets = DomExtractionFixer.repair_snippets_avec_validation(
                            snippets=snippets,
                            verbose=True,
                            keep_invalid=True
                        )
                    else:
                        # Mode SAFE : réparation conservative
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

            # ====================================================================
            # PHASE 7 : FORMATAGE
            # ====================================================================
            if self.auto_format and snippets and len(snippets) > 0:
                if status_callback:
                    status_callback("🎨 Formatage des snippets", 95)

                logger.info(f"\n{'='*80}")
                logger.info("🎨 FORMATAGE - ÉTAPE 7/8")
                logger.info(f"{'='*80}")

                try:
                    formatted_snippets = format_extracted_snippets(snippets)
                    if formatted_snippets:
                        snippets = formatted_snippets
                        logger.info(f"✅ {len(snippets)} snippet(s) formatés")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur formatage: {e}")

            # ====================================================================
            # PHASE 8 : VALIDATION FINALE AVEC AUTO-ESCALADE
            # ====================================================================
            if snippets and len(snippets) > 0:
                if status_callback:
                    status_callback("🔍 Validation finale", 97)

                logger.info(f"\n{'='*80}")
                logger.info("🔍 VALIDATION FINALE - ÉTAPE 8/8")
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

                # ✅ AUTO-ESCALADE VERS MODE AGGRESSIVE SI NÉCESSAIRE
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

                # ✅ RAPPORT FINAL
                logger.info(f"\n{'='*80}")
                logger.info(f"📊 RÉSULTATS FINAUX:")
                logger.info(f"   ✅ Snippets valides: {valid_count}")
                logger.info(f"   ⚠️ Snippets partiels: {invalid_count}")
                logger.info(f"   📦 Total conservé: {len(snippets)}")
                logger.info(f"   🎯 Méthode: UNIVERSAL EXTRACTION")

                if len(snippets) > 0:
                    avg_quality = sum(s.get('quality_score', 0) for s in snippets) / len(snippets)
                    logger.info(f"   🎯 Score moyen: {avg_quality:.1f}/100")
                    logger.info(f"   📈 Taux récupération: 100%")

                logger.info(f"{'='*80}")

            # ====================================================================
            # RETOUR FINAL
            # ====================================================================
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
        
    def _extract_snippets_robust(self, response: str) -> List[Dict]:
        """
        🆕 EXTRACTION ULTRA-ROBUSTE : Gère tous les cas de figure

        Stratégie :
        1. Trouver TOUS les # ACTION: (même sans format strict)
        2. Découper le texte en segments entre chaque ACTION
        3. Extraire métadonnées + code de chaque segment
        4. Gérer les blocs ```python et les blocs sans délimiteurs
        """
        snippets = []

        logger.info(f"\n{'='*80}")
        logger.info("🔍 EXTRACTION ROBUSTE DES SNIPPETS")
        logger.info(f"{'='*80}")
        logger.info(f"📄 Taille réponse: {len(response)} chars")

        # ================================================================
        # PHASE 0 : PRÉPARATION (identique à votre code)
        # ================================================================
        logger.info("⚡ PHASE 0.1 : Reconstruction tokens éclatés")
        try:
            from core.orchestration.advanced_code_recovery import DomExtractionFixer, RepairStats
            stats_temp = RepairStats()
            response = DomExtractionFixer._reconstruct_split_tokens(response, stats_temp, verbose=True)
            if stats_temp.operators_fixed > 0:
                logger.info(f"   ✅ {stats_temp.operators_fixed} token(s) reconstruits")
        except Exception as e:
            logger.warning(f"⚠️ Erreur reconstruction: {e}")

        logger.info("🔗 PHASE 0.2 : Fusion lignes éclatées")
        try:
            from core.orchestration.advanced_code_recovery import UltimateLineMerger
            lines = response.split('\n')
            merged_lines = UltimateLineMerger.merge_lines(lines)
            response = '\n'.join(merged_lines)
            logger.info(f"   ✅ {len(lines) - len(merged_lines)} lignes fusionnées")
        except Exception as e:
            logger.warning(f"⚠️ Erreur fusion: {e}")

        cleaned_response = self._clean_broken_lines(response)
        cleaned_response = self._clean_dom_pollution(cleaned_response)
        logger.info(f"🧹 Après nettoyage: {len(cleaned_response)} chars")

        # ================================================================
        # 🆕 PHASE 1 : TROUVER TOUS LES # ACTION: (ULTRA-FLEXIBLE)
        # ================================================================
        logger.info("🎯 PHASE 1 : Détection de TOUS les blocs ACTION")

        # Pattern ultra-flexible pour ACTION
        action_pattern = r'#\s*ACTION\s*:\s*(\w+)'
        action_matches = list(re.finditer(action_pattern, cleaned_response, re.IGNORECASE))

        logger.info(f"   🔍 {len(action_matches)} bloc(s) ACTION détectés")

        if not action_matches:
            logger.warning("⚠️ Aucun bloc ACTION détecté, tentative fallback...")
            return self._extract_fallback_snippets(cleaned_response)

        # ================================================================
        # 🆕 PHASE 2 : DÉCOUPER EN SEGMENTS ENTRE CHAQUE ACTION
        # ================================================================
        logger.info("✂️ PHASE 2 : Découpage en segments")

        segments = []

        for idx, action_match in enumerate(action_matches):
            try:
                action = action_match.group(1).strip().upper()
                segment_start = action_match.start()

                # Trouver la fin du segment (= début du prochain ACTION ou fin du texte)
                if idx + 1 < len(action_matches):
                    segment_end = action_matches[idx + 1].start()
                else:
                    segment_end = len(cleaned_response)

                # Extraire le segment complet
                segment_text = cleaned_response[segment_start:segment_end]

                logger.info(f"\n   📦 Segment {idx + 1}/{len(action_matches)}: {len(segment_text)} chars")

                # Extraire métadonnées du segment
                file_match = re.search(r'#\s*FILE\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                target_match = re.search(r'#\s*TARGET\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                position_match = re.search(r'#\s*POSITION\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)
                desc_match = re.search(r'#\s*DESCRIPTION\s*:\s*([^\n\r]+)', segment_text, re.IGNORECASE)

                file_path = file_match.group(1).strip() if file_match else f"code_{idx + 1}.py"
                target = target_match.group(1).strip() if target_match else ""
                position = position_match.group(1).strip().lower() if position_match else ""
                description = desc_match.group(1).strip() if desc_match else ""

                logger.info(f"      📁 FILE: {file_path}")
                if target:
                    logger.info(f"      🎯 TARGET: {target[:50]}...")
                if position:
                    logger.info(f"      📍 POSITION: {position}")

                # ============================================================
                # 🆕 EXTRACTION DU CODE (MULTI-MÉTHODES)
                # ============================================================
                code = ""

                # Méthode 1 : Chercher bloc ```python ... ```
                python_block_match = re.search(r'```python\s*\n(.*?)```', segment_text, re.DOTALL | re.IGNORECASE)

                if python_block_match:
                    code = python_block_match.group(1).strip()
                    logger.info(f"      ✅ Code extrait via ```python : {len(code)} chars")

                # Méthode 2 : Sinon, prendre tout après les métadonnées
                else:
                    # Trouver la dernière ligne de métadonnée
                    last_metadata_pos = 0

                    for pattern in [r'#\s*ACTION\s*:', r'#\s*FILE\s*:', r'#\s*TARGET\s*:', 
                                   r'#\s*POSITION\s*:', r'#\s*DESCRIPTION\s*:']:
                        matches = list(re.finditer(pattern, segment_text, re.IGNORECASE))
                        if matches:
                            last_match = matches[-1]
                            # Trouver la fin de la ligne
                            end_of_line = segment_text.find('\n', last_match.end())
                            if end_of_line != -1:
                                last_metadata_pos = max(last_metadata_pos, end_of_line + 1)

                    # Prendre tout après les métadonnées
                    if last_metadata_pos > 0:
                        code = segment_text[last_metadata_pos:].strip()
                        logger.info(f"      ✅ Code extrait après métadonnées : {len(code)} chars")
                    else:
                        logger.warning(f"      ⚠️ Impossible d'extraire le code du segment {idx + 1}")
                        continue
                    
                # Nettoyer le code des artefacts
                code = self._clean_code_artifacts(code)

                # Validation minimale
                if not code or len(code.strip()) < 20:
                    logger.warning(f"      ⚠️ Code trop court ({len(code)} chars), ignoré")
                    continue
                
                # Créer le snippet
                snippet = {
                    'action': action,
                    'title': self._generate_title(action, file_path, target),
                    'file': file_path,
                    'code': code,
                    'language': 'python',
                    'description': description or f"Code généré par {self.config['name']}",
                    'lineNumber': 0,
                    'target': target,
                    'position': position,
                    'platform': self.config['name']
                }

                snippets.append(snippet)
                logger.info(f"      ✅ Snippet {idx + 1} créé avec succès")

            except Exception as e:
                logger.error(f"      ❌ Erreur segment {idx + 1}: {e}")
                continue

        # ================================================================
        # RAPPORT FINAL
        # ================================================================
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ {len(snippets)} snippet(s) extraits sur {len(action_matches)} détectés")
        logger.info(f"{'='*80}\n")

        return snippets
    
    def _clean_code_artifacts(self, code: str) -> str:
        # Supprimer les délimiteurs ```
        code = re.sub(r'^```python\s*\n?', '', code, flags=re.MULTILINE | re.IGNORECASE)
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)

        # Supprimer les lignes de métadonnées résiduelles
        lines = code.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Ignorer les métadonnées
            if re.match(r'^#\s*(ACTION|FILE|TARGET|POSITION|DESCRIPTION)\s*:', stripped, re.IGNORECASE):
                continue
            
            # Ignorer les artefacts UI
            if stripped in ['python', 'Copier', 'Regenerate', 'Réessayer', 
                           'Comment puis-je vous aider ?', 'Sonnet 4.5']:
                continue
            
            # Ignorer les lignes courtes suspectes
            if len(stripped) < 3 and stripped not in ['', 'if', 'or', 'is']:
                continue
            
            cleaned_lines.append(line)

        code = '\n'.join(cleaned_lines)

        # Nettoyer les espaces multiples
        code = re.sub(r'\n{3,}', '\n\n', code)

        return code.strip()
        
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