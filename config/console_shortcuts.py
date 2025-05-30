#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
config/console_shortcuts.py - Configuration des raccourcis console par navigateur

Ce module gère les raccourcis clavier pour ouvrir la console de développement
selon le navigateur utilisé et le système d'exploitation.
"""

import platform
from typing import Dict, List, Tuple, Optional
from utils.logger import logger


class ConsoleShortcuts:
    """Gestionnaire des raccourcis console selon le navigateur et l'OS"""

    # Configuration des raccourcis par navigateur et OS
    SHORTCUTS = {
        "chrome": {
            "windows": ["ctrl+shift+j", "f12"],
            "linux": ["ctrl+shift+j", "f12"],
            "darwin": ["cmd+option+j", "f12"]  # darwin = macOS
        },
        "chromium": {
            "windows": ["ctrl+shift+j", "f12"],
            "linux": ["ctrl+shift+j", "f12"],
            "darwin": ["cmd+option+j", "f12"]
        },
        "firefox": {
            "windows": ["ctrl+shift+k", "f12"],
            "linux": ["ctrl+shift+k", "f12"],
            "darwin": ["cmd+option+k", "f12"]
        },
        "mozilla": {  # Alias pour Firefox
            "windows": ["ctrl+shift+k", "f12"],
            "linux": ["ctrl+shift+k", "f12"],
            "darwin": ["cmd+option+k", "f12"]
        },
        "edge": {
            "windows": ["f12", "ctrl+shift+i"],
            "linux": ["f12", "ctrl+shift+i"],
            "darwin": ["f12", "cmd+option+i"]
        },
        "safari": {
            "darwin": ["cmd+option+c"]  # Safari nécessite d'activer le menu Develop
        },
        "opera": {
            # Note: Opera ne supporte pas F12 par défaut pour les DevTools
            "windows": ["ctrl+shift+j", "ctrl+shift+i"],
            "linux": ["ctrl+shift+j", "ctrl+shift+i"],
            "darwin": ["cmd+option+j", "cmd+option+i"]
        },
        "brave": {
            "windows": ["ctrl+shift+j", "f12"],
            "linux": ["ctrl+shift+j", "f12"],
            "darwin": ["cmd+option+j", "f12"]
        }
    }

    # Navigation vers l'onglet Console après ouverture
    CONSOLE_TAB_NAVIGATION = {
        "chrome": "ctrl+]",  # Ou utiliser les flèches
        "firefox": None,  # S'ouvre directement sur Console
        "edge": "ctrl+]",
        "safari": None  # S'ouvre directement sur Console
    }

    def __init__(self):
        """Initialise le gestionnaire de raccourcis"""
        self.current_os = platform.system().lower()
        logger.info(f"ConsoleShortcuts initialisé - OS détecté: {self.current_os}")

    def get_console_shortcut(self, browser_name: str) -> List[str]:
        """
        Retourne les raccourcis pour ouvrir la console selon le navigateur

        Args:
            browser_name: Nom du navigateur (chrome, firefox, edge, etc.)

        Returns:
            Liste des raccourcis possibles (le premier est le principal)
        """
        browser = browser_name.lower()

        # Normaliser les noms de navigateur
        if "chrome" in browser and "chromium" not in browser:
            browser = "chrome"
        elif "firefox" in browser or "mozilla" in browser:
            browser = "firefox"
        elif "edge" in browser:
            browser = "edge"
        elif "safari" in browser:
            browser = "safari"
        elif "opera" in browser:
            browser = "opera"
        elif "brave" in browser:
            browser = "brave"

        # Obtenir les raccourcis selon l'OS
        if browser in self.SHORTCUTS:
            os_shortcuts = self.SHORTCUTS[browser].get(self.current_os, [])
            if os_shortcuts:
                logger.info(f"Raccourcis console pour {browser} sur {self.current_os}: {os_shortcuts}")
                return os_shortcuts

        # Fallback générique
        logger.warning(f"Navigateur '{browser}' non reconnu, utilisation du raccourci par défaut F12")
        return ["f12"]

    def get_primary_shortcut(self, browser_name: str) -> str:
        """Retourne le raccourci principal (recommandé) pour un navigateur"""
        shortcuts = self.get_console_shortcut(browser_name)
        return shortcuts[0] if shortcuts else "f12"

    def prepare_console_sequence(self, browser_name: str, keyboard_controller) -> List[Tuple[str, float]]:
        """
        Prépare la séquence complète pour ouvrir la console

        Args:
            browser_name: Nom du navigateur
            keyboard_controller: Contrôleur clavier pour exécuter les commandes

        Returns:
            Liste de tuples (commande, délai_après) pour exécuter la séquence
        """
        sequence = []

        # 1. Petit délai initial pour s'assurer que le navigateur est prêt
        sequence.append(("delay", 0.2))  # Délai sans action

        # 2. Obtenir le raccourci principal
        shortcut = self.get_primary_shortcut(browser_name)
        sequence.append((shortcut, 0.8))  # Plus de temps pour que la console s'ouvre

        # 3. Navigation vers l'onglet Console si nécessaire
        browser = browser_name.lower()
        if browser in self.CONSOLE_TAB_NAVIGATION and self.CONSOLE_TAB_NAVIGATION[browser]:
            sequence.append((self.CONSOLE_TAB_NAVIGATION[browser], 0.3))

        return sequence

    def execute_console_open(self, browser_name: str, keyboard_controller):
        """
        Exécute l'ouverture de la console avec la bonne séquence

        Args:
            browser_name: Nom du navigateur
            keyboard_controller: Contrôleur clavier

        Note:
            Assume que le focus est déjà sur la fenêtre du navigateur
        """
        import time

        try:
            logger.info(f"🔧 Ouverture console pour {browser_name}")

            # Préparer la séquence
            sequence = self.prepare_console_sequence(browser_name, keyboard_controller)

            # Exécuter la séquence
            for command, delay in sequence:
                if command == "delay":
                    # Simple délai sans action
                    time.sleep(delay)
                    logger.debug(f"Délai initial de {delay}s")
                elif "+" in command:
                    # C'est un hotkey (ex: ctrl+shift+j)
                    keys = command.split("+")
                    keyboard_controller.hotkey(*keys)
                    time.sleep(delay)
                    logger.debug(f"Exécuté: {command}, attente {delay}s")
                else:
                    # C'est une touche simple (ex: f12)
                    keyboard_controller.press_key(command)
                    time.sleep(delay)
                    logger.debug(f"Exécuté: {command}, attente {delay}s")

            logger.info("✅ Console ouverte avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur ouverture console: {e}")
            # Fallback sur F12 (sauf pour Opera)
            if browser_name.lower() != "opera":
                try:
                    keyboard_controller.press_key('f12')
                    time.sleep(0.5)
                    logger.info("Fallback F12 exécuté")
                    return True
                except:
                    return False
            return False

    def close_console(self, browser_name: str, keyboard_controller):
        """
        Ferme la console (généralement le même raccourci)

        Args:
            browser_name: Nom du navigateur
            keyboard_controller: Contrôleur clavier
        """
        import time

        try:
            # La plupart des navigateurs utilisent le même raccourci pour fermer
            shortcut = self.get_primary_shortcut(browser_name)

            if "+" in shortcut:
                keys = shortcut.split("+")
                keyboard_controller.hotkey(*keys)
            else:
                keyboard_controller.press_key(shortcut)

            time.sleep(0.3)
            logger.info("Console fermée")

        except Exception as e:
            logger.error(f"Erreur fermeture console: {e}")
            # Tentative avec F12 (sauf pour Opera)
            if browser_name.lower() != "opera":
                try:
                    keyboard_controller.press_key('f12')
                except:
                    pass

    def get_special_instructions(self, browser_name: str) -> Optional[str]:
        """
        Retourne des instructions spéciales pour certains navigateurs

        Args:
            browser_name: Nom du navigateur

        Returns:
            Instructions spéciales ou None
        """
        browser = browser_name.lower()

        if "safari" in browser:
            return (
                "⚠️ Safari nécessite d'activer le menu Develop:\n"
                "1. Safari → Preferences → Advanced\n"
                "2. Cocher 'Show Develop menu in menu bar'\n"
                "3. Ensuite utiliser Cmd+Option+C"
            )

        if "opera" in browser:
            return (
                "⚠️ Opera n'utilise pas F12 par défaut pour les DevTools.\n"
                "Utilisez Ctrl+Shift+J (console) ou Ctrl+Shift+I (DevTools)"
            )

        return None


