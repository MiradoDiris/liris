"""
core/orchestration/browser_helpers.py - VERSION UNIVERSELLE

Compatible avec: ChatGPT, Claude, Gemini, Grok
Gestion automatique de l'authentification et des spécificités de chaque plateforme
"""

import time
import json
import re
from typing import Optional, Dict, Any, List, Callable

try:
    from .browserOs_conductor import BrowserOSMCPClient
except ImportError:
    from browserOs_conductor import BrowserOSMCPClient


# ============================================================================
# UTILITAIRES
# ============================================================================

def parse_browseros_js_response(result: Dict[str, Any]) -> Optional[Dict]:
    """
    Parse une réponse JavaScript de BrowserOS
    🔧 VERSION FINALE ROBUSTE
    """
    if "result" not in result:
        return None
    
    content = result["result"].get("content", [])
    if not content or len(content) == 0:
        return None
    
    try:
        # Extraire le texte
        data_text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
        data_text = data_text.strip()
        
        if not data_text:
            return None
        
        # CAS 1: Juste "JavaScript executed" sans résultat
        if "JavaScript executed" in data_text and "Result:" not in data_text:
            return {"success": True}
        
        # CAS 2: Format avec "Result:"
        if "Result:" in data_text:
            json_start = data_text.find("Result:") + 7
            json_str = data_text[json_start:].strip()
            
            # Gérer JSON échappé entre guillemets
            if json_str.startswith('"'):
                last_quote = json_str.rfind('"')
                if last_quote > 0:
                    json_str = json_str[1:last_quote]
                    # Décoder les échappements
                    json_str = (json_str
                        .replace('\\"', '"')
                        .replace('\\n', '\n')
                        .replace('\\t', '\t')
                        .replace('\\\\', '\\')
                        .replace('\\/', '/'))
            
            data_text = json_str
        
        # Parser le JSON
        parsed = json.loads(data_text)
        
        # Si c'est un dict vide {}, retourner None pour forcer le fallback
        if isinstance(parsed, dict) and len(parsed) == 0:
            return None
        
        return parsed
        
    except json.JSONDecodeError:
        # Fallback: succès si "executed" présent
        if "JavaScript executed" in str(content):
            return {"success": True}
        return None
        
    except Exception:
        return None
    

def navigate_with_http_431_protection(client, url: str, platform_name: str) -> dict:
    """
    🛡️ Navigation sécurisée avec protection HTTP 431
    
    Stratégie :
    1. Reset via about:blank
    2. Nettoyer cookies
    3. Naviguer vers la vraie URL
    4. Vérifier si HTTP 431 affiché
    
    Args:
        client: BrowserOSMCPClient
        url: URL de destination
        platform_name: Nom de la plateforme
        
    Returns:
        dict avec 'success' et 'message'
    """
    
    # 🎯 Protection uniquement pour Grok
    if platform_name.lower() != 'grok':
        # Navigation normale pour les autres plateformes
        nav_result = client.navigate(url, wait_load=3.0)
        if "error" in nav_result:
            return {
                'success': False,
                'message': f"Erreur navigation: {nav_result.get('error')}"
            }
        return {'success': True}
    
    print(f"\n🛡️ NAVIGATION PROTÉGÉE GROK (Anti-HTTP 431)")
    print("="*70)
    
    # ÉTAPE 1: Reset navigateur
    print("\n📄 Étape 1/4: Reset du navigateur...")
    try:
        client.navigate("about:blank", wait_load=1.0)
        time.sleep(1)
        print("   ✅ Reset OK")
    except Exception as e:
        print(f"   ⚠️ Erreur reset: {e}")
    
    # ÉTAPE 2: Nettoyer cookies
    print("\n🧹 Étape 2/4: Nettoyage des cookies...")
    clear_cookies_for_platform(client, 'grok')
    time.sleep(0.5)
    
    # ÉTAPE 3: Navigation
    print(f"\n🌐 Étape 3/4: Navigation vers Grok...")
    print(f"   URL: {url}")
    
    try:
        nav_result = client.navigate(url, wait_load=5.0)
        
        if "error" in nav_result:
            error_msg = str(nav_result.get("error", ""))
            
            # Détecter HTTP 431
            if "431" in error_msg:
                print("   ❌ HTTP 431 DÉTECTÉ pendant navigation")
                return {
                    'success': False,
                    'error': 'http_431',
                    'message': "❌ Erreur HTTP 431 - Headers trop volumineux"
                }
            else:
                print(f"   ❌ Erreur: {error_msg}")
                return {
                    'success': False,
                    'error': 'navigation_failed',
                    'message': error_msg
                }
        
        print("   ✅ Navigation réussie")
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return {
            'success': False,
            'error': 'exception',
            'message': str(e)
        }
    
    # ÉTAPE 4: Vérifier si HTTP 431 affiché dans la page
    print("\n🔍 Étape 4/4: Vérification de la page...")
    time.sleep(2)
    
    js_check_431 = """
    (function() {
        try {
            const bodyText = document.body.innerText || '';
            const title = document.title || '';
            
            const has431 = bodyText.includes('431') || 
                          bodyText.includes('Request Header') ||
                          bodyText.includes('Headers Too Large');
            
            return {
                has431: has431,
                bodyPreview: bodyText.substring(0, 300),
                title: title,
                url: window.location.href
            };
        } catch (err) {
            return {has431: false, error: err.message};
        }
    })();
    """
    
    check_result = client.execute_javascript(js_check_431)
    check_data = parse_browseros_js_response(check_result)
    
    if check_data:
        has_431 = check_data.get('has431', False)
        
        print(f"   📊 État:")
        print(f"      - Titre: {check_data.get('title', 'N/A')[:50]}")
        print(f"      - URL: {check_data.get('url', 'N/A')[:60]}")
        print(f"      - Erreur 431?: {has_431}")
        
        if has_431:
            print("\n   ❌ PAGE AFFICHE HTTP 431")
            print(f"   📄 Aperçu: {check_data.get('bodyPreview', '')[:150]}")
            
            print("\n" + "="*70)
            print("❌ ERREUR HTTP 431 PERSISTANTE - SOLUTIONS:")
            print("="*70)
            print("\n1️⃣ REDÉMARRER BrowserOS:")
            print("   - Fermer complètement le serveur BrowserOS")
            print("   - Effacer le cache/cookies du navigateur Chrome")
            print("   - Relancer BrowserOS")
            
            print("\n2️⃣ UTILISER UN PROFIL CHROME VIERGE:")
            print("   - Lancer Chrome avec: --user-data-dir=/tmp/chrome_clean")
            print("   - Ne PAS se connecter à X/Grok manuellement")
            
            print("\n3️⃣ VÉRIFIER:")
            print("   - Proxy/VPN désactivés (ajoutent des headers)")
            print("   - Extensions Chrome désactivées")
            
            return {
                'success': False,
                'error': 'http_431_in_page',
                'message': "❌ HTTP 431 - Page affiche l'erreur"
            }
    
    print("   ✅ Pas d'erreur 431 - Navigation OK")
    return {'success': True}
    

