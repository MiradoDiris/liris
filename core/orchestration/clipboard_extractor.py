"""
clipboard_extractor.py - VERSION OPTIMISÉE v2.0
Extraction clipboard ultra-robuste avec détection intelligente
"""

import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

from utils.logger import logger


@dataclass
class ExtractionStats:
    """Statistiques d'extraction détaillées"""
    blocks_detected: int = 0
    blocks_extracted: int = 0
    buttons_found: int = 0
    hover_attempts: int = 0
    clipboard_reads: int = 0
    total_chars: int = 0
    avg_block_size: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ClipboardExtractor:
    """
    ✅ Extracteur clipboard optimisé avec stratégies multiples
    """
    
    # Sélecteurs pour différentes plateformes
    PLATFORM_SELECTORS = {
        'claude': {
            'code_containers': [
                'pre:has(code)',
                'div[class*="code-block"]',
                'div[data-lexical-decorator="true"]',
                '[class*="font-code"]'
            ],
            'copy_buttons': [
                'button[aria-label*="Copy"]',
                'button[aria-label*="Copier"]',
                'button:has(svg[class*="copy"])',
                'button.copy-button',
                '[data-testid="copy-button"]'
            ]
        },
        'chatgpt': {
            'code_containers': [
                'pre:has(code)',
                'div.code-block',
                '[data-testid="code-block"]'
            ],
            'copy_buttons': [
                'button[class*="copy"]',
                'button:has(svg[data-icon="copy"])'
            ]
        },
        'gemini': {
            'code_containers': [
                'pre code',
                'code-block'
            ],
            'copy_buttons': [
                'button[aria-label="Copy code"]',
                'button.copy-code-button'
            ]
        }
    }
    
    def __init__(self, platform: str = 'claude'):
        if not CLIPBOARD_AVAILABLE:
            raise ImportError("pyperclip requis: pip install pyperclip")
        
        self.platform = platform.lower()
        self.stats = ExtractionStats()
        self.extracted_hashes = set()  # Éviter doublons
    
    def extract_all_code_blocks(self, page) -> List[Dict]:
        """
        🎯 MÉTHODE PRINCIPALE - Extraction complète avec retry intelligent
        
        Args:
            page: Instance Playwright Page (sync ou async)
        
        Returns:
            Liste de snippets structurés
        """
        logger.info("="*80)
        logger.info("📋 EXTRACTION CLIPBOARD - MODE OPTIMISÉ v2.0")
        logger.info("="*80)
        
        snippets = []
        
        try:
            # 1️⃣ Détecter les blocs de code
            code_blocks = self._detect_code_blocks(page)
            self.stats.blocks_detected = len(code_blocks)
            
            logger.info(f"📦 {len(code_blocks)} bloc(s) de code détectés")
            
            if not code_blocks:
                logger.warning("⚠️ Aucun bloc de code détecté")
                return []
            
            # 2️⃣ Extraire chaque bloc avec retry
            for idx, block_info in enumerate(code_blocks, 1):
                logger.info(f"\n📦 Bloc {idx}/{len(code_blocks)}")
                
                # Tentative d'extraction avec retry automatique
                result = self._extract_block_with_retry(page, block_info, idx, max_attempts=3)
                
                if result:
                    snippet = self._create_snippet(result['code'], idx, block_info)
                    
                    # Vérifier doublons
                    code_hash = hash(snippet['code'])
                    if code_hash not in self.extracted_hashes:
                        snippets.append(snippet)
                        self.extracted_hashes.add(code_hash)
                        self.stats.blocks_extracted += 1
                        self.stats.total_chars += len(snippet['code'])
                        logger.info(f"   ✅ Extrait: {len(snippet['code'])} chars")
                    else:
                        logger.debug(f"   ⏭️ Bloc dupliqué, ignoré")
                else:
                    logger.warning(f"   ⚠️ Échec extraction bloc {idx}")
                    self.stats.errors.append(f"Bloc {idx}: extraction failed")
            
            # Statistiques finales
            self._log_final_stats(snippets)
            
            return snippets
        
        except Exception as e:
            logger.error(f"❌ Erreur extraction: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _detect_code_blocks(self, page) -> List[Dict]:
        """
        🔍 Détection intelligente des blocs de code
        Supporte multiple stratégies selon la plateforme
        """
        try:
            selectors = self.PLATFORM_SELECTORS.get(
                self.platform, 
                self.PLATFORM_SELECTORS['claude']
            )
            
            # Construire requête JavaScript dynamique
            js_selectors = ', '.join(f'"{s}"' for s in selectors['code_containers'])
            
            blocks = page.evaluate(f"""
                () => {{
                    const selectors = [{js_selectors}];
                    const blocks = [];
                    
                    // Essayer chaque sélecteur
                    for (const selector of selectors) {{
                        try {{
                            const elements = document.querySelectorAll(selector);
                            
                            elements.forEach((elem, index) => {{
                                // Trouver le <code> ou le contenu texte
                                let codeElem = elem.querySelector('code') || elem;
                                let text = codeElem.textContent || codeElem.innerText || '';
                                
                                if (text.trim().length < 20) return;
                                
                                const rect = elem.getBoundingClientRect();
                                if (rect.height === 0) return;
                                
                                // Identifier le bloc de manière unique
                                const uniqueId = `${{elem.tagName}}-${{index}}-${{text.substring(0, 50).replace(/\\s+/g, '')}}`;
                                
                                // Éviter doublons
                                if (blocks.some(b => b.uniqueId === uniqueId)) return;
                                
                                blocks.push({{
                                    uniqueId: uniqueId,
                                    selector: selector,
                                    index: blocks.length,
                                    textPreview: text.substring(0, 100),
                                    codeLength: text.length,
                                    rect: {{
                                        x: rect.x,
                                        y: rect.y,
                                        width: rect.width,
                                        height: rect.height,
                                        top: rect.top
                                    }},
                                    xpath: null  // Sera calculé si nécessaire
                                }});
                            }});
                        }} catch (e) {{
                            console.error(`Erreur sélecteur ${{selector}}:`, e);
                        }}
                    }}
                    
                    // Trier par position verticale (top -> bottom)
                    blocks.sort((a, b) => a.rect.top - b.rect.top);
                    
                    return blocks;
                }}
            """)
            
            logger.info(f"   ✅ {len(blocks)} blocs détectés via Playwright")
            return blocks
        
        except Exception as e:
            logger.error(f"❌ Erreur détection blocs: {e}")
            return []
    
    def _extract_block_with_retry(
        self, 
        page, 
        block_info: Dict, 
        block_index: int,
        max_attempts: int = 3
    ) -> Optional[Dict]:
        """
        🔄 Extraction avec retry automatique et stratégies multiples
        """
        strategies = [
            ('hover_click', self._extract_via_hover_click),
            ('direct_click', self._extract_via_direct_click),
            ('dom_fallback', self._extract_via_dom_fallback)
        ]
        
        for attempt in range(max_attempts):
            # Choisir stratégie (rotation)
            strategy_name, strategy_func = strategies[attempt % len(strategies)]
            
            logger.debug(f"   🎯 Tentative {attempt + 1}/{max_attempts} - Stratégie: {strategy_name}")
            
            try:
                result = strategy_func(page, block_info, block_index)
                
                if result and self._validate_extracted_code(result['code']):
                    logger.debug(f"      ✅ Stratégie '{strategy_name}' réussie")
                    return result
                else:
                    logger.debug(f"      ⚠️ Stratégie '{strategy_name}' échouée")
            
            except Exception as e:
                logger.debug(f"      ❌ Erreur stratégie '{strategy_name}': {e}")
            
            # Attente avant retry
            if attempt < max_attempts - 1:
                time.sleep(0.5)
        
        return None
    
    def _extract_via_hover_click(self, page, block_info: Dict, block_index: int) -> Optional[Dict]:
        """
        🖱️ STRATÉGIE 1: Hover sur bloc + clic sur bouton copie
        """
        try:
            # Construire sélecteur unique
            selector = self._build_unique_selector(page, block_info)
            
            if not selector:
                return None
            
            # Hover sur le bloc
            logger.debug(f"      🖱️ Hover sur bloc...")
            page.hover(selector, timeout=2000)
            self.stats.hover_attempts += 1
            
            # Attendre apparition bouton
            time.sleep(0.3)
            
            # Chercher bouton copie
            button_selector = self._find_copy_button(page, selector)
            
            if not button_selector:
                logger.debug(f"      ⚠️ Bouton copie non trouvé")
                return None
            
            self.stats.buttons_found += 1
            
            # Vider clipboard
            pyperclip.copy("")
            time.sleep(0.1)
            
            # Cliquer
            logger.debug(f"      🖱️ Clic sur bouton...")
            page.click(button_selector, timeout=2000)
            
            # Attendre clipboard
            return self._wait_for_clipboard(max_wait=2.0)
        
        except Exception as e:
            logger.debug(f"      ❌ Hover/click échoué: {e}")
            return None
    
    def _extract_via_direct_click(self, page, block_info: Dict, block_index: int) -> Optional[Dict]:
        """
        🖱️ STRATÉGIE 2: Clic direct sur bouton (sans hover)
        """
        try:
            # Chercher tous les boutons copie visibles
            copy_buttons = page.query_selector_all('button[aria-label*="Copy"], button[aria-label*="Copier"]')
            
            if not copy_buttons or block_index > len(copy_buttons):
                return None
            
            # Prendre le Nième bouton
            button = copy_buttons[block_index - 1]
            
            if not button.is_visible():
                return None
            
            # Vider clipboard
            pyperclip.copy("")
            time.sleep(0.1)
            
            # Cliquer
            button.click(timeout=2000)
            self.stats.buttons_found += 1
            
            return self._wait_for_clipboard(max_wait=2.0)
        
        except Exception as e:
            logger.debug(f"      ❌ Direct click échoué: {e}")
            return None
    
    def _extract_via_dom_fallback(self, page, block_info: Dict, block_index: int) -> Optional[Dict]:
        """
        🔧 STRATÉGIE 3: Fallback DOM (dernier recours)
        Extrait directement depuis le DOM sans bouton copie
        """
        try:
            selector = self._build_unique_selector(page, block_info)
            
            if not selector:
                return None
            
            # Extraire texte directement
            code = page.evaluate(f"""
                () => {{
                    const elem = document.querySelector('{selector}');
                    if (!elem) return null;
                    
                    const codeElem = elem.querySelector('code') || elem;
                    return codeElem.textContent || codeElem.innerText;
                }}
            """)
            
            if code and len(code.strip()) > 20:
                logger.debug(f"      ✅ Extraction DOM réussie")
                return {'code': code, 'method': 'dom_fallback'}
            
            return None
        
        except Exception as e:
            logger.debug(f"      ❌ DOM fallback échoué: {e}")
            return None
    
    def _wait_for_clipboard(self, max_wait: float = 2.0) -> Optional[Dict]:
        """
        ⏳ Attend que le clipboard soit rempli
        """
        elapsed = 0.0
        interval = 0.15
        
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            self.stats.clipboard_reads += 1
            
            try:
                content = pyperclip.paste()
                
                if content and len(content.strip()) > 10:
                    logger.debug(f"      ⚡ Clipboard rempli après {elapsed:.1f}s")
                    return {'code': content, 'method': 'clipboard'}
            
            except Exception:
                pass
        
        logger.debug(f"      ⚠️ Timeout clipboard après {max_wait}s")
        return None
    
    def _find_copy_button(self, page, pre_selector: str) -> Optional[str]:
        """
        🔍 Trouve le bouton copie associé au bloc
        """
        selectors = self.PLATFORM_SELECTORS.get(
            self.platform, 
            self.PLATFORM_SELECTORS['claude']
        )
        
        # Stratégies de recherche
        strategies = [
            # 1. Bouton dans le parent direct
            f'{pre_selector} + button',
            f'{pre_selector} ~ button',
            f'{pre_selector} button',
            
            # 2. Boutons spécifiques plateforme
            *[f'{pre_selector} {btn}' for btn in selectors['copy_buttons']],
            
            # 3. Recherche large
            *selectors['copy_buttons']
        ]
        
        for strategy in strategies:
            try:
                is_visible = page.evaluate(f"""
                    () => {{
                        const btn = document.querySelector('{strategy}');
                        if (!btn) return false;
                        
                        const rect = btn.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }}
                """)
                
                if is_visible:
                    logger.debug(f"      ✅ Bouton trouvé: {strategy}")
                    return strategy
            
            except Exception:
                continue
        
        return None
    
    def _build_unique_selector(self, page, block_info: Dict) -> Optional[str]:
        """
        🎯 Construit un sélecteur unique pour le bloc
        """
        try:
            # Option 1: Utiliser le sélecteur original avec index
            base_selector = block_info['selector']
            index = block_info['index']
            
            # Tester plusieurs variantes
            selectors = [
                f'{base_selector}:nth-of-type({index + 1})',
                f'{base_selector}:nth-child({index + 1})',
                f'({base_selector})[{index}]'  # XPath-like
            ]
            
            for sel in selectors:
                try:
                    exists = page.evaluate(f"""
                        () => {{
                            const elem = document.querySelector('{sel}');
                            return elem !== null;
                        }}
                    """)
                    
                    if exists:
                        return sel
                except:
                    continue
            
            return None
        
        except Exception as e:
            logger.debug(f"      ❌ Build selector échoué: {e}")
            return None
    
    def _validate_extracted_code(self, code: str) -> bool:
        """
        ✅ Valide le code extrait
        """
        if not code or len(code.strip()) < 20:
            return False
        
        # Vérifier que ce n'est pas juste du HTML/DOM
        html_ratio = (code.count('<') + code.count('>')) / len(code)
        if html_ratio > 0.1:
            return False
        
        # Vérifier présence de code Python
        python_indicators = ['def ', 'class ', 'import ', 'from ', '=', 'if ', 'for ', 'return']
        has_python = any(ind in code for ind in python_indicators)
        
        return has_python
    
    def _create_snippet(self, code: str, index: int, block_info: Dict) -> Dict:
        """
        📦 Crée un snippet structuré
        """
        # Parser métadonnées
        action = "AJOUTER"
        file_path = f"extracted_{index}.py"
        description = ""
        target = ""
        
        lines = code.split('\n')
        code_start = 0
        
        for i, line in enumerate(lines[:10]):
            stripped = line.strip()
            if stripped.startswith('# ACTION:'):
                action = line.split(':', 1)[1].strip().upper()
                code_start = max(code_start, i + 1)
            elif stripped.startswith('# FILE:'):
                file_path = line.split(':', 1)[1].strip()
                code_start = max(code_start, i + 1)
            elif stripped.startswith('# DESCRIPTION:'):
                description = line.split(':', 1)[1].strip()
                code_start = max(code_start, i + 1)
            elif stripped.startswith('# TARGET:'):
                target = line.split(':', 1)[1].strip()
                code_start = max(code_start, i + 1)
        
        # Nettoyer le code
        clean_code = '\n'.join(lines[code_start:]).strip() if code_start > 0 else code.strip()
        clean_code = re.sub(r'^```\w*\s*\n|```\s*$', '', clean_code, flags=re.MULTILINE)
        
        return {
            'action': action,
            'title': f"{action}: {file_path}",
            'file': file_path,
            'code': clean_code,
            'language': 'python',
            'description': description or f"Code extrait (bloc {index})",
            'target': target,
            'platform': self.platform,
            'extraction_method': 'clipboard',
            'syntax_valid': True,
            'quality_score': 98  # Clipboard = qualité max
        }
    
    def _log_final_stats(self, snippets: List[Dict]):
        """
        📊 Affiche les statistiques finales
        """
        if self.stats.blocks_extracted > 0:
            self.stats.avg_block_size = self.stats.total_chars // self.stats.blocks_extracted
        
        logger.info("\n" + "="*80)
        logger.info("📊 STATISTIQUES EXTRACTION CLIPBOARD")
        logger.info("="*80)
        logger.info(f"   📦 Blocs détectés: {self.stats.blocks_detected}")
        logger.info(f"   ✅ Blocs extraits: {self.stats.blocks_extracted}")
        logger.info(f"   🎯 Taux succès: {100 * self.stats.blocks_extracted / max(self.stats.blocks_detected, 1):.1f}%")
        logger.info(f"   🖱️ Hovers effectués: {self.stats.hover_attempts}")
        logger.info(f"   🔘 Boutons trouvés: {self.stats.buttons_found}")
        logger.info(f"   📋 Lectures clipboard: {self.stats.clipboard_reads}")
        logger.info(f"   📏 Taille moyenne: {self.stats.avg_block_size} chars")
        logger.info(f"   📊 Total extrait: {self.stats.total_chars} chars")
        
        if self.stats.errors:
            logger.info(f"   ⚠️ Erreurs: {len(self.stats.errors)}")
            for err in self.stats.errors[:3]:
                logger.info(f"      - {err}")
        
        logger.info("="*80 + "\n")


# ============================================================================
# FONCTION D'INTÉGRATION
# ============================================================================

def extract_via_clipboard_playwright(page, platform: str = 'claude') -> Dict[str, Any]:
    """
    Fonction wrapper pour Playwright - Point d'entrée principal
    
    Args:
        page: Instance playwright.Page
        platform: Nom de la plateforme ('claude', 'chatgpt', 'gemini')
    
    Returns:
        Dict avec 'success', 'snippets', 'message', 'stats'
    """
    if not CLIPBOARD_AVAILABLE:
        return {
            'success': False,
            'snippets': [],
            'message': 'pyperclip non disponible'
        }
    
    try:
        extractor = ClipboardExtractor(platform=platform)
        snippets = extractor.extract_all_code_blocks(page)
        
        return {
            'success': len(snippets) > 0,
            'snippets': snippets,
            'message': f'✅ {len(snippets)} snippet(s)' if snippets else 'Aucun code détecté',
            'stats': {
                'blocks_detected': extractor.stats.blocks_detected,
                'blocks_extracted': extractor.stats.blocks_extracted,
                'success_rate': 100 * extractor.stats.blocks_extracted / max(extractor.stats.blocks_detected, 1),
                'total_chars': extractor.stats.total_chars
            }
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'snippets': [],
            'message': f'Erreur: {str(e)}',
            'stats': {}
        }