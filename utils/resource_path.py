#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
utils/resource_path.py - Gestion des chemins de ressources pour PyInstaller
Résout les problèmes d'accès aux fichiers en mode .exe
"""

import os
import sys
from pathlib import Path


def is_frozen():
    """
    Vérifie si l'application est exécutée en mode frozen (PyInstaller)
    
    Returns:
        bool: True si frozen, False sinon
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_base_path():
    """
    Obtient le chemin de base de l'application
    
    Returns:
        Path: Chemin de base
    """
    if is_frozen():
        # En mode frozen, utiliser le répertoire temporaire de PyInstaller
        return Path(sys._MEIPASS)
    else:
        # En développement, utiliser le répertoire du script principal
        return Path(__file__).parent.parent


def get_executable_dir():
    """
    Obtient le répertoire de l'exécutable
    
    Returns:
        Path: Répertoire de l'exécutable
    """
    if is_frozen():
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


def resource_path(relative_path):
    """
    Obtient le chemin absolu vers une ressource embarquée.
    Fonctionne en développement et avec PyInstaller.
    À utiliser pour: images, traductions, fichiers de configuration embarqués
    
    Args:
        relative_path (str): Chemin relatif vers la ressource
        
    Returns:
        str: Chemin absolu vers la ressource
    """
    base = get_base_path()
    full_path = base / relative_path
    return str(full_path)


def data_path(relative_path):
    """
    Obtient le chemin vers les données utilisateur (persistantes).
    Utilise le répertoire de l'exécutable en .exe, le répertoire courant sinon.
    À utiliser pour: bases de données, fichiers de configuration utilisateur
    
    Args:
        relative_path (str): Chemin relatif vers les données
        
    Returns:
        str: Chemin absolu vers les données
    """
    base = get_executable_dir()
    full_path = base / relative_path
    return str(full_path)


def ensure_data_directory(relative_path):
    """
    S'assure que le répertoire de données existe.
    
    Args:
        relative_path (str): Chemin relatif vers le répertoire
        
    Returns:
        str: Chemin absolu vers le répertoire créé
    """
    full_path = data_path(relative_path)
    Path(full_path).mkdir(parents=True, exist_ok=True)
    return full_path


def get_config_path(filename):
    """
    Obtient le chemin vers un fichier de configuration utilisateur
    
    Args:
        filename (str): Nom du fichier de configuration
        
    Returns:
        str: Chemin absolu vers le fichier
    """
    ensure_data_directory('config')
    return data_path(os.path.join('config', filename))


def get_database_path(filename='liris.db'):
    """
    Obtient le chemin vers la base de données
    
    Args:
        filename (str): Nom du fichier de base de données
        
    Returns:
        str: Chemin absolu vers la base de données
    """
    ensure_data_directory('data')
    return data_path(os.path.join('data', filename))


def get_icon_path(icon_name):
    """
    Obtient le chemin vers une icône
    
    Args:
        icon_name (str): Nom de l'icône
        
    Returns:
        str: Chemin absolu vers l'icône
    """
    return resource_path(os.path.join('ui', 'resources', 'icons', icon_name))


def get_translation_path(language_code):
    """
    Obtient le chemin vers un fichier de traduction
    
    Args:
        language_code (str): Code de langue (ex: 'fr', 'en')
        
    Returns:
        str: Chemin absolu vers le fichier de traduction
    """
    return resource_path(
        os.path.join('ui', 'localization', 'translations', f'{language_code}.json')
    )


def debug_paths():
    """
    Affiche les chemins de débogage pour diagnostiquer les problèmes
    """
    print("=" * 60)
    print("DEBUG PATHS")
    print("=" * 60)
    print(f"is_frozen(): {is_frozen()}")
    print(f"sys.frozen: {getattr(sys, 'frozen', 'N/A')}")
    print(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    print(f"sys.executable: {sys.executable}")
    print(f"__file__: {__file__}")
    print(f"os.getcwd(): {os.getcwd()}")
    print(f"get_base_path(): {get_base_path()}")
    print(f"get_executable_dir(): {get_executable_dir()}")
    print(f"get_database_path(): {get_database_path()}")
    print(f"get_config_path('settings.json'): {get_config_path('settings.json')}")
    print("=" * 60)


# Test automatique au chargement du module
if __name__ == "__main__":
    debug_paths()