# Instance globale pour utilisation facile
console_shortcuts = ConsoleShortcuts()


# Fonction utilitaire pour intégration facile
def open_console_for_browser(browser_name: str, keyboard_controller) -> bool:
    """
    Ouvre la console pour un navigateur donné

    Args:
        browser_name: Nom du navigateur
        keyboard_controller: Instance du contrôleur clavier

    Returns:
        True si succès, False sinon

    Note:
        Cette fonction assume que le focus est déjà sur la fenêtre du navigateur.
        Si ce n'est pas le cas, cliquez d'abord sur la fenêtre du navigateur.
    """
    return console_shortcuts.execute_console_open(browser_name, keyboard_controller)


def close_console_for_browser(browser_name: str, keyboard_controller):
    """Ferme la console pour un navigateur donné"""
    console_shortcuts.close_console(browser_name, keyboard_controller)


# Tests
if __name__ == "__main__":
    # Test des raccourcis
    cs = ConsoleShortcuts()

    browsers = ["chrome", "firefox", "edge", "safari", "opera", "brave", "MyCustomChrome", "Mozilla Firefox"]

    print(f"Système d'exploitation détecté: {cs.current_os}\n")

    for browser in browsers:
        print(f"Navigateur: {browser}")
        shortcuts = cs.get_console_shortcut(browser)
        print(f"  Raccourcis: {shortcuts}")
        print(f"  Principal: {cs.get_primary_shortcut(browser)}")

        special = cs.get_special_instructions(browser)
        if special:
            print(f"  Instructions spéciales:\n    {special}")

        print()