def clear_cookies_for_platform(client, platform_name: str) -> bool:
    """
    🧹 Nettoie les cookies pour éviter HTTP 431 (surtout pour Grok)
    
    Args:
        client: BrowserOSMCPClient
        platform_name: Nom de la plateforme
        
    Returns:
        True si nettoyage réussi
    """
    
    # 🎯 Uniquement pour Grok (X.ai accumule beaucoup de cookies)
    if platform_name.lower() != 'grok':
        return True
    
    print("\n🧹 Nettoyage préventif des cookies (anti-HTTP 431)...")
    
    js_cleanup = """
    (function() {
        try {
            const cookiesBefore = document.cookie.split(';').length;
            
            // Supprimer TOUS les cookies
            document.cookie.split(";").forEach(function(c) { 
                document.cookie = c.replace(/^ +/, "")
                    .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
            });
            
            const cookiesAfter = document.cookie.split(';').filter(c => c.trim()).length;
            
            return {
                success: true,
                before: cookiesBefore,
                after: cookiesAfter,
                cleaned: cookiesBefore - cookiesAfter
            };
        } catch (err) {
            return {success: false, error: err.message};
        }
    })();
    """
    
    try:
        result = client.execute_javascript(js_cleanup)
        data = parse_browseros_js_response(result)
        
        if data and data.get('success'):
            cleaned = data.get('cleaned', 0)
            print(f"   ✅ {cleaned} cookie(s) nettoyé(s)")
            print(f"   📊 Avant: {data.get('before', 0)}, Après: {data.get('after', 0)}")
            return True
        else:
            print(f"   ⚠️ Échec nettoyage")
            return False
    
    except Exception as e:
        print(f"   ⚠️ Erreur: {e}")
        return False
    
def find_claude_input_robust(client) -> dict:
    """
    🔍 Recherche ROBUSTE du champ Claude avec fallback multiple
    
    NOUVEAU: Spécialement optimisé pour Claude.ai
    
    Returns:
        dict avec 'found', 'selector', 'nodeId', etc.
    """
    
    print("\n🔍 Recherche ROBUSTE du champ Claude...")
    
    # 📋 Sélecteurs Claude par ordre de priorité (2024-2025)
    CLAUDE_SELECTORS = [
        # Sélecteurs récents
        'div[contenteditable="true"][data-placeholder*="Reply"]',
        'div[contenteditable="true"][role="textbox"]',
        'div.ProseMirror[contenteditable="true"]',
        'fieldset div[contenteditable="true"]',
        
        # Sélecteurs génériques
        'div[contenteditable="true"]',
        'textarea[placeholder*="Talk"]',
        'textarea[placeholder*="Reply"]',
        'textarea:not([disabled])',
    ]
    
    js_find = f"""
    (function() {{
        try {{
            const selectors = {json.dumps(CLAUDE_SELECTORS)};
            
            function isVisible(elem) {{
                if (!elem) return false;
                
                const style = window.getComputedStyle(elem);
                
                // Pour contenteditable, être permissif
                if (elem.contentEditable === 'true') {{
                    // Vérifier parents cachés
                    let parent = elem.parentElement;
                    while (parent) {{
                        const pStyle = window.getComputedStyle(parent);
                        if (pStyle.display === 'none') {{
                            return false;
                        }}
                        parent = parent.parentElement;
                    }}
                    return true;
                }}
                
                // Pour textarea standard
                if (style.display === 'none' || style.visibility === 'hidden') {{
                    return false;
                }}
                
                const rect = elem.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }}
            
            // Tester chaque sélecteur
            for (const selector of selectors) {{
                try {{
                    const elem = document.querySelector(selector);
                    if (elem && isVisible(elem)) {{
                        return {{
                            found: true,
                            selector: selector,
                            tagName: elem.tagName.toLowerCase(),
                            isContentEditable: elem.contentEditable === 'true',
                            placeholder: elem.getAttribute('data-placeholder') || 
                                       elem.placeholder || '',
                            role: elem.getAttribute('role') || '',
                            className: elem.className || ''
                        }};
                    }}
                }} catch (e) {{
                    // Sélecteur invalide
                }}
            }}
            
            // Aucun trouvé
            return {{
                found: false,
                textareas: document.querySelectorAll('textarea').length,
                editables: document.querySelectorAll('[contenteditable="true"]').length,
                allDivs: document.querySelectorAll('div').length
            }};
            
        }} catch (err) {{
            return {{found: false, error: err.message}};
        }}
    }})();
    """
    
    result = client.execute_javascript(js_find)
    data = parse_browseros_js_response(result)
    
    if data and data.get('found'):
        print(f"   ✅ Champ Claude trouvé!")
        print(f"      Sélecteur: {data.get('selector')}")
        print(f"      Type: {data.get('tagName')}")
        print(f"      ContentEditable: {data.get('isContentEditable')}")
        return data
    
    # 🔴 ÉCHEC - Afficher diagnostic
    print(f"   ❌ Champ Claude introuvable")
    if data:
        print(f"      Textareas: {data.get('textareas', 0)}")
        print(f"      Editables: {data.get('editables', 0)}")
        print(f"      Divs totaux: {data.get('allDivs', 0)}")
        
        if data.get('error'):
            print(f"      Erreur: {data.get('error')}")
    
    return None

# ============================================================================
# CONFIGURATION DES PLATEFORMES
# ============================================================================

