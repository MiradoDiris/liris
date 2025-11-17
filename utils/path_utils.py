#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
utils/path_utils.py
Utilitaire pour gérer les chemins de ressources avec PyInstaller
"""

import os
import sys


def get_resource_path(relative_path):
    """
    Obtient le chemin absolu vers une ressource, fonctionne en développement et avec PyInstaller
    
    Args:
        relative_path: Chemin relatif vers la ressource
        
    Returns:
        str: Chemin absolu vers la ressource
    """
    try:
        # PyInstaller crée un dossier temporaire et stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # En développement, utiliser le dossier courant
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def get_app_dir():
    """
    Obtient le dossier de l'application
    
    Returns:
        str: Chemin absolu vers le dossier de l'application
    """
    if getattr(sys, 'frozen', False):
        # Application buildée avec PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Mode développement
        return os.path.dirname(os.path.abspath(__file__))