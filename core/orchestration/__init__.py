"""
Module d'orchestration des IA
Handlers pour la navigation automatique dans les plateformes IA

Structure:
---------
core/orchestration/
├── __init__.py                  ← Ce fichier
├── conductor.py                 ← AIConductor
├── browser_navigation_worker.py ← Worker de navigation
├── browserOs_conductor.py       ← Client BrowserOS MCP
├── gemini_handler.py            ← Handler Gemini
├── chatgpt_handler.py           ← Handler ChatGPT
├── claude_handler.py            ← Handler Claude
└── grok_handler.py              ← Handler Grok

Usage:
------
from core.orchestration.gemini_handler import interact_with_gemini
from core.orchestration.browserOs_conductor import BrowserOSMCPClient
from core.orchestration import AIConductor
"""

import sys
import os
from pathlib import Path

# ✅ Configuration du package
_PACKAGE_DIR = Path(__file__).parent.resolve()

# Ajouter le dossier parent au sys.path si nécessaire
if str(_PACKAGE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR.parent))

# Informations du package
__version__ = "1.0.0"
__author__ = "Liris AI"

# ✅ CORRECTION: Séparer les conductors des handlers
__all__ = [
    # Conducteurs principaux
    'AIConductor',
    'BrowserOSMCPClient',
    
    # Handlers de navigation
    'gemini_handler',
    'chatgpt_handler',
    'claude_handler',
    'grok_handler',
]

# Cache des modules importés
_handlers = {}


def _get_handler_path(handler_name):
    """Retourne le chemin d'un handler"""
    return _PACKAGE_DIR / f"{handler_name}.py"


def _lazy_import_handler(handler_name):
    """Import paresseux d'un handler avec gestion d'erreur"""
    if handler_name in _handlers:
        return _handlers[handler_name]
    
    handler_file = _get_handler_path(handler_name)
    
    if not handler_file.exists():
        raise ImportError(
            f"❌ Handler '{handler_name}' introuvable.\n"
            f"   Fichier attendu: {handler_file}\n"
            f"   Créez le fichier ou vérifiez l'installation."
        )
    
    try:
        # ✅ CORRECTION: Import depuis core.orchestration, pas browser_handlers
        module_path = f"core.orchestration.{handler_name}"
        
        # Si on est déjà dans le bon package, import relatif
        if __package__:
            module = __import__(handler_name, globals(), locals(), ['*'], level=0)
        else:
            module = __import__(module_path, fromlist=['*'])
        
        _handlers[handler_name] = module
        return module
        
    except ImportError as e:
        raise ImportError(
            f"❌ Impossible d'importer {handler_name}: {e}\n"
            f"   Vérifiez:\n"
            f"   • Le fichier existe: {handler_file.exists()}\n"
            f"   • Les dépendances sont installées\n"
            f"   • La syntaxe Python est correcte"
        )


def _lazy_import_conductor(conductor_name):
    """Import paresseux d'un conductor"""
    conductor_file = _PACKAGE_DIR / f"{conductor_name}.py"
    
    if not conductor_file.exists():
        raise ImportError(
            f"❌ Conductor '{conductor_name}' introuvable.\n"
            f"   Fichier attendu: {conductor_file}"
        )
    
    try:
        if __package__:
            module = __import__(conductor_name, globals(), locals(), ['*'], level=0)
        else:
            module_path = f"core.orchestration.{conductor_name}"
            module = __import__(module_path, fromlist=['*'])
        
        return module
        
    except ImportError as e:
        raise ImportError(
            f"❌ Impossible d'importer {conductor_name}: {e}"
        )


# ✅ Exports directs des classes principales
try:
    from .conductor import AIConductor
except ImportError:
    AIConductor = None

try:
    from .browserOs_conductor import BrowserOSMCPClient
except ImportError:
    BrowserOSMCPClient = None


