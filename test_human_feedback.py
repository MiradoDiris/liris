import requests
import json
import time

API_URL = "http://localhost:8086"

def test_feedback_flow():
    """Test complet du flux de feedback humain"""
    
    print("\n" + "="*80)
    print("🧪 TEST DU SYSTÈME DE FEEDBACK HUMAIN")
    print("="*80)
    
    # Vérifier que l'API est accessible
    print("\n🔍 Vérification de l'API...")
    try:
        response = requests.get(f"{API_URL}/")
        print(f"✅ API accessible - Status: {response.status_code}")
    except Exception as e:
        print(f"❌ API non accessible: {e}")
        return
    
    # TEST 1: Sample très ambigu (devrait déclencher faible confiance)
    print("\n" + "="*80)
    print("📤 TEST 1: Sample TRÈS ambigu")
    print("="*80)
    
    test_cases = [
        {
            "name": "Sample ultra-court et vague",
            "sample": {
                "sample_id": 100,
                "input": "C'est où ?",
                "output": "Là.",
                "validation_level": "strict",
                "rlhf_validation": True,
                "request_human_feedback": True,
                "confidence_threshold": 0.7
            }
        },
        {
            "name": "Sample avec symboles interdits",
            "sample": {
                "sample_id": 101,
                "input": "Comment aller aux factures ?",
                "output": "Menu > Ventes > Factures",
                "validation_level": "strict",
                "rlhf_validation": True,
                "request_human_feedback": True,
                "confidence_threshold": 0.7
            }
        },
        {
            "name": "Sample incohérent",
            "sample": {
                "sample_id": 102,
                "input": "Comment créer une facture ?",
                "output": "Pour gérer vos stocks, consultez l'inventaire.",
                "validation_level": "strict",
                "rlhf_validation": True,
                "request_human_feedback": True,
                "confidence_threshold": 0.7
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'─'*80}")
        print(f"🧪 Test: {test_case['name']}")
        print(f"{'─'*80}")
        
        response = requests.post(
            f"{API_URL}/verify-with-feedback",
            json=test_case['sample']
        )
        
        print(f"Status code: {response.status_code}")
        
        try:
            result = response.json()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Vérifier si feedback requis
            if result.get("needs_human_feedback"):
                print("\n✅ Feedback humain requis (comme attendu)")
                
                validation_id = result["validation_id"]
                pending_info = result["pending_feedback"]
                
                print(f"\n📋 Informations de la validation en attente:")
                print(f"   ID: {validation_id}")
                print(f"   Confiance RLHF: {pending_info['confidence_score']:.2%}")
                print(f"   Suggestion RLHF: {pending_info['suggested_decision']}")
                print(f"   Raisons de révision:")
                for reason in pending_info['reasons_for_review']:
                    print(f"      - {reason}")
                
                # Soumettre un feedback
                print("\n✍️  Soumission du feedback humain...")
                
                human_feedback = {
                    "sample_id": test_case['sample']['sample_id'],
                    "validation_id": validation_id,
                    "user_decision": "invalid",
                    "user_comments": "Effectivement invalide",
                    "corrected_output": "Pour créer une facture, allez dans Ventes puis cliquez sur Nouvelle facture.",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                
                response = requests.post(
                    f"{API_URL}/submit-feedback",
                    json=human_feedback
                )
                
                print(f"Status: {response.status_code}")
                feedback_result = response.json()
                print(json.dumps(feedback_result, indent=2, ensure_ascii=False))
                
                # Afficher les stats
                print("\n📊 Statistiques des feedbacks:")
                stats_response = requests.get(f"{API_URL}/feedback-statistics")
                stats = stats_response.json()
                print(json.dumps(stats, indent=2, ensure_ascii=False))
                
                break  # Sortir après le premier feedback réussi
                
            else:
                print("\n⚠️  Pas de feedback requis")
                print(f"   Confiance: {result.get('confidence', 'N/A')}")
                print(f"   Issues: {len(result.get('issues', []))}")
                if result.get('rlhf_data'):
                    print(f"   RLHF data: {result['rlhf_data']}")
        
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "="*80)
    print("✅ TESTS TERMINÉS")
    print("="*80)

if __name__ == "__main__":
    test_feedback_flow()