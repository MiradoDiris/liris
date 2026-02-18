#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de test pour l'API OSS Dataset Generator
"""

import requests
import json
import time

# Configuration
BASE_URL = "https://airistech.ai"
# Pour test local, décommentez la ligne suivante :
# BASE_URL = "http://localhost:8083"

def test_health():
    """Test de l'endpoint /health"""
    print("\n" + "="*60)
    print("🏥 Test de l'endpoint /health")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service: {data.get('status')}")
            print(f"📦 Version: {data.get('version')}")
            print(f"🤖 Modèle: {data.get('model')}")
            print(f"\n⚙️ Configuration:")
            for key, value in data.get('config', {}).items():
                print(f"   • {key}: {value}")
        else:
            print(f"❌ Erreur: {response.text}")
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")

def test_generate_dataset(prompt="liasse fiscale", nb_samples=5):
    """Test de l'endpoint /generator/v1/generate-dataset"""
    print("\n" + "="*60)
    print(f"🎯 Test de génération de dataset")
    print("="*60)
    print(f"Prompt: {prompt}")
    print(f"Samples: {nb_samples}")
    
    try:
        payload = {
            "prompt": prompt,
            "nb_samples": nb_samples,
            "temperature": 0.3,
            "enable_parallel": False  # False pour petit nombre
        }
        
        print(f"\n📤 Envoi de la requête...")
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/generator/v1/generate-dataset",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minutes max
        )
        
        duration = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"⏱️ Durée: {duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == "success":
                print(f"\n✅ Génération réussie!")
                print(f"📊 Samples générés: {data.get('count')}/{data.get('requested')}")
                print(f"⚡ Vitesse: {data.get('samples_per_second', 0):.2f} samples/s")
                
                print(f"\n📄 Exemples de samples:")
                for i, sample in enumerate(data.get('samples', [])[:3], 1):
                    print(f"\n   Sample {i}:")
                    print(f"   Input:  {sample.get('input', '')[:80]}...")
                    print(f"   Output: {sample.get('output', '')[:80]}...")
                
                if data.get('count', 0) > 3:
                    print(f"\n   ... et {data['count'] - 3} autres samples")
                
                # Sauvegarder dans un fichier
                output_file = "dataset_test_result.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Résultats complets sauvegardés dans: {output_file}")
                
            else:
                print(f"❌ Erreur: {data.get('error', 'Erreur inconnue')}")
        else:
            print(f"❌ Erreur HTTP: {response.text}")
            
    except requests.Timeout:
        print(f"⏱️ Timeout: La requête a pris plus de 5 minutes")
    except Exception as e:
        print(f"❌ Erreur: {e}")

def test_config():
    """Test de l'endpoint /config"""
    print("\n" + "="*60)
    print("⚙️ Test de mise à jour de la configuration")
    print("="*60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/config",
            params={
                "batch_size": 15,
                "parallel_workers": 8
            }
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuration mise à jour")
            print(f"\n📋 Nouvelle configuration:")
            for key, value in data.get('config', {}).items():
                print(f"   • {key}: {value}")
        else:
            print(f"❌ Erreur: {response.text}")
    except Exception as e:
        print(f"❌ Erreur: {e}")

def main():
    """Fonction principale de test"""
    print("\n" + "="*70)
    print("🧪 Tests de l'API OSS Dataset Generator")
    print("="*70)
    print(f"🌐 URL de base: {BASE_URL}")
    
    # Test 1: Health check
    test_health()
    
    # Test 2: Génération de dataset (petit échantillon)
    test_generate_dataset(prompt="liasse fiscale", nb_samples=5)
    
    # Test 3: Configuration (optionnel)
    # test_config()
    
    print("\n" + "="*70)
    print("✅ Tests terminés!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()