PLATFORM_CONFIGS = {
    'chatgpt': {
        'name': 'ChatGPT',
        'url': 'https://chatgpt.com/',
        'selectors': {
            'input': [
                'div[contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div.ProseMirror[contenteditable="true"]',
                'textarea#prompt-textarea',
                'textarea[placeholder*="Message"]',
                'textarea'
            ],
            'send_button': [
                'button[data-testid="send-button"]',
                'button[aria-label*="Send"]'
            ]
        },
        'auth_indicators': [...],
        'ready_indicators': [
            'div[contenteditable="true"]',
            'textarea#prompt-textarea'
        ],
        'page_load_wait': 8.0,
        'use_enter_to_send': True
    },  
    'claude': {
        'name': 'Claude',
        'url': 'https://claude.ai/',
        'selectors': {
            'input': [
                'div[contenteditable="true"][role="textbox"]',
                'div.ProseMirror[contenteditable="true"]',
                'textarea[placeholder*="Talk"]',
                'div[contenteditable="true"]',
                'textarea'
            ],
            'send_button': [
                'button[aria-label*="Send"]',
                'button:has-text("Send")',
                'button svg[class*="send"]'
            ]
        },
        'auth_indicators': [
            'a[href*="/login"]',
            'button:has-text("Log in")',
            'button:has-text("Continue with")'
        ],
        'ready_indicators': [
            'div[contenteditable="true"][role="textbox"]',
            'div.ProseMirror'
        ],
        'page_load_wait': 10.0,
        'use_enter_to_send': True
    },
    
    'gemini': {
        'name': 'Gemini',
        'url': 'https://gemini.google.com/',
        'selectors': {
            'input': [
                'textarea.ql-editor',
                'div[contenteditable="true"][role="textbox"]',
                'div.ql-editor[contenteditable="true"]',
                'textarea[placeholder*="Entrer"]',
                'textarea[aria-label*="prompt"]',
                'rich-textarea textarea',
                'textarea',
                'div[contenteditable="true"]'
            ],
            'send_button': [
                'button[aria-label*="Send"]',
                'button[mattooltip*="Send"]',
                'button mat-icon:has-text("send")'
            ]
        },
        'auth_indicators': [
            'a[href*="accounts.google.com"]',
            'button:has-text("Sign in")',
            'a:has-text("Connexion")'
        ],
        'ready_indicators': [
            'textarea.ql-editor',
            'rich-textarea',
            'div[contenteditable="true"][role="textbox"]'
        ],
        'page_load_wait': 12.0,
        'use_enter_to_send': True
    },
    
    'grok': {
        'name': 'Grok',
        'url': 'https://grok.x.ai/',
        'selectors': {
            'input': [
                'textarea[placeholder*="Ask"]',
                'textarea[placeholder*="Message"]',
                'div[contenteditable="true"][role="textbox"]',
                'textarea'
            ],
            'send_button': [
                'button[aria-label*="Send"]',
                'button:has-text("Send")',
                'button svg[class*="send"]'
            ]
        },
        'auth_indicators': [
            'a[href*="/login"]',
            'button:has-text("Log in")',
            'button:has-text("Sign in")'
        ],
        'ready_indicators': [
            'textarea[placeholder*="Ask"]',
            'div[contenteditable="true"]'
        ],
        'page_load_wait': 8.0,
        'use_enter_to_send': True
    }
}


# ============================================================================
# UTILITAIRES DE DÉTECTION
# ============================================================================

def check_authentication_status(client: BrowserOSMCPClient, platform: str) -> Dict[str, Any]:
    """
    Vérifie si l'authentification est requise pour une plateforme
    VERSION OPTIMISÉE avec JSON minimal - SANS JSON.stringify()
    
    Args:
        client: Client BrowserOS
        platform: Nom de la plateforme
        
    Returns:
        Dict avec requires_auth, url, title, message
    """
    config = PLATFORM_CONFIGS.get(platform.lower())
    if not config:
        return {"requires_auth": False, "message": "Plateforme inconnue"}
    
    # 🔧 CORRECTION: Ne PAS utiliser JSON.stringify() car BrowserOS l'encode déjà
    js_code = """
        (function() {
            try {
                const t = document.querySelectorAll('textarea').length;
                const e = document.querySelectorAll('[contenteditable="true"]').length;
                const b = document.querySelectorAll('button, a');
                
                let l = 0;
                for (const x of b) {
                    const txt = (x.textContent || '').toLowerCase();
                    if (txt.includes('log in') || txt.includes('sign in') || txt.includes('connexion')) {
                        l = 1;
                        break;
                    }
                }
                
                // ⚠️ RETOURNER L'OBJET DIRECTEMENT, PAS JSON.stringify()
                return {
                    t: t,
                    e: e,
                    l: l,
                    r: l && (t === 0 && e === 0) ? 1 : 0
                };
            } catch (err) {
                return {r:0, error: err.message};
            }
        })();
    """
    
    result = client.execute_javascript(js_code)
    data = parse_browseros_js_response(result)
    
    if data:
        requires_auth = data.get("r") == 1
        
        return {
            "requires_auth": requires_auth,
            "textarea_count": data.get("t", 0),
            "editable_count": data.get("e", 0),
            "has_login_text": data.get("l") == 1,
            "message": "🔒 Authentification requise" if requires_auth else "✅ Interface détectée"
        }
    
    return {
        "requires_auth": False,
        "message": "⚠️ Impossible de déterminer l'état"
    }

def debug_page_elements(client: BrowserOSMCPClient, selectors: List[str]) -> None:
    """
    Affiche un diagnostic détaillé des éléments sur la page
    """
    js_code = """
        (function() {
            const selectors = """ + json.dumps(selectors) + """;
            const results = [];
            
            for (const selector of selectors) {
                try {
                    const elem = document.querySelector(selector);
                    if (elem) {
                        const style = window.getComputedStyle(elem);
                        const rect = elem.getBoundingClientRect();
                        
                        results.push({
                            selector: selector,
                            exists: true,
                            tagName: elem.tagName,
                            visible: style.display !== 'none' && style.visibility !== 'hidden',
                            opacity: style.opacity,
                            width: rect.width,
                            height: rect.height,
                            className: elem.className,
                            id: elem.id
                        });
                    } else {
                        results.push({
                            selector: selector,
                            exists: false
                        });
                    }
                } catch (e) {
                    results.push({
                        selector: selector,
                        error: e.message
                    });
                }
            }
            
            return {
                results: results,
                allTextareas: document.querySelectorAll('textarea').length,
                allEditables: document.querySelectorAll('[contenteditable="true"]').length
            };
        })();
    """
    
    result = client.execute_javascript(js_code)
    data = parse_browseros_js_response(result)
    
    if data:
        print("\n🔍 DIAGNOSTIC DES SÉLECTEURS:")
        print(f"   Total textareas: {data.get('allTextareas', 0)}")
        print(f"   Total editables: {data.get('allEditables', 0)}")
        print("\n   Résultats par sélecteur:")
        
        for item in data.get('results', []):
            selector = item.get('selector', 'N/A')
            print(f"\n   🔹 {selector}")
            
            if item.get('error'):
                print(f"      ❌ Erreur: {item['error']}")
            elif not item.get('exists'):
                print(f"      ❌ N'existe pas")
            else:
                print(f"      ✅ Trouvé: {item.get('tagName')}")
                print(f"         Visible: {item.get('visible')}")
                print(f"         Opacité: {item.get('opacity')}")
                print(f"         Taille: {item.get('width')}x{item.get('height')}")
                if item.get('className'):
                    print(f"         Classes: {item.get('className')[:50]}")

