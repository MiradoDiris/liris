import sys
import os
import json
import time

import requests

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class DummyConductor:
    """Conductor minimal pour tester les clés API via les endpoints officiels."""
    
    def test_api_key(self, platform_name, api_config):
        """Teste la validité de la clé API selon la plateforme."""
        try:
            if platform_name == "Claude":
                return self._test_claude(api_config)
            elif platform_name == "Gemini":
                return self._test_gemini(api_config)
            else:
                return {
                    "success": False,
                    "error": f"Plateforme '{platform_name}' non supportée par le test local"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _test_claude(self, api_config):
        """Test de l'API Claude"""
        import requests
        
        base_url = api_config.get("base_url", "https://api.anthropic.com/v1/messages")
        if not base_url.endswith('/messages'):
            base_url = base_url.rstrip('/') + '/messages'
        
        headers = {
            "x-api-key": api_config["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": api_config.get("model", "claude-3-opus-20240229"),
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        try:
            response = requests.post(
                base_url, 
                headers=headers, 
                json=payload, 
                timeout=api_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True, 
                    "details": {
                        "status": 200,
                        "model": data.get("model"),
                        "message": "Clé valide et fonctionnelle"
                    }
                }
            elif response.status_code == 401:
                return {"success": False, "error": "Clé API invalide ou non autorisée"}
            elif response.status_code == 429:
                return {"success": False, "error": "Limite de taux dépassée"}
            else:
                return {
                    "success": False, 
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout - l'API ne répond pas"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Erreur de connexion - vérifiez votre connexion internet"}
        except Exception as e:
            return {"success": False, "error": f"Erreur: {str(e)}"}

    def _test_gemini(self, api_config):
        """Test basique de la clé API Google Gemini."""
        api_key = api_config.get("api_key")
        base_url = api_config.get("base_url", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}")
        
        payload = {"contents": [{"parts": [{"text": "Hello Gemini"}]}]}

        try:
            response = requests.post(base_url, json=payload, timeout=api_config.get("timeout", 30))
            if response.status_code == 200:
                return {"success": True, "details": {"status": 200, "message": "Clé valide"}}
            elif response.status_code == 401:
                return {"success": False, "error": "Clé API invalide ou expirée"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Erreur réseau: {str(e)}"}

def test_keyring_installation():
    """Teste si keyring est correctement installé"""
    print("🔍 Test 1: Installation de keyring")
    try:
        import keyring
        print("   ✅ Module keyring importé avec succès")
        print(f"   📦 Version: {keyring.__version__ if hasattr(keyring, '__version__') else 'inconnue'}")
        
        # Vérifier le backend utilisé
        backend = keyring.get_keyring()
        print(f"   🔐 Backend: {backend.__class__.__name__}")
        print(f"   📍 Module: {backend.__module__}")
        
        return True
    except ImportError as e:
        print(f"   ❌ Erreur import keyring: {e}")
        print("   💡 Solution: pip install keyring")
        return False

def test_keyring_helper():
    """Teste si KeyringHelper est accessible"""
    print("\n🔍 Test 2: Import de KeyringHelper")
    try:
        from utils.keyring_helper import KeyringHelper
        print("   ✅ KeyringHelper importé avec succès")
        print(f"   🔑 Service: {KeyringHelper.KEYRING_SERVICE}")
        
        # Vérifier les méthodes disponibles
        methods = [m for m in dir(KeyringHelper) if not m.startswith('_')]
        print(f"   📋 Méthodes disponibles: {', '.join(methods)}")
        
        return True
    except ImportError as e:
        print(f"   ❌ Erreur import KeyringHelper: {e}")
        print("   💡 Vérifiez que le fichier utils/keyring_helper.py existe")
        return False

def test_platform_configs():
    """Teste la récupération des configs pour chaque plateforme"""
    print("\n🔍 Test 3: Configurations des plateformes")
    try:
        from utils.keyring_helper import KeyringHelper
        
        platforms = ["Claude", "Gemini", "ChatGPT", "Grok", "DeepSeek"]
        configured_count = 0
        
        for platform in platforms:
            config = KeyringHelper.get_platform_config(platform)
            if config and config.get('api_key'):
                configured_count += 1
                has_key = '✅'
                has_model = '✅' if config.get('model') else '⚠️'
                print(f"   {platform}:")
                print(f"      {has_key} Clé API: configurée ({len(config.get('api_key', ''))} car.)")
                print(f"      {has_model} Modèle: {config.get('model', 'non configuré')}")
                print(f"      📊 Max tokens: {config.get('max_tokens', 'défaut')}")
                print(f"      ⏱️ Timeout: {config.get('timeout', 'défaut')}s")
                
                # Vérifier les champs additionnels
                if config.get('base_url'):
                    print(f"      🌐 URL: {config.get('base_url')}")
                if config.get('custom_headers'):
                    print(f"      📝 Headers: {len(config.get('custom_headers', {}))} définis")
            else:
                print(f"   {platform}: ❌ Non configuré")
        
        print(f"\n   📊 Résumé: {configured_count}/{len(platforms)} plateformes configurées")
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        return False

def test_keyring_write():
    """Teste l'écriture dans keyring"""
    print("\n🔍 Test 4: Écriture/Lecture dans keyring")
    try:
        import keyring
        
        service = "AI_Conductor_TEST"
        key = "test_config"
        test_data = {
            'api_key': 'test_key_12345',
            'model': 'test-model',
            'max_tokens': 4096,
            'timeout': 60,
            'base_url': 'https://api.test.com',
            'custom_headers': {'X-Test': 'true'}
        }
        
        # Écriture
        print("   💾 Écriture des données de test...")
        keyring.set_password(service, key, json.dumps(test_data))
        print("   ✅ Écriture réussie")
        
        # Lecture immédiate
        print("   📖 Lecture des données...")
        stored = keyring.get_password(service, key)
        if stored:
            parsed = json.loads(stored)
            
            # Vérification détaillée
            all_match = True
            for k, v in test_data.items():
                if parsed.get(k) != v:
                    print(f"   ⚠️ Différence pour '{k}': attendu={v}, reçu={parsed.get(k)}")
                    all_match = False
            
            if all_match:
                print("   ✅ Lecture réussie - toutes les données intactes")
            else:
                print("   ⚠️ Lecture réussie mais données différentes")
        else:
            print("   ❌ Échec de lecture")
            return False
        
        # Test de persistance (petite pause)
        print("   ⏳ Test de persistance (1s)...")
        time.sleep(1)
        stored_again = keyring.get_password(service, key)
        if stored_again and json.loads(stored_again) == test_data:
            print("   ✅ Données toujours présentes après pause")
        else:
            print("   ⚠️ Problème de persistance détecté")
        
        # Nettoyage
        keyring.delete_password(service, key)
        print("   ✅ Suppression réussie")
        
        # Vérification de la suppression
        try:
            deleted_check = keyring.get_password(service, key)
            if deleted_check is None:
                print("   ✅ Confirmation: données bien supprimées")
            else:
                print("   ⚠️ Avertissement: données encore présentes après suppression")
        except:
            print("   ✅ Confirmation: données bien supprimées")
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        return False

def test_keyring_api_widget_integration():
    """Teste l'intégration avec ApiKeyConfigWidget"""
    print("\n🔍 Test 5: Intégration ApiKeyConfigWidget")
    try:
        from ui.widgets.tabs.api_key_config_widget import ApiKeyConfigWidget
        print("   ✅ ApiKeyConfigWidget importé")

        # 👉 Ajout du conductor pour tests réels
        conductor = DummyConductor()

        # Récupération configuration
        config = ApiKeyConfigWidget.get_platform_config("Claude")
        if config and config.get('api_key'):
            result = conductor.test_api_key("Claude", config)
            print(f"   🌐 Test réel Claude: {result}")
        else:
            print("   ⚠️ Aucune clé Claude trouvée dans le trousseau")

        config = ApiKeyConfigWidget.get_platform_config("Gemini")
        if config and config.get('api_key'):
            result = conductor.test_api_key("Gemini", config)
            print(f"   🌐 Test réel Gemini: {result}")
        else:
            print("   ⚠️ Aucune clé Gemini trouvée dans le trousseau")

        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        return False

def test_security_checks():
    """Teste les aspects de sécurité"""
    print("\n🔍 Test 6: Vérifications de sécurité")
    try:
        import keyring
        
        service = "AI_Conductor_TEST_SECURITY"
        
        # Test 1: Données sensibles
        print("   🔐 Test de stockage de données sensibles...")
        sensitive_data = {
            'api_key': 'sk-proj-abc123xyz789-VERY_SECRET_KEY',
            'password': 'super_secret_password_123!@#'
        }
        
        keyring.set_password(service, "sensitive", json.dumps(sensitive_data))
        retrieved = json.loads(keyring.get_password(service, "sensitive"))
        
        if retrieved == sensitive_data:
            print("   ✅ Données sensibles stockées et récupérées correctement")
        else:
            print("   ⚠️ Problème avec le stockage de données sensibles")
        
        # Test 2: Caractères spéciaux
        print("   🔤 Test de caractères spéciaux...")
        special_data = {
            'test': 'Caractères: éàç ñ 中文 🔐 "quotes" \'apostrophe\' \\backslash'
        }
        
        keyring.set_password(service, "special", json.dumps(special_data, ensure_ascii=False))
        retrieved_special = json.loads(keyring.get_password(service, "special"))
        
        if retrieved_special == special_data:
            print("   ✅ Caractères spéciaux gérés correctement")
        else:
            print("   ⚠️ Problème avec les caractères spéciaux")
        
        # Test 3: Données volumineuses
        print("   📦 Test de données volumineuses...")
        large_data = {
            'api_key': 'x' * 1000,
            'config': {'data': 'y' * 5000}
        }
        
        keyring.set_password(service, "large", json.dumps(large_data))
        retrieved_large = json.loads(keyring.get_password(service, "large"))
        
        if len(retrieved_large['api_key']) == 1000:
            print("   ✅ Données volumineuses gérées correctement")
        else:
            print("   ⚠️ Problème avec les données volumineuses")
        
        # Nettoyage
        for key in ["sensitive", "special", "large"]:
            try:
                keyring.delete_password(service, key)
            except:
                pass
        
        print("   🧹 Nettoyage effectué")
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        return False

def test_error_handling():
    """Teste la gestion des erreurs"""
    print("\n🔍 Test 7: Gestion des erreurs")
    try:
        import keyring
        
        service = "AI_Conductor_TEST"
        
        # Test 1: Lecture d'une clé inexistante
        print("   🔍 Test de lecture d'une clé inexistante...")
        try:
            result = keyring.get_password(service, "nonexistent_key_12345")
            if result is None:
                print("   ✅ Retourne None pour clé inexistante")
            else:
                print(f"   ⚠️ Retourne '{result}' au lieu de None")
        except Exception as e:
            print(f"   ⚠️ Lève une exception: {type(e).__name__}")
        
        # Test 2: Suppression d'une clé inexistante
        print("   🗑️ Test de suppression d'une clé inexistante...")
        try:
            keyring.delete_password(service, "nonexistent_key_67890")
            print("   ⚠️ Suppression réussie (inattendu)")
        except keyring.errors.PasswordDeleteError:
            print("   ✅ PasswordDeleteError levée comme attendu")
        except Exception as e:
            print(f"   ⚠️ Exception inattendue: {type(e).__name__}")
        
        # Test 3: JSON invalide
        print("   📝 Test de JSON invalide...")
        keyring.set_password(service, "invalid_json", "{ invalid json }")
        stored = keyring.get_password(service, "invalid_json")
        try:
            json.loads(stored)
            print("   ⚠️ JSON invalide parsé sans erreur")
        except json.JSONDecodeError:
            print("   ✅ JSONDecodeError levée comme attendu")
        
        # Nettoyage
        try:
            keyring.delete_password(service, "invalid_json")
        except:
            pass
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        return False

def main():
    """Exécute tous les tests"""
    print("=" * 60)
    print("🔬 DIAGNOSTIC KEYRING COMPLET - AI CONDUCTOR")
    print("=" * 60)
    
    start_time = time.time()
    
    results = []
    results.append(("Installation keyring", test_keyring_installation()))
    results.append(("Import KeyringHelper", test_keyring_helper()))
    results.append(("Configurations plateformes", test_platform_configs()))
    results.append(("Test lecture/écriture", test_keyring_write()))
    results.append(("Intégration Widget", test_keyring_api_widget_integration()))
    results.append(("Vérifications sécurité", test_security_checks()))
    results.append(("Gestion des erreurs", test_error_handling()))
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, success in results:
        status = "✅ PASSÉ" if success else "❌ ÉCHEC"
        print(f"{status} - {name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"⏱️  Temps d'exécution: {elapsed_time:.2f}s")
    print(f"✅ Tests réussis: {passed}/{len(results)}")
    print(f"❌ Tests échoués: {failed}/{len(results)}")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 Tous les tests passent avec succès!")
        print("\n💡 CONSEILS D'UTILISATION:")
        print("   1. Ouvrez l'application et allez dans Configuration des clés API")
        print("   2. Sélectionnez une plateforme (Claude, Gemini, etc.)")
        print("   3. Entrez votre clé API")
        print("   4. Configurez le modèle (optionnel)")
        print("   5. Cliquez sur 'Tester la clé' pour valider")
        print("   6. Cliquez sur 'Enregistrer' pour sauvegarder")
        print("\n📚 La console de diagnostic vous guidera à chaque étape")
    else:
        print(f"\n⚠️  {failed} test(s) ont échoué")
        print("💡 Consultez les messages d'erreur ci-dessus pour plus de détails")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())