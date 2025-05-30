#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import json


def diagnostic_database():
    """Diagnostic complet de la base de données"""

    print("🔍 DIAGNOSTIC BASE DE DONNÉES LIRIS")
    print("=" * 50)

    # Localiser la base de données
    possible_paths = [
        "data/liris.db",
        "Liris/data/liris.db",
        "./data/liris.db"
    ]

    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print("❌ Fichier liris.db introuvable!")
        print("Chemins testés:", possible_paths)
        return

    print(f"✅ Base trouvée: {db_path}")
    print(f"📏 Taille: {os.path.getsize(db_path)} bytes")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\n📋 TABLES DISPONIBLES:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table['name']}")

        # Vérifier table platforms
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='platforms'")
        platforms_table = cursor.fetchone()

        if platforms_table:
            print("\n✅ Table 'platforms' existe")

            # Structure de la table
            cursor.execute("PRAGMA table_info(platforms)")
            columns = cursor.fetchall()
            print("📊 Colonnes:")
            for col in columns:
                print(f"  - {col['name']} ({col['type']})")

            # Contenu de la table
            cursor.execute("SELECT COUNT(*) as count FROM platforms")
            count = cursor.fetchone()['count']
            print(f"\n📈 Nombre d'enregistrements: {count}")

            if count > 0:
                print("\n🎯 PLATEFORMES EN BASE:")
                cursor.execute("SELECT name, created_at, updated_at FROM platforms")
                platforms = cursor.fetchall()
                for platform in platforms:
                    print(f"  - {platform['name']} (créé: {platform['created_at']}, MAJ: {platform['updated_at']})")

                # Détail du premier profil
                cursor.execute("SELECT name, profile_data FROM platforms LIMIT 1")
                first_platform = cursor.fetchone()
                if first_platform:
                    print(f"\n📄 EXEMPLE PROFIL ({first_platform['name']}):")
                    try:
                        profile_data = json.loads(first_platform['profile_data'])
                        extraction_config = profile_data.get('extraction_config', {})
                        response_area = extraction_config.get('response_area', {})
                        prompt_text = response_area.get('prompt_text', 'NON DÉFINI')
                        print(f"   📝 Prompt: '{prompt_text}'")
                        print(f"   🔧 Méthode: {response_area.get('method', 'NON DÉFINI')}")
                        print(f"   ⏱️ Wait time: {response_area.get('wait_time', 'NON DÉFINI')}")
                    except json.JSONDecodeError as e:
                        print(f"   ❌ JSON invalide: {str(e)}")
            else:
                print("⚠️ Table vide - aucune plateforme enregistrée")
        else:
            print("❌ Table 'platforms' inexistante")

        conn.close()

    except Exception as e:
        print(f"❌ Erreur: {str(e)}")


def test_get_platform():
    """Test direct de la méthode get_platform"""
    print("\n" + "=" * 50)
    print("🧪 TEST DIRECT get_platform")

    try:
        from core.data.database import Database

        db = Database()
        print("✅ Database instanciée")

        # Test get_platform pour ChatGPT
        print("\n🎯 Test db.get_platform('ChatGPT'):")
        result = db.get_platform('ChatGPT')
        print(f"Résultat: {result}")

        if result:
            print("✅ Profil trouvé en base")
            extraction_config = result.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})
            prompt_text = response_area.get('prompt_text', 'NON DÉFINI')
            print(f"📝 Prompt en base: '{prompt_text}'")
        else:
            print("❌ Aucun profil trouvé pour ChatGPT")

        db.close()

    except Exception as e:
        print(f"❌ Erreur test: {str(e)}")
        import traceback
        traceback.print_exc()


def migrate_json_to_db():
    """Migration forcée JSON vers DB"""
    print("\n" + "=" * 50)
    print("🔄 MIGRATION JSON → DATABASE")

    try:
        from core.data.database import Database

        db = Database()

        # Fichier ChatGPT.json
        json_file = "config/profiles/ChatGPT.json"
        if os.path.exists(json_file):
            print(f"📁 Lecture {json_file}")

            with open(json_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)

            print("📝 Profil JSON chargé")
            extraction_config = profile_data.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})
            prompt_text = response_area.get('prompt_text', 'PAS DE PROMPT_TEXT')
            print(f"📝 Prompt dans JSON: '{prompt_text}'")

            # AJOUTER UN PROMPT_TEXT S'IL N'EXISTE PAS
            if prompt_text == 'PAS DE PROMPT_TEXT':
                print("🔧 Ajout du prompt_text manquant...")
                if 'extraction_config' not in profile_data:
                    profile_data['extraction_config'] = {}
                if 'response_area' not in profile_data['extraction_config']:
                    profile_data['extraction_config']['response_area'] = {}
                profile_data['extraction_config']['response_area']['prompt_text'] = 'Bonjour, pouvez-vous me répondre ?'
                prompt_text = 'Bonjour, pouvez-vous me répondre ?'
                print(f"✅ Prompt ajouté: '{prompt_text}'")

            # Sauvegarder en base
            print("💾 Sauvegarde en base...")
            success = db.save_platform('ChatGPT', profile_data)
            print(f"Résultat: {success}")

            if success:
                # Vérifier
                print("🔍 Vérification...")
                saved_profile = db.get_platform('ChatGPT')
                if saved_profile:
                    saved_extraction = saved_profile.get('extraction_config', {})
                    saved_response = saved_extraction.get('response_area', {})
                    saved_prompt = saved_response.get('prompt_text', 'NON DÉFINI')
                    print(f"📝 Prompt sauvegardé: '{saved_prompt}'")
                    print("✅ Migration réussie!")
                else:
                    print("❌ Échec vérification")

        else:
            print(f"❌ Fichier {json_file} introuvable")

        # Migrer Claude aussi s'il existe
        claude_file = "config/profiles/Claude.json"
        if os.path.exists(claude_file):
            print(f"\n📁 Migration Claude...")
            with open(claude_file, 'r', encoding='utf-8') as f:
                claude_data = json.load(f)

            # Ajouter prompt_text s'il manque
            extraction_config = claude_data.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})
            if not response_area.get('prompt_text'):
                if 'extraction_config' not in claude_data:
                    claude_data['extraction_config'] = {}
                if 'response_area' not in claude_data['extraction_config']:
                    claude_data['extraction_config']['response_area'] = {}
                claude_data['extraction_config']['response_area']['prompt_text'] = 'Bonjour, pouvez-vous me répondre ?'

            success = db.save_platform('Claude', claude_data)
            print(f"✅ Claude migré: {success}")

        db.close()

    except Exception as e:
        print(f"❌ Erreur migration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Vérification et correction de la base de données Liris\n")

    # Étape 1: Vérifier la base
    diagnostic_database()
    print("\n" + "=" * 50)

    # Étape 2: Tester get_platform
    test_get_platform()
    print("\n" + "=" * 50)

    # Étape 3: Migrer les JSON
    migrate_json_to_db()

    print("\n" + "=" * 50)
    print("✅ Diagnostic terminé!")
    print("\n🎯 Relancez maintenant l'application")
    print("   Le debug devrait montrer:")
    print("   [DEBUG] ✅ PROFIL CHARGÉ DEPUIS DATABASE")
    print("   [DEBUG] Prompt sauvegardé trouvé: 'Votre prompt'")