def check_installation():
    """Vérifie l'installation du package et des handlers"""
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION DE L'INSTALLATION")
    print("=" * 70)
    print(f"📂 Emplacement: {_PACKAGE_DIR}")
    print(f"📦 Version: {__version__}\n")
    
    # Vérifier les fichiers principaux
    print("📋 Fichiers principaux:")
    
    main_files = {
        'conductor.py': 'AIConductor',
        'browserOs_conductor.py': 'BrowserOSMCPClient',
        'browser_navigation_worker.py': 'BrowserNavigationWorker',
    }
    
    main_ok = 0
    for filename, class_name in main_files.items():
        filepath = _PACKAGE_DIR / filename
        if filepath.exists():
            print(f"   ✅ {filename} ({class_name})")
            main_ok += 1
        else:
            print(f"   ❌ {filename} (MANQUANT)")
    
    # Vérifier les handlers
    print("\n🤖 Handlers de navigation:")
    
    handlers_to_check = [
        'gemini_handler',
        'chatgpt_handler',
        'claude_handler',
        'grok_handler',
    ]
    
    available = []
    missing = []
    
    for handler in handlers_to_check:
        handler_file = _get_handler_path(handler)
        
        if handler_file.exists():
            print(f"   ✅ {handler}.py")
            available.append(handler)
        else:
            print(f"   ❌ {handler}.py (MANQUANT)")
            missing.append(handler)
    
    # Résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ")
    print("=" * 70)
    print(f"✅ Fichiers principaux: {main_ok}/{len(main_files)}")
    print(f"✅ Handlers disponibles: {len(available)}/{len(handlers_to_check)}")
    
    if missing:
        print(f"\n⚠️  Handlers manquants: {', '.join(missing)}")
        print("\n💡 Pour créer un handler manquant:")
        print(f"   from core.orchestration import create_handler_template")
        print(f"   create_handler_template('{missing[0]}')")
    
    if main_ok == len(main_files) and not missing:
        print("\n🎉 Installation complète et fonctionnelle!")
        return True
    elif main_ok == len(main_files):
        print("\n✅ Installation de base OK (handlers optionnels manquants)")
        return True
    else:
        print("\n❌ Installation incomplète - fichiers principaux manquants")
        return False