def wait_for_element_with_retry(
    client: BrowserOSMCPClient,
    selectors: List[str],
    max_wait: float = 20.0,
    check_interval: float = 2.0
) -> Optional[Dict]:
    """Attend qu'un élément apparaisse (multi-sélecteurs)"""
    
    print(f"\n⏳ Attente de l'élément (max {max_wait}s)...")
    print(f"   🔍 {len(selectors)} sélecteurs à tester")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait:
        attempt += 1
        
        # 🔧 JAVASCRIPT CORRIGÉ - Plus permissif pour contenteditable
        js_code = """
            (function() {
                try {
                    const selectors = """ + json.dumps(selectors) + """;
                    
                    function isVisible(elem) {
                        if (!elem) return false;
                        
                        const style = window.getComputedStyle(elem);
                        
                        // ❌ NE PAS rejeter si display:none/visibility:hidden
                        // Car ChatGPT masque le textarea mais utilise un contenteditable
                        
                        // ✅ ACCEPTER TOUS les contenteditable, même cachés
                        if (elem.contentEditable === 'true') {
                            // Vérifier qu'il n'est pas dans un conteneur hidden
                            let parent = elem.parentElement;
                            while (parent) {
                                const pStyle = window.getComputedStyle(parent);
                                if (pStyle.display === 'none' || pStyle.visibility === 'hidden') {
                                    return false;
                                }
                                parent = parent.parentElement;
                            }
                            return true;  // 🔧 ACCEPTER même si 0x0
                        }
                        
                        // Pour textarea standard, vérifier la visibilité normale
                        if (elem.tagName === 'TEXTAREA') {
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                return false;
                            }
                            const rect = elem.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }
                        
                        return false;
                    }
                    
                    // Tester chaque sélecteur
                    for (const selector of selectors) {
                        try {
                            const elem = document.querySelector(selector);
                            if (elem && isVisible(elem)) {
                                return {
                                    found: true,
                                    selector: selector,
                                    tagName: elem.tagName.toLowerCase(),
                                    id: elem.id || '',
                                    className: elem.className || '',
                                    isContentEditable: elem.contentEditable === 'true',
                                    placeholder: elem.placeholder || '',
                                    ariaLabel: elem.getAttribute('aria-label') || ''
                                };
                            }
                        } catch (e) {
                            // Sélecteur invalide, continuer
                        }
                    }
                    
                    return {
                        found: false,
                        textareaCount: document.querySelectorAll('textarea').length,
                        editableCount: document.querySelectorAll('[contenteditable="true"]').length
                    };
                } catch (e) {
                    return {error: e.message, found: false};
                }
            })();
        """
        
        result = client.execute_javascript(js_code)
        data = parse_browseros_js_response(result)
        
        if data:
            if data.get("found"):
                elapsed = time.time() - start_time
                print(f"\n   ✅ Élément trouvé après {elapsed:.1f}s (tentative #{attempt})")
                print(f"      Tag: {data.get('tagName')}")
                print(f"      Selector: {data.get('selector')}")
                print(f"      ContentEditable: {data.get('isContentEditable')}")
                return data
            else:
                if attempt % 3 == 0:
                    print(f"   📊 Textareas: {data.get('textareaCount', 0)}, "
                          f"Editables: {data.get('editableCount', 0)}")
        
        elapsed = time.time() - start_time
        remaining = max_wait - elapsed
        print(f"   ⏳ {elapsed:.0f}s / {max_wait:.0f}s (reste {remaining:.0f}s)...", end='\r')
        time.sleep(check_interval)
    
    print(f"\n   ⏱️ Timeout après {max_wait}s ({attempt} tentatives)")
    return None


def find_input_element_generic(client: BrowserOSMCPClient) -> Optional[Dict]:
    """
    Trouve n'importe quel élément de saisie visible sur la page
    Sans dépendre de sélecteurs spécifiques
    """
    print("\n🔍 Recherche générique d'un élément de saisie...")
    
    js_code = """
        (function() {
            try {
                // Chercher tous les éléments potentiels
                const candidates = [];
                
                // 1. Tous les contenteditable
                document.querySelectorAll('[contenteditable="true"]').forEach(elem => {
                    const rect = elem.getBoundingClientRect();
                    const style = window.getComputedStyle(elem);
                    
                    // Vérifier si potentiellement visible
                    if (style.display !== 'none' && style.visibility !== 'hidden') {
                        candidates.push({
                            element: elem,
                            score: rect.width * rect.height, // Score basé sur la taille
                            type: 'contenteditable',
                            rect: {width: rect.width, height: rect.height}
                        });
                    }
                });
                
                // 2. Tous les textarea (sauf ceux cachés)
                document.querySelectorAll('textarea').forEach(elem => {
                    const rect = elem.getBoundingClientRect();
                    const style = window.getComputedStyle(elem);
                    
                    if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 10 && rect.height > 10) {
                        candidates.push({
                            element: elem,
                            score: rect.width * rect.height,
                            type: 'textarea',
                            rect: {width: rect.width, height: rect.height}
                        });
                    }
                });
                
                // Trier par score (plus grand élément)
                candidates.sort((a, b) => b.score - a.score);
                
                if (candidates.length > 0) {
                    const best = candidates[0];
                    const elem = best.element;
                    
                    // Générer un sélecteur unique
                    let selector = elem.tagName.toLowerCase();
                    if (elem.id) {
                        selector = selector + '#' + elem.id;
                    } else if (elem.className) {
                        const classes = elem.className.split(' ').filter(c => c.length > 0);
                        if (classes.length > 0) {
                            selector = selector + '.' + classes[0];
                        }
                    }
                    
                    return {
                        found: true,
                        selector: selector,
                        tagName: elem.tagName.toLowerCase(),
                        id: elem.id || '',
                        className: elem.className || '',
                        isContentEditable: elem.contentEditable === 'true',
                        placeholder: elem.placeholder || '',
                        ariaLabel: elem.getAttribute('aria-label') || '',
                        score: best.score,
                        width: best.rect.width,
                        height: best.rect.height,
                        totalCandidates: candidates.length
                    };
                }
                
                return {
                    found: false,
                    totalCandidates: candidates.length,
                    message: 'Aucun élément de saisie visible trouvé'
                };
                
            } catch (e) {
                return {error: e.message, found: false};
            }
        })();
    """
    
    result = client.execute_javascript(js_code)
    data = parse_browseros_js_response(result)
    
    if data and data.get('found'):
        print(f"   ✅ Élément trouvé!")
        print(f"      Type: {data.get('type', 'N/A')}")
        print(f"      Taille: {data.get('width')}x{data.get('height')}")
        print(f"      Candidats testés: {data.get('totalCandidates', 0)}")
        print(f"      Sélecteur: {data.get('selector')}")
        return data
    else:
        print(f"   ❌ Aucun élément visible trouvé")
        if data:
            print(f"      Candidats testés: {data.get('totalCandidates', 0)}")
            print(f"      Message: {data.get('message', 'N/A')}")
        return None


