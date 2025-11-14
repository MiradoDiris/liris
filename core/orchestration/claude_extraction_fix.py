import asyncio
import re
import time
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Page, Browser


# ============================================================================
# 🔥 NOUVEAU : EXTRACTEUR CLAUDE ANTI-CORRUPTION
# ============================================================================

class ClaudeExtractionFixed:
    """Extracteur optimisé pour Claude.ai avec stratégie anti-corruption"""
    
    @staticmethod
    async def extract_from_active_conversation(page_url: str, max_wait: int = 30) -> Dict:
        """
        🎯 EXTRACTION DEPUIS CONVERSATION ACTIVE
        
        Args:
            page_url: URL de la conversation Claude (ex: https://claude.ai/chat/xxx)
            max_wait: Timeout maximum
            
        Returns:
            {'success': bool, 'snippets': List[Dict], 'raw_text': str}
        """
        
        print(f"\n{'='*80}")
        print("🚀 EXTRACTION CLAUDE ANTI-CORRUPTION v2.0")
        print(f"{'='*80}")
        print(f"🔗 URL: {page_url}")
    
        if not re.search(r'claude\.ai/chat/[a-f0-9-]+', page_url):
            print(f"❌ URL invalide, doit contenir /chat/xxx")
            return {'success': False, 'snippets': [], 'error': 'Invalid URL'}
        
        playwright = None
        browser = None
        
        try:
            playwright = await async_playwright().start()
            
            # ✅ MODE VISIBLE pour debug (headless=False)
            browser = await playwright.chromium.launch(
                headless=False,  # 🔥 VISIBLE pour debug
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            page = await context.new_page()
            
            print(f"🌐 Navigation vers conversation active...")
            await page.goto(page_url, wait_until='domcontentloaded', timeout=15000)
            
            # ⏳ ATTENDRE QUE LE DERNIER MESSAGE SOIT VISIBLE
            print(f"⏳ Attente du dernier message Claude...")
            
            start_time = time.time()
            last_message_selector = 'div[class*="font-claude-message"]:last-of-type'
            
            try:
                await page.wait_for_selector(last_message_selector, timeout=max_wait * 1000)
                print(f"✅ Message détecté")
            except:
                print(f"⚠️ Timeout attente message, tentative extraction quand même...")
            
            # 🔍 EXTRACTION AVEC JAVASCRIPT INTELLIGENT
            print(f"\n🔍 Extraction du contenu...")
            
            extraction_result = await page.evaluate("""
                () => {
                    // 🎯 STRATÉGIE 1 : Chercher tous les messages Claude
                    const claudeMessages = document.querySelectorAll('[class*="font-claude-message"]');
                    
                    if (claudeMessages.length === 0) {
                        return {
                            success: false,
                            error: 'Aucun message Claude trouvé',
                            debugInfo: {
                                url: window.location.href,
                                bodyLength: document.body.innerText.length
                            }
                        };
                    }
                    
                    // 🎯 PRENDRE LE DERNIER MESSAGE
                    const lastMessage = claudeMessages[claudeMessages.length - 1];
                    
                    // 🔥 EXTRACTION DU TEXTE BRUT (évite la corruption)
                    let fullText = lastMessage.innerText || lastMessage.textContent;
                    
                    // 🎯 CHERCHER LES BLOCS DE CODE
                    const codeBlocks = [];
                    const preElements = lastMessage.querySelectorAll('pre');
                    
                    preElements.forEach((pre, idx) => {
                        const codeElement = pre.querySelector('code');
                        const codeText = codeElement ? codeElement.textContent : pre.textContent;
                        
                        if (codeText && codeText.length > 50) {
                            // 🔍 CHERCHER LES MÉTADONNÉES DANS LE CODE
                            const actionMatch = codeText.match(/# ACTION:\s*(\w+)/i);
                            const fileMatch = codeText.match(/# FILE:\s*([^\n]+)/i);
                            
                            codeBlocks.push({
                                index: idx,
                                code: codeText.trim(),
                                action: actionMatch ? actionMatch[1].toUpperCase() : 'AJOUTER',
                                file: fileMatch ? fileMatch[1].trim() : `generated_${idx}.py`,
                                hasMetadata: !!(actionMatch && fileMatch)
                            });
                        }
                    });
                    
                    return {
                        success: true,
                        fullText: fullText,
                        codeBlocks: codeBlocks,
                        messageCount: claudeMessages.length,
                        debugInfo: {
                            url: window.location.href,
                            lastMessageLength: fullText.length,
                            preCount: preElements.length
                        }
                    };
                }
            """)
            
            if not extraction_result.get('success'):
                print(f"❌ Échec extraction: {extraction_result.get('error')}")
                print(f"📊 Debug: {extraction_result.get('debugInfo')}")
                return {
                    'success': False,
                    'snippets': [],
                    'error': extraction_result.get('error'),
                    'debug': extraction_result.get('debugInfo')
                }
            
            # ✅ RÉSULTATS
            code_blocks = extraction_result.get('codeBlocks', [])
            full_text = extraction_result.get('fullText', '')
            
            print(f"\n✅ EXTRACTION RÉUSSIE")
            print(f"   📝 Texte complet: {len(full_text)} chars")
            print(f"   📦 Blocs de code: {len(code_blocks)}")
            
            # 🔥 TRANSFORMER EN SNIPPETS
            snippets = []
            
            for block in code_blocks:
                snippet = {
                    'action': block['action'],
                    'file': block['file'],
                    'code': block['code'],
                    'language': 'python',
                    'title': f"{block['action']} - {block['file']}",
                    'description': 'Extrait par extraction anti-corruption',
                    'has_metadata': block['hasMetadata'],
                    'quality_score': 95 if block['hasMetadata'] else 70
                }
                snippets.append(snippet)
                
                print(f"\n📦 Snippet {len(snippets)}:")
                print(f"   Action: {block['action']}")
                print(f"   Fichier: {block['file']}")
                print(f"   Code: {len(block['code'])} chars")
                print(f"   Métadonnées: {'✅' if block['hasMetadata'] else '❌'}")
            
            elapsed = time.time() - start_time
            print(f"\n⏱️ Temps total: {elapsed:.1f}s")
            print(f"{'='*80}\n")
            
            return {
                'success': True,
                'snippets': snippets,
                'raw_text': full_text,
                'extraction_time': elapsed,
                'debug': extraction_result.get('debugInfo')
            }
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'snippets': [],
                'error': str(e)
            }
        
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()


