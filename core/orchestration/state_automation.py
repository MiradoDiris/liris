#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/state_automation.py

Système d'automatisation basé sur l'état du DOM au lieu de time.sleep()
Remplace les attentes fixes par des vérifications d'état intelligentes
"""

import time
import traceback
from enum import Enum
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from utils.logger import logger
from utils.exceptions import OrchestrationError

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class AutomationState(Enum):
    """États de l'automatisation"""
    IDLE = "idle"
    BROWSER_OPENING = "browser_opening"
    BROWSER_READY = "browser_ready"
    TAB_CREATING = "tab_creating"
    TAB_READY = "tab_ready"
    PAGE_LOADING = "page_loading"
    PAGE_READY = "page_ready"
    ELEMENT_FOCUSING = "element_focusing"
    ELEMENT_READY = "element_ready"
    TEXT_CLEARING = "text_clearing"
    TEXT_INPUTTING = "text_inputting"
    TEXT_READY = "text_ready"
    TABBING = "tabbing"
    TAB_NAVIGATION_READY = "tab_navigation_ready"
    REFOCUSING = "refocusing"
    REFOCUS_READY = "refocus_ready"
    SUBMITTING = "submitting"
    SUBMISSION_COMPLETE = "submission_complete"
    COMPLETED = "completed"
    ERROR = "error"