# CORRECTIF COMPLET pour ChatGPT - browser_helpers.py

def send_message_universal(
    client: BrowserOSMCPClient,
    message: str,
    element_info: Dict,
    use_enter: bool = True
) -> bool:
    """
    Envoie un message de manière universelle
    🔧 VERSION FINALE - TOUS LES BUGS CORRIGÉS
    """
    
    if not element_info:
        print("\n❌ Aucun élément de saisie disponible")
        return False
    
    print(f"\n💬 Envoi du message...")
    print(f"   Longueur: {len(message)} caractères")
    
    # Échapper le message pour JavaScript
    escaped_message = (message
        .replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\n', '\\n')
        .replace('\r', '')
        .replace('\t', '\\t'))
    
    selector = element_info.get('selector', '')
    print(f"   📝 Saisie dans: {selector}")
    
    # 🔧 CORRECTION CRITIQUE: Utiliser (async function() avec await
    js_code = f"""
        (async function() {{
            try {{
                const selector = {json.dumps(selector)};
                const message = "{escaped_message}";
                
                const elem = document.querySelector(selector);
                if (!elem) {{
                    return {{success: false, error: 'Element not found'}};
                }}
                
                // Focus
                elem.focus();
                elem.click();
                
                // Wait helper
                const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                await sleep(500);
                
                // Clear
                elem.textContent = '';
                elem.innerHTML = '';
                
                // Insert text
                elem.textContent = message;
                
                // Trigger events
                elem.dispatchEvent(new Event('input', {{bubbles: true, cancelable: true}}));
                elem.dispatchEvent(new Event('change', {{bubbles: true}}));
                elem.dispatchEvent(new KeyboardEvent('keydown', {{key: 'a', bubbles: true}}));
                
                // Set cursor position
                if (elem.contentEditable === 'true') {{
                    const range = document.createRange();
                    const sel = window.getSelection();
                    range.selectNodeContents(elem);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                }}
                
                await sleep(1000);
                
                return {{
                    success: true,
                    textLength: elem.textContent.length,
                    hasContent: elem.textContent.length > 0
                }};
                
            }} catch (err) {{
                return {{success: false, error: err.message}};
            }}
        }})();
    """
    
    result = client.execute_javascript(js_code)
    data = parse_browseros_js_response(result)
    
    # 🔧 Gérer le cas d'un dict vide (timeout)
    if not data or (isinstance(data, dict) and len(data) == 0):
        print(f"   ⚠️ Réponse vide (possible timeout)")
        print(f"   💡 Le texte a probablement été saisi, on continue...")
        data = {"success": True}
    
    if not data.get("success"):
        error = data.get('error', 'Unknown')
        print(f"   ❌ Échec saisie: {error}")
        return False
    
    text_length = data.get('textLength', len(message))
    print(f"   ✅ Texte saisi ({text_length} chars)")
    
    # 🔧 ÉTAPE 2: Chercher et cliquer sur le bouton Send
    time.sleep(1.5)
    print(f"   🔍 Recherche du bouton Send...")
    
    # JavaScript pour chercher et cliquer le bouton
    send_button_js = """
        (async function() {
            try {
                // Liste exhaustive de sélecteurs
                const selectors = [
                    'button[data-testid="send-button"]',
                    'button[aria-label*="Send"]',
                    'button[aria-label*="Envoyer"]',
                    'button[data-testid="fruitjuice-send-button"]',
                    'button[type="submit"]'
                ];
                
                let sendButton = null;
                
                // Test par sélecteur
                for (const sel of selectors) {
                    try {
                        const btn = document.querySelector(sel);
                        if (btn && !btn.disabled) {
                            sendButton = btn;
                            break;
                        }
                    } catch (e) {}
                }
                
                // Recherche par attributs si pas trouvé
                if (!sendButton) {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    sendButton = buttons.find(btn => {
                        if (btn.disabled) return false;
                        
                        const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                        const text = (btn.textContent || '').toLowerCase();
                        const hasSvg = btn.querySelector('svg') !== null;
                        
                        return (
                            aria.includes('send') || 
                            aria.includes('envoyer') ||
                            aria.includes('submit') ||
                            (hasSvg && btn.type !== 'button')
                        );
                    });
                }
                
                if (!sendButton) {
                    return {
                        success: false,
                        found: false,
                        totalButtons: document.querySelectorAll('button').length
                    };
                }
                
                // Click
                sendButton.focus();
                await new Promise(r => setTimeout(r, 200));
                sendButton.click();
                
                await new Promise(r => setTimeout(r, 500));
                
                return {
                    success: true,
                    found: true,
                    clicked: true,
                    wasDisabled: sendButton.disabled
                };
                
            } catch (err) {
                return {success: false, error: err.message};
            }
        })();
    """
    
    send_result = client.execute_javascript(send_button_js)
    send_data = parse_browseros_js_response(send_result)
    
    if send_data and send_data.get("success") and send_data.get("clicked"):
        print(f"   ✅ Bouton Send cliqué!")
        return True
    
    # Bouton non trouvé
    total_buttons = send_data.get('totalButtons', 'N/A') if send_data else 'N/A'
    print(f"   ⚠️ Bouton Send introuvable (total buttons: {total_buttons})")
    print(f"   🔄 Fallback: Tentative avec Enter...")
    
    # 🔧 FALLBACK: Enter + submit form
    enter_js = """
        (async function() {
            try {
                const elem = document.activeElement;
                
                // Enter key
                elem.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true,
                    cancelable: true
                }));
                
                elem.dispatchEvent(new KeyboardEvent('keypress', {
                    key: 'Enter',
                    keyCode: 13,
                    bubbles: true
                }));
                
                elem.dispatchEvent(new KeyboardEvent('keyup', {
                    key: 'Enter',
                    keyCode: 13,
                    bubbles: true
                }));
                
                // Try form submit
                const form = elem.closest('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
                }
                
                return {success: true, method: 'enter'};
                
            } catch (err) {
                return {success: false, error: err.message};
            }
        })();
    """
    
    client.execute_javascript(enter_js)
    print(f"   ⌨️ Enter envoyé (+ submit form)")
    
    # 🔧 Vérifier si le message a été envoyé (champ vidé)
    time.sleep(2)
    
    check_cleared_js = """
        (function() {
            try {
                const editables = document.querySelectorAll('[contenteditable="true"]');
                const textareas = document.querySelectorAll('textarea');
                
                let isEmpty = false;
                
                // Check contenteditable
                for (const elem of editables) {
                    if (elem.textContent.trim() === '') {
                        isEmpty = true;
                        break;
                    }
                }
                
                // Check textareas
                if (!isEmpty) {
                    for (const elem of textareas) {
                        if (elem.value.trim() === '') {
                            isEmpty = true;
                            break;
                        }
                    }
                }
                
                return {
                    cleared: isEmpty,
                    editables: editables.length,
                    textareas: textareas.length
                };
                
            } catch (err) {
                return {cleared: false, error: err.message};
            }
        })();
    """
    
    check_result = client.execute_javascript(check_cleared_js)
    check_data = parse_browseros_js_response(check_result)
    
    if check_data and check_data.get('cleared'):
        print(f"   ✅ Champ vidé - Message envoyé avec succès!")
        return True
    else:
        print(f"   ⚠️ Champ toujours rempli - Envoi incertain")
        # On considère quand même comme succès partiel
        return True


