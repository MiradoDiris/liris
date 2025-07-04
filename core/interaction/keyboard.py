import time
import pyautogui
import platform  # Import the platform module to detect OS
from utils.logger import logger
from utils.exceptions import InteractionError


class KeyboardController:
    """
    Classe pour contrôler le clavier à l'aide de PyAutoGUI
    """

    def __init__(self, typing_speed='normal'):
        """
        Initialise le contrôleur de clavier

        Args:
            typing_speed (str): Vitesse de frappe ('slow', 'normal', 'fast')
        """
        logger.info("Initialisation du contrôleur de clavier")

        # Configuration de la vitesse de frappe
        self.typing_speeds = {
            'slow': 0.1,
            'normal': 0.05,
            'fast': 0.01
        }

        self.typing_interval = self.typing_speeds.get(typing_speed, 0.05)

        # Désactiver le failsafe de PyAutoGUI (optionnel)
        pyautogui.FAILSAFE = True

        # Determine the primary modifier key for the current OS
        self.modifier_key = self._get_os_modifier_key()

    def _get_os_modifier_key(self):
        """
        Détermine la touche de modification principale ('ctrl' ou 'command')
        en fonction du système d'exploitation.
        """
        if platform.system() == "Darwin":  # macOS
            return 'command'
        else:  # Windows, Linux, etc.
            return 'ctrl'

    def type_text(self, text, interval=None):
        """
        Tape le texte avec la vitesse configurée

        Args:
            text (str): Texte à saisir
            interval (float, optional): Intervalle entre les frappes (secondes)

        Returns:
            bool: True si la saisie a réussi, False sinon
        """
        try:
            interval = interval if interval is not None else self.typing_interval
            pyautogui.write(text, interval=interval)
            logger.debug(f"Texte saisi: {text[:20]}{'...' if len(text) > 20 else ''}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la saisie de texte: {str(e)}")
            raise InteractionError(f"Échec de la saisie clavier: {str(e)}")

    def press_key(self, key):
        """
        Appuie sur une touche spécifique

        Args:
            key (str): Touche à appuyer (format PyAutoGUI)

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        try:
            pyautogui.press(key)
            logger.debug(f"Touche pressée: {key}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'appui sur la touche {key}: {str(e)}")
            raise InteractionError(f"Échec de l'appui sur la touche: {str(e)}")

    def hotkey(self, *keys):
        """
        Utilise une combinaison de touches.
        Adapte la touche de modification (Ctrl/Command) en fonction de l'OS.

        Args:
            *keys: Liste des touches à appuyer simultanément. 'ctrl' will be
                   automatically replaced with 'command' on macOS.

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        try:
            # Replace 'ctrl' with the appropriate modifier key for the OS
            adjusted_keys = [self.modifier_key if key == 'ctrl' else key for key in keys]
            pyautogui.hotkey(*adjusted_keys)
            logger.debug(f"Combinaison de touches utilisée: {' + '.join(adjusted_keys)}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'utilisation de la combinaison: {str(e)}")
            raise InteractionError(f"Échec de la combinaison de touches: {str(e)}")

    def clear_field(self):
        """
        Efface le contenu d'un champ (sélectionne tout puis supprime)
        S'adapte à l'OS pour la touche de sélection.

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        try:
            # Select all (Ctrl+A or Command+A)
            self.hotkey(self.modifier_key, 'a')
            time.sleep(0.1) # Small delay to ensure selection registers

            # Delete
            pyautogui.press('delete')
            logger.debug("Champ effacé")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'effacement du champ: {str(e)}")
            raise InteractionError(f"Échec de l'effacement: {str(e)}")

    def press_enter(self):
        """
        Appuie sur la touche Entrée

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        return self.press_key('enter')

    def press_tab(self):
        """
        Appuie sur la touche Tab

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        return self.press_key('tab')

    def copy_to_clipboard(self):
        """
        Copie la sélection dans le presse-papiers (Ctrl+C ou Command+C)

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        return self.hotkey(self.modifier_key, 'c')

    def paste_from_clipboard(self):
        """
        Colle le contenu du presse-papiers (Ctrl+V ou Command+V)

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        return self.hotkey(self.modifier_key, 'v')

    def cut_to_clipboard(self):
        """
        Coupe la sélection dans le presse-papiers (Ctrl+X ou Command+X)

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        return self.hotkey(self.modifier_key, 'x')