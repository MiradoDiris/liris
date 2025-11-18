#!/usr/bin/env python3
"""
Script de test pour SnippetCard avec historique conversationnel
"""

from PyQt5 import QtWidgets
import sys
import os

# Ajouter le chemin du module si nécessaire
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Données de test - AVEC HISTORIQUE
test_snippet_with_history = {
    'title': 'AJOUTER - Code dans test.py',
    'action': 'AJOUTER',
    'file': 'core/orchestration/test.py',
    'code': 'def test():\n    pass',
    'language': 'python',
    'description': 'Test snippet',
    'lineNumber': 0,
    'target': 'def main()',
    'platform': 'Claude',
    'session_info': {
        'session_id': 'session_20250119_123456',
        'total_messages': 6,
        'conversation_turns': 3,
        'has_context': True  # ✅ IMPORTANT: True pour afficher l'icône
    },
    'conversation_history': [
        {
            'role': 'user',
            'content': 'Peux-tu créer une fonction de test ?'
        },
        {
            'role': 'assistant',
            'content': 'Bien sûr ! Voici une fonction de test simple...'
        },
        {
            'role': 'user',
            'content': 'Ajoute la gestion des erreurs'
        }
    ]
}

# Données de test - SANS HISTORIQUE
test_snippet_without_history = {
    'title': 'MODIFIER - Code dans autre.py',
    'action': 'MODIFIER',
    'file': 'utils/helpers.py',
    'code': 'def helper():\n    return True',
    'language': 'python',
    'description': 'Helper function',
    'lineNumber': 0,
    'target': '',
    'platform': 'ChatGPT'
    # ❌ Pas de session_info = pas d'icône
}

def main():
    print("\n" + "="*60)
    print("🧪 LANCEMENT DU TEST SNIPPET CARD")
    print("="*60 + "\n")
    
    app = QtWidgets.QApplication(sys.argv)
    
    # Créer une fenêtre de test
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Test SnippetCard - Icône Historique")
    window.setGeometry(100, 100, 900, 700)
    
    # Widget central avec scroll
    scroll = QtWidgets.QScrollArea()
    window.setCentralWidget(scroll)
    scroll.setWidgetResizable(True)
    
    central_widget = QtWidgets.QWidget()
    scroll.setWidget(central_widget)
    
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setSpacing(20)
    
    # Titre principal
    title_label = QtWidgets.QLabel("🧪 Test des SnippetCard - Debug Icône Historique")
    title_label.setStyleSheet("""
        font-size: 18px; 
        font-weight: bold; 
        padding: 15px;
        background: #2563eb;
        color: white;
        border-radius: 4px;
    """)
    layout.addWidget(title_label)
    
    # Instructions
    instructions = QtWidgets.QLabel(
        "📋 Instructions:\n"
        "• La carte 1 DOIT afficher l'icône ☰ (trois barres) à gauche du titre\n"
        "• La carte 2 NE DOIT PAS afficher l'icône (pas d'historique)\n"
        "• Vérifiez la console pour les messages de debug"
    )
    instructions.setStyleSheet("""
        padding: 10px;
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
        font-size: 11px;
    """)
    instructions.setWordWrap(True)
    layout.addWidget(instructions)
    
    # Importer SnippetCard
    try:
        from ui.widgets.tabs.snippet_card import SnippetCard
        
        # ===== SNIPPET 1: AVEC HISTORIQUE =====
        print("\n" + "🔵"*30)
        print("CRÉATION SNIPPET 1 - AVEC HISTORIQUE")
        print("🔵"*30)
        
        label1 = QtWidgets.QLabel("✅ Carte 1: AVEC historique conversationnel")
        label1.setStyleSheet("""
            padding: 10px; 
            background: #dbeafe;
            border-left: 4px solid #2563eb;
            font-weight: bold;
        """)
        layout.addWidget(label1)
        
        card1 = SnippetCard(test_snippet_with_history)
        card1.setStyleSheet("border: 2px solid #2563eb; border-radius: 4px;")
        layout.addWidget(card1)
        
        # ===== SNIPPET 2: SANS HISTORIQUE =====
        print("\n" + "🔴"*30)
        print("CRÉATION SNIPPET 2 - SANS HISTORIQUE")
        print("🔴"*30)
        
        label2 = QtWidgets.QLabel("❌ Carte 2: SANS historique conversationnel")
        label2.setStyleSheet("""
            padding: 10px; 
            background: #fee2e2;
            border-left: 4px solid #dc2626;
            font-weight: bold;
            margin-top: 20px;
        """)
        layout.addWidget(label2)
        
        card2 = SnippetCard(test_snippet_without_history)
        card2.setStyleSheet("border: 2px solid #dc2626; border-radius: 4px;")
        layout.addWidget(card2)
        
        layout.addStretch()
        
        # Résumé
        summary = QtWidgets.QLabel(
            "🎯 RÉSULTAT ATTENDU:\n\n"
            "Carte 1 (bleue):\n"
            "  [☰] Code généré    ← L'icône ☰ doit être visible ici\n"
            "  [A ajouter]\n\n"
            "Carte 2 (rouge):\n"
            "  Code généré        ← Pas d'icône\n"
            "  [A modifier]"
        )
        summary.setStyleSheet("""
            padding: 15px;
            background: #f3f4f6;
            border: 2px dashed #9ca3af;
            font-family: monospace;
            font-size: 11px;
            margin-top: 20px;
        """)
        summary.setWordWrap(True)
        layout.insertWidget(2, summary)
        
        print("\n" + "="*60)
        print("✅ FENÊTRE CRÉÉE - Vérifiez les logs ci-dessus")
        print("="*60 + "\n")
        
    except ImportError as e:
        error_label = QtWidgets.QLabel(
            f"❌ ERREUR D'IMPORT\n\n"
            f"Détails: {e}\n\n"
            f"Assurez-vous que snippet_card.py est dans le même dossier "
            f"ou accessible dans le PYTHONPATH"
        )
        error_label.setStyleSheet("""
            color: #dc2626; 
            padding: 20px;
            background: #fee2e2;
            border: 2px solid #dc2626;
            border-radius: 4px;
        """)
        error_label.setWordWrap(True)
        layout.addWidget(error_label)
        print(f"\n❌ ERREUR: {e}\n")
    
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()