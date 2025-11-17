#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/main.py
Point d'entrée de l'application avec dialogue de langue au démarrage
"""

import sys
import os
import traceback
import platform
import subprocess
from datetime import datetime
from typing import List, Optional
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QSettings, QTimer

# Import des utilitaires de gestion des chemins
def get_resource_path(relative_path):
    """Obtient le chemin absolu vers une ressource"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from ui.localization.translator import translator, tr
from ui.widgets.language_selector import LanguageSelector
from utils.logger import logger

import gc

sys.setrecursionlimit(50000)
gc.set_threshold(700, 10, 10)

try:
    import resource
    resource.setrlimit(resource.RLIMIT_STACK, (2**29, -1))
    logger.info("✅ Stack size augmenté à 512MB")
except:
    logger.info("⚠️ Impossible d'augmenter stack size (normal sous Windows)")
    pass

logger.info(f"✅ Configuration Python: recursion={sys.getrecursionlimit()}")


class LinuxWindow:
    """Linux window object mimicking PyGetWindow's Window class"""
    
    def __init__(self, title: str, window_id: str, x: int, y: int, width: int, height: int):
        self.title = title
        self._window_id = window_id
        self._x = x
        self._y = y
        self._width = width
        self._height = height
    
    @property
    def left(self) -> int:
        return self._x
    
    @property
    def top(self) -> int:
        return self._y
    
    @property
    def width(self) -> int:
        return self._width
    
    @property
    def height(self) -> int:
        return self._height
    
    @property
    def right(self) -> int:
        return self._x + self._width
    
    @property
    def bottom(self) -> int:
        return self._y + self._height
    
    def moveTo(self, x: int, y: int):
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-e', f'0,{x},{y},-1,-1'], 
                          check=True)
            self._x = x
            self._y = y
        except subprocess.CalledProcessError:
            pass
    
    def resizeTo(self, width: int, height: int):
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-e', f'0,-1,-1,{width},{height}'], 
                          check=True)
            self._width = width
            self._height = height
        except subprocess.CalledProcessError:
            pass
    
    def minimize(self):
        try:
            subprocess.run(['xdotool', 'windowminimize', self._window_id], check=True)
        except subprocess.CalledProcessError:
            pass
    
    def maximize(self):
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-b', 'add,maximized_vert,maximized_horz'], 
                          check=True)
        except subprocess.CalledProcessError:
            pass
    
    def activate(self):
        try:
            subprocess.run(['xdotool', 'windowactivate', self._window_id], check=True)
        except subprocess.CalledProcessError:
            pass
    
    def close(self):
        try:
            subprocess.run(['xdotool', 'windowclose', self._window_id], check=True)
        except subprocess.CalledProcessError:
            pass
    
    def __str__(self):
        return f"LinuxWindow(title='{self.title}', left={self.left}, top={self.top}, width={self.width}, height={self.height})"
    
    def __repr__(self):
        return self.__str__()


def getAllWindows() -> List[LinuxWindow]:
    """Get all windows - Linux implementation"""
    windows = []
    
    try:
        result = subprocess.run(['wmctrl', '-l', '-G'], capture_output=True, text=True, check=True)
        
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 7:
                window_id = parts[0]
                x = int(parts[2])
                y = int(parts[3])
                width = int(parts[4])
                height = int(parts[5])
                title = ' '.join(parts[7:])
                
                if (title and 
                    not title.startswith('@') and
                    title != 'Desktop' and
                    width > 0 and height > 0):
                    
                    windows.append(LinuxWindow(title, window_id, x, y, width, height))
    
    except subprocess.CalledProcessError as e:
        print(f"Error getting windows: {e}")
    
    return windows


def getWindowsWithTitle(title: str, exact: bool = False) -> List[LinuxWindow]:
    """Find windows by title"""
    all_windows = getAllWindows()
    
    if exact:
        return [w for w in all_windows if w.title == title]
    else:
        return [w for w in all_windows if title.lower() in w.title.lower()]