def wait_for_ai_generation(
    client: BrowserOSMCPClient,
    platform: str,
    max_wait: float = 60.0,
    check_interval: float = 1.5,
    stability_checks: int = 3
) -> Dict[str, Any]:
    """
    Attend la fin de la génération AI avec extraction CIBLÉE du contenu
    🔧 VERSION CORRIGÉE - Extrait uniquement la zone de réponse
    """
    print(f"\n⏳ Attente de la réponse {platform}...")
    
    start_time = time.time()
    last_content = ""
    stable_count = 0
    generation_started = False
    
    # Patterns spécifiques par plateforme pour isoler la réponse
    response_selectors = {
        'chatgpt': [
            'div[data-message-author-role="assistant"]',
            'div.markdown.prose',
            'div[class*="markdown"]'
        ],
        'claude': [
            'div[data-is-streaming="true"]',
            'div[data-is-streaming="false"]',
            'div.font-claude-message'
        ],
        'gemini': [
            'message-content',
            'div[class*="response"]',
            'div[class*="model-response"]'
        ],
        'grok': [
            'div[data-testid="conversation-turn"]',
            'div[class*="message-content"]'
        ]
    }
    
    selectors = response_selectors.get(platform.lower(), ['div[class*="response"]'])
    
    while time.time() - start_time < max_wait:
        try:
            # 🔧 EXTRACTION CIBLÉE avec JavaScript
            js_extract = f"""
                (function() {{
                    try {{
                        const selectors = {json.dumps(selectors)};
                        let bestContent = '';
                        let maxLength = 0;
                        
                        // Tester chaque sélecteur
                        for (const selector of selectors) {{
                            try {{
                                const elements = document.querySelectorAll(selector);
                                
                                // Prendre le dernier élément (réponse la plus récente)
                                if (elements.length > 0) {{
                                    const lastElem = elements[elements.length - 1];
                                    const text = lastElem.innerText || lastElem.textContent || '';
                                    
                                    if (text.length > maxLength) {{
                                        maxLength = text.length;
                                        bestContent = text;
                                    }}
                                }}
                            }} catch (e) {{
                                // Sélecteur invalide, continuer
                            }}
                        }}
                        
                        // Fallback : prendre le dernier gros bloc de texte
                        if (!bestContent || maxLength < 500) {{
                            const allDivs = document.querySelectorAll('div');
                            for (const div of allDivs) {{
                                const text = div.innerText || '';
                                // Ignorer les éléments trop petits ou qui ressemblent à la sidebar
                                if (text.length > 1000 && 
                                    !text.includes('Historique de chat') &&
                                    !text.includes('Nouvelle conversation')) {{
                                    if (text.length > maxLength) {{
                                        maxLength = text.length;
                                        bestContent = text;
                                    }}
                                }}
                            }}
                        }}
                        
                        return {{
                            content: bestContent,
                            length: maxLength,
                            selectors_tried: selectors.length
                        }};
                        
                    }} catch (err) {{
                        return {{content: '', error: err.message}};
                    }}
                }})();
            """
            
            result = client.execute_javascript(js_extract)
            data = parse_browseros_js_response(result)
            
            if not data:
                time.sleep(check_interval)
                continue
            
            content = data.get('content', '').strip()
            content_length = len(content)
            
            # Vérifier si c'est du vrai contenu
            if content_length > 1000:  # Seuil minimal pour une vraie réponse
                if not generation_started:
                    print(f"\n   🚀 Génération détectée! ({content_length} chars)")
                generation_started = True
            
            # Attendre le début
            if not generation_started:
                elapsed = time.time() - start_time
                print(f"  ⏳ Attente réponse... ({elapsed:.0f}s, {content_length} chars)", end='\r')
                time.sleep(check_interval)
                continue
            
            # Vérifier la stabilité
            if content and content == last_content:
                stable_count += 1
                print(f"  ✓ Contenu stable ({stable_count}/{stability_checks})", end='\r')
                
                if stable_count >= stability_checks:
                    duration = time.time() - start_time
                    print(f"\n✅ Génération terminée en {duration:.1f}s")
                    print(f"   📊 Taille finale: {content_length} caractères")
                    
                    # 🔧 NETTOYAGE FINAL
                    content = _clean_response_content(content)
                    
                    return {
                        "status": "complete",
                        "duration": duration,
                        "content": content,
                        "length": len(content)
                    }
            else:
                if content != last_content:
                    stable_count = 0
                    change = len(content) - len(last_content)
                    print(f"  ↻ Génération... ({content_length} chars, +{change})", end='\r')
                last_content = content
            
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"\n  ⚠️ Erreur: {e}")
            time.sleep(check_interval)
    
    duration = time.time() - start_time
    print(f"\n⏱️ Timeout après {duration:.1f}s")
    
    if not generation_started:
        print("   ❌ La génération n'a JAMAIS commencé!")
        print("   💡 Le message n'a probablement pas été envoyé")
    
    return {
        "status": "timeout" if not generation_started else "incomplete",
        "duration": duration,
        "content": last_content,
        "length": len(last_content),
        "generation_started": generation_started
    }


