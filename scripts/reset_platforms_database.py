#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
reset_platforms_database.py - Réinitialise la base de données des plateformes d'IA et les configurations associées.
"""

import os
import sqlite3
import shutil
from PyQt5.QtCore import QSettings

print("=== Réinitialisation des configurations des plateformes d'IA ===")

# 1. Réinitialiser les paramètres QSettings
settings = QSettings("Liris", "IACollaborative")
settings.clear()  # Efface tous les paramètres, pas seulement la langue
settings.sync()
print("✓ Tous les paramètres QSettings effacés")

# 2. Réinitialiser la base de données
db_path = os.path.join("data", "liris.db")
try:
    if os.path.exists(db_path):
        # Créer une sauvegarde de la base de données
        backup_path = db_path + ".backup"
        shutil.copy2(db_path, backup_path)
        print(f"✓ Sauvegarde de la base de données créée: {backup_path}")

        # Vider la table des plateformes
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_platforms")
        conn.commit()
        conn.close()
        print("✓ Table des plateformes vidée")
except Exception as e:
    print(f"✗ Erreur lors de la réinitialisation de la base de données: {str(e)}")

# 3. Réinitialiser les fichiers de profils
profiles_dir = os.path.join("config", "profiles")
try:
    if os.path.exists(profiles_dir):
        # Créer une sauvegarde du dossier des profils
        backup_dir = profiles_dir + "_backup"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.copytree(profiles_dir, backup_dir)
        print(f"✓ Sauvegarde des profils créée: {backup_dir}")

        # Supprimer uniquement les fichiers JSON et les marqueurs de suppression
        for file in os.listdir(profiles_dir):
            if file.endswith(".json") or file.startswith(".") and file.endswith(".deleted"):
                os.remove(os.path.join(profiles_dir, file))
        print("✓ Fichiers de profils supprimés")
except Exception as e:
    print(f"✗ Erreur lors de la réinitialisation des fichiers de profils: {str(e)}")

# 4. Supprimer le fichier marqueur d'initialisation
marker_file = os.path.join("ui", ".platforms_initialized")
try:
    if os.path.exists(marker_file):
        os.remove(marker_file)
        print("✓ Marqueur d'initialisation supprimé")
except Exception as e:
    print(f"✗ Erreur lors de la suppression du marqueur: {str(e)}")

print("\nRéinitialisation terminée. Redémarrez l'application.")
print("Les plateformes par défaut seront recréées au prochain démarrage.")