def create_handler_template(platform_name, output_path=None):
    """
    Crée un template de handler pour une nouvelle plateforme
    
    Args:
        platform_name: Nom de la plateforme (ex: 'perplexity')
        output_path: Chemin de sortie (optionnel, par défaut dans _PACKAGE_DIR)
    
    Returns:
        Path: Chemin du fichier créé
    """
    if not output_path:
        output_path = _PACKAGE_DIR / f"{platform_name}_handler.py"
    else:
        output_path = Path(output_path)
    
    template = f'''"""
Handler pour {platform_name.title()}
Navigation automatique et interaction avec {platform_name.title()}
"""

from .browserOs_conductor import BrowserOSMCPClient
import time
import json

def interact_with_{platform_name}(message):
    """
    Interagit automatiquement avec {platform_name.title()}
    
    Args:
        message (str): Message à envoyer à {platform_name.title()}
    
    Returns:
        BrowserOSMCPClient: Client avec la session active
    """
    print(f"🚀 Connexion à {platform_name.title()}")
    print("=" * 70)
    
    client = BrowserOSMCPClient()
    
    # 1. Initialize
    print("\\n1️⃣  Initialisation MCP")
    client.initialize()
    print("✅ Client initialisé")
    
    # 2. Navigate to platform
    print("\\n2️⃣  Navigation vers {platform_name.title()}")
    url = "https://{platform_name}.com/"  # TODO: Adapter l'URL réelle
    client.navigate(url)
    print(f"✅ Page {platform_name.title()} chargée")
    time.sleep(3)
    
    # 3. Get interactive elements
    print("\\n3️⃣  Analyse des éléments de la page")
    elements_result = client.get_interactive_elements()
    
    if "result" not in elements_result:
        print("❌ Impossible de récupérer les éléments")
        return client
    
    elements = elements_result.get("result", {{}}).get("content", [])
    
    if isinstance(elements, list) and len(elements) > 0:
        if isinstance(elements[0], dict) and "text" in elements[0]:
            try:
                elements = json.loads(elements[0]["text"])
            except:
                pass
    
    print(f"✅ {{len(elements) if isinstance(elements, list) else 0}} éléments trouvés")
    
    # 4. Find input field and send button
    print("\\n4️⃣  Recherche des éléments interactifs")
    
    input_field = None
    send_button = None
    
    if isinstance(elements, list):
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            
            elem_type = elem.get("tagName", "").lower()
            elem_role = elem.get("attributes", {{}}).get("role", "").lower()
            elem_aria = elem.get("attributes", {{}}).get("aria-label", "").lower()
            elem_text = elem.get("text", "").lower()
            
            # Chercher le champ de saisie
            if not input_field:
                if elem_type == "textarea":
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (textarea): nodeId={{elem.get('nodeId')}}")
                elif elem_role == "textbox":
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (textbox): nodeId={{elem.get('nodeId')}}")
                elif "input" in elem_aria or "search" in elem_aria or "prompt" in elem_aria:
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (aria): nodeId={{elem.get('nodeId')}}")
            
            # Chercher le bouton d'envoi
            if not send_button:
                if elem_type == "button":
                    if "send" in elem_text or "submit" in elem_text or "send" in elem_aria:
                        send_button = elem
                        print(f"   📘 Bouton d'envoi trouvé: nodeId={{elem.get('nodeId')}}")
    
    # 5. Send message
    if input_field:
        print("\\n5️⃣  Envoi du message")
        print(f"   💬 Message: {{message[:100]}}{{'...' if len(message) > 100 else ''}}")
        client.type_text(input_field["nodeId"], message)
        time.sleep(1)
        
        # 6. Click send or press Enter
        print("\\n6️⃣  Validation de l'envoi")
        if send_button:
            print("   🖱️  Clic sur le bouton d'envoi")
            client.click_element(send_button["nodeId"])
        else:
            print("   ⌨️  Appui sur Entrée")
            client.execute_javascript("""
                var event = new KeyboardEvent('keydown', {{
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    bubbles: true
                }});
                document.activeElement.dispatchEvent(event);
            """)
        
        print(f"\\n✅ Message envoyé à {platform_name.title()}!")
        
        # 7. Wait for response
        print("\\n7️⃣  Attente de la réponse...")
        time.sleep(8)
        
        # 8. Take screenshot
        print("\\n8️⃣  Capture d'écran")
        client.screenshot()
        print("✅ Screenshot capturé")
        
    else:
        print("\\n❌ Champ de saisie non trouvé")
        print("💡 Vérifiez les sélecteurs ou ajustez la logique de recherche")
    
    return client


if __name__ == "__main__":
    # Test du handler
    MESSAGE = "Test de connexion à {platform_name.title()}"
    
    print(f"🧪 Test du handler {platform_name}_handler")
    print("=" * 70)
    
    try:
        client = interact_with_{platform_name}(MESSAGE)
        print("\\n✅ Test réussi!")
    except Exception as e:
        print(f"\\n❌ Erreur lors du test: {{e}}")
        import traceback
        traceback.print_exc()
'''
    
    # Créer le fichier
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        print(f"✅ Template créé: {output_path}")
        print(f"💡 Personnalisez le fichier selon les spécificités de {platform_name.title()}")
        print(f"\n📝 Prochaines étapes:")
        print(f"   1. Adaptez l'URL dans navigate()")
        print(f"   2. Ajustez les sélecteurs si nécessaire")
        print(f"   3. Testez avec: python {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du template: {e}")
        raise


def list_available_handlers():
    """Liste tous les handlers disponibles"""
    print("\n🤖 Handlers disponibles:")
    print("=" * 70)
    
    handlers_to_check = [
        'gemini_handler',
        'chatgpt_handler',
        'claude_handler',
        'grok_handler',
    ]
    
    for handler in handlers_to_check:
        handler_file = _get_handler_path(handler)
        
        if handler_file.exists():
            # Essayer d'importer pour vérifier
            try:
                module = _lazy_import_handler(handler)
                func_name = f"interact_with_{handler.replace('_handler', '')}"
                
                if hasattr(module, func_name):
                    print(f"✅ {handler:20} → {func_name}()")
                else:
                    print(f"⚠️  {handler:20} (fonction manquante)")
                    
            except ImportError as e:
                print(f"❌ {handler:20} (erreur d'import: {str(e)[:40]}...)")
        else:
            print(f"❌ {handler:20} (fichier manquant)")
    
    print("=" * 70)


# ✅ Message d'information au chargement
if __name__ != "__main__":
    # Petit log discret au chargement
    try:
        from utils.logger import logger
        logger.debug(f"✅ Module orchestration chargé depuis {_PACKAGE_DIR}")
    except:
        pass