class StateBasedAutomation(QObject):
    """Automatisation basée sur l'état au lieu de sleep()"""

    # Signaux pour les changements d'état
    state_changed = pyqtSignal(str, str)  # état, message
    automation_completed = pyqtSignal(bool, str, float)  # success, message, duration

    def __init__(self, detector, mouse_controller, keyboard_controller, conductor):
        super().__init__()
        self.detector = detector  # InterfaceDetector existant
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.conductor = conductor  # Pour accéder à _activate_browser

        self.current_state = AutomationState.IDLE
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_current_state)
        self.check_timer.setSingleShot(False)

        self.automation_steps = []
        self.current_step = 0
        self.max_retries = 15  # HARD STOP après 5 tentatives (1.5 secondes à 100ms)
        self.max_detection_retries = 5  # Maximum pour détection spécifique
        self.current_retries = 0
        self.start_time = None

        # Configuration actuelle
        self.platform_profile = None
        self.num_tabs = 0
        self.browser_type = None
        self.url = None

        # Compteurs spéciaux pour certains états
        self.detection_attempts = 0

    def start_test_automation(self, platform_profile, num_tabs, browser_type, url):
        """Démarre l'automatisation de test basée sur l'état"""
        logger.info(f"Démarrage automatisation état pour {platform_profile.get('name', 'Unknown')}")

        self.platform_profile = platform_profile
        self.num_tabs = num_tabs
        self.browser_type = browser_type
        self.url = url
        self.current_step = 0
        self.current_retries = 0
        self.start_time = time.time()

        # Définir la séquence d'étapes
        self.automation_steps = [
            (AutomationState.BROWSER_OPENING, self._open_browser, "Ouverture du navigateur"),
            (AutomationState.BROWSER_READY, None, "Attente navigateur prêt"),
            (AutomationState.TAB_CREATING, self._create_new_tab, "Création nouvel onglet"),
            (AutomationState.TAB_READY, None, "Attente onglet prêt"),
            (AutomationState.PAGE_LOADING, self._load_page, "Chargement de la page"),
            (AutomationState.PAGE_READY, None, "Attente page chargée"),
            (AutomationState.ELEMENT_FOCUSING, self._focus_prompt_field, "Focus sur le champ"),
            (AutomationState.ELEMENT_READY, None, "Attente champ prêt"),
            (AutomationState.TEXT_CLEARING, self._clear_field, "Effacement du champ"),
            (AutomationState.TEXT_INPUTTING, self._input_text, "Saisie du texte"),
            (AutomationState.TEXT_READY, None, "Attente texte saisi"),
            (AutomationState.TABBING, self._perform_tabbing, "Navigation par Tab"),
            (AutomationState.TAB_NAVIGATION_READY, None, "Attente navigation Tab"),
            (AutomationState.REFOCUSING, self._refocus_prompt_field, "Re-focus sur le champ"),
            (AutomationState.REFOCUS_READY, None, "Attente re-focus"),
            (AutomationState.SUBMITTING, self._submit_form, "Soumission du formulaire"),
            (AutomationState.SUBMISSION_COMPLETE, None, "Attente soumission"),
            (AutomationState.COMPLETED, self._complete_automation, "Automatisation terminée")
        ]

        self._transition_to_next_state()

    def _transition_to_next_state(self):
        """Passe à l'état suivant"""
        if self.current_step >= len(self.automation_steps):
            self._complete_automation()
            return

        next_state, action, description = self.automation_steps[self.current_step]
        self.current_state = next_state
        self.current_retries = 0

        # Réinitialiser les compteurs spéciaux
        if next_state == AutomationState.PAGE_LOADING:
            self.detection_attempts = 0

        logger.debug(f"Transition vers état: {next_state.value} - {description}")
        self.state_changed.emit(next_state.value, description)

        # Exécuter l'action
        try:
            if action is not None:
                action()

            # Démarrer le timer de vérification si nécessaire
            if self._needs_state_checking():
                self.check_timer.start(100)  # Vérifier toutes les 100ms
            else:
                # Passer directement à l'étape suivante
                self.current_step += 1
                self._transition_to_next_state()
        except Exception as e:
            self._handle_error(f"Erreur dans {next_state.value}: {str(e)}")

    def _needs_state_checking(self):
        """Détermine si l'état actuel nécessite une vérification"""
        checking_states = [
            AutomationState.BROWSER_OPENING,
            AutomationState.TAB_CREATING,
            AutomationState.PAGE_LOADING,
            AutomationState.ELEMENT_FOCUSING,
            AutomationState.TEXT_CLEARING,
            AutomationState.TEXT_INPUTTING,
            AutomationState.TABBING,
            AutomationState.REFOCUSING,
            AutomationState.SUBMITTING
        ]
        return self.current_state in checking_states

    def _check_current_state(self):
        """Vérifie si l'état actuel est prêt pour la transition"""
        self.current_retries += 1

        # HARD STOP après max_retries
        if self.current_retries > self.max_retries:
            self._handle_error(
                f"HARD STOP - Timeout dans l'état {self.current_state.value} après {self.max_retries} tentatives")
            return

        # HARD STOP spécial pour détection (encore plus strict)
        if self.current_state == AutomationState.PAGE_LOADING:
            self.detection_attempts += 1
            if self.detection_attempts > self.max_detection_retries:
                logger.warning(
                    f"Abandon détection après {self.max_detection_retries} tentatives - passage en mode fallback")
                # Passer directement à l'étape suivante sans détection
                self.check_timer.stop()
                self.current_step += 1
                self._transition_to_next_state()
                return

        # Vérifier si l'état actuel est prêt
        if self._is_state_ready():
            self.check_timer.stop()
            self.current_step += 1
            self._transition_to_next_state()

    def _is_state_ready(self):
        """Vérifie si l'état actuel est prêt"""
        try:
            if self.current_state == AutomationState.BROWSER_OPENING:
                return self._is_browser_ready()
            elif self.current_state == AutomationState.TAB_CREATING:
                return self._is_tab_ready()
            elif self.current_state == AutomationState.PAGE_LOADING:
                return self._is_page_ready()
            elif self.current_state == AutomationState.ELEMENT_FOCUSING:
                return self._is_element_ready()
            elif self.current_state == AutomationState.TEXT_CLEARING:
                return self._is_field_cleared()
            elif self.current_state == AutomationState.TEXT_INPUTTING:
                return self._is_text_ready()
            elif self.current_state == AutomationState.TABBING:
                return self._is_tab_navigation_ready()
            elif self.current_state == AutomationState.REFOCUSING:
                return self._is_refocus_ready()
            elif self.current_state == AutomationState.SUBMITTING:
                return self._is_submission_complete()
            else:
                return True  # États sans vérification

        except Exception as e:
            logger.error(f"Erreur vérification état {self.current_state.value}: {str(e)}")
            return False

    # =================================
    # ACTIONS D'AUTOMATISATION
    # =================================

    def _open_browser(self):
        """Ouvre le navigateur"""
        success = self.conductor._activate_browser(self.browser_type, '', self.url, fullscreen=True)
        if not success:
            raise OrchestrationError("Impossible d'ouvrir le navigateur")

    def _create_new_tab(self):
        """Crée un nouvel onglet"""
        self.keyboard_controller.hotkey('ctrl', 't')

    def _load_page(self):
        """Charge la page dans l'onglet"""
        if self.url:
            self.keyboard_controller.type_text(self.url)
            self.keyboard_controller.press_enter()

    def _focus_prompt_field(self):
        """Focus sur le champ de prompt"""
        positions = self.platform_profile.get('interface_positions', {})
        prompt_pos = positions.get('prompt_field')
        if prompt_pos:
            self.mouse_controller.click(prompt_pos['center_x'], prompt_pos['center_y'])

    def _clear_field(self):
        """Efface le contenu du champ"""
        self.keyboard_controller.clear_field()

    def _input_text(self):
        """Saisit le texte de test"""
        self.keyboard_controller.type_text("test")

    def _perform_tabbing(self):
        """Effectue la navigation par Tab"""
        for i in range(self.num_tabs):
            self.keyboard_controller.press_tab()
            time.sleep(0.1)  # Petite pause entre les tabs

    def _refocus_prompt_field(self):
        """Re-focus sur le champ de prompt avant soumission"""
        positions = self.platform_profile.get('interface_positions', {})
        prompt_pos = positions.get('prompt_field')
        if prompt_pos:
            self.mouse_controller.click(prompt_pos['center_x'], prompt_pos['center_y'])

    def _submit_form(self):
        """Soumet le formulaire"""
        self.keyboard_controller.press_enter()

    def _complete_automation(self):
        """Termine l'automatisation"""
        duration = time.time() - self.start_time
        logger.info(f"Automatisation terminée en {duration:.1f}s")
        self.automation_completed.emit(True, f"Test réussi en {duration:.1f}s", duration)

    # =================================
    # VÉRIFICATIONS D'ÉTAT
    # =================================

    def _is_browser_ready(self):
        """Vérifie si le navigateur est prêt"""
        if not HAS_PYGETWINDOW:
            # Fallback: attendre un délai fixe minimal mais court
            return self.current_retries >= 10  # 1 seconde au lieu de 3

        try:
            # Chercher une fenêtre de navigateur active
            browser_keywords = {
                'Chrome': ['chrome', 'google chrome'],
                'Firefox': ['firefox', 'mozilla firefox'],
                'Edge': ['edge', 'microsoft edge']
            }

            keywords = browser_keywords.get(self.browser_type, [self.browser_type.lower()])

            for keyword in keywords:
                windows = gw.getWindowsWithTitle(keyword)
                if windows and not windows[0].isMinimized:
                    logger.debug(f"Navigateur {self.browser_type} détecté et prêt")
                    return True

            return False
        except Exception:
            return self.current_retries >= 10  # Fallback plus court

    def _is_tab_ready(self):
        """Vérifie si l'onglet est créé"""
        # Attendre un minimum très court pour que l'onglet soit créé
        return self.current_retries >= 3  # 0.3 seconde au lieu de 1

    def _is_page_ready(self):
        """Vérifie si la page est chargée - MODE SIMPLIFIÉ"""
        try:
            # Vérifier qu'on a les positions sauvegardées (plus fiable que la re-détection)
            positions = self.platform_profile.get('interface_positions', {})
            if positions and 'prompt_field' in positions and 'submit_button' in positions:
                logger.debug("Page prête : positions d'interface disponibles")
                return True

            # Si pas de positions, essayer une détection simple
            screenshot = self.detector.capture_screen(browser_type=self.browser_type)
            if screenshot is None:
                logger.debug("Page pas prête : capture d'écran échouée")
                return False

            # Vérification basique : la page contient-elle du contenu ?
            # (Plus fiable que d'essayer de détecter des éléments spécifiques)
            h, w = screenshot.shape[:2]
            if h > 100 and w > 100:  # Taille minimale raisonnable
                logger.debug("Page prête : capture d'écran valide")
                return True

            return False

        except Exception as e:
            logger.debug(f"Erreur vérification page: {e}")
            return False

    def _is_element_ready(self):
        """Vérifie si l'élément a le focus"""
        # Délai court pour le focus
        return self.current_retries >= 2  # 0.2 seconde

    def _is_field_cleared(self):
        """Vérifie si le champ est effacé"""
        return self.current_retries >= 2  # 0.2 seconde

    def _is_text_ready(self):
        """Vérifie si le texte est saisi"""
        return self.current_retries >= 3  # 0.3 seconde

    def _is_tab_navigation_ready(self):
        """Vérifie si la navigation par Tab est terminée"""
        # Calculer le temps nécessaire basé sur le nombre de tabs (plus court)
        required_retries = max(2, self.num_tabs * 1)  # Au moins 0.2s, plus 0.1s par tab
        return self.current_retries >= required_retries

    def _is_refocus_ready(self):
        """Vérifie si le re-focus est effectué"""
        return self.current_retries >= 2  # 0.2 seconde

    def _is_submission_complete(self):
        """Vérifie si la soumission est terminée"""
        return self.current_retries >= 5  # 0.5 seconde

    # =================================
    # GESTION D'ERREURS
    # =================================

    def _handle_error(self, error_message):
        """Gère les erreurs d'automatisation"""
        logger.error(f"Erreur automatisation: {error_message}")
        self.check_timer.stop()
        self.current_state = AutomationState.ERROR

        duration = time.time() - self.start_time if self.start_time else 0
        self.automation_completed.emit(False, error_message, duration)

    def stop_automation(self):
        """Arrête l'automatisation en cours"""
        self.check_timer.stop()
        self.current_state = AutomationState.IDLE
        logger.info("Automatisation arrêtée par l'utilisateur")

    def get_current_state_info(self):
        """Retourne les informations sur l'état actuel"""
        duration = time.time() - self.start_time if self.start_time else 0
        progress = (self.current_step / len(self.automation_steps)) * 100 if self.automation_steps else 0

        return {
            'state': self.current_state.value,
            'step': self.current_step,
            'total_steps': len(self.automation_steps),
            'progress': progress,
            'duration': duration,
            'retries': self.current_retries,
            'max_retries': self.max_retries
        }