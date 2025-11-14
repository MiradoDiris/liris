"""
Script de connexion et interaction automatique avec Claude
"""

from core.orchestration.browserOs_conductor import BrowserOSMCPClient
import time
import json

def interact_with_claude(message):
    """Interagit automatiquement avec Claude"""
    
    print("🧠 Connexion à Claude")
    print("=" * 70)
    
    client = BrowserOSMCPClient()
    
    # 1. Initialize
    print("\n1️⃣  Initialisation MCP")
    client.initialize()
    print("✅ Client initialisé")
    
    # 2. Navigate to Claude
    print("\n2️⃣  Navigation vers Claude")
    client.navigate("https://claude.ai/")
    print("✅ Page Claude chargée")
    time.sleep(3)
    
    # 3. Get interactive elements
    print("\n3️⃣  Analyse des éléments de la page")
    elements_result = client.get_interactive_elements()
    
    if "result" not in elements_result:
        print("❌ Impossible de récupérer les éléments")
        return
    
    elements = elements_result.get("result", {}).get("content", [])
    
    if isinstance(elements, list) and len(elements) > 0:
        if isinstance(elements[0], dict) and "text" in elements[0]:
            try:
                elements = json.loads(elements[0]["text"])
            except:
                pass
    
    print(f"✅ {len(elements) if isinstance(elements, list) else 0} éléments trouvés")
    
    # 4. Find input field
    print("\n4️⃣  Recherche du champ de saisie")
    
    input_field = None
    send_button = None
    
    if isinstance(elements, list):
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            
            elem_type = elem.get("tagName", "").lower()
            elem_id = elem.get("attributes", {}).get("id", "").lower()
            elem_placeholder = elem.get("attributes", {}).get("placeholder", "").lower()
            elem_role = elem.get("attributes", {}).get("role", "").lower()
            elem_class = elem.get("attributes", {}).get("class", "").lower()
            elem_text = elem.get("text", "").lower()
            elem_aria = elem.get("attributes", {}).get("aria-label", "").lower()
            
            # Chercher le champ de saisie
            if not input_field:
                if elem_type == "textarea":
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (textarea): nodeId={elem.get('nodeId')}")
                elif elem_role == "textbox":
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (textbox): nodeId={elem.get('nodeId')}")
                elif elem_type == "div" and "contenteditable" in elem.get("attributes", {}):
                    input_field = elem
                    print(f"   💬 Champ de saisie trouvé (contenteditable): nodeId={elem.get('nodeId')}")
            
            # Chercher le bouton d'envoi
            if not send_button:
                if elem_type == "button":
                    if "send" in elem_text or "submit" in elem_text or "envoyer" in elem_aria:
                        send_button = elem
                        print(f"   🔘 Bouton d'envoi trouvé: nodeId={elem.get('nodeId')}")
    
    # 5. Send message
    if input_field:
        print("\n5️⃣  Envoi du message")
        
        print(f"   💬 Message: {message[:100]}{'...' if len(message) > 100 else ''}")
        client.type_text(input_field["nodeId"], message)
        time.sleep(1)
        
        # 6. Click send or press Enter
        print("\n6️⃣  Envoi")
        if send_button:
            print(f"   🖱️  Clic sur le bouton")
            client.click_element(send_button["nodeId"])
        else:
            print(f"   ⌨️  Appui sur Entrée")
            client.execute_javascript("""
                var event = new KeyboardEvent('keydown', {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    bubbles: true
                });
                document.activeElement.dispatchEvent(event);
            """)
        
        print("\n✅ Message envoyé à Claude!")
        
        # 7. Wait for response and take screenshot
        print("\n7️⃣  Attente de la réponse...")
        time.sleep(8)
        
        print("\n8️⃣  Capture d'écran")
        client.screenshot()
        print("✅ Screenshot capturé")
        
    else:
        print("\n❌ Champ de saisie non trouvé")
    
    return client


if __name__ == "__main__":
    MESSAGE = "Bonjour Claude! Comment vas-tu aujourd'hui?"
    
    client = interact_with_claude(MESSAGE)