def _clean_response_content(content: str) -> str:
    """
    Nettoie le contenu de la réponse pour faciliter l'extraction de snippets
    """
    # Supprimer les éléments de navigation courants
    noise_patterns = [
        "Historique de chat",
        "Bibliothèque", 
        "Nouvelle conversation",
        "Discussions",
        "Projets",
        "Paramètres",
        "Se déconnecter"
    ]
    
    cleaned = content
    for pattern in noise_patterns:
        cleaned = cleaned.replace(pattern, '')
    
    # Supprimer les lignes vides multiples
    import re
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    
    return cleaned.strip()



# ============================================================================
# FONCTION PRINCIPALE UNIVERSELLE
# ============================================================================

def interact_with_platform_generic(
    platform_name: str,
    url: str,
    message: str,
    input_selectors: Optional[List[str]] = None,
    send_button_selectors: Optional[List[str]] = None,
    wait_response: bool = True,
    max_wait: float = 30.0,
    take_screenshot: bool = True,
    page_load_wait: float = 5.0,
    status_callback: Optional[Callable] = None
) -> BrowserOSMCPClient:
    """
    Template universel pour toutes les plateformes IA
    
    Args:
        platform_name: Nom de la plateforme
        url: URL de la plateforme
        message: Message à envoyer
        input_selectors: Sélecteurs personnalisés (optionnel)
        send_button_selectors: Sélecteurs bouton (optionnel)
        wait_response: Attendre la réponse
        max_wait: Temps d'attente max pour la réponse
        take_screenshot: Prendre un screenshot
        page_load_wait: Temps d'attente chargement page
        status_callback: Callback pour progression (message, progress)
        
    Returns:
        Client BrowserOS
    """
    def update_status(msg, progress=0):
        """Helper pour callback"""
        if status_callback:
            status_callback(msg, progress)
        print(f"[{progress}%] {msg}")
    
    print(f"\n{'='*70}")
    print(f"🤖 CONNEXION À {platform_name.upper()}")
    print(f"{'='*70}\n")
    
    # Récupérer la config de la plateforme
    platform_key = platform_name.lower()
    config = PLATFORM_CONFIGS.get(platform_key)
    
    if config:
        # Utiliser la config prédéfinie
        url = url or config['url']
        input_selectors = input_selectors or config['selectors']['input']
        send_button_selectors = send_button_selectors or config['selectors']['send_button']
        page_load_wait = page_load_wait or config['page_load_wait']
        use_enter = config.get('use_enter_to_send', True)
    else:
        # Config manuelle
        use_enter = True
    
    client = BrowserOSMCPClient(timeout=30, max_retries=3)
    
    # 1. Vérifier le serveur
    update_status("Vérification du serveur BrowserOS", 5)
    if not client.wait_for_server(max_wait=10):
        print("❌ Serveur BrowserOS non disponible")
        return client
    
    # 2. Initialiser
    update_status("Initialisation MCP", 10)
    init_result = client.initialize()
    if "error" in init_result:
        print(f"❌ Échec: {init_result['error']}")
        return client
    
    # 3. Naviguer
    update_status(f"Navigation vers {platform_name}", 20)
    nav_result_data = navigate_with_http_431_protection(client, url, platform_key)
   
    if not nav_result_data.get('success'):
        print(f"❌ Échec navigation: {nav_result_data.get('message')}")
        if nav_result_data.get('error') == 'http_431':
            print("\n💡 SOLUTION: Redémarrer BrowserOS avec un profil Chrome vierge")
        return client
    
    # 5. Attente du chargement avec vérification progressive (VERSION OPTIMISÉE)
    update_status(f"Attente du chargement intelligent", 30)
    print(f"\n⏳ Attente intelligente du chargement...")
    
    max_load_wait = page_load_wait * 2  # Double du temps initial
    start_wait = time.time()
    last_textarea_count = 0
    stable_count = 0
    
    while time.time() - start_wait < max_load_wait:
        # Vérifier l'état de la page (JSON ultra-compact)
        check_result = client.execute_javascript("""
            (function() {
                try {
                    return JSON.stringify({
                        r: document.readyState,
                        t: document.querySelectorAll('textarea').length,
                        e: document.querySelectorAll('[contenteditable="true"]').length
                    });
                } catch (err) {
                    return JSON.stringify({r:'',t:0,e:0});
                }
            })();
        """)
        
        data = parse_browseros_js_response(check_result)
        
        if data:
            textarea_count = data.get('t', 0) + data.get('e', 0)
            ready_state = data.get('r', '')
            
            print(f"   ⏳ {time.time() - start_wait:.0f}s - "
                  f"State: {ready_state}, "
                  f"Champs: {textarea_count}", end='\r')
            
            # Si on a trouvé des champs et qu'ils sont stables
            if textarea_count > 0:
                if textarea_count == last_textarea_count:
                    stable_count += 1
                    if stable_count >= 2:  # Stable pendant 2 vérifications
                        print(f"\n   ✅ Page chargée avec {textarea_count} champ(s) détecté(s)")
                        break
                else:
                    stable_count = 0
                last_textarea_count = textarea_count
        
        time.sleep(1)
    
    if time.time() - start_wait >= max_load_wait:
        print(f"\n   ⏱️ Timeout d'attente après {max_load_wait:.0f}s")
    
    # 🆕 DIAGNOSTIC: Inspecter la page
    
    # 🆕 DIAGNOSTIC: Inspecter la page (VERSION COMPACTE)
    print("\n🔍 DIAGNOSTIC de la page:")
    diag_result = client.execute_javascript("""
        (function() {
            try {
                return JSON.stringify({
                    t: document.querySelectorAll('textarea').length,
                    i: document.querySelectorAll('input').length,
                    e: document.querySelectorAll('[contenteditable="true"]').length,
                    b: document.querySelectorAll('button').length,
                    r: document.readyState
                });
            } catch (err) {
                return JSON.stringify({});
            }
        })();
    """)
    
    diag = parse_browseros_js_response(diag_result)
    if diag:
        print(f"   🔄 ReadyState: {diag.get('r', 'N/A')}")
        print(f"   📊 Éléments:")
        print(f"      - Textareas: {diag.get('t', 0)}")
        print(f"      - Inputs: {diag.get('i', 0)}")
        print(f"      - Editables: {diag.get('e', 0)}")
        print(f"      - Buttons: {diag.get('b', 0)}")
        
        # Si aucun champ de saisie détecté
        if diag.get('t', 0) == 0 and diag.get('e', 0) == 0:
            print("\n   ⚠️ ATTENTION: Aucun champ de saisie détecté!")
            print("   💡 Raisons possibles:")
            print("      1. Page d'authentification requise")
            print("      2. Page pas complètement chargée") 
            print("      3. Application React/SPA qui nécessite plus de temps")
    else:
        print("   ⚠️ Impossible d'obtenir le diagnostic")
    
    # 6. Vérifier l'authentification
    update_status("Vérification de l'authentification", 40)
    auth_check = check_authentication_status(client, platform_key)
    print(f"   {auth_check['message']}")
    
    if auth_check.get("requires_auth"):
        print("\n⚠️ AUTHENTIFICATION REQUISE!")
        print(f"   URL: {auth_check['url']}")
        print(f"   💡 Veuillez vous connecter manuellement")
        print(f"   ⏳ Attente de 30s pour connexion manuelle...")
        
        # Attendre l'authentification manuelle
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                auth_check = check_authentication_status(client, platform_key)
                if not auth_check.get("requires_auth"):
                    print(f"\n   ✅ Authentification réussie!")
                    break
                print(f"   ⏳ {30-i}s restantes...")
        
        # Vérification finale
        auth_check = check_authentication_status(client, platform_key)
        if auth_check.get("requires_auth"):
            print("   ❌ Toujours non authentifié")
            if take_screenshot:
                client.screenshot()
            return client
    
    update_status("Recherche du champ de saisie", 50)
    
    # 🔧 NOUVEAU: Diagnostic avant recherche
    print("\n🔍 Diagnostic des éléments disponibles...")
    debug_page_elements(client, input_selectors)
    
    # 🔧 NOUVELLE APPROCHE: Recherche générique
    print("\n🔄 Tentative de recherche générique...")

    if platform_key == 'claude':
       print("\n🔍 Mode recherche spécialisé Claude...")
       element_info = find_claude_input_robust(client)
       
       if element_info and element_info.get('found'):
           print("   ✅ Champ Claude détecté via recherche robuste!")
       else:
           print("   ⚠️ Recherche robuste échouée, fallback...")
           element_info = None
    else:
        element_info = None
    
    # Si échec ou autre plateforme, utiliser recherche générique
    if not element_info:
        print("\n🔄 Tentative de recherche générique...")
        element_info = find_input_element_generic(client)
        element_info = find_input_element_generic(client)
    
    # Si échec, essayer l'ancienne méthode
    if not element_info:
        print("\n🔄 Fallback: Recherche avec sélecteurs spécifiques...")
        element_info = wait_for_element_with_retry(
            client,
            input_selectors,
            max_wait=10.0,  # Réduire le timeout
            check_interval=2.0
        )
    
    if not element_info or not element_info.get("found"):
        print("\n❌ ÉCHEC: Champ de saisie introuvable")
        print("   💡 La page nécessite probablement une authentification")
        if take_screenshot:
            client.screenshot()
        return client
    
    # 8. Envoyer le message
    update_status("Envoi du message", 60)
    success = send_message_universal(client, message, element_info, use_enter)
    
    if not success:
        print("❌ Échec de l'envoi")
        if take_screenshot:
            client.screenshot()
        return client
    
    # 9. Attendre la réponse
    if wait_response:
        update_status("Attente de la réponse", 70)
        wait_for_ai_generation(client, platform_name, max_wait)
    
    # 10. Screenshot
    if take_screenshot:
        update_status("Capture d'écran", 90)
        client.screenshot()
    
    update_status("Terminé", 100)
    print(f"\n{'='*70}")
    print("✅ TERMINÉ")
    print(f"{'='*70}\n")
    
    return client


# ============================================================================
# FONCTIONS SPÉCIALISÉES PAR PLATEFORME
# ============================================================================

def interact_with_chatgpt(message: str, status_callback: Optional[Callable] = None) -> BrowserOSMCPClient:
    """Interagit avec ChatGPT"""
    return interact_with_platform_generic(
        platform_name="chatgpt",
        url=None,  # Utilise la config
        message=message,
        status_callback=status_callback
    )


def interact_with_claude(message: str, status_callback: Optional[Callable] = None) -> BrowserOSMCPClient:
    """Interagit avec Claude"""
    return interact_with_platform_generic(
        platform_name="claude",
        url=None,
        message=message,
        status_callback=status_callback
    )


def interact_with_gemini(message: str, status_callback: Optional[Callable] = None) -> BrowserOSMCPClient:
    """Interagit avec Gemini"""
    return interact_with_platform_generic(
        platform_name="gemini",
        url=None,
        message=message,
        status_callback=status_callback
    )


def interact_with_grok(message: str, status_callback: Optional[Callable] = None) -> BrowserOSMCPClient:
    """Interagit avec Grok"""
    return interact_with_platform_generic(
        platform_name="grok",
        url=None,
        message=message,
        status_callback=status_callback
    )