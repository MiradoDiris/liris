#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de test des endpoints GRPO
Vérifie que tous les services nécessaires sont opérationnels
"""

import requests
import json
from typing import Dict, Any
import sys

def test_vllm_connection() -> bool:
    """Test connexion vLLM"""
    print("\n" + "="*60)
    print("TEST 1: Connexion vLLM (Port 8000)")
    print("="*60)
    
    try:
        response = requests.get("http://localhost:8000/v1/models", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            print("✅ vLLM: CONNECTÉ")
            print(f"   URL: http://localhost:8000/v1")
            
            if 'data' in models_data:
                for model in models_data['data']:
                    print(f"   Modèle: {model.get('id', 'N/A')}")
            
            return True
        else:
            print(f"❌ vLLM: Status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ vLLM: Service non démarré")
        print("   💡 Démarrer avec: python -m vllm.entrypoints.openai.api_server --model MODEL_NAME")
        return False
    except Exception as e:
        print(f"❌ vLLM: Erreur - {e}")
        return False

def test_reward_api_connection(port: int = 8086) -> bool:
    """Test connexion Reward API"""
    print("\n" + "="*60)
    print(f"TEST 2: Connexion Reward API (Port {port})")
    print("="*60)
    
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Reward API: CONNECTÉ")
            print(f"   URL: http://localhost:{port}")
            print(f"   Status: {health_data.get('status', 'N/A')}")
            print(f"   vLLM Status: {health_data.get('vllm_status', 'N/A')}")
            print(f"   Model: {health_data.get('model', 'N/A')}")
            return True
        else:
            print(f"❌ Reward API: Status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Reward API: Service non démarré sur port {port}")
        print("   💡 Démarrer avec: python verification_api.py")
        return False
    except Exception as e:
        print(f"❌ Reward API: Erreur - {e}")
        return False

def test_verify_batch_endpoint(port: int = 8086) -> bool:
    """Test endpoint /verify-batch (utilisé par GRPO)"""
    print("\n" + "="*60)
    print("TEST 3: Endpoint /verify-batch")
    print("="*60)
    
    test_data = {
        "samples": [
            {
                "sample_id": 0,
                "input": "Comment accéder au menu principal ?",
                "output": "Allez dans le menu Fichier puis sélectionnez Options."
            },
            {
                "sample_id": 1,
                "input": "Où trouver les paramètres ?",
                "output": "Les paramètres se trouvent dans le menu Outils, sous-menu Configuration."
            }
        ],
        "validation_level": "standard",
        "rlhf_validation": False,  # Désactiver RLHF pour test rapide
        "domain": "comptabilité"
    }
    
    try:
        print("   Envoi de 2 samples de test...")
        response = requests.post(
            f"http://localhost:{port}/verify-batch",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ /verify-batch: FONCTIONNEL")
            print(f"   Total samples: {result.get('total_samples', 0)}")
            print(f"   Valid: {result.get('valid_samples', 0)}")
            print(f"   Warning: {result.get('warning_samples', 0)}")
            print(f"   Invalid: {result.get('invalid_samples', 0)}")
            print(f"   Quality globale: {result.get('overall_quality_score', 0):.2f}/100")
            
            # Afficher détails premier sample
            if result.get('results'):
                first_result = result['results'][0]
                print(f"\n   Détails Sample #0:")
                print(f"      Quality: {first_result.get('quality_score', 0):.2f}/100")
                print(f"      Status: {first_result.get('status', 'N/A')}")
                print(f"      Issues: {len(first_result.get('issues', []))}")
            
            return True
        else:
            print(f"❌ /verify-batch: Status {response.status_code}")
            print(f"   Erreur: {response.text[:200]}")
            return False
    except requests.exceptions.Timeout:
        print("❌ /verify-batch: TIMEOUT (>30s)")
        print("   💡 L'API prend trop de temps à répondre")
        return False
    except Exception as e:
        print(f"❌ /verify-batch: Erreur - {e}")
        return False

def test_grpo_format_compatibility(port: int = 8086) -> bool:
    """Test compatibilité format GRPO"""
    print("\n" + "="*60)
    print("TEST 4: Compatibilité Format GRPO")
    print("="*60)
    
    # Format exact utilisé par reward_model.py
    grpo_format = {
        "samples": [{
            "sample_id": 999,
            "input": "Test GRPO format",
            "output": "Réponse test pour vérifier compatibilité format GRPO avec l'API."
        }],
        "validation_level": "strict",
        "rlhf_validation": True,
        "domain": "comptabilité"
    }
    
    try:
        print("   Test du format exact utilisé par GRPO...")
        response = requests.post(
            f"http://localhost:{port}/verify-batch",
            json=grpo_format,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Vérifier que les champs attendus par GRPO sont présents
            required_fields = ['results']
            missing = [f for f in required_fields if f not in result]
            
            if missing:
                print(f"❌ Format incompatible: champs manquants {missing}")
                return False
            
            # Vérifier le format du premier résultat
            if result['results']:
                first = result['results'][0]
                required_result_fields = ['sample_id', 'quality_score', 'status']
                missing_result = [f for f in required_result_fields if f not in first]
                
                if missing_result:
                    print(f"❌ Format incompatible: champs résultat manquants {missing_result}")
                    return False
                
                print("✅ Format GRPO: COMPATIBLE")
                print(f"   sample_id: {first['sample_id']}")
                print(f"   quality_score (reward): {first['quality_score']:.2f}")
                print(f"   status: {first['status']}")
                print("\n   ✅ Le champ 'quality_score' sera utilisé comme REWARD par GRPO")
                return True
            else:
                print("❌ Pas de résultats dans la réponse")
                return False
        else:
            print(f"❌ Format GRPO: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Format GRPO: Erreur - {e}")
        return False

def test_port_conflict(config_port: int = 8086, api_port: int = 8086):
    """Détecte le conflit de ports"""
    print("\n" + "="*60)
    print("TEST 5: Détection Conflit de Ports")
    print("="*60)
    
    print(f"   Config GRPO (config.py): http://localhost:{config_port}")
    print(f"   API Vérification: http://localhost:{api_port}")
    
    if config_port != api_port:
        print(f"\n⚠️  CONFLIT DÉTECTÉ!")
        print(f"   GRPO essaiera de contacter le port {config_port}")
        print(f"   Mais l'API écoute sur le port {api_port}")
        print(f"\n💡 SOLUTIONS:")
        print(f"   1. Modifier config.py ligne 18:")
        print(f"      reward_api_url: str = \"http://localhost:{api_port}\"")
        print(f"   2. OU modifier l'API pour écouter sur port {config_port}")
        return False
    else:
        print(f"\n✅ Pas de conflit: les deux utilisent le port {api_port}")
        return True

def generate_summary_report(results: Dict[str, bool]):
    """Génère un rapport de synthèse"""
    print("\n" + "="*70)
    print("RAPPORT DE SYNTHÈSE - ENDPOINTS GRPO")
    print("="*70)
    
    all_tests = {
        "vllm": ("vLLM (Génération)", results.get("vllm", False)),
        "reward_api": ("Reward API (Scoring)", results.get("reward_api", False)),
        "verify_batch": ("/verify-batch (Rewards)", results.get("verify_batch", False)),
        "grpo_format": ("Format GRPO", results.get("grpo_format", False)),
        "port_check": ("Configuration Ports", results.get("port_check", False))
    }
    
    print("\n📊 Résultats des Tests:\n")
    
    for key, (name, passed) in all_tests.items():
        status = "✅ OK" if passed else "❌ KO"
        print(f"   {status:10} {name}")
    
    all_passed = all(passed for _, passed in all_tests.values())
    
    print("\n" + "="*70)
    
    if all_passed:
        print("🎉 TOUS LES TESTS SONT PASSÉS!")
        print("\n✅ Votre environnement est PRÊT pour le GRPO Training")
        print("\n📝 Prochaines étapes:")
        print("   1. Lancer l'API: python verification_api.py")
        print("   2. Lancer GRPO: python main_grpo.py")
        print("   3. (Optionnel) Monitor: python monitor_training.py")
    else:
        failed = [name for name, passed in all_tests.values() if not passed]
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        print(f"\n❌ Tests échoués: {', '.join(failed)}")
        print("\n💡 Consultez les détails ci-dessus pour les corrections")
        print("\n📖 Voir: corrections_endpoints_grpo.md pour les solutions")
    
    print("="*70 + "\n")
    
    return all_passed

def main():
    """Fonction principale"""
    print("\n")
    print("="*70)
    print("🔍 TEST DES ENDPOINTS GRPO")
    print("="*70)
    print("\nCe script vérifie que tous les services nécessaires")
    print("au fonctionnement du GRPO Training sont opérationnels.\n")
    
    results = {}
    
    # Test 1: vLLM
    results["vllm"] = test_vllm_connection()
    
    # Test 2: Reward API (essayer les deux ports)
    reward_api_ok = False
    detected_port = None
    
    for port in [8085, 8086]:
        if test_reward_api_connection(port):
            reward_api_ok = True
            detected_port = port
            break
    
    results["reward_api"] = reward_api_ok
    
    if not reward_api_ok:
        print("\n⚠️  Reward API non accessible - Arrêt des tests")
        generate_summary_report(results)
        sys.exit(1)
    
    # Test 3: verify-batch endpoint
    results["verify_batch"] = test_verify_batch_endpoint(detected_port)
    
    # Test 4: Format GRPO
    results["grpo_format"] = test_grpo_format_compatibility(detected_port)
    
    # Test 5: Port conflict
    config_port = 8086  # Port défini dans config.py
    results["port_check"] = test_port_conflict(config_port, detected_port)
    
    # Rapport final
    all_passed = generate_summary_report(results)
    
    # Code de sortie
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrompus par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)