def getActiveWindow() -> Optional[LinuxWindow]:
    """Get the currently active window"""
    try:
        result = subprocess.run(['xdotool', 'getactivewindow'], 
                              capture_output=True, text=True, check=True)
        window_id = result.stdout.strip()
        
        result = subprocess.run(['xdotool', 'getwindowgeometry', window_id], 
                              capture_output=True, text=True, check=True)
        
        x, y, width, height = 0, 0, 0, 0
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'Position:' in line:
                pos_part = line.split('Position:')[1].strip()
                if '(' in pos_part:
                    pos_part = pos_part.split('(')[0].strip()
                try:
                    x, y = map(int, pos_part.split(','))
                except ValueError:
                    coords = pos_part.replace(' ', '').split(',')
                    if len(coords) >= 2:
                        x, y = int(coords[0]), int(coords[1])
            elif 'Geometry:' in line:
                geo_part = line.split('Geometry:')[1].strip()
                width, height = map(int, geo_part.split('x'))
        
        title_result = subprocess.run(['xdotool', 'getwindowname', window_id], 
                                    capture_output=True, text=True, check=True)
        title = title_result.stdout.strip()
        
        return LinuxWindow(title, window_id, x, y, width, height)
    
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Error getting active window: {e}")
        return None


def getWindowsAt(x: int, y: int) -> List[LinuxWindow]:
    """Get windows at specified coordinates"""
    all_windows = getAllWindows()
    return [w for w in all_windows if w.left <= x <= w.right and w.top <= y <= w.bottom]


def setup_application_paths():
    """Configure les chemins de l'application"""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