# ============================================================================
# 🔥 INTÉGRATION DANS UNIVERSAL_BROWSER_HANDLER
# ============================================================================

def integrate_fixed_extraction():
    """
    🔧 MODIFICATIONS À FAIRE DANS universal_browser_handler.py
    
    1. REMPLACER la section Playwright (ligne ~580) par :
    """
    
    code_integration = '''
    if self.use_playwright:
        logger.info("🎭 Extraction avec Playwright ANTI-CORRUPTION")
        try:
            # 🔥 IMPORTER LE NOUVEAU EXTRACTEUR
            from core.orchestration.claude_extraction_fix import ClaudeExtractionFixed
            
            # ✅ RÉCUPÉRER L'URL DE CONVERSATION ACTIVE
            current_url_result = self.client.get_url()
            
            if "error" not in current_url_result and "result" in current_url_result:
                current_url = current_url_result["result"].get("url", self.config['url'])
                
                logger.info(f"🔗 URL conversation: {current_url}")
                
                # 🔥 UTILISER LE NOUVEL EXTRACTEUR
                playwright_result = asyncio.run(
                    ClaudeExtractionFixed.extract_from_active_conversation(
                        page_url=current_url,
                        max_wait=30  # ✅ Timeout réduit
                    )
                )
                
                if playwright_result.get('success'):
                    snippets = playwright_result['snippets']
                    extraction_method = "playwright_fixed"
                    
                    logger.info(f"✅ {len(snippets)} snippets extraits (ANTI-CORRUPTION)")
                    logger.info(f"⏱️ Temps: {playwright_result.get('extraction_time', 0):.1f}s")
                    
                    # ✅ SAUTER LA RÉPARATION (code déjà propre)
                    # Passer directement au formatage...
                    
        except Exception as e:
            logger.warning(f"⚠️ Erreur extraction fixe: {e}")
    '''
    
    return code_integration


# ============================================================================
# 🧪 TEST STANDALONE
# ============================================================================

async def test_extraction():
    """Test avec une vraie URL de conversation"""
    
    # ⚠️ REMPLACER PAR VOTRE URL DE CONVERSATION CLAUDE
    test_url = "https://claude.ai/chat/votre-conversation-id"
    
    result = await ClaudeExtractionFixed.extract_from_active_conversation(
        page_url=test_url,
        max_wait=30
    )
    
    if result['success']:
        print(f"\n✅ SUCCÈS!")
        print(f"📦 {len(result['snippets'])} snippets extraits")
        
        for idx, snippet in enumerate(result['snippets'], 1):
            print(f"\nSnippet {idx}:")
            print(f"  Fichier: {snippet['file']}")
            print(f"  Code (extrait): {snippet['code'][:200]}...")
    else:
        print(f"\n❌ ÉCHEC: {result.get('error')}")


if __name__ == "__main__":
    # ✅ TEST
    asyncio.run(test_extraction())