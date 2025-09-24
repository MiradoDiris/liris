#!/usr/bin/env python3

import sys
import os

# Ajouter le répertoire racine au path Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ConfigProvider
from core.orchestration.adapters.gemini_adapter import GeminiAdapter

def test_gemini():
    """Teste la connexion à Gemini"""
    print("🧪 Test de connexion à Gemini...")
    
    # Charger la configuration
    config_provider = ConfigProvider()
    gemini_config = config_provider.get_gemini_config()
    
    if not gemini_config or not gemini_config.get("api_key"):
        print("❌ Configuration Gemini non trouvée")
        return False
    
    print(f"✅ Clé API trouvée: {gemini_config['api_key'][:10]}...")
    
    # Tester l'adapteur
    adapter = GeminiAdapter(gemini_config)
    
    if adapter.test_connection():
        print("✅ Connexion à Gemini réussie!")
        
        # Test d'un prompt simple
        print("🧪 Test d'un prompt simple...")
        result = adapter.send_prompt("Dis bonjour en français en 3 mots maximum.")
        
        if result and result.get("status") == "completed":
            response = result["result"]["response"]
            print(f"✅ Réponse reçue: {response}")
            return True
        else:
            print(f"❌ Erreur: {result.get('error', 'Unknown error')}")
            return False
    else:
        print("❌ Échec de la connexion à Gemini")
        return False

if __name__ == "__main__":
    test_gemini()