"""
playwright_content_extractor.py - VERSION BROWSEROS NATIVE

✅ Extraction DIRECTE depuis la session BrowserOS active
❌ Plus de lancement de Playwright séparé
"""

import time
from typing import Dict, List, Optional, Any
from utils.logger import logger


class PlaywrightContentExtractor:
    """Extracteur de contenu utilisant la session BrowserOS ACTIVE"""
    
    def __init__(self, platform_name: str, browser_client=None):
        """
        Initialise l'extracteur avec le client BrowserOS actif
        
        Args:
            platform_name: Nom de la plateforme (claude, chatgpt, etc.)
            browser_client: Client BrowserOS déjà connecté
        """
        self.platform_name = platform_name.lower()
        self.client = browser_client
        
        if not self.client:
            raise ValueError("❌ Client BrowserOS requis ! Passer le client actif.")
        
        logger.info(f"✅ Extracteur initialisé avec session BrowserOS active ({self.platform_name})")
    
    def _execute_js(self, script: str) -> Any:
        """Exécute JavaScript via BrowserOS et retourne le résultat"""
        try:
            result = self.client.execute_javascript(script)
            
            if isinstance(result, dict):
                if "error" in result:
                    logger.error(f"❌ Erreur JS: {result['error']}")
                    return None
                if "result" in result:
                    return result["result"]
                return result
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Exception execute_js: {e}")
            return None
    
    def wait_for_response_complete(self, max_wait: float = 30.0) -> bool:
        """
        ✅ DÉTECTION ROBUSTE DU STREAMING CLAUDE
        Attend que la génération soit VRAIMENT terminée
        """
        logger.info("⏳ Attente de la fin de génération Claude...")
    
        start_time = time.time()
        stable_count = 0
        last_length = 0
        generation_detected = False
    
        while (time.time() - start_time) < max_wait:
            try:
                # 🎯 STRATÉGIE 1 : Vérifier TOUS les indicateurs de streaming
                streaming_status = self._execute_js("""
                    (() => {
                        // 🔴 INDICATEURS DE GÉNÉRATION ACTIVE
                        const streamingIndicators = {
                            // Bouton Stop présent
                            stopButton: !!document.querySelector('button[aria-label*="Stop"], button[aria-label*="Arrêt"]'),
                            
                            // Classes de streaming Claude
                            streamingClass: !!document.querySelector('[class*="streaming"], [class*="generating"]'),
                            
                            // Animations de curseur/pulse
                            cursorAnimation: !!document.querySelector('[class*="cursor"], [class*="blink"]'),
                            
                            // Texte incomplet (se termine par espace ou ellipse)
                            incompleteText: (() => {
                                const main = document.querySelector('main');
                                if (!main) return false;
                                const text = main.innerText.trim();
                                // Si se termine par "..." ou ellipse Unicode, génération en cours
                                return /[\.]{3}$|…$|\s{2,}$/.test(text);
                            })(),
                            
                            // Vérifier si le dernier message a un indicateur de typing
                            typingIndicator: !!document.querySelector('[data-testid*="typing"], [aria-live="polite"][class*="animate"]'),
                            
                            // Bouton Regenerate absent (apparaît après génération)
                            noRegenerateButton: !document.querySelector('button[aria-label*="Regenerate"], button[aria-label*="Régénérer"]')
                        };
                        
                        // Si UN SEUL indicateur est vrai, génération en cours
                        const isGenerating = Object.values(streamingIndicators).some(v => v);
                        
                        // Retourner détails pour debug
                        return {
                            isGenerating: isGenerating,
                            indicators: streamingIndicators,
                            contentLength: document.body?.innerText?.length || 0
                        };
                    })();
                """)
    
                if not streaming_status:
                    logger.debug("   ⚠️ Erreur récupération statut streaming")
                    time.sleep(2)
                    continue
                
                is_generating = streaming_status.get('isGenerating', False)
                current_length = streaming_status.get('contentLength', 0)
    
                # 🔴 Génération détectée
                if is_generating:
                    if not generation_detected:
                        logger.info("   🔴 Génération ACTIVE détectée")
                        generation_detected = True
                    
                    # Log périodique des indicateurs actifs
                    active = [k for k, v in streaming_status.get('indicators', {}).items() if v]
                    logger.debug(f"   🔄 Génération... ({current_length} chars, indicateurs: {', '.join(active)})")
                    
                    stable_count = 0
                    last_length = current_length
                    time.sleep(1.5)
                    continue
                
                # 🟢 Pas de génération détectée
                if not generation_detected:
                    # Première vérification : peut-être pas encore commencé
                    if time.time() - start_time < 5:
                        logger.debug("   ⏳ Attente démarrage génération...")
                        time.sleep(1)
                        continue
                    else:
                        logger.info("   ✅ Pas de génération détectée (contenu déjà prêt)")
                        return True
                
                # 🟡 Génération détectée précédemment, mais plus maintenant
                # Vérifier stabilité du contenu
                if current_length == last_length:
                    stable_count += 1
                    logger.debug(f"   🟡 Contenu stable ({stable_count}/3) - {current_length} chars")
                    
                    if stable_count >= 3:  # 4.5 secondes de stabilité
                        logger.info(f"   ✅ Génération terminée (contenu stable à {current_length} chars)")
                        
                        # ✅ VALIDATION FINALE : Vérifier que le bouton Regenerate est présent
                        final_check = self._execute_js("""
                            (() => {
                                return {
                                    hasRegenerateButton: !!document.querySelector('button[aria-label*="Regenerate"], button[aria-label*="Régénérer"]'),
                                    hasCodeBlocks: document.querySelectorAll('pre, code').length > 0,
                                    contentLength: document.body?.innerText?.length || 0
                                };
                            })();
                        """)
                        
                        if final_check and final_check.get('hasRegenerateButton'):
                            logger.info("   ✅ Bouton Regenerate confirmé - Génération complète")
                            return True
                        elif final_check and final_check.get('hasCodeBlocks'):
                            logger.info("   ✅ Code détecté - Génération probablement complète")
                            return True
                        else:
                            logger.warning("   ⚠️ Pas de bouton Regenerate, attente supplémentaire...")
                            time.sleep(2)
                            stable_count = 0
                else:
                    # Contenu change encore
                    stable_count = 0
                    last_length = current_length
                    logger.debug(f"   🔄 Contenu change : {last_length} → {current_length} chars")
    
                time.sleep(1.5)
    
            except Exception as e:
                logger.debug(f"   ⚠️ Erreur attente: {e}")
                time.sleep(1.5)
    
        logger.warning(f"⚠️ Timeout après {max_wait}s")
        
        # Diagnostic final
        try:
            final_state = self._execute_js("""
                (() => {
                    return {
                        hasStop: !!document.querySelector('button[aria-label*="Stop"]'),
                        hasRegen: !!document.querySelector('button[aria-label*="Regenerate"]'),
                        contentLength: document.body?.innerText?.length || 0,
                        codeBlocks: document.querySelectorAll('pre code').length
                    };
                })();
            """)
            logger.warning(f"   📊 État final : {final_state}")
        except:
            pass
        
        return False
    
    def get_last_response_content(self) -> str:
        """
        ✅ EXTRACTION DOM PROPRE via TreeWalker
        Évite la pollution DOM en parcourant intelligemment l'arbre
        """
        logger.info("📄 Extraction du contenu via TreeWalker...")

        # 🎯 STRATÉGIE 1 : TreeWalker pour extraction propre
        content = self._execute_js("""
            (() => {
                // Configuration du TreeWalker pour ne garder que les TEXT_NODE pertinents
                const walker = document.createTreeWalker(
                    document.querySelector('main') || document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: function(node) {
                            // Ignorer les nœuds vides
                            if (!node.textContent.trim()) {
                                return NodeFilter.FILTER_REJECT;
                            }

                            const parent = node.parentElement;
                            if (!parent) return NodeFilter.FILTER_REJECT;

                            // 🚫 FILTRAGE DES ÉLÉMENTS PARASITES

                            // Ignorer les boutons et contrôles UI
                            if (parent.tagName === 'BUTTON' || 
                                parent.closest('button, [role="button"]')) {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // Ignorer les éléments cachés
                            const style = window.getComputedStyle(parent);
                            if (style.display === 'none' || 
                                style.visibility === 'hidden' ||
                                style.opacity === '0') {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // Ignorer les scripts et styles
                            if (parent.tagName === 'SCRIPT' || 
                                parent.tagName === 'STYLE' ||
                                parent.tagName === 'NOSCRIPT') {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // Ignorer les éléments de navigation/header/footer
                            if (parent.closest('nav, header, footer, aside, [role="navigation"], [role="banner"]')) {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // Ignorer les tooltips, popups, modals
                            if (parent.closest('[role="tooltip"], [role="dialog"], [aria-hidden="true"]')) {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // Ignorer les éléments avec classes suspectes
                            const className = parent.className || '';
                            const suspectClasses = [
                                'button', 'btn', 'icon', 'menu', 
                                'toolbar', 'tooltip', 'modal', 'popup',
                                'header', 'footer', 'nav', 'sidebar'
                            ];

                            if (suspectClasses.some(cls => className.toLowerCase().includes(cls))) {
                                return NodeFilter.FILTER_REJECT;
                            }

                            // 🟢 ACCEPTER : Contenu principal
                            // Articles, paragraphes, code, listes
                            if (parent.closest('article, p, pre, code, li, blockquote, [class*="message"], [class*="response"], [class*="content"]')) {
                                return NodeFilter.FILTER_ACCEPT;
                            }

                            // Accepter si dans main/article
                            if (parent.closest('main, article, [role="main"]')) {
                                return NodeFilter.FILTER_ACCEPT;
                            }

                            return NodeFilter.FILTER_SKIP;
                        }
                    }
                );

                // Collecter le texte en préservant la structure
                const textParts = [];
                const seenTexts = new Set();

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();

                    // Éviter les doublons
                    if (text && !seenTexts.has(text)) {
                        seenTexts.add(text);

                        // Ajouter séparateur si c'est un nouveau bloc
                        const parent = node.parentElement;
                        if (parent && (
                            parent.tagName === 'P' || 
                            parent.tagName === 'DIV' ||
                            parent.tagName === 'LI'
                        )) {
                            if (textParts.length > 0) {
                                textParts.push('\n');
                            }
                        }

                        textParts.push(text);
                    }
                }

                return textParts.join(' ').trim();
            })();
        """)

        if content and len(content) > 100:
            logger.info(f"✅ TreeWalker : {len(content)} caractères extraits")
            return content.strip()

        # 🔄 STRATÉGIE 2 : Fallback avec sélecteurs spécifiques Claude
        logger.info("🔄 Fallback : sélecteurs spécifiques...")

        content = self._execute_js("""
            (() => {
                // Chercher spécifiquement les messages Claude
                const selectors = [
                    // Messages Claude
                    '[class*="font-claude-message"]',
                    '[class*="prose"]',
                    'article',
                    // Conteneurs de contenu
                    'main [class*="message"]',
                    'main [class*="response"]',
                    'main [class*="content"]',
                    // Fallback large
                    'main'
                ];

                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);

                    if (elements.length > 0) {
                        // Prendre le dernier élément (message le plus récent)
                        const lastElement = elements[elements.length - 1];

                        // Cloner pour nettoyage
                        const clone = lastElement.cloneNode(true);

                        // Supprimer éléments parasites du clone
                        const toRemove = clone.querySelectorAll(
                            'button, [role="button"], script, style, ' +
                            'nav, header, footer, aside, ' +
                            '[role="navigation"], [aria-hidden="true"]'
                        );

                        toRemove.forEach(el => el.remove());

                        const text = clone.innerText || clone.textContent;

                        if (text && text.length > 100) {
                            return text;
                        }
                    }
                }

                return '';
            })();
        """)

        if content and len(content) > 100:
            logger.info(f"✅ Fallback : {len(content)} caractères extraits")
            return content.strip()

        logger.error("❌ Aucun contenu extractible trouvé")

        # 🔍 DIAGNOSTIC
        structure = self._execute_js("""
            (() => {
                return {
                    url: window.location.href,
                    hasMain: !!document.querySelector('main'),
                    bodyLength: document.body.innerText.length,
                    messageCount: document.querySelectorAll('[class*="message"]').length,
                    articleCount: document.querySelectorAll('article').length,
                    claudeMessages: document.querySelectorAll('[class*="font-claude"]').length,
                    proseElements: document.querySelectorAll('[class*="prose"]').length
                };
            })();
        """)

        logger.error(f"🔍 Structure HTML : {structure}")

        return ""
    
    def get_code_blocks_clean(self) -> List[Dict[str, str]]:
        """Extrait tous les blocs de code proprement"""
        logger.info("🔍 Extraction des blocs de code...")
        
        blocks_data = self._execute_js("""
            (() => {
                const blocks = [];
                const codeElements = document.querySelectorAll('pre code, code[class*="language-"], pre');
                
                codeElements.forEach(elem => {
                    const code = elem.innerText || elem.textContent;
                    const className = elem.className || '';
                    
                    // Détecter le langage
                    let language = 'python';
                    const langMatch = className.match(/language-(\\w+)/);
                    if (langMatch) {
                        language = langMatch[1];
                    }
                    
                    // Filtrer les blocs trop courts
                    if (code && code.trim().length > 20) {
                        blocks.push({
                            language: language,
                            code: code.trim()
                        });
                    }
                });
                
                return blocks;
            })();
        """)
        
        if blocks_data and isinstance(blocks_data, list):
            logger.info(f"✅ {len(blocks_data)} bloc(s) de code extraits")
            return blocks_data
        
        logger.warning("⚠️ Aucun bloc de code trouvé")
        return []
    
    def extract_full_response_with_metadata(self) -> Dict[str, Any]:
        """Extrait la réponse complète avec métadonnées"""
        logger.info("📦 Extraction complète de la réponse...")
        
        # Attendre la fin de génération
        self.wait_for_response_complete()
        
        # Sécurité : attendre 1s supplémentaire
        time.sleep(1)
        
        # Extraire le texte
        text_content = self.get_last_response_content()
        
        # Extraire les blocs de code
        code_blocks = self.get_code_blocks_clean()
        
        # Métadonnées
        metadata = self._execute_js("""
            (() => {
                return {
                    url: window.location.href,
                    title: document.title
                };
            })();
        """)
        
        result = {
            'success': len(text_content) > 0,
            'platform': self.platform_name,
            'url': metadata.get('url', '') if metadata else '',
            'page_title': metadata.get('title', '') if metadata else '',
            'text': text_content,
            'code_blocks': code_blocks,
            'total_chars': len(text_content),
            'code_blocks_count': len(code_blocks),
        }
        
        logger.info(f"✅ Extraction : {result['total_chars']} chars, {result['code_blocks_count']} blocs")
        
        return result