def setup_platform_environment():
    """Configure l'environnement selon la plateforme"""
    system = platform.system()
    
    if system == "Linux":
        print(f"   → Plateforme détectée: Linux")
        
        display = os.environ.get('DISPLAY')
        if not display:
            print("   → Pas de DISPLAY détecté, configuration pour environnement headless")
        
        try:
            tools_missing = []
            
            try:
                subprocess.run(['wmctrl', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                tools_missing.append('wmctrl')
            
            try:
                subprocess.run(['xdotool', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                tools_missing.append('xdotool')
            
            if tools_missing:
                print(f"   ⚠ Outils manquants: {', '.join(tools_missing)}")
            else:
                print("   ✓ Outils de gestion des fenêtres Linux disponibles")
                
        except Exception as e:
            print(f"   ⚠ Erreur lors de la vérification des outils: {e}")
    
    elif system == "Windows":
        print(f"   → Plateforme détectée: Windows")
        print("   ✓ Support complet des fonctionnalités Windows")
    
    else:
        print(f"   → Plateforme détectée: {system}")


def import_with_fallback():
    """Importe MainWindow avec gestion des erreurs spécifiques à la plateforme"""
    system = platform.system()
    
    if system == "Linux":
        try:
            subprocess.run(['wmctrl', '--version'], capture_output=True, check=True)
            subprocess.run(['xdotool', '--version'], capture_output=True, check=True)
            
            sys.modules['pygetwindow'] = type('module', (), {
                'getAllWindows': getAllWindows,
                'getWindowsWithTitle': getWindowsWithTitle,
                'getActiveWindow': getActiveWindow,
                'getWindowsAt': getWindowsAt,
                'Win32Window': LinuxWindow
            })
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ImportError(
                "Outils nécessaires (wmctrl, xdotool) non installés. "
                "Installez-les avec 'sudo apt-get install wmctrl xdotool'."
            )
    
    elif system == "Windows":
        try:
            import pygetwindow as gw
            sys.modules['pygetwindow'] = gw
        except ImportError:
            raise ImportError("pygetwindow n'est pas installé. Installez-le avec 'pip install pygetwindow'.")
    
    else:
        raise NotImplementedError(f"Plateforme {system} non supportée")
    
    from ui.main_window import MainWindow
    return MainWindow


def show_language_selector_standalone(app):
    """
    Affiche le sélecteur de langue en mode standalone (sans fenêtre principale)
    Retourne la langue sélectionnée ou None si annulé
    """
    try:
        selector = LanguageSelector()
        
        # Configuration pour mode standalone
        selector.setWindowModality(QtCore.Qt.ApplicationModal)
        selector.setWindowFlags(
            QtCore.Qt.Dialog | 
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        
        # Centrer sur l'écran
        screen = app.primaryScreen().geometry()
        selector.move(
            (screen.width() - selector.width()) // 2,
            (screen.height() - selector.height()) // 2
        )
        
        # Sélectionner le français par défaut
        for i in range(selector.language_combo.count()):
            if selector.language_combo.itemData(i) == "fr":
                selector.language_combo.setCurrentIndex(i)
                break
        
        print("   → Affichage du sélecteur de langue...")
        
        # Afficher et attendre
        result = selector.exec_()
        
        if result == QtWidgets.QDialog.Accepted:
            selected_language = selector.get_selected_language()
            print(f"   ✓ Langue sélectionnée: {selected_language}")
            return selected_language
        else:
            print("   → Sélection annulée, utilisation du français par défaut")
            return "fr"
            
    except Exception as e:
        print(f"   ✗ Erreur lors de l'affichage du sélecteur: {e}")
        traceback.print_exc()
        return "fr"  # Fallback sur français


def main():
    print("\n=== DÉMARRAGE DE L'APPLICATION LIRIS ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Plateforme: {platform.system()} {platform.release()}")
    
    if getattr(sys, 'frozen', False):
        print(f"Mode: Exécutable buildé (PyInstaller)")
        print(f"Dossier temporaire: {sys._MEIPASS}")
    else:
        print(f"Mode: Développement")

    # Configurer les chemins
    print("\n1. Configuration des chemins...")
    setup_application_paths()
    print("   ✓ Chemins configurés")

    # Configuration spécifique à la plateforme
    print("\n2. Configuration de la plateforme...")
    setup_platform_environment()

    try:
        # Créer l'application Qt
        print("\n3. Création de QApplication...")
        app = QtWidgets.QApplication(sys.argv)
        
        if platform.system() == "Linux" and not os.environ.get('DISPLAY'):
            app.setAttribute(QtWidgets.QApplication.AA_X11InitThreads, True)
        
        print("   ✓ QApplication créée")

        # Gérer la sélection de langue
        print("\n4. Gestion de la langue...")
        settings = QSettings("Liris", "IACollaborative")
        settings.remove("language")
        saved_language = settings.value("language", None)
        
        selected_language = None
        
        if saved_language and saved_language in translator.get_available_languages():
            # Langue déjà sauvegardée
            print(f"   → Langue sauvegardée trouvée: {saved_language}")
            selected_language = saved_language
        else:
            # Première utilisation - Afficher le dialogue en mode standalone
            print("   → Première utilisation détectée")
            print("   → Affichage du sélecteur de langue en mode standalone...")
            
            # Afficher le dialogue AVANT de charger la fenêtre principale
            selected_language = show_language_selector_standalone(app)
            
            # Sauvegarder la sélection
            if selected_language:
                settings.setValue("language", selected_language)
                print(f"   ✓ Langue sauvegardée: {selected_language}")
        
        # Charger la langue sélectionnée
        if selected_language:
            success = translator.set_language(selected_language)
            if success:
                print(f"   ✓ Langue activée: {selected_language}")
            else:
                print(f"   ✗ Erreur lors du chargement de {selected_language}")
                translator.set_language(translator.DEFAULT_LANGUAGE)
        else:
            # Fallback
            translator.set_language(translator.DEFAULT_LANGUAGE)
            print(f"   ✓ Langue par défaut utilisée: {translator.DEFAULT_LANGUAGE}")

        # Maintenant, importer et créer la fenêtre principale
        print("\n5. Importation des modules...")
        MainWindow = import_with_fallback()
        print("   ✓ Modules importés avec succès")

        print("\n6. Création de la fenêtre principale...")
        window = MainWindow()
        print("   ✓ Fenêtre principale créée")

        # Afficher la fenêtre
        print("\n7. Affichage de la fenêtre...")
        window.show()
        print("   ✓ Fenêtre affichée")

        # Démarrer la boucle d'événements
        print("\n8. Démarrage de la boucle d'événements...")
        print("=== APPLICATION EN COURS D'EXÉCUTION ===")
        print("=== Appuyez sur Ctrl+C pour arrêter ===\n")
        
        sys.exit(app.exec_())

    except KeyboardInterrupt:
        print("\n=== ARRÊT DEMANDÉ PAR L'UTILISATEUR ===")
        sys.exit(0)
        
    except ImportError as e:
        print(f"\n=== ERREUR D'IMPORTATION ===")
        print(f"Erreur: {str(e)}")
        logger.critical(f"Erreur d'importation: {str(e)}", exc_info=True)
        sys.exit(1)

    except Exception as e:
        print(f"\n=== ERREUR CRITIQUE ===")
        print(f"Erreur: {str(e)}")
        print(f"Type: {type(e).__name__}")
        traceback.print_exc()
        logger.critical(f"Erreur critique lors du démarrage: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()