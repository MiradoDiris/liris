# Test script - vérification_tables.py
import sqlite3
import os

def test_tables():
    db_path = "data/liris.db"  # Remplacez par le chemin réel
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Vérifier que les tables existent
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables existantes:", tables)
    
    # Vérifier la structure de context_typologies
    cursor.execute("PRAGMA table_info(context_typologies)")
    columns = cursor.fetchall()
    print("Colonnes de context_typologies:", columns)
    
    # Vérifier la structure de strategy_items
    cursor.execute("PRAGMA table_info(strategy_items)")
    columns = cursor.fetchall()
    print("Colonnes de strategy_items:", columns)
    
    conn.close()

if __name__ == "__main__":
    test_tables()