# ============================================================================
# ✅ FONCTION INDÉPENDANTE (PAS UNE MÉTHODE DE CLASSE)
# ============================================================================

def extract_response_with_browseros(
    browser_client,
    platform_name: str,
    wait_response: bool = True,
    max_wait: float = 15.0  # ✅ Réduit de 30s → 15s
) -> Dict[str, Any]:
    """Extraction depuis session BrowserOS active"""
    try:
        if not browser_client:
            raise ValueError("❌ browser_client requis !")
        
        logger.info(f"🔗 Extraction depuis session BrowserOS active ({platform_name})")
        
        extractor = PlaywrightContentExtractor(platform_name, browser_client)
        
        if wait_response:
            # Vérifier d'abord si le contenu est déjà disponible
            quick_check = extractor._execute_js("""
                (() => {
                    const main = document.querySelector('main');
                    const text = main ? main.innerText : '';
                    return text.length > 1000;  // Si > 1000 chars, probablement prêt
                })();
            """)
            
            if not quick_check:
                logger.info("⏳ Contenu pas encore prêt, attente...")
                extractor.wait_for_response_complete(max_wait=max_wait)
            else:
                logger.info("✅ Contenu déjà disponible, pas d'attente")
        
        result = extractor.extract_full_response_with_metadata()
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction BrowserOS : {e}")
        return {
            'success': False,
            'error': str(e),
            'text': '',
            'code_blocks': [],
            'platform': platform_name
        }