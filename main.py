#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/main.py
Point d'entrée de l'application
Support Windows (via pygetwindow) et Linux (via wmctrl/xdotool)
Dépendances Linux: sudo apt-get install wmctrl xdotool xvfb
Dépendances Python: pip install pygetwindow python-xlib
"""

import sys
import os
import traceback
import platform
import subprocess
from datetime import datetime
from typing import List, Optional
from PyQt5 import QtWidgets
from PyQt5.QtCore import QSettings

from ui.localization.translator import translator, tr
from ui.widgets.language_selector import LanguageSelector
from utils.logger import logger


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
        """Move window to specified position"""
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-e', f'0,{x},{y},-1,-1'], 
                          check=True)
            self._x = x
            self._y = y
        except subprocess.CalledProcessError:
            pass
    
    def resizeTo(self, width: int, height: int):
        """Resize window to specified dimensions"""
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-e', f'0,-1,-1,{width},{height}'], 
                          check=True)
            self._width = width
            self._height = height
        except subprocess.CalledProcessError:
            pass
    
    def minimize(self):
        """Minimize the window"""
        try:
            subprocess.run(['xdotool', 'windowminimize', self._window_id], check=True)
        except subprocess.CalledProcessError:
            pass
    
    def maximize(self):
        """Maximize the window"""
        try:
            subprocess.run(['wmctrl', '-i', '-r', self._window_id, '-b', 'add,maximized_vert,maximized_horz'], 
                          check=True)
        except subprocess.CalledProcessError:
            pass
    
    def activate(self):
        """Activate/focus the window"""
        try:
            subprocess.run(['xdotool', 'windowactivate', self._window_id], check=True)
        except subprocess.CalledProcessError:
            pass
    
    def close(self):
        """Close the window"""
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
        # Use wmctrl to get window list with geometry
        result = subprocess.run(['wmctrl', '-l', '-G'], capture_output=True, text=True, check=True)
        
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 7:
                window_id = parts[0]
                desktop = parts[1]  # Desktop number (-1 for all desktops)
                x = int(parts[2])
                y = int(parts[3])
                width = int(parts[4])
                height = int(parts[5])
                title = ' '.join(parts[7:])
                
                # Filter out some system windows that might not be useful
                if (title and 
                    not title.startswith('@') and  # Skip @!0,0;BDHF type windows
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
        # Get active window ID
        result = subprocess.run(['xdotool', 'getactivewindow'], 
                              capture_output=True, text=True, check=True)
        window_id = result.stdout.strip()
        
        # Get window info
        result = subprocess.run(['xdotool', 'getwindowgeometry', window_id], 
                              capture_output=True, text=True, check=True)
        
        # Parse geometry
        x, y, width, height = 0, 0, 0, 0
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'Position:' in line:
                pos_part = line.split('Position:')[1].strip()
                # Handle format like "122,244 (screen: 0)" or just "122,244"
                if '(' in pos_part:
                    pos_part = pos_part.split('(')[0].strip()
                try:
                    x, y = map(int, pos_part.split(','))
                except ValueError:
                    # If parsing fails, try alternative method
                    coords = pos_part.replace(' ', '').split(',')
                    if len(coords) >= 2:
                        x, y = int(coords[0]), int(coords[1])
            elif 'Geometry:' in line:
                geo_part = line.split('Geometry:')[1].strip()
                width, height = map(int, geo_part.split('x'))
        
        # Get window title
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
    # S'assurer que le dossier courant est le dossier de l'application
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    # Ajouter le dossier racine au PYTHONPATH
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


def setup_platform_environment():
    """Configure l'environnement selon la plateforme"""
    system = platform.system()
    
    if system == "Linux":
        # Configuration pour Linux
        print(f"   → Plateforme détectée: Linux")
        
        # Vérifier si nous sommes dans un environnement headless
        display = os.environ.get('DISPLAY')
        if not display:
            print("   → Pas de DISPLAY détecté, configuration pour environnement headless")
            # Essayer de configurer un display virtuel
            try:
                result = subprocess.run(['which', 'xvfb-run'], capture_output=True)
                if result.returncode == 0:
                    print("   → Xvfb disponible")
                else:
                    print("   ⚠ Xvfb non disponible, certaines fonctionnalités peuvent ne pas fonctionner")
                    print("   → Installation suggérée: sudo apt-get install xvfb")
            except:
                pass
        
        # Vérifier la disponibilité des outils Linux pour la gestion des fenêtres
        try:
            tools_missing = []
            
            # Vérifier wmctrl
            try:
                subprocess.run(['wmctrl', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                tools_missing.append('wmctrl')
            
            # Vérifier xdotool
            try:
                subprocess.run(['xdotool', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                tools_missing.append('xdotool')
            
            if tools_missing:
                print(f"   ⚠ Outils manquants: {', '.join(tools_missing)}")
                print(f"   → Installation suggérée: sudo apt-get install {' '.join(tools_missing)}")
            else:
                print("   ✓ Outils de gestion des fenêtres Linux disponibles")
                
        except Exception as e:
            print(f"   ⚠ Erreur lors de la vérification des outils: {e}")
    
    elif system == "Windows":
        print(f"   → Plateforme détectée: Windows")
        print("   ✓ Support complet des fonctionnalités Windows")
    
    elif system == "Darwin":
        print(f"   → Plateforme détectée: macOS")
        print("   ⚠ Support macOS limité, certaines fonctionnalités peuvent ne pas fonctionner")
    
    else:
        print(f"   → Plateforme détectée: {system}")
        print("   ⚠ Plateforme non testée, certaines fonctionnalités peuvent ne pas fonctionner")


def import_with_fallback():
    """Importe MainWindow avec gestion des erreurs spécifiques à la plateforme"""
    system = platform.system()
    
    if system == "Linux":
        try:
            # Vérifier la disponibilité des outils Linux
            subprocess.run(['wmctrl', '--version'], capture_output=True, check=True)
            subprocess.run(['xdotool', '--version'], capture_output=True, check=True)
            print("   ✓ Outils Linux (wmctrl, xdotool) disponibles")
            
            # Définir les fonctions de gestion des fenêtres pour Linux
            sys.modules['pygetwindow'] = type('module', (), {
                'getAllWindows': getAllWindows,
                'getWindowsWithTitle': getWindowsWithTitle,
                'getActiveWindow': getActiveWindow,
                'getWindowsAt': getWindowsAt,
                'Win32Window': LinuxWindow  # Pour compatibilité avec les appels à pygetwindow.Win32Window
            })
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("   ✗ Erreur: Outils Linux manquants (wmctrl, xdotool)")
            print("   → Installation suggérée: sudo apt-get install wmctrl xdotool")
            raise ImportError(
                "Outils nécessaires (wmctrl, xdotool) non installés. "
                "Installez-les avec 'sudo apt-get install wmctrl xdotool'."
            )
    
    elif system == "Windows":
        try:
            import pygetwindow as gw
            sys.modules['pygetwindow'] = gw
        except ImportError:
            print("   ✗ Erreur: pygetwindow non disponible sur Windows")
            raise ImportError("pygetwindow n'est pas installé. Installez-le avec 'pip install pygetwindow'.")
    
    else:
        print(f"   ✗ Plateforme {system} non supportée pour la gestion des fenêtres")
        raise NotImplementedError(f"Plateforme {system} non supportée")
    
    try:
        from ui.main_window import MainWindow
        return MainWindow
    except ImportError as e:
        error_msg = str(e)
        if "pynput" in error_msg and system == "Linux":
            print("   ✗ Erreur: pynput nécessite un serveur X")
            print("   → Solution: Utiliser xvfb-run ou configurer DISPLAY")
            raise ImportError(
                "pynput nécessite un serveur X. "
                "Utilisez 'xvfb-run python3 main.py' ou configurez DISPLAY."
            )
        print(f"   ✗ Erreur d'importation: {error_msg}")
        raise


def main():
    print("\n=== DÉMARRAGE DE L'APPLICATION LIRIS ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Plateforme: {platform.system()} {platform.release()}")
    print(f"Répertoire actuel: {os.getcwd()}")

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
        
        # Configuration Qt pour les environnements headless
        if platform.system() == "Linux" and not os.environ.get('DISPLAY'):
            print("   → Configuration Qt pour environnement headless")
            app.setAttribute(QtWidgets.QApplication.AA_X11InitThreads, True)
        
        print("   ✓ QApplication créée")

        # Gérer la sélection de langue
        print("\n4. Sélection de la langue...")
        settings = QSettings("Liris", "IACollaborative")
        saved_language = settings.value("language", None)

        # IMPORTANT: Charger la langue AVANT de créer MainWindow
        if saved_language and saved_language in translator.get_available_languages():
            success = translator.set_language(saved_language)
            if success:
                print(f"   ✓ Langue restaurée: {saved_language}")
            else:
                print(f"   ✗ Erreur lors du chargement de {saved_language}")
                translator.set_language(translator.DEFAULT_LANGUAGE)
        else:
            # Première utilisation ou langue non disponible, montrer le sélecteur
            print("   → Première utilisation, affichage du sélecteur de langue")
            selector = LanguageSelector()

            # Trouver l'index du français par défaut
            for i in range(selector.language_combo.count()):
                if selector.language_combo.itemData(i) == "fr":
                    selector.language_combo.setCurrentIndex(i)
                    break

            if selector.exec_() == QtWidgets.QDialog.Accepted:
                selected_language = selector.get_selected_language()
                success = translator.set_language(selected_language)
                if success:
                    settings.setValue("language", selected_language)
                    print(f"   ✓ Langue sélectionnée: {selected_language}")
                else:
                    print(f"   ✗ Erreur lors du chargement de {selected_language}")
                    translator.set_language(translator.DEFAULT_LANGUAGE)
            else:
                # Si l'utilisateur annule, utiliser la langue par défaut
                translator.set_language(translator.DEFAULT_LANGUAGE)
                settings.setValue("language", translator.DEFAULT_LANGUAGE)
                print(f"   ✓ Langue par défaut utilisée: {translator.DEFAULT_LANGUAGE}")

        # Importer et créer la fenêtre principale avec gestion d'erreurs
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
        print("\n=== SOLUTIONS SUGGÉRÉES ===")
        
        if platform.system() == "Linux":
            print("Pour Linux:")
            print("1. Installer les dépendances système:")
            print("   sudo apt-get install python3-tk python3-dev xvfb wmctrl xdotool")
            print("2. Installer les dépendances Python:")
            print("   pip install python-xlib")
            print("3. Lancer avec display virtuel:")
            print("   xvfb-run -a python3 main.py")
            print("4. Ou configurer DISPLAY:")
            print("   export DISPLAY=:0.0")
        
        logger.critical(f"Erreur d'importation: {str(e)}")
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